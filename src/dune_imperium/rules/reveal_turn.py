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
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effects import recruit_troops
from dune_imperium.rules.frames import FrameKind, owned_top_frame, replace_player
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    lose_faction_influence,
)
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    is_spying_on_maker_space,
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
    if effect in (
        PersonalCardRevealChoiceEffect.PLACE_SPY,
        PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH,
    ):
        strength_choice = (
            ()
            if context.get("reveal_spy_recalled") is True
            or effect is PersonalCardRevealChoiceEffect.PLACE_SPY
            else (
                DomainAction(
                    action_id="gain_two_reveal_strength",
                    actor=player,
                ),
            )
        )
        if context.get("reveal_spy_recalled") is True or owner.spies_supply > 0:
            return (
                *strength_choice,
                *(
                    DomainAction(
                        action_id="place_reveal_spy",
                        actor=player,
                        arguments=(("post_id", post_id),),
                    )
                    for post_id in empty_observation_post_ids(state)
                )
            )
        return (
            *strength_choice,
            *(
                DomainAction(
                    action_id="recall_spy_for_reveal_placement",
                    actor=player,
                    arguments=(("post_id", post_id),),
                )
                for post_id in owner.spy_post_ids
            )
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


def legal_reveal_influence_exchange_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional Influence cost-and-reward choices for a Reveal card."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE.value
    ):
        return ()
    actions: list[DomainAction] = [
        DomainAction(action_id="decline_reveal_influence_exchange", actor=player)
    ]
    owner = state.players[player]
    for lost_faction in Faction:
        if influence_amount(owner.influence, lost_faction) == 0:
            continue
        recipients = alliance_recipients_after_influence_loss(
            state,
            player,
            lost_faction,
        )
        recipient_options: tuple[int | None, ...] = (
            tuple(recipients) if len(recipients) > 1 else (None,)
        )
        for gained_faction in Faction:
            for recipient in recipient_options:
                arguments: tuple[tuple[str, ActionValue], ...] = (
                    ("gained_faction", gained_faction.value),
                    ("lost_faction", lost_faction.value),
                )
                if recipient is not None:
                    arguments = (
                        ("alliance_recipient", recipient),
                        *arguments,
                    )
                actions.append(
                    DomainAction(
                        action_id="exchange_reveal_influence",
                        actor=player,
                        arguments=arguments,
                    )
                )
    return tuple(actions)


def legal_reveal_spice_influence_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional three-Spice payments for Reveal Influence."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE.value
    ):
        return ()
    decline = DomainAction(
        action_id="decline_reveal_spice_influence",
        actor=player,
    )
    if state.players[player].resources.spice < 3:
        return (decline,)
    return (
        decline,
        *(
            DomainAction(
                action_id="pay_reveal_spice_influence",
                actor=player,
                arguments=(("faction", faction.value),),
            )
            for faction in Faction
        ),
    )


def legal_reveal_sandworm_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Desert Power's mutually exclusive Reveal choices."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM.value
    ):
        return ()
    actions: list[DomainAction] = [
        DomainAction(action_id="decline_reveal_sandworm", actor=player),
    ]
    if _can_summon_reveal_sandworm(state, player):
        actions.append(
            DomainAction(
                action_id="pay_reveal_water_for_sandworm",
                actor=player,
            )
        )
    return tuple(actions)


