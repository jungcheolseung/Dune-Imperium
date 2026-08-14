"""Tests for Shield Wall state and protected Conflicts."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.core import GameState
from dune_imperium.rules.shield_wall import (
    current_conflict_is_shield_wall_protected,
    destroy_shield_wall,
)


def test_six_printed_conflicts_are_shield_wall_protected() -> None:
    assert {
        conflict.card.card_id
        for conflict in CONFLICTS
        if conflict.shield_wall_protected
    } == {
        "siege_of_arrakeen",
        "seize_spice_refinery",
        "secure_imperial_basin",
        "battle_for_imperial_basin",
        "battle_for_arrakeen",
        "battle_for_spice_refinery",
    }


def test_protected_conflict_blocks_only_while_wall_is_present() -> None:
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        current_conflict_ids=("siege_of_arrakeen",),
    )

    assert current_conflict_is_shield_wall_protected(state) is True
    destroyed = destroy_shield_wall(
        state,
        event_id="test:shield_wall",
        source="test_effect",
    )
    assert destroyed.state.shield_wall_present is False
    assert current_conflict_is_shield_wall_protected(destroyed.state) is False
    assert destroyed.events[0].kind == "shield_wall_destroyed"


def test_unprotected_conflict_never_uses_the_wall() -> None:
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        current_conflict_ids=("propaganda",),
    )

    assert current_conflict_is_shield_wall_protected(state) is False
    assert current_conflict_is_shield_wall_protected(
        replace(state, shield_wall_present=False)
    ) is False


def test_shield_wall_cannot_be_destroyed_twice() -> None:
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        shield_wall_present=False,
    )

    with pytest.raises(ValueError, match="already been destroyed"):
        destroy_shield_wall(
            state,
            event_id="test:shield_wall",
            source="test_effect",
        )
