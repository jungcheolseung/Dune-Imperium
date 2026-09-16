"""How much of a heuristic game goes to handler-level ``action not in legal_*`` guards.

Profiles run_policy_game and attributes each legal_* provider's cumulative time to
its callers; the share called from apply_* handlers is the cost of re-validating
what the dispatcher already
validated. Call counts are contention-immune; times are proportions of one run.
"""

import cProfile
import pstats
import sys

from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.config import RulesetConfig
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

games = int(sys.argv[1]) if len(sys.argv) > 1 else 10
flags = {k: True for k in sys.argv[2:]}
engine = UprisingRulesEngine()
config = RulesetConfig(**flags)
prof = cProfile.Profile()
prof.enable()
for seed in range(games):
    run_policy_game(
        engine, config, seed, [HeuristicAgent(seed=900000 + seed + s) for s in range(4)]
    )
prof.disable()
stats = pstats.Stats(prof)
stats.calc_callees()
total = stats.total_tt
rows = []
for func, (_cc, _nc, _tt, _ct, callers) in stats.stats.items():
    name = func[2]
    if not name.startswith("legal_"):
        continue
    for caller, value in callers.items():
        cname = caller[2]
        if cname.startswith("apply_") or cname.startswith("_apply_"):
            # value = (ncalls, nonrec, tottime, cumtime) of this edge
            rows.append((value[3], value[0], name, cname))
rows.sort(reverse=True)
guard_total = sum(r[0] for r in rows)
print(
    f"games={games} flags={flags} total={total:.2f}s "
    f"guard cumtime={guard_total:.3f}s ({100 * guard_total / total:.1f}%)"
)
for ct, n, name, cname in rows[:30]:
    print(f"{ct:7.3f}s {n:6d}  {name} <- {cname}")
