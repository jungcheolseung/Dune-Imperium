"""app_ai reads only what its seat may know, at the play UI's default options.

``test_app_ai_agent.py::test_choices_ignore_hidden_zones`` checks base +
CHOAM with Hard seats. The browser opens a game with CHOAM, the leader draft,
the promo cards, Bloodlines, the Tech Module, Immortality, Go to 11 and Epic
Game Mode checked (Arrakeen Scouts is one click away), and an app_ai seat
there faces human players, so its honesty is checked there too, with every
level seated.
"""

import copy
import random

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.determinize import determinize
from dune_imperium.core.chance import ChanceResolver
from dune_imperium.core.decisions import ChanceDecision, PlayerDecision
from dune_imperium.core.state import GamePhase
from dune_imperium.rules.engine import UprisingRulesEngine

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


@pytest.mark.parametrize(
    ("scouts", "game_seed"), [(False, 1), (True, 4)], ids=["ui-default", "scouts"]
)
def test_choices_ignore_hidden_zones_at_the_ui_defaults(
    scouts: bool, game_seed: int
) -> None:
    """Every multi-choice decision answers the same on a re-dealt twin.

    ``determinize`` re-deals exactly what the seat cannot see (deck orders,
    the opponents' hand/deck split, held Intrigue, the shared decks, the
    Tleilaxu deck) and leaves its view unchanged, so an honest agent answers
    the same on both states. Both answers come from copies of the live agent
    (same RNG position and memory); the live agent then plays on.
    """

    config = RulesetConfig(**UI_DEFAULT_OPTIONS, arrakeen_scouts=scouts)
    engine = UprisingRulesEngine()
    agents = [AppAIAgent(seed=200 + seat, level=seat % 3) for seat in range(4)]
    state = engine.reset(config, game_seed)
    chance = ChanceResolver(seed=game_seed)
    rng = random.Random(game_seed)
    checked: set[str] = set()
    decisions = 0
    for _ in range(30_000):
        if state.phase is GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        assert isinstance(decision, PlayerDecision)
        seat = decision.owner
        actions = engine.legal_actions(state, seat)
        view = engine.observe(state, seat)
        if len(actions) > 1:
            twin = determinize(state, seat, rng)
            assert engine.observe(twin, seat) == view
            on_twin = copy.deepcopy(agents[seat]).choose_action_with_state(
                twin, view, actions
            )
            on_state = copy.deepcopy(agents[seat]).choose_action_with_state(
                state, view, actions
            )
            assert on_twin == on_state, (decisions, view.decision_kind)
            checked.add(str(view.decision_kind))
            decisions += 1
        action = agents[seat].choose_action_with_state(state, view, actions)
        state = engine.apply(state, action, legal_actions=actions).state
    assert state.phase is GamePhase.FINISHED
    assert decisions > 300
    # The windows only the options reach were among the checked ones.
    assert {"turn", "reveal", "leader_draft"} <= checked
    assert any(kind.startswith("scouts_") for kind in checked) is scouts
    for agent in agents:
        assert not agent.fallbacks
