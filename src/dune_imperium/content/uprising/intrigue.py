"""Identities and transcribed play data for the 44-card Uprising Intrigue deck."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import (
    CardDefinition,
    DeckCardEntry,
    SourceDocument,
    SourceRef,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    AcquireReserveCard,
    CommanderDiscountThisTurn,
    CommandersInConflictAtLeast,
    CompletedContractsAtLeast,
    DeployFromGarrison,
    DestroyShieldWall,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    FlipBattleCard,
    FlipFaceUpConflictCard,
    GainCombatStrength,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainSolariPerUnitType,
    GainVictoryPoints,
    GiveIntrigueToOpponent,
    GrantAgentIconsThisTurn,
    GrantAgentIconThisTurn,
    GrantCombatDeployment,
    HasAlliance,
    HasHighCouncil,
    IgnoreInfluenceRequirementsThisTurn,
    InfluenceAtLeast,
    InNavigationSlot,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
    LoseTroops,
    OnRevealAcquisitionThisRound,
    OnUnitsDeployedInTurn,
    OpponentAllianceInfluenceAtLeast,
    PassTurn,
    PayResources,
    PeekTopCard,
    PermanentRevealPersuasion,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    RedirectSpiesOnTurnSpace,
    RetreatTroops,
    RevealContractsTakeOne,
    SandwormsInConflictAtLeast,
    SetAsideImperiumRowCard,
    SpiceMustFlowCardsAtLeast,
    SpiesPlacedAtLeast,
    SummonSandworm,
    TakeContract,
    TrashDiscardPileCard,
    TrashIntrigueCard,
    TrashPersonalCard,
    Trigger,
    TriggeredByFaction,
    WaterAtLeast,
)
from dune_imperium.content.uprising.types import AgentIcon, BattleIcon

BASE_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)
CHOAM_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 16)),)
BLOODLINES_SOURCES: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (2, 3)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)


@dataclass(frozen=True, slots=True)
class IntrigueCardEntry(DeckCardEntry):
    """One Intrigue identity plus its transcribed play options.

    ``options`` lists the alternative ways to play the card. A card printed as
    ``A —OR— B`` has two options; a card with several stacked lines has one
    option with several sections. ``play_data_complete`` marks that every
    printed option is transcribed and executable by the rules engine.
    """

    options: tuple[IntrigueOption, ...] = ()
    # Piter De Vries' Twisted Intrigue: never in the shared deck, dealt from
    # his own face-down deck; still an Intrigue card once held.
    twisted: bool = False
    # Steersman Y'rkoon's Navigation cards: not Intrigue cards at all, but
    # transcribed in the same effect DSL and resolved by the same choice
    # frames (``rules.navigation``).
    navigation: bool = False

    @property
    def play_data_complete(self) -> bool:
        """Return whether every printed option is transcribed."""

        return bool(self.options)

    @property
    def timings(self) -> frozenset[IntrigueTiming]:
        """Return every timing at which some option can be played."""

        return frozenset(option.timing for option in self.options)


def _plot(*sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(timing=IntrigueTiming.PLOT, sections=sections)


def _plot_trigger(trigger: Trigger, *sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(
        timing=IntrigueTiming.PLOT, sections=sections, trigger=trigger
    )


def _combat(*sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(timing=IntrigueTiming.COMBAT, sections=sections)


def _endgame(*sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(timing=IntrigueTiming.ENDGAME, sections=sections)


def _spice_or_endgame_flip(icon: BattleIcon) -> tuple[IntrigueOption, ...]:
    return (
        _plot(EffectSection(rewards=(GainResources(spice=1),))),
        _endgame(
            EffectSection(
                costs=(FlipBattleCard(icon),),
                rewards=(GainVictoryPoints(1),),
            )
        ),
    )


def _entry(
    catalog_id: int,
    slug: str,
    name: str,
    *,
    copies: int = 1,
    choam_only: bool = False,
    bloodlines_only: bool = False,
    tech_only: bool = False,
    options: tuple[IntrigueOption, ...] = (),
    twisted: bool = False,
) -> IntrigueCardEntry:
    expansion = "bloodlines" if bloodlines_only else "uprising"
    return IntrigueCardEntry(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=(
                BLOODLINES_SOURCES
                if bloodlines_only
                else CHOAM_SOURCES
                if choam_only
                else BASE_SOURCES
            ),
            catalog_url=f"https://dunecardshub.com/cards/{catalog_id}/{expansion}-{slug}",
        ),
        copies=copies,
        choam_only=choam_only,
        bloodlines_only=bloodlines_only,
        tech_only=tech_only,
        options=options,
        twisted=twisted,
    )


def _navigation(number: int, *options: IntrigueOption) -> IntrigueCardEntry:
    """One Navigation card (Steersman Y'rkoon), from the card face."""

    return IntrigueCardEntry(
        card=CardDefinition(
            card_id=f"navigation_card_{number}",
            name=f"Navigation Card {number}",
            sources=BLOODLINES_SOURCES,
            catalog_url=(
                "https://dunecardshub.com/images/"
                f"bloodlines-other-navigation-card-{number}.webp"
            ),
        ),
        bloodlines_only=True,
        options=options,
        navigation=True,
    )


def _twisted(slug: str, name: str, *options: IntrigueOption) -> IntrigueCardEntry:
    """One Twisted Intrigue card (Piter De Vries), from the card face."""

    return IntrigueCardEntry(
        card=CardDefinition(
            card_id=f"twisted_{slug.replace('-', '_')}",
            name=f"Twisted Intrigue: {name}",
            sources=BLOODLINES_SOURCES,
            catalog_url=(
                f"https://dunecardshub.com/images/bloodlines-other-twisted-intrigue-{slug}.webp"
            ),
        ),
        bloodlines_only=True,
        options=options,
        twisted=True,
    )


INTRIGUE_CARDS: Final = (
    _entry(
        448,
        "backed-by-choam",
        "Backed by CHOAM",
        choam_only=True,
        options=(
            _plot(
                EffectSection(
                    costs=(LoseInfluence(1),),
                    rewards=(GainResources(solari=4),),
                )
            ),
            _combat(
                EffectSection(
                    condition=CompletedContractsAtLeast(2),
                    rewards=(GainCombatStrength(4),),
                )
            ),
        ),
    ),
    _entry(
        139,
        "buy-access",
        "Buy Access",
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(solari=5),),
                    rewards=(GainInfluence(times=2, distinct=True),),
                )
            ),
        ),
    ),
    _entry(
        138,
        "call-to-arms",
        "Call to Arms",
        options=(
            _plot_trigger(
                OnRevealAcquisitionThisRound(),
                EffectSection(rewards=(RecruitTroops(1),)),
            ),
        ),
    ),
    _entry(
        135,
        "change-allegiances",
        "Change Allegiances",
        options=(
            _plot(EffectSection(costs=(LoseInfluence(1),), rewards=(GainInfluence(),))),
            _plot(
                EffectSection(
                    costs=(PayResources(spice=3),),
                    rewards=(GainInfluence(),),
                )
            ),
        ),
    ),
    _entry(
        450,
        "choam-profits",
        "CHOAM Profits",
        choam_only=True,
        options=(
            _endgame(
                EffectSection(
                    condition=CompletedContractsAtLeast(4),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
        ),
    ),
    _entry(
        147,
        "contingency-plan",
        "Contingency Plan",
        copies=3,
        options=(
            _plot(EffectSection(rewards=(GainResources(solari=2),))),
            _combat(EffectSection(rewards=(GainCombatStrength(3),))),
        ),
    ),
    _entry(
        129,
        "councilor-s-ambition",
        "Councilor's Ambition",
        options=(
            _plot(
                EffectSection(
                    condition=HasHighCouncil(),
                    rewards=(GainResources(water=2),),
                )
            ),
        ),
    ),
    _entry(
        159,
        "crysknife",
        "Crysknife",
        options=_spice_or_endgame_flip(BattleIcon.CRYSKNIFE),
    ),
    _entry(
        133,
        "cunning",
        "Cunning",
        options=(
            _plot(EffectSection(rewards=(DrawPersonalCards(1),))),
            _plot(
                EffectSection(
                    costs=(PayResources(spice=1),),
                    rewards=(DrawPersonalCards(1), TrashPersonalCard()),
                )
            ),
        ),
    ),
    _entry(
        132,
        "depart-for-arrakis",
        "Depart For Arrakis",
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(spice=2),),
                    rewards=(RecruitTroops(3),),
                ),
                EffectSection(
                    condition=InfluenceAtLeast(Faction.SPACING_GUILD, 3),
                    rewards=(DrawPersonalCards(1),),
                ),
            ),
        ),
    ),
    _entry(
        157,
        "desert-mouse",
        "Desert Mouse",
        options=_spice_or_endgame_flip(BattleIcon.DESERT_MOUSE),
    ),
    _entry(
        131,
        "detonation",
        "Detonation",
        copies=2,
        options=(
            _plot(EffectSection(rewards=(DestroyShieldWall(),))),
            _plot(EffectSection(rewards=(DeployFromGarrison(4),))),
        ),
    ),
    _entry(
        151,
        "devour",
        "Devour",
        options=(
            _combat(
                EffectSection(rewards=(GainCombatStrength(2),)),
                EffectSection(
                    condition=SandwormsInConflictAtLeast(1),
                    rewards=(GainCombatStrength(2), TrashPersonalCard()),
                ),
            ),
        ),
    ),
    _entry(
        144,
        "distraction",
        "Distraction",
        copies=2,
        options=(
            _plot_trigger(
                OnUnitsDeployedInTurn(3),
                EffectSection(rewards=(PlaceSpy(shared_post=True),)),
            ),
        ),
    ),
    _entry(
        149,
        "find-weakness",
        "Find Weakness",
        options=(
            _combat(
                EffectSection(rewards=(GainCombatStrength(2),)),
                EffectSection(
                    costs=(RecallSpy(1),),
                    rewards=(GainCombatStrength(3),),
                ),
            ),
        ),
    ),
    _entry(
        146,
        "go-to-ground",
        "Go To Ground",
        options=(
            _combat(
                EffectSection(
                    costs=(RetreatTroops(1, 2),),
                    rewards=(PlaceSpy(),),
                )
            ),
        ),
    ),
    _entry(
        140,
        "imperium-politics",
        "Imperium Politics",
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(solari=1),),
                    rewards=(
                        GainInfluence(
                            factions=(Faction.EMPEROR, Faction.SPACING_GUILD)
                        ),
                    ),
                )
            ),
        ),
    ),
    _entry(
        152,
        "impress",
        "Impress",
        options=(
            _combat(
                EffectSection(
                    rewards=(GainCombatStrength(2), AcquireCardUpTo(3)),
                )
            ),
        ),
    ),
    _entry(
        148,
        "inspire-awe",
        "Inspire Awe",
        options=(
            _plot(
                EffectSection(
                    rewards=(
                        AcquireCardUpTo(3, to_hand_if=SandwormsInConflictAtLeast(1)),
                    ),
                )
            ),
        ),
    ),
    _entry(
        142,
        "intelligence-report",
        "Intelligence Report",
        options=(
            _plot(
                EffectSection(rewards=(DrawPersonalCards(1),)),
                EffectSection(
                    condition=SpiesPlacedAtLeast(2),
                    rewards=(DrawPersonalCards(1),),
                ),
            ),
        ),
    ),
    _entry(
        447,
        "leverage",
        "Leverage",
        choam_only=True,
        options=(
            _plot(
                EffectSection(
                    condition=GainedSpiceThisTurn(1),
                    rewards=(TakeContract(1), GainResources(solari=1)),
                )
            ),
        ),
    ),
    _entry(
        143,
        "manipulate",
        "Manipulate",
        options=(_plot(EffectSection(rewards=(SetAsideImperiumRowCard(1),))),),
    ),
    _entry(
        145,
        "market-opportunity",
        "Market Opportunity",
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(spice=2),),
                    rewards=(GainResources(solari=5),),
                )
            ),
            _plot(
                EffectSection(
                    costs=(PayResources(solari=5),),
                    rewards=(GainResources(spice=5),),
                )
            ),
        ),
    ),
    _entry(
        128,
        "mercenaries",
        "Mercenaries",
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(solari=3),),
                    rewards=(DrawIntrigueCards(1), RecruitTroops(2)),
                )
            ),
        ),
    ),
    _entry(
        134,
        "opportunism",
        "Opportunism",
        options=(
            _plot(
                EffectSection(
                    costs=(LoseInfluence(2), PayResources(solari=2)),
                    rewards=(GainVictoryPoints(1),),
                ),
            ),
        ),
    ),
    _entry(
        158,
        "ornithopter",
        "Ornithopter",
        options=_spice_or_endgame_flip(BattleIcon.ORNITHOPTER),
    ),
    _entry(
        156,
        "questionable-methods",
        "Questionable Methods",
        options=(
            _combat(
                EffectSection(rewards=(GainCombatStrength(1),)),
                EffectSection(
                    costs=(LoseInfluence(1),),
                    rewards=(GainCombatStrength(4),),
                ),
            ),
        ),
    ),
    _entry(
        449,
        "reach-agreement",
        "Reach Agreement",
        choam_only=True,
        options=(
            _combat(
                EffectSection(
                    costs=(RetreatTroops(1, 2),),
                    rewards=(TakeContract(1),),
                )
            ),
        ),
    ),
    _entry(
        161,
        "secure-spice-trade",
        "Secure Spice Trade",
        options=(
            _endgame(
                EffectSection(
                    condition=SpiceMustFlowCardsAtLeast(2),
                    rewards=(GainVictoryPoints(1), GainResources(spice=2)),
                )
            ),
        ),
    ),
    _entry(
        141,
        "shaddam-s-favor",
        "Shaddam's Favor",
        options=(
            _plot(
                EffectSection(rewards=(RecruitTroops(1),)),
                EffectSection(
                    condition=InfluenceAtLeast(Faction.EMPEROR, 3),
                    rewards=(GainResources(solari=3),),
                ),
            ),
        ),
    ),
    _entry(
        160,
        "shadow-alliance",
        "Shadow Alliance",
        options=(
            _endgame(
                EffectSection(
                    condition=OpponentAllianceInfluenceAtLeast(4),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
        ),
    ),
    _entry(
        127,
        "sietch-ritual",
        "Sietch Ritual",
        options=(
            _plot(
                EffectSection(
                    costs=(DiscardFromHand(1),),
                    rewards=(
                        GainInfluence(factions=(Faction.BENE_GESSERIT, Faction.FREMEN)),
                    ),
                )
            ),
        ),
    ),
    _entry(
        136,
        "special-mission",
        "Special Mission",
        copies=2,
        options=(
            _plot(
                EffectSection(rewards=(PlaceSpy(factions=(Faction.BENE_GESSERIT,)),))
            ),
            _plot(
                EffectSection(
                    costs=(RecallSpy(1),),
                    rewards=(DestroyShieldWall(), GainResources(spice=2)),
                )
            ),
        ),
    ),
    _entry(
        150,
        "spice-is-power",
        "Spice is Power",
        options=(
            _combat(
                EffectSection(
                    costs=(RetreatTroops(3, 3),),
                    rewards=(GainResources(spice=3),),
                )
            ),
            _combat(
                EffectSection(
                    costs=(PayResources(spice=3),),
                    rewards=(GainCombatStrength(6),),
                )
            ),
        ),
    ),
    _entry(
        153,
        "spring-the-trap",
        "Spring The Trap",
        options=(
            _combat(
                EffectSection(
                    costs=(RecallSpy(2),),
                    rewards=(GainCombatStrength(7),),
                )
            ),
        ),
    ),
    _entry(
        130,
        "strategic-stockpiling",
        "Strategic Stockpiling",
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(spice=5),),
                    rewards=(GainVictoryPoints(1),),
                ),
                EffectSection(
                    condition=InfluenceAtLeast(Faction.FREMEN, 3),
                    costs=(PayResources(water=3),),
                    rewards=(GainVictoryPoints(1),),
                ),
            ),
        ),
    ),
    _entry(
        155,
        "tactical-option",
        "Tactical Option",
        options=(
            _combat(EffectSection(rewards=(GainCombatStrength(2),))),
            _combat(EffectSection(rewards=(RetreatTroops(1, None),))),
        ),
    ),
    _entry(
        137,
        "unexpected-allies",
        "Unexpected Allies",
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(water=2),),
                    rewards=(DestroyShieldWall(), SummonSandworm(1)),
                )
            ),
        ),
    ),
    _entry(
        154,
        "weirding-combat",
        "Weirding Combat",
        options=(
            _combat(
                EffectSection(rewards=(GainCombatStrength(3),)),
                EffectSection(
                    condition=InfluenceAtLeast(Faction.BENE_GESSERIT, 3),
                    rewards=(GainCombatStrength(2),),
                ),
            ),
        ),
    ),
    # Bloodlines Intrigue cards (2026-09-07): 15 retail + 1 CHOAM-only + 2
    # Tech-only [Bloodlines pp. 2-3]; options are transcribed from the card
    # faces slice by slice (an entry without options stays out of the deck).
    _entry(
        109,
        "adaptive-tactics",
        "Adaptive Tactics",
        bloodlines_only=True,
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(spice=1),),
                    rewards=(RecruitTroops(1), GrantCombatDeployment()),
                )
            ),
        ),
    ),
    _entry(
        110,
        "battlefield-research",
        "Battlefield Research",
        bloodlines_only=True,
        tech_only=True,
    ),
    _entry(
        111,
        "coercive-negotiation",
        "Coercive Negotiation",
        bloodlines_only=True,
        choam_only=True,
        options=(
            _plot_trigger(
                OnUnitsDeployedInTurn(3),
                EffectSection(rewards=(RevealContractsTakeOne(3),)),
            ),
        ),
    ),
    _entry(
        112,
        "desert-support",
        "Desert Support",
        bloodlines_only=True,
        options=(
            _combat(
                EffectSection(
                    costs=(PayResources(water=1),),
                    rewards=(GainCombatStrength(5),),
                )
            ),
        ),
    ),
    _entry(
        113,
        "emperor-s-invitation",
        "Emperor's Invitation",
        bloodlines_only=True,
        options=(
            _plot(EffectSection(rewards=(DrawPersonalCards(1),))),
            _plot(EffectSection(rewards=(GrantAgentIconThisTurn(AgentIcon.EMPEROR),))),
        ),
    ),
    _entry(
        114,
        "false-orders",
        "False Orders",
        bloodlines_only=True,
        options=(_plot(EffectSection(rewards=(RedirectSpiesOnTurnSpace(),))),),
    ),
    _entry(
        115,
        "grasp-arrakis",
        "Grasp Arrakis",
        bloodlines_only=True,
        options=(
            _combat(EffectSection(rewards=(GainCombatStrength(3),))),
            _combat(
                EffectSection(
                    costs=(FlipFaceUpConflictCard(2),),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
            _endgame(
                EffectSection(
                    costs=(FlipFaceUpConflictCard(2),),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
        ),
    ),
    _entry(
        116,
        "honor-guard",
        "Honor Guard",
        bloodlines_only=True,
        options=(
            _plot(
                EffectSection(
                    rewards=(RecruitTroops(1), CommanderDiscountThisTurn(1)),
                )
            ),
        ),
    ),
    _entry(
        117,
        "insider-information",
        "Insider Information",
        bloodlines_only=True,
        options=(
            _plot(
                EffectSection(
                    costs=(RecallSpy(1),),
                    rewards=(TrashPersonalCard(), DrawPersonalCards(1)),
                )
            ),
            _plot(EffectSection(rewards=(IgnoreInfluenceRequirementsThisTurn(),))),
        ),
    ),
    _entry(
        118,
        "rapid-engineering",
        "Rapid Engineering",
        bloodlines_only=True,
        tech_only=True,
    ),
    _entry(
        119,
        "return-the-favor",
        "Return the Favor",
        bloodlines_only=True,
        options=(
            # "1 sword. For each Faction where you have 2 Influence (or
            # more): +1 sword": one conditional line per Faction.
            _combat(
                EffectSection(rewards=(GainCombatStrength(1),)),
                *(
                    EffectSection(
                        condition=InfluenceAtLeast(faction, 2),
                        rewards=(GainCombatStrength(1),),
                    )
                    for faction in Faction
                ),
            ),
        ),
    ),
    _entry(
        120,
        "ripples-in-the-sand",
        "Ripples in the Sand",
        bloodlines_only=True,
        options=(
            _combat(
                EffectSection(rewards=(GainCombatStrength(3),)),
                EffectSection(
                    condition=SandwormsInConflictAtLeast(1),
                    rewards=(DrawIntrigueCards(1),),
                ),
            ),
        ),
    ),
    _entry(
        121,
        "sacred-pools",
        "Sacred Pools",
        bloodlines_only=True,
        options=(
            _plot(
                EffectSection(
                    costs=(DiscardFromHand(1),),
                    rewards=(GainResources(water=1),),
                )
            ),
            _endgame(
                EffectSection(
                    condition=WaterAtLeast(3),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
        ),
    ),
    _entry(
        122,
        "seize-production",
        "Seize Production",
        bloodlines_only=True,
        options=(
            _plot(EffectSection(rewards=(GainResources(solari=2),))),
            _plot(
                EffectSection(
                    condition=CommandersInConflictAtLeast(1),
                    rewards=(GainResources(spice=2),),
                )
            ),
        ),
    ),
    _entry(
        123,
        "sleeper-unit",
        "Sleeper Unit",
        bloodlines_only=True,
        options=(
            _plot(
                EffectSection(
                    costs=(PayResources(solari=1),),
                    rewards=(PlaceSpy(),),
                )
            ),
            _plot(
                EffectSection(
                    costs=(RecallSpy(1),),
                    rewards=(RecruitTroops(2),),
                )
            ),
        ),
    ),
    _entry(
        124,
        "tenuous-bond",
        "Tenuous Bond",
        bloodlines_only=True,
        options=(
            _plot(
                EffectSection(
                    costs=(LoseInfluence(1),),
                    rewards=(GainInfluence(),),
                )
            ),
            _combat(
                EffectSection(
                    costs=(LoseInfluence(1),),
                    rewards=(GainInfluence(),),
                )
            ),
            _plot(
                EffectSection(
                    costs=(TrashDiscardPileCard(1),),
                    rewards=(GainCombatStrength(4),),
                )
            ),
            _combat(
                EffectSection(
                    costs=(TrashDiscardPileCard(1),),
                    rewards=(GainCombatStrength(4),),
                )
            ),
        ),
    ),
    _entry(
        125,
        "the-strong-survive",
        "The Strong Survive",
        bloodlines_only=True,
        options=(
            _combat(EffectSection(rewards=(GainCombatStrength(3),))),
            _combat(
                EffectSection(
                    costs=(RetreatTroops(1, 1),),
                    rewards=(TrashPersonalCard(),),
                )
            ),
        ),
    ),
    _entry(
        126,
        "withdrawal-agreement",
        "Withdrawal Agreement",
        bloodlines_only=True,
        options=(
            _combat(
                EffectSection(
                    costs=(RetreatTroops(3, 3),),
                    rewards=(GainInfluence(),),
                )
            ),
        ),
    ),
    # --- Twisted Intrigue (Piter De Vries), card faces 2026-09-07 ---------
    _twisted(
        "ambitious",
        "Ambitious",
        _plot(
            EffectSection(
                costs=(LoseTroops(3),),
                rewards=(GainInfluence(where_opponent_leads=True),),
            )
        ),
    ),
    _twisted(
        "calculating",
        "Calculating",
        _plot(EffectSection(rewards=(GainSolariPerUnitType(),))),
    ),
    _twisted(
        "controlled",
        "Controlled",
        _plot(EffectSection(rewards=(PeekTopCard(),))),
        _combat(EffectSection(rewards=(GainCombatStrength(1),))),
    ),
    _twisted(
        "devious",
        "Devious",
        _plot(
            EffectSection(rewards=(TrashPersonalCard(hand_only=True, mandatory=True),))
        ),
        _plot(EffectSection(rewards=(DeployFromGarrison(2),))),
    ),
    _twisted(
        "discerning",
        "Discerning",
        _plot(
            EffectSection(costs=(DiscardFromHand(1),), rewards=(DrawPersonalCards(1),))
        ),
        _plot(EffectSection(condition=HasAlliance(), rewards=(DrawPersonalCards(1),))),
    ),
    _twisted(
        "insidious",
        "Insidious",
        _plot(
            EffectSection(
                costs=(GiveIntrigueToOpponent(bonus_spice_if_not_twisted=1),),
                rewards=(GainResources(spice=1),),
            )
        ),
    ),
    _twisted(
        "resourceful",
        "Resourceful",
        _plot(
            EffectSection(
                rewards=(
                    GrantAgentIconsThisTurn(
                        (AgentIcon.LANDSRAAD, AgentIcon.CITY, AgentIcon.SPICE_TRADE)
                    ),
                )
            )
        ),
    ),
    _twisted(
        "sadistic",
        "Sadistic",
        _plot(EffectSection(costs=(LoseTroops(1),), rewards=(DrawPersonalCards(1),))),
    ),
    _twisted(
        "shrewd",
        "Shrewd",
        _combat(
            EffectSection(
                costs=(LoseTroops(1, from_conflict=True),),
                rewards=(GainResources(spice=1),),
            )
        ),
    ),
    _twisted(
        "sinister",
        "Sinister",
        _combat(
            EffectSection(
                costs=(LoseTroops(2),),
                rewards=(DrawIntrigueCards(1), GainResources(solari=1)),
            )
        ),
    ),
    _twisted(
        "unnatural",
        "Unnatural",
        _plot(
            EffectSection(
                costs=(TrashIntrigueCard(troops_if_not_twisted=1),),
                rewards=(DrawIntrigueCards(1),),
            )
        ),
    ),
    _twisted(
        "withdrawn",
        "Withdrawn",
        IntrigueOption(
            timing=IntrigueTiming.PLOT,
            sections=(EffectSection(rewards=(PassTurn(),)),),
            turn_start_only=True,
        ),
    ),
    # --- Navigation cards (Steersman Y'rkoon), card faces 2026-09-07 ------
    _navigation(
        1,
        _plot(EffectSection(rewards=(GainResources(spice=1),))),
        _plot(
            EffectSection(
                costs=(PayResources(solari=2),),
                rewards=(GainInfluence(different_from_trigger=True, minimum_own=2),),
            )
        ),
    ),
    _navigation(
        2,
        _plot(EffectSection(rewards=(PlaceSpy(),))),
        _plot(
            EffectSection(
                costs=(RecallSpy(1),),
                rewards=(DrawIntrigueCards(1), GainResources(spice=2)),
            )
        ),
    ),
    _navigation(
        3,
        _plot(
            EffectSection(rewards=(GainResources(solari=2),)),
            EffectSection(
                condition=InNavigationSlot(4),
                rewards=(PermanentRevealPersuasion(1),),
            ),
        ),
    ),
    _navigation(
        4,
        _plot(EffectSection(rewards=(GainResources(spice=1),))),
        _plot(
            EffectSection(
                condition=InNavigationSlot(1),
                costs=(PayResources(water=1),),
                rewards=(AcquireReserveCard("the_spice_must_flow"),),
            )
        ),
    ),
    _navigation(
        5,
        _plot(
            EffectSection(
                rewards=(TrashPersonalCard(bonus_spice=2, bonus_minimum_cost=1),)
            )
        ),
    ),
    _navigation(
        6,
        _plot(EffectSection(rewards=(RecruitTroops(1),))),
        _plot(
            EffectSection(costs=(PayResources(solari=3),), rewards=(RecruitTroops(3),))
        ),
    ),
    _navigation(
        7,
        _plot(
            EffectSection(rewards=(GainResources(spice=1),)),
            EffectSection(condition=HasAlliance(), rewards=(DrawIntrigueCards(1),)),
        ),
    ),
    _navigation(
        8,
        _plot(
            EffectSection(rewards=(GainResources(water=1),)),
            EffectSection(
                condition=TriggeredByFaction(Faction.SPACING_GUILD),
                rewards=(GainResources(spice=1),),
            ),
        ),
    ),
    _navigation(
        9,
        _plot(EffectSection(rewards=(DrawPersonalCards(1),))),
        _plot(
            EffectSection(
                costs=(PayResources(spice=5),), rewards=(GainVictoryPoints(1),)
            )
        ),
    ),
    _navigation(
        10,
        _plot(EffectSection(costs=(LoseInfluence(1),), rewards=(GainInfluence(),))),
    ),
)


def intrigue_card_for_instance(instance_id: str) -> IntrigueCardEntry:
    """Return the Intrigue definition behind one ``intrigue:<id>:<copy>`` ID."""

    try:
        return INTRIGUE_CARDS_BY_INSTANCE[instance_id]
    except KeyError as error:
        raise ValueError(f"unknown Intrigue card instance: {instance_id}") from error


def intrigue_cards_for_choam(
    choam_module: bool,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
) -> tuple[IntrigueCardEntry, ...]:
    """Return physical card entries included by the selected setup.

    Bloodlines cards join only with the option [Bloodlines p. 3] and only
    once their options are transcribed (an untranscribed card cannot be
    played, so it waits out of the deck).
    """

    return tuple(
        entry
        for entry in INTRIGUE_CARDS
        if (choam_module or not entry.choam_only)
        and not entry.twisted
        and not entry.navigation
        and (
            not entry.bloodlines_only
            or (
                bloodlines
                and entry.play_data_complete
                and (tech_module or not entry.tech_only)
            )
        )
    )


def navigation_card_instance_ids() -> tuple[str, ...]:
    """Return the ten Navigation cards (Steersman Y'rkoon), in printed order."""

    return tuple(
        f"intrigue:{entry.card.card_id}:0"
        for entry in INTRIGUE_CARDS
        if entry.navigation
    )


def twisted_intrigue_instance_ids() -> tuple[str, ...]:
    """Return the twelve Twisted Intrigue cards (Piter De Vries)."""

    return tuple(
        f"intrigue:{entry.card.card_id}:0" for entry in INTRIGUE_CARDS if entry.twisted
    )


def intrigue_deck_instance_ids(
    choam_module: bool,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
) -> tuple[str, ...]:
    """Return stable IDs for every physical Intrigue card copy."""

    return tuple(
        f"intrigue:{entry.card.card_id}:{copy}"
        for entry in intrigue_cards_for_choam(
            choam_module, bloodlines=bloodlines, tech_module=tech_module
        )
        for copy in range(entry.copies)
    )


INTRIGUE_CARDS_BY_ID: Final = {entry.card.card_id: entry for entry in INTRIGUE_CARDS}
# Every physical copy of every identity, whatever the setup includes.
INTRIGUE_CARDS_BY_INSTANCE: Final = {
    f"intrigue:{entry.card.card_id}:{copy}": entry
    for entry in INTRIGUE_CARDS
    for copy in range(entry.copies)
}
