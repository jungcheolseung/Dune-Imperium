"""Arrakeen Scouts: turn-order choices of events and sales (slice 5).

docs/rules/arrakeen-scouts.md 6 and 9: "각자 선택"인 이벤트와 판매는 First
Player부터 차례로 한 가지를 고른다; "또는 패스"가 있으면 선택하지 않아도
된다; 패스가 없으면 반드시 하나를 해야 하며, 할 수 없는 쪽은 고를 수 없다
(OQ-071). Political Equilibrium, Rebuild Infrastructure (OQ-084).
"""

from dataclasses import replace
from typing import Any

from dune_imperium import RulesetConfig
from dune_imperium.content.arrakeen_scouts import EVENTS_BY_ID
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome, ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.engine import _advance_automatic
from dune_imperium.rules.frames import FrameKind

ENGINE = UprisingRulesEngine()
SCOUTS = RulesetConfig(arrakeen_scouts=True)


def _base(**seat_fields: Any) -> GameState:
    """Round 4's Scouts step about to draw its event; seat 0 is First Player."""

    state = ENGINE.reset(SCOUTS, 21)
    resolver = ChanceResolver(seed=21)
    while isinstance(ENGINE.current_decision(state), ChanceDecision):
        decision = ENGINE.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = ENGINE.apply(state, resolver.resolve(decision)).state
    rich = Resources(solari=5, spice=5, water=2)
    players = tuple(
        replace(
            player,
            **{"resources": rich, **seat_fields.get(str(player.player_id), {})},
        )
        for player in state.players
    )
    return replace(
        state,
        round_number=4,
        first_player=0,
        players=players,
        decision_stack=(),
        scouts_opening=True,
    )


def _reveal(state: GameState, item_id: str) -> GameState:
    advanced = _advance_automatic(RuleResult(state=state)).state
    frame = advanced.decision_stack[-1]
    assert frame.kind == FrameKind.SCOUTS_DRAW
    decision = frame.decision
    assert isinstance(decision, ChanceDecision)
    ticket = next(o for o in decision.options if o.split("#")[0] == item_id)
    return ENGINE.apply(
        advanced, ChanceOutcome(decision_id=decision.decision_id, values=(ticket,))
    ).state


def _owner(state: GameState) -> int:
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision)
    return decision.owner


def _offered(state: GameState) -> list[tuple[str, tuple[tuple[str, Any], ...]]]:
    return [
        (a.action_id, a.arguments) for a in ENGINE.legal_actions(state, _owner(state))
    ]


def _act(state: GameState, action_id: str, **arguments: Any) -> GameState:
    seat = _owner(state)
    action = DomainAction(
        action_id=action_id, actor=seat, arguments=tuple(sorted(arguments.items()))
    )
    legal = ENGINE.legal_actions(state, seat)
    assert action in legal, (action, legal)
    return ENGINE.apply(state, action, legal_actions=legal).state


def _on_turn(state: GameState) -> bool:
    return state.decision_stack[-1].kind == FrameKind.TURN


def test_royal_delegation_goes_round_the_table_and_may_be_passed() -> None:
    state = _reveal(_base(), "royal_delegation")
    seats = []
    while not _on_turn(state):
        assert state.decision_stack[-1].kind == FrameKind.SCOUTS_CHOICE
        seats.append(_owner(state))
        assert _offered(state) == [
            ("scouts_pass", ()),
            ("scouts_choose_option", (("option", 0),)),
        ]
        if _owner(state) == 1:
            solari = state.players[1].resources.solari
            state = _act(state, "scouts_choose_option", option=0)
            assert state.players[1].resources.solari == solari - 2
            assert state.players[1].influence.emperor == 1
        else:
            state = _act(state, "scouts_pass")
    assert seats == [0, 1, 2, 3]


def test_a_seat_that_cannot_pay_is_skipped() -> None:
    poor = {"resources": Resources(solari=1, spice=0, water=1)}
    state = _reveal(_base(**{"0": poor}), "royal_delegation")
    assert _owner(state) == 1
    assert any(
        e.kind == "scouts_choice_skipped" and dict(e.payload)["player"] == 0
        for e in state.event_log
    )


def test_private_stock_must_take_one_of_its_two_lines() -> None:
    state = _reveal(_base(), "private_stock")
    assert _offered(state) == [
        ("scouts_choose_option", (("option", 0),)),
        ("scouts_choose_option", (("option", 1),)),
    ]
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].resources.spice == spice + 1


def test_crackdown_takes_the_only_loss_a_seat_can_suffer() -> None:
    # Seat 0 has no Spy on the board: the Emperor loss is its only line, so it
    # is taken without a decision. Seat 1 holds a Spy and Emperor Influence.
    state = _base(
        **{
            "0": {"influence": Influence(emperor=2)},
            "1": {
                "influence": Influence(emperor=1),
                "spies_supply": 2,
                "spy_post_ids": ("arrakis-deep-desert",),
            },
            "2": {"influence": Influence()},
            "3": {"influence": Influence()},
        }
    )
    state = _reveal(state, "crackdown")
    assert state.players[0].influence.emperor == 1
    assert state.players[0].victory_points == 0  # dropped below 2
    assert _owner(state) == 1
    assert {action for action, _ in _offered(state)} == {"scouts_choose_option"}
    state = _act(state, "scouts_choose_option", option=0)
    state = _act(state, "scouts_recall_spy", post_id="arrakis-deep-desert")
    assert state.players[1].spy_post_ids == ()
    assert state.players[1].influence.emperor == 1
    # Seats 2 and 3 can do neither: nothing happens and the turn opens.
    assert _on_turn(state)


