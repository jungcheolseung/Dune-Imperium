"""Tests for expert-iteration labelling (``training.expert``)."""

import json
import random
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
from dune_imperium.agents import Agent, StateAgent, make_agent  # noqa: E402
from dune_imperium.cli.expert import (  # noqa: E402
    _ruleset_options,
    build_parser,
)
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision  # noqa: E402
from dune_imperium.core.state import GamePhase  # noqa: E402
from dune_imperium.evaluation.tournament import (  # noqa: E402
    play_match,
    tournament_specs,
)
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.rules.frames import FrameKind  # noqa: E402
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.expert import (  # noqa: E402
    ANCHOR,
    COLLECTION_MAX_STEPS,
    EXPERT_FORMAT,
    LABEL,
    TABLE_RULE,
    LabelConfig,
    LabelledGame,
    LabellingAgent,
    LabelRow,
    collect_to_directory,
    collection_specs,
    decision_frame,
    game_arrays,
    label_game,
    read_shards,
    run_meta,
    shard_paths,
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
# Every option of the exit-v2 collection (the full ruleset with the draft).
FULL = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
    leader_draft=True,
)
FULL_OPTIONS = {
    "go_to_11": True,
    "epic_game": True,
    "arrakeen_scouts": True,
    "leader_draft": True,
}


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
    observation, and a LABEL row's first candidate is the move played unless
    the seat's cycle guard steered it off that move.
    """

    teacher = _checkpoint(tmp_path)
    config = LabelConfig(
        label_probability=1.0, anchor_probability=1.0, rollouts=1, candidates=2
    )
    labellers = [LabellingAgent(teacher, seed=seat, config=config) for seat in range(4)]
    plain = [load_network_agent(teacher) for _ in range(4)]
    engine = UprisingRulesEngine()
    # Game 12; 11 until observation v33 grew by the B3d-2a review's 139
    # columns, which drew the untrained teacher's weights anew: its game
    # met its first Agent-effect decision (an ANCHOR row) only at decision
    # 195, past this walk.
    state = engine.reset(ALL, 12)
    chance = ChanceResolver(seed=12)
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
        if row.candidates[0] != row.played:
            # The greedy seat's cycle guard (keyed by the observation alone)
            # steered it off the top-ranked move it already made here; the
            # pipeline reports these as played_eq_cand0 < 1. The ranking
            # itself must still put the higher prior first.
            legal = row.legal.tolist()
            top = row.prior_logits[legal.index(int(row.candidates[0]))]
            assert top >= row.prior_logits[legal.index(int(row.played))]
        assert row.values.shape == (1, 2) and np.all(np.isfinite(row.values))
    for row in anchors:
        assert np.all(row.candidates == -1) and np.all(np.isnan(row.values))


def _row(
    kind: int,
    legal: list[int],
    played: int,
    candidates: list[int],
    worlds: int = 2,
    frame: str = "",
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
        frame=frame,
    )


def _game(
    seed: int,
    rows: list[LabelRow],
    *,
    seat_agents: tuple[str, ...] = (),
    labelled: tuple[bool, ...] = (),
) -> LabelledGame:
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
        seat_agents=seat_agents,
        labelled=labelled,
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


def test_only_complete_shards_are_listed(tmp_path: Path) -> None:
    """A write interrupted by a kill leaves nothing a shard listing picks up.

    The temporary file is hidden and never ends in ``.npz``; an older
    ``g<seed>.npz.tmp.npz`` leftover is ignored too, since reading a
    truncated one would fail every later training run.
    """

    meta = run_meta("teacher.pt", LabelConfig(rollouts=2), 50, "ruleset")
    write_game(tmp_path / "g20.npz", _game(20, [_row(LABEL, [2, 5], 2, [2, 5])]), meta)
    (tmp_path / "g21.npz.tmp.npz").write_bytes(b"truncated")
    (tmp_path / ".g22.npz.partial").write_bytes(b"truncated")

    assert [p.name for p in shard_paths(tmp_path)] == ["g20.npz"]
    assert not list(tmp_path.glob(".g20*"))
    assert read_shards(shard_paths(tmp_path)).rows == 1


# -- exit-v2: mixed tables, the full ruleset, decision frames -------------------
def test_labelling_seats_at_a_mixed_full_table_choose_like_checkpoint_seats(
    tmp_path: Path,
) -> None:
    """Two labelling seats and two ``app_ai`` seats of the full ruleset.

    A labelling seat is built as a tournament ``checkpoint:`` seat of the same
    seed is, so over the first ~200 decisions every one of its choices equals
    the plain seat's, while it records rows (each with the frame of its
    decision) and the ``app_ai`` seats record nothing. (The first 240 since
    stage B2: the Conflict reward windows' rows are decisions too, and seat
    1 decided only 19 times in the first 200.)
    """

    teacher = _checkpoint(tmp_path, FULL)
    config = LabelConfig(
        label_probability=1.0, anchor_probability=1.0, rollouts=1, candidates=2
    )
    labelling = (1, 3)
    policy_seed = 900_017
    labellers: dict[int, LabellingAgent] = {}
    plain: dict[int, Agent] = {}
    opponents: dict[int, StateAgent] = {}
    for seat in range(4):
        seed = policy_seed + seat
        if seat in labelling:
            labellers[seat] = LabellingAgent(
                teacher, seed=seed, config=config, game_config=FULL
            )
            plain[seat] = make_agent(f"checkpoint:{teacher}", seed, FULL)
        else:
            opponent = make_agent("app_ai", seed, FULL)
            assert isinstance(opponent, StateAgent)
            opponents[seat] = opponent
    engine = UprisingRulesEngine()
    state = engine.reset(FULL, 17)
    chance = ChanceResolver(seed=17)
    decisions = compared = 0
    seen_rows = dict.fromkeys(labelling, 0)
    while decisions < 240 and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        owner = decision.owner
        actions = engine.legal_actions(state, owner)
        view = engine.observe(state, owner)
        if owner in labellers:
            expected_frame = (
                FrameKind(state.decision_stack[-1].kind).value
                if state.decision_stack
                else f"phase:{state.phase.value}"
            )
            assert decision_frame(state) == expected_frame
            choice = labellers[owner].choose_action_with_state(state, view, actions)
            assert choice == plain[owner].choose_action(view, actions)
            compared += 1
            rows = labellers[owner].rows
            for row in rows[seen_rows[owner] :]:
                assert row.frame == expected_frame and row.seat == owner
            seen_rows[owner] = len(rows)
        else:
            choice = opponents[owner].choose_action_with_state(state, view, actions)
        state = engine.apply(state, choice, legal_actions=actions).state
        decisions += 1

    assert compared >= 40
    for seat, agent in labellers.items():
        labels = [row for row in agent.rows if row.kind == LABEL]
        assert labels and agent.decisions > 20
        assert all(row.seat == seat and row.frame for row in agent.rows)
    frames = {row.frame for agent in labellers.values() for row in agent.rows}
    assert "turn" in frames and len(frames) >= 2


def test_label_game_at_a_mixed_table_plays_the_game_play_match_plays(
    tmp_path: Path,
) -> None:
    """The same spec through ``label_game`` and through ``play_match``.

    Labelling changes no move and the ``app_ai`` seats play as in a
    tournament, so standings, victory points, per-seat decision counts and
    Leaders are those of the metered match. A full game with the tiny
    network takes about 3 s, so the whole game is compared.
    """

    teacher = _checkpoint(tmp_path, FULL)
    (spec,) = collection_specs(
        teacher,
        start_seed=2,
        games=1,
        opponent="app_ai",
        mixed_share=1.0,
        **FULL_OPTIONS,
    )
    kinds = [kind == f"checkpoint:{teacher}" for kind in spec.seat_agents]
    assert sum(kinds) == 2 and spec.leader_draft
    config = LabelConfig(
        label_probability=0.02, anchor_probability=0.05, rollouts=1, candidates=2
    )

    played = play_match(spec)
    labelled = label_game(spec, teacher, config)

    assert labelled.ranks == tuple(seat.rank for seat in played.seats)
    assert labelled.victory_points == tuple(
        seat.victory_points for seat in played.seats
    )
    assert labelled.decisions == tuple(seat.decisions for seat in played.seats)
    assert labelled.leader_ids == tuple(seat.leader_id for seat in played.seats)
    assert labelled.rounds == played.rounds
    assert labelled.seat_agents == spec.seat_agents
    assert labelled.labelled == tuple(kinds)
    assert labelled.mixed
    assert labelled.rows
    assert {row.seat for row in labelled.rows} <= {
        seat for seat, mine in enumerate(kinds) if mine
    }
    validate_game(labelled, ActionCodec(FULL).size)

    meta = run_meta(teacher, config, ActionCodec(FULL).size, FULL.identifier)
    write_game(tmp_path / "g2.npz", labelled, meta)
    data = read_shards([tmp_path / "g2.npz"])
    assert (
        data.rows == len(labelled.rows) and data.action_size == ActionCodec(FULL).size
    )
    assert data.frame.tolist() == [row.frame for row in labelled.rows]


def test_collect_to_directory_labels_mixed_games_of_the_games_own_catalog(
    tmp_path: Path,
) -> None:
    """A teacher trained on a narrower catalog still writes the game's rows.

    The shards index the full ruleset's action catalog, which is wider than
    the file's, so the header's ``action_size`` must be the game's.
    """

    teacher = _checkpoint(tmp_path, ALL)
    out = tmp_path / "shards"
    config = LabelConfig(
        label_probability=0.05, anchor_probability=0.05, rollouts=1, candidates=2
    )
    # Stage B3d-3 resized the catalog (the refusals are rows now), so the
    # seeded teacher network, and with it the game of seed 2, changed: that
    # game no longer meets a decision of untrained templates only. Seed 3's
    # does (6 of them).
    summary = collect_to_directory(
        teacher,
        out,
        start_seed=3,
        games=1,
        workers=1,
        config=config,
        opponent="app_ai",
        mixed_share=1.0,
        **FULL_OPTIONS,
    )
    assert summary["games"] == 1 and summary["failures"] == 0
    assert summary["mixed_games"] == 1 and summary["search_shape"] == [1, 2]
    assert summary["played_eq_cand0"] is not None

    (path,) = shard_paths(out)
    with np.load(path, allow_pickle=False) as handle:
        header = json.loads(str(handle["meta_json"]))
        assert handle["g_labelled"].tolist() == [
            kind.startswith("checkpoint:") for kind in header["seat_agents"]
        ]
    assert header["format"] == EXPERT_FORMAT == 2
    assert header["opponent"] == "app_ai" and header["mixed_share"] == 1.0
    assert header["table_rule"] == TABLE_RULE
    assert header["ruleset"] == FULL.identifier
    assert header["action_size"] == ActionCodec(FULL).size > ActionCodec(ALL).size
    assert header["leader_draft"] is True
    data = read_shards([path])
    assert data.frame.size > 0
    # Decisions made only of templates the file never trained on (the draft
    # and Scouts here) are not searched, so they are never labelled.
    assert int(str(summary["untrained_skips"])) > 0
    assert header["untrained_skips"] == summary["untrained_skips"]
    greedy = load_network_agent(teacher, FULL)
    for row in np.flatnonzero(data.kind == LABEL):
        start, stop = data.legal_offsets[row], data.legal_offsets[row + 1]
        assert not greedy.untrained_only(data.legal_indices[start:stop].tolist())


def _tables(opponent: str | None, *, games: int = 400, share: float = 0.5):  # type: ignore[no-untyped-def]
    return collection_specs(
        "teacher.pt",
        start_seed=1000,
        games=games,
        opponent=opponent,
        mixed_share=share,
    )


def test_collection_specs_draw_each_seeds_table_from_its_own_rule() -> None:
    kind = "checkpoint:teacher.pt"
    specs = _tables("app_ai")
    assert [spec.game_seed for spec in specs] == list(range(1000, 1400))
    mixed = [spec for spec in specs if "app_ai" in spec.seat_agents]
    assert 0.4 <= len(mixed) / len(specs) <= 0.6
    for spec in specs:
        rng = random.Random(f"exit-v2-table:{spec.game_seed}")
        is_mixed = rng.random() < 0.5
        learners = (0, 2) if rng.randrange(2) == 0 else (1, 3)
        if is_mixed:
            assert spec.seat_agents == tuple(
                kind if seat in learners else "app_ai" for seat in range(4)
            )
        else:
            assert spec.seat_agents == (kind,) * 4
    held_out = [spec for spec in specs if spec.game_seed % 10 == 0]
    teacher_seats = {
        frozenset(i for i, k in enumerate(spec.seat_agents) if k == kind)
        for spec in held_out
    }
    assert teacher_seats == {
        frozenset({0, 1, 2, 3}),
        frozenset({0, 2}),
        frozenset({1, 3}),
    }
    assert _tables("app_ai") == specs  # deterministic across calls
    # The same lineup and seed as a tournament builds them: policy seeds and
    # Leader rosters included.
    for spec in specs[:25]:
        (reference,) = tournament_specs(
            agents=spec.seat_agents,
            games=1,
            rulesets=(True,),
            start_seed=spec.game_seed,
            rotate_seats=False,
            rotate_leaders=True,
            promo_cards=True,
            bloodlines=True,
            tech_module=True,
            immortality=True,
            max_steps=COLLECTION_MAX_STEPS,
        )
        assert spec == reference


def test_collection_specs_mixed_share_extremes_and_no_opponent() -> None:
    kind = "checkpoint:teacher.pt"
    assert all(s.seat_agents == (kind,) * 4 for s in _tables(None, games=40))
    # Without an opponent the share is moot.
    assert _tables(None, games=40, share=0.9) == _tables(None, games=40)
    assert not any(
        "app_ai" in s.seat_agents for s in _tables("app_ai", games=60, share=0.0)
    )
    assert all(
        "app_ai" in s.seat_agents for s in _tables("app_ai", games=60, share=1.0)
    )


def test_collection_specs_defaults_reproduce_the_first_collection() -> None:
    expected = tournament_specs(
        agents=("checkpoint:teacher.pt",) * 4,
        games=7,
        rulesets=(True,),
        start_seed=40,
        rotate_seats=False,
        rotate_leaders=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        max_steps=COLLECTION_MAX_STEPS,
    )
    assert collection_specs("teacher.pt", start_seed=40, games=7) == expected
    assert all(s.leader_ids is not None and not s.leader_draft for s in expected)


def test_collection_specs_pass_the_ruleset_options_through() -> None:
    drafted = collection_specs(
        "teacher.pt", start_seed=3, games=2, opponent="app_ai", **FULL_OPTIONS
    )
    for spec in drafted:
        # The draft deals its own Leaders; no roster is fixed.
        assert spec.leader_ids is None
        assert spec.config == FULL
    plain = collection_specs(
        "teacher.pt", start_seed=3, games=1, choam=False, promo_cards=False
    )
    assert plain[0].config == RulesetConfig(
        bloodlines=True, tech_module=True, immortality=True
    )
    for bad in (
        {"opponent": "no_such_agent"},
        {"opponent": "app_ai", "mixed_share": 1.5},
        {"games": 0},
        {"tech_module": True, "bloodlines": False},
    ):
        arguments: dict[str, object] = {"start_seed": 1, "games": 1, **bad}
        with pytest.raises(ValueError):
            collection_specs("teacher.pt", **arguments)  # type: ignore[arg-type]


def test_format_2_shards_round_trip_frames_and_labelled_seats(tmp_path: Path) -> None:
    meta = run_meta(
        "teacher.pt",
        LabelConfig(rollouts=2),
        50,
        "ruleset",
        opponent="app_ai",
        mixed_share=0.25,
    )
    assert meta["opponent"] == "app_ai" and meta["mixed_share"] == 0.25
    assert meta["table_rule"] == "random.Random('exit-v2-table:<seed>')"
    assert {"teacher", "ruleset", "action_size", "label_config"} <= meta.keys()
    agents = ("app_ai", "checkpoint:teacher.pt", "app_ai", "checkpoint:teacher.pt")
    labelled = (False, True, False, True)
    first = _game(
        10,
        [
            _row(LABEL, [3, 7, 9], 7, [7, 3], frame="turn"),
            _row(ANCHOR, [1, 4], 4, [], frame="agent_effects"),
        ],
        seat_agents=agents,
        labelled=labelled,
    )
    second = _game(
        11,
        [_row(LABEL, [2, 5], 2, [2, 5], frame="phase:setup")],
        seat_agents=agents,
        labelled=labelled,
    )
    for game in (first, second):
        validate_game(game, 50)
        write_game(tmp_path / f"g{game.game_seed}.npz", game, meta)

    with np.load(tmp_path / "g10.npz", allow_pickle=False) as handle:
        header = json.loads(str(handle["meta_json"]))
        assert handle["g_labelled"].tolist() == [False, True, False, True]
        assert handle["frame"].tolist() == ["turn", "agent_effects"]
    assert header["format"] == 2
    assert header["seat_agents"] == list(agents)
    assert header["opponent"] == "app_ai"

    data = read_shards([tmp_path / "g10.npz", tmp_path / "g11.npz"])
    assert data.frame.tolist() == ["turn", "agent_effects", "phase:setup"]
    assert data.rows == 3

    # A game built without seat information reads as all-labelling.
    bare = _game(12, [_row(LABEL, [2, 5], 2, [2, 5])])
    assert game_arrays(bare)["g_labelled"].tolist() == [True] * 4
    # A row from a seat that did not label is refused.
    stray = _game(
        13, [_row(LABEL, [2, 5], 2, [2, 5])], seat_agents=agents, labelled=(True,) * 4
    )
    validate_game(stray, 50)
    wrong = _game(
        14,
        [_row(LABEL, [2, 5], 2, [2, 5])],
        seat_agents=agents,
        labelled=(True, False, True, False),
    )
    with pytest.raises(ValueError, match="unlabelled seat"):
        validate_game(wrong, 50)


def _write_format_1(path: Path, game: LabelledGame, meta: dict[str, object]) -> None:
    """A shard as ``EXPERT_FORMAT`` 1 wrote it: no ``frame``, no ``g_labelled``."""

    arrays = game_arrays(game)
    del arrays["frame"], arrays["g_labelled"]
    header = {**meta, "format": 1, "game_seed": game.game_seed}
    arrays["meta_json"] = np.asarray(json.dumps(header))
    with path.open("wb") as handle:
        np.savez_compressed(handle, allow_pickle=False, **arrays)


def test_format_1_shards_still_read_and_never_mix_with_format_2(
    tmp_path: Path,
) -> None:
    meta = run_meta("teacher.pt", LabelConfig(rollouts=2), 50, "ruleset")
    old = _game(20, [_row(LABEL, [3, 7, 9], 7, [7, 3]), _row(ANCHOR, [1, 4], 4, [])])
    older = _game(21, [_row(LABEL, [2, 5], 2, [2, 5])])
    new = _game(22, [_row(LABEL, [2, 5], 2, [2, 5], frame="turn")])
    _write_format_1(tmp_path / "g20.npz", old, meta)
    _write_format_1(tmp_path / "g21.npz", older, meta)
    write_game(tmp_path / "g22.npz", new, meta)

    data = read_shards([tmp_path / "g20.npz", tmp_path / "g21.npz"])
    assert data.rows == 3 and data.frame.tolist() == ["", "", ""]
    assert data.legal_indices.tolist() == [3, 7, 9, 1, 4, 2, 5]
    assert data.kind.tolist() == [LABEL, ANCHOR, LABEL]

    for order in (("g20", "g22"), ("g22", "g20")):
        with pytest.raises(ValueError, match="cannot be mixed"):
            read_shards([tmp_path / f"{name}.npz" for name in order])


def test_draft_and_fixed_roster_shards_never_stack(tmp_path: Path) -> None:
    """The ruleset identifier omits the draft, so the header carries it."""

    game = _game(30, [_row(LABEL, [2, 5], 2, [2, 5], frame="turn")])
    other = _game(31, [_row(LABEL, [2, 5], 2, [2, 5], frame="turn")])
    draft = run_meta("teacher.pt", LabelConfig(rollouts=2), 50, "r", leader_draft=True)
    fixed = run_meta("teacher.pt", LabelConfig(rollouts=2), 50, "r")
    assert draft["leader_draft"] is True and fixed["leader_draft"] is False
    write_game(tmp_path / "g30.npz", game, draft)
    write_game(tmp_path / "g31.npz", other, fixed)
    assert read_shards([tmp_path / "g30.npz"]).rows == 1
    with pytest.raises(ValueError, match="differs"):
        read_shards([tmp_path / "g30.npz", tmp_path / "g31.npz"])


def test_collect_cli_picks_the_ruleset_from_its_flags() -> None:
    parser = build_parser()
    base = ["collect", "--teacher", "t.pt", "--start-seed", "1", "--games", "1"]
    base += ["--out", "shards"]

    plain = parser.parse_args(base)
    assert (plain.rollouts, plain.candidates) == (8, 5)  # the shipped search
    assert plain.opponent is None and plain.mixed_share == 0.5
    assert _ruleset_options(plain) == {
        "choam": True,
        "promo_cards": True,
        "bloodlines": True,
        "tech_module": True,
        "immortality": True,
        "go_to_11": False,
        "epic_game": False,
        "arrakeen_scouts": False,
        "leader_draft": False,
    }

    flags = ["--choam", "--immortality", "--go-to-11", "--epic", "--leader-draft"]
    chosen = parser.parse_args(
        [*base, *flags, "--opponent", "app_ai", "--mixed-share", "0.25"]
    )
    assert chosen.opponent == "app_ai" and chosen.mixed_share == 0.25
    assert {k for k, v in _ruleset_options(chosen).items() if v} == {
        "choam",
        "immortality",
        "go_to_11",
        "epic_game",
        "leader_draft",
    }
    everything = parser.parse_args(
        [
            *base,
            "--choam",
            "--promo-cards",
            "--bloodlines",
            "--tech-module",
            "--immortality",
            "--go-to-11",
            "--epic",
            "--arrakeen-scouts",
            "--leader-draft",
        ]
    )
    assert all(_ruleset_options(everything).values())
