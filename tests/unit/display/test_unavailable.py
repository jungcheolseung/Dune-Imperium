"""The choices a seat cannot take right now, greyed out with the reason.

User request 2026-09-29: an option that cannot be taken right now is shown,
not selectable, with the reason, and becomes selectable as soon as it can be
taken (and the reverse), for the whole game. ``display.unavailable`` does it
for the Reveal shop, the seat's own Intrigue cards and effects waiting on
their condition; these tests pin each reason, and that a row goes away the
moment its action becomes legal. The legal actions themselves are the
engine's, untouched (``test_unavailable_consistency.py`` guards that).
"""

import random
from dataclasses import replace
from typing import Any, cast

from tests.support.reward_windows import answer_reward_windows
from tests.unit.rules.test_immortality_intrigue import (
    _combat_state,
    _fighter,
    _pass_through_combat,
)
from tests.unit.rules.test_tech import _combat_acquire_frame

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_placement, apply_whole
from dune_imperium.agents.determinize import determinize
from dune_imperium.content.bloodlines.sardaukar import (
    COMMANDER_SETUP_SPACE_IDS,
    skill_tile_instance_ids,
)
from dune_imperium.content.immortality.board import (
    RESEARCH_START_ID,
    TLEILAXU_TRACK_END,
    ResearchBonus,
)
from dune_imperium.content.immortality.tleilaxu import (
    RECLAIMED_FORCES,
    tleilaxu_card_for_instance,
    tleilaxu_deck_instance_ids,
)
from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.content.uprising.effect_dsl import (
    EffectSection,
    GainResources,
    IntrigueOption,
    IntrigueTiming,
    PayResources,
)
from dune_imperium.content.uprising.imperium import (
    imperium_card_for_instance,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.display import scouts
from dune_imperium.display.unavailable import (
    NOT_NOW_CODE,
    held_text,
    intrigue_option_reason,
    resource_reason,
    troops_reason,
    unavailable_choices,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_effect_frame import agent_box_is_waiting
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.combat import begin_combat_intrigue, resolve_combat_rewards
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effect_interpreter import OptionBlock
from dune_imperium.rules.frames import TECH_ACQUIRE_PENDING_KEY, FrameKind, with_context
from dune_imperium.rules.immortality import (
    _bonus_frame,
    advance_research,
    pending_research_bonuses,
)
from dune_imperium.rules.reveal_turn import pending_reveal_choices

ENGINE = UprisingRulesEngine()
BASE = RulesetConfig()
ROW = imperium_deck_instance_ids(False)[:5]  # five cards costing 3 Persuasion
TURN = DecisionFrame(
    kind="turn",
    frame_id="round:1:turn:0",
    decision=PlayerDecision(owner=0, prompt="Choose a turn"),
)


def _state(
    owner: PlayerState, *, config: RulesetConfig = BASE, **fields: Any
) -> GameState:
    values: dict[str, Any] = {
        "config": config,
        "seed": 1,
        "phase": GamePhase.PLAYER_TURNS,
        "round_number": 1,
        "players": (owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        "decision_stack": (TURN,),
    }
    values.update(fields)
    return GameState(**values)


def _reveal(state: GameState, persuasion: int) -> GameState:
    """Start seat 0's Reveal and give it ``persuasion`` to spend."""

    revealed = apply_whole(
        ENGINE, state, DomainAction(action_id="reveal_turn", actor=0)
    )
    frame = revealed.state.decision_stack[-1]
    assert frame.kind == FrameKind.REVEAL
    context = {**dict(frame.context), "persuasion": persuasion}
    frame = replace(frame, context=tuple(sorted(context.items())))
    return replace(
        revealed.state,
        decision_stack=(*revealed.state.decision_stack[:-1], frame),
    )


def _found(state: GameState, seat: int = 0) -> dict[str, Any]:
    found = unavailable_choices(state, seat, ENGINE.whole_actions(state, seat))
    assert isinstance(found, dict)
    return found


def _rows(found: dict[str, Any], surface: str) -> dict[str, dict[str, Any]]:
    return {row["key"]: row for row in found["rows"] if row["surface"] == surface}


def _legal(state: GameState, action_id: str) -> list[dict[str, Any]]:
    return [
        dict(action.arguments)
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == action_id
    ]


def test_the_reason_helpers_moved_and_display_scouts_re_exports_them() -> None:
    moved = vars(scouts)
    assert moved["_resource_reason"] is resource_reason
    assert moved["_troops_reason"] is troops_reason
    assert moved["_held"] is held_text
    assert resource_reason("spice", 3, 2) == (
        "Needs 3 spice (you have 2)",
        "{spice:3} 필요 (보유 2)",
        "cost",
    )


# --- The Reveal shop ---


def _shop(persuasion: int) -> GameState:
    return _reveal(
        _state(
            PlayerState(player_id=0),
            imperium_row=ROW,
            reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 0)),
        ),
        persuasion,
    )


def test_the_reveal_shop_greys_out_the_cards_the_seat_cannot_afford() -> None:
    state = _shop(2)
    found = _found(state)

    assert found["frame"] == "reveal"
    rows = _rows(found, "acquire")
    assert {row["action"]["action_id"] for row in rows.values()} == {
        "acquire_imperium",
        "acquire_reserve",
    }
    for instance_id in ROW:
        assert imperium_card_for_instance(instance_id).acquisition_cost == 3
        row = rows[f"acquire:{instance_id}"]
        assert row["action"] == {
            "action_id": "acquire_imperium",
            "arguments": {"instance_id": instance_id},
            "detail": None,
            "detail_ko": None,
        }
        assert (row["reason"], row["reason_ko"], row["code"]) == (
            "Needs 3 Persuasion (you have 2)",
            "{persuasion:3} 필요 (보유 2)",
            "cost",
        )
        assert found["refs"][instance_id]["code"] == "cost"
    empty = rows["acquire:the_spice_must_flow"]
    assert (empty["reason"], empty["code"]) == ("The Reserve stack is empty", "empty")
    # Prepare the Way costs 2: an ordinary buy, never greyed or dimmed.
    assert _legal(state, "acquire_reserve") == [{"card_id": "prepare_the_way"}]
    assert "acquire:prepare_the_way" not in rows
    assert "prepare_the_way" not in found["refs"]
    assert set(found["refs"]) == {*ROW, "the_spice_must_flow"}


def test_a_greyed_out_card_lights_up_as_soon_as_the_seat_can_afford_it() -> None:
    state = _shop(3)
    found = _found(state)

    assert {row["key"] for row in found["rows"]} == {"acquire:the_spice_must_flow"}
    assert set(found["refs"]) == {"the_spice_must_flow"}
    assert [item["instance_id"] for item in _legal(state, "acquire_imperium")] == [*ROW]


def test_set_aside_and_tleilaxu_cards_name_their_own_cost() -> None:
    config = RulesetConfig(immortality=True)
    tleilaxu = tleilaxu_deck_instance_ids()[:2]
    set_aside = ROW[0]
    supply = PlayerState(player_id=0).troops_supply
    owner = PlayerState(
        player_id=0,
        troops_supply=supply - 1,
        specimens=1,
        research_space=RESEARCH_START_ID,
        imperium_set_aside=(set_aside,),
    )
    state = _reveal(
        _state(owner, config=config, tleilaxu_row=tleilaxu),
        1,
    )
    rows = _rows(_found(state), "acquire")

    manipulated = rows[f"acquire:{set_aside}"]
    assert manipulated["action"]["action_id"] == "acquire_manipulated_imperium"
    # One Persuasion less than printed [Manipulate card].
    assert manipulated["reason"] == "Needs 2 Persuasion (you have 1)"
    for instance_id in tleilaxu:
        cost = tleilaxu_card_for_instance(instance_id).specimen_cost
        assert cost > 1  # Beguiling Pheromones 3, Chairdog 2
        key = f"acquire:{instance_id}"
        assert rows[key]["action"]["action_id"] == "acquire_tleilaxu"
        assert rows[key]["reason"] == f"Needs {cost} specimens (you have 1)"
        assert rows[key]["reason_ko"] == f"{{specimen:{cost}}} 필요 (보유 1)"
    reclaimed = [
        row
        for row in rows.values()
        if row["action"]["action_id"] == "acquire_reclaimed_forces"
    ]
    assert [row["action"]["arguments"] for row in reclaimed] == [
        {"choice": "troops"},
        {"choice": "tleilaxu"},
    ]
    assert {row["reason"] for row in reclaimed} == {
        f"Needs {RECLAIMED_FORCES.specimen_cost} specimens (you have 1)"
    }


_TLEILAXU_TRACK_END = (
    "Your Tleilaxu token is already at the end of its track",
    "{tleilaxu} 트랙 끝에 이미 도달함",
    "reward",
)


def test_reclaimed_forces_greys_out_only_the_tleilaxu_step_at_the_track_end() -> None:
    """The Tleilaxu choice would do nothing on the track's last space
    (OQ-048, OQ-071); the troops stay on offer, so the card is not dimmed."""

    supply = PlayerState(player_id=0).troops_supply
    owner = PlayerState(
        player_id=0,
        troops_supply=supply - RECLAIMED_FORCES.specimen_cost,
        specimens=RECLAIMED_FORCES.specimen_cost,
        research_space=RESEARCH_START_ID,
        tleilaxu_space=7,
    )
    state = _reveal(
        _state(
            owner,
            config=RulesetConfig(immortality=True),
            tleilaxu_row=tleilaxu_deck_instance_ids()[:2],
        ),
        0,
    )
    assert _legal(state, "acquire_reclaimed_forces") == [{"choice": "troops"}]
    found = _found(state)
    rows = _rows(found, "acquire")
    reclaimed = [
        row
        for row in rows.values()
        if row["action"]["action_id"] == "acquire_reclaimed_forces"
    ]
    assert [row["action"]["arguments"] for row in reclaimed] == [
        {"choice": "tleilaxu"}
    ]
    assert (
        reclaimed[0]["reason"],
        reclaimed[0]["reason_ko"],
        reclaimed[0]["code"],
    ) == _TLEILAXU_TRACK_END
    assert "reclaimed_forces" not in found["refs"]


# --- Intrigue cards ---


def _intrigue_state(*cards: str, **owner_fields: Any) -> GameState:
    owner = PlayerState(
        player_id=0,
        intrigue_cards=tuple(f"intrigue:{card}:0" for card in cards),
        **owner_fields,
    )
    return _state(owner, config=RulesetConfig(choam_module=True))


def test_an_intrigue_card_greys_out_with_its_failing_cost_or_condition() -> None:
    cards = (
        "imperium_politics",
        "councilor_s_ambition",
        "sietch_ritual",
        "backed_by_choam",
        "change_allegiances",
        "false_orders",
        "coercive_negotiation",
    )
    found = _found(_intrigue_state(*cards))
    rows = {
        row["action"]["arguments"]["card_id"]: row
        for row in _rows(found, "intrigue").values()
    }

    expected = {
        "imperium_politics": ("Needs 1 solari (you have 0)", "cost"),
        "councilor_s_ambition": ("Only if you hold a High Council seat", "condition"),
        "sietch_ritual": ("Needs 1 card in hand (you have 0)", "cost"),
        "backed_by_choam": ("Needs 1 Influence to lose (you have 0)", "cost"),
        "change_allegiances": ("None of its lines can be used now", "no_line"),
        "false_orders": ("Only after you send an Agent this turn", "reward"),
        # "When you deploy three or more units to the Conflict in a single
        # turn:" is checked first: a play condition (OQ-016, codec v129).
        "coercive_negotiation": (
            "Only if you have deployed 3 or more units to the Conflict this turn",
            "condition",
        ),
    }
    assert {
        card.split(":")[1]: (row["reason"], row["code"]) for card, row in rows.items()
    } == expected
    for card_id, row in rows.items():
        assert row["action"]["action_id"] == "play_intrigue"
        assert row["action"]["arguments"] == {"card_id": card_id, "option": 0}
        assert row["reason_ko"]
        # The card in the Intrigue hand is dimmed with the same reason.
        assert found["refs"][card_id]["reason"] == row["reason"]

    # With the units deployed, the empty bank is what blocks it (OQ-064).
    deployed = _found(
        _intrigue_state("coercive_negotiation", units_deployed_turn=3)
    )
    (bank_row,) = _rows(deployed, "intrigue").values()
    assert (bank_row["reason"], bank_row["code"]) == (
        "Needs 3 Contracts in the bank (there are 0)",
        "contract_bank",
    )
    assert bank_row["reason_ko"]


def test_an_intrigue_card_for_another_window_is_only_dimmed() -> None:
    """No row for a Combat card during a Plot turn (it would show every
    turn), only its card dimmed with when it is played."""

    found = _found(_intrigue_state("spice_is_power", "imperium_politics"))

    assert [row["action"]["arguments"]["card_id"] for row in found["rows"]] == [
        "intrigue:imperium_politics:0"
    ]
    assert found["refs"]["intrigue:spice_is_power:0"] == {
        "reason": "Combat Intrigue: played during combat",
        "reason_ko": "전투 책략 카드: 전투 중에 사용",
        "code": "timing",
    }


def test_harvest_cells_in_combat_intrigue_is_dimmed_until_the_conflict_ends() -> None:
    """User ruling 2026-10-06 (OQ-057 (11)): Harvest Cells is played only
    in the window after the Conflict's rewards, never in Combat Intrigue,
    so there it is only dimmed with when it is played, like a card printed
    for another window."""

    card = "intrigue:harvest_cells:0"
    owner = PlayerState(
        player_id=0,
        research_space=RESEARCH_START_ID,
        troops_supply=6,
        troops_conflict=3,
        combat_strength=6,
        has_revealed=True,
        intrigue_cards=(card, "intrigue:vicious_talents:0"),
    )
    state = begin_combat_intrigue(
        _state(
            owner,
            config=RulesetConfig(immortality=True),
            phase=GamePhase.COMBAT,
            first_player=0,
            reveal_order=(0, 1, 2, 3),
            decision_stack=(),
            current_conflict_ids=("skirmish_crysknife",),
        )
    ).state
    assert state.decision_stack[-1].kind == FrameKind.COMBAT_INTRIGUE
    assert [args["card_id"] for args in _legal(state, "play_intrigue")] == [
        "intrigue:vicious_talents:0"
    ]
    found = _found(state)
    assert _rows(found, "intrigue") == {}
    assert found["refs"][card] == {
        "reason": "Played after the Conflict resolves, if you lose 3 or more troops",
        "reason_ko": "{conflict}이 끝난 뒤 {troop}을 3 이상 잃었을 때 사용",
        "code": "timing",
    }


# --- Harvest Cells in its own window (Conflict end) ---------------------------

HARVEST_CELLS = ("intrigue:harvest_cells:0", "intrigue:harvest_cells:1")
# No Tleilaxu Row card its specimens could pay for: four specimens each.
PRICEY_ROW = ("tleilaxu:twisted_mentat:0", "tleilaxu:usurp:0")
# The Conflict's troops are back in the supply when the window opens; lost
# Sardaukar Commanders go back to their own supply and make no specimen
# [Bloodlines p. 4] (``combat._harvest_cells_has_effect``).
NO_TROOP_FOR_A_SPECIMEN = (
    "No troop in your supply to make a specimen",
    "{specimen}으로 만들 {troop}이 {supply}에 없음",
)
NO_TLEILAXU_CARD = (
    "; No Tleilaxu card your specimens could acquire",
    " · {specimen}으로 획득할 수 있는 {tleilaxu} 카드 없음",
)


def _conflict_end_window(*cards: str, **owner_fields: Any) -> GameState:
    """Seat 0's Conflict-end window after a Conflict it fought with three
    Commanders and no troop (Immortality and Bloodlines), holding ``cards``
    (the fixture of ``test_immortality_intrigue.py``'s
    ``test_harvest_cells_window_skips_a_copy_that_would_change_nothing``)."""

    values: dict[str, Any] = {
        "intrigue_cards": cards,
        "troops_supply": 0,
        "troops_garrison": 12,
        "troops_conflict": 0,
        "commanders_conflict": 3,
        "combat_strength": 6,
        "specimens": 0,
    }
    values.update(owner_fields)
    config = RulesetConfig(immortality=True, bloodlines=True)
    state = replace(
        _combat_state(_fighter(0, **values), config=config), tleilaxu_row=PRICEY_ROW
    )
    window = _pass_through_combat(ENGINE, state)
    assert window.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    return window


def _play_conflict_end(card_id: str) -> DomainAction:
    return DomainAction(
        action_id="play_conflict_end_intrigue",
        actor=0,
        arguments=(("card_id", card_id),),
    )


def test_harvest_cells_that_could_change_nothing_greys_out_in_its_window() -> None:
    """The window opens on public facts (OQ-103), so a seat that lost only
    Commanders sits in it holding a Harvest Cells it may not play: no troop
    to make a specimen of, and no Tleilaxu card the specimens could pay for
    (user ruling 2026-10-06, an Intrigue play needs an effect). The card
    shows greyed out among the Intrigue cards, and dims in the hand, with
    both dead effects explained."""

    first = HARVEST_CELLS[0]
    window = _conflict_end_window(first)
    assert ENGINE.whole_actions(window, 0) == (
        DomainAction(action_id="decline_conflict_end_intrigue", actor=0),
    )

    found = _found(window)
    assert found["frame"] == "conflict_end_trigger"
    reason = {
        "reason": NO_TROOP_FOR_A_SPECIMEN[0] + NO_TLEILAXU_CARD[0],
        "reason_ko": NO_TROOP_FOR_A_SPECIMEN[1] + NO_TLEILAXU_CARD[1],
        "code": "reward",
    }
    assert found["rows"] == [
        {
            "key": f"intrigue:{first}",
            "surface": "intrigue",
            "action": {
                "action_id": "play_conflict_end_intrigue",
                "arguments": {"card_id": first},
                "detail": None,
                "detail_ko": None,
            },
            "refs": [first],
            **reason,
        }
    ]
    assert found["refs"] == {first: reason}

    # A troop in the supply, or three specimens for Reclaimed Forces, makes
    # it playable: the row becomes the play at once.
    for fields in (
        {"troops_supply": 1, "troops_garrison": 11},
        {"specimens": 3, "troops_garrison": 9},
    ):
        lit = _conflict_end_window(first, **fields)
        assert _legal(lit, "play_conflict_end_intrigue") == [{"card_id": first}]
        assert unavailable_choices(lit, 0, ENGINE.whole_actions(lit, 0)) is None
    # Nobody else is shown anything of it.
    for seat in range(1, 4):
        legal = ENGINE.whole_actions(window, seat)
        assert legal == () and unavailable_choices(window, seat, legal) is None


def test_a_second_harvest_cells_greys_out_once_the_first_takes_the_troops() -> None:
    """Two troops and a Commander lost: both copies are offered, the first
    played takes both troops as its specimens, and the second, which could
    make no specimen and buy nothing with two, greys out in the window that
    stays open while the seat holds an Intrigue card (OQ-103). It reads as
    any copy with no troop to make a specimen of; the first copy is already
    in the discard pile and is not dimmed."""

    first, second = HARVEST_CELLS
    mixed = {"troops_garrison": 10, "troops_conflict": 2, "commanders_conflict": 1}
    both = _conflict_end_window(first, second, **mixed)
    assert unavailable_choices(both, 0, ENGINE.whole_actions(both, 0)) is None

    played = apply_whole(ENGINE, both, _play_conflict_end(first)).state
    # The first copy resolved at its play: its acquisition choice (nothing
    # in the pricey Row pays) is answered, and the window is back on top.
    assert played.decision_stack[-1].kind == FrameKind.INTRIGUE_CHOICE
    played = apply_whole(ENGINE, 
        played, DomainAction(action_id="decline_intrigue_tleilaxu", actor=0)
    ).state
    assert played.decision_stack[-1].kind == FrameKind.CONFLICT_END_TRIGGER
    assert played.players[0].troops_supply == 0
    assert _legal(played, "play_conflict_end_intrigue") == []
    found = _found(played)
    reason = (
        NO_TROOP_FOR_A_SPECIMEN[0] + NO_TLEILAXU_CARD[0],
        NO_TROOP_FOR_A_SPECIMEN[1] + NO_TLEILAXU_CARD[1],
        "reward",
    )
    (row,) = found["rows"]
    assert (row["key"], row["reason"], row["reason_ko"], row["code"]) == (
        f"intrigue:{second}",
        *reason,
    )
    assert row["action"]["arguments"] == {"card_id": second}
    assert set(found["refs"]) == {second}

    # A third troop lost leaves the second copy a specimen to make.
    three = _conflict_end_window(
        first, second, troops_garrison=9, troops_conflict=3, commanders_conflict=0
    )
    staged = apply_whole(ENGINE, three, _play_conflict_end(first)).state
    staged = apply_whole(ENGINE, 
        staged, DomainAction(action_id="decline_intrigue_tleilaxu", actor=0)
    ).state
    assert _legal(staged, "play_conflict_end_intrigue") == [{"card_id": second}]
    assert unavailable_choices(staged, 0, ENGINE.whole_actions(staged, 0)) is None


def test_harvest_cells_below_its_loss_says_how_many_units_are_lost() -> None:
    """Below its loss the provider withholds it first
    (``ConflictEndTriggerBlock.LOSS``). No window opens below the smallest
    loss any card names, so only a window built by hand meets it; the
    reason is the Combat Intrigue window's, with the units the seat loses."""

    card = HARVEST_CELLS[0]
    window = _conflict_end_window(card, troops_supply=1, troops_garrison=11)
    # The window records the units its seat lost as they went back to the
    # supply (``combat.conflict_end_loss``); make it two.
    frame = window.decision_stack[-1]
    short_frame = replace(frame, context=(("lost", 2), ("player", 0)))
    short = replace(window, decision_stack=(*window.decision_stack[:-1], short_frame))

    assert ENGINE.whole_actions(short, 0) == (
        DomainAction(action_id="decline_conflict_end_intrigue", actor=0),
    )
    (row,) = _found(short)["rows"]
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "Played after the Conflict resolves, if you lose 3 or more troops"
        " (you lose 2 units)",
        "{conflict}이 끝난 뒤 {troop}을 3 이상 잃었을 때 사용 (잃는 유닛 2)",
        "condition",
    )


