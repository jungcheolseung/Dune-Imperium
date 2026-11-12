"""Immortality's personal cards' Reveal choices, by card id.

docs/content-core-refactor-plan.md 8.3 (stage 4, step 4): each value lists
the card's Reveal choice keys in printed order -- the stable strings the
codec rows, the choice frames and the records name them by
(``content.registry.card_abilities.card_reveal_choices``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

IMMORTALITY_REVEAL_CHOICES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "for_humanity": ("may_lose_influence_for_vp_if_bene_gesserit_alliance",),
        "shadout_mapes": ("may_deploy_or_retreat_one_troop",),
        "tleilaxu_surgeon": ("may_lose_two_troops_for_two_specimens",),
    }
)
