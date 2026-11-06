"""Arrakeen Scouts on the original game: the items with mechanisms of their own
(stage P8c-1): the Mentat auction, Fremen Exchange and the original Covert
Operation.

The rules the tests quote (docs/rules/arrakeen-scouts.md 9a and the OQs it
names):

- The Mentat auction: "First Player부터 시계 방향으로 한 번씩, 앞선 최고 호가보다
  높은 액수(1부터 가진 통화까지)를 부르거나 패스한다(OQ-162 (3)). 가장 높게 부른
  좌석이 그 액수를 내고 Mentat을 가져와 이번 라운드에 Agent로 쓴다 ... 모두
  패스하면 아무 일도 없다." The mid auction "Mentat이 없으면 1위가 부른 Solari를
  내고 원하는 진영 Influence 1을 받는다" (OQ-162 (1)); "후반 판은 Mentat이 그
  라운드에 없으면 그 라운드의 후반 경매 추첨에서 Mentat 후반 판을 빼고 남은 후보에서
  뽑는다" (OQ-162 (2)); "후반 1위는 부른 spice를 내고 Mentat을 가져와 카드 1장을
  뽑는다" (OQ-162 (3)).
- The Mentat "이번 라운드 동안 Agent 하나로 쓴다(Agent turn에 보낼 수 있다).
  Phase 5 Recall에 제 칸으로 돌린다." [DI pp. 6, 13, 18]
  (docs/rules/imperium-base.md 9).
- Fremen Exchange: "각자 선택: troop 1 잃기 — garrison이나 Conflict에서,
  Bloodlines면 Commander도(OQ-163) — 또는 Fremen −1" (9a). OQ-163: "Holy
  War(OQ-036 (a))처럼 잃는 좌석이 zone(garrison/Conflict)과 유닛 종류(troop,
  Bloodlines면 Sardaukar Commander — OQ-036·OQ-105)를 고른다. troop 줄을 고르면
  잃을 유닛 창을 열고, 선택지가 하나여도 연다(OQ-036 보강 2026-09-30). troop 줄은
  garrison이나 Conflict에 유닛이 하나라도 있으면 고를 수 있다. 없으면 Fremen −1을
  해야 하고, 그것도 못 하면 아무 일도 없다."
- The original Covert Operation: "비밀 선택(7절): 다음 라운드 Solari 2 / 다음 라운드
  카드 1장 버리기 → 지금 고른 진영 Influence 1 / 두 라운드 뒤 spice 2 / 두 라운드 뒤
  카드 2장 버리기 → 지금 고른 진영 Influence 2" (9a). 7.1: "선택은 공개될 때까지
  다른 좌석이 모른다." 7.2 and OQ-085: the due picks resolve first, in event,
  line and seat order; "손의 카드 1장 버리기 → troop 3"은 버릴 카드가 있으면
  버리고 받는 선택형이다 (OQ-085 (c)); a reward not due by the game's end is
  lost (OQ-085 (a)).
"""

import random
from dataclasses import replace
from typing import Any

import pytest

from dune_imperium import BaseGame, RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.adapters.observation_encoding import (
    SCOUTS_SECRET_EVENT_IDS,
    encode_player_view,
    segment_slice,
)
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.agents.determinize import determinize
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import (
    disclose_hidden_zones,
    known_card_seats,
    observe_state,
    secret_pick_id,
)
from dune_imperium.core.player import Influence, Resources
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.display.scouts import scouts_choice_lines
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import executable_placements
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.phases import resolve_recall_or_endgame
from dune_imperium.rules.scouts_effects import SCOUTS_COLLECT, SCOUTS_NO_OPTION
from dune_imperium.server.session_log import log_step
from dune_imperium.server.sessions import _log_entry_json
from dune_imperium.simulation.invariants import (
    InvariantViolation,
    check_event_visibility,
    check_observation_privacy,
)

# Seated as named, so no Leader changes a cost and no Leader draft is dealt.
LEADERS = (
    "glossu_rabban",
    "count_ilban_richese",
    "earl_memnon_thorvald",
    "countess_ariana_thorvald",
)
ENGINE = UprisingRulesEngine(leader_ids=LEADERS)
ORIGINAL = RulesetConfig(
    base_game=BaseGame.IMPERIUM, arrakeen_scouts=True, first_player_seat_zero=True
)
ORIGINAL_IMMORTALITY = replace(ORIGINAL, immortality=True)
ORIGINAL_BLOODLINES = replace(ORIGINAL, bloodlines=True)


def _start(config: RulesetConfig, seed: int = 3) -> GameState:
    """Round 1, seat 0's first turn (the Scouts step's subcommittees drawn)."""

    state = ENGINE.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    while isinstance(decision := ENGINE.current_decision(state), ChanceDecision):
        state = ENGINE.apply(state, chance.resolve(decision)).state
    return state


def _seats(state: GameState, seat_fields: dict[int, dict[str, Any]]) -> GameState:
    rich = Resources(solari=5, spice=5, water=2)
    return replace(
        state,
        players=tuple(
            replace(
                player,
                **{"resources": rich, **seat_fields.get(player.player_id, {})},
            )
            for player in state.players
        ),
    )


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _offered(state: GameState) -> list[tuple[str, tuple[tuple[str, Any], ...]]]:
    return [
        (a.action_id, a.arguments) for a in ENGINE.whole_actions(state, _owner(state))
    ]


