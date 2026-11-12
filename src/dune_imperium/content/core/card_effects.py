"""The personal cards' Reveal choice keys and the codec's sets of them.

Stage 4 of docs/content-core-refactor-plan.md retired this module's enums (one
per kind of printed box): an Agent box, a Reveal choice and a greyed-icon
condition are named by plain string keys -- the values their members had --
and each card's keys live in its set's package, by card id
(``content.registry.card_abilities``). What stays here is codec v165's own:
the Reveal choice keys in catalog order and the sets its catalog filters by.
"""

from typing import Final

# Every Reveal choice key, in the order codec v165's catalog lists their
# ``resume_reveal_choice`` rows (the retired ``PersonalCardRevealChoiceEffect``
# member order): the keys sit in those rows and in the Reveal choice frames'
# context, so they are stable ids. A new key goes at the end, with a codec bump.
REVEAL_CHOICE_KEYS: Final[tuple[str, ...]] = (
    "recall_spy_to_draw_intrigue_if_two_placed",
    "may_recall_two_spies_for_three_persuasion",
    "place_spy",
    "place_two_spies",
    "place_spy_or_gain_two_strength",
    "may_lose_influence_to_gain_influence",
    "may_pay_three_spice_for_influence",
    "may_trash_other_emperor_for_three_strength",
    "may_retreat_two_troops_for_four_strength",
    "gain_five_solari_or_take_high_council",
    "may_pay_water_for_sandworm",
    "keep_spice_or_trash_self_for_vp_if_four_contracts",
    "command_may_trash_card",
    "command_place_spy",
    "command_gain_chosen_influence",
    "may_retreat_two_troops_for_two_persuasion",
    "may_trash_self_for_combat_icon",
    "may_recall_spy_for_three_strength",
    "command_may_trash_self_to_acquire_row_card",
    "may_trash_self_for_four_influence_if_four_contracts",
    "persuasion_or_contract",
    "gain_chosen_influence_if_two_tech",
    "may_lose_influence_for_vp_if_bene_gesserit_alliance",
    "may_deploy_or_retreat_one_troop",
    "may_deploy_or_retreat_one_troop_if_fremen_bond",
    "may_lose_two_troops_for_two_specimens",
    "may_deploy_one_troop",
    "choose_two_persuasion_or_two_strength",
    "may_pay_six_solari_for_victory_point",
    "may_pay_three_spice_for_victory_point_if_spacing_guild_alliance",
    "may_pay_three_solari_for_two_troops_and_deploy",
    "may_deploy_up_to_three_troops",
    "may_retreat_up_to_two_troops",
    "may_retreat_any_number_of_troops",
    "may_trash_self_to_move_any_number_of_troops",
    "may_move_freighter",
    "may_retreat_three_units_for_influence",
    "gain_chosen_influence",
    "may_trash_self_for_victory_point_if_three_tech_tiles",
    "may_place_two_negotiators",
    "may_place_negotiator",
    "acquire_card_up_to_five",
)
_REVEAL_CHOICE_KEY_SET: Final = frozenset(REVEAL_CHOICE_KEYS)


def checked_reveal_choice(value: str) -> str:
    """``value`` as a Reveal choice key; ValueError if no card prints it (as
    the retired enum's constructor raised)."""

    if value not in _REVEAL_CHOICE_KEY_SET:
        raise ValueError(f"{value!r} is not a valid Reveal choice key")
    return value


# Choice effects added by Bloodlines: their action templates join only the
# option's catalogs so the retail catalogs keep their size.
BLOODLINES_REVEAL_CHOICE_EFFECTS: frozenset[str] = frozenset(
    {
        "command_may_trash_card",
        "command_place_spy",
        "command_gain_chosen_influence",
        "may_retreat_two_troops_for_two_persuasion",
        "may_trash_self_for_combat_icon",
        "may_recall_spy_for_three_strength",
        "command_may_trash_self_to_acquire_row_card",
        "may_trash_self_for_four_influence_if_four_contracts",
        "persuasion_or_contract",
        "gain_chosen_influence_if_two_tech",
    }
)


# Choice effects added by the original game's Imperium cards (stage P3), and
# by the Rise of Ix cards played on it (stage P4d; Uprising with Rise of Ix is
# P7): outside every Uprising catalog, whose resume templates list one per
# choice effect of the Uprising family only.
IMPERIUM_REVEAL_CHOICE_EFFECTS: frozenset[str] = frozenset(
    {
        "may_move_freighter",
        "may_retreat_three_units_for_influence",
        "may_deploy_one_troop",
        "choose_two_persuasion_or_two_strength",
        "may_pay_six_solari_for_victory_point",
        "may_pay_three_spice_for_victory_point_if_spacing_guild_alliance",
        "may_pay_three_solari_for_two_troops_and_deploy",
        "may_deploy_up_to_three_troops",
        "may_retreat_up_to_two_troops",
        "may_retreat_any_number_of_troops",
        "may_trash_self_to_move_any_number_of_troops",
        "gain_chosen_influence",
        "may_trash_self_for_victory_point_if_three_tech_tiles",
        "may_place_two_negotiators",
        "may_place_negotiator",
        "acquire_card_up_to_five",
    }
)


# Choice effects added by Immortality; like the Bloodlines set their
# templates join only the option's catalogs.
IMMORTALITY_REVEAL_CHOICE_EFFECTS: frozenset[str] = (
    frozenset(
        {
            "may_lose_influence_for_vp_if_bene_gesserit_alliance",
            "may_deploy_or_retreat_one_troop",
            "may_lose_two_troops_for_two_specimens",
        }
    )
)
