"""Rise of Ix's six Leaders (stage P4a; docs/rules/rise-of-ix.md 10).

docs/base-game-and-ix-plan.md 17.1 and 17.7: six Leaders [Rise of Ix p. 2]
(docs/rules/rise-of-ix.md 2), each with the original game's one-ability
card shape: the left ability and the Signet Ring. Names come from the Steam
app's attribute table (``LeaderArchetypes.RiseOfIx.*``, the app title) and
the ability names from the app's ability classes (``…RiseOfIx.CoordinationAbility``
and the like), as ``content.imperium.leaders`` did for the original game; the
rules behind them are docs/rules/rise-of-ix.md 10.

These are stage P4a identity entries: a name and the two ability names. The
setup deviations (Yuna's ``starting_water``, Hundro's and Tessia's setup
steps) and the abilities themselves are not wired yet (stage P4e).
``rulesets.IMPERIUM_LEADER_IDS`` keeps the original game's eight; with
``rise_of_ix`` ``content_for`` offers them after those eight [Rise of Ix p. 3]
as each is wired (``rulesets.IX_LEADER_IDS_OFFERED``, none until stage P4e),
so the six are defined but not offered yet; setup takes Rise of Ix on the
original game since stage P4c-5.
``content.uprising.leaders``'s ``LEADERS_BY_ID`` resolves them next to the
original game's Leaders; code that lists Uprising's Leaders iterates
``LEADERS``, and the observation lists them from v39 (plan 17.1, 17.4).
"""

from typing import Final

from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.leaders import LeaderDefinition

# The component table lists the six Leaders [Rise of Ix p. 2]; the printed
# values are the app's (plan 2.4, D1).
_SOURCES: Final = (
    SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2,)),
    SourceRef(SourceDocument.CARD_FACE, (1,)),
)
# The card data come from the app (plan 2.4, D1); Dune Cards Hub's catalog
# is the reference picture.
_CATALOG: Final = "https://dunecardshub.com/"


def _leader(leader_id: str, name: str, ability: str, signet: str) -> LeaderDefinition:
    return LeaderDefinition(
        leader_id,
        name,
        _CATALOG,
        ability_name=ability,
        signet_name=signet,
        sources=_SOURCES,
    )


# Typed: ``content.uprising.leaders`` reads it while both modules load. An id
# is the snake case of the app's title without quotes; none repeats an id of
# Uprising's, Bloodlines' or the original game's Leaders (plan 17.2).
IX_LEADERS: Final[tuple[LeaderDefinition, ...]] = (
    _leader(
        "archduke_armand_ecaz", "Archduke Armand Ecaz", "Coordination", "Conscript"
    ),
    _leader("ilesa_ecaz", "Ilesa Ecaz", "One Step Ahead", "Guild Contacts"),
    _leader(
        "prince_rhombur_vernius",
        "Prince Rhombur Vernius",
        "Heavy Lasgun Cannons",
        "Ixian Technology",
    ),
    _leader(
        "princess_yuna_moritani",
        # The app's title keeps the quotation marks, so the id drops them.
        '"Princess" Yuna Moritani',
        "Smuggling Operation",
        "Final Delivery",
    ),
    _leader("tessia_vernius", "Tessia Vernius", "Careful Observation", "Duplicity"),
    _leader(
        "viscount_hundro_moritani",
        "Viscount Hundro Moritani",
        "Intelligence",
        "Couriers",
    ),
)
