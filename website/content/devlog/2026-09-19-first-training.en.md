+++
title = "The first real training run: a policy that only undid and repeated, and the learning rate"
description = "The first long run on the full-expansion configuration: telling a troop deploy-and-withdraw loop from a memory problem, fixing the action list and checkpoint format, rejecting PPO, and lowering the learning rate to break a plateau."
date = 2026-09-19T17:57:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-17"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/worklog/2026-09.md", "docs/worklog/handoff-core-before-2026-10-12.md", "docs/rl-environment.md"]
+++

## The first long run on the full-expansion configuration

[The previous entry]({{< relref path="devlog/2026-09-16-baseline-ai.md" lang="en" >}}) set the training target to the configuration with CHOAM, Bloodlines, Tech Module, Immortality and promos all on. It has 32,963 action codec entries and a network of about 19 million parameters. On the night of September 17 we ran the first long training on a Windows PC (i7-13700K, WSL2) set aside for training. Each iteration collected 32 games over 8 workers and updated once.

All numbers in this entry come from the engine before the rule corrections of September 20. Those corrections are covered in [the next entry]({{< relref path="devlog/2026-09-22-evaluation-corrections.md" lang="en" >}}).

## It looked like a memory failure but was the policy

The first run was stopped by a memory safety guard at iteration 19. Before adding memory, we looked at the policy. Eight self-play games sampled from that checkpoint's policy showed that 80% of decisions were a back-and-forth between deploying troops (`deploy_troops`) and withdrawing them (`withdraw_troops`), and in games cut at the 4,000-decision cap, 82–90% of decisions were revisits to a byte-identical observation. Iteration 20 had 13 of 32 games hit the cap, with 12.9 GB in the main process. The per-decision penalty and cap from September 6 had not prevented this, and the guard for collection was off because of that day's negative result.

We confirmed the cause with an intervention. Taking only the withdraw side out of what the policy can choose, on the same checkpoint and seeds, cut decisions per game from 3,018 to 699 and games hitting the cap from 3 of 8 to 0 of 8. A policy in training had found the undoable pair to be the easiest path, and memory was only the consequence.

We chose to have the collector and checkpoint play (`NetworkAgent`) not offer the withdraw actions (`withdraw_troops`, `withdraw_commanders`) to the policy. The engine keeps the full legal set, and the recorded mask equals the mask the policy saw, so training stays on-policy. The rule justification is the OQ-029 ruling: deployment may be done after the turn's other effects, so a policy that deploys last loses nothing ([`2bba03ab`](https://github.com/jungcheolseung/Dune-Imperium/commit/2bba03ab)). We then ran 837 iterations (26,784 games) in about 8 hours without a restart: 716–876 steps per game, one cut game in total, and flat group memory around 10 GB.

## Codec v105 and checkpoint format 2

Evaluating checkpoint 550 in the in-training evaluation counted only 79 of 80 games. With seed 13 and a Chani seat, `retreat_leader_troops(commanders=1, count=13)` was missing from the action codec so conversion failed, and the evaluation silently dropped failed games. We extended Fedaykin Maneuver's Commander share range to 19, the same as the Intrigue side that had been fixed in v104, adding 28 entries (codec v105), and pinned round-trips for every troop and Commander combination the engine can produce with a test ([`4f13a57d`](https://github.com/jungcheolseung/Dune-Imperium/commit/4f13a57d)). Failed evaluation games are now written to a separate file.

