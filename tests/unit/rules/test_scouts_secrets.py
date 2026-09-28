"""Arrakeen Scouts: secret picks (slice 7).

docs/rules/arrakeen-scouts.md 7.1: "이벤트가 공개되면 First Player부터 차례로
각 좌석이 네 가지 중 하나를 **비밀리에** 고른다. 선택은 공개될 때까지 다른
좌석이 모른다." 7.2: "공개 라운드의 Scouts 단계 맨 앞(그 라운드의 항목보다
먼저)에 선택을 공개하고 보상을 해결한다" in event order, line order and turn
order from the First Player (OQ-085 (b)); the discard line is the seat's to
take or leave (OQ-085 (c)); a pick not due by the game's end is lost
(OQ-085 (a)). [Scouts event: Covert Operation] [Scouts event: Offworld
Operation]
"""

import random
from dataclasses import replace
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.agents.determinize import determinize
from dune_imperium.content.immortality.board import (
    FIRST_GENETIC_MARKER_COLUMN,
    RESEARCH_SPACES,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import (
    disclose_hidden_zones,
    known_card_seats,
    observe_state,
    secret_pick_id,
)
from dune_imperium.core.player import Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.scouts_secrets import pick_alternatives
from dune_imperium.server.session_log import log_step, reveals_hidden_information
from dune_imperium.server.sessions import _log_entry_json
from dune_imperium.simulation.invariants import (
    InvariantViolation,
    check_event_visibility,
    check_observation_privacy,
)

ENGINE = UprisingRulesEngine()
SCOUTS = RulesetConfig(arrakeen_scouts=True)
IMMORTALITY = RulesetConfig(arrakeen_scouts=True, immortality=True)


def _base(config: RulesetConfig = SCOUTS, round_number: int = 4) -> GameState:
    """A Scouts step about to draw its event; seat 0 is First Player."""

    state = ENGINE.reset(config, 21)
    resolver = ChanceResolver(seed=21)
    while isinstance(ENGINE.current_decision(state), ChanceDecision):
        decision = ENGINE.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = ENGINE.apply(state, resolver.resolve(decision)).state
    rich = Resources(solari=5, spice=5, water=2)
    return replace(
        state,
        round_number=round_number,
        first_player=0,
        players=tuple(replace(p, resources=rich) for p in state.players),
        decision_stack=(),
        scouts_opening=True,
    )


def _advance(state: GameState) -> GameState:
    return _advance_automatic(RuleResult(state=state)).state


def _reveal(state: GameState, item_id: str) -> GameState:
    advanced = _advance(state)
    frame = advanced.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_DRAW
    decision = frame.decision
    assert isinstance(decision, ChanceDecision)
    ticket = next(o for o in decision.options if o.split("#")[0] == item_id)
    return ENGINE.apply(
        advanced, ChanceOutcome(decision_id=decision.decision_id, values=(ticket,))
    ).state


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _act(state: GameState, action_id: str, **arguments: Any) -> GameState:
    seat = _owner(state)
    action = DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )
    legal = ENGINE.legal_actions(state, seat)
    assert action in legal, (action, legal)
    return ENGINE.apply(state, action, legal_actions=legal).state


def _pick_all(state: GameState, picks: dict[int, int]) -> GameState:
    order = []
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_SECRET:
        seat = _owner(state)
        order.append(seat)
        state = _act(state, "scouts_secret_pick", pick=picks[seat])
    assert order == [0, 1, 2, 3]
    return state


def _next_round(state: GameState, round_number: int) -> GameState:
    """The Scouts step of a later round, before anything ran."""

    return replace(
        state,
        round_number=round_number,
        scouts_opening=True,
        decision_stack=(),
        scouts_item="",
        scouts_tasks=(),
    )


# Covert Operation (CHOAM off): 0 Spy (next round), 1 Solari 2 (next
# round), 2 discard -> 3 troops (two rounds), 3 lowest Influence +1 (two).
PICKS = {0: 1, 1: 0, 2: 2, 3: 3}