def test_a_start_of_turn_card_is_played_then_only_dimmed_after_that_point() -> None:
    state = _intrigue_state("twisted_withdrawn")
    withdrawn = {"card_id": "intrigue:twisted_withdrawn:0", "option": 0}

    assert _legal(state, "play_intrigue") == [withdrawn]
    assert unavailable_choices(state, 0, ENGINE.whole_actions(state, 0)) is None
    revealed = _reveal(state, 0)
    found = _found(revealed)
    assert found["rows"] == []
    assert found["refs"]["intrigue:twisted_withdrawn:0"]["reason"] == (
        "Only at the start of your turn"
    )


def test_both_start_of_turn_cards_grey_out_once_the_seat_acted() -> None:
    """Withdrawn and Litany Against Fear are only the turn's first action
    (OQ-095 (6), user ruling 2026-10-04): after a Plot on the still-open
    turn frame each is a greyed-out row with the same reason, Withdrawn
    among the Intrigue cards, Litany beside the Agent and Reveal turns."""

    litany = "imperium:litany_against_fear:0"
    state = _intrigue_state(
        "twisted_withdrawn", "contingency_plan", hand=(litany,)
    )
    assert _legal(state, "play_turn_start_card") == [{"card_id": litany}]
    plot = DomainAction(
        "play_intrigue",
        0,
        (("card_id", "intrigue:contingency_plan:0"), ("option", 0)),
    )
    plotted = apply_whole(ENGINE, state, plot).state
    assert plotted.decision_stack[-1].kind == "turn"
    assert _legal(plotted, "play_turn_start_card") == []
    assert _legal(plotted, "play_intrigue") == []

    found = _found(plotted)
    reason = {
        "reason": "Only at the start of your turn: you already acted this turn",
        "reason_ko": "차례를 시작할 때만 사용 — 이번 차례에 이미 다른 행동을 했음",
        "code": "turn_started",
    }
    (withdrawn_row,) = _rows(found, "intrigue").values()
    assert withdrawn_row["action"]["arguments"] == {
        "card_id": "intrigue:twisted_withdrawn:0",
        "option": 0,
    }
    assert {key: withdrawn_row[key] for key in reason} == reason
    assert found["refs"]["intrigue:twisted_withdrawn:0"] == reason
    (litany_row,) = _rows(found, "choice").values()
    assert litany_row["action"]["action_id"] == "play_turn_start_card"
    assert litany_row["card_id"] == litany
    assert {key: litany_row[key] for key in reason} == reason
    # The hand card is named, not dimmed.
    assert litany not in found["refs"]


def _detonation(troops: int, undeployable: int) -> GameState:
    """Seat 0 at its turn start with Detonation, ``troops`` in its garrison
    and ``undeployable`` of them barred from deploying this turn."""

    owner = PlayerState(
        player_id=0,
        intrigue_cards=("intrigue:detonation:0",),
        troops_garrison=troops,
        troops_supply=12 - troops,
    )
    turn = replace(TURN, context=(("undeployable_troops", undeployable),))
    return _state(owner, decision_stack=(turn,))


def test_a_deploy_line_with_nothing_to_deploy_is_greyed_with_its_reason() -> None:
    """Detonation's "Deploy up to four troops from your garrison" (option 1)
    with nothing it may deploy changes nothing, so it is not offered (user
    ruling 2026-10-06): with only Harkonnen Advisor's barred troop ("can't
    deploy ... this turn" [Piter De Vries card], OQ-038), or with an empty
    garrison, the row is greyed with the reason."""

    def reason(state: GameState) -> tuple[str, str, str]:
        assert _legal(state, "play_intrigue") == [
            {"card_id": "intrigue:detonation:0", "option": 0}
        ]
        row = _rows(_found(state), "intrigue")["intrigue:intrigue:detonation:0:1"]
        return row["reason"], row["reason_ko"], row["code"]

    assert reason(_detonation(1, 1)) == (
        "Your only garrison troop cannot deploy this turn",
        "{garrison}의 {troop}은 이번 차례에 배치할 수 없음",
        "reward",
    )
    assert reason(_detonation(2, 2))[0] == (
        "Your garrison troops cannot deploy this turn"
    )
    assert reason(_detonation(0, 0)) == (
        "Needs 1 troop in your garrison (you have 0)",
        "{garrison}에 {troop:1} 필요 (보유 0)",
        "garrison",
    )
    blocked = replace(
        _detonation(2, 0),
        decision_stack=(replace(TURN, context=(("units_deploy_blocked", True),)),),
    )
    assert reason(blocked) == (
        "Emperor of the Known Universe bars deploying units this turn",
        "알려진 우주의 황제: 이번 차례에는 유닛을 배치할 수 없음",
        "reward",
    )
    # One deployable troop beside the barred one: an ordinary play.
    assert {"card_id": "intrigue:detonation:0", "option": 1} in _legal(
        _detonation(2, 1), "play_intrigue"
    )


# User ruling 2026-10-06 ("아무 효과 없이 책략을 쓸 수 없는거지"): an Intrigue
# option none of whose effects could change anything now is greyed out.

_NO_CARD_TO_DRAW = (
    "No card to draw: your deck and discard pile are both empty",
    "뽑을 카드 없음: 덱과 버린 카드 더미가 모두 비었음",
    "empty",
)
_NO_SUPPLY_TROOP = (
    "Needs 1 troop in your supply (you have 0)",
    "{supply}에 {troop:1} 필요 (보유 0)",
    "reward",
)
_EMPTY_SUPPLY: dict[str, Any] = {"troops_supply": 0, "troops_garrison": 12}
_SENT: dict[str, Any] = {
    "agents_available": 0,
    "agent_locations": ("arrakeen", "carthag"),
}
_DAGGER = "player:0:starter:dagger:0"


def _seat_with(
    *cards: str, config: RulesetConfig = BASE, **owner_fields: Any
) -> GameState:
    owner = PlayerState(
        player_id=0,
        intrigue_cards=tuple(f"intrigue:{card}:0" for card in cards),
        **owner_fields,
    )
    return _state(owner, config=config)


def _intrigue_reason(
    state: GameState, card: str, option: int = 0
) -> tuple[str, str, str]:
    """The greyed row of ``card``'s ``option``, which the engine withholds."""

    assert {"card_id": f"intrigue:{card}:0", "option": option} not in _legal(
        state, "play_intrigue"
    )
    row = _rows(_found(state), "intrigue")[f"intrigue:intrigue:{card}:0:{option}"]
    return row["reason"], row["reason_ko"], row["code"]


def test_an_intrigue_option_that_could_change_nothing_names_its_effect() -> None:
    immortality = RulesetConfig(immortality=True)
    bloodlines = RulesetConfig(bloodlines=True)
    alone = replace(
        _seat_with("twisted_withdrawn", config=bloodlines, hand=(_DAGGER,)),
        players=(
            PlayerState(
                player_id=0,
                intrigue_cards=("intrigue:twisted_withdrawn:0",),
                hand=(_DAGGER,),
            ),
            *(PlayerState(player_id=seat, has_revealed=True) for seat in range(1, 4)),
        ),
    )
    cases: list[tuple[GameState, str, int, tuple[str, str, str]]] = [
        (_seat_with("cunning"), "cunning", 0, _NO_CARD_TO_DRAW),
        (
            _seat_with("shaddam_s_favor", **_EMPTY_SUPPLY),
            "shaddam_s_favor",
            0,
            _NO_SUPPLY_TROOP,
        ),
        (
            _seat_with("inspire_awe"),
            "inspire_awe",
            0,
            (
                "No card costing 3 or less to acquire",
                "획득할 수 있는 비용 3 이하 카드 없음",
                "reward",
            ),
        ),
        (
            replace(
                _seat_with("unexpected_allies", resources=Resources(water=2)),
                shield_wall_present=False,
            ),
            "unexpected_allies",
            0,
            ("No Conflict this round", "이번 라운드에 교전 없음", "no_conflict"),
        ),
        (
            _seat_with(
                "breakthrough",
                config=immortality,
                research_space="c8r2",
            ),
            "breakthrough",
            0,
            (
                "Past the second genetic marker Research draws a card,"
                " and your deck and discard pile are both empty",
                "두 번째 유전자 표지 뒤의 {research}는 카드를 뽑는데"
                " {deck}과 {discard_pile}이 모두 비었음",
                "empty",
            ),
        ),
        (
            _seat_with(
                "illicit_dealings",
                config=immortality,
                research_space=RESEARCH_START_ID,
                tleilaxu_space=TLEILAXU_TRACK_END,
            ),
            "illicit_dealings",
            0,
            _TLEILAXU_TRACK_END,
        ),
        (
            _seat_with(
                "shadowy_bargain",
                config=immortality,
                research_space=RESEARCH_START_ID,
                **_EMPTY_SUPPLY,
            ),
            "shadowy_bargain",
            0,
            (
                "No troop in your supply to make a specimen",
                "{specimen}로 만들 {troop}이 {supply}에 없음",
                "reward",
            ),
        ),
        (
            _seat_with(
                "emperor_s_invitation", config=bloodlines, hand=(_DAGGER,), **_SENT
            ),
            "emperor_s_invitation",
            1,
            (
                "Only before you send an Agent this turn",
                "이번 차례에 {agent}를 보내기 전에만",
                "reward",
            ),
        ),
        (
            _seat_with(
                "insider_information",
                config=bloodlines,
                hand=(_DAGGER,),
                influence=Influence(emperor=2, spacing_guild=2, fremen=2),
            ),
            "insider_information",
            1,
            (
                "No board space's Influence requirement is unmet",
                "못 채운 {influence_any} 조건이 있는 공간 없음",
                "reward",
            ),
        ),
        (
            _seat_with("twisted_calculating", config=bloodlines),
            "twisted_calculating",
            0,
            ("No unit of yours in the Conflict", "{conflict}에 내 유닛 없음", "reward"),
        ),
        (
            alone,
            "twisted_withdrawn",
            0,
            (
                "Every other player has revealed: the turn would come straight"
                " back to you",
                "다른 플레이어가 모두 공개를 마쳐 차례가 바로 돌아옴",
                "reward",
            ),
        ),
    ]
    for state, card, option, expected in cases:
        assert _intrigue_reason(state, card, option) == expected, card


def test_a_city_spy_after_a_recall_this_turn_is_greyed_with_why() -> None:
    """Special Mission's [Spy] on [City] with the supply empty and every
    City post full, one held by the seat's Spy alone: once a Spy was
    recalled this turn, recalling and replacing it changes nothing (OQ-101
    (b))."""

    owner = PlayerState(
        player_id=0,
        intrigue_cards=("intrigue:special_mission:0",),
        spies_supply=0,
        spies_recalled_turn=1,
        spy_post_ids=(
            "arrakis-research-station-spice-refinery",
            "fremen-desert-tactics-fremkit",
            "landsraad-assembly-hall-gather-support",
        ),
    )
    rivals = (
        PlayerState(
            player_id=1,
            spies_supply=2,
            spy_post_ids=("arrakis-research-station-sietch-tabr",),
        ),
        PlayerState(
            player_id=2,
            spies_supply=2,
            spy_post_ids=("arrakis-spice-refinery-arrakeen",),
        ),
        PlayerState(player_id=3),
    )
    state = _state(owner, players=(owner, *rivals))
    assert _intrigue_reason(state, "special_mission") == (
        "You already recalled a Spy this turn;"
        " recalling and replacing it would change nothing",
        "이번 차례에 이미 {spy}를 회수함 — 회수해 다시 놓아도 바뀌는 것 없음",
        "reward",
    )
    # Before any recall this turn the play stays (OQ-101 (b)).
    fresh = replace(owner, spies_recalled_turn=0)
    assert {"card_id": "intrigue:special_mission:0", "option": 0} in _legal(
        _state(fresh, players=(fresh, *rivals)), "play_intrigue"
    )


def test_an_option_with_every_effect_dead_explains_each_of_them() -> None:
    """When no effect of a card could change anything, the row names every
    distinct one, joined, so neither half is left unexplained."""

    bloodlines = RulesetConfig(bloodlines=True)
    mercenaries = _seat_with(
        "mercenaries", resources=Resources(solari=3), **_EMPTY_SUPPLY
    )
    assert _intrigue_reason(mercenaries, "mercenaries") == (
        "No Intrigue card to draw: the Intrigue deck is empty and its discard"
        " pile holds nothing to shuffle; Needs 1 troop in your supply (you have 0)",
        "뽑을 {intrigue_card} 없음: 책략 카드덱이 비었고 버린 더미에 섞을 카드 없음"
        " · {supply}에 {troop:1} 필요 (보유 0)",
        "reward",
    )
    honor_guard = _seat_with(
        "honor_guard",
        config=bloodlines,
        hand=(_DAGGER,),
        **_EMPTY_SUPPLY,
        **_SENT,
    )
    assert _intrigue_reason(honor_guard, "honor_guard") == (
        "Needs 1 troop in your supply (you have 0);"
        " No Sardaukar Commander left to recruit this turn",
        "{supply}에 {troop:1} 필요 (보유 0) · 이번 차례에 고용할 {commander} 없음",
        "reward",
    )
    cunning = _seat_with("cunning", resources=Resources(spice=1))
    assert _intrigue_reason(cunning, "cunning", 1) == (
        _NO_CARD_TO_DRAW[0] + "; No card in hand, discard pile or play to trash",
        _NO_CARD_TO_DRAW[1]
        + " · {hand}·{discard_pile}·{in_play}에 {trash}할 카드 없음",
        "reward",
    )
    # One effect left that can change something: an ordinary play.
    drawable = replace(mercenaries, intrigue_deck=("intrigue:bribery:0",))
    assert {"card_id": "intrigue:mercenaries:0", "option": 0} in _legal(
        drawable, "play_intrigue"
    )


def test_call_to_arms_row_explains_nothing_left_to_acquire() -> None:
    """Call to Arms in the seat's own Reveal turn with nothing it could
    still acquire there would recruit nothing (user ruling 2026-10-06)."""

    state = _state(
        PlayerState(player_id=0, intrigue_cards=("intrigue:call_to_arms:0",)),
        imperium_row=ROW,
        reserve_stacks=(("prepare_the_way", 8), ("the_spice_must_flow", 0)),
    )
    assert _intrigue_reason(_reveal(state, 0), "call_to_arms") == (
        "Nothing left to acquire in this Reveal turn",
        "이번 공개 차례에 더 획득할 수 있는 카드 없음",
        "reward",
    )
    # Two Persuasion buy Prepare the Way: the play is offered.
    assert {"card_id": "intrigue:call_to_arms:0", "option": 0} in _legal(
        _reveal(state, 2), "play_intrigue"
    )


def test_an_intrigue_row_becomes_a_play_as_soon_as_the_seat_can_pay() -> None:
    poor = _intrigue_state("imperium_politics")
    rich = _intrigue_state("imperium_politics", resources=Resources(solari=1))
    politics = {"card_id": "intrigue:imperium_politics:0", "option": 0}

    assert _legal(poor, "play_intrigue") == []
    assert [row["key"] for row in _found(poor)["rows"]] == [
        "intrigue:intrigue:imperium_politics:0:0"
    ]
    assert _legal(rich, "play_intrigue") == [politics]
    assert unavailable_choices(rich, 0, ENGINE.whole_actions(rich, 0)) is None


def test_finishing_a_lines_card_is_greyed_until_one_line_is_used() -> None:
    """At least one of a separate-lines card's lines must be used (OQ-058,
    user ruling 2026-10-04): until then the finish shows greyed out beside
    the lines, and it lights up as soon as one is used."""

    card = "intrigue:strategic_stockpiling:0"
    state = _intrigue_state(
        "strategic_stockpiling",
        influence=Influence(fremen=3),
        resources=Resources(spice=5, water=3),
    )
    play = DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card), ("option", 0)),
    )
    opened = apply_whole(ENGINE, state, play).state
    assert opened.decision_stack[-1].kind == FrameKind.INTRIGUE_EFFECTS
    assert _legal(opened, "finish_intrigue_effects") == []
    found = _found(opened)
    assert found["frame"] == FrameKind.INTRIGUE_EFFECTS
    (row,) = found["rows"]
    assert row["key"] == "choice:finish_intrigue_effects"
    assert row["surface"] == "choice"
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "Use at least one of its lines first",
        "먼저 줄을 하나 이상 써야 함",
        "line_first",
    )
    assert row["action"]["action_id"] == "finish_intrigue_effects"
    assert row["action"]["arguments"] == {}

    used = apply_whole(ENGINE, 
        opened,
        DomainAction(
            action_id="use_intrigue_effect", actor=0, arguments=(("section", 0),)
        ),
    ).state
    assert used.decision_stack[-1].kind == FrameKind.INTRIGUE_EFFECTS
    assert _legal(used, "finish_intrigue_effects") == [{}]
    assert unavailable_choices(used, 0, ENGINE.whole_actions(used, 0)) is None


# --- Effects waiting on their condition ---


def test_a_pending_reveal_choice_waits_greyed_out_until_its_condition_holds() -> None:
    """In High Places' two-Spy recall waits while one Spy is out; once Wheels
    Within Wheels' Reveal Spy is placed its own rows are offered (the fixture
    of test_reveal_turn.py's unavailable-choice test) [Main p. 12]. Every
    choice waits on the Reveal frame (OQ-095 (7) addition, codec v147), so the
    waiting row sits beside the legal Spy placement."""

    def instance(card_id: str) -> str:
        return next(i for i in imperium_deck_instance_ids(False) if f":{card_id}:" in i)

    in_high_places = instance("in_high_places")
    wheels = instance("wheels_within_wheels")
    state = _state(
        PlayerState(
            player_id=0,
            hand=(in_high_places, wheels),
            spies_supply=2,
            spy_post_ids=("arrakis-hagga-basin",),
        )
    )
    revealed = apply_whole(
        ENGINE, state, DomainAction(action_id="reveal_turn", actor=0)
    )
    pending = revealed.state
    assert pending.decision_stack[-1].kind == FrameKind.REVEAL

    rows = _rows(_found(pending), "waiting")
    recall = "may_recall_two_spies_for_three_persuasion"
    assert list(rows) == [f"waiting:{in_high_places}:{recall}"]
    row = rows[f"waiting:{in_high_places}:{recall}"]
    # The never-legal row that names the waiting choice's effect, led by its
    # card and worded as the card's choice (display.actions
    # reveal_choice_text), not "미룬 선택 재개".
    assert row["action"]["action_id"] == "resume_reveal_choice"
    assert row["action"]["arguments"] == {"effect": recall}
    assert row["action"]["detail"] == "You may recall 2 Spies → +3 Persuasion"
    assert row["action"]["detail_ko"] == (
        "{spy} 2 소환 가능 {arrow_right} {persuasion:3}"
    )
    assert (row["action"]["detail_title"], row["action"]["detail_title_ko"]) == (
        "In High Places",
        "높은 자리에서",
    )
    assert row["card_id"] == in_high_places
    assert row["reveal_choice"] == f"{in_high_places}:{recall}"
    assert "title_card" not in row
    # What keeps it closed, and that an optional choice lapses unused.
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "Needs 2 Spies of yours on the board (you have 1);"
        " it lapses unused when the Reveal turn ends",
        "보드에 내 {spy:2} 필요 (보유 1) — {reveal_turn}를 끝내면 쓰지 않은 채 사라짐",
        "waiting",
    )
    assert _legal(pending, "recall_spies_for_reveal") == []

    placement = next(
        action
        for action in ENGINE.whole_actions(pending, 0)
        if action.action_id == "place_reveal_spy"
    )
    placed = apply_whole(ENGINE, pending, placement).state
    assert placed.decision_stack[-1].kind == FrameKind.REVEAL
    assert _legal(placed, "recall_spies_for_reveal")
    found = unavailable_choices(placed, 0, ENGINE.whole_actions(placed, 0))
    assert found is None or not _rows(found, "waiting")


def _waiting_reveal_row(owner: PlayerState) -> dict[str, Any]:
    """Seat 0 reveals ``owner``'s hand (Bloodlines with CHOAM): the one
    waiting Reveal choice's greyed-out row."""

    state = _state(owner, config=RulesetConfig(bloodlines=True, choam_module=True))
    revealed = apply_whole(
        ENGINE, state, DomainAction(action_id="reveal_turn", actor=0)
    )
    assert revealed.state.decision_stack[-1].kind == FrameKind.REVEAL
    (row,) = _rows(_found(revealed.state), "waiting").values()
    return row


def test_a_command_choice_waits_with_the_persuasion_generated_so_far() -> None:
    """Pointing the Way's "Command (6+ Persuasion)" gain [Bloodlines p. 5] is
    judged on the Persuasion the Reveal turn generates [Bloodlines p. 12]:
    below six it waits greyed out with that figure, and a mandatory choice
    lapses only if still unmet when the Reveal ends (OQ-095 (7) addition)."""

    pointing = "imperium:pointing_the_way:0"
    row = _waiting_reveal_row(PlayerState(player_id=0, hand=(pointing,)))
    assert row["key"] == f"waiting:{pointing}:command_gain_chosen_influence"
    assert (row["action"]["detail_title"], row["action"]["detail_title_ko"]) == (
        "Pointing the Way",
        "길을 가리키다",
    )
    assert row["action"]["detail"] == (
        "Command (6+ Persuasion): Gain 1 Influence with a chosen Faction"
    )
    assert (row["reason"], row["reason_ko"]) == (
        "Command: needs 6 Persuasion generated this Reveal turn (you have 1);"
        " it lapses if still unmet when the Reveal turn ends",
        "{command}: 이번 {reveal_turn}에 만든 {persuasion:6} 필요 (지금 1)"
        " — {reveal_turn}를 끝낼 때까지 못 채우면 사라짐",
    )


