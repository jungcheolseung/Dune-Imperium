"""Arrakeen Scouts: auctions (slice 8).

docs/rules/arrakeen-scouts.md 8.1: "First Player부터 차례로 각 좌석이 입찰액을
비공개로 확정한다. 범위는 0부터 가진 자원(경매의 통화)과 상한(99, Mercenaries
3) 중 작은 쪽까지다. 앞선 입찰은 보이지 않는다." Ranking [Scouts schedule]:
"입찰액 내림차순의 공동 순위", "순위가 이기는 자리 수 이내이고 입찰액이 0보다
크면 이긴다. 1위가 동점이면 모두 1위 보상을 받고 2위 보상은 없다. 2위가 여럿
동점이면 모두 2위 보상을 받는다", "이긴 좌석만 입찰액을 낸다" (OQ-073).
8.2 Mercenaries (OQ-074), 8.3 Critical Moment (OQ-083, OQ-087).
"""

import random
from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.agents.determinize import determinize
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.observation import (
    known_card_seats,
    observe_state,
    secret_bid_id,
)
from dune_imperium.core.player import Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.scouts import _next_draw
from dune_imperium.rules.scouts_auctions import (
    close_bids,
    deploy_mercenaries,
    rank_bids,
    reveal_market,
)
from dune_imperium.server.session_log import log_step, reveals_hidden_information
from dune_imperium.server.sessions import _log_entry_json
from dune_imperium.simulation.invariants import check_observation_privacy

ENGINE = UprisingRulesEngine()
SCOUTS = RulesetConfig(arrakeen_scouts=True)
IMMORTALITY = RulesetConfig(arrakeen_scouts=True, immortality=True)


def _base(
    round_number: int = 5, config: RulesetConfig = SCOUTS, **seat_fields: Any
) -> GameState:
    """A round-5 Scouts step about to draw its mid auction; seat 0 first."""

    state = ENGINE.reset(config, 17)
    resolver = ChanceResolver(seed=17)
    while isinstance(ENGINE.current_decision(state), ChanceDecision):
        decision = ENGINE.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = ENGINE.apply(state, resolver.resolve(decision)).state
    rich = Resources(solari=6, spice=6, water=2)
    return replace(
        state,
        round_number=round_number,
        first_player=0,
        players=tuple(
            replace(p, resources=rich, **seat_fields.get(str(p.player_id), {}))
            for p in state.players
        ),
        decision_stack=(),
        scouts_opening=True,
        scouts_secrets_round=round_number,
        scouts_mid_auction_round=round_number,
        scouts_late_auction_round=9,
    )


def _draw(state: GameState, item_id: str) -> GameState:
    """Answer Scouts draws until ``item_id`` is revealed."""

    while True:
        state = _advance_automatic(RuleResult(state=state)).state
        frame = state.decision_stack[-1]
        if frame.kind != FrameKind.SCOUTS_DRAW:
            return state
        decision = frame.decision
        assert isinstance(decision, ChanceDecision)
        wanted = [o for o in decision.options if o.split("#")[0] == item_id]
        value = wanted[0] if wanted else decision.options[0]
        state = ENGINE.apply(
            state, ChanceOutcome(decision_id=decision.decision_id, values=(value,))
        ).state
        if wanted:
            return state


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _act(state: GameState, action_id: str, **arguments: Any) -> GameState:
    seat = _owner(state)
    action = DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )
    legal = ENGINE.legal_actions(state, seat)
    assert action in legal, (action, legal)
    return ENGINE.apply(state, action, legal_actions=legal).state


def _bid_all(state: GameState, bids: dict[int, int]) -> GameState:
    order = []
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_BID:
        seat = _owner(state)
        order.append(seat)
        state = _act(state, "scouts_bid", count=bids[seat])
        state = _act(state, "confirm_scouts_bid")
    assert order == [0, 1, 2, 3]
    return state