def _act(state: GameState, action_id: str, **arguments: Any) -> GameState:
    seat = _owner(state)
    action = DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )
    legal = (*ENGINE.legal_actions(state, seat), *ENGINE.whole_actions(state, seat))
    assert action in legal, (action, legal)
    return apply_whole(ENGINE, state, action).state


def _on_turn(state: GameState) -> bool:
    return state.decision_stack[-1].kind == FrameKind.TURN


def _collect(state: GameState, seat: int) -> GameState:
    """Collect a line its seat receives later -- an auction winner's, a
    revealed pick's without a cost: it waits for the seat's own click, the
    one action offered (user decision 2026-11-01, OQ-164)."""

    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    assert _owner(state) == seat
    assert _offered(state) == [(SCOUTS_COLLECT, ())]
    return _act(state, SCOUTS_COLLECT)


# --- The Mentat auction (OQ-162) ----------------------------------------------


def _auction_base(
    config: RulesetConfig = ORIGINAL,
    round_number: int = 5,
    seats: dict[int, dict[str, Any]] | None = None,
    **fields: Any,
) -> GameState:
    """Round ``round_number``'s Scouts step about to draw its auction; seat 0
    is First Player. ``fields`` set more of the state."""

    state = _seats(_start(config), seats or {})
    return replace(
        state,
        round_number=round_number,
        first_player=0,
        decision_stack=(),
        scouts_opening=True,
        scouts_secrets_round=round_number,
        scouts_mid_auction_round=round_number if round_number < 8 else 5,
        scouts_late_auction_round=round_number if round_number >= 8 else 9,
        **fields,
    )


def _draw_options(state: GameState) -> set[str]:
    """The next Scouts draw's options, without their ticket numbers."""

    advanced = _advance_automatic(RuleResult(state=state)).state
    frame = advanced.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_DRAW
    decision = frame.decision
    assert isinstance(decision, ChanceDecision)
    return {option.split("#")[0] for option in decision.options}


def _auction(state: GameState, item_id: str) -> GameState:
    """Answer Scouts draws until ``item_id`` is revealed."""

    while True:
        state = _advance_automatic(RuleResult(state=state)).state
        frame = state.decision_stack[-1]
        if frame.kind != FrameKind.SCOUTS_DRAW:
            return state
        decision = frame.decision
        assert isinstance(decision, ChanceDecision)
        wanted = [o for o in decision.options if o.split("#")[0] == item_id]
        state = ENGINE.apply(
            state,
            ChanceOutcome(
                decision_id=decision.decision_id,
                values=(wanted[0] if wanted else decision.options[0],),
            ),
        ).state
        if wanted:
            return state


def _calls(state: GameState) -> list[int]:
    counts = [
        dict(action.arguments)["count"]
        for action in ENGINE.whole_actions(state, _owner(state))
        if action.action_id == "scouts_call"
    ]
    assert all(isinstance(count, int) for count in counts)
    return [int(count) for count in counts]


def _call_all(state: GameState, calls: dict[int, int]) -> GameState:
    order = []
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_CALL:
        seat = _owner(state)
        order.append(seat)
        state = _act(state, "scouts_call", count=calls[seat])
    assert order == [0, 1, 2, 3]
    return state


def _solari(state: GameState) -> list[int]:
    return [player.resources.solari for player in state.players]


def _spice(state: GameState) -> list[int]:
    return [player.resources.spice for player in state.players]


def _away(state: GameState) -> GameState:
    """Seat 3 holds the Mentat this round (taken at the round's start, as a
    Sort Through the Chaos winner does [FAQ p. 4])."""

    holder = state.players[3]
    return replace(
        state,
        players=(
            *state.players[:3],
            replace(holder, mentat=True, agents_available=holder.agents_available + 1),
        ),
    )


def test_mentat_calls_rise_above_the_highest_and_stay_within_the_currency() -> None:
    state = _auction(
        _auction_base(
            seats={
                1: {"resources": Resources(solari=3, spice=9, water=0)},
                2: {"resources": Resources(solari=9, spice=0, water=0)},
            }
        ),
        "mentat_mid",
    )
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CALL
    # The mid auction calls Solari: seat 0 holds 5, 0 is the pass.
    assert _calls(state) == [0, 1, 2, 3, 4, 5]
    state = _act(state, "scouts_call", count=2)
    # Seat 1 holds 3 Solari (its 9 spice do not count): only 3 tops the 2.
    assert _calls(state) == [0, 3]
    state = _act(state, "scouts_call", count=0)
    # A pass does not lower the bar: seat 2 must still top 2.
    assert _calls(state) == [0, *range(3, 10)]
    state = _act(state, "scouts_call", count=7)
    # Seat 3's 5 Solari cannot top 7: it may only pass.
    assert _calls(state) == [0]
    calls = [
        dict(e.payload)["amount"] for e in state.event_log if e.kind == "scouts_called"
    ]
    assert calls[-3:] == [2, 0, 7]


