"""The decision windows on the original game (docs/app-ai-plan.md §12).

Each slice of the original port maps its cards, spaces and Leaders into the
windows; these tests play a few original games with four app_ai seats and
check that the Agent-turn window found an app ability for every mapped item
(``agent_effects._collect``'s ``unmapped`` reasons, the census of plan
§12.2).
"""

import logging
from collections import Counter
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.windows import agent_effects
from dune_imperium.config import BaseGame
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM, promo_cards=True)
ENGINE = UprisingRulesEngine()

#: Cards whose Agent box only needs app abilities ported before the original
#: stage: generic boxes, draws, Piter's Intrigue, the trash boxes.
MAPPED_CARDS = (
    "arrakis_recruiter",
    "stilgar",
    "opulence",
    "worm_riders",
    "sardaukar_legion",
    "crysknife_card",
    "duncan_loyal_blade",
    "power_play",
    "thumper",
    "dr_yueh",
    "space_travel",
    "bene_gesserit_initiate",
    "thufir_hawat",
    "kwisatz_haderach",
    "lady_jessica_card",
    "piter_de_vries_card",
    "gurney_halleck_card",
    "foldspace_card",
    "jessica_of_arrakis",
    "guild_administrator",
    "fedaykin_death_commando",
    "sietch_reverend_mother",
    "gene_manipulation",
)


@pytest.fixture(scope="module")
def unmapped() -> Counter[str]:
    """The ``unmapped`` reasons of the Agent-turn window over four games."""

    reasons: Counter[str] = Counter()
    collect = agent_effects._collect

    def spy(t: Any) -> None:
        collect(t)
        reasons.update(t.unmapped)

    agent_effects._collect = spy
    logging.getLogger("dune_imperium.agents.app_ai.agent").setLevel(logging.ERROR)
    try:
        for seed in (21, 22, 23, 24):
            agents = tuple(AppAIAgent(seed=seed * 10 + seat) for seat in range(4))
            run_policy_game(ENGINE, ORIGINAL, seed, agents)
    finally:
        agent_effects._collect = collect
    return reasons


def test_mapped_card_boxes_find_their_app_abilities(unmapped: Counter[str]) -> None:
    left = {
        reason: n
        for reason, n in unmapped.items()
        if reason.split(" ", 1)[0] in MAPPED_CARDS
    }
    assert left == {}


def test_original_spaces_find_their_app_abilities(unmapped: Counter[str]) -> None:
    spaces = ("Maker space", "board ", "Desert Tactics trash")
    assert not [reason for reason in unmapped if reason.startswith(spaces)]


def test_second_ability_of_a_class_is_found_by_its_index() -> None:
    from dune_imperium.agents.app_ai.catalog import card_entity

    jessica = card_entity("imperium:jessica_of_arrakis:0", 0)
    first = agent_effects._find(jessica, "BeneGesseritDrawAbility")
    second = agent_effects._find(jessica, "BeneGesseritDrawAbility#2")
    assert first is not None and second is not None
    assert first[1] < second[1]
    assert agent_effects._find(jessica, "BeneGesseritDrawAbility#3") is None
