"""A search seat's playouts stepped together (``batch_playouts``: on by
default for a current-codec file since 2026-11-10, ``::batch=off`` turns it off).

The batching changes how the network is asked, never what a playout does
with the answer: the tests below pin that the lockstep driver hands every
playout the answer it would get alone (the seams answering one ask at a time
give the plain seat's results bit for bit), that the batched reads match the
single reads to float rounding, and that a seat with it off never reads in
batches.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import ActionCodec  # noqa: E402
from dune_imperium.agents import network_search_agent  # noqa: E402
from dune_imperium.agents.agent_turn_steps import apply_whole  # noqa: E402
from dune_imperium.agents.network_search_agent import (  # noqa: E402
    NetworkSearchAgent,
    _LeafAsk,
    _PolicyAsk,
    is_agent_turn,
    orders_agent_effects,
)
from dune_imperium.agents.registry import make_agent, parse_search_kind  # noqa: E402
from dune_imperium.core.actions import DomainAction  # noqa: E402
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision  # noqa: E402
from dune_imperium.core.observation import PlayerView  # noqa: E402
from dune_imperium.core.state import GamePhase, GameState  # noqa: E402
from dune_imperium.rules.engine import UprisingRulesEngine  # noqa: E402
from dune_imperium.server.sessions import SessionError, _validate_seats  # noqa: E402
from dune_imperium.training import older_teacher  # noqa: E402
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.entity_network import (  # noqa: E402
    EntityNetwork,
    with_value_branch,
)
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.trunk_cache import TrunkCache  # noqa: E402

_RULES = RulesetConfig()
_ENGINE = UprisingRulesEngine()

Root = tuple[GameState, PlayerView, tuple[DomainAction, ...]]


def _mlp(tmp_path: Path, seed: int = 0, name: str = "mlp.pt") -> str:
    codec = ActionCodec(_RULES)
    torch.manual_seed(seed)
    network = PolicyValueNetwork(codec.size, hidden=(32,))
    path = tmp_path / name
    save_checkpoint(path, network, ruleset=_RULES.identifier, iteration=1, codec=codec)
    return str(path)


def _entity(tmp_path: Path) -> str:
    """A small network shaped like the play network E3: entity encoders, a
    value branch reading encoders of its own."""

    torch.manual_seed(0)
    network = EntityNetwork(
        _RULES, hidden=(32, 32), entity_width=16, seat_width=32, action_width=16
    )
    with torch.no_grad():
        for parameter in network.entity_own.values():
            parameter.normal_(0.0, 0.5)
        network.action_bias.normal_(0.0, 0.5)
    branched = with_value_branch(network.eval(), reward_step=1 / 6, value_encoders=True)
    assert branched.value_twin is not None
    with torch.no_grad():
        for parameter in branched.value_twin.seat_encoder.parameters():
            parameter.mul_(1.5)
    path = tmp_path / "entity.pt"
    save_checkpoint(
        path,
        branched,
        ruleset=_RULES.identifier,
        iteration=1,
        codec=ActionCodec(_RULES),
    )
    return str(path)


def _roots(seed: int, count: int, *, agent_turns: bool | None = None) -> list[Root]:
    """Seat 0's decisions a search seat searches in a heuristic game (only
    its Agent turns, or only the others, when ``agent_turns`` says so)."""

    state = _ENGINE.reset(_RULES, seed)
    chance = ChanceResolver(seed=seed)
    heuristics = [make_agent("heuristic", index) for index in range(_RULES.players)]
    roots: list[Root] = []
    while len(roots) < count and state.phase is not GamePhase.FINISHED:
        decision = _ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(_ENGINE, state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = _ENGINE.legal_actions(state, decision.owner)
        view = _ENGINE.observe(state, decision.owner)
        if (
            decision.owner == 0
            and len(actions) > 2
            and state.round_number >= 1
            and not orders_agent_effects(state)
            and (agent_turns is None or is_agent_turn(state) == agent_turns)
        ):
            roots.append((state, view, actions))
        choice = heuristics[decision.owner].choose_action_with_state(  # type: ignore[attr-defined]
            state, view, actions
        )
        state = apply_whole(_ENGINE, state, choice, legal_actions=actions).state
    return roots


def _one_at_a_time(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Make the batch seams answer each ask alone, through the single reads;
    returns the sizes of the batches they were handed."""

    sizes: list[int] = []

    def scores(
        self: NetworkSearchAgent, asks: Sequence[_PolicyAsk | _LeafAsk]
    ) -> list[np.ndarray]:
        sizes.append(len(asks))
        return [
            self._scores(ask.encoded, ask.offered)
            for ask in asks
            if isinstance(ask, _PolicyAsk)
        ]

    def leaves(
        self: NetworkSearchAgent, asks: Sequence[_PolicyAsk | _LeafAsk]
    ) -> list[float]:
        return [self._leaf_value(ask.view) for ask in asks if isinstance(ask, _LeafAsk)]

    monkeypatch.setattr(NetworkSearchAgent, "_batch_scores", scores)
    monkeypatch.setattr(NetworkSearchAgent, "_batch_leaves", leaves)
    return sizes


