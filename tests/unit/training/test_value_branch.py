"""The value branch, the graded reward, and reading values through one call.

docs/entity-self-play-plan.md section 3.1: the self-play value trains a body
of its own over the shared encoders, so a branched copy of the student must
start as the student, bit for bit, and its value must be what every reader
(the search's leaves above all) reads. Section 3.2: the value learns a graded
reward, so the search reads a finished playout on the same scale.
"""

import re
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from torch import Tensor  # noqa: E402

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.adapters.pettingzoo_env import (  # noqa: E402
    LOSER_REWARD,
    WINNER_REWARD,
    graded_reward,
)
from dune_imperium.agents.network_search_agent import (  # noqa: E402
    NetworkSearchAgent,
    finished_reward,
)
from dune_imperium.agents.registry import make_agent  # noqa: E402
from dune_imperium.core.state import GamePhase, GameState  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.rules.endgame import final_standings  # noqa: E402
from dune_imperium.simulation.runner import run_policy_game  # noqa: E402
from dune_imperium.training.checkpoint import (  # noqa: E402
    load_checkpoint,
    save_checkpoint,
)
from dune_imperium.training.entity_network import (  # noqa: E402
    EntityNetwork,
    with_value_branch,
)
from dune_imperium.training.policy import encoded_view  # noqa: E402

_CONFIG = RulesetConfig()
_ROOT = Path(__file__).resolve().parents[3]


def _network(seed: int = 0) -> EntityNetwork:
    torch.manual_seed(seed)
    network = EntityNetwork(
        _CONFIG, hidden=(32, 32), entity_width=16, seat_width=32, action_width=16
    )
    with torch.no_grad():
        for parameter in network.entity_own.values():
            parameter.normal_(0.0, 0.5)
        network.action_bias.normal_(0.0, 0.5)
    return network.eval()


@pytest.fixture(scope="module")
def finished() -> GameState:
    agents = [make_agent("heuristic", seat, _CONFIG) for seat in range(4)]
    state = run_policy_game(UprisingRulesEngine(), _CONFIG, 7, agents).state
    assert state.phase is GamePhase.FINISHED
    return state


@pytest.fixture(scope="module")
def observations(finished: GameState) -> Tensor:
    """Every seat's view of the finished game and of its start."""

    engine = UprisingRulesEngine()
    start = engine.reset(_CONFIG, 7)
    views = [
        encoded_view(engine.observe(state, seat))
        for state in (start, finished)
        for seat in range(4)
    ]
    stacked: Tensor = torch.from_numpy(np.stack(views))
    return stacked


def test_a_branch_starts_as_the_file(observations: Tensor) -> None:
    network = _network()
    branched = with_value_branch(network, aux_vp=True, aux_rank=True, reward_step=0.25)
    assert not branched.value_reads_trunk and network.value_reads_trunk
    masks = torch.ones(observations.shape[0], network.action_size)
    with torch.no_grad():
        logits, values = network(observations, masks)
        branched_logits, branched_values = branched(observations, masks)
        assert torch.equal(branched_logits, logits)
        assert torch.equal(branched_values, values)
        assert torch.equal(branched.values(observations), values)
        assert torch.equal(branched.trunk(observations), network.trunk(observations))
    assert branched.vp_head is not None and branched.rank_head is not None
    assert branched.reward_step == 0.25
    with pytest.raises(ValueError, match="already has a value branch"):
        with_value_branch(branched)


def test_the_branch_moves_the_value_and_not_the_policy(
    observations: Tensor,
) -> None:
    network = _network()
    branched = with_value_branch(network)
    assert branched.value_body is not None
    with torch.no_grad():
        for parameter in branched.value_body.parameters():
            parameter.add_(0.5)
        hidden, values = branched.trunk_and_values(observations)
        assert torch.equal(hidden, network.trunk(observations))
        assert not torch.equal(values, network.values(observations))
        assert torch.equal(values, branched.values(observations))
        # Read through the trunk, the head would answer the old value.
        assert torch.equal(
            branched.value_head(hidden).squeeze(-1), network.values(observations)
        )


