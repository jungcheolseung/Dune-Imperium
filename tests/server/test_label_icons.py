"""Guard: one rulebook icon per effect in the log and choice labels.

User report 2026-10-11 (after a real game): the activity log read "책략
뽑기" as the draw-Intrigue icon followed by the draw-a-card icon, and trash
labels the same way. Our labels wrote a noun term and a verb term side by
side ("{intrigue} {draw}", "카드 {trash}"), and ``phrase()`` turns every
``{term}`` that has an icon into that icon. But each rulebook icon already
stands for a whole effect ([Main p. 20], docs/rules/glossary-ko.md "카드
동작"): ``{draw}`` is "Draw a card", ``{intrigue}`` "Draw an Intrigue card",
``{discard}`` "Discard a card", ``{trash}`` "Trash one card",
``{trash_intrigue}`` "Trash an Intrigue card", ``{steal_intrigue}`` "Steal
Intrigue". The user chose "맞는 아이콘 하나로": a label naming one of those
effects writes that one icon; anything else the icons do not mean (an
Intrigue card as a noun, trashing this card, a Tech tile, a Spy, ...) is
written in words.

Printed-card twins (display/leaders_ko.py and the like) keep the icons the
card prints and are not scanned here.
"""

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_STATIC = _REPO / "src" / "dune_imperium" / "server" / "static"
_DISPLAY = _REPO / "src" / "dune_imperium" / "display"

# One effect written as two icons, or an icon for something it does not mean.
_FORBIDDEN = tuple(
    re.compile(pattern)
    for pattern in (
        # Draw an Intrigue card + draw a card.
        r"\{intrigue\}\s*\{draw\}",
        r"\{draw\}:?\s*\{intrigue\}",
        # Draw an Intrigue card + trash a card, for "trash an Intrigue card".
        r"\{intrigue\}\s*\{trash\}",
        r"\{trash\}:?\s*\{intrigue\}",
        # "card" beside the icon that already means "a card".
        r"카드 \{(?:draw|trash|discard)\}",
        r"카드 \d+장 \{(?:draw|trash|discard)\}",
        r"\{(?:draw|trash|discard)\}(?: \d+)? [Cc]ards?\b(?! [Ee]ffect)",
        # The trash icon on what it does not trash.
        r"\{(?:tech_tile|spy|contract|commander_skill)\}\s*\{trash\}",
        r"\{trash\}:?\s*\{(?:tech_tile|spy|contract|commander_skill)\}",
        r"\{spy\}를 \{trash\}",
        r"이 카드를? \{trash\}",
        r"\{trash\} [Tt]his [Cc]ard",
        r"\{trash\}:? another",
        r"\{trash\}:? [Bb]orrowed",
        r"빌린 카드 \{trash\}",
        r"\{\{card\}\} \{trash\}",
        r"\{trash\} \{\{card\}\}",
        # The draw-Intrigue icon for an Intrigue card that is played.
        r"\{intrigue\} 사용",
        r"(?:Play|Played) \{intrigue\}|\{intrigue\} Played",
        r"\{trash\}할 \{intrigue\}",
    )
)


def _json_const(name: str, filename: str) -> object:
    source = (_STATIC / filename).read_text()
    match = re.search(rf"^const {name} = (.*?);\n", source, re.MULTILINE | re.DOTALL)
    assert match, f"{name} not found in {filename}"
    return json.loads(match.group(1))


def _korean_label_texts() -> list[tuple[str, str]]:
    """Every string in labels.js's ``*_LABELS`` tables."""

    source = (_STATIC / "labels.js").read_text()
    texts: list[tuple[str, str]] = []
    for block in re.finditer(
        r"^const ([A-Z_]*LABELS) = \{(.*?)\n\};", source, re.MULTILINE | re.DOTALL
    ):
        for key, text in re.findall(
            r'^\s+"?([A-Za-z_0-9]+)"?:\s*\n?\s*"((?:[^"\\]|\\.)*)"',
            block.group(2),
            re.MULTILINE,
        ):
            texts.append((f"{block.group(1)}.{key}", text))
    assert len(texts) > 300, "labels.js tables were not read"
    return texts


def _client_texts() -> list[tuple[str, str]]:
    texts = _korean_label_texts()
    english = _json_const("LABELS_EN", "labels_en.js")
    assert isinstance(english, dict)
    for table, rows in english.items():
        texts += [(f"LABELS_EN.{table}.{key}", text) for key, text in rows.items()]
    ui_text = _json_const("UI_TEXT", "ui_text.js")
    assert isinstance(ui_text, dict)
    for key, entry in ui_text.items():
        texts += [(f"UI_TEXT.{key}.{lang}", entry[lang]) for lang in ("ko", "en")]
    prompts = _json_const("PROMPT_KO", "prompts_ko.js")
    assert isinstance(prompts, dict)
    texts += [(f"PROMPT_KO.{key}", text) for key, text in prompts.items()]
    patterns = _json_const("PROMPT_KO_PATTERNS", "prompts_ko.js")
    assert isinstance(patterns, list)
    texts += [(f"PROMPT_KO_PATTERNS.{source}", text) for source, text in patterns]
    return texts


def _offenders(texts: list[tuple[str, str]]) -> list[str]:
    return [
        f"{where}: {text!r}"
        for where, text in texts
        for pattern in _FORBIDDEN
        if pattern.search(text)
    ]


def test_client_labels_write_one_icon_per_effect() -> None:
    offenders = _offenders(_client_texts())
    assert not offenders, "; ".join(offenders[:20])


def test_generated_display_lines_write_one_icon_per_effect() -> None:
    """Our own generated Korean lines (not printed-card twins): the choice
    and unavailable-reason text the seat reads beside the labels."""

    texts = [
        (f"{name}:{number}", line)
        for name in ("actions.py", "unavailable.py", "scouts.py")
        for number, line in enumerate(
            (_DISPLAY / name).read_text().splitlines(), start=1
        )
    ]
    offenders = _offenders(texts)
    assert not offenders, "; ".join(offenders[:20])


def test_an_intrigue_card_named_as_a_noun_is_a_word() -> None:
    """``{intrigue_card}`` is the noun, a word with no icon; ``{intrigue}``
    stays the draw-an-Intrigue-card icon."""

    source = (_STATIC / "labels.js").read_text()
    row = re.search(r"^\s{2}intrigue_card: \{([^}]*)\},$", source, re.MULTILINE)
    assert row, "TERMS has no intrigue_card row"
    assert "icon: null" in row.group(1)
    assert 'ko: "책략 카드"' in row.group(1)
    assert 'en: "Intrigue card"' in row.group(1)
    korean = dict(_korean_label_texts())
    english = _json_const("LABELS_EN", "labels_en.js")
    assert isinstance(english, dict)
    assert korean["EVENT_LABELS.intrigue_card_drawn"] == "{intrigue}"
    assert english["EVENT_LABELS"]["intrigue_card_drawn"] == "{intrigue}"
    assert korean["EVENT_LABELS.intrigue_played"] == "{intrigue_card} 사용"
    assert english["EVENT_LABELS"]["intrigue_played"] == "{intrigue_card} Played"
    assert korean["EVENT_LABELS.intrigue_card_trashed"] == "{trash_intrigue}"
    assert korean["EVENT_LABELS.intrigue_card_stolen"] == "{steal_intrigue}"
    assert korean["EVENT_LABELS.card_trashed"] == "{trash}"
    assert korean["EVENT_LABELS.cards_drawn"] == "{draw}"