A codec change would have forced us to discard old checkpoints, and the overnight run was 34 files, so we built checkpoint format 2 first ([`ec52c18c`](https://github.com/jungcheolseung/Dune-Imperium/commit/ec52c18c)). Saving now writes the list of action template identities and the observation layout; loading moves output-layer rows and columns by identity, starts new entries at 0, and carries Adam's moments along. The 34 files written under v104 loaded under v105 with 32,963 entries preserved and 28 new ones, the seed 13 game ran to the end, the evaluation of 550 counted all 80 games (59 wins), and `--resume` for 2 iterations also worked.

Around then we also fixed tournament workers that each took as many torch threads as there were logical CPUs, costing 205 ms per decision; one thread per worker brought it to 9 ms with identical results. For 32-game iterations 8 workers were fastest, with 16 workers 1.5 times slower and 24 workers 2 times slower; we did not measure why.

## Learning rate 3e-4 plateaued and PPO collapsed

The overnight run at learning rate 3e-4 rose until iterations 400–550, plateaued, and fell back at 700. Checkpoint 550 scored 76.5% over 200 games against three heuristics. The in-training evaluation was 80 games (20 seeds times four rotations), with an error of plus or minus 5 points.

Our hypothesis for the plateau was that one iteration's independent samples are only the outcomes of 32 games, so updates are dragged around by noise. We tested two things in sequential A/Bs from the same starting point (550), same seeds, 32 games and 100 iterations.

First we compared PPO (clip 0.2, 3 epochs on the same batch) with a plain REINFORCE control. PPO took longer (98 minutes against 58) and collapsed.

| Evaluation | Start 550 | Control 650 | PPO 650 |
| --- | ---: | ---: | ---: |
| In-training evaluation (80 games, four readings) | | 70.0, 72.5, 71.2, 70.0% | 55.0, 33.8, 37.5, 42.5% |
| Four-checkpoint match (400 games, seeds from 1000) | 45.0% | 35.0% | 12.5% |
| vs 3 heuristics (200 games) | 76.5% | 75.5% | 43.0% |

(The value for the same starting point differs between tables because the other checkpoints at the table differ.) PPO's diagnostics were mild (clip fraction 0.04–0.06, approximate KL 0.004–0.006). On 24 new games the explained variance of the value function was 0.15 for the start, 0.07 for the control and 0.22 for PPO, so value overfitting was not the cause. This fits the hypothesis that PPO, training several times on the same 32 games, amplified outcome noise, but we did not confirm it by intervention. We kept PPO as an option and recorded the rejection ([`575687cf`](https://github.com/jungcheolseung/Dune-Imperium/commit/575687cf)).

Next we kept everything identical to the control and lowered only the learning rate to 1e-4 in REINFORCE, running 100 iterations from the same start. The in-training evaluation rose to 76.2, 72.5, 77.5 and 83.8% (control 70.0, 72.5, 71.2, 70.0%). In a 400-game four-checkpoint match, the 1e-4 run's 650 scored 33.0%, the start 550 scored 24.8%, the control 650 scored 24.5% and the same run's 600 scored 17.8%. Against three heuristics over 200 games it was 81.0% (start 76.5%, control 75.5%). Fluctuation between checkpoints remained (600 was the weakest).

We continued that run for 1,000 iterations (650 to 1650, from 22:20 to 08:10 the next day, 9 hours 50 minutes) with the same settings. There were no restarts, exceptions, failed evaluations or cut games, with 721–806 steps per game and a peak group memory of 11.3 GiB. The in-training evaluation (200 games) rose from 74.7% (mean of the first five readings) to 82.7% (mean of the last five; peak 87.5% at 1400). In the four-checkpoint match (400 games, seeds from 1000) the shares were 9.2% for 550, 21.8% for 1000, 32.0% for 1300 and 37.0% for 1650; against three heuristics over 200 games, 76.5% for 550, 79.5% for 1000, 84.5% for 1300 and 83.0% for 1650. The rise after 1400 was small, however (a four-way match of 1400, 1500, 1600 and 1650 gave 24.2, 24.8, 23.0 and 28.0%, standard error about 2.2 points). With the same algorithm and data, moving less per step was enough to break the plateau; this is one lineage and one seed.

## The learning rate that did not apply

On the afternoon of September 19 we moved training to a Mac mini (M4, 16 GB). We ported the memory guard and overnight supervisor to macOS, and `--device mps` matched numerically but gained only 5%, so we did not use it. We chose 4 workers: during collection the 4 performance cores were at 99.5% and the efficiency cores idle.

Before launching an experiment from 1650 with a lower rate (3e-5), we checked with a small network whether `--learning-rate` takes effect when resuming from a checkpoint with optimizer state. It did not. Restoring the optimizer let the saved learning rate overwrite the requested one, so the 3e-5 arm would actually have run at 1e-4 and we would have had two controls. We made the requested value win (moments and step count still carry over) and added tests that fail before the fix ([`61b09df`](https://github.com/jungcheolseung/Dune-Imperium/commit/61b09df)). Earlier runs were unaffected: the first 1e-4 experiment started from the numbered checkpoint 550, which has no optimizer state, and the overnight continuation asked for the rate its checkpoint already had. In the same period we recorded a mistake: the handoff listed four candidates and the one whose resume command was written there was launched without asking which was meant. Before a long run we now ask.

After the fix we compared 1e-4 (control) with 3e-5 from 1650. The in-training evaluation (200 games) averaged 82.6% and 84.2%, a difference of +1.6 points with a standard error of about 1.5. The four-checkpoint match (400 games) gave 27.8% for 3e-5 at 2050, 26.0% for the start 1650, 24.5% for 1e-4 at 2050 and 21.8% for 3e-5 at 1850, indistinguishable within a standard error of about 2.2 points; against three heuristics over 200 games the start scored 83.0%, 1e-4 at 2050 88.0% and 3e-5 at 2050 83.5%. In the in-training evaluation there was a stretch where 3e-5 rose four times in a row, but the control jumped once too and the match was flat, so we were right not to draw a conclusion from a few in-loop points.

## What is left

- The in-training evaluation had a seed defect. Each evaluation reused the same block of seeds (20–50), so the in-training curves in this entry are repeated readings of the same small sample, not a series of fresh samples. We found it on September 21 and fixed it (see [the next entry]({{< relref path="devlog/2026-09-22-evaluation-corrections.md" lang="en" >}})); the four-checkpoint matches and the 200-game runs against heuristics used a separate seed range (from 1000) and were not affected.
- The rule corrections of September 20 turned all numbers in this period, and the 1650 and 2050 checkpoints, into old-rule results.
- The reading that the learning rate alone broke the plateau is one lineage and one seed and has not been reproduced.
- We cleaned up 36 orphaned worker processes (947 MiB) left on this Mac since the evening of September 16, and wrote the procedure into the project's working instructions.

## References

- [Withholding the undo actions from the policy](https://github.com/jungcheolseung/Dune-Imperium/commit/2bba03ab)
- [Every Fedaykin Maneuver retreat in the codec](https://github.com/jungcheolseung/Dune-Imperium/commit/4f13a57d)
- [Migrating checkpoints across codec and observation versions](https://github.com/jungcheolseung/Dune-Imperium/commit/ec52c18c)
- [Opt-in PPO term and the rejected A/B](https://github.com/jungcheolseung/Dune-Imperium/commit/575687cf)
- [Training guard and supervisor on macOS](https://github.com/jungcheolseung/Dune-Imperium/commit/bd8732f)
- [Letting a resumed run set its learning rate](https://github.com/jungcheolseung/Dune-Imperium/commit/61b09df)
- [Checkpoint migration notes](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rl-environment.md)
- [September work log](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/worklog/2026-09.md)
