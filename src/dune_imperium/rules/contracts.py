"""Public Contract market choices for the Uprising CHOAM Module."""

from collections.abc import Mapping
from copy import replace
from enum import StrEnum
from typing import Final

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.contract_abilities import CONTRACT_ABILITIES
from dune_imperium.content.uprising.contracts import (
    ContractConditionKind,
    contract_for_instance,
)
from dune_imperium.content.uprising.effect_dsl import (
    DrawIntrigueCards,
    DrawPersonalCards,
    GainInfluence,
    GainResources,
    PlaceSpy,
    RecallAgent,
    RecruitTroops,
    Reward,
    TakeContract,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import turn_rows
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.contract_tiles import (
    contract_intrigue_trash_frame,
    owe_contract_completion_draw,
    receive_contract,
)
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
    eligible_agent_contract_ids,
    pending_agent_contract_ids,
    recall_agent_targets,
    recall_board_agent,
    recall_conflict_agent,
    recruit_shortfall_events,
    recruit_troops,
    turn_agent_in_conflict,
)
from dune_imperium.rules.frames import (
    FrameKind,
    own_turn_frame_index,
    owned_top_frame,
    replace_player,
    turn_owner_of,
    update_turn_recruits,
    with_context,
)
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.intrigue_deck import (
    draw_or_queue_intrigue_cards,
    with_trashed_intrigue,
)
from dune_imperium.rules.spy_placement import (
    place_spy,
    recall_spy,
    spy_options,
)


def contract_candidates_for_agent_turn(
    state: GameState,
    player: int,
    space_id: str,
) -> tuple[str, ...]:
    """Snapshot Contracts held when an Agent enters a matching space."""

    if not state.config.choam_module:
        return ()
    if not 0 <= player < state.config.players:
        raise ValueError("Contract owner must identify a configured player")
    space = BOARD_SPACES_BY_ID[space_id]
    candidates: list[str] = []
    for instance_id in state.players[player].active_contract_ids:
        condition = contract_for_instance(instance_id).condition
        if (
            condition.kind is ContractConditionKind.BOARD_SPACE
            and condition.target == space_id
        ) or (
            condition.kind is ContractConditionKind.HARVEST_SPICE
            and space.maker
        ):
            candidates.append(instance_id)
    return tuple(candidates)


def legal_contract_completion_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return mandatory Agent-turn Contract completions now available."""

    if not state.config.choam_module or not 0 <= player < state.config.players:
        return ()
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or context.get("pending_gather_intelligence") is True
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="complete_contract",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in eligible_agent_contract_ids(context, state.players)
    )


def apply_contract_completion(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Complete one eligible Contract and resolve its printed reward."""

    if action not in legal_contract_completion_actions(state, action.actor):
        raise ValueError("action is not a legal Contract completion")
    instance_id = dict(action.arguments).get("instance_id")
    if not isinstance(instance_id, str):
        raise RuntimeError("Contract completion has invalid instance ID")
    _, context = current_agent_effect_context(state)
    remaining = tuple(
        candidate
        for candidate in pending_agent_contract_ids(context)
        if candidate != instance_id
    )
    context["pending_contract_ids"] = ",".join(remaining)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"contract:{instance_id}"
    )
    completed = _complete_contract(state, action.actor, instance_id, source=source)
    next_state = advance_after_effect(
        completed.state,
        context,
        completed.state.players,
    )
    turn_space_id = context.get("space_id")
    # For a reward window, fixed now while the Agent-turn effect context is
    # still open: whether this turn's Agent has left for the Conflict via
    # Into the Fray, which a Recall Agent reward must exclude just like a
    # board space (OQ-068). The turn's rows judge it when taken instead.
    reward_turn_agent_in_conflict = isinstance(
        turn_space_id, str
    ) and turn_agent_in_conflict(
        completed.state.players[action.actor], context, turn_space_id
    )
    rewarded = _await_contract_reward(
        next_state,
        action.actor,
        instance_id,
        source,
        excluded_space_id=turn_space_id if isinstance(turn_space_id, str) else "",
        turn_agent_in_conflict=reward_turn_agent_in_conflict,
    )
    return RuleResult(state=rewarded, events=completed.events)


def complete_acquire_contracts(
    state: GameState,
    player: int,
    acquired_card_id: str,
    *,
    source: str,
) -> RuleResult:
    """Complete Contracts triggered by acquiring a named card."""

    if not state.config.choam_module:
        return RuleResult(state=state)
    if not 0 <= player < state.config.players:
        raise ValueError("Contract owner must identify a configured player")
    if not acquired_card_id or not source:
        raise ValueError("Acquire Contract trigger requires card and source IDs")
    matching = tuple(
        instance_id
        for instance_id in state.players[player].active_contract_ids
        if (
            (condition := contract_for_instance(instance_id).condition).kind
            is ContractConditionKind.ACQUIRE_CARD
            and condition.target == acquired_card_id
        )
    )
    next_state = state
    events: tuple[GameEvent, ...] = ()
    completions: list[tuple[str, str]] = []
    for instance_id in matching:
        completion_source = f"{source}:contract:{instance_id}"
        completed = _complete_contract(
            next_state, player, instance_id, source=completion_source
        )
        next_state = completed.state
        events = (*events, *completed.events)
        completions.append((instance_id, completion_source))
    # The first Contract's reward is answered first: its rows wait first on
    # the owner's turn, its window is pushed last.
    in_turn = turn_rows.waits_on_turn(next_state, player)
    for instance_id, completion_source in (
        completions if in_turn else reversed(completions)
    ):
        next_state = _await_contract_reward(
            next_state, player, instance_id, completion_source
        )
    return RuleResult(state=next_state, events=events)