def test_ranking_follows_the_app() -> None:
    assert rank_bids({0: 5, 1: 5, 2: 3, 3: 0}, 2) == {0: 0, 1: 0}
    assert rank_bids({0: 7, 1: 4, 2: 4, 3: 0}, 2) == {0: 0, 1: 1, 2: 1}
    assert rank_bids({0: 0, 1: 0, 2: 0, 3: 0}, 2) == {}
    assert rank_bids({0: 2, 1: 1, 2: 0, 3: 0}, 1) == {0: 0}


def test_bids_are_sealed_until_the_last_seat_confirms() -> None:
    state = _draw(_base(), "highest_bidder_mid")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_BID
    counts = [
        dict(a.arguments)["count"]
        for a in ENGINE.legal_actions(state, 0)
        if a.action_id == "scouts_bid"
    ]
    assert counts == list(range(7))  # 0..6 Solari
    state = _act(state, "scouts_bid", count=4)
    state = _act(state, "scouts_bid", count=3)  # changed its mind
    state = _act(state, "confirm_scouts_bid")
    assert known_card_seats(state)[secret_bid_id(5, 0)] == frozenset({0})
    view = observe_state(state, 1)
    assert view.scouts_bids_confirmed == (0,)
    own = observe_state(state, 0).private
    assert own is not None and own.scouts_bid == 3
    check_observation_privacy(state)
    # The next seat's choices do not depend on seat 0's bid.
    assert len(ENGINE.legal_actions(state, 1)) == 8


def test_the_winner_pays_and_takes_the_reward() -> None:
    state = _draw(_base(), "highest_bidder_mid")
    hands = [len(p.hand) for p in state.players]
    solari = [p.resources.solari for p in state.players]
    before = state
    state = _bid_all(state, {0: 2, 1: 5, 2: 5, 3: 0})
    # 1st place tied: both win, both pay; no second place (one place anyway).
    assert [p.resources.solari for p in state.players] == [
        solari[0],
        solari[1] - 5,
        solari[2] - 5,
        solari[3],
    ]
    assert len(state.players[1].hand) == hands[1] + 1
    assert len(state.players[2].hand) == hands[2] + 1
    assert state.scouts_bids == ()
    assert reveals_hidden_information(before, state, 3)


def test_mercenaries_everyone_pays_and_the_lowest_may_retreat() -> None:
    state = _draw(_base(), "mercenaries")
    state = _bid_all(state, {0: 1, 1: 3, 2: 1, 3: 2})
    # Seats 0 and 2 bid the least (1): each may retreat its 1 troop.
    assert [p.troops_conflict for p in state.players] == [1, 3, 1, 2]
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_RETREAT
    assert _owner(state) == 0
    state = _act(state, "scouts_retreat", count=1)
    assert _owner(state) == 2
    state = _act(state, "scouts_retreat", count=0)
    assert [p.troops_conflict for p in state.players] == [0, 3, 1, 2]


def _offered_retreats(state: GameState) -> list[tuple[int, int]]:
    """Decline every queued Mercenaries retreat; each seat and its most troops."""

    offered = []
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_RETREAT:
        seat = _owner(state)
        counts = [
            int(dict(a.arguments)["count"])
            for a in ENGINE.legal_actions(state, seat)
            if a.action_id == "scouts_retreat"
        ]
        offered.append((seat, max(counts)))
        state = _act(state, "scouts_retreat", count=0)
    return offered


@pytest.mark.parametrize(
    ("bids", "offered"),
    [
        ({0: 0, 1: 2, 2: 1, 3: 3}, [(2, 1)]),
        ({0: 0, 1: 0, 2: 2, 3: 2}, [(2, 2), (3, 2)]),
        ({0: 0, 1: 0, 2: 0, 3: 2}, [(3, 2)]),  # a lone positive bid is the lowest
        ({0: 0, 1: 0, 2: 0, 3: 0}, []),
    ],
)
def test_mercenaries_retreat_goes_to_the_lowest_positive_bid(
    bids: dict[int, int], offered: list[tuple[int, int]]
) -> None:
    """The seat that bid the least may retreat its Mercenaries troops
    (``spice.auction.description.mercenaries``). User ruling 2026-09-29
    (OQ-074 (c)): a 0 is not a bid; the lowest bidders among the seats that
    bid 1 or more may retreat, and a seat that bid 0 neither retreats nor
    blocks the others."""

    state = _draw(_base(), "mercenaries")
    state = _bid_all(state, bids)
    assert [p.troops_conflict for p in state.players] == [bids[s] for s in range(4)]
    assert _offered_retreats(state) == offered


