"""Check that two engines play the same games step by step.

The composed-effects switch (docs/composed-effects-plan.md, stage A) changes
how card effects are written inside the engine but must change nothing a
player, an agent or a save can see. This tool records seeded games on one
engine and replays them on another, comparing at every step:

- ``chance``: the chance decision (id, options, count, replacement);
- ``legal``: the decision owner and their legal actions, in order;
- ``views``: every seat's ``PlayerView`` before the step (what the page and
  the observation encoding read);
- ``events``: the step's events with their payloads and visibility;
- ``state``: the state after the step, without the decision stack, event log
  and revision (the record corpus fingerprint, ``records.portable.trace``);
- ``page``: what the play server sends with the owner's decision beside the
  legal list -- the greyed-out rows and their reasons
  (``display.unavailable``), the Agent-box and Reveal-choice groups and
  which row belongs to which (``display.actions``), the Scouts lines -- and
  each pending Reveal choice's own rows (``reveal_turn.pending_choice_entries``,
  which the app AI reads). Added after stage A4d, whose first version
  repeated a row inside one pending choice while the legal list stayed the
  same.

The decision stack is the engine's control flow and is left out on purpose:
a stage may store its pending effects differently, as long as nothing above
changes. (Saves hash the whole state, so a stage that changes the decision
stack's form also raises ``ACTION_CODEC_VERSION`` to refuse older saves.)

**Declared differences** (the cleanup stage, plan 5 "정리 단계"): a stage
that changes some of the above on purpose passes ``--differences <module>``,
whose ``RULES`` rewrite the base's recording into the candidate's form, drop
what only the candidate has, skip a step the candidate no longer has, answer
a window the base did not open, or name state fields left out
(``equivalence_rules``). Every other difference is still reported, and so is
every declared rule that never applied.

**Recording format 2** (since the declared differences): a game's file keeps
each step's content itself -- the legal list or chance decision, the page,
the events and the four views, canonical and zlib-compressed (about 0.7 MB a
game) -- plus the state's per-field digests and their field names. The
differences are applied when checking, so changing them needs no new
recording, and a difference is reported with what changed: the rows or
events only one engine has, the page part, the view keys, the state fields.
Format-1 recordings (digests only, ``*.pkl``) are refused: record again.

Record on the base engine, then check on the candidate::

    git archive <base> src | tar -x -C tmp/claude/<session>/engines/<base8>
    PYTHONPATH=tmp/claude/<session>/engines/<base8>/src .venv/bin/python \\
        scripts/ab/engine_equivalence.py record tmp/claude/<session>/equiv/<base8>
    uv run python scripts/ab/engine_equivalence.py check \\
        tmp/claude/<session>/equiv/<base8> [--differences <rules.py>]

``record`` plays every game of the plan (``--plan standard``: 200 games;
``quick``: 20) with the plan's agents. ``check`` replays the recorded steps
(no agents) and reports, per game, the first different step, the kinds of
difference and what differs. Both print a coverage line: how many steps
exercised each action id, so a stage can see that its effects were reached.
``compare <a> <b>`` says whether two recordings of the plan made the same
moves (agents re-recorded on the candidate: ``check`` replays without them).
Only the standard library and ``dune_imperium`` names present in both
engines are used.
"""

import argparse
import importlib.util
import json
import os
import pickle
import re
import subprocess
import sys
import traceback
import zlib
from collections import Counter
from collections.abc import Iterator, Sequence
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from equivalence_rules import At, Rule, Step

from dune_imperium.agents import StateAgent
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase
from dune_imperium.records.portable.trace import (
    DIGEST_SIZE,
    Fingerprint,
    canonical,
    field_names,
)
from dune_imperium.rules import UprisingRulesEngine

FULL = {
    "choam_module": True,
    "leader_draft": True,
    "promo_cards": True,
    "bloodlines": True,
    "tech_module": True,
    "immortality": True,
    "go_to_11": True,
    "epic_game": True,
    "arrakeen_scouts": True,
}
IMMORTALITY = {"choam_module": True, "bloodlines": True, "immortality": True}
CHOAM = {"choam_module": True, "promo_cards": True}
MIX = ("app_ai", "app_ai_medium", "heuristic", "random")

