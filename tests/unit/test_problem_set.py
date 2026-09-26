"""The evaluation problem set: mined positions restore, judges discriminate."""

from dataclasses import replace
from pathlib import Path

import pytest

from dune_imperium.agents import registry
from dune_imperium.cli.problems import main as problems_main
from dune_imperium.content.uprising.effect_dsl import IntrigueTiming
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.observation import PlayerView
from dune_imperium.evaluation.problem_set import (
    DEFAULT_SUITE,
    PROBLEMS,
    Position,
    _icon_play,
    _placement,
    agent_seed,
    answer,
    load_suite,
    mine,
    policy_probabilities,
    restore,
    save_suite,
    summarize_answers,
    unrestorable,
)
from dune_imperium.evaluation.tournament import MatchSpec, tournament_specs


def _full_specs(games: int, start: int = 0) -> list[MatchSpec]:
    return list(
        tournament_specs(
            agents=("heuristic",),
            games=games,
            rulesets=(True,),
            start_seed=start,
            rotate_leaders=True,
            promo_cards=True,
            bloodlines=True,
            tech_module=True,
            immortality=True,
        )
    )


def _sample(positions: list[Position], per_problem: int) -> list[Position]:
    picked: list[Position] = []
    for problem_id in PROBLEMS:
        picked += [p for p in positions if p.problem_id == problem_id][:per_problem]
    return picked


def _assert_discriminates(position: Position) -> None:
    engine, state, legal = restore(position)
    problem = PROBLEMS[position.problem_id]
    assert problem.detect(state, position.owner, legal), position.position_id
    right = [a for a in legal if problem.right(state, position.owner, a)]
    assert 0 < len(right) < len(legal), position.position_id


@pytest.fixture(scope="module")
def suite() -> list[Position]:
    return load_suite(DEFAULT_SUITE)


def test_freshly_mined_positions_restore_and_discriminate() -> None:
    positions = mine(_full_specs(4))
    assert positions, "four full-config heuristic games should give a position"
    for position in positions:
        _assert_discriminates(position)


def test_the_committed_suite_covers_every_problem_and_still_restores(
    suite: list[Position],
) -> None:
    assert {p.problem_id for p in suite} == set(PROBLEMS)
    assert len({p.position_id for p in suite}) == len(suite)
    # The judges are checked on a sample; restoring every stored position is
    # test_every_position_of_the_committed_suite_restores below.
    for position in _sample(suite, 3):
        _assert_discriminates(position)


def test_every_position_of_the_committed_suite_restores(
    suite: list[Position],
) -> None:
    # The same restore as `dune-imperium-problems check` (about 10 seconds).
    # A rule change that moves any stored position fails here, instead of
    # waiting for the next re-mine: on master 60f8e95 four of 106 positions
    # had stopped restoring unnoticed, because only a sample was restored.
    failures = unrestorable(suite)
    if failures:
        pytest.fail(
            f"{len(failures)} of {len(suite)} positions of {DEFAULT_SUITE.name} "
            "no longer restore; re-mine the suite (docs/evaluation/"
            "problem-set.md, 다시 캐는 명령):\n"
            + "\n".join(f"- {failure}" for failure in failures),
            pytrace=False,
        )


def test_the_suite_check_lists_every_position_that_moved(
    suite: list[Position],
) -> None:
    moved = [replace(position, fingerprint="0" * 16) for position in suite[1:3]]

    failures = unrestorable([suite[0], *moved])

    assert len(failures) == 2
    for position, failure in zip(moved, failures, strict=True):
        assert failure.startswith(f"{position.position_id}: ")
        assert "re-mine" in failure


def test_a_position_the_engine_no_longer_reaches_is_reported(
    suite: list[Position],
) -> None:
    moved = replace(suite[0], fingerprint="0" * 16)
    with pytest.raises(ValueError, match="re-mine"):
        restore(moved)


def test_a_position_for_another_seat_is_reported(suite: list[Position]) -> None:
    moved = replace(suite[0], owner=(suite[0].owner + 1) % 4)
    with pytest.raises(ValueError, match="re-mine"):
        restore(moved)


def test_a_position_its_problem_no_longer_detects_is_reported(
    suite: list[Position], monkeypatch: pytest.MonkeyPatch
) -> None:
    position = suite[0]
    problem = PROBLEMS[position.problem_id]
    monkeypatch.setitem(
        PROBLEMS, problem.problem_id, replace(problem, detect=lambda *args: False)
    )
    with pytest.raises(ValueError, match="no longer an instance"):
        restore(position)


def test_positions_mined_from_a_mixed_table_have_unique_ids() -> None:
    specs = tournament_specs(
        agents=("heuristic", "random"),
        games=2,
        rulesets=(True,),
        rotate_leaders=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
    )
    positions = mine(specs)
    ids = [p.position_id for p in positions]
    assert len(ids) == len(set(ids))
    keys = [
        (p.problem_id, p.owner, p.spec["game_seed"], tuple(p.spec["seat_agents"]))
        for p in positions
    ]
    assert len(keys) == len(set(keys))


def test_the_suite_file_round_trips(tmp_path: Path, suite: list[Position]) -> None:
    path = tmp_path / "suite.json"
    save_suite(path, suite[:5], "note")
    assert load_suite(path) == suite[:5]


def _first(suite: list[Position], problem_id: str) -> Position:
    return next(p for p in suite if p.problem_id == problem_id)


