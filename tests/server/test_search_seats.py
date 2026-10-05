"""Search seats (``search:<path>``) in the play server.

A search seat's decision costs about a second and a half on the browser's
default rules, so the session answers it on the game's worker thread rather
than inside the request that handed it over (``is_background_agent_kind``),
and a loaded save retraces its recorded answers rather than searching them
again (``ReplayableAgent``). The seats here search a small untrained file in
two worlds with two candidates, which keeps a game fast; everything else is
the seat a real game builds.
"""

import dataclasses
import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.agents import network_search_agent as search_module  # noqa: E402
from dune_imperium.agents.network_search_agent import (  # noqa: E402
    NetworkSearchAgent,
)
from dune_imperium.agents.registry import is_background_agent_kind  # noqa: E402
from dune_imperium.core.actions import DomainAction  # noqa: E402
from dune_imperium.core.observation import PlayerView  # noqa: E402
from dune_imperium.core.state import GameState, canonical_state_hash  # noqa: E402
from dune_imperium.rules.frames import FrameKind  # noqa: E402
from dune_imperium.server.session_log import undo_window  # noqa: E402
from dune_imperium.server.sessions import (  # noqa: E402
    GameSession,
    GameSessionManager,
    JsonObject,
    SessionError,
)

HUMAN_FIRST_SEED = 0  # seat 0 opens the first round
SEARCH_FIRST_SEED = 5  # seat 1 opens it
# Base rules, seat 0 taking action 0 against three search seats that answer
# their first legal action (``quick_search``): seat 3 plays Covert Operation,
# seat 0 discards for it first (step 338), and seat 1 is asked to discard
# next while seat 0's discard is still in seat 0's undo window.
COVERT_OPERATION_SEED = 7


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def _list(value: object) -> list[object]:
    assert isinstance(value, list)
    return value


