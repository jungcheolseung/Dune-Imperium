"""Every line of a Scouts choice, the ones a seat cannot take too (display).

User request 2026-09-29: a cost line the seat cannot take right now is shown
but not selectable, with the reason, and it becomes selectable as soon as the
seat can take it (and the reverse). The engine's legal actions stay exactly
as they are: a line is offered only when ``line_is_offered`` (OQ-046,
OQ-071), a subcommittee only when ``joinable_subcommittees`` (OQ-076), a
mission's way in only when ``join_targets`` (OQ-088). These tests pin the
display to those same checks.
"""

import random
from dataclasses import replace
from typing import Any, cast

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.arrakeen_scouts import (
    EVENTS_BY_ID,
    MISSIONS_BY_ID,
    SALES_BY_ID,
    SUBCOMMITTEES_BY_ID,
    ScoutsOption,
)
from dune_imperium.content.arrakeen_scouts.types import ScoutsCost, ScoutsReward
from dune_imperium.content.uprising.effect_dsl import PayResources
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.display.scouts import (
    scouts_choice_lines,
    scouts_option_text,
    scouts_option_text_ko,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.scouts_effects import (
    line_is_offered,
    line_unavailable_reason,
    offer_scouts_choice,
    option_is_affordable,
    reward_has_effect,
)
from dune_imperium.rules.scouts_missions import (
    join_targets,
    join_unavailable_reason,
    offer_mission_join,
)

ENGINE = UprisingRulesEngine()
SCOUTS = RulesetConfig(arrakeen_scouts=True)
LINE_ACTIONS = frozenset(
    {"scouts_choose_option", "join_subcommittee", "scouts_join_mission"}
)


def _state(
    owner: PlayerState, *, config: RulesetConfig = SCOUTS, **fields: Any
) -> GameState:
    values: dict[str, Any] = {
        "config": config,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 2,
        "first_player": 0,
        "players": (owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
    }
    values.update(fields)
    return GameState(**values)


def _owner(**overrides: Any) -> PlayerState:
    values: dict[str, Any] = {
        "player_id": 0,
        "hand": starting_deck_instance_ids(0),
        "resources": Resources(solari=5, spice=5, water=1),
    }
    values.update(overrides)
    return PlayerState(**values)


def _lines(state: GameState) -> tuple[dict[str, Any], tuple[DomainAction, ...]]:
    legal = ENGINE.legal_actions(state, 0)
    info = scouts_choice_lines(state, 0, legal)
    assert info is not None
    return info, legal


def _line_actions(legal: tuple[DomainAction, ...]) -> set[DomainAction]:
    return {action for action in legal if action.action_id in LINE_ACTIONS}


def _enabled(
    info: dict[str, Any], legal: tuple[DomainAction, ...]
) -> set[DomainAction]:
    return {legal[line["action_index"]] for line in info["lines"] if line["enabled"]}


def test_a_cost_line_without_a_reward_has_no_trailing_arrow() -> None:
    crackdown = EVENTS_BY_ID["crackdown"].options
    assert [scouts_option_text(option) for option in crackdown] == [
        "Recall a Spy",
        "Lose 1 Emperor Influence",
    ]
    assert scouts_option_text_ko(crackdown[0]) == "{spy} 소환"


def test_a_sale_shows_its_unpayable_line_disabled_with_the_reason() -> None:
    owner = _owner(resources=Resources(solari=5, spice=2))
    offered = offer_scouts_choice(
        _state(owner), 0, "unravel_the_future", source="round:2:scouts"
    )
    info, legal = _lines(offered.state)

    assert info["frame"] == "scouts_choice"
    assert info["item_id"] == "unravel_the_future"
    cheap, dear = info["lines"]
    # The pass comes first in the legal list; the line's own row is next.
    assert legal[cheap["action_index"]] == DomainAction(
        action_id="scouts_choose_option", actor=0, arguments=(("option", 0),)
    )
    assert cheap["enabled"] and cheap["reason"] is None
    assert cheap["text"] == "Pay 1 spice → Draw 1 card"
    assert dear["action_index"] is None and not dear["enabled"]
    assert dear["text"] == "Pay 3 spice → Draw 2 cards"
    assert (dear["reason"], dear["reason_ko"], dear["code"]) == (
        "Needs 3 spice (you have 2)",
        "{spice:3} 필요 (보유 2)",
        "cost",
    )
    assert _enabled(info, legal) == _line_actions(legal)


def test_a_subcommittee_offer_lists_claimed_unpayable_and_idle_lines() -> None:
    # Contingencies can be paid (an Intrigue card) but its recall cannot
    # happen: the one Agent out took the seat (OQ-071, OQ-075).
    owner = _owner(
        intrigue_cards=("intrigue:0",),
        agents_available=1,
        agent_locations=("high_council",),
    )
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_SUBCOMMITTEE,
        frame_id="offer:subcommittee",
        decision=PlayerDecision(owner=0, prompt="Join a subcommittee or decline"),
        context=(
            ("exclude_space", "high_council"),
            ("player", 0),
            ("source", "offer"),
            ("turn_closed", False),
        ),
    )
    state = _state(
        owner,
        scouts_subcommittees=("contingencies", "oversight", "readiness", "relations"),
        scouts_subcommittee_members=(("readiness", 2),),
        decision_stack=(frame,),
    )
    info, legal = _lines(state)

    assert info["frame"] == "scouts_subcommittee" and info["item_id"] is None
    lines = {line["subcommittee_id"]: line for line in info["lines"]}
    assert list(lines) == ["contingencies", "oversight", "readiness", "relations"]
    assert (lines["contingencies"]["reason"], lines["contingencies"]["code"]) == (
        "No other Agent to recall",
        "reward",
    )
    assert lines["contingencies"]["reason_ko"] == "소환할 다른 {agent} 없음"
    assert lines["oversight"]["reason"] == "Needs 1 Spy on the board (you have 0)"
    assert lines["readiness"]["code"] == "claimed"
    assert lines["readiness"]["seat"] == 2
    assert lines["relations"]["enabled"]
    assert lines["relations"]["text"] == (
        "Relations: Pay 2 spice → Gain 1 Influence (choose any Faction)"
    )
    assert _enabled(info, legal) == _line_actions(legal)


def test_fedaykin_assistance_lights_up_after_the_specimen_returns() -> None:
    """Supply 1, a specimen 1: the way in needs 2 supply troops, so it is
    greyed out until the seat returns the specimen [Immortality p. 8]
    (user ruling 2026-09-29, OQ-074, OQ-088)."""

    config = RulesetConfig(arrakeen_scouts=True, immortality=True)
    owner = _owner(troops_supply=1, troops_garrison=10, specimens=1)
    state = offer_mission_join(
        _state(owner, config=config), 0, "fedaykin_assistance", source="mission"
    ).state
    info, legal = _lines(state)

    (line,) = info["lines"]
    assert info["frame"] == "scouts_mission"
    assert info["item_id"] == "fedaykin_assistance"
    assert line["text"] == "Pay 1 spice, park 2 supply troops at Desert Tactics"
    assert not line["enabled"]
    assert (line["reason"], line["reason_ko"], line["code"]) == (
        "Needs 2 troops in your supply (you have 1)",
        "{supply}에 {troop:2} 필요 (보유 1)",
        "supply",
    )
    top_up = DomainAction(
        action_id="scouts_return_specimens", actor=0, arguments=(("count", 1),)
    )
    assert top_up in legal

    topped = ENGINE.apply(state, top_up).state
    info, legal = _lines(topped)
    (line,) = info["lines"]
    assert line["enabled"] and line["reason"] is None
    assert legal[line["action_index"]].action_id == "scouts_join_mission"


def test_choam_escort_without_a_contract_shows_the_contract_way_greyed_out() -> None:
    config = RulesetConfig(arrakeen_scouts=True, choam_module=True)
    state = offer_mission_join(
        _state(_owner(), config=config), 0, "choam_escort", source="mission"
    ).state
    info, legal = _lines(state)

    recruit, contract = info["lines"]
    assert recruit["enabled"] and recruit["text"] == "Recruit 1 troop"
    assert not contract["enabled"] and contract["code"] == "contract"
    assert contract["reason"] == "You have no face-up Contract"
    assert _enabled(info, legal) == _line_actions(legal)


def test_a_secret_pick_and_other_decisions_have_no_lines() -> None:
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_SECRET,
        frame_id="secret",
        decision=PlayerDecision(owner=0, prompt="Pick"),
        context=(("event_id", "covert_operation"),),
    )
    state = _state(_owner(), decision_stack=(frame,))
    assert scouts_choice_lines(state, 0, ENGINE.legal_actions(state, 0)) is None
    # Another seat's Scouts choice is never listed for this seat.
    offered = offer_scouts_choice(
        _state(_owner()), 0, "unravel_the_future", source="round:2:scouts"
    ).state
    assert scouts_choice_lines(offered, 1, ()) is None


