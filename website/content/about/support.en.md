+++
title = "Supported features"
description = "Supported game configurations, play features, and the operating systems checked so far."
date = 2026-10-20
lastmod = 2026-11-03
draft = false
weight = 20
[params]
source_ref = "81ca9468"
sources = ["README.md", "docs/rules/README.md", "docs/base-game-and-ix-plan.md", "src/dune_imperium/server/static/index.html", "src/dune_imperium/server/static/screens.js", "src/dune_imperium/server/seat_kinds.py", "docs/remote-play-host-guide.md", "docs/remote-play-player-guide.md", "docs/server-launcher-plan.md"]
+++
The target is the **four-player game** of both base games: the **original Dune: Imperium** and **Dune: Imperium - Uprising**. A new game picks one base game and turns on expansions. A single human can fill the other three seats with AI. This is a four-player game, rather than an implementation of the official solo mode.

## Game configurations

| Configuration | Original game | Uprising |
| --- | --- | --- |
| Four-player base game | Supported | Supported |
| Rise of Ix | Supported | Supported (the CHOAM board overlay half folded, as the official rules say) |
| Immortality, Go to 11 variant | Supported | Supported |
| Bloodlines, Tech Module | Supported (cards and leaders that do not fit the original are left out) | Supported |
| CHOAM Module | Not offered | Supported |
| Arrakeen Scouts | Supported (the companion app's original-game schedule) | Supported |
| Epic Game Mode | With all of Rise of Ix | Supported |
| Mixing in original cards | Not applicable | Supported (all but Calculated Hire, as the official rules say) |
| Promo cards | Original promos | Uprising promos |
| Public leader draft | Supported (a project convention) | Supported (a project convention) |

With both Rise of Ix and Bloodlines' Tech Module on, you choose how much of Rise of Ix to use: **all of Ix** (official), **Ix leaders and Tech tiles only** (the companion app's mix), or **Ix Tech tiles only** (official; not with Arrakeen Scouts). Arrakeen Scouts has no official rulebook, so the Dire Wolf Game Room app is its source.

Official Rivals solo/two-player rules, the original game's House Hagal automated opponent, the official three-player setup, and six-player team play are outside the current target. See [your first game]({{< relref path="guides/first-game.md" lang="en" >}}) for setup options.

## Play features

- Four seats mixing people and AI, plus watching all-AI games.
- Multiplayer through links to a host's room, with a waiting room that starts once every human seat is filled.
- Korean and English game interfaces, legal choices, help, and warnings before an unused effect is lost.
- Saving, loading, autosave, and replay review of finished games.
- Undo within the permitted information boundary.

## AI and base games

| AI | Original game | Uprising |
| --- | --- | --- |
| App AI hard, medium, easy | Supported | Supported |
| Heuristic, random | Supported | Supported |
| Search AI, trained checkpoint, rollout | Not seated yet | Supported |

The search AI's model was trained on Uprising games only, so it is not offered in the original game's seat list.
See [choosing an AI]({{< relref path="guides/choosing-ai.md" lang="en" >}}) for requirements.

## What has been tested

| Environment | Status |
| --- | --- |
| macOS | Server launcher and hosting workflow checked on a Mac mini |
| Native Windows | Windows 11: launcher start and stop, local and remote servers, app AI games and saving, remote seat joining, and recovery after a forced stop checked (2026-10-12). Guests from other PCs, display scaling, and Korean input remain |
| WSL2 | Launcher supported (2026-10-30). Its window opens on the Windows desktop through WSLg, and remote mode listens on every address. The admin link from the same PC and the Tailscale address answered. Guests from other PCs remain |
| Linux | Terminal instructions. A remote server runs as an always-on service on an Ubuntu PC. The launcher window on a desktop has not been checked |
| Guest browsers | Current desktop browsers with cookies enabled |
| Mobile-only play | Not validated |

The table separates implemented features from what has been checked on real devices. The website may be readable on a phone, but that does not make the game interface suitable for mobile play.

## Optional resources

Original card and board images and trained models are not included in the source. The text interface works without images, and the default AI does not need a trained model. The search AI needs a trained model file and extra dependencies; no model file is published yet.

[Downloads and installation]({{< relref path="downloads/_index.md" lang="en" >}}) · [Troubleshooting]({{< relref path="help/_index.md" lang="en" >}})
