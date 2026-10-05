"""A seat sees the composition of its own draw deck, never its order.

User decision 2026-10-05, under OQ-010's re-check principle (project
convention, not an official rule): every card reaches a personal deck
through zones its owner sees (the starting deck, the discard pile reshuffled
[Main pp. 5-6], acquisitions [Main p. 13], Tleilaxu cards put on top by
choice), so what the deck holds is something the owner can already deduce
and listing it reveals nothing new. The deck's order stays hidden
(``docs/rules/information-visibility.md``).

The list rides only in the observing seat's own ``private`` block as
``deck_cards``, sorted by card id, so these tests pin: it equals the owner's
sorted deck through reshuffles and draws; it cannot encode the order; and
no other view, log or summary changes when another seat's deck does.
"""

from __future__ import annotations

import json
import random
from collections.abc import Mapping
from dataclasses import replace

import pytest

from dune_imperium.core import GamePhase, GameState
from dune_imperium.rules.frames import replace_player
from dune_imperium.server.access import ANONYMOUS, AccessMode, Credentials
from dune_imperium.server.sessions import (
    GameSessionManager,
    SeatAccessError,
    _serialize_view,
    _state_after,
)

FOUR_HUMANS = ("human", "human", "human", "human")
ALL_AI = ("heuristic", "heuristic", "heuristic", "heuristic")
ADMIN_KEY = "deck-contents-admin-key"


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _ints(value: object) -> int:
    assert isinstance(value, int)
    return value


def _deck_cards(view: Mapping[str, object]) -> list[str]:
    cards = _obj(view["private"])["deck_cards"]
    assert isinstance(cards, list)
    assert all(isinstance(card, str) for card in cards)
    return [str(card) for card in cards]


def _step(manager: GameSessionManager, game_id: str, rng: random.Random) -> bool:
    """Let whoever decides take a random legal action; False when finished."""

    summary = manager.summary(game_id)
    if summary["finished"]:
        return False
    revision = _ints(summary["revision"])
    held = summary["confirmation"]
    if isinstance(held, int):
        manager.confirm_turn(game_id, held, revision)
        return True
    owner = _ints(_obj(summary["decision"])["owner"])
    actions = manager.legal_actions(game_id, owner)["actions"]
    assert isinstance(actions, list) and actions
    chosen = _obj(rng.choice(actions))
    manager.apply_action(game_id, owner, revision, _ints(chosen["index"]))
    return True


def _reshuffles(state: GameState) -> int:
    return sum(
        1 for event in state.event_log if event.kind == "personal_discard_shuffled"
    )


def _with_deck(state: GameState, seat: int, deck: tuple[str, ...]) -> GameState:
    return replace(
        state,
        players=replace_player(state.players, replace(state.players[seat], deck=deck)),
    )


def _midgame(seed: int = 5, steps: int = 60) -> tuple[GameSessionManager, str]:
    """Walk a four-human game at random until every seat's deck holds at
    least three cards (so each deck has an order to differ in)."""

    manager = GameSessionManager()
    game_id = str(manager.create_game(FOUR_HUMANS, game_seed=seed)["game_id"])
    session = manager._get(game_id)
    rng = random.Random(seed)
    for taken in range(800):
        if taken >= steps and all(len(p.deck) >= 3 for p in session.state.players):
            return manager, game_id
        assert _step(manager, game_id, rng)
    raise AssertionError("no state with a deck of three cards at every seat")


# --- (a) the owner's list is the sorted multiset of its deck --------------


def test_the_owner_sees_the_sorted_deck_through_draws_and_reshuffles() -> None:
    manager = GameSessionManager()
    game_id = str(manager.create_game(FOUR_HUMANS, game_seed=5)["game_id"])
    session = manager._get(game_id)
    rng = random.Random(5)
    sizes: list[int] = []
    for _ in range(400):
        state = session.state
        for seat in range(4):
            view = manager.view(game_id, seat)
            assert _deck_cards(view) == sorted(state.players[seat].deck)
            assert _obj(view["private"])["deck_size"] == len(_deck_cards(view))
        sizes.append(len(state.players[0].deck))
        if _reshuffles(state) >= 3 and any(
            later > earlier for earlier, later in zip(sizes, sizes[1:], strict=False)
        ):
            break
        assert _step(manager, game_id, rng)
    # The walk really crossed a reshuffle (the deck grew) and draws (it shrank).
    assert _reshuffles(session.state) >= 3
    assert any(
        later > earlier for earlier, later in zip(sizes, sizes[1:], strict=False)
    )
    assert any(
        later < earlier for earlier, later in zip(sizes, sizes[1:], strict=False)
    )


