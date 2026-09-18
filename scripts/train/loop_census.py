"""Census of long games under the training runner (undo actions withheld).

usage: loop_census2.py CHECKPOINT FIRST_ITERATION_INDEX GAMES
Plays GAMES sampled self-play games on the training seeds that start at the
given 0-based iteration index and reports the longest ones with their
dominant action ids and identical-observation revisit share.
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

import torch

from dune_imperium.config import RulesetConfig
from dune_imperium.training.checkpoint import load_checkpoint
from dune_imperium.training.loop import TRAINING_SEED_BASE
from dune_imperium.training.selfplay import SelfPlayRunner, SelfPlaySpec
from dune_imperium.training.torch_policy import TorchBatchPolicy

checkpoint = Path(sys.argv[1])
first_iteration = int(sys.argv[2])
games = int(sys.argv[3])
torch.set_num_threads(4)
network, info = load_checkpoint(checkpoint)
ruleset = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
)
runner = SelfPlayRunner(ruleset, max_steps=4_000, record=True, undo_actions=False)
catalog = runner.codec.catalog
first = TRAINING_SEED_BASE + first_iteration * 32
specs = tuple(
    SelfPlaySpec(game_seed=first + k, lineup=("learner",) * 4) for k in range(games)
)
policy = TorchBatchPolicy(
    network, torch.device("cpu"), seed=first_iteration * 1_000 + 1, sample=True
)
started = time.perf_counter()
result = runner.run({"learner": policy}, specs)
decisions = sorted(e.decisions for e in result.episodes)
print(
    f"checkpoint iteration {info.iteration}; {games} games in "
    f"{time.perf_counter() - started:.0f}s"
)
print(
    f"decisions/game: min {decisions[0]} median {decisions[len(decisions) // 2]} "
    f"max {decisions[-1]}; truncated {sum(e.truncated for e in result.episodes)}"
)
total = Counter()
for episode in result.episodes:
    total.update(catalog[s.action].action_id for s in episode.steps)
for episode in sorted(result.episodes, key=lambda e: -e.decisions)[:4]:
    kinds = Counter(catalog[s.action].action_id for s in episode.steps)
    seen: set[tuple[int, bytes]] = set()
    revisits = 0
    for step in episode.steps:
        key = (step.seat, step.observation.tobytes())
        revisits += key in seen
        seen.add(key)
    per_seat = dict(sorted(Counter(s.seat for s in episode.steps).items()))
    print(
        f"seed {episode.game_seed}: decisions {episode.decisions} rounds "
        f"{episode.rounds} truncated {episode.truncated} per seat {per_seat} "
        f"revisits {revisits / len(episode.steps):.0%}"
    )
    print("    top:", ", ".join(f"{n} {c}" for n, c in kinds.most_common(7)))
count_all = sum(total.values())
print(
    "all games top 10:",
    ", ".join(f"{n} {c / count_all:.1%}" for n, c in total.most_common(10)),
)
