"""Rise of Ix's ``IsSetEnabled(RiseOfIx)`` profile terms (plan §13): the
influence block of ``GetGainInfluenceValue`` (profile-influence-uprising.md
(D)), gated on ``AppContext.ix``."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.agents.app_ai.context import AppContext
from dune_imperium.agents.app_ai.profile import Profile
from dune_imperium.agents.app_ai.testing import first_decision, make_profile
from dune_imperium.config import BaseGame

IX = RulesetConfig(base_game=BaseGame.IMPERIUM, rise_of_ix=True)


def _profile(monkeypatch: pytest.MonkeyPatch, ix: bool) -> Profile:
    p = make_profile(first_decision("turn", config=IX))
    monkeypatch.setattr(AppContext, "ix", property(lambda self: ix))
    monkeypatch.setattr(p, "is_climax", lambda: False)
    return p


def test_spacing_guild_gains_the_rise_of_ix_bonus_below_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # First turn: every influence is 0, so ``cur <= 1``.
    on = _profile(monkeypatch, True)
    with_ix = on.gain_influence_value("spacing_guild", 1, -1, False).sum
    off = _profile(monkeypatch, False)
    without = off.gain_influence_value("spacing_guild", 1, -1, False).sum
    assert with_ix == pytest.approx(without * on.C.SpacingGuildRiseOfIxBonus)
    # Another faction, and a ranked call, take no bonus.
    assert on.gain_influence_value("emperor", 1, -1, False).sum == pytest.approx(
        off.gain_influence_value("emperor", 1, -1, False).sum
    )
