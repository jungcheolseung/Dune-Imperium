"""A person's seat handed to the AI mid-game, and taken back.

User request 2026-11-07: "플레이하던 사람이 나가거나, 본인이 원하는 경우 ai가
대신 이어서 플레이할 수 있게 하기". The user's choices the same day: the seat's
player or the host hands it over; the server's search AI takes it on
Uprising, the app AI at Hard on the original game; its player takes it back
at any time, from the next decision; a badge and a log line show it, and the
play clock counts on in the seat's total.
"""

import copy
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from dune_imperium.agents import make_agent
from dune_imperium.agents.app_ai.agent import AppAIAgent
from dune_imperium.config import BaseGame, RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.state import GameState
from dune_imperium.records.convert import convert_save_document
from dune_imperium.records.saves import (
    SavedGame,
    ai_played_steps,
    human_decisions,
)
from dune_imperium.rules.agent_turn import agent_card_pick
from dune_imperium.server import sessions as sessions_module
from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.persistence import SaveError, parse_save_document
from dune_imperium.server.session_log import (
    LogEntry,
    LoggedSeatChange,
    LoggedStep,
    LoggedUndo,
    seat_changes,
    undo_window,
)
from dune_imperium.server.sessions import (
    SERVER_SEARCH_OPTIONS,
    TAKEOVER_FALLBACK,
    GameNotStartedError,
    GameSession,
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SessionError,
)

ADMIN_KEY = "takeover-admin-key"
ADMIN = Credentials(admin_key=ADMIN_KEY)
TWO_PEOPLE = ("human", "human", "app_ai", "app_ai")
SEED = 3


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _list(value: object) -> list[object]:
    assert isinstance(value, list)
    return value


def _session(manager: GameSessionManager, game_id: str) -> GameSession:
    return manager._sessions[game_id]


def _owner(summary: JsonObject) -> int:
    """The seat that must act next: a pending press first, else the decision."""

    if summary["confirmation"] is not None:
        return _int(summary["confirmation"])
    return _int(_obj(summary["decision"])["owner"])


def _play(
    manager: GameSessionManager,
    game_id: str,
    seat: int,
    *,
    credentials: Credentials | None = None,
) -> JsonObject:
    """``seat`` presses its waiting turn end, or takes its legal action 0."""

    credentials = credentials or Credentials()
    summary = manager.summary(game_id)
    revision = _int(summary["revision"])
    if summary["confirmation"] == seat:
        return manager.confirm_turn(game_id, seat, revision, credentials=credentials)
    return manager.apply_action(game_id, seat, revision, 0, credentials=credentials)


def _play_until(
    manager: GameSessionManager,
    game_id: str,
    done: Callable[[JsonObject], bool],
    *,
    limit: int = 2000,
) -> JsonObject:
    """Let every person's seat play action 0 until ``done(summary)`` holds."""

    for _ in range(limit):
        manager.wait_for_ai(game_id)
        summary = manager.summary(game_id)
        if done(summary):
            return summary
        assert not summary["finished"], "the game ended first"
        _play(manager, game_id, _owner(summary))
    raise AssertionError("the position never came")


def _game(
    manager: GameSessionManager | None = None, seats: tuple[str, ...] = TWO_PEOPLE
) -> tuple[GameSessionManager, str]:
    manager = manager or GameSessionManager()
    summary = manager.create_game(seats, game_seed=SEED)
    return manager, str(summary["game_id"])


def _seat_changes_logged(summary_log: object) -> list[dict[str, object]]:
    entries = _list(_obj(summary_log)["entries"])
    return [_obj(entry) for entry in entries if _obj(entry)["type"] == "seat_change"]


# -- handing over ------------------------------------------------------------


