"""Tests for the policy-guided determinized search agent (``search:<path>``)."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from dune_imperium import RulesetConfig  # noqa: E402
from dune_imperium.adapters.pettingzoo_env import (  # noqa: E402
    LOSER_REWARD,
    WINNER_REWARD,
)
from dune_imperium.agents import (  # noqa: E402
    StateAgent,
    make_agent,
    network_search_agent,
)
from dune_imperium.agents.network_search_agent import (  # noqa: E402
    NetworkSearchAgent,
    SearchResult,
    adds_only_strength,
    finished_reward,
    holds_combat_lead,
    orders_agent_effects,
)
from dune_imperium.agents.registry import SEARCH_PREFIX, is_agent_kind  # noqa: E402
from dune_imperium.core.actions import DomainAction  # noqa: E402
from dune_imperium.core.chance import ChanceResolver  # noqa: E402
from dune_imperium.core.decisions import (  # noqa: E402
    ChanceDecision,
    PlayerDecision,
)
from dune_imperium.core.observation import PlayerView  # noqa: E402
from dune_imperium.core.state import GamePhase, GameState  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.rules.endgame import final_standings  # noqa: E402
from dune_imperium.rules.frames import FrameKind  # noqa: E402
from dune_imperium.training.checkpoint import save_checkpoint  # noqa: E402
from dune_imperium.training.network import PolicyValueNetwork  # noqa: E402
from dune_imperium.training.policy import without_undo_actions  # noqa: E402


def _checkpoint(tmp_path: Path, config: RulesetConfig) -> str:
    from dune_imperium.adapters.action_codec import ActionCodec

    torch.manual_seed(0)
    network = PolicyValueNetwork(ActionCodec(config).size, hidden=(32,))
    path = tmp_path / "policy.pt"
    save_checkpoint(path, network, ruleset=config.identifier, iteration=1)
    return str(path)


def _mid_game(config: RulesetConfig, seed: int, rounds: int) -> GameState:
    """Advance a heuristic game until ``rounds`` have begun."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [make_agent("heuristic", index) for index in range(config.players)]
    while state.round_number < rounds and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        choice = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), actions
        )
        state = engine.apply(state, choice).state
    return state


def test_a_search_seat_enters_by_file_like_a_checkpoint(tmp_path: Path) -> None:
    config = RulesetConfig()
    kind = f"{SEARCH_PREFIX}{_checkpoint(tmp_path, config)}"

    assert is_agent_kind(kind)
    assert not is_agent_kind(SEARCH_PREFIX)
    agent = make_agent(kind, 0)
    # The runner must hand it the state, or it would only play greedily.
    assert isinstance(agent, StateAgent)
    assert isinstance(agent, NetworkSearchAgent)
    # A plain seat reads its leaves from its own network.
    assert agent.value_network is agent.greedy.network
    # The measured defaults: effect ordering left to the network, five
    # candidates, eight worlds.
    assert agent.search_effect_order is False
    assert (agent.candidates, agent.rollouts) == (5, 8)
    with pytest.raises(ValueError, match="must not be negative"):
        NetworkSearchAgent(_checkpoint(tmp_path, config), seed=-1)
    with pytest.raises(ValueError, match="positive"):
        NetworkSearchAgent(_checkpoint(tmp_path, config), seed=0, rollouts=0)


def _other_checkpoint(tmp_path: Path, config: RulesetConfig) -> str:
    """A second file of the same shape with different weights."""

    from dune_imperium.adapters.action_codec import ActionCodec

    torch.manual_seed(1)
    network = PolicyValueNetwork(ActionCodec(config).size, hidden=(32,))
    path = tmp_path / "value.pt"
    save_checkpoint(path, network, ruleset=config.identifier, iteration=1)
    return str(path)


def _searched_decision(
    config: RulesetConfig, seed: int
) -> tuple[GameState, PlayerView, tuple[DomainAction, ...]]:
    """A mid-game decision that offers a choice."""

    engine = UprisingRulesEngine()
    state = _mid_game(config, seed=seed, rounds=2)
    decision = engine.current_decision(state)
    while isinstance(decision, ChanceDecision):
        state = engine.apply(state, ChanceResolver(seed=seed).resolve(decision)).state
        decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    actions = engine.legal_actions(state, decision.owner)
    assert len(without_undo_actions(actions)) > 1
    return state, engine.observe(state, decision.owner), actions