def legal_contract_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return place, or recall-first-or-decline, choices for a Contract Spy.

    Placing is mandatory while a Spy is in the supply (the erratum to
    [Main p. 11], OQ-057 (14)). Without one, "you may first recall one of
    your Spies for no effect" [Main pp. 11, 20]: the recall can be passed
    up, and once made the Spy is back in the supply and must be placed.
    """

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or "contract_spy_id" not in context
    ):
        return ()
    options = spy_options(
        state, player, None, shared_post=context.get("deep_cover") is True
    )
    return (
        *(
            (DomainAction(action_id="decline_contract_spy", actor=player),)
            if options.pass_up
            else ()
        ),
        *(
            DomainAction(
                action_id="recall_spy_for_contract",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.recall
        ),
        *(
            DomainAction(
                action_id="place_contract_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.place
        ),
    )


def apply_contract_spy_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Recall first or decline without a Spy in supply, or place the Spy."""

    if action not in legal_contract_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Contract Spy choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    instance_id = context.get("contract_spy_id")
    source = context.get("source")
    if not isinstance(instance_id, str) or not isinstance(source, str):
        raise RuntimeError("Contract Spy frame has invalid context")
    if action.action_id == "decline_contract_spy":
        return RuleResult(
            state=replace(state, decision_stack=state.decision_stack[:-1]),
            events=(
                GameEvent(
                    event_id=f"{source}:spy_unavailable",
                    kind="spy_placement_unavailable",
                    payload=(("contract_id", instance_id), ("player", action.actor)),
                ),
            ),
        )
    post_id = dict(action.arguments).get("post_id")
    if not isinstance(post_id, str):
        raise RuntimeError("Contract Spy choice has invalid post ID")
    owner = state.players[action.actor]
    if action.action_id == "recall_spy_for_contract":
        next_owner = recall_spy(owner, post_id)
        context["contract_spy_recalled"] = True
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        next_state = replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=(*state.decision_stack[:-1], next_frame),
        )
        event = GameEvent(
            event_id=f"{source}:spy_recalled:{post_id}",
            kind="spy_recalled",
            payload=(
                ("player", action.actor),
                ("post_id", post_id),
                ("source", instance_id),
            ),
        )
        return RuleResult(state=next_state, events=(event,))

    next_owner = place_spy(owner, post_id)
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
        decision_stack=state.decision_stack[:-1],
    )
    event = GameEvent(
        event_id=f"{source}:spy_placed:{post_id}",
        kind="spy_placed",
        payload=(
            ("contract_id", instance_id),
            ("player", action.actor),
            ("post_id", post_id),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_contract_recall_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the Agents a Contract recall reward may return to the Leader.

    One action per ``contract_recall_targets`` entry. With none the reward
    fizzles (the designer's Sardaukar II ruling, OQ-057), through
    ``resolve_contract_without_recall``: the owner confirms it instead of
    the engine fizzling it unasked (user ruling 2026-09-30, "결정 창 없이
    자동으로 넘어가는 곳도 모두 결정 창을 연다").
    """

    targets = contract_recall_targets(state, player)
    if targets is None:
        return ()
    if not targets:
        return (
            DomainAction(action_id="resolve_contract_without_recall", actor=player),
        )
    return tuple(
        # An earlier turn's Into the Fray Agent in the Conflict is one of
        # "your Agents" too (OQ-037 (d)), extended to every Recall Agent
        # effect by the 2026-09-26 user ruling (OQ-068).
        DomainAction(action_id="recall_conflict_agent_for_contract", actor=player)
        if target == "conflict"
        else DomainAction(
            action_id="recall_agent_for_contract",
            actor=player,
            arguments=(("space_id", target),),
        )
        for target in targets
    )


def contract_recall_targets(state: GameState, player: int) -> tuple[str, ...] | None:
    """Where ``player``'s Contract recall reward may take an Agent from.

    None unless the reward's recall frame is on top and the seat's own.
    The targets are its board spaces other than this turn's ("Return one of
    your other Agents on the board to your Leader (not the Agent you sent
    during this turn)" [Main p. 20]) and "conflict" for an earlier turn's
    Into the Fray Agent (OQ-068). Nothing else can be done while this frame
    is on top, so they stay fixed for its whole life. The provider offers
    one recall per target, or the confirm when there is none, and the page
    greys the recall out with this same answer (``display.unavailable``).
    """

    if not 0 <= player < state.config.players or not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.CONTRACT_REWARD_RECALL:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    context = dict(frame.context)
    excluded = context.get("excluded_space_id")
    return recall_agent_targets(
        state.players[player],
        excluded_space_id=excluded if isinstance(excluded, str) else "",
        turn_agent_in_conflict=context.get("turn_agent_in_conflict") is True,
    )


def apply_contract_recall_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Recall the chosen Agent for a completed Contract [Main p. 20]."""

    if action not in legal_contract_recall_actions(state, action.actor):
        raise ValueError("action is not a legal Contract recall choice")
    source = dict(state.decision_stack[-1].context).get("source")
    if not isinstance(source, str):
        raise RuntimeError("Contract recall frame has invalid source")
    owner = state.players[action.actor]
    if action.action_id == "resolve_contract_without_recall":
        # No other Agent to recall: the reward simply fizzles (the
        # designer's Sardaukar II ruling, OQ-057), now confirmed by the
        # owner rather than skipped unasked (user ruling 2026-09-30).
        return RuleResult(
            state=state.pop_decision(),
            events=(
                GameEvent(
                    event_id=f"{source}:reward:recall_unavailable",
                    kind="contract_recall_unavailable",
                    payload=(("player", action.actor),),
                ),
            ),
        )
    if action.action_id == "recall_conflict_agent_for_contract":
        next_owner, event = recall_conflict_agent(
            owner,
            player=action.actor,
            source=source,
            event_id=f"{source}:reward:recall:conflict",
        )
    else:
        space_id = dict(action.arguments).get("space_id")
        if not isinstance(space_id, str):
            raise RuntimeError("Contract recall choice has invalid space ID")
        next_owner, event = recall_board_agent(
            owner,
            space_id,
            player=action.actor,
            source=source,
            event_id=f"{source}:reward:recall:{space_id}",
        )
    next_state = replace(
        state.pop_decision(),
        players=replace_player(state.players, next_owner),
    )
    return RuleResult(state=next_state, events=(event,))


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
        kind=FrameKind.CONTRACT_MARKET,
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
    if contract_gain_opens_market(state, player):
        return RuleResult(
            state=state.push_decision(
                contract_choice_frame(player, count, source=source)
            )
        )
    return _gain_exhausted_market_solari(state, player, count, source=source)


def contract_gain_opens_market(state: GameState, player: int) -> bool:
    """Whether ``begin_contract_gain`` opens a market choice for ``player`` now.

    Otherwise the market is exhausted and the icons revert to Solari at once.
    Over an exhausted market Shaddam Corrino IV's icons still take his
    set-aside Sardaukar Contracts, which nobody has taken yet; the two-Solari
    reversion waits until they are gone too (OQ-021).
    """

    return bool(state.face_up_contract_ids) or _holds_set_aside_choice(
        state, player
    )


def _holds_set_aside_choice(state: GameState, player: int) -> bool:
    return (
        state.players[player].leader_id == "shaddam_corrino_iv"
        and bool(state.sardaukar_contract_ids)
    )


class ContractTakeBlock(StrEnum):
    """Why ``player`` cannot take one Contract of the market right now.

    The Bloodlines Immediate: "You can't take the new Immediate contract
    unless you have an Intrigue card to trash." `[Bloodlines p. 2]`.
    ``takeable_contract_ids`` offers a Contract exactly when
    ``contract_take_block`` is None, and the page's greyed-out row reads the
    same block (``display.unavailable``), so the two cannot disagree.
    """

    NEEDS_INTRIGUE = "needs_intrigue"


def market_contract_ids(state: GameState, player: int) -> tuple[str, ...]:
    """The Contracts a Contract icon of ``player`` chooses among.

    The face-up tokens, and for Shaddam Corrino IV his set-aside Sardaukar
    Contracts, taken in place of a generally available one [FAQ p. 3].
    """

    set_aside = (
        state.sardaukar_contract_ids
        if state.players[player].leader_id == "shaddam_corrino_iv"
        else ()
    )
    return (*state.face_up_contract_ids, *set_aside)


def contract_take_block(
    state: GameState, player: int, instance_id: str
) -> ContractTakeBlock | None:
    """Return why ``player`` cannot take ``instance_id`` now, or None.

    Only the seat's own Intrigue hand is read, so the answer is the same in
    any re-deal of the zones the seat cannot see.
    """

    if (
        contract_for_instance(instance_id).requires_intrigue_trash
        and not state.players[player].intrigue_cards
    ):
        return ContractTakeBlock.NEEDS_INTRIGUE
    return None


def takeable_contract_ids(state: GameState, player: int) -> tuple[str, ...]:
    """Return the Contracts ``player`` could take from the market right now.

    The Bloodlines Immediate "cannot be taken without an Intrigue card to
    trash" `[Bloodlines p. 2]`, so a market can hold face-up tokens and still
    offer this player nothing (``contract_take_block``).
    """

    return tuple(
        instance_id
        for instance_id in market_contract_ids(state, player)
        if contract_take_block(state, player, instance_id) is None
    )


def legal_contract_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return every Contract the pending owner may take right now.

    Shaddam Corrino IV may acquire a set-aside Sardaukar Contract in place
    of one of the generally available Contracts [FAQ p. 3], so his choices
    add the set-aside tiles while the market itself is open.

    When nothing in a non-empty market can be taken (only the Bloodlines
    Immediate is left and the owner holds no Intrigue card to trash), the
    icons are held, not converted to Solari (OQ-059), and the owner
    confirms that with ``hold_contract_icons`` instead of the engine
    closing the window unasked (user ruling 2026-09-30, "결정 창 없이
    자동으로 넘어가는 곳도 모두 결정 창을 연다"). An icon a Combat Intrigue
    card gives is settled when the card is played -- "교전 책략은 어쨌든 바로
    쓰고 효과 봐야하는거잖아" (user, 2026-10-02) -- so there the owner confirms
    ``resolve_contract_icons_without_contract`` and the icons fizzle at once.
    """

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.CONTRACT_MARKET:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    actions = [
        DomainAction(
            action_id="take_contract",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in takeable_contract_ids(state, player)
    ]
    if not actions and contract_icons_must_be_held(state):
        actions.append(
            DomainAction(
                action_id=(
                    "resolve_contract_icons_without_contract"
                    if _in_combat_intrigue(state)
                    else "hold_contract_icons"
                ),
                actor=player,
            )
        )
    return tuple(actions)


def _in_combat_intrigue(state: GameState) -> bool:
    """Whether a Combat Intrigue card is resolving (before the rewards)."""

    return state.phase is GamePhase.COMBAT and not state.combat_intrigue_complete


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
    bank = state.contract_bank
    sardaukar_set_aside = state.sardaukar_contract_ids
    replacement_id = ""
    if instance_value in sardaukar_set_aside:
        # A set-aside Sardaukar Contract is taken in place of a face-up one
        # [FAQ p. 3]; the market keeps its tiles and nothing refills.
        sardaukar_set_aside = tuple(
            candidate
            for candidate in sardaukar_set_aside
            if candidate != instance_value
        )
    else:
        market_index = market.index(instance_value)
        replacement_id = bank[0] if bank else ""
        if replacement_id:
            market[market_index] = replacement_id
            bank = bank[1:]
        else:
            del market[market_index]

    definition = contract_for_instance(instance_value)
    next_owner = receive_contract(state, state.players[action.actor], instance_value)
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
    if definition.requires_intrigue_trash:
        # The Bloodlines Immediate is paid by trashing an Intrigue card
        # [Bloodlines p. 2]; the taker chooses which one before it completes.
        remaining_stack = (
            *remaining_stack,
            contract_intrigue_trash_frame(
                action.actor,
                instance_value,
                source=f"{source_value}:contract:{instance_value}",
            ),
        )
    next_state = replace(
        state,
        players=players,
        contract_bank=bank,
        face_up_contract_ids=tuple(market),
        sardaukar_contract_ids=sardaukar_set_aside,
        decision_stack=remaining_stack,
        combat_rewards_resolved=_combat_rewards_done(state, remaining_stack),
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
    if definition.completes_immediately and not definition.requires_intrigue_trash:
        completed = complete_immediate_contract(
            next_state,
            action.actor,
            instance_value,
            source=f"{source_value}:contract:{instance_value}",
        )
        next_state = completed.state
        events.extend(completed.events)
    return RuleResult(state=next_state, events=tuple(events))


def complete_immediate_contract(
    state: GameState, player: int, instance_id: str, *, source: str
) -> RuleResult:
    """Complete an Immediate Contract the moment it is taken [Main p. 16]:
    ``receive_contract`` left it active; its reward waits in its window
    (OQ-112)."""

    completed = _complete_contract(state, player, instance_id, source=source)
    pushed = _await_contract_reward(completed.state, player, instance_id, source)
    return RuleResult(
        state=replace(
            pushed,
            combat_rewards_resolved=_combat_rewards_done(pushed, pushed.decision_stack),
        ),
        events=completed.events,
    )


def _contract_frame_owner(state: GameState) -> int | None:
    """Owner of a top Contract market frame, or None when there is none."""

    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.CONTRACT_MARKET:
        return None
    if not isinstance(frame.decision, PlayerDecision):
        return None
    return frame.decision.owner


def contract_icons_must_be_held(state: GameState) -> bool:
    """Return whether the open Contract choice has nothing it can take.

    The market is not empty, so the printed conversion does not apply -- "if
    all contracts have been taken by players, the icon reverts to giving you
    2 Solari" `[Main p. 16]` -- but every face-up token is out of reach, which
    happens when only the Bloodlines Immediate is left and the owner has no
    Intrigue card to trash `[Bloodlines p. 2]`. The icon waits for the rest of
    the turn instead (OQ-059), from a Conflict reward for the rest of that
    seat's Conflict rewards (user ruling 2026-10-02, L2-Q2), and in the
    Arrakeen Scouts step for the rest of the step; a Combat Intrigue's icon
    fizzles at once (``apply_contract_fizzle``, both user rulings of the same
    day).
    """

    player = _contract_frame_owner(state)
    if player is None or exhausted_contract_choice_is_pending(state):
        return False
    return not takeable_contract_ids(state, player)


def apply_contract_hold(state: GameState, action: DomainAction) -> RuleResult:
    """``hold_contract_icons``: the owner confirms the icons wait (OQ-059)."""

    if action not in legal_contract_actions(state, action.actor):
        raise ValueError("action is not a legal Contract choice")
    return hold_contract_icons(state)


def apply_contract_fizzle(state: GameState, action: DomainAction) -> RuleResult:
    """``resolve_contract_icons_without_contract``: a Combat Intrigue's icons
    that find nothing the owner can take fizzle as the card resolves.

    User ruling 2026-10-02 on OQ-059: "이건 책략 사용 시점에 완결해야지? 교전
    책략은 어쨌든 바로 쓰고 효과 봐야하는거잖아" -- the card's effect is
    complete when it is played, so its icons are neither held for the
    Conflict rewards nor converted to Solari (the market is not empty
    [Main p. 16]); they fizzle with the public event.
    """

    if action not in legal_contract_actions(state, action.actor):
        raise ValueError("action is not a legal Contract choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    remaining = context.get("remaining")
    source = context.get("source")
    if (
        isinstance(remaining, bool)
        or not isinstance(remaining, int)
        or remaining < 1
        or not isinstance(source, str)
    ):
        raise RuntimeError("Contract choice frame has invalid context")
    player = action.actor
    return RuleResult(
        state=state.pop_decision(),
        events=(
            GameEvent(
                event_id=f"{source}:contract_icons_fizzled:{player}:{remaining}",
                kind="contract_icons_fizzled",
                payload=(("count", remaining), ("player", player)),
            ),
        ),
    )


def hold_contract_icons(state: GameState) -> RuleResult:
    """Close the open choice and keep its icons on the seat.

    They wait for the turn's end (OQ-059), from a Conflict reward for the
    end of that seat's Conflict rewards (``combat_held_contract_owner``), or
    in the Arrakeen Scouts step for the step's end
    (``scouts._open_first_turn``); a token the seat can take meanwhile
    reopens the market.
    """

    if not contract_icons_must_be_held(state):
        raise ValueError("there is no Contract choice to hold")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    remaining = context.get("remaining")
    source = context.get("source")
    player = _contract_frame_owner(state)
    if (
        isinstance(remaining, bool)
        or not isinstance(remaining, int)
        or remaining < 1
        or not isinstance(source, str)
        or player is None
    ):
        raise RuntimeError("Contract choice frame has invalid context")
    owner = state.players[player]
    held = owner.held_contract_icons + remaining
    remaining_stack = state.decision_stack[:-1]
    next_state = replace(
        state,
        decision_stack=remaining_stack,
        players=replace_player(
            state.players, replace(owner, held_contract_icons=held)
        ),
        # Like every Conflict reward frame (``combat_rewards_done``).
        combat_rewards_resolved=_combat_rewards_done(state, remaining_stack),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:contract_icons_held:{player}:{remaining}",
                kind="contract_icons_held",
                payload=(
                    ("count", remaining),
                    ("held", held),
                    ("player", player),
                ),
            ),
        ),
    )


def held_contract_icons_can_open(state: GameState, player: int) -> bool:
    """Return whether a held icon may resolve now that the market allows it."""

    if not 0 <= player < state.config.players:
        return False
    return bool(state.players[player].held_contract_icons) and bool(
        takeable_contract_ids(state, player)
    )


def _combat_rewards_done(
    state: GameState, remaining: tuple[DecisionFrame, ...]
) -> bool:
    """``combat_rewards_resolved`` after a frame closes (Combat only)."""

    if state.phase is not GamePhase.COMBAT:
        return state.combat_rewards_resolved
    # Imported here: ``combat`` imports this module for its contract frames.
    from dune_imperium.rules.combat import combat_rewards_done

    return combat_rewards_done(state, remaining)


def combat_held_contract_owner(state: GameState) -> int | None:
    """A seat whose Conflict rewards are all resolved with icons still held.

    User ruling 2026-10-02 (L2-Q2, "보상 끝까지 보류 후 불발"): a Contract
    icon from a Conflict reward that finds nothing it can take is held while
    that seat resolves the rest of its Conflict rewards -- an Intrigue card
    gained meanwhile can make the Immediate takeable, and the market then
    reopens -- and once they are all resolved it fizzles with the public
    event, never carried into a later turn nor dropped silently. The Combat
    phase is no turn [Main p. 8], so no turn-end press would close it.

    The rewards are dealt one recipient at a time (``resolve_combat_rewards``),
    and what a recipient's frames set off for the seat (the Immediate's
    Intrigue trash, an owed Intrigue draw, a queued Navigation play, Skill
    choice, track Spy or Friends Everywhere bonus) is the seat's too. So the
    seat is done once it owns no frame on the stack and nothing is queued
    for it, and no chance step is pending (a reshuffle may still bring it an
    Intrigue card); its icons then fizzle before the next recipient is paid.
    None before the first reward is dealt. A Combat
    Intrigue's icons are never held: they fizzle as the card resolves
    (``apply_contract_fizzle``).
    """

    if state.phase is not GamePhase.COMBAT or not state.combat_intrigue_complete:
        return None
    if (
        not state.decision_stack
        and not state.combat_rewards_resolved
        and not state.combat_rewards_paid
    ):
        return None
    top = state.decision_stack[-1] if state.decision_stack else None
    if top is not None and not isinstance(top.decision, PlayerDecision):
        return None
    busy = {
        frame.decision.owner
        for frame in state.decision_stack
        if isinstance(frame.decision, PlayerDecision)
    }
    for queue in (
        state.pending_intrigue_draws,
        state.pending_navigation_plays,
        state.pending_skill_choices,
        state.pending_track_spies,
        state.scouts_four_bonus_choices,
    ):
        busy.update(entry[0] for entry in queue)
    for seat in state.players:
        if seat.held_contract_icons and seat.player_id not in busy:
            return seat.player_id
    return None


def fizzle_combat_held_contract_icons(state: GameState) -> RuleResult:
    """Fizzle the held icons of the seat whose Conflict rewards are done."""

    player = combat_held_contract_owner(state)
    if player is None:
        raise ValueError("no seat's Conflict rewards end with icons held")
    return fizzle_held_contract_icons(
        state,
        player,
        source=f"round:{state.round_number}:combat_reward:{player}",
    )


def open_held_contract_icons(state: GameState, player: int) -> RuleResult:
    """Reopen the market for icons held earlier this turn, or earlier in
    the seat's Conflict rewards."""

    if not held_contract_icons_can_open(state, player):
        raise ValueError("there are no held Contract icons to open")
    owner = state.players[player]
    count = owner.held_contract_icons
    cleared = replace(
        state,
        players=replace_player(
            state.players, replace(owner, held_contract_icons=0)
        ),
    )
    source = (
        f"round:{state.round_number}:combat_reward:{player}:held_contract"
        if state.phase is GamePhase.COMBAT
        else f"round:{state.round_number}:player:{player}:held_contract"
    )
    return RuleResult(
        state=cleared.push_decision(
            contract_choice_frame(player, count, source=source)
        ),
        events=(
            GameEvent(
                event_id=f"{source}:reopened:{count}",
                kind="contract_icons_reopened",
                payload=(("count", count), ("player", player)),
            ),
        ),
    )


def fizzle_held_contract_icons(
    state: GameState,
    player: int,
    *,
    source: str,
) -> RuleResult:
    """Drop the turn's unusable Contract icons without a substitute reward.

    The designer rules consistently that an effect with no valid target
    fizzles, and the two-Solari conversion is a separate printed condition
    that this market does not meet (OQ-059, user ruling 2026-09-10). The
    owner's turn-end press calls it, and so do the end of the seat's
    Conflict rewards (``combat_held_contract_owner``, user ruling
    2026-10-02, L2-Q2) and the end of the Arrakeen Scouts step
    (``scouts._open_first_turn``, same day).
    """

    owner = state.players[player]
    count = owner.held_contract_icons
    if not count:
        return RuleResult(state=state)
    next_state = replace(
        state,
        players=replace_player(
            state.players, replace(owner, held_contract_icons=0)
        ),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:contract_icons_fizzled:{player}:{count}",
                kind="contract_icons_fizzled",
                payload=(("count", count), ("player", player)),
            ),
        ),
    )


def exhausted_contract_choice_is_pending(state: GameState) -> bool:
    """Return whether the top Contract frame can resolve without player input."""

    if not state.decision_stack:
        return False
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.CONTRACT_MARKET or state.face_up_contract_ids:
        return False
    # Shaddam's icons still take a set-aside Sardaukar Contract over an
    # exhausted market (OQ-021).
    return not (
        isinstance(frame.decision, PlayerDecision)
        and _holds_set_aside_choice(state, frame.decision.owner)
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
        combat_rewards_resolved=_combat_rewards_done(state, state.decision_stack),
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


def complete_contract_by_effect(
    state: GameState,
    player: int,
    instance_id: str,
    *,
    source: str,
    excluded_space_id: str = "",
    turn_agent_in_conflict: bool = False,
) -> RuleResult:
    """Complete one active Contract by a card effect, ignoring its condition.

    CHOAM Demands (Bloodlines): "Complete one of your contracts." The
    printed reward resolves as for a normal completion, its choices pushed
    on top of the current decision stack. ``excluded_space_id`` is where the
    Agent of this turn went: a Recall Agent reward returns "one of your
    other Agents on the board ... (not the Agent you sent during this turn)"
    [Main p. 20]; ``turn_agent_in_conflict`` says whether Into the Fray has
    moved that Agent to the Conflict instead (OQ-068).
    """

    completed = _complete_contract(state, player, instance_id, source=source)
    rewarded = _await_contract_reward(
        completed.state,
        player,
        instance_id,
        source,
        excluded_space_id=excluded_space_id,
        turn_agent_in_conflict=turn_agent_in_conflict,
    )
    return RuleResult(state=rewarded, events=completed.events)


def _complete_contract(
    state: GameState,
    player: int,
    instance_id: str,
    *,
    source: str,
) -> RuleResult:
    """Complete an active Contract: the tile goes face down to its owner's
    completed zone and its reward waits in a window of its own
    (``_contract_reward_window``, stage B2, OQ-112). "Announce that you
    have completed it, gain the reward shown, then flip it face down"
    [Main p. 16]: the caller pushes the window, so its reward comes after
    whatever the completion itself closes."""

    owner = state.players[player]
    if instance_id not in owner.active_contract_ids:
        raise ValueError("completed Contract must be active")
    next_owner = replace(
        owner,
        active_contract_ids=tuple(
            candidate
            for candidate in owner.active_contract_ids
            if candidate != instance_id
        ),
        completed_contract_ids=(*owner.completed_contract_ids, instance_id),
        contracts_completed_turn=owner.contracts_completed_turn + 1,
    )
    # CHOAM Transports' draw: the owner's next step in its own turn, else
    # the engine's post-step draw (user decision 2026-10-10, OQ-106) -- right
    # after the completion, before every row of its reward (OQ-112).
    next_owner = owe_contract_completion_draw(state, next_owner)
    event = GameEvent(
        event_id=f"{source}:completed",
        kind="contract_completed",
        payload=(("contract_id", instance_id), ("player", player)),
    )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, next_owner)),
        events=(event,),
    )


