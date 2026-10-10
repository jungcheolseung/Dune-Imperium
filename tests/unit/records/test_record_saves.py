"""Save files read as records (records.saves) and the check command."""

import json
import shutil
from pathlib import Path

import pytest

from dune_imperium.cli import records as records_cli
from dune_imperium.cli.records import main
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.replay import GameReplay
from dune_imperium.records.migration import MigratedRecord, migrate_record
from dune_imperium.records.saves import (
    human_decisions,
    read_saved_game,
    saved_games,
)
from dune_imperium.rules import UprisingRulesEngine

DATA = Path(__file__).parent / "data"
OLD = "v135-app_ai-3"


def _save(
    directory: Path,
    save_id: str,
    *,
    seats: list[str],
    steps: int | None = None,
    **extra: object,
) -> Path:
    """Copy an old-engine record into ``directory`` as a save of ``seats``."""

    document = json.loads((DATA / f"{OLD}.json").read_text(encoding="utf-8"))
    document["seats"] = seats
    if steps is not None:
        document["steps"] = document["steps"][:steps]
    document.update(extra)
    path = directory / f"{save_id}.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_a_saved_game_reads_with_its_own_versions(tmp_path: Path) -> None:
    path = _save(tmp_path, "a" * 32, seats=["human", "app_ai", "human", "app_ai"])

    game = read_saved_game(path)

    assert game.parsed.replay.action_codec_version == 135
    assert game.human_seats == (0, 2)
    assert game.game_id == path.stem
    assert not game.finished


def _branch(path: Path, at: int) -> None:
    """Make the save at ``path`` take another move at step ``at``."""

    document = json.loads(path.read_text(encoding="utf-8"))
    step = document["steps"][at]
    assert step["type"] == "action"
    document["steps"][at] = {**step, "arguments": {**step["arguments"], "x": 1}}
    path.write_text(json.dumps(document), encoding="utf-8")


def test_a_restored_session_is_the_same_game(tmp_path: Path) -> None:
    seats = ["human", "app_ai", "app_ai", "app_ai"]
    # A restored session gets a new game id; its saves continue the line.
    _save(
        tmp_path,
        "a" * 32,
        seats=seats,
        steps=100,
        source_game_id="g1",
        saved_at="2026-10-01T10:00:00+00:00",
    )
    restored = _save(
        tmp_path,
        "b" * 32,
        seats=seats,
        source_game_id="g2",
        saved_at="2026-10-02T10:00:00+00:00",
    )
    other = _save(
        tmp_path,
        "c" * 32,
        seats=seats,
        steps=50,
        game_seed=7,
        saved_at="2026-10-03T10:00:00+00:00",
    )
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")

    assert [game.path for game in saved_games(tmp_path)] == [restored, other]
    assert len(saved_games(tmp_path, every_save=True)) == 3


def test_saves_with_other_seats_are_other_games(tmp_path: Path) -> None:
    # A record corpus plays every seat mix of a combo on the same seeds.
    heuristic = _save(
        tmp_path, "a" * 32, seats=["heuristic"] * 4, saved_at="2026-10-01T10:00:00"
    )
    mixed = _save(
        tmp_path,
        "b" * 32,
        seats=["heuristic", "app_ai", "heuristic", "app_ai"],
        steps=150,
        saved_at="2026-10-01T11:00:00",
    )

    assert [game.path for game in saved_games(tmp_path)] == [heuristic, mixed]


def test_a_branch_the_players_left_is_dropped(tmp_path: Path) -> None:
    seats = ["human", "app_ai", "app_ai", "app_ai"]
    # Saved, then taken back: the older save holds moves the game left.
    left = _save(tmp_path, "a" * 32, seats=seats, saved_at="2026-10-01T10:00:00+00:00")
    _branch(left, 120)
    played = _save(
        tmp_path, "b" * 32, seats=seats, steps=150, saved_at="2026-10-01T11:00:00+00:00"
    )

    assert [game.path for game in saved_games(tmp_path)] == [played]


