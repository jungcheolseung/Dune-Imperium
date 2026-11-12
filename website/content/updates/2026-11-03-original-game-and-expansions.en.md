+++
title = "The original Dune: Imperium and all expansions, changed screens and server"
description = "What changed since October 22: the original game and Rise of Ix, expansion combinations, Collect in Arrakeen Scouts, the waiting room and warnings, the WSL launcher, and remote server security hardening."
date = 2026-11-03
publishDate = 2026-11-03
lastmod = 2026-11-03
draft = false
tags = ["프로젝트 소식"]
[params]
source_ref = "81ca9468"
sources = ["README.md", "docs/development-handoff.md", "docs/worklog/2026-10.md", "docs/worklog/2026-11.md", "docs/remote-play-host-guide.md", "src/dune_imperium/server/static/index.html"]
update_kind = "project-status"
+++

This collects what changed for players from October 22 to November 3, after the [first update]({{< relref path="updates/2026-10-20-project-status.md" lang="en" >}}). It is a change notice for people who download the source and run it, not an announcement of a new release.

## Two base games and all expansions

- On the new game screen you choose the **base game**: Dune: Imperium - Uprising or Dune: Imperium (the original game). The original game has its whole board, cards and leaders, and is played on an original board image (when the image is among the image materials each person prepares).
- **Rise of Ix** can be turned on in both the original game and Uprising. Immortality, Bloodlines with Tech Module, Arrakeen Scouts, Epic Game Mode and promo cards can also be chosen in both base games. The CHOAM Module opens only in Uprising, and the original game's Epic Game Mode opens only together with all of Rise of Ix. Original-game cards can be mixed into Uprising.
- Turning on Rise of Ix and Tech Module together lets you choose how much of Ix to use (all, leaders and Tech tiles only, Tech tiles only).
- Original games seat the app AI (hard, normal, easy), the heuristic and the random AI. The search AI still sits only in Uprising.

The scope and tables are in [supported features]({{< relref path="about/support.md" lang="en" >}}), and how it was built is in the [original game and Rise of Ix devlog]({{< relref path="devlog/2026-11-02-original-game-and-ix.md" lang="en" >}}).

## Game screen

- A remote room opens as a **waiting room** until all human seats are filled, and any participant presses **Start game ▶**. Seats are assigned at random when the game starts. The "Random seating" box on the new game screen was removed (November 1).
- A **Player 1 starts** box was added (on by default). It is a project convention, not an official rule.
- When ending a turn or picking another row would lose an unused effect, a ⚠ warning line appears first (October 31).
- Later rewards in Arrakeen Scouts and the shares of events and missions are collected by the receiving player pressing **Collect**. Secret choices carry the round number in which the effect occurs (November 1). Details are in the [Scouts devlog]({{< relref path="devlog/2026-11-01-scouts-on-original.md" lang="en" >}}).
- App AI seat colors follow the app's default order (green, red, yellow, blue), the seat panel gained a **Details** window, and the activity log shows card images for each turn (October 26).
- A Conflict unit used for an effect this turn cannot be recalled, and a finished game cannot be undone.

## Server and launcher

- The server launcher also works on Windows **WSL2**. Run `scripts/launcher/install-wsl.sh` in a WSL terminal (October 30).
- Remote server security was hardened (November 3). Connections and request sizes have limits, and an admin key you choose yourself must be at least 16 characters of letters, digits, `-` and `_`. After updating, the host **opens the admin link once again**. [Host guide]({{< relref path="guides/hosting.md" lang="en" >}})
- The project's play server has used a search AI model retrained by self-play since October 31. No model file is published yet. [Self-play devlog]({{< relref path="devlog/2026-11-01-self-play-stage-one.md" lang="en" >}})

## When updating

The rule and action version (codec) was raised several times in this period. A new server may be unable to open saves from before the update, so finish games in progress with the code you were using, or keep the save file and that game's code version. [Saves and updating guide]({{< relref path="guides/controls.md" lang="en" >}})
