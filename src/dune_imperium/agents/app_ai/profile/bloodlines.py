"""App-style Bloodlines profile terms (docs/app-ai/bloodlines-systems.md §1).

Commander and Skill prices, forced-loss picks and the other Bloodlines
helpers the spec defines as new profile methods.
"""

from dune_imperium.agents.app_ai.profile.core import ProfileCore


class BloodlinesMixin(ProfileCore):
    """The app-style Bloodlines ``Profile`` methods."""
