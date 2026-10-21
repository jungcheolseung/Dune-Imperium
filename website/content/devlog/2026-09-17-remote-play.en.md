+++
title = "The remote play server: seat access, synchronization, autosave"
description = "Authentication, change notifications, client synchronization, turn confirmation and autosave so several browsers can share one server's game, rehearsed on a single computer through a virtual-network address."
date = 2026-09-17T23:15:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-17"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/multiplayer-design.md", "docs/remote-play-guide.md", "docs/worklog/2026-09.md"]
+++

## The engine already knew about seats

The goal was for friends far away to join one game from their own browsers. We wrote a design document first and looked at what the code already had. The engine already had every decision owned by one seat, per-seat views (PlayerView), action-log filtering, an undo count and turn-end confirmation. What was missing was a network session layer.

- There was no way to prove which seat you held. The server only checked "is this a human seat".
- The summary and save metadata of an unfinished game contained the game seed. Because the engine is deterministic, the seed reveals every deck order.
- The server had no way to tell a browser that something changed, so the screen had to ask; one refresh took 3 to 4 requests and re-downloaded the whole action log.

Measuring a full-expansion game (726 steps) with 3 humans and 1 heuristic, there were 663 state-changing requests, and resending the whole action log on each refresh came to 57.3 MB per game. The same day we confirmed seven design decisions (how seats are claimed, using Tailscale, keeping undo, not storing names or tokens in save files, forcing remote mode on non-loopback addresses, autosave per turn, and the implementation order).

## Seat access and admin rights are separate

We split access into two kinds.

