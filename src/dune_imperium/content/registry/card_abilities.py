"""Personal cards' box records across every game, by card id.

docs/content-core-refactor-plan.md 8.3 (stage 4): a card's records live in
its set's package keyed by its id, as its Reveal record already did, and
this module merges them -- Uprising's first, then Bloodlines', Immortality's
(its Imperium and Tleilaxu cards), the original game's and Rise of Ix's. A
card without such a box reads None. The Agent and Reveal-choice boxes move
here in the stage's later steps. The Agent box tables map a card id to its
box's key (``AGENT_BOX_KEYS``), the stable string its display text and record
are found by.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.bloodlines.agent_abilities import (
    BLOODLINES_AGENT_BOX_ABILITIES,
    BLOODLINES_AGENT_BOXES,
)
from dune_imperium.content.bloodlines.reveal_choice_abilities import (
    BLOODLINES_REVEAL_CHOICES,
)
from dune_imperium.content.bloodlines.trigger_abilities import (
    BLOODLINES_ACQUISITION_ABILITIES,
    BLOODLINES_DISCARD_ABILITIES,
    BLOODLINES_TRASH_ABILITIES,
    BLOODLINES_TURN_START_ABILITIES,
)
from dune_imperium.content.core.abilities import Ability
from dune_imperium.content.core.agent_boxes import (
    SHARED_AGENT_BOX_ABILITIES,
    SIGNET_BOX,
)
from dune_imperium.content.core.card_effects import REVEAL_CHOICE_KEYS
from dune_imperium.content.core.cards import (
    ImperiumCardEntry,
    PersonalCardDefinition,
)
from dune_imperium.content.immortality.agent_abilities import (
    IMMORTALITY_AGENT_BOX_ABILITIES,
    IMMORTALITY_AGENT_BOXES,
    IMMORTALITY_ICON_CONDITIONS,
)
from dune_imperium.content.immortality.reveal_choice_abilities import (
    IMMORTALITY_REVEAL_CHOICES,
)
from dune_imperium.content.immortality.rule_abilities import (
    IMMORTALITY_STANDING_ABILITIES,
)
from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
from dune_imperium.content.immortality.trigger_abilities import (
    IMMORTALITY_ACQUISITION_ABILITIES,
    IMMORTALITY_TRASH_ABILITIES,
)
from dune_imperium.content.imperium.agent_abilities import (
    IMPERIUM_AGENT_BOX_ABILITIES,
    IMPERIUM_AGENT_BOXES,
)
from dune_imperium.content.imperium.reveal_choice_abilities import (
    IMPERIUM_REVEAL_CHOICES,
)
from dune_imperium.content.imperium.trigger_abilities import (
    IMPERIUM_ACQUISITION_ABILITIES,
    IMPERIUM_TRASH_ABILITIES,
)
from dune_imperium.content.registry.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.registry.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.rise_of_ix.agent_abilities import (
    IX_AGENT_BOX_ABILITIES,
    IX_AGENT_BOXES,
)
from dune_imperium.content.rise_of_ix.reveal_choice_abilities import IX_REVEAL_CHOICES
from dune_imperium.content.rise_of_ix.trigger_abilities import IX_ACQUISITION_ABILITIES
from dune_imperium.content.uprising.agent_abilities import (
    UPRISING_AGENT_BOX_ABILITIES,
    UPRISING_AGENT_BOXES,
)
from dune_imperium.content.uprising.reveal_choice_abilities import (
    UPRISING_REVEAL_CHOICES,
)
from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID
from dune_imperium.content.uprising.trigger_abilities import (
    UPRISING_ACQUISITION_ABILITIES,
    UPRISING_DISCARD_ABILITIES,
    UPRISING_REVEAL_ACQUISITION_ABILITIES,
    UPRISING_TRASH_ABILITIES,
)

ACQUISITION_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        **UPRISING_ACQUISITION_ABILITIES,
        **BLOODLINES_ACQUISITION_ABILITIES,
        **IMMORTALITY_ACQUISITION_ABILITIES,
        **IMPERIUM_ACQUISITION_ABILITIES,
        **IX_ACQUISITION_ABILITIES,
    }
)
TRASH_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {
        **UPRISING_TRASH_ABILITIES,
        **BLOODLINES_TRASH_ABILITIES,
        **IMMORTALITY_TRASH_ABILITIES,
        **IMPERIUM_TRASH_ABILITIES,
    }
)
DISCARD_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {**UPRISING_DISCARD_ABILITIES, **BLOODLINES_DISCARD_ABILITIES}
)
REVEAL_ACQUISITION_ABILITIES: Final[Mapping[str, Ability]] = (
    UPRISING_REVEAL_ACQUISITION_ABILITIES
)
TURN_START_ABILITIES: Final[Mapping[str, Ability]] = BLOODLINES_TURN_START_ABILITIES
AGENT_BOXES: Final[Mapping[str, str]] = MappingProxyType(
    {
        **UPRISING_AGENT_BOXES,
        **BLOODLINES_AGENT_BOXES,
        **IMMORTALITY_AGENT_BOXES,
        **IMPERIUM_AGENT_BOXES,
        **IX_AGENT_BOXES,
    }
)
# Every personal card's Agent box key: the stable string the display text,
# the Agent records and the engine's special cases name a box by (the value
# of the retired ``PersonalCardAgentEffect`` member).
AGENT_BOX_KEYS: Final[frozenset[str]] = frozenset(AGENT_BOXES.values())
# Each card's Reveal choice keys in printed order (the keys are
# ``content.core.card_effects.REVEAL_CHOICE_KEYS``).
REVEAL_CHOICES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        **UPRISING_REVEAL_CHOICES,
        **BLOODLINES_REVEAL_CHOICES,
        **IMMORTALITY_REVEAL_CHOICES,
        **IMPERIUM_REVEAL_CHOICES,
        **IX_REVEAL_CHOICES,
    }
)
# The cards whose greyed Agent icons count under a printed condition, by card
# id: each value is the condition's key.
ICON_CONDITIONS: Final[Mapping[str, str]] = IMMORTALITY_ICON_CONDITIONS
ICON_CONDITION_KEYS: Final[frozenset[str]] = frozenset(ICON_CONDITIONS.values())


def card_icon_condition(card: PersonalCardDefinition) -> str | None:
    """The key of the condition under which the card's greyed Agent icons
    count, if it prints one."""

    return ICON_CONDITIONS.get(card.card.card_id)


def card_reveal_choices(card: PersonalCardDefinition) -> tuple[str, ...]:
    """A personal card's Reveal choice keys in printed order (none: empty)."""

    return REVEAL_CHOICES.get(card.card.card_id, ())
