"""The learner measures a step against a fixed critic when the batch carries one.

Stage 3 of docs/entity-self-play-plan.md keeps the stage-1 value as a fixed
critic: the loop hands its values to the learner as ``baselines``.
"""

import copy
from dataclasses import replace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from tests.unit.training.test_learner_local_legal import _synthetic  # noqa: E402

from dune_imperium.training.learner import Learner, LearnerConfig  # noqa: E402

_CPU = torch.device("cpu")
# Only the policy term moves the weights.
_CONFIG = LearnerConfig(
    learning_rate=1e-2, value_coefficient=0.0, entropy_coefficient=0.0
)


def test_baselines_replace_the_value_head() -> None:
    network, batch = _synthetic()
    learner = Learner(network, _CPU, _CONFIG, seed=0)
    values = torch.zeros(batch.actions.shape[0])
    assert learner._baselines(batch, values) is values
    fixed = replace(batch, baselines=np.full(batch.actions.shape[0], 0.25, np.float32))
    assert torch.equal(learner._baselines(fixed, values), torch.full_like(values, 0.25))


def test_a_step_at_its_baseline_teaches_nothing() -> None:
    network, batch = _synthetic()
    # Every return equals its baseline: no advantage anywhere.
    level = replace(batch, baselines=batch.returns.copy())
    before = copy.deepcopy(network.policy_head.weight.detach())
    Learner(network, _CPU, _CONFIG, seed=0).update(level)
    assert torch.equal(network.policy_head.weight.detach(), before)
    # Against the value head the same batch does move the policy.
    other, _ = _synthetic()
    moved_before = copy.deepcopy(other.policy_head.weight.detach())
    Learner(other, _CPU, _CONFIG, seed=0).update(batch)
    assert not torch.equal(other.policy_head.weight.detach(), moved_before)
