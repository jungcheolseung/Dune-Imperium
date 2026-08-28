"""Small typed effects and pending-effect frame utilities."""

from dataclasses import dataclass, replace

from dune_imperium.content.uprising.contracts import (
    ContractConditionKind,
    contract_for_instance,
)
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import FrameKind


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


def recruit_troops(player: PlayerState, count: int) -> tuple[PlayerState, int]:
    """Move up to ``count`` available troops from supply to garrison."""

    if count < 0:
        raise ValueError("troop recruit count must not be negative")
    recruited = min(player.troops_supply, count)
    return (
        replace(
            player,
            troops_supply=player.troops_supply - recruited,
            troops_garrison=player.troops_garrison + recruited,
        ),
        recruited,
    )


def current_agent_effect_context(
    state: GameState,
) -> tuple[DecisionFrame, dict[str, ActionValue]]:
    """Return and validate the current Agent-turn effect frame."""

    if not state.decision_stack:
        raise ValueError("there is no pending Agent-turn effect frame")
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(
        frame.decision, PlayerDecision
    ):
        raise ValueError("the current decision is not an Agent-turn effect")
    return frame, dict(frame.context)


def advance_after_effect(
    state: GameState,
    context: dict[str, ActionValue],
    players: tuple[PlayerState, ...] | None = None,
) -> GameState:
    """Keep the effect frame or open the clockwise player's next turn."""

    owner = context["turn_owner"]
    if isinstance(owner, bool) or not isinstance(owner, int):
        raise RuntimeError("Agent-turn effect frame has invalid owner")
    regular_pending = (
        context.get("pending_gather_intelligence", False),
        context["pending_agent_effect"],
        context["pending_board_effect"],
        context["pending_combat_deployment"],
        context["pending_faction_influence"],
    )
    next_players = state.players if players is None else players
    contracts_pending = bool(eligible_agent_contract_ids(context, next_players))
    if any(value is True for value in regular_pending) or contracts_pending:
        frame = state.decision_stack[-1]
        next_frame = replace(frame, context=tuple(sorted(context.items())))
    else:
        next_player = _next_unrevealed_player(state, owner)
        next_frame = DecisionFrame(
            kind=FrameKind.TURN,
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


def pending_agent_contract_ids(
    context: dict[str, ActionValue],
) -> tuple[str, ...]:
    """Decode the Agent-frame snapshot of Contracts held at placement time."""

    value = context.get("pending_contract_ids", "")
    if not isinstance(value, str):
        raise RuntimeError("Agent-turn effect frame has invalid Contract IDs")
    return tuple(instance_id for instance_id in value.split(",") if instance_id)


def eligible_agent_contract_ids(
    context: dict[str, ActionValue],
    players: tuple[PlayerState, ...],
) -> tuple[str, ...]:
    """Return snapshot Contracts whose completion condition is now satisfied."""

    owner_value = context.get("turn_owner")
    if isinstance(owner_value, bool) or not isinstance(owner_value, int):
        raise RuntimeError("Agent-turn effect frame has invalid owner")
    if not 0 <= owner_value < len(players):
        raise RuntimeError("Agent-turn effect frame owner is outside player state")
    owner = players[owner_value]
    spice_at_placement = context.get("spice_at_placement", owner.resources.spice)
    spice_spent = context.get("spice_spent_after_placement", 0)
    if (
        isinstance(spice_at_placement, bool)
        or not isinstance(spice_at_placement, int)
        or isinstance(spice_spent, bool)
        or not isinstance(spice_spent, int)
        or spice_at_placement < 0
        or spice_spent < 0
    ):
        raise RuntimeError("Agent-turn effect frame has invalid Spice tracking")
    spice_gained = owner.resources.spice - spice_at_placement + spice_spent

    eligible: list[str] = []
    for instance_id in pending_agent_contract_ids(context):
        if instance_id not in owner.active_contract_ids:
            continue
        condition = contract_for_instance(instance_id).condition
        if condition.kind is ContractConditionKind.BOARD_SPACE or (
            condition.kind is ContractConditionKind.HARVEST_SPICE
            and spice_gained >= condition.amount
        ):
            eligible.append(instance_id)
    return tuple(eligible)


def _next_unrevealed_player(state: GameState, owner: int) -> int:
    for offset in range(1, state.config.players + 1):
        candidate = (owner + offset) % state.config.players
        if not state.players[candidate].has_revealed:
            return candidate
    raise RuntimeError("no unrevealed player remains during Player Turns")
