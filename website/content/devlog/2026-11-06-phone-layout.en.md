+++
title = "A phone layout and panel toggles on the PC"
description = "We laid out the screen separately so a whole game can be played on a portrait phone, and on the PC the hand, players, shared cards and log panels are switched on and off from the header."
date = 2026-11-06T15:00:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-06"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/mobile-ui-plan.md", "docs/ui-improvement-plan.md", "docs/remote-play-player-guide.md", "docs/worklog/2026-11.md"]
+++

## Background

Joining a remote game from a phone just shrank the PC layout, so the board, the hand and the decision panel were hard to see together. On November 6 the user opened a session for a phone screen, and that session surveyed a 375×812 touch screen and wrote a plan. The scope the user chose was "as recommended, Android only": play a whole game on a portrait phone with the phone alone, leave screens 600 px wide and over unchanged, and verify with Playwright's Chromium phone emulation. The same day came a request to switch panels on and off on the PC too.

## The phone layout (merge `c08967e1`)

- It applies only below 600 px wide. The screen is one view (board, hand, players, shared cards, log) plus the decision panel and five tabs at the bottom; the other menus are under ☰ in the header.
- An Agent turn is played with taps alone. Choosing a card moves to the board view, and a space button does the same as the space glowing on the board. The board can be zoomed.
- Hover previews and log highlighting are on only on devices with a mouse. The room link, the review bar and choice boxes were enlarged to finger size.

One independent review agent, focused on the action list a seat is shown, raised six points, all fixed. For example, the same card and space choices now appear on the phone only as rows in the decision panel, and the screen is redrawn when the width crosses 600 px. A review by another tool (Codex) found no exposure of hidden information and pointed out three E2E checks that could pass while checking nothing; they were fixed (and the fixed checks were confirmed to fail on deliberately broken code).

## Panel toggles on the PC (merge `262216fd`)

- Toggles in the header switch the hand, player status, shared cards and log panels on and off. The toggles exist only from 700 px wide; from 1200 px they are laid out in full, and at 700–1199 px they fold into "View ▾". The room of a hidden panel goes to the board and the decision panel. The setting is kept in that browser.
- If a hidden panel is needed for the current decision, a dot marks it while it stays hidden. When an Agent turn is played with the hand hidden, the first step ("① Card") shows the hand.
- The toggles took the spare room in a 1366 px header and the seed and rules badges were cut off, so the user decided the badges do not need to be visible all game. They moved to the status line's description and to "This game's setup" at the top of help.
- During implementation a defect was caught: hiding the players panel let the grid pull the middle into the first column, and the board vanished.

The same day, the title of the game screen and the launcher became one, "Dune: Imperium" (Korean "듄: 임페리움"), whatever the game (merge `63ef2e49`).

## Verification and what is left

- Phone layout: full pytest and the browser E2E batch (including the new phone checks) ran, and after the review fixes the 11 E2E scripts covering the touched code passed.
- Panel toggles: the batch of 82 E2E scripts and the checks touched by the badge change passed. Being a layout and CSS change, it had no independent review; the diff was read directly before merging.
- A game on a real Android phone has not been played yet. Address-bar height, reconnecting after the screen turns off and on, and sound effects cannot be seen through emulation.
- On the phone, cards in the hand cannot be dragged to reorder them.

## References

- Phone layout ·
  PC panel toggles ·
  Screen title
- Phone layout plan ·
  UI improvement plan ·
  [Remote player guide](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/remote-play-player-guide.md) ·
  Work log, November