def test_the_late_mentat_auction_calls_spice() -> None:
    state = _auction(
        _auction_base(
            round_number=8, seats={0: {"resources": Resources(solari=9, spice=2)}}
        ),
        "mentat_late",
    )
    assert _calls(state) == [0, 1, 2]


def test_nobody_pays_and_nobody_takes_the_mentat_when_every_seat_passes() -> None:
    state = _auction(_auction_base(), "mentat_mid")
    solari, spice = _solari(state), _spice(state)
    state = _call_all(state, {0: 0, 1: 0, 2: 0, 3: 0})
    assert (_solari(state), _spice(state)) == (solari, spice)
    assert not any(player.mentat for player in state.players)
    assert not any(e.kind == "scouts_auction_won" for e in state.event_log)
    assert state.scouts_calls == ()
    # The round's event is drawn next, after the mid auction (2.1).
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW


def test_the_highest_mid_caller_pays_solari_and_takes_the_mentat() -> None:
    state = _auction(_auction_base(), "mentat_mid")
    solari, spice = _solari(state), _spice(state)
    agents = [player.agents_available for player in state.players]
    state = _call_all(state, {0: 1, 1: 0, 2: 3, 3: 0})
    # Only the winner pays its call; the auction is bid in Solari.
    assert _solari(state) == [solari[0], solari[1], solari[2] - 3, solari[3]]
    assert _spice(state) == spice
    # The Mentat waits for the winner's click (OQ-164).
    assert not state.players[2].mentat
    state = _collect(state, 2)
    winner = state.players[2]
    assert winner.mentat
    assert winner.agents_available == agents[2] + 1
    assert [p.mentat for p in state.players] == [False, False, True, False]
    won = [dict(e.payload) for e in state.event_log if e.kind == "scouts_auction_won"]
    assert won[-1] == {"item_id": "mentat_mid", "paid": 3, "place": 1, "player": 2}
    assert state.scouts_calls == ()
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW


def test_the_mid_winner_gains_influence_when_the_mentat_is_away() -> None:
    state = _auction(_away(_auction_base()), "mentat_mid")
    solari = _solari(state)
    state = _call_all(state, {0: 0, 1: 2, 2: 0, 3: 0})
    # Seat 1 pays its call, collects its line (OQ-164) and picks a Faction
    # (OQ-162 (1)); every Faction below the top is offered.
    state = _collect(state, 1)
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_EFFECT
    assert _owner(state) == 1
    assert {dict(args)["faction"] for _, args in _offered(state)} == {
        "emperor",
        "spacing_guild",
        "bene_gesserit",
        "fremen",
    }
    state = _act(state, "scouts_choose_faction", faction="fremen")
    assert state.players[1].influence.fremen == 1
    assert _solari(state) == [solari[0], solari[1] - 2, solari[2], solari[3]]
    # The Mentat stays with its holder.
    assert [p.mentat for p in state.players] == [False, False, False, True]


def test_the_mid_winner_gains_nothing_with_every_track_at_the_top() -> None:
    """The Influence line with every track at 6: the gain is lost (OQ-060),
    the call is still paid."""

    top = Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6)
    state = _auction(
        _away(_auction_base(seats={1: {"influence": top}})),
        "mentat_mid",
    )
    solari = _solari(state)
    state = _call_all(state, {0: 0, 1: 2, 2: 0, 3: 0})
    # The line is still the winner's to collect, though it gives nothing
    # (OQ-164; a step passing by itself opens a window too, 2026-09-30).
    state = _collect(state, 1)
    assert state.players[1].influence == top
    assert _solari(state)[1] == solari[1] - 2
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW


def test_the_late_winner_takes_the_mentat_and_a_card_and_sends_it_as_an_agent() -> None:
    state = _auction(_auction_base(round_number=8), "mentat_late")
    spice, solari = _spice(state), _solari(state)
    hand = len(state.players[0].hand)
    agents = state.players[0].agents_available
    state = _call_all(state, {0: 4, 1: 0, 2: 0, 3: 0})
    assert len(state.players[0].hand) == hand
    state = _collect(state, 0)
    seat = state.players[0]
    assert _spice(state) == [spice[0] - 4, spice[1], spice[2], spice[3]]
    assert _solari(state) == solari
    assert seat.mentat and seat.agents_available == agents + 1
    assert len(seat.hand) == hand + 1
    assert any(e.kind == "mentat_taken" for e in state.event_log)
    # The late round has no event: the Scouts step ends with the First
    # Player's turn, where the Mentat is one more Agent to send.
    assert _on_turn(state) and _owner(state) == 0
    assert executable_placements(state, 0)
    # Recall returns it to its space [DI p. 13].
    recalled = resolve_recall_or_endgame(
        replace(state, phase=GamePhase.RECALL_OR_ENDGAME, decision_stack=())
    ).state
    assert not any(player.mentat for player in recalled.players)
    assert recalled.players[0].agents_available == 2


def test_a_late_auction_with_no_call_leaves_the_mentat_on_its_space() -> None:
    state = _auction(_auction_base(round_number=9), "mentat_late")
    hands = [len(player.hand) for player in state.players]
    state = _call_all(state, {0: 0, 1: 0, 2: 0, 3: 0})
    assert not any(player.mentat for player in state.players)
    assert [len(player.hand) for player in state.players] == hands
    assert _on_turn(state)


