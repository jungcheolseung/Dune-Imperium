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
    CompletedContractsAtLeast,
    DiscardFromHand,
    DrawIntrigueCards,
    DrawPersonalCards,
    EffectSection,
    GainCombatStrength,
    GainInfluence,
    GainResources,
    GainVictoryPoints,
    HasHighCouncil,
    InfluenceAtLeast,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
    PayResources,
    RecruitTroops,
    SpiesPlacedAtLeast,
)

BASE_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)
CHOAM_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 16)),)


@dataclass(frozen=True, slots=True)
class IntrigueCardEntry(DeckCardEntry):
    """One Intrigue identity plus its transcribed play options.

    ``options`` lists the alternative ways to play the card. A card printed as
    ``A —OR— B`` has two options; a card with several stacked lines has one
    option with several sections. ``play_data_complete`` marks that every
    printed option is transcribed and executable by the rules engine.
    """

    options: tuple[IntrigueOption, ...] = ()
    play_data_complete: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.play_data_complete != bool(self.options):
            raise ValueError("Intrigue play data is complete exactly when transcribed")

    @property
    def timings(self) -> frozenset[IntrigueTiming]:
        """Return every timing at which some option can be played."""

        return frozenset(option.timing for option in self.options)


def _plot(*sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(timing=IntrigueTiming.PLOT, sections=sections)


def _combat(*sections: EffectSection) -> IntrigueOption:
    return IntrigueOption(timing=IntrigueTiming.COMBAT, sections=sections)


def _entry(
    catalog_id: int,
    slug: str,
    name: str,
    *,
    copies: int = 1,
    choam_only: bool = False,
    options: tuple[IntrigueOption, ...] = (),
) -> IntrigueCardEntry:
    return IntrigueCardEntry(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=CHOAM_SOURCES if choam_only else BASE_SOURCES,
            catalog_url=f"https://dunecardshub.com/cards/{catalog_id}/uprising-{slug}",
        ),
        copies=copies,
        choam_only=choam_only,
        options=options,
        play_data_complete=bool(options),
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
    _entry(138, "call-to-arms", "Call to Arms"),
    _entry(
        135,
        "change-allegiances",
        "Change Allegiances",
        options=(
            _plot(
                EffectSection(costs=(LoseInfluence(1),), rewards=(GainInfluence(),))
            ),
            _plot(
                EffectSection(
                    costs=(PayResources(spice=3),),
                    rewards=(GainInfluence(),),
                )
            ),
        ),
    ),
    _entry(450, "choam-profits", "CHOAM Profits", choam_only=True),
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
    _entry(159, "crysknife", "Crysknife"),
    _entry(133, "cunning", "Cunning"),
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
    _entry(157, "desert-mouse", "Desert Mouse"),
    _entry(131, "detonation", "Detonation", copies=2),
    _entry(151, "devour", "Devour"),
    _entry(144, "distraction", "Distraction", copies=2),
    _entry(149, "find-weakness", "Find Weakness"),
    _entry(146, "go-to-ground", "Go To Ground"),
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
    _entry(152, "impress", "Impress"),
    _entry(148, "inspire-awe", "Inspire Awe"),
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
    _entry(447, "leverage", "Leverage", choam_only=True),
    _entry(143, "manipulate", "Manipulate"),
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
    _entry(158, "ornithopter", "Ornithopter"),
    _entry(156, "questionable-methods", "Questionable Methods"),
    _entry(449, "reach-agreement", "Reach Agreement", choam_only=True),
    _entry(161, "secure-spice-trade", "Secure Spice Trade"),
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
    _entry(160, "shadow-alliance", "Shadow Alliance"),
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
    _entry(136, "special-mission", "Special Mission", copies=2),
    _entry(150, "spice-is-power", "Spice is Power"),
    _entry(153, "spring-the-trap", "Spring The Trap"),
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
    _entry(155, "tactical-option", "Tactical Option"),
    _entry(137, "unexpected-allies", "Unexpected Allies"),
    _entry(154, "weirding-combat", "Weirding Combat"),
)


INTRIGUE_CARDS_BY_ID: Final = {entry.card.card_id: entry for entry in INTRIGUE_CARDS}


def intrigue_card_for_instance(instance_id: str) -> IntrigueCardEntry:
    """Return the Intrigue definition behind one ``intrigue:<id>:<copy>`` ID."""

    parts = instance_id.split(":")
    if len(parts) != 3 or parts[0] != "intrigue":
        raise ValueError(f"not an Intrigue card instance: {instance_id}")
    try:
        return INTRIGUE_CARDS_BY_ID[parts[1]]
    except KeyError as error:
        raise ValueError(f"unknown Intrigue card: {instance_id}") from error


def intrigue_cards_for_choam(choam_module: bool) -> tuple[IntrigueCardEntry, ...]:
    """Return physical card entries included by the selected setup."""

    return tuple(
        entry for entry in INTRIGUE_CARDS if choam_module or not entry.choam_only
    )


def intrigue_deck_instance_ids(choam_module: bool) -> tuple[str, ...]:
    """Return stable IDs for every physical Intrigue card copy."""

    return tuple(
        f"intrigue:{entry.card.card_id}:{copy}"
        for entry in intrigue_cards_for_choam(choam_module)
        for copy in range(entry.copies)
    )
