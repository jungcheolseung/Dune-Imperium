"""Arrakeen Scouts: a unit a mission puts straight into the Conflict is a unit
deployed this turn (OQ-077 note 2026-11-02; cloud engine review finding 1).

The rules the tests quote:

- OQ-077 (b): "방문 때 "recruit"는 그 troop을 garrison으로 옮기는 recruit이며,
  그 turn에 recruit한 troop으로 센다". (c): ""곧바로 Conflict에"는 칸이 Combat 칸이
  아니어도 그 troop만 Conflict에 넣는다(그 troop 전용 배치 몫; garrison의 다른
  troop 배치를 열지 않는다)".
- The app: "recruit and immediately deploy" [Scouts mission: Security Detail],
  and "the Dreadnought is immediately deployed to the conflict" [Scouts
  mission: Armed Escort].
- The designer's ruling the user adopted (OQ-057, "디자이너 판정을 무조건
  따른다"; docs/rules/designer-rulings-audit.md): "You need to have a moment in
  time when there are 3 units in the conflict that were deployed to the
  conflict this turn, then that requirement becomes true."

So those units count for Distraction and Coercive Negotiation ("three or more
units"), Rise of Ix's Diversion ("four or more units", dreadnoughts
included) and the OQ-029 (3) withdrawal floor; being no basic deployment, they
take no allowance and are never withdrawn (OQ-029 1).
"""

from dataclasses import replace

import pytest
from tests.unit.rules import test_scouts_missions as uprising
from tests.unit.rules import test_scouts_original_missions as original
from tests.unit.rules import test_uprising_ix_options as ix

from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.rules.combat_deployment import (
    dreadnoughts_deployed_this_turn,
    legal_dreadnought_withdrawals,
    units_deployed_with_dreadnoughts,
)

DETONATION = "intrigue:detonation:0"
DISTRACTION = "intrigue:distraction:0"
DIVERSION = "intrigue:diversion:0"


def _play(card_id: str, option: int = 0) -> DomainAction:
    return DomainAction(
        action_id="play_intrigue",
        actor=0,
        arguments=(("card_id", card_id), ("option", option)),
    )


def _holding(state: GameState, *cards: str) -> GameState:
    """Seat 0 holds ``cards`` (taken out of the Intrigue deck)."""

    seat = replace(state.players[0], intrigue_cards=cards)
    return replace(
        state,
        players=(seat, *state.players[1:]),
        intrigue_deck=tuple(card for card in state.intrigue_deck if card not in cards),
    )


def _withdrawals(engine: object, state: GameState) -> set[object]:
    return {
        dict(action.arguments)["count"]
        for action in engine.whole_actions(state, 0)  # type: ignore[attr-defined]
        if action.action_id == "withdraw_troops"
    }


@pytest.mark.parametrize(
    ("mission_id", "space_id", "troops"),
    [
        ("security_detail", "deliver_supplies", 1),
        ("weirding_warfare", "espionage", 2),
        ("send_for_aid", "gather_support", 1),
    ],
)
def test_an_uprising_mission_troop_is_a_unit_deployed_this_turn(
    mission_id: str, space_id: str, troops: int
) -> None:
    state = uprising._answer(uprising._reveal(uprising._base(), mission_id), {0: ""})
    visited = uprising._visit(uprising._turn_for(state), space_id)
    seat = visited.players[0]
    assert seat.troops_conflict == troops
    assert (seat.units_deployed_turn, seat.units_deployed_peak) == (troops, troops)
    # No basic deployment: nothing to withdraw (OQ-029 1).
    assert _withdrawals(uprising.ENGINE, visited) == set()