# Every Agent-box record, by box key: the records several sets' cards share
# (``content.core.agent_boxes``), then each set's own. The Signet Ring icon's
# box (``SIGNET_BOX``) has none: the owner's Leader record is its effect.
AGENT_BOX_RECORD_TABLES: Final = (
    SHARED_AGENT_BOX_ABILITIES,
    UPRISING_AGENT_BOX_ABILITIES,
    BLOODLINES_AGENT_BOX_ABILITIES,
    IMMORTALITY_AGENT_BOX_ABILITIES,
    IMPERIUM_AGENT_BOX_ABILITIES,
    IX_AGENT_BOX_ABILITIES,
)
AGENT_BOX_ABILITIES: Final[Mapping[str, Ability]] = MappingProxyType(
    {key: record for table in AGENT_BOX_RECORD_TABLES for key, record in table.items()}
)


def agent_box_ability(key: str | None) -> Ability | None:
    """The record of the Agent box ``key`` names; None while its own code
    resolves it (or for no box)."""

    if key is None:
        return None
    return AGENT_BOX_ABILITIES.get(key)


def agent_box_key(card_id: str) -> str | None:
    """The key of the card's Agent box, if it prints one (a personal card)."""

    return AGENT_BOXES.get(card_id)


def card_agent_box(card: PersonalCardDefinition) -> str | None:
    """The key of a personal card's Agent box, if it prints one -- for
    Ghola's copy borrowing a box, the borrowed one."""

    if isinstance(card, ImperiumCardEntry) and card.borrowed_agent_box is not None:
        return card.borrowed_agent_box
    return AGENT_BOXES.get(card.card.card_id)


def box_uses_signet(key: str | None) -> bool:
    """Whether the Agent box ``key`` is the Signet Ring icon's, whose effect
    is the owner's Leader's Signet Ring ability [Main p. 20]."""

    return key == SIGNET_BOX


# Printed rule changes standing on a card (Immortality's Ghola, Usurp and
# Tleilaxu Infiltrator, and the Family Atomics token), by card id: each
# names the engine branch that applies it (``Ability.hook``).
STANDING_ABILITIES: Final[Mapping[str, Ability]] = IMMORTALITY_STANDING_ABILITIES


def card_standing_hook(card: PersonalCardDefinition) -> str | None:
    """The engine branch a personal card's printed rule change names, if it
    prints one."""

    record = STANDING_ABILITIES.get(card.card.card_id)
    return None if record is None else record.hook


def acquisition_ability(card_id: str) -> Ability | None:
    """The record of the card's acquire box, if it prints one (an Imperium
    or a Tleilaxu card)."""

    return ACQUISITION_ABILITIES.get(card_id)


