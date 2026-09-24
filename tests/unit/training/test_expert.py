"""Tests for expert-iteration labelling (``training.expert``)."""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.adapters.observation_encoding import (  # noqa: E402
    OBSERVATION_SIZE,
)
from dune_imperium.adapters.pettingzoo_env import (  # noqa: E402
    LOSER_REWARD,
    WINNER_REWARD,
)
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision  # noqa: E402
from dune_imperium.core.state import GamePhase  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.expert import (  # noqa: E402
    ANCHOR,
    LABEL,
    LabelConfig,
    LabelledGame,
    LabellingAgent,
    LabelRow,
    read_shards,
    run_meta,
    validate_game,
    write_game,
)
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.torch_policy import load_network_agent  # noqa: E402

ALL = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
)


def _checkpoint(tmp_path: Path, config: RulesetConfig = ALL) -> str:
    torch.manual_seed(0)
    network = PolicyValueNetwork(ActionCodec(config).size, hidden=(32,))
    path = tmp_path / "teacher.pt"
    save_checkpoint(
        path,
        network,
        ruleset=config.identifier,
        iteration=1,
        codec=ActionCodec(config),
    )
    return str(path)


def test_labelling_seats_play_like_greedy_seats_and_record_aligned_rows(
    tmp_path: Path,
) -> None:
    """Labelling never changes a move, and every row is internally aligned.

    Four labelling seats and four plain greedy seats of the same checkpoint
    answer the same decisions; each stored prior must be the network's own
    logits for the stored (ascending) legal set, recomputed from the stored
    observation, and a LABEL row's first candidate is the move played.
    """

    teacher = _checkpoint(tmp_path)
    config = LabelConfig(
        label_probability=1.0, anchor_probability=1.0, rollouts=1, candidates=2
    )
    labellers = [LabellingAgent(teacher, seed=seat, config=config) for seat in range(4)]
    plain = [load_network_agent(teacher) for _ in range(4)]
    engine = UprisingRulesEngine()
    state = engine.reset(ALL, 11)
    chance = ChanceResolver(seed=11)
    decisions = 0
    while decisions < 150 and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        owner = decision.owner
        actions = engine.legal_actions(state, owner)
        view = engine.observe(state, owner)
        choice = labellers[owner].choose_action_with_state(state, view, actions)
        assert choice == plain[owner].choose_action(view, actions)
        state = engine.apply(state, choice, legal_actions=actions).state
        decisions += 1

    rows = [row for agent in labellers for row in agent.rows]
    labels = [row for row in rows if row.kind == LABEL]
    anchors = [row for row in rows if row.kind == ANCHOR]
    assert len(labels) >= 5 and anchors
    network = labellers[0].network
    for row in rows:
        assert row.observation.dtype == np.uint8
        assert row.observation.shape == (OBSERVATION_SIZE,)
        assert np.all(np.diff(row.legal) > 0)
        assert row.played in set(row.legal.tolist())
        with torch.no_grad():
            hidden = network.trunk(
                torch.from_numpy(row.observation.astype(np.int32)).unsqueeze(0)
            )
            again = network.action_logits(
                hidden, torch.from_numpy(row.legal.astype(np.int64))
            )[0].numpy()
        assert np.allclose(again, row.prior_logits, atol=1e-5)
    for row in labels:
        valid = row.candidates >= 0
        assert valid.sum() == 2
        assert set(row.candidates[valid].tolist()) <= set(row.legal.tolist())
        assert row.candidates[0] == row.played
        assert row.values.shape == (1, 2) and np.all(np.isfinite(row.values))
    for row in anchors:
        assert np.all(row.candidates == -1) and np.all(np.isnan(row.values))


