+++
title = "Does mixing opponents improve training?"
description = "A controlled comparison of self-play and app-AI opponents from October 7, 2026."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
categories = ["AI 학습 실험"]
tags = ["self-play", "대조 실험", "탐색 평가"]
[params]
source_ref = "e7e9ad4f"
sources = ["docs/evaluation/m10-2026-10-07.md"]
experiment_date = 2026-10-07
experiment_code = "381f2e42"
+++
Does learning only against similar policies limit what an AI learns? Does mixing in a different kind of opponent help in actual matches?

On October 7, 2026, two runs started from the same model with different opponents. This article covers **the first 1,000 additional training iterations**, not the current play model's performance.

## The two models

Both started from model `8081`, with the same rules, training settings, and sequence of game seeds.

| Run | 32 games in each collection |
| --- | --- |
| M: mixed opponents | 16 games with two learner seats and two hard app AI seats, plus 16 self-play games |
| S: self-play only | 32 self-play games |

Each ran 1,000 further iterations. App AI actions are not learner data, so M collected 96 learner seat-games per iteration and S collected 128. Iteration counts were equal; data quantity and runtime were not.

## Conditions

- Date: October 7, 2026.
- Engine commit `381f2e42`, action codec v138, observation v30.
- CHOAM, promos, Bloodlines, Tech, Immortality, Go to 11, Epic, Arrakeen Scouts, and leader draft enabled.
- Learning rate `1e-4`, minibatch 1,024, four collection workers.
- Evaluation used separate seeds absent from training and training-time evaluation, starting at 3,400,000.

Short training-time evaluations were progress signals. Final judgments used separate matches, checking average rank and VP margin as well as wins.

## Mixed opponents helped direct policy play

A 2,800-game comparison used two M seats and two S seats. These were free-for-all games, not teams; the table combines each model's two seats' shares of wins.

| Result | M | S |
| --- | ---: | ---: |
| Win share | 52.9% | 47.1% |

The difference from unrounded data was **+5.9 percentage points**, with a 95% interval of **[+2.2, +9.5] points**. Rank and VP margin also favored M. Under these conditions, M won the direct comparison.

That does not establish the same benefit at every training stage, with every game configuration or opponent.

## Search produced a different result

Models are also used inside search, for candidates and position evaluation. Search using M and search using the starting model 8081 each played against three hard app AI opponents on the same seeds, 200 games per configuration.

| Search model | Win rate against three hard app AI seats |
| --- | ---: |
| Starting model 8081 | 79.5% |
| New model M | 69.0% |

Search with M differed by **−10.5 percentage points**, with a 95% interval of **[−17.5, −3.5] points**. Direct-policy improvement did not carry over to search in this initial comparison.

Policy changes and value changes need not help search in the same way. That is a possible explanation, not a cause established by this comparison.

## What this experiment established

Evaluate a model in the way it will be used. Direct policy play and search needed separate tests. At the time, the training lineage and the play server's search model were managed separately.

Further checks with new seeds and additional training followed. The [full experiment record](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/evaluation/m10-2026-10-07.md) includes them. This article's numbers come from sections 1–4 and are not combined with later experiments or current-model results.

[How search AI chooses a move]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}}) explains the roles of policy and value.
