"""Arrakeen Scouts: auctions (docs/rules/arrakeen-scouts.md 8).

Sealed auctions (To The Highest Bidder, Spies for Hire, CHOAM Negotiations,
Competitive Study, Mercenaries): each seat in turn order picks a bid with
``scouts_bid(count)``, as often as it likes, and confirms it with
``confirm_scouts_bid`` (OQ-073). The range is 0 to the lower of the seat's
own currency and the cap, so the offered counts say nothing of the other
bids. A bid is its seat's alone (``core.observation.secret_bid_id`` in
``known_card_seats``) until the last seat confirms; then every bid is
revealed at once and ranked as the app does [Scouts schedule]:

- competition ranking from the highest bid (equal bids share a rank);
- a seat wins when its rank is within the auction's places and it bid more
  than 0, so a tie for first leaves no second place and a tie for second
  gives every tied seat the second-place reward;
- only winners pay, except in Mercenaries, where every seat pays its spice
  and sends one supply troop per spice to the Conflict; the seats with the
  lowest bid may pull some or all of those troops back to their garrison
  (OQ-074).

Winners' rewards resolve from the First Player on (OQ-073).

Critical Moment is open: the Imperium deck's top two (late: three) cards are
revealed (``GameState.scouts_market_cards``), each seat from the First
Player calls once an amount of spice nobody has called yet, or passes
(``scouts_call(count)``, 0 = pass). The highest caller pays and takes one
of the cards into hand; in the late auction the second highest may buy one
of the rest the same way. What is left is removed from the game (OQ-083,
OQ-087).
"""

from dataclasses import replace
from typing import Final

from dune_imperium.content.arrakeen_scouts import AUCTIONS_BY_ID, AuctionKind
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import (
    acquire_imperium_for_intrigue,
    acquisition_spy_frame,
)
from dune_imperium.rules.contracts import begin_contract_gain
from dune_imperium.rules.frames import (
    FrameKind,
    context_int,
    context_str,
    owned_top_frame,
    replace_player,
)
from dune_imperium.rules.scouts_effects import push_scouts_effect

_BID_FRAME: Final = "Scouts bid frame"
_CALL_FRAME: Final = "Scouts call frame"
_TAKE_FRAME: Final = "Scouts market frame"
_RETREAT_FRAME: Final = "Mercenaries retreat frame"


def auction_tasks(auction_id: str, order: tuple[int, ...]) -> tuple[str, ...]:
    """Every seat bids (or calls) in turn order, then the auction closes."""

    if AUCTIONS_BY_ID[auction_id].kind is AuctionKind.OPEN_CARDS:
        return ("market", *(f"call:{seat}" for seat in order), "market_close")
    return (*(f"bid:{seat}" for seat in order), "bids_close")


def _currency(state: GameState, player: int, auction_id: str) -> int:
    resources = state.players[player].resources
    return int(getattr(resources, AUCTIONS_BY_ID[auction_id].currency))


def bid_cap(state: GameState, player: int) -> int:
    """The highest bid ``player`` may make in the running sealed auction."""

    auction = AUCTIONS_BY_ID[state.scouts_item]
    return min(_currency(state, player, auction.auction_id), auction.max_bid)


def rank_bids(bids: dict[int, int], places: int) -> dict[int, int]:
    """Each winning seat's place (0 first, 1 second) [Scouts schedule]."""

    winners: dict[int, int] = {}
    for seat, amount in bids.items():
        rank = 1 + sum(1 for other in bids.values() if other > amount)
        if rank <= places and amount > 0:
            winners[seat] = rank - 1
    return winners


# --- Sealed bids ----------------------------------------------------------------------


def offer_bid(
    state: GameState, player: int, auction_id: str, *, source: str
) -> RuleResult:
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_BID,
        frame_id=f"{source}:bid",
        decision=PlayerDecision(owner=player, prompt="Choose and confirm a sealed bid"),
        context=(("auction_id", auction_id), ("source", source)),
    )
    return RuleResult(state=state.push_decision(frame))


def legal_bid_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """Any count the seat's own currency covers, and the confirmation."""

    frame = owned_top_frame(state, FrameKind.SCOUTS_BID, player)
    if frame is None:
        return ()
    cap = bid_cap(state, player)
    return (
        DomainAction(action_id="confirm_scouts_bid", actor=player),
        *(
            DomainAction(
                action_id="scouts_bid", actor=player, arguments=(("count", count),)
            )
            for count in range(cap + 1)
        ),
    )


