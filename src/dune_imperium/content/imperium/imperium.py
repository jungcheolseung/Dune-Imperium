"""The original game's Imperium cards and its three promos (stage P3).

docs/base-game-and-ix-plan.md 16: 43 Imperium kinds, 67 cards [DI p. 3], and
the promos Duncan, Loyal Blade, Jessica of Arrakis and Thumper behind
``promo_cards`` (plan 9 8). Per D1 (plan 2.4) every value comes from the
Steam app: the attribute table for cost, copies, Factions, Agent icons and
the printed Reveal values, the card's screen pieces and English text for its
boxes; the rules behind them are docs/rules/imperium-base.md.

A name the original prints like another set's card keeps that card's id;
one printed otherwise takes the ``imperium_`` prefix (plan 4.2 7, 16.2).
Their ability records sit in the same tables as Uprising's
(``agent_abilities``, ``reveal_abilities``, ...).

While stage P3 is a trial (plan 16.7) these cards are not in the original
game's deck (``rulesets._imperium_content``) and not in the observation:
both come with stage P3a's single observation change (plan 16.1, 16.8 2).
``content.uprising.imperium.IMPERIUM_CARDS_BY_ID`` resolves them; code that
lists Uprising's own cards iterates ``IMPERIUM_CARDS`` instead.
"""

from typing import Final

from dune_imperium.content.schema import CardDefinition, SourceDocument, SourceRef
from dune_imperium.content.uprising.imperium import ImperiumCardEntry

# The rulebook lists the deck [DI p. 3]; the printed values are the app's
# (plan 2.4, D1).
IMPERIUM_SOURCES: Final = (SourceRef(SourceDocument.IMPERIUM_RULEBOOK, (3,)),)


def imperium_card(card_id: str, name: str) -> CardDefinition:
    """The identity of an original Imperium card (no Dune Cards Hub URL:
    the original's faces are not read, D1)."""

    return CardDefinition(card_id=card_id, name=name, sources=IMPERIUM_SOURCES)


# Typed: ``content.uprising.imperium`` reads it while both modules load.
IMPERIUM_BASE_CARDS: Final[tuple[ImperiumCardEntry, ...]] = ()