def test_political_equilibrium_lowers_the_highest_track_and_asks_on_a_tie() -> None:
    state = _base(
        **{
            "0": {"influence": Influence(fremen=3, emperor=1)},
            "1": {"influence": Influence(spacing_guild=2, bene_gesserit=2)},
            "2": {"influence": Influence()},
            "3": {"influence": Influence(fremen=1)},
        }
    )
    state = _reveal(state, "political_equilibrium")
    assert state.players[0].influence == Influence(fremen=2, emperor=1)
    assert _owner(state) == 1
    assert {dict(args)["faction"] for _, args in _offered(state)} == {
        "spacing_guild",
        "bene_gesserit",
    }
    state = _act(state, "scouts_lose_influence", faction="bene_gesserit")
    assert state.players[1].influence == Influence(spacing_guild=2, bene_gesserit=1)
    assert state.players[3].influence == Influence()
    assert _on_turn(state)


def test_rebuild_infrastructure_needs_two_seats_to_pay() -> None:
    assert EVENTS_BY_ID["rebuild_infrastructure"].rounds == (7, 7)
    state = replace(_base(), round_number=7, shield_wall_present=False)
    state = _reveal(state, "rebuild_infrastructure")
    assert _offered(state) == [
        ("scouts_pass", ()),
        ("scouts_choose_option", (("option", 0),)),
    ]
    spice = [player.resources.spice for player in state.players]
    state = _act(state, "scouts_pass")  # seat 0
    state = _act(state, "scouts_choose_option", option=0)  # seat 1 agrees
    assert state.players[1].resources.spice == spice[1]  # nobody pays yet
    state = _act(state, "scouts_choose_option", option=0)  # seat 2 agrees
    assert state.shield_wall_present
    assert state.players[1].resources.spice == spice[1] - 1
    assert state.players[2].resources.spice == spice[2] - 1
    assert _on_turn(state)  # seat 3 is not asked


def test_rebuild_infrastructure_with_one_volunteer_pays_nothing() -> None:
    state = replace(_base(), round_number=7, shield_wall_present=False)
    state = _reveal(state, "rebuild_infrastructure")
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=0)
    for _ in range(3):
        state = _act(state, "scouts_pass")
    assert not state.shield_wall_present
    assert state.players[0].resources.spice == spice
    assert _on_turn(state)


def test_rebuild_infrastructure_does_nothing_with_the_wall_standing() -> None:
    state = _reveal(replace(_base(), round_number=7), "rebuild_infrastructure")
    assert _on_turn(state)
    assert any(e.kind == "scouts_item_moot" for e in state.event_log)


def test_moment_of_revelation_puts_prepare_the_way_in_hand() -> None:
    state = _reveal(_base(), "moment_of_revelation")
    before = dict(state.reserve_stacks)["prepare_the_way"]
    state = _act(state, "scouts_choose_option", option=0)
    assert any(
        card.startswith("reserve:prepare_the_way") for card in state.players[0].hand
    )
    assert dict(state.reserve_stacks)["prepare_the_way"] == before - 1


def _late(state: GameState) -> GameState:
    """Round 9 with the late auction in round 8: the sale is drawn now."""

    return replace(
        state,
        round_number=9,
        scouts_mid_auction_round=5,
        scouts_late_auction_round=8,
    )


def _reveal_sale(state: GameState, sale_id: str) -> GameState:
    advanced = _advance_automatic(RuleResult(state=state)).state
    decision = advanced.decision_stack[-1].decision
    assert isinstance(decision, ChanceDecision)
    assert sale_id in decision.options
    return ENGINE.apply(
        advanced, ChanceOutcome(decision_id=decision.decision_id, values=(sale_id,))
    ).state


def test_secrets_for_sale_buys_two_intrigue_for_three_spice() -> None:
    state = _reveal_sale(_late(_base()), "secrets_for_sale")
    intrigue = len(state.players[0].intrigue_cards)
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=1)
    assert state.players[0].resources.spice == spice - 3
    assert len(state.players[0].intrigue_cards) == intrigue + 2


def test_shadow_warfare_sends_its_recruits_to_the_conflict() -> None:
    spies = {
        "spies_supply": 1,
        "spy_post_ids": ("arrakis-deep-desert", "arrakis-hagga-basin"),
    }
    state = _reveal_sale(_late(_base(**{"0": spies})), "shadow_warfare")
    conflict = state.players[0].troops_conflict
    spice = state.players[0].resources.spice
    state = _act(state, "scouts_choose_option", option=1)
    state = _act(state, "scouts_recall_spy", post_id="arrakis-deep-desert")
    state = _act(state, "scouts_recall_spy", post_id="arrakis-hagga-basin")
    assert state.players[0].troops_conflict == conflict + 3
    assert state.players[0].resources.spice == spice + 2


def test_betrayal_trades_bene_gesserit_influence_for_the_tleilaxu_track() -> None:
    config = RulesetConfig(arrakeen_scouts=True, immortality=True)
    state = ENGINE.reset(config, 21)
    resolver = ChanceResolver(seed=21)
    while isinstance(ENGINE.current_decision(state), ChanceDecision):
        decision = ENGINE.current_decision(state)
        assert isinstance(decision, ChanceDecision)
        state = ENGINE.apply(state, resolver.resolve(decision)).state
    seat = replace(state.players[0], influence=Influence(bene_gesserit=2))
    state = replace(
        state,
        round_number=4,
        first_player=0,
        players=(seat, *state.players[1:]),
        decision_stack=(),
        scouts_opening=True,
    )
    start = state.players[0].tleilaxu_space
    state = _reveal(state, "betrayal")
    state = _act(state, "scouts_choose_option", option=0)
    assert state.players[0].influence.bene_gesserit == 1
    assert state.players[0].tleilaxu_space != start
    assert isinstance(state.players[0], PlayerState)