def test_a_search_seat_can_read_its_leaves_from_another_file(tmp_path: Path) -> None:
    """``search:P::value=V`` plays P's policy and scores leaves with V's value."""

    config = RulesetConfig()
    policy, value = _checkpoint(tmp_path, config), _other_checkpoint(tmp_path, config)
    kind = f"{SEARCH_PREFIX}{policy}::value={value}"

    assert is_agent_kind(kind)
    agent = make_agent(kind, 0)
    assert isinstance(agent, NetworkSearchAgent)
    plain = NetworkSearchAgent(policy, seed=0)
    other = NetworkSearchAgent(value, seed=0)
    state, view, actions = _searched_decision(config, seed=5)

    # The policy is the first file's: same shortlist logits.
    assert np.array_equal(agent._logits(view, actions), plain._logits(view, actions))
    # The leaves are the second file's value head, not the first's.
    assert agent._leaf_value(view) == other._leaf_value(view)
    assert agent._leaf_value(view) != plain._leaf_value(view)
    assert not is_agent_kind(f"{SEARCH_PREFIX}{policy}::value=")
    assert not is_agent_kind(f"{SEARCH_PREFIX}::value={value}")
    with pytest.raises(ValueError, match="after ::value="):
        make_agent(f"{SEARCH_PREFIX}{policy}::value=", 0)
    with pytest.raises(ValueError, match="needs a path"):
        make_agent(f"{SEARCH_PREFIX}::value={value}", 0)


def test_a_seat_reading_its_own_file_as_value_searches_like_the_plain_seat(
    tmp_path: Path,
) -> None:
    """The option changes nothing when both parts come from one file."""

    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    state, view, actions = _searched_decision(config, seed=5)

    plain = NetworkSearchAgent(path, seed=3, candidates=3, rollouts=2)
    same = make_agent(f"{SEARCH_PREFIX}{path}::value={path}", 3)
    assert isinstance(same, NetworkSearchAgent)
    same.candidates, same.rollouts = 3, 2

    expected = plain.search_with_state(state, view, actions)
    assert expected.searched
    assert same.search_with_state(state, view, actions) == expected


def test_search_picks_among_the_network_s_own_best_actions(tmp_path: Path) -> None:
    """The search never leaves the candidate set, and repeats its own choice.

    The candidates are the network's highest-logit legal actions, so a
    searched decision is the network's shortlist re-ordered by playouts --
    not a free choice over the whole legal set.
    """

    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    state = _mid_game(config, seed=5, rounds=2)
    decision = engine.current_decision(state)
    while isinstance(decision, ChanceDecision):
        state = engine.apply(state, ChanceResolver(seed=5).resolve(decision)).state
        decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    actions = engine.legal_actions(state, decision.owner)
    view = engine.observe(state, decision.owner)
    if len(actions) < 2:  # pragma: no cover - the seed above yields a choice
        pytest.skip("need a decision with more than one legal action")

    agent = NetworkSearchAgent(path, seed=3, candidates=2, rollouts=1)
    chosen = agent.choose_action_with_state(state, view, actions)

    assert chosen in actions
    # It is one of the two the network ranks highest.
    order = (-agent._logits(view, actions)).argsort(kind="stable")
    assert chosen in [actions[index] for index in order[:2]]
    # Same seed, same state, same answer.
    twin = NetworkSearchAgent(path, seed=3, candidates=2, rollouts=1)
    assert twin.choose_action_with_state(state, view, actions) == chosen


def test_the_search_answers_a_run_of_decisions_legally(tmp_path: Path) -> None:
    """Drive a game with a search seat for a stretch of real decisions.

    The whole game at the measured knobs (four worlds, three candidates)
    costs minutes, so this drives a bounded run at one world and two
    candidates: every answer must be a legal action of that decision, and
    the engine must accept it.
    """

    config = RulesetConfig()
    agent = NetworkSearchAgent(
        _checkpoint(tmp_path, config), seed=2, rollouts=1, candidates=2
    )
    engine = UprisingRulesEngine()
    state = _mid_game(config, seed=9, rounds=2)
    chance = ChanceResolver(seed=99)
    searched = 0

    while searched < 8 and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        view = engine.observe(state, decision.owner)
        choice = agent.choose_action_with_state(state, view, actions)
        assert choice in actions
        if len(actions) > 1:
            searched += 1
        state = engine.apply(state, choice, legal_actions=actions).state

    assert searched == 8


def test_without_a_state_the_search_plays_the_network_greedily(
    tmp_path: Path,
) -> None:
    """The no-state path is the plain checkpoint agent's choice.

    Both are asked once from fresh agents: ``NetworkAgent`` keeps a cycle
    guard that deliberately answers differently the second time it meets the
    same position, so re-asking one agent is not the comparison.
    """

    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    state = _mid_game(config, seed=5, rounds=2)
    decision = engine.current_decision(state)
    while isinstance(decision, ChanceDecision):
        state = engine.apply(state, ChanceResolver(seed=5).resolve(decision)).state
        decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    actions = engine.legal_actions(state, decision.owner)
    view = engine.observe(state, decision.owner)

    searcher = make_agent(f"{SEARCH_PREFIX}{path}", 4)
    plain = make_agent(f"checkpoint:{path}", 4)

    assert searcher.choose_action(view, actions) == plain.choose_action(view, actions)