def test_each_seat_picks_in_secret_in_turn_order() -> None:
    state = _reveal(_base(), "covert_operation")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_SECRET
    # All four lines are always offered: the mask says nothing.
    assert [a.arguments for a in ENGINE.legal_actions(state, 0)] == [
        (("pick", pick),) for pick in range(4)
    ]
    state = _pick_all(state, PICKS)
    assert sorted(state.scouts_secret_picks) == [
        (4, "covert_operation", seat, pick) for seat, pick in sorted(PICKS.items())
    ]
    picked = [e for e in state.event_log if e.kind == "scouts_secret_picked"]
    assert all(set(dict(e.payload)) == {"item_id", "player"} for e in picked)
    assert all(e.visible_to is None for e in picked)
    view = observe_state(state, 2)
    assert view.private is not None
    assert view.private.scouts_secret_picks == ((4, "covert_operation", 2),)
    assert {seat for _, _, seat in view.scouts_secret_pending} == {0, 1, 2, 3}
    known = known_card_seats(state)
    for seat in range(4):
        assert known[secret_pick_id(4, seat)] == frozenset({seat})
    check_observation_privacy(state)
    # The Scouts step then opens the First Player's turn.
    assert state.decision_stack[-1].kind == FrameKind.TURN


def test_due_picks_are_revealed_first_and_resolved_in_line_then_seat_order() -> None:
    picked = _pick_all(_reveal(_base(), "covert_operation"), PICKS)
    before = _next_round(picked, 5)
    solari = before.players[0].resources.solari
    result = _advance_automatic(RuleResult(state=before))
    state = result.state
    revealed = [
        dict(e.payload) for e in result.events if e.kind == "scouts_secret_revealed"
    ]
    # Line 0 (seat 1's Spy) before line 1 (seat 0's Solari).
    assert [(r["player"], r["pick"]) for r in revealed] == [(1, 0), (0, 1)]
    assert reveals_hidden_information(before, state, None)
    # Seat 1 places its Spy first; the round's own draw waits.
    assert _owner(state) == 1
    assert state.players[0].resources.solari == solari
    post = next(
        a for a in ENGINE.legal_actions(state, 1) if a.action_id == "place_spy_on_space"
    )
    state = ENGINE.apply(state, post).state
    assert state.players[0].resources.solari == solari + 2
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW
    # The two-round picks wait, known now to be two-round lines.
    waiting = sorted(row[2:] for row in state.scouts_secret_picks)
    assert waiting == [(2, 2), (3, 3)]
    for row in state.scouts_secret_picks:
        assert pick_alternatives(state, row) == (2, 3)
    check_observation_privacy(state)


def test_the_discard_line_may_be_taken_or_left() -> None:
    picked = _pick_all(_reveal(_base(), "covert_operation"), PICKS)
    state = _advance(_next_round(picked, 5))
    while state.decision_stack[-1].kind != FrameKind.SCOUTS_DRAW:
        seat = _owner(state)
        state = ENGINE.apply(state, ENGINE.legal_actions(state, seat)[0]).state
    state = _advance(_next_round(state, 6))
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
    assert _owner(state) == 2
    assert [a.action_id for a in ENGINE.legal_actions(state, 2)] == [
        "scouts_pass",
        "scouts_choose_option",
    ]
    # Every offered line is in the Scouts codec (a line index up to 3).
    codec = ActionCodec(SCOUTS)
    for action in ENGINE.legal_actions(state, 2):
        assert codec.decode(codec.encode(action), 2) == action
    garrison = state.players[2].troops_garrison
    state = _act(state, "scouts_choose_option", option=2)
    state = _act(state, "scouts_discard", card_id=state.players[2].hand[0])
    assert state.players[2].troops_garrison == garrison + 3
    assert state.scouts_secret_picks == ()


