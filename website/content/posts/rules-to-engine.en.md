+++
title = "Turning board-game rules into an executable engine"
description = "Legal actions, information boundaries, and reproducible execution in the Dune: Imperium AI engine."
date = 2026-10-20
lastmod = 2026-10-20
draft = false
categories = ["규칙 엔진"]
tags = ["엔진 설계", "규칙 검증", "재현성"]
[params]
source_ref = "e7e9ad4f"
sources = ["README.md", "docs/implementation-plan.md", "docs/rules/README.md", "docs/rules/information-visibility.md", "docs/composed-effects-plan.md", "src/dune_imperium/rules/engine.py"]
+++
People can read cards, discuss legal choices, and consult a rulebook. A program needs an executable version of that process: who can choose what, what follows, and what information each player sees.

This engine was built before the game interface. This article explains its responsibilities, rather than adjudicating individual cards.

## One engine for play and training

People play through a web interface, while training runs many repeated games. Separate rule implementations could drift when a ruling changes, so both send actions to the same engine.

```text
Browser ─ Play server ─┐
                      ├─ Rules engine ─ Next state and events
AI / training ────────┘
```

The engine does not draw the interface or depend on a particular learning library. New interfaces and policies can reuse its rules.

## The engine defines the available choices

Instead of repeatedly rejecting arbitrary AI suggestions, the engine enumerates currently legal actions. The interface displays them and the learning environment permits only those choices.

Resolution can pause for another decision, including a payment, a target, or another player's response. These pauses are part of the game flow.

The legal-action list must therefore be correct. A missing choice or an early end-turn option affects both people and AI. Verification needs to cover the offered choices as well as the outcome.

## Show only the permitted information

The engine holds the complete state, but each player receives a separate view. The interface and AI must respect that boundary.

For example, the information specification cites the official explanation of when Intrigue cards become public as `[Main p. 7]`. See the [information specification](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/rules/information-visibility.md) and [official rules resources](https://www.direwolfdigital.com/dune-imperium/resources/).

Hiding a card on screen is insufficient if observations or logs reveal its identity. Those outputs are checked too.

## Reproduce random outcomes

A final score alone rarely explains a faulty game. The starting seed and recorded actions/chance outcomes let us examine the same progression again.

These records help reproduce bugs and compare versions. We can inspect offered choices, events, and player views. If changed rules prevent direct replay, versioning and migration paths are handled explicitly.

## Record repeated effects as shared parts

One handler per card creates many places to fix similar behavior. The project has been moving costs, conditions, rewards, and target selection into shared ability records.

A flow such as paying a cost to receive a resource can be represented by cost and reward parts. This describes the architecture, not a new ruling for a particular card. Unusual flows can retain dedicated handling.

During migration, the same games run on both engines to expose unexpected differences. Intentional ruling changes are documented and checked separately.

## Keep the evidence with the implementation

Official Dire Wolf Digital rulebooks, supplements, and FAQ are the rule sources. Gaps are identified as project conventions or open questions. A test expectation is not itself an official rule.

See the [composed-effects plan](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/composed-effects-plan.md) and [rules index](https://github.com/jungcheolseung/Dune-Imperium/blob/e7e9ad4f/docs/rules/README.md) for the detailed evidence and design.

[The next article]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}}) explains AI decisions on this engine.
