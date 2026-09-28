"""Arrakeen Scouts: one seat's cost -> reward line, and the subcommittees.

``push_scouts_effect`` opens a ``scouts_effect`` frame that resolves one
``ScoutsOption`` for one seat: its costs in order, then its rewards in
order (docs/rules/arrakeen-scouts.md). Each step is either automatic (paid
or gained at once, possibly opening another module's frame: a Spy
placement, a Contract pick, a reshuffle) or a choice this frame offers (a
card to discard or trash, a Spy to recall, a Faction, an Agent). The frame
stays on the stack under any frame a step opens and moves its cursor before
opening it, so it resumes by itself once that frame pops; the engine's
automatic advance runs the automatic steps. The same frame serves inside a
turn (a subcommittee joined at the High Council) and in the Scouts step.

Subcommittees [Scouts help] (docs/rules/arrakeen-scouts.md 4): taking a
High Council seat queues one offer (OQ-076); the offer lists the unclaimed
subcommittees whose cost the seat can pay, and joining one opens its line.
"""

from dataclasses import replace
from typing import Final, cast

from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS_BY_ID,
    EVENTS_BY_ID,
    SALES_BY_ID,
    SUBCOMMITTEES_BY_ID,
    ScoutsOption,
)
from dune_imperium.content.arrakeen_scouts.types import (
    AcquireReserveCardToHand,
    GainLowestInfluence,
    GainSpiceWithHelixBonus,
    LoseFactionInfluence,
    LoseGarrisonTroops,
    PaySpecimens,
    RecallOtherAgent,
    RecruitToConflict,
    ScoutsCost,
    ScoutsReward,
)
from dune_imperium.content.uprising.board import OBSERVATION_POSTS, Faction
from dune_imperium.content.uprising.effect_dsl import (
    DiscardFromHand,
    FlipBattleCard,
    FlipFaceUpConflictCard,
    GainInfluence,
    GiveIntrigueToOpponent,
    LoseInfluence,
    LoseTroops,
    PayResources,
    PlaceSpy,
    RecallSpy,
    RetreatTroops,
    Reward,
    TrashDiscardPileCard,
    TrashIntrigueCard,
    TrashPersonalCard,
)
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import acquire_reserve_for_intrigue
from dune_imperium.rules.card_discard import discard_personal_card_from_hand
from dune_imperium.rules.card_trash import trash_personal_card
from dune_imperium.rules.effect_interpreter import apply_rewards
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
    turn_owner_of,
    update_turn_recruits,
)
from dune_imperium.rules.influence import (
    MAX_INFLUENCE,
    gain_faction_influence,
    influence_amount,
)
from dune_imperium.rules.optional_trash import optional_trash_frame
from dune_imperium.rules.spy_moves import spy_placement_frame

_EFFECT_FRAME: Final = "Scouts effect frame"
_OFFER_FRAME: Final = "Subcommittee offer frame"
_ALL_POSTS: Final = tuple(post.post_id for post in OBSERVATION_POSTS)

type ScoutsStep = ScoutsCost | ScoutsReward
# Steps ``apply_rewards`` cannot take; the ones this module handles itself
# never reach it, the rest arrive with later slices.
_NOT_DSL_REWARDS: Final = (
    LoseFactionInfluence,
    LoseInfluence,
    LoseTroops,
    GiveIntrigueToOpponent,
    RetreatTroops,
    FlipBattleCard,
    TrashDiscardPileCard,
    FlipFaceUpConflictCard,
    GainSpiceWithHelixBonus,
)


# --- Which option -------------------------------------------------------------------


def scouts_option(item: str, index: int) -> ScoutsOption:
    """Return option ``index`` of a Scouts item (a subcommittee has one)."""

    if item in SUBCOMMITTEES_BY_ID:
        return SUBCOMMITTEES_BY_ID[item].option
    if item in EVENTS_BY_ID:
        event = EVENTS_BY_ID[item]
        if event.secret_choices:
            return event.secret_choices[index].option
        return event.options[index]
    if item in SALES_BY_ID:
        return SALES_BY_ID[item].options[index]
    if item in AUCTIONS_BY_ID:
        return ScoutsOption(rewards=AUCTIONS_BY_ID[item].rank_rewards[index])
    raise ValueError(f"unknown Scouts item: {item!r}")