def apply_reveal_sandworm_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Resolve Desert Power's Persuasion-or-sandworm Reveal choice."""

    if action not in legal_reveal_sandworm_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal sandworm choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal sandworm frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}"
    )
    if action.action_id == "decline_reveal_sandworm":
        return RuleResult(
            state=replace(state, decision_stack=state.decision_stack[:-1]),
            events=(
                GameEvent(
                    event_id=f"{source}:sandworm_declined",
                    kind="reveal_sandworm_declined",
                    payload=(("card_id", card_id), ("player", action.actor)),
                ),
            ),
        )

    if not _can_summon_reveal_sandworm(state, action.actor):
        raise RuntimeError("Desert Power sandworm choice is unavailable")
    owner = state.players[action.actor]
    previous_units = owner.troops_conflict + owner.sandworms_conflict
    reveal_context = _reveal_frame_context(state.decision_stack[:-1])
    current_strength = reveal_context.get("strength")
    sword_strength = reveal_context.get("sword_strength", 0)
    optional_sword_strength = reveal_context.get("optional_sword_strength", 0)
    if (
        isinstance(current_strength, bool)
        or not isinstance(current_strength, int)
        or isinstance(sword_strength, bool)
        or not isinstance(sword_strength, int)
        or isinstance(optional_sword_strength, bool)
        or not isinstance(optional_sword_strength, int)
    ):
        raise RuntimeError("Reveal sandworm frame has invalid strength")
    strength_delta = (
        3
        if previous_units
        else 3 + sword_strength + optional_sword_strength - current_strength
    )
    next_owner = replace(
        owner,
        resources=replace(owner.resources, water=owner.resources.water - 1),
        sandworms_conflict=owner.sandworms_conflict + 1,
        combat_strength=owner.combat_strength + strength_delta,
    )
    remaining = state.decision_stack[:-1]
    remaining = _add_reveal_persuasion(remaining, -2)
    remaining = _add_reveal_strength(remaining, strength_delta)
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=remaining,
        ),
        events=(
            GameEvent(
                event_id=f"{source}:sandworm",
                kind="reveal_sandworm_deployed",
                payload=(
                    ("amount", 1),
                    ("card_id", card_id),
                    ("player", action.actor),
                    ("water", 1),
                ),
            ),
            GameEvent(
                event_id=f"{source}:strength",
                kind="reveal_strength_gained",
                payload=(
                    ("amount", strength_delta),
                    ("card_id", card_id),
                    ("player", action.actor),
                ),
            ),
        ),
    )


def legal_reveal_card_trash_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return optional Emperor-card trash payments for the current Reveal."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != (
            PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH.value
        )
    ):
        return ()
    source_card_id = context.get("reveal_card_id")
    if not isinstance(source_card_id, str):
        raise RuntimeError("Reveal trash frame has invalid card ID")
    return (
        DomainAction(action_id="decline_reveal_card_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_reveal_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in state.players[player].in_play
            if card_id != source_card_id
            and Faction.EMPEROR in personal_card_for_instance(card_id).factions
        ),
    )


def legal_reveal_troop_retreat_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the optional two-troop Reveal retreat payment."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH.value
    ):
        return ()
    decline = DomainAction(action_id="decline_reveal_troop_retreat", actor=player)
    if state.players[player].troops_conflict < 2:
        return (decline,)
    return (
        decline,
        DomainAction(action_id="retreat_two_troops_for_reveal", actor=player),
    )


def legal_corrinth_city_reveal_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Corrinth City's mutually exclusive Reveal choices."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL.value
    ):
        return ()
    owner = state.players[player]
    take_seat = (
        ()
        if owner.high_council or owner.resources.solari < 5
        else (
            DomainAction(
                action_id="take_high_council_from_reveal",
                actor=player,
            ),
        )
    )
    return (
        DomainAction(action_id="gain_five_reveal_solari", actor=player),
        *take_seat,
    )


