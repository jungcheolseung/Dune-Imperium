"""The ten-card Uprising starting deck listed in Main Rulebook p. 3."""

from dataclasses import replace
from typing import Final

from dune_imperium.content.core.cards import StartingCardEntry
from dune_imperium.content.core.icons import AgentIcon
from dune_imperium.content.core.kept import kept_by_id
from dune_imperium.content.core.schema import CardDefinition, SourceDocument, SourceRef

MAIN_P3: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3,)),)

STARTING_DECK: Final = (
    StartingCardEntry(
        CardDefinition(
            "convincing_argument",
            "Convincing Argument",
            MAIN_P3,
        ),
        copies=2,
        reveal_persuasion=2,
    ),
    StartingCardEntry(
        CardDefinition("dagger", "Dagger", MAIN_P3),
        copies=2,
        agent_icons=(AgentIcon.LANDSRAAD,),
        reveal_strength=1,
    ),
    StartingCardEntry(
        CardDefinition("diplomacy", "Diplomacy", MAIN_P3),
        copies=1,
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
        ),
        reveal_persuasion=1,
    ),
    StartingCardEntry(
        CardDefinition(
            "dune_the_desert_planet",
            "Dune, the Desert Planet",
            MAIN_P3,
        ),
        copies=2,
        agent_icons=(AgentIcon.SPICE_TRADE,),
        reveal_persuasion=1,
    ),
    StartingCardEntry(
        CardDefinition("reconnaissance", "Reconnaissance", MAIN_P3),
        copies=1,
        agent_icons=(AgentIcon.CITY,),
        reveal_persuasion=1,
    ),
    StartingCardEntry(
        CardDefinition("seek_allies", "Seek Allies", MAIN_P3),
        copies=1,
        agent_icons=(
            AgentIcon.EMPEROR,
            AgentIcon.SPACING_GUILD,
            AgentIcon.BENE_GESSERIT,
            AgentIcon.FREMEN,
        ),
    ),
    StartingCardEntry(
        CardDefinition("signet_ring", "Signet Ring", MAIN_P3),
        copies=1,
        agent_icons=(
            AgentIcon.LANDSRAAD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        reveal_persuasion=1,
    ),
)

# Immortality: "Each player removes the two copies of Dune, the Desert
# Planet from their starting deck ... and replaces them with two copies of
# Experimentation" [Immortality p. 5]. Printed face: Spice Trade icon;
# Agent: Research; Reveal: 1 Persuasion and a specimen [card face].
EXPERIMENTATION: Final = StartingCardEntry(
    CardDefinition(
        "experimentation",
        "Experimentation",
        (
            SourceRef(SourceDocument.IMMORTALITY_RULEBOOK, (3, 5)),
            SourceRef(SourceDocument.CARD_FACE, (1,)),
        ),
    ),
    copies=2,
    agent_icons=(AgentIcon.SPICE_TRADE,),
    reveal_persuasion=1,
)
REPLACED_BY_EXPERIMENTATION: Final = "dune_the_desert_planet"

# Epic Game Mode: "Each player removes one copy of Dune, the Desert Planet
# from their starting deck and replaces it with one copy of Control the
# Spice" [Rise of Ix p. 10]; with Immortality no card is replaced and it
# starts in the discard pile instead [Immortality p. 12]. Printed face:
# Spice Trade icon; Agent: 1 spice -> trash a card, troop; Reveal: 1
# Persuasion, 1 spice [card face].
CONTROL_THE_SPICE: Final = StartingCardEntry(
    CardDefinition(
        "control_the_spice",
        "Control the Spice",
        (
            SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2, 10)),
            SourceRef(SourceDocument.CARD_FACE, (1,)),
        ),
        catalog_url=(
            "https://dunecardshub.com/images/rise-of-ix-imperium-control-the-spice.webp"
        ),
    ),
    copies=1,
    agent_icons=(AgentIcon.SPICE_TRADE,),
    reveal_persuasion=1,
)
REPLACED_BY_CONTROL_THE_SPICE: Final = "dune_the_desert_planet"

# The observation's personal-card universe lists Control the Spice after
# every older identity, not here among the starting cards (observation v28).
STARTING_CARDS_BY_ID: Final = {
    entry.card.card_id: entry
    for entry in (*STARTING_DECK, EXPERIMENTATION, CONTROL_THE_SPICE)
}


def starting_deck_entries(
    *, immortality: bool = False, epic_game: bool = False
) -> tuple[StartingCardEntry, ...]:
    """Return the ten-card starting deck of the selected setup.

    Immortality turns both Dune, the Desert Planet into Experimentation
    [Immortality p. 5]. Epic Game Mode without Immortality turns one of them
    into Control the Spice [Rise of Ix p. 10]; with Immortality the deck is
    unchanged and Control the Spice starts in the discard pile
    (``starting_discard_entries``) [Immortality p. 12].
    """

    if immortality:
        return tuple(
            EXPERIMENTATION
            if entry.card.card_id == REPLACED_BY_EXPERIMENTATION
            else entry
            for entry in STARTING_DECK
        )
    if not epic_game:
        return STARTING_DECK
    entries: list[StartingCardEntry] = []
    for entry in STARTING_DECK:
        if entry.card.card_id != REPLACED_BY_CONTROL_THE_SPICE:
            entries.append(entry)
            continue
        entries.append(replace(entry, copies=entry.copies - 1))
        entries.append(CONTROL_THE_SPICE)
    return tuple(entries)


def starting_discard_entries(
    *, immortality: bool = False, epic_game: bool = False
) -> tuple[StartingCardEntry, ...]:
    """Return the starting cards that begin the game in the discard pile.

    Only Control the Spice, in Epic Game Mode with Immortality
    [Immortality p. 12].
    """

    return (CONTROL_THE_SPICE,) if immortality and epic_game else ()


@kept_by_id
def starting_card_for_instance(instance_id: str) -> StartingCardEntry:
    """Resolve a stable per-player instance ID to its card definition."""

    marker = ":starter:"
    if marker not in instance_id:
        raise ValueError("not a starting-card instance ID")
    card_and_copy = instance_id.split(marker, maxsplit=1)[1]
    try:
        card_id, copy_text = card_and_copy.rsplit(":", maxsplit=1)
        copy = int(copy_text)
        entry = STARTING_CARDS_BY_ID[card_id]
    except (KeyError, ValueError) as error:
        raise ValueError("unknown starting-card instance ID") from error
    if copy < 0 or copy >= entry.copies:
        raise ValueError("starting-card copy index is out of range")
    return entry


def starting_instance_ids(
    player: int, entries: tuple[StartingCardEntry, ...]
) -> tuple[str, ...]:
    """Create stable IDs for one player's copies of ``entries``."""

    if player < 0:
        raise ValueError("player must not be negative")
    return tuple(
        f"player:{player}:starter:{entry.card.card_id}:{copy}"
        for entry in entries
        for copy in range(entry.copies)
    )


def starting_deck_instance_ids(
    player: int, *, immortality: bool = False, epic_game: bool = False
) -> tuple[str, ...]:
    """Create stable IDs for one player's unshuffled starting cards."""

    return starting_instance_ids(
        player, starting_deck_entries(immortality=immortality, epic_game=epic_game)
    )


def starting_discard_instance_ids(
    player: int, *, immortality: bool = False, epic_game: bool = False
) -> tuple[str, ...]:
    """Create stable IDs for one player's starting discard pile."""

    return starting_instance_ids(
        player, starting_discard_entries(immortality=immortality, epic_game=epic_game)
    )