def option_steps(option: ScoutsOption) -> tuple[ScoutsStep, ...]:
    """Costs in printed order, then rewards (costs are paid in full first)."""

    return (*option.costs, *option.rewards)


def option_is_affordable(state: GameState, player: int, option: ScoutsOption) -> bool:
    """Whether ``player`` can pay every cost of ``option`` now."""

    owner = state.players[player]
    solari = spice = water = 0
    for cost in option.costs:
        match cost:
            case PayResources():
                solari += cost.solari
                spice += cost.spice
                water += cost.water
            case DiscardFromHand(count=count):
                if len(owner.hand) < count:
                    return False
            case RecallSpy(count=count):
                if len(owner.spy_post_ids) < count:
                    return False
            case TrashIntrigueCard():
                if not owner.intrigue_cards:
                    return False
            case TrashPersonalCard(hand_only=hand_only):
                zones = (
                    owner.hand
                    if hand_only
                    else (*owner.hand, *owner.discard_pile, *owner.in_play)
                )
                if not zones:
                    return False
            case LoseGarrisonTroops(count=count):
                if owner.troops_garrison < count:
                    return False
            case PaySpecimens(count=count):
                if owner.specimens < count:
                    return False
            case _:
                # Influence losses are the only other costs; slice 5 adds them.
                raise NotImplementedError(f"Scouts cost not supported yet: {cost!r}")
    resources = owner.resources
    return (
        resources.solari >= solari
        and resources.spice >= spice
        and (resources.water >= water)
    )


# --- The effect frame --------------------------------------------------------------


def push_scouts_effect(
    state: GameState,
    player: int,
    item: str,
    option: int,
    *,
    source: str,
    exclude_space: str = "",
    turn_closed: bool = False,
) -> GameState:
    """Open the frame that resolves one seat's line of a Scouts item.

    ``exclude_space`` is the space of the Agent that just took the High
    Council seat (Contingencies recalls another, OQ-075). ``turn_closed``
    marks a line whose seat's turn has already closed, so nothing it grants
    joins a turn that opened since (OQ-044 (d)).
    """

    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_EFFECT,
        frame_id=f"{source}:effect",
        decision=PlayerDecision(
            owner=player, prompt="Resolve the Arrakeen Scouts effect"
        ),
        context=(
            ("exclude_space", exclude_space),
            ("item", item),
            ("option", option),
            ("picked", 0),
            ("player", player),
            ("source", source),
            ("step", 0),
            ("turn_closed", turn_closed),
        ),
    )
    return state.push_decision(frame)


def _effect_frame(state: GameState) -> DecisionFrame | None:
    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    return frame if frame.kind == FrameKind.SCOUTS_EFFECT else None


def _cursor(frame: DecisionFrame) -> tuple[int, str, ScoutsOption, int, int]:
    context = dict(frame.context)
    player = context_int(context, "player", owner=_EFFECT_FRAME)
    item = context_str(context, "item", owner=_EFFECT_FRAME)
    option = scouts_option(item, context_int(context, "option", owner=_EFFECT_FRAME))
    step = context_int(context, "step", owner=_EFFECT_FRAME)
    picked = context_int(context, "picked", owner=_EFFECT_FRAME)
    return player, item, option, step, picked


def _current_step(state: GameState, frame: DecisionFrame) -> ScoutsStep | None:
    player, _, option, step, _ = _cursor(frame)
    steps = option_steps(option)
    if step >= len(steps):
        return None
    current = steps[step]
    return current if _is_choice(state, player, frame, current) else None


def _is_choice(
    state: GameState, player: int, frame: DecisionFrame, step: ScoutsStep
) -> bool:
    """Whether ``step`` waits on this frame's own choice actions now."""

    owner = state.players[player]
    match step:
        case DiscardFromHand():
            return bool(owner.hand)
        case RecallSpy():
            return bool(owner.spy_post_ids)
        case TrashIntrigueCard():
            return bool(owner.intrigue_cards)
        case TrashPersonalCard(mandatory=True, hand_only=hand_only):
            return bool(
                owner.hand
                if hand_only
                else (*owner.hand, *owner.discard_pile, *owner.in_play)
            )
        case GainInfluence() if step.requires_choice:
            return len(_gainable_factions(owner, step)) > 1
        case GainLowestInfluence():
            return len(_lowest_factions(owner)) > 1
        case RecallOtherAgent():
            return len(_recallable_spaces(owner, frame)) > 0
    return False


