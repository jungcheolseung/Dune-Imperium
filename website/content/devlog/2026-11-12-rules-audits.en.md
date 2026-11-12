+++
title = "Three rules checks: separately printed effects, timing and order, paths no test reached"
description = "We searched every card for defects of the Slig Farmer family and fixed seven places. We swept when, in what order and by whose choice effects resolve in every expansion combination, and measured the rules code tests never run, so that every line real games pass through is now covered by a test."
date = 2026-11-12T09:30:00+09:00
publishDate = 2026-11-12
lastmod = 2026-11-12
draft = false
[params]
work_start = "2026-11-09"
retrospective = true
source_ref = "5af196e5"
sources = ["docs/reviews/2026-11-printed-effects-audit.md", "docs/reviews/2026-11-timing-audit.md", "docs/rules/open-questions.md", "docs/worklog/2026-11.md"]
+++

## Background

On November 8 a friends' game turned up [a defect where one of Slig Farmer's two effects vanished]({{< relref path="devlog/2026-11-10-play-feedback.md" lang="en" >}}). We started an audit to find defects of the same family on other cards, and went on to check the timing, order and deciding seat of effects, and the code that tests never reach. All three checks reported before fixing anything, and the user chose the direction of each fix. None of the three found an engine defect against the official rules; what was fixed were places where project rulings disagreed with each other.

## Audit of separately printed effects (merge `e3d2dfcb`, codec v170)

From about 2,000 lines of ability records for every card, space, tile, leader, Conflict, Contract and Scouts item, 319 cases with shapes where defects hide easily were filtered out, and three read-only agents split the areas and compared them with the card text. The exact Slig Farmer shape did not appear again. Two defect candidates and four fixed orders that differ from the principle came out, and two more were found during the audit.

| Item | Change | Basis |
| --- | --- | --- |
| Forbidden Weapons | During your turn the Shield Wall icon is one "destroy the Shield Wall" line, lapses at turn end if unused, greyed when there is no wall | OQ-095 (2) |
| Disposal Facility, Planetary Array | The trash icon on acquisition works the same way | Same ruling |
| Spice Agony (Lady Jessica) | Only the spice payment is one step; the Intrigue draw and the memory then stay as separate lines in any order | OQ-106 |
| Final Delivery (Princess Yuna) | 7 Solari is one line; Influence, troops and spice are separate lines | OQ-148 |
| The last space of Feyd's track | Arriving gives no troop; it stays as a Signet reward | OQ-027 |
| Throne Room Politics | The troop icon and the optional trash icon appear together as soon as the Agent is placed | OQ-027 |
| Control the Spice | Paying turns the troop into an armed icon; the trash becomes an optional line | OQ-148 |

Letting the owner choose the order can change outcomes. For example, with one troop left in the supply, you can first draw Spice Agony's Intrigue card and then decide where the last troop goes. Old records are moved by seven bridges, and the engine gate confirmed all 360 games identical with a declared difference that maps only the changed effects back to their old shape. 2,000 recorded games, human saves and the 240 problems all replayed. Two review rounds by another tool (Codex) found five issues, all fixed.

## Timing, order and deciding-seat audit (merges `8f665db6`, `18080c14`)

We built a tool that plays whole games with the engine alone and inspects every step: does a turn end only when its owner ends it, are Plot, Combat and Endgame Intrigue cards offered only at those moments, the seat order of windows several seats answer in turn, every seat's Reveal before Combat, and so on. 16 combinations × 16 seeds, 256 random and 256 heuristic games (about 510,000 steps) plus 112 Scouts games, all followed the rulings. There were four findings.

- **Panopticon and Spy Satellites (T-1).** At game end a seat's Panopticon always resolves before the same seat's Spy Satellites, which can lose 1 VP for each Faction at exactly 1 Influence. The user ruled "(c)": the order stays. The printed word "Worth" on Spy Satellites is read as a value assessed on the final Influence (the reasoning is recorded in OQ-040).
- **Seat order of the endgame Tech lines (T-2).** Only these started from seat 0, while every other multi-seat order started from the First Player `[Main p. 8]`. "As recommended", they now go clockwise from the First Player. Only the order of events changed, with the codec and observations unchanged, and only one of the 360 games actually differed.
- Two stale lines in the rules documents (D-1, D-2) were fixed.

## Paths no test reached (merge `12092a6e`, November 12)

We measured coverage of the rules, core, content, adapters and records code: lines 94.15% → 94.24%, branches 85.57% → 85.72%. Of the 1,737 blocks never run, 1,184 are a single `raise` guarding against illegal actions or broken invariants, and most of the rest is defensive code too. The comparison with real games matters more. Playing 1,440 games with the engine gate's soak configurations under coverage passed 88.6% of the rules code's lines and 77.2% of its branches, and only five places were passed by games but not by tests. Adding those five and some rare paths, 13 test functions (16 cases) were added, so every line games pass through is now also passed by tests. Each new test was confirmed to fail when its path is deliberately broken. No rule defect was found.

Unreached blocks were only listed as dead-code candidates, and the user decided to leave them. One hidden-information question the documents do not answer came up: who knows a played Navigation card before its option is chosen? The user ruled that only the owner sees Navigation cards, and that they become public to all only when the four face-down cards are revealed (OQ-168). The engine already worked that way, so only a test was added.

## What is left

- Four test candidates for rarely reached paths remain in the coverage notes.
- The audits saw what they saw on chosen combinations and seeds. Not finding a defect does not prove there is none.

## References

- Rulings of the separately printed effects audit ·
  Timing audit tools ·
  Endgame Tech lines ·
  Coverage and tests ·
  OQ-168
- Printed effects audit report ·
  Timing audit report ·
  [Open questions](https://github.com/jungcheolseung/Dune-Imperium/blob/master/docs/rules/open-questions.md) ·
  Work log, November
