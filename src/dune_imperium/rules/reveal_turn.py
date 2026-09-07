"""Start and score the basic portion of an Uprising Reveal turn.

Reveal effects resolve in any order the owner likes, with Persuasion usable
before, between and after them [Main p. 12]. Choice effects are queued as
serial ``REVEAL_CHOICE`` frames in card order; the owner may defer the frame
on top (``defer_reveal_choice``) to reach the ones below or the Reveal frame
itself, and later bring a deferred choice back with ``resume_reveal_choice``.
A resumed choice cannot be deferred again, so the Reveal cannot cycle. A
choice whose printed condition does not hold (too few Spies, not enough
Spice) also waits in the deferred queue instead of lapsing, because the
owner's later Reveal choices (a Spy placed, Spice gained) can still open it;
the Reveal turn cannot finish while a deferred choice is currently available,
and the ones still unavailable at the end simply never happen.
"""

from collections.abc import Mapping
from dataclasses import replace

from dune_imperium.content.bloodlines.sardaukar import skill_for_instance
from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
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
from dune_imperium.rules.combat_deployment import grant_combat_icon
from dune_imperium.rules.effects import recruit_shortfall_events, recruit_troops
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    frame_context,
    owned_top_frame,
    replace_player,
    replace_top_frame,
    reset_turn_counters,
    with_context,
)
from dune_imperium.rules.influence import (
    alliance_recipients_after_influence_loss,
    gain_faction_influence,
    influence_amount,
    lose_faction_influence,
)
from dune_imperium.rules.intrigue_deck import draw_or_queue_intrigue_cards
from dune_imperium.rules.intrigue_triggers import expire_reveal_faceup_intrigue
from dune_imperium.rules.planetologist import replace_sandworms, replaces_sandworms
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    is_spying_on_maker_space,
    place_spy,
    recall_spy,
)
from dune_imperium.rules.strength import units_strength


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
        PersonalCardRevealChoiceEffect.COMMAND_PLACE_SPY,
    ):
        strength_choice = (
            ()
            if context.get("reveal_spy_recalled") is True
            or effect
            in (
                PersonalCardRevealChoiceEffect.PLACE_SPY,
                PersonalCardRevealChoiceEffect.COMMAND_PLACE_SPY,
            )
            else (
                DomainAction(
                    action_id="gain_two_reveal_strength",
                    actor=player,
                ),
            )
        )
        if owner.spies_supply > 0:
            return (
                *strength_choice,
                *(
                    DomainAction(
                        action_id="place_reveal_spy",
                        actor=player,
                        arguments=(("post_id", post_id),),
                    )
                    for post_id in empty_observation_post_ids(state)
                ),
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
            ),
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
            return (DomainAction(action_id="decline_reveal_spy_recall", actor=player),)
        return tuple(
            DomainAction(
                action_id="recall_spy_for_reveal",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in post_ids
        )
    if effect is PersonalCardRevealChoiceEffect.MAY_RECALL_SPY_FOR_THREE_STRENGTH:
        # Arrakis Observer: "[recall a Spy] -> 3 swords", an arrow cost.
        return (
            DomainAction(action_id="decline_reveal_spy_recall", actor=player),
            *(
                DomainAction(
                    action_id="recall_spy_for_reveal",
                    actor=player,
                    arguments=(("post_id", post_id),),
                )
                for post_id in post_ids
            ),
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


def _frame_persuasion(frames: tuple[DecisionFrame, ...]) -> int | None:
    """Return the open Reveal frame's Persuasion total, if a Reveal is open."""

    for frame in reversed(frames):
        if frame.kind != FrameKind.REVEAL:
            continue
        value = dict(frame.context).get("persuasion")
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeError("Reveal frame has invalid Persuasion")
        return value
    return None


def legal_reveal_persuasion_or_contract_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Delivery Logistics: "1 Persuasion OR a contract"."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if (
        context.get("reveal_choice_effect")
        != PersonalCardRevealChoiceEffect.PERSUASION_OR_CONTRACT.value
    ):
        return ()
    return (
        DomainAction(action_id="gain_reveal_persuasion", actor=player),
        DomainAction(action_id="take_reveal_contract", actor=player),
    )


def apply_reveal_persuasion_or_contract(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Add one Persuasion to the Reveal, or open the Contract market."""

    if action not in legal_reveal_persuasion_or_contract_actions(state, action.actor):
        raise ValueError("action is not a legal Persuasion-or-Contract choice")
    context = dict(state.decision_stack[-1].context)
    card_id = context.get("reveal_card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Reveal choice frame has invalid card ID")
    source = f"round:{state.round_number}:player:{action.actor}:reveal_card:{card_id}"
    remaining = state.decision_stack[:-1]
    if action.action_id == "gain_reveal_persuasion":
        return RuleResult(
            state=replace(state, decision_stack=add_reveal_persuasion(remaining, 1)),
            events=(
                GameEvent(
                    event_id=f"{source}:persuasion",
                    kind="reveal_persuasion_gained",
                    payload=(
                        ("amount", 1),
                        ("card_id", card_id),
                        ("player", action.actor),
                    ),
                ),
            ),
        )
    from dune_imperium.rules.contracts import begin_contract_gain

    return begin_contract_gain(
        replace(state, decision_stack=remaining),
        action.actor,
        1,
        source=f"{source}:contract",
    )


def legal_reveal_influence_gain_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the Faction choices of a "gain 1 Influence of your choice" Reveal."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("reveal_choice_effect") not in (
        PersonalCardRevealChoiceEffect.COMMAND_GAIN_CHOSEN_INFLUENCE.value,
        PersonalCardRevealChoiceEffect.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH.value,
    ):
        return ()
    return tuple(
        DomainAction(
            action_id="gain_reveal_influence",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )


def apply_reveal_influence_gain(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Gain one Influence with the chosen Faction (Pointing the Way's Command)."""

    if action not in legal_reveal_influence_gain_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal Influence choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context.get("reveal_card_id")
    faction_value = dict(action.arguments).get("faction")
    if not isinstance(card_id, str) or not isinstance(faction_value, str):
        raise RuntimeError("Reveal Influence frame has invalid context")
    gained = gain_faction_influence(
        state,
        action.actor,
        Faction(faction_value),
        1,
        event_prefix=(
            f"round:{state.round_number}:player:{action.actor}:"
            f"reveal_card:{card_id}:influence:{faction_value}"
        ),
    )
    return RuleResult(
        state=replace(gained.state, decision_stack=gained.state.decision_stack[:-1]),
        events=gained.events,
    )


def legal_reveal_deployments(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the Combat-icon deployment during the owner's Reveal turn.

    "You may deploy any units you recruit this turn and up to two more from
    your garrison", never more than two from the garrison however many
    icons [Bloodlines p. 5]; troops and Sardaukar Commanders share the
    limit [Bloodlines p. 4].
    """

    frame = owned_top_frame(state, FrameKind.REVEAL, player)
    if frame is None:
        return ()
    context = dict(frame.context)
    if context.get("combat_deployment") is not True:
        return ()
    recruited = context_int(context, "reveal_troops_recruited", owner="Reveal frame")
    deployed = context_int(context, "reveal_units_deployed", owner="Reveal frame")
    remaining = recruited + 2 - deployed
    owner = state.players[player]
    actions: list[DomainAction] = []
    for action_id, garrison in (
        ("deploy_troops", owner.troops_garrison),
        ("deploy_commanders", owner.commanders_garrison),
    ):
        actions.extend(
            DomainAction(
                action_id=action_id, actor=player, arguments=(("count", count),)
            )
            for count in range(1, min(garrison, remaining) + 1)
        )
    return tuple(actions)


def apply_reveal_deployment(state: GameState, action: DomainAction) -> RuleResult:
    """Deploy garrison units during the Reveal turn (Combat icon)."""

    if action not in legal_reveal_deployments(state, action.actor):
        raise ValueError("action is not a legal Reveal deployment")
    count = dict(action.arguments)["count"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise RuntimeError("Reveal deployment has an invalid count")
    commanders = count if action.action_id == "deploy_commanders" else 0
    troops = count - commanders
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    context["reveal_units_deployed"] = (
        context_int(context, "reveal_units_deployed", owner="Reveal frame") + count
    )
    prepared = replace_top_frame(state, with_context(frame, context))
    counted = add_units_to_reveal(
        prepared, action.actor, troops=troops, commanders=commanders
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:reveal_deploy:"
            f"{context['reveal_units_deployed']}"
        ),
        kind="commanders_deployed" if commanders else "troops_deployed",
        payload=(("count", count), ("player", action.actor)),
    )
    return RuleResult(state=counted.state, events=(event, *counted.events))


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
    source = f"round:{state.round_number}:player:{action.actor}:reveal_card:{card_id}"
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
    if replaces_sandworms(owner):
        # Arrakis Planetologist: the water still buys the choice, the
        # sandworm becomes its replacement [Liet Kynes card].
        paid = replace(
            owner, resources=replace(owner.resources, water=owner.resources.water - 1)
        )
        remaining = add_reveal_persuasion(state.decision_stack[:-1], -2)
        popped = replace(
            state,
            players=replace_player(state.players, paid),
            decision_stack=remaining,
        )
        return replace_sandworms(popped, action.actor, 1, source=source)
    previous_units = owner.units_in_conflict
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
    effect_value = context.get("reveal_choice_effect")
    if effect_value not in (
        PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH.value,
        PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD.value,
        PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON.value,
        PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS.value,
    ):
        return ()
    source_card_id = context.get("reveal_card_id")
    if not isinstance(source_card_id, str):
        raise RuntimeError("Reveal trash frame has invalid card ID")
    owner = state.players[player]
    if effect_value == PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD.value:
        # Shrouded Counsel's "Command: trash a card": the black trash icon
        # targets hand, discard pile or in play and is optional [Main p. 20].
        candidates: tuple[str, ...] = (*owner.hand, *owner.discard_pile, *owner.in_play)
    elif effect_value in (
        PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON.value,
        PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS.value,
    ):
        # Disruption Tactics: "Trash this card -> Combat icon"; CHOAM
        # Demands: "trash this card -> Influence with each Faction" (arrows,
        # so optional); the card is in play while it is revealed.
        candidates = (source_card_id,) if source_card_id in owner.in_play else ()
    else:
        candidates = tuple(
            card_id
            for card_id in owner.in_play
            if card_id != source_card_id
            and Faction.EMPEROR in personal_card_for_instance(card_id).factions
        )
    return (
        DomainAction(action_id="decline_reveal_card_trash", actor=player),
        *(
            DomainAction(
                action_id="trash_reveal_card",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id in candidates
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
    if context.get("reveal_choice_effect") not in (
        PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH.value,
        PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION.value,
    ):
        return ()
    decline = DomainAction(action_id="decline_reveal_troop_retreat", actor=player)
    owner = state.players[player]
    # Sardaukar Commanders are troops for the retreat [Bloodlines p. 4];
    # ``commanders`` names their share of the two.
    return (
        decline,
        *(
            DomainAction(
                action_id="retreat_two_troops_for_reveal",
                actor=player,
                arguments=(() if commanders == 0 else (("commanders", commanders),)),
            )
            for commanders in range(3)
            if owner.troops_conflict >= 2 - commanders
            and owner.commanders_conflict >= commanders
        ),
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
    source = f"round:{state.round_number}:player:{action.actor}:reveal_card:{card_id}"
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
            PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS.value
        )
    ):
        return ()
    actions = [DomainAction(action_id="keep_contract_reveal_spice", actor=player)]
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
    source = f"round:{state.round_number}:player:{action.actor}:reveal_card:{card_id}"
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
    commanders = dict(action.arguments).get("commanders", 0)
    if isinstance(commanders, bool) or not isinstance(commanders, int):
        raise RuntimeError("Reveal troop-retreat has an invalid Commander count")
    troops = 2 - commanders
    if owner.troops_conflict < troops or owner.commanders_conflict < commanders:
        raise RuntimeError("Reveal troop-retreat payment requires two troops")
    remaining_units = owner.units_in_conflict - 2
    next_strength = owner.combat_strength if remaining_units else 0
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison + troops,
        troops_conflict=owner.troops_conflict - troops,
        commanders_garrison=owner.commanders_garrison + commanders,
        commanders_conflict=owner.commanders_conflict - commanders,
        combat_strength=next_strength,
    )
    remaining = state.decision_stack[:-1]
    strength_delta = next_strength - owner.combat_strength
    if strength_delta:
        remaining = add_reveal_strength(remaining, strength_delta)
    if context.get("reveal_choice_effect") == (
        PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION.value
    ):
        # Command Center (Bloodlines): "Retreat two troops -> +2 Persuasion".
        remaining = add_reveal_persuasion(remaining, 2)
        reward_event = GameEvent(
            event_id=f"{source}:persuasion",
            kind="reveal_persuasion_gained",
            payload=(("amount", 2), ("card_id", card_id), ("player", action.actor)),
        )
    else:
        remaining = add_reveal_optional_sword_strength(remaining, 4)
        reward_event = GameEvent(
            event_id=f"{source}:strength",
            kind="reveal_strength_gained",
            payload=(("amount", 4), ("card_id", card_id), ("player", action.actor)),
        )
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
            reward_event,
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
        f"round:{state.round_number}:player:{action.actor}:reveal_card:{source_card_id}"
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
    if (
        context.get("reveal_choice_effect")
        == PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD.value
    ):
        # Shrouded Counsel: the trash is the whole reward.
        return RuleResult(
            state=replace(
                trashed.state, decision_stack=trashed.state.decision_stack[:-1]
            ),
            events=trashed.events,
        )
    if (
        context.get("reveal_choice_effect")
        == PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON.value
    ):
        # Disruption Tactics: the Combat icon opens this Reveal's deployment
        # window [Bloodlines p. 5].
        popped = replace(
            trashed.state, decision_stack=trashed.state.decision_stack[:-1]
        )
        return RuleResult(
            state=grant_combat_icon(popped, action.actor), events=trashed.events
        )
    if context.get("reveal_choice_effect") == (
        PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS.value
    ):
        # CHOAM Demands: one Influence with each of the four Factions.
        working = replace(
            trashed.state, decision_stack=trashed.state.decision_stack[:-1]
        )
        influence_events: list[GameEvent] = []
        for faction in Faction:
            gained = gain_faction_influence(
                working,
                action.actor,
                faction,
                1,
                event_prefix=f"{source}:influence:{faction.value}",
            )
            working = gained.state
            influence_events.extend(gained.events)
        return RuleResult(state=working, events=(*trashed.events, *influence_events))
    owner = trashed.state.players[action.actor]
    counted_strength = 3 if owner.units_in_conflict else 0
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
    source = f"round:{state.round_number}:player:{action.actor}:reveal_card:{card_id}"

    arguments = dict(action.arguments)
    if action.action_id == "gain_two_reveal_strength":
        owner = state.players[action.actor]
        counted_strength = 2 if owner.units_in_conflict else 0
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
            events=(_spy_recalled_event(state, action.actor, card_id, post_id),),
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
    if effect is PersonalCardRevealChoiceEffect.MAY_RECALL_SPY_FOR_THREE_STRENGTH:
        post_id = arguments.get("post_id")
        if not isinstance(post_id, str):
            raise RuntimeError("Reveal Spy choice has invalid post ID")
        # Like Devious Strength: the swords count only while units are in
        # the Conflict [Main pp. 12-13].
        counted = 3 if owner.units_in_conflict else 0
        next_owner = replace(
            recall_spy(owner, post_id),
            combat_strength=owner.combat_strength + counted,
        )
        remaining = add_reveal_optional_sword_strength(remaining, 3)
        if counted:
            remaining = add_reveal_strength(remaining, counted)
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, next_owner),
                decision_stack=remaining,
            ),
            events=(
                _spy_recalled_event(state, action.actor, card_id, post_id),
                GameEvent(
                    event_id=f"{source}:strength",
                    kind="reveal_strength_gained",
                    payload=(
                        ("amount", 3),
                        ("card_id", card_id),
                        ("player", action.actor),
                    ),
                ),
            ),
        )
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
        if isinstance(optional_strength, bool) or not isinstance(
            optional_strength, int
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
        # Arrakis Planetologist's replacement ignores the Shield Wall.
        and (
            replaces_sandworms(owner)
            or not current_conflict_is_shield_wall_protected(state)
        )
    )


def _reveal_frame_context(
    frames: tuple[DecisionFrame, ...],
) -> dict[str, ActionValue]:
    """Find the active Reveal frame below any serial choice frames."""

    for frame in reversed(frames):
        if frame.kind == FrameKind.REVEAL:
            return dict(frame.context)
    raise RuntimeError("Reveal choice is missing its Reveal frame")


COMMAND_PERSUASION = 6
"""Persuasion a Reveal turn must generate for "Command (6+)" [Bloodlines p. 5]."""

# Tech tiles with a "Reveal Turn: Command (6+)" line, and the Reveal-frame
# key recording which have paid this Reveal.
_COMMAND_TECH = (
    ("delivery_bay", TechAbility.COMMAND_TWO_SOLARI),
    ("training_depot", TechAbility.COMMAND_TWO_STRENGTH),
)
_TECH_GRANTED_KEY = "tech_granted"
# Reveal-turn tile effects the owner still has to take, in any order the
# owner likes [Main p. 12] (OQ-044): Forbidden Weapons' mandatory choice and
# Panopticon's Spy placement.
TECH_PENDING_KEY = "tech_reveal_pending"


def tech_reveal_pending(context: Mapping[str, ActionValue]) -> tuple[str, ...]:
    """Return the tile ids whose Reveal-turn effect is still pending."""

    value = context.get(TECH_PENDING_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid pending tile effects")
    return tuple(key for key in value.split(",") if key)


def _reveal_effect_is_eligible(
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    card: PersonalCardDefinition,
    effect: PersonalCardRevealEffect,
    *,
    persuasion: int | None = None,
) -> bool:
    """Return whether one revealed card's automatic Reveal effect applies.

    Mirrors every gate ``begin_reveal_turn`` checks so the late-reveal path
    [FAQ p. 3] can re-adjudicate eligibility at arrival under the same
    rules. ``persuasion`` is the Reveal turn's current total for the
    Bloodlines "Command (6+)" gate; ``None`` (unknown yet) never satisfies
    it.
    """

    return (
        (not effect.requires_high_council or owner.high_council)
        and (
            not effect.requires_commander_in_conflict or owner.commanders_conflict >= 1
        )
        and (
            owner.troops_garrison + owner.commanders_garrison
            >= effect.minimum_garrisoned_units
        )
        and (
            not effect.requires_command
            or (persuasion is not None and persuasion >= COMMAND_PERSUASION)
        )
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
            not effect.requires_spying_on_maker_space or is_spying_on_maker_space(owner)
        )
        and not (
            len(owner.completed_contract_ids) >= 4
            and effect.spice > 0
            and (
                PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
                in card.reveal_choice_effects
            )
        )
    )


def _eligible_reveal_effects(
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    card_id: str,
    card: PersonalCardDefinition,
    *,
    persuasion: int | None = None,
) -> tuple[PersonalCardRevealEffect, ...]:
    """Return ``card``'s Reveal effects that currently apply."""

    return tuple(
        effect
        for effect in card.reveal_effects
        if _reveal_effect_is_eligible(
            owner, cards_in_play, card_id, card, effect, persuasion=persuasion
        )
    )


_GRANTED_EFFECTS_KEY = "granted_reveal_effects"


def _granted_reveal_effects(
    context: dict[str, ActionValue],
) -> dict[str, int | None]:
    """Decode which automatic Reveal effects already paid out this Reveal.

    Keys are ``card#index`` over ``card.reveal_effects``; the value is the
    completed-Contract count a per-Contract Persuasion effect was last paid
    for, or None for every other effect.
    """

    value = context.get(_GRANTED_EFFECTS_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid granted effects")
    granted: dict[str, int | None] = {}
    for item in value.split(","):
        if not item:
            continue
        key, separator, count = item.partition("=")
        granted[key] = int(count) if separator else None
    return granted


def _encode_granted(granted: dict[str, int | None]) -> str:
    return ",".join(
        key if count is None else f"{key}={count}" for key, count in granted.items()
    )


def _granted_entries(
    card_ids: tuple[str, ...],
    cards: tuple[PersonalCardDefinition, ...],
    owner: PlayerState,
    cards_in_play: tuple[str, ...],
    completed_contracts: int,
    *,
    persuasion: int | None = None,
) -> dict[str, int | None]:
    """Return the granted-effect entries for the cards' currently eligible effects."""

    entries: dict[str, int | None] = {}
    for card_id, card in zip(card_ids, cards, strict=True):
        for index, effect in enumerate(card.reveal_effects):
            if _reveal_effect_is_eligible(
                owner, cards_in_play, card_id, card, effect, persuasion=persuasion
            ):
                entries[f"{card_id}#{index}"] = (
                    completed_contracts
                    if effect.persuasion_per_completed_contract
                    else None
                )
    return entries


# Reveal gains the owner resolves as their own actions, in any order
# [Main p. 12] (OQ-045): troop recruits, Intrigue draws and resource gains.
# Their timing matters — the supply may fill (a troop lost to a Twisted
# Intrigue cost), a tile may arrive (Suspensor Suits through Rapid
# Engineering), or spice may be spent before Forbidden Weapons' trash — so
# they wait on the Reveal frame as ``kind|payload|source`` entries: the
# payload is a count for troops and Intrigue and ``solari/spice/water`` for
# resources.
REVEAL_GAINS_KEY = "reveal_pending_gains"
RevealGain = tuple[str, str, str]


def reveal_pending_gains(
    context: Mapping[str, ActionValue],
) -> tuple[RevealGain, ...]:
    """Return the (kind, payload, source) gains still waiting in this Reveal."""

    value = context.get(REVEAL_GAINS_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid pending gains")
    entries: list[RevealGain] = []
    for item in value.split(","):
        if not item:
            continue
        kind, payload, source = item.split("|", 2)
        entries.append((kind, payload, source))
    return tuple(entries)


def _encode_gains(entries: tuple[RevealGain, ...]) -> str:
    return ",".join(f"{kind}|{payload}|{source}" for kind, payload, source in entries)


def resource_gain_entry(
    source: str, *, solari: int = 0, spice: int = 0, water: int = 0
) -> RevealGain | None:
    """Return a pending resource gain, or None when nothing is gained."""

    if not (solari or spice or water):
        return None
    return ("resources", f"{solari}/{spice}/{water}", source)


def _resource_payload(payload: str) -> tuple[int, int, int]:
    solari, spice, water = (int(part) for part in payload.split("/"))
    return solari, spice, water


def _append_reveal_gains(
    frames: tuple[DecisionFrame, ...],
    entries: tuple[RevealGain, ...],
) -> tuple[DecisionFrame, ...]:
    """Queue more troop or Intrigue gains on the Reveal frame, wherever it sits."""

    if not entries:
        return frames
    position = _reveal_frame_position(frames)
    context = frame_context(frames[position])
    context[REVEAL_GAINS_KEY] = _encode_gains(
        (*reveal_pending_gains(context), *entries)
    )
    return (
        *frames[:position],
        with_context(frames[position], context),
        *frames[position + 1 :],
    )


def legal_reveal_gain_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the pending troop recruit and Intrigue draw of the owner's Reveal.

    Each resolves the oldest pending entry of its kind; entries of one kind
    are interchangeable (the same supply, the same deck), so no argument is
    needed. Both must be taken before the Reveal ends.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    frame = owned_top_frame(state, FrameKind.REVEAL, player)
    if frame is None:
        return ()
    pending = reveal_pending_gains(dict(frame.context))
    kinds = {kind for kind, _, _ in pending}
    actions: list[DomainAction] = []
    if "troops" in kinds:
        actions.append(DomainAction(action_id="recruit_reveal_troops", actor=player))
    if "intrigue" in kinds:
        actions.append(DomainAction(action_id="draw_reveal_intrigue", actor=player))
    # Resource gains differ in what they give, so each distinct bundle is
    # its own choice; equal bundles are interchangeable.
    for payload in dict.fromkeys(
        payload for kind, payload, _ in pending if kind == "resources"
    ):
        solari, spice, water = _resource_payload(payload)
        actions.append(
            DomainAction(
                action_id="gain_reveal_resources",
                actor=player,
                arguments=(("solari", solari), ("spice", spice), ("water", water)),
            )
        )
    return tuple(actions)


def apply_reveal_gain(state: GameState, action: DomainAction) -> RuleResult:
    """Recruit the next pending troops or draw the next pending Intrigue."""

    if action not in legal_reveal_gain_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal gain")
    player = action.actor
    frame = state.decision_stack[-1]
    context = frame_context(frame)
    pending = reveal_pending_gains(context)
    arguments = dict(action.arguments)
    if action.action_id == "gain_reveal_resources":
        wanted_payload = "/".join(
            str(arguments.get(name, 0)) for name in ("solari", "spice", "water")
        )
        index = next(
            i
            for i, (kind, payload, _) in enumerate(pending)
            if kind == "resources" and payload == wanted_payload
        )
    else:
        wanted = "troops" if action.action_id == "recruit_reveal_troops" else "intrigue"
        index = next(i for i, (kind, _, _) in enumerate(pending) if kind == wanted)
    kind, payload, source = pending[index]
    context[REVEAL_GAINS_KEY] = _encode_gains((*pending[:index], *pending[index + 1 :]))
    event_id = f"round:{state.round_number}:player:{player}:reveal_gain:{source}"
    owner = state.players[player]
    if kind == "resources":
        solari, spice, water = _resource_payload(payload)
        next_owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + solari,
                spice=owner.resources.spice + spice,
                water=owner.resources.water + water,
            ),
        )
        return RuleResult(
            state=replace(
                state,
                players=replace_player(state.players, next_owner),
                decision_stack=(
                    *state.decision_stack[:-1],
                    with_context(frame, context),
                ),
            ),
            events=(
                GameEvent(
                    event_id=event_id,
                    kind="reveal_resources_gained",
                    payload=(
                        ("player", player),
                        ("solari", solari),
                        ("source", source),
                        ("spice", spice),
                        ("water", water),
                    ),
                ),
            ),
        )
    count = int(payload)
    if kind == "troops":
        next_owner, recruited = recruit_troops(owner, count)
        context["reveal_troops_recruited"] = (
            context_int(context, "reveal_troops_recruited", owner="Reveal frame")
            + recruited
        )
        next_state = replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
        )
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=event_id,
                    kind="reveal_troops_recruited",
                    payload=(
                        ("player", player),
                        ("source", source),
                        ("troops", recruited),
                    ),
                ),
                *recruit_shortfall_events(event_id, player, count, recruited),
            ),
        )
    queued = replace(
        state,
        decision_stack=(*state.decision_stack[:-1], with_context(frame, context)),
    )
    drawn = draw_or_queue_intrigue_cards(queued, player, count, source=event_id)
    return RuleResult(state=drawn.state, events=drawn.events)


