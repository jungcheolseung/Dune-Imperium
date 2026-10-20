+++
title = "Your first game"
description = "Prepare the source, start the server, and create a game with one human and three AI opponents."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
weight = 10
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "pyproject.toml", ".python-version", "docs/remote-play-host-guide.md", "src/dune_imperium/cli/server.py", "scripts/launcher/Install Launcher.command", "scripts/launcher/Install Launcher.cmd"]
+++
Start with one human and three default AI opponents. You do not need model files or card and board images. You need a desktop browser and an environment that can run the game server.

Launcher operation has been checked on macOS. Windows scripts and CLI paths exist, but native Windows and separate Linux hardware checks remain. [Validation scope]({{< relref path="about/support.md" lang="en" >}})

## 1. Install Git and uv

Use Git to obtain the source and uv to prepare Python and the environment. See the [official Git downloads](https://git-scm.com/downloads).

Skip installation if these already work:

```text
git --version
uv --version
```

For uv, follow the [official installer instructions](https://docs.astral.sh/uv/getting-started/installation/). On macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows PowerShell with WinGet:

```powershell
winget install --id=astral-sh.uv -e
```

Reopen the terminal after installation and check `uv --version`.

## 2. Prepare the project folder

In the parent folder where you want to install, run:

```bash
git clone https://github.com/jungcheolseung/Dune-Imperium.git
cd Dune-Imperium
uv python install 3.14
```

Use your existing checkout if you already have one. uv prepares Python 3.14; you do not have to replace system Python or manually activate a virtual environment. [Installing Python with uv](https://docs.astral.sh/uv/guides/install-python/)

Run subsequent commands and launcher installation from this project folder.

## 3. Start the server

### Using the launcher

Open the appropriate file under `scripts/launcher`:

| System | Run once |
| --- | --- |
| macOS | `Install Launcher.command` |
| Windows | `Install Launcher.cmd` |

You can decline the optional search AI dependencies for your first game. That option installs packages, not a trained model.

After installation, open the **Dune Imperium Server** shortcut in the project folder. Choose local mode and start the server to open the game in your browser.

### Using a terminal

Alternatively, run the same commands in a macOS/Linux terminal or Windows PowerShell:

```bash
uv sync --locked --extra ui
uv run dune-imperium-server --autosave
```

Open `http://127.0.0.1:8000` in your browser. This command enables autosave. Keep the server terminal open while playing.

The dependency command above is for a new play environment. In an existing development/training environment, retain its dependencies with `uv sync --locked --extra rl --extra ui --extra train`.

## 4. Create a game

1. Set one of the four seats to human and the other three to app AI.
2. Choose the base game and any familiar expansion options.
3. Create the game and check whose decision is pending.
4. Choose a card and space, resolve remaining choices, then press **End turn ▶**.

App AI needs no model file. Without images, the game uses text cards and board displays.

## 5. Stop and continue

Use **Save** before stopping. The launcher and the terminal command above enable autosave, but autosave occurs at turn handover and may not preserve every pending choice within a turn.

Restart the server and load your game from the save list.

[Controls and saves]({{< relref path="guides/controls.md" lang="en" >}}) · [Choosing an AI]({{< relref path="guides/choosing-ai.md" lang="en" >}}) · [Invite friends]({{< relref path="guides/hosting.md" lang="en" >}})
