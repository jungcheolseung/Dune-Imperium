"""App AI fallbacks found by the 2026-10-29 big soak (Uprising, every option).

``checkpoints/2026-10-29/big-soak``: 5,000 Uprising games with the four seat
kinds rotated (``app_ai``, ``app_ai_medium``, ``app_ai_easy``,
``heuristic``); two games had random answers, both from ``app_ai_easy``:

- 7802985: Possible Futures' box offered without an influence pick
  (``agent_effects`` 5);
- 7801278: Sardaukar II's recall with an earlier turn's Into the Fray Agent
  in the Conflict among the targets (``contract_reward_recall`` 1).
"""

import pytest

from dune_imperium.agents.registry import make_agent
from dune_imperium.config import RulesetConfig
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

LINEUP = ("app_ai", "app_ai_medium", "app_ai_easy", "heuristic")
EVERY_OPTION = RulesetConfig(
    choam_module=True,
    promo_cards=True,
    bloodlines=True,
    tech_module=True,
    immortality=True,
    go_to_11=True,
    epic_game=True,
    arrakeen_scouts=True,
    leader_draft=True,
)


@pytest.mark.parametrize("seed", [7802985, 7801278])
def test_the_big_soak_games_have_no_app_ai_fallback(seed: int) -> None:
    # The soak's seats: seat p plays LINEUP[(p + seed) % 4] with seed 4 x seed + p.
    agents = tuple(make_agent(LINEUP[(p + seed) % 4], 4 * seed + p) for p in range(4))
    run_policy_game(UprisingRulesEngine(), EVERY_OPTION, seed, agents)
    assert [dict(getattr(agent, "fallbacks", {})) for agent in agents] == [{}] * 4
