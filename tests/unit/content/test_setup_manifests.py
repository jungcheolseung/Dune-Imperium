"""Integrity tests for setup-relevant Uprising card manifests."""

from collections import Counter

from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.leaders import LEADERS, leaders_for_choam
from dune_imperium.content.uprising.objectives import (
    OBJECTIVES,
    objectives_for_players,
)
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.types import BattleIcon, ConflictTier


def test_conflict_manifest_has_the_official_tier_counts() -> None:
    assert len(CONFLICTS) == 16
    assert len({conflict.card.card_id for conflict in CONFLICTS}) == 16
    assert Counter(conflict.tier for conflict in CONFLICTS) == {
        ConflictTier.ONE: 3,
        ConflictTier.TWO: 9,
        ConflictTier.THREE: 4,
    }
    assert all(conflict.card.catalog_url for conflict in CONFLICTS)


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