# --- A completed Contract's reward, icon by icon (stage B2, OQ-112) --------
#
# Like a Conflict reward (``rules/combat.py``), a completed Contract's
# reward waits in a window of its owner's: a row per icon the record prints
# (``CONTRACT_ABILITIES``), in any order. An automatic icon (resources,
# troops, a fixed Influence, an Intrigue or card draw) resolves on its row; a
# choice icon (a Contract, a Spy, an Agent recall) opens its own frame. The
# window is stacked where the Contract completed, in a turn or not; it opens
# even for a single icon (OQ-112 (2)).

CONTRACT_REWARD_ICON_ACTION: Final = "resolve_contract_reward_icon"
# Every icon a Contract reward may print, the action codec's order.
CONTRACT_REWARD_ICON_KINDS: Final = (
    "resources",
    "troops",
    "faction_influence",
    "intrigue",
    "cards",
    "contract",
    "spy",
    "deep_cover_spy",
    "recall_agent",
)
# The order the engine paid a Contract reward in before stage B2 (an older
# record's, and the AI seats', order): troops, resources and a fixed
# Influence at once, the Bloodlines Immediate's two draws, then its one
# choice (an Agent recall, a card draw, a Contract, a Spy).
_LEGACY_CONTRACT_ORDER: Final = (
    "troops",
    "resources",
    "faction_influence",
    "intrigue",
    "recall_agent",
    "cards",
    "contract",
    "spy",
    "deep_cover_spy",
)
_CONTRACT_ICONS_KEY: Final = "icons"
_CONTRACT_PRINTED_KEY: Final = "printed"


