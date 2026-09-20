"""Guard: the client's rule terms resolve, and their Korean comes from the
official glossary.

The client is dependency-free vanilla JS with no JS test runner, so the term
table is checked from Python: every ``{term}`` a label writes must name a row
of ``TERMS``, every ``TERMS`` row must carry an icon name the icon set
actually has (or none), and every Korean word must appear in
``docs/rules/glossary-ko.md``.

That last check is the point. The Korean the UI speaks has to be the word the
official Korean rulebook uses, not one someone made up here — ``lessons.md``
2026-09-09 records a real bug from guessing at trash versus discard.
"""

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_STATIC_DIR = _REPO / "src" / "dune_imperium" / "server" / "static"
_GLOSSARY = _REPO / "docs" / "rules" / "glossary-ko.md"
_ICON_DIR = _REPO / "assets" / "icons"


def _client_source() -> str:
    return "\n".join(
        path.read_text() for path in sorted(_STATIC_DIR.glob("*.js"))
    )


def _terms() -> dict[str, dict[str, str]]:
    source = _client_source()
    match = re.search(r"const TERMS = \{(.*?)\n\};", source, re.DOTALL)
    assert match, "TERMS block not found in any static/*.js"
    # icon is "" when the term has no icon of its own.
    rows: dict[str, dict[str, str]] = {}
    for entry in re.finditer(
        r"^\s{2}([a-z_]+):\s*\{(.*?)\},$", match.group(1), re.DOTALL | re.MULTILINE
    ):
        body = entry.group(2)
        icon = re.search(r'icon:\s*(?:"([^"]*)"|null)', body)
        korean = re.search(r'ko:\s*"([^"]*)"', body)
        english = re.search(r'en:\s*"([^"]*)"', body)
        assert icon and korean and english, f"malformed TERMS row: {entry.group(1)}"
        rows[entry.group(1)] = {
            "icon": icon.group(1) or "",
            "ko": korean.group(1),
            "en": english.group(1),
        }
    assert rows, "no TERMS rows parsed — the scan is broken"
    return rows


def _referenced_terms() -> set[str]:
    """Every ``{term}`` written inside a label table.

    Scoped to the ``*_LABELS`` blocks rather than the whole client, because
    plain JavaScript is full of braces — destructuring and template holes
    would otherwise read as term references.
    """
    source = _client_source()
    names: set[str] = set()
    for block in re.finditer(
        r"const [A-Z_]*LABELS = \{(.*?)\n\};", source, re.DOTALL
    ):
        for literal in re.findall(r'"((?:[^"\\]|\\.)*)"', block.group(1)):
            names.update(re.findall(r"\{([a-z_]+)(?::\d+)?\}", literal))
    return names


def test_every_referenced_term_is_defined() -> None:
    defined = set(_terms())
    referenced = _referenced_terms()
    assert referenced, "no term references found in the label tables — scan broken"
    missing = referenced - defined
    assert not missing, (
        f"labels name terms that TERMS does not define: {sorted(missing)}"
    )


def test_term_icons_exist() -> None:
    available = {path.stem for path in _ICON_DIR.glob("*.png")}
    if not available:  # the assets checkout is optional on some machines
        return
    unknown = {
        name: row["icon"]
        for name, row in _terms().items()
        if row["icon"] and row["icon"] not in available
    }
    assert not unknown, f"terms naming an icon that does not exist: {unknown}"


def test_korean_terms_come_from_the_glossary() -> None:
    glossary = _GLOSSARY.read_text()
    missing = {
        name: row["ko"]
        for name, row in _terms().items()
        if row["ko"] not in glossary
    }
    assert not missing, (
        "terms whose Korean is not in docs/rules/glossary-ko.md — add the row "
        f"with its rulebook citation instead of inventing a word: {missing}"
    )
