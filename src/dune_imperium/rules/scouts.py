"""Arrakeen Scouts: the Scouts step between Round Start and the first turn.

``arrakeen_scouts`` option (``docs/rules/arrakeen-scouts.md``). Each round,
after the Conflict reveal, the Control defense and the draw, the step reveals
the round's items in the app's order and only then opens the First Player's
turn (OQ-072) [Scouts help] [Scouts schedule].

Nothing is drawn ahead. Each item is drawn by a chance frame in the round it
is revealed. Every draw of the app depends only on the draws before it (the
families already out, the previous mission's type, the mid auction's
family), never on the game, so drawing at the reveal gives the app's
distribution and keeps no hidden future in the state
(``docs/arrakeen-scouts-design.md`` 4.3).

``_advance_automatic`` drives the step. While ``scouts_opening`` holds and
the stack is empty, ``advance_scouts_step`` does one unit of work: the
current item's next task, the item's close, the round's next draw, or the
first turn. An item pushes its own frames; a frame another rule module owns
(a Spy placement, a Contract pick) pops itself, and the step resumes from the
cursor (``scouts_item`` and ``scouts_tasks``), so no frame needs to know
where to return. The step's frames never sit above a turn frame, so nothing
it grants belongs to anyone's turn.
"""

from dataclasses import dataclass, replace
from typing import Final

from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS_BY_ID,
    EVENTS_BY_ID,
    MISSIONS_BY_ID,
    SALES_BY_ID,
    AuctionSlot,
    AutomaticEffect,
    EventKind,
    ScoutsPool,
    auctions_for,
    events_for,
    missions_for,
    sales_for,
    scouts_pool,
    subcommittees_for,
)
from dune_imperium.content.uprising.board import Faction
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.decisions import ChanceDecision, DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.frames import (
    FrameKind,
    context_str,
    owned_top_frame,
    reset_turn_counters,
)
from dune_imperium.rules.influence import grant_chosen_four_bonus
from dune_imperium.rules.scouts_auctions import (
    apply_top_up,
    auction_tasks,
    clear_market,
    close_bids,
    close_market,
    deploy_mercenaries,
    offer_bid,
    offer_call,
    offer_retreat,
    offer_take,
    offer_top_up,
    reveal_market,
    run_auction_reward,
)
from dune_imperium.rules.scouts_effects import (
    apply_scouts_effect_action,
    highest_factions,
    offer_scouts_choice,
    push_scouts_effect,
)
from dune_imperium.rules.scouts_missions import (
    apply_mission_join,
    mission_tasks,
    offer_mission_join,
    place_mission_goods,
)
from dune_imperium.rules.scouts_secrets import (
    offer_secret_pick,
    reveal_due_secrets,
    run_secret_reward,
    secret_tasks,
    secrets_are_due,
)

# Four players reveal five subcommittees: one of each tier, then the rest
# from the whole remaining pool [Scouts schedule].
SUBCOMMITTEE_COUNT: Final = 5
_TIERS: Final = (0, 1, 2)
# The mission layouts: two missions in round 2 and one in round 3 at 70%,
# else one and two [Scouts schedule]. Ten equal outcomes keep the odds.
_MISSION_LAYOUTS: Final = (((2, 2, 3), 7), ((2, 3, 3), 3))
_MISSION_COUNT: Final = 3
_EVENT_ROUNDS: Final = (4, 5, 6, 7)
_MID_ROUNDS: Final = (5, 6)
_LATE_ROUNDS: Final = (8, 9)

_DRAW_FRAME: Final = "Scouts draw frame"
_FOUR_BONUS_FRAME: Final = "Friends Everywhere frame"


@dataclass(frozen=True, slots=True)
class _Draw:
    """One pending chance draw of the Scouts step."""

    step: str
    options: tuple[str, ...]
    count: int = 1


# --- Queries --------------------------------------------------------------------------