def apply_corrinth_city_reveal(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Gain five Solari or pay five for a High Council seat."""

    if action not in legal_corrinth_city_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Corrinth City Reveal choice")
    context = dict(state.decision_stack[-1].context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Corrinth City Reveal frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}"
    )
    owner = state.players[action.actor]
    remaining = state.decision_stack[:-1]
    if action.action_id == "gain_five_reveal_solari":
        next_owner = replace(
            owner,
            resources=replace(owner.resources, solari=owner.resources.solari + 5),
        )
        event = GameEvent(
            event_id=f"{source}:solari",
            kind="reveal_solari_gained",
            payload=(
                ("amount", 5),
                ("card_id", card_id),
                ("player", action.actor),
            ),
        )
    else:
        if owner.high_council or owner.resources.solari < 5:
            raise RuntimeError("Corrinth City High Council choice is unavailable")
        next_owner = replace(
            owner,
            high_council=True,
            resources=replace(owner.resources, solari=owner.resources.solari - 5),
        )
        remaining = _add_reveal_persuasion(remaining, 2)
        event = GameEvent(
            event_id=f"{source}:high_council",
            kind="high_council_acquired",
            payload=(
                ("card_id", card_id),
                ("player", action.actor),
                ("solari", 5),
            ),
        )
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=remaining,
        ),
        events=(event,),
    )


def legal_contract_reveal_choice_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the CHOAM choice between Spice and a self-trash VP."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or context.get("reveal_choice_effect")
        != (
            PersonalCardRevealChoiceEffect
            .KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS.value
        )
    ):
        return ()
    actions = [
        DomainAction(action_id="keep_contract_reveal_spice", actor=player)
    ]
    if len(state.players[player].completed_contract_ids) >= 4:
        actions.append(
            DomainAction(action_id="trash_contract_reveal_for_vp", actor=player)
        )
    return tuple(actions)


def apply_contract_reveal_choice(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Gain printed Spice or trash the card for one VP."""

    if action not in legal_contract_reveal_choice_actions(state, action.actor):
        raise ValueError("action is not a legal Contract-count Reveal choice")
    context = dict(state.decision_stack[-1].context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Contract-count Reveal choice has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}:contract_count_choice"
    )
    if action.action_id == "keep_contract_reveal_spice":
        card = personal_card_for_instance(card_id)
        spice = sum(effect.spice for effect in card.reveal_effects)
        owner = state.players[action.actor]
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                spice=owner.resources.spice + spice,
            ),
        )
        return RuleResult(
            state=replace(
                state.pop_decision(),
                players=replace_player(state.players, next_owner),
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:spice",
                    kind="contract_reveal_spice_gained",
                    payload=(
                        ("amount", spice),
                        ("card_id", card_id),
                        ("player", action.actor),
                    ),
                ),
            ),
        )

    prepared = state.pop_decision()
    trashed = trash_personal_card(
        prepared,
        action.actor,
        card_id,
        source=source,
    )
    owner = trashed.state.players[action.actor]
    next_owner = replace(owner, victory_points=owner.victory_points + 1)
    next_state = replace(
        trashed.state,
        players=replace_player(trashed.state.players, next_owner),
    )
    event = GameEvent(
        event_id=f"{source}:victory_point",
        kind="contract_reveal_card_trashed_for_vp",
        payload=(
            ("card_id", card_id),
            ("player", action.actor),
            ("victory_points", 1),
        ),
    )
    return RuleResult(state=next_state, events=(*trashed.events, event))


