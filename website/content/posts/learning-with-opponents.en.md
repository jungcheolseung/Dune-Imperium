+++
title = "Does mixing opponents improve training?"
description = "A controlled comparison of self-play and app-AI opponents from October 7–8, 2026, rechecked with search seats on new seeds."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
categories = ["AI 학습 실험"]
tags = ["self-play", "대조 실험", "탐색 평가"]
[params]
source_ref = "c8f61677"
sources = ["docs/evaluation/m10-2026-10-07.md", "scripts/ab/paired.py"]
experiment_date = 2026-10-07
experiment_code = "381f2e42"
+++
Does learning only against similar policies limit what an AI learns? Does mixing in a different kind of opponent help in actual matches?

On October 7, 2026, two training runs from the same model were compared, changing only the opponents, and the results were rechecked on new seeds through the next day. This article covers that process and the final interpretation. It does not measure the current play model.

## Two models

Both runs started from model `8081`. It had been trained on October 6 for another 1,000 iterations from an earlier model with half its training games against app AI (the name is the lineage's iteration number), learned under v136 rules and migrated to this experiment's v138 rules. Rules, training settings, and seed order matched; only the opponents differed.

| Run | Training collection of 32 games |
| --- | --- |
| M: mixed opponents | 16 games with two learner seats and two hard app AIs; 16 self-play games |
| S: self-play only | All 32 games between learner seats |

Each run trained for 1,000 more iterations. App-AI actions are not learner data, so each iteration had 96 learner seat-games for M and 128 for S. Training iterations were equal; data volume and run time were not. M took 4 hours 24 minutes (15.0 seconds per iteration) and S 3 hours 53 minutes (13.2 seconds), with no truncated games. Both runs also readapted to new rules (card-audit corrections and "no playing an Intrigue card with no effect").

## Conditions

- Date: October 7, 2026 (follow-ups October 7–8).
- Engine commit `381f2e42`, action codec v138, observation v30. Follow-ups used a codec v139 engine.
- Rules: CHOAM, promo, Bloodlines, Tech, Immortality, Go to 11, Epic, Arrakeen Scouts, and leader draft.
- Learning rate `1e-4`, minibatch 1,024, four collection workers. The machine was a Mac mini (M4, 16 GB), and the runs went one after the other.
- Evaluation used separate seeds from 3,400,000, unused for training or in-training checks.
- Judging rules were written down before the results.

95% intervals were bootstrapped over seeds, treating the seat rotations of one seed as a single cluster. Games from the same seed share leaders, decks, and first player, so treating them as independent would make the interval too narrow.

## In-training signals were not used for comparison

During training, one model seat played three hard app AIs for 100 games to track progress. With a standard error of 4–5 points, the two runs were already 17 points apart (32% vs. 49%) after only 19 iterations from the same start. These numbers served only as a warning signal; final judgments came from separate matches by win share, mean rank, and VP margin.

## Mixed training won direct matches

Two M seats and two S seats played 2,800 games. This is not team play: four seats compete individually, and each model's share combines its two seats.

| Result | M | S |
| --- | ---: | ---: |
| Win share | 52.9% | 47.1% |

The unrounded difference was **+5.9 percentage points**, with a 95% interval of **[+2.2, +9.5]**. Mean rank and VP margin also favored M. M won although it used a quarter less training data per iteration than S.

Other comparisons pointed the same way.

| Comparison | Games | Result |
| --- | ---: | --- |
| M vs. starting model 8081 | 1,400 | +13.1 points [+8.0, +18.1] |
| S vs. starting model 8081 | 1,400 | +4.9 points [−0.3, +9.9] |
| Win share against two hard app AIs | 1,400 each | M 67.8%, S 63.8%, 8081 60.1% |

Since S was not clearly better than its starting model, M's gain was read as coming mostly from mixed training. This does not generalize to every game or training stage; it applies to this start model, rules, opponents, and training length.

## The first search comparison pointed the other way

Play can use models directly or as policy/value inputs to search. M and 8081 were each used in search against three hard app AIs.

Results over the same 50 seeds, 200 games each:

| Search model | Win rate vs. three hard app AIs |
| --- | ---: |
| Starting model 8081 | 79.5% |
| New model M | 69.0% |

Search with M differed by **−10.5 points** with a 95% interval of **[−17.5, −3.5]**. Under the pre-declared rule the play server's search model was not changed at that point. Possible explanations were recorded: the value target shifted because some games were against app AI, the policy specialized toward beating app AI, or the sample was small.

## On new seeds the difference disappeared

The reversal was rechecked on 50 new seeds. This time search with M was +1.0 points ([−8.0, +10.0]) against search with 8081, and search with S was at the same level. Under the pre-declared rule (the point estimate on new seeds must also be below zero), the reversal did not hold.

Over three seed blocks (150 seeds), search with M and with 8081 differed by **−0.5 points ([−5.8, +4.7])**. The same 8081 search won 79.5%, 68.0%, and 63.8% across the blocks, so a single 50-seed point estimate can move by about ±8 points. Of the three explanations, the small sample fit best; the policy/value split measurement was planned only if the reversal held, so it was skipped.

## Training further the same way

Model X was then trained for another 1,000 iterations from M. Against M directly, X was +2.0 points ([−3.3, +7.3]), within noise; most of the gain had come in the first 1,000 iterations.

Search told a different story. Over 100 seeds including new ones, search with X was **+11.3 points ([+5.3, +17.3])** stronger than search with 8081, and X's search won 78.0%, 77.9%, and 78.0% across three blocks. On October 8 the play server's search model was changed to X. The play model has changed again since, through later experiments.

## Lessons

Evaluate models the way they will be used. Direct-policy matches and search performance needed separate checks, and the two did not always move together.

A difference from one 50-seed block reverses easily: −10.5 points on the first block vanished over 150 seeds. Writing judging rules before the results and rechecking important decisions on new seeds remained the practice in later experiments.

All numbers and judging rules are in the [experiment record](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-10-07.md). See [how search AI chooses a move]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}}) for how search uses policy and value.
