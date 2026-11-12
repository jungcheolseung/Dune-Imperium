"""Bloodlines' personal cards' Reveal choices, by card id.

docs/content-core-refactor-plan.md 8.3 (stage 4, step 4): each value lists
the card's Reveal choice keys in printed order -- the stable strings the
codec rows, the choice frames and the records name them by
(``content.registry.card_abilities.card_reveal_choices``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

BLOODLINES_REVEAL_CHOICES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "arrakis_observer": ("may_recall_spy_for_three_strength",),
        "choam_demands": ("may_trash_self_for_four_influence_if_four_contracts",),
        "command_center": ("may_retreat_two_troops_for_two_persuasion",),
        "delivery_logistics": ("persuasion_or_contract",),
        "disruption_tactics": ("may_trash_self_for_combat_icon",),
        "engineered_miracle": ("command_may_trash_self_to_acquire_row_card",),
        "intelligence_training": ("command_place_spy",),
        "ixian_ambassador": ("gain_chosen_influence_if_two_tech",),
        "pointing_the_way": ("command_gain_chosen_influence",),
        "shrouded_counsel": ("command_may_trash_card",),
    }
)
