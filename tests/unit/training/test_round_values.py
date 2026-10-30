"""Stage 1 of the self-play plan: the table mix, round starts, TD targets, the fit.

docs/entity-self-play-plan.md sections 3.2, 3.4 and 4.1.
"""

import dataclasses
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.agents.registry import make_agent  # noqa: E402
from dune_imperium.core.state import GamePhase  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.simulation.runner import run_policy_game  # noqa: E402
from dune_imperium.training.entity_network import (  # noqa: E402
    EntityNetwork,
    with_value_branch,
)
from dune_imperium.training.policy import encoded_view  # noqa: E402
from dune_imperium.training.round_values import (  # noqa: E402
    CollectSpec,
    FitConfig,
    RoundData,
    collect_rounds,
    concatenate_rounds,
    fit_round_values,
    lambda_targets,
    leader_values,
    load_rounds,
    outcome_rewards,
    save_rounds,
)
from dune_imperium.training.table_mix import (  # noqa: E402
    DEFAULT_SHARES,
    PastSelves,
    TableMix,
    parse_shares,
)

_CONFIG = RulesetConfig()


# -- the mix ----------------------------------------------------------------------
def test_the_user_s_shares_deal_exactly_and_evenly() -> None:
    mix = TableMix.from_shares(DEFAULT_SHARES)
    assert len(mix.cycle) == 10
    assert {kind: mix.cycle.count(kind) for kind in DEFAULT_SHARES} == {
        "self": 5,
        "past": 3,
        "x": 1,
        "app": 1,
    }
    # Spread, not bunched: no kind twice in a row except where it must be.
    assert all(
        mix.cycle[index] != mix.cycle[index + 1] or mix.cycle[index] == "self"
        for index in range(len(mix.cycle) - 1)
    )
    assert mix.kind(3) == mix.kind(13)
    assert parse_shares("self=5,past=3,x=1,app=1") == dict(DEFAULT_SHARES)
    with pytest.raises(ValueError):
        parse_shares("teacher=1")


def test_a_table_seats_its_learners_by_seed() -> None:
    mix = TableMix(("self", "past", "x", "app"))
    agents = {"learner": "L", "x": "X", "app": "A"}
    table = mix.table(0, 5, **agents)
    assert table.kind == "self" and table.agents == ("L",) * 4
    assert table.learners == (0, 1, 2, 3)
    # Without past copies a past table is a self table (stage 1).
    assert mix.table(1, 5, **agents).kind == "self"
    past = mix.table(1, 5, **agents, past=("P1", "P2"))
    assert past.kind == "past" and len(past.learners) == 2
    assert sorted(past.agents)[:2] == ["L", "L"]
    assert set(past.agents) - {"L"} <= {"P1", "P2"}
    x = mix.table(2, 5, **agents)
    assert x == mix.table(2, 5, **agents)
    assert [x.agents[seat] for seat in x.learners] == ["L", "L"]
    assert sorted(x.agents) == ["L", "L", "X", "X"]
    app = mix.table(3, 6, **agents)
    assert sorted(app.agents) == ["A", "A", "L", "L"]


def test_past_selves_keep_the_newest_copies(tmp_path: Path) -> None:
    source = tmp_path / "latest.pt"
    pool = PastSelves(tmp_path / "past", every=2, size=2)
    assert pool.paths() == []
    for iteration in range(1, 8):
        source.write_text(str(iteration))
        kept = pool.keep(iteration, source)
        assert (kept is not None) == (iteration % 2 == 0)
    assert [path.name for path in pool.paths()] == ["past-000004.pt", "past-000006.pt"]
    assert pool.paths()[-1].read_text() == "6"


# -- targets ----------------------------------------------------------------------
def _trajectory_data(
    games: list[int], seats: list[int], rounds: list[int]
) -> RoundData:
    rows = len(games)
    return RoundData(
        ruleset=_CONFIG.identifier,
        leader_names=("a",),
        obs_columns=np.zeros(0, np.int16),
        obs_values=np.zeros(0, np.int16),
        obs_offsets=np.zeros(rows + 1, np.int64),
        games=np.asarray(games, np.int64),
        seats=np.asarray(seats, np.int8),
        rounds=np.asarray(rounds, np.int16),
        ranks=np.ones(rows, np.int8),
        victory_points=np.zeros((rows, 4), np.int16),
        tables=np.zeros(rows, np.int8),
        leaders=np.zeros(rows, np.int16),
    )


def test_the_next_round_is_the_same_game_and_seat() -> None:
    data = _trajectory_data(
        games=[7, 7, 8, 7, 7, 8],
        seats=[1, 0, 1, 0, 1, 1],
        rounds=[2, 1, 1, 2, 1, 2],
    )
    assert data.next_rows().tolist() == [-1, 3, 5, -1, 0, -1]


def test_lambda_targets_by_hand() -> None:
    # One seat's rounds 1, 2, 3 stored out of order: rows 2, 0, 1.
    following = np.asarray([1, -1, 0])
    values = np.asarray([0.4, 0.6, 0.2], dtype=np.float32)
    rewards = np.asarray([1.0, 1.0, 1.0], dtype=np.float32)
    targets = lambda_targets(following, values, rewards, 0.5)
    # Round 3: the reward. Round 2: 0.5 * 0.6 + 0.5 * 1. Round 1: 0.5 * 0.4 + 0.5 * 0.8.
    assert targets.tolist() == pytest.approx([0.8, 1.0, 0.6])
    assert lambda_targets(following, values, rewards, 1.0).tolist() == [1.0] * 3
    assert lambda_targets(following, values, rewards, 0.0).tolist() == pytest.approx(
        [0.6, 1.0, 0.4]
    )
    with pytest.raises(ValueError):
        lambda_targets(following, values, rewards, 1.5)


