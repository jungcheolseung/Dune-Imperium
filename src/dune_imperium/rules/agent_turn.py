"""Legal action enumeration and placement for an Uprising Agent turn."""

from dataclasses import replace

from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    BOARD_SPACES_BY_ID,
    BoardSpace,
    DynamicCost,
    Faction,
    InfluenceRequirement,
    ResourceCost,
)
from dune_imperium.content.uprising.starting_cards import starting_card_for_instance
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import Influence, PlayerState, Resources
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


def apply_agent_action(state: GameState, action: DomainAction) -> RuleResult:
    """Pay for and commit one legal card-and-space Agent placement.

    Board, Agent-card, and Faction effects remain pending so their rules-defined
    free ordering can be resolved by subsequent decisions.
    """

    if action not in legal_agent_actions(state, action.actor):
        raise ValueError("action is not a legal Agent turn in the current state")

    arguments = dict(action.arguments)
    card_instance_id = arguments["card_id"]
    space_id = arguments["space_id"]
    if not isinstance(card_instance_id, str) or not isinstance(space_id, str):
        raise ValueError("Agent action card_id and space_id must be strings")

    card = starting_card_for_instance(card_instance_id)
    space = BOARD_SPACES_BY_ID[space_id]
    cost_option, cost = _selected_cost(state, space, arguments.get("cost_option"))
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        resources=_pay_cost(owner.resources, cost),
        agents_available=owner.agents_available - 1,
        agent_locations=(*owner.agent_locations, space_id),
        hand=tuple(card_id for card_id in owner.hand if card_id != card_instance_id),
        in_play=(*owner.in_play, card_instance_id),
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    effect_frame = DecisionFrame(
        frame_id=(
            f"round:{state.round_number}:player:{action.actor}:agent_effects"
        ),
        decision=PlayerDecision(
            owner=action.actor,
            prompt="Choose the next Agent-turn effect to resolve",
        ),
        context=(
            ("card_id", card_instance_id),
            ("cost_option", cost_option),
            ("pending_agent_effect", card.agent_effect is not None),
            ("pending_board_effect", True),
            ("pending_faction_influence", space.faction is not None),
            ("space_id", space_id),
            ("turn_owner", action.actor),
        ),
    )
    next_state = replace(
        state,
        players=players,
        decision_stack=(*state.decision_stack[:-1], effect_frame),
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:agent:{space_id}"
        ),
        kind="agent_placed",
        payload=(
            ("card_id", card_instance_id),
            ("player", action.actor),
            ("space_id", space_id),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


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


def _selected_cost(
    state: GameState,
    space: BoardSpace,
    requested_option: bool | int | str | None,
) -> tuple[int, ResourceCost]:
    costs = dict(_effective_costs(state, space))
    if requested_option is None:
        if len(costs) != 1:
            raise ValueError("Agent action must identify its cost option")
        return next(iter(costs.items()))
    if isinstance(requested_option, bool) or not isinstance(requested_option, int):
        raise ValueError("Agent action cost_option must be an integer")
    try:
        return requested_option, costs[requested_option]
    except KeyError as error:
        raise ValueError("Agent action cost option is not available") from error


def _pay_cost(resources: Resources, cost: ResourceCost) -> Resources:
    return Resources(
        solari=resources.solari - cost.solari,
        spice=resources.spice - cost.spice,
        water=resources.water - cost.water,
    )


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
