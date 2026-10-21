+++
title = "Joining a friend’s room"
description = "Join through a host’s link without installing the game source or Python."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
weight = 30
[params]
source_ref = "e7e9ad4f"
sources = ["docs/remote-play-player-guide.md", "docs/remote-play-guide.md"]
+++
If a friend has already created a room, you do not need the source or Python. Prepare a current desktop browser, allow cookies, and get the **complete room link** from the host.

## On the same network

1. Connect to the same regular Wi-Fi or wired network as the host.
2. Open the complete link, including `/#game=...`.
3. Enter your name and join an empty human seat.

Images and AI run on the host. You do not need copies of their card or model files.

## From another location

The documented method uses Tailscale.

1. Install [Tailscale](https://tailscale.com/download) and sign in with your account.
2. Accept the host's **machine-share invitation**.
3. Check that the host PC appears in Tailscale.
4. Open the **game room link**, then enter your name and choose a seat.

The share invitation grants access to the PC; the room link opens a specific game. They are separate links. Tell the host if accepting the invitation fails. [Tailscale sharing](https://tailscale.com/docs/features/sharing)

If the shared PC appears at a different address, compare the Tailscale address with the room link and confirm with the host. Change only the address, keeping the port and `/#game=...` intact.

## Refreshing or rejoining

Use **the same room link and browser profile**. Your claim is associated with a browser cookie, not just your name. An incognito window or another browser may count as a new connection.

If you cleared cookies or changed devices, ask the host to release your old claim. If the old browser still works, you can leave the seat through the player menu before moving.

## Disconnections

| Symptom | Action |
| --- | --- |
| Room link will not open | Check the network/Tailscale and that the host server is running |
| Server disconnected | Restore your connection and refresh the same link; ask the host if it persists |
| Seat already in use | Use the original browser/profile or ask the host to release it |
| Asked to use a new room link | Get the new link for the restored game from the host |

See [controls]({{< relref path="guides/controls.md" lang="en" >}}) for game actions and [help]({{< relref path="help/_index.md" lang="en" >}}) for other problems.
