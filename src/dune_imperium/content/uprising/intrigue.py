"""Identities and transcribed play data for the 44-card Uprising Intrigue deck."""

from typing import Any, Final

from dune_imperium.content.core.cards import (
    IntrigueCardEntry,
    combat_lines_option,
    combat_option,
    endgame_option,
    intrigue_card_entry,
    plot_lines_option,
    plot_option,
    plot_trigger_option,
)
from dune_imperium.content.core.effects import (
    AcquireCardUpTo,
    CompletedContractsAtLeast,
    DeployFromGarrison,
    DestroyShieldWall,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    FlipBattleCard,
    GainCombatStrength,
    GainedSpiceThisTurn,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    HasHighCouncil,
    InfluenceAtLeast,
    IntrigueOption,
    LoseInfluence,
    OnRevealAcquisitionThisRound,
    OpponentAllianceInfluenceAtLeast,
    PayResources,
    PlaceSpy,
    RecallSpy,
    RecruitTroops,
    RetreatTroops,
    SandwormsInConflictAtLeast,
    SetAsideImperiumRowCard,
    SpiceMustFlowCardsAtLeast,
    SpiesPlacedAtLeast,
    SummonSandworm,
    TakeContract,
    TrashPersonalCard,
    UnitsDeployedThisTurnAtLeast,
)
from dune_imperium.content.core.icons import AgentIcon, BattleIcon, Faction
from dune_imperium.content.core.schema import GameOption, SourceDocument, SourceRef

BASE_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)
CHOAM_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 16)),)


def _spice_or_endgame_flip(icon: BattleIcon) -> tuple[IntrigueOption, ...]:
    return (
        plot_option(EffectSection(rewards=(GainResources(spice=1),))),
        endgame_option(
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
    requires: frozenset[GameOption] = frozenset(),
    **fields: Any,
) -> IntrigueCardEntry:
    return intrigue_card_entry(
        catalog_id,
        slug,
        name,
        catalog_set="uprising",
        sources=(
            CHOAM_SOURCES if GameOption.CHOAM_MODULE in requires else BASE_SOURCES
        ),
        requires=requires,
        **fields,
    )


# Uprising's own Intrigue cards; Bloodlines' and Immortality's are in their
# packages, and ``content.registry.intrigue.INTRIGUE_CARDS`` joins the three.
UPRISING_INTRIGUE_CARDS: Final = (
    _entry(
        448,
        "backed-by-choam",
        "Backed by CHOAM",
        requires=frozenset({GameOption.CHOAM_MODULE}),
        options=(
            plot_option(
                EffectSection(
                    costs=(LoseInfluence(1),),
                    rewards=(GainResources(solari=4),),
                )
            ),
            combat_option(
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
            plot_option(
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
            plot_trigger_option(
                OnRevealAcquisitionThisRound(),
                EffectSection(rewards=(RecruitTroops(1),)),
            ),
        ),
    ),
    _entry(
        135,
        "change-allegiances",
        "Change Allegiances",
        # Two arrow lines, no "—OR—" [card face]: one or both, each paid when
        # used (designer ruling OQ-057; OQ-058).
        options=(
            plot_lines_option(
                EffectSection(costs=(LoseInfluence(1),), rewards=(GainInfluence(),)),
                EffectSection(
                    costs=(PayResources(spice=3),),
                    rewards=(GainInfluence(),),
                ),
            ),
        ),
    ),
    _entry(
        450,
        "choam-profits",
        "CHOAM Profits",
        requires=frozenset({GameOption.CHOAM_MODULE}),
        options=(
            endgame_option(
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
            plot_option(EffectSection(rewards=(GainResources(solari=2),))),
            combat_option(EffectSection(rewards=(GainCombatStrength(3),))),
        ),
    ),
    _entry(
        129,
        "councilor-s-ambition",
        "Councilor's Ambition",
        options=(
            plot_option(
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
            plot_option(EffectSection(rewards=(DrawPersonalCards(1),))),
            plot_option(
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
            plot_lines_option(
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
            plot_option(EffectSection(rewards=(DestroyShieldWall(),))),
            plot_option(EffectSection(rewards=(DeployFromGarrison(4),))),
        ),
    ),
    _entry(
        151,
        "devour",
        "Devour",
        options=(
            combat_option(
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
            # "When you deploy three or more units to the Conflict in a
            # single turn:" / "You may place this Spy on the same observation
            # post as another player's Spy." [Distraction card]: played once
            # the units are deployed [Board Guide p. 10], not left waiting
            # face up (user ruling 2026-10-03, OQ-016).
            plot_option(
                EffectSection(
                    condition=UnitsDeployedThisTurnAtLeast(3),
                    rewards=(PlaceSpy(shared_post=True),),
                )
            ),
        ),
    ),
    _entry(
        149,
        "find-weakness",
        "Find Weakness",
        options=(
            combat_lines_option(
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
            combat_option(
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
            plot_option(
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
            combat_option(
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
            plot_option(
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
            plot_option(
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
        requires=frozenset({GameOption.CHOAM_MODULE}),
        options=(
            plot_option(
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
        options=(plot_option(EffectSection(rewards=(SetAsideImperiumRowCard(1),))),),
    ),
    _entry(
        145,
        "market-opportunity",
        "Market Opportunity",
        options=(
            plot_option(
                EffectSection(
                    costs=(PayResources(spice=2),),
                    rewards=(GainResources(solari=5),),
                )
            ),
            plot_option(
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
            plot_option(
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
            plot_option(
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
            combat_lines_option(
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
        requires=frozenset({GameOption.CHOAM_MODULE}),
        options=(
            combat_option(
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
            endgame_option(
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
            plot_option(
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
            endgame_option(
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
            plot_option(
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
            # "[Spy] on [City]": the disc is the City Agent icon, so the post
            # must connect to a City space [Special Mission card; Main p. 20].
            plot_option(EffectSection(rewards=(PlaceSpy(agent_icons=(AgentIcon.CITY,)),))),
            plot_option(
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
            combat_option(
                EffectSection(
                    costs=(RetreatTroops(3, 3),),
                    rewards=(GainResources(spice=3),),
                )
            ),
            combat_option(
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
            combat_option(
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
            plot_lines_option(
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
            combat_option(EffectSection(rewards=(GainCombatStrength(2),))),
            # "Retreat any number of your troops." [card face]: zero may be
            # chosen [Main p. 20] [FAQ p. 3] (docs/rules/uprising-systems.md).
            combat_option(EffectSection(rewards=(RetreatTroops(0, None),))),
        ),
    ),
    _entry(
        137,
        "unexpected-allies",
        "Unexpected Allies",
        options=(
            plot_option(
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
            combat_option(
                EffectSection(rewards=(GainCombatStrength(3),)),
                EffectSection(
                    condition=InfluenceAtLeast(Faction.BENE_GESSERIT, 3),
                    rewards=(GainCombatStrength(2),),
                ),
            ),
        ),
    ),
)