def test_a_finished_save_anchors_its_game(tmp_path: Path) -> None:
    seats = ["human", "app_ai", "app_ai", "app_ai"]
    finished = _save(
        tmp_path,
        "a" * 32,
        seats=seats,
        finished=True,
        saved_at="2026-10-01T10:00:00+00:00",
    )
    # Restored from an earlier save later and played another way a little.
    looked = _save(
        tmp_path, "b" * 32, seats=seats, steps=130, saved_at="2026-10-05T10:00:00+00:00"
    )
    _branch(looked, 120)

    assert [game.path for game in saved_games(tmp_path)] == [finished]


def test_human_decisions_are_the_recorded_actions_of_human_seats(
    tmp_path: Path,
) -> None:
    game = read_saved_game(
        _save(tmp_path, "a" * 32, seats=["human", "app_ai", "app_ai", "human"])
    )
    record = migrate_record(game.parsed.replay)
    assert record.complete and record.bridge_counts()

    decisions = list(human_decisions(game, record))

    recorded = [
        index
        for index, step in enumerate(game.parsed.replay.steps)
        if isinstance(step, DomainAction) and step.actor in (0, 3)
    ]
    assert [decision.recorded_index for decision in decisions] == recorded
    for decision in decisions:
        assert decision.seat in (0, 3)
        assert decision.chosen in decision.legal_actions


def test_check_reports_migrated_diverged_and_unreadable_saves(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    seats = ["human", "app_ai", "app_ai", "app_ai"]
    _save(tmp_path, "a" * 32, seats=seats, source_game_id="g1", name="옛 판")
    broken = json.loads((DATA / f"{OLD}.json").read_text(encoding="utf-8"))
    broken["seats"] = seats
    broken["source_game_id"] = "g2"
    broken["steps"][40] = {
        "type": "action",
        "action_id": "agent_turn",
        "actor": 0,
        "arguments": {"card_id": "player:0:starter:dagger:0", "space_id": "nowhere"},
    }
    (tmp_path / f"{'b' * 32}.json").write_text(json.dumps(broken), encoding="utf-8")
    shutil.copy(DATA / "v139-heuristic-1.json", tmp_path / f"{'c' * 32}.json")
    (tmp_path / "notes.json").write_text("[]", encoding="utf-8")

    # Every save: the broken copy is a branch of the same game.
    assert main(["check", "--saves-dir", str(tmp_path), "--every-save"]) == 0

    out = capsys.readouterr().out
    assert "옛 판" in out
    assert "migrated: every step applies; bridges:" in out
    assert "diverged at step 40 of 268 (round 1): seat 0 agent_turn(" in out
    assert "this engine waits for: seat" in out
    assert "unreadable notes.json" in out
    assert "3 games: 0 exact, 2 migrated, 1 diverged, 1 unreadable files" in out


def test_check_reports_an_engine_error_and_goes_on(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    seats = ["human", "app_ai", "app_ai", "app_ai"]
    _save(
        tmp_path,
        "a" * 32,
        seats=seats,
        name="첫 판",
        saved_at="2026-10-01T10:00:00+00:00",
    )
    _save(
        tmp_path,
        "b" * 32,
        seats=seats,
        name="둘째 판",
        game_seed=7,
        saved_at="2026-10-02T10:00:00+00:00",
    )
    real = migrate_record
    calls = []

    def first_fails(replay: GameReplay, engine: UprisingRulesEngine) -> MigratedRecord:
        calls.append(replay.seed)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return real(replay, engine)

    monkeypatch.setattr(records_cli, "migrate_record", first_fails)

    assert main(["check", "--saves-dir", str(tmp_path)]) == 0

    out = capsys.readouterr().out
    assert "failed: the engine raised RuntimeError: boom" in out
    assert "둘째 판" in out
    assert "2 games: 0 exact, 0 migrated, 1 diverged, 1 failed" in out
