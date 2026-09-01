"""Public Contract market choices for the Uprising CHOAM Module."""

from dataclasses import replace

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.contracts import (
    ContractConditionKind,
    ContractDefinition,
    contract_for_instance,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
    eligible_agent_contract_ids,
    pending_agent_contract_ids,
    recruit_troops,
)
from dune_imperium.rules.frames import FrameKind, replace_player
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    place_spy,
    recall_spy,
)


def contract_candidates_for_agent_turn(
    state: GameState,
    player: int,
    space_id: str,
) -> tuple[str, ...]:
    """Snapshot Contracts held when an Agent enters a matching space."""

    if not state.config.choam_module:
        return ()
    if not 0 <= player < state.config.players:
        raise ValueError("Contract owner must identify a configured player")
    space = BOARD_SPACES_BY_ID[space_id]
    candidates: list[str] = []
    for instance_id in state.players[player].active_contract_ids:
        condition = contract_for_instance(instance_id).condition
        if (
            condition.kind is ContractConditionKind.BOARD_SPACE
            and condition.target == space_id
        ) or (
            condition.kind is ContractConditionKind.HARVEST_SPICE
            and space.maker
        ):
            candidates.append(instance_id)
    return tuple(candidates)


def legal_contract_completion_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return mandatory Agent-turn Contract completions now available."""

    if not state.config.choam_module or not 0 <= player < state.config.players:
        return ()
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or context.get("pending_gather_intelligence") is True
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="complete_contract",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in eligible_agent_contract_ids(context, state.players)
    )


def apply_contract_completion(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Complete one eligible Contract and resolve its printed reward."""

    if action not in legal_contract_completion_actions(state, action.actor):
        raise ValueError("action is not a legal Contract completion")
    instance_id = dict(action.arguments).get("instance_id")
    if not isinstance(instance_id, str):
        raise RuntimeError("Contract completion has invalid instance ID")
    _, context = current_agent_effect_context(state)
    remaining = tuple(
        candidate
        for candidate in pending_agent_contract_ids(context)
        if candidate != instance_id
    )
    context["pending_contract_ids"] = ",".join(remaining)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"contract:{instance_id}"
    )
    garrison_before = state.players[action.actor].troops_garrison
    completed = _complete_contract_without_choices(
        state,
        action.actor,
        instance_id,
        source=source,
    )
    recruited = completed.state.players[action.actor].troops_garrison - garrison_before
    if recruited:
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
    next_state = advance_after_effect(
        completed.state,
        context,
        completed.state.players,
    )
    definition = contract_for_instance(instance_id)
    turn_space_id = context.get("space_id")
    follow_up = _begin_contract_reward_choice(
        next_state,
        action.actor,
        definition,
        source=source,
        excluded_space_id=turn_space_id if isinstance(turn_space_id, str) else "",
    )
    return RuleResult(
        state=follow_up.state,
        events=(*completed.events, *follow_up.events),
    )


def complete_acquire_contracts(
    state: GameState,
    player: int,
    acquired_card_id: str,
    *,
    source: str,
) -> RuleResult:
    """Complete Contracts triggered by acquiring a named card."""

    if not state.config.choam_module:
        return RuleResult(state=state)
    if not 0 <= player < state.config.players:
        raise ValueError("Contract owner must identify a configured player")
    if not acquired_card_id or not source:
        raise ValueError("Acquire Contract trigger requires card and source IDs")
    matching = tuple(
        instance_id
        for instance_id in state.players[player].active_contract_ids
        if (
            (condition := contract_for_instance(instance_id).condition).kind
            is ContractConditionKind.ACQUIRE_CARD
            and condition.target == acquired_card_id
        )
    )
    next_state = state
    events: tuple[GameEvent, ...] = ()
    for instance_id in matching:
        completed = _complete_contract_without_choices(
            next_state,
            player,
            instance_id,
            source=f"{source}:contract:{instance_id}",
        )
        definition = contract_for_instance(instance_id)
        if any(
            (
                definition.reward.personal_cards,
                definition.reward.contracts,
                definition.reward.spies,
            )
        ):
            raise NotImplementedError(
                "Acquire Contracts with choice rewards require an explicit frame"
            )
        next_state = completed.state
        events = (*events, *completed.events)
    return RuleResult(state=next_state, events=events)


