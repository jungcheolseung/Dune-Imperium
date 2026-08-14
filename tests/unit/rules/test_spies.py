"""Tests for Spy decisions around Agent placement."""

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.spies import (
    apply_gather_intelligence_action,
    legal_gather_intelligence_actions,
)

ASSEMBLY_POST = "landsraad-assembly-hall-gather-support"


def _instance(card_id: str) -> str:
    return next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if f":{card_id}:" in instance_id
    )


def _placed_state() -> tuple[GameState, str]:
    dagger = _instance("dagger")
    drawn = _instance("diplomacy")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        deck=(drawn,),
        spies_supply=2,
        spy_post_ids=(ASSEMBLY_POST,),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    action = next(
        candidate
        for candidate in legal_agent_actions(state, 0)
        if dict(candidate.arguments)["space_id"] == "assembly_hall"
    )
    return apply_agent_action(state, action).state, drawn


def test_gather_intelligence_recall_draws_before_other_agent_effects() -> None:
    state, drawn = _placed_state()
    engine_actions = UprisingRulesEngine().legal_actions(state, 0)

    assert {action.action_id for action in engine_actions} == {
        "decline_gather_intelligence",
        "gather_intelligence",
    }
    gather = next(
        action for action in engine_actions if action.action_id == "gather_intelligence"
    )
    result = apply_gather_intelligence_action(state, gather)
    owner = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    assert owner.hand == (drawn,)
    assert owner.deck == ()
    assert owner.spies_supply == 3
    assert owner.spy_post_ids == ()
    assert context["pending_gather_intelligence"] is False
    assert context["pending_board_effect"] is True
    assert result.events[0].kind == "gather_intelligence"


def test_gather_intelligence_can_be_declined_without_recalling_spy() -> None:
    state, _ = _placed_state()
    decline = next(
        action
        for action in legal_gather_intelligence_actions(state, 0)
        if action.action_id == "decline_gather_intelligence"
    )

    result = apply_gather_intelligence_action(state, decline)

    assert result.state.players[0].spies_supply == 2
    assert result.state.players[0].spy_post_ids == (ASSEMBLY_POST,)
    assert dict(result.state.decision_stack[-1].context)[
        "pending_gather_intelligence"
    ] is False
    assert result.events == ()


def test_unconnected_spy_does_not_open_gather_intelligence_window() -> None:
    dagger = _instance("dagger")
    owner = PlayerState(
        player_id=0,
        hand=(dagger,),
        spies_supply=2,
        spy_post_ids=("arrakis-deep-desert",),
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        players=(owner, *(PlayerState(player_id=seat) for seat in range(1, 4))),
        decision_stack=(
            DecisionFrame(
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    action = next(
        candidate
        for candidate in legal_agent_actions(state, 0)
        if dict(candidate.arguments)["space_id"] == "assembly_hall"
    )
    state = apply_agent_action(state, action).state

    assert legal_gather_intelligence_actions(state, 0) == ()
