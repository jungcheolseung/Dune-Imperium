"""Headless runners built on the public rules-engine contract."""

from collections.abc import Sequence
from dataclasses import dataclass

from dune_imperium.agents import Agent, RandomAgent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RulesEngine
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash
from dune_imperium.rules.endgame import FinalStanding, final_standings


@dataclass(frozen=True, slots=True)
class RoundSimulation:
    """Final state and replay record produced by a one-round simulation."""

    state: GameState
    replay: GameReplay


@dataclass(frozen=True, slots=True)
class GameSimulation:
    """Final state, official standings, and replay record of one full game."""

    state: GameState
    standings: tuple[FinalStanding, ...]
    replay: GameReplay


def run_random_round(
    engine: RulesEngine,
    config: RulesetConfig,
    game_seed: int,
    policy_seed: int,
    *,
    max_steps: int = 500,
) -> RoundSimulation:
    """Run four independently seeded random agents through one complete round."""

    if policy_seed < 0:
        raise ValueError("policy seed must not be negative")
    if max_steps < 1:
        raise ValueError("max_steps must be positive")

    agents = tuple(
        RandomAgent(seed=policy_seed + player) for player in range(config.players)
    )
    state = engine.reset(config, game_seed)
    started_round = state.round_number
    chance = ChanceResolver(seed=game_seed)
    steps: list[ReplayStep] = []

    for _ in range(max_steps):
        if _round_finished(state, started_round):
            return RoundSimulation(
                state=state,
                replay=_replay_record(config, game_seed, steps, state),
            )
        state = _advance_one_decision(engine, state, agents, chance, steps)

    raise RuntimeError(f"one round exceeded the {max_steps}-action limit")


def run_random_game(
    engine: RulesEngine,
    config: RulesetConfig,
    game_seed: int,
    policy_seed: int,
    *,
    max_steps: int = 30_000,
) -> GameSimulation:
    """Run four independently seeded random agents to a `FINISHED` game.

    Chance decisions such as deck reshuffles resolve through a
    ``ChanceResolver`` seeded with ``game_seed``, so one seed pair reproduces
    the entire game, and the returned replay re-derives the same final state.
    """

    if policy_seed < 0:
        raise ValueError("policy seed must not be negative")
    agents = tuple(
        RandomAgent(seed=policy_seed + player) for player in range(config.players)
    )
    return run_policy_game(engine, config, game_seed, agents, max_steps=max_steps)


def run_policy_game(
    engine: RulesEngine,
    config: RulesetConfig,
    game_seed: int,
    agents: Sequence[Agent],
    *,
    max_steps: int = 30_000,
) -> GameSimulation:
    """Run one full game with a caller-supplied agent per seat.

    Every agent only sees its own ``PlayerView`` and legal actions, so the
    M11 play interface and the M9 evaluation runner plug in through the same
    ``choose_action`` contract that ``run_random_game`` uses. Chance
    decisions resolve through a ``ChanceResolver`` seeded with ``game_seed``,
    and the returned replay re-derives the same final state.
    """

    if len(agents) != config.players:
        raise ValueError("exactly one agent per configured seat is required")
    if max_steps < 1:
        raise ValueError("max_steps must be positive")

    seat_agents = tuple(agents)
    state = engine.reset(config, game_seed)
    chance = ChanceResolver(seed=game_seed)
    steps: list[ReplayStep] = []

    for _ in range(max_steps):
        if state.phase is GamePhase.FINISHED:
            return GameSimulation(
                state=state,
                standings=final_standings(state),
                replay=_replay_record(config, game_seed, steps, state),
            )
        state = _advance_one_decision(engine, state, seat_agents, chance, steps)

    raise RuntimeError(f"the game exceeded the {max_steps}-action limit")


def _advance_one_decision(
    engine: RulesEngine,
    state: GameState,
    agents: tuple[Agent, ...],
    chance: ChanceResolver,
    steps: list[ReplayStep],
) -> GameState:
    decision = engine.current_decision(state)
    if isinstance(decision, ChanceDecision):
        outcome = chance.resolve(decision)
        steps.append(outcome)
        return engine.apply(state, outcome).state
    if not isinstance(decision, PlayerDecision):
        raise RuntimeError("the runner requires a pending decision")
    actions = engine.legal_actions(state, decision.owner)
    if not actions:
        raise RuntimeError("current player decision has no legal actions")
    observation = engine.observe(state, decision.owner)
    action = agents[decision.owner].choose_action(observation, actions)
    steps.append(action)
    return engine.apply(state, action).state


def _replay_record(
    config: RulesetConfig,
    game_seed: int,
    steps: list[ReplayStep],
    state: GameState,
) -> GameReplay:
    return GameReplay(
        ruleset=config,
        seed=game_seed,
        steps=tuple(steps),
        expected_state_hash=canonical_state_hash(state),
    )


def _round_finished(state: GameState, started_round: int) -> bool:
    return state.phase in (GamePhase.ENDGAME, GamePhase.FINISHED) or (
        state.round_number > started_round
    )
