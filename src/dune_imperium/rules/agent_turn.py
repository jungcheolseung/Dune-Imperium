"""Legal action enumeration and placement for an Uprising Agent turn."""

from dataclasses import replace

from dune_imperium.content.uprising.board import (
    BOARD_SPACES,
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    BoardSpace,
    DynamicCost,
    Faction,
    InfluenceRequirement,
    ResourceCost,
)
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_bonds import has_faction_bond


def legal_agent_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Enumerate card-and-space pairs currently legal for ``player``.

    Occupied spaces, Agent-icon access, printed costs, and printed Influence
    requirements are enforced here. Infiltrate is handled as a distinct form of
    an Agent action because it must also identify the Spy being recalled.
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
    actions: list[DomainAction] = []
    for card_instance_id in owner.hand:
        card = personal_card_for_instance(card_instance_id)
        for space in BOARD_SPACES:
            if not card_can_access_space(card.agent_icons, space, owner):
                continue
            if space.space_id in owner.agent_locations:
                continue
            if space.space_id == "swordmaster" and owner.swordmaster_acquired:
                continue
            if not _meets_requirement(owner.influence, space.requirement):
                continue
            occupying_opponents = tuple(
                candidate.player_id
                for candidate in state.players
                if candidate.player_id != player
                and space.space_id in candidate.agent_locations
            )
            if not occupying_opponents:
                actions.extend(
                    _actions_for_affordable_costs(
                        player,
                        card_instance_id,
                        space,
                        owner,
                        state,
                    )
                )
                continue
            # OQ-006 intentionally leaves multi-opponent occupancy unavailable
            # until an official ruling determines how many Spies it requires.
            if len(occupying_opponents) > 1:
                continue
            for post_id in _connected_spy_post_ids(owner, space.space_id):
                actions.extend(
                    _actions_for_affordable_costs(
                        player,
                        card_instance_id,
                        space,
                        owner,
                        state,
                        infiltrate_post_id=post_id,
                    )
                )
    return tuple(actions)


def card_can_access_space(
    agent_icons: tuple[AgentIcon, ...],
    space: BoardSpace,
    owner: PlayerState,
) -> bool:
    """Return whether a card's Agent icons make ``space`` a destination.

    A printed icon grants direct access. The Spy Agent icon instead grants
    access when at least one of the owner's currently placed Spies is connected
    to the destination, without recalling that Spy.
    """

    if space.agent_icon in agent_icons:
        return True
    if AgentIcon.SPY not in agent_icons:
        return False
    return bool(_connected_spy_post_ids(owner, space.space_id))


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

    card = personal_card_for_instance(card_instance_id)
    space = BOARD_SPACES_BY_ID[space_id]
    cost_option, cost = _selected_cost(state, space, arguments.get("cost_option"))
    owner = state.players[action.actor]
    infiltrate_post_id = arguments.get("infiltrate_post_id")
    if infiltrate_post_id is not None and not isinstance(infiltrate_post_id, str):
        raise ValueError("Agent action infiltrate_post_id must be a string")
    next_owner = replace(
        owner,
        resources=_pay_cost(owner.resources, cost),
        agents_available=owner.agents_available - 1,
        agent_locations=(*owner.agent_locations, space_id),
        spies_supply=owner.spies_supply + int(infiltrate_post_id is not None),
        spy_post_ids=tuple(
            post_id for post_id in owner.spy_post_ids if post_id != infiltrate_post_id
        ),
        hand=tuple(card_id for card_id in owner.hand if card_id != card_instance_id),
        in_play=(*owner.in_play, card_instance_id),
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    effect_frame = DecisionFrame(
        frame_id=(f"round:{state.round_number}:player:{action.actor}:agent_effects"),
        decision=PlayerDecision(
            owner=action.actor,
            prompt="Choose the next Agent-turn effect to resolve",
        ),
        context=(
            ("card_id", card_instance_id),
            ("cost_option", cost_option),
            (
                "pending_agent_effect",
                _agent_effect_is_available(
                    card.agent_effect,
                    owner,
                    space,
                    card_instance_id,
                ),
            ),
            ("pending_board_effect", True),
            ("pending_combat_deployment", space.combat),
            ("pending_faction_influence", space.faction is not None),
            (
                "pending_gather_intelligence",
                any(
                    space_id in post.connected_space_ids
                    and post.post_id in next_owner.spy_post_ids
                    for post in OBSERVATION_POSTS
                ),
            ),
            ("space_id", space_id),
            ("troops_recruited", 0),
            ("turn_owner", action.actor),
        ),
    )
    next_state = replace(
        state,
        players=players,
        decision_stack=(*state.decision_stack[:-1], effect_frame),
    )
    placement_event = GameEvent(
        event_id=(f"round:{state.round_number}:player:{action.actor}:agent:{space_id}"),
        kind="agent_placed",
        payload=(
            ("card_id", card_instance_id),
            ("player", action.actor),
            ("space_id", space_id),
        ),
    )
    infiltration_events = (
        ()
        if infiltrate_post_id is None
        else (
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"infiltrate:{space_id}:{infiltrate_post_id}"
                ),
                kind="spy_recalled_for_infiltrate",
                payload=(
                    ("player", action.actor),
                    ("post_id", infiltrate_post_id),
                    ("space_id", space_id),
                ),
            ),
        )
    )
    next_state, control_event = _apply_control_visit_bonus(next_state, space_id)
    events = (
        (placement_event, *infiltration_events)
        if control_event is None
        else (placement_event, *infiltration_events, control_event)
    )
    return RuleResult(state=next_state, events=events)


