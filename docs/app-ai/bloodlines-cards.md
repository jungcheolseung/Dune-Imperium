# Bloodlines cards for app_ai: app-style archetypes and abilities

> Main-session decisions in `docs/app-ai-plan.md` §11.7 (2026-10-05) override this file where they differ.

Status: specification for stage 3 of `docs/app-ai-plan.md` §11.6. Nothing here is implemented yet. Written 2026-10-05
on branch `app-ai-expansions`. Independently verified the same day (coverage, printed data, fits re-run on
`data/archetypes.py`, names grepped): D28 and D32 were changed by the verifier, and D27a and D31–D34 were added.

Scope: the 27 Bloodlines Imperium identities (33 copies, the promo Ruthless Leadership included), the 18 Bloodlines
Intrigue cards, the 12 Twisted Intrigue cards, the 2 Bloodlines Conflict cards and the 8 CHOAM contract tokens. Commanders,
Skills, Tech tiles, Navigation, Leaders and the Tuek's Sietch space belong to `bloodlines-systems.md`. Where an item
here depends on them, this file names the interface and lists it as OPEN (§11).

Binding rules: plan §3, §4, §11.3 (values), §11.4 (decisions), §11.5 (decisions already taken). This file applies them
item by item.

## 0. Conventions

- `W.X` = the app class `worm.canis.abilities.X` (every one is either ported, see `abilities/*.py` `@port`, or being ported
  by the parallel RoI/Immortality stage; the spec section is cited). `AS.X` = a new class
  `worm.canis.abilities.AppStyle.Bloodlines.X` defined in this file. Archetype short names are
  `<Kind>Archetypes.AppStyle.<PascalName>`. No PascalName equals the last part of an app short name: the names were checked
  against `data/archetypes.py`; the contract tokens get a `Bloodlines` prefix because `DeliverSupplies`, `HighCouncil`,
  `Secrets` and `SpiceRefinery` are app space names.
- `P` = the deciding seat, `AI` = its profile. Profile methods are written in the snake_case of `profile/core.py`:
  `card_draw_value()`, `buy_gains(n)`, `possible_persuasion_gain()`, `possible_persuasion()`,
  `card_draw_value_with_buy_gains()`, `intrigue_value()`, `spy_value()`, `recall_spy_value()`, `recall_spy(spies)`,
  `best_post(posts)`, `gain_influence_value(f, n, -1, False)`, `best_influence_exchange(...)`,
  `has_or_would_gain_alliance(f, n)`, `solari_value(n)`, `spice_value(n)`, `water_value(n)`, `persuasion_value(n)`,
  `strength_value(n)`, `troop_value(n)`, `victory_point_value(n)`, `trash_card_value()`, `trash_mod()`, `discard_value()`,
  `card_to_trash(targets, min)`, `discard_order(cards, sg_bonus)`, `acquire_value(card)`, `gain_contract_value()`,
  `best_contract(targets, forced)`, `deploy_value(owner)`, `units_to_deploy(...)`, `troops_to_retreat(max)`,
  `should_play_retreat_intrigue(name, a, b, n)`, `should_play_troop_intrigue(name, a, b, n)`, `estimated_conflict_rank(b)`,
  `current_conflict_interest()`, `conflict_posture_bounds()`, `is_climax()`, `is_final_round()`, `trash_intrigue_value()`.
  `gain_influence_value(None, n)` means the app's `Factions.None` (best faction): `NO_FACTION` in
  `profile/influence.py:58`, as `GainAnyInfluenceAbility` V calls it (imperium-b.md, Public Spectacle).
  Tech methods: `buy_tech_value(discount, allow_solari)`, `tech_tile_to_acquire(discount, allow_solari)` (`profile/tech.py`,
  app `BuyTechValue`, `TechTileToAcquire`, rix-tech.md §4). App helpers without a profile method keep their app name
  (`GetValueForRevealAbilities`, `ContractAbility.GetResourceValue`, `GainContractAbility.ContractValueForPlayer`,
  `AbilityForPlacement`, `GetRevealPreviewValue`).
- Constants: exact getter names of `data/constants.py`, written `K.Name`.
- `Upd(v, resp)` = `UpdateSelectionTargets`/`UpdateSelectionResponses` (first call sticks, later ones need a strictly
  greater value; generic-abilities.md §0.2). `ppg` = `possible_persuasion_gain()`.
- Icons: City = `Circle`, Spice Trade = `Triangle`, Landsraad = `Pentagon`, plus `Spy` and the faction names `Emperor`,
  `SpacingGuild`, `BeneGesserit`, `Fremen`. Order inside `IconList` follows the app: factions, Pentagon, Circle, Triangle,
  Spy.
- Every synthetic archetype has `ArchID` = its short name, `EntityType` (`Imperium`, `Intrigue`, `Conflict`,
  `ConflictReward`, `Contract`), `CardCount` = printed copies and `SetList` (`Bloodlines`, plus `CHOAMModule` or `TechModule`
  for module cards). `SetList` has one AI reader: `GetUprisingConflicts` keeps only conflicts whose `SetList` contains
  `Uprising` (`profile/combat.py` `uprising_conflicts`), so the two Bloodlines conflicts stay out of that pool (§6). It
  is otherwise informational. Attributes not listed are absent, as in the app data.
- `OTHER(f)` = `(P.Hand ++ P.AllCardsInPlay).Any(e != Owner and e ∋ f)`; `INPLAY(f)` = `P.AllCardsInPlay.Any(e != Owner
  and e ∋ f)` (imperium-b.md §0.5). "BGP" and "FDP" are the BG-in-play and Fremen-in-deck `ValueInPileForOtherPlay`
  patterns of imperium-b.md §0.5.

## 1. Value rules (fits on the app's data)

All fits read `data/archetypes.py` (app 4.1.2.1808). Scripts: session scratchpad `blcards/` (`median.py`, `dvfit.py`,
`agentbox.py`, `timing.py`).

### 1.1 Imperium `AcquireValue` (plan 11.3, re-checked)

`AcquireValue = PersuasionCost + offset(cost)`, offset = median of `AcquireValue − PersuasionCost` over the 151 app
`ImperiumType = Main` cards (BaseSet, Uprising with CHOAM, Rise of Ix, Immortality):

| cost | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| cards | 15 | 23 | 35 | 27 | 26 | 14 | 5 | 6 |
| median offset (re-check) | 0.0 | −0.1 | 0.0 | −0.2 | −0.2 | −0.2 | −0.2 | 0.0 |
| plan 11.3 | 0.0 | −0.1 | 0.0 | −0.2 | −0.2 | −0.2 | −0.2 | 0.0 |

The re-check gives the plan's table exactly. Fit: mean absolute error 0.33. 119/151 cards within ±0.3, and 31/151 exact.

### 1.2 Imperium `EarlyMod`, `LateMod`, `TrashValue`

- `LateMod` = the modal value for the cost: 0.8 for cost 1 (6 of 15 cards; 1.0 has 5), absent (1.0) for every other
  cost. This predicts 112/151 cards exactly. Cards affected: Bombast and Sandwalk.
- `EarlyMod`: absent. The mode is 1.0 at every cost, and 130/151 cards match.
- `TrashValue`: absent. No Uprising Main card has one. The nearest card with a trash trigger, Sardaukar Soldier, has none.

### 1.3 Imperium `DeferValue` (agent-box kinds)

What it does in the app: `DeferredAbility::Evaluate` returns `Owner.DeferValue ?? (Explicit ? 1 : 0)`, which is the
ordering value of the card's draws, of space-type influence and of riders without their own E. In addition,
`DeferredThresholdReached` sums the DeferValue of this turn's cards, the held intrigues and the spaces, and at ≥ 3 the
draws, space influence and contract gains wait in the post-action prompt (engine-order.md §4.1).

How the fit was made: each app Main Imperium card and each Tleilaxu card (169) was classified by the effects in its
Agent box. The Agent-timed abilities come from the `.ctor` timing store (`timing.py` over `dump/asm`), the agent texts
from the app's `loc/en_US.json` and the spec texts. The kinds are D (draw cards; D2 = two draw effects), Dc (discard a
card as a cost), T (trash a card), I (gain an Intrigue), F (gain Influence), S (place a Spy), R (resources or troops, also
conditional), M ("two Influence instead of one"), C (contract), A (each opponent loses or discards), X (other: acquire a
card, recall an Agent, tech, VP exchange, deploy, research, return to hand, space block).

| Agent-box kinds | n | app DeferValue (count) | rule | exact |
|---|---:|---|---:|---:|
| none / R / S / M / C / A / X / R+X | 27 / 28 / 3 / 5 / 1 / 5 / 19 / 2 | 0:26 1:1 / 0:28 / 0:3 / 0:4 3:1 / 0:1 / 0:2 1:2 2:1 / 0:7 1:5 2:7 / 0:1 1:1 | 0 | 26 / 28 / 3 / 4 / 1 / 2 / 7 / 1 |
| D, D+R, D+S, D+X | 11 / 5 / 1 / 3 | 1:9 2:2 / 1:5 / 1:1 / 1:2 2:1 | 1 | 9 / 5 / 1 / 2 |
| D2, D2+Dc | 6 / 2 | 2:6 / 2:2 | 2 | 6 / 2 |
| T, R+T, D+T | 8 / 5 / 4 | 2:7 0:1 / 2:5 / 2:3 3:1 | 2 | 7 / 5 / 3 |
| I, D+I, F+I | 7 / 1 / 1 | 2:7 / 2:1 / 1:1 | 2 | 7 / 1 / 0 |
| F, F+R, D+F | 12 / 2 / 1 | 2:7 0:2 1:2 3:1 / 0:1 2:1 / 1:1 | 2 | 7 / 1 / 0 |
| any + Dc (Dc+R, Dc+T, Dc+F, Dc+X, D+Dc, D+Dc+I, C+Dc) | 10 | 2:10 | 2 | 10 |

**Rule:** `DeferValue = min(2, max over kinds of w)`, where `w(D) = number of draw effects`,
`w(Dc) = w(T) = w(I) = w(F) = 2` and every other kind has w 0. The attribute is absent when the result is 0. The rule
predicts **138/169 cards exactly (82 %)**, and **49/54 of the cards dealt in an Uprising game**. The pattern suggested in
the task (draw → 1, Intrigue/Spy/influence → 2, immediate → 0) predicts 105/169 (62 %) and 35/54. It is refuted for
Spy: the 3 pure Spy boxes (BG Operative, Double Agent, Reliable Informant) have no DeferValue, and In High Places (draw +
Spy) has 1. The discard cost (Dc → 2, 10/10) is the strongest single signal. The five 3s (Shifting Allegiances,
Treacherous Maneuver, Tread in Darkness, and the starters Demand Attention and Signet Ring) are hand-made and are not
reproduced. The misses are Guild Ambassador, Other Memory, Rev. Mother Mohiam, Shifting Allegiances, Spice Smugglers,
Test of Humanity, Appropriate, Embedded Agent, Esmar Tuek (RoI), Ixian Engineer, Landing Rights, Bene Tleilax
Researcher, Clandestine Meeting, Dissecting Kit, High Priority Travel, Lisan al Gaib, Tleilaxu Master, Tleilaxu
Surgeon, Covert Operation, Leadership, Price Is No Object, Treacherous Maneuver, Tread in Darkness, Contaminator, Corrino
Genes, Ghola, Guild Impersonator, Industrial Espionage, Scientific Breakthrough, Slig Farmer and Subject X-137. 18 of the
31 misses involve an X, A or M kind (the X row alone splits 7/5/7 over the values 0/1/2), where the app shows no rule.
The other 13 are single-card exceptions.

### 1.4 Imperium `Tags`: meanings and readers

