"""App-style Arrakeen Scouts profile terms (docs/app-ai/scouts.md §2.1).

Line values, delayed payouts and the other Scouts prices the spec defines
as new profile methods.
"""

from dune_imperium.agents.app_ai.profile.core import ProfileCore


class ScoutsMixin(ProfileCore):
    """The app-style Arrakeen Scouts ``Profile`` methods."""
