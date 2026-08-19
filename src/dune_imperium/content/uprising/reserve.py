"""Finite Uprising Reserve stacks."""

from dataclasses import dataclass
from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.types import (
    AgentIcon,
    PersonalCardAgentEffect,
    PersonalCardRevealEffect,
)


@dataclass(frozen=True, slots=True)
class ReserveStackDefinition:
    """One face-up Reserve stack and its physical quantity."""

    card: CardDefinition
    copies: int
    acquisition_cost: int
    acquisition_vp: int = 0
    factions: tuple[Faction, ...] = ()
    agent_icons: tuple[AgentIcon, ...] = ()
    agent_effect: PersonalCardAgentEffect | None = None
    reveal_persuasion: int = 0
    reveal_strength: int = 0
    reveal_effects: tuple[PersonalCardRevealEffect, ...] = ()

    def __post_init__(self) -> None:
        if self.copies < 1:
            raise ValueError("reserve stack copies must be positive")
        if min(
            self.acquisition_cost,
            self.acquisition_vp,
            self.reveal_persuasion,
            self.reveal_strength,
        ) < 0:
            raise ValueError("Reserve acquisition values must not be negative")
        if len(self.agent_icons) != len(set(self.agent_icons)):
            raise ValueError("Reserve Agent icons must be unique")
        if len(self.factions) != len(set(self.factions)):
            raise ValueError("Reserve Factions must be unique")
        if len(self.reveal_effects) != len(set(self.reveal_effects)):
            raise ValueError("Reserve Reveal effects must be unique")


MAIN_P3_P5: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 5)),)

RESERVE_STACKS: Final = (
    ReserveStackDefinition(
        CardDefinition(
            "prepare_the_way",
            "Prepare the Way",
            MAIN_P3_P5,
            catalog_url=("https://dunecardshub.com/cards/537/uprising-prepare-the-way"),
        ),
        copies=8,
        acquisition_cost=2,
        agent_icons=(AgentIcon.LANDSRAAD, AgentIcon.CITY),
        agent_effect=(
            PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
        ),
        reveal_persuasion=2,
    ),
    ReserveStackDefinition(
        CardDefinition(
            "the_spice_must_flow",
            "The Spice Must Flow",
            MAIN_P3_P5,
            catalog_url=(
                "https://dunecardshub.com/cards/538/uprising-the-spice-must-flow"
            ),
        ),
        copies=10,
        acquisition_cost=9,
        acquisition_vp=1,
        reveal_strength=1,
    ),
)

RESERVE_STACKS_BY_ID: Final = {
    stack.card.card_id: stack for stack in RESERVE_STACKS
}


def reserve_card_for_instance(instance_id: str) -> ReserveStackDefinition:
    """Resolve one stable physical Reserve-card instance ID."""

    prefix = "reserve:"
    if not instance_id.startswith(prefix):
        raise ValueError("not a Reserve-card instance ID")
    try:
        card_id, copy_text = instance_id.removeprefix(prefix).rsplit(":", maxsplit=1)
        copy = int(copy_text)
        entry = RESERVE_STACKS_BY_ID[card_id]
    except (KeyError, ValueError) as error:
        raise ValueError("unknown Reserve-card instance ID") from error
    if copy < 0 or copy >= entry.copies:
        raise ValueError("Reserve-card copy index is out of range")
    return entry
