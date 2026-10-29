"""The original game's catalog holds none of Uprising's own content or systems.

docs/base-game-and-ix-plan.md 4.2 items 3-4 (stage P1): the original Dune:
Imperium gets a catalog of its own, built from its ruleset content, which
has no board or cards yet. Uprising's rows are unchanged (the 144 option
combinations are compared byte for byte at the stage's gate); what is
checked here is that no Uprising board space, observation post, Conflict,
Objective, Leader or card, and no row of the Spy, sandworm, Shield Wall or
Sietch Tabr systems, leaks into the other base game's catalog.
"""

from itertools import chain
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
from dune_imperium.content.rise_of_ix.conflicts import IX_CONFLICTS
from dune_imperium.content.rulesets import content_for

_UPRISING_SYSTEM_WORDS = (
    "spy",
    "spies",
    "sandworm",
    "shield_wall",
    "sietch_tabr",
    "post",
)


def _uprising_ids() -> frozenset[str]:
    """Every id Uprising's widest ruleset prints, but its starting cards
    (the original game prints the same ones [DI p. 3])."""

    content = content_for(
        RulesetConfig(
            choam_module=True,
            promo_cards=True,
            bloodlines=True,
            tech_module=True,
            immortality=True,
            epic_game=True,
            arrakeen_scouts=True,
        )
    )
    starting = {entry.card.card_id for entry in content.starting_deck_entries}
    ids = {
        *(space.space_id for space in content.board_spaces),
        *(post.post_id for post in content.observation_posts),
        *(conflict.card.card_id for conflict in content.conflicts),
        *(objective.objective_id for objective in content.objectives),
        *(leader.leader_id for leader in content.leaders),
        *(card.card.card_id for card in content.imperium_cards),
        *(stack.card.card_id for stack in content.reserve_stacks),
        *(
            part
            for instance in chain(
                content.intrigue_deck_instance_ids, content.contract_instance_ids
            )
            for part in instance.split(":")
            if not part.isdigit()
        ),
    }
    # The spaces printed alike on both boards are one definition (plan 4.2
    # item 7, 15.2): Arrakeen, Imperial Basin and Secrets.
    return frozenset(ids - starting - _original_ids() - {"intrigue", "contract", ""})


def _original_ids() -> frozenset[str]:
    """Every id the original game's ruleset prints."""

    content = content_for(RulesetConfig(base_game=BaseGame.IMPERIUM))
    return frozenset(
        {
            *(space.space_id for space in content.board_spaces),
            *(conflict.card.card_id for conflict in content.conflicts),
            *(leader.leader_id for leader in content.leaders),
            *(stack.card.card_id for stack in content.reserve_stacks),
        }
    )


def _original_card_ids() -> frozenset[str]:
    """The original game's own Imperium cards (stage P3): Imperial Spy's id is
    no Spy system, whatever its name says."""

    content = content_for(RulesetConfig(base_game=BaseGame.IMPERIUM))
    return frozenset(card.card.card_id for card in content.imperium_cards)


# The original board's High Council and Swordmaster print the icons of the
# same names [DI pp. 17-18], whose keys are Uprising's space ids.
_ORIGINAL_ICONS = frozenset({"high_council", "swordmaster"})
# A refusal or an empty confirmation names the verb of the effect it answers
# (``of``): Bypass Protocol's "acquire a card that costs 3 or less" with
# nothing to take confirms ``of=acquire``, which is also the id of Uprising's
# "acquire" Contract by coincidence of the word, not a leak.
_ORIGINAL_VERBS = frozenset({"acquire"})


# Economic Supremacy is the Conflict III of the Rise of Ix box [Rise of Ix
# pp. 2-3] (docs/rules/rise-of-ix.md 3 item 3, 12): Uprising holds it for its
# Epic Game Mode alone [Main p. 18], but every original game with Rise of Ix
# draws from it, so that catalog prints it as its own.
_RISE_OF_IX_IDS = frozenset({"economic_supremacy"})


def test_the_original_game_catalog_holds_no_uprising_content() -> None:
    original_cards = _original_card_ids()
    for config in (
        RulesetConfig(base_game=BaseGame.IMPERIUM),
        RulesetConfig(
            base_game=BaseGame.IMPERIUM,
            promo_cards=True,
            rise_of_ix=True,
            epic_game=True,
        ),
    ):
        catalog = ActionCodec(config).catalog
        own = _RISE_OF_IX_IDS if config.rise_of_ix else frozenset()
        uprising = _uprising_ids() - own
        original = _original_ids() | own
        leaks = sorted(
            {
                f"{template.action_id} {name}={value}"
                for template in catalog
                for name, value in template.arguments
                if isinstance(value, str)
                and not (name in ("icon", "effect") and value in _ORIGINAL_ICONS)
                and not (name == "of" and value in _ORIGINAL_VERBS)
                and any(part in uprising for part in value.split(":"))
            }
        )
        assert leaks == [], leaks[:20]
        # The original board's own Sietch Tabr (``imperium_sietch_tabr``) is
        # no Uprising system.
        systems = sorted(
            {
                template.action_id
                for template in catalog
                if any(word in template.action_id for word in _UPRISING_SYSTEM_WORDS)
                or any(
                    isinstance(value, str)
                    and value not in original
                    and not any(part in original_cards for part in value.split(":"))
                    and any(word in value for word in _UPRISING_SYSTEM_WORDS)
                    for _, value in template.arguments
                )
            }
        )
        assert systems == [], systems
        assert config.identifier.startswith("imperium-4p-")


