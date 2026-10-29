"""Rise of Ix dreadnoughts in ``GetUnitsToDeploy`` and ``DeployValue``
(profile/combat.py, plan §13): the strongest units first, the Baron's
Masterstroke swap, Diversion, and the dreadnought terms."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import (
    ENGINE,
    first_decision,
    make_profile,
    with_player,
)
from dune_imperium.config import BaseGame
from dune_imperium.core.decisions import PlayerDecision

IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)


def _profile(monkeypatch: pytest.MonkeyPatch, **changes: object) -> Profile:
    state = first_decision("turn", config=IX)
    decision = ENGINE.current_decision(state)
    assert isinstance(decision, PlayerDecision)
    p = make_profile(with_player(state, decision.owner, **changes), decision.owner)
    monkeypatch.setattr(p, "is_climax", lambda: True)  # "Climax": every unit
    monkeypatch.setattr(p, "_baron_holds_secret_factions", lambda: False)
    monkeypatch.setattr(p, "_holds_intrigue", lambda card: False)
    return p


def test_without_dreadnoughts_the_split_is_units_to_deploy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = _profile(monkeypatch)
    assert p.units_to_deploy_split(3, 0, 2) == (0, p.units_to_deploy(3, 2))


def test_dreadnoughts_go_first_up_to_max(monkeypatch: pytest.MonkeyPatch) -> None:
    p = _profile(monkeypatch)
    assert p.units_to_deploy_split(3, 2, 3) == (2, 1)
    assert p.units_to_deploy_split(3, 2, 1) == (1, 0)


def test_the_baron_swaps_a_dreadnought_for_a_troop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = _profile(monkeypatch, units_deployed_turn=2)
    monkeypatch.setattr(p, "_baron_holds_secret_factions", lambda: True)
    # [dreadnought, troop] chosen: 1 troop + 2 exhausted = 3 -> the troop
    # left over replaces the dreadnought.
    assert p.units_to_deploy_split(3, 1, 2) == (0, 2)
    # No dreadnought chosen: one more troop while under max.
    assert p.units_to_deploy_split(3, 0, 2) == (0, 2)


def test_diversion_adds_the_next_unit_in_strength_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = _profile(monkeypatch, units_deployed_turn=2)
    monkeypatch.setattr(p, "_holds_intrigue", lambda card: card == "diversion")
    monkeypatch.setattr(p, "is_climax", lambda: False)
    monkeypatch.setattr(p, "conflict_posture_bounds", lambda: (-1e9, 1e9))
    monkeypatch.setattr(p, "potential_strength", lambda n: _Sum(0))
    monkeypatch.setattr(p, "est_strength", lambda: _Sum(0))
    monkeypatch.setattr(p, "est_opponent_strength", lambda seat: _Sum(0))
    monkeypatch.setattr(p, "current_conflict_interest", lambda: _Sum(0.0))
    monkeypatch.setattr(p, "_conflict_rewards_allowed", lambda: 3)
    # "Mid Deploy 1" takes the dreadnought; 2 exhausted + 1 chosen = 3 under
    # max: the next unit in strength order (a troop) goes in too.
    assert p.units_to_deploy_split(3, 1, 2) == (1, 1)
    # Without Diversion only the one unit.
    monkeypatch.setattr(p, "_holds_intrigue", lambda card: False)
    assert p.units_to_deploy_split(3, 1, 2) == (1, 0)


class _Sum:
    def __init__(self, value: float) -> None:
        self.sum = value


def test_deploy_value_counts_garrisoned_dreadnoughts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dune_imperium.agents.app_ai.catalog import space_entity
    from dune_imperium.agents.app_ai.context import Board

    space = space_entity("arrakeen", Board.of(IX))
    none = _profile(monkeypatch, dreadnoughts_garrison=0, dreadnoughts_supply=2)
    two = _profile(monkeypatch, dreadnoughts_garrison=2, dreadnoughts_supply=0)
    assert two.deploy_value(space) - none.deploy_value(space) == pytest.approx(3.0)


@pytest.mark.parametrize(
    ("leader_id", "expected"),
    [("prince_rhombur_vernius", (1, 0)), ("archduke_armand_ecaz", (1, 1))],
)
def test_rhombur_dreadnoughts_count_four_in_the_take_while(
    monkeypatch: pytest.MonkeyPatch, leader_id: str, expected: tuple[int, int]
) -> None:
    """``HeavyLasgunCannonsAbility`` sets Rhombur's dreadnoughts' ``Strength``
    to 4 at ``GameStarted``: "Mid can win" asks 3 - 0 + 1 = 4, which his one
    dreadnought meets alone; anyone else's (3) takes a troop too."""

    p = _profile(monkeypatch, leader_id=leader_id)
    first = p.ctx.opponents[0].player_id
    monkeypatch.setattr(p, "is_climax", lambda: False)
    monkeypatch.setattr(p, "conflict_posture_bounds", lambda: (-1e9, 1e9))
    monkeypatch.setattr(p, "current_conflict_interest", lambda: _Sum(0.0))
    monkeypatch.setattr(p, "est_strength", lambda: _Sum(0))
    monkeypatch.setattr(p, "potential_strength", lambda n: _Sum(10))
    monkeypatch.setattr(
        p, "est_opponent_strength", lambda seat: _Sum(3 if seat == first else 0)
    )
    monkeypatch.setattr(p, "_conflict_rewards_allowed", lambda: 3)
    assert p.units_to_deploy_split(3, 1, 4) == expected