def legal_contract_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return recall-or-place choices for a Contract Spy reward."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or "contract_spy_id" not in context
    ):
        return ()
    owner = state.players[player]
    if context.get("contract_spy_recalled") is True or owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_contract_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in empty_observation_post_ids(state)
        )
    return tuple(
        DomainAction(
            action_id="recall_spy_for_contract",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in owner.spy_post_ids
    )


def apply_contract_spy_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Recall if necessary, then place a Spy granted by a Contract."""

    if action not in legal_contract_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Contract Spy choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    instance_id = context.get("contract_spy_id")
    source = context.get("source")
    post_id = dict(action.arguments).get("post_id")
    if (
        not isinstance(instance_id, str)
        or not isinstance(source, str)
        or not isinstance(post_id, str)
    ):
        raise RuntimeError("Contract Spy frame has invalid context")
    owner = state.players[action.actor]
    if action.action_id == "recall_spy_for_contract":
        next_owner = recall_spy(owner, post_id)
        context["contract_spy_recalled"] = True
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        next_state = replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=(*state.decision_stack[:-1], next_frame),
        )
        event = GameEvent(
            event_id=f"{source}:spy_recalled:{post_id}",
            kind="spy_recalled",
            payload=(
                ("player", action.actor),
                ("post_id", post_id),
                ("source", instance_id),
            ),
        )
        return RuleResult(state=next_state, events=(event,))

    next_owner = place_spy(owner, post_id)
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
        decision_stack=state.decision_stack[:-1],
    )
    event = GameEvent(
        event_id=f"{source}:spy_placed:{post_id}",
        kind="spy_placed",
        payload=(
            ("contract_id", instance_id),
            ("player", action.actor),
            ("post_id", post_id),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_contract_recall_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the Agents a Contract recall reward may return to the Leader."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.CONTRACT_REWARD_RECALL:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    excluded = dict(frame.context).get("excluded_space_id")
    return tuple(
        DomainAction(
            action_id="recall_agent_for_contract",
            actor=player,
            arguments=(("space_id", space_id),),
        )
        for space_id in state.players[player].agent_locations
        if space_id != excluded
    )


def apply_contract_recall_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Recall the chosen Agent for a completed Contract [Main p. 20]."""

    if action not in legal_contract_recall_actions(state, action.actor):
        raise ValueError("action is not a legal Contract recall choice")
    space_id = dict(action.arguments).get("space_id")
    if not isinstance(space_id, str):
        raise RuntimeError("Contract recall choice has invalid space ID")
    source = dict(state.decision_stack[-1].context).get("source")
    if not isinstance(source, str):
        raise RuntimeError("Contract recall frame has invalid source")
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        agents_available=owner.agents_available + 1,
        agent_locations=tuple(
            location for location in owner.agent_locations if location != space_id
        ),
    )
    next_state = replace(
        state.pop_decision(),
        players=replace_player(state.players, next_owner),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:reward:recall:{space_id}",
                kind="agent_recalled",
                payload=(
                    ("player", action.actor),
                    ("source", source),
                    ("space_id", space_id),
                ),
            ),
        ),
    )


def contract_choice_frame(
    player: int,
    count: int,
    *,
    source: str,
) -> DecisionFrame:
    """Build one serial choice for one or more Contract icons."""

    if player < 0:
        raise ValueError("Contract owner must not be negative")
    if count < 1:
        raise ValueError("Contract choice count must be positive")
    if not source:
        raise ValueError("Contract choice source must not be empty")
    return DecisionFrame(
        kind=FrameKind.CONTRACT_MARKET,
        frame_id=f"{source}:contract_market:{player}",
        decision=PlayerDecision(owner=player, prompt="Take a face-up Contract"),
        context=(("remaining", count), ("source", source)),
    )


def begin_contract_gain(
    state: GameState,
    player: int,
    count: int,
    *,
    source: str,
) -> RuleResult:
    """Open a market choice, or convert exhausted Contract icons to Solari."""

    if not state.config.choam_module:
        raise ValueError("Contract gains require the CHOAM Module")
    if not 0 <= player < state.config.players:
        raise ValueError("Contract owner must identify a configured player")
    if count < 1:
        raise ValueError("Contract gain count must be positive")
    if not source:
        raise ValueError("Contract choice source must not be empty")
    if state.face_up_contract_ids or _holds_set_aside_choice(state, player):
        # Over an exhausted market Shaddam Corrino IV still chooses between
        # his set-aside Sardaukar Contracts and the two-Solari conversion
        # (OQ-021), so his icons open the frame instead of auto-converting.
        return RuleResult(
            state=state.push_decision(
                contract_choice_frame(player, count, source=source)
            )
        )
    return _gain_exhausted_market_solari(state, player, count, source=source)


