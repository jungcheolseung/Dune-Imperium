"""Named, seed-constructible baseline agents for evaluation tooling."""

from collections.abc import Callable
from typing import Final

from dune_imperium.agents.base import Agent
from dune_imperium.agents.heuristic_agent import HeuristicAgent
from dune_imperium.agents.random_agent import RandomAgent
from dune_imperium.agents.rollout_agent import RolloutAgent

type AgentFactory = Callable[[int], Agent]


def _random(seed: int) -> Agent:
    return RandomAgent(seed=seed)


def _heuristic(seed: int) -> Agent:
    return HeuristicAgent(seed=seed)


def _rollout(seed: int) -> Agent:
    return RolloutAgent(seed=seed)


# Every baseline an evaluation can name on the command line. A factory takes
# the per-seat policy seed and returns a fresh agent; new baselines (rollout,
# search, checkpointed policies) register here so tournaments and reports
# refer to them by one stable name.
BASELINE_AGENT_FACTORIES: Final[dict[str, AgentFactory]] = {
    "random": _random,
    "heuristic": _heuristic,
    "rollout": _rollout,
}


def make_agent(kind: str, seed: int) -> Agent:
    """Instantiate the named baseline with ``seed``."""

    try:
        factory = BASELINE_AGENT_FACTORIES[kind]
    except KeyError:
        raise ValueError(f"unknown agent kind: {kind!r}") from None
    return factory(seed)
