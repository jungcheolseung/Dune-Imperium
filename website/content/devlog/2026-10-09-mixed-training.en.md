+++
title = "Mixing in opponents, and trying to learn from search"
description = "A control run on whether training against the app AI beats pure self-play, a search-seat reversal that did not reproduce on new seeds, the re-adaptations that followed, and a distillation experiment stopped before its verdict."
date = 2026-10-09T23:28:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-07"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/evaluation/m10-2026-10-07.md", "docs/evaluation/m10-2026-10-09.md", "docs/evaluation/exit-v2-2026-10-08.md", "docs/worklog/2026-10.md", "website/content/posts/learning-with-opponents.md"]
+++

## What was to be checked

The L3 retraining in the [previous entry]({{< relref path="devlog/2026-10-06-app-search-ai.md" lang="en" >}}) changed two things at once. Half of the training games were against the app AI on Hard (a rule-based AI ported from the computer opponent of the official digital edition (Steam)), and the network was adapted to the play screen's full rule set. When the result improved, the credit could not be split. This entry covers the control run that separates them (M versus S), the recheck of an opposite result seen on search seats, the two follow-up trainings (X and Y), and an attempt to teach the network the choices of search (ExIt v2). The detailed numbers and conditions of the first two experiments are in the technical article [Does changing the training opponents make the AI stronger?]({{< relref path="posts/learning-with-opponents.md" lang="en" >}}); this entry follows its final reading and only outlines the flow.

## M versus S: two runs that differ only in opponents (October 7)

From the same starting network (8081) with the same rules, settings, and seeds, only the opponent mix differed, and each run trained 1,000 more iterations. In M, 16 of each collection's 32 games were two learner seats against two app AI Hard seats; in S, all 32 were self-play. The app AI's moves are not training data, so M has 96 learner seat-games per iteration and S has 128. It is a comparison at equal iteration count, not at equal data or time. Both runs also went through re-adaptation to the new rules (the card-audit corrections and the ban on playing an Intrigue with no effect). The machine was a Mac mini (M4, 16 GB); M took 4 h 24 min and S took 3 h 53 min.

Judging followed rules written before the results, and every cell used seeds from 3,400,000 that training never touched. The in-training evaluation (one network seat against three app AI seats, 100 games) has a standard error of 4–5 points, and even 19 iterations after the same start the two runs differed by 17 points on it. So it was used only as a warning signal and never for the comparison.

| Comparison (network playing alone) | Games | Result (95% interval) |
| --- | ---: | --- |
| M vs starting network 8081 | 1,400 | +13.1 points [+8.0, +18.1] |
| S vs starting network 8081 | 1,400 | +4.9 points [−0.3, +9.9] |
| M vs S | 2,800 | +5.9 points [+2.2, +9.5] |

Played directly, the run with mixed opponents was ahead, even though it used a quarter less training data per iteration than S. The result is read only within this starting network, rule set, opponents, and training length.

## The search-seat reversal did not reproduce

Putting the same networks into the search AI against three app AI Hard seats gave the opposite result. On 200 games over the same 50 seeds, search with 8081 won 79.5% and search with M won 69.0%, a difference of −10.5 points [−17.5, −3.5]. By the declared rule the play server's network was left alone, and three explanations were noted: the value target may have been mixed, the policy may have tilted toward beating the app AI, or the sample may have been small.

Re-measuring on 50 new seeds gave M − 8081 = +1.0 points [−8.0, +10.0], and by the criterion (the point estimate must again be below zero on new seeds for the reversal to stand) the reversal did not hold. Pooled over the three groups of seeds, 150 in all, it is −0.5 points [−5.8, +4.7]. The win rate of the same 8081 search moved between groups as 79.5%, 68.0%, and 63.8%, so a single 50-seed point estimate has to be read with a swing of about ±8 points. The explanation that fits best is that the sample was small. The analysis that splits policy from value was to be run only if the reversal held, so it was skipped, and only the option for it (`search:<policy file>::value=<value file>`) was merged.

## X and the play server's network (October 8)

X, trained 1,000 iterations further from M, was within noise of M in network-only play: +2.0 points [−3.3, +7.3]. Nearly all the gain came in the first 1,000 iterations. With search it looked different. X's search first beat 8081's search by +14.1 points, but 8081 had been unusually low in that group of seeds, so it was re-measured on 50 new seeds: +8.5 points [+0.5, +16.5], and +11.3 points [+5.3, +17.3] over the combined 100 seeds (399 pairs). X's search won 78.0%, 77.9%, and 78.0% in the three groups. By decision, the play server's search network became X on October 8. Older saves continue on their original network, and the new network applies to new games after a server restart. The lesson from this experiment is that a gain in network-only strength and a gain in search-seat strength do not necessarily move together.

