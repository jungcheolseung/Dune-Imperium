# Intrigue implementation audit

This checklist records the Intrigue play boundary and every transcribed
Intrigue card. `docs/rules/player-turns.md` and
`docs/rules/combat-and-round-end.md` remain the rules sources of truth; Dune
Cards Hub card images are the printed-text reference and the DIU dataset is a
transcription bootstrap only.

## Effect DSL

Intrigue cards are transcribed with the composable DSL in
`content/uprising/effect_dsl.py` and executed by
`rules/effect_interpreter.py`.

| Piece | Meaning |
| --- | --- |
| `IntrigueOption(timing, sections)` | One way to play the card. `A —OR— B` cards have two options; stacked lines share one option. |
| `EffectSection(rewards, condition, cost)` | One printed line. It is *applicable* when its condition holds (or has none). |
| Conditions | `InfluenceAtLeast`, `HasHighCouncil`, `SpiesPlacedAtLeast`, `CompletedContractsAtLeast` |
| Costs | `PayResources` (automatic), `LoseInfluence`, `DiscardFromHand` (choice slots) |
| Rewards | `GainResources`, `GainVictoryPoints`, `RecruitTroops`, `DrawPersonalCards`, `DrawIntrigueCards`, `GainInfluence` (a choice slot unless one Faction is allowed), `GainCombatStrength` (transcribed, Combat play not wired yet) |

An option is playable when at least one section applies, the summed resource
costs are affordable, the player has enough total Influence for every
`LoseInfluence` step, and enough hand cards for every `DiscardFromHand` step.
Playing the card pays the resource costs immediately. If the applicable
sections contain choice slots, an `intrigue_choice` frame resolves them one
action at a time (all cost slots first, then reward slots); each step applies
its effect at once so later steps see the updated state. Automatic rewards
resolve after the last slot, draws last so a reshuffle chance frame sits on top
of the stack, and only then is the card discarded.

## Play boundary

| Area | Implemented behavior | Rule-sensitive note |
| --- | --- | --- |
| Timing | Plot options are offered while the owner holds the `turn`, `agent_effects`, or `reveal` frame during Player Turns. | The moment the turn choice is offered is treated as inside the owner's turn, so a Plot card may be played before committing to an Agent or Reveal turn. Project convention; see OQ-015. |
| Mandatory costs | Every applicable cost is paid when the card is played. A card whose applicable costs exceed the player's resources is not offered. | Strict reading of FAQ p. 2. A card with two cost lines whose second line is gated by Influence therefore requires both payments once the gate is met; see OQ-015. |
| Discard order | The card leaves the hidden hand at play time and reaches `intrigue_discard` after its effects resolve. | A draw the card causes can never reshuffle the card itself. Cards discarded while a reshuffle is pending stay in the discard. |
| Deck exhaustion | `rules/intrigue_deck.py` draws what the deck holds, then pushes a replayable chance frame to shuffle the discard for the remainder [FAQ p. 2]. With both piles empty the draw stops short. | `intrigue_trash` is never reshuffled [Main p. 20]. Older draw sites in board effects, combat rewards, and card triggers still read the deck directly and are scheduled to migrate to this boundary. |
| Agent-turn recruits | Troops recruited by a Plot during the owner's Agent turn are added to that frame's `troops_recruited` count, so they may be deployed if the deployment group is still pending. | Once deployment for the turn has been resolved, later recruits stay in the garrison. |
| Visibility | `intrigue_played` and `intrigue_cost_paid` events are public; draws report only counts. | Card identity stays hidden until played [Main p. 7]. |
| Choice slots | `choose_intrigue_faction(faction[, alliance_recipient])` resolves a `LoseInfluence` or multi-Faction `GainInfluence` step; `choose_intrigue_discard(card_id)` resolves a `DiscardFromHand` step. | Losing Influence reuses the shared transition, so Friendship VP loss and Alliance return/transfer (with a recipient choice on ties) behave exactly as in the Reveal exchange. Opponents have no legal actions while the frame is open. |

## Transcribed cards

Printed text was checked against the Dune Cards Hub card image for each card.

| Card | Copies | Options | Rule-sensitive note |
| --- | --- | --- | --- |
| Contingency Plan | 3 | Plot: gain 2 Solari. Combat: 3 strength. | Only the Plot option is offered until Combat play exists. |
| Councilor's Ambition | 1 | Plot: if High Council seat, gain 2 Water. | Unplayable without the seat. |
| Depart for Arrakis | 1 | Plot: pay 2 Spice → recruit 3 troops; Spacing Guild 3 Influence: draw 1 card. | The Spice cost is mandatory; the draw is a separate conditional line. |
| Intelligence Report | 1 | Plot: draw 1 card; with two or more Spies on the board, draw 1 more. | Spies are counted on Observation Posts. |
| Market Opportunity | 1 | Plot: pay 2 Spice → 5 Solari, or pay 5 Solari → 5 Spice. | Two options; each is offered only when affordable. |
| Mercenaries | 1 | Plot: pay 3 Solari → draw 1 Intrigue and recruit 2 troops. | Uses the shared Intrigue draw with reshuffle. |
| Shaddam's Favor | 1 | Plot: recruit 1 troop; Emperor 3 Influence: gain 3 Solari. | The troop is unconditional. |
| Strategic Stockpiling | 1 | Plot: pay 5 Spice → 1 VP; Fremen 3 Influence: pay 3 Water → 1 VP. | With Fremen 3 both costs are mandatory (OQ-015). |
| Buy Access | 1 | Plot: pay 5 Solari → gain 1 Influence with each of two different Factions. | "Choose two" is read as two distinct Factions. |
| Change Allegiances | 1 | Plot: lose 1 Influence → gain 1 Influence; or pay 3 Spice → gain 1 Influence. | The loss option needs at least one Influence anywhere; the gained Faction may equal the lost one. |
| Imperium Politics | 1 | Plot: pay 1 Solari → gain 1 Emperor or Spacing Guild Influence. | DIU lists Spacing Guild/Bene Gesserit; the printed card shows Emperor/Spacing Guild. |
| Opportunism | 1 | Plot: lose 2 Influence (any Factions, may repeat) and pay 2 Solari → 1 VP. | Both losses may come from one Faction with at least two Influence. |
| Sietch Ritual | 1 | Plot: discard a card from hand → gain 1 Bene Gesserit or Fremen Influence. | Unplayable with an empty hand, so effectively an Agent-turn card. The discarded card's hand-discard trigger fires. |
| Backed by CHOAM | 1 (CHOAM) | Plot: lose 1 Influence → 4 Solari. Combat: with two or more completed Contracts, 4 strength. | DIU lists four completed Contracts; the printed card says two. Only the Plot option is offered until Combat play exists. |

Remaining Intrigue identities (25) have setup identity only and are not
offered for play.
