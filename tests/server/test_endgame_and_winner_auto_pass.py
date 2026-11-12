"""The server passes Endgame Intrigue and closes a sole winner's reward window
for a human seat that holds no Intrigue card and can do nothing else there.

User decision 2026-11-09 ("1. 둘 다"), after the Combat Intrigue pass of the
same day (``test_combat_intrigue_auto_pass.py``):

- Endgame: "Endgame Intrigue 카드는 게임 종료 시점에만 플레이할 수 있다.
  Endgame에 들어가면 먼저 각자 가진 Endgame Intrigue를 원하는 만큼 플레이하고
  해결한 뒤 최종 Victory Point를 비교한다." [Main p. 7] [Main p. 15]
  (docs/rules/combat-and-round-end.md 9). A seat with no Intrigue card, a
  public count, and no wild pair among its face-up Objective and Conflict
  cards can only pass; the server passes for it, sealed like a press, while
  its unit is closed.
- The winner's window: "승리 책략은 승자의 창(1위 보상과 같은 창)에서만, 보상
  아이콘과 원하는 순서로 낸다" [DI p. 12] [FAQ p. 4]
  (docs/rules/imperium-base.md, OQ-121). The original game's sole winner
  closes its reward window with "no more winning Intrigue" once its reward
  rows are resolved; a winner holding no Intrigue card has nothing to play,
  so the server presses the close. It ends the winner's reward unit, whose
  end then waits for the winner's turn-end press while its reward rows can
  be taken back, and an undo takes the close back with the row before it.

The positions are real: seeded random games played by the engine up to the
window, then only the seats' Intrigue hands (and once a won Conflict) edited,
the one change made outside the rules. A session starts from that position
(``engine.reset`` returns it, as ``test_combat_intrigue_auto_pass.py`` does).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.config import BaseGame
from dune_imperium.core import (
    ChanceDecision,
    DomainAction,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.rules.combat import winning_intrigue_window_is_open
from dune_imperium.rules.endgame import _battle_icon
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.session_log import (
    endgame_pass_without_choice,
    live_steps,
    winning_close_without_choice,
    winning_intrigue_close,
)
from dune_imperium.server.sessions import GameSession, GameSessionManager, JsonObject

FOUR_HUMANS = ("human", "human", "human", "human")
ENDGAME_PASS = "pass_endgame_intrigue"
# A Plot card: never playable at the Endgame or in a reward window
# [Imperium Politics card].
PLOT_CARD = "intrigue:imperium_politics:0"
ENGINE = UprisingRulesEngine()
ORIGINAL = RulesetConfig(base_game=BaseGame("imperium"))


def _walk_to(
    config: RulesetConfig, seed: int, found: Callable[[GameState, int], bool]
) -> GameState:
    """A seeded random game up to the first player decision ``found`` names."""

    state = ENGINE.reset(config, seed)
    resolver = ChanceResolver(seed=seed)
    rng = random.Random(seed)
    for _ in range(20_000):
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(ENGINE, state, resolver.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        if found(state, decision.owner):
            return state
        state = apply_whole(
            ENGINE, state, rng.choice(ENGINE.whole_actions(state, decision.owner))
        ).state
    raise AssertionError("the walk never met the decision")


def _top_kind(state: GameState) -> object:
    return state.decision_stack[-1].kind if state.decision_stack else None


# Original game, seed 14: round 4's Conflict, won by seat 3 alone, whose
# window prints a Victory Point and a resource row before its close.
WINNER_START = _walk_to(ORIGINAL, 14, winning_intrigue_window_is_open)
WINNER = 3
# Original game, seed 6: round 2's winner, seat 2, whose window prints an
# Influence of its choice and an Intrigue card draw before its close.
DRAWING_START = _walk_to(ORIGINAL, 6, winning_intrigue_window_is_open)
DRAWING_WINNER = 2
# Uprising, seed 3: the Endgame window, opened for the First Player.
ENDGAME_START = _walk_to(
    RulesetConfig(),
    3,
    lambda state, _seat: _top_kind(state) == FrameKind.ENDGAME_INTRIGUE,
)


def _with_hands(state: GameState, hands: dict[int, tuple[str, ...]]) -> GameState:
    """``state`` with each seat's Intrigue hand set to ``hands`` (its cards
    taken out of the deck, the cards it held put back)."""

    held = {card for cards in hands.values() for card in cards}
    returned = tuple(
        card
        for seat in hands
        for card in state.players[seat].intrigue_cards
        if card not in held
    )
    players = tuple(
        replace(
            player, intrigue_cards=hands.get(player.player_id, player.intrigue_cards)
        )
        for player in state.players
    )
    deck = tuple(card for card in state.intrigue_deck if card not in held)
    return replace(state, players=players, intrigue_deck=(*deck, *returned))


def _session_at(
    monkeypatch: pytest.MonkeyPatch, start: GameState
) -> tuple[GameSessionManager, str, GameSession]:
    """A four-human session standing at ``start``, advanced as after any step."""

    manager = GameSessionManager()
    summary = manager.create_game(
        FOUR_HUMANS,
        game_seed=0,
        base_game=str(start.config.base_game),
        leader_draft=False,
    )
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    assert not session.steps
    session.state = start
    monkeypatch.setattr(session.engine, "reset", lambda config, seed: start)
    with session.lock:
        manager._advance_locked(session)
    return manager, game_id, session


def _owner(session: GameSession) -> int:
    decision = ENGINE.current_decision(session.state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _effects(state: GameState, seat: int) -> list[object]:
    return [
        dict(action.arguments).get("effect") or action.action_id
        for action in ENGINE.whole_actions(state, seat)
    ]


def _press_index(
    manager: GameSessionManager, game_id: str, seat: int, index: int
) -> JsonObject:
    revision = manager.summary(game_id)["revision"]
    assert isinstance(revision, int)
    return manager.apply_action(game_id, seat, revision, index)


def _log(manager: GameSessionManager, game_id: str, seat: int) -> list[JsonObject]:
    entries = manager.log(game_id, seat)["entries"]
    assert isinstance(entries, list)
    return [entry for entry in entries if isinstance(entry, dict)]


# --- the winner's close ---------------------------------------------------


def test_the_winners_close_is_offered_only_after_its_rows() -> None:
    start = _with_hands(WINNER_START, {WINNER: ()})
    assert _owner_at(start) == WINNER
    assert _effects(start, WINNER) == ["victory_points", "resources"]
    assert not winning_close_without_choice(start, WINNER)


def _owner_at(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def test_the_server_closes_a_card_less_winners_window_and_holds_its_unit_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = _with_hands(WINNER_START, {WINNER: ()})
    manager, game_id, session = _session_at(monkeypatch, start)
    assert session.steps == []

    _press_index(manager, game_id, WINNER, 0)  # its Victory Point
    assert _effects(session.state, WINNER) == ["resources"]
    summary = _press_index(manager, game_id, WINNER, 0)  # its resources

    # The server pressed the close: the step and log entry the winner's own
    # press would make, logged as one it had no choice but to make.
    [*_, last] = live_steps(session.log)
    assert (last.whole or last.step) == winning_intrigue_close(WINNER)
    for viewer in range(4):
        entries = _log(manager, game_id, viewer)
        assert entries[-1]["without_choice"] is True
        assert [entry.get("without_choice", False) for entry in entries[:-1]] == [
            False,
            False,
        ]
    # Not sealed: the reward unit's end waits for the winner's turn-end
    # press, its two rows still to take back (a held unit end, not the
    # next recipient's decision).
    assert summary["confirmation"] == WINNER
    assert session.undo_floor == 0
    assert winning_intrigue_window_is_open(start, WINNER)
    assert not winning_intrigue_window_is_open(session.state, WINNER)


def test_an_undo_takes_the_servers_close_back_with_the_row_before_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = _with_hands(WINNER_START, {WINNER: ()})
    manager, game_id, session = _session_at(monkeypatch, start)
    _press_index(manager, game_id, WINNER, 0)
    _press_index(manager, game_id, WINNER, 0)
    assert len(session.steps) == 3

    revision = manager.summary(game_id)["revision"]
    assert isinstance(revision, int)
    manager.undo(game_id, WINNER, revision, 1)

    # One undo, two steps: the close went back with the resources row, so
    # the winner stands at its resources row again, not at a close the
    # server would press at once.
    assert len(session.steps) == 1
    assert _owner(session) == WINNER
    assert _effects(session.state, WINNER) == ["resources"]
    assert manager.summary(game_id)["confirmation"] is None
    # Pressed again, the row is followed by the server's close again.
    summary = _press_index(manager, game_id, WINNER, 0)
    [*_, last] = live_steps(session.log)
    assert (last.whole or last.step) == winning_intrigue_close(WINNER)
    assert summary["confirmation"] == WINNER


def test_the_turn_end_press_after_the_servers_close_hands_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = _with_hands(WINNER_START, {WINNER: ()})
    manager, game_id, session = _session_at(monkeypatch, start)
    _press_index(manager, game_id, WINNER, 0)
    summary = _press_index(manager, game_id, WINNER, 0)
    revision = summary["revision"]
    assert isinstance(revision, int)
    after = manager.confirm_turn(game_id, WINNER, revision)
    assert after["confirmation"] is None
    # Sealed through the winner's two rows and the close.
    assert session.undo_floor >= 3
    # The game went on past the winner's reward unit.
    assert not winning_intrigue_window_is_open(session.state, WINNER)
    decision = ENGINE.current_decision(session.state)
    assert not (
        isinstance(decision, PlayerDecision)
        and decision.owner == WINNER
        and _top_kind(session.state) == FrameKind.COMBAT_REWARD_ICONS
    )


def test_a_close_with_nothing_else_to_take_back_is_sealed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The winner's rows were resolved before the session stood here, so the
    # close is the only step of its unit the server could hold back for it:
    # sealed like a pass, and the game plays on.
    state = _with_hands(WINNER_START, {WINNER: ()})
    for effect in ("victory_points", "resources"):
        [row] = [
            action
            for action in ENGINE.whole_actions(state, WINNER)
            if dict(action.arguments).get("effect") == effect
        ]
        state = apply_whole(ENGINE, state, row).state
    assert winning_close_without_choice(state, WINNER)
    manager, game_id, session = _session_at(monkeypatch, state)

    [first, *_] = live_steps(session.log)
    assert (first.whole or first.step) == winning_intrigue_close(WINNER)
    assert first.without_choice
    assert session.undo_floor >= 1
    assert manager.summary(game_id)["confirmation"] is None
    assert WINNER not in session.open_units
    assert not winning_intrigue_window_is_open(session.state, WINNER)


def test_a_winner_holding_an_intrigue_card_presses_its_own_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Hidden information: it holds a card it cannot play here, which only it
    # knows; the table sees that it holds one.
    start = _with_hands(WINNER_START, {WINNER: (PLOT_CARD,)})
    manager, game_id, session = _session_at(monkeypatch, start)
    _press_index(manager, game_id, WINNER, 0)
    summary = _press_index(manager, game_id, WINNER, 0)
    assert summary["confirmation"] is None
    assert _owner(session) == WINNER
    assert _effects(session.state, WINNER) == ["winning_intrigue"]
    assert winning_intrigue_window_is_open(session.state, WINNER)


def test_a_winner_whose_reward_drew_an_intrigue_card_is_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = _with_hands(DRAWING_START, {DRAWING_WINNER: ()})
    assert _owner_at(start) == DRAWING_WINNER
    assert _effects(start, DRAWING_WINNER) == ["choose_influence", "intrigue"]
    manager, game_id, session = _session_at(monkeypatch, start)

    def press(effect: str) -> JsonObject:
        [index] = [
            index
            for index, row in enumerate(_effects(session.state, DRAWING_WINNER))
            if row == effect
        ]
        return _press_index(manager, game_id, DRAWING_WINNER, index)

    # The Influence first (its Faction window's first row), then the draw,
    # so the close is what the window has left.
    press("choose_influence")
    _press_index(manager, game_id, DRAWING_WINNER, 0)
    assert _effects(session.state, DRAWING_WINNER) == ["intrigue"]
    summary = press("intrigue")
    # It holds the cards it drew: a winning Intrigue drawn here may be
    # played at once [FAQ p. 4], so its close stays its own press.
    assert session.state.players[DRAWING_WINNER].intrigue_cards
    assert winning_intrigue_window_is_open(session.state, DRAWING_WINNER)
    assert "winning_intrigue" in _effects(session.state, DRAWING_WINNER)
    assert summary["confirmation"] is None
    assert _owner(session) == DRAWING_WINNER


# --- Endgame --------------------------------------------------------------


def _endgame_seats(state: GameState) -> list[int]:
    assert state.first_player is not None
    return [
        (state.first_player + offset) % state.config.players
        for offset in range(state.config.players)
    ]


def test_a_card_less_seat_with_no_wild_pair_is_passed_at_the_endgame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = _endgame_seats(ENDGAME_START)[:2]
    start = _with_hands(ENDGAME_START, {first: (), second: (PLOT_CARD,)})
    assert endgame_pass_without_choice(start, first)
    manager, game_id, session = _session_at(monkeypatch, start)

    pressed = DomainAction(action_id=ENDGAME_PASS, actor=first)
    assert session.steps == [pressed]
    assert ENGINE.whole_actions(start, first) == (pressed,)
    # Sealed like a press: nothing to take back, no hold, no open unit.
    assert session.undo_floor == 1
    assert session.awaiting_confirmation is None
    assert first not in session.open_units
    for viewer in range(4):
        [entry] = _log(manager, game_id, viewer)
        assert entry["action_id"] == ENDGAME_PASS and entry["without_choice"] is True
    # The next seat holds a card, one it cannot play: it is asked.
    assert _owner(session) == second
    assert _effects(session.state, second) == [ENDGAME_PASS]


def _wild_and_partner(state: GameState) -> tuple[str, str]:
    """A wild-icon Conflict card and a card with a printed icon, from the
    game's Conflict deck and the seats' won Conflicts."""

    cards = {
        *state.conflict_deck,
        *state.unused_conflict_ids,
        *(card for player in state.players for card in player.won_conflict_ids),
    }
    icons = {card: _battle_icon(card) for card in cards}
    wild = sorted(
        card for card, icon in icons.items() if icon is not None and icon.name == "WILD"
    )
    printed = sorted(
        card for card, icon in icons.items() if icon is not None and icon.name != "WILD"
    )
    assert wild and printed
    return wild[0], printed[0]


def test_a_card_less_seat_with_a_wild_pair_is_asked_at_the_endgame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _endgame_seats(ENDGAME_START)[0]
    wild, partner = _wild_and_partner(ENDGAME_START)
    start = _with_hands(ENDGAME_START, {first: ()})
    # The pair moves to the seat's won Conflicts from wherever it lay; the
    # seat's own won Conflicts go to the unused ones (each card stays in one
    # shared zone). A pair card another seat had matched face down leaves
    # that seat's face-down cards too (the walk of the printed-effects audit's
    # merged engine, 2026-11-10, leaves the partner face down with seat 3).
    pair = (wild, partner)
    kept = start.players[first].won_conflict_ids
    players = tuple(
        replace(player, won_conflict_ids=pair, face_down_battle_card_ids=())
        if player.player_id == first
        else replace(
            player,
            won_conflict_ids=tuple(
                card for card in player.won_conflict_ids if card not in pair
            ),
            face_down_battle_card_ids=tuple(
                card for card in player.face_down_battle_card_ids if card not in pair
            ),
        )
        for player in start.players
    )
    start = replace(
        start,
        players=players,
        conflict_deck=tuple(card for card in start.conflict_deck if card not in pair),
        unused_conflict_ids=(
            *(card for card in start.unused_conflict_ids if card not in pair),
            *(card for card in kept if card not in pair),
        ),
    )
    assert not endgame_pass_without_choice(start, first)
    _manager, _game_id, session = _session_at(monkeypatch, start)
    assert session.steps == []
    assert _owner(session) == first
    assert set(_effects(session.state, first)) == {
        ENDGAME_PASS,
        "match_endgame_wild_icon",
    }


def test_the_endgame_window_is_where_the_walk_stopped() -> None:
    # The fixture's sanity: the walk stopped at the Endgame window, opened
    # for the First Player, with every seat to answer in turn.
    assert _top_kind(ENDGAME_START) == FrameKind.ENDGAME_INTRIGUE
    assert _owner_at(ENDGAME_START) == ENDGAME_START.first_player
    assert all(isinstance(player, PlayerState) for player in ENDGAME_START.players)
