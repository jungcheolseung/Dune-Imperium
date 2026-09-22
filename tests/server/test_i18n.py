"""Guard: the client speaks one language at a time (사용자 결정 2026-09-20).

The client is dependency-free vanilla JS with no JS test runner, so the
language tables are checked from Python, the way ``test_terms.py`` checks the
rule terms:

- no Korean string literal is left in ``static/*.js`` outside the tables that
  hold Korean on purpose (a literal elsewhere would stay Korean in English);
- every ``t("key")`` / ``tNode("key")`` names a ``UI_TEXT`` entry with both a
  Korean and an English text, the English holds no Hangul, and every entry is
  used;
- ``LABELS_EN`` mirrors each Korean label table key for key, keeps each
  value's ``{term}`` tokens and holds no Hangul;
- ``index.html``'s ``data-i18n`` keys exist and its inline Korean is the
  table's Korean;
- every prompt the engine shows a person has a Korean rendering.
"""

import ast
import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from dune_imperium.server.catalog import build_catalog

_REPO = Path(__file__).resolve().parents[2]
_STATIC = _REPO / "src" / "dune_imperium" / "server" / "static"
_RULES = _REPO / "src" / "dune_imperium" / "rules"
_HANGUL = re.compile(r"[가-힣]")
_TERM = re.compile(r"\{([a-z_]+)(?::\d+)?\}")
_HOLE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")

# Tables that hold Korean on purpose, by the name of their `const`.
_KOREAN_TABLES = re.compile(
    r"^(?:[A-Z_]*LABELS|TERMS|UI_TEXT|PROMPT_KO|PROMPT_KO_PATTERNS|SEAT_KINDS"
    r"|AGENT_ICON_GROUPS)$"
)
# The toggle names the other language in that language (i18n.js).
_ALLOWED_LITERALS = {"i18n.js": {"한국어"}}


def _literals(source: str) -> Iterator[tuple[int, str]]:
    """(offset, text) of every string or template literal, comments skipped.

    A small tokenizer, not a parser: enough for this client, which has regex
    literals only in a few tables. A regex is recognised after a punctuator
    that cannot end an expression.
    """
    index, size, previous = 0, len(source), ""
    while index < size:
        char = source[index]
        if source.startswith("//", index):
            end = source.find("\n", index)
            index = size if end < 0 else end
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            index = size if end < 0 else end + 2
            continue
        if char in "\"'`":
            end, depth = index + 1, 0
            while end < size:
                if source[end] == "\\":
                    end += 2
                    continue
                if char == "`" and source.startswith("${", end):
                    depth += 1
                    end += 2
                    continue
                if depth and source[end] == "}":
                    depth -= 1
                elif not depth and source[end] == char:
                    break
                end += 1
            yield index, source[index + 1 : end]
            index, previous = end + 1, "x"
            continue
        if char == "/" and previous in ("", "(", ",", "=", ":", "[", "!", "&", "|", "?",
                                        "{", "}", ";", "\n"):
            end, in_class = index + 1, False
            while end < size and (source[end] != "/" or in_class):
                if source[end] == "\\":
                    end += 2
                    continue
                if source[end] == "[":
                    in_class = True
                elif source[end] == "]":
                    in_class = False
                elif source[end] == "\n":
                    break
                end += 1
            index, previous = end + 1, "x"
            continue
        if not char.isspace():
            previous = char if char in "(,=:[!&|?{};" else "x"
        elif char == "\n" and previous in ("{", "}", ";"):
            previous = "\n"
        index += 1


def _table_spans(source: str) -> list[tuple[int, int, str]]:
    spans = []
    for match in re.finditer(r"^const ([A-Z_]+) = [\[{]", source, re.MULTILINE):
        opener = source[match.end() - 1]
        closer = "]" if opener == "[" else "}"
        end = source.find(f"\n{closer};", match.end())
        spans.append((match.start(), end if end > 0 else len(source), match.group(1)))
    return spans


