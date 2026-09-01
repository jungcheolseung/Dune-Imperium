"""Start and score the basic portion of an Uprising Reveal turn."""

from dataclasses import replace

from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.types import (
    PersonalCardRevealChoiceEffect,
    PersonalCardRevealEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.card_bonds import has_faction_bond
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effects import recruit_troops
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
    reset_turn_counters,
)
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    lose_faction_influence,
)
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.intrigue_triggers import expire_reveal_faceup_intrigue
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
        if len(post_ids) < 2:
            # The two-Spy condition is judged again when this queued choice
            # resolves in the owner's chosen Reveal order [Main p. 12]
            # [Main pp. 9, 20]; a freely ordered recall (for example In High
            # Places) can leave fewer than two, and the required recall and
            # draw are then unavailable.
            return (
                DomainAction(action_id="decline_reveal_spy_recall", actor=player),
            )
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
        units_deployed_turn=owner.units_deployed_turn + 1,
    )
    remaining = state.decision_stack[:-1]
    remaining = add_reveal_persuasion(remaining, -2)
    remaining = add_reveal_strength(remaining, strength_delta)
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
        remaining = add_reveal_persuasion(remaining, 2)
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
    # The self-trash is the cost of the Victory Point, so it is adjudicated
    # at resolution time [Main pp. 9, 20]: a card another effect already
    # trashed while this choice was pending can no longer pay it.
    if (
        len(state.players[player].completed_contract_ids) >= 4
        and context.get("reveal_card_id") in state.players[player].in_play
    ):
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
    remaining = add_reveal_optional_sword_strength(remaining, 4)
    strength_delta = next_strength - owner.combat_strength
    if strength_delta:
        remaining = add_reveal_strength(remaining, strength_delta)
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
    remaining = add_reveal_optional_sword_strength(remaining, 3)
    if counted_strength:
        remaining = add_reveal_strength(remaining, counted_strength)
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
        spice_spent_turn=owner.spice_spent_turn + 3,
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
        remaining = add_reveal_optional_sword_strength(remaining, 2)
        if counted_strength:
            remaining = add_reveal_strength(remaining, counted_strength)
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
    pending_draws = state.pending_intrigue_draws
    remaining = state.decision_stack[:-1]
    if (
        effect
        is PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED
    ):
        post_id = arguments.get("post_id")
        if not isinstance(post_id, str):
            raise RuntimeError("Reveal Spy choice has invalid post ID")
        next_owner = recall_spy(owner, post_id)
        events.append(_spy_recalled_event(state, action.actor, card_id, post_id))
        if intrigue_deck:
            next_owner = replace(
                next_owner,
                intrigue_cards=(*next_owner.intrigue_cards, intrigue_deck[0]),
            )
            intrigue_deck = intrigue_deck[1:]
            events.append(
                GameEvent(
                    event_id=f"{source}:intrigue_draw",
                    kind="intrigue_card_drawn",
                    payload=(("count", 1), ("player", action.actor)),
                )
            )
        else:
            pending_draws = (
                *pending_draws,
                (action.actor, 1, f"{source}:intrigue_draw"),
            )
    else:
        first_post_id = arguments.get("first_post_id")
        second_post_id = arguments.get("second_post_id")
        if not isinstance(first_post_id, str) or not isinstance(second_post_id, str):
            raise RuntimeError("Reveal Spy choice has invalid post IDs")
        next_owner = recall_spy(recall_spy(owner, first_post_id), second_post_id)
        remaining = add_reveal_persuasion(remaining, 2)
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
        pending_intrigue_draws=pending_draws,
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