def test_the_ai_plays_a_handed_seat_on_and_the_seat_stays_its_persons_place() -> None:
    manager, game_id = _game()
    _play_until(manager, game_id, lambda s: s["round_number"] == 2 and _owner(s) == 1)
    before = len(_session(manager, game_id).steps)

    summary = manager.hand_to_ai(game_id, 1)

    session = _session(manager, game_id)
    # The AI answered seat 1's decisions and the game went on to a person's.
    assert _owner(summary) == 0
    assert any(
        isinstance(step, DomainAction) and step.actor == 1
        for step in session.steps[before:]
    )
    # Still a person's place, which the AI plays (the badge's field).
    assert summary["seats"] == ["human", "human", "app_ai", "app_ai"]
    players = [_obj(player) for player in _list(summary["players"])]
    assert [player["ai"] for player in players] == [None, TAKEOVER_FALLBACK, None, None]
    assert session.seats[1] == TAKEOVER_FALLBACK
    assert session.places == TWO_PEOPLE
    # Its person still reads it; nobody acts for it.
    snapshot = manager.snapshot(game_id, 1)
    assert snapshot["actions"] is None
    assert _seat_changes_logged(snapshot["log"]) == [
        {
            "index": _list(_obj(snapshot["log"])["entries"]).index(
                _seat_changes_logged(snapshot["log"])[0]
            ),
            "type": "seat_change",
            "seat": 1,
            "ai": TAKEOVER_FALLBACK,
        }
    ]
    revision = _int(summary["revision"])
    calls: tuple[Callable[[], object], ...] = (
        lambda: manager.apply_action(game_id, 1, revision, 0),
        lambda: manager.confirm_turn(game_id, 1, revision),
        lambda: manager.undo(game_id, 1, revision),
        lambda: manager.legal_actions(game_id, 1),
    )
    for call in calls:
        with pytest.raises(SessionError, match="an AI plays seat 1 now"):
            call()
    with pytest.raises(SessionError, match="an AI already plays seat 1"):
        manager.hand_to_ai(game_id, 1)


def test_the_hand_over_presses_a_turn_end_that_waited_for_the_person() -> None:
    manager, game_id = _game()
    _play_until(manager, game_id, lambda s: s["confirmation"] == 0)
    session = _session(manager, game_id)
    assert session.open_units.get(0) is not None

    summary = manager.hand_to_ai(game_id, 0)

    assert summary["confirmation"] != 0
    assert 0 not in session.open_units
    # What the person played is sealed, and the game moved on past it.
    assert session.undo_floor >= 1
    assert not any(_obj(row)["seat"] == 0 for row in _list(summary["undo"]))


def test_a_game_whose_people_all_hand_over_is_played_to_its_end() -> None:
    manager, game_id = _game()
    _play_until(manager, game_id, lambda s: s["round_number"] == 3)
    manager.hand_to_ai(game_id, 0)
    summary = manager.hand_to_ai(game_id, 1)
    assert summary["finished"] is True
    # The finished game still loads, its seat changes made at their steps.
    restored = manager.restore_game(manager.save_document(game_id))
    assert restored["finished"] is True
    players = [_obj(player) for player in _list(restored["players"])]
    assert [player["ai"] for player in players][:2] == [TAKEOVER_FALLBACK] * 2


def test_the_original_game_hands_a_seat_to_the_app_ai() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(
        ("human", "app_ai", "app_ai", "app_ai"),
        base_game=BaseGame.IMPERIUM.value,
        game_seed=SEED,
    )
    game_id = str(summary["game_id"])
    _play_until(manager, game_id, lambda s: s["round_number"] == 2)
    finished = manager.hand_to_ai(game_id, 0)
    assert finished["finished"] is True
    assert _session(manager, game_id).seats[0] == "app_ai"


