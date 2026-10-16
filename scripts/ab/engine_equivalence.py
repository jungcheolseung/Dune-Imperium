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
  same; a recording made before has no ``page`` and skips it.

The decision stack is the engine's control flow and is left out on purpose:
a stage may store its pending effects differently, as long as nothing above
changes. (Saves hash the whole state, so a stage that changes the decision
stack's form also raises ``ACTION_CODEC_VERSION`` to refuse older saves.)

Record on the base engine, then check on the candidate::

    git archive <base> src | tar -x -C tmp/claude/<session>/engines/<base8>
    PYTHONPATH=tmp/claude/<session>/engines/<base8>/src .venv/bin/python \\
        scripts/ab/engine_equivalence.py record tmp/claude/<session>/equiv/<base8>
    uv run python scripts/ab/engine_equivalence.py check \\
        tmp/claude/<session>/equiv/<base8>

``record`` plays every game of the plan (``--plan standard``: 200 games;
``quick``: 20) with the plan's agents and keeps the actions, chance outcomes
and digests in one pickle a game. ``check`` replays the recorded steps (no
agents) and reports, per game, the first step and the kinds of difference.
Both print a coverage line: how many steps exercised each action id, so a
stage can see that its effects were reached. Only the standard library and
``dune_imperium`` names present in both engines are used.
"""

import argparse
import hashlib
import json
import os
import pickle
import subprocess
import sys
import traceback
from collections import Counter
from collections.abc import Iterator
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from dune_imperium.agents import StateAgent
from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase
from dune_imperium.records.portable.trace import Fingerprint, canonical
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
KINDS = ("chance", "legal", "views", "events", "state", "page")

type Spec = tuple[str, dict[str, bool], int, tuple[str, ...]]


def specs(plan: str) -> Iterator[Spec]:
    for prefix, options, first_seed, agents, games in PLANS[plan]:
        for offset in range(games):
            yield (f"{prefix}-{offset:03d}", options, first_seed + offset, agents)


def _digest(value: Any) -> bytes:
    text = json.dumps(canonical(value), sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(text.encode(), digest_size=8).digest()


def _page_key(state: Any, owner: int, legal: tuple[DomainAction, ...]) -> bytes:
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
            parts.append(read())
        except Exception as error:  # noqa: BLE001 - part of the digest
            parts.append(("raised", type(error).__name__))
    return _digest(parts)


def _chance_key(decision: ChanceDecision) -> bytes:
    return _digest(
        (
            decision.decision_id,
            decision.options,
            decision.count,
            decision.with_replacement,
        )
    )


class _Stepper:
    """Digests one game's steps on the importable engine."""

    def __init__(self, options: dict[str, bool], seed: int) -> None:
        self.config = RulesetConfig(**options)
        self.engine = UprisingRulesEngine()
        self.state = self.engine.reset(self.config, seed)
        self.fingerprint = Fingerprint()

    def views(self) -> bytes:
        return _digest(
            [
                self.engine.observe(self.state, seat)
                for seat in range(self.config.players)
            ]
        )

    def state_digest(self) -> bytes:
        return b"".join(self.fingerprint(self.state))


def record_game(args: tuple[str, Spec]) -> tuple[str, str]:
    out_dir, (name, options, seed, kinds) = args
    path = Path(out_dir) / f"{name}.pkl"
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
                legal_key = _chance_key(decision)
                page_key = b""
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
                page_key = _page_key(state, decision.owner, legal)
                result = stepper.engine.apply(state, action, legal_actions=legal)
                step = ("a", action.action_id, action.actor, action.arguments)
                legal_key = _digest((decision.owner, legal))
            else:
                end = "no_decision"
                break
            stepper.state = result.state
            rows.append(
                (
                    step,
                    legal_key,
                    views,
                    _digest(result.events),
                    stepper.state_digest(),
                    page_key,
                )
            )
    except Exception:  # noqa: BLE001 - the error is part of the record
        end = "error: " + traceback.format_exc()[-1500:]
    with path.open("wb") as handle:
        pickle.dump(
            {
                "spec": (name, options, seed, kinds),
                "initial": initial,
                "rows": rows,
                "end": end,
                "engine": _engine_commit(),
            },
            handle,
        )
    return name, f"{end[:70]} steps={len(rows)}"


def check_game(path: str) -> dict[str, Any]:
    with open(path, "rb") as handle:
        data = pickle.load(handle)  # noqa: S301 - our own files
    name, options, seed, _kinds = data["spec"]
    stepper = _Stepper(options, seed)
    report: dict[str, Any] = {
        "name": name,
        "steps": len(data["rows"]),
        "end": data["end"][:80],
    }
    if stepper.state_digest() != data["initial"]:
        return report | {"status": "different", "step": -1, "kinds": ["state"]}
    actions: Counter[str] = Counter()
    for index, row in enumerate(data["rows"]):
        step, legal_key, views, events, state_digest = row[:5]
        page = row[5] if len(row) > 5 else None
        state = stepper.state
        kinds: list[str] = []
        try:
            decision = stepper.engine.current_decision(state)
            if stepper.views() != views:
                kinds.append("views")
            if step[0] == "c":
                if (
                    not isinstance(decision, ChanceDecision)
                    or _chance_key(decision) != legal_key
                ):
                    kinds.append("chance")
                outcome = ChanceOutcome(decision_id=step[1], values=step[2])
                result = stepper.engine.apply(state, outcome)
            else:
                action = DomainAction(
                    action_id=step[1], actor=step[2], arguments=step[3]
                )
                actions[action.action_id] += 1
                if not isinstance(decision, PlayerDecision):
                    kinds.append("legal")
                    result = stepper.engine.apply(state, action)
                else:
                    legal = stepper.engine.legal_actions(state, decision.owner)
                    if _digest((decision.owner, legal)) != legal_key:
                        kinds.append("legal")
                    if page is not None and _page_key(
                        state, decision.owner, legal
                    ) != page:
                        kinds.append("page")
                    result = stepper.engine.apply(state, action)
        except Exception:  # noqa: BLE001 - reported
            return report | {
                "status": "raised",
                "step": index,
                "step_value": repr(step)[:300],
                "trace": traceback.format_exc()[-1500:],
                "actions": dict(actions),
            }
        stepper.state = result.state
        if _digest(result.events) != events:
            kinds.append("events")
        if stepper.state_digest() != state_digest:
            kinds.append("state")
        if kinds:
            return report | {
                "status": "different",
                "step": index,
                "kinds": kinds,
                "step_value": repr(step)[:300],
                "actions": dict(actions),
            }
    pages = all(len(row) > 5 for row in data["rows"])
    return report | {"status": "same", "actions": dict(actions), "pages": pages}


def _engine_commit() -> str:
    import dune_imperium

    source = Path(dune_imperium.__file__).resolve().parent
    try:
        return subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        return f"(not a checkout: {source})"


def _nice() -> None:
    if hasattr(os, "nice"):
        os.nice(10)


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

    paths = sorted(str(p) for p in Path(args.trace_dir).glob("*.pkl"))
    if not paths:
        sys.exit(f"no recorded games in {args.trace_dir}")
    with Pool(args.workers, initializer=_nice) as pool:
        results = list(pool.imap_unordered(check_game, paths))
    results.sort(key=lambda r: r["name"])
    if args.report:
        Path(args.report).write_text(json.dumps(results, indent=1))
    statuses = Counter(r["status"] for r in results)
    steps = sum(r["steps"] for r in results if r["status"] == "same")
    coverage: Counter[str] = Counter()
    for r in results:
        coverage.update(r.get("actions", {}))
    print(f"checked on {_engine_commit()}: {dict(statuses)}; {steps} steps the same")
    unpaged = sum(1 for r in results if r["status"] == "same" and not r.get("pages"))
    if unpaged:
        print(f"page not compared in {unpaged} games (recorded before the page kind)")
    print("action ids replayed:", len(coverage), dict(sorted(coverage.items())))
    for r in results:
        if r["status"] != "same":
            print(json.dumps({k: v for k, v in r.items() if k != "actions"})[:900])
    sys.exit(0 if statuses.keys() == {"same"} else 1)


if __name__ == "__main__":
    main()
