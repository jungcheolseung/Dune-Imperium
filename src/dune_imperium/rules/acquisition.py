"""Card acquisition during Reveal and card-driven Agent effects."""

from dataclasses import dataclass, replace

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.types import (
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardRevealAcquisitionEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.contracts import (
    begin_contract_gain,
    complete_acquire_contracts,
)
from dune_imperium.rules.effects import (
    advance_after_effect,
    current_agent_effect_context,
)
from dune_imperium.rules.frames import FrameKind, replace_player
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.reveal_turn import current_reveal_context
from dune_imperium.rules.spy_placement import (
    empty_observation_post_ids,
    place_spy,
    recall_spy,
    spied_factions,
)


def legal_acquisition_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return choices for a place-Spy acquisition bonus."""

    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or "acquisition_card_id" not in context
    ):
        return ()
    owner = state.players[player]
    if context.get("acquisition_spy_recalled") is True or owner.spies_supply > 0:
        return tuple(
            DomainAction(
                action_id="place_acquisition_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in empty_observation_post_ids(state)
        )
    return tuple(
        DomainAction(
            action_id="recall_spy_for_acquisition",
            actor=player,
            arguments=(("post_id", post_id),),
        )
        for post_id in owner.spy_post_ids
    )


def apply_acquisition_spy_action(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Recall if necessary, then place the Spy granted on acquisition."""

    if action not in legal_acquisition_spy_actions(state, action.actor):
        raise ValueError("action is not a legal acquisition Spy choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    card_id = context["acquisition_card_id"]
    post_id = dict(action.arguments).get("post_id")
    if not isinstance(card_id, str) or not isinstance(post_id, str):
        raise RuntimeError("acquisition Spy frame has invalid context")
    owner = state.players[action.actor]
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"acquire:{card_id}"
    )

    if action.action_id == "recall_spy_for_acquisition":
        next_owner = recall_spy(owner, post_id)
        context["acquisition_spy_recalled"] = True
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
                ("source", card_id),
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
            ("card_id", card_id),
            ("player", action.actor),
            ("post_id", post_id),
        ),
    )
    return RuleResult(state=next_state, events=(event,))