def _json_const(name: str, filename: str) -> Any:
    source = (_STATIC / filename).read_text()
    match = re.search(rf"^const {name} = (.*?);\n", source, re.MULTILINE | re.DOTALL)
    assert match, f"{name} not found in {filename}"
    return json.loads(match.group(1))


def _ui_text() -> dict[str, dict[str, str]]:
    table: dict[str, dict[str, str]] = _json_const("UI_TEXT", "ui_text.js")
    return table


def _client() -> dict[str, str]:
    return {path.name: path.read_text() for path in sorted(_STATIC.glob("*.js"))}


def test_no_korean_literal_outside_the_tables() -> None:
    stray = []
    for name, source in _client().items():
        spans = _table_spans(source)
        allowed = _ALLOWED_LITERALS.get(name, set())
        for offset, text in _literals(source):
            if not _HANGUL.search(text) or text in allowed:
                continue
            table = next((t for a, b, t in spans if a <= offset < b), None)
            if table and _KOREAN_TABLES.match(table):
                continue
            line = source.count("\n", 0, offset) + 1
            stray.append(f"{name}:{line}: {text[:40]!r}")
    assert not stray, (
        f"{len(stray)} Korean literals outside the language tables — move them "
        "into UI_TEXT and call t()/tNode(): " + "; ".join(stray[:10])
    )


# UI_TEXT keys are "<file stem>.<name>" (plus common. and html.).
_KEY_LITERAL = re.compile(
    r"^(?:common|html|app|board|core|help|i18n|panels|render|review|screens"
    r"|session|turn)\.[a-z0-9_]+$"
)


def _called_keys() -> dict[str, set[str]]:
    """Every string literal in the client shaped like a UI_TEXT key.

    Most are the first argument of t()/tNode(); some sit in a table the help
    panel or a helper passes on (t(textKey)). Counting every literal of that
    shape covers both, and a misspelt one shows up as a key with no entry.
    """
    keys: dict[str, set[str]] = {}
    for name, source in _client().items():
        if name == "ui_text.js":
            continue
        for _, text in _literals(source):
            if _KEY_LITERAL.match(text):
                keys.setdefault(text, set()).add(name)
        # Calls inside a template literal's ${...}, which the tokenizer
        # reads as part of the template.
        for key in re.findall(r"\bt(?:Node)?\(\s*\"([^\"]+)\"", source):
            if _KEY_LITERAL.match(key):
                keys.setdefault(key, set()).add(name)
    return keys


def _html_keys() -> set[str]:
    html = (_STATIC / "index.html").read_text()
    keys = set(re.findall(r'data-i18n="([^"]+)"', html))
    for attributes in re.findall(r'data-i18n-attr="([^"]+)"', html):
        for pair in attributes.split(";"):
            if "=" in pair:
                keys.add(pair.split("=", 1)[1].strip())
    return keys


def test_every_text_key_resolves_in_both_languages() -> None:
    table = _ui_text()
    used = set(_called_keys()) | _html_keys()
    missing = sorted(key for key in used if key not in table)
    assert not missing, f"keys with no UI_TEXT entry: {missing[:10]}"
    half = sorted(
        key
        for key, entry in table.items()
        if not entry.get("ko") or not entry.get("en")
    )
    assert not half, f"UI_TEXT entries missing a language: {half[:10]}"


def test_english_texts_hold_no_hangul_and_every_entry_is_used() -> None:
    table = _ui_text()
    korean = sorted(key for key, entry in table.items() if _HANGUL.search(entry["en"]))
    assert not korean, f"English texts with Korean in them: {korean[:10]}"
    used = set(_called_keys()) | _html_keys()
    unused = sorted(set(table) - used)
    assert not unused, f"UI_TEXT entries nothing uses: {unused[:10]}"