# --- Invariants over played games -----------------------------------------------


def _check_rules_helpers(state: GameState, seat: int) -> None:
    """The reason helpers agree with the checks the engine offers by."""

    options: list[tuple[ScoutsOption, str]] = [
        (subcommittee.option, excluded)
        for subcommittee in SUBCOMMITTEES_BY_ID.values()
        for excluded in ("", "high_council")
    ]
    options += [
        (option, "") for sale in SALES_BY_ID.values() for option in sale.options
    ]
    options += [
        (option, "") for event in EVENTS_BY_ID.values() for option in event.options
    ]
    for option, excluded in options:
        step = line_unavailable_reason(state, seat, option, exclude_space=excluded)
        offered = line_is_offered(state, seat, option, exclude_space=excluded)
        assert (step is None) == offered
        if step is None:
            continue
        if step in option.costs:
            # The named cost is one the seat cannot pay on its own (a
            # resource cost counts with the others of its line).
            assert not option_is_affordable(state, seat, option)
            if not isinstance(step, PayResources):
                single = ScoutsOption(costs=(cast(ScoutsCost, step),))
                assert not option_is_affordable(state, seat, single)
        else:
            reward = cast(ScoutsReward, step)
            assert option_is_affordable(state, seat, option)
            assert not reward_has_effect(state, seat, reward, exclude_space=excluded)
    owner = state.players[seat]
    for mission in MISSIONS_BY_ID.values():
        if join_unavailable_reason(state, seat, mission) == ("none", 0, 0):
            continue  # nobody takes part in this one
        targets = join_targets(state, seat, mission)
        for target in ("", "recruit", "-", *owner.active_contract_ids):
            reason = join_unavailable_reason(state, seat, mission, target)
            assert (reason is None) == (target in targets), (mission, target)


