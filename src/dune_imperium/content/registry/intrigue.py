"""Every Intrigue card any game prints, by id and by instance, and its resolver.

The original game's cards resolve here too (stage P3, plan 16), and Rise
of Ix's identity entries (stage P4a, plan 17) join them the same way.
``INTRIGUE_CARDS`` is the Uprising-format universe -- ``content.uprising.
intrigue``'s own cards, then Bloodlines' and Immortality's from their
packages (stage 4, plan 8.3) -- with the CHOAM, deck, Navigation and
Twisted filters over it.
Moved from ``content.uprising.intrigue`` (docs/content-core-refactor-plan.md
2B).
"""

from typing import Final

from dune_imperium.config import BaseGame
from dune_imperium.content.bloodlines.intrigue import (
    BLOODLINES_INTRIGUE_CARDS,
    ORIGINAL_GAME_LEFT_OUT_NAVIGATION_IDS,
)
from dune_imperium.content.core.cards import IntrigueCardEntry
from dune_imperium.content.core.schema import GameOption
from dune_imperium.content.immortality.intrigue import IMMORTALITY_INTRIGUE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.uprising.intrigue import UPRISING_INTRIGUE_CARDS

# The Uprising-format deck: Uprising's cards, then Bloodlines' and
# Immortality's (each dealt only with its option, ``intrigue_cards_for_choam``).
INTRIGUE_CARDS: Final = (
    *UPRISING_INTRIGUE_CARDS,
    *BLOODLINES_INTRIGUE_CARDS,
    *IMMORTALITY_INTRIGUE_CARDS,
)

INTRIGUE_CARDS_BY_ID: Final = {
    entry.card.card_id: entry
    for entry in (*INTRIGUE_CARDS, *IMPERIUM_INTRIGUE_CARDS, *IX_INTRIGUE_CARDS)
}
# Every physical copy of every identity, whatever the setup includes.
INTRIGUE_CARDS_BY_INSTANCE: Final = {
    f"intrigue:{entry.card.card_id}:{copy}": entry
    for entry in (*INTRIGUE_CARDS, *IMPERIUM_INTRIGUE_CARDS, *IX_INTRIGUE_CARDS)
    for copy in range(entry.copies)
}


def is_twisted_intrigue(instance_id: str) -> bool:
    """Return whether ``instance_id`` is one of Piter De Vries' Twisted cards.

    An ID outside the catalog (a test stand-in) is not Twisted.
    """

    entry = INTRIGUE_CARDS_BY_INSTANCE.get(instance_id)
    return entry is not None and entry.twisted


def intrigue_card_for_instance(instance_id: str) -> IntrigueCardEntry:
    """Return the Intrigue definition behind one ``intrigue:<id>:<copy>`` ID."""

    try:
        return INTRIGUE_CARDS_BY_INSTANCE[instance_id]
    except KeyError as error:
        raise ValueError(f"unknown Intrigue card instance: {instance_id}") from error


def intrigue_cards_for_choam(
    choam_module: bool,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
    immortality: bool = False,
) -> tuple[IntrigueCardEntry, ...]:
    """Return physical card entries included by the selected setup.

    Bloodlines cards join only with the option [Bloodlines p. 3] and
    Immortality cards only with theirs [Immortality p. 5], and only once
    their options are transcribed (an untranscribed card cannot be played,
    so it waits out of the deck).
    """

    return tuple(
        entry
        for entry in INTRIGUE_CARDS
        if (choam_module or GameOption.CHOAM_MODULE not in entry.requires)
        and not entry.twisted
        and not entry.navigation
        and (
            GameOption.BLOODLINES not in entry.requires
            or (
                bloodlines
                and entry.play_data_complete
                and (tech_module or GameOption.TECH_MODULE not in entry.requires)
            )
        )
        and (
            GameOption.IMMORTALITY not in entry.requires
            or (immortality and entry.play_data_complete)
        )
    )


def navigation_card_instance_ids(
    base_game: BaseGame = BaseGame.UPRISING,
) -> tuple[str, ...]:
    """Return the Navigation cards (Steersman Y'rkoon), in printed order: the
    ten, or the original game's nine (``ORIGINAL_GAME_LEFT_OUT_NAVIGATION_IDS``)."""

    return tuple(
        f"intrigue:{entry.card.card_id}:0"
        for entry in INTRIGUE_CARDS
        if entry.navigation
        and (
            base_game is BaseGame.UPRISING
            or entry.card.card_id not in ORIGINAL_GAME_LEFT_OUT_NAVIGATION_IDS
        )
    )


def twisted_intrigue_instance_ids() -> tuple[str, ...]:
    """Return the twelve Twisted Intrigue cards (Piter De Vries)."""

    return tuple(
        f"intrigue:{entry.card.card_id}:0" for entry in INTRIGUE_CARDS if entry.twisted
    )


def intrigue_deck_instance_ids(
    choam_module: bool,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
    immortality: bool = False,
) -> tuple[str, ...]:
    """Return stable IDs for every physical Intrigue card copy."""

    return tuple(
        f"intrigue:{entry.card.card_id}:{copy}"
        for entry in intrigue_cards_for_choam(
            choam_module,
            bloodlines=bloodlines,
            tech_module=tech_module,
            immortality=immortality,
        )
        for copy in range(entry.copies)
    )
