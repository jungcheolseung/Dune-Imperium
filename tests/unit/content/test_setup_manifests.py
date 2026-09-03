"""Integrity tests for setup-relevant Uprising card manifests."""

from collections import Counter

import pytest

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflicts import (
    CONFLICTS,
    CONFLICTS_BY_ID,
    ConflictReward,
    conflicts_by_tier,
)
from dune_imperium.content.uprising.contracts import (
    CONTRACTS,
    ContractCondition,
    ContractConditionKind,
    ContractReward,
    contract_for_instance,
    contract_instance_ids,
)
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    imperium_card_for_instance,
    imperium_cards_for_choam,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS,
    intrigue_cards_for_choam,
    intrigue_deck_instance_ids,
)
from dune_imperium.content.uprising.leaders import LEADERS, leaders_for_choam
from dune_imperium.content.uprising.objectives import (
    OBJECTIVES,
    objectives_for_players,
)
from dune_imperium.content.uprising.reserve import (
    RESERVE_STACKS,
    RESERVE_STACKS_BY_ID,
    reserve_card_for_instance,
)
from dune_imperium.content.uprising.types import (
    AgentIcon,
    BattleIcon,
    ConflictTier,
    PersonalCardAgentEffect,
)


def test_conflict_manifest_has_the_official_tier_counts() -> None:
    assert len(CONFLICTS) == 16
    assert len({conflict.card.card_id for conflict in CONFLICTS}) == 16
    assert Counter(conflict.tier for conflict in CONFLICTS) == {
        ConflictTier.ONE: 3,
        ConflictTier.TWO: 9,
        ConflictTier.THREE: 4,
    }
    assert all(conflict.card.catalog_url for conflict in CONFLICTS)


def test_tier_one_conflict_rewards_and_battle_icons_are_transcribed() -> None:
    crysknife = CONFLICTS_BY_ID["skirmish_crysknife"]
    ornithopter = CONFLICTS_BY_ID["skirmish_ornithopter"]
    desert_mouse = CONFLICTS_BY_ID["skirmish_desert_mouse"]

    assert crysknife.battle_icon is BattleIcon.CRYSKNIFE
    assert crysknife.rewards == (
        ConflictReward(choose_influence=1),
        ConflictReward(spice=1, intrigue=1),
        ConflictReward(spice=1),
    )
    assert ornithopter.battle_icon is BattleIcon.ORNITHOPTER
    assert ornithopter.rewards == (
        ConflictReward(solari=1, intrigue=1),
        ConflictReward(solari=2, intrigue=1),
        ConflictReward(intrigue=1),
    )
    assert desert_mouse.battle_icon is BattleIcon.DESERT_MOUSE
    assert desert_mouse.rewards == (
        ConflictReward(solari=2),
        ConflictReward(solari=3),
        ConflictReward(solari=2),
    )
    assert all(
        conflict.rewards is not None and conflict.battle_icon is not None
        for conflict in conflicts_by_tier(ConflictTier.ONE)
    )


