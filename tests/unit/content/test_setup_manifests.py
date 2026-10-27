"""Integrity tests for setup-relevant Uprising card manifests."""

from collections import Counter

import pytest

from dune_imperium.content.uprising.abilities import Ability, AbilityTiming
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflicts import (
    CONFLICTS,
    CONFLICTS_BY_ID,
    ConflictDefinition,
    check_conflict_reward_row,
    conflicts_by_tier,
)
from dune_imperium.content.uprising.contracts import (
    BLOODLINES_CONTRACTS,
    CONTRACTS,
    CONTRACTS_BY_ID,
    STANDARD_CONTRACTS,
    ContractDefinition,
    contract_for_instance,
    contract_instance_ids,
)
from dune_imperium.content.uprising.effect_dsl import (
    AcquiredCard,
    AllConditions,
    AllianceTaken,
    AtBoardSpace,
    AtMakerSpace,
    ContractTaken,
    DrawPersonalCards,
    EffectSection,
    GainedSpiceThisTurn,
    GainResources,
    GainVictoryPoints,
    HasHighCouncil,
    PayResources,
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
from dune_imperium.content.uprising.personal_cards import PersonalCardDefinition
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
from dune_imperium.display.structs import (
    ConflictRowParts,
    ContractRewardParts,
    conflict_row_parts,
    contract_reward_parts,
)
from dune_imperium.display.tokens import reveal_effect_text
from dune_imperium.rules.reveal_lines import reveal_lines


def _reveal_texts(card: PersonalCardDefinition) -> tuple[str, ...]:
    """The card's Reveal record, line by line, as its card text reads."""

    return tuple(reveal_effect_text(line) for line in reveal_lines(card))


def _rows(conflict: ConflictDefinition) -> tuple[ConflictRowParts, ...]:
    """A Conflict's three reward rows, read off their records piece by piece."""

    assert conflict.reward_rows is not None
    return tuple(conflict_row_parts(row) for row in conflict.reward_rows)


def _reward(contract: ContractDefinition) -> ContractRewardParts:
    """A Contract's reward line, read off its record piece by piece."""

    return contract_reward_parts(contract.reward_line)


def _harvest(amount: int) -> AllConditions:
    """ "Send an Agent to a Maker space and gain N or more spice that turn"."""

    return AllConditions((AtMakerSpace(), GainedSpiceThisTurn(amount)))


def test_conflict_manifest_has_the_official_tier_counts() -> None:
    # 16 Uprising cards plus the two Bloodlines cards (one I, one II), which
    # only enter the pool with the option [Bloodlines p. 3], and Rise of Ix's
    # Economic Supremacy, a fifth III only in Epic Game Mode [Main p. 18].
    assert len(CONFLICTS) == 19
    assert len({conflict.card.card_id for conflict in CONFLICTS}) == 19
    retail = tuple(
        conflict
        for conflict in CONFLICTS
        if not conflict.bloodlines_only and not conflict.epic_only
    )
    assert Counter(conflict.tier for conflict in retail) == {
        ConflictTier.ONE: 3,
        ConflictTier.TWO: 9,
        ConflictTier.THREE: 4,
    }
    assert Counter(
        conflict.tier for conflict in CONFLICTS if conflict.bloodlines_only
    ) == {ConflictTier.ONE: 1, ConflictTier.TWO: 1}
    assert [
        conflict.card.card_id for conflict in CONFLICTS if conflict.epic_only
    ] == ["economic_supremacy"]
    assert all(conflict.card.catalog_url for conflict in CONFLICTS)


def test_tier_one_conflict_rewards_and_battle_icons_are_transcribed() -> None:
    crysknife = CONFLICTS_BY_ID["skirmish_crysknife"]
    ornithopter = CONFLICTS_BY_ID["skirmish_ornithopter"]
    desert_mouse = CONFLICTS_BY_ID["skirmish_desert_mouse"]

    assert crysknife.battle_icon is BattleIcon.CRYSKNIFE
    assert _rows(crysknife) == (
        ConflictRowParts(choose_influence=1),
        ConflictRowParts(spice=1, intrigue=1),
        ConflictRowParts(spice=1),
    )
    assert ornithopter.battle_icon is BattleIcon.ORNITHOPTER
    assert _rows(ornithopter) == (
        ConflictRowParts(solari=1, intrigue=1),
        ConflictRowParts(solari=2, intrigue=1),
        ConflictRowParts(intrigue=1),
    )
    assert desert_mouse.battle_icon is BattleIcon.DESERT_MOUSE
    assert _rows(desert_mouse) == (
        ConflictRowParts(solari=2),
        ConflictRowParts(solari=3),
        ConflictRowParts(solari=2),
    )
    assert all(
        conflict.reward_rows is not None and conflict.battle_icon is not None
        for conflict in conflicts_by_tier(ConflictTier.ONE)
    )


def test_tier_two_conflict_rewards_and_battle_icons_are_transcribed() -> None:
    expected = {
        "choam_security": (
            BattleIcon.CRYSKNIFE,
            False,
            (
                ConflictRowParts(
                    troops=1,
                    contracts=1,
                    faction_influence=1,
                    influence_faction=Faction.SPACING_GUILD,
                ),
                ConflictRowParts(solari=2, water=1, troops=2),
                ConflictRowParts(intrigue=1, troops=1),
            ),
        ),
        "spice_freighters": (
            BattleIcon.CRYSKNIFE,
            False,
            (
                ConflictRowParts(
                    choose_influence=1,
                    optional_spice_cost=3,
                    optional_victory_points=1,
                ),
                ConflictRowParts(spice=1, water=1, troops=1),
                ConflictRowParts(spice=1, troops=1),
            ),
        ),
        "siege_of_arrakeen": (
            BattleIcon.ORNITHOPTER,
            True,
            (
                ConflictRowParts(
                    solari=2,
                    troops=2,
                    control_space_id="arrakeen",
                ),
                ConflictRowParts(solari=4, troops=1),
                ConflictRowParts(solari=3),
            ),
        ),
        "seize_spice_refinery": (
            BattleIcon.CRYSKNIFE,
            True,
            (
                ConflictRowParts(
                    spice=2,
                    place_spies=1,
                    control_space_id="spice_refinery",
                ),
                ConflictRowParts(spice=1, intrigue=1, troops=1),
                ConflictRowParts(spice=2),
            ),
        ),
        "test_of_loyalty": (
            BattleIcon.ORNITHOPTER,
            False,
            (
                ConflictRowParts(
                    solari=2,
                    place_spies=1,
                    faction_influence=1,
                    influence_faction=Faction.EMPEROR,
                ),
                ConflictRowParts(solari=4, troops=1),
                ConflictRowParts(solari=3),
            ),
        ),
        "shadow_contest": (
            BattleIcon.ORNITHOPTER,
            False,
            (
                ConflictRowParts(
                    intrigue=1,
                    faction_influence=1,
                    influence_faction=Faction.BENE_GESSERIT,
                ),
                ConflictRowParts(spice=1, intrigue=1, troops=1),
                ConflictRowParts(spice=1, troops=1),
            ),
        ),
        "secure_imperial_basin": (
            BattleIcon.DESERT_MOUSE,
            True,
            (
                ConflictRowParts(
                    spice=2,
                    troops=1,
                    control_space_id="imperial_basin",
                ),
                ConflictRowParts(water=2, troops=1),
                ConflictRowParts(water=1, troops=1),
            ),
        ),
        "protect_the_sietches": (
            BattleIcon.DESERT_MOUSE,
            False,
            (
                ConflictRowParts(
                    water=1,
                    troops=1,
                    faction_influence=1,
                    influence_faction=Faction.FREMEN,
                ),
                ConflictRowParts(spice=3, troops=1),
                ConflictRowParts(spice=2),
            ),
        ),
        "trade_dispute": (
            BattleIcon.DESERT_MOUSE,
            False,
            (
                ConflictRowParts(water=1, contracts=1, trash_cards=1),
                ConflictRowParts(spice=1, water=1, trash_cards=1),
                ConflictRowParts(water=1, troops=1),
            ),
        ),
    }

    assert {
        conflict.card.card_id: (
            conflict.battle_icon,
            conflict.shield_wall_protected,
            _rows(conflict),
        )
        for conflict in conflicts_by_tier(ConflictTier.TWO)
    } == expected


def test_tier_three_conflict_rewards_and_icons_are_transcribed() -> None:
    expected = {
        "propaganda": (
            BattleIcon.WILD,
            False,
            (
                ConflictRowParts(choose_distinct_influence=2),
                ConflictRowParts(spice=3, intrigue=1),
                ConflictRowParts(spice=3),
            ),
        ),
        "battle_for_imperial_basin": (
            BattleIcon.ORNITHOPTER,
            True,
            (
                ConflictRowParts(
                    victory_points=1,
                    control_space_id="imperial_basin",
                    optional_spice_cost=4,
                    optional_victory_points=1,
                ),
                ConflictRowParts(spice=5),
                ConflictRowParts(spice=3),
            ),
        ),
        "battle_for_arrakeen": (
            BattleIcon.CRYSKNIFE,
            True,
            (
                ConflictRowParts(
                    victory_points=1,
                    control_space_id="arrakeen",
                    optional_recall_spies=2,
                    optional_victory_points=1,
                ),
                ConflictRowParts(solari=3, spice=1, intrigue=1),
                ConflictRowParts(solari=2, spice=2),
            ),
        ),
        "battle_for_spice_refinery": (
            BattleIcon.DESERT_MOUSE,
            True,
            (
                ConflictRowParts(
                    victory_points=1,
                    control_space_id="spice_refinery",
                    optional_solari_cost=6,
                    optional_victory_points=1,
                ),
                ConflictRowParts(spice=3, intrigue=1),
                ConflictRowParts(spice=3),
            ),
        ),
    }

    assert {
        conflict.card.card_id: (
            conflict.battle_icon,
            conflict.shield_wall_protected,
            _rows(conflict),
        )
        for conflict in conflicts_by_tier(ConflictTier.THREE)
    } == expected


def _row(*lines: EffectSection) -> Ability:
    return Ability(timing=AbilityTiming.CONFLICT_REWARD, sections=lines)


def test_a_conflict_reward_row_the_payer_cannot_read_is_refused() -> None:
    """The checks the compiled ``ConflictReward`` ran, now on the record."""

    def arrow(cost: PayResources, points: int) -> EffectSection:
        return EffectSection(rewards=(GainVictoryPoints(points),), costs=(cost,))

    with pytest.raises(ValueError, match="share one VP value"):
        check_conflict_reward_row(
            _row(arrow(PayResources(spice=3), 1), arrow(PayResources(solari=6), 2))
        )
    with pytest.raises(TypeError, match="not a Conflict reward arrow"):
        check_conflict_reward_row(
            _row(
                EffectSection(
                    rewards=(GainResources(spice=1),), costs=(PayResources(solari=2),)
                )
            )
        )
    with pytest.raises(ValueError, match="twice"):
        check_conflict_reward_row(
            _row(
                EffectSection(rewards=(GainResources(spice=1),)),
                EffectSection(rewards=(GainResources(water=1),)),
            )
        )
    with pytest.raises(ValueError, match="no condition"):
        check_conflict_reward_row(
            _row(
                EffectSection(
                    rewards=(GainResources(spice=1),), condition=HasHighCouncil()
                )
            )
        )
    with pytest.raises(TypeError, match="not a Conflict reward"):
        check_conflict_reward_row(_row(EffectSection(rewards=(DrawPersonalCards(1),))))
    # Two arrows in one row are read: Economic Supremacy's first place prints
    # 6 Solari -> 1 VP and 4 spice -> 1 VP [Economic Supremacy card].
    both = _rows(CONFLICTS_BY_ID["economic_supremacy"])[0]
    assert (both.optional_spice_cost, both.optional_solari_cost) == (4, 6)


def test_reserve_play_data_matches_the_printed_cards() -> None:
    prepare = RESERVE_STACKS_BY_ID["prepare_the_way"]
    spice = RESERVE_STACKS_BY_ID["the_spice_must_flow"]

    # Purple "BENE GESSERIT" banner [card face]; Main p. 20 defines Bond by
    # other cards of that Faction in play.
    assert prepare.factions == (Faction.BENE_GESSERIT,)
    assert prepare.agent_icons == (AgentIcon.LANDSRAAD, AgentIcon.CITY)
    assert prepare.agent_effect is (
        PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
    )
    assert prepare.reveal_persuasion == 2
    assert prepare.reveal_strength == 0
    # Red "SPACING GUILD" banner [card face].
    assert spice.factions == (Faction.SPACING_GUILD,)
    assert spice.agent_icons == ()
    assert spice.agent_effect is None
    assert spice.reveal_persuasion == 0
    # The Reveal box prints an orange spice hexagon "1" [Main p. 20] (icon
    # guide: spice, not a sword), not a base sword.
    assert spice.reveal_strength == 0
    assert _reveal_texts(spice) == ("Gain 1 spice",)


def test_reserve_instance_ids_resolve_and_validate_copy_bounds() -> None:
    assert (
        reserve_card_for_instance("reserve:prepare_the_way:7").card.card_id
        == "prepare_the_way"
    )
    with pytest.raises(ValueError, match="copy index"):
        reserve_card_for_instance("reserve:prepare_the_way:8")


def test_base_setup_excludes_only_the_choam_leader() -> None:
    assert len(LEADERS) == 9 + 8 + 1
    assert len(leaders_for_choam(choam_module=False)) == 8
    assert len(leaders_for_choam(choam_module=True)) == 9
    assert len(leaders_for_choam(choam_module=True, bloodlines=True)) == 9 + 8
    # Kota Odax of Ix needs the Tech Module [Bloodlines p. 6].
    assert (
        len(leaders_for_choam(choam_module=True, bloodlines=True, tech_module=True))
        == 9 + 8 + 1
    )
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
        stack.card.card_id: (stack.acquisition_cost, stack.acquisition_vp)
        for stack in RESERVE_STACKS
    } == {
        "prepare_the_way": (2, 0),
        "the_spice_must_flow": (9, 1),
    }
    # The id table holds the original game's stacks too (plan 4.2 item 7).
    assert set(RESERVE_STACKS_BY_ID) == {
        "prepare_the_way",
        "the_spice_must_flow",
        "arrakis_liaison",
        "imperium_the_spice_must_flow",
        "foldspace_card",
    }


