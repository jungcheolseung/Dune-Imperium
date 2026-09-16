"""cProfile of run_policy_game (heuristic mirror, base): top functions by own time."""

import cProfile
import io
import pstats
import sys

from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.config import RulesetConfig
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

games = int(sys.argv[1]) if len(sys.argv) > 1 else 10
engine = UprisingRulesEngine()
config = RulesetConfig()
prof = cProfile.Profile()
prof.enable()
steps = 0
for seed in range(games):
    sim = run_policy_game(
        engine, config, seed, [HeuristicAgent(seed=900000 + seed + s) for s in range(4)]
    )
    steps += len(sim.replay.steps)
prof.disable()
print(f"games={games} steps={steps}")
s = io.StringIO()
ps = pstats.Stats(prof, stream=s).sort_stats("tottime")
ps.print_stats(28)
print(s.getvalue()[:6000])
s = io.StringIO()
ps = pstats.Stats(prof, stream=s).sort_stats("cumulative")
ps.print_stats(
    r"legal_actions|current_agent_effect_context|observe|_advance_automatic|_replace|__post_init__|canonical|score_action|choose_action"
)
print(
    "\n".join(
        line
        for line in s.getvalue().splitlines()
        if "dune_imperium" in line or "ncalls" in line
    )[:5000]
)
