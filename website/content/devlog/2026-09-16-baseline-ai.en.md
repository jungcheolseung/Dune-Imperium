+++
title = "Engine defects and measurement traps found while refining the baseline AI"
description = "While re-measuring the heuristic and rollout AIs on the expansion-enabled engine and reworking the board-space score table, the same comparisons exposed 13 engine defects and several mistakes in how we measured."
date = 2026-09-17T12:36:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-09"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/evaluation/baseline-2026-09-10.md", "docs/evaluation/baseline-2026-09-16.md", "docs/evaluation/throughput-2026-09-10.md", "docs/worklog/2026-09.md"]
+++

## Re-measuring the baseline on the expansion engine

Before seriously training the network we needed to know how strong the reference AIs were on the current engine. The September 6 baseline was measured on an engine without expansions; since then three expansions and dozens of rule rulings had arrived. This entry covers the work from the evening of September 9 to the 16th. There are no commits on the 12th to the 15th.

First we made the heuristic and rollout AIs value Immortality. The heuristic gave every Tleilaxu card the same score and every research branch the same score, and the rollout position value had no Immortality term. Cards now differ by printed specimen cost and per-effect adjustments, and research spaces by the printed bonus of the destination. In a 2:2 comparison against an AI with the old score table frozen (`--immortality`, 400 seeds times four seat rotations, 1,599 matches), the new table won 27.9% (mean rank 2.403) and the old one 22.1% (2.597). Equal AIs would split 25%, so this is +2.9 points.

We also closed gaps in the verification tools. The check that scrambles hidden information did not touch the Conflict, Skill, Tleilaxu and Twisted decks; this is fixed, with the Conflict deck scrambled within each tier because the tier on the card back is public. The card-conservation check gained the 18 Tech tiles, 14 Skills and 7 Commanders. The training loop was wired to accept expansion rule options. We compared 88 items marked unfinished in 7 planning and audit documents against the code: 42 were genuinely open and 46 were outdated lines in the documents.

When the baseline was re-measured on expansion rules on September 10, the heuristic's win rate against 3 random AIs was 84.0% over 100 games (95.0% before) and 89.2% over 800 games. Rollout against 3 heuristics went from 48.0% to 43.0% (100 games). We did not establish the cause at that time; that the score table had never been tuned for the wider action space became the next candidate. The re-measurement also found a defect in the rollout's imagined worlds: they shuffled the bottom Secret Project tiles that Kota Odax's owner had already seen, and 5 of 60 games died.

## Throughput fell by 1.60x, and why

The same tournament command went from 59.25 games/s to 38.71 games/s. The first suspect was the "try the effect first to see if it can resolve" check that arrived with a rules ruling (OQ-057) and its cache. That was a suspect picked by reading the code and written down as the cause before measuring.

Alternating three trees showed the regression was real: 1.60x slower with 8 workers and 1.63x with one process, and Python calls per step, a deterministic metric, rose from 1,218 to 1,849 (1.51x). It was larger with a single process, which rules out worker start-up or import cost. The suspect check turned out to be minor: 28,634 of 40,250 calls (71%) hit the cache, and it accounted for 2.7% of total time. The real cause was spread across an engine that now carries four expansions. We fixed three places.

| Fix | Wall-clock gain with 8 workers |
| --- | --- |
| A Protocol check asking the agent's kind on every decision, now once per seat | 1.2% |
| Validation that scanned expansion zones on every state copy even in games with expansions off, now skipped by a module flag | 3.1% |
| Six legal-action providers that rebuilt context on every call although the ruleset flag alone could answer | 2.4% |

Together that is 6.7% with 8 workers and 7.1% with one process. The commit message of the first fix said "0.62 s of 0.9 s", but that is CPU time, and with 8 parallel workers it is an eighth of that in wall-clock, so it overstated the gain. We did not rewrite the commit and corrected it in the evaluation document. So most of the regression was not recovered in this period, and because absolute speed of the same tree swings by up to 20% between runs, we only compare trees by alternating them within one run.

On September 16 we profiled the self-play path used by training for the first time. The observation encoder was the biggest item at 31%; rewriting it to produce byte-identical output cut collection wall-clock by 16.1% on the base game and 17.9% with all expansions. Having the engine reuse the legal-action list the runner had just built, instead of enumerating it twice, made a single-process heuristic mirror 13.6% faster.

## The board-space score table and the "-5.6 points"

In the heuristic's score table 21 of the 23 board spaces had the same default, so 11% of space-choosing decisions were ties. Pricing each space's printed yield with one conversion table and subtracting the printed cost gave +4.9, +5.1 and +5.0 points on three independent seed blocks for the base game with CHOAM (2:2 mirror). With all expansions on, though, it was -5.6 points, and an attempt to also raise expansion spaces was far worse at -34 points.

Splitting the expansions apart changed the sign.

