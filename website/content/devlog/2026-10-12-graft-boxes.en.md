+++
title = "Showing both grafted cards' boxes from the start"
description = "In Immortality's graft turns, the actions of both cards' Agent boxes are now offered together from the start (codec v143), and three rule outcomes that surfaced along the way were corrected."
date = 2026-10-12T11:54:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-12"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/graft-boxes-plan.md", "docs/rules/open-questions.md", "docs/worklog/2026-10.md"]
+++

## Opening the other card's effects again

The Immortality expansion lets a player play two stacked cards as one, called a graft. In a graft Agent turn you gain the effects of both cards, in addition to the board space effects, in any order (`[Immortality pp. 10-11]`). The engine, however, showed the Agent box of only one card at a time. To resolve the other card's effects you first had to press a "resolve the other card's box" action (`switch_graft_card`) to swap boxes.

After a game with friends, this was a nuisance: why press another button to see the other grafted card's effects? A first, screen-only stopgap put the card name and effect on each button. Then the thought came up that having the engine present both boxes from the start would be the more fundamental fix; after the cost was explained, the choice was the complete approach. The remaining design points (locking the other box while a multi-step choice is in progress, which defects to fix alongside, extending the AI observation) were settled on the recommended options.

## What changed

- **Both boxes appear from the start.** Box 0 is the card played, box 1 the graft partner. Box 1 actions reuse the same action id with `box=1`. `switch_graft_card` is gone; a row from either box resolves with one press. The decision window groups rows under "card name — Agent box" headings, with everything else under "Other choices".
- **While one box has a multi-step choice in progress, the other is locked.** After the first pick of "Choose two", between choosing and paying for Corrinth City, during remaining trashes, and during Signet steps, actions from the other box are withheld and the reason is shown. A deadlock where a choice that could no longer proceed kept the lock was found by the independent review and fixed.
- **The engine reuses the existing handlers.** Box 1 rows are computed through a virtual swap of 16 box-specific context key pairs, so the existing handlers run unchanged. A static-scan test and a random-game test fail if a new, unclassified key appears.
- **Action list and observation.** The action codec became v143 and the AI observation v31. `box=1` variants were added to the Immortality action list only; lists without graft are unchanged. The observation gained the two boxes' cards and pending flags (4 columns). In a trained network, each `box=1` row starts from the weights of the same action's unmarked row (for the play network of the time: 33,978 rows kept, 1,985 copied, 9 new, 1 dropped).

## Rule outcomes corrected on the way

The work set out to change only the shape of decisions, but handling the boxes separately exposed three defects in the old engine. Each is documented with its basis in the design document and pinned by tests.

1. Grafting Ghola onto Stitched Horror made the second box unable to pick its own two rewards; it received the first box's rewards again. The key is now per box.
2. The old engine tried a box swap in advance (a dry run) and misjudged boxes resolved by a choice as lapsing, hiding them. Partner boxes such as Piter and Dissecting Kit vanished this way; they are now reachable (`[Immortality pp. 10-11]`).
3. Ghola's copy shared its progress keys for Corrinth City, Arrakis Observer, and Signet Ring with the source box. Ghola copies the whole Agent box of the other card (`[Immortality p. 14]`), so the keys are now kept per box.

## Two rulings the same day

Two more changes followed, from an open question and a question that came up during play.

**Urgent Shigawire's boost and the graft partner (OQ-107, codec v144).** This card gives the next Bene Gesserit card all Agent icons and an extra card draw. Whether a graft partner that is a Bene Gesserit card also receives the draw was open; it was ruled that the partner does. The basis is the sentence that both grafted cards count as having sent the Agent: "Both played cards are considered to have 'sent' the Agent" (`[Immortality p. 10]`). If both are Bene Gesserit cards, the card played receives it. The same change fixed a turn-end defect. Previously the turn-end check dry-ran a box's ordinary resolution and read a box resolved by a choice as lapsing, so with Stitched Horror's mandatory "Choose two" still pending, "End turn" opened and pressing it lost the reward. Now End turn is not offered while a box still has a choice that gives an effect.

**Ghola and a boosted card (codec v145).** The question was whether, if Ghola copies the Agent box, the boosted draw should be copied too. Urgent Shigawire's draw is added to the Agent box and Ghola copies the entire box (`[Immortality p. 14]`), so a Ghola grafted to a boosted card now has the draw as well. A precedent in the same direction: Ghola with Carryall quadruples the base spice (`[FAQ p. 2]`). The review also turned up an existing defect: Throne Room Politics lost the added draw when it trashed itself with its own optional trash icon. It now keeps it, following the designer's public answer that when a card trashes itself by its own effect, its printed benefit is paid normally (OQ-022).

## What was checked

Checks at the v143 merge:

- 7,461 unit tests, static checks, and 62 browser E2E scenarios passed (a graft-specific scenario was added; two E2E seeds were re-chosen because the AI now plays graft turns differently).
- A 450-game automated soak went through 3,595 graft turns and 2,792 `box=1` actions without a failure. In 38,700 random walks under the lock conditions, the "no legal action" state occurred 0 times.
- An independent review ran a differential test, walking the old and new schemes 10,320 times each; its 1 blocking and 3 should-fix findings were all fixed. No hidden information leaked.
- Old records (codec below 143) are migrated by deleting `switch_graft_card` and tagging box 1 actions with `box=1`. All 6 local saved games migrated (0 field differences against the old engine over 5,344 moves), and all 285 positions of the problem set built from human games still resolved. On the 2,000-game record corpus (v142-c29f79d1): exact 560, equal 1,436, diverged 4 (1 Ghola with Stitched Horror, 3 lock cases), failed 0. An old order that hits the lock is not silently rewritten; it stops as a divergence.
- After v144, the same corpus check gave exact 1,861, equal 5, persistent difference 1, diverged 133. Of the 133, 132 were a turn end pressed while Beguiling Pheromones' mandatory trash was still pending, a move the new rules no longer allow. At v145, the 6 local saves and 285 problem positions all migrated, and there were 7,494 unit tests.

## What remains

- From this change on, saved games from codec v142, v143, and v144 do not open in the server. The records of finished games can be migrated with the record tooling.
- The AI now plays graft turns differently, so earlier heuristic-AI measurements pinned to the previous codec cannot be compared directly.
- The retraining run after the graft split ran only the control arm and stopped without a verdict (as decided). The play network was not changed.

## References

- [Graft boxes design and step-by-step record](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/graft-boxes-plan.md)
- [Graft boxes merge (codec v143)](https://github.com/jungcheolseung/Dune-Imperium/commit/3f5da2b0)
- [OQ-107 ruling and turn-end hold merge (codec v144)](https://github.com/jungcheolseung/Dune-Imperium/commit/420198c6)
- [Ghola boost draw merge (codec v145)](https://github.com/jungcheolseung/Dune-Imperium/commit/29f70d7c)
- [Open questions (OQ-107, OQ-057, OQ-022)](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/open-questions.md)
