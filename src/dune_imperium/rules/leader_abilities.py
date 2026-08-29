"""Leader ability and Signet Ring resolution for implemented Leaders.

Each Leader prints two abilities: the left one is used at the time written on
the card, and the Signet Ring ability fires when the Signet Ring starting card
is played on an Agent turn [Main pp. 6, 20]. Ability text is transcribed from
the card images referenced by ``content/uprising/leaders.py``; behaviour is
keyed by ``leader_id`` here so that setup keeps working for Leaders whose
abilities are not implemented yet — their Signet Ring placements stay withheld
through ``leader_signet_is_implemented``.
"""

from dataclasses import replace
from typing import Final

from dune_imperium.content.uprising.leaders import (
    FEYD_TRACK_BY_ID,
    FeydTrackReward,
)
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
    recruit_troops,
)
from dune_imperium.rules.frames import FrameKind, owned_top_frame, replace_player
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.reveal_turn import (
    add_reveal_optional_sword_strength,
    add_reveal_persuasion,
    add_reveal_strength,
)
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    place_spy,
    recall_spy,
)

# Leaders whose ability and Signet Ring behaviour is fully implemented. The
# dispatcher withholds Signet Ring placements for every other Leader so that
# each advertised action stays executable.
IMPLEMENTED_ABILITY_LEADER_IDS: Final = frozenset(
    {
        "feyd_rautha_harkonnen",
        "gurney_halleck",
        "lady_amber_metulli",
        "lady_jessica",
    }
)

# Always Smiling grants its Persuasion at six or more strength in the
# four-player game; the printed asterisk raises that to ten only in a
# six-player game [Gurney Halleck card].
ALWAYS_SMILING_STRENGTH: Final = 6


def leader_signet_is_implemented(leader_id: str | None) -> bool:
    """Return whether this Leader's Signet Ring ability can be resolved."""

    return leader_id in IMPLEMENTED_ABILITY_LEADER_IDS


def resolve_leader_signet(state: GameState) -> RuleResult:
    """Resolve the current player's Signet Ring ability [Main pp. 6, 20]."""

    _, context = current_agent_effect_context(state)
    if context.get("pending_agent_effect") is not True:
        raise ValueError("the current Agent turn has no pending card effect")
    player = context.get("turn_owner")
    card_id = context.get("card_id")
    if (
        isinstance(player, bool)
        or not isinstance(player, int)
        or not isinstance(card_id, str)
    ):
        raise RuntimeError("Agent-turn effect frame has invalid subject")
    owner = state.players[player]
    source = f"round:{state.round_number}:player:{player}:leader_signet"

    payload: tuple[tuple[str, ActionValue], ...]
    if owner.leader_id == "gurney_halleck":
        # Warmaster: recruit one troop [Gurney Halleck card]. A troop recruited
        # while visiting a Combat space stays deployable [FAQ p. 4].
        next_owner, recruited = recruit_troops(owner, 1)
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        payload = (("card_id", card_id), ("player", player), ("troops", recruited))
    elif owner.leader_id == "lady_amber_metulli":
        # Fill Coffers: gain one Solari, and one Spice while holding any
        # Faction Alliance [Lady Amber Metulli card].
        spice = 1 if owner.alliance_faction_ids else 0
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + 1,
                spice=owner.resources.spice + spice,
            ),
        )
        payload = (
            ("card_id", card_id),
            ("player", player),
            ("solari", 1),
            ("spice", spice),
        )
    elif owner.leader_id == "feyd_rautha_harkonnen":
        # Reached only when the Personal Training provider offers no choice:
        # the token already sits on the rightmost space, where it remains for
        # the rest of the game [Main p. 17], so there is no new space whose
        # reward could be earned. An active stage always has at least one
        # choice — a trash stage can decline, and a Spy stage always finds an
        # empty observation post because the thirteen posts outnumber the
        # twelve Spies.
        if legal_feyd_track_actions(state, player):
            raise RuntimeError("Personal Training requires a player choice")
        if isinstance(context.get("feyd_track_stage"), str):
            raise RuntimeError("Personal Training stage lost its choices")
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(state, context, state.players)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=source,
                    kind="agent_card_effect_unavailable",
                    payload=(("card_id", card_id), ("player", player)),
                ),
            ),
        )
    else:
        raise RuntimeError("this Leader's Signet Ring ability is not implemented")

    context["pending_agent_effect"] = False
    next_state = advance_after_effect(
        state,
        context,
        replace_player(state.players, next_owner),
    )
    event = GameEvent(
        event_id=source,
        kind="leader_signet_resolved",
        payload=payload,
    )
    return RuleResult(state=next_state, events=(event,))


