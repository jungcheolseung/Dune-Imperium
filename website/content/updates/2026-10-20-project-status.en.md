+++
title = "Initial status: available features and next work"
description = "Current play features, installation method, and remaining engine and AI work as of October 20, 2026."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
tags = ["프로젝트 소식"]
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/development-handoff.md", "docs/worklog/2026-10.md"]
update_kind = "project-status"
+++
This first update collects the project's current capabilities and guides. It does not announce a new game release or a downloadable model.

## Available play features

Four-player Uprising can be played against AI or with friends through a host's server. Optional configurations include CHOAM, Bloodlines with Tech Module, Immortality, Epic Game Mode, and Arrakeen Scouts. See [supported features]({{< relref path="about/support.md" lang="en" >}}) for the precise scope.

The interface provides Korean and English, saving/loading, permitted undo, and finished-game review. The default app AI does not need a model file. Search AI requires a compatible model and extra dependencies; the source does not include that model.

## Starting a game

- On your PC: follow [your first game]({{< relref path="guides/first-game.md" lang="en" >}}).
- As a host: use [hosting a room]({{< relref path="guides/hosting.md" lang="en" >}}).
- As a guest: use [joining a room]({{< relref path="guides/joining.md" lang="en" >}}).

Installation is from source. The macOS launcher path has been checked; native Windows and separate Linux hardware checks remain. (Added October 21: checks of the launcher, server and remote seat joining on native Windows 11 had already been done on October 12 in separate work and were merged into master on the 21st. Manual checks such as guests connecting from other PCs remain.) See [downloads]({{< relref path="downloads/_index.md" lang="en" >}}) and [validation scope]({{< relref path="about/support.md" lang="en" >}}).

## Next work to record

Engine work continues on consistent effect and action representations. AI work investigates card/action features and whether they improve actual matches and search. Play feedback informs controls, undo, and saves.

Follow the [development journal]({{< relref path="devlog/_index.md" lang="en" >}}). The initial technical articles cover engine structure, search decisions, and controlled training with different opponents.

Before updating an ongoing game, check [saves and compatibility]({{< relref path="guides/controls.md" lang="en" >}}).
