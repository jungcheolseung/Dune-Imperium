"""The original game's eight Leaders (docs/rules/imperium-base.md 12).

Names, ability names and setup values are the Steam app's (loc keys
``…staticability.title`` and ``…signetability.title``, P0 sweep). Every
Leader is defined here so the observation's Leader universe changes once
(docs/base-game-and-ix-plan.md 15.1); the original game's Leader list
(``rulesets.IMPERIUM_LEADER_IDS``) holds those whose abilities the engine
plays (stage P2a: four; P2b adds the rest).
"""

from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.leaders import LeaderDefinition

_SOURCES: Final = (
    SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (3, 4, 13)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)
# The card data come from the app (plan 2.4, D1); Dune Cards Hub's catalog
# is the reference picture.
_CATALOG: Final = "https://dunecardshub.com/"


def _leader(
    leader_id: str,
    name: str,
    ability: str,
    signet: str,
    *,
    extra_starting_spice: int = 0,
    extra_starting_solari: int = 0,
) -> LeaderDefinition:
    return LeaderDefinition(
        leader_id,
        name,
        _CATALOG,
        ability_name=ability,
        signet_name=signet,
        extra_starting_spice=extra_starting_spice,
        extra_starting_solari=extra_starting_solari,
        sources=_SOURCES,
    )


# Typed: ``content.uprising.leaders`` reads it while both modules load.
IMPERIUM_LEADERS: Final[tuple[LeaderDefinition, ...]] = (
    _leader("paul_atreides", "Paul Atreides", "Prescience", "Discipline"),
    _leader(
        "duke_leto_atreides",
        "Duke Leto Atreides",
        "Landsraad Popularity",
        "Prudent Diplomacy",
    ),
    _leader(
        "glossu_rabban",
        # The app's title; the card face prints GLOSSU "THE BEAST" RABBAN.
        'Glossu "Beast" Rabban',
        "Arrakis Fiefdom",
        "Brutality",
        extra_starting_spice=1,
        extra_starting_solari=1,
    ),
    _leader(
        "baron_vladimir_harkonnen",
        "Baron Vladimir Harkonnen",
        "Masterstroke",
        "Scheme",
    ),
    _leader(
        "count_ilban_richese",
        "Count Ilban Richese",
        "Ruthless Negotiator",
        "Manufacturing",
    ),
    _leader("helena_richese", "Helena Richese", "Eyes Everywhere", "Manipulate"),
    _leader(
        "earl_memnon_thorvald", "Earl Memnon Thorvald", "Connections", "Spice Hoard"
    ),
    _leader(
        "countess_ariana_thorvald",
        "Countess Ariana Thorvald",
        "Spice Addict",
        "Hidden Reservoir",
    ),
)