def test_both_languages_fill_the_same_holes() -> None:
    table = _ui_text()
    uneven = sorted(
        key
        for key, entry in table.items()
        if sorted(_HOLE.findall(entry["ko"])) != sorted(_HOLE.findall(entry["en"]))
    )
    assert not uneven, f"ko and en take different {{holes}}: {uneven[:10]}"


def _korean_tables() -> dict[str, dict[str, str]]:
    """The Korean label tables as {name: {key: text}}, read from the source."""
    tables: dict[str, dict[str, str]] = {}
    for filename in ("labels.js", "core.js"):
        source = (_STATIC / filename).read_text()
        for name in re.findall(r"^const ([A-Z_]*LABELS) = \{", source, re.MULTILINE):
            if name == "TERMS":
                continue
            block = re.search(rf"^const {name} = \{{(.*?)\n\}};", source, re.S | re.M)
            assert block
            rows = {}
            for match in re.finditer(
                r'^\s{2}("?)([A-Za-z_0-9]+)\1:\s*\n?\s*"((?:[^"\\]|\\.)*)"',
                block.group(1),
                re.M,
            ):
                rows[match.group(2)] = match.group(3)
            tables[name] = rows
        lists = re.findall(r"^const (SEAT_KINDS|AGENT_ICON_GROUPS) = \[", source, re.M)
        for name in lists:
            block = re.search(rf"^const {name} = \[(.*?)\n\];", source, re.S | re.M)
            assert block
            pairs = re.findall(r'\["([a-z_]+)",\s*"([^"]*)"\]', block.group(1))
            tables[name] = dict(pairs)
    return tables


def test_english_label_tables_mirror_the_korean() -> None:
    english = _json_const("LABELS_EN", "labels_en.js")
    problems = []
    for name, korean in _korean_tables().items():
        twin = english.get(name)
        if twin is None:
            problems.append(f"{name}: no English twin")
            continue
        if set(twin) != set(korean):
            missing = sorted(set(korean) - set(twin))[:5]
            extra = sorted(set(twin) - set(korean))[:5]
            problems.append(f"{name}: keys differ (missing {missing}, extra {extra})")
        for key in set(twin) & set(korean):
            if _HANGUL.search(twin[key]):
                problems.append(f"{name}.{key}: Korean in the English")
            if sorted(_TERM.findall(twin[key])) != sorted(_TERM.findall(korean[key])):
                problems.append(f"{name}.{key}: term tokens differ from the Korean")
    assert not problems, "; ".join(problems[:12])


# English on purpose in Korean text: the glossary has no row for these yet
# (docs/rules/glossary-ko.md, "아직 채우지 않은 것"), or they are a Leader's own
# name. scripts/e2e/log_words.py keeps the same list for the rendered log.
_KOREAN_KEEPS_ENGLISH = (
    "Other Memories",
    "Memories returned",
    "Memories",
    "Secret Project",
    "Wild card",
    "Crysknife",
    "Immediate",
    "Usurp",
    "Feyd",
    "Into the Fray",
    "Fedaykin Maneuver",
)
# Glossary rows the UI applies that have no TERMS entry of their own.
_GLOSSARY_WORDS = {
    "aside",
    "atomics",
    "bloodlines",
    "embassy",
    "flip",
    "flipped",
    "immortality",
    "infiltrate",
    "intelligence",
    "ixian",
    "navigation",
    "tactics",
    "uprising",
}
_TERM_FILLERS = {"a", "an", "and", "any", "card", "cards", "for", "in", "of", "on"}
_TERM_FILLERS |= {"one", "or", "the", "this", "to", "turn", "two"}