def test_a_fremen_bond_choice_waits_for_another_fremen_card() -> None:
    """Unswerving Loyalty: "Fremen Bond: You may deploy or retreat one of your
    troops" [Unswerving Loyalty card], an optional choice: without another
    Fremen card in play it waits, and lapses unused when the Reveal ends."""

    loyalty = "imperium:unswerving_loyalty:0"
    row = _waiting_reveal_row(
        PlayerState(player_id=0, hand=(loyalty,), troops_supply=10, troops_garrison=2)
    )
    assert (row["reason"], row["reason_ko"]) == (
        "Fremen Bond: needs another Fremen card in play;"
        " it lapses unused when the Reveal turn ends",
        "프레멘의 유대감: {in_play}에 다른 프레멘 카드 필요"
        " — {reveal_turn}를 끝내면 쓰지 않은 채 사라짐",
    )


def test_a_spice_payment_choice_waits_for_the_spice() -> None:
    """Spacing Guild's Favor's "3 spice -> Influence" arrow, short of spice."""

    favor = "imperium:spacing_guild_s_favor:0"
    row = _waiting_reveal_row(
        PlayerState(player_id=0, hand=(favor,), resources=Resources(spice=1))
    )
    assert (row["reason"], row["reason_ko"]) == (
        "Needs 3 spice (you have 1); it lapses unused when the Reveal turn ends",
        "{spice:3} 필요 (보유 1) — {reveal_turn}를 끝내면 쓰지 않은 채 사라짐",
    )


def test_a_choice_whose_card_another_effect_trashed_says_it_left_play() -> None:
    """"You can't receive or activate an effect from a card that is already
    trashed" (designer ruling, OQ-022; the Reveal's choices too, its
    2026-09-07 addition): once Calculus of Power trashes Corrinth City, the
    City's mandatory "-OR-" offers nothing and greys out with why, and that
    it simply lapses when the Reveal ends -- no later effect can meet it."""

    calculus = "imperium:calculus_of_power:0"
    corrinth = "imperium:corrinth_city:0"
    state = _state(
        PlayerState(
            player_id=0,
            hand=(calculus, corrinth),
            resources=Resources(solari=9),
            troops_supply=8,
            troops_conflict=1,
        ),
        config=RulesetConfig(bloodlines=True, choam_module=True),
    )
    revealed = apply_whole(
        ENGINE, state, DomainAction(action_id="reveal_turn", actor=0)
    )
    trash = next(
        action
        for action in ENGINE.whole_actions(revealed.state, 0)
        if action.action_id == "trash_reveal_card"
        and dict(action.arguments)["card_id"] == corrinth
    )
    trashed = apply_whole(ENGINE, revealed.state, trash).state
    rows = _rows(_found(trashed), "waiting")
    choice = "gain_five_solari_or_take_high_council"
    assert list(rows) == [f"waiting:{corrinth}:{choice}"]
    row = rows[f"waiting:{corrinth}:{choice}"]
    assert row["reveal_choice"] == f"{corrinth}:{choice}"
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "This card is no longer in play; it lapses when the Reveal turn ends",
        "이 카드가 더는 {in_play}에 없음 — {reveal_turn}를 끝내면 사라짐",
        "waiting",
    )


def test_a_withheld_agent_box_waits_greyed_out_until_its_condition_holds() -> None:
    """Prepare the Way's "draw a card with 2 Bene Gesserit Influence" is
    withheld while the Influence is short (OQ-057) and offered once it holds."""

    card = "reserve:prepare_the_way:0"
    state = _state(PlayerState(player_id=0, hand=(card,)))
    placement = next(iter(executable_placements(state, 0)))
    placed = apply_placement(ENGINE, state, placement).state
    assert placed.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    assert _legal(placed, "resolve_agent_card_effect") == []

    rows = list(_rows(_found(placed), "waiting").values())
    assert [row["action"]["action_id"] for row in rows] == ["resolve_agent_card_effect"]
    assert rows[0]["card_id"] == card
    assert rows[0]["code"] == "waiting"

    owner = placed.players[0]
    influence = Influence(bene_gesserit=2)
    met = replace(
        placed, players=(replace(owner, influence=influence), *placed.players[1:])
    )
    assert _legal(met, "resolve_agent_card_effect") == [{}]
    found = unavailable_choices(met, 0, ENGINE.whole_actions(met, 0))
    assert found is None or not _rows(found, "waiting")


def test_empty_gather_intelligence_is_offered_without_greyed_or_waiting_rows() -> None:
    """Gather Intelligence replaces the whole Agent-effect list while it is
    pending (``legal_agent_effect_frame_actions``). With both personal piles
    empty its recall is still offered (OQ-099, user ruling 2026-10-07
    "허용 (앱처럼)"), so nothing is greyed out, and the waiting box stays
    hidden. The box returns, greyed out, once the seat has declined."""

    card = "reserve:prepare_the_way:0"
    post = next(
        post
        for post in OBSERVATION_POSTS
        if "assembly_hall" in post.connected_space_ids
    )
    owner = PlayerState(
        player_id=0, hand=(card,), spy_post_ids=(post.post_id,), spies_supply=2
    )
    placed = apply_placement(
        ENGINE,
        _state(owner),
        DomainAction(
            action_id="agent_turn",
            actor=0,
            arguments=(("card_id", card), ("space_id", "assembly_hall")),
        ),
    ).state
    legal = ENGINE.whole_actions(placed, 0)

    assert [
        (action.action_id, dict(action.arguments)) for action in legal
    ] == [
        ("decline_gather_intelligence", {}),
        ("gather_intelligence", {"post_id": post.post_id}),
    ]
    assert agent_box_is_waiting(placed, 0)  # withheld (OQ-057), behind the choice
    assert unavailable_choices(placed, 0, legal) is None
    assert unavailable_choices(placed, 1, legal) is None

    declined = apply_whole(ENGINE, 
        placed, DomainAction(action_id="decline_gather_intelligence", actor=0)
    ).state
    rows = list(_rows(_found(declined), "waiting").values())
    assert [row["key"] for row in rows] == [f"waiting:agent_box:{card}"]
    assert not agent_box_is_waiting(declined, 1)  # only the box's owner's


_FULL = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
_ALL_AT_THE_TOP = {
    "reason": "Every Faction it can raise is already at the top (6)",
    "reason_ko": "올릴 수 있는 {faction}의 {influence_any}이 모두 이미 최고치(6)",
    "code": "top",
}


def test_an_influence_cost_line_with_every_cube_at_the_top_is_greyed() -> None:
    """A cost for Influence no cube can take is not offered (OQ-060,
    OQ-071): Imperium Politics with Emperor and Guild at 6 greys out with
    that reason, in both languages."""

    found = _found(
        _intrigue_state(
            "imperium_politics",
            resources=Resources(solari=1),
            influence=Influence(emperor=6, spacing_guild=6),
        )
    )
    (row,) = _rows(found, "intrigue").values()
    assert row["action"]["arguments"]["card_id"] == "intrigue:imperium_politics:0"
    assert {key: row[key] for key in ("reason", "reason_ko", "code")} == (
        _ALL_AT_THE_TOP
    )


def test_shaddam_s_signet_influence_with_every_cube_at_the_top_is_greyed() -> None:
    """Emperor of the Known Universe's three Solari buy nothing with every
    cube at 6 (OQ-060, OQ-071): only the Solari and troop is offered, and
    the payment shows greyed out beside it."""

    signet = "player:0:starter:signet_ring:0"
    owner = PlayerState(
        player_id=0,
        leader_id="shaddam_corrino_iv",
        resources=Resources(solari=3),
        hand=(signet,),
        influence=_FULL,
    )
    placed = _agent_turn(
        _state(owner, config=RulesetConfig(choam_module=True)), signet, "arrakeen"
    )
    assert "choose_leader_signet_influence" not in {
        action.action_id for action in ENGINE.whole_actions(placed, 0)
    }
    row = _rows(_found(placed), "choice")["choice:leader_signet_influence"]
    assert row["action"]["action_id"] == "choose_leader_signet_influence"
    assert {key: row[key] for key in ("reason", "reason_ko", "code")} == (
        _ALL_AT_THE_TOP
    )


def test_a_choose_a_faction_box_with_every_cube_at_the_top_waits_with_why() -> None:
    """Interstellar Trade's Influence with every cube at 6 waits for the
    turn's end (OQ-057 (1), OQ-060); the waiting row names the reason."""

    card = "imperium:interstellar_trade:0"
    owner = PlayerState(player_id=0, hand=(card,), influence=_FULL)
    placed = _agent_turn(
        _state(owner, config=RulesetConfig(choam_module=True)), card, "assembly_hall"
    )
    while board := [
        action
        for action in ENGINE.whole_actions(placed, 0)
        if action.action_id == "resolve_board_effect"
    ]:
        placed = apply_whole(ENGINE, placed, board[0]).state
    assert agent_box_is_waiting(placed, 0)
    row = _rows(_found(placed), "waiting")[f"waiting:agent_box:{card}"]
    assert row["reason"] == (
        "Every Faction it can raise is already at the top (6); it lapses if"
        " still unmet when the turn ends"
    )
    assert row["reason_ko"] == (
        "올릴 수 있는 {faction}의 {influence_any}이 모두 이미 최고치(6)"
        " — 차례가 끝날 때까지 못 채우면 사라짐"
    )
    assert row["code"] == "waiting"
    # The greyed row is led by its card and its box, like a legal box row
    # (display.actions.agent_box_row_title, user request 2026-10-11).
    action = row["action"]
    assert (action["detail_title"], action["detail_title_ko"]) == (
        "Interstellar Trade",
        "성간 교역",
    )
    assert action["detail"] and action["detail_ko"]


def test_a_reveal_influence_choice_with_every_cube_at_the_top_waits_with_why() -> (
    None
):
    """Spacing Guild's Favor's three spice with every cube at 6: the choice
    waits deferred and lapses with the Reveal (OQ-060, OQ-071)."""

    favor = "imperium:spacing_guild_s_favor:0"
    owner = PlayerState(
        player_id=0, hand=(favor,), resources=Resources(spice=3), influence=_FULL
    )
    revealed = apply_whole(ENGINE, 
        _state(owner), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    row = _rows(_found(revealed), "waiting")[
        f"waiting:{favor}:may_pay_three_spice_for_influence"
    ]
    assert row["reason"].startswith(_ALL_AT_THE_TOP["reason"])
    assert row["reason_ko"].startswith(_ALL_AT_THE_TOP["reason_ko"])
    assert row["code"] == "waiting"


def _agent_turn(
    state: GameState, card: str, space: str, **arguments: Any
) -> GameState:
    action = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)
        == {"card_id": card, "space_id": space, **arguments}
    )
    return apply_placement(ENGINE, state, action).state


def _payment_row(state: GameState) -> dict[str, Any]:
    (row,) = [
        row
        for row in _rows(_found(state), "choice").values()
        if row["key"].startswith("choice:agent_payment:")
    ]
    return row


# An optional effect of the Agent turn offers no refusal, and the turn's end
# lapses it (OQ-095 (2), user ruling 2026-10-14): its greyed row says so,
# and, while another effect of the turn offers a row, that one could still
# enable it (docs/unavailable-options-plan.md 1, the free order wording).
LAPSES = (
    "; it lapses unused when the turn ends",
    " — 차례가 끝나면 쓰지 않은 채 사라짐",
)
FREE_ORDER = (
    "; another effect of this turn can still meet it, and unused it lapses"
    " when the turn ends",
    " — 이번 차례의 다른 효과로 채우면 가능, 쓰지 않으면 차례가 끝날 때 사라짐",
)


def _lapsing(
    reason: tuple[str, str, str], tail: tuple[str, str]
) -> tuple[str, str, str]:
    return reason[0] + tail[0], reason[1] + tail[1], reason[2]


def _why(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["reason"], row["reason_ko"], row["code"]


def _optional_box_row(state: GameState) -> dict[str, Any]:
    """The one greyed row of an optional Agent box that offers nothing."""

    rows: list[dict[str, Any]] = [
        row
        for row in _found(state)["rows"]
        if row["key"].split(":", 1)[1].startswith("optional_box:")
    ]
    (row,) = rows
    return row


def test_an_agent_box_draw_with_empty_piles_greys_out_its_water() -> None:
    """Ecological Testing Station's "2 water -> draw 2" with an empty deck
    and discard pile buys nothing (OQ-071): the payment is not offered, and
    the box, optional (OQ-095 (2)), offers nothing at all. It shows greyed
    out with Gather Intelligence's reason, among the waiting effects while
    the visit's own card draw is still to come (a discard of the turn
    refills the pile)."""

    station = "imperium:ecological_testing_station:0"
    owner = PlayerState(player_id=0, hand=(station,), resources=Resources(water=2))
    placed = _agent_turn(_state(owner), station, "fremkit")
    assert "pay_agent_card_water" not in {
        action.action_id for action in ENGINE.whole_actions(placed, 0)
    }
    row = _optional_box_row(placed)
    assert row["surface"] == "waiting"
    assert row["action"]["action_id"] == "resolve_agent_card_effect"
    assert row["action"]["arguments"] == {}
    assert row["action"]["detail_title"] == "Ecological Testing Station"
    assert row["card_id"] == station
    assert _why(row) == _lapsing(
        (
            "No card to draw: your deck and discard pile are both empty",
            "뽑을 카드 없음: 덱과 버린 카드 더미가 모두 비었음",
            "empty",
        ),
        FREE_ORDER,
    )

    refilled = replace(
        placed,
        players=(
            replace(placed.players[0], discard_pile=("player:0:starter:dagger:0",)),
            *placed.players[1:],
        ),
    )
    legal = ENGINE.whole_actions(refilled, 0)
    assert "pay_agent_card_water" in {action.action_id for action in legal}
    assert unavailable_choices(refilled, 0, legal) is None


def test_tleilaxu_agent_payments_grey_out_at_the_track_end() -> None:
    """Tleilaxu Surgeon's "2 specimens -> 2 Tleilaxu" and Slig Farmer's
    "5 Solari -> Tleilaxu" with the token on the last space (OQ-048,
    OQ-071)."""

    config = RulesetConfig(immortality=True)
    supply = PlayerState(player_id=0).troops_supply
    surgeon = "imperium:tleilaxu_surgeon:0"
    owner = PlayerState(
        player_id=0,
        hand=(surgeon,),
        troops_supply=supply - 2,
        specimens=2,
        research_space=RESEARCH_START_ID,
        tleilaxu_space=7,
    )
    placed = _agent_turn(_state(owner, config=config), surgeon, "arrakeen")
    # The optional box offers nothing (OQ-095 (2)); the track's end never
    # comes back, so it sits among the choices, whatever else is left.
    row = _optional_box_row(placed)
    assert row["surface"] == "choice"
    assert row["action"]["action_id"] == "resolve_agent_card_effect"
    assert row["card_id"] == surgeon
    assert _why(row) == _lapsing(_TLEILAXU_TRACK_END, LAPSES)

    farmer = "tleilaxu:slig_farmer:0"
    face_dancer = "tleilaxu:face_dancer:0"
    owner = PlayerState(
        player_id=0,
        hand=(farmer, face_dancer),
        resources=Resources(solari=5),
        research_space=RESEARCH_START_ID,
        tleilaxu_space=7,
    )
    placed = _agent_turn(
        _state(owner, config=config), farmer, "assembly_hall", graft=True
    )
    grafted = apply_whole(ENGINE, 
        placed,
        DomainAction(
            action_id="choose_graft_partner",
            actor=0,
            arguments=(("card_id", face_dancer),),
        ),
    ).state
    assert "pay_agent_card_five_solari_for_tleilaxu" not in {
        action.action_id for action in ENGINE.whole_actions(grafted, 0)
    }
    row = _payment_row(grafted)
    assert row["action"]["action_id"] == "pay_agent_card_five_solari_for_tleilaxu"
    assert (row["reason"], row["reason_ko"], row["code"]) == _TLEILAXU_TRACK_END


# --- A branch of an open choice that cannot be taken now ---


def _desert_power(
    *, owner_fields: dict[str, Any] | None = None, **fields: Any
) -> GameState:
    """Seat 0 reveals Desert Power: its choice waits on the Reveal frame."""

    desert_power = next(
        i for i in imperium_deck_instance_ids(False) if ":desert_power:" in i
    )
    owner = replace(
        PlayerState(
            player_id=0,
            hand=(desert_power,),
            maker_hooks=True,
            resources=Resources(water=1),
        ),
        **(owner_fields or {}),
    )
    state = _state(owner, **{"current_conflict_ids": ("propaganda",), **fields})
    revealed = apply_whole(
        ENGINE, state, DomainAction(action_id="reveal_turn", actor=0)
    )
    assert revealed.state.decision_stack[-1].kind == FrameKind.REVEAL
    assert pending_reveal_choices(dict(revealed.state.decision_stack[-1].context)) == (
        (desert_power, "may_pay_water_for_sandworm"),
    )
    return revealed.state


def test_desert_power_without_maker_hooks_greys_out_the_sandworm_branch() -> None:
    """Option (B), user ruling 2026-09-30: "REVEAL_CHOICE 창을 열어 '설득 2'만
    고르게, 모래벌레 줄은 '메이커 작살 없음' 회색". The row sits on the new
    "choice" surface and names the card; the Persuasion branch is legal. The
    choice is a row of the Reveal frame (OQ-095 (7) addition, codec v147)."""

    state = _desert_power(owner_fields={"maker_hooks": False})
    found = _found(state)
    assert found["frame"] == FrameKind.REVEAL
    assert [row["surface"] for row in found["rows"]] == ["choice"]
    row = _rows(found, "choice")["choice:pay_reveal_water_for_sandworm"]
    assert row["action"]["action_id"] == "pay_reveal_water_for_sandworm"
    assert row["action"]["arguments"] == {}
    ((desert_power, _),) = pending_reveal_choices(
        dict(state.decision_stack[-1].context)
    )
    assert row["card_id"] == desert_power
    # Under its card's header on the page (codec v147).
    assert row["reveal_choice"] == f"{desert_power}:may_pay_water_for_sandworm"
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "No Maker Hooks",
        "{maker_hooks} 없음",
        "maker_hooks",
    )
    assert _legal(state, "decline_reveal_sandworm") == [{}]
    assert found["refs"] == {}


def test_each_sandworm_block_has_its_own_reason() -> None:
    """Water, a Conflict and the Shield Wall, in the block's order."""

    cases = [
        (
            _desert_power(owner_fields={"resources": Resources(water=0)}),
            ("Needs 1 water (you have 0)", "{water:1} 필요 (보유 0)", "cost"),
        ),
        (
            _desert_power(current_conflict_ids=()),
            ("No Conflict this round", "이번 라운드에 교전 없음", "no_conflict"),
        ),
        (
            _desert_power(
                current_conflict_ids=("siege_of_arrakeen",), shield_wall_present=True
            ),
            (
                "The Shield Wall protects this Conflict",
                "{shield_wall}이 이번 교전을 보호함",
                "shield_wall",
            ),
        ),
    ]
    for state, reason in cases:
        row = _rows(_found(state), "choice")["choice:pay_reveal_water_for_sandworm"]
        assert (row["reason"], row["reason_ko"], row["code"]) == reason


def test_no_sandworm_row_while_the_sandworm_branch_is_legal() -> None:
    state = _desert_power()
    assert _legal(state, "pay_reveal_water_for_sandworm") == [{}]
    assert unavailable_choices(state, 0, ENGINE.whole_actions(state, 0)) is None


def test_desert_power_without_maker_hooks_shows_no_waiting_row() -> None:
    """The old "waiting" row (a choice whose condition could still come true)
    is not shown: without Maker Hooks the choice is still offered, since its
    Persuasion branch can always be taken."""

    state = _desert_power(owner_fields={"maker_hooks": False})
    assert _legal(state, "decline_reveal_sandworm") == [{}]
    assert not _rows(_found(state), "waiting")


# --- A recall with no other Agent to recall ---

_NO_OTHER_AGENT = (
    "No other Agent of yours to recall (not the one sent this turn)",
    "소환할 다른 {agent} 없음 (이번 차례에 보낸 {agent} 제외)",
    "no_target",
)


def _place(state: GameState, space_id: str) -> GameState:
    action = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["space_id"] == space_id
    )
    return apply_placement(ENGINE, state, action).state


def _imperial_owner(**owner_fields: Any) -> PlayerState:
    return PlayerState(
        player_id=0,
        hand=("player:0:starter:dagger:0",),
        resources=Resources(solari=3),
        influence=Influence(emperor=2),
        **owner_fields,
    )


def _imperial_privilege(**owner_fields: Any) -> GameState:
    """Seat 0 at Imperial Privilege: its optional Intrigue trade and its
    recall are offered together (user ruling 2026-10-14)."""

    return _place(_state(_imperial_owner(**owner_fields)), "imperial_privilege")


_NO_INTRIGUE_TO_TRASH = (
    "No Intrigue card to trash",
    "폐기할 {intrigue_card} 없음",
    "cost",
)


