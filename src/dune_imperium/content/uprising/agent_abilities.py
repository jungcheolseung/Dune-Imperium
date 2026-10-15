"""Agent-box ability records of personal cards (composed effects, stage A2).

docs/composed-effects-plan.md 5 (A2): the personal cards whose Agent box is
a plain or conditional gain are written as ability records here and resolved
by ``rules.agent_box_abilities``; the card keeps its ``agent_effect`` value,
which names the record. The printed text is ``display/tokens.py``.

- ``requirement`` is a condition fixed by the placement -- the visited space
  is a Maker space, a Faction Bond among the cards already in play (it can
  only shrink) -- and is judged when the card is played: when it fails the
  box is never pending (OQ-028 (a)).
- A line's ``condition`` is judged when the box resolves, in the owner's
  order (OQ-028); while it fails the box waits and the turn's end fizzles it
  (OQ-057 (1)). A Bond box judges its Bond both ways: a trash in the same
  turn can break it.
- ``icons`` marks a box whose printed icons resolve one action each
  (OQ-027 card Agent box extensions); the others resolve as one action.
- ``hook`` names a special flow kept as code in ``rules.agent_effects``
  (``_BOX_HOOKS``): a box with no event of its own, sources found nowhere
  else, or a frame rewritten mid-way. Its sections list the fragments it
  gives where the DSL has them (the network's card features, plan 4.4);
  they describe the box, the hook judges and pays it (editing a hook
  record's condition changes no play).

The boxes not here keep their own code in ``rules.agent_effects`` until a
later stage moves them (plan 5).
"""

from collections.abc import Mapping
from copy import replace
from types import MappingProxyType
from typing import Final

from dune_imperium.content.uprising.abilities import (
    Ability,
    AbilityMark,
    AbilityStructure,
    AbilityTiming,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardForSolari,
    AcquireCardUpTo,
    AdvanceTleilaxu,
    AtMakerSpace,
    BoostNextBeneGesseritCard,
    CommandersInConflictAtLeast,
    CompleteContract,
    CompletedContractsAtLeast,
    Condition,
    ContractCompletedThisTurn,
    Cost,
    DiscardedCardHasFaction,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPerSandwormInConflict,
    DrawPersonalCards,
    EffectSection,
    FactionBond,
    ForceEnemyRetreat,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    Grafted,
    GrantCombatDeployment,
    HasAlliance,
    InfluenceAtLeast,
    LookAtIntrigueKeepOne,
    PayResources,
    PlaceSpy,
    PledgeFirstPlaceInfluence,
    RecruitTroops,
    Research,
    ReturnThisCardToHand,
    Reward,
    SandwormsInConflictAtLeast,
    SpendSpecimens,
    SpyRecalledThisTurn,
    TakeContract,
    TrashCard,
    TrashedCardHasFaction,
    TrashIntrigueCard,
    TrashPersonalCard,
    UnitsInConflictAtLeast,
)
from dune_imperium.content.uprising.types import PersonalCardAgentEffect

_BOX = PersonalCardAgentEffect
_BG = Faction.BENE_GESSERIT
_BG_BOND = FactionBond(_BG)
_BG_TWO = InfluenceAtLeast(_BG, 2)
_TWO_SPICE = GainedSpiceThisTurn(2)
_GUILD_DISCARD = DiscardedCardHasFaction(Faction.SPACING_GUILD)
_COMMANDER_IN_CONFLICT = CommandersInConflictAtLeast(1)
_EMPEROR_TRASH = TrashedCardHasFaction(Faction.EMPEROR)
_BRANCHING_PATH = (
    _BOX.MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
)
_JUNCTION_HEADQUARTERS = (
    _BOX.MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE
)


def _line(*rewards: Reward, condition: Condition | None = None) -> EffectSection:
    return EffectSection(rewards=rewards, condition=condition)