@pytest.mark.parametrize(
    ("config", "others"),
    [
        (ORIGINAL, {"highest_bidder_late", "mercenaries"}),
        (
            ORIGINAL_IMMORTALITY,
            {"highest_bidder_late", "mercenaries", "competitive_study_late"},
        ),
    ],
)
def test_the_late_draw_leaves_the_mentat_out_while_it_is_away(
    config: RulesetConfig, others: set[str]
) -> None:
    """OQ-162 (2): a round whose Mentat is away draws its late auction from
    the other candidates (the mid auction's family already out, 2.2). No
    card of today's takes the Mentat across rounds 8-9, so the state is
    built."""

    base = _auction_base(
        config,
        round_number=8,
        scouts_revealed=((5, "treachery_mid"),),
    )
    assert _draw_options(base) == others | {"mentat_late"}
    assert _draw_options(_away(base)) == others
    # A Sort Through the Chaos winner owed it at the round's start counts as
    # away too [FAQ p. 4].
    assert _draw_options(replace(base, mentat_owed_to=1)) == others


def test_the_mid_draw_keeps_the_mentat_while_it_is_away() -> None:
    base = _auction_base()
    assert "mentat_mid" in _draw_options(base)
    assert _draw_options(_away(base)) == _draw_options(base)


def test_an_uprising_game_never_draws_the_mentat() -> None:
    engine = UprisingRulesEngine()
    uprising = RulesetConfig(arrakeen_scouts=True, first_player_seat_zero=True)
    state = engine.reset(uprising, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    for round_number in (5, 8):
        base = replace(
            state,
            round_number=round_number,
            first_player=0,
            decision_stack=(),
            scouts_opening=True,
            scouts_secrets_round=round_number,
            scouts_mid_auction_round=5,
            scouts_late_auction_round=8,
        )
        options = _draw_options(base)
        assert options and not {"mentat_mid", "mentat_late"} & options


# --- Fremen Exchange (OQ-163) -------------------------------------------------


def _event_base(
    config: RulesetConfig = ORIGINAL,
    round_number: int = 5,
    seats: dict[int, dict[str, Any]] | None = None,
) -> GameState:
    """``round_number``'s Scouts step about to draw its event; seat 0 is First
    Player (the mid auction is round 6 when the event is round 5's)."""

    state = _seats(_start(config), seats or {})
    return replace(
        state,
        round_number=round_number,
        first_player=0,
        decision_stack=(),
        scouts_opening=True,
        scouts_secrets_round=round_number,
        scouts_mid_auction_round=6 if round_number == 5 else 5,
        scouts_late_auction_round=9,
    )


def _reveal(state: GameState, item_id: str) -> GameState:
    advanced = _advance_automatic(RuleResult(state=state)).state
    decision = advanced.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)
    ticket = next(o for o in decision.options if o.split("#")[0] == item_id)
    return ENGINE.apply(
        advanced, ChanceOutcome(decision_id=decision.decision_id, values=(ticket,))
    ).state


def _takes_nothing(state: GameState, seat: int) -> GameState:
    """A seat with no line it can take is asked too; its one row takes nothing
    (OQ-071, cleanup-2a)."""

    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
    assert _owner(state) == seat
    assert _offered(state) == [(SCOUTS_NO_OPTION, ())]
    return _act(state, SCOUTS_NO_OPTION)


def _units(**fields: int) -> dict[str, Any]:
    """A seat's units: none but the ``fields`` given (supply makes up 12)."""

    units = {"troops_garrison": 0, "troops_conflict": 0, **fields}
    supply = 12 - units["troops_garrison"] - units["troops_conflict"]
    return {**units, "troops_supply": supply}


_TROOP_LINE = ("scouts_choose_option", (("option", 0),))
_FREMEN_LINE = ("scouts_choose_option", (("option", 1),))


def _losses(state: GameState) -> list[tuple[tuple[str, Any], ...]]:
    assert state.decision_stack[-1].kind == FrameKind.OPPONENT_UNIT_LOSS
    return [args for action_id, args in _offered(state) if action_id == "lose_unit"]


def _exchange(
    seat_units: dict[str, Any], config: RulesetConfig = ORIGINAL, **seat: Any
) -> GameState:
    """Fremen Exchange revealed, seat 0 (First Player) asked first."""

    fields = {**seat_units, "influence": Influence(fremen=2), **seat}
    return _reveal(_event_base(config, seats={0: fields}), "fremen_exchange")


def test_fremen_exchange_is_a_choice_of_a_troop_or_fremen_influence() -> None:
    state = _exchange(_units(troops_garrison=2))
    # No pass: one of the two must be taken (9a, 6).
    assert _offered(state) == [_TROOP_LINE, _FREMEN_LINE]
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[0].influence.fremen == 1
    assert state.players[0].troops_garrison == 2