def _feyd_signet_context(
    state: GameState,
    player: int,
) -> dict[str, ActionValue] | None:
    """Return the effect-frame context while Feyd's Signet Ring is pending."""

    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    if context.get("pending_agent_effect") is not True:
        return None
    card_id = context.get("card_id")
    if not isinstance(card_id, str) or (
        personal_card_for_instance(card_id).agent_effect
        is not PersonalCardAgentEffect.LEADER_SIGNET
    ):
        return None
    if state.players[player].leader_id != "feyd_rautha_harkonnen":
        return None
    return context


def legal_feyd_track_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Personal Training's advance and stage choices."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    context = _feyd_signet_context(state, player)
    if context is None:
        return ()
    owner = state.players[player]
    stage_id = context.get("feyd_track_stage")
    if isinstance(stage_id, str):
        stage = FEYD_TRACK_BY_ID[stage_id]
        if stage.reward in (
            FeydTrackReward.PAY_SOLARI_TO_TRASH,
            FeydTrackReward.OPTIONAL_TRASH,
        ):
            # The trash icon targets a card in hand, discard pile, or in play
            # [Main p. 20]; the paid space additionally needs its one Solari.
            can_trash = (
                stage.reward is FeydTrackReward.OPTIONAL_TRASH
                or owner.resources.solari >= 1
            )
            return (
                DomainAction(action_id="decline_leader_card_trash", actor=player),
                *(
                    (
                        DomainAction(
                            action_id="trash_leader_card",
                            actor=player,
                            arguments=(("card_id", card_id),),
                        )
                        for card_id in (
                            *owner.hand,
                            *owner.discard_pile,
                            *owner.in_play,
                        )
                    )
                    if can_trash
                    else ()
                ),
            )
        # Spy stages place from supply on an empty observation post, first
        # recalling a Spy for no effect when the supply is empty
        # [Main pp. 11, 20].
        if context.get("feyd_spy_recalled") is True or owner.spies_supply > 0:
            return tuple(
                DomainAction(
                    action_id="place_leader_spy",
                    actor=player,
                    arguments=(("post_id", post_id),),
                )
                for post_id in empty_observation_post_ids(state)
            )
        return tuple(
            DomainAction(
                action_id="recall_spy_for_leader_placement",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in owner.spy_post_ids
        )
    current = FEYD_TRACK_BY_ID[owner.feyd_track_space]
    return tuple(
        DomainAction(
            action_id="advance_feyd_track",
            actor=player,
            arguments=(("space_id", next_space_id),),
        )
        for next_space_id in current.next_space_ids
    )


def apply_feyd_track_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve one Personal Training advance or stage choice."""

    if action not in legal_feyd_track_actions(state, action.actor):
        raise ValueError("action is not a legal Personal Training choice")
    _, context = current_agent_effect_context(state)
    player = action.actor
    owner = state.players[player]
    arguments = dict(action.arguments)
    source = f"round:{state.round_number}:player:{player}:leader_signet"

    if action.action_id == "advance_feyd_track":
        target_id = arguments.get("space_id")
        if not isinstance(target_id, str):
            raise RuntimeError("Personal Training advance has invalid space ID")
        target = FEYD_TRACK_BY_ID[target_id]
        moved_owner = replace(owner, feyd_track_space=target_id)
        events = [
            GameEvent(
                event_id=f"{source}:advance:{target_id}",
                kind="feyd_token_advanced",
                payload=(
                    ("from_space", owner.feyd_track_space),
                    ("player", player),
                    ("to_space", target_id),
                ),
            )
        ]
        if target.reward is FeydTrackReward.GAIN_TWO_SPICE:
            moved_owner = replace(
                moved_owner,
                resources=replace(
                    moved_owner.resources,
                    spice=moved_owner.resources.spice + 2,
                ),
            )
            context["pending_agent_effect"] = False
            events.append(
                GameEvent(
                    event_id=source,
                    kind="leader_signet_resolved",
                    payload=(("player", player), ("spice", 2)),
                )
            )
        elif target.reward is FeydTrackReward.TROOP_AND_SPY:
            moved_owner, recruited = recruit_troops(moved_owner, 1)
            previous = context.get("troops_recruited")
            if isinstance(previous, bool) or not isinstance(previous, int):
                raise RuntimeError(
                    "Agent-turn effect frame has invalid recruit count"
                )
            context["troops_recruited"] = previous + recruited
            context["feyd_track_stage"] = target_id
            events.append(
                GameEvent(
                    event_id=f"{source}:troops",
                    kind="leader_signet_troops_recruited",
                    payload=(("player", player), ("troops", recruited)),
                )
            )
        else:
            context["feyd_track_stage"] = target_id
        next_state = advance_after_effect(
            state,
            context,
            replace_player(state.players, moved_owner),
        )
        return RuleResult(state=next_state, events=tuple(events))

    if action.action_id == "decline_leader_card_trash":
        context.pop("feyd_track_stage")
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(state, context, state.players)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:trash_declined",
                    kind="leader_card_trash_declined",
                    payload=(("player", player),),
                ),
            ),
        )

    if action.action_id == "trash_leader_card":
        stage_id = context.get("feyd_track_stage")
        if not isinstance(stage_id, str):
            raise RuntimeError("Personal Training trash has no active stage")
        card_id = arguments.get("card_id")
        if not isinstance(card_id, str):
            raise RuntimeError("Personal Training trash has invalid card ID")
        events = []
        working = state
        if FEYD_TRACK_BY_ID[stage_id].reward is FeydTrackReward.PAY_SOLARI_TO_TRASH:
            if owner.resources.solari < 1:
                raise RuntimeError("Personal Training trash requires one Solari")
            paid_owner = replace(
                owner,
                resources=replace(
                    owner.resources,
                    solari=owner.resources.solari - 1,
                ),
            )
            working = replace(
                state,
                players=replace_player(state.players, paid_owner),
            )
            events.append(
                GameEvent(
                    event_id=f"{source}:solari_paid",
                    kind="leader_signet_solari_paid",
                    payload=(("amount", 1), ("player", player)),
                )
            )
        trashed = trash_personal_card(
            working,
            player,
            card_id,
            source=source,
        )
        context.pop("feyd_track_stage")
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(
            trashed.state,
            context,
            trashed.state.players,
        )
        return RuleResult(
            state=next_state,
            events=(*events, *trashed.events),
        )

    post_id = arguments.get("post_id")
    if not isinstance(post_id, str):
        raise RuntimeError("Personal Training Spy choice has invalid post ID")
    if action.action_id == "recall_spy_for_leader_placement":
        next_owner = recall_spy(owner, post_id)
        context["feyd_spy_recalled"] = True
        context["spy_recalled_this_turn"] = True
        next_state = advance_after_effect(
            state,
            context,
            replace_player(state.players, next_owner),
        )
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:spy_recalled:{post_id}",
                    kind="spy_recalled",
                    payload=(
                        ("player", player),
                        ("post_id", post_id),
                        ("source", "leader_signet"),
                    ),
                ),
            ),
        )

    next_owner = place_spy(owner, post_id)
    context.pop("feyd_track_stage")
    context.pop("feyd_spy_recalled", None)
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(
        state,
        context,
        replace_player(state.players, next_owner),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:spy_placed:{post_id}",
                kind="spy_placed",
                payload=(
                    ("player", player),
                    ("post_id", post_id),
                    ("source", "leader_signet"),
                ),
            ),
        ),
    )


def legal_leader_signet_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Lady Jessica's optional one-Spice Signet Ring payment.

    Spice Agony and Water of Life are both arrow effects that spend one Spice
    [Lady Jessica card] [Reverend Mother Jessica card]; the payment choice is
    judged when the Signet Ring resolves, so it never advertises an
    unaffordable payment.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_agent_effect") is not True:
        return ()
    card_id = context.get("card_id")
    if not isinstance(card_id, str) or (
        personal_card_for_instance(card_id).agent_effect
        is not PersonalCardAgentEffect.LEADER_SIGNET
    ):
        return ()
    owner = state.players[player]
    if owner.leader_id != "lady_jessica":
        return ()
    return (
        DomainAction(action_id="decline_leader_signet_payment", actor=player),
        *(
            (DomainAction(action_id="pay_leader_signet_spice", actor=player),)
            if owner.resources.spice >= 1
            else ()
        ),
    )


def apply_leader_signet_payment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Pay or decline the one-Spice Signet Ring ability of Jessica's faces."""

    if action not in legal_leader_signet_actions(state, action.actor):
        raise ValueError("action is not a legal Leader Signet payment choice")
    _, context = current_agent_effect_context(state)
    player = action.actor
    owner = state.players[player]
    source = f"round:{state.round_number}:player:{player}:leader_signet"
    context["pending_agent_effect"] = False

    if action.action_id == "decline_leader_signet_payment":
        next_state = advance_after_effect(state, context, state.players)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="leader_signet_payment_declined",
                    payload=(("player", player),),
                ),
            ),
        )

    if owner.resources.spice < 1:
        raise RuntimeError("the Signet Ring payment requires one Spice")
    previous_spent = context.get("spice_spent_after_placement", 0)
    if isinstance(previous_spent, bool) or not isinstance(previous_spent, int):
        raise RuntimeError("Agent-turn effect frame has invalid Spice spending")
    context["spice_spent_after_placement"] = previous_spent + 1
    next_owner = replace(
        owner,
        resources=replace(owner.resources, spice=owner.resources.spice - 1),
        spice_spent_turn=owner.spice_spent_turn + 1,
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:spice_paid",
            kind="leader_signet_spice_paid",
            payload=(("amount", 1), ("player", player)),
        )
    ]

    if owner.leader_face_id == "reverend_mother_jessica":
        # Water of Life: one Spice buys one water [Reverend Mother Jessica
        # card].
        next_owner = replace(
            next_owner,
            resources=replace(
                next_owner.resources,
                water=next_owner.resources.water + 1,
            ),
        )
        next_state = advance_after_effect(
            state,
            context,
            replace_player(state.players, next_owner),
        )
        events.append(
            GameEvent(
                event_id=source,
                kind="leader_signet_resolved",
                payload=(("player", player), ("water", 1)),
            )
        )
        return RuleResult(state=next_state, events=tuple(events))

    # Spice Agony: draw one Intrigue card and move a troop from the supply to
    # the Bene Gesserit area of the board, where it is now a memory
    # [Lady Jessica card]. With no troop left in the supply only the troop
    # part is lost.
    memories_gained = 1 if next_owner.troops_supply >= 1 else 0
    next_owner = replace(
        next_owner,
        troops_supply=next_owner.troops_supply - memories_gained,
        memories=next_owner.memories + memories_gained,
    )
    working = replace(state, players=replace_player(state.players, next_owner))
    intrigue_draw = draw_or_queue_intrigue_cards(
        working,
        player,
        1,
        source=f"{source}:intrigue_draw",
    )
    next_state = advance_after_effect(
        intrigue_draw.state,
        context,
        intrigue_draw.state.players,
    )
    events.append(
        GameEvent(
            event_id=source,
            kind="leader_signet_resolved",
            payload=(("memories", memories_gained), ("player", player)),
        )
    )
    return RuleResult(
        state=next_state,
        events=(*events, *intrigue_draw.events),
    )


