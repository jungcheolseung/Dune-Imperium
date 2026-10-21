+++
title = "Bloodlines, Tech Module and Immortality, and the designer's public answers"
description = "Three expansions implemented as independent options, and 13 public answers from the designer, collected by the community, applied to the engine."
date = 2026-09-09T14:56:00+09:00
publishDate = 2026-10-20
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-07"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/worklog/2026-09.md", "docs/rules/designer-rulings-audit.md", "docs/rules/open-questions.md", "docs/implementation-audits/bloodlines.md", "docs/implementation-audits/immortality.md"]
+++

## Expansions as options that can be switched on and off

With the base game finished, the goal was to add three expansions that attach to four-player Uprising: Bloodlines, Tech Module and Immortality. This covers only the parts used with Uprising; it is not an implementation of the full Rise of Ix game. For this period we put finishing the implementation ahead of AI training.

The three are rule options (`bloodlines`, `tech_module`, `immortality`) that can be switched on independently. Expansion-only cards, leaders and actions enter the decks and choices only when their option is on (the Bloodlines promo Ruthless Leadership needs promos and Bloodlines together; the leader Kota Odax needs the Tech Module). Cards that were not yet transcribed were kept out of the decks. With each expansion the AI input (observation) and action codec versions went up, and each time old checkpoints were blocked from loading.

| Expansion | What this entry implemented | Version changes |
| --- | --- | --- |
| Bloodlines | Sardaukar Commander and Skills, 2 Conflict cards, 8 leaders, Imperium, Intrigue, Twisted and Navigation cards, 8 contract tokens | observation v6–v8, codec v90 |
| Tech Module | 18 tech tiles, Ixian Embassy, the leader Kota Odax | observation v9, codec v91–v94 |
| Immortality | Research and Tleilaxu tracks, specimens, the Tleilaxu Row and Reclaimed Forces, Graft (an Agent turn that plays two cards), Ghola, Chairdog and Usurp, Family Atomics | observation v11–v15, codec v95–v97 |

For Bloodlines we went through each place where a Commander counts as a troop (retreating, deploying, tie-breaks). For tie-breaks we decided that a Commander in the garrison counts as a troop (`[Main p. 15]`, `[Bloodlines p. 4]`). For the Tech Module, buying a tile through a Landsraad visit and through a card discount share one handler. Immortality started with a rules document and a card transcription document, then proceeded in slices: the board (21 research spaces plus the start, 8 Tleilaxu spaces), the Tleilaxu Row, Graft, and the cards. It was finished in one day. Physical copy counts per card come from a community-made card list (30 Imperium cards and 15 Intrigue cards for Immortality).

## The option that save files forgot

While checking the screen after adding Bloodlines and the Tech Module, we found that the save document did not record these two options or the promo option, so loading a Bloodlines game tried to replay it under the base rules ([`255fc66`](https://github.com/jungcheolseung/Dune-Imperium/commit/255fc66)). All three options are now recorded in the ruleset block of the save document, and older documents without the field are read as off. The Immortality option has been saved this way from the start.

## Defects found by combination soaks

Random-game soaks with the expansions on turned up defects at every close-out. The soak periodically applies every legal action to check that action ids round-trip.

- The first run of the 7,000-game Bloodlines plus Tech Module soak failed 10 games in three families: a pending Command choice whose card was trashed by another effect, a dead end where the number of deployable troops was counted differently in two places and no legal action remained, and an arrow cost offered on a space that is not a faction space. After the fixes the same seeds all finished, and the 7,000-game rerun had no failures.
- The Immortality close-out (830 games) found a double reshuffle of the discard pile when drawing two cards, which left the same card in two zones; a dead end where Usurp offered a space with no opponent to follow; and a heuristic that switched the graft partner forever. After the fixes there were no failures.
- Two more came from the soak: Ghola copying Duncan Idaho's Signet space raised an error on the second placement after the Agent had already moved to the Conflict, and the codec's give-and-trash templates lacked an Immortality Intrigue when Bloodlines and Immortality were combined.

## Thirteen public answers from the designer

The community keeps a compiled FAQ document (1,223 lines) of public answers the designer gave on forums and messengers where the official rules and FAQ are silent. We compared the entries that fall within the implemented scope against the engine one by one. The result: about thirty entries matched, 13 differed from engine behavior, one content gap remained (the eight Bloodlines contract tokens), and two items needed a further check.

The earlier version of this entry mentioned only "follow-up bug fixes"; these were really 13 rule changes. The designer's answers are not official documents, but where the official documents are silent we decided to follow them, and recorded them under one ruling number (OQ-057). They went in batch by batch.

- **First batch (8):** an Intrigue card that can be played with no target (Impress), using one or both effects of Change Allegiances, a tech-acquiring Intrigue effect that cannot be declined while a tile is buyable, Ghola grafted to Long Reach giving all three icons, and Combat reward order following turn order from the first player when order matters, among others.
- **Second batch (2):** "Choose Two" is resolved only after both choices are made, and a Harvest Cells gained as a Combat reward can be used in that Combat.
- **Third batch (3):** a mandatory Agent box whose condition is false is hidden and only fizzles if nothing can resolve it by the end of the turn, Interstellar Trade triggers once, and Guild Spy triggers once per Reveal.

We also transcribed the eight Bloodlines contract tokens and applied two checks from the same audit (how Leadership counts swords, and recalling Duncan Idaho's Into the Fray Agent with Imperial Privilege). On the same day it was ruled that separately printed lines on an Intrigue card are used one at a time and paid when used (OQ-058). While doing this a transcription error was found on Calculus of Power, which we fixed: a plain trash icon is optional unless it is a cost or an instruction to trash the card itself (`[Main p. 20]`).

Part of this comparison was later corrected again. On October 4 Interstellar Trade was ruled the other way, so that each contract completed later pays once more, and some rows that the audit marked as matching (Spy placement being mandatory, the Harvest contract, Chairdog) were later shown to be wrong. The audit document keeps the current state with dates.

## What is left

- Being able to switch an expansion on is separate from the AI playing it well. Making the heuristic AI evaluate the expansion elements is covered in the next entry ([Refining the baseline AI]({{< relref path="devlog/2026-09-16-baseline-ai.md" lang="en" >}})).
- Card and board transcriptions were corrected again in a late-September full audit that produced more than 130 rule changes.

## References

- [Bloodlines slices 1–5 merge](https://github.com/jungcheolseung/Dune-Imperium/commit/dbd9b73)
- [Immortality option skeleton and card catalog](https://github.com/jungcheolseung/Dune-Imperium/commit/19ec0fe0)
- [Ghola, Chairdog and Usurp](https://github.com/jungcheolseung/Dune-Imperium/commit/0a97bf1c)
- [Eight Bloodlines contract tokens](https://github.com/jungcheolseung/Dune-Imperium/commit/80a51c86)
- [First batch of eight designer answers](https://github.com/jungcheolseung/Dune-Imperium/commit/5621ee23)
- [Third batch of designer answers](https://github.com/jungcheolseung/Dune-Imperium/commit/6782c899)
- [Using Intrigue lines separately (OQ-058)](https://github.com/jungcheolseung/Dune-Imperium/commit/fc91368f)
- [Designer answers audit](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/designer-rulings-audit.md)
- [Bloodlines rules specification](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/bloodlines.md)
- [Immortality rules specification](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/rules/immortality.md)
