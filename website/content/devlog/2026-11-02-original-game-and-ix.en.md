+++
title = "Adding the original Dune: Imperium and Rise of Ix: P0–P8-1"
description = "The engine, which held only Uprising, now has the original game as a second base game and Rise of Ix as an expansion, and both base games can be mixed with all expansions."
date = 2026-11-02T23:00:00+09:00
publishDate = 2026-11-03
lastmod = 2026-11-03
draft = false
[params]
work_start = "2026-10-22"
retrospective = true
source_ref = "81ca9468"
sources = ["docs/base-game-and-ix-plan.md", "docs/worklog/2026-10.md", "docs/worklog/2026-11.md", "docs/rules/imperium-base.md", "docs/rules/rise-of-ix.md", "docs/app-ai-plan.md", "src/dune_imperium/content/rulesets.py", "src/dune_imperium/server/seat_kinds.py"]
+++

## Background

Until October 21, the engine held only four-player Uprising and the expansions on top of it. The user wanted the original Dune: Imperium and Rise of Ix played on the same engine, with one condition: "All expansions must be combinable with each other in various combinations. But either base or Uprising must be present" (October 27). So the original game became a second **base game** next to Uprising, and Rise of Ix an expansion that goes on either base game.

We also set what had to be kept. An existing Uprising game must not change by a single character, because saves, records and trained models are tied to that action list. At each stage we replayed Uprising games on the same seeds and checked that they gave the same results.

## Card data from the app instead of images

Uprising cards were transcribed by reading card images, and the full audit on September 26 found 114 confirmed errors. To reduce the same mistakes, the original game and Rise of Ix were transcribed from the Steam digital edition's data (its per-card attribute table, the layouts it draws card faces with, and its English text) (user decisions October 21 and 23). The first stage measured whether this method was usable. The counts for the 130 original-game and Rise of Ix components were identical across the rulebook, the community list and the app values. Building 82 Uprising cards by the same method gave 79 identical to the current records and 0 wrong values. The app data and its analysis stay only in the private assets repository; the public repository holds only names, numbers and the project's own notation.

## What was done in each stage

| Stage | Period / merge | Work |
| --- | --- | --- |
| P0 | October 22–25, documents only | Registered the original rulebook as an official source, wrote the original game and Rise of Ix rule specifications, rulings OQ-113–127 |
| P1 | October 27 `dda6ddb0` | The engine now reads each version's spaces, decks and leaders from one place, and gained a "base game" axis. Uprising unchanged |
| P2 | October 27–28 `420c77a5` | The original board's 22 spaces, Mentat, 18 Conflict cards, 8 leaders and the draft |
| P3 | October 28–29 `6352199d` | All original Imperium and Intrigue cards, and the promos |
| P5·P6 | October 29 `33e01710`·`a4393427` | The screen for playing the original game in the browser, and the app AI that plays it |
| P4 | October 30 `21f28a1f` | Rise of Ix on the original game: Ix board, dreadnought, Tech tile, Shipping track, Unload, cards and leaders, Epic |
| P5·P6 Ix | October 30 `4ef229ec`·`c6c14aef` | The Rise of Ix screen and app AI |
| P7 | October 31 `b0dfb2e5` | All expansions on either base game: original + Immortality and Bloodlines, Uprising + Rise of Ix, Uprising + original cards |
| P8 | November 1 `6eb8f0f5` | Original + Arrakeen Scouts ([written up separately]({{< relref path="devlog/2026-11-01-scouts-on-original.md" lang="en" >}})) |
| P8-1 | November 2 `3b42c827` | Choosing how much of Ix to use with Rise of Ix + Tech Module |

Some decisions were made by the user directly. The combination of the original game with the CHOAM Module was not opened (October 30). Uprising + Rise of Ix follows the Uprising rulebook's method: the CHOAM board overlay is half folded and covers the Assembly Hall and Gather Support side of the board. Whether Shipping and Accept Contract are among the covered spaces was decided by the user (OQ-159). In P8-1, without Arrakeen Scouts the choice is among "all of Ix", "Ix Tech tiles only" (the official combination in the Bloodlines rulebook) and "Ix leaders and Tech tiles only" (the companion app's combination); with Scouts it is between the first and the third (OQ-165). Rulings the official documents do not answer were not invented; they were recorded in the rulings ledger under OQ numbers. Where a choice differs from the source, the in-game help shows it as a ruling notice.

## Screens and AI

The original game is played on an original board image. The 22 space names, 6 leaders and the reserve card names use the names in the official Korean rulebook, and cards with no Korean source show their English face. The 100 original card faces were drawn from the app's layouts.

At first the app AI answered 26–29% of decisions at random in the original game (because the app's 160 abilities had not been transcribed). After all of those abilities were transcribed, random answers were 0 at all three difficulties in the original game, original + Rise of Ix, and the new combinations of P7, P8 and P8-1. Games on the same Uprising seeds make the same moves as before the transcription. For reference, two hard app AIs against two heuristics in the original game, 600 games, gave per-seat win rates of 49.5% to 0.5%. This is not a pass criterion; it is an observation that the original game's heuristic is weak. So we made six original-game spaces use the values of the same-named Uprising spaces, and in 1,000 games of 2:2 against the old heuristic the result in the original game was 36.1% [34.8, 37.4] (25% at even odds).

The search AI does not sit in the original game. The model has never been trained on it, and it was not measured in an original-game seat.

## What was checked

The same gate was run at every stage merge. Taking the P7 gate (`be1112d1`) as an example:

- All 11,469 tests passed.
- 200 Uprising games were compared step by step against the engine before the change, all identical. Of the 400 changed among the 1,152 action-list configurations, 0 were configurations sold as Uprising.
- Completion soak of 25 combinations: 0 failed games. 2,000 recorded games, human saves and 281 human-game problem spots replayed unchanged.
- Browser E2E and same-seed same-move checks (including the search AI seat).

In P3, 5,000 games on the two original decks were played to the end with 0 failures; in P8, 2,100 games over 12 kinds had 0 failures. Hidden information received a separate independent review at each stage. In P2 a defect was found and fixed where the secret faction chosen by Baron Harkonnen appeared in the server's live log; the P5 Ix and P8 screen reviews found no leaks.

## What is left

- House Hagal as an automated opponent in the original game, and 1-, 2-, 3- and 6-player setups, were left out of scope.
- The Korean faces of original cards will be switched in after photos of the official Korean edition are obtained.
- For the search AI to play the original game, a model must be trained by self-play on that version. This has not been started.
- Original-game leader faces were drawn with the app's character and ability boxes mixed with a background from the English edition scan (user decision). Some overlapping remains on the Helena Richese face.

## References

- Original game and Rise of Ix plan with results per stage
- P1 base-game axis merge ·
  P2 ·
  P3 ·
  P4 ·
  P7 ·
  P8 ·
  P8-1
- Original-game screen ·
  Original-game app AI ·
  Original-game heuristic space values
- [Original game rule specification](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/imperium-base.md) ·
  [Rise of Ix rule specification](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/rise-of-ix.md)
- Work log, October ·
  November