def state_pool(state: GameState) -> ScoutsPool:
    """Return the schedule pool the game's expansions select."""

    return scouts_pool(immortality=state.config.immortality)


def item_kind(item_id: str) -> str:
    """Return ``mission``, ``event``, ``auction`` or ``sale`` for an item id."""

    if item_id in MISSIONS_BY_ID:
        return "mission"
    if item_id in EVENTS_BY_ID:
        return "event"
    if item_id in AUCTIONS_BY_ID:
        return "auction"
    if item_id in SALES_BY_ID:
        return "sale"
    raise ValueError(f"unknown Scouts item: {item_id!r}")


def revealed_in(state: GameState, round_number: int) -> tuple[str, ...]:
    """Return the items revealed in ``round_number``, in reveal order."""

    return tuple(item for rnd, item in state.scouts_revealed if rnd == round_number)


def revealed_of_kind(state: GameState, kind: str) -> tuple[str, ...]:
    """Return every revealed item of one kind, in reveal order."""

    return tuple(item for _, item in state.scouts_revealed if item_kind(item) == kind)


def turn_order(state: GameState) -> tuple[int, ...]:
    """Return every seat from the First Player clockwise (OQ-071)."""

    if state.first_player is None:
        raise ValueError("the Scouts step requires a First Player")
    return tuple(
        (state.first_player + offset) % state.config.players
        for offset in range(state.config.players)
    )


# --- The step driver ------------------------------------------------------------------


def scouts_step_is_pending(state: GameState) -> bool:
    """Whether the Scouts step must do its next unit of work now."""

    return (
        state.config.arrakeen_scouts
        and state.scouts_opening
        and state.phase is GamePhase.PLAYER_TURNS
        and not state.decision_stack
    )


def advance_scouts_step(state: GameState) -> RuleResult:
    """Run one unit of the step: a task, an item's close, a draw or the turn."""

    if not scouts_step_is_pending(state):
        raise ValueError("the Scouts step has nothing pending")
    if state.scouts_tasks:
        task, *rest = state.scouts_tasks
        return _run_task(replace(state, scouts_tasks=tuple(rest)), task)
    if state.scouts_item:
        return RuleResult(state=replace(state, scouts_item=""))
    if secrets_are_due(state):
        # The picks due this round come first, before its own item (OQ-085).
        return reveal_due_secrets(state, turn_order(state))
    draw = _next_draw(state)
    if draw is not None:
        return RuleResult(state=state.push_decision(_draw_frame(state, draw)))
    return _open_first_turn(state)


def _open_first_turn(state: GameState) -> RuleResult:
    """End the step and open the First Player's turn.

    The round's first turn opens without ``reset_turn_counters`` when there
    is no Scouts step (``phases.begin_round`` resets part of it); here the
    step may have moved any per-turn counter (a Spy recall, a completed
    Contract), so the First Player's are all reset as their turn opens.
    """

    from dune_imperium.rules.phases import turn_frame

    if state.first_player is None:
        raise ValueError("the first turn requires a First Player")
    players = reset_turn_counters(state.players, state.first_player)
    opened = replace(state, players=players, scouts_opening=False)
    return RuleResult(
        state=opened.push_decision(turn_frame(state.round_number, state.first_player))
    )


# --- Draws ----------------------------------------------------------------------------


def _next_draw(state: GameState) -> _Draw | None:
    round_number = state.round_number
    if round_number == 1:
        return _subcommittee_draw(state)
    if round_number in (2, 3):
        return _mission_draw(state)
    if round_number in _EVENT_ROUNDS:
        return _event_round_draw(state)
    if round_number in _LATE_ROUNDS:
        return _late_round_draw(state)
    return None


