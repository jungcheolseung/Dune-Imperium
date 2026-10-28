"""Rise of Ix's three new Conflict cards (stage P4a; docs/rules/rise-of-ix.md 12).

docs/base-game-and-ix-plan.md 17.1 and 17.7: Rise of Ix has four Conflict
cards, I 2, II 1 and III 1 [Rise of Ix p. 2] (docs/rules/rise-of-ix.md 2),
and its Conflict deck takes them with the original game's [Rise of Ix p. 3]
(docs/rules/rise-of-ix.md 3). Economic Supremacy, the one Conflict III, is
Uprising's Epic card already (``content.uprising.conflicts``, OQ-094) and is
not defined again; the three here are the two Skirmishes (I) and Trade
Monopoly (II). Like the original game's, they print no battle icon and no
Shield Wall.

Ids (docs/rules/rise-of-ix.md 12): the original game's Skirmishes are
``skirmish_a`` to ``skirmish_d`` (``content.imperium.conflicts``), so the
Ix Skirmishes take the app's own letters, ``skirmish_e`` and ``skirmish_f``
(``ConflictArchetypes.RiseOfIx.SkirmishE`` and ``SkirmishF``); Trade
Monopoly is ``trade_monopoly``. No other Conflict card has any of those ids.

These are stage P4a identity entries: name and tier only, ``reward_rows``
``None`` ("not transcribed", as ``ConflictDefinition`` documents). They are
in no pool: the Conflict deck takes only the transcribed cards, and the
observation lists them from v39 (plan 17.1, 17.4); neither is done yet, and
setup still refuses Rise of Ix. ``content.uprising.conflicts``'s
``CONFLICTS_BY_ID`` resolves them next to the original game's cards; code
that lists Uprising's or the original game's own Conflicts iterates
``CONFLICTS`` or ``IMPERIUM_CONFLICTS``.
"""

from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.conflicts import ConflictDefinition
from dune_imperium.content.uprising.types import ConflictTier

# The component table and the Conflict deck's setup [Rise of Ix pp. 2-3]; the
# printed values are the app's (plan 2.4, D1).
IX_CONFLICT_SOURCES: Final = (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2, 3)),)


def _conflict(content_id: str, name: str, tier: ConflictTier) -> ConflictDefinition:
    return ConflictDefinition(
        card=CardDefinition(content_id, name, IX_CONFLICT_SOURCES),
        tier=tier,
    )


# Typed: ``content.uprising.conflicts`` reads it while both modules load.
IX_CONFLICTS: Final[tuple[ConflictDefinition, ...]] = (
    _conflict("skirmish_e", "Skirmish", ConflictTier.ONE),
    _conflict("skirmish_f", "Skirmish", ConflictTier.ONE),
    _conflict("trade_monopoly", "Trade Monopoly", ConflictTier.TWO),
)
