+++
title = "Redrawing the public build's pictures ourselves, and a card encyclopedia"
description = "So that the board and cards can be seen without card scans, we redrew the icons, boards, pieces and card faces ourselves. Every face was checked against the printed cards, a card encyclopedia was built, and the play server now shows these pictures by default."
date = 2026-11-11T18:00:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-10"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/own-pictures-plan.md", "docs/local-images.md", "scripts/own_pictures/README.md", "docs/worklog/2026-11.md"]
+++

## Background

The public repository contains no card or board scans and no pictures from the digital edition. So an installation without a pictures folder showed cards as text only, and the board as a text list. On November 10 the user said they wanted to distribute the project but were stuck on the card pictures, and the direction agreed was this: redraw the public build's pictures ourselves, close to the originals but without the logo, never tracing over an underlay or vectorizing automatically. Card faces carry the information a player needs. The user said, "Don't ask, just keep going. We'll merge it all at once later," so the sub-stages ran one after another and were merged together.

## What was drawn (merge `1935a870`, November 10)

- **Card faces.** Wording and icon layouts were transcribed from the Steam digital edition's per-card layouts and English text and from the official Korean edition. 192 Imperium and Tleilaxu cards, 131 Intrigue, 40 Conflict, 38 Contract, 36 Tech and 33 leader faces are drawn in HTML. All sizes are proportions of the card, and box heights were set by measuring whole printed faces at one text size so nothing overflows in either language or at hand size. Where the digital edition's wording differs from print, print was followed.
- **Icons and log pictures.** 53 icons and 26 action-log pictures as hand-written SVG.
- **Boards.** From layout tables and our icons, Uprising (English and Korean space names), the original board, the Rise of Ix overlays and the Ix board, and the Bene Tleilax board are drawn at the scans' proportions. The board screen runs as usual without a scan.
- **Pieces and tokens.** Seat pieces of 8 kinds × 4 colors, the Combat marker, Alliance tokens, the First Player marker, Maker Hooks, Sardaukar Commander, Shield Wall, and 6 card backs without the logo.
- The 47 location tiles and the Arrakeen Scouts illustrations are not drawn; popover text stands in for them.

## Faction marks: redrawn twice (November 10)

The first Faction marks were wrong. The user pointed out that the Faction icons are the original Dune symbols adapted for the game and asked us to look them up; compared with the 2021 film's Faction symbols, the Fremen (a cross disc) and the Bene Gesserit (a lens) were off. After the redraw the user still said, "These icons look cheap??? Is this the best you can do??", and decided that the Faction marks, like proper nouns, must keep the original shape, while other icons such as Solari only need the right feel. So the Faction marks were drawn again with proportions such as band thickness, the ends of rings and holes, and crossbar length matched to the original marks, the lines written by hand as curves, and pieces and tokens such as the sandworm, Agent and Dreadnought were redrawn too (merges `35d54218`, `2e8a1962`).

## Polishing, a full review and the card encyclopedia (merge `7c8673c6`, November 11)

- **The remaining faces.** 27 Bloodlines Imperium cards, 10 Navigation cards and 5 Objective cards were transcribed from printed cards and photos of the official Korean edition, so every card, Intrigue, Conflict, Contract, Tech, leader, Skill and Objective now has a face.
- **Full review.** The user asked for "a full visual review of every card, token, board space and so on". We made 276 comparison sheets, and 4 Sonnet review agents (approved by the user, about 790,000 tokens) compared them with the printed cards. The main session re-checked the 106 findings against print and fixed, among others, 10 Rise of Ix Contracts whose digital-edition layout belonged to another tile, 3 hidden spies, 2 red bands, 2 Korean faces and 3 wordings. Mismatches with a printed card of the same name from another box, and intended differences, were left out.
- **Korean boards.** Korean versions of the original board, the Rise of Ix pieces, Tuek's Sietch and the Research Station overlay were drawn separately.
- **Card encyclopedia.** "Card encyclopedia ▶" on the new-game screen and in the help window (also during a game). Tabs by kind, name search in Korean and English, filtering by box, ordering by Persuasion cost, and clicking a card opens its large face, its text and the rulings that mention it.
- Of the 1,216 lines of face wording and game text, no icon name falls back to plain text.

## The server's default pictures (merge `b3f6b25d`, November 11)

The user: "Make the default play with the images we generated, and if someone has their own card images or board data, let them play with those." The play server now shows these pictures by default. Card and board scans you own are used only with the server's `--pictures assets` or the launcher's "pictures folder", and whatever that folder lacks is filled with these pictures.

The drawing code moved into the repository under `scripts/own_pictures/`, and a test redraws everything each time and compares it byte for byte with the committed files (merge `1214c5e2`). The review tools that set the pictures beside printed cards read private pictures, so they are not part of the public copy.

## Verification and what is left

- Every merge ran the full pytest and the picture E2E scripts (`own_pictures` and others). A review by another tool (Codex) found no hidden-information or private-picture leaks, and pointed out that multi-Faction cards showed only the first Faction's ribbon; they now stack a ribbon per Faction, as in print.
- The 46 board-space popover pictures and the Scouts illustrations stay undrawn, as decided.
- At the time of writing, exporting to the public repository (stage 6 of the plan) was still the user's decision.
- Anyone who kept a pictures folder in the game folder's `assets` has to pick that folder once in the launcher to see the scans as before.

## References

- Public-build pictures, stages 0–5 ·
  After the film's Faction symbols ·
  Faction marks and pieces ·
  Polishing, full review, card encyclopedia ·
  Drawing code ·
  Default pictures
- Own pictures plan ·
  [Using pictures you own](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/local-images.md) ·
  Work log, November
