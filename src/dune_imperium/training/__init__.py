"""Self-play data collection for M10 training (requires the ``rl`` extra)."""

from dune_imperium.training.policy import (
    UNDO_ACTION_IDS,
    AgentBatchPolicy,
    BatchPolicy,
    PolicyRequest,
    RandomBatchPolicy,
    without_undo_actions,
)
from dune_imperium.training.selfplay import (
    Episode,
    SelfPlayResult,
    SelfPlayRunner,
    SelfPlaySpec,
    TrainingBatch,
    TrajectoryStep,
    apply_step_penalty,
    select_policy_steps,
    stack_episodes,
)

__all__ = [
    "UNDO_ACTION_IDS",
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
    "apply_step_penalty",
    "select_policy_steps",
    "stack_episodes",
    "without_undo_actions",
]
