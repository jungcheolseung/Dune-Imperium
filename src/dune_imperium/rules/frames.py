"""Decision-frame kinds and shared frame/context helpers for rule modules."""

from dataclasses import replace
from enum import StrEnum

from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState

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
    CONTRACT_REWARD_RECALL = "contract_reward_recall"
    CONTRACT_INTRIGUE_TRASH = "contract_intrigue_trash"
    CONTROL_DEFENSE = "control_defense"
    COMBAT_INTRIGUE = "combat_intrigue"
    COMBAT_REWARD_INFLUENCE = "combat_reward_influence"
    COMBAT_REWARD_DISTINCT_INFLUENCE = "combat_reward_distinct_influence"
    COMBAT_REWARD_OPTIONAL = "combat_reward_optional"
    COMBAT_REWARD_SPY_RECALL = "combat_reward_spy_recall"
    COMBAT_REWARD_TRASH = "combat_reward_trash"
    CONFLICT_END_TRIGGER = "conflict_end_trigger"
    COMBAT_REWARD_SPY = "combat_reward_spy"
    ENDGAME_INTRIGUE = "endgame_intrigue"
    ROUND_START_RESHUFFLE = "round_start_reshuffle"
    PERSONAL_DRAW_RESHUFFLE = "personal_draw_reshuffle"
    INTRIGUE_RESHUFFLE = "intrigue_reshuffle"
    INTRIGUE_CHOICE = "intrigue_choice"
    INTRIGUE_EFFECTS = "intrigue_effects"
    INTRIGUE_TRIGGER_SPY = "intrigue_trigger_spy"
    LEADER_DRAFT = "leader_draft"
    SECRETS_STEAL = "secrets_steal"
    # Sardaukar Standard's Skill choice for the Commander it acquires.
    SKILL_CHOICE = "skill_choice"
    # Bloodlines opponent decisions: a Spy forced off a post (Holy War,
    # False Orders) and a unit lost from a chosen zone (Holy War).
    OPPONENT_SPY_MOVE = "opponent_spy_move"
    OPPONENT_UNIT_LOSS = "opponent_unit_loss"
    # False Orders: the owner's Spy placement on the turn's board space.
    SPY_PLACEMENT = "spy_placement"
    # Coercive Negotiation: three Contracts revealed from the bank.
    INTRIGUE_TRIGGER_CONTRACT = "intrigue_trigger_contract"
    # An optional "[trash] icon" reward (Liet Kynes' sandworm replacement).
    OPTIONAL_TRASH = "optional_trash"
    # Steersman Y'rkoon: choosing the four Navigation slots at setup, and
    # choosing how to play the next Navigation card.
    NAVIGATION_SETUP = "navigation_setup"
    NAVIGATION_CHOICE = "navigation_choice"
    # Tech Module: a card-granted Acquire Tech (with its discount) and Kota
    # Odax's Secret Project pick.
    TECH_ACQUISITION = "tech_acquisition"
    TECH_SECRET_PROJECT = "tech_secret_project"
    # Immortality: the research token's direction choice and the optional
    # or chosen bonuses of a research space [Immortality p. 6].
    RESEARCH_ADVANCE = "research_advance"
    RESEARCH_BONUS = "research_bonus"
    # Immortality Graft: choosing the second card of a two-card play.
    GRAFT_PARTNER = "graft_partner"
    # Imperium Ceremony: keep one of the Intrigue deck's top two cards.
    INTRIGUE_PEEK = "intrigue_peek"
    # Long Live the Fighters: the atomic draw-then-discard pick over the top
    # three personal cards. It owns a frame rather than a flag on the Agent
    # effect frame so the exclusivity is structural: while the pick is open no
    # other Agent-turn effect is offered, because the effect frame is not on
    # top of the stack.
    LONG_LIVE_FIGHTERS = "long_live_fighters"


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


