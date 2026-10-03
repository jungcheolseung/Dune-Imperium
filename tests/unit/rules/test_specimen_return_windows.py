"""Where a specimen may be returned to the supply outside the owner's turn.

"You may return any of your specimens to your supply at any time"
[Immortality p. 8]. OQ-050 (user ruling 2026-10-04, "앱 구현 방식으로
가자", following the Steam app): besides every decision of the owner's own
Agent or Reveal turn, the engine offers the return at the owner's Combat
Intrigue priority and -- while the supply has no troop -- at the owner's
Round Start Control defense, so the defending troop can come from a
specimen.
"""

from dataclasses import replace

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.combat import begin_combat_intrigue
from dune_imperium.rules.frames import FrameKind
from dune_imperium.rules.immortality import legal_specimen_return_actions
from dune_imperium.rules.phases import begin_round

IMMORTALITY = RulesetConfig(immortality=True)


def _ids(actions: tuple[DomainAction, ...]) -> list[str]:
    return [action.action_id for action in actions]


def _controlled_round_start(
    *, troops_supply: int, specimens: int, config: RulesetConfig = IMMORTALITY
) -> GameState:
    # Seat 2 controls Arrakeen as its Conflict is revealed.
    players = tuple(
        PlayerState(
            player_id=player,
            deck=tuple(f"player:{player}:card:{index}" for index in range(5)),
            troops_supply=troops_supply if player == 2 else 9,
            troops_garrison=12 - troops_supply - specimens if player == 2 else 3,
            specimens=specimens if player == 2 else 0,
            control_space_ids=("arrakeen",) if player == 2 else (),
        )
        for player in range(4)
    )
    state = GameState(
        config=config,
        seed=1,
        phase=GamePhase.ROUND_START,
        first_player=0,
        players=players,
        conflict_deck=("siege_of_arrakeen",),
    )
    return begin_round(state).state


def test_a_defender_with_only_specimens_may_return_one_for_the_troop() -> None:
    engine = UprisingRulesEngine()
    state = _controlled_round_start(troops_supply=0, specimens=2)
    assert state.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    assert _ids(engine.legal_actions(state, 2)) == [
        "decline_control_defense",
        "return_specimen",
    ]

    (returned,) = legal_specimen_return_actions(state, 2)
    after_return = engine.apply(state, returned).state

    defender = after_return.players[2]
    assert defender.specimens == 1 and defender.troops_supply == 1
    assert after_return.decision_stack[-1].kind == FrameKind.CONTROL_DEFENSE
    # One specimen covers the one defending troop; no second return.
    assert _ids(engine.legal_actions(after_return, 2)) == [
        "decline_control_defense",
        "deploy_control_defense",
    ]
    deploy = engine.legal_actions(after_return, 2)[1]
    deployed = engine.apply(after_return, deploy).state
    assert deployed.players[2].troops_conflict == 1
    assert deployed.players[2].troops_supply == 0


def test_a_defender_with_supply_troops_is_not_offered_a_return() -> None:
    engine = UprisingRulesEngine()
    state = _controlled_round_start(troops_supply=3, specimens=2)

    assert _ids(engine.legal_actions(state, 2)) == [
        "decline_control_defense",
        "deploy_control_defense",
    ]


def test_a_defender_whose_supply_emptied_meanwhile_may_return_a_specimen() -> None:
    # An effect in the same step (an Earn Any Alliance completion) can empty
    # the supply after the frame opened; a specimen still covers the troop.
    engine = UprisingRulesEngine()
    state = _controlled_round_start(troops_supply=1, specimens=1)
    defender = state.players[2]
    emptied = replace(
        defender,
        troops_supply=0,
        troops_garrison=defender.troops_garrison + 1,
    )
    state = replace(state, players=(*state.players[:2], emptied, state.players[3]))

    assert _ids(engine.legal_actions(state, 2)) == [
        "decline_control_defense",
        "return_specimen",
    ]


def test_no_defense_opens_without_a_troop_or_a_specimen() -> None:
    state = _controlled_round_start(troops_supply=0, specimens=0)

    assert all(
        frame.kind != FrameKind.CONTROL_DEFENSE for frame in state.decision_stack
    )


def _combat_intrigue(config: RulesetConfig = IMMORTALITY) -> GameState:
    players = tuple(
        PlayerState(
            player_id=player,
            troops_supply=4,
            troops_garrison=(4 if config.immortality else 6)
            if player in (0, 1)
            else 8,
            troops_conflict=2 if player in (0, 1) else 0,
            specimens=2 if player in (0, 1) and config.immortality else 0,
        )
        for player in range(4)
    )
    state = GameState(
        config=config,
        seed=1,
        phase=GamePhase.COMBAT,
        round_number=1,
        first_player=0,
        players=players,
    )
    return begin_combat_intrigue(state).state


def test_the_seat_with_combat_intrigue_priority_may_return_a_specimen() -> None:
    engine = UprisingRulesEngine()
    state = _combat_intrigue()
    decision = state.decision_stack[-1].decision
    assert isinstance(decision, PlayerDecision) and decision.owner == 0

    actions = engine.legal_actions(state, 0)
    assert {"pass_combat_intrigue", "return_specimen"} <= set(_ids(actions))
    # Only the seat holding priority.
    assert legal_specimen_return_actions(state, 1) == ()

    (returned,) = legal_specimen_return_actions(state, 0)
    after = engine.apply(state, returned).state

    assert after.players[0].specimens == 1
    assert after.players[0].troops_supply == 5
    # Priority stays with the seat; the return is not a pass.
    assert after.decision_stack[-1] == state.decision_stack[-1]


def test_combat_intrigue_offers_no_return_without_immortality() -> None:
    state = _combat_intrigue(RulesetConfig())

    assert legal_specimen_return_actions(state, 0) == ()
