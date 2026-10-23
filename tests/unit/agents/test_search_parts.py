"""Search seat experiments E1 (flip margin, prior anchor) and E3 (halving).

Handoff "학습·AI", the 2026-10-21 order: both are off by default and are
turned on per seat with options (``search:<path>::flip=...``).
"""

import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.agents.agent_turn_steps import apply_whole  # noqa: E402
from dune_imperium.agents.network_search_agent import (  # noqa: E402
    NetworkSearchAgent,
    SearchResult,
    _Shortlist,
)
from dune_imperium.agents.registry import (  # noqa: E402
    is_agent_kind,
    make_agent,
    parse_search_kind,
)
from dune_imperium.core.actions import DomainAction  # noqa: E402
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision  # noqa: E402
from dune_imperium.core.observation import PlayerView  # noqa: E402
from dune_imperium.core.state import GamePhase, GameState  # noqa: E402
from dune_imperium.rules.engine import UprisingRulesEngine  # noqa: E402
from dune_imperium.server.sessions import SessionError, _validate_seats  # noqa: E402
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402

_RULES = RulesetConfig()
_ENGINE = UprisingRulesEngine()
NAN = float("nan")


def _checkpoint(tmp_path: Path) -> str:
    codec = ActionCodec(_RULES)
    torch.manual_seed(0)
    network = PolicyValueNetwork(codec.size, hidden=(32,))
    path = tmp_path / "policy.pt"
    save_checkpoint(path, network, ruleset=_RULES.identifier, iteration=1, codec=codec)
    return str(path)


def _seat(tmp_path: Path, **options: float) -> NetworkSearchAgent:
    return NetworkSearchAgent(
        _checkpoint(tmp_path),
        seed=3,
        rollouts=2,
        candidates=3,
        config=_RULES,
        **options,  # type: ignore[arg-type]
    )


def test_by_default_the_pick_is_the_first_largest_column_sum(tmp_path: Path) -> None:
    seat = _seat(tmp_path)
    rng = np.random.default_rng(0)
    for _ in range(200):
        values = rng.integers(-2, 3, size=(4, 5)).astype(float) / 4
        totals = [sum(column) for column in zip(*values, strict=True)]
        assert seat._pick(values.tolist(), ()) == totals.index(max(totals))


def test_a_flip_margin_keeps_the_network_s_first_candidate_on_small_gains(
    tmp_path: Path,
) -> None:
    seat = _seat(tmp_path, flip_margin=0.01)
    close = [[0.100, 0.105, 0.0], [0.100, 0.105, 0.0]]
    clear = [[0.100, 0.150, 0.0], [0.100, 0.150, 0.0]]
    assert seat._pick(close, ()) == 0
    assert seat._pick(clear, ()) == 1
    assert _seat(tmp_path)._pick(close, ()) == 1


def test_a_prior_weight_adds_the_network_s_log_probability(tmp_path: Path) -> None:
    seat = _seat(tmp_path, prior_weight=0.1)
    values = [[0.10, 0.12], [0.10, 0.12]]
    priors = (math.log(0.9), math.log(0.1))  # 0.1 + 0.1 ln 0.9 > 0.12 + 0.1 ln 0.1
    assert seat._pick(values, priors) == 0
    assert _seat(tmp_path)._pick(values, priors) == 1


def test_the_shortlist_carries_log_probabilities_summing_to_one(
    tmp_path: Path,
) -> None:
    seat = NetworkSearchAgent(
        _checkpoint(tmp_path),
        seed=3,
        rollouts=4,
        candidates=2,
        halving=4,
        config=_RULES,
    )
    state = _ENGINE.reset(_RULES, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := _ENGINE.current_decision(state), ChanceDecision):
        state = _ENGINE.apply(state, chance.resolve(decision)).state
    assert isinstance(decision, PlayerDecision)
    view = _ENGINE.observe(state, decision.owner)
    plan = seat._shortlist(state, view, _ENGINE.legal_actions(state, decision.owner))
    assert isinstance(plan, _Shortlist)
    assert len(plan.candidates) == 4 == len(plan.priors)
    assert list(plan.priors) == sorted(plan.priors, reverse=True)
    assert all(prior <= 0 for prior in plan.priors)