def test_the_snapshot_and_a_review_step_carry_the_same_list() -> None:
    manager, game_id = _midgame()
    state = manager._get(game_id).state
    for seat in range(4):
        snapshot_view = _obj(manager.snapshot(game_id, seat)["view"])
        assert _deck_cards(snapshot_view) == sorted(state.players[seat].deck)

    # A finished game's review shows the reviewed seat's list at that step.
    finished = GameSessionManager()
    finished_id = str(finished.create_game(ALL_AI, game_seed=13)["game_id"])
    session = finished._get(finished_id)
    assert session.state.phase is GamePhase.FINISHED
    for step in (0, len(session.steps) // 2, len(session.steps)):
        at_step = _state_after(session, step)
        reviewed = _obj(finished.review_state(finished_id, 2, step)["view"])
        assert _deck_cards(reviewed) == sorted(at_step.players[2].deck)


# --- (b) the order cannot be read off the list ----------------------------


@pytest.mark.parametrize("seed", [1, 5, 9])
def test_states_differing_only_in_deck_order_serialize_identically(seed: int) -> None:
    manager, game_id = _midgame(seed=seed)
    session = manager._get(game_id)
    state = session.state
    for seat in range(4):
        deck = state.players[seat].deck
        assert len(deck) >= 2, "the walk must leave a deck whose order can differ"
        baseline = _serialize_view(session.engine.observe(state, seat), state)
        orders = [
            tuple(reversed(deck)),
            (*deck[1:], deck[0]),
            tuple(random.Random(seed + seat).sample(deck, len(deck))),
        ]
        for order in orders:
            if order == deck:
                continue
            variant = _with_deck(state, seat, order)
            assert variant.players[seat].deck != deck
            serialized = _serialize_view(session.engine.observe(variant, seat), variant)
            assert _deck_cards(serialized) == _deck_cards(baseline)
            # Stronger: nothing else in the owner's view moved either.
            assert serialized == baseline


# --- (c) nobody else gets it ----------------------------------------------


def test_no_other_view_log_or_summary_depends_on_a_seats_deck() -> None:
    manager, game_id = _midgame()
    session = manager._get(game_id)
    original = session.state
    owner = 0
    deck = original.players[owner].deck
    assert deck, "the walk must leave the owner a deck"
    # Same size (the count is public), different cards: only seat 0's own
    # private block may notice.
    swapped = original.imperium_deck[: len(deck)]
    assert len(swapped) == len(deck) and not set(swapped) & set(deck)
    changed = _with_deck(original, owner, swapped)

    def everything_but_the_owner() -> dict[str, object]:
        seen: dict[str, object] = {
            "summary": manager.summary(game_id),
            "seatless snapshot": manager.snapshot(game_id),
            "identify": manager.identify(game_id),
        }
        for seat in range(4):
            if seat == owner:
                continue
            seen[f"view {seat}"] = manager.view(game_id, seat)
            seen[f"snapshot {seat}"] = manager.snapshot(game_id, seat)
            seen[f"log {seat}"] = manager.log(game_id, seat)
        return seen

    session.state = original
    before = everything_but_the_owner()
    owner_before = manager.view(game_id, owner)
    session.state = changed
    after = everything_but_the_owner()
    owner_after = manager.view(game_id, owner)
    session.state = original

    assert after == before
    # The owner's own block is the one place the list lives.
    assert _deck_cards(owner_before) == sorted(deck)
    assert _deck_cards(owner_after) == sorted(swapped)
    assert _obj(owner_before)["players"] == _obj(owner_after)["players"], (
        "the public block of the owner shows no deck contents"
    )
    # In plain text, too: another seat's view and the public summary name none
    # of the owner's starter instance ids (they are per seat, and a card in
    # the deck is in no public zone of the same state). The logs are left out
    # of this scan: they may name a card from when it was played, before a
    # reshuffle put it back; the equality above covers them.
    starters = [card for card in deck if card.startswith(f"player:{owner}:starter:")]
    assert starters
    for name, payload in before.items():
        if name.startswith(("log", "snapshot")):
            continue
        text = json.dumps(payload)
        assert not [card for card in starters if card in text], name
    for seat in range(4):
        if seat != owner:
            text = json.dumps(_obj(before[f"snapshot {seat}"])["view"])
            assert not [card for card in starters if card in text], seat
    # The owner's private block is the only key that differs.
    private_before = _obj(owner_before["private"])
    private_after = _obj(owner_after["private"])
    assert {
        key for key in private_before if private_before[key] != private_after[key]
    } == {"deck_cards"}
    assert "deck_cards" not in json.dumps(
        {key: value for key, value in owner_before.items() if key != "private"}
    )


def test_remote_seats_cannot_reach_another_seats_list() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    admin = Credentials(admin_key=ADMIN_KEY)
    game_id = str(
        manager.create_game(FOUR_HUMANS, game_seed=5, credentials=admin)["game_id"]
    )
    tokens = {
        seat: manager.claim_seat(game_id, seat, f"P{seat}").token for seat in (0, 1)
    }
    seat_zero = Credentials(seat_tokens=frozenset({tokens[0]}))
    seat_one = Credentials(seat_tokens=frozenset({tokens[1]}))
    state = manager._get(game_id).state

    own = manager.view(game_id, 0, credentials=seat_zero)
    assert _deck_cards(own) == sorted(state.players[0].deck)

    for stranger in (seat_one, ANONYMOUS):
        with pytest.raises(SeatAccessError):
            manager.view(game_id, 0, credentials=stranger)
        with pytest.raises(SeatAccessError):
            manager.snapshot(game_id, 0, credentials=stranger)
    # What seat 1's holder (and a seatless visitor) can read has none of
    # seat 0's starter instance ids, and only the holder's own view has a list.
    starters = [
        card for card in state.players[0].deck if card.startswith("player:0:starter:")
    ]
    assert starters
    holder = manager.view(game_id, 1, credentials=seat_one)
    assert _deck_cards(holder) == sorted(state.players[1].deck)
    holder_text = json.dumps(holder)
    assert not [card for card in starters if card in holder_text]
    for payload in (
        manager.snapshot(game_id, credentials=seat_one),
        manager.snapshot(game_id, credentials=ANONYMOUS),
        manager.summary(game_id),
    ):
        text = json.dumps(payload)
        assert "deck_cards" not in text
        assert not [card for card in starters if card in text]