# (name prefix, ruleset options, first seed, seat agents, games) per plan.
PLANS: dict[str, tuple[tuple[str, dict[str, bool], int, tuple[str, ...], int], ...]] = {
    "standard": (
        ("random-full", FULL, 8_100_000, ("random",) * 4, 60),
        ("random-immortality", IMMORTALITY, 8_110_000, ("random",) * 4, 30),
        ("random-choam", CHOAM, 8_120_000, ("random",) * 4, 20),
        ("random-base", {}, 8_130_000, ("random",) * 4, 10),
        ("heuristic-full", FULL, 8_140_000, ("heuristic",) * 4, 40),
        ("mix-full", FULL, 8_150_000, MIX, 40),
    ),
    "quick": (
        ("random-full", FULL, 8_100_000, ("random",) * 4, 8),
        ("random-base", {}, 8_130_000, ("random",) * 4, 2),
        ("heuristic-full", FULL, 8_140_000, ("heuristic",) * 4, 5),
        ("mix-full", FULL, 8_150_000, MIX, 5),
    ),
}
MAX_STEPS = 30_000
# Answered candidate decisions in a row before the check gives up (a rule
# answering a decision that its own move opens again).
MAX_ANSWERED = 50
KINDS = ("fields", "chance", "legal", "views", "events", "state", "page", "end")
FORMAT = 2
SUFFIX = ".equiv"
# A recorded step's parts, stored column by column (they compress better).
COLUMNS = ("step", "decision", "page", "events", "views", "state")
# The page metadata parts, in their order in a step's ``page``.
PAGE_PARTS = (
    "pending_choice_entries",
    "unavailable_choices",
    "agent_box_headers",
    "agent_box_of_rows",
    "reveal_choice_headers",
    "reveal_choice_of_rows",
    "scouts_choice_lines",
)
# Items listed per side when a difference is reported.
SHOWN = 8
_SEAT_FIELD = re.compile(r"^players\[\d+\]\.(.+)$")

type Spec = tuple[str, dict[str, bool], int, tuple[str, ...]]


def specs(plan: str) -> Iterator[Spec]:
    for prefix, options, first_seed, agents, games in PLANS[plan]:
        for offset in range(games):
            yield (f"{prefix}-{offset:03d}", options, first_seed + offset, agents)


def _text(value: Any) -> str:
    """Canonical JSON: content is compared as this text, as the digests of
    format 1 were (Python's ``True == 1`` would hide a payload change)."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _page(state: Any, owner: int, legal: tuple[DomainAction, ...]) -> list[Any]:
    """The decision's page metadata and pending Reveal choice rows (see
    the module doc); a function that raises contributes its error's type."""

    from dune_imperium.display.actions import (
        agent_box_headers,
        agent_box_of_rows,
        reveal_choice_headers,
        reveal_choice_of_rows,
    )
    from dune_imperium.display.scouts import scouts_choice_lines
    from dune_imperium.display.unavailable import unavailable_choices
    from dune_imperium.rules.reveal_turn import pending_choice_entries

    parts: list[Any] = []
    for read in (
        lambda: pending_choice_entries(state, owner),
        lambda: unavailable_choices(state, owner, legal),
        lambda: agent_box_headers(state, owner),
        lambda: agent_box_of_rows(state, owner, legal),
        lambda: reveal_choice_headers(state, owner),
        lambda: reveal_choice_of_rows(state, owner, legal),
        lambda: scouts_choice_lines(state, owner, legal),
    ):
        try:
            parts.append(canonical(read()))
        except Exception as error:  # noqa: BLE001 - part of the content
            parts.append(["raised", type(error).__name__])
    return parts


def _decision(decision: Any, legal: tuple[DomainAction, ...]) -> Any:
    """A decision's compared content: the owner and legal list, or the
    chance decision's id, options, count and replacement."""

    if isinstance(decision, ChanceDecision):
        return canonical(
            (
                decision.decision_id,
                decision.options,
                decision.count,
                decision.with_replacement,
            )
        )
    if isinstance(decision, PlayerDecision):
        return canonical((decision.owner, legal))
    return None