def _subcommittee_draw(state: GameState) -> _Draw | None:
    drawn = state.scouts_subcommittees
    if len(drawn) >= SUBCOMMITTEE_COUNT:
        return None
    pool = subcommittees_for(state_pool(state), choam=state.config.choam_module)
    if len(drawn) < len(_TIERS):
        tier = _TIERS[len(drawn)]
        options = tuple(entry.subcommittee_id for entry in pool if entry.tier == tier)
        return _Draw(step=f"subcommittee_tier_{tier}", options=options)
    rest = tuple(
        entry.subcommittee_id for entry in pool if entry.subcommittee_id not in drawn
    )
    return _Draw(
        step="subcommittee_rest",
        options=rest,
        count=SUBCOMMITTEE_COUNT - len(drawn),
    )


def _mission_draw(state: GameState) -> _Draw | None:
    if not state.scouts_mission_rounds:
        options = tuple(
            f"layout:{''.join(map(str, layout))}#{ticket}"
            for layout, tickets in _MISSION_LAYOUTS
            for ticket in range(tickets)
        )
        return _Draw(step="mission_layout", options=options)
    revealed = revealed_of_kind(state, "mission")
    slot = len(revealed)
    if slot >= _MISSION_COUNT:
        return None
    if state.scouts_mission_rounds[slot] != state.round_number:
        return None
    removed = {MISSIONS_BY_ID[mission_id].app.family for mission_id in revealed}
    last_type = (
        MISSIONS_BY_ID[revealed[-1]].mission_type
        if slot == _MISSION_COUNT - 1
        else None
    )
    round_number = state.round_number
    options = tuple(
        entry.mission_id
        for entry in missions_for(state_pool(state), choam=state.config.choam_module)
        if entry.app.family not in removed
        and entry.rounds[0] <= round_number <= entry.rounds[1]
        and entry.mission_type != last_type
    )
    if not options:
        raise RuntimeError("no mission can fill the schedule slot")
    return _Draw(step="mission", options=options)


def _event_round_draw(state: GameState) -> _Draw | None:
    round_number = state.round_number
    here = revealed_in(state, round_number)
    if round_number == _MID_ROUNDS[0] and not state.scouts_mid_auction_round:
        return _Draw(
            step="mid_auction_round",
            options=tuple(f"round:{value}" for value in _MID_ROUNDS),
        )
    if round_number == state.scouts_mid_auction_round and not any(
        item_kind(item) == "auction" for item in here
    ):
        return _auction_draw(state, slot=AuctionSlot.MID)
    if not any(item_kind(item) == "event" for item in here):
        return _event_draw(state)
    return None


def _event_draw(state: GameState) -> _Draw:
    round_number = state.round_number
    removed = {
        EVENTS_BY_ID[event_id].app.family
        for event_id in revealed_of_kind(state, "event")
    }
    options = tuple(
        f"{entry.event_id}#{ticket}"
        for entry in events_for(state_pool(state), choam=state.config.choam_module)
        if entry.app.family not in removed
        and entry.rounds[0] <= round_number <= entry.rounds[1]
        for ticket in range(entry.weight_tickets)
    )
    if not options:
        raise RuntimeError("no event can fill the round")
    return _Draw(step="event", options=options)


def _late_round_draw(state: GameState) -> _Draw | None:
    round_number = state.round_number
    here = revealed_in(state, round_number)
    if round_number == _LATE_ROUNDS[0] and not state.scouts_late_auction_round:
        return _Draw(
            step="late_auction_round",
            options=tuple(f"round:{value}" for value in _LATE_ROUNDS),
        )
    if round_number == state.scouts_late_auction_round:
        if any(item_kind(item) == "auction" for item in here):
            return None
        return _auction_draw(state, slot=AuctionSlot.LATE)
    if any(item_kind(item) == "sale" for item in here):
        return None
    options = tuple(entry.sale_id for entry in sales_for(state_pool(state)))
    return _Draw(step="sale", options=options)