def _first_choice(config: RulesetConfig, seed: int, effect_order: bool) -> GameState:
    """Play heuristic seats to the first multi-action decision of one kind."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [make_agent("heuristic", index) for index in range(config.players)]
    while state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        if len(actions) > 1 and orders_agent_effects(state) is effect_order:
            return state
        choice = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), actions
        )
        state = engine.apply(state, choice).state
    raise AssertionError("no such decision in the game")  # pragma: no cover


def test_effect_ordering_can_be_left_to_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With ``search_effect_order=False`` only Agent-effect ordering skips search.

    That decision is answered by the greedy network without a single
    playout, and every other decision is still searched.
    """

    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    playouts: list[int] = []

    def counting(self: NetworkSearchAgent, *args: object) -> float:
        playouts.append(1)
        return 0.0

    monkeypatch.setattr(NetworkSearchAgent, "_playout", counting)
    agent = NetworkSearchAgent(
        path, seed=1, rollouts=1, candidates=2, search_effect_order=False
    )

    ordering = _first_choice(config, seed=7, effect_order=True)
    decision = engine.current_decision(ordering)
    assert isinstance(decision, PlayerDecision)
    assert decision.prompt == "Choose the next Agent-turn effect to resolve"
    actions = engine.legal_actions(ordering, decision.owner)
    view = engine.observe(ordering, decision.owner)
    chosen = agent.choose_action_with_state(ordering, view, actions)
    assert playouts == []
    assert chosen == make_agent(f"checkpoint:{path}", 1).choose_action(view, actions)

    other = _first_choice(config, seed=7, effect_order=False)
    decision = engine.current_decision(other)
    assert isinstance(decision, PlayerDecision)
    agent.choose_action_with_state(
        other,
        engine.observe(other, decision.owner),
        engine.legal_actions(other, decision.owner),
    )
    assert playouts


def test_the_cycle_guard_steers_a_repeated_decision_to_an_untried_move() -> None:
    """``_Taken``: an identical decision (observation and legal set) in the
    same round is steered to a move not yet made there; once every move was
    made, all are offered again, and a new round forgets them."""

    from dune_imperium.agents.network_search_agent import _Taken

    guard = _Taken()
    first, second = DomainAction("x", 0), DomainAction("y", 0)
    encoded = np.zeros(3, dtype=np.int32)
    key, moves = guard.untried(1, 0, encoded, (first, second))
    assert tuple(moves) == (first, second)
    guard.record(key, first)
    again, moves = guard.untried(1, 0, encoded, (first, second))
    assert again == key and tuple(moves) == (second,)
    assert guard.breaks == 1
    guard.record(key, second)
    assert tuple(guard.untried(1, 0, encoded, (first, second))[1]) == (first, second)
    assert tuple(guard.untried(2, 0, encoded, (first, second))[1]) == (first, second)


