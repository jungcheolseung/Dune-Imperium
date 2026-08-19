"""Start and score the basic portion of an Uprising Reveal turn."""

from dataclasses import replace

from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardRevealChoiceEffect
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_bonds import has_faction_bond
from dune_imperium.rules.effects import recruit_troops
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    place_spy,
    recall_spy,
)


def legal_reveal_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Spy choices for the current serial Reveal effect."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    effect_value = context.get("reveal_choice_effect")
    if not isinstance(effect_value, str):
        return ()
    effect = PersonalCardRevealChoiceEffect(effect_value)
    owner = state.players[player]
    if effect is PersonalCardRevealChoiceEffect.PLACE_SPY:
        if context.get("reveal_spy_recalled") is True or owner.spies_supply > 0:
            return tuple(
                DomainAction(
                    action_id="place_reveal_spy",
                    actor=player,
                    arguments=(("post_id", post_id),),
                )
                for post_id in empty_observation_post_ids(state)
            )
        return tuple(
            DomainAction(
                action_id="recall_spy_for_reveal_placement",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in owner.spy_post_ids
        )
    occupied = frozenset(state.players[player].spy_post_ids)
    post_ids = tuple(
        post.post_id for post in OBSERVATION_POSTS if post.post_id in occupied
    )
    if (
        effect
        is PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED
    ):
        return tuple(
            DomainAction(
                action_id="recall_spy_for_reveal",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in post_ids
        )
    if effect is PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION:
        return (
            DomainAction(action_id="decline_reveal_spy_recall", actor=player),
            *(
                DomainAction(
                    action_id="recall_spies_for_reveal",
                    actor=player,
                    arguments=(
                        ("first_post_id", first_post_id),
                        ("second_post_id", second_post_id),
                    ),
                )
                for index, first_post_id in enumerate(post_ids)
                for second_post_id in post_ids[index + 1 :]
            ),
        )
    return ()


def apply_reveal_spy_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve the current Reveal effect's Spy placement or recall choice."""

    if action not in legal_reveal_spy_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal Spy choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("reveal_card_id")
    effect_value = context.get("reveal_choice_effect")
    if not isinstance(card_id, str) or not isinstance(effect_value, str):
        raise RuntimeError("Reveal Spy frame has invalid context")
    effect = PersonalCardRevealChoiceEffect(effect_value)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}"
    )

    arguments = dict(action.arguments)
    if action.action_id == "recall_spy_for_reveal_placement":
        post_id = arguments.get("post_id")
        if not isinstance(post_id, str):
            raise RuntimeError("Reveal Spy choice has invalid post ID")
        next_owner = recall_spy(state.players[action.actor], post_id)
        context["reveal_spy_recalled"] = True
        next_frame = replace(frame, context=tuple(sorted(context.items())))
        return RuleResult(
            state=replace(
                state,
                players=_replace_player(state, next_owner),
                decision_stack=(*state.decision_stack[:-1], next_frame),
            ),
            events=(
                _spy_recalled_event(state, action.actor, card_id, post_id),
            ),
        )

    if action.action_id == "place_reveal_spy":
        post_id = arguments.get("post_id")
        if not isinstance(post_id, str):
            raise RuntimeError("Reveal Spy choice has invalid post ID")
        next_owner = place_spy(state.players[action.actor], post_id)
        return RuleResult(
            state=replace(
                state,
                players=_replace_player(state, next_owner),
                decision_stack=state.decision_stack[:-1],
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:spy_placed:{post_id}",
                    kind="spy_placed",
                    payload=(
                        ("card_id", card_id),
                        ("player", action.actor),
                        ("post_id", post_id),
                    ),
                ),
            ),
        )

    if action.action_id == "decline_reveal_spy_recall":
        return RuleResult(
            state=replace(state, decision_stack=state.decision_stack[:-1]),
            events=(
                GameEvent(
                    event_id=f"{source}:spy_recall_declined",
                    kind="reveal_spy_recall_declined",
                    payload=(("card_id", card_id), ("player", action.actor)),
                ),
            ),
        )

    owner = state.players[action.actor]
    events: list[GameEvent] = []
    intrigue_deck = state.intrigue_deck
    remaining = state.decision_stack[:-1]
    if (
        effect
        is PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED
    ):
        if not intrigue_deck:
            raise ValueError("the Intrigue deck does not contain enough cards")
        post_id = arguments.get("post_id")
        if not isinstance(post_id, str):
            raise RuntimeError("Reveal Spy choice has invalid post ID")
        next_owner = recall_spy(owner, post_id)
        next_owner = replace(
            next_owner,
            intrigue_cards=(*next_owner.intrigue_cards, intrigue_deck[0]),
        )
        intrigue_deck = intrigue_deck[1:]
        events.extend(
            (
                _spy_recalled_event(state, action.actor, card_id, post_id),
                GameEvent(
                    event_id=f"{source}:intrigue_draw",
                    kind="intrigue_card_drawn",
                    payload=(("count", 1), ("player", action.actor)),
                ),
            )
        )
    else:
        first_post_id = arguments.get("first_post_id")
        second_post_id = arguments.get("second_post_id")
        if not isinstance(first_post_id, str) or not isinstance(second_post_id, str):
            raise RuntimeError("Reveal Spy choice has invalid post IDs")
        next_owner = recall_spy(recall_spy(owner, first_post_id), second_post_id)
        remaining = _add_reveal_persuasion(remaining, 2)
        events.extend(
            (
                _spy_recalled_event(state, action.actor, card_id, first_post_id),
                _spy_recalled_event(state, action.actor, card_id, second_post_id),
                GameEvent(
                    event_id=f"{source}:persuasion",
                    kind="reveal_persuasion_gained",
                    payload=(
                        ("amount", 2),
                        ("card_id", card_id),
                        ("player", action.actor),
                    ),
                ),
            )
        )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    next_state = replace(
        state,
        players=players,
        intrigue_deck=intrigue_deck,
        decision_stack=remaining,
    )
    return RuleResult(state=next_state, events=tuple(events))