def test_tier_two_conflict_rewards_and_battle_icons_are_transcribed() -> None:
    expected = {
        "choam_security": (
            BattleIcon.CRYSKNIFE,
            False,
            (
                ConflictReward(
                    troops=1,
                    contracts=1,
                    faction_influence=1,
                    influence_faction=Faction.SPACING_GUILD,
                ),
                ConflictReward(solari=2, water=1, troops=2),
                ConflictReward(intrigue=1, troops=1),
            ),
        ),
        "spice_freighters": (
            BattleIcon.CRYSKNIFE,
            False,
            (
                ConflictReward(
                    choose_influence=1,
                    optional_spice_cost=3,
                    optional_victory_points=1,
                ),
                ConflictReward(spice=1, water=1, troops=1),
                ConflictReward(spice=1, troops=1),
            ),
        ),
        "siege_of_arrakeen": (
            BattleIcon.ORNITHOPTER,
            True,
            (
                ConflictReward(
                    solari=2,
                    troops=2,
                    control_space_id="arrakeen",
                ),
                ConflictReward(solari=4, troops=1),
                ConflictReward(solari=3),
            ),
        ),
        "seize_spice_refinery": (
            BattleIcon.CRYSKNIFE,
            True,
            (
                ConflictReward(
                    spice=2,
                    place_spies=1,
                    control_space_id="spice_refinery",
                ),
                ConflictReward(spice=1, intrigue=1, troops=1),
                ConflictReward(spice=2),
            ),
        ),
        "test_of_loyalty": (
            BattleIcon.ORNITHOPTER,
            False,
            (
                ConflictReward(
                    solari=2,
                    place_spies=1,
                    faction_influence=1,
                    influence_faction=Faction.EMPEROR,
                ),
                ConflictReward(solari=4, troops=1),
                ConflictReward(solari=3),
            ),
        ),
        "shadow_contest": (
            BattleIcon.ORNITHOPTER,
            False,
            (
                ConflictReward(
                    intrigue=1,
                    faction_influence=1,
                    influence_faction=Faction.BENE_GESSERIT,
                ),
                ConflictReward(spice=1, intrigue=1, troops=1),
                ConflictReward(spice=1, troops=1),
            ),
        ),
        "secure_imperial_basin": (
            BattleIcon.DESERT_MOUSE,
            True,
            (
                ConflictReward(
                    spice=2,
                    troops=1,
                    control_space_id="imperial_basin",
                ),
                ConflictReward(water=2, troops=1),
                ConflictReward(water=1, troops=1),
            ),
        ),
        "protect_the_sietches": (
            BattleIcon.DESERT_MOUSE,
            False,
            (
                ConflictReward(
                    water=1,
                    troops=1,
                    faction_influence=1,
                    influence_faction=Faction.FREMEN,
                ),
                ConflictReward(spice=3, troops=1),
                ConflictReward(spice=2),
            ),
        ),
        "trade_dispute": (
            BattleIcon.DESERT_MOUSE,
            False,
            (
                ConflictReward(water=1, contracts=1, trash_cards=1),
                ConflictReward(spice=1, water=1, trash_cards=1),
                ConflictReward(water=1, troops=1),
            ),
        ),
    }

    assert {
        conflict.card.card_id: (
            conflict.battle_icon,
            conflict.shield_wall_protected,
            conflict.rewards,
        )
        for conflict in conflicts_by_tier(ConflictTier.TWO)
    } == expected


def test_tier_three_conflict_rewards_and_icons_are_transcribed() -> None:
    expected = {
        "propaganda": (
            BattleIcon.WILD,
            False,
            (
                ConflictReward(choose_distinct_influence=2),
                ConflictReward(spice=3, intrigue=1),
                ConflictReward(spice=3),
            ),
        ),
        "battle_for_imperial_basin": (
            BattleIcon.ORNITHOPTER,
            True,
            (
                ConflictReward(
                    victory_points=1,
                    control_space_id="imperial_basin",
                    optional_spice_cost=4,
                    optional_victory_points=1,
                ),
                ConflictReward(spice=5),
                ConflictReward(spice=3),
            ),
        ),
        "battle_for_arrakeen": (
            BattleIcon.CRYSKNIFE,
            True,
            (
                ConflictReward(
                    victory_points=1,
                    control_space_id="arrakeen",
                    optional_recall_spies=2,
                    optional_victory_points=1,
                ),
                ConflictReward(solari=3, spice=1, intrigue=1),
                ConflictReward(solari=2, spice=2),
            ),
        ),
        "battle_for_spice_refinery": (
            BattleIcon.DESERT_MOUSE,
            True,
            (
                ConflictReward(
                    victory_points=1,
                    control_space_id="spice_refinery",
                    optional_solari_cost=6,
                    optional_victory_points=1,
                ),
                ConflictReward(spice=3, intrigue=1),
                ConflictReward(spice=3),
            ),
        ),
    }

    assert {
        conflict.card.card_id: (
            conflict.battle_icon,
            conflict.shield_wall_protected,
            conflict.rewards,
        )
        for conflict in conflicts_by_tier(ConflictTier.THREE)
    } == expected


