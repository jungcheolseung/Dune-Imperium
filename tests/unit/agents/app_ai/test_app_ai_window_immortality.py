"""The Immortality decision windows of app_ai (``windows/immortality.py``).

Each test reaches a real Immortality game state (``testing.play_until`` /
``first_decision``), sets the fields that decide the answer, opens the window
with the engine's own frame builders where the heuristic game does not reach
it, and checks the exact action the app's evaluator gives.
"""

import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from functools import cache

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.abilities.base import Answer, Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.generic import TrashCustomAbility
from dune_imperium.agents.app_ai.abilities.immortality import (
    GainAnyFactionInfluenceCustomAbility,
    GainResearchAbility,
    HarvestCellsAbility,
    ImperiumCeremonyAbility,
    graft_card_evaluate,
)
from dune_imperium.agents.app_ai.catalog import (
    card_entity,
    intrigue_entity,
    space_entity,
    track_entity,
)
from dune_imperium.agents.app_ai.choice import first_strictly_best
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile.immortality import research_space_entity
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
    with_state,
)
from dune_imperium.agents.app_ai.windows import handler_for
from dune_imperium.agents.app_ai.windows import immortality as W
from dune_imperium.agents.app_ai.windows.agent_effects import (
    CONTROL_THE_SPICE_TRASH_INTENT,
    STITCHED_HORROR_TRASH_INTENT,
)
from dune_imperium.agents.app_ai.windows.common import (
    TurnRowGap,
    research_icon_now,
    waiting_turn_row,
)
from dune_imperium.agents.app_ai.windows.intrigue import (
    INTENT,
    INTENT_AT,
    RESEARCH_INTENT,
    event_stamp,
    intrigue_request,
)
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory, arg
from dune_imperium.agents.app_ai.windows.turn import GRAFT_PARTNER_INTENT
from dune_imperium.content.immortality.board import ResearchBonus
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.effects import agent_card_source
from dune_imperium.rules.immortality import (
    _bonus_frame,
    advance_research,
    move_research_token,
    pending_research_bonuses,
)
from dune_imperium.rules.intrigue_peek import begin_intrigue_peek
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.simulation.runner import run_policy_game

IMMORTALITY = RulesetConfig(choam_module=True, immortality=True)


