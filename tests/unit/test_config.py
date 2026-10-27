"""Tests for the supported ruleset boundary."""

from itertools import product
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.core.state import _canonicalize


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
        match="only four-player games are currently supported",
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


def test_epic_game_follows_go_to_11_in_the_identifier() -> None:
    # OQ-092: an independent option, token ``+epic`` between ``+go11`` and
    # ``+scouts`` (docs/rules/epic-game-mode.md section 7).
    assert RulesetConfig(epic_game=True).identifier == "uprising-4p-base+epic"
    assert (
        RulesetConfig(
            choam_module=True,
            promo_cards=True,
            bloodlines=True,
            tech_module=True,
            immortality=True,
            go_to_11=True,
            epic_game=True,
            arrakeen_scouts=True,
        ).identifier
        == "uprising-4p-choam+promo+bloodlines+tech+immortality+go11+epic+scouts"
    )
    assert (
        RulesetConfig(epic_game=True, arrakeen_scouts=True).identifier
        == "uprising-4p-base+epic+scouts"
    )


def test_epic_game_plays_to_twelve_with_five_garrison_troops() -> None:
    # Ten [Main p. 15] and three [Main p. 5]; twelve and five in Epic Game
    # Mode [Rise of Ix p. 10]. With Go to 11 the game runs 0 -> 12 (OQ-093).
    assert RulesetConfig().endgame_victory_points == 10
    assert RulesetConfig().starting_garrison_troops == 3
    assert RulesetConfig(immortality=True, go_to_11=True).endgame_victory_points == 10
    epic = RulesetConfig(epic_game=True)
    assert (epic.endgame_victory_points, epic.starting_garrison_troops) == (12, 5)
    assert epic.starting_victory_points == 1
    both = RulesetConfig(immortality=True, go_to_11=True, epic_game=True)
    assert (both.starting_victory_points, both.endgame_victory_points) == (0, 12)
    assert RulesetConfig().epic_game is False


def test_go_to_11_requires_immortality() -> None:
    # OQ-091 (user decision, not a rulebook rule): the variant is offered
    # only with the Immortality expansion.
    option_sets: tuple[dict[str, Any], ...] = (
        {},
        {"bloodlines": True},
        {"arrakeen_scouts": True},
    )
    for flags in option_sets:
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
    for (
        choam,
        promo,
        bloodlines,
        tech,
        immortality,
        go_to_11,
        epic,
        scouts,
    ) in product((False, True), repeat=8):
        if (tech and not bloodlines) or (go_to_11 and not immortality):
            continue
        config = RulesetConfig(
            choam_module=choam,
            promo_cards=promo,
            bloodlines=bloodlines,
            tech_module=tech,
            immortality=immortality,
            go_to_11=go_to_11,
            epic_game=epic,
            arrakeen_scouts=scouts,
        )
        assert RulesetConfig.from_identifier(config.identifier) == config
        seen += 1
    # 72 without Epic Game Mode, 72 with it (it requires no other option).
    assert seen == 144
    for bad in (
        "uprising-3p-base",
        "uprising-4p-tech",
        "uprising-4p-base+bloodlines+promo",
        "uprising-4p-choam+promo+promo",
        "uprising-4p-base+scouts+promo",
        "uprising-4p-base+immortality+scouts+go11",
        "uprising-4p-base+immortality+goto11",
        "uprising-4p-base+scouts+epic",
        "uprising-4p-base+immortality+epic+go11",
        "uprising-4p-base+epic+immortality",
        "uprising-4p-base+epic+epic",
        "uprising-4p-base+epic_game",
    ):
        with pytest.raises(ValueError, match="unknown ruleset identifier"):
            RulesetConfig.from_identifier(bad)
    # The identifier parses; the configuration itself rejects Tech alone.
    with pytest.raises(ValueError, match="requires the Bloodlines"):
        RulesetConfig.from_identifier("uprising-4p-base+tech")
    with pytest.raises(ValueError, match="requires the Immortality"):
        RulesetConfig.from_identifier("uprising-4p-base+go11")


def test_the_first_player_option_keeps_the_ruleset_identifier() -> None:
    # OQ-132: who gets which Objective changes no card and no action
    # catalog, so a checkpoint trained on the ruleset answers for either
    # deal (like the Leader draft, which the identifier also leaves out).
    printed = RulesetConfig(choam_module=True, bloodlines=True)
    seat_zero = RulesetConfig(
        choam_module=True, bloodlines=True, first_player_seat_zero=True
    )
    assert seat_zero.identifier == printed.identifier
    assert RulesetConfig.from_identifier(seat_zero.identifier) == printed