def _auction_draw(state: GameState, *, slot: AuctionSlot) -> _Draw:
    round_number = state.round_number
    taken = {
        AUCTIONS_BY_ID[auction_id].app.family
        for auction_id in revealed_of_kind(state, "auction")
    }
    options = tuple(
        entry.auction_id
        for entry in auctions_for(state_pool(state), choam=state.config.choam_module)
        if entry.slot in (slot, AuctionSlot.EITHER)
        and entry.rounds[0] <= round_number <= entry.rounds[1]
        and entry.app.family not in taken
    )
    if not options:
        raise RuntimeError("no auction can fill the schedule slot")
    return _Draw(step=f"{slot.value}_auction", options=options)


def _draw_frame(state: GameState, draw: _Draw) -> DecisionFrame:
    serial = len(state.scouts_revealed)
    decision_id = f"round:{state.round_number}:scouts:{draw.step}:{serial}"
    return DecisionFrame(
        kind=FrameKind.SCOUTS_DRAW,
        frame_id=f"{decision_id}:draw",
        decision=ChanceDecision(
            decision_id=decision_id,
            prompt="Draw the Arrakeen Scouts schedule",
            options=draw.options,
            count=draw.count,
        ),
        context=(("step", draw.step),),
    )


def scouts_draw_is_pending(state: GameState) -> bool:
    """Whether the top frame is a Scouts chance draw."""

    return bool(state.decision_stack) and (
        state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW
    )


def apply_scouts_draw(state: GameState, outcome: ChanceOutcome) -> RuleResult:
    """Record one Scouts draw and reveal what it drew."""

    if not scouts_draw_is_pending(state):
        raise ValueError("there is no pending Scouts draw")
    frame = state.decision_stack[-1]
    step = context_str(dict(frame.context), "step", owner=_DRAW_FRAME)
    popped = state.pop_decision()
    round_number = state.round_number
    if step.startswith("subcommittee_"):
        drawn = (*popped.scouts_subcommittees, *outcome.values)
        next_state = replace(popped, scouts_subcommittees=drawn)
        if len(drawn) < SUBCOMMITTEE_COUNT:
            return RuleResult(state=next_state)
        return RuleResult(
            state=next_state,
            events=(
                GameEvent(
                    event_id=f"round:{round_number}:scouts:subcommittees",
                    kind="scouts_subcommittees_revealed",
                    payload=(
                        ("round", round_number),
                        ("subcommittee_ids", ",".join(drawn)),
                    ),
                ),
            ),
        )
    if step == "contract_shuffle":
        return _deal_cleared_contracts(popped, outcome)
    (value,) = outcome.values
    if step == "mission_layout":
        layout = tuple(int(digit) for digit in value.split(":")[1].split("#")[0])
        return RuleResult(
            state=replace(popped, scouts_mission_rounds=layout),
            events=(
                GameEvent(
                    event_id=f"round:{round_number}:scouts:mission_layout",
                    kind="scouts_mission_layout",
                    payload=(("rounds", ",".join(map(str, layout))),),
                ),
            ),
        )
    if step in ("mid_auction_round", "late_auction_round"):
        auction_round = int(value.split(":")[1])
        slot = step.removesuffix("_auction_round")
        recorded = (
            replace(popped, scouts_mid_auction_round=auction_round)
            if slot == "mid"
            else replace(popped, scouts_late_auction_round=auction_round)
        )
        return RuleResult(
            state=recorded,
            events=(
                GameEvent(
                    event_id=f"round:{round_number}:scouts:{slot}_auction_round",
                    kind="scouts_auction_round",
                    payload=(("round", auction_round), ("slot", slot)),
                ),
            ),
        )
    return _reveal(popped, value.split("#")[0])


def _reveal(state: GameState, item_id: str) -> RuleResult:
    """Put a drawn item on the table and queue its tasks."""

    round_number = state.round_number
    kind = item_kind(item_id)
    revealed = replace(
        state,
        scouts_revealed=(*state.scouts_revealed, (round_number, item_id)),
        scouts_item=item_id,
        scouts_tasks=_item_tasks(state, item_id),
    )
    return RuleResult(
        state=revealed,
        events=(
            GameEvent(
                event_id=f"round:{round_number}:scouts:{kind}:{item_id}",
                kind="scouts_item_revealed",
                payload=(
                    ("item_id", item_id),
                    ("kind", kind),
                    ("round", round_number),
                ),
            ),
        ),
    )


