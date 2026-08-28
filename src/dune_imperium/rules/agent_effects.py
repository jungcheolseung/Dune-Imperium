"""Resolution of starting-card and Faction Agent-turn effects."""

from dataclasses import replace

from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import (
    PersonalCardAgentEffect,
    PersonalCardTrashEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_bonds import has_faction_bond
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
    recruit_troops,
)
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    observation_post_ids_for_factions,
    place_spy,
    recall_spy,
)

_LONG_LIVE_SELECTION_STARTED = "long_live_fighters_selection_started"
_LONG_LIVE_DRAW_CARD_ID = "long_live_fighters_draw_card_id"
_LONG_LIVE_DRAW_ACTION_ID = "select_long_live_fighters_draw"
_LONG_LIVE_DISCARD_ACTION_ID = "select_long_live_fighters_discard"


def legal_agent_card_discard_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional hand-discard choices for the current Agent card."""

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
    _, source_card_id, _ = _effect_subject(context)
    source_card = personal_card_for_instance(source_card_id)
    effect = source_card.agent_effect
    if effect not in (
        PersonalCardAgentEffect.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD,
        PersonalCardAgentEffect.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD,
        PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD,
        PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD,
        PersonalCardAgentEffect.MAY_DISCARD_TO_TAKE_CONTRACT,
    ):
        return ()
    may_pay = (
        effect
        is not PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD
        or bool(state.intrigue_deck)
    )
    return (
        *(
            (DomainAction(action_id="decline_agent_card_discard", actor=player),)
            if effect
            in (
                PersonalCardAgentEffect.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD,
                PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD,
                PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD,
                PersonalCardAgentEffect.MAY_DISCARD_TO_TAKE_CONTRACT,
            )
            else ()
        ),
        *(
            DomainAction(
                action_id="discard_agent_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in state.players[player].hand
            if may_pay
            and not (
                effect
                is (
                    PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD
                )
                and Faction.SPACING_GUILD
                in personal_card_for_instance(card_id).factions
                and not state.intrigue_deck
            )
        ),
    )


def apply_agent_card_discard(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or discard one hand card, then resolve its conditional draw."""

    if action not in legal_agent_card_discard_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card discard choice")
    _, context = current_agent_effect_context(state)
    context["pending_agent_effect"] = False
    source = f"round:{state.round_number}:player:{action.actor}:agent_card_discard"
    if action.action_id == "decline_agent_card_discard":
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="agent_card_discard_declined",
                    payload=(("player", action.actor),),
                ),
            ),
        )

    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Agent-card discard choice has invalid card ID")
    discarded_card = personal_card_for_instance(card_id)
    discarded = discard_personal_card_from_hand(
        state,
        action.actor,
        card_id,
        source=source,
    )
    prepared = advance_after_effect(
        discarded.state,
        context,
        discarded.state.players,
    )
    source_card = personal_card_for_instance(_effect_subject(context)[1])
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_DISCARD_TO_TAKE_CONTRACT
    ):
        contracts = begin_contract_gain(
            prepared,
            action.actor,
            1,
            source=f"{source}:contract_reward",
        )
        return RuleResult(
            state=contracts.state,
            events=(*discarded.events, *contracts.events),
        )
    draws_intrigue = False
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD
    ):
        draw_count = 2 if Faction.SPACING_GUILD in discarded_card.factions else 0
    elif (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD
    ):
        draws_intrigue = True
        draw_count = 1
    elif (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD
    ):
        draws_intrigue = Faction.SPACING_GUILD in discarded_card.factions
        draw_count = 1
    else:
        draw_count = 2 if Faction.SPACING_GUILD in discarded_card.factions else 1
    if draws_intrigue:
        if not prepared.intrigue_deck:
            raise RuntimeError("Agent-card discard has no Intrigue reward")
        next_owner = prepared.players[action.actor]
        next_owner = replace(
            next_owner,
            intrigue_cards=(*next_owner.intrigue_cards, prepared.intrigue_deck[0]),
        )
        prepared = replace(
            prepared,
            players=_replace_player(prepared, next_owner),
            intrigue_deck=prepared.intrigue_deck[1:],
        )
    if draw_count == 0:
        return RuleResult(state=prepared, events=discarded.events)
    drawn = draw_or_request_personal_cards(
        prepared,
        action.actor,
        draw_count,
        source=f"{source}:{card_id}:draw",
    )
    intrigue_events = (
        (
            GameEvent(
                event_id=f"{source}:{card_id}:intrigue_draw",
                kind="intrigue_card_drawn",
                payload=(("count", 1), ("player", action.actor)),
            ),
        )
        if draws_intrigue
        else ()
    )
    return RuleResult(
        state=drawn.state,
        events=(*discarded.events, *intrigue_events, *drawn.events),
    )


