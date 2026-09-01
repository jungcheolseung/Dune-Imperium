# Spy implementation audit

This checklist records the implemented Spy slice and the rule boundaries that
remain deferred. The official summaries in `docs/rules/` are the source of
truth for the transition code.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Supply | Each player always accounts for exactly three Spies between supply and Observation Posts. | Placement spends one Spy and recall returns one Spy. |
| Occupancy | Normal Spy placement selects a post unoccupied by every player. Double Agent may instead share an opponent's post while its owner is spying on the space visited that turn. | The 13 stable post IDs and their board-space edges are recorded in `docs/rules/observation-posts.md`; one player can never place two of their own Spies on one post. |
| Espionage | After paying 1 Spice, the player draws one personal card and may place one Spy. | Declining the optional Spy does not decline the card draw. Bene Gesserit influence remains a separately ordered Agent-turn effect. |
| Empty supply | To place through Espionage with no Spy in supply, the player first selects one of their placed Spies to recall without effect and then must select an empty post. Declining the optional placement stays available until a recall is chosen. | Recall and placement are separate decisions so the engine does not enumerate every ordered pair as one action. Once recall is chosen, placement cannot be declined, and placement re-checks the supply when it resolves: if a freely ordered effect consumed the recalled Spy, the recall choice reopens instead of failing [Main pp. 11, 20]. |
| Gather Intelligence | Immediately after Agent placement, a connected Spy opens a decline-or-recall decision before Agent-card, board-space, deployment, or Faction effects. Recalling draws one personal card. | At most one Spy can be used for Gather Intelligence in a turn. An empty deck uses the shared replayable discard reshuffle; only an empty deck and discard pile suppress the recall action. |
| Infiltrate | An otherwise legal Agent card may enter a space occupied by any number of opponents by selecting and recalling one connected Spy as part of the Agent action. | The recalled Spy is removed before the Gather Intelligence window, so it cannot be used for both effects. One recall admits the Agent however many opponent Agents share the space (OQ-006 decided convention, [Main p. 11]). |
| Spy Agent icon | A card's Spy Agent icon makes every space connected to one of the player's placed Spies an available Agent destination. | Destination access does not recall the Spy. Transcribed Imperium cards use the same destination path; three remaining base cards still await full play-data transcription. |
| Conflict reward | A Spy reward selects one globally empty post and spends a Spy from supply. | This existing reward path does not currently offer the empty-supply recall permission because the reward itself is mandatory only when executable. |
| Agent-card placement | Bene Gesserit Operative selects any globally empty post; Reliable Informant is restricted to posts connected to Emperor, Bene Gesserit, or Spacing Guild spaces; Double Agent adds its conditional sharing exception. | With an empty supply, recall and placement are separate mandatory decisions. A restricted effect offers only recalls that can open a destination when every eligible post is occupied. |
| Acquisition placement | Acquiring Strike Fleet or Guild Spy immediately opens a Spy placement choice over the current Reveal frame. | The acquired card is discarded and the row is refilled before choosing the post; an empty supply uses the same recall-then-place sequence and then returns to Reveal purchasing. |
| Current-turn recall | The Agent effect frame records whether Infiltrate, Gather Intelligence, or Espionage recalled a Spy during that Agent turn. | Strike Fleet recruits three troops, Rebel Supplier recruits two, Imperial Spymaster draws one Intrigue card, and Public Spectacle gains chosen Faction Influence from this turn-scoped flag. |
| Reveal recall | Spy Network checks for at least two placed Spies when Reveal begins, then requires the owner to choose and recall one before drawing one Intrigue card. | The choice frame blocks purchases and other turn actions until it returns to the underlying Reveal frame. With fewer than two Spies, no choice opens. |
| Reveal recall cost | In High Places may recall any two placed Spies to add two Persuasion, or decline without changing state. | Two-Spy payment is one atomic action selected from canonical unordered pairs, keeping the action catalog smaller and preventing partial payment. |
| Reveal placement | Public Spectacle and Wheels Within Wheels place one Spy during Reveal. | The serial choice blocks purchasing until placement finishes; an empty supply requires recalling one owned Spy first, without triggering a recall benefit. |
| Reveal placement alternative | Undercover Asset chooses between placing one Spy and gaining two strength. | Before a Spy is recalled, either branch remains available. Recalling for an empty supply commits to placement so the recall cannot be taken before switching to strength. |
| Spied Factions | Guild Spy treats a Faction as spied on when one of its owner's Observation Posts is connected to a space of that Faction. | Acquiring The Spice Must Flow during that Reveal gains one Influence for each distinct matching Faction; multiple posts connected to the same Faction do not duplicate it. |