def test_a_plain_network_reads_its_value_from_the_trunk(
    observations: Tensor,
) -> None:
    network = _network()
    with torch.no_grad():
        hidden, values = network.trunk_and_values(observations)
        assert torch.equal(hidden, network.trunk(observations))
        assert torch.equal(values, network.value_head(hidden).squeeze(-1))
        assert torch.equal(network.value_input(observations), hidden)
    spec = network.arch_spec()
    assert not {"value_branch", "aux_rank", "reward_step"} & set(spec)
    assert not any(key.startswith("value_body") for key in network.state_dict())


def test_a_branched_file_saves_and_loads(tmp_path: Path, observations: Tensor) -> None:
    branched = with_value_branch(_network(), aux_rank=True, reward_step=1 / 6)
    assert branched.value_body is not None
    with torch.no_grad():
        for parameter in branched.value_body.parameters():
            parameter.mul_(1.5)
    path = tmp_path / "branched.pt"
    save_checkpoint(
        path,
        branched,
        ruleset=_CONFIG.identifier,
        iteration=1,
        codec=ActionCodec(_CONFIG),
    )
    loaded, _ = load_checkpoint(path)
    assert isinstance(loaded, EntityNetwork)
    assert loaded.arch_spec() == branched.arch_spec()
    assert loaded.reward_step == 1 / 6
    with torch.no_grad():
        assert torch.equal(loaded.values(observations), branched.values(observations))


def test_the_graded_reward() -> None:
    assert [graded_reward(rank, 0.0) for rank in (1, 2, 3, 4)] == [
        WINNER_REWARD,
        LOSER_REWARD,
        LOSER_REWARD,
        LOSER_REWARD,
    ]
    graded = [graded_reward(rank, 1 / 6) for rank in (1, 2, 3, 4)]
    assert graded == pytest.approx([1.0, -1 / 6, -1 / 3, -1 / 2])
    assert sum(graded) == pytest.approx(0.0)


def test_the_search_reads_a_branched_file_s_value_and_scale(
    tmp_path: Path, finished: GameState
) -> None:
    branched = with_value_branch(_network(), reward_step=1 / 6)
    assert branched.value_body is not None
    with torch.no_grad():
        for parameter in branched.value_body.parameters():
            parameter.add_(0.25)
    path = tmp_path / "branched.pt"
    save_checkpoint(
        path,
        branched,
        ruleset=_CONFIG.identifier,
        iteration=1,
        codec=ActionCodec(_CONFIG),
    )
    agent = NetworkSearchAgent(str(path), seed=0, config=_CONFIG)
    standings = final_standings(finished)
    last = next(s.player for s in standings if s.rank == 4)
    assert finished_reward(finished, last) == LOSER_REWARD
    assert finished_reward(finished, last, 1 / 6) == pytest.approx(-0.5)
    horizon = finished.round_number + 1
    assert agent._playout(finished, last, horizon, 0) == pytest.approx(-0.5)
    view = UprisingRulesEngine().observe(finished, last)
    observation = torch.from_numpy(encoded_view(view)).unsqueeze(0)
    with torch.no_grad():
        expected = float(branched.values(observation)[0])
        through_trunk = float(branched.value_head(branched.trunk(observation))[0, 0])
    assert agent._leaf_value(view) == expected
    assert agent._leaf_value(view) != through_trunk


# Where ``value_head`` may be called: the networks themselves, the two
# readers that ask ``value_reads_trunk`` first, and the stage-1 fit, which
# feeds it the branch's own hidden.
_READERS = {
    "src/dune_imperium/training/network.py",
    "src/dune_imperium/training/entity_network.py",
    "src/dune_imperium/agents/network_search_agent.py",
    "src/dune_imperium/training/older_teacher.py",
    "src/dune_imperium/training/round_values.py",
}


def test_values_are_read_through_the_network_s_calls() -> None:
    """``value_head(trunk(...))`` reads a branched network's value wrong."""

    callers = {
        str(path.relative_to(_ROOT))
        for folder in ("src", "scripts")
        for path in (_ROOT / folder).rglob("*.py")
        if re.search(r"\bvalue_head\(", path.read_text(encoding="utf-8"))
    }
    assert callers <= _READERS, sorted(callers - _READERS)