def _with_troops(
    state: GameState, seat: int, supply: int, specimens: int = 0
) -> GameState:
    """``seat`` holds ``supply`` supply troops and ``specimens`` specimens;
    the rest of its 12 wait in the garrison."""

    owner = state.players[seat]
    total = owner.troops_supply + owner.troops_garrison + owner.specimens
    changed = replace(
        owner,
        troops_supply=supply,
        specimens=specimens,
        troops_garrison=total - supply - specimens,
    )
    players = list(state.players)
    players[seat] = changed
    return replace(state, players=tuple(players))


def _bid_counts(state: GameState, seat: int) -> list[int]:
    return [
        int(dict(a.arguments)["count"])
        for a in ENGINE.legal_actions(state, seat)
        if a.action_id == "scouts_bid"
    ]


@pytest.mark.parametrize(
    ("config", "supply", "specimens", "spice", "counts"),
    [
        (SCOUTS, 1, 0, 6, [0, 1]),
        (SCOUTS, 0, 0, 6, [0]),
        (SCOUTS, 9, 0, 2, [0, 1, 2]),  # spice is the lower cap
        (SCOUTS, 9, 0, 6, [0, 1, 2, 3]),  # Mercenaries' own cap
        (IMMORTALITY, 1, 1, 6, [0, 1, 2]),
        (IMMORTALITY, 0, 1, 6, [0, 1]),
        (IMMORTALITY, 1, 5, 6, [0, 1, 2, 3]),
    ],
)
def test_mercenaries_bid_cap_counts_the_troops_a_seat_can_send(
    config: RulesetConfig, supply: int, specimens: int, spice: int, counts: list[int]
) -> None:
    """OQ-074 (a), user ruling 2026-09-29: the Mercenaries bid is capped at
    the lower of the seat's spice, 3 and its troops, supply troops plus its
    specimens with Immortality."""

    base = _with_troops(_base(config=config), 0, supply, specimens)
    owner = base.players[0]
    rich = replace(owner, resources=replace(owner.resources, spice=spice))
    state = _draw(replace(base, players=(rich, *base.players[1:])), "mercenaries")
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_BID
    assert _owner(state) == 0
    assert _bid_counts(state, 0) == counts


def test_mercenaries_every_spice_bid_is_one_troop_in_the_conflict() -> None:
    """OQ-074 (a): with the cap on the troops a seat can send, a seat never
    pays for a troop it does not deploy. Seat 1 holds one supply troop, so
    its highest bid is 1 and it deploys it."""

    state = _draw(_with_troops(_base(), 1, 1), "mercenaries")
    spice = state.players[1].resources.spice
    state = _bid_all(state, {0: 0, 1: 1, 2: 0, 3: 0})
    assert state.players[1].troops_conflict == 1
    assert state.players[1].troops_supply == 0
    assert state.players[1].resources.spice == spice - 1


def test_mercenaries_refuses_a_bid_beyond_the_seats_troops() -> None:
    """A bid above ``bid_cap`` cannot happen by the rules; the deployment
    says so instead of deploying less than was paid for."""

    state = _with_troops(replace(_base(), scouts_item="mercenaries"), 1, 0)
    with pytest.raises(RuntimeError, match="exceeds its seat's troops"):
        deploy_mercenaries(state, "mercenaries:0=0,1=1,2=2,3=0")