def test_the_takeover_ai_is_the_search_ai_where_the_server_has_one_for_the_game(
    tmp_path: Path,
) -> None:
    # Each base game's own network (user decisions 2026-11-07 "탐색 AI, 원판은
    # 앱 AI" and 2026-11-08 "원판도 탐색 AI"); the app AI where there is none.
    network = tmp_path / "search.pt"
    network.write_bytes(b"")
    original_network = tmp_path / "search-imperium.pt"
    original_network.write_bytes(b"")
    uprising, original = RulesetConfig(), RulesetConfig(base_game=BaseGame.IMPERIUM)
    searching = GameSessionManager(search_checkpoint=network)
    assert searching.takeover_kind(uprising) == (
        f"search:{network.resolve()}{SERVER_SEARCH_OPTIONS}"
    )
    assert searching.takeover_kind(original) == TAKEOVER_FALLBACK
    both = GameSessionManager(
        search_checkpoint=network,
        imperium_search_checkpoint=original_network,
        search_turn_extend=16,
    )
    assert both.takeover_kind(uprising) == (
        f"search:{network.resolve()}{SERVER_SEARCH_OPTIONS}::turn_extend=16"
    )
    assert both.takeover_kind(original) == (
        f"search:{original_network.resolve()}{SERVER_SEARCH_OPTIONS}::turn_extend=16"
    )
    only_original = GameSessionManager(imperium_search_checkpoint=original_network)
    assert only_original.takeover_kind(uprising) == TAKEOVER_FALLBACK
    assert GameSessionManager().takeover_kind(uprising) == TAKEOVER_FALLBACK
    assert GameSessionManager().takeover_kind(original) == TAKEOVER_FALLBACK


# -- taking back --------------------------------------------------------------


def test_the_person_takes_the_seat_back_and_answers_the_next_decision() -> None:
    manager, game_id = _game()
    _play_until(manager, game_id, lambda s: s["round_number"] == 2 and _owner(s) == 0)
    manager.hand_to_ai(game_id, 1)
    _play_until(manager, game_id, lambda s: s["round_number"] == 3 and _owner(s) == 0)

    summary = manager.take_back(game_id, 1)

    session = _session(manager, game_id)
    assert session.seats[1] == "human"
    assert 1 not in session.agents
    players = [_obj(player) for player in _list(summary["players"])]
    assert players[1]["ai"] is None
    # Seat 1 plays its own next decision again.
    after = _play_until(manager, game_id, lambda s: _owner(s) == 1)
    assert manager.snapshot(game_id, 1)["actions"] is not None
    _play(manager, game_id, 1)
    assert after["finished"] is False
    with pytest.raises(SessionError, match="person already plays it"):
        manager.take_back(game_id, 1)


def test_the_seats_undo_window_closes_at_its_own_change_only() -> None:
    def step(seat: int) -> LoggedStep:
        return LoggedStep(
            step=DomainAction("pass_turn", seat),
            events=(),
            reveals=False,
            hidden_arguments=frozenset(),
        )

    log: list[LogEntry] = [
        step(1),
        step(1),
        LoggedSeatChange(seat=1, kind="human"),
        step(1),
    ]
    assert undo_window(log, 1) == 1
    # Another seat's change touches no state: seat 0's window runs past it.
    other: list[LogEntry] = [
        step(0),
        step(0),
        LoggedSeatChange(seat=1, kind="app_ai", seed=7),
    ]
    assert undo_window(other, 0) == 2
    undone: list[LogEntry] = [
        step(0),
        LoggedSeatChange(seat=1, kind="app_ai", seed=7),
        LoggedStep(
            step=DomainAction("pass_turn", 0),
            events=(),
            reveals=False,
            hidden_arguments=frozenset(),
            undone=True,
        ),
        LoggedUndo(seat=0, count=1),
        step(0),
    ]
    assert undo_window(undone, 0) == 2
    # The change sits after the one live step logged before it.
    assert [position for position, _ in seat_changes(undone)] == [1]