@pytest.fixture
def search_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A ``search:`` seat kind over a small untrained file, searching less."""

    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.training.checkpoint import save_checkpoint
    from dune_imperium.training.network import PolicyValueNetwork

    base = RulesetConfig()
    codec = ActionCodec(base)
    torch.manual_seed(0)
    path = tmp_path / "policy.pt"
    save_checkpoint(
        path,
        PolicyValueNetwork(codec.size, hidden=(32,)),
        ruleset=base.identifier,
        iteration=1,
        codec=codec,
    )

    class _Smaller(NetworkSearchAgent):
        def __init__(
            self, path: str, *, seed: int, config: RulesetConfig | None = None
        ) -> None:
            super().__init__(path, seed=seed, rollouts=2, candidates=2, config=config)

    # ``make_agent`` imports the class from the module when a seat is built.
    monkeypatch.setattr(search_module, "NetworkSearchAgent", _Smaller)
    return f"search:{path}"


class _Gate:
    """Holds every search seat's answer while closed (it starts open)."""

    def __init__(self) -> None:
        self.asked = threading.Event()
        self.opened = threading.Event()
        self.opened.set()
        self.states: list[GameState] = []

    def close(self) -> None:
        self.asked.clear()
        self.opened.clear()

    def open(self) -> None:
        self.opened.set()

    def pass_through(self, state: GameState) -> None:
        self.states.append(state)
        self.asked.set()
        assert self.opened.wait(30), "the test never opened the gate"


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Gate]:
    """Route every searched answer through a gate the test controls."""

    held = _Gate()
    search = NetworkSearchAgent.choose_action_with_state

    def gated(
        agent: NetworkSearchAgent,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        held.pass_through(state)
        return search(agent, state, observation, legal_actions)

    monkeypatch.setattr(NetworkSearchAgent, "choose_action_with_state", gated)
    yield held
    # A worker still held must not outlive the test blocked.
    held.open()


def _covert_operation_player(state: GameState) -> int | None:
    """The seat whose Covert Operation the pending discard answers, if any."""

    top = state.decision_stack[-1]
    if top.kind != FrameKind.OPPONENT_CARD_DISCARD:
        return None
    player = dict(top.context)["covert_operation_owner"]
    assert isinstance(player, int)
    return player


@pytest.fixture
def quick_search(monkeypatch: pytest.MonkeyPatch) -> Iterator[_Gate]:
    """Search seats that answer their first legal action at once.

    Still background seats, only without the playouts, so a game reaches a
    late position in a second. The gate holds just the discards a Covert
    Operation asks of them: answers inside another seat's Agent turn.
    """

    held = _Gate()

    def first(
        agent: NetworkSearchAgent,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        if _covert_operation_player(state) is not None:
            held.pass_through(state)
        return legal_actions[0]

    monkeypatch.setattr(NetworkSearchAgent, "choose_action_with_state", first)
    yield held
    held.open()


class _Rings:
    """A change listener that records every ring."""

    def __init__(self) -> None:
        self.payloads: list[JsonObject | None] = []

    def __call__(self, game_id: str, payload: JsonObject | None) -> None:
        self.payloads.append(payload)


def _within[T](seconds: float, call: Callable[[], T]) -> T:
    """Run ``call`` on another thread; fail if it does not return in time.

    A request that blocked on a session lock held by the search would hang
    the test instead of failing it.
    """

    results: list[T] = []
    thread = threading.Thread(target=lambda: results.append(call()), daemon=True)
    thread.start()
    thread.join(seconds)
    assert results, "the call did not return while the seat was thinking"
    return results[0]


def _worker(game_id: str) -> threading.Thread | None:
    return next(
        (
            thread
            for thread in threading.enumerate()
            if thread.name == f"ai-worker-{game_id}"
        ),
        None,
    )


def _settled(manager: GameSessionManager, summary: JsonObject) -> JsonObject:
    game_id = _text(summary["game_id"])
    manager.wait_for_ai(game_id)
    return manager.summary(game_id)


def _advance(
    manager: GameSessionManager, summary: JsonObject, steps: int
) -> JsonObject:
    """Seat 0 confirms its turn ends and otherwise takes legal action 0,
    each time once the search seats have answered."""

    game_id = _text(summary["game_id"])
    for _ in range(steps):
        summary = _settled(manager, summary)
        if summary["finished"]:
            break
        revision = _int(summary["revision"])
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(game_id, seat=0, revision=revision)
        else:
            summary = manager.apply_action(game_id, seat=0, revision=revision, index=0)
    return _settled(manager, summary)


def _held_or_rested(manager: GameSessionManager, game_id: str, gate: _Gate) -> bool:
    """Wait until the gate holds a search seat (True) or none thinks (False)."""

    session = manager._sessions[game_id]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if gate.asked.is_set():
            return True
        with session.lock:
            if not session.ai_worker and session.thinking is None:
                return False
        time.sleep(0.002)
    raise AssertionError("the search seats neither answered nor reached the gate")


def _play_until_held(
    manager: GameSessionManager, summary: JsonObject, gate: _Gate
) -> JsonObject:
    """Play seat 0 like ``_advance`` until the gate holds a search seat."""

    game_id = _text(summary["game_id"])
    for _ in range(1000):
        if _held_or_rested(manager, game_id, gate):
            return _within(5, lambda: manager.summary(game_id))
        summary = manager.summary(game_id)
        assert not summary["finished"], "the game ended before the gate held"
        revision = _int(summary["revision"])
        if summary["confirmation"] == 0:
            manager.confirm_turn(game_id, seat=0, revision=revision)
        else:
            manager.apply_action(game_id, seat=0, revision=revision, index=0)
    raise AssertionError("the gate never held a search seat")


def _unguarded_undo_window(manager: GameSessionManager, game_id: str) -> int:
    """Seat 0's undo window as the log and the press would leave it."""

    session = manager._sessions[game_id]
    with session.lock:
        unsealed = len(session.steps) - session.undo_floor
        return max(0, min(undo_window(session.log, 0), unsealed))


def _seat_steps(steps: object, seats: set[int]) -> int:
    assert isinstance(steps, list)
    return sum(
        1 for step in steps if isinstance(step, DomainAction) and step.actor in seats
    )


# -- which seats think in the background ------------------------------------


def test_only_search_seats_think_in_the_background() -> None:
    assert is_background_agent_kind("search:/some/policy.pt")
    for kind in ("human", "app_ai", "heuristic", "random", "rollout", "checkpoint:x"):
        assert not is_background_agent_kind(kind)

    # Every other seat still answers inside the request.
    manager = GameSessionManager()
    seats = ("human", "app_ai", "heuristic", "rollout")
    summary = manager.create_game(seats, game_seed=SEARCH_FIRST_SEED)
    assert summary["thinking"] is None
    assert _obj(summary["decision"])["owner"] == 0
    assert _worker(_text(summary["game_id"])) is None


# -- the server's own search AI (the seat kind ``search``) -------------------


def test_a_bare_search_seat_plays_the_servers_checkpoint(
    search_kind: str, tmp_path: Path
) -> None:
    """``search`` seats ``search:<the real file>`` of the manager's network.

    The server is handed a symlink (``~/.dune-imperium/search.pt`` is one),
    resolved when it starts: the game and its save name the file the link
    pointed at, and repointing the link afterwards changes neither.
    """

    network = Path(search_kind.removeprefix("search:")).resolve()
    link = tmp_path / "links" / "search.pt"
    link.parent.mkdir()
    link.symlink_to(network)
    manager = GameSessionManager(search_checkpoint=link)
    assert manager.search_checkpoint == network

    summary = manager.create_game(
        ("human", "search", "heuristic", "search"), game_seed=HUMAN_FIRST_SEED
    )
    game_id = _text(summary["game_id"])
    seated = f"search:{network}"
    assert summary["seats"] == ["human", seated, "heuristic", seated]
    assert [_obj(player)["kind"] for player in _list(summary["players"])] == [
        "human",
        seated,
        "heuristic",
        seated,
    ]
    assert isinstance(manager._sessions[game_id].agents[1], NetworkSearchAgent)
    summary = _advance(manager, summary, 12)
    assert _seat_steps(manager._sessions[game_id].steps, {1, 3}) > 0

    document = _obj(_roundtrip(manager.save_game(game_id)))
    assert document["seats"] == ["human", seated, "heuristic", seated]

    other = tmp_path / "other.pt"
    other.write_bytes(network.read_bytes())
    link.unlink()
    link.symlink_to(other)
    restored = manager.restore_game(document)
    assert restored["seats"] == ["human", seated, "heuristic", seated]
    manager.wait_for_ai(_text(restored["game_id"]))
    # Only a restart reads the link again.
    later = manager.create_game(
        ("human", "search", "heuristic", "heuristic"), game_seed=HUMAN_FIRST_SEED
    )
    assert _list(later["seats"])[1] == seated
    manager.wait_for_ai(_text(later["game_id"]))


def test_a_bare_search_seat_is_refused_without_a_checkpoint() -> None:
    manager = GameSessionManager()
    assert manager.search_checkpoint is None

    with pytest.raises(SessionError, match="--search-checkpoint"):
        manager.create_game(("human", "search", "heuristic", "heuristic"))
    assert manager.list_games() == []


def test_an_explicit_search_path_still_seats_that_file(search_kind: str) -> None:
    # API users name the file themselves, with or without a server network.
    manager = GameSessionManager()

    summary = manager.create_game(
        ("human", search_kind, "heuristic", "heuristic"), game_seed=HUMAN_FIRST_SEED
    )

    assert _list(summary["seats"])[1] == search_kind
    manager.wait_for_ai(_text(summary["game_id"]))


# -- thinking off the request ------------------------------------------------


def test_creation_returns_while_the_search_seats_think(
    search_kind: str, gate: _Gate
) -> None:
    manager = GameSessionManager()
    rings = _Rings()
    manager.add_change_listener(rings)
    gate.close()

    summary = manager.create_game(
        ("human", search_kind, search_kind, search_kind),
        game_seed=SEARCH_FIRST_SEED,
    )

    # Seat 1 opens the round: creation hands it over instead of answering.
    game_id = _text(summary["game_id"])
    assert summary["thinking"] == 1
    assert _obj(summary["decision"])["owner"] == 1
    assert gate.asked.wait(10)
    # The search holds no lock: the table is served meanwhile.
    thinking = _within(5, lambda: manager.summary(game_id))
    assert thinking["thinking"] == 1
    assert thinking["revision"] == summary["revision"]
    snapshot = _within(5, lambda: manager.snapshot(game_id, 0))
    assert snapshot["actions"] is None
    assert _within(5, lambda: manager.doorbell(game_id))["thinking"] == 1
    assert rings.payloads == []

    gate.open()
    manager.wait_for_ai(game_id)

    rested = manager.summary(game_id)
    assert rested["thinking"] is None
    assert _obj(rested["decision"])["owner"] == 0
    assert _int(rested["revision"]) > _int(summary["revision"])
    steps = manager._sessions[game_id].steps
    background = _seat_steps(steps, {1, 2, 3})
    assert background >= 3
    # One ring per background step, in order, the last one at rest.
    assert len(rings.payloads) == background
    bells = [_obj(payload) for payload in rings.payloads]
    sequence = [_int(bell["seq"]) for bell in bells]
    assert sequence == sorted(set(sequence))
    assert bells[-1]["thinking"] is None
    assert bells[-1]["revision"] == rested["revision"]
    assert all(bell["thinking"] in (1, 2, 3) for bell in bells[:-1])
    assert not manager._sessions[game_id].ai_worker


def test_a_human_hand_over_returns_before_the_search_answers(
    search_kind: str, gate: _Gate
) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(
        ("human", search_kind, "heuristic", "heuristic"),
        game_seed=HUMAN_FIRST_SEED,
    )
    game_id = _text(summary["game_id"])
    assert summary["thinking"] is None

    gate.close()
    for _ in range(200):
        revision = _int(summary["revision"])
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(game_id, seat=0, revision=revision)
        else:
            summary = manager.apply_action(game_id, seat=0, revision=revision, index=0)
        if summary["thinking"] is not None:
            break
    else:  # pragma: no cover - seat 1 decides within seat 0's first turns
        raise AssertionError("the search seat never got a decision")

    # The press (or step) came back while the seat was still to answer.
    assert summary["thinking"] == 1
    assert gate.asked.wait(10)
    assert not gate.opened.is_set()
    thinking = _within(5, lambda: manager.snapshot(game_id, 0))
    assert _obj(thinking["summary"])["thinking"] == 1
    assert thinking["actions"] is None
    # Nothing can be taken back from under a thinking seat.
    assert _obj(thinking["summary"])["undo"] == []
    with pytest.raises(SessionError, match="take back at most 0"):
        manager.undo(game_id, 0, revision=_int(summary["revision"]))
    with pytest.raises(SessionError, match="another seat"):
        manager.apply_action(
            game_id, seat=0, revision=_int(summary["revision"]), index=0
        )

    gate.open()
    rested = _settled(manager, summary)
    assert rested["thinking"] is None
    assert _int(rested["revision"]) > _int(summary["revision"])
    assert rested["finished"] or _obj(rested["decision"])["owner"] == 0


def test_an_answer_for_a_state_that_has_moved_on_is_dropped(
    search_kind: str, gate: _Gate, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The worker applies an answer only to the state it was asked about.

    Nothing in the session replaces the state under a thinking seat today
    (an undo is refused, a load is a new session), so the test does it by
    hand: the same position as a new object, which the first answer was
    not computed from.
    """

    answers: list[DomainAction] = []

    def scripted(
        agent: NetworkSearchAgent,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        gate.pass_through(state)
        # The first answer is the last legal action, every later one the first.
        answer = legal_actions[-1] if not answers else legal_actions[0]
        answers.append(answer)
        return answer

    monkeypatch.setattr(NetworkSearchAgent, "choose_action_with_state", scripted)
    manager = GameSessionManager()
    gate.close()
    summary = manager.create_game(
        ("human", search_kind, "heuristic", "heuristic"),
        game_seed=SEARCH_FIRST_SEED,
    )
    game_id = _text(summary["game_id"])
    session = manager._sessions[game_id]
    assert gate.asked.wait(10)
    asked = gate.states[0]
    steps_before = len(session.steps)
    with session.lock:
        assert session.state is asked
        session.state = dataclasses.replace(asked)
    gate.open()
    manager.wait_for_ai(game_id)

    # Asked again from the new object, and only that answer was applied.
    assert gate.states[1] is not asked
    assert gate.states[1] == asked
    assert answers[0] != answers[1]
    assert session.steps[steps_before] == answers[1]


def test_deleting_the_game_stops_its_worker(search_kind: str, gate: _Gate) -> None:
    manager = GameSessionManager()
    rings = _Rings()
    manager.add_change_listener(rings)
    gate.close()
    summary = manager.create_game(
        ("human", search_kind, search_kind, search_kind),
        game_seed=SEARCH_FIRST_SEED,
    )
    game_id = _text(summary["game_id"])
    session = manager._sessions[game_id]
    assert gate.asked.wait(10)
    worker = _worker(game_id)
    assert worker is not None
    steps = len(session.steps)

    manager.delete(game_id)
    gate.open()
    worker.join(10)

    assert not worker.is_alive()
    assert len(session.steps) == steps
    assert not session.ai_worker
    # The deletion was the last ring: the answer was dropped, not published.
    assert rings.payloads == [None]


def test_a_failing_search_falls_back_and_the_game_goes_on(
    search_kind: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken(*_: object) -> DomainAction:
        raise RuntimeError("search exploded")

    greedy = NetworkSearchAgent.choose_action
    view_calls: list[int] = []

    def greedy_once_broken(
        agent: NetworkSearchAgent,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        view_calls.append(1)
        if len(view_calls) == 1:
            raise RuntimeError("greedy exploded too")
        return greedy(agent, observation, legal_actions)

    monkeypatch.setattr(NetworkSearchAgent, "choose_action_with_state", broken)
    monkeypatch.setattr(NetworkSearchAgent, "choose_action", greedy_once_broken)
    manager = GameSessionManager()
    with caplog.at_level(logging.ERROR, logger="dune_imperium.server.sessions"):
        summary = manager.create_game(
            ("human", search_kind, search_kind, search_kind),
            game_seed=SEARCH_FIRST_SEED,
        )
        game_id = _text(summary["game_id"])
        manager.wait_for_ai(game_id)

    rested = manager.summary(game_id)
    assert rested["thinking"] is None
    assert _obj(rested["decision"])["owner"] == 0
    background = _seat_steps(manager._sessions[game_id].steps, {1, 2, 3})
    messages = [record.getMessage() for record in caplog.records]
    assert sum("failed to answer" in text for text in messages) == background
    assert sum("failed again" in text for text in messages) == 1
    assert len(view_calls) == background


def test_a_failing_worker_step_frees_the_table(
    search_kind: str,
    quick_search: _Gate,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A step the engine refuses stops the worker without stranding the game.

    The seat stops thinking and the table hears it, so seat 0 gets back the
    undo its own discard had (the same failure inside a request would have
    left it too), takes the discard back and plays on; nothing retried the
    failed step in between.
    """

    applied = GameSessionManager._agent_step_locked
    failed: list[int] = []

    def refused_once(
        manager: GameSessionManager,
        session: GameSession,
        seat: int,
        action: DomainAction,
    ) -> bool:
        if not failed and _covert_operation_player(session.state) is not None:
            failed.append(seat)
            raise RuntimeError("the engine refused the discard")
        return applied(manager, session, seat, action)

    manager = GameSessionManager()
    rings = _Rings()
    manager.add_change_listener(rings)
    quick_search.close()
    summary = manager.create_game(
        ("human", search_kind, search_kind, search_kind),
        game_seed=COVERT_OPERATION_SEED,
    )
    game_id = _text(summary["game_id"])
    held_session = manager._sessions[game_id]
    held = _play_until_held(manager, summary, quick_search)
    window = _unguarded_undo_window(manager, game_id)
    assert window > 0
    steps = len(held_session.steps)
    monkeypatch.setattr(GameSessionManager, "_agent_step_locked", refused_once)
    rings.payloads.clear()

    with caplog.at_level(logging.ERROR, logger="dune_imperium.server.sessions"):
        quick_search.open()
        manager.wait_for_ai(game_id, timeout=10)

    assert failed == [_obj(held["decision"])["owner"]]
    assert any("AI worker" in record.getMessage() for record in caplog.records)
    worker = _worker(game_id)
    if worker is not None:
        worker.join(10)
    assert not held_session.ai_worker
    stopped = manager.summary(game_id)
    assert stopped["thinking"] is None
    assert stopped["revision"] == held["revision"]
    assert len(held_session.steps) == steps
    # The tables heard the seat stop thinking.
    assert [_obj(bell)["thinking"] for bell in rings.payloads] == [None]
    assert _obj(rings.payloads[0])["revision"] == held["revision"]
    # The undo the thinking seat had kept closed is open again.
    assert stopped["undo"] == [{"seat": 0, "steps": window}]
    taken_back = manager.undo(
        game_id, 0, revision=_int(stopped["revision"]), steps=window
    )
    assert _obj(taken_back["decision"])["owner"] == 0

    # Playing on hands the discard over again, and this time it goes in.
    rested = _advance(manager, taken_back, 1)
    assert failed == [_obj(held["decision"])["owner"]]
    assert len(held_session.steps) > steps
    assert rested["thinking"] is None


def test_a_worker_step_that_fails_after_it_was_applied_still_rings(
    search_kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    advance = GameSessionManager._advance_locked
    failed: list[int] = []

    def failing_on_the_worker(
        manager: GameSessionManager, session: GameSession
    ) -> None:
        if not failed and threading.current_thread().name.startswith("ai-worker-"):
            failed.append(len(session.steps))
            raise RuntimeError("the advance failed")
        advance(manager, session)

    manager = GameSessionManager()
    rings = _Rings()
    manager.add_change_listener(rings)
    monkeypatch.setattr(GameSessionManager, "_advance_locked", failing_on_the_worker)
    summary = manager.create_game(
        ("human", search_kind, search_kind, search_kind),
        game_seed=SEARCH_FIRST_SEED,
    )
    game_id = _text(summary["game_id"])
    session = manager._sessions[game_id]
    manager.wait_for_ai(game_id, timeout=30)

    # Seat 1's answer went in before the advance after it failed.
    assert failed == [len(session.steps)]
    last = session.steps[-1]
    assert isinstance(last, DomainAction) and last.actor == 1
    stopped = manager.summary(game_id)
    assert stopped["thinking"] is None
    assert _int(stopped["revision"]) > _int(summary["revision"])
    assert not session.ai_worker
    # ...and the tables heard of it.
    assert len(rings.payloads) == 1
    bell = _obj(rings.payloads[0])
    assert bell["revision"] == stopped["revision"]
    assert bell["thinking"] is None


def test_the_hand_over_listener_hears_the_search_seats_reach_a_human(
    search_kind: str,
) -> None:
    manager = GameSessionManager()
    heard: list[object] = []

    def autosave(game_id: str) -> None:
        # Runs after the lock is released, on the worker: it may read.
        heard.append(manager.summary(game_id)["thinking"])
        manager.save_document(game_id)

    manager.add_hand_over_listener(autosave)
    summary = manager.create_game(
        ("human", search_kind, search_kind, search_kind),
        game_seed=SEARCH_FIRST_SEED,
    )
    manager.wait_for_ai(_text(summary["game_id"]))

    assert heard == [None]


# -- saving and loading --------------------------------------------------------


def _roundtrip(document: object) -> object:
    return json.loads(json.dumps(document))


def test_a_search_seat_restores_without_searching_again(
    search_kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A load retraces the search seat's answers instead of playing them out.

    The restored seat must still resume where the saved one stood: the two
    sessions answer the same human moves with the same steps afterwards.
    """

    seats = ("human", search_kind, "heuristic", "random")
    manager = GameSessionManager()
    original = _advance(manager, manager.create_game(seats, game_seed=34), 30)
    game_id = _text(original["game_id"])
    session = manager._sessions[game_id]
    assert _seat_steps(session.steps, {1}) > 10
    document = manager.save_game(game_id)

    def no_playouts(*_: object) -> float:
        raise AssertionError("a restore must not search again")

    with monkeypatch.context() as patch:
        patch.setattr(NetworkSearchAgent, "_playout", no_playouts)
        restored = manager.restore_game(_roundtrip(document))
    assert restored["thinking"] is None
    twin = manager._sessions[_text(restored["game_id"])]
    assert twin.steps == session.steps
    assert canonical_state_hash(twin.state) == canonical_state_hash(session.state)

    saved_steps = len(session.steps)
    original = _advance(manager, original, 30)
    restored = _advance(manager, restored, 30)
    assert _seat_steps(session.steps[saved_steps:], {1}) > 5
    assert twin.steps == session.steps
    assert restored["revision"] == original["revision"]


def test_a_game_saved_while_a_seat_thinks_thinks_again_when_loaded(
    search_kind: str, gate: _Gate
) -> None:
    manager = GameSessionManager()
    gate.close()
    original = manager.create_game(
        ("human", search_kind, search_kind, search_kind),
        game_seed=SEARCH_FIRST_SEED,
    )
    assert gate.asked.wait(10)
    document = manager.save_game(_text(original["game_id"]))

    gate.open()
    restored = manager.restore_game(_roundtrip(document))
    assert restored["thinking"] == 1

    original = _settled(manager, original)
    restored = _settled(manager, restored)
    first = manager._sessions[_text(original["game_id"])]
    second = manager._sessions[_text(restored["game_id"])]
    assert second.steps == first.steps
    assert restored["revision"] == original["revision"]