def test_determinize_keeps_a_mercenaries_bid_within_the_troop_cap() -> None:
    state = _draw(_with_troops(_base(), 0, 1), "mercenaries")
    state = _act(state, "scouts_bid", count=1)
    state = _act(state, "confirm_scouts_bid")
    samples = {
        amount
        for seed in range(20)
        for seat, amount, _ in determinize(state, 1, random.Random(seed)).scouts_bids
        if seat == 0
    }
    assert samples == {0, 1}


def test_critical_moment_calls_are_open_and_distinct() -> None:
    state = _draw(_base(), "critical_moment_mid")
    market = state.scouts_market_cards
    assert len(market) == 2
    state = _act(state, "scouts_call", count=3)
    amounts = {dict(a.arguments)["count"] for a in ENGINE.legal_actions(state, 1)}
    assert 3 not in amounts and 0 in amounts and 4 in amounts
    state = _act(state, "scouts_call", count=4)
    state = _act(state, "scouts_call", count=0)
    state = _act(state, "scouts_call", count=1)
    # Seat 1 called highest: pays 4 and takes a card into hand.
    assert _owner(state) == 1
    spice = state.players[1].resources.spice
    state = _act(state, "scouts_take_card", slot=1)
    assert market[1] in state.players[1].hand
    assert state.players[1].resources.spice <= spice - 4 + 0  # any bonus aside
    assert market[0] in state.imperium_removed
    assert state.scouts_market_cards == ()


def test_the_log_hides_a_bid_from_the_other_seats() -> None:
    before = _draw(_base(), "highest_bidder_mid")
    action = DomainAction(action_id="scouts_bid", actor=0, arguments=(("count", 4),))
    transition = ENGINE.apply(before, action)
    entry = log_step(before, transition.state, action, transition.events)
    assert entry.sealed and not entry.reveals
    assert _log_entry_json(0, entry, seat=2, finished=False)["arguments"] == {
        "count": "(비공개)"
    }


def test_determinize_redeals_other_seats_confirmed_bids() -> None:
    state = _draw(_base(), "highest_bidder_mid")
    state = _act(state, "scouts_bid", count=5)
    state = _act(state, "confirm_scouts_bid")
    samples = {
        determinize(state, 1, random.Random(seed)).scouts_bids for seed in range(10)
    }
    assert len(samples) > 1
    assert all(0 <= amount <= 6 for rows in samples for _, amount, _ in rows)


def test_every_auction_action_is_in_the_codec() -> None:
    codec = ActionCodec(SCOUTS)
    state = _draw(_base(), "highest_bidder_mid")
    for action in ENGINE.legal_actions(state, 0):
        assert codec.decode(codec.encode(action), 0) == action


def test_the_last_confirm_is_a_reveal_even_when_nothing_moves() -> None:
    """Review (2026-09-28): an all-zero Mercenaries auction moves no card or
    resource, yet the last confirmation still reveals four bids."""

    state = _draw(_base(), "mercenaries")
    for _ in range(3):
        state = _act(state, "scouts_bid", count=0)
        state = _act(state, "confirm_scouts_bid")
    state = _act(state, "scouts_bid", count=0)
    before = state
    state = _act(state, "confirm_scouts_bid")
    assert reveals_hidden_information(before, state, 3)
    assert state.scouts_bids == ()


def test_the_last_bidder_sees_the_same_table_whatever_the_others_bid() -> None:
    """Design 4.8: the last seat's choices, view and encoding must not depend
    on the bids confirmed before it."""

    from dune_imperium.adapters.observation_encoding import encode_player_view

    tables = []
    for bids in ({0: 0, 1: 5, 2: 1}, {0: 6, 1: 0, 2: 3}):
        state = _draw(_base(), "highest_bidder_mid")
        for seat in range(3):
            state = _act(state, "scouts_bid", count=bids[seat])
            state = _act(state, "confirm_scouts_bid")
        tables.append(
            (
                ENGINE.legal_actions(state, 3),
                encode_player_view(observe_state(state, 3)),
            )
        )
    assert tables[0] == tables[1]


