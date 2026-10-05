"""Training-loop options for re-adapting to the play UI's ruleset (L3).

Opponent games mixed into self-play, the rule options the UI offers (Go to
11, Epic Game Mode, Arrakeen Scouts, the Leader draft), Leader rotation,
and resuming a checkpoint trained on another ruleset.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("torch")

from dune_imperium.cli.train import main as train_main  # noqa: E402
from dune_imperium.evaluation import tournament_specs  # noqa: E402
from dune_imperium.evaluation.tournament import (  # noqa: E402
    MatchSpec,
    rotated_leader_ids,
)
from dune_imperium.training import loop as loop_module  # noqa: E402
from dune_imperium.training.checkpoint import load_checkpoint  # noqa: E402
from dune_imperium.training.learner import LearnerConfig  # noqa: E402
from dune_imperium.training.loop import TrainConfig, train  # noqa: E402

UNUSED = Path("unused")


def _learner_positions(lineup: tuple[str, ...]) -> list[int]:
    return [seat for seat, name in enumerate(lineup) if name == "learner"]


def test_opponent_games_mix_evenly_into_self_play() -> None:
    config = TrainConfig(
        out_dir=UNUSED,
        games_per_iteration=8,
        opponent="app_ai",
        learner_seats=2,
        opponent_games=4,
    )

    specs = loop_module._iteration_specs(config, 0)

    against = [spec for spec in specs if "app_ai" in spec.lineup]
    assert len(against) == 4
    # Every other game, so each collection worker deals its share.
    assert ["app_ai" in spec.lineup for spec in specs] == [False, True] * 4
    assert all(spec.lineup == ("learner",) * 4 for spec in specs if spec not in against)
    # The learner seats keep alternating among the opponent games alone.
    assert [_learner_positions(spec.lineup) for spec in against] == [
        [0, 2],
        [1, 3],
        [0, 2],
        [1, 3],
    ]


def test_opponent_games_spread_one_in_four() -> None:
    config = TrainConfig(
        out_dir=UNUSED, games_per_iteration=32, opponent="app_ai", opponent_games=8
    )

    flags = [
        "app_ai" in spec.lineup for spec in loop_module._iteration_specs(config, 3)
    ]

    assert sum(flags) == 8
    assert [index for index, flag in enumerate(flags) if flag] == list(range(3, 32, 4))


def test_without_opponent_games_every_game_seats_the_opponent() -> None:
    config = TrainConfig(
        out_dir=UNUSED, games_per_iteration=4, opponent="app_ai", learner_seats=1
    )

    specs = loop_module._iteration_specs(config, 0)

    assert all(spec.lineup.count("app_ai") == 3 for spec in specs)
    assert [_learner_positions(spec.lineup) for spec in specs] == [[0], [1], [2], [3]]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"opponent_games": 4}, "needs an opponent"),
        ({"opponent": "app_ai", "opponent_games": 0}, "between 1 and"),
        ({"opponent": "app_ai", "opponent_games": 9}, "between 1 and"),
        ({"rotate_leaders": True, "leader_draft": True}, "cannot be combined"),
        ({"go_to_11": True}, "requires the Immortality"),
        ({"retarget": True}, "needs a checkpoint"),
    ],
)
def test_invalid_option_mixes_are_rejected(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        TrainConfig(out_dir=UNUSED, games_per_iteration=8, **kwargs)  # type: ignore[arg-type]


def test_rotated_leaders_follow_the_tournament_derivation() -> None:
    config = TrainConfig(
        out_dir=UNUSED,
        games_per_iteration=4,
        choam_module=True,
        bloodlines=True,
        tech_module=True,
        rotate_leaders=True,
    )

    specs = loop_module._iteration_specs(config, 0)

    assert [spec.leader_ids for spec in specs] == [
        rotated_leader_ids(spec.game_seed, True, True, True) for spec in specs
    ]
    assert len({spec.leader_ids for spec in specs}) > 1
    plain = loop_module._iteration_specs(TrainConfig(out_dir=UNUSED), 0)
    assert all(spec.leader_ids is None for spec in plain)


def test_the_ruleset_carries_every_ui_option() -> None:
    config = TrainConfig(
        out_dir=UNUSED,
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

    assert config.ruleset.identifier == (
        "uprising-4p-choam+promo+bloodlines+tech+immortality+go11+epic+scouts"
    )
    assert config.ruleset.leader_draft


def test_the_evaluation_plays_the_training_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[dict[str, object]] = []

    def capture(**kwargs: object) -> object:
        seen.append(kwargs)
        return tournament_specs(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(loop_module, "tournament_specs", capture)
    config = TrainConfig(
        out_dir=tmp_path,
        games_per_iteration=1,
        immortality=True,
        go_to_11=True,
        epic_game=True,
        leader_draft=True,
        eval_every=1,
        eval_games=1,
        eval_opponent="random",
    )
    monkeypatch.setattr(
        loop_module, "run_tournament", lambda specs, **_: _stop(list(specs))
    )

    with pytest.raises(_Captured) as captured:
        loop_module._evaluate(config, tmp_path / "latest.pt", 1)

    (kwargs,) = seen
    assert kwargs["go_to_11"] and kwargs["epic_game"] and kwargs["immortality"]
    assert kwargs["leader_draft"] and not kwargs["rotate_leaders"]
    specs = captured.value.specs
    assert specs and all(spec.config.leader_draft for spec in specs)
    assert all(spec.config.epic_game and spec.config.go_to_11 for spec in specs)


class _Captured(Exception):
    def __init__(self, specs: list[MatchSpec]) -> None:
        super().__init__("captured")
        self.specs = specs


def _stop(specs: list[MatchSpec]) -> object:
    raise _Captured(specs)


def _tiny(out_dir: Path, **kwargs: object) -> TrainConfig:
    return TrainConfig(
        out_dir=out_dir,
        iterations=1,
        games_per_iteration=2,
        seed=1,
        hidden=(16,),
        learner=LearnerConfig(minibatch_size=512),
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_mixed_iteration_logs_the_win_rate_against_the_opponent(
    tmp_path: Path,
) -> None:
    result = train(
        _tiny(
            tmp_path / "run",
            opponent="app_ai",
            learner_seats=2,
            opponent_games=1,
            leader_draft=True,
        )
    )

    (record,) = result.records
    assert record.games == 2
    assert record.opponent_win_rate is not None
    assert record.opponent_win_rate in (0.0, 0.5)
    assert record.truncated == 0
    line = json.loads(result.log_path.read_text().splitlines()[0])
    assert line["opponent_win_rate"] == record.opponent_win_rate
    # Pure self-play has no opponent games to report.
    selfplay = train(_tiny(tmp_path / "selfplay"))
    assert selfplay.records[0].opponent_win_rate is None


def test_retarget_resumes_a_checkpoint_onto_another_ruleset(tmp_path: Path) -> None:
    base = train(_tiny(tmp_path / "base", opponent="random"))
    _, base_info = load_checkpoint(base.latest_checkpoint)
    assert base_info.ruleset == "uprising-4p-base"

    with pytest.raises(ValueError, match="different ruleset"):
        train(
            _tiny(
                tmp_path / "refused",
                opponent="random",
                epic_game=True,
                resume=base.latest_checkpoint,
            )
        )
    moved = train(
        _tiny(
            tmp_path / "epic",
            opponent="random",
            epic_game=True,
            resume=base.latest_checkpoint,
            retarget=True,
        )
    )

    network, info = load_checkpoint(moved.latest_checkpoint)
    assert info.ruleset == "uprising-4p-base+epic"
    assert info.iteration == 2
    assert network.action_size > base_info.action_size


def test_cli_forwards_the_new_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[TrainConfig] = []

    def capture(config: TrainConfig, **_: object) -> object:
        seen.append(config)
        raise SystemExit(0)

    monkeypatch.setattr("dune_imperium.cli.train.train", capture)
    with pytest.raises(SystemExit):
        train_main(
            [
                "--out",
                str(tmp_path),
                "--immortality",
                "--go-to-11",
                "--epic",
                "--arrakeen-scouts",
                "--leader-draft",
                "--opponent",
                "app_ai",
                "--learner-seats",
                "2",
                "--opponent-games",
                "16",
                "--resume",
                str(tmp_path / "x.pt"),
                "--retarget",
            ]
        )

    (config,) = seen
    assert config.go_to_11 and config.epic_game and config.arrakeen_scouts
    assert config.leader_draft and not config.rotate_leaders
    assert config.opponent == "app_ai" and config.opponent_games == 16
    assert config.retarget and config.resume == tmp_path / "x.pt"
    with pytest.raises(SystemExit) as excinfo:
        train_main(["--out", str(tmp_path), "--leader-draft", "--rotate-leaders"])
    assert excinfo.value.code == 2
