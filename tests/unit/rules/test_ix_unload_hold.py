"""An arrow's right side held while its cost's Unload box is decided.

Rule: docs/rules/rise-of-ix.md 7, the designer ruling "비용 → 효과 줄의
왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤 오른쪽으로 간다" (BGG
Forum 2023, adopted in 9.3). A box whose icon is the owner's decision (the
Freighter's move, "you may move your Freighter in one of two ways" [Rise of
Ix p. 5]) cannot be paid inside the payment: the cost is paid, the box's
automatic icons with it, and the arrow's right side waits under a hold until
the decision's window -- and whatever it opens -- is answered
(``rules.unload``). These tests mark cards already in the deck as Unload
cards with a Freighter box (``_marked``); the Freighter Fleet card's own data
has its own tests.
"""

import json
from collections.abc import Iterator
from dataclasses import replace

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec, action_codec
from dune_imperium.agents.agent_turn_steps import steps_after
from dune_imperium.core import (
    ChanceDecision,
    ChanceResolver,
    DomainAction,
    GameState,
    PlayerDecision,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine, unload
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.effect_steps import first_step
from dune_imperium.rules.frames import FrameKind, is_unload_hold
from dune_imperium.simulation.invariants import check_observation_privacy

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, first_player_seat_zero=True
)
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
TRUTHSAYER = "imperium:truthsayer:0"
JAMIS = "imperium:jamis:0"
SHAI_HULUD = "imperium:shai_hulud:0"
MOHIAM = "imperium:reverend_mother_mohiam:0"
INITIATE = "imperium:bene_gesserit_initiate:0"
PROBE = "intrigue:ixian_probe:0"
CHOAM_DELEGATE = "imperium:choam_delegate:0"
# Marked as Unload cards whose box is one Freighter icon.
MARKED = ("imperium:sayyadina:0", "imperium:truthsayer:1")
FREIGHTER_ROWS = {"advance_freighter", "recall_freighter", "decline_freighter"}
TEST_PAYER = "test_unload_hold"


@unload.hold_payer(TEST_PAYER)
def _test_payer(state: GameState, player: int, values: object) -> RuleResult:
    """A hand-built path's right side: the Solari it names."""

    assert isinstance(values, dict)
    owner = state.players[player]
    paid = replace(
        owner,
        resources=replace(
            owner.resources, solari=owner.resources.solari + int(values["solari"])
        ),
    )
    return RuleResult(
        state=replace(
            state,
            players=(*state.players[:player], paid, *state.players[player + 1 :]),
        ),
        events=(
            GameEvent(
                event_id="test:right_side",
                kind="resources_gained",
                payload=(("player", player), ("solari", int(values["solari"]))),
            ),
        ),
    )


