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

The one exception to the hidden order is the top card a card effect shows
its owner (Glowglobes, section (d)); the owner's deck list marks it, and the
tests there pin that only the owner's payload ever names it.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections.abc import Mapping
from dataclasses import replace

import pytest

from dune_imperium.core import GamePhase, GameState
from dune_imperium.rules.frames import replace_player
from dune_imperium.server import sessions as sessions_module
from dune_imperium.server.access import ANONYMOUS, AccessMode, Credentials
from dune_imperium.server.sessions import (
    GameSessionManager,
    SeatAccessError,
    SessionError,
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


def _without_pools(value: object) -> object:
    """``value`` with every seat's ``deck_pool`` left out."""

    if isinstance(value, dict):
        return {
            key: _without_pools(item)
            for key, item in value.items()
            if key != "deck_pool"
        }
    if isinstance(value, list):
        return [_without_pools(item) for item in value]
    return value


def _pool(view: object, seat: int) -> list[str]:
    players = _obj(view)["players"]
    assert isinstance(players, list)
    pool = _obj(players[seat])["deck_pool"]
    assert isinstance(pool, list) and all(isinstance(card, str) for card in pool)
    # Card ids only: never an instance id, so no copy is placed.
    assert not [card for card in pool if ":" in str(card)]
    return [str(card) for card in pool]


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


def _freeze_play_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop the server's clock so two reads differ only by the state.

    A snapshot carries the play clock's age (``play_clock``), which grows
    between the two reads below whatever the deck holds.
    """

    frozen = time.monotonic()
    monkeypatch.setattr(sessions_module, "_monotonic", lambda: frozen)


def test_no_other_view_log_or_summary_depends_on_a_seats_deck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, game_id = _midgame()
    _freeze_play_clock(monkeypatch)
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
    # The deck in another order, and a hand card traded with a deck card:
    # nothing any seat sees changes, the owner's public block included.
    hand = original.players[owner].hand
    traded = replace(
        original,
        players=replace_player(
            original.players,
            replace(
                original.players[owner],
                deck=(*hand[:1], *reversed(deck[1:])),
                hand=(deck[0], *hand[1:]),
            ),
        ),
    )
    session.state = traded
    reordered = everything_but_the_owner()
    owner_reordered = manager.view(game_id, owner)
    session.state = original

    assert reordered == before
    assert _obj(owner_reordered)["players"] == _obj(owner_before)["players"]
    # Another deck composition shows in one field only: the owner's deck
    # pool, by card identity (OQ-010 ruling 6, user decision 2026-10-13).
    assert _without_pools(after) == _without_pools(before)
    assert _pool(owner_after, owner) != _pool(owner_before, owner)
    for seat in range(4):
        if seat != owner:
            assert _pool(after[f"view {seat}"], owner) == _pool(owner_after, owner)
    # The owner's own block is the one place the list of instances lives.
    assert _deck_cards(owner_before) == sorted(deck)
    assert _deck_cards(owner_after) == sorted(swapped)
    assert _without_pools(_obj(owner_before)["players"]) == _without_pools(
        _obj(owner_after)["players"]
    ), "the public block of the owner shows no deck contents but its pool"
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


# --- (d) Glowglobes: the one deck card below the top stays hidden ---------
#
# "| Glowglobes | 2 | Influence 1 선택 | 언제든 자기 덱 맨 위 카드를 볼 수 있다 |"
# (docs/rules/bloodlines.md, [Tech tile faces] [Bloodlines p. 7]). The engine
# puts that card in the owner's own ``private.peeked_card_id``
# (core/observation.py ``peeked_card_id``), and the client marks it in the
# owner's deck list (static/panels.js ``openDeckList``; a display convention
# on top of OQ-010 ruling 5, not a rule change). The list adds nothing the
# payload did not already carry, so these tests pin the payload: the owner
# sees the top card and nothing about the order below it, and no other
# reader -- another seat, a seatless spectator, a remote stranger, a review
# of the live game -- learns which card is on top.


def _give_glowglobes(state: GameState, seat: int) -> GameState:
    """Hand ``seat`` the Glowglobes tile from wherever it lies (a tile is in
    exactly one zone, core/state.py)."""

    players = state.players
    for other in range(len(players)):
        tiles = players[other].tech_ids
        if "glowglobes" in tiles:
            kept = tuple(tile for tile in tiles if tile != "glowglobes")
            players = replace_player(players, replace(players[other], tech_ids=kept))
    owner = players[seat]
    players = replace_player(
        players, replace(owner, tech_ids=(*owner.tech_ids, "glowglobes"))
    )
    return replace(
        state,
        tech_stacks=tuple(
            tuple(tile for tile in stack if tile != "glowglobes")
            for stack in state.tech_stacks
        ),
        tech_trash=tuple(tile for tile in state.tech_trash if tile != "glowglobes"),
        players=players,
    )


def _group(card: str) -> str:
    """A deck card's catalog card: copies of one card share it."""

    return re.sub(r"^player:\d+:starter:", "", card).rsplit(":", 1)[0]


def _glowglobes_midgame(
    *, access: AccessMode = AccessMode.OPEN
) -> tuple[GameSessionManager, str, dict[int, Credentials]]:
    """A Bloodlines + Tech game walked until every deck holds four cards,
    seat 0 then given Glowglobes. Remote games also seat holders 0 and 1."""

    remote = access is AccessMode.REMOTE
    manager = (
        GameSessionManager(access=access, admin_key=ADMIN_KEY)
        if remote
        else GameSessionManager()
    )
    game_id = str(
        manager.create_game(
            FOUR_HUMANS,
            bloodlines=True,
            tech_module=True,
            game_seed=7,
            credentials=Credentials(admin_key=ADMIN_KEY) if remote else ANONYMOUS,
        )["game_id"]
    )
    holders: dict[int, Credentials] = {}
    if remote:
        for seat in (0, 1):
            token = manager.claim_seat(game_id, seat, f"P{seat}").token
            holders[seat] = Credentials(seat_tokens=frozenset({token}))
    session = manager._get(game_id)
    if not remote:
        rng = random.Random(7)
        for _ in range(800):
            if all(len(player.deck) >= 4 for player in session.state.players):
                break
            assert _step(manager, game_id, rng)
    session.state = _give_glowglobes(session.state, 0)
    assert len(session.state.players[0].deck) >= 4
    return manager, game_id, holders


def test_glowglobes_owner_sees_the_top_card_and_nothing_below_it() -> None:
    manager, game_id, _ = _glowglobes_midgame()
    session = manager._get(game_id)
    state = session.state
    deck = state.players[0].deck
    view = manager.view(game_id, 0)
    private = _obj(view["private"])
    assert private["peeked_card_id"] == deck[0]
    assert deck[0] in _deck_cards(view)
    assert _deck_cards(view) == sorted(deck)
    assert _obj(manager.snapshot(game_id, 0)["view"])["private"] == private

    # Below the top: any order serializes the owner's view identically.
    baseline = _serialize_view(session.engine.observe(state, 0), state)
    below = deck[1:]
    for order in (
        tuple(reversed(below)),
        (*below[1:], below[0]),
        tuple(random.Random(3).sample(below, len(below))),
    ):
        if order == below:
            continue
        variant = _with_deck(state, 0, (deck[0], *order))
        assert _serialize_view(session.engine.observe(variant, 0), variant) == baseline

    # A different top card (same cards, so the same list) moves exactly one
    # field of the owner's view: the peeked card itself.
    swaps = [index for index in range(1, len(deck)) if deck[index] != deck[0]]
    assert swaps
    for index in swaps:
        swapped = list(deck)
        swapped[0], swapped[index] = swapped[index], swapped[0]
        variant = _with_deck(state, 0, tuple(swapped))
        changed = _serialize_view(session.engine.observe(variant, 0), variant)
        before, after = _obj(baseline["private"]), _obj(changed["private"])
        assert {key for key in before if before[key] != after[key]} == {
            "peeked_card_id"
        }
        assert after["peeked_card_id"] == deck[index]
        assert {key: value for key, value in changed.items() if key != "private"} == {
            key: value for key, value in baseline.items() if key != "private"
        }


def test_no_other_reader_learns_the_glowglobes_top_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, game_id, _ = _glowglobes_midgame()
    _freeze_play_clock(monkeypatch)
    session = manager._get(game_id)
    original = session.state
    deck = original.players[0].deck
    # A top card of another card (not just another copy), same multiset.
    index = next(i for i in range(1, len(deck)) if _group(deck[i]) != _group(deck[0]))
    swapped = list(deck)
    swapped[0], swapped[index] = swapped[index], swapped[0]
    changed = _with_deck(original, 0, tuple(swapped))

    def everything_but_the_owner() -> dict[str, object]:
        seen: dict[str, object] = {
            "summary": manager.summary(game_id),
            "seatless snapshot": manager.snapshot(game_id),
            "identify": manager.identify(game_id),
        }
        for seat in (1, 2, 3):
            seen[f"view {seat}"] = manager.view(game_id, seat)
            seen[f"snapshot {seat}"] = manager.snapshot(game_id, seat)
            seen[f"log {seat}"] = manager.log(game_id, seat)
        return seen

    session.state = original
    before = everything_but_the_owner()
    session.state = changed
    after = everything_but_the_owner()
    owner_after = manager.view(game_id, 0)
    session.state = original

    assert after == before
    assert _obj(owner_after["private"])["peeked_card_id"] == deck[index]
    # No other seat holds a peek of its own, and the owner's top card is in
    # no other reader's payload (the logs may name it from before a
    # reshuffle; the equality above covers them).
    for seat in (1, 2, 3):
        assert _obj(_obj(before[f"view {seat}"])["private"])["peeked_card_id"] == ""
    for top in (deck[0], deck[index]):
        for name, payload in before.items():
            if name.startswith("log"):
                continue
            seen = payload
            if name.startswith("snapshot"):
                seen = _obj(payload)["view"]
            assert top not in json.dumps(seen), name

    # The live game opens no review, for the owner's seat or any other: it is
    # refused because the game is not over (sessions.py _require_finished),
    # not for some other reason a broader SessionError would also accept.
    for seat in range(4):
        with pytest.raises(SessionError, match="opens after the game finishes"):
            manager.review_state(game_id, seat, 0)


def test_remote_strangers_cannot_reach_the_glowglobes_top_card() -> None:
    manager, game_id, holders = _glowglobes_midgame(access=AccessMode.REMOTE)
    state = manager._get(game_id).state
    top = state.players[0].deck[0]

    own = manager.view(game_id, 0, credentials=holders[0])
    assert _obj(own["private"])["peeked_card_id"] == top
    for stranger in (holders[1], ANONYMOUS):
        with pytest.raises(SeatAccessError):
            manager.view(game_id, 0, credentials=stranger)
        with pytest.raises(SeatAccessError):
            manager.snapshot(game_id, 0, credentials=stranger)
    holder = manager.view(game_id, 1, credentials=holders[1])
    assert _obj(holder["private"])["peeked_card_id"] == ""
    assert top not in json.dumps(holder)
    for payload in (
        manager.snapshot(game_id, credentials=holders[1]),
        manager.snapshot(game_id, credentials=ANONYMOUS),
        manager.summary(game_id),
    ):
        assert top not in json.dumps(payload)
