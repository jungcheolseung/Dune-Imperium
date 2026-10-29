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

Every personal card's Agent box has its record here (composed A3g); a
leader's Signet Ring (``LEADER_SIGNET``) keeps its own code.
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
    AtFactionSpace,
    AtMakerSpace,
    BlockChosenSpaceForOpponentsNextAgent,
    BoostNextBeneGesseritCard,
    CommandersInConflictAtLeast,
    CompleteContract,
    CompletedContractsAtLeast,
    Condition,
    ContractCompletedThisTurn,
    Cost,
    DestroyShieldWall,
    DiscardedCardHasFaction,
    DiscardFromHand,
    DoubleBaseHarvestSpice,
    DoubleBonusHarvestSpice,
    DrawIntrigueCards,
    DrawPerSandwormInConflict,
    DrawPersonalCards,
    EachOpponentDiscardsCard,
    EachOpponentDiscardsOrLosesDeployedTroop,
    EachOpponentLosesTroop,
    EffectSection,
    FactionBond,
    ForceEnemyRetreat,
    Freighter,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainSolariPerPartnerAgentIcon,
    GainVictoryPoints,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    Grafted,
    GraftedTrash,
    GraftedWithFaction,
    GrantCombatDeployment,
    HasAlliance,
    InfluenceAtLeast,
    LookAtIntrigueKeepOne,
    LoseInfluence,
    LoseTroops,
    OpponentsMoveSpiesFromVisitedSpace,
    PayResources,
    PlaceSpy,
    PledgeFirstPlaceInfluence,
    RecallAgent,
    RecruitTroops,
    Research,
    ReturnOtherGraftedCardAtRevealStart,
    ReturnThisCardToHand,
    Reward,
    SandwormsInConflictAtLeast,
    SpendSpecimens,
    SpyRecalledThisTurn,
    SummonSandworm,
    TakeCardFromDiscard,
    TakeContract,
    TrashCard,
    TrashedCardHasFaction,
    TrashIntrigueCard,
    TrashPersonalCard,
    TrashThisCard,
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
_GUILD_TWO = InfluenceAtLeast(Faction.SPACING_GUILD, 2)
_HIGH_PRIORITY_TRAVEL = (
    _BOX.DRAW_ONE_OR_COMBAT_ICON_IF_SPACING_GUILD_INFLUENCE_TWO
)
_INTERSTELLAR_CONSPIRACY = (
    _BOX.GAIN_SPICE_AND_CHOSEN_INFLUENCE_IF_GRAFTED_WITH_EMPEROR_OR_GUILD
)
_EMPEROR_TRASH = TrashedCardHasFaction(Faction.EMPEROR)
_BRANCHING_PATH = (
    _BOX.MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
)
_JUNCTION_HEADQUARTERS = (
    _BOX.MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE
)
_LOCAL_FENCE = _BOX.MAY_PAY_TWO_SPICE_FOR_FIVE_SOLARI_OR_FIVE_SOLARI_FOR_FOUR_SPICE


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
    mark: AbilityMark = AbilityMark.MANDATORY,
) -> Ability:
    """A box resolved by the named special flow (``agent_effects._BOX_HOOKS``)."""

    return Ability(
        timing=AbilityTiming.AGENT_BOX,
        sections=(_line(*rewards, condition=condition),) if rewards else (),
        mark=mark,
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
            # Crysknife (original game): one Solari.
            _BOX.GAIN_ONE_SOLARI: _box(GainResources(solari=1)),
            # Opulence (original game): three Solari.
            _BOX.GAIN_THREE_SOLARI: _box(GainResources(solari=3)),
            _BOX.GAIN_ONE_SPICE: _box(GainResources(spice=1)),
            _BOX.GAIN_WATER: _box(GainResources(water=1)),
            # Sayyadina (Rise of Ix): "[3 water] -> [1 Victory Point]".
            # An optional arrow, once per turn [DI p. 9] [FAQ p. 3].
            _BOX.MAY_PAY_THREE_WATER_FOR_VP: _pay(
                PayResources(water=3), GainVictoryPoints(1)
            ),
            # Local Fence (Rise of Ix): "[2 spice] -> [5 Solari] -OR- [5
            # Solari] -> [4 spice]" [Steam app screen pieces and text]: two
            # arrows, each optional (player-turns.md [Main p. 9] [FAQ p. 3]),
            # and "-OR-" takes one (imperium-base.md 10.1), so the owner pays
            # one or neither; each line is its own row (``payment_box``).
            _LOCAL_FENCE: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(GainResources(solari=5),),
                        costs=(PayResources(spice=2),),
                    ),
                    EffectSection(
                        rewards=(GainResources(spice=4),),
                        costs=(PayResources(solari=5),),
                    ),
                ),
                mark=AbilityMark.OPTIONAL,
                structure=AbilityStructure.ONE_OF,
            ),
            _BOX.RECRUIT_TWO_TROOPS: _box(RecruitTroops(2)),
            # Arrakis Recruiter (original game): one troop; a Combat space
            # lets the owner deploy it [DI p. 10] [FAQ p. 4].
            _BOX.RECRUIT_ONE_TROOP: _box(RecruitTroops(1)),
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
            # Desert Ambush (Rise of Ix): "For each troop you deploy this turn,
            # you may force an enemy unit to retreat." [Steam app text] -- an
            # optional target box ("may"), open all turn: each troop the owner
            # deploys this turn (OQ-029's count) buys one retreat of an enemy
            # troop or dreadnought, the owner picking it (rise-of-ix.md 6, 9.3).
            _BOX.MAY_FORCE_ENEMY_UNIT_RETREAT_FOR_EACH_TROOP_DEPLOYED: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(ForceEnemyRetreat(units=True, per_troop_deployed=True)),
                ),
                mark=AbilityMark.OPTIONAL,
            ),
            # CHOAM Demands.
            _BOX.COMPLETE_ONE_CONTRACT: _box(CompleteContract()),
            # --- Discard arrows (composed effects, A3d) ---------------------------
            # Delivery Agreement.
            _BOX.MAY_DISCARD_TO_TAKE_CONTRACT: _discard(_line(TakeContract(1))),
            # I Believe.
            _BOX.MAY_DISCARD_TO_DRAW_ONE: _discard(_line(DrawPersonalCards(1))),
            # Engineered Miracle.
            _BOX.MAY_DISCARD_FOR_WATER: _discard(_line(GainResources(water=1))),
            # Guild Chief Administrator (Rise of Ix): "[Discard] -> [Trash a
            # card]" [Steam app screen pieces]. The discard is the arrow's
            # optional cost [Rise of Ix p. 7] [FAQ p. 2], an Unload card's box
            # paid in full before the trash (rise-of-ix.md 7); the trash is a
            # black trash icon, optional once the cost is paid ("검은색 trash
            # 아이콘으로 trash하는 효과는 선택이다" [FAQ p. 3], uprising-
            # systems.md), as Control the Spice's is. The card just discarded
            # is in the discard pile, so a card to trash is always there.
            _BOX.MAY_DISCARD_TO_TRASH_A_CARD: _discard(_line(TrashPersonalCard())),
            # Space-time Folding: "Draw 1 card (2 if the discarded card has
            # Spacing Guild affiliation)".
            _BOX.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD: _discard(
                _line(DrawPersonalCards(1)),
                _line(DrawPersonalCards(1), condition=_GUILD_DISCARD),
            ),
            # Arrakis Observer: "You may discard a card -> Place a Spy with Deep
            # Cover; if you discarded a Spacing Guild card: Gain 2 spice" -- the
            # spice comes with the discard, the Spy is the box's next step.
            _BOX.MAY_DISCARD_FOR_DEEP_COVER_SPY: _discard(
                _line(PlaceSpy(shared_post=True)),
                _line(GainResources(spice=2), condition=_GUILD_DISCARD),
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
            # Guild Envoy: "[discard]" then, printed below it, "If you
            # discarded a Spacing Guild card: [card][card]" [card face] -- no
            # arrow, so the discard is no cost but the box's own mandatory
            # effect ("Agent turn에 play하면 반드시 card를 discard한다."
            # [FAQ p. 2]). The draw, a hidden draw printed apart, is armed
            # as its own step (OQ-106, user decision 2026-10-25 "Guild Envoy는
            # (가) discard와 draw를 별개 단계로 나눠"; engine audit
            # 2026-10-22, P6), as Guild Spy's is.
            _BOX.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD: _discard(
                _line(DrawPersonalCards(2), condition=_GUILD_DISCARD),
                mark=AbilityMark.MANDATORY,
                armed=("cards",),
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
            # Shai-Hulud (Rise of Ix): "[Trash a card] -> [2 troops]" [Steam app
            # screen pieces and log text]: an arrow whose cost is a trashed card,
            # optional like every arrow cost [FAQ p. 3]; the troops come at once
            # (``agent_box_abilities.apply_trash``).
            _BOX.TRASH_PERSONAL_CARD_TO_RECRUIT_TWO: _trash(
                EffectSection(rewards=(RecruitTroops(2),), costs=(TrashCard(),))
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
            # --- Unit-loss arrow, payment hook (composed effects, A3f) -----------
            # Piter, Genius Advisor: "You may lose 1 troop -> Draw 2 cards,
            # Research", the rewards armed as icons once the troop (or a
            # Sardaukar Commander, OQ-105) is lost (OQ-106).
            _BOX.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(DrawPersonalCards(2),), costs=(LoseTroops(),)
                    ),
                    _line(Research()),
                ),
                mark=AbilityMark.OPTIONAL,
                armed_icons=("cards", "research"),
            ),
            # Control the Spice: "You may pay 1 spice -> You may trash a card,
            # Recruit 1 troop" -- a paid arrow (``apply_payment``): the troop
            # now, the black trash icon on a frame of its own (cleanup-2d).
            _BOX.MAY_PAY_SPICE_TO_TRASH_AND_RECRUIT: _pay(
                PayResources(spice=1), TrashPersonalCard(), RecruitTroops(1)
            ),
            # --- A plain line beside a choice line (composed effects, A3f) ------
            # Southern Faith: "Choose one: Draw 1 card / If Bene Gesserit Bond:
            # Gain 1 Bene Gesserit Influence".
            _BOX.DRAW_ONE_OR_BENE_GESSERIT_INFLUENCE_IF_BOND: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(DrawPersonalCards(1)),
                    _line(GainInfluence(factions=(_BG,)), condition=_BG_BOND),
                ),
                structure=AbilityStructure.ONE_OF,
            ),
            # High Priority Travel: "If you have 2 or more Spacing Guild
            # Influence: Choose one: Draw 1 card / Combat".
            _HIGH_PRIORITY_TRAVEL: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(DrawPersonalCards(1), condition=_GUILD_TWO),
                    _line(GrantCombatDeployment(), condition=_GUILD_TWO),
                ),
                structure=AbilityStructure.ONE_OF,
            ),
            # Interstellar Conspiracy: "Gain 1 spice, If grafted with an Emperor
            # or Spacing Guild card: Gain 1 Influence with a chosen Faction" --
            # each icon resolves on its own, in the owner's order (OQ-027, user
            # decision 2026-10-18 "원칙대로 아이콘마다 나누자"; engine audit
            # 2026-10-22, P4): the spice may come first, to pay for another
            # effect before the Faction is chosen.
            _INTERSTELLAR_CONSPIRACY: _icons(
                ("spice", _line(GainResources(spice=1))),
                (
                    "influence",
                    _line(
                        GainInfluence(),
                        condition=GraftedWithFaction(
                            (Faction.EMPEROR, Faction.SPACING_GUILD)
                        ),
                    ),
                ),
            ),
            # Possible Futures: "Choose one: Gain 1 Influence with a chosen
            # Faction / Recruit 2 troops; if Bene Gesserit Bond: get both" -- the
            # Bond turns the choice into both, named apart, so the flow stays code
            # (``agent_effects`` hook ``possible_futures``).
            _BOX.CHOSEN_INFLUENCE_OR_TWO_TROOPS_BOTH_IF_BOND: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(_line(GainInfluence()), _line(RecruitTroops(2))),
                structure=AbilityStructure.ONE_OF,
                hook="possible_futures",
            ),
            # --- Printed icons with a choice icon (composed effects, A3f) -------
            # Each icon resolves on its own (OQ-027); a choice icon is answered
            # by its own rows (the Influence choice, the Agent recall, the trash),
            # an automatic one by ``resolve_agent_card_effect(effect=...)``.
            # Dangerous Rhetoric: "Trash this card, Gain 1 Influence with a chosen
            # Faction" -- queued Influence first, the order the old engine kept.
            _BOX.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE: _icons(
                ("influence", _line(GainInfluence())),
                ("trash_self", _line(TrashThisCard())),
            ),
            # Clandestine Meeting: "[Bene Gesserit Influence] [Intrigue card]"
            # -- the Influence answered by its one-Faction row (cleanup-2d-5,
            # user decision 2026-10-18: "원칙대로 아이콘마다 나누자").
            _BOX.GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE: _icons(
                ("influence", _line(GainInfluence(factions=(_BG,)))),
                ("intrigue", _line(DrawIntrigueCards(1))),
            ),
            # Occupation: "[draw 1] [Combat]" [Immortality p. 16] -- the Combat
            # icon answered by ``take_agent_card_combat_icon`` (cleanup-2d-5).
            _BOX.DRAW_ONE_AND_COMBAT_ICON: _icons(
                ("cards", _line(DrawPersonalCards(1))),
                ("combat", _line(GrantCombatDeployment())),
            ),
            # Foldspace (the original game's Reserve): "Draw 1 card" and "Trash
            # this card", separate effects (designer ruling, BGG Forum;
            # docs/rules/imperium-base.md 13.3); trashed by its own effect it
            # keeps the draw (OQ-022's designer follow-up).
            _BOX.DRAW_ONE_AND_TRASH_SELF: _icons(
                ("cards", _line(DrawPersonalCards(1))),
                ("trash_self", _line(TrashThisCard())),
            ),
            # Steersman: "Draw 1 card, Recall 1 Agent".
            _BOX.DRAW_ONE_AND_RECALL_AGENT: _icons(
                ("cards", _line(DrawPersonalCards(1))),
                ("recall", _line(RecallAgent())),
            ),
            # Twisted Mentat: "You may recall the Agent you sent this turn" (an
            # optional icon, ``agent_effects.OPTIONAL_AGENT_ICONS``).
            _BOX.MAY_RECALL_AGENT_SENT_THIS_TURN: _icons(
                ("recall", _line(RecallAgent(sent_this_turn=True, optional=True))),
            ),
            # Landing Rights (Rise of Ix): the Freighter icon [Steam app screen
            # pieces]: "you may move your Freighter in one of two ways" [Rise
            # of Ix p. 5] (docs/rules/rise-of-ix.md 5). An optional icon
            # (``agent_effects.OPTIONAL_AGENT_ICONS``) answered by its own rows
            # (``advance_agent_card_freighter``, ``recall_agent_card_freighter``).
            _BOX.MAY_MOVE_FREIGHTER: _icons(("freighter", _line(Freighter()))),
            # Tread in Darkness: "If Bene Gesserit Bond: You may trash a card,
            # Draw 1 card" -- the Bond opens the box and is judged again on each
            # icon when it resolves (OQ-028); the trash stays optional (OQ-058).
            _BOX.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(TrashPersonalCard(), condition=_BG_BOND),
                    _line(DrawPersonalCards(1), condition=_BG_BOND),
                ),
                structure=AbilityStructure.SEPARATE,
                requirement=_BG_BOND,
                icons=("trash", "cards"),
            ),
            # In High Places: "If you have another Bene Gesserit card in play:
            # [draw 1 card] [Spy]" -- as Tread in Darkness, the Bond opens the
            # box and is judged again on each icon (OQ-028); the Spy icon is
            # answered by the box's Spy rows (cleanup-2d-5).
            _BOX.DRAW_ONE_AND_PLACE_SPY_IF_BENE_GESSERIT_BOND: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(DrawPersonalCards(1), condition=_BG_BOND),
                    _line(PlaceSpy(), condition=_BG_BOND),
                ),
                structure=AbilityStructure.SEPARATE,
                requirement=_BG_BOND,
                icons=("cards", "spy"),
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
            # Spice Smugglers (original game): "[2 spice] -> [Spacing Guild
            # Influence] [3 Solari]" -- a paid arrow whose two rewards wait as
            # icons once the spice is paid, each its own step in the owner's
            # order: user ruling 2026-10-29 (OQ-148 (가)), as Duncan Idaho's
            # (OQ-027, OQ-106). The Solari keep it worth paying at the top of
            # the Guild's track (OQ-060, OQ-071).
            _BOX.MAY_PAY_TWO_SPICE_FOR_SPACING_GUILD_INFLUENCE_AND_THREE_SOLARI: (
                Ability(
                    timing=AbilityTiming.AGENT_BOX,
                    sections=(
                        EffectSection(
                            rewards=(GainInfluence(factions=(Faction.SPACING_GUILD,)),),
                            costs=(PayResources(spice=2),),
                        ),
                        _line(GainResources(solari=3)),
                    ),
                    mark=AbilityMark.OPTIONAL,
                    armed_icons=("influence", "solari"),
                )
            ),
            # Fremen Camp (original game): "[2 spice] -> [3 troops]" -- a paid
            # arrow, the troops recruited at once [DI p. 9] [FAQ p. 3].
            _BOX.MAY_PAY_TWO_SPICE_FOR_THREE_TROOPS: _pay(
                PayResources(spice=2), RecruitTroops(3)
            ),
            # Duncan Idaho (original game): "[1 water] -> [troop] [draw 1
            # card]" -- a paid arrow whose two rewards wait as icons once the
            # water is paid, each its own step (OQ-027 (b), OQ-106).
            _BOX.MAY_PAY_ONE_WATER_FOR_TROOP_AND_DRAW_ONE: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(RecruitTroops(1),), costs=(PayResources(water=1),)
                    ),
                    _line(DrawPersonalCards(1)),
                ),
                mark=AbilityMark.OPTIONAL,
                armed_icons=("troops", "cards"),
            ),
            # --- One action with follow-ups for the opponents (composed A3g) -----
            # Covert Operation: "Each opponent discards a card" -- one frame per
            # opponent holding a card, named ``<box>:opponent:<seat>``.
            _BOX.EACH_OPPONENT_DISCARDS_PERSONAL_CARD: _box(EachOpponentDiscardsCard()),
            # Gun Thopter (original game): "Each opponent loses one garrisoned
            # troop" -- Holy War's window, each loss limited to the garrison;
            # an opponent with none is unaffected [FAQ p. 2].
            _BOX.EACH_OPPONENT_LOSES_GARRISON_TROOP: _box(
                EachOpponentLosesTroop(garrison_only=True)
            ),
            # Holy War: "Each opponent loses one troop. Each opponent spying on
            # the board space where you sent an Agent this turn must move that
            # Spy" -- every loss first, then the Spy moves (OQ-036).
            _BOX.EACH_OPPONENT_LOSES_TROOP_AND_MOVES_SPY: _box(
                EachOpponentLosesTroop(), OpponentsMoveSpiesFromVisitedSpace()
            ),
            # Chairdog: "At the start of your Reveal turn, return the other
            # grafted card from play to your hand" -- noted at the graft; the box
            # waits while that card is out of play.
            _BOX.RETURN_OTHER_GRAFTED_TO_HAND_AT_REVEAL_START: _box(
                ReturnOtherGraftedCardAtRevealStart()
            ),
            # --- Special flows (hooks) -------------------------------------------
            # Seek Allies: "Trash this card." [Main p. 20] -- the box trashes
            # its own card (cleanup-2d).
            _BOX.TRASH_SELF: _box(TrashThisCard()),
            # Overthrow: "Gain two Influence instead of one." [Overthrow card]
            # -- the 2 replace the visited Faction space's 1, as Subversive
            # Advisor's and Treacherous Maneuver's do (OQ-046, OQ-128, user
            # ruling 2026-10-25 "이건 통일하는게 맞아"); nothing to gain off a
            # Faction space.
            _BOX.GAIN_VISITED_FACTION_INFLUENCE: _box(
                GainInfluence(visited_space=True, times=2, replaces_space=True),
                requirement=AtFactionSpace(),
            ),
            # Lisan al Gaib: the Fremen Influence, the Bond judged when the box
            # resolves (a grafted partner may give it).
            _BOX.GAIN_FREMEN_INFLUENCE_IF_BENE_GESSERIT_BOND: _box(
                GainInfluence(factions=(Faction.FREMEN,)), condition=_BG_BOND
            ),
            # --- Special flows of the boxes no stage listed (composed A3g) -------
            # Their rows, events and frames are their own. A record lists its
            # lines when the DSL can say the whole box; a box it cannot say
            # whole has no line (a part alone would misread as the box), its
            # printed text in the comment.
            # Subversive Advisor: "Gain 2 Influence with the visited Faction,
            # Trash this card" -- the 2 replace the space's 1 (never 2 + 1).
            _BOX.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF: _box(
                GainInfluence(visited_space=True, times=2, replaces_space=True),
                TrashThisCard(),
                requirement=AtFactionSpace(),
            ),
            # Long Live the Fighters: "If you have 3 or more cards in your deck:
            # Look at the top 3 cards, Draw 1, Discard 1, Trash 1" -- the
            # owner's pick frame over the pending box.
            _BOX.LOOK_AT_TOP_THREE: _hook("long_live_the_fighters"),
            # Treacherous Maneuver: "You may trash this card and an Emperor card
            # from your hand -> Gain 2 Influence instead of 1 Influence with the
            # visited Faction" -- a trash box: the hand's Emperor card is the
            # pick, this card follows it (cleanup-2d).
            _BOX.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(
                            GainInfluence(
                                visited_space=True, times=2, replaces_space=True
                            ),
                        ),
                        costs=(
                            TrashCard(hand_only=True, faction=Faction.EMPEROR),
                            TrashCard(this_card=True),
                        ),
                    ),
                ),
                mark=AbilityMark.OPTIONAL,
            ),
            # Corrinth City: "You may discard 2 cards and pay 5 solari -> Gain 1
            # VP" -- the two discards picked one by one, then all paid at once
            # (a discard-and-pay arrow, cleanup-2d).
            _BOX.MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(GainVictoryPoints(1),),
                        costs=(DiscardFromHand(2), PayResources(solari=5)),
                    ),
                ),
                mark=AbilityMark.OPTIONAL,
            ),
            # Arrakis Revolt: "If Maker Hooks: You may pay 2 spice -> You may
            # remove the Shield Wall, Summon 1 sandworm" -- the removal folded
            # into the payment row (OQ-026; a wall-and-worm arrow, cleanup-2d).
            _BOX.MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS: (
                Ability(
                    timing=AbilityTiming.AGENT_BOX,
                    sections=(
                        EffectSection(
                            rewards=(
                                DestroyShieldWall(),
                                SummonSandworm(requires_maker_hooks=True),
                            ),
                            costs=(PayResources(spice=2),),
                        ),
                    ),
                    mark=AbilityMark.OPTIONAL,
                )
            ),
            # The Beast's Spoils: "Gain rewards for your face-up battle icons:
            # Crysknife: You may trash a card, Desert Mouse: Gain 1 spice,
            # Ornithopter: Recruit 1 troop".
            _BOX.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON: _hook("beasts_spoils"),
            # Long Reach: "Choose two Factions: Gain 1 Influence with each" --
            # both named before either is paid (a target choice, cleanup-2d).
            _BOX.GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE: _box(
                GainInfluence(times=2, distinct=True)
            ),
            # Dissecting Kit: "You may trash the other grafted card -> Generate
            # 1 specimen" (cleanup-2d).
            _BOX.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN: _pay(
                TrashCard(grafted=GraftedTrash.OTHER), GenerateSpecimens(1)
            ),
            # Scientific Breakthrough: "Research, If 2 genetic markers: You may
            # trash this card -> Gain 1 VP" -- the trash line judged once the
            # Research has settled.
            _BOX.RESEARCH_AND_MAY_TRASH_SELF_FOR_VP_IF_TWO_MARKERS: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(Research()),
                    EffectSection(
                        rewards=(GainVictoryPoints(1),),
                        condition=GeneticMarkersAtLeast(2),
                        costs=(TrashCard(this_card=True),),
                    ),
                ),
                structure=AbilityStructure.SEPARATE,
                hook="scientific_breakthrough",
            ),
            # Slig Farmer: "Gain 1 solari per Agent icon on the other grafted
            # card, You may pay 5 solari -> Advance the Tleilaxu track" -- the
            # payment row pays the Solari too (cleanup-2d).
            _BOX.GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU: (
                Ability(
                    timing=AbilityTiming.AGENT_BOX,
                    sections=(
                        _line(GainSolariPerPartnerAgentIcon()),
                        EffectSection(
                            rewards=(AdvanceTleilaxu(1),),
                            costs=(PayResources(solari=5),),
                        ),
                    ),
                )
            ),
            # Stitched Horror: "Choose two: Gain 1 water / Recruit 1 troop /
            # Trash a card / Advance the Tleilaxu track" -- both named before
            # either is paid (cleanup-2d).
            _BOX.CHOOSE_TWO_OF_WATER_TROOP_TRASH_TLEILAXU: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(GainResources(water=1)),
                    _line(RecruitTroops(1)),
                    _line(TrashPersonalCard()),
                    _line(AdvanceTleilaxu(1)),
                ),
                structure=AbilityStructure.CHOOSE_TWO,
            ),
            # Beguiling Pheromones: "If you sent an Agent to a Faction space this
            # turn: Trash one of the grafted cards, Gain 1 Influence with that
            # Faction".
            # Its "If you sent an Agent to a Faction space this turn" is the
            # visited Faction's gain (no Faction, nothing offered; cleanup-2d).
            _BOX.TRASH_GRAFTED_CARD_FOR_VISITED_FACTION_INFLUENCE: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(GainInfluence(visited_space=True),),
                        costs=(TrashCard(grafted=GraftedTrash.EITHER),),
                    ),
                ),
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
            # Smuggler's Thopter (original game): "Spacing Guild Influence 2:
            # [draw] [draw]" -- two printed draw icons, each its own step with
            # the Influence judged when it resolves (OQ-027, OQ-028, OQ-106).
            _BOX.DRAW_TWO_IF_SPACING_GUILD_INFLUENCE_TWO: _icons(
                ("cards", _line(DrawPersonalCards(1), condition=_GUILD_TWO)),
                ("cards_second", _line(DrawPersonalCards(1), condition=_GUILD_TWO)),
            ),
            # Worm Riders (original game): two spice.
            _BOX.GAIN_TWO_SPICE: _box(GainResources(spice=2)),
            # Guild Ambassador (original game): "[Spacing Guild Influence] -OR-
            # [2 spice]" -- a printed -OR- the owner must settle (the P0
            # sweep's "choose one (must)"; Southern Faith's plain-beside-choice
            # shape). The 2 spice is the plain line, the Influence the choice
            # line; a track at 6 gains nothing (OQ-060), so only the spice is
            # then offered.
            _BOX.GAIN_SPACING_GUILD_INFLUENCE_OR_TWO_SPICE: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(GainResources(spice=2)),
                    _line(GainInfluence(factions=(Faction.SPACING_GUILD,))),
                ),
                structure=AbilityStructure.ONE_OF,
            ),
            # The Voice (original game): "Choose any board space. Opponents can't
            # send their next Agents there this round." -- one mandatory target
            # choice among every board space on the table (imperium-base.md 15):
            # its rows are the spaces (``agent_box_abilities.target_rows``), and
            # the block lands on every opponent's seat state
            # (``PlayerState.voice_blocked_space_ids``, OQ-116).
            _BOX.BLOCK_CHOSEN_SPACE_FOR_OPPONENTS_NEXT_AGENT: _box(
                BlockChosenSpaceForOpponentsNextAgent()
            ),
            # Other Memory (original game): "[draw 1] -OR- Draw a Bene Gesserit
            # card from your discard pile" -- a printed -OR- the owner must
            # settle (the P0 sweep's "choose one (must)"; Guild Ambassador's
            # plain-beside-choice shape). The draw is the plain line, its own
            # hidden step (OQ-106); the card taken from the discard pile is the
            # choice line, offered only with a Bene Gesserit card there.
            _BOX.DRAW_ONE_OR_BENE_GESSERIT_CARD_FROM_DISCARD: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(DrawPersonalCards(1)),
                    _line(TakeCardFromDiscard(Faction.BENE_GESSERIT)),
                ),
                structure=AbilityStructure.ONE_OF,
            ),
            # Gurney Halleck (original game): "[2 troops] [draw 1 card]" -- two
            # printed icons, each its own step in the owner's order (OQ-027);
            # the hidden draw is apart from the public recruit (OQ-106).
            _BOX.RECRUIT_TWO_AND_DRAW_ONE: _icons(
                ("troops", _line(RecruitTroops(2))),
                ("cards", _line(DrawPersonalCards(1))),
            ),
            # Imperial Spy (original game): "Trash this card -> [Intrigue card]"
            # -- the card trashes itself as the arrow's cost, then the Intrigue
            # draw is armed as an icon of its own (OQ-022, OQ-106; Pivotal
            # Gambit's shape). Trashed by anything else it draws nothing
            # [FAQ p. 2].
            _BOX.MAY_TRASH_SELF_TO_DRAW_INTRIGUE: _trash(
                EffectSection(
                    rewards=(DrawIntrigueCards(1),),
                    costs=(TrashCard(this_card=True),),
                ),
                armed=("intrigue",),
            ),
            # Missionaria Protectiva (original game): "If you have another Bene
            # Gesserit card in play: [Influence of your choice]" -- the Bond
            # opens the box at the placement and is judged again when it
            # resolves (OQ-028); a track at 6 is not offered (OQ-060).
            _BOX.GAIN_CHOSEN_INFLUENCE_IF_BENE_GESSERIT_BOND: _box(
                GainInfluence(), condition=_BG_BOND, requirement=_BG_BOND
            ),
            # Gene Manipulation (original game): "[trash] AND If you have
            # another Bene Gesserit card in play: [2 spice]" -- two printed
            # icons, each its own step in the owner's order (OQ-027), the Bond
            # judged when the spice icon resolves (OQ-028: trashing the other
            # Bene Gesserit card first loses the spice); the black trash icon is
            # optional [DI p. 16] [FAQ p. 3].
            _BOX.MAY_TRASH_AND_GAIN_TWO_SPICE_IF_BENE_GESSERIT_BOND: _icons(
                ("trash", _line(TrashPersonalCard())),
                ("spice", _line(GainResources(spice=2), condition=_BG_BOND)),
            ),
            # Reverend Mother Mohiam (original game): "If you have another Bene
            # Gesserit card in play, each opponent discards two cards" -- the
            # Bond opens the box at the placement and is judged again when it
            # resolves (OQ-028); each opponent picks, clockwise from the next
            # seat, as many as the hand holds (OQ-118, [FAQ p. 3]).
            _BOX.EACH_OPPONENT_DISCARDS_TWO_IF_BENE_GESSERIT_BOND: _box(
                EachOpponentDiscardsCard(2), condition=_BG_BOND, requirement=_BG_BOND
            ),
            # Firm Grip (original game): "[2 Solari] -> Choose one: [Spacing Guild
            # Influence] / [Bene Gesserit Influence] / [Fremen Influence]" -- an
            # optional arrow paid once [DI p. 9] [FAQ p. 3]; paid, its reward waits
            # as an icon and the owner picks the Faction (never a track at 6,
            # OQ-060). No Emperor choice.
            _BOX.MAY_PAY_TWO_SOLARI_FOR_CHOSEN_INFLUENCE: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    EffectSection(
                        rewards=(
                            GainInfluence(
                                factions=(
                                    Faction.SPACING_GUILD,
                                    Faction.BENE_GESSERIT,
                                    Faction.FREMEN,
                                )
                            ),
                        ),
                        costs=(PayResources(solari=2),),
                    ),
                ),
                mark=AbilityMark.OPTIONAL,
                armed_icons=("influence",),
            ),
            # Shifting Allegiances (original game): "[lose 1 Influence with a
            # chosen Faction] [2 spice] -> [2 Influence with one chosen
            # Faction]" -- an optional arrow paid once [DI p. 9] [FAQ p. 3]; the
            # loss and the spice are its cost, and paid, the +2 waits as an
            # armed "influence" icon whose Faction the owner picks (the same
            # one may be lost and gained again [FAQ p. 4]; one unbreakable
            # gain, imperium-base.md 13.3).
            _BOX.MAY_LOSE_INFLUENCE_AND_PAY_TWO_SPICE_FOR_TWO_INFLUENCE: (
                Ability(
                    timing=AbilityTiming.AGENT_BOX,
                    sections=(
                        EffectSection(
                            rewards=(GainInfluence(times=2, one_faction=True),),
                            costs=(LoseInfluence(1), PayResources(spice=2)),
                        ),
                    ),
                    mark=AbilityMark.OPTIONAL,
                    armed_icons=("influence",),
                )
            ),
            # Test of Humanity (original game): "Each opponent chooses: Discard a
            # card -OR- Lose a deployed troop" -- one frame per opponent, the
            # next seat first, named ``<box>:opponent:<seat>`` as Covert
            # Operation's; each offers what it can do (imperium-base.md 13.1).
            _BOX.EACH_OPPONENT_DISCARDS_OR_LOSES_DEPLOYED_TROOP: _box(
                EachOpponentDiscardsOrLosesDeployedTroop()
            ),
            # Carryall (original game): "Double the base (not bonus) spice you
            # harvest with this Agent" -- the harvest reads this record
            # (``board_effects.apply_maker_space_action``); there is nothing to
            # resolve, so the box never opens (``AbilityMark.AUTOMATIC``,
            # ``agent_box_abilities.opens_at_placement``).
            _BOX.DOUBLE_BASE_HARVEST_SPICE: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(_line(DoubleBaseHarvestSpice()),),
                mark=AbilityMark.AUTOMATIC,
            ),
            # Thumper (promo): "Double the bonus spice you harvest with this
            # Agent" -- Carryall's shape for the bonus; the harvest reads this
            # record and the box never opens.
            _BOX.DOUBLE_BONUS_HARVEST_SPICE: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(_line(DoubleBonusHarvestSpice()),),
                mark=AbilityMark.AUTOMATIC,
            ),
            # Jessica of Arrakis (promo): "If you have another Bene Gesserit card
            # in play: [draw 1] [draw 1]" -- the Bond opens the box at the
            # placement and is judged again on each icon when it resolves
            # (OQ-028), each draw its own step (OQ-027, OQ-106); Smuggler's
            # Thopter's two draw icons (``cards`` / ``cards_second``) under
            # Tread in Darkness's Bond.
            _BOX.DRAW_TWO_IF_BENE_GESSERIT_BOND: Ability(
                timing=AbilityTiming.AGENT_BOX,
                sections=(
                    _line(DrawPersonalCards(1), condition=_BG_BOND),
                    _line(DrawPersonalCards(1), condition=_BG_BOND),
                ),
                structure=AbilityStructure.SEPARATE,
                requirement=_BG_BOND,
                icons=("cards", "cards_second"),
            ),
        }
    )
)


def agent_box_ability(effect: PersonalCardAgentEffect | None) -> Ability | None:
    """The record of ``effect``'s Agent box; None while its own code resolves it."""

    if effect is None:
        return None
    return AGENT_BOX_ABILITIES.get(effect)
