"""The app-style archetypes of the items the Steam app does not have.

Bloodlines (Imperium, Intrigue, Twisted Intrigue and Navigation cards,
Conflict cards, contract tokens, leaders, the Sardaukar Commander and its
Skills, Tech tiles, Tuek's Sietch) and the Arrakeen Scouts lines, built by
docs/app-ai-plan.md §11.3 and the specs docs/app-ai/bloodlines-cards.md,
docs/app-ai/bloodlines-systems.md and docs/app-ai/scouts.md: the app's
attribute names, the printed numbers of our content definitions, and the
hand-authored app values computed by rules fitted on the app's own data.
Kept apart from the app's own (``archetypes.py``); every key is
``<kind>.app_style.<name>``.

Generated data: do not edit by hand.
``SCOUTS_LINES`` maps each Scouts line (``<item id>:<line index>``) to its
archetype; a line whose ability the spec gives a troop count carries it as
``AbilityTroops``.
"""

# ruff: noqa: E501  (generated data: ability class names do not wrap)

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from dune_imperium.agents.app_ai.data.archetypes import Archetype

SYNTHETIC: Final[Mapping[str, Archetype]] = MappingProxyType(
    {
        "auction.app_style.scouts_choam_negotiations_late0": Archetype(
            short="auction.app_style.scouts_choam_negotiations_late0",
            kind="other",
            title="CHOAM Negotiations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_choam_negotiations_late0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "AbilityIDs": ("ability.activated.uprising.gain_contract_custom",),
                }
            ),
        ),
        "auction.app_style.scouts_choam_negotiations_late1": Archetype(
            short="auction.app_style.scouts_choam_negotiations_late1",
            kind="other",
            title="CHOAM Negotiations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_choam_negotiations_late1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.gain_contract_custom",),
                }
            ),
        ),
        "auction.app_style.scouts_choam_negotiations_mid0": Archetype(
            short="auction.app_style.scouts_choam_negotiations_mid0",
            kind="other",
            title="CHOAM Negotiations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_choam_negotiations_mid0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.gain_contract_custom",),
                }
            ),
        ),
        "auction.app_style.scouts_competitive_study_late0": Archetype(
            short="auction.app_style.scouts_competitive_study_late0",
            kind="other",
            title="Competitive Study",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_competitive_study_late0",
                    "EntityType": "ScoutsLine",
                    "Specimen": 1,
                    "AbilityIDs": (
                        "ability.activated.immortality.gain_research_custom",
                    ),
                }
            ),
        ),
        "auction.app_style.scouts_competitive_study_late1": Archetype(
            short="auction.app_style.scouts_competitive_study_late1",
            kind="other",
            title="Competitive Study",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_competitive_study_late1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.activated.immortality.gain_research_custom",
                    ),
                }
            ),
        ),
        "auction.app_style.scouts_competitive_study_mid0": Archetype(
            short="auction.app_style.scouts_competitive_study_mid0",
            kind="other",
            title="Competitive Study",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_competitive_study_mid0",
                    "EntityType": "ScoutsLine",
                    "Specimen": 1,
                    "AbilityIDs": (
                        "ability.activated.immortality.gain_research_custom",
                    ),
                }
            ),
        ),
        "auction.app_style.scouts_highest_bidder_late0": Archetype(
            short="auction.app_style.scouts_highest_bidder_late0",
            kind="other",
            title="To The Highest Bidder",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_highest_bidder_late0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.draw", "ability.activated.draw"),
                }
            ),
        ),
        "auction.app_style.scouts_highest_bidder_late1": Archetype(
            short="auction.app_style.scouts_highest_bidder_late1",
            kind="other",
            title="To The Highest Bidder",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_highest_bidder_late1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.draw",),
                }
            ),
        ),
        "auction.app_style.scouts_highest_bidder_mid0": Archetype(
            short="auction.app_style.scouts_highest_bidder_mid0",
            kind="other",
            title="To The Highest Bidder",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_highest_bidder_mid0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.draw",),
                }
            ),
        ),
        "auction.app_style.scouts_spies_for_hire_late0": Archetype(
            short="auction.app_style.scouts_spies_for_hire_late0",
            kind="other",
            title="Spies for Hire",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_spies_for_hire_late0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "AbilityIDs": ("ability.activated.uprising.place_spy_custom",),
                }
            ),
        ),
        "auction.app_style.scouts_spies_for_hire_late1": Archetype(
            short="auction.app_style.scouts_spies_for_hire_late1",
            kind="other",
            title="Spies for Hire",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_spies_for_hire_late1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.place_spy_custom",),
                }
            ),
        ),
        "auction.app_style.scouts_spies_for_hire_mid0": Archetype(
            short="auction.app_style.scouts_spies_for_hire_mid0",
            kind="other",
            title="Spies for Hire",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_spies_for_hire_mid0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.place_spy_custom",),
                }
            ),
        ),
        "auction.app_style.scouts_treachery_late0": Archetype(
            short="auction.app_style.scouts_treachery_late0",
            kind="other",
            title="Treachery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_treachery_late0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "auction.app_style.scouts_treachery_late1": Archetype(
            short="auction.app_style.scouts_treachery_late1",
            kind="other",
            title="Treachery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_treachery_late1",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "auction.app_style.scouts_treachery_mid0": Archetype(
            short="auction.app_style.scouts_treachery_mid0",
            kind="other",
            title="Treachery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "auction.app_style.scouts_treachery_mid0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "commander.app_style.sardaukar_commander": Archetype(
            short="commander.app_style.sardaukar_commander",
            kind="other",
            title="Sardaukar Commander",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "commander.app_style.sardaukar_commander",
                    "CardCount": 7,
                    "EntityType": "Commander",
                    "SetList": ("bloodlines",),
                    "SolariCost": 2,
                    "Strength": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "conflict.app_style.skirmish_wild": Archetype(
            short="conflict.app_style.skirmish_wild",
            kind="conflict",
            title="Skirmish (Wild)",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.app_style.skirmish_wild",
                    "BattleIcon": "Wildcard",
                    "CardCount": 1,
                    "ConflictLevel": 1,
                    "ConflictRewardArchetypes": (
                        "conflict.app_style.skirmish_wild_first",
                        "conflict.app_style.skirmish_wild_second",
                        "conflict.app_style.skirmish_wild_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("bloodlines",),
                    "Tags": ("BattleIcon",),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.app_style.skirmish_wild_first": Archetype(
            short="conflict.app_style.skirmish_wild_first",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.app_style.skirmish_wild_first",
                    "CustomAbilityIDs": (
                        "ability.conflict.uprising.trash_conflict_custom",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("bloodlines",),
                }
            ),
        ),
        "conflict.app_style.skirmish_wild_second": Archetype(
            short="conflict.app_style.skirmish_wild_second",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.app_style.skirmish_wild_second",
                    "EntityType": "ConflictReward",
                    "SetList": ("bloodlines",),
                    "Solari": 1,
                    "Water": 1,
                }
            ),
        ),
        "conflict.app_style.skirmish_wild_third": Archetype(
            short="conflict.app_style.skirmish_wild_third",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.app_style.skirmish_wild_third",
                    "EntityType": "ConflictReward",
                    "SetList": ("bloodlines",),
                    "Solari": 2,
                }
            ),
        ),
        "conflict.app_style.stormsin_the_south": Archetype(
            short="conflict.app_style.stormsin_the_south",
            kind="conflict",
            title="Storms in the South",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.app_style.stormsin_the_south",
                    "BattleIcon": "Wildcard",
                    "CardCount": 1,
                    "ConflictLevel": 2,
                    "ConflictRewardArchetypes": (
                        "conflict.app_style.stormsin_the_south_first",
                        "conflict.app_style.stormsin_the_south_second",
                        "conflict.app_style.stormsin_the_south_third",
                    ),
                    "EntityType": "Conflict",
                    "SetList": ("bloodlines",),
                    "Tags": ("BattleIcon", "Spy"),
                    "AbilityIDs": (
                        "ability.conflict.uprising.generic_conflict_first",
                        "ability.conflict.uprising.generic_conflict_second",
                        "ability.conflict.uprising.generic_conflict_third",
                    ),
                }
            ),
        ),
        "conflict.app_style.stormsin_the_south_first": Archetype(
            short="conflict.app_style.stormsin_the_south_first",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.app_style.stormsin_the_south_first",
                    "CustomAbilityIDs": (
                        "ability.activated.uprising.place_spy_custom",
                    ),
                    "EntityType": "ConflictReward",
                    "SetList": ("bloodlines",),
                    "Spice": 2,
                }
            ),
        ),
        "conflict.app_style.stormsin_the_south_second": Archetype(
            short="conflict.app_style.stormsin_the_south_second",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.app_style.stormsin_the_south_second",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 2,
                    "SetList": ("bloodlines",),
                    "Solari": 2,
                }
            ),
        ),
        "conflict.app_style.stormsin_the_south_third": Archetype(
            short="conflict.app_style.stormsin_the_south_third",
            kind="conflict_reward",
            title=None,
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "conflict.app_style.stormsin_the_south_third",
                    "EntityType": "ConflictReward",
                    "IntrigueCard": 1,
                    "SetList": ("bloodlines",),
                    "Solari": 2,
                }
            ),
        ),
        "contract.app_style.bloodlines_deliver_supplies": Archetype(
            short="contract.app_style.bloodlines_deliver_supplies",
            kind="contract",
            title="Deliver Supplies",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.app_style.bloodlines_deliver_supplies",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.deliver_supplies",),
                    "SetList": ("bloodlines", "choam_module"),
                    "Solari": 1,
                    "Tags": ("Spy",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.place_spy_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.app_style.bloodlines_earn_any_alliance": Archetype(
            short="contract.app_style.bloodlines_earn_any_alliance",
            kind="contract",
            title="Earn Any Alliance",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.app_style.bloodlines_earn_any_alliance",
                    "CardCount": 1,
                    "ContractType": "Alliance",
                    "EntityType": "Contract",
                    "SetList": ("bloodlines", "choam_module"),
                    "Solari": 2,
                    "Troops": 2,
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.earn_alliance_contract",
                    ),
                }
            ),
        ),
        "contract.app_style.bloodlines_harvest3": Archetype(
            short="contract.app_style.bloodlines_harvest3",
            kind="contract",
            title="Harvest 3+",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.app_style.bloodlines_harvest3",
                    "CardCount": 1,
                    "ContractType": "Harvest",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": (
                        "space.original.imperial_basin",
                        "space.uprising.hagga_basin_up",
                        "space.uprising.deep_desert",
                        "space.app_style.tueks_sietch",
                    ),
                    "SetList": ("bloodlines", "choam_module"),
                    "Solari": 2,
                    "SpiceCost": 3,
                    "Tags": ("Spy",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.harvest3_spy_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.app_style.bloodlines_harvest4": Archetype(
            short="contract.app_style.bloodlines_harvest4",
            kind="contract",
            title="Harvest 4+",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.app_style.bloodlines_harvest4",
                    "CardCount": 1,
                    "ContractType": "Harvest",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": (
                        "space.original.imperial_basin",
                        "space.uprising.hagga_basin_up",
                        "space.uprising.deep_desert",
                        "space.app_style.tueks_sietch",
                    ),
                    "SetList": ("bloodlines", "choam_module"),
                    "Solari": 3,
                    "SpiceCost": 4,
                    "Tags": ("Spy",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.harvest4_spy_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.app_style.bloodlines_high_council": Archetype(
            short="contract.app_style.bloodlines_high_council",
            kind="contract",
            title="High Council",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.app_style.bloodlines_high_council",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.high_council_up",),
                    "SetList": ("bloodlines", "choam_module"),
                    "Tags": ("RecallAgent",),
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.recall_agent_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.app_style.bloodlines_immediate": Archetype(
            short="contract.app_style.bloodlines_immediate",
            kind="contract",
            title="Immediate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.app_style.bloodlines_immediate",
                    "CardCount": 1,
                    "ContractType": "Immediate",
                    "DeferValue": 1,
                    "EntityType": "Contract",
                    "SetList": ("bloodlines", "choam_module"),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.immediate_trash_intrigue_contract",
                    ),
                }
            ),
        ),
        "contract.app_style.bloodlines_secrets": Archetype(
            short="contract.app_style.bloodlines_secrets",
            kind="contract",
            title="Secrets",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.app_style.bloodlines_secrets",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "DeferValue": 1,
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.original.secrets",),
                    "SetList": ("bloodlines", "choam_module"),
                    "Solari": 2,
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.draw1_contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "contract.app_style.bloodlines_spice_refinery": Archetype(
            short="contract.app_style.bloodlines_spice_refinery",
            kind="contract",
            title="Spice Refinery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "contract.app_style.bloodlines_spice_refinery",
                    "CardCount": 1,
                    "ContractType": "Space",
                    "EntityType": "Contract",
                    "ReferencedArchetypeIDs": ("space.uprising.spice_refinery",),
                    "SetList": ("bloodlines", "choam_module"),
                    "Troops": 2,
                    "AbilityIDs": (
                        "ability.activated.uprising.contract.contract",
                        "ability.triggered.uprising.activate_contract_triggered",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_assassination0": Archetype(
            short="event.app_style.scouts_assassination0",
            kind="other",
            title="Assassination",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_assassination0",
                    "EntityType": "ScoutsLine",
                    "Spice": 2,
                    "AbilityIDs": ("ability.app_style.scouts.trash_from_hand_cost",),
                }
            ),
        ),
        "event.app_style.scouts_bene_gesserit_treachery0": Archetype(
            short="event.app_style.scouts_bene_gesserit_treachery0",
            kind="other",
            title="Bene Gesserit Treachery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_bene_gesserit_treachery0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.lose_garrison_troops_cost",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_bene_gesserit_treachery1": Archetype(
            short="event.app_style.scouts_bene_gesserit_treachery1",
            kind="other",
            title="Bene Gesserit Treachery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_bene_gesserit_treachery1",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"BeneGesserit": -1},
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_betrayal0": Archetype(
            short="event.app_style.scouts_betrayal0",
            kind="other",
            title="Betrayal",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_betrayal0",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"BeneGesserit": -1},
                    "AbilityIDs": (
                        "ability.activated.immortality.gain_tleilaxu_influence_custom",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_choam_bargain0": Archetype(
            short="event.app_style.scouts_choam_bargain0",
            kind="other",
            title="CHOAM Bargain",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_choam_bargain0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.draw",),
                }
            ),
        ),
        "event.app_style.scouts_choam_bargain1": Archetype(
            short="event.app_style.scouts_choam_bargain1",
            kind="other",
            title="CHOAM Bargain",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_choam_bargain1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.gain_contract_custom",),
                }
            ),
        ),
        "event.app_style.scouts_change_of_plans0": Archetype(
            short="event.app_style.scouts_change_of_plans0",
            kind="other",
            title="Change of Plans",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_change_of_plans0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.discard_cost",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_covert_assistance0": Archetype(
            short="event.app_style.scouts_covert_assistance0",
            kind="other",
            title="Covert Assistance",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_covert_assistance0",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"BeneGesserit": 1},
                    "AbilityIDs": ("ability.app_style.scouts.recall_spy_cost",),
                }
            ),
        ),
        "event.app_style.scouts_covert_operation0": Archetype(
            short="event.app_style.scouts_covert_operation0",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_covert_operation0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.place_spy_custom",),
                }
            ),
        ),
        "event.app_style.scouts_covert_operation1": Archetype(
            short="event.app_style.scouts_covert_operation1",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_covert_operation1",
                    "EntityType": "ScoutsLine",
                    "Solari": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_covert_operation2": Archetype(
            short="event.app_style.scouts_covert_operation2",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_covert_operation2",
                    "EntityType": "ScoutsLine",
                    "Troops": 3,
                    "AbilityIDs": ("ability.app_style.scouts.discard_cost",),
                }
            ),
        ),
        "event.app_style.scouts_covert_operation3": Archetype(
            short="event.app_style.scouts_covert_operation3",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_covert_operation3",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.gain_lowest_influence",),
                }
            ),
        ),
        "event.app_style.scouts_covert_operation_choam0": Archetype(
            short="event.app_style.scouts_covert_operation_choam0",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_covert_operation_choam0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.place_spy_custom",),
                }
            ),
        ),
        "event.app_style.scouts_covert_operation_choam1": Archetype(
            short="event.app_style.scouts_covert_operation_choam1",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_covert_operation_choam1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.gain_contract_custom",),
                }
            ),
        ),
        "event.app_style.scouts_covert_operation_choam2": Archetype(
            short="event.app_style.scouts_covert_operation_choam2",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_covert_operation_choam2",
                    "EntityType": "ScoutsLine",
                    "Troops": 3,
                    "AbilityIDs": ("ability.app_style.scouts.discard_cost",),
                }
            ),
        ),
        "event.app_style.scouts_covert_operation_choam3": Archetype(
            short="event.app_style.scouts_covert_operation_choam3",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_covert_operation_choam3",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.gain_lowest_influence",),
                }
            ),
        ),
        "event.app_style.scouts_crackdown0": Archetype(
            short="event.app_style.scouts_crackdown0",
            kind="other",
            title="Crackdown",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_crackdown0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.recall_spy_cost",),
                }
            ),
        ),
        "event.app_style.scouts_crackdown1": Archetype(
            short="event.app_style.scouts_crackdown1",
            kind="other",
            title="Crackdown",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_crackdown1",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"Emperor": -1},
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_desert_gift0": Archetype(
            short="event.app_style.scouts_desert_gift0",
            kind="other",
            title="Desert Gift",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_desert_gift0",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"Fremen": 1},
                    "AbilityIDs": ("ability.app_style.scouts.discard_cost",),
                }
            ),
        ),
        "event.app_style.scouts_emperors_tax0": Archetype(
            short="event.app_style.scouts_emperors_tax0",
            kind="other",
            title="The Emperor's Tax",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_emperors_tax0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_emperors_tax1": Archetype(
            short="event.app_style.scouts_emperors_tax1",
            kind="other",
            title="The Emperor's Tax",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_emperors_tax1",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"Emperor": -1},
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_fremen_exchange0": Archetype(
            short="event.app_style.scouts_fremen_exchange0",
            kind="other",
            title="Fremen Exchange",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_fremen_exchange0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.lose_troops_cost",),
                }
            ),
        ),
        "event.app_style.scouts_fremen_exchange1": Archetype(
            short="event.app_style.scouts_fremen_exchange1",
            kind="other",
            title="Fremen Exchange",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_fremen_exchange1",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"Fremen": -1},
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_funeral_rites0": Archetype(
            short="event.app_style.scouts_funeral_rites0",
            kind="other",
            title="Funeral Rites",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_funeral_rites0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.trash_from_hand_cost",),
                }
            ),
        ),
        "event.app_style.scouts_funeral_rites1": Archetype(
            short="event.app_style.scouts_funeral_rites1",
            kind="other",
            title="Funeral Rites",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_funeral_rites1",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"Fremen": -1},
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_gift_of_water0": Archetype(
            short="event.app_style.scouts_gift_of_water0",
            kind="other",
            title="Gift of Water",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_gift_of_water0",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"Fremen": 1},
                    "WaterCost": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_guild_negotiation0": Archetype(
            short="event.app_style.scouts_guild_negotiation0",
            kind="other",
            title="Guild Negotiation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_guild_negotiation0",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "SpiceCost": 1,
                    "AbilityIDs": ("ability.app_style.scouts.discard_cost",),
                }
            ),
        ),
        "event.app_style.scouts_imperium_bene_gesserit_treachery0": Archetype(
            short="event.app_style.scouts_imperium_bene_gesserit_treachery0",
            kind="other",
            title="Bene Gesserit Treachery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_bene_gesserit_treachery0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.discard_cost",),
                }
            ),
        ),
        "event.app_style.scouts_imperium_bene_gesserit_treachery1": Archetype(
            short="event.app_style.scouts_imperium_bene_gesserit_treachery1",
            kind="other",
            title="Bene Gesserit Treachery",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_bene_gesserit_treachery1",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"BeneGesserit": -1},
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_imperium_covert_operation0": Archetype(
            short="event.app_style.scouts_imperium_covert_operation0",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_covert_operation0",
                    "EntityType": "ScoutsLine",
                    "Solari": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_imperium_covert_operation1": Archetype(
            short="event.app_style.scouts_imperium_covert_operation1",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_covert_operation1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.discard_cost",
                        "ability.activated.gain_any_influence_agent",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_imperium_covert_operation2": Archetype(
            short="event.app_style.scouts_imperium_covert_operation2",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_covert_operation2",
                    "EntityType": "ScoutsLine",
                    "Spice": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_imperium_covert_operation3": Archetype(
            short="event.app_style.scouts_imperium_covert_operation3",
            kind="other",
            title="Covert Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_covert_operation3",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.discard_cost",
                        "ability.app_style.scouts.discard_cost",
                        "ability.app_style.scouts.gain_two_influence",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_imperium_gift_of_water0": Archetype(
            short="event.app_style.scouts_imperium_gift_of_water0",
            kind="other",
            title="Gift of Water",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_gift_of_water0",
                    "EntityType": "ScoutsLine",
                    "ReferencedArchetypeIDs": ("imperium.original.arrakis_liaison",),
                    "WaterCost": 1,
                    "AbilityIDs": ("ability.app_style.scouts.acquire_reserve_to_hand",),
                }
            ),
        ),
        "event.app_style.scouts_imperium_guild_negotiation0": Archetype(
            short="event.app_style.scouts_imperium_guild_negotiation0",
            kind="other",
            title="Guild Negotiation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_guild_negotiation0",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"SpacingGuild": 1},
                    "SolariCost": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_imperium_political_equilibrium0": Archetype(
            short="event.app_style.scouts_imperium_political_equilibrium0",
            kind="other",
            title="Political Equilibrium",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_political_equilibrium0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.lose_highest_influence",),
                }
            ),
        ),
        "event.app_style.scouts_imperium_rotating_doors0": Archetype(
            short="event.app_style.scouts_imperium_rotating_doors0",
            kind="other",
            title="Rotating Doors",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_rotating_doors0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "AbilityIDs": ("ability.app_style.scouts.discard_intrigue_cost",),
                }
            ),
        ),
        "event.app_style.scouts_imperium_secrets_for_sale0": Archetype(
            short="event.app_style.scouts_imperium_secrets_for_sale0",
            kind="other",
            title="Secrets for Sale",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_secrets_for_sale0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "SolariCost": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_imperium_secrets_for_sale1": Archetype(
            short="event.app_style.scouts_imperium_secrets_for_sale1",
            kind="other",
            title="Secrets for Sale",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_secrets_for_sale1",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "SpiceCost": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_imperium_water_for_spice_smugglers0": Archetype(
            short="event.app_style.scouts_imperium_water_for_spice_smugglers0",
            kind="other",
            title="Water for Spice Smugglers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_water_for_spice_smugglers0",
                    "EntityType": "ScoutsLine",
                    "WaterCost": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_imperium_water_for_spice_smugglers1": Archetype(
            short="event.app_style.scouts_imperium_water_for_spice_smugglers1",
            kind="other",
            title="Water for Spice Smugglers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_imperium_water_for_spice_smugglers1",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"SpacingGuild": -1},
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_ingratiate0": Archetype(
            short="event.app_style.scouts_ingratiate0",
            kind="other",
            title="Ingratiate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_ingratiate0",
                    "EntityType": "ScoutsLine",
                    "SpecimenCost": 1,
                    "AbilityIDs": ("ability.activated.gain_any_influence_agent",),
                }
            ),
        ),
        "event.app_style.scouts_intriguing_gift0": Archetype(
            short="event.app_style.scouts_intriguing_gift0",
            kind="other",
            title="Intriguing Gift",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_intriguing_gift0",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"BeneGesserit": 1},
                    "AbilityIDs": ("ability.app_style.scouts.discard_intrigue_cost",),
                }
            ),
        ),
        "event.app_style.scouts_market_research0": Archetype(
            short="event.app_style.scouts_market_research0",
            kind="other",
            title="Market Research",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_market_research0",
                    "EntityType": "ScoutsLine",
                    "Spice": 2,
                    "AbilityIDs": ("ability.app_style.scouts.recall_spy_cost",),
                }
            ),
        ),
        "event.app_style.scouts_moment_of_revelation0": Archetype(
            short="event.app_style.scouts_moment_of_revelation0",
            kind="other",
            title="Moment of Revelation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_moment_of_revelation0",
                    "EntityType": "ScoutsLine",
                    "ReferencedArchetypeIDs": ("imperium.uprising.prepare_the_way",),
                    "SpiceCost": 2,
                    "AbilityIDs": ("ability.app_style.scouts.acquire_reserve_to_hand",),
                }
            ),
        ),
        "event.app_style.scouts_new_innovations0": Archetype(
            short="event.app_style.scouts_new_innovations0",
            kind="other",
            title="New Innovations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_new_innovations0",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 1,
                    "AbilityIDs": (
                        "ability.activated.immortality.gain_research_custom",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_new_innovations1": Archetype(
            short="event.app_style.scouts_new_innovations1",
            kind="other",
            title="New Innovations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_new_innovations1",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 1,
                    "AbilityIDs": (
                        "ability.activated.immortality.gain_research_custom",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_no_coming_back0": Archetype(
            short="event.app_style.scouts_no_coming_back0",
            kind="other",
            title="No Coming Back",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_no_coming_back0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.trash_from_hand_cost",
                        "ability.activated.gain_any_influence_agent",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_no_coming_back1": Archetype(
            short="event.app_style.scouts_no_coming_back1",
            kind="other",
            title="No Coming Back",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_no_coming_back1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.trash_from_hand_cost",
                        "ability.app_style.scouts.gain_two_influence",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_no_coming_back2": Archetype(
            short="event.app_style.scouts_no_coming_back2",
            kind="other",
            title="No Coming Back",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_no_coming_back2",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.trash_from_hand_cost",),
                }
            ),
        ),
        "event.app_style.scouts_offworld_operation0": Archetype(
            short="event.app_style.scouts_offworld_operation0",
            kind="other",
            title="Offworld Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_offworld_operation0",
                    "EntityType": "ScoutsLine",
                    "Solari": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_offworld_operation1": Archetype(
            short="event.app_style.scouts_offworld_operation1",
            kind="other",
            title="Offworld Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_offworld_operation1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.helix_spice",),
                }
            ),
        ),
        "event.app_style.scouts_offworld_operation2": Archetype(
            short="event.app_style.scouts_offworld_operation2",
            kind="other",
            title="Offworld Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_offworld_operation2",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.activated.immortality.gain_tleilaxu_influence_custom",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_offworld_operation3": Archetype(
            short="event.app_style.scouts_offworld_operation3",
            kind="other",
            title="Offworld Operation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_offworld_operation3",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_political_equilibrium0": Archetype(
            short="event.app_style.scouts_political_equilibrium0",
            kind="other",
            title="Political Equilibrium",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_political_equilibrium0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.app_style.scouts.lose_highest_influence",),
                }
            ),
        ),
        "event.app_style.scouts_private_stock0": Archetype(
            short="event.app_style.scouts_private_stock0",
            kind="other",
            title="Private Stock",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_private_stock0",
                    "EntityType": "ScoutsLine",
                    "Spice": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_private_stock1": Archetype(
            short="event.app_style.scouts_private_stock1",
            kind="other",
            title="Private Stock",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_private_stock1",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.draw",),
                }
            ),
        ),
        "event.app_style.scouts_rebuild_infrastructure0": Archetype(
            short="event.app_style.scouts_rebuild_infrastructure0",
            kind="other",
            title="Rebuild Infrastructure",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_rebuild_infrastructure0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 1,
                    "AbilityIDs": ("ability.app_style.scouts.shield_wall_return",),
                }
            ),
        ),
        "event.app_style.scouts_rotating_doors0": Archetype(
            short="event.app_style.scouts_rotating_doors0",
            kind="other",
            title="Rotating Doors",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_rotating_doors0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.trash_intrigue_cost",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_royal_delegation0": Archetype(
            short="event.app_style.scouts_royal_delegation0",
            kind="other",
            title="Royal Delegation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_royal_delegation0",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"Emperor": 1},
                    "SolariCost": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_share_intelligence0": Archetype(
            short="event.app_style.scouts_share_intelligence0",
            kind="other",
            title="Share Intelligence",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_share_intelligence0",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.trash_intrigue_cost",
                        "ability.activated.gain_any_influence_agent",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_smoke_and_mirrors0": Archetype(
            short="event.app_style.scouts_smoke_and_mirrors0",
            kind="other",
            title="Smoke and Mirrors",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_smoke_and_mirrors0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.place_spy_custom",),
                }
            ),
        ),
        "event.app_style.scouts_smoke_and_mirrors1": Archetype(
            short="event.app_style.scouts_smoke_and_mirrors1",
            kind="other",
            title="Smoke and Mirrors",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_smoke_and_mirrors1",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "SolariCost": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_termination_request0": Archetype(
            short="event.app_style.scouts_termination_request0",
            kind="other",
            title="Termination Request",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_termination_request0",
                    "EntityType": "ScoutsLine",
                    "Specimen": 1,
                    "AbilityIDs": ("ability.app_style.scouts.trash_from_hand_cost",),
                }
            ),
        ),
        "event.app_style.scouts_test_of_loyalty0": Archetype(
            short="event.app_style.scouts_test_of_loyalty0",
            kind="other",
            title="Test of Loyalty",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_test_of_loyalty0",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"Emperor": 1},
                    "AbilityIDs": (
                        "ability.app_style.scouts.lose_garrison_troops_cost",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_water_discipline0": Archetype(
            short="event.app_style.scouts_water_discipline0",
            kind="other",
            title="Water Discipline",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_water_discipline0",
                    "EntityType": "ScoutsLine",
                    "WaterCost": 1,
                    "AbilityIDs": (
                        "ability.activated.trash_custom",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "event.app_style.scouts_water_for_spice_smugglers0": Archetype(
            short="event.app_style.scouts_water_for_spice_smugglers0",
            kind="other",
            title="Water for Spice Smugglers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_water_for_spice_smugglers0",
                    "EntityType": "ScoutsLine",
                    "WaterCost": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "event.app_style.scouts_water_for_spice_smugglers1": Archetype(
            short="event.app_style.scouts_water_for_spice_smugglers1",
            kind="other",
            title="Water for Spice Smugglers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "event.app_style.scouts_water_for_spice_smugglers1",
                    "EntityType": "ScoutsLine",
                    "FactionInfluence": {"SpacingGuild": -1},
                    "AbilityIDs": (),
                }
            ),
        ),
        "imperium.app_style.arrakis_observer": Archetype(
            short="imperium.app_style.arrakis_observer",
            kind="imperium",
            title="Arrakis Observer",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.app_style.arrakis_observer",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("bloodlines",),
                    "Tags": ("Spy", "WantSpy", "RecallSpy", "WantSG"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.arrakis_observer_agent",
                        "ability.app_style.bloodlines.arrakis_observer_reveal",
                    ),
                }
            ),
        ),
        "imperium.app_style.bombast": Archetype(
            short="imperium.app_style.bombast",
            kind="imperium",
            title="Bombast",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.0,
                    "ArchID": "imperium.app_style.bombast",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.bombast_command",
                    ),
                }
            ),
        ),
        "imperium.app_style.choam_demands": Archetype(
            short="imperium.app_style.choam_demands",
            kind="imperium",
            title="CHOAM Demands",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.8,
                    "ArchID": "imperium.app_style.choam_demands",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 6,
                    "SetList": ("bloodlines", "choam_module"),
                    "Tags": ("WantContract4",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.choam_demands_agent",
                        "ability.app_style.bloodlines.choam_demands_reveal",
                    ),
                }
            ),
        ),
        "imperium.app_style.command_center": Archetype(
            short="imperium.app_style.command_center",
            kind="imperium",
            title="Command Center",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.app_style.command_center",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("bloodlines",),
                    "Tags": ("EmperorInfluence",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.command_center_agent",
                        "ability.app_style.bloodlines.command_center_reveal",
                    ),
                }
            ),
        ),
        "imperium.app_style.corrupt_bureaucrat": Archetype(
            short="imperium.app_style.corrupt_bureaucrat",
            kind="imperium",
            title="Corrupt Bureaucrat",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.app_style.corrupt_bureaucrat",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "IconList": ("SpacingGuild", "Pentagon", "Spy"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("bloodlines", "choam_module"),
                    "Tags": ("WantSpy", "WantRecall", "IncentiveDiscard", "Contract"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.corrupt_bureaucrat_agent",
                        "ability.app_style.bloodlines.corrupt_bureaucrat_discard",
                    ),
                }
            ),
        ),
        "imperium.app_style.delivery_logistics": Archetype(
            short="imperium.app_style.delivery_logistics",
            kind="imperium",
            title="Delivery Logistics",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.app_style.delivery_logistics",
                    "CardCount": 2,
                    "ConditionalIconList": (
                        "Emperor",
                        "SpacingGuild",
                        "BeneGesserit",
                        "Pentagon",
                        "Circle",
                        "Triangle",
                    ),
                    "EntityType": "Imperium",
                    "FactionList": ("SpacingGuild",),
                    "ImperiumType": "Main",
                    "PersuasionCost": 2,
                    "SetList": ("bloodlines", "choam_module"),
                    "Tags": ("Contract", "WantContractX"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.delivery_logistics_reveal",
                    ),
                }
            ),
        ),
        "imperium.app_style.disruption_tactics": Archetype(
            short="imperium.app_style.disruption_tactics",
            kind="imperium",
            title="Disruption Tactics",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.app_style.disruption_tactics",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("bloodlines",),
                    "Tags": ("Combat",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.disruption_tactics_agent",
                        "ability.app_style.bloodlines.disruption_tactics_reveal",
                    ),
                }
            ),
        ),
        "imperium.app_style.eliminate_allies": Archetype(
            short="imperium.app_style.eliminate_allies",
            kind="imperium",
            title="Eliminate Allies",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.app_style.eliminate_allies",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Spy",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("bloodlines",),
                    "Strength": 1,
                    "Tags": ("WantSpy",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.trash_agent",
                        "ability.app_style.bloodlines.eliminate_allies_trash",
                    ),
                }
            ),
        ),
        "imperium.app_style.elite_forces": Archetype(
            short="imperium.app_style.elite_forces",
            kind="imperium",
            title="Elite Forces",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.app_style.elite_forces",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor", "SpacingGuild"),
                    "IconList": ("Emperor", "SpacingGuild"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("bloodlines",),
                    "Strength": 1,
                    "Tags": ("WantE", "Combat"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.elite_forces_agent",
                    ),
                }
            ),
        ),
        "imperium.app_style.engineered_miracle": Archetype(
            short="imperium.app_style.engineered_miracle",
            kind="imperium",
            title="Engineered Miracle",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.app_style.engineered_miracle",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Fremen", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("bloodlines",),
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.engineered_miracle_agent",
                        "ability.app_style.bloodlines.engineered_miracle_command",
                    ),
                }
            ),
        ),
        "imperium.app_style.fremen_war_name": Archetype(
            short="imperium.app_style.fremen_war_name",
            kind="imperium",
            title="Fremen War Name",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.app_style.fremen_war_name",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("bloodlines",),
                    "Tags": ("FremenBond", "ConditionalStrength"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.fremen_war_name_troop",
                        "ability.app_style.bloodlines.fremen_war_name_draw",
                        "ability.app_style.bloodlines.fremen_war_name_bond",
                    ),
                }
            ),
        ),
        "imperium.app_style.holy_war": Archetype(
            short="imperium.app_style.holy_war",
            kind="imperium",
            title="Holy War",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.8,
                    "ArchID": "imperium.app_style.holy_war",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Emperor", "SpacingGuild", "BeneGesserit", "Pentagon"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("bloodlines",),
                    "Tags": ("FremenBond", "Combat"),
                    "Troops": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.holy_war_agent",
                        "ability.app_style.bloodlines.holy_war_bond",
                    ),
                }
            ),
        ),
        "imperium.app_style.i_believe": Archetype(
            short="imperium.app_style.i_believe",
            kind="imperium",
            title="I Believe",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.app_style.i_believe",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("bloodlines",),
                    "Tags": ("DiscardEnabler",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.i_believe_agent",
                        "ability.app_style.bloodlines.i_believe_command",
                    ),
                }
            ),
        ),
        "imperium.app_style.imperial_throneship": Archetype(
            short="imperium.app_style.imperial_throneship",
            kind="imperium",
            title="Imperial Throneship",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("RankE",),
                    "AcquireValue": 6.8,
                    "ArchID": "imperium.app_style.imperial_throneship",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": (
                        "Emperor",
                        "SpacingGuild",
                        "BeneGesserit",
                        "Pentagon",
                        "Circle",
                        "Triangle",
                    ),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 7,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.app_style.bloodlines.imperial_throneship_reveal",
                        "ability.activated.acquire",
                        "ability.activated.agent_gain_intrigue",
                        "ability.app_style.bloodlines.imperial_throneship_triggered",
                    ),
                }
            ),
        ),
        "imperium.app_style.intelligence_training": Archetype(
            short="imperium.app_style.intelligence_training",
            kind="imperium",
            title="Intelligence Training",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("PlaceSpy",),
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.app_style.intelligence_training",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Pentagon", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 3,
                    "SetList": ("bloodlines",),
                    "Strength": 1,
                    "Tags": ("Spy",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.intelligence_training_command",
                        "ability.app_style.bloodlines.acquire_place_spy_bonus",
                    ),
                }
            ),
        ),
        "imperium.app_style.ixian_ambassador": Archetype(
            short="imperium.app_style.ixian_ambassador",
            kind="imperium",
            title="Ixian Ambassador",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "AgentSpice": 1,
                    "ArchID": "imperium.app_style.ixian_ambassador",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "IconList": ("Pentagon",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("bloodlines", "tech_module"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.ixian_ambassador_reveal",
                    ),
                }
            ),
        ),
        "imperium.app_style.litany_against_fear": Archetype(
            short="imperium.app_style.litany_against_fear",
            kind="imperium",
            title="Litany Against Fear",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.0,
                    "ArchID": "imperium.app_style.litany_against_fear",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 3,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.litany_turn_start",
                    ),
                }
            ),
        ),
        "imperium.app_style.mercantile_affairs": Archetype(
            short="imperium.app_style.mercantile_affairs",
            kind="imperium",
            title="Mercantile Affairs",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Contract",),
                    "AcquireValue": 4.8,
                    "ArchID": "imperium.app_style.mercantile_affairs",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit", "Circle", "Triangle", "Spy"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 5,
                    "SetList": ("bloodlines", "choam_module"),
                    "Tags": ("WantSpy", "WantContractX"),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.mercantile_affairs_agent",
                        "ability.app_style.bloodlines.acquire_contract_bonus",
                    ),
                }
            ),
        ),
        "imperium.app_style.pointing_the_way": Archetype(
            short="imperium.app_style.pointing_the_way",
            kind="imperium",
            title="Pointing the Way",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 5.8,
                    "ArchID": "imperium.app_style.pointing_the_way",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Fremen", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 6,
                    "SetList": ("bloodlines",),
                    "Strength": 2,
                    "Tags": ("WantHooks",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.pointing_the_way_agent",
                        "ability.app_style.bloodlines.pointing_the_way_command",
                    ),
                }
            ),
        ),
        "imperium.app_style.possible_futures": Archetype(
            short="imperium.app_style.possible_futures",
            kind="imperium",
            title="Possible Futures",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Water",),
                    "AcquireValue": 8.0,
                    "ArchID": "imperium.app_style.possible_futures",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit", "Fremen"),
                    "IconList": ("Pentagon", "Circle", "Triangle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 8,
                    "SetList": ("bloodlines",),
                    "Tags": ("WantBG",),
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.possible_futures_agent",
                    ),
                }
            ),
        ),
        "imperium.app_style.quash_rebellion": Archetype(
            short="imperium.app_style.quash_rebellion",
            kind="imperium",
            title="Quash Rebellion",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.8,
                    "AgentSolari": 2,
                    "ArchID": "imperium.app_style.quash_rebellion",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "SpacingGuild", "Pentagon"),
                    "ImperiumType": "Main",
                    "PersuasionCost": 5,
                    "SetList": ("bloodlines",),
                    "Strength": 2,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.app_style.bloodlines.quash_rebellion_reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.quash_rebellion_triggered",
                    ),
                }
            ),
        ),
        "imperium.app_style.ruthless_leadership": Archetype(
            short="imperium.app_style.ruthless_leadership",
            kind="imperium",
            title="Ruthless Leadership",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.app_style.ruthless_leadership",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Circle", "Triangle"),
                    "ImperiumType": "Promo",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("bloodlines",),
                    "Strength": 1,
                    "Tags": ("Combat",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.ruthless_leadership_trash",
                        "ability.app_style.bloodlines.ruthless_leadership_trash",
                        "ability.app_style.bloodlines.ruthless_leadership_command",
                    ),
                }
            ),
        ),
        "imperium.app_style.sandwalk": Archetype(
            short="imperium.app_style.sandwalk",
            kind="imperium",
            title="Sandwalk",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.0,
                    "ArchID": "imperium.app_style.sandwalk",
                    "CardCount": 2,
                    "DeferValue": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Fremen",),
                    "IconList": ("Triangle",),
                    "ImperiumType": "Main",
                    "LateMod": 0.8,
                    "Persuasion": 1,
                    "PersuasionCost": 1,
                    "SetList": ("bloodlines",),
                    "Strength": 1,
                    "Tags": ("FremenBond",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.app_style.bloodlines.sandwalk_reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.sandwalk_draw",
                        "ability.app_style.bloodlines.sandwalk_bond",
                    ),
                }
            ),
        ),
        "imperium.app_style.sardaukar_standard": Archetype(
            short="imperium.app_style.sardaukar_standard",
            kind="imperium",
            title="Sardaukar Standard",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.app_style.sardaukar_standard",
                    "CardCount": 1,
                    "EntityType": "Imperium",
                    "FactionList": ("Emperor",),
                    "IconList": ("Emperor", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 2,
                    "PersuasionCost": 4,
                    "SetList": ("bloodlines",),
                    "Troops": 1,
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.sardaukar_standard_trash",
                    ),
                }
            ),
        ),
        "imperium.app_style.shrouded_counsel": Archetype(
            short="imperium.app_style.shrouded_counsel",
            kind="imperium",
            title="Shrouded Counsel",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 3.8,
                    "ArchID": "imperium.app_style.shrouded_counsel",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("Spy",),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 4,
                    "SetList": ("bloodlines",),
                    "Tags": ("WantSpy",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.activated.agent_gain_intrigue",
                        "ability.app_style.bloodlines.shrouded_counsel_command",
                    ),
                }
            ),
        ),
        "imperium.app_style.southern_faith": Archetype(
            short="imperium.app_style.southern_faith",
            kind="imperium",
            title="Southern Faith",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 4.8,
                    "ArchID": "imperium.app_style.southern_faith",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit", "Fremen"),
                    "IconList": ("Fremen", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 5,
                    "SetList": ("bloodlines",),
                    "Strength": 2,
                    "Tags": ("WantBG",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.southern_faith_agent",
                        "ability.app_style.bloodlines.southern_faith_command",
                    ),
                }
            ),
        ),
        "imperium.app_style.urgent_shigawire": Archetype(
            short="imperium.app_style.urgent_shigawire",
            kind="imperium",
            title="Urgent Shigawire",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 1.9,
                    "ArchID": "imperium.app_style.urgent_shigawire",
                    "CardCount": 2,
                    "EntityType": "Imperium",
                    "FactionList": ("BeneGesserit",),
                    "IconList": ("BeneGesserit", "Circle"),
                    "ImperiumType": "Main",
                    "Persuasion": 1,
                    "PersuasionCost": 2,
                    "SetList": ("bloodlines",),
                    "Tags": ("WantBG",),
                    "AbilityIDs": (
                        "ability.play.agent",
                        "ability.play.reveal",
                        "ability.activated.acquire",
                        "ability.app_style.bloodlines.urgent_shigawire_agent",
                    ),
                }
            ),
        ),
        "intrigue.app_style.adaptive_tactics": Archetype(
            short="intrigue.app_style.adaptive_tactics",
            kind="intrigue",
            title="Adaptive Tactics",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.adaptive_tactics",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.adaptive_tactics",),
                }
            ),
        ),
        "intrigue.app_style.battlefield_research": Archetype(
            short="intrigue.app_style.battlefield_research",
            kind="intrigue",
            title="Battlefield Research",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.battlefield_research",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat", "Endgame"),
                    "Rating": 2,
                    "SetList": ("bloodlines", "tech_module"),
                    "Tags": ("BuyTech", "ConditionalEndgameVP"),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.battlefield_research_combat",
                        "ability.app_style.bloodlines.battlefield_research_endgame",
                    ),
                }
            ),
        ),
        "intrigue.app_style.coercive_negotiation": Archetype(
            short="intrigue.app_style.coercive_negotiation",
            kind="intrigue",
            title="Coercive Negotiation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.coercive_negotiation",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines", "choam_module"),
                    "Tags": ("Contract",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.coercive_negotiation",
                    ),
                }
            ),
        ),
        "intrigue.app_style.desert_support": Archetype(
            short="intrigue.app_style.desert_support",
            kind="intrigue",
            title="Desert Support",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.desert_support",
                    "CardCount": 1,
                    "CombatValue": 5.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "Strength": 5,
                    "AbilityIDs": ("ability.app_style.bloodlines.desert_support",),
                }
            ),
        ),
        "intrigue.app_style.emperors_invitation": Archetype(
            short="intrigue.app_style.emperors_invitation",
            kind="intrigue",
            title="Emperor's Invitation",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.emperors_invitation",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.emperors_invitation",),
                }
            ),
        ),
        "intrigue.app_style.false_orders": Archetype(
            short="intrigue.app_style.false_orders",
            kind="intrigue",
            title="False Orders",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.false_orders",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "Tags": ("Spy",),
                    "AbilityIDs": ("ability.app_style.bloodlines.false_orders",),
                }
            ),
        ),
        "intrigue.app_style.grasp_arrakis": Archetype(
            short="intrigue.app_style.grasp_arrakis",
            kind="intrigue",
            title="Grasp Arrakis",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.grasp_arrakis",
                    "CardCount": 1,
                    "CombatValue": 3.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat", "Endgame"),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "Strength": 3,
                    "Tags": ("ConditionalEndgameVP",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.grasp_arrakis_combat",
                        "ability.app_style.bloodlines.grasp_arrakis_endgame",
                    ),
                }
            ),
        ),
        "intrigue.app_style.honor_guard": Archetype(
            short="intrigue.app_style.honor_guard",
            kind="intrigue",
            title="Honor Guard",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.honor_guard",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.honor_guard",),
                }
            ),
        ),
        "intrigue.app_style.insider_information": Archetype(
            short="intrigue.app_style.insider_information",
            kind="intrigue",
            title="Insider Information",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.insider_information",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "Tags": ("WantSpy", "RecallSpy"),
                    "AbilityIDs": ("ability.app_style.bloodlines.insider_information",),
                }
            ),
        ),
        "intrigue.app_style.rapid_engineering": Archetype(
            short="intrigue.app_style.rapid_engineering",
            kind="intrigue",
            title="Rapid Engineering",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.rapid_engineering",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines", "tech_module"),
                    "Tags": ("BuyTech", "DiscardEnabler"),
                    "AbilityIDs": ("ability.app_style.bloodlines.rapid_engineering",),
                }
            ),
        ),
        "intrigue.app_style.return_the_favor": Archetype(
            short="intrigue.app_style.return_the_favor",
            kind="intrigue",
            title="Return the Favor",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.return_the_favor",
                    "CardCount": 1,
                    "CombatValue": 1.0,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "Strength": 5,
                    "Tags": (
                        "EmperorInfluence",
                        "SpacingGuildInfluence",
                        "BeneGesseritInfluence",
                        "FremenInfluence",
                    ),
                    "AbilityIDs": ("ability.app_style.bloodlines.return_the_favor",),
                }
            ),
        ),
        "intrigue.app_style.ripplesin_the_sand": Archetype(
            short="intrigue.app_style.ripplesin_the_sand",
            kind="intrigue",
            title="Ripples in the Sand",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.ripplesin_the_sand",
                    "CardCount": 1,
                    "CombatValue": 3.0,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "Strength": 3,
                    "Tags": ("WantHooks",),
                    "AbilityIDs": ("ability.app_style.bloodlines.ripples_in_the_sand",),
                }
            ),
        ),
        "intrigue.app_style.sacred_pools": Archetype(
            short="intrigue.app_style.sacred_pools",
            kind="intrigue",
            title="Sacred Pools",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.sacred_pools",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Endgame"),
                    "Rating": 3,
                    "SetList": ("bloodlines",),
                    "Tags": ("DiscardEnabler", "ConditionalEndgameVP"),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.sacred_pools_plot",
                        "ability.app_style.bloodlines.sacred_pools_endgame",
                    ),
                }
            ),
        ),
        "intrigue.app_style.seize_production": Archetype(
            short="intrigue.app_style.seize_production",
            kind="intrigue",
            title="Seize Production",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.seize_production",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.seize_production",),
                }
            ),
        ),
        "intrigue.app_style.sleeper_unit": Archetype(
            short="intrigue.app_style.sleeper_unit",
            kind="intrigue",
            title="Sleeper Unit",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.sleeper_unit",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "Tags": ("Spy", "WantSpy", "RecallSpy"),
                    "AbilityIDs": ("ability.app_style.bloodlines.sleeper_unit",),
                }
            ),
        ),
        "intrigue.app_style.tenuous_bond": Archetype(
            short="intrigue.app_style.tenuous_bond",
            kind="intrigue",
            title="Tenuous Bond",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.tenuous_bond",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Combat"),
                    "Rating": 3,
                    "SetList": ("bloodlines",),
                    "Strength": 4,
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.tenuous_bond_plot",
                        "ability.app_style.bloodlines.tenuous_bond_combat",
                    ),
                }
            ),
        ),
        "intrigue.app_style.the_strong_survive": Archetype(
            short="intrigue.app_style.the_strong_survive",
            kind="intrigue",
            title="The Strong Survive",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.the_strong_survive",
                    "CardCount": 1,
                    "CombatValue": 3.0,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "Strength": 3,
                    "AbilityIDs": ("ability.app_style.bloodlines.the_strong_survive",),
                }
            ),
        ),
        "intrigue.app_style.twisted_ambitious": Archetype(
            short="intrigue.app_style.twisted_ambitious",
            kind="intrigue",
            title="Twisted Intrigue: Ambitious",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_ambitious",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_ambitious",),
                }
            ),
        ),
        "intrigue.app_style.twisted_calculating": Archetype(
            short="intrigue.app_style.twisted_calculating",
            kind="intrigue",
            title="Twisted Intrigue: Calculating",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_calculating",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_calculating",),
                }
            ),
        ),
        "intrigue.app_style.twisted_controlled": Archetype(
            short="intrigue.app_style.twisted_controlled",
            kind="intrigue",
            title="Twisted Intrigue: Controlled",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_controlled",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot", "Combat"),
                    "Rating": 3,
                    "SetList": ("bloodlines",),
                    "Strength": 1,
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.twisted_controlled_plot",
                        "ability.app_style.bloodlines.twisted_controlled_combat",
                    ),
                }
            ),
        ),
        "intrigue.app_style.twisted_devious": Archetype(
            short="intrigue.app_style.twisted_devious",
            kind="intrigue",
            title="Twisted Intrigue: Devious",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_devious",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_devious",),
                }
            ),
        ),
        "intrigue.app_style.twisted_discerning": Archetype(
            short="intrigue.app_style.twisted_discerning",
            kind="intrigue",
            title="Twisted Intrigue: Discerning",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_discerning",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_discerning",),
                }
            ),
        ),
        "intrigue.app_style.twisted_insidious": Archetype(
            short="intrigue.app_style.twisted_insidious",
            kind="intrigue",
            title="Twisted Intrigue: Insidious",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_insidious",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_insidious",),
                }
            ),
        ),
        "intrigue.app_style.twisted_resourceful": Archetype(
            short="intrigue.app_style.twisted_resourceful",
            kind="intrigue",
            title="Twisted Intrigue: Resourceful",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_resourceful",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_resourceful",),
                }
            ),
        ),
        "intrigue.app_style.twisted_sadistic": Archetype(
            short="intrigue.app_style.twisted_sadistic",
            kind="intrigue",
            title="Twisted Intrigue: Sadistic",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_sadistic",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_sadistic",),
                }
            ),
        ),
        "intrigue.app_style.twisted_shrewd": Archetype(
            short="intrigue.app_style.twisted_shrewd",
            kind="intrigue",
            title="Twisted Intrigue: Shrewd",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_shrewd",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_shrewd",),
                }
            ),
        ),
        "intrigue.app_style.twisted_sinister": Archetype(
            short="intrigue.app_style.twisted_sinister",
            kind="intrigue",
            title="Twisted Intrigue: Sinister",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_sinister",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_sinister",),
                }
            ),
        ),
        "intrigue.app_style.twisted_unnatural": Archetype(
            short="intrigue.app_style.twisted_unnatural",
            kind="intrigue",
            title="Twisted Intrigue: Unnatural",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_unnatural",
                    "CardCount": 1,
                    "DeferValue": 2,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_unnatural",),
                }
            ),
        ),
        "intrigue.app_style.twisted_withdrawn": Archetype(
            short="intrigue.app_style.twisted_withdrawn",
            kind="intrigue",
            title="Twisted Intrigue: Withdrawn",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.twisted_withdrawn",
                    "CardCount": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Plot",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.twisted_withdrawn",),
                }
            ),
        ),
        "intrigue.app_style.withdrawal_agreement": Archetype(
            short="intrigue.app_style.withdrawal_agreement",
            kind="intrigue",
            title="Withdrawal Agreement",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "intrigue.app_style.withdrawal_agreement",
                    "CardCount": 1,
                    "DeferValue": 1,
                    "EntityType": "Intrigue",
                    "IntrigueTypeList": ("Combat",),
                    "Rating": 2,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.withdrawal_agreement",
                    ),
                }
            ),
        ),
        "leader.app_style.chani_leader": Archetype(
            short="leader.app_style.chani_leader",
            kind="leader",
            title="Chani",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.app_style.chani_leader",
                    "EntityType": "Leader",
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.tactician",
                        "ability.app_style.bloodlines.fedaykin_maneuver_signet",
                    ),
                }
            ),
        ),
        "leader.app_style.count_hasimir_fenring": Archetype(
            short="leader.app_style.count_hasimir_fenring",
            kind="leader",
            title="Count Hasimir Fenring",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.app_style.count_hasimir_fenring",
                    "EntityType": "Leader",
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.assassin",
                        "ability.app_style.bloodlines.corrino_liaison_signet",
                    ),
                }
            ),
        ),
        "leader.app_style.duncan_idaho_leader": Archetype(
            short="leader.app_style.duncan_idaho_leader",
            kind="leader",
            title="Duncan Idaho",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.app_style.duncan_idaho_leader",
                    "EntityType": "Leader",
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.ginaz_swordmaster",
                        "ability.app_style.bloodlines.into_the_fray_signet",
                    ),
                }
            ),
        ),
        "leader.app_style.esmar_tuek_leader": Archetype(
            short="leader.app_style.esmar_tuek_leader",
            kind="leader",
            title="Esmar Tuek",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.app_style.esmar_tuek_leader",
                    "EntityType": "Leader",
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.tueks_sietch_leader",
                        "ability.app_style.bloodlines.smuggle_spice_signet",
                    ),
                }
            ),
        ),
        "leader.app_style.gaius_helen_mohiam": Archetype(
            short="leader.app_style.gaius_helen_mohiam",
            kind="leader",
            title="Gaius Helen Mohiam",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.app_style.gaius_helen_mohiam",
                    "EntityType": "Leader",
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.clandestine",
                        "ability.app_style.bloodlines.listeners_signet",
                    ),
                }
            ),
        ),
        "leader.app_style.kota_odax_of_ix": Archetype(
            short="leader.app_style.kota_odax_of_ix",
            kind="leader",
            title="Kota Odax of Ix",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.app_style.kota_odax_of_ix",
                    "EntityType": "Leader",
                    "SetList": ("bloodlines", "tech_module"),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.secret_project",
                        "ability.app_style.bloodlines.reverse_engineering_signet",
                    ),
                }
            ),
        ),
        "leader.app_style.liet_kynes_leader": Archetype(
            short="leader.app_style.liet_kynes_leader",
            kind="leader",
            title="Liet Kynes",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.app_style.liet_kynes_leader",
                    "EntityType": "Leader",
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.arrakis_planetologist",
                        "ability.app_style.bloodlines.judge_of_the_change_signet",
                    ),
                }
            ),
        ),
        "leader.app_style.piter_de_vries_leader": Archetype(
            short="leader.app_style.piter_de_vries_leader",
            kind="leader",
            title="Piter De Vries",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.app_style.piter_de_vries_leader",
                    "EntityType": "Leader",
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.twisted_genius",
                        "ability.activated.uprising.warmaster",
                    ),
                }
            ),
        ),
        "leader.app_style.steersman_yrkoon_leader": Archetype(
            short="leader.app_style.steersman_yrkoon_leader",
            kind="leader",
            title="Steersman Y'rkoon",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "leader.app_style.steersman_yrkoon_leader",
                    "EntityType": "Leader",
                    "SetList": ("bloodlines",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.strange_form",
                        "ability.app_style.bloodlines.hungry_for_spice",
                        "ability.app_style.bloodlines.plot_course",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_botanical_stationed_support0": Archetype(
            short="mission.app_style.scouts_botanical_stationed_support0",
            kind="other",
            title="Botanical Testing - Stationed Support",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 2,
                    "ArchID": "mission.app_style.scouts_botanical_stationed_support0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.discard_cost",
                        "ability.app_style.scouts.parked_troops_to_conflict",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_choam_escort0": Archetype(
            short="mission.app_style.scouts_choam_escort0",
            kind="other",
            title="CHOAM Escort",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "mission.app_style.scouts_choam_escort0",
                    "EntityType": "ScoutsLine",
                    "Troops": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "mission.app_style.scouts_choam_escort1": Archetype(
            short="mission.app_style.scouts_choam_escort1",
            kind="other",
            title="CHOAM Escort",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "mission.app_style.scouts_choam_escort1",
                    "EntityType": "ScoutsLine",
                    "Solari": 1,
                    "Spice": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "mission.app_style.scouts_coordinate_with_the_emperor0": Archetype(
            short="mission.app_style.scouts_coordinate_with_the_emperor0",
            kind="other",
            title="Coordinate With The Emperor",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 1,
                    "ArchID": "mission.app_style.scouts_coordinate_with_the_emperor0",
                    "EntityType": "ScoutsLine",
                    "Solari": 2,
                    "SpecimenCost": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.parked_troops_to_garrison",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_fedaykin_assistance0": Archetype(
            short="mission.app_style.scouts_fedaykin_assistance0",
            kind="other",
            title="Fedaykin Assistance",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 2,
                    "ArchID": "mission.app_style.scouts_fedaykin_assistance0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.parked_troops_to_garrison",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_genetic_research0": Archetype(
            short="mission.app_style.scouts_genetic_research0",
            kind="other",
            title="Genetic Research",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 1,
                    "ArchID": "mission.app_style.scouts_genetic_research0",
                    "EntityType": "ScoutsLine",
                    "Solari": 2,
                    "AbilityIDs": (
                        "ability.app_style.scouts.lose_garrison_troops_cost",
                        "ability.app_style.scouts.parked_troops_to_conflict",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_guild_maneuvers0": Archetype(
            short="mission.app_style.scouts_guild_maneuvers0",
            kind="other",
            title="Guild Maneuvers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 2,
                    "ArchID": "mission.app_style.scouts_guild_maneuvers0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.parked_troops_to_conflict",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_imperium_coordinate_with_the_emperor0": Archetype(
            short="mission.app_style.scouts_imperium_coordinate_with_the_emperor0",
            kind="other",
            title="Coordinate With The Emperor",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 1,
                    "ArchID": "mission.app_style.scouts_imperium_coordinate_with_the_emperor0",
                    "EntityType": "ScoutsLine",
                    "Solari": 2,
                    "SpecimenCost": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.parked_troops_to_garrison",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_muster_strongarmed_alliance0": Archetype(
            short="mission.app_style.scouts_muster_strongarmed_alliance0",
            kind="other",
            title="Muster an Army - Strongarmed Alliance",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 1,
                    "ArchID": "mission.app_style.scouts_muster_strongarmed_alliance0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.parked_troops_to_conflict",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_prison_planet0": Archetype(
            short="mission.app_style.scouts_prison_planet0",
            kind="other",
            title="Prison Planet",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "mission.app_style.scouts_prison_planet0",
                    "EntityType": "ScoutsLine",
                    "Spice": 2,
                    "AbilityIDs": (
                        "ability.app_style.scouts.lose_garrison_troops_cost",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_sapho_juice0": Archetype(
            short="mission.app_style.scouts_sapho_juice0",
            kind="other",
            title="Sapho Juice",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "mission.app_style.scouts_sapho_juice0",
                    "EntityType": "ScoutsLine",
                    "Spice": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "mission.app_style.scouts_security_detail0": Archetype(
            short="mission.app_style.scouts_security_detail0",
            kind="other",
            title="Security Detail",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 1,
                    "ArchID": "mission.app_style.scouts_security_detail0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.parked_troops_to_conflict",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_send_for_aid0": Archetype(
            short="mission.app_style.scouts_send_for_aid0",
            kind="other",
            title="Send for Aid",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 1,
                    "ArchID": "mission.app_style.scouts_send_for_aid0",
                    "EntityType": "ScoutsLine",
                    "Water": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.lose_garrison_troops_cost",
                        "ability.app_style.scouts.parked_troops_to_conflict",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_stowaways0": Archetype(
            short="mission.app_style.scouts_stowaways0",
            kind="other",
            title="Stowaways",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 2,
                    "ArchID": "mission.app_style.scouts_stowaways0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.parked_troops_to_conflict",
                    ),
                }
            ),
        ),
        "mission.app_style.scouts_tleilaxu_offering0": Archetype(
            short="mission.app_style.scouts_tleilaxu_offering0",
            kind="other",
            title="Tleilaxu Offering",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "mission.app_style.scouts_tleilaxu_offering0",
                    "EntityType": "ScoutsLine",
                    "Specimen": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "mission.app_style.scouts_weirding_warfare0": Archetype(
            short="mission.app_style.scouts_weirding_warfare0",
            kind="other",
            title="Weirding Warfare",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 2,
                    "ArchID": "mission.app_style.scouts_weirding_warfare0",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 2,
                    "AbilityIDs": (
                        "ability.app_style.scouts.parked_troops_to_conflict",
                    ),
                }
            ),
        ),
        "navigation.app_style.navigation_card1": Archetype(
            short="navigation.app_style.navigation_card1",
            kind="other",
            title="Navigation Card 1",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card1",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card1",),
                }
            ),
        ),
        "navigation.app_style.navigation_card10": Archetype(
            short="navigation.app_style.navigation_card10",
            kind="other",
            title="Navigation Card 10",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card10",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card10",),
                }
            ),
        ),
        "navigation.app_style.navigation_card2": Archetype(
            short="navigation.app_style.navigation_card2",
            kind="other",
            title="Navigation Card 2",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card2",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card2",),
                }
            ),
        ),
        "navigation.app_style.navigation_card3": Archetype(
            short="navigation.app_style.navigation_card3",
            kind="other",
            title="Navigation Card 3",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card3",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card3",),
                }
            ),
        ),
        "navigation.app_style.navigation_card4": Archetype(
            short="navigation.app_style.navigation_card4",
            kind="other",
            title="Navigation Card 4",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card4",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card4",),
                }
            ),
        ),
        "navigation.app_style.navigation_card5": Archetype(
            short="navigation.app_style.navigation_card5",
            kind="other",
            title="Navigation Card 5",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card5",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card5",),
                }
            ),
        ),
        "navigation.app_style.navigation_card6": Archetype(
            short="navigation.app_style.navigation_card6",
            kind="other",
            title="Navigation Card 6",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card6",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card6",),
                }
            ),
        ),
        "navigation.app_style.navigation_card7": Archetype(
            short="navigation.app_style.navigation_card7",
            kind="other",
            title="Navigation Card 7",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card7",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card7",),
                }
            ),
        ),
        "navigation.app_style.navigation_card8": Archetype(
            short="navigation.app_style.navigation_card8",
            kind="other",
            title="Navigation Card 8",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card8",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card8",),
                }
            ),
        ),
        "navigation.app_style.navigation_card9": Archetype(
            short="navigation.app_style.navigation_card9",
            kind="other",
            title="Navigation Card 9",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "navigation.app_style.navigation_card9",
                    "CardCount": 1,
                    "EntityType": "Navigation",
                    "IntrigueTypeList": (),
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.navigation_card9",),
                }
            ),
        ),
        "sale.app_style.scouts_fremen_mercenaries0": Archetype(
            short="sale.app_style.scouts_fremen_mercenaries0",
            kind="other",
            title="Fremen Mercenaries",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 2,
                    "ArchID": "sale.app_style.scouts_fremen_mercenaries0",
                    "EntityType": "ScoutsLine",
                    "WaterCost": 1,
                    "AbilityIDs": ("ability.app_style.scouts.recruit_to_conflict",),
                }
            ),
        ),
        "sale.app_style.scouts_fremen_mercenaries1": Archetype(
            short="sale.app_style.scouts_fremen_mercenaries1",
            kind="other",
            title="Fremen Mercenaries",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 4,
                    "ArchID": "sale.app_style.scouts_fremen_mercenaries1",
                    "EntityType": "ScoutsLine",
                    "WaterCost": 2,
                    "AbilityIDs": ("ability.app_style.scouts.recruit_to_conflict",),
                }
            ),
        ),
        "sale.app_style.scouts_fremen_mercenaries2": Archetype(
            short="sale.app_style.scouts_fremen_mercenaries2",
            kind="other",
            title="Fremen Mercenaries",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 6,
                    "ArchID": "sale.app_style.scouts_fremen_mercenaries2",
                    "EntityType": "ScoutsLine",
                    "WaterCost": 3,
                    "AbilityIDs": ("ability.app_style.scouts.recruit_to_conflict",),
                }
            ),
        ),
        "sale.app_style.scouts_fremen_mercenaries3": Archetype(
            short="sale.app_style.scouts_fremen_mercenaries3",
            kind="other",
            title="Fremen Mercenaries",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 8,
                    "ArchID": "sale.app_style.scouts_fremen_mercenaries3",
                    "EntityType": "ScoutsLine",
                    "WaterCost": 4,
                    "AbilityIDs": ("ability.app_style.scouts.recruit_to_conflict",),
                }
            ),
        ),
        "sale.app_style.scouts_fremen_mercenaries4": Archetype(
            short="sale.app_style.scouts_fremen_mercenaries4",
            kind="other",
            title="Fremen Mercenaries",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 10,
                    "ArchID": "sale.app_style.scouts_fremen_mercenaries4",
                    "EntityType": "ScoutsLine",
                    "WaterCost": 5,
                    "AbilityIDs": ("ability.app_style.scouts.recruit_to_conflict",),
                }
            ),
        ),
        "sale.app_style.scouts_fremen_mercenaries5": Archetype(
            short="sale.app_style.scouts_fremen_mercenaries5",
            kind="other",
            title="Fremen Mercenaries",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 12,
                    "ArchID": "sale.app_style.scouts_fremen_mercenaries5",
                    "EntityType": "ScoutsLine",
                    "WaterCost": 6,
                    "AbilityIDs": ("ability.app_style.scouts.recruit_to_conflict",),
                }
            ),
        ),
        "sale.app_style.scouts_imperium_connections0": Archetype(
            short="sale.app_style.scouts_imperium_connections0",
            kind="other",
            title="Imperium Connections",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "sale.app_style.scouts_imperium_connections0",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 2,
                    "AbilityIDs": ("ability.activated.uprising.place_spy_custom",),
                }
            ),
        ),
        "sale.app_style.scouts_imperium_connections1": Archetype(
            short="sale.app_style.scouts_imperium_connections1",
            kind="other",
            title="Imperium Connections",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "sale.app_style.scouts_imperium_connections1",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 2,
                    "Water": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "sale.app_style.scouts_secrets_for_sale0": Archetype(
            short="sale.app_style.scouts_secrets_for_sale0",
            kind="other",
            title="Secrets for Sale",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "sale.app_style.scouts_secrets_for_sale0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "SpiceCost": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "sale.app_style.scouts_secrets_for_sale1": Archetype(
            short="sale.app_style.scouts_secrets_for_sale1",
            kind="other",
            title="Secrets for Sale",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "sale.app_style.scouts_secrets_for_sale1",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 2,
                    "SpiceCost": 3,
                    "AbilityIDs": (),
                }
            ),
        ),
        "sale.app_style.scouts_shadow_warfare0": Archetype(
            short="sale.app_style.scouts_shadow_warfare0",
            kind="other",
            title="Shadow Warfare",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 1,
                    "ArchID": "sale.app_style.scouts_shadow_warfare0",
                    "EntityType": "ScoutsLine",
                    "Spice": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.recall_spy_cost",
                        "ability.app_style.scouts.recruit_to_conflict",
                    ),
                }
            ),
        ),
        "sale.app_style.scouts_shadow_warfare1": Archetype(
            short="sale.app_style.scouts_shadow_warfare1",
            kind="other",
            title="Shadow Warfare",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AbilityTroops": 3,
                    "ArchID": "sale.app_style.scouts_shadow_warfare1",
                    "EntityType": "ScoutsLine",
                    "Spice": 2,
                    "AbilityIDs": (
                        "ability.app_style.scouts.recall_spy_cost",
                        "ability.app_style.scouts.recall_spy_cost",
                        "ability.app_style.scouts.recruit_to_conflict",
                    ),
                }
            ),
        ),
        "sale.app_style.scouts_unravel_the_future0": Archetype(
            short="sale.app_style.scouts_unravel_the_future0",
            kind="other",
            title="Unravel the Future",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "sale.app_style.scouts_unravel_the_future0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 1,
                    "AbilityIDs": ("ability.activated.draw",),
                }
            ),
        ),
        "sale.app_style.scouts_unravel_the_future1": Archetype(
            short="sale.app_style.scouts_unravel_the_future1",
            kind="other",
            title="Unravel the Future",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "sale.app_style.scouts_unravel_the_future1",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 3,
                    "AbilityIDs": ("ability.activated.draw", "ability.activated.draw"),
                }
            ),
        ),
        "sale.app_style.scouts_water_peddlers0": Archetype(
            short="sale.app_style.scouts_water_peddlers0",
            kind="other",
            title="Soo-Soo Sook! Water Peddlers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "sale.app_style.scouts_water_peddlers0",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 2,
                    "Water": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "sale.app_style.scouts_water_peddlers1": Archetype(
            short="sale.app_style.scouts_water_peddlers1",
            kind="other",
            title="Soo-Soo Sook! Water Peddlers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "sale.app_style.scouts_water_peddlers1",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 4,
                    "Water": 2,
                    "AbilityIDs": (),
                }
            ),
        ),
        "skill.app_style.canny": Archetype(
            short="skill.app_style.canny",
            kind="other",
            title="Canny",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "skill.app_style.canny",
                    "CardCount": 2,
                    "EntityType": "Skill",
                    "SetList": ("bloodlines",),
                    "Strength": 2,
                    "AbilityIDs": ("ability.app_style.bloodlines.canny_skill",),
                }
            ),
        ),
        "skill.app_style.charismatic": Archetype(
            short="skill.app_style.charismatic",
            kind="other",
            title="Charismatic",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "skill.app_style.charismatic",
                    "CardCount": 2,
                    "EntityType": "Skill",
                    "Persuasion": 1,
                    "SetList": ("bloodlines",),
                    "AbilityIDs": ("ability.app_style.bloodlines.skill_reveal",),
                }
            ),
        ),
        "skill.app_style.desperate": Archetype(
            short="skill.app_style.desperate",
            kind="other",
            title="Desperate",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "skill.app_style.desperate",
                    "CardCount": 2,
                    "EntityType": "Skill",
                    "SetList": ("bloodlines",),
                    "Strength": 3,
                    "AbilityIDs": ("ability.app_style.bloodlines.desperate_skill",),
                }
            ),
        ),
        "skill.app_style.driven": Archetype(
            short="skill.app_style.driven",
            kind="other",
            title="Driven",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "skill.app_style.driven",
                    "CardCount": 2,
                    "EntityType": "Skill",
                    "SetList": ("bloodlines",),
                    "Spice": 1,
                    "AbilityIDs": ("ability.app_style.bloodlines.skill_reveal",),
                }
            ),
        ),
        "skill.app_style.fierce": Archetype(
            short="skill.app_style.fierce",
            kind="other",
            title="Fierce",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "skill.app_style.fierce",
                    "CardCount": 2,
                    "EntityType": "Skill",
                    "SetList": ("bloodlines",),
                    "Strength": 1,
                    "AbilityIDs": ("ability.app_style.bloodlines.fierce_skill",),
                }
            ),
        ),
        "skill.app_style.hardy": Archetype(
            short="skill.app_style.hardy",
            kind="other",
            title="Hardy",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "skill.app_style.hardy",
                    "CardCount": 2,
                    "EntityType": "Skill",
                    "SetList": ("bloodlines",),
                    "Troops": 1,
                    "AbilityIDs": ("ability.app_style.bloodlines.skill_reveal",),
                }
            ),
        ),
        "skill.app_style.loyal": Archetype(
            short="skill.app_style.loyal",
            kind="other",
            title="Loyal",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "skill.app_style.loyal",
                    "CardCount": 2,
                    "EntityType": "Skill",
                    "InfluenceRequirements": ({"Amount": 3, "Faction": "Emperor"},),
                    "SetList": ("bloodlines",),
                    "Strength": 2,
                    "AbilityIDs": ("ability.app_style.bloodlines.loyal_skill",),
                }
            ),
        ),
        "space.app_style.tueks_sietch": Archetype(
            short="space.app_style.tueks_sietch",
            kind="space",
            title="Tuek's Sietch",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AgentIcon": "Triangle",
                    "ArchID": "space.app_style.tueks_sietch",
                    "BonusSpice": 0,
                    "CombatSpace": True,
                    "EntityType": "Space",
                    "ObservationPosts": (),
                    "PossibleSpice": 1,
                    "SetList": ("bloodlines",),
                    "Tags": ("Harvest",),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.tueks_sietch_deferred",
                        "ability.activated.deploy_units",
                        "ability.space.space",
                    ),
                }
            ),
        ),
        "subcommittee.app_style.scouts_analytics0": Archetype(
            short="subcommittee.app_style.scouts_analytics0",
            kind="other",
            title="Analytics",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_analytics0",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 1,
                    "AbilityIDs": (
                        "ability.activated.immortality.gain_research_custom",
                    ),
                }
            ),
        ),
        "subcommittee.app_style.scouts_appropriations0": Archetype(
            short="subcommittee.app_style.scouts_appropriations0",
            kind="other",
            title="Appropriations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_appropriations0",
                    "EntityType": "ScoutsLine",
                    "Water": 1,
                    "AbilityIDs": ("ability.app_style.scouts.discard_cost",),
                }
            ),
        ),
        "subcommittee.app_style.scouts_choam_coordination0": Archetype(
            short="subcommittee.app_style.scouts_choam_coordination0",
            kind="other",
            title="CHOAM Coordination",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_choam_coordination0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.gain_contract_custom",),
                }
            ),
        ),
        "subcommittee.app_style.scouts_choam_management0": Archetype(
            short="subcommittee.app_style.scouts_choam_management0",
            kind="other",
            title="CHOAM Management",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_choam_management0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 1,
                    "AbilityIDs": (
                        "ability.activated.uprising.gain_contract_custom",
                        "ability.activated.uprising.gain_contract_custom",
                    ),
                }
            ),
        ),
        "subcommittee.app_style.scouts_contingencies0": Archetype(
            short="subcommittee.app_style.scouts_contingencies0",
            kind="other",
            title="Contingencies",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_contingencies0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": (
                        "ability.app_style.scouts.trash_intrigue_cost",
                        "ability.activated.uprising.recall_agent",
                    ),
                }
            ),
        ),
        "subcommittee.app_style.scouts_development0": Archetype(
            short="subcommittee.app_style.scouts_development0",
            kind="other",
            title="Development",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_development0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 3,
                    "AbilityIDs": (
                        "ability.activated.draw",
                        "ability.activated.draw",
                        "ability.activated.draw",
                    ),
                }
            ),
        ),
        "subcommittee.app_style.scouts_forecasting0": Archetype(
            short="subcommittee.app_style.scouts_forecasting0",
            kind="other",
            title="Forecasting",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_forecasting0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 1,
                    "AbilityIDs": ("ability.activated.draw", "ability.activated.draw"),
                }
            ),
        ),
        "subcommittee.app_style.scouts_growth_project0": Archetype(
            short="subcommittee.app_style.scouts_growth_project0",
            kind="other",
            title="Growth Project",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_growth_project0",
                    "EntityType": "ScoutsLine",
                    "Specimen": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "subcommittee.app_style.scouts_imperium_appropriations0": Archetype(
            short="subcommittee.app_style.scouts_imperium_appropriations0",
            kind="other",
            title="Appropriations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_imperium_appropriations0",
                    "EntityType": "ScoutsLine",
                    "Spice": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "subcommittee.app_style.scouts_imperium_intelligence0": Archetype(
            short="subcommittee.app_style.scouts_imperium_intelligence0",
            kind="other",
            title="Intelligence",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_imperium_intelligence0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.draw",),
                }
            ),
        ),
        "subcommittee.app_style.scouts_imperium_oversight0": Archetype(
            short="subcommittee.app_style.scouts_imperium_oversight0",
            kind="other",
            title="Oversight",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_imperium_oversight0",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 1,
                    "AbilityIDs": ("ability.activated.trash_custom",),
                }
            ),
        ),
        "subcommittee.app_style.scouts_intelligence0": Archetype(
            short="subcommittee.app_style.scouts_intelligence0",
            kind="other",
            title="Intelligence",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_intelligence0",
                    "EntityType": "ScoutsLine",
                    "AbilityIDs": ("ability.activated.uprising.place_spy_custom",),
                }
            ),
        ),
        "subcommittee.app_style.scouts_investigations0": Archetype(
            short="subcommittee.app_style.scouts_investigations0",
            kind="other",
            title="Investigations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_investigations0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "SolariCost": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "subcommittee.app_style.scouts_joint_forces0": Archetype(
            short="subcommittee.app_style.scouts_joint_forces0",
            kind="other",
            title="Joint Forces",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_joint_forces0",
                    "EntityType": "ScoutsLine",
                    "SolariCost": 2,
                    "Troops": 3,
                    "AbilityIDs": (),
                }
            ),
        ),
        "subcommittee.app_style.scouts_leverage0": Archetype(
            short="subcommittee.app_style.scouts_leverage0",
            kind="other",
            title="Leverage",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_leverage0",
                    "EntityType": "ScoutsLine",
                    "IntrigueCard": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.recall_spy_cost",
                        "ability.app_style.scouts.recall_spy_cost",
                        "ability.activated.gain_any_influence_agent",
                    ),
                }
            ),
        ),
        "subcommittee.app_style.scouts_oversight0": Archetype(
            short="subcommittee.app_style.scouts_oversight0",
            kind="other",
            title="Oversight",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_oversight0",
                    "EntityType": "ScoutsLine",
                    "Spice": 1,
                    "AbilityIDs": (
                        "ability.app_style.scouts.recall_spy_cost",
                        "ability.activated.trash_custom",
                    ),
                }
            ),
        ),
        "subcommittee.app_style.scouts_political_affairs0": Archetype(
            short="subcommittee.app_style.scouts_political_affairs0",
            kind="other",
            title="Political Affairs",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_political_affairs0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 4,
                    "AbilityIDs": ("ability.app_style.scouts.gain_two_influence",),
                }
            ),
        ),
        "subcommittee.app_style.scouts_readiness0": Archetype(
            short="subcommittee.app_style.scouts_readiness0",
            kind="other",
            title="Readiness",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_readiness0",
                    "EntityType": "ScoutsLine",
                    "Troops": 1,
                    "AbilityIDs": (),
                }
            ),
        ),
        "subcommittee.app_style.scouts_relations0": Archetype(
            short="subcommittee.app_style.scouts_relations0",
            kind="other",
            title="Relations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_relations0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 2,
                    "AbilityIDs": ("ability.activated.gain_any_influence_agent",),
                }
            ),
        ),
        "subcommittee.app_style.scouts_tleilaxu_relations0": Archetype(
            short="subcommittee.app_style.scouts_tleilaxu_relations0",
            kind="other",
            title="Tleilaxu Relations",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "ArchID": "subcommittee.app_style.scouts_tleilaxu_relations0",
                    "EntityType": "ScoutsLine",
                    "SpiceCost": 3,
                    "AbilityIDs": ("ability.app_style.scouts.gain_two_tleilaxu",),
                }
            ),
        ),
        "tech_tile.app_style.advanced_data_analysis": Archetype(
            short="tech_tile.app_style.advanced_data_analysis",
            kind="other",
            title="Advanced Data Analysis",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 6.0,
                    "ArchID": "tech_tile.app_style.advanced_data_analysis",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 3,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.advanced_data_analysis",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.choam_transports": Archetype(
            short="tech_tile.app_style.choam_transports",
            kind="other",
            title="CHOAM Transports",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Contract",),
                    "AcquireValue": 12.0,
                    "ArchID": "tech_tile.app_style.choam_transports",
                    "CardCount": 1,
                    "EarlyMod": 1.2,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "choam_module", "tech_module"),
                    "SpiceCost": 6,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.choam_transports",
                        "ability.app_style.bloodlines.acquire_effects_bonus",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.delivery_bay": Archetype(
            short="tech_tile.app_style.delivery_bay",
            kind="other",
            title="Delivery Bay",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Imperium",),
                    "AcquireValue": 6.0,
                    "ArchID": "tech_tile.app_style.delivery_bay",
                    "CardCount": 1,
                    "EarlyMod": 1.5,
                    "EntityType": "TechTile",
                    "LateMod": 0.0,
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 3,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.conflict.original.draw_imperium_acquired",
                        "ability.app_style.bloodlines.delivery_bay",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.forbidden_weapons": Archetype(
            short="tech_tile.app_style.forbidden_weapons",
            kind="other",
            title="Forbidden Weapons",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Troop", "ShieldWall"),
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.app_style.forbidden_weapons",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 2,
                    "Tags": (),
                    "AbilityIDs": ("ability.app_style.bloodlines.forbidden_weapons",),
                }
            ),
        ),
        "tech_tile.app_style.gene_locked_vault": Archetype(
            short="tech_tile.app_style.gene_locked_vault",
            kind="other",
            title="Gene-Locked Vault",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("IntrigueOrImperium",),
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.app_style.gene_locked_vault",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 2,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.gene_locked_vault_acquired",
                        "ability.app_style.bloodlines.gene_locked_vault",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.glowglobes": Archetype(
            short="tech_tile.app_style.glowglobes",
            kind="other",
            title="Glowglobes",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("AnyRank",),
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.app_style.glowglobes",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 2,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.conflict.original.memocorders_acquired",
                        "ability.app_style.bloodlines.glowglobes",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.navigation_chamber": Archetype(
            short="tech_tile.app_style.navigation_chamber",
            kind="other",
            title="Navigation Chamber",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("AnyRank",),
                    "AcquireValue": 10.0,
                    "ArchID": "tech_tile.app_style.navigation_chamber",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 5,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.conflict.original.memocorders_acquired",
                        "ability.app_style.bloodlines.navigation_chamber",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.ornithopter_fleet": Archetype(
            short="tech_tile.app_style.ornithopter_fleet",
            kind="other",
            title="Ornithopter Fleet",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Troop", "Troop"),
                    "AcquireValue": 8.0,
                    "ArchID": "tech_tile.app_style.ornithopter_fleet",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 4,
                    "Tags": (),
                    "AbilityIDs": ("ability.app_style.bloodlines.ornithopter_fleet",),
                }
            ),
        ),
        "tech_tile.app_style.panopticon": Archetype(
            short="tech_tile.app_style.panopticon",
            kind="other",
            title="Panopticon",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 10.0,
                    "ArchID": "tech_tile.app_style.panopticon",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 5,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.activated.uprising.place_spy_reveal",
                        "ability.app_style.bloodlines.panopticon",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.planetary_array": Archetype(
            short="tech_tile.app_style.planetary_array",
            kind="other",
            title="Planetary Array",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Trash",),
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.app_style.planetary_array",
                    "CardCount": 1,
                    "EarlyMod": 1.5,
                    "EntityType": "TechTile",
                    "LateMod": 0.5,
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 2,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.activated.disposal_facility_acquired",
                        "ability.app_style.bloodlines.planetary_array",
                        "ability.app_style.bloodlines.acquire_effects_bonus",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.plasteel_blades": Archetype(
            short="tech_tile.app_style.plasteel_blades",
            kind="other",
            title="Plasteel Blades",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Solari", "Solari", "Solari", "Solari"),
                    "AcquireValue": 6.0,
                    "ArchID": "tech_tile.app_style.plasteel_blades",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 3,
                    "Tags": (),
                    "AbilityIDs": ("ability.app_style.bloodlines.plasteel_blades",),
                }
            ),
        ),
        "tech_tile.app_style.rapid_dropships": Archetype(
            short="tech_tile.app_style.rapid_dropships",
            kind="other",
            title="Rapid Dropships",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Troop", "Troop"),
                    "AcquireValue": 8.0,
                    "ArchID": "tech_tile.app_style.rapid_dropships",
                    "CardCount": 1,
                    "EarlyMod": 1.1,
                    "EntityType": "TechTile",
                    "LateMod": 0.75,
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 4,
                    "Tags": (),
                    "AbilityIDs": ("ability.app_style.bloodlines.rapid_dropships",),
                }
            ),
        ),
        "tech_tile.app_style.sardaukar_high_command": Archetype(
            short="tech_tile.app_style.sardaukar_high_command",
            kind="other",
            title="Sardaukar High Command",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("VP",),
                    "AcquireValue": 14.0,
                    "ArchID": "tech_tile.app_style.sardaukar_high_command",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 7,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.sardaukar_high_command",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.self_destroying_messages": Archetype(
            short="tech_tile.app_style.self_destroying_messages",
            kind="other",
            title="Self-Destroying Messages",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Intrigue", "Intrigue"),
                    "AcquireValue": 8.0,
                    "ArchID": "tech_tile.app_style.self_destroying_messages",
                    "CardCount": 1,
                    "EarlyMod": 1.5,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 4,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.acquire_effects_bonus",
                        "ability.triggered.ix.minimic_film",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.servo_receivers": Archetype(
            short="tech_tile.app_style.servo_receivers",
            kind="other",
            title="Servo-Receivers",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("Signet",),
                    "AcquireValue": 4.0,
                    "ArchID": "tech_tile.app_style.servo_receivers",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 2,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.servo_receivers_acquired",
                        "ability.app_style.bloodlines.servo_receivers",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.spy_drones": Archetype(
            short="tech_tile.app_style.spy_drones",
            kind="other",
            title="Spy Drones",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireEffectList": ("PlaceSpy", "PlaceSpy"),
                    "AcquireValue": 10.0,
                    "ArchID": "tech_tile.app_style.spy_drones",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 5,
                    "Tags": (),
                    "AbilityIDs": (
                        "ability.app_style.bloodlines.spy_drones",
                        "ability.app_style.bloodlines.acquire_effects_bonus",
                    ),
                }
            ),
        ),
        "tech_tile.app_style.suspensor_suits": Archetype(
            short="tech_tile.app_style.suspensor_suits",
            kind="other",
            title="Suspensor Suits",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 6.0,
                    "ArchID": "tech_tile.app_style.suspensor_suits",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 3,
                    "Tags": (),
                    "AbilityIDs": ("ability.app_style.bloodlines.suspensor_suits",),
                }
            ),
        ),
        "tech_tile.app_style.training_depot": Archetype(
            short="tech_tile.app_style.training_depot",
            kind="other",
            title="Training Depot",
            in_uprising=False,
            in_uprising_choam=False,
            attributes=MappingProxyType(
                {
                    "AcquireValue": 2.0,
                    "ArchID": "tech_tile.app_style.training_depot",
                    "CardCount": 1,
                    "EntityType": "TechTile",
                    "SetList": ("bloodlines", "tech_module"),
                    "SpiceCost": 1,
                    "Tags": (),
                    "AbilityIDs": ("ability.app_style.bloodlines.training_depot",),
                }
            ),
        ),
    }
)

