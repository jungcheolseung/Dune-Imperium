"""Playing Intrigue cards from a player's hidden hand.

Plot Intrigue may be played at any point during the owner's own Agent turn or
Reveal turn [Main pp. 7-8]. This project treats the moment the turn frame is
offered to its owner as already inside that turn, so Plot cards may also be
played before the Agent or Reveal choice is committed. Every applicable cost
printed on the card is mandatory once the card is played [FAQ p. 2].

Cards whose text needs player choices (which Faction to lose or gain, which
card to discard) open an ``INTRIGUE_CHOICE`` frame and resolve one choice slot
per action; the card is discarded when the last slot completes.
"""

from dataclasses import replace

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    DiscardFromHand,
    DrawPersonalCards,
    EffectSection,
    GainInfluence,
    IntrigueOption,
    IntrigueTiming,
    LoseInfluence,
)
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_INSTANCE,
    intrigue_card_for_instance,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.effect_interpreter import (
    ChoiceSlot,
    applicable_sections,
    apply_rewards,
    automatic_rewards,
    choice_slots,
    option_is_playable,
    pay_cost,
    resource_cost,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    frame_context,
    owned_top_frame,
    replace_player,
    replace_top_frame,
    top_frame,
    with_context,
)
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    lose_faction_influence,
)

# Frames during which the owner is inside their own Agent or Reveal turn.
PLOT_FRAME_KINDS = frozenset(
    {FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL}
)

_CHOICE_FRAME = "Intrigue choice frame"


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
        entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
        if entry is None or not entry.play_data_complete:
            continue
        for index, option in enumerate(entry.options):
            if option.timing is not IntrigueTiming.PLOT:
                continue
            if frame.kind == FrameKind.REVEAL and _draws_personal_cards(owner, option):
                # Cards drawn during a Reveal turn must be revealed at once
                # [FAQ p. 3]; that boundary is not implemented, so such
                # options are withheld until the Reveal is over.
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
    """Reveal and pay for one Intrigue option, then resolve or open choices."""

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
    section_indexes = tuple(
        index for index, section in enumerate(option.sections) if section in sections
    )
    cost = resource_cost(sections)

    paid_owner = pay_cost(owner, cost)
    source = f"round:{state.round_number}:player:{player}:intrigue:{card_id}"
    # Reveal and pay first. The card stays in the owner's Intrigue hand while
    # it resolves and reaches the discard pile only at the end, so a draw it
    # causes cannot reshuffle the card itself and no card leaves every zone.
    played_state = replace(state, players=replace_player(state.players, paid_owner))
    if cost is not None and cost.spice:
        played_state = _update_agent_turn_frame(
            played_state, spice_spent=cost.spice
        )
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

    if choice_slots(sections):
        frame = DecisionFrame(
            kind=FrameKind.INTRIGUE_CHOICE,
            frame_id=f"{source}:choice",
            decision=PlayerDecision(owner=player, prompt="Resolve the Intrigue choice"),
            context=(
                ("card_id", card_id),
                ("chosen_factions", ""),
                ("option", option_index),
                ("sections", ",".join(str(index) for index in section_indexes)),
                ("slot", 0),
                ("source", source),
            ),
        )
        return RuleResult(
            state=played_state.push_decision(frame), events=tuple(events)
        )

    finished = _finish_play(played_state, player, card_id, sections, source)
    return RuleResult(state=finished.state, events=(*events, *finished.events))


