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
| Conflict reward | A Spy reward selects one globally empty post and spends a Spy from supply. | This existing reward path does not currently offer the empty-supply recall permission because the reward itself is mandatory only when executable. |

## Deferred Spy systems

- `Infiltrate`: recall a connected Spy to enter a space occupied by another
  player's Agent.
- The Spy Agent icon as an alternate destination-access icon.
- General `Recall Spy` icons and card-specific Spy effects.
- The multiple-opponent Infiltrate interpretation tracked by OQ-006 and the
  Gather Intelligence/contract ordering tracked by OQ-011.

## Action and replay compatibility

Espionage added one decline action and 13 each of recall and placement actions.
Gather Intelligence adds one decline action and 13 post-specific recall
actions. The fixed action catalog therefore changes from version 3 (455
entries) to version 4 (469 entries), and new replay records default to codec
version 4.
