"""Every Imperium card any game prints, by id, and its instance resolver.

The original game's cards resolve here too (stage P3, plan 16): a lookup
table across both base games, as ``BOARD_SPACES_BY_ID`` is. Rise of Ix's
identity entries (stage P4a, plan 17) join it the same way. ``IMPERIUM_CARDS``
is the Uprising-format universe -- ``content.uprising.imperium``'s own cards,
then Bloodlines' and Immortality's from their packages (stage 4, plan 8.3)
-- with the CHOAM and deck filters over it.
Moved from ``content.uprising.imperium`` (docs/content-core-refactor-plan.md
2B).
"""

from typing import Final

from dune_imperium.content.bloodlines.imperium import BLOODLINES_IMPERIUM_CARDS
from dune_imperium.content.core.cards import ImperiumCardEntry
from dune_imperium.content.core.kept import kept_by_id
from dune_imperium.content.core.schema import GameOption
from dune_imperium.content.immortality.imperium import IMMORTALITY_IMPERIUM_CARDS
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.uprising.imperium import UPRISING_IMPERIUM_CARDS

# The Uprising-format deck: Uprising's cards, then Bloodlines' and
# Immortality's (each dealt only with its option, ``imperium_cards_for_choam``).
IMPERIUM_CARDS: Final = (
    *UPRISING_IMPERIUM_CARDS,
    *BLOODLINES_IMPERIUM_CARDS,
    *IMMORTALITY_IMPERIUM_CARDS,
)

IMPERIUM_CARDS_BY_ID: Final = {
    entry.card.card_id: entry
    for entry in (*IMPERIUM_CARDS, *IMPERIUM_BASE_CARDS, *IX_IMPERIUM_CARDS)
}


@kept_by_id
def imperium_card_for_instance(instance_id: str) -> ImperiumCardEntry:
    """Resolve a stable Imperium deck instance ID to its definition."""

    prefix = "imperium:"
    if not instance_id.startswith(prefix):
        raise ValueError("not an Imperium-card instance ID")
    try:
        card_id, copy_text = instance_id.removeprefix(prefix).rsplit(":", maxsplit=1)
        copy = int(copy_text)
        entry = IMPERIUM_CARDS_BY_ID[card_id]
    except (KeyError, ValueError) as error:
        raise ValueError("unknown Imperium-card instance ID") from error
    if copy < 0 or copy >= entry.copies:
        raise ValueError("Imperium-card copy index is out of range")
    return entry


def imperium_cards_for_choam(
    choam_module: bool,
    promo_cards: bool = False,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
    immortality: bool = False,
) -> tuple[ImperiumCardEntry, ...]:
    """Return physical card entries included by the selected setup.

    Bloodlines cards join only with the option [Bloodlines p. 3] and
    Immortality cards only with theirs [Immortality p. 4], and only once
    their play data is complete: an incomplete card would be inert in a
    hand, so it waits out of the deck until its slice lands.
    """

    return tuple(
        entry
        for entry in IMPERIUM_CARDS
        if (choam_module or GameOption.CHOAM_MODULE not in entry.requires)
        and (promo_cards or GameOption.PROMO_CARDS not in entry.requires)
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


def imperium_deck_instance_ids(
    choam_module: bool,
    promo_cards: bool = False,
    *,
    bloodlines: bool = False,
    tech_module: bool = False,
    immortality: bool = False,
) -> tuple[str, ...]:
    """Return stable IDs for every physical Imperium card copy."""

    return tuple(
        f"imperium:{entry.card.card_id}:{copy}"
        for entry in imperium_cards_for_choam(
            choam_module,
            promo_cards,
            bloodlines=bloodlines,
            tech_module=tech_module,
            immortality=immortality,
        )
        for copy in range(entry.copies)
    )
