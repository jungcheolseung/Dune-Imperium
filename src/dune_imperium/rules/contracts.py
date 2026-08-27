"""Public Contract market choices for the Uprising CHOAM Module."""

from dataclasses import replace

from dune_imperium.content.uprising.contracts import contract_for_instance
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState


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
    if state.face_up_contract_ids:
        return RuleResult(
            state=state.push_decision(
                contract_choice_frame(player, count, source=source)
            )
        )
    return _gain_exhausted_market_solari(state, player, count, source=source)


def legal_contract_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return every currently face-up Contract for the pending owner."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if ":contract_market:" not in frame.frame_id:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    return tuple(
        DomainAction(
            action_id="take_contract",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in state.face_up_contract_ids
    )


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
    market_index = market.index(instance_value)
    bank = state.contract_bank
    replacement_id = bank[0] if bank else ""
    if replacement_id:
        market[market_index] = replacement_id
        bank = bank[1:]
    else:
        del market[market_index]

    definition = contract_for_instance(instance_value)
    owner = state.players[action.actor]
    if definition.completes_immediately:
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + 2,
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
                    ("solari", 2),
                ),
            )
        )
    return RuleResult(state=next_state, events=tuple(events))


def exhausted_contract_choice_is_pending(state: GameState) -> bool:
    """Return whether the top Contract frame can resolve without player input."""

    return bool(
        state.decision_stack
        and ":contract_market:" in state.decision_stack[-1].frame_id
        and not state.face_up_contract_ids
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