def test_the_batch_option_parses_and_stays_off_the_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _mlp(tmp_path)
    kind = f"search:{path}::flip=0.01::turn_extend=16::batch=on"
    assert parse_search_kind(kind) == (
        path,
        {"flip_margin": 0.01, "turn_extend": 16, "batch_playouts": True},
    )
    seat = make_agent(kind, 0, _RULES)
    assert isinstance(seat, NetworkSearchAgent) and seat.batch_playouts
    # On by default since 2026-11-10 (the user); ``::batch=off`` turns it off.
    default = make_agent(f"search:{path}::flip=0.01", 0, _RULES)
    assert isinstance(default, NetworkSearchAgent) and default.batch_playouts
    assert NetworkSearchAgent(path, seed=0).batch_playouts
    off = f"search:{path}::flip=0.01::batch=off"
    assert parse_search_kind(off) == (
        path,
        {"flip_margin": 0.01, "batch_playouts": False},
    )
    plain = make_agent(off, 0, _RULES)
    assert isinstance(plain, NetworkSearchAgent) and not plain.batch_playouts
    for bad in ("::batch=1", "::batch=true"):
        with pytest.raises(ValueError, match="::batch=on or ::batch=off"):
            parse_search_kind(f"search:{path}{bad}")
    with pytest.raises(ValueError, match="empty search option"):
        parse_search_kind(f"search:{path}::batch=")
    # A measurement option: a table seat may carry neither (it takes the
    # default).
    for table_kind in (kind, off):
        with pytest.raises(SessionError, match="with options"):
            _validate_seats((table_kind, "human", "human", "human"), _RULES)
    # An older codec's file plays its playouts through the adapter's walker,
    # which asks move by move: nothing to batch, so its default is off and
    # asking for the batching is refused.
    monkeypatch.setattr(older_teacher, "reads_older_rows", lambda _path: True)
    with pytest.raises(ValueError, match="current-codec"):
        NetworkSearchAgent(path, seed=0, batch_playouts=True)


@pytest.mark.parametrize(
    ("network", "options", "agent_turns"),
    [
        ("mlp", {}, False),
        ("mlp", {"value": True}, False),
        ("mlp", {"halving": 3}, False),
        ("mlp", {"turn_extend": 4, "flip_margin": 0.01}, True),
        ("entity", {}, False),
        ("entity", {"turn_extend": 4}, True),
    ],
)
def test_lockstep_playouts_answer_as_one_after_another(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    network: str,
    options: dict[str, Any],
    agent_turns: bool,
) -> None:
    """With every ask answered alone, the lockstep seat's results are the
    plain seat's bit for bit: the same playouts, values, choices and RNG.
    Only the network's batched rounding is left to the option."""

    path = _entity(tmp_path) if network == "entity" else _mlp(tmp_path)
    options = dict(options)
    if options.pop("value", False):
        options["value_path"] = _mlp(tmp_path, seed=1, name="value.pt")
    if "turn_extend" in options:
        # Play the extension too, settled or not.
        monkeypatch.setattr(NetworkSearchAgent, "_settled", lambda self, values: False)

    def seat(batch: bool) -> NetworkSearchAgent:
        return NetworkSearchAgent(
            path,
            seed=5,
            rollouts=2,
            candidates=3,
            config=_RULES,
            batch_playouts=batch,
            **options,
        )

    sizes = _one_at_a_time(monkeypatch)
    plain, batched = seat(False), seat(True)
    searched = 0
    for state, view, actions in _roots(seed=3, count=2, agent_turns=agent_turns):
        expected = plain.search_with_state(state, view, actions)
        # ``repr``: exact floats, and a halving seat's NaN equal to itself.
        assert repr(batched.search_with_state(state, view, actions)) == repr(expected)
        assert batched._rng.getstate() == plain._rng.getstate()
        searched += expected.searched
    assert searched
    # The seams were asked for several playouts at once.
    assert max(sizes) > 1


