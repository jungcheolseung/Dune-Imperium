"""The observation array and a search decision's trunk cache (ai-speedup).

Both are speed work for the search seat: neither may change a number a
network reads or returns.
"""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.adapters.observation_encoding import (  # noqa: E402
    encode_player_view,
)
from dune_imperium.agents import StateAgent, make_agent  # noqa: E402
from dune_imperium.agents.agent_turn_steps import apply_whole  # noqa: E402
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision  # noqa: E402
from dune_imperium.core.observation import PlayerView  # noqa: E402
from dune_imperium.core.state import GamePhase  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.training import policy  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.policy import encoded_view  # noqa: E402
from dune_imperium.training.trunk_cache import TrunkCache  # noqa: E402

_EVERYTHING = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    arrakeen_scouts=True,
)


def _views(config: RulesetConfig, seed: int, decisions: int) -> list[PlayerView]:
    """Every seat's view at each of a heuristic game's first ``decisions``."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [make_agent("heuristic", index) for index in range(config.players)]
    views: list[PlayerView] = []
    while len(views) < decisions * config.players:
        assert state.phase is not GamePhase.FINISHED
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(engine, state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        views.extend(engine.observe(state, seat) for seat in range(config.players))
        actions = engine.legal_actions(state, decision.owner)
        agent = agents[decision.owner]
        assert isinstance(agent, StateAgent)
        choice = agent.choose_action_with_state(
            state, engine.observe(state, decision.owner), actions
        )
        state = apply_whole(engine, state, choice, legal_actions=actions).state
    return views


@pytest.mark.parametrize("config", [RulesetConfig(), _EVERYTHING])
def test_the_observation_array_is_numpy_s_conversion_of_the_encoding(
    config: RulesetConfig,
) -> None:
    for view in _views(config, seed=4, decisions=80):
        expected = np.asarray(encode_player_view(view), dtype=np.int32)
        array = encoded_view(view)
        assert array.dtype == np.int32 and array.shape == expected.shape
        assert array.flags.c_contiguous and array.flags.writeable
        assert np.array_equal(array, expected)


def test_a_value_outside_a_byte_takes_numpy_s_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    view = _views(RulesetConfig(), seed=4, decisions=1)[0]
    for values in ((1, 300, 0), (2, -1, 7), (0, 255, 1)):
        monkeypatch.setattr(policy, "encode_player_view", lambda _, v=values: v)
        array = encoded_view(view)
        assert array.dtype == np.int32
        assert np.array_equal(array, np.asarray(values, dtype=np.int32))


def _network(seed: int) -> PolicyValueNetwork:
    torch.manual_seed(seed)
    return PolicyValueNetwork(ActionCodec(RulesetConfig()).size, hidden=(16,))


def test_a_decision_reads_each_observation_s_trunk_once() -> None:
    views = _views(RulesetConfig(), seed=4, decisions=3)
    first, second = encoded_view(views[0]), encoded_view(views[1])
    assert not np.array_equal(first, second)
    network, other = _network(0), _network(1)
    cache = TrunkCache()

    def trunk(net: PolicyValueNetwork, observation: np.ndarray) -> object:
        with torch.no_grad():
            return net.trunk(torch.from_numpy(observation).unsqueeze(0))

    # Outside a decision nothing is kept.
    outside = cache.hidden(network, first)
    assert torch.equal(outside, trunk(network, first)) and len(cache) == 0
    assert cache.hidden(network, first) is not outside

    with cache.decision():
        kept = cache.hidden(network, first)
        assert torch.equal(kept, trunk(network, first))
        assert cache.hidden(network, first.copy()) is kept
        assert cache.hidden(network, second) is not kept
        # Another network's trunk of the same observation is its own.
        theirs = cache.hidden(other, first)
        assert torch.equal(theirs, trunk(other, first))
        with cache.decision():  # a nested use shares the decision
            assert cache.hidden(network, first) is kept
        assert len(cache) == 3
        assert (cache.hits, cache.misses) == (2, 3)
    assert len(cache) == 0
    with cache.decision():
        assert cache.hidden(network, first) is not kept
