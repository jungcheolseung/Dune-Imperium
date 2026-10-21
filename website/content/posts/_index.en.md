+++
title = "Technical articles"
description = "How the rules engine, AI decisions, training, and evaluation work."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
weight = 40
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/implementation-plan.md", "docs/evaluation/README.md"]
+++
This project turns board-game rules into executable code and builds AI opponents on top. These articles explain the structure and behavior. Follow the [development journal]({{< relref path="devlog/_index.md" lang="en" >}}) for progress over time.

## Rules engine

Card effects, legal actions, hidden information, replay, and verification.

[Turning board-game rules into an executable engine]({{< relref path="posts/rules-to-engine.md" lang="en" >}})

## AI experiments

How AI chooses a move, and what changes when opponents, models, or search settings change. Results include measurement dates, conditions, failed attempts, and open questions.

- [How search AI chooses a move]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}})
- [Does mixing opponents improve training?]({{< relref path="posts/learning-with-opponents.md" lang="en" >}})
- [Inside the AI model: from reading a position to scoring moves]({{< relref path="posts/model-architecture.md" lang="en" >}})
- [Checking the model structure against other game AIs]({{< relref path="posts/architecture-survey.md" lang="en" >}})

See [guides]({{< relref path="guides/_index.md" lang="en" >}}) to play and [updates]({{< relref path="updates/_index.md" lang="en" >}}) for user-visible changes.
