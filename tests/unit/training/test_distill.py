"""Tests for expert-iteration distillation (``training.distill``)."""

import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.adapters.observation_encoding import OBSERVATION_SIZE  # noqa: E402
from dune_imperium.adapters.pettingzoo_env import (  # noqa: E402
    LOSER_REWARD,
    WINNER_REWARD,
)
from dune_imperium.agents import make_agent  # noqa: E402
from dune_imperium.cli.expert import main  # noqa: E402
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.training.checkpoint import (  # noqa: E402
    load_checkpoint,
    save_checkpoint,
)
from dune_imperium.training.distill import (  # noqa: E402
    DistillConfig,
    clustered_difference,
    distill,
    evaluate,
    legal_log_probs,
    policy_targets,
    row_target,
    save_candidate,
    search_choice,
)
from dune_imperium.training.expert import (  # noqa: E402
    ANCHOR,
    LABEL,
    ExpertData,
    LabelConfig,
    LabelledGame,
    LabelRow,
    run_meta,
    write_game,
)
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402


def _stack_rows(
    *,
    legal: Sequence[Sequence[int]],
    prior_logits: Sequence[Sequence[float]],
    kind: Sequence[int],
    candidates: Sequence[Sequence[int]],
    values: Sequence[Sequence[Sequence[float]]],
    played: Sequence[int] | None = None,
    z: Sequence[float] | None = None,
    weight: Sequence[float] | None = None,
    game_seed: Sequence[int] | None = None,
    observations: np.ndarray | None = None,
    action_size: int = 32,
) -> ExpertData:
    """Build a small ``ExpertData`` directly from per-row Python lists."""

    count = len(legal)
    lengths = np.asarray([len(row) for row in legal], dtype=np.int64)
    offsets = np.zeros(count + 1, dtype=np.int64)
    np.cumsum(lengths, out=offsets[1:])
    legal_indices = (
        np.concatenate([np.asarray(row, dtype=np.int32) for row in legal])
        if count
        else np.zeros(0, dtype=np.int32)
    )
    flat_prior = (
        np.concatenate([np.asarray(row, dtype=np.float32) for row in prior_logits])
        if count
        else np.zeros(0, dtype=np.float32)
    )
    obs = (
        observations
        if observations is not None
        else np.zeros((count, OBSERVATION_SIZE), dtype=np.uint8)
    )
    return ExpertData(
        observations=obs,
        legal_indices=legal_indices,
        legal_offsets=offsets,
        prior_logits=flat_prior,
        kind=np.asarray(kind, dtype=np.int8),
        seat=np.zeros(count, dtype=np.int8),
        round=np.zeros(count, dtype=np.int16),
        decision_index=np.arange(count, dtype=np.int32),
        seat_decisions=np.zeros(count, dtype=np.int32),
        candidates=np.asarray(candidates, dtype=np.int32),
        values=np.asarray(values, dtype=np.float32),
        played=np.asarray(
            played if played is not None else [0] * count, dtype=np.int32
        ),
        z=np.asarray(z if z is not None else [0.0] * count, dtype=np.float32),
        weight=np.asarray(
            weight if weight is not None else [1.0] * count, dtype=np.float32
        ),
        game_seed=np.asarray(
            game_seed if game_seed is not None else [1] * count, dtype=np.int64
        ),
        action_size=action_size,
    )


def _prior_from_logits(logits: np.ndarray) -> np.ndarray:
    """The same float64 softmax ``row_target`` builds its prior from."""

    values = np.asarray(logits, dtype=np.float64)
    shifted = np.exp(values - values.max())
    result: np.ndarray = shifted / shifted.sum()
    return result


