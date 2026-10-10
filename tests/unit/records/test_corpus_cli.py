"""The ``dune-imperium-records corpus`` command."""

from pathlib import Path

import pytest

from dune_imperium.cli.records import main


def test_the_corpus_command_lists_keys_and_picks(
    tiny_corpus: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = ["--root", str(tiny_corpus.parent)]
    assert main(["corpus", "list", *root]) == 0
    listing = capsys.readouterr().out
    assert "v141-01234567-r1  codec v141, commit 01234567, on master" in listing
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
