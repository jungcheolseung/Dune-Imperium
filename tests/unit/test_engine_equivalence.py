"""The engine equivalence tool and its declared differences (scripts/ab).

docs/composed-effects-plan.md 5 "정리 단계" 2: the cleanup stage changes events,
rows and windows on purpose, so ``engine_equivalence.py check`` translates the
base's recording with declared rules and still reports every other
difference. A candidate engine here is the real engine with one change
patched in.
"""

import importlib.util
import pickle
import sys
import zlib
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import dune_imperium
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import Transition
from dune_imperium.core.events import GameEvent
from dune_imperium.display import unavailable
from dune_imperium.rules import UprisingRulesEngine

_AB = Path(__file__).resolve().parents[2] / "scripts" / "ab"
SPEC: tuple[str, dict[str, bool], int, tuple[str, ...]] = (
    "game",
    {},
    8_130_000,
    ("random",) * 4,
)
CONFIRM = "probe_confirm"


@pytest.fixture
def eq(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    monkeypatch.syspath_prepend(str(_AB))
    spec = importlib.util.spec_from_file_location(
        "engine_equivalence", _AB / "engine_equivalence.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "MAX_STEPS", 250)
    monkeypatch.setattr(_Confirming, "pending", {})
    yield module
    sys.modules.pop("equivalence_rules", None)


def _record(eq: ModuleType, tmp_path: Path) -> Path:
    eq.record_game((str(tmp_path), SPEC))
    return tmp_path / f"game{eq.SUFFIX}"


def _rules(tmp_path: Path, name: str, body: str) -> str:
    path = tmp_path / f"{name}.py"
    path.write_text(
        "from dune_imperium.core.actions import DomainAction\n"
        "from equivalence_rules import Rule\n\n" + body
    )
    return str(path)


def _common_kind(eq: ModuleType, recording: Path) -> str:
    kinds = [event["kind"] for row in eq.load(recording)["rows"] for event in row[3]]
    return str(max(set(kinds), key=kinds.count))


class _Renaming(UprisingRulesEngine):
    """Names one event kind differently."""

    renamed: dict[str, str] = {}

    def apply(self, state: Any, action: Any, legal_actions: Any = None) -> Transition:
        moved = super().apply(state, action, legal_actions=legal_actions)
        return replace(
            moved,
            events=tuple(
                replace(event, kind=self.renamed.get(event.kind, event.kind))
                for event in moved.events
            ),
        )


def _reversed_deck(state: Any) -> Any:
    """``state`` with seat 0's hidden deck in the other order."""

    first = replace(state.players[0], deck=tuple(reversed(state.players[0].deck)))
    return replace(state, players=(first, *state.players[1:]))


class _Confirming(UprisingRulesEngine):
    """Opens a one-row confirm window after every Agent turn; the confirm
    may announce itself, reorder a hidden deck, or open the window again."""

    pending: dict[int, Any] = {}
    announce = False
    reorder = False
    reopen = False

    def _held(self, state: Any) -> bool:
        return self.pending.get(id(state)) is state

    def current_decision(self, state: Any) -> Any:
        if self._held(state):
            return PlayerDecision(owner=0, prompt="confirm")
        return super().current_decision(state)

    def legal_actions(self, state: Any, player: int) -> Any:
        if self._held(state):
            return (DomainAction(action_id=CONFIRM, actor=0),)
        return super().legal_actions(state, player)

    def apply(self, state: Any, action: Any, legal_actions: Any = None) -> Transition:
        if self._held(state):
            assert action.action_id == CONFIRM
            after = replace(state, revision=state.revision + 1)
            if self.reorder:
                after = _reversed_deck(after)
            if self.reopen:
                self.pending[id(after)] = after
            events = (GameEvent("probe", "probe_confirmed"),) if self.announce else ()
            return Transition(
                state=after, action=action, events=events, next_decision=None
            )
        moved = super().apply(state, action, legal_actions=legal_actions)
        if getattr(action, "action_id", None) == "finish_agent_turn":
            self.pending[id(moved.state)] = moved.state
        return moved


class _ExtraRow(UprisingRulesEngine):
    """Offers one more row, never taken, at every Agent turn."""

    def legal_actions(self, state: Any, player: int) -> Any:
        legal = super().legal_actions(state, player)
        if any(action.action_id == "finish_agent_turn" for action in legal):
            return (*legal, DomainAction(action_id="probe_row", actor=player))
        return legal


def test_the_same_engine_plays_the_same_steps(eq: ModuleType, tmp_path: Path) -> None:
    result = eq.check_game((str(_record(eq, tmp_path)), None))
    assert result["status"] == "same"
    assert result["steps"] == 250
    assert result["hits"] == {}


def test_a_renamed_event_is_reported_until_it_is_declared(
    eq: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = _record(eq, tmp_path)
    kind = _common_kind(eq, recording)
    monkeypatch.setattr(_Renaming, "renamed", {kind: "probe_kind"})
    monkeypatch.setattr(eq, "UprisingRulesEngine", _Renaming)

    undeclared = eq.check_game((str(recording), None))
    assert undeclared["status"] == "different"
    assert undeclared["kinds"] == ["events"]
    assert f'"kind":"{kind}"' in undeclared["diff"]["events"]["old_only"][0]
    assert '"kind":"probe_kind"' in undeclared["diff"]["events"]["new_only"][0]

    rename = _rules(
        tmp_path,
        "rename",
        f'''
def _old(step):
    hit = False
    for event in step.events:
        if event["kind"] == "{kind}":
            event["kind"] = "probe_kind"
            hit = True
    return hit


RULES = (Rule("rename", why="test", old=_old),)
''',
    )
    declared = eq.check_game((str(recording), rename))
    assert declared["status"] == "same"
    assert declared["hits"]["rename:old"] > 0

    # A second, undeclared rename is still caught.
    others = [
        event["kind"]
        for row in eq.load(recording)["rows"]
        for event in row[3]
        if event["kind"] != kind
    ]
    monkeypatch.setattr(
        _Renaming, "renamed", {kind: "probe_kind", others[0]: "probe_other"}
    )
    still = eq.check_game((str(recording), rename))
    assert still["status"] == "different"
    assert '"kind":"probe_other"' in still["diff"]["events"]["new_only"][0]


def test_a_new_window_is_reported_until_a_rule_answers_it(
    eq: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = _record(eq, tmp_path)
    monkeypatch.setattr(_Confirming, "pending", {})
    monkeypatch.setattr(eq, "UprisingRulesEngine", _Confirming)

    undeclared = eq.check_game((str(recording), None))
    assert undeclared["status"] == "different"
    assert "legal" in undeclared["kinds"]
    assert CONFIRM in undeclared["diff"]["legal"]["new_only"][0]

    confirm = _rules(
        tmp_path,
        "confirm",
        f'''
def _answer(at):
    if at.legal and at.legal[0].action_id == "{CONFIRM}":
        return at.legal[0]
    return None


RULES = (Rule("confirm", why="test", answer=_answer),)
''',
    )
    # Each answered move shifts the candidate's revision; the views still match.
    declared = eq.check_game((str(recording), confirm))
    assert declared["status"] == "same"
    assert declared["hits"]["confirm:answer"] > 0


def test_a_step_the_candidate_no_longer_has_vanishes_when_declared(
    eq: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_Confirming, "pending", {})
    with monkeypatch.context() as patch:
        patch.setattr(eq, "UprisingRulesEngine", _Confirming)
        recording = _record(eq, tmp_path)

    undeclared = eq.check_game((str(recording), None))
    assert undeclared["status"] in {"different", "raised"}

    vanish = _rules(
        tmp_path,
        "vanish",
        f'''
def _old(step):
    if step.step[0] == "a" and step.step[1] == "{CONFIRM}":
        step.vanish = True
        return True
    return False


RULES = (Rule("vanish", why="test", old=_old),)
''',
    )
    declared = eq.check_game((str(recording), vanish))
    assert declared["status"] == "same"
    assert declared["hits"]["vanish:old"] > 0


def test_a_row_only_the_candidate_offers_is_normalised_by_a_new_rule(
    eq: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = _record(eq, tmp_path)
    monkeypatch.setattr(eq, "UprisingRulesEngine", _ExtraRow)

    undeclared = eq.check_game((str(recording), None))
    assert undeclared["status"] == "different"
    assert "probe_row" in undeclared["diff"]["legal"]["new_only"][0]

    drop = _rules(
        tmp_path,
        "drop",
        """
def _new(old, candidate):
    if old.step[0] != "a" or candidate.decision is None:
        return False
    rows = [row for row in candidate.decision[1] if row["action_id"] != "probe_row"]
    if len(rows) == len(candidate.decision[1]):
        return False
    candidate.decision[1] = rows
    candidate.page = old.page
    return True


RULES = (Rule("drop", why="test", new=_new),)
""",
    )
    declared = eq.check_game((str(recording), drop))
    assert declared["status"] == "same"
    assert declared["hits"]["drop:new"] > 0


def test_a_state_field_must_be_declared_to_be_left_out(
    eq: ModuleType, tmp_path: Path
) -> None:
    recording = _record(eq, tmp_path)
    # Fields only the base had, with a value (the candidate's digest is the
    # absent value's).
    raw = pickle.loads(zlib.decompress(recording.read_bytes()))
    absent = b"\x01\x02\x03\x04"
    seats = [f"players[{seat}].probe_seat" for seat in range(4)]
    raw["fields"] = (*raw["fields"], "probe_field", *seats)
    raw["schema"]["GameState"] = [*raw["schema"]["GameState"], "probe_field"]
    raw["schema"]["PlayerState"] = [*raw["schema"]["PlayerState"], "probe_seat"]
    raw["initial"] += absent * 5
    raw["columns"]["state"] = [
        digest + absent * 5 for digest in raw["columns"]["state"]
    ]
    recording.write_bytes(zlib.compress(pickle.dumps(raw)))

    undeclared = eq.check_game((str(recording), None))
    assert undeclared["kinds"] == ["fields"]
    assert undeclared["step"] == -1
    assert undeclared["diff"]["fields"] == [
        "GameState.probe_field",
        "PlayerState.probe_seat",
    ]

    # One declaration a field covers every seat and the end-of-game schema check.
    left_out = _rules(
        tmp_path,
        "left_out",
        'FIELDS = frozenset({"GameState.probe_field", "PlayerState.probe_seat"})\n'
        'RULES = (Rule("left_out", why="test", state_fields=FIELDS),)\n',
    )
    declared = eq.check_game((str(recording), left_out))
    assert declared["status"] == "same"
    assert declared["hits"]["left_out:fields"] > 2


def test_the_mask_compares_only_the_kept_fields(eq: ModuleType) -> None:
    mask = eq._Mask(("a", "b", "c"), frozenset({"b"}))
    old = b"AAAABBBBCCCC"
    assert mask(old) == mask(b"AAAAXXXXCCCC")
    assert mask(old) != mask(b"AAAAXXXXCCCD")
    assert mask.left_out_differing(old, b"AAAAXXXXCCCC") == {"b"}
    assert mask.differing(old, b"AAAAXXXXCCCD") == ["c"]


def test_a_rule_that_never_applied_is_listed(
    eq: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    idle = _rules(
        tmp_path,
        "idle",
        'RULES = (Rule("idle", why="test", old=lambda step: False),)\n',
    )
    result = eq.check_game((str(_record(eq, tmp_path)), idle))
    eq._summary([result], eq.load_rules(idle))
    assert "declared but never applied: ['idle']" in capsys.readouterr().out


def test_compare_finds_the_first_different_move(eq: ModuleType, tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    a, b = _record(eq, first), _record(eq, second)
    assert eq.compare_game((a, b))["status"] == "same"
    raw = pickle.loads(zlib.decompress(b.read_bytes()))
    raw["columns"]["step"][7] = ("a", "probe", 0, ())
    b.write_bytes(zlib.compress(pickle.dumps(raw)))
    assert eq.compare_game((a, b)) | {"moves": None, "ends": None} == {
        "name": "game",
        "status": "different",
        "step": 7,
        "moves": None,
        "ends": None,
    }


def test_a_format_one_recording_is_refused(eq: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "old.pkl").write_bytes(pickle.dumps({"rows": []}))
    with pytest.raises(SystemExit, match="record again"):
        eq.recordings(tmp_path)


def test_a_flag_turned_into_a_number_is_a_difference(eq: ModuleType) -> None:
    # Content is compared as canonical text: Python's True == 1 must not hide it.
    old = eq.Step(0, ("a", "x", 0, ()), [0, [{"flag": True}]], None, [], "[]")
    new = eq.Step(0, ("a", "x", 0, ()), [0, [{"flag": 1}]], None, [], "[]")
    assert "legal" in eq._before_diff(old, new)


def test_text_comparison_catches_a_flag_turned_into_a_number_everywhere(
    eq: ModuleType,
) -> None:
    step = ("a", "x", 0, ())
    old = eq.Step(0, step, [0, []], [True], [{"flag": True}], '[{"flag":true}]')
    new = eq.Step(0, step, [0, []], [1], [{"flag": 1}], '[{"flag":1}]')
    assert set(eq._step_diff(old, new)) == {"views", "page", "events"}


@pytest.mark.parametrize(
    ("change", "kind", "shown"),
    [
        ("state", "state", "players[0].deck"),
        ("view", "views", "seat0.imperium_deck_size"),
        ("page", "page", "unavailable_choices"),
        ("initial", "state", "players[0].deck"),
    ],
)
def test_an_undeclared_change_is_reported_with_what_differs(
    eq: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    kind: str,
    shown: str,
) -> None:
    recording = _record(eq, tmp_path)

    class _Changed(UprisingRulesEngine):
        def reset(self, config: Any, seed: int) -> Any:
            state = super().reset(config, seed)
            return _reversed_deck(state) if change == "initial" else state

        def apply(
            self, state: Any, action: Any, legal_actions: Any = None
        ) -> Transition:
            moved = super().apply(state, action, legal_actions=legal_actions)
            if change == "state" and moved.state.revision == 40:
                return replace(moved, state=_reversed_deck(moved.state))
            return moved

        def observe(self, state: Any, player: int) -> Any:
            view = super().observe(state, player)
            if change == "view" and state.revision == 40:
                return replace(view, imperium_deck_size=view.imperium_deck_size + 1)
            return view

    def grey(state: Any, seat: int, legal: Any) -> Any:
        choices = original(state, seat, legal)
        return None if choices is None else {**choices, "probe": True}

    original = unavailable.unavailable_choices
    if change == "page":
        monkeypatch.setattr(unavailable, "unavailable_choices", grey)
    monkeypatch.setattr(eq, "UprisingRulesEngine", _Changed)
    result = eq.check_game((str(recording), None))
    assert result["status"] == "different"
    assert result["kinds"] == [kind]
    assert shown in str(result["diff"][kind])
    if change == "initial":
        assert result["step"] == -1


def test_a_nested_field_the_candidate_adds_is_reported_until_declared(
    eq: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = _record(eq, tmp_path)

    @dataclass(frozen=True, slots=True)
    class _Config(RulesetConfig):
        probe_extra: int = 0

    _Config.__qualname__ = "RulesetConfig"
    monkeypatch.setattr(eq, "RulesetConfig", _Config)
    undeclared = eq.check_game((str(recording), None))
    assert undeclared["kinds"] == ["fields"]
    assert undeclared["diff"]["fields"] == ["RulesetConfig.probe_extra"]

    added = _rules(
        tmp_path,
        "added",
        'FIELDS = frozenset({"RulesetConfig.probe_extra"})\n'
        'RULES = (Rule("added", why="test", state_fields=FIELDS),)\n',
    )
    assert eq.check_game((str(recording), added))["status"] == "same"


@pytest.mark.parametrize(
    ("option", "kind"), [("announce", "events"), ("reorder", "state")]
)
def test_a_vanished_step_still_compares_its_events_and_the_state(
    eq: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    option: str,
    kind: str,
) -> None:
    monkeypatch.setattr(_Confirming, option, True)
    with monkeypatch.context() as patch:
        patch.setattr(eq, "UprisingRulesEngine", _Confirming)
        recording = _record(eq, tmp_path)
    vanish = _rules(
        tmp_path,
        "vanish",
        f"""
def _old(step):
    if step.step[0] == "a" and step.step[1] == "{CONFIRM}":
        step.vanish = True


RULES = (Rule("vanish", why="test", old=_old),)
""",
    )
    result = eq.check_game((str(recording), vanish))
    assert result["status"] == "different"
    assert result["kinds"] == [kind]
    assert result["step_value"].startswith(f"('a', '{CONFIRM}'")


def test_moves_replace_or_drop_the_recorded_move(
    eq: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    recording = _record(eq, plain)
    both = _rules(
        tmp_path,
        "both",
        f"""
def _moves(old, at):
    if old.step[0] == "a" and old.step[1] == "finish_agent_turn":
        recorded = DomainAction(old.step[1], old.step[2], old.step[3])
        return (recorded, DomainAction("{CONFIRM}", 0))
    return None


RULES = (Rule("both", why="test", moves=_moves),)
""",
    )
    with monkeypatch.context() as patch:
        patch.setattr(eq, "UprisingRulesEngine", _Confirming)
        result = eq.check_game((str(recording), both))
        assert result["status"] == "same"
        assert result["hits"]["both:moves"] > 0

        confirmed = tmp_path / "confirmed"
        confirmed.mkdir()
        with_confirm = _record(eq, confirmed)
    none = _rules(
        tmp_path,
        "none",
        f"""
def _moves(old, at):
    if old.step[0] == "a" and old.step[1] == "{CONFIRM}":
        return []
    return None


RULES = (Rule("none", why="test", moves=_moves),)
""",
    )
    result = eq.check_game((str(with_confirm), none))
    assert result["status"] == "same"
    assert result["hits"]["none:moves"] > 0


def test_an_old_hook_may_rename_the_replayed_move(
    eq: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = _record(eq, tmp_path)

    class _Renamed(UprisingRulesEngine):
        def legal_actions(self, state: Any, player: int) -> Any:
            return tuple(
                replace(action, action_id="probe_finish")
                if action.action_id == "finish_agent_turn"
                else action
                for action in super().legal_actions(state, player)
            )

        def apply(
            self, state: Any, action: Any, legal_actions: Any = None
        ) -> Transition:
            if getattr(action, "action_id", None) == "probe_finish":
                action = replace(action, action_id="finish_agent_turn")
                legal = super().legal_actions(state, action.actor)
                return super().apply(state, action, legal_actions=legal)
            return super().apply(state, action)

    monkeypatch.setattr(eq, "UprisingRulesEngine", _Renamed)
    rename = _rules(
        tmp_path,
        "rename",
        """
def _old(step):
    if step.step[0] == "a" and step.step[1] == "finish_agent_turn":
        step.step = ("a", "probe_finish", *step.step[2:])
    if step.step[0] == "a":
        for row in step.decision[1]:
            if row["action_id"] == "finish_agent_turn":
                row["action_id"] = "probe_finish"


RULES = (Rule("rename", why="test", old=_old),)
""",
    )
    result = eq.check_game((str(recording), rename))
    assert result["status"] == "same", result.get("diff") or result.get("trace")
    assert result["hits"]["rename:old"] > 0


def test_the_answer_cap_stops_a_rule_that_keeps_answering(
    eq: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = _record(eq, tmp_path)
    monkeypatch.setattr(_Confirming, "reopen", True)
    monkeypatch.setattr(eq, "UprisingRulesEngine", _Confirming)
    confirm = _rules(
        tmp_path,
        "confirm",
        f"""
def _answer(at):
    return at.legal[0] if at.legal and at.legal[0].action_id == "{CONFIRM}" else None


RULES = (Rule("confirm", why="test", answer=_answer),)
""",
    )
    result = eq.check_game((str(recording), confirm))
    assert result["status"] == "raised"
    assert f"more than {eq.MAX_ANSWERED} answered decisions" in result["trace"]


def test_a_hook_that_edits_a_step_is_counted_whatever_it_returns(
    eq: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recording = _record(eq, tmp_path)
    monkeypatch.setattr(eq, "UprisingRulesEngine", _ExtraRow)
    quiet = _rules(
        tmp_path,
        "quiet",
        """
def _new(old, candidate):
    if old.step[0] == "a":
        candidate.decision = old.decision
        candidate.page = old.page
    return False


RULES = (Rule("quiet", why="test", new=_new),)
""",
    )
    result = eq.check_game((str(recording), quiet))
    assert result["status"] == "same"
    assert result["hits"]["quiet:new"] > 0


def test_the_recording_s_end_is_compared(eq: ModuleType, tmp_path: Path) -> None:
    recording = _record(eq, tmp_path)
    raw = pickle.loads(zlib.decompress(recording.read_bytes()))
    raw["end"] = "finished"
    recording.write_bytes(zlib.compress(pickle.dumps(raw)))
    result = eq.check_game((str(recording), None))
    assert result["kinds"] == ["end"]


def test_an_archived_engine_is_not_named_after_the_checkout_holding_it(
    eq: ModuleType, tmp_path: Path
) -> None:
    checkout = Path(dune_imperium.__file__).resolve().parent
    inside = checkout.parents[1] / "scripts" / "ab"
    assert eq._engine_commit(inside).startswith("(not a checkout")
    assert eq._engine_commit(tmp_path).startswith("(not a checkout")
    assert len(eq._engine_commit(checkout)) == 40
