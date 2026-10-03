"""Recruit and specimen shortfalls taken once troops return to the supply.

OQ-030 and OQ-049 (user ruling 2026-10-04, "앱 구현 방식으로 가자", following
the Steam app): what a recruit or a specimen icon cannot take from an empty
supply waits on the seat, and is taken -- troops first, then specimens -- as
soon as troops come back to that seat's supply during the same player turn.
Every seat's shortfall clears when a turn opens, and is dropped whenever no
player turn is open.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
    Resources,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.effects import recruit_troops
from dune_imperium.rules.frames import reset_turn_counters
from dune_imperium.rules.leader_abilities import (
    legal_leader_placement_ability_actions,
)
from dune_imperium.rules.scouts_effects import push_scouts_effect
from dune_imperium.rules.shortfall import (
    drop_stale_shortfalls,
    refill_shortfall,
    shortfall_is_stale,
    shortfall_refill_seat,
)
from dune_imperium.rules.specimens import generate_specimens

DIPLOMACY = "player:0:starter:diplomacy:0"


def _turn_state(owner: PlayerState, config: RulesetConfig) -> GameState:
    return GameState(
        config=config,
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        round_number=1,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )


def test_a_recruit_records_what_the_supply_could_not_cover() -> None:
    owner = PlayerState(player_id=0, troops_supply=1, troops_garrison=11)

    recruited_owner, recruited = recruit_troops(owner, 3)

    assert recruited == 1
    assert recruited_owner.troops_supply == 0
    assert recruited_owner.ungained_troops == 2


def test_other_memories_makes_up_a_recruit_shortfall_this_turn() -> None:
    # Uprising alone reaches it: Lady Jessica's Other Memories returns her
    # memories to the supply after a recruit fell short.
    owner = PlayerState(
        player_id=0,
        leader_id="lady_jessica",
        leader_face_id="lady_jessica",
        resources=Resources(spice=1, water=1),
        troops_supply=0,
        troops_garrison=3,
        troops_conflict=7,
        memories=2,
        hand=(DIPLOMACY,),
        ungained_troops=1,
    )
    state = _turn_state(owner, RulesetConfig())
    placement = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "espionage"
        and dict(action.arguments)["card_id"] == DIPLOMACY
    )
    placed = apply_agent_action(state, placement).state
    use = next(
        action
        for action in legal_leader_placement_ability_actions(placed, 0)
        if action.action_id == "use_other_memories"
    )

    result = UprisingRulesEngine().apply(placed, use)

    seat = result.state.players[0]
    assert seat.memories == 0
    assert seat.troops_garrison == 4
    assert seat.troops_supply == 1
    assert seat.ungained_troops == 0
    refills = [event for event in result.events if event.kind == "shortfall_refilled"]
    assert len(refills) == 1
    assert dict(refills[0].payload) == {"player": 0, "specimens": 0, "troops": 1}
    # The made-up troop is this turn's recruit.
    turn = next(
        frame
        for frame in result.state.decision_stack
        if frame.kind == "agent_effects"
    )
    assert dict(turn.context)["troops_recruited"] == 1


def test_a_returned_specimen_makes_up_a_recruit_shortfall() -> None:
    config = RulesetConfig(immortality=True)
    owner = PlayerState(
        player_id=0,
        troops_supply=0,
        troops_garrison=10,
        specimens=2,
        ungained_troops=1,
    )
    state = _turn_state(owner, config)
    engine = UprisingRulesEngine()
    (returned,) = (
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "return_specimen"
    )

    result = engine.apply(state, returned)

    seat = result.state.players[0]
    assert seat.specimens == 1
    assert seat.troops_supply == 0
    assert seat.troops_garrison == 11
    assert seat.ungained_troops == 0
    assert dict(result.state.decision_stack[-1].context)["troops_recruited"] == 1


def test_troops_are_made_up_before_specimens() -> None:
    state = _turn_state(
        PlayerState(
            player_id=0,
            troops_supply=2,
            troops_garrison=10,
            ungained_troops=1,
            ungained_specimens=2,
        ),
        RulesetConfig(immortality=True),
    )

    assert shortfall_refill_seat(state) == 0
    seat = refill_shortfall(state, 0).state.players[0]

    assert seat.troops_garrison == 11
    assert seat.specimens == 1
    assert seat.troops_supply == 0
    assert seat.ungained_troops == 0
    assert seat.ungained_specimens == 1


def test_a_specimen_shortfall_waits_like_a_recruit() -> None:
    state = _turn_state(
        PlayerState(player_id=0, troops_supply=1, troops_garrison=11),
        RulesetConfig(immortality=True),
    )

    seat = generate_specimens(state, 0, 3, source="test").state.players[0]

    assert seat.specimens == 1
    assert seat.ungained_specimens == 2


def test_nothing_is_made_up_outside_player_turns() -> None:
    owner = PlayerState(
        player_id=0, troops_supply=3, troops_garrison=9, ungained_troops=2
    )
    state = _turn_state(owner, RulesetConfig())
    assert shortfall_refill_seat(state) == 0

    # A Conflict reward's shortfall is dropped: Combat is no one's turn and
    # troops returning to the supply at its end make nothing up.
    combat = replace(state, phase=GamePhase.COMBAT, decision_stack=())
    assert shortfall_refill_seat(combat) is None
    assert shortfall_is_stale(combat)
    dropped = drop_stale_shortfalls(combat)
    assert dropped.events == ()
    assert dropped.state.players[0].ungained_troops == 0
    assert dropped.state.players[0].troops_supply == 3
    assert not shortfall_is_stale(dropped.state)


def test_every_seat_s_shortfall_clears_when_a_turn_opens() -> None:
    players = (
        PlayerState(player_id=0, ungained_troops=1),
        PlayerState(player_id=1, ungained_specimens=2),
        PlayerState(player_id=2),
        PlayerState(player_id=3, ungained_troops=3),
    )

    cleared = reset_turn_counters(players, 1, closing=0)

    assert all(seat.ungained_troops == 0 for seat in cleared)
    assert all(seat.ungained_specimens == 0 for seat in cleared)


def test_a_refill_on_another_seat_is_not_the_turn_owner_s_recruit() -> None:
    owner = PlayerState(player_id=0, troops_supply=5, troops_garrison=7)
    state = _turn_state(owner, RulesetConfig())
    other = PlayerState(
        player_id=1, troops_supply=1, troops_garrison=11, ungained_troops=1
    )
    state = replace(state, players=(owner, other, *state.players[2:]))

    assert shortfall_refill_seat(state) == 1
    refilled = refill_shortfall(state, 1).state

    assert refilled.players[1].troops_garrison == 12
    assert refilled.players[1].ungained_troops == 0
    assert dict(refilled.decision_stack[-1].context).get("troops_recruited", 0) == 0


def test_a_refill_during_a_reveal_counts_as_that_reveal_s_recruit() -> None:
    owner = PlayerState(
        player_id=0,
        troops_supply=0,
        troops_garrison=8,
        troops_conflict=2,
        specimens=2,
        research_space="c0r3",
        hand=(DIPLOMACY,),
        agents_available=0,
        agent_locations=("espionage", "arrakeen"),
    )
    state = replace(
        _turn_state(owner, RulesetConfig(immortality=True)),
        first_player=0,
        players=(
            owner,
            *(PlayerState(player_id=s, research_space="c0r3") for s in range(1, 4)),
        ),
        current_conflict_ids=("siege_of_arrakeen",),
    )
    engine = UprisingRulesEngine()
    (reveal,) = (
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "reveal_turn"
    )
    revealed = engine.apply(state, reveal).state
    waiting = replace(revealed.players[0], ungained_troops=1)
    revealed = replace(revealed, players=(waiting, *revealed.players[1:]))
    (returned,) = (
        action
        for action in engine.legal_actions(revealed, 0)
        if action.action_id == "return_specimen"
    )

    result = engine.apply(revealed, returned)

    assert [event.kind for event in result.events] == [
        "specimen_returned",
        "shortfall_refilled",
    ]
    assert result.state.players[0].troops_garrison == 9
    assert dict(result.state.decision_stack[-1].context)["reveal_troops_recruited"] == 1


def test_a_scouts_line_tops_up_its_own_recruit_before_the_shortfall() -> None:
    # Arrakeen Scouts' Readiness line returns a specimen for its own troop:
    # the line takes that troop, and the older shortfall keeps waiting.
    owner = PlayerState(
        player_id=0,
        troops_supply=0,
        troops_garrison=11,
        specimens=1,
        ungained_troops=1,
    )
    state = push_scouts_effect(
        _turn_state(owner, RulesetConfig(immortality=True, arrakeen_scouts=True)),
        0,
        "readiness",
        0,
        source="test",
    )
    engine = UprisingRulesEngine()
    (top_up,) = (
        action
        for action in engine.legal_actions(state, 0)
        if action.action_id == "scouts_return_specimens"
        and dict(action.arguments)["count"] == 1
    )

    result = engine.apply(state, top_up)

    seat = result.state.players[0]
    assert seat.troops_garrison == 12 and seat.troops_supply == 0
    assert seat.ungained_troops == 1
    kinds = [event.kind for event in result.events]
    assert "shortfall_refilled" not in kinds
    assert "troops_recruit_short" not in kinds


def test_a_specimen_shortfall_waits_only_with_immortality() -> None:
    # Only Immortality generates specimens; without it a stray count must
    # not pick a seat whose refill would then have nothing to do.
    owner = PlayerState(
        player_id=0, troops_supply=2, troops_garrison=10, ungained_specimens=1
    )

    assert shortfall_refill_seat(_turn_state(owner, RulesetConfig())) is None
