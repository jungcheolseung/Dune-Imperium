"""Tests for save documents, the save file store, and replay review."""

import json
from pathlib import Path

import pytest

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.server.persistence import (
    SAVE_FORMAT,
    SAVE_FORMAT_VERSION,
    SaveError,
    SaveStore,
    UnknownSaveError,
    parse_save_document,
)
from dune_imperium.server.sessions import (
    GameSessionManager,
    JsonObject,
    SeatAccessError,
    SessionError,
)

HUMAN_FIRST = ("human", "heuristic", "heuristic", "heuristic")


def _obj(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _rows(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    return [_obj(item) for item in value]


def _int(value: object) -> int:
    assert isinstance(value, int)
    return value


def _text(value: object) -> str:
    assert isinstance(value, str)
    return value


def _texts(value: object) -> list[str]:
    assert isinstance(value, list)
    return [_text(item) for item in value]


def _advance(
    manager: GameSessionManager,
    summary: JsonObject,
    steps: int,
) -> JsonObject:
    """Apply the first legal action of seat 0 ``steps`` times."""

    game_id = _text(summary["game_id"])
    for _ in range(steps):
        if summary["finished"]:
            break
        if summary["confirmation"] == 0:
            summary = manager.confirm_turn(
                game_id, seat=0, revision=_int(summary["revision"])
            )
            continue
        summary = manager.apply_action(
            game_id, seat=0, revision=_int(summary["revision"]), index=0
        )
    return summary


def _finish(manager: GameSessionManager, summary: JsonObject) -> JsonObject:
    summary = _advance(manager, summary, 2_000)
    assert summary["finished"] is True
    return summary


def _roundtrip(document: object) -> object:
    """Prove the document survives JSON before handing it to a load."""

    return json.loads(json.dumps(document))


@pytest.fixture(scope="module")
def finished_game() -> tuple[GameSessionManager, JsonObject]:
    """One finished human-seat game shared by the read-only tests."""

    manager = GameSessionManager()
    summary = _finish(manager, manager.create_game(HUMAN_FIRST, game_seed=14))
    return manager, summary


def test_save_documents_stamp_current_versions() -> None:
    manager = GameSessionManager()
    summary = _advance(manager, manager.create_game(HUMAN_FIRST, game_seed=31), 3)

    document = manager.save_game(_text(summary["game_id"]), name="테스트 저장")

    assert document["format"] == SAVE_FORMAT
    assert document["format_version"] == SAVE_FORMAT_VERSION
    assert document["action_codec_version"] == ACTION_CODEC_VERSION
    assert _text(document["ruleset_version"])
    assert _text(document["content_version"])
    assert document["name"] == "테스트 저장"
    assert document["seats"] == list(HUMAN_FIRST)
    assert document["game_seed"] == 31
    assert document["finished"] is False
    assert document["source_game_id"] == summary["game_id"]
    assert _text(document["expected_state_hash"])
    steps = _rows(document["steps"])
    # Setup chance resolves inside ``reset``; chance steps only appear once
    # the game hits a reshuffle, so early saves may hold actions only.
    assert {"action"} <= {step["type"] for step in steps} <= {"action", "chance"}
    json.dumps(document)


def test_a_restored_game_continues_like_the_unsaved_session() -> None:
    manager = GameSessionManager()
    original = _advance(manager, manager.create_game(HUMAN_FIRST, game_seed=31), 5)

    document = manager.save_game(_text(original["game_id"]))
    restored = manager.restore_game(_roundtrip(document))

    assert restored["game_id"] != original["game_id"]
    for field in ("revision", "phase", "round_number", "decision", "seats"):
        assert restored[field] == original[field], field

    original_end = _finish(manager, original)
    restored_end = _finish(manager, restored)
    assert restored_end["standings"] == original_end["standings"]
    assert restored_end["revision"] == original_end["revision"]


def test_a_search_agent_seat_restores_from_a_save() -> None:
    manager = GameSessionManager()
    seats = ("human", "rollout", "heuristic", "random")
    original = _advance(manager, manager.create_game(seats, game_seed=34), 8)

    document = manager.save_game(_text(original["game_id"]))
    restored = manager.restore_game(_roundtrip(document))

    assert restored["seats"] == list(seats)
    for field in ("revision", "phase", "round_number", "decision"):
        assert restored[field] == original[field], field


def _tiny_search_seat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A ``search:`` seat kind over a small untrained file, searching less.

    The seat searches two candidates in two worlds instead of five in eight,
    which keeps a test game fast; everything else is the seat a game builds.
    """

    torch = pytest.importorskip("torch")
    from dune_imperium import RulesetConfig
    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.agents import network_search_agent as module
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

    class _Smaller(module.NetworkSearchAgent):
        def __init__(
            self, path: str, *, seed: int, config: RulesetConfig | None = None
        ) -> None:
            super().__init__(path, seed=seed, rollouts=2, candidates=2, config=config)

    monkeypatch.setattr(module, "NetworkSearchAgent", _Smaller)
    return f"search:{path}"


def test_a_search_seat_restores_without_searching_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A load retraces the search seat's answers instead of playing them out.

    The restored seat must still resume where the saved one stood: the two
    sessions answer the same human moves with the same steps afterwards.
    """

    from dune_imperium.agents.network_search_agent import NetworkSearchAgent
    from dune_imperium.core.actions import DomainAction
    from dune_imperium.core.state import canonical_state_hash

    seats = ("human", _tiny_search_seat(tmp_path, monkeypatch), "heuristic", "random")
    manager = GameSessionManager()
    original = _advance(manager, manager.create_game(seats, game_seed=34), 30)
    game_id = _text(original["game_id"])
    session = manager._sessions[game_id]

    def search_seat_steps(steps: object) -> int:
        assert isinstance(steps, list)
        return sum(
            1 for step in steps if isinstance(step, DomainAction) and step.actor == 1
        )

    assert search_seat_steps(session.steps) > 10
    document = manager.save_game(game_id)

    def no_playouts(*_: object) -> float:
        raise AssertionError("a restore must not search again")

    with monkeypatch.context() as patch:
        patch.setattr(NetworkSearchAgent, "_playout", no_playouts)
        restored = manager.restore_game(_roundtrip(document))
    twin = manager._sessions[_text(restored["game_id"])]
    assert twin.steps == session.steps
    assert canonical_state_hash(twin.state) == canonical_state_hash(session.state)

    saved_steps = len(session.steps)
    original = _advance(manager, original, 30)
    restored = _advance(manager, restored, 30)
    assert search_seat_steps(session.steps[saved_steps:]) > 5
    assert twin.steps == session.steps
    assert restored["revision"] == original["revision"]


def test_a_finished_game_can_be_saved_and_restored(
    finished_game: tuple[GameSessionManager, JsonObject],
) -> None:
    manager, summary = finished_game

    document = manager.save_game(_text(summary["game_id"]))
    assert document["finished"] is True
    restored = manager.restore_game(_roundtrip(document))

    assert restored["finished"] is True
    assert restored["standings"] == summary["standings"]


def test_restoring_rejects_stale_or_tampered_documents(
    finished_game: tuple[GameSessionManager, JsonObject],
) -> None:
    manager, summary = finished_game
    document = manager.save_game(_text(summary["game_id"]))

    stale = {**document, "action_codec_version": ACTION_CODEC_VERSION - 1}
    with pytest.raises(SaveError, match="action_codec_version"):
        manager.restore_game(_roundtrip(stale))

    with pytest.raises(SaveError, match="not a dune-imperium save"):
        manager.restore_game(_roundtrip({**document, "format": "other"}))

    with pytest.raises(SaveError, match="state hash"):
        manager.restore_game(
            _roundtrip({**document, "expected_state_hash": "tampered"})
        )

    steps = _rows(document["steps"])
    tampered_index = next(
        index
        for index, step in enumerate(steps)
        if step["type"] == "chance" and len(_texts(step["values"])) >= 2
    )
    values = _texts(steps[tampered_index]["values"])
    values[0], values[1] = values[1], values[0]
    tampered_steps: list[object] = list(steps)
    tampered_steps[tampered_index] = {**steps[tampered_index], "values": values}
    with pytest.raises(SaveError, match=f"save step {tampered_index} "):
        manager.restore_game(
            _roundtrip({**document, "steps": tampered_steps})
        )

    bad_seats = {**document, "seats": ["human", "alien", "random", "random"]}
    with pytest.raises(SessionError, match="unknown seat assignment"):
        manager.restore_game(_roundtrip(bad_seats))


def test_the_save_store_lists_reads_and_deletes(tmp_path: Path) -> None:
    store = SaveStore(tmp_path / "saves")
    assert store.list() == []

    manager = GameSessionManager()
    summary = _advance(manager, manager.create_game(HUMAN_FIRST, game_seed=31), 1)
    document = manager.save_game(_text(summary["game_id"]), name="슬롯 1")

    metadata = store.write(document)
    save_id = _text(metadata["save_id"])
    assert "steps" not in metadata
    assert metadata["name"] == "슬롯 1"
    assert _int(metadata["step_count"]) > 0
    assert store.list() == [metadata]

    stored = store.read(save_id)
    assert _rows(stored["steps"])
    restored = manager.restore_game(stored)
    assert restored["revision"] == summary["revision"]

    (tmp_path / "saves" / ("f" * 32 + ".json")).write_text("{", encoding="utf-8")
    listing = store.list()
    assert len(listing) == 2
    assert any(entry.get("error") for entry in listing)

    store.delete(save_id)
    with pytest.raises(UnknownSaveError):
        store.read(save_id)
    with pytest.raises(UnknownSaveError):
        store.delete(save_id)
    with pytest.raises(UnknownSaveError):
        store.read("../outside")


def test_review_replays_a_finished_game_for_a_human_seat(
    finished_game: tuple[GameSessionManager, JsonObject],
) -> None:
    manager, summary = finished_game
    game_id = _text(summary["game_id"])

    review = manager.review(game_id, 0)
    steps = _rows(review["steps"])
    assert review["step_count"] == len(steps)
    assert steps

    kinds = {step["type"] for step in steps}
    assert kinds == {"action", "chance"}
    # A finished game is fully disclosed (OQ-010 ruling 4): every step is
    # labelled in full whoever acted, and chance outcomes carry their values.
    for step in steps:
        if step["type"] == "chance":
            assert _text(step["decision_id"])
            assert _texts(step["values"])
        else:
            assert _text(step["action_id"])
            assert isinstance(step["arguments"], dict)
    assert any(step["type"] == "action" and step["actor"] == 0 for step in steps)
    assert any(step["type"] == "action" and step["actor"] != 0 for step in steps)

    final = manager.review_state(game_id, 0, len(steps))
    assert final["phase"] == "finished"
    assert final["view"] == manager.view(game_id, 0)
    start = manager.review_state(game_id, 0, 0)
    assert start["view"] != final["view"]
    json.dumps(review)
    json.dumps(final)

    # Every hidden zone is disclosed at every reviewed step, and the live
    # view of the finished game carries the same disclosure.
    disclosure = _obj(_obj(final["view"])["disclosure"])
    seats = _rows(disclosure["players"])
    assert [seat["player"] for seat in seats] == [0, 1, 2, 3]
    assert {"hand", "deck", "intrigue_cards"} <= set(seats[1])
    assert {"imperium_deck", "intrigue_deck", "contract_bank", "conflict_deck"} <= (
        set(disclosure)
    )
    start_disclosure = _obj(_obj(start["view"])["disclosure"])
    assert _texts(_rows(start_disclosure["players"])[1]["hand"])
    assert _texts(start_disclosure["imperium_deck"])

    # Any configured seat — including an AI seat — can be reviewed.
    assert manager.review(game_id, 1)["seat"] == 1
    assert _obj(manager.review_state(game_id, 1, 0)["view"])["player"] == 1

    with pytest.raises(SessionError, match="out of range"):
        manager.review_state(game_id, 0, len(steps) + 1)
    with pytest.raises(SessionError, match="out of range"):
        manager.review_state(game_id, 0, -1)
    with pytest.raises(SeatAccessError):
        manager.review(game_id, 4)
    with pytest.raises(SeatAccessError):
        manager.review_state(game_id, 4, 0)


def test_a_game_of_ai_seats_only_is_reviewed_with_its_whole_log() -> None:
    # Nobody can sit at such a game, so the review is the only way to watch
    # it: the timeline plus the unredacted log of what every step did.
    manager = GameSessionManager()
    summary = manager.create_game(("heuristic",) * 4, game_seed=3)
    game_id = _text(summary["game_id"])
    assert summary["finished"] is True
    assert "view" not in manager.snapshot(game_id)

    review = manager.review(game_id, 0)
    steps = _rows(review["steps"])
    log = _rows(review["log"])
    # No seat could take anything back: one live log entry per step, in order.
    assert [entry["index"] for entry in log] == list(range(len(steps)))
    assert not any(entry["type"] == "undo" or entry["undone"] for entry in log)
    for step, entry in zip(steps, log, strict=True):
        assert entry["type"] == step["type"]
        if step["type"] == "chance":
            assert entry["decision_id"] == step["decision_id"]
            assert entry["values"] == step["values"]
        else:
            assert (entry["actor"], entry["action_id"]) == (
                step["actor"],
                step["action_id"],
            )
            assert entry["arguments"] == step["arguments"]
    # Nothing is redacted once the game is over (OQ-010 ruling 4): a draw
    # names its cards to every reader, whichever seat is reviewed.
    kinds = {_text(event["kind"]) for entry in log for event in _rows(entry["events"])}
    assert "game_finished" in kinds
    assert manager.review(game_id, 2)["log"] == review["log"]
    assert not any(
        "(비공개)" in _obj(entry["arguments"]).values()
        for entry in log
        if entry["type"] == "action"
    )
    json.dumps(review)
    assert _obj(manager.review_state(game_id, 0, 0)["view"])["player"] == 0


def test_review_requires_a_finished_game() -> None:
    manager = GameSessionManager()
    summary = manager.create_game(HUMAN_FIRST, game_seed=13)
    game_id = _text(summary["game_id"])

    with pytest.raises(SessionError, match="finishes"):
        manager.review(game_id, 0)
    with pytest.raises(SessionError, match="finishes"):
        manager.review_state(game_id, 0, 0)
    # Disclosure is a post-game convention only (OQ-010 ruling 4).
    assert "disclosure" not in manager.view(game_id, 0)


def test_saves_keep_the_expansion_and_module_flags() -> None:
    # A save used to record only players/CHOAM/draft, so a Bloodlines + Tech
    # Module game reloaded as a base game and its recorded steps no longer
    # replayed. Older documents without the keys still read as "off".
    manager = GameSessionManager()
    created = manager.create_game(
        HUMAN_FIRST,
        game_seed=31,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        go_to_11=True,
        epic_game=True,
        arrakeen_scouts=True,
    )
    original = _advance(manager, created, 5)

    document = manager.save_game(_text(original["game_id"]))
    ruleset = _obj(document["ruleset"])
    assert ruleset["promo_cards"] is True
    assert ruleset["bloodlines"] is True
    assert ruleset["tech_module"] is True
    assert ruleset["immortality"] is True
    assert ruleset["go_to_11"] is True
    assert ruleset["epic_game"] is True
    assert ruleset["arrakeen_scouts"] is True

    restored = manager.restore_game(_roundtrip(document))
    for field in ("revision", "phase", "round_number", "decision", "seats"):
        assert restored[field] == original[field], field
    assert restored["bloodlines"] is True
    assert restored["tech_module"] is True
    assert restored["immortality"] is True
    assert restored["go_to_11"] is True
    assert restored["epic_game"] is True
    assert restored["arrakeen_scouts"] is True

    legacy = _obj(_roundtrip(manager.save_game(_text(original["game_id"]))))
    legacy_ruleset = dict(_obj(legacy["ruleset"]))
    for key in (
        "promo_cards",
        "bloodlines",
        "tech_module",
        "immortality",
        "go_to_11",
        "epic_game",
        "arrakeen_scouts",
    ):
        del legacy_ruleset[key]
    parsed = parse_save_document({**legacy, "ruleset": legacy_ruleset})
    assert parsed.replay.ruleset.bloodlines is False
    assert parsed.replay.ruleset.go_to_11 is False
    assert parsed.replay.ruleset.epic_game is False
    # Epic Game Mode needs no other option (OQ-092).
    epic_only = parse_save_document(
        {**legacy, "ruleset": {**legacy_ruleset, "epic_game": True}}
    )
    assert epic_only.replay.ruleset.epic_game is True
    # Go to 11 without Immortality is no ruleset (OQ-091).
    with pytest.raises(SaveError, match="Immortality"):
        parse_save_document(
            {**legacy, "ruleset": {**legacy_ruleset, "go_to_11": True}}
        )
    with pytest.raises(SaveError):
        parse_save_document(
            {**legacy, "ruleset": {**legacy_ruleset, "bloodlines": "yes"}}
        )


# --- app_ai seats ------------------------------------------------------------
#
# Restore builds fresh app_ai agents and asks them every recorded AI step
# again (``_replay_recorded_steps``): their memory and RNG are rebuilt only
# if each answer comes out the same, in this process or after a server
# restart in a new one.

APP_AI_SEATS = ("human", "app_ai", "app_ai_medium", "app_ai_easy")


def _ui_default_game(
    manager: GameSessionManager,
    seats: tuple[str, ...],
    game_seed: int,
    *,
    scouts: bool = False,
) -> JsonObject:
    """A game with the rule options the browser's setup screen starts with
    checked (CHOAM, the leader draft, the promo cards, Bloodlines, the Tech
    Module, Immortality, Go to 11, Epic Game Mode), Arrakeen Scouts if asked."""

    return manager.create_game(
        seats,
        game_seed=game_seed,
        choam_module=True,
        leader_draft=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        go_to_11=True,
        epic_game=True,
        arrakeen_scouts=scouts,
    )


def _undo_and_branch(manager: GameSessionManager, summary: JsonObject) -> JsonObject:
    """Play seat 0 until it may take a step back, take it back, then pick
    its last legal action instead of the first (a different branch)."""

    game_id = _text(summary["game_id"])
    for _ in range(200):
        if any(_obj(entry)["seat"] == 0 for entry in _rows(summary["undo"])):
            undone = manager.undo(game_id, 0, revision=_int(summary["revision"]))
            assert undone["undo_count"] == _int(summary["undo_count"]) + 1
            listing = _rows(manager.legal_actions(game_id, 0)["actions"])
            return manager.apply_action(
                game_id,
                seat=0,
                revision=_int(undone["revision"]),
                index=len(listing) - 1,
            )
        summary = _advance(manager, summary, 1)
    raise AssertionError("seat 0 never had a step to take back")


def _agent_state(manager: GameSessionManager, game_id: str) -> list[object]:
    """What each app_ai seat carries from decision to decision."""

    from dune_imperium.agents.app_ai import AppAIAgent

    session = manager._sessions[game_id]
    carried: list[object] = []
    for seat in sorted(session.agents):
        agent = session.agents[seat]
        assert isinstance(agent, AppAIAgent)
        carried.append(
            (
                seat,
                agent._rng.getstate(),
                agent.memory,
                dict(agent.mirrored),
                dict(agent.fallbacks),
            )
        )
    return carried


def _final(manager: GameSessionManager, summary: JsonObject) -> tuple[object, ...]:
    from dune_imperium.core.state import canonical_state_hash

    session = manager._sessions[_text(summary["game_id"])]
    return (
        tuple(session.steps),
        canonical_state_hash(session.state),
        summary["standings"],
        summary["revision"],
    )


@pytest.mark.parametrize(
    ("scouts", "game_seed"), [(False, 5), (True, 6)], ids=["ui-default", "scouts"]
)
def test_an_app_ai_game_restores_and_plays_on_like_the_unsaved_one(
    scouts: bool, game_seed: int
) -> None:
    manager = GameSessionManager()
    created = _ui_default_game(manager, APP_AI_SEATS, game_seed, scouts=scouts)
    summary = _advance(manager, created, 25)
    # A human undo before the save: app_ai never sees the undone branch.
    summary = _undo_and_branch(manager, summary)
    original = _advance(manager, summary, 30)
    assert original["finished"] is False
    assert _int(original["undo_count"]) == 1

    document = manager.save_game(_text(original["game_id"]))
    restored = manager.restore_game(_roundtrip(document))

    for field in ("revision", "phase", "round_number", "decision", "seats"):
        assert restored[field] == original[field], field
    assert restored["undo_count"] == 1
    # Every AI step regenerated: memory, RNG and counters are where they were.
    assert _agent_state(manager, _text(restored["game_id"])) == _agent_state(
        manager, _text(original["game_id"])
    )
    original_end = _final(manager, _finish(manager, original))
    restored_end = _final(manager, _finish(manager, restored))
    assert restored_end == original_end


_RESTORE_IN_A_NEW_PROCESS = """
import json, sys
from dune_imperium.core.state import canonical_state_hash
from dune_imperium.server.sessions import GameSessionManager

manager = GameSessionManager()
with open(sys.argv[1], encoding="utf-8") as handle:
    summary = manager.restore_game(json.load(handle))
game_id = summary["game_id"]
session = manager._sessions[game_id]
restored = canonical_state_hash(session.state)
for _ in range(2_000):
    if summary["finished"]:
        break
    if summary["confirmation"] == 0:
        summary = manager.confirm_turn(game_id, seat=0, revision=summary["revision"])
    else:
        summary = manager.apply_action(
            game_id, seat=0, revision=summary["revision"], index=0
        )
print(json.dumps({
    "string_hash": hash("app_ai"),
    "restored": restored,
    "final": canonical_state_hash(session.state),
    "standings": summary["standings"],
}))
"""


def test_an_app_ai_save_restores_in_a_process_with_another_hash_seed(
    tmp_path: Path,
) -> None:
    """Restart recovery: the server that loads an autosave is a new process,
    with another string-hash seed. A decision that followed the iteration
    order of a set of strings would replay differently there."""

    import os
    import subprocess
    import sys

    from dune_imperium.core.state import canonical_state_hash

    manager = GameSessionManager()
    created = _ui_default_game(manager, APP_AI_SEATS, 7, scouts=True)
    original = _advance(manager, created, 40)
    assert original["finished"] is False
    document = manager.save_game(_text(original["game_id"]))
    path = tmp_path / "app_ai.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    saved_hash = canonical_state_hash(
        manager._sessions[_text(original["game_id"])].state
    )
    end = _finish(manager, original)
    final_hash = canonical_state_hash(manager._sessions[_text(end["game_id"])].state)

    reports = []
    for hash_seed in ("1", "2718"):
        completed = subprocess.run(
            [sys.executable, "-c", _RESTORE_IN_A_NEW_PROCESS, str(path)],
            env={**os.environ, "PYTHONHASHSEED": hash_seed},
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr[-4000:]
        report = _obj(json.loads(completed.stdout.strip().splitlines()[-1]))
        assert report["restored"] == saved_hash, hash_seed
        assert report["final"] == final_hash, hash_seed
        assert report["standings"] == end["standings"], hash_seed
        reports.append(report)
    # The two processes really did hash strings differently.
    assert reports[0]["string_hash"] != reports[1]["string_hash"]


@pytest.mark.parametrize("failure", ["raises", "illegal"])
def test_a_failing_app_ai_window_never_stalls_a_live_game(
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """User decision 2026-10-05: a window that raises, or that answers with
    an illegal action, gets the app's ``DefaultRandomChoice`` from the
    agent's own RNG (never a heuristic), counted under ``error:<kind>`` and
    logged; the game plays on, and a save of it restores and plays on alike.
    """

    import logging

    from dune_imperium.agents.app_ai import AppAIAgent
    from dune_imperium.agents.app_ai.windows import turn
    from dune_imperium.agents.app_ai.windows.run import DecisionRun
    from dune_imperium.core.actions import DomainAction

    real = turn.HANDLERS["turn"]

    def failing(run: DecisionRun) -> DomainAction | None:
        # Deterministic, so a restore's replay fails at the same decisions:
        # the Agent-turn window fails in odd rounds and works in even ones.
        if run.ctx.state.round_number % 2 == 1:
            if failure == "raises":
                raise RuntimeError("probe: the turn window broke")
            return DomainAction("probe_not_an_action", run.ctx.seat)
        return real(run)

    monkeypatch.setitem(turn.HANDLERS, "turn", failing)
    manager = GameSessionManager()
    with caplog.at_level(logging.WARNING, logger="dune_imperium.agents.app_ai"):
        created = manager.create_game(
            APP_AI_SEATS, game_seed=8, choam_module=True, bloodlines=True
        )
        original = _advance(manager, created, 60)

    # Not stuck: seat 0 decides or confirms (or the game is over).
    assert original["finished"] or (
        original["confirmation"] == 0 or _obj(original["decision"])["owner"] == 0
    )
    session = manager._sessions[_text(original["game_id"])]
    errors = 0
    for seat in (1, 2, 3):
        agent = session.agents[seat]
        assert isinstance(agent, AppAIAgent)
        assert set(agent.fallbacks) <= {"error:turn"}
        errors += agent.fallbacks["error:turn"]
    assert errors > 0
    records = [r for r in caplog.records if r.name.startswith("dune_imperium")]
    assert len(records) == errors
    for record in records:
        assert record.levelno == logging.ERROR
        assert "turn decision" in record.getMessage()
        if failure == "raises":
            assert record.exc_info is not None
            assert "the turn window broke" in str(record.exc_info[1])
        else:
            assert "illegal action" in record.getMessage()
            assert "probe_not_an_action" in record.getMessage()

    document = manager.save_game(_text(original["game_id"]))
    restored = manager.restore_game(_roundtrip(document))
    for field in ("revision", "phase", "round_number", "decision"):
        assert restored[field] == original[field], field
    assert _agent_state(manager, _text(restored["game_id"])) == _agent_state(
        manager, _text(original["game_id"])
    )
    original_end = _final(manager, _finish(manager, original))
    restored_end = _final(manager, _finish(manager, restored))
    assert restored_end == original_end