| Expansions on | Win-rate difference of the new table |
| --- | --- |
| Immortality only | +16.0, +17.0 points |
| Bloodlines only | +3.8 points |
| Bloodlines and Immortality | +9.2 points |
| Bloodlines and Tech Module | -6.6, -4.8 points |

The -5.6 was an average of two opposite effects. Only the Tech Module disliked the table, and the reason is printed in the rules: a tech tile can be bought only on a turn when the Agent goes to a Landsraad space (`[Bloodlines p. 7]`), and the new table put the cheap Landsraad spaces at the bottom, so tiles went unbought (tech tiles per seat fell from 2.48 to 1.16). So at first we used the old two-space table only with the Tech Module.

On September 11 we tested five variants of the tech-tile value table (noise or worse, worst -4.8 points) and 22 cells of a Tech-specific space table (all lost to the two-space table), and rejected all of them. What did turn up was that the top three spaces (Imperial Basin, Secrets, Arrakeen) were too high. On the 16th we lowered and raised spaces one at a time, in this order:

1. A table with the three spaces at the floor (0.3) beat the first conversion table; pitting demotion levels 0.45, 0.5, 0.6 and 0.75 against each other, we adopted 0.6.
2. Lowering spaces one at a time, only Imperial Basin at the floor won on every axis, and lowering Arrakeen lost. A table with Imperial Basin 0.3, Secrets 0.6 and Arrakeen 1.2 beat the 0.6 table (base +17.2, +16.8 points; CHOAM +16.2, +12.7).
3. Deliver Supplies to 0.4 (+2.6 to +9.6 points on all axes) and Espionage to 0.6 (+2.7 to +8.8).
4. A final 32 cells that undid the lowered spaces or raised low ones were all losses or noise, so we judged the table a local optimum in both directions and closed the work.

Ties among cards that reach the same space were handled separately. We adopted a rule that, after the space is chosen, picks the cheapest card reaching it (+1.4, +0.4 points; +3.6 with all expansions), and a rule that breaks ties in faction choice, trashing and same-cost buys only inside the set the score already ties (+5.1 to +9.1 points on every axis and both seed blocks).

## The rollout AI and the final baseline

As the heuristic got stronger the rollout's edge shrank, because it picks candidates with the same score. On the base game, rollout against 3 heuristics fell from 43.0% to 28.0% (100 games; with all expansions, 60 games, 41.7% to 31.7%). The cause was sampling noise in the playouts. The default (6 candidates, 2 imagined worlds) scored 28.0%, but with the same budget of 12 playouts per decision, 3 candidates and 4 worlds scored 54.0%, 2 candidates and 6 worlds 49.0%, and 4 candidates and 3 worlds 48.0%. Raising candidates alone to 12 gave 34.0%, and looking two rounds ahead was worse at 17.0%. What decided a move was the number of imagined worlds, not the number of candidates, and six candidates compared over two worlds was especially noise-prone. Common random numbers, which share randomness across candidates within one imagined world, raised even the old default to 50.0%. With a standard error of about 4.5 points per 100-game cell the same-budget variants could not be told apart, so a 200-game final chose 4 worlds, 3 candidates and common random numbers (55.0%) as the default. The doubled budget of 8 worlds, 3 candidates and common random numbers (60% over 100 games, about 150 ms per decision) is a separate strong setting, which we also offered as a seat type on the play server.

The final baseline is the same 12 cells re-measured with the same commands (Apple M4 with 10 cores, 8 workers, leader rotation, no illegal actions or failures).

| Cell | Sep 6 (pre-expansion engine) | Sep 10 midday | Sep 16 |
| --- | ---: | ---: | ---: |
| 1 heuristic vs 3 random, base, 100 games | 95.0% | 84.0% | 96.0% |
| 1 heuristic vs 3 random, base, 800 games | | 89.2% | 98.4% |
| 1 heuristic vs 3 random, CHOAM, 800 games | | 84.4% | 98.6% |
| 1 rollout vs 3 heuristic, base, 100 games | 48.0% | 43.0% | 54.0% |
| 1 rollout vs 3 heuristic, all expansions + promos, 60 games | | 41.7% | 60.0% |
| heuristic four-seat mirror (base+CHOAM 400 games, all expansions 200) | 25.0% | 25.0% | 25.0% |

Mirrors came out at exactly 25.0% with mean rank 2.50, so we kept confirming there is no seat bias. The binomial standard error of a 100-game cell is about 5 points, so small differences between 100-game and 60-game values in the table cannot be told apart.

## Thirteen engine defects found by the A/B runs

Changing a score table takes the AI into states it never visited before. The comparisons and soaks of this period found 13 defects, all fixed: ten in the engine rules and three in the part of the rollout that re-deals hidden information.