def test_a_search_seat_finishes_a_turn_whose_boxes_offer_the_same_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ghola copying From the Tanks: both grafted boxes offer the same plain
    resolution (box 0's untagged, box 1's ``box=1``, codec v143). A search
    seat that always ranks the box rows first resolves each box once and
    ends the turn: there is no switch to loop on any more (it once stalled
    a tournament match, docs/evaluation/m10-2026-09-22.md section 13)."""

    from tests.unit.rules.test_graft_boxes import GHOLA, IMMORTALITY, TANKS
    from tests.unit.rules.test_graft_boxes import _graft as graft
    from tests.unit.rules.test_graft_boxes import _state as box_state

    path = _checkpoint(tmp_path, IMMORTALITY)
    engine = UprisingRulesEngine()
    state = graft(box_state((GHOLA, TANKS), troops_supply=9), GHOLA, "arrakeen", TANKS)

    def boxes_first(
        self: NetworkSearchAgent, encoded: np.ndarray, legal: Sequence[DomainAction]
    ) -> np.ndarray:
        return np.array(
            [float(action.action_id == "resolve_agent_card_effect") for action in legal]
        )

    monkeypatch.setattr(NetworkSearchAgent, "_scores", boxes_first)
    monkeypatch.setattr(NetworkSearchAgent, "_leaf_value", lambda self, view: 0.0)
    agent = NetworkSearchAgent(
        path,
        seed=0,
        rollouts=1,
        candidates=2,
        max_rollout_steps=300,
        search_effect_order=True,
    )
    resolved = 0
    for _ in range(40):
        decision = engine.current_decision(state)
        if not isinstance(decision, PlayerDecision) or decision.owner != 0:
            break
        actions = engine.legal_actions(state, 0)
        choice = agent.choose_action_with_state(
            state, engine.observe(state, 0), actions
        )
        resolved += choice.action_id == "resolve_agent_card_effect"
        state = engine.apply(state, choice, legal_actions=actions).state
    else:  # pragma: no cover - the failure this test guards against
        pytest.fail("the search seat never ended its grafted turn")
    assert resolved == 2
    # Three troops, From the Tanks' two twice and Arrakeen's one (a Combat
    # space, so some may have been deployed).
    seat = state.players[0]
    assert seat.troops_garrison + seat.troops_conflict == 3 + 2 + 2 + 1


def test_a_finished_playout_is_read_as_the_value_head_s_reward(
    tmp_path: Path,
) -> None:
    """A playout that ends the game scores the winner's or a loser's reward.

    Unfinished playouts are read by the value head, trained toward exactly
    those rewards. The rank ladder used before (100/70/40/10) put any
    finished playout, even a fourth place, above every unfinished one.
    """

    config = RulesetConfig()
    state = _mid_game(config, seed=3, rounds=99)
    assert state.phase is GamePhase.FINISHED
    standings = final_standings(state)
    winner = next(s.player for s in standings if s.rank == 1)
    last = next(s.player for s in standings if s.rank == config.players)

    assert finished_reward(state, winner) == WINNER_REWARD
    assert finished_reward(state, last) == LOSER_REWARD
    agent = NetworkSearchAgent(_checkpoint(tmp_path, config), seed=0)
    horizon = state.round_number + 1
    assert agent._playout(state, winner, horizon, 0) == WINNER_REWARD
    assert agent._playout(state, last, horizon, 0) == LOSER_REWARD


def test_a_playout_reaching_the_horizon_is_read_after_the_round_start_draw(
    tmp_path: Path,
) -> None:
    """The leaf is read once the hands are drawn, not at the Control defense.

    Round Start reveals, asks the optional defense, then draws [Main p. 8]
    [Main p. 20] (OQ-072). The round number moves at the reveal, so a
    playout that stopped there read a state with every hand empty, one the
    value head never trained on.
    """

    from dataclasses import replace

    from dune_imperium.rules.phases import prepare_round_start
    from dune_imperium.rules.setup import create_initial_state

    config = RulesetConfig()
    setup = create_initial_state(
        config,
        seed=71,
        leader_ids=(
            "feyd_rautha_harkonnen",
            "gurney_halleck",
            "lady_amber_metulli",
            "lady_jessica",
        ),
    ).state
    controller = replace(setup.players[2], control_space_ids=("arrakeen",))
    setup = replace(
        setup,
        players=(*setup.players[:2], controller, setup.players[3]),
        conflict_deck=(
            "siege_of_arrakeen",
            *(card for card in setup.conflict_deck if card != "siege_of_arrakeen"),
        ),
    )
    state = prepare_round_start(setup).state
    assert state.phase is GamePhase.ROUND_START
    assert state.round_number == 1
    leaves: list[PlayerView] = []

    class Recording(NetworkSearchAgent):
        def _leaf_value(self, view: PlayerView) -> float:
            leaves.append(view)
            return 0.0

    agent = Recording(_checkpoint(tmp_path, config), seed=0)
    agent._playout(state, 0, state.round_number, 0)

    (leaf,) = leaves
    assert leaf.phase is GamePhase.PLAYER_TURNS
    assert leaf.round_number == state.round_number
    assert leaf.private is not None
    assert len(leaf.private.hand) == 5


def test_a_search_result_carries_the_values_behind_its_choice(tmp_path: Path) -> None:
    """``search_with_state`` returns the candidates and per-world values.

    Expert iteration trains on these values, so the choice must be exactly
    the first candidate with the largest summed value, and the same agent
    state must give the same choice through ``choose_action_with_state``.
    """

    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    state = _first_choice(config, seed=7, effect_order=False)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    actions = engine.legal_actions(state, decision.owner)
    view = engine.observe(state, decision.owner)

    agent = NetworkSearchAgent(path, seed=5, rollouts=2, candidates=2)
    result = agent.search_with_state(state, view, actions)

    assert result.searched
    assert len(result.candidates) == 2
    assert set(result.candidates) <= set(actions)
    assert len(result.values) == 2 and all(len(row) == 2 for row in result.values)
    totals = result.totals
    assert result.chosen == result.candidates[totals.index(max(totals))]
    twin = NetworkSearchAgent(path, seed=5, rollouts=2, candidates=2)
    assert twin.choose_action_with_state(state, view, actions) == result.chosen


def test_candidates_can_be_evaluated_without_letting_the_search_choose(
    tmp_path: Path,
) -> None:
    """``candidate_order`` and ``evaluate_candidates`` repeat a searched decision.

    Expert iteration labels a greedy player's decisions: it asks the search
    for its ranking and its playout values without the search choosing, so
    both must equal what ``search_with_state`` computes for the same seed.
    """

    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    state = _first_choice(config, seed=7, effect_order=False)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    actions = engine.legal_actions(state, decision.owner)
    view = engine.observe(state, decision.owner)

    searched = NetworkSearchAgent(path, seed=5, rollouts=2, candidates=2)
    result = searched.search_with_state(state, view, actions)
    labeller = NetworkSearchAgent(path, seed=5, rollouts=2, candidates=2)
    ranked = labeller.candidate_order(view, actions)

    assert ranked[:2] == result.candidates
    assert labeller.evaluate_candidates(state, view.player, ranked[:2]) == result.values


def _base_checkpoint_with_templates(tmp_path: Path) -> str:
    """A small file trained without Arrakeen Scouts, carrying its catalog."""

    from dune_imperium.adapters.action_codec import ActionCodec

    base = RulesetConfig()
    codec = ActionCodec(base)
    torch.manual_seed(0)
    network = PolicyValueNetwork(codec.size, hidden=(32,))
    path = tmp_path / "base.pt"
    save_checkpoint(
        path, network, ruleset=base.identifier, iteration=1, codec=codec
    )
    return str(path)


def _untrained_only_states(
    agent: NetworkSearchAgent, config: RulesetConfig, seed: int, count: int
) -> list[GameState]:
    """States of a heuristic game at decisions the file was never trained on."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    players = [make_agent("heuristic", index) for index in range(config.players)]
    found: list[GameState] = []
    while len(found) < count and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        offered = without_undo_actions(actions)
        if len(offered) > 1 and agent._untrained_only(offered):
            found.append(state)
        choice = players[decision.owner].choose_action(
            engine.observe(state, decision.owner), actions
        )
        state = engine.apply(state, choice).state
    return found


