"""Reusable checks for the engine-*generated* Korean display text (Track 1).

Feature decided 2026-09-25: the effect text ``display/*.py`` generates from
engine data gets a Korean twin (``*_ko`` functions, ``<field>_ko`` catalog
entries); printed card wording stays English. Every ``display/*_ko``
generator's tests import these instead of writing their own copies, so a new
generator (a later step's ``effect_dsl_text_ko.py``, ``cards_ko`` helpers,
...) gets the same guards for free:

- every ``{term}``/``{term:count}`` placeholder names a real
  ``static/labels.js`` ``TERMS`` key (``assert_placeholders_are_terms``);
- a Korean line holds no Latin-alphabet word beyond an explicitly allowed
  one — a board-space name (always English), a card with no known Korean
  print, or another caller-supplied exception
  (``assert_no_stray_latin``);
- an English line that trashes renders 폐기 (or the ``{trash}``/
  ``{trash_intrigue}`` placeholder) and never 버리, and one that discards
  the opposite (``assert_trash_and_discard_match`` —
  ``docs/rules/glossary-ko.md``: "trash와 discard를 절대 섞지 않는다";
  ``docs/lessons.md`` 2026-09-09 logs a real bug from mixing them).
"""

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_STATIC = _REPO / "src" / "dune_imperium" / "server" / "static"
_PLACEHOLDER = re.compile(r"\{([a-z_]+)(?::(\d+))?\}")
_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z'+]*")

_TRASH_TOKENS = ("폐기", "{trash}", "{trash_intrigue}")
_DISCARD_TOKENS = ("버리", "{discard}")
# "trashed"/"trashes" — \btrash\b alone misses the inflected forms.
_TRASH_EN = re.compile(r"\btrash(?:e[sd])?\b", re.IGNORECASE)
# "discards"/"discarded"/"discarding" the verb, but not "discard pile(s)",
# the zone name — stripped first so its own literal "discard" is never
# counted as the verb (a line can name the pile while trashing, e.g. "Trash
# a card from your discard pile").
_DISCARD_PILE_EN = re.compile(r"\bdiscard piles?\b", re.IGNORECASE)
_DISCARD_EN = re.compile(r"\bdiscard(?:s|ed|ing)?\b", re.IGNORECASE)


def terms_keys() -> frozenset[str]:
    """Every name a Korean line's ``{term}`` placeholder may use.

    Read from ``static/labels.js``'s ``TERMS`` table so this list can never
    drift from what the client's ``phrase()`` actually expands.
    """

    source = (_STATIC / "labels.js").read_text()
    block = re.search(r"^const TERMS = \{(.*?)\n\};", source, re.S | re.M)
    assert block, "TERMS not found in labels.js"
    keys = re.findall(r"^\s+([a-z_]+): \{", block.group(1), re.M)
    assert keys, "no TERMS keys read — the pattern is broken"
    return frozenset(keys)


def placeholders(text: str) -> list[str]:
    """Every ``{term}``/``{term:count}`` name used in ``text``."""

    return [match.group(1) for match in _PLACEHOLDER.finditer(text)]


def assert_placeholders_are_terms(
    text: str, terms: frozenset[str] | None = None
) -> None:
    known = terms if terms is not None else terms_keys()
    unknown = [name for name in placeholders(text) if name not in known]
    assert not unknown, f"{text!r} uses unknown placeholder(s): {unknown}"


def strip_placeholders(text: str) -> str:
    """``text`` with every ``{term}``/``{term:count}`` blanked out."""

    return _PLACEHOLDER.sub(" ", text)


def assert_no_stray_latin(
    text: str, allowed: frozenset[str] | set[str] = frozenset()
) -> None:
    """Every Latin-alphabet run in ``text`` sits inside an allowed phrase.

    ``allowed`` holds whole phrases that may legitimately stay English — a
    board-space name (glossary "공간 이름" row: always English), a card
    with no known Korean print, a Leader's own name, or anything else a
    caller passes. Phrases are stripped longest-first, so a short name
    nested inside a longer one (e.g. "Arrakeen" inside "Arrakeen I") is not
    double-counted; whatever Latin remains after that is a stray leak.
    """

    bare = strip_placeholders(text)
    for phrase in sorted(allowed, key=len, reverse=True):
        bare = bare.replace(phrase, " ")
    stray = _LATIN_WORD.findall(bare)
    assert not stray, f"{text!r} has un-allowed Latin text: {stray}"


def assert_trash_and_discard_match(english: str, korean: str) -> None:
    """The Korean line matches English verb-for-verb: trash 폐기, discard 버리.

    Checked as two independent equivalences (English trashes iff Korean has
    폐기; English discards iff Korean has 버리), not as an "and not the
    other" pair — a line that legitimately trashes AND discards (e.g. "Draw
    1, Discard 1, Trash 1") must show both, which the old one-sided check
    could never pass (2026-09-25 review). "Discard pile(s)" (the zone name)
    is stripped from the English before matching so it is never counted as
    the discard *verb* — its own Korean name, 버림 더미, does not contain
    the verb stem 버리 either, so a line that trashes a card from the
    discard pile correctly needs only 폐기.
    """

    stripped_en = _DISCARD_PILE_EN.sub(" ", english)
    trashes_en = _TRASH_EN.search(stripped_en) is not None
    discards_en = _DISCARD_EN.search(stripped_en) is not None
    trashes_ko = any(token in korean for token in _TRASH_TOKENS)
    discards_ko = any(token in korean for token in _DISCARD_TOKENS)
    assert trashes_en == trashes_ko, (
        f"{english!r} (trashes={trashes_en}) does not match Korean 폐기 "
        f"presence ({trashes_ko}): {korean!r}"
    )
    assert discards_en == discards_ko, (
        f"{english!r} (discards={discards_en}) does not match Korean 버리 "
        f"presence ({discards_ko}): {korean!r}"
    )
