"""Reading a record corpus (records.corpus) and the ``corpus`` command."""

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.cli.records import main
from dune_imperium.records.corpus import Corpus, CorpusRow, corpora
from dune_imperium.records.migration import migrate_record, walk
from dune_imperium.records.saves import read_saved_game
from dune_imperium.rules import UprisingRulesEngine


def _ids(rows: list[CorpusRow]) -> list[str]:
    return [row.id for row in rows]


def test_a_corpus_opens_by_id_or_by_path(tiny_corpus: Path) -> None:
    assert [corpus.path for corpus in corpora(tiny_corpus.parent)] == [tiny_corpus]
    by_id = Corpus.open(tiny_corpus.name, root=tiny_corpus.parent)
    assert by_id.id == Corpus.open(tiny_corpus).id == tiny_corpus.name
    assert tiny_corpus.name == f"v{ACTION_CODEC_VERSION}-01234567-r1"
    with pytest.raises(FileNotFoundError):
        Corpus.open("v0-missing", root=tiny_corpus.parent)
    assert corpora(tiny_corpus / "nowhere") == []


def test_rows_name_their_shard_line_and_seats(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    rows = corpus.rows()
    assert sorted(_ids(list(rows))) == [
        "base.h4.1",
        "full.h4.1",
        "full.h4.2",
        "no-tech.rhra.1",
    ]
    row = corpus.row("full.h4.2")
    assert (row.shard, row.line, row.seed, row.cut_rounds) == ("full.h4.1-2", 1, 2, 1)
    assert row.ruleset.startswith("uprising-4p-choam+promo") and row.ruleset.endswith(
        "+draft"
    )
    assert row.natural and not row.finished and row.rounds == 2
    assert corpus.games() == {
        ("base", "h4"): 1,
        ("full", "h4"): 2,
        ("no-tech", "rhra"): 1,
    }


def test_pick_filters_by_keys_groups_and_counts(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    everything = corpus.pick()
    # Round-robin over (combo, mix) in sorted order, each group by seed.
    assert _ids(everything) == ["base.h4.1", "full.h4.1", "no-tech.rhra.1", "full.h4.2"]
    assert _ids(corpus.pick(limit=3)) == ["base.h4.1", "full.h4.1", "no-tech.rhra.1"]
    assert _ids(corpus.pick(combo="full")) == ["full.h4.1", "full.h4.2"]
    assert _ids(corpus.pick(mix="rhra")) == ["no-tech.rhra.1"]
    # The base combo plays without the Arrakeen Scouts.
    assert _ids(corpus.pick(["chance_kinds:round:scouts:*"])) == [
        "full.h4.1",
        "no-tech.rhra.1",
        "full.h4.2",
    ]
    assert _ids(corpus.pick(without=["chance_kinds:round:scouts:*"])) == ["base.h4.1"]
    # Every ``has`` pattern must match; min_count applies to them.
    row = corpus.row("full.h4.1")
    count = row.count("action_ids:agent_turn")
    assert corpus.pick(
        ["action_ids:agent_turn"], min_count=count + 1, combo="full"
    ) == [
        other
        for other in corpus.pick(combo="full")
        if other.count("action_ids:agent_turn") > count
    ]
    assert corpus.pick(["action_ids:agent_turn", "no_such:*"]) == []


def test_a_pick_seed_shuffles_each_group_deterministically(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    full = corpus.row("full.h4.1")
    # Eight records in the full.h4 group.
    corpus._rows = (
        *corpus.rows(),
        *(replace(full, id=f"full.h4.{seed}", seed=seed) for seed in range(3, 9)),
    )
    by_seed = [f"full.h4.{seed}" for seed in range(1, 9)]
    assert _ids(corpus.pick(combo="full")) == by_seed
    orders = [_ids(corpus.pick(combo="full", seed=seed)) for seed in range(1, 6)]
    assert all(sorted(order) == sorted(by_seed) for order in orders)
    # Some seed reorders the group, seeds differ, and a seed repeats itself.
    assert any(order != by_seed for order in orders)
    assert len({tuple(order) for order in orders}) > 1
    assert _ids(corpus.pick(combo="full", seed=3)) == orders[2]


def test_pick_leaves_steered_records_out_unless_asked(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    corpus._rows = tuple(
        replace(row, steer="prison_planet") if row.id == "full.h4.1" else row
        for row in corpus.rows()
    )
    assert "full.h4.1" not in _ids(corpus.pick())
    assert "full.h4.1" in _ids(corpus.pick(natural=False))
    records, _ = corpus.key_counts("action_ids:agent_turn", natural=True)[
        "action_ids:agent_turn"
    ]
    assert records == 3


def test_key_counts_sum_records_and_occurrences(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    counts = corpus.key_counts("action_ids:*")
    assert counts and all(key.startswith("action_ids:") for key in counts)
    records, occurrences = counts["action_ids:agent_turn"]
    assert records == 4
    assert occurrences == sum(
        row.count("action_ids:agent_turn") for row in corpus.rows()
    )
    assert list(counts) == sorted(counts)


def test_a_record_walked_on_its_engine_matches_its_trace(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    engine = UprisingRulesEngine()
    for row in corpus.rows():
        record = migrate_record(corpus.replay(row), engine)
        assert record.exact
        trace = corpus.trace(row)
        assert trace.steps == row.steps == len(record.steps)
        fingerprint = corpus.fingerprint()
        differences = 0
        for state, migrated in walk(record, engine):
            assert migrated.recorded_index is not None
            if fingerprint(state) != trace.before(migrated.recorded_index):
                differences += 1
        assert differences == 0, row.id
        assert fingerprint(record.state) == trace.final()


def test_a_shard_file_that_does_not_match_the_manifest_is_refused(
    tiny_corpus: Path, tmp_path: Path
) -> None:
    copy = tmp_path / tiny_corpus.name
    shutil.copytree(tiny_corpus, copy)
    corpus = Corpus.open(copy)
    row = corpus.row("full.h4.1")
    index = copy / "shards" / "full.h4.1-2.index.jsonl.zst"
    index.write_bytes(index.read_bytes() + b"\0")
    with pytest.raises(ValueError, match="does not match the manifest's sha256"):
        Corpus.open(copy).rows()
    records = copy / "shards" / "full.h4.1-2.records.jsonl.zst"
    data = bytearray(records.read_bytes())
    data[-1] ^= 1
    records.write_bytes(bytes(data))
    with pytest.raises(ValueError, match="does not match the manifest's sha256"):
        corpus.document(row)


def test_a_row_that_names_another_line_is_refused(tiny_corpus: Path) -> None:
    corpus = Corpus.open(tiny_corpus)
    row = corpus.row("full.h4.1")
    assert corpus.document(row)["corpus"]["id"] == "full.h4.1"
    with pytest.raises(ValueError, match="line 1 is not full.h4.1"):
        corpus.document(replace(row, line=1))


def test_an_exported_record_says_whether_its_game_finished(
    tiny_corpus: Path, tmp_path: Path
) -> None:
    corpus = Corpus.open(tiny_corpus)
    row = corpus.row("full.h4.1")
    assert not row.finished
    (unfinished,) = corpus.export([row], tmp_path / "unfinished")
    (finished,) = corpus.export([replace(row, finished=True)], tmp_path / "finished")
    assert not read_saved_game(unfinished).finished
    assert read_saved_game(finished).finished


def test_exported_records_check_exact(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus = Corpus.open(tiny_corpus)
    paths = corpus.export(corpus.pick(), tmp_path / "picks")
    assert sorted(path.name for path in paths) == [
        "base.h4.1.json",
        "full.h4.1.json",
        "full.h4.2.json",
        "no-tech.rhra.1.json",
    ]
    assert main(["check", "--saves-dir", str(tmp_path / "picks"), "--every-save"]) == 0
    assert "4 games: 4 exact, 0 migrated, 0 diverged" in capsys.readouterr().out
