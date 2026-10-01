"""Arrakeen Scouts: auctions (docs/rules/arrakeen-scouts.md 8).

Sealed auctions (To The Highest Bidder, Spies for Hire, CHOAM Negotiations,
Competitive Study, Mercenaries): each seat in turn order picks a bid with
``scouts_bid(count)``, as often as it likes, and confirms it with
``confirm_scouts_bid`` (OQ-073). The range is 0 to the lower of the seat's
own currency and the cap (Mercenaries: and the seat's troops, OQ-074 (a)),
so the offered counts say nothing of the other bids. A bid is its seat's
alone (``core.observation.secret_bid_id`` in ``known_card_seats``) until
the last seat confirms; then every bid is revealed at once and ranked as
the app does [Scouts schedule]:

- competition ranking from the highest bid (equal bids share a rank);
- a seat wins when its rank is within the auction's places and it bid more
  than 0, so a tie for first leaves no second place and a tie for second
  gives every tied seat the second-place reward;
- only winners pay, except in Mercenaries, where every seat pays its spice
  and sends one supply troop per spice to the Conflict; the seats with the
  lowest bid of 1 or more may retreat some or all of those troops to their
  garrison (a 0 is not a bid: it neither retreats nor blocks, OQ-074 (c),
  user ruling 2026-09-29). A Mercenaries bid is also capped at the troops
  the seat can send, its supply plus (Immortality) its specimens, and a seat
  whose bid exceeds its supply returns the shortfall of specimens to it by
  itself before deploying (OQ-074 (a), user ruling 2026-09-29; "at any
  time" [Immortality p. 8]). The retreat is the game's retreat
  (``retreat_units``: Chani's Tactics token counts it, OQ-074 (c)).

Winners' rewards resolve by place, first place first, and seats sharing a
place from the First Player on (OQ-073, user ruling 2026-09-29).

Critical Moment is open: the Imperium deck's top two (late: three) cards are
revealed (``GameState.scouts_market_cards``), each seat from the First
Player calls once an amount of spice nobody has called yet, or passes
(``scouts_call(count)``, 0 = pass). The highest caller pays and takes one
of the cards into hand; in the late auction the second highest may buy one
of the rest the same way. What is left, all of it when every seat passes,
is removed from the game (OQ-083, OQ-087). It is not drawn while the deck
holds fewer cards than it reveals (OQ-087 (b), user ruling 2026-09-29).
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
from dune_imperium.rules.specimens import return_specimens
from dune_imperium.rules.units import retreat_units

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


def mercenary_troops(state: GameState, player: int) -> int:
    """The troops ``player`` can send to Mercenaries: its supply, plus its
    specimens with Immortality (a specimen returns to the supply "at any
    time" [Immortality p. 8])."""

    owner = state.players[player]
    return owner.troops_supply + (owner.specimens if state.config.immortality else 0)


def bid_cap(state: GameState, player: int) -> int:
    """The highest bid ``player`` may make in the running sealed auction.

    The lower of the seat's currency and the auction's cap; Mercenaries also
    caps it at the troops the seat can send (``mercenary_troops``), so every
    spice a seat pays puts a troop in the Conflict (OQ-074 (a), user ruling
    2026-09-29). Supply troops and specimens are public, so the offered
    counts still say nothing of the other bids.
    """

    auction = AUCTIONS_BY_ID[state.scouts_item]
    cap = min(_currency(state, player, auction.auction_id), auction.max_bid)
    if auction.kind is AuctionKind.MERCENARIES:
        cap = min(cap, mercenary_troops(state, player))
    return cap


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
    """Any count up to ``bid_cap``, and the confirmation."""

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
        for seat in order:
            owner = players[seat]
            paid = bids.get(seat, 0)
            players[seat] = replace(
                owner,
                resources=replace(owner.resources, spice=owner.resources.spice - paid),
            )
        tasks = [
            "mercenaries:" + ",".join(f"{seat}={bids.get(seat, 0)}" for seat in order)
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
        # First place first; seats sharing a place from the First Player on.
        by_place = sorted(winners, key=lambda seat: (winners[seat], order.index(seat)))
        tasks = [f"auction_reward:{seat}:{winners[seat]}" for seat in by_place]
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


# --- Mercenaries ----------------------------------------------------------------------


def deploy_mercenaries(state: GameState, task: str) -> RuleResult:
    """Send each seat's paid troops to the Conflict, then queue the lowest
    bidders' retreats.

    Every spice bid is one troop: ``bid_cap`` never lets a bid exceed the
    seat's supply plus (Immortality) its specimens, and a seat whose bid
    exceeds its supply returns the shortfall of specimens to it first, by
    itself, one ``specimen_returned`` event each (OQ-074 (a), user ruling
    2026-09-29; "at any time" [Immortality p. 8]).

    The app lets the seat that bid the least spice retreat any of those
    troops to its garrison (``spice.auction.description.mercenaries``).
    User ruling 2026-09-29 (OQ-074 (c)): a 0 is not a bid, so the lowest
    bid is the lowest among the seats that bid 1 or more, and every seat
    tied at it may retreat the troops it put in; a seat that bid 0 neither
    retreats nor blocks the others. A lone positive bidder is therefore also
    the lowest and may retreat; when nobody bid more than 0 nobody retreats.
    """

    paid_by_seat = [
        (int(seat), int(paid))
        for seat, paid in (
            entry.split("=") for entry in task.removeprefix("mercenaries:").split(",")
        )
    ]
    source = f"round:{state.round_number}:scouts:{state.scouts_item}"
    working = state
    events: list[GameEvent] = []
    for seat, paid in paid_by_seat:
        if paid > mercenary_troops(working, seat):
            # ``bid_cap`` counts the same troops, and nothing moves them
            # between the bids and the deployment.
            raise RuntimeError("a Mercenaries bid exceeds its seat's troops")
        short = paid - working.players[seat].troops_supply
        if short > 0:
            topped = return_specimens(
                working, seat, short, source=f"{source}:top_up:{seat}"
            )
            working = topped.state
            events.extend(topped.events)
        owner = working.players[seat]
        working = replace(
            working,
            players=replace_player(
                working.players,
                replace(
                    owner,
                    troops_supply=owner.troops_supply - paid,
                    troops_conflict=owner.troops_conflict + paid,
                ),
            ),
        )
        events.append(
            GameEvent(
                event_id=f"{source}:mercenaries:{seat}",
                kind="scouts_mercenaries_deployed",
                payload=(("paid", paid), ("player", seat), ("troops", paid)),
            )
        )
    bids = [(seat, paid) for seat, paid in paid_by_seat if paid > 0]
    lowest = min((paid for _, paid in bids), default=0)
    retreats = tuple(f"retreat:{seat}:{paid}" for seat, paid in bids if paid == lowest)
    return RuleResult(
        state=replace(working, scouts_tasks=(*retreats, *working.scouts_tasks)),
        events=tuple(events),
    )


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
    source = f"round:{state.round_number}:scouts:mercenaries:retreated:{action.actor}"
    retreated = (
        retreat_units(state.pop_decision(), action.actor, source, troops=count)
        if count
        else RuleResult(state=state.pop_decision())
    )
    return RuleResult(
        state=retreated.state,
        events=(
            GameEvent(
                event_id=source,
                kind="scouts_mercenaries_retreated",
                payload=(("count", count), ("player", action.actor)),
            ),
            *retreated.events,
        ),
    )


# --- Critical Moment -----------------------------------------------------------------


def reveal_market(state: GameState) -> RuleResult:
    """Reveal the Imperium deck's top two (late: three) cards.

    The deck always holds them: the schedule draw leaves Critical Moment out
    while the deck is short (OQ-087 (b), user ruling 2026-09-29;
    ``rules.scouts._auction_draw``), and nothing draws from the deck between
    that draw and this reveal.
    """

    auction_id = state.scouts_item
    count = AUCTIONS_BY_ID[auction_id].revealed_cards
    if len(state.imperium_deck) < count:
        raise RuntimeError("Critical Moment was drawn with a short Imperium deck")
    cards = state.imperium_deck[:count]
    revealed = replace(
        state,
        imperium_deck=state.imperium_deck[count:],
        scouts_market_cards=cards,
        scouts_calls=(),
    )
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
    # The Scouts step runs outside any turn (no turn frame is on the stack),
    # so ``turn_owner_of`` finds none and nothing this acquisition recruits
    # joins a turn's deployment allowance.
    acquired = acquire_imperium_for_intrigue(
        working,
        player,
        instance_id,
        to_hand=True,
        source=source,
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
