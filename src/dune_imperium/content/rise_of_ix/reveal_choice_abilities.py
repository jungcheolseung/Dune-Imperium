"""Rise of Ix's personal cards' Reveal choices, by card id.

docs/content-core-refactor-plan.md 8.3 (stage 4, step 4): each value lists
the card's Reveal choice keys in printed order -- the stable strings the
codec rows, the choice frames and the records name them by
(``content.registry.card_abilities.card_reveal_choices``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

IX_REVEAL_CHOICES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "freighter_fleet": ("may_move_freighter",),
        "guild_chief_administrator": ("may_move_freighter",),
        "ix_guild_compact": ("may_place_two_negotiators",),
        "ixian_engineer": ("may_trash_self_for_victory_point_if_three_tech_tiles",),
        "negotiated_withdrawal": ("may_retreat_three_units_for_influence",),
        "satellite_ban": ("may_retreat_up_to_two_troops",),
        "web_of_power": ("gain_chosen_influence",),
        "boundless_ambition": ("acquire_card_up_to_five",),
    }
)
