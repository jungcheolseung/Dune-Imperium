"""The server passes Combat Intrigue for a human seat with no Intrigue card.

User request 2026-11-09: "전투단계에서 책략카드가 없는 사람한테는 굳이 책략
사용 여부를 물어보지 않아도 좋을 것 같아. 어차피 모든 플레이어가 그
플레이어가 책략카드가 없는 걸 알고 있기 때문에 바로 넘어가도 무관할 듯해".

The rule (docs/rules/combat-and-round-end.md section 2): "Beginning with the
First Player and proceeding clockwise, each player with at least one unit in
the Conflict may play any number of Combat Intrigue cards, or may pass. ...
Once all players involved in Combat pass consecutively, you then resolve the
Combat." [Main p. 14]. The engine still asks and records every pass
(``sessions._auto_pass_intrigue_locked`` answers for the seat), so
saves, replays and AI seats are as before.

The condition is the seat's empty Intrigue hand, a public count, never "no
Combat Intrigue it can play": a seat holding cards it cannot play is asked,
or the pass would tell the table what it holds. A seat that played a card in
this opportunity presses its own pass (its pass confirms the play). A seat
with specimens is passed for too: it may return one "at any time"
[Immortality p. 8], and its own Conflict reward window offers that return
right before a reward recruits (OQ-050, user decision 2026-11-09).

The positions are real: a seeded random game played by the engine up to its
first Combat Intrigue with every seat in the Conflict, then only the seats'
Intrigue hands (and once specimens) edited, the one change made outside the
rules. A session starts from that position (``engine.reset`` returns it, as
``tests/server/test_undo.py`` does).
"""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.agent_turn_steps import apply_whole, steps_after
from dune_imperium.core import (
    ChanceDecision,
    DomainAction,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.rules.combat import (
    COMBAT_INTRIGUE_PLAYED_KEY,
    _participants_from_mask,
)
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server import sessions as sessions_module
from dune_imperium.server.session_log import live_steps, log_step
from dune_imperium.server.sessions import GameSession, GameSessionManager, JsonObject

FOUR_HUMANS = ("human", "human", "human", "human")
PASS = "pass_combat_intrigue"
# A Plot card: never playable in Combat [Imperium Politics card].
PLOT_CARD = "intrigue:imperium_politics:0"
# A Combat card with no cost or condition of its own: "Gain 3 swords"
# [Weirding Combat card].
COMBAT_CARD = "intrigue:weirding_combat:0"
ENGINE = UprisingRulesEngine()


def _combat_start(config: RulesetConfig, seed: int) -> GameState:
    """A seeded random game up to its first Combat Intrigue opportunity with
    every seat in the Conflict."""

    state = ENGINE.reset(config, seed)
    resolver = ChanceResolver(seed=seed)
    rng = random.Random(seed)
    for _ in range(5000):
        top = state.decision_stack[-1] if state.decision_stack else None
        if top is not None and top.kind == FrameKind.COMBAT_INTRIGUE:
            mask = dict(top.context)["participants_mask"]
            assert isinstance(mask, int)
            if len(_participants_from_mask(4, mask, state.first_player)) == 4:
                return state
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(ENGINE, state, resolver.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        state = apply_whole(
            ENGINE, state, rng.choice(ENGINE.whole_actions(state, decision.owner))
        ).state
    raise AssertionError("no Combat Intrigue with every seat in the Conflict")


# Base game, seed 3: round 2's Combat Intrigue, participants 1, 2, 3, 0.
BASE_START = _combat_start(RulesetConfig(), 3)
# Immortality, seed 3: round 3's, participants 2, 3, 0, 1.
IMMORTALITY_START = _combat_start(RulesetConfig(immortality=True), 3)


def _participants(state: GameState) -> tuple[int, ...]:
    mask = dict(state.decision_stack[-1].context)["participants_mask"]
    assert isinstance(mask, int)
    return _participants_from_mask(4, mask, state.first_player)


def _with_hands(
    state: GameState, hands: dict[int, tuple[str, ...]], **extra: int
) -> GameState:
    """``state`` with each seat's Intrigue hand set to ``hands`` (its cards
    taken out of the deck), and any ``specimens_<seat>`` set (a specimen is
    one of the seat's twelve troops, taken from or given back to its
    supply)."""

    held = {card for cards in hands.values() for card in cards}
    returned = tuple(
        card
        for seat in hands
        for card in state.players[seat].intrigue_cards
        if card not in held
    )

    def specimens(player: PlayerState) -> int:
        return extra.get(f"specimens_{player.player_id}", player.specimens)

    players = tuple(
        replace(
            player,
            intrigue_cards=hands.get(player.player_id, player.intrigue_cards),
            specimens=specimens(player),
            troops_supply=player.troops_supply + player.specimens - specimens(player),
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
        FOUR_HUMANS, game_seed=0, immortality=start.config.immortality
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


def _ids(session: GameSession, seat: int) -> list[str]:
    return _ids_at(session.state, seat)


def _ids_at(state: GameState, seat: int) -> list[str]:
    return [action.action_id for action in ENGINE.whole_actions(state, seat)]


def _press(
    manager: GameSessionManager,
    game_id: str,
    seat: int,
    action_id: str,
    **arguments: object,
) -> JsonObject:
    session = manager._get(game_id)
    actions = ENGINE.whole_actions(session.state, seat)
    [index] = [
        index
        for index, action in enumerate(actions)
        if action.action_id == action_id
        and all(
            dict(action.arguments).get(key) == value for key, value in arguments.items()
        )
    ]
    summary = manager.summary(game_id)
    revision = summary["revision"]
    assert isinstance(revision, int)
    return manager.apply_action(game_id, seat, revision, index)


def _log(manager: GameSessionManager, game_id: str, seat: int) -> list[JsonObject]:
    entries = manager.log(game_id, seat)["entries"]
    assert isinstance(entries, list)
    return [entry for entry in entries if isinstance(entry, dict)]


def test_a_seat_with_no_intrigue_card_is_passed_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seat 1 holds nothing; seat 2, next, holds a card it cannot play here.
    assert _participants(BASE_START) == (1, 2, 3, 0)
    start = _with_hands(BASE_START, {1: (), 2: (PLOT_CARD,)})
    manager, game_id, session = _session_at(monkeypatch, start)

    pressed = DomainAction(action_id=PASS, actor=1)
    assert session.steps == [pressed]
    # The step and log entry its own press would make: the rules offer that
    # one pass and nothing else.
    assert ENGINE.whole_actions(start, 1) == (pressed,)
    assert ENGINE.legal_actions(start, 1) == (pressed,)
    transition = ENGINE.apply(start, pressed)
    assert live_steps(session.log)[0] == log_step(
        start, transition.state, pressed, transition.events
    )
    # Sealed like a press: nothing to take back, no hold, no open unit.
    assert session.undo_floor == 1
    assert session.awaiting_confirmation is None
    assert 1 not in session.open_units
    summary = manager.summary(game_id)
    assert summary["undo"] == []
    # Every seat's log names it a pass its seat could only make, so the page
    # does not take it for the seat's own look at the table.
    for viewer in range(4):
        [entry] = _log(manager, game_id, viewer)
        assert entry["action_id"] == PASS and entry["without_choice"] is True
    # Seat 2 is asked: it holds a card, even one it cannot play now.
    assert _owner(session) == 2
    assert _ids(session, 2) == [PASS]


def test_a_seat_holding_an_intrigue_card_it_cannot_play_is_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Hidden information: its only legal action is the pass, but whether it
    # holds a Combat card is its own; the table sees only that it holds one.
    start = _with_hands(BASE_START, {1: (PLOT_CARD,)})
    _manager, _game_id, session = _session_at(monkeypatch, start)

    assert session.steps == []
    assert _owner(session) == 1
    assert _ids(session, 1) == [PASS]


def test_every_seat_without_a_card_passes_and_the_combat_resolves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = _with_hands(BASE_START, {0: (), 1: (), 2: (), 3: ()})
    _manager, _game_id, session = _session_at(monkeypatch, start)

    assert session.steps[:4] == [
        DomainAction(action_id=PASS, actor=seat) for seat in (1, 2, 3, 0)
    ]
    assert session.state.combat_intrigue_complete
    kinds = [
        event.kind for entry in live_steps(session.log)[:4] for event in entry.events
    ]
    assert "combat_intrigue_finished" in kinds


def test_a_seat_with_specimens_is_passed_for_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The rules offer it the pass and a specimen's return [Immortality p. 8]
    # (OQ-050), but the return waits for its own Conflict reward window,
    # right before a reward recruits (user decision 2026-11-09, "보상 받을
    # 때 그때 표본을 반환하면 되는거 아니야?"): the server passes for it.
    assert _participants(IMMORTALITY_START) == (2, 3, 0, 1)
    start = _with_hands(IMMORTALITY_START, {2: (), 3: (PLOT_CARD,)}, specimens_2=1)
    assert sorted(_ids_at(start, 2)) == [PASS, "return_specimen"]
    manager, game_id, session = _session_at(monkeypatch, start)

    assert session.steps == [DomainAction(action_id=PASS, actor=2)]
    assert session.state.players[2].specimens == 1
    assert 2 not in session.open_units
    assert _owner(session) == 3
    for viewer in range(4):
        [entry] = _log(manager, game_id, viewer)
        assert entry["actor"] == 2 and entry["without_choice"] is True


def test_a_seat_whose_unit_is_open_presses_its_own_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A step it may still take back is never sealed for it: with its unit
    # open the server leaves the opportunity to the seat.
    start = _with_hands(IMMORTALITY_START, {2: (), 3: (PLOT_CARD,)}, specimens_2=1)
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=0, immortality=True)
    session = manager._get(str(summary["game_id"]))
    session.state = start
    session.open_units[2] = 0
    with session.lock:
        assert not manager._auto_pass_intrigue_locked(session, 2)
        del session.open_units[2]
        assert manager._auto_pass_intrigue_locked(session, 2)
    assert session.steps == [DomainAction(action_id=PASS, actor=2)]


def test_without_specimens_the_same_seat_is_passed_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = _with_hands(IMMORTALITY_START, {2: (), 3: (PLOT_CARD,)}, specimens_2=0)
    _manager, _game_id, session = _session_at(monkeypatch, start)
    assert session.steps == [DomainAction(action_id=PASS, actor=2)]
    assert _owner(session) == 3


def test_a_seat_that_played_its_last_card_presses_its_own_pass_and_is_read_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seat 1 holds nothing and is passed for; seat 2 plays its only card.
    start = _with_hands(BASE_START, {0: (), 1: (), 2: (COMBAT_CARD,), 3: ()})
    manager, game_id, session = _session_at(monkeypatch, start)
    assert session.steps == [DomainAction(action_id=PASS, actor=1)]
    assert _owner(session) == 2

    summary = _press(manager, game_id, 2, "play_intrigue", card_id=COMBAT_CARD)
    # Its hand is empty now, but it played in this opportunity: its own
    # pass confirms the play, which it may still take back.
    assert session.state.players[2].intrigue_cards == ()
    assert dict(session.state.decision_stack[-1].context).get(
        COMBAT_INTRIGUE_PLAYED_KEY
    )
    assert _owner(session) == 2
    assert _ids(session, 2) == [PASS]
    undo = summary["undo"]
    # (The play is its effect-first steps, stage B3c-1.)
    assert isinstance(undo, list)
    assert [row["seat"] for row in undo if isinstance(row, dict)] == [2]

    # Seat 1 gains an Intrigue card meanwhile (edited in: the one change
    # outside the rules). Priority comes back to it after seat 2's pass and
    # the passes the server takes for seats 3 and 0; it is asked then.
    session.state = replace(
        session.state,
        players=tuple(
            replace(player, intrigue_cards=(PLOT_CARD,))
            if player.player_id == 1
            else player
            for player in session.state.players
        ),
    )
    _press(manager, game_id, 2, PASS)
    # Its pressed pass is a pass of its own; the server's for seats 3 and 0
    # are not.
    flags = [
        (entry["actor"], entry.get("without_choice", False))
        for entry in _log(manager, game_id, 0)
        if entry["type"] == "action" and entry["action_id"] == PASS
    ]
    assert flags == [(1, True), (2, False), (3, True), (0, True)]
    assert session.steps[-3:] == [
        DomainAction(action_id=PASS, actor=seat) for seat in (2, 3, 0)
    ]
    assert _owner(session) == 1
    assert not session.state.combat_intrigue_complete


def test_ai_seats_are_left_to_themselves(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only a human seat's opportunity is answered by the server; an AI seat
    # passes as its own agent decides (the same step).
    start = _with_hands(BASE_START, {0: (), 1: (), 2: (), 3: ()})
    manager = GameSessionManager()
    summary = manager.create_game(("human", "random", "random", "random"), game_seed=0)
    session = manager._get(str(summary["game_id"]))
    assert not session.steps
    session.state = start
    monkeypatch.setattr(session.engine, "reset", lambda config, seed: start)
    with session.lock:
        manager._advance_locked(session)
    assert session.steps[:4] == [
        DomainAction(action_id=PASS, actor=seat) for seat in (1, 2, 3, 0)
    ]


def _server_passes(session: GameSession, sent: set[int]) -> list[int]:
    """The steps that pass Combat Intrigue and no request sent."""

    return [
        index
        for index, step in enumerate(session.steps)
        if isinstance(step, DomainAction)
        and step.action_id == PASS
        and index not in sent
    ]


def test_an_auto_pass_replays_after_a_load() -> None:
    # A real four-human game (seed 1, the first legal action each time): the
    # server's passes are in its steps like pressed ones, so a save loads
    # into the same steps, undo floor and state.
    manager = GameSessionManager()
    summary = manager.create_game(FOUR_HUMANS, game_seed=1)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    sent: set[int] = set()
    while not _server_passes(session, sent):
        assert not summary["finished"], "no server pass in the game"
        held = summary["confirmation"]
        revision = summary["revision"]
        assert isinstance(revision, int)
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, revision)
            continue
        decision = summary["decision"]
        assert isinstance(decision, dict)
        owner = decision["owner"]
        assert isinstance(owner, int)
        whole = ENGINE.whole_actions(session.state, owner)[0]
        first = len(session.steps)
        sent.update(range(first, first + steps_after(session.state, whole) + 1))
        summary = manager.apply_action(game_id, owner, revision, 0)
    [index, *_] = _server_passes(session, sent)
    step = session.steps[index]
    assert isinstance(step, DomainAction)
    before = sessions_module._state_after(session, index)
    assert before.players[step.actor].intrigue_cards == ()
    assert session.undo_floor > index

    restored = manager.restore_game(manager.save_game(game_id))
    reloaded = manager._get(str(restored["game_id"]))
    assert reloaded.steps == session.steps
    assert reloaded.undo_floor == session.undo_floor
    assert restored["undo"] == summary["undo"]
    assert reloaded.state == session.state
    # The log rebuilds the mark from the position; the save holds none.
    assert _log(manager, str(restored["game_id"]), 0) == _log(manager, game_id, 0)
    assert _log(manager, game_id, 0)[index]["without_choice"] is True
