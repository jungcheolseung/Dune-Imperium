"""Static display catalog of public printed content for the web UI.

Everything here is printed, table-visible card data taken from the content
manifests — names, costs, icons — so the UI can render text cards without
ever touching hidden state. The catalog is immutable for a given ruleset
build and safe to cache on the client.
"""

from functools import cache

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.conflicts import CONFLICTS
from dune_imperium.content.uprising.contracts import CONTRACTS_BY_ID
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_ID
from dune_imperium.content.uprising.leaders import LEADERS
from dune_imperium.content.uprising.objectives import OBJECTIVES
from dune_imperium.content.uprising.reserve import RESERVE_STACKS
from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID
from dune_imperium.server.sessions import JsonObject, JsonValue


@cache
def build_catalog() -> JsonObject:
    """Return every display mapping the browser UI needs, keyed by ID."""

    cards: dict[str, JsonValue] = {}
    for card_id, starter in STARTING_CARDS_BY_ID.items():
        cards[card_id] = _personal_card(
            starter.card.name,
            cost=None,
            persuasion=starter.reveal_persuasion,
            swords=starter.reveal_strength,
            factions=tuple(faction.value for faction in starter.factions),
            agent_icons=tuple(icon.value for icon in starter.agent_icons),
        )
    for stack in RESERVE_STACKS:
        cards[stack.card.card_id] = _personal_card(
            stack.card.name,
            cost=stack.acquisition_cost,
            persuasion=stack.reveal_persuasion,
            swords=stack.reveal_strength,
            factions=(),
            agent_icons=tuple(icon.value for icon in stack.agent_icons),
        )
    for card_id, entry in IMPERIUM_CARDS_BY_ID.items():
        cards[card_id] = _personal_card(
            entry.card.name,
            cost=entry.acquisition_cost,
            persuasion=entry.reveal_persuasion,
            swords=entry.reveal_strength,
            factions=tuple(faction.value for faction in entry.factions),
            agent_icons=tuple(icon.value for icon in entry.agent_icons),
        )

    intrigue: dict[str, JsonValue] = {}
    for intrigue_id, intrigue_entry in INTRIGUE_CARDS_BY_ID.items():
        timings: list[JsonValue] = [
            timing
            for timing in sorted(
                {option.timing.value for option in intrigue_entry.options}
            )
        ]
        intrigue[intrigue_id] = {
            "name": intrigue_entry.card.name,
            "timings": timings,
        }
    return {
        "cards": cards,
        "intrigue": intrigue,
        "contracts": {
            contract_id: {"name": definition.card.name}
            for contract_id, definition in CONTRACTS_BY_ID.items()
        },
        "conflicts": {
            conflict.card.card_id: {
                "name": conflict.card.name,
                "tier": conflict.tier.value,
            }
            for conflict in CONFLICTS
        },
        "leaders": {
            leader.leader_id: {
                "name": leader.name,
                "ability": leader.ability_name,
                "signet": leader.signet_name,
            }
            for leader in LEADERS
        },
        "spaces": {
            space_id: {"name": space.name}
            for space_id, space in BOARD_SPACES_BY_ID.items()
        },
        "objectives": {
            objective.objective_id: {
                "name": objective.objective_id.replace("_", " ").title(),
                "icon": objective.battle_icon.value,
            }
            for objective in OBJECTIVES
        },
    }


def _personal_card(
    name: str,
    *,
    cost: int | None,
    persuasion: int,
    swords: int,
    factions: tuple[str, ...],
    agent_icons: tuple[str, ...],
) -> JsonObject:
    return {
        "name": name,
        "cost": cost,
        "persuasion": persuasion,
        "swords": swords,
        "factions": list(factions),
        "agent_icons": list(agent_icons),
    }