def legal_agent_card_acquisitions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return Price is No Object's optional Solari acquisitions."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        frame, context = current_agent_effect_context(state)
    except ValueError:
        return ()
    if (
        not isinstance(frame.decision, PlayerDecision)
        or frame.decision.owner != player
        or context.get("pending_agent_effect") is not True
    ):
        return ()
    source_id = context.get("card_id")
    if not isinstance(source_id, str):
        raise RuntimeError("Agent acquisition frame has invalid card ID")
    source = personal_card_for_instance(source_id)
    if (
        source.agent_effect
        is not PersonalCardAgentEffect.ACQUIRE_WITH_SOLARI_TO_HAND
    ):
        return ()

    solari = state.players[player].resources.solari
    reserve_actions = tuple(
        DomainAction(
            action_id="acquire_reserve_with_solari",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id, count in state.reserve_stacks
        if count > 0 and RESERVE_STACKS_BY_ID[card_id].acquisition_cost <= solari
    )
    imperium_actions = tuple(
        DomainAction(
            action_id="acquire_imperium_with_solari",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in state.imperium_row
        if (
            (definition := imperium_card_for_instance(instance_id)).acquisition_cost
            is not None
            and definition.acquisition_cost <= solari
            and (
                not definition.has_acquisition_bonus
                or definition.acquisition_effect is not None
            )
        )
    )
    return (
        DomainAction(action_id="decline_agent_card_acquisition", actor=player),
        *reserve_actions,
        *imperium_actions,
    )


def apply_agent_card_acquisition(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or acquire one card to hand by paying its cost in Solari."""

    if action not in legal_agent_card_acquisitions(state, action.actor):
        raise ValueError("action is not a legal Agent-card acquisition")
    _, context = current_agent_effect_context(state)
    context["pending_agent_effect"] = False
    source = f"round:{state.round_number}:player:{action.actor}:agent_acquisition"
    if action.action_id == "decline_agent_card_acquisition":
        next_state = advance_after_effect(state, context)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="agent_card_acquisition_declined",
                    payload=(("player", action.actor),),
                ),
            ),
        )

    if action.action_id == "acquire_reserve_with_solari":
        return _acquire_reserve_to_hand_with_solari(state, action, context)
    return _acquire_imperium_to_hand_with_solari(state, action, context)


def _acquire_reserve_to_hand_with_solari(
    state: GameState,
    action: DomainAction,
    context: dict[str, ActionValue],
) -> RuleResult:
    card_id = dict(action.arguments).get("card_id")
    if not isinstance(card_id, str):
        raise RuntimeError("Agent Reserve acquisition has invalid card ID")
    definition = RESERVE_STACKS_BY_ID[card_id]
    instance_id = next_reserve_instance_id(state, card_id)
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"acquire_with_solari:{instance_id}"
    )
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        hand=(*owner.hand, instance_id),
        resources=replace(
            owner.resources,
            solari=owner.resources.solari - definition.acquisition_cost,
        ),
        victory_points=owner.victory_points + definition.acquisition_vp,
    )
    reserve_stacks = tuple(
        (candidate_id, count - 1 if candidate_id == card_id else count)
        for candidate_id, count in state.reserve_stacks
    )
    prepared = replace(
        state,
        players=replace_player(state.players, next_owner),
        reserve_stacks=reserve_stacks,
    )
    completed = complete_acquire_contracts(
        prepared,
        action.actor,
        card_id,
        source=source,
    )
    next_state = advance_after_effect(
        completed.state,
        context,
        completed.state.players,
    )
    event = GameEvent(
        event_id=source,
        kind="card_acquired",
        payload=(
            ("card_id", card_id),
            ("destination", "hand"),
            ("payment", "solari"),
            ("player", action.actor),
        ),
    )
    return RuleResult(state=next_state, events=(event, *completed.events))


def _acquire_imperium_to_hand_with_solari(
    state: GameState,
    action: DomainAction,
    context: dict[str, ActionValue],
) -> RuleResult:
    instance_id = dict(action.arguments).get("instance_id")
    if not isinstance(instance_id, str):
        raise RuntimeError("Agent Imperium acquisition has invalid instance ID")
    definition = imperium_card_for_instance(instance_id)
    if not state.imperium_deck:
        raise NotImplementedError(
            "Imperium Row refill after deck exhaustion is unresolved"
        )
    cost = definition.acquisition_cost
    if cost is None:
        raise RuntimeError("Imperium card is missing its acquisition cost")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"acquire_with_solari:{instance_id}"
    )

    row = list(state.imperium_row)
    row[row.index(instance_id)] = state.imperium_deck[0]
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        hand=(*owner.hand, instance_id),
        resources=replace(
            owner.resources,
            solari=owner.resources.solari - cost,
        ),
    )
    bonus = _resolve_imperium_acquisition_bonus(
        state,
        action.actor,
        instance_id,
        next_owner,
    )
    next_owner = bonus.owner
    acquisition_events = bonus.events
    places_spy = bonus.places_spy
    takes_contract = bonus.takes_contract
    base_frame = replace(
        state.decision_stack[-1],
        context=tuple(sorted(context.items())),
    )
    prepared = replace(
        state,
        players=replace_player(state.players, next_owner),
        imperium_deck=state.imperium_deck[1:],
        imperium_row=tuple(row),
        intrigue_deck=bonus.intrigue_deck,
        pending_intrigue_draws=_with_pending_draw(state, bonus.pending_draw),
        decision_stack=(*state.decision_stack[:-1], base_frame),
    )
    if (
        definition.acquisition_effect
        is PersonalCardAcquisitionEffect.GAIN_SPACING_GUILD_INFLUENCE
    ):
        gained = gain_faction_influence(
            prepared,
            action.actor,
            Faction.SPACING_GUILD,
            1,
            event_prefix=(
                f"round:{state.round_number}:player:{action.actor}:"
                f"acquire_with_solari:{instance_id}:influence:spacing_guild"
            ),
        )
        prepared = gained.state
        acquisition_events = (*acquisition_events, *gained.events)
    completed = complete_acquire_contracts(
        prepared,
        action.actor,
        definition.card.card_id,
        source=source,
    )
    prepared = completed.state
    acquisition_events = (*acquisition_events, *completed.events)
    if places_spy:
        next_state = replace(
            prepared,
            decision_stack=(
                *prepared.decision_stack,
                acquisition_spy_frame(state, action.actor, instance_id),
            ),
        )
    elif takes_contract:
        resumed = advance_after_effect(
            prepared,
            context,
            prepared.players,
        )
        contracts = begin_contract_gain(
            resumed,
            action.actor,
            1,
            source=f"{source}:acquisition_bonus",
        )
        next_state = contracts.state
        acquisition_events = (*acquisition_events, *contracts.events)
    else:
        next_state = advance_after_effect(
            prepared,
            context,
            prepared.players,
        )
    event = GameEvent(
        event_id=source,
        kind="card_acquired",
        payload=(
            ("card_id", definition.card.card_id),
            ("destination", "hand"),
            ("instance_id", instance_id),
            ("payment", "solari"),
            ("player", action.actor),
        ),
    )
    return RuleResult(state=next_state, events=(event, *acquisition_events))


def legal_reserve_acquisitions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate affordable, non-empty Reserve stacks for the revealer."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        context = current_reveal_context(state)
    except ValueError:
        return ()
    owner = context["turn_owner"]
    persuasion = context["persuasion"]
    if (
        isinstance(owner, bool)
        or not isinstance(owner, int)
        or isinstance(persuasion, bool)
        or not isinstance(persuasion, int)
    ):
        raise RuntimeError("Reveal frame has invalid acquisition context")
    if owner != player:
        return ()

    return tuple(
        DomainAction(
            action_id="acquire_reserve",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id, count in state.reserve_stacks
        if count > 0
        and RESERVE_STACKS_BY_ID[card_id].acquisition_cost <= persuasion
    )


def apply_reserve_acquisition(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Spend Persuasion and put one Reserve card in the discard pile."""

    if action not in legal_reserve_acquisitions(state, action.actor):
        raise ValueError("action is not a legal Reserve acquisition")
    card_id = dict(action.arguments)["card_id"]
    if not isinstance(card_id, str):
        raise ValueError("Reserve acquisition card_id must be a string")
    definition = RESERVE_STACKS_BY_ID[card_id]
    context = current_reveal_context(state)
    persuasion = context["persuasion"]
    if isinstance(persuasion, bool) or not isinstance(persuasion, int):
        raise RuntimeError("Reveal frame has invalid Persuasion")

    instance_id = next_reserve_instance_id(state, card_id)
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        discard_pile=(*owner.discard_pile, instance_id),
        victory_points=owner.victory_points + definition.acquisition_vp,
    )
    players = tuple(
        next_owner if player.player_id == action.actor else player
        for player in state.players
    )
    reserve_stacks = tuple(
        (candidate_id, count - 1 if candidate_id == card_id else count)
        for candidate_id, count in state.reserve_stacks
    )
    context["persuasion"] = persuasion - definition.acquisition_cost
    frame = state.decision_stack[-1]
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    next_state = replace(
        state,
        players=players,
        reserve_stacks=reserve_stacks,
        decision_stack=(*state.decision_stack[:-1], next_frame),
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}"
        ),
        kind="card_acquired",
        payload=(("card_id", card_id), ("player", action.actor)),
    )
    triggered = _resolve_reveal_acquisition_triggers(
        next_state,
        action.actor,
        card_id,
    )
    completed = complete_acquire_contracts(
        triggered.state,
        action.actor,
        card_id,
        source=f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}",
    )
    return RuleResult(
        state=completed.state,
        events=(event, *triggered.events, *completed.events),
    )


