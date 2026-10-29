# app_ai: Rise of Ix on the original board (port notes)

> The plan, slices and status are in `docs/app-ai-plan.md` §13. This file
> records how each Rise of Ix decision is answered and every judgement call,
> so later readers can tell the app's behaviour from our mapping of it.

Status (2026-10-30, branch `claude/base-ix-p6-ix`): every Rise of Ix decision
our engine offers in an original + Ix game (draft, promos) is answered by an
app class. The census has no random answer and no unported class: 15 games
per level, seeds 8100+. The six Ix Leaders wait for P4e, which makes them
candidates.

Unlike the Bloodlines and Scouts files beside this one, Rise of Ix is a
**faithful port**: the Steam app plays Rise of Ix itself. Values come from the
app's classes. Our work is the mapping from our engine's decisions to the
app's prompts.

## Sources

- **Specs** (app analysis, assets `analysis/ai/spec/`):
  - `rix-tech.md`: tiles, Freighter (§4.6–4.7), Dreadnought space (§6.7),
    engine order (§7.4).
  - `generic-abilities.md` §4.2: the acquire-destination picker.
  - `05-agent-placement.md` §10: `GetBestOption`.
- **Decompiled C:** assets `ghidra/p6ix/<addr>.c`. Index
  `targets-named.tsv`: 127 classes, 3,406 functions. `targets2-named.tsv`:
  the profile's deploy and resource functions.
- **Literals, counts and branch directions:** confirmed in the annotated
  disassembly, `dump/asm/worm-canis.dll/<class>.asm`.

## Context and board

- `AppContext.ix` is `IsSetEnabled(RiseOfIx = 2)`.
- `Board.ix` replaces the four spaces the CHOAM overlay covers (their
  `RemovedFromSetList` holds `RiseOfIx`) with the four Ix spaces, in the
  app's typedef order.
- Catalog tables: `IX_*_ARCHETYPES`. The tiles are the app's own
  `TechTileArchetypes.RiseOfIx.*`, not the app-style Bloodlines ones.

## Decisions and the app classes that answer them

| Our decision | App class or profile method | Notes |
|---|---|---|
| `freighter_move` (Conflict-reward Freighter) | `FreighterAbility` (`FreighterCustomAbility`): `GetFreighterSelections(-1).Item1` at `FreighterValue` | Explicit: the app always moves; `decline_freighter` is never its answer. Level 2 before the climax draws the match RNG; here the seat's RNG. |
| Freighter rows of spaces, cards and Intrigue | `FreighterAgentAbility` / `FreighterRevealAbility`; Diversion's and Expedite's play answer | Intrigue rows replay the play's recorded answer (`_intent`). |
| `shipping_reward_icons` and Shipping rows in the turn and Reveal windows | `ShippingTrackAbility1/2/3` (space 1: `Item2` of `GetFreighterSelections(LastShippingRecallSpace)`, 100; space 2: `GainAnyInfluenceAbility`; space 3: 100) | `LastShippingRecallSpace` is the highest space still owed. Our engine splits space 2's recruit and Influence (OQ-148); both answer the one app ability. Explicit sources hold the prompt, so pending rows come first. |
| `dreadnought_control_choice` | `DreadnoughtControlAbility` | Detonation Devices' VP at 100 when held. Otherwise the shuffled spaces score: another seat's at its VP, the seat's own at 1, an open Imperial Basin at 3, other open spaces at 2. Strictly better wins. |
| Commission (Dreadnought space) | `DreadnoughtSpaceAbility`, automatic | The space's own Acquire Tech is `AcquireTechAbility`. |
| `deploy_dreadnoughts` / `deploy_troops` | `GetUnitsToDeploy` over troops and dreadnoughts (`units_to_deploy_split`) | Strongest first (`OrderByDescending(Strength)`, then `TakeWhile`). The Baron's Masterstroke swaps a chosen dreadnought for a troop; Diversion adds the next unit. The dreadnoughts deploy first and the troops are kept for the next decision. The app never withdraws. |
| Shipping recruits off a Combat space | `TroopTransportsAbility` when held | P4 ruling: Troop Transports allows the deployment (rise-of-ix.md 15). Without the tile the app has no key, so the deployment stays unused. |
| Tech acquisition | By the frame's discount: 0 `AcquireTechAbility` (Dreadnought space), 1 `AcquireTechAbilityDiscount1` (Tech Negotiation), 2 `AcquireTechAbilityShippingTrack2` | Negotiators are spent before spice: the variant with the most (rix-tech §7.1). |
| Tech Negotiation's "OR" | `TechNegotiationDeferredAbility`: the Negotiation area at 1.0 against the affordable tiles | A tile answer becomes `acquire_negotiation_tech`; the tile itself is picked in the acquisition window. |
| `flip_tech`, `trash_tech`, acquire effects | The tile classes (Flagship, Holoprojectors, Invasion Ships, Training Drones; Spy Satellites, Sonic Snoopers; `ShuttleFleetAcquiredAbility`, `MemocordersAcquiredAbility`) | The turn, Agent-turn and Reveal windows share the sources. |
| `intrigue_bottom_pick` (Sonic Snoopers) | `SonicSnoopersAbility` names the bad Intrigue cards at once | Our engine asks one card at a time: the next bad card still in hand, then finish. The draw comes after, so the hand only shrinks meanwhile. |
| Disposal Facility's Reveal trash | `DisposalFacilityAbility` (`GetCardToTrash`, minimum 1.0) | No card named leaves it unused. |
| Spaceport's Foldspace | The destination picker: option 0, top of deck, for every card except The Spice Must Flow (generic-abilities §4.2) | |
| Ix Imperium boxes | `_DISCARD_ABILITY` (Truthsayer), `_PAYMENT_ABILITY` (Sayyadina), `_TRASH_ABILITY` (Jamis) | |
| Intrigue slots | Strongarm's zone, Double Cross's victim (`OpponentLosesTroop`), Urgent Mission's Agent (`RecallYourAgent`) | Each comes from the play's recorded answer. Urgent Mission is an original card; Ix's extra Agents exposed its missing case. |