def test_the_original_game_with_rise_of_ix_draws_economic_supremacy() -> None:
    """Stage P4a (docs/base-game-and-ix-plan.md 17.1): the catalog of every
    original game with Rise of Ix, Epic Game Mode or not, holds Economic
    Supremacy's rows, since it is that box's Conflict III [Rise of Ix p. 3]
    (docs/rules/rise-of-ix.md 3 item 3); Uprising prints it only for Epic
    Game Mode [Main p. 18]. The Ix Conflicts whose rewards are not yet
    transcribed are in no catalog (``content.rulesets``)."""

    untranscribed = {
        conflict.card.card_id
        for conflict in content_for(
            RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
        ).conflicts
        if conflict.reward_rows is None
    }
    assert not untranscribed
    for epic_game in (False, True):
        for promo_cards in (False, True):
            config = RulesetConfig(
                base_game=BaseGame.IMPERIUM,
                rise_of_ix=True,
                epic_game=epic_game,
                promo_cards=promo_cards,
            )
            catalog = ActionCodec(config).catalog
            chosen = {
                dict(template.arguments)["card_id"]
                for template in catalog
                if template.action_id == "choose_conflict_card"
            }
            assert chosen == {
                conflict.card.card_id for conflict in content_for(config).conflicts
            }
            assert "economic_supremacy" in chosen
            # Its reward rows (rise-of-ix.md 12, epic-game-mode.md 6).
            assert {
                template.action_id
                for template in catalog
                if ("printed", "economic_supremacy") in template.arguments
            } >= {"gain", "pay"}
    plain = ActionCodec(RulesetConfig(base_game=BaseGame.IMPERIUM)).catalog
    assert not any(
        "economic_supremacy" in str(value)
        for template in plain
        for _, value in template.arguments
    )


_OVERLAID_SPACES = frozenset(
    {"hall_of_oratory", "rally_troops", "secure_contract", "sell_melange"}
)
_IX_SPACES = frozenset(
    {"dreadnought", "tech_negotiation", "interstellar_shipping", "smuggling"}
)


def _rows_naming(
    config: RulesetConfig, name: str
) -> frozenset[tuple[str, tuple[Any, ...]]]:
    return frozenset(
        (template.action_id, template.arguments)
        for template in ActionCodec(config).catalog
        if any(value == name for _, value in template.arguments)
    )


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"epic_game": True},
        {"promo_cards": True},
        {"promo_cards": True, "epic_game": True},
    ],
    ids=str,
)
def test_the_original_game_with_rise_of_ix_builds_a_catalog(
    options: dict[str, bool],
) -> None:
    """Stage P4a's board axis (docs/rules/rise-of-ix.md 3 item 1, 3): the
    original game's catalog with ``rise_of_ix`` is built from its content.
    The overlay's four spaces replace the four they cover [Rise of Ix p. 3]
    [Rise of Ix p. 12]; Economic Supremacy, Rise of Ix's Conflict III, has its
    rows with or without Epic Game Mode (Uprising holds it for Epic alone
    [Main p. 18]); a Rise of Ix Conflict whose rewards are not transcribed has
    none."""

    config = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True, **options)
    catalog = ActionCodec(config).catalog
    assert catalog
    spaces = {
        dict(template.arguments)["space_id"]
        for template in catalog
        if template.action_id == "choose_space"
    }
    assert _IX_SPACES <= spaces
    assert not _OVERLAID_SPACES & spaces
    economic = _rows_naming(config, "economic_supremacy")
    assert ("choose_conflict_card", (("card_id", "economic_supremacy"),)) in economic
    assert {action_id for action_id, _ in economic} >= {
        "choose_conflict_card",
        "decline",
        "gain",
        "pay",
        "resolve",
    }
    # The same rows whether or not Epic Game Mode is on.
    assert economic == _rows_naming(
        RulesetConfig(
            base_game=BaseGame.IMPERIUM,
            rise_of_ix=True,
            **{**options, "epic_game": False},
        ),
        "economic_supremacy",
    )
    for conflict in IX_CONFLICTS:
        if conflict.reward_rows is None:
            assert not _rows_naming(config, conflict.card.card_id)


def test_the_original_game_without_rise_of_ix_keeps_its_own_rows() -> None:
    """Without ``rise_of_ix`` the catalog has the four overlaid spaces and no
    Economic Supremacy row, Epic Game Mode (stage P4e) included."""

    for options in ({}, {"epic_game": True}):
        config = RulesetConfig(base_game=BaseGame.IMPERIUM, **options)
        spaces = {
            dict(template.arguments)["space_id"]
            for template in ActionCodec(config).catalog
            if template.action_id == "choose_space"
        }
        assert _OVERLAID_SPACES <= spaces
        assert not _IX_SPACES & spaces
        assert not _rows_naming(config, "economic_supremacy")