def reset_turn_counters(
    players: tuple[PlayerState, ...],
    player: int,
) -> tuple[PlayerState, ...]:
    """Restart one player's per-turn bookkeeping as their turn opens.

    Deployment counters return to zero and the Spice-gained tracking takes a
    fresh snapshot of the player's current Spice.
    """

    owner = players[player]
    return replace_player(
        players,
        replace(
            owner,
            units_deployed_turn=0,
            deploy_trigger_offered_at=0,
            units_deployed_committed=0,
            spice_at_turn_start=owner.resources.spice,
            spice_spent_turn=0,
            commander_recruited_turn=False,
            contracts_completed_turn=0,
            # A held Contract icon never outlives the turn it was gained on
            # (OQ-059); the turn's close fizzles it with an event and this is
            # the belt-and-braces reset.
            held_contract_icons=0,
            commander_discount_turn=0,
            ignores_influence_requirements_turn=False,
            granted_agent_icon_turn="",
            combat_icon_turn=False,
            hungry_for_spice_granted_turn=False,
            spies_recalled_turn=0,
            suspensor_owed=0,
        ),
    )


def turn_owner_of(state: GameState) -> int | None:
    """Return whose Agent or Reveal turn is in progress, if any.

    The turn's own frame (turn, Agent effects or Reveal) sits lowest on the
    stack during Player Turns; frames above it belong to that turn's
    effects, whoever decides them.
    """

    if state.phase is not GamePhase.PLAYER_TURNS:
        return None
    for frame in state.decision_stack:
        if frame.kind in (
            FrameKind.TURN,
            FrameKind.AGENT_EFFECTS,
            FrameKind.REVEAL,
        ) and isinstance(frame.decision, PlayerDecision):
            return frame.decision.owner
    return None


def reveal_is_open_for(state: GameState, player: int) -> bool:
    """Return whether ``player``'s Reveal frame is on the decision stack."""

    return any(
        frame.kind == FrameKind.REVEAL
        and isinstance(frame.decision, PlayerDecision)
        and frame.decision.owner == player
        for frame in state.decision_stack
    )


def update_turn_recruits(
    state: GameState,
    *,
    troops_recruited: int = 0,
    spice_spent: int = 0,
) -> GameState:
    """Keep the turn owner's bookkeeping in step with a mid-turn effect.

    Troops recruited during the owner's turn join that turn's deployment
    allowance whether the effect resolved before or after placing the Agent
    (a Reveal turn's recruits feed its Combat-icon deployment
    [Bloodlines p. 5]). Spice paid for an effect is recorded as spent so
    that Harvest Spice Contracts, which count Spice gained from every source
    during the turn [Main p. 16], still see the full amount gained.
    """

    for index in range(len(state.decision_stack) - 1, -1, -1):
        frame = state.decision_stack[index]
        if frame.kind == FrameKind.REVEAL:
            context = frame_context(frame)
            recruited = context.get("reveal_troops_recruited", 0)
            if isinstance(recruited, bool) or not isinstance(recruited, int):
                raise RuntimeError("Reveal frame has an invalid recruit count")
            context["reveal_troops_recruited"] = recruited + troops_recruited
            return replace(
                state,
                decision_stack=(
                    *state.decision_stack[:index],
                    with_context(frame, context),
                    *state.decision_stack[index + 1 :],
                ),
            )
        if frame.kind not in (FrameKind.AGENT_EFFECTS, FrameKind.TURN):
            continue
        context = frame_context(frame)
        previous = context.get("troops_recruited", 0)
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("turn frame has an invalid recruit count")
        context["troops_recruited"] = previous + troops_recruited
        if frame.kind == FrameKind.AGENT_EFFECTS:
            spent = context_int(context, "spice_spent_after_placement")
            context["spice_spent_after_placement"] = spent + spice_spent
        updated = with_context(frame, context)
        return replace(
            state,
            decision_stack=(
                *state.decision_stack[:index],
                updated,
                *state.decision_stack[index + 1 :],
            ),
        )
    return state
