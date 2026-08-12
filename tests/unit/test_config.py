"""Tests for the supported ruleset boundary."""

import pytest

from dune_imperium import RulesetConfig


def test_default_config_selects_four_player_base_uprising() -> None:
    config = RulesetConfig()

    assert config.players == 4
    assert config.choam_module is False
    assert config.identifier == "uprising-4p-base"


def test_choam_module_has_a_distinct_identifier() -> None:
    config = RulesetConfig(choam_module=True)

    assert config.identifier == "uprising-4p-choam"


@pytest.mark.parametrize("players", [0, 1, 2, 3, 5, 6])
def test_unsupported_player_count_is_rejected(players: int) -> None:
    with pytest.raises(
        ValueError,
        match="only four-player Uprising is currently supported",
    ):
        RulesetConfig(players=players)