def test_conflict_reward_rejects_incomplete_compound_effects() -> None:
    with pytest.raises(ValueError, match="fixed Influence"):
        ConflictReward(faction_influence=1)
    with pytest.raises(ValueError, match="cost and reward"):
        ConflictReward(optional_spice_cost=3)
    with pytest.raises(ValueError, match="one cost type"):
        ConflictReward(
            optional_spice_cost=3,
            optional_solari_cost=2,
            optional_victory_points=1,
        )


def test_reserve_play_data_matches_the_printed_cards() -> None:
    prepare = RESERVE_STACKS_BY_ID["prepare_the_way"]
    spice = RESERVE_STACKS_BY_ID["the_spice_must_flow"]

    assert prepare.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.CITY)
    assert prepare.agent_effect is (
        PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
    )
    assert prepare.reveal_persuasion == 2
    assert prepare.reveal_strength == 0
    assert spice.agent_icons == ()
    assert spice.agent_effect is None
    assert spice.reveal_persuasion == 0
    assert spice.reveal_strength == 1


def test_reserve_instance_ids_resolve_and_validate_copy_bounds() -> None:
    assert (
        reserve_card_for_instance("reserve:prepare_the_way:7").card.card_id
        == "prepare_the_way"
    )
    with pytest.raises(ValueError, match="copy index"):
        reserve_card_for_instance("reserve:prepare_the_way:8")


def test_base_setup_excludes_only_the_choam_leader() -> None:
    assert len(LEADERS) == 9
    assert len(leaders_for_choam(choam_module=False)) == 8
    assert len(leaders_for_choam(choam_module=True)) == 9
    assert {leader.leader_id for leader in LEADERS if leader.choam_only} == {
        "shaddam_corrino_iv"
    }


def test_leader_specific_setup_metadata_is_explicit() -> None:
    leaders = {leader.leader_id: leader for leader in LEADERS}

    assert leaders["feyd_rautha_harkonnen"].uses_feyd_token is True
    assert leaders["lady_jessica"].setup_face_id == "lady_jessica"
    assert leaders["lady_jessica"].alternate_face_id == "reverend_mother_jessica"


def test_four_player_objective_suite_matches_the_official_components() -> None:
    assert len(OBJECTIVES) == 5

    objectives = objectives_for_players(4)

    assert len(objectives) == 4
    assert Counter(objective.battle_icon for objective in objectives) == {
        BattleIcon.DESERT_MOUSE: 2,
        BattleIcon.CRYSKNIFE: 2,
    }
    assert sum(objective.grants_first_player for objective in objectives) == 1
    assert {
        objective.objective_id
        for objective in objectives
        if objective.grants_first_player
    } == {"objective_desert_mouse"}
    assert all(
        objective.objective_id != "objective_ornithopter_1_3p"
        for objective in objectives
    )


def test_reserve_stacks_are_finite_and_have_no_foldspace() -> None:
    assert {stack.card.card_id: stack.copies for stack in RESERVE_STACKS} == {
        "prepare_the_way": 8,
        "the_spice_must_flow": 10,
    }
    assert {
        card_id: (stack.acquisition_cost, stack.acquisition_vp)
        for card_id, stack in RESERVE_STACKS_BY_ID.items()
    } == {
        "prepare_the_way": (2, 0),
        "the_spice_must_flow": (9, 1),
    }