def apply_reveal_troop_retreat(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or retreat two troops for four Reveal strength."""

    if action not in legal_reveal_troop_retreat_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal troop-retreat choice")
    context = dict(state.decision_stack[-1].context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal troop-retreat frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}"
    )
    if action.action_id == "decline_reveal_troop_retreat":
        return RuleResult(
            state=replace(state, decision_stack=state.decision_stack[:-1]),
            events=(
                GameEvent(
                    event_id=f"{source}:troop_retreat_declined",
                    kind="reveal_troop_retreat_declined",
                    payload=(("card_id", card_id), ("player", action.actor)),
                ),
            ),
        )

    owner = state.players[action.actor]
    if owner.troops_conflict < 2:
        raise RuntimeError("Reveal troop-retreat payment requires two troops")
    remaining_units = owner.troops_conflict - 2 + owner.sandworms_conflict
    next_strength = owner.combat_strength if remaining_units else 0
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison + 2,
        troops_conflict=owner.troops_conflict - 2,
        combat_strength=next_strength,
    )
    remaining = state.decision_stack[:-1]
    remaining = _add_reveal_optional_sword_strength(remaining, 4)
    strength_delta = next_strength - owner.combat_strength
    if strength_delta:
        remaining = _add_reveal_strength(remaining, strength_delta)
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=remaining,
        ),
        events=(
            GameEvent(
                event_id=f"{source}:troops_retreated",
                kind="troops_retreated",
                payload=(("count", 2), ("player", action.actor)),
            ),
            GameEvent(
                event_id=f"{source}:strength",
                kind="reveal_strength_gained",
                payload=(
                    ("amount", 4),
                    ("card_id", card_id),
                    ("player", action.actor),
                ),
            ),
        ),
    )


def apply_reveal_card_trash(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or trash another Emperor card for three Reveal strength."""

    if action not in legal_reveal_card_trash_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal card trash choice")
    context = dict(state.decision_stack[-1].context)
    source_card_id = context.get("reveal_card_id")
    if not isinstance(source_card_id, str):
        raise RuntimeError("Reveal trash frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{source_card_id}"
    )
    if action.action_id == "decline_reveal_card_trash":
        return RuleResult(
            state=replace(state, decision_stack=state.decision_stack[:-1]),
            events=(
                GameEvent(
                    event_id=f"{source}:trash_declined",
                    kind="reveal_card_trash_declined",
                    payload=(("card_id", source_card_id), ("player", action.actor)),
                ),
            ),
        )

    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal trash choice has invalid card ID")
    trashed = trash_personal_card(
        state,
        action.actor,
        card_id,
        source=source,
    )
    owner = trashed.state.players[action.actor]
    counted_strength = 3 if owner.troops_conflict + owner.sandworms_conflict else 0
    next_owner = replace(
        owner,
        combat_strength=owner.combat_strength + counted_strength,
    )
    remaining = trashed.state.decision_stack[:-1]
    remaining = _add_reveal_optional_sword_strength(remaining, 3)
    if counted_strength:
        remaining = _add_reveal_strength(remaining, counted_strength)
    return RuleResult(
        state=replace(
            trashed.state,
            players=replace_player(trashed.state.players, next_owner),
            decision_stack=remaining,
        ),
        events=(
            *trashed.events,
            GameEvent(
                event_id=f"{source}:strength",
                kind="reveal_strength_gained",
                payload=(
                    ("amount", 3),
                    ("card_id", source_card_id),
                    ("player", action.actor),
                ),
            ),
        ),
    )


def apply_reveal_spice_influence(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or pay three Spice and gain one chosen Faction Influence."""

    if action not in legal_reveal_spice_influence_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal Spice payment")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal Spice-payment frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}:spice_influence"
    )
    if action.action_id == "decline_reveal_spice_influence":
        return RuleResult(
            state=replace(state, decision_stack=state.decision_stack[:-1]),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="reveal_spice_influence_declined",
                    payload=(("card_id", card_id), ("player", action.actor)),
                ),
            ),
        )

    faction_value = dict(action.arguments).get("faction")
    if not isinstance(faction_value, str):
        raise RuntimeError("Reveal Spice payment has invalid Faction")
    owner = state.players[action.actor]
    if owner.resources.spice < 3:
        raise RuntimeError("Reveal Influence payment requires three Spice")
    owner = replace(
        owner,
        resources=replace(owner.resources, spice=owner.resources.spice - 3),
    )
    paid = replace(state, players=replace_player(state.players, owner))
    gained = gain_faction_influence(
        paid,
        action.actor,
        Faction(faction_value),
        1,
        event_prefix=f"{source}:gained:{faction_value}",
    )
    payment_event = GameEvent(
        event_id=f"{source}:paid",
        kind="reveal_spice_paid",
        payload=(
            ("amount", 3),
            ("card_id", card_id),
            ("player", action.actor),
        ),
    )
    return RuleResult(
        state=replace(
            gained.state,
            decision_stack=gained.state.decision_stack[:-1],
        ),
        events=(payment_event, *gained.events),
    )


def apply_reveal_influence_exchange(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or atomically pay and resolve a Reveal Influence exchange."""

    if action not in legal_reveal_influence_exchange_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal Influence exchange")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal Influence frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{card_id}:influence_exchange"
    )
    if action.action_id == "decline_reveal_influence_exchange":
        return RuleResult(
            state=replace(state, decision_stack=state.decision_stack[:-1]),
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="reveal_influence_exchange_declined",
                    payload=(("card_id", card_id), ("player", action.actor)),
                ),
            ),
        )

    arguments = dict(action.arguments)
    lost_value = arguments.get("lost_faction")
    gained_value = arguments.get("gained_faction")
    recipient = arguments.get("alliance_recipient")
    if not isinstance(lost_value, str) or not isinstance(gained_value, str):
        raise RuntimeError("Reveal Influence exchange has invalid Factions")
    if recipient is not None and (
        isinstance(recipient, bool) or not isinstance(recipient, int)
    ):
        raise RuntimeError("Reveal Influence exchange has invalid recipient")
    lost = lose_faction_influence(
        state,
        action.actor,
        Faction(lost_value),
        1,
        event_prefix=f"{source}:lost:{lost_value}",
        alliance_recipient=recipient,
    )
    gained = gain_faction_influence(
        lost.state,
        action.actor,
        Faction(gained_value),
        1,
        event_prefix=f"{source}:gained:{gained_value}",
    )
    return RuleResult(
        state=replace(
            gained.state,
            decision_stack=gained.state.decision_stack[:-1],
        ),
        events=(*lost.events, *gained.events),
    )


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
    if action.action_id == "gain_two_reveal_strength":
        owner = state.players[action.actor]
        counted_strength = 2 if owner.troops_conflict + owner.sandworms_conflict else 0
        next_owner = replace(
            owner,
            combat_strength=owner.combat_strength + counted_strength,
        )
        remaining = state.decision_stack[:-1]
        remaining = _add_reveal_optional_sword_strength(remaining, 2)
        if counted_strength:
            remaining = _add_reveal_strength(remaining, counted_strength)
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, next_owner),
                decision_stack=remaining,
            ),
            events=(
                GameEvent(
                    event_id=f"{source}:strength",
                    kind="reveal_strength_gained",
                    payload=(
                        ("amount", 2),
                        ("card_id", card_id),
                        ("player", action.actor),
                    ),
                ),
            ),
        )
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
                players=replace_player(state.players, next_owner),
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
                players=replace_player(state.players, next_owner),
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