# -- 1. tilt-mode targets ---------------------------------------------------
def test_tilt_target_equals_prior_when_candidate_values_tie() -> None:
    """Equal candidate means leave the prior exactly unchanged (module docstring)."""

    legal = np.asarray([0, 1, 2, 3, 4], dtype=np.int32)
    prior_logits = np.asarray([0.2, -0.5, 1.1, 0.0, 0.4], dtype=np.float32)
    candidates = np.asarray([1, 3, -1], dtype=np.int32)
    values = np.full((2, 3), np.nan, dtype=np.float32)
    values[:, :2] = 0.7  # both tied candidates share the same mean value
    target = row_target(LABEL, legal, prior_logits, candidates, values, DistillConfig())
    assert np.allclose(target, _prior_from_logits(prior_logits), atol=1e-7)


def test_tilt_target_preserves_prior_mass_outside_and_inside_candidates() -> None:
    legal = np.asarray([0, 1, 2, 3, 4, 5], dtype=np.int32)
    prior_logits = np.asarray([0.1, 0.4, -0.2, 0.9, 0.0, -0.6], dtype=np.float32)
    candidates = np.asarray([1, 4, -1], dtype=np.int32)
    values = np.full((2, 3), np.nan, dtype=np.float32)
    values[0, :2] = [0.9, 0.1]
    values[1, :2] = [0.8, 0.2]
    target = row_target(
        LABEL, legal, prior_logits, candidates, values, DistillConfig(tau=0.05)
    )

    prior = _prior_from_logits(prior_logits)
    outside = np.array([True, False, True, True, False, True])
    assert np.allclose(target[outside], prior[outside], atol=1e-9)
    position = np.searchsorted(legal, [1, 4])
    assert target[position].sum() == pytest.approx(prior[position].sum(), abs=1e-9)


def test_tilt_target_with_tiny_tau_favors_the_best_summed_candidate() -> None:
    legal = np.asarray([2, 5, 9], dtype=np.int32)
    prior_logits = np.asarray([0.0, 0.0, 0.0], dtype=np.float32)
    candidates = np.asarray([2, 5, 9], dtype=np.int32)
    values = np.asarray([[0.10, 0.60, 0.40], [0.20, 0.55, 0.45]], dtype=np.float32)
    target = row_target(
        LABEL, legal, prior_logits, candidates, values, DistillConfig(tau=1e-6)
    )
    assert int(np.argmax(target)) == 1  # candidate 5 has the largest summed value


def test_tilt_target_with_padded_candidates() -> None:
    """K=3 candidate slots, only 2 valid; the NaN-padded column must be ignored."""

    legal = np.asarray([1, 2, 3, 4], dtype=np.int32)
    prior_logits = np.asarray([0.0, 0.2, -0.1, 0.3], dtype=np.float32)
    candidates = np.asarray([2, 4, -1], dtype=np.int32)
    values = np.full((2, 3), np.nan, dtype=np.float32)
    values[:, 0] = [0.3, 0.5]
    values[:, 1] = [0.1, 0.1]
    target = row_target(
        LABEL, legal, prior_logits, candidates, values, DistillConfig(tau=0.01)
    )
    assert target.shape == legal.shape
    assert np.all(np.isfinite(target))
    assert target.sum() == pytest.approx(1.0, abs=1e-6)


def test_policy_targets_rows_sum_to_one_and_offsets_match_legal_lengths() -> None:
    data = _stack_rows(
        legal=[[0, 1, 2], [0, 3], [1, 2, 3, 4]],
        prior_logits=[[0.1, 0.2, 0.3], [0.5, -0.1], [0.0, 0.4, -0.3, 0.2]],
        kind=[LABEL, ANCHOR, LABEL],
        candidates=[[0, 2], [-1, -1], [1, 4]],
        values=[
            [[0.4, 0.6], [0.3, 0.7]],
            [[np.nan, np.nan], [np.nan, np.nan]],
            [[0.2, 0.8], [0.5, 0.5]],
        ],
    )
    rows = np.arange(data.rows)
    flat, offsets = policy_targets(data, rows, DistillConfig())
    lengths = data.legal_offsets[1:] - data.legal_offsets[:-1]
    assert np.array_equal(np.diff(offsets), lengths)
    for position in range(len(rows)):
        piece = flat[offsets[position] : offsets[position + 1]]
        assert piece.sum() == pytest.approx(1.0, abs=1e-5)