def legal_leader_placement_ability_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Other Memories' use-or-decline choice after a placement."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_leader_ability") is not True:
        return ()
    return (
        DomainAction(action_id="use_other_memories", actor=player),
        DomainAction(action_id="decline_other_memories", actor=player),
    )


def apply_leader_placement_ability(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Use or decline Other Memories on a Bene Gesserit placement.

    Using it returns every memory to the supply, draws one card per memory,
    and flips the Leader to Reverend Mother Jessica [Lady Jessica card]. The
    Reverend Mother ability may then be used on this same turn [FAQ p. 3], so
    the flip opens the paid board-repeat window for the visited space.
    """

    if action not in legal_leader_placement_ability_actions(state, action.actor):
        raise ValueError("action is not a legal Leader placement ability choice")
    _, context = current_agent_effect_context(state)
    player = action.actor
    context["pending_leader_ability"] = False
    source = f"round:{state.round_number}:player:{player}:other_memories"

    if action.action_id == "decline_other_memories":
        next_state = advance_after_effect(state, context, state.players)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="leader_ability_declined",
                    payload=(("player", player),),
                ),
            ),
        )

    owner = state.players[player]
    memories = owner.memories
    next_owner = replace(
        owner,
        troops_supply=owner.troops_supply + memories,
        memories=0,
        leader_face_id="reverend_mother_jessica",
    )
    context["pending_leader_board_repeat"] = True
    next_state = advance_after_effect(
        state,
        context,
        replace_player(state.players, next_owner),
    )
    flip_event = GameEvent(
        event_id=source,
        kind="leader_flipped",
        payload=(
            ("leader_face_id", "reverend_mother_jessica"),
            ("memories_returned", memories),
            ("player", player),
        ),
    )
    if memories == 0:
        return RuleResult(state=next_state, events=(flip_event,))
    draw = draw_or_request_personal_cards(
        next_state,
        player,
        memories,
        source=f"{source}:draw",
    )
    return RuleResult(state=draw.state, events=(flip_event, *draw.events))


def legal_leader_board_repeat_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Reverend Mother's paid repeat of the visited space's effects.

    The repeat choice waits until the printed board effect has resolved once,
    then offers spending one water to repeat it [Reverend Mother Jessica
    card]. The Agent-send Influence is a Faction rule, not a printed space
    effect [Main p. 7], so it is not repeated.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("pending_leader_board_repeat") is not True:
        return ()
    if context.get("pending_board_effect") is True:
        return ()
    owner = state.players[player]
    return (
        DomainAction(action_id="decline_leader_board_repeat", actor=player),
        *(
            (DomainAction(action_id="pay_leader_board_repeat", actor=player),)
            if owner.resources.water >= 1
            else ()
        ),
    )


def apply_leader_board_repeat(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Pay one water to repeat the printed space effects, or decline."""

    if action not in legal_leader_board_repeat_actions(state, action.actor):
        raise ValueError("action is not a legal Leader board-repeat choice")
    _, context = current_agent_effect_context(state)
    player = action.actor
    context["pending_leader_board_repeat"] = False
    source = f"round:{state.round_number}:player:{player}:leader_board_repeat"

    if action.action_id == "decline_leader_board_repeat":
        next_state = advance_after_effect(state, context, state.players)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="leader_ability_declined",
                    payload=(("player", player),),
                ),
            ),
        )

    owner = state.players[player]
    if owner.resources.water < 1:
        raise RuntimeError("the board repeat requires one water")
    next_owner = replace(
        owner,
        resources=replace(owner.resources, water=owner.resources.water - 1),
    )
    context["pending_board_effect"] = True
    # Per-resolution markers of the first pass must not leak into the repeat.
    context.pop("espionage_spy_recalled", None)
    next_state = advance_after_effect(
        state,
        context,
        replace_player(state.players, next_owner),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=source,
                kind="leader_board_repeat_paid",
                payload=(
                    ("player", player),
                    ("space_id", context.get("space_id", "")),
                    ("water", 1),
                ),
            ),
        ),
    )


