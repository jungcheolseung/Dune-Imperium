"""The ``dune-imperium-records corpus`` command."""

import hashlib
import json
import shutil
from compression import zstd
from pathlib import Path
from typing import Any

import pytest

from dune_imperium.adapters.action_codec import ACTION_CODEC_VERSION
from dune_imperium.cli import records as records_cli
from dune_imperium.cli.records import main
from dune_imperium.records.corpus import Corpus


def _picked(out: str) -> list[str]:
    """The ids a ``corpus pick`` printed, in order."""

    return [line.split()[0] for line in out.splitlines() if line.startswith("  ")]


def _edited_copy(
    tiny_corpus: Path,
    tmp_path: Path,
    *,
    steered: tuple[str, ...] = (),
    failures: dict[str, list[dict[str, Any]]] | None = None,
) -> Path:
    """A copy of the tiny corpus with ``steered`` records and shard failures."""

    copy = tmp_path / "root" / tiny_corpus.name
    shutil.copytree(tiny_corpus, copy)
    manifest = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
    for shard in manifest["shards"]:
        shard["failures"] = (failures or {}).get(shard["stem"], [])
        index = copy / "shards" / f"{shard['stem']}.index.jsonl.zst"
        rows = [
            json.loads(line)
            for line in zstd.decompress(index.read_bytes()).splitlines()
        ]
        for row in rows:
            if row["id"] in steered:
                row["steer"] = "prison_planet"
        data = zstd.compress("".join(json.dumps(row) + "\n" for row in rows).encode())
        index.write_bytes(data)
        shard["sha256"]["index"] = hashlib.sha256(data).hexdigest()
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return copy


def test_the_corpus_command_lists_keys_and_picks(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = ["--root", str(tiny_corpus.parent)]
    codec = ACTION_CODEC_VERSION
    assert main(["corpus", "list", *root]) == 0
    listing = capsys.readouterr().out
    assert f"v{codec}-01234567-r1  codec v{codec}, commit 01234567, on master" in (
        listing
    )
    assert "base.h4 1, full.h4 2, no-tech.rhra 1" in listing

    assert main(["corpus", "keys", tiny_corpus.name, "draws:*", *root]) == 0
    keys = capsys.readouterr().out
    assert "keys match 'draws:*' over 4 records" in keys
    assert "draws:card@" in keys

    ids = tmp_path / "ids.txt"
    out = tmp_path / "picks"
    arguments = ["--has", "chance_kinds:round:scouts:*", "--limit", "1"]
    assert (
        main(
            [
                "corpus",
                "pick",
                str(tiny_corpus),
                *arguments,
                "--ids-out",
                str(ids),
                "--export",
                str(out),
            ]
        )
        == 0
    )
    picked = capsys.readouterr().out
    assert "3 of 4 records match; 1 picked" in picked
    assert "full.h4.1  full h4" in picked
    assert ids.read_text() == "full.h4.1\n"
    assert [path.name for path in out.iterdir()] == ["full.h4.1.json"]
    assert (
        f"wrote 1 save files to {out}, one per record; check them with: "
        f"dune-imperium-records check --saves-dir {out} --every-save"
    ) in picked


def test_list_says_whether_the_engine_trees_match_head_and_counts_failures(
    tiny_corpus: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = {"seed": 3, "error": "RuntimeError: boom"}
    copy = _edited_copy(tiny_corpus, tmp_path, failures={"full.h4.1-2": [failure]})
    trees = Corpus.open(copy).manifest["engine_trees"]
    root = ["--root", str(copy.parent)]
    for head, answer in (
        (trees, "yes"),
        ({**trees, "rules": "2" * 40}, "no"),
        (None, "?"),
    ):
        monkeypatch.setattr(records_cli, "_head_engine_trees", lambda head=head: head)
        assert main(["corpus", "list", *root]) == 0
        listing = capsys.readouterr().out
        assert f"engine trees match HEAD: {answer}\n" in listing
        assert "  4 games, 1 failures, " in listing


def test_keys_natural_leaves_steered_records_out(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = _edited_copy(tiny_corpus, tmp_path, steered=("full.h4.1",))
    corpus = Corpus.open(copy)
    key = "action_ids:agent_turn"
    for flags, records in (([], 4), (["--natural"], 3)):
        assert main(["corpus", "keys", str(copy), key, *flags]) == 0
        out = capsys.readouterr().out
        assert f"1 keys match {key!r} over {records} records" in out
        _, count = corpus.key_counts(key, natural=bool(flags))[key]
        assert f"{records:8d} {count:8d}  {key}\n" in out


def test_pick_options_reach_the_pick(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus = Corpus.open(tiny_corpus)

    def pick(*arguments: str) -> str:
        assert main(["corpus", "pick", str(tiny_corpus), *arguments]) == 0
        return capsys.readouterr().out

    out = pick("--not", "chance_kinds:round:scouts:*")
    assert "1 of 4 records match" in out and _picked(out) == ["base.h4.1"]
    out = pick("--combo", "full")
    assert "2 of 4 records match" in out
    assert _picked(out) == ["full.h4.1", "full.h4.2"]
    out = pick("--mix", "rhra")
    assert "1 of 4 records match" in out and _picked(out) == ["no-tech.rhra.1"]

    key = "action_ids:agent_turn"
    most = max(row.count(key) for row in corpus.rows())
    expected = [row.id for row in corpus.pick([key], min_count=most)]
    assert 0 < len(expected) < 4
    out = pick("--has", key, "--min-count", str(most))
    assert f"{len(expected)} of 4 records match" in out and _picked(out) == expected

    # A seed that reorders the full.h4 group.
    seed = next(
        seed
        for seed in range(1, 50)
        if corpus.pick(combo="full", seed=seed) != corpus.pick(combo="full")
    )
    out = pick("--combo", "full", "--seed", str(seed))
    assert _picked(out) == ["full.h4.2", "full.h4.1"]


def test_pick_leaves_steered_records_out_unless_asked(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = _edited_copy(tiny_corpus, tmp_path, steered=("full.h4.1",))
    assert main(["corpus", "pick", str(copy)]) == 0
    out = capsys.readouterr().out
    assert "3 of 3 records match" in out and "full.h4.1" not in _picked(out)
    assert main(["corpus", "pick", str(copy), "--steered"]) == 0
    out = capsys.readouterr().out
    assert "4 of 4 records match" in out and "full.h4.1" in _picked(out)


def test_an_unknown_corpus_is_a_one_line_error(
    tiny_corpus: Path, tmp_path: Path
) -> None:
    with pytest.raises(SystemExit, match="^no record corpus 'v0-missing' in "):
        main(["corpus", "keys", "v0-missing", "--root", str(tiny_corpus.parent)])
    with pytest.raises(SystemExit, match=f"^no record corpus '{tiny_corpus.name}'"):
        main(["corpus", "pick", tiny_corpus.name, "--root", str(tmp_path)])
