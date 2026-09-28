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


def test_bloodlines_and_tech_module_extend_the_identifier() -> None:
    assert RulesetConfig(bloodlines=True).identifier == "uprising-4p-base+bloodlines"
    assert (
        RulesetConfig(choam_module=True, bloodlines=True, tech_module=True).identifier
        == "uprising-4p-choam+bloodlines+tech"
    )
    assert (
        RulesetConfig(promo_cards=True, bloodlines=True).identifier
        == "uprising-4p-base+promo+bloodlines"
    )


def test_immortality_extends_the_identifier_independently() -> None:
    assert RulesetConfig(immortality=True).identifier == "uprising-4p-base+immortality"
    assert (
        RulesetConfig(
            choam_module=True, bloodlines=True, tech_module=True, immortality=True
        ).identifier
        == "uprising-4p-choam+bloodlines+tech+immortality"
    )


def test_arrakeen_scouts_extends_the_identifier_independently() -> None:
    assert RulesetConfig(arrakeen_scouts=True).identifier == "uprising-4p-base+scouts"
    assert (
        RulesetConfig(
            choam_module=True,
            bloodlines=True,
            tech_module=True,
            immortality=True,
            arrakeen_scouts=True,
        ).identifier
        == "uprising-4p-choam+bloodlines+tech+immortality+scouts"
    )


def test_go_to_11_follows_immortality_in_the_identifier() -> None:
    assert (
        RulesetConfig(immortality=True, go_to_11=True).identifier
        == "uprising-4p-base+immortality+go11"
    )
    assert (
        RulesetConfig(
            choam_module=True,
            promo_cards=True,
            bloodlines=True,
            tech_module=True,
            immortality=True,
            go_to_11=True,
            arrakeen_scouts=True,
        ).identifier
        == "uprising-4p-choam+promo+bloodlines+tech+immortality+go11+scouts"
    )


def test_go_to_11_requires_immortality() -> None:
    # OQ-091 (user decision, not a rulebook rule): the variant is offered
    # only with the Immortality expansion.
    for flags in ({}, {"bloodlines": True}, {"arrakeen_scouts": True}):
        with pytest.raises(
            ValueError,
            match="the Go to 11 variant requires the Immortality expansion",
        ):
            RulesetConfig(go_to_11=True, **flags)


def test_go_to_11_starts_every_score_marker_on_zero() -> None:
    # Four-player setup starts on 1 [Main p. 5]; Go to 11 on 0
    # [Immortality p. 12].
    assert RulesetConfig().starting_victory_points == 1
    assert RulesetConfig(immortality=True).starting_victory_points == 1
    assert (
        RulesetConfig(immortality=True, go_to_11=True).starting_victory_points == 0
    )


def test_tech_module_requires_bloodlines() -> None:
    with pytest.raises(
        ValueError,
        match="the Tech Module requires the Bloodlines expansion",
    ):
        RulesetConfig(tech_module=True)


def test_from_identifier_rebuilds_every_option_combination() -> None:
    from itertools import product

    seen = 0
    for choam, promo, bloodlines, tech, immortality, go_to_11, scouts in product(
        (False, True), repeat=7
    ):
        if (tech and not bloodlines) or (go_to_11 and not immortality):
            continue
        config = RulesetConfig(
            choam_module=choam,
            promo_cards=promo,
            bloodlines=bloodlines,
            tech_module=tech,
            immortality=immortality,
            go_to_11=go_to_11,
            arrakeen_scouts=scouts,
        )
        assert RulesetConfig.from_identifier(config.identifier) == config
        seen += 1
    assert seen == 72
    for bad in (
        "uprising-3p-base",
        "uprising-4p-tech",
        "uprising-4p-base+bloodlines+promo",
        "uprising-4p-choam+promo+promo",
        "uprising-4p-base+scouts+promo",
        "uprising-4p-base+immortality+scouts+go11",
        "uprising-4p-base+immortality+goto11",
    ):
        with pytest.raises(ValueError, match="unknown ruleset identifier"):
            RulesetConfig.from_identifier(bad)
    # The identifier parses; the configuration itself rejects Tech alone.
    with pytest.raises(ValueError, match="requires the Bloodlines"):
        RulesetConfig.from_identifier("uprising-4p-base+tech")
    with pytest.raises(ValueError, match="requires the Immortality"):
        RulesetConfig.from_identifier("uprising-4p-base+go11")