| Tag | App meaning (evidence) | Readers (what it changes) |
|---|---|---|
| `WantSpy` | Spy agent icon (9/9 Uprising cards with the icon) or a spy-dependent effect (BG Operative, In High Places, Rebel Supplier, Spy Network) | `SpyValue` × (1 + 0.25 per tagged card, Imperium cards and intrigue hand); `GetSynergyMod` "WantSpy Spy count incentive"; base VIP "Spy Card Incentive" when an owned card has `Spy`; ×`K.WantSpyImperiumMod` in `AcquireValue` for Feyd and Margot |
| `Spy` | the card places a Spy (agent, reveal or acquire; 11 of the 12 such cards, the exception being Spy Network) | base VIP (owner tag) |
| `WantRecall` | "if you recalled a Spy this turn" (4/4) | `RecallSpyValue` + `K.SpyRecallMod` per such card in play (Agent turn) |
| `RecallSpy` | recalls a Spy as a cost (In High Places, Spy Network) | none |
| `FremenBond` | has a Fremen Bond (6/6 bond classes) | base VIP: Fremen owner → +`K.SynergyBondWithFremenInDeck` |
| `WantE`, `WantSG`, `WantBG`, `WantF` | needs another card of that faction: Emperor card (Calculus, Coordination, Treacherous Maneuver), discarded Guild card (Guild Envoy, Guild Spy, Space-Time Folding), BG card in play (4/4) | base VIP: owner of that faction → +`K.SynergyWithFactionInDeck` |
| `<Faction>Influence` | effect gated by that faction's influence ≥ 2 (Wheels, Hidden Missive, Maker Keeper) | `GetFriendshipMod` TwoInfluenceCheck |
| `<Faction>Alliance` | effect gated by that faction's Alliance | `GetFriendshipMod` AllianceCheck |
| `DiscardEnabler` | makes you discard, unless the discard has a Guild bonus (those cards carry `WantSG` instead): Captured Mentat, Corrinth City, Delivery Agreement, LLtF | VIP ×`K.DiscardEnablerMod` with an `IncentiveDiscard` candidate |
| `IncentiveDiscard` | benefits from being discarded (Spacing Guild's Favor) | `GetDiscardOrder` puts it first; VIP ×`K.DiscardIncentiveMod` |
| `WantContract2/4/X` | contract-count conditions (Cargo Runner 2/4, Delivery Agreement 4, Priority Contracts 4, Interstellar Trade X) | `WantContractCount` (→ `GainContractValue`); `GetSynergyMod` contract incentives |
| `Contract` | the card gives a contract from its agent/reveal box (Delivery Agreement, Priority Contracts; not the acquire effect of Interstellar Trade) | none |
| `WantHooks` | sandworm-dependent (Desert Power, Leadership) | `GetSynergyMod` hooks incentives |
| `ConditionalStrength`, `NamedCharacter`, `Combat`, `RecallAgent`, `WantHC`, `Sandworm`, `MakerHooks` | descriptive | none |

Bloodlines Imperium tags are in the §3.0 table, each set by the meaning above.

### 1.5 Intrigue `DeferValue`

What it does in the app: held intrigues add their DeferValue to `DeferredThresholdReached` (intrigues.md §2.4). There
is no other reader. The fit was made on the 39 Uprising intrigue archetypes (CHOAM included), whose texts are in
intrigues.md §6–§8.

**Rule:** `DeferValue = max over kinds of w`, where `w(draw) = number of draws` (Intelligence Report 2, Depart 1),
`w(trash a card) = 2` (Cunning, Devour), `w(gain Intrigue) = 2` (Mercenaries), `w(gain Influence) = 1` (Buy Access,
Imperium Politics, Sietch Ritual), `w(acquire a card) = 1` (Inspire Awe, Impress) and every other kind has w 0. The rule
predicts **37/39 exactly**. The misses are Change Allegiances (influence swap, 2) and Opportunism (VP, 1). A Bloodlines
card with the same effect as a miss takes the miss's value (plan 11.3: nearest app card). Tenuous Bond's swap takes
Change Allegiances' 2. Acquire Tech is not covered by the rule (no Uprising card has it) and takes Machine Culture
(RoI, the app's acquire-tech intrigue): 2.

### 1.6 Intrigue `Strength` and `CombatValue`

What they do in the app: `StrengthIntrigueAbility.StrengthValue = MeetsCost ? Strength : 0` and `CombatValue` is the
cost of spending the card. A card is worth `10 − CV` when it is a member of the first improving combination, and the
cheapest card is played first (intrigues.md §5). The fit was made on the 12 Uprising archetypes that can be played in
Combat.

- `Strength` = the largest printed sword total (Weirding Combat 5 = 3 + 2, Devour 4, Find Weakness 5): 10/10 of the
  cards with swords.
- `CombatValue`: no swords → absent (Go to Ground, Reach Agreement). A dual Plot/Combat card → absent (Contingency Plan,
  Backed by CHOAM). Otherwise it is the swords gained without paying anything (Impress 2, Devour 2, Find Weakness 2,
  Weirding Combat 3, Tactical Option 2). When every sword is behind a cost, it is the costed swords (Spice Is Power 6,
  Spring the Trap 7). The attribute is exact for **10/12** cards. The misses are Tactical Option (attribute 1, but the
  override returns 2) and Questionable Methods (absent, with an override). Counting the effective values the app uses,
  the fit is 11/12, the exception being Questionable Methods at 5 when the AI has influence.

### 1.7 Intrigue `Rating`

No code in any assembly reads `Rating` (intrigues.md §3). It is set for completeness to the Uprising mode for the card's
type: Plot 2 (11 of 21), Combat 2 (6 of 10), Plot+Endgame 3 (3 of 3). Plot+Combat is a 3/4 tie in Uprising (Backed by
CHOAM 3, Contingency Plan 4) and takes the all-sets mode, 3 (4 of 5). Combat+Endgame has no Uprising card and takes the
all-sets mode, 2. No Bloodlines card is Endgame-only, so that type (an Uprising 2/3/4 tie) is not needed. Fit: 21/36 on
the Uprising cards of the types used here (22/39 if Endgame-only is set to 3).

### 1.8 Intrigue `Tags`

The only live readers for an intrigue are `WantSpy` (`SpyValue`, which counts the intrigue hand) and `WantContract2/4/X`
(`WantContractCount`). The other tags are descriptive and follow the Uprising usage: `Spy` (places a spy: Distraction,
Go to Ground, Special Mission), `RecallSpy` (recall option), `WantHooks` (sandworm condition: Devour), `Contract`
(Leverage, Reach Agreement), `<Faction>Influence` (influence-gated bonus: Weirding Combat), `DiscardEnabler` (Sietch
Ritual), `ConditionalEndgameVP` (endgame VP), `BuyTech` (Machine Culture, the RoI acquire-tech intrigue).

### 1.9 Intrigue `IsBadIntrigue` (junk test)

Readers: `TrashIntrigueValue()` (0 while any held intrigue is junk), Branching Path and Junction HQ trash picks, Imperial
Privilege, and the new Bloodlines trash/give pickers (the `JunkIntriguePick` helper, §2.10). **Rule:** each new intrigue copies
the predicate of the app card with the same kind of effect (intrigues.md §11; rule 11.4 allows the nearest such card,
those choices are §9 D31 and D32). When there is none, the card is junk iff it cannot do anything now, as Sietch Ritual
is. A dual card is junk if either half is (`WormIntriguePlayable::IsBadIntrigue` = OR).
The per-card predicates are in the §4 and §5 tables.

### 1.10 Contract attributes

- `DeferValue` = the number of cards the reward draws. The two app contracts that draw two (`ContractBase_6`, `_12`)
  have 2, and the other 16 Uprising contracts have none: **18/18**. A contract adds to the threshold only when it is face
  up and on a space visited this turn.
- `ContractType`: Space / Harvest / Immediate as printed. Earn Any Alliance gets a new value `Alliance` (§7).
- `Tags`: `Spy` for a Spy reward (`ContractBase_4`, `_9`: 2/2), `RecallAgent` for an Agent recall (`_13`: 1/1).

### 1.11 Conflict attributes

They are copied from the card (`ConflictLevel`, `BattleIcon`). `Tags` = `BattleIcon` (every Uprising conflict has it)
plus `Spy` when a reward places a Spy (Seize Spice Refinery, Test of Loyalty). Reward archetypes use the app reward
attributes (`Solari`, `Spice`, `Water`, `IntrigueCard`, `Troops`, `CustomAbilityIDs`).

## 2. Shared app-style machinery

These are new classes and helpers used by several items. Each lists its app precedent.

### 2.1 `AS.CommandRevealAbility` (abstract) — Command (6+)

Precedents: `RevealAbility` riders (generic-abilities.md §3.1) and `get_PossiblePersuasion` (profile-economy.md §5.1),
which is the app's own forecast of the Reveal's Persuasion.

```
class AS.CommandRevealAbility : W.ActivatedAbilities.DeferredAbility
  .ctor: AbilityTiming = Reveal(2); HideInvalidDeferred = true
  Cost = engine Command flag      # our frame offers the effect only once the Reveal generated ≥ 6 Persuasion (OQ-033, OQ-043)
  CommandReached(P):
      if P.IsInPlayerTurn(Reveal): return Cost(P)
      return AI.possible_persuasion() >= 6          # pool + HC 2 + Assembly Hall + Σ hand reveal preview (this card included)
  ValueForPlayer(P, with) = CommandReached(P) ? Reward(P) : empty     # abstract Reward
```
Class structure (the app classes are single-inheritance): only the three automatic leaves derive from
`AS.CommandRevealAbility`: `AS.BombastCommandAbility`, `AS.IBelieveCommandAbility`, `AS.SouthernFaithCommandAbility`
(SelectionMode Explicit, `AlwaysRunImmediately` true, E = 100, Rebel Supplier shape; `Reward` given per card).
`CommandReached(P)` is also a shared static helper. The other Command abilities derive from the matching app base class
and call `CommandReached` in their V: `AS.RuthlessLeadershipCommandAbility` (`AS.RevealCombatIconAbility`, §2.2),
`AS.IntelligenceTrainingCommandAbility` (`PlaceSpyRevealAbility`), `AS.PointingTheWayCommandAbility`
(`GainAnyInfluenceRevealAbility`), `AS.ShroudedCounselCommandAbility` (`TrashAbility`) and
`AS.EngineeredMiracleCommandAbility` (§3.11). Ordering: Command choices are answered before buying, in active-card order
(plan 11.5). A self-trash attached to a Command effect is not priced, as in the app (Dangerous Rhetoric:
imperium-a.md §2.10; Subversive Advisor, Priority Contracts, Treacherous Maneuver: imperium-b.md §3 "Not priced").

### 2.2 `AS.RevealCombatIconAbility` (abstract) — the Combat icon in a Reveal turn

Precedents: `DeployUnitsAbility` (generic-abilities.md §11) with a card owner (`SardaukarCoordinationAgentAbility`,
imperium-b.md), and `ShadoutMapesAbility` (immortality.md §5.15), the app's own deploy in a Reveal turn (its E is a
100 sentinel and its V the constant `K.ShadoutMapesRevealValue`; only the existence of a Reveal-turn deploy is copied,
the values come from `DeployUnitsAbility`).

```
class AS.RevealCombatIconAbility : W.ActivatedAbilities.DeployUnitsAbility
  .ctor: AbilityTiming = Reveal(2)                  # replaces DeployUnits' Agent timing
  Gate(P) abstract
  ValueForPlayer(P, with) = Gate(P) ? AI.deploy_value(Owner) : empty   # Owner is a card: DeployValue's space terms are skipped
  Evaluate = DeployUnitsAbility.Evaluate            # units = AI.units_to_deploy(garrison, max); Upd(0.5, units)
```
It answers our `deploy_troops(count)`/`deploy_commanders(count)` in the Reveal window: the unit list from
`units_to_deploy` is split by kind, and Commanders are ordered as `bloodlines-systems.md` specifies (OPEN-1).
Leaves: `AS.RuthlessLeadershipCommandAbility` (Gate = `CommandReached`), `AS.HolyWarBondAbility` (Gate = `OTHER(Fremen)`)
and `AS.DisruptionTacticsRevealAbility` (§3.8). In an Agent turn, a card's Combat icon (Elite Forces, Adaptive Tactics) is
valued `deploy_value(Owner)` and answered by the existing Agent-turn deploy handler.

### 2.3 Fremen Reveal bonds

Precedent: `SouthernEldersBondAbility` and `NorthernWatermasterBondAbility` (imperium-b.md).
`AS.<Card>BondAbility : W.TriggeredAbilities.BondAbility` with `BondFaction` Fremen, timing Reveal and NoCost. `V(P, with)
= OTHER(Fremen) ? Reward : empty`. P = the inherited FDP. The rewards are Sandwalk `persuasion_value(1)` and Fremen War Name
`strength_value(2)`. Holy War uses §2.2 (its bond class is a `DeployUnitsAbility`, so it overrides
`ValueInPileForOtherPlay` with FDP itself, §3.13). A bond that adds Persuasion also overrides the card's
`GetRevealPreviewValue` to add it while `OTHER(Fremen)` holds. Precedent: `SouthernEldersRevealAbility` overrides only
`GetRevealPreviewValue` (imperium-b.md); that its body adds the bond's Persuasion is inferred, since the body was not
read (profile-economy.md §5.1). See OPEN-6.

### 2.4 `AS.DiscardForRewardAgentAbility` (abstract) — "may discard a card → reward"

Precedent: `SpacetimeFoldingAbility` (imperium-b.md), with the Guild bonus of `GuildSpyAgentAbility` (imperium-a.md §2.19).
```
class AS.DiscardForRewardAgentAbility : W.ActivatedAbilities.DeferredAbility
  .ctor: Agent(1); WillClearUndo; SelectionMode Optional(0); Cost = HasImperiumCardInHand.Any
  Evaluate: s = AI.discard_value() + Reward(P)
            card = AI.discard_order(targets, SgBonus)[0] or return 0
            if SgBonus and card ∋ SpacingGuild: s += SgReward(P)
            Upd(s, [card])                                   # Optional: used iff > 0
  ValueForPlayer(P, with): if P.HandCount < 2: empty
            s = AI.discard_value() + Reward(P)
            if SgBonus and with.Any(): c = AI.discard_order(hand − Owner, True)[0]; if c ∋ SpacingGuild: s += SgReward(P)
            return s
```
With `SgBonus = False` the discard pick is `discard_order(targets, False)`, as in Captured Mentat's agent E
(imperium-a.md §2.5), the app's discard-for-reward card without a Guild bonus. It answers our `discard_agent_card(card)`
with E's card, or `decline_agent_card_discard` when E ≤ 0.

### 2.5 `GainedSpice(P, with, n)` — "if you gained n or more spice this turn"

Precedent: `Harvest3ContractAbility::ValueForPlayer` (board.md §3.5), which tests the candidate space's
`Spice + BonusSpice`.
`GainedSpice = P.HasGainedSpiceThisTurn.AtLeast(n) or (S = CollectFirst<WormSpace>(with); S and S.Spice + S.BonusSpice >= n)`.
The engine's Cost is the predicate itself. The effect waits until it is true or the turn ends (OQ-057 (1)).

### 2.6 Conditional Reveal gains

Precedent: `BeneGesseritOperativeRevealAbility` + `BeneGesseritOperativeTriggeredAbility` (imperium-a.md §2.2): a
`RevealAbility` subclass that overrides `GetRevealPreviewValue` (listed in profile-economy.md §5.1; that it adds the
Persuasion while the condition holds now is inferred, the body was not read, OPEN-6), plus a `TriggeredAbility`
(timing Reveal, no E) with `V = cond(P) ? reward : empty` (verified).

### 2.7 `UnlockValue(P, grant)` — Plots that grant Agent icons or waive requirements

Precedents: Contingency Plan and Backed by CHOAM (intrigues.md §7.1, §7.5). A T0 Plot that makes a better placement
possible is worth 100, and `DetermineTurn` then runs again.
```
UnlockValue(P, grant):        # grant = extra Agent icons (all hand cards) or "ignore Influence requirements"
    best_now = max AgentAbility total over the turn window's legal (card, space) pairs (0 if none)
    best_new = max over hand cards c and board spaces S that become legal only under grant
               (S free or infiltrable per our legality, every SpaceAbility.CanBeRun) of
               Σ S.Abilities.ValueForPlayer(P, [c]) + c.AgentAbility.ValueForPlayer(P, [S])   # AgentAbility::Evaluate
    return best_new - best_now
Plot E: if P.IsInPlayerTurn(0) and UnlockValue(P, grant) > 0: Upd(100, [grant option])
```

### 2.8 `LoseUnitPick` — paying units and the victim's loss

Precedents: `TleilaxuSurgeonRevealAbility` and `PiterGeniusAdvisorAbility` (immortality.md §5.20, §6.16). The AI pays from
the **garrison** when `AI.estimated_conflict_rank(0)` has a value (it expects a reward place), and otherwise from the
**Conflict**. Desert Scouts takes "the first troop", so troops go before Commanders (plan 11.5). This answers
`lose_intrigue_troop(zone, commanders)` (Twisted costs, own seat) and `opponent_unit_loss` (victim, plan 11.5).
`resolve_unit_loss_without_unit` is the forced single answer.

### 2.9 `SpyMovePick` — the victim's forced Spy move (`opponent_spy_move`)

Precedent: `PlaceSpyEvaluator` / `GetBestPost` (profile-influence-uprising.md §2). `move_spy(post)` = `AI.best_post(allowed
posts)` (`PostValue` never reads occupancy). `lose_moved_spy` is the forced single answer when no post is allowed (OQ-065).

### 2.10 `JunkIntriguePick` (helper) — which Intrigue to trash or give

Precedent: `BranchingPathAbility::Evaluate` (imperium-a.md §2.3). Shuffle the candidates and score each `IsBadIntrigue ?
5.0 : 1.0`; the first strict best wins. The price of losing a card is `AI.trash_intrigue_value()` (0 while a junk intrigue
is held, else `K.TrashIntrigueValue` = −1.25), as in Branching Path's V. It answers `trash_intrigue_for_contract`,
`trash_intrigue_hand_card` (Unnatural) and `give_intrigue_card` (Insidious; the bonus spice for a non-Twisted card is
priced in the Insidious E, §5).

### 2.11 Acquire-effect bonuses (plan 11.5)

Precedent: `ChaumurkyAbility.SpecificAcquireValue` = `IntrigueValue` per Intrigue (rix-tech.md §8.2). The ability sits on
the card, has no E and is never offered.
- `AS.AcquirePlaceSpyBonusAbility`: `SpecificAcquireValue = AI.spy_value().Sum`.
- `AS.AcquireContractBonusAbility`: `SpecificAcquireValue = GainContractAbility.ContractValueForPlayer(P).Sum`, i.e.
  `GainContractValue` when the market has options, else `solari_value(2)`.

Valued acquire effects stay in `AcquireEffectList` (`RankE`, `Water`) and need no bonus.

### 2.12 `DrawPlotGate(P)` — when a draw Plot is played

Precedent: `CunningAbility` (intrigues.md §7.8), without its spice clause:
`P.IntrigueHandCount > 3 or AI.is_final_round() or (P.IsInPlayerTurn(0) and P.RemainingAgents.Any()) or
(P.IsInPlayerTurn(2) and AI.buy_gains(ppg) >= 1.0)`. The value of a draw is `AI.card_draw_value() + AI.buy_gains(ppg)`.

### 2.13 `RankWith(P, strengths)` — a new helper

This is the app's `GetConflictRank` (profile-combat.md: rank 1 + the sizes of the groups above, +1 if tied, > 3 → place 4)
evaluated on a modified strength list. It is new because `current_conflict_rank(bonus)` can only change P's own strength.
Used by Disruption Tactics (§3.8).

## 3. Imperium cards (27 identities, 33 copies)

### 3.0 Archetype attributes

All of these have `EntityType Imperium` and `ImperiumType Main`, except Ruthless Leadership, which has `Promo` like the
app's promos. `AcquireValue` = cost + §1.1 offset. `DeferValue` comes from §1.3 (kinds in brackets). Printed data is at
`content/uprising/imperium.py:<line>`.

| card (`card_id`) | src lines | `ImperiumArchetypes.AppStyle.` | Cost | CC | FactionList | IconList | Pers | Str | other reveal / agent attrs | AcqV | LateMod | DV | AcquireEffectList | Tags |
|---|---|---|---:|---:|---|---|---:|---:|---|---:|---:|---:|---|---|
| ruthless_leadership | 1127–1151 (cost 1131, icons 1138, P/S 1142–1143) | RuthlessLeadership | 4 | 1 | Emperor | Circle, Triangle | 1 | 1 | – | 3.8 | – | 2 (T) | – | Combat |
| arrakis_observer | 1157–1171 (1161, 1164, 1166) | ArrakisObserver | 3 | 1 | SpacingGuild | Circle, Triangle | 1 | – | – | 3.0 | – | 2 (Dc,S,R) | – | Spy, WantSpy, RecallSpy, WantSG |
| bombast | 1172–1187 (1176, 1179, 1180, solari 1183) | Bombast | 1 | 1 | Emperor | Pentagon | 1 | – | – | 1.0 | 0.8 | – | – | – |
| choam_demands (CHOAM) | 1188–1202 (1192, 1196) | CHOAMDemands | 6 | 1 | SpacingGuild | Pentagon, Circle, Triangle | – | – | – | 5.8 | – | – (C) | – | WantContract4 |
| command_center | 1203–1217 (1207, 1210, 1212) | CommandCenter | 3 | 1 | Emperor | Emperor, Circle | 1 | – | – | 3.0 | – | – (R) | – | EmperorInfluence |
| corrupt_bureaucrat (CHOAM) | 1218–1231 (1222, 1226, P 1229) | CorruptBureaucrat | 4 | 1 | SpacingGuild | SpacingGuild, Pentagon, Spy | 2 | – | – | 3.8 | – | – (C) | – | WantSpy, WantRecall, IncentiveDiscard, Contract |
| delivery_logistics (CHOAM) | 1232–1244 (1236, copies 1237, 1241) | DeliveryLogistics | 2 | 2 | SpacingGuild | – (`ConditionalIconList` Emperor, SpacingGuild, BeneGesserit, Pentagon, Circle, Triangle = contract-space icons, no reader) | – | – | – | 1.9 | – | – | – | Contract, WantContractX |
| disruption_tactics | 1245–1259 (1249, 1252, 1254) | DisruptionTactics | 2 | 1 | Fremen | Fremen, Triangle | 1 | – | – | 1.9 | – | – (A) | – | Combat |
| eliminate_allies | 1260–1273 (1264, 1267, 1270–1271) | EliminateAllies | 2 | 1 | Emperor | Spy | 1 | 1 | – | 1.9 | – | 2 (T) | – | WantSpy |
| elite_forces | 1274–1286 (1278, 1280–1281, 1283–1284) | EliteForces | 3 | 1 | Emperor, SpacingGuild | Emperor, SpacingGuild | 1 | 1 | – | 3.0 | – | 2 (T,I,R) | – | WantE, Combat |
| engineered_miracle | 1287–1301 (1291, 1294, 1296) | EngineeredMiracle | 3 | 1 | BeneGesserit | Fremen, Triangle | 1 | – | – | 3.0 | – | 2 (Dc,R) | – | DiscardEnabler |
| fremen_war_name | 1302–1320 (1306, 1309, 1313, bond 1316) | FremenWarName | 4 | 1 | Fremen | Fremen, Triangle | 2 | – | – | 3.8 | – | 1 (D,R) | – | FremenBond, ConditionalStrength |
| holy_war | 1321–1343 (1325, 1328–1333, 1336) | HolyWar | 5 | 1 | Fremen | Emperor, SpacingGuild, BeneGesserit, Pentagon | 1 | – | Troops 1 | 4.8 | – | – (A) | – | FremenBond, Combat |
| i_believe | 1344–1358 (1348, 1351, 1353, 1355) | IBelieve | 3 | 1 | Fremen | Fremen, Circle | 1 | – | – | 3.0 | – | 2 (Dc,D) | – | DiscardEnabler |
| imperial_throneship | 1359–1384 (1363, 1366, 1368–1375, 1377, 1380) | ImperialThroneship | 7 | 1 | Emperor | Emperor, SpacingGuild, BeneGesserit, Pentagon, Circle, Triangle | 2 | – | – | 6.8 | – | 2 (I) | RankE | – |
| intelligence_training | 1385–1400 (1389, copies 1390, 1393, 1395–1397) | IntelligenceTraining | 3 | 2 | Emperor | Pentagon, Circle | 1 | 1 | – | 3.0 | – | – | PlaceSpy | Spy |
| ixian_ambassador (Tech) | 1404–1419 (1408, copies 1409, 1412–1414) | IxianAmbassador | 4 | 2 | – | Pentagon | 1 | – | `AgentSpice` 1 | 3.8 | – | – (R) | – | – |
| litany_against_fear | 1420–1430 (1424, 1428) | LitanyAgainstFear | 3 | 1 | BeneGesserit | – | 2 | – | – | 3.0 | – | – | – | – |
| mercantile_affairs (CHOAM) | 1431–1452 (1435, 1439, 1441–1446, 1450) | MercantileAffairs | 5 | 1 | BeneGesserit | BeneGesserit, Circle, Triangle, Spy | 2 | – | – | 4.8 | – | 2 (I) | Contract | WantSpy, WantContractX |
| pointing_the_way | 1453–1468 (1457, 1460, 1462–1463) | PointingtheWay | 6 | 1 | Fremen | Fremen, Circle, Triangle | 1 | 2 | – | 5.8 | – | 2 (I) | – | WantHooks |
| possible_futures | 1469–1485 (1473, 1476, 1477–1478, 1482–1483) | PossibleFutures | 8 | 1 | BeneGesserit, Fremen | Pentagon, Circle, Triangle | 2 | – | Water 1 | 8.0 | – | 2 (F/R) | Water | WantBG |
| quash_rebellion | 1486–1501 (1490, copies 1491, 1494–1496, 1498) | QuashRebellion | 5 | 2 | Emperor | Emperor, SpacingGuild, Pentagon | – | 2 | `AgentSolari` 2 | 4.8 | – | – (R) | – | – |
| sandwalk | 1502–1520 (1506, copies 1507, 1510, 1512–1513, 1516) | Sandwalk | 1 | 2 | Fremen | Triangle | 1 | 1 | – | 1.0 | 0.8 | 1 (D) | – | FremenBond |
| sardaukar_standard | 1521–1533 (1525, 1528, 1530–1531) | SardaukarStandard | 4 | 1 | Emperor | Emperor, Circle | 2 | – | Troops 1 | 3.8 | – | – | – | – |
| shrouded_counsel | 1534–1546 (1538, 1541, 1543) | ShroudedCounsel | 4 | 1 | BeneGesserit | Spy | 1 | – | – | 3.8 | – | 2 (I) | – | WantSpy |
| southern_faith | 1547–1562 (1551, 1554, 1558–1560) | SouthernFaith | 5 | 1 | BeneGesserit, Fremen | Fremen, Circle | 1 | 2 | – | 4.8 | – | 2 (D/F) | – | WantBG |
| urgent_shigawire | 1563–1575 (1567, copies 1568, 1571, 1573) | UrgentShigawire | 2 | 2 | BeneGesserit | BeneGesserit, Circle | 1 | – | – | 1.9 | – | – (X) | – | WantBG |

Every list of `WormAbilityIDs` below starts with `W.PlayAbilities.AgentAbility, <reveal ability>,
W.ActivatedAbilities.AcquireAbility`, the app order for Uprising cards. The reveal ability is `W.PlayAbilities.RevealAbility`
unless a subclass is named. Only the card-specific tail is listed.

### 3.1 Ruthless Leadership (promo)

Printed: Agent "if you have a Commander in the Conflict: trash up to two cards"; Reveal P1 S1, "Command: Combat icon"
(`imperium.py:1139–1149`).
Tail: `AS.RuthlessLeadershipTrashAbility` ×2, `AS.RuthlessLeadershipCommandAbility`.
```
AS.RuthlessLeadershipTrashAbility : W.ActivatedAbilities.TrashAgentAbility         # precedent BeneGesseritTrashAbility
  Cost = engine (P.CommandersConflict >= 1).Then(TrashAbility.Cost)
  ValueForPlayer(P, with) = (P.CommandersConflict + P.CommandersGarrison >= 1) ? TrashAbility.V(P, with) : empty
                                         # TrashCardValue + TrashMod; garrison counted as in ChaniCleverTacticianAgentAbility V
  Evaluate = TrashAbility.Evaluate       # card_to_trash(targets, 1.0): junk, else "used, trash nothing" at 1.0
AS.RuthlessLeadershipCommandAbility : AS.RevealCombatIconAbility, Gate = CommandReached (§2.1)
```
Windows: `trash_agent_card` = E's card, `decline_agent_card_trash` when E has no card (asked once per icon). The Reveal
`deploy_*` comes from §2.2.

### 3.2 Arrakis Observer

Printed: Agent "may discard → Spy with Deep Cover; +2 spice if the discard was a Guild card"; Reveal P1, "may recall a
Spy → 3 swords" (`:1165–1169`).
Tail: `AS.ArrakisObserverAgentAbility`, `AS.ArrakisObserverRevealAbility`.
- `ArrakisObserverAgentAbility : AS.DiscardForRewardAgentAbility` with `Reward = spy_value().Sum`, `SgBonus = True` and
  `SgReward = spice_value(2)`.
- `ArrakisObserverRevealAbility : W.ActivatedAbilities.DeferredAbility`, a Reveal ability with WillClearUndo, Optional
  and Cost `HasAtLeastSpiesOnBoard(1)`. Precedents: SpyNetworkAbility (recall pricing) and CalculusofPowerEmperorAbility
  (→ 3 Strength):
  ```
  E: (spy, _) = AI.recall_spy(targets); if spy is None: return 0
     Upd(AI.strength_value(3) + AI.recall_spy_value().Sum, [spy])          # used iff > 0
  V: MeetsCost ? strength_value(3) + recall_spy_value().Sum : empty
  ```
Windows: `discard_agent_card`/decline; `place_agent_card_spy(post)` = `best_post(engine posts)`, deep cover widening the
list (`PostValue` ignores occupancy, and Double Agent is the app's shared-post precedent); `recall_spy_for_reveal(spy)` =
E's spy, or no answer when E ≤ 0.

### 3.3 Bombast

Printed: Reveal P1, "Command: 3 Solari, then trash this card" (`:1181–1185`).
Tail: `AS.BombastCommandAbility` (§2.1, `Reward = solari_value(3)`, automatic; the self-trash is not priced). The engine
resolves it, so there is no window.

### 3.4 CHOAM Demands (CHOAM)

Printed: Agent "complete one of your contracts (condition ignored)"; Reveal "with ≥ 4 completed contracts: may trash
this → +1 Influence in all four factions" (`:1197–1200`).
Tail: `AS.CHOAMDemandsAgentAbility`, `AS.CHOAMDemandsRevealAbility`.
```
AS.CHOAMDemandsAgentAbility : DeferredAbility (Agent, Explicit, not auto)      # mandatory box, P picks the contract
  E: for c in targets (own active contracts): Upd(c.ContractAbility.GetResourceValue(P).Sum, [c])   # board.md §3.4 vslot 91
     # forced: nothing > 0 → DefaultRandomChoice
  V: max over own active contracts of GetResourceValue(P).Sum, else empty
AS.CHOAMDemandsRevealAbility : DeferredAbility (Reveal, Optional)              # precedent DeliveryAgreementRevealAbility (≥4 → trash → VP)
  Cost = P.GetContractsCompletedCount >= 4
  E = V = Σ over the four factions of AI.gain_influence_value(f, 1, -1, False).Sum    # card loss not priced
```
Windows: `complete_contract_by_card` = E's contract; `trash_reveal_card` (this card) iff E > 0.

### 3.5 Command Center

Printed: Agent "recruit 1 if Emperor Influence ≥ 2"; Reveal P1, "may retreat two troops → +2 Persuasion"
(`:1211–1215`).
Tail: `AS.CommandCenterAgentAbility`, `AS.CommandCenterRevealAbility`.
- `CommandCenterAgentAbility : DeferredAbility` follows the `WheelsWithinWheelsEmperorAbility` shape: Agent, Explicit,
  `AlwaysRunImmediately` true, Cost `HasFactionInfluence.AtLeast(Emperor, 2)`,
  `V = GetFactionInfluence(Emperor) >= 2 ? troop_value(1) : empty`, E inherited (DV).
- `CommandCenterRevealAbility : DeferredAbility` is a Reveal ability, Optional, with Cost
  `HasUnitsDeployed<WormTroop>.AtLeast(2)`. Precedent: Go to Ground, where the retreat test is passed and the value is the
  reward:
  ```
  s = AI.should_play_retreat_intrigue("Command Center", 2, 6, 2)
  n = P.ConflictTroops + P.CommandersConflict          # a Commander is a troop for a retreat [Bloodlines p. 4]
  E: if s > 0 and n >= 2: Upd(persuasion_value(2), null)
  V: same gate and term
  ```
Windows: `retreat_two_troops_for_reveal(commanders = max(0, 2 − P.ConflictTroops))` iff E > 0: troops first, as for
every unit cost here (§2.8, plan 11.5 Desert Scouts). The engine offers `commanders` 0–2 (`rules/reveal_turn.py:815`).
The Agent effect has no window (automatic).

### 3.6 Corrupt Bureaucrat (CHOAM)

Printed: Agent "take a contract if you recalled a Spy this turn"; Reveal P2; "when discarded: 3 Solari"
(`:1227–1229`).
Tail: `AS.CorruptBureaucratAgentAbility`, `AS.CorruptBureaucratDiscardAbility`.
- `CorruptBureaucratAgentAbility : W.ActivatedAbilities.Uprising.GainContractAbility`. It overrides Cost to
  `HasRecalledSpy.Then(base)`, the PublicSpectacleAbility pattern. Its V is gated, the Rebel Supplier and Imperial
  Spymaster way: `V = P.HasRecalledSpyThisTurn ? ContractValueForPlayer(P, with) : empty`. E is inherited:
  `ContractEvaluate(forced=True)`.
- `CorruptBureaucratDiscardAbility : W.TriggeredAbilities.TriggeredAbility` has no AI hook, like
  SpacingGuildsFavorDiscardAbility. The AI's interest comes from the `IncentiveDiscard` tag.

Windows: `contract_market` → `take_contract` = `best_contract(targets, forced=True)`.

### 3.7 Delivery Logistics (CHOAM)

Printed: Agent icons = the icons of your incomplete contracts; Reveal "1 Persuasion OR take a contract" (`:1241–1242`).
Tail: `AS.DeliveryLogisticsRevealAbility : DeferredAbility`, a Reveal ability, Explicit (choose one), following the
`DeliveryAgreementRevealAbility` shape:
```
E: Upd(persuasion_value(1), [Int 0]); Upd(GainContractAbility.ContractValueForPlayer(P).Sum, [Int 1])   # strict >
V: max of the two
```
The Agent icons are pure engine legality: `agent_turn` already lists the extra spaces, and AgentAbility.Evaluate values
them. Windows: `gain_reveal_persuasion` / `take_reveal_contract`, then `contract_market` = `best_contract(forced=True)`.

### 3.8 Disruption Tactics

Printed: Agent "one opponent's troop retreats from the Conflict"; Reveal P1, "may trash this card → Combat icon"
(`:1253–1257`).
Tail: `AS.DisruptionTacticsAgentAbility`, `AS.DisruptionTacticsRevealAbility`.
```
AS.DisruptionTacticsAgentAbility : DeferredAbility (Agent, Explicit; mandatory box, P picks the victim)
  Gain(P, o): c = Match.CurrentConflict(); if c is None or P.Strength <= 0: return 0
       vCur = c.AbilityForPlacement(RankWith(P, current))?.ValueForPlayer(P, []).Sum ?? 0
       vNew = c.AbilityForPlacement(RankWith(P, current with o.Strength − 2))?.ValueForPlayer(P, []).Sum ?? 0
       return vNew − vCur                        # reward-place delta, StrengthIntrigueAbility §5.2 (intrigues.md)
  E: for (o, commander?) in targets: Upd(Gain(P, o), [o, commander?])     # forced: nothing > 0 → DefaultRandomChoice
  V: max(0, max_o Gain(P, o))
AS.DisruptionTacticsRevealAbility : AS.RevealCombatIconAbility
  SelectionMode Optional; Gate = true; E: units = units_to_deploy(...); if units: Upd(0.5, ...)   # card loss not priced
```
The harm done to the victim beyond the change in P's own reward is valued 0 (plan 11.4). Windows:
`retreat_opponent_troop(player, commanders?)` = E's pick; `trash_reveal_card` (self) iff the Reveal E > 0, then `deploy_*`.

### 3.9 Eliminate Allies

Printed: Agent "trash a card (may be this one)"; Reveal P1 S1; "when trashed: recruit 2" (`:1268–1271`).
Tail: `W.ActivatedAbilities.TrashAgentAbility` (generic, as on Calculus of Power and Desert Survival) and
`AS.EliminateAlliesTrashAbility : W.TriggeredAbilities.TriggeredAbility` (no AI hook, the SardaukarSoldierAbility
precedent). There is no `TrashValue`, so the AI does not aim to trash this card itself (§1.2). Windows:
`trash_agent_card`/decline.

### 3.10 Elite Forces

Printed: Agent "may trash a card from hand; if it was an Emperor card: Intrigue + troop + Combat icon"
(`:1282`).
Tail: `AS.EliteForcesAgentAbility : W.ActivatedAbilities.TrashAbility` (Agent, Optional, hand targets). Precedents:
TreacherousManeuverAbility for the Emperor-card pick, which does not price the trashed card, and TrashAbility for junk:
```
E: emp = hand cards ∋ Emperor
   card = card_to_trash(emp, 0.0).card or first(c in emp, c.PersuasionCost < 4) or (is_climax() and emp[0]) or None
   best = card ? (intrigue_value() + troop_value(1) + deploy_value(Owner), card) : None
   (junk, jv) = card_to_trash(hand, 1.0); if junk and (best is None or jv > best.v): best = (jv, junk)
   if best: Upd(best.v, [best.card])
V: the Treacherous Maneuver gate (an Emperor candidate exists as above) ? intrigue_value() + troop_value(1) + deploy_value(Owner) : empty
```
Windows: `trash_agent_card` (hand) / `decline_agent_card_trash`, then the Agent-turn deploy.

### 3.11 Engineered Miracle

Printed: Agent "may discard → 1 water"; Reveal P1, "Command: may trash this → acquire any Imperium Row card"
(`:1295–1299`).
Tail: `AS.EngineeredMiracleAgentAbility` (§2.4, `Reward = water_value(1)`, `SgBonus = False`) and
`AS.EngineeredMiracleCommandAbility : AS.CommandRevealAbility`, Optional, which follows `TleilaxuMasterAbility`
(immortality.md §5.19) without the cost cap:
```
E: for c in targets (row cards): Upd(acquire_value(c).Sum, [c])          # used iff > 0; card loss not priced
Reward(P) = max over ImperiumRowCards of acquire_value(c).Sum (empty if none)
```
Windows: `discard_agent_card`/decline; `command_acquire_row_card(c)` / `decline_command_acquisition`.

### 3.12 Fremen War Name

Printed: Agent "if you gained ≥ 2 spice this turn: recruit 1 + draw 1"; Reveal P2, "Fremen Bond: 2 swords"
(`:1310–1318`).
Tail: `AS.FremenWarNameTroopAbility`, `AS.FremenWarNameDrawAbility`, `AS.FremenWarNameBondAbility`.
- `TroopAbility : DeferredAbility` follows the RebelSupplierAbility shape: Agent, Explicit, auto, E 100, Cost
  `HasGainedSpiceThisTurn.AtLeast(2)`, `V = GainedSpice(P, with, 2) ? troop_value(1) : empty`.
- `DrawAbility : W.ActivatedAbilities.DrawAbility` has Cost `HasGainedSpiceThisTurn.AtLeast(2).Then(HasDrawableCard)` and
  `V = GainedSpice(P, with, 2) ? card_draw_value() + buy_gains(ppg) : empty`, which is DrawAbility.V with the estimate in
  place of MeetsCost. E = DV 1; CanRunImmediately is inherited.
- `BondAbility` follows §2.3 with `strength_value(2)`.

Windows: `resolve_agent_card_effect` (the waiting icons) is answered in the app's state order (plan §4.2).

### 3.13 Holy War

Printed: Agent "each opponent loses a unit, then each opponent Spy watching your space moves"; Reveal P1 + recruit 1,
"Fremen Bond: Combat icon" (`:1334–1340`).
Tail: `AS.HolyWarAgentAbility : DeferredAbility` (Agent, Explicit, auto, E 100, **V = empty**: opponent harm, with the
Gun Thopter precedent, whose BaseSet "each opponent loses one garrisoned troop" has no AI term) and `AS.HolyWarBondAbility`
(§2.2, Gate = `OTHER(Fremen)`; its `ValueInPileForOtherPlay` = FDP, the inherited P of every app Fremen `BondAbility`,
because this class is a `DeployUnitsAbility` and does not inherit it).
Windows opened for **victims**: `opponent_unit_loss` (§2.8) and `opponent_spy_move` (§2.9). The owner's only window is the
bond's `deploy_*`.

### 3.14 I Believe

Printed: Agent "may discard → draw 1"; Reveal P1, "Command: recruit 2" (`:1352–1355`).
Tail: `AS.IBelieveAgentAbility` (§2.4, `Reward = card_draw_value() + buy_gains(ppg)`) and `AS.IBelieveCommandAbility`
(§2.1, `Reward = troop_value(2)`, automatic).

### 3.15 Imperial Throneship

Printed: Agent "draw an Intrigue"; Reveal P2, "with ≥ 4 garrisoned units: +1 Persuasion, 3 Solari"; acquire "+1 Emperor
Influence" (`:1366–1382`).
Tail: `W.ActivatedAbilities.AgentGainIntrigueAbility`, with `AS.ImperialThroneshipRevealAbility : W.PlayAbilities.RevealAbility`
in the reveal slot (preview +1 Persuasion while `P.GarrisonUnits >= 4`) and `AS.ImperialThroneshipTriggeredAbility`
(§2.6, `V = P.GarrisonUnits >= 4 ? persuasion_value(1) + solari_value(3) : empty`). Here `GarrisonUnits` counts
garrisoned troops and Commanders, as the card does (`minimum_garrisoned_units`, `imperium.py:1380`; the app's
`GarrisonUnits` has no Commander, OPEN-1). The acquire effect `RankE` is valued by `GetAcquireEffectsValue`.

### 3.16 Intelligence Training

Printed: Reveal P1 S1, "Command: place a Spy"; acquire "place a Spy" (`:1393–1398`).
Tail: `AS.IntelligenceTrainingCommandAbility : W.ActivatedAbilities.Uprising.PlaceSpyRevealAbility` with the
`CommandReached` gate in V (`spy_value()`), E inherited; and `AS.AcquirePlaceSpyBonusAbility` (§2.11). Windows: the
reveal Spy placement and `acquisition_spy` = `best_post`.

### 3.17 Ixian Ambassador (Tech Module)

Printed: Agent 1 spice; Reveal P1, "with ≥ 2 Tech tiles: +1 Influence of choice" (`:1413–1417`).
Tail: `AS.IxianAmbassadorRevealAbility : W.ActivatedAbilities.GainAnyInfluenceRevealAbility`. Cost
`P.TechTileCount >= 2 .Then(CanGainInfluence)`; `V = P.TechTileCount >= 2 ? gain_influence_value(None, 1) : empty`, gated
the Rebel Supplier way. E is inherited (+100 per track). Window: `gain_reveal_influence(f)`.

### 3.18 Litany Against Fear

Printed: Reveal P2; "turn start: play this → draw 1 and pass" (`:1427–1428`).
Tail: `AS.LitanyTurnStartAbility : DeferredAbility` with timing None. It is offered only in the `turn` window as
`play_turn_start_card` and competes in `DetermineTurn` with the placements:
```
E = AI.card_draw_value_with_buy_gains() + K.CardPlayValueRevealPenalty * GetValueForRevealAbilities(Owner, P).Sum
    # the card leaves the hand unrevealed: AgentAbility V term (f) precedent; the pass itself has no app value
```

### 3.19 Mercantile Affairs (CHOAM)

Printed: Agent "draw an Intrigue if you completed a contract this turn"; acquire "take a contract" (`:1439–1449`).
Tail: `AS.MercantileAffairsAgentAbility : DeferredAbility` follows the ImperialSpymasterAbility shape: Agent, Explicit,
E 100, Cost = contract completed this turn,
`V = (P.ContractsCompletedThisTurn > 0 or own face-up contract c with c.ContractAbility.ValueForPlayer(P, [S]) > 0
for the candidate space S) ? intrigue_value() : empty`. This is the candidate-space test of Smuggler's Harvester and of
the SpaceAbility contract term. The card also has `AS.AcquireContractBonusAbility` (§2.11). Window: `contract_market`
after the acquisition, `best_contract(forced=True)`.

### 3.20 Pointing the Way

Printed: Agent "draw an Intrigue if you have a sandworm in the Conflict"; Reveal P1 S2, "Command: +1 Influence of choice"
(`:1461–1466`).
Tail: `AS.PointingTheWayAgentAbility : DeferredAbility` (ImperialSpymasterAbility shape, Cost
`HasUnitsDeployed<WormSandworm>.Any` as on Leadership, `V = P.ConflictSandwormCount > 0 ? intrigue_value() : empty`) and
`AS.PointingTheWayCommandAbility : W.ActivatedAbilities.GainAnyInfluenceRevealAbility` with the `CommandReached` gate in
V. Window: `gain_reveal_influence(f)` = the GainAnyInfluence E argmax.

### 3.21 Possible Futures

Printed: Agent "+1 Influence of choice OR recruit 2; both with a BG Bond"; Reveal P2 + 1 water; acquire 1 water
(`:1476–1483`).
Tail: `AS.PossibleFuturesAgentAbility : DeferredAbility` (Agent, Explicit). The Agent-box bond is handled like In High
Places (plan 11.5): `Bond = INPLAY(BeneGesserit)`, judged at play (OQ-028 (a)).
```
inf = max over tracks gain_influence_value(t, 1).Sum; tr = troop_value(2)
E: if Bond: Upd(100, [best track])                   # both happen; GainAnyInfluence "Static Boost"
   else: Upd(inf, [Int 0, best track]); Upd(tr, [Int 1])      # strict >: ties keep influence
V: Bond ? gain_influence_value(None, 1) + tr : max(gain_influence_value(None, 1), tr)
P (ValueInPileForOtherPlay): BGP with X = 0.75 × min(gain_influence_value(None, 1), tr)   # the bond's extra
```
Windows: `resolve_agent_card_effect` (option) and the faction picker.

### 3.22 Quash Rebellion

Printed: Agent 2 Solari; Reveal S2, "+2 Persuasion with a Commander in the Conflict" (`:1495–1498`).
Tail: `AS.QuashRebellionRevealAbility : W.PlayAbilities.RevealAbility` in the reveal slot (preview +2 Persuasion while
`P.CommandersConflict >= 1`) and `AS.QuashRebellionTriggeredAbility` (§2.6, `V = P.CommandersConflict >= 1 ?
persuasion_value(2) : empty`). There is no window.

### 3.23 Sandwalk

Printed: Agent "draw 1 if you gained ≥ 2 spice this turn"; Reveal P1 S1, "Fremen Bond: +1 Persuasion"
(`:1511–1518`).
Tail: `AS.SandwalkDrawAbility` (as FremenWarNameDrawAbility, §3.12), with `AS.SandwalkRevealAbility : W.PlayAbilities.RevealAbility`
in the reveal slot (preview +1 while `OTHER(Fremen)`) and `AS.SandwalkBondAbility` (§2.3, `persuasion_value(1)`).

### 3.24 Sardaukar Standard

Printed: Reveal P2 + recruit 1; "when trashed: acquire the bank Commander (+ Skill)" (`:1529–1531`).
Tail: `AS.SardaukarStandardTrashAbility : W.TriggeredAbilities.TriggeredAbility` (no AI hook, the SardaukarSoldierAbility
precedent). The `skill_choice` it opens is answered by `bloodlines-systems.md` (OPEN-1).

### 3.25 Shrouded Counsel

Printed: Agent "draw an Intrigue"; Reveal P1, "Command: may trash a card" (`:1542–1544`).
Tail: `W.ActivatedAbilities.AgentGainIntrigueAbility` and `AS.ShroudedCounselCommandAbility : W.ActivatedAbilities.TrashAbility`
(timing Reveal, Optional). Its V is `CommandReached ? trash_card_value() + trash_mod() : empty`, and its E is
`TrashAbility.Evaluate`. An answer with no card maps to declining. Window: `trash_reveal_card` (junk only).

### 3.26 Southern Faith

Printed: Agent "draw 1 OR (BG Bond) +1 BG Influence"; Reveal P1 S2, "Command: 2 spice" (`:1555–1560`).
Tail: `AS.SouthernFaithAgentAbility : DeferredAbility` (Agent, Explicit; the bond is handled like In High Places) and
`AS.SouthernFaithCommandAbility` (§2.1, `spice_value(2)`, automatic).
```
Bond = INPLAY(BeneGesserit); draw = HasDrawableCard ? card_draw_value() + buy_gains(ppg) : 0
inf = gain_influence_value(BeneGesserit, 1, -1, False).Sum
E: Upd(draw, [Int 0]); if Bond: Upd(inf, [Int 1])          # strict >: ties keep the draw
V: Bond ? max(draw, inf) : draw;   P: BGP with X = 0.75 × max(0, inf − draw)
```

### 3.27 Urgent Shigawire

Printed: Agent "the next BG card you play this round has every Agent icon and draws 1" (`:1572`).
Tail: `AS.UrgentShigawireAgentAbility : DeferredAbility` (Agent, Explicit, auto, E 100):
```
V: if P.Hand.Any(c != Owner and c ∋ BeneGesserit) and P.RemainingAgents.Count() >= 2:
       0.75 × (card_draw_value() + buy_gains(ppg))         # BeneGesseritDrawAbility P "No Bene Gesserit in Play" term
   else empty                                               # the icon grant: 0 (no precedent, 11.4)
```
When the boosted card is played later, the extra icons appear in the engine's legal pairs. The extra draw is not
re-valued at that placement, because the app has no pending-boost term.

## 4. Intrigue cards (18)

### 4.0 Archetype attributes

All have `EntityType Intrigue` and `CardCount 1`. Source: `content/uprising/intrigue.py:<line>`. `SetList` = `Bloodlines`
(Coercive Negotiation also has `CHOAMModule`; Battlefield Research and Rapid Engineering also have `TechModule`).
Column attributes: Types = `IntrigueTypeList`, Str = `Strength`, CV = `CombatValue`, DV = `DeferValue`; `IsBadIntrigue`
is a code override, not an attribute.

| card | src | `IntrigueArchetypes.AppStyle.` | Types | Str | CV | DV (rule) | Rating | Tags | IsBadIntrigue (precedent) |
|---|---|---|---|---:|---:|---:|---:|---|---|
| adaptive_tactics | 783–796 (spice 791, troop 792) | AdaptiveTactics | Plot | – | – | – | 2 | – | `CurrentRound < 3` (Mercenaries) |
| battlefield_research | 802–822 (811–812, 817–818) | BattlefieldResearch | Combat, Endgame | – | – | 2 (Machine Culture) | 2 | BuyTech, ConditionalEndgameVP | Combat: `is_climax()` (Reach Agreement); Endgame: tiles 0 → true, 1 → `is_climax()`, ≥ 2 → false (CHOAM Profits shape kept at the same distance from the card's threshold 3, §9 D32) |
| coercive_negotiation | 823–841 (836–837) | CoerciveNegotiation | Plot | – | – | – (contract) | 2 | Contract | `is_climax()` (Leverage) |
| desert_support | 842–855 (850–851) | DesertSupport | Combat | 5 | 5 | – | 2 | – | `P.Water == 0` (Unexpected Allies) |
| emperor_s_invitation | 856–865 (862–863) | EmperorsInvitation | Plot | – | – | 1 (draw) | 2 | – | false (Cunning) |
| false_orders | 866–872 (871) | FalseOrders | Plot | – | – | – (spy) | 2 | Spy | `SpyDeployedCount >= 2` (Distraction) |
| grasp_arrakis | 876–890 (882, 885–886) | GraspArrakis | Combat, Endgame | 3 | 3 | – | 2 | ConditionalEndgameVP | false (Contingency Plan combat, battle-icon endgame half) |
| honor_guard | 891–903 (899) | HonorGuard | Plot | – | – | – | 2 | – | `GarrisonTroops >= 6` (Call to Arms) |
| insider_information | 904–918 (912–913, 916) | InsiderInformation | Plot | – | – | 2 (trash+draw, Cunning) | 2 | WantSpy, RecallSpy | false (Special Mission) |
| rapid_engineering | 922–942 (931–932, 937–938) | RapidEngineering | Plot | – | – | 2 (Machine Culture) | 2 | BuyTech, DiscardEnabler | `tech_tile_to_acquire(1, False) is None and TechTileCount < 3` (Sietch Ritual: nothing doable) |
| return_the_favor | 943–962 (952–959) | ReturntheFavor | Combat | 5 | 1 | – | 2 | EmperorInfluence, SpacingGuildInfluence, BeneGesseritInfluence, FremenInfluence | false (Weirding Combat) |
| ripples_in_the_sand | 963–977 (970, 972–973) | RipplesintheSand | Combat | 3 | 3 | 2 (Intrigue) | 2 | WantHooks | `!HasMakerHooks and is_climax()` (Devour) |
| sacred_pools | 978–997 (986–987, 992–993) | SacredPools | Plot, Endgame | – | – | – | 3 | DiscardEnabler, ConditionalEndgameVP | Plot false; Endgame: Water 0 → true, 1 → `is_climax()`, ≥ 2 → false (CHOAM Profits shape at the same distance from the threshold 3, §9 D32) |
| seize_production | 998–1012 (1004, 1007–1008) | SeizeProduction | Plot | – | – | – | 2 | – | false (Contingency Plan plot) |
| sleeper_unit | 1013–1032 (1021–1022, 1027–1028) | SleeperUnit | Plot | – | – | – | 2 | Spy, WantSpy, RecallSpy | false (Special Mission) |
| tenuous_bond | 1036–1055 (1044–1045, 1050–1051) | TenuousBond | Plot, Combat | 4 | – | 2 (Change Allegiances) | 3 | – | false (Change Allegiances, Contingency Plan combat) |
| the_strong_survive | 1056–1070 (1062, 1065–1066) | TheStrongSurvive | Combat | 3 | 3 | 2 (trash) | 2 | – | false (Tactical Option) |
| withdrawal_agreement | 1071–1084 (1079–1080) | WithdrawalAgreement | Combat | – | – | 1 (influence) | 2 | – | `is_climax()` (Reach Agreement) |

### 4.1 Abilities and windows

Plot E values compete in the app's three windows: T0, post-Agent and post-Reveal (plan §4.4). `UpdR(v, resp)` answers
`play_intrigue(card, option)`. The later `intrigue_choice`/`intrigue_effects` steps are answered with the response held in
`Memory.intents` (plan §4.6). Combat cards derive from `W.PlayAbilities.StrengthIntrigueAbility` and use its base
Evaluate unless a wrapper is given.

| card | WormAbilityIDs | Evaluate (precedent) | sub-answers |
|---|---|---|---|
| Adaptive Tactics | `AS.AdaptiveTacticsAbility` (Plot; Cost Spice ≥ 1) | `v = (is_final_round() and Reveal) ? 100 : should_play_troop_intrigue("Adaptive Tactics", 6, 4, 1)`; `UpdR(v, [])` if v > 0. This is Mercenaries without the deploy-window gate, because the card brings its own Combat icon. The spice is not priced, as in Mercenaries | deploy window → DeployUnitsAbility E |
| Battlefield Research | `AS.BattlefieldResearchCombatAbility` (Strength-less StrengthIntrigueAbility), `AS.BattlefieldResearchEndgameAbility` (timing Endgame 4, Cost `TechTileCount >= 3`, no E) | Combat follows Go to Ground: `s = should_play_retreat_intrigue("Battlefield Research", 2, 6, 2)`; `n = troops_to_retreat(2)`; if s > 0 and n > 0 and `buy_tech_value(1, False)` > 0, the value is `buy_tech_value(1, False)` (the reward's app price, AcquireTechAbility.V with discount 1). Endgame is automatic | `retreat_intrigue_troops(n, troops first)`; `tech_acquisition` → `W.ActivatedAbilities.RiseOfIx.AcquireTechAbilityDiscount1` E (forced while affordable: the first `TileAcquireValue` max) |
| Coercive Negotiation | `AS.CoerciveNegotiationAbility` (Plot; Cost units deployed this turn ≥ 3 and bank ≥ 3) | `UpdR(gain_contract_value().Sum, [])`. This is the Distraction gate plus the generic contract price, since the tokens are hidden until play | `take_trigger_contract` = `best_contract(3 revealed, forced=True)` |
| Desert Support | `AS.DesertSupportAbility` (Cost Water ≥ 1) | base (StrengthValue 5 when Water ≥ 1); the water is not priced (Spice Is Power) | – |
| Emperor's Invitation | `AS.EmperorsInvitationAbility` (Plot, 2 options) | `UnlockValue(P, {Emperor})` > 0 at T0 → `UpdR(100, [Int 1])`; else if `DrawPlotGate` → `UpdR(draw, [Int 0])` (§2.7, §2.12) | – |
| False Orders | `AS.FalseOrdersAbility` (Plot; Cost an Agent sent this turn) | Distraction: `if SpyDeployedCount > 2: 0` else `UpdR(spy_value().Sum, [])`. Moving opponents' spies is harm, valued 0 | own `spy_placement` = `best_post(turn-space posts)`; victims answer `opponent_spy_move` (§2.9) |
| Grasp Arrakis | `AS.GraspArrakisCombatAbility` (StrengthValue 3), `AS.GraspArrakisEndgameAbility` (Endgame, Cost ≥ 2 face-up Conflict cards) | Combat base. Endgame is automatic, after `ScoreBattleIconsPairs` | `flip_battle_card(card_id)` ×2 (`rules/intrigue.py:994`): the two face-up Conflict cards with the lowest `battle_icon_value`, i.e. unpaired ones first; ties in the engine's order (§9 D17) |
| Honor Guard | `AS.HonorGuardAbility` (Plot) | Shaddam's Favor shape: `UpdR(100, [])` if a troop is in supply and (`IntrigueHandCount > 3` or `is_final_round()` or (a deploy window is open and `current_conflict_interest() > upper bound`)), or if the discount makes a Commander recruit pass the `bloodlines-systems.md` rule this turn (OPEN-2) | – |
| Insider Information | `AS.InsiderInformationAbility` (Plot, 2 options) | `UnlockValue(P, ignore Influence requirements)` > 0 at T0 → `UpdR(100, [Int 1])`. Otherwise, if a spy can be recalled: `spy = recall_spy(spies)`, `v = recall_spy_value() + card_draw_value_with_buy_gains() + (card_to_trash(targets, 1.0).value if a junk card exists)`, and `UpdR(v, [Int 0, spy])` if v > 0 (Special Mission recall, Shishakli trash + draw) | `recall_spy_for_intrigue` = spy; `trash_intrigue_card` = junk or decline |
| Rapid Engineering | `AS.RapidEngineeringAbility` (Plot, 2 options) | Option A, if a tile is affordable at discount 1: `va = discard_value() + buy_tech_value(1, False)` with the card `discard_order(hand, False)[0]`. Option B, if `TechTileCount >= 3`: shuffle the tracks, take the top 2 `gain_influence_value(t, 1)`, `vb = max(0.5, sum)` (GainAnyTwoInfluenceConflictAbility E). Each is answered if > 0, and the later one needs a strictly greater value | `choose_intrigue_discard`; `tech_acquisition` as Battlefield Research; `choose_intrigue_faction` ×2 = the top 2 |
| Return the Favor | `AS.ReturnTheFavorAbility` | base; `StrengthValue(p) = 1 + #factions with influence ≥ 2` (the WeirdingCombat override) | – |
| Ripples in the Sand | `AS.RipplesInTheSandAbility` | Devour: `v = base`; `+ intrigue_value()` if `ConflictSandwormCount > 0`, with no gate; `UpdR(v)` | – |
| Sacred Pools | `AS.SacredPoolsPlotAbility`, `AS.SacredPoolsEndgameAbility` (Endgame, Cost Water ≥ 3) | Plot: `if P.Water >= 3: 0` (kept for the Endgame VP, the Crysknife "keep" precedent). Otherwise Sietch Ritual: discard = `discard_order(hand, False)[0]`, `v = water_value(1) + (10 if IntrigueHandCount > 3 or is_climax())`, and `UpdR(v, [discard])` if v ≥ 3.0 | `choose_intrigue_discard` |
| Seize Production | `AS.SeizeProductionAbility` (Plot, 2 options) | At T0, if 1–2 Solari short of Swordmaster/High Council: `UpdR(100, [Int 0])` (Contingency Plan). Otherwise, under the Councilor's Ambition gate (`is_final_round()` or hand > 3 or (T0 and an agent left)): `UpdR(solari_value(2), [Int 0])`, then if `CommandersConflict >= 1`: `UpdR(spice_value(2), [Int 1])` | – |
| Sleeper Unit | `AS.SleeperUnitAbility` (Plot, 2 options) | Special Mission: if a placement is possible and `spy_value() > solari_value(1)`: `UpdR(spy_value(), [Int 0])`. Otherwise, if a recall is possible: `v = recall_spy_value() + troop_value(2)` with spy = `recall_spy`, `UpdR(v, [Int 1, spy])` if v > 0 | `place_intrigue_spy` = `best_post`; `recall_spy_for_intrigue` |
| Tenuous Bond | `AS.TenuousBondPlotAbility`, `AS.TenuousBondCombatAbility` (Cost: a discard-pile card of cost ≥ 1; StrengthValue 4) | Plot: the swap branch of Change Allegiances only, `(L, G, x) = best_influence_exchange(-1, +1, …)`, `UpdR(x, [L])` if x ≥ 2.0. Combat: base | gain track = `choose_faction_influence` (`abilities/intrigue.py` `choose_faction_influence`, line 1113 at HEAD b244047a; ChooseFactionInfluenceEvaluator, +100 per track); trashed card (`trash_intrigue_card`) = `card_to_trash(eligible, 0.0)` (the LLtF `GetTrashCard` threshold), else the lowest `acquire_value`, first in engine order on ties (Shishakli fallback, imperium-b.md) |
| The Strong Survive | `AS.TheStrongSurviveAbility` (CombatValue override = StrengthValue) | Tactical Option: the strength option is base `v` [Int 0]. The retreat option is 150 [Int 1, unit] under TO's conditions (not close, not climax, lead ≥ 10) and `troops_to_retreat(1) > 0` | `retreat_intrigue_troops(1, troop first)`; `trash_intrigue_card` = junk or decline |
| Withdrawal Agreement | `AS.WithdrawalAgreementAbility` (Strength-less) | `s = should_play_retreat_intrigue("Withdrawal Agreement", 6, 10, 3)` (the retreat-3 parameters of Spice Is Power). If s > 0 and `ConflictUnits >= 3`: `v = gain_influence_value(None, 1).Sum`, `UpdR(v, [3 units])` if v > 0 (Go to Ground: value = reward) | `retreat_intrigue_troops(3, troops first)`; faction = GainAnyInfluence E |

## 5. Twisted Intrigue (12)

Plan 11.5 and OQ-097 apply. Twisted cards are dealt from Piter's private deck, are ordinary Intrigue cards in a hand
(stealable, giftable, and counted for the `IntrigueCard` abundance of `intrigue_value()`), and are never reshuffled into
the Intrigue deck. They must be left out of any Intrigue-deck composition estimate. app_ai has no such estimate today:
`intrigue_value()` is flat and reads only the hand size. Any estimate added later must skip the `twisted_*` ids.

All have `EntityType Intrigue`, `CardCount 1`, `SetList Bloodlines` and no Tags. Source: `intrigue.py:<line>`. Short name
`IntrigueArchetypes.AppStyle.Twisted<Name>`.

| card | src | Types | Str | CV | DV | Rating | IsBadIntrigue |
|---|---|---|---:|---:|---:|---:|---|
| Ambitious | 1086–1095 (lose 3: 1091) | Plot | – | – | 1 | 2 | units (garrison + conflict) < 3, or no faction where an opponent leads (nothing doable) |
| Calculating | 1096–1100 (1099) | Plot | – | – | – | 2 | false (Contingency Plan) |
| Controlled | 1101–1106 (1104–1105) | Plot, Combat | 1 | – | 1 | 3 | false (Contingency Plan) |
| Devious | 1107–1114 (1111, deploy 2: 1113) | Plot | – | – | 2 | 2 | false (Cunning) |
| Discerning | 1115–1122 (1119, 1121) | Plot | – | – | 1 | 2 | false (Cunning) |
| Insidious | 1123–1132 (1128–1129) | Plot | – | – | – | 2 | `IntrigueHandCount < 2` (cannot pay) |
| Resourceful | 1133–1145 (1139–1141) | Plot | – | – | – | 2 | false |
| Sadistic | 1146–1150 (1149) | Plot | – | – | 1 | 2 | false (Cunning) |
| Shrewd | 1151–1160 (1156–1157) | Combat | – | – | – | 2 | `is_climax()` (Reach Agreement) |
| Sinister | 1161–1170 (1166–1167) | Combat | – | – | 2 | 2 | units < 2 (cannot pay) |
| Unnatural | 1171–1180 (1176–1177) | Plot | – | – | 2 | 2 | `IntrigueHandCount < 2` (cannot pay) |
| Withdrawn | 1181–1189 (1186–1187) | Plot (turn start only) | – | – | – | 2 | **true** (never worth playing) |

Each card has one class `AS.Twisted<Name>Ability` per printed half, as listed below. Unit costs are paid with
`LoseUnitPick` (§2.8), which answers `lose_intrigue_troop`.

| card | Evaluate (precedent) | sub-answers |
|---|---|---|
| Ambitious | `v = max over eligible f of gain_influence_value(f, 1).Sum + troop_value(-3)`; `UpdR(v, [f])` if v > 0. The troop cost follows Tleilaxu Surgeon (`GetTroopValue(-n)`), the gain is GetGainInfluenceValue | `choose_intrigue_faction` = f |
| Calculating | `k` = number of unit types P has in the Conflict (troop, sandworm, Commander, Agent). Under the Crysknife-style gate with the Reveal turn in place of its T0 spice clause (`is_final_round()` or hand > 3 or `IsInPlayerTurn(Reveal)`): `UpdR(solari_value(k), [])` if k ≥ 1 | – |
| Controlled | Plot: under `DrawPlotGate`, `UpdR(card_draw_value() + buy_gains(ppg) + solari_value(-1), [])`. The top card is hidden before the peek, so the expected draw-for-1-Solari is used. Combat: base (StrengthValue 1, CV absent) | after the peek: `discard_top_card` if `card_to_trash([top], 0.0)` finds it (junk); else `draw_top_card_for_solari` if `card_draw_value() + buy_gains(ppg) + solari_value(-1) > 0`; else `put_back_top_card` (LLtF evaluator: junk out, keep the rest) |
| Devious | Option A (mandatory trash from hand): `(c, tv) = card_to_trash(hand, 1.0)`, and `UpdR(tv, [Int 0, c])` only if c (junk). Option B: `n = min(2, intrigue_deploy_troops(p, garrison))` (`abilities/intrigue.py` `intrigue_deploy_troops`, line 1361 at HEAD b244047a, the RapidMobilization helper of Detonation's deploy branch; 0 outside the Reveal turn except in the final round), and `UpdR(100, [Int 1, n units])` if n > 0, replacing A by strict > | `trash_intrigue_card`; `deploy_intrigue_troops` |
| Discerning | Option A: `discard_value() + card_draw_value() + buy_gains(ppg)` with `discard_order(hand, False)[0]` (Space-Time Folding). Option B: with an Alliance, `card_draw_value() + buy_gains(ppg)`. Both under `DrawPlotGate`; the better > 0 is played | `choose_intrigue_discard` |
| Insidious | `card = JunkIntriguePick(hand − this)`; `v = spice_value(card is Twisted ? 1 : 2) + trash_intrigue_value()`; `UpdR(v, [card])` if v > 0. The gift to the opponent is valued 0 (11.4) | `give_intrigue_card(card, player)`: player = the first offered (§9 D21) |
| Resourceful | `UnlockValue(P, {Pentagon, Circle, Triangle})` > 0 at T0 → `UpdR(100, [])`; else 0 | – |
| Sadistic | `v = troop_value(-1) + card_draw_value() + buy_gains(ppg)`; `UpdR(v)` if v > 0 (Piter, Genius Advisor: lose a troop → draws, no gate) | `lose_intrigue_troop` |
| Shrewd | `s = should_play_retreat_intrigue("Shrewd", 2, 6, 1)`; if s > 0: `v = spice_value(1) + troop_value(-1)` (the unit is lost, not retreated); `UpdR(v)` if v > 0 | `lose_intrigue_troop(conflict)` |
| Sinister | `v = intrigue_value() + solari_value(1) + troop_value(-2)`; `UpdR(v)` if v > 0 (Tleilaxu Surgeon cost) | `lose_intrigue_troop` ×2 |
| Unnatural | `card = JunkIntriguePick(hand − this)`; `v = intrigue_value() + trash_intrigue_value() + (card not Twisted ? troop_value(1) : 0)`; `UpdR(v, [card])` if v > 0 | `trash_intrigue_hand_card` = card |
| Withdrawn | never offered a value: E = 0 (a pass has no app value). It is the preferred card for JunkIntriguePick | – |

## 6. Conflict cards (2)

Machinery: `GenericConflictFirst/Second/ThirdAbility` value each place with `ValueForRewardsFrom` and
`GetBattleIconValue` (board.md §2.4). A `Wildcard` icon is ×`K.MatchModWildcard` (1.5) in every case, and that formula
already covers wild–wild pairs. Custom rewards are `W.ConflictAbilities.Uprising.TrashConflictCustomAbility` and
`W.ActivatedAbilities.Uprising.PlaceSpyCustomAbility` (both ported). Each conflict archetype lists its three reward
archetypes in `ConflictRewardArchetypes` (read by `GetConflictReward`, board.md §2.4.0), as `PropagandaUP` does.

`RelativeConflictValue` pool: the two cards are **not** added. The app's pool is `GetUprisingConflicts` = conflict
archetypes whose `SetList` contains `Uprising` and that have no `RemovedFromSetList` (board.md §2.6, ported in
`profile/combat.py` `uprising_conflicts`). It is set-based, not deck-based: it leaves out both CHOAM Security and Trade
Dispute variants although they are dealt, and in an Epic game it leaves out Economic Supremacy although it is the
current conflict (epic-goto11-promo-draft.md §2.4, §8 item 1: "keep ES out of the RCV average pool"). The synthetic
archetypes carry `SetList` `Bloodlines`, so the faithful filter leaves them out without a change (§9 D28). When one
of them is the current conflict, its `ConflictValue` is divided by the Uprising cards of its level.

| card (src `content/uprising/conflicts.py`) | `ConflictArchetypes.AppStyle.` | `ConflictLevel` | `BattleIcon` | Tags | WormAbilityIDs | `ConflictRewardArchetypes` 1st / 2nd / 3rd (`EntityType ConflictReward`) |
|---|---|---:|---|---|---|---|
| skirmish_wild (377–391; tier 384, icon 385, rewards 387–389) | SkirmishWild | 1 | Wildcard | BattleIcon | GenericConflictFirst/Second/ThirdAbility | `…SkirmishWildFirst` {CustomAbilityIDs [TrashConflictCustomAbility]} / `…Second` {Water 1, Solari 1} / `…Third` {Solari 2} |
| storms_in_the_south (393–413; tier 403, icon 404, rewards 409–411) | StormsintheSouth | 2 | Wildcard | BattleIcon, Spy | same | `…First` {Spice 2, CustomAbilityIDs [PlaceSpyCustomAbility]} / `…Second` {IntrigueCard 2, Solari 2} / `…Third` {IntrigueCard 1, Solari 2} |

Windows: `combat_reward_trash` uses TrashAbility E (junk, or nothing at 1.0). `combat_reward_spy` (deep cover) =
`best_post` over the engine's wider post list. A won wild card does not pair on arrival (our engine). Endgame wild pairs
(`match_endgame_wild_icon`) follow `ScoreBattleIconsPairs` (plan §5).

## 7. Contract tokens (8, CHOAM only)

Machinery: `ContractAbility.SpecificAcquireValue` drives `GetBestContract` (Space / Harvest / Immediate / Acquire
branches, board.md §3.4). `ContractAbility.ValueForPlayer` merges into placement through `SpaceAbility`'s contract term
(§3.5). Our completion is immediate and mandatory (plan §6). E only orders the effects and answers the sub-prompts:
`contract_reward_spy` = `best_post`, `contract_reward_recall` = `AI.recall_agent(agents) ?? agents[0]` (GetRecallAgent,
RecallAgentContractAbility E).

| token (`bloodlines_*`, src `content/uprising/contracts.py`) | `ContractArchetypes.AppStyle.` | ContractType | ReferencedArchetypeIDs | reward attrs | DV | Tags | WormAbilityIDs |
|---|---|---|---|---|---:|---|---|
| deliver_supplies (403–411; reward 410) | BloodlinesDeliverSupplies | Space | `SpaceArchetypes.Uprising.DeliverSupplies` | Solari 1 | – | Spy | `W…ContractAbilities.PlaceSpyContractAbility`, `W.TriggeredAbilities.Uprising.ActivateContractTriggeredAbility` |
| earn_any_alliance (412–417; 415–416) | BloodlinesEarnAnyAlliance | **Alliance** (new) | – | Solari 2, Troops 2 | – | – | `AS.EarnAllianceContractAbility` |
| harvest_3 (418–423; 421–422) | BloodlinesHarvest3 | Harvest | `SpaceArchetypes.BaseSet.ImperialBasin`, `SpaceArchetypes.Uprising.HaggaBasinUP`, `SpaceArchetypes.Uprising.DeepDesert` (as `ContractBase_1`; + Tuek's Sietch when present, OPEN-3) | Solari 2, `SpiceCost` 3 | – | Spy | `AS.Harvest3SpyContractAbility`, ActivateContractTriggeredAbility |
| harvest_4 (424–429; 427–428) | BloodlinesHarvest4 | Harvest | same | Solari 3, `SpiceCost` 4 | – | Spy | `AS.Harvest4SpyContractAbility`, ActivateContractTriggeredAbility |
| high_council (430–440; 435, 439) | BloodlinesHighCouncil | Space | `SpaceArchetypes.Uprising.HighCouncilUP` | – | – | RecallAgent | `W…ContractAbilities.RecallAgentContractAbility`, ActivateContractTriggeredAbility |
| immediate (441–448; 446–447) | BloodlinesImmediate | Immediate | – | – | 1 | – | `AS.ImmediateTrashIntrigueContractAbility` |
| secrets (449–457; 454, 456) | BloodlinesSecrets | Space | `SpaceArchetypes.BaseSet.Secrets` | Solari 2 | 1 | – | `AS.Draw1ContractAbility`, ActivateContractTriggeredAbility |
| spice_refinery (458–466; 463, 465) | BloodlinesSpiceRefinery | Space | `SpaceArchetypes.Uprising.SpiceRefinery` | Troops 2 | – | – | `W…ContractAbilities.ContractAbility`, ActivateContractTriggeredAbility |

The reused app classes are exact precedents: `ContractBase_14`/`_4` (Space, Solari or Troops plus a Spy),
`ContractBase_13` (recall an Agent) and `ContractBase_15` (Troops 2). Deep cover changes only the engine's post list. The
new classes are:
```
AS.Draw1ContractAbility : W…ContractAbilities.Draw2ContractAbility
  GetResourceValue(P) = ContractAbility.GetResourceValue(P) + card_draw_value() + buy_gains(ppg)    # one card (Draw2 adds 2·CardDrawValue)
AS.Harvest3SpyContractAbility : W…ContractAbilities.Harvest3ContractAbility      # Harvest4 likewise with 4
  GetResourceValue(P) = ContractAbility.GetResourceValue(P) + spy_value().Sum      # PlaceSpyContractAbility override
  ValueForPlayer(P, with) = Harvest3 gate (space spice + bonus ≥ 3) ? this.GetResourceValue(P) : empty
      # the app's Harvest3 V calls the base GetResourceValue non-virtually; this override keeps the Spy term
AS.ImmediateTrashIntrigueContractAbility : W…ContractAbilities.ContractAbility   # ContractType Immediate
  GetResourceValue(P) = intrigue_value() + card_draw_value() + buy_gains(ppg) + trash_intrigue_value()
  # SpecificAcquireValue (Immediate branch) = GetResourceValue: not round-discounted, as ContractBase_19
AS.EarnAllianceContractAbility : W…ContractAbilities.ContractAbility             # ContractType Alliance (new)
  SpecificAcquireValue(P):
     v  = K.AcquireContractRewardValueModRatio × GetResourceValue(P).Sum × max((9 − round)·0.125, 0.25)   # RewardValueMod, Acquire ratio
     near = any faction f whose Alliance P does not hold with AI.has_or_would_gain_alliance(f, 1)
     v += (near ? 3.0 : −3.0) × K.AcquireContractHighCouncilModRatio                # the HighCouncilMod shape of the TSMF contract; its RoundMod is not copied (§9 D23)
  ValueForPlayer: empty (no contract space); completion is automatic (`rules/contracts.py:1500` `complete_alliance_contracts`)
```
Windows: `contract_market` `take_contract` = `best_contract(forced=True)`. When no token can be taken,
`hold_contract_icons`/`resolve_contract_icons_without_contract` is the forced single answer (plan 11.5). The Immediate
token's `contract_intrigue_trash` is answered by `JunkIntriguePick` (§2.10). It cannot be taken without an Intrigue
(engine, OQ-059).

## 8. Decision windows answered (summary)

| window / id | items | answer |
|---|---|---|
| `agent_effects` `trash_agent_card`/decline | Ruthless Leadership ×2, Eliminate Allies, Elite Forces | TrashAbility E / Elite Forces E; decline when no card |
| `discard_agent_card`/decline | Arrakis Observer, Engineered Miracle, I Believe | §2.4 E |
| `place_agent_card_spy` | Arrakis Observer | `best_post` (deep cover posts) |
| `resolve_agent_card_effect` + faction pickers | Possible Futures, Southern Faith, Fremen War Name, Command Center | item E; app state order (plan §4.2) |
| `complete_contract_by_card` | CHOAM Demands | §3.4 E |
| `retreat_opponent_troop` | Disruption Tactics | §3.8 E |
| `opponent_unit_loss` / `opponent_spy_move` (victim) | Holy War, False Orders | §2.8, §2.9 |
| `turn` `play_turn_start_card` | Litany | §3.18 E vs placements |
| `turn`/post-action `play_intrigue` | all Plots | §4.1, §5 |
| `combat_intrigue` `play_intrigue` | Combat halves | StrengthIntrigueAbility E and wrappers |
| `intrigue_choice` (lose/give/peek/trash/retreat/faction/discard, Grasp Arrakis `flip_battle_card`) | §4, §5 | `Memory.intents` from E; `LoseUnitPick`, `JunkIntriguePick` |
| `intrigue_trigger_contract` | Coercive Negotiation | `best_contract(forced=True)` |
| `tech_acquisition` | Battlefield Research, Rapid Engineering | AcquireTechAbilityDiscount1 E |
| `reveal_choice` `trash_reveal_card` | CHOAM Demands, Disruption Tactics, Shrouded Counsel | item E |
| `recall_spy_for_reveal` / `retreat_two_troops_for_reveal(commanders)` | Arrakis Observer / Command Center | item E; Commanders only for the troops missing (§3.5) |
| `command_acquire_row_card`/decline | Engineered Miracle | §3.11 E |
| `gain_reveal_influence` | Pointing the Way, Ixian Ambassador | GainAnyInfluence E |
| `gain_reveal_persuasion`/`take_reveal_contract` | Delivery Logistics | §3.7 E |
| `reveal` `deploy_troops`/`deploy_commanders` | Ruthless Leadership, Holy War, Disruption Tactics | §2.2 |
| `contract_market`, `contract_intrigue_trash`, `contract_reward_*` | tokens, Corrupt Bureaucrat, Mercantile Affairs, Delivery Logistics | §7 |
| `combat_reward_trash`/`combat_reward_spy` | Skirmish (Wild), Storms in the South | §6 |
| `acquisition_spy` | Intelligence Training | `best_post` |

## 9. App-style decisions

Every judgement not fixed by plan 11.3–11.5.

| # | decision | precedent |
|---|---|---|
| D1 | Imperium DeferValue = `min(2, max_kind w)` with Dc = 2; no 3s | fit §1.3 (138/169) |
| D2 | LateMod 0.8 for cost 1, otherwise absent; no EarlyMod or TrashValue | fit §1.2; Sardaukar Soldier (no TrashValue) |
| D3 | Ruthless Leadership keeps `ImperiumType Promo` but takes the §1.1 AcquireValue | plan 11.3 covers every non-app card; the app promos have no AcquireValue only because they are app cards |
| D4 | Command V gate = `possible_persuasion() >= 6` outside the Reveal turn | profile-economy.md §5.1 (`get_PossiblePersuasion` is the app's reveal forecast) |
| D5 | A Reveal-turn Combat icon = DeployUnitsAbility with a card owner, E 0.5 | Sardaukar Coordination (imperium-b.md: DeployUnitsAbility E/V with an Imperium-card owner); Shadout Mapes (immortality.md §5.15) only shows that the app deploys in a Reveal turn |
| D6 | Conditional effects at placement count only when already true, except "spice gained" (candidate space spice + bonus) and "contract completed" (an own contract at the candidate space) | Rebel Supplier and Imperial Spymaster (already true); Harvest3ContractAbility V and Smuggler's Harvester (candidate space) |
| D7 | Corrupt Bureaucrat's contract V is gated by the recall (Public Spectacle's ungated V is not copied) | Rebel Supplier, Strike Fleet, Imperial Spymaster (3 of 4 recall-conditioned cards) |
| D8 | Ruthless Leadership's trash V counts Commanders in the garrison too | ChaniCleverTacticianAgentAbility V (garrison counted) |
| D9 | Disruption Tactics victim = the largest change in P's own reward place; the harm itself is 0 | StrengthIntrigueAbility reward delta (intrigues.md §5.2); plan 11.4 (harm without precedent = 0) |
| D10 | Holy War box V = 0 | Gun Thopter (BaseSet, the same effect): `GunThopterAgentAbility` overrides only `RunImmediateEffects`/`Undo` (`dump/worm-canis.dll.cs:50836`), so there is no AI term |
| D11 | Litany = draw value + reveal penalty × the card's reveal value; the pass is 0 | AgentAbility V term (f), generic-abilities.md §2.2 |
| D12 | Urgent Shigawire V = 0.75 × draw when a BG card is in hand and ≥ 2 agents remain; the icon grant is 0 at Shigawire's own placement; no re-valuation of the boosted play | Draw: BeneGesseritDrawAbility P (imperium-a.md §2.22). Icons: no precedent. This departs from the literal rule 11.4 (no precedent → the one-time price of what the effect gives now, 0 only for harm and information): the grant gives nothing now, and the extra spaces are valued later by `AgentAbility.Evaluate` over the engine's wider legal pairs. The alternative is 0.75 × `UnlockValue` of the best BG hand card under all icons (§2.7). Main session to confirm |
| D13 | Icon-grant / requirement-waiver Plots: 100 at T0 iff they unlock a strictly better placement | Contingency Plan, Backed by CHOAM (enabling T0 plots) |
| D14 | Units are paid from the garrison iff `estimated_conflict_rank(0)` has a value; troops before Commanders | Tleilaxu Surgeon reveal, Piter Genius Advisor; Desert Scouts (plan 11.5) |
| D15 | Agent-box choices between two effects (Southern Faith, Possible Futures) use plain values, without GainAnyInfluence's +100 | plan 11.4 "각 보기의 가치"; the +100 is only an ordering sentinel |
| D16 | Adaptive Tactics drops Mercenaries' deploy-window gate | the card brings its own Combat icon; plan 11.4 |
| D17 | Grasp Arrakis flips the two lowest-`battle_icon_value` face-up Conflict cards, after pairs are scored | no precedent: plan 11.4, the cheapest loss |
| D18 | Battlefield Research / Rapid Engineering price the tech reward with `buy_tech_value(1, False)`, the discard with `discard_value()` | AcquireTechAbility V (rix-tech.md §6.1); Space-Time Folding |
| D19 | Calculating plays in the Reveal turn instead of Crysknife's T0 spice clause | Crysknife gate (intrigues.md §7.7); units are counted after deployment |
| D20 | Controlled's play value uses the expected draw-for-1-Solari (top card hidden); after the peek, junk → discard | honesty rule plan §4.8; LLtF evaluator |
| D21 | Insidious / `give_intrigue_card` recipient = the first opponent offered | plan 11.5 Scouts `scouts_lose_influence_to` (first offered) |
| D22 | Twisted junk tests: the same-effect app card, else "cannot pay"; Withdrawn always junk | intrigues.md §11; Sietch Ritual |
| D23 | Earn Any Alliance SAV = RewardValueMod (Acquire ratio) ± 3 × ratio for "one step from a new Alliance"; the Acquire branch's `RoundMod` (arc ±3 × 0.33) is not copied | TSMF Acquire contract (board.md §3.4, HighCouncilMod shape), `HasOrWouldGainAlliance`; RoundMod dropped because it prices TSMF's late purchase timing, which has no Alliance analogue (no precedent: rule 11.4) |
| D24 | Harvest-Spy tokens keep the Spy term in their own V | PlaceSpyContractAbility; the app's non-virtual call would drop it |
| D25 | Command Center retreat: retreat test `(2, 6, 2)` and value = the reward | Go to Ground / Reach Agreement (intrigues.md §4.1, §6.11). Nearer in card type and timing is `ChaniCleverTacticianRevealAbility` (imperium-a.md §2.7: retreat two troops in the Reveal → 4 swords; E = `GetTroopValue(2)` when ConflictUnits ≥ 3, ConflictTroops ≥ 2 and not final round). It was not used because its reward offsets the 4 lost swords, while Command Center's +2 Persuasion does not; the retreat test prices that loss. Main session to confirm |
| D26 | Withdrawal Agreement: retreat test `(6, 10, 3)` | Spice Is Power retreat-3 |
| D27 | Arrakis Observer has `WantSG` and no `DiscardEnabler` | Guild Envoy, Guild Spy, Space-Time Folding (a Guild discard bonus means WantSG and no DiscardEnabler) |
| D27a | Tag judgements beyond the fitted meanings: Arrakis Observer `WantSpy` (its Reveal recalls a Spy; Spy Network precedent); Mercantile Affairs and Delivery Logistics `WantContractX` (a contract-dependent effect without a count; Interstellar Trade is the only app `WantContractX`, 1/1); Urgent Shigawire `WantBG` (needs a later BG card); Elite Forces `WantE` (needs an Emperor card in hand, Treacherous Maneuver) | §1.4 meanings; each is one-card evidence |
| D28 | The Bloodlines conflicts are **not** in their level's RelativeConflictValue pool (changed by the verifier from "both join") | board.md §2.6: the pool is `GetUprisingConflicts`, a `SetList ∋ Uprising` filter, not the deck; epic-goto11-promo-draft.md §2.4 and §8 item 1: Economic Supremacy is dealt but kept out of the pool. Rule 11.4: follow that precedent; the faithful `uprising_conflicts` port then needs no change |
| D29 | Sacred Pools' Plot half is held while `Water >= 3` | Crysknife intrigue (holds the plot half while its endgame half can score) |
| D30 | Seize Production = Contingency Plan for Solari at T0, else the Councilor's Ambition gate | intrigues.md §7.5, §7.6 |
| D31 | `IsBadIntrigue` by nearest effect where no app card has the same one: Adaptive Tactics ← Mercenaries (pay a resource → troops); Desert Support ← Unexpected Allies (`Water == 0`; Spice Is Power, the pay-for-swords card, returns false); Honor Guard ← Call to Arms (`GarrisonTroops >= 6`; Shaddam's Favor, whose play shape Honor Guard copies, tests its Emperor clause); Withdrawal Agreement and Shrewd ← Reach Agreement (retreat → reward; Go to Ground's test is about spies) | intrigues.md §11; rule 11.4 (nearest precedent) |
| D32 | Endgame VP halves (Battlefield Research ≥ 3 tiles, Sacred Pools ≥ 3 water) copy CHOAM Profits' junk test at the same distance from their own threshold: 3 or more short → true, 2 short → `is_climax()`, 1 short or met → false (changed by the verifier: the first draft copied CHOAM Profits' constant 2, which made "1 short" depend on the climax) | intrigues.md §8.1 (CHOAM Profits needs 4: `< 2` true, `== 2` climax, `> 2` false); Shadow Alliance §8.3 also treats "1 short" as not junk |
| D33 | Rapid Engineering's second option (≥ 3 tiles: +1 Influence in two factions, free) uses `GainAnyTwoInfluenceConflictAbility` E, not Buy Access's gated E | board.md §2.4.3 is the same free two-faction gain; Buy Access (intrigues.md §7.2) pays 5 Solari and is gated on that cost (Swordmaster, climax) |
| D34 | The BGP `X` of Possible Futures and Southern Faith is 0.75 × the bond's extra value | `BeneGesseritDrawAbility` and In High Places' spy use 0.75 × the conditional reward (imperium-a.md §2.22); Southern Elders uses the full reward (`GetTroopValue(2)`, imperium-b.md), so both readings have a precedent. Main session to confirm |

## 10. Counts

67 items: 27 Imperium identities, 18 Intrigues, 12 Twisted, 2 Conflicts, 8 tokens.

New `AS.` classes: 89. That is 5 shared (CommandRevealAbility, RevealCombatIconAbility, DiscardForRewardAgentAbility,
AcquirePlaceSpyBonusAbility, AcquireContractBonusAbility), 44 Imperium, 22 Intrigue (one per printed half), 13 Twisted
(one per printed half; Controlled has two) and 5 contract classes, all named in §3–§7. There are 7 new helpers that are
not ability classes: `GainedSpice`, `UnlockValue`, `LoseUnitPick`, `SpyMovePick`, `JunkIntriguePick`, `DrawPlotGate` and
`RankWith`.

Reused app classes: TrashAgentAbility, TrashAbility, AgentGainIntrigueAbility, DrawAbility, DeferredAbility,
DeployUnitsAbility, BondAbility, TriggeredAbility, RevealAbility, AgentAbility, AcquireAbility,
GainAnyInfluenceRevealAbility, PlaceSpyRevealAbility, GainContractAbility, StrengthIntrigueAbility, IntrigueAbility,
AcquireTechAbilityDiscount1, GenericConflictFirst/Second/ThirdAbility, TrashConflictCustomAbility,
PlaceSpyCustomAbility, ContractAbility, PlaceSpyContractAbility, RecallAgentContractAbility, Draw2ContractAbility,
Harvest3/4ContractAbility, ActivateContractTriggeredAbility (29). Shapes copied without reuse: SpacetimeFolding,
GuildSpyAgent, SouthernEldersBond, BeneGesseritOperative, WheelsWithinWheelsEmperor, RebelSupplier, ImperialSpymaster,
TleilaxuMaster, TreacherousManeuver, CalculusofPowerEmperor, SpyNetwork, DeliveryAgreementReveal, Change Allegiances,
Tactical Option, Special Mission, Distraction, Devour, Weirding Combat, Go to Ground, Reach Agreement, Mercenaries,
Sietch Ritual, Cunning, Contingency Plan, Councilor's Ambition, Shaddam's Favor, Branching Path, Tleilaxu Surgeon,
Piter Genius Advisor, Chaumurky, GainAnyTwoInfluenceConflict, Detonation/RapidMobilization.

## 11. OPEN

| # | open item | what settles it |
|---|---|---|
| OPEN-1 | Commander-related interfaces: the Commander order inside `units_to_deploy` splits (§2.2), the `skill_choice` after Sardaukar Standard (§3.24), and the `P.CommandersConflict`/`P.CommandersGarrison` reads | `bloodlines-systems.md` Commander and Skill sections (same stage) |
| OPEN-2 | Honor Guard's discount clause needs the systems doc's recruit rule as a callable `(cost) → bool` | `bloodlines-systems.md` Commander recruit rule |
| OPEN-3 | Harvest tokens' `ReferencedArchetypeIDs` should include the Tuek's Sietch synthetic space when Esmar Tuek is in the game | the space short name chosen in `bloodlines-systems.md` |
| OPEN-4 | `UnlockValue` needs the turn window to evaluate hypothetical (card, space) pairs under an icon grant; the engine legality for "space becomes legal" (free/infiltrable, cost payable, requirements) must be reproduced in `AppContext` without reading hidden state | implementation stage 4, a small legality helper in `windows/turn.py`; test against our `agent_turn` legal set after playing the Plot |
| OPEN-5 | The MachineCulture E branches are UNTRACED (rix-tech.md §6.5); Battlefield Research / Rapid Engineering use `buy_tech_value` instead | tracing `MachineCulturePlotAbility::Evaluate @0x4bf3730` would allow a faithful shape |
| OPEN-6 | Whether the generator should emit `GetRevealPreviewValue` overrides (Sandwalk, Quash Rebellion, Imperial Throneship): they change `possible_persuasion()` and `buy_gains` everywhere | decide with the generator; the app does it for BG Operative and Southern Elders, so the default here is yes |
