"""The ruleset content lookup (docs/base-game-and-ix-plan.md 4.2 item 2)."""

import itertools
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.content.rulesets import content_for
from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.conflicts import CONFLICTS, conflicts_by_tier
from dune_imperium.content.uprising.contracts import contract_instance_ids
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    GainResources,
    PlaceSpy,
)
from dune_imperium.content.uprising.imperium import (
    imperium_cards_for_choam,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.intrigue import intrigue_deck_instance_ids
from dune_imperium.content.uprising.leaders import leaders_for_choam
from dune_imperium.content.uprising.objectives import objectives_for_players
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import (
    starting_deck_entries,
    starting_deck_instance_ids,
    starting_discard_entries,
)
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.rules import UprisingRulesEngine

_OPTIONS = (
    "choam_module",
    "promo_cards",
    "bloodlines",
    "tech_module",
    "immortality",
    "go_to_11",
    "epic_game",
    "arrakeen_scouts",
)


def _configs() -> list[RulesetConfig]:
    configs = []
    for values in itertools.product((False, True), repeat=len(_OPTIONS)):
        try:
            options: dict[str, Any] = dict(zip(_OPTIONS, values, strict=True))
            configs.append(RulesetConfig(**options))
        except ValueError:
            continue
    return configs


@pytest.mark.parametrize("config", _configs(), ids=lambda config: config.identifier)
def test_uprising_content_is_the_uprising_tables(config: RulesetConfig) -> None:
    # The lookup is a pure refactor for Uprising: every table it returns is
    # the one the content modules give for the configuration's options.
    content = content_for(config)
    assert content.board_spaces is BOARD_SPACES
    assert content.observation_posts is OBSERVATION_POSTS
    assert content.conflicts is CONFLICTS
    assert content.reserve_stacks is RESERVE_STACKS
    assert content.leaders == leaders_for_choam(
        config.choam_module,
        bloodlines=config.bloodlines,
        tech_module=config.tech_module,
    )
    flags = {
        "bloodlines": config.bloodlines,
        "tech_module": config.tech_module,
        "immortality": config.immortality,
    }
    assert content.imperium_cards == imperium_cards_for_choam(
        config.choam_module, config.promo_cards, **flags
    )
    assert content.imperium_deck_instance_ids == imperium_deck_instance_ids(
        config.choam_module, config.promo_cards, **flags
    )
    assert content.intrigue_deck_instance_ids == intrigue_deck_instance_ids(
        config.choam_module, **flags
    )
    assert content.contract_instance_ids == contract_instance_ids(
        bloodlines=config.bloodlines
    )
    assert content.objectives == objectives_for_players(4)
    starting = {"immortality": config.immortality, "epic_game": config.epic_game}
    assert content.starting_deck_entries == starting_deck_entries(**starting)
    assert content.starting_discard_entries == starting_discard_entries(**starting)
    assert content.starting_deck_instance_ids(2) == starting_deck_instance_ids(
        2, **starting
    )
    for tier in ConflictTier:
        assert content.conflicts_by_tier(tier) == conflicts_by_tier(
            tier, bloodlines=config.bloodlines, epic_game=config.epic_game
        )
    assert content_for(config) is content


def test_uprising_board_values() -> None:
    # The values the Uprising board prints, kept as data for the base-game
    # axis: the Influence 4 bonuses [Main p. 7], the Maker spaces [Main
    # p. 13], the two with sandworms [Board Guide pp. 1-2] and the Control
    # visit bonuses [Main p. 10].
    content = content_for(RulesetConfig())
    assert dict(content.influence_four_bonuses) == {
        Faction.EMPEROR: PlaceSpy(),
        Faction.SPACING_GUILD: GainResources(solari=3),
        Faction.BENE_GESSERIT: DrawIntrigueCards(1),
        Faction.FREMEN: GainResources(water=1),
    }
    assert content.maker_space_ids == ("deep_desert", "hagga_basin", "imperial_basin")
    assert content.sandworm_space_ids == ("deep_desert", "hagga_basin")
    assert dict(content.control_visit_bonuses) == {
        "arrakeen": "solari",
        "spice_refinery": "solari",
        "imperial_basin": "spice",
    }
    assert content.maker_bonus_spice_for(("esmar_tuek",)) == (
        ("deep_desert", 0),
        ("hagga_basin", 0),
        ("imperial_basin", 0),
        ("tuek_sietch", 0),
    )


def test_the_original_game_has_no_content_but_its_starting_deck_yet() -> None:
    # Stage P1: the axis is in, the original game's boards, Conflicts,
    # Leaders, Reserve and decks arrive in P2-P4. Its starting deck is
    # Uprising's printing [DI p. 3] (docs/rules/imperium-base.md 2); it
    # prints no Objective, observation post, Contract or sandworm.
    for config in (
        RulesetConfig(base_game=BaseGame.IMPERIUM),
        RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True, epic_game=True),
    ):
        content = content_for(config)
        assert content.base_game is BaseGame.IMPERIUM
        for table in (
            content.board_spaces,
            content.observation_posts,
            content.conflicts,
            content.reserve_stacks,
            content.leaders,
            content.imperium_deck_instance_ids,
            content.intrigue_deck_instance_ids,
            content.contract_instance_ids,
            content.objectives,
        ):
            assert table == ()
        assert content.maker_space_ids == content.sandworm_space_ids == ()
        assert not content.control_visit_bonuses
        assert not content.influence_four_bonuses
        assert all(
            content.conflicts_by_tier(tier) == () for tier in ConflictTier
        )
        assert content.starting_deck_entries == starting_deck_entries()
        assert content.starting_discard_entries == ()
        assert content.starting_deck_instance_ids(1) == starting_deck_instance_ids(1)
        assert content.card_ids == {
            entry.card.card_id for entry in starting_deck_entries()
        }


def test_a_combination_without_its_content_cannot_be_set_up() -> None:
    # Every expansion combines with either base game (user decision
    # 2026-10-27), but the engine plays only what it holds: no original
    # board before stage P2, no Rise of Ix before P4 (P7 with Uprising).
    with pytest.raises(NotImplementedError, match="imperium base game has no board"):
        UprisingRulesEngine().reset(RulesetConfig(base_game=BaseGame.IMPERIUM), 0)
    with pytest.raises(NotImplementedError, match="Rise of Ix has no content"):
        UprisingRulesEngine().reset(RulesetConfig(rise_of_ix=True), 0)