def test_korean_text_never_spells_a_glossary_term_in_english() -> None:
    """A rule word the glossary gives in Korean is never left in English.

    The guards above look at what a table holds, not at what its Korean says;
    on 2026-09-21 eleven chrome strings still read "Hand (공개)", "내 discard",
    "Navigation 3장 남음", "(Flip됨)", "Ixian Embassy", "Bloodlines 확장" and the
    like. Proper nouns (catalog names) and the phrases the glossary has no
    row for stay English; file paths are not words.
    """
    labels = (_STATIC / "labels.js").read_text()
    block = re.search(r"^const TERMS = \{(.*?)\n\};", labels, re.S | re.M)
    assert block
    english = re.findall(r'^\s+[a-z_]+: \{[^}]*en: "([^"]*)"', block.group(1), re.M)
    assert english, "no TERMS entry read — the pattern is broken"
    words = {w.lower() for phrase in english for w in re.findall(r"[A-Za-z]+", phrase)}
    words = (words - _TERM_FILLERS) | _GLOSSARY_WORDS

    names: set[str] = set()
    for table in build_catalog().values():
        if not isinstance(table, dict):
            continue
        for entry in table.values():
            name = entry.get("name") if isinstance(entry, dict) else None
            if isinstance(name, str):
                names.add(name)
    keep = sorted(names | set(_KOREAN_KEEPS_ENGLISH), key=len, reverse=True)

    texts = [
        (f"{table}.{key}", text)
        for table, rows in _korean_tables().items()
        for key, text in rows.items()
    ]
    texts += [(f"UI_TEXT.{key}", entry["ko"]) for key, entry in _ui_text().items()]
    leaks = []
    for where, text in texts:
        bare = re.sub(r"\{\{?[A-Za-z0-9_:]+\}?\}|\S*/\S*", " ", text)
        for name in keep:
            bare = bare.replace(name, " ")
        found = sorted(
            {w for w in re.findall(r"[A-Za-z]+", bare) if w.lower() in words}
        )
        if found:
            leaks.append(f"{where}: {found} in {text!r}")
    assert not leaks, "; ".join(leaks[:10])


# Catalog names the glossary still gives in Korean where they are a status
# rather than the board space: the High Council seat (원로회) and the
# Swordmaster (소드마스터) [Main p. 17]. The guard above strips catalog
# names, so it cannot see these in Korean text.
_KOREAN_STATUS_NAMES = ("High Council", "Swordmaster")


def test_korean_text_names_the_council_seat_and_swordmaster_in_korean() -> None:
    texts = [
        (f"{table}.{key}", text)
        for table, rows in _korean_tables().items()
        for key, text in rows.items()
    ]
    texts += [(f"UI_TEXT.{key}", entry["ko"]) for key, entry in _ui_text().items()]
    prompts = (_STATIC / "prompts_ko.js").read_text()
    korean_prompts = re.findall(r'^\s+"[^"]*": "([^"]*)",?$', prompts, re.M)
    texts += [("PROMPT_KO", ko) for ko in korean_prompts]
    assert len(texts) > 300, "the tables were not read"
    leaks = [
        f"{where}: {text!r}"
        for where, text in texts
        for name in _KOREAN_STATUS_NAMES
        if name in text
    ]
    assert not leaks, "; ".join(leaks[:10])


def test_every_label_table_switches_language() -> None:
    """A table left out of ``LABEL_TABLES`` stays Korean in English.

    setLanguage() swaps only the tables i18n.js names; the mirror test above
    checks that an English twin exists, not that anything ever reads it.
    """
    registered = re.search(
        r"^const LABEL_TABLES = \{(.*?)\n\};",
        (_STATIC / "i18n.js").read_text(),
        re.S | re.M,
    )
    assert registered
    names = set(re.findall(r"^\s+([A-Z_]+),", registered.group(1), re.M))
    lists = {"SEAT_KINDS", "AGENT_ICON_GROUPS"}  # LABEL_LISTS, swapped apart
    missing = sorted(set(_korean_tables()) - lists - names)
    assert not missing, f"label tables setLanguage() never swaps: {missing}"


