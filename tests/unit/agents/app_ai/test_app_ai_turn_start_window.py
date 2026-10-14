"""The turn's start window answers as the app's one turn-start prompt did.

Until codec 146 our TURN frame offered Litany Against Fear
(``play_turn_start_card``) and Withdrawn (its turn-start ``play_intrigue``)
among the turn's usual choices, and app_ai ranked them in one
``DetermineTurn`` prompt. Since the user ruling of 2026-10-14 (OQ-095 (6))
the engine asks the start first and alone, with ``decline_turn_start``, and
the usual choices follow the refusal. ``windows/turn._turn_start_window``
answers the window by running that one prompt again. This test rebuilds the
earlier engine's list independently (the rule providers it was made of, in
their order) and checks, at every window of a real all-option game with an
app_ai seat at every level, that the window's answer is the play the
earlier prompt chose, or the refusal when it chose anything else, and that
a refusal leaves the agent's RNG and memory as they were.
"""

import copy
from collections import Counter

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.testing import make_profile
from dune_imperium.agents.app_ai.windows import turn
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase, GameState
from dune_imperium.rules.agent_turn import legal_turn_start_card_actions
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.rules.intrigue import legal_intrigue_play_actions

#: The rule options the play UI's setup screen starts with checked.
UI_DEFAULT_OPTIONS = {
    "choam_module": True,
    "leader_draft": True,
    "promo_cards": True,
    "bloodlines": True,
    "tech_module": True,
    "immortality": True,
    "go_to_11": True,
    "epic_game": True,
}
#: A game whose windows hold Litany alone (played and not), Withdrawn alone,
#: and both (picked 2026-10-14 from seeds 1-15).
GAME_SEED = 9
_EARLIER_ORDER = ("agent_turn", "play_turn_start_card", "reveal_turn", "play_intrigue")


def _earlier_prompt(
    engine: UprisingRulesEngine, state: GameState, seat: int, decline: DomainAction
) -> tuple[DomainAction, ...]:
    """The earlier TURN frame's list: the placements, the turn-start cards,
    the Reveal, every Plot (Withdrawn's included, the start being open),
    then the rest, as the engine lists them once the start is declined."""

    usual = engine.legal_actions(engine.apply(state, decline).state, seat)
    return (
        *(a for a in usual if a.action_id == "agent_turn"),
        *legal_turn_start_card_actions(state, seat),
        *(a for a in usual if a.action_id == "reveal_turn"),
        *legal_intrigue_play_actions(state, seat),
        *(a for a in usual if a.action_id not in _EARLIER_ORDER),
    )


def test_the_window_answers_as_the_one_turn_prompt_did() -> None:
    engine = UprisingRulesEngine()
    config = RulesetConfig(**UI_DEFAULT_OPTIONS)
    agents = [
        AppAIAgent(seed=100 * GAME_SEED + seat, level=(seat + GAME_SEED) % 3)
        for seat in range(4)
    ]
    state = engine.reset(config, GAME_SEED)
    chance = ChanceResolver(seed=GAME_SEED)
    seen: Counter[str] = Counter()
    for _ in range(30_000):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        seat = decision.owner
        legal = engine.legal_actions(state, seat)
        view = engine.observe(state, seat)
        decline = next((a for a in legal if a.action_id == "decline_turn_start"), None)
        if decline is not None:
            plays = tuple(a for a in legal if a != decline)
            earlier = _earlier_prompt(engine, state, seat, decline)
            # The window rebuilds exactly that list, in that order.
            profile = make_profile(state, seat)
            run = DecisionRun(profile.ctx, profile, legal, profile.rng, Memory())
            assert turn._prompt_with_start(run, plays, decline) == earlier
            # The earlier prompt's answer, from a copy of the live agent.
            was = copy.deepcopy(agents[seat]).choose_action_with_state(
                state, view, earlier
            )
            probe = copy.deepcopy(agents[seat])
            now = probe.choose_action_with_state(state, view, legal)
            kinds = {a.action_id for a in plays}
            if kinds == {"play_turn_start_card", "play_intrigue"}:
                seen["both"] += 1
            if was in plays:
                assert now == was
                seen[f"{was.action_id} played"] += 1
            else:
                assert now == decline
                assert probe._rng.getstate() == agents[seat]._rng.getstate()
                assert probe.memory == agents[seat].memory
                seen[f"{'+'.join(sorted(kinds))} declined"] += 1
        action = agents[seat].choose_action_with_state(state, view, legal)
        state = engine.apply(state, action, legal_actions=legal).state
    assert state.phase is GamePhase.FINISHED
    for agent in agents:
        assert not agent.fallbacks
    # The game covers each branch.
    assert seen["play_turn_start_card played"] > 0
    assert seen["play_turn_start_card declined"] > 0
    assert seen["play_intrigue declined"] > 0
    assert seen["both"] > 0
