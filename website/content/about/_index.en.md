+++
title = "About the project"
description = "A rules engine, a browser interface, and AI opponents for four-player Uprising."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
weight = 10
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/implementation-plan.md", "docs/rules/README.md"]
+++
Dune: Imperium AI is a personal development and research project aiming to make **Dune: Imperium - Uprising playable with capable, enjoyable AI opponents**. Actual play, training, experiments, and evaluation share the same rules engine.

## Rules engine

The Python engine plays a four-player Uprising game from setup to the end. It enumerates legal actions, applies choices, and separates what each player may see. Where official sources do not give a clear answer, project rulings are documented separately.

Tests and replay records help check changes to rules and features. [The engine article]({{< relref path="posts/rules-to-engine.md" lang="en" >}}) explains this approach.

## Playing with people and AI

Play in a browser against three AI opponents, or invite friends and fill the remaining seats with AI. The interface includes card and space selection, turn confirmation, saving and loading, permitted undo, and review of finished games. The game interface supports Korean and English.

One PC runs the server. Guests do not need the source code or Python. See the [guides]({{< relref path="guides/_index.md" lang="en" >}}) for hosting and joining.

## Learning and evaluating AI

We train models through repeated games and test both direct model decisions and search guided by those models. Performance claims need the opponent, rules, model, and game count. Improvements, unsuccessful attempts, and remaining limitations are recorded in the [development journal]({{< relref path="devlog/_index.md" lang="en" >}}).

## Current availability

Installation is currently from source. The launcher and hosting workflow have been checked on macOS, and launcher, server and remote seat joining on native Windows 11; manual checks such as guests connecting from other PCs remain. Linux has not been checked separately. Original card and board images and trained models are not included in the source. A text interface and the default AI work without them. Development targets wide desktop screens; playing a whole game on a phone alone has not been validated.

[Supported features]({{< relref path="about/support.md" lang="en" >}}) · [Downloads and installation]({{< relref path="downloads/_index.md" lang="en" >}}) · [Roadmap]({{< relref path="about/roadmap.md" lang="en" >}})

## The project and the original game

This is an unofficial personal project, not an official game or digital product of the original publisher. Rules follow [Dire Wolf Digital's official resources](https://www.direwolfdigital.com/dune-imperium/resources/) first. Original card and board images are not distributed from this repository.

Code and development documents are in the [GitHub repository](https://github.com/jungcheolseung/Dune-Imperium).