def _seat(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _run(
    state: GameState, *, memory: Memory | None = None, rng_seed: int = 0
) -> DecisionRun:
    seat = _seat(state)
    profile = make_profile(state, seat, rng_seed=rng_seed)
    # The whole actions the rules resolve (stage B3c-1: the Conflict-end
    # window offers a play effect first).
    actions = ENGINE.whole_actions(state, seat)
    return DecisionRun(profile.ctx, profile, actions, profile.rng, memory or Memory())


def _arg(action: DomainAction | None, name: str) -> object:
    assert action is not None
    return arg(action, name)


def _with(
    actions: Sequence[DomainAction], action_id: str, name: str, value: object
) -> DomainAction:
    for action in actions:
        if action.action_id == action_id and arg(action, name) == value:
            return action
    raise AssertionError(f"no {action_id}({name}={value!r})")


def _with_legal(run: DecisionRun, *extra: DomainAction) -> DecisionRun:
    """``run`` with ``extra`` actions appended to its legal list."""

    return DecisionRun(run.ctx, run.profile, (*run.legal, *extra), run.rng, run.memory)


@cache
def _graft(seed: int) -> GameState:
    return first_decision("graft_partner", config=IMMORTALITY, seed=seed)


@cache
def _research() -> GameState:
    """Seat 1 of seed 1, round 2: a research step from c1r3 (Spiritual
    Fervor's acquire box), hand empty, Dagger and Reconnaissance in play."""

    return first_decision("research_advance", config=IMMORTALITY, seed=1)


def _research_seat(**changes: object) -> tuple[GameState, int]:
    state = _research()
    seat = _seat(state)
    return with_player(state, seat, **changes), seat


def _bonus_state(before: str, space: str, **changes: object) -> GameState:
    """The research token moved from ``before`` onto ``space`` (its bonus
    waiting on the Reveal, or its optional trash on top)."""

    state, seat = _research_seat(research_space=before, **changes)
    return move_research_token(state, seat, space, source="test").state


_BONUS_OF: dict[str, ResearchBonus] = {
    "c6r6": ResearchBonus.INFLUENCE_ANY,
    "c7r3": ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE,
    "c8r6": ResearchBonus.SEVEN_SOLARI_FOR_TWO_TLEILAXU,
}


def _window(space: str, **changes: object) -> GameState:
    """``space``'s bonus window, as it opens outside the owner's turn
    (Combat, the Arrakeen Scouts step; cleanup-2b)."""

    state, seat = _research_seat(research_space=space, **changes)
    return state.push_decision(_bonus_frame(seat, _BONUS_OF[space], "test"))


def _waiting(space: str, **changes: object) -> GameState:
    """``space``'s bonus waiting on the seat's Reveal frame, on top
    (cleanup-2b): its rows beside the Reveal's others."""

    state, seat = _research_seat(research_space=space, **changes)
    queued = turn_rows.queue(
        state.pop_decision(),
        seat,
        (turn_rows.RESEARCH_BONUS, "test", _BONUS_OF[space].value),
    )
    assert queued is not None
    return queued


# -- registry ----------------------------------------------------------------------


def test_every_window_of_the_module_is_registered() -> None:
    for kind, handler in W.HANDLERS.items():
        assert handler_for(kind) is handler
    assert set(W.HANDLERS) == {
        "graft_partner",
        "research_advance",
        "research_bonus",
        "optional_trash",
        "intrigue_peek",
        "conflict_end_trigger",
    }


# -- graft_partner -----------------------------------------------------------------


def _graft_parts(state: GameState) -> tuple[str, str]:
    context = dict(state.decision_stack[-1].context)
    return str(context["card_id"]), str(context["space_id"])


def test_graft_partner_takes_the_turn_windows_stored_partner() -> None:
    # Seed 71, round 3: seat 0's Face Dancer placed at the Sardaukar space,
    # three partners in hand. Seed 1 (Ghola placed at Spice Refinery) was
    # this window until the Conflict-end change (troops back before the
    # windows, Harvest Cells resolving as it is played, 2026-10-18) moved
    # every later game. Of seeds 1-120 only 31, 71, 74 and 108 first reach
    # a Graft card placed with three partners; seed 31's evaluator pick is
    # its last partner (the stored one below would not differ from it), so
    # the first that works is 71.
    state = _graft(71)
    placed, _space = _graft_parts(state)
    run = _run(state)
    partners = [str(arg(a, "card_id")) for a in run.legal]
    assert len(partners) == 3
    assert partners[-1] != _evaluator_partner(state)[0]
    key = (GRAFT_PARTNER_INTENT, state.round_number, placed)
    run.memory.intents[key] = partners[-1]
    assert _arg(W.graft_partner(run), "card_id") == partners[-1]
    assert key not in run.memory.intents


def _evaluator_partner(state: GameState, rng_seed: int = 0) -> tuple[str | None, float]:
    placed, space_id = _graft_parts(state)
    seat = _seat(state)
    profile = make_profile(state, seat, rng_seed=rng_seed)
    hand = set(state.players[seat].hand)
    refs = [str(arg(a, "card_id")) for a in ENGINE.legal_actions(state, seat)]
    candidates = tuple(card_entity(r, seat if r in hand else None) for r in refs)
    answer = graft_card_evaluate(
        profile,
        Request((TargetInfo(candidates, (), 1, 1, True),), forced=True),
        card_entity(placed, seat),
        space_entity(space_id, profile.ctx.board),
    )
    ref = answer.response[0][0] if answer.response and answer.response[0] else None
    return (None if ref is None else str(ref)), answer.value


def test_graft_partner_without_a_stored_partner_is_graft_card_evaluator() -> None:
    state = _graft(71)
    expected, value = _evaluator_partner(state)
    assert expected is not None and value > 0  # 100 base value
    assert _arg(W.graft_partner(_run(state)), "card_id") == expected


def test_graft_partner_ignores_an_illegal_stored_partner() -> None:
    state = _graft(71)
    placed, _space = _graft_parts(state)
    run = _run(state)
    key = (GRAFT_PARTNER_INTENT, state.round_number, placed)
    run.memory.intents[key] = "imperium:not_a_partner:0"
    expected, _value = _evaluator_partner(state)
    assert _arg(W.graft_partner(run), "card_id") == expected
    assert key not in run.memory.intents


@pytest.mark.parametrize("rng_seed", [0, 1, 2])
def test_graft_partner_of_a_plain_card_is_the_default_random_choice(
    rng_seed: int,
) -> None:
    """``GraftCardEvaluator`` answers nothing for a non-Graft played card: the
    forced prompt falls to ``DefaultRandomChoice`` (a uniform legal partner)."""

    # Seed 128, round 3: seat 1 placed its Signet Ring at Arrakeen with two
    # Graft partners in hand. Seed 3 reached such a window until 5654d7f8 (a
    # Combat Intrigue pass right after a card play no longer counts as a
    # consecutive pass, 2026-10-07), seed 137 until the Conflict-end window
    # opened on public facts (OQ-103, codec v141) moved its game, seed 107
    # until Imperial Privilege's card draw became its own icon (2026-10-10,
    # OQ-027 (d)) moved its game at round 3 seat 3's Imperial Privilege
    # visit, and seed 193 until the Conflict-end change (troops back before
    # the windows, Harvest Cells resolving as it is played, 2026-10-18) moved
    # every later game; of seeds 1-127 every first Graft window now has a
    # Graft card placed or a plain card with one partner.
    state = _graft(128)
    placed, _space = _graft_parts(state)
    assert placed.endswith("signet_ring:0")
    assert _evaluator_partner(state, rng_seed)[0] is None
    run = _run(state, rng_seed=rng_seed)
    legal = run.by_id("choose_graft_partner")
    expected = legal[random.Random(rng_seed).randrange(len(legal))]
    assert W.graft_partner(run) == expected


_UNKNOWN_CARD = "imperium:not_an_app_card:0"


def test_graft_partner_with_an_unknown_partner_is_a_gap() -> None:
    """No stored partner and a candidate with no app archetype: None (the
    census shows it), never a silent pick."""

    state = _graft(71)
    stray = DomainAction(
        action_id="choose_graft_partner",
        actor=_seat(state),
        arguments=(("card_id", _UNKNOWN_CARD),),
    )
    run = _run(state)
    assert W.graft_partner(_with_legal(run, stray)) is None


# -- research_advance --------------------------------------------------------------


def _gain_research_answer(state: GameState) -> Answer:
    seat = _seat(state)
    profile = make_profile(state, seat)
    spaces = [str(arg(a, "space_id")) for a in ENGINE.legal_actions(state, seat)]
    entities = tuple(research_space_entity(s) for s in spaces)
    ability = GainResearchAbility(research_space_entity("c0r3"))
    return ability.evaluate(profile, Request((TargetInfo(entities),)))


def test_research_advance_is_gain_research_evaluate() -> None:
    """From c1r3: c2r2 and c2r4 at ``SpaceValue + 1.0``, NextIndices order,
    the first strictly best above the 1.0 "no space" answer."""

    state = _research()
    profile = make_profile(state, _seat(state))
    values = [(s, profile.research_space_value(s).sum + 1.0) for s in ("c2r2", "c2r4")]
    best = first_strictly_best(values)
    assert best is not None and best[1] > 1.0
    answer = _gain_research_answer(state)
    assert answer.response == ((f"research:{best[0]}",),)
    assert _arg(W.research_advance(_run(state)), "space_id") == best[0]


def test_research_advance_without_a_space_worth_more_than_zero() -> None:
    """At Tleilaxu rank 7 with no Solari, c8r4 and c8r6 are both worth 0: the
    app answers "no space" (and would draw instead); the window takes the
    first strictly best space."""

    state, _seat_ = _research_seat(
        research_space="c7r5",
        tleilaxu_space=7,
        resources=replace(_research().players[1].resources, solari=0),
    )
    answer = _gain_research_answer(state)
    assert answer.value == 1.0 and answer.response == ((),)
    assert _arg(W.research_advance(_run(state)), "space_id") == "c8r4"


def test_research_advance_takes_a_breakthrough_plays_space() -> None:
    """A Breakthrough play's recorded answer names the space
    (``windows.intrigue.research_intent``), even against the floor pick."""

    base, seat = _research_seat()
    instance = "intrigue:breakthrough:0"
    played = GameEvent(
        event_id="test:breakthrough",
        kind="intrigue_played",
        payload=(("card_id", instance), ("player", seat)),
    )
    base = with_state(base, event_log=(*base.event_log, played))
    source = f"round:{base.round_number}:player:{seat}:intrigue:{instance}:research:0"
    state = advance_research(base, seat, source=source).state
    floor_pick = str(_gain_research_answer(state).response[0][0])  # type: ignore[index]
    other = next(s for s in ("c2r2", "c2r4") if f"research:{s}" != floor_pick)
    memory = Memory()
    memory.intents[(INTENT, instance)] = Answer(1.0, ((f"research:{other}",),))
    memory.intents[(INTENT_AT, instance)] = event_stamp(base) - 1
    assert _arg(W.research_advance(_run(state, memory=memory)), "space_id") == other


# -- research_bonus ----------------------------------------------------------------


def test_research_bonus_influence_is_gain_any_influence_evaluate() -> None:
    state = _window("c6r6")
    assert state.decision_stack[-1].kind == "research_bonus"
    profile = make_profile(state, _seat(state))
    tracks = tuple(track_entity(f) for f in FACTIONS)
    answer = GainAnyFactionInfluenceCustomAbility(
        research_space_entity("c6r6")
    ).evaluate(profile, Request((TargetInfo(tracks),)))
    assert answer.response is not None
    action = W.research_bonus(_run(state))
    assert action is not None and action.action_id == "choose_research_influence"
    assert _arg(action, "faction") == answer.response[0][0]
    # Waiting on the turn, the forced Influence is taken first, the same.
    waiting = _waiting("c6r6")
    assert W.research_bonus_now(_run(waiting)) == action


def test_a_research_bonus_moved_in_the_turn_waits_on_it() -> None:
    state = _bonus_state("c5r5", "c6r6")
    assert state.decision_stack[-1].kind != "research_bonus"
    turn = state.pop_decision()
    assert [b for b, _ in pending_research_bonuses(turn, _seat(state))] == [
        ResearchBonus.INFLUENCE_ANY
    ]


_SPRING_THE_TRAP = "intrigue:spring_the_trap:0"


def _no_spies() -> dict[str, object]:
    """Changes recalling every Spy of the research seat to its supply."""

    me = _research().players[1]
    return {"spy_post_ids": (), "spies_supply": me.spies_supply + len(me.spy_post_ids)}


_SPICE_IS_POWER = "intrigue:spice_is_power:0"  # ``IsBadIntrigue`` false


def test_research_bonus_trashes_a_junk_intrigue() -> None:
    """Spring the Trap with no Spy on the board is junk (``IsBadIntrigue``):
    ``TrashIntrigueForDrawAndIntrigue`` answers it at 5.0."""

    state = _window("c7r3", intrigue_cards=(_SPRING_THE_TRAP,), **_no_spies())
    action = W.research_bonus(_run(state))
    assert action is not None
    assert action.action_id == "trash_intrigue_for_research_bonus"
    assert _arg(action, "card_id") == _SPRING_THE_TRAP
    waiting = _waiting("c7r3", intrigue_cards=(_SPRING_THE_TRAP,), **_no_spies())
    assert W.research_bonus_now(_run(waiting)) == action


def test_research_bonus_keeps_a_useful_intrigue() -> None:
    state = _window("c7r3", intrigue_cards=(_SPRING_THE_TRAP,))
    assert state.players[_seat(state)].spy_post_ids  # not junk with a Spy out
    action = W.research_bonus(_run(state))
    assert action is not None and action.action_id == "decline_research_bonus"
    # Waiting on the turn, the app leaves it on its playmat for now.
    waiting = _waiting("c7r3", intrigue_cards=(_SPRING_THE_TRAP,))
    assert W.research_bonus_now(_run(waiting)) is None


def _c8r6(tleilaxu: int, solari: int, *, waiting: bool = False) -> GameState:
    resources = replace(_research().players[1].resources, solari=solari)
    build = _waiting if waiting else _window
    return build("c8r6", tleilaxu_space=tleilaxu, resources=resources)


def test_research_bonus_pays_seven_solari_for_two_tleilaxu() -> None:
    state = _c8r6(tleilaxu=0, solari=9)
    assert state.decision_stack[-1].kind == "research_bonus"
    action = W.research_bonus(_run(state))
    assert action is not None and action.action_id == "pay_research_bonus"
    assert W.research_bonus_now(_run(_c8r6(0, 9, waiting=True))) == action


@pytest.mark.parametrize("tleilaxu", [6, 7])
def test_research_bonus_never_pays_near_the_end_of_the_tleilaxu_track(
    tleilaxu: int,
) -> None:
    """Rank 7: the app's ``Cost`` (``CanGainTleilaxu``) fails, no key; rank 6:
    ``PaySolariForTleilaxuInfluence``'s V is 0 above rank 5."""

    state = _c8r6(tleilaxu=tleilaxu, solari=9)
    # At rank 7 the engine no longer offers the payment either: it would buy
    # nothing (OQ-071, ``ResearchBonusBlock.TLEILAXU_TRACK_END``).
    assert {a.action_id for a in _run(state).legal} == (
        {"pay_research_bonus", "decline_research_bonus"}
        if tleilaxu < 7
        else {"decline_research_bonus"}
    )
    action = W.research_bonus(_run(state))
    assert action is not None and action.action_id == "decline_research_bonus"
    assert W.research_bonus_now(_run(_c8r6(tleilaxu, 9, waiting=True))) is None


def test_research_bonus_lapse_is_the_only_decline() -> None:
    """c7r3 with no Intrigue in hand: the window opens with the lapse only
    (``decline_research_bonus``), which is the answer."""

    state = _window("c7r3", intrigue_cards=())
    run = _run(state)
    assert {a.action_id for a in run.legal} == {"decline_research_bonus"}
    action = W.research_bonus(run)
    assert action is not None and action.action_id == "decline_research_bonus"


def test_research_bonus_with_an_unknown_choice_is_a_gap() -> None:
    """A bonus id the window does not know is not answered with the decline
    (regression: the handler used to fall through to ``decline``)."""

    state = _window("c7r3", intrigue_cards=())
    run = _run(state)
    seat = _seat(state)
    mystery = DomainAction(action_id="mystery_research_bonus", actor=seat)
    assert W.research_bonus(_with_legal(run, mystery)) is None


def _icon_window(
    bonus: ResearchBonus, icons: tuple[str, ...], **changes: object
) -> GameState:
    """``bonus``'s window ordering ``icons``, as it opens outside the owner's
    turn (Combat, the Arrakeen Scouts step)."""

    state, seat = _research_seat(**changes)
    return state.push_decision(_bonus_frame(seat, bonus, "test", icons=icons))


def _icon_effects(run: DecisionRun) -> list[str]:
    return [str(arg(a, "effect")) for a in run.by_id("resolve_research_icon")]


def test_research_icon_now_takes_the_specimen_before_the_other_icons() -> None:
    """User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    OQ-027 [Main p. 9]: the owner orders a research space's independent icons.
    The app has no such order (it resolves them inside the step that moves the
    token), so the AI takes the older engine's: specimen, Tleilaxu, trash."""

    # c3r5 in the owner's turn: a specimen and a Tleilaxu advance wait as rows.
    pair = _bonus_state("c2r4", "c3r5").pop_decision()
    run = _run(pair)
    assert _icon_effects(run) == ["specimen", "tleilaxu"]
    first = research_icon_now(run)
    assert first is not None and _arg(first, "effect") == "specimen"
    # Whatever order the rows are listed in.
    backwards = DecisionRun(
        run.ctx, run.profile, tuple(reversed(run.legal)), run.rng, run.memory
    )
    assert _icon_effects(backwards) == ["tleilaxu", "specimen"]
    assert research_icon_now(backwards) == first
    # The turn's waiting-row hook takes the same row first.
    assert waiting_turn_row(run) == first
    taken = apply_whole(ENGINE, pair, first).state
    second = research_icon_now(_run(taken))
    assert second is not None and _arg(second, "effect") == "tleilaxu"

    # c3r3: the trash rows are not icon rows; the specimen goes first.
    trash_pair = _bonus_state("c2r2", "c3r3").pop_decision()
    trash_run = _run(trash_pair)
    assert "trash_optional_card" in {a.action_id for a in trash_run.legal}
    row = research_icon_now(trash_run)
    assert row is not None and _arg(row, "effect") == "specimen"


def test_research_icon_now_is_none_without_an_icon_row() -> None:
    # User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    # OQ-027 [Main p. 9]: no icon row, nothing taken (a direction frame, c7r3's
    # arrow window).
    assert research_icon_now(_run(_research())) is None
    assert research_icon_now(_run(_window("c7r3", intrigue_cards=()))) is None


@pytest.mark.parametrize(
    ("bonus", "icons", "expected"),
    [
        (ResearchBonus.TRASH_AND_SPECIMEN, ("specimen", "trash"), "specimen"),
        (ResearchBonus.TRASH_AND_SPECIMEN, ("trash", "specimen"), "specimen"),
        (ResearchBonus.TRASH_AND_SPECIMEN, ("trash",), "trash"),
        (ResearchBonus.TLEILAXU_AND_SPECIMEN, ("specimen", "tleilaxu"), "specimen"),
        (ResearchBonus.TLEILAXU_AND_SPECIMEN, ("tleilaxu", "specimen"), "specimen"),
        (ResearchBonus.TLEILAXU_AND_SPECIMEN, ("tleilaxu",), "tleilaxu"),
        (
            ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE,
            ("intrigue", "cards"),
            "intrigue",
        ),
        (
            ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE,
            ("cards", "intrigue"),
            "intrigue",
        ),
        (ResearchBonus.TRASH_INTRIGUE_FOR_CARD_AND_INTRIGUE, ("cards",), "cards"),
    ],
)
def test_research_bonus_takes_the_first_icon_of_an_icon_window(
    bonus: ResearchBonus, icons: tuple[str, ...], expected: str
) -> None:
    """User decision 2026-10-17, composed-effects plan 5, rule decision 5;
    OQ-027 [Main p. 9]: a window ordering a pair's icons (or c7r3's rewards)
    has no decline; the handler answers the first icon in the fixed order
    (``RESEARCH_ICON_ORDER``), not the order the rows are listed in."""

    state = _icon_window(bonus, icons)
    run = _run(state)
    assert sorted(_icon_effects(run)) == sorted(icons)
    assert {a.action_id for a in run.legal} == {"resolve_research_icon"}
    action = W.research_bonus(run)
    assert action is not None and action.action_id == "resolve_research_icon"
    assert _arg(action, "effect") == expected


def test_research_advance_with_a_space_off_the_track_is_a_gap() -> None:
    state = _research()
    run = _run(state)
    stray = DomainAction(
        action_id="choose_research_space",
        actor=_seat(state),
        arguments=(("space_id", "c9r9"),),
    )
    assert W.research_advance(_with_legal(run, stray)) is None


def test_research_advance_takes_a_reveal_research_keys_space() -> None:
    """Tleilaxu Master's Reveal research: the space the ``reveal`` window
    stored under ``RESEARCH_INTENT`` (read and dropped by
    ``windows.intrigue.research_intent``) beats the floor pick."""

    base, seat = _research_seat()
    source = f"round:{base.round_number}:player:{seat}:reveal_gain:research:0"
    state = advance_research(base, seat, source=source).state
    floor_pick = str(_gain_research_answer(state).response[0][0])  # type: ignore[index]
    other = next(s for s in ("c2r2", "c2r4") if f"research:{s}" != floor_pick)
    memory = Memory()
    key = (RESEARCH_INTENT, state.round_number, seat)
    memory.intents[key] = other
    assert _arg(W.research_advance(_run(state, memory=memory)), "space_id") == other
    assert key not in memory.intents


# -- optional_trash ----------------------------------------------------------------


def _get_card_to_trash(state: GameState, rng_seed: int = 0) -> str | None:
    seat = _seat(state)
    profile = make_profile(state, seat, rng_seed=rng_seed)
    # The whole actions: on the turn a trash is its icon's row, then the
    # card (stage B3c-2b).
    refs = [
        str(arg(a, "card_id"))
        for a in ENGINE.whole_actions(state, seat)
        if a.action_id == "trash_optional_card"
    ]
    cards = tuple(card_entity(r, seat) for r in refs)
    answer = TrashCustomAbility(Entity(Kind.CARD, "x")).evaluate(
        profile, Request((TargetInfo(cards),))
    )
    assert answer.response is not None
    return str(answer.response[0][0]) if answer.response[0] else None


def _trash_source(state: GameState, seat: int) -> str:
    return f"round:{state.round_number}:player:{seat}:research:c3r3"


def _trash_window(**changes: object) -> GameState:
    """A research space's optional trash window, as it opens outside the
    owner's turn (Combat, the Arrakeen Scouts step; cleanup-2b)."""

    state, seat = _research_seat(**changes)
    return state.push_decision(optional_trash_frame(seat, _trash_source(state, seat)))


def _waiting_trash(**changes: object) -> GameState:
    """A research space's optional trash waiting on the seat's Reveal frame,
    on top (cleanup-2b): its rows beside the Reveal's others, no decline."""

    state, seat = _research_seat(**changes)
    # The research space's trash, recording its printer (stage B3c-2b).
    source = _trash_source(state, seat)
    queued = turn_rows.queue(
        state.pop_decision(),
        seat,
        (turn_rows.OPTIONAL_TRASH, source, f"research|{source.rsplit(':', 1)[1]}"),
    )
    assert queued is not None
    return queued


def _no_junk(**changes: object) -> dict[str, object]:
    """Only the Signet Ring (``TrashValue`` 0) can be trashed."""

    me = _research().players[1]
    signet = "player:1:starter:signet_ring:0"
    cards = (*me.deck, *me.discard_pile, *me.in_play)
    return {
        "deck": tuple(c for c in cards if c != signet),
        "hand": (signet,),
        "discard_pile": (),
        "in_play": (),
        **changes,
    }


def test_a_research_hex_trashes_its_owners_turn_rows() -> None:
    """Inside the owner's own turn c3r3's trash waits on the turn as rows,
    with no decline (cleanup-2b), beside its specimen: the two icons are
    independent effects in the owner's order (user decision 2026-10-17,
    composed-effects plan 5, rule decision 5; OQ-027 [Main p. 9])."""

    state = _bonus_state("c2r2", "c3r3")
    seat = _seat(state)
    reveal = state.pop_decision()
    assert [kind for kind, _, _ in turn_rows.pending(reveal.decision_stack[-1])] == [
        turn_rows.RESEARCH_ICON,
        turn_rows.OPTIONAL_TRASH,
    ]
    ids = {a.action_id for a in ENGINE.whole_actions(reveal, seat)}
    assert {"trash_optional_card", "resolve_research_icon"} <= ids
    assert "decline_optional_trash" not in ids


@pytest.mark.parametrize("rng_seed", [0, 3])
def test_optional_trash_of_a_research_hex_is_get_card_to_trash(rng_seed: int) -> None:
    state = _trash_window()
    assert state.decision_stack[-1].kind == "optional_trash"
    expected = _get_card_to_trash(state, rng_seed)
    assert expected is not None  # the Dagger in play is junk
    action = W.optional_trash(_run(state, rng_seed=rng_seed))
    assert action is not None and action.action_id == "trash_optional_card"
    assert _arg(action, "card_id") == expected


@pytest.mark.parametrize("rng_seed", [0, 3])
def test_a_waiting_trash_is_get_card_to_trash(rng_seed: int) -> None:
    state = _waiting_trash()
    expected = _get_card_to_trash(state, rng_seed)
    assert expected is not None
    action = W.optional_trash_now(_run(state, rng_seed=rng_seed))
    assert action is not None and action.action_id == "trash_optional_card"
    assert _arg(action, "card_id") == expected


def test_optional_trash_declines_without_a_junk_card() -> None:
    """Only the Signet Ring (``TrashValue`` 0) can be trashed: "trash
    nothing" at 1.0 is the answer."""

    state = _trash_window(**_no_junk())
    assert _get_card_to_trash(state) is None
    action = W.optional_trash(_run(state))
    assert action is not None and action.action_id == "decline_optional_trash"


def test_a_waiting_trash_with_no_junk_card_is_answered_once() -> None:
    """In the turn "trash nothing" takes no row: the trash waits for the
    turn end to lapse it, and the app, which prompts once per icon, is not
    asked again (``TRASH_ANSWERED_INTENT``)."""

    state = _waiting_trash(**_no_junk())
    seat = _seat(state)
    memory = Memory()
    assert W.optional_trash_now(_run(state, memory=memory)) is None
    key = (W.TRASH_ANSWERED_INTENT, state.round_number, _trash_source(state, seat))
    assert memory.intents[key] is True
    assert W.optional_trash_now(_run(state, memory=memory)) is None


def test_optional_trash_with_an_unknown_card_is_a_gap() -> None:
    state = _trash_window()
    stray = DomainAction(
        action_id="trash_optional_card",
        actor=_seat(state),
        arguments=(("card_id", _UNKNOWN_CARD),),
    )
    assert W.optional_trash(_with_legal(_run(state), stray)) is None


def test_a_waiting_trash_with_an_unknown_card_is_a_gap() -> None:
    state = _waiting_trash()
    stray = DomainAction(
        action_id="trash_optional_card",
        actor=_seat(state),
        arguments=(("card_id", _UNKNOWN_CARD),),
    )
    with pytest.raises(TurnRowGap):
        W.optional_trash_now(_with_legal(_run(state), stray))


def test_a_waiting_planetologist_card_is_drawn_first() -> None:
    """Liet Kynes' replacement in the owner's turn waits as a trash and an
    Intrigue card (cleanup-2b); the card is drawn first, as the replacement
    paid it before the trash."""

    state, seat = _research_seat()
    source = f"round:{state.round_number}:player:{seat}:hagga_basin:planetologist:0"
    turn = state.pop_decision()
    # The trash records the leader that printed it (stage B3c-2b).
    for kind, value in (
        (turn_rows.OPTIONAL_TRASH, "leader|liet_kynes"),
        (turn_rows.PLANETOLOGIST_INTRIGUE, ""),
    ):
        queued = turn_rows.queue(turn, seat, (kind, source, value))
        assert queued is not None
        turn = queued
    action = W.optional_trash_now(_run(turn))
    assert action == DomainAction(action_id="draw_planetologist_intrigue", actor=seat)


def test_planetologist_frame_draws_its_intrigue_first() -> None:
    """Liet Kynes' replacement frame holds its Intrigue card as its own step
    (``draw_planetologist_intrigue``, user ruling 2026-10-10, OQ-106); the
    window takes it before the trash, as the replacement paid it before."""

    state, seat = _research_seat()
    source = f"round:{state.round_number}:player:{seat}:hagga_basin:planetologist:0"
    state = state.push_decision(optional_trash_frame(seat, source, intrigue=True))
    action = W.optional_trash(_run(state))
    assert action == DomainAction(action_id="draw_planetologist_intrigue", actor=seat)


_CONTROL_THE_SPICE = "player:1:starter:control_the_spice:0"


def _agent_effects_frame(seat: int, card: str) -> DecisionFrame:
    """The seat's own Agent-effect frame, its active card ``card``."""

    return DecisionFrame(
        kind="agent_effects",
        frame_id="test:agent_effects",
        decision=PlayerDecision(owner=seat, prompt="Agent effects"),
        context=(("card_id", card),),
    )


def _control_the_spice_trash() -> GameState:
    """Control the Spice's trash frame, named exactly after its box (the
    own Agent-effect frame's active card)."""

    state, seat = _research_seat()
    state = state.push_decision(_agent_effects_frame(seat, _CONTROL_THE_SPICE))
    source = agent_card_source(state.round_number, seat, _CONTROL_THE_SPICE)
    return state.push_decision(optional_trash_frame(seat, source))


def test_optional_trash_follows_control_the_spices_stored_answer() -> None:
    """The stored card is trashed even where ``GetCardToTrash`` would pick
    another (the Reconnaissance, never the junk-most card)."""

    state = _control_the_spice_trash()
    reconnaissance = "player:1:starter:reconnaissance:0"
    assert _get_card_to_trash(state) != reconnaissance
    key = (CONTROL_THE_SPICE_TRASH_INTENT, state.round_number, _CONTROL_THE_SPICE)
    run = _run(state)
    run.memory.intents[key] = reconnaissance
    assert _arg(W.optional_trash(run), "card_id") == reconnaissance
    assert key not in run.memory.intents


@pytest.mark.parametrize("stored", [None, "imperium:not_owned:0"])
def test_optional_trash_declines_a_stored_nothing_or_an_illegal_card(
    stored: object,
) -> None:
    state = _control_the_spice_trash()
    key = (CONTROL_THE_SPICE_TRASH_INTENT, state.round_number, _CONTROL_THE_SPICE)
    run = _run(state)
    run.memory.intents[key] = stored
    action = W.optional_trash(run)
    assert action is not None and action.action_id == "decline_optional_trash"


def test_optional_trash_ignores_another_cards_stored_answer() -> None:
    state = _control_the_spice_trash()
    other = (CONTROL_THE_SPICE_TRASH_INTENT, state.round_number, "other:card:0")
    run = _run(state)
    run.memory.intents[other] = "player:1:starter:reconnaissance:0"
    assert _arg(W.optional_trash(run), "card_id") == _get_card_to_trash(state)
    assert other in run.memory.intents


def test_optional_trash_follows_stitched_horrors_stored_answer() -> None:
    """Stitched Horror's trash pick (source ``<box>:<n>``): the card its
    Evaluate named, keyed by the box's card."""

    state = first_decision("agent_effects", config=IMMORTALITY, seed=1)
    seat = _seat(state)
    card = str(dict(state.decision_stack[-1].context)["card_id"])
    source = f"{agent_card_source(state.round_number, seat, card)}:1"
    state = state.push_decision(optional_trash_frame(seat, source))
    run = _run(state)
    refs = [str(arg(a, "card_id")) for a in run.by_id("trash_optional_card")]
    chosen = next(r for r in refs if r != _get_card_to_trash(state))
    key = (STITCHED_HORROR_TRASH_INTENT, state.round_number, card)
    run.memory.intents[key] = chosen
    assert _arg(W.optional_trash(run), "card_id") == chosen
    assert key not in run.memory.intents


# -- intrigue_peek -----------------------------------------------------------------


def _peek(top: tuple[str, str], **changes: object) -> GameState:
    state, seat = _research_seat(**changes)
    rest = tuple(i for i in state.intrigue_deck if i not in top)
    state = with_state(state, intrigue_deck=(*top, *rest))
    return begin_intrigue_peek(state, seat, source="test").state


def test_intrigue_peek_keeps_the_card_that_is_not_junk() -> None:
    state = _peek((_SPRING_THE_TRAP, _SPICE_IS_POWER), **_no_spies())
    assert state.decision_stack[-1].kind == "intrigue_peek"
    for rng_seed in range(6):
        action = W.intrigue_peek(_run(state, rng_seed=rng_seed))
        assert _arg(action, "instance_id") == _SPICE_IS_POWER


def test_intrigue_peek_is_imperium_ceremony_evaluate_intrigue() -> None:
    """Two cards that are not junk tie at 50: the shuffle decides."""

    top = (_SPICE_IS_POWER, "intrigue:call_to_arms:0")
    state = _peek(top)
    seat = _seat(state)
    picks = set()
    for rng_seed in range(8):
        profile = make_profile(state, seat, rng_seed=rng_seed)
        cards = tuple(intrigue_entity(i, seat) for i in top)
        answer = ImperiumCeremonyAbility(Entity(Kind.CARD, "x")).evaluate_intrigue(
            profile, Request((TargetInfo(cards),))
        )
        assert answer.value == 50.0 and answer.response is not None
        action = W.intrigue_peek(_run(state, rng_seed=rng_seed))
        assert _arg(action, "instance_id") == answer.response[0][0]
        picks.add(answer.response[0][0])
    assert picks == set(top)


def test_intrigue_peek_with_an_unknown_card_is_a_gap() -> None:
    state = _peek((_SPICE_IS_POWER, "intrigue:call_to_arms:0"))
    stray = DomainAction(
        action_id="keep_peeked_intrigue",
        actor=_seat(state),
        arguments=(("instance_id", "intrigue:not_an_app_card:0"),),
    )
    assert W.intrigue_peek(_with_legal(_run(state), stray)) is None


# -- conflict_end_trigger ----------------------------------------------------------

_HARVEST_CELLS = "intrigue:harvest_cells:0"


@cache
def _conflict_end() -> GameState:
    """A Combat state with Harvest Cells in hand and only the Conflict-end
    window open (OQ-057): the seat's three troops have already gone back to
    its supply, which the window records as ``lost`` (user decision
    2026-10-18)."""

    state = first_decision("combat_intrigue", config=IMMORTALITY, seed=2)
    seat = _seat(state)
    me = state.players[seat]
    state = with_player(
        state,
        seat,
        intrigue_cards=(_HARVEST_CELLS,),
        troops_conflict=0,
        troops_supply=me.troops_supply + me.troops_conflict,
    )
    return with_state(
        state,
        decision_stack=(_conflict_end_frame(seat, played=False),),
        combat_rewards_resolved=True,
    )


def _conflict_end_frame(seat: int, *, played: bool) -> DecisionFrame:
    """The seat's Conflict-end window as the engine builds it: the loss in
    its context and, once a card was played in it, ``played``."""

    context: dict[str, bool | int | str] = {"lost": 3, "player": seat}
    if played:
        context["played"] = True
    return DecisionFrame(
        kind="conflict_end_trigger",
        frame_id="test:conflict_end_trigger",
        decision=PlayerDecision(owner=seat, prompt="test"),
        context=tuple(sorted(context.items())),
    )


def test_conflict_end_plays_harvest_cells_and_records_its_answer() -> None:
    state = _conflict_end()
    run = _run(state)
    action = W.conflict_end_trigger(run)
    assert action is not None and action.action_id == "play_conflict_end_intrigue"
    assert _arg(action, "card_id") == _HARVEST_CELLS
    seat = _seat(state)
    profile = make_profile(state, seat)
    expected = HarvestCellsAbility(intrigue_entity(_HARVEST_CELLS, seat)).evaluate(
        profile, intrigue_request(profile.ctx, _HARVEST_CELLS, True)
    )
    assert expected.value > 0
    assert run.memory.intents[(INTENT, _HARVEST_CELLS)] == expected
    stamp = run.memory.intents[(INTENT_AT, _HARVEST_CELLS)]
    applied = apply_whole(ENGINE, state, action, legal_actions=run.legal).state
    # The stamp counts the log's events but the effect picks (stage B3).
    assert stamp == event_stamp(state)
    log = [event for event in applied.event_log if event.kind != "effect_picked"]
    assert log[stamp].kind == "intrigue_played"
    # The card resolved at its play: the acquisition choice is on top of the
    # window and the app's answer is the one recorded for it.
    assert applied.decision_stack[-1].kind == "intrigue_choice"
    assert log[stamp + 1].kind == "specimens_generated"


def test_conflict_end_finishes_the_window_after_a_play() -> None:
    """Once a card was played in the window its one press reads "finish"
    (the engine offers no decline): with nothing else to play the handler
    answers it."""

    state = _conflict_end()
    seat = _seat(state)
    state = with_player(state, seat, intrigue_cards=())
    state = with_state(state, decision_stack=(_conflict_end_frame(seat, played=True),))
    run = _run(state)
    assert {a.action_id for a in run.legal} == {"finish_conflict_end_intrigue"}
    action = W.conflict_end_trigger(run)
    assert action is not None and action.action_id == "finish_conflict_end_intrigue"


def test_conflict_end_declines_when_harvest_cells_cannot_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``Cost`` (3 troops lost at this Conflict's end) failing means no key."""

    monkeypatch.setattr(HarvestCellsAbility, "meets_cost", lambda self, p: False)
    action = W.conflict_end_trigger(_run(_conflict_end()))
    assert action is not None and action.action_id == "decline_conflict_end_intrigue"


def test_conflict_end_without_a_combat_ability_is_a_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A card the engine offers but with no Combat-turn app ability to
    evaluate is not silently declined: the handler returns None so the
    census counts the gap (regression: it used to skip the key)."""

    monkeypatch.setattr(W, "ability_for_prompt", lambda card, combat: None)
    run = _run(_conflict_end())
    assert run.first("play_conflict_end_intrigue") is not None
    assert W.conflict_end_trigger(run) is None


# -- whole games -------------------------------------------------------------------


@pytest.mark.parametrize(
    "config",
    [
        RulesetConfig(choam_module=True, immortality=True),
        RulesetConfig(choam_module=False, immortality=True, epic_game=True),
    ],
)
def test_app_ai_games_answer_every_immortality_window(config: RulesetConfig) -> None:
    agents = [AppAIAgent(seed=70 + seat) for seat in range(4)]
    run_policy_game(ENGINE, config, 5, agents)
    fallbacks: Counter[str] = Counter()
    mirrored: Counter[str] = Counter()
    for agent in agents:
        fallbacks.update(agent.fallbacks)
        mirrored.update(agent.mirrored)
    assert not {kind: fallbacks[kind] for kind in W.HANDLERS if fallbacks[kind]}
    assert mirrored["research_advance"] > 0