class _Gate:
    """Holds the app AI's answers while closed (it starts open), and keeps
    which agent was asked about which state."""

    def __init__(self) -> None:
        self.asked = threading.Event()
        self.opened = threading.Event()
        self.opened.set()
        self.calls: list[tuple[AppAIAgent, GameState]] = []
        # An agent whose answers raise once the gate lets them through.
        self.failing: AppAIAgent | None = None


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Gate]:
    held = _Gate()
    answer = AppAIAgent.choose_action_with_state

    def gated(
        agent: AppAIAgent,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        held.calls.append((agent, state))
        held.asked.set()
        assert held.opened.wait(30), "the test never opened the gate"
        if agent is held.failing:
            raise RuntimeError("the replaced agent fails")
        return answer(agent, state, observation, legal_actions)

    monkeypatch.setattr(AppAIAgent, "choose_action_with_state", gated)
    yield held
    held.opened.set()


def _paced_game_at_seat_1(gate: _Gate) -> tuple[GameSessionManager, str, int]:
    """A paced game resting on seat 1's own decision, its step count."""

    manager = GameSessionManager(pace_unit=0.0, default_ai_pace="normal")
    manager, game_id = _game(manager)
    _play_until(manager, game_id, lambda s: s["round_number"] == 2 and _owner(s) == 1)
    return manager, game_id, len(_session(manager, game_id).steps)


def test_taking_back_drops_the_answer_the_ai_is_still_computing(gate: _Gate) -> None:
    manager, game_id, steps = _paced_game_at_seat_1(gate)
    gate.opened.clear()
    gate.asked.clear()

    handed = manager.hand_to_ai(game_id, 1)
    assert handed["thinking"] == 1
    assert gate.asked.wait(30)
    taken = manager.take_back(game_id, 1)
    assert taken["thinking"] is None
    gate.opened.set()
    manager.wait_for_ai(game_id)

    session = _session(manager, game_id)
    assert len(session.steps) == steps
    summary = manager.summary(game_id)
    assert _owner(summary) == 1
    assert _obj(summary["decision"])["owner_is_human"] is True
    assert manager.snapshot(game_id, 1)["actions"] is not None
    # The record holds both changes and no AI step between them.
    document = manager.save_document(game_id)
    assert [
        (position, change.kind)
        for position, change in seat_changes(parse_save_document(document).log or ())
    ] == [(steps, TAKEOVER_FALLBACK), (steps, "human")]
    manager.restore_game(document)


def test_an_answer_of_an_agent_the_seat_no_longer_has_is_dropped(gate: _Gate) -> None:
    manager, game_id, steps = _paced_game_at_seat_1(gate)
    gate.opened.clear()
    gate.asked.clear()
    manager.hand_to_ai(game_id, 1)
    assert gate.asked.wait(30)
    first = _session(manager, game_id).agents[1]
    asked = _session(manager, game_id).state
    assert gate.calls[-1] == (first, asked)
    manager.take_back(game_id, 1)
    # Handed on again before the first agent's answer came back: the game's
    # state is the same object, so only the agent tells the answers apart.
    manager.hand_to_ai(game_id, 1)
    second = _session(manager, game_id).agents[1]
    assert second is not first
    gate.opened.set()
    manager.wait_for_ai(game_id)
    # The first agent's answer was dropped, so the second one was asked
    # about the same decision in its place.
    assert any(agent is second and state is asked for agent, state in gate.calls), (
        "the second agent never answered the decision the first one left"
    )
    _play_until(manager, game_id, lambda s: _owner(s) == 0 and s["thinking"] is None)

    # A load builds only the second agent, at its step, and regenerates
    # every answer the session applied: the first agent's never was.
    document = manager.save_document(game_id)
    kinds = [
        change.kind
        for _, change in seat_changes(parse_save_document(document).log or ())
    ]
    assert kinds == [TAKEOVER_FALLBACK, "human", TAKEOVER_FALLBACK]
    restored = manager.restore_game(document)
    restored_session = _session(manager, str(restored["game_id"]))
    assert restored_session.steps == _session(manager, game_id).steps
    assert len(restored_session.steps) > steps


def test_a_save_made_while_the_ai_thinks_loads_and_thinks_again(gate: _Gate) -> None:
    manager, game_id, steps = _paced_game_at_seat_1(gate)
    gate.opened.clear()
    gate.asked.clear()
    manager.hand_to_ai(game_id, 1)
    assert gate.asked.wait(30)
    document = manager.save_document(game_id)
    # A load regenerates the app AI seats' earlier steps through the gate.
    gate.opened.set()
    restored = manager.restore_game(document)
    copy_id = str(restored["game_id"])
    assert restored["thinking"] == 1
    for game in (game_id, copy_id):
        _play_until(manager, game, lambda s: s["round_number"] == 3)
    assert _session(manager, copy_id).steps == _session(manager, game_id).steps


def test_a_failure_of_an_agent_the_seat_no_longer_has_stalls_nothing(
    gate: _Gate,
) -> None:
    """Codex review r1 (2026-11-07): the replaced agent's failure must not
    end the new agent's thinking, or nobody answers the seat's decision."""

    manager, game_id, steps = _paced_game_at_seat_1(gate)
    gate.opened.clear()
    gate.asked.clear()
    manager.hand_to_ai(game_id, 1)
    assert gate.asked.wait(30)
    replaced = _session(manager, game_id).agents[1]
    assert isinstance(replaced, AppAIAgent)
    gate.failing = replaced
    manager.take_back(game_id, 1)
    manager.hand_to_ai(game_id, 1)
    gate.opened.set()
    manager.wait_for_ai(game_id)

    session = _session(manager, game_id)
    assert session.thinking is None
    step = session.steps[steps]
    assert isinstance(step, DomainAction) and step.actor == 1
    restored = manager.restore_game(manager.save_document(game_id))
    assert _session(manager, str(restored["game_id"])).steps == session.steps


# -- undo around another seat's change ---------------------------------------


def test_another_seats_change_leaves_an_open_undo_and_a_load_places_it() -> None:
    manager, game_id = _game()
    session = _session(manager, game_id)

    def undoable(summary: JsonObject) -> bool:
        return _owner(summary) == 0 and any(
            _obj(row)["seat"] == 0 for row in _list(summary["undo"])
        )

    summary = _play_until(manager, game_id, undoable)
    window = next(
        _int(_obj(row)["steps"])
        for row in _list(summary["undo"])
        if _obj(row)["seat"] == 0
    )
    steps = len(session.steps)

    handed = manager.hand_to_ai(game_id, 1)
    # Seat 0 still owns the decision; its window stays open.
    assert len(session.steps) == steps
    assert any(
        _obj(row) == {"seat": 0, "steps": window} for row in _list(handed["undo"])
    )
    manager.undo(game_id, 0, _int(handed["revision"]), window)
    # The change happened before whatever replaces the steps taken back.
    assert [position for position, _ in seat_changes(session.log)] == [steps - window]
    _play_until(manager, game_id, lambda s: s["round_number"] == 3)
    document = manager.save_document(game_id)
    restored = manager.restore_game(document)
    assert _session(manager, str(restored["game_id"])).steps == session.steps
    # The records count the AI's steps from the change on, the undone ones
    # before it left out.
    assert ai_played_steps(parse_save_document(document)) == {
        index
        for index, step in enumerate(session.steps)
        if index >= steps - window
        and isinstance(step, DomainAction)
        and step.actor == 1
    }


def test_a_hand_over_waits_behind_another_seats_pending_press() -> None:
    """Seat 0's turn end waits for its press; seat 1 is handed over then.
    Nothing moves until seat 0 presses, seat 0 may still take its steps
    back across seat 1's change, and the save of each moment loads."""

    manager, game_id = _game()
    session = _session(manager, game_id)
    _play_until(manager, game_id, lambda s: s["confirmation"] == 0)
    steps = len(session.steps)
    held = manager.summary(game_id)
    window = next(
        _int(_obj(row)["steps"])
        for row in _list(held["undo"])
        if _obj(row)["seat"] == 0
    )

    handed = manager.hand_to_ai(game_id, 1)
    assert handed["confirmation"] == 0
    assert len(session.steps) == steps
    manager.restore_game(manager.save_document(game_id))

    manager.undo(game_id, 0, _int(handed["revision"]), window)
    assert [position for position, _ in seat_changes(session.log)] == [steps - window]
    later = _int(held["round_number"]) + 1
    _play_until(manager, game_id, lambda s: s["round_number"] == later)
    restored = manager.restore_game(manager.save_document(game_id))
    assert _session(manager, str(restored["game_id"])).steps == session.steps


def test_the_ai_finishes_an_agent_turn_the_person_had_begun() -> None:
    """Handed over between the Agent card pick and the space pick: the AI
    sends the person's card (``PlacementMemory`` has no plan for it, so the
    picked card's placements are weighed afresh), and a load agrees."""

    manager = GameSessionManager()
    summary = manager.create_game(("human", "app_ai", "app_ai", "app_ai"), game_seed=11)
    game_id = str(summary["game_id"])
    session = _session(manager, game_id)
    for _ in range(400):
        summary = manager.summary(game_id)
        picked = agent_card_pick(session.state, 0)
        if picked is not None and summary["round_number"] == 2:
            break
        if summary["confirmation"] == 0:
            manager.confirm_turn(game_id, 0, _int(summary["revision"]))
            continue
        rows = _list(manager.legal_actions(game_id, 0)["actions"])
        index = next(
            (
                _int(_obj(row)["index"])
                for row in rows
                if _obj(row)["action_id"] == "choose_agent_card"
            ),
            0,
        )
        manager.apply_action(game_id, 0, _int(summary["revision"]), index)
    else:
        raise AssertionError("seat 0 never stood between its two Agent steps")
    steps = len(session.steps)

    manager.hand_to_ai(game_id, 0)

    sent = session.steps[steps]
    assert isinstance(sent, DomainAction)
    assert (sent.actor, sent.action_id) == (0, "place_agent")
    restored = manager.restore_game(manager.save_document(game_id))
    assert _session(manager, str(restored["game_id"])).steps == session.steps


# -- save, load and records ---------------------------------------------------


def _handed_and_taken_back() -> tuple[GameSessionManager, str]:
    manager, game_id = _game()
    _play_until(manager, game_id, lambda s: s["round_number"] == 2 and _owner(s) == 0)
    manager.hand_to_ai(game_id, 1)
    _play_until(manager, game_id, lambda s: s["round_number"] == 4 and _owner(s) == 0)
    manager.take_back(game_id, 1)
    _play_until(manager, game_id, lambda s: s["round_number"] == 5)
    return manager, game_id


def test_a_load_builds_the_ai_at_its_step_and_plays_on_alike() -> None:
    manager, game_id = _game()
    _play_until(manager, game_id, lambda s: s["round_number"] == 2 and _owner(s) == 0)
    manager.hand_to_ai(game_id, 1)
    _play_until(manager, game_id, lambda s: s["round_number"] == 3 and _owner(s) == 0)
    document = manager.save_document(game_id)
    assert document["seats"] == list(TWO_PEOPLE)

    restored = manager.restore_game(document)
    copy_id = str(restored["game_id"])
    players = [_obj(player) for player in _list(restored["players"])]
    assert players[1]["ai"] == TAKEOVER_FALLBACK
    # Both play on alike: the loaded AI answers as the live one does.
    for game in (game_id, copy_id):
        _play_until(manager, game, lambda s: s["round_number"] == 5)
    assert _session(manager, copy_id).steps == _session(manager, game_id).steps


def test_records_count_none_of_the_ais_steps_as_the_persons() -> None:
    manager, game_id = _handed_and_taken_back()
    document = manager.save_document(game_id)
    parsed = parse_save_document(document)
    changes = seat_changes(parsed.log or ())
    handed, back = changes[0][0], changes[1][0]
    by_ai = ai_played_steps(parsed)
    steps = parsed.replay.steps
    assert by_ai == {
        index
        for index, step in enumerate(steps)
        if handed <= index < back and isinstance(step, DomainAction) and step.actor == 1
    }
    assert by_ai
    game = SavedGame(
        path=Path("takeover.json"),
        game_id=game_id,
        name=None,
        saved_at=None,
        finished=False,
        parsed=parsed,
    )
    persons = [decision.recorded_index for decision in human_decisions(game)]
    assert not set(persons) & by_ai
    assert {
        index
        for index, step in enumerate(steps)
        if isinstance(step, DomainAction) and step.actor in (0, 1)
    } - by_ai == set(persons)


def test_a_conversion_keeps_the_seat_changes_at_their_steps() -> None:
    manager, game_id = _handed_and_taken_back()
    document = manager.save_document(game_id)
    original = seat_changes(parse_save_document(document).log or ())
    # A save of another ruleset stamp has its log rebuilt from the steps.
    stale = copy.deepcopy(document)
    stale["ruleset_version"] = "older"
    converted = convert_save_document(stale).document
    kept = [
        entry
        for entry in _list(converted["log"])
        if _obj(entry)["type"] == "seat_change"
    ]
    assert len(kept) == 2
    assert seat_changes(parse_save_document(converted).log or ()) == original
    restored = manager.restore_game(converted)
    assert _session(manager, str(restored["game_id"])).steps == (
        _session(manager, game_id).steps
    )


def _with_change(document: JsonObject, change: dict[str, object]) -> JsonObject:
    edited = copy.deepcopy(document)
    log = _list(edited["log"])
    log.append(change)
    return edited


def test_a_load_refuses_a_seat_change_the_game_could_not_have_made() -> None:
    manager, game_id = _game()
    _play_until(manager, game_id, lambda s: s["round_number"] == 2)
    document = manager.save_document(game_id)
    bad = [
        ({"type": "seat_change", "seat": 2, "kind": "app_ai", "seed": 1}, "no person"),
        ({"type": "seat_change", "seat": 1, "kind": "human", "seed": None}, "twice"),
        ({"type": "seat_change", "seat": 1, "kind": "nobody", "seed": 1}, "to an AI"),
        ({"type": "seat_change", "seat": 1, "kind": "app_ai"}, "needs its seed"),
        ({"type": "seat_change", "seat": 1, "kind": "human", "seed": 4}, "no agent"),
    ]
    for change, reason in bad:
        with pytest.raises(SaveError, match=reason):
            manager.restore_game(_with_change(document, change))


# -- who may change a seat's hands --------------------------------------------


def _remote_game() -> tuple[GameSessionManager, str, Credentials, Credentials]:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    summary = manager.create_game(TWO_PEOPLE, game_seed=SEED, credentials=ADMIN)
    game_id = str(summary["game_id"])
    zero = manager.claim_seat(game_id, 0, "Zero")
    one = manager.claim_seat(game_id, 1, "One")
    return (
        manager,
        game_id,
        Credentials(seat_tokens=frozenset({zero.token})),
        Credentials(seat_tokens=frozenset({one.token})),
    )


def test_the_player_or_the_host_hands_over_and_only_the_player_takes_back() -> None:
    manager, game_id, zero, one = _remote_game()
    with pytest.raises(SeatAccessError, match="holder or the host"):
        manager.hand_to_ai(game_id, 1, credentials=zero)
    with pytest.raises(SeatAccessError, match="holder or the host"):
        manager.hand_to_ai(game_id, 1)
    manager.hand_to_ai(game_id, 1, credentials=ADMIN)
    with pytest.raises(SeatAccessError, match="holder may take it back"):
        manager.take_back(game_id, 1, credentials=ADMIN)
    with pytest.raises(SeatAccessError, match="holder may take it back"):
        manager.take_back(game_id, 1, credentials=zero)
    # The holder still reads the seat the AI plays, and takes it back.
    assert manager.snapshot(game_id, 1, credentials=one)["actions"] is None
    manager.take_back(game_id, 1, credentials=one)
    manager.hand_to_ai(game_id, 1, credentials=one)
    with pytest.raises(SeatAccessError):
        manager.hand_to_ai(game_id, 2, credentials=ADMIN)


def test_two_seats_are_handed_over_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The host hands over two players who left, the second while the first
    seat's agent is still being built off the lock; both go through, each
    with its own seed."""

    manager, game_id = _game()
    build = make_agent
    started: list[bool] = []

    def building(kind: str, seed: int, config: RulesetConfig | None = None) -> object:
        if not started:
            started.append(True)
            manager.hand_to_ai(game_id, 0)
        return build(kind, seed, config)

    # The name sessions.py builds a seat's agent with.
    monkeypatch.setattr(sessions_module, "make_agent", building)
    outer = manager.hand_to_ai(game_id, 1)

    players = [_obj(player) for player in _list(outer["players"])]
    assert [player["ai"] for player in players][:2] == [TAKEOVER_FALLBACK] * 2
    seeds = {
        change.seat: change.seed
        for _, change in seat_changes(_session(manager, game_id).log)
    }
    assert len(set(seeds.values())) == 2
    manager.restore_game(manager.save_document(game_id))


def test_every_change_of_hands_is_saved_and_an_unwatched_game_at_each_turn() -> None:
    """The autosave (``add_hand_over_listener``) comes at each change of
    hands; when the AI plays every person's place, at each AI turn end."""

    manager = GameSessionManager(pace_unit=0.0, default_ai_pace="normal")
    calls: list[int] = []
    manager.add_hand_over_listener(
        lambda game: calls.append(len(_session(manager, game).steps))
    )
    manager, game_id = _game(manager)
    _play_until(manager, game_id, lambda s: s["round_number"] == 2 and _owner(s) == 0)
    calls.clear()
    manager.hand_to_ai(game_id, 1)
    manager.wait_for_ai(game_id)
    assert calls, "the hand-over was not saved"
    calls.clear()
    manager.take_back(game_id, 1)
    assert len(calls) == 1
    calls.clear()

    manager.hand_to_ai(game_id, 0)
    manager.hand_to_ai(game_id, 1)
    manager.wait_for_ai(game_id, timeout=120)
    assert manager.summary(game_id)["finished"] is True
    # Saved along the way, not only at the end.
    assert len(calls) > 10
    assert calls[1] < calls[-1]


def test_a_seat_changes_hands_only_while_the_game_runs() -> None:
    manager = GameSessionManager(access=AccessMode.REMOTE, admin_key=ADMIN_KEY)
    room = manager.create_game(
        TWO_PEOPLE, game_seed=SEED, seats_at_start=True, credentials=ADMIN
    )
    with pytest.raises(GameNotStartedError):
        manager.hand_to_ai(str(room["game_id"]), 0, credentials=ADMIN)

    manager, game_id = _game()
    manager.hand_to_ai(game_id, 0)
    manager.hand_to_ai(game_id, 1)
    with pytest.raises(SessionError, match="the game is over"):
        manager.take_back(game_id, 1)


def test_the_saved_steps_and_log_agree_after_changes() -> None:
    """Live log steps and the recorded steps stay one for one."""

    manager, game_id = _handed_and_taken_back()
    session = _session(manager, game_id)
    live = [
        entry.step
        for entry in session.log
        if isinstance(entry, LoggedStep) and not entry.undone
    ]
    assert live == session.steps
    assert all(
        isinstance(step, (DomainAction, ChanceOutcome)) for step in session.steps
    )
