+++
title = "Help and troubleshooting"
description = "Answers to installation, connections, seats, AI models, and save-file questions."
date = 2026-10-20
lastmod = 2026-11-06
draft = false
weight = 60
[params]
source_ref = "5d2fea34"
sources = ["README.md", "docs/remote-play-host-guide.md", "scripts/launcher/install.sh", "scripts/launcher/install.ps1", "docs/remote-play-player-guide.md", "docs/local-images.md", "docs/human-records.md"]
+++
## Can I play directly on this website?

The game server runs on your PC or the host's PC. This website provides information and installation/play guides. Start with [your first game]({{< relref path="guides/first-game.md" lang="en" >}}) or [joining a friend]({{< relref path="guides/joining.md" lang="en" >}}).

## Does playing alone use the official solo rules?

The target is the four-player game. A single human plays with three AI seats. Neither the official Rivals solo mode nor the original game's House Hagal automated opponent is implemented.

## What do guests install?

Only the host prepares the source and Python. Local-network guests open the room link in a desktop browser. Remote guests also install Tailscale and accept the machine-share invitation.

## Card or board images are missing

Original images are not included in the source. The text interface works without them. Remote guests should ask the host whether images are available.

## Search AI is not listed

In an original game this is expected: the search AI currently sits only at Uprising tables. In an Uprising game, check that the host has a model file and the additional dependencies. Installing packages alone does not create a model file. You can start with app AI without a model. [Choosing an AI]({{< relref path="guides/choosing-ai.md" lang="en" >}})

## The launcher will not open or the server fails to start

Read the launcher's error message first. If it says another program is using port 8000, pick another port with the launcher's **빈 포트 찾기** (find a free port) button.

After the one-line install, close the launcher and run the same install line again; if the install stops, its last line says why. For a terminal diagnosis, run this in the game folder (`.venv\Scripts\python.exe` on Windows):

```bash
.venv/bin/python -m dune_imperium.launcher.cli --check
```

After a source install, check that the project folder is present and `uv --version` works, then run from the project folder:

```bash
uv run python -m dune_imperium.launcher.cli --check
```

Check for an existing server using the port. See [validation scope]({{< relref path="about/support.md" lang="en" >}}) for Windows and Linux.

## The admin link does not let me in

- After an update, open the admin link once more. Since the hardening of 3 November 2026, the host is recognised by a session cookie signed with the key.
- If "too many wrong admin keys" appears, open the right link again after a minute.
- If a server started from the terminal refuses to start and mentions the admin key's length, change the key to 16 or more characters from letters, digits, `-` and `_`.
- If a page shows `invalid host header`, connect with an IP address, `localhost`, or the server PC's name (such as Tailscale's `<name>.<tailnet>.ts.net`).

The troubleshooting table of the [detailed host guide](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/remote-play-host-guide.md) has more symptoms and fixes.

## The room link will not open

- Check that the host server is running.
- Use the same regular LAN/Wi-Fi, or check Tailscale when remote.
- Use the entire link, including `/#game=...`.
- With a shared Tailscale PC, compare the host address in your Tailscale list with the address in the link.

If the address differs or connection still fails, consult the [guest]({{< relref path="guides/joining.md" lang="en" >}}) and [host]({{< relref path="guides/hosting.md" lang="en" >}}) guides.

## My seat is already in use after refreshing

Use the original browser profile and room address. Entering the same name alone does not restore your claim. After clearing cookies or changing devices, ask the host to release the previous claim before rejoining.

## I finished choosing, but the turn has not advanced

Check for **End turn ▶** or **Confirm ▶**. Some choices require explicit confirmation. The interface also indicates whether undo is available. [Controls]({{< relref path="guides/controls.md" lang="en" >}})

## Where are saves, and what if one stops loading after an update?

The default folder is `saves/` inside the project on the server PC. Rules/action-version changes can prevent old saves from loading directly. Finish ongoing games on the same code and models when possible.

Keep the originals and consult record migration if needed. Migrating a game record and resuming an old save unchanged are different features.

## Where can I report a bug or suggest a feature?

Use [GitHub Issues](https://github.com/jungcheolseung/Dune-Imperium/issues) and include:

- Operating system, browser, and code version.
- Enabled options and the action preceding the problem.
- Expected behavior, actual behavior, and the error message.

Before attaching saves or logs, check for admin links/keys and participant details. For connection problems, mention whether you use a local network or Tailscale.