def _record_granted_effects(
    frames: tuple[DecisionFrame, ...],
    entries: dict[str, int | None],
) -> tuple[DecisionFrame, ...]:
    """Merge granted-effect entries into the Reveal frame, wherever it sits."""

    if not entries:
        return frames
    position = _reveal_frame_position(frames)
    context = frame_context(frames[position])
    granted = _granted_reveal_effects(context)
    granted.update(entries)
    context[_GRANTED_EFFECTS_KEY] = _encode_granted(granted)
    return (
        *frames[:position],
        with_context(frames[position], context),
        *frames[position + 1 :],
    )


def _add_reveal_sword(
    frames: tuple[DecisionFrame, ...],
    amount: int,
    *,
    counts_toward_combat: bool,
) -> tuple[DecisionFrame, ...]:
    """Add sword strength to the Reveal frame (counted only with a unit)."""

    position = _reveal_frame_position(frames)
    context = frame_context(frames[position])
    context["sword_strength"] = (
        context_int(context, "sword_strength", owner="Reveal frame") + amount
    )
    if counts_toward_combat:
        context["strength"] = (
            context_int(context, "strength", owner="Reveal frame") + amount
        )
    return (
        *frames[:position],
        with_context(frames[position], context),
        *frames[position + 1 :],
    )