def apply_bid_action(state: GameState, action: DomainAction) -> RuleResult:
    """Pick a bid (no public trace), or confirm it (public: who, not what)."""

    if action not in legal_bid_actions(state, action.actor):
        raise ValueError("action is not a legal bid")
    context = dict(state.decision_stack[-1].context)
    auction_id = context_str(context, "auction_id", owner=_BID_FRAME)
    source = context_str(context, "source", owner=_BID_FRAME)
    player = action.actor
    current = next((row for row in state.scouts_bids if row[0] == player), None)
    others = tuple(row for row in state.scouts_bids if row[0] != player)
    if action.action_id == "scouts_bid":
        count = dict(action.arguments)["count"]
        assert isinstance(count, int)
        return RuleResult(
            state=replace(state, scouts_bids=(*others, (player, count, False)))
        )
    amount = 0 if current is None else current[1]
    return RuleResult(
        state=replace(
            state.pop_decision(), scouts_bids=(*others, (player, amount, True))
        ),
        events=(
            GameEvent(
                event_id=f"{source}:confirmed",
                kind="scouts_bid_confirmed",
                payload=(("item_id", auction_id), ("player", player)),
            ),
        ),
    )


def close_bids(state: GameState, auction_id: str, order: tuple[int, ...]) -> RuleResult:
    """Reveal every bid, then pay and queue the rewards (or Mercenaries)."""

    auction = AUCTIONS_BY_ID[auction_id]
    source = f"round:{state.round_number}:scouts:{auction_id}"
    bids = {seat: amount for seat, amount, _ in state.scouts_bids}
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:revealed:{seat}",
            kind="scouts_bid_revealed",
            payload=(
                ("count", bids.get(seat, 0)),
                ("item_id", auction_id),
                ("player", seat),
            ),
        )
        for seat in order
    ]
    players = list(state.players)
    currency = auction.currency
    tasks: list[str] = []
    if auction.kind is AuctionKind.MERCENARIES:
        deployed: dict[int, int] = {}
        for seat in order:
            owner = players[seat]
            paid = bids.get(seat, 0)
            troops = min(paid, owner.troops_supply)
            players[seat] = replace(
                owner,
                resources=replace(owner.resources, spice=owner.resources.spice - paid),
                troops_supply=owner.troops_supply - troops,
                troops_conflict=owner.troops_conflict + troops,
            )
            deployed[seat] = troops
            events.append(
                GameEvent(
                    event_id=f"{source}:mercenaries:{seat}",
                    kind="scouts_mercenaries_deployed",
                    payload=(("paid", paid), ("player", seat), ("troops", troops)),
                )
            )
        lowest = min(bids.get(seat, 0) for seat in order)
        tasks = [
            f"retreat:{seat}:{deployed[seat]}"
            for seat in order
            if bids.get(seat, 0) == lowest and deployed[seat]
        ]
    else:
        winners = rank_bids({seat: bids.get(seat, 0) for seat in order}, auction.places)
        for seat in order:
            if seat not in winners:
                continue
            owner = players[seat]
            paid = bids[seat]
            if getattr(owner.resources, currency) < paid:
                raise RuntimeError("a winning bid exceeds its seat's currency")
            players[seat] = replace(
                owner,
                resources=replace(
                    owner.resources,
                    **{currency: getattr(owner.resources, currency) - paid},
                ),
            )
            events.append(
                GameEvent(
                    event_id=f"{source}:won:{seat}",
                    kind="scouts_auction_won",
                    payload=(
                        ("item_id", auction_id),
                        ("paid", paid),
                        ("place", winners[seat] + 1),
                        ("player", seat),
                    ),
                )
            )
            tasks.append(f"auction_reward:{seat}:{winners[seat]}")
    return RuleResult(
        state=replace(
            state,
            players=tuple(players),
            scouts_bids=(),
            scouts_tasks=(*tasks, *state.scouts_tasks),
        ),
        events=tuple(events),
    )


def run_auction_reward(state: GameState, task: str) -> RuleResult:
    seat, place = task.removeprefix("auction_reward:").split(":")
    auction_id = state.scouts_item
    source = f"round:{state.round_number}:scouts:{auction_id}:reward:{seat}"
    return RuleResult(
        state=push_scouts_effect(
            state, int(seat), auction_id, int(place), source=source
        )
    )


# --- Mercenaries' retreat -----------------------------------------------------------


