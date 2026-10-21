+++
title = "Roadmap"
description = "Current development work and remaining checks, without promised release dates."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
weight = 30
[params]
source_ref = "c8f61677"
sources = ["docs/development-handoff.md", "docs/composed-effects-plan.md", "docs/entity-network-plan.md", "docs/evaluation/architecture-survey-2026-10-21.md"]
+++
The goal is a reliable rules engine and AI people want to play against. These are current directions, not a release schedule.

## Available now

Four-player Uprising and selectable modules can be played to completion, against AI or remotely with friends. Saving, replay, training, and evaluation tools are also in use. See [supported features]({{< relref path="about/support.md" lang="en" >}}) for the scope.

## Continuing work

**Make the rules engine's representation consistent.** Card and board effects are recorded as shared pieces, and player actions are split into card, space, effect, and target steps. The plan's remaining stage adds Rise of Ix, base-game Imperium, and Conspiracy cards as the same records. Replay checks accompany changes that affect saves and models.

**Represent cards and actions in the model.** We experiment with architectures that read entity features and are retraining the play model for the new action units. A new architecture alone is not a reason to replace the play model; actual matches and search performance determine that choice.

**Refine how search AI chooses and compares candidates first.** In our measurements and in the survey of other game AIs, search moved win rates more than model structure. So we will first test not overturning the model's choice on small differences, giving more simulations to promising candidates, and choosing possible worlds by the moves opponents actually made, and then change the retraining method and the model structure. The evidence and order are in [Checking the model structure against other game AIs]({{< relref path="posts/architecture-survey.md" lang="en" >}}).

**Improve play usability.** Work continues on unavailable-choice explanations, confirmation and undo, and save/recovery guidance. Feedback from games with friends informs these changes.

## Distribution and installation

Native Windows checks and a verified game release remain. Standalone installers and optional models will be linked when they actually exist.

User-visible changes go in [updates]({{< relref path="updates/_index.md" lang="en" >}}); implementation and experiments go in the [development journal]({{< relref path="devlog/_index.md" lang="en" >}}).