def test_a_mission_troop_kept_in_the_garrison_is_not_deployed() -> None:
    # "Units can't be deployed to the Conflict this turn." [Shaddam Corrino IV
    # card] [Main p. 17]: the troop is recruited into the garrison (OQ-130),
    # so the turn deployed nothing.
    state = uprising._answer(
        uprising._reveal(uprising._base(), "send_for_aid"), {0: ""}
    )
    turn = uprising._turn_for(state)
    banned = replace(
        turn,
        decision_stack=(
            replace(
                turn.decision_stack[-1], context=(("units_deploy_blocked", True),)
            ),
        ),
    )
    seat = uprising._visit(banned, "gather_support").players[0]
    assert seat.troops_conflict == 0
    assert (seat.units_deployed_turn, seat.units_deployed_peak) == (0, 0)


def test_distraction_counts_the_security_detail_troop() -> None:
    """Security Detail's troop and Detonation's two garrison troops make the
    turn's three units [Distraction card]; without the mission troop the two
    did not (cloud review finding 1)."""

    state = uprising._answer(
        uprising._reveal(uprising._base(), "security_detail"), {0: ""}
    )
    state = _holding(uprising._turn_for(state), DETONATION, DISTRACTION)
    engine = uprising.ENGINE
    visited = uprising._visit(state, "deliver_supplies")
    assert _play(DISTRACTION) not in engine.whole_actions(visited, 0)
    opened = apply_whole(engine, visited, _play(DETONATION, 1)).state
    deployed = apply_whole(
        engine,
        opened,
        DomainAction(
            action_id="deploy_intrigue_troops", actor=0, arguments=(("count", 2),)
        ),
    ).state
    seat = deployed.players[0]
    assert (seat.troops_conflict, seat.units_deployed_turn) == (3, 3)
    assert _play(DISTRACTION) in engine.whole_actions(deployed, 0)


def test_stowaways_troops_are_units_deployed_this_turn_with_rise_of_ix() -> None:
    state = uprising._answer(
        uprising._reveal(uprising._base(ix.SCOUTS), "stowaways"), {0: ""}
    )
    visited = ix._scouts_visit(uprising._turn_for(state), "smuggling")
    seat = visited.players[0]
    assert (seat.troops_conflict, seat.units_deployed_turn) == (2, 2)
    assert units_deployed_with_dreadnoughts(visited, 0) == 2


def _armed_escort(config: object) -> GameState:
    state = uprising._reveal(
        uprising._base(config),  # type: ignore[arg-type]
        "armed_escort",
        scouts_revealed=ix._TYPE_ONE_FIRST,
    )
    return uprising._turn_for(state)


def test_the_armed_escort_dreadnought_is_a_unit_deployed_this_turn() -> None:
    """"the Dreadnought is immediately deployed to the conflict" [Scouts
    mission: Armed Escort]: a unit of the turn for Diversion's count, kept as
    the turn's effect deployment -- no allowance, no withdrawal."""

    visited = ix._scouts_visit(_armed_escort(ix.SCOUTS), "dreadnought")
    seat = visited.players[0]
    assert seat.dreadnoughts_conflict == 1
    # A dreadnought is no troop [Rise of Ix p. 6]: the troops' count holds none.
    assert seat.units_deployed_turn == 0
    assert dreadnoughts_deployed_this_turn(visited, 0) == 1
    assert units_deployed_with_dreadnoughts(visited, 0) == 1
    assert seat.units_peak_with_dreadnoughts == 1
    assert legal_dreadnought_withdrawals(visited, 0) == ()


def test_diversion_counts_the_armed_escort_dreadnought() -> None:
    """The escort's dreadnought and Detonation's three garrison troops are the
    turn's four units, dreadnoughts included [Diversion card] (rise-of-ix.md
    6, table row "unit")."""

    state = _holding(_armed_escort(ix.SCOUTS), DETONATION, DIVERSION)
    engine = ix.SCOUTS_ENGINE
    visited = ix._scouts_visit(state, "dreadnought")
    opened = apply_whole(engine, visited, _play(DETONATION, 1)).state
    deployed = apply_whole(
        engine,
        opened,
        DomainAction(
            action_id="deploy_intrigue_troops", actor=0, arguments=(("count", 3),)
        ),
    ).state
    assert units_deployed_with_dreadnoughts(deployed, 0) == 4
    assert _play(DIVERSION) in engine.whole_actions(deployed, 0)