def test_imperial_privilege_with_no_other_agent_greys_out_the_recall() -> None:
    """OQ-023: with no other Agent only the recall is skipped and the card
    still drawn; user ruling 2026-09-30 ("결정 창 없이 자동으로 넘어가는
    곳도 모두 결정 창을 연다") makes the owner confirm it, with the recall
    greyed out beside the confirm on the "choice" surface. Since the user
    ruling of 2026-10-10 ("4번은 소환과 뽑기가 당연히 두 단계로 나눠야지",
    OQ-027 (d)) the draw is the space's own ``cards`` icon: offered beside
    the confirm and left pending by it. The optional Intrigue trade, with
    no Intrigue card in hand, offers nothing (OQ-095 (2)) and waits while
    the draw is left; once nothing else is, it sits among the choices."""

    state = _imperial_privilege()
    assert _legal(state, "resolve_imperial_privilege_without_recall") == [{}]
    assert _legal(state, "resolve_board_effect") == [{"effect": "cards"}]
    assert _legal(state, "trash_intrigue_for_imperial_privilege") == []
    found = _found(state)
    assert found["frame"] == FrameKind.AGENT_EFFECTS
    row = _rows(found, "choice")["choice:imperial_privilege_recall"]
    assert row["action"]["action_id"] == "recall_agent_for_imperial_privilege"
    assert row["action"]["arguments"] == {}
    assert (row["reason"], row["reason_ko"], row["code"]) == _NO_OTHER_AGENT
    assert row["refs"] == []
    trade = _rows(found, "waiting")["waiting:imperial_privilege_intrigue"]
    assert trade["action"]["action_id"] == "trash_intrigue_for_imperial_privilege"
    assert trade["action"]["arguments"] == {}
    assert _why(trade) == _lapsing(_NO_INTRIGUE_TO_TRASH, FREE_ORDER)

    # The confirm draws nothing and the row goes with the pending recall;
    # the draw stays offered on its own.
    confirmed = apply_whole(ENGINE, 
        state,
        DomainAction(action_id="resolve_imperial_privilege_without_recall", actor=0),
    ).state
    assert confirmed.players[0].hand == state.players[0].hand
    assert _legal(confirmed, "resolve_board_effect") == [{"effect": "cards"}]
    after = unavailable_choices(confirmed, 0, ENGINE.whole_actions(confirmed, 0))
    assert after is None or not _rows(after, "choice")

    drawn = apply_whole(ENGINE, 
        confirmed,
        DomainAction(
            action_id="resolve_board_effect", actor=0, arguments=(("effect", "cards"),)
        ),
    ).state
    assert [action.action_id for action in ENGINE.whole_actions(drawn, 0)] == [
        "finish_agent_turn"
    ]
    last = _rows(_found(drawn), "choice")["choice:imperial_privilege_intrigue"]
    assert _why(last) == _lapsing(_NO_INTRIGUE_TO_TRASH, LAPSES)


def test_no_recall_row_while_imperial_privilege_has_a_target() -> None:
    state = _imperial_privilege(agents_available=1, agent_locations=("arrakeen",))
    assert _legal(state, "recall_agent_for_imperial_privilege") == [
        {"space_id": "arrakeen"}
    ]
    assert _legal(state, "resolve_imperial_privilege_without_recall") == []
    found = unavailable_choices(state, 0, ENGINE.whole_actions(state, 0))
    assert found is None or not _rows(found, "choice")
    # With an Intrigue card in hand the trade is offered beside the recall,
    # and nothing greys it out.
    card = "intrigue:held"
    held = _imperial_privilege(
        agents_available=1, agent_locations=("arrakeen",), intrigue_cards=(card,)
    )
    assert _legal(held, "trash_intrigue_for_imperial_privilege") == [
        {"card_id": card}
    ]
    assert unavailable_choices(held, 0, ENGINE.whole_actions(held, 0)) is None


def _sardaukar_ii(**owner_fields: Any) -> GameState:
    """Seat 0 completes Sardaukar II at the Sardaukar space."""

    truthtrance = next(
        i for i in imperium_deck_instance_ids(True) if ":truthtrance:" in i
    )
    owner = PlayerState(
        player_id=0,
        hand=(truthtrance,),
        resources=Resources(solari=10, spice=10, water=10),
        active_contract_ids=("contract:sardaukar_ii",),
        **owner_fields,
    )
    placed = _place(
        _state(owner, config=RulesetConfig(choam_module=True)), "sardaukar"
    )
    complete = next(
        action
        for action in ENGINE.whole_actions(placed, 0)
        if action.action_id == "complete_contract"
    )
    # The reward waits in its window (stage B2, OQ-112); answer it up to the
    # recall frame its recall icon opens.
    completed = answer_reward_windows(ENGINE, apply_whole(
        ENGINE, placed, complete
    ).state)
    assert completed.decision_stack[-1].kind == FrameKind.CONTRACT_REWARD_RECALL
    return completed


def test_a_contract_recall_with_no_other_agent_greys_out_the_recall() -> None:
    """Sardaukar II's reward "simply fizzles" with no other Agent (the
    designer's ruling, OQ-057); its window now opens with only the confirm
    and the recall greyed out (user ruling 2026-09-30)."""

    state = _sardaukar_ii()
    assert [
        action.action_id for action in ENGINE.whole_actions(state, 0)
    ] == ["resolve_contract_without_recall"]
    found = _found(state)
    assert found["frame"] == FrameKind.CONTRACT_REWARD_RECALL
    assert [row["key"] for row in found["rows"]] == ["choice:contract_recall"]
    row = found["rows"][0]
    assert row["action"]["action_id"] == "recall_agent_for_contract"
    assert row["action"]["arguments"] == {}
    assert (row["reason"], row["reason_ko"], row["code"]) == _NO_OTHER_AGENT


def test_no_contract_recall_row_while_the_reward_has_a_target() -> None:
    state = _sardaukar_ii(agents_available=1, agent_locations=("arrakeen",))
    assert _legal(state, "recall_agent_for_contract") == [{"space_id": "arrakeen"}]
    assert unavailable_choices(state, 0, ENGINE.whole_actions(state, 0)) is None


# --- A research bonus whose cost cannot be paid ---


def _research_bonus(origin: str, target: str, **owner_fields: Any) -> GameState:
    """Seat 0 advances its research token from ``origin`` to ``target`` in
    its own turn: the bonus then waits on the turn frame as rows
    (cleanup-2b, ``turn_rows``)."""

    owner = PlayerState(player_id=0, research_space=origin, **owner_fields)
    state = _state(owner, config=RulesetConfig(immortality=True))
    advanced = advance_research(state, 0, source="test").state
    choice = next(
        action
        for action in ENGINE.whole_actions(advanced, 0)
        if action.action_id == "choose_research_space"
        and dict(action.arguments)["space_id"] == target
    )
    chosen = apply_whole(ENGINE, advanced, choice).state
    assert chosen.decision_stack[-1].kind == FrameKind.TURN
    assert pending_research_bonuses(chosen, 0)
    return chosen


def _research_rows(found: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = found["rows"] if found is not None else []
    return [row for row in rows if "research" in row["key"]]


_FREE_ORDER = (
    "; another effect of this turn can still meet it, and unused it lapses"
    " when the turn ends",
    " — 이번 차례의 다른 효과로 채우면 가능, 쓰지 않으면 차례가 끝날 때 사라짐",
)


def test_a_research_bonus_without_an_intrigue_card_greys_out_the_trash() -> None:
    """c7r3's "Trash an Intrigue card" arrow [Immortality p. 16] with an
    empty Intrigue hand, waiting on the turn (cleanup-2b): no row and no
    decline; the trash shows greyed out with the waiting ones -- an Intrigue
    card drawn later in the turn would pay for it -- naming no card, and
    says it lapses."""

    state = _research_bonus("c6r2", "c7r3")
    legal = {action.action_id for action in ENGINE.whole_actions(state, 0)}
    assert not legal & {
        "trash_intrigue_for_research_bonus",
        "decline_research_bonus",
    }
    found = _found(state)
    assert found["frame"] == FrameKind.TURN
    rows = _research_rows(found)
    assert [row["key"] for row in rows] == ["waiting:research_bonus_trash"]
    row = rows[0]
    assert row["action"]["action_id"] == "trash_intrigue_for_research_bonus"
    assert row["action"]["arguments"] == {}
    assert row["refs"] == []
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "No Intrigue card to trash" + _FREE_ORDER[0],
        "폐기할 {intrigue_card} 없음" + _FREE_ORDER[1],
        "cost",
    )


def test_a_research_bonus_short_of_solari_greys_out_the_payment() -> None:
    """c8r6's "7 Solari -> two Tleilaxu" arrow with 3 Solari."""

    state = _research_bonus("c7r5", "c8r6", resources=Resources(solari=3))
    assert _legal(state, "pay_research_bonus") == []
    rows = _research_rows(_found(state))
    assert [row["key"] for row in rows] == ["waiting:research_bonus_pay"]
    row = rows[0]
    assert row["action"]["action_id"] == "pay_research_bonus"
    assert row["action"]["arguments"] == {}
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "Needs 7 solari (you have 3)" + _FREE_ORDER[0],
        "{solari:7} 필요 (보유 3)" + _FREE_ORDER[1],
        "cost",
    )


def test_a_research_bonus_at_the_tleilaxu_track_end_greys_out_the_payment() -> None:
    """c8r6's "7 Solari -> two Tleilaxu" arrow with the token on the last
    space: the advances would do nothing (OQ-048), so the cost is not
    offered (OQ-071) and shows greyed out with that reason; nothing in the
    turn can change it, so it lapses unused."""

    state = _research_bonus(
        "c7r5", "c8r6", resources=Resources(solari=9), tleilaxu_space=7
    )
    assert _legal(state, "pay_research_bonus") == []
    rows = _research_rows(_found(state))
    assert [row["key"] for row in rows] == ["choice:research_bonus_pay"]
    row = rows[0]
    assert row["action"]["action_id"] == "pay_research_bonus"
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        _TLEILAXU_TRACK_END[0] + "; it lapses unused when the turn ends",
        _TLEILAXU_TRACK_END[1] + " — 차례가 끝나면 쓰지 않은 채 사라짐",
        _TLEILAXU_TRACK_END[2],
    )


def test_a_research_bonus_window_outside_the_turn_greys_out_the_payment() -> None:
    """Outside its owner's turn (Combat, the Arrakeen Scouts step) the
    window opens with only the decline when the cost cannot be paid (user
    ruling 2026-09-30), and the payment shows greyed out on "choice"."""

    owner = PlayerState(
        player_id=0, research_space="c8r6", resources=Resources(solari=3)
    )
    state = _state(owner, config=RulesetConfig(immortality=True))
    window = state.push_decision(
        _bonus_frame(0, ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU, "test")
    )
    assert [action.action_id for action in ENGINE.whole_actions(window, 0)] == [
        "decline_research_bonus"
    ]
    found = _found(window)
    assert found["frame"] == FrameKind.RESEARCH_BONUS
    assert [row["key"] for row in found["rows"]] == ["choice:research_bonus_pay"]
    row = found["rows"][0]
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "Needs 7 solari (you have 3)",
        "{solari:7} 필요 (보유 3)",
        "cost",
    )


def test_a_research_icon_window_adds_no_greyed_out_row() -> None:
    """User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    OQ-027 [Main p. 9]: outside the turn a pair's icons (and c7r3's rewards,
    once its cost is paid) are ordered in one window that offers a row for
    each of them, so nothing is greyed out beside them."""

    owner = PlayerState(player_id=0, research_space="c7r3")
    state = _state(owner, config=RulesetConfig(immortality=True))
    # The arrow's own window, with no Intrigue card to pay it, greys out its
    # trash (the control: this test would otherwise prove nothing).
    arrow = state.push_decision(
        _bonus_frame(0, ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE, "test")
    )
    assert [row["key"] for row in _research_rows(_found(arrow))] == [
        "choice:research_bonus_trash"
    ]
    windows = {
        ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE: ("intrigue", "cards"),
        ResearchBonus.TRASH_AND_SPECIMEN: ("specimen", "trash"),
        ResearchBonus.TLEILAXU_AND_SPECIMEN: ("specimen", "tleilaxu"),
    }
    for bonus, icons in windows.items():
        window = state.push_decision(_bonus_frame(0, bonus, "test", icons=icons))
        legal = ENGINE.whole_actions(window, 0)
        assert {action.action_id for action in legal} == {"resolve_research_icon"}
        assert unavailable_choices(window, 0, legal) is None, bonus


def test_no_research_bonus_row_while_its_cost_can_be_paid() -> None:
    held = "intrigue:ambush:0"
    cases = [
        (_research_bonus("c6r2", "c7r3", intrigue_cards=(held,)), "trash"),
        (
            _research_bonus("c7r5", "c8r6", resources=Resources(solari=7)),
            "pay_research_bonus",
        ),
    ]
    for state, offered in cases:
        legal = ENGINE.whole_actions(state, 0)
        assert any(offered in action.action_id for action in legal), offered
        assert _research_rows(unavailable_choices(state, 0, legal)) == []
    # Nor for the Influence bonus, which has no cost.
    influence = _research_bonus("c5r5", "c6r6")
    found = unavailable_choices(influence, 0, ENGINE.whole_actions(influence, 0))
    assert _research_rows(found) == []


# --- A Conflict reward's Faction already at the top ---

_AT_THE_TOP = ("Already at the top", "이미 최고치", "top")
_INFLUENCE_CONFIRM = DomainAction(
    action_id="resolve_combat_influence_without_faction", actor=0
)


def _combat_reward(conflict_id: str, influence: Influence) -> GameState:
    """Seat 0 alone wins ``conflict_id``: its reward windows are open (the
    reward window's rows are answered up to the first choice, stage B2)."""

    owner = PlayerState(player_id=0, combat_strength=8, influence=influence)
    state = _state(
        owner,
        phase=GamePhase.COMBAT,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        decision_stack=(),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1"),
    )
    return answer_reward_windows(ENGINE, resolve_combat_rewards(state).state)


def _influence_rows(found: dict[str, Any]) -> dict[str, tuple[str, str, str]]:
    rows = _rows(found, "choice")
    for key, row in rows.items():
        faction = row["action"]["arguments"]["faction"]
        assert key == f"choice:combat_reward_influence:{faction}"
    return {
        row["action"]["arguments"]["faction"]: (
            row["reason"],
            row["reason_ko"],
            row["code"],
        )
        for row in rows.values()
    }


def test_a_reward_with_every_faction_at_the_top_greys_them_beside_a_confirm() -> None:
    """OQ-060: the "choose a Faction" reward is lost when every track is at
    6, but the window opens (user ruling 2026-09-30, "결정 창 없이 자동으로
    넘어가는 곳도 모두 결정 창을 연다") with only the confirm, and every
    Faction greyed out "이미 최고치" on the "choice" surface."""

    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _combat_reward("skirmish_crysknife", full)
    assert state.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_INFLUENCE
    assert ENGINE.whole_actions(state, 0) == (_INFLUENCE_CONFIRM,)
    found = _found(state)
    assert found["frame"] == FrameKind.COMBAT_REWARD_INFLUENCE
    assert {row["action"]["action_id"] for row in found["rows"]} == {
        "choose_combat_reward_influence"
    }
    assert _influence_rows(found) == {
        "emperor": _AT_THE_TOP,
        "spacing_guild": _AT_THE_TOP,
        "bene_gesserit": _AT_THE_TOP,
        "fremen": _AT_THE_TOP,
    }
    assert found["refs"] == {}

    confirmed = apply_whole(ENGINE, state, _INFLUENCE_CONFIRM)
    assert "combat_reward_influence_unavailable" in {
        event.kind for event in confirmed.events
    }
    assert confirmed.state.players[0].influence == full


def test_a_faction_at_the_top_is_greyed_beside_the_ones_it_can_take() -> None:
    """A track at 6 can come down again (an Influence loss), so it shows
    greyed out in any reward window, not only the empty one (plan section 4,
    row 14)."""

    state = _combat_reward("spice_freighters", Influence(emperor=6, fremen=2))
    offered = _legal(state, "choose_combat_reward_influence")
    assert [args["faction"] for args in offered] == [
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    ]
    assert _legal(state, "resolve_combat_influence_without_faction") == []
    assert _influence_rows(_found(state)) == {"emperor": _AT_THE_TOP}


def test_choose_two_greys_the_faction_it_already_named() -> None:
    """Propaganda's "Choose two" names two different Factions: after the
    first pick its second window greys that Faction out as named, and the
    tracks at 6 as at the top; the confirm then pays the named one."""

    state = _combat_reward(
        "propaganda", Influence(emperor=6, spacing_guild=6, bene_gesserit=6)
    )
    assert state.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_DISTINCT_INFLUENCE
    first = _found(state)
    assert {row["action"]["action_id"] for row in first["rows"]} == {
        "choose_distinct_combat_reward_influence"
    }
    assert set(_influence_rows(first)) == {"emperor", "spacing_guild", "bene_gesserit"}
    named = apply_whole(ENGINE, 
        state,
        DomainAction(
            action_id="choose_distinct_combat_reward_influence",
            actor=0,
            arguments=(("faction", "fremen"),),
        ),
    ).state
    assert ENGINE.whole_actions(named, 0) == (_INFLUENCE_CONFIRM,)
    assert _influence_rows(_found(named)) == {
        "emperor": _AT_THE_TOP,
        "spacing_guild": _AT_THE_TOP,
        "bene_gesserit": _AT_THE_TOP,
        "fremen": (
            "Already named for this reward",
            "이 보상에서 이미 고른 진영",
            "named",
        ),
    }


def test_no_influence_row_while_every_faction_can_be_taken() -> None:
    state = _combat_reward("skirmish_crysknife", Influence())
    assert len(_legal(state, "choose_combat_reward_influence")) == 4
    assert unavailable_choices(state, 0, ENGINE.whole_actions(state, 0)) is None


def _faction_rows(
    found: dict[str, Any], key: str, action_id: str
) -> dict[str, tuple[str, str, str]]:
    rows = _rows(found, "choice")
    assert {row["action"]["action_id"] for row in rows.values()} == {action_id}
    for row_key, row in rows.items():
        assert row_key == f"choice:{key}:{row['action']['arguments']['faction']}"
    return {
        row["action"]["arguments"]["faction"]: (
            row["reason"],
            row["reason_ko"],
            row["code"],
        )
        for row in rows.values()
    }


def test_the_research_influence_bonus_greys_the_factions_at_the_top() -> None:
    """c6r6's "Influence with any Faction" never offers a Faction at 6 --
    "합법 행동 provider는 이미 6인 진영을 제시하지 않으므로" (OQ-060) -- and
    shows it greyed out "이미 최고치" as a Conflict reward does. With every
    track at 6 it waits on the turn, offering nothing, like an Agent box's
    Influence, and lapses at the turn end (cleanup-2b)."""

    some = _research_bonus("c5r5", "c6r6", influence=Influence(emperor=6, fremen=2))
    assert [args["faction"] for args in _legal(some, "choose_research_influence")] == [
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    ]
    assert _legal(some, "decline_research_bonus") == []
    found = _found(some)
    assert found["frame"] == FrameKind.TURN
    assert _faction_rows(
        found, "research_influence", "choose_research_influence"
    ) == {"emperor": _AT_THE_TOP}

    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    none = _research_bonus("c5r5", "c6r6", influence=full)
    assert _legal(none, "choose_research_influence") == []
    assert _legal(none, "decline_research_bonus") == []
    rows = _research_rows(_found(none))
    assert [row["key"] for row in rows] == ["waiting:research_influence"]
    assert (rows[0]["reason_ko"], rows[0]["code"]) == (
        "올릴 수 있는 {faction}의 {influence_any}이 모두 이미 최고치(6)"
        " — 차례가 끝날 때까지 못 채우면 사라짐",
        "waiting",
    )


_FACTION_NAMES = ("emperor", "spacing_guild", "bene_gesserit", "fremen")


def _at_shipping(influence: Influence) -> GameState:
    """Seat 0 has sent an Agent to Shipping; its Influence icon waits."""

    owner = PlayerState(
        player_id=0,
        hand=("player:0:starter:dune_the_desert_planet:0",),
        resources=Resources(spice=3),
        influence=influence,
    )
    state = _state(owner)
    place = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments)["space_id"] == "shipping"
    )
    return apply_placement(ENGINE, state, place).state


def test_shipping_greys_the_factions_at_the_top() -> None:
    """Shipping's "Influence with a chosen Faction" [Board Guide p. 2]
    offers only the Factions below 6 (OQ-060); the rest show greyed out."""

    state = _at_shipping(Influence(spacing_guild=6, bene_gesserit=6))
    assert [args["faction"] for args in _legal(state, "choose_shipping_influence")] == [
        "emperor",
        "fremen",
    ]
    assert _faction_rows(
        _found(state), "shipping_influence", "choose_shipping_influence"
    ) == {"spacing_guild": _AT_THE_TOP, "bene_gesserit": _AT_THE_TOP}

    # Below the top everywhere: no row.
    open_tracks = _at_shipping(Influence(spacing_guild=2))
    assert len(_legal(open_tracks, "choose_shipping_influence")) == 4
    assert (
        unavailable_choices(open_tracks, 0, ENGINE.whole_actions(open_tracks, 0))
        is None
    )


_ALL_AT_THE_TOP_WAITING = (
    "Every Faction it can raise is already at the top (6);"
    " it lapses if still unmet when the turn ends",
    "올릴 수 있는 {faction}의 {influence_any}이 모두 이미 최고치(6)"
    " — 차례가 끝날 때까지 못 채우면 사라짐",
    "waiting",
)


def test_shipping_with_every_faction_at_the_top_waits_for_the_turn_end() -> None:
    """User decision 2026-10-17 (composed-effects plan 5, rule decision 1;
    OQ-060, OQ-057 (1)): with every cube at 6 Shipping's Influence offers no
    Faction, holds nothing, and shows one waiting row that the turn's end
    lapses, like an Agent box's Influence there."""

    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _at_shipping(full)
    assert _legal(state, "choose_shipping_influence") == []
    found = _found(state)
    assert _rows(found, "choice") == {}
    rows = _rows(found, "waiting")
    assert list(rows) == ["waiting:shipping_influence"]
    row = rows["waiting:shipping_influence"]
    assert row["action"]["action_id"] == "choose_shipping_influence"
    assert row["action"]["arguments"] == {}
    assert _why(row) == _ALL_AT_THE_TOP_WAITING


