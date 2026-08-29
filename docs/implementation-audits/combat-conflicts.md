# Combat and Conflict implementation audit

This checklist records rule-sensitive implementation choices so they can be
reviewed without reading the transition code. Official rule summaries under
`docs/rules/` take precedence over external structured card data.

## Verified behavior

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Ranking | Four-player zero-strength and tie rules determine reward rows. | A tied first place has no winner and leaves the Conflict on the board. |
| Sandworms | A player with at least one sandworm receives the assigned reward twice. | Control and battle icons are never doubled. Optional costs are offered twice. |
| Troop rewards | Troops move from supply to garrison before Combat cleanup. | Rewards resolve before Conflict troops return to supply, so an empty supply can limit recruitment. |
| Contract icon | With CHOAM disabled, each icon grants 2 Solari. With CHOAM enabled, every repeated icon opens the shared public Contract market choice. | Sandworm doubling repeats the selection. If the market runs out between repetitions, each remaining icon converts to 2 Solari. |
| Trash icon | The player may decline or trash from hand, discard pile, or in play. | Reserve cards return to their Reserve stack instead of entering the trash zone. |
| Spy reward | Each repeated reward selects an empty Observation Post and spends one Spy from supply. | Globally occupied posts are excluded. No choice is opened without a Spy or empty post. |
| Control | A sole winner replaces the marker at the printed critical location; every later visit pays its controller 1 Solari or spice as printed. | There are exactly three critical locations and three markers per player; already owning all three needs no fourth-marker choice. |
| Tier III VP | Printed VP and optional Spice/Solari payment rewards repeat under a sandworm. | Each repeated optional reward requires its own payment; Control still occurs once. |
| Propaganda | Each `Choose two` requires two distinct Factions. | A sandworm repeats the whole reward, so the same pair may be chosen again in the second group. |
| Arrakeen Spy cost | The player may decline or recall one selected pair of placed Spies for 1 VP. | Spies return to supply; having fewer than two placed Spies leaves only decline. |
| Influence | Friendship VP, printed track bonuses, Alliance acquisition or upward transfer, and Influence loss use shared transitions. | Captured Mentat proves that a legal loss reaches multiple recipients only when they were tied with the holder; the holder explicitly selects one as required by the FAQ. |
| Shield Wall | Setup begins with the token present; the six printed protected Conflicts remove Maker-space sandworm actions until permanent destruction. | Sietch Tabr exposes explicit keep/destroy choices; the Conflict-card symbol denotes protection, not detonation. |
| Battle icons | A sole winner takes the Conflict face up and a mandatory same-icon pair with a face-up Objective or won Conflict flips both cards for 1 VP. | Multiple same-icon candidates are unreachable with official content, so the guard against them is a content tripwire; the wild icon never pairs during Combat. See [objectives.md](objectives.md). |
| Combat Intrigue priority | Participants rotate from First Player order until all pass consecutively, even when they hold Intrigue cards. | Combat-timed options of the transcribed Intrigue deck are offered to the priority holder with units in the Conflict; see [intrigue.md](intrigue.md). |

## Explicitly retained guards

- `_matching_battle_card` raises if a Conflict icon is untranscribed or if
  two same-icon face-up candidates ever become reachable; official content
  cannot produce either state today ([objectives.md](objectives.md)).

## Project conventions and unresolved ordering

- Rewards are traversed in rank order and player seat order. Official sources do
  not specify the order among players tied for the same reward row.
- Intrigue cards are consequently drawn in that deterministic traversal order.
  This is an engine convention until an official ruling supplies another order.
- Automatic parts of all assigned rewards are applied before queued player
  choices. Current supported choices do not alter another player's already
  calculated rank, but future interactive rewards must re-audit this sequencing.
- A critical-location Control bonus is paid immediately after Agent placement,
  before the visitor resolves freely ordered Agent, board, and Faction effects.
  OQ-008 remains open for future content where this relative timing can change a
  legal choice or result.

## External-data discrepancies found

- DIU's Trade Dispute entry lists only hand and played cards for its trash icon.
  The official general trash rule also includes the discard pile and makes the
  black trash icon optional.
- DIU uses inconsistent spellings such as `Imperial Bassin` and `Spice Freights`;
  local IDs and printed English names are normalized independently.
