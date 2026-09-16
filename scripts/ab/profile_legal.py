"""cProfile of run_policy_game restricted to the legal-action and observation paths.

Call counts are contention-immune; cumulative times are proportions of one run.
"""

import cProfile
import io
import pstats

from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.config import RulesetConfig
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

engine = UprisingRulesEngine()
config = RulesetConfig()
prof = cProfile.Profile()
prof.enable()
for seed in range(10):
    run_policy_game(
        engine, config, seed, [HeuristicAgent(seed=900000 + seed + s) for s in range(4)]
    )
prof.disable()
s = io.StringIO()
ps = pstats.Stats(prof, stream=s).sort_stats("cumulative")
ps.print_stats(
    r"agent_turn\.py|observation\.py|legal_actions|agent_effect_frame|board_effects\.py:.*legal|reveal_turn\.py:.*legal"
)
lines = [
    line
    for line in s.getvalue().splitlines()
    if "dune_imperium" in line or "ncalls" in line
]
print("\n".join(lines[:45]))