def test_the_troop_line_opens_the_loss_window_with_one_option() -> None:
    """OQ-163: "troop 줄을 고르면 잃을 유닛 창을 열고, 선택지가 하나여도 연다"."""

    state = _exchange(_units(troops_garrison=2))
    state = _act(state, "scouts_choose_option", option=0)
    assert _owner(state) == 0
    assert _losses(state) == [(("zone", "garrison"),)]
    state = _act(state, "lose_unit", zone="garrison")
    seat = state.players[0]
    assert (seat.troops_garrison, seat.troops_supply) == (1, 11)
    assert seat.influence.fremen == 2
    lost = [dict(e.payload) for e in state.event_log if e.kind == "unit_lost"]
    assert lost[-1] == {"commanders": 0, "player": 0, "zone": "garrison"}
    # The next seat is asked next.
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
    assert _owner(state) == 1


def test_a_seat_with_troops_only_in_the_conflict_loses_one_there() -> None:
    state = _exchange(_units(troops_conflict=2), combat_strength=4)
    state = _act(state, "scouts_choose_option", option=0)
    assert _losses(state) == [(("zone", "conflict"),)]
    state = _act(state, "lose_unit", zone="conflict")
    seat = state.players[0]
    assert (seat.troops_conflict, seat.troops_supply) == (1, 11)
    # A unit lost from the Conflict takes its strength with it (OQ-036 (a)).
    assert seat.combat_strength == 2


def test_both_zones_are_offered_when_both_hold_a_troop() -> None:
    state = _exchange(_units(troops_garrison=1, troops_conflict=1), combat_strength=2)
    state = _act(state, "scouts_choose_option", option=0)
    assert _losses(state) == [(("zone", "garrison"),), (("zone", "conflict"),)]
    state = _act(state, "lose_unit", zone="conflict")
    seat = state.players[0]
    assert (seat.troops_garrison, seat.troops_conflict) == (1, 0)


def test_mercenaries_troops_in_the_conflict_can_pay_fremen_exchange() -> None:
    """OQ-163: "같은 라운드(5·6)의 Mercenaries 중간 경매가 이벤트보다 먼저 troop을
    넣는다" -- those troops are units in the Conflict the seat may lose."""

    base = _auction_base(
        seats={0: {**_units(), "influence": Influence(fremen=1)}, 1: _units()}
    )
    state = _auction(base, "mercenaries")
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_BID:
        state = _act(state, "scouts_bid", count=1 if _owner(state) == 0 else 0)
        state = _act(state, "confirm_scouts_bid")
    # Seat 0 alone bid: the lowest bidder, it may retreat; it keeps its troop.
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_RETREAT
    state = _act(state, "scouts_retreat", count=0)
    assert state.players[0].troops_conflict == 1
    state = _auction(state, "fremen_exchange")
    assert _offered(state) == [_TROOP_LINE, _FREMEN_LINE]
    state = _act(state, "scouts_choose_option", option=0)
    assert _losses(state) == [(("zone", "conflict"),)]
    state = _act(state, "lose_unit", zone="conflict")
    assert state.players[0].troops_conflict == 0
    # Seat 1 has no unit anywhere and no Fremen Influence.
    _takes_nothing(state, 1)


def test_a_garrison_commander_is_offered_with_bloodlines() -> None:
    state = _exchange(
        _units(troops_garrison=1),
        ORIGINAL_BLOODLINES,
        commanders_garrison=1,
        commanders_supply=0,
    )
    state = _act(state, "scouts_choose_option", option=0)
    assert _losses(state) == [
        (("zone", "garrison"),),
        (("commanders", 1), ("zone", "garrison")),
    ]
    state = _act(state, "lose_unit", commanders=1, zone="garrison")
    seat = state.players[0]
    assert (seat.commanders_garrison, seat.commanders_supply) == (0, 1)
    assert seat.troops_garrison == 1


def test_a_commander_alone_pays_the_troop_line() -> None:
    state = _exchange(
        _units(), ORIGINAL_BLOODLINES, commanders_garrison=1, commanders_supply=0
    )
    assert _offered(state) == [_TROOP_LINE, _FREMEN_LINE]
    state = _act(state, "scouts_choose_option", option=0)
    assert _losses(state) == [(("commanders", 1), ("zone", "garrison"))]


def test_nothing_to_lose_leaves_only_fremen() -> None:
    state = _exchange(_units())
    # The troop line is shown greyed, not offered (6, "할 수 없는 쪽은 고를 수
    # 없다").
    assert _offered(state) == [_FREMEN_LINE]
    shown = scouts_choice_lines(state, 0, ENGINE.whole_actions(state, 0))
    assert shown is not None
    lines = shown["lines"]
    assert isinstance(lines, list)
    troop, fremen = lines
    assert (troop["enabled"], fremen["enabled"]) == (False, True)
    assert troop["reason"] == "No troop in your garrison or the Conflict"
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[0].influence.fremen == 1


def test_neither_line_leaves_the_seat_nothing_to_take() -> None:
    state = _exchange(_units(), influence=Influence())
    state = _takes_nothing(state, 0)
    assert state.players[0].influence.fremen == 0
    assert _owner(state) == 1


def test_the_loss_window_rows_are_in_the_original_scouts_catalog() -> None:
    state = _exchange(_units(troops_garrison=1, troops_conflict=1), combat_strength=2)
    state = _act(state, "scouts_choose_option", option=0)
    codec = ActionCodec(ORIGINAL)
    for action in ENGINE.legal_actions(state, 0):
        assert codec.decode(codec.encode(action), 0) == action