def scouts_effect_can_advance(state: GameState) -> bool:
    """Whether the top Scouts effect frame waits on an automatic step."""

    frame = _effect_frame(state)
    return frame is not None and _current_step(state, frame) is None


def _moved(state: GameState, frame: DecisionFrame, *, step: int) -> GameState:
    """Replace the top frame's cursor (fresh step: no pick made yet)."""

    context = dict(frame.context)
    context["step"] = step
    context["picked"] = 0
    moved = replace(frame, context=tuple(sorted(context.items())))
    return replace(state, decision_stack=(*state.decision_stack[:-1], moved))


def advance_scouts_effect(state: GameState) -> RuleResult:
    """Run the top frame's automatic step, or close the frame when done."""

    frame = _effect_frame(state)
    if frame is None:
        raise ValueError("there is no Scouts effect frame")
    player, item, option, step, _ = _cursor(frame)
    context = dict(frame.context)
    source = context_str(context, "source", owner=_EFFECT_FRAME)
    steps = option_steps(option)
    if step >= len(steps):
        return RuleResult(
            state=state.pop_decision(),
            events=(
                GameEvent(
                    event_id=f"{source}:resolved",
                    kind="scouts_effect_resolved",
                    payload=(("item_id", item), ("player", player)),
                ),
            ),
        )
    moved = _moved(state, frame, step=step + 1)
    return _apply_automatic(
        moved,
        player,
        steps[step],
        source=f"{source}:{step}",
        turn_closed=context.get("turn_closed") is True,
    )


def _credit_turn(
    state: GameState,
    player: int,
    *,
    turn_closed: bool,
    troops: int = 0,
    spice_spent: int = 0,
) -> GameState:
    """Count recruits and spice spent toward ``player``'s own open turn only."""

    if turn_closed or turn_owner_of(state) != player or not (troops or spice_spent):
        return state
    return update_turn_recruits(state, troops_recruited=troops, spice_spent=spice_spent)