def test_a_search_seat_hands_untrained_only_scouts_decisions_to_a_heuristic(
    tmp_path: Path,
) -> None:
    # Design D6 (2026-09-30): a search seat may play Arrakeen Scouts. Its
    # file never saw a Scouts template, so a decision offering only those has
    # tied zero logits and no shortlist to search: the seat answers it with
    # the heuristic its greedy agent holds, seeded with the agent seed.
    from dune_imperium.agents.heuristic_agent import HeuristicAgent

    scouts = RulesetConfig(arrakeen_scouts=True)
    path = _base_checkpoint_with_templates(tmp_path)
    agent = NetworkSearchAgent(path, seed=4, rollouts=1, candidates=2, config=scouts)
    twin = HeuristicAgent(seed=4)
    engine = UprisingRulesEngine()
    assert agent.greedy.codec.config == scouts

    states = _untrained_only_states(agent, scouts, seed=6, count=3)
    assert len(states) == 3
    for state in states:
        decision = engine.current_decision(state)
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        view = engine.observe(state, decision.owner)
        result = agent.search_with_state(state, view, actions)
        assert not result.searched
        assert result.chosen == twin.choose_action(view, without_undo_actions(actions))


def test_search_playouts_hand_untrained_only_decisions_to_a_seeded_heuristic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inside a playout every seat's untrained-only decision goes to a
    heuristic seeded from the playout's chance seed, so the playout stays
    reproducible and two candidates meet the same answers."""

    from dune_imperium.agents import network_search_agent as module
    from dune_imperium.agents.heuristic_agent import HeuristicAgent

    seeds: list[int] = []

    class _Counting(HeuristicAgent):
        def __post_init__(self) -> None:
            super().__post_init__()
            seeds.append(self.seed)

    monkeypatch.setattr(module, "HeuristicAgent", _Counting)
    scouts = RulesetConfig(arrakeen_scouts=True)
    agent = NetworkSearchAgent(
        _base_checkpoint_with_templates(tmp_path),
        seed=4,
        rollouts=1,
        candidates=2,
        config=scouts,
    )
    (state,) = _untrained_only_states(agent, scouts, seed=6, count=1)
    decision = UprisingRulesEngine().current_decision(state)
    assert isinstance(decision, PlayerDecision)

    horizon = state.round_number + 1
    first = agent._playout(state, decision.owner, horizon, 11)
    assert seeds == [11]
    assert agent._playout(state, decision.owner, horizon, 11) == first


# -- retracing recorded decisions (a loaded save) ---------------------------


@dataclass(frozen=True)
class _Decided:
    """One decision of a search seat, its answer, and its memory after it."""

    state: GameState
    view: PlayerView
    actions: tuple[DomainAction, ...]
    result: SearchResult
    kind: str
    memory_after: tuple[object, ...]


def _memory(agent: NetworkSearchAgent) -> tuple[object, ...]:
    """Everything a search seat remembers from one decision to the next.

    Its RNG stream and cycle guard, and its greedy agent's guard and lazily
    built heuristic fallback (whose RNG the untrained-only decisions use).
    """

    greedy = agent.greedy
    fallback = greedy._fallback
    return (
        agent._rng.getstate(),
        agent._taken._round,
        {key: frozenset(taken) for key, taken in agent._taken._taken.items()},
        agent._taken.breaks,
        greedy._guard._round,
        {key: frozenset(taken) for key, taken in greedy._guard._taken.items()},
        None if fallback is None else fallback._rng.getstate(),
    )


def _search_seat_game(
    agent: NetworkSearchAgent, config: RulesetConfig, seed: int, seat: int, count: int
) -> list[_Decided]:
    """Play ``agent`` in ``seat`` beside heuristics for ``count`` decisions."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    others = [make_agent("heuristic", index) for index in range(config.players)]
    decided: list[_Decided] = []
    while len(decided) < count and state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        view = engine.observe(state, decision.owner)
        if decision.owner != seat:
            choice = others[decision.owner].choose_action(view, actions)
            state = engine.apply(state, choice, legal_actions=actions).state
            continue
        offered = without_undo_actions(actions)
        if orders_agent_effects(state):
            kind = "effect order"
        elif len(offered) == 1:
            kind = "forced"
        elif agent._untrained_only(offered):
            kind = "untrained"
        else:
            kind = "shortlist"
        result = agent.search_with_state(state, view, actions)
        if result.searched:
            kind = "searched"
        decided.append(_Decided(state, view, actions, result, kind, _memory(agent)))
        state = engine.apply(state, result.chosen, legal_actions=actions).state
    return decided


