"""Guard: the action log's picture table names real event kinds and pictures.

The client is dependency-free vanilla JS with no JS test runner, so the
table (``LOG_EVENT_ICONS`` in ``static/log_icons.js``) is read from Python
the way ``test_action_labels.py`` reads ``EVENT_LABELS``: every client script
is searched, so moving the table to another file keeps the guard on.

A key names a rulebook icon (``display.icons.ICON_NAMES``), one of the log's
own pictures (``log:``, ``display.log_icons.LOG_ICON_NAMES``) or an Alliance
token (``alliance:``, ``display.token_images.ALLIANCE_TOKEN_FACTIONS``);
``{faction}`` and ``{agent_icon}`` expand to every value the engine writes
there. A misspelt name would only show as a line without its picture.
"""

import re
from pathlib import Path

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.display.icons import ICON_NAMES
from dune_imperium.display.log_icons import LOG_ICON_NAMES
from dune_imperium.display.token_images import ALLIANCE_TOKEN_FACTIONS

_STATIC_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "dune_imperium" / "server" / "static"
)
_SLOT_VALUES = {
    "faction": tuple(faction.value for faction in Faction),
    "agent_icon": tuple(icon.value for icon in AgentIcon),
}


def _table(name: str) -> str:
    matches: list[str] = [
        found
        for path in sorted(_STATIC_DIR.glob("*.js"))
        for found in re.findall(
            rf"const {name} = \{{(.*?)\n\}};", path.read_text(), re.DOTALL
        )
    ]
    assert matches, f"no {name} block in any of {_STATIC_DIR}/*.js"
    assert len(matches) == 1, f"{name} is defined more than once"
    return matches[0]


def _log_event_icons() -> dict[str, str]:
    body = _table("LOG_EVENT_ICONS")
    entries = re.findall(r'^\s{2}([a-z_]+): "([^"]+)",$', body, re.MULTILINE)
    keys = [kind for kind, _ in entries]
    assert len(keys) == len(set(keys)), "a kind is listed twice"
    # Every line of the block is an entry or a comment: nothing is skipped.
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    assert len(entries) == sum(not line.startswith("//") for line in lines)
    return dict(entries)


def _event_label_kinds() -> set[str]:
    return set(re.findall(r"^\s{2}([a-z_]+):", _table("EVENT_LABELS"), re.MULTILINE))


def _expansions(template: str) -> list[str]:
    slots = re.findall(r"\{([a-z_]+)\}", template)
    assert len(slots) <= 1, template
    if not slots:
        return [template]
    slot = slots[0]
    assert slot in _SLOT_VALUES, f"unknown slot {{{slot}}} in {template}"
    return [template.replace(f"{{{slot}}}", value) for value in _SLOT_VALUES[slot]]


def test_every_log_icon_kind_is_a_labelled_event_kind() -> None:
    table = _log_event_icons()
    assert len(table) > 100, "LOG_EVENT_ICONS scan is broken"
    unknown = set(table) - _event_label_kinds()
    assert not unknown, f"log icons for unknown event kinds: {sorted(unknown)}"


def test_every_log_icon_names_an_existing_picture() -> None:
    missing: list[str] = []
    for kind, template in _log_event_icons().items():
        for key in _expansions(template):
            if key.startswith("log:"):
                known = key.removeprefix("log:") in LOG_ICON_NAMES
            elif key.startswith("alliance:"):
                known = key.removeprefix("alliance:") in ALLIANCE_TOKEN_FACTIONS
            else:
                known = key in ICON_NAMES
            if not known:
                missing.append(f"{kind}: {key}")
    assert not missing, f"log icons naming no picture: {missing}"


def test_every_log_picture_is_used() -> None:
    """A picture nothing shows is not worth extracting. The Round numerals
    head a "game" card (log_icons.js neutralLogIcon), not an event line."""
    used = {
        key.removeprefix("log:")
        for template in _log_event_icons().values()
        for key in _expansions(template)
        if key.startswith("log:")
    }
    rounds = {name for name in LOG_ICON_NAMES if name.startswith("round_")}
    assert set(LOG_ICON_NAMES) - rounds == used
