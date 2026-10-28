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


def test_the_original_game_catalog_holds_no_uprising_content() -> None:
    uprising = _uprising_ids()
    original = _original_ids()
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
