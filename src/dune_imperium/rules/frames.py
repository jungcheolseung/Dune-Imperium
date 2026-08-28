"""Decision-frame kinds and shared frame/context helpers for rule modules."""

from dataclasses import replace
from enum import StrEnum

from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState

type FrameContext = dict[str, ActionValue]


class FrameKind(StrEnum):
    """Every decision frame the Uprising rules currently push."""

    TURN = "turn"
    AGENT_EFFECTS = "agent_effects"
    OPPONENT_CARD_DISCARD = "opponent_card_discard"
    ACQUISITION_SPY = "acquisition_spy"
    REVEAL = "reveal"
    REVEAL_CHOICE = "reveal_choice"
    CONTRACT_MARKET = "contract_market"
    CONTRACT_REWARD_SPY = "contract_reward_spy"
    CONTROL_DEFENSE = "control_defense"
    COMBAT_INTRIGUE = "combat_intrigue"
    COMBAT_REWARD_INFLUENCE = "combat_reward_influence"
    COMBAT_REWARD_DISTINCT_INFLUENCE = "combat_reward_distinct_influence"
    COMBAT_REWARD_OPTIONAL = "combat_reward_optional"
    COMBAT_REWARD_SPY_RECALL = "combat_reward_spy_recall"
    COMBAT_REWARD_TRASH = "combat_reward_trash"
    COMBAT_REWARD_SPY = "combat_reward_spy"
    ENDGAME_WILD = "endgame_wild"
    ROUND_START_RESHUFFLE = "round_start_reshuffle"
    PERSONAL_DRAW_RESHUFFLE = "personal_draw_reshuffle"
    INTRIGUE_RESHUFFLE = "intrigue_reshuffle"
    INTRIGUE_CHOICE = "intrigue_choice"


def top_frame(state: GameState) -> DecisionFrame | None:
    """Return the current decision frame, if any."""

    return state.decision_stack[-1] if state.decision_stack else None


def top_frame_of_kind(state: GameState, kind: FrameKind) -> DecisionFrame | None:
    """Return the current frame only when it has ``kind``."""

    frame = top_frame(state)
    return frame if frame is not None and frame.kind == kind else None


def owned_top_frame(
    state: GameState,
    kind: FrameKind,
    player: int,
) -> DecisionFrame | None:
    """Return the current frame when ``player`` owns a ``kind`` player decision."""

    if not 0 <= player < state.config.players:
        return None
    frame = top_frame_of_kind(state, kind)
    if (
        frame is None
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return None
    return frame


def frame_context(frame: DecisionFrame) -> FrameContext:
    """Return a mutable copy of the frame's context."""

    return dict(frame.context)


def with_context(frame: DecisionFrame, context: FrameContext) -> DecisionFrame:
    """Return ``frame`` carrying ``context`` in canonical sorted order."""

    return replace(frame, context=tuple(sorted(context.items())))


def replace_top_frame(state: GameState, frame: DecisionFrame) -> GameState:
    """Return a state whose top frame is replaced by ``frame``."""

    if not state.decision_stack:
        raise IndexError("cannot replace the top of an empty decision stack")
    return replace(state, decision_stack=(*state.decision_stack[:-1], frame))


def context_int(context: FrameContext, key: str, *, owner: str = "frame") -> int:
    """Read a required non-bool integer from a frame context."""

    value = context.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(f"{owner} has invalid {key}")
    return value


def frame_context_int(frame: DecisionFrame, key: str) -> int | None:
    """Read an optional non-bool integer from a frame's context."""

    value = dict(frame.context).get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def context_str(context: FrameContext, key: str, *, owner: str = "frame") -> str:
    """Read a required string from a frame context."""

    value = context.get(key)
    if not isinstance(value, str):
        raise RuntimeError(f"{owner} has invalid {key}")
    return value


def replace_player(
    players: tuple[PlayerState, ...],
    player: PlayerState,
) -> tuple[PlayerState, ...]:
    """Return ``players`` with the seat matching ``player.player_id`` replaced."""

    return tuple(
        player if candidate.player_id == player.player_id else candidate
        for candidate in players
    )


def reveal_is_open_for(state: GameState, player: int) -> bool:
    """Return whether ``player``'s Reveal frame is on the decision stack."""

    return any(
        frame.kind == FrameKind.REVEAL
        and isinstance(frame.decision, PlayerDecision)
        and frame.decision.owner == player
        for frame in state.decision_stack
    )
