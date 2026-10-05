"""The ``agent_effects`` window in Arrakeen Scouts games (scouts.md §3.3,
§3.5, §4.7; docs/app-ai-plan.md §11.8).

Each test reaches a real Agent turn of a Scouts game (the first turn, the
seat's hand and the Scouts goods adjusted, then a real ``agent_turn``),
builds the ``DecisionRun`` the agent would build and asserts the source the
window builds or the exact action it answers. Ability answers a branch
depends on are pinned (``monkeypatch``); ``intrigue_play_sources`` (another
window's) is stubbed.
"""

import random
from collections.abc import Mapping

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import scouts as sc
from dune_imperium.agents.app_ai.abilities.base import Answer
from dune_imperium.agents.app_ai.agent import AppAIAgent
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import agent_effects as ae
from dune_imperium.agents.app_ai.windows.common import Source, Stage
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GameState
from dune_imperium.simulation.runner import run_policy_game

SCOUTS = RulesetConfig(choam_module=False, arrakeen_scouts=True)
PLAIN = RulesetConfig(choam_module=False)
RICH = Resources(solari=9, spice=6, water=2)

_RESERVE = "imperial_reserve"


@pytest.fixture(autouse=True)
def no_plots(monkeypatch: pytest.MonkeyPatch) -> None:
    """``intrigue_play_sources`` belongs to the intrigue window: stub it."""

    monkeypatch.setattr(ae, "intrigue_play_sources", lambda run, plays, combat: [])


# ---------------------------------------------------------------------------
# Real states
# ---------------------------------------------------------------------------


def _settle(state: GameState) -> GameState:
    chance = ChanceResolver(seed=1)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _apply(state: GameState, seat: int, action: DomainAction) -> GameState:
    legal = ENGINE.legal_actions(state, seat)
    return _settle(ENGINE.apply(state, action, legal_actions=legal).state)


def _place(
    config: RulesetConfig,
    space: str,
    *,
    adjust: Mapping[str, object] | None = None,
    **before: object,
) -> tuple[GameState, int]:
    """The first turn's seat sends an Agent to ``space`` with any hand card
    (Influence and resources adjusted by ``before``, the state by
    ``adjust``)."""

    state = first_decision("turn", config=config, seed=1)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    if adjust:
        state = with_state(state, **adjust)
    if before:
        state = with_player(state, seat, **before)
    placements = [
        action
        for action in ENGINE.legal_actions(state, seat)
        if action.action_id == "agent_turn"
        and arg(action, "space_id") == space
        and arg(action, "infiltrate_post_id") is None
    ]
    assert placements, f"no card goes to {space}"
    plain = [a for a in placements if "signet_ring" not in str(arg(a, "card_id"))]
    state = _apply(state, seat, (plain or placements)[0])
    assert state.decision_stack[-1].kind == "agent_effects"
    return state, seat


def _run(state: GameState, seat: int, memory: Memory | None = None) -> DecisionRun:
    profile = make_profile(state, seat)
    legal = ENGINE.legal_actions(state, seat)
    return DecisionRun(
        profile.ctx, profile, legal, random.Random(0), memory or Memory()
    )


def _turn(state: GameState, seat: int, memory: Memory | None = None) -> ae._Turn:
    t = ae._turn(_run(state, seat, memory))
    ae._collect(t)
    return t


def _source(t: ae._Turn, label: str) -> Source:
    found = [s for s in t.sources if s.label == label]
    assert found, (label, [s.label for s in t.sources], t.unmapped)
    return found[0]


def _evaluate(source: Source) -> tuple[float, DomainAction | None]:
    assert source.evaluate is not None
    return source.evaluate()


def _a(seat: int, action_id: str, **arguments: str | int) -> DomainAction:
    return DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )


def _ids(state: GameState, seat: int) -> set[str]:
    return {a.action_id for a in ENGINE.legal_actions(state, seat)}


# ---------------------------------------------------------------------------
# scouts_collect_mission (scouts.md §3.5, D26)
# ---------------------------------------------------------------------------


