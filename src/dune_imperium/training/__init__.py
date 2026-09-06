"""Self-play data collection for M10 training (requires the ``rl`` extra)."""

from dune_imperium.training.policy import (
    AgentBatchPolicy,
    BatchPolicy,
    PolicyRequest,
    RandomBatchPolicy,
)
from dune_imperium.training.selfplay import (
    Episode,
    SelfPlayResult,
    SelfPlayRunner,
    SelfPlaySpec,
    TrainingBatch,
    TrajectoryStep,
    select_policy_steps,
    stack_episodes,
)

__all__ = [
    "AgentBatchPolicy",
    "BatchPolicy",
    "Episode",
    "PolicyRequest",
    "RandomBatchPolicy",
    "SelfPlayResult",
    "SelfPlayRunner",
    "SelfPlaySpec",
    "TrainingBatch",
    "TrajectoryStep",
    "select_policy_steps",
    "stack_episodes",
]