def _contract_icon_kind(piece: Reward) -> str:
    match piece:
        case GainResources():
            return "resources"
        case RecruitTroops():
            return "troops"
        case GainInfluence(factions=(_,)):
            return "faction_influence"
        case DrawIntrigueCards():
            return "intrigue"
        case DrawPersonalCards():
            return "cards"
        case TakeContract():
            return "contract"
        case PlaceSpy(shared_post=True):
            return "deep_cover_spy"
        case PlaceSpy():
            return "spy"
        case RecallAgent():
            return "recall_agent"
    raise TypeError(f"{piece!r} is not a Contract reward icon")


def contract_reward_icons(instance_id: str) -> tuple[tuple[str, Reward], ...]:
    """Each icon of a Contract's reward with the piece that prints it, in
    printed order."""

    definition = contract_for_instance(instance_id)
    # A second copy shares its first copy's record.
    ability = CONTRACT_ABILITIES[definition.copy_of or definition.card.card_id]
    (line,) = ability.sections
    return tuple((_contract_icon_kind(piece), piece) for piece in line.rewards)


def contract_icon_piece(instance_id: str, kind: str) -> Reward:
    """The first piece of a Contract's reward that prints ``kind``."""

    return next(
        piece for icon, piece in contract_reward_icons(instance_id) if icon == kind
    )