- **Seat access:** whoever claims an empty seat first gets it. The server issues a per-seat token in a cookie (HttpOnly, SameSite=Strict, limited to that game's path), and matches the token to the seat by value, not by cookie name. Neither actions nor views open for a seat that is not yours, and the credential check runs before the revision check.
- **Admin rights:** obtained through an admin link the host receives when starting the server. It allows administration such as releasing a seat on someone's behalf, but it never opens any seat's view, because the host is also a player.

In remote mode the seed of an unfinished game and training checkpoint paths are hidden from the summary. Listening on a non-loopback address requires `--remote`. The checks at this stage include forged requests that put another seat's token under this seat's cookie name and releasing or claiming with another seat's token. We also confirmed in code that all 55 prompt strings in the summary everyone receives are either fixed strings or interpolate only public values such as seat numbers and costs.

## One request per refresh, and notifications that carry only a signal

We merged a refresh into a single snapshot request returning the summary, view, available actions and the tail of the action log. The server decides where the log increment starts: undo retroactively changes earlier entries and the end of a game lifts the hiding, so when the range marker does not match, the whole log is sent again. For the same full-expansion game, one refresh went from 4 requests and 120.7 KB (gzip 12.3 KB) to 1 request and 14.6 KB (gzip 3.3 KB), and the cumulative total per game from 64.8 MB (gzip 6.7 MB) to 8.3 MB (gzip 1.81 MB).

On top of that we added change notifications. The server pushes a signal carrying only eight public fields over SSE, and a client requests a snapshot only if the signal differs from its screen. The notification carries nothing private, and a test pins its key set. With three browsers, a change appeared on another screen in 241 ms. A screen whose stream is blocked (three consecutive failures, or no first signal within 5 seconds) falls back to polling every 2 seconds. Presence (`online`) travels the same way, so a released seat shows offline immediately, and a reclaimed seat is not turned off when the old connection closes later. Shutting down used to take 3.2 seconds with an error log because of open streams; changing the shutdown handling made it 0.32 seconds with a clean log.

## Two cases where the client ran ahead of the server

Building the server was one thing; whether the browser follows it correctly was another. A check that every screen converges to the server state after each move by the seat the server names exposed two races (`90bb420`).

1. A notification about seat changes only triggered a request to reload identity, and when its response arrived late the summary on screen went back in time. After the opponent had confirmed the turn end, the page still waited for that confirmation, and no further notification came, so both sides waited on each other. We reproduced it by delaying a response by 0.7 seconds. An earlier "action buttons never appear, 30-second wait" symptom had the same shape, but we had not reproduced that exact run, so we recorded this as a confirmed defect that produces the same symptom. The summary state is now written only when opening a game or receiving a snapshot.
2. A joining page opens a stream and requests a snapshot at the same time; if that snapshot arrived after the notification about its own connection, the old player list came back. A notification arriving mid-flight now triggers one more refresh.

The same check found other defects: the server logging an error for a stream closed early (`9361562`), and the [hidden] attribute losing to CSS so the host saw a seed input field. We decided to keep these checks in the repository (`74667eb`), having seen the scripts vanish each time we changed machines.

## Turn confirmation and autosave

On a remote server a turn is not handed to the next seat until the player who pressed end turn confirms it. There was a gap in the promise that confirmation closes the undo window. The window is read from the action log, and the log closes only when the next seat acts, so if the next seat was a human who had not yet moved, the confirming seat could undo and take the turn back (`e3d4bac`). A floor in the session now stops undo below the confirmed point; the floor is not saved, so loading a save from that moment asks that seat to confirm once more.

Autosave runs when the turn passes on (after confirmation, after a move that hands the decision to another seat, and at game end). There is one slot per game, replaced atomically; the document is built and written under one lock so that two requests finishing almost simultaneously cannot overwrite a newer document with an older one. Playing a full game with 3 humans and 1 heuristic, the base game autosaved 112 times with a median of 3.1 ms (max 6.1 ms), and all expansions 89 times at 3.2 ms, so we left it as a synchronous write in the request thread. The host screen gained a saved-games list and an "autosave" mark, and a player waiting while the server is gone sees "server connection lost". A test that kills the server process, restarts with the same save folder and loads also passed (the saved state was within one turn).

## The rehearsal: one computer, a virtual-network address

To be clear, this was not a record of playing with friends. The rehearsal ran on a single Mac mini. We opened the server only on that computer's Tailscale address and connected the browsers to that same address. It is the same machine, so it was not a connection across the internet, but it did test the same environment friends would use: plain HTTP, which is not a secure context. Cookies are HttpOnly and SameSite=Strict but have no Secure attribute (a Secure cookie is dropped over plain HTTP). Because the server listens only on that address, a connection to `127.0.0.1` is refused.

We applied network emulation in the browser's developer tools to the friend-side screen only (all expansions, first visit with an empty cache).

| Line | Time until the table is playable | Until all images load | Downloaded | Time for a move to show on the other screen |
| --- | ---: | ---: | ---: | ---: |
| 100 Mbit/s, RTT 20 ms | 0.2 s | 1.8 s | 18.5 MB | 29 ms |
| 10 Mbit/s, RTT 120 ms | 0.8 s | 16.3 s | 18.6 MB | 158 ms |

Almost all of the download is two board scans (11.6 MB and 6.3 MB), and a reload downloads only 0.03 MB in both cases (cache). The table is playable within a second even without images, so we did not make a smaller web version and will only do so if it proves slow in real play.

The rehearsal also exposed a defect in the server launcher. If Tailscale is off, that address does not exist on the machine, yet the tool printed the admin link before the server had failed to start. It now probes the address and port first, explains the reason without printing a link (with a Tailscale hint for non-loopback addresses) and exits with code 1 (`8896ec8`).

## What is left

We kept what was not verified as a checklist in the operations guide: a real game across the internet, a Windows (WSL2) host, the notification sound actually playing (the browser's autoplay policy), keeping a connection for hours (reconnecting after sleep or a Wi-Fi switch), and how a rollout AI seat feels. What came out of real games with friends continues in October in [the launcher and play feedback]({{< relref path="devlog/2026-10-11-launcher-feedback.md" lang="en" >}}). The final test count at this stage was 1,732.

## References

- [Remote access: seat claims and an admin key](https://github.com/jungcheolseung/Dune-Imperium/commit/e6b9c9da)
- [Client synchronization fix](https://github.com/jungcheolseung/Dune-Imperium/commit/90bb420)
- [Slice 4 merge](https://github.com/jungcheolseung/Dune-Imperium/commit/de709423)
- [Autosave when the turn passes on](https://github.com/jungcheolseung/Dune-Imperium/commit/903090d6)
- [Tailscale address rehearsal](https://github.com/jungcheolseung/Dune-Imperium/commit/ff380679)
- [Refuse an unlistenable address before printing a link](https://github.com/jungcheolseung/Dune-Imperium/commit/8896ec8)
- [Remote multiplayer design document](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/multiplayer-design.md)
- [Operations guide](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/remote-play-guide.md)
