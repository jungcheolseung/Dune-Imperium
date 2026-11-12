+++
title = "Install with one line, without Git or Python"
description = "On macOS and Windows one command line installs and updates the game."
date = 2026-11-06
publishDate = 2026-11-06
lastmod = 2026-11-06
draft = false
tags = ["프로젝트 소식"]
[params]
source_ref = "5d2fea34"
sources = ["README.md", "docs/remote-play-host-guide.md", "docs/worklog/2026-11.md", "scripts/launcher/install.sh", "scripts/launcher/install.ps1"]
update_kind = "project-status"
+++

Until now, running the game yourself meant installing Git and uv and cloning the source. From November 6, one command line installs it on macOS and Windows. This is a new way to install, not the announcement of a release: the one-line install also fetches the latest source from GitHub.

## The lines

macOS **Terminal**:

```bash
curl -fsSL https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.sh | sh
```

Windows **PowerShell**:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.ps1 | iex"
```

## What changes

- One `Dune Imperium` folder in your home folder receives the game files, uv, Python 3.14 and the server packages, and a launcher shortcut appears. Nothing is written outside the folder and PATH is not changed, so removing the game means deleting the folder.
- To update, close the launcher and run the same line again. Saves, launcher settings, images and model files stay.
- App AI is included. Card and board images and the search AI are not.
- On 2026-11-06 a fresh install, an update, a path with Hangul and spaces, and creating a game on the installed server were checked on an Apple Silicon Mac and on Windows 11 (PowerShell 5.1, a PC without uv or Python). Linux and WSL2 still install from source.

Details are in [downloads and installation]({{< relref path="downloads/_index.md" lang="en" >}}) and [your first game]({{< relref path="guides/first-game.md" lang="en" >}}). Guests joining a friend's room still install nothing.