def _contract_reward_window(
    player: int,
    instance_id: str,
    source: str,
    *,
    excluded_space_id: str = "",
    turn_agent_in_conflict: bool = False,
) -> DecisionFrame:
    """The owner's window over a completed Contract's reward icons.

    ``excluded_space_id`` and ``turn_agent_in_conflict`` are fixed at the
    completion, while the Agent turn is still open: a Recall Agent icon may
    not take the Agent sent this turn [Main p. 20], on the board or moved
    into the Conflict (OQ-068)."""

    printed = [kind for kind, _piece in contract_reward_icons(instance_id)]
    icons = [
        kind for kind in _LEGACY_CONTRACT_ORDER for _ in range(printed.count(kind))
    ]
    context: dict[str, ActionValue] = {
        "contract_id": instance_id,
        "excluded_space_id": excluded_space_id,
        _CONTRACT_ICONS_KEY: ",".join(icons),
        _CONTRACT_PRINTED_KEY: ",".join(dict.fromkeys(printed)),
        "source": source,
        "turn_agent_in_conflict": turn_agent_in_conflict,
    }
    return DecisionFrame(
        kind=FrameKind.CONTRACT_REWARD_ICONS,
        frame_id=f"{source}:reward_icons",
        decision=PlayerDecision(owner=player, prompt="Gain your Contract reward"),
        context=tuple(sorted(context.items())),
    )


