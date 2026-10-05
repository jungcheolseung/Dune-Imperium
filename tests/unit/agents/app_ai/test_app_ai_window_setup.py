"""The setup windows: the leader draft (spec/epic-goto11-promo-draft.md §5)."""

from collections import Counter

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine

ENGINE = UprisingRulesEngine()


def _draft(seed: int, agent_seed: int) -> tuple[GameState, list[AppAIAgent], list[str]]:
    """Run the leader draft with four app_ai seats; return the picks in order."""

    config = RulesetConfig(choam_module=True, leader_draft=True)
    state = ENGINE.reset(config, seed)
    chance = ChanceResolver(seed=seed)
    agents = [AppAIAgent(seed=agent_seed + seat) for seat in range(4)]
    picks: list[str] = []
    for _ in range(200):
        decision = ENGINE.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = ENGINE.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        if state.decision_stack[-1].kind != "leader_draft":
            return state, agents, picks
        seat = decision.owner
        actions = ENGINE.legal_actions(state, seat)
        view = ENGINE.observe(state, seat)
        action = agents[seat].choose_action_with_state(state, view, actions)
        assert action in actions
        if action.action_id == "pick_leader":
            picks.append(str(dict(action.arguments)["leader_id"]))
        state = ENGINE.apply(state, action, legal_actions=actions).state
    raise AssertionError("the draft never ended")


def test_every_draft_pick_is_mirrored_and_legal() -> None:
    state, agents, picks = _draft(seed=4, agent_seed=10)
    assert len(picks) == 4 == len(set(picks))
    fallbacks: Counter[str] = Counter()
    for agent in agents:
        fallbacks.update(agent.fallbacks)
    assert fallbacks["leader_draft"] == 0
    assert sum(agent.mirrored["leader_draft"] for agent in agents) == 4
    assert state.decision_stack[-1].kind != "leader_draft"


def test_picks_are_uniform_not_evaluated() -> None:
    """``ChooseStartingLeaderEvaluator`` picks at random: the same table gives
    different first picks for different agent seeds, and the same seeds give
    the same draft."""

    first = Counter(_draft(seed=4, agent_seed=s)[2][0] for s in range(0, 400, 4))
    assert len(first) == 6  # every leader of the shared pool gets picked
    assert max(first.values()) < 35  # 100 draws over 6 leaders: no favourite
    assert _draft(seed=4, agent_seed=7)[2] == _draft(seed=4, agent_seed=7)[2]
