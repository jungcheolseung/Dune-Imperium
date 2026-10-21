+++
title = "Rule changes that came from questions during play"
description = "Starting from questions that came up while playing, hidden draws were split from public choices, the decline button on optional effects was removed, and Reveal choices became rows of the Reveal list."
date = 2026-10-14T21:46:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-10-10"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/rules/open-questions.md", "docs/lessons.md", "docs/worklog/2026-10.md"]
+++

## When a question split the rules document and the engine

The order for changing a rule in this project is fixed. Check the official sentence and its page; if the documents are silent, add an open question (OQ) to the list and rule on it; and keep official rules and project rulings distinct. Between 10 and 14 October, a few questions that came up while playing changed the structure of the implementation. This entry goes through them.

There is an earlier example. On 6 October the question came up whether an Intrigue card should be playable with no effect at all. The FAQ says that to play an Intrigue card you must meet its conditions and pay its costs, and gives examples (`[FAQ p. 2]`). So an Intrigue option is now offered only when its printed conditions are met, its cost can be paid, and at least one of its effects can change something right now (codec v138). All 124 options of the 90 Intrigue cards were checked, 42 cases where a card could be played with no effect were reproduced in real states, and an earlier broadening (playing an "up to" deployment Intrigue with no troops) was reverted.

## Public choices and hidden draws are separate steps (OQ-106, codec v142)

One of the 10 items left after play on 10 October concerned Imperial Privilege. The choice to recall an Agent and the card draw were bundled into one action, so the recall could not be undone. The ruling: recall and draw must of course be two steps, a basic principle. The reason: you may want to trash a card from the discard pile before drawing. When the deck is empty, drawing reshuffles the discard pile, so a card trashed beforehand does not return to the deck.

The official documents only say printed effects are carried out in any order (`[Main p. 9]`), so this is a project ruling, not an official rule. It was applied to the whole engine rather than to Imperial Privilege alone.

