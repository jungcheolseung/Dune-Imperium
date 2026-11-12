+++
title = "The play server's search AI: E3 position values and 16 worlds on Agent turns"
description = "We gave the search AI an encoder that learns only the position value (E3), and raised the worlds to 16 when the move chosen on an Agent turn is still uncertain. The server with both changes beat the previous day's server over 140 games. Two probes for a bigger leap produced nothing usable as a seat."
date = 2026-11-08T10:00:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-03"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/value-model-plan.md", "docs/search-ai.md", "docs/evaluation/2026-11-mps-value.md", "docs/worklog/2026-11.md", "docs/development-handoff.md"]
+++

## Background

For every decision the search AI builds several worlds in which what it cannot see (opponents' hands, deck order and so on) is dealt again, plays each candidate move to the end of the round, and compares the candidates by the **position value** of the result (the value network's judgment). If the position value is wrong, the search picks the wrong side no matter how much it plays. In [the November 1 entry]({{< relref path="devlog/2026-11-01-self-play-stage-one.md" lang="en" >}}) a model whose value was retrained by self-play went onto the server, but its win rate was not confirmed. This time we fixed the position value itself and then raised the number of worlds the search uses on top of it.

## Three position-value experiments (November 3)

On sets of positions whose answer is the result of playing them to the end (test sets), we measured how much better than the server model each candidate explains the answer. We went from cheapest to most expensive.

| Experiment | Round 3 vs server [95%] | Round 5 | Round 7 | Verdict |
| --- | --- | --- | --- | --- |
| E1 more training | −0.002 [−0.027, +0.025] | +0.004 [−0.011, +0.019] | −0.004 [−0.017, +0.007] | Not better |
| E2 larger value branch | −0.012 [−0.052, +0.027] | −0.020 [−0.050, +0.006] | +0.006 [−0.015, +0.026] | Not better |
| E3 encoder for the position value | +0.118 [+0.059, +0.182] | +0.089 [+0.056, +0.128] | +0.054 [+0.021, +0.088] | Better |

E3 gives the value branch an encoder of its own, so that it learns a summary for the position value instead of reading the summary the policy uses. The policy is untouched and bit-for-bit the same as the server's, and time per search decision rose by 0.5%. A second test set from 80 games on new seeds (1,920 positions) reproduced the result: +0.119 at round 3, +0.095 at round 5, +0.064 at round 7. Training more or growing the branch did not help, while a separate encoder did, so what held the value back was the summary the policy had learned.

Two E3 seats and two server-model seats played 140 games 2:2 on new seeds.

| Measure | E3 vs server | Verdict |
| --- | --- | --- |
| Games won | 53.6% vs 46.4%, +7.1 pp [−8.6, +22.9] | Within noise |
| Average place | −0.264 [−0.471, −0.057] | Confirmed |
| VP difference per game | +0.53 [−0.06, +1.12] | Within noise |

On November 4 the user decided "switch to E3", and the play server's search AI model was replaced with the E3 file (merge `08c63783`). The old file was kept for rolling back.

## More worlds on Agent turns (November 4–5)

A diagnosis with E3 showed that on Agent turns the move chosen with the default 8 worlds agreed with the move chosen with the other 24 worlds only 67.6% of the time; with 8 worlds the choice wavers. In a pilot that re-evaluated 595 Agent turns from 40 real search games with 32 worlds, a rule of "add 8 more worlds only when the 8-world choice is still open" used 12.98 worlds on average and chose as well as a fixed 16 worlds. On the Mac, though, an Agent turn went from 1.35 to 2.24 seconds and the AI's time per game rose 37%, over the threshold set in advance (+25%). So it went in as a setting the host turns on, not as the default.

- Search seat options `::turn_worlds` (always N worlds on Agent turns) and `::turn_extend` (more only while open), and the server switch `--search-turn-extend 16` (merge `7b8db790`).
- A checkbox in the server launcher, "Search AI: more worlds on Agent turns (stronger, about 1.4 times slower)" (merge `c4af58af`).

On November 5 a cumulative match measured both changes together. Two of today's server seats (E3 + conditional 16 worlds) played two of the previous day's server seats (the October 31 model + 8 worlds), with the same policy, over 140 games on new seeds (the decision rules were written down before the run).

| Measure | Today vs previous day | Verdict |
| --- | --- | --- |
| Games won | 61.4% vs 38.6%, +22.9 pp [+5.7, +40.0] | Confirmed |
| Average place | −0.364 [−0.607, −0.114] | Confirmed |
| VP difference per game | +1.05 [+0.48, +1.61] | Confirmed |

The user decided: "So the new server is stronger? Then it should replace the old one." The play server PC was restarted with 16 worlds, and the Mac's launcher setting was changed so it uses 16 worlds from its next start. On the Celeron PC, 400 steps of a game with one search seat went from 106 to 177 seconds (+67%; +37% on the Mac). A bug where the launcher did not pass this switch when using the default model was fixed at the same time (merge `a4018be8`).

## Training tools

- Value training and batched evaluation also run on the Mac's GPU (MPS) (merge `ecf3d549`). They matched the CPU within tolerances set in advance, and one epoch was 2.2–2.5 times faster. The default stays CPU, and the search seat stays on the CPU.
- The 100,000-game self-play data and the test sets were moved to observation v42 (merge `e728ecb9`), so training runs directly on the current master.

## Two probes for a bigger leap (November 8)

The user said "the AI is too weak; it needs a big leap". Two ideas were tried briefly.

- **Hand purchases to the app AI:** replacing only the search seat's card purchases with the app AI's choices made it worse. Games won −17.1 pp [−32.9, −1.4].
- **Look one move ahead at own decisions inside playouts:** we measured whether the search chooses better when, inside the playouts it plays, it thinks a little longer about its own decisions. Doing this only for its own purchases gave +0.0008 [−0.0001, +0.0018], which cannot be judged; doing it for all its own decisions gave +0.0061 [+0.0028, +0.0095], better (about +0.09 VP per decision, with the gain concentrated on Agent turns). But it takes 31 times the time, so it is only an upper bound, not something a seat can use. The value is E3's position value at the start of the next round, not a win rate.

Cheaper follow-ups (splitting where the gain comes from, or teaching the seat's moves to the playout model) were left for the user to decide.

## What is left

- The cumulative match measures E3 and 16 worlds together. E3 alone did not confirm a difference in games won.
- Whether games against people got better was not measured.
- How the search uses the position value (the average over worlds, the 0.01 flip threshold) has not been diagnosed yet.
- This search AI is the Uprising model. The search AI for the original game was [trained separately]({{< relref path="devlog/2026-11-08-original-board-search.md" lang="en" >}}).

## References

- Merge of the code that reads E3, with the stage-3 records ·
  Agent-turn world options ·
  Launcher checkbox ·
  Launcher default-model fix
- MPS training ·
  Data moved to observation v42
- Position-value plan and results ·
  Search AI description ·
  MPS measurement ·
  Work log, November
