"""Guard: every engine action id has a Korean label in the browser UI.

The client is dependency-free vanilla JS with no JS test runner, so the
label table is checked from Python: the engine's action ids are the keys of
its dispatcher (``ACTION_HANDLERS``) plus every ``action_id="..."`` literal in
the rules sources, and each must be a key of the ``ACTION_LABELS`` object in
the client. The literal scan alone missed six ids written through a constant
or a conditional (``select_long_live_fighters_draw``, ``pay_agent_card_water``
…), which the log printed as prettified English.

The table lives in ``static/labels.js``, but this scan searches every client
script rather than naming one file, so splitting the client further does not
silently turn the guard off.
"""

import re
from pathlib import Path

from dune_imperium.rules.engine import ACTION_HANDLERS

_REPO = Path(__file__).resolve().parents[2]
_SOURCE_DIRS = (
    _REPO / "src" / "dune_imperium" / "rules",
    _REPO / "src" / "dune_imperium" / "core",
    _REPO / "src" / "dune_imperium" / "simulation",
)
_STATIC_DIR = _REPO / "src" / "dune_imperium" / "server" / "static"


def _engine_action_ids() -> set[str]:
    ids: set[str] = set(ACTION_HANDLERS)
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


def _engine_event_kinds() -> set[str]:
    """Every event kind the engine can emit.

    Not just the ``kind="literal"`` keyword: the engine also writes
    ``kind = "x"`` and picks one of two with ``kind=("a" if ... else "b")``.
    A scan that only matched the first form missed four kinds that a real
    game emits 62 times, so it took every string in the assignment. The
    parentheses are optional: ``kind="alliance_gained" if holder is None else
    "alliance_transferred"`` went unlabelled until the pattern allowed that.
    """
    kinds: set[str] = set()
    for directory in _SOURCE_DIRS:
        for path in directory.rglob("*.py"):
            text = path.read_text()
            # kind="x" and kind = "x"
            kinds.update(re.findall(r'kind\s*=\s*"([a-z_]+)"', text))
            # kind=("a" if <cond> else "b")
            for first, second in re.findall(
                r'kind\s*=\s*\(?\s*"([a-z_]+)"\s+if\b[^()]*?\belse\s+"([a-z_]+)"',
                text,
                re.DOTALL,
            ):
                kinds.update((first, second))
    return kinds


def _labelled_event_kinds() -> set[str]:
    matches = [
        found
        for path in sorted(_STATIC_DIR.glob("*.js"))
        for found in re.findall(
            r"const EVENT_LABELS = \{(.*?)\n\};", path.read_text(), re.DOTALL
        )
    ]
    assert matches, f"no EVENT_LABELS block in any of {_STATIC_DIR}/*.js"
    assert len(matches) == 1, "EVENT_LABELS is defined more than once"
    return set(re.findall(r"^\s{2}([a-z_]+):", matches[0], re.MULTILINE))


def test_every_engine_event_kind_has_a_label() -> None:
    """Without a label the log prints prettify(kind), which is English.

    Measured before this guard existed: 93 unlabelled kinds accounted for
    40% of the event lines in three full all-expansion games.
    """
    engine_kinds = _engine_event_kinds()
    assert engine_kinds, "no event kinds found — scan is broken"
    missing = engine_kinds - _labelled_event_kinds()
    assert not missing, f"event kinds without UI labels: {sorted(missing)}"


def test_labels_do_not_reference_removed_event_kinds() -> None:
    stale = _labelled_event_kinds() - _engine_event_kinds()
    assert not stale, f"labels for unknown event kinds: {sorted(stale)}"
