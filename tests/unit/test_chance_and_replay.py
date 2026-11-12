"""Tests for explicit chance outcomes and deterministic replay."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import (
    ChanceDecision,
    ChanceOutcome,
    ChanceReplayError,
    ChanceResolver,
    DecisionFrame,
    DomainAction,
    GameEvent,
    GameReplay,
    GameState,
    IllegalActionError,
    PlayerDecision,
    PlayerView,
    ReplayMismatchError,
    RuleResult,
    RulesEngine,
    canonical_state_hash,
    replay_game,
)


class ObjectiveThenPassEngine(RulesEngine):
    """Tiny chance-to-player flow used as an engine contract fixture."""

    verify_input_immutability = True

    def _initial_state(self, config: RulesetConfig, seed: int) -> GameState:
        frame = DecisionFrame(
            kind="setup_chance",
            frame_id="choose_objectives",
            decision=ChanceDecision(
                decision_id="setup:objectives",
                prompt="Choose two objectives in order",
                options=("objective:a", "objective:b", "objective:c"),
                count=2,
            ),
        )
        return GameState(config=config, seed=seed, decision_stack=(frame,))

    def legal_actions(
        self,
        state: GameState,
        player: int,
    ) -> tuple[DomainAction, ...]:
        decision = self.current_decision(state)
        if isinstance(decision, PlayerDecision) and decision.owner == player:
            return (DomainAction("pass", actor=player),)
        return ()

    def _apply_legal(self, state: GameState, action: DomainAction) -> RuleResult:
        event = GameEvent(
            event_id="player:pass",
            kind="player_passed",
            payload=(("player", action.actor),),
        )
        return RuleResult(state=state.pop_decision(), events=(event,))

    def _apply_chance(self, state: GameState, outcome: ChanceOutcome) -> RuleResult:
        next_state = state.pop_decision().push_decision(
            DecisionFrame(
                kind="pass",
                frame_id="player_pass",
                decision=PlayerDecision(owner=0, prompt="Pass"),
            )
        )
        event = GameEvent(
            event_id="setup:objectives",
            kind="objectives_selected",
            payload=(("first", outcome.values[0]), ("second", outcome.values[1])),
        )
        return RuleResult(state=next_state, events=(event,))

    def observe(self, state: GameState, player: int) -> PlayerView:
        return PlayerView(player=player, revision=state.revision, phase=state.phase)


def test_seeded_chance_is_repeatable_and_records_the_actual_outcome() -> None:
    decision = ChanceDecision(
        decision_id="shuffle:test",
        prompt="Shuffle",
        options=("a", "b", "c", "d"),
        count=4,
    )

    first = ChanceResolver(seed=42)
    second = ChanceResolver(seed=42)

    assert first.resolve(decision) == second.resolve(decision)
    assert first.outcomes == second.outcomes
    assert set(first.outcomes[0].values) == set(decision.options)


def test_recorded_chance_is_injected_without_using_the_original_rng() -> None:
    decision = ChanceDecision(
        decision_id="draw:test",
        prompt="Draw",
        options=("a", "b"),
    )
    recorded = (ChanceOutcome("draw:test", ("b",)),)
    resolver = ChanceResolver(seed=999, recorded=recorded)

    assert resolver.resolve(decision) == recorded[0]
    assert resolver.exhausted is True


def test_recorded_chance_must_match_the_current_decision() -> None:
    decision = ChanceDecision(
        decision_id="draw:test",
        prompt="Draw",
        options=("a", "b"),
    )
    resolver = ChanceResolver(
        seed=0,
        recorded=(ChanceOutcome("different", ("a",)),),
    )

    with pytest.raises(ChanceReplayError, match="does not match"):
        resolver.resolve(decision)


def test_engine_rejects_invalid_chance_without_changing_state() -> None:
    engine = ObjectiveThenPassEngine()
    state = engine.reset(RulesetConfig(), seed=5)
    before = canonical_state_hash(state)

    with pytest.raises(IllegalActionError, match="unavailable"):
        engine.apply(
            state,
            ChanceOutcome("setup:objectives", ("objective:a", "unknown")),
        )

    assert canonical_state_hash(state) == before


def test_action_and_chance_stream_replays_to_the_same_state() -> None:
    engine = ObjectiveThenPassEngine()
    state = engine.reset(RulesetConfig(), seed=123)
    decision = engine.current_decision(state)
    assert isinstance(decision, ChanceDecision)

    chance = ChanceResolver(seed=123).resolve(decision)
    state = engine.apply(state, chance).state
    action = engine.legal_actions(state, 0)[0]
    state = engine.apply(state, action).state

    replay = GameReplay(
        ruleset=RulesetConfig(),
        seed=123,
        steps=(chance, action),
        expected_state_hash=canonical_state_hash(state),
    )

    assert replay_game(engine, replay) == state


def test_replay_detects_a_different_final_state() -> None:
    engine = ObjectiveThenPassEngine()
    replay = GameReplay(
        ruleset=RulesetConfig(),
        seed=123,
        steps=(
            ChanceOutcome(
                "setup:objectives",
                ("objective:a", "objective:b"),
            ),
            DomainAction("pass", actor=0),
        ),
        expected_state_hash="0" * 64,
    )

    with pytest.raises(ReplayMismatchError, match="final state hash differs"):
        replay_game(engine, replay)
