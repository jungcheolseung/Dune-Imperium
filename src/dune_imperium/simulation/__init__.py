"""Headless game simulation helpers."""

from dune_imperium.simulation.coverage import (
    Census,
    collect_game_coverage,
    merge_coverage,
    normalize_instance_id,
    zero_coverage,
)
from dune_imperium.simulation.invariants import (
    CardCensus,
    InvariantViolation,
    check_observation_privacy,
    check_state_invariants,
)
from dune_imperium.simulation.runner import (
    GameSimulation,
    RoundSimulation,
    run_policy_game,
    run_random_game,
    run_random_round,
)
from dune_imperium.simulation.sweep import (
    GameCheckReport,
    SweepFailure,
    SweepReport,
    run_checked_game,
    run_sweep,
    sweep_specs,
)

__all__ = [
    "CardCensus",
    "Census",
    "GameCheckReport",
    "GameSimulation",
    "InvariantViolation",
    "RoundSimulation",
    "SweepFailure",
    "SweepReport",
    "check_observation_privacy",
    "check_state_invariants",
    "collect_game_coverage",
    "merge_coverage",
    "normalize_instance_id",
    "run_checked_game",
    "run_policy_game",
    "run_random_game",
    "run_random_round",
    "run_sweep",
    "sweep_specs",
    "zero_coverage",
]
