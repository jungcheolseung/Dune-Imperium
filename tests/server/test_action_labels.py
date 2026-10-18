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

import ast
import re
from pathlib import Path

from dune_imperium.rules.ability_executor import table_event_kinds
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
    # The pending-ability executor names its refusal and "named for later"
    # events through tables (composed effects, codec v148).
    kinds.update(table_event_kinds())
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


def _event_emitters(kind: str) -> list[tuple[Path, ast.FunctionDef, set[str]]]:
    """(file, innermost function, payload keys) of every ``kind="<kind>"``
    call in the engine sources; the keys are the literal ones of a
    ``payload=((key, value), ...)`` tuple."""

    found: list[tuple[Path, ast.FunctionDef, set[str]]] = []

    def visit(node: ast.AST, path: Path, owner: ast.FunctionDef | None) -> None:
        if isinstance(node, ast.FunctionDef):
            owner = node
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if (
                    keyword.arg == "kind"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value == kind
                ):
                    assert owner is not None, f"{path}: {kind} outside a function"
                    payload = next(
                        (k.value for k in node.keywords if k.arg == "payload"), None
                    )
                    keys = {
                        pair.elts[0].value
                        for pair in getattr(payload, "elts", ())
                        if isinstance(pair, ast.Tuple)
                        and pair.elts
                        and isinstance(pair.elts[0], ast.Constant)
                        and isinstance(pair.elts[0].value, str)
                    }
                    found.append((path, owner, keys))
        for child in ast.iter_child_nodes(node):
            visit(child, path, owner)

    for directory in _SOURCE_DIRS:
        for path in sorted(directory.rglob("*.py")):
            visit(ast.parse(path.read_text()), path, None)
    return found


def _implied_leaders() -> dict[str, str]:
    """panels.js EVENT_IMPLIED_LEADER: {event kind: the Leader it names}."""
    source = (_STATIC_DIR / "panels.js").read_text()
    block = re.search(
        r"^const EVENT_IMPLIED_LEADER = \{(.*?)\n\};", source, re.S | re.M
    )
    assert block, "no EVENT_IMPLIED_LEADER block in panels.js"
    rows = dict(
        re.findall(r'^\s{2}([a-z_]+): \{\s*leader: "([a-z_]+)"', block.group(1), re.M)
    )
    # The table may be empty (cleanup-2c-4), but a row the pattern cannot
    # read must not pass for a missing one.
    assert len(rows) == block.group(1).count("leader:"), (
        "an EVENT_IMPLIED_LEADER row was not read: the pattern is broken"
    )
    return rows


def test_an_implied_leader_event_has_one_emitter_naming_that_leader() -> None:
    """The log names a Leader for an event whose payload names none.

    User report 2026-10-10: Staban Tuek's Smuggle Spice payout read "지도자
    능력으로 스파이스 획득" with neither the Leader nor the ability named. The
    client then named them from a table, panels.js EVENT_IMPLIED_LEADER, which
    is right only while the kind has one emitter in the engine and the emitter
    pays that Leader alone. Cleanup-2c-4 made Smuggle Spice a plain
    ``resources_gained`` whose source names the Leader
    (``round:R:player:P:leader:staban_tuek``), so the table is empty now; the
    check stays for a kind that is added to it again.
    """
    implied = _implied_leaders()
    for kind, leader in implied.items():
        emitters = _event_emitters(kind)
        assert len(emitters) == 1, (
            f"{kind}: {len(emitters)} emitters "
            f"{[(p.name, f.name) for p, f, _ in emitters]}; panels.js "
            "EVENT_IMPLIED_LEADER can name only one Leader"
        )
        path, function, _ = emitters[0]
        named = {
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert leader in named, (
            f"{kind}: {path.name} {function.name} never names {leader}"
        )


def test_no_signet_event_writes_bonus_spice() -> None:
    """Esmar Tuek's Smuggle Spice ("Place 1 bonus spice on Tuek's Sietch -or-
    take 1 bonus spice from a Maker board space" [Esmar Tuek card]) used to
    write the space's ``bonus_spice`` change on ``leader_signet_resolved``,
    which panels.js logEventPayload read as a bonus spice taken. The Signet
    box's event carries only the card and the seat now (cleanup-2c-4: what
    the ability gave is a ``resources_gained``, tests/unit/rules/
    test_bloodlines_leaders.py pins it), so no writer is left."""
    writers = [
        (path.name, function.name)
        for path, function, keys in _event_emitters("leader_signet_resolved")
        if "bonus_spice" in keys
    ]
    assert writers == []
