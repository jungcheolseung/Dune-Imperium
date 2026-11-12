+++
title = "Hosting a room"
description = "Run the server, create a room, and send friends the game link."
date = 2026-10-20
lastmod = 2026-11-03
draft = false
weight = 20
[params]
source_ref = "81ca9468"
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
4. Start the server and create a game in the admin page, choosing the base game, expansions and seats.

Include yourself in the human-seat count. Fill remaining seats with AI; use app AI if you have no model files. Original-game tables seat only the app AI, heuristic and random AI.

With the launcher on WSL, a remote-mode server accepts connections on every address, and the admin link opens in Windows as `127.0.0.1`. The room link you send keeps the address you chose. If guests cannot open a LAN address, the Windows firewall is blocking it; use the Tailscale address.

For terminal operation, replace both sample addresses with the host PC's actual address:

```bash
uv run dune-imperium-server --remote --host 192.168.1.20 --public-url http://192.168.1.20:8000
```

The host also connects through that LAN address. Remote servers autosave on turn handover by default.

When you set the admin key yourself in the terminal (`--admin-key` or `DUNE_IMPERIUM_ADMIN_KEY`), it must be **16 or more** characters from letters, digits, `-` and `_`. A shorter key, or one with other characters, makes the server say why and refuse to start. Without a key the server makes a new one at each start. The launcher makes a key that follows this rule by itself.

## 3. Send the room link

Select the created game and copy its room link. Send the **entire link**, including `/#game=...`, together with the [guest guide]({{< relref path="guides/joining.md" lang="en" >}}).

Keep the admin link yourself; send guests the room link. New Tailscale guests also need the separate machine-share invitation.

A room with human seats opens as a **waiting room**. Guests enter a name and press **Join**; the game does not run until every human seat is filled. Then anyone who joined presses **Start game ▶**, and the server assigns the people's seats at random.

## 4. During play and recovery

Keep the server PC and launcher running. Closing one guest's browser does not remove the room while the server remains active. Ask returning players to use the same room link and browser.

Before stopping, use **Save now** in the host panel. Loading a save after restarting creates a new room link. Send that new link and have players reclaim their original seats.

## After an update

Since the server hardening of 3 November 2026, the admin browser receives a session signed with the key as its cookie, not the key itself. A browser that used an earlier version must **open the admin link once more** after the update to be the host again. With the same key, a restarted server keeps it as host for 30 days; after a key change, open the admin link again. More than five wrong admin links in a minute are refused for a while; open the right link again after a minute.

See the [detailed host guide](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/remote-play-host-guide.md) for firewall settings, address selection, releasing seats, and recovery. Hosting on native Windows 11 and on WSL has been checked, but guests connecting to a Windows or WSL host from another PC have not been tested yet.
