"""Influence, spies, contracts, battle icons, hooks, Shield Wall, agent recall.

Spec: spec/profile-influence-uprising.md.

Implements the matching methods declared in ``profile/core.py`` (same
names and signatures). Port each app method from the spec in the assets
checkout, replaying the binary's Add/Multiply order with ``Summer``.
"""

from dune_imperium.agents.app_ai.profile.core import ProfileCore


class InfluenceMixin(ProfileCore):
    """Overrides of the ProfileCore declarations for this area."""
