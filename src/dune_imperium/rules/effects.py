"""Small typed effects and pending-effect frame utilities."""

from dataclasses import dataclass, replace

from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState


@dataclass(frozen=True, slots=True)
class GainResourcesEffect:
    """Gain public spendable resources from the bank."""

    solari: int = 0
    spice: int = 0
    water: int = 0

    def __post_init__(self) -> None:
        if min(self.solari, self.spice, self.water) < 0:
            raise ValueError("resource gains must not be negative")
        if self.solari == self.spice == self.water == 0:
            raise ValueError("a resource-gain effect must gain something")


@dataclass(frozen=True, slots=True)
class DrawImperiumCardsEffect:
    """Draw cards from the current player's personal deck."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("card draw count must be positive")


@dataclass(frozen=True, slots=True)
class DrawIntrigueCardsEffect:
    """Draw hidden cards from the shared Intrigue deck."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("Intrigue draw count must be positive")


@dataclass(frozen=True, slots=True)
class RecruitTroopsEffect:
    """Recruit as many troops as possible up to ``count``."""

    count: int

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("troop recruit count must be positive")


type AutomaticEffect = (
    GainResourcesEffect
    | DrawImperiumCardsEffect
    | DrawIntrigueCardsEffect
    | RecruitTroopsEffect
)


def current_agent_effect_context(
    state: GameState,
) -> tuple[DecisionFrame, dict[str, ActionValue]]:
    """Return and validate the current Agent-turn effect frame."""

    if not state.decision_stack:
        raise ValueError("there is no pending Agent-turn effect frame")
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision):
        raise ValueError("the current decision is not an Agent-turn effect")
    context = dict(frame.context)
    required = {
        "card_id",
        "cost_option",
        "pending_agent_effect",
        "pending_board_effect",
        "pending_combat_deployment",
        "pending_faction_influence",
        "space_id",
        "turn_owner",
    }
    if not required.issubset(context):
        raise ValueError("the current decision is not an Agent-turn effect")
    return frame, context


def advance_after_effect(
    state: GameState,
    context: dict[str, ActionValue],
    players: tuple[PlayerState, ...] | None = None,
) -> GameState:
    """Keep the effect frame or open the clockwise player's next turn."""

    owner = context["turn_owner"]
    if isinstance(owner, bool) or not isinstance(owner, int):
        raise RuntimeError("Agent-turn effect frame has invalid owner")
    pending = (
        context["pending_agent_effect"],
        context["pending_board_effect"],
        context["pending_combat_deployment"],
        context["pending_faction_influence"],
    )
    next_players = state.players if players is None else players
    if any(value is True for value in pending):
        frame = state.decision_stack[-1]
        next_frame = replace(frame, context=tuple(sorted(context.items())))
    else:
        next_player = (owner + 1) % state.config.players
        next_frame = DecisionFrame(
            frame_id=f"round:{state.round_number}:turn:{next_player}",
            decision=PlayerDecision(
                owner=next_player,
                prompt="Choose an Agent turn or Reveal turn",
            ),
            context=(("round", state.round_number), ("turn_owner", next_player)),
        )
    return replace(
        state,
        players=next_players,
        decision_stack=(*state.decision_stack[:-1], next_frame),
    )
