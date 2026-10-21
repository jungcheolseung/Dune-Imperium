+++
title = "Evaluation tools and the first training loop"
description = "A tournament tool for random, heuristic and rollout AIs and a batched self-play runner, then a first neural network whose training exposed policy loops and engine dead ends."
date = 2026-09-06T22:40:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-06"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/evaluation/baseline-2026-09-06.md", "docs/worklog/2026-09.md"]
+++

## A yardstick before any training

By this date the engine had two AIs: one that picks a random legal action (`random`) and a heuristic that scores each action (`heuristic`). Before training a neural network we needed a repeatable way to say what it was stronger than. In one day we built three things in order and then ran the first training.

## The tournament tool and the baseline

The tournament tool (`dune-imperium-tournament`) bundles seed, the AI at each seat, rule options and leader assignment into one match specification and spreads matches over worker processes. The four seat rotations of one seed share leaders, decks and first player and differ only in who sits where, so seat bias can be measured separately. Results report win rate (first place in the official final ranking), mean rank, mean VP, VP margin against the other three seats, first-player results, time per decision and the number of illegal actions. An illegal action is counted and replaced by the first legal one.

The first baseline used the base game with no expansions, 25 seeds times four seat rotations (100 games).

| Matchup | Games | Result |
| --- | --- | --- |
| 1 heuristic vs 3 random | 100 | heuristic wins 95.0%, mean rank 1.06, VP margin +5.74 |
| heuristic mirror (all four seats heuristic) | 400 | 22.8–26.8% per seat, first player 25.0% |
| random mirror | 200 | 20.5–30.5% per seat |
| 1 rollout vs 3 heuristic | 100 | rollout wins 48.0%, mean rank 1.90, VP margin +1.51 |

The heuristic mirror showed no clear seat or first-player bias. By leader the results split (Gurney Halleck 38.3%, Staban Tuek 17.2%), which says the heuristic uses leader abilities unevenly; it is not evidence about leader balance. With 8 workers the tool ran at about 60 games/s, and illegal actions were 0 in every run.

