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
| Conditions | `InfluenceAtLeast`, `HasHighCouncil`, `SpiesPlacedAtLeast`, `CompletedContractsAtLeast`, `SandwormsInConflictAtLeast` |
| Triggers | `IntrigueOption.trigger` marks an option that does nothing when played: the card waits face up and its sections fire later [FAQ p. 2]. `OnRevealAcquisitionThisRound` fires once per card the owner acquires during their own Reveal turn. Trigger sections must be free and unconditional. |
| Costs | `PayResources` (automatic), `LoseInfluence`, `DiscardFromHand`, `RecallSpy`, `RetreatTroops` (choice slots) |
| Rewards | `GainResources`, `GainVictoryPoints`, `RecruitTroops`, `DrawPersonalCards`, `DrawIntrigueCards`, `GainInfluence` (a choice slot unless one Faction is allowed), `DestroyShieldWall` (a detonate/keep choice slot while the token is present), `DeployFromGarrison` (a count choice slot), `SummonSandworm` (automatic; no effect against a protected Conflict), `TrashPersonalCard` (an optional trash slot over hand, discard and play), `PlaceSpy` (a placement slot, recall-first when supply is empty), `RetreatTroops` (a count slot, also usable as a cost), `TakeContract` (automatic; opens the Contract market frame), `GainCombatStrength` (automatic; adds to `combat_strength` during Combat), `AcquireCardUpTo` (a target choice slot over the Imperium Row and Reserve within a printed cost cap) |

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
| Timing | Plot options are offered while the owner holds the `turn`, `agent_effects`, or `reveal` frame during Player Turns. | The moment the turn choice is offered is treated as inside the owner's turn, so a Plot card may be played before committing to an Agent or Reveal turn. The window closes when the last pending Agent-turn group resolves (the frame auto-advances), so a Plot meant for the end of the turn must be played before that group. Project convention; see OQ-015. |
| Combat timing | Combat options are offered in the `combat_intrigue` frame to the participant who currently holds priority; playing one restarts the consecutive-pass count and its strength applies immediately [Main p. 14]. Choice slots open on top of the Combat frame and return to it. | Only players with units in the Conflict ever hold the frame, so `GainCombatStrength` never lands on a unit-less player. "When you win" cards are not transcribed yet. |
| Retreats in Combat | `retreat_intrigue_troops(count)` moves troops to the garrison and removes two strength each; a player left without units keeps no strength [Main pp. 12, 14]. After the card finishes, `refresh_combat_participants` drops unit-less players from the loop at once and hands priority to the next remaining participant (OQ-003 convention). | If nobody remains the Intrigue step ends and rewards resolve. Players without units at Combat start never enter the loop. |
| Reveal-turn draws | During the `reveal` frame, Plot options whose applicable sections draw personal cards — or would acquire a card to hand (`AcquireCardUpTo.to_hand_if` currently holding) — are withheld. | FAQ p. 3 says cards drawn during a Reveal turn are revealed at once and used this turn; that boundary is not implemented yet, so options that would put an unrevealed card in hand wait until the Reveal is over. Inspire Awe stays available mid-Reveal while its acquisition goes to the discard pile. |
| Face-up triggers | Playing a triggered option moves the card from the hidden Intrigue hand to the owner's public `intrigue_faceup` zone [FAQ p. 2]; no choice frame opens and no reward resolves yet. `rules/intrigue_triggers.py` fires the per-acquisition trigger at every Reveal-turn acquisition site (Persuasion Reserve/Row acquisitions and Intrigue-effect acquisitions made while the owner's Reveal frame is open) and recruits are supply-limited. When the owner's Reveal turn ends, the card moves to the Intrigue discard whether or not it ever fired (OQ-016). | Face-up identity is public in every observation. Agent-turn acquisitions (Price is No Object) are outside the printed window. The reshuffle never touches the face-up zone. |
| Cost-capped acquisition | An `AcquireCardUpTo` slot offers every Imperium Row card and non-empty Reserve stack whose printed cost is within the cap [Main p. 13]; no Persuasion is spent and the acquisition is not declinable. The card lands in the owner's discard pile [Main pp. 6, 13], or in hand when the card text's condition holds at resolution. The Row position refills at once and acquire boxes resolve immediately [Main pp. 13, 20]; a place-Spy box pushes the shared `acquisition_spy` frame and a Contract box opens the Contract market, both only after the Intrigue card has finished resolving. | An option with no target within the cap is not offered, like the other infeasible-reward gates (Prepare the Way at cost 2 makes this rare). Acquire-box follow-up frames therefore sit above the timing frame while the Intrigue card is already in `intrigue_discard`; the consecutive-pass reset happens before they open. Contract completion for the acquired card is checked, though no card within cost 3 carries one. |
| Mandatory costs | Every applicable cost is paid when the card is played. A card whose applicable costs exceed the player's resources is not offered. | Strict reading of FAQ p. 2. A card with two cost lines whose second line is gated by Influence therefore requires both payments once the gate is met; see OQ-015. |
| Discard order | The card stays in the owner's Intrigue hand while it resolves (including while an `intrigue_choice` frame is open) and reaches `intrigue_discard` after its effects resolve. | Card conservation holds at every state. A draw the card causes can never reshuffle the card itself. Cards discarded while a reshuffle is pending stay in the discard. |
| Deck exhaustion | `rules/intrigue_deck.py` draws what the deck holds, then shuffles the discard through a replayable chance frame for the remainder [FAQ p. 2]. With both piles empty the draw stops short. Every other draw site (board effects, Combat rewards, acquisition and trash triggers, Agent-card and Reveal draws, the Bene Gesserit Influence bonus) draws what it can and queues the shortfall in `GameState.pending_intrigue_draws`; the dispatcher resolves the queue before the next player decision. | `intrigue_trash` is never reshuffled [Main p. 20]. An Intrigue card's own draw resolves before the card is discarded, so the card never joins the reshuffle; queued draws from other effects resolve after their transition, so a card discarded by that transition may be reshuffled. The Influence track-bonus event now reports only the count, not the card identity [Main p. 7]. |
| Agent-turn recruits | Troops recruited by a Plot during the owner's turn are recorded on the `turn` or `agent_effects` frame; the effect frame inherits the pre-placement count, so they may be deployed if the deployment group is still pending. | Once deployment for the turn has been resolved, later recruits stay in the garrison. |
| Units mid-Reveal | Troops or sandworms that a Plot puts into the Conflict during the owner's Reveal turn update `combat_strength` and the Reveal frame's strength like Desert Power's sandworm: the first units also make the revealed sword strength count [Main p. 13]. Before the Reveal they simply move. | A section whose only reward is the detonation icon is not applicable once the Shield Wall is gone, so Detonation then offers only its deployment option. |
| Harvest accounting | Spice paid for an Intrigue during the Agent-turn frame is added to `spice_spent_after_placement`; Spice an Intrigue grants counts like any other gain. | Harvest Spice Contracts count Spice gained from every source during the turn at a Maker space [Main p. 16], so paying Spice must not hide the harvest while Intrigue gains legitimately contribute. |
| Visibility | `intrigue_played` and `intrigue_cost_paid` events are public; draws report only counts. | Card identity stays hidden until played [Main p. 7]. |
| Choice slots | `choose_intrigue_faction(faction[, alliance_recipient])` resolves a `LoseInfluence` or multi-Faction `GainInfluence` step; `choose_intrigue_discard(card_id)` resolves a `DiscardFromHand` step; `detonate_shield_wall`/`keep_shield_wall` resolve a `DestroyShieldWall` step; `deploy_intrigue_troops(count)` resolves a `DeployFromGarrison` step; `trash_intrigue_card(card_id)`/`decline_intrigue_trash` resolve a `TrashPersonalCard` step; `place_intrigue_spy(post_id)` and `recall_spy_for_intrigue(post_id)` resolve `PlaceSpy` and `RecallSpy` steps. Choice slots resolve before the automatic rewards, so a card drawn by the same option is not yet available to a trash slot printed after it (project convention; see Cunning). | Losing Influence reuses the shared transition, so Friendship VP loss and Alliance return/transfer (with a recipient choice on ties) behave exactly as in the Reveal exchange. Opponents have no legal actions while the frame is open. |