def _apply_automatic(
    state: GameState,
    player: int,
    step: ScoutsStep,
    *,
    source: str,
    turn_closed: bool,
) -> RuleResult:
    owner = state.players[player]
    match step:
        case PayResources(solari=solari, spice=spice, water=water):
            paid = replace(
                owner,
                resources=replace(
                    owner.resources,
                    solari=owner.resources.solari - solari,
                    spice=owner.resources.spice - spice,
                    water=owner.resources.water - water,
                ),
            )
            next_state = replace(state, players=replace_player(state.players, paid))
            next_state = _credit_turn(
                next_state, player, turn_closed=turn_closed, spice_spent=spice
            )
            return RuleResult(
                state=next_state,
                events=(
                    GameEvent(
                        event_id=f"{source}:paid",
                        kind="scouts_cost_paid",
                        payload=(
                            ("player", player),
                            ("solari", solari),
                            ("spice", spice),
                            ("water", water),
                        ),
                    ),
                ),
            )
        case LoseGarrisonTroops(count=count):
            lost = min(count, owner.troops_garrison)
            next_owner = replace(
                owner,
                troops_garrison=owner.troops_garrison - lost,
                troops_supply=owner.troops_supply + lost,
            )
            return _owner_event(
                state,
                next_owner,
                GameEvent(
                    event_id=f"{source}:scouts_troops_lost",
                    kind="scouts_troops_lost",
                    payload=(("count", lost), ("player", player)),
                ),
            )
        case PaySpecimens(count=count):
            paid_count = min(count, owner.specimens)
            next_owner = replace(
                owner,
                specimens=owner.specimens - paid_count,
                troops_supply=owner.troops_supply + paid_count,
            )
            return _owner_event(
                state,
                next_owner,
                GameEvent(
                    event_id=f"{source}:scouts_specimens_paid",
                    kind="scouts_specimens_paid",
                    payload=(("count", paid_count), ("player", player)),
                ),
            )
        case RecruitToConflict(count=count):
            deployed = min(count, owner.troops_supply)
            next_owner = replace(
                owner,
                troops_supply=owner.troops_supply - deployed,
                troops_conflict=owner.troops_conflict + deployed,
            )
            return _owner_event(
                state,
                next_owner,
                GameEvent(
                    event_id=f"{source}:scouts_troops_to_conflict",
                    kind="scouts_troops_to_conflict",
                    payload=(("count", deployed), ("player", player)),
                ),
            )
        case PlaceSpy():
            return RuleResult(
                state=spy_placement_frame(
                    state,
                    player,
                    _ALL_POSTS,
                    source=source,
                    turn_closed=turn_closed,
                )
            )
        case TrashPersonalCard():
            # The trash icon: optional [Main p. 20].
            return RuleResult(
                state=state.push_decision(
                    optional_trash_frame(player, source, turn_closed=turn_closed)
                )
            )
        case AcquireReserveCardToHand(card_id=card_id):
            if dict(state.reserve_stacks).get(card_id, 0) < 1:
                return RuleResult(state=state)
            acquired = acquire_reserve_for_intrigue(
                state,
                player,
                card_id,
                to_hand=True,
                source=source,
                credit_turn_recruits=not turn_closed,
            )
            return acquired.result
        case GainInfluence() if step.requires_choice:
            factions = _gainable_factions(owner, step)
            if not factions:
                return RuleResult(state=state)  # every track is at the top
            return gain_faction_influence(
                state, player, factions[0], step.times, event_prefix=source
            )
        case GainLowestInfluence():
            (faction,) = _lowest_factions(owner)
            return gain_faction_influence(
                state, player, faction, 1, event_prefix=source
            )
        case RecallOtherAgent():
            return RuleResult(state=state)  # no other Agent is out (OQ-075)
        case DiscardFromHand() | RecallSpy() | TrashIntrigueCard():
            # A choice with nothing left to choose (checked before paying a
            # cost; a delayed reward's may run dry): nothing happens.
            return RuleResult(state=state)
    if isinstance(step, _NOT_DSL_REWARDS):
        raise NotImplementedError(f"Scouts step not supported yet: {step!r}")
    outcome = apply_rewards(state, player, (cast(Reward, step),), source=source)
    next_state = _credit_turn(
        outcome.result.state,
        player,
        turn_closed=turn_closed,
        troops=outcome.troops_recruited,
    )
    return RuleResult(state=next_state, events=outcome.result.events)


def _owner_event(state: GameState, owner: PlayerState, event: GameEvent) -> RuleResult:
    return RuleResult(
        state=replace(state, players=replace_player(state.players, owner)),
        events=(event,),
    )


def _gainable_factions(owner: PlayerState, step: GainInfluence) -> tuple[Faction, ...]:
    allowed = step.factions if step.factions is not None else tuple(Faction)
    return tuple(
        faction
        for faction in allowed
        if influence_amount(owner.influence, faction) < MAX_INFLUENCE
    )


def _lowest_factions(owner: PlayerState) -> tuple[Faction, ...]:
    lowest = min(influence_amount(owner.influence, faction) for faction in Faction)
    return tuple(
        faction
        for faction in Faction
        if influence_amount(owner.influence, faction) == lowest
    )


def _recallable_spaces(owner: PlayerState, frame: DecisionFrame) -> tuple[str, ...]:
    excluded = context_str(dict(frame.context), "exclude_space", owner=_EFFECT_FRAME)
    locations = list(owner.agent_locations)
    if excluded in locations:
        locations.remove(excluded)  # only the one Agent that took the seat
    return tuple(dict.fromkeys(locations))


# --- Choices -------------------------------------------------------------------------


def legal_scouts_effect_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Offer the current choice step's options."""

    frame = owned_top_frame(state, FrameKind.SCOUTS_EFFECT, player)
    if frame is None:
        return ()
    step = _current_step(state, frame)
    owner = state.players[player]

    def offer(
        action_id: str, name: str, values: tuple[str, ...]
    ) -> tuple[DomainAction, ...]:
        return tuple(
            DomainAction(action_id=action_id, actor=player, arguments=((name, value),))
            for value in dict.fromkeys(values)
        )

    match step:
        case DiscardFromHand():
            return offer("scouts_discard", "card_id", owner.hand)
        case TrashPersonalCard(hand_only=hand_only):
            zones = (
                owner.hand
                if hand_only
                else (*owner.hand, *owner.discard_pile, *owner.in_play)
            )
            return offer("scouts_trash_card", "card_id", zones)
        case TrashIntrigueCard():
            return offer("scouts_trash_intrigue", "card_id", owner.intrigue_cards)
        case RecallSpy():
            return offer("scouts_recall_spy", "post_id", owner.spy_post_ids)
        case GainInfluence():
            factions = _gainable_factions(owner, step)
            return offer(
                "scouts_choose_faction", "faction", tuple(f.value for f in factions)
            )
        case GainLowestInfluence():
            factions = _lowest_factions(owner)
            return offer(
                "scouts_choose_faction", "faction", tuple(f.value for f in factions)
            )
        case RecallOtherAgent():
            return offer(
                "scouts_recall_agent", "space_id", _recallable_spaces(owner, frame)
            )
    return ()


