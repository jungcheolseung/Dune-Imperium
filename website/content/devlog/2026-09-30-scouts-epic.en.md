+++
title = "Adding Arrakeen Scouts, Go to 11, and Epic Game Mode as options"
description = "Arrakeen Scouts, a mode with no official rulebook, was implemented and corrected against its source text. Go to 11 and Epic Game Mode were added, with games that leave Scouts and Epic off kept byte-identical. Scouts decisions the network never learned are answered by the heuristic."
date = 2026-09-30T15:42:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-27"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/worklog/2026-09.md", "docs/arrakeen-scouts-design.md", "docs/rules/epic-game-mode.md", "docs/implementation-audits/epic-game-mode.md", "docs/rules/open-questions.md"]
+++

## Three options and one principle

From September 27 to 30, three rule options were added.

- **Arrakeen Scouts:** a module in which subcommittees, missions, events, auctions, and sales are revealed round by round. It has no official rulebook; its source is the mode in the official companion app.
- **Go to 11:** a scoring variant introduced in the Immortality rulebook.
- **Epic Game Mode:** the longer-game variant of the Rise of Ix rulebook.

One principle guided all three: **a game with an option off must stay the same as before.** Adding options must not change the meaning of existing game records, saves, or training data. At each slice, the chance flow, the catalogue (4,425 rows by default), and the old observation columns of an option-off ruleset were checked against their old values and the reference values pinned again. Scouts and Epic were kept byte-identical, and Epic was additionally checked to leave the catalogues of 72 option-off rulesets byte-identical to the previous master. Go to 11 adds a single starting-score setting and behaves as before when off (apart from the state hash).

## Implementing Arrakeen Scouts

The engine carries only the four-player rules. The round layout is five subcommittees in round 1, missions in rounds 2–3, and events in rounds 4–7; a mid-game auction may appear in rounds 5–6 and a late auction in rounds 8–9, and a sale appears in whichever of rounds 8–9 has no late auction. Subcommittees are joined by taking a High Council seat, missions are stood on a space and collected by the first seat to visit it, and auctions are sealed bids.

Design decisions:

- **The schedule is drawn by chance in the round where it becomes public.** Drawing everything at game start would leave a hidden future in the engine state. Each draw depends only on earlier draws, so the distribution is the same while avoiding that. Subcommittees are drawn at the start of round 1 so they are not revealed before the leader draft.
- **The Scouts phase belongs to no seat's turn.** Like Control defence placement, it stands without a turn frame and keeps its own progress marker, to avoid it being counted in "this turn" effects or creating deadlocks.
- **Sealed bids and secret picks are confirmed privately, one seat at a time**, so that action numbers, public events, and the server's previews reveal nothing to other seats.

The work was split into ten slices (spec and catalogue, option skeleton, schedule and round flow, subcommittees, choice events and sales, missions, secret picks, auctions, server and screen, heuristic and cross soak), each as a `Play` and `Document` commit pair. When it finished on September 28, the action codec had gone from v111 to v119 and the observation from v21 to v25, with 2,694 pytest tests and 29 browser E2E scripts passing. Thousands of random and heuristic soak games had no failures. The soak found two bugs: a third domination by a seat that had placed a Prison Planet control marker, and a deadlock when an Intrigue-less visitor met a face-down Immediate contract of CHOAM Research (OQ-090). The independent review of slice 7 found and fixed paths where information leaked through the undo decision and the preview in the secret-pick phase.

## Batch review against the source text

With so many items, once the implementation was done the wording of every item was compared line by line with the English source text, in three batch reviews on September 29 plus remaining rulings on the 30th. Where the source is silent, a project convention was chosen and recorded as an open question with its reasoning.

- **Joining a mission.** A mission may be joined only if all the printed troops can be stood. The implementation had been letting a seat with a single troop join and stand what it had, a choice the source does not offer (OQ-088). In Immortality, missing troops can be made up by first returning specimens to the supply.
- **Auction rewards and bids.** Rewards go in rank order, ties starting from the first player (OQ-073). The Mercenaries bid cap is the number of troops that can be placed.
- **When to join a subcommittee.** An attempt to rebuild subcommittees as a board icon in free order within the turn collided with the English source and was reverted. A later ruling (OQ-076, alternative C) lets a seat join at any point in the turn in which it newly took a High Council seat, in the same free order as other effects (`[Main p. 9]`, a project convention). A limit—when joining was a turn's last effect, its cost and reward lines resolved after the turn closed and missed that turn's spice ledger—was confirmed by experiment, and was resolved by the October work that made turn end an explicit step (see [the October post]({{< relref path="devlog/2026-10-09-turn-end.md" lang="en" >}})).
- **Round Start order.** Reveal, Control defence placement (optional), then drawing cards (`[Main p. 8, 10, 20]`). The review found a stall in about 1% of Tech games, where a deferred Tech card draw slipped between defence placement and the hand draw, and it was fixed.
- **Greyed-out options.** The first step of showing choices that cannot be taken, with the reason, exposes the engine's own blocked-choice check unchanged. A comparison over 130,000 decisions from the same states found 0 differences in legal actions, and 0 information leaks.

After these reviews and rulings the codec was v123 (from v120 after the Go to 11 merge) and the observation v27 (from v25). Verification on the last batch was 2,851 pytest tests, 1,950 soak games with 0 failures, and 31 E2E scripts.

## Go to 11

