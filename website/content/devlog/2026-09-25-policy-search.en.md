+++
title = "From 25% to 58% with the same network, by adding search"
description = "Play-time search on a model that training could no longer improve raised its win rate, and its cost fell from 405 s to 18 s a match. Feeding the search back into the network failed, and candidate and world counts were tuned to set the default."
date = 2026-09-25T14:51:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-22"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/evaluation/m10-2026-09-22.md", "docs/worklog/2026-09.md", "docs/search-ai.md"]
+++

## Where training had nothing more to teach

In [the previous post]({{< relref path="devlog/2026-09-22-evaluation-corrections.md" lang="en" >}}), training stalled again after re-adaptation, and the trained policy beat both of the repository's baselines (the heuristic and the rollout search). The next question was whether this lineage really had nowhere left to go. An exploiter experiment tested it: can a dedicated policy, trained only to beat the frozen 5081, beat 5081? If it can, the stall is just weaknesses being hidden and training against varied opponents should help; if not, 5081 is a local optimum of its own basin.

The exploiter started from 5081 and trained 2,000 iterations (5081 to 7081) against two frozen copies of 5081. That is about 25 million training rows, the same amount as 1,000 ordinary self-play iterations (the original plan, one against three for 1,000 iterations, was rejected because it had only a quarter of the rows). Results, one exploiter against three frozen 5081s over 1,400 games:

| Exploiter | Win rate (null 25%) | 95% interval | Mean rank |
|---|---|---|---|
| 6000 (919 iterations) | 26.9% | [24.5, 29.2] | 2.424 |
| 7081 (2,000 iterations) | 25.4% | [23.1, 27.7] | 2.501 |

That falls far short of the pre-declared bar (30% or more with a lower bound of 27.5% or more), and there is no trend. The exploiter's own training win rate stayed flat at 10.7–14.6% across all 2,000 iterations while entropy rose. So there is no weakness within reach of this training method near 5081. What the experiment cannot say: it rules out nothing about distant counter-strategies (such as buy-heavy decks), and the exploiter also started from 5081.

## Play-time search instead of more training

So search was added at play time instead. The existing rollout search rested all three of its parts (candidates, simulations, leaf evaluation) on the heuristic's "buy lots of cards" prior, and it won 9.4% against this network. The part that re-deals hidden information at random to make plausible states ("worlds") stayed, and the other three parts were replaced by the network.

- Candidates are the top three actions by network output.
- For each candidate, all four seats play greedy network moves to the end of the round in four worlds. Candidates share the same random numbers, which reduces comparison noise.
- The end-of-round state is scored by the value output, and a finished game is read by its actual ranking.

Before trusting it, the world generator was checked for leaks. With seat 0 at round 5, 30 generated worlds matched the true opponent hand in only 0.00–0.07 of cases and the deck order in 0.00, while the seat's own hand and the public Imperium Row matched at 1.00.

