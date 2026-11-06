+++
title = "About the project"
description = "A rules engine, a browser interface, and AI opponents for four-player Dune: Imperium and Dune: Imperium - Uprising."
date = 2026-10-20
lastmod = 2026-11-06
draft = false
weight = 10
[params]
source_ref = "81ca9468"
sources = ["README.md", "docs/implementation-plan.md", "docs/rules/README.md", "docs/base-game-and-ix-plan.md", "src/dune_imperium/server/seat_kinds.py"]
+++
Dune: Imperium AI is a personal development and research project aiming to make **the board game Dune: Imperium playable with capable, enjoyable AI opponents**. Actual play, training, experiments, and evaluation share the same rules engine.

The project started with four-player Dune: Imperium - Uprising. At the end of October 2026 it added the original Dune: Imperium and Rise of Ix. A game now picks one of the two base games and mixes in expansions for four players.

## Rules engine

The Python engine plays a four-player game of either base game from setup to the end. It enumerates legal actions, applies choices, and separates what each player may see. Expansions combine with either base game and with each other; the one combination not offered is the original game with the CHOAM Module. Where official sources do not give a clear answer, project rulings are documented separately, and the game's help window lists them as well.

Tests and replay records help check changes to rules and features. [The engine article]({{< relref path="posts/rules-to-engine.md" lang="en" >}}) explains this approach.

## Playing with people and AI

Play in a browser against three AI opponents, or invite friends and fill the remaining seats with AI. The original game and Uprising each play on their own board. The interface includes card and space selection, turn confirmation, saving and loading, permitted undo, and review of finished games. The game interface supports Korean and English.

One PC runs the server. Guests do not need the source code or Python. See the [guides]({{< relref path="guides/_index.md" lang="en" >}}) for hosting and joining.

## Learning and evaluating AI

The default opponent is the app AI, a port of the official Steam app's computer opponent; it plays both base games with every expansion. The research AI combines a model trained through repeated games with search that tries a few candidate moves guided by that model. This search AI currently sits only at Uprising tables, because its model has never trained on the original game.

Performance claims need the opponent, rules, model, and game count. Improvements, unsuccessful attempts, and remaining limitations are recorded in the [development journal]({{< relref path="devlog/_index.md" lang="en" >}}).

## Current availability

On macOS and Windows one command line installs the game without Git or Python; elsewhere installation is from source. The server launcher runs on macOS, native Windows 11 and WSL2 on Windows. Launcher, server and remote seat joining have been checked on macOS and native Windows; on WSL2 the launcher and connections from the same PC have been checked. On Linux, a terminal server runs as an always-on service on an Ubuntu PC. Guests connecting from other PCs to a Windows or WSL host, and the launcher window on a Linux desktop, remain to be checked. Original card and board images and trained models are not included in the source. A text interface and the default AI work without them. Development targets wide desktop screens; playing a whole game on a phone alone has not been validated.

[Supported features]({{< relref path="about/support.md" lang="en" >}}) · [Downloads and installation]({{< relref path="downloads/_index.md" lang="en" >}}) · [Roadmap]({{< relref path="about/roadmap.md" lang="en" >}})

## The project and the original game

This is an unofficial personal project, not an official game or digital product of the original publisher. Rules follow [Dire Wolf Digital's official resources](https://www.direwolfdigital.com/dune-imperium/resources/) first. Original card and board images are not distributed from this repository or this website.

The code, its tests and the rules documents are in the [GitHub repository](https://github.com/jungcheolseung/Dune-Imperium).