def _agent_effect_is_available(
    effect: PersonalCardAgentEffect | None,
    owner: PlayerState,
    space: BoardSpace,
    card_instance_id: str,
) -> bool:
    if effect is None:
        return False
    if effect is PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO:
        return owner.influence.bene_gesserit >= 2
    if effect is PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO:
        return owner.resources.water >= 2
    if (
        effect
        is PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
    ):
        return owner.influence.bene_gesserit >= 2
    if effect is PersonalCardAgentEffect.GAIN_SPICE_IF_MAKER_SPACE:
        return space.maker
    if effect is PersonalCardAgentEffect.RECRUIT_ONE_IF_MAKER_SPACE:
        return space.maker
    if (
        effect
        is PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO
    ):
        return (
            owner.influence.bene_gesserit >= 2 or owner.influence.fremen >= 2
        )
    if effect is PersonalCardAgentEffect.RECRUIT_TWO_IF_BENE_GESSERIT_BOND:
        return has_faction_bond(
            (*owner.in_play, card_instance_id),
            card_instance_id,
            Faction.BENE_GESSERIT,
        )
    if effect is PersonalCardAgentEffect.RETURN_SELF_IF_BENE_GESSERIT_BOND:
        return has_faction_bond(
            (*owner.in_play, card_instance_id),
            card_instance_id,
            Faction.BENE_GESSERIT,
        )
    return True


def _actions_for_affordable_costs(
    player: int,
    card_instance_id: str,
    space: BoardSpace,
    owner: PlayerState,
    state: GameState,
    infiltrate_post_id: str | None = None,
) -> tuple[DomainAction, ...]:
    costs = _effective_costs(state, space)
    include_choice = space.dynamic_cost is None and len(space.cost_options) > 1
    actions: list[DomainAction] = []
    for cost_option, cost in costs:
        if not _can_afford(owner, cost):
            continue
        argument_items: list[tuple[str, str | int]] = [("card_id", card_instance_id)]
        if include_choice:
            argument_items.append(("cost_option", cost_option))
        if infiltrate_post_id is not None:
            argument_items.append(("infiltrate_post_id", infiltrate_post_id))
        argument_items.append(("space_id", space.space_id))
        actions.append(
            DomainAction(
                action_id="agent_turn",
                actor=player,
                arguments=tuple(argument_items),
            )
        )
    return tuple(actions)


def _connected_spy_post_ids(
    owner: PlayerState,
    space_id: str,
) -> tuple[str, ...]:
    connected_post_ids = {
        post.post_id
        for post in OBSERVATION_POSTS
        if space_id in post.connected_space_ids
    }
    return tuple(
        post_id for post_id in owner.spy_post_ids if post_id in connected_post_ids
    )


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


def _apply_control_visit_bonus(
    state: GameState,
    space_id: str,
) -> tuple[GameState, GameEvent | None]:
    resource = {
        "arrakeen": "solari",
        "spice_refinery": "solari",
        "imperial_basin": "spice",
    }.get(space_id)
    if resource is None:
        return state, None
    controllers = tuple(
        player for player in state.players if space_id in player.control_space_ids
    )
    if not controllers:
        return state, None
    if len(controllers) > 1:
        raise RuntimeError("a critical location cannot have multiple controllers")

    controller = controllers[0]
    next_controller = replace(
        controller,
        resources=replace(
            controller.resources,
            **{resource: getattr(controller.resources, resource) + 1},
        ),
    )
    players = tuple(
        next_controller if player.player_id == next_controller.player_id else player
        for player in state.players
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:control_bonus:{space_id}:"
            f"{controller.player_id}"
        ),
        kind="control_bonus_gained",
        payload=(
            ("amount", 1),
            ("player", controller.player_id),
            ("resource", resource),
            ("space_id", space_id),
        ),
    )
    return replace(state, players=players), event