def _item_tasks(state: GameState, item_id: str) -> tuple[str, ...]:
    order = turn_order(state)
    event = EVENTS_BY_ID.get(item_id)
    if item_id in SALES_BY_ID or (event is not None and event.kind is EventKind.CHOICE):
        # Each seat in turn order picks a line (OQ-071).
        return tuple(f"offer:{seat}" for seat in order)
    if event is not None and event.kind is EventKind.SHARED:
        if state.shield_wall_present:
            return ("moot",)  # Rebuild Infrastructure: nothing to rebuild
        return tuple(f"rebuild:{seat}|-1" for seat in order)
    if event is not None and event.automatic is AutomaticEffect.POLITICAL_EQUILIBRIUM:
        return tuple(f"equilibrium:{seat}" for seat in order)
    if item_id in MISSIONS_BY_ID:
        return mission_tasks(state, item_id, order)
    if item_id in AUCTIONS_BY_ID:
        return auction_tasks(item_id, order)
    if event is not None and event.kind is EventKind.SECRET:
        return secret_tasks(order)
    if event is not None:
        if event.kind is EventKind.ROUND_MODIFIER:
            return ("modifier",)
        if event.automatic is AutomaticEffect.MATING_SEASON:
            return ("mating_season",)
        if event.automatic is AutomaticEffect.CLEAR_THE_MARKET:
            return ("clear_row",)
        if event.automatic is AutomaticEffect.CLEAR_THE_MARKET_CONTRACTS:
            return ("clear_row", "clear_contracts")
    return ("unimplemented",)


# --- Tasks ----------------------------------------------------------------------------


def _run_task(state: GameState, task: str) -> RuleResult:
    item = state.scouts_item
    source = f"round:{state.round_number}:scouts:{item}"
    if task.startswith("offer:"):
        seat = int(task.removeprefix("offer:"))
        return offer_scouts_choice(state, seat, item, source=f"{source}:{seat}")
    if task.startswith("rebuild:"):
        rebuild_seat, volunteer = task.removeprefix("rebuild:").split("|")
        return offer_scouts_choice(
            state,
            int(rebuild_seat),
            item,
            source=f"{source}:{rebuild_seat}",
            volunteer=int(volunteer),
        )
    if task.startswith("equilibrium:"):
        seat = int(task.removeprefix("equilibrium:"))
        if not highest_factions(state.players[seat]):
            return RuleResult(state=state)
        return RuleResult(
            state=push_scouts_effect(state, seat, item, 0, source=f"{source}:{seat}")
        )
    if task.startswith("secret:"):
        secret_seat = int(task.removeprefix("secret:"))
        return offer_secret_pick(
            state, secret_seat, item, source=f"{source}:{secret_seat}"
        )
    if task.startswith("secret_reward:"):
        return run_secret_reward(state, task)
    if task.startswith("bid:"):
        bid_seat = int(task.removeprefix("bid:"))
        return offer_bid(state, bid_seat, item, source=f"{source}:{bid_seat}")
    if task == "bids_close":
        return close_bids(state, item, turn_order(state))
    if task.startswith("auction_reward:"):
        return run_auction_reward(state, task)
    if task.startswith("top_up:"):
        return offer_top_up(state, task)
    if task.startswith("mercenaries:"):
        return deploy_mercenaries(state, task)
    if task.startswith("retreat:"):
        return offer_retreat(state, task)
    if task == "market":
        return reveal_market(state)
    if task.startswith("call:"):
        call_seat = int(task.removeprefix("call:"))
        return offer_call(state, call_seat, source=f"{source}:{call_seat}")
    if task == "market_close":
        return close_market(state)
    if task.startswith("take:"):
        return offer_take(state, task)
    if task == "market_clear":
        return clear_market(state)
    if task == "goods":
        return place_mission_goods(state, item, source=source)
    if task.startswith("join:"):
        join_seat = int(task.removeprefix("join:"))
        return offer_mission_join(
            state, join_seat, item, source=f"{source}:{join_seat}"
        )
    if task == "moot":
        return RuleResult(
            state=state,
            events=(
                GameEvent(
                    event_id=f"{source}:moot",
                    kind="scouts_item_moot",
                    payload=(("item_id", item),),
                ),
            ),
        )
    if task == "modifier":
        return _set_round_modifier(state)
    if task == "mating_season":
        return _mating_season(state)
    if task == "clear_row":
        return _clear_row(state)
    if task == "clear_contracts":
        return _clear_contracts(state)
    if task == "unimplemented":
        return RuleResult(
            state=state,
            events=(
                GameEvent(
                    event_id=f"round:{state.round_number}:scouts:{state.scouts_item}:pending",
                    kind="scouts_item_unimplemented",
                    payload=(("item_id", state.scouts_item),),
                ),
            ),
        )
    raise RuntimeError(f"unknown Scouts task: {task!r}")


