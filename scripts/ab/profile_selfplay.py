"""cProfile of the M10 collection path (SelfPlayRunner, heuristic seats, recording)."""

import cProfile
import io
import pstats
import sys

from dune_imperium.config import RulesetConfig
from dune_imperium.training.policy import AgentBatchPolicy
from dune_imperium.training.selfplay import SelfPlayRunner, SelfPlaySpec

games = int(sys.argv[1]) if len(sys.argv) > 1 else 8
policy = sys.argv[2] if len(sys.argv) > 2 else "heuristic"
config = RulesetConfig()
runner = SelfPlayRunner(config, record=True)
specs = [
    SelfPlaySpec(game_seed=2_000_000 + s, lineup=(policy,) * 4) for s in range(games)
]
prof = cProfile.Profile()
prof.enable()
result = runner.run({policy: AgentBatchPolicy(policy, 1)}, specs)
prof.disable()
print(
    f"games={games} decisions={result.decisions} "
    f"duration={result.duration_seconds:.2f}s "
    f"({result.decisions / result.duration_seconds:,.0f} dec/s)"
)
s = io.StringIO()
ps = pstats.Stats(prof, stream=s).sort_stats("tottime")
ps.print_stats(25)
print(s.getvalue()[:5500])
s = io.StringIO()
ps = pstats.Stats(prof, stream=s).sort_stats("cumulative")
ps.print_stats(
    r"legal_actions|engine\.py.*apply|observe_state|encode_player_view|codec|_advance_automatic|_replace|__post_init__|choose_action|_request|_apply\b|act\b|canonical"
)
print(
    "\n".join(
        line
        for line in s.getvalue().splitlines()
        if "dune_imperium" in line or "ncalls" in line
    )[:5000]
)
