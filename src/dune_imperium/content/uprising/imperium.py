"""Setup identities for the 69-card Uprising Imperium deck."""

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


IMPERIUM_CARDS: Final = (
    _entry(30, "bene-gesserit-operative", "Bene Gesserit Operative", copies=2),
    _entry(45, "branching-path", "Branching Path"),
    _entry(42, "calculus-of-power", "Calculus of Power", copies=2),
    _entry(61, "captured-mentat", "Captured Mentat"),
    _entry(181, "cargo-runner", "Cargo Runner", choam_only=True),
    _entry(67, "chani-clever-tactician", "Chani, Clever Tactician"),
    _entry(69, "corrinth-city", "Corrinth City"),
    _entry(35, "covert-operation", "Covert Operation"),
    _entry(44, "dangerous-rhetoric", "Dangerous Rhetoric"),
    _entry(182, "delivery-agreement", "Delivery Agreement", choam_only=True),
    _entry(71, "desert-power", "Desert Power"),
    _entry(27, "desert-survival", "Desert Survival", copies=2),
    _entry(37, "double-agent", "Double Agent", copies=2),
    _entry(46, "ecological-testing-station", "Ecological Testing Station"),
    _entry(23, "fedaykin-stilltent", "Fedaykin Stilltent"),
    _entry(38, "guild-envoy", "Guild Envoy"),
    _entry(43, "guild-spy", "Guild Spy"),
    _entry(21, "hidden-missive", "Hidden Missive"),
    _entry(24, "imperial-spymaster", "Imperial Spymaster"),
    _entry(64, "in-high-places", "In High Places"),
    _entry(184, "interstellar-trade", "Interstellar Trade", choam_only=True),
    _entry(68, "junction-headquarters", "Junction Headquarters"),
    _entry(63, "leadership", "Leadership"),
    _entry(74, "long-live-the-fighters", "Long Live the Fighters"),
    _entry(19, "maker-keeper", "Maker Keeper", copies=2),
    _entry(32, "maula-pistol", "Maula Pistol", copies=2),
    _entry(34, "northern-watermaster", "Northern Watermaster"),
    _entry(75, "overthrow", "Overthrow"),
    _entry(49, "paracompass", "Paracompass"),
    _entry(73, "price-is-no-object", "Price is No Object"),
    _entry(183, "priority-contracts", "Priority Contracts", choam_only=True),
    _entry(55, "public-spectacle", "Public Spectacle", copies=2),
    _entry(40, "rebel-supplier", "Rebel Supplier", copies=2),
    _entry(20, "reliable-informant", "Reliable Informant"),
    _entry(51, "sardaukar-coordination", "Sardaukar Coordination", copies=2),
    _entry(15, "sardaukar-soldier", "Sardaukar Soldier"),
    _entry(48, "shishakli", "Shishakli"),
    _entry(17, "smuggler-s-harvester", "Smuggler's Harvester", copies=2),
    _entry(47, "smuggler-s-haven", "Smuggler's Haven"),
    _entry(56, "southern-elders", "Southern Elders"),
    _entry(12, "space-time-folding", "Space-time Folding"),
    _entry(60, "spacing-guild-s-favor", "Spacing Guild's Favor", copies=2),
    _entry(25, "spy-network", "Spy Network"),
    _entry(76, "steersman", "Steersman"),
    _entry(70, "stilgar-the-devoted", "Stilgar, The Devoted"),
    _entry(65, "strike-fleet", "Strike Fleet"),
    _entry(62, "subversive-advisor", "Subversive Advisor"),
    _entry(66, "treacherous-maneuver", "Treacherous Maneuver"),
    _entry(58, "tread-in-darkness", "Tread in Darkness", copies=2),
    _entry(53, "truthtrance", "Truthtrance", copies=2),
    _entry(28, "undercover-asset", "Undercover Asset"),
    _entry(11, "unswerving-loyalty", "Unswerving Loyalty", copies=2),
    _entry(14, "weirding-woman", "Weirding Woman", copies=2),
    _entry(22, "wheels-within-wheels", "Wheels Within Wheels"),
)


def imperium_cards_for_choam(choam_module: bool) -> tuple[DeckCardEntry, ...]:
    """Return physical card entries included by the selected setup."""

    return tuple(
        entry for entry in IMPERIUM_CARDS if choam_module or not entry.choam_only
    )


def imperium_deck_instance_ids(choam_module: bool) -> tuple[str, ...]:
    """Return stable IDs for every physical Imperium card copy."""

    return tuple(
        f"imperium:{entry.card.card_id}:{copy}"
        for entry in imperium_cards_for_choam(choam_module)
        for copy in range(entry.copies)
    )
