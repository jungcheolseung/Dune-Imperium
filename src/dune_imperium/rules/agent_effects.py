"""Resolution of starting-card and Faction Agent-turn effects."""

from dataclasses import replace

from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID, Faction
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardAgentEffect
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.card_bonds import has_faction_bond
from dune_imperium.rules.card_draw import draw_or_request_personal_cards
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
    recruit_troops,
)
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    place_spy,
    recall_spy,
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
    if source_card.agent_effect is not PersonalCardAgentEffect.PLACE_SPY:
        return ()

    owner = state.players[player]
    if context.get("agent_card_spy_recalled") is True or owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_agent_card_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in empty_observation_post_ids(state)
        )
    return tuple(
        DomainAction(
            action_id="recall_spy_for_agent_card",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in owner.spy_post_ids
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


def legal_agent_card_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Desert Survival's optional personal-card trash choices."""

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
    if source_card.agent_effect is not PersonalCardAgentEffect.TRASH_PERSONAL_CARD:
        return ()

    owner = state.players[player]
    eligible = (*owner.hand, *owner.discard_pile, *owner.in_play)
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
    next_state = advance_after_effect(
        trashed.state,
        context,
        trashed.state.players,
    )
    return RuleResult(state=next_state, events=trashed.events)


def legal_agent_card_payment_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Ecological Testing Station's optional Water payment."""

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
        is not PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO
    ):
        return ()
    if state.players[player].resources.water < 2:
        raise RuntimeError("pending Agent-card payment is not affordable")
    return (
        DomainAction(action_id="decline_agent_card_payment", actor=player),
        DomainAction(action_id="pay_agent_card_water", actor=player),
    )


def apply_agent_card_payment(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve or decline an Agent-box Water payment and card draw."""

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
    next_owner = replace(
        owner,
        resources=replace(owner.resources, water=owner.resources.water - 2),
    )
    players = _replace_player(state, next_owner)
    paid_state = advance_after_effect(state, context, players)
    event = GameEvent(
        event_id=f"{source}:paid",
        kind="agent_card_payment_resolved",
        payload=(
            ("player", action.actor),
            ("resource", "water"),
            ("spent", 2),
        ),
    )
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
    elif effect is PersonalCardAgentEffect.DRAW_PERSONAL_CARD:
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
        PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
        PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO,
    ):
        draw = draw_or_request_personal_cards(
            next_state,
            player,
            1,
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
