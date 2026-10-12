"""The app's Family Atomics rule as a network seat borrows it."""

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.family_atomics import (
    FAMILY_ATOMICS_ACTION,
    app_uses_family_atomics,
)
from dune_imperium.agents.registry import make_agent
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules import UprisingRulesEngine


def _reveal_persuasion(state: GameState, seat: int) -> int | None:
    """The Persuasion of ``seat``'s own open Reveal frame, if any."""

    for frame in reversed(state.decision_stack):
        if frame.kind == "reveal":
            if getattr(frame.decision, "owner", None) != seat:
                return None
            value = dict(frame.context).get("persuasion")
            return value if isinstance(value, int) else None
    return None


def test_the_rule_spends_the_token_only_in_the_seat_s_reveal_with_4_to_8() -> None:
    """Over app_ai games: never outside the seat's own Reveal turn, never
    outside 4-8 Persuasion, and both answers occur."""

    config = RulesetConfig(immortality=True)
    engine = UprisingRulesEngine()
    spent = kept = 0
    for seed in (1, 2):
        state = engine.reset(config, seed)
        chance = ChanceResolver(seed=seed)
        agents = [make_agent("app_ai", seed * 10 + seat) for seat in range(4)]
        while state.phase is not GamePhase.FINISHED:
            decision = engine.current_decision(state)
            if isinstance(decision, ChanceDecision):
                state = engine.apply(state, chance.resolve(decision)).state
                continue
            assert isinstance(decision, PlayerDecision)
            seat = decision.owner
            actions = engine.legal_actions(state, seat)
            view = engine.observe(state, seat)
            if any(action.action_id == FAMILY_ATOMICS_ACTION for action in actions):
                if app_uses_family_atomics(state, view):
                    persuasion = _reveal_persuasion(state, seat)
                    assert persuasion is not None and 4 <= persuasion <= 8
                    spent += 1
                else:
                    kept += 1
            choice = agents[seat].choose_action_with_state(state, view, actions)
            state = engine.apply(state, choice, legal_actions=actions).state
    assert spent and kept
