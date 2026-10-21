"""A search seat playing a file of a codec before the two-step Agent turn.

Handoff "학습·AI", the 2026-10-21 order, step 0: ``search:<path>`` of an MLP
written before codec v150 searches through the older-codec adapter
(``training.older_teacher``) instead of the few rows its head reaches.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.action_codec import (  # noqa: E402
    ActionCodec,
    _normalize_arguments,
)
from dune_imperium.adapters.observation_encoding import (  # noqa: E402
    encode_player_view,
)
from dune_imperium.agents.agent_turn_steps import apply_whole  # noqa: E402
from dune_imperium.agents.engine_order import engine_order_answer  # noqa: E402
from dune_imperium.agents.network_search_agent import (  # noqa: E402
    NetworkSearchAgent,
    SearchResult,
    _Shortlist,
)
from dune_imperium.agents.registry import make_agent  # noqa: E402
from dune_imperium.core.actions import DomainAction  # noqa: E402
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision  # noqa: E402
from dune_imperium.core.observation import PlayerView  # noqa: E402
from dune_imperium.core.state import GamePhase, GameState  # noqa: E402
from dune_imperium.rules.agent_turn import executable_placements  # noqa: E402
from dune_imperium.rules.engine import UprisingRulesEngine  # noqa: E402
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.older_teacher import (  # noqa: E402
    OlderNetworkAgent,
    OlderTeacher,
    TemplateKey,
    reads_older_rows,
)
from dune_imperium.training.policy import without_undo_actions  # noqa: E402

_RULES = RulesetConfig()
_ENGINE = UprisingRulesEngine()


def _placement_templates(seed: int, rounds: int) -> list[TemplateKey]:
    """Whole placements an older codec named, from a heuristic game's turns."""

    state = _ENGINE.reset(_RULES, seed)
    chance = ChanceResolver(seed=seed)
    agents = [make_agent("heuristic", index) for index in range(_RULES.players)]
    seen: dict[TemplateKey, None] = {}
    while state.round_number <= rounds and state.phase is not GamePhase.FINISHED:
        decision = _ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(_ENGINE, state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        for placement in executable_placements(state, decision.owner):
            arguments = _normalize_arguments(placement.arguments, placement.actor)
            seen[(placement.action_id, arguments)] = None
        actions = _ENGINE.legal_actions(state, decision.owner)
        choice = agents[decision.owner].choose_action_with_state(  # type: ignore[attr-defined]
            state, _ENGINE.observe(state, decision.owner), actions
        )
        state = apply_whole(_ENGINE, state, choice, legal_actions=actions).state
    return list(seen)


def _older_file(tmp_path: Path, codec_version: int = 147) -> str:
    """A current file rewritten as an older codec's: its template list gains
    the whole placements (``agent_turn``) a pre-v150 codec had, with rows."""

    codec = ActionCodec(_RULES)
    torch.manual_seed(0)
    network = PolicyValueNetwork(codec.size, hidden=(16,))
    path = tmp_path / "older.pt"
    save_checkpoint(path, network, ruleset=_RULES.identifier, iteration=1, codec=codec)
    document = torch.load(path, map_location="cpu", weights_only=True)
    extra = _placement_templates(seed=5, rounds=3)
    document["action_templates"] = [
        *document["action_templates"],
        *(
            [action_id, [list(item) for item in arguments]]
            for action_id, arguments in extra
        ),
    ]
    head = document["state_dict"]
    head["policy_head.weight"] = torch.cat(
        [head["policy_head.weight"], torch.randn(len(extra), 16) * 3.0]
    )
    head["policy_head.bias"] = torch.cat(
        [head["policy_head.bias"], torch.zeros(len(extra))]
    )
    document["action_size"] = codec.size + len(extra)
    document["action_codec_version"] = codec_version
    torch.save(document, path)
    return str(path)


def _first_turn() -> tuple[GameState, int]:
    state = _ENGINE.reset(_RULES, 3)
    chance = ChanceResolver(seed=3)
    while isinstance(decision := _ENGINE.current_decision(state), ChanceDecision):
        state = _ENGINE.apply(state, chance.resolve(decision)).state
    assert decision is not None
    return state, decision.owner


def test_a_file_before_the_two_step_turn_is_read_through_its_own_rows(
    tmp_path: Path,
) -> None:
    older = _older_file(tmp_path)
    assert reads_older_rows(older)
    current = tmp_path / "current.pt"
    codec = ActionCodec(_RULES)
    save_checkpoint(
        current,
        PolicyValueNetwork(codec.size, hidden=(16,)),
        ruleset=_RULES.identifier,
        iteration=1,
        codec=codec,
    )
    assert not reads_older_rows(current)

    seat = make_agent(f"search:{older}", 7, _RULES)
    assert isinstance(seat, NetworkSearchAgent)
    assert seat.older is not None
    with pytest.raises(ValueError, match="no catalog network"):
        _ = seat.greedy
    with pytest.raises(ValueError, match="own value head"):
        NetworkSearchAgent(older, seed=0, value_path=str(current))
    plain = make_agent(f"search:{current}", 7, _RULES)
    assert isinstance(plain, NetworkSearchAgent)
    assert plain.older is None


def test_candidates_are_ranked_by_the_adapter_s_step_probabilities(
    tmp_path: Path,
) -> None:
    """At a card pick the candidates are the cards whose placements the file
    gives the most probability in sum, best first (``OlderTeacher.answer``)."""

    seat = NetworkSearchAgent(
        _older_file(tmp_path), seed=0, candidates=3, config=_RULES
    )
    state, player = _first_turn()
    view = _ENGINE.observe(state, player)
    legal = _ENGINE.legal_actions(state, player)
    plan = seat._shortlist(state, view, legal)
    assert isinstance(plan, _Shortlist)
    offered = without_undo_actions(legal)
    assert seat.older is not None
    answer = OlderTeacher(seat.older.older).answer(state, player, view, offered)
    order = np.argsort(-answer.probabilities, kind="stable")
    assert plan.candidates == tuple(offered[int(index)] for index in order[:3])
    # The step's score is its probability's log: a row no placement reaches
    # ranks last.
    encoded = np.asarray(encode_player_view(view), dtype=np.int32)
    scores = seat._candidate_scores(state, player, encoded, offered)
    with np.errstate(divide="ignore"):
        assert np.allclose(scores, np.log(answer.probabilities))


def test_the_leaves_are_the_older_file_s_value(tmp_path: Path) -> None:
    seat = NetworkSearchAgent(_older_file(tmp_path), seed=0, config=_RULES)
    state, player = _first_turn()
    view = _ENGINE.observe(state, player)
    assert seat.older is not None
    encoded = np.asarray(encode_player_view(view), dtype=np.int32)
    assert seat._leaf_value(view) == seat.older.older.scores(encoded, [])[1]


@dataclass(frozen=True, slots=True)
class _Decided:
    state: GameState
    view: PlayerView
    actions: tuple[DomainAction, ...]
    result: SearchResult
    memory_after: tuple[object, ...]


def _memory(seat: NetworkSearchAgent) -> tuple[object, ...]:
    """What the seat carries from one decision to the next: its RNG and cycle
    guard, and its adapter seat's guard, placement memory and heuristics."""

    answerer = seat._answerer
    assert isinstance(answerer, OlderNetworkAgent)
    fallbacks = answerer.teacher._fallbacks
    return (
        seat._rng.getstate(),
        seat._taken._round,
        {key: frozenset(taken) for key, taken in seat._taken._taken.items()},
        seat._taken.breaks,
        answerer._round,
        {key: frozenset(taken) for key, taken in answerer._taken.items()},
        answerer._memory._kept,
        tuple(
            sorted(
                (str(key), agent._rng.getstate()) for key, agent in fallbacks.items()
            )
        ),
    )


def _game(
    seat: NetworkSearchAgent, *, seed: int, chair: int, count: int
) -> list[_Decided]:
    """``seat`` in ``chair`` beside heuristics for ``count`` of its decisions."""

    state = _ENGINE.reset(_RULES, seed)
    chance = ChanceResolver(seed=seed)
    others = [make_agent("heuristic", index) for index in range(_RULES.players)]
    decided: list[_Decided] = []
    while len(decided) < count and state.phase is not GamePhase.FINISHED:
        decision = _ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = apply_whole(_ENGINE, state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = _ENGINE.legal_actions(state, decision.owner)
        view = _ENGINE.observe(state, decision.owner)
        if decision.owner != chair:
            choice = others[decision.owner].choose_action_with_state(  # type: ignore[attr-defined]
                state, view, actions
            )
            state = apply_whole(_ENGINE, state, choice, legal_actions=actions).state
            continue
        result = seat.search_with_state(state, view, actions)
        assert result.chosen in actions
        forced = engine_order_answer(state, chair, without_undo_actions(actions))
        if forced is not None:
            assert result.chosen == forced and not result.searched
        decided.append(_Decided(state, view, actions, result, _memory(seat)))
        state = _ENGINE.apply(state, result.chosen, legal_actions=actions).state
    return decided


def test_an_older_search_seat_plays_legally_and_retraces_its_answers(
    tmp_path: Path,
) -> None:
    """A loaded save retraces the seat's answers (``replay_decision``): the
    next answers are the ones the searching seat gave, so its RNG, guards,
    placement memory and heuristics end where they did."""

    path = _older_file(tmp_path)

    def seat() -> NetworkSearchAgent:
        return NetworkSearchAgent(
            path, seed=11, rollouts=2, candidates=2, config=_RULES
        )

    decided = _game(seat(), seed=0, chair=1, count=40)
    assert len(decided) == 40
    assert sum(entry.result.searched for entry in decided) >= 5
    for split in (7, 23):
        twin = seat()
        for entry in decided[:split]:
            assert twin.replay_decision(
                entry.state, entry.view, entry.actions, entry.result.chosen
            )
        assert _memory(twin) == decided[split - 1].memory_after
        for entry in decided[split:]:
            answer = twin.choose_action_with_state(
                entry.state, entry.view, entry.actions
            )
            assert answer == entry.result.chosen
        assert _memory(twin) == decided[-1].memory_after


def test_every_playout_is_an_older_network_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The playouts play the file's whole actions (``OlderNetworkAgent``),
    never its migrated catalog rows."""

    seat = NetworkSearchAgent(_older_file(tmp_path), seed=0, rollouts=2, config=_RULES)
    state, player = _first_turn()
    view = _ENGINE.observe(state, player)
    legal = _ENGINE.legal_actions(state, player)
    plan = seat._shortlist(state, view, legal)
    assert isinstance(plan, _Shortlist)
    walkers: list[OlderNetworkAgent] = []  # kept alive, so identities differ
    played = OlderNetworkAgent.choose_action_with_state

    def counted(
        walker: OlderNetworkAgent,
        state: GameState,
        observation: PlayerView,
        legal_actions: tuple[DomainAction, ...],
    ) -> DomainAction:
        if not any(walker is seen for seen in walkers):
            walkers.append(walker)
        return played(walker, state, observation, legal_actions)

    def catalog_rows(*_: object) -> bool:
        raise AssertionError("an older seat's playout read its catalog rows")

    monkeypatch.setattr(OlderNetworkAgent, "choose_action_with_state", counted)
    monkeypatch.setattr(NetworkSearchAgent, "_untrained_only", catalog_rows)
    values = seat.evaluate_candidates(state, player, plan.candidates)
    assert len(values) == 2 and all(len(row) == len(plan.candidates) for row in values)
    # One fresh walker per playout: worlds × candidates.
    assert len(walkers) == 2 * len(plan.candidates)
