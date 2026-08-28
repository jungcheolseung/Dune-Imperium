"""Playing Intrigue cards from a player's hidden hand.

Plot Intrigue may be played at any point during the owner's own Agent turn or
Reveal turn [Main pp. 7-8]. This project treats the moment the turn frame is
offered to its owner as already inside that turn, so Plot cards may also be
played before the Agent or Reveal choice is committed. Every applicable cost
printed on the card is mandatory once the card is played [FAQ p. 2].
"""

from dataclasses import replace

from dune_imperium.content.uprising.effect_dsl import IntrigueTiming
from dune_imperium.content.uprising.intrigue import intrigue_card_for_instance
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.effect_interpreter import (
    applicable_sections,
    apply_rewards,
    option_is_playable,
    pay_cost,
    total_cost,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    frame_context,
    replace_player,
    replace_top_frame,
    top_frame,
    with_context,
)

# Frames during which the owner is inside their own Agent or Reveal turn.
PLOT_FRAME_KINDS = frozenset(
    {FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL}
)


def legal_intrigue_play_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return every Plot option ``player`` can currently play."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if state.phase is not GamePhase.PLAYER_TURNS:
        return ()
    frame = top_frame(state)
    if (
        frame is None
        or frame.kind not in PLOT_FRAME_KINDS
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return ()
    owner = state.players[player]
    actions: list[DomainAction] = []
    for card_id in owner.intrigue_cards:
        entry = intrigue_card_for_instance(card_id)
        if not entry.play_data_complete:
            continue
        for index, option in enumerate(entry.options):
            if option.timing is not IntrigueTiming.PLOT:
                continue
            if option_is_playable(owner, option):
                actions.append(
                    DomainAction(
                        action_id="play_intrigue",
                        actor=player,
                        arguments=(("card_id", card_id), ("option", index)),
                    )
                )
    return tuple(actions)


def apply_intrigue_play(state: GameState, action: DomainAction) -> RuleResult:
    """Reveal, pay for, resolve, and discard one Intrigue option."""

    if action not in legal_intrigue_play_actions(state, action.actor):
        raise ValueError("action is not a legal Intrigue play")
    arguments = dict(action.arguments)
    card_id = arguments["card_id"]
    option_index = arguments["option"]
    if not isinstance(card_id, str) or isinstance(option_index, bool):
        raise RuntimeError("Intrigue play has invalid arguments")
    assert isinstance(option_index, int)
    player = action.actor
    owner = state.players[player]
    option = intrigue_card_for_instance(card_id).options[option_index]
    sections = applicable_sections(owner, option)
    cost = total_cost(sections)

    paid_owner = pay_cost(owner, cost)
    paid_owner = replace(
        paid_owner,
        intrigue_cards=tuple(
            held for held in paid_owner.intrigue_cards if held != card_id
        ),
    )
    source = f"round:{state.round_number}:player:{player}:intrigue:{card_id}"
    # Reveal and pay first; the card reaches the discard pile only after its
    # effects resolve, so a draw it causes cannot reshuffle the card itself.
    played_state = replace(state, players=replace_player(state.players, paid_owner))
    events: list[GameEvent] = [
        GameEvent(
            event_id=source,
            kind="intrigue_played",
            payload=(
                ("card_id", card_id),
                ("option", option_index),
                ("player", player),
            ),
        )
    ]
    if cost is not None:
        events.append(
            GameEvent(
                event_id=f"{source}:cost",
                kind="intrigue_cost_paid",
                payload=(
                    ("player", player),
                    ("solari", cost.solari),
                    ("spice", cost.spice),
                    ("water", cost.water),
                ),
            )
        )

    rewards = tuple(reward for section in sections for reward in section.rewards)
    outcome = apply_rewards(played_state, player, rewards, source=source)
    next_state = replace(
        outcome.result.state,
        intrigue_discard=(*outcome.result.state.intrigue_discard, card_id),
    )
    events.extend(outcome.result.events)
    if outcome.troops_recruited:
        next_state = _record_recruited_troops(next_state, outcome.troops_recruited)
    return RuleResult(state=next_state, events=tuple(events))


def _record_recruited_troops(state: GameState, recruited: int) -> GameState:
    """Let troops recruited during an Agent turn join that turn's deployment."""

    for index in range(len(state.decision_stack) - 1, -1, -1):
        frame = state.decision_stack[index]
        if frame.kind != FrameKind.AGENT_EFFECTS:
            continue
        context = frame_context(frame)
        previous = context_int(
            context, "troops_recruited", owner="Agent-turn effect frame"
        )
        context["troops_recruited"] = previous + recruited
        updated = with_context(frame, context)
        if index == len(state.decision_stack) - 1:
            return replace_top_frame(state, updated)
        return replace(
            state,
            decision_stack=(
                *state.decision_stack[:index],
                updated,
                *state.decision_stack[index + 1 :],
            ),
        )
    return state