def _holds_set_aside_choice(state: GameState, player: int) -> bool:
    return (
        state.players[player].leader_id == "shaddam_corrino_iv"
        and bool(state.sardaukar_contract_ids)
    )


def legal_contract_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return every Contract the pending owner may take right now.

    Shaddam Corrino IV may acquire a set-aside Sardaukar Contract in place
    of one of the generally available Contracts [FAQ p. 3], so his choices
    add the set-aside tiles while the market itself is open.
    """

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.CONTRACT_MARKET:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    set_aside = (
        state.sardaukar_contract_ids
        if state.players[player].leader_id == "shaddam_corrino_iv"
        else ()
    )
    actions = [
        DomainAction(
            action_id="take_contract",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in (*state.face_up_contract_ids, *set_aside)
    ]
    if set_aside and not state.face_up_contract_ids:
        # With every generally available Contract taken, each of Shaddam's
        # icons chooses between a set-aside tile and the printed two-Solari
        # conversion [Main p. 16] (OQ-021).
        actions.append(
            DomainAction(action_id="take_exhausted_contract_solari", actor=player)
        )
    return tuple(actions)


def apply_contract_action(state: GameState, action: DomainAction) -> RuleResult:
    """Take one face-up Contract and refill its market position when possible."""

    if action not in legal_contract_actions(state, action.actor):
        raise ValueError("action is not a legal Contract choice")
    instance_value = dict(action.arguments).get("instance_id")
    if not isinstance(instance_value, str):
        raise RuntimeError("Contract choice has invalid instance ID")

    frame = state.decision_stack[-1]
    context = dict(frame.context)
    remaining_value = context.get("remaining")
    source_value = context.get("source")
    if (
        isinstance(remaining_value, bool)
        or not isinstance(remaining_value, int)
        or remaining_value < 1
        or not isinstance(source_value, str)
    ):
        raise RuntimeError("Contract choice frame has invalid context")

    market = list(state.face_up_contract_ids)
    bank = state.contract_bank
    sardaukar_set_aside = state.sardaukar_contract_ids
    replacement_id = ""
    if instance_value in sardaukar_set_aside:
        # A set-aside Sardaukar Contract is taken in place of a face-up one
        # [FAQ p. 3]; the market keeps its tiles and nothing refills.
        sardaukar_set_aside = tuple(
            candidate
            for candidate in sardaukar_set_aside
            if candidate != instance_value
        )
    else:
        market_index = market.index(instance_value)
        replacement_id = bank[0] if bank else ""
        if replacement_id:
            market[market_index] = replacement_id
            bank = bank[1:]
        else:
            del market[market_index]

    definition = contract_for_instance(instance_value)
    owner = state.players[action.actor]
    if definition.completes_immediately:
        reward = definition.reward
        if any(
            (
                reward.water,
                reward.troops,
                reward.personal_cards,
                reward.contracts,
                reward.spies,
                reward.influence,
            )
        ):
            raise NotImplementedError(
                "Immediate Contracts with non-Solari rewards are not implemented"
            )
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + reward.solari,
            ),
            completed_contract_ids=(
                *owner.completed_contract_ids,
                instance_value,
            ),
        )
    else:
        next_owner = replace(
            owner,
            active_contract_ids=(*owner.active_contract_ids, instance_value),
        )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )

    remaining_count = remaining_value - 1
    remaining_stack = state.decision_stack[:-1]
    if remaining_count:
        remaining_stack = (
            *remaining_stack,
            replace(
                frame,
                context=(
                    ("remaining", remaining_count),
                    ("source", source_value),
                ),
            ),
        )
    next_state = replace(
        state,
        players=players,
        contract_bank=bank,
        face_up_contract_ids=tuple(market),
        sardaukar_contract_ids=sardaukar_set_aside,
        decision_stack=remaining_stack,
        combat_rewards_resolved=(
            not remaining_stack
            if state.phase is GamePhase.COMBAT
            else state.combat_rewards_resolved
        ),
    )
    events = [
        GameEvent(
            event_id=(
                f"{source_value}:contract_taken:{action.actor}:{instance_value}:"
                f"{remaining_value}"
            ),
            kind="contract_taken",
            payload=(
                ("contract_id", instance_value),
                ("player", action.actor),
                ("replacement_id", replacement_id),
                ("source", source_value),
            ),
        )
    ]
    if definition.completes_immediately:
        events.append(
            GameEvent(
                event_id=(
                    f"{source_value}:contract_completed:{action.actor}:{instance_value}"
                ),
                kind="contract_completed",
                payload=(
                    ("contract_id", instance_value),
                    ("player", action.actor),
                    ("solari", definition.reward.solari),
                ),
            )
        )
    return RuleResult(state=next_state, events=tuple(events))


def apply_exhausted_contract_solari(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Convert one of Shaddam's Contract icons to two Solari by choice.

    Over an exhausted market his icons choose between a set-aside Sardaukar
    Contract and the printed two-Solari conversion [Main p. 16] (OQ-021).
    """

    if action not in legal_contract_actions(state, action.actor):
        raise ValueError("action is not a legal Contract choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    remaining_value = context.get("remaining")
    source_value = context.get("source")
    if (
        isinstance(remaining_value, bool)
        or not isinstance(remaining_value, int)
        or remaining_value < 1
        or not isinstance(source_value, str)
    ):
        raise RuntimeError("Contract choice frame has invalid context")

    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        resources=replace(owner.resources, solari=owner.resources.solari + 2),
    )
    players = tuple(
        next_owner if candidate.player_id == action.actor else candidate
        for candidate in state.players
    )
    remaining_count = remaining_value - 1
    remaining_stack = state.decision_stack[:-1]
    if remaining_count:
        remaining_stack = (
            *remaining_stack,
            replace(
                frame,
                context=(
                    ("remaining", remaining_count),
                    ("source", source_value),
                ),
            ),
        )
    next_state = replace(
        state,
        players=players,
        decision_stack=remaining_stack,
        combat_rewards_resolved=(
            not remaining_stack
            if state.phase is GamePhase.COMBAT
            else state.combat_rewards_resolved
        ),
    )
    event = GameEvent(
        event_id=(
            f"{source_value}:contract_market_exhausted:{action.actor}:"
            f"choice:{remaining_value}"
        ),
        kind="contract_icons_converted_to_solari",
        payload=(
            ("count", 1),
            ("player", action.actor),
            ("solari", 2),
            ("source", source_value),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def exhausted_contract_choice_is_pending(state: GameState) -> bool:
    """Return whether the top Contract frame can resolve without player input."""

    if not state.decision_stack:
        return False
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.CONTRACT_MARKET or state.face_up_contract_ids:
        return False
    # Shaddam still holds a real choice over an exhausted market: a
    # set-aside Sardaukar Contract or the two-Solari conversion (OQ-021).
    return not (
        isinstance(frame.decision, PlayerDecision)
        and _holds_set_aside_choice(state, frame.decision.owner)
    )


def resolve_exhausted_contract_choice(state: GameState) -> RuleResult:
    """Convert every icon left in the top choice frame to two Solari."""

    if not exhausted_contract_choice_is_pending(state):
        raise ValueError("there is no exhausted Contract choice to resolve")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    remaining = context.get("remaining")
    source = context.get("source")
    if (
        isinstance(remaining, bool)
        or not isinstance(remaining, int)
        or remaining < 1
        or not isinstance(source, str)
        or not isinstance(frame.decision, PlayerDecision)
    ):
        raise RuntimeError("Contract choice frame has invalid context")
    working = replace(state, decision_stack=state.decision_stack[:-1])
    return _gain_exhausted_market_solari(
        working,
        frame.decision.owner,
        remaining,
        source=source,
    )


def _gain_exhausted_market_solari(
    state: GameState,
    player: int,
    count: int,
    *,
    source: str,
) -> RuleResult:
    owner = state.players[player]
    solari = count * 2
    next_owner = replace(
        owner,
        resources=replace(owner.resources, solari=owner.resources.solari + solari),
    )
    players = tuple(
        next_owner if candidate.player_id == player else candidate
        for candidate in state.players
    )
    next_state = replace(
        state,
        players=players,
        combat_rewards_resolved=(
            not state.decision_stack
            if state.phase is GamePhase.COMBAT
            else state.combat_rewards_resolved
        ),
    )
    event = GameEvent(
        event_id=f"{source}:contract_market_exhausted:{player}:{count}",
        kind="contract_icons_converted_to_solari",
        payload=(
            ("count", count),
            ("player", player),
            ("solari", solari),
            ("source", source),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def _complete_contract_without_choices(
    state: GameState,
    player: int,
    instance_id: str,
    *,
    source: str,
) -> RuleResult:
    definition = contract_for_instance(instance_id)
    owner = state.players[player]
    if instance_id not in owner.active_contract_ids:
        raise ValueError("completed Contract must be active")
    reward = definition.reward
    next_owner, recruited = recruit_troops(owner, reward.troops)
    next_owner = replace(
        next_owner,
        resources=replace(
            next_owner.resources,
            solari=next_owner.resources.solari + reward.solari,
            water=next_owner.resources.water + reward.water,
        ),
        active_contract_ids=tuple(
            candidate
            for candidate in next_owner.active_contract_ids
            if candidate != instance_id
        ),
        completed_contract_ids=(
            *next_owner.completed_contract_ids,
            instance_id,
        ),
    )
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
    )
    influence_events: tuple[GameEvent, ...] = ()
    if reward.influence_faction is not None:
        gained = gain_faction_influence(
            next_state,
            player,
            reward.influence_faction,
            reward.influence,
            event_prefix=f"{source}:reward:{reward.influence_faction.value}",
        )
        next_state = gained.state
        influence_events = gained.events
    event = GameEvent(
        event_id=f"{source}:completed",
        kind="contract_completed",
        payload=(
            ("contract_id", instance_id),
            ("contracts", reward.contracts),
            ("influence", reward.influence),
            (
                "influence_faction",
                ""
                if reward.influence_faction is None
                else reward.influence_faction.value,
            ),
            ("personal_cards", reward.personal_cards),
            ("player", player),
            ("recall_agents", reward.recall_agents),
            ("solari", reward.solari),
            ("spies", reward.spies),
            ("troops", recruited),
            ("water", reward.water),
        ),
    )
    return RuleResult(state=next_state, events=(event, *influence_events))


def _begin_contract_reward_choice(
    state: GameState,
    player: int,
    definition: ContractDefinition,
    *,
    source: str,
    excluded_space_id: str = "",
) -> RuleResult:
    reward = definition.reward
    choice_count = sum(
        bool(value)
        for value in (
            reward.personal_cards,
            reward.contracts,
            reward.spies,
            reward.recall_agents,
        )
    )
    if choice_count > 1:
        raise NotImplementedError(
            "Contract rewards with multiple serial choices are not implemented"
        )
    if reward.recall_agents:
        # Recall one of your Agents; the just-sent Agent is not a valid
        # target [Main p. 20], and with no other placed Agent the reward
        # does nothing.
        candidates = tuple(
            space_id
            for space_id in state.players[player].agent_locations
            if space_id != excluded_space_id
        )
        if not candidates:
            return RuleResult(
                state=state,
                events=(
                    GameEvent(
                        event_id=f"{source}:reward:recall_unavailable",
                        kind="contract_recall_unavailable",
                        payload=(("player", player),),
                    ),
                ),
            )
        frame = DecisionFrame(
            kind=FrameKind.CONTRACT_REWARD_RECALL,
            frame_id=f"{source}:reward:recall",
            decision=PlayerDecision(
                owner=player,
                prompt="Choose one of your other Agents to recall",
            ),
            context=(
                ("excluded_space_id", excluded_space_id),
                ("source", source),
                ("turn_owner", player),
            ),
        )
        return RuleResult(state=state.push_decision(frame))
    if reward.personal_cards:
        return draw_or_request_personal_cards(
            state,
            player,
            reward.personal_cards,
            source=f"{source}:reward:personal_draw",
        )
    if reward.contracts:
        return begin_contract_gain(
            state,
            player,
            reward.contracts,
            source=f"{source}:reward",
        )
    if reward.spies:
        frame = DecisionFrame(
            kind=FrameKind.CONTRACT_REWARD_SPY,
            frame_id=f"{source}:reward:spy",
            decision=PlayerDecision(
                owner=player,
                prompt="Choose an Observation Post for the Contract Spy",
            ),
            context=(
                ("contract_spy_id", f"contract:{definition.card.card_id}"),
                ("source", source),
                ("turn_owner", player),
            ),
        )
        return RuleResult(state=state.push_decision(frame))
    return RuleResult(state=state)