def _spy_recalled_event(
    state: GameState,
    player: int,
    card_id: str,
    post_id: str,
) -> GameEvent:
    return GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{player}:"
            f"reveal_card:{card_id}:spy_recalled:{post_id}"
        ),
        kind="spy_recalled",
        payload=(
            ("player", player),
            ("post_id", post_id),
            ("source", card_id),
        ),
    )


def _replace_player(
    state: GameState,
    player: PlayerState,
) -> tuple[PlayerState, ...]:
    return tuple(
        player if candidate.player_id == player.player_id else candidate
        for candidate in state.players
    )


def _add_reveal_persuasion(
    frames: tuple[DecisionFrame, ...],
    amount: int,
) -> tuple[DecisionFrame, ...]:
    """Add Persuasion to the Reveal frame below serial choice frames."""

    for index in range(len(frames) - 1, -1, -1):
        context = dict(frames[index].context)
        persuasion = context.get("persuasion")
        if persuasion is None:
            continue
        if isinstance(persuasion, bool) or not isinstance(persuasion, int):
            raise RuntimeError("Reveal frame has invalid Persuasion")
        context["persuasion"] = persuasion + amount
        return (
            *frames[:index],
            replace(frames[index], context=tuple(sorted(context.items()))),
            *frames[index + 1 :],
        )
    raise RuntimeError("Reveal Spy choice is missing its Reveal frame")


def legal_reveal_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Return the always-available Reveal choice for the current turn owner."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    frame_parts = frame.frame_id.split(":")
    if (
        len(frame_parts) != 4
        or frame_parts[0] != "round"
        or frame_parts[2:] != ["turn", str(player)]
    ):
        return ()
    decision = frame.decision
    if not isinstance(decision, PlayerDecision) or decision.owner != player:
        return ()
    return (DomainAction(action_id="reveal_turn", actor=player),)