def grant_late_reveal_effects(result: RuleResult) -> RuleResult:
    """Pay out revealed cards' automatic effects whose condition came true later.

    Automatic Reveal effects are applied when the Reveal begins. A printed
    condition that fails at that moment — two Spies placed, a High Council
    seat, a Faction Bond, spying on a Maker space, completed Contracts — can
    still be met by the owner's later choices in the same Reveal: a Spy
    placed by another card's Reveal effect, a seat bought through Corrinth
    City, a Fremen card arriving late, an Acquire Contract completed by a
    purchase. Reveal effects resolve in any order the owner likes
    [Main p. 12], so each such effect pays out the first time its condition
    holds during the Reveal and is recorded on the Reveal frame so it never
    repeats; per-Contract Persuasion pays the increment for newly completed
    Contracts (OQ-028).
    """

    state = result.state
    position = next(
        (
            index
            for index in range(len(state.decision_stack) - 1, -1, -1)
            if state.decision_stack[index].kind == FrameKind.REVEAL
        ),
        None,
    )
    if position is None:
        return result
    frame = state.decision_stack[position]
    if not isinstance(frame.decision, PlayerDecision):
        return result
    player = frame.decision.owner
    context = frame_context(frame)
    granted = _granted_reveal_effects(context)
    owner = state.players[player]
    revealed_ids = tuple(
        context_str(context, f"revealed_card_{index:03d}", owner="Reveal frame")
        for index in range(
            context_int(context, "revealed_card_count", owner="Reveal frame")
        )
    )
    revealed_cards = tuple(
        personal_card_for_instance(card_id) for card_id in revealed_ids
    )
    completed = len(owner.completed_contract_ids)
    units = owner.units_in_conflict
    frames = state.decision_stack
    next_owner = owner
    events: list[GameEvent] = list(result.events)
    late_gains: list[RevealGain] = []
    pending_influence: list[tuple[str, PersonalCardRevealEffect]] = []
    pending_trashes: list[tuple[str, str]] = []
    pending_combat_icons = 0
    newly_granted: dict[str, int | None] = {}
    for card_id, card in zip(revealed_ids, revealed_cards, strict=True):
        for index, effect in enumerate(card.reveal_effects):
            key = f"{card_id}#{index}"
            source = f"round:{state.round_number}:player:{player}:reveal_card:{card_id}"
            if effect.persuasion_per_completed_contract:
                counted = granted.get(key)
                if counted is None or completed <= counted:
                    continue
                delta = effect.persuasion_per_completed_contract * (completed - counted)
                frames = add_reveal_persuasion(frames, delta)
                newly_granted[key] = completed
                events.append(
                    GameEvent(
                        event_id=f"{source}:{index}:late_contracts:{completed}",
                        kind="reveal_effect_granted_late",
                        payload=(
                            ("card_id", card_id),
                            ("effect_index", index),
                            ("persuasion", delta),
                            ("player", player),
                        ),
                    )
                )
                continue
            if key in granted or key in newly_granted:
                continue
            if not _reveal_effect_is_eligible(
                next_owner,
                next_owner.in_play,
                card_id,
                card,
                effect,
                persuasion=_frame_persuasion(frames),
            ):
                continue
            persuasion = _reveal_effect_persuasion(effect, revealed_cards, completed)
            sword = _reveal_effect_strength(effect, revealed_cards)
            if persuasion:
                frames = add_reveal_persuasion(frames, persuasion)
            if sword:
                frames = _add_reveal_sword(
                    frames, sword, counts_toward_combat=units > 0
                )
            next_owner = replace(
                next_owner,
                combat_strength=next_owner.combat_strength + (sword if units else 0),
            )
            if effect.recruit_troops:
                late_gains.append(("troops", str(effect.recruit_troops), card_id))
            if effect.draw_intrigue:
                late_gains.append(("intrigue", str(effect.draw_intrigue), card_id))
            resources = resource_gain_entry(
                card_id, solari=effect.solari, spice=effect.spice, water=effect.water
            )
            if resources is not None:
                late_gains.append(resources)
            if effect.influence_faction is not None:
                pending_influence.append((f"{source}:{index}", effect))
            if effect.trashes_self:
                pending_trashes.append((f"{source}:{index}:late", card_id))
            if effect.grants_combat_icon:
                pending_combat_icons += 1
            newly_granted[key] = None
            events.append(
                GameEvent(
                    event_id=f"{source}:{index}:late",
                    kind="reveal_effect_granted_late",
                    payload=(
                        ("card_id", card_id),
                        ("effect_index", index),
                        ("persuasion", persuasion),
                        ("player", player),
                        ("solari", effect.solari),
                        ("spice", effect.spice),
                        ("strength", sword),
                        ("troops", effect.recruit_troops),
                        ("water", effect.water),
                    ),
                )
            )
    # Tech tiles whose Command (6+) line opens late pay the same way.
    late_persuasion = _frame_persuasion(frames)
    reveal_context = frame_context(frames[_reveal_frame_position(frames)])
    tech_granted = tuple(
        key
        for key in str(reveal_context.get(_TECH_GRANTED_KEY, "")).split(",")
        if key
    )
    late_tech = tuple(
        tech_id
        for tech_id, ability in _COMMAND_TECH
        if late_persuasion is not None
        and late_persuasion >= COMMAND_PERSUASION
        and tech_id not in tech_granted
        and has_tech(next_owner.tech_ids, ability)
    )
    for tech_id in late_tech:
        solari = 2 if tech_id == "delivery_bay" else 0
        sword = 2 if tech_id == "training_depot" else 0
        if sword:
            frames = _add_reveal_sword(frames, sword, counts_toward_combat=units > 0)
        next_owner = replace(
            next_owner,
            combat_strength=next_owner.combat_strength + (sword if units else 0),
        )
        tile_resources = resource_gain_entry(f"tech:{tech_id}", solari=solari)
        if tile_resources is not None:
            late_gains.append(tile_resources)
        events.append(
            GameEvent(
                event_id=f"round:{state.round_number}:player:{player}:tech:{tech_id}:late",
                kind="tech_reveal_bonus",
                payload=(
                    ("player", player),
                    ("solari", solari),
                    ("strength", sword),
                    ("tech_id", tech_id),
                ),
            )
        )
    if late_tech:
        position = _reveal_frame_position(frames)
        reveal_context = frame_context(frames[position])
        reveal_context[_TECH_GRANTED_KEY] = ",".join((*tech_granted, *late_tech))
        frames = (
            *frames[:position],
            with_context(frames[position], reveal_context),
            *frames[position + 1 :],
        )
    if not newly_granted and not late_tech:
        return result
    frames = _record_granted_effects(frames, newly_granted)
    frames = _append_reveal_gains(frames, tuple(late_gains))
    working = replace(
        state,
        players=replace_player(state.players, next_owner),
        decision_stack=frames,
    )
    for trash_source, trashed_card_id in pending_trashes:
        if trashed_card_id in working.players[player].in_play:
            trashed = trash_personal_card(
                working, player, trashed_card_id, source=trash_source
            )
            working = trashed.state
            events.extend(trashed.events)
    if pending_combat_icons:
        working = grant_combat_icon(working, player)
    for influence_source, effect in pending_influence:
        assert effect.influence_faction is not None
        gained = gain_faction_influence(
            working,
            player,
            Faction(effect.influence_faction.value),
            effect.influence,
            event_prefix=f"{influence_source}:influence:{effect.influence_faction.value}",
        )
        working = gained.state
        events.extend(gained.events)
    return RuleResult(state=working, events=tuple(events))


