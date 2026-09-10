"""Named, seed-constructible baseline agents for evaluation tooling."""

from collections.abc import Callable
from typing import Final

from dune_imperium.agents.base import Agent
from dune_imperium.agents.heuristic_agent import (
    SPACE_BONUSES_BEFORE_RETUNE,
    UPRISING_SPACE_BONUSES,
    HeuristicAgent,
)
from dune_imperium.agents.random_agent import RandomAgent
from dune_imperium.agents.rollout_agent import RolloutAgent

type AgentFactory = Callable[[int], Agent]


def _random(seed: int) -> Agent:
    return RandomAgent(seed=seed)


def _heuristic(seed: int) -> Agent:
    return HeuristicAgent(seed=seed)


def _heuristic_untuned(seed: int) -> Agent:
    """The heuristic with the board space ranking from before 2026-09-10.

    A retune of the score tables is only believable against the ranking it
    replaced, on the same seeds and seat rotations. Registering the old table
    here keeps that A/B reproducible from the committed tree; the 2026-09-09
    retune had to register a scratch module at runtime because the registry
    had no slot for a variant.
    """

    return HeuristicAgent(seed=seed, space_bonuses=SPACE_BONUSES_BEFORE_RETUNE)


def _heuristic_flat_cards(seed: int) -> Agent:
    """The heuristic before the 2026-09-10 spent-card ranking.

    Every card that reaches a board space cost the same to send, so the choice
    among them fell to the tie-break RNG. Pinning that here keeps the paired
    A/B for the Reveal-box pricing reproducible from the committed tree, the
    way ``heuristic_untuned`` does for the board space table.
    """

    return HeuristicAgent(seed=seed, spent_card_value=None)


def _heuristic_uprising_table(seed: int) -> Agent:
    """The heuristic with the priced Uprising space ranking on every ruleset.

    Every ruleset uses that ranking now except one: the Tech Module keeps the
    two-entry table, because a Tech tile is bought on a Landsraad visit
    [Bloodlines p. 7] and the priced ranking puts the cheap Landsraad spaces
    at the bottom (-6.6pp and -4.8pp, docs/evaluation/baseline-2026-09-10.md
    section 15). This variant is the other side of that one open A/B, so
    pricing a Tech ranking can be measured against it from the committed tree.
    """

    return HeuristicAgent(seed=seed, space_bonuses=UPRISING_SPACE_BONUSES)


def _rollout(seed: int) -> Agent:
    return RolloutAgent(seed=seed)


# Every baseline an evaluation can name on the command line. A factory takes
# the per-seat policy seed and returns a fresh agent; new baselines (rollout,
# search, checkpointed policies) register here so tournaments and reports
# refer to them by one stable name.
BASELINE_AGENT_FACTORIES: Final[dict[str, AgentFactory]] = {
    "random": _random,
    "heuristic": _heuristic,
    "heuristic_untuned": _heuristic_untuned,
    "heuristic_flat_cards": _heuristic_flat_cards,
    "heuristic_uprising_table": _heuristic_uprising_table,
    "rollout": _rollout,
}


# A trained policy enters by file: ``checkpoint:<path>``. Worker processes
# resolve the path themselves, so no runtime registration has to cross a
# process boundary. The training package (torch) is imported only then.
CHECKPOINT_PREFIX: Final = "checkpoint:"


def is_agent_kind(kind: str) -> bool:
    """Return whether ``make_agent`` can build ``kind``."""

    return kind in BASELINE_AGENT_FACTORIES or (
        kind.startswith(CHECKPOINT_PREFIX) and len(kind) > len(CHECKPOINT_PREFIX)
    )


def make_agent(kind: str, seed: int) -> Agent:
    """Instantiate the named baseline (or a checkpoint) with ``seed``."""

    if kind.startswith(CHECKPOINT_PREFIX):
        path = kind[len(CHECKPOINT_PREFIX) :]
        if not path:
            raise ValueError("checkpoint agent kind needs a path")
        from dune_imperium.training.torch_policy import load_network_agent

        return load_network_agent(path)
    try:
        factory = BASELINE_AGENT_FACTORIES[kind]
    except KeyError:
        raise ValueError(f"unknown agent kind: {kind!r}") from None
    return factory(seed)
