"""Share the browser's reviewed literal tables without executing JavaScript."""

import json
import re
from pathlib import Path
from typing import Any

STATIC = Path(__file__).resolve().parents[1] / "server" / "static"
TABLES = (
    "ACTION_LABELS", "EVENT_LABELS", "PHASE_LABELS", "FACTION_LABELS", "VALUE_LABELS",
    "PAYLOAD_KEY_LABELS",
)


def _block(source: str, name: str) -> str:
    match = re.search(rf"const {name} = (\{{.*?\n\}});", source, re.DOTALL)
    if match is None:
        raise ValueError(f"missing UI table: {name}")
    return re.sub(r"/\*.*?\*/", "", match[1], flags=re.DOTALL)


def _words(block: str) -> dict[str, str]:
    rows = re.findall(
        r'^\s*(?:"([^"]+)"|([a-z_]+)):\s*("(?:[^"\\]|\\.)*")\s*,?\s*$',
        block, re.MULTILINE,
    )
    if not rows:
        raise ValueError("empty UI table")
    return {quoted or bare: json.loads(value) for quoted, bare, value in rows}


def build_ui_data(static: Path = STATIC) -> dict[str, Any]:
    source = (static / "labels.js").read_text(encoding="utf-8")
    korean = {name: _words(_block(source, name)) for name in TABLES}
    english = json.loads(_block(
        (static / "labels_en.js").read_text(encoding="utf-8"), "LABELS_EN"
    ))
    core = (static / "core.js").read_text(encoding="utf-8")
    kinds = re.search(r"const SEAT_KINDS = \[(.*?)\n\];", core, re.DOTALL)
    if kinds is None:
        raise ValueError("missing seat kind names")
    korean["SEAT_KINDS"] = {
        key: json.loads(text)
        for key, text in re.findall(
            r'\["([a-z_]+)",\s*("(?:[^"\\]|\\.)*")\]', kinds[1]
        )
    }
    groups = re.search(r"const AGENT_ICON_GROUPS = \[(.*?)\n\];", core, re.DOTALL)
    if groups is None:
        raise ValueError("missing Agent icon names")
    korean["AGENT_ICON_GROUPS"] = {
        key: json.loads(text)
        for key, text in re.findall(
            r'\["([a-z_]+)",\s*("(?:[^"\\]|\\.)*")\]', groups[1]
        )
    }
    if set(korean["AGENT_ICON_GROUPS"]) != set(english["AGENT_ICON_GROUPS"]):
        raise ValueError("Agent icon language keys differ")
    terms = {}
    for key, value in re.findall(
        r"^\s{2}([a-z_]+):\s*\{(.*?)\}",
        _block(source, "TERMS"), re.MULTILINE | re.DOTALL,
    ):
        words = {
            name: json.loads(text)
            for name, text in re.findall(r'(ko|en):\s*("(?:[^"\\]|\\.)*")', value)
        }
        if set(words) != {"ko", "en"}:
            raise ValueError(f"incomplete term: {key}")
        terms[key] = words
    if not terms:
        raise ValueError("empty rule-term table")
    for name in TABLES:
        if set(korean[name]) != set(english[name]):
            raise ValueError(f"UI language keys differ: {name}")
    prompts = json.loads(_block(
        (static / "prompts_ko.js").read_text(encoding="utf-8"), "PROMPT_KO"
    ))
    ui = json.loads(_block(
        (static / "ui_text.js").read_text(encoding="utf-8"), "UI_TEXT"
    ))
    if not all(set(pair) == {"ko", "en"} for pair in ui.values()):
        raise ValueError("incomplete UI translation")
    return {
        "ko": korean, "en": english, "terms": terms, "prompts": prompts,
        "ui": ui,
    }


def write_ui_data(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_ui_data(), ensure_ascii=False), encoding="utf-8")
