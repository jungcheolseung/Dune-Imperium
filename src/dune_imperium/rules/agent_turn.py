"""Legal action enumeration for an Uprising Agent turn."""

from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    BoardSpace,
    DynamicCost,
    Faction,
    InfluenceRequirement,
    ResourceCost,
)
from dune_imperium.content.uprising.starting_cards import starting_card_for_instance
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence, PlayerState
from dune_imperium.core.state import GamePhase, GameState


def legal_agent_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Enumerate card-and-space pairs currently legal for ``player``.

    Occupied spaces, printed costs, and printed Influence requirements are
    enforced here. Spy infiltration and effect-specific exceptions are deferred
    until their rule systems are implemented.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return ()
    decision = state.decision_stack[-1].decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()

    owner = state.players[player]
    if owner.agents_available == 0:
        return ()
    occupied = {
        space_id
        for candidate in state.players
        for space_id in candidate.agent_locations
    }
    actions: list[DomainAction] = []
    for card_instance_id in owner.hand:
        card = starting_card_for_instance(card_instance_id)
        for space in BOARD_SPACES:
            if space.agent_icon not in card.agent_icons or space.space_id in occupied:
                continue
            if not _meets_requirement(owner.influence, space.requirement):
                continue
            actions.extend(
                _actions_for_affordable_costs(
                    player,
                    card_instance_id,
                    space,
                    owner,
                    state,
                )
            )
    return tuple(actions)


def _actions_for_affordable_costs(
    player: int,
    card_instance_id: str,
    space: BoardSpace,
    owner: PlayerState,
    state: GameState,
) -> tuple[DomainAction, ...]:
    costs = _effective_costs(state, space)
    include_choice = space.dynamic_cost is None and len(space.cost_options) > 1
    actions: list[DomainAction] = []
    for cost_option, cost in costs:
        if not _can_afford(owner, cost):
            continue
        arguments: tuple[tuple[str, str | int], ...]
        if include_choice:
            arguments = (
                ("card_id", card_instance_id),
                ("cost_option", cost_option),
                ("space_id", space.space_id),
            )
        else:
            arguments = (
                ("card_id", card_instance_id),
                ("space_id", space.space_id),
            )
        actions.append(
            DomainAction(
                action_id="agent_turn",
                actor=player,
                arguments=arguments,
            )
        )
    return tuple(actions)


def _effective_costs(
    state: GameState,
    space: BoardSpace,
) -> tuple[tuple[int, ResourceCost], ...]:
    if space.dynamic_cost is DynamicCost.SWORDMASTER:
        someone_has_swordmaster = any(
            player.swordmaster_acquired for player in state.players
        )
        option = 1 if someone_has_swordmaster else 0
        return ((option, space.cost_options[option]),)
    costs = space.cost_options or (ResourceCost(),)
    return tuple(enumerate(costs))


def _can_afford(player: PlayerState, cost: ResourceCost) -> bool:
    return (
        player.resources.solari >= cost.solari
        and player.resources.spice >= cost.spice
        and player.resources.water >= cost.water
    )


def _meets_requirement(
    influence: Influence,
    requirement: InfluenceRequirement | None,
) -> bool:
    if requirement is None:
        return True
    match requirement.faction:
        case Faction.EMPEROR:
            amount = influence.emperor
        case Faction.SPACING_GUILD:
            amount = influence.spacing_guild
        case Faction.BENE_GESSERIT:
            amount = influence.bene_gesserit
        case Faction.FREMEN:
            amount = influence.fremen
    return amount >= requirement.amount
