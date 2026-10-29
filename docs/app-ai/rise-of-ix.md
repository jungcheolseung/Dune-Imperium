# app_ai: Rise of Ix on the original board (port notes)

> The plan, slices and status are in `docs/app-ai-plan.md` §13. This file
> records how each Rise of Ix decision is answered and every judgement call,
> so later readers can tell the app's behaviour from our mapping of it.

Status (2026-10-30, branch `claude/base-ix-p6-ix`): every Rise of Ix decision
our engine offers in an original + Ix game (draft, promos) is answered by an
app class. The census has no random answer and no unported class: 20 games
per level, seeds 8100+. All six Ix Leaders are in (P4 `6c6b747e`).

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
| Ix Imperium boxes | `_DISCARD_ABILITY` (Truthsayer, Satellite Ban, Spice Trader), `_PAYMENT_ABILITY` (Sayyadina), `_TRASH_ABILITY` (Jamis), `_BOX_ABILITY` (Bounty Hunter: `BountyHunterAbility`, run at once) | |
| Imperial Bashar's "troop -OR- trash" box | `ImperialBasharAgentAbility` (Explicit): option 0 the plain `resolve_agent_card_effect`, option 1 its card's `trash_agent_card` row | The second info lists the trash rows' cards in our rows' order. An answer with no row (option 1 with no card, or the troop when none can join) uses the key on nothing, and the box lapses at the turn's end (OQ-095 (2)). Mapped before P4's `claude/p4d-imperium-b` reached P4, and checked on a trial merge. |
| Ixian Engineer's Acquire Tech icon (`acquire_agent_card_tech`) | `AcquireTechAgentAbility` (the Dreadnought space's `AcquireTechAbility`, Agent timing) over `GetAcquireTechTileTargets(M, P, 0, false)` | A tile answer takes the row. The Acquire Tech frame it opens asks the same class (discount 0). |
| Ixian Engineer's Reveal "3+ Tech tiles: trash this card -> 1 VP" | `IxianEngineerAbility` (Optional, E 100) | CHOAM Demands' `trash_reveal_card` shape. |
| Web of Power's three Influence-2 lines | `WebOfPowerEmperorAbility` (Solari), `WebOfPowerSpacingGuildAbility` (draw), `WebOfPowerFremenAbility` (water) | Wheels Within Wheels' shape, in `_ICON_ABILITY`. |
| Web of Power's Reveal Faction pick (`gain_chosen_influence`) | `WebOfPowerRevealAbility` (a `GainAnyInfluenceAbility`, Explicit) | The chosen track's `gain_reveal_influence` row. |
| Esmar Tuek's paid box (`pay_agent_card_spice`, then a Spacing Guild Influence and a card) | `EsmarTuekAbility` (Optional) | Spice Smugglers' shape: the Influence and the card follow the payment (the order of the app's three actions is UNTRACED; Spice Smugglers' is kept). |
| In The Shadows' box (`discard_agent_card`, then `choose_agent_card_influence`) | `InTheShadowsAgentAbility` (Optional): one answer `((card,), (track,))` over the hand and the Emperor, Spacing Guild and Fremen tracks | The track waits in `Memory.intents` for the Influence step. |
| Treachery's box and Reveal (`deploy_reveal_supply_troops`) | `PowerPlayAgentAbility`, with the Explicit `TreacheryTrashSelfAbility` folded into the one action (as Subversive Advisor's trash); `TreacheryRevealAbility`, a state-300 `RevealAbility` | The Reveal's two troops are an automatic gain (kind `deploy`). |
| Guild Accord | `GuildAccordUnloadAbility`, `GuildAccordAllianceAbility` | Nothing to choose. |
| Satellite Ban's Reveal "retreat up to two troops" | `SatelliteBanRevealAbility` | The effect is Scout's. Its table entry is the shared `OptionalRetreatAbility`, so each card answers with its own class. |
| Intrigue slots | Strongarm's zone, Double Cross's victim (`OpponentLosesTroop`), Urgent Mission's Agent (`RecallYourAgent`) | Each comes from the play's recorded answer. Urgent Mission is an original card; Ix's extra Agents exposed its missing case. |
| Advanced Weaponry's commission (`commission_intrigue_dreadnought`) | `AdvancedWeaponryPlotAbility` commissions as it runs | No prompt in the app: taken; declined only when no commission is offered. |
| Second Wave's `deploy_intrigue_troops` | `SecondWaveAbility`: `GetUnitsToDeploy` over the garrison units | The request lists one index per garrison unit, dreadnoughts first, `NumberToSelect = Min(count, 2)` (`<Targets>` @0x4bf7d40). The row has as many units, with as many `dreadnoughts`, as the answer chose. An empty answer deploys none: the swords alone. |
| Machine Culture's Plot and its Acquire Tech frame | `MachineCulturePlotAbility`: its targets are `GetAcquireTechTileTargets(M, P, 0, false)` (`<Targets>d__6` @0x4bf4970: no discount, no Solari); its answer names the tile | The app's `RunImmediateEffects` buys that target without asking again. Our engine opens an Acquire Tech frame (printer `intrigue\|machine_culture`) with no refusal while a tile is in reach. The Tech window replays the play's answer (`intrigue_tech_tile`) and never relies on a decline row. |
| War Chest, Diversion | `WarChestCombatAbility` / `WarChestEndgameAbility`; `DiversionAbility` (its Freighter slot as Expedite's) | War Chest's 2 Solari are the Combat line's cost; nothing to choose. |
| Double Cross's victim when its play named none | `DefaultRandomChoice` over the offered opponents | A forced prompt answered at 0 or less draws a random key, here the card's (seed 8112). The target prompt that follows is forced too. |
| Endgame plays of Plans Within Plans and Grand Conspiracy | Played without a prompt (`EndgamePhase`). The app's engine scores the count: `CountTotalPoints` gives 1 VP for three, 2 VP for four (@0x4ca8030, @0x4bec350) | Our engine offers each count as an exclusive -OR- option (OQ-058), both when four are met. The window plays the option with the most VP. Before 2026-10-30 it took the first (1 VP); this also changes original games. |

## Leaders

The twenty-one classes are in `abilities/ix_leaders.py` (Tessia's eight
and their abstract `CarefulObservationFactionAbility` included); Rhombur's
`IxianTechnologyAbility` is in `abilities/tech.py`.

| Leader | Decision | App class | Notes |
|---|---|---|---|
| Archduke Armand Ecaz | Conscript (Signet): `acquire_leader_imperium` / `acquire_leader_reserve` | `ConscriptAbility` (Optional): the Row, then the Reserve without Foldspace, cost 3 or less; answer `((card,), (destination,))` | Destination option 0 is the top of the deck while our engine offers `to_deck_top` (Spaceport), else the discard pile. |
| | Coordination (Reveal): `trash_leader_reveal_card` | `CoordinationAbility` (Optional; Cost: the Reveal turn and two Agents on Landsraad, City or Spice Trade spaces) | `GetCardToTrash` over the cards in play; "trash nothing" (`((),)`) is no candidate. |
| Ilesa Ecaz | One Step Ahead (`round_start_set_aside`) | `OneStepAheadRoundAbility`: of the three best Agent-box cards, the first with one Agent icon; else `GetBestOption`'s card is removed and the first left is set aside | A forced `KeepCard` prompt: an empty answer is `DefaultRandomChoice`. Its Turn and Send halves have no AI hook. |
| | Guild Contacts (Signet): `acquire_leader_reserve` (Foldspace) | `GuildContactsAbility` (Optional): 100 with option 0 before the Late arc and the climax | `<Targets>d__8` lists "deck" only when it is allowed, then "discard" (asm). |
| Prince Rhombur Vernius | Ixian Technology (Signet): `acquire_leader_tech` / `place_leader_negotiator` | `IxianTechnologyAbility`: the Negotiation area at 1.0 against the tiles in reach (no discount) | The Acquire Tech frame asks `AcquireTechAbility`, the same argmax. |
| | Heavy Lasgun Cannons | Sets his dreadnoughts' `Strength` to 4 | `GetUnitsToDeploy` sums 4 per dreadnought for him (`profile/combat.py`). |
| "Princess" Yuna Moritani | Final Delivery (Signet): `choose_leader_signet_influence` | `FinalDeliveryAbility` (Optional): each track at its `GetGainInfluenceValue` | With every Faction at the top our engine offers the payment alone; the app has no track to answer, so the key lapses. |
| Viscount Hundro Moritani | Couriers (Signet): `advance_leader_freighter` / `recall_leader_freighter` | `CouriersAbility` (Optional): `GetFreighterSelections(-1).Item1` at `FreighterValue` | |
| | Intelligence (setup `intrigue_peek`, source `setup:intelligence:<seat>`) | `IntelligenceAbility::EvaluateIntrigue`: the higher `Rating` | Imperium Ceremony's peek keeps `ImperiumCeremonyAbility`. |
| Tessia Vernius | Careful Observation reward (1): `discard_snooper_card` in her turn (no refusal; lapses), or the `OPTIONAL_DISCARD` window outside it (`decline_snooper_discard`) | The reached track's `CarefulObservation<Faction>Ability`: `GetDiscardOrder`'s first card at 1.0, `((),)` for none | In her turn "discard nothing" is no candidate; in the window it is the refusal. Rewards (2)-(4) are paid by the engine. |
| | Duplicity (Signet): `lose_leader_influence`, then `choose_leader_signet_influence` | `DuplicityAbility` (Optional): one prompt over the lose tracks and the Snooper tracks, `GetBestInfluenceExchange` -> `((lose,), (gain,))` | The loss takes the first track; the second waits in `Memory.intents` for the gain step (the app answers both before the loss). |

Judgement (Tessia): the app numbers her Snooper rewards by the order its
abilities run, ours by the order the tokens are reached; a waiting reward
(1) is the app's first run, so `snooper_factions_used` is empty while one
waits. One action reaching two tokens pays (2) before asking (1) in ours.

Quid Pro Quo's per-Faction Influence (`resolve_effect_influence`, OQ-153)
is taken first, in `GetAgentSpaceFactions`' board order: the app's
`QuidProQuoAbility` gains them as it runs, without asking.

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
- Some cards still have no window consumer, because their engine entries
  have no play data yet (P4d, as of P4 `3b8cd83c`):
  - Imperium: Guild Chief Administrator, Weirding Way, Negotiated
    Withdrawal, Embedded Agent. (Satellite Ban, Spice Trader, Imperial
    Bashar, Bounty Hunter, Web of Power, Ixian Engineer, Esmar Tuek, Guild
    Accord, In The Shadows and Treachery are on P4's `claude/p4d-imperium-b`;
    their rows are mapped and checked on a trial merge. Freighter Fleet,
    Ix-Guild Compact and Boundless Ambition wait for P4's Unload hold.)
  - Intrigue: Strategic Push (P4's `claude/p4d-strategic-push`).
  Their response shapes are checked when the engine offers their rows.
  Quid Pro Quo (P4d-6b), Grand Conspiracy, War Chest, Machine Culture and
  Diversion (P4d) are now played and answered.
- Negotiated Withdrawal's `Cost` is not ported as `meets_cost`. Imperial
  Bashar's is: `HasTrashableCard` or a troop in the supply (@0x4dc3c70).
- `GetBestInfluenceExchange`'s bool argument has no counterpart in
  `profile.best_influence_exchange`.

## What waits

- **Closing runs**: the original + Ix soak and the Hard vs heuristic
  measurement, booked on the CPU board once Tessia and the remaining cards
  are in.