def apply_scouts_effect_action(state: GameState, action: DomainAction) -> RuleResult:
    """Resolve one pick of the current choice step."""

    if action not in legal_scouts_effect_actions(state, action.actor):
        raise ValueError("action is not a legal Arrakeen Scouts choice")
    frame = state.decision_stack[-1]
    player, _, option, step, picked = _cursor(frame)
    context = dict(frame.context)
    source = f"{context_str(context, 'source', owner=_EFFECT_FRAME)}:{step}"
    turn_closed = context.get("turn_closed") is True
    current = option_steps(option)[step]
    value = str(dict(action.arguments)[action.arguments[0][0]])
    count = getattr(current, "count", 1)
    done = picked + 1 >= count or action.action_id in (
        "scouts_choose_faction",
        "scouts_recall_agent",
        "scouts_trash_card",
        "scouts_trash_intrigue",
    )
    if done:
        cursor_state = _moved(state, frame, step=step + 1)
    else:
        context["picked"] = picked + 1
        cursor_state = replace(
            state,
            decision_stack=(
                *state.decision_stack[:-1],
                replace(frame, context=tuple(sorted(context.items()))),
            ),
        )
    owner = cursor_state.players[player]
    pick_source = f"{source}:{picked}"
    match action.action_id:
        case "scouts_discard":
            return discard_personal_card_from_hand(
                cursor_state, player, value, source=pick_source
            )
        case "scouts_trash_card":
            return trash_personal_card(
                cursor_state, player, value, source=pick_source, turn_closed=turn_closed
            )
        case "scouts_trash_intrigue":
            next_owner = replace(
                owner,
                intrigue_cards=tuple(c for c in owner.intrigue_cards if c != value),
            )
            return RuleResult(
                state=replace(
                    cursor_state,
                    players=replace_player(cursor_state.players, next_owner),
                    intrigue_trash=(*cursor_state.intrigue_trash, value),
                ),
                events=(
                    GameEvent(
                        event_id=f"{pick_source}:intrigue_trashed",
                        kind="intrigue_card_trashed",
                        payload=(("card_id", value), ("player", player)),
                    ),
                ),
            )
        case "scouts_recall_spy":
            recalled = replace(
                owner,
                spies_supply=owner.spies_supply + 1,
                spies_recalled_turn=owner.spies_recalled_turn
                + (0 if turn_closed else 1),
                spy_post_ids=tuple(p for p in owner.spy_post_ids if p != value),
            )
            return RuleResult(
                state=replace(
                    cursor_state,
                    players=replace_player(cursor_state.players, recalled),
                ),
                events=(
                    GameEvent(
                        event_id=f"{pick_source}:recalled:{value}",
                        kind="spy_recalled",
                        payload=(("player", player), ("post_id", value)),
                    ),
                ),
            )
        case "scouts_choose_faction":
            times = current.times if isinstance(current, GainInfluence) else 1
            return gain_faction_influence(
                cursor_state, player, Faction(value), times, event_prefix=pick_source
            )
        case "scouts_recall_agent":
            locations = list(owner.agent_locations)
            locations.remove(value)
            recalled_agent = replace(
                owner,
                agents_available=owner.agents_available + 1,
                agent_locations=tuple(locations),
            )
            return RuleResult(
                state=replace(
                    cursor_state,
                    players=replace_player(cursor_state.players, recalled_agent),
                ),
                events=(
                    GameEvent(
                        event_id=f"{pick_source}:agent_recalled",
                        kind="agent_recalled",
                        payload=(("player", player), ("space_id", value)),
                    ),
                ),
            )
    raise RuntimeError(f"unknown Scouts choice: {action.action_id}")


