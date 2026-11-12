"""An Arrakeen Scouts choice must not tell the table what a hidden hand holds
(hidden-information sweep of 2026-11-11, finding 1,
docs/reviews/2026-11-hidden-info-sweep.md; fixed by the user's decision of
2026-11-11 "(가)", OQ-071).

docs/rules/information-visibility.md: "일반 hand의 identity는 소유자만 보고,
장수는 전원에게 공개한다." and, of OQ-010 ruling 6, "각 좌석의 **덱과 숨은
손패를 합친 카드 구성**(어떤 카드가 몇 장)은 전원에게 공개한다 ... 어느 카드가
덱이고 어느 카드가 손패인지, 어느 사본인지는 비공개다".

The original game's Scouts events Desert Gift ("시작 카드 ... 가 아닌 카드 1장
버리기 → Fremen +1, 또는 패스") and No Coming Back (trash a starting card from
hand) offer a line only while the seat's hand holds a card of the kind its
cost names (``scouts_effects.option_is_affordable``, ``HandCardFilter``).
Before the fix a seat with no such line was asked with the prompt "Nothing in
this Arrakeen Scouts item can be taken" and the one answer
``resolve_scouts_choice_without_option`` (event ``scouts_choice_skipped``),
and a seat with one with "Choose an Arrakeen Scouts option or pass" and the
answer ``scouts_pass`` (event ``scouts_choice_passed``): the prompt is in the
public summary every client reads, and the answer in every seat's log, so
both told the table whether the hand held such a card. Now both seats get
the pass and the same wording (``scouts_effects.legal_scouts_choice_actions``).

Two twins differ only in which of seat 1's pool cards lie in its hand and
which in its deck: the same pool, hand size and deck size. The one change
made outside the rules is those cards, taken off the Imperium deck.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

import pytest

from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.scouts_effects import offer_scouts_choice
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.sessions import GameSessionManager

SEAT = 1
OTHERS = (0, 2, 3)
ADMIN_KEY = "scouts-choice-hidden-hand-key"
ADMIN = Credentials(admin_key=ADMIN_KEY)


@dataclass(frozen=True)
class _Table:
    manager: GameSessionManager
    game_id: str
    seats: dict[int, Credentials]


def _table() -> _Table:
    """A remote original + Scouts table, four claimed seats, played by first
    legal answers up to the first Agent turn: every hand is dealt."""

    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    summary = manager.create_game(
        ("human",) * 4,
        base_game="imperium",
        arrakeen_scouts=True,
        game_seed=5,
        credentials=ADMIN,
    )
    game_id = str(summary["game_id"])
    seats = {
        seat: Credentials(
            seat_tokens=frozenset({manager.claim_seat(game_id, seat, f"P{seat}").token})
        )
        for seat in range(4)
    }
    session = manager._get(game_id)
    engine = session.engine
    while not all(len(player.hand) == 5 for player in session.state.players):
        state = session.state
        seat = session.awaiting_confirmation
        if seat is not None:
            manager.confirm_turn(
                game_id,
                seat,
                state.revision,
                undo_count=session.undo_count,
                credentials=seats[seat],
            )
            continue
        decision = engine.current_decision(state)
        assert isinstance(decision, PlayerDecision)
        manager.apply_action(
            game_id,
            decision.owner,
            state.revision,
            0,
            undo_count=session.undo_count,
            credentials=seats[decision.owner],
        )
    return _Table(manager, game_id, seats)


def _twins(state: GameState, item: str) -> tuple[GameState, GameState]:
    """Seat 1's pool with Imperium cards in it, laid out two ways, and the
    item's choice opened for seat 1 on top.

    Desert Gift (a card that is not a starting card): one Imperium card in
    the deck, or in the hand. No Coming Back (a starting card): a hand of
    five Imperium cards, or of four and a starting card.
    """

    player = state.players[SEAT]
    hand, deck = player.hand, player.deck
    if item == "desert_gift":
        taken = state.imperium_deck[:1]
        card = taken[0]
        placed = (
            replace(player, deck=(card, *deck[1:])),
            replace(player, hand=(card, *hand[1:]), deck=(hand[0], *deck[1:])),
        )
    else:
        taken = state.imperium_deck[:5]
        placed = (
            replace(player, hand=taken, deck=(*hand, *deck)),
            replace(
                player, hand=(*taken[:4], hand[0]), deck=(taken[4], *hand[1:], *deck)
            ),
        )
    twins = []
    for seat_state in placed:
        players = list(state.players)
        players[SEAT] = seat_state
        twin = replace(
            state,
            players=tuple(players),
            imperium_deck=state.imperium_deck[len(taken) :],
        )
        source = f"round:{twin.round_number}:scouts:{item}:{SEAT}"
        twins.append(offer_scouts_choice(twin, SEAT, item, source=source).state)
    return twins[0], twins[1]


@dataclass(frozen=True)
class _Seen:
    """What the table outside seat 1 is served before and after its answer."""

    prompt: object
    answers: tuple[str, ...]
    after: tuple[object, ...]


def _compared(payload: Mapping[str, object]) -> dict[str, object]:
    """``payload`` without what two tables differ in whatever they hold: the
    room's random id and the play clock's wall-clock times."""

    return {key: value for key, value in payload.items() if key not in _UNCOMPARED}


_UNCOMPARED = frozenset({"game_id", "clock"})


def _seen(item: str, twin_index: int) -> tuple[_Seen, bool]:
    table = _table()
    manager, game_id = table.manager, table.game_id
    session = manager._get(game_id)
    twin = _twins(session.state, item)[twin_index]
    session.state = twin
    has_line = any(
        action.action_id == "scouts_choose_option"
        for action in session.engine.whole_actions(twin, SEAT)
    )
    # The public summary: any client holding the room link reads it.
    served = manager.summary(game_id)["decision"]
    assert isinstance(served, dict) and served["owner"] == SEAT
    actions = manager.legal_actions(game_id, SEAT, credentials=table.seats[SEAT])
    rows = actions["actions"]
    assert isinstance(rows, list)
    # What the seat answers when it takes nothing: every seat reads the
    # action id of that step in its log.
    answers = tuple(
        str(row["action_id"])
        for row in rows
        if isinstance(row, dict) and row["action_id"] != "scouts_choose_option"
    )
    passes = [
        row
        for row in rows
        if isinstance(row, dict) and row["action_id"] == "scouts_pass"
    ]
    assert len(passes) == 1
    logged = len(session.log)
    manager.apply_action(
        game_id,
        SEAT,
        session.state.revision,
        int(str(passes[0]["index"])),
        undo_count=session.undo_count,
        credentials=table.seats[SEAT],
    )
    after: list[object] = [_compared(manager.summary(game_id))]
    for seat in OTHERS:
        credentials = table.seats[seat]
        after.append(_compared(manager.view(game_id, seat, credentials=credentials)))
        after.append(
            _compared(manager.log(game_id, seat, after=logged, credentials=credentials))
        )
    return _Seen(served["prompt"], answers, tuple(after)), has_line


@pytest.mark.parametrize("item", ["desert_gift", "no_coming_back"])
def test_a_scouts_choice_shows_the_table_nothing_of_the_hand(item: str) -> None:
    # The twins look alike from every other seat: pool, hand and deck sizes.
    table = _table()
    engine = table.manager._get(table.game_id).engine
    in_deck, in_hand = _twins(table.manager._get(table.game_id).state, item)
    for seat in OTHERS:
        assert engine.observe(in_deck, seat) == engine.observe(in_hand, seat)

    (without, without_line), (holding, holding_line) = _seen(item, 0), _seen(item, 1)
    # Seat 1 can take the line in exactly one twin.
    assert (without_line, holding_line) == (False, True)
    assert without.prompt == holding.prompt == (
        "Choose an Arrakeen Scouts option or pass"
    )
    assert without.answers == holding.answers == ("scouts_pass",)
    # Its pass reads the same to the table: the summary, and every other
    # seat's view and log.
    assert without.after == holding.after