def test_a_lockstep_seat_plays_the_plain_seat_s_moves_through_a_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fixed seeds, a stretch of real decisions in one seat against
    heuristics: with the single reads behind the seams, the batched seat
    makes every move the plain seat makes, its cycle guard and stream
    included."""

    _one_at_a_time(monkeypatch)
    path = _mlp(tmp_path)
    moves: dict[bool, list[DomainAction]] = {}
    for batch in (False, True):
        seat = NetworkSearchAgent(
            path, seed=7, rollouts=2, candidates=3, config=_RULES, batch_playouts=batch
        )
        state = _ENGINE.reset(_RULES, 11)
        chance = ChanceResolver(seed=11)
        heuristics = [make_agent("heuristic", i) for i in range(_RULES.players)]
        made: list[DomainAction] = []
        searched = 0
        while searched < 6 and state.phase is not GamePhase.FINISHED:
            decision = _ENGINE.current_decision(state)
            if isinstance(decision, ChanceDecision):
                state = apply_whole(_ENGINE, state, chance.resolve(decision)).state
                continue
            assert isinstance(decision, PlayerDecision)
            actions = _ENGINE.legal_actions(state, decision.owner)
            view = _ENGINE.observe(state, decision.owner)
            if decision.owner == 0:
                result = seat.search_with_state(state, view, actions)
                searched += result.searched
                choice = result.chosen
                made.append(choice)
            else:
                choice = heuristics[decision.owner].choose_action_with_state(  # type: ignore[attr-defined]
                    state, view, actions
                )
            state = apply_whole(_ENGINE, state, choice, legal_actions=actions).state
        moves[batch] = made
    assert moves[True] == moves[False]


@pytest.mark.parametrize("network", ["mlp", "mlp-split", "entity"])
def test_batched_reads_match_the_single_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, network: str
) -> None:
    """The real seams: each playout step's logits and each leaf's value read
    in a batch match the batch-of-one reads to float rounding (``mlp-split``
    reads its leaves from another file's value head)."""

    path = _entity(tmp_path) if network == "entity" else _mlp(tmp_path)
    value = _mlp(tmp_path, seed=1, name="value.pt") if network == "mlp-split" else None
    seat = NetworkSearchAgent(
        path,
        seed=5,
        rollouts=2,
        candidates=3,
        config=_RULES,
        value_path=value,
        batch_playouts=True,
    )
    single = NetworkSearchAgent(
        path, seed=5, config=_RULES, value_path=value, batch_playouts=False
    )
    asked: list[list[_PolicyAsk | _LeafAsk]] = []
    original = NetworkSearchAgent._answer_together

    def record(
        self: NetworkSearchAgent, asks: Sequence[_PolicyAsk | _LeafAsk]
    ) -> list[Any]:
        asked.append(list(asks))
        return original(self, asks)

    monkeypatch.setattr(NetworkSearchAgent, "_answer_together", record)
    (state, view, actions), *_ = _roots(seed=3, count=1, agent_turns=False)
    assert seat.search_with_state(state, view, actions).searched
    policy = [ask for asks in asked for ask in asks if isinstance(ask, _PolicyAsk)]
    leaves = [ask for asks in asked for ask in asks if isinstance(ask, _LeafAsk)]
    assert len(policy) > 10 and leaves
    # Batches as the lockstep formed them, through the real seams.
    for asks in asked:
        mine = [ask for ask in asks if isinstance(ask, _PolicyAsk)]
        if mine:
            got = seat._batch_scores(mine)
            for ask, row in zip(mine, got, strict=True):
                want = single._scores(ask.encoded, ask.offered)
                assert row.shape == want.shape
                np.testing.assert_allclose(row, want, rtol=1e-4, atol=1e-5)
        ends = [ask for ask in asks if isinstance(ask, _LeafAsk)]
        if ends:
            for end, leaf in zip(ends, seat._batch_leaves(ends), strict=True):
                assert leaf == pytest.approx(single._leaf_value(end.view), abs=1e-5)


def test_a_batched_seat_searches_a_run_of_decisions_legally(tmp_path: Path) -> None:
    """The real batched seat: the same shortlist as the plain seat (the root
    is read alone), legal choices, every candidate valued in every world."""

    path = _entity(tmp_path)
    seat = NetworkSearchAgent(
        path, seed=2, rollouts=2, candidates=3, config=_RULES, batch_playouts=True
    )
    plain = NetworkSearchAgent(
        path, seed=2, rollouts=2, candidates=3, config=_RULES, batch_playouts=False
    )
    searched = 0
    for state, view, actions in _roots(seed=9, count=4):
        mine = seat.search_with_state(state, view, actions)
        theirs = plain.search_with_state(state, view, actions)
        assert mine.chosen in actions
        assert mine.candidates == theirs.candidates
        assert len(mine.values) == len(theirs.values)
        assert all(np.isfinite(row).all() for row in mine.values)
        searched += mine.searched
    assert searched


def test_an_unbatched_seat_reads_one_view_at_a_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a plain seat read in a batch")

    for name in ("_lockstep", "_batch_scores", "_batch_leaves"):
        monkeypatch.setattr(NetworkSearchAgent, name, refuse)
    monkeypatch.setattr(TrunkCache, "hidden_batch", refuse)
    seat = NetworkSearchAgent(
        _mlp(tmp_path),
        seed=5,
        rollouts=2,
        candidates=3,
        halving=3,
        config=_RULES,
        batch_playouts=False,
    )
    (state, view, actions), *_ = _roots(seed=3, count=1, agent_turns=False)
    assert seat.search_with_state(state, view, actions).searched
    seat.halving = 0
    assert seat.search_with_state(state, view, actions).searched
    assert network_search_agent.DEFAULT_BATCH_PLAYOUTS is True


def test_evaluating_no_candidates_gives_empty_rows_either_way(tmp_path: Path) -> None:
    # Codex review r1: the batched rows were cut by the candidate count.
    path = _mlp(tmp_path)
    (state, view, _), *_ = _roots(seed=3, count=1, agent_turns=False)
    rows = {
        batch: NetworkSearchAgent(
            path, seed=5, rollouts=2, config=_RULES, batch_playouts=batch
        ).evaluate_candidates(state, view.player, ())
        for batch in (False, True)
    }
    assert rows[True] == rows[False] == ((), ())
