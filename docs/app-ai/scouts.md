# app_ai: the app-style Arrakeen Scouts extension (spec)

> Main-session decisions in `docs/app-ai-plan.md` §11.7 (2026-10-05) override this file where they differ.

Status: specification (plan §11.6 stage 2'), not implemented. Branch `app-ai-expansions`; engine pointers re-checked at
`34287dd4` (no change in `rules/scouts*.py` or `content/arrakeen_scouts/` since the R9 map's `f89f05f3`).
Independently verified at `b244047a` (coverage, printed data, references, rules 11.3–11.5); the verifier's fixes are
the §4.1 face-down card term, the `SubcommitteeOfferAbility` / `MissionPiecesSpaceAbility` members, the overlay
plumbing (§4.8), two window pointers and D46–D49.

The Steam app has no Arrakeen Scouts (it comes from the companion app), so **every Scouts decision here is an app-style
extension** (plan §11.1 option 3). Binding rules: `docs/app-ai-plan.md` §11.3 (values), §11.4 (new decisions), §11.5
"Arrakeen Scouts (R9)" (forced losses: least loss; auctions: bid up to the surplus, no opponent model; delayed payouts:
no discount, 0 when the game may end first; subcommittees: join the best line if > 0; alliance recipient: first
offered; Rebuild Infrastructure: resource prices, agree iff own net value > 0; Scouts-step draws: the app's draw price).
This file applies them item by item; judgement calls are collected in §7.

Sources: rules `docs/rules/arrakeen-scouts.md` (rd), content `src/dune_imperium/content/arrakeen_scouts/*.py`, engine
`src/dune_imperium/rules/scouts*.py`, map R9 (`scratchpad/appai/repo-map/R9-scouts.md`), app specs in
`assets/reference/dune-steam-app/dad97e2021144d45b5b4f022e07bd3b3/analysis/ai/spec/` (cited as `spec/<file> §n`; the
Errata at the end of each file were checked: none touches a method used here). Paths below are relative to
`src/dune_imperium/` unless they start with `docs/` or `spec/`.

## 0. Notation

All prices are existing profile methods (`agents/app_ai/profile/core.py`, Immortality ones in `profile/immortality.py`)
unless marked NEW (defined in §2.1). `GetResourceValue` is linear in the amount, with the abundance level read from
current holdings (spec/profile-economy §3), so a cost is the same call with a negative amount (SpaceAbility precedent,
spec/generic-abilities §6.1).

| Short | Profile method (app name) | Spec |
|---|---|---|
| `Sol(n)` `Spi(n)` `Wat(n)` | `solari_value(n)`, `spice_value(n)`, `water_value(n)` (GetSolariValue …) | profile-economy §3, §3.1 |
| `Tr(n)` | `troop_value(n, False)` (GetTroopValue; positive amounts capped at the supply troops) | profile-economy §3 |
| `UTr(n)` | `uncapped_troop_value(n)` **NEW** §2.1 | — |
| `Spec(n)` | `specimen_value(n)` (GetSpecimenValue) | immortality §2.3–2.4 |
| `Int` | `intrigue_value()` (get_IntrigueValue) | profile-economy §4.4 |
| `Draw` | `DrawAbility.ValueForPlayer` = `card_draw_value_with_buy_gains()` if a card is drawable, else 0 | generic-abilities §7 |
| `CDV` | `card_draw_value()` (get_CardDrawValue) | profile-economy §4.2 |
| `Spy` / `RSpy` | `spy_value().sum` / `recall_spy_value().sum` (SpyValue / RecallSpyValue) | profile-influence-uprising §2.1–2.2 |
| `G(f,n)` | `gain_influence_value(f, n, -1, False).sum` (GetGainInfluenceValue; `n < 0` = the loss branch) | profile-influence-uprising §1.1 |
| `Gany` | `gain_any_influence_value(p, 1).sum` = `G(None, 1)` | generic-abilities §9 |
| `K` | `GainContractAbility.ContractValueForPlayer` = `gain_contract_value().sum` if a Contract can be taken, else `Sol(2)` | generic-abilities §15 |
| `KC` | `gain_contract_value().sum` (GainContractValue): one Contract card that exists (no `Sol(2)` fallback) | profile-influence-uprising §3.2 |
| `Trash` | `TrashAbility.ValueForPlayer` = `trash_card_value() + trash_mod()` | generic-abilities §12.1, profile-economy §11.1 |
| `TI` | `trash_intrigue_value()` (0 with a junk Intrigue in hand, else `TrashIntrigueValue` −1.25) | intrigues §4.5 |
| `Disc` | `discard_value()` (DiscardEarly/Mid/Late, −1) | profile-economy §4.3 |
| `RA` | `recall_agent_value()` (5.0; −3.0 with no Agent out) | generic-abilities §14.2 |
| `RV` | `GainResearchAbility.ValueForPlayer` = `research_value().sum` (ResearchValue) | immortality §2.1, §3.1 |
| `TV(n)` | `tleilaxu_value(n).sum` (TleilaxuValue) | immortality §2.2 |
| `A(c)` | `acquire_value(c).sum` (WormImperiumPlayable::AcquireValue; already 0 below MinimumAcquireValue) | profile-economy §6 |
| `H` | `maker_hooks_value()` (MakerHooksValue; 0 when holding hooks) | profile-influence-uprising §5.1 |
| `BWV` | `blow_wall_value().sum` (BlowWallValue; always ≥ 0) | profile-influence-uprising §6.1 |
| `TB(f)` | `track_bonus_value(f)` **NEW** = block (C) of GetGainInfluenceValue | profile-influence-uprising §1.1 |
| `Gate` | `scouts_conflict_troops_gate()` **NEW** (0 or 100) | intrigues §4.2 |
| `CT(n)` / `CTp(n)` | `Gate > 0 ? Tr(n) : 0` (supply troops) / `Gate > 0 ? UTr(n) : 0` (parked troops) | — |
| `later(v,d)` | `scouts_later(v, d)` **NEW** | — |
| `L(x)` | `scouts_line_value(x)` **NEW** = the value of line archetype `x` (§2.2) | — |
| `mc`, `DRC`, `FSB` | `make_choice`, `default_random_choice`, `first_strictly_best` (`agents/app_ai/choice.py`) | plan §4.1, §4.7 |

`mc` = shuffle → keep > 0 → stable sort descending → first (None = the empty answer). **Least loss** (plan §11.4):
shuffle with the agent RNG, then `FSB` over all candidates including ≤ 0 values (uniform among tied best).

## 1. Primitive prices (R9 §1)

Each Scouts cost/reward primitive is encoded on a *line archetype* (§2.2) either as an app attribute priced by
`scouts_line_value` or as a `WormAbilityIDs` entry whose `ValueForPlayer` gives the price. The choice step column is the
`scouts_effect` action (or other window) the primitive opens and the app evaluator that answers it (§3.2).

| Primitive | Encoding on the line | Price | Choice step → answer | Precedent |
|---|---|---|---|---|
| `GainResources(solari,spice,water)` | `Solari`/`Spice`/`Water` | `Sol(s)+Spi(p)+Wat(w)` | — | ValueForRewardsFrom (generic §18) |
| `PayResources(solari,spice,water)` | `SolariCost`/`SpiceCost`/`WaterCost` | `Sol(−s)+Spi(−p)+Wat(−w)` | — | SpaceAbility cost lines (generic §6.1); Pay*ToGainVP (§20) |
| `DrawPersonalCards(n)` | `DrawAbility` × n | `n·Draw` | — | Research Station's two `DrawAbility` (board §1.5 "2·Draw") |
| `DrawIntrigueCards(n)` | `IntrigueCard` n | `n·Int` | — | ValueForRewardsFrom "Intrigue * n" |
| `PlaceSpy()` | `Uprising.PlaceSpyCustomAbility` | `Spy` | `spy_placement` → PlaceSpyEvaluator / RecallSpyEvaluator (`spy_answer`) | generic §13; Seize Spice Refinery 1st |
| `RecallSpy(n)` (cost) | `RecallSpyCostAbility` × n **NEW** | `n·RSpy` | `scouts_recall_spy` → RecallSpyEvaluator | Recall2SpiesVPAbility (generic §21: `2·RecallSpyValue`) |
| `RecruitTroops(n)` | `Troops` n | `Tr(n)` | `scouts_return_specimens` (Immortality) → shortfall | ValueForRewardsFrom; ReturnSpecimenAbility (immortality §3.4) |
| `RecruitToConflict(n)` | `RecruitToConflictAbility`(Troops n) **NEW** | `CT(n)` | same top-up | ShouldPlayTroopIntrigue gate (intrigues §4.2, §7.9, §7.18) |
| `GainInfluence((F,))` | `FactionInfluence {F: 1}` | `G(F,1)` | — | GainInfluenceAbility (generic §8) |
| `GainInfluence()` any | `GainAnyInfluenceAgentAbility` | `Gany` | `scouts_choose_faction` → GainAnyInfluenceAbility::Evaluate | generic §9 |
| `GainLowestInfluence()` | `GainLowestInfluenceAbility` **NEW** | max over lowest tracks of `G(f,1)` | `scouts_choose_faction` → same, lowest tracks only | ChooseFactionInfluenceEvaluator (influence §1.5) |
| `LoseFactionInfluence(F)` (cost) | `FactionInfluence {F: −1}` | `G(F,−1)` | `scouts_lose_influence_to` → first recipient | ValueForRewardsFrom (amount not checked > 0) |
| `LoseHighestInfluence()` | `LoseHighestInfluenceAbility` **NEW** | max over highest tracks of `G(f,−1)` | `scouts_lose_influence(_to)` → least loss | GetBestInfluenceExchange loss side (influence §1.4) |
| `TakeContract(n)` | `Uprising.GainContractCustomAbility` × n | `n·K` | `contract_market` → GetBestContract(forced) | generic §15 |
| `TrashPersonalCard()` (optional reward) | `TrashCustomAbility` | `Trash` | `optional_trash` → GetCardToTrash(targets, 1.0) | generic §12.1 |
| `TrashPersonalCard(hand_only, mandatory)` (cost) | `TrashFromHandCostAbility` **NEW** | junk in hand ? `trash_card_value()` : `Disc` | `scouts_trash_card` → GetCardToTrash(hand, −DBL_MAX) | GetCardToTrash (economy §11.2) |
| `DiscardFromHand(n)` (cost) | `DiscardCostAbility` **NEW** | `n·Disc` | `scouts_discard` → GetDiscardOrder first | Corrinth City Agent, Delivery Agreement (imperium-a §2.8, §2.11) |
| `TrashIntrigueCard()` (cost) | `TrashIntrigueCostAbility` **NEW** | `TI` | `scouts_trash_intrigue` → Branching Path pick | Branching Path (imperium-a §2.3) |
| `LoseGarrisonTroops(n)` (cost) | `LoseGarrisonTroopsCostAbility` **NEW** | `Tr(−n)` | — | GetResourceValue negative amount |
| `RecallOtherAgent()` | `Uprising.RecallAgentAbility` | `RA` | `scouts_recall_agent` → GetRecallAgent ?? first | Imperial Privilege (board §1.4.9) |
| `AcquireReserveCardToHand(c)` | `AcquireReserveToHandAbility` **NEW** | `A(c)+CDV` | — | AcquireAbility (generic §4.1) + one card in hand |
| `GenerateSpecimens(n)` | `Specimen` n | `Spec(n)` | — | ResearchTrack SpaceValue (immortality §2.10) |
| `PaySpecimens(n)` (cost) | `SpecimenCost` n | `Spec(−n)` | — | GetSpecimenValue negative (immortality §2.4) |
| `Research()` | `Immortality.GainResearchCustomAbility` | `RV` | `research_advance` (Immortality port: SpaceValue + 1.0) | immortality §3.1 |
| `AdvanceTleilaxu(1)` | `Immortality.GainTleilaxuInfluenceCustomAbility` | `TV(1)` | — | immortality §3.2 |
| `AdvanceTleilaxu(2)` | `GainTwoTleilaxuAbility` **NEW** | `TV(2)` | — | PaySolariForTleilaxuInfluence (`TleilaxuValue(2)`, immortality §3.4) |
| `GainSpiceWithHelixBonus()` | `HelixSpiceAbility` **NEW** | `Spi(GM ≥ 1 ? 2 : 1)` | — | (GM = `ctx.genetic_markers()`, OQ-089 (b)) |
| Influence-4 bonus (Friends Everywhere) | — | `TB(f)` | `scouts_four_bonus` → §3.11 | GetGainInfluenceValue block (C) |
| Shield Wall returned (Rebuild) | `ShieldWallReturnAbility` **NEW** | `−BWV` | — | BlowWallValue (influence §6.1) |

Reused classes are full names under `worm.canis.abilities.ActivatedAbilities.` (e.g. `…Uprising.PlaceSpyCustomAbility`,
`…GainAnyInfluenceAgentAbility`, `…Immortality.GainResearchCustomAbility`); all are ported in `abilities/generic.py`
(`DrawAbility` :728, `TrashCustomAbility` :1225, `PlaceSpyCustomAbility` :1299, `RecallAgentAbility` :1323,
`GainContractCustomAbility` :1420, `GainAnyInfluenceAgentAbility` :993) or in the Immortality stage
(`abilities/immortality.py`). None of their `ValueForPlayer`s is gated by their engine `Cost` except `DrawAbility`
(`HasDrawableCard`), which is the right gate here.

Not priced by any primitive (new layers, §3): bid and call amounts, delays, goods lying on the board, round-long rule
changes, the subcommittee opportunity.

## 2. App-style machinery

### 2.1 Profile extensions (NEW, snake_case methods on `Profile`)

```
uncapped_troop_value(n)          # GetResourceValue(Troops, n, false) without "amount = Min(amount, supply troops)"
                                 # (profile-economy §3, Troops block): for troops that do not come from the supply
                                 # (parked mission troops, troops a specimen top-up will supply).

scouts_conflict_troops_gate()    # ShouldPlayTroopIntrigue (intrigues §4.2) without its supply line, with the
                                 # notFirstExtra 6 / firstExtra 4 both app callers pass:
    if not P.CanDeploy: return 0                      # port: _can_deploy (False only inside Shaddam's blocked turn)
    (lb, ub) = conflict_posture_bounds(); i = current_conflict_interest().sum
    if is_climax(): return 100
    if i > ub: return 100
    if not i > lb: return 0
    exp = est_strength().sum; opp = max(est_opponent_strength(o).sum for o in opponents)
    d = opp - exp
    return (0 if abs(d) > 6 else 100) if d > 0 else (0 if exp > opp + 4 else 100)

scouts_later(v, d)               # plan §11.4/§11.5 delayed payout, d = rounds until the payout
    if d >= 1 and is_final_round(): return 0          # profile-economy §1.3 (EndgameTriggerScore via ctx)
    if d >= 2 and is_climax(): return 0               # §1.2; is_final_round() implies is_climax()
    return v

track_bonus_value(f)             # block (C) of GetGainInfluenceValue (influence §1.1), Uprising branch
    Emperor: spy_value().sum; SpacingGuild: resource_value(Solari, 3); BeneGesserit: intrigue_value();
    Fremen: resource_value(Water, 1)

scouts_line_value(line)          # §2.2
subcommittee_opportunity(excl)   # max(0, max over s in ctx.joinable_subcommittees(excl) of L(line of s));
                                 # 0 when the seat holds a council seat or has joined one
```

### 2.2 Line archetypes and `scouts_line_value`

Every Scouts line (one `ScoutsOption`, `content/arrakeen_scouts/types.py:204-227`) is a synthetic archetype, kept
apart from the app extraction (plan §11.3) in a generated module (proposal: `agents/app_ai/data/appstyle_scouts.py`,
generated from the content tuples). Short name `<Kind>Archetypes.AppStyle.Scouts<PascalItem><k>` with
`Kind ∈ {Subcommittee, Mission, Event, Auction, Sale}` and `k` = our option index (auction lines: `k` = place − 1). The
`Scouts` prefix keeps every name clear of app short names (false friends `CovertOperation`, `Mercenaries`, `Leverage`,
`Intelligence…`, R9 §5).

Attributes (app names only): `ArchID`, `EntityType = "ScoutsLine"` (new value; no app code path used here switches on
it), the costs `SolariCost`/`SpiceCost`/`WaterCost`/`SpecimenCost`, the gains `Solari`/`Spice`/`Water`/`Troops`/
`IntrigueCard`/`Specimen`/`FactionInfluence`, and `WormAbilityIDs` (costs first, then rewards, the engine's order).
**No hand-authored values**: every number is printed data (cited per item in §5), so the §11.3 fitted rules
(`AcquireValue`, `DeferValue`, `CombatValue` …) do not apply — a Scouts line is never acquired, deferred or played in
a Conflict. The owner entity of a line's abilities is a new Python-side `Kind.SCOUTS` (`ref = "<item>:<k>"`).

```
scouts_line_value(L):                                  # WormSpace::ValueForPlayer shape (generic §14.2: merge of the
    v = DefaultValueSummer                             #   abilities' V) + the attribute pricing of ValueForRewardsFrom
    if L.SpiceCost    > 0: v.Add(GetSpiceValue(-L.SpiceCost), "Scouts Spice Cost")        # (generic §18) + the
    if L.SolariCost   > 0: v.Add(GetSolariValue(-L.SolariCost), "Scouts Solari Cost")     #   SpaceAbility cost lines
    if L.WaterCost    > 0: v.Add(GetWaterValue(-L.WaterCost), "Scouts Water Cost")         #   (generic §6.1)
    if L.SpecimenCost > 0: v.Add(GetSpecimenValue(-L.SpecimenCost), "Scouts Specimen Cost")
    for a in (Water, Spice, Solari): if L.a > 0: v.Add(GetResourceValue(a, L.a, false), a)
    for (f, n) in L.FactionInfluence: v.Add(GetGainInfluenceValue(f, n, -1, false).Sum)  # n = -1 for a loss
    if L.Troops > 0:       v.Add(GetTroopValue(L.Troops, false), "Troop * n")
    if L.IntrigueCard > 0: v.Add(IntrigueValue * L.IntrigueCard, "Intrigue * n")
    if L.Specimen > 0:     v.Add(GetSpecimenValue(L.Specimen), "Specimens")
    for id in L.WormAbilityIDs: v.Merge(ability(id, owner=L).ValueForPlayer(P, []))
    return v.Sum
```
A line the engine does not offer (`line_is_offered`, `rules/scouts_effects.py:245`) is never a candidate: windows
take candidates from the legal actions, and `subcommittee_opportunity` from `joinable_subcommittees`
(`rules/scouts_effects.py:1308`), which applies the same test.

### 2.3 New ability classes (`worm.canis.abilities.AppStyle.Scouts.*`)

Common members unless stated: base `DeferredAbility`; `Timing` None (the Scouts step is outside any turn; inside a turn
the line runs in its own `scouts_effect` frame); `CanRunImmediately` = true (`AlwaysRunImmediately`; a line's steps are
never post-action keys); `SpecificAcquireValue`, `ValueInPileForOtherPlay` = base (empty); `IsBadIntrigue` n/a; `Cost`
= the engine's affordability test (`option_is_affordable`, `rules/scouts_effects.py:165`). `SelectionMode` Explicit (3)
for a step that asks (forced once the line is taken), Implicit (2) otherwise.

```
RecallSpyCostAbility            # SM 3; one per Spy recalled
  V(P,w) = {RecallSpyValue().Sum "Scouts Recall Spy"}
  E(ctx) = (spy, v) = GetRecallSpy(targets<WormSpy>); UpdateTargets(v + 100.0, [spy])   # = RecallSpyEvaluator (influence §2.5)

DiscardCostAbility              # SM 3
  V = {DiscardValue "Scouts Discard"}
  E = card = GetDiscardOrder(P, targets<WormImperiumPlayable>, false).First(); UpdateTargets(1.0, [card])   # ChooseDiscardEvaluator

TrashIntrigueCostAbility        # SM 3
  V = {TrashIntrigueValue()}
  E = cards = Shuffle(targets<WormIntriguePlayable>); for c in cards: Upd(c.IsBadIntrigue(P) ? 5.0 : 1.0, src, [c])  # strict

TrashFromHandCostAbility        # SM 3 (Funeral Rites, Termination Request)
  V = {(GetCardToTrash(P.Hand, 1.0).card != null) ? TrashCardValue : DiscardValue}
  E = (card, v) = GetCardToTrash(targets, -DBL_MAX); UpdateTargets(v, [card])            # junk first, else the cheapest

LoseGarrisonTroopsCostAbility   # SM 2
  V = {GetTroopValue(-1, false) "Scouts Lose Troop"}

RecruitToConflictAbility        # SM 2; ability attribute Troops = n (set in the ctor, as Pay3SpiceToGain1VPAbility sets SpiceCost)
  V = Gate > 0 ? {GetTroopValue(Troops, false) "Scouts Troops To Conflict"} : {}

ParkedTroopsToConflictAbility   # SM 2; Troops = n (mission troops that reach the Conflict on the seat's visit)
  V = Gate > 0 ? {UTr(Troops)} : {}
ParkedTroopsToGarrisonAbility   # SM 2; Troops = n (recruited to the garrison on the visit)
  V = {UTr(Troops)}

GainLowestInfluenceAbility      # SM 3
  lowest = FactionList tracks where P's influence is minimal (and can still gain)
  V = Max over lowest of GetGainInfluenceValue(f, 1)   (Sum, first max)
  E = for t in targets<WormFactionTrack>: s = GetGainInfluenceValue(t.F, 1); s.Add(100.0); Upd(s.Sum, src, [t])  # strict

LoseHighestInfluenceAbility     # SM 3
  highest = tracks where P's influence is maximal (> 0)   # rules/scouts_effects.py:693 highest_factions
  V = Max over highest of GetGainInfluenceValue(f, -1)  (least negative); {} (0) when no track is above 0
  E = tracks = Shuffle(targets); for t: Upd(GetGainInfluenceValue(t.F, -1).Sum, src, [t])   # strict, first call sticks

AcquireReserveToHandAbility     # SM 2; ReferencedArchetypeIDs = [ImperiumArchetypes.Uprising.PreparetheWay]
  V = stack not empty ? {AcquireValue(card, P).Sum "Acquire", CardDrawValue "To Hand"} : {}

HelixSpiceAbility               # SM 2
  V = {GetSpiceValue(P.GeneticMarkers >= 1 ? 2 : 1)}

GainTwoTleilaxuAbility          # SM 2; Cost CanGainTleilaxuInfluence
  V = {TleilaxuValue(2).Sum}

ShieldWallReturnAbility         # SM 2
  V = {-BlowWallValue().Sum "Shield Wall Returned"}

SubcommitteeOfferAbility        # SelectionMode Optional (0); Timing Agent (High Council) / Reveal (Corrinth City)
  CanRunImmediately = false       # overrides the common default: it is a post-action / post-reveal key (D23)
  Cost = choose_subcommittee is legal (rules/scouts_effects.py:1370: >= 1 joinable now); gates the prompt key only, not V
  V(P,w) = {subcommittee_opportunity(excl)}  if not P.HighCouncilSeat else {}   # excl: "high_council" on the space
  E(ctx) = c = mc(over joinable s: L(line of s)); if c: Upd(c.value, src, [c.s]) # empty -> declined (Optional)

MissionPiecesSpaceAbility       # base DeferredAbility, NOT SpaceAbility (a SpaceAbility subclass would add the
                                #   generic base(S) a second time, the HighCouncilUprisingSpaceAbility quirk, board §1.4.10);
                                # Timing None; CanRunImmediately = true (engine-order state 400, the space's own gains);
                                # SelectionMode Explicit (3) when Imperial Reserve's two goods both wait, else Implicit (2);
                                # Cost = mission_collectable (rules/scouts_missions.py:598), prompt only; V (§4.1) is not
                                #   gated by it, as SpaceAbility's V is not
  E (Imperial Reserve with both goods) = Upd(GetSpiceValue(1), ["spice"]); Upd(GetSolariValue(2), ["solari"])  # strict
  E (otherwise) = Upd(V.Sum, src, [""])                              # the single scouts_collect_mission("")

DesertRidingAbility : SpaceAbilities.Uprising.HaggaBasinUprisingDeferredAbility       # board §1.4.18
  V(P,w) = s = base V; if token and not P.HasMakerHooks:
               sV = GetSpiceValue(2 + SpiceGainReduction); if MakerHooksValue() > sV: s.Add(MakerHooksValue() - sV, "Desert Riding")
  E(ctx) = base E (UpdR(sV,[0]); worms option [1] if hooks);
           if token and not P.HasMakerHooks: UpdR(MakerHooksValue(), src, [IntTargetResponse(2)])   # strict: spice wins ties

CorrinthCityRevealScoutsAbility : ActivatedAbilities.Uprising.CorrinthCityRevealAbility   # imperium-a §2.8
  E = base E, with option 1's summer += subcommittee_opportunity("") when P.CanTakeHighCouncilSeat
  V = base V unchanged (its seat test is inverted: the opportunity is 0 in the seated branch it values)
```

### 2.4 New evaluators (`worm.canis.ai.evaluators.AppStyle.Scouts.*`, where the app keeps its prompt evaluators)

`ScoutsChoiceEvaluator` (§3.1), `SubcommitteeEvaluator` (§3.3), `MissionJoinEvaluator` (§3.4), `SecretPickEvaluator`
(§3.6), `SealedBidEvaluator` and `MercenariesBidEvaluator` (§3.7), `MercenariesRetreatEvaluator` (§3.8),
`CriticalMomentCallEvaluator` (§3.9), `CriticalMomentTakeEvaluator` (§3.10), `FourBonusEvaluator` (§3.11).

## 3. Decision windows

Handlers: a new `agents/app_ai/windows/scouts.py` for the ten `scouts_*` kinds, plus additions to `agent_effects`
(subcommittee, mission collect, Desert Riding), `reveal` (subcommittee) and an `optional_trash` handler. Census = R9 §2
(60 heuristic games). A decision with one legal action never reaches a handler (`agent.py`). "Forced" = no skip action.

### 3.1 `scouts_choice` — `scouts_choose_option(option)` / `scouts_pass` (census 580 / 394)

Frames: an event's or sale's lines (`offer_scouts_choice`, `rules/scouts_effects.py:1027`), Rebuild Infrastructure
(`volunteer` in the context, `_rebuild` :1245), a revealed secret pick with a cost (`only_option`, `offer_only_line`
:1080). Legal: `legal_scouts_choice_actions` :1156 (pass first when passable).

- Per offered line `i`: `v_i = L(line(item, i))`; Rebuild: `v_0 = L(EventArchetypes.AppStyle.ScoutsRebuildInfrastructure0)
  = Spi(−1) − BWV`.
- **Pass legal** (every sale, `passable` events, Rebuild, only-line): `c = mc(v_i)`; `c` → `scouts_choose_option(c)`;
  None → `scouts_pass`. Not forced.
- **Mandatory** (`private_stock`, `smoke_and_mirrors`, `choam_bargain`, and the Influence Reduction family
  `crackdown`, `water_for_spice_smugglers`, `bene_gesserit_treachery`, `funeral_rites`): `c = mc(v_i)` if any `v_i > 0`;
  otherwise the family's forced loss → **least loss** over the offered lines; the other three → `DRC` (plan §11.4).
- Rebuild: `BWV ≥ 0` and `Spi(−1) < 0`, so the seat always passes (computed, not hard-coded).

### 3.2 `scouts_effect` — the choice steps of a taken line (forced)

Opened wherever a line resolves (Scouts step, auction reward, secret reward, or inside the seat's turn for a joined
subcommittee). Legal: `legal_scouts_effect_actions` (`rules/scouts_effects.py:772-837`); a step asks only when there is
more than one way (`_is_choice` :387). Each step is answered by the `Evaluate` of the line ability that owns it:

| Action (census) | Step | Answer |
|---|---|---|
| `scouts_discard(card_id)` (40) | `DiscardFromHand` | `DiscardCostAbility.E`: `discard_order(offered, False)[0]` |
| `scouts_trash_card(card_id)` (19) | mandatory hand trash | `TrashFromHandCostAbility.E`: `card_to_trash(offered, -inf)` |
| `scouts_trash_intrigue(card_id)` (19) | `TrashIntrigueCard` | `TrashIntrigueCostAbility.E`: shuffled, first junk (`bad_intrigue_cards_in_hand`), else first |
| `scouts_recall_spy(post_id)` (107) | `RecallSpy` | RecallSpyEvaluator = `worst_recall_action` (`windows/common.py`) |
| `scouts_choose_faction(faction)` (38) | `GainInfluence()` / lowest tie | `GainAnyInfluenceAbility.Evaluate` / `GainLowestInfluenceAbility.E` = `choose_faction_influence` over the offered tracks (`abilities/intrigue.py:1113`) |
| `scouts_recall_agent(space_id)` (4) | `RecallOtherAgent` | `RecallAgentAbility.Evaluate`: `recall_agent(agents) ?? first offered`; the `conflict` pseudo-space is not a WormSpace (skipped by GetRecallAgent, reachable as the fallback) |
| `scouts_lose_influence(faction)` (4) | `LoseHighestInfluence` tie | `LoseHighestInfluenceAbility.E` (least loss) |
| `scouts_lose_influence_to(alliance_recipient, faction)` (0) | recipient tie | faction: the fixed one (`LoseFactionInfluence`) or least loss (`LoseHighestInfluence`); then the **first** offered action of that faction (plan §11.5; `_faction_action`, `windows/intrigue.py:644`) |
| `scouts_return_specimens(count)` (0) | recruit with a short supply (`_specimen_top_up` :421) | the largest offered count: ReturnSpecimenAbility returns exactly the shortfall (immortality §3.4) |

No value threshold applies: the line was chosen already (its value was > 0 or it was forced).

### 3.3 Subcommittees — three entry points (census 208/222, 3/3, 182/182)

- **`agent_effects`** (High Council seat taken; `legal_subcommittee_choice_actions`, `rules/scouts_effects.py:1370`):
  one PROMPT source "Subcommittee" (Optional, `explicit=False`) realised by `choose_subcommittee` = 
  `SubcommitteeOfferAbility.E` with `excl = pending_subcommittee_exclude` (:1337); it stores the picked id in
  `memory.intents[("subcommittee", round, seat)]` (plan §4.6). `decline_subcommittee` joins `t.declines`, so it is taken
  only when no prompt source is worth > 0 (the existing `skip` order, before `finish_agent_turn`). With nothing joinable
  now only the decline is legal; because joinability is recomputed at every decision, a line that becomes affordable
  later in the turn reappears as a key (the free order of OQ-076 C needs no extra term).
- **`reveal`** (Corrinth City's seat; `queue_reveal_subcommittee_offer`, `rules/scouts_offers.py:70`): the same PROMPT
  source in the post-reveal prompt (`excl = ""`); on the End Turn path `decline_subcommittee` is one of the Optional
  blockers the adapter declines (`windows/reveal.py` §3 of its docstring).
- **`scouts_subcommittee`** frame (`join_subcommittee(subcommittee_id)` / `decline_subcommittee`,
  `legal_subcommittee_actions` :1387): the stored intent if still legal; else `mc` over the joinable lines' `L`; None →
  `decline_subcommittee`. Not forced. No deny-the-opponents and no wait terms (plan §11.5).

### 3.4 `scouts_mission` — `scouts_join_mission(target)` / `scouts_decline_mission` / `scouts_return_specimens(count)` (275/275/0)

Legal: `legal_mission_join_actions` (`rules/scouts_missions.py:422`); targets `join_targets` :297; top-up
`mission_top_up` :373 (counts 1..short, only when the specimens cover the whole shortfall).

- Candidates: each legal target `t` with `J(t) = L(line(mission, t))` (§5.2; CHOAM Escort: `"recruit"` → line 0, a
  Contract id → line 1); and, when top-up counts are legal, the troop way that needs them with
  `J_top = J(troop line, troops priced UTr) + Spec(−short)`, realised by `scouts_return_specimens(short)`.
- `c = mc(...)`; None → `scouts_decline_mission`. Not forced. After a top-up the frame asks again and the join is legal.
- Delayed payoffs are priced now with no discount and no end-of-game zero: the pieces can be collected in the same
  round (`later(·, 0)`).

### 3.5 Inside `agent_effects`: `scouts_collect_mission(choice)` (472) and `take_desert_riding_hooks(space_id)` (98)

- `scouts_collect_mission` (mandatory; `legal_mission_collect_actions`, `rules/scouts_missions.py:629`): an automatic
  `Stage.SPACE` source (the visit's printed pieces, engine-order state 400), `order` = the position of
  `scouts_mission` in the frame's `board_icons`. With Imperial Reserve's two goods (`_imperial_reserve_choices` :619,
  legal order spice then Solari, the goods placement order :184-189): `MissionPiecesSpaceAbility.E` = `FSB` of
  `("spice", Spi(1))`, `("solari", Sol(2))` — spice on ties. Otherwise its single action.
- `take_desert_riding_hooks` (offered beside `harvest_maker_spice` at Hagga Basin to a hookless seat while the token is
  out, `rules/board_effects.py:1495-1510`): `_maker` uses `DesertRidingAbility` instead of the plain Hagga Basin ability;
  response 2 → `take_desert_riding_hooks`, 1 → `summon_maker_sandworms`, else `harvest_maker_spice`. Forced like the
  base choice (Explicit).

### 3.6 `scouts_secret` — `scouts_secret_pick(pick)` (40)

Legal: all four picks always (`legal_secret_pick_actions`, `rules/scouts_secrets.py:76`). Value of pick `k` with delay
`d_k` (`events.py` `SecretChoice.delay`): `w_k = later(L_k, d_k)`, where a line with a cost (Covert Operation 2:
discard 1 → recruit 3) is an optional only-line at resolution (`offer_only_line`), so `L_k = max(0, L(line))`.
`mc(w_k)`; **forced**: none > 0 → `DRC`. Prices use the current state ("the same value as receiving it now").

### 3.7 `scouts_bid` — `scouts_bid(count)` / `confirm_scouts_bid` (688/688)

Legal: `legal_bid_actions` (`rules/scouts_auctions.py:137`), counts `0..bid_cap` (:94). Two-step: the frame stays open
after `scouts_bid`; the seat's current bid is private (`PrivatePlayerView.scouts_bid`, −1 = none = 0 at confirm).

- **Sealed auctions** (`SealedBidEvaluator`): `V = L(first-place line)` (§5.4); `b* = max{b ∈ [1, cap] : V + Sol(−b) > 0}`,
  else 0 (plan §11.4, "up to the surplus"). Two-place auctions bid on the first-place line (§7 D18).
- **Mercenaries** (`MercenariesBidEvaluator`; everyone pays and sends its bid in troops, `deploy_mercenaries` :275):
  `M(b) = CTp(b) + Spi(−b) + (b > supply ? Spec(−(b − supply)) : 0)` (auto top-up, OQ-074 (a));
  `b* = max{b ∈ [1, cap] : M(b) > 0}`, else 0.
- Answer: own bid == `b*` → `confirm_scouts_bid`; else `scouts_bid(count=b*)` (and `b* = 0` with no bid yet → confirm).
  Forced (the empty answer is a 0 bid). Deterministic, so the two decisions agree without an intent.

### 3.8 `scouts_retreat` — `scouts_retreat(count)` (40)

The lowest positive Mercenaries bidder (`legal_retreat_actions`, `rules/scouts_auctions.py:356`):
`n = min(troops_to_retreat(max), max)` with `max` the largest legal count (GetTroopsToRetreat, profile-combat §10;
callers OptionalRetreatAbility, Tactical Option). Forced (0 is legal).

### 3.9 `scouts_call` — `scouts_call(count)` (120)

Open, single-shot, unique amounts (`legal_call_actions`, `rules/scouts_auctions.py:439`). `CriticalMomentCallEvaluator`:
`V = max over scouts_market_cards c of (A(c) + CDV)` (public cards); `r = max{b ≥ 1 : V + Spi(−b) > 0}`; answer the
largest legal amount `≤ r`; none → `scouts_call(0)` (pass). Not forced. A losing call costs nothing
(`close_market` :480), so no shading.

### 3.10 `scouts_market` — `scouts_take_card(slot)` / `scouts_decline_card` (47 / 17)

`legal_take_actions` (`rules/scouts_auctions.py:520`); `amount` and `place` in the frame context. Per slot
`u_s = A(card) + CDV`. Place 0 (forced): `mc(u_s)`; none > 0 → `DRC`. Place 1: `s = mc(u_s)`; take `s` iff
`u_s + Spi(−amount) > 0`, else (and when `mc` returns None) `scouts_decline_card`. Acquisition bonuses then open `acquisition_spy` /
`contract_market` (existing handlers). Bloodlines cards: §8 O1.

### 3.11 `scouts_four_bonus` — `choose_four_bonus(faction)` (12)

`legal_four_bonus_actions` (`rules/scouts.py:765`), all four factions. `FourBonusEvaluator`: `mc` over `TB(f)`
(Emperor `Spy`, Spacing Guild `Sol(3)`, Bene Gesserit `Int`, Fremen `Wat(1)`; content of the bonuses
`rules/influence.py:474-521`). Forced: none > 0 → `DRC`.

### 3.12 Automatic items that leave a choice

| Item | Choice left | Answer |
|---|---|---|
| Political Equilibrium (`events.py:231-240`; task `equilibrium:`, `rules/scouts.py:541-547`) | tie on the highest track, alliance-recipient tie | §3.2 `scouts_lose_influence(_to)` |
| Rebuild Infrastructure (`events.py:411-421`) | agree or pass | §3.1 (always pass) |
| Revealed secret picks (`reveal_due_secrets`, `rules/scouts_secrets.py:124`) | cost line → only-line `scouts_choice`; Spy post, Contract, lowest-track tie | §3.1; `spy_placement`, `contract_market` (existing); §3.2 |
| Auction rewards (`run_auction_reward`, `rules/scouts_auctions.py:261`) | the reward line's steps (Spy post, Contract, research direction) | existing windows, §3.13 |
| Mercenaries deployment (:275-340) | the lowest bidders' retreat | §3.8 (top-up automatic) |
| Mission goods placement, Mating Season, Clear the Market, Unlikely Allies / Eyes on Arrakis / Market Opening / Friends Everywhere activation | none | §4 (valuation terms only) |
| Recruits with a short supply (Immortality) | `scouts_return_specimens` | §3.2 / §3.4 |
| Sietch Tabr while Desert Riding's token is the last free Maker Hooks (OQ-079 (e), `rules/board_effects.py:853-867`) | none: `take_sietch_tabr_supplies` still gives hooks, the token is taken automatically | no term (the hooks option is priced `MakerHooksValue` as before) |

### 3.13 Existing windows reached through Scouts lines

| Window | From | Answer |
|---|---|---|
| `spy_placement` (239 vs 41/58 without Scouts) | every `PlaceSpy` | existing handler `spy_placement` (`windows/uprising.py:135`, which calls `spy_answer`, `windows/common.py:171`); `post_value` gains the Valued Informants term (§4.3) |
| `contract_market` | `TakeContract` | existing (`contract_market`, `windows/uprising.py:234`; GetBestContract forced) |
| `optional_trash` (42/42) | Oversight, Water Discipline | **new handler**: `TrashCustomAbility.Evaluate` = `card_to_trash(targets, 1.0)`; a card → `trash_optional_card(card_id)`, none → `decline_optional_trash` (the app answers "use, trash nothing" at 1.0; generic §12.1). Shared with Immortality's research hexes (§8 O2) |
| `research_advance` | Analytics, New Innovations, Competitive Study | Immortality port (`GainResearchAbility.Evaluate`: SpaceValue + 1.0), plus §4.6 |
| `acquisition_spy`, `contract_market` | Critical Moment / Moment of Revelation acquisition bonuses | existing |

## 4. Valuation terms Scouts adds to existing windows

Each term is gated by Scouts state (goods rows, the round modifier, `arrakeen_scouts`), so games without the option stay
byte-identical.

### 4.1 Mission pieces on board spaces — `MissionPiecesSpaceAbility`

Appended to every board space's `WormAbilityIDs` when `arrakeen_scouts` is on (an overlay in `catalog.space_entity`, §4.8),
so `AgentAbility.Evaluate` (the turn window), `WormSpace::ValueForPlayer` and GetRecallAgent's `50 − value` see it.
Precedent for a seat-specific visit bonus: the contract term of `SpaceAbility::ValueForPlayer` (generic §6.1).

```
V(P, w) for space S:                                    # what P's visit would collect now (apply_mission_collect,
    v = {}                                              #   rules/scouts_missions.py:655-793)
    for (m, seat, loc, n) in ctx.scouts_parked if seat == P and loc == S and m in _VISITED:
        v.Add(m in _TO_CONFLICT ? CTp(n) : UTr(n))      # _TO_CONFLICT :70 (Security Detail, Weirding Warfare,
                                                        #   Send for Aid); garrison: Fedaykin, Coordinate (OQ-077)
    reserve = []
    for (m, loc, r, n, seat) in ctx.scouts_goods if loc == S and seat in (-1, P) and m in _VISITED
                                                  and r != "marker" and n > 0:
        price = {solari: Sol(n), spice: Spi(n), water: Wat(n)}[r]
        if m == imperial_reserve: reserve.append(price) else v.Add(price)
    if reserve: v.Add(max(reserve), "Imperial Reserve")             # one good per visit (OQ-078)
    card = first (m, loc, c) in ctx.scouts_board_card_counts if loc == S and c > 0 and m in _VISITED
                                                                    # (mission, location, count): identities hidden
    if card: v.Add(card.m == choam_research ? KC : Int, "Mission card")   # one face-down card per visit
    return v                                                        # {} (0) when P has nothing to collect at S
```
The face-down card is priced generically (D46): a CHOAM Research Contract is a card that exists, so `KC`
(`gain_contract_value().sum`) and not `K`, whose `Sol(2)` fallback is a Contract icon's 2 Solari once every Contract
has been taken (`docs/rules/choam-module.md`, `[Main p. 16]`), which cannot happen to a card lying on the space; an
Emperor's Schemes card is `Int`. Only one mission uses each location (Research Station, Sardaukar),
matching `_takeable_card` (`rules/scouts_missions.py:580`).

### 4.2 Desert Riding at Hagga Basin

`SpaceArchetypes.Uprising.HaggaBasinUP`'s `HaggaBasinUprisingDeferredAbility` is replaced by `DesertRidingAbility`
(§2.3) while the token is out (`desert_riding_token`, `rules/scouts_missions.py:968`): V becomes `max(Spi(2), H)` for a
hookless seat; E adds option 2. Hooks priced `MakerHooksValue` as Sietch Tabr does (influence §5.2).

### 4.3 Valued Informants goods on posts — `PostValue`

`WormObservationPost::PostValue` (influence §2.3) gains, for a post `p` with a goods row at `post:p`
(`place_mission_goods`, `rules/scouts_missions.py:190-201`): `+ Sol(1)` "Urban Surveillance" or `+ Spi(1)` "Planetary
Exploration" (amounts `missions.py:71`, `:81`). Affects every placement (`spy_placement`, `acquisition_spy`, contract
and track Spies); recalls are unaffected (a post with goods has no Spy). The decision to place a Spy stays
`SpyValue` (post-independent, generic §13.1).

### 4.4 CHOAM Escort goods on a Contract

`ContractAbility::GetResourceValue` (generic §16) of a Contract `k` with goods rows `contract:k` for P:
`+ Sol(1) + Spi(1)` "CHOAM Escort" (`missions.py:108`), paid by the engine on completion (`claim_due_mission_goods`
:919).

### 4.5 The subcommittee opportunity

`SubcommitteeOfferAbility` is appended to `SpaceArchetypes.Uprising.HighCouncilUP` (V = `subcommittee_opportunity
("high_council")` while the seat can still be taken: the Agent being placed is the one Contingencies may not recall),
next to `HighCouncilSpaceAbility`'s `HighCouncilValue`; Corrinth City uses `CorrinthCityRevealScoutsAbility` (§2.3).
Affordability is read in the current state (the seat's 5 Solari is not subtracted, §7 D24).

### 4.6 Immortality goods

| Mission | Term | Where |
|---|---|---|
| Sponsored Research (Helix spice 2, `missions.py:120`) | `+ Spi(2)` "Sponsored Research" to the research-space value of the first-marker spaces (app idx 7–9) while the spice waits and `P.GeneticMarkers == 0` (claim: `rules/immortality.py:349-354`) | `research_space_value` (immortality §2.10) |
| Back Room Deal (Solari 2 on Reclaimed Forces, `missions.py:131`) | `+ Sol(2)` to `v` in `ReclaimedForcesAcquireAbility.Evaluate` while the Solari wait (claim `rules/tleilaxu_row.py:251`) | immortality §3.6 |
| Tleilaxu Offering (2 parked troops, `missions.py:220`) | `+ Spec(parked)` "Tleilaxu Offering" in `TleilaxuValue(n)` when `cur < 3 <= cur + n` and P has troops parked there (`TLEILAXU_OFFERING_TRACK_SPACE`, `rules/scouts_missions.py:55`); added after the late-game cut | immortality §2.2 |
| Coordinate With The Emperor | in §4.1 (Sardaukar) | — |

### 4.7 Round modifiers (`state.scouts_round_modifier`, `RoundModifier`, `types.py:374-380`)

| Modifier | Term |
|---|---|
| `faction_spaces_are_combat` (Eyes on Arrakis, `events.py:391-400`) | overlay on the five faction spaces that are not Combat spaces (`dutiful_service`, `sardaukar`, `deliver_supplies`, `espionage`, `secrets`; `content/uprising/board.py:122-156`; engine test `space_is_combat`, `rules/scouts_modifiers.py:58`): `CombatSpace = True` and `WormAbilityIDs += ActivatedAbilities.DeployUnitsAbility` (the app's own class). Turn value gains `DeployValue(S)`, `_deploy` finds the ability, GetRecallAgent reads the flag. |
| `spice_must_flow_discount` (Market Opening, `events.py:381-390`) | while `not scouts_discount_used`: the Reserve TSMF entity (`ImperiumArchetypes.Uprising.TheSpiceMustFlowUP`) reads `PersuasionCost = 9 − 2 = 7` (`content/uprising/reserve.py:93`, `MARKET_OPENING_DISCOUNT` `rules/scouts_modifiers.py:34`) for PredictCardBuys/GetBuyGains and the AcquireValue consolidation term. Owned TSMF cards are unchanged. |
| `any_faction_four_bonus` (Friends Everywhere, `events.py:401-410`) | in GetGainInfluenceValue block (C), when the gain crosses into 4: add `max_g TB(g)` (FactionList order, first max) instead of `TB(F)`. |
| `ignore_influence_requirements` (Unlikely Allies, `events.py:349-358`) | **none**: space legality comes from our legal `agent_turn` actions (`rules/agent_turn.py:265-279` already waives it) and no ported value reads `InfluenceRequirements` (grep of `agents/app_ai`). |
| Mating Season (`events.py:339-348`) | **none**: `_space_bonus_spice` (`abilities/generic.py:260-270`) reads `state.maker_bonus_spice`, which `_mating_season` raises (`rules/scouts.py:636-654`). |

### 4.8 Where the space overlays live

`catalog.space_entity(space_id, board)` sees only the `Board` (`context.py:50`: `choam`, `immortality`), and its callers
pass `p.ctx.board` (`abilities/generic.py:305`, `imperium_a.py:207`, `imperium_b.py:180`, `leaders.py:973`). So
`Board` gains two fields, both public and both `False` outside Scouts (games without the option keep today's
entities): `scouts` (`config.arrakeen_scouts`; turns on the `MissionPiecesSpaceAbility` overlay of §4.1, the
`SubcommitteeOfferAbility` of §4.5 and the `DesertRidingAbility` swap of §4.2, whose V/E then read the token through
`ctx`) and `faction_spaces_combat` (this round's `scouts_round_modifier == "faction_spaces_are_combat"`, read by
`AppContext.board` from the public state each time; turns on the Eyes on Arrakis overlay of §4.7). `Board.of(config)`
sets `scouts` only; `AppContext.board` adds the round flag.

## 5. Item catalog

`D` = the line's `WormAbilityIDs` (short names; `Up.` = `ActivatedAbilities.Uprising.`, `Im.` = `ActivatedAbilities.
Immortality.`, `AS.` = `AppStyle.Scouts.`); attributes in app names; `V` = `L(line)` in §0 notation. File:line cites
`content/arrakeen_scouts/`. Pools: UP = Uprising, IM = Uprising+Immortality (`types.py:41-46`).

### 5.1 Subcommittees — `subcommittees.py:36-170`, archetypes `SubcommitteeArchetypes.AppStyle.Scouts<Name>0`

Windows: §3.3 (join), §3.2 (steps). Joined inside the seat's turn: `RSpy` includes the WantRecall bonus there
(RecallSpyValue reads `IsInPlayerTurn(AgentTurn)`).

| id (lines) | printed line | attributes | D | V |
|---|---|---|---|---|
| `appropriations` (:38-47) | discard 1 → water 1 | `Water 1` | `AS.DiscardCostAbility` | `Disc + Wat(1)` |
| `intelligence` (:48-55) | → Spy | — | `Up.PlaceSpyCustomAbility` | `Spy` |
| `readiness` (:56-63) | → recruit 1 | `Troops 1` | — | `Tr(1)` |
| `choam_coordination` (:64-72), CHOAM | → Contract 1 | — | `Up.GainContractCustomAbility` | `K` |
| `growth_project` (:73-80), IM | → specimen 1 | `Specimen 1` | — | `Spec(1)` |
| `oversight` (:82-92) | recall Spy 1 → trash + spice 1 | `Spice 1` | `AS.RecallSpyCostAbility`, `TrashCustomAbility` | `RSpy + Trash + Spi(1)` |
| `investigations` (:93-102) | Solari 1 → Intrigue 1 | `SolariCost 1`, `IntrigueCard 1` | — | `Sol(−1) + Int` |
| `forecasting` (:103-112) | spice 1 → draw 2 | `SpiceCost 1` | `DrawAbility` ×2 | `Spi(−1) + 2·Draw` |
| `choam_management` (:113-121), CHOAM | spice 1 → Contract 2 | `SpiceCost 1` | `Up.GainContractCustomAbility` ×2 | `Spi(−1) + 2K` |
| `analytics` (:122-129), IM | Solari 1 → Research | `SolariCost 1` | `Im.GainResearchCustomAbility` | `Sol(−1) + RV` |
| `relations` (:131-138) | spice 2 → any +1 | `SpiceCost 2` | `GainAnyInfluenceAgentAbility` | `Spi(−2) + Gany` |
| `contingencies` (:139-148) | trash Intrigue → recall other Agent | — | `AS.TrashIntrigueCostAbility`, `Up.RecallAgentAbility` | `TI + RA` |
| `leverage` (:149-159) | recall Spy 2 → any +1 + Intrigue 1 | `IntrigueCard 1` | `AS.RecallSpyCostAbility` ×2, `GainAnyInfluenceAgentAbility` | `2·RSpy + Gany + Int` |
| `tleilaxu_relations` (:160-169), IM | spice 3 → Tleilaxu 2 | `SpiceCost 3` | `AS.GainTwoTleilaxuAbility` | `Spi(−3) + TV(2)` |

### 5.2 Missions — `missions.py:27-223`, archetypes `MissionArchetypes.AppStyle.Scouts<Name><k>` (join lines only)

Join = §3.4; collect = §3.5/§4.1. Supply troops leaving the supply cost nothing (the app prices no supply troop, §7 D9);
at join the supply holds the troops, so `Tr(n) = UTr(n)` there.

| id (lines), type, rounds, pool | printed | join line(s): attributes / D | V (join) | Board term |
|---|---|---|---|---|
| `security_detail` (:29-40), 0, 2–3 | park supply troop 1 on Deliver Supplies; visit → Conflict | 0: `AS.ParkedTroopsToConflictAbility`(Troops 1) | `CTp(1)` | §4.1 |
| `imperial_reserve` (:41-51), 0, 2–3 | spice 1 + Solari 2 on Imperial Privilege | no join | — | §4.1 (one of the two); §3.5 pick |
| `desert_riding` (:52-61), 0, 2–3 | Maker Hooks token at Hagga Basin | no join | — | §4.2 |
| `urban_surveillance` (:62-72), 0, 2–3 | Solari 1 on empty City posts | no join | — | §4.3 |
| `planetary_exploration` (:73-82), 0, 2–3 | spice 1 on empty Maker posts | no join | — | §4.3 |
| `choam_research` (:83-94), 0, 2–3, CHOAM | 2 face-down Contracts at Research Station | no join | — | §4.1 (`K`) |
| `choam_escort` (:95-110), 0, 2–3, CHOAM | recruit 1, or Solari 1 + spice 1 on an own Contract | 0 `"recruit"`: `Troops 1`; 1 `<contract>`: `Solari 1`, `Spice 1` | `Tr(1)`; `Sol(1)+Spi(1)` (paid on completion, no discount) | §4.4 |
| `sponsored_research` (:111-121), 0, 2, IM | spice 2 beside the Helix | no join | — | §4.6 |
| `back_room_deal` (:122-132), 0, 2–3, IM | Solari 2 on Reclaimed Forces | no join | — | §4.6 |
| `prison_planet` (:134-145), 1, 2–3, UP | lose garrison troop 1; marker + spice 2 on Sardaukar | 0: `Spice 2`; `AS.LoseGarrisonTroopsCostAbility` | `Tr(−1) + Spi(2)` | §4.1 (spice 2; marker unpriced) |
| `emperors_schemes` (:146-156), 1, 2–3 | 2 face-down Intrigue at Sardaukar | no join | — | §4.1 (`Int`) |
| `fedaykin_assistance` (:157-169), 1, 3 | spice 1; park supply troops 2 on Desert Tactics → garrison | 0: `SpiceCost 1`; `AS.ParkedTroopsToGarrisonAbility`(Troops 2) | `Spi(−1) + UTr(2)` | §4.1 |
| `weirding_warfare` (:170-182), 1, 2–3 | Solari 2; park supply troops 2 on Espionage → Conflict | 0: `SolariCost 2`; `AS.ParkedTroopsToConflictAbility`(Troops 2) | `Sol(−2) + CTp(2)` | §4.1 |
| `send_for_aid` (:183-195), 1, 2–3 | garrison troop 1 to Gather Support + water 1 → Conflict + water | 0: `Water 1`; `AS.LoseGarrisonTroopsCostAbility`, `AS.ParkedTroopsToConflictAbility`(Troops 1) | `Tr(−1) + CTp(1) + Wat(1)` | §4.1 |
| `coordinate_with_the_emperor` (:196-210), 1, 3, IM | specimen 1 to Sardaukar + Solari 2 → Solari 2 + garrison troop | 0: `SpecimenCost 1`, `Solari 2`; `AS.ParkedTroopsToGarrisonAbility`(Troops 1) | `Spec(−1) + Sol(2) + UTr(1)` | §4.1 |
| `tleilaxu_offering` (:211-222), 1, 2, IM | park supply troops 2 on Tleilaxu space 3 → 2 specimens | 0: `Specimen 2` | `Spec(2)` | §4.6 |

### 5.3 Events — `events.py:58-510`, archetypes `EventArchetypes.AppStyle.Scouts<Name><k>`

P = passable (§3.1), M = mandatory, LF = Influence Reduction family (least loss), S = secret (§3.6, `d` = delay).

| id (lines), tickets | kind | line `k`: attributes / D → V |
|---|---|---|
| `private_stock` (:60-72), 5 | M | 0: `Spice 1` → `Spi(1)` · 1: `DrawAbility` → `Draw` |
| `market_research` (:73-85), 5 | P | 0: `Spice 2`; `AS.RecallSpyCostAbility` → `RSpy + Spi(2)` |
| `smoke_and_mirrors` (:87-101), 5 | M | 0: `Up.PlaceSpyCustomAbility` → `Spy` · 1: `SolariCost 1`, `IntrigueCard 1` → `Sol(−1) + Int` |
| `rotating_doors` (:102-117), 5 | P | 0: `IntrigueCard 1`; `AS.TrashIntrigueCostAbility`, `DrawAbility` → `TI + Int + Draw` |
| `moment_of_revelation` (:119-134), 10 | P | 0: `SpiceCost 2`; `AS.AcquireReserveToHandAbility` (Prepare the Way, cost 2 `content/uprising/reserve.py:74`) → `Spi(−2) + A(PtW) + CDV` |
| `water_discipline` (:135-150), 10 | P | 0: `WaterCost 1`; `TrashCustomAbility`, `DrawAbility` → `Wat(−1) + Trash + Draw` |
| `royal_delegation` (:152-167), 6 | P | 0: `SolariCost 2`, `FactionInfluence {Emperor: 1}` → `Sol(−2) + G(Emp,1)` |
| `guild_negotiation` (:168-183), 6 | P | 0: `SpiceCost 1`, `FactionInfluence {SpacingGuild: 1}`; `AS.DiscardCostAbility` → `Spi(−1) + Disc + G(SG,1)` |
| `covert_assistance` (:184-198), 6 | P | 0: `FactionInfluence {BeneGesserit: 1}`; `AS.RecallSpyCostAbility` → `RSpy + G(BG,1)` |
| `gift_of_water` (:199-213), 6 | P | 0: `WaterCost 1`, `FactionInfluence {Fremen: 1}` → `Wat(−1) + G(Fr,1)` |
| `share_intelligence` (:214-229), 6 | P | 0: `SolariCost 1`; `AS.TrashIntrigueCostAbility`, `GainAnyInfluenceAgentAbility` → `TI + Sol(−1) + Gany` |
| `political_equilibrium` (:231-240), 6 | automatic | 0: `AS.LoseHighestInfluenceAbility` (ties only, §3.2) |
| `crackdown` (:241-253), 6 | M, LF | 0: `AS.RecallSpyCostAbility` → `RSpy` · 1: `FactionInfluence {Emperor: −1}` → `G(Emp,−1)` |
| `water_for_spice_smugglers` (:254-266), 6 | M, LF | 0: `WaterCost 1` → `Wat(−1)` · 1: `FactionInfluence {SpacingGuild: −1}` → `G(SG,−1)` |
| `bene_gesserit_treachery` (:267-279), 6 | M, LF | 0: `AS.LoseGarrisonTroopsCostAbility` → `Tr(−1)` · 1: `FactionInfluence {BeneGesserit: −1}` → `G(BG,−1)` |
| `funeral_rites` (:280-292), 6 | M, LF | 0: `AS.TrashFromHandCostAbility` → junk ? `trash_card_value()` : `Disc` · 1: `FactionInfluence {Fremen: −1}` → `G(Fr,−1)` |
| `covert_operation` (:294-314), 10, no CHOAM | S | 0 (d1): `Up.PlaceSpyCustomAbility` → `Spy` · 1 (d1): `Solari 2` → `Sol(2)` · 2 (d2): `Troops 3`; `AS.DiscardCostAbility` → `max(0, Disc + Tr(3))` · 3 (d2): `AS.GainLowestInfluenceAbility` |
| `covert_operation_choam` (:315-337), 10, CHOAM | S | as above, but 1 (d1): `Up.GainContractCustomAbility` → `K` |
| `mating_season` (:339-348), 10 | automatic | no line; §4.7 |
| `unlikely_allies` (:349-358), 10 | modifier | no line; §4.7 |
| `clear_the_market` (:359-369) / `_choam` (:370-380), 10 | automatic | no line, no term |
| `market_opening` (:381-390), 10 | modifier | no line; §4.7 |
| `eyes_on_arrakis` (:391-400), 10 | modifier | no line; §4.7 |
| `friends_everywhere` (:401-410), 10, rounds 5–7 | modifier | no line; §4.7, §3.11 |
| `rebuild_infrastructure` (:411-421), 10, round 7 | P (shared) | 0: `SpiceCost 1`; `AS.ShieldWallReturnAbility` → `Spi(−1) − BWV` |
| `choam_bargain` (:422-435), 10, CHOAM | M | 0: `DrawAbility` → `Draw` · 1: `Up.GainContractCustomAbility` → `K` |
| `ingratiate` (:437-447), 10, IM | P | 0: `SpecimenCost 1`; `GainAnyInfluenceAgentAbility` → `Spec(−1) + Gany` |
| `betrayal` (:448-463), 10, IM | P | 0: `FactionInfluence {BeneGesserit: −1}`; `Im.GainTleilaxuInfluenceCustomAbility` → `G(BG,−1) + TV(1)` |
| `new_innovations` (:464-477), 10, IM | P | 0: `SolariCost 1`; `Im.GainResearchCustomAbility` → `Sol(−1) + RV` · 1: `SpiceCost 1`; same → `Spi(−1) + RV` |
| `termination_request` (:478-490), 10, IM | P | 0: `Specimen 1`; `AS.TrashFromHandCostAbility` → `(junk ? trash_card_value() : Disc) + Spec(1)` |
| `offworld_operation` (:491-509), 10, IM | S | 0 (d1): `Solari 2` → `Sol(2)` · 1 (d1): `AS.HelixSpiceAbility` → `Spi(GM≥1 ? 2 : 1)` · 2 (d2): `Im.GainTleilaxuInfluenceCustomAbility` → `TV(1)` · 3 (d2): `IntrigueCard 1` → `Int` |

### 5.4 Auctions — `auctions.py:47-186`, archetypes `AuctionArchetypes.AppStyle.Scouts<Name><place−1>`

Bid caps: `MAX_AUCTION_BID = 99` (`auctions.py:36`), `MAX_MERCENARIES_BID = 3` (:38). Window §3.7–§3.10.

| id (lines), slot | currency | 1st line → V | 2nd line → V |
|---|---|---|---|
| `highest_bidder_mid` (:48-59), mid | Solari | `DrawAbility` → `Draw` | — |
| `highest_bidder_late` (:60-72), late | Solari | `DrawAbility` ×2 → `2·Draw` | `DrawAbility` → `Draw` |
| `mercenaries` (:73-83), either | spice (≤ 3, ≤ supply + specimens) | no line: `M(b)` §3.7 (`RecruitToConflict` priced `CTp`) | retreat §3.8 |
| `competitive_study_mid` (:84-95), mid, IM | Solari | `Specimen 1`; `Im.GainResearchCustomAbility` → `RV + Spec(1)` | — |
| `competitive_study_late` (:96-108), late, IM | Solari | same → `RV + Spec(1)` | `Im.GainResearchCustomAbility` → `RV` |
| `spies_for_hire_mid` (:109-120), mid | Solari | `Up.PlaceSpyCustomAbility` → `Spy` | — |
| `spies_for_hire_late` (:121-133), late | Solari | `IntrigueCard 1`; `Up.PlaceSpyCustomAbility` → `Spy + Int` | `Up.PlaceSpyCustomAbility` → `Spy` |
| `critical_moment_mid` (:134-145), mid | spice (open) | no line: 1 of 2 revealed to hand, §3.9–3.10 | — |
| `critical_moment_late` (:146-158), late | spice (open) | no line: 1 of 3 to hand | may buy 1 of the rest |
| `choam_negotiations_mid` (:159-171), mid, CHOAM | Solari | `Up.GainContractCustomAbility` → `K` | — |
| `choam_negotiations_late` (:172-185), late, CHOAM | Solari | `IntrigueCard 1`; `Up.GainContractCustomAbility` → `K + Int` | `Up.GainContractCustomAbility` → `K` |

### 5.5 Sales — `auctions.py:190-250`, archetypes `SaleArchetypes.AppStyle.Scouts<Name><k>` (all passable, §3.1)

| id (lines) | line 0 → V | line 1 → V |
|---|---|---|
| `unravel_the_future` (:191-204) | `SpiceCost 1`; `DrawAbility` → `Spi(−1) + Draw` | `SpiceCost 3`; `DrawAbility` ×2 → `Spi(−3) + 2·Draw` |
| `imperium_connections` (:205-216) | `SolariCost 2`; `Up.PlaceSpyCustomAbility` → `Sol(−2) + Spy` | `SolariCost 2`, `Water 1` → `Sol(−2) + Wat(1)` |
| `secrets_for_sale` (:217-230) | `SpiceCost 1`, `IntrigueCard 1` → `Spi(−1) + Int` | `SpiceCost 3`, `IntrigueCard 2` → `Spi(−3) + 2·Int` |
| `shadow_warfare` (:231-249) | `Spice 1`; `AS.RecallSpyCostAbility`, `AS.RecruitToConflictAbility`(Troops 1) → `RSpy + CT(1) + Spi(1)` | `Spice 2`; `AS.RecallSpyCostAbility` ×2, `AS.RecruitToConflictAbility`(Troops 3) → `2·RSpy + CT(3) + Spi(2)` |

Line archetypes in total: 14 + 9 + 42 + 12 + 8 = 85.

## 6. `AppContext` accessors (honesty, plan §4.8)

New read-only accessors, all public or own-seat: `scouts` (option flag), `scouts_round_modifier`, `scouts_discount_used`,
`scouts_item`, `scouts_subcommittees`, `scouts_subcommittee_members`, `joinable_subcommittees(exclude_space)` and
`pending_subcommittee_exclude()` (engine predicates on public state and the seat's own hand/Intrigue/resources),
`scouts_goods`, `scouts_parked`, `scouts_board_card_counts` (the public view's `(mission, location, count)` rows,
`core/observation.py:239`, built by `_board_card_counts` `:445`; **never** `state.scouts_goods_cards`, which holds the
hidden identities), `desert_riding_token()`, `scouts_market_cards`, `scouts_calls`, `own_scouts_bid()` (private
view). `board` (`context.py:108`) adds `faction_spaces_combat` from `scouts_round_modifier` (§4.8). Not read: other
seats' secret picks and sealed bids (`scouts_bids_confirmed` is public but unused).

## 7. App-style decisions

| # | Decision | Precedent |
|---|---|---|
| D1 | A Scouts line is a synthetic archetype valued like a space: attribute prices + merge of its abilities' V | `WormSpace::ValueForPlayer` (generic §14.2), `ValueForRewardsFrom` (§18), SpaceAbility cost lines (§6.1) |
| D2 | `n` cards drawn = `n` DrawAbility instances | Research Station's two DrawAbility (board §1.5) |
| D3 | `n` Intrigue = `n·IntrigueValue`; `n` Contracts = `n` GainContractCustomAbility | ValueForRewardsFrom; generic §15 |
| D4 | Discard cost = `DiscardValue`, pick = GetDiscardOrder first | Corrinth City Agent / Delivery Agreement (imperium-a §2.8, §2.11); ChooseDiscardEvaluator (economy §12.2) |
| D5 | Forced hand trash: junk in hand ? `TrashCardValue` : `DiscardValue`; pick GetCardToTrash(hand, −DBL_MAX) | no precedent: rule 11.4 "app has no machine" (one-time price: the card leaves this round's hand; permanence unpriced) + forced least loss via GetCardToTrash's own ranking (economy §11.2) |
| D6 | Trash-Intrigue cost = `TrashIntrigueValue()`, pick = shuffled first junk else first | Branching Path (imperium-a §2.3; intrigues §4.5) |
| D7 | Garrison troop lost = `GetTroopValue(−1)` | GetResourceValue negative amounts (SpaceAbility costs, generic §6.1) |
| D8 | Influence loss as `FactionInfluence {F: −1}` | ValueForRewardsFrom does not check `n > 0` (generic §18) |
| D9 | Supply troops moved off the supply cost 0 | no precedent: rule 11.4 (the app prices only gained troops and garrison abundance, economy §3) |
| D10 | Troops not from the supply (parked, topped up) priced uncapped (`uncapped_troop_value`) | no precedent: rule 11.4 (the app's supply cap assumes troops come from the supply) |
| D11 | Troops straight into the Conflict = troop price gated by ShouldPlayTroopIntrigue (minus its supply line; 6/4) | Mercenaries / Depart for Arrakis intrigues (intrigues §4.2, §7.9, §7.18) |
| D12 | Card acquired to hand = `AcquireValue + CardDrawValue` | no precedent: rule 11.4 (one-time price of one more card in hand this round; no BuyGains: the card is known) |
| D13 | Delayed payout `later(v, d)`: d1 zero if IsFinalRound, d2 zero if IsClimax; missions d0 | plan 11.5; IsFinalRound/IsClimax (economy §1.2–1.3) |
| D14 | Secret line with a cost priced `max(0, L)` | it resolves as an optional only-line (`offer_only_line`); plan 11.4 optional rule |
| D15 | Mandatory Influence Reduction events: least loss when no line > 0; other mandatory items `mc`/DRC | plan 11.4 (forced loss) / 11.4 (several options) |
| D16 | Least-loss ties random (shuffle, then first strictly best) | plan 11.4; GetBestInfluenceExchange's shuffled lists (influence §1.4) |
| D17 | Alliance recipient: first offered | plan 11.5; `windows/intrigue.py:644` (UNTRACED in the app) |
| D18 | Two-place sealed auctions bid on the first-place line | no precedent: rule 11.4 (no opponent model → no place estimate; the item offered is the first-place line) |
| D19 | Bid = largest `b` with `V + Sol(−b) > 0` | plan 11.4/11.5 |
| D20 | Mercenaries treated as a purchase with the same rule; specimen top-up cost included | plan 11.4; OQ-074 (a) |
| D21 | Mercenaries retreat = GetTroopsToRetreat(max) | OptionalRetreatAbility, Tactical Option (profile-combat §10) |
| D22 | Critical Moment: call the largest legal amount ≤ reservation; second place buys iff worth − call > 0 | plan 11.4 (losing calls cost nothing) |
| D23 | Subcommittee: in-turn Optional key at the best line value; decline when no key > 0; no deny/wait term | plan 11.5; post-action prompt (plan §4.2, engine-order §3) |
| D24 | Subcommittee opportunity added where the app adds HighCouncilValue; current-state affordability | HighCouncilSpaceAbility V, CorrinthCityRevealAbility E (board §1.4.10, imperium-a §2.8) |
| D25 | Mission join by line value; voluntary specimen top-up iff join + `Spec(−short)` > 0 | ReturnSpecimenAbility returns exactly the shortfall (immortality §3.4); the voluntary case: rule 11.4 optional payment |
| D26 | Mission collect = automatic Stage.SPACE; Imperial Reserve FSB(spice 1, Solari 2), spice on ties | engine-order state 400; strict keep-first (generic §0.2) |
| D27 | Desert Riding = third Hagga Basin option at `MakerHooksValue`, spice wins ties | Sietch Tabr hooks price (influence §5.2); DesertSpace E (board §1.4.18) |
| D28 | Rebuild: agree iff `Spi(−1) − BWV > 0` (never) | plan 11.5; BlowWallValue (influence §6.1); opponent denial 0 (rule 11.4) |
| D29 | Friends Everywhere: block (C) uses `max TB` | GetGainInfluenceValue block (C) (influence §1.1) |
| D30 | Eyes on Arrakis: CombatSpace + DeployUnitsAbility overlay on the five spaces | app space archetypes (Fremkit, Desert Tactics carry both) |
| D31 | Market Opening: TSMF `PersuasionCost` 7 for the Reserve entity while the discount is unused | the knapsack/AcquireValue read `PersuasionCost` (economy §5.3, §6) |
| D32 | Unlikely Allies: no term | legality is the engine's; no value reads requirements |
| D33 | Valued Informants goods added to PostValue | PostValue additive terms (influence §2.3) |
| D34 | CHOAM Escort goods added to the loaded Contract's completion value | ContractAbility::GetResourceValue (generic §16) |
| D35–D37 | Sponsored Research / Back Room Deal / Tleilaxu Offering terms (§4.6); the offering term added after the late cut | immortality §2.2, §2.10, §3.6 |
| D38 | Four-bonus pick `mc(TB)` | block (C) prices |
| D39 | In-line specimen top-up: the largest offered count | ReturnSpecimenAbility (immortality §3.4) |
| D40 | Forced windows with no positive candidate (secret pick, four bonus, Critical Moment 1st place, non-loss mandatory events) → DRC | plan 11.4; `DefaultRandomChoice` |
| D41 | Scouts-step draws use the DrawAbility price (CardDrawValue + BuyGains) | plan 11.5 (the app's draw price, unchanged) |
| D42 | Line values use the capped `Tr(n)`: a recruit that would need a top-up is valued as the app values a recruit from an empty supply | GetResourceValue troop cap (economy §3) |
| D43 | Prison Planet's marker and its loss risk unpriced | no precedent: rule 11.4 |
| D44 | To-Conflict mission troops gated at evaluation time (current Conflict), also at join time | D11 + plan 11.4 "as if received now" |
| D45 | CHOAM Escort Contract target: `mc` over equal values (random Contract) | plan 11.4 several options |
| D46 | Mission pieces join the visited space's value for the seat that would collect them (`MissionPiecesSpaceAbility`, a `DeferredAbility` so the generic `base(S)` is not counted twice); the face-down card is priced by kind only: Contract `KC`, Intrigue `Int` | contract term of `SpaceAbility::ValueForPlayer` (board §1.3, generic §6.1); "no generic space value" of `DesertSpaceDeferredAbility` (board §1.4.18); honesty (plan §4.8) for the generic card price |
| D47 | Lowest-track tie (Covert Operation 3) answered with the gain picker `G(f,1) + 100`, first strict best | `ChooseFactionInfluenceEvaluator` (influence §1.5), `GainAnyInfluenceAbility::Evaluate` (generic §9) |
| D48 | Contingencies' Agent pick = `RecallAgentAbility.Evaluate` (`GetRecallAgent ?? first`); the Into-the-Fray `conflict` Agent is reachable only as the fallback | Imperial Privilege's `RecallAgentAbility` (board §1.4.9, generic §14.1); `GetRecallAgent` skips a parent that is not a `WormSpace` |
| D49 | Tleilaxu Offering's join is worth `Spec(2)` (supply troops cost 0 by D9, payout `d = 0` by D13), so app_ai joins whenever it holds 2 supply troops and its token is below the third space, though the troops wait until the token gets there | arithmetic consequence of D9 + D13, recorded so the A/B can check it (no further precedent) |

## 8. OPEN

| # | Open point | What settles it |
|---|---|---|
| O1 | Critical Moment / Clear the Market can reveal Bloodlines cards (no app archetype): `A(c)` needs their synthetic archetypes | the Bloodlines generator (`docs/app-ai/bloodlines-cards.md`) |
| O2 | One `optional_trash` handler serves Scouts (Oversight, Water Discipline) and Immortality (research hexes c3r3/c7r5, Stitched Horror, Throne Room Politics) and Epic (Control the Spice) | stage 4 assigns one owner; the answer (TrashCustomAbility.Evaluate) is the same |
| O3 | Immortality-pool prices (`research_value`, `tleilaxu_value`, `specimen_value`, `GainResearchCustomAbility`, `GainTleilaxuInfluenceCustomAbility`, ReturnSpecimenAbility, `research_advance`) come from the parallel stage 2 port | that port's tests |
| O4 | Census coverage: no `scouts_lose_influence_to`, `scouts_return_specimens` or Immortality-pool item in the 60-game cell; only 3 Corrinth City offers | a Scouts + Immortality census with app_ai seats after stage 4 |