# --- Holy War's unit loss ---

_NO_UNIT_TO_LOSE = ("No unit to lose", "잃을 유닛 없음", "no_unit")


def _unit_loss(**fields: Any) -> GameState:
    """Seat 1's Holy War unit-loss window, opened by seat 0's card."""

    from dune_imperium.rules.unit_loss import opponent_unit_loss_frames

    state = _state(PlayerState(player_id=0), config=RulesetConfig(bloodlines=True))
    loser = PlayerState(player_id=1, **fields)
    state = replace(state, players=(state.players[0], loser, *state.players[2:]))
    pushed = opponent_unit_loss_frames(state, 0, source="holy_war").state
    assert pushed.decision_stack[-1].kind == FrameKind.OPPONENT_UNIT_LOSS
    return pushed


def _loss_rows(state: GameState) -> dict[str, tuple[str, str, str]]:
    found = unavailable_choices(state, 1, ENGINE.whole_actions(state, 1))
    if found is None:
        return {}
    assert found["frame"] == FrameKind.OPPONENT_UNIT_LOSS
    rows = _rows(found, "choice")
    for row in rows.values():
        assert row["action"]["action_id"] == "lose_unit"
    return {
        key.removeprefix("choice:lose_unit:"): (
            row["reason"],
            row["reason_ko"],
            row["code"],
        )
        for key, row in rows.items()
    }


def test_a_seat_with_no_unit_confirms_beside_greyed_rows() -> None:
    """User ruling 2026-09-30 (OQ-036 (a)): every opponent is asked, and a
    seat with no unit gets the window with every row greyed out ("잃을 유닛
    없음") and a confirm. Commander rows only for a seat that owns one."""

    state = _unit_loss(troops_supply=12, troops_garrison=0)
    assert [a.action_id for a in ENGINE.whole_actions(state, 1)] == [
        "resolve_unit_loss_without_unit"
    ]
    assert _loss_rows(state) == {
        "garrison:0": _NO_UNIT_TO_LOSE,
        "conflict:0": _NO_UNIT_TO_LOSE,
    }
    owning = _unit_loss(troops_supply=12, troops_garrison=0, commanders_supply=1)
    assert set(_loss_rows(owning)) == {
        "garrison:0",
        "garrison:1",
        "conflict:0",
        "conflict:1",
    }
    assert set(_loss_rows(owning).values()) == {_NO_UNIT_TO_LOSE}


def test_an_empty_zone_is_greyed_beside_the_units_the_seat_can_lose() -> None:
    state = _unit_loss()  # three troops in the garrison
    assert _legal_for(state, 1) == [("lose_unit", {"zone": "garrison"})]
    assert _loss_rows(state) == {
        "conflict:0": (
            "No troop in the Conflict",
            "{conflict}에 {troop} 없음",
            "no_unit",
        ),
    }
    commander = _unit_loss(
        troops_supply=7, troops_conflict=2, commanders_conflict=1, combat_strength=6
    )
    assert _legal_for(commander, 1) == [
        ("lose_unit", {"zone": "garrison"}),
        ("lose_unit", {"zone": "conflict"}),
        ("lose_unit", {"commanders": 1, "zone": "conflict"}),
    ]
    assert _loss_rows(commander) == {
        "garrison:1": (
            "No Sardaukar Commander in your garrison",
            "{garrison}에 {commander} 없음",
            "no_unit",
        ),
    }


def test_no_unit_loss_row_for_another_seat_or_once_answered() -> None:
    state = _unit_loss(troops_supply=12, troops_garrison=0)
    # Seat 2 waits under seat 1's window: nothing is shown to it yet.
    assert unavailable_choices(state, 2, ENGINE.whole_actions(state, 2)) is None
    confirmed = apply_whole(ENGINE, state, ENGINE.whole_actions(state, 1)[0]).state
    decision = confirmed.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision) and decision.owner == 2
    assert _loss_rows(confirmed) == {}


def _legal_for(state: GameState, seat: int) -> list[tuple[str, dict[str, Any]]]:
    return [
        (action.action_id, dict(action.arguments))
        for action in ENGINE.whole_actions(state, seat)
    ]


# --- Whose decision ---


def test_nothing_is_greyed_out_for_a_seat_that_does_not_decide() -> None:
    state = _shop(0)

    assert unavailable_choices(state, 1, ENGINE.whole_actions(state, 1)) is None
    assert unavailable_choices(state, 0, ()) is not None  # the seat's own
    empty = _state(PlayerState(player_id=0))
    assert unavailable_choices(empty, 0, ENGINE.whole_actions(empty, 0)) is None


def test_no_reason_is_the_generic_fallback() -> None:
    state = _intrigue_state(
        "imperium_politics", "councilor_s_ambition", "sietch_ritual", "spice_is_power"
    )
    for found in (_found(state), _found(_shop(0))):
        whys = [*found["rows"], *found["refs"].values()]
        assert whys
        assert all(why["code"] != NOT_NOW_CODE for why in whys)


def test_the_text_fallbacks_carry_the_fallback_code() -> None:
    """The "Cannot pay: ..." and "Nothing to do now: ..." texts are fallbacks
    for a block no specific reason covers yet. They carry ``NOT_NOW_CODE``,
    so the check above and the seeded sweep in
    test_unavailable_consistency.py fail on them. None is reachable from a
    printed card today, so blocks the provider never returns drive them."""

    pay = PayResources(solari=1)
    gain = GainResources(solari=1)
    option = IntrigueOption(
        timing=IntrigueTiming.PLOT,
        sections=(EffectSection(rewards=(gain,), costs=(pay,)),),
    )
    rich = _intrigue_state(resources=Resources(solari=1))

    cost = intrigue_option_reason(rich, 0, option, pay)
    assert cost[0].startswith("Cannot pay: ") and cost[2] == NOT_NOW_CODE
    reward = intrigue_option_reason(rich, 0, option, gain)
    assert reward[0].startswith("Nothing to do now: ") and reward[2] == NOT_NOW_CODE
    # The resource check blocked, yet nothing is short.
    short = intrigue_option_reason(rich, 0, option, OptionBlock.COST)
    assert short[0].startswith("Cannot pay: ") and short[2] == NOT_NOW_CODE
    for english, korean, _ in (cost, reward, short):
        assert korean and english != korean


# --- Arrakeen Scouts: the new High Council seat's subcommittee choice -------------

DAGGER = "player:0:starter:dagger:0"


def _council_seat(spice: int, display: tuple[str, ...]) -> GameState:
    """Seat 0 sent the Dagger to the High Council and took the seat: its
    subcommittee choice is one more effect of the visit (OQ-076)."""

    owner = PlayerState(
        player_id=0,
        hand=(DAGGER,),
        resources=Resources(solari=5, spice=spice, water=1),
    )
    state = _state(
        owner,
        config=RulesetConfig(arrakeen_scouts=True),
        round_number=2,
        scouts_subcommittees=display,
    )
    state = apply_placement(
        ENGINE,
        state,
        DomainAction(
            action_id="agent_turn",
            actor=0,
            arguments=(("card_id", DAGGER), ("space_id", "high_council")),
        ),
    ).state
    state = apply_whole(ENGINE, 
        state,
        DomainAction(
            action_id="resolve_board_effect",
            actor=0,
            arguments=(("effect", "high_council"),),
        ),
    ).state
    assert state.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    return state


def test_a_subcommittee_choice_nothing_can_meet_waits_greyed_out() -> None:
    """``choose_subcommittee`` is offered exactly when a subcommittee can be
    joined now; while none can, the row says why. In an Agent turn the
    offer has no refusal and lapses when the turn ends (OQ-095 (2), user
    ruling 2026-10-14), which the row says; with nothing else of the turn
    left to meet it, it sits among the choices (a Steersman draw still to
    come keeps it waiting: ``tests/unit/rules/test_scouts_subcommittees.py``
    ``test_a_subcommittee_becomes_choosable_once_the_turn_pays_for_it``)."""
    several = _council_seat(0, ("oversight", "relations", "leverage"))
    assert _legal(several, "choose_subcommittee") == []
    assert _legal(several, "decline_subcommittee") == []
    assert _legal(several, "finish_agent_turn") == [{}]
    row = _rows(_found(several), "choice")["choice:choose_subcommittee"]
    assert row["action"]["action_id"] == "choose_subcommittee"
    assert _why(row) == _lapsing(
        (
            "No subcommittee you can join now",
            "지금 가입할 수 있는 소위원회 없음",
            "subcommittee",
        ),
        LAPSES,
    )
    # One subcommittee left: its own reason, by name.
    one = _council_seat(1, ("relations",))
    row = _rows(_found(one), "choice")["choice:choose_subcommittee"]
    assert row["reason"] == "Relations: Needs 2 spice (you have 1)" + LAPSES[0]
    assert row["reason_ko"].startswith("외교: ")
    assert row["reason_ko"].endswith(LAPSES[1])
    assert row["code"] == "cost"


def test_the_subcommittee_row_goes_once_one_can_be_joined() -> None:
    state = _council_seat(2, ("relations",))
    assert _legal(state, "choose_subcommittee") == [{}]
    found = unavailable_choices(state, 0, ENGINE.whole_actions(state, 0))
    rows = found["rows"] if found is not None else []
    assert isinstance(rows, list)
    assert "waiting:choose_subcommittee" not in {row["key"] for row in rows}


def test_every_subcommittee_taken_greys_the_choice_beside_the_turn_end() -> None:
    """With every subcommittee already taken the new seat's offer is still
    armed (user ruling 2026-09-30, OQ-076 (c); unreachable with four
    players); in the Agent turn only the turn's end is offered, which
    lapses it (OQ-095 (2), user ruling 2026-10-14). It can never light up,
    so the row sits among the choices that cannot be taken, not the
    waiting ones, and says it lapses."""
    state = _council_seat(5, ("relations",))
    state = replace(state, scouts_subcommittee_members=(("relations", 1),))
    assert [action.action_id for action in ENGINE.whole_actions(state, 0)] == [
        "finish_agent_turn"
    ]
    found = _found(state)
    assert not _rows(found, "waiting")
    row = _rows(found, "choice")["choice:choose_subcommittee"]
    assert _why(row) == _lapsing(
        (
            "Every subcommittee already has a member",
            "모든 소위원회에 가입한 플레이어가 있음",
            "claimed",
        ),
        LAPSES,
    )


# --- A Skill choice with a Skill the seat already holds (Bloodlines) ---

BLOODLINES = RulesetConfig(bloodlines=True)
_SKILL_HELD = ("You already have this Skill", "이미 가진 {commander_skill}", "held")


def _bank_skill_choice(held: tuple[int, ...], *, fresh: bool) -> GameState:
    """Sardaukar Standard's bank Commander owed to seat 0, whose Skills are
    ``held`` (tile indexes). Tiles 1 and 3 (the second copies of the Skills
    of tiles 0 and 2) are face up, with tile 5, a Skill nobody holds, when
    ``fresh``."""

    from dune_imperium.content.bloodlines.sardaukar import skill_tile_instance_ids
    from dune_imperium.rules.sardaukar import begin_skill_choice

    tiles = skill_tile_instance_ids()
    face_up = (tiles[1], tiles[3], *((tiles[5],) if fresh else ()))
    owner = PlayerState(player_id=0, skill_ids=tuple(tiles[i] for i in held))
    taken = {tiles[i] for i in held} | set(face_up)
    state = _state(
        owner,
        config=BLOODLINES,
        skill_face_up=face_up,
        skill_stack=tuple(tile for tile in tiles if tile not in taken),
        sardaukar_commanders_bank=1,
        pending_skill_choices=((0, "imperium:sardaukar_standard:0", "test"),),
    )
    opened = begin_skill_choice(state).state
    assert opened.decision_stack[-1].kind == FrameKind.SKILL_CHOICE
    return opened


def test_a_bank_commander_with_no_skill_to_choose_greys_every_skill() -> None:
    """User ruling 2026-10-02 (L2-Q3: "①②는 확인 창"): a bank Commander
    gained when no Skill can be chosen opens the Skill choice with only the
    confirm (OQ-031, OQ-035 (b): the Commander comes without a Skill); every
    face-up Skill shows greyed out as already held."""
    state = _bank_skill_choice(held=(0, 2), fresh=False)
    assert ENGINE.whole_actions(state, 0) == (
        DomainAction(action_id="resolve_commander_without_skill", actor=0),
    )
    found = _found(state)
    assert found["frame"] == FrameKind.SKILL_CHOICE
    rows = _rows(found, "choice")
    assert len(rows) == 2
    for row in rows.values():
        assert row["action"]["action_id"] == "choose_skill"
        assert (row["reason"], row["reason_ko"], row["code"]) == _SKILL_HELD


def test_a_held_skill_is_greyed_beside_the_ones_the_seat_can_choose() -> None:
    state = _bank_skill_choice(held=(0,), fresh=True)
    legal = ENGINE.whole_actions(state, 0)
    assert {action.action_id for action in legal} == {"choose_skill"}
    offered = {dict(action.arguments)["skill_id"] for action in legal}
    found = _found(state)
    greyed = {
        row["action"]["arguments"]["skill_id"]
        for row in _rows(found, "choice").values()
    }
    assert len(offered) == 2 and len(greyed) == 1
    assert not offered & greyed


# --- An Acquire Tech with every stack empty (Tech Module) ---


def test_an_acquire_tech_with_every_stack_empty_greys_the_acquisition() -> None:
    """A card's Acquire Tech with no tile left opens with only the refusal
    (user ruling 2026-09-30; OQ-057 (9) "살 수 없으면 거절만"), and the
    acquisition shows greyed out with the reason."""
    from dune_imperium.rules.tech import push_tech_acquisition

    config = RulesetConfig(bloodlines=True, tech_module=True)
    owner = PlayerState(player_id=0, resources=Resources(spice=9))
    state = _state(owner, config=config, tech_stacks=((), (), ()))
    opened = push_tech_acquisition(state, 0, discount=1, source="test").state
    assert ENGINE.whole_actions(opened, 0) == (
        DomainAction(action_id="decline_tech", actor=0),
    )
    found = _found(opened)
    assert found["frame"] == FrameKind.TECH_ACQUISITION
    [row] = found["rows"]
    assert row["key"] == "choice:acquire_tech"
    assert row["action"] == {
        "action_id": "acquire_tech",
        "arguments": {},
        "detail": row["action"]["detail"],
        "detail_ko": row["action"]["detail_ko"],
    }
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "Every Tech stack is empty",
        "{tech_tile} 더미가 모두 비었음",
        "empty",
    )
    # A tile left to take: no row.
    stocked = push_tech_acquisition(
        _state(owner, config=config, tech_stacks=(("training_depot",), (), ())),
        0,
        discount=1,
        source="test",
    ).state
    assert unavailable_choices(stocked, 0, ENGINE.whole_actions(stocked, 0)) is None


# --- Agent-box icons withheld until the turn's end (OQ-057 (1)) ---


def _imperium(card_id: str) -> str:
    return next(i for i in imperium_deck_instance_ids(False) if f":{card_id}:" in i)


def _icon_rows(state: GameState) -> dict[str, tuple[str, str, str]]:
    """The greyed Agent-box icon rows, keyed by surface and icon."""

    found = unavailable_choices(state, 0, ENGINE.whole_actions(state, 0))
    rows = found["rows"] if found is not None else []
    assert isinstance(rows, list)
    return {
        row["key"]: (row["reason"], row["reason_ko"], row["code"])
        for row in rows
        if row["key"].split(":", 1)[1].startswith("agent_icon:")
    }


def test_steersman_recall_with_no_target_is_greyed_until_the_turn_end() -> None:
    """User ruling 2026-10-02 (L2-Q3: "③은 회색 줄만"): Steersman's Recall
    Agent icon with no other Agent opens no window; it shows greyed out
    while the turn is open, and the turn's end press still fizzles it
    (OQ-057 (1))."""
    steersman = _imperium("steersman")
    owner = PlayerState(
        player_id=0, agents_available=2, hand=(steersman,), deck=(DAGGER,)
    )
    state = _place(_state(owner), "deliver_supplies")
    assert not [
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id.startswith(("recall_agent", "recall_conflict_agent"))
    ]
    no_target = (
        "No other Agent of yours to recall (not the one sent this turn);"
        " it lapses when the turn ends",
        "소환할 다른 {agent} 없음 (이번 차례에 보낸 {agent} 제외)"
        " — 차례가 끝날 때 사라짐",
        "no_target",
    )
    assert _icon_rows(state) == {"choice:agent_icon:recall": no_target}
    row = _rows(_found(state), "choice")["choice:agent_icon:recall"]
    assert row["action"]["action_id"] == "recall_agent_for_agent_card"
    assert row["action"]["arguments"] == {}
    assert row["card_id"] == steersman
    # Resolve everything else: the row stays until the press, which fizzles
    # the icon.
    finish = DomainAction(action_id="finish_agent_turn", actor=0)
    while finish not in (legal := ENGINE.whole_actions(state, 0)):
        state = apply_whole(ENGINE, state, legal[0]).state
    assert _icon_rows(state) == {"choice:agent_icon:recall": no_target}
    finished = apply_whole(ENGINE, state, finish)
    assert any(
        event.kind == "agent_card_effect_unavailable"
        and dict(event.payload)["effect"] == "recall"
        for event in finished.events
    )

    # Another Agent on the board: the recall is offered, no row.
    other = replace(owner, agents_available=1, agent_locations=("arrakeen",))
    assert _icon_rows(_place(_state(other), "deliver_supplies")) == {}


def test_a_conditioned_agent_icon_is_greyed_with_its_threshold() -> None:
    """Hidden Missive's troop and card draw at two Bene Gesserit Influence:
    below it the icons are not offered and wait for the turn's end (OQ-057
    (1)); they show greyed out with what is missing, and are offered again
    once the condition holds (``agent_icon_block``). A later effect of the
    turn can still meet it, so they sit under "waiting", beside a single
    Agent box withheld by the same rule (``_agent_box``)."""
    missive = _imperium("hidden_missive")
    below = PlayerState(
        player_id=0, hand=(missive,), influence=Influence(bene_gesserit=1)
    )
    state = _place(_state(below), "gather_support")
    reason = (
        "Needs 2 Bene Gesserit Influence (you have 1);"
        " it lapses if still unmet when the turn ends",
        "{influence_bene_gesserit} 2 필요 (보유 1)"
        " — 차례가 끝날 때까지 못 채우면 사라짐",
        "condition",
    )
    assert _icon_rows(state) == {
        "waiting:agent_icon:troops": reason,
        "waiting:agent_icon:cards": reason,
    }
    row = _rows(_found(state), "waiting")["waiting:agent_icon:troops"]
    assert row["action"]["action_id"] == "resolve_agent_card_effect"
    assert row["action"]["arguments"] == {"effect": "troops"}
    assert row["card_id"] == missive

    met = replace(below, influence=Influence(bene_gesserit=2))
    assert _icon_rows(_place(_state(met), "gather_support")) == {}


def test_a_grafted_box_s_greyed_icons_name_their_own_card_and_box() -> None:
    """Hidden Missive's icons wait for 2 Bene Gesserit Influence (OQ-027)
    while it is grafted to Face Dancer (codec v143: both boxes from the
    start). Each greyed row names its box (``box``, plan 4.11: the page sets
    it under its card's header), and box 0's rows keep reading Hidden
    Missive with its condition after box 1 resolved and became the active
    box: they used to be described with whichever box acted last ("Face
    Dancer: Recruit 1 troop")."""

    missive = "imperium:hidden_missive:0"
    face_dancer = "tleilaxu:face_dancer:0"
    owner = PlayerState(player_id=0, hand=(missive, face_dancer))
    config = RulesetConfig(immortality=True)
    placed = _agent_turn(
        _state(owner, config=config, imperium_deck=imperium_deck_instance_ids(True)),
        missive,
        "assembly_hall",
        graft=True,
    )
    grafted = apply_whole(ENGINE, 
        placed,
        DomainAction(
            action_id="choose_graft_partner",
            actor=0,
            arguments=(("card_id", face_dancer),),
        ),
    ).state
    partner = DomainAction(
        action_id="resolve_agent_card_effect", actor=0, arguments=(("box", 1),)
    )
    assert partner in ENGINE.whole_actions(grafted, 0)
    expected = {
        "waiting:agent_icon:troops": (
            "Hidden Missive",
            "Recruit 1 troop (at 2 Bene Gesserit Influence)",
        ),
        "waiting:agent_icon:cards": (
            "Hidden Missive",
            "Draw 1 card (at 2 Bene Gesserit Influence)",
        ),
    }
    for state in (grafted, apply_whole(ENGINE, grafted, partner).state):
        rows = _rows(_found(state), "waiting")
        assert {
            key: (row["action"]["detail_title"], row["action"]["detail"])
            for key, row in rows.items()
        } == expected
        assert {row["box"] for row in rows.values()} == {0}


def test_a_single_card_s_greyed_box_rows_are_box_zero() -> None:
    """A single card's turn has box 0 only; its greyed rows say so, and a
    row of no box (a Faction space's recall) carries none."""

    missive = "imperium:hidden_missive:0"
    owner = PlayerState(player_id=0, hand=(missive,))
    state = _place(_state(owner), "gather_support")
    rows = _rows(_found(state), "waiting")
    assert set(rows) == {"waiting:agent_icon:troops", "waiting:agent_icon:cards"}
    assert {row["box"] for row in rows.values()} == {0}
    assert all("box" not in row for row in _found(_imperial_privilege())["rows"])