def test_outcome_rewards_are_graded() -> None:
    data = _trajectory_data([1] * 4, [0, 1, 2, 3], [1] * 4)
    data = dataclasses.replace(data, ranks=np.asarray([1, 2, 3, 4], np.int8))
    assert outcome_rewards(data, 1 / 6).tolist() == pytest.approx(
        [1.0, -1 / 6, -1 / 3, -1 / 2]
    )


# -- collection and the fit ---------------------------------------------------------
@pytest.fixture(scope="module")
def collected() -> RoundData:
    spec = CollectSpec(config=_CONFIG, learner="heuristic", x="heuristic")
    return collect_rounds(spec, [(0, 20), (1, 21)])


def test_round_starts_are_the_states_a_leaf_is_read_at(collected: RoundData) -> None:
    engine = UprisingRulesEngine()
    expected: list[tuple[int, int, np.ndarray]] = []
    seen = [0]

    def hook(state):  # type: ignore[no-untyped-def]
        if (
            state.round_number > seen[0]
            and state.phase is not GamePhase.ROUND_START
            and state.phase is not GamePhase.FINISHED
        ):
            seen[0] = state.round_number
            for seat in range(4):
                expected.append(
                    (
                        state.round_number,
                        seat,
                        encoded_view(engine.observe(state, seat)),
                    )
                )

    agents = [make_agent("heuristic", 20 * 4 + seat, _CONFIG) for seat in range(4)]
    simulation = run_policy_game(engine, _CONFIG, 20, agents, on_state=hook)
    first = np.flatnonzero(collected.games == 20)
    assert len(first) == len(expected)
    dense = collected.observations(first)
    for row, (round_number, seat, _) in zip(first, expected, strict=True):
        assert collected.rounds[row] == round_number
        assert collected.seats[row] == seat
    assert np.array_equal(dense, np.stack([view for _, _, view in expected]))
    # Every seat's rounds run 1..K, and the rows carry the game's ending.
    places = {standing.player: standing for standing in simulation.standings}
    for seat in range(4):
        mine = first[collected.seats[first] == seat]
        assert collected.rounds[mine].tolist() == list(range(1, len(mine) + 1))
        assert set(collected.ranks[mine].tolist()) == {places[seat].rank}
        assert collected.victory_points[mine[0], 0] == places[seat].victory_points
        assert (
            collected.victory_points[mine[0], 1]
            == places[(seat + 1) % 4].victory_points
        )
    assert all(collected.leader_names)


def test_round_shards_save_load_and_join(tmp_path: Path, collected: RoundData) -> None:
    path = tmp_path / "rounds-000000020.npz"
    save_rounds(collected, path)
    loaded = load_rounds(path)
    rows = np.arange(loaded.rows)
    assert np.array_equal(loaded.observations(rows), collected.observations(rows))
    first = np.flatnonzero(collected.games == 20)
    second = np.flatnonzero(collected.games == 21)
    joined = concatenate_rounds([_subset(collected, second), _subset(collected, first)])
    assert joined.rows == collected.rows
    names = [joined.leader_names[index] for index in joined.leaders]
    original = [collected.leader_names[index] for index in collected.leaders]
    assert names == [original[row] for row in [*second, *first]]
    assert np.array_equal(
        joined.observations(np.arange(joined.rows)),
        collected.observations(np.concatenate([second, first])),
    )


def _subset(data: RoundData, rows: np.ndarray) -> RoundData:
    from dune_imperium.training.teacher import gather_rows

    columns, offsets = gather_rows(data.obs_columns, data.obs_offsets, rows)
    values, _ = gather_rows(data.obs_values, data.obs_offsets, rows)
    return dataclasses.replace(
        data,
        obs_columns=columns,
        obs_values=values,
        obs_offsets=offsets,
        games=data.games[rows],
        seats=data.seats[rows],
        rounds=data.rounds[rows],
        ranks=data.ranks[rows],
        victory_points=data.victory_points[rows],
        tables=data.tables[rows],
        leaders=data.leaders[rows],
    )


def test_the_fit_moves_the_value_and_keeps_the_policy(collected: RoundData) -> None:
    torch.manual_seed(0)
    start = EntityNetwork(
        _CONFIG, hidden=(32,), entity_width=16, seat_width=32, action_width=16
    ).eval()
    network = with_value_branch(start, aux_vp=True, aux_rank=True, reward_step=1 / 6)
    config = FitConfig(lam=0.8, step=1 / 6, fits=2, epochs=2, minibatch=16, chunk=64)
    fitted, records = fit_round_values(network, collected, config)
    assert [(record["fit"], record["epoch"]) for record in records] == [
        (1, 1),
        (1, 2),
        (2, 1),
        (2, 2),
    ]
    heldout = records[-1]["heldout"]
    assert heldout["rows"] == int((collected.games == 20).sum())
    assert set(heldout["by_round"]) == {
        str(round_number)
        for round_number in set(collected.rounds[collected.games == 20].tolist())
    }
    observations = torch.from_numpy(collected.observations(np.arange(collected.rows)))
    with torch.no_grad():
        assert torch.equal(fitted.trunk(observations), start.trunk(observations))
        assert not torch.equal(
            fitted.values(observations), network.values(observations)
        )
    for name, parameter in start.state_dict().items():
        if not name.startswith(("value_head", "vp_head")):
            assert torch.equal(fitted.state_dict()[name], parameter), name
    # The input file is not touched.
    assert network.value_body is not None and all(
        torch.equal(a, b)
        for a, b in zip(
            network.value_body.parameters(), start.body.parameters(), strict=True
        )
    )
    leaders = leader_values(fitted, collected, np.arange(collected.rows), config)
    assert set(leaders) <= set(collected.leader_names) and leaders
