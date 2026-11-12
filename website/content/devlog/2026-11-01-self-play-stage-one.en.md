+++
title = "A new model for the search AI: failed distillation experiments and self-play stage one"
description = "On the engine with changed action units, we trained students to imitate a teacher model in several ways, but they lost or drew in the search seat. After narrowing the cause to value estimation, a model whose value was retrained by self-play was put on the play server."
date = 2026-11-01T18:00:00+09:00
publishDate = 2026-11-03
lastmod = 2026-11-03
draft = false
[params]
work_start = "2026-10-22"
retrospective = true
source_ref = "81ca9468"
sources = ["docs/development-handoff.md", "docs/entity-self-play-plan.md", "docs/worklog/2026-10.md", "docs/worklog/2026-11.md", "docs/search-ai.md"]
+++

## Background

Since [the action units changed]({{< relref path="devlog/2026-10-20-action-units.md" lang="en" >}}) on October 20, the play server's search AI model (MLP, codec v147) knows only some of the new action rows. On October 22 we attached an adapter that reads them as the old action units to the search seat and recovered its strength (1 against 3 hard app AIs, 400 games: 81.8% against 82.2% on the v149 engine, difference −0.5 points [−6.0, +5.0]). The remaining question was how to make a new model that reads card and space features (the entity network) as strong as that, or stronger. In the order set in the [model structure check]({{< relref path="devlog/2026-10-21-structure-check.md" lang="en" >}}), we handled search first and then the learning signal.

All intervals below are 95% intervals, and the pass rules were written before running. The interval of a 400-game win-rate difference is about ±5 points, so rank and VP difference were read together.

## Refining search: only one passed

- **E1 flip threshold (passed).** The model's top candidate is replaced only when the mean difference over a few rollouts exceeds 0.01. The first test (1 against 3 hard app AIs) fell short at +0.7 points [−5.2, +7.0]. The second test (1 against 3 play models, 400 games) gave 77.5% against 76.0%, +1.5 points [−5.0, +8.0], with a VP difference of +0.53 [+0.16, +0.92], meeting the pre-written rule (win-rate difference above −2 points and a confirmed VP improvement). It was turned on for the play server's search AI on October 23 (`79bdcb5b`).
- **E3 candidate allocation (fell short).** Dividing simulations among 8 candidates gave 78.2%, −3.5 points [−9.2, +2.0].
- **Surrounding settings (fell short).** Letting the model choose the leader +4.5 points [−1.3, +10.5], prior-probability weighting +3.5 points, and threshold 0.02 +5.0 points [−1.0, +11.0]: all intervals covered 0. All three cells were above the same control cell, so we also recorded the possibility that the control cell came out low.

## Students imitating the teacher: mostly short

| Experiment | Result | Verdict |
| --- | --- | --- |
| E5 distilling again on positions the student played (twice) | −4.5 points against the teacher [−11.3, +2.0], disagreement 17.62% on uncertain decisions (target below 15%) | Fell short |
| E6 reinforcement learning + a term to imitate the teacher (800 iterations) | −7.6 points [−12.6, −2.6] against the teacher in 1,400 2:2 games | Fell short |
| Mixed-data DAgger (2.6 million rows) | −4.3 points against the teacher [−10.2, +2.0], disagreement 17.53% | Fell short |
| E8 wider model | Disagreement 17.88% and 17.60% (baseline 16.53%) | Fell short |
| E8 4 times the data (10.4 million rows) | Disagreement 14.31%, model alone 55.5% against teacher 55.2% | Target passed |

With more data, the student for the first time played as well as the teacher. But when that student was put in the search seat, it was clearly weaker than the server seat: 70.0% against 77.5%, −7.5 points [−14.2, −1.0], VP difference −0.88 [−1.32, −0.45]. A model that is strong alone but loses inside search had already happened in September.

To separate the cause, we attached the teacher's value (leaf evaluation) to the student's policy and got 78.2%, +8.3 points [+2.2, +14.0] above the student alone. Most of what the student lost in search was in **value estimation**. The student chose Liet Kynes in 72 games (48.6%) and lost many of those games.

The network trained on value alone (E7b) was clearly better than the student by +5.6 points [+2.2, +9.1] (300 seeds, 1,200 games), but against the server seat it was clearly behind with a win rate of −0.3 points [−3.8, +3.3] and a VP difference of −0.30 [−0.53, −0.07], a "partial pass". Using that value network only for choosing the leader gave a confirmed +3.1 points [+0.9, +5.4], which also showed that a large share of the gain lies in leader choice. The user decided not to fix this separately but to resolve it with self-play.

## Self-play stage one: value learns the final win

The October 30 plan (entity-self-play-plan.md) set the direction "no need to imitate the teacher". One model holds both policy and value, and from now on it learns only from the results of its own games and its own search. Two of the user's important decisions:

- **Reward:** mostly first place, with graded differences. 1st +1, 2nd −1/6, 3rd −1/3, 4th −1/2 (sum 0). The user: "let's not treat 2nd, 3rd and 4th the same".
- **Opponents:** a higher share of self games. Stage one is 80% the current self, 10% the old play model, 10% hard app AI.

After a 5,000-game pilot, the main training was run. From 00:26 to 12:00 on October 31 we collected 100,000 games (in 20% of them the leaders were dealt at random) and trained the value branch with per-round TD (λ = 0.8). The error against game results fell 4.3% from the starting student.

Two new models and two server models played 140 games 2:2 (a size chosen by the user).

| Metric | New model against server model | Verdict |
| --- | --- | --- |
| Win share | 55% against 45%, difference +10 points [−7, +26] | Not confirmed |
| Mean rank | 2.41 against 2.59 | Not confirmed |
| VP difference per game | +0.71 [+0.16, +1.28] | Confirmed |

The win rate was not confirmed. Seeing this result, the user decided "let's switch to the new network", and on October 31 the play server's search AI model was replaced with the new file. The old file is kept, so returning only needs a link change, and earlier saves continue with the old model recorded in them. Whether it improved in real games against people has not been measured yet.

## Looking two rounds ahead: worse

We built a measurement option that makes search play out two rounds ahead instead of to the end of this round (`01627431`) and measured it with the student model. The result, finished on November 1, showed no visible win-rate difference, a confirmed worsening of mean rank and VP difference, and 2.46 times the time per decision. Whether to repeat the same comparison with the self-play stage one model was left as a user decision.

## Experiment speed

On October 27 the experiment tools were sped up (`39477e34`). One search decision became 13–14% faster, and every choice and simulation value in the 6 gate games was identical to the bit. Training with the distillation data held as an in-memory copy cut an epoch from 1,650 seconds to 585 seconds. We also built a tool to filter value networks offline before the 400-game gate. However, this tool measures how closely a model searches like the old v147 model, so it cannot pick out a model better than v147.

## What was not done and what is left

- **Stage three (training in which the policy improves) has not been run yet.** The plan includes mixing game-result learning with self-search labels at 6:4, and the label cost was measured in advance (1.29–1.48 seconds per searched decision, about 5,000 per hour on 4 cores). There is no record of a search-label training run in this period.
- The new model learned only from Uprising games. It has never trained on the original game or Rise of Ix, so the search AI does not sit in the original game.
- Search speedups that change the numbers (such as batching simulations to compute the model at once) were put on hold because they need a gate verdict.

## References

- Search seat option and flip threshold merge ·
  AI experiment speed
- Self-play stage one tools ·
  Main training tree ·
  Horizon option ·
  Server model replacement record
- Training and AI items in the development handoff ·
  Work log, October