## Transcribed cards

Printed text was checked against the Dune Cards Hub card image for each card.

| Card | Copies | Options | Rule-sensitive note |
| --- | --- | --- | --- |
| Contingency Plan | 3 | Plot: gain 2 Solari. Combat: 3 strength. | Each half is offered only at its timing. |
| Councilor's Ambition | 1 | Plot: if High Council seat, gain 2 Water. | Unplayable without the seat. |
| Depart for Arrakis | 1 | Plot: pay 2 Spice → recruit 3 troops; Spacing Guild 3 Influence: draw 1 card. | The Spice cost is mandatory; the draw is a separate conditional line. |
| Intelligence Report | 1 | Plot: draw 1 card; with two or more Spies on the board, draw 1 more. | Spies are counted on Observation Posts. |
| Market Opportunity | 1 | Plot: pay 2 Spice → 5 Solari, or pay 5 Solari → 5 Spice. | Two options; each is offered only when affordable. |
| Mercenaries | 1 | Plot: pay 3 Solari → draw 1 Intrigue and recruit 2 troops. | Uses the shared Intrigue draw with reshuffle. |
| Shaddam's Favor | 1 | Plot: recruit 1 troop; Emperor 3 Influence: gain 3 Solari. | The troop is unconditional. |
| Strategic Stockpiling | 1 | Plot: pay 5 Spice → 1 VP; Fremen 3 Influence: pay 3 Water → 1 VP. | With Fremen 3 both costs are mandatory (OQ-015). |
| Buy Access | 1 | Plot: pay 5 Solari → gain 1 Influence with each of two different Factions. | "Choose two" is read as two distinct Factions. |
| Call to Arms | 1 | Plot: during your Reveal turn this round, whenever you acquire a card, recruit 1 troop. | Waits face up until the owner's Reveal turn [FAQ p. 2]; fires per acquisition, including one an Intrigue effect makes mid-Reveal; expires with that Reveal turn (OQ-016). |
| Change Allegiances | 1 | Plot: lose 1 Influence → gain 1 Influence; or pay 3 Spice → gain 1 Influence. | The loss option needs at least one Influence anywhere; the gained Faction may equal the lost one. |
| Imperium Politics | 1 | Plot: pay 1 Solari → gain 1 Emperor or Spacing Guild Influence. | DIU lists Spacing Guild/Bene Gesserit; the printed card shows Emperor/Spacing Guild. |
| Impress | 1 | Combat: 2 strength; acquire a card that costs 3 or less. | The printed cap is 3 (the handoff briefly recorded 4). The strength lands when the card finishes, after the acquisition slot. |
| Inspire Awe | 1 | Plot: acquire a card that costs 3 or less; with a sandworm in the Conflict the card goes to hand. | The sandworm sentence only changes the destination; it never gates playability. The to-hand form is withheld during the owner's Reveal turn (OQ-015). |
| Opportunism | 1 | Plot: lose 2 Influence (any Factions, may repeat) and pay 2 Solari → 1 VP. | Both losses may come from one Faction with at least two Influence. |
| Sietch Ritual | 1 | Plot: discard a card from hand → gain 1 Bene Gesserit or Fremen Influence. | Unplayable with an empty hand, so effectively an Agent-turn card. The discarded card's hand-discard trigger fires. |
| Backed by CHOAM | 1 (CHOAM) | Plot: lose 1 Influence → 4 Solari. Combat: with two or more completed Contracts, 4 strength. | DIU lists four completed Contracts; the printed card says two. |
| Weirding Combat | 1 | Combat: 3 strength; Bene Gesserit 3 Influence: +2. | Conditional line, no cost. |
| Questionable Methods | 1 | Combat: 1 strength; lose 1 Influence → +4. | The Influence line is mandatory under OQ-015(b), so the card needs at least one Influence to play. |
| Find Weakness | 1 | Combat: 2 strength; recall a Spy → +3. | The recall line is mandatory under OQ-015(b), so the card needs a placed Spy to play. |
| Devour | 1 | Combat: 2 strength; with a sandworm in the Conflict, +2 and an optional trash. | Trash slot resolves before the strength is added; both belong to the same section. |
| Go to Ground | 1 | Combat: retreat one or two troops → place a Spy. | The Spy placement still resolves even if the retreat emptied the Conflict; the player then leaves the loop. |
| Spice is Power | 1 | Combat: retreat three troops → 3 Spice; or pay 3 Spice → 6 strength. | Each half is offered only when affordable. |
| Tactical Option | 1 | Combat: 2 strength; or retreat any number of troops. | "Any number" is read as one or more. |
| Reach Agreement | 1 (CHOAM) | Combat: retreat one or two troops → take a Contract. | Opens the shared Contract market frame on top of the Combat frame; not playable with the module off. |
| Detonation | 2 | Plot: Shield Wall detonation icon; or deploy up to four garrison troops to the Conflict. | The icon is a choice [Main pp. 10, 20]; the deployment option needs at least one garrison troop. |
| Cunning | 1 | Plot: draw 1 card; or pay 1 Spice → draw 1 card and optionally trash a card. | The trash choice is taken before the draw resolves, so the drawn card cannot be the one trashed (convention, OQ-015). |
| Special Mission | 2 | Plot: place a Spy on a Bene Gesserit-connected post; or recall a Spy → Shield Wall detonation icon and 2 Spice. | Placement needs a Spy in supply or a placed Spy to recall first; the recall option needs a placed Spy. |
| Unexpected Allies | 1 | Plot: pay 2 Water → Shield Wall detonation icon, then summon 1 sandworm. | No Maker Hooks marking on the card, so none is required. Keeping the wall against a protected Conflict leaves the sandworm effect with nothing to do [Main p. 20]; the Water stays paid. |

Remaining Intrigue identities (10) have setup identity only and are not
offered for play.