def test_critical_moment_second_place_may_decline_and_all_passes_clear() -> None:
    late = replace(
        _base(round_number=8), scouts_mid_auction_round=5, scouts_late_auction_round=8
    )
    state = _draw(late, "critical_moment_late")
    market = state.scouts_market_cards
    assert len(market) == 3
    for amount in (2, 5, 0, 1):
        state = _act(state, "scouts_call", count=amount)
    assert _owner(state) == 1  # 5 first
    state = _act(state, "scouts_take_card", slot=0)
    assert _owner(state) == 0  # 2 second, may decline
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_decline_card")
    assert state.players[0].resources.spice == spice
    assert set(market[1:]) <= set(state.imperium_removed)

    state = _draw(_base(), "critical_moment_mid")
    market = state.scouts_market_cards
    for _ in range(4):
        state = _act(state, "scouts_call", count=0)
    assert set(market) <= set(state.imperium_removed)
    assert state.scouts_market_cards == ()


@pytest.mark.parametrize(("deck_size", "offered"), [(1, False), (2, True)])
def test_critical_moment_mid_leaves_the_draw_while_the_deck_is_short(
    deck_size: int, offered: bool
) -> None:
    """OQ-087 (b), user ruling 2026-09-29: an auction that cannot happen in
    full leaves the pool, so the mid Critical Moment is drawn only while the
    Imperium deck holds the two cards it reveals."""

    base = _base()
    state = replace(base, imperium_deck=base.imperium_deck[:deck_size])
    draw = _next_draw(state)
    assert draw is not None and draw.step == "mid_auction"
    assert ("critical_moment_mid" in draw.options) is offered
    assert {"highest_bidder_mid", "mercenaries", "spies_for_hire_mid"} <= set(
        draw.options
    )


@pytest.mark.parametrize(("deck_size", "offered"), [(2, False), (3, True)])
def test_critical_moment_late_leaves_the_draw_while_the_deck_is_short(
    deck_size: int, offered: bool
) -> None:
    """OQ-087 (b): the late Critical Moment reveals three cards."""

    base = replace(
        _base(round_number=8), scouts_mid_auction_round=5, scouts_late_auction_round=8
    )
    state = replace(base, imperium_deck=base.imperium_deck[:deck_size])
    draw = _next_draw(state)
    assert draw is not None and draw.step == "late_auction"
    assert ("critical_moment_late" in draw.options) is offered
    assert len(draw.options) >= 2


def test_critical_moment_with_an_empty_deck_is_never_drawn() -> None:
    base = _base()
    empty = replace(base, imperium_deck=(), imperium_removed=base.imperium_deck)
    state = _draw(empty, "critical_moment_mid")
    # The draw could not pick it: another auction was revealed instead.
    assert state.scouts_item != "critical_moment_mid"
    assert state.scouts_market_cards == ()
    # The reveal itself refuses a short deck (it cannot be reached).
    short = replace(
        base, scouts_item="critical_moment_mid", imperium_deck=base.imperium_deck[:1]
    )
    with pytest.raises(RuntimeError, match="short Imperium deck"):
        reveal_market(short)


def test_the_heuristic_bids_once_then_confirms() -> None:
    """Slice 10: a sealed bid would otherwise tie every count with the
    confirmation, and the agent re-picked until it drew the confirmation."""

    from dune_imperium.agents import HeuristicAgent

    state = _draw(_base(), "highest_bidder_mid")
    agent = HeuristicAgent(seed=3)
    steps = 0
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_BID:
        seat = _owner(state)
        legal = ENGINE.legal_actions(state, seat)
        action = agent.choose_action(observe_state(state, seat), legal)
        state = ENGINE.apply(state, action, legal_actions=legal).state
        steps += 1
    assert steps == 8  # a bid and a confirmation per seat


def test_the_heuristic_calls_a_small_open_amount() -> None:
    from dune_imperium.agents.heuristic_agent import score_action

    def call(count: int) -> float:
        return score_action(
            DomainAction(
                action_id="scouts_call", actor=0, arguments=(("count", count),)
            )
        )

    assert call(3) > call(2) > call(1) > call(0) > call(4)