def test_imperium_manifest_matches_base_and_choam_counts() -> None:
    # 57 Uprising identities (72 cards) plus the 26 Bloodlines identities
    # (32 cards: 25 retail, 5 CHOAM-only, 2 Tech-only) [Bloodlines p. 2],
    # the Bloodlines promo Ruthless Leadership, and the 25 Immortality
    # identities, 30 cards [Immortality p. 3] (Dissecting Kit, Tleilaxu
    # Master, High Priority Travel, Planned Coupling and Spiritual Fervor
    # twice — the BGG card inventory, 2026-09-08).
    assert len(IMPERIUM_CARDS) == 57 + 26 + 1 + 25
    assert sum(entry.copies for entry in IMPERIUM_CARDS) == 72 + 32 + 1 + 30
    immortality = tuple(entry for entry in IMPERIUM_CARDS if entry.immortality_only)
    assert len(immortality) == 25
    assert sum(entry.copies for entry in immortality) == 30
    assert all(entry.card.catalog_url for entry in immortality)
    assert not any(entry.promo or entry.choam_only for entry in immortality)
    # Only transcribed Immortality cards join the option's deck, and none
    # joins without the option.
    assert {
        entry.card.card_id
        for entry in imperium_cards_for_choam(True, True, immortality=True)
        if entry.immortality_only
    } == {
        "bene_tleilax_lab",
        "bene_tleilax_researcher",
        "blank_slate",
        "clandestine_meeting",
        "corrupt_smuggler",
        "dissecting_kit",
        "for_humanity",
        "high_priority_travel",
        "imperium_ceremony",
        "interstellar_conspiracy",
        "keys_to_power",
        "lisan_al_gaib",
        "long_reach",
        "occupation",
        "organ_merchants",
        "planned_coupling",
        "replacement_eyes",
        "sardaukar_quartermaster",
        "shadout_mapes",
        "show_of_strength",
        "spiritual_fervor",
        "stillsuit_manufacturer",
        "throne_room_politics",
        "tleilaxu_master",
        "tleilaxu_surgeon",
    }
    assert not any(
        entry.immortality_only for entry in imperium_cards_for_choam(True, True)
    )
    bloodlines = tuple(
        entry for entry in IMPERIUM_CARDS if entry.bloodlines_only and not entry.promo
    )
    assert sum(entry.copies for entry in bloodlines) == 32
    assert sum(entry.copies for entry in bloodlines if entry.choam_only) == 5
    assert sum(entry.copies for entry in bloodlines if entry.tech_only) == 2
    assert all(entry.card.catalog_url for entry in bloodlines)
    assert sum(entry.copies for entry in imperium_cards_for_choam(False)) == 65
    # The three Uprising promo cards join either ruleset only on request;
    # the Bloodlines promo needs the expansion as well.
    assert {entry.card.card_id for entry in IMPERIUM_CARDS if entry.promo} == {
        "arrakis_revolt",
        "pivotal_gambit",
        "the_beast_s_spoils",
        "ruthless_leadership",
    }
    assert sum(entry.copies for entry in imperium_cards_for_choam(False, True)) == 68
    assert sum(entry.copies for entry in imperium_cards_for_choam(True, True)) == 72
    assert (
        sum(
            entry.copies
            for entry in imperium_cards_for_choam(False, True, bloodlines=True)
        )
        == 65 + 25 + 3 + 1
    )
    assert (
        sum(
            entry.copies
            for entry in imperium_cards_for_choam(False, False, bloodlines=True)
        )
        == 65 + 25
    )
    assert not any(entry.promo and entry.choam_only for entry in IMPERIUM_CARDS)
    assert {
        entry.card.card_id
        for entry in IMPERIUM_CARDS
        if entry.choam_only and not entry.bloodlines_only
    } == {
        "cargo_runner",
        "delivery_agreement",
        "interstellar_trade",
        "priority_contracts",
    }
    assert all(entry.acquisition_cost is not None for entry in IMPERIUM_CARDS)


