+++
title = "Separating the shared engine vocabulary from each expansion's data"
description = "We moved the engine's basic vocabulary out of the Uprising package into a shared layer and gave every card's ability record the same card-id structure. Through all four stages the same games ended with the same results."
date = 2026-11-06T09:00:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-03"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/content-core-refactor-plan.md", "docs/worklog/2026-11.md"]
+++

## Background

Because the engine was built starting from Uprising, the basic vocabulary that every game uses — the language card effects are written in (the effect DSL), the frame of ability records, Factions and icons, the formats of board and card entries — lived inside `content/uprising`. The original game, Rise of Ix, Bloodlines and Immortality packages borrowed it from Uprising, and sets imported each other in 23 places. On November 3 the user asked to manage the basic rules and each expansion's specifics separately, giving the coming Conspiracy expansion as the reason. The user agreed to a proposal to split the work into three stages (survey and plan → move and prove sameness → rewrite imports and enforce the dependency rules with tests). The condition was that the work change **nothing** in rule behavior or the codec.

## What changed

| Stage | Merge | Content |
| --- | --- | --- |
| 1 and 2 | November 4 `d5ca0fd5` | Shared vocabulary (effect DSL, ability record frame, Factions and icons, board and card entry schemas) into nine modules in `content/core/`, cross-set id tables and lookups into eleven modules in `content/registry/`. The old modules re-exported the same objects, so outside imports stayed as they were. Data imports between sets went from 23 to 1 |
| 3 | November 4 `a1397cce` | A map of 265 name pairs rewrote the imports of 306 files to the modules where the names are defined. The old modules and the import-order devices were removed (the cycles disappeared). Dependency rule tests: core imports only core; a set imports only core, configuration and itself |
| Part of 4 | November 4 `ede364e1` | Trash, discard, turn-start and acquire records of 37 cards keyed by card id in their own sets. Bloodlines, Immortality and Rise of Ix cards and leaders that sat inside the Uprising package moved to their own packages |
| Rest of 4 | November 5 `b6cdbc06` | 146 Agent box records and the Reveal choices into card-id tables, the icon condition, Tech tiles into core (the last import between sets disappeared) |
| Expansion flags | November 5 `c04aaf8c` | Six expansion flags scattered over cards became one `requires` (the set of game options a piece needs) |
| Agent boxes | November 6 `2642685b`, `7aec611d` | Where the engine compared box names as strings, it now asks the box's record. Ghola and Usurp are also recognized by standing records instead of card ids |

## How sameness was checked

At every stage the engine gate ran on the Mac mini.

- The 360 games recorded on master (200 standard Uprising games, 160 original-game and expansion games) were replayed step by step on the new code and were all identical with no declared differences.
- The action catalogs of 1,440 rule combinations, the digest of the observation encoding, and the 623 rows of the entity network's feature table matched master.
- 14 soak configurations, 2,000 recorded games, human saves and the problem sets, and the browser E2E all passed.

Folding the expansion flags renames six feature columns of the entity network. A column-name map moves the trained weights to the new columns when a model file is loaded, and comparing the current play model at 1,449 positions gave the same best move everywhere (largest value difference 5.4e-7, from summation order). A post-merge review by another tool (Codex) found that renamed columns were also counted as "dropped columns", so only the warning count was wrong; that was fixed (merge `cd3b143e`).

## Preparing for Conspiracy

On November 6 the official design diary no. 2, "Raids", was recorded in the Conspiracy section of the plan. It notes where the Reveal-turn raids and each seat's raid board, Agent box effects that last the whole round, and Agent boxes switched on by a condition would fit into the current structure. Rules interpretation waits for the rulebook.

## What is left

- The refactoring that changes no behavior is finished. The next stage comes after reading the Conspiracy rulebook.
- Some stages were done by cloud sessions and the rest by local sessions; the gates and merges ran on the Mac mini.

## References

- Stages 1 and 2 ·
  Stage 3 ·
  First part of stage 4 ·
  Rest of stage 4 ·
  Expansion flags ·
  Agent box records ·
  Ghola and Usurp ·
  Column count fix
- Content core separation plan ·
  Work log, November
