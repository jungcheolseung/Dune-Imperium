"""The record-corpus drivers: the record writer and the corpus generator."""

import ast
import hashlib
import json
import subprocess
from collections.abc import Callable
from compression import zstd
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dune_imperium.config import RulesetConfig
from dune_imperium.core.state import canonical_state_hash
from dune_imperium.records.corpus import Corpus
from dune_imperium.records.migration import migrate_record
from dune_imperium.records.portable import trace as portable_trace
from dune_imperium.records.portable.trace import Fingerprint, census_of
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.server.persistence import parse_save_document
from dune_imperium.simulation.coverage import collect_game_coverage

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts" / "records"
DRIVERS = ("old_engine_record.py", "corpus_generate.py")
# The engine names an old-side driver may import: all stable from codec v135
# to v142 (the corpus design's allowlist), plus ``dune_imperium`` itself for
# the checkout's path (a plain ``import``) and ``FrameKind`` for the
# manifest's frame catalog.
ENGINE_API = {
    "dune_imperium.rules": {"UprisingRulesEngine"},
    "dune_imperium.agents.registry": {"make_agent"},
    "dune_imperium.config": {"RulesetConfig"},
    "dune_imperium.simulation.runner": {"run_policy_game"},
    "dune_imperium.server.persistence": {"serialize_step"},
    "dune_imperium.core.state": {"canonical_state_hash"},
    "dune_imperium.adapters.action_codec": {"ACTION_CODEC_VERSION"},
    "dune_imperium.simulation.coverage": {
        "collect_game_coverage",
        "normalize_instance_id",
    },
    "dune_imperium.core.actions": {"DomainAction"},
    "dune_imperium.core.chance": {"ChanceOutcome"},
    "dune_imperium.core.decisions": {"PlayerDecision"},
    "dune_imperium.rules.frames": {"FrameKind"},
}


def _rows(corpus: Corpus) -> dict[str, Any]:
    return {row.id: row for row in corpus.rows()}


def test_the_drivers_touch_the_engine_only_through_allowed_names() -> None:
    for name in DRIVERS:
        tree = ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("dune_imperium"):
                        assert alias.name == "dune_imperium", f"{name}: {alias.name}"
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "dune_imperium"
            ):
                allowed = ENGINE_API.get(node.module or "", set())
                for alias in node.names:
                    assert alias.name in allowed, f"{name}: {node.module}.{alias.name}"


def test_the_portable_trace_loads_by_path_beside_the_package(
    generator: ModuleType,
) -> None:
    loaded = generator.trace
    assert loaded.__name__ == "_corpus_trace"
    assert loaded is not portable_trace
    assert Path(loaded.__file__) == Path(portable_trace.__file__)
    state = UprisingRulesEngine().reset(RulesetConfig(choam_module=True), 3)
    assert loaded.Fingerprint()(state) == Fingerprint()(state)


def test_modules_with_turns_modules_off_and_every_combo_is_a_ruleset(
    generator: ModuleType,
) -> None:
    record = generator.record
    assert record.modules_with(()) == record.MODULES
    modules = record.modules_with(("immortality", "go_to_11"))
    assert modules["immortality"] is False and modules["go_to_11"] is False
    assert modules["bloodlines"] is True
    for name in ("players", "nonsense"):
        with pytest.raises(SystemExit):
            record.modules_with((name,))
    for combo in generator.COMBOS:
        generator.combo_config(combo)  # config.py's rules hold
    base = generator.combo_config("base")
    assert (base.choam_module, base.leader_draft, base.bloodlines) == (
        True,
        True,
        False,
    )


