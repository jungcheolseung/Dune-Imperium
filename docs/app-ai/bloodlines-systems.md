# app_ai app-style extension: Bloodlines systems

> Main-session decisions in `docs/app-ai-plan.md` §11.7 (2026-10-05) override this file where they differ.

Scope: the 9 Bloodlines Leaders (abilities and Signet Rings), Sardaukar Commanders and the 7 Skills, the 10 Navigation
cards and Steersman Y'rkoon's setup and choice, the 18 Tech tiles and every Tech Module decision, the Bloodlines board
changes, the new decision windows (`skill_choice`, `opponent_spy_move`, `opponent_unit_loss`, `optional_trash`,
`contract_intrigue_trash`, `intrigue_trigger_contract`, `leader_signet`, deep-cover `spy_placement`), the ids no census
game ever offered, and the automatic Bloodlines effects that must show up as valuation terms.
Out of scope (companion `docs/app-ai/bloodlines-cards.md`): Imperium, Intrigue, Twisted Intrigue, Conflict cards and
contract tokens, with their value fits and card abilities (Disruption Tactics, CHOAM Demands, Holy War's own box, …).

Binding rules: `docs/app-ai-plan.md` §3, §4, §11.3 (values), §11.4 (decisions), §11.5 (decisions already taken). This
file applies them item by item. Every judgement they do not dictate is in §10 "App-style decisions" (D-numbers).

## 0. Conventions and sources

- `SPEC/` = `assets/reference/dune-steam-app/dad97e2021144d45b5b4f022e07bd3b3/analysis/ai/spec/` (the Errata at the end
  of each file override its body). `R8` = the repository map `scratchpad/appai/repo-map/R8-bloodlines.md`.
- Content citations are `src/dune_imperium/…` file:line. `sardaukar.py` = `content/bloodlines/sardaukar.py`,
  `tech.py` = `content/bloodlines/tech.py`, `rtech.py` = `rules/tech.py`, `leaders.py` = `content/uprising/leaders.py`,
  `intrigue.py` = `content/uprising/intrigue.py`, `la.py` = `rules/leader_abilities.py`. `rules/` and `content/` are
  byte-identical to `f89f05f3` (`git diff --stat f89f05f3 HEAD -- src/dune_imperium/rules src/dune_imperium/content
  src/dune_imperium/core` is empty at worktree HEAD `b244047a`, and the worktree has no uncommitted change there), so
  R8's pointers hold; the ones relied on here were re-read. Pointers into `agents/app_ai/` are to HEAD `b244047a`
  (other stages are editing those files; e.g. `profile/combat.py` `_conflict_units`/`_garrison_units` are at
  `:201`/`:207` at HEAD).
- Profile methods are the snake_case names of `profile/core.py` (`troop_value`, `strength_value`, `spy_value`,
  `card_to_trash`, `gain_influence_value`, …). The Rise of Ix tech methods come from the parallel stage
  (`profile/tech.py`): `tech_tile_acquire_value` (`WormTechTilePlayable::AcquireValue`), `tech_acquire_targets`
  (`GetAcquireTechTileTargets`), `tech_tile_to_acquire` (`TechTileToAcquire`), `tech_options_mod` (`TechOptionsMod`),
  `buy_tech_value` (`BuyTechValue`), `tech_face_up_tiles`, `tech_negotiator_count`. Constants are `C.<Getter>` of
  `data/constants.py`.
- New elements are marked **NEW**: ability classes `worm.canis.abilities.AppStyle.Bloodlines.<Name>` (written
  `AS.<Name>` below), archetype short names `<Kind>Archetypes.AppStyle.<Name>`, the EntityType values `Commander`,
  `Skill`, `Navigation` (the app enum has none), the AcquireEffects values `IntrigueOrImperium`, `ShieldWall`,
  `Signet` (outside the app's `GetAcquireEffectsValue` jump table, so worth 0 there, like `PlaceSpy`/`Contract`; D16), and
  the AppStyle helpers of §1 (not app methods). Reused app classes are written with their full app name.
- Pseudo-code: `s.add(label, x)`, `s.multiply(label, m)` (summer), `UST(v, response)` = `UpdateSelectionTargets`
  (first strictly best kept, first call always sticks), `Answer(value, response)`; `make_choice` = plan §3.
  "Precedent" = the app class whose computation is copied.
- Census (decisions where the id was legal), written `bl / tech / promo`: R8's census ran before OQ-098 (Tech acquire
  icons in free order) was merged, so it has no `resolve_tech_acquire_effect`. I re-ran the same heuristic census on
  this worktree (30 seeds × CHOAM off/on per option, leaders rotated; scratch `blsys/census_bl.py`, output
  `blsys/census-bl.json`). Those numbers are used below. The census counts, per action id, the decisions in which
  that id was legal; it has no per-window decision totals, so a sum over ids that are offered together (a recall with
  its decline) over-counts decisions. The app_ai census itself cannot run Bloodlines yet (catalog `KeyError: 'skirmish_wild'`).

## 1. Shared app-style machinery

### 1.1 Units: Commanders and the Into the Fray Agent (D1)

The app counts every `WormUnit` in `GarrisonUnits`/`ConflictUnits` and filters troops with `OfType<WormTroop>`. A
Commander is "a 'troop' that's worth 2 strength in the Conflict" (`sardaukar.py:30-31`, `docs/rules/bloodlines.md` §3).

| app read | app-style value |
|---|---|
| `GarrisonUnits` | `troops_garrison + commanders_garrison` (port `_garrison_units`, `profile/combat.py:207`) |
| `ConflictUnits` | `PlayerState.units_in_conflict` (`core/player.py:229`: troops + sandworms + Commanders + `agent_in_conflict`) |
| `GarrisonTroops`, `HasUnitsDeployed<WormTroop>`, `ConflictTroops` | include Commanders; never the Into the Fray Agent (a unit, not a troop) |
| `GetNextTroops(n)`, `P.Supply…OfType<WormTroop>()`, the troop-supply cap of `GetResourceValue(Troops)` | supply **troops only**: a supply Commander cannot be recruited by a troop icon, only by the paid once-per-turn recruit (`docs/rules/bloodlines.md` §3, "supply의 Commander는 일반 수단으로 recruit할 수 없다" `[Bloodlines p. 4]`) |
| unit strength in `GetUnitsToDeploy` / `PotentialStrength` | troop 2, Commander 2 (`sardaukar.py:31`), Into the Fray Agent 2 or 3 (`rules/strength.py:34`) |

### 1.2 Commander and Skill prices (plan §11.5 "Commander")

```
CommanderUnitValue() = troop_value(1) + strength_value(COMMANDER_STRENGTH - 2)    # sardaukar.py:31; troop strength 2
                     = troop_value(1)                                              # GetResourceValue(amount 0) = 0
SkillValue(skill)    = Σ a.value_for_player(P, with) over abilities_of(skill)      # §2.2; one-time price (D2)
CommanderAcquireNet(skill, with) = CommanderUnitValue() + SkillValue(skill) - solari_value(commander_cost(me))
RecruitNet()         = CommanderUnitValue() - solari_value(commander_cost(me))     # re-buy: no Skill attached
commander_cost(me)   = rules/sardaukar.py:99 (2 − Honor Guard − Sardaukar High Command, floor 0)
```

### 1.3 Deploying with Commanders (D6)

`DeployUnitsAbility::Evaluate` = `GetUnitsToDeploy(units, max)` at 0.5 (`SPEC/generic-abilities.md` §11,
`SPEC/profile-combat.md` §8): units are taken strongest-first, stable in prompt order. All garrison units have strength
2, so the prompt order decides the kind. App-style prompt order: **Commanders first iff `me.skill_ids` is non-empty and
`me.commanders_conflict == 0`** (one Commander in the Conflict activates every Skill), else troops first.

- `N = units_to_deploy(garrison troops + garrison Commanders, max)`, with `max` = the largest legal `t + c` of our
  per-kind rooms (`rules/combat_deployment.py:131 deployment_rooms`). The port's count signature stays; only the
  unit list it stands for grows.
- Split N over the order above, each kind capped by its legal maximum (`legal_combat_deployments` `combat_deployment.py:238` /
  `legal_commander_deployments` `:269`). Emit the first kind's `deploy_troops(n)` /
  `deploy_commanders(n)` and store the other in `Memory.intents[("agent_effects", "deploy_split", round, seat)]`
  (plan §4.6); the follow-up deploys it before anything else. `withdraw_troops` / `withdraw_commanders`: never (plan §4.5).
- Reveal-turn Combat icon (`reveal_turn.py:462`): the same `DeployUnitsAbility` key at 0.5 in the post-Reveal list
  (D61).

### 1.4 Retreat and forced loss (D7, D8)

- **Retreat** (units return to the garrison): troops first; a Commander only when no troop is left in the Conflict
  (`DesertScoutsAbility` retreats `OfType<WormTroop>().Take(1)`, `SPEC/leaders.md` §8.1; plan §11.5). Applies to
  `retreat_leader_troops(count, commanders)`, `retreat_leader_commander`, and the card retreats of the companion file.
  The Into the Fray Agent cannot retreat (engine).
- **Forced loss** (victim side, plan §11.4 "강제 손실"): lose the option with the smallest `LoseUnitValue`; ties at
  random from the agent RNG.

```
LoseUnitValue(zone, kind):
    garrison troop       -> troop_value(1)                                   # GetResourceValue(Troops, 1)
    garrison Commander   -> CommanderUnitValue()                             # = troop_value(1)
    Conflict troop       -> strength_value(2)
    Conflict Commander   -> strength_value(2)
                            + (me.commanders_conflict == 1 ? Σ ActiveSkillLoss(s) for s in me.skill_ids : 0)
    Chani, Conflict zone -> value - TacticsReward(1)                         # §4.1; the loss advances her track
ActiveSkillLoss(s) = Canny/Fierce/Loyal: their SkillValue now; Charismatic/Driven/Hardy: SkillValue if the seat has
                     not revealed this round (the bonus is paid when the Reveal begins), else 0; Desperate: 0
```

### 1.5 Deep-cover posts (plan §11.5 question)

`WormObservationPost::PostValue` reads no other seat's Spy or Agent (`SPEC/profile-influence-uprising.md` §2.3:
"Nothing here checks opponents' spies or agents"). `GetBestPost`/`GetPostSelection` rank whatever list they are given.
**App-style reading (D50): a post that already holds an opponent's Spy is valued exactly like an empty post. No new
term.** The shared post gives this seat the same Gather Intelligence and infiltration uses, and the opponent's Spy stays.
The existing `windows/uprising.py:spy_placement` / `common.spy_answer` already feed the engine's legal posts (which
exclude only posts with an own Spy, `rules/spy_moves.py:306`) to `PlaceSpyEvaluator`. Implementation note:
`AppContext.post_owner` returns one seat, but a deep-cover post can hold several seats' Spies. Own-Spy tests must read
`me.spy_post_ids`, as every current caller does. The "free post" tests (Special Mission's `CanDeployOnCircle`) stay
correct, because a shared post is not free.

### 1.6 Private information (plan §11.5)

| item | who sees it | AppContext rule |
|---|---|---|
| Navigation slots (`PlayerView.navigation_slots`, `core/observation.py:140`) and box | owner only (box: nobody) | own seat only; opponents never value Y'rkoon's Navigation |
| Secret Project (`observation.py:142`); candidates (`observation.py:616`, setup frame only) | owner only | own seat only; others see `has_secret_project`; the two unchosen bottom tiles are forgotten (OQ-041) |
| Glowglobes' peeked top card (`observation.py:134`) | owner | ignored (information is worth 0, plan §11.4) |
| Twisted deck order / Intrigue deck estimate | — | Twisted cards excluded from the Intrigue-deck composition (plan §11.5, OQ-097) |

### 1.7 Icon grants and cost changes

- **Placement.** `AgentAbility::Evaluate` iterates the engine's `ValidSpaces` (`SPEC/generic-abilities.md` §2.1). Here
  that is our legal `agent_turn` targets, which already include every space a grant opens: Mohiam's Spy icon on every
  card, Servo-Receivers' faction icons on the Signet Ring, Liet's ignored Sietch Tabr requirement. Each newly
  reachable space is valued like any other (card value + Σ space-ability values), so a permanent grant needs no term
  of its own.
- **Icon counts** (`DeckAgentIcons`, `WormImperiumPlayable::AcquireValue` "New Icons", contract `AgentIconsMod`): read
  the owner's card `IconList` as printed ∪ permanent grants: Mohiam adds `Spy` to every card; Servo-Receivers adds
  `Emperor, SpacingGuild, BeneGesserit, Fremen` to `ImperiumArchetypes.BaseSet.SignetRing` (D40).
- **IconGrantValue** (for a decision that *grants* icons; no leader decision does, the turn-scoped card grants are in
  the companion file): `max(0, max_c best_s∈Valid(c ∪ grant) AgentEval(c, s) − max_c best_s∈Valid(c) AgentEval(c, s))`
  over hand cards `c`, with `AgentEval` = the `AgentAbility::Evaluate` total.
- **Costs.** Duncan: Swordmaster's runtime `SolariCost` − 2, floor 0 (`rules/agent_turn.py:1000`), in
  `space_solari_cost` (`abilities/generic.py:273`, the app's `DecreaseInitialCost` precedent) (D35). Navigation
  Chamber: every legal `agent_turn(discount=spice|solari)` variant is its own target with the space cost reduced by 1
  (`agent_turn.py:941`). `SolariDiscount` −1 or **NEW** `SpiceDiscount` −1 feed `SpaceAbility` "Space … Cost" and
  `CanAgentAbilityBePlayedWithSpace`. The first strictly best variant wins (D60).

## 2. Sardaukar Commanders and Skills (R8 §3)

### 2.1 Archetypes

| short | EntityType | attributes (source) | WormAbilityIDs |
|---|---|---|---|
| `CommanderArchetypes.AppStyle.SardaukarCommander` | Commander NEW | `Strength` 2 (`sardaukar.py:31`), `SolariCost` 2 (`:29`), `CardCount` 7 (`:24`) | () — the purchase lives on the spaces (§6), the re-buy on the playmat |
| `SkillArchetypes.AppStyle.Canny` | Skill NEW | `CardCount` 2 (`:33`), `Strength` 2 (`:82`) | `AS.CannySkillAbility` |
| `SkillArchetypes.AppStyle.Charismatic` | Skill | `CardCount` 2, `Persuasion` 1 (`:86`) | `AS.SkillRevealAbility` |
| `SkillArchetypes.AppStyle.Desperate` | Skill | `CardCount` 2, `Strength` 3 (`:89`) | `AS.DesperateSkillAbility` |
| `SkillArchetypes.AppStyle.Driven` | Skill | `CardCount` 2, `Spice` 1 (`:91`) | `AS.SkillRevealAbility` |
| `SkillArchetypes.AppStyle.Fierce` | Skill | `CardCount` 2, `Strength` 1 (`:97`), +1 with an opposing sandworm (`:98`) | `AS.FierceSkillAbility` |
| `SkillArchetypes.AppStyle.Hardy` | Skill | `CardCount` 2, `Troops` 1 (`:102`) | `AS.SkillRevealAbility` |
| `SkillArchetypes.AppStyle.Loyal` | Skill | `CardCount` 2, `Strength` 2 (`:108`), `InfluenceRequirements` {Emperor: 3} (`:109`) | `AS.LoyalSkillAbility` |

Skill tiles have no `AcquireValue`: they are never bought, only chosen (§2.3).

### 2.2 Classes

```
AS.SkillRevealAbility : TriggeredAbilities.TriggeredAbility       # timing Reveal; automatic, no Evaluate
  value_for_player(P, with):                                       # precedent RevealAbility §3.1 ValueAttributes
      for attr in (Spice, Persuasion, Troops): n = Owner.int_attr(attr)
          if n > 0: s.add("Skill " + attr, resource_value(attr, n))   # Persuasion: arc value + buy gains

AS.CannySkillAbility : TriggeredAbility                            # timing Combat (5); automatic
  value_for_player(P, with):
      if AgentOnLandsraad(with): s.add("Canny", strength_value(Owner.Strength))
  AgentOnLandsraad(with) = an own Agent on a space with AgentIcon Pentagon, or the space in `with` is Pentagon

AS.FierceSkillAbility : TriggeredAbility                           # timing Combat
  value_for_player(P, with):
      n = 1 + (1 if any(op.sandworms_conflict > 0 for op in opponents) else 0)       # sardaukar.py:97-98
      s.add("Fierce", strength_value(n))

AS.LoyalSkillAbility : TriggeredAbility                            # timing Combat
  value_for_player(P, with):
      if me.influence.emperor >= 3: s.add("Loyal", strength_value(2))               # sardaukar.py:108-109

AS.DesperateSkillAbility : ActivatedAbilities.DeferredAbility      # timing Reveal; SelectionMode Optional
  meets_cost: me.commanders_conflict >= 1                          # rules/sardaukar.py:678
  value_for_player(P, with): s.add("Desperate", strength_value(3))
  evaluate(P, request):                                            # precedent DeviousStrengthAbility (leaders §3.1), D9
      reason = "Last Round" if is_final_round() else None
      if reason is None:
          (lb, ub) = conflict_posture_bounds(); ci = current_conflict_interest().sum
          mine = est_strength().sum; opp = [est_opponent_strength(o).sum for o in opponents]
          if   ci >= ub and any(abs(mine - x) < 5 for x in opp): reason = "High conflict interest"
          elif ci >= lb and any(abs(mine - x) < 2 for x in opp): reason = "Mid conflict interest"
          else: return Answer(0.0, None)
      return Answer(100.0, ((skill_id,),), "Desperate | " + reason)
```

`strength_value` is `GetResourceValue(Strength, n)`, which is 0 while `ConflictUnits == 0` and `RemainingAgents <= 1`
(`SPEC/profile-economy.md` §3). So a Strength Skill is worth nothing late in a round when the seat has no unit fighting.
This follows mechanically from the app's own formula.

```
AS.AcquireCommanderAbility : DeferredAbility                       # owner = one of the six Commander spaces (§6)
  timing Agent; SelectionMode Explicit (the pending icon blocks finish_agent_turn, OQ-095); never immediate
  value_for_player(P, with=[card]):                                # D4
      if Owner.ref not in state.sardaukar_commander_space_ids: return s
      cost = commander_cost(me)
      if not can_agent_ability_be_played_with_space(Owner, Solari, cost): return s     # WaterOfLife precedent
      best = max(CommanderAcquireNet(k, [Owner]) for k in eligible face-up Skills) or CommanderAcquireNet(None)
      s.add("Sardaukar Commander", max(0.0, best))
  evaluate(P, request):                                            # precedent AcquireTechAbility::Evaluate (D3)
      for k in request skills (face-up order) or [None]: UST(CommanderAcquireNet(k, [Owner]), k)
      if not (stored.value > 0): UST-replace with Answer(0.5, ())  # empty answer = decline
  -> acquire_sardaukar_commander(skill_id=k) | acquire_sardaukar_commander() | decline_sardaukar_commander

AS.RecruitCommanderAbility : DeferredAbility                       # owner = the playmat custom row; timing None
  SelectionMode Optional; meets_cost: our engine offers recruit_sardaukar_commander (rules/sardaukar.py:604)
  evaluate(P, request):                                            # D5: rule 11.4 net; 100 = Mercenaries' ordering value
      net = RecruitNet()
      if net <= 0: return Answer(0.0, None)
      if DeployWindowOpen(): return Answer(100.0, (), "Recruit Commander | before deploy")
      return Answer(net, (), "Recruit Commander")
  DeployWindowOpen() = own Agent turn whose deploy key is still unused and has Commander room
                       (combat space or pending Combat icon), or a Reveal-turn Combat icon
```

### 2.3 Windows and ids

| window: id (args) | census bl/tech/promo | answer |
|---|---|---|
| agent_effects: `acquire_sardaukar_commander(skill_id?)` / `decline_sardaukar_commander` | 259/276/241 ; 1536/1659/1654 | `AS.AcquireCommanderAbility` (E) in the post-action list |
| agent_effects, reveal: `recruit_sardaukar_commander` | 1515/1631/1269 ; reveal 125/117/60 | `AS.RecruitCommanderAbility` (O) in the post-Agent / post-Reveal list |
| agent_effects: `deploy_commanders(count)` / `withdraw_commanders(count)` | 2124/2313/1914 ; 845/930/797 | §1.3 split; withdraw never |
| reveal: `deploy_troops` / `deploy_commanders` (Combat icon) | 38/35/38 ; 14/7/14 | `DeployUnitsAbility` key at 0.5, §1.3 split (D61) |
| reveal: `trash_skill_for_strength(skill_id)` | 113/132/113 | `AS.DesperateSkillAbility` (O) |
| reveal: `retreat_leader_commander` (Lady Amber's Desert Scouts) | 103/227/156 | `DesertScoutsAbility::Evaluate` unchanged (1.0 iff `troops_to_retreat(1) > 0`); its Cost counts Commanders (§1.1); the unit is the existing troop retreat id while `troops_conflict > 0`, else `retreat_leader_commander` (plan §11.5) |
| skill_choice: `choose_skill(skill_id)` (bank Commander from Sardaukar Standard, `rules/card_trash.py:131`) | 3 / 33 (Plasteel frames included; `decline_skill`, legal only there, 32) / 3 | forced: `make_choice` over `SkillValue` (plan §11.4 "여러 보기 중 하나": shuffle, > 0, stable descending sort, first, so ties are random); nothing > 0 → `DefaultRandomChoice` |
| skill_choice: `choose_skill` / `decline_skill` (Plasteel Blades, `rules/sardaukar.py:115`) | tech: `decline_skill` 32 | `AS.PlasteelBladesAbility` (§3.3) |
| skill_choice: `resolve_commander_without_skill` | 0 (never) | offered alone (`rules/sardaukar.py:531`): the agent takes the single legal action |

## 3. Tech Module (R8 §11, §2.14; plan §11.3, §11.5)

### 3.1 The Rise of Ix machinery and where our acquisition model differs

The faithful ports (`SPEC/rix-tech.md` §3, §4, §6.1) are used unchanged except for the acquisition model
(`SPEC/rix-tech.md` §1.3):

| app machinery | adaptation (all inside `tech_face_up_tiles` / `tech_acquire_targets`; the valuation is untouched) |
|---|---|
| `GetAcquireTechTileTargets`: face-up tops of stacks 1, 2, 3, affordable iff `SpiceCost <= discount + Max(Spice, allowSolari ? Solari : 0) + negotiators` | candidates = face-up tops in stack order (`rtech.py:218`), then the own Secret Project (`rtech.py:294`); affordable iff `tech_cost(me, t, discount, secret=(t is own Secret Project)) <= me.spice` (`rtech.py:196`) and, for Advanced Data Analysis, the seat has a Spy on the board (it has no `acquire_tech` variant otherwise, `rtech.py:313`, `:346`). The High Council seat's −1 (`tech.py:20`) replaces the negotiators (both automatic, owner-wide discounts; `tech_negotiator_count()` stays 0). The Tech Discount icon is `TechDiscount` 1 (`tech.py:23`); the Secret Project's −1 (`rtech.py:90`) is per tile; floor 0. `allowSolari` is always false (D12) |
| placement value of a Landsraad space before our engine offers anything | same list with the seat assumed when the space being valued is High Council: its first visit grants the seat before the tile is bought (`[Bloodlines p. 7]` example, `docs/rules/bloodlines.md` §5) |
| `WormTechTilePlayable::AcquireValue` (§3.1), `TechTileToAcquire` (§4.2), `TechOptionsMod` (§4.3), `BuyTechValue` (§4.4) | unchanged, over the synthetic archetypes of §3.2. `MachineCultureTechValueMod` never fires (no Machine Culture). `NegotiateTechValue` is unused (no negotiators) |
| Acquire Tech on the Tech Negotiation / Dreadnought spaces, Ixian Engineer | **Landsraad visit** ("may", `[Bloodlines p. 7]`): `ActivatedAbilities.RiseOfIx.AcquireTechAbility` (TechDiscount 0) appended to the 5 Landsraad spaces (§6; Dreadnought-space precedent, rix-tech §6.7). Explicit, never immediate, so it sits in the post-action list. Its V = `BuyTechValue(0, false)`. Its E = §6.1: the first strictly best tile > 0, else the empty answer at 0.5 → `decline_tech` |
| `AcquireTechAbilityDiscount1` (custom ability) | **Tech Discount icon** (Battlefield Research, Rapid Engineering; `tech_acquisition` window): same class. Our engine forces the purchase when a tile is affordable (OQ-057 (9)). When E answers empty and `decline_tech` is not legal, buy `TechTileToAcquire(1)`'s tile, the first by value in stack order even at value 0 (rix-tech §4.2) (D13). `decline_tech` alone (nothing affordable) is auto |
| — | **Kota's Secret Project**: an extra candidate in every offer (above) |
| — | **Advanced Data Analysis** prerequisite: `acquire_tech(advanced_data_analysis, post_id)` has one variant per own Spy (`rtech.py:313`). `post_id` = `recall_spy(own spies)`, the spy on the worst post (`RecallSpyEvaluator` precedent, D14) |
| acquire effects run immediately and forced (`AcquireTechTile` §7.2) | OQ-098: our engine queues them (`rtech.py:141`) and offers `resolve_tech_acquire_effect` in any order. App-style: app_ai resolves every owed key as a follow-up right after the purchase, before any other source, in the engine's key order `acquire_effect_keys` (`tech.py:141-160`) (D15). Each key is answered by the class in the table below |
| tile activations: Optional deferred abilities offered in the turn prompts (§7.4) | `flip_tech` joins the turn-start prompt (`turn`), the post-Agent list and the post-Reveal list as a source valued by the tile's E (D25) |

Acquire-effect keys (`rtech.py:95 tech_acquire_effect_arguments`, applied at `rtech.py:514`):

| key (tiles) | app class (precedent) | answer |
|---|---|---|
| `solari` (Plasteel Blades), `troops` (Forbidden Weapons, Ornithopter Fleet, Rapid Dropships), `intrigue` (Self-Destroying Messages), `victory_points` (Sardaukar High Command) | generic acquire actions, no question (Price Is No Object, Chaumurky, Flagship) | resolve |
| `cards` (Delivery Bay) | `ConflictAbilities.BaseSet.DrawImperiumAcquiredAbility` (Spaceport) | resolve |
| `contracts` (CHOAM Transports) | generic `Contract` action (Interstellar Trade's acquire) | resolve; then `contract_market` → existing handler (`GetBestContract`, forced) |
| `influence` (Glowglobes, Navigation Chamber) | `ConflictAbilities.BaseSet.MemocordersAcquiredAbility` E: per track `gain_influence_value(F, 1).sum + 100`, first strictly best in `FACTIONS` order | `faction` = that track |
| `intrigue_or_card` (Gene-Locked Vault) | `AS.GeneLockedVaultAcquiredAbility` (§3.3) | `choice` |
| `shield_wall` (Forbidden Weapons) | `ChooseBlowWall` (`should_blow_wall()`; `SPEC/profile-influence-uprising.md` §6.4) | `destroy_shield_wall=True` iff legal and `should_blow_wall()`, else the plain key |
| `signet` (Servo-Receivers) | `AS.ServoReceiversAcquiredAbility` (no E) | resolve; then `leader_signet` (§7) |
| `trash` (Planetary Array) | `ActivatedAbilities.DisposalFacilityAcquiredAbility` (identical acquire effect) | resolve; then `optional_trash` (§7) |
| `spy_0`, `spy_1` (Spy Drones) | generic `PlaceSpy` action (deep cover) | resolve; then `spy_placement` → `spy_answer` (§1.5). A second Spy with an empty supply recalls the worst-post Spy, which may be the one just placed |

### 3.2 Tile archetypes (plan §11.3: `AcquireValue = 2 × SpiceCost`; `EarlyMod`/`LateMod` per plan §11.7: the RoI tile with the nearest lasting ability first, else the one with an identical acquire effect, else none)

Mods per plan §11.7 (`SPEC/rix-tech.md` §1.2 nearest column). Nearest lasting ability: Planetary Array = Windtraps
(win-Conflict trigger; EarlyMod 1.5, LateMod 0.5), Self-Destroying Messages = Minimic Film (Reveal +1 Persuasion; 1.5 /
none), Delivery Bay = Disposal Facility (6+ Persuasion condition; 1.5 / 0.0), Rapid Dropships = Training Drones (flip to
deploy; 1.1 / 0.75), CHOAM Transports = Holtzman Engine (conditional Endgame VP; 1.2 / none). Identical acquire effect
only: Glowglobes and Navigation Chamber = Memocorders (no mods); Sardaukar High Command = Flagship (no mods). Delivery Bay (1 of Spaceport's 2 draws) and Ornithopter Fleet (2 troops
vs Invasion Ships' special-cased 4) are not identical. All tiles: `EntityType` TechTile, `Tags` () (tile tags have no
4-player reader: `CountCardTags` counts Imperium cards and hand Intrigues only).

| our `tech_id` (cost line) | short `TechTileArchetypes.AppStyle.*` | SpiceCost | AcquireValue | Early/Late | AcquireEffectList | WormAbilityIDs (order) |
|---|---|---:|---:|---|---|---|
| advanced_data_analysis (`tech.py:173`) | AdvancedDataAnalysis | 3 | 6.0 | – | () | `AS.AdvancedDataAnalysisAbility` |
| choam_transports (`:180`, contract `:183`) | CHOAMTransports | 6 | 12.0 | 1.2 / – (Holtzman Engine) | (Contract) | `AS.CHOAMTransportsAbility`, `AS.AcquireEffectsBonusAbility` |
| delivery_bay (`:188`, draw `:191`) | DeliveryBay | 3 | 6.0 | 1.5 / 0.0 (Disposal Facility) | (Imperium) | `ConflictAbilities.BaseSet.DrawImperiumAcquiredAbility`, `AS.DeliveryBayAbility` |
| forbidden_weapons (`:196`, wall `:198`, troop `:199`) | ForbiddenWeapons | 2 | 4.0 | – | (Troop, ShieldWall) | `AS.ForbiddenWeaponsAbility` |
| gene_locked_vault (`:204`, `:207`) | GeneLockedVault | 2 | 4.0 | – | (IntrigueOrImperium) | `AS.GeneLockedVaultAcquiredAbility`, `AS.GeneLockedVaultAbility` |
| glowglobes (`:212`, `:215`) | Glowglobes | 2 | 4.0 | – (Memocorders) | (AnyRank) | `ConflictAbilities.BaseSet.MemocordersAcquiredAbility`, `AS.GlowglobesAbility` |
| navigation_chamber (`:220`, `:222`) | NavigationChamber | 5 | 10.0 | – (Memocorders) | (AnyRank) | `ConflictAbilities.BaseSet.MemocordersAcquiredAbility`, `AS.NavigationChamberAbility` |
| ornithopter_fleet (`:227`, troops `:230`) | OrnithopterFleet | 4 | 8.0 | – | (Troop, Troop) | `AS.OrnithopterFleetAbility` |
| panopticon (`:232`) | Panopticon | 5 | 10.0 | – | () | `ActivatedAbilities.Uprising.PlaceSpyRevealAbility`, `AS.PanopticonAbility` |
| planetary_array (`:236`, trash `:238`) | PlanetaryArray | 2 | 4.0 | 1.5 / 0.5 (Windtraps) | (Trash) | `ActivatedAbilities.DisposalFacilityAcquiredAbility`, `AS.PlanetaryArrayAbility`, `AS.AcquireEffectsBonusAbility` |
| plasteel_blades (`:243`, Solari `:245`) | PlasteelBlades | 3 | 6.0 | – | (Solari ×4) | `AS.PlasteelBladesAbility` |
| rapid_dropships (`:250`, troops `:253`) | RapidDropships | 4 | 8.0 | 1.1 / 0.75 (Training Drones) | (Troop, Troop) | `AS.RapidDropshipsAbility` |
| sardaukar_high_command (`:258`, VP `:261`) | SardaukarHighCommand | 7 | 14.0 | – (Flagship) | (VP) | `AS.SardaukarHighCommandAbility` |
| self_destroying_messages (`:266`, Intrigue `:269`) | SelfDestroyingMessages | 4 | 8.0 | 1.5 / – (Minimic Film) | (Intrigue, Intrigue) | `AS.AcquireEffectsBonusAbility`, `TriggeredAbilities.RiseOfIx.MinimicFilmAbility` |
| servo_receivers (`:276`, signet `:279`) | ServoReceivers | 2 | 4.0 | – | (Signet) | `AS.ServoReceiversAcquiredAbility`, `AS.ServoReceiversAbility` |
| spy_drones (`:284`, spies `:287`) | SpyDrones | 5 | 10.0 | – | (PlaceSpy, PlaceSpy) | `AS.SpyDronesAbility`, `AS.AcquireEffectsBonusAbility` |
| suspensor_suits (`:292`) | SuspensorSuits | 3 | 6.0 | – | () | `AS.SuspensorSuitsAbility` |
| training_depot (`:298`) | TrainingDepot | 1 | 2.0 | – | () | `AS.TrainingDepotAbility` |

Valued by `GetAcquireEffectsValue` (`SPEC/profile-economy.md` §9): Troop, Solari, VP, AnyRank. Worth 0 there: Imperium,
Intrigue, Trash, PlaceSpy, Contract and the NEW values. The specific bonuses of §3.3 add Intrigue, Trash, PlaceSpy and
Contract (plan §11.5). They also price `IntrigueOrImperium`, `ShieldWall`, `Signet` and Advanced Data Analysis' Spy
loss. `Imperium` (Delivery Bay's draw) stays unpriced, as Spaceport's two draws are in the app (D18).

Worked values (Hard, Supplied abundance, Mid arc unless stated; `MinimumAcquireValue` 1.2/1.7/2.2):
Training Depot Mid 2.0, Late 0 (2.0 < 2.2), Early 0 (no EarlyMod). Self-Destroying Messages 8.0 + 2 × 2.5 = 13.0.
Sardaukar High Command 14.0 + `victory_point_value(1)` 6.0 = 20.0. Planetary Array Early with `TrashMod` −1:
(4.0 + 2.75 − 1.0) × 1.5 = 8.625, Late (same terms) × 0.5 = 2.875. Spy Drones, no Spy out: 10.0 + 2 × 1.66 = 13.32. Advanced Data Analysis
with one Spy out: 6.0 − 1.66 × 0.67 = 4.888.

### 3.3 Tile ability classes

```
AS.AcquireEffectsBonusAbility : WormAbilityDefinition              # SAV only (plan §11.5, D17)
  specific_acquire_value(P):
      for e in Owner.AcquireEffectList:                            # each entry priced on the current state
          Intrigue -> s.add("Acquire Intrigue", intrigue_value())                     # ChaumurkyAbility SAV
          Trash    -> s.add("Acquire Trash", trash_card_value() + trash_mod())        # DisposalFacilityAcquired V
          PlaceSpy -> s.add("Acquire Spy", spy_value().sum)                           # PlaceSpyAbility V
          Contract -> s.add("Acquire Contract", gain_contract_value().sum if contract options exist
                                                 else solari_value(2))                # GainContractAbility V

AS.AdvancedDataAnalysisAbility : DeferredAbility                   # Flip: draw an Intrigue (rtech.py:694)
                                                                   # tile activations are Optional deferred abilities (rix-tech §1.3, §7.4)
  SelectionMode Optional; meets_cost: tile owned and not flipped this round
  specific_acquire_value(P): s.add("Spy to box", -spy_value().sum)                    # D22
  evaluate(P, r): Answer(100.0, (), "Advanced Data Analysis | always flip")           # D23 (Chaumurky "always play")

AS.SpyDronesAbility : DeferredAbility                              # Flip: 1 Solari (+ optional trash after a recall)
  SelectionMode Optional; evaluate: Answer(100.0, ())                                 # D23
  the trash follow-up is `optional_trash` (§7)

AS.RapidDropshipsAbility : DeferredAbility                         # Agent turn Flip: Combat icon (rtech.py:658)
  timing Agent; SelectionMode Optional
  evaluate(P, r):                                                  # D24, precedent TrainingDronesAbility (rix-tech §8.14)
      if this turn's Agent space is a Combat space or a Combat icon was already granted this turn:
          return Answer(0.0, None)                                 # the icon adds nothing: the garrison room stays 2
                                                                   # however many icons ("[Bloodlines pp. 5, 12]", bloodlines.md §4)
      if units_to_deploy(garrison units, 2) > 0: return Answer(100.0, ())
      return Answer(0.0, None)

AS.ForbiddenWeaponsAbility : DeferredAbility                       # Reveal, must choose (rtech.py:738/830)
  timing Reveal; SelectionMode Explicit
  evaluate(P, r):                                                  # forced loss, D26
      for each offered choose_tech_strength(faction F[, alliance_recipient]) in Faction order:
          v = strength_value(3) + gain_influence_value(F, -1).sum                     # bare action: F term 0
      trash: v = spice_value(-me.spice) - HeldTileValue(forbidden_weapons)            # spice 0: 0 - …
      best = first strictly best (strength rows, then trash)
      return Answer(best.v if best.v > 0 else 1.0, best)                              # RecallSpyIntelligence 1.0
      alliance_recipient: the first offered (plan §11.5 precedent "먼저 제시된 이")
  specific_acquire_value(P):                                       # ShieldWall, D20
      if state.shield_wall_present and should_blow_wall(): s.add("Shield Wall", blow_wall_value().sum)

AS.GeneLockedVaultAcquiredAbility : TechTileAcquiredAbility         # Intrigue OR draw
  specific_acquire_value(P): s.add("Acquire Intrigue", intrigue_value())             # D19
  evaluate(P, r):
      UST(intrigue_value(), choice=intrigue)                                         # GainIntrigueAcquiredAbility V
      UST(card_draw_value_with_buy_gains(), choice=card)                             # DrawImperiumAcquiredAbility V
AS.GeneLockedVaultAbility: passive steal protection, no AI hook (an opponent-side effect, plan §11.4 → 0)

AS.ServoReceiversAcquiredAbility : TechTileAcquiredAbility          # use the Leader's Signet Ring once
  AlwaysRunImmediately; no Evaluate (the leader_signet window answers)
  specific_acquire_value(P):                                       # D21, precedent AgentAbility §2.2(d)
      W = [this turn's Agent space] if the seat is in its own Agent turn with an Agent placed, else []
                                                                   # OQ-062 (b): "this turn" = the Agent turn in progress
      for a in leader abilities of type SignetAbility: s.merge(a.value_for_player(P, W))    # Y'rkoon: none → 0
  # With W = [] each Bloodlines signet V takes its no-space branch: Fedaykin skips the affordability gate (WaterOfLife
  # does the same with no space, leaders §6.1); Into the Fray 0 (no Agent to send); Judge of the Change 0 (no icon);
  # Smuggle Spice PlaceValue takes its "otherwise" branch; Corrino Liaison, Listeners, Reverse Engineering ignore W.
AS.ServoReceiversAbility: passive (Signet Ring icons, §1.7), no AI hook

AS.PlasteelBladesAbility : TriggeredAbility                        # on every Commander recruit: trash → extra Skill
  evaluate(P, r)  [skill_choice with decline_skill]:               # D10
      k* = first strictly best SkillValue over offered Skills
      v  = SkillValue(k*) - HeldTileValue(plasteel_blades)
      return Answer(v, ((k*,),)) if v > 0 else Answer(0.0, None)    # Optional → decline_skill

AS.PanopticonAbility: Reveal troop (automatic) and Endgame influence, no AI hook. The Reveal Spy is the reused
  `PlaceSpyRevealAbility` (E = SpyValue, Explicit; Covert Operation precedent), then `spy_placement` (all posts,
  not deep cover, rtech.py:817).
AS.CHOAMTransportsAbility, AS.PlanetaryArrayAbility, AS.SuspensorSuitsAbility, AS.DeliveryBayAbility,
AS.TrainingDepotAbility, AS.GlowglobesAbility, AS.NavigationChamberAbility, AS.OrnithopterFleetAbility,
AS.SardaukarHighCommandAbility: TriggeredAbility, no hook; their valuation terms are in §9.

HeldTileValue(t) = AcquireValue(t) x [EarlyMod(t,1.0), 1.0, LateMod(t,1.0)][game_arc()]   # NEW helper, D11 as revised by plan §11.7
```

### 3.4 Tech windows and ids

| window: id (args) | census (tech) | answer |
|---|---|---|
| agent_effects: `acquire_tech(tech_id[, post_id])` / `decline_tech` | 490 / 2242 | Landsraad `AcquireTechAbility` (E) in the post-action list, §3.1 |
| agent_effects, tech_acquisition: `resolve_tech_acquire_effect(effect, tech_id[, faction\|choice\|destroy_shield_wall])` | 974 ; 15 (absent from R8's census, post-OQ-098) | follow-up right after the purchase, §3.1 key table |
| tech_acquisition: `acquire_tech` / `decline_tech` (card Tech Discount; Combat for Battlefield Research) | 42 / 24 | `AcquireTechAbilityDiscount1` E, D13 |
| turn, agent_effects, reveal: `flip_tech(tech_id)` | turn 99, agent_effects 760, reveal 0 (legal there for Advanced Data Analysis and Spy Drones, `rtech.py:658`, but never offered in the census) | the tile's activation E (§3.3) as a source in the turn-start prompt / post-action lists |
| reveal: `choose_tech_strength(faction, alliance_recipient)` / `choose_tech_trash` | 372 / 372 | `AS.ForbiddenWeaponsAbility` (Explicit) |
| reveal: `place_tech_spy` | 347 | `PlaceSpyRevealAbility` (Explicit, `spy_value`) |
| agent_effects, leader_signet: `trash_leader_tech(tech_id)` / `gain_leader_signet_spice` | 72/138 ; 2/2 | Kota's `AS.ReverseEngineeringSignetAbility` (§4.9) |
| tech_secret_project: `choose_secret_project(tech_id)` | 15 | `AS.SecretProjectAbility` (§4.9) |

## 4. Leaders (R8 §8)

The app AI picks leaders at random (`SPEC/leaders.md` §1), so the only decisions are the in-game abilities. A
`SignetAbility`'s V reaches the AI only when the AI values a Signet Ring placement (`AgentAbility` §2.2(d), with
`with = [space]`). Its E answers the prompt (plan §4.2 stages). Explicit signets force the post-Agent prompt. Optional
ones are used only when their E is > 0 and the best (D29). Archetypes use the app's `Leader` suffix where an app card
shares the name (`LeaderArchetypes.Uprising.GurneyHalleckLeader` precedent; R8 open point 8). Attributes: `EntityType`
Leader and `WormAbilityIDs`, the only AI-read attributes of the app's leader archetypes (`Name`/`SetList` are not read).

| our `leader_id` (`leaders.py`) | short `LeaderArchetypes.AppStyle.*` | WormAbilityIDs | signet SelectionMode / immediacy |
|---|---|---|---|
| chani (`:167`) | ChaniLeader | `AS.TacticianAbility`, `AS.FedaykinManeuverSignetAbility` | Optional |
| count_hasimir_fenring (`:177`) | CountHasimirFenring | `AS.AssassinAbility`, `AS.CorrinoLiaisonSignetAbility` | Optional |
| duncan_idaho (`:186`) | DuncanIdahoLeader | `AS.GinazSwordmasterAbility`, `AS.IntoTheFraySignetAbility` | Optional |
| esmar_tuek (`:195`) | EsmarTuekLeader | `AS.TueksSietchLeaderAbility`, `AS.SmuggleSpiceSignetAbility` | Explicit (mandatory either-or, `la.py:1186`) |
| gaius_helen_mohiam (`:204`) | GaiusHelenMohiam | `AS.ClandestineAbility`, `AS.ListenersSignetAbility` | Optional |
| piter_de_vries (`:213`) | PiterDeVriesLeader | `AS.TwistedGeniusAbility`, `ActivatedAbilities.Uprising.WarmasterAbility` | Explicit, AlwaysRunImmediately (automatic, `la.py:515`) |
| steersman_y_rkoon (`:223`) | SteersmanYrkoonLeader | `AS.StrangeFormAbility`, `AS.HungryForSpiceAbility`, `AS.PlotCourseAbility` | no SignetAbility (no Signet Ring card, `leaders.py:232`) |
| liet_kynes (`:236`) | LietKynesLeader | `AS.ArrakisPlanetologistAbility`, `AS.JudgeOfTheChangeSignetAbility` | Explicit, CanRunImmediately true (automatic, `la.py:529`) |
| kota_odax_of_ix (`:247`) | KotaOdaxOfIx | `AS.SecretProjectAbility`, `AS.ReverseEngineeringSignetAbility` | Explicit (mandatory either-or, `la.py:1234`) |

Leader-specific branches inside shared profile methods (the app keeps such terms there, `SPEC/leaders.md` §2): §9.

### 4.1 Chani — Tactician, Fedaykin Maneuver (`la.py:1121`)

```
TacticsReward(k) = spice_value(1) if the token passes index 5 (rules/tactics.py:16)
                 + water_value(1) if it reaches index 10 (:15; then reset to 2, :14; excess dropped)
AS.TacticianAbility: TriggeredAbility, no hook (terms: §1.4 loss value, Fedaykin below)
AS.FedaykinManeuverSignetAbility : SignetAbility                   # retreat any number OR (Fremen ≥2) water → draw 2
  selection_mode: Optional
  value_for_player(P, with=[space] or []):                        # D30
      if me.influence.fremen >= 2 and (space is None
              or can_agent_ability_be_played_with_space(space, Water, 1)):            # WaterOfLife: no space, no gate
          s.add("Fedaykin Draw", max(0.0, water_value(-1) + Draw2()))
      (no Fedaykin Draw term otherwise; the retreat branch is not valued, as Desert Scouts' V has no AI caller)
  Draw2() = 2 * card_draw_value() + buy_gains(possible_persuasion_gain())             # Draw2ContractAbility price
  evaluate(P, r):
      k = troops_to_retreat(me.troops_conflict + me.commanders_conflict)              # GetTroopsToRetreat; sandworms
                                                                                      # and the Conflict Agent cannot retreat (la.py:1121)
      if k > 0 and a retreat of k is offered: UST(1.0 + TacticsReward(k), retreat k, troops first §1.4)
      if pay_leader_signet_water offered:     UST(water_value(-1) + Draw2(), water)
      value <= 0 → decline_leader_signet_payment
```

### 4.2 Count Hasimir Fenring — Assassin, Corrino Liaison (`la.py:1149`)

```
AS.AssassinAbility: TriggeredAbility, no hook. Term: trash_card_value() += solari_value(1) "Assassin" for Fenring
  (D33; Intrigue trashes excluded, as the rule; precedent Count Ilban's "Leader Ability Card Draw" in SpaceAbility V)
AS.CorrinoLiaisonSignetAbility : SignetAbility                     # trash a card in play OR deep-cover Spy on Emperor
  selection_mode: Optional
  value_for_player(P, with):                                       # D32
      a = trash_card_value() + trash_mod()                                            # TrashAbility V (incl. Assassin)
      b = (spy_value().sum * C.ArrakisInformantMod) if len(me.spy_post_ids) <= 2 else 0.0   # ArrakisInformant V
      s.add("Corrino Liaison", max(a, b))
  evaluate(P, r):                                                  # D31, fixed priority as Chronicler's Insight
      (c, v) = card_to_trash(in-play cards offered, 1.0)                             # TrashAbility::Evaluate
      if c: return Answer(v, trash_leader_card(c))
      if a Spy placement (or recall-first) is offered: return Answer(spy_value().sum, ())   # ArrakisInformant E
      return Answer(0.0, None)                                                         # → decline
  post / recall: PlaceSpyEvaluator / RecallSpyEvaluator via common.spy_answer (deep cover, §1.5)
```

### 4.3 Duncan Idaho — Ginaz Swordmaster, Into the Fray (`la.py:1216`)

```
AS.GinazSwordmasterAbility: TriggeredAbility, no hook; Swordmaster cost term §1.7 (D35)
AS.IntoTheFraySignetAbility : SignetAbility                        # this turn's Agent → Conflict, strength 2 (3 w/ Swordmaster)
  selection_mode: Optional
  value_for_player(P, with=[space]): s.add("Into the Fray", deploy_value(space))     # DeployUnitsAbility V (D34)
                                                                   # with = [] (no Agent this turn): nothing
  evaluate(P, r):                                                  # DeployUnitsAbility E (D34)
      unit strength u = 3 if me.swordmaster_acquired else 2        # rules/strength.py:34
      if GetUnitsToDeploy([agent unit u], 1) is non-empty: return Answer(0.5, deploy_leader_agent)
      return Answer(0.0, None)                                     # → decline
```
The Conflict Agent's `Parent` is not a `WormSpace`, so `GetRecallAgent` skips it (the port already tests
`agent.ref not in SPACE_ARCHETYPES`). It is reached only through `RecallAgentAbility`'s `?? agents.FirstOrDefault()`
fallback, where it is listed last (D55). `RecallAgentValue`'s "has deployed agents" counts it (D56).

### 4.4 Esmar Tuek — Tuek's Sietch, Smuggle Spice (`la.py:1186`)

```
AS.TueksSietchLeaderAbility: TriggeredAbility (own visit +1 Solari, opponent visit → Esmar draws an Intrigue,
  rules/agent_turn.py:719); the +1 Solari is priced in AS.TueksSietchDeferredAbility (§6); the opponent side is 0 (D38)
AS.SmuggleSpiceSignetAbility : SignetAbility                       # place 1 bonus spice on Tuek's Sietch OR take 1 from a Maker space
  selection_mode: Explicit
  PlaceValue(with) = spice_value(1) * C.BonusSpiceMod   if this turn's Agent space (or `with`) is Tuek's Sietch and
                                                       its take_tuek_sietch_spice/_card choice is still unanswered
                                                       (our engine pays Tuek's Sietch's bonus spice with that choice,
                                                       board_effects.py:1431; once answered, the placed spice waits)
                   = 0.0                               elif is_final_round()
                   = spice_value(1)                    otherwise                     # D36 (plan §11.4 later gains)
  value_for_player(P, with): s.add("Smuggle Spice", max(spice_value(1) if any Maker bonus spice else 0, PlaceValue(with)))
  evaluate(P, r):
      for take_leader_bonus_spice(space) in board order: UST(spice_value(1), take space)     # spice first
      if place_leader_bonus_spice offered: UST(PlaceValue(), place)                           # replaces only if strictly greater
```

### 4.5 Gaius Helen Mohiam — Clandestine, Listeners (`la.py:1249`)

```
AS.ClandestineAbility: no hook. IconList + Spy (§1.7, D40). The forced Gather Intelligence leaves one legal key;
  with several connected Spies the existing RecallSpyIntelligenceAbility answer (GetRecallSpy) picks the post
AS.ListenersSignetAbility : SignetAbility                          # Spy on a Landsraad post OR pay 1 spice → Spy anywhere
  selection_mode: Optional
  value_for_player(P, with):                                       # D32
      if len(me.spy_post_ids) <= 2: s.add("Listeners Spy", spy_value().sum * C.ArrakisInformantMod)
  evaluate(P, r):                                                  # D39
      if a Landsraad placement / recall-first is offered: return Answer(spy_value().sum, ())  # post: GetBestPost(Landsraad)
      if pay_leader_signet_spice offered:
          v = spy_value().sum + spice_value(-1)
          if v > 0: return Answer(v, pay)                          # follow-up: GetBestPost over all offered posts
      return Answer(0.0, None)
```

### 4.6 Piter De Vries — Twisted Genius, Harkonnen Advisor (`la.py:515`)

`AS.TwistedGeniusAbility`: no hook (setup and the Round Start draw ask nothing). Harkonnen Advisor reuses
`ActivatedAbilities.Uprising.WarmasterAbility` (Gurney): V = `troop_value(1)`, AlwaysRunImmediately (D41). The
troop's deploy ban changes no app price. Twisted cards: companion file.

### 4.7 Steersman Y'rkoon — Strange Form, Hungry for Spice, Plot Course

`AS.StrangeFormAbility`: no hook (no water, no Signet Ring: `leaders.py:232-233`; Servo-Receivers' signet gives
nothing, `la.py:281`). `AS.HungryForSpiceAbility` and `AS.PlotCourseAbility`: no hook; their terms are in §9
(SpaceAbility, GetGainInfluenceValue) and the Navigation windows of §5.

### 4.8 Liet Kynes — Arrakis Planetologist, Judge of the Change (`la.py:529`)

```
AS.ArrakisPlanetologistAbility: no hook. Terms (D44):
  resource_value(SandWorms, n) for Liet = n × (trash_card_value() + trash_mod() + spice_value(1) + intrigue_value())
      "Planetologist", replacing the sandworm branch (precedent: Muad'Dib's per-worm add-on in GetResourceValue).
  The worm option of the desert spaces and of Arrakis Revolt is available under the Shield Wall
  (rules/planetologist.py:20; _can_deploy_sandworms ignores the wall for Liet).
  Each replacement's trash opens optional_trash (§7).
AS.JudgeOfTheChangeSignetAbility : SignetAbility                   # automatic; V only (D45, FillCoffers precedent)
  can_run_immediately: true
  value_for_player(P, with=[space] or []):
      icon = space.AgentIcon if space else None                    # no space (Servo-Receivers outside an Agent turn): nothing
      Pentagon and me.influence.emperor >= 2 -> s.add("Judge Water", water_value(1))
      Circle   -> s.add("Judge Solari", solari_value(1))
      Triangle -> s.add("Judge Spice", spice_value(1))
```

### 4.9 Kota Odax of Ix — Secret Project, Reverse Engineering (`la.py:1234`, `rtech.py:1084`)

```
AS.SecretProjectAbility : DeferredAbility                          # setup, tech_secret_project; forced; V empty
                                                                   # (the discount acts through tech_cost, §3.1)
  evaluate(P, r):                                                  # D27, TechTileToAcquire ordering (rix-tech §4.2)
      first tile of OrderByDescending(tech_tile_acquire_value(t).sum) over the offered bottom tiles, stack order
      (a tile worth 0 is still chosen; at setup the Early arc zeroes every tile without EarlyMod > 1)
AS.ReverseEngineeringSignetAbility : SignetAbility                 # 1 spice OR trash own tile → Intrigue + draw
  selection_mode: Explicit
  Trash(t) = intrigue_value() + card_draw_value_with_buy_gains() - HeldTileValue(t)
  value_for_player(P, with): s.add("Reverse Engineering", max(spice_value(1), max(Trash(t) for t in me.tech_ids)))   # Shaddam max(a,b)
                             # no tile held: spice_value(1) alone
  evaluate(P, r):                                                  # D28
      UST(spice_value(1), gain_leader_signet_spice)                # first
      for t in me.tech_ids: UST(Trash(t), trash_leader_tech(t))    # strictly greater only
```

## 5. Navigation (R8 §7, §2.13)

Archetypes `NavigationArchetypes.AppStyle.NavigationCard1` … `NavigationCard10`: `EntityType` Navigation NEW,
`CardCount` 1, `IntrigueTypeList` () (no timing band), `WormAbilityIDs` [`AS.NavigationCard<N>Ability`] (one subclass
per card of the base `AS.NavigationAbility`). Not Intrigue cards: never in the Intrigue hand, never `IsBadIntrigue`.

`OptionValue(card, option, slot, F)` (F = the triggering faction; `None` at setup, when every trigger-, alliance- and
influence-conditional part is 0, plan §11.4 "as now"):

| card (`intrigue.py`) | option 0 | option 1 | precedent |
|---|---|---|---|
| 1 (`:1191`) | `spice_value(1)` | Solari ≥ 2: `max_{G ≠ F, inf(G) ≥ 2} gain_influence_value(G, 1).sum + solari_value(-2)` | GainAnyInfluence max; PayAttribute net |
| 2 (`:1201`) | a post free or recallable: `spy_value().sum` | own Spy out: `recall_spy_value().sum + intrigue_value() + spice_value(2)` | PlaceSpyAbility V; Special Mission recall |
| 3 (`:1211`) | `solari_value(2) + (persuasion_value(1) if slot == 4 else 0)` | – | one-time price (plan §11.4) |
| 4 (`:1221`) | `spice_value(1)` | slot 1, water ≥ 1: `acquire_value(TSMF).sum + water_value(-1)` | AcquireAbility value |
| 5 (`:1232`) | `trash_card_value() + trash_mod()` (+2 spice unpriced) | – | TrashAbility V; Chronicler's Insight leaves the spice unpriced (D47) |
| 6 (`:1240`) | `troop_value(1)` | Solari ≥ 3: `troop_value(3) + solari_value(-3)` | resource prices |
| 7 (`:1247`) | `spice_value(1) + (intrigue_value() if has an Alliance else 0)` | – | |
| 8 (`:1254`) | `water_value(1) + (spice_value(1) if F == SpacingGuild else 0)` | – | |
| 9 (`:1264`) | `card_draw_value_with_buy_gains()` | Spice ≥ 5: `spice_value(-5) + victory_point_value(1)` | DrawAbility V; PayAttributeToGainVPAbility V |
| 10 (`:1273`) | `best_influence_exchange(-1, +1)` value; played iff ≥ 2.0 | – | ChangeAllegiancesAbility E (D48) |

`NavigationValue(card, slot, F) = max over playable options of OptionValue` (0 if none).

- **`navigation_setup`** (`rules/navigation.py:82`; census 52/36/52): four steps; step i fills slot i (left → right),
  and the card left over goes to the box. Each step is forced: `make_choice` over `NavigationValue(card, i, None)`;
  nothing > 0 → `DefaultRandomChoice` (D46).
- **`navigation_choice`** (`navigation.py:228`; census play 39/26/33, decline 4/2/5): `play_navigation(option)` =
  the first strictly best `OptionValue` with the real slot and trigger. Without `decline_navigation` the prompt is
  forced: ≤ 0 → `DefaultRandomChoice`. `decline_navigation` is offered exactly when every playable option has a cost
  (`navigation.py:262`: Card 10's Influence loss, nothing playable, or any card whose only playable options carry an
  arrow cost). Then the prompt is optional (plan §11.4 "선택적 효과·지불"): play the best option iff its `OptionValue`
  > 0, else decline; Card 10 uses its precedent instead (play iff the exchange value is ≥ 2.0, D48). Nothing playable
  leaves `decline` alone (auto).
- **Follow-ups** (the option resolves through `intrigue_choice` frames). The answer is stored in
  `Memory.intents[("navigation", card_id)]` (plan §4.6):
  1 = the chosen G; 2 = `PlaceSpyEvaluator` / `GetRecallSpy`;
  5 = the trash ranking of `ChroniclersInsightAbility::Evaluate` (the same "trash; 2 spice if it cost ≥ 1"; the app
  ranks the hand, here it ranks whatever cards the trash frame offers): paid cards `card_to_trash(…, 0.0)` → any
  `card_to_trash(…, 0.0)` → the lowest-reveal-value paid card of cost < 3 → none = decline;
  10 = lose the exchange's L, then gain with `ChooseFactionInfluenceEvaluator` on the post-loss state
  (Change Allegiances).
- **Plot Course trigger** term: §9 (GetGainInfluenceValue leader block).

## 6. Board changes (R8 §12)

| change | app-style element |
|---|---|
| Sardaukar Commander on 6 spaces (`sardaukar.py:16-23`: Sardaukar, Dutiful Service, Deliver Supplies, High Council, Gather Support, Assembly Hall) | append `AS.AcquireCommanderAbility` to `SpaceArchetypes.Uprising.{Sardaukar, DutifulServiceUP/DutifulServiceCHOAM, DeliverSupplies, HighCouncilUP, GatherSupport, AssemblyHall}` (catalog `SPACE_ARCHETYPES`) with `bloodlines` on; V is 0 once the space's Commander is gone. None of the six is a Combat space, so the Commander goes to the garrison and is deployable this turn only through a Combat icon (its own recruit room, OQ-070; §1.3) |
| Ixian Embassy: Acquire Tech on the 5 Landsraad spaces incl. the first High Council visit (`board_effects.py:351-357`); High Council seat −1 | append `ActivatedAbilities.RiseOfIx.AcquireTechAbility` to `HighCouncilUP, ImperialPrivilege, SwordmasterUP, AssemblyHall, GatherSupport` with `tech_module` on; discount model §3.1. Note: `AgentAbility::Evaluate` sums V over all space abilities, so High Council (which already counts its base `SpaceAbility` twice, generic §6.1) gets `BuyTechValue` once |
| Tuek's Sietch (Esmar only; `content/uprising/board.py:284-295`: Spice Trade, Combat, Maker, free, "1 spice OR draw 1", bonus spice) | `SpaceArchetypes.AppStyle.TueksSietch`: `EntityType` Space, `AgentIcon` Triangle, `CombatSpace` True, `BonusSpice` 0 (runtime `maker_bonus_spice`), `PossibleSpice` 1, `ObservationPosts` (), `Tags` (Harvest) (Hagga Basin precedent). WormAbilityIDs: `AS.TueksSietchDeferredAbility`, `ActivatedAbilities.DeployUnitsAbility`, `SpaceAbilities.SpaceAbility` |
| Combat icon (Agent and Reveal turns, `combat_deployment.py:646`) | a `DeployUnitsAbility` custom key wherever our engine offers the deployment off a Combat space (SardaukarCoordinationAgentAbility precedent, D61); in the placement value only through the cards that print it (companion file) and Rapid Dropships |
| Command (6+) (`reveal_turn.py:303, 2361-2378`) | plan §11.5: judged on Persuasion *generated*, so a buy never cancels it; Command choices resolve like other Reveal effects in active-card order before buys. Tile Command effects (Delivery Bay, Training Depot) are automatic |
| Spy with Deep Cover (`spy_moves.py:306`) | §1.5 |

```
AS.TueksSietchDeferredAbility : DeferredAbility                    # Explicit; timing None; precedent HaggaBasinUprisingDeferredAbility (D37)
  value_for_player(P, with):
      spice = spice_value(1); draw = card_draw_value_with_buy_gains()
      s.add("Tuek's Sietch Spice" if spice > draw else "Tuek's Sietch Draw", max(spice, draw))
      if leader is Esmar Tuek: s.add("Tuek's Sietch Solari", solari_value(1))       # leader term (D37)
  evaluate(P, r):
      UST(spice_value(1), take_tuek_sietch_spice)                                    # stored first
      UST(card_draw_value_with_buy_gains(), take_tuek_sietch_card)                   # strictly greater only
```
The bonus spice is priced by the generic `SpaceAbility` (`BonusSpice × BonusSpiceMod`). Census of
`take_tuek_sietch_spice/card`: 225/209/222.

## 7. New decision windows (R8 §2)

| window (`frames.py`) | ids (rule pointer) | census bl/tech/promo | decider | answer |
|---|---|---|---|---|
| `skill_choice` (`:48`) | `choose_skill`, `decline_skill`, `resolve_commander_without_skill` (`rules/sardaukar.py:502`) | 3 / 33+32 / 3 | owner | §2.3 |
| `opponent_spy_move` (`:51`) | `move_spy(post_id)`, `lose_moved_spy` (`rules/spy_moves.py:103`) | 19/11/16 | the Spy's owner (victim) | forced; least loss = keep the best post: `best_post(offered posts)` (PlaceSpyEvaluator, D49); `lose_moved_spy` is offered alone (auto) |
| `opponent_unit_loss` (`:52`) | `lose_unit(zone[, commanders])`, `resolve_unit_loss_without_unit` (`rules/unit_loss.py:199`; candidates in `UNIT_LOSS_CANDIDATES` order `:41`) | 125+13 / 117+12 / 101+13 | victim | forced; min `LoseUnitValue` (§1.4); the "without unit" id is offered alone (auto). The same evaluator answers the Twisted `lose_intrigue_troop` costs (companion file) |
| `optional_trash` (`:58`) — Bloodlines sources | `trash_optional_card(card_id)`, `decline_optional_trash` (`rules/optional_trash.py:33`; targets hand ⧺ discard ⧺ in play) | 40+40 / 97+97 / 54+54 | owner | Planetary Array's acquire key: `DisposalFacilityAcquiredAbility::Evaluate`. Spy Drones' flip trash and Liet's per-worm trash (`planetologist.py:26`): `TrashAbility::Evaluate`. Both run `card_to_trash(targets, 1.0)`; a card → trash it, none → decline (D51). The source is read from the frame's `source` (`…:tech:planetary_array:acquire:trash`, `…:tech:spy_drones:flip`, `…:planetologist:<i>`). Immortality/Epic sources: their own spec files |
| `contract_intrigue_trash` (`:26`) | `trash_intrigue_for_contract(card_id)` (`rules/contracts.py:1384`) | 6/9/8 | owner | forced; `BranchingPathAbility` pick (`_trash_intrigue_choice`, `abilities/imperium_a.py:235`: the held Intrigues shuffled with the agent RNG, then the first `IsBadIntrigue` card at 5.0, else the first at 1.0) (D52). The Bloodlines and Twisted `IsBadIntrigue` predicates come from the companion file |
| `intrigue_trigger_contract` | `take_trigger_contract(instance_id)` (`rules/intrigue_triggers.py:390`) | 7/11/12 | owner | forced; `GainContractAbility.ContractEvaluate(forced=True)` = `best_contract(offered, forced=True)` (D53) |
| `leader_signet` (`:84`) | the seat's signet ids (`la.py:1009`, `engine.py:559`) | tech only, per id: `decline_leader_signet_payment` 12, `place_leader_spy` 8, `pay_leader_signet_spice` 4, `gain_leader_signet_spice`/`trash_leader_tech` 2, `deploy_leader_agent` 2, `retreat_leader_troops` 2, `place_`/`take_leader_bonus_spice` 1, `advance_feyd_track`, `trash_leader_card`, `gain_leader_signet_troop`, `recall_spy_for_leader_placement` 1 each | owner | Servo-Receivers' granted use. The leader's `SignetAbility` E is evaluated as a single-source prompt, mapped exactly as the agent_effects leader rows do (`windows/agent_effects.py` docstring, "The leader"). Optional and E ≤ 0 → `decline_leader_signet_payment`; Explicit and nothing > 0 → `DefaultRandomChoice` (D54). Effects "this turn" find nothing outside an Agent turn (OQ-062; engine) |
| `spy_placement`, `contract_reward_spy`, `place_leader_spy`, `place_agent_card_spy` — deep cover | Spy Drones (`rtech.py:606`), Storms in the South 1st (`combat.py:455-462`), Corrino Liaison, Deliver Supplies token, Arrakis Observer | spy_placement, all contexts: `place_spy_on_space` 150/258/135 (base 37); recall-first (`recall_spy_for_placement`, always with `decline_spy_placement`) 15/51/15 (base 2) | owner | existing `common.spy_answer` (never declines: recall the worst-post Spy, then place on the best post); deep-cover posts valued per §1.5 |
| `navigation_setup`, `navigation_choice` | §5 | §5 | owner | §5 |
| `tech_acquisition`, `tech_secret_project` | §3.4 | §3.4 | owner | §3.4 |

## 8. Ids never legal in the census (R8 open point 9)

Re-checked on the new census. Never legal: `hold_contract_icons`, `resolve_contract_icons_without_contract`,
`lose_moved_spy`, `resolve_commander_without_skill`, `recall_conflict_agent_for_agent_card` and `_for_contract`;
`recall_conflict_agent_for_imperial_privilege` was legal 3 times (`bloodlines_promo`). The row of ids that are offered
alone is included because they share the answer, though they were legal: `resolve_unit_loss_without_unit` 13/12/13,
`decline_tech` (tech_acquisition) 24, `decline_navigation` 4/2/5 (the census does not separate the alone cases).

| id | why it is never chosen against alternatives | answer |
|---|---|---|
| `hold_contract_icons`, `resolve_contract_icons_without_contract` | offered only when no contract can be taken (`rules/contracts.py:668-676`), alone | single legal action → taken without a handler (`agent.py`: `len(legal_actions) == 1`); the app's `GetBestContract` empty answer |
| `lose_moved_spy` | offered only with no target post, alone (`spy_moves.py:124`) | auto (single) |
| `resolve_commander_without_skill` | offered only with no Skill and no Plasteel decline, alone (`rules/sardaukar.py:531`) | auto (single) |
| `resolve_unit_loss_without_unit`, `decline_tech` (nothing affordable), `decline_navigation` (nothing playable) | alone | auto (single) |
| `recall_conflict_agent_for_agent_card` / `_for_contract` / `_for_imperial_privilege` | offered with the other recall targets (`rules/agent_effects.py:1452`, `contracts.py:380`, `board_effects.py:1141`) | the Conflict Agent is an extra AGENT candidate placed **after** the board Agents. `GetRecallAgent` skips it (not on a space), so it is picked only by the `?? agents.FirstOrDefault()` fallback when it is the only candidate (D55). `RecallAgentContractAbility` E is the same with value `RecallAgentValue + 1.0` |

## 9. Automatic Bloodlines effects as valuation terms (R8 §2.17)

| effect (pointer) | term (where) | precedent / decision |
|---|---|---|
| Commander strength 2; Skill strength re-judged (`strength.py:46-139`) | none beyond §1.1 unit counts (current `Strength` already includes them; EstStrength anticipates no leader/skill strength) | app EstStrength reads `me.Strength` |
| Commanders return to supply after Combat (`combat.py:1408`) | none (troops return too) | — |
| Into the Fray Agent strength (`strength.py:34`) | a Conflict unit (§1.1) | D1 |
| Chani's Tactics track (`rules/tactics.py:25`) | `TacticsReward` in Fedaykin E and in the loss value (§1.4, §4.1) | plan §11.4 one-time price |
| Assassin +1 Solari per trashed card (`rules/card_trash.py:91`) | `trash_card_value() += solari_value(1)` for Fenring | D33 |
| Eliminate Allies / Sardaukar Standard trash triggers; Corrupt Bureaucrat discard trigger (`card_trash.py:111/131`, `card_discard.py:89`) | card data, companion file (app: `SardaukarSoldierAbility` has no AI hook; discard triggers act only through the `IncentiveDiscard` tag) | — |
| Twisted draw each Round Start (`phases.py:139`) | none (no decision; leaders are random) | — |
| Tuek's Sietch visit (`agent_turn.py:719`) | Esmar's +1 Solari in `AS.TueksSietchDeferredAbility` V; the opponent side 0 | D37, D38 |
| Hungry for Spice (`la.py:2434`) | `SpaceAbility.ValueForPlayer` leader term: Y'rkoon, `not me.hungry_for_spice_granted_turn` and `spice_gained_this_turn(me) < 3 <= spice_gained_this_turn(me) + space.Spice + BonusSpice + PossibleSpice` (`rules/agent_effects.py:4786`) → `+ card_draw_value() + buy_gains(possible_persuasion_gain())` "Hungry for Spice" | Count Ilban's "Leader Ability Card Draw" (generic §6.1), D42 |
| Plot Course triggers (`rules/influence.py:80`) | `GetGainInfluenceValue` leader block: `elif L == SteersmanYrkoonLeader and cur <= 1: S += amount × NavigationValue(next slot card, its slot, F)` "Steersman Y'rkoon Plot Course" (0 with no slot card left) | Margot / Irulan (leaders §2.1: flat proxy × amount, `cur <= 1`, no "reaches 2" test), D43 |
| Judge of the Change / Harkonnen Advisor (`la.py:529/515`) | their signet V (§4.6, §4.8) | — |
| Ginaz Swordmaster (`agent_turn.py:1000`) | runtime Swordmaster `SolariCost` − 2 (§1.7) | D35 |
| Clandestine (`agent_icons.py:122`, `spies.py:55`) | IconList + Spy (§1.7) | D40 |
| Planetologist (`planetologist.py:26`, `agent_turn.py:276`) | SandWorms value replaced (§4.8) | D44 |
| Earn Any Alliance completion (`contracts.py:1500`) | companion file (contract tokens) | — |
| Suspensor Suits (`rtech.py:903`) | `intrigue_value() += troop_value(1)` "Suspensor Suits" while the seat owns the tile and is in its own Agent or Reveal turn | D59 |
| Planetary Array draw on a Conflict win (`combat.py:1450`) | `RelativeConflictValue`: `if owns PlanetaryArray: res.add("Planetary Array", card_draw_value_with_buy_gains())` | Windtraps (`profile-combat.md` §5.2), D58 |
| CHOAM Transports draw per completed contract (`contract_tiles.py:21`) | `ContractAbility.GetResourceValue += card_draw_value_with_buy_gains()` "CHOAM Transports" for its owner | Draw2ContractAbility's draw term, D57 |
| Tech endgame (CHOAM Transports VP, Panopticon influence; `rtech.py:986`) | none (`GetConditionalEndgameVP` feeds only the UI) | rix-tech §7.4 |
| Ornithopter Fleet (`ornithopter.py:51`) | `GetBattleIconValue` reads the owner's battle icons and the evaluated icon as Ornithopter (engine fact) | — |
| Wild battle icons pair at Endgame (`endgame.py:278`) | companion file (Conflict cards) | — |
| Self-Destroying Messages +1 Persuasion; Charismatic (Commander in the Conflict); Navigation 3's `reveal_persuasion_bonus` | `GetRevealPreview["Persuasion"]` outside the own Reveal turn: +1 / +1 / +bonus | Minimic Film (`profile-economy.md` §5.1), D62 |
| Delivery Bay 2 Solari / Training Depot 2 swords on Command | none (preview keys Solari/Strength have no AI reader) | — |
| Navigation Chamber, Sardaukar High Command cost cuts | the costs themselves (§1.7; `commander_cost`) | — |

## 10. App-style decisions

| # | decision | precedent (spec, section) or rule |
|---|---|---|
| D1 | Commanders count as `WormTroop`/units in every app unit count; the Into the Fray Agent as a unit, not a troop | rule text (`bloodlines.md` §3); app `ConflictUnits`/`GarrisonUnits` count every `WormUnit` child, `GarrisonTroops` only troops (`profile-combat.md` §0 conventions). Supply troop reads stay troop-only (§1.1, rule text). Agent: no precedent, rule 11.4 (a unit in the Conflict) |
| D2 | `SkillValue` is a one-time price with its condition judged now (also Navigation 3's slot-4 Persuasion, §5) | no app method yields a count of remaining activations: `GetGameArc`, `IsFinalRound`/`IsClimax`, and the only `CurrentRound`-based remaining-game term, contract `RewardValueMod` `max((9 − CurrentRound) × 0.125, 0.25)` (influence §3.4), is a discount ≤ 1.0 on one reward, not a multiplier → rule 11.4 last item (1회 가격); conditions judged now as `MeetsCost`-gated V (`generic-abilities.md` §7). See OPEN 7 |
| D3 | Commander purchase: Explicit, empty answer at 0.5 when the net ≤ 0 | `AcquireTechAbility::Evaluate` (rix-tech §6.1) |
| D4 | Commander-space placement V = `max(0, net)`, 0 when unaffordable with the space cost | `WaterOfLifeSignetAbility` V (leaders §6.1); rule 11.4 "얻는 것 − 내는 것" |
| D5 | Supply recruit taken iff its net > 0; valued 100 while a deploy window is open (so it resolves before the deploy key at 0.5), else at its net | rule 11.4 net; 100 = Mercenaries' value in a deploy window (intrigues §7.18). Mercenaries' posture gate (`ShouldPlayTroopIntrigue`, §4.2) is deliberately not copied: the recruit is a priced purchase under rule 11.4, not a combat play |
| D6 | Deploy order: Commanders first iff a Skill is held and no Commander is in the Conflict | no precedent: rule 11.4 "여러 보기 중 하나" (a Commander's activation is worth `SkillValue`, a troop's 0) |
| D7 | Retreat troops first, Commanders last | `DesertScoutsAbility` (leaders §8.1); plan §11.5 |
| D8 | `LoseUnitValue` prices: garrison = `troop_value(1)`, Conflict = `strength_value(2)` (+ Skills when the last Commander, − Chani's track reward) | rule 11.4 "강제 손실"; prices from `GetResourceValue` |
| D9 | Desperate uses Devious Strength's conditions with 3 strength | `DeviousStrengthAbility` (leaders §3.1) |
| D10 | Plasteel Blades trash iff `SkillValue(best) − HeldTileValue > 0` | rule 11.4 optional payment |
| D11 | `HeldTileValue(t) = AcquireValue(t) × arc mod` (plan §11.7; was `tech_tile_acquire_value(t)`) | no precedent (the app never values an owned tile): rule 11.4 (nearest price of the same object) |
| D12 | Tech affordability: the High Council seat stands for the negotiators; Secret Project per tile; the seat assumed when valuing High Council | rix-tech §4.1 (automatic owner-wide discount); `[Bloodlines p. 7]` example |
| D13 | A forced card acquire whose E is empty buys `TechTileToAcquire(1)`'s tile | rix-tech §4.2 (returns a tile even at 0) |
| D14 | Advanced Data Analysis boxes the Spy on the worst post | `RecallSpyEvaluator` (influence §2.5) |
| D15 | Tech acquire effects resolved at once, in the engine's key order | `AcquireTechTile` §7.2 (immediate); rule 11.4 order questions |
| D16 | NEW AcquireEffects values `IntrigueOrImperium`, `ShieldWall`, `Signet` | no app enum; valued 0 by `GetAcquireEffectsValue` like `PlaceSpy`/`Contract` (profile-economy §9) |
| D17 | Bonus prices: Intrigue = `IntrigueValue`; Trash = `TrashCardValue + TrashMod`; PlaceSpy = `SpyValue`; Contract = `ContractValueForPlayer` | Chaumurky SAV (rix-tech §8.2); `DisposalFacilityAcquiredAbility` V (§8.3); `PlaceSpyAbility` V (generic §13.2); `GainContractAbility` V (generic §15) |
| D18 | No bonus for an `Imperium` (draw) acquire effect | Spaceport (rix-tech §3.3, §8.12) |
| D19 | Gene-Locked Vault: SAV `IntrigueValue`; the choice is argmax(Intrigue V, Draw V) | `GainIntrigueAcquiredAbility` V, `DrawImperiumAcquiredAbility` V (rix-tech §8.11-8.12) |
| D20 | Forbidden Weapons' Shield Wall: `BlowWallValue` iff `ShouldBlowWall` | Sietch Tabr option / `ChooseBlowWall` (influence §6) |
| D21 | Servo-Receivers SAV = the leader `SignetAbility` V with this turn's Agent space during an own Agent turn, else with no space | `AgentAbility` §2.2(d); OQ-062 (b) ("this turn" = the Agent turn in progress) |
| D22 | Advanced Data Analysis SAV = −`SpyValue` | `RecallSpyValue`'s −SpyValue (influence §2.2); Detonation Devices' negative bonus (rix-tech §3.4) |
| D23 | Advanced Data Analysis and Spy Drones flips: E 100 | Chaumurky "always play", Flagship/Training Drones 100 (rix-tech §8.2, §8.4, §8.14) |
| D24 | Rapid Dropships: 100 off a Combat space when `GetUnitsToDeploy` deploys | `TrainingDronesAbility` (rix-tech §8.14), inverted space test |
| D25 | Flip sources join the turn-start prompt and both post-action lists | rix-tech §7.4 |
| D26 | Forbidden Weapons is a forced loss: least loss, answered at max(v, 1.0); influence lost where `gain_influence_value(F, −1)` hurts least; Alliance recipient = first offered | rule 11.4 "강제 손실"; `RecallSpyIntelligenceAbility` 1.0 (engine-order §3.4); plan §11.5 Scouts precedent |
| D27 | Secret Project: `TechTileToAcquire` ordering (value desc, stack order) | rix-tech §4.2 |
| D28 | Reverse Engineering: spice first, a tile only if strictly better; V = max | `DesertSpaceDeferredAbility` order (board, leaders §9.6); Shaddam V `Math.Max(a, b)` (leaders §11.3) |
| D29 | Signet SelectionMode: Optional where our engine offers a decline, Explicit where the choice is mandatory | `SignetAbility` Explicit default; Optional overrides (Spice Agony, Water of Life, Chronicler's Insight; leaders §0.1.6) |
| D30 | Fedaykin: draw 2 priced as Draw-2; retreat at 1.0 + Tactics reward, count from `GetTroopsToRetreat` | `Draw2ContractAbility` (influence §3.5); `DesertScoutsAbility` 1.0 (leaders §8.1) |
| D31 | Corrino Liaison: trash a junk card first, else the Spy | Chronicler's Insight fixed priority (leaders §10.2); `ArrakisInformantAbility` E (§7.2) |
| D32 | Restricted-post Spy signets (Fenring, Mohiam) use Arrakis Informant's V incl. `ArrakisInformantMod` | `ArrakisInformantAbility` V (leaders §7.2) |
| D33 | Assassin priced inside `TrashCardValue` | Count Ilban's leader term in `SpaceAbility` V (generic §6.1) |
| D34 | Into the Fray: V = `DeployValue(space)`, E = 0.5 when `GetUnitsToDeploy` takes the Agent unit | `DeployUnitsAbility` (generic §11) |
| D35 | Duncan's Swordmaster discount on the runtime `SolariCost` | `SwordmasterUprisingSpaceAbility` `DecreaseInitialCost` (`abilities/generic.py:273`) |
| D36 | Smuggle Spice: take = `spice_value(1)`; place = ×`BonusSpiceMod` when Tuek's Sietch is this turn's space and its choice (which pays the bonus spice) is still pending, else `spice_value(1)` unless the final round | rule 11.4 later gains; `SpaceAbility` bonus-spice price (generic §6.1) |
| D37 | Tuek's Sietch: spice-first choice; Esmar's +1 Solari in its V | `HaggaBasinUprisingDeferredAbility` (leaders §9.6); leader terms in space V (generic §6.1) |
| D38 | Benefits to or harm of opponents are worth 0 (Esmar's Intrigue from an opponent's visit, Gene-Locked Vault) | rule 11.4 (no opponent model) |
| D39 | Listeners: Landsraad Spy at `SpyValue`; pay 1 spice only when no Landsraad post is open | `ArrakisInformantAbility` E; rule 11.4 net |
| D40 | Permanent icon grants added to the owner's `IconList` reads | app `ConditionalIconList` attribute (condition-dependent icons); otherwise rule 11.4 |
| D41 | Harkonnen Advisor = `WarmasterAbility` | identical price (leaders §4.1) |
| D42 | Hungry for Spice in `SpaceAbility` V | Count Ilban (generic §6.1) |
| D43 | Plot Course in `GetGainInfluenceValue`, `cur <= 1`, × amount | Margot / Irulan (leaders §2.1) |
| D44 | Liet's worms priced as trash + spice + Intrigue, available under the wall | Muad'Dib per-worm add-on (leaders §9.4); `TrashAbility` V |
| D45 | Judge of the Change V by the space icon | `FillCoffersAbility` V (leaders §8.2) |
| D46 | Navigation setup: slot-by-slot argmax, values "as now" | rule 11.4 "여러 보기 중 하나", "나중에 받는 것" |
| D47 | Navigation 5: Chronicler's trash ranking, +2 spice unpriced | `ChroniclersInsightAbility` (leaders §10.2) |
| D48 | Navigation 10 played iff the exchange ≥ 2.0 | `ChangeAllegiancesAbility` (intrigues §7.4) |
| D49 | A moved Spy goes to the best allowed post | `PlaceSpyEvaluator` (influence §2.5); plan §11.5 victim rule |
| D50 | Deep-cover posts valued as empty posts | `PostValue` ignores other seats (influence §2.3) |
| D51 | Bloodlines optional trashes: `TrashAbility` / `DisposalFacilityAcquiredAbility` E | generic §12.1; rix-tech §8.3 |
| D52 | Immediate token's Intrigue trash: bad Intrigue first | `BranchingPathAbility` (imperium-a §2.3) |
| D53 | Coercive Negotiation pick: `GetBestContract(forced)` | `GainContractAbility.ContractEvaluate` (generic §15) |
| D54 | Servo-Receivers' signet use: a single-source prompt | engine-order §0 (forced / non-forced rules) |
| D55 | The Conflict Agent is the last recall candidate and is skipped by `GetRecallAgent` | app code `a.Parent as WormSpace` (generic §14.2) |
| D56 | `RecallAgentValue` counts the Conflict Agent as deployed | no precedent: rule 11.4 (OQ-068: it is "your Agent") |
| D57 | CHOAM Transports' draw in `ContractAbility.GetResourceValue` | `Draw2ContractAbility` (influence §3.5) |
| D58 | Planetary Array's draw in `RelativeConflictValue` | Windtraps (profile-combat §5.2) |
| D59 | Suspensor Suits: + `troop_value(1)` on `IntrigueValue` in the own turn | no precedent (Sonic Snoopers is a ×mod of another effect): rule 11.4 one-time price |
| D60 | Navigation Chamber: each discount variant is a target; the first strictly best wins | `AgentAbility::Evaluate` (generic §2.1) |
| D61 | Reveal-turn and off-Combat-space deploys use `DeployUnitsAbility` at 0.5 | `SardaukarCoordinationAgentAbility` (imperium-b) |
| D62 | Self-Destroying Messages, Charismatic, Navigation 3 add Persuasion to `GetRevealPreview` | Minimic Film (profile-economy §5.1) |

## 11. OPEN

Settled by plan §11.7 (2026-10-05): items 1 and 2 (tile mods by nearest lasting ability; `HeldTileValue` =
`AcquireValue` × arc mod), 5 (yes, Bloodlines games only), 7 (priced once), 8 (add `CardDrawValueWithBuyGains −
SpyValue` when negative) and 9 (add the extra-Skill term to both nets).

1. **Early-arc consequence of plan §11.3.** With `EarlyMod` only on Planetary Array, every other tile is worth 0 in
   rounds 1-3 ("Not early tech", rix-tech §3.1), so the Early AI buys only Planetary Array. `BuyTechValue` still adds
   `max(2.0, ½ cost) × 1.0` to Landsraad placements in the Early arc (rix-tech §10.4). Both follow from the rule as
   written. Settle: the main session confirms that 11.3's "없으면 없음(1.0)" is meant to block Early purchases.
2. **`HeldTileValue` (D11)** inherits (1): in the Early arc every owned tile is worth 0. So Kota trashes tiles freely
   and Plasteel Blades is always traded for a Skill. Settle with (1), or choose a different held-tile price.
3. Twisted and Bloodlines `IsBadIntrigue` predicates (used by D52) come from the companion file.
4. The port's `units_to_deploy(count, max)` assumes strength-2 units. The Commander split works with the count. The
   Into the Fray strength-3 unit needs the unit-list form (`GetUnitsToDeploy(units, max)` with per-unit strength).
   This is an implementation detail with no behaviour question.
5. D56 (`RecallAgentValue` with only the Conflict Agent out) changes an existing port. Confirm before implementing.
6. No app_ai census of Bloodlines is possible until the catalog maps the Bloodlines content (`skirmish_wild`, …).
   Recount `fallbacks`/`UNPORTED` for the windows above then (plan §11.6 stage 5).
7. **Lasting effects priced once (D2).** A Skill pays every round a Commander fights, and Navigation 3 in slot 4 pays
   at every later Reveal, but both are priced once. Plan §11.4 multiplies by the number of uses "if the app's
   remaining-round judgement can count them". The app's only `CurrentRound`-based remaining-game term is the contract
   `RewardValueMod` factor `max((9 − CurrentRound) × 0.125, 0.25)` (`SPEC/profile-influence-uprising.md` §3.4), whose
   literal 9 could be read as an implied game length (uses left ≈ `9 − CurrentRound`). Settle: the main session
   decides whether that factor counts as "can count" (then price × `max(9 − CurrentRound, 1)`) or not (one-time, as
   written).
8. **Mohiam's forced Gather Intelligence** (Clandestine, `spies.py:55`) has no valuation term. `SpaceAbility` V adds
   its flat `SpaceSpyUseIntelligenceMod` 1.25 only when the recall is wanted (`CardDrawValueWithBuyGains > SpyValue`
   or 3 Spies out, `SPEC/generic-abilities.md` §6.1); when it is not wanted, Mohiam still loses the Spy and the app
   prices nothing. Settle: keep the app term unchanged (as written), or add `CardDrawValueWithBuyGains − SpyValue`
   when negative (rule 11.4 one-time price of a forced effect).
9. **Plasteel Blades' extra Skill is not in `CommanderAcquireNet` / `RecruitNet`.** Every recruit (acquire, supply
   re-buy, bank Commander) opens the optional trade (`rules/sardaukar.py:115`), worth `max(0, SkillValue(best other
   eligible Skill) − HeldTileValue(plasteel_blades))` by D10's own formula. Settle: add that term to both nets for the
   tile's owner (rule 11.4 "얻는 것"), or leave it out as written.