def _set_round_modifier(state: GameState) -> RuleResult:
    event = EVENTS_BY_ID[state.scouts_item]
    if event.modifier is None:
        raise RuntimeError("a round-modifier event names its modifier")
    return RuleResult(
        state=replace(state, scouts_round_modifier=event.modifier.value),
        events=(
            GameEvent(
                event_id=f"round:{state.round_number}:scouts:modifier",
                kind="scouts_round_modifier",
                payload=(
                    ("event_id", event.event_id),
                    ("modifier", event.modifier.value),
                ),
            ),
        ),
    )


def _mating_season(state: GameState) -> RuleResult:
    """One more spice on each Maker space, Tuek's Sietch included (OQ-082)."""

    maker_bonus_spice = tuple(
        (space_id, amount + 1) for space_id, amount in state.maker_bonus_spice
    )
    return RuleResult(
        state=replace(state, maker_bonus_spice=maker_bonus_spice),
        events=(
            GameEvent(
                event_id=f"round:{state.round_number}:scouts:mating_season",
                kind="scouts_maker_spice_added",
                payload=(
                    ("amount", 1),
                    ("space_ids", ",".join(space for space, _ in maker_bonus_spice)),
                ),
            ),
        ),
    )


def _clear_row(state: GameState) -> RuleResult:
    """Remove the Imperium Row and deal a new one from the deck.

    The removed cards leave the game, as Family Atomics' do (OQ-083,
    OQ-051); a short deck deals what it has.
    """

    removed = state.imperium_row
    dealt = state.imperium_deck[:5]
    return RuleResult(
        state=replace(
            state,
            imperium_removed=(*state.imperium_removed, *removed),
            imperium_row=dealt,
            imperium_deck=state.imperium_deck[5:],
        ),
        events=(
            GameEvent(
                event_id=f"round:{state.round_number}:scouts:clear_row",
                kind="scouts_row_cleared",
                payload=(("dealt", ",".join(dealt)), ("removed", ",".join(removed))),
            ),
        ),
    )


def _clear_contracts(state: GameState) -> RuleResult:
    """Deal new face-up Contracts, then shuffle the old ones into the bank.

    [Scouts event: Clear the Market] (CHOAM): the old pair goes into the
    face-down supply after the new pair is dealt from it, so the shuffle is
    one chance frame over the rest of the bank and the old pair. The old
    pair always goes; a short bank deals what it has and leaves the other
    slots empty (OQ-083).
    """

    old = state.face_up_contract_ids
    if not old:
        return RuleResult(state=state)
    dealt_count = min(len(old), len(state.contract_bank))
    pool = (*state.contract_bank[dealt_count:], *old)
    draw = _Draw(step="contract_shuffle", options=pool, count=len(pool))
    return RuleResult(state=state.push_decision(_draw_frame(state, draw)))


