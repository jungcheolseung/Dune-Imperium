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
from dune_imperium.rules.scouts_auctions import rank_bids
from dune_imperium.server.session_log import log_step, reveals_hidden_information
from dune_imperium.server.sessions import _log_entry_json
from dune_imperium.simulation.invariants import check_observation_privacy

ENGINE = UprisingRulesEngine()
SCOUTS = RulesetConfig(arrakeen_scouts=True)


def _base(round_number: int = 5, **seat_fields: Any) -> GameState:
    """A round-5 Scouts step about to draw its mid auction; seat 0 first."""

    state = ENGINE.reset(SCOUTS, 17)
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


def test_critical_moment_reveals_what_a_short_deck_has() -> None:
    base = _base()
    state = _draw(
        replace(base, imperium_deck=base.imperium_deck[:1]), "critical_moment_mid"
    )
    assert len(state.scouts_market_cards) == 1
    empty = replace(base, imperium_deck=(), imperium_removed=base.imperium_deck)
    state = _draw(empty, "critical_moment_mid")
    # No card, no calls: the round's event draw comes next.
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW
    assert state.scouts_market_cards == ()


def test_mercenaries_deploy_only_what_the_supply_holds() -> None:
    state = _draw(_base(), "mercenaries")
    short = replace(
        state.players[1],
        troops_supply=1,
        troops_garrison=state.players[1].troops_garrison
        + state.players[1].troops_supply
        - 1,
    )
    state = replace(state, players=(state.players[0], short, *state.players[2:]))
    spice = state.players[1].resources.spice
    state = _bid_all(state, {0: 0, 1: 3, 2: 0, 3: 0})
    assert state.players[1].troops_conflict == 1
    assert state.players[1].resources.spice == spice - 3
