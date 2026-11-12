"""Every Reserve stack any game prints, by id, and its instance resolver.

The original game's stacks follow Uprising's. Moved from
``content.uprising.reserve`` (docs/content-core-refactor-plan.md 2B).
"""

from collections.abc import Iterable
from typing import Final

from dune_imperium.content.core.cards import ReserveStackDefinition
from dune_imperium.content.core.kept import kept_by_id
from dune_imperium.content.imperium.reserve import IMPERIUM_RESERVE_STACKS
from dune_imperium.content.uprising.reserve import RESERVE_STACKS

RESERVE_STACKS_BY_ID: Final = {
    stack.card.card_id: stack for stack in (*RESERVE_STACKS, *IMPERIUM_RESERVE_STACKS)
}


def reserve_printing(card_id: str, stack_ids: Iterable[str]) -> str:
    """The Reserve card a sentence naming ``card_id`` acquires in a game
    whose Reserve holds ``stack_ids``: that printing when the game has it,
    else the game's printing of the same card by name -- an id names one
    printing (``content.rulesets``), and the original game's The Spice Must
    Flow is its own ("imperium_the_spice_must_flow"), as the two printings a
    sentence naming it reads elsewhere (``ReserveCostDiscount.card_ids``,
    ``rules.conditions.spice_must_flow_copies``). Bloodlines' Navigation card
    4 names Uprising's (stage P7c)."""

    stacks = tuple(stack_ids)
    if card_id in stacks:
        return card_id
    name = RESERVE_STACKS_BY_ID[card_id].card.name
    return next(
        (other for other in stacks if RESERVE_STACKS_BY_ID[other].card.name == name),
        card_id,
    )


@kept_by_id
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
