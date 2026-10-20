+++
title = "Entity-network experiments and a matched learning rate"
description = "Build shared card/space features, then revise an apparent architecture gain after a controlled comparison."
date = 2026-10-14
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-13"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/entity-network-plan.md", "docs/worklog/2026-10.md"]
+++
## Changing the input representation

An entity-based network represented cards, spaces, and actions through shared features rather than only fixed identity numbers. Evaluation tools and baselines preceded distillation from the existing model and reinforcement learning.

The entity model initially beat the comparison MLP, suggesting an architecture benefit. The learning rates, however, differed.

## Matching the learning rate changed the interpretation

On October 14, a matched-rate 1,400-game comparison showed a +0.1 percentage-point difference, with a 95% interval from −4.7 to +5.1 points. It did not establish a stronger architecture under those conditions. The earlier gain was reinterpreted as an effect of the learning recipe/settings.

Search evaluation also failed to establish a win-rate advantage under the declared criteria. Implementing a new architecture and justifying replacement of the play model were separate outcomes.

## What remained useful

The feature representation and evaluation/distillation tools supported later work connecting ability records to model input. This experiment is not presented as confirmed superiority of the new architecture.

## References

- [entity-network-plan.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/entity-network-plan.md)
- [Correct the entity record: at a matched learning rate the MLP is as strong](https://github.com/jungcheolseung/Dune-Imperium/commit/4df74232)