A variant from the Immortality rulebook. In a four-player game the score marker starts at 0 rather than 1, and the Endgame opens at 10 points (`[Immortality p. 12]`). Using a variant from the original-game rulebook with Uprising, and allowing it only when Immortality is on, are project decisions (OQ-091). The new-game screen turns it on by default, while the engine and CLI default to off, so training and soak baselines do not change. That the end condition stays at 10 rather than becoming 11 is pinned by a test (`test_go_to_11_still_enters_endgame_at_ten`). Verification: 2,714 pytest tests, 30 E2E scripts, 2,200 soak games plus 900 after the Scouts merge with 0 failures, and 0 illegal actions in 4 checkpoint-seat games. The codec is v120.

## Epic Game Mode

A variant from the Rise of Ix rulebook (`[Rise of Ix p. 10]`). The game goes to 12 points, Conflict I is not used, and 5 random Conflict II cards go on top of 5 Conflict III cards. One Dune, the Desert Planet in each starting deck is replaced by Control the Spice, each player draws 1 Intrigue card, and the garrison starts with 5 troops. In Uprising there is one Conflict III card too few, so the rulebook tells players to add Economic Supremacy (`[Main p. 18]`).

The Rise of Ix expansion itself is not implemented; only the two cards this mode uses were brought in (a project decision, OQ-092). Economic Supremacy has no battle icon, and its two-arrow reward on one line is asked in printed order (Solari, then spice). With Go to 11 on as well, the game starts at 0 and ends at 12 (OQ-093). The Rise of Ix rulebook recommends Scouts for a longer game, so one fixed game with both options on is kept as a test.

Epic was built on a separate branch and verified with 2,813 pytest tests, 30 E2E scripts, and 1,200 `--epic` soak games with 0 failures. Merging it with the Scouts line on September 30 meant resolving 7 conflicting files (version comments, imports, labels); after merging, 2,968 pytest tests, 31 E2E scripts, and 1,150 automatic games with 0 failures passed. The merged codec is v124 and the observation v28.

## Scouts decisions the network never learned

Seating the network and search-AI seats in a Scouts game raised a problem. Existing checkpoints were trained without Scouts, and the outputs for new action slots start at zero. Playing the v111 baseline checkpoint (7081) against three heuristics for 200 games each, 82–91% of the seat's Scouts decisions offered only such untrained slots, and its choices degenerated to the first line.

- Sealed bids always confirmed 0, and Critical Moment bids were always 0.
- Secret picks were always number 0, and it never joined a mission.
- It always declined when offered a subcommittee, and almost always chose line 0 for events and sales.

So when all legal actions of a decision are untrained slots, a heuristic seeded from the agent seed answers instead. The search seat does not search those decisions, and inside simulations a heuristic seeded from the chance seed answers. A decision with at least one trained action in the mix is still chosen by the network ([implementation](https://github.com/jungcheolseung/Dune-Imperium/commit/dde069ff), [allowing the seats](https://github.com/jungcheolseung/Dune-Imperium/commit/408c33ff)).

In a paired comparison of 200 same-seed games (seat 0 against three heuristics), the win rate in the default configuration went from 46.0% to 45.5% (−0.5 points [−9.5, +8.5]), and with all expansions on from 84.5% to 90.5% (+6.0 points [0.0, +12.0], lower bound at 0). A heuristic in seat 0 on the same seeds wins 22.5% and 24.5%. The strength is similar or slightly better; what changed is that the seat now bids and joins missions and subcommittees. An independent review confirmed that a search seat's own decisions are bit-for-bit the same even when others' bids and secret picks change.

**This does not mean the network learned Scouts.** The heuristic simply answers decisions made of untrained slots, and Scouts is not part of the training configuration. The same rule applies generally to slots created during a codec migration, so files older than the current codec (the control 5081 has 43 such slots and 5600 has 16) hand `take_contract` decisions to the heuristic even on their own ruleset, 2–3 times in 10 games (with the same choice). Comparisons that use such controls are read with that in mind.

Mission pieces were also drawn on the board: stood troops as cubes in the seat colour, the Prison Planet control marker as a flag in the seat colour, bank goods at their printed size. Positions come from a table measured on the scan, and the E2E checks all 16 missions across six seeds. As a last check, one game was played through in the browser (seat 0 human, seat 1 a checkpoint, seats 2–3 heuristics; all expansions plus Epic, Go to 11 and Scouts; seed 7), which ended in round 8 at 12 VP. Joining a mission cannot be undone because the next step is a chance event, not because of a bug (OQ-010).

## What remains open

- Scouts has not been trained on. Whether to include it in training is to be decided separately.
- The effect of the heuristic fallback comes from one 200-game pair, and the all-expansions interval has a lower bound of 0. It shows the seat did not get weaker, not that it got stronger.
- For Epic's Economic Supremacy, whether the cost being asked is Solari or spice is not in the observation and can only be told by order. It needs another look when Epic games enter training.

## References

- [Scouts completion (slice 10)](https://github.com/jungcheolseung/Dune-Imperium/commit/44666254)
- [Go to 11 merge](https://github.com/jungcheolseung/Dune-Imperium/commit/1c86685b)
- [Epic merge](https://github.com/jungcheolseung/Dune-Imperium/commit/8b3780ee), [Epic and Scouts combination test](https://github.com/jungcheolseung/Dune-Imperium/commit/423596d0)
- [Scouts AI seats merge](https://github.com/jungcheolseung/Dune-Imperium/commit/b7cf49cf)
- [Subcommittee join timing (OQ-076)](https://github.com/jungcheolseung/Dune-Imperium/commit/88b9ea43)
- [Epic Game Mode rules spec](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/epic-game-mode.md), [Epic implementation audit](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/implementation-audits/epic-game-mode.md)
- [Open questions and rulings (OQ-073, 076, 088, 091–093)](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/open-questions.md)