def test_an_ungrafted_card_s_icons_are_greyed_among_the_choices() -> None:
    """Sardaukar Quartermaster's "If grafted: [troop] [card]": played alone
    the icons wait for the turn's end and fizzle there (OQ-057 (1)), but
    nothing later in the turn can graft the card, so the rows sit among the
    choices that cannot be taken ("choice"), not the waiting ones."""
    quartermaster = "imperium:sardaukar_quartermaster:0"
    owner = PlayerState(
        player_id=0, hand=(quartermaster,), research_space=RESEARCH_START_ID
    )
    state = _place(_state(owner, config=RulesetConfig(immortality=True)), "arrakeen")
    reason = (
        "Only when the card is grafted; it lapses when the turn ends",
        "{graft}한 카드일 때만 — 차례가 끝날 때 사라짐",
        "condition",
    )
    assert _icon_rows(state) == {
        "choice:agent_icon:troops": reason,
        "choice:agent_icon:cards": reason,
    }


def test_cargo_runner_s_four_contract_line_waits_with_its_count() -> None:
    """Cargo Runner's two lines are two icons (OQ-027): at three completed
    contracts the first is offered and the second ("If you have completed
    four or more contracts: [draw 1]" [Cargo Runner card]) waits with what
    is missing; a contract completed later in the turn can still meet it,
    so it sits under "waiting" (OQ-057 (1))."""
    cargo = next(
        i for i in imperium_deck_instance_ids(True) if ":cargo_runner:" in i
    )
    owner = PlayerState(
        player_id=0,
        hand=(cargo,),
        deck=(DAGGER,),
        completed_contract_ids=(
            "contract:deliver_supplies",
            "contract:espionage_i",
            "contract:espionage_i_copy_2",
        ),
    )
    state = _place(
        _state(owner, config=RulesetConfig(choam_module=True)), "assembly_hall"
    )
    assert _icon_rows(state) == {
        "waiting:agent_icon:cards_second": (
            "Needs 4 completed contracts (you have 3);"
            " it lapses if still unmet when the turn ends",
            "완수한 {contract} 4개 필요 (완수 3)"
            " — 차례가 끝날 때까지 못 채우면 사라짐",
            "condition",
        ),
    }


def test_tread_in_darkness_draw_greys_out_once_its_bond_card_is_trashed() -> None:
    """Tread in Darkness's [trash] and [draw 1] are two icons (OQ-027), each
    judged on "another Bene Gesserit card in play" when it resolves
    (OQ-028). Trashing that card first leaves the draw waiting for a Bond
    that cannot come back this turn: a "choice" row until the turn's end."""
    tread = _imperium("tread_in_darkness")
    bond = _imperium("truthtrance")
    owner = PlayerState(player_id=0, hand=(tread,), deck=(DAGGER,), in_play=(bond,))
    state = _place(_state(owner), "arrakeen")
    assert _icon_rows(state) == {}
    trash = next(
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "trash_agent_card"
        and dict(action.arguments)["card_id"] == bond
    )
    state = apply_whole(ENGINE, state, trash).state
    assert _icon_rows(state) == {
        "choice:agent_icon:cards": (
            "Needs another Bene Gesserit card in play;"
            " it lapses when the turn ends",
            "{in_play}에 다른 베네 게세리트 카드 필요 — 차례가 끝날 때 사라짐",
            "condition",
        ),
    }


def test_in_high_places_icons_grey_out_once_its_bond_card_is_trashed() -> None:
    """In High Places' [draw 1] and [Spy] are two icons (cleanup-2d-5, user
    decision 2026-10-18), each judged on its Bond when it resolves (OQ-028):
    without the Bond both wait as "choice" rows until the turn's end."""
    in_high_places = _imperium("in_high_places")
    bond = _imperium("truthtrance")
    owner = PlayerState(
        player_id=0, hand=(in_high_places,), deck=(DAGGER,), in_play=(bond,)
    )
    state = _place(_state(owner), "secrets")
    assert _icon_rows(state) == {}
    lost = replace(
        state.players[0],
        in_play=tuple(card for card in state.players[0].in_play if card != bond),
        trashed=(bond,),
    )
    state = replace(state, players=(lost, *state.players[1:]))
    reason = (
        "Needs another Bene Gesserit card in play; it lapses when the turn ends",
        "{in_play}에 다른 베네 게세리트 카드 필요 — 차례가 끝날 때 사라짐",
        "condition",
    )
    assert _icon_rows(state) == {
        "choice:agent_icon:cards": reason,
        "choice:agent_icon:spy": reason,
    }


def test_stillsuit_manufacturer_return_waits_for_the_fremen_alliance() -> None:
    """Stillsuit Manufacturer's "[Fremen] Alliance: Return this card from
    play to your hand." is its own icon (OQ-027): without the Alliance it
    waits, and an Alliance formed later in the turn can still meet it
    ("waiting", OQ-057 (1))."""
    stillsuit = "imperium:stillsuit_manufacturer:0"
    owner = PlayerState(
        player_id=0, hand=(stillsuit,), research_space=RESEARCH_START_ID
    )
    state = _place(_state(owner, config=RulesetConfig(immortality=True)), "arrakeen")
    assert _icon_rows(state) == {
        "waiting:agent_icon:return_self": (
            "Needs the Fremen Alliance;"
            " it lapses if still unmet when the turn ends",
            "프레멘 {alliance} 필요 — 차례가 끝날 때까지 못 채우면 사라짐",
            "condition",
        ),
    }


def test_fill_coffers_spice_waits_for_an_alliance() -> None:
    """Lady Amber Metulli's Signet: "[1 Solari] —AND— If you have an
    Alliance: [1 spice]" [Lady Amber Metulli card]. Without an Alliance the
    spice icon waits; one formed later in the turn can still meet it."""
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=("player:0:starter:signet_ring:0",),
    )
    state = _place(_state(owner), "arrakeen")
    assert _icon_rows(state) == {
        "waiting:agent_icon:spice": (
            "Needs an Alliance; it lapses if still unmet when the turn ends",
            "{alliance} 필요 — 차례가 끝날 때까지 못 채우면 사라짐",
            "condition",
        ),
    }


# --- A Contract the seat cannot take, and Contract icons held (OQ-059) ---

_IMMEDIATE = "contract:bloodlines_immediate"
_CHOAM_BLOODLINES = RulesetConfig(choam_module=True, bloodlines=True)
_NO_INTRIGUE_TO_TRASH = (
    "No Intrigue card to trash",
    "폐기할 {intrigue_card} 없음",
    "cost",
)
_HOLD = DomainAction(action_id="hold_contract_icons", actor=0)


def _contract_market(market: tuple[str, ...], **owner_fields: Any) -> GameState:
    """Seat 0's Contract icon over ``market``: its window is on top."""

    owner = PlayerState(player_id=0, **owner_fields)
    state = _state(owner, config=_CHOAM_BLOODLINES, face_up_contract_ids=market)
    return begin_contract_gain(state, 0, 1, source="test").state


def _take(instance_id: str) -> dict[str, Any]:
    return {"instance_id": instance_id}


def test_the_immediate_greys_out_without_an_intrigue_card_to_trash() -> None:
    """"You can't take the new Immediate contract unless you have an Intrigue
    card to trash." [Bloodlines p. 2]: ``contract_take_block`` withholds it,
    the other token stays an ordinary choice, and the market token dims."""

    state = _contract_market((_IMMEDIATE, "contract:arrakeen_i"))
    assert _legal(state, "take_contract") == [_take("contract:arrakeen_i")]
    found = _found(state)
    assert found["frame"] == FrameKind.CONTRACT_MARKET
    rows = _rows(found, "choice")
    assert list(rows) == [f"choice:take_contract:{_IMMEDIATE}"]
    row = rows[f"choice:take_contract:{_IMMEDIATE}"]
    assert row["action"]["action_id"] == "take_contract"
    assert row["action"]["arguments"] == _take(_IMMEDIATE)
    assert (row["reason"], row["reason_ko"], row["code"]) == _NO_INTRIGUE_TO_TRASH
    assert found["refs"] == {
        _IMMEDIATE: {
            "reason": _NO_INTRIGUE_TO_TRASH[0],
            "reason_ko": _NO_INTRIGUE_TO_TRASH[1],
            "code": _NO_INTRIGUE_TO_TRASH[2],
        }
    }


def test_an_unreachable_market_greys_out_the_immediate_beside_the_hold() -> None:
    """Nothing in a non-empty market can be taken: the window opens with only
    ``hold_contract_icons`` (OQ-059; user ruling 2026-09-30, "결정 창 없이
    자동으로 넘어가는 곳도 모두 결정 창을 연다"), the Immediate greyed out
    beside it. The held-icons row is not added on the market itself."""

    state = _contract_market((_IMMEDIATE,))
    assert ENGINE.whole_actions(state, 0) == (_HOLD,)
    found = _found(state)
    assert [row["key"] for row in found["rows"]] == [
        f"choice:take_contract:{_IMMEDIATE}"
    ]


def test_no_market_row_once_the_seat_holds_an_intrigue_card() -> None:
    state = _contract_market((_IMMEDIATE,), intrigue_cards=("intrigue:0",))
    assert _legal(state, "take_contract") == [_take(_IMMEDIATE)]
    assert unavailable_choices(state, 0, ENGINE.whole_actions(state, 0)) is None


def _held_reason(lapse_en: str, lapse_ko: str) -> tuple[str, str, str]:
    return (
        "1 Contract icon held: taken once you have an Intrigue card to trash,"
        f" lost when {lapse_en}",
        "{contract} 아이콘 1개 보류 — 폐기할 {intrigue_card}가 생기면 가져감,"
        f" {lapse_ko} 사라짐",
        "waiting",
    )


def test_held_contract_icons_wait_greyed_out_for_the_rest_of_the_turn() -> None:
    """The held icons are shown to their seat (``held_contract_icons`` had no
    view before): a "waiting" row naming the token they wait for, in the
    seat's next decision of the turn, until the turn-end press fizzles them."""

    def instance(card_id: str) -> str:
        return next(i for i in imperium_deck_instance_ids(True) if f":{card_id}:" in i)

    mentat = instance("captured_mentat")  # a Spice Trade Agent icon
    owner = PlayerState(
        player_id=0,
        hand=(mentat, instance("truthtrance")),
        resources=Resources(solari=10, spice=10, water=10),
    )
    state = _state(
        owner, config=_CHOAM_BLOODLINES, face_up_contract_ids=(_IMMEDIATE,)
    )
    place = next(
        action
        for action in executable_placements(state, 0)
        if dict(action.arguments) == {"card_id": mentat, "space_id": "accept_contract"}
    )
    placed = apply_placement(ENGINE, state, place).state
    icon = DomainAction(
        action_id="resolve_board_effect", actor=0, arguments=(("effect", "contract"),)
    )
    opened = apply_whole(ENGINE, placed, icon).state
    assert ENGINE.whole_actions(opened, 0) == (_HOLD,)
    held = apply_whole(ENGINE, opened, _HOLD).state
    assert held.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS

    found = _found(held)
    rows = _rows(found, "waiting")
    assert list(rows) == [f"waiting:held_contracts:{_IMMEDIATE}"]
    row = rows[f"waiting:held_contracts:{_IMMEDIATE}"]
    assert row["action"]["action_id"] == "take_contract"
    assert row["action"]["arguments"] == _take(_IMMEDIATE)
    assert (row["reason"], row["reason_ko"], row["code"]) == _held_reason(
        "the turn ends", "차례가 끝나면"
    )


def test_conflict_reward_icons_wait_for_the_seat_s_rewards_to_end() -> None:
    """A Conflict reward's held icon lapses at the end of the seat's Conflict
    rewards (user ruling 2026-10-02, L2-Q2: "보상 끝까지 보류 후 불발"), and
    its row says so in the seat's remaining reward windows."""

    owner = PlayerState(player_id=0, combat_strength=8)
    state = _state(
        owner,
        config=_CHOAM_BLOODLINES,
        phase=GamePhase.COMBAT,
        first_player=0,
        decision_stack=(),
        face_up_contract_ids=(_IMMEDIATE,),
        current_conflict_ids=("choam_security",),
        combat_intrigue_complete=True,
        conflict_first_place_influence_bonus=1,
        intrigue_deck=("intrigue:0", "intrigue:1"),
    )
    # The reward window's rows are answered up to the Contract market its
    # Contract icon opens (stage B2, OQ-112).
    rewards = answer_reward_windows(ENGINE, resolve_combat_rewards(state).state)
    assert ENGINE.whole_actions(rewards, 0) == (_HOLD,)
    held = apply_whole(ENGINE, rewards, _HOLD).state
    assert held.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_ICONS
    held = answer_reward_windows(ENGINE, held)
    assert held.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_INFLUENCE

    row = _rows(_found(held), "waiting")[f"waiting:held_contracts:{_IMMEDIATE}"]
    assert (row["reason"], row["reason_ko"], row["code"]) == _held_reason(
        "your Conflict rewards end", "교전 보상을 다 받으면"
    )


def test_icons_held_in_the_scouts_step_say_when_they_lapse() -> None:
    """Held in the Arrakeen Scouts step (no turn frame on the stack), the
    icons reopen the market once an Intrigue card arrives and fizzle when
    the step ends (user ruling 2026-10-02 on OQ-059, "Scouts 단계 안에서
    보류 후 불발"), and the row says so."""

    outside = _state(
        PlayerState(player_id=0),
        config=_CHOAM_BLOODLINES,
        decision_stack=(),
        face_up_contract_ids=(_IMMEDIATE,),
    )
    state = begin_contract_gain(outside, 0, 1, source="scouts").state
    assert [frame.kind for frame in state.decision_stack] == [
        FrameKind.CONTRACT_MARKET
    ]
    scouts = replace(
        state,
        config=replace(_CHOAM_BLOODLINES, arrakeen_scouts=True),
        scouts_opening=True,
        first_player=0,
    )
    held = apply_whole(ENGINE, scouts, _HOLD).state
    assert held.players[0].held_contract_icons == 1
    later = replace(
        held,
        decision_stack=(
            DecisionFrame(
                kind=FrameKind.SCOUTS_CHOICE,
                frame_id="scouts:later",
                decision=PlayerDecision(owner=0, prompt="later"),
            ),
        ),
    )

    # The later frame is a bare stand-in: no legal list is asked of it.
    found = unavailable_choices(later, 0, ())
    assert isinstance(found, dict)
    row = _rows(found, "waiting")[f"waiting:held_contracts:{_IMMEDIATE}"]
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "1 Contract icon held: taken once you have an Intrigue card to trash,"
        " lost when the Arrakeen Scouts step ends",
        "{contract} 아이콘 1개 보류 — 폐기할 {intrigue_card}가 생기면 가져감,"
        " 아라킨 스카웃 단계가 끝나면 사라짐",
        "waiting",
    )


# --- Optional effects of the Agent turn that offer nothing (OQ-095 (2)) -----
#
# User ruling 2026-10-14: an optional effect ("may", an arrow cost, a black
# trash icon [FAQ p. 3]) offers no refusal in its owner's Agent turn, and
# the turn's end lapses it unused. One that cannot be used now therefore
# offers no row; it shows greyed out with its provider's block, under
# "waiting" while another effect of the turn offers a row (it might still
# enable it), under "choice" once nothing else is left, and says it lapses.

SMUGGLERS_HAVEN = "imperium:smuggler_s_haven:0"
CORRINTH_CITY = "imperium:corrinth_city:0"
BRANCHING_PATH = "imperium:branching_path:0"
PRICE_IS_NO_OBJECT = "imperium:price_is_no_object:0"
SIGNET_RING = "player:0:starter:signet_ring:0"
DIPLOMACY = "player:0:starter:diplomacy:0"
TECH_CONFIG = RulesetConfig(bloodlines=True, tech_module=True)
TECH_STACKS = (
    ("glowglobes", "training_depot", "panopticon"),
    ("gene_locked_vault", "delivery_bay", "servo_receivers"),
    ("advanced_data_analysis", "plasteel_blades", "spy_drones"),
)


def _resolve_the_rest(state: GameState) -> GameState:
    """Resolve the visit's icons and Faction Influence, leaving the turn
    with only its optional effects and its end."""

    while steps := [
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id in ("resolve_board_effect", "resolve_faction_influence")
    ]:
        state = apply_whole(ENGINE, state, steps[0]).state
    return state


def _smugglers_haven(space_id: str, spice: int = 3) -> GameState:
    owner = PlayerState(
        player_id=0, hand=(SMUGGLERS_HAVEN,), resources=Resources(spice=spice)
    )
    return _agent_turn(_state(owner), SMUGGLERS_HAVEN, space_id)


def test_smuggler_s_haven_short_of_spice_waits_then_lapses_unused() -> None:
    """"You may pay 4 spice -> 1 VP" with 3 spice offers nothing (no
    refusal, OQ-095 (2)). While the Maker space's harvest is still to come
    the box waits, in the free order wording, and lights up as soon as the
    harvest pays for it; with nothing else of the turn left it sits among
    the choices and says it lapses unused when the turn ends."""

    short = ("Needs 4 spice (you have 3)", "{spice:4} 필요 (보유 3)", "cost")
    basin = _smugglers_haven("imperial_basin")
    assert _legal(basin, "pay_agent_card_spice") == []
    assert _legal(basin, "decline_agent_card_payment") == []
    row = _optional_box_row(basin)
    assert row["key"] == f"waiting:optional_box:{SMUGGLERS_HAVEN}"
    assert row["action"]["action_id"] == "resolve_agent_card_effect"
    assert row["action"]["detail_title"] == "Smuggler's Haven"
    assert row["card_id"] == SMUGGLERS_HAVEN
    assert row["box"] == 0
    assert _why(row) == _lapsing(short, FREE_ORDER)
    harvested = apply_whole(ENGINE, 
        basin,
        DomainAction(
            action_id="harvest_maker_spice",
            actor=0,
            arguments=(("space_id", "imperial_basin"),),
        ),
    ).state
    assert _legal(harvested, "pay_agent_card_spice") == [{}]
    assert unavailable_choices(harvested, 0, ENGINE.whole_actions(harvested, 0)) is None

    done = _resolve_the_rest(_smugglers_haven("deliver_supplies"))
    assert [action.action_id for action in ENGINE.whole_actions(done, 0)] == [
        "finish_agent_turn"
    ]
    row = _optional_box_row(done)
    assert row["key"] == f"choice:optional_box:{SMUGGLERS_HAVEN}"
    assert _why(row) == _lapsing(short, LAPSES)


def test_corrinth_city_short_of_solari_or_of_cards_greys_out() -> None:
    """"You may discard two cards and pay 5 Solari -> 1 VP": the Solari
    first, then the two cards in hand, as its provider gates it
    (``agent_card_cost_block``). Dutiful Service's own Solari, still to
    come, may pay the 5, so the box waits until they are in; then only the
    two cards are missing, and nothing else of the turn is left."""

    def placed(solari: int, *hand: str) -> GameState:
        owner = PlayerState(
            player_id=0,
            hand=(CORRINTH_CITY, *hand),
            resources=Resources(solari=solari),
        )
        return _agent_turn(_state(owner), CORRINTH_CITY, "dutiful_service")

    state = placed(3)
    assert _why(_optional_box_row(state)) == _lapsing(
        ("Needs 5 solari (you have 3)", "{solari:5} 필요 (보유 3)", "cost"),
        FREE_ORDER,
    )
    done = _resolve_the_rest(state)
    assert done.players[0].resources.solari >= 5
    assert _why(_optional_box_row(done)) == _lapsing(
        (
            "Needs 2 cards in hand (you have 0)",
            "{hand}에 카드 2장 필요 (보유 0)",
            "cost",
        ),
        LAPSES,
    )
    both = _resolve_the_rest(placed(3, DAGGER, "player:0:starter:dagger:1"))
    assert _legal(both, "select_corrinth_city_discard")
    assert unavailable_choices(both, 0, ENGINE.whole_actions(both, 0)) is None


def test_branching_path_without_the_alliance_or_an_intrigue_card() -> None:
    """"[Bene Gesserit] Alliance: you may trash an Intrigue card -> an
    Intrigue card and 2 spice": the Alliance first (a Faction step of the
    turn may still grant it, OQ-028), then an Intrigue card to trash."""

    def placed(**owner_fields: Any) -> GameState:
        owner = PlayerState(player_id=0, hand=(BRANCHING_PATH,), **owner_fields)
        return _agent_turn(_state(owner), BRANCHING_PATH, "arrakeen")

    row = _optional_box_row(placed())
    assert row["surface"] == "waiting"
    assert _why(row) == _lapsing(
        (
            "Needs the Bene Gesserit Alliance",
            "베네 게세리트 {alliance} 필요",
            "condition",
        ),
        FREE_ORDER,
    )
    allied = placed(alliance_faction_ids=("bene_gesserit",))
    assert _why(_optional_box_row(allied)) == _lapsing(
        _NO_INTRIGUE_TO_TRASH, FREE_ORDER
    )


def test_price_is_no_object_with_nothing_affordable_greys_out() -> None:
    """Price is No Object's Solari acquisition with nothing the Solari can
    buy (``agent_card_acquisition_block``)."""

    owner = PlayerState(
        player_id=0, hand=(PRICE_IS_NO_OBJECT,), resources=Resources()
    )
    state = _resolve_the_rest(
        _agent_turn(_state(owner), PRICE_IS_NO_OBJECT, "secrets")
    )
    assert _why(_optional_box_row(state)) == _lapsing(
        (
            "No card you can acquire with your Solari (you have 0)",
            "{solari}로 획득할 수 있는 카드 없음 (보유 0)",
            "cost",
        ),
        LAPSES,
    )