def _await_contract_reward(
    state: GameState,
    player: int,
    instance_id: str,
    source: str,
    *,
    excluded_space_id: str = "",
    turn_agent_in_conflict: bool = False,
) -> GameState:
    """Where a completed Contract's reward waits: inside its owner's own
    turn, an icon each as rows of that turn (OQ-112 (4), user decision
    2026-10-19 B3-4: "차례 안에서 완수한 계약의 보상은 차례의 줄이다"),
    beside the turn's other effects and holding its end; elsewhere -- in
    Combat, in the Arrakeen Scouts step or a Scouts line, a finished game --
    its window (``_contract_reward_window``). The window fixes what a Recall
    Agent icon may not take now (it is answered next); a row judges it when
    it is taken (``_turn_agent_exclusion``)."""

    if turn_rows.waits_on_turn(state, player) and state.phase is not (
        GamePhase.FINISHED
    ):
        for kind, _piece in contract_reward_icons(instance_id):
            queued = turn_rows.queue(
                state,
                player,
                (turn_rows.CONTRACT_ICON, source, _icon_row_value(instance_id, kind)),
            )
            assert queued is not None
            state = queued
        return state
    return state.push_decision(
        _contract_reward_window(
            player,
            instance_id,
            source,
            excluded_space_id=excluded_space_id,
            turn_agent_in_conflict=turn_agent_in_conflict,
        )
    )


def legal_contract_icon_row_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """A row per icon of a Contract completed in the owner's turn that waits
    on it (OQ-112 (4)), each Contract's in printed order."""

    frame = turn_rows.rows_frame(state, player)
    if frame is None:
        return ()
    rows: dict[DomainAction, None] = {}
    for kind, _source, value in turn_rows.pending(frame):
        if kind != turn_rows.CONTRACT_ICON:
            continue
        instance_id, icon = _icon_row_parts(value)
        rows.setdefault(
            DomainAction(
                action_id=CONTRACT_REWARD_ICON_ACTION,
                actor=player,
                arguments=(("contract_id", instance_id), ("effect", icon)),
            ),
            None,
        )
    return tuple(rows)


def legacy_contract_icon_row(state: GameState, player: int) -> DomainAction | None:
    """The row of a Contract completed in the owner's turn that the engine
    before stage B3b paid next (its window: the oldest Contract first, its
    icons in ``_LEGACY_CONTRACT_ORDER``), or None when none waits."""

    frame = turn_rows.rows_frame(state, player)
    if frame is None:
        return None
    waiting = [
        _icon_row_parts(value)
        for kind, _source, value in turn_rows.pending(frame)
        if kind == turn_rows.CONTRACT_ICON
    ]
    if not waiting:
        return None
    oldest = waiting[0][0]
    icons = {icon for instance_id, icon in waiting if instance_id == oldest}
    icon = next(kind for kind in _LEGACY_CONTRACT_ORDER if kind in icons)
    return DomainAction(
        action_id=CONTRACT_REWARD_ICON_ACTION,
        actor=player,
        arguments=(("contract_id", oldest), ("effect", icon)),
    )


def _contract_window_icons(frame: DecisionFrame) -> tuple[str, ...]:
    text = dict(frame.context)[_CONTRACT_ICONS_KEY]
    return tuple(str(text).split(",")) if text else ()


def legal_contract_reward_icon_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """One row per icon kind still to resolve, in printed order."""

    frame = owned_top_frame(state, FrameKind.CONTRACT_REWARD_ICONS, player)
    if frame is None:
        return ()
    remaining = set(_contract_window_icons(frame))
    printed = str(dict(frame.context)[_CONTRACT_PRINTED_KEY]).split(",")
    return tuple(
        DomainAction(
            action_id=CONTRACT_REWARD_ICON_ACTION,
            actor=player,
            arguments=(("effect", kind),),
        )
        for kind in printed
        if kind in remaining
    )


def legacy_contract_reward_icon(state: GameState, player: int) -> DomainAction | None:
    """The row the engine before stage B2 resolved next in ``player``'s
    Contract reward window, or None outside one (``_LEGACY_CONTRACT_ORDER``)."""

    frame = owned_top_frame(state, FrameKind.CONTRACT_REWARD_ICONS, player)
    if frame is None:
        return None
    icons = _contract_window_icons(frame)
    if not icons:
        return None
    return DomainAction(
        action_id=CONTRACT_REWARD_ICON_ACTION,
        actor=player,
        arguments=(("effect", icons[0]),),
    )


