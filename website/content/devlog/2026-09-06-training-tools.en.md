+++
title = "Evaluation tools and the first training loop"
description = "Connect baseline tournaments, self-play, a policy/value network, learning, and checkpoints."
date = 2026-09-06
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-09-06"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/evaluation/baseline-2026-09-06.md", "docs/worklog/2026-09.md"]
+++
## Establishing comparisons

Before learning, a tournament tool compared random, heuristic, and rollout agents with recorded seeds and seat assignments. This allowed later versions to be evaluated under repeatable conditions.

A self-play runner batched neural-network inference across games. The shared engine advanced the games, and each policy chose among legal actions.

## The first model and learning loop

An MLP with policy/value outputs, a learner, checkpoint saving/loading, and periodic evaluation were connected. The initial algorithm was REINFORCE with a value baseline, before later PPO and input-architecture experiments.

Repeated games exposed both policy cycles and engine states with no legal action. Those were treated as different problems.

## Remaining questions

Producing a checkpoint did not establish strong play. Training quantity, comparison opponents, and the correctness of evaluation became major subsequent tasks.

## References

- [Add the M9 baseline tournament runner and report](https://github.com/jungcheolseung/Dune-Imperium/commit/03687815)
- [Add the lockstep self-play runner with batched policy inference](https://github.com/jungcheolseung/Dune-Imperium/commit/ad32ea01)
- [Add the M10 policy network, learner, checkpoints, and training loop](https://github.com/jungcheolseung/Dune-Imperium/commit/01a6a181)
