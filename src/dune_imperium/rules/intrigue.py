"""Playing Intrigue cards from a player's hidden hand.

Plot Intrigue may be played at any point during the owner's own Agent turn or
Reveal turn [Main pp. 7-8]. This project treats the moment the turn frame is
offered to its owner as already inside that turn, so Plot cards may also be
played before the Agent or Reveal choice is committed. Every applicable cost
printed on the card is mandatory once the card is played [FAQ p. 2].

Cards whose text needs player choices (which Faction to lose or gain, which
card to discard) open an ``INTRIGUE_CHOICE`` frame and resolve one choice slot
per action; the card is discarded when the last slot completes. The frame
stores the option's pending ability and the composed-effects executor
(``rules.ability_executor``, stage A1) offers and applies each slot; this
module keeps the card's play, its frames and its finish.
"""

from collections.abc import Mapping
from copy import replace
from enum import StrEnum
from typing import Final

from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardUpTo,
    EffectSection,
    IntrigueOption,
    IntrigueTiming,
    OnTroopsLostAtConflictEnd,
    PeekTopCard,
    RevealContractsTakeOne,
    UnitsDeployedThisTurnAtLeast,
)
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_INSTANCE,
    intrigue_card_for_instance,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.ability_executor import (
    STACKED,
    PendingAbility,
    ability_rows,
    acquire_by_piece,
    acquires_to_hand,
    apply_automatic_rewards,
    apply_piece,
    current_piece,
    decode_pending,
    encode_pending,
    entry_sections,
    intrigue_ref,
    rewards_wait,
)
from dune_imperium.rules.acquisition import open_acquisition_frames
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.combat import (
    COMBAT_INTRIGUE_PLAYED_KEY,
    refresh_combat_participants,
)
from dune_imperium.rules.effect_interpreter import (
    ChoiceSlot,
    OptionUnplayable,
    applicable_sections,
    choice_slots,
    condition_holds,
    option_unplayable_reason,
    pay_cost,
    play_changes_nothing,
    resource_cost,
    section_is_usable,
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
    turn_start_is_open,
    with_context,
)
from dune_imperium.rules.gain_events import resources_paid_event
from dune_imperium.rules.intrigue_triggers import (
    open_contract_reveal,
    waits_for_reveal_turn,
)

# Frames during which the owner is inside their own Agent or Reveal turn.
PLOT_FRAME_KINDS = frozenset(
    {FrameKind.TURN, FrameKind.AGENT_EFFECTS, FrameKind.REVEAL}
)

_CHOICE_FRAME = "Intrigue choice frame"
# The keys the choice frame stores its pending ability under, and the lines
# frame its lines not used yet, one pending entry each (codec v148;
# ``ability_executor.PendingAbility.encode``, ``encode_pending``).
PENDING_ABILITY_KEY: Final = "pending_ability"
PENDING_LINES_KEY: Final = "pending_lines"


class IntriguePlayBlock(StrEnum):
    """Why an Intrigue option is not for the window open now (its timing).

    ``intrigue_play_block`` returns one of these, or the option's own reason
    (``option_unplayable_reason``); the legal list plays exactly the options
    without a block, and the page greys out the others with that reason
    (``display.unavailable``, user request 2026-09-29).
    """

    TIMING = "timing"  # printed for another window (Plot, Combat, Endgame)
    TURN_START = "turn_start"  # "At the start of your turn", after that point
    # "When you lose at least three troops at the end of a Conflict:"
    # [Harvest Cells card]: played only in the Conflict-end window once the
    # rewards resolved, never in an Intrigue window (user ruling 2026-10-06,
    # OQ-057 (11): "This card is played after combat resolves.").
    CONFLICT_END = "conflict_end"
    # "At the start of your turn" (Withdrawn) on the turn frame after the
    # seat already acted in the turn (OQ-095 (6), user ruling 2026-10-04).
    TURN_STARTED = "turn_started"