def legal_imperium_acquisitions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate affordable cards currently visible in the Imperium Row."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    try:
        context = current_reveal_context(state)
    except ValueError:
        return ()
    owner = context["turn_owner"]
    persuasion = context["persuasion"]
    if (
        isinstance(owner, bool)
        or not isinstance(owner, int)
        or isinstance(persuasion, bool)
        or not isinstance(persuasion, int)
    ):
        raise RuntimeError("Reveal frame has invalid acquisition context")
    if owner != player:
        return ()

    actions: list[DomainAction] = []
    for instance_id in state.imperium_row:
        cost = imperium_card_for_instance(instance_id).acquisition_cost
        if cost is not None and cost <= persuasion:
            actions.append(
                DomainAction(
                    action_id="acquire_imperium",
                    actor=player,
                    arguments=(("instance_id", instance_id),),
                )
            )
    return tuple(actions)


def apply_imperium_acquisition(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Acquire one Row card and immediately refill its position."""

    if action not in legal_imperium_acquisitions(state, action.actor):
        raise ValueError("action is not a legal Imperium Row acquisition")
    instance_id = dict(action.arguments)["instance_id"]
    if not isinstance(instance_id, str):
        raise ValueError("Imperium acquisition instance_id must be a string")
    definition = imperium_card_for_instance(instance_id)
    if definition.has_acquisition_bonus and definition.acquisition_effect is None:
        raise NotImplementedError(
            f"acquisition bonus is not implemented: {definition.card.card_id}"
        )
    if not state.imperium_deck:
        raise NotImplementedError(
            "Imperium Row refill after deck exhaustion is unresolved"
        )
    cost = definition.acquisition_cost
    if cost is None:
        raise RuntimeError("Imperium card is missing its acquisition cost")

    context = current_reveal_context(state)
    persuasion = context["persuasion"]
    if isinstance(persuasion, bool) or not isinstance(persuasion, int):
        raise RuntimeError("Reveal frame has invalid Persuasion")
    row = list(state.imperium_row)
    row[row.index(instance_id)] = state.imperium_deck[0]
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        discard_pile=(*owner.discard_pile, instance_id),
    )
    bonus = _resolve_imperium_acquisition_bonus(
        state,
        action.actor,
        instance_id,
        next_owner,
    )
    next_owner = bonus.owner
    intrigue_deck = bonus.intrigue_deck
    acquisition_events = bonus.events
    places_spy = bonus.places_spy
    takes_contract = bonus.takes_contract
    players = replace_player(state.players, next_owner)
    context["persuasion"] = persuasion - cost
    frame = state.decision_stack[-1]
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    decision_stack = (*state.decision_stack[:-1], next_frame)
    if places_spy:
        decision_stack = (
            *decision_stack,
            acquisition_spy_frame(state, action.actor, instance_id),
        )
    next_state = replace(
        state,
        players=players,
        imperium_deck=state.imperium_deck[1:],
        imperium_row=tuple(row),
        intrigue_deck=intrigue_deck,
        pending_intrigue_draws=_with_pending_draw(state, bonus.pending_draw),
        decision_stack=decision_stack,
    )
    if (
        definition.acquisition_effect
        is PersonalCardAcquisitionEffect.GAIN_SPACING_GUILD_INFLUENCE
    ):
        gained = gain_faction_influence(
            next_state,
            action.actor,
            Faction.SPACING_GUILD,
            1,
            event_prefix=(
                f"round:{state.round_number}:player:{action.actor}:"
                f"acquire:{instance_id}:influence:spacing_guild"
            ),
        )
        next_state = gained.state
        acquisition_events = (*acquisition_events, *gained.events)
    completed = complete_acquire_contracts(
        next_state,
        action.actor,
        definition.card.card_id,
        source=f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}",
    )
    next_state = completed.state
    acquisition_events = (*acquisition_events, *completed.events)
    if takes_contract:
        contracts = begin_contract_gain(
            next_state,
            action.actor,
            1,
            source=(
                f"round:{state.round_number}:player:{action.actor}:"
                f"acquire:{instance_id}:acquisition_bonus"
            ),
        )
        next_state = contracts.state
        acquisition_events = (*acquisition_events, *contracts.events)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}"
        ),
        kind="card_acquired",
        payload=(
            ("card_id", definition.card.card_id),
            ("instance_id", instance_id),
            ("player", action.actor),
        ),
    )
    return RuleResult(state=next_state, events=(event, *acquisition_events))


@dataclass(frozen=True, slots=True)
class AcquisitionBonus:
    """Result of an acquisition bonus before its follow-up choice."""

    owner: PlayerState
    intrigue_deck: tuple[str, ...]
    events: tuple[GameEvent, ...]
    places_spy: bool
    takes_contract: bool
    pending_draw: tuple[int, int, str] | None = None


def _resolve_imperium_acquisition_bonus(
    state: GameState,
    player: int,
    instance_id: str,
    owner: PlayerState,
) -> AcquisitionBonus:
    """Apply one supported acquisition bonus before its follow-up choice."""

    definition = imperium_card_for_instance(instance_id)
    effect = definition.acquisition_effect
    intrigue_deck = state.intrigue_deck
    events: tuple[GameEvent, ...] = ()
    pending_draw: tuple[int, int, str] | None = None
    if effect is PersonalCardAcquisitionEffect.DRAW_INTRIGUE_CARD:
        source = (
            f"round:{state.round_number}:player:{player}:"
            f"acquire:{instance_id}:intrigue_draw"
        )
        if intrigue_deck:
            owner = replace(
                owner,
                intrigue_cards=(*owner.intrigue_cards, intrigue_deck[0]),
            )
            intrigue_deck = intrigue_deck[1:]
            events = (
                GameEvent(
                    event_id=source,
                    kind="intrigue_card_drawn",
                    payload=(("count", 1), ("player", player)),
                ),
            )
        else:
            # The deck is empty: the dispatcher reshuffles the discard and
            # completes the draw before the next player decision [FAQ p. 2].
            pending_draw = (player, 1, source)
    elif effect is PersonalCardAcquisitionEffect.GAIN_TWO_SOLARI:
        owner = replace(
            owner,
            resources=replace(
                owner.resources,
                solari=owner.resources.solari + 2,
            ),
        )
        events = (
            GameEvent(
                event_id=(
                    f"round:{state.round_number}:player:{player}:"
                    f"acquire:{instance_id}:solari"
                ),
                kind="acquisition_resource_gained",
                payload=(
                    ("amount", 2),
                    ("player", player),
                    ("resource", "solari"),
                ),
            ),
        )
    return AcquisitionBonus(
        owner=owner,
        intrigue_deck=intrigue_deck,
        events=events,
        places_spy=effect is PersonalCardAcquisitionEffect.PLACE_SPY,
        takes_contract=effect is PersonalCardAcquisitionEffect.TAKE_CONTRACT,
        pending_draw=pending_draw,
    )


def _with_pending_draw(
    state: GameState,
    pending_draw: tuple[int, int, str] | None,
) -> tuple[tuple[int, int, str], ...]:
    if pending_draw is None:
        return state.pending_intrigue_draws
    return (*state.pending_intrigue_draws, pending_draw)


def next_reserve_instance_id(state: GameState, card_id: str) -> str:
    """Return an unused ``reserve:<card>:<copy>`` ID for the next acquisition.

    Reserve copies are physically identical, so an ID only has to be unique
    among copies currently owned by any player. A copy trashed back onto the
    stack may therefore be re-issued while lower copy indexes stay in play.
    """

    if dict(state.reserve_stacks)[card_id] < 1:
        raise ValueError("the Reserve stack is empty")
    prefix = f"reserve:{card_id}:"
    owned = {
        instance_id
        for player in state.players
        for zone in (
            player.deck,
            player.hand,
            player.discard_pile,
            player.in_play,
            player.trashed,
        )
        for instance_id in zone
        if instance_id.startswith(prefix)
    }
    # Count down so the ID matches the historical ``count - 1`` scheme unless a
    # returned copy would collide with one still in play.
    for copy in reversed(range(RESERVE_STACKS_BY_ID[card_id].copies)):
        candidate = f"{prefix}{copy}"
        if candidate not in owned:
            return candidate
    raise RuntimeError("every Reserve copy is already owned")


def acquisition_spy_frame(
    state: GameState,
    player: int,
    instance_id: str,
) -> DecisionFrame:
    """Return the follow-up frame for a place-Spy acquisition bonus."""

    return DecisionFrame(
        kind=FrameKind.ACQUISITION_SPY,
        frame_id=(
            f"round:{state.round_number}:player:{player}:"
            f"acquisition_spy:{instance_id}"
        ),
        decision=PlayerDecision(
            owner=player,
            prompt="Choose an Observation Post for the acquired Spy",
        ),
        context=(
            ("acquisition_card_id", instance_id),
            ("turn_owner", player),
        ),
    )



def acquirable_reserve_card_ids(
    state: GameState,
    max_cost: int,
) -> tuple[str, ...]:
    """Return non-empty Reserve stacks whose printed cost is within the cap."""

    return tuple(
        card_id
        for card_id, count in state.reserve_stacks
        if count > 0 and RESERVE_STACKS_BY_ID[card_id].acquisition_cost <= max_cost
    )


def acquirable_imperium_instance_ids(
    state: GameState,
    max_cost: int,
) -> tuple[str, ...]:
    """Return Imperium Row cards within the cap whose bonus is implemented."""

    return tuple(
        instance_id
        for instance_id in state.imperium_row
        if (
            (definition := imperium_card_for_instance(instance_id)).acquisition_cost
            is not None
            and definition.acquisition_cost <= max_cost
            and (
                not definition.has_acquisition_bonus
                or definition.acquisition_effect is not None
            )
        )
    )


@dataclass(frozen=True, slots=True)
class IntrigueAcquisition:
    """One card acquired by an Intrigue effect, before its follow-up frames.

    ``places_spy`` and ``takes_contract`` report acquire-box bonuses whose
    frames the caller pushes once the Intrigue card itself has resolved.
    """

    result: RuleResult
    instance_id: str
    places_spy: bool = False
    takes_contract: bool = False


def acquire_reserve_for_intrigue(
    state: GameState,
    player: int,
    card_id: str,
    *,
    to_hand: bool,
    source: str,
) -> IntrigueAcquisition:
    """Acquire one Reserve card without Persuasion for an Intrigue effect."""

    definition = RESERVE_STACKS_BY_ID[card_id]
    instance_id = next_reserve_instance_id(state, card_id)
    owner = state.players[player]
    destination = "hand" if to_hand else "discard"
    next_owner = replace(
        owner,
        hand=(*owner.hand, instance_id) if to_hand else owner.hand,
        discard_pile=(
            owner.discard_pile if to_hand else (*owner.discard_pile, instance_id)
        ),
        victory_points=owner.victory_points + definition.acquisition_vp,
    )
    reserve_stacks = tuple(
        (candidate_id, count - 1 if candidate_id == card_id else count)
        for candidate_id, count in state.reserve_stacks
    )
    prepared = replace(
        state,
        players=replace_player(state.players, next_owner),
        reserve_stacks=reserve_stacks,
    )
    completed = complete_acquire_contracts(prepared, player, card_id, source=source)
    event = GameEvent(
        event_id=f"{source}:acquired:{instance_id}",
        kind="card_acquired",
        payload=(
            ("card_id", card_id),
            ("destination", destination),
            ("player", player),
        ),
    )
    return IntrigueAcquisition(
        result=RuleResult(
            state=completed.state, events=(event, *completed.events)
        ),
        instance_id=instance_id,
    )


def acquire_imperium_for_intrigue(
    state: GameState,
    player: int,
    instance_id: str,
    *,
    to_hand: bool,
    source: str,
) -> IntrigueAcquisition:
    """Acquire one Imperium Row card without Persuasion for an Intrigue effect.

    The Row position refills from the Imperium Deck at once [Main p. 13] and
    any acquire box resolves immediately [Main p. 20]. Bonuses that need a
    follow-up decision are reported to the caller instead of pushing frames.
    """

    definition = imperium_card_for_instance(instance_id)
    if definition.has_acquisition_bonus and definition.acquisition_effect is None:
        raise NotImplementedError(
            f"acquisition bonus is not implemented: {definition.card.card_id}"
        )
    if not state.imperium_deck:
        raise NotImplementedError(
            "Imperium Row refill after deck exhaustion is unresolved"
        )
    destination = "hand" if to_hand else "discard"
    row = list(state.imperium_row)
    row[row.index(instance_id)] = state.imperium_deck[0]
    owner = state.players[player]
    next_owner = replace(
        owner,
        hand=(*owner.hand, instance_id) if to_hand else owner.hand,
        discard_pile=(
            owner.discard_pile if to_hand else (*owner.discard_pile, instance_id)
        ),
    )
    bonus = _resolve_imperium_acquisition_bonus(state, player, instance_id, next_owner)
    prepared = replace(
        state,
        players=replace_player(state.players, bonus.owner),
        imperium_deck=state.imperium_deck[1:],
        imperium_row=tuple(row),
        intrigue_deck=bonus.intrigue_deck,
        pending_intrigue_draws=_with_pending_draw(state, bonus.pending_draw),
    )
    acquisition_events = bonus.events
    if (
        definition.acquisition_effect
        is PersonalCardAcquisitionEffect.GAIN_SPACING_GUILD_INFLUENCE
    ):
        gained = gain_faction_influence(
            prepared,
            player,
            Faction.SPACING_GUILD,
            1,
            event_prefix=f"{source}:influence:spacing_guild",
        )
        prepared = gained.state
        acquisition_events = (*acquisition_events, *gained.events)
    completed = complete_acquire_contracts(
        prepared,
        player,
        definition.card.card_id,
        source=source,
    )
    event = GameEvent(
        event_id=f"{source}:acquired:{instance_id}",
        kind="card_acquired",
        payload=(
            ("card_id", definition.card.card_id),
            ("destination", destination),
            ("instance_id", instance_id),
            ("player", player),
        ),
    )
    return IntrigueAcquisition(
        result=RuleResult(
            state=completed.state,
            events=(event, *acquisition_events, *completed.events),
        ),
        instance_id=instance_id,
        places_spy=bonus.places_spy,
        takes_contract=bonus.takes_contract,
    )


def _resolve_reveal_acquisition_triggers(
    state: GameState,
    player: int,
    acquired_card_id: str,
) -> RuleResult:
    if acquired_card_id != "the_spice_must_flow":
        return RuleResult(state=state)
    trigger_cards = tuple(
        played_card_id
        for played_card_id in state.players[player].in_play
        if personal_card_for_instance(played_card_id).reveal_acquisition_effect
        is (
            PersonalCardRevealAcquisitionEffect.GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW
        )
    )
    next_state = state
    events: tuple[GameEvent, ...] = ()
    for trigger_card_id in trigger_cards:
        for faction in spied_factions(next_state.players[player]):
            gained = gain_faction_influence(
                next_state,
                player,
                faction,
                1,
                event_prefix=(
                    f"round:{state.round_number}:player:{player}:"
                    f"reveal_card:{trigger_card_id}:spice_must_flow:"
                    f"{faction.value}"
                ),
            )
            next_state = gained.state
            events = (*events, *gained.events)
    return RuleResult(state=next_state, events=events)
