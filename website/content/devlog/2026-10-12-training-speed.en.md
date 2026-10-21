+++
title = "Measuring and reducing collection overhead"
description = "Game collection takes 93% of a training iteration. Computing only the legal action rows and dealing games evenly across workers cut it, and the engine's state-copy and app AI lookup costs were measured separately."
date = 2026-10-12T23:43:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-12"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/worklog/2026-10.md", "docs/evaluation/engine-throughput-2026-10-12.md"]
+++

## Measuring the bottleneck first

A re-adaptation run trains around 800 iterations. The question was whether training could go faster and where the biggest bottleneck was, and the first step was measuring before changing anything. The measurement used the re-adaptation settings (network Y, one worker process playing 8 games).

- 93% of an iteration is game collection. The rest is the training update.
- Eight self-play games took 11.7 s, of which the network took 7.7 s (66%).
- Eight games against the app AI took 16.6 s: 6.3 s for the network and 5.5 s for the app AI.
- Nearly all of the network time was computing all 33,986 rows of the policy head and sampling over a 34,000-wide distribution. A decision has about 5 legal actions on average.

## Two changes

1. **Compute only the legal actions.** The sampling path runs only the shared trunk, then reads only the head rows for the union of legal actions in the batch. The probability distribution equals the masked softmax of the full computation restricted to those rows. A test checked 80 real batches within 1e-6, and a review checked 358 batches over 12 games with every expansion on at a relative error of 4e-6 or less. The greedy path used for frozen-checkpoint opponents is unchanged.
2. **Deal games evenly.** Games with the app AI were the odd-numbered ones, so dealing by position gave worker processes 1 and 3 only app AI games. Games are now dealt in turn within each seat composition (seats per policy).

## How much faster

Collecting 32 games on 4 worker processes, alternated three times under the same conditions, went from 19.2–20.5 s to 9.1–9.5 s every time. This was measured while another training run used the same machine. By game type, eight self-play games went from 11.7 s to 4.7 s and eight app AI games from 16.6 s to 9.5 s. The merge for this unit is `317b1b99`.

It was then re-measured on a quiet machine. These are medians of 9 runs each, with 4, 5, 6, 8, and 10 worker processes alternated over three passes on the seeds of the same three iterations.

| Worker processes | 4 | 5 | 6 | 8 | 10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Collection time (s) | 6.78 | 6.86 | 6.69 | 6.31 | 6.64 |
| Worker memory | 2.0 GB | — | — | 3.9 GB | 4.9 GB |

Eight processes were 7% faster (about 6 minutes over 800 iterations), but the memory doubled and the machine is shared with other work, so 4 stayed. Each worker plays its games in lockstep, so collection ends when the longest game ends, and adding workers does not shorten that game. The 9.1–9.5 s above is therefore a value under load; on the quiet machine 4 workers took 6.8 s. None of this guarantees the same speed-up on another machine or under another load.

After the reduction, the new bottleneck was the engine (rule progress and building observations) at 76% for self-play, and the app AI at 46% for games against it.

## Follow-up engine investigation and improvements

Aiming at the new bottleneck, engine speed was investigated on a separate branch. It was measured on one CPU thread in another Linux environment (WSL), finishing games with an older network migrated there, so it is not compared directly with the Mac measurement above. In eight self-play games there were 54,203 state dataclass copies, 28,922 game-state checks, 14,889 seat-state checks, and 145,942 rebuilds of the Agent-effect context. In games against the app AI, the app AI's judgement was about 57% of the time, and it rebuilt card information objects millions of times.

Two things were changed.

- **State copy (`2b417f51`).** A copy function is generated once from the declared fields and the engine uses it. Invariant checks in the constructor and the normalization of the public hand still run. New fields are included automatically, and unknown fields or unusual constructors fall back to the standard copy.
- **App AI card-information lookups (`aa355d4a`, `adf6785a`).** The list of immutable card information is normalized once, and card-ID parsing and card-object lookup are reused through pure-function caches capped at 4,096 entries. Score evaluation and ability objects are not cached. The first cache was a mutable module-level dict that broke the global-state audit, so it was changed to a pure-function cache with the audit test kept.

Before comparing times, it was checked that the runs are the same. On two self-play games and four games against the app AI, the observations, the legal sets offered, the actions, and the final full-state hash matched between the baseline and the new engine, and the hashes after loading saves with the basic, CHOAM, and all-options setups and playing on matched too. The timing tool (`compare_engine_collection.py`) collects with the same network and seeds on two source trees, alternating, and refuses to compare times if the results differ.

These are the median time reductions on real collection, from the same 8 games alternated three times each.

| Condition | Reduction |
| --- | ---: |
| Self-play, 1 worker process | 1.2% |
| Half self-play, half against the app AI, 1 worker process | 13.0% |
| Same mix, 2 worker processes (pool start and transfer included) | 11.6% |

The effect on self-play collection was nearly nil. Timing the copy functions alone, the game state went from 38.48 to 27.52 microseconds and the seat state from 30.86 to 17.22, but that is a function's cost and not a saving in the whole collection. A 15.7–17.7% reduction in app AI collection from a temporary stand-in during the investigation was not carried over as an effect on the whole either. At merge, on the Mac with the training settings unchanged (network Y, 32 games, 4 worker processes, all modules and the draft, half against the app AI, iterations 101–103), the median collection time with sources from before and after alternated went from 8.65 s to 8.08 s (−6.6%; 7 of 9 runs were faster when paired by iteration). A browser was using the machine a little at the time, so the spread is wide. This merge is `67359032`.

### An approach not adopted

Emptying PlayerState's `__post_init__` to remove the checking cost was not used, because it changed the observations. That function normalizes the public hand as well as checking. An experiment that kept the normalization and dropped only the checks was meant to separate the cost and was not adopted.

## Not pairing runs by seed across the change

The first change (`85a51097`) altered how sampling consumes random numbers and how games are dealt. So the same seed and the same number of worker processes gives different games than before it. Runs and census numbers from before and after are not paired by seed. The engine's state-copy and app AI lookup improvements, in contrast, did not change behaviour, and the match checks above produced the same games.

## References

- [Training bottleneck investigation and engine improvement measurements](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/engine-throughput-2026-10-12.md)
- [Work log 2026-10 (collection speed, worker-count re-measurement)](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/worklog/2026-10.md)
- [Compute only legal actions and deal games evenly](https://github.com/jungcheolseung/Dune-Imperium/commit/85a51097)
- [Collection speed-up merge](https://github.com/jungcheolseung/Dune-Imperium/commit/317b1b99)
- [State-copy improvement](https://github.com/jungcheolseung/Dune-Imperium/commit/2b417f51)
- [Engine speed improvement merge](https://github.com/jungcheolseung/Dune-Imperium/commit/67359032)
