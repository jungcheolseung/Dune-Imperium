+++
title = "Roadmap"
description = "Current development work and remaining checks, without promised release dates."
date = 2026-10-20
lastmod = 2026-11-03
draft = false
weight = 30
[params]
source_ref = "81ca9468"
sources = ["docs/development-handoff.md", "docs/base-game-and-ix-plan.md", "docs/entity-self-play-plan.md", "docs/reviews/2026-11-cloud-server-security.md", "docs/evaluation/2026-11-engine-speed.md"]
+++
The goal is a reliable rules engine and AI people want to play against. These are current directions, not a release schedule.

## Available now

Four-player games of the original Dune: Imperium and Dune: Imperium - Uprising can be played to completion with every expansion, against AI or remotely with friends. Saving, replay, training, and evaluation tools are also in use. See [supported features]({{< relref path="about/support.md" lang="en" >}}) for the scope.

## Finished large work

**The original game and Rise of Ix.** From 22 October to 2 November 2026, stages added the original game's board, cards and leaders, Rise of Ix, every combination of the two base games and the expansions, and Arrakeen Scouts on the original game. Each stage checked that existing Uprising games still produce the same results. The process is in the [development journal]({{< relref path="devlog/2026-11-02-original-game-and-ix.md" lang="en" >}}). The original game's House Hagal automated opponent and two-, three- and six-player setups are out of scope.

## Continuing work

**Let the search AI play the original game.** The search AI's current model was trained on Uprising games only. Original and Rise of Ix tables seat the app AI, heuristic and random AI. For the model to learn the original game, self-play data from that game has to be collected first.

**Let the AI learn from its own games.** On 31 October the play server's search AI switched to a model built by self-play stage 1 (value learning). Next come a fresh comparison of how many rounds ahead to look, and stage 3, where the policy itself improves. Stage 3 exists only as a plan and has not been run. A new model replaces the current one only after matches and search show an improvement. [Self-play stage 1 record]({{< relref path="devlog/2026-11-01-self-play-stage-one.md" lang="en" >}})

**Reduce the remaining server load.** Of the security review's findings, two are kept as notes: reviewing a finished game's replay and undo hold the server's CPU for a long time. The engine speed work was measured in the cloud and on the Mac mini; its effect on the play-server PC has not been measured yet.

**Improve play usability.** Work continues on unavailable-choice explanations, confirmation and undo, and save/recovery guidance. Feedback from games with friends informs these changes. Korean faces for the original game's cards will follow once photos of the official Korean edition are available.

## Distribution and installation

The first step is making the current installation method and guides easy to find. Checking guests who connect from other PCs to a Windows or WSL host, and preparing a verified release, remain. Standalone installers and optional models will be linked when they actually exist.

User-visible changes go in [updates]({{< relref path="updates/_index.md" lang="en" >}}); implementation and experiments go in the [development journal]({{< relref path="devlog/_index.md" lang="en" >}}).
