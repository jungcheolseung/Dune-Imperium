+++
title = "First codec v150 retraining attempt: the previous network as teacher"
description = "An adapter let the previous codec's play network act on the new action units, followed by one distillation and reinforcement learning run. The new network was weaker than its teacher and was not installed."
date = 2026-10-21T08:00:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-21"
source_ref = "c8f61677"
sources = ["docs/worklog/2026-10.md", "docs/development-handoff.md", "src/dune_imperium/training/older_teacher.py"]
+++
## Why retraining was needed

After the action units changed in [stage B]({{< relref path="devlog/2026-10-20-action-units.md" lang="en" >}}), the play network (an MLP trained at codec v147) knew only 84 of the 4,311 new action rows. Decisions on unlearned rows fall back to the heuristic, which weakens search AI seats.

Instead of training from scratch, the first approach used the current network as a teacher for a student network on the new action units. The student is the entity network that reads card and space features.

## Teacher adapter

The new engine asks for card and space, or effect and target, separately. The adapter regroups these steps into one old-engine action, attaches the old action row, and collects the old network's scores onto the current step's choices. In a sample of 3,932 decisions, 94.7% received an old row. 4.8% were decisions the old engine never asked, such as reward icon order, and use the old engine's fixed answer; 0.5% use the heuristic.

In the first run, 695 of 1,000 games hit the 30,000-step limit. The cause was a loop of re-choosing a Scouts bid at the same position without confirming it. The fix stops the seat from repeating an action already chosen at the same observation.

The old network on the v149 engine was compared with the adapter on the v150 engine: one seat against three hard app AIs, all options and leader draft, 1,000 games each. Win rates were 54.7% and 54.8%, and 996 of the 1,000 games on the same seeds ended with the same final VP and ranks.

## Distillation and reinforcement learning

One chain ran overnight on the Mac mini.

1. 2,599,119 training rows from games played by the teacher (80 iterations, 17 minutes, no truncated games)
2. Student, 4 epochs: 87.5% agreement with the teacher
3. Reinforcement learning (REINFORCE, learning rate 1e-5), 800 iterations, 3.6 hours

Win rates against three hard app AIs on the same 400 game seeds:

| Model | Win rate |
| --- | ---: |
| Old network (v149 engine) | 56.5% |
| Adapter teacher (v150 engine) | 56.8% |
| Teacher's distribution, top choice at each step | 57.5% |
| Student, 4 epochs (REINFORCE start) | 47.5% |
| Student, 12 epochs (cosine learning-rate decay) | 52.0% |
| REINFORCE 300 / 600 / 800 iterations | 52.2% / 49.0% / 51.5% |

Picking the teacher's top choice at each step already reached 57.5%, so splitting actions into steps was not itself a loss; the strength was lost in distillation. The student agreed with the teacher on 99.2% of confident decisions (top probability above 0.9) but only 79% of decisions where the teacher was split (below 0.6, 32% of all decisions). In-training 25-game evaluations moved between 0.41 and 0.54, so REINFORCE at 1e-5 did not show steady improvement either.

Finally, in a 2-vs-2 network comparison (1,400 games), the REINFORCE 800 network's win rate was 7.0 points below the adapter teacher (95% interval −12.1 to −1.7 points).

## Outcome and next decision

The new network was not installed for play, and the search-seat comparison was not run. The adapter, its measurement tournament seat, and the student learning-rate decay option were merged into master. The adapter seat is for measurement only and cannot be chosen on the play server.

Since the adapter reproduces the old network's strength on v150 almost exactly, there are three candidates: let search AI seats use the old network through the adapter (needs design and implementation), restart REINFORCE from the 12-epoch student, or scale up distillation. None has been chosen yet.

## References

- [Merge retrain-v150: the older-codec teacher for the stage B retrain](https://github.com/jungcheolseung/Dune-Imperium/commit/7aa8d9bc)
- [older_teacher.py](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/src/dune_imperium/training/older_teacher.py)
- [docs/worklog/2026-10.md](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/worklog/2026-10.md)
- [development-handoff.md](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/development-handoff.md)
