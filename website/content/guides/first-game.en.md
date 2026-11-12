+++
title = "Your first game"
description = "Install the game, start the server, and create a game with one human and three AI opponents."
date = 2026-10-20
lastmod = 2026-11-06
draft = false
weight = 10
[params]
source_ref = "5d2fea34"
sources = ["README.md", "pyproject.toml", ".python-version", "docs/remote-play-host-guide.md", "src/dune_imperium/cli/server.py", "src/dune_imperium/server/static/index.html", "src/dune_imperium/server/static/screens.js", "scripts/launcher/install.sh", "scripts/launcher/install.ps1", "scripts/launcher/Install Launcher.command", "scripts/launcher/Install Launcher.cmd", "scripts/launcher/install-wsl.sh"]
+++
Start with one human and three default AI opponents. You do not need model files or card and board images. You need a desktop browser and an environment that can run the game server.

The launcher and server have been checked on macOS, native Windows 11 and WSL2 on Windows. A few manual checks remain (such as guests connecting from other PCs to a Windows or WSL host), and the launcher window on a Linux desktop has not been checked. The one-line install was checked on an Apple Silicon Mac and on Windows 11 on 2026-11-06. [Validation scope]({{< relref path="about/support.md" lang="en" >}})

## 1. Install with one line (no Git or Python needed)

On macOS and Windows one command line installs everything. The game files, uv, Python 3.14 and the server packages go into one `Dune Imperium` folder in your home folder; finally it makes the launcher shortcut and opens the launcher.

macOS: open the **Terminal** app (Applications → Utilities) and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.sh | sh
```

Windows: open **PowerShell** from the Start menu and paste:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/jungcheolseung/Dune-Imperium/master/scripts/launcher/install.ps1 | iex"
```

To update, close the launcher and run the same line again; saves and launcher settings stay. To remove the game, delete the folder. More details are on [downloads and installation]({{< relref path="downloads/_index.md" lang="en" >}}).

If you installed with one line, skip sections 2 and 3 and go to [4. Start the server](#4-start-the-server). On Linux and WSL2, install from source as below.

## 2. Installing from source: Git and uv

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

## 3. Prepare the project folder

In the parent folder where you want to install, run:

```bash
git clone https://github.com/jungcheolseung/Dune-Imperium.git
cd Dune-Imperium
uv python install 3.14
```

Use your existing checkout if you already have one. uv prepares Python 3.14; you do not have to replace system Python or manually activate a virtual environment. [Installing Python with uv](https://docs.astral.sh/uv/guides/install-python/)

Run subsequent commands and launcher installation from this project folder.

## 4. Start the server

### Using the launcher

After the one-line install the shortcut is already there: skip the table and open **Dune Imperium Server** in the game folder.

After a source install, run the appropriate file under `scripts/launcher` once:

| System | Run once |
| --- | --- |
| macOS | `Install Launcher.command` |
| Windows | `Install Launcher.cmd` |
| WSL2 on Windows | `scripts/launcher/install-wsl.sh` in a WSL terminal |

You can decline the optional search AI dependencies for your first game. That option installs packages, not a trained model.

After installation, open the **Dune Imperium Server** shortcut in the project folder. Under WSL the shortcut is in the project folder under `\\wsl.localhost\<distribution>\…` in Windows Explorer. Choose local mode and start the server to open the game in your browser.

### Using a terminal

After a source install you can instead run these commands in a macOS/Linux terminal or Windows PowerShell:

```bash
uv sync --locked --extra ui
uv run dune-imperium-server --autosave
```

Open `http://127.0.0.1:8000` in your browser. This command enables autosave. Keep the server terminal open while playing.

The dependency command above is for a new play environment. In an existing development/training environment, retain its dependencies with `uv sync --locked --extra rl --extra ui --extra train`.

## 5. Create a game

1. Under **Base game**, choose Dune: Imperium - Uprising or the original Dune: Imperium.
2. Set one of the four seats to human and the other three to app AI.
3. Choose the rule options. The new-game screen opens with Player 1 as First Player, leader draft, CHOAM, promo cards, Bloodlines, Tech, Immortality, Go to 11 and Epic Game Mode switched on. Rise of Ix, original cards and Arrakeen Scouts are off. Uncheck them all to learn the base game alone.
4. Create the game and check whose decision is pending.
5. Choose a card and space, resolve remaining choices, then press **End turn ▶**.

With the original game chosen, the CHOAM and original-cards boxes are locked, and Epic Game Mode opens only with all of Rise of Ix. With both Rise of Ix and Tech on, a choice appears for how much of Rise of Ix to use (all of it, leaders and Tech tiles only, or Tech tiles only). Player 1 as First Player and the leader draft are project conventions, not official rules.

App AI needs no model file. Without images, the game uses text cards and board displays.

## 6. Stop and continue

Use **Save** before stopping. The launcher and the terminal command above enable autosave, but autosave occurs at turn handover and may not preserve every pending choice within a turn.

Restart the server and load your game from the save list.

[Controls and saves]({{< relref path="guides/controls.md" lang="en" >}}) · [Choosing an AI]({{< relref path="guides/choosing-ai.md" lang="en" >}}) · [Invite friends]({{< relref path="guides/hosting.md" lang="en" >}})