def apply_contract_reward_icon(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one icon of a completed Contract's reward (OQ-112): a row of
    its window, or a row waiting on its owner's turn (OQ-112 (4))."""

    player = action.actor
    arguments = dict(action.arguments)
    kind = arguments.get("effect")
    if "contract_id" in arguments:
        return _apply_contract_icon_row(state, player, arguments)
    frame = owned_top_frame(state, FrameKind.CONTRACT_REWARD_ICONS, player)
    if frame is None:
        raise ValueError("no Contract reward window is open for this seat")
    icons = list(_contract_window_icons(frame))
    if not isinstance(kind, str) or kind not in icons:
        raise ValueError(f"no {kind!r} icon waits in this Contract reward")
    icons.remove(kind)
    context = dict(frame.context)
    instance_id = str(context["contract_id"])
    source = str(context["source"])
    if icons:
        context[_CONTRACT_ICONS_KEY] = ",".join(icons)
        stack = (*state.decision_stack[:-1], with_context(frame, context))
    else:
        stack = state.decision_stack[:-1]
    state = replace(state, decision_stack=stack)
    return _pay_contract_icon(
        state,
        player,
        instance_id,
        kind,
        source,
        excluded_space_id=str(context["excluded_space_id"]),
        turn_agent_in_conflict=context["turn_agent_in_conflict"] is True,
        remaining=len(icons),
    )


def _apply_contract_icon_row(
    state: GameState, player: int, arguments: Mapping[str, ActionValue]
) -> RuleResult:
    """Resolve a completed Contract's icon waiting on its owner's turn."""

    instance_id, kind = arguments.get("contract_id"), arguments.get("effect")
    frame = turn_rows.rows_frame(state, player)
    items = [
        (item, _icon_row_parts(item[2]))
        for item in (() if frame is None else turn_rows.pending(frame))
        if item[0] == turn_rows.CONTRACT_ICON
    ]
    found = next(
        (
            (item, parts)
            for item, parts in items
            if parts[0] == instance_id and parts[1] == kind
        ),
        None,
    )
    if found is None:
        raise ValueError(f"no {kind!r} icon of {instance_id!r} waits on this turn")
    item, (instance, icon) = found
    excluded_space_id, in_conflict = _turn_agent_exclusion(state, player)
    state = turn_rows.take(state, player, item)
    remaining = sum(1 for _, parts in items if parts[0] == instance) - 1
    return _pay_contract_icon(
        state,
        player,
        instance,
        icon,
        item[1],
        excluded_space_id=excluded_space_id,
        turn_agent_in_conflict=in_conflict,
        remaining=remaining,
    )


def _turn_agent_exclusion(state: GameState, player: int) -> tuple[str, bool]:
    """What a Recall Agent icon taken now may not recall: "not the Agent you
    sent during this turn" [Main p. 20] -- still on the turn's space, or
    moved to the Conflict by Into the Fray (OQ-068) -- read from the owner's
    open Agent-turn effect frame when the row is taken, since the turn's
    other effects may move that Agent between the completion and the row. A
    Reveal, or a turn before its Agent is sent, sent none."""

    index = own_turn_frame_index(state, player)
    if index is None:
        return "", False
    frame = state.decision_stack[index]
    context = dict(frame.context)
    space_id = context.get("space_id")
    if frame.kind != FrameKind.AGENT_EFFECTS or not isinstance(space_id, str):
        return "", False
    return space_id, turn_agent_in_conflict(state.players[player], context, space_id)


def _icon_row_value(instance_id: str, kind: str) -> str:
    return f"{instance_id}|{kind}"


def _icon_row_parts(value: str) -> tuple[str, str]:
    instance_id, kind = value.split("|")
    return instance_id, kind


def _pay_contract_icon(
    state: GameState,
    player: int,
    instance_id: str,
    kind: str,
    source: str,
    *,
    excluded_space_id: str,
    turn_agent_in_conflict: bool,
    remaining: int,
) -> RuleResult:
    """Pay one icon of a completed Contract's reward: an automatic icon at
    once, a choice icon by opening its frame. ``remaining`` counts the
    Contract's icons still waiting after this one (the event's id)."""

    piece = contract_icon_piece(instance_id, kind)
    owner = state.players[player]
    events: list[GameEvent] = []
    details: list[tuple[str, ActionValue]] = []
    match kind, piece:
        case "troops", RecruitTroops(count=count):
            recruited_owner, recruited = recruit_troops(owner, count)
            state = replace(
                state, players=replace_player(state.players, recruited_owner)
            )
            if recruited and turn_owner_of(state) == player:
                # Troops recruited during the owner's own turn "from any
                # source" may be deployed [Main p. 10] [FAQ p. 4].
                state = update_turn_recruits(state, troops_recruited=recruited)
            events.extend(
                recruit_shortfall_events(
                    f"{source}:completed", player, count, recruited
                )
            )
            details.append(("troops", recruited))
        case "resources", GainResources(solari=solari, spice=spice, water=water):
            next_owner = replace(
                owner,
                resources=replace(
                    owner.resources,
                    solari=owner.resources.solari + solari,
                    spice=owner.resources.spice + spice,
                    water=owner.resources.water + water,
                ),
            )
            state = replace(state, players=replace_player(state.players, next_owner))
            events.append(
                resources_gained_event(
                    f"{source}:contract_reward",
                    player,
                    solari=solari,
                    spice=spice,
                    water=water,
                )
            )
        case "faction_influence", GainInfluence(times=times, factions=(faction,)):
            gained = gain_faction_influence(
                state,
                player,
                faction,
                times,
                event_prefix=f"{source}:reward:{faction.value}",
            )
            state = gained.state
            events.extend(gained.events)
            details.extend((("faction", faction.value), ("influence", times)))
        case "intrigue", DrawIntrigueCards(count=count):
            drawn = draw_or_queue_intrigue_cards(
                state, player, count, source=f"{source}:reward:intrigue"
            )
            state = drawn.state
            events.extend(drawn.events)
            details.append(("intrigue_cards", count))
        case "cards", DrawPersonalCards(count=count):
            drawn = draw_or_request_personal_cards(
                state, player, count, source=f"{source}:reward:personal_draw"
            )
            state = drawn.state
            events.extend(drawn.events)
            details.append(("personal_cards", count))
        case "contract", TakeContract(count=count):
            gain = begin_contract_gain(state, player, count, source=f"{source}:reward")
            state = gain.state
            events.extend(gain.events)
            details.append(("contracts", count))
        case "spy" | "deep_cover_spy", PlaceSpy():
            deep_cover = kind == "deep_cover_spy"
            state = state.push_decision(
                DecisionFrame(
                    kind=FrameKind.CONTRACT_REWARD_SPY,
                    frame_id=f"{source}:reward:spy",
                    decision=PlayerDecision(
                        owner=player,
                        prompt=(
                            "Choose an Observation Post for the Contract Spy "
                            "with Deep Cover"
                            if deep_cover
                            else "Choose an Observation Post for the Contract Spy"
                        ),
                    ),
                    context=(
                        (
                            "contract_spy_id",
                            f"contract:{contract_for_instance(instance_id).card.card_id}",
                        ),
                        ("deep_cover", deep_cover),
                        ("source", source),
                        ("turn_owner", player),
                    ),
                )
            )
        case "recall_agent", RecallAgent():
            # Recall one of your Agents; the just-sent Agent is not a valid
            # target [Main p. 20], and with no other placed Agent -- on the
            # board or, an earlier turn's Into the Fray Agent, in the
            # Conflict (OQ-037 (d), extended to every Recall Agent effect by
            # the 2026-09-26 user ruling, OQ-068) -- the reward does nothing.
            # The frame opens either way, and with no target it offers only
            # the confirm ``resolve_contract_without_recall`` (user ruling
            # 2026-09-30: every automatic skip opens a decision window).
            in_conflict = turn_agent_in_conflict
            targets = recall_agent_targets(
                state.players[player],
                excluded_space_id=excluded_space_id,
                turn_agent_in_conflict=in_conflict,
            )
            state = state.push_decision(
                DecisionFrame(
                    kind=FrameKind.CONTRACT_REWARD_RECALL,
                    frame_id=f"{source}:reward:recall",
                    decision=PlayerDecision(
                        owner=player,
                        prompt=(
                            "Choose one of your other Agents to recall"
                            if targets
                            else "No other Agent to recall"
                        ),
                    ),
                    context=(
                        ("excluded_space_id", excluded_space_id),
                        ("source", source),
                        ("turn_agent_in_conflict", in_conflict),
                        ("turn_owner", player),
                    ),
                )
            )
        case _:
            raise ValueError(f"{kind!r} is not a Contract reward icon")
    events.append(
        GameEvent(
            event_id=f"{source}:reward_icon:{remaining}",
            kind="contract_reward_icon_resolved",
            payload=tuple(
                sorted(
                    (
                        ("contract_id", instance_id),
                        ("effect", kind),
                        ("player", player),
                        *details,
                    )
                )
            ),
        )
    )
    if not state.decision_stack:
        state = replace(
            state,
            combat_rewards_resolved=_combat_rewards_done(state, state.decision_stack),
        )
    return RuleResult(state=state, events=tuple(events))


# --- Bloodlines Immediate: trash an Intrigue card -----------------------------------


def legal_contract_intrigue_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the hand Intrigue cards the Bloodlines Immediate may trash."""

    frame = owned_top_frame(state, FrameKind.CONTRACT_INTRIGUE_TRASH, player)
    if frame is None:
        return ()
    return tuple(
        DomainAction(
            action_id="trash_intrigue_for_contract",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in state.players[player].intrigue_cards
    )


def apply_contract_intrigue_trash(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Trash the chosen Intrigue card and complete the Bloodlines Immediate.

    "Requires an Intrigue card": trash an Intrigue card -> draw an Intrigue
    card and a card [card face] [Bloodlines p. 2]. The tile waits in the
    active zone only while this frame is open; nothing else can act on it
    there, and it moves to the completed zone here. The trashed card joins
    the shared Intrigue discard before the draw (OQ-061, user ruling
    2026-10-04).
    """

    if action not in legal_contract_intrigue_trash_actions(state, action.actor):
        raise ValueError("action is not a legal Contract Intrigue trash")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    instance_id = context.get("contract_id")
    source = context.get("source")
    if not isinstance(instance_id, str) or not isinstance(source, str):
        raise RuntimeError("Contract Intrigue trash frame has invalid context")
    card_id = str(dict(action.arguments)["card_id"])
    player = action.actor
    owner = state.players[player]
    if instance_id not in owner.active_contract_ids:
        raise RuntimeError("the Immediate Contract awaiting its trash must be active")
    next_owner = replace(
        owner,
        intrigue_cards=tuple(held for held in owner.intrigue_cards if held != card_id),
        active_contract_ids=tuple(
            held for held in owner.active_contract_ids if held != instance_id
        ),
        completed_contract_ids=(*owner.completed_contract_ids, instance_id),
        contracts_completed_turn=owner.contracts_completed_turn + 1,
    )
    # CHOAM Transports' draw, right after the completion (``_complete_contract``).
    next_owner = owe_contract_completion_draw(state, next_owner)
    remaining = state.decision_stack[:-1]
    next_state = with_trashed_intrigue(
        replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=remaining,
            combat_rewards_resolved=_combat_rewards_done(state, remaining),
        ),
        card_id,
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:intrigue_trashed",
            kind="intrigue_card_trashed",
            payload=(("card_id", card_id), ("player", player)),
        ),
        GameEvent(
            event_id=f"{source}:completed",
            kind="contract_completed",
            payload=(("contract_id", instance_id), ("player", player)),
        ),
    ]
    # Its reward, an Intrigue card and a card, waits on the owner's turn or
    # in its window (OQ-112).
    pushed = _await_contract_reward(next_state, player, instance_id, source)
    next_state = replace(
        pushed,
        combat_rewards_resolved=_combat_rewards_done(pushed, pushed.decision_stack),
    )
    return RuleResult(state=next_state, events=tuple(events))