def _reserve_goods(spice: int, solari: int) -> dict[str, object]:
    rows = (
        (_RESERVE, "imperial_privilege", "spice", spice, -1),
        (_RESERVE, "imperial_privilege", "solari", solari, -1),
    )
    return {"scouts_goods": tuple(row for row in rows if row[3] > 0)}


def _imperial_privilege(spice: int, solari: int) -> tuple[GameState, int]:
    return _place(
        SCOUTS,
        "imperial_privilege",
        adjust=_reserve_goods(spice, solari),
        resources=RICH,
        influence=Influence(emperor=2),
    )


def test_mission_collect_is_automatic_with_the_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _imperial_privilege(spice=1, solari=0)
    actions = [
        a
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "scouts_collect_mission"
    ]
    assert actions == [_a(seat, "scouts_collect_mission", choice="")]
    t = _turn(state, seat)
    source = _source(t, "Scouts mission pieces")
    icons = str(t.context["board_icons"]).split(",")
    assert source.stage is Stage.SPACE
    assert source.order == icons.index("scouts_mission")
    assert source.actions == (actions[0],)


@pytest.mark.parametrize("pick", ["spice", "solari"])
def test_imperial_reserve_pick_is_the_ability_answer(
    monkeypatch: pytest.MonkeyPatch, pick: str
) -> None:
    state, seat = _imperial_privilege(spice=1, solari=2)
    choices = {
        str(arg(a, "choice"))
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "scouts_collect_mission"
    }
    assert choices == {"spice", "solari"}
    monkeypatch.setattr(
        sc.MissionPiecesSpaceAbility,
        "evaluate",
        lambda self, p, r: Answer(1.0, ((pick,),)),
    )
    source = _source(_turn(state, seat), "Scouts mission pieces")
    assert source.actions == (_a(seat, "scouts_collect_mission", choice=pick),)


# ---------------------------------------------------------------------------
# Subcommittees (scouts.md §3.3, D23)
# ---------------------------------------------------------------------------


def _high_council() -> tuple[GameState, int]:
    state, seat = _place(SCOUTS, "high_council", resources=RICH)
    seat_effect = _a(seat, "resolve_board_effect", effect="high_council")
    state = _apply(state, seat, seat_effect)  # the seat taken arms the offer
    assert "decline_subcommittee" in _ids(state, seat)
    return state, seat


def test_subcommittee_choice_keeps_the_pick_for_its_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _high_council()
    if "choose_subcommittee" not in _ids(state, seat):
        pytest.skip("nothing joinable in this state")
    joinable = make_profile(state, seat).ctx.joinable_subcommittees("high_council")
    pick = joinable[0]
    monkeypatch.setattr(
        sc.SubcommitteeOfferAbility,
        "evaluate",
        lambda self, p, r: Answer(3.0, ((pick,),)),
    )
    memory = Memory()
    t = _turn(state, seat, memory)
    source = _source(t, "Subcommittee")
    assert source.extra["explicit"] is False
    assert _evaluate(source) == (3.0, _a(seat, "choose_subcommittee"))
    key = (ae.SUBCOMMITTEE_INTENT, state.round_number, seat)
    assert t.on_choose[_a(seat, "choose_subcommittee")] == [(key, pick)]
    assert _a(seat, "decline_subcommittee") in t.declines
    assert key not in memory.intents  # evaluating alone writes nothing


def test_subcommittee_unused_key_is_the_decline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _high_council()
    monkeypatch.setattr(
        sc.SubcommitteeOfferAbility, "evaluate", lambda self, p, r: Answer(0.0, None)
    )
    t = _turn(state, seat)
    if "choose_subcommittee" in _ids(state, seat):
        assert _evaluate(_source(t, "Subcommittee")) == (0.0, None)
    assert _a(seat, "decline_subcommittee") in t.declines


