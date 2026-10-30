"""Rise of Ix's four spaces (abilities/ix_board.py, agent_effects._ix_spaces;
plan §13): the space classes' terms, and the Agent-turn window finding an
app ability for every Ix space row in played original + Ix games."""

import logging
from collections import Counter
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai import AppAIAgent
from dune_imperium.agents.app_ai.abilities import ix_board as ib
from dune_imperium.agents.app_ai.abilities.base import UnportedAbility, abilities_of
from dune_imperium.agents.app_ai.abilities.generic import SpaceAbility
from dune_imperium.agents.app_ai.catalog import IX_SPACE_ARCHETYPES, space_entity
from dune_imperium.agents.app_ai.context import Board
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.agents.app_ai.windows import agent_effects
from dune_imperium.config import BaseGame
from dune_imperium.rules.engine import UprisingRulesEngine
from dune_imperium.simulation.runner import run_policy_game

IX = RulesetConfig(
    base_game=BaseGame.IMPERIUM, rise_of_ix=True, promo_cards=True, leader_draft=True
)
BOARD = Board.of(IX)

#: The Agent-turn rows ``_ix_spaces`` maps.
IX_ROWS = (
    "advance_board_freighter",
    "recall_board_freighter",
    "resolve_shipping_reward",
    "place_board_negotiator",
    "acquire_negotiation_tech",
    "commission_board_dreadnought",
    "acquire_board_tech",
)


@pytest.mark.parametrize("space_id", list(IX_SPACE_ARCHETYPES))
def test_every_ix_space_ability_is_ported(space_id: str) -> None:
    abilities = abilities_of(space_entity(space_id, BOARD))
    assert abilities
    assert not [a for a in abilities if isinstance(a, UnportedAbility)]


def test_the_dreadnought_space_adds_one_dreadnought_to_the_space_value() -> None:
    p = make_profile(first_decision("turn", config=IX))
    space = space_entity("dreadnought", BOARD)
    ported = ib.DreadnoughtSpaceAbility(space).value_for_player(p).sum
    generic = SpaceAbility(space).value_for_player(p).sum
    assert ported == pytest.approx(generic + p.dreadnought_value(1, False))


def test_tech_negotiation_persuasion_is_one_persuasion() -> None:
    p = make_profile(first_decision("turn", config=IX))
    ability = ib.TechNegotiationTriggeredAbility(
        space_entity("tech_negotiation", BOARD)
    )
    assert ability.value_for_player(p).sum == pytest.approx(p.persuasion_value(1))
    assert ability.should_exhaust is False


@pytest.fixture(scope="module")
def unmapped() -> Counter[str]:
    reasons: Counter[str] = Counter()
    collect = agent_effects._collect

    def spy(t: Any) -> None:
        collect(t)
        reasons.update(t.unmapped)

    agent_effects._collect = spy
    previous = logging.getLogger("dune_imperium.agents.app_ai.agent").level
    try:
        for seed in (8000, 8001, 8002):
            agents = tuple(AppAIAgent(seed=seed * 10 + s) for s in range(4))
            run_policy_game(UprisingRulesEngine(), IX, seed, agents)
    finally:
        agent_effects._collect = collect
        logging.getLogger("dune_imperium.agents.app_ai.agent").setLevel(previous)
    return reasons


def test_the_turn_window_maps_every_ix_space_row(unmapped: Counter[str]) -> None:
    left = {r: n for r, n in unmapped.items() if any(row in r for row in IX_ROWS)}
    assert left == {}
    assert not [
        r for r in unmapped if r.startswith(("tech_negotiation", "dreadnought "))
    ]


def _control_answer(
    controllers: dict[str, int | None], vp: int = 0
) -> tuple[str, float]:
    from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo

    state = first_decision("turn", config=IX)
    p = make_profile(state)
    entities = tuple(space_entity(s, BOARD) for s in controllers)
    ability = ib.DreadnoughtControlAbility(entities[0], controllers)
    p.ctx.vp = lambda player: vp  # type: ignore[method-assign]
    answer = ability.evaluate(p, Request(infos=(TargetInfo(entities=entities),)))
    assert answer.response is not None and answer.response[0] == (ib.DREADNOUGHT_PLACE,)
    return str(answer.response[1][0]), answer.value


def test_dreadnought_control_prefers_an_open_imperial_basin() -> None:
    seat = make_profile(first_decision("turn", config=IX)).ctx.seat
    ref, value = _control_answer(
        {"arrakeen": None, "carthag": seat, "imperial_basin": None}
    )
    assert (ref, value) == ("imperial_basin", 3.0)


def test_dreadnought_control_blocks_a_leader_with_more_vp_than_three() -> None:
    seat = make_profile(first_decision("turn", config=IX)).ctx.seat
    other = (seat + 1) % 4
    ref, value = _control_answer(
        {"arrakeen": other, "carthag": None, "imperial_basin": None}, vp=5
    )
    assert (ref, value) == ("arrakeen", 5.0)


def test_tech_acquisition_spends_negotiators_first() -> None:
    from dune_imperium.agents.app_ai.windows.bloodlines import _tile_action
    from dune_imperium.core.actions import DomainAction

    plain = DomainAction(
        action_id="acquire_tech", actor=0, arguments=(("tech_id", "artillery"),)
    )
    paid = DomainAction(
        action_id="acquire_tech",
        actor=0,
        arguments=(("negotiators", 1), ("tech_id", "artillery")),
    )
    assert _tile_action(None, [plain, paid], "artillery") is paid  # type: ignore[arg-type]