def _reveal_effect_persuasion(
    effect: PersonalCardRevealEffect,
    revealed_cards: tuple[PersonalCardDefinition, ...],
    completed_contracts: int,
) -> int:
    """Return one eligible effect's Persuasion over the given revealed set."""

    return (
        effect.persuasion
        * (
            sum(
                Faction(effect.per_revealed_faction.value) in card.factions
                for card in revealed_cards
            )
            if effect.per_revealed_faction is not None
            else 1
        )
        + effect.persuasion_per_completed_contract * completed_contracts
    )


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


def reveal_choice_prompt(effect: PersonalCardRevealChoiceEffect) -> str:
    """Return the REVEAL_CHOICE frame prompt text for one choice effect."""

    return (
        "Trash this card for one Influence with each Faction, or decline"
        if effect
        is (
            PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS
        )
        else "Choose one Persuasion or a Contract"
        if effect is PersonalCardRevealChoiceEffect.PERSUASION_OR_CONTRACT
        else "Recall a Spy for three swords or decline"
        if effect is PersonalCardRevealChoiceEffect.MAY_RECALL_SPY_FOR_THREE_STRENGTH
        else "Command: trash this card to acquire an Imperium Row card, or decline"
        if effect
        is PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD
        else "Trash this card for the Combat icon or decline"
        if effect is PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON
        else "Command: trash a card or decline"
        if effect is PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD
        else "Command: choose where to place a Spy"
        if effect is PersonalCardRevealChoiceEffect.COMMAND_PLACE_SPY
        else "Command: choose a Faction to gain one Influence with"
        if effect is PersonalCardRevealChoiceEffect.COMMAND_GAIN_CHOSEN_INFLUENCE
        else "Two or more Tech tiles: choose a Faction to gain one Influence with"
        if effect is PersonalCardRevealChoiceEffect.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH
        else "Retreat two troops for two Persuasion or decline"
        if effect
        is PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION
        else "Choose Influence to lose and gain or decline this Reveal effect"
        if effect is PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE
        else "Pay three Spice for Influence or decline this Reveal effect"
        if effect is PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE
        else "Choose a Spy placement or gain two strength"
        if effect is PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH
        else "Choose where to place a Spy for this Reveal effect"
        if effect is PersonalCardRevealChoiceEffect.PLACE_SPY
        else "Choose two Spies to recall or decline this Reveal effect"
        if effect
        is (PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION)
        else "Trash another Emperor card or decline this Reveal effect"
        if effect
        is (PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH)
        else "Retreat two troops for four strength or decline"
        if effect
        is (PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH)
        else "Gain five Solari or pay five for a High Council seat"
        if effect
        is (PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL)
        else "Keep two Persuasion or pay one Water for a sandworm"
        if effect is PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM
        else "Gain Spice or trash this card for one Victory Point"
        if effect
        is (
            PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
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
    *,
    persuasion: int | None = None,
) -> bool:
    """Return whether one revealed card's choice effect currently opens.

    Mirrors every availability gate ``begin_reveal_turn`` checks, evaluated
    against whichever ``owner``/``state`` snapshot the caller passes, so the
    late-reveal path [FAQ p. 3] can push the same choice under the same
    rules at arrival time. ``persuasion`` gates the Bloodlines "Command
    (6+)" choices; a deferred Command choice reopens once the Reveal's
    Persuasion reaches six [Bloodlines p. 5].
    """

    command_open = persuasion is not None and persuasion >= COMMAND_PERSUASION
    return (
        (
            effect
            in (
                PersonalCardRevealChoiceEffect.COMMAND_PLACE_SPY,
                PersonalCardRevealChoiceEffect.COMMAND_GAIN_CHOSEN_INFLUENCE,
            )
            and command_open
        )
        or (
            # Ixian Ambassador: judged when the choice opens (OQ-028); a
            # Plot acquisition during the Reveal can still meet it.
            effect is PersonalCardRevealChoiceEffect.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH
            and len(owner.tech_ids) >= 2
        )
        or (
            effect is PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD
            and command_open
            and bool((*owner.hand, *owner.discard_pile, *owner.in_play))
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION
            and owner.troops_conflict + owner.commanders_conflict >= 2
        )
        or effect is PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON
        or (
            effect is PersonalCardRevealChoiceEffect.MAY_RECALL_SPY_FOR_THREE_STRENGTH
            and len(owner.spy_post_ids) >= 1
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD
            and command_open
            and bool(state.imperium_row)
            and card_id in cards_in_play
        )
        or (
            effect
            is (
                PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS
            )
            and len(owner.completed_contract_ids) >= 4
            and card_id in cards_in_play
        )
        or (
            effect is PersonalCardRevealChoiceEffect.PERSUASION_OR_CONTRACT
            and state.config.choam_module
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE
            and any(
                influence_amount(owner.influence, faction) > 0 for faction in Faction
            )
        )
        or (
            effect is PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE
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
                and Faction.EMPEROR in personal_card_for_instance(candidate_id).factions
                for candidate_id in cards_in_play
            )
        )
        or (
            effect
            is PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH
            # Sardaukar Commanders are troops for the retreat [Bloodlines p. 4].
            and owner.troops_conflict + owner.commanders_conflict >= 2
        )
        or effect
        is PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL
        or (
            effect is PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM
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
                PersonalCardRevealChoiceEffect.KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
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
            f"round:{round_number}:player:{player}:reveal_spy:{card_id}:{effect.value}"
        ),
        decision=PlayerDecision(owner=player, prompt=reveal_choice_prompt(effect)),
        context=(
            ("reveal_card_id", card_id),
            ("reveal_choice_effect", effect.value),
            ("turn_owner", player),
        ),
    )


