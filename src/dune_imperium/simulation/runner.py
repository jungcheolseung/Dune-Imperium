"""Headless runners built on the public rules-engine contract."""

from dataclasses import dataclass

from dune_imperium.agents import RandomAgent
from dune_imperium.config import RulesetConfig
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.engine import RulesEngine
from dune_imperium.core.replay import GameReplay, ReplayStep
from dune_imperium.core.state import GamePhase, GameState, canonical_state_hash


@dataclass(frozen=True, slots=True)
class RoundSimulation:
    """Final state and replay record produced by a one-round simulation."""

    state: GameState
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
            replay = GameReplay(
                ruleset=config,
                seed=game_seed,
                steps=tuple(steps),
                expected_state_hash=canonical_state_hash(state),
            )
            return RoundSimulation(state=state, replay=replay)

        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            outcome = chance.resolve(decision)
            state = engine.apply(state, outcome).state
            steps.append(outcome)
            continue
        if not isinstance(decision, PlayerDecision):
            raise RuntimeError("one-round runner requires a pending player decision")
        actions = engine.legal_actions(state, decision.owner)
        if not actions:
            raise RuntimeError("current player decision has no legal actions")
        observation = engine.observe(state, decision.owner)
        action = agents[decision.owner].choose_action(observation, actions)
        state = engine.apply(state, action).state
        steps.append(action)

    raise RuntimeError(f"one round exceeded the {max_steps}-action limit")


def _round_finished(state: GameState, started_round: int) -> bool:
    return state.phase in (GamePhase.ENDGAME, GamePhase.FINISHED) or (
        state.round_number > started_round
    )