The same day an error in the hidden states the search AI imagines was also fixed. The finished Conflict deck is, from the top, 1 level-I, 5 level-II, and 4 level-III cards, and the unused level-I and II cards go back to the box face down (`[Main p. 4]`). The level at each depth is public, but which cards were boxed is not. The imagined states had been shuffling only the cards left in the deck, so the deck's and the box's cards of the same level are now pooled and dealt again. Because this fix brings the AI in line with a rule, it was merged without a measurement, by decision, and search measurements before and after it are not compared directly. A turn-end engine defect found by a search playout in this period is described in the [turn-end entry]({{< relref path="devlog/2026-10-09-turn-end.md" lang="en" >}}).

## Y: re-adapting after the rules changed (October 9)

X had been trained on codec v139, and the pause before a reveal (v140) and the Conflict-end window (v141) came later. Loading X under v141 kept every action and added none. It played without trouble, but it had never trained on the changed timing of decisions. Training 800 more iterations from X produced Y (same settings, half of the games against the app AI, 19:25–23:03, about 16 s per iteration, no truncated games).

Y against X, both on v141 with seeds from 6,000,000, over 1,400 games: win rate +10.1 points [+5.0, +15.3], rank difference −0.159 [−0.226, −0.095], score margin +0.42 [+0.24, +0.61]. It cleared the declared criterion (lower bound above zero), so network-only strength improved with re-adaptation. A large rise within the first thousand iterations after a rule change had been seen in earlier re-adaptations too. But this is network-only strength. The search comparison (Y's search against X's search) had not been measured, and as seen above the two can diverge, so the play server's network stayed X at that point. As a by-product of the run, a defect was found and fixed the same day in which the app AI raised a negative-spice error when it priced a Spice Refinery trade under the Navigation Chamber's spice discount. Rule behaviour did not change, and since the run used the engine from before the fix, the app AI answered a few of those decisions randomly.

## Teaching the network what search chooses: ExIt v2

The next question was that gains in network-only play do not carry over well to the search seat, while search adds a great deal to the network. Against three app AI Hard seats, search over X wins 78%, while the network alone averaged around 44% in in-training evaluation. The first expert-iteration attempt (September 24), which teaches the network the choices of search, showed no gain. It was not that the target was weak, but that the student failed to learn or generalize. The target already pointed at the search's choice in 89% of the decisions search clearly flips, yet the student followed it in only 18.5% of unseen games.

The second design changed these things.

- The teacher is search over X (5 candidates × 8 imagined hidden states). The positions use the whole play rule set with the draft, and half of the games are two X seats against two app AI seats. Only X seats' decisions are labelled.
- The students are X, and X widened with a slot input that reads the identities of the Row and Conflict cards.
- Agreement on trained games and on unseen games is measured side by side, to tell a generalization problem from a lack of training.
- The gates were fixed before results. With each student playing X 2:2 over 1,400 games, the run stops unless the best student is at least +2.5 points, because a rule of "best of four above zero" would pass 94% of the time even with no effect.

A pilot of 32 games took 15.8 minutes on 8 worker processes, about 122 games an hour, with about 134 labels per game. Search flipped the network's first choice in 45.5% of decisions, 35.9% were clear flips, and in 24.5% the two halves of the imagined states chose different moves. That is label noise similar to the first attempt, and doubling the worlds did not reduce it. Where search differed from the network was concentrated in the Agent turn's space and card choices.

Collection stopped at 510 games (about 68,000 labels) starting from seed 5,000,100. The rules had moved to v141 in the meantime, so the collected data's action numbering no longer matched, and it was decided to finish at this point and retrain later. The judging stage was not run. So there is no result that this attempt made the AI stronger, and the declared judging rules remain unexamined. The code (collection, training, diagnostics) was merged. To continue, one would either finish collection on the old engine or restart from a pilot under the new rules.

## References

- [Does changing the training opponents make the AI stronger? (technical article)]({{< relref path="posts/learning-with-opponents.md" lang="en" >}})
- [Mixing opponents and follow-ups (M vs S, the reversal recheck, X's search check)](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-10-07.md)
- [Re-adapting X to v141 (Y)](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-10-09.md)
- [Expert iteration v2: design, pilot, and stop](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/exit-v2-2026-10-08.md)
- [ExIt v2 code merge](https://github.com/jungcheolseung/Dune-Imperium/commit/0747caec)
- [Searching with a separate policy and value file](https://github.com/jungcheolseung/Dune-Imperium/commit/38d38fa3)
- [Dealing boxed Conflict cards by level in the search AI's imagined states](https://github.com/jungcheolseung/Dune-Imperium/commit/717f88be)
