+++
title = "Downloads and installation"
description = "Install with one command line or from source, and see what has been checked on each system."
date = 2026-10-20
lastmod = 2026-11-06
draft = false
weight = 20
[params]
source_ref = "5d2fea34"
sources = ["README.md", "pyproject.toml", "docs/remote-play-host-guide.md", "scripts/launcher/install.sh", "scripts/launcher/install.ps1", "scripts/launcher/Install Launcher.command", "scripts/launcher/Install Launcher.cmd", "scripts/launcher/install-wsl.sh"]
+++
On macOS and Windows you install with **one command line**; you do not need to install Git or Python first. The one-line install also fetches the latest source from GitHub. As of November 6, 2026, no standalone installer or trained model has been published as a GitHub Release. The same installation plays both the original game and Uprising.

[Source on GitHub](https://github.com/jungcheolseung/Dune-Imperium) · [Start your first game]({{< relref path="guides/first-game.md" lang="en" >}})

## Install with one line

macOS: open the **Terminal** app (Applications → Utilities) and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.sh | sh
```

Windows: open **PowerShell** from the Start menu and paste:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.ps1 | iex"
```

It makes a `Dune Imperium` folder in your home folder and puts the game files, uv, Python 3.14 and the server packages in it. Finally it makes the launcher shortcut and opens the launcher. The first run downloads a few tens of MB; the installed folder is about 160 MB.

| Task | How |
| --- | --- |
| Start next time | Double-click **Dune Imperium Server** in that folder. You can drag it to the Dock or pin it to the taskbar |
| Update | Close the launcher and run the same line again. Saves, launcher settings, images and model files stay |
| Remove | Delete the whole folder. The installer writes nothing outside it and does not change PATH |

It stops instead of installing into a Git checkout or a folder that already holds other files. If the launcher is open during an update, it asks you to close it first. Details are in the [repository's host guide](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/remote-play-host-guide.md#한-줄-설치-gitpython-없이).

## What do you need?

| Goal | Requirements |
| --- | --- |
| Play against AI on your PC | The one-line install (macOS, Windows), or the source code, Git and uv |
| Host a room for friends | The above, plus a network guests can use |
| Join a friend's room | Desktop browser and room link; Tailscale when connecting from elsewhere |

Guests do not need the source, Python, or model files. Go to [joining a room]({{< relref path="guides/joining.md" lang="en" >}}).

## Operating systems

| System | Installation and validation |
| --- | --- |
| macOS | One-line install (checked on an Apple Silicon Mac, 2026-11-06), or clone the source, then install the launcher or use the terminal. Launcher checked on a Mac mini |
| Windows | One-line install (checked with PowerShell 5.1 on Windows 11, 2026-11-06), or clone the source, then use the launcher installer or PowerShell. Launcher, server and remote seat joining checked on native Windows 11 (2026-10-12); connections from other PCs, display scaling and IME input remain to be checked |
| WSL2 on Windows | Clone the source inside WSL, then run `scripts/launcher/install-wsl.sh` in a WSL terminal (since 2026-10-30). The launcher window opens on the Windows desktop through WSLg. Guests from other PCs remain to be checked |
| Linux | Terminal instructions. A remote server runs as an always-on service on an Ubuntu PC. The launcher window on a desktop has not been checked |

To install from source, install Git and uv first, then follow the [starting guide]({{< relref path="guides/first-game.md" lang="en" >}}). The project uses Python 3.14, which uv installs together with the project environment. The source install's launcher scripts (`Install Launcher`) run **inside the cloned project folder**.

## AI models are optional

The default app-style AI needs no trained model and comes with the one-line install. Search AI and checkpoint AI need a compatible model and additional dependencies on the host PC; the one-line install includes neither. Installing the dependencies does not download a model. These two AIs sit only at Uprising tables, and no model file is published at present.

[AI types and requirements]({{< relref path="guides/choosing-ai.md" lang="en" >}})

## Images and saves

Original card and board images are not included in the public source or the one-line install; the text interface works without them. Details for connecting local images are in the [repository guide](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/local-images.md).

Saves remain on the server PC. With the one-line install they are in the game folder's `saves`, and updating with the same line keeps them. When updating a source install, keep your save folder and existing model files, and read [saving and updates]({{< relref path="guides/controls.md" lang="en" >}}).
