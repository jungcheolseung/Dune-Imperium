+++
title = "Downloads and installation"
description = "Install from source, or join a friend’s room without installing the game."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
weight = 20
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "pyproject.toml", "docs/remote-play-host-guide.md", "scripts/launcher/Install Launcher.command", "scripts/launcher/Install Launcher.cmd"]
+++
The available installation method is currently **from the project source**. As checked on October 20, 2026, no standalone installer or trained model has been published as a GitHub Release.

[Source on GitHub](https://github.com/jungcheolseung/Dune-Imperium) · [Start your first game]({{< relref path="guides/first-game.md" lang="en" >}})

## What do you need?

| Goal | Requirements |
| --- | --- |
| Play against AI on your PC | Source code, Git, uv, and the server environment |
| Host a room for friends | The above, plus a network guests can use |
| Join a friend's room | Desktop browser and room link; Tailscale when connecting from elsewhere |

Guests do not need the source, Python, or model files. Go to [joining a room]({{< relref path="guides/joining.md" lang="en" >}}).

## Operating systems

| System | Installation and validation |
| --- | --- |
| macOS | Clone the source, then install the launcher or use the terminal. Launcher checked on a Mac mini |
| Windows | Clone the source, then use the launcher installer or PowerShell. Native hardware validation remains |
| Linux | Terminal instructions; separate hardware validation remains |

The project uses Python 3.14. uv can install that Python version and manage the project environment. Install Git and uv, then follow the [starting guide]({{< relref path="guides/first-game.md" lang="en" >}}).

Run launcher installer scripts **inside the project folder**. They are not standalone installers you can download on their own. The guide uses a Git checkout, rather than presenting a source ZIP as a ready-to-run package.

## AI models are optional

The default app-style AI needs no trained model. Search AI and checkpoint AI need a compatible model and additional dependencies on the host PC. Installing the dependencies does not download a model.

[AI types and requirements]({{< relref path="guides/choosing-ai.md" lang="en" >}})

## Images and saves

Original card and board images are not included in the public source; the text interface works without them. Details for connecting local images are in the [repository guide](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/local-images.md).

Saves remain on the server PC. Keep your save folder and existing model files when updating, and read [saving and updates]({{< relref path="guides/controls.md" lang="en" >}}).