def test_intrigue_manifest_matches_base_and_choam_counts() -> None:
    # 39 Uprising identities (44 cards) plus 18 Bloodlines cards (15 retail,
    # 1 CHOAM-only, 2 Tech-only) [Bloodlines p. 2].
    # 18 Bloodlines Intrigue cards plus the 12 Twisted Intrigue cards and
    # the 10 Navigation cards (Y'rkoon), which share the Intrigue schema,
    # and the 11 Immortality identities, 15 cards [Immortality p. 3]
    # (Gruesome Sacrifice, Harvest Cells, Illicit Dealings and Vicious
    # Talents twice — the BGG card inventory, 2026-09-08).
    assert len(INTRIGUE_CARDS) == 39 + 18 + 12 + 10 + 11
    assert sum(entry.copies for entry in INTRIGUE_CARDS) == 44 + 18 + 12 + 10 + 15
    immortality = tuple(entry for entry in INTRIGUE_CARDS if entry.immortality_only)
    assert len(immortality) == 11
    assert all(entry.play_data_complete for entry in immortality)
    assert (
        sum(
            entry.immortality_only
            for entry in intrigue_cards_for_choam(True, immortality=True)
        )
        == 11
    )
    assert not any(entry.immortality_only for entry in intrigue_cards_for_choam(True))
    bloodlines = tuple(
        entry
        for entry in INTRIGUE_CARDS
        if entry.bloodlines_only and not entry.twisted and not entry.navigation
    )
    assert len(bloodlines) == 18
    assert sum(entry.twisted for entry in INTRIGUE_CARDS) == 12
    assert sum(entry.choam_only for entry in bloodlines) == 1
    assert sum(entry.tech_only for entry in bloodlines) == 2
    assert sum(entry.copies for entry in intrigue_cards_for_choam(False)) == 40
    assert {
        entry.card.card_id
        for entry in INTRIGUE_CARDS
        if entry.choam_only and not entry.bloodlines_only
    } == {
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

    assert len(STANDARD_CONTRACTS) == len(instances) == len(set(instances)) == 20
    assert len({contract.card.card_id for contract in STANDARD_CONTRACTS}) == 20
    assert all(contract.card.catalog_url for contract in CONTRACTS)
    assert not any(contract.bloodlines_only for contract in STANDARD_CONTRACTS)
    assert {
        contract.card.card_id
        for contract in STANDARD_CONTRACTS
        if contract.completes_immediately
    } == {"immediate"}
    assert contract_for_instance("contract:high_council_ii").card.name == (
        "High Council II"
    )


def test_standard_contracts_are_the_twenty_uprising_tiles_not_rise_of_ix() -> None:
    """"20 Contract tokens" plus "10 Contract tokens with contrasting backs",
    "Used only with the RISE OF IX expansion" to "jumpstart the completion of
    contracts" [Main p. 16]. The BGG card inventory's Contracts tab says
    which is which and counts the copies; every Rise of Ix tile prints
    "+1 Contract" and no standard tile does."""

    faces = Counter(
        contract.copy_of or contract.card.card_id for contract in STANDARD_CONTRACTS
    )
    assert faces == {
        "acquire": 1,
        "arrakeen_i": 1,
        "arrakeen_ii": 1,
        "deliver_supplies": 1,
        "espionage_i": 2,
        "harvest_3": 2,
        "harvest_4": 1,
        "heighliner_i": 1,
        "heighliner_ii": 1,
        "high_council_i": 1,
        "high_council_ii": 1,
        "immediate": 1,
        "research_station_i": 1,
        "research_station_ii": 1,
        "sardaukar_i": 1,
        "sardaukar_ii": 1,
        "spice_refinery_i": 1,
        "spice_refinery_ii": 1,
    }
    assert not any(_reward(contract).contracts for contract in STANDARD_CONTRACTS)
    for contract in STANDARD_CONTRACTS:
        if contract.copy_of is not None:
            first = CONTRACTS_BY_ID[contract.copy_of]
            assert (contract.card.name, contract.terms) == (
                first.card.name,
                first.terms,
            )


def test_contracts_kept_from_observation_v20_keep_their_index() -> None:
    """The observation's Contract segments follow this order, so the tiles
    that replaced the four Rise of Ix ones took their places and nothing else
    moved (observation v21); training/checkpoint.py re-links a v20 file's
    columns by identity from its own copy of the old order."""

    assert [contract.card.card_id for contract in STANDARD_CONTRACTS] == [
        "acquire",
        "arrakeen_i",
        "arrakeen_ii",
        "deliver_supplies",
        "espionage_i",
        "espionage_i_copy_2",  # v20: espionage_ii
        "harvest_3",
        "harvest_3_copy_2",  # v20: harvest_3_contract
        "harvest_4",
        "spice_refinery_i",  # v20: harvest_4_contract
        "heighliner_i",
        "heighliner_ii",
        "spice_refinery_ii",  # v20: heighliner_iii
        "high_council_i",
        "high_council_ii",
        "immediate",
        "research_station_i",
        "research_station_ii",
        "sardaukar_i",
        "sardaukar_ii",
    ]


def test_bloodlines_contract_manifest_adds_eight_tokens_to_the_same_bank() -> None:
    # Eight contract tokens shuffle into the existing contracts with the
    # CHOAM Module [Bloodlines p. 2]; one copy each (BGG card inventory).
    instances = contract_instance_ids(bloodlines=True)

    assert len(BLOODLINES_CONTRACTS) == 8
    assert all(contract.bloodlines_only for contract in BLOODLINES_CONTRACTS)
    assert len(CONTRACTS) == len(instances) == len(set(instances)) == 28
    assert len({contract.card.card_id for contract in CONTRACTS}) == 28
    assert instances[:20] == contract_instance_ids()
    assert {
        contract.card.card_id
        for contract in CONTRACTS
        if contract.completes_immediately
    } == {"immediate", "bloodlines_immediate"}
    immediate = contract_for_instance("contract:bloodlines_immediate")
    assert immediate.requires_intrigue_trash
    assert not contract_for_instance("contract:immediate").requires_intrigue_trash


def test_bloodlines_contract_manifest_transcribes_printed_faces() -> None:
    printed = {
        contract.card.card_id: (contract.requirement, _reward(contract))
        for contract in BLOODLINES_CONTRACTS
    }

    assert printed == {
        "bloodlines_deliver_supplies": (
            AtBoardSpace("deliver_supplies"),
            ContractRewardParts(solari=1, deep_cover_spies=1),
        ),
        "bloodlines_earn_any_alliance": (
            AllianceTaken(),
            ContractRewardParts(solari=2, troops=2),
        ),
        "bloodlines_harvest_3": (
            _harvest(3),
            ContractRewardParts(solari=2, spies=1),
        ),
        "bloodlines_harvest_4": (
            _harvest(4),
            ContractRewardParts(solari=3, spies=1),
        ),
        "bloodlines_high_council": (
            AtBoardSpace("high_council"),
            ContractRewardParts(recall_agents=1),
        ),
        "bloodlines_immediate": (
            ContractTaken(),
            ContractRewardParts(intrigue_cards=1, personal_cards=1),
        ),
        "bloodlines_secrets": (
            AtBoardSpace("secrets"),
            ContractRewardParts(solari=2, personal_cards=1),
        ),
        "bloodlines_spice_refinery": (
            AtBoardSpace("spice_refinery"),
            ContractRewardParts(troops=2),
        ),
    }
    # The Immediate tile costs an Intrigue card trashed when taken
    # [Bloodlines p. 2]: its record's line carries the cost.
    assert CONTRACTS_BY_ID["bloodlines_immediate"].requires_intrigue_trash
    assert not CONTRACTS_BY_ID["immediate"].requires_intrigue_trash


def test_standard_contract_manifest_transcribes_printed_conditions_and_rewards() -> (
    None
):
    printed = {
        contract.card.card_id: (contract.requirement, _reward(contract))
        for contract in STANDARD_CONTRACTS
    }

    assert printed == {
        "acquire": (
            AcquiredCard("the_spice_must_flow"),
            ContractRewardParts(
                solari=3,
                influence_faction=Faction.SPACING_GUILD,
                influence=1,
            ),
        ),
        "arrakeen_i": (
            AtBoardSpace("arrakeen"),
            ContractRewardParts(water=1),
        ),
        "arrakeen_ii": (
            AtBoardSpace("arrakeen"),
            ContractRewardParts(troops=1, spies=1),
        ),
        "deliver_supplies": (
            AtBoardSpace("deliver_supplies"),
            ContractRewardParts(solari=3),
        ),
        "espionage_i": (
            AtBoardSpace("espionage"),
            ContractRewardParts(solari=3),
        ),
        "espionage_i_copy_2": (
            AtBoardSpace("espionage"),
            ContractRewardParts(solari=3),
        ),
        "harvest_3": (
            _harvest(3),
            ContractRewardParts(solari=3),
        ),
        "harvest_3_copy_2": (
            _harvest(3),
            ContractRewardParts(solari=3),
        ),
        "harvest_4": (
            _harvest(4),
            ContractRewardParts(solari=4),
        ),
        "spice_refinery_i": (
            AtBoardSpace("spice_refinery"),
            ContractRewardParts(personal_cards=2),
        ),
        "heighliner_i": (
            AtBoardSpace("heighliner"),
            ContractRewardParts(water=2),
        ),
        "heighliner_ii": (
            AtBoardSpace("heighliner"),
            ContractRewardParts(troops=2),
        ),
        "spice_refinery_ii": (
            AtBoardSpace("spice_refinery"),
            ContractRewardParts(water=1),
        ),
        "high_council_i": (
            AtBoardSpace("high_council"),
            ContractRewardParts(
                influence_faction=Faction.BENE_GESSERIT,
                influence=1,
            ),
        ),
        "high_council_ii": (
            AtBoardSpace("high_council"),
            ContractRewardParts(solari=3),
        ),
        "immediate": (
            ContractTaken(),
            ContractRewardParts(solari=2),
        ),
        "research_station_i": (
            AtBoardSpace("research_station"),
            ContractRewardParts(solari=2, spies=1),
        ),
        "research_station_ii": (
            AtBoardSpace("research_station"),
            ContractRewardParts(solari=3),
        ),
        "sardaukar_i": (
            AtBoardSpace("sardaukar"),
            ContractRewardParts(personal_cards=2),
        ),
        "sardaukar_ii": (
            AtBoardSpace("sardaukar"),
            ContractRewardParts(recall_agents=1),
        ),
    }


def test_imperium_costs_cover_the_printed_range_and_resolve_instances() -> None:
    costs = {
        entry.card.card_id: entry.acquisition_cost
        for entry in IMPERIUM_CARDS
        if not entry.bloodlines_only and not entry.immortality_only
    }

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
        entry.card.card_id
        for entry in IMPERIUM_CARDS
        if entry.has_acquisition_bonus
        and not entry.bloodlines_only
        and not entry.immortality_only
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
    assert {
        entry.card.card_id
        for entry in IMPERIUM_CARDS
        if entry.has_acquisition_bonus and entry.immortality_only
    } == {"lisan_al_gaib", "occupation", "spiritual_fervor"}
    instance = imperium_deck_instance_ids(False)[0]
    assert imperium_card_for_instance(instance).card.card_id in costs
