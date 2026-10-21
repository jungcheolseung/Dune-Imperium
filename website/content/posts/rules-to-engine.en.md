+++
title = "Turning board-game rules into an executable engine"
description = "Legal actions, information boundaries, and reproducible execution in the Dune: Imperium AI engine."
date = 2026-10-20
lastmod = 2026-10-21
draft = false
categories = ["규칙 엔진"]
tags = ["엔진 설계", "규칙 검증", "재현성"]
[params]
source_ref = "c8f61677"
sources = ["README.md", "docs/implementation-plan.md", "docs/rules/README.md", "docs/rules/information-visibility.md", "docs/composed-effects-plan.md", "docs/stage-b-plan.md", "docs/human-records.md", "docs/lessons.md"]
+++
People can read cards, discuss legal choices, and consult a rulebook. A program needs an executable version of that process: who can choose what, what follows, and what information each player sees.

This engine was built before the game interface. This article explains its responsibilities, rather than adjudicating individual cards. Descriptions and numbers are as of October 21, 2026, at action codec v150.

## One engine for play and training

The project has a browser interface and training code that plays many games. Separate rule implementations would let a fix in one path miss the other, so both send actions to the same engine.

```text
Player browser ─ play server ─┐
                             ├─ rules engine ─ next state and events
AI / training environment ────┘
```

The engine neither renders the interface nor depends on a training library. Code that uses PyTorch lives only in the training, AI, and evaluation layers, and the engine does not import it. New interfaces and policies can reuse its rules.

## The engine defines legal actions

Instead of letting an AI propose any action and rejecting illegal ones, the engine lists current legal actions. The interface displays that list, and the training environment masks every other action. The action list the AI sees (the codec) has 4,311 rows with every option enabled, and each decision opens only its legal rows.

Resolution can pause for another decision, including a payment, a target, or another player's response. For example, an Agent turn is split into choosing a card and choosing a space, and a pending effect is resolved by choosing which effect to use and then its target. A half-made choice is visible only to that player and can be undone within the turn. The official rules have no such intermediate state, so it is defined as a project convention (OQ-111).

It was not always split this way. Until October 19, 2026, a single Agent-turn action carried the card, space, graft, infiltrated post, discount, and cost choice, and made up 72% of a 36,385-row action list. The change is described in the [development journal]({{< relref path="devlog/2026-10-20-action-units.md" lang="en" >}}).

This makes the legal-action list itself a correctness requirement. A missing action or premature turn end affects both human choices and AI decisions, so the offered choices are tested, not only outcomes. Random and heuristic AIs play many games to the end while every transition is checked: no card appears or disappears, play never gets stuck, and the record replays as recorded. When this check first ran on August 30, 2026 with 10,000 games per ruleset, 46 games (0.23%) exposed five families of hidden bugs; after the fixes, all 20,000 games passed.

## Showing only available information

The engine manages the full state while seats see different information. The project separates full state from seat observations and checks that the interface and AI respect that boundary.

For example, the information boundary follows the official sentence that an Intrigue card is revealed to opponents only when it is played, recorded as `[Main p. 7]`. The order of a personal deck is hidden from everyone, including its owner. A card that entered a hand through a public route stays visible to all until it leaves the hand. The combined composition of a deck and hidden hand is something anyone can count from public events, so it is shown to every seat; this last item is marked as a project ruling rather than an official sentence. ([Information specification](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/information-visibility.md), [official rules resources](https://www.direwolfdigital.com/dune-imperium/resources/))

Hidden information can leak through AI inputs or logs even when the visual interface hides it, so observations and logs are reviewed too. The full-game checks build states that differ only in what a seat cannot know, such as deck order, opponents' hands, and opponents' Intrigue cards, and confirm that the seat's observation stays the same.

## Reproducible randomness

A final score rarely explains a broken game. The project records the initial seed and actions/chance outcomes so the same game can be replayed.

Records store moves by meaning rather than by row number in the action list: an action as its name, seat, and arguments; a chance outcome as which decision produced which value. Records therefore stay readable when the action list changes. When the engine flow changes and the new engine asks something the old one did not, a conversion step for that version threshold fills the gap.

These records reproduce bugs and compare engines before and after changes. Each structural change replays a set of 2,000 older records on the new engine and compares the state at every point. At v150, which split the action units, 1,568 matched at every point, 431 differed for a while and ended in the same state, and 1 diverged because rewards are now resolved in a different order. Browser save files are also replayed from the start and compared when loaded, so a rules or action-version change may stop an old save from loading directly.

## Recording repeated effects as shared pieces

One handler per card means every similar effect must be found and changed separately. Costs, conditions, rewards, and target selection were therefore moved into shared ability records. Personal cards, Intrigue, leaders, Tech, contracts and Conflict rewards, board spaces, and expansion effects are expressed as records that shared execution paths read. Card text and AI input features are generated from the same records.

For example, "pay a cost and gain a resource" can be described as cost and reward parts. This is an illustration, not a new ruling for a particular card. Flows that do not fit the common shape keep dedicated handling rather than being forced into it.

During the migration the same 200 games were played on the old and new engines, comparing the legal choices and their order, events, every seat's observation, and chance outcomes. Intentional ruling changes were kept in a defined-differences list, and the next stage started only with no other difference. The plan's remaining stage adds cards from other expansions as the same records.

## Evidence before code

The rule sources are Dire Wolf Digital's official rulebooks, supplements, and FAQ. Arrakeen Scouts has no rulebook, so its source is the help text and item definitions of the official companion app. Unanswered cases are labeled project rulings and recorded as open questions; as of October 21, 2026 the list has 112 entries.

A test expectation does not make behavior official, and neither does a code-review finding. In August 2026 a review finding was applied without checking the rules document, wrongly excluding spice gained from an Intrigue card from a Harvest contract; the rule counts spice from every source that turn. Since then, changing rule behavior starts by quoting the governing rule sentence and page.

Connecting evidence, implementation, and verification is part of engine development. See the [composed-effects plan](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/composed-effects-plan.md), the [action-unit design](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/stage-b-plan.md), and the [rules index](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/README.md).

The [next article]({{< relref path="posts/how-search-ai-chooses.md" lang="en" >}}) explains how AI chooses moves using this engine.
