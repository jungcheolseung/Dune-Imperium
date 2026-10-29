"""The profile on the original board: ``IsSetEnabled(Uprising = 4)`` false.

The app's profile tests the Uprising set in a few places (spec
``profile-influence-uprising.md`` §1.1 (C)/(E), ``board.md`` §1.3,
``profile-economy.md`` §1.2, §3.1, §7.1); an original game takes the other
path. Each test reads the reasons of one value (``Summer.tracing``) on an
original state and on the same Uprising one.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.abilities import generic as g
from dune_imperium.agents.app_ai.catalog import space_entity
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.summer import Summer
from dune_imperium.agents.app_ai.testing import (
    first_decision,
    make_profile,
    with_player,
)
from dune_imperium.config import BaseGame
from dune_imperium.core.decisions import PlayerDecision
from dune_imperium.core.player import Influence
from dune_imperium.core.state import GameState
from dune_imperium.rules.engine import UprisingRulesEngine

ORIGINAL = RulesetConfig(base_game=BaseGame.IMPERIUM)
ENGINE = UprisingRulesEngine()


@pytest.fixture(autouse=True)
def _tracing(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(Summer, "tracing", True)
    yield


def _seat(state: GameState) -> int:
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    return decision.owner


@pytest.fixture(scope="module")
def original() -> GameState:
    return first_decision("turn", config=ORIGINAL)


@pytest.fixture(scope="module")
def uprising() -> GameState:
    return first_decision("turn")


def _profile(
    monkeypatch: pytest.MonkeyPatch, state: GameState, **stubs: Callable[..., Any]
) -> Profile:
    p = make_profile(state, _seat(state))
    defaults: dict[str, Callable[..., Any]] = {
        "game_arc": lambda: 0,
        "is_climax": lambda: False,
        "resource_value": lambda attr, n, include=False: 0.5 * n,
        "intrigue_value": lambda: 2.0,
        "spy_value": lambda: Summer(1.66),
    }
    defaults.update(stubs)
    for name, fn in defaults.items():
        monkeypatch.setattr(p, name, fn)
    return p


def _reasons(summer: Summer) -> dict[str, float]:
    assert summer.reasons is not None
    return {reason: amount for _, reason, amount in summer.reasons}


def test_the_uprising_set_is_off_on_the_original_board(
    original: GameState, uprising: GameState
) -> None:
    assert not make_profile(original, _seat(original)).ctx.uprising
    assert make_profile(uprising, _seat(uprising)).ctx.uprising


def test_emperor_track_bonus_is_three_troops_off_uprising(
    monkeypatch: pytest.MonkeyPatch, original: GameState, uprising: GameState
) -> None:
    """``GetGainInfluenceValue`` (C) @0x490ad61: the Emperor 3 -> 4 bonus is
    the Spy in Uprising, the literal 3.0 "Resource Bonus (Troops)" off it."""

    for state, uprising_on in ((original, False), (uprising, True)):
        seat = _seat(state)
        at_three = with_player(state, seat, influence=Influence(emperor=3))
        reasons = _reasons(
            _profile(monkeypatch, at_three).gain_influence_value("emperor", 1)
        )
        if uprising_on:
            assert reasons.get("Resource Bonus(Spy)") == pytest.approx(1.66)
            assert "Resource Bonus (Troops)" not in reasons
        else:
            assert reasons.get("Resource Bonus (Troops)") == 3.0
            assert "Resource Bonus(Spy)" not in reasons


def test_space_value_skips_the_uprising_block_off_uprising(
    monkeypatch: pytest.MonkeyPatch, original: GameState
) -> None:
    """``SpaceAbility::ValueForPlayer`` @0x4bafaf0: ``S is WormSpace &&
    IsSetEnabled(4)`` gates the contract, Spy-infiltrate, Gather
    Intelligence and Reverend Mother terms; an occupied original space
    carries no "Recall spy to infiltrate" term."""

    seat = _seat(original)
    other = (seat + 1) % 4
    player = original.players[other]
    occupied = with_player(
        original,
        other,
        agents_available=player.agents_available - 1,
        agent_locations=(*player.agent_locations, "arrakeen"),
    )
    p = _profile(monkeypatch, occupied)
    assert p.ctx.space_occupants("arrakeen")
    space = space_entity("arrakeen", p.ctx.board)
    reasons = _reasons(g.SpaceAbility(space).value_for_player(p))
    assert not [r for r in reasons if "infiltrate" in r or "Gather" in r]


def test_the_baron_deploys_a_fourth_unit_for_his_masterstroke(
    monkeypatch: pytest.MonkeyPatch, original: GameState
) -> None:
    """``GetUnitsToDeploy`` @0x49167cc: with his secret Factions held, when
    this turn's deployed units and the troops chosen make exactly 3, one
    more troop goes in (while under ``max``)."""

    seat = _seat(original)
    stubs: dict[str, Callable[..., Any]] = {
        "is_climax": lambda: False,
        "conflict_posture_bounds": lambda: (1.0, 10.0),
        "current_conflict_interest": lambda: Summer(5.0),
        "est_strength": lambda: Summer(0.0),
        "potential_strength": lambda n: Summer(5.0),
        "est_opponent_strength": lambda s: Summer(
            {0: 10.0, 1: 2.0, 2: 0.0, 3: 0.0}[(s - seat - 1) % 4]
        ),
    }

    def deploy(**changes: object) -> int:
        state = with_player(original, seat, **changes)
        p = _profile(monkeypatch, state, **stubs)
        return p.units_to_deploy(4, 4)

    # "Mid can get 2nd": 3 strength requested, two troops.
    assert deploy() == 2
    baron = {
        "leader_id": "baron_vladimir_harkonnen",
        "masterstroke_factions": ("emperor", "fremen"),
    }
    assert deploy(**baron) == 2
    assert deploy(**baron, units_deployed_turn=1) == 3
    assert deploy(**baron, units_deployed_turn=1, masterstroke_revealed=True) == 2
