"""Time ``legal_actions`` over recorded equivalence games (composed-effects gate 6).

``scripts/ab/engine_equivalence.py record`` keeps every step of 200 seeded
games. This replays the recorded steps of ``games`` of them (spread over the
plan) on the importable engine and sums the wall time of ``legal_actions``
at every player decision, ``repeats`` times each: overall, and where an
Intrigue choice or lines frame is on top. Run it on the stage's start
master and on its branch in turn, a few times each, and compare the per-call
times (docs/composed-effects-plan.md 6, item 6)::

    PYTHONPATH=tmp/claude/<session>/engines/<base8>/src .venv/bin/python \
        scripts/ab/time_legal.py tmp/claude/<session>/equiv/<base8> 100 3
    .venv/bin/python scripts/ab/time_legal.py \
        tmp/claude/<session>/equiv/<base8> 100 3
"""

import pickle
import sys
import time
from pathlib import Path

from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.rules import UprisingRulesEngine

# Frames the stage A1 moved onto the executor; a later stage adds its own.
INTRIGUE = {"intrigue_choice", "intrigue_effects"}


def main() -> None:
    trace_dir, games, repeats = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    files = sorted(trace_dir.glob("*.pkl"))[:: max(1, 200 // games)][:games]
    engine = UprisingRulesEngine()
    total = intrigue = 0.0
    calls = intrigue_calls = 0
    for path in files:
        data = pickle.loads(path.read_bytes())
        _name, options, seed, _kinds = data["spec"]
        state = engine.reset(RulesetConfig(**options), seed)
        for step, *_ in data["rows"]:
            if step[0] == "c":
                state = engine.apply(
                    state, ChanceOutcome(decision_id=step[1], values=step[2])
                ).state
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
            action = DomainAction(action_id=step[1], actor=step[2], arguments=step[3])
            state = engine.apply(state, action, legal_actions=legal).state
    print(
        f"games={len(files)} calls={calls} total_s={total:.3f} "
        f"per_call_us={total / calls * 1e6:.1f} intrigue_calls={intrigue_calls} "
        f"intrigue_s={intrigue:.4f} "
        f"intrigue_per_call_us={intrigue / max(1, intrigue_calls) * 1e6:.1f}"
    )


if __name__ == "__main__":
    main()
