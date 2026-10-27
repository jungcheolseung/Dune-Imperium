"""The original game's cards against the app's attribute table.

docs/base-game-and-ix-plan.md 9 (4) and 11 (1), D4-1: the numbers, icons,
copies and Factions of the original Imperium and Intrigue cards come from the
Steam app's attribute table (``agents/app_ai/data/archetypes.py``), and a
plain pytest keeps every card equal to it. ``scripts/dwgr/imperium_entries.py``
writes the entries from the same table; this test reads it on its own, so a
slip in the generator does not pass unseen. A printed value the app does
not hold in that field is listed in ``EXCEPTIONS`` with its ground.
"""

import re
from collections import Counter

from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.types import AgentIcon

# The app's Agent icon names; Pentagon/Circle/Triangle are Landsraad/City/
# Spice Trade (the app's own legend, P0 sweep).
_ICONS = {
    "Emperor": AgentIcon.EMPEROR,
    "SpacingGuild": AgentIcon.SPACING_GUILD,
    "BeneGesserit": AgentIcon.BENE_GESSERIT,
    "Fremen": AgentIcon.FREMEN,
    "Pentagon": AgentIcon.LANDSRAAD,
    "Circle": AgentIcon.CITY,
    "Triangle": AgentIcon.SPICE_TRADE,
}
_FACTIONS = {
    "Emperor": Faction.EMPEROR,
    "SpacingGuild": Faction.SPACING_GUILD,
    "BeneGesserit": Faction.BENE_GESSERIT,
    "Fremen": Faction.FREMEN,
}
_BASE_PROMOS = frozenset({"Duncan, Loyal Blade", "Jessica of Arrakis", "Thumper"})
# Names another kind already uses take ``_card`` (plan 16.2).
_SUFFIXED = frozenset(
    {
        "Crysknife",
        "Chani",
        "Duncan Idaho",
        "Gurney Halleck",
        "Lady Jessica",
        "Liet Kynes",
        "Piter De Vries",
    }
)
# (card id, field) -> why the entry differs from the app's attribute.
EXCEPTIONS: dict[tuple[str, str], str] = {}


def _title(archetype: Archetype) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", archetype.title or "")).strip()


def _id(archetype: Archetype) -> str:
    title = _title(archetype)
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower().replace("'", "")).strip("_")
    return f"{slug}_card" if title in _SUFFIXED else slug


def _imperium_archetypes() -> dict[str, Archetype]:
    return {
        _id(archetype): archetype
        for short, archetype in ARCHETYPES.items()
        if (
            short.startswith("ImperiumArchetypes.BaseSet.")
            and archetype.attributes.get("ImperiumType") == "Main"
        )
        or (
            short.startswith("ImperiumArchetypes.Promo.")
            and _title(archetype) in _BASE_PROMOS
        )
    }


def _intrigue_archetypes() -> dict[str, Archetype]:
    return {
        _id(archetype): archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith("IntrigueArchetypes.BaseSet.")
    }


def test_every_original_card_has_an_entry_and_no_more() -> None:
    # 43 Imperium kinds and 67 cards, 34 Intrigue kinds and 40 cards [DI p. 3],
    # and the three promos (plan 9 8).
    imperium = {entry.card.card_id: entry for entry in IMPERIUM_BASE_CARDS}
    intrigue = {entry.card.card_id: entry for entry in IMPERIUM_INTRIGUE_CARDS}
    assert len(imperium) == len(IMPERIUM_BASE_CARDS)
    assert len(intrigue) == len(IMPERIUM_INTRIGUE_CARDS)
    assert set(imperium) == set(_imperium_archetypes())
    assert set(intrigue) == set(_intrigue_archetypes())
    deck = [entry for entry in IMPERIUM_BASE_CARDS if not entry.promo]
    assert (len(deck), sum(entry.copies for entry in deck)) == (43, 67)
    assert (len(intrigue), sum(e.copies for e in IMPERIUM_INTRIGUE_CARDS)) == (34, 40)


def test_names_copies_and_costs_match_the_app() -> None:
    table = _imperium_archetypes()
    for entry in IMPERIUM_BASE_CARDS:
        archetype = table[entry.card.card_id]
        assert entry.card.name == _title(archetype), entry.card.card_id
        assert entry.copies == archetype.attributes["CardCount"], entry.card.card_id
        assert entry.acquisition_cost == archetype.attributes.get(
            "PersuasionCost", 0
        ), entry.card.card_id
        assert entry.promo == (".Promo." in archetype.short), entry.card.card_id
    intrigue = _intrigue_archetypes()
    for entry in IMPERIUM_INTRIGUE_CARDS:
        archetype = intrigue[entry.card.card_id]
        assert entry.card.name == _title(archetype), entry.card.card_id
        assert entry.copies == archetype.attributes["CardCount"], entry.card.card_id


def test_transcribed_cards_match_the_app_attributes() -> None:
    table = _imperium_archetypes()
    for entry in IMPERIUM_BASE_CARDS:
        if not entry.play_data_complete:
            continue
        card_id = entry.card.card_id
        attributes = table[card_id].attributes
        expected = {
            "factions": tuple(_FACTIONS[f] for f in attributes.get("FactionList", ())),
            "agent_icons": Counter(_ICONS[i] for i in attributes.get("IconList", ())),
            "reveal_persuasion": attributes.get("Persuasion", 0),
            "reveal_strength": attributes.get("Strength", 0),
        }
        actual = {
            "factions": entry.factions,
            "agent_icons": Counter(entry.agent_icons),
            "reveal_persuasion": entry.reveal_persuasion,
            "reveal_strength": entry.reveal_strength,
        }
        for field, value in expected.items():
            if (card_id, field) in EXCEPTIONS:
                continue
            assert actual[field] == value, (card_id, field)


def test_intrigue_types_match_the_app() -> None:
    table = _intrigue_archetypes()
    for entry in IMPERIUM_INTRIGUE_CARDS:
        if not entry.play_data_complete:
            continue
        printed = {
            str(t).lower()
            for t in table[entry.card.card_id].attributes["IntrigueTypeList"]
        }
        assert {timing.value for timing in entry.timings} == printed, entry.card.card_id