# -- 2. hard-mode targets and ANCHOR rows ------------------------------------
def test_hard_mode_targets_the_first_candidate_on_a_tie() -> None:
    legal = np.asarray([0, 1, 2], dtype=np.int32)
    prior_logits = np.asarray([0.0, 0.0, 0.0], dtype=np.float32)
    candidates = np.asarray([2, 0, -1], dtype=np.int32)
    values = np.full((2, 3), np.nan, dtype=np.float32)
    values[:, :2] = 0.5  # exact tie between candidates 2 and 0
    target = row_target(
        LABEL, legal, prior_logits, candidates, values, DistillConfig(mode="hard")
    )
    expected = np.zeros(3, dtype=np.float64)
    expected[np.searchsorted(legal, 2)] = 1.0  # first candidate in candidate order
    assert np.array_equal(target, expected)


def test_hard_mode_targets_the_search_choice_when_not_tied() -> None:
    legal = np.asarray([3, 6, 9], dtype=np.int32)
    prior_logits = np.asarray([0.1, 0.2, 0.3], dtype=np.float32)
    candidates = np.asarray([9, 3, 6], dtype=np.int32)
    values = np.asarray([[0.1, 0.9, 0.2], [0.2, 0.8, 0.1]], dtype=np.float32)
    target = row_target(
        LABEL, legal, prior_logits, candidates, values, DistillConfig(mode="hard")
    )
    expected = np.zeros(3, dtype=np.float64)
    expected[np.searchsorted(legal, 3)] = 1.0  # candidate 3 has the largest sum
    assert np.array_equal(target, expected)


def test_anchor_rows_target_the_prior_in_either_mode() -> None:
    legal = np.asarray([0, 2, 5], dtype=np.int32)
    prior_logits = np.asarray([0.3, -0.2, 1.0], dtype=np.float32)
    candidates = np.asarray([0, 2, -1], dtype=np.int32)  # must be ignored for ANCHOR
    values = np.asarray([[0.1, 0.9, np.nan], [0.2, 0.8, np.nan]], dtype=np.float32)
    expected = _prior_from_logits(prior_logits)
    for mode in ("tilt", "hard"):
        target = row_target(
            ANCHOR, legal, prior_logits, candidates, values, DistillConfig(mode=mode)
        )
        assert np.allclose(target, expected, atol=1e-9)


# -- 3. search_choice ---------------------------------------------------------
def test_search_choice_picks_the_first_argmax_and_flags_short_rows() -> None:
    candidates = np.asarray(
        [
            [1, 2, 3],  # three valid, distinct summed values
            [4, 5, -1],  # two valid, tied summed values -> first wins
            [6, -1, -1],  # only one valid -> no choice
            [-1, -1, -1],  # none valid -> no choice
        ],
        dtype=np.int32,
    )
    values = np.full((4, 2, 3), np.nan, dtype=np.float32)
    values[0] = [[0.1, 0.5, 0.3], [0.2, 0.4, 0.3]]  # sums 0.3, 0.9, 0.6 -> index 1
    values[1, :, :2] = [[0.4, 0.4], [0.6, 0.6]]  # sums 1.0, 1.0 -> tie, index 0
    values[2, :, :1] = [[0.9], [0.9]]
    choice = search_choice(candidates, values)
    assert choice.tolist() == [1, 0, -1, -1]