# --- Subcommittees --------------------------------------------------------------------


def subcommittee_offer_is_queued(state: GameState) -> bool:
    """Whether a queued offer can open now (after chance and Conflict rewards)."""

    if not state.scouts_subcommittee_offers:
        return False
    frame = state.decision_stack[-1] if state.decision_stack else None
    if frame is None:
        return True
    if isinstance(frame.decision, ChanceDecision):
        return False
    return not str(frame.kind).startswith("combat_reward")


def joinable_subcommittees(state: GameState, player: int) -> tuple[str, ...]:
    """Unclaimed subcommittees of the display whose cost ``player`` can pay."""

    claimed = {subcommittee for subcommittee, _ in state.scouts_subcommittee_members}
    return tuple(
        subcommittee_id
        for subcommittee_id in state.scouts_subcommittees
        if subcommittee_id not in claimed
        and option_is_affordable(
            state, player, SUBCOMMITTEES_BY_ID[subcommittee_id].option
        )
    )


def begin_subcommittee_offer(state: GameState) -> RuleResult:
    """Open the oldest offer, or let it lapse when nothing can be joined."""

    (player, source, exclude_space, turn_closed), *rest = (
        state.scouts_subcommittee_offers
    )
    remaining = replace(state, scouts_subcommittee_offers=tuple(rest))
    if not joinable_subcommittees(remaining, player):
        return RuleResult(
            state=remaining,
            events=(
                GameEvent(
                    event_id=f"{source}:subcommittee_unavailable",
                    kind="scouts_subcommittee_unavailable",
                    payload=(("player", player),),
                ),
            ),
        )
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_SUBCOMMITTEE,
        frame_id=f"{source}:subcommittee",
        decision=PlayerDecision(owner=player, prompt="Join a subcommittee or decline"),
        context=(
            ("exclude_space", exclude_space),
            ("player", player),
            ("source", source),
            ("turn_closed", turn_closed),
        ),
    )
    return RuleResult(state=remaining.push_decision(frame))


def legal_subcommittee_actions(
    state: GameState, player: int
) -> tuple[DomainAction, ...]:
    """Join one joinable subcommittee, or decline (the chance is then gone)."""

    if owned_top_frame(state, FrameKind.SCOUTS_SUBCOMMITTEE, player) is None:
        return ()
    return (
        DomainAction(action_id="decline_subcommittee", actor=player),
        *(
            DomainAction(
                action_id="join_subcommittee",
                actor=player,
                arguments=(("subcommittee_id", subcommittee_id),),
            )
            for subcommittee_id in joinable_subcommittees(state, player)
        ),
    )


def apply_subcommittee_action(state: GameState, action: DomainAction) -> RuleResult:
    """Join (and open its line) or decline the subcommittee offer."""

    if action not in legal_subcommittee_actions(state, action.actor):
        raise ValueError("action is not a legal subcommittee choice")
    frame = state.decision_stack[-1]
    context = dict(frame.context)
    source = context_str(context, "source", owner=_OFFER_FRAME)
    popped = state.pop_decision()
    if action.action_id == "decline_subcommittee":
        return RuleResult(
            state=popped,
            events=(
                GameEvent(
                    event_id=f"{source}:subcommittee_declined",
                    kind="scouts_subcommittee_declined",
                    payload=(("player", action.actor),),
                ),
            ),
        )
    subcommittee_id = str(dict(action.arguments)["subcommittee_id"])
    joined = replace(
        popped,
        scouts_subcommittee_members=(
            *popped.scouts_subcommittee_members,
            (subcommittee_id, action.actor),
        ),
    )
    opened = push_scouts_effect(
        joined,
        action.actor,
        subcommittee_id,
        0,
        source=f"{source}:{subcommittee_id}",
        exclude_space=context_str(context, "exclude_space", owner=_OFFER_FRAME),
        turn_closed=context.get("turn_closed") is True,
    )
    return RuleResult(
        state=opened,
        events=(
            GameEvent(
                event_id=f"{source}:subcommittee_joined",
                kind="scouts_subcommittee_joined",
                payload=(
                    ("player", action.actor),
                    ("subcommittee_id", subcommittee_id),
                ),
            ),
        ),
    )
