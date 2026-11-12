"""Bloodlines' Intrigue cards for the Uprising-format deck (``bloodlines``).

Moved from ``content.uprising.intrigue`` (docs/content-core-refactor-plan.md
8.3, user decision 2026-11-04): the set's own cards, Piter De Vries' Twisted
Intrigue cards and Steersman Y'rkoon's Navigation cards;
``content.registry.intrigue`` puts them after Uprising's own cards.
"""

from typing import Any, Final

from dune_imperium.content.core.cards import (
    IntrigueCardEntry,
    combat_option,
    endgame_option,
    intrigue_card_entry,
    plot_option,
)
from dune_imperium.content.core.effects import (
    AcquireReserveCard,
    AcquireTech,
    CommanderDiscountThisTurn,
    CommandersInConflictAtLeast,
    DeployFromGarrison,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    FlipFaceUpConflictCard,
    GainCombatStrength,
    GainInfluence,
    GainResources,
    GainSolariPerUnitType,
    GainVictoryPoints,
    GiveIntrigueToOpponent,
    GrantAgentIconsThisTurn,
    GrantAgentIconThisTurn,
    GrantCombatDeployment,
    HasAlliance,
    IgnoreInfluenceRequirementsThisTurn,
    InfluenceAtLeast,
    InNavigationSlot,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
    LoseTroops,
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
    TechTilesAtLeast,
    TrashDiscardPileCard,
    TrashIntrigueCard,
    TrashPersonalCard,
    TriggeredByFaction,
    UnitsDeployedThisTurnAtLeast,
    WaterAtLeast,
)
from dune_imperium.content.core.icons import AgentIcon, Faction
from dune_imperium.content.core.schema import (
    CardDefinition,
    GameOption,
    SourceDocument,
    SourceRef,
)

BLOODLINES_SOURCES: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (2, 3)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)


def _entry(
    catalog_id: int,
    slug: str,
    name: str,
    **fields: Any,
) -> IntrigueCardEntry:
    return intrigue_card_entry(
        catalog_id,
        slug,
        name,
        catalog_set="bloodlines",
        sources=BLOODLINES_SOURCES,
        **fields,
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
        requires=frozenset({GameOption.BLOODLINES}),
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=options,
        twisted=True,
    )