- A multi-icon Agent box dead end: when the first icon recalled the only Agent, the copy's recall icon had nowhere to go and no legal action remained (Ghola grafted to Steersman), found in one of 1,599 comparison matches.
- Retreating with more than 12 units, because a Commander is a separate component from the 12 troops and units can reach 19 (action codec v104).
- Graft partner candidates all filtered out so no legal action remained (a card with a Spy icon whose cost recalls that Spy).
- Offering to withdraw more units than are actually in the Conflict.
- Ghola's borrowed Agent box not being read by payment and discard handling, so it charged the wrong cost.
- Graft partner judgment still counting a Spy that Infiltrate had recalled.
- Cases with no rule in the official documents, ruled on in the project: a contract icon left in the market with no token to take (OQ-059), and an Influence choice vanishing when every faction track is at 6 (OQ-060).
- Reveal strength tracking left over after the Conflict became empty, making combat strength negative.
- A graft placement on an occupied space demanding two different promises of one partner, leaving no choice.
- In the rollout: the Secret Project tile bottoms, the top 3 Contracts of Coercive Negotiation, and the top 3 cards of Long Live the Fighters were re-dealt in imagined worlds, turning the actual legal choice illegal.

The soak was run twice on September 16 at the same size, after the score-table work and after the tie-break rules: with the heuristic, 2,000 games each for base+CHOAM, Bloodlines, Bloodlines+Tech, Immortality and all expansions+promos, 1,000 draft games with all expansions+promos, and 1,000 random games with all expansions+promos, 12,000 in all. There were no failures in the card-conservation, dead-end, observation-leak, replay, legal-action-application and codec-round-trip checks.

## Lessons about measuring

- **Raising a score in one place applies elsewhere too.** Two attempts to break card ties by adding a term to the score function lost (base+CHOAM -2.2 and -6.0 points, all expansions -8.6). Among tied spaces the term became a space-selecting term, and scaling it down gave -8.6 with all expansions, identical down to the decision counts. The adopted method narrows only after the space is chosen.
- **A combined number hides offsetting effects.** Splitting -5.6 by expansion gave results from +17.0 to -6.6, and even the -6.6 was a CHOAM-on value; the same expansion combination without CHOAM was -13.6 and -9.9, nearly twice as bad. Conditions must be written with the number.
- **The wiring you measured may not be the wiring you ship.** The "995 remaining ties" came from a probe that forced the table onto all expansions; measured on the shipped configuration it was 852 for base+CHOAM and 1,652 for all expansions. The earlier claim that "38 action kinds are coin flips" was also exaggerated; the measurement was 0.
- **A control must not change in the middle of an A/B.** Moving the improved rule into the repository while a comparison ran made parallel workers read the new code, and the comparison became variant against variant. About 20 minutes were lost, and the control became a variant with a fixed name. For the same reason, a pinned-table variant inherits the rest of the current table, so we now name every space that changes.
- **"Better than before" is not "correct".** We read beating the old table as meaning the table was right; the top-space ablation showed the table itself was wrong.
- **Measure a suspect found by reading.** The first-named suspect in the throughput regression was a minor term.

## One last check before training

On the morning of September 17 we made a final check that the full-expansion configuration (CHOAM, Bloodlines, Tech Module, Immortality and promos all on) was ready as the training target. It has 32,963 action codec entries (4,371 for the base game) and a network of about 19 million parameters. On a laptop with about 8 GB of memory, 32 games over 6 workers is impossible with all expansions; 16 games, 2 workers and an update minibatch of 1024 was the limit. Six training iterations, `--resume`, and loading checkpoints in the tournament tool all worked, a soak of 300 heuristic, 300 random and 100 draft games had no failures, and all 60 open rules questions were settled. Training continues in [the next entry]({{< relref path="devlog/2026-09-19-first-training.md" lang="en" >}}).

## References

- [Immortality evaluation terms](https://github.com/jungcheolseung/Dune-Imperium/commit/21b5318)
- [Closing gaps in the verification tools](https://github.com/jungcheolseung/Dune-Imperium/commit/7867f7c)
- [Throughput regression report](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/throughput-2026-09-10.md)
- [Board-space table differentiation](https://github.com/jungcheolseung/Dune-Imperium/commit/30f377b)
- [Old table only for the Tech Module](https://github.com/jungcheolseung/Dune-Imperium/commit/aa46132)
- [Card tie-break after the space is chosen](https://github.com/jungcheolseung/Dune-Imperium/commit/69bf880)
- [Faction, trash and buy tie-breaks](https://github.com/jungcheolseung/Dune-Imperium/commit/e6fa084)
- [Rollout common random numbers](https://github.com/jungcheolseung/Dune-Imperium/commit/c88f111)
- [Encoder rewrite](https://github.com/jungcheolseung/Dune-Imperium/commit/cf67b96)
- [2026-09-10 baseline](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/baseline-2026-09-10.md)
- [2026-09-16 baseline](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/baseline-2026-09-16.md)
