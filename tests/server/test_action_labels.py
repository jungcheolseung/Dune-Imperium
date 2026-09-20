"""Guard: every engine action id has a Korean label in the browser UI.

The client is dependency-free vanilla JS with no JS test runner, so the
label table is checked from Python by scanning the rules sources for
``action_id="..."`` literals and asserting each appears as a key of the
``ACTION_LABELS`` object in the client.

The table lives in ``static/labels.js``, but this scan searches every client
script rather than naming one file, so splitting the client further does not
silently turn the guard off.
"""

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SOURCE_DIRS = (
    _REPO / "src" / "dune_imperium" / "rules",
    _REPO / "src" / "dune_imperium" / "core",
    _REPO / "src" / "dune_imperium" / "simulation",
)
_STATIC_DIR = _REPO / "src" / "dune_imperium" / "server" / "static"


def _engine_action_ids() -> set[str]:
    ids: set[str] = set()
    for directory in _SOURCE_DIRS:
        for path in directory.rglob("*.py"):
            ids.update(
                re.findall(r'action_id="([a-z_]+)"', path.read_text())
            )
    return ids


def _labelled_action_ids() -> set[str]:
    matches = [
        found
        for path in sorted(_STATIC_DIR.glob("*.js"))
        for found in re.findall(
            r"const ACTION_LABELS = \{(.*?)\n\};", path.read_text(), re.DOTALL
        )
    ]
    assert matches, f"no ACTION_LABELS block in any of {_STATIC_DIR}/*.js"
    assert len(matches) == 1, "ACTION_LABELS is defined more than once"
    return set(re.findall(r"^\s{2}([a-z_]+):", matches[0], re.MULTILINE))


def test_every_engine_action_id_has_a_label() -> None:
    engine_ids = _engine_action_ids()
    labelled = _labelled_action_ids()
    assert engine_ids, "no action ids found — scan is broken"
    missing = engine_ids - labelled
    assert not missing, f"action ids without UI labels: {sorted(missing)}"


def test_labels_do_not_reference_removed_action_ids() -> None:
    stale = _labelled_action_ids() - _engine_action_ids()
    assert not stale, f"labels for unknown action ids: {sorted(stale)}"