BLOODLINES_INTRIGUE_CARDS: Final = (
    # Bloodlines Intrigue cards (2026-09-07): 15 retail + 1 CHOAM-only + 2
    # Tech-only [Bloodlines pp. 2-3]; options are transcribed from the card
    # faces slice by slice (an entry without options stays out of the deck).
    _entry(
        109,
        "adaptive-tactics",
        "Adaptive Tactics",
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            plot_option(
                EffectSection(
                    costs=(PayResources(spice=1),),
                    rewards=(RecruitTroops(1), GrantCombatDeployment()),
                )
            ),
        ),
    ),
    # Battlefield Research (Tech Module, card face): "Retreat one or two of
    # your troops -> Acquire Tech (1 spice off) — OR — If you have three or
    # more Tech tiles: 1 VP", Combat / Endgame. Each band has one timing, in
    # its colour and the footer's: the red retreat band is Combat, the
    # dark-green VP band Endgame [card face; Main p. 7].
    _entry(
        110,
        "battlefield-research",
        "Battlefield Research",
        requires=frozenset({GameOption.BLOODLINES, GameOption.TECH_MODULE}),
        options=(
            combat_option(
                EffectSection(
                    costs=(RetreatTroops(1, 2),),
                    rewards=(AcquireTech(1),),
                )
            ),
            endgame_option(
                EffectSection(
                    condition=TechTilesAtLeast(3),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
        ),
    ),
    _entry(
        111,
        "coercive-negotiation",
        "Coercive Negotiation",
        requires=frozenset({GameOption.CHOAM_MODULE, GameOption.BLOODLINES}),
        options=(
            # "When you deploy three or more units to the Conflict in a
            # single turn: Reveal three contracts from the bank. Take one and
            # trash the other two." [Coercive Negotiation card] -- a play
            # condition like Distraction's (OQ-016).
            plot_option(
                EffectSection(
                    condition=UnitsDeployedThisTurnAtLeast(3),
                    rewards=(RevealContractsTakeOne(3),),
                )
            ),
        ),
    ),
    _entry(
        112,
        "desert-support",
        "Desert Support",
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            combat_option(
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            plot_option(EffectSection(rewards=(DrawPersonalCards(1),))),
            plot_option(EffectSection(rewards=(GrantAgentIconThisTurn(AgentIcon.EMPEROR),))),
        ),
    ),
    _entry(
        114,
        "false-orders",
        "False Orders",
        requires=frozenset({GameOption.BLOODLINES}),
        options=(plot_option(EffectSection(rewards=(RedirectSpiesOnTurnSpace(),))),),
    ),
    # Grasp Arrakis (Combat / Endgame): the red band's three swords are the
    # Combat half, the dark-green band's "Flip two of your face-up Conflict
    # cards -> 1 VP" the Endgame half [card face; Main p. 7].
    _entry(
        115,
        "grasp-arrakis",
        "Grasp Arrakis",
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            combat_option(EffectSection(rewards=(GainCombatStrength(3),))),
            endgame_option(
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            plot_option(
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            plot_option(
                EffectSection(
                    costs=(RecallSpy(1),),
                    rewards=(TrashPersonalCard(), DrawPersonalCards(1)),
                )
            ),
            plot_option(EffectSection(rewards=(IgnoreInfluenceRequirementsThisTurn(),))),
        ),
    ),
    # Rapid Engineering (Tech Module, card face): "Discard a card -> Acquire
    # Tech (1 spice off) — OR — If you have three or more Tech tiles: choose
    # two: Emperor / Guild / Bene Gesserit / Fremen Influence", Plot.
    _entry(
        118,
        "rapid-engineering",
        "Rapid Engineering",
        requires=frozenset({GameOption.BLOODLINES, GameOption.TECH_MODULE}),
        options=(
            plot_option(
                EffectSection(
                    costs=(DiscardFromHand(1),),
                    rewards=(AcquireTech(1),),
                )
            ),
            plot_option(
                EffectSection(
                    condition=TechTilesAtLeast(3),
                    rewards=(GainInfluence(times=2, distinct=True),),
                )
            ),
        ),
    ),
    _entry(
        119,
        "return-the-favor",
        "Return the Favor",
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            # "1 sword. For each Faction where you have 2 Influence (or
            # more): +1 sword": one conditional line per Faction.
            combat_option(
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            combat_option(
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            plot_option(
                EffectSection(
                    costs=(DiscardFromHand(1),),
                    rewards=(GainResources(water=1),),
                )
            ),
            endgame_option(
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            plot_option(EffectSection(rewards=(GainResources(solari=2),))),
            plot_option(
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            plot_option(
                EffectSection(
                    costs=(PayResources(solari=1),),
                    rewards=(PlaceSpy(),),
                )
            ),
            plot_option(
                EffectSection(
                    costs=(RecallSpy(1),),
                    rewards=(RecruitTroops(2),),
                )
            ),
        ),
    ),
    # Tenuous Bond (Plot / Combat): the gold band's Influence swap is the
    # Plot half, the red band's "Trash a card from your discard pile that
    # costs 1 or more -> 4 swords" the Combat half [card face; Main p. 7].
    _entry(
        124,
        "tenuous-bond",
        "Tenuous Bond",
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            plot_option(
                EffectSection(
                    costs=(LoseInfluence(1),),
                    rewards=(GainInfluence(),),
                )
            ),
            combat_option(
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            combat_option(EffectSection(rewards=(GainCombatStrength(3),))),
            combat_option(
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
        requires=frozenset({GameOption.BLOODLINES}),
        options=(
            combat_option(
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
        plot_option(
            EffectSection(
                costs=(LoseTroops(3),),
                rewards=(GainInfluence(where_opponent_leads=True),),
            )
        ),
    ),
    _twisted(
        "calculating",
        "Calculating",
        plot_option(EffectSection(rewards=(GainSolariPerUnitType(),))),
    ),
    _twisted(
        "controlled",
        "Controlled",
        plot_option(EffectSection(rewards=(PeekTopCard(),))),
        combat_option(EffectSection(rewards=(GainCombatStrength(1),))),
    ),
    _twisted(
        "devious",
        "Devious",
        plot_option(
            EffectSection(rewards=(TrashPersonalCard(hand_only=True, mandatory=True),))
        ),
        plot_option(EffectSection(rewards=(DeployFromGarrison(2),))),
    ),
    _twisted(
        "discerning",
        "Discerning",
        plot_option(
            EffectSection(costs=(DiscardFromHand(1),), rewards=(DrawPersonalCards(1),))
        ),
        plot_option(
            EffectSection(condition=HasAlliance(), rewards=(DrawPersonalCards(1),))
        ),
    ),
    _twisted(
        "insidious",
        "Insidious",
        plot_option(
            EffectSection(
                costs=(GiveIntrigueToOpponent(bonus_spice_if_not_twisted=1),),
                rewards=(GainResources(spice=1),),
            )
        ),
    ),
    _twisted(
        "resourceful",
        "Resourceful",
        plot_option(
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
        plot_option(
            EffectSection(costs=(LoseTroops(1),), rewards=(DrawPersonalCards(1),))
        ),
    ),
    _twisted(
        "shrewd",
        "Shrewd",
        combat_option(
            EffectSection(
                costs=(LoseTroops(1, from_conflict=True),),
                rewards=(GainResources(spice=1),),
            )
        ),
    ),
    _twisted(
        "sinister",
        "Sinister",
        combat_option(
            EffectSection(
                costs=(LoseTroops(2),),
                rewards=(DrawIntrigueCards(1), GainResources(solari=1)),
            )
        ),
    ),
    _twisted(
        "unnatural",
        "Unnatural",
        plot_option(
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
        plot_option(EffectSection(rewards=(GainResources(spice=1),))),
        plot_option(
            EffectSection(
                costs=(PayResources(solari=2),),
                rewards=(GainInfluence(different_from_trigger=True, minimum_own=2),),
            )
        ),
    ),
    _navigation(
        2,
        plot_option(EffectSection(rewards=(PlaceSpy(),))),
        plot_option(
            EffectSection(
                costs=(RecallSpy(1),),
                rewards=(DrawIntrigueCards(1), GainResources(spice=2)),
            )
        ),
    ),
    _navigation(
        3,
        plot_option(
            EffectSection(rewards=(GainResources(solari=2),)),
            EffectSection(
                condition=InNavigationSlot(4),
                rewards=(PermanentRevealPersuasion(1),),
            ),
        ),
    ),
    _navigation(
        4,
        plot_option(EffectSection(rewards=(GainResources(spice=1),))),
        plot_option(
            EffectSection(
                condition=InNavigationSlot(1),
                costs=(PayResources(water=1),),
                rewards=(AcquireReserveCard("the_spice_must_flow"),),
            )
        ),
    ),
    _navigation(
        5,
        plot_option(
            EffectSection(
                rewards=(TrashPersonalCard(bonus_spice=2, bonus_minimum_cost=1),)
            )
        ),
    ),
    _navigation(
        6,
        plot_option(EffectSection(rewards=(RecruitTroops(1),))),
        plot_option(
            EffectSection(costs=(PayResources(solari=3),), rewards=(RecruitTroops(3),))
        ),
    ),
    _navigation(
        7,
        plot_option(
            EffectSection(rewards=(GainResources(spice=1),)),
            EffectSection(condition=HasAlliance(), rewards=(DrawIntrigueCards(1),)),
        ),
    ),
    _navigation(
        8,
        plot_option(
            EffectSection(rewards=(GainResources(water=1),)),
            EffectSection(
                condition=TriggeredByFaction(Faction.SPACING_GUILD),
                rewards=(GainResources(spice=1),),
            ),
        ),
    ),
    _navigation(
        9,
        plot_option(EffectSection(rewards=(DrawPersonalCards(1),))),
        plot_option(
            EffectSection(
                costs=(PayResources(spice=5),), rewards=(GainVictoryPoints(1),)
            )
        ),
    ),
    _navigation(
        10,
        plot_option(
            EffectSection(costs=(LoseInfluence(1),), rewards=(GainInfluence(),))
        ),
    ),
)

# "Steersman Y'rkoon을 쓰면 Spy를 놓거나 회수하는 Navigation 카드를 뺀다" with
# the original game [Bloodlines p. 3] (docs/rules/bloodlines.md 2a): card 2,
# whose two Plots place a Spy and recall one; the original board has no
# observation post.
ORIGINAL_GAME_LEFT_OUT_NAVIGATION_IDS: Final = frozenset({"navigation_card_2"})