SCOUTS_LINES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "analytics:0": "subcommittee.app_style.scouts_analytics0",
        "appropriations:0": "subcommittee.app_style.scouts_appropriations0",
        "assassination:0": "event.app_style.scouts_assassination0",
        "bene_gesserit_treachery:0": "event.app_style.scouts_bene_gesserit_treachery0",
        "bene_gesserit_treachery:1": "event.app_style.scouts_bene_gesserit_treachery1",
        "betrayal:0": "event.app_style.scouts_betrayal0",
        "botanical_stationed_support:0": "mission.app_style.scouts_botanical_stationed_support0",
        "change_of_plans:0": "event.app_style.scouts_change_of_plans0",
        "choam_bargain:0": "event.app_style.scouts_choam_bargain0",
        "choam_bargain:1": "event.app_style.scouts_choam_bargain1",
        "choam_coordination:0": "subcommittee.app_style.scouts_choam_coordination0",
        "choam_escort:0": "mission.app_style.scouts_choam_escort0",
        "choam_escort:1": "mission.app_style.scouts_choam_escort1",
        "choam_management:0": "subcommittee.app_style.scouts_choam_management0",
        "choam_negotiations_late:0": "auction.app_style.scouts_choam_negotiations_late0",
        "choam_negotiations_late:1": "auction.app_style.scouts_choam_negotiations_late1",
        "choam_negotiations_mid:0": "auction.app_style.scouts_choam_negotiations_mid0",
        "competitive_study_late:0": "auction.app_style.scouts_competitive_study_late0",
        "competitive_study_late:1": "auction.app_style.scouts_competitive_study_late1",
        "competitive_study_mid:0": "auction.app_style.scouts_competitive_study_mid0",
        "contingencies:0": "subcommittee.app_style.scouts_contingencies0",
        "coordinate_with_the_emperor:0": "mission.app_style.scouts_coordinate_with_the_emperor0",
        "covert_assistance:0": "event.app_style.scouts_covert_assistance0",
        "covert_operation:0": "event.app_style.scouts_covert_operation0",
        "covert_operation:1": "event.app_style.scouts_covert_operation1",
        "covert_operation:2": "event.app_style.scouts_covert_operation2",
        "covert_operation:3": "event.app_style.scouts_covert_operation3",
        "covert_operation_choam:0": "event.app_style.scouts_covert_operation_choam0",
        "covert_operation_choam:1": "event.app_style.scouts_covert_operation_choam1",
        "covert_operation_choam:2": "event.app_style.scouts_covert_operation_choam2",
        "covert_operation_choam:3": "event.app_style.scouts_covert_operation_choam3",
        "crackdown:0": "event.app_style.scouts_crackdown0",
        "crackdown:1": "event.app_style.scouts_crackdown1",
        "desert_gift:0": "event.app_style.scouts_desert_gift0",
        "development:0": "subcommittee.app_style.scouts_development0",
        "emperors_tax:0": "event.app_style.scouts_emperors_tax0",
        "emperors_tax:1": "event.app_style.scouts_emperors_tax1",
        "fedaykin_assistance:0": "mission.app_style.scouts_fedaykin_assistance0",
        "forecasting:0": "subcommittee.app_style.scouts_forecasting0",
        "fremen_exchange:0": "event.app_style.scouts_fremen_exchange0",
        "fremen_exchange:1": "event.app_style.scouts_fremen_exchange1",
        "fremen_mercenaries:0": "sale.app_style.scouts_fremen_mercenaries0",
        "fremen_mercenaries:1": "sale.app_style.scouts_fremen_mercenaries1",
        "fremen_mercenaries:2": "sale.app_style.scouts_fremen_mercenaries2",
        "fremen_mercenaries:3": "sale.app_style.scouts_fremen_mercenaries3",
        "fremen_mercenaries:4": "sale.app_style.scouts_fremen_mercenaries4",
        "fremen_mercenaries:5": "sale.app_style.scouts_fremen_mercenaries5",
        "funeral_rites:0": "event.app_style.scouts_funeral_rites0",
        "funeral_rites:1": "event.app_style.scouts_funeral_rites1",
        "genetic_research:0": "mission.app_style.scouts_genetic_research0",
        "gift_of_water:0": "event.app_style.scouts_gift_of_water0",
        "growth_project:0": "subcommittee.app_style.scouts_growth_project0",
        "guild_maneuvers:0": "mission.app_style.scouts_guild_maneuvers0",
        "guild_negotiation:0": "event.app_style.scouts_guild_negotiation0",
        "highest_bidder_late:0": "auction.app_style.scouts_highest_bidder_late0",
        "highest_bidder_late:1": "auction.app_style.scouts_highest_bidder_late1",
        "highest_bidder_mid:0": "auction.app_style.scouts_highest_bidder_mid0",
        "imperium_appropriations:0": "subcommittee.app_style.scouts_imperium_appropriations0",
        "imperium_bene_gesserit_treachery:0": "event.app_style.scouts_imperium_bene_gesserit_treachery0",
        "imperium_bene_gesserit_treachery:1": "event.app_style.scouts_imperium_bene_gesserit_treachery1",
        "imperium_connections:0": "sale.app_style.scouts_imperium_connections0",
        "imperium_connections:1": "sale.app_style.scouts_imperium_connections1",
        "imperium_coordinate_with_the_emperor:0": "mission.app_style.scouts_imperium_coordinate_with_the_emperor0",
        "imperium_covert_operation:0": "event.app_style.scouts_imperium_covert_operation0",
        "imperium_covert_operation:1": "event.app_style.scouts_imperium_covert_operation1",
        "imperium_covert_operation:2": "event.app_style.scouts_imperium_covert_operation2",
        "imperium_covert_operation:3": "event.app_style.scouts_imperium_covert_operation3",
        "imperium_gift_of_water:0": "event.app_style.scouts_imperium_gift_of_water0",
        "imperium_guild_negotiation:0": "event.app_style.scouts_imperium_guild_negotiation0",
        "imperium_intelligence:0": "subcommittee.app_style.scouts_imperium_intelligence0",
        "imperium_oversight:0": "subcommittee.app_style.scouts_imperium_oversight0",
        "imperium_political_equilibrium:0": "event.app_style.scouts_imperium_political_equilibrium0",
        "imperium_rotating_doors:0": "event.app_style.scouts_imperium_rotating_doors0",
        "imperium_secrets_for_sale:0": "event.app_style.scouts_imperium_secrets_for_sale0",
        "imperium_secrets_for_sale:1": "event.app_style.scouts_imperium_secrets_for_sale1",
        "imperium_water_for_spice_smugglers:0": "event.app_style.scouts_imperium_water_for_spice_smugglers0",
        "imperium_water_for_spice_smugglers:1": "event.app_style.scouts_imperium_water_for_spice_smugglers1",
        "ingratiate:0": "event.app_style.scouts_ingratiate0",
        "intelligence:0": "subcommittee.app_style.scouts_intelligence0",
        "intriguing_gift:0": "event.app_style.scouts_intriguing_gift0",
        "investigations:0": "subcommittee.app_style.scouts_investigations0",
        "joint_forces:0": "subcommittee.app_style.scouts_joint_forces0",
        "leverage:0": "subcommittee.app_style.scouts_leverage0",
        "market_research:0": "event.app_style.scouts_market_research0",
        "moment_of_revelation:0": "event.app_style.scouts_moment_of_revelation0",
        "muster_strongarmed_alliance:0": "mission.app_style.scouts_muster_strongarmed_alliance0",
        "new_innovations:0": "event.app_style.scouts_new_innovations0",
        "new_innovations:1": "event.app_style.scouts_new_innovations1",
        "no_coming_back:0": "event.app_style.scouts_no_coming_back0",
        "no_coming_back:1": "event.app_style.scouts_no_coming_back1",
        "no_coming_back:2": "event.app_style.scouts_no_coming_back2",
        "offworld_operation:0": "event.app_style.scouts_offworld_operation0",
        "offworld_operation:1": "event.app_style.scouts_offworld_operation1",
        "offworld_operation:2": "event.app_style.scouts_offworld_operation2",
        "offworld_operation:3": "event.app_style.scouts_offworld_operation3",
        "oversight:0": "subcommittee.app_style.scouts_oversight0",
        "political_affairs:0": "subcommittee.app_style.scouts_political_affairs0",
        "political_equilibrium:0": "event.app_style.scouts_political_equilibrium0",
        "prison_planet:0": "mission.app_style.scouts_prison_planet0",
        "private_stock:0": "event.app_style.scouts_private_stock0",
        "private_stock:1": "event.app_style.scouts_private_stock1",
        "readiness:0": "subcommittee.app_style.scouts_readiness0",
        "rebuild_infrastructure:0": "event.app_style.scouts_rebuild_infrastructure0",
        "relations:0": "subcommittee.app_style.scouts_relations0",
        "rotating_doors:0": "event.app_style.scouts_rotating_doors0",
        "royal_delegation:0": "event.app_style.scouts_royal_delegation0",
        "sapho_juice:0": "mission.app_style.scouts_sapho_juice0",
        "secrets_for_sale:0": "sale.app_style.scouts_secrets_for_sale0",
        "secrets_for_sale:1": "sale.app_style.scouts_secrets_for_sale1",
        "security_detail:0": "mission.app_style.scouts_security_detail0",
        "send_for_aid:0": "mission.app_style.scouts_send_for_aid0",
        "shadow_warfare:0": "sale.app_style.scouts_shadow_warfare0",
        "shadow_warfare:1": "sale.app_style.scouts_shadow_warfare1",
        "share_intelligence:0": "event.app_style.scouts_share_intelligence0",
        "smoke_and_mirrors:0": "event.app_style.scouts_smoke_and_mirrors0",
        "smoke_and_mirrors:1": "event.app_style.scouts_smoke_and_mirrors1",
        "spies_for_hire_late:0": "auction.app_style.scouts_spies_for_hire_late0",
        "spies_for_hire_late:1": "auction.app_style.scouts_spies_for_hire_late1",
        "spies_for_hire_mid:0": "auction.app_style.scouts_spies_for_hire_mid0",
        "stowaways:0": "mission.app_style.scouts_stowaways0",
        "termination_request:0": "event.app_style.scouts_termination_request0",
        "test_of_loyalty:0": "event.app_style.scouts_test_of_loyalty0",
        "tleilaxu_offering:0": "mission.app_style.scouts_tleilaxu_offering0",
        "tleilaxu_relations:0": "subcommittee.app_style.scouts_tleilaxu_relations0",
        "treachery_late:0": "auction.app_style.scouts_treachery_late0",
        "treachery_late:1": "auction.app_style.scouts_treachery_late1",
        "treachery_mid:0": "auction.app_style.scouts_treachery_mid0",
        "unravel_the_future:0": "sale.app_style.scouts_unravel_the_future0",
        "unravel_the_future:1": "sale.app_style.scouts_unravel_the_future1",
        "water_discipline:0": "event.app_style.scouts_water_discipline0",
        "water_for_spice_smugglers:0": "event.app_style.scouts_water_for_spice_smugglers0",
        "water_for_spice_smugglers:1": "event.app_style.scouts_water_for_spice_smugglers1",
        "water_peddlers:0": "sale.app_style.scouts_water_peddlers0",
        "water_peddlers:1": "sale.app_style.scouts_water_peddlers1",
        "weirding_warfare:0": "mission.app_style.scouts_weirding_warfare0",
    }
)