class _Stepper:
    """Plays one game on the importable engine."""

    def __init__(
        self,
        options: dict[str, bool],
        seed: int,
        fields: tuple[str, ...] | None = None,
        schema: dict[str, list[str]] | None = None,
    ) -> None:
        self.config = RulesetConfig(**options)
        self.engine = UprisingRulesEngine()
        self.state = self.engine.reset(self.config, seed)
        self.fingerprint = Fingerprint(names=fields, schema=schema)

    def views(self, offset: int = 0) -> str:
        """Every seat's view, with the revision moved back by ``offset``
        (the moves this engine made more than the recording's)."""

        views = [
            canonical(self.engine.observe(self.state, seat))
            for seat in range(self.config.players)
        ]
        if offset:
            for view in views:
                view["revision"] -= offset
        return _text(views)

    def state_digest(self) -> bytes:
        return b"".join(self.fingerprint(self.state))


def record_game(args: tuple[str, Spec]) -> tuple[str, str]:
    out_dir, (name, options, seed, kinds) = args
    path = Path(out_dir) / f"{name}{SUFFIX}"
    if path.exists():
        return name, "cached"
    stepper = _Stepper(options, seed)
    config = stepper.config
    agents = [
        make_agent(kind, seed * 10 + seat, config) for seat, kind in enumerate(kinds)
    ]
    chance = ChanceResolver(seed=seed)
    rows: list[tuple[Any, ...]] = []
    end = "max_steps"
    initial = stepper.state_digest()
    try:
        for _ in range(MAX_STEPS):
            state = stepper.state
            if state.phase is GamePhase.FINISHED:
                end = "finished"
                break
            decision = stepper.engine.current_decision(state)
            views = stepper.views()
            if isinstance(decision, ChanceDecision):
                outcome = chance.resolve(decision)
                result = stepper.engine.apply(state, outcome)
                step: tuple[Any, ...] = ("c", outcome.decision_id, outcome.values)
                content = _decision(decision, ())
                page = None
            elif isinstance(decision, PlayerDecision):
                legal = stepper.engine.legal_actions(state, decision.owner)
                if not legal:
                    end = "no_legal_actions"
                    break
                agent = agents[decision.owner]
                view = stepper.engine.observe(state, decision.owner)
                action = (
                    agent.choose_action_with_state(state, view, legal)
                    if isinstance(agent, StateAgent)
                    else agent.choose_action(view, legal)
                )
                page = _page(state, decision.owner, legal)
                result = stepper.engine.apply(state, action, legal_actions=legal)
                step = ("a", action.action_id, action.actor, action.arguments)
                content = _decision(decision, legal)
            else:
                end = "no_decision"
                break
            stepper.state = result.state
            rows.append(
                (
                    step,
                    content,
                    page,
                    canonical(result.events),
                    views,
                    stepper.state_digest(),
                )
            )
    except Exception:  # noqa: BLE001 - the error is part of the record
        end = "error: " + traceback.format_exc()[-1500:]
    data = {
        "format": FORMAT,
        "spec": (name, options, seed, kinds),
        "fields": stepper.fingerprint.names,
        "schema": stepper.fingerprint.class_schema,
        "initial": initial,
        "columns": {
            column: [row[index] for row in rows] for index, column in enumerate(COLUMNS)
        },
        "end": end,
        "engine": _engine_commit(),
    }
    path.write_bytes(zlib.compress(pickle.dumps(data, protocol=5), 6))
    return name, f"{end[:70]} steps={len(rows)}"


def load(path: Path | str) -> dict[str, Any]:
    """One recorded game (format 2)."""

    data: dict[str, Any] = pickle.loads(zlib.decompress(Path(path).read_bytes()))  # noqa: S301 - our own files
    if data.get("format") != FORMAT:
        raise ValueError(f"{path}: recording format {data.get('format')}, not {FORMAT}")
    columns = data.pop("columns")
    data["rows"] = list(zip(*(columns[column] for column in COLUMNS), strict=True))
    return data


def recordings(trace_dir: Path | str) -> list[Path]:
    """The recorded games under ``trace_dir``, by name."""

    paths = sorted(Path(trace_dir).glob(f"*{SUFFIX}"))
    if not paths and any(Path(trace_dir).glob("*.pkl")):
        sys.exit(f"{trace_dir} holds format-1 recordings (*.pkl): record again")
    if not paths:
        sys.exit(f"no recorded games in {trace_dir}")
    return paths


_RULES: dict[str | None, tuple[Rule, ...]] = {None: ()}


