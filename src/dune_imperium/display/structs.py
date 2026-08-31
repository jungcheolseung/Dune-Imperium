"""English text for standard Contract and Conflict card structures.

Wording follows the same shared display contract as ``effect_dsl_text``:
short imperative fragments, no trailing period, resources lowercase, game
terms capitalized as printed. ``contract_condition_text`` is an exhaustive
``match`` over ``ContractConditionKind`` so ``mypy`` fails if a new kind is
added without matching text support; the two reward renderers each publish
the dataclass field names they consume so a test can assert every field on
``ContractReward``/``ConflictReward`` is handled.
"""

from typing import assert_never

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.conflicts import ConflictDefinition, ConflictReward
from dune_imperium.content.uprising.contracts import (
    ContractCondition,
    ContractConditionKind,
    ContractReward,
)
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID

_FACTION_NAMES: dict[Faction, str] = {
    Faction.EMPEROR: "Emperor",
    Faction.SPACING_GUILD: "Spacing Guild",
    Faction.BENE_GESSERIT: "Bene Gesserit",
    Faction.FREMEN: "Fremen",
}


def _faction_name(faction: Faction) -> str:
    return _FACTION_NAMES[faction]


def _plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def _spy_text(count: int) -> str:
    if count == 1:
        return "Place a Spy"
    return f"Place {count} Spies"


def _card_name(card_id: str) -> str:
    """Resolve an acquirable card ID against the Imperium and Reserve pools."""

    if card_id in IMPERIUM_CARDS_BY_ID:
        return IMPERIUM_CARDS_BY_ID[card_id].card.name
    if card_id in RESERVE_STACKS_BY_ID:
        return RESERVE_STACKS_BY_ID[card_id].card.name
    raise ValueError(f"unknown acquirable card id: {card_id!r}")


def contract_condition_text(condition: ContractCondition) -> str:
    """Render one standard Contract's printed completion condition."""

    match condition.kind:
        case ContractConditionKind.BOARD_SPACE:
            space = BOARD_SPACES_BY_ID[condition.target]
            return f"Send an Agent to {space.name}"
        case ContractConditionKind.HARVEST_SPICE:
            return (
                f"Send an Agent to a Maker space and gain {condition.amount} "
                "or more spice that turn"
            )
        case ContractConditionKind.ACQUIRE_CARD:
            return f"Acquire {_card_name(condition.target)}"
        case ContractConditionKind.IMMEDIATE:
            return "Complete immediately when taken"
        case _:
            assert_never(condition.kind)


_HANDLED_CONTRACT_REWARD_FIELDS: frozenset[str] = frozenset(
    {
        "solari",
        "water",
        "troops",
        "personal_cards",
        "contracts",
        "spies",
        "recall_agents",
        "influence_faction",
        "influence",
    }
)


def contract_reward_text(reward: ContractReward) -> str:
    """Render one standard Contract's printed reward line."""

    parts: list[str] = []
    if reward.solari:
        parts.append(f"Gain {reward.solari} solari")
    if reward.water:
        parts.append(f"Gain {reward.water} water")
    if reward.troops:
        parts.append(f"Recruit {reward.troops} {_plural(reward.troops, 'troop')}")
    if reward.personal_cards:
        parts.append(
            f"Draw {reward.personal_cards} {_plural(reward.personal_cards, 'card')}"
        )
    if reward.contracts:
        contracts_noun = _plural(reward.contracts, "Contract")
        parts.append(f"Take {reward.contracts} {contracts_noun}")
    if reward.spies:
        parts.append(_spy_text(reward.spies))
    if reward.recall_agents:
        parts.append(
            f"Recall {reward.recall_agents} {_plural(reward.recall_agents, 'Agent')}"
        )
    if reward.influence_faction is not None:
        faction_name = _faction_name(reward.influence_faction)
        parts.append(f"Gain {reward.influence} {faction_name} Influence")
    return ", ".join(parts)


_HANDLED_CONFLICT_REWARD_FIELDS: frozenset[str] = frozenset(
    {
        "solari",
        "spice",
        "water",
        "intrigue",
        "troops",
        "place_spies",
        "contracts",
        "trash_cards",
        "victory_points",
        "choose_influence",
        "choose_distinct_influence",
        "faction_influence",
        "influence_faction",
        "control_space_id",
        "optional_spice_cost",
        "optional_solari_cost",
        "optional_recall_spies",
        "optional_victory_points",
    }
)


def _choose_influence_text(count: int, *, distinct: bool) -> str:
    choice = "a different Faction" if distinct else "a Faction"
    if count == 1:
        return f"Gain 1 Influence (choose {choice})"
    return f"Gain {count} Influence (choose {choice} each time)"


def _optional_trade_text(reward: ConflictReward) -> str | None:
    if reward.optional_spice_cost:
        cost_text = f"pay {reward.optional_spice_cost} spice"
    elif reward.optional_solari_cost:
        cost_text = f"pay {reward.optional_solari_cost} solari"
    elif reward.optional_recall_spies:
        count = reward.optional_recall_spies
        cost_text = "recall a Spy" if count == 1 else f"recall {count} Spies"
    else:
        return None
    return f"You may {cost_text} → Gain {reward.optional_victory_points} VP"


def conflict_reward_text(reward: ConflictReward) -> str:
    """Render one Conflict card's printed reward row."""

    parts: list[str] = []
    if reward.solari:
        parts.append(f"Gain {reward.solari} solari")
    if reward.spice:
        parts.append(f"Gain {reward.spice} spice")
    if reward.water:
        parts.append(f"Gain {reward.water} water")
    if reward.intrigue:
        parts.append(
            f"Draw {reward.intrigue} Intrigue {_plural(reward.intrigue, 'card')}"
        )
    if reward.troops:
        parts.append(f"Recruit {reward.troops} {_plural(reward.troops, 'troop')}")
    if reward.place_spies:
        parts.append(_spy_text(reward.place_spies))
    if reward.contracts:
        contracts_noun = _plural(reward.contracts, "Contract")
        parts.append(f"Take {reward.contracts} {contracts_noun}")
    if reward.trash_cards:
        if reward.trash_cards == 1:
            parts.append("Trash a card")
        else:
            parts.append(f"Trash {reward.trash_cards} cards")
    if reward.victory_points:
        parts.append(f"Gain {reward.victory_points} VP")
    if reward.choose_influence:
        parts.append(_choose_influence_text(reward.choose_influence, distinct=False))
    if reward.choose_distinct_influence:
        parts.append(
            _choose_influence_text(reward.choose_distinct_influence, distinct=True)
        )
    if reward.influence_faction is not None:
        faction_name = _faction_name(reward.influence_faction)
        parts.append(f"Gain {reward.faction_influence} {faction_name} Influence")
    if reward.control_space_id is not None:
        space = BOARD_SPACES_BY_ID[reward.control_space_id]
        parts.append(f"Take control of {space.name}")
    optional = _optional_trade_text(reward)
    if optional is not None:
        parts.append(optional)
    return ", ".join(parts)


def conflict_rewards_texts(definition: ConflictDefinition) -> list[str] | None:
    """Render "1st"/"2nd"/"3rd" reward lines, or None when unpublished."""

    if definition.rewards is None:
        return None
    labels = ("1st", "2nd", "3rd")
    return [
        f"{label}: {conflict_reward_text(reward)}"
        for label, reward in zip(labels, definition.rewards, strict=True)
    ]
