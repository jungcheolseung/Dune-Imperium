"""Time ``legal_actions`` over recorded equivalence games (composed-effects gate 6).

``scripts/ab/engine_equivalence.py record`` keeps every step of 200 seeded
games. This replays the recorded steps of ``games`` of them (spread over the
plan) on the importable engine and sums the wall time of ``legal_actions``
at every player decision, ``repeats`` times each: overall, where an
Intrigue choice or lines frame is on top (stage A1), and where the
Agent-turn effect frame is (stage A2). Run it on the stage's start
master and on its branch in turn, a few times each, and compare the per-call
times (docs/composed-effects-plan.md 6, item 6)::

    PYTHONPATH=tmp/claude/<session>/engines/<base8>/src .venv/bin/python \
        scripts/ab/time_legal.py tmp/claude/<session>/equiv/<base8> 100 3
    .venv/bin/python scripts/ab/time_legal.py \
        tmp/claude/<session>/equiv/<base8> 100 3

A candidate that changes the steps on purpose replays the recording through
its declared differences (``engine_equivalence.py check --differences``),
given as a fourth argument: their ``old`` hooks rewrite or drop a recorded
step, ``moves`` replace it, and ``answer`` takes the decisions the base did
not have. Only the recorded steps' decisions are timed, so the call counts
stay those of the base. Give the base the same module with a fifth argument
``base``: matching the answers asks the engine for the next decision's legal
list, which warms its caches for the timed calls (about 15% at cleanup-2a),
while the ``old`` and ``moves`` hooks, which put a recorded step in the
candidate's form (dropping a refusal the base still needs), are not applied.
"""

import sys
import time
from collections.abc import Sequence
from typing import Any

from engine_equivalence import load, load_rules, recordings
from equivalence_rules import At, Rule, Step

from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.rules import UprisingRulesEngine

# Frames the stage A1 moved onto the executor; a later stage adds its own.
INTRIGUE = {"intrigue_choice", "intrigue_effects"}
# The Agent-turn effect frame, whose boxes stage A2 began to move.
AGENT = {"agent_effects"}


def _answer(
    engine: UprisingRulesEngine,
    state: object,
    rules: tuple[Rule, ...],
    old: Step,
    rows: Sequence[Any] = (),
    *,
    apply: bool = True,
) -> object:
    """Apply the declared answers to decisions the base did not have
    (``rows``: the recording's, for an answer the base gave later). On the
    base (``apply`` false) the answers are only matched, for the caches: the
    base recorded the games, and an answer could take its own later step
    (its cleanup's Harvest Cells choice) for the candidate's."""

    while rules:
        decision = engine.current_decision(state)
        legal = (
            engine.legal_actions(state, decision.owner)
            if isinstance(decision, PlayerDecision)
            else ()
        )
        at = At(engine, state, decision, legal, old, rows, old.index)
        move = next(
            (m for rule in rules if rule.answer and (m := rule.answer(at)) is not None),
            None,
        )
        if move is None or not apply:
            break
        state = engine.apply(state, move).state
    return state


def _chance(engine: UprisingRulesEngine, state: Any, step: Sequence[Any]) -> Any:
    """The recorded chance outcome, under the decision this engine asks when
    only its name changed (cleanup-2c renamed the draws, and the reshuffles
    named after them): the same shuffle of the same cards."""

    decision = engine.current_decision(state)
    decision_id = str(step[1])
    if (
        isinstance(decision, ChanceDecision)
        and decision.decision_id != decision_id
        and sorted(decision.options) == sorted(step[2])
        and decision_id.rsplit(":", 1)[1] == decision.decision_id.rsplit(":", 1)[1]
    ):
        decision_id = decision.decision_id
    return ChanceOutcome(decision_id=decision_id, values=tuple(step[2]))


def main() -> None:
    trace_dir, games, repeats = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    rules = load_rules(sys.argv[4]) if len(sys.argv) > 4 else ()
    base = len(sys.argv) > 5 and sys.argv[5] == "base"
    files = recordings(trace_dir)[:: max(1, 200 // games)][:games]
    engine = UprisingRulesEngine()
    total = intrigue = agent = 0.0
    calls = intrigue_calls = agent_calls = 0
    for path in files:
        data = load(path)
        _name, options, seed, _kinds = data["spec"]
        state = engine.reset(RulesetConfig(**options), seed)
        for index, row in enumerate(data["rows"]):
            old = Step(index, *row[:5])
            for rule in rules:
                if rule.old is not None and not base:
                    rule.old(old)
            if old.vanish:
                continue
            step = old.step
            if step[0] == "c":
                state = engine.apply(state, _chance(engine, state, step)).state
                state = _answer(engine, state, rules, old, data["rows"], apply=not base)
                continue
            decision = engine.current_decision(state)
            assert isinstance(decision, PlayerDecision)
            top = str(state.decision_stack[-1].kind)
            start = time.perf_counter()
            for _ in range(repeats):
                legal = engine.legal_actions(state, decision.owner)
            spent = time.perf_counter() - start
            total += spent
            calls += repeats
            if top in INTRIGUE:
                intrigue += spent
                intrigue_calls += repeats
            if top in AGENT:
                agent += spent
                agent_calls += repeats
            action = DomainAction(action_id=step[1], actor=step[2], arguments=step[3])
            at = At(engine, state, decision, legal, old, data["rows"], index)
            moves = next(
                (
                    tuple(m)
                    for rule in rules
                    if rule.moves
                    and not base
                    and (m := rule.moves(old, at)) is not None
                ),
                None,
            )
            if moves is None:
                state = engine.apply(state, action, legal_actions=legal).state
            else:
                for move in moves:
                    state = engine.apply(state, move).state
            state = _answer(engine, state, rules, old, data["rows"], apply=not base)
    print(
        f"games={len(files)} calls={calls} total_s={total:.3f} "
        f"per_call_us={total / calls * 1e6:.1f} intrigue_calls={intrigue_calls} "
        f"intrigue_s={intrigue:.4f} "
        f"intrigue_per_call_us={intrigue / max(1, intrigue_calls) * 1e6:.1f} "
        f"agent_calls={agent_calls} "
        f"agent_per_call_us={agent / max(1, agent_calls) * 1e6:.1f}"
    )


if __name__ == "__main__":
    main()
