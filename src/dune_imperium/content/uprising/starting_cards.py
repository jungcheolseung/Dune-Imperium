"""The ten-card Uprising starting deck listed in Main Rulebook p. 3."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAgentEffect,
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
    reveal_persuasion: int = 0
    reveal_strength: int = 0
    reveal_effects: tuple[PersonalCardRevealEffect, ...] = ()

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("starting-card copies must be positive")
        if len(self.agent_icons) != len(set(self.agent_icons)):
            raise ValueError("starting-card Agent icons must be unique")
        if len(self.factions) != len(set(self.factions)):
            raise ValueError("starting-card Factions must be unique")
        if len(self.reveal_effects) != len(set(self.reveal_effects)):
            raise ValueError("starting-card Reveal effects must be unique")
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

STARTING_CARDS_BY_ID: Final = {
    entry.card.card_id: entry for entry in STARTING_DECK
}


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


def starting_deck_instance_ids(player: int) -> tuple[str, ...]:
    """Create stable IDs for one player's unshuffled starting cards."""

    if player < 0:
        raise ValueError("player must not be negative")
    return tuple(
        f"player:{player}:starter:{entry.card.card_id}:{copy}"
        for entry in STARTING_DECK
        for copy in range(entry.copies)
    )
