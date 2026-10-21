+++
title = "A browser screen for human play, saving and undo, and a board-centred table"
description = "How the heuristic AI and the leader draft became seats, and how the session server, the browser screen, saving and review, generated effect text, undo and the action log, and the game table drawn on the board came about."
date = 2026-09-03T20:39:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-08-30"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/worklog/2026-08.md", "docs/worklog/2026-09.md", "docs/implementation-plan.md", "docs/rules/information-visibility.md", "docs/rules/open-questions.md", "docs/card-data-sources.md"]
+++

## A screen for humans came first

On August 30 the implementation plan was reordered so that the human play screen (M11) comes before the evaluation environment (M9) and training (M10). With the engine and its full-game verification done, a human actually playing games was judged the earliest way to check the rules and the experience, and the completion condition of this stage does not need a strong AI. The screen was fixed as a local web screen, with a random AI and a simple rule-based AI as the first opponents.

## Kinds of seat: human, heuristic, random, and the leader draft

The engine could already run a whole game (earlier entries), so what was new in this stage is who sits at the seats.

- **Heuristic AI:** it scores legal actions with a static preference. Direct victory points rank highest, then permanent upgrades, acquisitions scaled by cost, and full deployment; declines and passing rank lowest. The scores are a strategy preference, not a rules ruling. Running this AI also exposed [bugs the random check had not found]({{< relref path="devlog/2026-08-30-random-sweep.md" lang="en" >}}).
- **Leader draft:** a setup in which six revealed leaders are picked one at a time in reverse turn order, the first player last. It is a project ruling (OQ-007), not an official rule, and is turned on as a ruleset option. So that the size of the action list does not depend on the option, the `pick_leader` action is always in the list (codec v79). The draft adds six revealed-leader slots to the observation, making it v2 (1,415 integers).

## The session server and the first screen

On August 31 a FastAPI-based server (`dune-imperium-server`, optional install `ui`) and a dependency-free single page of HTML, CSS, and JavaScript were built.

- `GameSessionManager`, which manages games, does not depend on a web framework. Each seat is set to human, heuristic, or random; chance and AI seats advance automatically, so a game always stops at a human decision or at the final standings.
- A human receives only the observation and the legal-action list of their own seat. Asking for another seat is refused (403), and an action sent from a stale screen is refused (409) because the game's revision number no longer matches.
- The browser knows no rules. It only draws the observations, choices, and catalog the server sends.

On a real server and browser, a draft game was created from the setup screen and the action buttons on the screen alone were driven for 103 decisions to a 10-round final standing, with 0 server errors. There were 833 pytest tests at that point.

## Saving, loading, and review

A save writes the game's record (actions and chance outcomes) as versioned JSON together with the action codec, ruleset, and content versions. The random-number state itself is not saved. On loading, chance outcomes and AI decisions are regenerated from fresh randomness with the same seeds and checked against the record, and finally the state hash is verified. A loaded game therefore continues exactly like one that was never saved. The price is that a save file is tied to the engine and AI code of the time of saving, and a file that differs or was tampered with fails to load, naming the step where it diverged. In other words, changing the engine can make old saves unreadable, which is why a separate record-migration effort appeared later.

The record contains shuffle outcomes, that is, the order of private decks, so over HTTP only a summary is sent, not the content of a save file. Review of a finished game (a step slider) at first showed only the human seat and only its own actions in detail. On a real browser a draft game was created, saved midway and loaded, finished with 79 more decisions through the screen buttons, saved again, stepped through a 491-step review, and deleted, all without server errors. Tests went from 833 to 842.

## Generating effect text from engine data

If the screen showed only names, you had to memorize the effects of spaces and cards. So a `display` package generates the English effect text from the engine's content data. The Intrigue, contract, Conflict, and board-space tables are rendered mechanically, while the effect names of personal cards, the choice-driven spaces, and the leader faces were copied by hand from audit documents checked against the card art. Coverage tests pin every effect name, DSL element, card, space, and leader face, so adding new content without text makes the tests fail. In the course of this work, a statement in an earlier handoff document, "two unimplemented spaces", was found to be wrong; it was actually four in the base ruleset, and was corrected. Card pictures are local pictures that a developer prepares on their own machine and are not in the repository; without them the screen shows text cards.

The 22-space board panel, a detail popover on every chip, effect previews on action buttons, and 111 action labels were added then. Tests went from 842 to 934, and on a real server and browser in both rulesets the 22 spaces, unimplemented badges, popovers, six action steps, and 0 page errors were confirmed. The spaces carrying that badge (four in the base ruleset and one in CHOAM) were implemented on September 1.

## The information boundary, undo, and the action log

On September 2 two things were decided. First, the four scopes of OQ-010 (how much to disclose). Opponents' discard piles and completed contracts are public; the live log shows each player only the events that player may see, and public events carry names only for cards in public zones; when a game ends, all hidden zones are disclosed. The observation became v3 (1,967 integers) accordingly.

