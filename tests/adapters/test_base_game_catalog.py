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

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters import ActionCodec
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
    return frozenset(ids - starting - {"intrigue", "contract", ""})


def test_the_original_game_catalog_holds_no_uprising_content() -> None:
    uprising = _uprising_ids()
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
        leaks = sorted(
            {
                f"{template.action_id} {name}={value}"
                for template in catalog
                for name, value in template.arguments
                if isinstance(value, str)
                and any(part in uprising for part in value.split(":"))
            }
        )
        assert leaks == [], leaks[:20]
        systems = sorted(
            {
                template.action_id
                for template in catalog
                if any(word in template.action_id for word in _UPRISING_SYSTEM_WORDS)
                or any(
                    isinstance(value, str)
                    and any(word in value for word in _UPRISING_SYSTEM_WORDS)
                    for _, value in template.arguments
                )
            }
        )
        assert systems == [], systems
        assert config.identifier.startswith("imperium-4p-")