# --- The original Covert Operation: a pick that names its Faction -------------

# Its four picks (9a): 0 next round 2 Solari; 1 next round discard 1 -> 1
# Influence with the Faction named now; 2 in two rounds 2 spice; 3 in two
# rounds discard 2 -> 2 Influence with the one Faction named now.
_COVERT = "imperium_covert_operation"
_FACTIONS = ("emperor", "spacing_guild", "bene_gesserit", "fremen")
# Seat -> (pick, Faction or ""): every line once.
_PICKS: dict[int, tuple[int, str]] = {
    0: (1, "fremen"),
    1: (0, ""),
    2: (3, "emperor"),
    3: (2, ""),
}


def _pick_action(seat: int, pick: int, faction: str = "") -> DomainAction:
    arguments: tuple[tuple[str, Any], ...] = (("pick", pick),)
    if faction:
        arguments = (("faction", faction), ("pick", pick))
    return DomainAction(action_id="scouts_secret_pick", actor=seat, arguments=arguments)


def _every_pick(seat: int) -> tuple[DomainAction, ...]:
    return (
        _pick_action(seat, 0),
        *(_pick_action(seat, 1, faction) for faction in _FACTIONS),
        _pick_action(seat, 2),
        *(_pick_action(seat, 3, faction) for faction in _FACTIONS),
    )


def _covert(
    round_number: int = 4, seats: dict[int, dict[str, Any]] | None = None
) -> GameState:
    """Covert Operation revealed in ``round_number``; seat 0 picks first."""

    return _reveal(_event_base(round_number=round_number, seats=seats), _COVERT)


def _pick_all(
    state: GameState, picks: dict[int, tuple[int, str]] = _PICKS
) -> GameState:
    order = []
    while state.decision_stack[-1].kind == FrameKind.SCOUTS_SECRET:
        seat = _owner(state)
        order.append(seat)
        pick, faction = picks[seat]
        state = apply_whole(ENGINE, state, _pick_action(seat, pick, faction)).state
    assert order == [0, 1, 2, 3]
    return state


def _next_round(state: GameState, round_number: int) -> GameState:
    """The Scouts step of a later round, before anything ran."""

    return replace(
        state,
        round_number=round_number,
        scouts_opening=True,
        decision_stack=(),
        scouts_item="",
        scouts_tasks=(),
    )


def _until_draw(state: GameState) -> GameState:
    """Answer the revealed picks' lines with their first offered action."""

    state = _advance_automatic(RuleResult(state=state)).state
    while state.decision_stack[-1].kind != FrameKind.SCOUTS_DRAW:
        seat = _owner(state)
        state = apply_whole(ENGINE, state, ENGINE.whole_actions(state, seat)[0]).state
    return state


def test_the_original_covert_operation_offers_every_pick_and_faction() -> None:
    """The mask says nothing: each seat is offered all four lines, the two
    that name a Faction once per Faction, whatever it holds (7.1: "선택은
    공개될 때까지 다른 좌석이 모른다")."""

    poor = {
        "hand": (),
        "influence": Influence(emperor=6, spacing_guild=6, bene_gesserit=6, fremen=6),
    }
    state = _covert(seats={1: poor})
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_SECRET
    assert ENGINE.whole_actions(state, 0) == _every_pick(0)
    state = apply_whole(ENGINE, state, _pick_action(0, 0)).state
    assert ENGINE.whole_actions(state, 1) == _every_pick(1)
    # One step each: a Faction pick is one row, as a plain pick is, so the
    # log's steps cannot tell them apart.
    rows = ENGINE.legal_actions(state, 1)
    assert len(rows) == 10
    assert {row.action_id for row in rows} == {"choose_option"}
    codec = ActionCodec(ORIGINAL)
    for row in rows:
        assert codec.decode(codec.encode(row), 1) == row


