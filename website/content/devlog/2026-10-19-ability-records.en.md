+++
title = "Shared ability records for effects and AI input"
description = "Move repeated card, board, and expansion effects to shared records while updating logs, migration, and model features."
date = 2026-10-19
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-10-14"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/composed-effects-plan.md", "docs/entity-network-plan.md", "docs/worklog/2026-10.md"]
+++
## Reducing per-card branches

Similar effects spread across handlers create more places to change and verify. Costs, targets, rewards, and action shapes moved into ability records read by shared execution paths.

The migration covered Intrigue and personal cards, then Reveal effects, contracts/conflict rewards, board spaces, leaders/Tech, and expansions. Follow-up work consolidated handlers and event names, and connected model input to the same records.

## Structure changes and ruling changes

The same games ran on old/new engines to compare choices, events, and observations. Intentional ruling differences were listed separately. Record migration and browser checks were updated alongside the action catalog.

The second cleanup batch and model inputs were merged on October 19 at action codec v149. Some reward tallies remained, with execution/payout redesign left for the next stage. The overall transition was not finished.

## No immediate model replacement

A retrained model with the new inputs did not clearly beat the existing play model in preliminary comparisons. The final search-seat replacement gate was not run, so the play model remained unchanged.

## References

- [composed-effects-plan.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/composed-effects-plan.md)
- [Merge cleanup2: composed-effects cleanup-2, the A8 network inputs, codec v149](https://github.com/jungcheolseung/Dune-Imperium/commit/86086c6d)
- [entity-network-plan.md](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/entity-network-plan.md)
