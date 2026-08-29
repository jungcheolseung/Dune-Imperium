"""Tests for implemented Leader abilities and Signet Ring resolution."""


import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.core.engine import RuleResult
from dune_imperium.rules.agent_effects import resolve_agent_card_effect
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.leader_abilities import (
    apply_leader_reveal_action,
    grant_leader_reveal_passives,
    legal_leader_reveal_actions,
)
from dune_imperium.rules.reveal_turn import begin_reveal_turn


def _signet_instance(player: int = 0) -> str:
    return f"player:{player}:starter:signet_ring:0"


def _turn_state(owner: PlayerState) -> GameState:
    return GameState(
        config=RulesetConfig(),
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


def _signet_action_to(state: GameState, space_id: str) -> DomainAction:
    return next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == space_id
        and dict(action.arguments)["card_id"] == _signet_instance()
    )


def test_warmaster_signet_recruits_one_deployable_troop() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)
    resolved = result.state.players[0]
    context = dict(result.state.decision_stack[-1].context)

    # Warmaster recruits one troop [Gurney Halleck card]; a troop recruited on
    # a Combat-space turn may still deploy [FAQ p. 4], so it joins the frame's
    # recruit count alongside the board recruits.
    assert resolved.troops_garrison == owner.troops_garrison + 1
    assert resolved.troops_supply == owner.troops_supply - 1
    assert context["troops_recruited"] == 1
    assert context["pending_agent_effect"] is False
    assert result.events[0].kind == "leader_signet_resolved"
    assert dict(result.events[0].payload)["troops"] == 1


def test_warmaster_signet_recruits_nothing_from_an_empty_supply() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=(_signet_instance(),),
        troops_supply=0,
        troops_garrison=12,
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)

    assert result.state.players[0].troops_garrison == 12
    assert dict(result.events[0].payload)["troops"] == 0


def test_fill_coffers_signet_gains_solari_only_without_an_alliance() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)
    resources = result.state.players[0].resources

    assert resources.solari == 1
    assert resources.spice == 0
    assert dict(result.events[0].payload)["spice"] == 0


def test_fill_coffers_signet_adds_spice_while_holding_an_alliance() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=(_signet_instance(),),
        alliance_faction_ids=("fremen",),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    result = resolve_agent_card_effect(placed)
    resources = result.state.players[0].resources

    # Fill Coffers: one Solari, and one Spice with an Alliance [Lady Amber
    # Metulli card].
    assert resources.solari == 1
    assert resources.spice == 1


def test_signet_ring_stays_withheld_for_an_unimplemented_leader() -> None:
    engine = UprisingRulesEngine()
    implemented = _turn_state(
        PlayerState(
            player_id=0,
            leader_id="gurney_halleck",
            hand=(_signet_instance(),),
        )
    )
    unimplemented = _turn_state(
        PlayerState(
            player_id=0,
            leader_id="muad_dib",
            hand=(_signet_instance(),),
        )
    )

    assert any(
        dict(action.arguments).get("card_id") == _signet_instance()
        for action in engine.legal_actions(implemented, 0)
    )
    assert not any(
        dict(action.arguments).get("card_id") == _signet_instance()
        for action in engine.legal_actions(unimplemented, 0)
    )


def test_unimplemented_leader_signet_resolution_is_rejected() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="muad_dib",
        hand=(_signet_instance(),),
    )
    state = _turn_state(owner)
    placed = apply_agent_action(state, _signet_action_to(state, "arrakeen")).state

    with pytest.raises(RuntimeError, match="not implemented"):
        resolve_agent_card_effect(placed)


def _reveal_state(owner: PlayerState) -> GameState:
    return begin_reveal_turn(
        _turn_state(owner),
        DomainAction(action_id="reveal_turn", actor=0),
    ).state


def test_desert_scouts_retreats_one_troop_during_the_reveal_turn() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=("player:0:starter:dagger:0",),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)
    context = dict(revealed.decision_stack[-1].context)
    assert context["strength"] == 2 * 2 + 1

    (action,) = legal_leader_reveal_actions(revealed, 0)
    assert action.action_id == "retreat_leader_troop"
    result = apply_leader_reveal_action(revealed, action)
    resolved = result.state.players[0]
    next_context = dict(result.state.decision_stack[-1].context)

    # Desert Scouts retreats one troop to the garrison [Lady Amber Metulli
    # card] [Main p. 20]; with a unit still in the Conflict only that troop's
    # two strength leaves the total.
    assert resolved.troops_conflict == 1
    assert resolved.troops_garrison == 4
    assert resolved.combat_strength == 3
    assert next_context["strength"] == 3
    assert next_context["leader_reveal_ability_used"] is True
    assert legal_leader_reveal_actions(result.state, 0) == ()


def test_desert_scouts_retreating_the_last_unit_zeroes_the_strength() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=("player:0:starter:dagger:0",),
        troops_supply=8,
        troops_garrison=3,
        troops_conflict=1,
    )
    revealed = _reveal_state(owner)

    (action,) = legal_leader_reveal_actions(revealed, 0)
    result = apply_leader_reveal_action(revealed, action)

    assert result.state.players[0].troops_conflict == 0
    assert result.state.players[0].combat_strength == 0
    assert dict(result.state.decision_stack[-1].context)["strength"] == 0


def test_desert_scouts_is_not_offered_without_conflict_troops() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="lady_amber_metulli",
        hand=("player:0:starter:dagger:0",),
    )
    revealed = _reveal_state(owner)

    assert legal_leader_reveal_actions(revealed, 0) == ()


def test_desert_scouts_is_not_offered_to_other_leaders() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0",),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)

    assert legal_leader_reveal_actions(revealed, 0) == ()


def test_always_smiling_grants_persuasion_at_six_strength() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0", "player:0:starter:dagger:1"),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)
    assert dict(revealed.decision_stack[-1].context)["strength"] == 6

    result = grant_leader_reveal_passives(RuleResult(state=revealed))
    context = dict(result.state.decision_stack[-1].context)

    # Always Smiling: six or more strength during the Reveal turn grants one
    # Persuasion in the four-player game [Gurney Halleck card].
    assert context["persuasion"] == 1
    assert context["leader_persuasion_granted"] is True
    assert result.events[-1].kind == "reveal_persuasion_gained"


def test_always_smiling_stays_quiet_below_six_strength() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0",),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)
    assert dict(revealed.decision_stack[-1].context)["strength"] == 5

    result = grant_leader_reveal_passives(RuleResult(state=revealed))

    assert result.state is revealed
    assert dict(result.state.decision_stack[-1].context)["persuasion"] == 0


def test_always_smiling_does_not_grant_twice() -> None:
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0", "player:0:starter:dagger:1"),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    revealed = _reveal_state(owner)

    first = grant_leader_reveal_passives(RuleResult(state=revealed))
    second = grant_leader_reveal_passives(RuleResult(state=first.state))

    assert second.state is first.state
    assert dict(second.state.decision_stack[-1].context)["persuasion"] == 1


def test_always_smiling_is_wired_through_the_engine_reveal() -> None:
    engine = UprisingRulesEngine()
    owner = PlayerState(
        player_id=0,
        leader_id="gurney_halleck",
        hand=("player:0:starter:dagger:0", "player:0:starter:dagger:1"),
        troops_supply=7,
        troops_garrison=3,
        troops_conflict=2,
    )
    state = _turn_state(owner)

    transition = engine.apply(state, DomainAction(action_id="reveal_turn", actor=0))
    context = dict(transition.state.decision_stack[-1].context)

    assert context["persuasion"] == 1
    assert context["leader_persuasion_granted"] is True