def trash_ability(card_id: str) -> Ability | None:
    """The record of the card's trash box, if it prints one."""

    return TRASH_ABILITIES.get(card_id)


def discard_ability(card_id: str) -> Ability | None:
    """The record of the card's discard box, if it prints one."""

    return DISCARD_ABILITIES.get(card_id)


def reveal_acquisition_ability(card_id: str) -> Ability | None:
    """The record of the card's box that fires on an acquisition during its
    owner's Reveal turn (Guild Spy), if it prints one."""

    return REVEAL_ACQUISITION_ABILITIES.get(card_id)


def turn_start_ability(card_id: str) -> Ability | None:
    """The record of the card's turn-start alternative (Litany Against Fear),
    if it prints one."""

    return TURN_START_ABILITIES.get(card_id)


def _check_cards() -> None:
    """Every record names an Imperium (or, for an acquire box, a Tleilaxu)
    card whose play data is complete, and an acquire box a card that prints an
    acquisition bonus -- as the card's own fields were checked before they
    moved here."""

    for card_id in ACQUISITION_ABILITIES:
        acquired: ImperiumCardEntry | None = IMPERIUM_CARDS_BY_ID.get(
            card_id, TLEILAXU_CARDS_BY_ID.get(card_id)
        )
        if (
            acquired is None
            or not acquired.play_data_complete
            or not acquired.has_acquisition_bonus
        ):
            raise ValueError(f"{card_id} is not a complete card with an acquire box")

    tables = (
        UPRISING_AGENT_BOXES,
        BLOODLINES_AGENT_BOXES,
        IMMORTALITY_AGENT_BOXES,
        IMPERIUM_AGENT_BOXES,
        IX_AGENT_BOXES,
    )
    if sum(map(len, tables)) != len(AGENT_BOXES):
        raise ValueError("a card's Agent box is listed by two sets")
    personal: dict[str, PersonalCardDefinition] = {
        **STARTING_CARDS_BY_ID,
        **RESERVE_STACKS_BY_ID,
        **IMPERIUM_CARDS_BY_ID,
        **TLEILAXU_CARDS_BY_ID,
    }
    for card_id in AGENT_BOXES:
        card = personal.get(card_id)
        if card is None or (
            isinstance(card, ImperiumCardEntry) and not card.play_data_complete
        ):
            raise ValueError(f"{card_id} is not a complete personal card")
    if sum(map(len, AGENT_BOX_RECORD_TABLES)) != len(AGENT_BOX_ABILITIES):
        raise ValueError("an Agent-box record is kept by two sets")
    if set(AGENT_BOX_ABILITIES) != AGENT_BOX_KEYS - {SIGNET_BOX}:
        raise ValueError("every Agent box but the Signet Ring needs one record")
    choice_tables = (
        UPRISING_REVEAL_CHOICES,
        BLOODLINES_REVEAL_CHOICES,
        IMMORTALITY_REVEAL_CHOICES,
        IMPERIUM_REVEAL_CHOICES,
        IX_REVEAL_CHOICES,
    )
    if sum(map(len, choice_tables)) != len(REVEAL_CHOICES):
        raise ValueError("a card's Reveal choices are listed by two sets")
    known = frozenset(REVEAL_CHOICE_KEYS)
    for card_id, choices in REVEAL_CHOICES.items():
        card = personal.get(card_id)
        if card is None or (
            isinstance(card, ImperiumCardEntry) and not card.play_data_complete
        ):
            raise ValueError(f"{card_id} is not a complete personal card")
        if not choices or len(set(choices)) != len(choices):
            raise ValueError(f"{card_id}'s Reveal choices must be unique")
        if not known.issuperset(choices):
            raise ValueError(f"{card_id} names an unknown Reveal choice")
    for card_id in ICON_CONDITIONS:
        card = personal.get(card_id)
        if not isinstance(card, ImperiumCardEntry) or not card.play_data_complete:
            raise ValueError(f"{card_id} is not a complete Imperium card")
    # A card naming the Factions its Spy may go to places a Spy.
    for card_id, card in personal.items():
        if card.agent_spy_factions and AGENT_BOXES.get(card_id) != "place_spy":
            raise ValueError("Spy target Factions require a place-Spy Agent effect")

    for table in (
        TRASH_ABILITIES,
        DISCARD_ABILITIES,
        REVEAL_ACQUISITION_ABILITIES,
        TURN_START_ABILITIES,
    ):
        for card_id in table:
            entry = IMPERIUM_CARDS_BY_ID.get(card_id)
            if entry is None or not entry.play_data_complete:
                raise ValueError(f"{card_id} is not a complete Imperium card")


_check_cards()
