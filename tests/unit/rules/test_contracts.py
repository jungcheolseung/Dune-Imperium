"""Tests for the CHOAM Module's public Contract market."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import GamePhase, GameState, PlayerState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.contracts import (
    apply_contract_action,
    begin_contract_gain,
    legal_contract_actions,
)


def _state(
    *,
    market: tuple[str, ...] = (
        "contract:arrakeen_i",
        "contract:high_council_ii",
    ),
    bank: tuple[str, ...] = ("contract:research_station_i",),
) -> GameState:
    return GameState(
        config=RulesetConfig(choam_module=True),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=tuple(PlayerState(player_id=seat) for seat in range(4)),
        contract_bank=bank,
        face_up_contract_ids=market,
    )


def test_contract_choice_takes_selected_tile_and_refills_the_same_position() -> None:
    state = begin_contract_gain(
        _state(),
        0,
        1,
        source="round:1:test",
    ).state
    actions = legal_contract_actions(state, 0)

    assert tuple(dict(action.arguments)["instance_id"] for action in actions) == (
        "contract:arrakeen_i",
        "contract:high_council_ii",
    )

    result = apply_contract_action(state, actions[0])

    assert result.state.players[0].active_contract_ids == ("contract:arrakeen_i",)
    assert result.state.face_up_contract_ids == (
        "contract:research_station_i",
        "contract:high_council_ii",
    )
    assert result.state.contract_bank == ()
    assert result.state.decision_stack == ()
    assert result.events[0].kind == "contract_taken"


def test_contract_market_shrinks_after_the_bank_is_empty() -> None:
    state = begin_contract_gain(
        _state(bank=()),
        2,
        1,
        source="round:1:test",
    ).state
    action = legal_contract_actions(state, 2)[1]

    result = apply_contract_action(state, action)

    assert result.state.face_up_contract_ids == ("contract:arrakeen_i",)
    assert result.state.players[2].active_contract_ids == ("contract:high_council_ii",)


def test_empty_market_converts_each_contract_icon_to_two_solari() -> None:
    result = begin_contract_gain(
        _state(market=(), bank=()),
        1,
        2,
        source="round:1:test",
    )

    assert result.state.players[1].resources.solari == 4
    assert result.state.decision_stack == ()
    assert result.events[0].kind == "contract_icons_converted_to_solari"


def test_immediate_contract_completes_and_grants_two_solari_when_taken() -> None:
    state = begin_contract_gain(
        _state(market=("contract:immediate",), bank=()),
        3,
        1,
        source="round:1:test",
    ).state

    result = apply_contract_action(state, legal_contract_actions(state, 3)[0])
    owner = result.state.players[3]

    assert owner.active_contract_ids == ()
    assert owner.completed_contract_ids == ("contract:immediate",)
    assert owner.resources.solari == 2
    assert [event.kind for event in result.events] == [
        "contract_taken",
        "contract_completed",
    ]


def test_engine_converts_a_second_icon_after_the_last_contract_is_taken() -> None:
    engine = UprisingRulesEngine()
    state = begin_contract_gain(
        _state(market=("contract:arrakeen_i",), bank=()),
        0,
        2,
        source="round:1:test",
    ).state
    action = legal_contract_actions(state, 0)[0]

    transition = engine.apply(state, action)

    assert transition.state.players[0].active_contract_ids == ("contract:arrakeen_i",)
    assert transition.state.players[0].resources.solari == 2
    assert transition.state.decision_stack == ()
    assert [event.kind for event in transition.events] == [
        "contract_taken",
        "contract_icons_converted_to_solari",
    ]


def test_contract_zones_reject_duplicates_and_module_off_state() -> None:
    state = _state()
    owner = replace(
        state.players[0],
        active_contract_ids=("contract:arrakeen_i",),
    )
    with pytest.raises(ValueError, match="two zones"):
        replace(state, players=(owner, *state.players[1:]))

    with pytest.raises(ValueError, match="CHOAM Module"):
        GameState(
            config=RulesetConfig(),
            seed=1,
            face_up_contract_ids=("contract:arrakeen_i",),
        )