_DEFERRED_CHOICES_KEY = "deferred_reveal_choices"
_RESUMED_KEY = "reveal_choice_resumed"
_CHOICE_FRAME = "Reveal choice frame"


def _deferred_reveal_choices(
    context: dict[str, ActionValue],
) -> tuple[tuple[str, str], ...]:
    """Decode the Reveal frame's deferred (card, effect) queue, oldest first."""

    value = context.get(_DEFERRED_CHOICES_KEY, "")
    if not isinstance(value, str):
        raise RuntimeError("Reveal frame has invalid deferred choices")
    entries: list[tuple[str, str]] = []
    for item in value.split(","):
        if not item:
            continue
        card_id, _, effect = item.partition("|")
        entries.append((card_id, effect))
    return tuple(entries)


def _encode_deferred(entries: tuple[tuple[str, str], ...]) -> str:
    return ",".join(f"{card_id}|{effect}" for card_id, effect in entries)


def _reveal_frame_position(frames: tuple[DecisionFrame, ...]) -> int:
    for index in range(len(frames) - 1, -1, -1):
        if frames[index].kind == FrameKind.REVEAL:
            return index
    raise RuntimeError("Reveal choice is missing its Reveal frame")


def _queue_deferred_choices(
    frames: tuple[DecisionFrame, ...],
    entries: tuple[tuple[str, str], ...],
) -> tuple[DecisionFrame, ...]:
    """Append (card, effect) entries to the Reveal frame's deferred queue."""

    if not entries:
        return frames
    position = _reveal_frame_position(frames)
    context = frame_context(frames[position])
    context[_DEFERRED_CHOICES_KEY] = _encode_deferred(
        (*_deferred_reveal_choices(context), *entries)
    )
    return (
        *frames[:position],
        with_context(frames[position], context),
        *frames[position + 1 :],
    )


