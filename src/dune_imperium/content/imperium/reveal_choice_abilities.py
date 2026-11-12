"""The original Dune: Imperium's personal cards' Reveal choices, by card id.

docs/content-core-refactor-plan.md 8.3 (stage 4, step 4): each value lists
the card's Reveal choice keys in printed order -- the stable strings the
codec rows, the choice frames and the records name them by
(``content.registry.card_abilities.card_reveal_choices``).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

IMPERIUM_REVEAL_CHOICES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "gun_thopter": ("may_deploy_one_troop",),
        "bene_gesserit_sister": ("choose_two_persuasion_or_two_strength",),
        "chani_card": ("may_retreat_any_number_of_troops",),
        "guild_ambassador": (
            "may_pay_three_spice_for_victory_point_if_spacing_guild_alliance",
        ),
        "gurney_halleck_card": ("may_pay_three_solari_for_two_troops_and_deploy",),
        "opulence": ("may_pay_six_solari_for_victory_point",),
        "sardaukar_legion": ("may_deploy_up_to_three_troops",),
        "scout": ("may_retreat_up_to_two_troops",),
        "duncan_loyal_blade": ("may_trash_self_to_move_any_number_of_troops",),
    }
)
