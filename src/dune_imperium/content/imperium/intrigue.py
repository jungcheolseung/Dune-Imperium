"""The original game's Intrigue cards (stage P3).

docs/base-game-and-ix-plan.md 16: 34 kinds, 40 cards [DI p. 3]. Per D1
(plan 2.4) the printed effects come from the Steam app's screen pieces and
English text; the rules behind them are docs/rules/imperium-base.md, the
Plot / Combat / Endgame timings [DI pp. 13-14] those of Uprising.

While stage P3 is a trial (plan 16.7) these cards are not in the original
game's Intrigue deck and not in the observation: both come with stage P3a
(plan 16.1, 16.8 2). ``content.uprising.intrigue``'s ``INTRIGUE_CARDS_BY_ID``
and ``INTRIGUE_CARDS_BY_INSTANCE`` resolve them; code that lists Uprising's
own cards iterates ``INTRIGUE_CARDS`` instead.
"""

from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.intrigue import IntrigueCardEntry

IMPERIUM_INTRIGUE_SOURCES: Final = (
    SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (3, 13, 14)),
)


def intrigue_card(card_id: str, name: str) -> CardDefinition:
    """The identity of an original Intrigue card."""

    return CardDefinition(
        card_id=card_id, name=name, sources=IMPERIUM_INTRIGUE_SOURCES
    )


# Typed: ``content.uprising.intrigue`` reads it while both modules load.
IMPERIUM_INTRIGUE_CARDS: Final[tuple[IntrigueCardEntry, ...]] = ()
