"""The rulings notice (display.house_rulings, user request 2026-10-24).

The user asked for every ruling, in three groups shown apart: "이걸로 하되,
(가),(나),(다) 모두 구분지어서 보여지는게 맞겠다". These checks keep the notice
tied to open-questions.md, which stays the record: every entry restates a
decided question, every decided question is on the notice (or named below
with the reason it is not), and the document is the one the data writes.
"""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from dune_imperium.display.house_rulings import (
    HOUSE_RULINGS,
    RulingGame,
    RulingGroup,
    house_rulings_markdown,
)

_ROOT = Path(__file__).resolve().parents[3]

# Decided questions the notice leaves out, and why: they change nothing a
# player sees in the rules (what the project keeps internally).
NOT_ON_THE_NOTICE: dict[str, str] = {}

# What a player is never shown (user decision 2026-10-14, the same pattern as
# tests/server/test_i18n.py): a question number, a path, a command argument.
_DEVELOPER_TALK = re.compile(
    r"\bOQ-?\d+|\b(?:docs|src|saves|checkpoints|scripts|tmp)/"
    r"|(?<![\w-])--[a-z]|\.(?:py|md|pt)\b|\buv\b|\bextras?\b"
)
_HANGUL = re.compile(r"[가-힣]")


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "house_rulings_doc", _ROOT / "scripts" / "house_rulings_doc.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _index() -> dict[str, tuple[str, str]]:
    script = _script()
    text = (_ROOT / "docs" / "rules" / "open-questions.md").read_text("utf-8")
    index: dict[str, tuple[str, str]] = script.question_index(text)
    assert len(index) > 100, "the index table was not read"
    return index


def test_the_document_is_the_one_the_data_writes() -> None:
    anchors = {question: anchor for question, (anchor, _) in _index().items()}
    document = (_ROOT / "docs" / "rules" / "house-rulings-ko.md").read_text("utf-8")
    assert document == house_rulings_markdown(anchors), (
        "docs/rules/house-rulings-ko.md is stale: uv run scripts/house_rulings_doc.py"
    )


def test_every_entry_restates_a_settled_question() -> None:
    # A RESOLVED question can still hold a part the project ruled (OQ-005's
    # wild pairing, OQ-013's deck discards); an OPEN one is not ruled yet.
    index = _index()
    for entry in HOUSE_RULINGS:
        assert entry.question in index, entry.oq
        assert index[entry.question][1] in {"DECIDED", "RESOLVED"}, (
            entry.oq,
            index[entry.question],
        )
    marks = [entry.oq for entry in HOUSE_RULINGS]
    assert len(marks) == len(set(marks)), "an entry is listed twice"


def test_every_decided_question_is_on_the_notice() -> None:
    decided = {
        question for question, (_, status) in _index().items() if status == "DECIDED"
    }
    listed = {entry.question for entry in HOUSE_RULINGS}
    missing = sorted(decided - listed - set(NOT_ON_THE_NOTICE))
    assert not missing, f"decided questions not on the notice: {missing}"
    stale = sorted(set(NOT_ON_THE_NOTICE) & listed)
    assert not stale, f"listed and also excused: {stale}"


def test_each_entry_reads_in_both_languages_without_developer_talk() -> None:
    for entry in HOUSE_RULINGS:
        texts = {
            "title_ko": entry.title_ko,
            "title": entry.title,
            "ruling_ko": entry.ruling_ko,
            "ruling": entry.ruling,
            "sources_ko": entry.sources_ko,
            "sources": entry.sources,
        }
        for field in ("title_ko", "title", "ruling_ko", "ruling"):
            assert texts[field], (entry.oq, field)
        for field in ("title_ko", "ruling_ko"):
            assert _HANGUL.search(texts[field]), (entry.oq, field)
        for field in ("title", "ruling", "sources"):
            assert not _HANGUL.search(texts[field]), (entry.oq, field)
        # The first two groups say which source is followed and which is not.
        named = entry.group is not RulingGroup.PROJECT
        assert bool(entry.sources_ko) == named == bool(entry.sources), entry.oq
        for field, text in texts.items():
            assert not _DEVELOPER_TALK.search(text), (entry.oq, field, text)


def test_the_groups_and_games_are_all_used() -> None:
    assert {entry.group for entry in HOUSE_RULINGS} == set(RulingGroup)
    assert {entry.game for entry in HOUSE_RULINGS} == set(RulingGame)
