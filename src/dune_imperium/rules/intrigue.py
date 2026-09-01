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
    AcquireCardUpTo,
    DeployFromGarrison,
    DestroyShieldWall,
    DiscardFromHand,
    EffectSection,
    FlipBattleCard,
    GainInfluence,
    IntrigueTiming,
    LoseInfluence,
    PlaceSpy,
    RecallSpy,
    RetreatTroops,
    SetAsideImperiumRowCard,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS_BY_INSTANCE,
    intrigue_card_for_instance,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.acquisition import (
    acquirable_imperium_instance_ids,
    acquirable_reserve_card_ids,
    acquire_imperium_for_intrigue,
    acquire_reserve_for_intrigue,
    acquisition_spy_frame,
    take_imperium_row_card,
)
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.combat import refresh_combat_participants
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effect_interpreter import (
    ChoiceSlot,
    applicable_sections,
    apply_rewards,
    automatic_rewards,
    choice_slots,
    condition_holds,
    cost_slots,
    flippable_battle_card_ids,
    option_is_playable,
    pay_cost,
    resource_cost,
    spy_placement_targets,
)
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    frame_context,
    owned_top_frame,
    replace_player,
    replace_top_frame,
    reveal_is_open_for,
    top_frame,
    with_context,
)
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    lose_faction_influence,
)
from dune_imperium.rules.reveal_turn import add_units_to_reveal
from dune_imperium.rules.shield_wall import destroy_shield_wall
from dune_imperium.rules.spy_placement import (
    observation_post_ids_for_factions,
    place_spy,
    recall_spy,
    solo_occupied_post_ids,
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
    """Return every Plot or Combat option ``player`` can currently play."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    frame = top_frame(state)
    if (
        frame is None
        or not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
    ):
        return ()
    if state.phase is GamePhase.PLAYER_TURNS and frame.kind in PLOT_FRAME_KINDS:
        timing = IntrigueTiming.PLOT
    elif state.phase is GamePhase.COMBAT and frame.kind == FrameKind.COMBAT_INTRIGUE:
        # Only the participant whose priority it is may play [Main p. 14].
        timing = IntrigueTiming.COMBAT
    elif (
        state.phase is GamePhase.ENDGAME
        and frame.kind == FrameKind.ENDGAME_INTRIGUE
    ):
        # Endgame Intrigue resolves in the owner's Endgame window
        # [Main pp. 7, 15].
        timing = IntrigueTiming.ENDGAME
    else:
        return ()
    owner = state.players[player]
    actions: list[DomainAction] = []
    for card_id in owner.intrigue_cards:
        entry = INTRIGUE_CARDS_BY_INSTANCE.get(card_id)
        if entry is None or not entry.play_data_complete:
            continue
        for index, option in enumerate(entry.options):
            if option.timing is not timing:
                continue
            if option_is_playable(state, player, option):
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
    sections = applicable_sections(
        state, player, option, shield_wall_present=state.shield_wall_present
    )
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

    if option.trigger is not None:
        # The effect does not apply yet: the card waits face up in front of
        # its owner until the trigger fires [FAQ p. 2].
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

    if choice_slots(sections, shield_wall_present=state.shield_wall_present):
        frame = DecisionFrame(
            kind=FrameKind.INTRIGUE_CHOICE,
            frame_id=f"{source}:choice",
            decision=PlayerDecision(owner=player, prompt="Resolve the Intrigue choice"),
            context=(
                ("card_id", card_id),
                ("chosen_factions", ""),
                ("option", option_index),
                ("sections", ",".join(str(index) for index in section_indexes)),
                ("shield_wall_at_play", state.shield_wall_present),
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
        case DestroyShieldWall():
            # The detonation icon is a choice [Main pp. 10, 20].
            actions.append(DomainAction(action_id="detonate_shield_wall", actor=player))
            actions.append(DomainAction(action_id="keep_shield_wall", actor=player))
        case DeployFromGarrison(up_to=up_to):
            actions.extend(
                DomainAction(
                    action_id="deploy_intrigue_troops",
                    actor=player,
                    arguments=(("count", count),),
                )
                for count in range(1, min(up_to, owner.troops_garrison) + 1)
            )
        case TrashPersonalCard():
            # The black trash icon is optional [Main p. 20].
            actions.append(
                DomainAction(action_id="decline_intrigue_trash", actor=player)
            )
            actions.extend(
                DomainAction(
                    action_id="trash_intrigue_card",
                    actor=player,
                    arguments=(("card_id", owned),),
                )
                for owned in (*owner.hand, *owner.discard_pile, *owner.in_play)
            )
        case RecallSpy():
            actions.extend(
                DomainAction(
                    action_id="recall_spy_for_intrigue",
                    actor=player,
                    arguments=(("post_id", post_id),),
                )
                for post_id in owner.spy_post_ids
            )
        case RetreatTroops(minimum=minimum, maximum=maximum):
            limit = (
                owner.troops_conflict
                if maximum is None
                else min(maximum, owner.troops_conflict)
            )
            actions.extend(
                DomainAction(
                    action_id="retreat_intrigue_troops",
                    actor=player,
                    arguments=(("count", count),),
                )
                for count in range(minimum, limit + 1)
            )
        case FlipBattleCard(icon=icon):
            actions.extend(
                DomainAction(
                    action_id="flip_battle_card",
                    actor=player,
                    arguments=(("card_id", conflict_id),),
                )
                for conflict_id in flippable_battle_card_ids(owner, icon)
            )
        case SetAsideImperiumRowCard():
            actions.extend(
                DomainAction(
                    action_id="manipulate_imperium_row",
                    actor=player,
                    arguments=(("instance_id", instance_id),),
                )
                for instance_id in state.imperium_row
            )
        case AcquireCardUpTo(max_cost=max_cost):
            actions.extend(
                DomainAction(
                    action_id="acquire_intrigue_reserve",
                    actor=player,
                    arguments=(("card_id", card_id),),
                )
                for card_id in acquirable_reserve_card_ids(state, max_cost)
            )
            actions.extend(
                DomainAction(
                    action_id="acquire_intrigue_imperium",
                    actor=player,
                    arguments=(("instance_id", instance_id),),
                )
                for instance_id in acquirable_imperium_instance_ids(state, max_cost)
            )
        case PlaceSpy():
            targets = spy_placement_targets(state, player, slot)
            if owner.spies_supply > 0:
                actions.extend(
                    DomainAction(
                        action_id="place_intrigue_spy",
                        actor=player,
                        arguments=(("post_id", post_id),),
                    )
                    for post_id in targets
                )
            else:
                # With an empty supply the owner may first recall one Spy
                # [Main pp. 11, 20]. Only recalls that keep the placement
                # reachable are offered: any Spy while a target post is
                # free, otherwise a Spy that is the sole occupant of an
                # allowed post (a shared post stays occupied).
                allowed_posts = (
                    observation_post_ids_for_factions(slot.factions)
                    if slot.factions is not None
                    else None
                )
                recallable = (
                    owner.spy_post_ids
                    if targets
                    else solo_occupied_post_ids(state, player, allowed_posts)
                )
                actions.extend(
                    DomainAction(
                        action_id="recall_spy_for_intrigue",
                        actor=player,
                        arguments=(("post_id", post_id),),
                    )
                    for post_id in recallable
                )
            # Placing the Spy is optional ("you may") [Main pp. 11, 20].
            actions.append(
                DomainAction(action_id="decline_intrigue_spy", actor=player)
            )
    sections = _sections(context)
    if (
        context.get("rewards_applied") is not True
        and context_int(context, "slot", owner=_CHOICE_FRAME)
        >= len(cost_slots(sections))
        and automatic_rewards(sections)
    ):
        # Icons on one Intrigue line are independent effects and the owner
        # picks their order (OQ-015), so once every arrow cost is paid the
        # pending automatic rewards may resolve before, between, or after
        # the remaining reward slots.
        actions.append(
            DomainAction(action_id="resolve_intrigue_rewards", actor=player)
        )
    return tuple(actions)


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
    # The frame is marked before the rewards apply so a draw that pushes a
    # reshuffle chance frame stacks on the already-updated frame, exactly
    # like the acquisition slot's advance-before-move pattern.
    context["rewards_applied"] = True
    advanced = replace_top_frame(state, with_context(frame, context))
    applied = _apply_section_rewards(
        advanced, action.actor, _sections(context), f"{source}:rewards"
    )
    return RuleResult(state=applied.state, events=applied.events)


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
        case AcquireCardUpTo():
            return _apply_intrigue_acquisition(
                state, frame, context, player, slot, action, step_source
            )
        case SetAsideImperiumRowCard():
            instance_id = str(arguments["instance_id"])
            imperium_row, imperium_deck = take_imperium_row_card(state, instance_id)
            owner = state.players[player]
            keeper = replace(
                owner,
                imperium_set_aside=(*owner.imperium_set_aside, instance_id),
            )
            result = RuleResult(
                state=replace(
                    state,
                    players=replace_player(state.players, keeper),
                    imperium_deck=imperium_deck,
                    imperium_row=imperium_row,
                ),
                events=(
                    GameEvent(
                        event_id=f"{step_source}:set_aside:{instance_id}",
                        kind="imperium_row_card_set_aside",
                        payload=(
                            ("card_id", imperium_card_for_instance(
                                instance_id
                            ).card.card_id),
                            ("instance_id", instance_id),
                            ("player", player),
                        ),
                    ),
                ),
            )
        case FlipBattleCard():
            flipped_id = str(arguments["card_id"])
            owner = state.players[player]
            flipped_owner = replace(
                owner,
                face_down_battle_card_ids=(
                    *owner.face_down_battle_card_ids,
                    flipped_id,
                ),
            )
            result = RuleResult(
                state=replace(
                    state, players=replace_player(state.players, flipped_owner)
                ),
                events=(
                    GameEvent(
                        event_id=f"{step_source}:flipped:{flipped_id}",
                        kind="battle_card_flipped",
                        payload=(("card_id", flipped_id), ("player", player)),
                    ),
                ),
            )
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
        case DestroyShieldWall():
            if action.action_id == "detonate_shield_wall":
                result = destroy_shield_wall(
                    state, event_id=f"{step_source}:shield_wall", source=source
                )
            else:
                result = RuleResult(
                    state=state,
                    events=(
                        GameEvent(
                            event_id=f"{step_source}:shield_wall_kept",
                            kind="shield_wall_kept",
                            payload=(("player", player),),
                        ),
                    ),
                )
        case DeployFromGarrison():
            count = arguments["count"]
            assert isinstance(count, int)
            result = _deploy_units(state, player, step_source, troops=count)
        case TrashPersonalCard():
            if action.action_id == "decline_intrigue_trash":
                result = RuleResult(
                    state=state,
                    events=(
                        GameEvent(
                            event_id=f"{step_source}:trash_declined",
                            kind="intrigue_trash_declined",
                            payload=(("player", player),),
                        ),
                    ),
                )
            else:
                result = trash_personal_card(
                    state, player, str(arguments["card_id"]), source=step_source
                )
        case RetreatTroops():
            count = arguments["count"]
            assert isinstance(count, int)
            result = _retreat_units(state, player, step_source, troops=count)
        case PlaceSpy() if action.action_id == "decline_intrigue_spy":
            # The Spy placement is optional [Main pp. 11, 20].
            result = RuleResult(
                state=state,
                events=(
                    GameEvent(
                        event_id=f"{step_source}:spy_declined",
                        kind="intrigue_spy_declined",
                        payload=(("player", player),),
                    ),
                ),
            )
        case RecallSpy() | PlaceSpy():
            post_id = str(arguments["post_id"])
            owner = state.players[player]
            if action.action_id == "recall_spy_for_intrigue":
                next_owner = recall_spy(owner, post_id)
                kind = "spy_recalled"
            else:
                next_owner = place_spy(owner, post_id)
                kind = "spy_placed"
            result = RuleResult(
                state=replace(state, players=replace_player(state.players, next_owner)),
                events=(
                    GameEvent(
                        event_id=f"{step_source}:{kind}:{post_id}",
                        kind=kind,
                        payload=(("player", player), ("post_id", post_id)),
                    ),
                ),
            )
            if isinstance(slot, PlaceSpy) and kind == "spy_recalled":
                # The recall only prepared the placement; stay on this slot.
                next_state = replace_top_frame(result.state, frame)
                return RuleResult(state=next_state, events=result.events)
        case _:
            raise RuntimeError("Intrigue choice frame has an unsupported slot")

    context["slot"] = slot_index + 1
    next_state = replace_top_frame(result.state, with_context(frame, context))
    if slot_index + 1 < len(_slots(context)):
        return RuleResult(state=next_state, events=result.events)

    finished = _finish_play(
        next_state.pop_decision(),
        player,
        card_id,
        _sections(context),
        source,
        skip_rewards=context.get("rewards_applied") is True,
    )
    return RuleResult(
        state=finished.state,
        events=(*result.events, *finished.events),
    )


def _apply_intrigue_acquisition(
    state: GameState,
    frame: DecisionFrame,
    context: dict[str, ActionValue],
    player: int,
    slot: AcquireCardUpTo,
    action: DomainAction,
    step_source: str,
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
    slot_index = context_int(context, "slot", owner=_CHOICE_FRAME)
    # "Put that card in your hand" overrides the discard destination only
    # while its printed condition holds at resolution time.
    to_hand = slot.to_hand_if is not None and condition_holds(
        state, player, slot.to_hand_if
    )
    context["slot"] = slot_index + 1
    advanced = replace_top_frame(state, with_context(frame, context))
    arguments = dict(action.arguments)
    if action.action_id == "acquire_intrigue_reserve":
        acquired = acquire_reserve_for_intrigue(
            advanced,
            player,
            str(arguments["card_id"]),
            to_hand=to_hand,
            source=step_source,
        )
    else:
        acquired = acquire_imperium_for_intrigue(
            advanced,
            player,
            str(arguments["instance_id"]),
            to_hand=to_hand,
            source=step_source,
        )
    next_state = acquired.result.state
    events = acquired.result.events
    top = top_frame(next_state)
    if top is None or top.frame_id != frame.frame_id:
        raise RuntimeError("Intrigue acquisition buried its choice frame")
    if slot_index + 1 >= len(_slots(context)):
        finished = _finish_play(
            next_state.pop_decision(),
            player,
            card_id,
            _sections(context),
            source,
            skip_rewards=context.get("rewards_applied") is True,
        )
        next_state = finished.state
        events = (*events, *finished.events)
    if acquired.places_spy:
        next_state = next_state.push_decision(
            acquisition_spy_frame(next_state, player, acquired.instance_id)
        )
    elif acquired.takes_contract:
        contracts = begin_contract_gain(
            next_state, player, 1, source=f"{step_source}:acquisition_bonus"
        )
        next_state = contracts.state
        events = (*events, *contracts.events)
    return RuleResult(state=next_state, events=events)


def _apply_section_rewards(
    state: GameState,
    player: int,
    sections: tuple[EffectSection, ...],
    source: str,
) -> RuleResult:
    """Apply the sections' automatic rewards and their turn bookkeeping."""

    outcome = apply_rewards(
        state, player, automatic_rewards(sections), source=source
    )
    next_state = outcome.result.state
    events: list[GameEvent] = list(outcome.result.events)
    if outcome.troops_recruited:
        next_state = _update_agent_turn_frame(
            next_state, troops_recruited=outcome.troops_recruited
        )
    if outcome.sandworms_deployed and reveal_is_open_for(next_state, player):
        # The interpreter moved the sandworms; during a Reveal turn their
        # strength must also join the revealed total [Main p. 13].
        owner = next_state.players[player]
        rolled_back = replace(
            next_state,
            players=replace_player(
                next_state.players,
                replace(
                    owner,
                    sandworms_conflict=owner.sandworms_conflict
                    - outcome.sandworms_deployed,
                ),
            ),
        )
        counted = add_units_to_reveal(
            rolled_back, player, sandworms=outcome.sandworms_deployed
        )
        next_state = counted.state
        events.extend(counted.events)
    elif outcome.sandworms_deployed:
        # A summoned sandworm is immediately deployed [Main p. 20], so it
        # joins the owner's per-turn deployment count.
        owner = next_state.players[player]
        next_state = replace(
            next_state,
            players=replace_player(
                next_state.players,
                replace(
                    owner,
                    units_deployed_turn=owner.units_deployed_turn
                    + outcome.sandworms_deployed,
                ),
            ),
        )
    return RuleResult(state=next_state, events=tuple(events))


def _finish_play(
    state: GameState,
    player: int,
    card_id: str,
    sections: tuple[EffectSection, ...],
    source: str,
    *,
    skip_rewards: bool = False,
) -> RuleResult:
    """Apply pending automatic rewards, discard the card, and update turns.

    ``skip_rewards`` marks that the owner already resolved the automatic
    rewards mid-frame at a point of their choosing (OQ-015).
    """

    applied = (
        RuleResult(state=state)
        if skip_rewards
        else _apply_section_rewards(state, player, sections, source)
    )
    resolved = applied.state
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
    next_state = refresh_combat_participants(_reset_combat_passes(next_state))
    return RuleResult(state=next_state, events=applied.events)


def _retreat_units(
    state: GameState,
    player: int,
    step_source: str,
    *,
    troops: int,
) -> RuleResult:
    """Return Conflict troops to the garrison, adjusting Combat strength.

    Each troop carried two strength; a player left without units keeps no
    strength at all [Main pp. 12, 14].
    """

    owner = state.players[player]
    if troops < 1 or owner.troops_conflict < troops:
        raise RuntimeError("Intrigue retreat exceeds the troops in the Conflict")
    remaining_units = owner.troops_conflict - troops + owner.sandworms_conflict
    next_strength = (
        max(owner.combat_strength - 2 * troops, 0) if remaining_units else 0
    )
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison + troops,
        troops_conflict=owner.troops_conflict - troops,
        combat_strength=next_strength,
    )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, next_owner)),
        events=(
            GameEvent(
                event_id=f"{step_source}:retreat",
                kind="troops_retreated",
                payload=(("count", troops), ("player", player)),
            ),
        ),
    )