def test_each_pick_resolves_in_its_round_with_the_faction_named_at_the_pick() -> None:
    """7.2: the picks due resolve first in the round they fall due, in line
    then seat order (OQ-085 (b)); a pick's Influence goes to the Faction it
    named (9a)."""

    picked = _pick_all(_covert())
    assert sorted(picked.scouts_secret_picks) == [
        (4, _COVERT, seat, pick) for seat, (pick, _) in sorted(_PICKS.items())
    ]
    assert sorted(picked.scouts_secret_factions) == [
        (4, 0, "fremen"),
        (4, 2, "emperor"),
    ]
    before = _next_round(picked, 5)
    solari = before.players[1].resources.solari
    hand = before.players[0].hand
    result = _advance_automatic(RuleResult(state=before))
    state = result.state
    revealed = [
        dict(e.payload) for e in result.events if e.kind == "scouts_secret_revealed"
    ]
    # Line 0 (seat 1) before line 1 (seat 0); the reveal names the Faction.
    assert revealed == [
        {"event_round": 4, "item_id": _COVERT, "pick": 0, "player": 1},
        {
            "event_round": 4,
            "faction": "fremen",
            "item_id": _COVERT,
            "pick": 1,
            "player": 0,
        },
    ]
    # Seat 1's line has no cost: it waits for its click (OQ-164).
    assert state.players[1].resources.solari == solari
    state = _collect(state, 1)
    assert state.players[1].resources.solari == solari + 2
    # Seat 0's line is its to pay: discard a card, then +1 Fremen.
    assert _owner(state) == 0
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 1),)),
    ]
    state = _act(state, "scouts_choose_option", option=1)
    state = _act(state, "scouts_discard", card_id=hand[0])
    seat = state.players[0]
    assert seat.influence.fremen == 1
    assert (seat.influence.emperor, seat.influence.spacing_guild) == (0, 0)
    assert hand[0] in seat.discard_pile
    assert state.decision_stack[-1].kind == FrameKind.SCOUTS_DRAW
    # The two-round picks wait, their Factions with them.
    assert sorted(row[2:] for row in state.scouts_secret_picks) == [(2, 3), (3, 2)]
    assert state.scouts_secret_factions == ((4, 2, "emperor"),)

    state = _next_round(state, 6)
    spice = state.players[3].resources.spice
    hand = state.players[2].hand
    state = _advance_automatic(RuleResult(state=state)).state
    # Line 2 (seat 3) before line 3 (seat 2).
    state = _collect(state, 3)
    assert state.players[3].resources.spice == spice + 2
    assert _owner(state) == 2
    state = _act(state, "scouts_choose_option", option=3)
    state = _act(state, "scouts_discard", card_id=hand[0])
    state = _act(state, "scouts_discard", card_id=hand[1])
    seat = state.players[2]
    assert seat.influence.emperor == 2
    assert seat.influence.fremen == 0
    assert state.scouts_secret_picks == () and state.scouts_secret_factions == ()


def test_a_pick_seat_may_leave_its_line_at_the_reveal() -> None:
    """OQ-085 (c): the discard line is the seat's to take or leave."""

    state = _advance_automatic(
        RuleResult(state=_next_round(_pick_all(_covert()), 5))
    ).state
    state = _collect(state, 1)
    assert _owner(state) == 0
    hand = state.players[0].hand
    state = _act(state, "scouts_pass")
    assert state.players[0].influence.fremen == 0
    assert state.players[0].hand == hand


def test_an_empty_hand_at_the_reveal_gets_nothing() -> None:
    """OQ-071: "비용만 내고 보상을 받지 못하는 경우는 없어야 한다" and a line whose
    cost cannot be paid is not taken: the seat only confirms it takes
    nothing. Two cards short by one is the same."""

    picked = _pick_all(_covert())
    players = list(picked.players)
    players[0] = replace(
        players[0],
        discard_pile=(*players[0].discard_pile, *players[0].hand),
        hand=(),
    )
    state = _advance_automatic(
        RuleResult(state=_next_round(replace(picked, players=tuple(players)), 5))
    ).state
    state = _collect(state, 1)
    state = _takes_nothing(state, 0)
    assert state.players[0].influence.fremen == 0
    assert state.scouts_secret_factions == ((4, 2, "emperor"),)

    players = list(state.players)
    players[2] = replace(
        players[2],
        discard_pile=(*players[2].discard_pile, *players[2].hand[1:]),
        hand=players[2].hand[:1],
    )
    state = _next_round(replace(state, players=tuple(players)), 6)
    state = _advance_automatic(RuleResult(state=state)).state
    state = _collect(state, 3)
    state = _takes_nothing(state, 2)
    assert state.players[2].influence.emperor == 0
    assert state.scouts_secret_factions == ()


def test_a_named_faction_at_the_top_gives_nothing_to_pay_for() -> None:
    """OQ-071: a cost line is offered only when what it buys can change
    something; Influence on a track at the top is lost (OQ-060), so the seat
    keeps its card and takes nothing."""

    picked = _pick_all(_covert())
    players = list(picked.players)
    players[0] = replace(players[0], influence=Influence(fremen=6))
    state = _advance_automatic(
        RuleResult(state=_next_round(replace(picked, players=tuple(players)), 5))
    ).state
    state = _collect(state, 1)
    hand = state.players[0].hand
    state = _takes_nothing(state, 0)
    assert state.players[0].hand == hand


def test_a_pick_never_due_is_dropped_and_disclosed_after_the_game() -> None:
    """OQ-085 (a): a reward not due by the game's end is lost; review shows
    the pick and its Faction (OQ-010 ruling 4)."""

    picked = _pick_all(_covert(round_number=7))
    state = _until_draw(_next_round(picked, 8))
    # Round 8 resolved the one-round picks; the two-round ones (due in round
    # 9) wait, and a game over after round 8 never resolves them.
    assert sorted(row[2:] for row in state.scouts_secret_picks) == [(2, 3), (3, 2)]
    disclosed = disclose_hidden_zones(state)
    assert disclosed.scouts_secret_picks == state.scouts_secret_picks
    assert disclosed.scouts_secret_factions == ((7, 2, "emperor"),)


# --- Hidden information of a pick's Faction ----------------------------------