@pytest.mark.parametrize(
    "expansion", [None, "arrakeen_scouts", "immortality"], ids=["base", "scouts", "imm"]
)
def test_a_retraced_search_seat_answers_like_the_one_that_searched(
    tmp_path: Path, expansion: str | None
) -> None:
    """Retracing decisions 1..k leaves the seat where searching them did.

    A loaded save tells a fresh search seat its recorded answers instead of
    running the playouts again (``replay_decision``); its next answers must
    be the ones the saved seat would have given, so its RNG stream and its
    cycle guard end where the searching seat's did, and the greedy agent's
    own guard and heuristic fallback too. The Scouts game seats a file
    trained without Scouts, so some decisions go to that heuristic; the
    Immortality game offers the Family Atomics token, which the app's rule
    keeps or spends.
    """

    config = RulesetConfig(**({expansion: True} if expansion else {}))
    path = _base_checkpoint_with_templates(tmp_path)

    def seat_agent() -> NetworkSearchAgent:
        return NetworkSearchAgent(
            path, seed=11, rollouts=2, candidates=2, config=config
        )

    decided = _search_seat_game(seat_agent(), config, seed=3, seat=1, count=70)
    assert len(decided) == 70
    kinds = {entry.kind for entry in decided}
    assert {"searched", "effect order", "forced"} <= kinds
    if expansion == "arrakeen_scouts":
        assert "untrained" in kinds

    for split in (9, 35, 69):
        twin = seat_agent()
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
    # Each part of the game the splits cut was searched somewhere.
    assert any(entry.kind == "searched" for entry in decided[:9])
    assert any(entry.kind == "searched" for entry in decided[35:])


def test_retracing_refuses_an_answer_the_seat_could_not_have_given(
    tmp_path: Path,
) -> None:
    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)

    def seat_agent() -> NetworkSearchAgent:
        return NetworkSearchAgent(path, seed=5, rollouts=2, candidates=2)

    decided = _search_seat_game(seat_agent(), config, seed=4, seat=2, count=40)

    def refused(index: int, action: DomainAction) -> bool:
        twin = seat_agent()
        for entry in decided[:index]:
            assert twin.replay_decision(
                entry.state, entry.view, entry.actions, entry.result.chosen
            )
        entry = decided[index]
        return not twin.replay_decision(entry.state, entry.view, entry.actions, action)

    # A searched decision: an offered action the network did not shortlist.
    index, entry = next(
        (index, entry)
        for index, entry in enumerate(decided)
        if entry.kind == "searched"
        and len(without_undo_actions(entry.actions)) > len(entry.result.candidates)
    )
    outside = next(
        action
        for action in without_undo_actions(entry.actions)
        if action not in entry.result.candidates
    )
    assert refused(index, outside)
    # The candidate the playouts did not pick is still a possible answer.
    other = next(
        action for action in entry.result.candidates if action != entry.result.chosen
    )
    assert not refused(index, other)
    # A decision the greedy network answers: anything but its answer.
    index, entry = next(
        (index, entry)
        for index, entry in enumerate(decided)
        if entry.kind == "effect order"
    )
    wrong = next(action for action in entry.actions if action != entry.result.chosen)
    assert refused(index, wrong)


FAMILY_ATOMICS = DomainAction("use_family_atomics", 0)


def _atomics_checkpoint(tmp_path: Path, config: RulesetConfig) -> str:
    """A network that ranks the Family Atomics token first wherever offered."""

    from dune_imperium.adapters.action_codec import ActionCodec

    torch.manual_seed(0)
    codec = ActionCodec(config)
    network = PolicyValueNetwork(codec.size, hidden=(32,))
    with torch.no_grad():
        network.policy_head.bias[codec.encode(FAMILY_ATOMICS)] = 50.0
    path = tmp_path / "atomics.pt"
    save_checkpoint(path, network, ruleset=config.identifier, iteration=1)
    return str(path)


