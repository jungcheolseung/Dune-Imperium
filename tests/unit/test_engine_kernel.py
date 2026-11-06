"""Contract tests for the rules-engine kernel."""

from dataclasses import replace

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GameEvent,
    GamePhase,
    GameState,
    IllegalActionError,
    PlayerDecision,
    PlayerView,
    RuleResult,
    RulesEngine,
    canonical_state_hash,
)


class PassAroundEngine(RulesEngine):
    """Small deterministic rule system used to verify kernel behavior."""

    verify_input_immutability = True

    def _initial_state(self, config: RulesetConfig, seed: int) -> GameState:
        frame = DecisionFrame(
            kind="pass",
            frame_id="pass:0",
            decision=PlayerDecision(owner=0, prompt="Pass once"),
        )
        return GameState(config=config, seed=seed, decision_stack=(frame,))

    def legal_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        decision = self.current_decision(state)
        if not isinstance(decision, PlayerDecision) or decision.owner != player:
            return ()
        return (DomainAction(action_id="pass", actor=player),)

    def _apply_legal(self, state: GameState, action: DomainAction) -> RuleResult:
        next_state = state.pop_decision()
        next_player = state.revision + 1
        if next_player < state.config.players:
            next_state = next_state.push_decision(
                DecisionFrame(
                    kind="pass",
                    frame_id=f"pass:{next_player}",
                    decision=PlayerDecision(
                        owner=next_player,
                        prompt="Pass once",
                    ),
                )
            )
        event = GameEvent(
            event_id=f"pass:{state.revision}",
            kind="player_passed",
            payload=(("player", action.actor),),
        )
        return RuleResult(state=next_state, events=(event,))

    def observe(self, state: GameState, player: int) -> PlayerView:
        return PlayerView(
            player=player,
            revision=state.revision,
            phase=state.phase,
            public_data=(("pending_decisions", len(state.decision_stack)),),
        )


def play_pass_round(engine: PassAroundEngine, seed: int) -> GameState:
    state = engine.reset(RulesetConfig(), seed)
    for player in range(4):
        action = engine.legal_actions(state, player)[0]
        state = engine.apply(state, action).state
    return state


def test_same_seed_and_actions_produce_same_canonical_state() -> None:
    engine = PassAroundEngine()

    first = play_pass_round(engine, seed=1234)
    second = play_pass_round(engine, seed=1234)

    assert canonical_state_hash(first) == canonical_state_hash(second)
    assert first.revision == 4
    assert len(first.event_log) == 4
    assert engine.current_decision(first) is None


def test_illegal_action_is_rejected_without_changing_state() -> None:
    engine = PassAroundEngine()
    state = engine.reset(RulesetConfig(), seed=7)
    before = canonical_state_hash(state)

    with pytest.raises(IllegalActionError, match="does not own"):
        engine.apply(state, DomainAction(action_id="pass", actor=1))

    assert canonical_state_hash(state) == before
    assert state.revision == 0


def test_unlisted_action_is_rejected() -> None:
    engine = PassAroundEngine()
    state = engine.reset(RulesetConfig(), seed=7)

    with pytest.raises(IllegalActionError, match="not legal"):
        engine.apply(state, DomainAction(action_id="invented", actor=0))


def test_observe_is_deterministic_and_does_not_mutate_state() -> None:
    engine = PassAroundEngine()
    state = engine.reset(RulesetConfig(), seed=9)
    before = canonical_state_hash(state)

    assert engine.observe(state, 0) == engine.observe(state, 0)
    assert canonical_state_hash(state) == before


def test_clone_is_equal_but_not_identical() -> None:
    engine = PassAroundEngine()
    state = engine.reset(RulesetConfig(), seed=11)

    clone = engine.clone_full(state)

    assert clone == state
    assert clone is not state


def test_only_finished_phase_is_terminal() -> None:
    engine = PassAroundEngine()
    state = engine.reset(RulesetConfig(), seed=11)

    assert engine.is_terminal(state) is False
    assert engine.is_terminal(replace(state, phase=GamePhase.FINISHED)) is True


def test_rules_cannot_change_revision_directly() -> None:
    class BrokenEngine(PassAroundEngine):
        def _apply_legal(self, state: GameState, action: DomainAction) -> RuleResult:
            return RuleResult(state=replace(state, revision=99))

    engine = BrokenEngine()
    state = engine.reset(RulesetConfig(), seed=1)

    with pytest.raises(RuntimeError, match="revision updates"):
        engine.apply(state, engine.legal_actions(state, 0)[0])


class CountingEngine(PassAroundEngine):
    """Count how often the kernel asks for the legal set."""

    enumerations = 0

    def legal_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        type(self).enumerations += 1
        return super().legal_actions(state, player)


def test_a_vouched_legal_set_replaces_the_second_enumeration() -> None:
    # A runner has just enumerated the legal set of this state so an agent
    # could choose; handing it back makes the legality check a membership
    # test instead of a second enumeration (throughput report 2026-09-10,
    # section 5, item 2).
    engine = CountingEngine()
    CountingEngine.enumerations = 0
    state = engine.reset(RulesetConfig(), seed=1)
    legal = engine.legal_actions(state, 0)
    assert CountingEngine.enumerations == 1

    vouched = engine.apply(state, legal[0], legal_actions=legal)

    assert CountingEngine.enumerations == 1
    checked = engine.apply(state, legal[0])
    assert CountingEngine.enumerations == 2
    assert vouched.state == checked.state
    assert vouched.events == checked.events


def test_a_vouched_legal_set_is_trusted_only_as_the_set() -> None:
    engine = PassAroundEngine()
    state = engine.reset(RulesetConfig(), seed=1)
    legal = engine.legal_actions(state, 0)

    # The owner check still runs before the membership test.
    foreign = DomainAction(action_id="pass", actor=1)
    with pytest.raises(IllegalActionError):
        engine.apply(state, foreign, legal_actions=(foreign,))
    # A legal action outside the vouched tuple is rejected: the tuple is the
    # set, not a hint.
    with pytest.raises(IllegalActionError):
        engine.apply(state, legal[0], legal_actions=())

