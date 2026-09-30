"""The ten-card Uprising starting deck listed in Main Rulebook p. 3."""

from dataclasses import dataclass, replace
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAgentEffect,
    PersonalCardDiscardEffect,
    PersonalCardRevealAcquisitionEffect,
    PersonalCardRevealChoiceEffect,
    PersonalCardRevealEffect,
)

# Backward-compatible content name; Agent effects are now shared by every
# personal Imperium-card source rather than being starting-card-specific.
StartingCardAgentEffect = PersonalCardAgentEffect


@dataclass(frozen=True, slots=True)
class StartingCardEntry:
    """One starting-card definition and its per-player quantity."""

    card: CardDefinition
    copies: int
    factions: tuple[Faction, ...] = ()
    agent_icons: tuple[AgentIcon, ...] = ()
    agent_effect: PersonalCardAgentEffect | None = None
    agent_spy_factions: tuple[Faction, ...] = ()
    discard_effect: PersonalCardDiscardEffect | None = None
    reveal_acquisition_effect: PersonalCardRevealAcquisitionEffect | None = None
    reveal_persuasion: int = 0
    reveal_strength: int = 0
    reveal_effects: tuple[PersonalCardRevealEffect, ...] = ()
    reveal_choice_effects: tuple[PersonalCardRevealChoiceEffect, ...] = ()

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("starting-card copies must be positive")
        if len(self.agent_icons) != len(set(self.agent_icons)):
            raise ValueError("starting-card Agent icons must be unique")
        if len(self.factions) != len(set(self.factions)):
            raise ValueError("starting-card Factions must be unique")
        if len(self.agent_spy_factions) != len(set(self.agent_spy_factions)):
            raise ValueError("starting-card Spy target Factions must be unique")
        if self.agent_spy_factions and (
            self.agent_effect is not PersonalCardAgentEffect.PLACE_SPY
        ):
            raise ValueError("Spy target Factions require a place-Spy Agent effect")
        if len(self.reveal_effects) != len(set(self.reveal_effects)):
            raise ValueError("starting-card Reveal effects must be unique")
        if len(self.reveal_choice_effects) != len(set(self.reveal_choice_effects)):
            raise ValueError("starting-card Reveal choices must be unique")
        if min(self.reveal_persuasion, self.reveal_strength) < 0:
            raise ValueError("starting-card Reveal values must not be negative")


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
        agent_effect=PersonalCardAgentEffect.TRASH_SELF,
    ),
    StartingCardEntry(
        CardDefinition("signet_ring", "Signet Ring", MAIN_P3),
        copies=1,
        agent_icons=(
            AgentIcon.LANDSRAAD,
            AgentIcon.CITY,
            AgentIcon.SPICE_TRADE,
        ),
        agent_effect=PersonalCardAgentEffect.LEADER_SIGNET,
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
    agent_effect=PersonalCardAgentEffect.RESEARCH,
    reveal_persuasion=1,
    reveal_effects=(PersonalCardRevealEffect(specimens=1),),
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
    agent_effect=PersonalCardAgentEffect.MAY_PAY_SPICE_TO_TRASH_AND_RECRUIT,
    reveal_persuasion=1,
    reveal_effects=(PersonalCardRevealEffect(spice=1),),
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


def starting_deck_instance_ids(
    player: int, *, immortality: bool = False, epic_game: bool = False
) -> tuple[str, ...]:
    """Create stable IDs for one player's unshuffled starting cards."""

    if player < 0:
        raise ValueError("player must not be negative")
    return tuple(
        f"player:{player}:starter:{entry.card.card_id}:{copy}"
        for entry in starting_deck_entries(
            immortality=immortality, epic_game=epic_game
        )
        for copy in range(entry.copies)
    )


def starting_discard_instance_ids(
    player: int, *, immortality: bool = False, epic_game: bool = False
) -> tuple[str, ...]:
    """Create stable IDs for one player's starting discard pile."""

    if player < 0:
        raise ValueError("player must not be negative")
    return tuple(
        f"player:{player}:starter:{entry.card.card_id}:{copy}"
        for entry in starting_discard_entries(
            immortality=immortality, epic_game=epic_game
        )
        for copy in range(entry.copies)
    )