@pytest.fixture
def _marked(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """``MARKED`` give a Freighter icon when discarded or trashed; the
    catalog is rebuilt with their rows, and rebuilt again without them."""

    def icons(card_id: str) -> tuple[tuple[str, int], ...]:
        return ((unload.FREIGHTER_ICON, 1),) if card_id in MARKED else ()

    monkeypatch.setattr(unload, "unload_icons", icons)
    monkeypatch.setattr(action_codec, "unload_icons", icons)
    action_codec._catalog_of.cache_clear()
    yield
    action_codec._catalog_of.cache_clear()


def _rows(state: GameState, seat: int = 0) -> tuple[DomainAction, ...]:
    codec = ActionCodec(IX)
    rows = ENGINE.legal_actions(state, seat)
    for row in rows:
        assert codec.decode(codec.encode(row), seat) == row
    return rows


def _row_ids(state: GameState, seat: int = 0) -> set[str]:
    return {row.action_id for row in _rows(state, seat)}


def _give(state: GameState, seat: int, **zones: tuple[str, ...]) -> GameState:
    named = {card for cards in zones.values() for card in cards}
    players = []
    for player in state.players:
        cleaned = replace(
            player,
            deck=tuple(c for c in player.deck if c not in named),
            hand=tuple(c for c in player.hand if c not in named),
            discard_pile=tuple(c for c in player.discard_pile if c not in named),
            in_play=tuple(c for c in player.in_play if c not in named),
        )
        if player.player_id == seat:
            cleaned = replace(cleaned, **zones)  # type: ignore[arg-type]
        players.append(cleaned)
    return replace(
        state,
        players=tuple(players),
        imperium_deck=tuple(c for c in state.imperium_deck if c not in named),
        imperium_row=tuple(c for c in state.imperium_row if c not in named),
    )


def _seat(state: GameState, seat: int, **fields: object) -> GameState:
    owner = replace(state.players[seat], **fields)  # type: ignore[arg-type]
    return replace(
        state, players=(*state.players[:seat], owner, *state.players[seat + 1 :])
    )


def _start(seed: int = 3) -> GameState:
    state = ENGINE.reset(IX, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _do(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> RuleResult:
    whole = next(
        row
        for row in ENGINE.whole_actions(state, seat)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    events: list[GameEvent] = []
    while True:
        rows = _rows(state, seat)
        left = 0 if whole in rows else steps_after(state, whole)
        row = whole if whole in rows else first_step(state, whole)
        assert row in rows
        result = ENGINE.apply(state, row)
        events.extend(result.events)
        state = result.state
        if left == 0:
            return RuleResult(state=state, events=tuple(events))


def _kinds(events: tuple[GameEvent, ...]) -> list[str]:
    return [event.kind for event in events]


def _holds(state: GameState) -> list[int]:
    return [
        index
        for index, frame in enumerate(state.decision_stack)
        if is_unload_hold(frame)
    ]


def _truthsayer_paid(state: GameState, discarded: str) -> tuple[GameState, RuleResult]:
    """Seat 0's Truthsayer on Wealth, "[Discard] -> [draw 1 card]", paid
    with ``discarded``; returns the state before the payment and its result."""

    kept = state.players[0].hand[0]
    state = _give(state, 0, hand=(TRUTHSAYER, discarded, kept))
    state = _do(state, "choose_agent_card", card_id=TRUTHSAYER).state
    state = _do(state, "place_agent", space_id="wealth").state
    return state, _do(state, "discard_agent_card", card_id=discarded)


# --- A discard cost --------------------------------------------------------------


@pytest.mark.usefixtures("_marked")
def test_a_discard_cost_holds_the_draw_until_the_freighter_is_decided() -> None:
    """ "Unload를 끝까지 해결한 뒤 오른쪽으로 간다" (rise-of-ix.md 7): the
    discard is paid, its Freighter's window opens above the hold, and the
    draw waits; while it is open its rows are the seat's only ones -- no turn
    end, no other effect."""
    before, paid = _truthsayer_paid(_start(), MARKED[0])
    state = paid.state
    owner = state.players[0]
    assert MARKED[0] in owner.discard_pile
    assert len(owner.hand) == len(before.players[0].hand) - 1
    assert "card_unloaded" in _kinds(paid.events)
    assert "agent_card_effect_resolved" not in _kinds(paid.events)
    assert state.decision_stack[-1].kind is FrameKind.FREIGHTER_MOVE
    assert _holds(state) == [len(state.decision_stack) - 2]
    assert state.decision_stack[-3].kind is FrameKind.AGENT_EFFECTS
    assert _row_ids(state) == {"advance_freighter", "decline_freighter"}
    for seat in (1, 2, 3):
        assert not _rows(state, seat)
    check_observation_privacy(state)
    moved = _do(state, "advance_freighter")
    after = moved.state
    assert after.players[0].freighter_space == 1
    assert len(after.players[0].hand) == len(owner.hand) + 1
    assert not _holds(after)
    kinds = _kinds(moved.events)
    assert kinds.index("freighter_moved") < kinds.index("agent_card_effect_resolved")
    assert after.decision_stack[-1].kind is FrameKind.AGENT_EFFECTS
    check_observation_privacy(after)


@pytest.mark.usefixtures("_marked")
def test_a_recall_inside_the_hold_opens_its_rewards_window_first() -> None:
    """Inside the hold the Freighter's recall rewards do not wait on the turn
    (where the right side could be taken before them): they open their own
    window above the hold (``turn_rows.waits_on_turn``), and the draw comes
    only after them."""
    state = _seat(_start(), 0, freighter_space=1)
    _, paid = _truthsayer_paid(state, MARKED[0])
    state = paid.state
    hand = len(state.players[0].hand)
    recalled = _do(state, "recall_freighter").state
    assert recalled.decision_stack[-1].kind is FrameKind.SHIPPING_REWARD_ICONS
    assert _holds(recalled)
    assert len(recalled.players[0].hand) == hand
    assert not _row_ids(recalled) & {"finish_agent_turn", "resolve_unload_icon"}
    spice = recalled.players[0].resources.spice
    rewarded = _do(recalled, "resolve_shipping_reward", effect="spice")
    after = rewarded.state
    assert after.players[0].resources.spice == spice + 2
    assert len(after.players[0].hand) == hand + 1
    assert not _holds(after)


@pytest.mark.usefixtures("_marked")
def test_two_discards_hold_once_for_both_freighters() -> None:
    """Ixian Probe's "Discard, Discard -> draw 2 cards" (an Intrigue cost
    piece, ``ability_executor``): the first discard holds the second piece
    and the draw; the second pick follows the Freighter's answer."""
    state = _start()
    kept = state.players[0].hand[0]
    state = replace(
        state, intrigue_deck=tuple(c for c in state.intrigue_deck if c != PROBE)
    )
    state = _seat(
        _give(state, 0, hand=(MARKED[0], MARKED[1], kept)), 0, intrigue_cards=(PROBE,)
    )
    state = _do(state, "play_intrigue", card_id=PROBE, option=0).state
    first = _do(state, "choose_intrigue_discard", card_id=MARKED[0]).state
    assert first.decision_stack[-1].kind is FrameKind.FREIGHTER_MOVE
    assert _row_ids(first) == {"advance_freighter", "decline_freighter"}
    first = _do(first, "decline_freighter").state
    assert not _holds(first)
    assert {
        dict(row.arguments)["card_id"]
        for row in ENGINE.whole_actions(first, 0)
        if row.action_id == "choose_intrigue_discard"
    } == {MARKED[1], kept}
    second = _do(first, "choose_intrigue_discard", card_id=MARKED[1])
    assert "cards_drawn" not in _kinds(second.events)
    state = second.state
    assert state.decision_stack[-1].kind is FrameKind.FREIGHTER_MOVE
    hand = len(state.players[0].hand)
    done = _do(state, "advance_freighter").state
    assert len(done.players[0].hand) == hand + 2
    assert not _holds(done)


# --- A trash cost ----------------------------------------------------------------


@pytest.mark.usefixtures("_marked")
def test_a_trash_cost_holds_what_it_buys() -> None:
    """Shai-Hulud's "[Trash a card] -> [2 troops]": the troops wait until
    the trashed card's Freighter is answered, even by its "may" decline."""
    state = _give(_start(), 0, hand=(SHAI_HULUD, MARKED[0]))
    state = _do(state, "choose_agent_card", card_id=SHAI_HULUD).state
    state = _do(state, "place_agent", space_id="imperial_basin").state
    garrison = state.players[0].troops_garrison
    trashed = _do(state, "trash_agent_card", card_id=MARKED[0])
    state = trashed.state
    assert MARKED[0] in state.players[0].trashed
    assert state.players[0].troops_garrison == garrison
    assert _row_ids(state) == {"advance_freighter", "decline_freighter"}
    declined = _do(state, "decline_freighter")
    assert declined.state.players[0].troops_garrison == garrison + 2
    kinds = _kinds(declined.events)
    assert kinds.index("freighter_declined") < kinds.index("agent_card_effect_resolved")
    assert not _holds(declined.state)


# --- Boxes without a decision ----------------------------------------------------


def test_a_box_without_a_decision_is_still_paid_inside_the_payment() -> None:
    """CHOAM Delegate's "[3 Solari]" needs no decision: no hold, the Solari
    before the draw in the one payment, as before."""
    before, paid = _truthsayer_paid(_start(), CHOAM_DELEGATE)
    assert not _holds(paid.state)
    assert paid.state.decision_stack[-1].kind is FrameKind.AGENT_EFFECTS
    assert paid.state.players[0].resources.solari == (
        before.players[0].resources.solari + 3
    )
    event = next(event for event in paid.events if event.kind == "card_unloaded")
    assert dict(event.payload) == {
        "card_id": CHOAM_DELEGATE,
        "pending": False,
        "player": 0,
    }


# --- Effects, not costs ----------------------------------------------------------


@pytest.mark.usefixtures("_marked")
def test_an_effect_s_freighter_waits_as_a_may_row_of_the_turn() -> None:
    """Jamis' "Trash a card", an effect in the owner's own turn: the
    Freighter waits as a row of the turn that opens its window; "may"
    [Rise of Ix p. 5], it holds no turn end back and lapses at the press
    (OQ-095 (2))."""
    state = _give(_start(), 0, hand=(JAMIS, MARKED[0]))
    state = _do(state, "choose_agent_card", card_id=JAMIS).state
    state = _do(state, "place_agent", space_id="stillsuits").state
    state = _do(state, "trash_agent_card", card_id=MARKED[0]).state
    assert not _holds(state)
    state = _do(state, "resolve_board_effect", effect="resources").state
    state = _do(state, "resolve_faction_influence").state
    assert "resolve_unload_icon" in _row_ids(state)
    assert any(
        row.action_id == "finish_agent_turn" for row in ENGINE.whole_actions(state, 0)
    )
    opened = _do(state, "resolve_unload_icon", card_id=MARKED[0], effect="freighter")
    assert opened.state.decision_stack[-1].kind is FrameKind.FREIGHTER_MOVE
    finished = _do(state, "finish_agent_turn")
    lapsed = next(e for e in finished.events if e.kind == "unload_icon_lapsed")
    assert dict(lapsed.payload) == {
        "card_id": MARKED[0],
        "effect": "freighter",
        "player": 0,
    }


@pytest.mark.usefixtures("_marked")
def test_an_opponent_s_discard_opens_the_owner_s_freighter_window() -> None:
    """ "남의 효과로 버려져도 된다" (rise-of-ix.md 7): outside its owner's turn
    the Freighter opens seat 1's own window, which closes back to the
    discard it came from."""
    state = _start()
    other = state.players[1].hand[0]
    state = _give(state, 0, hand=(MOHIAM,), in_play=(INITIATE,))
    state = _give(state, 1, hand=(MARKED[0], other))
    state = _do(state, "choose_agent_card", card_id=MOHIAM).state
    state = _do(state, "place_agent", space_id="secrets").state
    state = _do(state, "resolve_agent_card_effect").state
    state = _do(state, "discard_opponent_card", seat=1, card_id=MARKED[0]).state
    top = state.decision_stack[-1]
    assert top.kind is FrameKind.FREIGHTER_MOVE
    assert isinstance(top.decision, PlayerDecision) and top.decision.owner == 1
    assert not _holds(state)
    state = _do(state, "advance_freighter", seat=1).state
    assert state.players[1].freighter_space == 1
    assert state.decision_stack[-1].kind is FrameKind.OPPONENT_CARD_DISCARD


# --- Outside its owner's turn ----------------------------------------------------


@pytest.mark.usefixtures("_marked")
def test_a_hold_outside_its_owner_s_turn_closes_back_to_the_frame_below() -> None:
    """A cost paid outside the owner's turn (here built by hand during
    Combat): the hold and its window are the owner's; answering them pays
    the right side and returns to the frame below, another seat's, which no
    other step reordered."""
    state = _give(_start(), 1, hand=(MARKED[0],))
    state = replace(state, phase=GamePhase.COMBAT)
    below = state.decision_stack[-1]
    paid = discard_personal_card_from_hand(
        state, 1, MARKED[0], source="test:cost", unload_at_once=True
    )
    assert unload.unload_holds(paid.events)
    held = unload.push_unload_hold(
        paid.state, 1, source="test:cost", payer=TEST_PAYER, values={"solari": 2}
    )
    settled = unload.settle_unloads(RuleResult(state=held, events=paid.events)).state
    assert [frame.kind for frame in settled.decision_stack[-3:]] == [
        below.kind,
        FrameKind.UNLOAD_ICONS,
        FrameKind.FREIGHTER_MOVE,
    ]
    assert _row_ids(settled, 1) == {"advance_freighter", "decline_freighter"}
    assert not _rows(settled, 0)
    solari = settled.players[1].resources.solari
    closed = ENGINE.apply(settled, DomainAction("decline_freighter", 1))
    assert closed.state.players[1].resources.solari == solari + 2
    assert closed.state.decision_stack[-1] == below
    assert "test:right_side" in [event.event_id for event in closed.events]


# --- Save, load and undo -------------------------------------------------------


def _replayed(start: GameState, steps: tuple[DomainAction, ...]) -> GameState:
    """A save is the game's steps from its start (``core.replay``); loading
    replays them. Here the start is a hand-built state."""

    state = start
    for step in steps:
        state = ENGINE.apply(state, step).state
    return state


def _steps_of(
    state: GameState, action_id: str, seat: int = 0, **arguments: object
) -> tuple[GameState, tuple[DomainAction, ...]]:
    """Take one whole action by its steps; return the state and the steps."""

    whole = next(
        row
        for row in ENGINE.whole_actions(state, seat)
        if row.action_id == action_id
        and all(
            dict(row.arguments).get(key) == value for key, value in arguments.items()
        )
    )
    steps: list[DomainAction] = []
    while True:
        rows = ENGINE.legal_actions(state, seat)
        row = whole if whole in rows else first_step(state, whole)
        left = 0 if whole in rows else steps_after(state, whole)
        steps.append(row)
        state = ENGINE.apply(state, row).state
        if left == 0:
            return state, tuple(steps)


@pytest.mark.usefixtures("_marked")
def test_save_load_and_undo_keep_the_held_right_side_once() -> None:
    """Saved and loaded (the steps replayed) inside the hold, the state is
    the same and finishing it pays the draw once; taking the opening step
    back (an undo replays the steps before it) leaves no hold, and taking
    it again opens the same one. The hold's values are plain JSON."""
    start = _start()
    kept = start.players[0].hand[0]
    start = _give(start, 0, hand=(TRUTHSAYER, MARKED[0], kept))
    state, picked = _steps_of(start, "choose_agent_card", card_id=TRUTHSAYER)
    state, placed = _steps_of(state, "place_agent", space_id="wealth")
    before = state
    held, opening = _steps_of(state, "discard_agent_card", card_id=MARKED[0])
    steps = (*picked, *placed, *opening)
    loaded = _replayed(start, steps)
    assert canonical_state_hash(loaded) == canonical_state_hash(held)
    (hold,) = (held.decision_stack[index] for index in _holds(held))
    values = dict(hold.context)["unload_hold_values"]
    assert isinstance(values, str) and json.loads(values) == {"card_id": MARKED[0]}
    finished, answer = _steps_of(loaded, "advance_freighter")
    assert len(finished.players[0].hand) == len(held.players[0].hand) + 1
    assert canonical_state_hash(_replayed(start, (*steps, *answer))) == (
        canonical_state_hash(finished)
    )
    assert not _holds(finished)
    assert not any(row.action_id == "resolve_unload_icon" for row in _rows(finished))
    undone = _replayed(start, (*picked, *placed))
    assert canonical_state_hash(undone) == canonical_state_hash(before)
    assert not _holds(undone)
    again, _ = _steps_of(undone, "discard_agent_card", card_id=MARKED[0])
    assert canonical_state_hash(again) == canonical_state_hash(held)


def test_every_cost_path_registers_its_payer() -> None:
    """The cost paths whose right side is paid in their own step register a
    payer (the others' right side already waits under the hold as a row)."""
    assert {
        "agent_box_discard",
        "agent_box_trash",
        "agent_box_discard_pay",
        "agent_box_graft_trash",
        "intrigue_choice",
        "tech_flip_discard",
    } <= set(unload._PAYERS)