# -- The base-game axis (docs/base-game-and-ix-plan.md 4.2 item 1) -------------


def test_the_base_game_defaults_to_uprising_and_keeps_its_identifiers() -> None:
    # Every Uprising identifier stays byte for byte what it was: saves,
    # checkpoints and records rebuild their codec from it.
    assert RulesetConfig().base_game is BaseGame.UPRISING
    assert RulesetConfig(base_game=BaseGame.UPRISING) == RulesetConfig()
    assert RulesetConfig(choam_module=True).identifier == "uprising-4p-choam"


def test_the_original_game_has_its_own_identifier_prefix() -> None:
    imperium = RulesetConfig(base_game=BaseGame.IMPERIUM)
    assert imperium.identifier == "imperium-4p-base"
    assert (
        RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True).identifier
        == "imperium-4p-base+ix"
    )
    assert (
        RulesetConfig(
            base_game=BaseGame.IMPERIUM,
            promo_cards=True,
            rise_of_ix=True,
            epic_game=True,
        ).identifier
        == "imperium-4p-base+promo+ix+epic"
    )
    # A save or a command line may name the base game by its string.
    assert RulesetConfig(base_game="imperium") == imperium  # type: ignore[arg-type]
    assert RulesetConfig(base_game="imperium").base_game is BaseGame.IMPERIUM  # type: ignore[arg-type]


_EXPANSIONS = (
    "choam_module",
    "promo_cards",
    "rise_of_ix",
    "bloodlines",
    "tech_module",
    "immortality",
    "go_to_11",
    "epic_game",
    "arrakeen_scouts",
)


def _combinations(base_game: BaseGame) -> list[RulesetConfig]:
    configs = []
    for values in product((False, True), repeat=len(_EXPANSIONS)):
        options: dict[str, Any] = dict(zip(_EXPANSIONS, values, strict=True))
        if (options["tech_module"] and not options["bloodlines"]) or (
            options["go_to_11"] and not options["immortality"]
        ):
            continue
        configs.append(RulesetConfig(base_game=base_game, **options))
    return configs


def test_every_expansion_combines_with_either_base_game() -> None:
    # User decision 2026-10-27: "모든 확장은 서로 서로 다양한 조합으로 결합될
    # 수 있어야해. 다만 base나 uprising 둘 중 하나는 꼭 있어야 하고". Only an
    # expansion's own parts keep their requirement: the Tech Module comes
    # with Bloodlines [Bloodlines pp. 6-7], Go to 11 with Immortality
    # (OQ-091).
    for base_game in BaseGame:
        configs = _combinations(base_game)
        # 2^9 option sets, less Tech without Bloodlines and Go to 11
        # without Immortality: 3 of 4 for each pair.
        assert len(configs) == 512 * 3 // 4 * 3 // 4 == 288
        identifiers = {config.identifier for config in configs}
        assert len(identifiers) == 288
        for config in configs:
            assert RulesetConfig.from_identifier(config.identifier) == config
    assert (
        RulesetConfig(base_game=BaseGame.IMPERIUM, choam_module=True).identifier
        == "imperium-4p-choam"
    )
    assert (
        RulesetConfig(rise_of_ix=True, bloodlines=True).identifier
        == "uprising-4p-base+ix+bloodlines"
    )
    assert (
        RulesetConfig(base_game=BaseGame.IMPERIUM, epic_game=True).identifier
        == "imperium-4p-base+epic"
    )


def test_from_identifier_refuses_an_unknown_original_game_identifier() -> None:
    for bad in (
        "imperium-3p-base",
        "imperium-4p-ix",
        "imperium-4p-base+ix+promo",
        "imperium-4p-base+epic+ix",
        "dune-4p-base",
    ):
        with pytest.raises(ValueError, match="unknown ruleset identifier"):
            RulesetConfig.from_identifier(bad)
    # The identifier parses; the configuration itself rejects the option.
    with pytest.raises(ValueError, match="requires the Bloodlines"):
        RulesetConfig.from_identifier("imperium-4p-base+tech")


def test_the_axis_leaves_uprising_state_hashes_alone() -> None:
    # The new fields are left out of the canonical state hash at their
    # defaults, so every Uprising save keeps its hash
    # (RulesetConfig.HASH_OMITTED_AT_DEFAULT).
    canonical = _canonicalize(RulesetConfig())
    assert "base_game" not in canonical
    assert "rise_of_ix" not in canonical
    imperium = _canonicalize(RulesetConfig(base_game=BaseGame.IMPERIUM))
    assert imperium["base_game"] == "imperium"
