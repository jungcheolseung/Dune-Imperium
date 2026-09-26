# Spy implementation audit

This checklist records the implemented Spy slice and the rule boundaries that
remain deferred. The official summaries in `docs/rules/` are the source of
truth for the transition code.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Supply | Each player always accounts for exactly three Spies between supply and Observation Posts. | Placement spends one Spy and recall returns one Spy. |
| Occupancy | Normal Spy placement selects a post unoccupied by every player. Double Agent's Spy goes only on a post connected to the space its Agent visited that turn, and may share that post with another player's Spy ("[Spy] spying on the board space you sent an Agent to this turn. You may place this Spy on the same observation post as another player's Spy." [Double Agent card]; the "[Spy] on [icon]" placement limit [Main p. 20]). | The 13 stable post IDs and their board-space edges are recorded in `docs/rules/observation-posts.md`; one player can never place two of their own Spies on one post. |
| Espionage | After paying 1 Spice, the player draws one personal card and may place one Spy. | Declining the optional Spy does not decline the card draw. Bene Gesserit influence remains a separately ordered Agent-turn effect. |
| Empty supply | To place through Espionage with no Spy in supply, the player first selects one of their placed Spies to recall without effect and then must select an empty post. Declining the optional placement stays available until a recall is chosen. | Recall and placement are separate decisions so the engine does not enumerate every ordered pair as one action. Once recall is chosen, placement cannot be declined, and placement re-checks the supply when it resolves: if a freely ordered effect consumed the recalled Spy, the recall choice reopens instead of failing [Main pp. 11, 20]. |
| Gather Intelligence | Immediately after Agent placement, a connected Spy opens a decline-or-recall decision before Agent-card, board-space, deployment, or Faction effects. Recalling draws one personal card. | At most one Spy can be used for Gather Intelligence in a turn. An empty deck uses the shared replayable discard reshuffle; only an empty deck and discard pile suppress the recall action. |
| Infiltrate | An otherwise legal Agent card may enter a space occupied by any number of opponents by selecting and recalling one connected Spy as part of the Agent action. | The recalled Spy is removed before the Gather Intelligence window, so it cannot be used for both effects. One recall admits the Agent however many opponent Agents share the space (OQ-006 decided convention, [Main p. 11]). |
| Spy Agent icon | A card's Spy Agent icon makes every space connected to one of the player's placed Spies an available Agent destination. | Destination access does not recall the Spy. Transcribed Imperium cards use the same destination path; three remaining base cards still await full play-data transcription. |
| Conflict reward | A Spy reward selects one globally empty post (Deep Cover: any post without the owner's Spy) and spends a Spy from supply; one frame per printed Spy, times the sandworm multiplier. | With the supply empty the owner may recall one of their Spies first or decline [Main pp. 11, 20] (`recall_spy_for_combat_reward`, `decline_combat_reward_spy`); after the recall the placement is mandatory. Corrected 2026-09-26: the reward used to open only as many frames as the supply held at payment. |
| Contract and Leader rewards | Contract Spy rewards (Arrakeen II, Research Station I, Harvest 3+/4+, Deliver Supplies' Deep Cover) and Leader Spy placements (Feyd-Rautha's Personal Training Spy spaces, Lady Margot Fenring's Arrakis Informant, Staban Tuek's Unseen Network, Mohiam's paid Listeners Spy) follow the same rule. | With the supply empty they offer `decline_contract_spy` / `decline_leader_spy_placement` beside the recalls until one is made (OQ-057 (14)); Count Hasimir Fenring's and Mohiam's unpaid "— OR —" choices keep their own decline only until a recall is made: the recall begins a Spy half, so afterwards Fenring may only place the Spy (no trash, no decline) and Mohiam may place it next to the Landsraad or pay for a Spy anywhere. Corrected 2026-09-26: the recall used to be forced. |
| Agent-card placement | Bene Gesserit Operative selects any globally empty post; Reliable Informant is restricted to posts connected to Emperor, Bene Gesserit, or Fremen spaces (re-read from the card face 2026-09-26: the third target icon is the blue Fremen sietch badge, not the red Spacing Guild infinity symbol); Double Agent is restricted to posts connected to the space visited that turn, empty or holding another player's Spy, never the owner's own. | With an empty supply, recall and placement are separate mandatory decisions. A restricted effect offers only recalls that can open a destination when every eligible post is occupied. |
| Acquisition placement | Acquiring Strike Fleet or Guild Spy immediately opens a Spy placement choice over the current Reveal frame. | The acquired card is discarded and the row is refilled before choosing the post; an empty supply uses the same recall-then-place sequence and then returns to Reveal purchasing. |
| Current-turn recall | "If you recalled a Spy this turn:" reads the seat counter `PlayerState.spies_recalled_turn`, which every recall of the seat's own Spies raises: Infiltrate, Gather Intelligence, Espionage, Signet, an Intrigue Recall Spy cost, and the recall-first before a placement [Main pp. 11, 20]. The counter restarts when the seat's turn opens and at Round Start. | Strike Fleet recruits three troops, Rebel Supplier recruits two, Imperial Spymaster draws one Intrigue card, Public Spectacle gains chosen Faction Influence, and Corrupt Bureaucrat takes a contract; none of the faces limits how the Spy was recalled, the same all-paths scope as Spy Drones (OQ-044 (d)). Until 2026-09-26 an Agent-frame flag counted only Infiltrate, Gather Intelligence, Espionage and Signet recalls. |
| Reveal recall | Spy Network checks for at least two placed Spies when Reveal begins; the owner may then recall one to draw one Intrigue card, or decline, since the recall is an arrow cost [Main p. 20] (2026-09-26). | The choice frame blocks purchases and other turn actions until it returns to the underlying Reveal frame. With fewer than two Spies, no choice opens. |
| Reveal recall cost | In High Places may recall any two placed Spies to add three Persuasion [In High Places card] (+2 until 2026-09-26), or decline without changing state. | Two-Spy payment is one atomic action selected from canonical unordered pairs, keeping the action catalog smaller and preventing partial payment. |
| Reveal placement | Public Spectacle and Wheels Within Wheels place one Spy during Reveal. | The serial choice blocks purchasing until placement finishes; with an empty supply the owner may first recall one owned Spy, without a recall benefit, or decline the placement (OQ-057 (14), 2026-09-26); after the recall the placement is mandatory. |
| Reveal placement alternative | Undercover Asset chooses between placing one Spy and gaining two strength. | Before a Spy is recalled, either branch remains available. Recalling for an empty supply commits to placement so the recall cannot be taken before switching to strength. |
| Reveal placement, two icons | Covert Operation's Reveal prints two Spy icons and no Persuasion [Covert Operation card] (two Persuasion until 2026-09-26). | `PLACE_TWO_SPIES` resolves each icon through the plain Reveal Spy placement (as `PLACE_SPY`, so the same supply and recall rules apply); after the first icon the frame becomes a `PLACE_SPY` frame of the same card, which may be deferred like any Reveal choice [Main p. 12]. |
| Agent-card Bond Spy | In High Places' Agent box draws one card and places one plain Spy when another Bene Gesserit card is in play [In High Places card] (one water until 2026-09-26). | The Bond is judged when the box resolves; the Spy opens the shared `spy_placement` frame under the draw (any unoccupied post; mandatory with a Spy in supply, optional recall first with an empty one, OQ-057 (14)). |
| Spied Factions | Guild Spy treats a Faction as spied on when one of its owner's Observation Posts is connected to a space of that Faction. | Acquiring The Spice Must Flow during that Reveal gains one Influence for each distinct matching Faction; multiple posts connected to the same Faction do not duplicate it. |

## Spy boundaries

- (2026-09-10) No Spy effect is left untranscribed. The current content prints
  no standalone "Recall Spy" Agent icon — `AgentIcon` carries the seven board
  icons plus `SPY` — and every card-specific recall is its own effect member
  (`RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED`,
  `MAY_RECALL_SPY_FOR_THREE_STRENGTH`, and the turn-scoped recall flags above).
  A future expansion that prints a standalone recall icon would need one.
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

