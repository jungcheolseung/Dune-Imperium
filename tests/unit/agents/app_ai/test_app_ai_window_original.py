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

ORIGINAL = RulesetConfig(
    base_game=BaseGame.IMPERIUM, promo_cards=True, leader_draft=True
)
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
def fallbacks() -> Counter[str]:
    """The random answers of four app_ai seats over six original games."""

    counted: Counter[str] = Counter()
    logging.getLogger("dune_imperium.agents.app_ai.agent").setLevel(logging.ERROR)
    for seed in (31, 32, 33, 34, 35, 36):
        agents = tuple(AppAIAgent(seed=seed * 10 + seat) for seat in range(4))
        run_policy_game(ENGINE, ORIGINAL, seed, agents)
        for agent in agents:
            counted.update(agent.fallbacks)
    return counted


def test_the_reveal_window_maps_every_original_decision(
    fallbacks: Counter[str],
) -> None:
    """The original Reveal choices (Gun Thopter, Bene Gesserit Sister,
    Chani, Scout, Sardaukar Legion, Gurney Halleck, Opulence, Guild
    Ambassador, Duncan Loyal Blade), the Reserve and the acquire icons."""

    assert fallbacks["reveal"] == 0
    assert not [key for key in fallbacks if key.startswith("error:")]


def test_no_original_decision_falls_back(fallbacks: Counter[str]) -> None:
    """Every window on the original game (plan §12's goal): the Agent turn,
    Reveal, Conflict rewards, Intrigue choices, the victim's discard and the
    Masterstroke setup."""

    assert dict(fallbacks) == {}


def test_the_baron_picks_two_masterstroke_factions() -> None:
    """``masterstroke_setup``: the two Factions of one
    ``MasterstrokeAbility1`` answer, asked one at a time by our engine."""

    leaders = (
        "baron_vladimir_harkonnen",
        "paul_atreides",
        "duke_leto_atreides",
        "glossu_rabban",
    )
    engine = UprisingRulesEngine(leader_ids=leaders)
    config = RulesetConfig(base_game=BaseGame.IMPERIUM)
    agents = tuple(AppAIAgent(seed=70 + seat) for seat in range(4))
    result = run_policy_game(engine, config, 7, agents)
    baron = next(
        p for p in result.state.players if p.leader_id == "baron_vladimir_harkonnen"
    )
    assert len(set(baron.masterstroke_factions)) == 2
    assert not any(agent.fallbacks for agent in agents)
    assert agents[baron.player_id].mirrored["masterstroke_setup"] == 2


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
        for seed in (21, 22, 23, 24, 25, 26):
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


def test_original_signets_find_their_leaders_app_abilities(
    unmapped: Counter[str],
) -> None:
    """The eight original Leaders' Signet boxes and choices (Discipline,
    Manufacturing, Spice Hoard, Hidden Reservoir, Brutality, Prudent
    Diplomacy, Scheme, Manipulate) and Memnon's Connections."""

    left = [
        reason
        for reason in unmapped
        if reason.startswith("signet ")
        or reason
        in (
            "unknown action set_aside_leader_imperium",
            "unknown action choose_connections_influence",
        )
    ]
    assert left == []


def test_original_spaces_find_their_app_abilities(unmapped: Counter[str]) -> None:
    spaces = ("Maker space", "board ", "Desert Tactics trash")
    assert not [reason for reason in unmapped if reason.startswith(spaces)]


def test_the_agent_turn_window_maps_every_original_decision(
    unmapped: Counter[str],
) -> None:
    """Every card box and choice, Signet, space and payment of the original
    game: no Agent-turn decision falls back (plan §12.2's census)."""

    assert dict(unmapped) == {}


def test_second_ability_of_a_class_is_found_by_its_index() -> None:
    from dune_imperium.agents.app_ai.catalog import card_entity

    jessica = card_entity("imperium:jessica_of_arrakis:0", 0)
    first = agent_effects._find(jessica, "BeneGesseritDrawAbility")
    second = agent_effects._find(jessica, "BeneGesseritDrawAbility#2")
    assert first is not None and second is not None
    assert first[1] < second[1]
    assert agent_effects._find(jessica, "BeneGesseritDrawAbility#3") is None


def test_kwisatz_haderach_is_valued_with_the_agent_it_sends() -> None:
    """The turn window gives ``KwisatzHaderachAbility::Evaluate`` its two
    infos (spaces, then P's Agents: one still in P's area, the placed ones)
    and plays the answer's Agent as ``from_space``."""

    import random
    from dataclasses import replace

    from dune_imperium.agents.agent_turn_steps import placements_for_steps
    from dune_imperium.agents.app_ai.context import AppContext
    from dune_imperium.agents.app_ai.data.constants import TABLES
    from dune_imperium.agents.app_ai.profile import Profile
    from dune_imperium.agents.app_ai.testing import ENGINE as TEST_ENGINE
    from dune_imperium.agents.app_ai.testing import play_until, with_player
    from dune_imperium.agents.app_ai.windows import turn
    from dune_imperium.agents.app_ai.windows.run import DecisionRun, Memory
    from dune_imperium.core.decisions import PlayerDecision

    config = RulesetConfig(base_game=BaseGame.IMPERIUM)
    state = play_until(
        lambda s, owner: (
            s.decision_stack[-1].kind == "turn"
            and s.round_number >= 3
            and len(s.players[owner].agent_locations) >= 1
        ),
        config=config,
        seed=5,
    )
    decision = TEST_ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    seat = decision.owner
    kwisatz = next(
        c for c in (*state.imperium_deck, *state.imperium_row) if "kwisatz" in c
    )
    me = state.players[seat]
    state = replace(
        state,
        imperium_deck=tuple(c for c in state.imperium_deck if c != kwisatz),
        imperium_row=tuple(c for c in state.imperium_row if c != kwisatz),
    )
    state = with_player(
        state,
        seat,
        hand=(kwisatz, *me.hand[1:]),
        discard_pile=(*me.discard_pile, me.hand[0]),
    )
    shown = placements_for_steps(state, seat, TEST_ENGINE.legal_actions(state, seat))
    assert shown is not None
    placements = [
        a
        for a in shown[0]
        if a.action_id == "agent_turn" and dict(a.arguments)["card_id"] == kwisatz
    ]
    origins = {dict(a.arguments).get("from_space") for a in placements}
    assert None in origins and len(origins) >= 2
    view = TEST_ENGINE.observe(state, seat)
    ctx = AppContext(state, seat, view)
    run = DecisionRun(
        ctx,
        Profile(ctx, TABLES[2], random.Random(0)),
        tuple(shown[0]),
        random.Random(0),
        Memory(),
    )
    agents = turn._kwisatz_agents(run, placements)
    assert agents[0].ref == "player_area"
    assert {a.ref for a in agents[1:]} == origins - {None}
    value, action = turn._card_evaluate(run, kwisatz, placements)()
    assert action in placements
    assert value != 0.0