def legal_agent_card_long_live_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Long Live the Fighters' two private top-card choices.

    The first choice is exposed only after the Agent effect has explicitly
    started resolving. This preserves the free ordering of the board,
    Faction, and card effect groups while still checking the three-card
    requirement at the point of resolution.
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
    _, source_card_id, _ = _effect_subject(context)
    source_card = personal_card_for_instance(source_card_id)
    if source_card.agent_effect is not PersonalCardAgentEffect.LOOK_AT_TOP_THREE:
        return ()
    if context.get(_LONG_LIVE_SELECTION_STARTED) is not True:
        return ()

    top_cards = state.players[player].deck[:3]
    if len(top_cards) < 3:
        raise RuntimeError(
            "Long Live the Fighters selection requires three cards in the deck"
        )
    draw_card_id = context.get(_LONG_LIVE_DRAW_CARD_ID)
    if draw_card_id is None:
        return tuple(
            DomainAction(
                action_id=_LONG_LIVE_DRAW_ACTION_ID,
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in top_cards
        )
    if not isinstance(draw_card_id, str) or draw_card_id not in top_cards:
        raise RuntimeError("Long Live the Fighters frame has an invalid draw card")
    return tuple(
        DomainAction(
            action_id=_LONG_LIVE_DISCARD_ACTION_ID,
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in top_cards
        if card_id != draw_card_id
    )


def apply_agent_card_long_live_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve one Long Live the Fighters choice.

    The selected cards remain in the deck after the first action. The second
    action commits draw, discard, and trash together, so no unrelated decision
    can be interleaved with this one card effect.
    """

    if action not in legal_agent_card_long_live_actions(state, action.actor):
        raise ValueError("action is not a legal Long Live the Fighters choice")
    _, context = current_agent_effect_context(state)
    player, source_card_id, _ = _effect_subject(context)
    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Long Live the Fighters choice has invalid card ID")

    source = (
        f"round:{state.round_number}:player:{player}:"
        f"agent_card:{source_card_id}:long_live_fighters"
    )
    if action.action_id == _LONG_LIVE_DRAW_ACTION_ID:
        context[_LONG_LIVE_DRAW_CARD_ID] = card_id
        frame = state.decision_stack[-1]
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        return RuleResult(
            state=replace(
                state,
                decision_stack=(*state.decision_stack[:-1], next_frame),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:selection_started",
                    kind="long_live_fighters_selection_started",
                    payload=(("player", player),),
                ),
            ),
        )

    draw_card_id = context.get(_LONG_LIVE_DRAW_CARD_ID)
    if not isinstance(draw_card_id, str):
        raise RuntimeError("Long Live the Fighters frame is missing its draw card")
    top_cards = state.players[player].deck[:3]
    if len(top_cards) < 3 or draw_card_id not in top_cards or card_id not in top_cards:
        raise RuntimeError("Long Live the Fighters frame has invalid top cards")
    if card_id == draw_card_id:
        raise RuntimeError("Long Live the Fighters cannot draw and discard one card")
    trash_card_id = next(
        candidate
        for candidate in top_cards
        if candidate not in (draw_card_id, card_id)
    )

    # Stage the printed draw and discard moves first. The remaining card stays
    # in the deck for the shared trash transition, so a future trash trigger
    # observes the same zones as the completed printed order.
    owner = state.players[player]
    staged_owner = replace(
        owner,
        deck=tuple(
            candidate
            for candidate in owner.deck
            if candidate not in (draw_card_id, card_id)
        ),
        hand=(*owner.hand, draw_card_id),
        discard_pile=(*owner.discard_pile, card_id),
    )
    staged_state = replace(
        state,
        players=_replace_player(state, staged_owner),
    )
    trashed = trash_personal_card(
        staged_state,
        player,
        trash_card_id,
        source=source,
        allow_deck=True,
    )
    next_owner = trashed.state.players[player]
    context["pending_agent_effect"] = False
    context.pop(_LONG_LIVE_SELECTION_STARTED, None)
    context.pop(_LONG_LIVE_DRAW_CARD_ID, None)
    next_state = advance_after_effect(
        trashed.state,
        context,
        _replace_player(trashed.state, next_owner),
    )
    discard_event = GameEvent(
        event_id=f"{source}:discard:{card_id}",
        kind="card_discarded",
        payload=(("card_id", card_id), ("player", player)),
    )
    resolved_event = GameEvent(
        event_id=f"{source}:resolved",
        kind="agent_card_effect_resolved",
        payload=(("card_id", source_card_id), ("player", player)),
    )
    return RuleResult(
        state=next_state,
        events=(discard_event, *trashed.events, resolved_event),
    )


def legal_opponent_card_discard_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return hand cards the current Covert Operation target may discard."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or "covert_operation_card_id" not in context
        or "covert_operation_owner" not in context
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="discard_opponent_card",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id in state.players[player].hand
    )


def apply_opponent_card_discard(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Discard one target-owned card and expose the next opponent decision."""

    if action not in legal_opponent_card_discard_actions(state, action.actor):
        raise ValueError("action is not a legal opponent-card discard")
    context = dict(state.decision_stack[-1].context)
    source_card_id = context["covert_operation_card_id"]
    source_owner = context["covert_operation_owner"]
    card_id = dict(action.arguments).get("card_id")
    if (
        not isinstance(source_card_id, str)
        or isinstance(source_owner, bool)
        or not isinstance(source_owner, int)
        or not isinstance(card_id, str)
    ):
        raise RuntimeError("Covert Operation frame has invalid context")
    discarded = discard_personal_card_from_hand(
        state,
        action.actor,
        card_id,
        source=(
            f"round:{state.round_number}:player:{source_owner}:"
            f"agent_card:{source_card_id}:opponent:{action.actor}"
        ),
    )
    return RuleResult(
        state=replace(
            discarded.state,
            decision_stack=discarded.state.decision_stack[:-1],
        ),
        events=discarded.events,
    )


def legal_agent_card_influence_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Faction choices for the current Agent-card effect."""

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
    _, source_card_id, _ = _effect_subject(context)
    source_card = personal_card_for_instance(source_card_id)
    effect = source_card.agent_effect
    if effect not in (
        PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE,
        PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN,
        PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE,
    ):
        return ()
    if (
        effect
        is PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN
        and context.get("spy_recalled_this_turn") is not True
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="choose_agent_card_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )


def apply_agent_card_influence(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve the current Agent card's selected Faction Influence."""

    if action not in legal_agent_card_influence_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card Influence choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    faction_value = dict(action.arguments).get("faction")
    if not isinstance(faction_value, str):
        raise RuntimeError("Agent-card Influence choice has invalid Faction")
    faction = Faction(faction_value)
    source_card = personal_card_for_instance(source_card_id)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}"
    )
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE
    ):
        prepared = trash_personal_card(
            state,
            action.actor,
            source_card_id,
            source=source,
        )
    else:
        prepared = RuleResult(state=state)
    gained = gain_faction_influence(
        prepared.state,
        action.actor,
        faction,
        1,
        event_prefix=f"{source}:influence:{faction.value}",
    )
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(
        gained.state,
        context,
        gained.state.players,
    )
    return RuleResult(
        state=next_state,
        events=(*prepared.events, *gained.events),
    )