def test_imperium_manifest_matches_base_and_choam_counts() -> None:
    assert len(IMPERIUM_CARDS) == 57
    assert sum(entry.copies for entry in IMPERIUM_CARDS) == 72
    assert sum(entry.copies for entry in imperium_cards_for_choam(False)) == 65
    # The three Uprising promo cards join either ruleset only on request.
    assert {entry.card.card_id for entry in IMPERIUM_CARDS if entry.promo} == {
        "arrakis_revolt",
        "pivotal_gambit",
        "the_beast_s_spoils",
    }
    assert sum(entry.copies for entry in imperium_cards_for_choam(False, True)) == 68
    assert sum(entry.copies for entry in imperium_cards_for_choam(True, True)) == 72
    assert not any(entry.promo and entry.choam_only for entry in IMPERIUM_CARDS)
    assert {entry.card.card_id for entry in IMPERIUM_CARDS if entry.choam_only} == {
        "cargo_runner",
        "delivery_agreement",
        "interstellar_trade",
        "priority_contracts",
    }
    assert all(entry.acquisition_cost is not None for entry in IMPERIUM_CARDS)


def test_intrigue_manifest_matches_base_and_choam_counts() -> None:
    assert len(INTRIGUE_CARDS) == 39
    assert sum(entry.copies for entry in INTRIGUE_CARDS) == 44
    assert sum(entry.copies for entry in intrigue_cards_for_choam(False)) == 40
    assert {entry.card.card_id for entry in INTRIGUE_CARDS if entry.choam_only} == {
        "backed_by_choam",
        "choam_profits",
        "leverage",
        "reach_agreement",
    }
    assert (
        next(
            entry.copies
            for entry in INTRIGUE_CARDS
            if entry.card.card_id == "special_mission"
        )
        == 2
    )


def test_shared_deck_manifests_have_unique_ids_urls_and_instances() -> None:
    for entries in (IMPERIUM_CARDS, INTRIGUE_CARDS):
        ids = tuple(entry.card.card_id for entry in entries)
        assert len(ids) == len(set(ids))
        # The Uprising promo cards have no Dune Cards Hub catalog page.
        assert all(
            entry.card.catalog_url for entry in entries if not entry.promo
        )
        assert all(entry.card.catalog_url is None for entry in entries if entry.promo)

    for instance_ids, expected in (
        (imperium_deck_instance_ids(False), 65),
        (imperium_deck_instance_ids(True), 69),
        (intrigue_deck_instance_ids(False), 40),
        (intrigue_deck_instance_ids(True), 44),
    ):
        assert len(instance_ids) == len(set(instance_ids)) == expected


def test_standard_contract_manifest_has_twenty_unique_physical_tiles() -> None:
    instances = contract_instance_ids()

    assert len(CONTRACTS) == len(instances) == len(set(instances)) == 20
    assert len({contract.card.card_id for contract in CONTRACTS}) == 20
    assert all(contract.card.catalog_url for contract in CONTRACTS)
    assert {
        contract.card.card_id
        for contract in CONTRACTS
        if contract.completes_immediately
    } == {"immediate"}
    assert contract_for_instance("contract:high_council_ii").card.name == (
        "High Council II"
    )


