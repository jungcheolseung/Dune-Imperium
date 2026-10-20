+++
title = "Arrakeen Scouts and Epic Game Mode"
description = "Connect round events, missions, auctions, secret choices, browser displays, and AI seats."
date = 2026-09-30
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-09-28"
retrospective = true
source_ref = "e7e9ad4f"
sources = ["docs/worklog/2026-09.md", "docs/implementation-audits/epic-game-mode.md"]
+++
## Decisions at round opening

Arrakeen Scouts was implemented in stages: schedule, round modifiers, subcommittees, events/sales, missions, secret choices, and auctions. Selection order and payment questions were recorded and checked in follow-up work.

On September 30, Epic Game Mode was integrated and a fixed combined game was checked. The board displayed troops, goods, and card counts committed to missions.

## Unlearned actions

Older checkpoints had not learned the new module's decisions. Equal scores could repeatedly select the first action. Decisions whose legal actions were all unlearned therefore used a heuristic fallback.

Checkpoint and search seats could then participate in Scouts games. This did not mean the network had learned the module's strategy. Operational support and learned coverage were kept distinct.

## References

- [Document the Arrakeen Scouts completion (slice 10)](https://github.com/jungcheolseung/Dune-Imperium/commit/44666254)
- [Pin an Epic Game Mode game with Arrakeen Scouts on the merged line](https://github.com/jungcheolseung/Dune-Imperium/commit/423596d0)
- [Let checkpoint and search seats play Arrakeen Scouts](https://github.com/jungcheolseung/Dune-Imperium/commit/408c33ff)