## Deferred Spy systems

- General `Recall Spy` icons and remaining card-specific Spy effects.
- The multiple-opponent Infiltrate interpretation (OQ-006) and the Gather
  Intelligence/contract ordering (OQ-011) are now decided project rulings in
  `docs/rules/open-questions.md`; they reopen only if an official ruling
  appears.

## Action and replay compatibility

Espionage added one decline action and 13 each of recall and placement actions.
Gather Intelligence added one decline action and 13 post-specific recall
actions in codec version 4. Infiltrate adds every valid starting-card,
board-space, and connected-post combination, changing the fixed action catalog
from 469 entries to 534 entries in version 5. Endgame actions later advance the
catalog to version 6. Bene Gesserit Operative adds 13 card-placement and 13
card-recall templates, while its two physical copies add eight Agent actions;
personal-card content advances the replay default to version 21 with a
1196-entry catalog. Reliable Informant's four Agent templates then advance the
default at that slice to version 22 with 1200 entries; it reuses the card-level Spy
choice templates. Strike Fleet adds 13 acquisition-placement, 13
acquisition-recall, and 51 Spy-icon Agent templates, advancing that slice's
default to version 23 with 1277 entries.
Imperial Spymaster adds 51 Agent templates and advances that slice's default to
version 24 with 1328 entries.
Spy Network adds 13 Reveal-recall templates and advances that slice's default to
version 25 with 1341 entries.
In High Places adds one decline, 78 unordered two-Spy recall, and eight Agent
templates, advancing that slice's default to version 26 with 1428 entries.
Rebel Supplier's two physical copies add 26 City Agent templates, advancing the
default at that slice to version 27 with 1454 entries.
Dangerous Rhetoric adds 51 Spy-icon Agent templates and four shared Faction
choice templates, advancing that slice's default to version 28 with 1509 entries.
Public Spectacle's two copies add 102 Spy-icon Agent templates, and Reveal
placement adds 13 placement and 13 recall templates, advancing that slice's
default to version 29 with 1637 entries.
Wheels Within Wheels reuses the Reveal choices and adds 51 Spy-icon Agent
templates, advancing that slice's default to version 30 with 1688 entries.
Guild Spy reuses acquisition placement and hand-discard choices while adding 51
Spy-icon Agent templates, advancing that slice's default to version 40 with 2193
entries.
Covert Operation adds another 51 Spy-icon Agent templates and 93 opponent-owned
discard templates, advancing that slice's default to version 41 with 2337
entries.
The two Calculus of Power copies add 102 Spy-icon Agent templates plus 94 Reveal
trash choices, advancing the default at that slice to version 42 with 2533
entries. Later non-Spy card slices advance the current replay default to codec
version 52 with 3111 entries without changing these Spy templates.

## Agent-card placement and supply

An Agent-card Spy placement (`place_agent_card_spy`) is offered only while
the owner has a Spy in supply at that moment; otherwise the card offers
`recall_spy_for_agent_card` again [Main pp. 11, 20]. The earlier
`agent_card_spy_recalled` flag is no longer sufficient on its own because the
free ordering of Agent-turn groups lets the Espionage board effect consume a
Spy that was recalled for the card.

