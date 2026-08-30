"""Tests for the OQ-007 six-Leader public draft (project convention)."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.leaders import LEADERS_BY_ID, leaders_for_choam
from dune_imperium.core import DomainAction, GamePhase, PlayerDecision
from dune_imperium.core.engine import IllegalActionError
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.engine import DEFAULT_LEADER_IDS
from dune_imperium.rules.leader_draft import draft_pick_order, remaining_draft_pool
from dune_imperium.rules.setup import create_draft_initial_state


def _pick(actor: int, leader_id: str) -> DomainAction:
    return DomainAction(
        action_id="pick_leader",
        actor=actor,
        arguments=(("leader_id", leader_id),),
    )


def _draft_reset(
    engine: UprisingRulesEngine,
    *,
    seed: int,
    choam_module: bool = False,
) -> GameState:
    return engine.reset(
        RulesetConfig(choam_module=choam_module, leader_draft=True), seed
    )


def _seed_with_pool_member(leader_id: str, *, choam_module: bool) -> int:
    engine = UprisingRulesEngine()
    for seed in range(64):
        state = _draft_reset(engine, seed=seed, choam_module=choam_module)
        if leader_id in state.leader_draft_pool:
            return seed
    raise AssertionError(f"no scanned seed put {leader_id} into the pool")


def test_draft_reset_pauses_on_a_public_six_leader_pool() -> None:
    engine = UprisingRulesEngine()
    state = _draft_reset(engine, seed=5)

    assert state.phase is GamePhase.SETUP
    assert len(state.leader_draft_pool) == 6
    assert len(set(state.leader_draft_pool)) == 6
    legal_ids = {leader.leader_id for leader in leaders_for_choam(False)}
    assert set(state.leader_draft_pool) <= legal_ids
    assert all(player.leader_id is None for player in state.players)
    assert state.first_player is not None

    frame = state.decision_stack[-1]
    assert frame.kind == "leader_draft"
    assert isinstance(frame.decision, PlayerDecision)
    assert frame.decision.owner == (state.first_player + 3) % 4

    offered = engine.legal_actions(state, frame.decision.owner)
    assert {a.action_id for a in offered} == {"pick_leader"}
    assert {dict(a.arguments)["leader_id"] for a in offered} == set(
        state.leader_draft_pool
    )


def test_same_seed_reproduces_the_same_pool() -> None:
    engine = UprisingRulesEngine()
    first = _draft_reset(engine, seed=9)
    second = _draft_reset(engine, seed=9)

    assert first.leader_draft_pool == second.leader_draft_pool
    assert first.first_player == second.first_player


def test_picks_run_in_reverse_turn_order_and_finish_setup() -> None:
    engine = UprisingRulesEngine()
    state = _draft_reset(engine, seed=5)
    assert state.first_player is not None
    order = draft_pick_order(state.first_player, 4)
    assert order[-1] == state.first_player

    picked: dict[int, str] = {}
    for expected_owner in order:
        frame = state.decision_stack[-1]
        assert isinstance(frame.decision, PlayerDecision)
        assert frame.decision.owner == expected_owner
        choice = remaining_draft_pool(state)[0]
        picked[expected_owner] = choice
        state = engine.apply(state, _pick(expected_owner, choice)).state

    # The last pick hands off through Round Start into round 1.
    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.round_number == 1
    for seat, leader_id in picked.items():
        definition = LEADERS_BY_ID[leader_id]
        assert state.players[seat].leader_id == leader_id
        assert state.players[seat].leader_face_id == (
            definition.setup_face_id or leader_id
        )
    unused = set(state.leader_draft_pool) - set(picked.values())
    assert len(unused) == 2


def test_a_taken_leader_cannot_be_picked_again() -> None:
    engine = UprisingRulesEngine()
    state = _draft_reset(engine, seed=5)
    assert state.first_player is not None
    order = draft_pick_order(state.first_player, 4)
    taken = state.leader_draft_pool[0]

    state = engine.apply(state, _pick(order[0], taken)).state
    offered = engine.legal_actions(state, order[1])
    assert taken not in {dict(a.arguments)["leader_id"] for a in offered}
    with pytest.raises(IllegalActionError):
        engine.apply(state, _pick(order[1], taken))
    # Only the seat holding the pick may act.
    assert engine.legal_actions(state, order[0]) == ()


def test_picking_staban_removes_diplomacy_from_the_shuffled_deck() -> None:
    seed = _seed_with_pool_member("staban_tuek", choam_module=False)
    engine = UprisingRulesEngine()
    state = _draft_reset(engine, seed=seed)
    assert state.first_player is not None
    picker = draft_pick_order(state.first_player, 4)[0]
    before = state.players[picker].deck
    assert any(":diplomacy:" in instance_id for instance_id in before)

    state = engine.apply(state, _pick(picker, "staban_tuek")).state
    after = state.players[picker].deck

    assert not any(":diplomacy:" in instance_id for instance_id in after)
    # Filtering keeps the pre-shuffled order of every remaining card.
    assert after == tuple(
        instance_id for instance_id in before if ":diplomacy:" not in instance_id
    )


def test_picking_shaddam_sets_the_sardaukar_contracts_aside() -> None:
    seed = _seed_with_pool_member("shaddam_corrino_iv", choam_module=True)
    engine = UprisingRulesEngine()
    state = _draft_reset(engine, seed=seed, choam_module=True)
    assert state.first_player is not None
    # The Contract market waits until the picks decide the set-aside.
    assert len(state.contract_bank) == 20
    assert state.face_up_contract_ids == ()

    order = draft_pick_order(state.first_player, 4)
    state = engine.apply(state, _pick(order[0], "shaddam_corrino_iv")).state
    for owner in order[1:]:
        choice = remaining_draft_pool(state)[0]
        state = engine.apply(state, _pick(owner, choice)).state

    assert state.sardaukar_contract_ids == (
        "contract:sardaukar_i",
        "contract:sardaukar_ii",
    )
    assert len(state.face_up_contract_ids) == 2
    assert len(state.contract_bank) == 16
    assert not set(state.sardaukar_contract_ids) & (
        set(state.contract_bank) | set(state.face_up_contract_ids)
    )


def test_a_draft_without_shaddam_deals_the_full_contract_market() -> None:
    engine = UprisingRulesEngine()
    for seed in range(64):
        state = _draft_reset(engine, seed=seed, choam_module=True)
        if "shaddam_corrino_iv" not in state.leader_draft_pool:
            break
    else:
        raise AssertionError("no scanned seed kept Shaddam out of the pool")
    assert state.first_player is not None

    for owner in draft_pick_order(state.first_player, 4):
        choice = remaining_draft_pool(state)[0]
        state = engine.apply(state, _pick(owner, choice)).state

    assert state.sardaukar_contract_ids == ()
    assert len(state.face_up_contract_ids) == 2
    assert len(state.contract_bank) == 18


def test_the_draft_constructor_requires_the_ruleset_option() -> None:
    with pytest.raises(ValueError, match="leader_draft option"):
        create_draft_initial_state(RulesetConfig(), seed=1)


def test_fixed_leader_setup_is_unchanged_without_the_option() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), 5)

    assert state.phase is GamePhase.PLAYER_TURNS
    assert state.leader_draft_pool == ()
    assert tuple(player.leader_id for player in state.players) == DEFAULT_LEADER_IDS
