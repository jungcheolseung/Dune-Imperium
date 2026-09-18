"""The training loop records evaluation matches that failed."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("torch")

from dune_imperium.evaluation import run_tournament  # noqa: E402
from dune_imperium.evaluation.tournament import (  # noqa: E402
    MatchFailure,
    TournamentReport,
)
from dune_imperium.training import loop as loop_module  # noqa: E402
from dune_imperium.training.learner import LearnerConfig  # noqa: E402
from dune_imperium.training.loop import TrainConfig, train  # noqa: E402


def test_the_loop_records_failed_evaluation_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # On 2026-09-18 one in-loop evaluation match raised (a codec range defect)
    # and was silently left out of the win rate; the count and the message are
    # now part of the record.
    def with_a_failure(specs: object, **kwargs: object) -> TournamentReport:
        report = run_tournament(specs, **kwargs)  # type: ignore[arg-type]
        failure = MatchFailure(
            ruleset="uprising-4p-base",
            game_seed=13,
            policy_seed=900_013,
            seat_agents=("heuristic",) * 4,
            error="ValueError: action is not present in this codec version",
        )
        return replace(report, failures=(*report.failures, failure))

    monkeypatch.setattr(loop_module, "run_tournament", with_a_failure)
    result = train(
        TrainConfig(
            out_dir=tmp_path / "run",
            iterations=1,
            games_per_iteration=1,
            hidden=(16,),
            learner=LearnerConfig(minibatch_size=512),
            eval_every=1,
            eval_games=1,
        )
    )

    assert result.records[0].eval_failures == 1
    assert result.records[0].eval_win_rate is not None
    line = json.loads(result.log_path.read_text().splitlines()[0])
    assert line["eval_failures"] == 1
    log = (tmp_path / "run" / "eval_failures.log").read_text()
    assert "iteration 1" in log and "seed=13" in log and "codec version" in log
