+++
title = "Supported features"
description = "Implemented game options, play features, and the limits of device testing."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
weight = 20
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/rules/README.md", "docs/remote-play-host-guide.md", "docs/remote-play-player-guide.md", "docs/server-launcher-plan.md"]
+++
The target is **four-player Dune: Imperium - Uprising**. A single human can fill the other three seats with AI. This is a four-player game, rather than an implementation of the official solo mode.

## Game configurations

| Configuration | Current scope |
| --- | --- |
| Uprising | Four-player base game |
| CHOAM Module | Selectable during setup |
| Bloodlines | Expansion and Tech Module options |
| Immortality | Expansion and Go to 11 variant |
| Epic Game Mode | The mode from Rise of Ix; the full Rise of Ix expansion is not supported |
| Arrakeen Scouts | Optional module on the four-player Uprising engine |
| Promos and leader draft | Supported promos and an optional public draft; the public draft is a project convention |

Official Rivals solo/two-player rules, the official three-player setup, and six-player team play are outside the current target. See [your first game]({{< relref path="guides/first-game.md" lang="en" >}}) for setup options.

## Play features

- Four seats mixing people and AI, plus watching all-AI games.
- Multiplayer through links to a host's room.
- Korean and English game interfaces, legal choices, and help.
- Saving, loading, autosave, and replay review of finished games.
- Undo within the permitted information boundary.

See [choosing an AI]({{< relref path="guides/choosing-ai.md" lang="en" >}}) for requirements.

## What has been tested

| Environment | Status |
| --- | --- |
| macOS | Launcher and hosting workflow checked on a Mac mini |
| Native Windows | Installer scripts and launcher code available; hardware validation remains |
| Linux | CLI instructions available; separate hardware validation remains |
| WSL2 | Outside the standard guide; window and networking setup need separate checks |
| Guest browsers | Guides assume a current desktop browser with cookies enabled |
| Mobile-only game play | Not validated |

Implementation and device validation are different. The website adapting to a phone does not establish mobile support for the game itself.

## Optional files

Original card and board images and trained models are not included. You can start with text cards and the default AI. Search AI needs a compatible model and additional dependencies.

[Installation]({{< relref path="downloads/_index.md" lang="en" >}}) · [Troubleshooting]({{< relref path="help/_index.md" lang="en" >}})
