"""Setup identities for the 44-card Uprising Intrigue deck."""

from typing import Final

from dune_imperium.content.schema import (
    CardDefinition,
    DeckCardEntry,
    SourceDocument,
    SourceRef,
)

BASE_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4)),)
CHOAM_SOURCES: Final = (SourceRef(SourceDocument.MAIN_RULEBOOK, (3, 4, 16)),)


def _entry(
    catalog_id: int,
    slug: str,
    name: str,
    *,
    copies: int = 1,
    choam_only: bool = False,
) -> DeckCardEntry:
    return DeckCardEntry(
        card=CardDefinition(
            card_id=slug.replace("-", "_"),
            name=name,
            sources=CHOAM_SOURCES if choam_only else BASE_SOURCES,
            catalog_url=f"https://dunecardshub.com/cards/{catalog_id}/uprising-{slug}",
        ),
        copies=copies,
        choam_only=choam_only,
    )


INTRIGUE_CARDS: Final = (
    _entry(448, "backed-by-choam", "Backed by CHOAM", choam_only=True),
    _entry(139, "buy-access", "Buy Access"),
    _entry(138, "call-to-arms", "Call to Arms"),
    _entry(135, "change-allegiances", "Change Allegiances"),
    _entry(450, "choam-profits", "CHOAM Profits", choam_only=True),
    _entry(147, "contingency-plan", "Contingency Plan", copies=3),
    _entry(129, "councilor-s-ambition", "Councilor's Ambition"),
    _entry(159, "crysknife", "Crysknife"),
    _entry(133, "cunning", "Cunning"),
    _entry(132, "depart-for-arrakis", "Depart For Arrakis"),
    _entry(157, "desert-mouse", "Desert Mouse"),
    _entry(131, "detonation", "Detonation", copies=2),
    _entry(151, "devour", "Devour"),
    _entry(144, "distraction", "Distraction", copies=2),
    _entry(149, "find-weakness", "Find Weakness"),
    _entry(146, "go-to-ground", "Go To Ground"),
    _entry(140, "imperium-politics", "Imperium Politics"),
    _entry(152, "impress", "Impress"),
    _entry(148, "inspire-awe", "Inspire Awe"),
    _entry(142, "intelligence-report", "Intelligence Report"),
    _entry(447, "leverage", "Leverage", choam_only=True),
    _entry(143, "manipulate", "Manipulate"),
    _entry(145, "market-opportunity", "Market Opportunity"),
    _entry(128, "mercenaries", "Mercenaries"),
    _entry(134, "opportunism", "Opportunism"),
    _entry(158, "ornithopter", "Ornithopter"),
    _entry(156, "questionable-methods", "Questionable Methods"),
    _entry(449, "reach-agreement", "Reach Agreement", choam_only=True),
    _entry(161, "secure-spice-trade", "Secure Spice Trade"),
    _entry(141, "shaddam-s-favor", "Shaddam's Favor"),
    _entry(160, "shadow-alliance", "Shadow Alliance"),
    _entry(127, "sietch-ritual", "Sietch Ritual"),
    _entry(136, "special-mission", "Special Mission", copies=2),
    _entry(150, "spice-is-power", "Spice is Power"),
    _entry(153, "spring-the-trap", "Spring The Trap"),
    _entry(130, "strategic-stockpiling", "Strategic Stockpiling"),
    _entry(155, "tactical-option", "Tactical Option"),
    _entry(137, "unexpected-allies", "Unexpected Allies"),
    _entry(154, "weirding-combat", "Weirding Combat"),
)


def intrigue_cards_for_choam(choam_module: bool) -> tuple[DeckCardEntry, ...]:
    """Return physical card entries included by the selected setup."""

    return tuple(
        entry for entry in INTRIGUE_CARDS if choam_module or not entry.choam_only
    )


def intrigue_deck_instance_ids(choam_module: bool) -> tuple[str, ...]:
    """Return stable IDs for every physical Intrigue card copy."""

    return tuple(
        f"intrigue:{entry.card.card_id}:{copy}"
        for entry in intrigue_cards_for_choam(choam_module)
        for copy in range(entry.copies)
    )