# -- 4. legal_log_probs -------------------------------------------------------
def test_legal_log_probs_matches_masked_log_softmax_with_padding() -> None:
    torch.manual_seed(0)
    network = PolicyValueNetwork(12, observation_size=OBSERVATION_SIZE, hidden=(16,))
    network.eval()
    rng = np.random.default_rng(0)
    observations = torch.from_numpy(
        rng.integers(0, 50, size=(2, OBSERVATION_SIZE)).astype(np.int32)
    )
    with torch.no_grad():
        hidden = network.trunk(observations)
        full_logits = network.policy_head(hidden)
    index = torch.as_tensor([[0, 3, 7, 11], [2, 5, 0, 0]], dtype=torch.int64)
    valid = torch.as_tensor([[True, True, True, True], [True, True, False, False]])
    with torch.no_grad():
        result = legal_log_probs(network, hidden, index, valid)
    for row in range(2):
        legal_row = index[row][valid[row]]
        expected = torch.log_softmax(full_logits[row, legal_row], dim=-1)
        assert torch.allclose(result[row][valid[row]], expected, atol=1e-5)


# -- 5. distill actually learns -----------------------------------------------
def _bit_flip_data(
    rng: np.random.Generator, *, games: int, rows_per_game: int
) -> ExpertData:
    """LABEL rows whose search value favours the candidate matching ``observation[0]``.

    ``observation[0]`` is 0 or 1; the favoured candidate (of the row's two,
    the only two legal actions) alternates with it by a clear 0.05 margin, so
    a network that reads that one bit reaches near-perfect ``agree_target``.
    """

    total = games * rows_per_game
    observations = np.zeros((total, OBSERVATION_SIZE), dtype=np.uint8)
    bits = rng.integers(0, 2, size=total)
    observations[:, 0] = bits
    legal_rows = [[2, 5] for _ in range(total)]
    prior_rows = [[0.0, 0.0] for _ in range(total)]
    candidate_rows = [[2, 5] for _ in range(total)]
    value_rows = [
        [[0.55, 0.50], [0.55, 0.50]] if bit == 0 else [[0.50, 0.55], [0.50, 0.55]]
        for bit in bits
    ]
    game_seed = [index // rows_per_game for index in range(total)]
    return _stack_rows(
        legal=legal_rows,
        prior_logits=prior_rows,
        kind=[LABEL] * total,
        candidates=candidate_rows,
        values=value_rows,
        observations=observations,
        game_seed=game_seed,
        action_size=12,
    )


def test_distill_learns_a_clean_bit_signal_and_keeps_the_best_epoch() -> None:
    # 100 rows/game (not ~10) so the fixed minibatch_size=64 below still gives
    # enough gradient steps per epoch for max_grad_norm=1.0 to move the
    # policy head meaningfully in 4 epochs.
    rng = np.random.default_rng(0)
    data = _bit_flip_data(rng, games=40, rows_per_game=100)
    assert int((data.game_seed % 10 == 0).sum()) > 0  # some games are held out

    torch.manual_seed(1)
    network = PolicyValueNetwork(12, hidden=(16,))
    config = DistillConfig(
        tau=0.005,
        max_epochs=4,
        minibatch_size=64,
        learning_rate=1e-2,
        warmup_steps=1,
        threads=1,
    )
    report = distill(network, data, config)

    assert report.best_epoch >= 1
    best = report.per_epoch[report.best_epoch - 1]
    assert (
        best.agree_target > report.before.agree_target + 0.2
        or best.agree_target > 0.9
    )

    heldout_rows = np.flatnonzero(data.heldout(config.heldout_modulus))
    replayed = evaluate(network, data, heldout_rows, config)
    assert replayed.objective == pytest.approx(best.objective, abs=1e-6)


# -- 6. heldout() -------------------------------------------------------------
def test_heldout_is_determined_only_by_game_seed_modulus() -> None:
    data = _stack_rows(
        legal=[[0, 1]] * 7,
        prior_logits=[[0.0, 0.0]] * 7,
        kind=[LABEL] * 7,
        candidates=[[0, 1]] * 7,
        values=[[[0.2, 0.3], [0.25, 0.35]]] * 7,
        game_seed=[0, 1, 5, 10, 15, 20, 7],
    )
    assert data.heldout().tolist() == [True, False, False, True, False, True, False]
    assert data.heldout(5).tolist() == [True, False, True, True, True, True, False]


# -- 7. evaluate ---------------------------------------------------------------
def test_evaluate_against_itself_has_zero_diff_and_matches_stored_prior() -> None:
    torch.manual_seed(2)
    network = PolicyValueNetwork(8, hidden=(16,))
    network.eval()
    legal = np.asarray([1, 3, 5], dtype=np.int32)

    def prior_for(observation: np.ndarray) -> list[float]:
        with torch.no_grad():
            hidden = network.trunk(
                torch.from_numpy(observation.astype(np.int32)).unsqueeze(0)
            )
            logits = network.action_logits(
                hidden, torch.from_numpy(legal.astype(np.int64))
            )
        result: list[float] = logits[0].numpy().astype(np.float32).tolist()
        return result

    rng = np.random.default_rng(3)
    observations = rng.integers(0, 40, size=(4, OBSERVATION_SIZE)).astype(np.uint8)
    prior_rows = [prior_for(observations[i]) for i in range(4)]
    data = _stack_rows(
        legal=[legal.tolist()] * 4,
        prior_logits=prior_rows,
        kind=[LABEL, ANCHOR, LABEL, ANCHOR],
        candidates=[[1, 3], [-1, -1], [1, 5], [-1, -1]],
        values=[
            [[0.2, 0.3], [0.25, 0.35]],
            [[np.nan, np.nan], [np.nan, np.nan]],
            [[0.4, 0.1], [0.5, 0.2]],
            [[np.nan, np.nan], [np.nan, np.nan]],
        ],
        observations=observations,
        game_seed=[1, 1, 2, 2],
        z=[0.5, -0.5, 1.0, -1.0],
        action_size=8,
    )
    config = DistillConfig()
    rows = np.arange(data.rows)
    stats = evaluate(network, data, rows, config)
    for key in ("agree_target", "value_error"):
        assert clustered_difference(stats, stats, key) == (0.0, 0.0, 0.0)

    checked = evaluate(network, data, rows, config, check_prior=True)
    assert checked.prior_max_abs_diff <= 1e-5


# -- 8. save_candidate ---------------------------------------------------------
def test_save_candidate_round_trips_and_produces_working_agents(tmp_path: Path) -> None:
    config = RulesetConfig()
    codec = ActionCodec(config)
    torch.manual_seed(4)
    network = PolicyValueNetwork(codec.size, hidden=(16,))
    parent = tmp_path / "parent.pt"
    save_checkpoint(
        parent, network, ruleset=config.identifier, iteration=3, codec=codec
    )

    out = tmp_path / "candidate.pt"
    save_candidate(out, network, parent=parent, metadata={"tag": "t"})

    reloaded, info = load_checkpoint(out)
    assert info.iteration == 3
    for (name, expected), (_, actual) in zip(
        network.state_dict().items(), reloaded.state_dict().items(), strict=True
    ):
        assert torch.equal(expected, actual), name

    checkpoint_agent = make_agent(f"checkpoint:{out}", 0)
    search_agent = make_agent(f"search:{out}", 0)
    assert checkpoint_agent is not None
    assert search_agent is not None

    engine = UprisingRulesEngine()
    state = engine.reset(config, 3)
    chance = ChanceResolver(seed=3)
    decision = engine.current_decision(state)
    while isinstance(decision, ChanceDecision):
        state = engine.apply(state, chance.resolve(decision)).state
        decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    owner = decision.owner
    actions = engine.legal_actions(state, owner)
    view = engine.observe(state, owner)
    chosen = checkpoint_agent.choose_action(view, actions)
    assert chosen in actions


# -- 9. CLI end to end ----------------------------------------------------------
def _real_prior_logits(
    network: PolicyValueNetwork, observation: np.ndarray, legal: np.ndarray
) -> np.ndarray:
    with torch.no_grad():
        hidden = network.trunk(
            torch.from_numpy(observation.astype(np.int32)).unsqueeze(0)
        )
        logits = network.action_logits(hidden, torch.from_numpy(legal.astype(np.int64)))
    result: np.ndarray = logits[0].numpy().astype(np.float32)
    return result


def _cli_game(
    network: PolicyValueNetwork, rng: np.random.Generator, *, seed: int
) -> LabelledGame:
    """Five rows of one game: real prior logits from ``network``, tiny candidates."""

    rows = []
    legal = np.asarray([0, 1, 2, 3, 4], dtype=np.int32)
    for index in range(5):
        observation = rng.integers(0, 40, size=OBSERVATION_SIZE).astype(np.uint8)
        prior = _real_prior_logits(network, observation, legal)
        kind = LABEL if index % 2 == 0 else ANCHOR
        candidates = np.full(2, -1, dtype=np.int32)
        values = np.full((2, 2), np.nan, dtype=np.float32)
        played = int(legal[0])
        if kind == LABEL:
            candidates[:] = [0, 2]
            values[:, 0] = [0.3, 0.4]
            values[:, 1] = [0.5, 0.6]
            played = 2
        rows.append(
            LabelRow(
                kind=kind,
                seat=0,
                round_number=1,
                decision_index=index,
                observation=observation,
                legal=legal,
                prior_logits=prior,
                candidates=candidates,
                values=values,
                played=played,
            )
        )
    return LabelledGame(
        game_seed=seed,
        rows=tuple(rows),
        rewards=(WINNER_REWARD, LOSER_REWARD, LOSER_REWARD, LOSER_REWARD),
        ranks=(1, 2, 3, 4),
        victory_points=(10, 8, 6, 4),
        leader_ids=("a", "b", "c", "d"),
        rounds=5,
        decisions=(5, 0, 0, 0),
        seconds=0.1,
        guard_skips=0,
        played_is_first=0,
    )


def test_cli_train_and_metrics_round_trip_on_synthetic_shards(tmp_path: Path) -> None:
    config = RulesetConfig()
    codec = ActionCodec(config)
    torch.manual_seed(5)
    parent_network = PolicyValueNetwork(codec.size, hidden=(16,))
    parent_path = tmp_path / "parent.pt"
    save_checkpoint(
        parent_path, parent_network, ruleset=config.identifier, iteration=1, codec=codec
    )

    data_dir = tmp_path / "data"
    rng = np.random.default_rng(6)
    meta = run_meta(
        str(parent_path),
        LabelConfig(rollouts=2, candidates=2),
        codec.size,
        config.identifier,
    )
    for seed in (10, 11, 12):  # seed 10 is held out (game_seed % 10 == 0)
        game = _cli_game(parent_network, rng, seed=seed)
        write_game(data_dir / f"g{seed}.npz", game, meta)

    candidate_path = tmp_path / "candidate.pt"
    report_path = tmp_path / "report.json"
    train_code = main(
        [
            "train",
            "--init",
            str(parent_path),
            "--data",
            str(data_dir),
            "--out",
            str(candidate_path),
            "--report",
            str(report_path),
            "--epochs",
            "1",
            "--threads",
            "1",
        ]
    )
    assert train_code == 0
    assert candidate_path.exists()
    assert report_path.exists()

    metrics_path = tmp_path / "metrics.json"
    metrics_code = main(
        [
            "metrics",
            "--student",
            str(candidate_path),
            "--reference",
            str(parent_path),
            "--data",
            str(data_dir),
            "--json",
            str(metrics_path),
            "--threads",
            "1",
        ]
    )
    assert metrics_code == 0
    assert metrics_path.exists()
    result = json.loads(metrics_path.read_text())
    assert {"pass", "checks", "student", "reference"} <= result.keys()
    assert result["checks"]["G0e_pipeline"] is True
