"""The port of ``worm.canis.ai.WormAIProfile``: one instance per decision."""

from dune_imperium.agents.app_ai.profile.combat import CombatMixin
from dune_imperium.agents.app_ai.profile.core import ProfileCore
from dune_imperium.agents.app_ai.profile.economy import EconomyMixin
from dune_imperium.agents.app_ai.profile.immortality import ImmortalityMixin
from dune_imperium.agents.app_ai.profile.influence import InfluenceMixin
from dune_imperium.agents.app_ai.profile.tech import TechMixin


class Profile(
    EconomyMixin,
    InfluenceMixin,
    CombatMixin,
    ImmortalityMixin,
    TechMixin,
    ProfileCore,
):
    """``WormAIProfile``: valuation helpers for one seat at one decision."""


__all__ = ["Profile"]
