"""The windows that answer Rise of Ix's Tech tiles (plan §13): Flip and
trash activations in the turn, Agent-turn and Reveal windows, the acquire
effects, Disposal Facility, Sonic Snoopers' pick and Tech acquisition."""

import logging
from collections import Counter

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.agents.app_ai.windows import ix
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
from dune_imperium.config import BaseGame
from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, promo_cards=True, leader_draft=True
)
#: Windows whose Rise of Ix decisions are the Tech tiles' and the board's.
TECH_WINDOWS = (
    "turn",
    "reveal",
    "tech_acquisition",
    "intrigue_bottom_pick",
    "freighter_move",
    "shipping_reward_icons",
    "dreadnought_control_choice",
)


@pytest.fixture(scope="module")
def fallbacks() -> Counter[str]:
    counted: Counter[str] = Counter()
    previous = logging.getLogger("dune_imperium.agents.app_ai.agent").level
    try:
        for seed in (8000, 8001, 8002, 8003):
            agents = tuple(AppAIAgent(seed=seed * 10 + s) for s in range(4))
            run_policy_game(UprisingRulesEngine(), IX, seed, agents)
            for agent in agents:
                counted.update(agent.fallbacks)
    finally:
        logging.getLogger("dune_imperium.agents.app_ai.agent").setLevel(previous)
    return counted


def test_the_tech_and_board_windows_never_fall_back(fallbacks: Counter[str]) -> None:
    assert {k: n for k, n in fallbacks.items() if k in TECH_WINDOWS} == {}
    assert not [k for k in fallbacks if k.startswith("error:")]


def _bottom_run(monkeypatch: pytest.MonkeyPatch, bad: list[str]) -> DecisionRun:
    p = make_profile(first_decision("turn", config=IX))
    seat = p.ctx.seat
    cards = [Entity(Kind.INTRIGUE, ref, None, seat) for ref in bad]
    monkeypatch.setattr(p, "bad_intrigue_cards_in_hand", lambda: cards)
    legal = (
        DomainAction(
            action_id="put_intrigue_on_bottom",
            actor=seat,
            arguments=(("card_id", "intrigue:a:0"),),
        ),
        DomainAction(
            action_id="put_intrigue_on_bottom",
            actor=seat,
            arguments=(("card_id", "intrigue:b:0"),),
        ),
        DomainAction(action_id="finish_intrigue_bottom", actor=seat),
    )
    return DecisionRun(p.ctx, p, legal, p.rng, Memory())


def test_sonic_snoopers_puts_the_bad_cards_then_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chosen = ix.intrigue_bottom_pick(_bottom_run(monkeypatch, ["intrigue:b:0"]))
    assert chosen is not None and dict(chosen.arguments) == {"card_id": "intrigue:b:0"}
    done = ix.intrigue_bottom_pick(_bottom_run(monkeypatch, []))
    assert done is not None and done.action_id == "finish_intrigue_bottom"
