"""The ruleset content lookup (docs/base-game-and-ix-plan.md 4.2 item 2)."""

import itertools

import pytest

from dune_imperium import RulesetConfig
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
            configs.append(RulesetConfig(**dict(zip(_OPTIONS, values, strict=True))))
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