def test_auction_rewards_resolve_by_place_then_turn_order() -> None:
    """OQ-073, user ruling 2026-09-29: winners' rewards resolve first place
    first, and seats sharing a place from the First Player on. Seat 3 (idx 3)
    wins first place though it sits after the tied 2nd-place seats 0 and 1
    (idx 0, 1) in turn order."""

    state = replace(
        _base(),
        scouts_item="highest_bidder_late",
        scouts_bids=((0, 3, True), (1, 3, True), (2, 0, True), (3, 5, True)),
    )
    result = close_bids(state, "highest_bidder_late", (0, 1, 2, 3))
    assert result.state.scouts_tasks == (
        "auction_reward:3:0",
        "auction_reward:0:1",
        "auction_reward:1:1",
    )


@pytest.mark.parametrize("config", [SCOUTS, IMMORTALITY])
def test_close_bids_only_takes_spice_and_queues_mercenaries_tasks(
    config: RulesetConfig,
) -> None:
    """OQ-074: Mercenaries deploys later (``deploy_mercenaries``);
    ``close_bids`` itself only pays each seat's bid and queues the one
    deployment task. With Immortality too: the specimen top-up is part of
    the deployment (OQ-074 (a))."""

    state = replace(
        _base(config=config),
        scouts_item="mercenaries",
        scouts_bids=((0, 3, True), (1, 0, True), (2, 0, True), (3, 0, True)),
    )
    spice = state.players[0].resources.spice
    result = close_bids(state, "mercenaries", (0, 1, 2, 3))
    assert result.state.players[0].resources.spice == spice - 3
    assert result.state.players[0].troops_conflict == 0
    assert result.state.scouts_tasks == ("mercenaries:0=3,1=0,2=0,3=0",)


def test_mercenaries_returns_the_specimen_shortfall_by_itself() -> None:
    """OQ-074 (a), user ruling 2026-09-29: the bid counts specimens, so the
    deployment returns a seat's shortfall of specimens to its supply by
    itself ("at any time" [Immortality p. 8]), one ``specimen_returned``
    event each, and deploys the whole bid; no seat is asked. Seat 0 (supply
    1, specimens 2) bids 3 and returns 2; seat 1 (supply 1, specimens 5)
    bids 2 and returns only its shortfall of 1."""

    base = _base(config=IMMORTALITY)
    base = _with_troops(_with_troops(base, 0, 1, 2), 1, 1, 5)
    state = _draw(base, "mercenaries")
    before = len(state.event_log)
    state = _bid_all(state, {0: 3, 1: 2, 2: 0, 3: 0})
    seat0, seat1 = state.players[:2]
    assert (seat0.troops_conflict, seat0.troops_supply, seat0.specimens) == (3, 0, 0)
    assert (seat1.troops_conflict, seat1.troops_supply, seat1.specimens) == (2, 0, 4)
    returned = [
        dict(e.payload)["player"]
        for e in state.event_log[before:]
        if e.kind == "specimen_returned"
    ]
    assert returned == [0, 0, 1]
    deployed = {
        dict(e.payload)["player"]: dict(e.payload)["troops"]
        for e in state.event_log[before:]
        if e.kind == "scouts_mercenaries_deployed"
    }
    assert deployed == {0: 3, 1: 2, 2: 0, 3: 0}
    # Seat 1 bid the least of the positive bids: its retreat comes next.
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_RETREAT
    assert _owner(state) == 1


def test_mercenaries_without_a_shortfall_returns_no_specimen() -> None:
    base = _with_troops(_base(config=IMMORTALITY), 0, 5, 2)
    state = _draw(base, "mercenaries")
    before = len(state.event_log)
    state = _bid_all(state, {0: 3, 1: 0, 2: 0, 3: 0})
    assert state.players[0].specimens == 2
    assert state.players[0].troops_conflict == 3
    assert not any(e.kind == "specimen_returned" for e in state.event_log[before:])