def _deal_cleared_contracts(state: GameState, outcome: ChanceOutcome) -> RuleResult:
    """Deal the new face-up Contracts; ``outcome`` is the shuffled bank.

    A short bank deals fewer than it removes, possibly none (OQ-083).
    """

    removed = state.face_up_contract_ids
    dealt = state.contract_bank[: min(len(removed), len(state.contract_bank))]
    return RuleResult(
        state=replace(state, face_up_contract_ids=dealt, contract_bank=outcome.values),
        events=(
            GameEvent(
                event_id=f"round:{state.round_number}:scouts:clear_contracts",
                kind="scouts_contracts_cleared",
                # Joined: the old pair is back in the hidden bank, but its
                # identities were public while face up (as Family Atomics'
                # removed Row).
                payload=(("dealt", ",".join(dealt)), ("removed", ",".join(removed))),
            ),
        ),
    )


# --- Friends Everywhere ------------------------------------------------------------


def four_bonus_choice_is_queued(state: GameState) -> bool:
    """Whether a Friends Everywhere choice can open now.

    Like the Emperor track's Spy (``spy_moves.track_spy_is_queued``): after
    any pending chance frame and after a Conflict's own reward choices.
    """

    if not state.scouts_four_bonus_choices:
        return False
    frame = state.decision_stack[-1] if state.decision_stack else None
    if frame is None:
        return True
    if isinstance(frame.decision, ChanceDecision):
        return False
    return not str(frame.kind).startswith("combat_reward")


def begin_four_bonus_choice(state: GameState) -> RuleResult:
    """Open the oldest queued Friends Everywhere choice."""

    player, reached, source = state.scouts_four_bonus_choices[0]
    remaining = replace(
        state, scouts_four_bonus_choices=state.scouts_four_bonus_choices[1:]
    )
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_FOUR_BONUS,
        frame_id=f"{source}:four_bonus",
        decision=PlayerDecision(
            owner=player, prompt="Choose which Influence 4 bonus to take"
        ),
        context=(("reached", reached), ("source", source)),
    )
    return RuleResult(state=remaining.push_decision(frame))


def legal_four_bonus_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Offer every Faction's Influence 4 bonus (the reached one included)."""

    if owned_top_frame(state, FrameKind.SCOUTS_FOUR_BONUS, player) is None:
        return ()
    return tuple(
        DomainAction(
            action_id="choose_four_bonus",
            actor=player,
            arguments=(("faction", faction.value),),
        )
        for faction in Faction
    )


def apply_four_bonus_choice(state: GameState, action: DomainAction) -> RuleResult:
    """Earn the chosen Faction's Influence 4 bonus."""

    if action not in legal_four_bonus_actions(state, action.actor):
        raise ValueError("action is not a legal Friends Everywhere choice")
    context = dict(state.decision_stack[-1].context)
    reached = Faction(context_str(context, "reached", owner=_FOUR_BONUS_FRAME))
    source = context_str(context, "source", owner=_FOUR_BONUS_FRAME)
    chosen = Faction(str(dict(action.arguments)["faction"]))
    return grant_chosen_four_bonus(
        state.pop_decision(), action.actor, reached, chosen, source=source
    )


# --- Specimen top-ups ------------------------------------------------------------


def apply_scouts_return_specimens(state: GameState, action: DomainAction) -> RuleResult:
    """Return specimens before a Scouts recruit, mission or Mercenaries
    deployment: each frame that offers it resolves it."""

    kind = state.decision_stack[-1].kind if state.decision_stack else None
    if kind == FrameKind.SCOUTS_EFFECT:
        return apply_scouts_effect_action(state, action)
    if kind == FrameKind.SCOUTS_MISSION:
        return apply_mission_join(state, action)
    if kind == FrameKind.SCOUTS_TOP_UP:
        return apply_top_up(state, action)
    raise ValueError("no Scouts frame offers a specimen return")