def _available_deferred_choices(
    state: GameState,
    player: int,
    context: dict[str, ActionValue],
) -> tuple[tuple[str, str], ...]:
    """Return the deferred entries whose printed condition holds right now."""

    owner = state.players[player]
    persuasion = context.get("persuasion")
    return tuple(
        (card_id, effect_value)
        for card_id, effect_value in _deferred_reveal_choices(context)
        if _reveal_choice_effect_is_available(
            state,
            player,
            owner,
            owner.in_play,
            card_id,
            PersonalCardRevealChoiceEffect(effect_value),
            persuasion=(
                persuasion
                if isinstance(persuasion, int) and not isinstance(persuasion, bool)
                else None
            ),
        )
    )


def legal_defer_reveal_choice_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return the choice to put the current Reveal choice off until later.

    Reveal effects may be resolved in any order [Main p. 12]; deferring the
    frame on top uncovers the next choice or the Reveal frame's acquisitions.
    A choice that already started (a Spy recalled for its placement) and a
    choice brought back by ``resume_reveal_choice`` cannot be deferred.
    """

    frame = owned_top_frame(state, FrameKind.REVEAL_CHOICE, player)
    if frame is None:
        return ()
    context = frame_context(frame)
    if context.get("reveal_spy_recalled") is True or context.get(_RESUMED_KEY) is True:
        return ()
    return (DomainAction(action_id="defer_reveal_choice", actor=player),)


def apply_defer_reveal_choice(state: GameState, action: DomainAction) -> RuleResult:
    """Move the current Reveal choice to the Reveal frame's deferred queue."""

    if action not in legal_defer_reveal_choice_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal choice deferral")
    frame = state.decision_stack[-1]
    context = frame_context(frame)
    card_id = context_str(context, "reveal_card_id", owner=_CHOICE_FRAME)
    effect = context_str(context, "reveal_choice_effect", owner=_CHOICE_FRAME)
    frames = _queue_deferred_choices(state.decision_stack[:-1], ((card_id, effect),))
    return RuleResult(
        state=replace(state, decision_stack=frames),
        events=(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"reveal_card:{card_id}:{effect}:deferred"
                ),
                kind="reveal_choice_deferred",
                payload=(
                    ("card_id", card_id),
                    ("effect", effect),
                    ("player", action.actor),
                ),
            ),
        ),
    )


