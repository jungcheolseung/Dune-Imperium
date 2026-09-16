"""Named, seed-constructible baseline agents for evaluation tooling."""

from collections.abc import Callable
from typing import Final

from dune_imperium.agents.base import Agent
from dune_imperium.agents.heuristic_agent import (
    SPACE_BONUSES_BEFORE_DEMOTION,
    SPACE_BONUSES_BEFORE_ESPIONAGE,
    SPACE_BONUSES_BEFORE_RETUNE,
    SPACE_BONUSES_DEMOTED_TO_FLOOR,
    SPACE_BONUSES_MEDIAN_DEMOTION,
    SPACE_BONUSES_SPLIT_DEMOTION,
    UNIFORM_TIES,
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
    """The heuristic with the rubric-priced space ranking of 2026-09-10.

    That ranking priced every space on one rubric and beat the two-entry table
    on base+CHOAM, Bloodlines and Immortality but lost on the Tech Module
    (docs/evaluation/baseline-2026-09-10.md sections 13 to 16). Demoting its
    three most-visited spaces (Imperial Basin, Secrets, Arrakeen) beats it on
    every ruleset (section 18), so the demoted table is ``heuristic`` now and
    this variant pins the rubric-priced one for the paired A/B.
    """

    return HeuristicAgent(seed=seed, space_bonuses=SPACE_BONUSES_BEFORE_DEMOTION)


def _heuristic_floor_table(seed: int) -> Agent:
    """The heuristic with the three demoted spaces at the floor (2026-09-11).

    The demotion was first committed at 0.3, below every other yield. Measured
    one ruleset axis at a time, the median (0.6) beats that floor on base,
    CHOAM and Immortality and loses only on the Tech Module without CHOAM
    (docs/evaluation/baseline-2026-09-10.md section 18(h)), so the median is
    ``heuristic`` now and this variant pins the floor for the paired A/B.
    """

    return HeuristicAgent(seed=seed, space_bonuses=SPACE_BONUSES_DEMOTED_TO_FLOOR)


def _heuristic_median_table(seed: int) -> Agent:
    """The heuristic with the three demoted spaces at the median (2026-09-16 am).

    Ablating that table one space at a time showed Imperial Basin alone at
    the floor beats it on every axis while Arrakeen wants to be higher
    (docs/evaluation/baseline-2026-09-10.md sections 18(i) and 18(j)), so the
    split table is ``heuristic`` now and this variant pins the median one for
    the paired A/B.
    """

    return HeuristicAgent(seed=seed, space_bonuses=SPACE_BONUSES_MEDIAN_DEMOTION)


def _heuristic_split_table(seed: int) -> Agent:
    """The heuristic with the split table of 2026-09-16 noon.

    Imperial Basin at the floor and Arrakeen above every one-shot yield, with
    Deliver Supplies still at its rubric price; its own ablation then sent
    Deliver Supplies down (docs/evaluation/baseline-2026-09-10.md section
    18(l)), so this variant pins the split table for the paired A/B.
    """

    return HeuristicAgent(seed=seed, space_bonuses=SPACE_BONUSES_SPLIT_DEMOTION)


def _heuristic_supplies_table(seed: int) -> Agent:
    """The heuristic with the Deliver Supplies table of 2026-09-16 afternoon.

    Espionage still at its rubric price; that table's own ablation then sent
    Espionage down (docs/evaluation/baseline-2026-09-10.md section 18(m)), so
    this variant pins it for the paired A/B.
    """

    return HeuristicAgent(seed=seed, space_bonuses=SPACE_BONUSES_BEFORE_ESPIONAGE)


def _heuristic_uniform_ties(seed: int) -> Agent:
    """The heuristic before the 2026-09-16 within-family tie-breaks.

    A Faction to gain Influence with, a card to trash or discard, and one of
    two same-cost cards to buy all fell to the tie-break RNG. Pinning that
    here keeps the paired A/B of docs/evaluation/baseline-2026-09-16.md
    section 14 reproducible from the committed tree.
    """

    return HeuristicAgent(seed=seed, tie_breaks=UNIFORM_TIES)


def _rollout(seed: int) -> Agent:
    return RolloutAgent(seed=seed)


def _rollout_untuned(seed: int) -> Agent:
    """The rollout search with its 2026-09-06 knobs.

    Two sampled worlds, six candidates and fresh playout seeds; re-tuned on
    2026-09-16 when the strengthened heuristic left it near parity
    (docs/evaluation/baseline-2026-09-16.md section 13). Pinned here so the
    paired A/B against the current defaults reruns from the committed tree.
    """

    return RolloutAgent(
        seed=seed,
        rollouts=2,
        candidates=6,
        horizon_rounds=1,
        paired_playouts=False,
        opponent_reference="max",
        deck_by_value=False,
    )


def _rollout_count_max(seed: int) -> Agent:
    """The rollout search with the 2026-09-16 evening value function.

    Playouts read against the strongest opponent and the deck counted by
    card; re-measured on 2026-09-16 night against three tie-break heuristics
    (docs/evaluation/baseline-2026-09-16.md section 15), where the mean
    reference with the printed-value deck won. Pinned here so the paired
    A/B reruns from the committed tree.
    """

    return RolloutAgent(seed=seed, opponent_reference="max", deck_by_value=False)


def _rollout_strong(seed: int) -> Agent:
    """The rollout search at twice the default budget.

    Eight sampled worlds over three candidates with common random numbers:
    60% against three heuristics on base at about 150 ms a decision on an M4
    (docs/evaluation/baseline-2026-09-16.md section 13), a stronger table
    opponent for the play server and for evaluations that can afford it.
    """

    return RolloutAgent(
        seed=seed, rollouts=8, candidates=3, horizon_rounds=1, paired_playouts=True
    )


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
    "heuristic_floor_table": _heuristic_floor_table,
    "heuristic_median_table": _heuristic_median_table,
    "heuristic_split_table": _heuristic_split_table,
    "heuristic_supplies_table": _heuristic_supplies_table,
    "heuristic_uniform_ties": _heuristic_uniform_ties,
    "rollout": _rollout,
    "rollout_untuned": _rollout_untuned,
    "rollout_count_max": _rollout_count_max,
    "rollout_strong": _rollout_strong,
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