A new check was added too. An invariant in the sweep fails whenever a card named in a public event sits in a hidden zone at any transition, and a pass over 24 random games found and fixed three leaks. The random-steal event of Secrets was split into a public one and a restricted one, and the "cards drawn" and "discard pile shuffled" events were changed to carry only counts.

Undo follows the direction "information that has been disclosed must remain checkable". For each card the server computes which seats know it, and if after an action some seat knows a card it did not know before, the action counts as a disclosing step (a player disclosing a card only they knew, by playing Intrigue, discarding, or revealing, is the exception). The undoable span is the run of the seat's own non-disclosing steps counted from the end. It closes at chance, at another seat's action, and at a disclosing step, so no randomness falls inside the undone span, and restoring means reapplying the record from the start. Since another choice after undoing can reach the same revision number again, the browser also sends an undo generation number with actions and undo requests, and the server accepts only if both match (409 otherwise). The screen gained an "undo" button and an action log in which undone entries are struck through. The save format became v2, holding the log and the undone steps, and v1 saves are still read. That night each action also got a "cannot be undone" label, and when the next decision belongs to another seat the turn has to be confirmed before play moves on. On September 24 that confirmation was replaced by making every turn end wait for a single press.

The boundary had two holes at first. On September 20, only the choice of Staban Tuek was reported as not undoable, a false alarm (removing a card by name from the starting deck reveals nothing new). On September 24 a real game found a leak: after buying a card from the Tleilaxu Row, undo was possible, and the Row refill in between had shown the next card of the Tleilaxu deck. The cause was that the per-card disclosure list did not know the face-down piles of the expansions (the Tleilaxu deck, the Skill stack, the Tech stacks) or cards only their owner sees. The list was corrected after comparing it with the observations and choices over 200 random games of all expansions (144,660 states, 41 million card judgments), and all 12 new tests were confirmed to fail on the code before the fix.

## A game table drawn on the board

On September 3 the game screen, a text list until then, was rebuilt on top of the board picture (M11 slice 7). The positions of the 22 board spaces and 13 observation posts were measured by hand with a grid overlay and fixed. Legal spaces glow and can be clicked to place an Agent. If there is one legal action it is applied at once, and if there are several the matching ones are highlighted in the list on the right. Seat-coloured Agent tokens, control marks, Maker Spice, and Spies are drawn over the board. The layout is a fixed three columns (seat cards on the left, the board and shared cards in the middle, decision, undo, and action log on the right, and the player's hand along the bottom). Effect text is redrawn with icons.

On a real server and browser, 22 spaces, the board picture, and 65 icons were drawn, 12 steps were played, and 19 action-log entries accumulated (0 JS and server errors); the space positions were checked against the picture by eye on screenshots. pytest was at 1,015 tests. Local assets were also tidied the same day. Icons, the board picture, and card pictures are all local material on the developer's machine, not in the repository, and when missing the screen shows text and words instead.

## What remained

- The screen at this point was usable for a human to play a whole game; stepwise action choice, a Korean screen, and remote play came later.
- That a save file is tied to the engine of its time was a design decision made then, and a record-migration tool followed later.
- Background colour left at the corners of some Agent icons, and telling apart the action labels of two copies of the same card, were open improvements at this point.

## References

- [Session server](https://github.com/jungcheolseung/Dune-Imperium/commit/4fbd7517) and [first full game in the browser](https://github.com/jungcheolseung/Dune-Imperium/commit/42be8833)
- [Heuristic AI](https://github.com/jungcheolseung/Dune-Imperium/commit/1a449f4f) and [leader draft](https://github.com/jungcheolseung/Dune-Imperium/commit/c0c17953)
- [Save, load, and review server](https://github.com/jungcheolseung/Dune-Imperium/commit/8ab3cd25) and [browser screen](https://github.com/jungcheolseung/Dune-Imperium/commit/e44900ae)
- [Effect-text display package](https://github.com/jungcheolseung/Dune-Imperium/commit/a4befd4f) and [22-space board panel](https://github.com/jungcheolseung/Dune-Imperium/commit/d275a664)
- [Observation v3 and disclosure scope](https://github.com/jungcheolseung/Dune-Imperium/commit/8bb3bfe3) and [event visibility check](https://github.com/jungcheolseung/Dune-Imperium/commit/7a52c178)
- [Undo and session log server](https://github.com/jungcheolseung/Dune-Imperium/commit/0e761315), [undo buttons and action log in the browser](https://github.com/jungcheolseung/Dune-Imperium/commit/993bf11d)
- [Game screen on the board picture](https://github.com/jungcheolseung/Dune-Imperium/commit/6b9eae24) and [per-action undo labels and turn confirmation](https://github.com/jungcheolseung/Dune-Imperium/commit/cab29f20)
- [Expansion-pile leak fix (September 24)](https://github.com/jungcheolseung/Dune-Imperium/commit/9bdf232a)
- [Information-visibility rules](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/information-visibility.md) and [the open-questions list containing OQ-010](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/open-questions.md)
- [Card data and picture handling policy](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/card-data-sources.md)