# --- Bloodlines Earn Any Alliance -----------------------------------------------------


def alliance_recipients(events: tuple[GameEvent, ...]) -> tuple[int, ...]:
    """The seats that took an Alliance token in ``events``, in order."""

    recipients: list[int] = []
    for event in events:
        if event.kind not in ("alliance_gained", "alliance_transferred"):
            continue
        to_player = dict(event.payload).get("to_player")
        if (
            isinstance(to_player, int)
            and not isinstance(to_player, bool)
            and to_player not in recipients
        ):
            recipients.append(to_player)
    return tuple(recipients)


def complete_alliance_contracts(result: RuleResult) -> RuleResult:
    """Complete Earn Any Alliance when its holder takes a new Alliance token.

    "Earn any Alliance is completed the next time you take an Alliance token
    you do not already have" [Bloodlines p. 2]. The engine runs this after
    each transition on the step's Alliance events, so the completion never
    interrupts the effect that moved the Influence, and a tile taken earlier
    in the same turn completes on a later bump of that turn (no placement
    snapshot applies: the condition is the Alliance itself, not an Agent
    visit). Troops recruited during the holder's own turn join that turn's
    deployment allowance like any other mid-turn recruit [Main p. 10]
    [FAQ p. 4].
    """

    state = result.state
    if not state.config.choam_module or not state.config.bloodlines:
        return result
    recipients = [
        player
        for player in alliance_recipients(result.events)
        if 0 <= player < state.config.players
    ]
    if not recipients:
        return result
    events = list(result.events)
    for player in recipients:
        for instance_id in state.players[player].active_contract_ids:
            condition = contract_for_instance(instance_id).condition
            if condition.kind is not ContractConditionKind.EARN_ALLIANCE:
                continue
            completion_source = (
                f"round:{state.round_number}:player:{player}:contract:{instance_id}"
            )
            completed = _complete_contract(
                state, player, instance_id, source=completion_source
            )
            state = _await_contract_reward(
                completed.state, player, instance_id, completion_source
            )
            events.extend(completed.events)
            if state.phase is GamePhase.FINISHED:
                # An Endgame Navigation card's Influence may take the token
                # in the step that finishes the game; no seat answers a
                # decision after that, so the reward is paid at once, in the
                # order the engine paid it in before stage B2.
                paid = _settle_finished_reward(state, player)
                state = paid.state
                events.extend(paid.events)
    return RuleResult(state=state, events=tuple(events))


def _settle_finished_reward(state: GameState, player: int) -> RuleResult:
    """Answer the reward window on top of a finished game in the older
    engine's order (Earn Any Alliance prints only automatic icons)."""

    depth = len(state.decision_stack)
    events: list[GameEvent] = []
    while (
        state.decision_stack
        and state.decision_stack[-1].kind == FrameKind.CONTRACT_REWARD_ICONS
    ):
        answer = legacy_contract_reward_icon(state, player)
        if answer is None:
            raise RuntimeError("a finished game's Contract reward has no row")
        paid = apply_contract_reward_icon(state, answer)
        state = paid.state
        events.extend(paid.events)
    if len(state.decision_stack) != depth - 1:
        raise RuntimeError("a finished game's Contract reward opened a choice")
    return RuleResult(state=state, events=tuple(events))