def _box(
    *rewards: Reward,
    condition: Condition | None = None,
    requirement: Condition | None = None,
) -> Ability:
    """A box resolved as one action: its rewards on one line."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(_line(*rewards, condition=condition),),
        requirement=requirement,
    )


def _hook(
    name: str,
    *rewards: Reward,
    condition: Condition | None = None,
    requirement: Condition | None = None,
) -> Ability:
    """A box resolved by the named special flow (``agent_effects._BOX_HOOKS``)."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(_line(*rewards, condition=condition),) if rewards else (),
        requirement=requirement,
        hook=name,
    )


def _pay(cost: Cost, *rewards: Reward) -> Ability:
    """An optional arrow with no target to pick: "You may pay X -> Y" (the
    arrow cost is optional [Main p. 20] [FAQ p. 3])."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(EffectSection(rewards=rewards, costs=(cost,)),),
        mark=AbilityMark.OPTIONAL,
    )


def _discard(
    *lines: EffectSection,
    mark: AbilityMark = AbilityMark.OPTIONAL,
    armed: tuple[str, ...] = (),
) -> Ability:
    """A discard arrow: "[You may] discard a card -> ...". The first line
    carries the cost; a later line's condition reads the discarded card;
    ``armed`` keys the lines armed as icons once the cost is paid."""

    first, *rest = lines
    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(replace(first, costs=(DiscardFromHand(),)), *rest),
        mark=mark,
        armed_icons=armed,
    )


def _trash(*lines: EffectSection, armed: tuple[str, ...] = ()) -> Ability:
    """An optional trash box: black trash icons [FAQ p. 3], or an arrow whose
    first line carries a ``TrashCard`` cost."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=lines,
        mark=AbilityMark.OPTIONAL,
        armed_icons=armed,
    )


