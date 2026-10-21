+++
title = "Rejecting the rank reward and fixing two in-training evaluation bugs"
description = "The rank reward was re-checked against a control run and rejected, a checkpoint ladder gave training stalls a second reading, and two bugs in the in-training evaluation were fixed: repeated seeds and reading the wrong model's row."
date = 2026-09-22T09:02:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-20"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/evaluation/m10-2026-09-22.md", "docs/worklog/2026-09.md", "docs/lessons.md"]
+++

## Measuring training that looked stalled

The first network training run (September 17–19) is covered in [the previous post]({{< relref path="devlog/2026-09-19-first-training.md" lang="en" >}}). A full audit of the printed icons then corrected rules (September 20, action codec v105 to v107), so the checkpoints were carried over to the new rules. The starting point is the checkpoint trained to iteration 2,081 at learning rate 1e-4 (2081 below). In-training evaluation made learning look stalled, and this post records re-checking that reading.

The first change was to the measuring instrument. Until then, 2–5 point differences were judged from four-player mixed tournaments of about 400 games, and the next measurement showed that sample cannot tell such differences apart.

- The tournament CLI now writes one row per match (seed, configuration, rank and VP per seat).
- A script compares two agents with a paired test, giving bootstrap 95% intervals clustered by seed. The seat rotations of one seed are the same game with the same leaders, decks and first player, so they count as one cluster.
- The default design is a 2-versus-2 mirror (A, B, A, B).

Three arms trained for 200 iterations with the same settings and different seeds were compared with each other and with the starting point over 600 mirror games. Arm against arm, win-rate differences were 0.3–2.3 points; against the starting point they were +1.7, −5.0 and +5.3 points, with mixed signs, and pooled +0.7 points [−5.2, +6.6]. This design resolves win-rate differences only to about ±7.7 points. The required number of games grows with the square: about 1,400 games for 10 points, 5,700 for 5 points, and 15,800 for 3 points (4.4 hours per cell). Every earlier A/B was below that line.

## The rank reward looked like a success at first

The training reward is winner-take-all (+1 for the winner, −1/3 for the others). A single win or loss carries about 0.8 bits per seat, while the finishing order the engine already computes carries about 2 bits. So a `--rank-rewards` option was added that spreads the order linearly over [+1, −1] (off by default).

Training 1,000 iterations from 2081 with this option clearly beat the starting point: +17.9 points [+12.7, +22.9] over 1,400 mirror games, and 32.4% for one network against three copies of the starting point (null 25%). But that was "rank reward against the start", not "rank reward against the normal reward".

The next day a control run was trained for the same length with a command identical letter for letter except for that option. That the option took effect was confirmed from the value loss (0.393 against 0.266).

| Comparison (1,400 games each) | Win rate | Mean rank | VP margin |
|---|---|---|---|
| Rank reward vs control | +2.9 points [−2.3, +8.0], within noise | −0.072 [−0.136, −0.009] | +0.239 [+0.092, +0.386] |
| Rank reward vs start | +17.9 points [+12.7, +22.9] | −0.325 | +0.830 |
| Control vs start | +19.1 points [+14.3, +24.0] | −0.295 | +0.727 |

The rank-reward arm being slightly ahead on rank and VP margin is expected, since it optimises rank; winning is what counts, and that is the win rate. The control rose by the same amount, so the gain came from 1,000 iterations of training, not from the reward. The rank reward was rejected for lack of effect. Behaviour did not change either (deck 9.25 to 8.96 cards, purchase rate 14.0% to 9.1%).

## The ladder: up, then flat again

From the end of the control run (3081), another 2,000 iterations with the same settings reached 5081, and the intermediate checkpoints were chained together with 1,400 mirror games each.

| Interval | Iterations | Win-rate difference [95% interval] |
|---|---|---|
| 2081 to 3081 | 1,000 | +19.1 points [+14.3, +24.0] |
| 3081 to 4000 | 919 | +3.0 points [−2.1, +8.1] |
| 4000 to 5081 | 1,081 | +1.6 points [−3.3, +6.4] |
| 2081 to 5081, cumulative | 3,000 | +15.0 points [+9.7, +20.1] |

The rise sits entirely in the first 1,000 iterations after the rule fix; the following 2,000 are within noise. The circumstantial evidence points to re-adaptation to the rules. 2081 had been trained under the old rules, so when it was carried over, the rows of the policy output for new actions started at zero. Of the 295 rows that were all zero, 228 became active by 3081, in the same interval where the rise is concentrated. That new rows came alive does not mean the rise was due to them, and causation was not tested.

