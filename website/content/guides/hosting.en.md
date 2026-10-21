+++
title = "Hosting a room"
description = "Run the server, create a room, and send friends the game link."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
weight = 20
[params]
source_ref = "e7e9ad4f"
sources = ["docs/remote-play-host-guide.md", "docs/remote-play-player-guide.md", "docs/multiplayer-design.md"]
+++
The host installs and runs the server and manages rooms and saves. Guests join through a link. The host also needs to claim a human seat in the game room.

First prepare the project and launcher using [your first game]({{< relref path="guides/first-game.md" lang="en" >}}). This guide covers private games over a local network or Tailscale.

## 1. Choose a connection

| Where guests are | Connection |
| --- | --- |
| Same Wi-Fi or wired network | Host PC's LAN address |
| Different locations | Install and sign into Tailscale, then share the server PC |

Avoid guest Wi-Fi that isolates devices. For remote guests, follow [Tailscale's machine sharing guide](https://tailscale.com/docs/features/sharing) and have them accept the share invitation.

## 2. Start a remote server

1. Open **Dune Imperium Server**.
2. Choose remote mode.
3. Select the LAN address for local guests or the Tailscale address for remote guests.
4. Start the server and create a game in the admin page.

Include yourself in the human-seat count. Fill remaining seats with AI; use app AI if you have no model files.

For terminal operation, replace both sample addresses with the host PC's actual address:

```bash
uv run dune-imperium-server --remote --host 192.168.1.20 --public-url http://192.168.1.20:8000
```

The host also connects through that LAN address. Remote servers autosave on turn handover by default.

## 3. Send the room link

Select the created game and copy its room link. Send the **entire link**, including `/#game=...`, together with the [guest guide]({{< relref path="guides/joining.md" lang="en" >}}).

Keep the admin link yourself; send guests the room link. New Tailscale guests also need the separate machine-share invitation.

## 4. During play and recovery

Keep the server PC and launcher running. Closing one guest's browser does not remove the room while the server remains active. Ask returning players to use the same room link and browser.

Before stopping, use **Save now** in the host panel. Loading a save after restarting creates a new room link. Send that new link and have players reclaim their original seats.

See the [detailed host guide](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/remote-play-host-guide.md) for firewall settings, address selection, releasing seats, and recovery. Hosting on native Windows 11 has been checked, but guests connecting to a Windows host from another PC have not been tested yet.
