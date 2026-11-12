"""Every app archetype of the app AI (all sets, Hagal and mode-only
content excluded): every attribute the AI can read, and the ability
list. ``in_uprising``/``in_uprising_choam`` say whether a 4-player
Uprising game deals it without/with the CHOAM module.

Generated data: do not edit by hand. Keys are ``<kind>.<set>.<name>``,
e.g. ``imperium.uprising.captured_mentat``.
"""

# ruff: noqa: E501  (generated data: ability class names do not wrap)

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final


@dataclass(frozen=True, slots=True)
class Archetype:
    """One app archetype: identity, game membership and attributes."""

    short: str
    kind: str
    title: str | None
    in_uprising: bool
    in_uprising_choam: bool
    attributes: Mapping[str, object]


ARCHETYPES: Final[Mapping[str, Archetype]] = MappingProxyType(
    {
        "conflict.original.battle_for_arrakeen": Archetype(
            short="conflict.original.battle_for_arrakeen",
            kind="conflict",
            title="Battle for Arrakeen",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.battle_for_arrakeen",
                    "ConflictLevel": 3,
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.arrakeen",),
                    "SetList": ("original",),
                    "Tags": ("Control",),
                    "VictoryPoints": 2,
                    "AbilityIDs": (
                        "ability.conflict.original.battle_for_arrakeen_first",
                        "ability.conflict.original.battle_for_arrakeen_second",
                        "ability.conflict.original.battle_for_arrakeen_third",
                    ),
                }
            ),
        ),
        "conflict.original.battle_for_carthag": Archetype(
            short="conflict.original.battle_for_carthag",
            kind="conflict",
            title="Battle for Carthag",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.battle_for_carthag",
                    "ConflictLevel": 3,
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.carthag",),
                    "SetList": ("original",),
                    "Tags": ("Control",),
                    "VictoryPoints": 2,
                    "AbilityIDs": (
                        "ability.conflict.original.battle_for_carthag_first",
                        "ability.conflict.original.battle_for_carthag_second",
                        "ability.conflict.original.battle_for_carthag_third",
                    ),
                }
            ),
        ),
        "conflict.original.battle_for_imperial_basin": Archetype(
            short="conflict.original.battle_for_imperial_basin",
            kind="conflict",
            title="Battle for Imperial Basin",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.battle_for_imperial_basin",
                    "ConflictLevel": 3,
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.imperial_basin",),
                    "SetList": ("original",),
                    "Tags": ("Control",),
                    "VictoryPoints": 2,
                    "AbilityIDs": (
                        "ability.conflict.original.battle_for_imperial_basin_first",
                        "ability.conflict.original.battle_for_imperial_basin_second",
                        "ability.conflict.original.battle_for_imperial_basin_third",
                    ),
                }
            ),
        ),
        "conflict.original.cloakand_dagger": Archetype(
            short="conflict.original.cloakand_dagger",
            kind="conflict",
            title="Cloak and Dagger",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.cloakand_dagger",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.conflict.original.cloak_and_dagger_first",
                        "ability.conflict.original.cloak_and_dagger_second",
                        "ability.conflict.original.cloak_and_dagger_third",
                    ),
                }
            ),
        ),
        "conflict.original.desert_power": Archetype(
            short="conflict.original.desert_power",
            kind="conflict",
            title="Desert Power",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.desert_power",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "VictoryPoints": 1,
                    "AbilityIDs": (
                        "ability.conflict.original.desert_power_first",
                        "ability.conflict.original.desert_power_second",
                        "ability.conflict.original.desert_power_third",
                    ),
                }
            ),
        ),
        "conflict.original.grand_vision": Archetype(
            short="conflict.original.grand_vision",
            kind="conflict",
            title="Grand Vision",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.grand_vision",
                    "ConflictLevel": 3,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.conflict.original.grand_vision_first",
                        "ability.conflict.original.grand_vision_second",
                        "ability.conflict.original.grand_vision_third",
                    ),
                }
            ),
        ),
        "conflict.original.guild_bank_raid": Archetype(
            short="conflict.original.guild_bank_raid",
            kind="conflict",
            title="Guild Bank Raid",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.guild_bank_raid",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.conflict.original.guild_bank_raid_first",
                        "ability.conflict.original.guild_bank_raid_second",
                        "ability.conflict.original.guild_bank_raid_third",
                    ),
                }
            ),
        ),
        "conflict.original.machinations": Archetype(
            short="conflict.original.machinations",
            kind="conflict",
            title="Machinations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.machinations",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.conflict.original.machinations_first",
                        "ability.conflict.original.machinations_second",
                        "ability.conflict.original.machinations_third",
                    ),
                }
            ),
        ),
        "conflict.original.raid_stockpiles": Archetype(
            short="conflict.original.raid_stockpiles",
            kind="conflict",
            title="Raid Stockpiles",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.raid_stockpiles",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.conflict.original.raid_stockpiles_first",
                        "ability.conflict.original.raid_stockpiles_second",
                        "ability.conflict.original.raid_stockpiles_third",
                    ),
                }
            ),
        ),
        "conflict.original.secure_imperial_basin": Archetype(
            short="conflict.original.secure_imperial_basin",
            kind="conflict",
            title="Secure Imperial Basin",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.secure_imperial_basin",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.imperial_basin",),
                    "SetList": ("original",),
                    "Tags": ("Control",),
                    "VictoryPoints": 1,
                    "AbilityIDs": (
                        "ability.conflict.original.secure_imperial_basin_first",
                        "ability.conflict.original.secure_imperial_basin_second",
                        "ability.conflict.original.secure_imperial_basin_third",
                    ),
                }
            ),
        ),
        "conflict.original.siege_of_arrakeen": Archetype(
            short="conflict.original.siege_of_arrakeen",
            kind="conflict",
            title="Siege of Arrakeen",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.siege_of_arrakeen",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.arrakeen",),
                    "SetList": ("original",),
                    "Tags": ("Control",),
                    "VictoryPoints": 1,
                    "AbilityIDs": (
                        "ability.conflict.original.siege_of_arrakeen_first",
                        "ability.conflict.original.siege_of_arrakeen_second",
                        "ability.conflict.original.siege_of_arrakeen_third",
                    ),
                }
            ),
        ),
        "conflict.original.siege_of_carthag": Archetype(
            short="conflict.original.siege_of_carthag",
            kind="conflict",
            title="Siege of Carthag",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.siege_of_carthag",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.carthag",),
                    "SetList": ("original",),
                    "Tags": ("Control",),
                    "VictoryPoints": 1,
                    "AbilityIDs": (
                        "ability.conflict.original.siege_of_carthag_first",
                        "ability.conflict.original.siege_of_carthag_second",
                        "ability.conflict.original.siege_of_carthag_third",
                    ),
                }
            ),
        ),
        "conflict.original.skirmish_a": Archetype(
            short="conflict.original.skirmish_a",
            kind="conflict",
            title="Skirmish",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.skirmish_a",
                    "ConflictLevel": 1,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "VictoryPoints": 1,
                    "AbilityIDs": (
                        "ability.conflict.original.skirmish_a_first",
                        "ability.conflict.original.skirmish_a_second",
                        "ability.conflict.original.skirmish_a_third",
                    ),
                }
            ),
        ),
        "conflict.original.skirmish_b": Archetype(
            short="conflict.original.skirmish_b",
            kind="conflict",
            title="Skirmish",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.skirmish_b",
                    "ConflictLevel": 1,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "VictoryPoints": 1,
                    "AbilityIDs": (
                        "ability.conflict.original.skirmish_b_first",
                        "ability.conflict.original.skirmish_b_second",
                        "ability.conflict.original.skirmish_b_third",
                    ),
                }
            ),
        ),
        "conflict.original.skirmish_c": Archetype(
            short="conflict.original.skirmish_c",
            kind="conflict",
            title="Skirmish",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.skirmish_c",
                    "ConflictLevel": 1,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.conflict.original.skirmish_c_first",
                        "ability.conflict.original.skirmish_c_second",
                        "ability.conflict.original.skirmish_c_third",
                    ),
                }
            ),
        ),
        "conflict.original.skirmish_d": Archetype(
            short="conflict.original.skirmish_d",
            kind="conflict",
            title="Skirmish",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.skirmish_d",
                    "ConflictLevel": 1,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.conflict.original.skirmish_d_first",
                        "ability.conflict.original.skirmish_d_second",
                        "ability.conflict.original.skirmish_d_third",
                    ),
                }
            ),
        ),
        "conflict.original.sort_through_the_chaos": Archetype(
            short="conflict.original.sort_through_the_chaos",
            kind="conflict",
            title="Sort Through the Chaos",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.sort_through_the_chaos",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.conflict.original.sort_through_the_chaos_first",
                        "ability.conflict.original.sort_through_the_chaos_second",
                        "ability.conflict.original.sort_through_the_chaos_third",
                    ),
                }
            ),
        ),
        "conflict.original.terrible_purpose": Archetype(
            short="conflict.original.terrible_purpose",
            kind="conflict",
            title="Terrible Purpose",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.original.terrible_purpose",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "SetList": ("original",),
                    "VictoryPoints": 1,
                    "AbilityIDs": (
                        "ability.conflict.original.terrible_purpose_first",
                        "ability.conflict.original.terrible_purpose_second",
                        "ability.conflict.original.terrible_purpose_third",
                    ),
                }
            ),
        ),
        "conflict.ix.economic_supremacy": Archetype(
            short="conflict.ix.economic_supremacy",
            kind="conflict",
            title="Economic Supremacy",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.ix.economic_supremacy",
                    "ConflictLevel": 3,
                    "EntityType": "Conflict",
                    "SetList": ("ix",),
                    "VictoryPoints": 4,
                    "AbilityIDs": (
                        "ability.conflict.ix.economic_supremacy_first",
                        "ability.conflict.ix.economic_supremacy_second",
                        "ability.conflict.ix.economic_supremacy_third",
                        "ability.conflict.ix.economic_supremacy_solari",
                        "ability.conflict.ix.economic_supremacy_spice",
                    ),
                }
            ),
        ),
        "conflict.ix.skirmish_e": Archetype(
            short="conflict.ix.skirmish_e",
            kind="conflict",
            title="Skirmish",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.ix.skirmish_e",
                    "ConflictLevel": 1,
                    "EntityType": "Conflict",
                    "SetList": ("ix",),
                    "Tags": ("Freighter",),
                    "AbilityIDs": (
                        "ability.conflict.ix.skirmish_e_first",
                        "ability.conflict.ix.skirmish_e_second",
                        "ability.conflict.ix.skirmish_e_third",
                    ),
                }
            ),
        ),
        "conflict.ix.skirmish_f": Archetype(
            short="conflict.ix.skirmish_f",
            kind="conflict",
            title="Skirmish",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.ix.skirmish_f",
                    "ConflictLevel": 1,
                    "EntityType": "Conflict",
                    "SetList": ("ix",),
                    "Tags": ("Freighter",),
                    "AbilityIDs": (
                        "ability.conflict.ix.skirmish_f_first",
                        "ability.conflict.ix.skirmish_f_second",
                        "ability.conflict.ix.skirmish_f_third",
                    ),
                }
            ),
        ),
        "conflict.ix.trade_monopoly": Archetype(
            short="conflict.ix.trade_monopoly",
            kind="conflict",
            title="Trade Monopoly",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.ix.trade_monopoly",
                    "ConflictLevel": 2,
                    "EntityType": "Conflict",
                    "SetList": ("ix",),
                    "Tags": ("Freighter",),
                    "AbilityIDs": (
                        "ability.conflict.ix.trade_monopoly_first",
                        "ability.conflict.ix.trade_monopoly_second",
                        "ability.conflict.original.trade_monopoly_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.battle_for_arrakeen_up": Archetype(
            short="conflict.uprising.battle_for_arrakeen_up",
            kind="conflict",
            title="Battle for Arrakeen",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_arrakeen_up",
                    "BattleIcon": "Crysknife",
                    "ConflictLevel": 3,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.battle_for_arrakeen_up_first",
                        "conflict.uprising.battle_for_arrakeen_up_second",
                        "conflict.uprising.battle_for_arrakeen_up_third",
                    ),
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.arrakeen",),
                    "SetList": ("uprising",),
                    "Tags": ("Control", "BattleIcon", "RecallSpy", "ShieldWall"),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                        "ability.activated.uprising.recall2_spies_vp",
                    ),
                }
            ),
        ),
        "conflict.uprising.battle_for_arrakeen_up_first": Archetype(
            short="conflict.uprising.battle_for_arrakeen_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_arrakeen_up_first",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.take_control_conflict",
                        "ability.activated.uprising.recall2_spies_vp",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "VictoryPoints": 1,
                }
            ),
        ),
        "conflict.uprising.battle_for_arrakeen_up_second": Archetype(
            short="conflict.uprising.battle_for_arrakeen_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_arrakeen_up_second",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Solari": 3,
                    "Spice": 1,
                }
            ),
        ),
        "conflict.uprising.battle_for_arrakeen_up_third": Archetype(
            short="conflict.uprising.battle_for_arrakeen_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_arrakeen_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "Spice": 2,
                }
            ),
        ),
        "conflict.uprising.battle_for_imperial_basin_up": Archetype(
            short="conflict.uprising.battle_for_imperial_basin_up",
            kind="conflict",
            title="Battle for Imperial Basin",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_imperial_basin_up",
                    "BattleIcon": "Ornithopter",
                    "ConflictLevel": 3,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.battle_for_imperial_basin_up_first",
                        "conflict.uprising.battle_for_imperial_basin_up_second",
                        "conflict.uprising.battle_for_imperial_basin_up_third",
                    ),
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.imperial_basin",),
                    "SetList": ("uprising",),
                    "Tags": ("Control", "BattleIcon", "ShieldWall"),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                        "ability.conflict.uprising.pay4_spice_to_gain1_vp",
                    ),
                }
            ),
        ),
        "conflict.uprising.battle_for_imperial_basin_up_first": Archetype(
            short="conflict.uprising.battle_for_imperial_basin_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_imperial_basin_up_first",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.take_control_conflict",
                        "ability.conflict.uprising.pay4_spice_to_gain1_vp",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "VictoryPoints": 1,
                }
            ),
        ),
        "conflict.uprising.battle_for_imperial_basin_up_second": Archetype(
            short="conflict.uprising.battle_for_imperial_basin_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_imperial_basin_up_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 5,
                }
            ),
        ),
        "conflict.uprising.battle_for_imperial_basin_up_third": Archetype(
            short="conflict.uprising.battle_for_imperial_basin_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_imperial_basin_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 3,
                }
            ),
        ),
        "conflict.uprising.battle_for_spice_refinery_up": Archetype(
            short="conflict.uprising.battle_for_spice_refinery_up",
            kind="conflict",
            title="Battle for Spice Refinery",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_spice_refinery_up",
                    "BattleIcon": "DesertMouse",
                    "ConflictLevel": 3,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.battle_for_spice_refinery_up_first",
                        "conflict.uprising.battle_for_spice_refinery_up_second",
                        "conflict.uprising.battle_for_spice_refinery_up_third",
                    ),
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.uprising.spice_refinery",),
                    "SetList": ("uprising",),
                    "Tags": ("Control", "BattleIcon", "ShieldWall"),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                        "ability.conflict.uprising.pay6_solari_to_gain1_vp",
                    ),
                }
            ),
        ),
        "conflict.uprising.battle_for_spice_refinery_up_first": Archetype(
            short="conflict.uprising.battle_for_spice_refinery_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_spice_refinery_up_first",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.take_control_conflict",
                        "ability.conflict.uprising.pay6_solari_to_gain1_vp",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "VictoryPoints": 1,
                }
            ),
        ),
        "conflict.uprising.battle_for_spice_refinery_up_second": Archetype(
            short="conflict.uprising.battle_for_spice_refinery_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_spice_refinery_up_second",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Spice": 3,
                }
            ),
        ),
        "conflict.uprising.battle_for_spice_refinery_up_third": Archetype(
            short="conflict.uprising.battle_for_spice_refinery_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.battle_for_spice_refinery_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 3,
                }
            ),
        ),
        "conflict.uprising.choam_security_choam": Archetype(
            short="conflict.uprising.choam_security_choam",
            kind="conflict",
            title="CHOAM Security",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.choam_security_choam",
                    "BattleIcon": "Crysknife",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.choam_security_choam_first",
                        "conflict.uprising.choam_security_choam_second",
                        "conflict.uprising.choam_security_choam_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("choam_module",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.choam_security_choam_first": Archetype(
            short="conflict.uprising.choam_security_choam_first",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.choam_security_choam_first",
                    "CustomAbilityIDs": (
                        "ability.activated.uprising.gain_contract_custom",
                    ),
                    "EntityType": "ConflictReward",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "SetList": ("uprising",),
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.choam_security_choam_second": Archetype(
            short="conflict.uprising.choam_security_choam_second",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.choam_security_choam_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "Troops": 2,
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.choam_security_choam_third": Archetype(
            short="conflict.uprising.choam_security_choam_third",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.choam_security_choam_third",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.choam_security_up": Archetype(
            short="conflict.uprising.choam_security_up",
            kind="conflict",
            title="CHOAM Security",
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.choam_security_up",
                    "BattleIcon": "Crysknife",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.choam_security_up_first",
                        "conflict.uprising.choam_security_up_second",
                        "conflict.uprising.choam_security_up_third",
                    ),
                    "EntityType": "Conflict",
                    "RemovedFromSetList": ("choam_module",),
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.choam_security_up_first": Archetype(
            short="conflict.uprising.choam_security_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.choam_security_up_first",
                    "EntityType": "ConflictReward",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.choam_security_up_second": Archetype(
            short="conflict.uprising.choam_security_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.choam_security_up_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "Troops": 2,
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.choam_security_up_third": Archetype(
            short="conflict.uprising.choam_security_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.choam_security_up_third",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.propaganda_up": Archetype(
            short="conflict.uprising.propaganda_up",
            kind="conflict",
            title="Propaganda",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.propaganda_up",
                    "BattleIcon": "Wildcard",
                    "ConflictLevel": 3,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.propaganda_up_first",
                        "conflict.uprising.propaganda_up_second",
                        "conflict.uprising.propaganda_up_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.propaganda_up_first": Archetype(
            short="conflict.uprising.propaganda_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.propaganda_up_first",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.gain_any_two_influence_conflict",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                }
            ),
        ),
        "conflict.uprising.propaganda_up_second": Archetype(
            short="conflict.uprising.propaganda_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.propaganda_up_second",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Spice": 3,
                }
            ),
        ),
        "conflict.uprising.propaganda_up_third": Archetype(
            short="conflict.uprising.propaganda_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.propaganda_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 3,
                }
            ),
        ),
        "conflict.uprising.protect_the_sietches_up": Archetype(
            short="conflict.uprising.protect_the_sietches_up",
            kind="conflict",
            title="Protect the Sietches",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.protect_the_sietches_up",
                    "BattleIcon": "DesertMouse",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.protect_the_sietches_up_first",
                        "conflict.uprising.protect_the_sietches_up_second",
                        "conflict.uprising.protect_the_sietches_up_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.protect_the_sietches_up_first": Archetype(
            short="conflict.uprising.protect_the_sietches_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.protect_the_sietches_up_first",
                    "EntityType": "ConflictReward",
                    "FactionInfluence": {"Fremen": 1},
                    "SetList": ("uprising",),
                    "Troops": 1,
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.protect_the_sietches_up_second": Archetype(
            short="conflict.uprising.protect_the_sietches_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.protect_the_sietches_up_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 3,
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.protect_the_sietches_up_third": Archetype(
            short="conflict.uprising.protect_the_sietches_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.protect_the_sietches_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 2,
                }
            ),
        ),
        "conflict.uprising.secure_imperial_basin_up": Archetype(
            short="conflict.uprising.secure_imperial_basin_up",
            kind="conflict",
            title="Secure Imperial Basin",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.secure_imperial_basin_up",
                    "BattleIcon": "DesertMouse",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.secure_imperial_basin_up_first",
                        "conflict.uprising.secure_imperial_basin_up_second",
                        "conflict.uprising.secure_imperial_basin_up_third",
                    ),
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.imperial_basin",),
                    "SetList": ("uprising",),
                    "Tags": ("Control", "BattleIcon", "ShieldWall"),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.secure_imperial_basin_up_first": Archetype(
            short="conflict.uprising.secure_imperial_basin_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.secure_imperial_basin_up_first",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.take_control_conflict",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 2,
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.secure_imperial_basin_up_second": Archetype(
            short="conflict.uprising.secure_imperial_basin_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.secure_imperial_basin_up_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Troops": 1,
                    "Water": 2,
                }
            ),
        ),
        "conflict.uprising.secure_imperial_basin_up_third": Archetype(
            short="conflict.uprising.secure_imperial_basin_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.secure_imperial_basin_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Troops": 1,
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.seize_spice_refinery_up": Archetype(
            short="conflict.uprising.seize_spice_refinery_up",
            kind="conflict",
            title="Seize Spice Refinery",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.seize_spice_refinery_up",
                    "BattleIcon": "Crysknife",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.seize_spice_refinery_up_first",
                        "conflict.uprising.seize_spice_refinery_up_second",
                        "conflict.uprising.seize_spice_refinery_up_third",
                    ),
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.uprising.spice_refinery",),
                    "SetList": ("uprising",),
                    "Tags": ("Control", "BattleIcon", "Spy", "ShieldWall"),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.seize_spice_refinery_up_first": Archetype(
            short="conflict.uprising.seize_spice_refinery_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.seize_spice_refinery_up_first",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.take_control_conflict",
                        "ability.activated.uprising.place_spy_custom",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 2,
                }
            ),
        ),
        "conflict.uprising.seize_spice_refinery_up_second": Archetype(
            short="conflict.uprising.seize_spice_refinery_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.seize_spice_refinery_up_second",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Spice": 1,
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.seize_spice_refinery_up_third": Archetype(
            short="conflict.uprising.seize_spice_refinery_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.seize_spice_refinery_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 2,
                }
            ),
        ),
        "conflict.uprising.shadow_contest_up": Archetype(
            short="conflict.uprising.shadow_contest_up",
            kind="conflict",
            title="Shadow Contest",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.shadow_contest_up",
                    "BattleIcon": "Ornithopter",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.shadow_contest_up_first",
                        "conflict.uprising.shadow_contest_up_second",
                        "conflict.uprising.shadow_contest_up_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.shadow_contest_up_first": Archetype(
            short="conflict.uprising.shadow_contest_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.shadow_contest_up_first",
                    "EntityType": "ConflictReward",
                    "FactionInfluence": {"BeneGesserit": 1},
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                }
            ),
        ),
        "conflict.uprising.shadow_contest_up_second": Archetype(
            short="conflict.uprising.shadow_contest_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.shadow_contest_up_second",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Spice": 1,
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.shadow_contest_up_third": Archetype(
            short="conflict.uprising.shadow_contest_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.shadow_contest_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 1,
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.siege_of_arrakeen_up": Archetype(
            short="conflict.uprising.siege_of_arrakeen_up",
            kind="conflict",
            title="Siege of Arrakeen",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.siege_of_arrakeen_up",
                    "BattleIcon": "Ornithopter",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.siege_of_arrakeen_up_first",
                        "conflict.uprising.siege_of_arrakeen_up_second",
                        "conflict.uprising.siege_of_arrakeen_up_third",
                    ),
                    "EntityType": "Conflict",
                    "ReferencedArchetypeIDs": ("space.original.arrakeen",),
                    "SetList": ("uprising",),
                    "Tags": ("Control", "BattleIcon", "ShieldWall"),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.siege_of_arrakeen_up_first": Archetype(
            short="conflict.uprising.siege_of_arrakeen_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.siege_of_arrakeen_up_first",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.take_control_conflict",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "Troops": 2,
                }
            ),
        ),
        "conflict.uprising.siege_of_arrakeen_up_second": Archetype(
            short="conflict.uprising.siege_of_arrakeen_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.siege_of_arrakeen_up_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 4,
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.siege_of_arrakeen_up_third": Archetype(
            short="conflict.uprising.siege_of_arrakeen_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.siege_of_arrakeen_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 3,
                }
            ),
        ),
        "conflict.uprising.skirmish_g": Archetype(
            short="conflict.uprising.skirmish_g",
            kind="conflict",
            title="Skirmish",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_g",
                    "BattleIcon": "Ornithopter",
                    "ConflictLevel": 1,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.skirmish_g_first",
                        "conflict.uprising.skirmish_g_second",
                        "conflict.uprising.skirmish_g_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.skirmish_g_first": Archetype(
            short="conflict.uprising.skirmish_g_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_g_first",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Solari": 1,
                }
            ),
        ),
        "conflict.uprising.skirmish_g_second": Archetype(
            short="conflict.uprising.skirmish_g_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_g_second",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Solari": 2,
                }
            ),
        ),
        "conflict.uprising.skirmish_g_third": Archetype(
            short="conflict.uprising.skirmish_g_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_g_third",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                }
            ),
        ),
        "conflict.uprising.skirmish_h": Archetype(
            short="conflict.uprising.skirmish_h",
            kind="conflict",
            title="Skirmish",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_h",
                    "BattleIcon": "Crysknife",
                    "ConflictLevel": 1,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.skirmish_h_first",
                        "conflict.uprising.skirmish_h_second",
                        "conflict.uprising.skirmish_h_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.skirmish_h_first": Archetype(
            short="conflict.uprising.skirmish_h_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_h_first",
                    "CustomAbilityIDs": (
                        "ability.activated.gain_any_influence_conflict",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                }
            ),
        ),
        "conflict.uprising.skirmish_h_second": Archetype(
            short="conflict.uprising.skirmish_h_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_h_second",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("uprising",),
                    "Spice": 1,
                }
            ),
        ),
        "conflict.uprising.skirmish_h_third": Archetype(
            short="conflict.uprising.skirmish_h_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_h_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 1,
                }
            ),
        ),
        "conflict.uprising.skirmish_i": Archetype(
            short="conflict.uprising.skirmish_i",
            kind="conflict",
            title="Skirmish",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_i",
                    "BattleIcon": "DesertMouse",
                    "ConflictLevel": 1,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.skirmish_i_first",
                        "conflict.uprising.skirmish_i_second",
                        "conflict.uprising.skirmish_i_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.skirmish_i_first": Archetype(
            short="conflict.uprising.skirmish_i_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_i_first",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 2,
                }
            ),
        ),
        "conflict.uprising.skirmish_i_second": Archetype(
            short="conflict.uprising.skirmish_i_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_i_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 3,
                }
            ),
        ),
        "conflict.uprising.skirmish_i_third": Archetype(
            short="conflict.uprising.skirmish_i_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.skirmish_i_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 2,
                }
            ),
        ),
        "conflict.uprising.spice_freighters_up": Archetype(
            short="conflict.uprising.spice_freighters_up",
            kind="conflict",
            title="Spice Freighters",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.spice_freighters_up",
                    "BattleIcon": "Crysknife",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.spice_freighters_up_first",
                        "conflict.uprising.spice_freighters_up_second",
                        "conflict.uprising.spice_freighters_up_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                        "ability.conflict.uprising.pay3_spice_to_gain1_vp",
                    ),
                }
            ),
        ),
        "conflict.uprising.spice_freighters_up_first": Archetype(
            short="conflict.uprising.spice_freighters_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.spice_freighters_up_first",
                    "CustomAbilityIDs": (
                        "ability.activated.gain_any_influence_conflict",
                        "ability.conflict.uprising.pay3_spice_to_gain1_vp",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                }
            ),
        ),
        "conflict.uprising.spice_freighters_up_second": Archetype(
            short="conflict.uprising.spice_freighters_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.spice_freighters_up_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 1,
                    "Troops": 1,
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.spice_freighters_up_third": Archetype(
            short="conflict.uprising.spice_freighters_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.spice_freighters_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 1,
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.test_of_loyalty_up": Archetype(
            short="conflict.uprising.test_of_loyalty_up",
            kind="conflict",
            title="Test of Loyalty",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.test_of_loyalty_up",
                    "BattleIcon": "Ornithopter",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.test_of_loyalty_up_first",
                        "conflict.uprising.test_of_loyalty_up_second",
                        "conflict.uprising.test_of_loyalty_up_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon", "Spy"),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.test_of_loyalty_up_first": Archetype(
            short="conflict.uprising.test_of_loyalty_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.test_of_loyalty_up_first",
                    "CustomAbilityIDs": (
                        "ability.activated.uprising.place_spy_custom",
                    ),
                    "EntityType": "ConflictReward",
                    "FactionInfluence": {"Emperor": 1},
                    "SetList": ("uprising",),
                    "Solari": 2,
                }
            ),
        ),
        "conflict.uprising.test_of_loyalty_up_second": Archetype(
            short="conflict.uprising.test_of_loyalty_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.test_of_loyalty_up_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 4,
                    "Troops": 1,
                }
            ),
        ),
        "conflict.uprising.test_of_loyalty_up_third": Archetype(
            short="conflict.uprising.test_of_loyalty_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.test_of_loyalty_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 3,
                }
            ),
        ),
        "conflict.uprising.trade_dispute_choam": Archetype(
            short="conflict.uprising.trade_dispute_choam",
            kind="conflict",
            title="Trade Dispute",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.trade_dispute_choam",
                    "BattleIcon": "DesertMouse",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.trade_dispute_choam_first",
                        "conflict.uprising.trade_dispute_choam_second",
                        "conflict.uprising.trade_dispute_choam_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("choam_module",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.trade_dispute_choam_first": Archetype(
            short="conflict.uprising.trade_dispute_choam_first",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.trade_dispute_choam_first",
                    "CustomAbilityIDs": (
                        "ability.activated.uprising.gain_contract_custom",
                        "ability.conflict.uprising.trash_conflict_custom",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.trade_dispute_choam_second": Archetype(
            short="conflict.uprising.trade_dispute_choam_second",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.trade_dispute_choam_second",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.trash_conflict_custom",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 1,
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.trade_dispute_choam_third": Archetype(
            short="conflict.uprising.trade_dispute_choam_third",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.trade_dispute_choam_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Troops": 1,
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.trade_dispute_up": Archetype(
            short="conflict.uprising.trade_dispute_up",
            kind="conflict",
            title="Trade Dispute",
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.trade_dispute_up",
                    "BattleIcon": "DesertMouse",
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.uprising.trade_dispute_up_first",
                        "conflict.uprising.trade_dispute_up_second",
                        "conflict.uprising.trade_dispute_up_third",
                    ),
                    "EntityType": "Conflict",
                    "RemovedFromSetList": ("choam_module",),
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.uprising.trade_dispute_up_first": Archetype(
            short="conflict.uprising.trade_dispute_up_first",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.trade_dispute_up_first",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.trash_conflict_custom",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.trade_dispute_up_second": Archetype(
            short="conflict.uprising.trade_dispute_up_second",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.trade_dispute_up_second",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.trash_conflict_custom",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Spice": 1,
                    "Water": 1,
                }
            ),
        ),
        "conflict.uprising.trade_dispute_up_third": Archetype(
            short="conflict.uprising.trade_dispute_up_third",
            kind="conflict_reward",
            title=None,
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.uprising.trade_dispute_up_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("uprising",),
                    "Troops": 1,
                    "Water": 1,
                }
            ),
        ),
        "contract.uprising.contract_base_1": Archetype(
            short="contract.uprising.contract_base_1",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_1",
                    "CardCount": 2,
                    "ContractType": "Harvest",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": (
                        "space.original.imperial_basin",
                        "space.uprising.hagga_basin_up",
                        "space.uprising.deep_desert",
                    ),
                    "SetList": ("uprising",),
                    "Solari": 3,
                    "SpiceCost": 3,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.harvest3_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_10": Archetype(
            short="contract.uprising.contract_base_10",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_10",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.high_council_up",),
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.bene_gesserit_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_11": Archetype(
            short="contract.uprising.contract_base_11",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_11",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.high_council_up",),
                    "SetList": ("uprising",),
                    "Solari": 3,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_12": Archetype(
            short="contract.uprising.contract_base_12",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_12",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "DeferValue": 2,
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.sardaukar",),
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.draw2_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_13": Archetype(
            short="contract.uprising.contract_base_13",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_13",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.sardaukar",),
                    "SetList": ("uprising",),
                    "Tags": ("RecallAgent",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.recall_agent_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_14": Archetype(
            short="contract.uprising.contract_base_14",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_14",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.deliver_supplies",),
                    "SetList": ("uprising",),
                    "Solari": 3,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_15": Archetype(
            short="contract.uprising.contract_base_15",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_15",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.heighliner_up",),
                    "SetList": ("uprising",),
                    "Troops": 2,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_16": Archetype(
            short="contract.uprising.contract_base_16",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_16",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.heighliner_up",),
                    "SetList": ("uprising",),
                    "Water": 2,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_17": Archetype(
            short="contract.uprising.contract_base_17",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_17",
                    "CardCount": 2,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.espionage",),
                    "SetList": ("uprising",),
                    "Solari": 3,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_19": Archetype(
            short="contract.uprising.contract_base_19",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_19",
                    "CardCount": 1,
                    "ContractType": "Immediate",
                    "EntityType": "Contract",
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "AbilityIDs": ("ability.activated.uprising.contract.contract",),
                }
            ),
        ),
        "contract.uprising.contract_base_20": Archetype(
            short="contract.uprising.contract_base_20",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_20",
                    "CardCount": 1,
                    "ContractType": "Acquire",
                    "EntityType": "Contract",
                    "SetList": ("uprising",),
                    "Solari": 3,
                    "Tags": ("WantTSMF",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.tsmf_contract",
                        "ability.triggered.uprising.activate_tsmf_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_3": Archetype(
            short="contract.uprising.contract_base_3",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_3",
                    "CardCount": 1,
                    "ContractType": "Harvest",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": (
                        "space.original.imperial_basin",
                        "space.uprising.hagga_basin_up",
                        "space.uprising.deep_desert",
                    ),
                    "SetList": ("uprising",),
                    "Solari": 4,
                    "SpiceCost": 4,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.harvest4_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_4": Archetype(
            short="contract.uprising.contract_base_4",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_4",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.original.arrakeen",),
                    "SetList": ("uprising",),
                    "Tags": ("Spy",),
                    "Troops": 1,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.place_spy_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_5": Archetype(
            short="contract.uprising.contract_base_5",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_5",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.original.arrakeen",),
                    "SetList": ("uprising",),
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_6": Archetype(
            short="contract.uprising.contract_base_6",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_6",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "DeferValue": 2,
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.spice_refinery",),
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.draw2_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_7": Archetype(
            short="contract.uprising.contract_base_7",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_7",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.spice_refinery",),
                    "SetList": ("uprising",),
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_8": Archetype(
            short="contract.uprising.contract_base_8",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_8",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": (
                        "space.original.research_station",
                        "space.immortality.research_station_immortality",
                        "space.uprising.research_station_up",
                    ),
                    "SetList": ("uprising",),
                    "Solari": 3,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_base_9": Archetype(
            short="contract.uprising.contract_base_9",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_base_9",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": (
                        "space.original.research_station",
                        "space.immortality.research_station_immortality",
                        "space.uprising.research_station_up",
                    ),
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "Tags": ("Spy",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.place_spy_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_1": Archetype(
            short="contract.uprising.contract_ro_i_1",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_1",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.ix.smuggling",),
                    "SetList": ("uprising", "ix"),
                    "Tags": ("Contract",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_10": Archetype(
            short="contract.uprising.contract_ro_i_10",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_10",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.espionage",),
                    "SetList": ("uprising", "ix"),
                    "Solari": 1,
                    "Tags": ("Contract",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_2": Archetype(
            short="contract.uprising.contract_ro_i_2",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_2",
                    "CardCount": 1,
                    "ContractType": "Harvest",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": (
                        "space.original.imperial_basin",
                        "space.uprising.hagga_basin_up",
                        "space.uprising.deep_desert",
                    ),
                    "SetList": ("uprising", "ix"),
                    "SpiceCost": 3,
                    "Tags": ("Contract",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_harvest3_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_3": Archetype(
            short="contract.uprising.contract_ro_i_3",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_3",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.ix.interstellar_shipping",),
                    "SetList": ("uprising", "ix"),
                    "Tags": ("Contract",),
                    "TechNegotiator": 1,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_4": Archetype(
            short="contract.uprising.contract_ro_i_4",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_4",
                    "CardCount": 1,
                    "ContractType": "Harvest",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": (
                        "space.original.imperial_basin",
                        "space.uprising.hagga_basin_up",
                        "space.uprising.deep_desert",
                    ),
                    "SetList": ("uprising", "ix"),
                    "Solari": 2,
                    "SpiceCost": 4,
                    "Tags": ("Contract",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_harvest4_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_5": Archetype(
            short="contract.uprising.contract_ro_i_5",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_5",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.ix.tech_negotiation",),
                    "SetList": ("uprising", "ix"),
                    "Tags": ("Contract",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_6": Archetype(
            short="contract.uprising.contract_ro_i_6",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_6",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.ix.dreadnought_space",),
                    "SetList": ("uprising", "ix"),
                    "Tags": ("Contract",),
                    "TechNegotiator": 1,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_7": Archetype(
            short="contract.uprising.contract_ro_i_7",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_7",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.high_council_up",),
                    "SetList": ("uprising", "ix"),
                    "Tags": ("Contract",),
                    "TechNegotiator": 1,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_8": Archetype(
            short="contract.uprising.contract_ro_i_8",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_8",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.heighliner_up",),
                    "SetList": ("uprising", "ix"),
                    "Solari": 3,
                    "Tags": ("Contract",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.uprising.contract_ro_i_9": Archetype(
            short="contract.uprising.contract_ro_i_9",
            kind="contract",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.uprising.contract_ro_i_9",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.original.secrets",),
                    "SetList": ("uprising", "ix"),
                    "Tags": ("Contract",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.roi_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "imperium.original.arrakis_liaison": Archetype(
            short="imperium.original.arrakis_liaison",
            kind="reserve",
            title="Arrakis Liaison",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.original.arrakis_liaison",
                    "CardCount": 8,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Pentagon", "Circle"),
                    "ImperiumType": "Reserve",
                    "LateMod": 0.8,
                    "Persuasion": 2,
                    "PersuasionCost": 2,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.original.arrakis_recruiter": Archetype(
            short="imperium.original.arrakis_recruiter",
            kind="imperium",
            title="Arrakis Recruiter",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.2,
                    "AgentTroops": 1,
                    "ArchID": "imperium.original.arrakis_recruiter",
                    "CardCount": 2,
                    "EarlyMod": 1.2,
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("original",),
                    "Strength": 1,
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.original.assassination_mission": Archetype(
            short="imperium.original.assassination_mission",
            kind="imperium",
            title="Assassination Mission",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.1,
                    "ArchID": "imperium.original.assassination_mission",
                    "CardCount": 2,
                    "EarlyMod": 1.2,
                    "EntityType": "Imperium",
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "PersuasionCost": 1,
                    "SetList": ("original",),
                    "Solari": 1,
                    "Strength": 1,
                    "TrashValue": 1.5,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.triggered.original.assassination_mission",
                    ),
                }
            ),
        ),
        "imperium.original.bene_gesserit_initiate": Archetype(
            short="imperium.original.bene_gesserit_initiate",
            kind="imperium",
            title="Bene Gesserit Initiate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.original.bene_gesserit_initiate",
                    "CardCount": 2,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "imperium.original.bene_gesserit_sister": Archetype(
            short="imperium.original.bene_gesserit_sister",
            kind="imperium",
            title="Bene Gesserit Sister",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.original.bene_gesserit_sister",
                    "CardCount": 3,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit", "Pentagon"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "Tags": ("ConditionalStrength",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.original.bene_gesserit_sister_reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.bene_gesserit_sister",
                    ),
                }
            ),
        ),
        "imperium.original.choam_directorship": Archetype(
            short="imperium.original.choam_directorship",
            kind="imperium",
            title="CHOAM Directorship",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("RankE", "RankSG", "RankBG", "RankF"),
                    "AcquireValue": 2.0,
                    "ArchID": "imperium.original.choam_directorship",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "ImperiumType": "Main",
                    "LateMod": 1.33,
                    "PersuasionCost": 8,
                    "SetList": ("original",),
                    "Solari": 3,
                    "TrashValue": 0.5,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.original.choam_directorship_acquire",
                    ),
                }
            ),
        ),
        "imperium.original.carryall": Archetype(
            short="imperium.original.carryall",
            kind="imperium",
            title="Carryall",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.4,
                    "ArchID": "imperium.original.carryall",
                    "CardCount": 1,
                    "EarlyMod": 1.33,
                    "EntityType": "Imperium",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.33,
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("original",),
                    "Spice": 1,
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.original.carry_all_agent",
                    ),
                }
            ),
        ),
        "imperium.original.chani": Archetype(
            short="imperium.original.chani",
            kind="imperium",
            title="Chani",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Water",),
                    "AcquireValue": 2.9,
                    "ArchID": "imperium.original.chani",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 5,
                    "SetList": ("original",),
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.activated.original.chani_reveal",
                        "ability.play.reveal",
                    ),
                }
            ),
        ),
        "imperium.original.convincing_argument": Archetype(
            short="imperium.original.convincing_argument",
            kind="starter",
            title="Convincing Argument",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 0.0,
                    "ArchID": "imperium.original.convincing_argument",
                    "EntityType": "Imperium",
                    "ImperiumType": "Starter",
                    "Persuasion": 2,
                    "SetList": ("original",),
                    "TrashValue": 0.25,
                    "AbilityIDs": ("ability.play.agent", "ability.play.reveal"),
                }
            ),
        ),
        "imperium.original.crysknife": Archetype(
            short="imperium.original.crysknife",
            kind="imperium",
            title="Crysknife",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.2,
                    "AgentSolari": 1,
                    "ArchID": "imperium.original.crysknife",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 0.9,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "Strength": 1,
                    "Tags": ("FremenBond",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.crysknife",
                    ),
                }
            ),
        ),
        "imperium.original.dagger": Archetype(
            short="imperium.original.dagger",
            kind="starter",
            title="Dagger",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": -1.0,
                    "ArchID": "imperium.original.dagger",
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Starter",
                    "SetList": ("original",),
                    "Strength": 1,
                    "TrashValue": 1.0,
                    "AbilityIDs": ("ability.play.agent", "ability.play.reveal"),
                }
            ),
        ),
        "imperium.original.diplomacy": Archetype(
            short="imperium.original.diplomacy",
            kind="starter",
            title="Diplomacy",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.0,
                    "ArchID": "imperium.original.diplomacy",
                    "EntityType": "Imperium",
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Starter",
                    "Persuasion": 1,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": ("ability.play.agent", "ability.play.reveal"),
                }
            ),
        ),
        "imperium.original.dr_yueh": Archetype(
            short="imperium.original.dr_yueh",
            kind="imperium",
            title="Dr. Yueh",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.2,
                    "ArchID": "imperium.original.dr_yueh",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.7,
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("original",),
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "imperium.original.duncan_idaho": Archetype(
            short="imperium.original.duncan_idaho",
            kind="imperium",
            title="Duncan Idaho",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.1,
                    "ArchID": "imperium.original.duncan_idaho",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 4,
                    "SetList": ("original",),
                    "Strength": 2,
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.duncan_idaho",
                    ),
                }
            ),
        ),
        "imperium.original.dune_the_desert_planet": Archetype(
            short="imperium.original.dune_the_desert_planet",
            kind="starter",
            title="Dune, the Desert Planet",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": -1.0,
                    "ArchID": "imperium.original.dune_the_desert_planet",
                    "EntityType": "Imperium",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Starter",
                    "Persuasion": 1,
                    "SetList": ("original",),
                    "TrashValue": 1.0,
                    "AbilityIDs": ("ability.play.agent", "ability.play.reveal"),
                }
            ),
        ),
        "imperium.original.fedaykin_death_commando": Archetype(
            short="imperium.original.fedaykin_death_commando",
            kind="imperium",
            title="Fedaykin Death Commando",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.2,
                    "ArchID": "imperium.original.fedaykin_death_commando",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "Tags": ("FremenBond", "ConditionalStrength"),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.original.fedaykin_death_commando_reveal",
                        "ability.activated.acquire",
                        "ability.play.original.fedaykin_death_commando",
                        "ability.activated.trash_agent",
                    ),
                }
            ),
        ),
        "imperium.original.firm_grip": Archetype(
            short="imperium.original.firm_grip",
            kind="imperium",
            title="Firm Grip",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.1,
                    "ArchID": "imperium.original.firm_grip",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "Pentagon"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 4,
                    "SetList": ("original",),
                    "Tags": ("EmperorAlliance",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.play.original.firm_grip_ability2",
                        "ability.activated.original.firm_grip_agent",
                        "ability.play.original.firm_grip_reveal",
                    ),
                }
            ),
        ),
        "imperium.original.foldspace_imperium": Archetype(
            short="imperium.original.foldspace_imperium",
            kind="reserve",
            title="Foldspace",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.original.foldspace_imperium",
                    "CardCount": 6,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "IconList": (
                        "Emperor",
                        "SpacingGuild",
                        "BeneGesserit",
                        "Fremen",
                        "Pentagon",
                        "Circle",
                        "Triangle",
                    ),
                    "ImperiumType": "Reserve",
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.draw",
                        "ability.activated.trash_self",
                    ),
                }
            ),
        ),
        "imperium.original.fremen_camp": Archetype(
            short="imperium.original.fremen_camp",
            kind="imperium",
            title="Fremen Camp",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.0,
                    "ArchID": "imperium.original.fremen_camp",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("original",),
                    "Strength": 1,
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.fremen_camp",
                    ),
                }
            ),
        ),
        "imperium.original.gene_manipulation": Archetype(
            short="imperium.original.gene_manipulation",
            kind="imperium",
            title="Gene Manipulation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.5,
                    "ArchID": "imperium.original.gene_manipulation",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Pentagon", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "Tags": ("WantBG",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.original.gene_manipulation",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.trash_agent",
                    ),
                }
            ),
        ),
        "imperium.original.guild_administrator": Archetype(
            short="imperium.original.guild_administrator",
            kind="imperium",
            title="Guild Administrator",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.1,
                    "ArchID": "imperium.original.guild_administrator",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.trash_agent",
                    ),
                }
            ),
        ),
        "imperium.original.guild_ambassador": Archetype(
            short="imperium.original.guild_ambassador",
            kind="imperium",
            title="Guild Ambassador",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.6,
                    "ArchID": "imperium.original.guild_ambassador",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 4,
                    "SetList": ("original",),
                    "Tags": ("SpacingGuildAlliance",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.guild_ambassador_reveal",
                        "ability.activated.original.guild_ambassador_agent",
                    ),
                }
            ),
        ),
        "imperium.original.guild_bankers": Archetype(
            short="imperium.original.guild_bankers",
            kind="imperium",
            title="Guild Bankers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.original.guild_bankers",
                    "CardCount": 1,
                    "EarlyMod": 0.8,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Emperor", "SpacingGuild", "Pentagon"),
                    "ImperiumType": "Main",
                    "LateMod": 1.33,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.play.original.guild_bankers",
                    ),
                }
            ),
        ),
        "imperium.original.gun_thopter": Archetype(
            short="imperium.original.gun_thopter",
            kind="imperium",
            title="Gun Thopter",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.original.gun_thopter",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 4,
                    "SetList": ("original",),
                    "Strength": 3,
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.activated.acquire",
                        "ability.play.original.gun_thopter_agent",
                        "ability.activated.original.gun_thopter_reveal",
                        "ability.play.reveal",
                    ),
                }
            ),
        ),
        "imperium.original.gurney_halleck": Archetype(
            short="imperium.original.gurney_halleck",
            kind="imperium",
            title="Gurney Halleck",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 6.5,
                    "AgentTroops": 2,
                    "ArchID": "imperium.original.gurney_halleck",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "LateMod": 1.33,
                    "Persuasion": 2,
                    "PersuasionCost": 6,
                    "SetList": ("original",),
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.gurney_halleck",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "imperium.original.imperial_spy": Archetype(
            short="imperium.original.imperial_spy",
            kind="imperium",
            title="Imperial Spy",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.original.imperial_spy",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("original",),
                    "Strength": 1,
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.imperial_spy",
                    ),
                }
            ),
        ),
        "imperium.original.kwisatz_haderach": Archetype(
            short="imperium.original.kwisatz_haderach",
            kind="imperium",
            title="Kwisatz Haderach",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 9.0,
                    "ArchID": "imperium.original.kwisatz_haderach",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 8,
                    "SetList": ("original",),
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.original.kwisatz_haderach",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "imperium.original.lady_jessica": Archetype(
            short="imperium.original.lady_jessica",
            kind="imperium",
            title="Lady Jessica",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("AnyRank",),
                    "AcquireValue": 5.75,
                    "ArchID": "imperium.original.lady_jessica",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit", "Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 1.33,
                    "Persuasion": 3,
                    "PersuasionCost": 7,
                    "SetList": ("original",),
                    "Strength": 1,
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.original.lady_jessica_acquire",
                        "ability.activated.draw",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "imperium.original.liet_kynes": Archetype(
            short="imperium.original.liet_kynes",
            kind="imperium",
            title="Liet Kynes",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("RankE",),
                    "AcquireValue": 2.65,
                    "ArchID": "imperium.original.liet_kynes",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "Fremen"),
                    "IconList": ("Fremen", "Circle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 5,
                    "SetList": ("original",),
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.original.liet_kynes_reveal",
                        "ability.activated.acquire",
                        "ability.play.original.liet_kynes",
                    ),
                }
            ),
        ),
        "imperium.original.missionaria_protectiva": Archetype(
            short="imperium.original.missionaria_protectiva",
            kind="imperium",
            title="Missionaria Protectiva",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 0.3,
                    "ArchID": "imperium.original.missionaria_protectiva",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EarlyMod": 0.8,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("original",),
                    "Tags": ("WantBG",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.missionaria_protectiva",
                    ),
                }
            ),
        ),
        "imperium.original.opulence": Archetype(
            short="imperium.original.opulence",
            kind="imperium",
            title="Opulence",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.9,
                    "AgentSolari": 3,
                    "ArchID": "imperium.original.opulence",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 6,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.opulence",
                    ),
                }
            ),
        ),
        "imperium.original.other_memory": Archetype(
            short="imperium.original.other_memory",
            kind="imperium",
            title="Other Memory",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.9,
                    "ArchID": "imperium.original.other_memory",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 1.1,
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.other_memory",
                    ),
                }
            ),
        ),
        "imperium.original.piter_de_vries": Archetype(
            short="imperium.original.piter_de_vries",
            kind="imperium",
            title="Piter De Vries",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.4,
                    "ArchID": "imperium.original.piter_de_vries",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon", "Circle"),
                    "ImperiumType": "Main",
                    "LateMod": 1.1,
                    "Persuasion": 3,
                    "PersuasionCost": 5,
                    "SetList": ("original",),
                    "Strength": 1,
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.agent_gain_intrigue",
                    ),
                }
            ),
        ),
        "imperium.original.power_play": Archetype(
            short="imperium.original.power_play",
            kind="imperium",
            title="Power Play",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.2,
                    "ArchID": "imperium.original.power_play",
                    "CardCount": 3,
                    "EarlyMod": 0.66,
                    "EntityType": "Imperium",
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Main",
                    "LateMod": 1.33,
                    "PersuasionCost": 5,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.trash_self",
                        "ability.play.original.power_play_agent",
                    ),
                }
            ),
        ),
        "imperium.original.reconnaissance": Archetype(
            short="imperium.original.reconnaissance",
            kind="starter",
            title="Reconnaissance",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": -0.5,
                    "ArchID": "imperium.original.reconnaissance",
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Starter",
                    "Persuasion": 1,
                    "SetList": ("original",),
                    "TrashValue": 0.5,
                    "AbilityIDs": ("ability.play.agent", "ability.play.reveal"),
                }
            ),
        ),
        "imperium.original.reverend_mother_mohiam": Archetype(
            short="imperium.original.reverend_mother_mohiam",
            kind="imperium",
            title="Reverend Mother Mohiam",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.5,
                    "ArchID": "imperium.original.reverend_mother_mohiam",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "BeneGesserit"),
                    "IconList": ("Emperor", "BeneGesserit"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 6,
                    "SetList": ("original",),
                    "Spice": 2,
                    "Tags": ("NamedCharacter", "WantBG"),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.original.reverend_mother_mohiam",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.original.reverend_mother_mohiam_deferred",
                    ),
                }
            ),
        ),
        "imperium.original.sardaukar_infantry": Archetype(
            short="imperium.original.sardaukar_infantry",
            kind="imperium",
            title="Sardaukar Infantry",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.1,
                    "ArchID": "imperium.original.sardaukar_infantry",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("original",),
                    "Strength": 2,
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.original.sardaukar_legion": Archetype(
            short="imperium.original.sardaukar_legion",
            kind="imperium",
            title="Sardaukar Legion",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.4,
                    "AgentTroops": 2,
                    "ArchID": "imperium.original.sardaukar_legion",
                    "CardCount": 2,
                    "EarlyMod": 0.9,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "Pentagon"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.sardaukar_legion",
                        "ability.play.agent",
                    ),
                }
            ),
        ),
        "imperium.original.scout": Archetype(
            short="imperium.original.scout",
            kind="imperium",
            title="Scout",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 0.8,
                    "ArchID": "imperium.original.scout",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("original",),
                    "Strength": 1,
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.activated.original.scout",
                        "ability.play.reveal",
                    ),
                }
            ),
        ),
        "imperium.original.seek_allies": Archetype(
            short="imperium.original.seek_allies",
            kind="starter",
            title="Seek Allies",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.0,
                    "ArchID": "imperium.original.seek_allies",
                    "EntityType": "Imperium",
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Starter",
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.original.seek_allies_agent",
                        "ability.play.reveal",
                        "ability.activated.trash_self",
                    ),
                }
            ),
        ),
        "imperium.original.shifting_allegiances": Archetype(
            short="imperium.original.shifting_allegiances",
            kind="imperium",
            title="Shifting Allegiances",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.original.shifting_allegiances",
                    "CardCount": 2,
                    "DeferValue": 3,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 1.1,
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.shifting_allegiances",
                    ),
                }
            ),
        ),
        "imperium.original.sietch_reverend_mother": Archetype(
            short="imperium.original.sietch_reverend_mother",
            kind="imperium",
            title="Sietch Reverend Mother",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.5,
                    "ArchID": "imperium.original.sietch_reverend_mother",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit", "Fremen"),
                    "IconList": ("BeneGesserit", "Fremen"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 4,
                    "SetList": ("original",),
                    "Tags": ("FremenBond",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.play.original.sietch_reverend_mother",
                        "ability.activated.trash_agent",
                        "ability.play.original.sietch_reverend_mother_reveal",
                    ),
                }
            ),
        ),
        "imperium.original.signet_ring": Archetype(
            short="imperium.original.signet_ring",
            kind="starter",
            title="Signet Ring",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.original.signet_ring",
                    "DeferValue": 3,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Starter",
                    "Persuasion": 1,
                    "SetList": ("original",),
                    "SignetIcons": 1,
                    "TrashValue": 0.0,
                    "AbilityIDs": ("ability.play.agent", "ability.play.reveal"),
                }
            ),
        ),
        "imperium.original.smugglers_thopter": Archetype(
            short="imperium.original.smugglers_thopter",
            kind="imperium",
            title="Smuggler's Thopter",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.1,
                    "ArchID": "imperium.original.smugglers_thopter",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("original",),
                    "Spice": 1,
                    "Tags": ("SpacingGuildInfluence",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.smugglers_thopter",
                        "ability.activated.original.smugglers_thopter",
                    ),
                }
            ),
        ),
        "imperium.original.space_travel": Archetype(
            short="imperium.original.space_travel",
            kind="imperium",
            title="Space Travel",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.7,
                    "ArchID": "imperium.original.space_travel",
                    "CardCount": 2,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild",),
                    "ImperiumType": "Main",
                    "LateMod": 1.1,
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "imperium.original.spice_hunter": Archetype(
            short="imperium.original.spice_hunter",
            kind="imperium",
            title="Spice Hunter",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 0.9,
                    "ArchID": "imperium.original.spice_hunter",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("original",),
                    "Strength": 1,
                    "Tags": ("FremenBond",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.original.spice_hunter",
                    ),
                }
            ),
        ),
        "imperium.original.spice_smugglers": Archetype(
            short="imperium.original.spice_smugglers",
            kind="imperium",
            title="Spice Smugglers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.1,
                    "ArchID": "imperium.original.spice_smugglers",
                    "CardCount": 2,
                    "EarlyMod": 1.1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("original",),
                    "Strength": 1,
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.spice_smugglers",
                    ),
                }
            ),
        ),
        "imperium.original.stilgar": Archetype(
            short="imperium.original.stilgar",
            kind="imperium",
            title="Stilgar",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.4,
                    "AgentWater": 1,
                    "ArchID": "imperium.original.stilgar",
                    "CardCount": 1,
                    "EarlyMod": 0.97,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 5,
                    "SetList": ("original",),
                    "Strength": 3,
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.original.test_of_humanity": Archetype(
            short="imperium.original.test_of_humanity",
            kind="imperium",
            title="Test of Humanity",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.original.test_of_humanity",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit", "Pentagon", "Circle"),
                    "ImperiumType": "Main",
                    "LateMod": 0.85,
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.original.test_of_humanity",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.test_of_humanity_deferred",
                    ),
                }
            ),
        ),
        "imperium.original.the_spice_must_flow": Archetype(
            short="imperium.original.the_spice_must_flow",
            kind="reserve",
            title="The Spice Must Flow",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("VP",),
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.original.the_spice_must_flow",
                    "CardCount": 10,
                    "EarlyMod": 0.66,
                    "EntityType": "Imperium",
                    "ImperiumType": "Reserve",
                    "LateMod": 1.33,
                    "PersuasionCost": 9,
                    "SetList": ("original",),
                    "Spice": 1,
                    "TrashValue": 0.5,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.original.the_voice": Archetype(
            short="imperium.original.the_voice",
            kind="imperium",
            title="The Voice",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.0,
                    "ArchID": "imperium.original.the_voice",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 2,
                    "SetList": ("original",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.the_voice",
                    ),
                }
            ),
        ),
        "imperium.original.thufir_hawat": Archetype(
            short="imperium.original.thufir_hawat",
            kind="imperium",
            title="Thufir Hawat",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.4,
                    "ArchID": "imperium.original.thufir_hawat",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "IconList": (
                        "Emperor",
                        "SpacingGuild",
                        "BeneGesserit",
                        "Fremen",
                        "Circle",
                        "Triangle",
                    ),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("original",),
                    "Tags": ("NamedCharacter",),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.original.thufir_hawat_reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                        "ability.activated.reveal_gain_intrigue",
                    ),
                }
            ),
        ),
        "imperium.original.worm_riders": Archetype(
            short="imperium.original.worm_riders",
            kind="imperium",
            title="Worm Riders",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.0,
                    "AgentSpice": 2,
                    "ArchID": "imperium.original.worm_riders",
                    "CardCount": 2,
                    "EarlyMod": 0.97,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 6,
                    "SetList": ("original",),
                    "Tags": (
                        "FremenInfluence",
                        "FremenAlliance",
                        "ConditionalStrength",
                    ),
                    "TrashValue": 0.0,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.triggered.original.worm_riders_influence",
                        "ability.play.original.worm_riders_alliance",
                        "ability.play.original.worm_riders_reveal",
                    ),
                }
            ),
        ),
        "imperium.immortality.bene_tleilax_lab": Archetype(
            short="imperium.immortality.bene_tleilax_lab",
            kind="imperium",
            title="Bene Tleilax Lab",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "AgentSpecimen": 1,
                    "ArchID": "imperium.immortality.bene_tleilax_lab",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("immortality",),
                    "Tags": ("Helix",),
                    "AbilityIDs": (
                        "ability.play.immortality.specimen_agent",
                        "ability.activated.acquire",
                        "ability.play.reveal",
                        "ability.activated.immortality.bene_tleilax_lab",
                    ),
                }
            ),
        ),
        "imperium.immortality.bene_tleilax_researcher": Archetype(
            short="imperium.immortality.bene_tleilax_researcher",
            kind="imperium",
            title="Bene Tleilax Researcher",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.7,
                    "ArchID": "imperium.immortality.bene_tleilax_researcher",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("immortality",),
                    "Tags": ("Graft", "Helix", "DoubleHelix"),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.activated.acquire",
                        "ability.play.immortality.bene_tleilax_researcher_reveal",
                        "ability.activated.immortality.gain_research_agent",
                        "ability.triggered.immortality.bene_tleilax_researcher_reveal_helix",
                        "ability.triggered.immortality.bene_tleilax_researcher_reveal_double_helix",
                    ),
                }
            ),
        ),
        "imperium.immortality.blank_slate": Archetype(
            short="imperium.immortality.blank_slate",
            kind="imperium",
            title="Blank Slate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.0,
                    "ArchID": "imperium.immortality.blank_slate",
                    "CardCount": 1,
                    "ConditionalIconList": (
                        "Emperor",
                        "SpacingGuild",
                        "BeneGesserit",
                        "Fremen",
                    ),
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("immortality",),
                    "Tags": ("WantsGraft",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.immortality.clandestine_meeting": Archetype(
            short="imperium.immortality.clandestine_meeting",
            kind="imperium",
            title="Clandestine Meeting",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.immortality.clandestine_meeting",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionInfluence": {"BeneGesserit": 1},
                    "FactionList": ("BeneGesserit",),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("immortality",),
                    "Tags": ("WantsGraft",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.agent_gain_intrigue",
                        "ability.space.gain_influence",
                    ),
                }
            ),
        ),
        "imperium.immortality.corrupt_smuggler": Archetype(
            short="imperium.immortality.corrupt_smuggler",
            kind="imperium",
            title="Corrupt Smuggler",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.9,
                    "ArchID": "imperium.immortality.corrupt_smuggler",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild", "Fremen"),
                    "IconList": ("SpacingGuild", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("immortality",),
                    "Strength": 1,
                    "Tags": ("WantsGraft",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.corrupt_smuggler",
                    ),
                }
            ),
        ),
        "imperium.immortality.dissecting_kit": Archetype(
            short="imperium.immortality.dissecting_kit",
            kind="imperium",
            title="Dissecting Kit",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.6,
                    "ArchID": "imperium.immortality.dissecting_kit",
                    "CardCount": 2,
                    "EarlyMod": 1.2,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon", "Circle"),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("immortality",),
                    "Tags": ("Graft", "Helix", "Shadow"),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.dissecting_kit_agent",
                        "ability.activated.immortality.dissecting_kit_reveal",
                    ),
                }
            ),
        ),
        "imperium.immortality.experimentation": Archetype(
            short="imperium.immortality.experimentation",
            kind="starter",
            title="Experimentation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "imperium.immortality.experimentation",
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Starter",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "Specimen": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.immortality.gain_research_agent",
                    ),
                }
            ),
        ),
        "imperium.immortality.for_humanity": Archetype(
            short="imperium.immortality.for_humanity",
            kind="imperium",
            title="For Humanity",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 7.0,
                    "ArchID": "imperium.immortality.for_humanity",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit", "Pentagon", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 7,
                    "SetList": ("immortality",),
                    "Tags": ("BeneGesseritAlliance",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.for_humanity_reveal",
                        "ability.activated.immortality.for_humanity_agent",
                    ),
                }
            ),
        ),
        "imperium.immortality.high_priority_travel": Archetype(
            short="imperium.immortality.high_priority_travel",
            kind="imperium",
            title="High Priority Travel",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 0.9,
                    "ArchID": "imperium.immortality.high_priority_travel",
                    "CardCount": 2,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Pentagon", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("immortality",),
                    "Solari": 1,
                    "Tags": ("SpacingGuildInfluence", "Combat"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.high_priority_travel",
                        "ability.activated.high_priority_travel_deploy_units_custom",
                    ),
                }
            ),
        ),
        "imperium.immortality.imperium_ceremony": Archetype(
            short="imperium.immortality.imperium_ceremony",
            kind="imperium",
            title="Imperium Ceremony",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 6.5,
                    "ArchID": "imperium.immortality.imperium_ceremony",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "SpacingGuild"),
                    "IconList": ("Emperor", "SpacingGuild", "Pentagon"),
                    "ImperiumType": "Main",
                    "Persuasion": 3,
                    "PersuasionCost": 6,
                    "SetList": ("immortality",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.imperium_ceremony",
                    ),
                }
            ),
        ),
        "imperium.immortality.interstellar_conspiracy": Archetype(
            short="imperium.immortality.interstellar_conspiracy",
            kind="imperium",
            title="Interstellar Conspiracy",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.7,
                    "AgentSpice": 1,
                    "ArchID": "imperium.immortality.interstellar_conspiracy",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("immortality",),
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.interstellar_conspiracy",
                    ),
                }
            ),
        ),
        "imperium.immortality.keys_to_power": Archetype(
            short="imperium.immortality.keys_to_power",
            kind="imperium",
            title="Keys to Power",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.0,
                    "ArchID": "imperium.immortality.keys_to_power",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild", "BeneGesserit"),
                    "IconList": ("SpacingGuild", "BeneGesserit", "Pentagon"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 5,
                    "SetList": ("immortality",),
                    "Tags": ("EmperorInfluence",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.keys_to_power",
                    ),
                }
            ),
        ),
        "imperium.immortality.lisanal_gaib": Archetype(
            short="imperium.immortality.lisanal_gaib",
            kind="imperium",
            title="Lisan al Gaib",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Spice",),
                    "AcquireValue": 2.0,
                    "ArchID": "imperium.immortality.lisanal_gaib",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit", "Fremen"),
                    "IconList": ("Fremen", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("immortality",),
                    "Tags": ("NamedCharacter", "FremenBond", "ConditionalStrength"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.play.immortality.lisan_al_gaib_agent",
                        "ability.triggered.immortality.lisan_al_gaib_reveal",
                        "ability.play.immortality.lisan_al_gaib_reveal_preview",
                    ),
                }
            ),
        ),
        "imperium.immortality.long_reach": Archetype(
            short="imperium.immortality.long_reach",
            kind="imperium",
            title="Long Reach",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 6.0,
                    "ArchID": "imperium.immortality.long_reach",
                    "CardCount": 1,
                    "ConditionalIconList": ("Pentagon", "Circle", "Triangle"),
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 6,
                    "SetList": ("immortality",),
                    "Tags": ("WantsGraft", "WantBG"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.activated.immortality.long_reach_agent",
                        "ability.activated.reveal_gain_intrigue",
                        "ability.play.original.thufir_hawat_reveal",
                    ),
                }
            ),
        ),
        "imperium.immortality.occupation": Archetype(
            short="imperium.immortality.occupation",
            kind="imperium",
            title="Occupation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Troop", "Troop", "Troop"),
                    "AcquireValue": 5.7,
                    "ArchID": "imperium.immortality.occupation",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": (
                        "Emperor",
                        "SpacingGuild",
                        "BeneGesserit",
                        "Fremen",
                        "Circle",
                        "Triangle",
                    ),
                    "ImperiumType": "Main",
                    "PersuasionCost": 8,
                    "SetList": ("immortality",),
                    "Spice": 1,
                    "Tags": ("Combat",),
                    "Troops": 1,
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                        "ability.activated.deploy_units",
                    ),
                }
            ),
        ),
        "imperium.immortality.organ_merchants": Archetype(
            short="imperium.immortality.organ_merchants",
            kind="imperium",
            title="Organ Merchants",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.7,
                    "ArchID": "imperium.immortality.organ_merchants",
                    "CardCount": 1,
                    "EarlyMod": 1.1,
                    "EntityType": "Imperium",
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 0.9,
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("immortality",),
                    "Solari": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.organ_merchants",
                    ),
                }
            ),
        ),
        "imperium.immortality.planned_coupling": Archetype(
            short="imperium.immortality.planned_coupling",
            kind="imperium",
            title="Planned Coupling",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.immortality.planned_coupling",
                    "CardCount": 2,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("immortality",),
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "imperium.immortality.replacement_eyes": Archetype(
            short="imperium.immortality.replacement_eyes",
            kind="imperium",
            title="Replacement Eyes",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.5,
                    "ArchID": "imperium.immortality.replacement_eyes",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EarlyMod": 1.1,
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.9,
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("immortality",),
                    "Strength": 1,
                    "Tags": ("Graft", "Shadow"),
                    "TrashValue": 0.1,
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.triggered.immortality.replacement_eyes_trash",
                        "ability.activated.immortality.replacement_eyes_agent",
                    ),
                }
            ),
        ),
        "imperium.immortality.sardaukar_quartermaster": Archetype(
            short="imperium.immortality.sardaukar_quartermaster",
            kind="imperium",
            title="Sardaukar Quartermaster",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.immortality.sardaukar_quartermaster",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Pentagon", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("immortality",),
                    "Strength": 2,
                    "Tags": ("WantsGraft",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.sardaukar_quartermaster_troop",
                        "ability.activated.immortality.sardaukar_quartermaster_draw",
                    ),
                }
            ),
        ),
        "imperium.immortality.shadout_mapes": Archetype(
            short="imperium.immortality.shadout_mapes",
            kind="imperium",
            title="Shadout Mapes",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.0,
                    "ArchID": "imperium.immortality.shadout_mapes",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("immortality",),
                    "Strength": 1,
                    "Tags": ("NamedCharacter",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.shadout_mapes",
                    ),
                }
            ),
        ),
        "imperium.immortality.show_of_strength": Archetype(
            short="imperium.immortality.show_of_strength",
            kind="imperium",
            title="Show of Strength",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.immortality.show_of_strength",
                    "CardCount": 1,
                    "ConditionalIconList": ("Pentagon", "Triangle"),
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "Fremen"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("immortality",),
                    "Strength": 2,
                    "Tags": ("WantsGraft",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                        "ability.activated.draw",
                        "ability.triggered.immortality.show_of_strength",
                    ),
                }
            ),
        ),
        "imperium.immortality.spiritual_fervor": Archetype(
            short="imperium.immortality.spiritual_fervor",
            kind="imperium",
            title="Spiritual Fervor",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Research",),
                    "AcquireValue": 1.5,
                    "ArchID": "imperium.immortality.spiritual_fervor",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("immortality",),
                    "Specimen": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.immortality.stillsuit_manufacturer": Archetype(
            short="imperium.immortality.stillsuit_manufacturer",
            kind="imperium",
            title="Stillsuit Manufacturer",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.5,
                    "AgentWater": 1,
                    "ArchID": "imperium.immortality.stillsuit_manufacturer",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("immortality",),
                    "Tags": ("FremenBond", "FremenAlliance"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.stillsuit_manufacturer_agent",
                        "ability.triggered.immortality.stillsuit_manufacturer_reveal",
                    ),
                }
            ),
        ),
        "imperium.immortality.throne_room_politics": Archetype(
            short="imperium.immortality.throne_room_politics",
            kind="imperium",
            title="Throne Room Politics",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.3,
                    "AgentTroops": 1,
                    "ArchID": "imperium.immortality.throne_room_politics",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "BeneGesserit"),
                    "IconList": ("Emperor",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("immortality",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.immortality.throne_room_politics_reveal",
                        "ability.activated.acquire",
                        "ability.activated.trash_agent",
                        "ability.activated.ix.in_the_shadows_reveal",
                    ),
                }
            ),
        ),
        "imperium.immortality.tleilaxu_master": Archetype(
            short="imperium.immortality.tleilaxu_master",
            kind="imperium",
            title="Tleilaxu Master",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.0,
                    "ArchID": "imperium.immortality.tleilaxu_master",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("immortality",),
                    "Tags": ("Helix", "DoubleHelix"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.immortality.tleilaxu_master",
                        "ability.activated.immortality.gain_research_reveal",
                        "ability.activated.immortality.gain_research_reveal",
                    ),
                }
            ),
        ),
        "imperium.immortality.tleilaxu_surgeon": Archetype(
            short="imperium.immortality.tleilaxu_surgeon",
            kind="imperium",
            title="Tleilaxu Surgeon",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.immortality.tleilaxu_surgeon",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Emperor", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("immortality",),
                    "Tags": ("Shadow",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.tleilaxu_surgeon_agent",
                        "ability.activated.immortality.tleilaxu_surgeon_reveal",
                    ),
                }
            ),
        ),
        "imperium.promo.arrakis_revolt": Archetype(
            short="imperium.promo.arrakis_revolt",
            kind="imperium",
            title="Arrakis Revolt",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "imperium.promo.arrakis_revolt",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Promo",
                    "Persuasion": 1,
                    "PersuasionCost": 6,
                    "SetList": ("uprising",),
                    "Strength": 3,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.promo.arrakis_revolt",
                    ),
                }
            ),
        ),
        "imperium.promo.boundless_ambition": Archetype(
            short="imperium.promo.boundless_ambition",
            kind="imperium",
            title="Boundless Ambition",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.0,
                    "ArchID": "imperium.promo.boundless_ambition",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Promo",
                    "PersuasionCost": 5,
                    "SetList": ("ix",),
                    "SignetIcons": 1,
                    "Tags": ("IncentiveDiscard",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.activated.promo.boundless_ambition_reveal",
                        "ability.triggered.promo.boundless_ambition_unload",
                        "ability.triggered.promo.boundless_ambition_unload_opp",
                    ),
                }
            ),
        ),
        "imperium.promo.duncan_loyal_blade": Archetype(
            short="imperium.promo.duncan_loyal_blade",
            kind="imperium",
            title="Duncan, Loyal Blade",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.0,
                    "AgentTroops": 1,
                    "ArchID": "imperium.promo.duncan_loyal_blade",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Fremen", "Circle"),
                    "ImperiumType": "Promo",
                    "LateMod": 1.2,
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("original",),
                    "Strength": 2,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.promo.duncan_loyal_blade",
                        "ability.activated.promo.duncan_loyal_blade_deploy",
                        "ability.activated.promo.duncan_loyal_blade_retreat",
                    ),
                }
            ),
        ),
        "imperium.promo.jessica_of_arrakis": Archetype(
            short="imperium.promo.jessica_of_arrakis",
            kind="imperium",
            title="Jessica of Arrakis",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.5,
                    "ArchID": "imperium.promo.jessica_of_arrakis",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Promo",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "Strength": 2,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.bene_gesserit_draw",
                        "ability.activated.bene_gesserit_draw",
                    ),
                }
            ),
        ),
        "imperium.promo.pivotal_gambit": Archetype(
            short="imperium.promo.pivotal_gambit",
            kind="imperium",
            title="Pivotal Gambit",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "imperium.promo.pivotal_gambit",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle"),
                    "ImperiumType": "Promo",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Strength": 2,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.promo.pivotal_gambit",
                    ),
                }
            ),
        ),
        "imperium.promo.the_beasts_spoils": Archetype(
            short="imperium.promo.the_beasts_spoils",
            kind="imperium",
            title="The Beast's Spoils",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "imperium.promo.the_beasts_spoils",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Promo",
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Strength": 3,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.promo.the_beasts_spoils_crysknife",
                        "ability.activated.promo.the_beasts_spoils_desert_mouse",
                        "ability.activated.promo.the_beasts_spoils_ornithopter",
                    ),
                }
            ),
        ),
        "imperium.promo.thumper": Archetype(
            short="imperium.promo.thumper",
            kind="imperium",
            title="Thumper",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.75,
                    "ArchID": "imperium.promo.thumper",
                    "CardCount": 1,
                    "EarlyMod": 1.2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Promo",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("original",),
                    "Spice": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.appropriate": Archetype(
            short="imperium.ix.appropriate",
            kind="imperium",
            title="Appropriate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Freighter",),
                    "AcquireValue": 4.9,
                    "ArchID": "imperium.ix.appropriate",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Pentagon", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 5,
                    "SetList": ("ix",),
                    "Tags": ("EmperorInfluence", "BuyTech", "Freighter"),
                    "AbilityIDs": (
                        "ability.activated.ix.appropriate",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.bounty_hunter": Archetype(
            short="imperium.ix.bounty_hunter",
            kind="imperium",
            title="Bounty Hunter",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.1,
                    "ArchID": "imperium.ix.bounty_hunter",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "InfiltrationIconList": ("Circle",),
                    "LateMod": 0.66,
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("ix",),
                    "Strength": 1,
                    "Tags": ("Infiltrator",),
                    "AbilityIDs": (
                        "ability.activated.ix.bounty_hunter",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.choam_delegate": Archetype(
            short="imperium.ix.choam_delegate",
            kind="imperium",
            title="CHOAM Delegate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.1,
                    "ArchID": "imperium.ix.choam_delegate",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "InfiltrationIconList": ("Triangle",),
                    "LateMod": 0.66,
                    "PersuasionCost": 1,
                    "SetList": ("ix",),
                    "Solari": 3,
                    "Tags": ("IncentiveDiscard", "Infiltrator"),
                    "TrashValue": 1.15,
                    "AbilityIDs": (
                        "ability.triggered.ix.unload",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.control_the_spice": Archetype(
            short="imperium.ix.control_the_spice",
            kind="starter",
            title="Control The Spice",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "imperium.ix.control_the_spice",
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Starter",
                    "Persuasion": 1,
                    "SetList": ("ix",),
                    "Spice": 1,
                    "AbilityIDs": (
                        "ability.activated.ix.control_the_spice",
                        "ability.play.agent",
                        "ability.play.reveal",
                    ),
                }
            ),
        ),
        "imperium.ix.court_intrigue": Archetype(
            short="imperium.ix.court_intrigue",
            kind="imperium",
            title="Court Intrigue",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.2,
                    "ArchID": "imperium.ix.court_intrigue",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor",),
                    "ImperiumType": "Main",
                    "InfiltrationIconList": ("Emperor",),
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("ix",),
                    "Strength": 1,
                    "Tags": ("Infiltrator",),
                    "AbilityIDs": (
                        "ability.activated.ix.court_intrigue",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.desert_ambush": Archetype(
            short="imperium.ix.desert_ambush",
            kind="imperium",
            title="Desert Ambush",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.1,
                    "ArchID": "imperium.ix.desert_ambush",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("ix",),
                    "Strength": 1,
                    "AbilityIDs": (
                        "ability.activated.ix.desert_ambush",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.embedded_agent": Archetype(
            short="imperium.ix.embedded_agent",
            kind="imperium",
            title="Embedded Agent",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.7,
                    "ArchID": "imperium.ix.embedded_agent",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Main",
                    "InfiltrationIconList": ("Pentagon",),
                    "LateMod": 0.9,
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("ix",),
                    "Tags": ("Infiltrator", "Freighter", "WantBG"),
                    "AbilityIDs": (
                        "ability.activated.original.embedded_agent",
                        "ability.play.original.thufir_hawat_reveal",
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.activated.reveal_gain_intrigue",
                    ),
                }
            ),
        ),
        "imperium.ix.esmar_tuek": Archetype(
            short="imperium.ix.esmar_tuek",
            kind="imperium",
            title="Esmar Tuek",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.9,
                    "ArchID": "imperium.ix.esmar_tuek",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 5,
                    "SetList": ("ix",),
                    "Solari": 2,
                    "Spice": 2,
                    "Tags": ("IncentiveDiscard", "NamedCharacter"),
                    "TrashValue": 1.3,
                    "AbilityIDs": (
                        "ability.triggered.ix.unload",
                        "ability.activated.ix.esmar_tuek",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.freighter_fleet": Archetype(
            short="imperium.ix.freighter_fleet",
            kind="imperium",
            title="Freighter Fleet",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.1,
                    "ArchID": "imperium.ix.freighter_fleet",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.66,
                    "PersuasionCost": 2,
                    "SetList": ("ix",),
                    "Tags": ("IncentiveDiscard", "Freighter"),
                    "TrashValue": 1.2,
                    "AbilityIDs": (
                        "ability.triggered.ix.freighter_fleet_opp_track_positive",
                        "ability.triggered.ix.freighter_fleet_opp_track_zero",
                        "ability.triggered.ix.freighter_fleet_unload",
                        "ability.activated.ix.freighter_reveal",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.full_scale_assault": Archetype(
            short="imperium.ix.full_scale_assault",
            kind="imperium",
            title="Full-Scale Assault",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Dreadnought",),
                    "AcquireValue": 8.0,
                    "AgentTroops": 2,
                    "ArchID": "imperium.ix.full_scale_assault",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 8,
                    "SetList": ("ix",),
                    "Tags": ("ConditionalStrength",),
                    "AbilityIDs": (
                        "ability.play.ix.full_scale_assault_reveal",
                        "ability.triggered.ix.full_scale_assault",
                        "ability.play.agent",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.guild_accord": Archetype(
            short="imperium.ix.guild_accord",
            kind="imperium",
            title="Guild Accord",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.5,
                    "ArchID": "imperium.ix.guild_accord",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild",),
                    "ImperiumType": "Main",
                    "InfiltrationIconList": ("SpacingGuild",),
                    "LateMod": 1.2,
                    "PersuasionCost": 6,
                    "SetList": ("ix",),
                    "Tags": ("IncentiveDiscard", "SpacingGuildAlliance", "Infiltrator"),
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.triggered.ix.guild_accord_unload",
                        "ability.triggered.ix.guild_accord_alliance",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.guild_chief_administrator": Archetype(
            short="imperium.ix.guild_chief_administrator",
            kind="imperium",
            title="Guild Chief Administrator",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.9,
                    "ArchID": "imperium.ix.guild_chief_administrator",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EarlyMod": 1.1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("ix",),
                    "Tags": ("DiscardEnabler", "Freighter"),
                    "AbilityIDs": (
                        "ability.activated.ix.guild_chief_administrator",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.ix.freighter_reveal",
                    ),
                }
            ),
        ),
        "imperium.ix.imperial_bashar": Archetype(
            short="imperium.ix.imperial_bashar",
            kind="imperium",
            title="Imperial Bashar",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.9,
                    "ArchID": "imperium.ix.imperial_bashar",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EarlyMod": 1.1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("ix",),
                    "Strength": 2,
                    "AbilityIDs": (
                        "ability.activated.ix.imperial_bashar_agent",
                        "ability.triggered.ix.imperial_bashar_reveal",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.imperial_shock_trooper": Archetype(
            short="imperium.ix.imperial_shock_trooper",
            kind="imperium",
            title="Imperial Shock Trooper",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.ix.imperial_shock_trooper",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("ix",),
                    "Strength": 2,
                    "AbilityIDs": (
                        "ability.play.ix.imperial_shock_trooper",
                        "ability.play.agent",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.in_the_shadows": Archetype(
            short="imperium.ix.in_the_shadows",
            kind="imperium",
            title="In The Shadows",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.7,
                    "ArchID": "imperium.ix.in_the_shadows",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Pentagon", "Circle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 2,
                    "SetList": ("ix",),
                    "Tags": (
                        "IncentiveDiscard",
                        "BeneGesseritInfluence",
                        "DiscardEnabler",
                    ),
                    "AbilityIDs": (
                        "ability.activated.ix.in_the_shadows_agent",
                        "ability.activated.ix.in_the_shadows_reveal",
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.triggered.ix.in_the_shadows_unload",
                        "ability.play.ix.in_the_shadows_reveal_preview",
                    ),
                }
            ),
        ),
        "imperium.ix.ix_guild_compact": Archetype(
            short="imperium.ix.ix_guild_compact",
            kind="imperium",
            title="Ix-Guild Compact",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.ix.ix_guild_compact",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild",),
                    "ImperiumType": "Main",
                    "LateMod": 0.66,
                    "PersuasionCost": 3,
                    "SetList": ("ix",),
                    "Tags": ("IncentiveDiscard", "DiscardEnabler"),
                    "AbilityIDs": (
                        "ability.activated.ix.ix_guild_compact_agent",
                        "ability.play.ix.ix_guild_compact_reveal",
                        "ability.triggered.ix.unload",
                        "ability.play.agent",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.ixian_engineer": Archetype(
            short="imperium.ix.ixian_engineer",
            kind="imperium",
            title="Ixian Engineer",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.5,
                    "ArchID": "imperium.ix.ixian_engineer",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 5,
                    "SetList": ("ix",),
                    "Tags": ("BuyTech",),
                    "AbilityIDs": (
                        "ability.activated.ix.ixian_engineer",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.ix.acquire_tech_agent",
                    ),
                }
            ),
        ),
        "imperium.ix.jamis": Archetype(
            short="imperium.ix.jamis",
            kind="imperium",
            title="Jamis",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.ix.jamis",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EarlyMod": 1.3,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen",),
                    "ImperiumType": "Main",
                    "InfiltrationIconList": ("Fremen",),
                    "LateMod": 0.75,
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("ix",),
                    "Strength": 2,
                    "Tags": ("NamedCharacter", "Infiltrator"),
                    "AbilityIDs": (
                        "ability.activated.trash_agent",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.landing_rights": Archetype(
            short="imperium.ix.landing_rights",
            kind="imperium",
            title="Landing Rights",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.0,
                    "ArchID": "imperium.ix.landing_rights",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "LateMod": 8.0,
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("ix",),
                    "Tags": ("Freighter",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.ix.freighter_agent",
                    ),
                }
            ),
        ),
        "imperium.ix.local_fence": Archetype(
            short="imperium.ix.local_fence",
            kind="imperium",
            title="Local Fence",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.ix.local_fence",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("ix",),
                    "AbilityIDs": (
                        "ability.activated.ix.local_fence",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.negotiated_withdrawal": Archetype(
            short="imperium.ix.negotiated_withdrawal",
            kind="imperium",
            title="Negotiated Withdrawal",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Troop",),
                    "AcquireValue": 4.3,
                    "ArchID": "imperium.ix.negotiated_withdrawal",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("ix",),
                    "AbilityIDs": (
                        "ability.activated.ix.negotiated_withdrawal",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.satellite_ban": Archetype(
            short="imperium.ix.satellite_ban",
            kind="imperium",
            title="Satellite Ban",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.9,
                    "ArchID": "imperium.ix.satellite_ban",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild", "Fremen"),
                    "IconList": ("SpacingGuild", "Fremen"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("ix",),
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": (
                        "ability.activated.ix.satellite_ban",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.original.satellite_ban_reveal",
                    ),
                }
            ),
        ),
        "imperium.ix.sayyadina": Archetype(
            short="imperium.ix.sayyadina",
            kind="imperium",
            title="Sayyadina",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.ix.sayyadina",
                    "CardCount": 1,
                    "EarlyMod": 0.75,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit", "Fremen"),
                    "IconList": ("BeneGesserit", "Fremen"),
                    "ImperiumType": "Main",
                    "LateMod": 1.1,
                    "PersuasionCost": 3,
                    "SetList": ("ix",),
                    "Tags": ("FremenBond",),
                    "AbilityIDs": (
                        "ability.play.ix.sayyadina_reveal",
                        "ability.activated.ix.sayyadina",
                        "ability.triggered.ix.sayyadina_bond",
                        "ability.play.agent",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.shai_hulud": Archetype(
            short="imperium.ix.shai_hulud",
            kind="imperium",
            title="Shai-Hulud",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Trash",),
                    "AcquireValue": 6.4,
                    "ArchID": "imperium.ix.shai_hulud",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "PersuasionCost": 7,
                    "SetList": ("ix",),
                    "Tags": ("FremenBond", "ConditionalStrength"),
                    "AbilityIDs": (
                        "ability.activated.ix.shai_hulud",
                        "ability.triggered.ix.shai_hulud_bond",
                        "ability.activated.ix.shai_hulud_acquire",
                        "ability.play.agent",
                        "ability.play.ix.shai_hulud_reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.spice_trader": Archetype(
            short="imperium.ix.spice_trader",
            kind="imperium",
            title="Spice Trader",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.ix.spice_trader",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("ix",),
                    "Strength": 1,
                    "Tags": ("FremenInfluence", "DiscardEnabler"),
                    "AbilityIDs": (
                        "ability.activated.ix.spice_trader",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.treachery": Archetype(
            short="imperium.ix.treachery",
            kind="imperium",
            title="Treachery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 6.5,
                    "ArchID": "imperium.ix.treachery",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Main",
                    "LateMod": 1.2,
                    "PersuasionCost": 6,
                    "SetList": ("ix",),
                    "Tags": ("IncentiveDiscard",),
                    "AbilityIDs": (
                        "ability.triggered.ix.unload",
                        "ability.play.ix.treachery_reveal",
                        "ability.activated.ix.treachery_trash_self",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.original.power_play_agent",
                    ),
                }
            ),
        ),
        "imperium.ix.truthsayer": Archetype(
            short="imperium.ix.truthsayer",
            kind="imperium",
            title="Truthsayer",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.1,
                    "ArchID": "imperium.ix.truthsayer",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "BeneGesserit"),
                    "IconList": ("Emperor", "BeneGesserit", "Pentagon"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("ix",),
                    "Strength": 1,
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": (
                        "ability.activated.ix.truthsayer",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.water_peddler": Archetype(
            short="imperium.ix.water_peddler",
            kind="imperium",
            title="Water Peddler",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Water",),
                    "AcquireValue": 1.0,
                    "ArchID": "imperium.ix.water_peddler",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "ImperiumType": "Main",
                    "LateMod": 0.66,
                    "PersuasionCost": 1,
                    "SetList": ("ix",),
                    "Tags": ("IncentiveDiscard",),
                    "TrashValue": 1.1,
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.triggered.ix.unload",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.web_of_power": Archetype(
            short="imperium.ix.web_of_power",
            kind="imperium",
            title="Web of Power",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.5,
                    "ArchID": "imperium.ix.web_of_power",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit",),
                    "ImperiumType": "Main",
                    "InfiltrationIconList": ("BeneGesserit",),
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("ix",),
                    "Tags": (
                        "FremenInfluence",
                        "SpacingGuildInfluence",
                        "EmperorInfluence",
                        "Infiltrator",
                    ),
                    "AbilityIDs": (
                        "ability.activated.ix.web_of_power_emperor",
                        "ability.activated.ix.web_of_power_spacing_guild",
                        "ability.activated.ix.web_of_power_fremen",
                        "ability.activated.ix.web_of_power_reveal",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.ix.weirding_way": Archetype(
            short="imperium.ix.weirding_way",
            kind="imperium",
            title="Weirding Way",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.2,
                    "ArchID": "imperium.ix.weirding_way",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("ix",),
                    "Strength": 2,
                    "AbilityIDs": (
                        "ability.activated.ix.weirding_way",
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.uprising.bene_gesserit_operative": Archetype(
            short="imperium.uprising.bene_gesserit_operative",
            kind="imperium",
            title="Bene Gesserit Operative",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.8,
                    "ArchID": "imperium.uprising.bene_gesserit_operative",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Tags": ("Spy", "WantSpy"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.uprising.bene_gesserit_operative_reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.place_spy_agent",
                        "ability.triggered.immortality.bene_gesserit_operative_triggered",
                    ),
                }
            ),
        ),
        "imperium.uprising.branching_path": Archetype(
            short="imperium.uprising.branching_path",
            kind="imperium",
            title="Branching Path",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.8,
                    "ArchID": "imperium.uprising.branching_path",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Tags": ("BeneGesseritAlliance",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.branching_path",
                    ),
                }
            ),
        ),
        "imperium.uprising.calculus_of_power": Archetype(
            short="imperium.uprising.calculus_of_power",
            kind="imperium",
            title="Calculus of Power",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.9,
                    "ArchID": "imperium.uprising.calculus_of_power",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Circle", "Spy"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Tags": ("WantE", "WantSpy"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.uprising.calculus_of_power_reveal",
                        "ability.activated.acquire",
                        "ability.activated.trash_agent",
                        "ability.activated.uprising.calculus_of_power_emperor",
                    ),
                }
            ),
        ),
        "imperium.uprising.captured_mentat": Archetype(
            short="imperium.uprising.captured_mentat",
            kind="imperium",
            title="Captured Mentat",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.0,
                    "ArchID": "imperium.uprising.captured_mentat",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("uprising",),
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.ix.captured_mentat_agent",
                        "ability.activated.original.captured_mentat_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.cargo_runner": Archetype(
            short="imperium.uprising.cargo_runner",
            kind="imperium",
            title="Cargo Runner",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.8,
                    "ArchID": "imperium.uprising.cargo_runner",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("choam_module",),
                    "Tags": ("WantContract2", "WantContract4"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.cargo_runner2_contracts_draw",
                        "ability.activated.uprising.cargo_runner4_contracts_draw",
                    ),
                }
            ),
        ),
        "imperium.uprising.chani_clever_tactician": Archetype(
            short="imperium.uprising.chani_clever_tactician",
            kind="imperium",
            title="Chani, Clever Tactician",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.8,
                    "ArchID": "imperium.uprising.chani_clever_tactician",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 5,
                    "SetList": ("uprising",),
                    "Tags": ("NamedCharacter", "FremenBond"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.uprising.southern_elders_reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.chani_clever_tactician_agent",
                        "ability.activated.uprising.chani_clever_tactician_reveal",
                        "ability.triggered.uprising.southern_elders_bond",
                    ),
                }
            ),
        ),
        "imperium.uprising.corrinth_city": Archetype(
            short="imperium.uprising.corrinth_city",
            kind="imperium",
            title="Corrinth City",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.8,
                    "ArchID": "imperium.uprising.corrinth_city",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "Pentagon"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 6,
                    "SetList": ("uprising",),
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.corrinth_city_agent",
                        "ability.activated.uprising.corrinth_city_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.covert_operation": Archetype(
            short="imperium.uprising.covert_operation",
            kind="imperium",
            title="Covert Operation",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.8,
                    "ArchID": "imperium.uprising.covert_operation",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Spy",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Tags": ("Spy", "WantSpy"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.covert_operation",
                        "ability.activated.uprising.place_spy_reveal",
                        "ability.activated.uprising.place_spy_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.dangerous_rhetoric": Archetype(
            short="imperium.uprising.dangerous_rhetoric",
            kind="imperium",
            title="Dangerous Rhetoric",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.uprising.dangerous_rhetoric",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon", "Spy"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "Tags": ("WantSpy",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.dangerous_rhetoric",
                        "ability.activated.trash_self",
                    ),
                }
            ),
        ),
        "imperium.uprising.delivery_agreement": Archetype(
            short="imperium.uprising.delivery_agreement",
            kind="imperium",
            title="Delivery Agreement",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.8,
                    "ArchID": "imperium.uprising.delivery_agreement",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 5,
                    "SetList": ("choam_module",),
                    "Tags": ("DiscardEnabler", "Contract", "WantContract4"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.delivery_agreement_agent",
                        "ability.activated.uprising.delivery_agreement_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.demand_attention": Archetype(
            short="imperium.uprising.demand_attention",
            kind="starter",
            title="Demand Attention",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "imperium.uprising.demand_attention",
                    "CardCount": 1,
                    "DeferValue": 3,
                    "EntityType": "Imperium",
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Starter",
                    "Persuasion": 1,
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.demand_attention",
                    ),
                }
            ),
        ),
        "imperium.uprising.desert_call": Archetype(
            short="imperium.uprising.desert_call",
            kind="starter",
            title="Desert Call",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "imperium.uprising.desert_call",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Starter",
                    "Persuasion": 1,
                    "SetList": ("uprising",),
                    "Tags": ("Sandworm", "MakerHooks"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.desert_call",
                    ),
                }
            ),
        ),
        "imperium.uprising.desert_power_imperium": Archetype(
            short="imperium.uprising.desert_power_imperium",
            kind="imperium",
            title="Desert Power",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.8,
                    "ArchID": "imperium.uprising.desert_power_imperium",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 6,
                    "SetList": ("uprising",),
                    "Tags": ("WantHooks", "Sandworm", "MakerHooks"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.uprising.desert_power_reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.desert_power_agent",
                        "ability.activated.uprising.desert_power_deferred",
                    ),
                }
            ),
        ),
        "imperium.uprising.desert_survival": Archetype(
            short="imperium.uprising.desert_survival",
            kind="imperium",
            title="Desert Survival",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.0,
                    "ArchID": "imperium.uprising.desert_survival",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.trash_agent",
                    ),
                }
            ),
        ),
        "imperium.uprising.double_agent": Archetype(
            short="imperium.uprising.double_agent",
            kind="imperium",
            title="Double Agent",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.8,
                    "ArchID": "imperium.uprising.double_agent",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "SpacingGuild"),
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "Tags": ("Spy",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.double_agent",
                    ),
                }
            ),
        ),
        "imperium.uprising.ecological_testing_station": Archetype(
            short="imperium.uprising.ecological_testing_station",
            kind="imperium",
            title="Ecological Testing Station",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.8,
                    "ArchID": "imperium.uprising.ecological_testing_station",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Tags": ("FremenBond",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.ecological_testing_station",
                        "ability.triggered.uprising.ecological_testing_station_bond",
                    ),
                }
            ),
        ),
        "imperium.uprising.fedaykin_stilltent": Archetype(
            short="imperium.uprising.fedaykin_stilltent",
            kind="imperium",
            title="Fedaykin Stilltent",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.0,
                    "ArchID": "imperium.uprising.fedaykin_stilltent",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.fedaykin_stilltent",
                    ),
                }
            ),
        ),
        "imperium.uprising.guild_envoy": Archetype(
            short="imperium.uprising.guild_envoy",
            kind="imperium",
            title="Guild Envoy",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.9,
                    "ArchID": "imperium.uprising.guild_envoy",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Tags": ("WantSG",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.guild_envoy",
                        "ability.activated.uprising.spacing_guild_discard_draw",
                        "ability.activated.uprising.spacing_guild_discard_draw",
                    ),
                }
            ),
        ),
        "imperium.uprising.guild_spy": Archetype(
            short="imperium.uprising.guild_spy",
            kind="imperium",
            title="Guild Spy",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("PlaceSpy",),
                    "AcquireValue": 3.1,
                    "ArchID": "imperium.uprising.guild_spy",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Spy",),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Tags": ("WantSpy", "WantSG", "Spy"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.guild_spy_agent",
                        "ability.activated.uprising.guild_spy_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.hidden_missive": Archetype(
            short="imperium.uprising.hidden_missive",
            kind="imperium",
            title="Hidden Missive",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.8,
                    "ArchID": "imperium.uprising.hidden_missive",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "Tags": ("BeneGesseritInfluence",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.bene_gesserit_influence_draw",
                        "ability.activated.uprising.bene_gesserit_influence_troop",
                    ),
                }
            ),
        ),
        "imperium.uprising.imperial_spymaster": Archetype(
            short="imperium.uprising.imperial_spymaster",
            kind="imperium",
            title="Imperial Spymaster",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.8,
                    "ArchID": "imperium.uprising.imperial_spymaster",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "Spy"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "Tags": ("WantSpy", "WantRecall"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.imperial_spymaster",
                    ),
                }
            ),
        ),
        "imperium.uprising.in_high_places": Archetype(
            short="imperium.uprising.in_high_places",
            kind="imperium",
            title="In High Places",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("PlaceSpy",),
                    "AcquireValue": 4.7,
                    "ArchID": "imperium.uprising.in_high_places",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "BeneGesserit"),
                    "IconList": ("Emperor", "BeneGesserit"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 5,
                    "SetList": ("uprising",),
                    "Tags": ("WantBG", "Spy", "WantSpy", "RecallSpy"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.original.in_high_places_reveal",
                        "ability.activated.acquire",
                        "ability.activated.bene_gesserit_draw",
                        "ability.activated.uprising.in_high_places_place_spy",
                        "ability.activated.uprising.in_high_places_persuasion",
                    ),
                }
            ),
        ),
        "imperium.uprising.interstellar_trade": Archetype(
            short="imperium.uprising.interstellar_trade",
            kind="imperium",
            title="Interstellar Trade",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Contract",),
                    "AcquireValue": 6.8,
                    "ArchID": "imperium.uprising.interstellar_trade",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 7,
                    "SetList": ("choam_module",),
                    "Tags": ("WantContractX",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.uprising.interstellar_trade_reveal",
                        "ability.activated.acquire",
                        "ability.activated.gain_any_influence_agent",
                        "ability.play.original.interstellar_trade",
                        "ability.triggered.uprising.interstellar_trade_triggered",
                    ),
                }
            ),
        ),
        "imperium.uprising.junction_headquarters": Archetype(
            short="imperium.uprising.junction_headquarters",
            kind="imperium",
            title="Junction Headquarters",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.6,
                    "ArchID": "imperium.uprising.junction_headquarters",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 6,
                    "SetList": ("uprising",),
                    "Tags": ("SpacingGuildAlliance",),
                    "Troops": 1,
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.junction_headquarters",
                    ),
                }
            ),
        ),
        "imperium.uprising.leadership": Archetype(
            short="imperium.uprising.leadership",
            kind="imperium",
            title="Leadership",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.8,
                    "ArchID": "imperium.uprising.leadership",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 5,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "Tags": ("ConditionalStrength", "WantHooks"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.leadership_agent",
                        "ability.triggered.ix.imperial_bashar_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.long_live_the_fighters": Archetype(
            short="imperium.uprising.long_live_the_fighters",
            kind="imperium",
            title="Long Live the Fighters",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 7.0,
                    "ArchID": "imperium.uprising.long_live_the_fighters",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 7,
                    "SetList": ("uprising",),
                    "Strength": 3,
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.long_live_the_fighters",
                        "ability.activated.uprising.long_live_the_fighters_start",
                    ),
                }
            ),
        ),
        "imperium.uprising.maker_keeper": Archetype(
            short="imperium.uprising.maker_keeper",
            kind="imperium",
            title="Maker Keeper",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.8,
                    "ArchID": "imperium.uprising.maker_keeper",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit", "Fremen"),
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Tags": ("BeneGesseritInfluence", "FremenInfluence"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.maker_keeper_bene_gesserit",
                        "ability.activated.uprising.maker_keeper_fremen",
                    ),
                }
            ),
        ),
        "imperium.uprising.maula_pistol": Archetype(
            short="imperium.uprising.maula_pistol",
            kind="imperium",
            title="Maula Pistol",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.uprising.maula_pistol",
                    "CardCount": 2,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "imperium.uprising.northern_watermaster": Archetype(
            short="imperium.uprising.northern_watermaster",
            kind="imperium",
            title="Northern Watermaster",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.8,
                    "AgentWater": 1,
                    "ArchID": "imperium.uprising.northern_watermaster",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Tags": ("FremenBond",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.triggered.uprising.northern_watermaster_bond",
                    ),
                }
            ),
        ),
        "imperium.uprising.overthrow": Archetype(
            short="imperium.uprising.overthrow",
            kind="imperium",
            title="Overthrow",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Intrigue",),
                    "AcquireValue": 8.0,
                    "ArchID": "imperium.uprising.overthrow",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 8,
                    "SetList": ("uprising",),
                    "Strength": 2,
                    "Troops": 1,
                    "AbilityIDs": (
                        "ability.play.original.power_play_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.uprising.paracompass": Archetype(
            short="imperium.uprising.paracompass",
            kind="imperium",
            title="Paracompass",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "AgentSolari": 2,
                    "ArchID": "imperium.uprising.paracompass",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 4,
                    "SetList": ("uprising",),
                    "Tags": ("WantHC",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.uprising.paracompass_reveal",
                        "ability.activated.acquire",
                        "ability.triggered.uprising.paracompass_triggered",
                    ),
                }
            ),
        ),
        "imperium.uprising.prepare_the_way": Archetype(
            short="imperium.uprising.prepare_the_way",
            kind="reserve",
            title="Prepare the Way",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.8,
                    "ArchID": "imperium.uprising.prepare_the_way",
                    "CardCount": 8,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Pentagon", "Circle"),
                    "ImperiumType": "Reserve",
                    "LateMod": 0.9,
                    "Persuasion": 2,
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Tags": ("BeneGesseritInfluence",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.bene_gesserit_influence_draw",
                    ),
                }
            ),
        ),
        "imperium.uprising.price_is_no_object": Archetype(
            short="imperium.uprising.price_is_no_object",
            kind="imperium",
            title="Price Is No Object",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Solari", "Solari"),
                    "AcquireValue": 6.0,
                    "ArchID": "imperium.uprising.price_is_no_object",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "BeneGesserit"),
                    "IconList": ("Emperor", "BeneGesserit"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 6,
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.price_is_no_object",
                    ),
                }
            ),
        ),
        "imperium.uprising.priority_contracts": Archetype(
            short="imperium.uprising.priority_contracts",
            kind="imperium",
            title="Priority Contracts",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.8,
                    "ArchID": "imperium.uprising.priority_contracts",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Pentagon", "Triangle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 6,
                    "SetList": ("choam_module",),
                    "Tags": ("WantContract4", "Contract"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.gain_contract",
                        "ability.activated.uprising.priority_contracts_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.public_spectacle": Archetype(
            short="imperium.uprising.public_spectacle",
            kind="imperium",
            title="Public Spectacle",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.9,
                    "ArchID": "imperium.uprising.public_spectacle",
                    "CardCount": 2,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Spy",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("uprising",),
                    "Tags": ("WantSpy", "Spy", "WantRecall"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.public_spectacle",
                        "ability.activated.uprising.place_spy_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.rebel_supplier": Archetype(
            short="imperium.uprising.rebel_supplier",
            kind="imperium",
            title="Rebel Supplier",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.8,
                    "ArchID": "imperium.uprising.rebel_supplier",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 3,
                    "SetList": ("uprising",),
                    "Spice": 1,
                    "Strength": 1,
                    "Tags": ("WantSpy", "WantRecall"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.rebel_supplier",
                    ),
                }
            ),
        ),
        "imperium.uprising.reliable_informant": Archetype(
            short="imperium.uprising.reliable_informant",
            kind="imperium",
            title="Reliable Informant",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.uprising.reliable_informant",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Solari": 1,
                    "Tags": ("Spy",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.reliable_informant",
                    ),
                }
            ),
        ),
        "imperium.uprising.sardaukar_coordination": Archetype(
            short="imperium.uprising.sardaukar_coordination",
            kind="imperium",
            title="Sardaukar Coordination",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.uprising.sardaukar_coordination",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "Pentagon"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("uprising",),
                    "Tags": ("WantE",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.uprising.sardaukar_coordination_reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.sardaukar_coordination_agent",
                        "ability.play.uprising.sardaukar_coordination_triggered",
                    ),
                }
            ),
        ),
        "imperium.uprising.sardaukar_soldier": Archetype(
            short="imperium.uprising.sardaukar_soldier",
            kind="imperium",
            title="Sardaukar Soldier",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.0,
                    "ArchID": "imperium.uprising.sardaukar_soldier",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.triggered.uprising.sardaukar_soldier",
                    ),
                }
            ),
        ),
        "imperium.uprising.shishakli": Archetype(
            short="imperium.uprising.shishakli",
            kind="imperium",
            title="Shishakli",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.uprising.shishakli",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 4,
                    "SetList": ("uprising",),
                    "Strength": 2,
                    "Tags": ("FremenBond",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.shishakli_agent",
                        "ability.activated.original.crysknife",
                    ),
                }
            ),
        ),
        "imperium.uprising.smugglers_harvester": Archetype(
            short="imperium.uprising.smugglers_harvester",
            kind="imperium",
            title="Smuggler's Harvester",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.0,
                    "ArchID": "imperium.uprising.smugglers_harvester",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.smugglers_harvester",
                    ),
                }
            ),
        ),
        "imperium.uprising.smugglers_haven": Archetype(
            short="imperium.uprising.smugglers_haven",
            kind="imperium",
            title="Smuggler's Haven",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.uprising.smugglers_haven",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.smugglers_haven_agent",
                        "ability.activated.uprising.smugglers_haven_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.southern_elders": Archetype(
            short="imperium.uprising.southern_elders",
            kind="imperium",
            title="Southern Elders",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.7,
                    "ArchID": "imperium.uprising.southern_elders",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit", "Fremen"),
                    "IconList": ("BeneGesserit", "Fremen"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 4,
                    "SetList": ("uprising",),
                    "Tags": ("FremenBond", "WantBG"),
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.activated.uprising.southern_elders_agent",
                        "ability.triggered.uprising.southern_elders_bond",
                        "ability.play.uprising.southern_elders_reveal",
                    ),
                }
            ),
        ),
        "imperium.uprising.spacetime_folding": Archetype(
            short="imperium.uprising.spacetime_folding",
            kind="imperium",
            title="Space-Time Folding",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 0.9,
                    "ArchID": "imperium.uprising.spacetime_folding",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("uprising",),
                    "Tags": ("WantSG",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.spacetime_folding",
                        "ability.activated.uprising.spacing_guild_discard_draw",
                    ),
                }
            ),
        ),
        "imperium.uprising.spacing_guilds_favor": Archetype(
            short="imperium.uprising.spacing_guilds_favor",
            kind="imperium",
            title="Spacing Guild's Favor",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.0,
                    "ArchID": "imperium.uprising.spacing_guilds_favor",
                    "CardCount": 2,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 5,
                    "SetList": ("uprising",),
                    "Tags": ("IncentiveDiscard",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                        "ability.activated.uprising.spacing_guilds_favor_reveal",
                        "ability.triggered.uprising.spacing_guilds_favor_discard",
                    ),
                }
            ),
        ),
        "imperium.uprising.spy_network": Archetype(
            short="imperium.uprising.spy_network",
            kind="imperium",
            title="Spy Network",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("PlaceSpy",),
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.uprising.spy_network",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "SpacingGuild"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "Tags": ("WantSpy", "RecallSpy"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.spy_network",
                    ),
                }
            ),
        ),
        "imperium.uprising.steersman": Archetype(
            short="imperium.uprising.steersman",
            kind="imperium",
            title="Steersman",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("RankSG",),
                    "AcquireValue": 8.0,
                    "ArchID": "imperium.uprising.steersman",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EarlyMod": 1.2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild", "Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 8,
                    "SetList": ("uprising",),
                    "Spice": 2,
                    "Tags": ("RecallAgent",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                        "ability.activated.uprising.recall_agent",
                    ),
                }
            ),
        ),
        "imperium.uprising.stilgar_the_devoted": Archetype(
            short="imperium.uprising.stilgar_the_devoted",
            kind="imperium",
            title="Stilgar, The Devoted",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.7,
                    "AgentTroops": 2,
                    "ArchID": "imperium.uprising.stilgar_the_devoted",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 6,
                    "SetList": ("uprising",),
                    "Tags": ("NamedCharacter",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.activated.acquire",
                        "ability.play.original.liet_kynes_reveal",
                        "ability.play.original.liet_kynes",
                    ),
                }
            ),
        ),
        "imperium.uprising.strike_fleet": Archetype(
            short="imperium.uprising.strike_fleet",
            kind="imperium",
            title="Strike Fleet",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("PlaceSpy",),
                    "AcquireValue": 5.0,
                    "ArchID": "imperium.uprising.strike_fleet",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "IconList": ("Spy",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("uprising",),
                    "Strength": 3,
                    "Tags": ("WantSpy", "WantRecall", "Spy"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.strike_fleet",
                    ),
                }
            ),
        ),
        "imperium.uprising.subversive_advisor": Archetype(
            short="imperium.uprising.subversive_advisor",
            kind="imperium",
            title="Subversive Advisor",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("PlaceSpy",),
                    "AcquireValue": 5.0,
                    "ArchID": "imperium.uprising.subversive_advisor",
                    "CardCount": 1,
                    "EarlyMod": 0.9,
                    "EntityType": "Imperium",
                    "IconList": ("Spy",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("uprising",),
                    "Tags": ("WantSpy", "Spy"),
                    "AbilityIDs": (
                        "ability.play.original.power_play_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.subversive_advisor_trash_self",
                    ),
                }
            ),
        ),
        "imperium.uprising.the_spice_must_flow_up": Archetype(
            short="imperium.uprising.the_spice_must_flow_up",
            kind="reserve",
            title="The Spice Must Flow",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("VP",),
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.uprising.the_spice_must_flow_up",
                    "CardCount": 10,
                    "EarlyMod": 0.75,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "ImperiumType": "Reserve",
                    "LateMod": 1.33,
                    "PersuasionCost": 9,
                    "SetList": ("uprising",),
                    "Spice": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.uprising.treacherous_maneuver": Archetype(
            short="imperium.uprising.treacherous_maneuver",
            kind="imperium",
            title="Treacherous Maneuver",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.6,
                    "ArchID": "imperium.uprising.treacherous_maneuver",
                    "CardCount": 1,
                    "DeferValue": 3,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("uprising",),
                    "Tags": ("WantE",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.original.thufir_hawat_reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.treacherous_maneuver",
                        "ability.activated.reveal_gain_intrigue",
                    ),
                }
            ),
        ),
        "imperium.uprising.treadin_darkness": Archetype(
            short="imperium.uprising.treadin_darkness",
            kind="imperium",
            title="Tread in Darkness",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.uprising.treadin_darkness",
                    "CardCount": 2,
                    "DeferValue": 3,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "Tags": ("WantBG",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.bene_gesserit_trash",
                        "ability.activated.bene_gesserit_draw",
                    ),
                }
            ),
        ),
        "imperium.uprising.truthtrance": Archetype(
            short="imperium.uprising.truthtrance",
            kind="imperium",
            title="Truthtrance",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.0,
                    "ArchID": "imperium.uprising.truthtrance",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Fremen"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "imperium.uprising.undercover_asset": Archetype(
            short="imperium.uprising.undercover_asset",
            kind="imperium",
            title="Undercover Asset",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.uprising.undercover_asset",
                    "CardCount": 1,
                    "EarlyMod": 1.2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "SpacingGuild"),
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Tags": ("Spy",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.original.undercover_asset_reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.undercover_asset",
                    ),
                }
            ),
        ),
        "imperium.uprising.unswerving_loyalty": Archetype(
            short="imperium.uprising.unswerving_loyalty",
            kind="imperium",
            title="Unswerving Loyalty",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 0.9,
                    "ArchID": "imperium.uprising.unswerving_loyalty",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("uprising",),
                    "Tags": ("FremenBond",),
                    "Troops": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.unswerving_loyalty",
                    ),
                }
            ),
        ),
        "imperium.uprising.weirding_woman": Archetype(
            short="imperium.uprising.weirding_woman",
            kind="imperium",
            title="Weirding Woman",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 0.8,
                    "ArchID": "imperium.uprising.weirding_woman",
                    "CardCount": 2,
                    "EarlyMod": 1.2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("uprising",),
                    "Strength": 1,
                    "Tags": ("WantBG",),
                    "AbilityIDs": (
                        "ability.play.uprising.weirding_woman_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.weirding_woman",
                    ),
                }
            ),
        ),
        "imperium.uprising.wheels_within_wheels": Archetype(
            short="imperium.uprising.wheels_within_wheels",
            kind="imperium",
            title="Wheels Within Wheels",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.8,
                    "ArchID": "imperium.uprising.wheels_within_wheels",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "SpacingGuild"),
                    "IconList": ("Spy",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("uprising",),
                    "Tags": (
                        "EmperorInfluence",
                        "SpacingGuildInfluence",
                        "Spy",
                        "WantSpy",
                    ),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.uprising.wheels_within_wheels_emperor",
                        "ability.activated.uprising.wheels_within_wheels_spacing_guild",
                        "ability.activated.uprising.place_spy_reveal",
                    ),
                }
            ),
        ),
        "intrigue.original.allied_armada": Archetype(
            short="intrigue.original.allied_armada",
            kind="intrigue",
            title="Allied Armada",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.allied_armada",
                    "CardCount": 1,
                    "CombatValue": 8.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 1,
                    "SetList": ("original",),
                    "Strength": 7,
                    "AbilityIDs": ("ability.play.original.allied_armada",),
                }
            ),
        ),
        "intrigue.original.ambush": Archetype(
            short="intrigue.original.ambush",
            kind="intrigue",
            title="Ambush",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.ambush",
                    "CardCount": 2,
                    "CombatValue": 5.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 5,
                    "SetList": ("original",),
                    "Strength": 4,
                    "AbilityIDs": ("ability.play.original.ambush",),
                }
            ),
        ),
        "intrigue.original.bindu_suspension": Archetype(
            short="intrigue.original.bindu_suspension",
            kind="intrigue",
            title="Bindu Suspension",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.bindu_suspension",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.bindu_suspension",),
                }
            ),
        ),
        "intrigue.original.bribery": Archetype(
            short="intrigue.original.bribery",
            kind="intrigue",
            title="Bribery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.bribery",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.bribery",),
                }
            ),
        ),
        "intrigue.original.bypass_protocol": Archetype(
            short="intrigue.original.bypass_protocol",
            kind="intrigue",
            title="Bypass Protocol",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.bypass_protocol",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 5,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.bypass_protocol",),
                }
            ),
        ),
        "intrigue.original.choam_shares": Archetype(
            short="intrigue.original.choam_shares",
            kind="intrigue",
            title="CHOAM Shares",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.choam_shares",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 1,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.choam_shares",),
                }
            ),
        ),
        "intrigue.original.calculated_hire": Archetype(
            short="intrigue.original.calculated_hire",
            kind="intrigue",
            title="Calculated Hire",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.calculated_hire",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.calculated_hire",),
                }
            ),
        ),
        "intrigue.original.charisma": Archetype(
            short="intrigue.original.charisma",
            kind="intrigue",
            title="Charisma",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.charisma",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 5,
                    "SetList": ("original",),
                    "Tags": ("Persuasion",),
                    "AbilityIDs": ("ability.play.original.charisma",),
                }
            ),
        ),
        "intrigue.original.corner_the_market": Archetype(
            short="intrigue.original.corner_the_market",
            kind="intrigue",
            title="Corner<br>the Market",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.corner_the_market",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Endgame",),
                    "Rating": 1,
                    "SetList": ("original",),
                    "Tags": ("ConditionalEndgameVP",),
                    "AbilityIDs": ("ability.play.original.corner_the_market",),
                }
            ),
        ),
        "intrigue.original.councilors_dispensation": Archetype(
            short="intrigue.original.councilors_dispensation",
            kind="intrigue",
            title="Councilor's<br>Dispensation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.councilors_dispensation",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("original",),
                    "Tags": ("WantHC",),
                    "AbilityIDs": ("ability.play.original.councilors_dispensation",),
                }
            ),
        ),
        "intrigue.original.demand_respect": Archetype(
            short="intrigue.original.demand_respect",
            kind="intrigue",
            title="Demand Respect",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.demand_respect",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 3,
                    "SetList": ("original",),
                    "Tags": ("Victory",),
                    "AbilityIDs": ("ability.play.original.demand_respect",),
                }
            ),
        ),
        "intrigue.original.dispatchan_envoy": Archetype(
            short="intrigue.original.dispatchan_envoy",
            kind="intrigue",
            title="Dispatch an<br>Envoy",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.dispatchan_envoy",
                    "CardCount": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 4,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.dispatch_an_envoy",),
                }
            ),
        ),
        "intrigue.original.double_cross": Archetype(
            short="intrigue.original.double_cross",
            kind="intrigue",
            title="Double Cross",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.double_cross",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.double_cross",),
                }
            ),
        ),
        "intrigue.original.favored_subject": Archetype(
            short="intrigue.original.favored_subject",
            kind="intrigue",
            title="Favored Subject",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.favored_subject",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "FactionInfluence": {"Emperor": 1},
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 4,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.favored_subject",),
                }
            ),
        ),
        "intrigue.original.guild_authorization": Archetype(
            short="intrigue.original.guild_authorization",
            kind="intrigue",
            title="Guild<br>Authorization",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.guild_authorization",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 5,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.guild_authorization",),
                }
            ),
        ),
        "intrigue.original.infiltrate": Archetype(
            short="intrigue.original.infiltrate",
            kind="intrigue",
            title="Infiltrate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.infiltrate",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 1,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.infiltrate",),
                }
            ),
        ),
        "intrigue.original.know_their_ways": Archetype(
            short="intrigue.original.know_their_ways",
            kind="intrigue",
            title="Know Their Ways",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.know_their_ways",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "FactionInfluence": {"Fremen": 1},
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 4,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.know_their_ways",),
                }
            ),
        ),
        "intrigue.original.master_tactician": Archetype(
            short="intrigue.original.master_tactician",
            kind="intrigue",
            title="Master Tactician",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.master_tactician",
                    "CardCount": 3,
                    "CombatValue": 4.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 4,
                    "SetList": ("original",),
                    "Strength": 3,
                    "AbilityIDs": ("ability.play.original.master_tactician",),
                }
            ),
        ),
        "intrigue.original.plans_within_plans": Archetype(
            short="intrigue.original.plans_within_plans",
            kind="intrigue",
            title="Plans<br>Within Plans",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.plans_within_plans",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Endgame",),
                    "Rating": 1,
                    "SetList": ("original",),
                    "Tags": ("ConditionalEndgameVP",),
                    "AbilityIDs": ("ability.play.original.plans_within_plans",),
                }
            ),
        ),
        "intrigue.original.poison_snooper": Archetype(
            short="intrigue.original.poison_snooper",
            kind="intrigue",
            title="Poison Snooper",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.poison_snooper",
                    "CardCount": 2,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.poison_snooper",),
                }
            ),
        ),
        "intrigue.original.private_army": Archetype(
            short="intrigue.original.private_army",
            kind="intrigue",
            title="Private Army",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.private_army",
                    "CardCount": 2,
                    "CombatValue": 7.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 1,
                    "SetList": ("original",),
                    "Strength": 5,
                    "AbilityIDs": ("ability.play.original.private_army",),
                }
            ),
        ),
        "intrigue.original.rapid_mobilization": Archetype(
            short="intrigue.original.rapid_mobilization",
            kind="intrigue",
            title="Rapid<br>Mobilization",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.rapid_mobilization",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 1,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.rapid_mobilization",),
                }
            ),
        ),
        "intrigue.original.recruitment_mission": Archetype(
            short="intrigue.original.recruitment_mission",
            kind="intrigue",
            title="Recruitment<br>Mission",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.recruitment_mission",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 5,
                    "SetList": ("original",),
                    "Tags": ("Persuasion",),
                    "AbilityIDs": ("ability.play.original.recruitment_mission",),
                }
            ),
        ),
        "intrigue.original.refocus": Archetype(
            short="intrigue.original.refocus",
            kind="intrigue",
            title="Refocus",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.refocus",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.refocus",),
                }
            ),
        ),
        "intrigue.original.reinforcements": Archetype(
            short="intrigue.original.reinforcements",
            kind="intrigue",
            title="Reinforcements",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.reinforcements",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.reinforcements",),
                }
            ),
        ),
        "intrigue.original.secretof_the_sisterhood": Archetype(
            short="intrigue.original.secretof_the_sisterhood",
            kind="intrigue",
            title="Secret of the<br>Sisterhood",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.secretof_the_sisterhood",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "FactionInfluence": {"BeneGesserit": 1},
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 4,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.secret_of_the_sisterhood",),
                }
            ),
        ),
        "intrigue.original.staged_incident": Archetype(
            short="intrigue.original.staged_incident",
            kind="intrigue",
            title="Staged Incident",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.staged_incident",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.staged_incident",),
                }
            ),
        ),
        "intrigue.original.the_sleeper_must_awaken": Archetype(
            short="intrigue.original.the_sleeper_must_awaken",
            kind="intrigue",
            title="The Sleeper <br>Must Awaken",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.the_sleeper_must_awaken",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 1,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.the_sleeper_must_awaken",),
                }
            ),
        ),
        "intrigue.original.tiebreaker": Archetype(
            short="intrigue.original.tiebreaker",
            kind="intrigue",
            title="Tiebreaker",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.tiebreaker",
                    "CardCount": 1,
                    "CombatValue": 2.5,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat", "Endgame"),
                    "Rating": 2,
                    "SetList": ("original",),
                    "Strength": 2,
                    "AbilityIDs": (
                        "ability.play.original.tiebreaker",
                        "ability.play.original.tiebreaker_ability2",
                    ),
                }
            ),
        ),
        "intrigue.original.to_the_victor": Archetype(
            short="intrigue.original.to_the_victor",
            kind="intrigue",
            title="To the Victor...",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.to_the_victor",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 4,
                    "SetList": ("original",),
                    "Tags": ("Victory",),
                    "AbilityIDs": ("ability.play.original.to_the_victor",),
                }
            ),
        ),
        "intrigue.original.urgent_mission": Archetype(
            short="intrigue.original.urgent_mission",
            kind="intrigue",
            title="Urgent Mission",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.urgent_mission",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 5,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.urgent_mission",),
                }
            ),
        ),
        "intrigue.original.water_peddlers_union": Archetype(
            short="intrigue.original.water_peddlers_union",
            kind="intrigue",
            title="Water Peddlers<br>Union",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.water_peddlers_union",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 5,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.water_peddlers_union",),
                }
            ),
        ),
        "intrigue.original.water_of_life": Archetype(
            short="intrigue.original.water_of_life",
            kind="intrigue",
            title="Water of Life",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.water_of_life",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.water_of_life",),
                }
            ),
        ),
        "intrigue.original.windfall": Archetype(
            short="intrigue.original.windfall",
            kind="intrigue",
            title="Windfall",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.original.windfall",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 5,
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.play.original.windfall",),
                }
            ),
        ),
        "intrigue.immortality.breakthrough": Archetype(
            short="intrigue.immortality.breakthrough",
            kind="intrigue",
            title="Breakthrough",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.breakthrough",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("immortality",),
                    "AbilityIDs": ("ability.play.immortality.breakthrough",),
                }
            ),
        ),
        "intrigue.immortality.counterattack": Archetype(
            short="intrigue.immortality.counterattack",
            kind="intrigue",
            title="Counterattack",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.counterattack",
                    "CardCount": 1,
                    "CombatValue": 4.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Combat"),
                    "Rating": 3,
                    "SetList": ("immortality",),
                    "Strength": 4,
                    "AbilityIDs": (
                        "ability.play.immortality.counterattack_plot",
                        "ability.play.immortality.counterattack_combat",
                    ),
                }
            ),
        ),
        "intrigue.immortality.disguised_bureaucrat": Archetype(
            short="intrigue.immortality.disguised_bureaucrat",
            kind="intrigue",
            title="Disguised Bureaucrat",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.disguised_bureaucrat",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("immortality",),
                    "Tags": ("Helix", "DoubleHelix"),
                    "AbilityIDs": ("ability.play.immortality.disguised_bureaucrat",),
                }
            ),
        ),
        "intrigue.immortality.economic_positioning": Archetype(
            short="intrigue.immortality.economic_positioning",
            kind="intrigue",
            title="Economic Positioning",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.economic_positioning",
                    "CardCount": 1,
                    "CombatValue": 2.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat", "Endgame"),
                    "Rating": 2,
                    "SetList": ("immortality",),
                    "Tags": ("ConditionalEndgameVP",),
                    "AbilityIDs": (
                        "ability.play.immortality.economic_positioning_combat",
                        "ability.play.immortality.economic_positioning_endgame",
                    ),
                }
            ),
        ),
        "intrigue.immortality.gruesome_sacrifice": Archetype(
            short="intrigue.immortality.gruesome_sacrifice",
            kind="intrigue",
            title="Gruesome Sacrifice",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.gruesome_sacrifice",
                    "CardCount": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("immortality",),
                    "Tags": ("Shadow",),
                    "AbilityIDs": ("ability.play.immortality.gruesome_sacrifice",),
                }
            ),
        ),
        "intrigue.immortality.harvest_cells": Archetype(
            short="intrigue.immortality.harvest_cells",
            kind="intrigue",
            title="Harvest Cells",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.harvest_cells",
                    "CardCount": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 3,
                    "SetList": ("immortality",),
                    "AbilityIDs": ("ability.play.immortality.harvest_cells",),
                }
            ),
        ),
        "intrigue.immortality.illicit_dealings": Archetype(
            short="intrigue.immortality.illicit_dealings",
            kind="intrigue",
            title="Illicit Dealings",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.illicit_dealings",
                    "CardCount": 2,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("immortality",),
                    "Tags": ("Shadow",),
                    "AbilityIDs": ("ability.play.immortality.illicit_dealings",),
                }
            ),
        ),
        "intrigue.immortality.shadowy_bargain": Archetype(
            short="intrigue.immortality.shadowy_bargain",
            kind="intrigue",
            title="Shadowy Bargain",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.shadowy_bargain",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Endgame"),
                    "Rating": 2,
                    "SetList": ("immortality",),
                    "Tags": ("Shadow",),
                    "AbilityIDs": (
                        "ability.play.immortality.shadowy_bargain_plot",
                        "ability.play.immortality.shadowy_bargain_endgame",
                    ),
                }
            ),
        ),
        "intrigue.immortality.study_melange": Archetype(
            short="intrigue.immortality.study_melange",
            kind="intrigue",
            title="Study Melange",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.study_melange",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Endgame"),
                    "Rating": 3,
                    "SetList": ("immortality",),
                    "Tags": ("DoubleHelix", "ConditionalEndgameVP"),
                    "AbilityIDs": (
                        "ability.play.immortality.study_melange_plot",
                        "ability.play.immortality.study_melange_endgame",
                    ),
                }
            ),
        ),
        "intrigue.immortality.tleilaxu_puppet": Archetype(
            short="intrigue.immortality.tleilaxu_puppet",
            kind="intrigue",
            title="Tleilaxu Puppet",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.tleilaxu_puppet",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Endgame"),
                    "Rating": 3,
                    "SetList": ("immortality",),
                    "Tags": ("DoubleHelix", "ConditionalEndgameVP", "WantHC"),
                    "AbilityIDs": (
                        "ability.play.immortality.tleilaxu_puppet_plot",
                        "ability.play.immortality.tleilaxu_puppet_endgame",
                    ),
                }
            ),
        ),
        "intrigue.immortality.vicious_talents": Archetype(
            short="intrigue.immortality.vicious_talents",
            kind="intrigue",
            title="Vicious Talents",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.immortality.vicious_talents",
                    "CardCount": 2,
                    "CombatValue": 3.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 4,
                    "SetList": ("immortality",),
                    "Strength": 6,
                    "Tags": ("Helix", "DoubleHelix"),
                    "AbilityIDs": ("ability.play.immortality.vicious_talents",),
                }
            ),
        ),
        "intrigue.ix.advanced_weaponry": Archetype(
            short="intrigue.ix.advanced_weaponry",
            kind="intrigue",
            title="Advanced Weaponry",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.advanced_weaponry",
                    "CardCount": 1,
                    "CombatValue": 5.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Combat"),
                    "Rating": 3,
                    "SetList": ("ix",),
                    "Strength": 4,
                    "AbilityIDs": (
                        "ability.play.ix.advanced_weaponry_plot",
                        "ability.play.ix.advanced_weaponry_combat",
                    ),
                }
            ),
        ),
        "intrigue.ix.blackmail": Archetype(
            short="intrigue.ix.blackmail",
            kind="intrigue",
            title="Blackmail",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.blackmail",
                    "CardCount": 1,
                    "CombatValue": 6.5,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 1,
                    "SetList": ("ix",),
                    "Strength": 5,
                    "AbilityIDs": ("ability.play.ix.blackmail",),
                }
            ),
        ),
        "intrigue.ix.cannon_turrets": Archetype(
            short="intrigue.ix.cannon_turrets",
            kind="intrigue",
            title="Cannon Turrets",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.cannon_turrets",
                    "CardCount": 1,
                    "CombatValue": 4.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 3,
                    "SetList": ("ix",),
                    "Strength": 2,
                    "AbilityIDs": ("ability.play.ix.cannon_turrets",),
                }
            ),
        ),
        "intrigue.ix.cull": Archetype(
            short="intrigue.ix.cull",
            kind="intrigue",
            title="Cull",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.cull",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("ix",),
                    "AbilityIDs": ("ability.play.ix.cull",),
                }
            ),
        ),
        "intrigue.ix.diversion": Archetype(
            short="intrigue.ix.diversion",
            kind="intrigue",
            title="Diversion",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.diversion",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 4,
                    "SetList": ("ix",),
                    "Tags": ("Freighter",),
                    "AbilityIDs": ("ability.play.ix.diversion",),
                }
            ),
        ),
        "intrigue.ix.expedite": Archetype(
            short="intrigue.ix.expedite",
            kind="intrigue",
            title="Expedite",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.expedite",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("ix",),
                    "Tags": ("Freighter",),
                    "AbilityIDs": ("ability.play.ix.expedite",),
                }
            ),
        ),
        "intrigue.ix.finesse": Archetype(
            short="intrigue.ix.finesse",
            kind="intrigue",
            title="Finesse",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.finesse",
                    "CardCount": 1,
                    "CombatValue": 2.0,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Combat"),
                    "Rating": 3,
                    "SetList": ("ix",),
                    "Strength": 2,
                    "AbilityIDs": (
                        "ability.play.ix.finesse_plot",
                        "ability.play.ix.finesse_combat",
                    ),
                }
            ),
        ),
        "intrigue.ix.glimpse_the_path": Archetype(
            short="intrigue.ix.glimpse_the_path",
            kind="intrigue",
            title="Glimpse the Path",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.glimpse_the_path",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("ix",),
                    "AbilityIDs": ("ability.play.ix.glimpse_the_path",),
                }
            ),
        ),
        "intrigue.ix.grand_conspiracy": Archetype(
            short="intrigue.ix.grand_conspiracy",
            kind="intrigue",
            title="Grand Conspiracy",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.grand_conspiracy",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Endgame",),
                    "Rating": 1,
                    "SetList": ("ix",),
                    "Tags": ("ConditionalEndgameVP", "WantHC", "WantTSMF"),
                    "AbilityIDs": ("ability.play.ix.grand_conspiracy",),
                }
            ),
        ),
        "intrigue.ix.ixian_probe": Archetype(
            short="intrigue.ix.ixian_probe",
            kind="intrigue",
            title="Ixian Probe",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.ixian_probe",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("ix",),
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": ("ability.play.ix.ixian_probe",),
                }
            ),
        ),
        "intrigue.ix.machine_culture": Archetype(
            short="intrigue.ix.machine_culture",
            kind="intrigue",
            title="Machine Culture",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.machine_culture",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Endgame"),
                    "Rating": 2,
                    "SetList": ("ix",),
                    "Tags": ("BuyTech", "ConditionalEndgameVP"),
                    "AbilityIDs": (
                        "ability.play.ix.machine_culture_plot",
                        "ability.play.ix.machine_culture_endgame",
                    ),
                }
            ),
        ),
        "intrigue.ix.quid_pro_quo": Archetype(
            short="intrigue.ix.quid_pro_quo",
            kind="intrigue",
            title="Quid Pro Quo",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.quid_pro_quo",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 1,
                    "SetList": ("ix",),
                    "AbilityIDs": ("ability.play.ix.quid_pro_quo",),
                }
            ),
        ),
        "intrigue.ix.second_wave": Archetype(
            short="intrigue.ix.second_wave",
            kind="intrigue",
            title="Second Wave",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.second_wave",
                    "CardCount": 1,
                    "CombatValue": 7.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 4,
                    "SetList": ("ix",),
                    "Strength": 2,
                    "AbilityIDs": ("ability.play.ix.second_wave",),
                }
            ),
        ),
        "intrigue.ix.secret_forces": Archetype(
            short="intrigue.ix.secret_forces",
            kind="intrigue",
            title="Secret Forces",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.secret_forces",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 4,
                    "SetList": ("ix",),
                    "Tags": ("WantHC",),
                    "AbilityIDs": ("ability.play.ix.secret_forces",),
                }
            ),
        ),
        "intrigue.ix.strategic_push": Archetype(
            short="intrigue.ix.strategic_push",
            kind="intrigue",
            title="Strategic Push",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.strategic_push",
                    "CardCount": 1,
                    "CombatValue": 0.5,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 4,
                    "SetList": ("ix",),
                    "Strength": 2,
                    "AbilityIDs": ("ability.play.ix.strategic_push",),
                }
            ),
        ),
        "intrigue.ix.strongarm": Archetype(
            short="intrigue.ix.strongarm",
            kind="intrigue",
            title="Strongarm",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.strongarm",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("ix",),
                    "AbilityIDs": ("ability.play.ix.strongarm",),
                }
            ),
        ),
        "intrigue.ix.war_chest": Archetype(
            short="intrigue.ix.war_chest",
            kind="intrigue",
            title="War Chest",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.ix.war_chest",
                    "CardCount": 1,
                    "CombatValue": 3.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat", "Endgame"),
                    "Rating": 1,
                    "SetList": ("ix",),
                    "Strength": 4,
                    "Tags": ("ConditionalEndgameVP",),
                    "AbilityIDs": (
                        "ability.play.ix.war_chest_combat",
                        "ability.play.ix.war_chest_endgame",
                    ),
                }
            ),
        ),
        "intrigue.uprising.backed_by_choam": Archetype(
            short="intrigue.uprising.backed_by_choam",
            kind="intrigue",
            title="Backed by CHOAM",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.backed_by_choam",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Combat"),
                    "Rating": 3,
                    "SetList": ("choam_module",),
                    "Strength": 4,
                    "Tags": ("WantContract2",),
                    "AbilityIDs": (
                        "ability.play.original.backed_by_choam_plot",
                        "ability.play.original.backed_by_choam_combat",
                    ),
                }
            ),
        ),
        "intrigue.uprising.buy_access": Archetype(
            short="intrigue.uprising.buy_access",
            kind="intrigue",
            title="Buy Access",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.buy_access",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "AbilityIDs": ("ability.play.uprising.buy_access",),
                }
            ),
        ),
        "intrigue.uprising.choam_profits": Archetype(
            short="intrigue.uprising.choam_profits",
            kind="intrigue",
            title="CHOAM Profits",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.choam_profits",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Endgame",),
                    "Rating": 2,
                    "SetList": ("choam_module",),
                    "Tags": ("WantContract4", "ConditionalEndgameVP"),
                    "AbilityIDs": ("ability.play.uprising.choam_profits",),
                }
            ),
        ),
        "intrigue.uprising.call_to_arms": Archetype(
            short="intrigue.uprising.call_to_arms",
            kind="intrigue",
            title="Call to Arms",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.call_to_arms",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "AbilityIDs": ("ability.play.original.call_to_arms",),
                }
            ),
        ),
        "intrigue.uprising.change_allegiances": Archetype(
            short="intrigue.uprising.change_allegiances",
            kind="intrigue",
            title="Change Allegiances",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.change_allegiances",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "AbilityIDs": ("ability.play.original.change_allegiances",),
                }
            ),
        ),
        "intrigue.uprising.contingency_plan": Archetype(
            short="intrigue.uprising.contingency_plan",
            kind="intrigue",
            title="Contingency Plan",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.contingency_plan",
                    "CardCount": 3,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Combat"),
                    "Rating": 4,
                    "SetList": ("uprising",),
                    "Strength": 3,
                    "AbilityIDs": (
                        "ability.play.original.contingency_plan_plot",
                        "ability.play.uprising.contingency_plan_combat",
                    ),
                }
            ),
        ),
        "intrigue.uprising.councilors_ambition": Archetype(
            short="intrigue.uprising.councilors_ambition",
            kind="intrigue",
            title="Councilor's Ambition",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.councilors_ambition",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Tags": ("WantHC",),
                    "AbilityIDs": ("ability.play.original.councilors_ambition",),
                }
            ),
        ),
        "intrigue.uprising.crysknife_intrigue": Archetype(
            short="intrigue.uprising.crysknife_intrigue",
            kind="intrigue",
            title="Crysknife",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.crysknife_intrigue",
                    "BattleIcon": "Crysknife",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Endgame"),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.play.original.gain_spice_intrigue",
                        "ability.play.uprising.complete_battle_icon_pair_endgame",
                    ),
                }
            ),
        ),
        "intrigue.uprising.cunning": Archetype(
            short="intrigue.uprising.cunning",
            kind="intrigue",
            title="Cunning",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.cunning",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.play.uprising.cunning",
                        "ability.play.uprising.cunning_trash",
                    ),
                }
            ),
        ),
        "intrigue.uprising.depart_for_arrakis": Archetype(
            short="intrigue.uprising.depart_for_arrakis",
            kind="intrigue",
            title="Depart for Arrakis",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.depart_for_arrakis",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Tags": ("SpacingGuildInfluence",),
                    "AbilityIDs": ("ability.play.original.depart_for_arrakis",),
                }
            ),
        ),
        "intrigue.uprising.desert_mouse": Archetype(
            short="intrigue.uprising.desert_mouse",
            kind="intrigue",
            title="Desert Mouse",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.desert_mouse",
                    "BattleIcon": "DesertMouse",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Endgame"),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.play.original.gain_spice_intrigue",
                        "ability.play.uprising.complete_battle_icon_pair_endgame",
                    ),
                }
            ),
        ),
        "intrigue.uprising.detonation": Archetype(
            short="intrigue.uprising.detonation",
            kind="intrigue",
            title="Detonation",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.detonation",
                    "CardCount": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Tags": ("BlowWall",),
                    "AbilityIDs": ("ability.play.original.detonation",),
                }
            ),
        ),
        "intrigue.uprising.devour": Archetype(
            short="intrigue.uprising.devour",
            kind="intrigue",
            title="Devour",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.devour",
                    "CardCount": 1,
                    "CombatValue": 2.0,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Strength": 4,
                    "Tags": ("WantHooks",),
                    "AbilityIDs": ("ability.play.uprising.devour",),
                }
            ),
        ),
        "intrigue.uprising.distraction": Archetype(
            short="intrigue.uprising.distraction",
            kind="intrigue",
            title="Distraction",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.distraction",
                    "CardCount": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Tags": ("Spy",),
                    "AbilityIDs": ("ability.play.uprising.distraction",),
                }
            ),
        ),
        "intrigue.uprising.find_weakness": Archetype(
            short="intrigue.uprising.find_weakness",
            kind="intrigue",
            title="Find Weakness",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.find_weakness",
                    "CardCount": 1,
                    "CombatValue": 2.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Strength": 5,
                    "Tags": ("WantSpy", "RecallSpy"),
                    "AbilityIDs": ("ability.play.uprising.find_weakness",),
                }
            ),
        ),
        "intrigue.uprising.go_to_ground": Archetype(
            short="intrigue.uprising.go_to_ground",
            kind="intrigue",
            title="Go to Ground",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.go_to_ground",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Tags": ("Spy",),
                    "AbilityIDs": ("ability.play.uprising.go_to_ground",),
                }
            ),
        ),
        "intrigue.uprising.imperium_politics": Archetype(
            short="intrigue.uprising.imperium_politics",
            kind="intrigue",
            title="Imperium Politics",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.imperium_politics",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 4,
                    "SetList": ("uprising",),
                    "AbilityIDs": ("ability.play.uprising.imperium_politics",),
                }
            ),
        ),
        "intrigue.uprising.impress": Archetype(
            short="intrigue.uprising.impress",
            kind="intrigue",
            title="Impress",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.impress",
                    "CardCount": 1,
                    "CombatValue": 2.0,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Strength": 2,
                    "AbilityIDs": ("ability.play.uprising.impress",),
                }
            ),
        ),
        "intrigue.uprising.inspire_awe": Archetype(
            short="intrigue.uprising.inspire_awe",
            kind="intrigue",
            title="Inspire Awe",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.inspire_awe",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Tags": ("WantHooks",),
                    "AbilityIDs": ("ability.play.uprising.inspire_awe",),
                }
            ),
        ),
        "intrigue.uprising.intelligence_report": Archetype(
            short="intrigue.uprising.intelligence_report",
            kind="intrigue",
            title="Intelligence Report",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.intelligence_report",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Tags": ("WantSpy",),
                    "AbilityIDs": ("ability.play.uprising.intelligence_report",),
                }
            ),
        ),
        "intrigue.uprising.leverage": Archetype(
            short="intrigue.uprising.leverage",
            kind="intrigue",
            title="Leverage",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.leverage",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("choam_module",),
                    "Tags": ("Contract",),
                    "AbilityIDs": ("ability.play.original.leverage",),
                }
            ),
        ),
        "intrigue.uprising.manipulate_intrigue": Archetype(
            short="intrigue.uprising.manipulate_intrigue",
            kind="intrigue",
            title="Manipulate",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.manipulate_intrigue",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "AbilityIDs": ("ability.play.uprising.manipulate_up",),
                }
            ),
        ),
        "intrigue.uprising.market_opportunity": Archetype(
            short="intrigue.uprising.market_opportunity",
            kind="intrigue",
            title="Market Opportunity",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.market_opportunity",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "AbilityIDs": ("ability.play.original.market_opportunity",),
                }
            ),
        ),
        "intrigue.uprising.mercenaries": Archetype(
            short="intrigue.uprising.mercenaries",
            kind="intrigue",
            title="Mercenaries",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.mercenaries",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "AbilityIDs": ("ability.play.uprising.mercenaries",),
                }
            ),
        ),
        "intrigue.uprising.opportunism": Archetype(
            short="intrigue.uprising.opportunism",
            kind="intrigue",
            title="Opportunism",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.opportunism",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "AbilityIDs": ("ability.play.uprising.opportunism",),
                }
            ),
        ),
        "intrigue.uprising.ornithopter": Archetype(
            short="intrigue.uprising.ornithopter",
            kind="intrigue",
            title="Ornithopter",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.ornithopter",
                    "BattleIcon": "Ornithopter",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Endgame"),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.play.original.gain_spice_intrigue",
                        "ability.play.uprising.complete_battle_icon_pair_endgame",
                    ),
                }
            ),
        ),
        "intrigue.uprising.questionable_methods": Archetype(
            short="intrigue.uprising.questionable_methods",
            kind="intrigue",
            title="Questionable Methods",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.questionable_methods",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Strength": 5,
                    "AbilityIDs": ("ability.play.uprising.questionable_methods",),
                }
            ),
        ),
        "intrigue.uprising.reach_agreement": Archetype(
            short="intrigue.uprising.reach_agreement",
            kind="intrigue",
            title="Reach Agreement",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.reach_agreement",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("choam_module",),
                    "Tags": ("Contract",),
                    "AbilityIDs": ("ability.play.uprising.reach_agreement",),
                }
            ),
        ),
        "intrigue.uprising.secure_spice_trade": Archetype(
            short="intrigue.uprising.secure_spice_trade",
            kind="intrigue",
            title="Secure Spice Trade",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.secure_spice_trade",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Endgame",),
                    "Rating": 4,
                    "SetList": ("uprising",),
                    "Tags": ("WantTSMF", "ConditionalEndgameVP"),
                    "AbilityIDs": ("ability.play.uprising.secure_spice_trade",),
                }
            ),
        ),
        "intrigue.uprising.shaddams_favor": Archetype(
            short="intrigue.uprising.shaddams_favor",
            kind="intrigue",
            title="Shaddam's Favor",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.shaddams_favor",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Tags": ("EmperorInfluence",),
                    "AbilityIDs": ("ability.play.original.shaddams_favor",),
                }
            ),
        ),
        "intrigue.uprising.shadow_alliance": Archetype(
            short="intrigue.uprising.shadow_alliance",
            kind="intrigue",
            title="Shadow Alliance",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.shadow_alliance",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Endgame",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Tags": ("ConditionalEndgameVP",),
                    "AbilityIDs": ("ability.play.uprising.shadow_alliance",),
                }
            ),
        ),
        "intrigue.uprising.sietch_ritual": Archetype(
            short="intrigue.uprising.sietch_ritual",
            kind="intrigue",
            title="Sietch Ritual",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.sietch_ritual",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "FactionInfluence": {"BeneGesserit": 1},
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": ("ability.play.original.sietch_ritual",),
                }
            ),
        ),
        "intrigue.uprising.special_mission": Archetype(
            short="intrigue.uprising.special_mission",
            kind="intrigue",
            title="Special Mission",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.special_mission",
                    "CardCount": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Tags": ("Spy", "WantSpy", "RecallSpy", "BlowWall"),
                    "AbilityIDs": ("ability.play.uprising.special_mission",),
                }
            ),
        ),
        "intrigue.uprising.spice_is_power": Archetype(
            short="intrigue.uprising.spice_is_power",
            kind="intrigue",
            title="Spice Is Power",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.spice_is_power",
                    "CardCount": 1,
                    "CombatValue": 6.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Strength": 6,
                    "AbilityIDs": ("ability.play.uprising.spice_is_power",),
                }
            ),
        ),
        "intrigue.uprising.spring_the_trap": Archetype(
            short="intrigue.uprising.spring_the_trap",
            kind="intrigue",
            title="Spring the Trap",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.spring_the_trap",
                    "CardCount": 1,
                    "CombatValue": 7.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Strength": 7,
                    "Tags": ("WantSpy", "RecallSpy"),
                    "AbilityIDs": ("ability.play.uprising.spring_the_trap",),
                }
            ),
        ),
        "intrigue.uprising.strategic_stockpiling": Archetype(
            short="intrigue.uprising.strategic_stockpiling",
            kind="intrigue",
            title="Strategic Stockpiling",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.strategic_stockpiling",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("uprising",),
                    "Tags": ("FremenInfluence",),
                    "AbilityIDs": ("ability.play.uprising.strategic_stockpiling",),
                }
            ),
        ),
        "intrigue.uprising.tactical_option": Archetype(
            short="intrigue.uprising.tactical_option",
            kind="intrigue",
            title="Tactical Option",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.tactical_option",
                    "CardCount": 1,
                    "CombatValue": 1.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Strength": 2,
                    "AbilityIDs": ("ability.play.uprising.tactical_option",),
                }
            ),
        ),
        "intrigue.uprising.unexpected_allies": Archetype(
            short="intrigue.uprising.unexpected_allies",
            kind="intrigue",
            title="Unexpected Allies",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.unexpected_allies",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Tags": ("Sandworm", "BlowWall"),
                    "AbilityIDs": ("ability.play.uprising.unexpected_allies",),
                }
            ),
        ),
        "intrigue.uprising.weirding_combat": Archetype(
            short="intrigue.uprising.weirding_combat",
            kind="intrigue",
            title="Weirding Combat",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.uprising.weirding_combat",
                    "CardCount": 1,
                    "CombatValue": 3.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 3,
                    "SetList": ("uprising",),
                    "Strength": 5,
                    "Tags": ("BeneGesseritInfluence",),
                    "AbilityIDs": ("ability.play.uprising.weirding_combat",),
                }
            ),
        ),
        "leader.original.baron_vladimir_harkonnen": Archetype(
            short="leader.original.baron_vladimir_harkonnen",
            kind="leader",
            title="Baron Vladimir Harkonnen",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.original.baron_vladimir_harkonnen",
                    "EntityType": "Leader",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.triggered.original.masterstroke_ability1",
                        "ability.triggered.original.masterstroke_ability2",
                        "ability.activated.original.scheme",
                    ),
                }
            ),
        ),
        "leader.original.count_ilban_richese": Archetype(
            short="leader.original.count_ilban_richese",
            kind="leader",
            title="Count Ilban Richese",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.original.count_ilban_richese",
                    "EntityType": "Leader",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.triggered.original.ruthless_negotiator",
                        "ability.activated.original.manufacturing",
                        "ability.activated.leader_draw",
                    ),
                }
            ),
        ),
        "leader.original.countess_ariana_thorvald": Archetype(
            short="leader.original.countess_ariana_thorvald",
            kind="leader",
            title="Countess Ariana Thorvald",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.original.countess_ariana_thorvald",
                    "EntityType": "Leader",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.triggered.original.spice_addict_ability1",
                        "ability.triggered.original.spice_addict_ability2",
                        "ability.activated.original.hidden_reservoir",
                        "ability.activated.leader_draw",
                    ),
                }
            ),
        ),
        "leader.original.duke_leto_atreides": Archetype(
            short="leader.original.duke_leto_atreides",
            kind="leader",
            title="Duke Leto Atreides",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.original.duke_leto_atreides",
                    "EntityType": "Leader",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.triggered.original.landsraad_popularity",
                        "ability.activated.original.prudent_diplomacy",
                    ),
                }
            ),
        ),
        "leader.original.earl_memnon_thorvald": Archetype(
            short="leader.original.earl_memnon_thorvald",
            kind="leader",
            title="Earl Memnon Thorvald",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.original.earl_memnon_thorvald",
                    "EntityType": "Leader",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.triggered.original.connections",
                        "ability.activated.original.spice_hoard",
                        "ability.activated.original.connections_influence",
                    ),
                }
            ),
        ),
        "leader.original.glossu_the_beast_rabban": Archetype(
            short="leader.original.glossu_the_beast_rabban",
            kind="leader",
            title='Glossu "Beast" Rabban',
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.original.glossu_the_beast_rabban",
                    "EntityType": "Leader",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.triggered.original.arrakis_fiefdom",
                        "ability.activated.original.brutality",
                    ),
                }
            ),
        ),
        "leader.original.helena_richese": Archetype(
            short="leader.original.helena_richese",
            kind="leader",
            title="Helena Richese",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.original.helena_richese",
                    "EntityType": "Leader",
                    "SetList": ("original",),
                    "AbilityIDs": ("ability.activated.original.manipulate",),
                }
            ),
        ),
        "leader.original.paul_atreides": Archetype(
            short="leader.original.paul_atreides",
            kind="leader",
            title="Paul Atreides",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.original.paul_atreides",
                    "EntityType": "Leader",
                    "SetList": ("original",),
                    "AbilityIDs": (
                        "ability.triggered.original.prescience",
                        "ability.activated.original.discipline",
                    ),
                }
            ),
        ),
        "leader.immortality.blank_slate_leader": Archetype(
            short="leader.immortality.blank_slate_leader",
            kind="leader",
            title="Blank Slate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.immortality.blank_slate_leader",
                    "EntityType": "Leader",
                }
            ),
        ),
        "leader.ix.archduke_armand_ecaz": Archetype(
            short="leader.ix.archduke_armand_ecaz",
            kind="leader",
            title="Archduke Armand Ecaz",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.ix.archduke_armand_ecaz",
                    "EntityType": "Leader",
                    "SetList": ("ix",),
                    "AbilityIDs": (
                        "ability.activated.ix.coordination",
                        "ability.activated.ix.conscript",
                    ),
                }
            ),
        ),
        "leader.ix.ilesa_ecaz": Archetype(
            short="leader.ix.ilesa_ecaz",
            kind="leader",
            title="Ilesa Ecaz",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.ix.ilesa_ecaz",
                    "EntityType": "Leader",
                    "SetList": ("ix",),
                    "AbilityIDs": (
                        "ability.activated.ix.guild_contacts",
                        "ability.triggered.ix.one_step_ahead_round",
                        "ability.triggered.ix.one_step_ahead_turn",
                        "ability.triggered.ix.one_step_ahead_send",
                    ),
                }
            ),
        ),
        "leader.ix.prince_rhombur_vernius": Archetype(
            short="leader.ix.prince_rhombur_vernius",
            kind="leader",
            title="Prince Rhombur Vernius",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.ix.prince_rhombur_vernius",
                    "EntityType": "Leader",
                    "SetList": ("ix",),
                    "AbilityIDs": (
                        "ability.triggered.ix.heavy_lasgun_cannons",
                        "ability.activated.ix.ixian_technology",
                    ),
                }
            ),
        ),
        "leader.ix.princess_yuna_moritani": Archetype(
            short="leader.ix.princess_yuna_moritani",
            kind="leader",
            title='"Princess" Yuna Moritani',
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.ix.princess_yuna_moritani",
                    "EntityType": "Leader",
                    "SetList": ("ix",),
                    "AbilityIDs": (
                        "ability.activated.ix.final_delivery",
                        "ability.play.ix.smuggling_operation_solari",
                        "ability.play.ix.smuggling_operation_water",
                    ),
                }
            ),
        ),
        "leader.ix.tessia_vernius": Archetype(
            short="leader.ix.tessia_vernius",
            kind="leader",
            title="Tessia Vernius",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.ix.tessia_vernius",
                    "EntityType": "Leader",
                    "SetList": ("ix",),
                    "AbilityIDs": (
                        "ability.triggered.ix.careful_obeservation_setup",
                        "ability.activated.ix.careful_observation_emperor",
                        "ability.activated.ix.careful_observation_spacing_guild",
                        "ability.activated.ix.careful_observation_bene_gesserit",
                        "ability.activated.ix.careful_observation_fremen",
                        "ability.play.ix.careful_observation_triggered",
                        "ability.play.ix.careful_observation_opp_triggered",
                        "ability.activated.original.duplicity",
                    ),
                }
            ),
        ),
        "leader.ix.viscount_hundro_moritani": Archetype(
            short="leader.ix.viscount_hundro_moritani",
            kind="leader",
            title="Viscount Hundro Moritani",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.ix.viscount_hundro_moritani",
                    "EntityType": "Leader",
                    "SetList": ("ix",),
                    "AbilityIDs": (
                        "ability.activated.ix.couriers",
                        "ability.triggered.ix.intelligence",
                    ),
                }
            ),
        ),
        "leader.uprising.feyd_rautha_harkonnen": Archetype(
            short="leader.uprising.feyd_rautha_harkonnen",
            kind="leader",
            title="Feyd-Rautha Harkonnen",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.feyd_rautha_harkonnen",
                    "EntityType": "Leader",
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.activated.uprising.devious_strength",
                        "ability.triggered.uprising.personal_training_setup",
                        "ability.activated.uprising.personal_training",
                        "ability.activated.uprising.personal_training_trash",
                        "ability.activated.uprising.personal_training_pay_to_trash",
                    ),
                }
            ),
        ),
        "leader.uprising.gurney_halleck_leader": Archetype(
            short="leader.uprising.gurney_halleck_leader",
            kind="leader",
            title="Gurney Halleck",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.gurney_halleck_leader",
                    "EntityType": "Leader",
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.activated.uprising.warmaster",
                        "ability.triggered.uprising.always_smiling",
                    ),
                }
            ),
        ),
        "leader.uprising.lady_amber_metulli": Archetype(
            short="leader.uprising.lady_amber_metulli",
            kind="leader",
            title="Lady Amber Metulli",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.lady_amber_metulli",
                    "EntityType": "Leader",
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.activated.uprising.desert_scouts",
                        "ability.activated.uprising.fill_coffers",
                        "ability.triggered.uprising.fill_coffers_triggered",
                    ),
                }
            ),
        ),
        "leader.uprising.lady_jessica_leader": Archetype(
            short="leader.uprising.lady_jessica_leader",
            kind="leader",
            title="Lady Jessica",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.lady_jessica_leader",
                    "EntityType": "Leader",
                    "LeaderUpgradeArchetypes": (
                        "leader.uprising.reverend_mother_jessica",
                    ),
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.triggered.uprising.other_memories_setup",
                        "ability.activated.uprising.other_memories",
                        "ability.triggered.uprising.other_memories_triggered",
                        "ability.activated.uprising.spice_agony",
                    ),
                }
            ),
        ),
        "leader.uprising.lady_margot_fenring": Archetype(
            short="leader.uprising.lady_margot_fenring",
            kind="leader",
            title="Lady Margot Fenring",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.lady_margot_fenring",
                    "EntityType": "Leader",
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.activated.uprising.arrakis_informant",
                        "ability.triggered.uprising.loyalty",
                    ),
                }
            ),
        ),
        "leader.uprising.muad_dib": Archetype(
            short="leader.uprising.muad_dib",
            kind="leader",
            title="Muad'Dib",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.muad_dib",
                    "EntityType": "Leader",
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.activated.uprising.lead_the_way",
                        "ability.activated.uprising.unpredictable_foe",
                    ),
                }
            ),
        ),
        "leader.uprising.princess_irulan": Archetype(
            short="leader.uprising.princess_irulan",
            kind="leader",
            title="Princess Irulan",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.princess_irulan",
                    "EntityType": "Leader",
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.triggered.uprising.imperial_birthright",
                        "ability.activated.uprising.imperial_birthright_deferred",
                        "ability.activated.uprising.chroniclers_insight",
                        "ability.activated.uprising.chroniclers_insight_acquire",
                    ),
                }
            ),
        ),
        "leader.uprising.reverend_mother_jessica": Archetype(
            short="leader.uprising.reverend_mother_jessica",
            kind="other",
            title="Reverend Mother Jessica",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.reverend_mother_jessica",
                    "EntityType": "LeaderUpgrade",
                    "Flipped": True,
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.activated.uprising.water_of_life_signet",
                        "ability.activated.uprising.reverend_mother",
                    ),
                }
            ),
        ),
        "leader.uprising.shaddam_corrino_iv": Archetype(
            short="leader.uprising.shaddam_corrino_iv",
            kind="leader",
            title="Shaddam Corrino IV",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.shaddam_corrino_iv",
                    "EntityType": "Leader",
                    "SetList": ("choam_module",),
                    "AbilityIDs": (
                        "ability.triggered.uprising.sardaukar_commander",
                        "ability.triggered.uprising.emperor_of_the_known_universe_suppress",
                        "ability.activated.uprising.emperor_of_the_known_universe_signet",
                    ),
                }
            ),
        ),
        "leader.uprising.staban_tuek": Archetype(
            short="leader.uprising.staban_tuek",
            kind="leader",
            title="Staban Tuek",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.uprising.staban_tuek",
                    "EntityType": "Leader",
                    "SetList": ("uprising",),
                    "AbilityIDs": (
                        "ability.triggered.uprising.limited_allies",
                        "ability.triggered.uprising.smuggle_spice",
                        "ability.activated.uprising.unseen_network",
                        "ability.activated.uprising.unseen_network_landsraad",
                        "ability.activated.uprising.unseen_network_influence",
                    ),
                }
            ),
        ),
        "space.original.arrakeen": Archetype(
            short="space.original.arrakeen",
            kind="space",
            title="Arrakeen",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Circle",
                    "ArchID": "space.original.arrakeen",
                    "CombatSpace": True,
                    "ControlSolari": 1,
                    "DeferValue": 1,
                    "EntityType": "Space",
                    "ObservationPosts": (10,),
                    "SetList": ("original", "uprising"),
                    "Tags": ("City",),
                    "Troops": 1,
                    "AbilityIDs": (
                        "ability.activated.deploy_units",
                        "ability.activated.draw",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.original.carthag": Archetype(
            short="space.original.carthag",
            kind="space",
            title="Carthag",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Circle",
                    "ArchID": "space.original.carthag",
                    "CombatSpace": True,
                    "ControlSolari": 1,
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "SetList": ("original",),
                    "Tags": ("City",),
                    "Troops": 1,
                    "AbilityIDs": (
                        "ability.activated.deploy_units",
                        "ability.space.space",
                        "ability.activated.agent_gain_intrigue",
                    ),
                }
            ),
        ),
        "space.original.conspire": Archetype(
            short="space.original.conspire",
            kind="space",
            title="Conspire",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Emperor",
                    "ArchID": "space.original.conspire",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "Faction": "Emperor",
                    "FactionInfluence": {"Emperor": 1},
                    "SetList": ("original",),
                    "Solari": 5,
                    "SpiceCost": 4,
                    "Tags": ("Faction",),
                    "Troops": 2,
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.original.conspire_space",
                        "ability.activated.agent_gain_intrigue",
                    ),
                }
            ),
        ),
        "space.original.foldspace_space": Archetype(
            short="space.original.foldspace_space",
            kind="space",
            title="Foldspace",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "SpacingGuild",
                    "ArchID": "space.original.foldspace_space",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "Faction": "SpacingGuild",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "ReferencedArchetypeIDs": ("imperium.original.foldspace_imperium",),
                    "SetList": ("original",),
                    "Tags": ("Faction",),
                    "AbilityIDs": (
                        "ability.activated.original.foldspace_deferred",
                        "ability.space.space",
                        "ability.space.gain_influence",
                    ),
                }
            ),
        ),
        "space.original.hagga_basin": Archetype(
            short="space.original.hagga_basin",
            kind="space",
            title="Hagga Basin",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.original.hagga_basin",
                    "BonusSpice": 0,
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "SetList": ("original",),
                    "Spice": 2,
                    "Tags": ("Harvest",),
                    "WaterCost": 1,
                    "AbilityIDs": (
                        "ability.activated.deploy_units",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.original.hall_of_oratory": Archetype(
            short="space.original.hall_of_oratory",
            kind="space",
            title="Hall of Oratory",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.original.hall_of_oratory",
                    "EntityType": "Space",
                    "RemovedFromSetList": ("ix",),
                    "SetList": ("original",),
                    "Tags": ("Landsraad",),
                    "Troops": 1,
                    "AbilityIDs": (
                        "ability.triggered.original.hall_of_oratory_ability2",
                        "ability.space.original.hall_of_oratory_space",
                    ),
                }
            ),
        ),
        "space.original.hardy_warriors": Archetype(
            short="space.original.hardy_warriors",
            kind="space",
            title="Hardy Warriors",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Fremen",
                    "ArchID": "space.original.hardy_warriors",
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "Faction": "Fremen",
                    "FactionInfluence": {"Fremen": 1},
                    "SetList": ("original",),
                    "Tags": ("Faction",),
                    "Troops": 2,
                    "WaterCost": 1,
                    "AbilityIDs": (
                        "ability.activated.deploy_units",
                        "ability.space.gain_influence",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.original.heighliner": Archetype(
            short="space.original.heighliner",
            kind="space",
            title="Heighliner",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "SpacingGuild",
                    "ArchID": "space.original.heighliner",
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "Faction": "SpacingGuild",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "SetList": ("original",),
                    "SpiceCost": 6,
                    "Tags": ("Faction",),
                    "Troops": 5,
                    "Water": 2,
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.activated.deploy_units",
                        "ability.space.original.heighliner_space",
                    ),
                }
            ),
        ),
        "space.original.high_council": Archetype(
            short="space.original.high_council",
            kind="space",
            title="High Council",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.original.high_council",
                    "EntityType": "Space",
                    "SetList": ("original",),
                    "SolariCost": 5,
                    "Tags": ("Landsraad",),
                    "AbilityIDs": (
                        "ability.space.original.high_council_space",
                        "ability.triggered.original.high_council_ability2",
                    ),
                }
            ),
        ),
        "space.original.imperial_basin": Archetype(
            short="space.original.imperial_basin",
            kind="space",
            title="Imperial Basin",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.original.imperial_basin",
                    "BonusSpice": 0,
                    "CombatSpace": True,
                    "ControlSpice": 1,
                    "EntityType": "Space",
                    "ObservationPosts": (13,),
                    "SetList": ("original", "uprising"),
                    "Spice": 1,
                    "Tags": ("Harvest",),
                    "AbilityIDs": (
                        "ability.activated.deploy_units",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.original.mentat": Archetype(
            short="space.original.mentat",
            kind="space",
            title="Mentat",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.original.mentat",
                    "DeferValue": 1,
                    "EntityType": "Space",
                    "SetList": ("original",),
                    "SolariCost": 2,
                    "Tags": ("Landsraad",),
                    "AbilityIDs": (
                        "ability.space.original.mentat_space",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "space.original.rally_troops": Archetype(
            short="space.original.rally_troops",
            kind="space",
            title="Rally Troops",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.original.rally_troops",
                    "EntityType": "Space",
                    "RemovedFromSetList": ("ix",),
                    "SetList": ("original",),
                    "SolariCost": 4,
                    "Tags": ("Landsraad",),
                    "Troops": 4,
                    "AbilityIDs": ("ability.space.space",),
                }
            ),
        ),
        "space.original.research_station": Archetype(
            short="space.original.research_station",
            kind="space",
            title="Research Station",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Circle",
                    "ArchID": "space.original.research_station",
                    "CombatSpace": True,
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "RemovedFromSetList": ("immortality",),
                    "SetList": ("original",),
                    "Tags": ("City",),
                    "WaterCost": 2,
                    "AbilityIDs": (
                        "ability.activated.deploy_units",
                        "ability.activated.draw",
                        "ability.activated.draw",
                        "ability.activated.draw",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.original.secrets": Archetype(
            short="space.original.secrets",
            kind="space",
            title="Secrets",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "BeneGesserit",
                    "ArchID": "space.original.secrets",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "Faction": "BeneGesserit",
                    "FactionInfluence": {"BeneGesserit": 1},
                    "ObservationPosts": (3,),
                    "SetList": ("original", "uprising"),
                    "Tags": ("Faction",),
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.original.secrets_space",
                        "ability.activated.agent_gain_intrigue",
                    ),
                }
            ),
        ),
        "space.original.secure_contract": Archetype(
            short="space.original.secure_contract",
            kind="space",
            title="Secure Contract",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.original.secure_contract",
                    "EntityType": "Space",
                    "RemovedFromSetList": ("ix",),
                    "SetList": ("original",),
                    "Solari": 3,
                    "Tags": ("CHOAM",),
                    "AbilityIDs": ("ability.space.space",),
                }
            ),
        ),
        "space.original.selective_breeding": Archetype(
            short="space.original.selective_breeding",
            kind="space",
            title="Selective Breeding",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "BeneGesserit",
                    "ArchID": "space.original.selective_breeding",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "Faction": "BeneGesserit",
                    "FactionInfluence": {"BeneGesserit": 1},
                    "SetList": ("original",),
                    "SpiceCost": 2,
                    "Tags": ("Faction",),
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.space",
                        "ability.activated.original.selective_breeding_deferred",
                    ),
                }
            ),
        ),
        "space.original.sell_melange": Archetype(
            short="space.original.sell_melange",
            kind="space",
            title="Sell Melange",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.original.sell_melange",
                    "EntityType": "Space",
                    "RemovedFromSetList": ("ix",),
                    "SetList": ("original",),
                    "Tags": ("CHOAM",),
                    "AbilityIDs": ("ability.space.original.sell_melange_space",),
                }
            ),
        ),
        "space.original.sietch_tabr": Archetype(
            short="space.original.sietch_tabr",
            kind="space",
            title="Sietch Tabr",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Circle",
                    "ArchID": "space.original.sietch_tabr",
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "InfluenceRequirements": ({"Amount": 2, "Faction": "Fremen"},),
                    "SetList": ("original",),
                    "Tags": ("City",),
                    "Troops": 1,
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.space.space",
                        "ability.activated.deploy_units",
                    ),
                }
            ),
        ),
        "space.original.stillsuits": Archetype(
            short="space.original.stillsuits",
            kind="space",
            title="Stillsuits",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Fremen",
                    "ArchID": "space.original.stillsuits",
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "Faction": "Fremen",
                    "FactionInfluence": {"Fremen": 1},
                    "SetList": ("original",),
                    "Tags": ("Faction",),
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.activated.deploy_units",
                        "ability.space.gain_influence",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.original.swordmaster": Archetype(
            short="space.original.swordmaster",
            kind="space",
            title="Swordmaster",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.original.swordmaster",
                    "EntityType": "Space",
                    "SetList": ("original",),
                    "SolariCost": 8,
                    "Tags": ("Landsraad",),
                    "AbilityIDs": ("ability.space.original.swordmaster_space",),
                }
            ),
        ),
        "space.original.the_great_flat": Archetype(
            short="space.original.the_great_flat",
            kind="space",
            title="The Great Flat",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.original.the_great_flat",
                    "BonusSpice": 0,
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "SetList": ("original",),
                    "Spice": 3,
                    "Tags": ("Harvest",),
                    "WaterCost": 2,
                    "AbilityIDs": (
                        "ability.activated.deploy_units",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.original.wealth": Archetype(
            short="space.original.wealth",
            kind="space",
            title="Wealth",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Emperor",
                    "ArchID": "space.original.wealth",
                    "EntityType": "Space",
                    "Faction": "Emperor",
                    "FactionInfluence": {"Emperor": 1},
                    "SetList": ("original",),
                    "Solari": 2,
                    "Tags": ("Faction",),
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.immortality.research_station_immortality": Archetype(
            short="space.immortality.research_station_immortality",
            kind="space",
            title="Research Station",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Circle",
                    "ArchID": "space.immortality.research_station_immortality",
                    "CombatSpace": True,
                    "DeferValue": 3,
                    "EntityType": "Space",
                    "ObservationPosts": (8, 9),
                    "SetList": ("immortality",),
                    "Tags": ("Research",),
                    "WaterCost": 2,
                    "AbilityIDs": (
                        "ability.activated.deploy_units",
                        "ability.activated.draw",
                        "ability.activated.draw",
                        "ability.space.space",
                        "ability.activated.immortality.gain_research_agent",
                    ),
                }
            ),
        ),
        "space.ix.dreadnought_space": Archetype(
            short="space.ix.dreadnought_space",
            kind="space",
            title="Dreadnought",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.ix.dreadnought_space",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "ObservationPosts": (6,),
                    "SetList": ("ix",),
                    "SolariCost": 3,
                    "Tags": ("Landsraad",),
                    "AbilityIDs": (
                        "ability.activated.ix.acquire_tech",
                        "ability.space.ix.dreadnought_space",
                    ),
                }
            ),
        ),
        "space.ix.interstellar_shipping": Archetype(
            short="space.ix.interstellar_shipping",
            kind="space",
            title="Interstellar Shipping",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.ix.interstellar_shipping",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "InfluenceRequirements": (
                        {"Amount": 2, "Faction": "SpacingGuild"},
                    ),
                    "ObservationPosts": (7,),
                    "SetList": ("ix",),
                    "Tags": ("CHOAM",),
                    "AbilityIDs": (
                        "ability.space.ix.interstellar_shipping_space",
                        "ability.activated.ix.freighter_agent",
                        "ability.activated.ix.freighter_agent",
                    ),
                }
            ),
        ),
        "space.ix.smuggling": Archetype(
            short="space.ix.smuggling",
            kind="space",
            title="Smuggling",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.ix.smuggling",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "ObservationPosts": (7,),
                    "SetList": ("ix",),
                    "Solari": 1,
                    "Tags": ("CHOAM",),
                    "AbilityIDs": (
                        "ability.space.ix.smuggling_space",
                        "ability.activated.ix.freighter_agent",
                    ),
                }
            ),
        ),
        "space.ix.tech_negotiation": Archetype(
            short="space.ix.tech_negotiation",
            kind="space",
            title="Tech Negotiation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.ix.tech_negotiation",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "ObservationPosts": (6,),
                    "SetList": ("ix",),
                    "Tags": ("Landsraad",),
                    "AbilityIDs": (
                        "ability.activated.ix.tech_negotiation_deferred",
                        "ability.triggered.ix.tech_negotiation_triggered",
                        "ability.space.ix.tech_negotiation_space",
                    ),
                }
            ),
        ),
        "space.uprising.accept_contract_choam": Archetype(
            short="space.uprising.accept_contract_choam",
            kind="space",
            title="Accept Contract",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.uprising.accept_contract_choam",
                    "DeferValue": 1,
                    "EntityType": "Space",
                    "ObservationPosts": (7,),
                    "RemovedFromSetList": ("ix",),
                    "SetList": ("choam_module",),
                    "Tags": ("Harvest",),
                    "AbilityIDs": (
                        "ability.space.space",
                        "ability.activated.draw",
                        "ability.activated.uprising.gain_contract",
                    ),
                }
            ),
        ),
        "space.uprising.accept_contract_up": Archetype(
            short="space.uprising.accept_contract_up",
            kind="space",
            title="Accept Contract",
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.uprising.accept_contract_up",
                    "DeferValue": 1,
                    "EntityType": "Space",
                    "ObservationPosts": (7,),
                    "RemovedFromSetList": ("ix", "choam_module"),
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "Tags": ("Harvest",),
                    "AbilityIDs": ("ability.space.space", "ability.activated.draw"),
                }
            ),
        ),
        "space.uprising.assembly_hall": Archetype(
            short="space.uprising.assembly_hall",
            kind="space",
            title="Assembly Hall",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.uprising.assembly_hall",
                    "EntityType": "Space",
                    "ObservationPosts": (6,),
                    "RemovedFromSetList": ("ix",),
                    "SetList": ("uprising",),
                    "Tags": ("Landsraad",),
                    "AbilityIDs": (
                        "ability.triggered.uprising.assembly_hall",
                        "ability.space.uprising.assembly_hall_space",
                        "ability.activated.agent_gain_intrigue",
                    ),
                }
            ),
        ),
        "space.uprising.deep_desert": Archetype(
            short="space.uprising.deep_desert",
            kind="space",
            title="Deep Desert",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.uprising.deep_desert",
                    "BonusSpice": 0,
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "ObservationPosts": (11,),
                    "PossibleSpice": 4,
                    "SetList": ("uprising",),
                    "Tags": ("Harvest",),
                    "WaterCost": 3,
                    "AbilityIDs": (
                        "ability.space.uprising.deep_desert_deferred",
                        "ability.activated.deploy_units",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.uprising.deliver_supplies": Archetype(
            short="space.uprising.deliver_supplies",
            kind="space",
            title="Deliver Supplies",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "SpacingGuild",
                    "ArchID": "space.uprising.deliver_supplies",
                    "EntityType": "Space",
                    "Faction": "SpacingGuild",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "ObservationPosts": (2,),
                    "SetList": ("uprising",),
                    "Tags": ("Faction",),
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.uprising.desert_tactics": Archetype(
            short="space.uprising.desert_tactics",
            kind="space",
            title="Desert Tactics",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Fremen",
                    "ArchID": "space.uprising.desert_tactics",
                    "CombatSpace": True,
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "Faction": "Fremen",
                    "FactionInfluence": {"Fremen": 1},
                    "ObservationPosts": (4,),
                    "SetList": ("uprising",),
                    "Tags": ("Faction",),
                    "Troops": 1,
                    "WaterCost": 1,
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.space",
                        "ability.activated.trash_agent",
                        "ability.activated.deploy_units",
                    ),
                }
            ),
        ),
        "space.uprising.dutiful_service_choam": Archetype(
            short="space.uprising.dutiful_service_choam",
            kind="space",
            title="Dutiful Service",
            in_uprising=False,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Emperor",
                    "ArchID": "space.uprising.dutiful_service_choam",
                    "DeferValue": 1,
                    "EntityType": "Space",
                    "Faction": "Emperor",
                    "FactionInfluence": {"Emperor": 1},
                    "ObservationPosts": (1,),
                    "SetList": ("choam_module",),
                    "Tags": ("Faction",),
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.space",
                        "ability.activated.uprising.gain_contract",
                    ),
                }
            ),
        ),
        "space.uprising.dutiful_service_up": Archetype(
            short="space.uprising.dutiful_service_up",
            kind="space",
            title="Dutiful Service",
            in_uprising=True,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Emperor",
                    "ArchID": "space.uprising.dutiful_service_up",
                    "EntityType": "Space",
                    "Faction": "Emperor",
                    "FactionInfluence": {"Emperor": 1},
                    "ObservationPosts": (1,),
                    "RemovedFromSetList": ("choam_module",),
                    "SetList": ("uprising",),
                    "Solari": 2,
                    "Tags": ("Faction",),
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.uprising.espionage": Archetype(
            short="space.uprising.espionage",
            kind="space",
            title="Espionage",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "BeneGesserit",
                    "ArchID": "space.uprising.espionage",
                    "DeferValue": 1,
                    "EntityType": "Space",
                    "Faction": "BeneGesserit",
                    "FactionInfluence": {"BeneGesserit": 1},
                    "ObservationPosts": (3,),
                    "SetList": ("uprising",),
                    "SpiceCost": 1,
                    "Tags": ("Faction",),
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.uprising.espionage_space",
                        "ability.activated.draw",
                        "ability.activated.uprising.place_spy_agent",
                    ),
                }
            ),
        ),
        "space.uprising.fremkit": Archetype(
            short="space.uprising.fremkit",
            kind="space",
            title="Fremkit",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Fremen",
                    "ArchID": "space.uprising.fremkit",
                    "CombatSpace": True,
                    "DeferValue": 1,
                    "EntityType": "Space",
                    "Faction": "Fremen",
                    "FactionInfluence": {"Fremen": 1},
                    "ObservationPosts": (4,),
                    "SetList": ("uprising",),
                    "Tags": ("Faction",),
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.space",
                        "ability.activated.draw",
                        "ability.activated.deploy_units",
                    ),
                }
            ),
        ),
        "space.uprising.gather_support": Archetype(
            short="space.uprising.gather_support",
            kind="space",
            title="Gather Support",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.uprising.gather_support",
                    "EntityType": "Space",
                    "ObservationPosts": (6,),
                    "PossibleSolariCost": 2,
                    "RemovedFromSetList": ("ix",),
                    "SetList": ("uprising",),
                    "Tags": ("Landsraad",),
                    "Troops": 2,
                    "AbilityIDs": ("ability.space.uprising.gather_support",),
                }
            ),
        ),
        "space.uprising.hagga_basin_up": Archetype(
            short="space.uprising.hagga_basin_up",
            kind="space",
            title="Hagga Basin",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.uprising.hagga_basin_up",
                    "BonusSpice": 0,
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "ObservationPosts": (12,),
                    "PossibleSpice": 2,
                    "SetList": ("uprising",),
                    "Tags": ("Harvest",),
                    "WaterCost": 1,
                    "AbilityIDs": (
                        "ability.space.uprising.hagga_basin_uprising_deferred",
                        "ability.activated.deploy_units",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "space.uprising.heighliner_up": Archetype(
            short="space.uprising.heighliner_up",
            kind="space",
            title="Heighliner",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "SpacingGuild",
                    "ArchID": "space.uprising.heighliner_up",
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "Faction": "SpacingGuild",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "ObservationPosts": (2,),
                    "SetList": ("uprising",),
                    "SpiceCost": 5,
                    "Tags": ("Faction",),
                    "Troops": 5,
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.original.heighliner_space",
                        "ability.activated.deploy_units",
                    ),
                }
            ),
        ),
        "space.uprising.high_council_up": Archetype(
            short="space.uprising.high_council_up",
            kind="space",
            title="High Council",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.uprising.high_council_up",
                    "EntityType": "Space",
                    "ObservationPosts": (5,),
                    "SetList": ("uprising",),
                    "SolariCost": 5,
                    "Tags": ("Landsraad",),
                    "AbilityIDs": (
                        "ability.space.original.high_council_space",
                        "ability.triggered.original.high_council_ability2",
                        "ability.space.uprising.high_council_uprising_space",
                        "ability.activated.uprising.high_council_gain_intrigue",
                    ),
                }
            ),
        ),
        "space.uprising.imperial_privilege": Archetype(
            short="space.uprising.imperial_privilege",
            kind="space",
            title="Imperial Privilege",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.uprising.imperial_privilege",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "InfluenceRequirements": ({"Amount": 2, "Faction": "Emperor"},),
                    "ObservationPosts": (5,),
                    "SetList": ("uprising",),
                    "SolariCost": 3,
                    "Tags": ("Landsraad",),
                    "AbilityIDs": (
                        "ability.space.space",
                        "ability.activated.draw",
                        "ability.activated.uprising.imperial_privilege",
                        "ability.activated.uprising.recall_agent",
                    ),
                }
            ),
        ),
        "space.uprising.research_station_up": Archetype(
            short="space.uprising.research_station_up",
            kind="space",
            title="Research Station",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Circle",
                    "ArchID": "space.uprising.research_station_up",
                    "CombatSpace": True,
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "ObservationPosts": (8, 9),
                    "RemovedFromSetList": ("immortality",),
                    "SetList": ("uprising",),
                    "Tags": ("City",),
                    "Troops": 2,
                    "WaterCost": 2,
                    "AbilityIDs": (
                        "ability.space.space",
                        "ability.activated.deploy_units",
                        "ability.activated.draw",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "space.uprising.sardaukar": Archetype(
            short="space.uprising.sardaukar",
            kind="space",
            title="Sardaukar",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Emperor",
                    "ArchID": "space.uprising.sardaukar",
                    "EntityType": "Space",
                    "Faction": "Emperor",
                    "FactionInfluence": {"Emperor": 1},
                    "ObservationPosts": (1,),
                    "SetList": ("uprising",),
                    "SpiceCost": 4,
                    "Tags": ("Faction",),
                    "Troops": 4,
                    "AbilityIDs": (
                        "ability.space.gain_influence",
                        "ability.space.space",
                        "ability.activated.agent_gain_intrigue",
                    ),
                }
            ),
        ),
        "space.uprising.shipping": Archetype(
            short="space.uprising.shipping",
            kind="space",
            title="Shipping",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.uprising.shipping",
                    "DeferValue": 2,
                    "EntityType": "Space",
                    "InfluenceRequirements": (
                        {"Amount": 2, "Faction": "SpacingGuild"},
                    ),
                    "ObservationPosts": (7,),
                    "RemovedFromSetList": ("ix",),
                    "SetList": ("uprising",),
                    "Solari": 5,
                    "SpiceCost": 3,
                    "Tags": ("Harvest",),
                    "AbilityIDs": (
                        "ability.space.space",
                        "ability.activated.gain_any_influence_agent",
                    ),
                }
            ),
        ),
        "space.uprising.sietch_tabr_up": Archetype(
            short="space.uprising.sietch_tabr_up",
            kind="space",
            title="Sietch Tabr",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Circle",
                    "ArchID": "space.uprising.sietch_tabr_up",
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "InfluenceRequirements": ({"Amount": 2, "Faction": "Fremen"},),
                    "ObservationPosts": (8,),
                    "SetList": ("uprising",),
                    "Tags": ("City",),
                    "AbilityIDs": (
                        "ability.space.uprising.sietch_tabr_uprising_deferred_space",
                        "ability.activated.deploy_units",
                        "ability.space.space",
                        "ability.activated.uprising.blow_wall_custom",
                    ),
                }
            ),
        ),
        "space.uprising.spice_refinery": Archetype(
            short="space.uprising.spice_refinery",
            kind="space",
            title="Spice Refinery",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Circle",
                    "ArchID": "space.uprising.spice_refinery",
                    "CombatSpace": True,
                    "ControlSolari": 1,
                    "EntityType": "Space",
                    "ObservationPosts": (9, 10),
                    "SetList": ("uprising",),
                    "Tags": ("City",),
                    "AbilityIDs": (
                        "ability.space.uprising.spice_refinery",
                        "ability.activated.deploy_units",
                    ),
                }
            ),
        ),
        "space.uprising.swordmaster_up": Archetype(
            short="space.uprising.swordmaster_up",
            kind="space",
            title="Swordmaster",
            in_uprising=True,
            in_uprising_choam=True,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Pentagon",
                    "ArchID": "space.uprising.swordmaster_up",
                    "EntityType": "Space",
                    "ObservationPosts": (5,),
                    "SetList": ("uprising",),
                    "SolariCost": 8,
                    "Tags": ("Landsraad",),
                    "AbilityIDs": (
                        "ability.space.uprising.swordmaster_uprising_space",
                    ),
                }
            ),
        ),
        "tech_tile.ix.artillery": Archetype(
            short="tech_tile.ix.artillery",
            kind="other",
            title="Artillery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.0,
                    "ArchID": "tech_tile.ix.artillery",
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 1,
                    "AbilityIDs": ("ability.triggered.ix.artillery",),
                }
            ),
        ),
        "tech_tile.ix.chaumurky": Archetype(
            short="tech_tile.ix.chaumurky",
            kind="other",
            title="Chaumurky",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Intrigue", "Intrigue"),
                    "AcquireValue": 8.0,
                    "ArchID": "tech_tile.ix.chaumurky",
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 4,
                    "Tags": ("HagalTech",),
                    "AbilityIDs": ("ability.activated.chaumurky",),
                }
            ),
        ),
        "tech_tile.ix.detonation_devices": Archetype(
            short="tech_tile.ix.detonation_devices",
            kind="other",
            title="Detonation Devices",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 6.0,
                    "ArchID": "tech_tile.ix.detonation_devices",
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 3,
                    "Tags": ("HagalTech",),
                }
            ),
        ),
        "tech_tile.ix.disposal_facility": Archetype(
            short="tech_tile.ix.disposal_facility",
            kind="other",
            title="Disposal Facility",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Trash",),
                    "AcquireValue": 6.0,
                    "ArchID": "tech_tile.ix.disposal_facility",
                    "EarlyMod": 1.5,
                    "EntityType": "TechTile",
                    "LateMod": 0.0,
                    "SetList": ("ix",),
                    "SpiceCost": 3,
                    "AbilityIDs": (
                        "ability.activated.ix.disposal_facility",
                        "ability.activated.disposal_facility_acquired",
                        "ability.activated.ix.disposal_facility_triggered",
                    ),
                }
            ),
        ),
        "tech_tile.ix.flagship": Archetype(
            short="tech_tile.ix.flagship",
            kind="other",
            title="Flagship",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("VP",),
                    "AcquireValue": 16.0,
                    "ArchID": "tech_tile.ix.flagship",
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 8,
                    "Tags": ("HagalTech",),
                    "AbilityIDs": ("ability.activated.ix.flagship",),
                }
            ),
        ),
        "tech_tile.ix.holoprojectors": Archetype(
            short="tech_tile.ix.holoprojectors",
            kind="other",
            title="Holoprojectors",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 6.0,
                    "ArchID": "tech_tile.ix.holoprojectors",
                    "EarlyMod": 1.1,
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 3,
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": ("ability.activated.ix.holoprojectors",),
                }
            ),
        ),
        "tech_tile.ix.holtzman_engine": Archetype(
            short="tech_tile.ix.holtzman_engine",
            kind="other",
            title="Holtzman Engine",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 12.0,
                    "ArchID": "tech_tile.ix.holtzman_engine",
                    "EarlyMod": 1.2,
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 6,
                    "Tags": ("HagalTech", "ConditionalEndgameVP", "WantTSMF"),
                    "AbilityIDs": (
                        "ability.triggered.ix.holtzman_engine",
                        "ability.activated.ix.holtzman_engine_endgame",
                    ),
                }
            ),
        ),
        "tech_tile.ix.invasion_ships": Archetype(
            short="tech_tile.ix.invasion_ships",
            kind="other",
            title="Invasion Ships",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Troop", "Troop", "Troop", "Troop"),
                    "AcquireValue": 10.0,
                    "ArchID": "tech_tile.ix.invasion_ships",
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 5,
                    "Tags": ("DiscardEnabler", "HagalTech"),
                    "AbilityIDs": ("ability.activated.ix.invasion_ships",),
                }
            ),
        ),
        "tech_tile.ix.memocorders": Archetype(
            short="tech_tile.ix.memocorders",
            kind="other",
            title="Memocorders",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("AnyRank",),
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.ix.memocorders",
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 2,
                    "Tags": ("HagalTech", "ConditionalEndgameVP"),
                    "AbilityIDs": (
                        "ability.activated.memocorders",
                        "ability.conflict.original.memocorders_acquired",
                    ),
                }
            ),
        ),
        "tech_tile.ix.minimic_film": Archetype(
            short="tech_tile.ix.minimic_film",
            kind="other",
            title="Minimic Film",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.ix.minimic_film",
                    "EarlyMod": 1.5,
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 2,
                    "AbilityIDs": ("ability.triggered.ix.minimic_film",),
                }
            ),
        ),
        "tech_tile.ix.restricted_ordnance": Archetype(
            short="tech_tile.ix.restricted_ordnance",
            kind="other",
            title="Restricted Ordnance",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 8.0,
                    "ArchID": "tech_tile.ix.restricted_ordnance",
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 4,
                    "Tags": ("WantHC",),
                    "AbilityIDs": ("ability.triggered.ix.restricted_ordnance",),
                }
            ),
        ),
        "tech_tile.ix.shuttle_fleet": Archetype(
            short="tech_tile.ix.shuttle_fleet",
            kind="other",
            title="Shuttle Fleet",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("AnyTwoDifferentRanks",),
                    "AcquireValue": 12.0,
                    "ArchID": "tech_tile.ix.shuttle_fleet",
                    "EarlyMod": 1.2,
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 6,
                    "Tags": ("HagalTech",),
                    "AbilityIDs": (
                        "ability.triggered.ix.shuttle_fleet",
                        "ability.conflict.original.shuttle_fleet_acquired",
                    ),
                }
            ),
        ),
        "tech_tile.ix.sonic_snoopers": Archetype(
            short="tech_tile.ix.sonic_snoopers",
            kind="other",
            title="Sonic Snoopers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Intrigue",),
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.ix.sonic_snoopers",
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 2,
                    "Tags": ("HagalTech",),
                    "AbilityIDs": (
                        "ability.activated.ix.sonic_snoopers",
                        "ability.conflict.original.gain_intrigue_acquired",
                    ),
                }
            ),
        ),
        "tech_tile.ix.spaceport": Archetype(
            short="tech_tile.ix.spaceport",
            kind="other",
            title="Spaceport",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Imperium", "Imperium"),
                    "AcquireValue": 10.0,
                    "ArchID": "tech_tile.ix.spaceport",
                    "EarlyMod": 1.2,
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 5,
                    "AbilityIDs": (
                        "ability.conflict.original.draw_imperium_acquired",
                        "ability.conflict.original.draw_imperium_acquired",
                    ),
                }
            ),
        ),
        "tech_tile.ix.spy_satellites": Archetype(
            short="tech_tile.ix.spy_satellites",
            kind="other",
            title="Spy Satellites",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 8.0,
                    "ArchID": "tech_tile.ix.spy_satellites",
                    "EntityType": "TechTile",
                    "SetList": ("ix",),
                    "SpiceCost": 4,
                    "Tags": ("HagalTech", "ConditionalEndgameVP"),
                    "AbilityIDs": (
                        "ability.activated.ix.spy_satellites",
                        "ability.activated.spy_satellites_endgame",
                    ),
                }
            ),
        ),
        "tech_tile.ix.training_drones": Archetype(
            short="tech_tile.ix.training_drones",
            kind="other",
            title="Training Drones",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 6.0,
                    "ArchID": "tech_tile.ix.training_drones",
                    "EarlyMod": 1.1,
                    "EntityType": "TechTile",
                    "LateMod": 0.75,
                    "SetList": ("ix",),
                    "SpiceCost": 3,
                    "Tags": ("HagalTech",),
                    "AbilityIDs": ("ability.activated.ix.training_drones",),
                }
            ),
        ),
        "tech_tile.ix.troop_transports": Archetype(
            short="tech_tile.ix.troop_transports",
            kind="other",
            title="Troop Transports",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.ix.troop_transports",
                    "EntityType": "TechTile",
                    "LateMod": 0.75,
                    "SetList": ("ix",),
                    "SpiceCost": 2,
                    "Tags": ("HagalTech",),
                    "AbilityIDs": ("ability.activated.ix.troop_transports",),
                }
            ),
        ),
        "tech_tile.ix.windtraps": Archetype(
            short="tech_tile.ix.windtraps",
            kind="other",
            title="Windtraps",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Water",),
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.ix.windtraps",
                    "EarlyMod": 1.5,
                    "EntityType": "TechTile",
                    "LateMod": 0.5,
                    "SetList": ("ix",),
                    "SpiceCost": 2,
                    "Tags": ("HagalTech",),
                    "AbilityIDs": ("ability.conflict.ix.windtraps",),
                }
            ),
        ),
        "tleilaxu.immortality.beguiling_pheromones": Archetype(
            short="tleilaxu.immortality.beguiling_pheromones",
            kind="other",
            title="Beguiling Pheromones",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.beguiling_pheromones",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 3,
                    "Strength": 1,
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.immortality.graft_agent",
                        "ability.activated.immortality.beguiling_pheromones",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.chairdog": Archetype(
            short="tleilaxu.immortality.chairdog",
            kind="other",
            title="Chairdog",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.chairdog",
                    "CardCount": 1,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 2,
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.immortality.chairdog_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.immortality.graft_agent",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.contaminator": Archetype(
            short="tleilaxu.immortality.contaminator",
            kind="other",
            title="Contaminator",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.contaminator",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Tleilaxu",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 1,
                    "Tags": ("Shadow",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.gain_tleilaxu_influence_agent",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.corrino_genes": Archetype(
            short="tleilaxu.immortality.corrino_genes",
            kind="other",
            title="Corrino Genes",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Solari", "Solari"),
                    "ArchID": "tleilaxu.immortality.corrino_genes",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Tleilaxu",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 1,
                    "Tags": ("WantsGraft", "Shadow"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.corrino_genes",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.face_dancer": Archetype(
            short="tleilaxu.immortality.face_dancer",
            kind="other",
            title="Face Dancer",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.face_dancer",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Tleilaxu",
                    "FactionList": ("Emperor", "SpacingGuild", "Fremen"),
                    "IconList": ("Emperor", "SpacingGuild", "Fremen"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 2,
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.face_dancer_initiate": Archetype(
            short="tleilaxu.immortality.face_dancer_initiate",
            kind="other",
            title="Face Dancer Initiate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.face_dancer_initiate",
                    "CardCount": 1,
                    "EntityType": "Tleilaxu",
                    "FactionList": ("Emperor", "SpacingGuild", "Fremen"),
                    "IconList": ("Emperor", "SpacingGuild", "Fremen"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 1,
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.from_the_tanks": Archetype(
            short="tleilaxu.immortality.from_the_tanks",
            kind="other",
            title="From the Tanks",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentTroops": 2,
                    "ArchID": "tleilaxu.immortality.from_the_tanks",
                    "CardCount": 1,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 2,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.ghola": Archetype(
            short="tleilaxu.immortality.ghola",
            kind="other",
            title="Ghola",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.ghola",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 3,
                    "Strength": 1,
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.immortality.ghola_agent",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.guild_impersonator": Archetype(
            short="tleilaxu.immortality.guild_impersonator",
            kind="other",
            title="Guild Impersonator",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.guild_impersonator",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Tleilaxu",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 2,
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.play.immortality.guild_impersonator",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.industrial_espionage": Archetype(
            short="tleilaxu.immortality.industrial_espionage",
            kind="other",
            title="Industrial Espionage",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.industrial_espionage",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 1,
                    "Tags": ("WantsGraft",),
                    "AbilityIDs": (
                        "ability.play.immortality.specimen_grafted_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.industrial_espionage_research",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.reclaimed_forces": Archetype(
            short="tleilaxu.immortality.reclaimed_forces",
            kind="other",
            title="Reclaimed Forces",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Troop", "Troop", "Shadow"),
                    "ArchID": "tleilaxu.immortality.reclaimed_forces",
                    "CardCount": 1,
                    "EntityType": "Tleilaxu",
                    "ImperiumType": "Reserve",
                    "SetList": ("immortality",),
                    "SpecimenCost": 3,
                    "AbilityIDs": (
                        "ability.activated.immortality.reclaimed_forces_acquire",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.scientific_breakthrough": Archetype(
            short="tleilaxu.immortality.scientific_breakthrough",
            kind="other",
            title="Scientific Breakthrough",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.scientific_breakthrough",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 3,
                    "Strength": 1,
                    "Tags": ("DoubleHelix",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.scientific_breakthrough",
                        "ability.activated.immortality.gain_research_agent",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.slig_farmer": Archetype(
            short="tleilaxu.immortality.slig_farmer",
            kind="other",
            title="Slig Farmer",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.slig_farmer",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 2,
                    "Tags": ("Graft", "Shadow"),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.slig_farmer_solari",
                        "ability.activated.immortality.slig_farmer_tleilaxu",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.stitched_horror": Archetype(
            short="tleilaxu.immortality.stitched_horror",
            kind="other",
            title="Stitched Horror",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.stitched_horror",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 3,
                    "Strength": 1,
                    "Tags": ("Graft", "Shadow"),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.stitched_horror",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.subject_x137": Archetype(
            short="tleilaxu.immortality.subject_x137",
            kind="other",
            title="Subject X-137",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Shadow",),
                    "ArchID": "tleilaxu.immortality.subject_x137",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Pentagon", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 2,
                    "Tags": ("Helix", "Shadow", "NamedCharacter"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.subject_x137",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.tleilaxu_infiltrator": Archetype(
            short="tleilaxu.immortality.tleilaxu_infiltrator",
            kind="other",
            title="Tleilaxu Infiltrator",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.tleilaxu_infiltrator",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Circle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 2,
                    "Tags": ("Graft", "DoubleHelix"),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.draw",
                        "ability.play.immortality.tleilaxu_infiltrator",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.twisted_mentat": Archetype(
            short="tleilaxu.immortality.twisted_mentat",
            kind="other",
            title="Twisted Mentat",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.twisted_mentat",
                    "CardCount": 1,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Pentagon", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "Specimen": 1,
                    "SpecimenCost": 4,
                    "Strength": 1,
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.twisted_mentat",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.unnatural_reflexes": Archetype(
            short="tleilaxu.immortality.unnatural_reflexes",
            kind="other",
            title="Unnatural Reflexes",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.unnatural_reflexes",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 3,
                    "Strength": 1,
                    "Tags": ("Graft", "Helix"),
                    "AbilityIDs": (
                        "ability.play.immortality.graft_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.immortality.unnatural_reflexes",
                        "ability.activated.immortality.unnatural_reflexes",
                    ),
                }
            ),
        ),
        "tleilaxu.immortality.usurp": Archetype(
            short="tleilaxu.immortality.usurp",
            kind="other",
            title="Usurp",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.immortality.usurp",
                    "CardCount": 1,
                    "EntityType": "Tleilaxu",
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "Specimen": 1,
                    "SpecimenCost": 4,
                    "Strength": 1,
                    "Tags": ("Graft",),
                    "AbilityIDs": (
                        "ability.play.immortality.usurp_agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                    ),
                }
            ),
        ),
        "tleilaxu.promo.piter_genius_advisor": Archetype(
            short="tleilaxu.promo.piter_genius_advisor",
            kind="other",
            title="Piter, Genius Advisor",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "tleilaxu.promo.piter_genius_advisor",
                    "CardCount": 1,
                    "EntityType": "Tleilaxu",
                    "IconList": ("Pentagon", "Triangle"),
                    "ImperiumType": "Promo",
                    "Persuasion": 1,
                    "SetList": ("immortality",),
                    "SpecimenCost": 3,
                    "Strength": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.promo.piter_genius_advisor",
                    ),
                }
            ),
        ),
    }
)