def test_spice_agony_without_spice_greys_out_the_signet_ring() -> None:
    """Lady Jessica's Spice Agony ("1 spice ->", an arrow) offers nothing
    without spice (``signet_optional_block``); the Signet Ring's box shows
    greyed out, led by its card, while the space's icons could still pay."""

    owner = PlayerState(
        player_id=0,
        leader_id="lady_jessica",
        leader_face_id="lady_jessica",
        resources=Resources(water=1),
        troops_supply=9,
        hand=(SIGNET_RING,),
    )
    state = _agent_turn(_state(owner), SIGNET_RING, "arrakeen")
    assert _legal(state, "pay_leader_signet_spice") == []
    assert _legal(state, "decline_leader_signet_payment") == []
    row = _optional_box_row(state)
    assert row["surface"] == "waiting"
    assert row["action"]["detail_title"] == "Signet Ring"
    assert _why(row) == _lapsing(
        ("Needs 1 spice (you have 0)", "{spice:1} 필요 (보유 0)", "cost"), FREE_ORDER
    )


def test_reverend_mother_s_repeat_waits_for_the_space_then_for_water() -> None:
    """Reverend Mother's repeat (water 1 -> repeat, an arrow) waits for the
    visit's own effects, then offers nothing without water
    (``leader_board_repeat_block``); both say it lapses unused."""

    owner = PlayerState(
        player_id=0,
        leader_id="lady_jessica",
        leader_face_id="reverend_mother_jessica",
        resources=Resources(water=0),
        troops_supply=9,
        hand=(DIPLOMACY,),
        deck=(DAGGER,),
    )
    # Fremkit's card draw gives no water: nothing of the turn pays the repeat.
    placed = _agent_turn(_state(owner), DIPLOMACY, "fremkit")
    row = _rows(_found(placed), "waiting")["waiting:leader_board_repeat"]
    assert row["action"]["action_id"] == "pay_leader_board_repeat"
    assert _why(row) == (
        "Only after the space's own effects are resolved; unused, it lapses"
        " when the turn ends",
        "이 공간의 효과를 모두 해결한 뒤에만 — 쓰지 않으면 차례가 끝날 때 사라짐",
        "timing",
    )
    resolved = placed
    while icons := _legal(resolved, "resolve_board_effect"):
        resolved = apply_whole(ENGINE, 
            resolved,
            DomainAction(
                action_id="resolve_board_effect",
                actor=0,
                arguments=tuple(icons[0].items()),
            ),
        ).state
    assert _legal(resolved, "resolve_faction_influence") == [{}]
    water = ("Needs 1 water (you have 0)", "{water:1} 필요 (보유 0)", "cost")
    row = _rows(_found(resolved), "waiting")["waiting:leader_board_repeat"]
    assert _why(row) == _lapsing(water, FREE_ORDER)
    done = _resolve_the_rest(resolved)
    row = _rows(_found(done), "choice")["choice:leader_board_repeat"]
    assert _why(row) == _lapsing(water, LAPSES)


def _commander_visit(solari: int, space_id: str = "dutiful_service") -> GameState:
    skills = skill_tile_instance_ids()
    owner = PlayerState(
        player_id=0,
        hand=starting_deck_instance_ids(0),
        resources=Resources(solari=solari, water=2),
    )
    state = _state(
        owner,
        config=BLOODLINES,
        sardaukar_commander_space_ids=COMMANDER_SETUP_SPACE_IDS,
        sardaukar_commanders_bank=1,
        skill_face_up=tuple(skills[:4]),
        skill_stack=tuple(skills[4:]),
    )
    return _place(state, space_id)


def test_a_sardaukar_commander_short_of_solari_greys_out() -> None:
    """The visit's Commander for 2 Solari [Bloodlines p. 4] is optional and
    offers nothing with 1 Solari (``sardaukar_commander_block``). Dutiful
    Service's own Solari, still to come, pay for it: the row waits, and
    goes once they are in; at Deliver Supplies nothing else pays, and the
    row sits among the choices once the visit is resolved."""

    state = _commander_visit(1)
    assert _legal(state, "acquire_sardaukar_commander") == []
    assert _legal(state, "decline_sardaukar_commander") == []
    short = ("Needs 2 solari (you have 1)", "{solari:2} 필요 (보유 1)", "cost")
    row = _rows(_found(state), "waiting")["waiting:sardaukar_commander"]
    assert row["action"]["action_id"] == "acquire_sardaukar_commander"
    assert row["action"]["arguments"] == {}
    assert _why(row) == _lapsing(short, FREE_ORDER)
    paid = _resolve_the_rest(state)
    assert _legal(paid, "acquire_sardaukar_commander")
    assert unavailable_choices(paid, 0, ENGINE.whole_actions(paid, 0)) is None

    done = _resolve_the_rest(_commander_visit(1, "deliver_supplies"))
    row = _rows(_found(done), "choice")["choice:sardaukar_commander"]
    assert _why(row) == _lapsing(short, LAPSES)


def _landsraad_visit(spice: int, stacks: Any = TECH_STACKS, **owner: Any) -> GameState:
    deck = starting_deck_instance_ids(0)
    seat = PlayerState(
        player_id=0,
        hand=deck[:5],
        deck=deck[5:],
        resources=Resources(solari=4, spice=spice, water=2),
        **owner,
    )
    return _place(
        _state(seat, config=TECH_CONFIG, tech_stacks=stacks), "assembly_hall"
    )


def test_a_landsraad_tech_offer_with_no_tile_in_reach_greys_out() -> None:
    """The Ixian Embassy's "may acquire" on a Landsraad visit [Bloodlines
    p. 7] offers nothing when no tile is affordable
    (``landsraad_tech_block``): the cheapest tile's cost; Advanced Data
    Analysis alone in reach without a Spy to trash; every stack empty."""

    state = _landsraad_visit(0)
    assert _legal(state, "acquire_tech") == []
    assert _legal(state, "decline_tech") == []
    row = _rows(_found(state), "waiting")["waiting:landsraad_tech"]
    assert row["action"]["action_id"] == "acquire_tech"
    assert row["action"]["arguments"] == {}
    assert _why(row) == _lapsing(
        (
            "No Tech tile you can afford: the cheapest costs 2 spice (you have 0)",
            "살 수 있는 {tech_tile} 없음: 가장 싼 타일 {spice:2} (보유 0)",
            "cost",
        ),
        FREE_ORDER,
    )
    spy = _landsraad_visit(3, stacks=(("advanced_data_analysis",), (), ()))
    assert _why(_rows(_found(spy), "waiting")["waiting:landsraad_tech"]) == (
        _lapsing(
            (
                "Advanced Data Analysis needs a Spy of yours on the board to trash",
                "고급 데이터 분석은 보드에 있는 내 {spy}를 폐기해야 함",
                "cost",
            ),
            FREE_ORDER,
        )
    )
    empty = _resolve_the_rest(_landsraad_visit(3, stacks=((), (), ())))
    assert _why(_rows(_found(empty), "choice")["choice:landsraad_tech"]) == (
        _lapsing(
            ("Every Tech stack is empty", "{tech_tile} 더미가 모두 비었음", "empty"),
            LAPSES,
        )
    )
    lit = _landsraad_visit(3)
    assert _legal(lit, "acquire_tech")
    assert unavailable_choices(lit, 0, ENGINE.whole_actions(lit, 0)) is None


def test_the_optional_rows_read_nothing_hidden() -> None:
    """The rows read only public state and the seat's own zones: re-dealing
    every zone the seat cannot see (``agents.determinize``) leaves the
    legal list and the rows as they are, and no other seat is shown any."""

    states = (
        _smugglers_haven("imperial_basin"),
        _resolve_the_rest(_smugglers_haven("deliver_supplies")),
        _imperial_privilege(),
        _commander_visit(1),
        _landsraad_visit(0),
        _council_seat(0, ("oversight", "relations", "leverage")),
    )
    rng = random.Random(11)
    for state in states:
        legal = ENGINE.whole_actions(state, 0)
        found = unavailable_choices(state, 0, legal)
        assert found is not None and found["rows"]
        for _ in range(20):
            hidden = determinize(state, 0, rng)
            hidden_legal = ENGINE.whole_actions(hidden, 0)
            assert hidden_legal == legal
            assert unavailable_choices(hidden, 0, hidden_legal) == found
        for seat in range(1, 4):
            other = determinize(state, seat, rng)
            other_legal = ENGINE.whole_actions(other, seat)
            assert unavailable_choices(other, seat, other_legal) is None


# --- A Conflict reward's payment the seat cannot make (plan 4, row 1) --------
#
# "Each optional cost is its own arrow" [Main p. 9] [FAQ p. 3]: the window
# always offers the refusal; the payment (a resource, or Arrakeen's two
# Spies recalled from the board) is legal exactly when
# ``combat_reward_payment_block`` / ``combat_reward_spy_recall_block`` are
# None, and otherwise shows greyed out on the "choice" surface beside it.

_PAY = DomainAction(action_id="pay_combat_reward", actor=0)
_DECLINE_REWARD = DomainAction(action_id="decline_combat_reward", actor=0)
_RECALL_SPIES = "recall_spies_for_combat_reward"
_EPIC = RulesetConfig(epic_game=True)


def reward_window(
    conflict_id: str,
    *,
    config: RulesetConfig = BASE,
    sandworm: bool = False,
    **owner_fields: Any,
) -> GameState:
    """Seat 0 alone wins ``conflict_id`` and its first payment window is open
    (a "choose a Faction" Influence in front of it is answered)."""

    owner = PlayerState(
        player_id=0,
        combat_strength=8,
        sandworms_conflict=1 if sandworm else 0,
        **owner_fields,
    )
    state = _state(
        owner,
        config=config,
        phase=GamePhase.COMBAT,
        first_player=0,
        reveal_order=(0, 1, 2, 3),
        decision_stack=(),
        current_conflict_ids=(conflict_id,),
        combat_intrigue_complete=True,
        intrigue_deck=("intrigue:0", "intrigue:1"),
    )
    state = answer_reward_windows(ENGINE, resolve_combat_rewards(state).state)
    while state.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_INFLUENCE:
        state = apply_whole(ENGINE, state, ENGINE.whole_actions(state, 0)[0]).state
        state = answer_reward_windows(ENGINE, state)
    return state


def _reward_payment_row(state: GameState, action_id: str) -> dict[str, Any]:
    found = _found(state)
    assert found["refs"] == {}
    row = _rows(found, "choice")[f"choice:{action_id}"]
    assert [r["key"] for r in found["rows"]] == [f"choice:{action_id}"]
    assert row["action"]["action_id"] == action_id
    assert row["action"]["arguments"] == {}
    return row


def test_a_spice_payment_short_of_spice_greys_out_beside_the_refusal() -> None:
    """Spice Freighters: "pay 3 spice for 1 VP" with 1 spice, the case that
    showed only the refusal (79% of these windows)."""

    state = reward_window("spice_freighters", resources=Resources(spice=1))
    assert state.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_OPTIONAL
    assert ENGINE.whole_actions(state, 0) == (_DECLINE_REWARD,)
    row = _reward_payment_row(state, "pay_combat_reward")
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "Needs 3 spice (you have 1)",
        "{spice:3} 필요 (보유 1)",
        "cost",
    )
    assert "card_id" not in row and row["refs"] == []


def test_a_solari_payment_short_of_solari_names_the_solari() -> None:
    state = reward_window("battle_for_spice_refinery", resources=Resources(solari=5))
    assert ENGINE.whole_actions(state, 0) == (_DECLINE_REWARD,)
    row = _reward_payment_row(state, "pay_combat_reward")
    assert (row["reason"], row["reason_ko"], row["code"]) == (
        "Needs 6 solari (you have 5)",
        "{solari:6} 필요 (보유 5)",
        "cost",
    )
    state = reward_window("battle_for_imperial_basin", resources=Resources(spice=2))
    row = _reward_payment_row(state, "pay_combat_reward")
    assert (row["reason"], row["reason_ko"]) == (
        "Needs 4 spice (you have 2)",
        "{spice:4} 필요 (보유 2)",
    )


def test_a_payment_the_seat_can_make_is_legal_and_greys_nothing() -> None:
    for conflict_id, resources in (
        ("spice_freighters", Resources(spice=3)),
        ("battle_for_imperial_basin", Resources(spice=9)),
        ("battle_for_spice_refinery", Resources(solari=6)),
    ):
        state = reward_window(conflict_id, resources=resources)
        assert ENGINE.whole_actions(state, 0) == (_DECLINE_REWARD, _PAY)
        assert unavailable_choices(state, 0, ENGINE.whole_actions(state, 0)) is None


def test_each_arrow_of_a_reward_is_judged_in_its_own_window() -> None:
    """Economic Supremacy prints 6 Solari then 4 spice, each its own arrow:
    paying the first leaves the second window to be judged on what is left,
    and a sandworm offers an arrow a second time [Main p. 14]."""

    ready = reward_window(
        "economic_supremacy", config=_EPIC, resources=Resources(solari=6, spice=3)
    )
    assert dict(ready.decision_stack[-1].context)["resource"] == "solari"
    assert ENGINE.whole_actions(ready, 0) == (_DECLINE_REWARD, _PAY)
    assert unavailable_choices(ready, 0, ENGINE.whole_actions(ready, 0)) is None
    paid = answer_reward_windows(ENGINE, apply_whole(ENGINE, ready, _PAY).state)
    assert dict(paid.decision_stack[-1].context)["resource"] == "spice"
    assert ENGINE.whole_actions(paid, 0) == (_DECLINE_REWARD,)
    row = _reward_payment_row(paid, "pay_combat_reward")
    assert (row["reason"], row["reason_ko"]) == (
        "Needs 4 spice (you have 3)",
        "{spice:4} 필요 (보유 3)",
    )
    declined = answer_reward_windows(
        ENGINE, apply_whole(ENGINE, ready, _DECLINE_REWARD).state
    )
    assert (
        _reward_payment_row(declined, "pay_combat_reward")["reason_ko"]
        == "{spice:4} 필요 (보유 3)"
    )

    twice = reward_window(
        "spice_freighters", sandworm=True, resources=Resources(spice=3)
    )
    assert ENGINE.whole_actions(twice, 0) == (_DECLINE_REWARD, _PAY)
    again = answer_reward_windows(ENGINE, apply_whole(ENGINE, twice, _PAY).state)
    while again.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_INFLUENCE:
        again = apply_whole(ENGINE, again, ENGINE.whole_actions(again, 0)[0]).state
        again = answer_reward_windows(ENGINE, again)
    assert again.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_OPTIONAL
    assert ENGINE.whole_actions(again, 0) == (_DECLINE_REWARD,)
    assert _reward_payment_row(again, "pay_combat_reward")["reason_ko"] == (
        "{spice:3} 필요 (보유 0)"
    )


def _post_ids(count: int) -> tuple[str, ...]:
    return tuple(post.post_id for post in OBSERVATION_POSTS[:count])


def test_arrakeen_s_spy_recall_short_of_spies_greys_out_the_recall() -> None:
    """"Recall 2 Spies" needs two of the seat's Spies on the board: with one
    (or none) only the refusal is legal and the recall greys out, "게임판에
    스파이 2 필요"."""

    for count, held_en, held_ko in ((1, "1", "1"), (0, "0", "0")):
        state = reward_window(
            "battle_for_arrakeen",
            spies_supply=3 - count,
            spy_post_ids=_post_ids(count),
        )
        assert state.decision_stack[-1].kind == FrameKind.COMBAT_REWARD_SPY_RECALL
        assert ENGINE.whole_actions(state, 0) == (_DECLINE_REWARD,)
        row = _reward_payment_row(state, _RECALL_SPIES)
        assert (row["reason"], row["reason_ko"], row["code"]) == (
            f"Needs 2 Spies of yours on the board (you have {held_en})",
            f"보드에 내 {{spy:2}} 필요 (보유 {held_ko})",
            "cost",
        )


def test_a_spy_recall_with_two_spies_on_the_board_is_legal_and_greys_nothing() -> None:
    state = reward_window(
        "battle_for_arrakeen", spies_supply=0, spy_post_ids=_post_ids(3)
    )
    legal = ENGINE.whole_actions(state, 0)
    assert legal[0] == _DECLINE_REWARD and len(legal) == 4
    assert {action.action_id for action in legal[1:]} == {_RECALL_SPIES}
    assert unavailable_choices(state, 0, legal) is None


def test_no_payment_row_for_a_seat_that_does_not_decide_it() -> None:
    for state in (
        reward_window("spice_freighters", resources=Resources(spice=1)),
        reward_window(
            "battle_for_arrakeen", spies_supply=2, spy_post_ids=_post_ids(1)
        ),
    ):
        for seat in range(1, 4):
            legal = ENGINE.whole_actions(state, seat)
            assert unavailable_choices(state, seat, legal) is None


def test_the_payment_rows_read_nothing_hidden() -> None:
    """Resources and Spies on the board are public: re-dealing every zone
    the seat cannot see leaves the legal list and the rows as they are."""

    states = (
        reward_window("spice_freighters", resources=Resources(spice=1)),
        reward_window("battle_for_spice_refinery", resources=Resources(solari=2)),
        reward_window(
            "battle_for_arrakeen", spies_supply=2, spy_post_ids=_post_ids(1)
        ),
    )
    rng = random.Random(5)
    for state in states:
        legal = ENGINE.whole_actions(state, 0)
        found = cast(dict[str, Any] | None, unavailable_choices(state, 0, legal))
        assert found is not None and len(found["rows"]) == 1
        for _ in range(20):
            hidden = determinize(state, 0, rng)
            hidden_legal = ENGINE.whole_actions(hidden, 0)
            assert hidden_legal == legal
            assert unavailable_choices(hidden, 0, hidden_legal) == found
        for seat in range(1, 4):
            other = determinize(state, seat, rng)
            other_legal = ENGINE.whole_actions(other, seat)
            assert unavailable_choices(other, seat, other_legal) is None


# --- A Maker space's sandworm and Desert Riding branches (plan 4, row 8) ----
#
# Deep Desert and Hagga Basin print "spice, or with Maker Hooks summon
# sandworms" [Board Guide pp. 1-2]; ``legal_maker_space_actions`` offers
# ``summon_maker_sandworms`` exactly when ``maker_sandworm_block`` is None
# and Desert Riding's ``take_desert_riding_hooks`` (Hagga Basin, token on the
# board) exactly when ``desert_riding_block`` is None. Each shows greyed out
# on the "choice" surface beside the spice, worded as Desert Power's
# sandworm is.

DESERT_PLANET = "player:0:starter:dune_the_desert_planet:0"
_DESERT_RIDING_TOKEN = ("desert_riding", "hagga_basin", "maker_hooks", 1, -1)
# The token is Arrakeen Scouts' mission piece (state.scouts_goods).
_SCOUTS = RulesetConfig(arrakeen_scouts=True)
_NO_HOOKS = ("No Maker Hooks", "{maker_hooks} 없음", "maker_hooks")
_WALL = (
    "The Shield Wall protects this Conflict",
    "{shield_wall}이 이번 교전을 보호함",
    "shield_wall",
)


def _maker_visit(
    space_id: str,
    *,
    owner_fields: dict[str, Any] | None = None,
    barred: bool = False,
    token: bool = False,
    **fields: Any,
) -> GameState:
    """Seat 0 sends its Agent to a Maker space (one water for Hagga Basin,
    three for Deep Desert); the harvest is still to choose. ``token``: the
    Desert Riding token waits beside Hagga Basin."""

    owner_values: dict[str, Any] = {
        "hand": (DESERT_PLANET,),
        "resources": Resources(water=3),
        "maker_hooks": True,
    }
    owner_values.update(owner_fields or {})
    owner = PlayerState(player_id=0, **owner_values)
    values: dict[str, Any] = {
        "current_conflict_ids": ("propaganda",),
        "maker_bonus_spice": (
            ("deep_desert", 2),
            ("hagga_basin", 1),
            ("imperial_basin", 0),
        ),
    }
    if token:
        values.update(config=_SCOUTS, scouts_goods=(_DESERT_RIDING_TOKEN,))
    values.update(fields)
    state = _agent_turn(_state(owner, **values), DESERT_PLANET, space_id)
    if barred:
        frame = state.decision_stack[-1]
        context = {**dict(frame.context), "units_deploy_blocked": True}
        frame = replace(frame, context=tuple(sorted(context.items())))
        state = replace(state, decision_stack=(*state.decision_stack[:-1], frame))
    return state


def _maker_rows(state: GameState) -> dict[str, dict[str, Any]]:
    raw = unavailable_choices(state, 0, ENGINE.whole_actions(state, 0))
    if raw is None:
        return {}
    found = cast(dict[str, Any], raw)
    assert found["frame"] == FrameKind.AGENT_EFFECTS
    assert found["refs"] == {}
    rows = {row["key"].split(":", 1)[1]: row for row in found["rows"]}
    assert all(row["surface"] == "choice" for row in rows.values())
    return rows


def _sandworm_row(state: GameState, space_id: str) -> dict[str, Any]:
    rows = _maker_rows(state)
    assert list(rows) == ["summon_maker_sandworms"]
    row = rows["summon_maker_sandworms"]
    assert row["action"]["action_id"] == "summon_maker_sandworms"
    assert row["action"]["arguments"] == {"space_id": space_id}
    return row


_MAKER_IDS = frozenset(
    {"harvest_maker_spice", "summon_maker_sandworms", "take_desert_riding_hooks"}
)


def _legal_ids(state: GameState) -> list[str]:
    """The Maker choice's legal actions (the turn's other rows left out)."""

    return [
        action.action_id
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id in _MAKER_IDS
    ]