def test_no_other_seat_sees_a_pick_or_its_faction_before_the_reveal() -> None:
    state = _pick_all(_covert())
    picked = [e for e in state.event_log if e.kind == "scouts_secret_picked"]
    # The public event names the seat, never the line or the Faction.
    assert [set(dict(e.payload)) for e in picked] == [{"item_id", "player"}] * 4
    assert all(e.visible_to is None for e in picked)
    check_event_visibility(state, picked)
    known = known_card_seats(state)
    for seat in range(4):
        assert known[secret_pick_id(4, seat)] == frozenset({seat})
    for observer in range(4):
        view = observe_state(state, observer)
        assert view.private is not None
        assert view.private.scouts_secret_factions == tuple(
            (4, _COVERT, faction)
            for seat, (_, faction) in _PICKS.items()
            if seat == observer and faction
        )
        # Every seat sees the same of the others: who picked, nothing more.
        assert {seat for _, _, seat in view.scouts_secret_pending} == {0, 1, 2, 3}
    # Another Faction or another line for another seat changes nothing it
    # sees (the sweep's leak check scrambles both).
    check_observation_privacy(state)
    for observer in range(4):
        for faction in _FACTIONS:
            other = (observer + 2) % 4
            moved = replace(
                state,
                scouts_secret_picks=tuple(
                    (row[0], row[1], row[2], 3 if row[2] == other else row[3])
                    for row in state.scouts_secret_picks
                ),
                scouts_secret_factions=(
                    *(row for row in state.scouts_secret_factions if row[1] != other),
                    (4, other, faction),
                ),
            )
            assert encode_player_view(observe_state(moved, observer)) == (
                encode_player_view(observe_state(state, observer))
            )


def test_the_observer_sees_its_own_faction_in_its_observation() -> None:
    state = _pick_all(_covert())
    columns = segment_slice("private_scouts_secret_faction")
    width = len(_FACTIONS)
    event = SCOUTS_SECRET_EVENT_IDS.index(_COVERT)
    for observer in range(4):
        values = encode_player_view(observe_state(state, observer))[columns]
        _, faction = _PICKS[observer]
        expected = [0] * len(values)
        if faction:
            expected[event * width + _FACTIONS.index(faction)] = 4
        assert list(values) == expected


def test_the_log_hides_a_faction_pick_like_any_pick() -> None:
    """Another seat's log entry shows one sealed ``pick`` for every line, so a
    Faction pick looks like any other (session_log.SEALED_SHOWN_KEYS)."""

    before = _covert()
    entries = {}
    for pick, faction in ((1, "fremen"), (0, "")):
        whole = _pick_action(0, pick, faction)
        (row,) = (
            row
            for row in ENGINE.legal_actions(before, 0)
            if dict(row.arguments).get("option") == pick
            and dict(row.arguments).get("faction", "") == faction
        )
        transition = ENGINE.apply(before, row)
        entry = log_step(before, transition.state, row, transition.events)
        assert entry.sealed and entry.whole == whole
        assert not entry.reveals
        entries[pick] = entry
    named = entries[1]
    assert _log_entry_json(0, named, seat=0, finished=False)["arguments"] == {
        "faction": "fremen",
        "pick": 1,
    }
    for entry in entries.values():
        assert _log_entry_json(0, entry, seat=1, finished=False)["arguments"] == {
            "pick": "(비공개)"
        }
    assert _log_entry_json(0, named, seat=1, finished=True)["arguments"] == {
        "faction": "fremen",
        "pick": 1,
    }


def test_a_public_pick_event_may_not_carry_the_faction() -> None:
    state = _pick_all(_covert())
    leaky = GameEvent(
        event_id="leak",
        kind="scouts_secret_picked",
        payload=(("faction", "fremen"), ("item_id", _COVERT), ("player", 0)),
    )
    with pytest.raises(InvariantViolation):
        check_event_visibility(state, (leaky,))


def test_determinize_redeals_the_other_seats_factions_only() -> None:
    state = _pick_all(_covert())
    seen: set[tuple[tuple[int, int, str], ...]] = set()
    for seed in range(16):
        sampled = determinize(state, 0, random.Random(seed))
        picks = {row[2]: row[3] for row in sampled.scouts_secret_picks}
        named = {row[1]: row[2] for row in sampled.scouts_secret_factions}
        assert picks[0] == 1 and named[0] == "fremen"
        # A redealt line names a Faction exactly when it is a Faction line.
        for seat, pick in picks.items():
            assert (seat in named) == (pick in (1, 3))
        seen.add(tuple(sorted(sampled.scouts_secret_factions)))
    assert len(seen) > 1


def test_an_uprising_game_redeals_no_faction() -> None:
    """No Uprising line names a Faction, so no Faction is drawn for one."""

    engine = UprisingRulesEngine()
    config = RulesetConfig(arrakeen_scouts=True)
    state = engine.reset(config, 21)
    chance = ChanceResolver(seed=21)
    while isinstance(decision := engine.current_decision(state), ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
    state = replace(
        state,
        round_number=4,
        first_player=0,
        scouts_secret_picks=tuple(
            (4, "covert_operation", seat, 1) for seat in range(4)
        ),
    )
    for seed in range(4):
        sampled = determinize(state, 2, random.Random(seed))
        assert sampled.scouts_secret_factions == ()
        assert len(sampled.scouts_secret_picks) == 4