def _icons(*lines: tuple[str, EffectSection]) -> Ability:
    """A box whose printed icons resolve one action each (OQ-027)."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=tuple(section for _, section in lines),
        structure=AbilityStructure.SEPARATE,
        icons=tuple(key for key, _ in lines),
    )


AGENT_BOX_ABILITIES: Final[Mapping[PersonalCardAgentEffect, Ability]] = (
    MappingProxyType(
        {
            # --- One action: gains -------------------------------------------
            _BOX.GAIN_TWO_SOLARI: _box(GainResources(solari=2)),
            _BOX.GAIN_ONE_SPICE: _box(GainResources(spice=1)),
            _BOX.GAIN_WATER: _box(GainResources(water=1)),
            _BOX.RECRUIT_TWO_TROOPS: _box(RecruitTroops(2)),
            _BOX.BOOST_NEXT_BENE_GESSERIT_CARD_THIS_ROUND: _box(
                BoostNextBeneGesseritCard()
            ),
            _BOX.GAIN_SPICE_IF_MAKER_SPACE: _box(
                GainResources(spice=1), requirement=AtMakerSpace()
            ),
            _BOX.GAIN_TWO_SPICE_IF_MAKER_SPACE: _box(
                GainResources(spice=2), requirement=AtMakerSpace()
            ),
            _BOX.RECRUIT_ONE_IF_MAKER_SPACE: _box(
                RecruitTroops(1), requirement=AtMakerSpace()
            ),
            _BOX.RECRUIT_ONE_IF_EMPEROR_INFLUENCE_TWO: _box(
                RecruitTroops(1), condition=InfluenceAtLeast(Faction.EMPEROR, 2)
            ),
            _BOX.RECRUIT_TWO_IF_BENE_GESSERIT_BOND: _box(
                RecruitTroops(2), condition=_BG_BOND, requirement=_BG_BOND
            ),
            _BOX.RETURN_SELF_IF_BENE_GESSERIT_BOND: _box(
                ReturnThisCardToHand(), condition=_BG_BOND, requirement=_BG_BOND
            ),
            _BOX.RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN: _box(
                RecruitTroops(3), condition=SpyRecalledThisTurn()
            ),
            _BOX.RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN: _box(
                RecruitTroops(2), condition=SpyRecalledThisTurn()
            ),
            _BOX.GAIN_TWO_SPICE_IF_GRAFTED: _box(
                GainResources(spice=2), condition=Grafted()
            ),
            _BOX.GAIN_TWO_SPICE_IF_EMPEROR_INFLUENCE_TWO: _box(
                GainResources(spice=2), condition=InfluenceAtLeast(Faction.EMPEROR, 2)
            ),
            # Throne Room Politics: the troop, then the black trash icon on a
            # frame of its own [Main p. 20].
            _BOX.RECRUIT_ONE_AND_MAY_TRASH: _box(RecruitTroops(1), TrashPersonalCard()),
            # --- One action: card draws ----------------------------------------
            _BOX.DRAW_PERSONAL_CARD: _box(DrawPersonalCards(1)),
            _BOX.DRAW_TWO_CARDS: _box(DrawPersonalCards(2)),
            _BOX.DRAW_PER_SANDWORM_IN_CONFLICT: _box(
                DrawPerSandwormInConflict(), condition=SandwormsInConflictAtLeast(1)
            ),
            _BOX.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: _box(
                DrawPersonalCards(1), condition=_BG_TWO
            ),
            _BOX.DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN: _box(
                DrawPersonalCards(1), condition=_TWO_SPICE
            ),
            _BOX.DRAW_TWO_IF_ONE_MARKER: _box(
                DrawPersonalCards(2), condition=GeneticMarkersAtLeast(1)
            ),
            # --- One action: Intrigue draws ------------------------------------
            _BOX.DRAW_INTRIGUE_CARD: _box(DrawIntrigueCards(1)),
            _BOX.DRAW_INTRIGUE_IF_SANDWORM_IN_CONFLICT: _box(
                DrawIntrigueCards(1), condition=SandwormsInConflictAtLeast(1)
            ),
            _BOX.DRAW_INTRIGUE_IF_CONTRACT_COMPLETED_THIS_TURN: _box(
                DrawIntrigueCards(1), condition=ContractCompletedThisTurn()
            ),
            _BOX.DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN: _box(
                DrawIntrigueCards(1), condition=SpyRecalledThisTurn()
            ),
            _BOX.DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT: _box(
                DrawIntrigueCards(1), condition=UnitsInConflictAtLeast(3)
            ),
            # --- One action: a follow-up after the box ---------------------------
            _BOX.TAKE_CONTRACT: _box(TakeContract(1)),
            _BOX.TAKE_CONTRACT_IF_SPY_RECALLED_THIS_TURN: _box(
                TakeContract(1), condition=SpyRecalledThisTurn()
            ),
            _BOX.RESEARCH: _box(Research()),
            _BOX.ADVANCE_TLEILAXU: _box(AdvanceTleilaxu(1)),
            _BOX.ADVANCE_TLEILAXU_IF_ONE_MARKER: _box(
                AdvanceTleilaxu(1), condition=GeneticMarkersAtLeast(1)
            ),
            _BOX.ADVANCE_TLEILAXU_IF_GRAFTED: _box(
                AdvanceTleilaxu(1), condition=Grafted()
            ),
            _BOX.GENERATE_SPECIMEN: _box(GenerateSpecimens(1)),
            _BOX.PEEK_TWO_INTRIGUE_KEEP_ONE: _box(LookAtIntrigueKeepOne(2)),
            # Guild Impersonator: "If you gained spice this turn: [Spacing
            # Guild Influence]".
            _BOX.GAIN_SPACING_GUILD_INFLUENCE_IF_GAINED_SPICE_THIS_TURN: _box(
                GainInfluence(factions=(Faction.SPACING_GUILD,)),
                condition=GainedSpiceThisTurn(1),
            ),
            # --- A choice of target (composed effects, A3c) ----------------------
            # Interstellar Trade, For Humanity: "Gain 1 Influence with a chosen
            # Faction".
            _BOX.GAIN_CHOSEN_INFLUENCE: _box(GainInfluence()),
            # Public Spectacle: "If you recalled a Spy this turn: ...".
            _BOX.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN: _box(
                GainInfluence(), condition=SpyRecalledThisTurn()
            ),
            # Bene Gesserit Operative, Reliable Informant: "Place a Spy"; the
            # Faction marks printed beside the Spy icon (the card's
            # ``agent_spy_factions``) limit the post.
            _BOX.PLACE_SPY: _box(PlaceSpy()),
            # Double Agent.
            _BOX.PLACE_SPY_ON_VISITED_SPACE_MAY_SHARE: _box(
                PlaceSpy(shared_post=True, visited_space=True)
            ),
            # Disruption Tactics.
            _BOX.FORCE_OPPONENT_TROOP_RETREAT: _box(ForceEnemyRetreat()),
            # CHOAM Demands.
            _BOX.COMPLETE_ONE_CONTRACT: _box(CompleteContract()),
            # --- Discard arrows (composed effects, A3d) ---------------------------
            # Delivery Agreement.
            _BOX.MAY_DISCARD_TO_TAKE_CONTRACT: _discard(_line(TakeContract(1))),
            # I Believe.
            _BOX.MAY_DISCARD_TO_DRAW_ONE: _discard(_line(DrawPersonalCards(1))),
            # Engineered Miracle.
            _BOX.MAY_DISCARD_FOR_WATER: _discard(_line(GainResources(water=1))),
            # Space-time Folding: "Draw 1 card (2 if the discarded card has
            # Spacing Guild affiliation)".
            _BOX.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD: _discard(
                _line(DrawPersonalCards(1)),
                _line(DrawPersonalCards(1), condition=_GUILD_DISCARD),
            ),
            # Captured Mentat: the rewards are armed as icons once the discard
            # is paid, each resolved on its own (OQ-027).
            _BOX.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD: _discard(
                _line(DrawIntrigueCards(1)),
                _line(DrawPersonalCards(1)),
                armed=("intrigue", "cards"),
            ),
            # Guild Spy: "Draw 1 card (also Draw 1 Intrigue card if the
            # discarded card has Spacing Guild affiliation)".
            _BOX.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD: _discard(
                _line(DrawPersonalCards(1)),
                _line(DrawIntrigueCards(1), condition=_GUILD_DISCARD),
                armed=("cards", "intrigue"),
            ),
            # Guild Envoy: the discard is not optional.
            _BOX.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD: _discard(
                _line(DrawPersonalCards(2), condition=_GUILD_DISCARD),
                mark=AbilityMark.MANDATORY,
            ),
            # --- Intrigue arrows (composed effects, A3d) --------------------------
            # Branching Path: "If Bene Gesserit Alliance: You may trash an
            # Intrigue card -> Draw 1 Intrigue card, Gain 2 spice"; the Alliance
            # over the whole arrow sits on the cost line, judged when the cost
            # is paid, and both rewards are then armed.
            _BRANCHING_PATH: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(DrawIntrigueCards(1),),
                        condition=HasAlliance(_BG),
                        costs=(TrashIntrigueCard(),),
                    ),
                    _line(GainResources(spice=2)),
                ),
                mark=AbilityMark.OPTIONAL,
                armed_icons=("intrigue", "spice"),
            ),
            # Junction Headquarters: "If Spacing Guild Alliance: You may trash
            # an Intrigue card and pay 2 spice -> Gain 1 VP".
            _JUNCTION_HEADQUARTERS: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(GainVictoryPoints(1),),
                        condition=HasAlliance(Faction.SPACING_GUILD),
                        costs=(TrashIntrigueCard(), PayResources(spice=2)),
                    ),
                ),
                mark=AbilityMark.OPTIONAL,
            ),
            # --- Trash boxes (composed effects, A3e) -----------------------------
            # Calculus of Power, Desert Survival, Eliminate Allies: "You may trash
            # a card" -- the black trash icon is the whole box.
            _BOX.TRASH_PERSONAL_CARD: _trash(_line(TrashPersonalCard())),
            # Ruthless Leadership: "If you have one or more Sardaukar Commanders
            # in the Conflict: You may trash a card, You may trash a card", the
            # condition judged at each trash (OQ-028).
            _BOX.MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT: _trash(
                _line(TrashPersonalCard(), condition=_COMMANDER_IN_CONFLICT),
                _line(TrashPersonalCard(), condition=_COMMANDER_IN_CONFLICT),
            ),
            # Shishakli, Replacement Eyes: "You may trash a card -> Draw 1 card".
            _BOX.TRASH_PERSONAL_CARD_TO_DRAW_ONE: _trash(
                EffectSection(rewards=(DrawPersonalCards(1),), costs=(TrashCard(),))
            ),
            # Pivotal Gambit: the card trashes itself as the cost, then its troop
            # and the first-place pledge are armed as icons (OQ-022, OQ-027).
            _BOX.MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE: _trash(
                EffectSection(
                    rewards=(RecruitTroops(1),), costs=(TrashCard(this_card=True),)
                ),
                _line(PledgeFirstPlaceInfluence()),
                armed=("troops", "pledge"),
            ),
            # Elite Forces: "You may trash a card from your hand. If you trash an
            # Emperor card: Draw 1 Intrigue card, Recruit 1 troop, Combat" -- the
            # draw and the troop armed as icons, the Combat paid with the trash.
            _BOX.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS: _trash(
                EffectSection(
                    rewards=(DrawIntrigueCards(1),),
                    condition=_EMPEROR_TRASH,
                    costs=(TrashCard(hand_only=True),),
                ),
                _line(RecruitTroops(1), condition=_EMPEROR_TRASH),
                _line(GrantCombatDeployment(), condition=_EMPEROR_TRASH),
                armed=("intrigue", "troops"),
            ),
            # --- Optional acquisitions (composed effects, A3f) -------------------
            # Price is No Object: "You may acquire an Imperium Row or Reserve
            # card to your hand, paying its cost in solari".
            _BOX.ACQUIRE_WITH_SOLARI_TO_HAND: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(_line(AcquireCardForSolari()),),
                mark=AbilityMark.OPTIONAL,
            ),
            # Tleilaxu Master: "If 1 genetic marker: You may acquire a card
            # costing 6 or less, If 2 genetic markers: put it in your hand",
            # both judged when the box resolves (OQ-028).
            _BOX.MAY_ACQUIRE_CARD_UP_TO_SIX_IF_ONE_MARKER: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(
                        AcquireCardUpTo(6, to_hand_if=GeneticMarkersAtLeast(2)),
                        condition=GeneticMarkersAtLeast(1),
                    ),
                ),
                mark=AbilityMark.OPTIONAL,
            ),
            # --- Optional arrows with no target (composed effects, A3b) ---------
            # Ecological Testing Station.
            _BOX.PAY_TWO_WATER_TO_DRAW_TWO: _pay(
                PayResources(water=2), DrawPersonalCards(2)
            ),
            # Smuggler's Haven.
            _BOX.MAY_PAY_FOUR_SPICE_FOR_VP: _pay(
                PayResources(spice=4), GainVictoryPoints(1)
            ),
            # Organ Merchants.
            _BOX.MAY_PAY_SPECIMEN_FOR_FOUR_SOLARI: _pay(
                SpendSpecimens(1), GainResources(solari=4)
            ),
            # Tleilaxu Surgeon.
            _BOX.MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU: _pay(
                SpendSpecimens(2), AdvanceTleilaxu(2)
            ),
            # --- Special flows (hooks) -------------------------------------------
            # Seek Allies: "Trash this card." -- the trash's events alone.
            _BOX.TRASH_SELF: _hook("seek_allies"),
            # Overthrow: one more Influence with the visited Faction, with no
            # event of its own; reachable only on a Faction space (the
            # placement code's rule, not a printed condition).
            _BOX.GAIN_VISITED_FACTION_INFLUENCE: _hook("overthrow"),
            # Lisan al Gaib: the Fremen Influence, its events alone.
            _BOX.GAIN_FREMEN_INFLUENCE_IF_BENE_GESSERIT_BOND: _hook(
                "lisan_al_gaib",
                GainInfluence(factions=(Faction.FREMEN,)),
                condition=_BG_BOND,
            ),
            # Clandestine Meeting: its Intrigue draw is named ``<box>:intrigue``.
            _BOX.GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE: _hook(
                "clandestine_meeting",
                GainInfluence(factions=(_BG,)),
                DrawIntrigueCards(1),
            ),
            # Occupation: the Combat grant rewrites the frame; the draw is
            # named ``<box>:draw``.
            _BOX.DRAW_ONE_AND_COMBAT_ICON: _hook(
                "occupation", DrawPersonalCards(1), GrantCombatDeployment()
            ),
            # In High Places: the Spy frame under the draw, both named ``<box>``.
            _BOX.DRAW_ONE_AND_PLACE_SPY_IF_BENE_GESSERIT_BOND: _hook(
                "in_high_places",
                DrawPersonalCards(1),
                PlaceSpy(),
                condition=_BG_BOND,
                requirement=_BG_BOND,
            ),
            # --- Icon by icon (OQ-027) -------------------------------------------
            # Hidden Missive.
            _BOX.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: _icons(
                ("troops", _line(RecruitTroops(1), condition=_BG_TWO)),
                ("cards", _line(DrawPersonalCards(1), condition=_BG_TWO)),
            ),
            # Maker Keeper.
            _BOX.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO: _icons(
                ("water", _line(GainResources(water=1), condition=_BG_TWO)),
                (
                    "spice",
                    _line(
                        GainResources(spice=1),
                        condition=InfluenceAtLeast(Faction.FREMEN, 2),
                    ),
                ),
            ),
            # Wheels Within Wheels.
            _BOX.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO: _icons(
                (
                    "solari",
                    _line(
                        GainResources(solari=2),
                        condition=InfluenceAtLeast(Faction.EMPEROR, 2),
                    ),
                ),
                (
                    "spice",
                    _line(
                        GainResources(spice=1),
                        condition=InfluenceAtLeast(Faction.SPACING_GUILD, 2),
                    ),
                ),
            ),
            # Fremen War Name: "If you gained [2 spice] or more this turn:".
            _BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN: _icons(
                ("troops", _line(RecruitTroops(1), condition=_TWO_SPICE)),
                ("cards", _line(DrawPersonalCards(1), condition=_TWO_SPICE)),
            ),
            # Tleilaxu Infiltrator (its "Enemy Agents don't block your Agent
            # this turn" is a placement rule, ``agent_turn``).
            _BOX.DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS: _icons(
                ("cards", _line(DrawPersonalCards(1))),
                (
                    "intrigue",
                    _line(DrawIntrigueCards(1), condition=GeneticMarkersAtLeast(2)),
                ),
            ),
            # Sardaukar Quartermaster: "If grafted: troop, draw a card".
            _BOX.RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED: _icons(
                ("troops", _line(RecruitTroops(1), condition=Grafted())),
                ("cards", _line(DrawPersonalCards(1), condition=Grafted())),
            ),
            # Cargo Runner: two printed lines, two and four completed Contracts.
            _BOX.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO: _icons(
                (
                    "cards",
                    _line(DrawPersonalCards(1), condition=CompletedContractsAtLeast(2)),
                ),
                (
                    "cards_second",
                    _line(DrawPersonalCards(1), condition=CompletedContractsAtLeast(4)),
                ),
            ),
            # Industrial Espionage: "[draw 1]" and, on its own line, "If
            # grafted: [Research] [specimen]".
            _BOX.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED: _icons(
                ("cards", _line(DrawPersonalCards(1))),
                (
                    "research",
                    _line(Research(), GenerateSpecimens(1), condition=Grafted()),
                ),
            ),
            # Stillsuit Manufacturer: "[water] —AND— [Fremen] Alliance: Return
            # this card from play to your hand."
            _BOX.GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE: _icons(
                ("water", _line(GainResources(water=1))),
                (
                    "return_self",
                    _line(
                        ReturnThisCardToHand(),
                        condition=HasAlliance(Faction.FREMEN),
                    ),
                ),
            ),
        }
    )
)


def agent_box_ability(effect: PersonalCardAgentEffect | None) -> Ability | None:
    """The record of ``effect``'s Agent box; None while its own code resolves it."""

    if effect is None:
        return None
    return AGENT_BOX_ABILITIES.get(effect)