@pytest.mark.parametrize(
    "config",
    [
        RulesetConfig(arrakeen_scouts=True, choam_module=True),
        RulesetConfig(arrakeen_scouts=True, choam_module=True, immortality=True),
    ],
    ids=["choam", "immortality-choam"],
)
def test_enabled_lines_are_exactly_the_legal_line_actions(
    config: RulesetConfig,
) -> None:
    seen: set[str] = set()
    disabled = 0
    for seed in range(4):
        state = ENGINE.reset(config, seed)
        resolver = ChanceResolver(seed=seed)
        rng = random.Random(seed)
        while state.phase is not GamePhase.FINISHED:
            decision = ENGINE.current_decision(state)
            if isinstance(decision, ChanceDecision):
                state = ENGINE.apply(state, resolver.resolve(decision)).state
                continue
            assert isinstance(decision, PlayerDecision)
            seat = decision.owner
            legal = ENGINE.legal_actions(state, seat)
            found = scouts_choice_lines(state, seat, legal)
            if found is not None:
                info = cast(dict[str, Any], found)
                seen.add(str(info["frame"]))
                assert _enabled(info, legal) == _line_actions(legal)
                for line in info["lines"]:
                    if line["enabled"]:
                        assert line["reason"] is None and line["text"]
                        continue
                    disabled += 1
                    assert line["code"] != "unavailable", line  # no fallback
                    assert line["reason"] and line["reason_ko"], line
                _check_rules_helpers(state, seat)
            state = ENGINE.apply(state, rng.choice(legal)).state
    assert seen == {"scouts_choice", "scouts_subcommittee", "scouts_mission"}
    assert disabled > 0


def test_the_helpers_agree_with_line_is_offered_on_a_poor_seat() -> None:
    """Nothing to pay with: every line with a cost names its first cost."""

    owner = replace(
        _owner(hand=(), resources=Resources()),
        troops_supply=0,
        troops_garrison=12,
    )
    state = _state(owner)
    _check_rules_helpers(state, 0)
    unravel = SALES_BY_ID["unravel_the_future"].options[1]
    assert line_unavailable_reason(state, 0, unravel) == unravel.costs[0]
