"""Immortality's Intrigue cards for the Uprising-format deck (``immortality``).

Moved from ``content.uprising.intrigue`` (docs/content-core-refactor-plan.md
8.3, user decision 2026-11-04); ``content.registry.intrigue`` puts them after
Bloodlines' cards.
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
    AcquireTleilaxuCard,
    AdvanceTleilaxu,
    AllConditions,
    DeployFromGarrison,
    EffectSection,
    GainCombatStrength,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    GenerateSpecimens,
    GeneticMarkersAtLeast,
    HasHighCouncil,
    IntrigueOption,
    IntrigueTiming,
    LoseTroops,
    OnTroopsLostAtConflictEnd,
    OpponentPlayedCombatIntrigue,
    Research,
    RetreatTroops,
    RevealPersuasionThisRound,
    SolariAtLeast,
    SpiceAtLeast,
)
from dune_imperium.content.core.schema import GameOption, SourceDocument, SourceRef

IMMORTALITY_SOURCES: Final = (
    SourceRef(SourceDocument.IMMORTALITY_RULEBOOK, (3, 5)),
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
        catalog_set="immortality",
        sources=IMMORTALITY_SOURCES,
        **fields,
    )


IMMORTALITY_INTRIGUE_CARDS: Final = (
    # Immortality Intrigue cards (2026-09-08): 15 cards [Immortality p. 3];
    # the Dune Cards Hub catalog lists 11 identities, one copy each (see
    # docs/implementation-audits/immortality.md). Options are transcribed
    # from the card faces slice by slice (an entry without options stays
    # out of the deck).
    # Breakthrough (Plot): Research.
    _entry(
        392,
        "breakthrough",
        "Breakthrough",
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(plot_option(EffectSection(rewards=(Research(),))),),
    ),
    # Counterattack (Plot / Combat): deploy up to two garrison troops —OR—
    # if an opponent played a Combat Intrigue card in this Conflict: 4 swords.
    _entry(
        393,
        "counterattack",
        "Counterattack",
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(
            plot_option(EffectSection(rewards=(DeployFromGarrison(2),))),
            combat_option(
                EffectSection(
                    condition=OpponentPlayedCombatIntrigue(),
                    rewards=(GainCombatStrength(4),),
                )
            ),
        ),
    ),
    # Disguised Bureaucrat (Plot): one genetic marker: 1 spice; two: an
    # Influence of your choice.
    _entry(
        394,
        "disguised-bureaucrat",
        "Disguised Bureaucrat",
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(
            plot_option(
                EffectSection(
                    condition=GeneticMarkersAtLeast(1),
                    rewards=(GainResources(spice=1),),
                ),
                EffectSection(
                    condition=GeneticMarkersAtLeast(2),
                    rewards=(GainInfluence(),),
                ),
            ),
        ),
    ),
    # Economic Positioning (Combat / Endgame): retreat two troops -> 3
    # Solari —OR— if you have 10 or more Solari: 1 VP.
    _entry(
        395,
        "economic-positioning",
        "Economic Positioning",
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(
            combat_option(
                EffectSection(
                    costs=(RetreatTroops(2, 2),),
                    rewards=(GainResources(solari=3),),
                )
            ),
            endgame_option(
                EffectSection(
                    condition=SolariAtLeast(10),
                    rewards=(GainVictoryPoints(1),),
                )
            ),
        ),
    ),
    # Gruesome Sacrifice (Combat): lose two of your troops in the Conflict
    # -> Tleilaxu and 2 specimens.
    _entry(
        396,
        "gruesome-sacrifice",
        "Gruesome Sacrifice",
        copies=2,
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(
            combat_option(
                EffectSection(
                    costs=(LoseTroops(2, from_conflict=True),),
                    rewards=(AdvanceTleilaxu(1), GenerateSpecimens(2)),
                )
            ),
        ),
    ),
    # Harvest Cells (Combat): when you lose at least three troops at the
    # end of a Conflict: 2 specimens; you may also acquire a Tleilaxu card.
    _entry(
        397,
        "harvest-cells",
        "Harvest Cells",
        copies=2,
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(
            IntrigueOption(
                timing=IntrigueTiming.COMBAT,
                sections=(
                    EffectSection(
                        rewards=(GenerateSpecimens(2), AcquireTleilaxuCard())
                    ),
                ),
                trigger=OnTroopsLostAtConflictEnd(3),
            ),
        ),
    ),
    # Illicit Dealings (Plot): Tleilaxu.
    _entry(
        398,
        "illicit-dealings",
        "Illicit Dealings",
        copies=2,
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(plot_option(EffectSection(rewards=(AdvanceTleilaxu(1),))),),
    ),
    # Shadowy Bargain (Plot / Endgame): a specimen —OR— Tleilaxu.
    _entry(
        399,
        "shadowy-bargain",
        "Shadowy Bargain",
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(
            plot_option(EffectSection(rewards=(GenerateSpecimens(1),))),
            endgame_option(EffectSection(rewards=(AdvanceTleilaxu(1),))),
        ),
    ),
    # Study Melange (Plot / Endgame): 1 spice —OR— if you have 3 or more
    # spice, at two genetic markers: 1 VP.
    _entry(
        400,
        "study-melange",
        "Study Melange",
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(
            plot_option(EffectSection(rewards=(GainResources(spice=1),))),
            endgame_option(
                EffectSection(
                    condition=AllConditions(
                        (SpiceAtLeast(3), GeneticMarkersAtLeast(2))
                    ),
                    rewards=(GainVictoryPoints(1),),
                ),
            ),
        ),
    ),
    # Tleilaxu Puppet (Plot / Endgame): 1 Persuasion during your Reveal
    # turn this round —OR— with a High Council seat, at two genetic
    # markers: 1 VP.
    _entry(
        401,
        "tleilaxu-puppet",
        "Tleilaxu Puppet",
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(
            plot_option(EffectSection(rewards=(RevealPersuasionThisRound(1),))),
            endgame_option(
                EffectSection(
                    condition=AllConditions(
                        (HasHighCouncil(), GeneticMarkersAtLeast(2))
                    ),
                    rewards=(GainVictoryPoints(1),),
                ),
            ),
        ),
    ),
    # Vicious Talents (Combat): 2 swords; one genetic marker: +2; two: +2.
    _entry(
        402,
        "vicious-talents",
        "Vicious Talents",
        copies=2,
        requires=frozenset({GameOption.IMMORTALITY}),
        options=(
            combat_option(
                EffectSection(rewards=(GainCombatStrength(2),)),
                EffectSection(
                    condition=GeneticMarkersAtLeast(1),
                    rewards=(GainCombatStrength(2),),
                ),
                EffectSection(
                    condition=GeneticMarkersAtLeast(2),
                    rewards=(GainCombatStrength(2),),
                ),
            ),
        ),
    ),
)