def begin_reveal_turn(state: GameState, action: DomainAction) -> RuleResult:
    """Reveal the hand and calculate its basic Persuasion and strength."""

    if action not in legal_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal turn")
    owner = state.players[action.actor]
    revealed = owner.hand
    cards = tuple(personal_card_for_instance(card_id) for card_id in revealed)
    cards_in_play = (*owner.in_play, *revealed)
    reveal_effects = tuple(
        effect
        for card_id, card in zip(revealed, cards, strict=True)
        for effect in card.reveal_effects
        if (not effect.requires_high_council or owner.high_council)
        and (not effect.requires_swordmaster or owner.swordmaster_acquired)
        and len(owner.spy_post_ids) >= effect.minimum_spies_placed
        and (
            effect.required_faction_bond is None
            or has_faction_bond(
                cards_in_play,
                card_id,
                Faction(effect.required_faction_bond.value),
            )
        )
    )
    persuasion = sum(card.reveal_persuasion for card in cards) + sum(
        effect.persuasion
        * (
            sum(
                Faction(effect.per_revealed_faction.value) in card.factions
                for card in cards
            )
            if effect.per_revealed_faction is not None
            else 1
        )
        for effect in reveal_effects
    )
    if owner.high_council:
        persuasion += 2
    if "assembly_hall" in owner.agent_locations:
        persuasion += 1

    sword_strength = sum(card.reveal_strength for card in cards)
    units = owner.troops_conflict + owner.sandworms_conflict
    strength = 0
    if units > 0:
        strength = (
            owner.troops_conflict * 2 + owner.sandworms_conflict * 3 + sword_strength
        )
    next_owner = replace(
        owner,
        resources=replace(
            owner.resources,
            solari=owner.resources.solari
            + sum(effect.solari for effect in reveal_effects),
            spice=owner.resources.spice
            + sum(effect.spice for effect in reveal_effects),
            water=owner.resources.water
            + sum(effect.water for effect in reveal_effects),
        ),
    )
    next_owner, _ = recruit_troops(
        next_owner,
        sum(effect.recruit_troops for effect in reveal_effects),
    )
    next_owner = replace(
        next_owner,
        hand=(),
        in_play=(*owner.in_play, *revealed),
        combat_strength=strength,
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    context: list[tuple[str, ActionValue]] = [
        ("persuasion", persuasion),
        ("revealed_card_count", len(revealed)),
        ("strength", strength),
        ("turn_owner", action.actor),
    ]
    context.extend(
        (f"revealed_card_{index:03d}", card_id)
        for index, card_id in enumerate(revealed)
    )
    reveal_frame = DecisionFrame(
        frame_id=f"round:{state.round_number}:player:{action.actor}:reveal",
        decision=PlayerDecision(
            owner=action.actor,
            prompt="Resolve Reveal effects and acquire cards",
        ),
        context=tuple(sorted(context)),
    )
    choice_frames = tuple(
        DecisionFrame(
            frame_id=(
                f"round:{state.round_number}:player:{action.actor}:"
                f"reveal_spy:{card_id}:{effect.value}"
            ),
            decision=PlayerDecision(
                owner=action.actor,
                prompt=(
                    "Choose where to place a Spy for this Reveal effect"
                    if effect is PersonalCardRevealChoiceEffect.PLACE_SPY
                    else "Choose two Spies to recall or decline this Reveal effect"
                    if effect
                    is (
                        PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION
                    )
                    else "Choose a Spy to recall for this Reveal effect"
                ),
            ),
            context=(
                ("reveal_card_id", card_id),
                ("reveal_choice_effect", effect.value),
                ("turn_owner", action.actor),
            ),
        )
        for card_id, card in zip(revealed, cards, strict=True)
        for effect in card.reveal_choice_effects
        if effect is PersonalCardRevealChoiceEffect.PLACE_SPY
        or (
            effect
            in (
                PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED,
                PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION,
            )
            and len(owner.spy_post_ids) >= 2
        )
    )
    next_state = replace(
        state,
        players=players,
        decision_stack=(
            *state.decision_stack[:-1],
            reveal_frame,
            *reversed(choice_frames),
        ),
    )
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{action.actor}:reveal",
        kind="reveal_started",
        payload=(
            ("cards", len(revealed)),
            ("persuasion", persuasion),
            ("player", action.actor),
            ("strength", strength),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def current_reveal_context(state: GameState) -> dict[str, ActionValue]:
    """Return and validate the current Reveal resolution frame."""

    if not state.decision_stack:
        raise ValueError("there is no pending Reveal turn")
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision):
        raise ValueError("the current decision is not a Reveal turn")
    context = dict(frame.context)
    required = {"persuasion", "revealed_card_count", "strength", "turn_owner"}
    if not required.issubset(context):
        raise ValueError("the current decision is not a Reveal turn")
    return context


def legal_finish_reveal_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the explicit action that ends the current Reveal turn."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        context = current_reveal_context(state)
    except ValueError:
        return ()
    owner = context["turn_owner"]
    if isinstance(owner, bool) or not isinstance(owner, int) or owner != player:
        return ()
    return (DomainAction(action_id="finish_reveal", actor=player),)


def finish_reveal_turn(state: GameState, action: DomainAction) -> RuleResult:
    """Clean up in-play cards and advance or enter Combat."""

    if action not in legal_finish_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal cleanup")
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        has_revealed=True,
        discard_pile=(*owner.discard_pile, *owner.in_play),
        in_play=(),
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    next_player = _next_unrevealed_player(players, action.actor)
    if next_player is None:
        phase = GamePhase.COMBAT
        decision_stack = state.decision_stack[:-1]
    else:
        phase = GamePhase.PLAYER_TURNS
        decision_stack = (
            *state.decision_stack[:-1],
            DecisionFrame(
                frame_id=f"round:{state.round_number}:turn:{next_player}",
                decision=PlayerDecision(
                    owner=next_player,
                    prompt="Choose an Agent turn or Reveal turn",
                ),
                context=(
                    ("round", state.round_number),
                    ("turn_owner", next_player),
                ),
            ),
        )
    next_state = replace(
        state,
        phase=phase,
        players=players,
        reveal_order=(*state.reveal_order, action.actor),
        decision_stack=decision_stack,
    )
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{action.actor}:reveal_finished",
        kind="reveal_finished",
        payload=(("player", action.actor),),
    )
    return RuleResult(state=next_state, events=(event,))


def _next_unrevealed_player(
    players: tuple[PlayerState, ...],
    owner: int,
) -> int | None:
    for offset in range(1, len(players) + 1):
        candidate = (owner + offset) % len(players)
        player = players[candidate]
        if not player.has_revealed:
            return candidate
    return None