The rollout AI builds imagined worlds by re-dealing what the observer cannot see (opponents' hands, deck order), takes the top 6 heuristic-scored candidates, and plays each one to the end of the round in every imagined world. It costs about 25 ms per decision, roughly 4 seconds per game. These baseline numbers were all replaced after the heuristic was reworked on September 10 and 16 (see [the next entry]({{< relref path="devlog/2026-09-16-baseline-ai.md" lang="en" >}})).

## The batched self-play runner and the first network

The self-play runner advances many games one step at a time in lockstep, gathers the requests of seats that share a policy, and runs inference once per policy. With 32 games in one process it reached about 4,900 decisions/s; the engine's `apply` dominated, so policy cost was invisible.

The first network takes the log-transformed observation vector through a 512x512 MLP and outputs logits for 4,354 actions (illegal ones masked) plus a value. Training is REINFORCE with a value baseline, and at this stage the only reward is the terminal one (winner +1, others -1/3). Collection, update, log, checkpoint and periodic tournament evaluation form one loop (`dune-imperium-train`). A checkpoint records the observation version, action codec version and rule options, and loading refuses a mismatch. Training started on an Apple M4 CPU, with PyTorch as an optional extra.

| Checkpoint | Amount of training | Result (base game, 25 seeds x 4 rotations) |
| --- | --- | --- |
| First | 30 iterations x 32 games (960 self-play games, about 6 min) | vs 3 random 100.0% (100 games); vs 3 heuristic 56.0% (100 games) |
| Second | 100 iterations x 64 games (6,400 games, about 14 min, 8 collection workers) | vs 3 heuristic 89.0% (mean rank 1.14, 100 games); vs 3 first checkpoints 61.0% (100 games); vs 3 rollout 66.7% (48 games) |
| Continued | 100 more iterations on top of the above | vs 3 of the 100-iteration checkpoint 35.0% (100 games; equal strength would be 25%); vs 3 heuristic 90.9% (99 games) |

We first tried starting against three heuristics, but the initial policy never won a game, every reward was identical, and nothing was learned for 20 iterations. Self-play, where every game has a winner, produced a signal. Collection over 8 workers reached about 8,500 decisions/s (single process about 3,600).

## Two problems that repeated runs exposed

**An engine dead end.** A policy in training reached a decision with no legal action at all (seed 4000098): the target of Imperial Privilege's recall had disappeared later in the same turn. The fix re-checks the target at resolution time ([`d9f11a54`](https://github.com/jungcheolseung/Dune-Imperium/commit/d9f11a54)). The 7,000-game random soak had not found that state; the policy found it in 4 iterations. In a 100-game match of the continued checkpoint against three heuristics, one game also ended in an engine error ("no Spy in supply"): a Spy recalled for a placement was used by another effect in the same turn, yet the placement was still offered. Five providers with the same shape were changed to check at resolution time (`[Main pp. 11, 20]`).

**A policy loop.** Because of action pairs that can be undone (deploying and withdrawing troops, deferring and resuming a choice), an untrained policy repeated the same pair up to the 30,000-step limit. For greedy play we added a guard that hides an action already chosen in the same round on an identical observation. The same behavior then appeared during training: the first long run (150 iterations) died at iteration 41 with out of memory. The policy had learned the loop, decisions per game grew from 680 to 1,793, and the learner computed logits for 110,000 rows at once. We fixed three things: the learner computes values in pieces, 0.0005 per decision is subtracted from the terminal reward in proportion to the seat's later decisions, and training games are cut at 4,000 decisions ([`3a028fec`](https://github.com/jungcheolseung/Dune-Imperium/commit/3a028fec)).

The line between the two: if there is no legal action or applying one raises an error, it is an engine defect; if legal actions exist and the policy keeps choosing the same pair, it is a policy problem. The first was fixed in the engine rules and the second on the training side.

We also applied the same guard to the collection policy and retrained from scratch, and it failed. By iteration 25 the policy's entropy had dropped to 0.20 and decisions per game had grown to 1,301 (768 in the unguarded run). The guard changes the action distribution but the learner makes no correction for it, and the loop continued through variants that differ only in the troop count. So the guard stays for greedy evaluation only, and loops during collection are handled by the per-decision penalty and the 4,000-decision cap ([`2c03ac28`](https://github.com/jungcheolseung/Dune-Imperium/commit/2c03ac28)).

## Other work that day, and what is left

The same day we recorded a public event when the supply cannot cover a troop recruit, and ruled that recruiting takes what is available at resolution time with no retroactive top-up. Combat strength became a single value updated at every step from the Agent turn on, which raised the observation format from v4 to v5; none of the three checkpoints above can be loaded by the new engine.

The win rates above come from the engine of that moment, the base game, and a single training run. Having a checkpoint is not evidence that the AI is strong. The win rate against heuristics was close to saturating (89% to 91%), so what followed was finding more discriminating opponents and checking the accuracy of the evaluation tools. Training on expansion rules continues in [The first real training run]({{< relref path="devlog/2026-09-19-first-training.md" lang="en" >}}).

## References

- [First tournament tool and baseline](https://github.com/jungcheolseung/Dune-Imperium/commit/03687815)
- [Batched-inference self-play runner](https://github.com/jungcheolseung/Dune-Imperium/commit/ad32ea01)
- [First network, learner and checkpoints](https://github.com/jungcheolseung/Dune-Imperium/commit/01a6a181)
- [Training memory bound and per-decision penalty](https://github.com/jungcheolseung/Dune-Imperium/commit/3a028fec)
- [Reverting the guard during collection (negative result)](https://github.com/jungcheolseung/Dune-Imperium/commit/2c03ac28)
- [2026-09-06 baseline report](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/baseline-2026-09-06.md)
