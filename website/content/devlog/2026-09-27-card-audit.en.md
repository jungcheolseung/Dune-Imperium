+++
title = "A full audit re-reading 348 card and board transcriptions"
description = "348 card and board items were re-checked against their printed faces, 114 confirmed errors were fixed, and the action codec went from v107 to v111. Earlier measurements and checkpoints now belong to the old rules, so M10 training restarted on the new ones."
date = 2026-09-28T07:32:00+09:00
publishDate = 2026-10-21
lastmod = 2026-10-21
draft = false
[params]
work_start = "2026-09-25"
retrospective = true
source_ref = "c8f61677"
sources = ["docs/implementation-audits/transcription-audit-2026-09-26.md", "docs/evaluation/m10-2026-09-27.md", "docs/evaluation/m10-2026-09-28.md", "docs/worklog/2026-09.md"]
+++

## From two misreadings to a full audit

On September 25, re-reading card faces revealed that the Signet rewards of Chani and Count Hasimir Fenring had been transcribed wrongly. Chani's Fedaykin Maneuver had been implemented as recruiting two troops, but the icon on the card is "draw two cards"; Fenring's Corrino Liaison was a plain Spy, but the card shows a Spy with Deep Cover. Searching for that icon by template matching across 368 cards turned up a third case the engine's list did not have: the first-place reward of Storms in the South (a Bloodlines Conflict). That pointed to a problem with the transcription process rather than with one card, so every card and board space was re-checked from scratch.

## Method

There were 348 items: 8 starting cards, 2 Reserve, 109 Imperium, 20 Tleilaxu, 90 Intrigue (including Twisted and Navigation), 28 Contract, 18 Conflict, 18 Tech, 7 Skill, 19 leaders (counting flipped faces), 23 board spaces, and 6 board items (the Influence tracks, observation posts, the Bene Tleilax board, the Ixian Embassy, the Research Station overlay, and card counts). Each item went through three steps.

1. **Blind transcription.** Without looking at engine data or code, the card face is enlarged and its icons and text copied down. The official icon guides (`[Main p. 20]`, `[Bloodlines pp. 5, 12]`, `[Immortality p. 16]`, `[Board Guide p. 14]`) and a list of look-alike icons were used as references.
2. **Comparison with the engine.** The transcription is compared with the engine definition, implementation, and display text. Wherever the blind transcription and the engine disagree, the card is enlarged again to decide which one is right.
3. **Independent rebuttal.** Each discrepancy faces three independent attempts to refute it, and it is confirmed only if at least two fail.

A separate mechanical comparison against a community-compiled card list (affiliations, Agent icons, costs, Reveal values, card counts) then found nothing the audit had missed; 8 errors in that list were settled from the card faces. The 8 findings with the widest impact were checked by hand against the printed cards.

The result was 258 matches, 89 mismatches, and 1 uncertain. Confirmed findings numbered 114 (80 rules, 32 display, 2 uncertain), and 2 were refuted. Card counts were all correct.

## Base-game cards were wrong too

The confirmed findings included several base-game cards, not only expansions: the Reveal of The Spice Must Flow (1 spice, not 1 sword), the Reveal of Covert Operation (2 Spy rather than 2 Persuasion), Subversive Advisor (1 Persuasion rather than 1 Solari), the Agent icons of Calculus of Power, Maker Keeper, Undercover Asset and Chani, Clever Tactician, the affiliations of Prepare the Way, Bene Gesserit Operative, In High Places and Overthrow, and the 2 Persuasion of Sardaukar Coordination. In other words, every game and every training run since the August implementation had been using the old values.

The rule errors were not only about numbers on a card but also about when and over what scope an effect fires. Examples include places that forced an unrefusable recall-first when a Spy reward arrived with the Spy supply empty, and places where the Command (6+) check must look at the Persuasion left after spending rather than the Persuasion generated.

## Handling

113 of the confirmed findings were fixed in eight work units (card data, new Imperium effects, Agent-box logic, Reveal logic, Intrigue, Spy/Conflict rewards/contracts, Tech/Skill/leaders/Ixian Embassy, and display text), each in its own working tree and merged after an independent review. The remaining one (the default Influence when Subversive Advisor is trashed first) is a rare ordering the official documents do not answer, and it was left unfixed at the time.

After merging, an integration review of six areas (Reveal, leaders and setup, Agent boxes, Combat/Contract/Spy, Intrigue/Tech/board, content/codec/observation) found 18 more confirmed problems between units. Examples: retreating two troops through Command Center did not reduce strength, and a card entering during Reveal paid its Command (6+) effect twice.

Where the rulebook is silent, the case was filed as an open question for a ruling instead of being filled in.

- Tenuous Bond, Grasp Arrakis and Battlefield Research allow only the one timing printed on the space's colour band and below the card (COMBAT / ENDGAME, PLOT / COMBAT) per space; the earlier transcription that opened both timings was an error.
- Coercive Negotiation is mandatory once its condition holds, and cannot be played with fewer than three contracts in the bank.
- A forced Spy move from False Orders goes to an empty observation post not connected to the space where the Agent was sent, as the official FAQ says (`[FAQ p. 2]`), and a Spy with nowhere to go returns to the supply.
- Acquiring through Reclaimed Forces counts as acquiring, so a face-up Call to Arms fires (`[Immortality p. 9]`). Every Agent recall can bring back an Agent that went into the Conflict, as Imperial Privilege does. Recruiting a Commander creates a separate deployment slot for a Commander (`[Main p. 10]`, `[FAQ p. 4]`).

## Correcting the standard contract set