def test_mercenaries_retreat_advances_chanis_tactics_token() -> None:
    """OQ-074 (c): the Mercenaries retreat is the game's own retreat
    (``retreat_units``); Chani's Tactics token counts it like any other
    retreat, and retreating 0 troops changes nothing and does not raise."""

    base = _base()
    seat = replace(base.players[0], leader_id="chani")
    state = _draw(replace(base, players=(seat, *base.players[1:])), "mercenaries")
    space = state.players[0].tactics_track_space
    state = _bid_all(state, {0: 1, 1: 3, 2: 1, 3: 2})
    assert _owner(state) == 0
    state = _act(state, "scouts_retreat", count=1)
    assert state.players[0].tactics_track_space == space + 1
    assert _owner(state) == 2
    before = state.players[2].troops_conflict
    state = _act(state, "scouts_retreat", count=0)
    assert state.players[2].troops_conflict == before


def test_specimen_top_up_covers_every_scouts_recruit_and_parking_count() -> None:
    """MAX_SPECIMEN_TOP_UP bounds every specimen top-up the rules offer as
    an action: every RecruitTroops/RecruitToConflict reward in the Scouts
    content and every mission's parked troop count (user ruling 2026-09-29).
    Mercenaries returns its shortfall by itself (OQ-074 (a))."""

    from dune_imperium.content.arrakeen_scouts import (
        AUCTIONS,
        EVENTS,
        MAX_SPECIMEN_TOP_UP,
        SALES,
        SUBCOMMITTEES,
    )
    from dune_imperium.content.arrakeen_scouts.types import RecruitToConflict
    from dune_imperium.content.uprising.effect_dsl import RecruitTroops
    from dune_imperium.rules.scouts_missions import _PARKING

    options = [
        option
        for event in EVENTS
        for option in (
            *event.options,
            *(choice.option for choice in event.secret_choices),
        )
    ]
    options += [option for sale in SALES for option in sale.options]
    options += [subcommittee.option for subcommittee in SUBCOMMITTEES]
    recruit_counts = [
        reward.count
        for option in options
        for reward in option.rewards
        if isinstance(reward, (RecruitTroops, RecruitToConflict))
    ]
    recruit_counts += [
        reward.count
        for auction in AUCTIONS
        for rewards in auction.rank_rewards
        for reward in rewards
        if isinstance(reward, (RecruitTroops, RecruitToConflict))
    ]
    assert recruit_counts  # the content actually recruits somewhere
    assert MAX_SPECIMEN_TOP_UP >= max(recruit_counts)
    assert MAX_SPECIMEN_TOP_UP >= max(count for _, count in _PARKING.values())


def test_spies_for_hire_may_draw_its_intrigue_before_placing_the_spy() -> None:
    """OQ-100 (user ruling 2026-10-05, "순서 자유로"): the winner's Intrigue
    draw may come before its Spy placement; the placement waits on top and
    the draw is not given twice."""
    base = replace(
        _base(round_number=8),
        scouts_mid_auction_round=5,
        scouts_late_auction_round=8,
    )
    state = _draw(base, "spies_for_hire_late")
    state = _bid_all(state, {0: 0, 1: 3, 2: 1, 3: 0})
    assert state.decision_stack[-1].kind == FrameKind.SPY_PLACEMENT
    assert _owner(state) == 1
    intrigue = len(state.players[1].intrigue_cards)
    state = _act(state, "scouts_rewards_first")
    assert len(state.players[1].intrigue_cards) == intrigue + 1
    assert state.decision_stack[-1].kind == FrameKind.SPY_PLACEMENT
    post = next(
        dict(a.arguments)["post_id"]
        for a in ENGINE.legal_actions(state, 1)
        if a.action_id == "place_spy_on_space"
    )
    state = _act(state, "place_spy_on_space", post_id=post)
    assert post in state.players[1].spy_post_ids
    assert len(state.players[1].intrigue_cards) == intrigue + 1
