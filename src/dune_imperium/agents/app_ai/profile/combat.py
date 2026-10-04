"""Conflict and combat — spec/profile-combat.md.

Implements the matching methods declared in ``profile/core.py`` (same
names and signatures). Port each app method from the spec in the assets
checkout, replaying the binary's Add/Multiply order with ``Summer``.
"""

from dune_imperium.agents.app_ai.profile.core import ProfileCore


class CombatMixin(ProfileCore):
    """Overrides of the ProfileCore declarations for this area."""
