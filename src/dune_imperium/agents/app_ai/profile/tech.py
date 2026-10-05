"""Rise of Ix tech — spec/rix-tech.md §3-§4: the ``WormAIProfile`` tech methods.

Tile values (``WormTechTilePlayable::AcquireValue``), ``TechTileToAcquire``,
``TechOptionsMod``, ``BuyTechValue`` and ``NegotiateTechValue``: the faithful
base of the app-style Bloodlines Tech Module (docs/app-ai-plan.md §11.3).
"""

from dune_imperium.agents.app_ai.profile.core import ProfileCore


class TechMixin(ProfileCore):
    """The Rise of Ix tech ``WormAIProfile`` methods."""