- **Scope.** Effects printed separately on the same card or space (Urgent Shigawire, Cunning and Insider Information, the arrow rewards of Piter and Kota), draws triggered by other effects (Influence-track bonuses, the Tleilaxu track's Intrigue spaces reached through Research, Hungry for Spice, trash triggers), and the draws on Arrakeen Scouts rows were all split. A public choice reveals no hidden information, so it can be undone; only the draw cannot. The draw is the player's own step, ordered freely among the player's other actions, and the turn cannot end while one remains.
- **One exception.** Esmar Tuek's Tuek's Sietch gives an Intrigue card along with the visit. It was ruled that, since other control bonuses are also received right at the visit, leaving only this one unsplit is more natural.
- **Three places that collided with a designer's public answers.** One answer said the CHOAM Transports draw happens as soon as the contract is completed and cannot be deferred. Another said faction bonuses, such as the Bene Gesserit Influence-4 Intrigue card, may interrupt the flow (which also covers Princess Irulan). A published rules answer said Overthrow's acquire effect must be taken immediately on acquiring. Turning these into free-order steps would contradict those answers. All three were settled as "an immediately following, separate step": the trigger step can be undone, and the very next and only legal action is that draw. No other effect or End turn can intervene.

Two more points were settled the same day. The cost discount of the Navigation Chamber Tech tile is read as mandatory because the tile's sentence has no wording of choice (OQ-104). That is a project reading of the official documents' silence on whether it can be declined. Before, a full-price placement was offered next to the discounted one, and the heuristic AI saw the two rows as equal and paid full price on about half of the spaces (measured over 200 seeds). And whether a Commander may be given up when losing troops, whether to an opponent's effect or as a self-paid cost, was settled as "unify" (OQ-105). The basis is the sentence that a Commander is a strength-2 troop in a Conflict and troop-targeting effects apply to it (`[Bloodlines p. 4]`). Piter, the Bene Gesserit Treachery event, and Prison Planet now accept a Commander.

Verification: 7,247 unit tests, 55 browser E2E scenarios, migrating the 4 local saved games' old records (0 divergences), and an independent review for each rule unit. The 2,000-game record corpus check (v141) gave exact 6, equal 639, transient 1,046, persistent 0, diverged 309, failed 0. Every diverged game was a move the new rules made illegal (298 Navigation Chamber full-price payments, 8 Treachery cases for a seat with only Commanders and 0 Bene Gesserit Influence, and so on). Of the 112 positions in the problem set built from human games, 110 resolved; the other 2 were spots where the full-price Navigation Chamber payment had become illegal, and were removed from the set by decision.

## Why did the decline button exist? (codec v146)

On 14 October a question came up whether Smuggler's Haven was really a mandatory space, since it is a cost-paying ability and so optional. Then: why do optional actions have a separate decline button at all?

The cause was history. The decline button was a device from when the engine closed the turn by itself after the last effect (19 August); an optional effect needed some press to finish. When turn end became a single press on 30 September and 8 October, that premise vanished but the button stayed, and nobody had checked it against the project rule sentence that End turn appears only when mandatory effects are finished. The official FAQ calls "may", arrow costs, and black trash icons optional (`[FAQ p. 3]`).

The new behavior: an optional effect inside one's own Agent turn has no decline action, does not block "End turn", and lapses unused when pressed. The lapse is recorded as an event, and the log says which effect it was. The removed declines include the 27 optional Agent boxes' decline rows and the Tech acquire and sub-committee join declines. Old records' declines are dropped on migration (33,503 in the 2,000-game v145 corpus), with 0 persistent differences. The work also fixed an existing stall in which no legal action remained after a Spy recall because no space was left to place on.

**A standalone window pulled out of the engine.** For things like Gather Intelligence, which must be chosen alone first, the current standalone window is right, and turn-start cards (Litany Against Fear, Withdrawn) were to be chosen alone first too. It was first built as an engine frame with a decline action. But that window opens only for a seat holding such a card, so its decline step and public event alone let other seats know the card was in the hand. It was added after the first independent review, so it had not been reviewed, and was found after the commit while preparing the second review. Before merging it was removed from the engine (the action list, record migration, and AI handling with it) and moved to a view shown only on the card holder's own screen. The rule since: if the condition for opening a window depends on something hidden such as the hand or deck, build it as a screen view, not an engine frame. The engine already respects the rule's timing.

## Reveal choices as rows of the Reveal list (codec v147)

The official rule is that Reveal effects are carried out in any order and acquiring can happen before, between, or after them (`[Main p. 12]`). The engine, however, opened a window for each revealed card and made you answer first; to reorder you had to press defer and resume. The decision was to change this structure.

- Every optional choice goes into the Reveal's pending list and is offered as a row, together with purchases, automatic gains, and Plots. Defer and resume are gone.
- The 16 kinds of optional effects lapse without a decline and do not block ending the Reveal. The 10 kinds of mandatory effects (Spy placement, either-or choices, gaining Influence) block ending it while usable.
- When several cards offer the same action, a `source` tells which card's effect it is. The base action list grew from 4,413 to 4,553 rows, and the all-options list from 35,972 to 36,379.
- On screen, under per-card headings, "may skip" and "must choose" effects are shown separately, and a choice that cannot be used now stays as a greyed row with the reason.

**Existing defects that surfaced.** The old window did not re-check its conditions when answered. For example, Unswerving Loyalty could still deploy on the condition of a card that had been trashed earlier in the same Reveal. Conversely, the choice of a card trashed by another effect kept being offered: even after Calculus of Power trashed Corrinth City, its 5 Solari choice remained. Receiving or activating the effect of an already-trashed card is not allowed under the designer's public answer (OQ-022), and a note extending that answer to "Reveal choices too" had been implemented for only one card (Engineered Miracle, then CHOAM Demands). A test even pinned the opposite behavior (a trashed Priority Contracts still giving its spice branch), with no rule sentence permitting it recorded. The independent review found this after the move to a list, and a rule was added to the lessons document: when a ruling says "apply to all of X", list every X (here, all 26 Reveal choices) and check each.

The first fixed AI bought before taking choices that give persuasion, and played weaker (in 88 of 1,115 Reveals with a choice). After fixing the order, it matched the old Reveal decisions 99.48% of the time on 200 earlier-recorded games.

Verification: the independent review's 360-game sweep had 0 stalls or exceptions, all 26 choices were offered, and there was no hidden-information leak. 7,660 unit tests and 65 browser E2E scenarios passed. The previous-codec corpus (v145) check over 2,000 games gave 1,955 the same and 45 diverged: 2 Unswerving Loyalty games and 43 games that took the choice of a trashed card (all after a Calculus of Power trash). Since that is the result of a rule fix, it was left as divergence rather than dressed up with a migration bridge. All 9 human games migrated to the end.

## What the record checks were for

Each change above put a step that migrates old records to the new engine into the same commit as the code, then replayed those records and counted where they diverge. Changing a rule necessarily diverges some old records; the point is not to hide where, but to classify them as "moves the rules made illegal" and keep the list. That is what lets us tell a change of structure only from a change of ruling.

## What remains

- Each time the codec rises (v142, v146, v147), saved games of the previous codec do not open in the server. The records of finished games can be migrated with the record tooling.
- OQ-104, OQ-105, and OQ-106 are project rulings, not official rules. Each states a reopening condition: when the official documents settle the resolution unit or undoing of printed effects.
- The restructuring of card effects that followed continues in the [ability-records entry]({{< relref path="devlog/2026-10-19-ability-records.md" lang="en" >}}).

## References

- [Open questions (OQ-104, OQ-105, OQ-106 and others)](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/open-questions.md)
- [Lessons record (2026-10-14)](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/lessons.md)
- [Play feedback of 10 items, merge (codec v142)](https://github.com/jungcheolseung/Dune-Imperium/commit/6cde2736)
- [Optional effects lapse at turn end, merge (codec v146)](https://github.com/jungcheolseung/Dune-Imperium/commit/214e7929)
- [Reveal choices, merge (codec v147)](https://github.com/jungcheolseung/Dune-Imperium/commit/fb6a7ec4)
- [No Intrigue play for no effect, merge (codec v138)](https://github.com/jungcheolseung/Dune-Imperium/commit/62f63413)