def offer_retreat(state: GameState, task: str) -> RuleResult:
    seat, troops = task.removeprefix("retreat:").split(":")
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_RETREAT,
        frame_id=f"round:{state.round_number}:scouts:mercenaries:retreat:{seat}",
        decision=PlayerDecision(
            owner=int(seat), prompt="Retreat any of your Mercenaries troops"
        ),
        context=(("troops", int(troops)),),
    )
    return RuleResult(state=state.push_decision(frame))


def legal_retreat_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    frame = owned_top_frame(state, FrameKind.SCOUTS_RETREAT, player)
    if frame is None:
        return ()
    troops = context_int(dict(frame.context), "troops", owner=_RETREAT_FRAME)
    troops = min(troops, state.players[player].troops_conflict)
    return tuple(
        DomainAction(
            action_id="scouts_retreat", actor=player, arguments=(("count", count),)
        )
        for count in range(troops + 1)
    )


def apply_retreat(state: GameState, action: DomainAction) -> RuleResult:
    if action not in legal_retreat_actions(state, action.actor):
        raise ValueError("action is not a legal Mercenaries retreat")
    count = dict(action.arguments)["count"]
    assert isinstance(count, int)
    owner = state.players[action.actor]
    moved = replace(
        owner,
        troops_conflict=owner.troops_conflict - count,
        troops_garrison=owner.troops_garrison + count,
    )
    return RuleResult(
        state=replace(
            state.pop_decision(), players=replace_player(state.players, moved)
        ),
        events=(
            GameEvent(
                event_id=f"round:{state.round_number}:scouts:mercenaries:retreated:{action.actor}",
                kind="scouts_mercenaries_retreated",
                payload=(("count", count), ("player", action.actor)),
            ),
        ),
    )


# --- Critical Moment -----------------------------------------------------------------


def reveal_market(state: GameState) -> RuleResult:
    """Reveal the deck's top cards; fewer when it runs short (OQ-087 (b))."""

    auction_id = state.scouts_item
    count = min(AUCTIONS_BY_ID[auction_id].revealed_cards, len(state.imperium_deck))
    cards = state.imperium_deck[:count]
    revealed = replace(
        state,
        imperium_deck=state.imperium_deck[count:],
        scouts_market_cards=cards,
        scouts_calls=(),
    )
    if not cards:
        # Nothing to bid for: the calls and the close have no work.
        return RuleResult(state=replace(revealed, scouts_tasks=("moot",)))
    return RuleResult(
        state=revealed,
        events=(
            GameEvent(
                event_id=f"round:{state.round_number}:scouts:{auction_id}:market",
                kind="scouts_market_revealed",
                payload=(("card_ids", ",".join(cards)), ("item_id", auction_id)),
            ),
        ),
    )


def offer_call(state: GameState, player: int, *, source: str) -> RuleResult:
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_CALL,
        frame_id=f"{source}:call",
        decision=PlayerDecision(owner=player, prompt="Call an amount of spice or pass"),
        context=(("source", source),),
    )
    return RuleResult(state=state.push_decision(frame))


def legal_call_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    """A pass (0), or any amount up to the seat's spice nobody has called."""

    if owned_top_frame(state, FrameKind.SCOUTS_CALL, player) is None:
        return ()
    auction = AUCTIONS_BY_ID[state.scouts_item]
    called = {amount for _, amount in state.scouts_calls}
    top = min(state.players[player].resources.spice, auction.max_bid)
    return tuple(
        DomainAction(
            action_id="scouts_call", actor=player, arguments=(("count", amount),)
        )
        for amount in range(top + 1)
        if amount == 0 or amount not in called
    )


def apply_call(state: GameState, action: DomainAction) -> RuleResult:
    if action not in legal_call_actions(state, action.actor):
        raise ValueError("action is not a legal call")
    source = context_str(
        dict(state.decision_stack[-1].context), "source", owner=_CALL_FRAME
    )
    # ``count`` is the spice called (0 a pass): the UI's count stepper.
    amount = dict(action.arguments)["count"]
    assert isinstance(amount, int)
    return RuleResult(
        state=replace(
            state.pop_decision(),
            scouts_calls=(*state.scouts_calls, (action.actor, amount)),
        ),
        events=(
            GameEvent(
                event_id=f"{source}:called",
                kind="scouts_called",
                payload=(("amount", amount), ("player", action.actor)),
            ),
        ),
    )


def close_market(state: GameState) -> RuleResult:
    """Queue the highest caller's purchase (and the second's, late)."""

    auction = AUCTIONS_BY_ID[state.scouts_item]
    ranked = sorted(
        ((amount, seat) for seat, amount in state.scouts_calls if amount > 0),
        reverse=True,
    )[: auction.places]
    tasks = [
        f"take:{seat}:{amount}:{place}" for place, (amount, seat) in enumerate(ranked)
    ]
    return RuleResult(
        state=replace(state, scouts_tasks=(*tasks, "market_clear", *state.scouts_tasks))
    )