def test_subcommittee_choice_is_written_when_chosen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state, seat = _high_council()
    if "choose_subcommittee" not in _ids(state, seat):
        pytest.skip("nothing joinable in this state")
    pick = make_profile(state, seat).ctx.joinable_subcommittees("high_council")[0]
    monkeypatch.setattr(
        sc.SubcommitteeOfferAbility,
        "evaluate",
        lambda self, p, r: Answer(500.0, ((pick,),)),
    )
    memory = Memory()
    key = (ae.SUBCOMMITTEE_INTENT, state.round_number, seat)
    for _ in range(20):
        action = ae.agent_effects_window(_run(state, seat, memory))
        assert action is not None
        if action.action_id == "choose_subcommittee":
            break
        state = _apply(state, seat, action)
    else:
        raise AssertionError("never chose the subcommittee")
    assert memory.intents[key] == pick


# ---------------------------------------------------------------------------
# Desert Riding at Hagga Basin (scouts.md §3.5, §4.2, D27)
# ---------------------------------------------------------------------------


def _hagga_basin(**before: object) -> tuple[GameState, int]:
    token = ("desert_riding", "hagga_basin", "maker_hooks", 1, -1)
    return _place(
        SCOUTS,
        "hagga_basin",
        adjust={"scouts_goods": (token,)},
        resources=RICH,
        **before,
    )


@pytest.mark.parametrize(
    ("option", "expected"),
    [(2, "take_desert_riding_hooks"), (0, "harvest_maker_spice")],
)
def test_desert_riding_maps_option_two_to_the_hooks(
    monkeypatch: pytest.MonkeyPatch, option: int, expected: str
) -> None:
    state, seat = _hagga_basin()
    assert "take_desert_riding_hooks" in _ids(state, seat)
    monkeypatch.setattr(
        sc.DesertRidingAbility,
        "evaluate",
        lambda self, p, r: Answer(4.0, ((option,),)),
    )
    t = _turn(state, seat)
    source = _source(t, "Maker space")
    assert source.extra["explicit"] is True
    _value, action = _evaluate(source)
    assert action is not None and action.action_id == expected


def test_desert_riding_ability_answers_hagga_basin_without_the_token() -> None:
    # Scouts swaps the ability whether or not the token is out: the base
    # harvest/summon choice is still answered (no fallback).
    state, seat = _place(SCOUTS, "hagga_basin", resources=RICH)
    assert "take_desert_riding_hooks" not in _ids(state, seat)
    _value, action = _evaluate(_source(_turn(state, seat), "Maker space"))
    assert action is not None and action.action_id == "harvest_maker_spice"


# ---------------------------------------------------------------------------
# Market Opening's Reserve card (scouts.md §4.7, D31; plan §11.8)
# ---------------------------------------------------------------------------


def test_market_opening_discounts_the_reserve_card_offered_here() -> None:
    state, seat = _place(SCOUTS, "high_council", resources=RICH)
    t = ae._turn(_run(state, seat))
    reserve = (_a(seat, "acquire_reserve_with_solari", card_id="the_spice_must_flow"),)
    (plain,) = ae._acquire_entities(t, (), reserve)
    state = with_state(
        state,
        scouts_round_modifier="spice_must_flow_discount",
        scouts_discount_used=False,
    )
    t = ae._turn(_run(state, seat))
    (discounted,) = ae._acquire_entities(t, (), reserve)
    assert discounted.int_attr("PersuasionCost") == plain.int_attr("PersuasionCost") - 2


# ---------------------------------------------------------------------------
# Gating and a whole game
# ---------------------------------------------------------------------------


def test_scouts_ids_are_unknown_outside_scouts() -> None:
    state, seat = _place(PLAIN, "high_council", resources=RICH)
    run = _run(state, seat)
    widened = DecisionRun(
        run.ctx,
        run.profile,
        (*run.legal, _a(seat, "decline_subcommittee")),
        run.rng,
        Memory(),
    )
    t = ae._turn(widened)
    ae._collect(t)
    assert t.unmapped == ["unknown action decline_subcommittee"]
    assert ae.agent_effects_window(widened) is None


def test_scouts_game_has_no_agent_effects_fallback() -> None:
    agents = [AppAIAgent(seed=11 + s) for s in range(4)]
    run_policy_game(ENGINE, SCOUTS, 5, agents)
    assert sum(a.fallbacks.get("agent_effects", 0) for a in agents) == 0
    assert sum(a.mirrored.get("agent_effects", 0) for a in agents) > 0
