+++
title = "A server admin page, and letting the AI play a person's seat"
description = "We built an admin page where the host looks after the server in a browser, and made it possible to hand a person's seat to the AI mid-game and take it back."
date = 2026-11-08T14:00:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-06"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/multiplayer-design.md", "docs/remote-play-host-guide.md", "docs/worklog/2026-11.md"]
+++

## Background

On the PC that keeps the play server running, seeing the admin link meant logging in to that machine every time. And when one person had to leave a remote game, the game had to be paused or ended. On November 6–7 the user asked for two things: an admin page for the server, and a way for "an AI to carry on playing when a player leaves, or when they want it to".

## The server admin page (merge `cf4f5f59`, November 7)

- **Who is admin.** Friends come in over the same Tailscale path, so "inside the network means admin" cannot tell them apart. The user chose "Tailscale account + key link". If the host names the admin account when starting the server, the server asks Tailscale which account the connecting device belongs to and, for that account, issues the same signed cookie as the key link. Devices shared with friends and tagged devices are refused. The key link still works. The account name lives only in the host's service settings; code and documents use placeholders.
- **The page.** `/admin` shows the server (commit, codec and observation versions, uptime, options), the machine (load, memory, disk), games in progress (seats, connections, room link, save now, free a seat, delete), saves (load, delete), and the last 200 log lines. The new-game screen gained a "Server admin" link.
- **Fixed in review.** A read-only review by another tool (Codex) confirmed four issues: the app AI's log recorded the moves it proposed as they were, so cards in a hand could leak to the log page (now only the server's own logs are collected); concurrent account lookups for the same address each started a process; the status response was missing its no-cache header; and a tagged device could be accepted as a login.

Deployed to the play server PC, the status response was 403 without a cookie and 200 after the account sign-in, and an unknown Host got 400.

## Letting the AI play a person's seat (merge `c4cc1fdb`, November 8)

We explained the design first and asked four questions. The user chose the following.

| Question | Choice |
| --- | --- |
| Who hands it over | The person in that seat (a button) and the host (the admin page). No automatic hand-over when a connection drops |
| Which AI takes it | The search AI if the server has a search AI model for that game, otherwise app AI Hard (for the original game, the search AI from the same day the [original-game model]({{< relref path="devlog/2026-11-08-original-board-search.md" lang="en" >}}) arrived) |
| When to take it back | Any time, from the next decision |
| How it is shown | A badge and a log line; thinking time is added to that seat |

- The seats as created and who is playing them now were separated. While the AI plays, the person in that seat can still watch, read the log and take the seat back; actions, turn end and undo work only while the person plays.
- If the seat was waiting for its own turn-end press when it is handed over, the hand-over is that press. On taking back, any answer the AI was computing is discarded.
- A change of hands is an entry in the save's log. Loading sets up an AI of the same kind and seed at that point and rebuilds its moves. Moves played by the AI are left out of the human problem set. The save format number and the codec are unchanged; old builds that do not know the entry refuse such a save.
- On screen: "Let the AI play"/"Play myself" on the seat card, an "AI plays" badge on a seat the AI is playing ("Thinking…" while it searches), and a log line saying the AI took the seat. At 1366×768 the name line got cut off, so the button moved to the line below.

A review by another tool (Codex) found that if the old AI's computation raised an error between taking a seat back and handing it over again, the new AI stopped. An independent review ran 300 random operations × 3 seeds × remote and open rooms × immediate and paced play, comparing save and load every 7 operations, with 0 mismatches, and raised six low-severity points (auto-save on every change of hands, the seed when seats are handed over in a row, and so on). All were fixed. 23 new server tests and 12 deliberate mutations were all caught, and the new E2E `seat_takeover` passed.

## What is left

- The refusal of a real friend's device by the account lookup has not been seen yet.
- Automatic hand-over when a connection drops was not chosen by the user, so it is not there.

## References

- Admin page ·
  Letting the AI play
- Multiplayer design ·
  [Host guide](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/remote-play-host-guide.md) ·
  Work log, November
