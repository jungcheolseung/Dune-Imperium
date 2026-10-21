+++
title = "Correcting the training method's name and checking the model structure"
description = "Training long described as PPO was REINFORCE; we corrected the records, surveyed public work on other game AIs to check the model structure, and set the order of the next improvements."
date = 2026-10-21T21:00:00+09:00
publishDate = 2026-10-22
lastmod = 2026-10-22
draft = false
[params]
work_start = "2026-10-21"
source_ref = "37a19db6"
sources = ["docs/worklog/2026-10.md", "docs/development-handoff.md", "docs/evaluation/architecture-survey-2026-10-21.md", "docs/rl-environment.md", "docs/lessons.md"]
+++

## Background

After the [first retraining attempt]({{< relref path="devlog/2026-10-21-retrain-teacher.md" lang="en" >}}) fell short of its teacher, we explained the training setup again from the start. Two things came up: the training method had the wrong name, and numbers such as the model's widths had not been chosen by measurement.

## Correcting the training method's name

The learner runs PPO with `--clip` and REINFORCE with a value baseline without it. All 26 training runs since September 20, 2026 ran without `--clip`, and every run log shows a `clip_fraction` of 0. Yet plans, work logs, the handoff and devlog posts had called this training "PPO 1e-5". PPO (clip 0.2, each batch used three times) was tried once on September 18; a model that won 76.5% against three heuristic seats fell to 43.0%, and the setting was dropped.

We changed the wording to REINFORCE in 18 documents and four devlog posts on this site, and kept the records of the real PPO experiment of September 18 as they were. A lesson was recorded: name a training method only after checking its command line and logs.

## Checking the model structure

The two models (the MLP and the entity model) were equally strong when trained the same way (1,400 games on October 14, +0.1 points [−4.7, +5.1]). The 512-wide body and 64-value entity vectors had either no recorded reason or were a starting point chosen inside a speed budget, and doubling the entity widths on October 13 left distillation agreement at 95.0%.

So we surveyed public work in five strands: board games, digital card games, imperfect-information games, and large game agents, plus studies of structure versus training method. The conclusions are in [Checking the model structure against other game AIs]({{< relref path="posts/architecture-survey.md" lang="en" >}}): the current structure sits inside common designs but nothing shows it is optimal, and in published comparisons search at play time moved win rates far more than structure, followed by the training method. The model itself is described in [Inside the AI model]({{< relref path="posts/model-architecture.md" lang="en" >}}).

Following the survey, the order of work was set again: first let search AI use the old model on the current engine, then test search parts (keep the model's first choice on small differences, candidate and simulation allocation), retrain by distilling on the student's own positions with kickstarting, and change the structure after that. Each experiment has a pass rule; none had run when this post was written.

## Checks and open points

- Every remaining "PPO" in the edited documents was checked to refer to the real PPO experiment or to the learner's option.
- Of the survey's numbers, the LoCM search result (26.8% → 51.35%) was checked against the paper's abstract. Figures on which the notes disagreed were left out of the public post.
- On the same day the site's browser check was fixed: with an installed Chrome it could not click the journal list, because the site's smooth scrolling and the checker's retry scrolling overlapped. The check now runs with reduced motion.
- Results of the next experiments will follow in later posts.

## References

- [Commit correcting the training method's name](https://github.com/jungcheolseung/Dune-Imperium/commit/7fe69ac6)
- [Model structure survey report](https://github.com/jungcheolseung/Dune-Imperium/blob/37a19db6/docs/evaluation/architecture-survey-2026-10-21.md)
- [Handoff with the new order](https://github.com/jungcheolseung/Dune-Imperium/blob/37a19db6/docs/development-handoff.md)
- [Browser check fix](https://github.com/jungcheolseung/Dune-Imperium/commit/7e29371e)
