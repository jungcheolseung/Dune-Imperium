"""Spy decisions tied to Agent placement timing."""

from dataclasses import replace

from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
)


def legal_gather_intelligence_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the immediate post-placement Gather Intelligence choice."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_gather_intelligence") is not True:
        return ()
    space_id = context.get("space_id")
    if not isinstance(space_id, str):
        raise RuntimeError("Agent-turn effect frame has invalid space ID")

    owner = state.players[player]
    connected_post_ids = {
        post.post_id
        for post in OBSERVATION_POSTS
        if space_id in post.connected_space_ids
    }
    actions = [
        DomainAction(action_id="decline_gather_intelligence", actor=player)
    ]
    if owner.deck:
        actions.extend(
            DomainAction(
                action_id="gather_intelligence",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in owner.spy_post_ids
            if post_id in connected_post_ids
        )
    return tuple(actions)


def apply_gather_intelligence_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline Gather Intelligence or recall one connected Spy to draw."""

    if action not in legal_gather_intelligence_actions(state, action.actor):
        raise ValueError("action is not a legal Gather Intelligence choice")
    _, context = current_agent_effect_context(state)
    owner = state.players[action.actor]
    events: list[GameEvent] = []
    if action.action_id == "gather_intelligence":
        post_id = dict(action.arguments).get("post_id")
        if not isinstance(post_id, str):
            raise RuntimeError("Gather Intelligence has invalid post ID")
        owner = replace(
            owner,
            spies_supply=owner.spies_supply + 1,
            spy_post_ids=tuple(
                candidate for candidate in owner.spy_post_ids if candidate != post_id
            ),
            deck=owner.deck[1:],
            hand=(*owner.hand, owner.deck[0]),
        )
        events.append(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"gather_intelligence:{post_id}"
                ),
                kind="gather_intelligence",
                payload=(("player", action.actor), ("post_id", post_id)),
            )
        )

    context["pending_gather_intelligence"] = False
    players = tuple(
        owner if candidate.player_id == action.actor else candidate
        for candidate in state.players
    )
    next_state = advance_after_effect(state, context, players)
    return RuleResult(state=next_state, events=tuple(events))
