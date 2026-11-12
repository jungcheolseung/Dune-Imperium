+++
title = "Reasons for every choice you cannot make, and five deferred table effects"
description = "We finished the last eight rows of the work that shows choices you cannot make right now, greyed out with a reason. We added effects such as a bought card flying to its buyer and an Alliance changing hands, with a switch to turn effects off."
date = 2026-11-11T22:30:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-10"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/unavailable-options-plan.md", "docs/ui-improvement-plan.md", "docs/worklog/2026-11.md"]
+++

## Background

On September 29 the user asked that choices you cannot make right now be shown greyed out with a reason instead of hidden, and on September 30 decided that "stage 3 is done in full". Of the plan's 18 rows, 10 were finished by October and eight were left. The principles are the same as at the start: only the engine decides what is legal, the reason on a greyed row is the very engine check that filters that choice, and it is sent only to the deciding seat.

This time we also built the five effects deferred from the October 8 "game-like effects" stage.

## Reasons for choices you cannot make: finishing stage 3

On November 10 the eight rows were compared against master again, and the work followed the order the user approved ("Yes, proposed order").

- **Faction choices and capped acquisitions.** In the Faction choices of Intrigue cards, Agent cards and Reveals, Factions you cannot pick are greyed: "Already at the top", "Already named for this effect", "Needs N Influence to lose (have M)", "No opponent has more Influence than you". An acquisition over a cap reads like "Costs 5: only a card costing 3 or less".
- **Tech tiles.** Each tile shows its reason (not enough spice or Solari, the price after returning all of Rise of Ix's negotiators, Advanced Data Analysis without a spy), and the tile on the board is dimmed too.
- **Multi-line Intrigue cards and the long tail.** Intrigue lines that cannot be used, the Contract VP threshold on Reveal, leader Signet abilities, "-OR-" boxes, and card-specific acquisition conditions.
- **The space popover (row 18).** Opening a board space dims the cost options you cannot pay there now, with a reason badge. This was the user's choice "(a) one line in the space popover".
- **Arrakeen Scouts' Political Equilibrium** (November 11). It is the only window that chooses a Faction to lose Influence from your highest Faction, so every Faction that is not highest is greyed with "Not your highest Faction (highest: Fremen 3)". Ties stay choosable, and if all are zero there is one confirmation.

Each batch is pinned by tests that compare the old filters with the new checks on seeded games made poorer and richer, and the reasons were checked to stay the same when hidden information is re-dealt (leaks). In the engine gate's identity check only the greyed rows changed, so with a declared difference that exempts just that part, all 360 games were identical. Building the legal action list did not get slower. Each batch had an independent Claude review and a review by another tool (Codex), and all findings were applied.

## Five deferred effects (merge `ad46917e`)

- **A bought card:** flies from where it was shown among the shared cards to the buyer's discard pile, deck or hand count.
- **Alliances:** a gain, transfer or loss banner ("Fremen Alliance gained!", and on a transfer, who it was taken from) while the token flies between the Faction row and the seat panel. Influence cubes slide when their space changes.
- **Conflict cards:** go from the Conflict space to the winner only in games where the winner keeps the card. In the original game the card stays, so it does not fly.
- **Round clean-up:** spice drops onto each empty Maker space, the placed Agents return to their seats one by one, and the First Player marker moves.
- **Turning effects off:** one checkbox under "This screen" at the top of help turns off card notices, banners and motion. It is kept in that browser only; sounds and the log stay.

All of them read only the public events filtered per seat and the screen state, so there are no new engine events and nothing hidden is shown. The server does not wait for effects, so turns do not slow down. A new E2E, `table_motion`, plays a seeded game to the end and matches each movement's start and end against what it reads separately from the log and the screen, with screenshots in both languages at PC and phone sizes.

## What is left

- The effects have not yet been seen in a real remote game (normal speed) with friends.
- When several Agents on the same space return, they start overlapped from the middle of the space.

## References

- Stage 3 batches one and two ·
  Batches three and four, and row 18 ·
  Political Equilibrium greyed Factions ·
  Deferred effects
- Unavailable options plan ·
  UI improvement plan ·
  Work log, November