def legal_intrigue_choice_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the choices for the current Intrigue choice slot."""

    frame = owned_top_frame(state, FrameKind.INTRIGUE_CHOICE, player)
    if frame is None:
        return ()
    context = frame_context(frame)
    slot = _current_slot(context)
    owner = state.players[player]
    actions: list[DomainAction] = []
    match slot:
        case LoseInfluence():
            for faction in Faction:
                if influence_amount(owner.influence, faction) == 0:
                    continue
                recipients = alliance_recipients_after_influence_loss(
                    state, player, faction
                )
                recipient_options: tuple[int | None, ...] = (
                    tuple(recipients) if len(recipients) > 1 else (None,)
                )
                for recipient in recipient_options:
                    arguments: tuple[tuple[str, ActionValue], ...] = (
                        ("faction", faction.value),
                    )
                    if recipient is not None:
                        arguments = (("alliance_recipient", recipient), *arguments)
                    actions.append(
                        DomainAction(
                            action_id="choose_intrigue_faction",
                            actor=player,
                            arguments=arguments,
                        )
                    )
        case GainInfluence(factions=allowed, distinct=distinct):
            chosen = _chosen_factions(context)
            for faction in allowed if allowed is not None else tuple(Faction):
                if distinct and faction in chosen:
                    continue
                actions.append(
                    DomainAction(
                        action_id="choose_intrigue_faction",
                        actor=player,
                        arguments=(("faction", faction.value),),
                    )
                )
        case DiscardFromHand():
            actions.extend(
                DomainAction(
                    action_id="choose_intrigue_discard",
                    actor=player,
                    arguments=(("card_id", hand_card),),
                )
                for hand_card in owner.hand
            )
    return tuple(actions)


def apply_intrigue_choice(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one choice slot and finish the card after the last slot."""

    if action not in legal_intrigue_choice_actions(state, action.actor):
        raise ValueError("action is not a legal Intrigue choice")
    frame = state.decision_stack[-1]
    context = frame_context(frame)
    player = action.actor
    card_id = context_str(context, "card_id", owner=_CHOICE_FRAME)
    source = context_str(context, "source", owner=_CHOICE_FRAME)
    slot_index = context_int(context, "slot", owner=_CHOICE_FRAME)
    slot = _current_slot(context)
    arguments = dict(action.arguments)
    step_source = f"{source}:slot:{slot_index}"

    match slot:
        case LoseInfluence():
            faction = Faction(str(arguments["faction"]))
            recipient = arguments.get("alliance_recipient")
            assert recipient is None or isinstance(recipient, int)
            result = lose_faction_influence(
                state,
                player,
                faction,
                1,
                event_prefix=f"{step_source}:lost:{faction.value}",
                alliance_recipient=recipient,
            )
        case GainInfluence():
            faction = Faction(str(arguments["faction"]))
            result = gain_faction_influence(
                state,
                player,
                faction,
                1,
                event_prefix=f"{step_source}:gained:{faction.value}",
            )
            context["chosen_factions"] = ",".join(
                (*(f.value for f in _chosen_factions(context)), faction.value)
            )
        case DiscardFromHand():
            result = discard_personal_card_from_hand(
                state, player, str(arguments["card_id"]), source=step_source
            )
        case _:
            raise RuntimeError("Intrigue choice frame has an unsupported slot")

    context["slot"] = slot_index + 1
    next_state = replace_top_frame(result.state, with_context(frame, context))
    if slot_index + 1 < len(_slots(context)):
        return RuleResult(state=next_state, events=result.events)

    finished = _finish_play(
        next_state.pop_decision(), player, card_id, _sections(context), source
    )
    return RuleResult(
        state=finished.state,
        events=(*result.events, *finished.events),
    )


def _finish_play(
    state: GameState,
    player: int,
    card_id: str,
    sections: tuple[EffectSection, ...],
    source: str,
) -> RuleResult:
    """Apply automatic rewards, discard the card, and update turn bookkeeping."""

    rewards = automatic_rewards(sections)
    outcome = apply_rewards(state, player, rewards, source=source)
    resolved = outcome.result.state
    owner = resolved.players[player]
    next_state = replace(
        resolved,
        players=replace_player(
            resolved.players,
            replace(
                owner,
                intrigue_cards=tuple(
                    held for held in owner.intrigue_cards if held != card_id
                ),
            ),
        ),
        intrigue_discard=(*resolved.intrigue_discard, card_id),
    )
    if outcome.troops_recruited or outcome.spice_gained:
        next_state = _update_agent_turn_frame(
            next_state,
            troops_recruited=outcome.troops_recruited,
            spice_gained=outcome.spice_gained,
        )
    return RuleResult(state=next_state, events=outcome.result.events)


def _draws_personal_cards(owner: PlayerState, option: IntrigueOption) -> bool:
    return any(
        isinstance(reward, DrawPersonalCards)
        for section in applicable_sections(owner, option)
        for reward in section.rewards
    )


def _sections(context: dict[str, ActionValue]) -> tuple[EffectSection, ...]:
    card_id = context_str(context, "card_id", owner=_CHOICE_FRAME)
    option_index = context_int(context, "option", owner=_CHOICE_FRAME)
    option = intrigue_card_for_instance(card_id).options[option_index]
    raw = context_str(context, "sections", owner=_CHOICE_FRAME)
    return tuple(option.sections[int(index)] for index in raw.split(",") if index)


def _slots(context: dict[str, ActionValue]) -> tuple[ChoiceSlot, ...]:
    return choice_slots(_sections(context))


def _current_slot(context: dict[str, ActionValue]) -> ChoiceSlot:
    slots = _slots(context)
    index = context_int(context, "slot", owner=_CHOICE_FRAME)
    if not 0 <= index < len(slots):
        raise RuntimeError("Intrigue choice frame slot is out of range")
    return slots[index]


def _chosen_factions(context: dict[str, ActionValue]) -> tuple[Faction, ...]:
    raw = context_str(context, "chosen_factions", owner=_CHOICE_FRAME)
    return tuple(Faction(value) for value in raw.split(",") if value)


def _update_agent_turn_frame(
    state: GameState,
    *,
    troops_recruited: int = 0,
    spice_spent: int = 0,
    spice_gained: int = 0,
) -> GameState:
    """Keep the owner's turn bookkeeping in step with an Intrigue effect.

    Troops recruited during the owner's turn join that turn's deployment
    allowance whether the Plot was played before or after placing the Agent.
    Spice paid or gained by the card is excluded from the Harvest Spice
    Contract accounting, which only tracks Spice harvested at the space.
    """

    for index in range(len(state.decision_stack) - 1, -1, -1):
        frame = state.decision_stack[index]
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
            baseline = context_int(context, "spice_at_placement")
            context["spice_at_placement"] = baseline + spice_gained
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