def intrigue_window(state: GameState, player: int) -> IntrigueTiming | None:
    """Return the Intrigue window ``player`` has open now, or None.

    Plot during the owner's own turn frames, Combat at the owner's Combat
    Intrigue priority, Endgame in the owner's Endgame window.
    """

    frame = top_frame(state)
    if (
        frame is None
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return None
    if state.phase is GamePhase.PLAYER_TURNS and frame.kind in PLOT_FRAME_KINDS:
        return IntrigueTiming.PLOT
    if state.phase is GamePhase.COMBAT and frame.kind == FrameKind.COMBAT_INTRIGUE:
        # Only the participant whose priority it is may play [Main p. 14].
        return IntrigueTiming.COMBAT
    if state.phase is GamePhase.ENDGAME and frame.kind == FrameKind.ENDGAME_INTRIGUE:
        # Endgame Intrigue resolves in the owner's Endgame window
        # [Main pp. 7, 15].
        return IntrigueTiming.ENDGAME
    return None


def intrigue_play_block(
    state: GameState,
    player: int,
    frame_kind: str,
    timing: IntrigueTiming,
    option: IntrigueOption,
) -> IntriguePlayBlock | OptionUnplayable | None:
    """Why ``player`` cannot play ``option`` in the ``timing`` window now."""

    if isinstance(option.trigger, OnTroopsLostAtConflictEnd):
        # Harvest Cells: "To play an Intrigue card, you must meet its
        # conditions and pay its costs." [FAQ p. 2], and its condition is
        # the loss at the Conflict's end, so it waits for the window after
        # the rewards (``combat.offer_conflict_end_triggers``) instead of
        # going face up in Combat Intrigue (user ruling 2026-10-06).
        return IntriguePlayBlock.CONFLICT_END
    if option.timing is not timing:
        return IntriguePlayBlock.TIMING
    if option.turn_start_only and frame_kind != FrameKind.TURN:
        # "At the start of your turn" (Withdrawn): only before the Agent or
        # Reveal choice.
        return IntriguePlayBlock.TURN_START
    if option.turn_start_only and not turn_start_is_open(state, player):
        # "At the start of your turn: Pass your turn." [Withdrawn card]: only
        # as the turn's first action -- once the seat did anything else in
        # the turn (a Plot, a specimen return, its Emperor track Spy), the
        # start is over (OQ-095 (6), user ruling 2026-10-04). That also
        # covers an owed Emperor track Spy, which only an action of the
        # seat's own turn can leave waiting in it.
        return IntriguePlayBlock.TURN_STARTED
    return option_unplayable_reason(state, player, option)


def plays_turn_start_option(action: DomainAction) -> bool:
    """Whether ``action`` plays an "At the start of your turn" Intrigue option.

    Such a play is the turn's first action itself, so it does not end the
    start of the turn the way any other action does (``end_turn_start``).
    """

    if action.action_id != "play_intrigue":
        return False
    arguments = dict(action.arguments)
    card_id = arguments.get("card_id")
    option_index = arguments.get("option")
    if not isinstance(card_id, str) or not isinstance(option_index, int):
        return False
    entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
    return (
        entry is not None
        and 0 <= option_index < len(entry.options)
        and entry.options[option_index].turn_start_only
    )


def legal_intrigue_play_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return every Plot or Combat option ``player`` can currently play."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    timing = intrigue_window(state, player)
    if timing is None:
        return ()
    frame_kind = state.decision_stack[-1].kind
    owner = state.players[player]
    actions: list[DomainAction] = []
    for card_id in owner.intrigue_cards:
        entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
        if entry is None or not entry.play_data_complete:
            continue
        for index, option in enumerate(entry.options):
            if intrigue_play_block(state, player, frame_kind, timing, option) is None:
                actions.append(
                    DomainAction(
                        action_id="play_intrigue",
                        actor=player,
                        arguments=(("card_id", card_id), ("option", index)),
                    )
                )
    return tuple(actions)


def without_effect_event(source: str, card_id: str, player: int) -> GameEvent:
    """The public note that a play changes nothing: every line is one without
    a cost and fizzles (OQ-113 (C) and (5), user ruling 2026-10-24: played
    all the same, warned beforehand and logged; ``play_changes_nothing``)."""

    return GameEvent(
        event_id=f"{source}:without_effect",
        kind="intrigue_without_effect",
        payload=(("card_id", card_id), ("player", player)),
    )


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
    source = f"round:{state.round_number}:player:{player}:intrigue:{card_id}"
    if option.separate:
        return _play_separate_lines(
            state, player, card_id, option_index, option, source
        )
    sections = applicable_sections(state, player, option)
    cost = resource_cost(sections)

    paid_owner = pay_cost(owner, cost)
    deployed_condition = max(
        (
            section.condition.count
            for section in sections
            if isinstance(section.condition, UnitsDeployedThisTurnAtLeast)
        ),
        default=0,
    )
    if deployed_condition:
        # Distraction / Coercive Negotiation used this turn's deployment as
        # their condition: a withdrawal may no longer drop below it (OQ-029).
        paid_owner = replace(
            paid_owner,
            units_deployed_committed=max(
                paid_owner.units_deployed_committed, deployed_condition
            ),
        )
    # Reveal and pay first. The card stays in the owner's Intrigue hand while
    # it resolves and reaches the discard pile only at the end, so a draw it
    # causes cannot reshuffle the card itself and no card leaves every zone.
    played_state = replace(state, players=replace_player(state.players, paid_owner))
    if (
        option.timing is IntrigueTiming.COMBAT
        and state.phase is GamePhase.COMBAT
        and player not in played_state.combat_intrigue_players
    ):
        # Counterattack (Immortality): "If an opponent played a Combat
        # Intrigue card in this Conflict".
        played_state = replace(
            played_state,
            combat_intrigue_players=(*played_state.combat_intrigue_players, player),
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
    if cost is not None and (cost.solari or cost.spice or cost.water):
        events.append(
            resources_paid_event(
                source, player, solari=cost.solari, spice=cost.spice, water=cost.water
            )
        )
    if option.trigger is None and play_changes_nothing(state, player, sections):
        events.append(without_effect_event(source, card_id, player))

    if option.trigger is not None:
        # The effect does not apply yet: the card waits face up in front of
        # its owner until the trigger fires [FAQ p. 2] (Call to Arms; Harvest
        # Cells is never played here, ``IntriguePlayBlock.CONFLICT_END``).
        waiting_owner = played_state.players[player]
        moved = replace(
            waiting_owner,
            intrigue_cards=tuple(
                held for held in waiting_owner.intrigue_cards if held != card_id
            ),
            intrigue_faceup=(*waiting_owner.intrigue_faceup, card_id),
        )
        events.append(
            GameEvent(
                event_id=f"{source}:faceup",
                kind="intrigue_kept_faceup",
                payload=(("card_id", card_id), ("player", player)),
            )
        )
        return RuleResult(
            state=replace(
                played_state, players=replace_player(played_state.players, moved)
            ),
            events=tuple(events),
        )

    return _resolve_paid_option(
        played_state, player, card_id, option_index, option, sections, source, events
    )


def resolve_conflict_end_trigger(
    state: GameState,
    player: int,
    card_id: str,
    *,
    source: str,
) -> RuleResult:
    """Resolve a Conflict-end trigger card from the hand as it is played
    (Harvest Cells, in its window once the troops are back in the supply).

    User decision 2026-10-18 ("세포 수확은 내는 즉시 표본 2를 주고 획득
    여부만 묻게 해줘"): its automatic rewards apply at once and only its
    choice is asked -- "You may also acquire a Tleilaxu card (paying its
    normal cost)." [Harvest Cells card]; the card then finishes as usual.
    """

    entry = intrigue_card_for_instance(card_id)
    option_index = next(
        index for index, option in enumerate(entry.options) if option.trigger
    )
    option = entry.options[option_index]
    sections = applicable_sections(state, player, option)
    return _resolve_paid_option(
        state, player, card_id, option_index, option, sections, source, [],
        rewards_first=True,
    )


def _resolve_paid_option(
    played_state: GameState,
    player: int,
    card_id: str,
    option_index: int,
    option: IntrigueOption,
    sections: tuple[EffectSection, ...],
    source: str,
    events: list[GameEvent],
    *,
    separate: bool = False,
    rewards_first: bool = False,
) -> RuleResult:
    """Open the option's choice frame, or finish it when nothing is chosen.

    With ``rewards_first`` the automatic rewards apply now, as the frame
    opens, and only its choices are left (``resolve_conflict_end_trigger``).

    The frame stores the option's pending ability (``ability_executor``):
    the lines that apply, judged now, and whether the Shield Wall stands,
    which decides whether a detonation icon is a choice. With ``separate``
    the sections are lines of a card whose ``intrigue_effects`` frame stays
    open beneath: finishing them applies their rewards but leaves the card
    in play (OQ-058).
    """

    state = played_state
    paid_owner = played_state.players[player]
    if choice_slots(sections, shield_wall_present=state.shield_wall_present):
        entry = PendingAbility(
            Source.INTRIGUE,
            intrigue_ref(card_id, option_index),
            tuple(
                index
                for index, section in enumerate(option.sections)
                if section in sections
            ),
            shield_wall=state.shield_wall_present,
            rewards_applied=rewards_first,
        )
        frame = DecisionFrame(
            kind=FrameKind.INTRIGUE_CHOICE,
            frame_id=f"{source}:choice",
            decision=PlayerDecision(owner=player, prompt="Resolve the Intrigue choice"),
            context=(
                ("card_id", card_id),
                # Controlled: the deck's top card, seen by the owner only
                # (the observation's private view surfaces it).
                (
                    "peeked_card_id",
                    paid_owner.deck[0]
                    if paid_owner.deck
                    and any(
                        isinstance(reward, PeekTopCard)
                        for section in sections
                        for reward in section.rewards
                    )
                    else "",
                ),
                (PENDING_ABILITY_KEY, entry.encode()),
                ("separate_effect", separate),
                ("source", source),
            ),
        )
        opened = played_state.push_decision(frame)
        if not rewards_first:
            return RuleResult(state=opened, events=tuple(events))
        # The frame is in place before the rewards apply, so a draw that
        # pushes a reshuffle stacks above it (as ``apply_intrigue_rewards``).
        rewarded = apply_automatic_rewards(
            opened, player, sections, f"{source}:rewards", played_card_id=card_id
        )
        return RuleResult(state=rewarded.state, events=(*events, *rewarded.events))

    finished = finish_intrigue_play(
        played_state, player, card_id, sections, source, discard=not separate
    )
    return RuleResult(state=finished.state, events=(*events, *finished.events))


# --- Separate printed lines (OQ-058) --------------------------------------------------

_EFFECTS_FRAME = "Intrigue effects frame"


def _effects_option(
    context: dict[str, ActionValue],
) -> tuple[str, int, IntrigueOption, tuple[PendingAbility, ...]]:
    """The card, its option and the pending entries of its unused lines."""

    card_id = context_str(context, "card_id", owner=_EFFECTS_FRAME)
    option_index = context_int(context, "option", owner=_EFFECTS_FRAME)
    option = intrigue_card_for_instance(card_id).options[option_index]
    lines = decode_pending(
        context_str(context, PENDING_LINES_KEY, owner=_EFFECTS_FRAME)
    )
    return card_id, option_index, option, lines


def _open_lines(lines: tuple[PendingAbility, ...]) -> tuple[int, ...]:
    """The printed lines the pending entries still hold, in printed order."""

    return tuple(index for entry in lines for index in entry.sections)


def _play_separate_lines(
    state: GameState,
    player: int,
    card_id: str,
    option_index: int,
    option: IntrigueOption,
    source: str,
) -> RuleResult:
    """Open the card's lines: cost-free lines resolve now, arrow lines wait."""

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
    usable = tuple(
        section
        for section in option.sections
        if section_is_usable(state, player, section)
    )
    if play_changes_nothing(state, player, usable):
        events.append(without_effect_event(source, card_id, player))
    working = state
    if (
        option.timing is IntrigueTiming.COMBAT
        and state.phase is GamePhase.COMBAT
        and player not in working.combat_intrigue_players
    ):
        working = replace(
            working,
            combat_intrigue_players=(*working.combat_intrigue_players, player),
        )
    # A cost-free line resolves at once and counts as used even when it
    # fizzles (``section_is_usable``; OQ-113 (C), user ruling 2026-10-24:
    # Depart for Arrakis' draw with an empty deck and discard pile, OQ-058).
    automatic = tuple(
        index
        for index, section in enumerate(option.sections)
        if not section.costs and section_is_usable(working, player, section)
    )
    # Each line not used yet waits as a pending entry of its own; the
    # cost-free ones resolved now count as used, and finishing waits for one
    # used line (``intrigue_effects_finish_is_open``).
    lines = tuple(
        PendingAbility(Source.INTRIGUE, intrigue_ref(card_id, option_index), (index,))
        for index in range(len(option.sections))
        if index not in automatic
    )
    frame = DecisionFrame(
        kind=FrameKind.INTRIGUE_EFFECTS,
        frame_id=f"{source}:effects",
        decision=PlayerDecision(
            owner=player, prompt="Use one of the card's lines, or finish the card"
        ),
        context=(
            ("card_id", card_id),
            ("option", option_index),
            (PENDING_LINES_KEY, encode_pending(lines)),
            ("player", player),
            ("source", source),
        ),
    )
    working = working.push_decision(frame)
    if automatic:
        return _resolve_paid_option(
            working,
            player,
            card_id,
            option_index,
            option,
            tuple(option.sections[index] for index in automatic),
            f"{source}:auto",
            events,
            separate=True,
        )
    settled = _settle_effects_frame(working, player, card_id)
    return RuleResult(state=settled.state, events=(*events, *settled.events))


def _remaining_lines(
    state: GameState, player: int, context: dict[str, ActionValue]
) -> tuple[int, ...]:
    """Unused arrow lines whose printed condition holds (cost aside)."""

    _, _, option, lines = _effects_option(context)
    return tuple(
        index
        for index in _open_lines(lines)
        if option.sections[index].costs
        and (
            (condition := option.sections[index].condition) is None
            or condition_holds(state, player, condition)
        )
    )


def _settle_effects_frame(state: GameState, player: int, card_id: str) -> RuleResult:
    """Close the effects frame and discard the card once no line can follow."""

    frame = owned_top_frame(state, FrameKind.INTRIGUE_EFFECTS, player)
    if frame is None:
        return RuleResult(state=state)
    context = frame_context(frame)
    if context_str(context, "card_id", owner=_EFFECTS_FRAME) != card_id:
        return RuleResult(state=state)
    if _remaining_lines(state, player, context):
        return RuleResult(state=state)
    source = context_str(context, "source", owner=_EFFECTS_FRAME)
    return finish_intrigue_play(state.pop_decision(), player, card_id, (), source)


def _usable_lines(
    state: GameState, player: int, context: dict[str, ActionValue]
) -> tuple[int, ...]:
    """Unused arrow lines the owner can use now (condition and cost)."""

    _, _, option, lines = _effects_option(context)
    return tuple(
        index
        for index in _open_lines(lines)
        if option.sections[index].costs
        and section_is_usable(state, player, option.sections[index])
    )


def intrigue_lines_used(context: Mapping[str, ActionValue]) -> tuple[int, ...]:
    """The lines a separate-lines card's frame has used so far (OQ-058).

    In printed order; () for a context that is not such a frame's.
    """

    card_id, option_index = context.get("card_id"), context.get("option")
    raw = context.get(PENDING_LINES_KEY)
    if (
        not isinstance(card_id, str)
        or not isinstance(option_index, int)
        or not isinstance(raw, str)
    ):
        return ()
    count = len(intrigue_card_for_instance(card_id).options[option_index].sections)
    open_lines = _open_lines(decode_pending(raw))
    return tuple(index for index in range(count) if index not in open_lines)


def intrigue_effects_finish_is_open(state: GameState, player: int) -> bool:
    """Whether the owner may finish its separate-lines card now (OQ-058).

    At least one line must be used first (OQ-058, user ruling 2026-10-04,
    "최소 한 줄은 써야 함", as the Steam app does): "To play an Intrigue
    card, you must meet its conditions and pay its costs" [FAQ pp. 2-3]. A
    cost-free line resolved as the card was played counts as used; after
    one line the others stay optional. Finishing is open anyway when no
    unused line can be used, so the frame never dead-ends; the play gate
    (one usable line, ``option_unplayable_reason``) keeps that unreachable
    before a line is used, since nothing acts between the play and the
    owner's first line choice.
    """

    frame = owned_top_frame(state, FrameKind.INTRIGUE_EFFECTS, player)
    if frame is None:
        return False
    context = frame_context(frame)
    return bool(intrigue_lines_used(context)) or not _usable_lines(
        state, player, context
    )


def legal_intrigue_effect_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Use one of the card's unused arrow lines now, or finish the card
    once a line was used (``intrigue_effects_finish_is_open``)."""

    frame = owned_top_frame(state, FrameKind.INTRIGUE_EFFECTS, player)
    if frame is None:
        return ()
    finish = (
        (DomainAction(action_id="finish_intrigue_effects", actor=player),)
        if intrigue_effects_finish_is_open(state, player)
        else ()
    )
    return (
        *finish,
        *(
            DomainAction(
                action_id="use_intrigue_effect",
                actor=player,
                arguments=(("section", index),),
            )
            for index in _usable_lines(state, player, frame_context(frame))
        ),
    )


def apply_intrigue_effect(state: GameState, action: DomainAction) -> RuleResult:
    """Pay for and resolve one printed line, or finish the card (OQ-058)."""

    if action not in legal_intrigue_effect_actions(state, action.actor):
        raise ValueError("action is not a legal Intrigue line choice")
    player = action.actor
    frame = state.decision_stack[-1]
    context = frame_context(frame)
    card_id, option_index, option, lines = _effects_option(context)
    source = context_str(context, "source", owner=_EFFECTS_FRAME)
    if action.action_id == "finish_intrigue_effects":
        finished = finish_intrigue_play(
            state.pop_decision(), player, card_id, (), source
        )
        return RuleResult(
            state=finished.state,
            events=(
                GameEvent(
                    event_id=f"{source}:finished",
                    kind="intrigue_effects_finished",
                    payload=(("card_id", card_id), ("player", player)),
                ),
                *finished.events,
            ),
        )
    index = context_int(dict(action.arguments), "section", owner=_EFFECTS_FRAME)
    section = option.sections[index]
    cost = resource_cost((section,))
    owner = state.players[player]
    paid_owner = pay_cost(owner, cost)
    # The line's entry leaves the list and resolves (``_resolve_paid_option``).
    context[PENDING_LINES_KEY] = encode_pending(
        tuple(entry for entry in lines if entry.sections != (index,))
    )
    working = replace_top_frame(
        replace(state, players=replace_player(state.players, paid_owner)),
        with_context(frame, context),
    )
    line_source = f"{source}:line:{index}"
    events: list[GameEvent] = [
        GameEvent(
            event_id=line_source,
            kind="intrigue_effect_used",
            payload=(("card_id", card_id), ("player", player), ("section", index)),
        )
    ]
    if cost is not None and (cost.solari or cost.spice or cost.water):
        events.append(
            resources_paid_event(
                line_source,
                player,
                solari=cost.solari,
                spice=cost.spice,
                water=cost.water,
            )
        )
    return _resolve_paid_option(
        working,
        player,
        card_id,
        option_index,
        option,
        (section,),
        line_source,
        events,
        separate=True,
    )


def pending_intrigue_ability(
    context: Mapping[str, ActionValue],
) -> PendingAbility | None:
    """The pending ability an Intrigue choice frame stores, or None.

    The entry is the option (or the one line) being resolved: its step is
    the choice slot, its pieces the slots (``ability_executor``). None for a
    context that holds no Intrigue entry.
    """

    raw = context.get(PENDING_ABILITY_KEY)
    if not isinstance(raw, str):
        return None
    try:
        entry = PendingAbility.decode(raw)
    except ValueError:
        return None
    return entry if entry.source is Source.INTRIGUE else None


def _choice_entry(context: dict[str, ActionValue]) -> PendingAbility:
    return PendingAbility.decode(
        context_str(context, PENDING_ABILITY_KEY, owner=_CHOICE_FRAME)
    )


def current_intrigue_choice_slot(state: GameState, player: int) -> ChoiceSlot | None:
    """Return the deciding player's current slot, including its gain/loss kind.

    Presentation uses the same slot as the legal provider: a shared Faction
    choice action can pay Influence or gain it on the next step of one card.
    """

    frame = owned_top_frame(state, FrameKind.INTRIGUE_CHOICE, player)
    if frame is None:
        return None
    entry = _choice_entry(frame_context(frame))
    if rewards_wait(entry):
        return None
    piece = current_piece(entry)
    if piece is None:
        raise RuntimeError("Intrigue choice frame slot is out of range")
    return piece


def legal_intrigue_choice_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the choices for the current Intrigue choice slot.

    The executor's rows for a frame stacked on the turn (``STACKED``): the
    slot's targets with an optional icon's refusal, then -- once every
    arrow cost is paid -- the row that resolves the automatic rewards,
    which is all a frame offers when the line's draw waits for its own
    step (``rewards_wait``, OQ-106).
    """

    frame = owned_top_frame(state, FrameKind.INTRIGUE_CHOICE, player)
    if frame is None:
        return ()
    context = frame_context(frame)
    return ability_rows(
        state,
        player,
        _choice_entry(context),
        STACKED,
        played_card_id=context_str(context, "card_id", owner=_CHOICE_FRAME),
    )


def apply_intrigue_rewards(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve the card's automatic rewards at the owner's chosen point.

    Icons on one Intrigue line are independent effects whose order the owner
    picks (OQ-015), so the non-choice rewards may land before, between, or
    after the remaining choice slots; the final slot then finishes the card
    without applying them again.
    """

    if action not in legal_intrigue_choice_actions(state, action.actor):
        raise ValueError("action is not a legal Intrigue rewards resolution")
    frame = owned_top_frame(state, FrameKind.INTRIGUE_CHOICE, action.actor)
    if frame is None:
        raise RuntimeError("Intrigue rewards resolution requires its choice frame")
    context = frame_context(frame)
    source = context_str(context, "source", owner=_CHOICE_FRAME)
    entry = _choice_entry(context)
    if rewards_wait(entry):
        # The last slot left the line's draw as its own step (OQ-106): the
        # rewards apply now and the card finishes, as the last slot used to.
        return finish_intrigue_play(
            state.pop_decision(),
            action.actor,
            context_str(context, "card_id", owner=_CHOICE_FRAME),
            entry_sections(entry),
            f"{source}:rewards",
            discard=context.get("separate_effect") is not True,
        )
    # The frame is marked before the rewards apply so a draw that pushes a
    # reshuffle chance frame stacks on the already-updated frame, exactly
    # like the acquisition slot's advance-before-move pattern.
    context[PENDING_ABILITY_KEY] = replace(entry, rewards_applied=True).encode()
    advanced = replace_top_frame(state, with_context(frame, context))
    return apply_automatic_rewards(
        advanced,
        action.actor,
        entry_sections(entry),
        f"{source}:rewards",
        played_card_id=context_str(context, "card_id", owner=_CHOICE_FRAME),
    )


def apply_intrigue_choice(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one choice slot and finish the card after the last slot.

    The executor applies the answer (``apply_piece``); this frame keeps the
    card's bookkeeping: frames a slot pushes are lifted above the updated
    choice frame, and the last slot finishes the card.
    """

    if action not in legal_intrigue_choice_actions(state, action.actor):
        raise ValueError("action is not a legal Intrigue choice")
    frame = state.decision_stack[-1]
    context = frame_context(frame)
    player = action.actor
    card_id = context_str(context, "card_id", owner=_CHOICE_FRAME)
    source = context_str(context, "source", owner=_CHOICE_FRAME)
    entry = _choice_entry(context)
    piece = current_piece(entry)
    if isinstance(piece, AcquireCardUpTo):
        return _apply_intrigue_acquisition(
            state, frame, context, entry, player, piece, action
        )
    applied = apply_piece(state, player, entry, action, source=source)
    result = applied.result
    if applied.stays:
        # The recall only prepared the placement; the frame stays as it was.
        return RuleResult(
            state=replace_top_frame(result.state, frame), events=result.events
        )
    entry = applied.entry
    context[PENDING_ABILITY_KEY] = entry.encode()
    lifted, pushed = _lift_pushed_frames(frame.frame_id, result.state)
    next_state = replace_top_frame(lifted, with_context(frame, context))
    if current_piece(entry) is not None or rewards_wait(entry):
        return RuleResult(state=_restack(next_state, pushed), events=result.events)

    finished = finish_intrigue_play(
        next_state.pop_decision(),
        player,
        card_id,
        entry_sections(entry),
        source,
        skip_rewards=entry.rewards_applied,
        discard=context.get("separate_effect") is not True,
    )
    return RuleResult(
        state=_restack(finished.state, pushed),
        events=(*result.events, *finished.events),
    )


def _lift_pushed_frames(
    frame_id: str, after: GameState
) -> tuple[GameState, tuple[DecisionFrame, ...]]:
    """Split off the frames a slot pushed above the choice frame ``frame_id``.

    An acquired card's Research box (Spiritual Fervor, Immortality) opens
    its direction choice at once; the slot bookkeeping must still address
    the choice frame, so the pushed frames are lifted and restacked on top
    afterwards. Frames a late reveal slid in below the choice frame stay
    where they are.
    """

    index = next(
        (
            position
            for position, frame in enumerate(after.decision_stack)
            if frame.frame_id == frame_id
        ),
        None,
    )
    if index is None:
        raise RuntimeError("Intrigue choice frame vanished during its slot")
    pushed = after.decision_stack[index + 1 :]
    return replace(after, decision_stack=after.decision_stack[: index + 1]), pushed


def _restack(state: GameState, pushed: tuple[DecisionFrame, ...]) -> GameState:
    """Put the lifted frames back on top of ``state``."""

    if not pushed:
        return state
    return replace(state, decision_stack=(*state.decision_stack, *pushed))


def _apply_intrigue_acquisition(
    state: GameState,
    frame: DecisionFrame,
    context: dict[str, ActionValue],
    entry: PendingAbility,
    player: int,
    piece: AcquireCardUpTo,
    action: DomainAction,
) -> RuleResult:
    """Resolve an acquisition slot, finishing the card before follow-up frames.

    The slot advances on the choice frame before the card moves, so the frame
    is never buried. An acquire box that needs its own decision (a Spy post,
    the Contract market) opens only after the Intrigue card has resolved and
    reached the discard, exactly as those bonuses stack on the Reveal and
    Price is No Object acquisition paths [Main p. 20].
    """

    card_id = context_str(context, "card_id", owner=_CHOICE_FRAME)
    source = context_str(context, "source", owner=_CHOICE_FRAME)
    step_source = f"{source}:slot:{entry.step}"
    to_hand = acquires_to_hand(state, player, piece)
    taken = replace(entry, step=entry.step + 1)
    last = current_piece(taken) is None
    context[PENDING_ABILITY_KEY] = taken.encode()
    advanced = replace_top_frame(state, with_context(frame, context))
    acquired = acquire_by_piece(
        advanced, player, action, to_hand=to_hand, step_source=step_source
    )
    if acquired is None:
        # Nothing within the cap: the card is still played and the
        # acquisition part alone fizzles (designer ruling, Impress; OQ-057).
        skipped_events: tuple[GameEvent, ...] = (
            GameEvent(
                event_id=f"{step_source}:acquisition_unavailable",
                kind="intrigue_acquisition_unavailable",
                payload=(("card_id", card_id), ("player", player)),
            ),
        )
        if last:
            finished = finish_intrigue_play(
                advanced.pop_decision(),
                player,
                card_id,
                entry_sections(taken),
                source,
                skip_rewards=taken.rewards_applied,
                discard=context.get("separate_effect") is not True,
            )
            return RuleResult(
                state=finished.state, events=(*skipped_events, *finished.events)
            )
        return RuleResult(state=advanced, events=skipped_events)
    next_state, pushed = _lift_pushed_frames(frame.frame_id, acquired.result.state)
    events = acquired.result.events
    top = top_frame(next_state)
    if top is None or top.frame_id != frame.frame_id:
        raise RuntimeError("Intrigue acquisition buried its choice frame")
    if last:
        finished = finish_intrigue_play(
            next_state.pop_decision(),
            player,
            card_id,
            entry_sections(taken),
            source,
            skip_rewards=taken.rewards_applied,
            discard=context.get("separate_effect") is not True,
        )
        next_state = finished.state
        events = (*events, *finished.events)
    opened = open_acquisition_frames(
        _restack(next_state, pushed), player, acquired, source=step_source
    )
    return RuleResult(state=opened.state, events=(*events, *opened.events))


def finish_intrigue_play(
    state: GameState,
    player: int,
    card_id: str,
    sections: tuple[EffectSection, ...],
    source: str,
    *,
    skip_rewards: bool = False,
    discard: bool = True,
) -> RuleResult:
    """Apply pending automatic rewards, discard the card, and update turns.

    ``skip_rewards`` marks that the owner already resolved the automatic
    rewards mid-frame at a point of their choosing (OQ-015). Without
    ``discard`` only one line of a separate-lines card finished: the card
    stays in play under its ``intrigue_effects`` frame, which closes on its
    own once no line can follow (OQ-058).
    """

    applied = (
        RuleResult(state=state)
        if skip_rewards
        else apply_automatic_rewards(
            state, player, sections, source, played_card_id=card_id
        )
    )
    resolved = applied.state
    if not discard:
        settled = _settle_effects_frame(resolved, player, card_id)
        return RuleResult(
            state=settled.state, events=(*applied.events, *settled.events)
        )
    owner = resolved.players[player]
    if intrigue_card_for_instance(card_id).navigation:
        # A played Navigation card leaves its slot face up next to the
        # Leader; the transient slot bookkeeping ends with it.
        next_state = replace(
            resolved,
            players=replace_player(
                resolved.players,
                replace(
                    owner,
                    navigation_slots=tuple(
                        held for held in owner.navigation_slots if held != card_id
                    ),
                    navigation_played=(*owner.navigation_played, card_id),
                    navigation_active_slot=0,
                    navigation_trigger_faction="",
                ),
            ),
        )
        return RuleResult(state=next_state, events=applied.events)
    held_cards = tuple(held for held in owner.intrigue_cards if held != card_id)
    kept_events: tuple[GameEvent, ...] = ()
    if waits_for_reveal_turn(sections):
        # "If the card does something that won't apply until your next
        # Reveal turn (for example: Charisma, Recruitment Mission), keep it
        # face up in front of you until then, then use and discard it."
        # [FAQ p. 2] (Tleilaxu Puppet, Manipulate): discarded when the
        # owner's Reveal turn ends (``expire_reveal_faceup_intrigue``).
        next_state = replace(
            resolved,
            players=replace_player(
                resolved.players,
                replace(
                    owner,
                    intrigue_cards=held_cards,
                    intrigue_faceup=(*owner.intrigue_faceup, card_id),
                ),
            ),
        )
        kept_events = (
            GameEvent(
                event_id=f"{source}:faceup",
                kind="intrigue_kept_faceup",
                payload=(("card_id", card_id), ("player", player)),
            ),
        )
    else:
        next_state = replace(
            resolved,
            players=replace_player(
                resolved.players, replace(owner, intrigue_cards=held_cards)
            ),
            intrigue_discard=(*resolved.intrigue_discard, card_id),
        )
    refreshed = refresh_combat_participants(_reset_combat_passes(next_state, player))
    final_state = refreshed.state
    if any(
        isinstance(reward, RevealContractsTakeOne)
        for section in sections
        for reward in section.rewards
    ):
        # Coercive Negotiation: the owner chooses among the revealed
        # Contracts after the card has left the hand, so it cannot pay for
        # the Immediate token itself [Bloodlines p. 2] [Main p. 7].
        final_state = open_contract_reveal(final_state, player, card_id, source=source)
    return RuleResult(
        state=final_state,
        events=(*applied.events, *kept_events, *refreshed.events),
    )


def _reset_combat_passes(state: GameState, player: int) -> GameState:
    """A played Combat Intrigue restarts the consecutive-pass count.

    "전투 참여자 전원이 **연속으로** pass했을 때만 카드 플레이 절차를 끝내고
    Combat를 해결한다." [Main p. 14] (docs/rules/combat-and-round-end.md).
    The Combat Intrigue frame need not be on top: a card can leave a window
    of its own above it (Reach Agreement's Contract market, Battlefield
    Research's Tech window, a reshuffle for a draw) when its play finishes,
    so the frame is found in the stack. The seat holding priority is also
    marked as having played this opportunity, so its next pass only hands
    priority on [Main p. 15] (``COMBAT_INTRIGUE_PLAYED_KEY``).
    """

    for index in range(len(state.decision_stack) - 1, -1, -1):
        frame = state.decision_stack[index]
        if frame.kind != FrameKind.COMBAT_INTRIGUE:
            continue
        context = frame_context(frame)
        played = (
            isinstance(frame.decision, PlayerDecision)
            and frame.decision.owner == player
        )
        if context.get("consecutive_passes") == 0 and (
            not played or context.get(COMBAT_INTRIGUE_PLAYED_KEY)
        ):
            return state
        context["consecutive_passes"] = 0
        if played:
            context[COMBAT_INTRIGUE_PLAYED_KEY] = 1
        return replace(
            state,
            decision_stack=(
                *state.decision_stack[:index],
                with_context(frame, context),
                *state.decision_stack[index + 1 :],
            ),
        )
    return state