def _first_atomics_choice(config: RulesetConfig, seed: int) -> GameState:
    """Play heuristic seats to the first Agent-effect choice offering the token."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [make_agent("heuristic", index) for index in range(config.players)]
    while state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        if orders_agent_effects(state) and any(
            action.action_id == FAMILY_ATOMICS.action_id for action in actions
        ):
            return state
        choice = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), actions
        )
        state = engine.apply(state, choice).state
    raise AssertionError("no such decision in the game")  # pragma: no cover


def test_the_app_s_rule_decides_when_a_search_seat_spends_family_atomics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A network that always spends the token is overruled by the app's rule.

    With ``family_atomics="network"`` the seat spends it at the first Agent
    effect choice, as the trained networks do; by default it asks the app's
    rule, keeps the token when the rule says no and spends it when it says
    yes.
    """

    config = RulesetConfig(immortality=True)
    path = _atomics_checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    state = _first_atomics_choice(config, seed=3)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    actions = engine.legal_actions(state, seat)
    view = engine.observe(state, seat)
    asked: list[int] = []

    def rule(answer: bool) -> object:
        def ask(state: GameState, observation: PlayerView) -> bool:
            asked.append(observation.player)
            return answer

        return ask

    def seat_agent(family_atomics: str = "app") -> NetworkSearchAgent:
        return NetworkSearchAgent(
            path,
            seed=1,
            rollouts=1,
            candidates=2,
            config=config,
            family_atomics=family_atomics,
        )

    monkeypatch.setattr(network_search_agent, "app_uses_family_atomics", rule(False))
    chosen = seat_agent(family_atomics="network").choose_action_with_state(
        state, view, actions
    )
    assert chosen.action_id == FAMILY_ATOMICS.action_id
    assert asked == []

    chosen = seat_agent().choose_action_with_state(state, view, actions)
    assert chosen.action_id != FAMILY_ATOMICS.action_id
    assert asked == [seat]
    # Without a state the rule cannot be read, and the seat keeps the token.
    assert seat_agent().choose_action(view, actions).action_id != "use_family_atomics"

    monkeypatch.setattr(network_search_agent, "app_uses_family_atomics", rule(True))
    chosen = seat_agent().choose_action_with_state(state, view, actions)
    assert chosen.action_id == FAMILY_ATOMICS.action_id


def test_every_seat_of_a_playout_follows_the_app_s_family_atomics_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The playouts ask the rule for every seat that is offered the token.

    Under a rule that always keeps it, no playout spends it, although the
    network ranks it first; the same playouts with the network deciding do.
    """

    config = RulesetConfig(immortality=True)
    path = _atomics_checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    state = _first_atomics_choice(config, seed=3)
    decision = engine.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    candidates = tuple(
        action
        for action in without_undo_actions(engine.legal_actions(state, seat))
        if action.action_id != FAMILY_ATOMICS.action_id
    )[:2]
    applied: list[str] = []
    real_apply = UprisingRulesEngine.apply

    def recording(self: UprisingRulesEngine, *args: object, **kwargs: object) -> object:
        step = args[1]
        if isinstance(step, DomainAction):
            applied.append(step.action_id)
        return real_apply(self, *args, **kwargs)  # type: ignore[arg-type]

    asked: list[int] = []

    def keep(state: GameState, observation: PlayerView) -> bool:
        asked.append(observation.player)
        return False

    monkeypatch.setattr(UprisingRulesEngine, "apply", recording)
    monkeypatch.setattr(network_search_agent, "app_uses_family_atomics", keep)

    searcher = NetworkSearchAgent(path, seed=1, rollouts=1, config=config)
    searcher.evaluate_candidates(state, seat, candidates)
    assert FAMILY_ATOMICS.action_id not in applied
    assert set(asked) - {seat}

    applied.clear()
    networked = NetworkSearchAgent(
        path, seed=1, rollouts=1, config=config, family_atomics="network"
    )
    networked.evaluate_candidates(state, seat, candidates)
    assert FAMILY_ATOMICS.action_id in applied


def test_a_search_seat_names_who_decides_family_atomics(tmp_path: Path) -> None:
    path = _checkpoint(tmp_path, RulesetConfig())
    with pytest.raises(ValueError, match="family_atomics"):
        NetworkSearchAgent(path, seed=0, family_atomics="heuristic")


def _play(card: str, option: int) -> DomainAction:
    return DomainAction(
        "play_intrigue", 0, (("card_id", f"intrigue:{card}:0"), ("option", option))
    )


def test_a_combat_intrigue_that_only_adds_strength_is_recognised() -> None:
    assert adds_only_strength(_play("spice_is_power", 1))  # pay 3 spice: 6 swords
    assert adds_only_strength(_play("weirding_combat", 0))
    assert not adds_only_strength(_play("spice_is_power", 0))  # retreat: 3 spice
    assert not adds_only_strength(_play("devour", 0))  # also trashes a card
    assert not adds_only_strength(_play("contingency_plan", 0))  # the Plot half
    assert not adds_only_strength(DomainAction("pass_combat_intrigue", 0))


def _combat_intrigue_choices(
    config: RulesetConfig, seed: int
) -> list[tuple[GameState, int, tuple[DomainAction, ...]]]:
    """Every Combat Intrigue decision of a heuristic game offering such a card."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [make_agent("heuristic", index) for index in range(config.players)]
    found = []
    while state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        actions = engine.legal_actions(state, decision.owner)
        if state.decision_stack[-1].kind == FrameKind.COMBAT_INTRIGUE and any(
            adds_only_strength(action) for action in actions
        ):
            found.append((state, decision.owner, actions))
        choice = agents[decision.owner].choose_action(
            engine.observe(state, decision.owner), actions
        )
        state = engine.apply(state, choice).state
    return found