def _reset_combat_passes(state: GameState) -> GameState:
    """A played Combat Intrigue restarts the consecutive-pass count [Main p. 14]."""

    frame = top_frame(state)
    if frame is None or frame.kind != FrameKind.COMBAT_INTRIGUE:
        return state
    context = frame_context(frame)
    if context.get("consecutive_passes") == 0:
        return state
    context["consecutive_passes"] = 0
    return replace_top_frame(state, with_context(frame, context))


def _deploy_units(
    state: GameState,
    player: int,
    step_source: str,
    *,
    troops: int,
) -> RuleResult:
    """Move garrison troops into the Conflict, counting strength mid-Reveal."""

    owner = state.players[player]
    if troops < 1 or owner.troops_garrison < troops:
        raise RuntimeError("Intrigue deployment exceeds the garrison")
    event = GameEvent(
        event_id=f"{step_source}:deploy",
        kind="troops_deployed",
        payload=(("count", troops), ("player", player)),
    )
    if reveal_is_open_for(state, player):
        counted = add_units_to_reveal(state, player, troops=troops)
        return RuleResult(state=counted.state, events=(event, *counted.events))
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison - troops,
        troops_conflict=owner.troops_conflict + troops,
        units_deployed_turn=owner.units_deployed_turn + troops,
    )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, next_owner)),
        events=(event,),
    )


def _sections(context: dict[str, ActionValue]) -> tuple[EffectSection, ...]:
    card_id = context_str(context, "card_id", owner=_CHOICE_FRAME)
    option_index = context_int(context, "option", owner=_CHOICE_FRAME)
    option = intrigue_card_for_instance(card_id).options[option_index]
    raw = context_str(context, "sections", owner=_CHOICE_FRAME)
    return tuple(option.sections[int(index)] for index in raw.split(",") if index)


def _slots(context: dict[str, ActionValue]) -> tuple[ChoiceSlot, ...]:
    wall = context.get("shield_wall_at_play", True)
    return choice_slots(_sections(context), shield_wall_present=wall is True)


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
) -> GameState:
    """Keep the owner's turn bookkeeping in step with an Intrigue effect.

    Troops recruited during the owner's turn join that turn's deployment
    allowance whether the Plot was played before or after placing the Agent.
    Spice paid for the card is recorded as spent so that Harvest Spice
    Contracts, which count Spice gained from every source during the turn
    [Main p. 16], still see the full amount gained; Spice the card grants
    counts toward those Contracts like any other gain.
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
