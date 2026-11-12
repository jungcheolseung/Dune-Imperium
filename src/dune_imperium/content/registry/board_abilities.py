"""Every board space's printed icons as records, across every board.

The original game's spaces share the table (one id, one printing;
docs/base-game-and-ix-plan.md 4.2 item 7), then Rise of Ix's four spaces
(no other board holds them), then Uprising's. Merged here from
``content.uprising.board_abilities`` (docs/content-core-refactor-plan.md 2B).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.content.core.abilities import Ability
from dune_imperium.content.imperium.board_abilities import (
    IMPERIUM_BOARD_CHOICE_ABILITIES,
    IMPERIUM_BOARD_SPACE_ABILITIES,
    IMPERIUM_SHARED_OVERLAYS,
)
from dune_imperium.content.rise_of_ix.board_abilities import (
    IX_BOARD_SPACE_ABILITIES,
)
from dune_imperium.content.uprising.board_abilities import (
    UPRISING_BOARD_CHOICE_ABILITIES,
    UPRISING_BOARD_SPACE_ABILITIES,
)

BOARD_SPACE_ABILITIES: Final[Mapping[tuple[str, int, str], Ability]] = MappingProxyType(
    {
        **IMPERIUM_BOARD_SPACE_ABILITIES,
        **IX_BOARD_SPACE_ABILITIES,
        **UPRISING_BOARD_SPACE_ABILITIES,
    }
)

BOARD_CHOICE_ABILITIES: Final[Mapping[tuple[str, str], Ability]] = MappingProxyType(
    {
        **IMPERIUM_BOARD_CHOICE_ABILITIES,
        **UPRISING_BOARD_CHOICE_ABILITIES,
    }
)


def board_space_ability(
    space_id: str,
    cost_option: int,
    *,
    choam_module: bool,
    immortality: bool,
    seated: bool = False,
) -> Ability | None:
    """The record of one visit's printed icons, the printed alternative the
    modules and the visitor select first; None for a space resolved by its
    own choice. An original space an overlay covers reads the overlay's one
    record (``IMPERIUM_SHARED_OVERLAYS``)."""

    for variant, applies in (
        ("no_choam", not choam_module),
        ("immortality", immortality),
        ("seated", seated),
    ):
        if not applies:
            continue
        if (space_id, cost_option, variant) in BOARD_SPACE_ABILITIES:
            return BOARD_SPACE_ABILITIES[space_id, cost_option, variant]
        # An overlay printed once for both boards (the Research Station's).
        shared = IMPERIUM_SHARED_OVERLAYS.get((space_id, variant))
        if shared is not None:
            return BOARD_SPACE_ABILITIES[shared, cost_option, variant]
    return BOARD_SPACE_ABILITIES.get((space_id, cost_option, ""))