def test_standard_contract_manifest_transcribes_printed_conditions_and_rewards() -> (
    None
):
    printed = {
        contract.card.card_id: (contract.condition, contract.reward)
        for contract in CONTRACTS
    }

    assert printed == {
        "acquire": (
            ContractCondition(
                ContractConditionKind.ACQUIRE_CARD,
                target="the_spice_must_flow",
            ),
            ContractReward(
                solari=3,
                influence_faction=Faction.SPACING_GUILD,
                influence=1,
            ),
        ),
        "arrakeen_i": (
            ContractCondition(ContractConditionKind.BOARD_SPACE, target="arrakeen"),
            ContractReward(water=1),
        ),
        "arrakeen_ii": (
            ContractCondition(ContractConditionKind.BOARD_SPACE, target="arrakeen"),
            ContractReward(troops=1, spies=1),
        ),
        "deliver_supplies": (
            ContractCondition(
                ContractConditionKind.BOARD_SPACE,
                target="deliver_supplies",
            ),
            ContractReward(solari=3),
        ),
        "espionage_i": (
            ContractCondition(ContractConditionKind.BOARD_SPACE, target="espionage"),
            ContractReward(solari=3),
        ),
        "espionage_ii": (
            ContractCondition(ContractConditionKind.BOARD_SPACE, target="espionage"),
            ContractReward(solari=1, contracts=1),
        ),
        "harvest_3": (
            ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=3),
            ContractReward(solari=3),
        ),
        "harvest_3_contract": (
            ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=3),
            ContractReward(contracts=1),
        ),
        "harvest_4": (
            ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=4),
            ContractReward(solari=4),
        ),
        "harvest_4_contract": (
            ContractCondition(ContractConditionKind.HARVEST_SPICE, amount=4),
            ContractReward(solari=2, contracts=1),
        ),
        "heighliner_i": (
            ContractCondition(ContractConditionKind.BOARD_SPACE, target="heighliner"),
            ContractReward(water=2),
        ),
        "heighliner_ii": (
            ContractCondition(ContractConditionKind.BOARD_SPACE, target="heighliner"),
            ContractReward(troops=2),
        ),
        "heighliner_iii": (
            ContractCondition(ContractConditionKind.BOARD_SPACE, target="heighliner"),
            ContractReward(solari=3, contracts=1),
        ),
        "high_council_i": (
            ContractCondition(
                ContractConditionKind.BOARD_SPACE,
                target="high_council",
            ),
            ContractReward(
                influence_faction=Faction.BENE_GESSERIT,
                influence=1,
            ),
        ),
        "high_council_ii": (
            ContractCondition(
                ContractConditionKind.BOARD_SPACE,
                target="high_council",
            ),
            ContractReward(solari=3),
        ),
        "immediate": (
            ContractCondition(ContractConditionKind.IMMEDIATE),
            ContractReward(solari=2),
        ),
        "research_station_i": (
            ContractCondition(
                ContractConditionKind.BOARD_SPACE,
                target="research_station",
            ),
            ContractReward(solari=2, spies=1),
        ),
        "research_station_ii": (
            ContractCondition(
                ContractConditionKind.BOARD_SPACE,
                target="research_station",
            ),
            ContractReward(solari=3),
        ),
        "sardaukar_i": (
            ContractCondition(ContractConditionKind.BOARD_SPACE, target="sardaukar"),
            ContractReward(personal_cards=2),
        ),
        "sardaukar_ii": (
            ContractCondition(ContractConditionKind.BOARD_SPACE, target="sardaukar"),
            ContractReward(recall_agents=1),
        ),
    }


def test_imperium_costs_cover_the_printed_range_and_resolve_instances() -> None:
    costs = {entry.card.card_id: entry.acquisition_cost for entry in IMPERIUM_CARDS}

    assert Counter(costs.values()) == {
        1: 5,
        2: 9,
        3: 15,
        4: 8,
        5: 9,
        6: 7,
        7: 2,
        8: 2,
    }
    assert min(cost for cost in costs.values() if cost is not None) == 1
    assert max(cost for cost in costs.values() if cost is not None) == 8
    assert costs["sardaukar_soldier"] == 1
    assert costs["bene_gesserit_operative"] == 3
    assert costs["overthrow"] == 8
    assert {
        entry.card.card_id for entry in IMPERIUM_CARDS if entry.has_acquisition_bonus
    } == {
        "arrakis_revolt",
        "guild_spy",
        "in_high_places",
        "interstellar_trade",
        "overthrow",
        "price_is_no_object",
        "spy_network",
        "steersman",
        "strike_fleet",
        "subversive_advisor",
    }
    instance = imperium_deck_instance_ids(False)[0]
    assert imperium_card_for_instance(instance).card.card_id in costs