One search seat against three frozen 5081s won 58.0% [48.3, 67.7] of 100 games (null 25%), mean rank 1.740. The same file played greedily is 25.0% by definition, so the same network went from 25% to 58%. For scale, 3,000 iterations of training moved the same measure by about 6 points. This is search against greedy 5081, not search against search or against people. The seat entered the seat list as `search:<file>` ([implementation](https://github.com/jungcheolseung/Dune-Imperium/commit/4b52b9e7)).

## Cost: 405 s a match down to 18 s

The first search cost 2.0 s per decision (greedy: 4 ms) and about 405 s per match: 3 hours for 100 matches and 41 hours for the standard 1,400-match cell. Savings that do not change strength were separated from savings that trade strength.

1. **Read only the legal rows.** Profiling put 65% of the time in the network forward pass, mostly one policy-output layer. That layer has one row per action in the whole catalogue, while search needs only the values of the few legal actions of a decision. After running the trunk once and reading only the presented actions' rows, values differed from the full forward pass by at most 3.8e-6, with 0 of 1,695 decisions changing their top choice. Re-running the same 100 seeds gave identical ranks and VP in all 100 matches, and the cost fell from 405 s to 76 s a match ([change](https://github.com/jungcheolseung/Dune-Imperium/commit/45dc9a3d)).
2. **Leave effect-order decisions to the network.** Across 1,197 searched decisions, search overturned the network's top choice 22.6% of the time, but "choose the next Agent-turn effect", which takes 62.8% of the time, was overturned only 10.1% of the time. Leaving that decision to the network cut the cost 3.3 times, and a paired comparison on 300 fresh games gave −2.7 points [−10.0, +5.0] in win rate and +0.06 in rank, within noise.
3. **A cycle guard.** While widening the paired comparison, one match ran for over an hour. The search seat was repeating `switch_graft_card`, which swaps a Graft pair, forever. Forbidding a move already played in the same round with the same observation and legal list ended that match in 24 s. The guard does change results (38 of the same 100 matches differed in rank or VP, and the mean fell from 71 s to 46 s a match), but strength did not move in a paired comparison: +1 point [−3, +5].

The seat shipped this way took a median of 18 s a match (maximum 28 s) and 0.078 s per decision on 300 fresh games, and won 61.7%. Against the seat that also searches effect order (64.3%, median 45 s) the difference is −2.7 points [−10.0, +5.0], so the loss is bounded only to "within about 10 points even if real". From the original cell the speedup is roughly 22 times a match. The 405 s and the 18 s use different seed sets, so this is not a strict like-for-like comparison.

## The leaf-scale fix and the M10 table

An overnight run (September 24, 03:07–09:11, about 4,900 matches, no stalls, failures or illegal actions) exposed a flaw in leaf evaluation. Finished simulations were read on a rank ladder (100/70/40/10) and unfinished ones by the value output (targets +1 / −1/3), so the scales differed. A simulation that ended in last place was scored above every unfinished one, and the seat tried to end games early. Reading finished games on the value output's scale gave +5.2 points [+3.4, +7.1] over 1,400 fresh paired games ([fix](https://github.com/jungcheolseung/Dune-Imperium/commit/294d1433)).

## Feeding search back into the network: no effect

Since search wins, distilling its choices into the network should make it stronger without search (expert iteration v1). The current champion played greedily, and at half the decisions search evaluated the candidates and recorded values (about 180,000 labels from 1,392 matches); the network was trained to lean toward search's choice. The offline gate passed, but one distilled network against three 5081s won 25.2% and 24.4% (1,400 games each), the same as the null. Where search clearly overturned 5081's top choice, the distilled model followed search only 18.5% of the time. This looks like a representation limit: the network cannot separate the states that need overturning from similar ones. A variant that taught only the clear overturns hard got weaker (20.9%), and a search whose value head alone was refitted ranked worse. A third iteration was not run. The conclusion holds for this scale and this representation only.

## Tuning candidate and world counts to set the default

Search itself was tuned instead. The rule, written before the results: play 400 matches per variant, and confirm the best on 1,000 fresh matches.

| Variant | Per match | Win rate | Against the shipped seat (3 candidates × 4 worlds) |
|---|---|---|---|
| 5 candidates | 31 s | 72.2% (400 matches) | +9.5 points [+3.5, +15.5] |
| 8 candidates | 44 s | 70.0% | +7.3 points [+0.5, +14.0]; −2.3 vs 5 candidates |
| 2-round horizon | 61 s | 59.0% (200 matches) | −2.5 points; stopped at 3.4× the cost |
| 5 candidates × 8 worlds | 59 s | 75.2% | +12.5 points [+6.5, +18.5] |

On 1,000 fresh matches, 5 candidates won 66.1% (against 62.0%, +4.1 points [+0.1, +8.1]) and 5 × 8 won 76.1% [73.7, 78.7], +10.0 points [+6.4, +13.7] over 5 candidates and +14.1 points [+10.5, +17.7] over the shipped seat. 8 candidates were no better than 5, so that axis counts as saturated. 16 worlds won 78.3% on the same matches, +2.2 points [−1.6, +5.8] over 8 worlds; that missed the declared rule (lower bound above 0) at twice the cost, so the default stayed at 8 worlds. The `search:` default therefore became 5 candidates × 8 worlds (about 58 s a match) ([default change](https://github.com/jungcheolseung/Dune-Imperium/commit/3ce189b7)).

The M10 table for the new default seat against every baseline and the previous champion (one search seat against three opponents, null 25%):

| Three opponents | Matches | Search win rate [95% interval] |
|---|---|---|
| Random | 100 | 100% |
| Heuristic | 300 | 99.3% [98.3, 100.0] |
| Rollout | 200 | 89.5% [85.0, 93.5] |
| Previous champion 2081 | 300 | 81.3% [77.0, 85.7] |
| Current champion 5081 | 1,000 | 76.1% [73.7, 78.7] |

In a search-versus-search 2-versus-2 mirror, the new default also beat the earlier seat (400 matches, 60.0% to 40.0%).

## What remains open

- Every table is one search seat against three greedy opponents. Search against search, or against people, was not measured at scale.
- These numbers were measured under the rules before the full rules audit and must be measured again afterwards (see [the audit post]({{< relref path="devlog/2026-09-27-card-audit.md" lang="en" >}})).
- Three variants were compared on the same 400 matches and the best chosen, so the evidence is the 1,000-match confirmation.
- Connecting this search seat to the play screen is covered in [an October post]({{< relref path="devlog/2026-10-06-app-search-ai.md" lang="en" >}}).

## References

- [Exploiter experiment record](https://github.com/jungcheolseung/Dune-Imperium/commit/65888d41)
- [First measurement of policy-guided search](https://github.com/jungcheolseung/Dune-Imperium/commit/cb843d71)
- [Search cost summary](https://github.com/jungcheolseung/Dune-Imperium/commit/81be064e), [cycle guard](https://github.com/jungcheolseung/Dune-Imperium/commit/c50614f8)
- [Expert iteration v1 merge](https://github.com/jungcheolseung/Dune-Imperium/commit/30e9da9c)
- [Sixteen-world confirmation](https://github.com/jungcheolseung/Dune-Imperium/commit/fe423fd2)
- [M10 evaluation collection, sections 11–16](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-09-22.md)
- [Search AI description](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/search-ai.md)