def legal_resume_reveal_choice_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return one resume action per kind of deferred choice that can open now.

    A deferred choice whose printed condition currently fails stays queued
    without an action: a later Reveal choice of the owner (a Spy placed,
    Spice gained) can still satisfy it [Main p. 12].
    """

    frame = owned_top_frame(state, FrameKind.REVEAL, player)
    if frame is None:
        return ()
    kinds: list[str] = []
    for _, effect in _available_deferred_choices(state, player, frame_context(frame)):
        if effect not in kinds:
            kinds.append(effect)
    return tuple(
        DomainAction(
            action_id="resume_reveal_choice",
            actor=player,
            arguments=(("effect", effect),),
        )
        for effect in kinds
    )


def apply_resume_reveal_choice(state: GameState, action: DomainAction) -> RuleResult:
    """Bring the oldest openable deferred choice of the named kind back on top.

    Availability is judged now, in the owner's chosen order [Main p. 12]
    [Main pp. 9, 20]; the action is only offered while some entry of that
    kind can open.
    """

    if action not in legal_resume_reveal_choice_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal choice resumption")
    frame = state.decision_stack[-1]
    context = frame_context(frame)
    effect_value = str(dict(action.arguments)["effect"])
    player = action.actor
    available = _available_deferred_choices(state, player, context)
    card_id = next(
        entry_card for entry_card, effect in available if effect == effect_value
    )
    entries = list(_deferred_reveal_choices(context))
    entries.remove((card_id, effect_value))
    context[_DEFERRED_CHOICES_KEY] = _encode_deferred(tuple(entries))
    reveal_frame = with_context(frame, context)
    effect = PersonalCardRevealChoiceEffect(effect_value)
    source = (
        f"round:{state.round_number}:player:{player}:"
        f"reveal_card:{card_id}:{effect_value}"
    )
    resumed_event = GameEvent(
        event_id=f"{source}:resumed",
        kind="reveal_choice_resumed",
        payload=(("card_id", card_id), ("effect", effect_value), ("player", player)),
    )
    choice = _build_reveal_choice_frame(state.round_number, player, card_id, effect)
    choice_context = frame_context(choice)
    choice_context[_RESUMED_KEY] = True
    return RuleResult(
        state=replace(
            state,
            decision_stack=(
                *state.decision_stack[:-1],
                reveal_frame,
                with_context(choice, choice_context),
            ),
        ),
        events=(resumed_event,),
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
                    context_int(context, "strength", owner="Reveal frame") + sword_delta
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

    frame_persuasion = _frame_persuasion(state.decision_stack)
    eligible = _eligible_reveal_effects(
        next_owner,
        cards_in_play,
        card_id,
        card,
        persuasion=(
            None
            if frame_persuasion is None
            else frame_persuasion + card.reveal_persuasion
        ),
    )
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
                next_owner,
                cards_in_play,
                other_id,
                other_card,
                effect,
                persuasion=_frame_persuasion(state.decision_stack),
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

    # Troop recruits, Intrigue draws and resources join the Reveal's pending
    # gains so the owner keeps choosing their order [Main p. 12] (OQ-045).
    late_gains: tuple[RevealGain, ...] = tuple(
        entry
        for effect in eligible
        for entry in (
            ("troops", str(effect.recruit_troops), card_id)
            if effect.recruit_troops
            else None,
            ("intrigue", str(effect.draw_intrigue), card_id)
            if effect.draw_intrigue
            else None,
            resource_gain_entry(
                card_id, solari=effect.solari, spice=effect.spice, water=effect.water
            ),
        )
        if entry is not None
    )

    units = next_owner.units_in_conflict
    counts_toward_combat = units > 0
    if counts_toward_combat and sword_delta:
        next_owner = replace(
            next_owner, combat_strength=next_owner.combat_strength + sword_delta
        )

    source = f"round:{state.round_number}:player:{player}:reveal_card:{card_id}"
    next_state = replace(
        state,
        players=replace_player(state.players, next_owner),
        decision_stack=_append_reveal_gains(
            _record_granted_effects(
                _apply_late_reveal_frame_update(
                    state.decision_stack,
                    card_id,
                    persuasion_delta,
                    sword_delta,
                    counts_toward_combat=counts_toward_combat,
                ),
                _granted_entries(
                    (card_id,), (card,), next_owner, cards_in_play, completed_contracts
                ),
            ),
            late_gains,
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
    choice_frames: list[DecisionFrame] = []
    late_deferred: list[tuple[str, str]] = []
    for choice_effect in card.reveal_choice_effects:
        if _reveal_choice_effect_is_available(
            next_state,
            player,
            latest_owner,
            cards_in_play,
            card_id,
            choice_effect,
            persuasion=_frame_persuasion(next_state.decision_stack),
        ):
            choice_frames.append(
                _build_reveal_choice_frame(
                    state.round_number, player, card_id, choice_effect
                )
            )
        else:
            late_deferred.append((card_id, choice_effect.value))
    if choice_frames:
        next_state = replace(
            next_state,
            decision_stack=_insert_after_reveal_frame(
                next_state.decision_stack, tuple(reversed(choice_frames))
            ),
        )
    if late_deferred:
        next_state = replace(
            next_state,
            decision_stack=_queue_deferred_choices(
                next_state.decision_stack, tuple(late_deferred)
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

    def eligible_effects(
        persuasion: int | None,
    ) -> tuple[tuple[str, PersonalCardRevealEffect], ...]:
        return tuple(
            (card_id, effect)
            for card_id, card in zip(revealed, cards, strict=True)
            for effect in _eligible_reveal_effects(
                owner, cards_in_play, card_id, card, persuasion=persuasion
            )
        )

    # Sardaukar Commander Skills pay their Reveal-turn bonus once while a
    # Commander is in the Conflict [Bloodlines p. 4] [Skill tile faces].
    active_skills = (
        tuple(skill_for_instance(instance_id) for instance_id in owner.skill_ids)
        if owner.commanders_conflict > 0
        else ()
    )

    def total_persuasion(
        effects: tuple[tuple[str, PersonalCardRevealEffect], ...],
    ) -> int:
        total = sum(card.reveal_persuasion for card in cards) + sum(
            _reveal_effect_persuasion(effect, cards, len(owner.completed_contract_ids))
            for _, effect in effects
        )
        if owner.high_council:
            total += 2
        if "assembly_hall" in owner.agent_locations:
            total += 1
        # Persuasion generated in this Reveal turn from outside the cards
        # counts toward "Command (6+)" too [Bloodlines p. 5]: Charismatic,
        # Navigation card 3 from slot 4 ("during each of your Reveal turns,
        # 1 Persuasion") and Self-Destroying Messages ("Reveal Turn: 1
        # Persuasion").
        total += sum(skill.reveal_persuasion for skill in active_skills)
        total += owner.reveal_persuasion_bonus
        if has_tech(owner.tech_ids, TechAbility.REVEAL_PERSUASION):
            total += 1
        return total

    # "Command (6+)" effects open on the Persuasion the other effects
    # generate [Bloodlines p. 5]; they never add Persuasion themselves.
    persuasion = total_persuasion(eligible_effects(None))
    reveal_effects = eligible_effects(persuasion)
    persuasion = total_persuasion(reveal_effects)
    # Tech tiles with "Reveal Turn: Command (6+)" lines pay once the total
    # is known; a later Command opening pays them late [Bloodlines p. 5].
    tech_granted = tuple(
        tech_id
        for tech_id, ability in _COMMAND_TECH
        if persuasion >= COMMAND_PERSUASION and has_tech(owner.tech_ids, ability)
    )
    tech_sword = 2 if "training_depot" in tech_granted else 0

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
    sword_strength = (
        sum(strength for _, strength in card_strengths)
        + sum(
            effect.strength_per_other_sword_card
            * sum(
                strength > 0
                for card_id, strength in card_strengths
                if card_id != effect_card_id
            )
            for effect_card_id, effect in reveal_effects
        )
        + tech_sword
    )
    # One formula for the units' share (the engine keeps combat_strength
    # equal to it after every step before the Reveal); the Reveal adds the
    # revealed swords, and without a unit there is no strength [Main p. 12].
    units = owner.units_in_conflict
    # The Skill strength already folded into the running value stays.
    strength = (
        units_strength(owner) + sword_strength + owner.skill_strength_applied
        if units > 0
        else 0
    )
    next_owner = owner
    # Panopticon: "Reveal Turn: a Spy and a troop" [Panopticon Tech tile];
    # the Spy placement opens below.
    panopticon = has_tech(owner.tech_ids, TechAbility.PANOPTICON)
    # Troop recruits, Intrigue draws and resource gains wait for the owner's
    # order (OQ-045).
    reveal_troops_recruited = 0
    resource_gains = (
        *(
            resource_gain_entry(
                card_id, solari=effect.solari, spice=effect.spice, water=effect.water
            )
            for card_id, effect in reveal_effects
        ),
        *(
            resource_gain_entry(
                f"skill:{skill.skill_id}",
                spice=skill.reveal_spice,
                water=skill.reveal_water,
            )
            for skill in active_skills
        ),
        resource_gain_entry(
            "tech:delivery_bay", solari=2 if "delivery_bay" in tech_granted else 0
        ),
    )
    pending_gains: tuple[RevealGain, ...] = (
        *(
            ("troops", str(effect.recruit_troops), card_id)
            for card_id, effect in reveal_effects
            if effect.recruit_troops
        ),
        *((("troops", "1", "tech:panopticon"),) if panopticon else ()),
        *(
            ("intrigue", str(effect.draw_intrigue), card_id)
            for card_id, effect in reveal_effects
            if effect.draw_intrigue
        ),
        *(entry for entry in resource_gains if entry is not None),
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
        (
            _GRANTED_EFFECTS_KEY,
            _encode_granted(
                _granted_entries(
                    revealed,
                    cards,
                    owner,
                    cards_in_play,
                    len(owner.completed_contract_ids),
                    persuasion=persuasion,
                )
            ),
        ),
        # Combat-icon deployment during the Reveal [Bloodlines p. 5]: open
        # when an icon arrived earlier this turn, counting this Reveal's
        # recruits toward the limit.
        ("combat_deployment", owner.combat_icon_turn),
        ("optional_sword_strength", 0),
        ("persuasion", persuasion),
        ("reveal_troops_recruited", reveal_troops_recruited),
        (REVEAL_GAINS_KEY, _encode_gains(pending_gains)),
        ("reveal_units_deployed", 0),
        ("revealed_card_count", len(revealed)),
        ("strength", strength),
        ("sword_strength", sword_strength),
        (_TECH_GRANTED_KEY, ",".join(tech_granted)),
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
    choice_frames: list[DecisionFrame] = []
    deferred: list[tuple[str, str]] = []
    for card_id, card in zip(revealed, cards, strict=True):
        for choice_effect in card.reveal_choice_effects:
            if _reveal_choice_effect_is_available(
                state,
                action.actor,
                owner,
                cards_in_play,
                card_id,
                choice_effect,
                persuasion=persuasion,
            ):
                choice_frames.append(
                    _build_reveal_choice_frame(
                        state.round_number, action.actor, card_id, choice_effect
                    )
                )
            else:
                # Queued rather than skipped: a later Reveal choice of the
                # owner can still satisfy its printed condition [Main p. 12].
                deferred.append((card_id, choice_effect.value))
    reveal_context = frame_context(reveal_frame)
    reveal_context[_DEFERRED_CHOICES_KEY] = _encode_deferred(tuple(deferred))
    reveal_frame = with_context(reveal_frame, reveal_context)
    # Forbidden Weapons' "Reveal Turn: You must choose" and Panopticon's Spy
    # wait on the Reveal frame for the owner's order (OQ-044).
    reveal_context[TECH_PENDING_KEY] = ",".join(
        (
            *(
                ("forbidden_weapons",)
                if has_tech(owner.tech_ids, TechAbility.FORBIDDEN_WEAPONS)
                else ()
            ),
            *(("panopticon",) if panopticon else ()),
        )
    )
    reveal_frame = with_context(reveal_frame, reveal_context)
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
        if effect.trashes_self:
            # Bombast: "3 Solari and trash this card" — the card leaves play
            # once its Command effect pays out.
            trashed = trash_personal_card(
                next_state, action.actor, card_id, source=f"{event.event_id}:{card_id}"
            )
            next_state = trashed.state
            events.extend(trashed.events)
        if effect.grants_combat_icon:
            # Holy War's Fremen Bond: this Reveal may deploy as though at a
            # Combat space [Bloodlines p. 5].
            next_state = grant_combat_icon(next_state, action.actor)
    events.extend(
        GameEvent(
            event_id=f"{event.event_id}:tech:{tech_id}",
            kind="tech_reveal_bonus",
            payload=(
                ("player", action.actor),
                ("solari", 2 if tech_id == "delivery_bay" else 0),
                ("strength", 2 if tech_id == "training_depot" else 0),
                ("tech_id", tech_id),
            ),
        )
        for tech_id in tech_granted
    )
    events.extend(
        GameEvent(
            event_id=f"{event.event_id}:skill:{skill.skill_id}",
            kind="skill_reveal_bonus",
            payload=(
                ("persuasion", skill.reveal_persuasion),
                ("player", action.actor),
                ("skill_id", skill.skill_id),
                ("spice", skill.reveal_spice),
                ("water", skill.reveal_water),
            ),
        )
        for skill in active_skills
        if skill.reveal_persuasion or skill.reveal_spice or skill.reveal_water
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
    if _available_deferred_choices(state, player, context):
        # A deferred choice that can open now still has to be resolved; the
        # ones whose condition fails simply lapse when the Reveal ends.
        return ()
    if reveal_pending_gains(context):
        # Every troop recruit and Intrigue draw must be taken (OQ-045).
        return ()
    pending_tech = tech_reveal_pending(context)
    if "forbidden_weapons" in pending_tech or (
        "panopticon" in pending_tech
        and (
            state.players[player].spies_supply > 0
            or bool(state.players[player].spy_post_ids)
        )
    ):
        # Forbidden Weapons must be chosen; Panopticon's Spy must be placed
        # while a Spy can still reach a post (OQ-044).
        return ()
    return (DomainAction(action_id="finish_reveal", actor=player),)


def finish_reveal_turn(state: GameState, action: DomainAction) -> RuleResult:
    """Clean up in-play cards and advance or enter Combat."""

    if action not in legal_finish_reveal_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal cleanup")
    # Deferred choices whose printed condition never came back lapse here.
    lapsed_events = tuple(
        GameEvent(
            event_id=(
                f"round:{state.round_number}:player:{action.actor}:"
                f"reveal_card:{card_id}:{effect}:unavailable"
            ),
            kind="reveal_choice_unavailable",
            payload=(
                ("card_id", card_id),
                ("effect", effect),
                ("player", action.actor),
            ),
        )
        for card_id, effect in _deferred_reveal_choices(
            frame_context(state.decision_stack[-1])
        )
    )
    # A tile effect nobody could take (Panopticon without a Spy) lapses too.
    lapsed_events = (
        *lapsed_events,
        *(
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{action.actor}:"
                    f"reveal:{tech_id}:unavailable"
                ),
                kind="tech_reveal_unavailable",
                payload=(("player", action.actor), ("tech_id", tech_id)),
            )
            for tech_id in tech_reveal_pending(frame_context(state.decision_stack[-1]))
        ),
    )
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
        state=next_state,
        events=(*lapsed_events, *expired.events, *removal_events, event),
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
    commanders: int = 0,
) -> RuleResult:
    """Record units that entered the Conflict during ``player``'s Reveal turn.

    Mirrors Desert Power: the first units make the revealed sword strength
    count, later units add their own value only [Main p. 13]. A Sardaukar
    Commander is worth 2 like a troop [Bloodlines p. 4].
    """

    owner = state.players[player]
    value = 2 * troops + 3 * sandworms + 2 * commanders
    if value == 0:
        return RuleResult(state=state)
    previous_units = owner.units_in_conflict
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
        commanders_garrison=owner.commanders_garrison - commanders,
        commanders_conflict=owner.commanders_conflict + commanders,
        combat_strength=owner.combat_strength + strength_delta,
        units_deployed_turn=(
            owner.units_deployed_turn + troops + sandworms + commanders
        ),
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
                    f"units:{owner.units_in_conflict}"
                ),
                kind="reveal_strength_gained",
                payload=(("amount", strength_delta), ("player", player)),
            ),
        ),
    )