def test_offworld_operation_pays_more_past_the_helix() -> None:
    """OQ-089 (b): "Helix: spice 2" once the research token has reached the
    first genetic marker."""

    state = _reveal(_base(IMMORTALITY), "offworld_operation")
    state = _pick_all(state, {0: 1, 1: 1, 2: 0, 3: 0})
    past = next(
        s.space_id for s in RESEARCH_SPACES if s.column == FIRST_GENETIC_MARKER_COLUMN
    )
    seat0 = replace(state.players[0], research_space=past)
    state = replace(state, players=(seat0, *state.players[1:]))
    spice = [p.resources.spice for p in state.players]
    result = _advance_automatic(RuleResult(state=_next_round(state, 5)))
    state = result.state
    gained = {
        dict(e.payload)["player"]: dict(e.payload)["spice"]
        for e in result.events
        if e.kind == "scouts_helix_spice"
    }
    assert gained == {0: 2, 1: 1}
    assert state.players[0].resources.spice == spice[0] + 2
    assert state.players[1].resources.spice == spice[1] + 1


def test_picks_never_due_are_disclosed_after_the_game() -> None:
    picked = _pick_all(_reveal(_base(round_number=7), "covert_operation"), PICKS)
    assert disclose_hidden_zones(picked).scouts_secret_picks == (
        picked.scouts_secret_picks
    )


def test_determinize_redeals_only_the_other_seats_picks() -> None:
    state = _pick_all(_reveal(_base(), "covert_operation"), PICKS)
    for seed in range(8):
        sampled = determinize(state, 2, random.Random(seed))
        rows = {row[2]: row for row in sampled.scouts_secret_picks}
        assert rows[2] == (4, "covert_operation", 2, 2)
        assert all(0 <= row[3] < 4 for row in rows.values())
    seen = {
        determinize(state, 2, random.Random(seed)).scouts_secret_picks
        for seed in range(8)
    }
    assert len(seen) > 1


def test_a_public_pick_event_may_not_carry_the_pick() -> None:
    state = _pick_all(_reveal(_base(), "covert_operation"), PICKS)
    leaky = GameEvent(
        event_id="leak",
        kind="scouts_secret_picked",
        payload=(("item_id", "covert_operation"), ("pick", 1), ("player", 0)),
    )
    try:
        check_event_visibility(state, (leaky,))
    except InvariantViolation:
        pass
    else:
        raise AssertionError("a sealed value in a public event must fail")


def test_the_log_hides_a_pick_from_every_other_seat() -> None:
    before = _reveal(_base(), "covert_operation")
    action = DomainAction(
        action_id="scouts_secret_pick", actor=0, arguments=(("pick", 3),)
    )
    transition = ENGINE.apply(before, action)
    entry = log_step(before, transition.state, action, transition.events)
    assert entry.sealed
    # The pick itself reveals nothing, so its seat may still take it back.
    assert not entry.reveals
    assert _log_entry_json(0, entry, seat=0, finished=False)["arguments"] == {"pick": 3}
    assert _log_entry_json(0, entry, seat=1, finished=False)["arguments"] == {
        "pick": "(비공개)"
    }
    assert _log_entry_json(0, entry, seat=1, finished=True)["arguments"] == {"pick": 3}


def test_revealing_only_the_actors_own_pick_is_still_a_reveal() -> None:
    """Review finding (2026-09-28): the "own card" exception must not cover a
    pick falling due, or a step's undoability would tell its actor whether
    any other seat's pick was due with its own."""

    picks = {0: 0, 1: 2, 2: 2, 3: 3}
    before = _next_round(_pick_all(_reveal(_base(), "covert_operation"), picks), 5)
    after = _advance(before)
    assert [row[2] for row in after.scouts_secret_picks] == [1, 2, 3]
    assert reveals_hidden_information(before, after, 0)


def test_a_preview_running_into_the_reveal_shows_nothing() -> None:
    from dune_imperium.server.sessions import preview_outcome

    picked = _pick_all(_reveal(_base(), "covert_operation"), PICKS)
    before = _next_round(picked, 5)
    result = _advance_automatic(RuleResult(state=before))
    action = DomainAction(action_id="decline_control_defense", actor=0)
    assert preview_outcome(action, result) is None
    quiet = RuleResult(state=result.state, events=())
    assert preview_outcome(action, quiet) is quiet
    pick = DomainAction(
        action_id="scouts_secret_pick", actor=0, arguments=(("pick", 0),)
    )
    assert preview_outcome(pick, quiet) is None