def add_reveal_persuasion(
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


def add_reveal_strength(
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


def add_reveal_optional_sword_strength(
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


def _reveal_effect_is_eligible(
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    card: PersonalCardDefinition,
    effect: PersonalCardRevealEffect,
) -> bool:
    """Return whether one revealed card's automatic Reveal effect applies.

    Mirrors every gate ``begin_reveal_turn`` checks so the late-reveal path
    [FAQ p. 3] can re-adjudicate eligibility at arrival under the same
    rules.
    """

    return (
        (not effect.requires_high_council or owner.high_council)
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


def _eligible_reveal_effects(
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    card: PersonalCardDefinition,
) -> tuple[PersonalCardRevealEffect, ...]:
    """Return ``card``'s Reveal effects that currently apply."""

    return tuple(
        effect
        for effect in card.reveal_effects
        if _reveal_effect_is_eligible(owner, cards_in_play, card_id, card, effect)
    )


def _reveal_effect_persuasion(
    effect: PersonalCardRevealEffect,
    revealed_cards: tuple[PersonalCardDefinition, ...],
    completed_contracts: int,
) -> int:
    """Return one eligible effect's Persuasion over the given revealed set."""

    return effect.persuasion * (
        sum(
            Faction(effect.per_revealed_faction.value) in card.factions
            for card in revealed_cards
        )
        if effect.per_revealed_faction is not None
        else 1
    ) + effect.persuasion_per_completed_contract * completed_contracts


def _reveal_effect_strength(
    effect: PersonalCardRevealEffect,
    revealed_cards: tuple[PersonalCardDefinition, ...],
) -> int:
    """Return one eligible effect's own-card strength over the revealed set."""

    return effect.strength * (
        sum(
            Faction(effect.per_revealed_faction.value) in card.factions
            for card in revealed_cards
        )
        if effect.per_revealed_faction is not None
        else 1
    )


def _card_reveal_strength(
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    card: PersonalCardDefinition,
    revealed_cards: tuple[PersonalCardDefinition, ...],
) -> int:
    """Return one card's own strength before any sword cross-term is added."""

    return card.reveal_strength + sum(
        _reveal_effect_strength(effect, revealed_cards)
        for effect in _eligible_reveal_effects(owner, cards_in_play, card_id, card)
    )


def _reveal_choice_prompt(effect: PersonalCardRevealChoiceEffect) -> str:
    """Return the REVEAL_CHOICE frame prompt text for one choice effect."""

    return (
        "Choose Influence to lose and gain or decline this Reveal effect"
        if effect
        is PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE
        else "Pay three Spice for Influence or decline this Reveal effect"
        if effect is PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE
        else "Choose a Spy placement or gain two strength"
        if effect is PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH
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
        if effect is PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM
        else "Gain Spice or trash this card for one Victory Point"
        if effect
        is (
            PersonalCardRevealChoiceEffect
            .KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
        )
        else "Choose a Spy to recall for this Reveal effect"
    )


def _reveal_choice_effect_is_available(
    state: GameState,
    player: int,
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    effect: PersonalCardRevealChoiceEffect,
) -> bool:
    """Return whether one revealed card's choice effect currently opens.

    Mirrors every availability gate ``begin_reveal_turn`` checks, evaluated
    against whichever ``owner``/``state`` snapshot the caller passes, so the
    late-reveal path [FAQ p. 3] can push the same choice under the same
    rules at arrival time.
    """

    return (
        (
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
            and _can_summon_reveal_sandworm(state, player)
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


def _build_reveal_choice_frame(
    round_number: int,
    player: int,
    card_id: str,
    effect: PersonalCardRevealChoiceEffect,
) -> DecisionFrame:
    """Return the REVEAL_CHOICE frame for one revealed card's choice effect."""

    return DecisionFrame(
        kind=FrameKind.REVEAL_CHOICE,
        frame_id=(
            f"round:{round_number}:player:{player}:"
            f"reveal_spy:{card_id}:{effect.value}"
        ),
        decision=PlayerDecision(owner=player, prompt=_reveal_choice_prompt(effect)),
        context=(
            ("reveal_card_id", card_id),
            ("reveal_choice_effect", effect.value),
            ("turn_owner", player),
        ),
    )


def _apply_late_reveal_frame_update(
    frames: tuple[DecisionFrame, ...],
    card_id: str,
    persuasion_delta: int,
    sword_delta: int,
    *,
    counts_toward_combat: bool,
) -> tuple[DecisionFrame, ...]:
    """Record one late-arriving card on the Reveal frame, wherever it sits.

    A chance or choice frame can be layered above the Reveal frame when a
    card lands in hand mid-Reveal (a Personal-draw reshuffle chance, or the
    Intrigue choice frame an acquisition slot resolves under), so this scans
    for it by kind rather than assuming the stack top, mirroring
    ``replace_top_frame``'s single-frame replacement.
    """

    for index in range(len(frames) - 1, -1, -1):
        if frames[index].kind != FrameKind.REVEAL:
            continue
        context = dict(frames[index].context)
        count = context_int(context, "revealed_card_count", owner="Reveal frame")
        context[f"revealed_card_{count:03d}"] = card_id
        context["revealed_card_count"] = count + 1
        if persuasion_delta:
            context["persuasion"] = (
                context_int(context, "persuasion", owner="Reveal frame")
                + persuasion_delta
            )
        if sword_delta:
            context["sword_strength"] = (
                context_int(context, "sword_strength", owner="Reveal frame")
                + sword_delta
            )
            if counts_toward_combat:
                context["strength"] = (
                    context_int(context, "strength", owner="Reveal frame")
                    + sword_delta
                )
        return (
            *frames[:index],
            replace(frames[index], context=tuple(sorted(context.items()))),
            *frames[index + 1 :],
        )
    raise RuntimeError("late-reveal card is missing its Reveal frame")


def _insert_after_reveal_frame(
    frames: tuple[DecisionFrame, ...],
    new_frames: tuple[DecisionFrame, ...],
) -> tuple[DecisionFrame, ...]:
    """Insert frames directly above the Reveal frame, wherever it sits.

    A pending Intrigue choice frame above the Reveal frame must stay on top
    so the card that caused this late reveal is not buried mid-resolution;
    the new frames slot in between it and the Reveal frame instead.
    """

    for index in range(len(frames) - 1, -1, -1):
        if frames[index].kind == FrameKind.REVEAL:
            return (*frames[: index + 1], *new_frames, *frames[index + 1 :])
    raise RuntimeError("late-reveal choice is missing its Reveal frame")


def _late_reveal_one_card(
    state: GameState,
    player: int,
    card_id: str,
) -> RuleResult:
    """Immediately reveal one card that just entered ``player``'s hand.

    A card drawn or acquired to hand during a player's own Reveal turn is
    revealed at once and used in that same Reveal turn [FAQ p. 3]: it moves
    to ``in_play``, grants its own Reveal contribution evaluated over the
    now-larger revealed set, adds the increment its arrival causes to other
    already-revealed cards' cross-scaling effects, and opens its own choice
    effects. Amounts already granted to other cards are final and are never
    recomputed here, only added to.
    """

    owner = state.players[player]
    if card_id not in owner.hand:
        raise RuntimeError("late-reveal card is not in the owner's hand")
    card = personal_card_for_instance(card_id)
    context = _reveal_frame_context(state.decision_stack)
    previously_revealed_ids = tuple(
        context_str(context, f"revealed_card_{index:03d}", owner="Reveal frame")
        for index in range(
            context_int(context, "revealed_card_count", owner="Reveal frame")
        )
    )

    next_owner = replace(
        owner,
        hand=tuple(candidate for candidate in owner.hand if candidate != card_id),
        in_play=(*owner.in_play, card_id),
    )
    cards_in_play = next_owner.in_play
    completed_contracts = len(next_owner.completed_contract_ids)
    revealed_cards = tuple(
        personal_card_for_instance(instance_id)
        for instance_id in (*previously_revealed_ids, card_id)
    )

    eligible = _eligible_reveal_effects(next_owner, cards_in_play, card_id, card)
    persuasion_gain = card.reveal_persuasion + sum(
        _reveal_effect_persuasion(effect, revealed_cards, completed_contracts)
        for effect in eligible
    )
    own_strength = card.reveal_strength + sum(
        _reveal_effect_strength(effect, revealed_cards) for effect in eligible
    )
    other_positive_strength = sum(
        _card_reveal_strength(
            next_owner,
            cards_in_play,
            other_id,
            personal_card_for_instance(other_id),
            revealed_cards,
        )
        > 0
        for other_id in previously_revealed_ids
    )
    sword_delta = own_strength + sum(
        effect.strength_per_other_sword_card * other_positive_strength
        for effect in eligible
        if effect.strength_per_other_sword_card
    )

    persuasion_increment = 0
    for other_id in previously_revealed_ids:
        other_card = personal_card_for_instance(other_id)
        for effect in other_card.reveal_effects:
            if (
                effect.per_revealed_faction is None
                and not effect.strength_per_other_sword_card
            ):
                continue
            if not _reveal_effect_is_eligible(
                next_owner, cards_in_play, other_id, other_card, effect
            ):
                continue
            if (
                effect.per_revealed_faction is not None
                and Faction(effect.per_revealed_faction.value) in card.factions
            ):
                persuasion_increment += effect.persuasion
                sword_delta += effect.strength
            if effect.strength_per_other_sword_card and own_strength > 0:
                sword_delta += effect.strength_per_other_sword_card
    persuasion_delta = persuasion_gain + persuasion_increment

    next_owner = replace(
        next_owner,
        resources=replace(
            next_owner.resources,
            solari=next_owner.resources.solari
            + sum(effect.solari for effect in eligible),
            spice=next_owner.resources.spice
            + sum(effect.spice for effect in eligible),
            water=next_owner.resources.water
            + sum(effect.water for effect in eligible),
        ),
    )
    next_owner, _ = recruit_troops(
        next_owner, sum(effect.recruit_troops for effect in eligible)
    )

    units = next_owner.troops_conflict + next_owner.sandworms_conflict
    counts_toward_combat = units > 0
    if counts_toward_combat and sword_delta:
        next_owner = replace(
            next_owner, combat_strength=next_owner.combat_strength + sword_delta
        )

    source = f"round:{state.round_number}:player:{player}:reveal_card:{card_id}"
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
        decision_stack=_apply_late_reveal_frame_update(
            state.decision_stack,
            card_id,
            persuasion_delta,
            sword_delta,
            counts_toward_combat=counts_toward_combat,
        ),
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:late_reveal",
            kind="personal_card_late_revealed",
            payload=(
                ("card_id", card_id),
                ("persuasion", persuasion_delta),
                ("player", player),
                ("strength", sword_delta),
            ),
        )
    ]

    for effect in eligible:
        if effect.draw_intrigue == 0:
            continue
        drawn = draw_or_queue_intrigue_cards(
            next_state,
            player,
            effect.draw_intrigue,
            source=f"{source}:intrigue_draw",
        )
        next_state = drawn.state
        events.extend(drawn.events)
    for effect in eligible:
        if effect.influence_faction is None:
            continue
        gained = gain_faction_influence(
            next_state,
            player,
            Faction(effect.influence_faction.value),
            effect.influence,
            event_prefix=f"{source}:influence:{effect.influence_faction.value}",
        )
        next_state = gained.state
        events.extend(gained.events)

    latest_owner = next_state.players[player]
    choice_frames = tuple(
        _build_reveal_choice_frame(state.round_number, player, card_id, effect)
        for effect in card.reveal_choice_effects
        if _reveal_choice_effect_is_available(
            next_state, player, latest_owner, cards_in_play, card_id, effect
        )
    )
    if choice_frames:
        next_state = replace(
            next_state,
            decision_stack=_insert_after_reveal_frame(
                next_state.decision_stack, tuple(reversed(choice_frames))
            ),
        )

    return RuleResult(state=next_state, events=tuple(events))


def reveal_late_arrivals(
    state: GameState,
    player: int,
    card_ids: tuple[str, ...],
) -> RuleResult:
    """Immediately reveal personal cards that just entered a Reveal hand.

    A card drawn or acquired to hand during the owner's own Reveal turn is
    revealed and used at once [FAQ p. 3] rather than withheld to the next
    round. Cards are processed one at a time in the given (draw) order, so
    a later card's cross-scaling effects see every card revealed before it.
    """

    working = state
    events: list[GameEvent] = []
    for card_id in card_ids:
        step = _late_reveal_one_card(working, player, card_id)
        working = step.state
        events.extend(step.events)
    return RuleResult(state=working, events=tuple(events))


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
        for effect in _eligible_reveal_effects(owner, cards_in_play, card_id, card)
    )
    persuasion = sum(card.reveal_persuasion for card in cards) + sum(
        _reveal_effect_persuasion(effect, cards, len(owner.completed_contract_ids))
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
                _reveal_effect_strength(effect, cards)
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
        _build_reveal_choice_frame(state.round_number, action.actor, card_id, effect)
        for card_id, card in zip(revealed, cards, strict=True)
        for effect in card.reveal_choice_effects
        if _reveal_choice_effect_is_available(
            state, action.actor, owner, cards_in_play, card_id, effect
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
        intrigue_draw = draw_or_queue_intrigue_cards(
            next_state,
            action.actor,
            effect.draw_intrigue,
            source=(
                f"round:{state.round_number}:player:{action.actor}:"
                f"reveal_card:{card_id}:intrigue_draw"
            ),
        )
        next_state = intrigue_draw.state
        events.extend(intrigue_draw.events)
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


REVEAL_CONTEXT_KEYS = frozenset(
    {"persuasion", "revealed_card_count", "strength", "turn_owner"}
)


def current_reveal_context(state: GameState) -> dict[str, ActionValue]:
    """Return and validate the current Reveal resolution frame."""

    if not state.decision_stack:
        raise ValueError("there is no pending Reveal turn")
    frame = state.decision_stack[-1]
    if frame.kind != FrameKind.REVEAL or not isinstance(frame.decision, PlayerDecision):
        raise ValueError("the current decision is not a Reveal turn")
    context = dict(frame.context)
    if not REVEAL_CONTEXT_KEYS.issubset(context):
        raise ValueError("the Reveal frame is missing context")
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
    # Face-up Intrigue whose window was this Reveal turn expires with it.
    expired = expire_reveal_faceup_intrigue(state, action.actor)
    working = expired.state
    owner = working.players[action.actor]
    # A set-aside Imperium card not acquired by the end of this Reveal turn
    # leaves the game [FAQ p. 3].
    removed = owner.imperium_set_aside
    removal_events = tuple(
        GameEvent(
            event_id=(
                f"round:{working.round_number}:player:{action.actor}:"
                f"imperium_removed:{instance_id}"
            ),
            kind="imperium_card_removed",
            payload=(("instance_id", instance_id), ("player", action.actor)),
        )
        for instance_id in removed
    )
    if removed:
        working = replace(
            working, imperium_removed=(*working.imperium_removed, *removed)
        )
    next_owner = replace(
        owner,
        has_revealed=True,
        discard_pile=(*owner.discard_pile, *owner.in_play),
        in_play=(),
        imperium_set_aside=(),
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in working.players
    )
    next_player = _next_unrevealed_player(players, action.actor)
    if next_player is None:
        phase = GamePhase.COMBAT
        decision_stack = working.decision_stack[:-1]
    else:
        phase = GamePhase.PLAYER_TURNS
        players = reset_turn_counters(players, next_player)
        decision_stack = (
            *working.decision_stack[:-1],
            DecisionFrame(
                kind=FrameKind.TURN,
                frame_id=f"round:{working.round_number}:turn:{next_player}",
                decision=PlayerDecision(
                    owner=next_player,
                    prompt="Choose an Agent turn or Reveal turn",
                ),
                context=(
                    ("round", working.round_number),
                    ("turn_owner", next_player),
                ),
            ),
        )
    next_state = replace(
        working,
        phase=phase,
        players=players,
        reveal_order=(*working.reveal_order, action.actor),
        decision_stack=decision_stack,
    )
    event = GameEvent(
        event_id=f"round:{state.round_number}:player:{action.actor}:reveal_finished",
        kind="reveal_finished",
        payload=(("player", action.actor),),
    )
    return RuleResult(
        state=next_state, events=(*expired.events, *removal_events, event)
    )


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


def add_units_to_reveal(
    state: GameState,
    player: int,
    *,
    troops: int = 0,
    sandworms: int = 0,
) -> RuleResult:
    """Record units that entered the Conflict during ``player``'s Reveal turn.

    Mirrors Desert Power: the first units make the revealed sword strength
    count, later units add their own value only [Main p. 13].
    """

    owner = state.players[player]
    value = 2 * troops + 3 * sandworms
    if value == 0:
        return RuleResult(state=state)
    previous_units = owner.troops_conflict + owner.sandworms_conflict
    context = _reveal_frame_context(state.decision_stack)
    current_strength = context.get("strength")
    sword_strength = context.get("sword_strength", 0)
    optional_sword_strength = context.get("optional_sword_strength", 0)
    if (
        isinstance(current_strength, bool)
        or not isinstance(current_strength, int)
        or isinstance(sword_strength, bool)
        or not isinstance(sword_strength, int)
        or isinstance(optional_sword_strength, bool)
        or not isinstance(optional_sword_strength, int)
    ):
        raise RuntimeError("Reveal frame has invalid strength")
    strength_delta = (
        value
        if previous_units
        else value + sword_strength + optional_sword_strength - current_strength
    )
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison - troops,
        troops_conflict=owner.troops_conflict + troops,
        sandworms_conflict=owner.sandworms_conflict + sandworms,
        combat_strength=owner.combat_strength + strength_delta,
        units_deployed_turn=owner.units_deployed_turn + troops + sandworms,
    )
    return RuleResult(
        state=replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=add_reveal_strength(state.decision_stack, strength_delta),
        ),
        events=(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{player}:reveal:"
                    f"units:{owner.troops_conflict + owner.sandworms_conflict}"
                ),
                kind="reveal_strength_gained",
                payload=(("amount", strength_delta), ("player", player)),
            ),
        ),
    )