def _alone_in_the_lead(state: GameState, seat: int) -> bool:
    mine = state.players[seat].combat_strength
    return all(
        player.combat_strength < mine
        for index, player in enumerate(state.players)
        if index != seat
    )


def test_a_search_seat_holds_strength_intrigue_only_while_alone_in_the_lead(
    tmp_path: Path,
) -> None:
    """Passing keeps every option while the seat leads `[Main p. 14]`; tied
    or behind, the cards stay offered."""

    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    choices = _combat_intrigue_choices(config, seed=0)
    leading = [c for c in choices if _alone_in_the_lead(c[0], c[1])]
    trailing = [c for c in choices if not _alone_in_the_lead(c[0], c[1])]
    assert leading and trailing

    for state, seat, actions in leading:
        held = holds_combat_lead(state, seat, actions)
        assert held == tuple(a for a in actions if not adds_only_strength(a))
        view = engine.observe(state, seat)
        plan = NetworkSearchAgent(path, seed=1, config=config)._shortlist(
            state, view, actions
        )
        chosen = plan if isinstance(plan, DomainAction) else plan.candidates
        assert not any(
            adds_only_strength(action)
            for action in ((chosen,) if isinstance(chosen, DomainAction) else chosen)
        )
        plain = NetworkSearchAgent(
            path, seed=1, config=config, hold_combat_lead=False
        )._shortlist(state, view, actions)
        assert not isinstance(plain, DomainAction)
        assert any(adds_only_strength(action) for action in plain.candidates)
    for state, seat, actions in trailing:
        assert holds_combat_lead(state, seat, actions) == actions


def _before_the_lead(config: RulesetConfig, seed: int) -> GameState:
    """A seat's last own decision before it alone leads at Combat Intrigue
    holding a card that only adds strength (that seat decides there)."""

    engine = UprisingRulesEngine()
    state = engine.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [make_agent("heuristic", index) for index in range(config.players)]
    last: dict[int, GameState] = {}
    while state.phase is not GamePhase.FINISHED:
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        seat = decision.owner
        actions = engine.legal_actions(state, seat)
        if state.decision_stack[-1].kind == FrameKind.COMBAT_INTRIGUE:
            if seat in last and _alone_in_the_lead(state, seat) and any(
                adds_only_strength(action) for action in actions
            ):
                return last[seat]
        else:
            last[seat] = state
        choice = agents[seat].choose_action(engine.observe(state, seat), actions)
        state = engine.apply(state, choice).state
    raise AssertionError("no such decision in the game")  # pragma: no cover


def test_every_seat_of_a_playout_holds_strength_intrigue_in_the_lead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = RulesetConfig()
    path = _checkpoint(tmp_path, config)
    engine = UprisingRulesEngine()
    start = _before_the_lead(config, seed=0)
    decision = engine.current_decision(start)
    assert isinstance(decision, PlayerDecision)
    candidates = without_undo_actions(engine.legal_actions(start, decision.owner))[:2]

    violations: list[DomainAction] = []
    real_apply = UprisingRulesEngine.apply

    def checking(self: UprisingRulesEngine, *args: object, **kwargs: object) -> object:
        before, step = args[0], args[1]
        if (
            isinstance(before, GameState)
            and isinstance(step, DomainAction)
            and before.decision_stack
            and before.decision_stack[-1].kind == FrameKind.COMBAT_INTRIGUE
            and adds_only_strength(step)
            and _alone_in_the_lead(before, step.actor)
        ):
            violations.append(step)
        return real_apply(self, *args, **kwargs)  # type: ignore[arg-type]

    held: list[int] = []
    real_hold = network_search_agent.holds_combat_lead

    def counting(
        state: GameState, seat: int, offered: tuple[DomainAction, ...]
    ) -> tuple[DomainAction, ...]:
        kept = real_hold(state, seat, offered)
        if len(kept) < len(offered):
            held.append(seat)
        return kept

    monkeypatch.setattr(UprisingRulesEngine, "apply", checking)
    monkeypatch.setattr(network_search_agent, "holds_combat_lead", counting)
    NetworkSearchAgent(path, seed=1, rollouts=4, config=config).evaluate_candidates(
        start, decision.owner, candidates
    )
    assert held
    assert violations == []