On the evening of September 27, one more issue surfaced, unrelated to the audit. The 20 standard contracts included four Rise of Ix–only tiles (Espionage II, the Contract versions of Harvest 3+ and 4+, and Heighliner III) without the expansion, in place of Spice Refinery I and II and the second copies of Espionage I and Harvest 3+ (`[Main p. 16]`). This correction took the codec to v111 and the observation to v21.

The same evening, a display bug was fixed where a lookup could not tell a board space from a contract sharing its id, so the Deliver Supplies space showed the contract's picture. Lookups now take the kind, and a JavaScript error on any page now counts as an E2E failure.

## Versions and checks

- **Codec:** audit v108, three rulings v109, declining an Agent-box Spy v110, contract set v111. The observation stayed v20, with the encoder byte-identical through the audit, and became v21 with the contract-set fix.
- **Checkpoints:** format-2 checkpoints carry over to a new codec by action identity. 5081 went from v107 to v108 with 32,980 kept, 24 new, 7 dropped, and from v110 to v111 with 32,991 kept, 16 new, 16 dropped (observation: 4,305 columns kept, 22 new, 44 dropped).
- **Checks right after the audit:** 2,279 pytest tests, Ruff, mypy, 3,400 random and heuristic soak games with 0 failures, a codec probe that encodes every legal action with 0 missing, and 7 browser E2E scripts. The evaluation problem set and the observation golden encodings were pinned again as far as the rules moved them.

## Earlier measurements belong to the old rules

Because the rules changed widely, down to base-game cards, the evaluation numbers and checkpoints in the [evaluation corrections]({{< relref path="devlog/2026-09-22-evaluation-corrections.md" lang="en" >}}) and [search AI]({{< relref path="devlog/2026-09-25-policy-search.md" lang="en" >}}) entries (5081, the 7081 exploiter, the search-seat table) all come from the old rules and must not be read as performance under the new ones. Later training and comparisons were re-measured from a baseline on the new rules.

## Restarting M10 on the new rules

**v110 re-adaptation.** From 5081, 1,000 iterations with the same settings reached 6081 (4.5 hours). The ladder, 1,400 mirror games each:

| Comparison | Win-rate difference [95% interval] |
|---|---|
| 5600 vs 5081 | +8.1 points [+3.0, +13.4] |
| 6081 vs 5600 | −3.6 points [−8.9, +1.6], VP margin separated |
| 6081 vs 5081 | +3.1 points [−2.0, +8.1] |

The re-adaptation gain was all there within the first 500 iterations. The win rate against three heuristic opponents (86.5% and 86.8%) is still saturated.

**The `mlp_slots` attempt.** The network reads the whole observation as magnitudes, so the hypothesis was that it cannot tell apart cells that encode "which card is there" as a number, such as the Imperium Row and the current Conflict. Swapping cards confirmed it: the mean change of the value output was 0.0013 for a far Row card and 0.0011 for a Conflict swap, about one thirtieth of a hand-card swap (0.039). A network that adds an embedding row for each such cell, `mlp_slots`, was trained under the same conditions. Its response clearly grew (2.4× for a far Row swap, 6.3× for the Conflict). But against the ordinary MLP trained the same way from 6081, the win-rate difference was +1.3 points [−2.3, +4.9], inconclusive, and after extending to 2,000 iterations it was −4.2 points [−7.8, −0.6], so under the pre-declared rule it was closed as futile. Making the network read the Row and getting a stronger player from that information were separate things, and self-play driven by a single outcome signal did not bring out the latter. In the same stretch, a learner that uses only legal actions made the update step 4.3 times faster, and an iteration dropped from about 15.5 s to 10 s.

**v111 re-adaptation.** After the contract fix, the v110 checkpoints were carried to v111 and trained another 1,000 iterations (7081, about 3 hours). This time the network kept rising for the full 1,000 iterations.

| Comparison (1,400 games each) | Win-rate difference [95% interval] |
|---|---|
| 6600 vs 5600 | +7.0 points [+1.7, +12.3] |
| 7081 vs 6600 | +11.7 points [+6.6, +16.9] |
| 7081 vs 5600 | +18.3 points [+13.1, +23.4] |

7081 became the v111 baseline checkpoint. The +18.3 points should not be read as a general strength gap, though. The reference, 5600, started with the four new contracts' action rows and observation columns at zero and never trained on them, so part of the gap may be "cannot handle the new contracts", and 7081 was not measured against any other opponent. The reason this stretch kept rising is also unknown.

## What remains open

- The search-seat table has not been re-measured under the new rules. The candidates are re-measuring the seat table with 7081, retrying expert iteration with the slot network, and running the same setting longer.
- All training comparisons are two arms with a single training seed.
- The value-sensitivity measurements look only at the value output; what the policy buys in response to the Row was not measured.

## References

- [Audit record: method, findings list, handling, rulings](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/implementation-audits/transcription-audit-2026-09-26.md)
- [Audit-fix merge](https://github.com/jungcheolseung/Dune-Imperium/commit/566109b0)
- [Chani and Fenring Signet correction](https://github.com/jungcheolseung/Dune-Imperium/commit/27ed643e)
- [Standard contract set correction](https://github.com/jungcheolseung/Dune-Imperium/commit/0553c2e3)
- [M10 restart record: v110 re-adaptation and mlp_slots](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-09-27.md)
- [M10 record: v111 re-adaptation and the slot extension](https://github.com/jungcheolseung/Dune-Imperium/blob/c8f61677/docs/evaluation/m10-2026-09-28.md)
- [Previous post: search AI]({{< relref path="devlog/2026-09-25-policy-search.md" lang="en" >}})