def test_the_genetic_research_troop_is_a_unit_deployed_this_turn() -> None:
    state = original._answer(
        original._reveal(original._base(), "genetic_research"), {0: ""}
    )
    seat = original._visit(state, "selective_breeding").players[0]
    assert seat.troops_conflict == 1
    assert (seat.units_deployed_turn, seat.units_deployed_peak) == (1, 1)


def _stationed_support(config: object) -> GameState:
    """Seat 0 parked Stationed Support's two troops at the original Research
    Station, a Combat space, and sends an Agent there; the others passed."""

    state = original._reveal(
        original._base(config),  # type: ignore[arg-type]
        "botanical_stationed_support",
    )
    state = original._act(state, "scouts_join_mission", target="")
    state = original._act(state, "scouts_discard", card_id=state.players[0].hand[-1])
    return original._answer(state, {})


def _visit_research_station(state: GameState) -> GameState:
    visited = original._send_agent(
        original._turn_for(state), "imperium_research_station"
    )
    collect = next(
        action
        for action in original.ENGINE.whole_actions(visited, 0)
        if action.action_id == "scouts_collect_mission"
    )
    return apply_whole(original.ENGINE, visited, collect).state


def test_stationed_support_troops_join_the_turns_deployment_count() -> None:
    """On the original board the mission troops and the basic deployment's
    two garrison troops are the turn's four units; only the two deployed
    from the garrison may be withdrawn (OQ-029 1), and the deployment room is
    still two garrison troops (OQ-077 (c): the mission troops open no other
    deployment)."""

    visited = _visit_research_station(_stationed_support(original.ORIGINAL))
    engine = original.ENGINE
    seat = visited.players[0]
    assert (seat.troops_conflict, seat.units_deployed_turn) == (2, 2)
    deploys = {
        dict(action.arguments)["count"]
        for action in engine.whole_actions(visited, 0)
        if action.action_id == "deploy_troops"
    }
    assert deploys == {1, 2}
    deployed = apply_whole(
        engine,
        visited,
        DomainAction(action_id="deploy_troops", actor=0, arguments=(("count", 2),)),
    ).state
    seat = deployed.players[0]
    assert (seat.troops_conflict, seat.units_deployed_turn) == (4, 4)
    assert seat.units_deployed_peak == 4
    assert _withdrawals(engine, deployed) == {1, 2}


def test_diversion_on_the_original_board_holds_the_mission_troops_floor() -> None:
    """Original board with Rise of Ix: the two Stationed Support troops and
    two deployed garrison troops make Diversion's four units; once it is
    played, no withdrawal may take the turn below them (OQ-029 (3))."""

    state = _holding(_stationed_support(original.ORIGINAL_IX), DIVERSION)
    engine = original.ENGINE
    visited = _visit_research_station(state)
    deployed = apply_whole(
        engine,
        visited,
        DomainAction(action_id="deploy_troops", actor=0, arguments=(("count", 2),)),
    ).state
    assert units_deployed_with_dreadnoughts(deployed, 0) == 4
    assert _withdrawals(engine, deployed) == {1, 2}
    assert _play(DIVERSION) in engine.whole_actions(deployed, 0)
    played = apply_whole(engine, deployed, _play(DIVERSION)).state
    while played.decision_stack[-1].kind != "agent_effects":
        # The Freighter icon is a "may" [Rise of Ix p. 5]: take it.
        choice = next(
            action
            for action in engine.whole_actions(played, 0)
            if action.action_id != "finish_agent_turn"
        )
        played = apply_whole(engine, played, choice).state
    assert _withdrawals(engine, played) == set()