def _row(
    kind: int, legal: list[int], played: int, candidates: list[int], worlds: int = 2
) -> LabelRow:
    width = 3
    padded = np.full(width, -1, dtype=np.int32)
    padded[: len(candidates)] = candidates
    values = np.full((worlds, width), np.nan, dtype=np.float32)
    values[:, : len(candidates)] = 0.25
    return LabelRow(
        kind=kind,
        seat=1,
        round_number=2,
        decision_index=7,
        observation=np.arange(OBSERVATION_SIZE, dtype=np.int64).astype(np.uint8),
        legal=np.asarray(legal, dtype=np.int32),
        prior_logits=np.linspace(0.0, 1.0, len(legal), dtype=np.float32),
        candidates=padded,
        values=values,
        played=played,
    )


def _game(seed: int, rows: list[LabelRow]) -> LabelledGame:
    return LabelledGame(
        game_seed=seed,
        rows=tuple(rows),
        rewards=(LOSER_REWARD, WINNER_REWARD, LOSER_REWARD, LOSER_REWARD),
        ranks=(2, 1, 3, 4),
        victory_points=(9, 11, 7, 5),
        leader_ids=("a", "b", "c", "d"),
        rounds=9,
        decisions=(100, 120, 110, 90),
        seconds=1.0,
        guard_skips=0,
        played_is_first=1,
    )


def test_game_shards_round_trip_and_refuse_bad_input(tmp_path: Path) -> None:
    meta = run_meta("teacher.pt", LabelConfig(rollouts=2), 50, "ruleset")
    first = _game(10, [_row(LABEL, [3, 7, 9], 7, [7, 3]), _row(ANCHOR, [1, 4], 4, [])])
    second = _game(11, [_row(LABEL, [2, 5], 2, [2, 5])])
    for game in (first, second):
        validate_game(game, 50)
        write_game(tmp_path / f"g{game.game_seed}.npz", game, meta)

    data = read_shards([tmp_path / "g10.npz", tmp_path / "g11.npz"], weights=[1.0, 0.5])
    assert data.rows == 3
    assert data.legal_offsets.tolist() == [0, 3, 5, 7]
    assert data.legal_indices.tolist() == [3, 7, 9, 1, 4, 2, 5]
    assert data.kind.tolist() == [LABEL, ANCHOR, LABEL]
    assert data.candidates[0].tolist() == [7, 3, -1]
    assert data.values.shape == (3, 2, 3)
    assert data.z.tolist() == [WINNER_REWARD, WINNER_REWARD, WINNER_REWARD]
    assert data.weight.tolist() == [1.0, 1.0, 0.5]
    assert data.heldout().tolist() == [True, True, False]
    assert data.seat_decisions.tolist() == [120, 120, 120]

    with pytest.raises(ValueError, match="duplicate game seed"):
        read_shards([tmp_path / "g10.npz", tmp_path / "g10.npz"])
    with pytest.raises(ValueError, match="ascending"):
        validate_game(_game(12, [_row(LABEL, [7, 3], 7, [7, 3])]), 50)
    with pytest.raises(ValueError, match="not offered"):
        validate_game(_game(13, [_row(ANCHOR, [3, 7], 8, [])]), 50)
    with pytest.raises(ValueError, match="candidates"):
        validate_game(_game(14, [_row(LABEL, [3, 7], 7, [7, 9])]), 50)
    wide = _game(15, [_row(LABEL, [2, 5], 2, [2, 5], worlds=4)])
    write_game(tmp_path / "g15.npz", wide, meta)
    with pytest.raises(ValueError, match="search shape"):
        read_shards([tmp_path / "g10.npz", tmp_path / "g15.npz"])
    elsewhere = run_meta("teacher.pt", LabelConfig(rollouts=2), 60, "ruleset")
    write_game(
        tmp_path / "g16.npz", _game(16, [_row(LABEL, [2, 5], 2, [2, 5])]), elsewhere
    )
    with pytest.raises(ValueError, match="differs"):
        read_shards([tmp_path / "g10.npz", tmp_path / "g16.npz"])
