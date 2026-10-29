"""Card acquisition during Reveal and card-driven Agent effects."""

from copy import replace
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.content.immortality.board import genetic_markers_reached
from dune_imperium.content.immortality.tleilaxu import tleilaxu_card_for_instance
from dune_imperium.content.uprising.abilities import Ability, AbilityMark
from dune_imperium.content.uprising.agent_abilities import agent_box_ability
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.effect_dsl import (
    AcquireCardForSolari,
    AcquireCardUpTo,
    AdvanceTleilaxu,
    CommissionDreadnought,
    DrawIntrigueCards,
    Freighter,
    GainInfluence,
    GainResources,
    GeneticMarkersAtLeast,
    PlaceSpy,
    RecruitTroops,
    Research,
    Reward,
    TakeContract,
    TrashPersonalCard,
)
from dune_imperium.content.uprising.imperium import (
    ImperiumCardEntry,
    imperium_card_for_instance,
)
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.reveal_choice_abilities import (
    reveal_choice_ability,
)
from dune_imperium.content.uprising.trigger_abilities import (
    acquisition_ability,
)
from dune_imperium.content.uprising.types import (
    PersonalCardAcquisitionEffect,
    PersonalCardRevealChoiceEffect,
)
from dune_imperium.core.actions import ActionValue, DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquire_icons import (
    acquire_box_icons,
    queue_acquire_icons,
)
from dune_imperium.rules.action_shapes import Source
from dune_imperium.rules.box_events import BoxOutcome, agent_box_event
from dune_imperium.rules.card_trash import credit_trash_recruits, trash_personal_card
from dune_imperium.rules.contracts import (
    begin_contract_gain,
    complete_acquire_contracts,
    contract_gain_opens_market,
)
from dune_imperium.rules.deck_top import place_on_deck_top
from dune_imperium.rules.effects import (
    OptionalBlockKind,
    OptionalEffectBlock,
    active_agent_card,
    advance_after_effect,
    agent_card_source,
    current_agent_effect_context,
    recruit_shortfall_events,
    recruit_troops,
    short_of,
)
from dune_imperium.rules.frames import (
    OWED_ORIGIN_ACQUIRE,
    FrameKind,
    context_int,
    context_str,
    replace_player,
    reveal_is_open_for,
    turn_owner_of,
    update_turn_recruits,
)
from dune_imperium.rules.gain_events import resources_gained_event
from dune_imperium.rules.immortality import advance_research, advance_tleilaxu
from dune_imperium.rules.influence import gain_faction_influence
from dune_imperium.rules.intrigue_deck import (
    triggered_intrigue_draw,
)
from dune_imperium.rules.intrigue_triggers import fire_reveal_acquisition_intrigue
from dune_imperium.rules.optional_trash import open_optional_trash, trash_printer
from dune_imperium.rules.reveal_turn import (
    current_reveal_context,
    fire_guild_spy_on_spice_must_flow,
    open_pending_reveal_choice,
    pending_choice_rows,
    reveal_late_arrivals,
)
from dune_imperium.rules.scouts_modifiers import (
    discount_used_after,
    reserve_discount,
)
from dune_imperium.rules.spy_placement import (
    place_spy,
    recall_spy,
    spy_options,
)


class AcquireBlock(StrEnum):
    """Why a card of the Reveal shop cannot be acquired right now.

    Each Reveal acquisition provider keeps a card exactly when its block is
    None, and the page's greyed-out "can't acquire now" rows read the same
    block (``display.unavailable``, user request 2026-09-29), so the reason
    shown can never disagree with the legal list.
    """

    EMPTY = "empty"  # the Reserve stack has no card left
    NO_COST = "no_cost"  # no printed Persuasion cost to pay
    PERSUASION = "persuasion"  # costs more than the Persuasion left
    SPECIMENS = "specimens"  # costs more specimens than the seat holds
    NOT_IMPLEMENTED = "not_implemented"  # its acquire bonus is not implemented
    # Reclaimed Forces' Tleilaxu choice with the token on the track's last
    # space, where the advance does nothing (OQ-048, OQ-071).
    TLEILAXU_TRACK_END = "tleilaxu_track_end"


def deck_top_offered(state: GameState, player: int) -> bool:
    """Whether a card ``player`` acquires may go on top of their deck now.

    Recruitment Mission: "You may put cards you acquire on top of your deck"
    -- the whole card applies only to the owner's Reveal turn this round, and
    for each card acquired the owner chooses top of deck or discard pile
    [FAQ p. 3] (docs/rules/imperium-base.md 13.2). It is effective while the
    owner's own Reveal turn is open and cleared when that turn ends
    (``PlayerState.acquire_to_deck_top_round``); a card acquired before the
    Plot was played is unaffected (13.3), which holds as it is the Plot's
    play that sets the flag.

    Rise of Ix's Spaceport: "얻는 카드를 덱 위에 놓을 수 있다"
    (docs/rules/rise-of-ix.md 4) -- the same choice for every card its owner
    acquires, whenever it is acquired: the tile prints no round or turn, so
    it needs no open Reveal (stage P4c-2c). Both can apply at once; the card
    is placed once, where the owner chooses, and a Bypass Protocol card that
    is forced on top (``AcquireCardUpTo.to_deck_top``) has no choice to make.
    """

    owner = state.players[player]
    return (
        owner.acquire_to_deck_top_round and reveal_is_open_for(state, player)
    ) or (
        state.config.rise_of_ix
        and has_tech(owner.tech_ids, TechAbility.ACQUIRED_CARDS_ON_DECK)
    )


def with_deck_top_twins(
    state: GameState, player: int, actions: tuple[DomainAction, ...]
) -> tuple[DomainAction, ...]:
    """``actions`` with each followed by its ``to_deck_top`` twin while
    ``deck_top_offered`` (Recruitment Mission): the card's own row stays and
    the twin puts it on top of the deck instead of the discard pile."""

    if not deck_top_offered(state, player):
        return actions
    return tuple(
        twin
        for action in actions
        for twin in (
            action,
            replace(action, arguments=(*action.arguments, ("to_deck_top", True))),
        )
    )


def acquired_card_placed(
    owner: PlayerState, instance_id: str, *, to_deck_top: bool
) -> PlayerState:
    """``owner`` with an acquired card in the discard pile, or on top of the
    deck (Bypass Protocol, Recruitment Mission) -- placed first, so the
    card's acquire box resolves with it already there (the Immortality
    precedent, ``rules.tleilaxu_row``). A card put on top of the deck is
    known to every seat until it is drawn or the deck is shuffled (OQ-145,
    ``rules.deck_top``)."""

    if to_deck_top:
        return place_on_deck_top(owner, instance_id)
    return replace(owner, discard_pile=(*owner.discard_pile, instance_id))


def _wants_deck_top(action: DomainAction) -> bool:
    return dict(action.arguments).get("to_deck_top") is True


