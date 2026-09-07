"""Forced Spy moves and space-bound Spy placements (Bloodlines).

Holy War and False Orders read "each opponent spying on the board space
where you sent an Agent this turn must move that Spy"; False Orders then
lets its owner place a Spy on that space. Where a Spy may move is not
printed: the project convention (OQ-036, user decision) applies the normal
placement rule, so its owner moves it to any empty Observation Post. One
is always free: thirteen posts hold at most the twelve Spies in the game.
"""

from dataclasses import replace

from dune_imperium.content.uprising.board import OBSERVATION_POSTS
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    place_spy,
    recall_spy,
)


def connected_post_ids(space_id: str) -> tuple[str, ...]:
    """Return the Observation Posts adjacent to ``space_id`` in board order."""

    return tuple(
        post.post_id
        for post in OBSERVATION_POSTS
        if space_id in post.connected_space_ids
    )


def opponent_seats(state: GameState, actor: int) -> tuple[int, ...]:
    """Return the other seats clockwise from ``actor``."""

    count = state.config.players
    return tuple((actor + offset) % count for offset in range(1, count))


def turn_space_spy_frames(
    state: GameState,
    actor: int,
    space_id: str,
    *,
    source: str,
) -> RuleResult:
    """Push one Spy-move decision per opposing Spy watching ``space_id``.

    Frames are pushed so the next clockwise opponent decides first.
    """

    posts = set(connected_post_ids(space_id))
    frames: list[DecisionFrame] = []
    for seat in opponent_seats(state, actor):
        for post_id in state.players[seat].spy_post_ids:
            if post_id not in posts:
                continue
            frames.append(
                DecisionFrame(
                    kind=FrameKind.OPPONENT_SPY_MOVE,
                    frame_id=f"{source}:spy_move:{seat}:{post_id}",
                    decision=PlayerDecision(
                        owner=seat, prompt="Move your Spy off the watched space"
                    ),
                    context=(
                        ("player", seat),
                        ("post_id", post_id),
                        ("source", source),
                    ),
                )
            )
    next_state = replace(
        state, decision_stack=(*state.decision_stack, *reversed(frames))
    )
    return RuleResult(state=next_state)


def legal_spy_move_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer every empty post; the mover chooses (OQ-036)."""

    frame = owned_top_frame(state, FrameKind.OPPONENT_SPY_MOVE, player)
    if frame is None:
        return ()
    targets = empty_observation_post_ids(state)
    if not targets:
        raise RuntimeError("thirteen posts cannot all be occupied by twelve Spies")
    return tuple(
        DomainAction(
            action_id="move_spy",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in targets
    )


def apply_spy_move(state: GameState, action: DomainAction) -> RuleResult:
    """Move the Spy to the chosen post."""

    if action not in legal_spy_move_actions(state, action.actor):
        raise ValueError("action is not a legal Spy move")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    origin = context_str(context, "post_id", owner="Spy move frame")
    owner = state.players[action.actor]
    recalled = recall_spy(owner, origin)
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{frame.frame_id}:recalled",
            kind="spy_recalled",
            payload=(("player", action.actor), ("post_id", origin)),
        )
    ]
    target = str(dict(action.arguments)["post_id"])
    next_owner = place_spy(recalled, target)
    events.append(
        GameEvent(
            event_id=f"{frame.frame_id}:placed:{target}",
            kind="spy_placed",
            payload=(("player", action.actor), ("post_id", target)),
        )
    )
    next_state = replace(
        state.pop_decision(), players=replace_player(state.players, next_owner)
    )
    return RuleResult(state=next_state, events=tuple(events))


def spy_placement_frame(
    state: GameState,
    player: int,
    allowed_post_ids: tuple[str, ...],
    *,
    source: str,
    deep_cover: bool = False,
) -> GameState:
    """Push the owner's placement of a Spy on one of ``allowed_post_ids``.

    With ``deep_cover`` the placement ignores opponents' Spies (Spy with
    Deep Cover [Bloodlines pp. 5, 12]); only the owner's own Spies block.
    """

    return state.push_decision(
        DecisionFrame(
            kind=FrameKind.SPY_PLACEMENT,
            frame_id=f"{source}:spy_placement",
            decision=PlayerDecision(
                owner=player,
                prompt=(
                    "Place a Spy with Deep Cover"
                    if deep_cover
                    else "Place a Spy on the watched space"
                ),
            ),
            context=(
                ("allowed_post_ids", ",".join(allowed_post_ids)),
                ("deep_cover", deep_cover),
                ("player", player),
                ("source", source),
            ),
        )
    )


def legal_spy_placement_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Place on an allowed empty post, recalling first without a Spy in supply."""

    frame = owned_top_frame(state, FrameKind.SPY_PLACEMENT, player)
    if frame is None:
        return ()
    context = dict(frame.context)
    allowed = frozenset(
        context_str(context, "allowed_post_ids", owner="Spy placement frame").split(",")
    )
    owner = state.players[player]
    if context.get("deep_cover") is True:
        targets = tuple(
            post.post_id
            for post in OBSERVATION_POSTS
            if post.post_id in allowed and post.post_id not in owner.spy_post_ids
        )
    else:
        targets = empty_observation_post_ids(state, allowed)
    if targets and owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_spy_on_space",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in targets
        )
    if targets and owner.spy_post_ids:
        # No Spy in supply: recall one first [Main pp. 11, 20].
        return tuple(
            DomainAction(
                action_id="recall_spy_for_placement",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in owner.spy_post_ids
        )
    # Nothing can be placed (every allowed post is occupied, or no Spy).
    return (DomainAction(action_id="decline_spy_placement", actor=player),)


def apply_spy_placement(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve the placement frame's chosen action."""

    if action not in legal_spy_placement_actions(state, action.actor):
        raise ValueError("action is not a legal Spy placement choice")
    frame = state.decision_stack[-1]
    owner = state.players[action.actor]
    if action.action_id == "decline_spy_placement":
        return RuleResult(
            state=state.pop_decision(),
            events=(
                GameEvent(
                    event_id=f"{frame.frame_id}:unavailable",
                    kind="spy_placement_unavailable",
                    payload=(("player", action.actor),),
                ),
            ),
        )
    post_id = str(dict(action.arguments)["post_id"])
    if action.action_id == "recall_spy_for_placement":
        recalled = recall_spy(owner, post_id)
        return RuleResult(
            state=replace(state, players=replace_player(state.players, recalled)),
            events=(
                GameEvent(
                    event_id=f"{frame.frame_id}:recalled:{post_id}",
                    kind="spy_recalled",
                    payload=(("player", action.actor), ("post_id", post_id)),
                ),
            ),
        )
    placed = place_spy(owner, post_id)
    return RuleResult(
        state=replace(
            state.pop_decision(), players=replace_player(state.players, placed)
        ),
        events=(
            GameEvent(
                event_id=f"{frame.frame_id}:placed:{post_id}",
                kind="spy_placed",
                payload=(("player", action.actor), ("post_id", post_id)),
            ),
        ),
    )
