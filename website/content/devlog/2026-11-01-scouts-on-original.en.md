+++
title = "Arrakeen Scouts on the original game and the \"Collect\" click"
description = "Arrakeen Scouts can now be played on the original game, and later rewards and event and mission shares are now collected by the receiving player clicking."
date = 2026-11-01T23:00:00+09:00
publishDate = 2026-11-03
lastmod = 2026-11-03
draft = false
[params]
work_start = "2026-10-31"
retrospective = true
source_ref = "81ca9468"
sources = ["docs/worklog/2026-11.md", "docs/base-game-and-ix-plan.md", "docs/rules/arrakeen-scouts.md", "docs/rules/open-questions.md"]
+++

## Background

Arrakeen Scouts is a module of the Dire Wolf Game Room companion app, so it has no rulebook; its sources are the app's help text, schedule generation code and item definitions. It had been playable in Uprising since late September, and the last stage (P8) of the original game and Rise of Ix plan was moving it to the original game (user, October 31: "let's proceed with the P8 plan").

## What was moved to the original game

For an original game the app uses four original-only item bundles, without observation posts and Spies. The three subcommittees shared with Uprising use the original game's wording. New mechanisms include the Mentat public auction, Fremen Exchange, Stationed Support, and the secret faction choice of the original Covert Operation. Where the app and the rulebook do not decide, the user decided.

- In rounds with no Mentat, the late-appearing Mentat auction is removed from that round's draw (OQ-162).
- In Fremen Exchange, the seat that loses troops chooses whether they come out of the garrison or out of the Conflict (OQ-163).
- Scouts names follow the Korean of the Game Room app.

On screen, seven original-game spaces gained a mission token slot, and a faction chosen by Covert Operation is visible only to the choosing seat; other seats see "chosen". The Mentat auction shows bids in that auction's currency. The app AI gives 0 random answers at all three difficulties in the five original + Scouts combinations.

The merge gate (`cd81cfad`) had 12,159 tests in total, a 2,100-game soak over 12 kinds with 0 failures, a 200-game Uprising comparison all identical, 288 changed action-list configurations among 1,152 (all original + Scouts), and 77 browser E2E tests passing. Three hidden-information reviews found no leaks.

## The game where "two rounds later" seemed to vanish

On November 1 the user reported from a game played on WSL: "It was supposed to be getting Tleilaxu after 2 rounds, but it didn't come in." Tracing the records showed the engine was correct. The Offworld Operation chosen in round 4, "Tleilaxu 1 space two rounds later", was resolved at the start of the round 6 Scouts phase. But "two rounds later" is easy to read as round 7, and the automatic reveal passed within the same screen update as the Critical Moment auction.

We fixed only the screen first (`4ab1edf1`). The round number in which the effect occurs, such as "Round 6: …", was added to the secret choice's row and card, the revealed row, and the log. We also tried holding the reveal on screen, but set that aside as the next fix was judged better.

## "Collect", pressed by the receiving player

The user request was "don't make it automatic; make it so the player must click as a choice to receive it". It was changed in two parts.

1. **Revealed secret choices and the auction winner's reward** (`0078fc95`, codec v161, OQ-164). A row with no cost waits for one **Collect** from the receiving seat. Rows that are already choices (the picks in events and sales, subcommittees, mission participation) and secret-choice rows that cost something are unchanged. A card drawn by Collect cannot be undone.
2. **All remaining payouts** (`1da08e04`, codec v162, OQ-164 (a) and (b)). The user decided "both by click", and for the two design questions "both (a)". In the original Tap into Spice Reserves, each seat's 1 spice now goes to Collect, starting from the First Player. A mission's shares such as CHOAM Escort, Tleilaxu Offering, Valued Informants, Sponsored Research and Back Room Deal leave the board the moment they arise and become a share that seat will collect. The Collect window opens immediately, so even in the middle of a seat's own turn or inside another seat's action, it waits until that seat collects. Troops and mercenaries that enter the Conflict through a mission are left as they are (user ruling).

We also fixed a point raised in another game on the same day. After receiving spice from Seize Production, that Commander could still be recalled; a unit with strong effects this turn can no longer be recalled (`22223a75`, codec v160, OQ-029 (3)).

## What was checked

- Collect stage 1: Scouts soak of 2,400 games with 0 failures; of 2,000 recorded games, 412 unchanged and 1,588 replayed through a bridge that fills in Collect, 0 mismatches. 0 mismatches in human saves. Browser E2E on the merged tree, 78 tests passed.
- Collect stage 2: Scouts soak of 2,400 games gave 1 invariant warning (an Emperor track Spy waiting behind a Collect window; correct by design, accepted, and a rerun of 300 games all passed). Of 2,000 recorded games, 1,009 unchanged and 983 replayed through the bridge, and 8 differ only midway, with 0 mismatches.
- In same-seed comparisons against the engine before the change, games with random seats diverge from the point where the Collect window appears. This is an expected difference because Collect is a new decision, and the comparison tool declares that difference. No game changed outside the declared difference.

## What is left

- On November 2, in P8-1, we fixed a defect where the step in which Ilesa Ecaz sets cards aside never opened in Scouts games (before the Scouts phase, per OQ-122). On November 3, a hidden-information audit found and closed a gap there that exposed whether another seat had made a secret choice ([review summary]({{< relref path="devlog/2026-11-03-cloud-reviews.md" lang="en" >}})).
- Since this is a module with no official rulebook, the basis was the app's behavior and the user's rulings. The rulings can be seen in the game screen's ruling notices.

## References

- P8 engine merge ·
  P8 screen ·
  P8 app AI
- Revealed-round notation ·
  Collect stage 1 ·
  Collect stage 2 ·
  Recall floor
- [Arrakeen Scouts rule specification](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/arrakeen-scouts.md) ·
  Work log, November