def test_static_page_keys_exist_and_match_the_korean() -> None:
    table = _ui_text()
    html = (_STATIC / "index.html").read_text()
    wrong = []
    for match in re.finditer(r'data-i18n="([^"]+)"[^>]*>([^<]*)<', html):
        key, inline = match.group(1), " ".join(match.group(2).split())
        if key not in table:
            wrong.append(f"{key}: no entry")
        elif inline != " ".join(table[key]["ko"].split()):
            wrong.append(f"{key}: inline {inline!r} != {table[key]['ko']!r}")
    assert not wrong, "; ".join(wrong[:10])
    leftover = [
        " ".join(text.split())
        for text in re.findall(r">([^<>]*[가-힣][^<>]*)<", html)
    ]
    marked = {
        " ".join(m.group(2).split())
        for m in re.finditer(r'data-i18n="([^"]+)"[^>]*>([^<]*)<', html)
    }
    unmarked = [text for text in leftover if text not in marked]
    assert not unmarked, f"Korean text in index.html without data-i18n: {unmarked[:8]}"


def _prompts() -> set[str]:
    """Every prompt literal a PlayerDecision can carry, f-strings as patterns.

    Chance decisions ("Shuffle …", "Deal …") are resolved by the engine and
    never shown to a person; they are left out by their ChanceDecision call.
    """
    prompts: set[str] = set()
    for path in sorted(_RULES.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            # A prompt built by a helper (reveal_choice_prompt): every string
            # it can return.
            if isinstance(node, ast.FunctionDef) and node.name.endswith("_prompt"):
                for inner in ast.walk(node):
                    if (
                        isinstance(inner, ast.Constant)
                        and isinstance(inner.value, str)
                        and inner is not getattr(node.body[0], "value", None)
                    ):
                        prompts.add(inner.value)
                continue
            if not isinstance(node, ast.Call):
                continue
            callee = node.func.id if isinstance(node.func, ast.Name) else getattr(
                node.func, "attr", ""
            )
            if callee != "PlayerDecision":
                continue
            for keyword in node.keywords:
                if keyword.arg != "prompt":
                    continue
                # Every string the value can be, a conditional's branches
                # included ("… with Deep Cover" if deep_cover else "…"); an
                # f-string counts whole, not as its literal pieces.
                pieces = {
                    id(piece)
                    for joined in ast.walk(keyword.value)
                    if isinstance(joined, ast.JoinedStr)
                    for piece in joined.values
                }
                for value in ast.walk(keyword.value):
                    if id(value) in pieces:
                        continue
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        prompts.add(value.value)
                    elif isinstance(value, ast.JoinedStr):
                        parts = []
                        for piece in value.values:
                            if isinstance(piece, ast.Constant):
                                parts.append(str(piece.value))
                            else:
                                parts.append("{}")
                        prompts.add("".join(parts))
    return prompts


def test_every_person_facing_prompt_has_korean() -> None:
    korean = _json_const("PROMPT_KO", "prompts_ko.js")
    patterns = [
        re.compile(source)
        for source, _ in _json_const("PROMPT_KO_PATTERNS", "prompts_ko.js")
    ]
    missing = []
    for prompt in sorted(_prompts()):
        if prompt in korean:
            continue
        # An f-string hole holds a number or a resource name (combat.py's
        # optional payment is spice or solari, .title()d).
        holes = prompt.count("{}")
        samples = [prompt]
        for _ in range(holes):
            samples = [
                sample.replace("{}", value, 1)
                for sample in samples
                for value in ("3", "Spice", "Solari")
            ]
        if any(pattern.fullmatch(sample) for sample in samples for pattern in patterns):
            continue
        missing.append(prompt)
    assert not missing, f"{len(missing)} prompts with no Korean: {missing[:8]}"
    stray = sorted(key for key, text in korean.items() if not _HANGUL.search(text))
    assert not stray, f"PROMPT_KO entries that are not Korean: {stray[:5]}"