def load_rules(path: str | None) -> tuple[Rule, ...]:
    """The ``RULES`` of a declared-differences module, loaded once per
    process."""

    if path not in _RULES:
        spec = importlib.util.spec_from_file_location("declared_differences", path)
        if spec is None or spec.loader is None:
            raise ValueError(f"cannot load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rules = tuple(module.RULES)
        names = [rule.name for rule in rules]
        if len(set(names)) != len(names):
            raise ValueError(f"{path}: rule names repeat")
        _RULES[path] = rules
    return _RULES[path]


# --- what differs ------------------------------------------------------------------


def _items(old: list[Any], new: list[Any]) -> dict[str, Any]:
    """The items only one side has (as text), or where their order parts."""

    old_text = [_text(item) for item in old]
    new_text = [_text(item) for item in new]
    only_old = list((Counter(old_text) - Counter(new_text)).elements())
    only_new = list((Counter(new_text) - Counter(old_text)).elements())
    out: dict[str, Any] = {}
    if only_old:
        out["old_only"] = [item[:300] for item in only_old[:SHOWN]]
    if only_new:
        out["new_only"] = [item[:300] for item in only_new[:SHOWN]]
    if not out:
        out["order_from"] = next(
            (
                index
                for index, pair in enumerate(zip(old_text, new_text, strict=False))
                if pair[0] != pair[1]
            ),
            None,
        )
    return out


def _both(old: Any, new: Any) -> dict[str, Any]:
    return {"old": _text(old)[:300], "new": _text(new)[:300]}


def _legal_diff(old: Any, new: Any) -> dict[str, Any]:
    if (
        isinstance(old, list)
        and isinstance(new, list)
        and len(old) == len(new) == 2
        and isinstance(old[1], list)
        and isinstance(new[1], list)
    ):
        out = {} if old[0] == new[0] else {"owner": [old[0], new[0]]}
        if old[1] != new[1]:
            out |= _items(old[1], new[1])
        return out
    return _both(old, new)


def _page_diff(old: Any, new: Any) -> dict[str, Any]:
    if not (
        isinstance(old, list)
        and isinstance(new, list)
        and len(old) == len(new) == len(PAGE_PARTS)
    ):
        return _both(old, new)
    out: dict[str, Any] = {}
    for name, part_old, part_new in zip(PAGE_PARTS, old, new, strict=True):
        if part_old != part_new:
            if isinstance(part_old, list) and isinstance(part_new, list):
                out[name] = _items(part_old, part_new)
            else:
                out[name] = _both(part_old, part_new)
    return out


def _view_keys(old: list[Any], new: list[Any]) -> list[str]:
    """The view keys that differ, as ``seat<s>.<key>`` (one level deeper in
    ``players`` and ``private``)."""

    keys: list[str] = []
    for seat, (view_old, view_new) in enumerate(zip(old, new, strict=False)):
        for key in sorted(set(view_old) | set(view_new)):
            value_old, value_new = view_old.get(key), view_new.get(key)
            if value_old == value_new:
                continue
            if (
                key == "players"
                and isinstance(value_old, list)
                and isinstance(value_new, list)
            ):
                for index, (one_old, one_new) in enumerate(
                    zip(value_old, value_new, strict=False)
                ):
                    keys += [
                        f"seat{seat}.players[{index}].{sub}"
                        for sub in sorted(set(one_old) | set(one_new))
                        if one_old.get(sub) != one_new.get(sub)
                    ]
            elif (
                key == "private"
                and isinstance(value_old, dict)
                and isinstance(value_new, dict)
            ):
                keys += [
                    f"seat{seat}.private.{sub}"
                    for sub in sorted(set(value_old) | set(value_new))
                    if value_old.get(sub) != value_new.get(sub)
                ]
            else:
                keys.append(f"seat{seat}.{key}")
    if len(old) != len(new):
        keys.append("seats")
    return keys[: SHOWN * 2]


def _state_fields(fields: tuple[str, ...], old: bytes, new: bytes) -> list[str]:
    return [
        name
        for index, name in enumerate(fields)
        if old[index * DIGEST_SIZE : (index + 1) * DIGEST_SIZE]
        != new[index * DIGEST_SIZE : (index + 1) * DIGEST_SIZE]
    ][: SHOWN * 2]


class _Mask:
    """The state digests with the declared fields left out."""

    def __init__(self, fields: tuple[str, ...], left_out: frozenset[str]) -> None:
        self.fields = fields
        self.kept = [index for index, name in enumerate(fields) if name not in left_out]
        self.all = len(self.kept) == len(fields)
        self.left_out = frozenset(fields) & left_out

    def __call__(self, digests: bytes) -> bytes:
        if self.all:
            return digests
        return b"".join(
            digests[index * DIGEST_SIZE : (index + 1) * DIGEST_SIZE]
            for index in self.kept
        )

    def without(self, names: set[str]) -> _Mask:
        """This mask with ``names`` left out as well (one step's)."""

        return _Mask(self.fields, self.left_out | frozenset(names))

    def differing(self, old: bytes, new: bytes) -> list[str]:
        kept = {self.fields[index] for index in self.kept}
        return [name for name in _state_fields(self.fields, old, new) if name in kept]

    def left_out_differing(self, old: bytes, new: bytes) -> set[str]:
        """The left-out fields whose digests differ (to count their rules)."""

        if self.all or old == new:
            return set()
        return {
            name
            for index, name in enumerate(self.fields)
            if name in self.left_out
            and old[index * DIGEST_SIZE : (index + 1) * DIGEST_SIZE]
            != new[index * DIGEST_SIZE : (index + 1) * DIGEST_SIZE]
        }


# --- checking ------------------------------------------------------------------------


def _recorded_move(step: tuple[Any, ...]) -> DomainAction | ChanceOutcome:
    if step[0] == "c":
        return ChanceOutcome(decision_id=step[1], values=step[2])
    return DomainAction(action_id=step[1], actor=step[2], arguments=step[3])


def _snapshot(*steps: Step) -> tuple[Any, ...]:
    """What a hook may change in steps, to count the hooks that did (a hook's
    own answer is not trusted: an edit it did not report would hide a
    difference uncounted)."""

    return tuple(
        (
            _text([step.step, step.decision, step.page, step.events]),
            step.vanish,
            step.state_unchecked,
            tuple(sorted(step.fields_unchecked)),
            step.views_now(),
        )
        for step in steps
    )


def _class_field(name: str) -> str:
    """A fingerprint field's declared form: ``GameState.<field>`` or
    ``PlayerState.<field>`` (every seat's)."""

    match = _SEAT_FIELD.match(name)
    return f"PlayerState.{match.group(1)}" if match else f"GameState.{name}"


def _fields_hit(hits: Counter[str], rules: tuple[Rule, ...], names: set[str]) -> None:
    for rule in rules:
        if rule.state_fields & names:
            hits[f"{rule.name}:fields"] += 1


def _at(stepper: _Stepper, old: Step, rows: Sequence[Any] = ()) -> At:
    state = stepper.state
    decision = stepper.engine.current_decision(state)
    legal = (
        stepper.engine.legal_actions(state, decision.owner)
        if isinstance(decision, PlayerDecision)
        else ()
    )
    return At(stepper.engine, state, decision, legal, old, rows, old.index)


def _before_diff(old: Step, candidate: Step) -> dict[str, Any]:
    """What differs before the step: the views, the decision, the page."""

    diff: dict[str, Any] = {}
    if old.views_now() != candidate.views_now():
        diff["views"] = _view_keys(old.views, candidate.views)
    if _text(old.decision) != _text(candidate.decision):
        kind = "chance" if old.step[0] == "c" else "legal"
        diff[kind] = _legal_diff(old.decision, candidate.decision)
    if _text(old.page) != _text(candidate.page):
        diff["page"] = _page_diff(old.page, candidate.page)
    return diff


def _step_diff(old: Step, candidate: Step) -> dict[str, Any]:
    """What differs in a step but the state: a vanished step has only its
    events compared (the base's, translated, against none)."""

    diff = {} if old.vanish else _before_diff(old, candidate)
    if _text(old.events) != _text(candidate.events):
        diff["events"] = _items(old.events, candidate.events)
    return diff


def _salvage(rules: tuple[Rule, ...], old: Step, candidate: Step) -> dict[str, Any]:
    """The before-step difference when the step itself raised (the ``new``
    hooks run again, uncounted)."""

    if old.vanish or not candidate.views_text:
        return {}
    try:
        for rule in rules:
            if rule.new is not None:
                rule.new(old, candidate)
        return _before_diff(old, candidate)
    except Exception:  # noqa: BLE001 - the raise is reported instead
        return {}


class _Game:
    """One game's check: the candidate stepper, the declared rules and what
    they did."""

    def __init__(self, data: dict[str, Any], rules: tuple[Rule, ...]) -> None:
        _name, options, seed, _kinds = data["spec"]
        self.data = data
        self.rules = rules
        self.fields: tuple[str, ...] = tuple(data["fields"])
        self.declared = frozenset().union(*(rule.state_fields for rule in rules))
        self.stepper = _Stepper(options, seed, self.fields, data["schema"])
        self.mask = _Mask(
            self.fields,
            frozenset(n for n in self.fields if _class_field(n) in self.declared),
        )
        self.answering = any(rule.answer is not None for rule in rules)
        self.hits: Counter[str] = Counter()
        self.answered: Counter[str] = Counter()
        self.actions: Counter[str] = Counter()
        self.offset = 0

    def _hook(self, rule: Rule, hook: str, function: Any, *steps: Step) -> None:
        """Call ``function(*steps)`` and count it when it changed them."""

        before = _snapshot(*steps)
        function(*steps)
        if _snapshot(*steps) != before:
            self.hits[f"{rule.name}:{hook}"] += 1

    def fields_hit(self, names: set[str]) -> None:
        _fields_hit(self.hits, self.rules, {_class_field(n) for n in names})

    def translate(self, old: Step) -> None:
        for rule in self.rules:
            if rule.old is not None:
                self._hook(rule, "old", rule.old, old)

    def moves(self, old: Step, at: At) -> tuple[Any, ...] | None:
        if old.vanish:
            return ()
        for rule in self.rules:
            if rule.moves is not None:
                moves = rule.moves(old, at)
                if moves is not None:
                    self.hits[f"{rule.name}:moves"] += 1
                    return tuple(moves)
        return None

    def answer(self, at: At) -> Any:
        for rule in self.rules:
            if rule.answer is not None:
                move = rule.answer(at)
                if move is not None:
                    self.hits[f"{rule.name}:answer"] += 1
                    window = (
                        ",".join(sorted({action.action_id for action in at.legal}))
                        if at.legal
                        else type(at.decision).__name__
                    )
                    self.answered[f"{rule.name}: {window}"] += 1
                    return move
        return None

    def normalise(self, old: Step, candidate: Step) -> None:
        for rule in self.rules:
            if rule.new is not None:
                self._hook(rule, "new", rule.new, old, candidate)

    def play(self, old: Step, candidate: Step) -> None:
        """Play the recorded step on the candidate (the candidate's moves,
        then the decisions the rules answer), filling in its content."""

        stepper = self.stepper
        at = _at(stepper, old, self.data["rows"])
        moves = self.moves(old, at)
        if moves == ():
            old.vanish = True
            self.offset -= 1
            return
        candidate.views_text = stepper.views(self.offset)
        candidate.decision = _decision(at.decision, at.legal)
        if isinstance(at.decision, PlayerDecision):
            candidate.page = _page(at.state, at.decision.owner, at.legal)
        # An ``old`` hook may have rewritten the recorded move.
        planned = moves or (_recorded_move(old.step),)
        produced: list[Any] = []
        try:
            for move in planned:
                result = stepper.engine.apply(stepper.state, move)
                stepper.state = result.state
                produced.extend(result.events)
            self.offset += len(planned) - 1
            answered = 0
            while self.answering and stepper.state.phase is not GamePhase.FINISHED:
                move = self.answer(_at(stepper, old, self.data["rows"]))
                if move is None:
                    break
                answered += 1
                if answered > MAX_ANSWERED:
                    raise RuntimeError(
                        f"more than {MAX_ANSWERED} answered decisions in a row"
                    )
                result = stepper.engine.apply(stepper.state, move)
                stepper.state = result.state
                produced.extend(result.events)
                self.offset += 1
        finally:
            candidate.events = canonical(produced)

    def end_diff(self) -> dict[str, Any]:
        """The recording's end against the candidate's, after the last step."""

        end = self.data["end"]
        state = self.stepper.state
        if end == "finished" and state.phase is not GamePhase.FINISHED:
            return {"end": [end, str(state.phase)]}
        if end == "no_legal_actions" and _at(self.stepper, Step(-1, ())).legal:
            return {"end": [end, "legal actions"]}
        return {}

    def nested_fields(self) -> set[str]:
        """Nested fields the candidate adds or drops: its digests use the
        recording's class schema, so they would be left out silently."""

        schema = self.data["schema"]
        return {
            f"{qualname}.{name}"
            for qualname, names in self.stepper.fingerprint.class_schema.items()
            if qualname in schema
            for name in set(names) ^ set(schema[qualname])
        }


def check_game(args: tuple[str, str | None]) -> dict[str, Any]:
    path, rules_path = args
    data = load(path)
    game = _Game(data, load_rules(rules_path))
    report: dict[str, Any] = {
        "name": data["spec"][0],
        "steps": len(data["rows"]),
        "end": data["end"][:80],
    }

    def done(status: str, **more: Any) -> dict[str, Any]:
        if "diff" in more:
            more["kinds"] = [kind for kind in KINDS if kind in more["diff"]]
        return report | {
            "status": status,
            **more,
            "actions": dict(game.actions),
            "hits": dict(game.hits),
            "answered": dict(game.answered),
        }

    stepper, mask = game.stepper, game.mask
    changed = {
        _class_field(n) for n in set(field_names(stepper.state)) ^ set(game.fields)
    }
    _fields_hit(game.hits, game.rules, changed)
    if changed - game.declared:
        return done(
            "different", step=-1, diff={"fields": sorted(changed - game.declared)}
        )
    initial = stepper.state_digest()
    game.fields_hit(mask.left_out_differing(data["initial"], initial))
    if mask(initial) != mask(data["initial"]):
        return done(
            "different",
            step=-1,
            diff={"state": mask.differing(data["initial"], initial)},
        )
    for index, row in enumerate(data["rows"]):
        step, content, page, events, views, state_digest = row
        if step[0] == "a":
            game.actions[step[1]] += 1
        old = Step(index, step, content, page, events, views)
        candidate = Step(index, step)
        try:
            game.translate(old)
            game.play(old, candidate)
            game.normalise(old, candidate)
            now = stepper.state_digest()
        except Exception:  # noqa: BLE001 - reported
            trace = traceback.format_exc()[-1500:]
            # A recorded move the candidate's decision refuses: what differed
            # before it is the useful report.
            before = _salvage(game.rules, old, candidate)
            return done(
                "different" if before else "raised",
                step=index,
                step_value=repr(step)[:300],
                diff=before,
                trace=trace,
            )
        diff = _step_diff(old, candidate)
        game.fields_hit(mask.left_out_differing(state_digest, now))
        unchecked = old.state_unchecked or candidate.state_unchecked
        skipped = old.fields_unchecked | candidate.fields_unchecked
        step_mask = mask.without(skipped) if skipped else mask
        if not unchecked and step_mask(now) != step_mask(state_digest):
            diff["state"] = step_mask.differing(state_digest, now)
        if diff:
            return done("different", step=index, step_value=repr(step)[:300], diff=diff)
    last = len(data["rows"])
    end = game.end_diff()
    if end:
        return done("different", step=last, diff=end)
    nested = game.nested_fields()
    _fields_hit(game.hits, game.rules, nested)
    if nested - game.declared:
        return done(
            "different", step=last, diff={"fields": sorted(nested - game.declared)}
        )
    return done("same", base_error=data["end"].startswith("error"))


def compare_game(args: tuple[Path, Path]) -> dict[str, Any]:
    """Whether two recordings of one game made the same moves to the same
    end."""

    first, second = (load(path) for path in args)
    moves = [
        [_text(canonical(row[0])) for row in data["rows"]] for data in (first, second)
    ]
    ends = [data["end"].split(":", 1)[0] for data in (first, second)]
    report = {"name": first["spec"][0]}
    if moves[0] == moves[1] and ends[0] == ends[1]:
        return report | {"status": "same"}
    step = next(
        (
            index
            for index, pair in enumerate(zip(*moves, strict=False))
            if pair[0] != pair[1]
        ),
        min(map(len, moves)),
    )
    return report | {
        "status": "different",
        "step": step,
        "moves": [side[step][:200] if step < len(side) else None for side in moves],
        "ends": [first["end"][:80], second["end"][:80]],
    }


def _engine_commit(source: Path | None = None) -> str:
    """The commit of the importable engine's checkout, or a note when it is
    not one (a ``git archive``d base inside another checkout)."""

    if source is None:
        import dune_imperium

        source = Path(dune_imperium.__file__).resolve().parent
    try:
        top, head = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "--show-toplevel", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except OSError, subprocess.CalledProcessError, ValueError:
        return f"(not a checkout: {source})"
    if Path(top).resolve() / "src" / "dune_imperium" != source:
        return f"(not a checkout: {source})"
    return head


def _nice() -> None:
    if hasattr(os, "nice"):
        os.nice(10)


def _summary(results: list[dict[str, Any]], rules: tuple[Rule, ...]) -> None:
    statuses = Counter(r["status"] for r in results)
    steps = sum(r["steps"] for r in results if r["status"] == "same")
    coverage: Counter[str] = Counter()
    hits: Counter[str] = Counter()
    answered: Counter[str] = Counter()
    for r in results:
        coverage.update(r.get("actions", {}))
        hits.update(r.get("hits", {}))
        answered.update(r.get("answered", {}))
    print(f"checked on {_engine_commit()}: {dict(statuses)}; {steps} steps the same")
    print("action ids replayed:", len(coverage), dict(sorted(coverage.items())))
    errors = [r["name"] for r in results if r.get("base_error")]
    if errors:
        print(f"recordings that end in a base-engine error ({len(errors)}):", errors)
    if rules:
        print("declared differences applied:", dict(sorted(hits.items())))
        # Answered decisions are not compared themselves: list their windows.
        if answered:
            print("answered windows:", dict(sorted(answered.items())))
        unused = [
            rule.name
            for rule in rules
            if not any(key.startswith(f"{rule.name}:") for key in hits)
        ]
        if unused:
            print("declared but never applied:", unused)
    for r in results:
        if r["status"] != "same":
            shown = {k: v for k, v in r.items() if k not in ("actions", "hits")}
            print(json.dumps(shown)[:1500])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record", help="play the plan on the importable engine")
    record.add_argument("out_dir")
    record.add_argument("--plan", choices=sorted(PLANS), default="standard")
    record.add_argument("--workers", type=int, default=6)
    check = sub.add_parser(
        "check", help="replay recorded games on the importable engine"
    )
    check.add_argument("trace_dir")
    check.add_argument("--workers", type=int, default=6)
    check.add_argument("--report", help="write every game's result as JSON here")
    check.add_argument(
        "--differences", help="a module of declared differences (equivalence_rules)"
    )
    compare = sub.add_parser(
        "compare", help="whether two recordings of the plan made the same moves"
    )
    compare.add_argument("first")
    compare.add_argument("second")
    args = parser.parse_args()

    if args.command == "record":
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        todo = [(str(out), spec) for spec in specs(args.plan)]
        ends: Counter[str] = Counter()
        with Pool(args.workers, initializer=_nice) as pool:
            for name, status in pool.imap_unordered(record_game, todo):
                ends[status.split(" ")[0]] += 1
                print(name, status, flush=True)
        print("recorded on", _engine_commit(), dict(ends))
        return

    if args.command == "compare":
        pairs = [
            (path, Path(args.second) / path.name) for path in recordings(args.first)
        ]
        missing = [str(second) for _first, second in pairs if not second.exists()]
        if missing:
            sys.exit(f"missing in {args.second}: {missing[:5]}")
        compared = [compare_game(pair) for pair in pairs]
        for r in compared:
            if r["status"] != "same":
                print(json.dumps(r))
        statuses = Counter(r["status"] for r in compared)
        print(dict(statuses))
        sys.exit(0 if statuses.keys() == {"same"} else 1)

    paths = recordings(args.trace_dir)
    rules = load_rules(args.differences)
    with Pool(args.workers, initializer=_nice) as pool:
        results = list(
            pool.imap_unordered(check_game, [(str(p), args.differences) for p in paths])
        )
    results.sort(key=lambda r: r["name"])
    if args.report:
        Path(args.report).write_text(json.dumps(results, indent=1))
    _summary(results, rules)
    sys.exit(0 if {r["status"] for r in results} == {"same"} else 1)


if __name__ == "__main__":
    main()