def legal_agent_card_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return placement or recall choices for an Agent-box Spy icon."""

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
    _, source_card_id, _ = _effect_subject(context)
    source_card = personal_card_for_instance(source_card_id)
    if source_card.agent_effect not in (
        PersonalCardAgentEffect.PLACE_SPY,
        PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE,
    ):
        return ()

    owner = state.players[player]
    allowed_post_ids = (
        observation_post_ids_for_factions(source_card.agent_spy_factions)
        if source_card.agent_spy_factions
        else None
    )
    placements = empty_observation_post_ids(state, allowed_post_ids)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE
        and _owner_is_spying_on_visited_space(state, player, context)
    ):
        opponent_posts = {
            post_id
            for candidate in state.players
            if candidate.player_id != player
            for post_id in candidate.spy_post_ids
        }
        placements = tuple(
            post.post_id
            for post in OBSERVATION_POSTS
            if post.post_id not in owner.spy_post_ids
            and (
                post.post_id in opponent_posts
                or post.post_id in placements
            )
        )
    if context.get("agent_card_spy_recalled") is True or owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_agent_card_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in placements
        )
    recall_post_ids = owner.spy_post_ids
    if not placements and allowed_post_ids is not None:
        recall_post_ids = tuple(
            post_id for post_id in owner.spy_post_ids if post_id in allowed_post_ids
        )
    return tuple(
        DomainAction(
            action_id="recall_spy_for_agent_card",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in recall_post_ids
    )


def apply_agent_card_spy_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve a card's place-Spy effect, recalling first when necessary."""

    if action not in legal_agent_card_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card Spy choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    post_id = dict(action.arguments).get("post_id")
    if not isinstance(post_id, str):
        raise RuntimeError("Agent-card Spy choice has invalid post ID")
    owner = state.players[action.actor]
    source = (
        f"round:{state.round_number}:player:{action.actor}:agent_card:{source_card_id}"
    )

    if action.action_id == "recall_spy_for_agent_card":
        next_owner = recall_spy(owner, post_id)
        context["agent_card_spy_recalled"] = True
        next_state = advance_after_effect(
            state,
            context,
            _replace_player(state, next_owner),
        )
        event = GameEvent(
            event_id=f"{source}:spy_recalled:{post_id}",
            kind="spy_recalled",
            payload=(
                ("player", action.actor),
                ("post_id", post_id),
                ("source", source_card_id),
            ),
        )
        return RuleResult(state=next_state, events=(event,))

    next_owner = place_spy(owner, post_id)
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(
        state,
        context,
        _replace_player(state, next_owner),
    )
    event = GameEvent(
        event_id=f"{source}:spy_placed:{post_id}",
        kind="spy_placed",
        payload=(
            ("card_id", source_card_id),
            ("player", action.actor),
            ("post_id", post_id),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_agent_card_recall_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Agent locations that Steersman may recall."""

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
    _, source_card_id, _ = _effect_subject(context)
    if (
        personal_card_for_instance(source_card_id).agent_effect
        is not PersonalCardAgentEffect.DRAW_ONE_AND_RECALL_AGENT
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="recall_agent_for_agent_card",
            actor=player,
            arguments=(("space_id", space_id),),
        )
        for space_id in state.players[player].agent_locations
    )


def apply_agent_card_recall(state: GameState, action: DomainAction) -> RuleResult:
    """Recall one Agent for Steersman, then draw one personal card."""

    if action not in legal_agent_card_recall_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card recall choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    space_id = dict(action.arguments).get("space_id")
    if not isinstance(space_id, str):
        raise RuntimeError("Agent-card recall choice has invalid space ID")
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        agents_available=owner.agents_available + 1,
        agent_locations=tuple(
            location for location in owner.agent_locations if location != space_id
        ),
    )
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(
        state,
        context,
        _replace_player(state, next_owner),
    )
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}"
    )
    drawn = draw_or_request_personal_cards(
        next_state,
        action.actor,
        1,
        source=f"{source}:draw",
    )
    return RuleResult(
        state=drawn.state,
        events=(
            GameEvent(
                event_id=f"{source}:agent_recalled:{space_id}",
                kind="agent_recalled",
                payload=(
                    ("card_id", source_card_id),
                    ("player", action.actor),
                    ("space_id", space_id),
                ),
            ),
            *drawn.events,
        ),
    )


def legal_agent_card_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional personal-card trash choices for the current Agent card."""

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
    _, source_card_id, _ = _effect_subject(context)
    source_card = personal_card_for_instance(source_card_id)
    if source_card.agent_effect not in (
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD,
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE,
        PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND,
        PersonalCardAgentEffect.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE,
        PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE,
    ):
        return ()

    owner = state.players[player]
    eligible = (*owner.hand, *owner.discard_pile, *owner.in_play)
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE
    ):
        eligible = tuple(
            card_id
            for card_id in owner.hand
            if card_id != source_card_id
            and Faction.EMPEROR in personal_card_for_instance(card_id).factions
        )
    if (
        source_card.agent_effect
        is (
            PersonalCardAgentEffect.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE
        )
    ):
        eligible = tuple(
            card_id
            for card_id in eligible
            if len(state.intrigue_deck)
            >= 1
            + int(
                getattr(personal_card_for_instance(card_id), "trash_effect", None)
                is PersonalCardTrashEffect.DRAW_INTRIGUE_CARD
            )
        )
    return (
        DomainAction(action_id="decline_agent_card_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_agent_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in eligible
        ),
    )


def apply_agent_card_trash(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve or decline an Agent-box personal-card trash choice."""

    if action not in legal_agent_card_trash_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card trash choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    source_card = personal_card_for_instance(source_card_id)
    context["pending_agent_effect"] = False
    source = f"round:{state.round_number}:player:{action.actor}:agent_card"
    if action.action_id == "decline_agent_card_trash":
        next_state = advance_after_effect(state, context)
        event = GameEvent(
            event_id=f"{source}:trash_declined",
            kind="agent_card_trash_declined",
            payload=(("player", action.actor),),
        )
        return RuleResult(state=next_state, events=(event,))

    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Agent-card trash choice has invalid card ID")
    trashed = trash_personal_card(
        state,
        action.actor,
        card_id,
        source=source,
    )
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE
    ):
        source_trashed = trash_personal_card(
            trashed.state,
            action.actor,
            source_card_id,
            source=source,
        )
        space_id = context.get("space_id")
        if not isinstance(space_id, str):
            raise RuntimeError("Agent-turn effect frame has invalid space")
        faction = BOARD_SPACES_BY_ID[space_id].faction
        if faction is None:
            raise RuntimeError("Treacherous Maneuver requires a Faction space")
        gained = gain_faction_influence(
            source_trashed.state,
            action.actor,
            faction,
            1,
            event_prefix=f"{source}:extra_influence:{faction.value}",
        )
        next_state = advance_after_effect(
            gained.state,
            context,
            gained.state.players,
        )
        return RuleResult(
            state=next_state,
            events=(*trashed.events, *source_trashed.events, *gained.events),
        )
    if (
        source_card.agent_effect
        is (
            PersonalCardAgentEffect.MAY_TRASH_FOR_INTRIGUE_AND_TWO_TROOPS_IF_BENE_GESSERIT_ALLIANCE
        )
    ):
        if not trashed.state.intrigue_deck:
            raise RuntimeError("Branching Path trash has no Intrigue reward")
        next_owner, recruited = recruit_troops(
            trashed.state.players[action.actor],
            2,
        )
        next_owner = replace(
            next_owner,
            intrigue_cards=(
                *next_owner.intrigue_cards,
                trashed.state.intrigue_deck[0],
            ),
        )
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        rewarded = replace(
            trashed.state,
            players=_replace_player(trashed.state, next_owner),
            intrigue_deck=trashed.state.intrigue_deck[1:],
        )
        next_state = advance_after_effect(
            rewarded,
            context,
            rewarded.players,
        )
        return RuleResult(
            state=next_state,
            events=(
                *trashed.events,
                GameEvent(
                    event_id=f"{source}:trash_reward:intrigue_draw",
                    kind="intrigue_card_drawn",
                    payload=(("count", 1), ("player", action.actor)),
                ),
            ),
        )
    next_state = advance_after_effect(
        trashed.state,
        context,
        trashed.state.players,
    )
    if (
        source_card.agent_effect
        in (
            PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE,
            PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND,
        )
    ):
        drawn = draw_or_request_personal_cards(
            next_state,
            action.actor,
            1,
            source=f"{source}:trash_draw",
        )
        return RuleResult(
            state=drawn.state,
            events=(*trashed.events, *drawn.events),
        )
    return RuleResult(state=next_state, events=trashed.events)


def legal_agent_card_intrigue_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional Intrigue-and-Spice payment choices for an Agent card."""

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
    _, source_card_id, _ = _effect_subject(context)
    effect = personal_card_for_instance(source_card_id).agent_effect
    if (
        effect
        is not (
            PersonalCardAgentEffect.MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE
        )
    ):
        return ()
    owner = state.players[player]
    if (
        Faction.SPACING_GUILD.value not in owner.alliance_faction_ids
        or owner.resources.spice < 2
        or not owner.intrigue_cards
    ):
        raise RuntimeError("pending Agent-card Intrigue payment is not affordable")
    return (
        DomainAction(action_id="decline_agent_card_intrigue_payment", actor=player),
        *(
            DomainAction(
                action_id="pay_agent_card_intrigue_and_spice",
                actor=player,
                arguments=(("intrigue_card_id", card_id),),
            )
            for card_id in owner.intrigue_cards
        ),
    )


def apply_agent_card_intrigue_payment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or trash one Intrigue and pay two Spice for one VP."""

    if action not in legal_agent_card_intrigue_payment_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card Intrigue payment")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}:intrigue_payment"
    )
    if action.action_id == "decline_agent_card_intrigue_payment":
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="agent_card_payment_declined",
                    payload=(("card_id", source_card_id), ("player", action.actor)),
                ),
            ),
        )

    intrigue_card_id = dict(action.arguments).get("intrigue_card_id")
    if not isinstance(intrigue_card_id, str):
        raise RuntimeError("Agent-card Intrigue payment has invalid card ID")
    owner = state.players[action.actor]
    previous_spent = context.get("spice_spent_after_placement", 0)
    if isinstance(previous_spent, bool) or not isinstance(previous_spent, int):
        raise RuntimeError("Agent-turn effect frame has invalid Spice spending")
    context["spice_spent_after_placement"] = previous_spent + 2
    next_owner = replace(
        owner,
        resources=replace(
            owner.resources,
            spice=owner.resources.spice - 2,
        ),
        victory_points=owner.victory_points + 1,
        intrigue_cards=tuple(
            card_id
            for card_id in owner.intrigue_cards
            if card_id != intrigue_card_id
        ),
    )
    next_state = advance_after_effect(
        replace(
            state,
            intrigue_trash=(*state.intrigue_trash, intrigue_card_id),
        ),
        context,
        _replace_player(state, next_owner),
    )
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:intrigue_trashed:{intrigue_card_id}",
                kind="intrigue_card_trashed",
                payload=(
                    ("card_id", intrigue_card_id),
                    ("player", action.actor),
                ),
            ),
            GameEvent(
                event_id=f"{source}:paid",
                kind="agent_card_payment_resolved",
                payload=(
                    ("card_id", source_card_id),
                    ("player", action.actor),
                    ("resource", "spice"),
                    ("spent", 2),
                ),
            ),
        ),
    )


def legal_agent_card_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional resource payments for the current Agent card."""

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
    _, source_card_id, _ = _effect_subject(context)
    source_card = personal_card_for_instance(source_card_id)
    if source_card.agent_effect not in (
        PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO,
        PersonalCardAgentEffect.MAY_PAY_FOUR_SPICE_FOR_VP,
    ):
        return ()
    owner = state.players[player]
    if (
        source_card.agent_effect
        is PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO
        and owner.resources.water < 2
    ) or (
        source_card.agent_effect
        is PersonalCardAgentEffect.MAY_PAY_FOUR_SPICE_FOR_VP
        and owner.resources.spice < 4
    ):
        raise RuntimeError("pending Agent-card payment is not affordable")
    return (
        DomainAction(action_id="decline_agent_card_payment", actor=player),
        DomainAction(
            action_id=(
                "pay_agent_card_water"
                if source_card.agent_effect
                is PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO
                else "pay_agent_card_spice"
            ),
            actor=player,
        ),
    )


def legal_corrinth_city_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Corrinth City's optional, atomic two-card payment choices."""

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
    _, source_card_id, _ = _effect_subject(context)
    source_card = personal_card_for_instance(source_card_id)
    if (
        source_card.agent_effect
        is not PersonalCardAgentEffect.MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP
    ):
        return ()
    owner = state.players[player]
    if owner.resources.solari < 5 or len(owner.hand) < 2:
        raise RuntimeError("pending Corrinth City payment is not affordable")
    first_card_id = context.get("corrinth_first_card_id")
    if first_card_id is not None and not isinstance(first_card_id, str):
        raise RuntimeError("pending Corrinth City payment has invalid first card")
    return (
        DomainAction(action_id="decline_corrinth_city_payment", actor=player),
        *(
            DomainAction(
                action_id=(
                    "select_corrinth_city_discard"
                    if first_card_id is None
                    else "pay_corrinth_city"
                ),
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in owner.hand
            if card_id != first_card_id
        ),
    )


def apply_corrinth_city_payment(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or pay Corrinth City's complete cost before resolving discards."""

    if action not in legal_corrinth_city_payment_actions(state, action.actor):
        raise ValueError("action is not a legal Corrinth City payment choice")
    _, context = current_agent_effect_context(state)
    _, source_card_id, _ = _effect_subject(context)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"agent_card:{source_card_id}"
    )
    if action.action_id == "decline_corrinth_city_payment":
        context["pending_agent_effect"] = False
        return RuleResult(
            state=advance_after_effect(state, context),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="corrinth_city_payment_declined",
                    payload=(("player", action.actor),),
                ),
            ),
        )

    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Corrinth City payment has invalid card ID")
    if action.action_id == "select_corrinth_city_discard":
        context["corrinth_first_card_id"] = card_id
        frame = state.decision_stack[-1]
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        return RuleResult(
            state=replace(
                state,
                decision_stack=(*state.decision_stack[:-1], next_frame),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:first_discard_selected",
                    kind="corrinth_city_payment_started",
                    payload=(("player", action.actor),),
                ),
            ),
        )

    first_card_id = context.get("corrinth_first_card_id")
    if not isinstance(first_card_id, str):
        raise RuntimeError("Corrinth City payment is missing its first card")
    context["pending_agent_effect"] = False
    owner = state.players[action.actor]
    if owner.resources.solari < 5:
        raise RuntimeError("Corrinth City payment requires five Solari")
    paid_owner = replace(
        owner,
        resources=replace(owner.resources, solari=owner.resources.solari - 5),
    )
    paid_state = replace(state, players=_replace_player(state, paid_owner))
    first_discard = discard_personal_card_from_hand(
        paid_state,
        action.actor,
        first_card_id,
        source=source,
    )
    second_discard = discard_personal_card_from_hand(
        first_discard.state,
        action.actor,
        card_id,
        source=source,
    )
    resolved_owner = second_discard.state.players[action.actor]
    resolved_owner = replace(
        resolved_owner,
        victory_points=resolved_owner.victory_points + 1,
    )
    next_state = advance_after_effect(
        second_discard.state,
        context,
        _replace_player(second_discard.state, resolved_owner),
    )
    return RuleResult(
        state=next_state,
        events=(
            *first_discard.events,
            *second_discard.events,
            GameEvent(
                event_id=f"{source}:resolved",
                kind="corrinth_city_payment_resolved",
                payload=(
                    ("player", action.actor),
                    ("solari", 5),
                    ("victory_points", 1),
                ),
            ),
        ),
    )


