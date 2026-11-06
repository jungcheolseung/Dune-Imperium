"""Rise of Ix's Conflict ports (abilities/ix_conflicts.py, plan §13): each
place's terms against stubbed prices, Trade Monopoly 3rd's "-OR-", and the
catalog's reward entities."""

from collections.abc import Callable
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import ix_conflicts as ic
from dune_imperium.agents.app_ai.abilities.base import (
    Request,
    UnportedAbility,
    abilities_of,
)
from dune_imperium.agents.app_ai.abilities.generic import ConflictAbility
from dune_imperium.agents.app_ai.catalog import conflict_entity
from dune_imperium.agents.app_ai.entities import Entity, Kind
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.config import BaseGame

IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)
OWNER = Entity(Kind.CONFLICT, "trade_monopoly", None)


def _profile(monkeypatch: pytest.MonkeyPatch, **prices: float) -> Profile:
    p = make_profile(first_decision("turn", config=IX))
    stubs: dict[str, Callable[..., Any]] = {
        "troop_value": lambda n, include=False: 0.9 * n,
        "spice_value": lambda n: 0.5 * n,
        "solari_value": lambda n: 0.25 * n,
        "water_value": lambda n: prices.get("water", 1.0) * n,
        "intrigue_value": lambda: prices.get("intrigue", 2.0),
        "freighter_value": lambda: 4.2,
        "freighter_selections": lambda space=-1: (1, 0, "Level 3"),
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(p, name, stub)
    return p


@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (ic.SkirmishEFirstAbility, 0.9 + 4.2),
        (ic.SkirmishESecondAbility, 1.0),
        (ic.SkirmishEThirdAbility, 0.5),
        (ic.SkirmishFFirstAbility, 0.5 + 4.2),
        (ic.SkirmishFSecondAbility, 0.75),
        (ic.SkirmishFThirdAbility, 0.5),
        (ic.TradeMonopolyFirstAbility, 0.9 + 8.4),
        (ic.TradeMonopolySecondAbility, 1.0 + 2.0),
        (ic.TradeMonopolyThirdAbility, 2.0),
    ],
)
def test_each_place_values_its_printed_rewards(
    monkeypatch: pytest.MonkeyPatch, cls: type[ConflictAbility], expected: float
) -> None:
    p = _profile(monkeypatch)
    assert cls(OWNER).value_for_player(p).sum == pytest.approx(expected)


def test_the_first_places_with_a_freighter_answer_item1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = _profile(monkeypatch)
    for cls in (ic.SkirmishEFirstAbility, ic.SkirmishFFirstAbility):
        answer = cls(OWNER).evaluate(p, Request())
        assert answer.response == ((1,),)
        assert answer.value == pytest.approx(4.2)


@pytest.mark.parametrize(
    ("water", "intrigue", "option"), [(1.0, 2.0, 0), (3.0, 2.0, 1), (2.0, 2.0, 0)]
)
def test_trade_monopoly_third_takes_the_strictly_better_option(
    monkeypatch: pytest.MonkeyPatch, water: float, intrigue: float, option: int
) -> None:
    p = _profile(monkeypatch, water=water, intrigue=intrigue)
    answer = ic.TradeMonopolyThirdAbility(OWNER).evaluate(p, Request())
    assert answer.response == ((option,),)


@pytest.mark.parametrize("conflict_id", ["skirmish_e", "skirmish_f", "trade_monopoly"])
def test_each_ix_conflict_lists_its_three_ported_places(conflict_id: str) -> None:
    abilities = abilities_of(conflict_entity(conflict_id, False))
    assert len(abilities) == 3
    assert not any(isinstance(a, UnportedAbility) for a in abilities)
    assert sorted(getattr(a, "place", 0) for a in abilities) == [1, 2, 3]