def offer_take(state: GameState, task: str) -> RuleResult:
    seat, amount, place = (int(part) for part in task.removeprefix("take:").split(":"))
    if not state.scouts_market_cards:
        return RuleResult(state=state)
    if state.players[seat].resources.spice < amount:
        # A call never exceeds the caller's spice and nothing is spent
        # before the purchase, so this cannot happen by the rules.
        raise RuntimeError("a Critical Moment caller cannot pay its call")
    frame = DecisionFrame(
        kind=FrameKind.SCOUTS_MARKET,
        frame_id=f"round:{state.round_number}:scouts:{state.scouts_item}:take:{seat}",
        decision=PlayerDecision(
            owner=seat,
            prompt=(
                "Pay your call and take a revealed card"
                if place == 0
                else "Pay your call for a revealed card, or decline"
            ),
        ),
        context=(("amount", amount), ("place", place)),
    )
    return RuleResult(state=state.push_decision(frame))


def legal_take_actions(state: GameState, player: int) -> tuple[DomainAction, ...]:
    frame = owned_top_frame(state, FrameKind.SCOUTS_MARKET, player)
    if frame is None:
        return ()
    place = context_int(dict(frame.context), "place", owner=_TAKE_FRAME)
    return (
        *(
            (DomainAction(action_id="scouts_decline_card", actor=player),)
            if place
            else ()
        ),
        *(
            DomainAction(
                action_id="scouts_take_card", actor=player, arguments=(("slot", slot),)
            )
            for slot in range(len(state.scouts_market_cards))
        ),
    )


def apply_take(state: GameState, action: DomainAction) -> RuleResult:
    """Pay the call and acquire the card into hand [Scouts auction: Critical
    Moment]; its acquisition bonus resolves as for any acquired card."""

    if action not in legal_take_actions(state, action.actor):
        raise ValueError("action is not a legal Critical Moment purchase")
    context = dict(state.decision_stack[-1].context)
    popped = state.pop_decision()
    player = action.actor
    source = f"round:{state.round_number}:scouts:{state.scouts_item}:take:{player}"
    if action.action_id == "scouts_decline_card":
        return RuleResult(
            state=popped,
            events=(
                GameEvent(
                    event_id=f"{source}:declined",
                    kind="scouts_card_declined",
                    payload=(("player", player),),
                ),
            ),
        )
    amount = context_int(context, "amount", owner=_TAKE_FRAME)
    slot = dict(action.arguments)["slot"]
    assert isinstance(slot, int)
    instance_id = popped.scouts_market_cards[slot]
    owner = popped.players[player]
    paid = replace(
        owner,
        resources=replace(owner.resources, spice=owner.resources.spice - amount),
    )
    working = replace(popped, players=replace_player(popped.players, paid))
    acquired = acquire_imperium_for_intrigue(
        working,
        player,
        instance_id,
        to_hand=True,
        source=source,
        credit_turn_recruits=False,
        from_market=True,
    )
    next_state = acquired.result.state
    events = acquired.result.events
    if acquired.places_spy:
        next_state = next_state.push_decision(
            acquisition_spy_frame(next_state, player, instance_id)
        )
    elif acquired.takes_contract:
        contracts = begin_contract_gain(
            next_state, player, 1, source=f"{source}:acquisition_bonus"
        )
        next_state = contracts.state
        events = (*events, *contracts.events)
    return RuleResult(
        state=next_state,
        events=(
            GameEvent(
                event_id=f"{source}:paid",
                kind="scouts_card_bought",
                payload=(
                    ("amount", amount),
                    ("instance_id", instance_id),
                    ("player", player),
                ),
            ),
            *events,
        ),
    )


def clear_market(state: GameState) -> RuleResult:
    """Unbought cards leave the game (OQ-083)."""

    cleared = state.scouts_market_cards
    return RuleResult(
        state=replace(
            state,
            scouts_market_cards=(),
            scouts_calls=(),
            imperium_removed=(*state.imperium_removed, *cleared),
        ),
        events=(
            GameEvent(
                event_id=f"round:{state.round_number}:scouts:{state.scouts_item}:cleared",
                kind="scouts_market_cleared",
                payload=(("card_ids", ",".join(cleared)),),
            ),
        )
        if cleared
        else (),
    )