def test_a_record_parses_and_replays_to_its_hash(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    engine = UprisingRulesEngine()
    for row in corpus.rows():
        document = corpus.document(row)
        parsed = parse_save_document(document, check_versions=False)
        state = engine.reset(parsed.replay.ruleset, parsed.replay.seed)
        for step in parsed.replay.steps:
            state = engine.apply(state, step).state
        assert canonical_state_hash(state) == document["expected_state_hash"]
        assert state.round_number == 2  # cut after round 1
        assert parsed.seats == row.seats
    rhra = corpus.document(corpus.row("no-tech.rhra.1"))
    assert rhra["seats"] == ["random", "heuristic", "random", "app_ai"]
    assert rhra["corpus"]["seat_seeds"] == [10, 11, 12, 13]
    assert (
        rhra["name"]
        == "random/heuristic/random/app_ai seed 1, rounds 1-1, engine 01234567"
    )
    assert rhra["ruleset"]["tech_module"] is False


def test_the_cli_writes_the_bytes_play_record_makes(
    generator: ModuleType,
    tiny_corpus: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    record = generator.record
    monkeypatch.setattr(record, "engine_commit", lambda: "01234567")
    record.main([str(tmp_path), "1", "heuristic", "1"])
    written = (tmp_path / "v141-heuristic-1.json").read_bytes()
    assert capsys.readouterr().out.endswith(" steps\n")
    corpus = Corpus.open(tiny_corpus)
    document = corpus.document(corpus.row("full.h4.1"))
    del document["corpus"]
    assert written == json.dumps(document, separators=(",", ":")).encode()


def test_the_manifest_lists_every_shard_with_its_hashes(tiny_corpus: Path) -> None:
    manifest = json.loads((tiny_corpus / "manifest.json").read_text())
    assert manifest["id"] == "v141-01234567-r1"
    assert manifest["games"] == 4
    assert len(manifest["fingerprint_fields"]) == len(
        portable_trace.field_names(UprisingRulesEngine().reset(RulesetConfig(), 1))
    )
    assert {"GameState", "PlayerState", "Resources", "RulesetConfig"} <= set(
        manifest["class_schema"]
    )
    assert "agent_effects" in manifest["frame_catalog"]
    assert manifest["unordered_zones"] == list(portable_trace.UNORDERED)
    shards = {shard["stem"]: shard for shard in manifest["shards"]}
    assert set(shards) == {"full.h4.1-2", "base.h4.1-1", "no-tech.rhra.1-1"}
    for stem, shard in shards.items():
        assert shard["failures"] == []
        lengths = []
        for part, suffix in (
            ("records", ".records.jsonl.zst"),
            ("index", ".index.jsonl.zst"),
            ("trace", ".trace.bin.zst"),
        ):
            data = (tiny_corpus / "shards" / f"{stem}{suffix}").read_bytes()
            assert hashlib.sha256(data).hexdigest() == shard["sha256"][part]
            raw = zstd.decompress(data)
            if part == "trace":
                lengths.append(len(portable_trace.read_traces(raw)))
            else:
                lengths.append(len(raw.splitlines()))
        assert lengths == [shard["games"]] * 3


def test_every_record_replays_exactly(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    engine = UprisingRulesEngine()
    for row in corpus.rows():
        migrated = migrate_record(corpus.replay(row), engine)
        assert migrated.exact, row.id
        assert canonical_state_hash(migrated.state) == row.final_hash


def test_the_census_keys_equal_the_coverage_census(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    engine = UprisingRulesEngine()
    for row in corpus.rows():
        replay = corpus.replay(row)
        state = engine.reset(replay.ruleset, replay.seed)
        for step in replay.steps:
            state = engine.apply(state, step).state
        assert census_of(row.keys) == collect_game_coverage(state, replay.steps)
        leaders = {player.leader_id for player in state.players}
        assert {key[8:] for key in row.matching("leaders:*")} == leaders


def test_rows_carry_frames_offers_and_draws(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    row = corpus.row("full.h4.1")
    assert row.count("frames:leader_draft") >= 1
    assert row.count("offered:agent_turn") >= row.count("action_ids:agent_turn") > 0
    draws = row.matching("draws:*")
    assert draws and all(row.positions(key) is not None for key in draws)
    assert row.steps == corpus.trace(row).steps
    assert not row.matching("chance_values:*discard_shuffle=*")


def test_regenerating_a_shard_gives_the_same_bytes(
    generator: ModuleType,
    tiny_corpus: Path,
    make_identity: Callable[..., Any],
    tmp_path: Path,
) -> None:
    again = generator.generate(
        tmp_path,
        [generator.Request("base", "h4", 1, 1)],
        identity=make_identity(),
        workers=1,
        rounds=1,
        log=lambda line: None,
    )
    for suffix in (".records.jsonl.zst", ".index.jsonl.zst", ".trace.bin.zst"):
        name = f"base.h4.1-1{suffix}"
        assert (again / "shards" / name).read_bytes() == (
            tiny_corpus / "shards" / name
        ).read_bytes()


def test_a_rerun_keeps_finished_shards_and_refuses_overlaps(
    generator: ModuleType,
    tiny_corpus: Path,
    make_identity: Callable[..., Any],
    tiny_requests: list[Any],
) -> None:
    lines: list[str] = []
    before = (tiny_corpus / "shards" / "full.h4.1-2.trace.bin.zst").stat().st_mtime_ns
    generator.generate(
        tiny_corpus.parent,
        tiny_requests,
        identity=make_identity(),
        workers=1,
        rounds=1,
        log=lines.append,
    )
    assert "3 shards kept, 0 to play" in lines[0]
    after = (tiny_corpus / "shards" / "full.h4.1-2.trace.bin.zst").stat().st_mtime_ns
    assert before == after
    with pytest.raises(SystemExit, match="overlap"):
        generator.generate(
            tiny_corpus.parent,
            [generator.Request("full", "h4", 2, 3)],
            identity=make_identity(),
            workers=1,
            rounds=1,
        )


def test_a_branch_engine_needs_branch_ok(
    generator: ModuleType, make_identity: Callable[..., Any], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="not on master"):
        generator.generate(
            tmp_path, [], identity=make_identity(on_master=False), workers=1
        )


def test_shards_split_at_250_games(generator: ModuleType) -> None:
    specs = generator.plan_shards([generator.Request("full", "h4", 1, 600)])
    assert [spec.stem for spec in specs] == [
        "full.h4.1-250",
        "full.h4.251-500",
        "full.h4.501-600",
    ]
    standard = [generator.Request(c, m, 1, n) for c, m, n in generator.STANDARD_PLAN]
    assert (
        sum(spec.hi - spec.lo + 1 for spec in generator.plan_shards(standard)) == 2000
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_a_dirty_engine_src_is_refused(generator: ModuleType, tmp_path: Path) -> None:
    repo = tmp_path / "engine"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "engine.py").write_text("A = 1\n")
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "add", "src")
    _git(
        repo,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "commit",
        "-q",
        "-m",
        "engine",
    )
    identity = generator.engine_identity(repo)
    assert identity.on_master and len(identity.commit) == 40
    (repo / "src" / "engine.py").write_text("A = 2\n")
    with pytest.raises(SystemExit, match="uncommitted"):
        generator.engine_identity(repo)