def _add_reveal_strength(
    frames: tuple[DecisionFrame, ...],
    amount: int,
) -> tuple[DecisionFrame, ...]:
    """Add counted strength to the Reveal frame below serial choices."""

    for index in range(len(frames) - 1, -1, -1):
        context = dict(frames[index].context)
        strength = context.get("strength")
        if strength is None:
            continue
        if isinstance(strength, bool) or not isinstance(strength, int):
            raise RuntimeError("Reveal frame has invalid strength")
        context["strength"] = strength + amount
        return (
            *frames[:index],
            replace(frames[index], context=tuple(sorted(context.items()))),
            *frames[index + 1 :],
        )
    raise RuntimeError("Reveal trash choice is missing its Reveal frame")


def _add_reveal_optional_sword_strength(
    frames: tuple[DecisionFrame, ...],
    amount: int,
) -> tuple[DecisionFrame, ...]:
    """Record a chosen sword bonus even when no unit currently counts it."""

    for index in range(len(frames) - 1, -1, -1):
        context = dict(frames[index].context)
        if "strength" not in context or "persuasion" not in context:
            continue
        optional_strength = context.get("optional_sword_strength", 0)
        if (
            isinstance(optional_strength, bool)
            or not isinstance(optional_strength, int)
        ):
            raise RuntimeError("Reveal frame has invalid optional sword strength")
        context["optional_sword_strength"] = optional_strength + amount
        return (
            *frames[:index],
            replace(frames[index], context=tuple(sorted(context.items()))),
            *frames[index + 1 :],
        )
    raise RuntimeError("Reveal choice is missing its Reveal frame")