## Profile

- `IsSetEnabled(RiseOfIx)` blocks:
  - `GetGainInfluenceValue` (D): the Spacing Guild bonus, Grand Conspiracy,
    Memocorders, and Tessia on a Snooper track.
  - `DeployValue`: dreadnoughts at 1.5 each, and Negotiated Withdrawal
    with two or more garrisoned troops.
- `HasTech` terms (rix-tech §5): inert without the tile.
- `GetFreighterSelections`, `get_FreighterValue`, the Tech stack tops, the
  Negotiators and the supply dreadnoughts read the Ix state.
- `GarrisonUnits` and `ConflictUnits` count dreadnoughts.
- `GetBestOption` (0x4911370), as `original_intrigue.best_option`:
  - It takes the strict maximum from 0.0 over the hand's cards and each card's
    valid spaces.
  - The value is the card's Agent value plus the space abilities' values,
    both computed with the card.
  - Read by Glimpse the Path and Ixian Probe; Ilesa's One Step Ahead will
    read it too.

## Judgement calls (kept as the app has them unless noted)

- **Boundless Ambition** (promo): the Reveal reads the playmat's
  `BoundlessAmbitionCustomAbility`.
  - Value: the AcquireValue of the best Row card costing less than 6.
  - Answer: the strictly best card, option 0.
- **Shai-Hulud**: the card lists `ShaiHuludAcquireAbility` (an acquire-time
  trash) before its plain `AcquireAbility`. The Reveal window looks up the
  exact class first, so the purchase is valued by the plain one.
- **Spice Smugglers** (original, P4's OQ-148): the paid box's Spacing Guild
  Influence row comes before its Solari row, the app's order. The same fix
  is on `claude/spice-smugglers-app-ai` for the P4 merge.
- **Negotiated Withdrawal**: its Evaluate reads both units and tracks from the
  first target info, so it never retreats. Ported as compiled.
- **Units in the Conflict**: they have no entity kind. `DesertAmbushAbility`
  and `NegotiatedWithdrawalAbility` take them as `ConflictUnit` constructor
  data.
- **Diversion / Expedite**: the app draws `GetFreighterSelections` and
  `FreighterValue` separately. At a level-2 Freighter the RNG draw count
  differs from the app's.
- **Diversion's cost**: read as `max(units_deployed_turn,
  units_deployed_peak) >= 4`.
- **Machine Culture's Endgame cost**: read as phase ENDGAME or FINISHED.
- **Grand Conspiracy's `ValueInPileForOtherPlay`**: multiplies an empty
  summer, so it is always 0. Kept.
- **Second Wave**: options are one index per garrison unit (dreadnoughts
  first), and `max_select` is `NumberToSelect`.
- **"This turn's exhausted units"** (Baron, Diversion): read as
  `units_deployed_turn`. When the app readies them is UNTRACED.

## Independent review (2026-10-30)

A read-only review agent (the session's model) compared 16 of the
agent-ported classes with the decompiled C and the asm: 8 Imperium and 8
Intrigue. The classes themselves matched: value terms, literals, price
arguments, branches and response shapes.

It confirmed two problems, both fixed in `16d6acda`:
- **Missing targets.** `intrigue_request` gave Blackmail, Cull and
  Finesse's Plot no targets, so their evaluates were empty and the cards
  were never played. Their Influence slots now replay the play's answer.
- **NaN gates.** Three comparisons now take NaN to the early return, as
  `ucomisd; jb(e)` does.

Left open by the review:
- Some cards still have no window consumer: Spice Trader, Guild Chief
  Administrator, Imperial Bashar, Weirding Way, Negotiated Withdrawal,
  Embedded Agent, Quid Pro Quo, Grand Conspiracy and War Chest. Their engine
  entries have no play data yet (P4d). Their response shapes are checked
  when the engine offers their rows.
- The `Cost`s of Imperial Bashar and Negotiated Withdrawal are not ported as
  `meets_cost`.
- `GetBestInfluenceExchange`'s bool argument has no counterpart in
  `profile.best_influence_exchange`.

## What waits

- **The six Leaders (P4e)**: 20 classes, `round_start_set_aside` (Ilesa,
  with `best_option`), `optional_discard` (Tessia), and the setup of Tessia
  and Hundro.
- **Closing runs**: the original + Ix soak and the Hard vs heuristic
  measurement, booked on the CPU board once P4e lands.