This corrected two readings from the day before. Right after the control run, the notes said "the existing setup still learns" and "the earlier stall may have been a measurement limit". The ladder suggests that after re-adaptation it stalled again at 2–3 points or less per 1,000 iterations. Two points can only say "it changed by this much"; saying "it keeps rising" or "it stopped" takes three or more.

## Two bugs in the in-training evaluation

The in-training evaluation (`--eval-every`) is a tripwire, not a judging tool. Two bugs turned up during this period.

1. **Repeated seeds.** The evaluation function did not pass a start seed, so every evaluation replayed seeds 0–24. This applies whatever the opponent: the evaluations of one run were not a sequence of samples but repeated measurements of the same small sample. Each evaluation now uses its own non-overlapping seed block (starting at 1,000,000) ([fix](https://github.com/jungcheolseung/Dune-Imperium/commit/afb30642)).
2. **Reading the wrong model's row.** The evaluation read the first summary row whose name starts with `checkpoint:`. When the opponent is also a checkpoint, both names share that prefix, and the summary is sorted by name, so it read the row of the opponent that sorts first, a row that merges three seats. The reported value was (1 − actual win rate) / 3: correct at a tie, and falling as the model gets stronger. A 21.3% recorded by the in-training evaluation reproduced as 36.0% when the same input was run through the tournament CLI, and (100 − 36.0) / 3 = 21.3. The fixed evaluation gives the CLI's 36.0% on the same input ([fix](https://github.com/jungcheolseung/Dune-Imperium/commit/fe2196c8)).

The two bugs reached different scopes. Repeated seeds affected every in-training evaluation; the wrong-row read affected only evaluations against a checkpoint opponent. The default opponent, the heuristic, shares no prefix, so past numbers against it stand. All checkpoint-opponent evaluations of this period (the three arms, the rank reward, the control, the 2,000-iteration run) were inverted.

What hid the rise of the rank-reward run was not the repeated seeds but the second bug. That run was recorded as nearly flat at 24.5%, close to (1 − 0.324) / 3 = 22.5%. The message of the commit that fixed the repeated seeds names them as the cause of the hidden rise. The commit was not rewritten; the correction was left in the work log and with the second fix. The conclusions in this post all come from tournaments and paired comparisons run after training, so neither bug affects them.

## Other things checked

- **The policy hardly buys cards.** The starting deck of 10 ends at 9.94 cards; there are 15–21 decisions per game where buying is legal and it buys in 14.0% of them (the heuristic: 94.3%). Comparing the model with a variant that overrides only the buy decisions over 1,400 games each, always buying gave −17.0 points [−22.0, −12.1] and buying half the time gave −11.0 points [−15.9, −6.0]. Buying was not an improvement direction for this policy. That is the result of forcing purchases on a policy that does not know how to use the cards, so it does not mean deck-building itself is weak.
- **Against the existing baselines.** Against three heuristic opponents the win rate saturated at 89–92%, and the search-style baseline won 9.4% (96 games) against three checkpoints. In other words, the repository had no opponent left to teach this policy anything. This leads into [the next post]({{< relref path="devlog/2026-09-25-policy-search.md" lang="en" >}}).
- **A side improvement.** Storing only the presented actions in compressed form instead of the full-width legal set reproduced a resumed run to six decimal places and cut a full-expansion iteration from 50.5 s to 15.2 s (same Mac mini, with other programs left open).

## What remains open

- All conclusions come from one lineage and one training seed. The rank reward was tried in one configuration only.
- The re-adaptation reading of the ladder is circumstantial. No experiment isolated the effect of the newly active rows.
- The 95% interval of 1,400 mirror games is still about ±5 points, so differences of 3 points or less remain indistinguishable.
- These numbers and checkpoints predate the full rules audit. That audit is covered in [the card and board audit post]({{< relref path="devlog/2026-09-27-card-audit.md" lang="en" >}}).

## References

- [Rank-reward option](https://github.com/jungcheolseung/Dune-Imperium/commit/df2e9ced)
- [Rejecting the rank reward with a control](https://github.com/jungcheolseung/Dune-Imperium/commit/6b96e510)
- [Per-match rows and the paired comparison tool](https://github.com/jungcheolseung/Dune-Imperium/commit/3da40c2f)
- Evaluation fixes: [seed blocks](https://github.com/jungcheolseung/Dune-Imperium/commit/afb30642), [reading its own row](https://github.com/jungcheolseung/Dune-Imperium/commit/fe2196c8)
- [M10 evaluation collection](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-09-22.md)
- [Lessons log](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/lessons.md)
