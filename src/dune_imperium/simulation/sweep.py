"""Large-scale random full-game verification sweeps for M7.

``run_checked_game`` plays one seeded random game to ``FINISHED`` while
checking, after every transition, the global card-conservation invariants
and, at sampled player decisions, the observation-privacy invariant. It
also detects deadlocks (a pending player decision with no legal action or
a game that never finishes) and verifies the recorded replay.
``run_sweep`` fans a seed range out over worker processes and aggregates
one report, which the ``dune-imperium-sweep`` CLI prints.
"""

import time
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from dune_imperium.agents import RandomAgent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.replay import GameReplay, ReplayStep, replay_game
from dune_imperium.core.state import GamePhase, canonical_state_hash
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.endgame import final_standings
from dune_imperium.simulation.invariants import (
    CardCensus,
    InvariantViolation,
    check_observation_privacy,
    check_state_invariants,
)


@dataclass(frozen=True, slots=True)
class GameCheckReport:
    """One finished, invariant-checked random game."""

    ruleset: str
    game_seed: int
    policy_seed: int
    steps: int
    rounds: int
    winner: int


@dataclass(frozen=True, slots=True)
class SweepFailure:
    """One game that violated an invariant or crashed."""

    ruleset: str
    game_seed: int
    policy_seed: int
    error: str


@dataclass(frozen=True, slots=True)
class SweepReport:
    """Aggregated result of one verification sweep."""

    games: tuple[GameCheckReport, ...]
    failures: tuple[SweepFailure, ...]
    duration_seconds: float

    @property
    def total_steps(self) -> int:
        return sum(game.steps for game in self.games)


def run_checked_game(
    config: RulesetConfig,
    game_seed: int,
    policy_seed: int,
    *,
    max_steps: int = 30_000,
    privacy_interval: int = 25,
    verify_replay: bool = True,
) -> GameCheckReport:
    """Play one random game to FINISHED under every invariant check."""

    if max_steps < 1:
        raise ValueError("max_steps must be positive")
    if privacy_interval < 0:
        raise ValueError("privacy_interval must not be negative")

    engine = UprisingRulesEngine()
    state = engine.reset(config, game_seed)
    census = CardCensus.from_state(state)
    check_state_invariants(state, census)
    if privacy_interval:
        check_observation_privacy(state)

    agents = tuple(
        RandomAgent(seed=policy_seed + player) for player in range(config.players)
    )
    chance = ChanceResolver(seed=game_seed)
    steps: list[ReplayStep] = []
    player_decisions = 0

    for _ in range(max_steps):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if decision is None:
            raise InvariantViolation("an unfinished game has no pending decision")
        if isinstance(decision, ChanceDecision):
            outcome = chance.resolve(decision)
            steps.append(outcome)
            state = engine.apply(state, outcome).state
        else:
            if not isinstance(decision, PlayerDecision):
                raise InvariantViolation(f"unknown decision type: {decision!r}")
            actions = engine.legal_actions(state, decision.owner)
            if not actions:
                raise InvariantViolation(
                    f"deadlock: player {decision.owner} has no legal action"
                )
            if privacy_interval and player_decisions % privacy_interval == 0:
                check_observation_privacy(state)
            player_decisions += 1
            observation = engine.observe(state, decision.owner)
            action = agents[decision.owner].choose_action(observation, actions)
            steps.append(action)
            state = engine.apply(state, action).state
        try:
            check_state_invariants(state, census)
        except InvariantViolation as violation:
            raise InvariantViolation(
                f"after step {len(steps)}: {violation}"
            ) from None
    else:
        raise InvariantViolation(f"the game exceeded the {max_steps}-step limit")

    if privacy_interval:
        check_observation_privacy(state)
    standings = final_standings(state)
    if verify_replay:
        replay_game(
            engine,
            GameReplay(
                ruleset=config,
                seed=game_seed,
                steps=tuple(steps),
                expected_state_hash=canonical_state_hash(state),
            ),
        )
    return GameCheckReport(
        ruleset=config.identifier,
        game_seed=game_seed,
        policy_seed=policy_seed,
        steps=len(steps),
        rounds=state.round_number,
        winner=standings[0].player,
    )


@dataclass(frozen=True, slots=True)
class _GameSpec:
    choam_module: bool
    game_seed: int
    policy_seed: int
    max_steps: int
    privacy_interval: int
    verify_replay: bool


def _run_spec(spec: _GameSpec) -> GameCheckReport | SweepFailure:
    config = RulesetConfig(choam_module=spec.choam_module)
    try:
        return run_checked_game(
            config,
            spec.game_seed,
            spec.policy_seed,
            max_steps=spec.max_steps,
            privacy_interval=spec.privacy_interval,
            verify_replay=spec.verify_replay,
        )
    except Exception as error:  # noqa: BLE001 - every failure belongs in the report
        return SweepFailure(
            ruleset=config.identifier,
            game_seed=spec.game_seed,
            policy_seed=spec.policy_seed,
            error=f"{type(error).__name__}: {error}",
        )


def run_sweep(
    specs: Iterable[_GameSpec],
    *,
    workers: int = 0,
) -> SweepReport:
    """Run every game spec, optionally across worker processes."""

    started = time.perf_counter()
    spec_list = list(specs)
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_run_spec, spec_list, chunksize=4))
    else:
        results = [_run_spec(spec) for spec in spec_list]
    games = tuple(result for result in results if isinstance(result, GameCheckReport))
    failures = tuple(result for result in results if isinstance(result, SweepFailure))
    return SweepReport(
        games=games,
        failures=failures,
        duration_seconds=time.perf_counter() - started,
    )


def sweep_specs(
    *,
    games: int,
    rulesets: tuple[bool, ...],
    start_seed: int,
    policy_offset: int = 700_000,
    max_steps: int = 30_000,
    privacy_interval: int = 25,
    verify_replay: bool = True,
) -> tuple[_GameSpec, ...]:
    """Build the seeded per-game specs for a sweep."""

    if games < 1:
        raise ValueError("a sweep needs at least one game")
    return tuple(
        _GameSpec(
            choam_module=choam_module,
            game_seed=seed,
            policy_seed=policy_offset + seed,
            max_steps=max_steps,
            privacy_interval=privacy_interval,
            verify_replay=verify_replay,
        )
        for choam_module in rulesets
        for seed in range(start_seed, start_seed + games)
    )