@pytest.mark.parametrize(
    ("count", "schedule"),
    [(8, [1, 4, 8]), (5, [2, 5, 7]), (3, [6, 11]), (2, [20])],
)
def test_halving_spends_the_plain_budget_in_halving_rounds(
    tmp_path: Path, count: int, schedule: list[int]
) -> None:
    seat = NetworkSearchAgent(
        _checkpoint(tmp_path),
        seed=0,
        rollouts=8,
        candidates=5,
        halving=8,
        config=_RULES,
    )
    assert seat._halving_rounds(count) == schedule
    assert seat._world_count(count) == sum(schedule)
    alive, spent = count, 0
    for new in schedule:
        spent += new * alive
        alive = max(1, (alive + 1) // 2)
    assert spent <= 8 * 5


def test_halving_drops_the_worse_half_and_picks_among_the_last_round(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Candidate i plays value i/10 in every world except the first, where
    candidate 0 plays 1.0: halving keeps 0 after the first round on its lucky
    world but the later worlds decide; dropped candidates hold NaN."""

    seat = NetworkSearchAgent(
        _checkpoint(tmp_path),
        seed=0,
        rollouts=8,
        candidates=5,
        halving=8,
        config=_RULES,
    )
    calls: list[int] = []

    def playout(
        self: NetworkSearchAgent,
        state: object,
        seat: int,
        horizon: int,
        chance_seed: int,
    ) -> float:
        index = state  # the fake apply below passes the candidate index through
        calls.append(index)  # type: ignore[arg-type]
        return 1.0 if (index == 0 and len(calls) <= 8) else index / 10  # type: ignore[operator]

    class _Applied:
        def __init__(self, state: object) -> None:
            self.state = state

    monkeypatch.setattr(NetworkSearchAgent, "_playout", playout)
    monkeypatch.setattr(seat._engine, "apply", lambda world, action: _Applied(action))
    monkeypatch.setattr(
        NetworkSearchAgent,
        "_worlds",
        lambda self, state, s, count=None: iter([(None, 0)] * (count or 0)),
    )
    candidates = tuple(range(8))
    values = seat._search_halving(SimpleNamespace(round_number=1), 0, candidates, ())  # type: ignore[arg-type]
    assert len(values) == 13 and len(calls) == 8 + 4 * 4 + 2 * 8
    last = values[-1]
    survivors = [index for index, value in enumerate(last) if not np.isnan(value)]
    assert survivors == [6, 7]
    assert seat._pick(values, ()) == 7


def test_search_options_parse_and_stay_off_the_tables(tmp_path: Path) -> None:
    path = _checkpoint(tmp_path)
    kind = f"search:{path}::flip=0.01::prior=0.03::halving=8"
    assert parse_search_kind(kind) == (
        path,
        {"flip_margin": 0.01, "prior_weight": 0.03, "halving": 8},
    )
    assert is_agent_kind(kind)
    seat = make_agent(kind, 0, _RULES)
    assert isinstance(seat, NetworkSearchAgent)
    assert (seat.flip_margin, seat.prior_weight, seat.halving) == (0.01, 0.03, 8)
    for bad in ("::flip", "::flip=", "::nope=1", "::flip=0.1::flip=0.2", "::halving=1"):
        assert not is_agent_kind(f"search:{path}{bad}") or bad == "::halving=1"
    with pytest.raises(ValueError):
        make_agent(f"search:{path}::halving=1", 0, _RULES)
    # A table seat may carry the flip margin (the server's search AI does,
    # ``SERVER_SEARCH_OPTIONS``); the other options stay measurement tools.
    for refused in (kind, f"search:{path}::prior=0.03", f"search:{path}::halving=8"):
        with pytest.raises(SessionError, match="with options"):
            _validate_seats((refused, "human", "human", "human"), _RULES)
    with pytest.raises(SessionError, match="split"):
        _validate_seats(
            (f"search:{path}::value={path}", "human", "human", "human"), _RULES
        )
    _validate_seats((f"search:{path}", "human", "human", "human"), _RULES)
    _validate_seats((f"search:{path}::flip=0.01", "human", "human", "human"), _RULES)


def test_a_retraced_halving_seat_answers_like_the_one_that_searched(
    tmp_path: Path,
) -> None:
    """A retrace draws as many worlds as halving did (``_world_count``)."""

    path = _checkpoint(tmp_path)

    def seat() -> NetworkSearchAgent:
        return NetworkSearchAgent(
            path,
            seed=11,
            rollouts=4,
            candidates=2,
            halving=4,
            flip_margin=0.005,
            config=_RULES,
        )

    state = _ENGINE.reset(_RULES, 0)
    chance = ChanceResolver(seed=0)
    heuristics = [make_agent("heuristic", index) for index in range(_RULES.players)]
    playing = seat()
    decided: list[
        tuple[GameState, PlayerView, tuple[DomainAction, ...], SearchResult, object]
    ] = []
    while len(decided) < 30 and state.phase is not GamePhase.FINISHED:
        decision = _ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(_ENGINE, state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = _ENGINE.legal_actions(state, decision.owner)
        view = _ENGINE.observe(state, decision.owner)
        if decision.owner != 1:
            choice = heuristics[decision.owner].choose_action_with_state(  # type: ignore[attr-defined]
                state, view, actions
            )
            state = apply_whole(_ENGINE, state, choice, legal_actions=actions).state
            continue
        result = playing.search_with_state(state, view, actions)
        decided.append((state, view, actions, result, playing._rng.getstate()))
        state = _ENGINE.apply(state, result.chosen, legal_actions=actions).state
    assert sum(entry[3].searched for entry in decided) >= 3
    twin = seat()
    for state, view, actions, result, _ in decided[:15]:
        assert twin.replay_decision(state, view, actions, result.chosen)
    assert twin._rng.getstate() == decided[14][4]
    for state, view, actions, result, _ in decided[15:]:
        assert twin.choose_action_with_state(state, view, actions) == result.chosen


def test_the_default_pick_compares_sums_exactly_whatever_the_world_count(
    tmp_path: Path,
) -> None:
    """A mean over three worlds rounds; the defaults compare the column sums
    themselves, as the seat always did (review note on 02d6e1fa)."""

    seat = NetworkSearchAgent(
        _checkpoint(tmp_path), seed=0, rollouts=3, candidates=2, config=_RULES
    )
    values = [[1 - 2**-53, 1.0], [0.0, 0.0], [0.0, 0.0]]
    totals = [sum(column) for column in zip(*values, strict=True)]
    assert seat._pick(values, ()) == totals.index(max(totals)) == 1


def test_search_options_must_be_finite_and_within_the_budget(tmp_path: Path) -> None:
    path = _checkpoint(tmp_path)
    for options in ({"flip_margin": float("nan")}, {"prior_weight": float("inf")}):
        with pytest.raises(ValueError, match="finite"):
            NetworkSearchAgent(path, seed=0, config=_RULES, **options)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="first round"):
        NetworkSearchAgent(path, seed=0, halving=16, config=_RULES)  # 16 x 4 > 40
    NetworkSearchAgent(path, seed=0, halving=8, config=_RULES)  # 8 x 3 <= 40
    for bad in (
        "::flip=nan",
        "::prior=inf",
        "::flip=-0.1",
        "::halving=1",
        "::halving=-2",
    ):
        assert not is_agent_kind(f"search:{path}{bad}")


def test_a_network_draft_seat_lets_the_network_pick_the_leader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``::draft=network``: the Leader pick is the network's, with no
    playouts, and a retrace draws no worlds for it."""

    path = _checkpoint(tmp_path)
    config = RulesetConfig(leader_draft=True)
    state = _ENGINE.reset(config, 5)
    chance = ChanceResolver(seed=5)
    while isinstance(decision := _ENGINE.current_decision(state), ChanceDecision):
        state = _ENGINE.apply(state, chance.resolve(decision)).state
    assert isinstance(decision, PlayerDecision)
    actions = _ENGINE.legal_actions(state, decision.owner)
    assert len(actions) > 1 and {action.action_id for action in actions} == {
        "choose_leader"
    }
    view = _ENGINE.observe(state, decision.owner)

    def seat(*, network_draft: bool = False) -> NetworkSearchAgent:
        return NetworkSearchAgent(
            path,
            seed=3,
            rollouts=2,
            candidates=3,
            config=config,
            network_draft=network_draft,
        )

    greedy = seat()._answerer.choose_action_with_state(state, view, actions)
    plain = seat().search_with_state(state, view, actions)
    assert plain.searched

    def no_playouts(*_: object) -> float:
        raise AssertionError("the network picks the Leader")

    monkeypatch.setattr(NetworkSearchAgent, "_playout", no_playouts)
    drafting = seat(network_draft=True)
    result = drafting.search_with_state(state, view, actions)
    assert not result.searched and result.chosen == greedy
    twin = seat(network_draft=True)
    before = twin._rng.getstate()
    assert twin.replay_decision(state, view, actions, result.chosen)
    assert twin._rng.getstate() == before


def test_the_draft_option_parses_and_stays_off_the_tables(tmp_path: Path) -> None:
    path = _checkpoint(tmp_path)
    kind = f"search:{path}::flip=0.01::draft=network"
    assert parse_search_kind(kind) == (
        path,
        {"flip_margin": 0.01, "network_draft": True},
    )
    seat = make_agent(kind, 0, _RULES)
    assert isinstance(seat, NetworkSearchAgent) and seat.network_draft
    assert not make_agent(f"search:{path}", 0, _RULES).network_draft  # type: ignore[attr-defined]
    for bad in ("::draft=1", "::draft=", "::draft=search"):
        assert not is_agent_kind(f"search:{path}{bad}")
    with pytest.raises(SessionError, match="with options"):
        _validate_seats((kind, "human", "human", "human"), _RULES)
