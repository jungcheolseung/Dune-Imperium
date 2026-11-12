+++
title = "A finished game's course chart, and a breakdown of points"
description = "When a game ends, a line chart shows each seat's chance of finishing first round by round. The score window breaks down where each seat's points came from."
date = 2026-11-08T18:00:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-07"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/win-odds.md", "docs/worklog/2026-11.md"]
+++

## Background

On November 7 the user asked to "show each player's chance of winning from the current position in the game". We showed the design and a short measurement first and asked four questions. The choices were: numbers for all four seats from public information only, from round 1, at the start of each round, and in replays too. During the merge, though, the user reconsidered where it belongs: "It's right that it must not be visible during play; showing the course after the game ends seems right." So it lives only in the result window and in replays. The next day the user also wanted to see where points come from.

## The course chart (merge `b382ae0e`)

- **The number.** The search AI's four position values (E3) are turned into chances of finishing first with softmax(2.9 · value). It is the chance "if four AIs played on". The 2.9 was fitted on two test sets; either gave 2.7–3.1, independent of the round.
- **Is it right.** In 160 games with the UI's default rules, seats shown at 25% won 26.6% and seats shown at 55% won 55.2%. Round 1 is no better than chance (so is the answer from playing to the end), and the Brier score is 0.623 at round 5 and 0.505 at round 8 (0.750 for guessing 25% everywhere).
- **Public information only.** A spectator world that re-deals every seat as if it were an opponent was added. It also re-deals Y'rkoon's Navigation slots, Kota's Secret Project and drawn Twisted cards, and forgets cards known to others (OQ-149). The average over 16 worlds lost no accuracy compared with a seat's own view.
- **Only at round starts.** Reading in the middle of a round was worse than keeping the round-start number (Brier up to +0.19).
- **Server.** It does not answer for unfinished games, so nothing is computed during play. Once a game ends it is read through the room link, computed once per round-start position (not saved). Games without a model, such as the original game, get "not available".
- **Screen.** Under the ranking in the result window, a "How the game went" chart: one line per seat, the winner's thicker, a dashed 25% line, per-round marks and a table for screen readers. The replay bar gets a small chart with a vertical line at the cursor's round. The first design's in-game "♛34%" on the seat panel was dropped.

A review by another tool (Codex) confirmed three leaks in the spectator world (a drawn Twisted card's identity stayed real, known Intrigue cards were moved into hidden hands, and Conflicts were shuffled in box order), and all three were fixed. Tests that fail on the code before the fix guard them. This work also turned up similar leaks in the search AI's own worlds, which were fixed separately ([hidden information]({{< relref path="devlog/2026-11-11-hidden-information.md" lang="en" >}})).

## Breakdown of points (merge `60628603`)

The user: "I'd like to see what my current points are made of. Say 11 points: 2 of them from The Spice Must Flow, 4 from Influence, 1 from an Alliance …"

- The window the score button opens now starts with a "What the points are made of" table. It shows each seat's net points by source, with the existing round-by-round record below it.
- Columns: starting points, Influence, Alliances, The Spice Must Flow, Conflict rewards, battle icon pairs, Intrigue cards, card effects, the Tleilaxu track and Tech tiles. Each shows the Faction, card, Conflict or tile names, and zero columns are hidden. In a review, only points up to the cursor are shown.
- The server's score ledger splits each step's change per seat by source. Influence and Alliances are counted from the board, the rest from that step's public events. The engine, events, codec and saves are unchanged, so a game already in progress shows the breakdown from the beginning once the server is restarted with the new code.
- Tests check, on both boards × 8 expansion combinations, that the sources add up to every step's change and to the final score. Anything unexplained would go to "other", and it never appeared in any tested game.
- The review found that in the original game a Conflict reward was labeled with the wrong Conflict card's name (in the original game Conflict cards pile up). The totals were right; only the name was fixed.

## What is left

- How well the course chart matches games against people was not measured. With the original-game model the 2.9 can be refitted and the chart opened for the original game.
- The play servers have to be restarted to show both features.

## References

- Course chart ·
  Breakdown of points
- Course chart description ·
  Work log, November