def test_a_maker_space_without_maker_hooks_greys_out_the_sandworm() -> None:
    for space_id in ("hagga_basin", "deep_desert"):
        state = _maker_visit(space_id, owner_fields={"maker_hooks": False})
        assert _legal_ids(state) == ["harvest_maker_spice"]
        assert _why(_sandworm_row(state, space_id)) == _NO_HOOKS


def test_each_maker_sandworm_block_has_its_own_reason() -> None:
    """A Conflict, Emperor of the Known Universe's deployment ban and the
    Shield Wall, in the block's order (Maker Hooks first)."""

    cases = [
        (
            "hagga_basin",
            _maker_visit("hagga_basin", current_conflict_ids=()),
            ("No Conflict this round", "이번 라운드에 교전 없음", "no_conflict"),
        ),
        (
            "deep_desert",
            _maker_visit("deep_desert", barred=True),
            (
                "Emperor of the Known Universe bars deploying units this turn",
                "알려진 우주의 황제: 이번 차례에는 유닛을 배치할 수 없음",
                "reward",
            ),
        ),
        (
            "hagga_basin",
            _maker_visit(
                "hagga_basin",
                current_conflict_ids=("siege_of_arrakeen",),
                shield_wall_present=True,
            ),
            _WALL,
        ),
    ]
    for space_id, state, reason in cases:
        assert "summon_maker_sandworms" not in _legal_ids(state)
        assert _why(_sandworm_row(state, space_id)) == reason
    # Several blocks at once name the first: no Maker Hooks before no Conflict.
    both = _maker_visit(
        "hagga_basin", owner_fields={"maker_hooks": False}, current_conflict_ids=()
    )
    assert _why(_sandworm_row(both, "hagga_basin")) == _NO_HOOKS


def test_the_shield_wall_does_not_withhold_arrakis_planetologist() -> None:
    """Liet Kynes replaces the sandworms "even when the Conflict is protected
    by the Shield Wall" [Liet Kynes card]: the summon stays legal, no row."""

    state = _maker_visit(
        "hagga_basin",
        owner_fields={"leader_id": "liet_kynes"},
        current_conflict_ids=("siege_of_arrakeen",),
        shield_wall_present=True,
    )
    assert "summon_maker_sandworms" in _legal_ids(state)
    assert _maker_rows(state) == {}


def test_a_sandworm_the_seat_can_summon_is_legal_and_greys_nothing() -> None:
    for space_id in ("hagga_basin", "deep_desert"):
        state = _maker_visit(space_id)
        assert _legal_ids(state) == ["harvest_maker_spice", "summon_maker_sandworms"]
        assert _maker_rows(state) == {}


def test_imperial_basin_prints_no_sandworm_and_gets_no_row() -> None:
    state = _maker_visit("imperial_basin", owner_fields={"maker_hooks": False})
    assert _legal_ids(state) == ["harvest_maker_spice"]
    assert _maker_rows(state) == {}


def test_a_seat_holding_maker_hooks_cannot_take_the_desert_riding_token() -> None:
    """OQ-079 (b): the token is one of the four Maker Hooks, and a seat that
    holds Maker Hooks gets no second one; it keeps its spice or its sandworm."""

    state = _maker_visit("hagga_basin", token=True)
    assert _legal_ids(state) == ["harvest_maker_spice", "summon_maker_sandworms"]
    rows = _maker_rows(state)
    assert list(rows) == ["take_desert_riding_hooks"]
    row = rows["take_desert_riding_hooks"]
    assert row["action"]["arguments"] == {"space_id": "hagga_basin"}
    assert _why(row) == (
        "You already hold Maker Hooks",
        "이미 가진 {maker_hooks}",
        "held",
    )
    # Both branches blocked at once: the sandworm and the token each show.
    both = _maker_visit(
        "hagga_basin", token=True, current_conflict_ids=()
    )
    assert list(_maker_rows(both)) == [
        "summon_maker_sandworms",
        "take_desert_riding_hooks",
    ]


def test_the_desert_riding_token_is_offered_without_maker_hooks() -> None:
    state = _maker_visit(
        "hagga_basin",
        owner_fields={"maker_hooks": False},
        token=True,
    )
    assert _legal_ids(state) == ["harvest_maker_spice", "take_desert_riding_hooks"]
    # Only the sandworm (no Maker Hooks) is greyed out; the token is legal.
    assert list(_maker_rows(state)) == ["summon_maker_sandworms"]


def test_no_desert_riding_row_without_the_token_or_off_hagga_basin() -> None:
    """The token waits beside Hagga Basin alone, and only while it is on the
    board: otherwise the option does not exist, so nothing greys out."""

    assert _maker_rows(_maker_visit("hagga_basin")) == {}
    elsewhere = _maker_visit("deep_desert", token=True)
    assert _maker_rows(elsewhere) == {}


def test_the_maker_rows_read_nothing_hidden() -> None:
    states = (
        _maker_visit("hagga_basin", owner_fields={"maker_hooks": False}),
        _maker_visit("deep_desert", current_conflict_ids=()),
        _maker_visit("hagga_basin", token=True),
    )
    rng = random.Random(8)
    for state in states:
        legal = ENGINE.whole_actions(state, 0)
        found = unavailable_choices(state, 0, legal)
        assert found is not None and found["rows"]
        for _ in range(20):
            hidden = determinize(state, 0, rng)
            hidden_legal = ENGINE.whole_actions(hidden, 0)
            assert hidden_legal == legal
            assert unavailable_choices(hidden, 0, hidden_legal) == found
        for seat in range(1, 4):
            other = determinize(state, seat, rng)
            other_legal = ENGINE.whole_actions(other, seat)
            assert unavailable_choices(other, seat, other_legal) is None


# --- Sietch Tabr's detonation once the Shield Wall is gone (plan 4, row 13) --
#
# Sietch Tabr prints a choose-one row; the "water and destroy the Shield
# Wall" branch destroys a token that a detonation may already have removed
# for good. ``legal_sietch_tabr_actions`` offers it exactly when
# ``sietch_tabr_wall_block`` is None, and it shows greyed out otherwise.

_WALL_GONE = (
    "The Shield Wall is already destroyed",
    "{shield_wall}이 이미 파괴됨",
    "condition",
)
_DETONATE = "take_sietch_tabr_water_and_destroy_wall"


RECONNAISSANCE = "player:0:starter:reconnaissance:0"  # a City icon


def _sietch_tabr_visit(**fields: Any) -> GameState:
    owner = PlayerState(
        player_id=0,
        hand=(RECONNAISSANCE,),
        influence=Influence(fremen=2),
    )
    return _agent_turn(_state(owner, **fields), RECONNAISSANCE, "sietch_tabr")


def _sietch_ids(state: GameState) -> list[str]:
    return [
        action.action_id
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id.startswith("take_sietch_tabr")
    ]


def test_sietch_tabr_greys_out_the_detonation_once_the_wall_is_destroyed() -> None:
    gone = _sietch_tabr_visit(shield_wall_present=False)
    assert _sietch_ids(gone) == ["take_sietch_tabr_supplies", "take_sietch_tabr_water"]
    found = _found(gone)
    assert found["frame"] == FrameKind.AGENT_EFFECTS and found["refs"] == {}
    row = _rows(found, "choice")[f"choice:{_DETONATE}"]
    assert [r["key"] for r in found["rows"]] == [f"choice:{_DETONATE}"]
    assert row["action"]["action_id"] == _DETONATE
    assert row["action"]["arguments"] == {}
    assert _why(row) == _WALL_GONE


def test_sietch_tabr_with_the_wall_in_place_offers_the_detonation() -> None:
    present = _sietch_tabr_visit(shield_wall_present=True)
    assert _sietch_ids(present) == [
        "take_sietch_tabr_supplies",
        "take_sietch_tabr_water",
        _DETONATE,
    ]
    assert unavailable_choices(present, 0, ENGINE.whole_actions(present, 0)) is None


def test_the_detonation_row_goes_once_the_choice_is_taken() -> None:
    gone = _sietch_tabr_visit(shield_wall_present=False)
    taken = apply_whole(ENGINE, 
        gone, DomainAction(action_id="take_sietch_tabr_water", actor=0)
    ).state
    assert _sietch_ids(taken) == []
    found = unavailable_choices(taken, 0, ENGINE.whole_actions(taken, 0))
    assert found is None or all(
        _DETONATE not in row["key"] for row in cast(dict[str, Any], found)["rows"]
    )


def test_the_detonation_row_reads_nothing_hidden() -> None:
    state = _sietch_tabr_visit(shield_wall_present=False)
    legal = ENGINE.whole_actions(state, 0)
    found = cast(dict[str, Any] | None, unavailable_choices(state, 0, legal))
    assert found is not None and len(found["rows"]) == 1
    rng = random.Random(13)
    for _ in range(20):
        hidden = determinize(state, 0, rng)
        hidden_legal = ENGINE.whole_actions(hidden, 0)
        assert hidden_legal == legal
        assert unavailable_choices(hidden, 0, hidden_legal) == found
    for seat in range(1, 4):
        other = determinize(state, seat, rng)
        other_legal = ENGINE.whole_actions(other, seat)
        assert unavailable_choices(other, seat, other_legal) is None


# --- A Leader's Reveal ability with nothing to act on (plan 4, row 17) -------
#
# Lady Amber's Desert Scouts ("Reveal Turn: You may retreat one of your
# troops") needs a unit in the Conflict, Feyd-Rautha's Devious Strength
# ("Reveal Turn: recall one of your Spies for two swords") a Spy on the
# board. ``legal_leader_reveal_actions`` offers them exactly when
# ``leader_reveal_block`` is None; otherwise their actions sit under
# "waiting" with the block and the Reveal tail of a card's optional choice.

_AMBER = "lady_amber_metulli"
_FEYD = "feyd_rautha_harkonnen"
_REVEAL_TAIL = (
    "; it lapses unused when the Reveal turn ends",
    " — {reveal_turn}를 끝내면 쓰지 않은 채 사라짐",
)
_NO_UNIT_TO_RETREAT = (
    "No unit of yours in the Conflict to retreat",
    "{conflict}에 후퇴할 내 유닛 없음",
    "no_unit",
)
_NO_SPY = (
    "Needs 1 Spy of yours on the board (you have 0)",
    "보드에 내 {spy:1} 필요 (보유 0)",
    "cost",
)


_BLOODLINES = RulesetConfig(bloodlines=True)


def _leader_reveal(
    leader_id: str, *, config: RulesetConfig = BASE, **owner_fields: Any
) -> GameState:
    """Seat 0 of ``leader_id`` opens its Reveal turn."""

    owner = PlayerState(
        player_id=0, leader_id=leader_id, hand=(DAGGER,), **owner_fields
    )
    revealed = apply_whole(ENGINE, 
        _state(owner, config=config), DomainAction(action_id="reveal_turn", actor=0)
    ).state
    assert revealed.decision_stack[-1].kind == FrameKind.REVEAL
    return revealed


def _ability_ids(state: GameState) -> list[str]:
    return [
        action.action_id
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id
        in ("retreat_leader_troop", "retreat_leader_commander", "recall_spy_for_leader")
    ]


def _ability_rows(state: GameState) -> dict[str, dict[str, Any]]:
    raw = unavailable_choices(state, 0, ENGINE.whole_actions(state, 0))
    if raw is None:
        return {}
    found = cast(dict[str, Any], raw)
    assert found["frame"] == FrameKind.REVEAL and found["refs"] == {}
    rows = {row["key"]: row for row in found["rows"]}
    assert all(row["surface"] == "waiting" for row in rows.values())
    # The ability names no card and sits under no revealed card's header.
    assert not any("reveal_choice" in row or "card_id" in row for row in rows.values())
    return rows


def _reveal_lapsing(reason: tuple[str, str, str]) -> tuple[str, str, str]:
    return reason[0] + _REVEAL_TAIL[0], reason[1] + _REVEAL_TAIL[1], reason[2]


def test_lady_amber_with_no_unit_in_the_conflict_waits_greyed_out() -> None:
    state = _leader_reveal(_AMBER, troops_garrison=3, troops_conflict=0)
    assert _ability_ids(state) == []
    rows = _ability_rows(state)
    assert list(rows) == ["waiting:leader_reveal:retreat_leader_troop"]
    row = rows["waiting:leader_reveal:retreat_leader_troop"]
    assert row["action"]["action_id"] == "retreat_leader_troop"
    assert row["action"]["arguments"] == {}
    assert _why(row) == _reveal_lapsing(_NO_UNIT_TO_RETREAT)


def test_lady_amber_with_a_unit_in_the_conflict_is_offered_the_retreat() -> None:
    state = _leader_reveal(_AMBER, troops_garrison=2, troops_conflict=1)
    assert _ability_ids(state) == ["retreat_leader_troop"]
    assert _ability_rows(state) == {}
    # A Sardaukar Commander counts as a troop for the retreat [Bloodlines p. 4].
    commander = _leader_reveal(_AMBER, config=_BLOODLINES, commanders_conflict=1)
    assert _ability_ids(commander) == ["retreat_leader_commander"]
    assert _ability_rows(commander) == {}


def test_a_commander_owner_sees_the_commander_retreat_greyed_out_too() -> None:
    """Only a seat that owns a Sardaukar Commander is shown its retreat."""

    state = _leader_reveal(
        _AMBER, config=_BLOODLINES, commanders_garrison=1, troops_garrison=3
    )
    assert _ability_ids(state) == []
    rows = _ability_rows(state)
    assert list(rows) == [
        "waiting:leader_reveal:retreat_leader_troop",
        "waiting:leader_reveal:retreat_leader_commander",
    ]
    for row in rows.values():
        assert _why(row) == _reveal_lapsing(_NO_UNIT_TO_RETREAT)


def test_feyd_rautha_without_a_spy_on_the_board_waits_greyed_out() -> None:
    state = _leader_reveal(_FEYD)
    assert _ability_ids(state) == []
    rows = _ability_rows(state)
    assert list(rows) == ["waiting:leader_reveal:recall_spy_for_leader"]
    row = rows["waiting:leader_reveal:recall_spy_for_leader"]
    assert row["action"]["action_id"] == "recall_spy_for_leader"
    assert row["action"]["arguments"] == {}
    assert _why(row) == _reveal_lapsing(_NO_SPY)
    # With a Spy on the board the ability is legal, one recall per post.
    posts = tuple(post.post_id for post in OBSERVATION_POSTS[:2])
    spied = _leader_reveal(_FEYD, spies_supply=1, spy_post_ids=posts)
    assert _ability_ids(spied) == ["recall_spy_for_leader"] * 2
    assert _ability_rows(spied) == {}


def test_the_ability_row_goes_once_it_is_used_and_for_other_leaders() -> None:
    """The ability is used at most once per Reveal turn: once used there is
    nothing left to grey out. A Leader without a Reveal-turn ability, or a
    seat that is not revealing, shows no row."""

    posts = tuple(post.post_id for post in OBSERVATION_POSTS[:1])
    spied = _leader_reveal(_FEYD, spies_supply=2, spy_post_ids=posts)
    used = apply_whole(ENGINE, 
        spied,
        DomainAction(
            action_id="recall_spy_for_leader",
            actor=0,
            arguments=(("post_id", posts[0]),),
        ),
    ).state
    assert _ability_ids(used) == []
    assert _ability_rows(used) == {}
    assert _ability_rows(_leader_reveal("paul_atreides")) == {}
    turn = _state(PlayerState(player_id=0, leader_id=_AMBER))
    assert _ability_rows(turn) == {}


def test_the_leader_reveal_rows_read_nothing_hidden() -> None:
    states = (
        _leader_reveal(_AMBER, troops_garrison=3),
        _leader_reveal(_FEYD),
        _leader_reveal(
            _AMBER, config=_BLOODLINES, commanders_garrison=1, troops_garrison=3
        ),
    )
    rng = random.Random(17)
    for state in states:
        legal = ENGINE.whole_actions(state, 0)
        found = unavailable_choices(state, 0, legal)
        assert found is not None and found["rows"]
        for _ in range(20):
            hidden = determinize(state, 0, rng)
            hidden_legal = ENGINE.whole_actions(hidden, 0)
            assert hidden_legal == legal
            assert unavailable_choices(hidden, 0, hidden_legal) == found
        for seat in range(1, 4):
            other = determinize(state, seat, rng)
            other_legal = ENGINE.whole_actions(other, seat)
            assert unavailable_choices(other, seat, other_legal) is None


# --- A Tech tile's acquire "Influence with any Faction" ---
# User decision 2026-10-17 (composed-effects plan 5, rule decision 1; OQ-060):
# like Shipping's, Glowglobes' and Navigation Chamber's Influence offers no
# Faction at the top, and with every cube at 6 it waits for the turn's end
# (OQ-057 (1)) or, in Combat, for its owner's confirm.


def _bought_glowglobes(influence: Influence) -> GameState:
    """A Landsraad visit that bought Glowglobes: its Influence is owed."""

    state = _resolve_the_rest(_landsraad_visit(3, influence=influence))
    buy = next(
        action
        for action in ENGINE.whole_actions(state, 0)
        if action.action_id == "acquire_tech"
        and dict(action.arguments).get("tech_id") == "glowglobes"
    )
    bought = apply_whole(ENGINE, state, buy).state
    assert bought.decision_stack[-1].kind == FrameKind.AGENT_EFFECTS
    return bought


def test_a_tech_acquire_influence_greys_the_factions_at_the_top() -> None:
    """The Factions below 6 stay on offer (OQ-060); Emperor and Fremen at
    the top show greyed out "이미 최고치" on the "choice" surface, as
    Shipping's do."""

    state = _bought_glowglobes(Influence(emperor=6, fremen=6))
    assert [
        args["faction"] for args in _legal(state, "resolve_tech_acquire_effect")
    ] == ["spacing_guild", "bene_gesserit"]
    found = _found(state)
    assert found["frame"] == FrameKind.AGENT_EFFECTS
    assert _rows(found, "waiting") == {}
    assert _faction_rows(
        found, "tech_acquire_influence:glowglobes", "resolve_tech_acquire_effect"
    ) == {"emperor": _AT_THE_TOP, "fremen": _AT_THE_TOP}

    # Below the top everywhere: no row.
    open_tracks = _bought_glowglobes(Influence(emperor=2))
    assert len(_legal(open_tracks, "resolve_tech_acquire_effect")) == 4
    assert (
        unavailable_choices(open_tracks, 0, ENGINE.whole_actions(open_tracks, 0))
        is None
    )


def test_a_tech_acquire_influence_with_every_faction_at_the_top_waits() -> None:
    """With every cube at 6 nothing is offered and the turn's end is not
    held: one waiting row says so (OQ-060, OQ-057 (1)), in the Agent turn
    and, with the Reveal's own tail, in the Reveal turn."""

    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _bought_glowglobes(full)
    assert _legal(state, "resolve_tech_acquire_effect") == []
    assert [a.action_id for a in ENGINE.whole_actions(state, 0)] == [
        "finish_agent_turn"
    ]
    found = _found(state)
    assert _rows(found, "choice") == {}
    rows = _rows(found, "waiting")
    assert list(rows) == ["waiting:tech_acquire_influence:glowglobes"]
    row = rows["waiting:tech_acquire_influence:glowglobes"]
    assert row["action"]["action_id"] == "resolve_tech_acquire_effect"
    assert row["action"]["arguments"] == {
        "effect": "influence",
        "tech_id": "glowglobes",
    }
    assert _why(row) == _ALL_AT_THE_TOP_WAITING

    owner = PlayerState(
        player_id=0, hand=starting_deck_instance_ids(0)[:5], influence=full
    )
    revealed = _reveal(_state(owner, config=TECH_CONFIG), 0)
    frame = revealed.decision_stack[-1]
    owing = {**dict(frame.context), TECH_ACQUIRE_PENDING_KEY: "glowglobes:influence"}
    waiting = replace(
        revealed,
        decision_stack=(*revealed.decision_stack[:-1], with_context(frame, owing)),
    )
    assert _legal(waiting, "resolve_tech_acquire_effect") == []
    reveal_row = _rows(_found(waiting), "waiting")[
        "waiting:tech_acquire_influence:glowglobes"
    ]
    assert _why(reveal_row) == (
        "Every Faction it can raise is already at the top (6);"
        " it lapses if still unmet when the Reveal turn ends",
        "올릴 수 있는 {faction}의 {influence_any}이 모두 이미 최고치(6)"
        " — {reveal_turn}를 끝낼 때까지 못 채우면 사라짐",
        "waiting",
    )


def test_a_combat_tech_acquire_influence_shows_the_four_greyed_factions() -> None:
    """In Combat's acquire-effects-only frame (Battlefield Research) no turn
    end lapses the icon: with every cube at 6 the owner's confirm is legal
    and the four Factions show greyed out beside it, with no waiting row.
    With a Faction below 6 only the others are greyed and there is no
    confirm (OQ-060, OQ-098)."""

    full = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _combat_acquire_frame(full)
    assert _legal(state, "resolve_tech_influence_without_faction") == [{}]
    assert _legal(state, "resolve_tech_acquire_effect") == []
    found = _found(state)
    assert found["frame"] == FrameKind.TECH_ACQUISITION
    assert _rows(found, "waiting") == {}
    assert _faction_rows(
        found, "tech_acquire_influence:glowglobes", "resolve_tech_acquire_effect"
    ) == {faction: _AT_THE_TOP for faction in _FACTION_NAMES}

    some = _combat_acquire_frame(replace(full, fremen=5))
    assert _legal(some, "resolve_tech_influence_without_faction") == []
    assert [
        args["faction"] for args in _legal(some, "resolve_tech_acquire_effect")
    ] == ["fremen"]
    assert _faction_rows(
        _found(some), "tech_acquire_influence:glowglobes", "resolve_tech_acquire_effect"
    ) == {
        "emperor": _AT_THE_TOP,
        "spacing_guild": _AT_THE_TOP,
        "bene_gesserit": _AT_THE_TOP,
    }
