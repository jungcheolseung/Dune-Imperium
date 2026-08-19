# Spy implementation audit

This checklist records the implemented Spy slice and the rule boundaries that
remain deferred. The official summaries in `docs/rules/` are the source of
truth for the transition code.

## Implemented behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Supply | Each player always accounts for exactly three Spies between supply and Observation Posts. | Placement spends one Spy and recall returns one Spy. |
| Occupancy | A Spy can be placed only on an Observation Post unoccupied by every player. | The 13 stable post IDs and their board-space edges are recorded in `docs/rules/observation-posts.md`. |
| Espionage | After paying 1 Spice, the player draws one personal card and may place one Spy. | Declining the optional Spy does not decline the card draw. Bene Gesserit influence remains a separately ordered Agent-turn effect. |
| Empty supply | To place through Espionage with no Spy in supply, the player first selects one of their placed Spies to recall without effect and then must select an empty post. | Recall and placement are separate decisions so the engine does not enumerate every ordered pair as one action. Once recall is chosen, placement cannot be declined. |
| Gather Intelligence | Immediately after Agent placement, a connected Spy opens a decline-or-recall decision before Agent-card, board-space, deployment, or Faction effects. Recalling draws one personal card. | At most one Spy can be used for Gather Intelligence in a turn. If the personal deck is empty, only decline is exposed because discard reshuffling remains deferred. |
| Infiltrate | An otherwise legal Agent card may enter a space occupied by one opponent by selecting and recalling a connected Spy as part of the Agent action. | The recalled Spy is removed before the Gather Intelligence window, so it cannot be used for both effects. Multiple-opponent occupancy remains deferred under OQ-006. |
| Spy Agent icon | A card's Spy Agent icon makes every space connected to one of the player's placed Spies an available Agent destination. | Destination access does not recall the Spy. Imperium-card icon transcription remains part of the broader content milestone. |
| Conflict reward | A Spy reward selects one globally empty post and spends a Spy from supply. | This existing reward path does not currently offer the empty-supply recall permission because the reward itself is mandatory only when executable. |
| Agent-card placement | Bene Gesserit Operative selects any globally empty post; Reliable Informant is restricted to posts connected to Emperor, Bene Gesserit, or Spacing Guild spaces. | With an empty supply, recall and placement are separate mandatory decisions. A restricted effect offers only recalls that can open a destination when every eligible post is occupied. |
| Acquisition placement | Acquiring Strike Fleet immediately opens a Spy placement choice over the current Reveal frame. | The acquired card is discarded and the row is refilled before choosing the post; an empty supply uses the same recall-then-place sequence and then returns to Reveal purchasing. |
| Current-turn recall | The Agent effect frame records whether Infiltrate, Gather Intelligence, or Espionage recalled a Spy during that Agent turn. | Strike Fleet reads this flag to recruit three troops; the flag is scoped to one turn and cannot carry into a later Agent action. |

## Deferred Spy systems

- General `Recall Spy` icons and remaining card-specific Spy effects.
- The multiple-opponent Infiltrate interpretation tracked by OQ-006 and the
  Gather Intelligence/contract ordering tracked by OQ-011.

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
current default to version 22 with 1200 entries; it reuses the card-level Spy
choice templates. Strike Fleet adds 13 acquisition-placement, 13
acquisition-recall, and 51 Spy-icon Agent templates, advancing the current
default to version 23 with 1277 entries.
