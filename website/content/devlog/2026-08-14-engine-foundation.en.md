+++
title = "Rules specification and a one-round engine"
description = "Define the four-player Uprising target and connect setup through the end of a round."
date = 2026-08-14
publishDate = 2026-10-20
lastmod = 2026-10-20
draft = false
[params]
work_start = "2026-08-12"
retrospective = true
source_ref = "f1941ea0"
sources = ["docs/implementation-plan.md"]
+++
## Establishing the implementation target

The target was four-player Uprising, with official rules documented before implementation. The environment moved to Python 3.14 and uv. Work began on state, actions, and chance handling before the interface.

## Connecting a round

Seeded setup, redacted player observations, and legal action enumeration were added. Agent placement, Reveal turns and acquisitions, combat ranking/rewards, Makers, and Recall were then connected.

Random outcomes were recorded for replay, using both a fixed seed and the actual sequence of outcomes.

## What was checked

A random one-round runner and debug CLI were added, together with fixed scenarios for the rulebook's Agent, Reveal, and round-end examples. The completed scope was one round. Full games, remaining card abilities, and learning were still later work.

## References

- [Document Uprising rules and implementation plan](https://github.com/jungcheolseung/Dune-Imperium/commit/fe29f63b)
- [Record chance outcomes for deterministic replay](https://github.com/jungcheolseung/Dune-Imperium/commit/4f41ed91)
- [implementation-plan.md](https://github.com/jungcheolseung/Dune-Imperium/blob/f1941ea0/docs/implementation-plan.md)