def _can_summon_reveal_sandworm(state: GameState, player: int) -> bool:
    """Return whether Desert Power can currently deploy its sandworm."""

    owner = state.players[player]
    return (
        owner.maker_hooks
        and owner.resources.water >= 1
        and bool(state.current_conflict_ids)
        and not current_conflict_is_shield_wall_protected(state)
    )


def _reveal_frame_context(
    frames: tuple[DecisionFrame, ...],
) -> dict[str, ActionValue]:
    """Find the active Reveal frame below any serial choice frames."""

    for frame in reversed(frames):
        if frame.kind == FrameKind.REVEAL:
            return dict(frame.context)
    raise RuntimeError("Reveal choice is missing its Reveal frame")


def legal_reveal_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Return the always-available Reveal choice for the current turn owner."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    if state.phase is not GamePhase.PLAYER_TURNS or not state.decision_stack:
        return ()
    if owned_top_frame(state, FrameKind.TURN, player) is None:
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
        (card_id, effect)
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
        and (
            not effect.requires_spying_on_maker_space
            or is_spying_on_maker_space(owner)
        )
        and not (
            len(owner.completed_contract_ids) >= 4
            and effect.spice > 0
            and (
                PersonalCardRevealChoiceEffect
                .KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
                in card.reveal_choice_effects
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
        + effect.persuasion_per_completed_contract
        * len(owner.completed_contract_ids)
        for _, effect in reveal_effects
    )
    if owner.high_council:
        persuasion += 2
    if "assembly_hall" in owner.agent_locations:
        persuasion += 1

    card_strengths = tuple(
        (
            card_id,
            card.reveal_strength
            + sum(
                effect.strength
                * (
                    sum(
                        Faction(effect.per_revealed_faction.value)
                        in revealed_card.factions
                        for revealed_card in cards
                    )
                    if effect.per_revealed_faction is not None
                    else 1
                )
                for effect_card_id, effect in reveal_effects
                if effect_card_id == card_id
            ),
        )
        for card_id, card in zip(revealed, cards, strict=True)
    )
    sword_strength = sum(strength for _, strength in card_strengths) + sum(
        effect.strength_per_other_sword_card
        * sum(
            strength > 0
            for card_id, strength in card_strengths
            if card_id != effect_card_id
        )
        for effect_card_id, effect in reveal_effects
    )
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
            + sum(effect.solari for _, effect in reveal_effects),
            spice=owner.resources.spice
            + sum(effect.spice for _, effect in reveal_effects),
            water=owner.resources.water
            + sum(effect.water for _, effect in reveal_effects),
        ),
    )
    next_owner, _ = recruit_troops(
        next_owner,
        sum(effect.recruit_troops for _, effect in reveal_effects),
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
        ("optional_sword_strength", 0),
        ("persuasion", persuasion),
        ("revealed_card_count", len(revealed)),
        ("strength", strength),
        ("sword_strength", sword_strength),
        ("turn_owner", action.actor),
    ]
    context.extend(
        (f"revealed_card_{index:03d}", card_id)
        for index, card_id in enumerate(revealed)
    )
    reveal_frame = DecisionFrame(
        kind=FrameKind.REVEAL,
        frame_id=f"round:{state.round_number}:player:{action.actor}:reveal",
        decision=PlayerDecision(
            owner=action.actor,
            prompt="Resolve Reveal effects and acquire cards",
        ),
        context=tuple(sorted(context)),
    )
    choice_frames = tuple(
        DecisionFrame(
            kind=FrameKind.REVEAL_CHOICE,
            frame_id=(
                f"round:{state.round_number}:player:{action.actor}:"
                f"reveal_spy:{card_id}:{effect.value}"
            ),
            decision=PlayerDecision(
                owner=action.actor,
                prompt=(
                    "Choose Influence to lose and gain or decline this Reveal effect"
                    if effect
                    is (
                        PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE
                    )
                    else "Pay three Spice for Influence or decline this Reveal effect"
                    if effect
                    is PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE
                    else "Choose a Spy placement or gain two strength"
                    if effect
                    is PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH
                    else "Choose where to place a Spy for this Reveal effect"
                    if effect is PersonalCardRevealChoiceEffect.PLACE_SPY
                    else "Choose two Spies to recall or decline this Reveal effect"
                    if effect
                    is (
                        PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION
                    )
                    else "Trash another Emperor card or decline this Reveal effect"
                    if effect
                    is (
                        PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH
                    )
                    else "Retreat two troops for four strength or decline"
                    if effect
                    is (
                        PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH
                    )
                    else "Gain five Solari or pay five for a High Council seat"
                    if effect
                    is (
                        PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL
                    )
                    else "Keep two Persuasion or pay one Water for a sandworm"
                    if effect
                    is PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM
                    else "Gain Spice or trash this card for one Victory Point"
                    if effect
                    is (
                        PersonalCardRevealChoiceEffect
                        .KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
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
        if (
            effect
            is PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE
            and any(
                influence_amount(owner.influence, faction) > 0
                for faction in Faction
            )
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE
            and owner.resources.spice >= 3
        )
        or effect
        in (
            PersonalCardRevealChoiceEffect.PLACE_SPY,
            PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH,
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH
            and any(
                candidate_id != card_id
                and Faction.EMPEROR
                in personal_card_for_instance(candidate_id).factions
                for candidate_id in cards_in_play
            )
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH
            and owner.troops_conflict >= 2
        )
        or effect
        is PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM
            and _can_summon_reveal_sandworm(state, action.actor)
        )
        or (
            effect
            in (
                PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED,
                PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION,
            )
            and len(owner.spy_post_ids) >= 2
        )
        or (
            effect
            is (
                PersonalCardRevealChoiceEffect
                .KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
            )
            and len(owner.completed_contract_ids) >= 4
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
    events: list[GameEvent] = [event]
    for card_id, effect in reveal_effects:
        if effect.draw_intrigue == 0:
            continue
        drawn = next_state.intrigue_deck[: effect.draw_intrigue]
        draw_owner = next_state.players[action.actor]
        draw_owner = replace(
            draw_owner,
            intrigue_cards=(*draw_owner.intrigue_cards, *drawn),
        )
        next_state = replace(
            next_state,
            players=tuple(
                draw_owner if player.player_id == action.actor else player
                for player in next_state.players
            ),
            intrigue_deck=next_state.intrigue_deck[len(drawn) :],
        )
        events.append(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"reveal_card:{card_id}:intrigue_draw"
                ),
                kind="intrigue_card_drawn",
                payload=(("count", len(drawn)), ("player", action.actor)),
            )
        )
    for card_id, effect in reveal_effects:
        if effect.influence_faction is None:
            continue
        gained = gain_faction_influence(
            next_state,
            action.actor,
            Faction(effect.influence_faction.value),
            effect.influence,
            event_prefix=(
                f"round:{state.round_number}:player:{action.actor}:"
                f"reveal_card:{card_id}:influence:{effect.influence_faction.value}"
            ),
        )
        next_state = gained.state
        events.extend(gained.events)
    return RuleResult(state=next_state, events=tuple(events))


def current_reveal_context(state: GameState) -> dict[str, ActionValue]:
    """Return and validate the current Reveal resolution frame."""

    if not state.decision_stack:
        raise ValueError("there is no pending Reveal turn")
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.REVEAL or not isinstance(frame.decision, PlayerDecision):
        raise ValueError("the current decision is not a Reveal turn")
    return dict(frame.context)


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
                kind=FrameKind.TURN,
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
