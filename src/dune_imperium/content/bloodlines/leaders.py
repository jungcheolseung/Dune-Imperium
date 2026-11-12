"""Bloodlines' Leaders (``bloodlines``).

Moved from ``content.uprising.leaders`` (docs/content-core-refactor-plan.md
8.3, user decision 2026-11-04); ``content.registry.leaders`` puts them after
Uprising's own Leaders.
"""

from typing import Final

from dune_imperium.content.core.cards import LeaderDefinition
from dune_imperium.content.core.schema import GameOption, SourceDocument, SourceRef


def _bloodlines_face(slug: str) -> str:
    """Dune Cards Hub's face image of a Bloodlines Leader (reference only)."""

    return f"https://dunecardshub.com/images/bloodlines-leader-{slug}.webp"


BLOODLINES_LEADER_SOURCES: Final = (
    SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (3, 12)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)


BLOODLINES_LEADERS: Final = (
    # Bloodlines Leaders, transcribed from the card faces (2026-09-07); the
    # rulebook adds only their clarifications [Bloodlines pp. 3, 12].
    LeaderDefinition(
        "chani",
        "Chani",
        _bloodlines_face("chani"),
        requires=frozenset({GameOption.BLOODLINES}),
        uses_tactics_track=True,
        ability_name="Tactician",
        signet_name="Fedaykin Maneuver",
        sources=BLOODLINES_LEADER_SOURCES,
    ),
    LeaderDefinition(
        "count_hasimir_fenring",
        "Count Hasimir Fenring",
        _bloodlines_face("count-hasimir-fenring"),
        requires=frozenset({GameOption.BLOODLINES}),
        ability_name="Assassin",
        signet_name="Corrino Liaison",
        sources=BLOODLINES_LEADER_SOURCES,
    ),
    LeaderDefinition(
        "duncan_idaho",
        "Duncan Idaho",
        _bloodlines_face("duncan-idaho"),
        requires=frozenset({GameOption.BLOODLINES}),
        ability_name="Ginaz Swordmaster",
        signet_name="Into the Fray",
        sources=BLOODLINES_LEADER_SOURCES,
    ),
    LeaderDefinition(
        "esmar_tuek",
        "Esmar Tuek",
        _bloodlines_face("esmar-tuek"),
        requires=frozenset({GameOption.BLOODLINES}),
        ability_name="Tuek's Sietch",
        signet_name="Smuggle Spice",
        sources=BLOODLINES_LEADER_SOURCES,
    ),
    LeaderDefinition(
        "gaius_helen_mohiam",
        "Gaius Helen Mohiam",
        _bloodlines_face("gaius-helen-mohiam"),
        requires=frozenset({GameOption.BLOODLINES}),
        ability_name="Clandestine",
        signet_name="Listeners",
        sources=BLOODLINES_LEADER_SOURCES,
    ),
    LeaderDefinition(
        "piter_de_vries",
        "Piter De Vries",
        _bloodlines_face("piter-de-vries"),
        requires=frozenset({GameOption.BLOODLINES}),
        uses_twisted_intrigue=True,
        ability_name="Twisted Genius",
        signet_name="Harkonnen Advisor",
        sources=BLOODLINES_LEADER_SOURCES,
    ),
    LeaderDefinition(
        "steersman_y_rkoon",
        "Steersman Y'rkoon",
        _bloodlines_face("steersman-y-rkoon"),
        requires=frozenset({GameOption.BLOODLINES}),
        ability_name="Strange Form / Hungry for Spice",
        signet_name="Plot Course",
        # Strange Form: "You start the game with no water and without
        # Signet Ring in your deck."
        removed_starting_card_ids=("signet_ring",),
        starting_water=0,
        sources=BLOODLINES_LEADER_SOURCES,
    ),
    LeaderDefinition(
        "liet_kynes",
        "Liet Kynes",
        _bloodlines_face("liet-kynes"),
        requires=frozenset({GameOption.BLOODLINES}),
        ability_name="Arrakis Planetologist",
        signet_name="Judge of the Change",
        sources=BLOODLINES_LEADER_SOURCES,
    ),
    # Tech Module: "A player has the option to choose Kota Odax of Ix as
    # their Leader" [Bloodlines p. 6]; card face transcribed 2026-09-07.
    LeaderDefinition(
        "kota_odax_of_ix",
        "Kota Odax of Ix",
        _bloodlines_face("kota-odax-of-ix"),
        requires=frozenset({GameOption.BLOODLINES, GameOption.TECH_MODULE}),
        ability_name="Secret Project",
        signet_name="Reverse Engineering",
        sources=(
            SourceRef(SourceDocument.BLOODLINES_RULEBOOK, (6,)),
            SourceRef(SourceDocument.CARD_FACE, (1,)),
        ),
    ),
)