def legal_leader_reveal_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Leader abilities usable during the owner's open Reveal turn."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    frame = owned_top_frame(state, FrameKind.REVEAL, player)
    if frame is None:
        return ()
    if dict(frame.context).get("leader_reveal_ability_used") is True:
        return ()
    owner = state.players[player]
    if owner.leader_id == "lady_amber_metulli" and owner.troops_conflict >= 1:
        # Desert Scouts: "Reveal Turn: You may retreat one of your troops."
        return (DomainAction(action_id="retreat_leader_troop", actor=player),)
    if owner.leader_id == "feyd_rautha_harkonnen" and owner.spy_post_ids:
        # Devious Strength: "Reveal Turn: recall one of your Spies for two
        # swords" — an arrow cost usable once per Reveal turn [Main p. 20]
        # [FAQ p. 3].
        return tuple(
            DomainAction(
                action_id="recall_spy_for_leader",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in owner.spy_post_ids
        )
    return ()


def apply_leader_reveal_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve one optional Reveal-turn Leader ability."""

    if action not in legal_leader_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal-turn Leader ability")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["leader_reveal_ability_used"] = True
    owner = state.players[action.actor]
    source = f"round:{state.round_number}:player:{action.actor}:leader_reveal"
    decision_stack = (
        *state.decision_stack[:-1],
        replace(frame, context=tuple(sorted(context.items()))),
    )

    if action.action_id == "recall_spy_for_leader":
        # Devious Strength: the recalled Spy pays for two swords; like other
        # sword bonuses they only count while units are in the Conflict
        # [Main pp. 12-13].
        post_id = dict(action.arguments).get("post_id")
        if not isinstance(post_id, str):
            raise RuntimeError("Devious Strength has an invalid post ID")
        counted = 2 if owner.troops_conflict + owner.sandworms_conflict else 0
        next_owner = replace(
            recall_spy(owner, post_id),
            combat_strength=owner.combat_strength + counted,
        )
        decision_stack = add_reveal_optional_sword_strength(decision_stack, 2)
        if counted:
            decision_stack = add_reveal_strength(decision_stack, counted)
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, next_owner),
                decision_stack=decision_stack,
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:spy_recalled:{post_id}",
                    kind="spy_recalled",
                    payload=(
                        ("player", action.actor),
                        ("post_id", post_id),
                        ("source", "devious_strength"),
                    ),
                ),
                GameEvent(
                    event_id=f"{source}:strength",
                    kind="reveal_strength_gained",
                    payload=(("amount", 2), ("player", action.actor)),
                ),
            ),
        )

    # Desert Scouts retreats one troop from the Conflict to the garrison
    # [Main p. 20]. Without remaining units the revealed swords stop counting.
    remaining_units = owner.troops_conflict - 1 + owner.sandworms_conflict
    next_strength = owner.combat_strength - 2 if remaining_units else 0
    strength_delta = next_strength - owner.combat_strength
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison + 1,
        troops_conflict=owner.troops_conflict - 1,
        combat_strength=next_strength,
    )
    if strength_delta:
        decision_stack = add_reveal_strength(decision_stack, strength_delta)
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=decision_stack,
        ),
        events=(
            GameEvent(
                event_id=f"{source}:troops_retreated",
                kind="troops_retreated",
                payload=(("count", 1), ("player", action.actor)),
            ),
        ),
    )


def grant_leader_reveal_passives(result: RuleResult) -> RuleResult:
    """Apply automatic Reveal-turn Leader abilities after a transition.

    Always Smiling: during Gurney Halleck's Reveal turn, once his strength in
    the Conflict reaches six or more, he gains one Persuasion [Gurney Halleck
    card]. The grant fires the first time the condition holds and is recorded
    in the Reveal frame so it cannot repeat within the same Reveal turn.
    """

    state = result.state
    for frame in reversed(state.decision_stack):
        if frame.kind != FrameKind.REVEAL:
            continue
        if not isinstance(frame.decision, PlayerDecision):
            return result
        context = dict(frame.context)
        if context.get("leader_persuasion_granted") is True:
            return result
        owner = state.players[frame.decision.owner]
        if owner.leader_id != "gurney_halleck":
            return result
        if owner.combat_strength < ALWAYS_SMILING_STRENGTH:
            return result
        stack = tuple(
            replace(
                candidate,
                context=tuple(
                    sorted({**dict(candidate.context),
                            "leader_persuasion_granted": True}.items())
                ),
            )
            if candidate is frame
            else candidate
            for candidate in state.decision_stack
        )
        stack = add_reveal_persuasion(stack, 1)
        event = GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{frame.decision.owner}:"
                "leader_reveal:persuasion"
            ),
            kind="reveal_persuasion_gained",
            payload=(
                ("amount", 1),
                ("leader_id", "gurney_halleck"),
                ("player", frame.decision.owner),
            ),
        )
        return RuleResult(
            state=replace(state, decision_stack=stack),
            events=(*result.events, event),
        )
    return result
