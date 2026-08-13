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
    acquisition_cost: int,
    *,
    copies: int = 1,
    choam_only: bool = False,
    has_acquisition_bonus: bool = False,
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
        acquisition_cost=acquisition_cost,
        has_acquisition_bonus=has_acquisition_bonus,
    )


IMPERIUM_CARDS: Final = (
    _entry(30, "bene-gesserit-operative", "Bene Gesserit Operative", 3, copies=2),
    _entry(45, "branching-path", "Branching Path", 3),
    _entry(42, "calculus-of-power", "Calculus of Power", 3, copies=2),
    _entry(61, "captured-mentat", "Captured Mentat", 5),
    _entry(181, "cargo-runner", "Cargo Runner", 3, choam_only=True),
    _entry(67, "chani-clever-tactician", "Chani, Clever Tactician", 5),
    _entry(69, "corrinth-city", "Corrinth City", 6),
    _entry(35, "covert-operation", "Covert Operation", 3),
    _entry(44, "dangerous-rhetoric", "Dangerous Rhetoric", 3),
    _entry(182, "delivery-agreement", "Delivery Agreement", 5, choam_only=True),
    _entry(71, "desert-power", "Desert Power", 6),
    _entry(27, "desert-survival", "Desert Survival", 2, copies=2),
    _entry(37, "double-agent", "Double Agent", 3, copies=2),
    _entry(46, "ecological-testing-station", "Ecological Testing Station", 3),
    _entry(23, "fedaykin-stilltent", "Fedaykin Stilltent", 2),
    _entry(38, "guild-envoy", "Guild Envoy", 3),
    _entry(43, "guild-spy", "Guild Spy", 3, has_acquisition_bonus=True),
    _entry(21, "hidden-missive", "Hidden Missive", 2),
    _entry(24, "imperial-spymaster", "Imperial Spymaster", 2),
    _entry(64, "in-high-places", "In High Places", 5, has_acquisition_bonus=True),
    _entry(
        184,
        "interstellar-trade",
        "Interstellar Trade",
        7,
        choam_only=True,
        has_acquisition_bonus=True,
    ),
    _entry(68, "junction-headquarters", "Junction Headquarters", 6),
    _entry(63, "leadership", "Leadership", 5),
    _entry(74, "long-live-the-fighters", "Long Live the Fighters", 7),
    _entry(19, "maker-keeper", "Maker Keeper", 2, copies=2),
    _entry(32, "maula-pistol", "Maula Pistol", 3, copies=2),
    _entry(34, "northern-watermaster", "Northern Watermaster", 3),
    _entry(75, "overthrow", "Overthrow", 8, has_acquisition_bonus=True),
    _entry(49, "paracompass", "Paracompass", 4),
    _entry(
        73,
        "price-is-no-object",
        "Price is No Object",
        6,
        has_acquisition_bonus=True,
    ),
    _entry(183, "priority-contracts", "Priority Contracts", 6, choam_only=True),
    _entry(55, "public-spectacle", "Public Spectacle", 4, copies=2),
    _entry(40, "rebel-supplier", "Rebel Supplier", 3, copies=2),
    _entry(20, "reliable-informant", "Reliable Informant", 2),
    _entry(51, "sardaukar-coordination", "Sardaukar Coordination", 4, copies=2),
    _entry(15, "sardaukar-soldier", "Sardaukar Soldier", 1),
    _entry(48, "shishakli", "Shishakli", 4),
    _entry(17, "smuggler-s-harvester", "Smuggler's Harvester", 1, copies=2),
    _entry(47, "smuggler-s-haven", "Smuggler's Haven", 4),
    _entry(56, "southern-elders", "Southern Elders", 4),
    _entry(12, "space-time-folding", "Space-time Folding", 1),
    _entry(60, "spacing-guild-s-favor", "Spacing Guild's Favor", 5, copies=2),
    _entry(25, "spy-network", "Spy Network", 2, has_acquisition_bonus=True),
    _entry(76, "steersman", "Steersman", 8, has_acquisition_bonus=True),
    _entry(70, "stilgar-the-devoted", "Stilgar, The Devoted", 6),
    _entry(65, "strike-fleet", "Strike Fleet", 5, has_acquisition_bonus=True),
    _entry(
        62,
        "subversive-advisor",
        "Subversive Advisor",
        5,
        has_acquisition_bonus=True,
    ),
    _entry(66, "treacherous-maneuver", "Treacherous Maneuver", 5),
    _entry(58, "tread-in-darkness", "Tread in Darkness", 4, copies=2),
    _entry(53, "truthtrance", "Truthtrance", 4, copies=2),
    _entry(28, "undercover-asset", "Undercover Asset", 2),
    _entry(11, "unswerving-loyalty", "Unswerving Loyalty", 1, copies=2),
    _entry(14, "weirding-woman", "Weirding Woman", 1, copies=2),
    _entry(22, "wheels-within-wheels", "Wheels Within Wheels", 2),
)

IMPERIUM_CARDS_BY_ID: Final = {
    entry.card.card_id: entry for entry in IMPERIUM_CARDS
}


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


def imperium_card_for_instance(instance_id: str) -> DeckCardEntry:
    """Resolve a stable Imperium deck instance ID to its definition."""

    prefix = "imperium:"
    if not instance_id.startswith(prefix):
        raise ValueError("not an Imperium-card instance ID")
    try:
        card_id, copy_text = instance_id.removeprefix(prefix).rsplit(":", maxsplit=1)
        copy = int(copy_text)
        entry = IMPERIUM_CARDS_BY_ID[card_id]
    except (KeyError, ValueError) as error:
        raise ValueError("unknown Imperium-card instance ID") from error
    if copy < 0 or copy >= entry.copies:
        raise ValueError("Imperium-card copy index is out of range")
    return entry