def take_imperium_row_card(
    state: GameState, instance_id: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Remove one Row card, refilling its position while the deck lasts.

    Returns the next ``(imperium_row, imperium_deck)`` pair. The Row refills
    from the top of the Imperium Deck [Main p. 13]; the official documents do
    not cover an exhausted deck, so by the OQ-004 project convention the Row
    then keeps operating with fewer cards, and nothing reshuffles back into
    the Imperium Deck.
    """

    row = list(state.imperium_row)
    if state.imperium_deck:
        row[row.index(instance_id)] = state.imperium_deck[0]
        return tuple(row), state.imperium_deck[1:]
    row.remove(instance_id)
    return tuple(row), state.imperium_deck


def legal_acquisition_spy_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return choices for a place-Spy acquisition bonus.

    Placing is mandatory while a Spy is in the supply (the erratum to
    [Main p. 11], OQ-057 (14)). Without one, "If you have no Spies in your
    supply when you need to place one, you may first recall one of your
    Spies for no effect" [Main pp. 11, 20]: the recall can be passed up
    (``decline_acquisition_spy``), and once made the Spy is back in the
    supply and must be placed.
    """

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
    options = spy_options(state, player, None, shared_post=False)
    return (
        *(
            (DomainAction(action_id="decline_acquisition_spy", actor=player),)
            if options.pass_up
            else ()
        ),
        *(
            DomainAction(
                action_id="recall_spy_for_acquisition",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.recall
        ),
        *(
            DomainAction(
                action_id="place_acquisition_spy",
                actor=player,
                arguments=(("post_id", post_id),),
            )
            for post_id in options.place
        ),
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
    if not isinstance(card_id, str):
        raise RuntimeError("acquisition Spy frame has invalid context")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"acquire:{card_id}"
    )
    if action.action_id == "decline_acquisition_spy":
        return RuleResult(
            state=_resume_after_acquisition_spy(state.pop_decision()),
            events=(
                GameEvent(
                    event_id=f"{source}:spy_unavailable",
                    kind="spy_placement_unavailable",
                    payload=(("card_id", card_id), ("player", action.actor)),
                ),
            ),
        )
    post_id = dict(action.arguments).get("post_id")
    if not isinstance(post_id, str):
        raise RuntimeError("acquisition Spy frame has invalid context")
    owner = state.players[action.actor]

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
    next_state = _resume_after_acquisition_spy(
        replace(
            state,
            players=replace_player(state.players, next_owner),
            decision_stack=state.decision_stack[:-1],
        )
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


def _contract_rows_only(before: GameState, after: GameState) -> GameState:
    """``after``, the state ``complete_acquire_contracts`` left over an
    Agent-turn acquisition's ``before``: a Contract completed in its owner's
    own turn waits on it as rows (OQ-112 (4)), so no window was pushed and
    the effect frame stays on top for ``advance_after_effect``."""

    if len(after.decision_stack) != len(before.decision_stack):
        raise RuntimeError("an Agent-turn Acquire Contract opened a window")
    return after


def _resume_after_acquisition_spy(state: GameState) -> GameState:
    """Advance the Agent turn under a finished acquisition Spy, if any.

    An Agent-turn acquisition (Price is No Object) returns to an effect
    frame that may have nothing left pending; advance it like every other
    discharging handler so the Agent turn can end. Reveal acquisitions
    return to the Reveal frame, which keeps its own purchase actions.
    """

    top_frame = state.decision_stack[-1] if state.decision_stack else None
    if top_frame is not None and top_frame.kind == FrameKind.AGENT_EFFECTS:
        return advance_after_effect(state, dict(top_frame.context))
    return state


def agent_box_acquisition(
    ability: Ability | None,
) -> tuple[AcquireCardUpTo | AcquireCardForSolari, GeneticMarkersAtLeast | None] | None:
    """The optional acquisition a recorded Agent box offers, and the genetic
    marker condition its line prints (composed effects, A3f).

    Tleilaxu Master's "If 1 genetic marker: You may acquire a card costing 6
    or less" and Price is No Object's Solari acquisition to hand: the
    refusal, then one row per card in reach; with the condition unmet the
    box offers nothing (it is optional and lapses at the turn's end).
    """

    if (
        ability is None
        or ability.mark is not AbilityMark.OPTIONAL
        or ability.icons
        or ability.hook is not None
        or len(ability.sections) != 1
        or ability.sections[0].costs
        or len(ability.sections[0].rewards) != 1
    ):
        return None
    (line,) = ability.sections
    (piece,) = line.rewards
    condition = line.condition
    if condition is not None and not isinstance(condition, GeneticMarkersAtLeast):
        return None
    match piece:
        case AcquireCardForSolari():
            return piece, condition
        case AcquireCardUpTo(to_hand_if=None | GeneticMarkersAtLeast()):
            return piece, condition
    return None


def _recorded_acquisition(
    context: dict[str, ActionValue],
) -> tuple[AcquireCardUpTo | AcquireCardForSolari, GeneticMarkersAtLeast | None] | None:
    return agent_box_acquisition(
        agent_box_ability(active_agent_card(context).agent_effect)
    )


def legal_agent_card_acquisitions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Return a recorded Agent box's optional acquisitions (see above)."""

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
    recorded = _recorded_acquisition(context)
    if recorded is None:
        return ()
    piece, condition = recorded
    if condition is not None and (
        _marker_block(state.players[player], condition) is not None
    ):
        # Judged now (OQ-028).
        return ()
    return (
        DomainAction(action_id="decline_agent_card_acquisition", actor=player),
        *_agent_card_acquisition_targets(state, player, piece),
    )


def _marker_block(
    owner: PlayerState, condition: GeneticMarkersAtLeast
) -> OptionalEffectBlock | None:
    markers = genetic_markers_reached(owner.research_space)
    return short_of(OptionalBlockKind.GENETIC_MARKERS, condition.count, markers)


def _agent_card_acquisition_targets(
    state: GameState, player: int, piece: AcquireCardUpTo | AcquireCardForSolari
) -> tuple[DomainAction, ...]:
    """The acquisitions the box's piece offers: by its cost cap, or paid in
    Solari to hand."""

    if isinstance(piece, AcquireCardUpTo):
        return (
            *(
                DomainAction(
                    action_id="acquire_reserve_by_card",
                    actor=player,
                    arguments=(("card_id", card_id),),
                )
                for card_id in acquirable_reserve_card_ids(state, piece.max_cost)
            ),
            *(
                DomainAction(
                    action_id="acquire_imperium_by_card",
                    actor=player,
                    arguments=(("instance_id", instance_id),),
                )
                for instance_id in acquirable_imperium_instance_ids(
                    state, piece.max_cost, player=player
                )
            ),
        )
    solari = state.players[player].resources.solari
    reserve_actions = tuple(
        DomainAction(
            action_id="acquire_reserve_with_solari",
            actor=player,
            arguments=(("card_id", card_id),),
        )
        for card_id, count in state.reserve_stacks
        if count > 0
        and not RESERVE_STACKS_BY_ID[card_id].icon_only
        and reserve_cost(state, card_id) <= solari
    )
    # The owner's own Manipulate set-aside card is offered too, for its
    # printed cost in Solari [FAQ p. 3].
    imperium_actions = tuple(
        DomainAction(
            action_id="acquire_imperium_with_solari",
            actor=player,
            arguments=(("instance_id", instance_id),),
        )
        for instance_id in acquirable_imperium_instance_ids(
            state, solari, player=player
        )
    )
    return (*reserve_actions, *imperium_actions)


def agent_card_acquisition_block(
    state: GameState, player: int
) -> OptionalEffectBlock | None:
    """Why a recorded Agent box's acquisition acquires nothing now.

    ``legal_agent_card_acquisitions`` offers it only while its genetic
    marker condition holds (``_marker_block``) and the cards exactly as
    ``_agent_card_acquisition_targets`` names them; with none, nothing is in
    reach (``needed``: the cost cap, 0 for a Solari acquisition, ``held``
    of them). None for any other box. The page greys an optional box that
    offers nothing out with it (``display.unavailable``, OQ-095 (2)).
    """

    try:
        _, context = current_agent_effect_context(state)
    except ValueError:
        return None
    recorded = _recorded_acquisition(context)
    if recorded is None:
        return None
    piece, condition = recorded
    owner = state.players[player]
    if condition is not None:
        marker = _marker_block(owner, condition)
        if marker is not None:
            return marker
    if _agent_card_acquisition_targets(state, player, piece):
        return None
    return OptionalEffectBlock(
        OptionalBlockKind.NOTHING_TO_ACQUIRE,
        needed=piece.max_cost if isinstance(piece, AcquireCardUpTo) else 0,
        held=owner.resources.solari,
    )


def apply_agent_card_acquisition(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Decline or acquire one card for a recorded Agent box."""

    if action not in legal_agent_card_acquisitions(state, action.actor):
        raise ValueError("action is not a legal Agent-card acquisition")
    _, context = current_agent_effect_context(state)
    recorded = _recorded_acquisition(context)
    assert recorded is not None
    context["pending_agent_effect"] = False
    card_instance_id = context_str(context, "card_id", owner="Agent-turn effect frame")
    box = agent_card_source(state.round_number, action.actor, card_instance_id)
    if action.action_id == "decline_agent_card_acquisition":
        next_state = advance_after_effect(state, context)
        return RuleResult(
            state=next_state,
            events=(
                agent_box_event(
                    box, card_instance_id, action.actor, BoxOutcome.DECLINED
                ),
            ),
        )

    if action.action_id == "acquire_reserve_with_solari":
        acquired = _acquire_reserve_to_hand_with_solari(state, action, context)
    elif action.action_id in ("acquire_reserve_by_card", "acquire_imperium_by_card"):
        piece, _ = recorded
        assert isinstance(piece, AcquireCardUpTo)
        acquired = _acquire_by_agent_card(state, action, context, piece, box)
    else:
        acquired = _acquire_imperium_to_hand_with_solari(state, action, context)
    return RuleResult(
        state=acquired.state,
        events=(
            *acquired.events,
            agent_box_event(box, card_instance_id, action.actor, BoxOutcome.RESOLVED),
        ),
    )


def _acquire_by_agent_card(
    state: GameState,
    action: DomainAction,
    context: dict[str, ActionValue],
    piece: AcquireCardUpTo,
    source: str,
) -> RuleResult:
    """A free acquisition by the cost cap, named after the box (``source``);
    ``to_hand_if`` (Tleilaxu Master's two genetic markers) sends it to the
    hand."""

    owner = state.players[action.actor]
    to_hand = isinstance(piece.to_hand_if, GeneticMarkersAtLeast) and (
        genetic_markers_reached(owner.research_space) >= piece.to_hand_if.count
    )
    # The box has resolved; the acquisition's own follow-ups (a Research
    # direction, a Spy post, the Contract market) stack above the turn.
    next_state = advance_after_effect(state, context)
    arguments = dict(action.arguments)
    if action.action_id == "acquire_reserve_by_card":
        acquired = acquire_reserve_for_intrigue(
            next_state,
            action.actor,
            str(arguments["card_id"]),
            to_hand=to_hand,
            source=source,
        )
    else:
        acquired = acquire_imperium_for_intrigue(
            next_state,
            action.actor,
            str(arguments["instance_id"]),
            to_hand=to_hand,
            source=source,
        )
    opened = open_acquisition_frames(
        acquired.result.state, action.actor, acquired, source=source
    )
    return RuleResult(
        state=opened.state, events=(*acquired.result.events, *opened.events)
    )


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
        hand_public=(*owner.hand_public, instance_id),
        resources=replace(
            owner.resources,
            solari=owner.resources.solari - reserve_cost(state, card_id),
        ),
        victory_points=owner.victory_points + definition.acquisition_vp,
    )
    reserve_stacks = tuple(
        (candidate_id, count - 1 if candidate_id == card_id else count)
        for candidate_id, count in state.reserve_stacks
    )
    discount_used = discount_used_after(state, card_id)
    prepared = replace(
        state,
        players=replace_player(state.players, next_owner),
        reserve_stacks=reserve_stacks,
        scouts_discount_used=discount_used,
    )
    completed = complete_acquire_contracts(
        prepared,
        action.actor,
        card_id,
        source=source,
    )
    # An Acquire Contract's icons wait on this Agent turn as rows; its
    # troops' row credits the turn's recruits itself [Main p. 10] [FAQ p. 4].
    next_state = advance_after_effect(
        _contract_rows_only(prepared, completed.state), context
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
    cost = definition.acquisition_cost
    if cost is None:
        raise RuntimeError("Imperium card is missing its acquisition cost")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"acquire_with_solari:{instance_id}"
    )

    imperium_row, imperium_deck, set_aside = take_acquired_imperium_card(
        state, action.actor, instance_id
    )
    owner = state.players[action.actor]
    next_owner = replace(
        owner,
        imperium_set_aside=set_aside,
        hand=(*owner.hand, instance_id),
        hand_public=(*owner.hand_public, instance_id),
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
    if bonus.recruited:
        # Arrakis Revolt's and Occupation's acquire-box troops join this
        # Agent turn's recruit count like any other Plot recruit [Main
        # p. 10] [FAQ p. 4]; ``context`` is written back below (and, for a
        # Combat-icon deployment, threaded through ``advance_after_effect``
        # further down), so the credit must land here rather than on a
        # frame ``update_turn_recruits`` would find and this handler would
        # then overwrite (the stale-context trap, ``docs/lessons.md``
        # 2026-09-26 item 4).
        previous = context_int(
            context, "troops_recruited", owner="Agent-turn effect frame"
        )
        context["troops_recruited"] = previous + bonus.recruited
    base_frame = replace(
        state.decision_stack[-1],
        context=tuple(sorted(context.items())),
    )
    prepared = replace(
        state,
        players=replace_player(state.players, next_owner),
        imperium_deck=imperium_deck,
        imperium_row=imperium_row,
        intrigue_deck=bonus.intrigue_deck,
        pending_intrigue_draws=_with_pending_draw(state, bonus.pending_draw),
        decision_stack=(*state.decision_stack[:-1], base_frame),
    )
    gained = _acquisition_influence(prepared, action.actor, definition, source=source)
    prepared = gained.state
    acquisition_events = (*acquisition_events, *gained.events)
    completed = complete_acquire_contracts(
        prepared,
        action.actor,
        definition.card.card_id,
        source=source,
    )
    # An Acquire Contract's icons wait on this Agent turn as rows; its
    # troops' row credits the turn's recruits itself.
    prepared = _contract_rows_only(prepared, completed.state)
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
    # A Research box (Immortality) opens its direction choice above the
    # settled effect frame, never inside it.
    tracked = apply_acquisition_track_effects(
        next_state, action.actor, definition, source=source
    )
    next_state = tracked.state
    acquisition_events = (*acquisition_events, *tracked.events)
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
    persuasion = revealer_persuasion(state, player)
    if persuasion is None:
        return ()
    return with_deck_top_twins(
        state,
        player,
        tuple(
            DomainAction(
                action_id="acquire_reserve",
                actor=player,
                arguments=(("card_id", card_id),),
            )
            for card_id, count in state.reserve_stacks
            if reserve_acquisition_block(state, card_id, count, persuasion) is None
        ),
    )


def revealer_persuasion(state: GameState, player: int) -> int | None:
    """Return the Persuasion ``player`` has left in their own open Reveal.

    None unless the decision on top is ``player``'s Reveal frame
    (``current_reveal_context``); a Reveal frame with invalid context raises,
    as the acquisition providers always did.
    """

    try:
        context = current_reveal_context(state)
    except ValueError:
        return None
    owner = context["turn_owner"]
    persuasion = context["persuasion"]
    if (
        isinstance(owner, bool)
        or not isinstance(owner, int)
        or isinstance(persuasion, bool)
        or not isinstance(persuasion, int)
    ):
        raise RuntimeError("Reveal frame has invalid acquisition context")
    return persuasion if owner == player else None


def reserve_acquisition_block(
    state: GameState, card_id: str, count: int, persuasion: int
) -> AcquireBlock | None:
    """Why one card of a Reserve stack holding ``count`` cannot be bought now.

    The cost is ``reserve_cost``'s, the one the payment reads too.
    """

    if count <= 0:
        return AcquireBlock.EMPTY
    if RESERVE_STACKS_BY_ID[card_id].icon_only:
        # The original game's Foldspace: "(Foldspace is acquired at the board
        # space of the same name ...)" [DI p. 11], only through its icon
        # [FAQ p. 2] (docs/rules/open-questions.md OQ-125).
        return AcquireBlock.NO_COST
    if reserve_cost(state, card_id) > persuasion:
        return AcquireBlock.PERSUASION
    return None


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
    to_deck_top = _wants_deck_top(action)
    owner = state.players[action.actor]
    next_owner = replace(
        acquired_card_placed(owner, instance_id, to_deck_top=to_deck_top),
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
    discount_used = discount_used_after(state, card_id)
    context["persuasion"] = persuasion - reserve_cost(state, card_id)
    frame = state.decision_stack[-1]
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    next_state = replace(
        state,
        players=players,
        reserve_stacks=reserve_stacks,
        scouts_discount_used=discount_used,
        decision_stack=(*state.decision_stack[:-1], next_frame),
    )
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}"
        ),
        kind="card_acquired",
        payload=(
            ("card_id", card_id),
            *((("destination", "deck_top"),) if to_deck_top else ()),
            ("player", action.actor),
        ),
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
    # A Reserve card's own acquisition effect is its Victory Points, so no
    # frame opens on shipped content; one that did would hold Call to Arms
    # until it closes (OQ-012, user ruling 2026-10-04).
    fired = fire_reveal_acquisition_intrigue(
        completed.state,
        action.actor,
        source=f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}",
        started=state,
    )
    return RuleResult(
        state=fired.state,
        events=(event, *triggered.events, *completed.events, *fired.events),
    )


def legal_imperium_acquisitions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Enumerate affordable cards currently visible in the Imperium Row."""

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    persuasion = revealer_persuasion(state, player)
    if persuasion is None:
        return ()
    return with_deck_top_twins(
        state,
        player,
        tuple(
            DomainAction(
                action_id="acquire_imperium",
                actor=player,
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in state.imperium_row
            if imperium_acquisition_block(instance_id, persuasion) is None
        ),
    )


def imperium_acquisition_block(
    instance_id: str, persuasion: int
) -> AcquireBlock | None:
    """Why an Imperium Row card cannot be bought with ``persuasion`` now."""

    cost = imperium_card_for_instance(instance_id).acquisition_cost
    if cost is None:
        return AcquireBlock.NO_COST
    if cost > persuasion:
        return AcquireBlock.PERSUASION
    return None


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
    cost = definition.acquisition_cost
    if cost is None:
        raise RuntimeError("Imperium card is missing its acquisition cost")

    context = current_reveal_context(state)
    persuasion = context["persuasion"]
    if isinstance(persuasion, bool) or not isinstance(persuasion, int):
        raise RuntimeError("Reveal frame has invalid Persuasion")
    imperium_row, imperium_deck = take_imperium_row_card(state, instance_id)
    to_deck_top = _wants_deck_top(action)
    owner = state.players[action.actor]
    next_owner = acquired_card_placed(owner, instance_id, to_deck_top=to_deck_top)
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
    if bonus.recruited:
        # Arrakis Revolt's and Occupation's acquire-box troops recruited
        # during a Reveal turn join that turn's Combat-icon deploy count
        # [Bloodlines p. 5], since a troop recruited "from any source" this
        # turn may be deployed [Main p. 10] [FAQ p. 4].
        previous = context_int(context, "reveal_troops_recruited", owner="Reveal frame")
        context["reveal_troops_recruited"] = previous + bonus.recruited
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
        imperium_deck=imperium_deck,
        imperium_row=imperium_row,
        intrigue_deck=intrigue_deck,
        pending_intrigue_draws=_with_pending_draw(state, bonus.pending_draw),
        decision_stack=decision_stack,
    )
    effects = _acquisition_effects(
        next_state,
        action.actor,
        definition,
        source=f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}",
    )
    next_state = effects.state
    acquisition_events = (*acquisition_events, *effects.events)
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
    # Call to Arms comes after the card's own acquisition effects (OQ-012),
    # also after the frames they opened -- the Spy post, the Research
    # direction, the Contract market -- once those are answered (user
    # ruling 2026-10-04).
    fired = fire_reveal_acquisition_intrigue(
        next_state,
        action.actor,
        source=f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}",
        started=state,
    )
    next_state = fired.state
    acquisition_events = (*acquisition_events, *fired.events)
    event = GameEvent(
        event_id=(
            f"round:{state.round_number}:player:{action.actor}:acquire:{instance_id}"
        ),
        kind="card_acquired",
        payload=(
            ("card_id", definition.card.card_id),
            *(
                (("destination", "deck_top"),)
                if to_deck_top
                # The instance is named only for the discard pile, as the
                # Tleilaxu Row's event does; the deck-top card is public too
                # (OQ-145, ``rules.deck_top``) but the payload stays as it
                # was so old saves replay their events.
                else (("instance_id", instance_id),)
            ),
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
    # Arrakis Revolt's and Occupation's acquire-box troops [RECRUIT_ONE_TROOP,
    # RECRUIT_THREE_TROOPS]; every caller must still join them to the turn's
    # recruit count itself [Main p. 10] [FAQ p. 4].
    recruited: int = 0


def _acquired_definition(instance_id: str) -> ImperiumCardEntry:
    """Return the Imperium-style definition behind a Row or Tleilaxu instance."""

    if instance_id.startswith("tleilaxu:"):
        return tleilaxu_card_for_instance(instance_id)
    return imperium_card_for_instance(instance_id)


def _acquire_rewards(definition: ImperiumCardEntry) -> tuple[Reward, ...]:
    """The rewards of the card's acquire box, from its record (composed A4a)."""

    ability = acquisition_ability(definition.acquisition_effect)
    return () if ability is None else ability.sections[0].rewards


def acquire_box_draws_intrigue(instance_id: str) -> bool:
    """Whether the acquire box of the Imperium Row or Tleilaxu card
    ``instance_id`` draws an Intrigue card (an owed draw, OQ-106)."""

    rewards = _acquire_rewards(_acquired_definition(instance_id))
    return any(isinstance(reward, DrawIntrigueCards) for reward in rewards)


def acquire_box_places_spy(instance_id: str) -> bool:
    """Whether the acquire box of the Imperium Row or Tleilaxu card
    ``instance_id`` places a Spy (``acquisition_spy_frame``)."""

    rewards = _acquire_rewards(_acquired_definition(instance_id))
    return any(isinstance(reward, PlaceSpy) for reward in rewards)


def _acquisition_effects(
    state: GameState, player: int, definition: ImperiumCardEntry, *, source: str
) -> RuleResult:
    """The acquired card's effects after its bonus, in this order: the
    acquire box's Influence (``_acquisition_influence``), its track steps
    (``apply_acquisition_track_effects``) and the Contracts the acquisition
    completes (``complete_acquire_contracts``)."""

    influenced = _acquisition_influence(state, player, definition, source=source)
    state, events = influenced.state, influenced.events
    tracked = apply_acquisition_track_effects(state, player, definition, source=source)
    completed = complete_acquire_contracts(
        _acquisition_trash(tracked.state, player, definition, source=source),
        player,
        definition.card.card_id,
        source=source,
    )
    return RuleResult(
        state=completed.state, events=(*events, *tracked.events, *completed.events)
    )


def _acquisition_trash(
    state: GameState, player: int, definition: ImperiumCardEntry, *, source: str
) -> GameState:
    """The acquire box's black Trash icon (Shai-Hulud, Rise of Ix).

    "When you acquire a card, you immediately resolve its acquire box, once"
    [Main p. 20] (docs/rules/player-turns.md), so the trash is offered the
    moment the card sits in its zone, as a row waiting on the owner's own
    turn or a window of its own elsewhere (``optional_trash``). The icon is
    optional: "Trash ... 비용이거나 카드가 자기를 trash하라고 할 때만 의무"
    [DI p. 16] (docs/rules/imperium-base.md 11), and neither applies to an
    acquire box's icon. It takes a card of the hand, the discard pile or
    play, the acquired card included once it is there.
    """

    if not any(
        isinstance(reward, TrashPersonalCard) for reward in _acquire_rewards(definition)
    ):
        return state
    return open_optional_trash(
        state,
        player,
        f"{source}:trash",
        printer=trash_printer(Source.ACQUISITION, definition.card.card_id),
    )


def apply_acquisition_track_effects(
    state: GameState,
    player: int,
    definition: ImperiumCardEntry,
    *,
    source: str,
) -> RuleResult:
    """Pay an acquire box that moves a Bene Tleilax token (Immortality).

    Spiritual Fervor's box researches and Subject X-137's advances the
    Tleilaxu token [card faces]; both resolve after the card has reached
    its zone, and the research may open a direction choice.
    """

    for reward in _acquire_rewards(definition):
        match reward:
            case Research():
                return advance_research(
                    state, player, source=f"{source}:acquisition_bonus"
                )
            case AdvanceTleilaxu(count=count):
                return advance_tleilaxu(state, player, count)
    return RuleResult(state=state)


def _acquisition_influence_faction(
    effect: PersonalCardAcquisitionEffect | None,
) -> Faction | None:
    """Return the Faction an acquisition bonus raises by one, if any: the
    box's single fixed Influence icon (Steersman, Imperial Throneship). A box
    of several icons or a chosen Faction is paid icon by icon instead
    (``rules.acquire_icons``) and is refused here, never half paid."""

    ability = acquisition_ability(effect)
    rewards = () if ability is None else ability.sections[0].rewards
    gains = [reward for reward in rewards if isinstance(reward, GainInfluence)]
    if not gains:
        return None
    (reward,) = gains
    if reward.factions is None or reward.requires_choice:
        raise ValueError(f"{reward!r} is not a fixed Faction's Influence")
    return reward.factions[0]


def _acquisition_influence(
    state: GameState,
    player: int,
    definition: ImperiumCardEntry,
    *,
    source: str,
) -> RuleResult:
    """The acquire box's Influence. One fixed Faction's icon is gained at
    once (``<source>:influence:<faction>``), as it always was; a box of
    several icons or a Faction of the owner's choice waits as a row per icon
    on the owner's turn (``acquire_icons``, OQ-141)."""

    if acquire_box_icons(definition) is not None:
        return RuleResult(
            state=queue_acquire_icons(state, player, definition, source=source)
        )
    faction = _acquisition_influence_faction(definition.acquisition_effect)
    if faction is None:
        return RuleResult(state=state)
    return gain_faction_influence(
        state,
        player,
        faction,
        1,
        event_prefix=f"{source}:influence:{faction.value}",
    )


def _resolve_imperium_acquisition_bonus(
    state: GameState,
    player: int,
    instance_id: str,
    owner: PlayerState,
) -> AcquisitionBonus:
    """Apply one supported acquisition bonus before its follow-up choice."""

    definition = _acquired_definition(instance_id)
    rewards = _acquire_rewards(definition)
    intrigue_deck = state.intrigue_deck
    events: tuple[GameEvent, ...] = ()
    pending_draw: tuple[int, int, str] | None = None
    recruited = 0
    box = f"round:{state.round_number}:player:{player}:acquire:{instance_id}"
    for reward in rewards:
        match reward:
            case DrawIntrigueCards(count=count):
                if count != 1:
                    raise ValueError(f"{reward!r}: an acquire box draws one card")
                # Overthrow's acquire box: inside the seat's own turn the
                # card is its own step, the one right after the purchase:
                # "Acquire Effects must be taken immediately upon acquiring
                # the Card or Tech." (Direwolf Discord; user decision
                # 2026-10-10, OQ-106, ``draw_is_immediate``; OQ-042). The Row
                # refill still makes the purchase itself irreversible.
                owner, intrigue_deck, drawn, pending_draw = triggered_intrigue_draw(
                    state,
                    owner,
                    player,
                    origin=f"{OWED_ORIGIN_ACQUIRE}{instance_id}",
                    source=f"{box}:intrigue_draw",
                )
                events = (*events, *drawn)
            case GainResources():
                # Price is No Object's and Corrino Genes' 2 Solari, Possible
                # Futures' water, Lisan al Gaib's spice.
                owner = replace(
                    owner,
                    resources=replace(
                        owner.resources,
                        solari=owner.resources.solari + reward.solari,
                        spice=owner.resources.spice + reward.spice,
                        water=owner.resources.water + reward.water,
                    ),
                )
                events = (
                    *events,
                    resources_gained_event(
                        box,
                        player,
                        solari=reward.solari,
                        spice=reward.spice,
                        water=reward.water,
                    ),
                )
            case RecruitTroops(count=wanted):
                # Arrakis Revolt's (promo) and Occupation's (Immortality)
                # acquire boxes: the troops go to the garrison like any
                # recruit [Main p. 20].
                owner, recruited = recruit_troops(owner, wanted)
                troop_source = f"{box}:troop"
                events = (
                    *events,
                    GameEvent(
                        event_id=troop_source,
                        kind="acquisition_troop_recruited",
                        payload=(("amount", recruited), ("player", player)),
                    ),
                    *recruit_shortfall_events(troop_source, player, wanted, recruited),
                )
            case (
                PlaceSpy()
                | TakeContract()
                | GainInfluence()
                | Research()
                | TrashPersonalCard()
                | CommissionDreadnought()
                | Freighter()
            ):
                # Left to the purchase path: its Spy choice or Contract
                # market, the Influence, the track after the card's zone, the
                # optional trash once the card sits in its zone
                # (``_acquisition_trash``), Full-Scale Assault's optional
                # Dreadnought icon and Appropriate's optional Freighter icon
                # (``acquire_icons``).
                pass
            case AdvanceTleilaxu():
                pass
            case _:
                raise TypeError(f"{reward!r} is not an acquire box's reward")
    return AcquisitionBonus(
        owner=owner,
        intrigue_deck=intrigue_deck,
        events=events,
        places_spy=any(isinstance(reward, PlaceSpy) for reward in rewards),
        takes_contract=any(isinstance(reward, TakeContract) for reward in rewards),
        pending_draw=pending_draw,
        recruited=recruited,
    )


def _with_pending_draw(
    state: GameState,
    pending_draw: tuple[int, int, str] | None,
) -> tuple[tuple[int, int, str], ...]:
    if pending_draw is None:
        return state.pending_intrigue_draws
    return (*state.pending_intrigue_draws, pending_draw)


# Shared with the Tleilaxu Row acquisition (``rules.tleilaxu_row``).
resolve_acquisition_bonus = _resolve_imperium_acquisition_bonus
with_pending_draw = _with_pending_draw


def reserve_cost(state: GameState, card_id: str) -> int:
    """Return what acquiring one card of a Reserve stack costs now.

    Every legality check and payment of a Reserve acquisition reads its cost
    here, so an effect that changes it (Arrakeen Scouts' Market Opening)
    changes the check and the payment together.
    """

    printed = RESERVE_STACKS_BY_ID[card_id].acquisition_cost
    return max(0, printed - reserve_discount(state, card_id))


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
            # Ilesa Ecaz's card set aside by One Step Ahead (Rise of Ix).
            (player.set_aside_card_id,) if player.set_aside_card_id else (),
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



MANIPULATE_DISCOUNT = 1


def manipulated_cost(instance_id: str) -> int | None:
    """What a set-aside (Manipulate) card costs its owner: one less."""

    cost = imperium_card_for_instance(instance_id).acquisition_cost
    if cost is None:
        return None
    return max(cost - MANIPULATE_DISCOUNT, 0)


def legal_manipulated_acquisitions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Offer the revealer their own set-aside Imperium cards at the discount.

    Only the player who removed the card may acquire it [FAQ p. 3], for one
    Persuasion less [Manipulate card], during their Reveal turn this round.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("player must identify a configured seat")
    owner = state.players[player]
    if not owner.imperium_set_aside:
        return ()
    persuasion = revealer_persuasion(state, player)
    if persuasion is None:
        return ()
    return with_deck_top_twins(
        state,
        player,
        tuple(
            DomainAction(
                action_id="acquire_manipulated_imperium",
                actor=player,
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in owner.imperium_set_aside
            if manipulated_acquisition_block(instance_id, persuasion) is None
        ),
    )


def manipulated_acquisition_block(
    instance_id: str, persuasion: int
) -> AcquireBlock | None:
    """Why a set-aside card cannot be bought back with ``persuasion`` now."""

    cost = manipulated_cost(instance_id)
    if cost is None:
        return AcquireBlock.NO_COST
    if cost > persuasion:
        return AcquireBlock.PERSUASION
    definition = imperium_card_for_instance(instance_id)
    if definition.has_acquisition_bonus and definition.acquisition_effect is None:
        return AcquireBlock.NOT_IMPLEMENTED
    return None


def apply_manipulated_acquisition(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Acquire one set-aside Imperium card for one Persuasion less."""

    if action not in legal_manipulated_acquisitions(state, action.actor):
        raise ValueError("action is not a legal set-aside acquisition")
    instance_id = dict(action.arguments)["instance_id"]
    if not isinstance(instance_id, str):
        raise ValueError("set-aside acquisition instance_id must be a string")
    definition = imperium_card_for_instance(instance_id)
    cost = manipulated_cost(instance_id)
    if cost is None:
        raise RuntimeError("set-aside Imperium card is missing its cost")

    context = current_reveal_context(state)
    persuasion = context["persuasion"]
    if isinstance(persuasion, bool) or not isinstance(persuasion, int):
        raise RuntimeError("Reveal frame has invalid Persuasion")
    to_deck_top = _wants_deck_top(action)
    owner = state.players[action.actor]
    next_owner = acquired_card_placed(
        replace(
            owner,
            imperium_set_aside=tuple(
                held for held in owner.imperium_set_aside if held != instance_id
            ),
        ),
        instance_id,
        to_deck_top=to_deck_top,
    )
    bonus = _resolve_imperium_acquisition_bonus(
        state,
        action.actor,
        instance_id,
        next_owner,
    )
    context["persuasion"] = persuasion - cost
    if bonus.recruited:
        # Same Reveal-turn recruit count as the ordinary Row purchase
        # [Main p. 10] [FAQ p. 4] [Bloodlines p. 5].
        previous = context_int(context, "reveal_troops_recruited", owner="Reveal frame")
        context["reveal_troops_recruited"] = previous + bonus.recruited
    frame = state.decision_stack[-1]
    next_frame = replace(frame, context=tuple(sorted(context.items())))
    decision_stack = (*state.decision_stack[:-1], next_frame)
    if bonus.places_spy:
        decision_stack = (
            *decision_stack,
            acquisition_spy_frame(state, action.actor, instance_id),
        )
    next_state = replace(
        state,
        players=replace_player(state.players, bonus.owner),
        intrigue_deck=bonus.intrigue_deck,
        pending_intrigue_draws=_with_pending_draw(state, bonus.pending_draw),
        decision_stack=decision_stack,
    )
    acquisition_events = bonus.events
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"acquire_manipulated:{instance_id}"
    )
    effects = _acquisition_effects(next_state, action.actor, definition, source=source)
    next_state = effects.state
    acquisition_events = (*acquisition_events, *effects.events)
    if bonus.takes_contract:
        contracts = begin_contract_gain(
            next_state,
            action.actor,
            1,
            source=f"{source}:acquisition_bonus",
        )
        next_state = contracts.state
        acquisition_events = (*acquisition_events, *contracts.events)
    # As on the Row: after the frames the card's own effects opened
    # (OQ-012, user ruling 2026-10-04).
    fired = fire_reveal_acquisition_intrigue(
        next_state,
        action.actor,
        source=source,
        started=state,
    )
    next_state = fired.state
    acquisition_events = (*acquisition_events, *fired.events)
    event = GameEvent(
        event_id=source,
        kind="card_acquired",
        payload=(
            ("card_id", definition.card.card_id),
            *((("destination", "deck_top"),) if to_deck_top else ()),
            ("discount", MANIPULATE_DISCOUNT),
            *(() if to_deck_top else (("instance_id", instance_id),)),
            ("player", action.actor),
        ),
    )
    return RuleResult(state=next_state, events=(event, *acquisition_events))


def acquirable_reserve_card_ids(
    state: GameState,
    max_cost: int,
) -> tuple[str, ...]:
    """Return non-empty Reserve stacks whose current cost is within the cap.

    The cost is ``reserve_cost``'s, so a discount in force (Arrakeen Scouts'
    Market Opening) counts toward the cap.
    """

    return tuple(
        card_id
        for card_id, count in state.reserve_stacks
        if count > 0
        # Foldspace is never one (OQ-125).
        and not RESERVE_STACKS_BY_ID[card_id].icon_only
        and reserve_cost(state, card_id) <= max_cost
    )


def acquirable_imperium_instance_ids(
    state: GameState,
    max_cost: int,
    *,
    player: int | None = None,
) -> tuple[str, ...]:
    """Return Imperium cards within the cap whose bonus is implemented.

    The Row's cards, then -- when ``player`` is given -- that player's own
    Manipulate set-aside cards at their printed cost: "You may use other
    means to acquire the card (for example: Bypass Protocol, Boundless
    Ambition), though the 1 persuasion discount will not apply" [FAQ p. 3].
    An opponent's set-aside card is never offered [FAQ p. 3].
    """

    set_aside = () if player is None else state.players[player].imperium_set_aside
    return tuple(
        instance_id
        for instance_id in (*state.imperium_row, *set_aside)
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


def take_acquired_imperium_card(
    state: GameState, player: int, instance_id: str
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Remove a card a non-Reveal acquire effect took from the Row or set-aside.

    Returns the next ``(imperium_row, imperium_deck, imperium_set_aside)``
    triple for ``player``. A Row card refills its position
    (``take_imperium_row_card``); the owner's own Manipulate set-aside card
    simply leaves that zone, since the Row already refilled when it was set
    aside [Manipulate card] [FAQ p. 3].
    """

    set_aside = state.players[player].imperium_set_aside
    if instance_id in set_aside:
        return (
            state.imperium_row,
            state.imperium_deck,
            tuple(held for held in set_aside if held != instance_id),
        )
    imperium_row, imperium_deck = take_imperium_row_card(state, instance_id)
    return imperium_row, imperium_deck, set_aside


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


def open_acquisition_frames(
    state: GameState, player: int, acquired: IntrigueAcquisition, *, source: str
) -> RuleResult:
    """Open what an acquisition left its caller: the acquired card's Spy post
    (``acquisition_spy_frame``) or else the Contract market (named
    ``<source>:acquisition_bonus``); the events are the market's only."""

    if acquired.places_spy:
        return RuleResult(
            state=state.push_decision(
                acquisition_spy_frame(state, player, acquired.instance_id)
            ),
            events=(),
        )
    if acquired.takes_contract:
        return begin_contract_gain(
            state, player, 1, source=f"{source}:acquisition_bonus"
        )
    return RuleResult(state=state, events=())


def acquire_reserve_for_intrigue(
    state: GameState,
    player: int,
    card_id: str,
    *,
    to_hand: bool,
    source: str,
    to_deck_top: bool = False,
) -> IntrigueAcquisition:
    """Acquire one Reserve card without Persuasion for an Intrigue effect.

    ``to_deck_top`` puts it on top of the deck instead of the discard pile
    (Bypass Protocol, Recruitment Mission); never together with ``to_hand``.
    """

    if to_hand and to_deck_top:
        raise ValueError("a card goes to the hand or the deck top, not both")
    definition = RESERVE_STACKS_BY_ID[card_id]
    instance_id = next_reserve_instance_id(state, card_id)
    owner = state.players[player]
    destination = "hand" if to_hand else "deck_top" if to_deck_top else "discard"
    placed = (
        replace(
            owner,
            hand=(*owner.hand, instance_id),
            hand_public=(*owner.hand_public, instance_id),
        )
        if to_hand
        else acquired_card_placed(owner, instance_id, to_deck_top=to_deck_top)
    )
    next_owner = replace(
        placed, victory_points=owner.victory_points + definition.acquisition_vp
    )
    reserve_stacks = tuple(
        (candidate_id, count - 1 if candidate_id == card_id else count)
        for candidate_id, count in state.reserve_stacks
    )
    discount_used = discount_used_after(state, card_id)
    prepared = replace(
        state,
        players=replace_player(state.players, next_owner),
        reserve_stacks=reserve_stacks,
        scouts_discount_used=discount_used,
    )
    triggered = _resolve_reveal_acquisition_triggers(prepared, player, card_id)
    completed = complete_acquire_contracts(
        triggered.state, player, card_id, source=source
    )
    fired = fire_reveal_acquisition_intrigue(
        completed.state,
        player,
        source=source,
        started=state,
    )
    event = GameEvent(
        event_id=f"{source}:acquired:{instance_id}",
        kind="card_acquired",
        payload=(
            ("card_id", card_id),
            ("destination", destination),
            ("player", player),
        ),
    )
    result_state = fired.state
    result_events: tuple[GameEvent, ...] = (
        event,
        *triggered.events,
        *completed.events,
        *fired.events,
    )
    if to_hand and reveal_is_open_for(result_state, player):
        # A card acquired to hand during the owner's own Reveal turn is
        # revealed and used at once rather than withheld [FAQ p. 3].
        late = reveal_late_arrivals(result_state, player, (instance_id,))
        result_state = late.state
        result_events = (*result_events, *late.events)
    return IntrigueAcquisition(
        result=RuleResult(state=result_state, events=result_events),
        instance_id=instance_id,
    )


def legal_reveal_command_acquisition_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Engineered Miracle: "Command: Trash this card -> Acquire a card from
    the Imperium Row" (any cost, no Persuasion).

    An arrow cost: no refusal is offered, and the choice lapses at
    ``finish_reveal`` when it is left unused (OQ-095 (7) addition).
    """

    pending = pending_choice_rows(
        state, player, legal_reveal_command_acquisition_actions
    )
    if pending is not None:
        return pending
    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    expected = PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD
    if context.get("reveal_choice_effect") != expected.value:
        return ()
    source_card_id = context.get("reveal_card_id")
    if source_card_id not in state.players[player].in_play:
        # The card already left play (another effect trashed it while this
        # choice waited): an effect of a trashed card can't be activated
        # (OQ-022), so nothing remains.
        return ()
    return with_deck_top_twins(
        state,
        player,
        tuple(
            DomainAction(
                action_id="command_acquire_row_card",
                actor=player,
                arguments=(("instance_id", instance_id),),
            )
            for instance_id in state.imperium_row
        ),
    )


def apply_reveal_command_acquisition(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Trash the revealed card and take the chosen Imperium Row card."""

    state = open_pending_reveal_choice(state, action)
    if action not in legal_reveal_command_acquisition_actions(state, action.actor):
        raise ValueError("action is not a legal Command acquisition choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    source_card_id = context.get("reveal_card_id")
    if not isinstance(source_card_id, str):
        raise RuntimeError("Reveal acquisition frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{source_card_id}:command_acquisition"
    )
    popped = replace(state, decision_stack=state.decision_stack[:-1])
    instance_id = str(dict(action.arguments)["instance_id"])
    trashed = trash_personal_card(popped, action.actor, source_card_id, source=source)
    # The Reveal frame, not an AGENT_EFFECTS one, is below: the self-trash's
    # own troops (none on a shipped card yet) are credited here.
    trashed = credit_trash_recruits(trashed, action.actor)
    acquired = acquire_imperium_for_intrigue(
        trashed.state,
        action.actor,
        instance_id,
        to_hand=False,
        source=source,
        to_deck_top=_wants_deck_top(action),
    )
    opened = open_acquisition_frames(
        acquired.result.state, action.actor, acquired, source=source
    )
    return RuleResult(
        state=opened.state,
        events=(*trashed.events, *acquired.result.events, *opened.events),
    )


# --- A card's "Acquire a card that costs N or less" ---------------------------
# Boundless Ambition (Rise of Ix promo): revealed, a mandatory Reveal choice;
# discarded or trashed, the acquisition window of its Unload (``rules.unload``).

_REVEAL_UP_TO: Final = PersonalCardRevealChoiceEffect.ACQUIRE_CARD_UP_TO_FIVE


def acquisition_cap(effect: PersonalCardRevealChoiceEffect) -> int | None:
    """The cost cap of a Reveal choice whose record is one "Acquire a card
    that costs N or less" (``AcquireCardUpTo``), else None."""

    ability = reveal_choice_ability(effect)
    if len(ability.sections) != 1:
        return None
    (line,) = ability.sections
    if line.costs or line.condition is not None or len(line.rewards) != 1:
        return None
    (piece,) = line.rewards
    return piece.max_cost if isinstance(piece, AcquireCardUpTo) else None


def acquisitions_up_to(
    state: GameState,
    player: int,
    max_cost: int,
    *,
    imperium_action: str,
    reserve_action: str,
) -> tuple[DomainAction, ...]:
    """The rows of a free "Acquire a card that costs ``max_cost`` or less"
    for ``player``: each Reserve card and each Imperium Row card within the
    cap (and the seat's own Manipulate set-aside card, at its printed cost
    [FAQ p. 3]), never Foldspace (OQ-125), each followed by its deck-top twin
    while one is offered (Recruitment Mission, Spaceport)."""

    return with_deck_top_twins(
        state,
        player,
        (
            *(
                DomainAction(
                    action_id=reserve_action,
                    actor=player,
                    arguments=(("card_id", card_id),),
                )
                for card_id in acquirable_reserve_card_ids(state, max_cost)
            ),
            *(
                DomainAction(
                    action_id=imperium_action,
                    actor=player,
                    arguments=(("instance_id", instance_id),),
                )
                for instance_id in acquirable_imperium_instance_ids(
                    state, max_cost, player=player
                )
            ),
        ),
    )


def acquire_by_row(
    state: GameState, player: int, action: DomainAction, *, source: str
) -> RuleResult:
    """Acquire the card an ``acquisitions_up_to`` row names -- to the discard
    pile, or for its twin on top of the deck -- and open what the acquisition
    leaves its caller (``open_acquisition_frames``), named after ``source``."""

    arguments = dict(action.arguments)
    to_deck_top = _wants_deck_top(action)
    if "instance_id" in arguments:
        acquired = acquire_imperium_for_intrigue(
            state,
            player,
            str(arguments["instance_id"]),
            to_hand=False,
            source=source,
            to_deck_top=to_deck_top,
        )
    else:
        acquired = acquire_reserve_for_intrigue(
            state,
            player,
            str(arguments["card_id"]),
            to_hand=False,
            source=source,
            to_deck_top=to_deck_top,
        )
    opened = open_acquisition_frames(
        acquired.result.state, player, acquired, source=source
    )
    return RuleResult(
        state=opened.state, events=(*acquired.result.events, *opened.events)
    )


def legal_reveal_card_acquisition_actions(
    state: GameState,
    player: int,
) -> tuple[DomainAction, ...]:
    """Boundless Ambition's Reveal: "Acquire a card that costs [5] or less."
    [Steam app text], from the Row or the Reserve (OQ-125).

    Mandatory: it holds ``finish_reveal`` while a card is in reach, and with
    none it offers nothing and lapses there, as every mandatory choice with
    nothing to choose does (``mandatory_choice_is_pending``).
    """

    pending = pending_choice_rows(
        state, player, legal_reveal_card_acquisition_actions
    )
    if pending is not None:
        return pending
    if not 0 <= player < state.config.players or not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    if context.get("reveal_choice_effect") != _REVEAL_UP_TO.value:
        return ()
    if context.get("reveal_card_id") not in state.players[player].in_play:
        # Another effect trashed the card while the choice waited (OQ-022).
        return ()
    max_cost = acquisition_cap(_REVEAL_UP_TO)
    assert max_cost is not None
    return acquisitions_up_to(
        state,
        player,
        max_cost,
        imperium_action="acquire_reveal_imperium_card",
        reserve_action="acquire_reveal_reserve_card",
    )


def apply_reveal_card_acquisition(
    state: GameState,
    action: DomainAction,
) -> RuleResult:
    """Acquire the chosen card for a revealed card's acquisition; the choice
    is used up."""

    state = open_pending_reveal_choice(state, action)
    if action not in legal_reveal_card_acquisition_actions(state, action.actor):
        raise ValueError("action is not a legal Reveal acquisition")
    context = dict(state.decision_stack[-1].context)
    source_card_id = context.get("reveal_card_id")
    if not isinstance(source_card_id, str):
        raise RuntimeError("Reveal acquisition frame has invalid card ID")
    source = (
        f"round:{state.round_number}:player:{action.actor}:"
        f"reveal_card:{source_card_id}:acquisition"
    )
    return acquire_by_row(state.pop_decision(), action.actor, action, source=source)


def acquire_imperium_for_intrigue(
    state: GameState,
    player: int,
    instance_id: str,
    *,
    to_hand: bool,
    source: str,
    from_market: bool = False,
    to_deck_top: bool = False,
) -> IntrigueAcquisition:
    """Acquire one Imperium Row card without Persuasion for an Intrigue effect.

    The Row position refills from the Imperium Deck at once [Main p. 13] and
    any acquire box resolves immediately [Main p. 20]. Bonuses that need a
    follow-up decision are reported to the caller instead of pushing frames.
    ``from_market`` takes the card from Arrakeen Scouts' Critical Moment
    cards instead of the Row, with nothing to refill. The player's own
    Manipulate set-aside card is taken from that zone instead, also with
    nothing to refill (``take_acquired_imperium_card``, [FAQ p. 3]).
    ``to_deck_top`` puts the card on top of the deck instead of the discard
    pile (Bypass Protocol, Recruitment Mission), placed before its acquire
    box resolves; never together with ``to_hand``.
    """

    if to_hand and to_deck_top:
        raise ValueError("a card goes to the hand or the deck top, not both")
    definition = imperium_card_for_instance(instance_id)
    if definition.has_acquisition_bonus and definition.acquisition_effect is None:
        raise NotImplementedError(
            f"acquisition bonus is not implemented: {definition.card.card_id}"
        )
    destination = "hand" if to_hand else "deck_top" if to_deck_top else "discard"
    market = state.scouts_market_cards
    owner = state.players[player]
    set_aside = owner.imperium_set_aside
    if from_market:
        if instance_id not in market:
            raise ValueError("the card is not among the revealed cards")
        imperium_row, imperium_deck = state.imperium_row, state.imperium_deck
        market = tuple(card for card in market if card != instance_id)
    else:
        imperium_row, imperium_deck, set_aside = take_acquired_imperium_card(
            state, player, instance_id
        )
    taken_owner = replace(owner, imperium_set_aside=set_aside)
    next_owner = (
        replace(
            taken_owner,
            hand=(*owner.hand, instance_id),
            hand_public=(*owner.hand_public, instance_id),
        )
        if to_hand
        else acquired_card_placed(taken_owner, instance_id, to_deck_top=to_deck_top)
    )
    bonus = _resolve_imperium_acquisition_bonus(state, player, instance_id, next_owner)
    prepared = replace(
        state,
        players=replace_player(state.players, bonus.owner),
        imperium_deck=imperium_deck,
        imperium_row=imperium_row,
        scouts_market_cards=market,
        intrigue_deck=bonus.intrigue_deck,
        pending_intrigue_draws=_with_pending_draw(state, bonus.pending_draw),
    )
    if bonus.recruited and turn_owner_of(prepared) == player:
        # Shared by many callers: a card-granted Acquire Tech style effect
        # played mid-turn (Tleilaxu Master, a Leader's Signet acquisition,
        # Engineered Miracle's Command, a Navigation or Inspire Awe pick),
        # where the recruiting frame may no longer be the stack's top by
        # now, and Impress's identical Combat reward or an Arrakeen Scouts
        # Critical Moment purchase, which are outside any turn and credit
        # nothing. Troops recruited during the owner's own turn "from any
        # source" join its deploy allowance [Main p. 10] [FAQ p. 4];
        # ``turn_owner_of`` finds that turn's frame directly instead of
        # trusting a possibly stale local context.
        prepared = update_turn_recruits(prepared, troops_recruited=bonus.recruited)
    acquisition_events = bonus.events
    completed = _acquisition_effects(prepared, player, definition, source=source)
    # The caller opens the Spy post or the Contract market only after this
    # returns (after the Intrigue card itself, [Main p. 20]); Call to Arms
    # waits for those frames too, like for a Research direction opened here
    # (OQ-012, user ruling 2026-10-04). An exhausted market opens none.
    fired = fire_reveal_acquisition_intrigue(
        completed.state,
        player,
        source=source,
        started=state,
        frames_follow=(
            bonus.places_spy
            or (
                bonus.takes_contract
                and contract_gain_opens_market(completed.state, player)
            )
        ),
    )
    event = GameEvent(
        event_id=f"{source}:acquired:{instance_id}",
        kind="card_acquired",
        payload=(
            ("card_id", definition.card.card_id),
            ("destination", destination),
            # A card put on top of the deck is named by its identity only, as
            # the Tleilaxu Row's event does (the payload predates OQ-145,
            # which makes that card public: ``rules.deck_top``).
            *(() if to_deck_top else (("instance_id", instance_id),)),
            ("player", player),
        ),
    )
    result_state = fired.state
    result_events: tuple[GameEvent, ...] = (
        event,
        *acquisition_events,
        *completed.events,
        *fired.events,
    )
    if to_hand and reveal_is_open_for(result_state, player):
        # A card acquired to hand during the owner's own Reveal turn is
        # revealed and used at once rather than withheld [FAQ p. 3].
        late = reveal_late_arrivals(result_state, player, (instance_id,))
        result_state = late.state
        result_events = (*result_events, *late.events)
    return IntrigueAcquisition(
        result=RuleResult(state=result_state, events=result_events),
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
    # Guild Spy: once per copy per Reveal, only during the owner's Reveal
    # (designer ruling, OQ-057).
    return fire_guild_spy_on_spice_must_flow(state, player, acquired=True)