def test_holding_problem_marks_only_the_battle_icon_plot_play_wrong(
    suite: list[Position],
) -> None:
    position = _first(suite, "last_round_hold_battle_icon")
    _, state, legal = restore(position)
    assert not state.conflict_deck  # the round is certainly the last
    judge = PROBLEMS[position.problem_id].right
    for action in legal:
        is_plot_icon = _icon_play(action, IntrigueTiming.PLOT) is not None
        assert judge(state, position.owner, action) is not is_plot_icon


def test_endgame_problem_marks_only_passing_wrong(suite: list[Position]) -> None:
    position = _first(suite, "endgame_battle_icon_vp")
    _, state, legal = restore(position)
    judge = PROBLEMS[position.problem_id].right
    for action in legal:
        expected = action.action_id != "pass_endgame_intrigue"
        assert judge(state, position.owner, action) is expected


def test_summon_problem_scores_only_the_summon_or_spice_choice(
    suite: list[Position],
) -> None:
    problem = PROBLEMS["deep_desert_summon_into_contest"]
    assert problem.scored is not None
    position = _first(suite, problem.problem_id)
    _, state, legal = restore(position)
    for action in legal:
        committed = action.action_id in (
            "summon_maker_sandworms",
            "harvest_maker_spice",
        )
        assert problem.scored(action) is committed
        if committed:
            expected = action.action_id == "summon_maker_sandworms"
            assert problem.right(state, position.owner, action) is expected


def test_every_position_gets_its_own_agent_seed(suite: list[Position]) -> None:
    seeds = {agent_seed(position, 0) for position in suite}
    assert len(seeds) == len(suite)
    assert agent_seed(suite[0], 7) == agent_seed(suite[0], 0) + 7


def test_a_placement_counts_the_seats_ahead() -> None:
    assert _placement(0, [4, 2, 0]) == 0
    assert _placement(4, [4, 2, 0]) == 1  # a tie is not ahead
    assert _placement(3, [4, 5, 0]) == 3


class _DeferFirst:
    """Resolves some other effect first, then takes ``final`` if it can."""

    def __init__(self, final: str) -> None:
        self.final = final
        self.deferred = False

    def choose_action(
        self, observation: PlayerView, legal_actions: tuple[DomainAction, ...]
    ) -> DomainAction:
        scored = PROBLEMS["deep_desert_summon_into_contest"].scored
        assert scored is not None
        others = [a for a in legal_actions if not scored(a)]
        if not self.deferred and others:
            self.deferred = True
            return others[0]
        for action in legal_actions:
            if action.action_id == self.final:
                return action
        return legal_actions[0]


@pytest.mark.parametrize(
    ("final", "right"),
    [("summon_maker_sandworms", True), ("harvest_maker_spice", False)],
)
def test_resolving_another_effect_first_only_defers_the_answer(
    suite: list[Position],
    monkeypatch: pytest.MonkeyPatch,
    final: str,
    right: bool,
) -> None:
    scored = PROBLEMS["deep_desert_summon_into_contest"].scored
    assert scored is not None
    position = next(
        p
        for p in suite
        if p.problem_id == "deep_desert_summon_into_contest"
        and any(not scored(a) for a in restore(p)[2])
    )
    monkeypatch.setitem(
        registry.BASELINE_AGENT_FACTORIES,
        "defer_first",
        lambda seed: _DeferFirst(final),
    )
    result = answer(position, "defer_first")
    assert result.resolved
    assert result.deferred >= 1
    assert result.right is right


def test_a_rule_agent_is_scored_on_its_choice_only(suite: list[Position]) -> None:
    answers = [answer(p, "heuristic") for p in _sample(suite, 1)]
    assert all(a.p_right is None for a in answers)
    summary = summarize_answers(answers)
    assert set(summary) == set(PROBLEMS)
    for row in summary.values():
        assert 0.0 <= row["right"] <= 1.0
        assert row["mean_p_right"] is None


def test_a_network_is_scored_by_its_probability_on_the_right_answers(
    tmp_path: Path, suite: list[Position]
) -> None:
    torch = pytest.importorskip("torch")
    from dune_imperium import RulesetConfig
    from dune_imperium.adapters.action_codec import ActionCodec
    from dune_imperium.training.checkpoint import save_checkpoint
    from dune_imperium.training.network import PolicyValueNetwork

    config = RulesetConfig(
        choam_module=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
    )
    torch.manual_seed(0)
    network = PolicyValueNetwork(ActionCodec(config).size, hidden=(16,))
    path = tmp_path / "policy.pt"
    save_checkpoint(path, network, ruleset=config.identifier, iteration=1)
    kind = f"checkpoint:{path}"
    for position in _sample(suite, 1):
        result = answer(position, kind)
        assert result.p_right is not None
        assert 0.0 < result.p_right < 1.0
        # The probabilities are the greedy agent's own: they sum to one and
        # their argmax is the action it plays.
        engine, state, legal = restore(position)
        agent = registry.make_agent(kind, 0)
        view = engine.observe(state, position.owner)
        probabilities = policy_probabilities(agent, view, legal)
        assert probabilities is not None
        assert abs(sum(probabilities.values()) - 1.0) < 1e-6
        best = max(probabilities, key=lambda action: probabilities[action])
        assert best == agent.choose_action(view, legal)


def test_the_cli_scores_a_suite(
    tmp_path: Path, suite: list[Position], capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "suite.json"
    save_suite(path, _sample(suite, 1), "cli")
    problems_main(["score", "--agents", "random", "--suite", str(path)])
    out = capsys.readouterr().out
    assert "## random" in out
    for problem_id in PROBLEMS:
        assert problem_id in out
    problems_main(["check", "--suite", str(path)])
    assert (
        f"{len(PROBLEMS)}/{len(PROBLEMS)} positions restore" in capsys.readouterr().out
    )