def apply_agent_card_payment(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve or decline an Agent-box resource payment."""

    if action not in legal_agent_card_payment_actions(state, action.actor):
        raise ValueError("action is not a legal Agent-card payment choice")
    _, context = current_agent_effect_context(state)
    context["pending_agent_effect"] = False
    source = f"round:{state.round_number}:player:{action.actor}:agent_card_payment"
    if action.action_id == "decline_agent_card_payment":
        next_state = advance_after_effect(state, context)
        event = GameEvent(
            event_id=f"{source}:declined",
            kind="agent_card_payment_declined",
            payload=(("player", action.actor),),
        )
        return RuleResult(state=next_state, events=(event,))

    owner = state.players[action.actor]
    source_card = personal_card_for_instance(_effect_subject(context)[1])
    pays_water = (
        source_card.agent_effect
        is PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO
    )
    resource = "water" if pays_water else "spice"
    spent = 2 if pays_water else 4
    if not pays_water:
        previous_spent = context.get("spice_spent_after_placement", 0)
        if isinstance(previous_spent, bool) or not isinstance(previous_spent, int):
            raise RuntimeError("Agent-turn effect frame has invalid Spice spending")
        context["spice_spent_after_placement"] = previous_spent + spent
    next_owner = replace(
        owner,
        resources=replace(
            owner.resources,
            water=owner.resources.water - (spent if pays_water else 0),
            spice=owner.resources.spice - (0 if pays_water else spent),
        ),
        victory_points=owner.victory_points + (0 if pays_water else 1),
    )
    players = _replace_player(state, next_owner)
    paid_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=f"{source}:paid",
        kind="agent_card_payment_resolved",
        payload=(
            ("player", action.actor),
            ("resource", resource),
            ("spent", spent),
        ),
    )
    if not pays_water:
        return RuleResult(state=paid_state, events=(event,))
    draw = draw_or_request_personal_cards(
        paid_state,
        action.actor,
        2,
        source=source,
    )
    return RuleResult(state=draw.state, events=(event, *draw.events))


def resolve_agent_card_effect(state: GameState) -> RuleResult:
    """Resolve the supported Agent box in the current effect frame."""

    _, context = current_agent_effect_context(state)
    if context["pending_agent_effect"] is not True:
        raise ValueError("the current Agent turn has no pending card effect")
    player, card_instance_id, _ = _effect_subject(context)
    card = personal_card_for_instance(card_instance_id)
    effect = card.agent_effect

    owner = state.players[player]
    if effect is PersonalCardAgentEffect.TRASH_SELF:
        trashed = trash_personal_card(
            state,
            player,
            card_instance_id,
            source=f"round:{state.round_number}:player:{player}:agent_card",
        )
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(
            trashed.state,
            context,
            trashed.state.players,
        )
        return RuleResult(state=next_state, events=trashed.events)
    elif (
        effect
        is PersonalCardAgentEffect.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF
    ):
        space_id = context.get("space_id")
        if not isinstance(space_id, str):
            raise RuntimeError("Agent-turn effect frame has invalid space")
        faction = BOARD_SPACES_BY_ID[space_id].faction
        if faction is None:
            raise RuntimeError("card effect requires a visited Faction space")
        source = (
            f"round:{state.round_number}:player:{player}:"
            f"agent_card:{card_instance_id}"
        )
        gained = gain_faction_influence(
            state,
            player,
            faction,
            2,
            event_prefix=f"{source}:influence:{faction.value}",
        )
        trashed = trash_personal_card(
            gained.state,
            player,
            card_instance_id,
            source=source,
        )
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(
            trashed.state,
            context,
            trashed.state.players,
        )
        return RuleResult(
            state=next_state,
            events=(*gained.events, *trashed.events),
        )
    elif effect is PersonalCardAgentEffect.LOOK_AT_TOP_THREE:
        if context.get(_LONG_LIVE_SELECTION_STARTED) is True:
            raise RuntimeError(
                "Long Live the Fighters selection is already in progress"
            )
        if len(owner.deck) < 3:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
        else:
            context[_LONG_LIVE_SELECTION_STARTED] = True
            frame = state.decision_stack[-1]
            next_frame = replace(frame, context=tuple(sorted(context.items())))
            source = (
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}:long_live_fighters"
            )
            return RuleResult(
                state=replace(
                    state,
                    decision_stack=(*state.decision_stack[:-1], next_frame),
                ),
                events=(
                    GameEvent(
                        event_id=f"{source}:ready",
                        kind="agent_card_effect_ready",
                        payload=(
                            ("card_id", card_instance_id),
                            ("player", player),
                        ),
                    ),
                ),
            )
    elif effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD:
        next_owner = owner
        event_kind = "agent_card_effect_resolved"
    elif (
        effect
        is PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO
    ):
        next_owner = owner
        event_kind = (
            "agent_card_effect_resolved"
            if len(owner.completed_contract_ids) >= 2
            else "agent_card_effect_unavailable"
        )
    elif effect is PersonalCardAgentEffect.TAKE_CONTRACT:
        context["pending_agent_effect"] = False
        resumed = advance_after_effect(state, context)
        contracts = begin_contract_gain(
            resumed,
            player,
            1,
            source=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}"
            ),
        )
        event = GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}"
            ),
            kind="agent_card_effect_resolved",
            payload=(("card_id", card_instance_id), ("player", player)),
        )
        return RuleResult(
            state=contracts.state,
            events=(event, *contracts.events),
        )
    elif effect is PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_PERSONAL_CARD:
        context["pending_agent_effect"] = False
        base_frame = replace(
            state.decision_stack[-1],
            context=tuple(sorted(context.items())),
        )
        targets = tuple(
            (player + offset) % state.config.players
            for offset in range(1, state.config.players)
            if state.players[(player + offset) % state.config.players].hand
        )
        frames = tuple(
            DecisionFrame(
                frame_id=(
                    f"round:{state.round_number}:player:{player}:"
                    f"agent_card:{card_instance_id}:opponent:{target}"
                ),
                decision=PlayerDecision(
                    owner=target,
                    prompt="Choose a card to discard for Covert Operation",
                ),
                context=(
                    ("covert_operation_card_id", card_instance_id),
                    ("covert_operation_owner", player),
                ),
            )
            for target in reversed(targets)
        )
        base_state = replace(
            state,
            decision_stack=(*state.decision_stack[:-1], base_frame, *frames),
        )
        next_state = (
            base_state
            if targets
            else advance_after_effect(base_state, context, base_state.players)
        )
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=(
                        f"round:{state.round_number}:player:{player}:"
                        f"agent_card:{card_instance_id}"
                    ),
                    kind="agent_card_effect_resolved",
                    payload=(("card_id", card_instance_id), ("player", player)),
                ),
            ),
        )
    elif effect is PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT:
        if owner.sandworms_conflict == 0:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = owner
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO:
        if owner.influence.bene_gesserit < 2:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = owner
        event_kind = "agent_card_effect_resolved"
    elif (
        effect
        is PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO
    ):
        if owner.influence.bene_gesserit < 2:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner, recruited = recruit_troops(owner, 1)
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_SPICE_IF_MAKER_SPACE:
        space_id = context.get("space_id")
        if not isinstance(space_id, str) or not BOARD_SPACES_BY_ID[space_id].maker:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + 1,
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_MAKER_SPACE:
        space_id = context.get("space_id")
        if not isinstance(space_id, str) or not BOARD_SPACES_BY_ID[space_id].maker:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + 2,
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.RECRUIT_ONE_IF_MAKER_SPACE:
        space_id = context.get("space_id")
        if not isinstance(space_id, str) or not BOARD_SPACES_BY_ID[space_id].maker:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner, recruited = recruit_troops(owner, 1)
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.RECRUIT_TWO_TROOPS:
        next_owner, recruited = recruit_troops(owner, 2)
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_WATER:
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                water=owner.resources.water + 1,
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_TWO_SOLARI:
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + 2,
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_VISITED_FACTION_INFLUENCE:
        space_id = context.get("space_id")
        if not isinstance(space_id, str):
            raise RuntimeError("Agent-turn effect frame has invalid space")
        faction = BOARD_SPACES_BY_ID[space_id].faction
        if faction is None:
            raise RuntimeError("card effect requires a visited Faction space")
        gained = gain_faction_influence(
            state,
            player,
            faction,
            1,
            event_prefix=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}:influence:{faction.value}"
            ),
        )
        context["pending_agent_effect"] = False
        next_state = advance_after_effect(
            gained.state,
            context,
            gained.state.players,
        )
        return RuleResult(state=next_state, events=gained.events)
    elif (
        effect
        is PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO
    ):
        gains_water = owner.influence.bene_gesserit >= 2
        gains_spice = owner.influence.fremen >= 2
        if not gains_water and not gains_spice:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + int(gains_spice),
                water=owner.resources.water + int(gains_water),
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif (
        effect
        is PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO
    ):
        gains_solari = owner.influence.emperor >= 2
        gains_spice = owner.influence.spacing_guild >= 2
        if not gains_solari and not gains_spice:
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + 2 * int(gains_solari),
                spice=owner.resources.spice + int(gains_spice),
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.RECRUIT_TWO_IF_BENE_GESSERIT_BOND:
        if not has_faction_bond(
            owner.in_play,
            card_instance_id,
            Faction.BENE_GESSERIT,
        ):
            raise RuntimeError("conditional Agent effect is not available")
        next_owner, recruited = recruit_troops(owner, 2)
        previous = context.get("troops_recruited")
        if isinstance(previous, bool) or not isinstance(previous, int):
            raise RuntimeError("Agent-turn effect frame has invalid recruit count")
        context["troops_recruited"] = previous + recruited
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.RETURN_SELF_IF_BENE_GESSERIT_BOND:
        if not has_faction_bond(
            owner.in_play,
            card_instance_id,
            Faction.BENE_GESSERIT,
        ):
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = replace(
            owner,
            hand=(*owner.hand, card_instance_id),
            in_play=tuple(
                candidate
                for candidate in owner.in_play
                if candidate != card_instance_id
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect is PersonalCardAgentEffect.GAIN_WATER_IF_BENE_GESSERIT_BOND:
        if not has_faction_bond(
            owner.in_play,
            card_instance_id,
            Faction.BENE_GESSERIT,
        ):
            raise RuntimeError("conditional Agent effect is not available")
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                water=owner.resources.water + 1,
            ),
        )
        event_kind = "agent_card_effect_resolved"
    elif effect in (
        PersonalCardAgentEffect.PLACE_SPY,
        PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE,
    ):
        if legal_agent_card_spy_actions(state, player):
            raise RuntimeError("place-Spy Agent effect requires a player choice")
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN:
        if context.get("spy_recalled_this_turn") is True:
            next_owner, recruited = recruit_troops(owner, 3)
            previous = context.get("troops_recruited")
            if isinstance(previous, bool) or not isinstance(previous, int):
                raise RuntimeError("Agent-turn effect frame has invalid recruit count")
            context["troops_recruited"] = previous + recruited
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN:
        if context.get("spy_recalled_this_turn") is True:
            next_owner, recruited = recruit_troops(owner, 2)
            previous = context.get("troops_recruited")
            if isinstance(previous, bool) or not isinstance(previous, int):
                raise RuntimeError("Agent-turn effect frame has invalid recruit count")
            context["troops_recruited"] = previous + recruited
            event_kind = "agent_card_effect_resolved"
        else:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN:
        if context.get("spy_recalled_this_turn") is not True:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
        else:
            if not state.intrigue_deck:
                raise ValueError("the Intrigue deck does not contain enough cards")
            next_owner = replace(
                owner,
                intrigue_cards=(*owner.intrigue_cards, state.intrigue_deck[0]),
            )
            context["pending_agent_effect"] = False
            next_state = advance_after_effect(
                replace(state, intrigue_deck=state.intrigue_deck[1:]),
                context,
                _replace_player(state, next_owner),
            )
            source = (
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}"
            )
            return RuleResult(
                state=next_state,
                events=(
                    GameEvent(
                        event_id=source,
                        kind="agent_card_effect_resolved",
                        payload=(
                            ("card_id", card_instance_id),
                            ("player", player),
                        ),
                    ),
                    GameEvent(
                        event_id=f"{source}:intrigue_draw",
                        kind="intrigue_card_drawn",
                        payload=(("count", 1), ("player", player)),
                    ),
                ),
            )
    elif effect is PersonalCardAgentEffect.DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT:
        if owner.troops_conflict + owner.sandworms_conflict < 3:
            next_owner = owner
            event_kind = "agent_card_effect_unavailable"
        else:
            if not state.intrigue_deck:
                raise ValueError("the Intrigue deck does not contain enough cards")
            next_owner = replace(
                owner,
                intrigue_cards=(*owner.intrigue_cards, state.intrigue_deck[0]),
            )
            context["pending_agent_effect"] = False
            next_state = advance_after_effect(
                replace(state, intrigue_deck=state.intrigue_deck[1:]),
                context,
                _replace_player(state, next_owner),
            )
            source = (
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card_instance_id}"
            )
            return RuleResult(
                state=next_state,
                events=(
                    GameEvent(
                        event_id=source,
                        kind="agent_card_effect_resolved",
                        payload=(
                            ("card_id", card_instance_id),
                            ("player", player),
                        ),
                    ),
                    GameEvent(
                        event_id=f"{source}:intrigue_draw",
                        kind="intrigue_card_drawn",
                        payload=(("count", 1), ("player", player)),
                    ),
                ),
            )
    elif (
        effect
        is PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN
    ):
        if context.get("spy_recalled_this_turn") is True:
            raise RuntimeError("Agent-card Influence effect requires a player choice")
        next_owner = owner
        event_kind = "agent_card_effect_unavailable"
    elif effect is PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE:
        raise RuntimeError("Agent-card Influence effect requires a player choice")
    else:
        raise NotImplementedError(
            f"personal-card Agent effect is not implemented: {card.card.card_id}"
        )
    players = _replace_player(state, next_owner)
    context["pending_agent_effect"] = False
    next_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:"
            f"agent_card:{card_instance_id}"
        ),
        kind=event_kind,
        payload=(("card_id", card_instance_id), ("player", player)),
    )
    if effect in (
        PersonalCardAgentEffect.DRAW_PERSONAL_CARD,
        PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT,
        PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
        PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
        PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO,
    ):
        if effect is PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT:
            draw_count = owner.sandworms_conflict
        elif (
            effect
            is PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO
        ):
            draw_count = min(len(owner.completed_contract_ids) // 2, 2)
        else:
            draw_count = 1
        if draw_count == 0:
            return RuleResult(state=next_state, events=(event,))
        draw = draw_or_request_personal_cards(
            next_state,
            player,
            draw_count,
            source=(
                f"round:{state.round_number}:player:{player}:"
                f"agent_card:{card.card.card_id}"
            ),
        )
        return RuleResult(state=draw.state, events=(event, *draw.events))
    return RuleResult(state=next_state, events=(event,))


def resolve_faction_influence(state: GameState) -> RuleResult:
    """Gain the visited Faction's Influence and resolve crossed boundaries."""

    _, context = current_agent_effect_context(state)
    if context["pending_faction_influence"] is not True:
        raise ValueError("the current Agent turn has no pending Faction Influence")
    player, _, space_id = _effect_subject(context)
    faction = BOARD_SPACES_BY_ID[space_id].faction
    if faction is None:
        raise RuntimeError("pending Faction Influence requires a Faction space")

    gained = gain_faction_influence(
        state,
        player,
        faction,
        1,
        event_prefix=(
            f"round:{state.round_number}:player:{player}:influence:{faction.value}"
        ),
    )
    context["pending_faction_influence"] = False
    next_state = advance_after_effect(
        gained.state,
        context,
        gained.state.players,
    )
    return RuleResult(state=next_state, events=gained.events)


def _effect_subject(context: dict[str, bool | int | str]) -> tuple[int, str, str]:
    player = context["turn_owner"]
    card_id = context["card_id"]
    space_id = context["space_id"]
    if (
        isinstance(player, bool)
        or not isinstance(player, int)
        or not isinstance(card_id, str)
        or not isinstance(space_id, str)
    ):
        raise RuntimeError("Agent-turn effect frame has invalid subject")
    return player, card_id, space_id


def _replace_player(
    state: GameState,
    player: PlayerState,
) -> tuple[PlayerState, ...]:
    return tuple(
        player if candidate.player_id == player.player_id else candidate
        for candidate in state.players
    )


def _owner_is_spying_on_visited_space(
    state: GameState,
    player: int,
    context: dict[str, ActionValue],
) -> bool:
    space_id = context.get("space_id")
    if not isinstance(space_id, str):
        raise RuntimeError("Agent-turn effect frame has invalid space")
    occupied = frozenset(state.players[player].spy_post_ids)
    return any(
        space_id in post.connected_space_ids and post.post_id in occupied
        for post in OBSERVATION_POSTS
    )
