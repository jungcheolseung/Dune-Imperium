"""The ruleset content lookup (docs/base-game-and-ix-plan.md 4.2 item 2)."""

import itertools
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
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
    RecruitTroops,
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


def test_the_original_game_plays_its_own_board_and_its_transcribed_cards() -> None:
    # Stage P2 (docs/base-game-and-ix-plan.md 15): the original board's 22
    # spaces [DI pp. 17-18], its 18 Conflicts (I 4, II 10, III 4 [DI p. 3]),
    # its three Reserve stacks [DI p. 3] and the Leaders the engine plays
    # (four in P2a, one more per P2b Leader); its Imperium and Intrigue decks
    # hold the cards stage P3 has transcribed so far (plan 16.1), the promos
    # waiting for ``promo_cards``. Its starting deck is Uprising's printing
    # [DI p. 3]; it prints no Objective, observation post, Contract or
    # sandworm.
    config = RulesetConfig(base_game=BaseGame.IMPERIUM)
    content = content_for(config)
    assert content.base_game is BaseGame.IMPERIUM
    assert len(content.board_spaces) == 22
    assert {"arrakeen", "imperial_basin", "secrets"} <= {
        space.space_id for space in content.board_spaces
    }
    assert [len(content.conflicts_by_tier(tier)) for tier in ConflictTier] == [
        4,
        10,
        4,
    ]
    assert content.conflicts == content.conflict_pool
    assert {stack.card.card_id: stack.copies for stack in content.reserve_stacks} == {
        "arrakis_liaison": 8,
        "imperium_the_spice_must_flow": 10,
        "foldspace_card": 6,
    }
    assert [leader.leader_id for leader in content.leaders] == [
        "paul_atreides",
        "duke_leto_atreides",
        "glossu_rabban",
        "baron_vladimir_harkonnen",
        "count_ilban_richese",
        "helena_richese",
        "earl_memnon_thorvald",
        "countess_ariana_thorvald",
    ]
    imperium = [
        e for e in IMPERIUM_BASE_CARDS if e.play_data_complete and not e.promo
    ]
    assert content.imperium_cards == tuple(imperium)
    assert content.imperium_deck_instance_ids == tuple(
        f"imperium:{e.card.card_id}:{copy}"
        for e in imperium
        for copy in range(e.copies)
    )
    assert content.intrigue_deck_instance_ids == tuple(
        f"intrigue:{e.card.card_id}:{copy}"
        for e in IMPERIUM_INTRIGUE_CARDS
        if e.play_data_complete
        for copy in range(e.copies)
    )
    assert {"arrakis_recruiter", "gun_thopter"} <= {
        e.card.card_id for e in content.imperium_cards
    }
    for table in (
        content.observation_posts,
        content.contract_instance_ids,
        content.objectives,
        content.sandworm_space_ids,
    ):
        assert table == ()
    # The Maker spaces [DI p. 13] [FAQ p. 2] and the Control bonuses: 1
    # Solari at Arrakeen and Carthag, 1 spice at Imperial Basin [DI p. 10].
    assert content.maker_space_ids == (
        "the_great_flat",
        "imperium_hagga_basin",
        "imperial_basin",
    )
    assert dict(content.control_visit_bonuses) == {
        "arrakeen": "solari",
        "carthag": "solari",
        "imperial_basin": "spice",
    }
    # The Influence 4 bonuses, read off the Steam app (user decision D3,
    # plan 15.3).
    assert dict(content.influence_four_bonuses) == {
        Faction.EMPEROR: RecruitTroops(2),
        Faction.SPACING_GUILD: GainResources(solari=3),
        Faction.BENE_GESSERIT: DrawIntrigueCards(1),
        Faction.FREMEN: GainResources(water=1),
    }
    assert content.starting_deck_entries == starting_deck_entries()
    assert content.starting_discard_entries == ()
    assert content.starting_deck_instance_ids(1) == starting_deck_instance_ids(1)
    # The promos' ids are the base game's whatever the options, as Uprising's
    # are; their copies join the deck with ``promo_cards`` only (plan 9 8).
    promos = [e for e in IMPERIUM_BASE_CARDS if e.play_data_complete and e.promo]
    assert {e.card.card_id for e in promos} == {
        "duncan_loyal_blade",
        "jessica_of_arrakis",
        "thumper",
    }
    assert content.card_ids == {
        *(entry.card.card_id for entry in starting_deck_entries()),
        "arrakis_liaison",
        "imperium_the_spice_must_flow",
        "foldspace_card",
        *(entry.card.card_id for entry in imperium),
        *(entry.card.card_id for entry in promos),
    }
    with_promos = content_for(
        RulesetConfig(base_game=BaseGame.IMPERIUM, promo_cards=True)
    )
    assert with_promos.imperium_cards == (*imperium, *promos)
    assert set(with_promos.imperium_deck_instance_ids) - set(
        content.imperium_deck_instance_ids
    ) == {
        "imperium:duncan_loyal_blade:0",
        "imperium:jessica_of_arrakis:0",
        "imperium:thumper:0",
    }
    assert content.card_ids == with_promos.card_ids


def test_a_combination_without_its_content_cannot_be_set_up() -> None:
    # Every expansion combines with either base game (user decision
    # 2026-10-27), but the engine plays only what it holds: no Rise of Ix
    # before P4 (P7 with Uprising), and the original game with no option
    # before the stage that brings it (plan 15.4).
    with pytest.raises(NotImplementedError, match="Rise of Ix has no content"):
        UprisingRulesEngine().reset(RulesetConfig(rise_of_ix=True), 0)
    for option, stage in (
        ("choam_module", "P7"),
        ("bloodlines", "P7"),
        ("immortality", "P7"),
        ("epic_game", "P4"),
        ("arrakeen_scouts", "P8"),
        ("rise_of_ix", "P4"),
    ):
        config = RulesetConfig(base_game=BaseGame.IMPERIUM, **{option: True})
        with pytest.raises(NotImplementedError, match=f"{option} from stage {stage}"):
            UprisingRulesEngine().reset(config, 0)
    state = UprisingRulesEngine().reset(RulesetConfig(base_game=BaseGame.IMPERIUM), 0)
    assert len(state.players) == 4
