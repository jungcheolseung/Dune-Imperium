"""Rise of Ix's cards against the app's attribute table.

docs/base-game-and-ix-plan.md 17.7, as P3a's ``test_imperium_app_table.py``
did for the original game: the names, copies and costs of Rise of Ix's
Imperium and Intrigue cards come from the Steam app's attribute table
(``agents/app_ai/data/archetypes.py``), and a plain pytest keeps every
identity entry equal to it. ``scripts/dwgr/imperium_entries.py --set ix``
writes the entries from the same table; this test reads it on its own, so a
slip in the generator does not pass unseen.
"""

import re

from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES, Archetype
from dune_imperium.content.imperium.imperium import IMPERIUM_BASE_CARDS
from dune_imperium.content.imperium.intrigue import IMPERIUM_INTRIGUE_CARDS
from dune_imperium.content.rise_of_ix.imperium import IX_IMPERIUM_CARDS
from dune_imperium.content.rise_of_ix.intrigue import IX_INTRIGUE_CARDS
from dune_imperium.content.schema import SourceDocument, SourceRef
from dune_imperium.content.uprising.imperium import (
    IMPERIUM_CARDS,
    IMPERIUM_CARDS_BY_ID,
)
from dune_imperium.content.uprising.intrigue import (
    INTRIGUE_CARDS,
    INTRIGUE_CARDS_BY_ID,
    INTRIGUE_CARDS_BY_INSTANCE,
)
from dune_imperium.content.uprising.leaders import LEADERS_BY_ID
from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID

# The one name Rise of Ix prints that another kind already uses: the
# Bloodlines Leader ``esmar_tuek`` (plan 17.2); it takes ``_card``.
_SUFFIXED = frozenset({"Esmar Tuek"})
_IX_PROMOS = frozenset({"Boundless Ambition"})


def _title(archetype: Archetype) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", archetype.title or "")).strip()


def _id(archetype: Archetype) -> str:
    title = _title(archetype)
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower().replace("'", "")).strip("_")
    return f"{slug}_card" if title in _SUFFIXED else slug


def _imperium_archetypes() -> dict[str, Archetype]:
    # The Imperium deck's Main cards plus the one promo; not Control the
    # Spice, the Epic starting card (``ImperiumType`` Starter).
    return {
        _id(archetype): archetype
        for short, archetype in ARCHETYPES.items()
        if (
            short.startswith("ImperiumArchetypes.RiseOfIx.")
            and archetype.attributes.get("ImperiumType") == "Main"
        )
        or (
            short.startswith("ImperiumArchetypes.Promo.")
            and _title(archetype) in _IX_PROMOS
        )
    }


def _intrigue_archetypes() -> dict[str, Archetype]:
    return {
        _id(archetype): archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith("IntrigueArchetypes.RiseOfIx.")
    }


def test_every_ix_card_has_an_entry_and_no_more() -> None:
    # 29 Imperium kinds and 35 cards, the promo apart, and 17 Intrigue cards
    # [Rise of Ix p. 2] (docs/rules/rise-of-ix.md 2).
    imperium = {entry.card.card_id: entry for entry in IX_IMPERIUM_CARDS}
    intrigue = {entry.card.card_id: entry for entry in IX_INTRIGUE_CARDS}
    assert len(imperium) == len(IX_IMPERIUM_CARDS)
    assert len(intrigue) == len(IX_INTRIGUE_CARDS)
    assert set(imperium) == set(_imperium_archetypes())
    assert set(intrigue) == set(_intrigue_archetypes())
    deck = [entry for entry in IX_IMPERIUM_CARDS if not entry.promo]
    assert (len(deck), sum(entry.copies for entry in deck)) == (29, 35)
    promos = [entry for entry in IX_IMPERIUM_CARDS if entry.promo]
    assert [(e.card.name, e.copies) for e in promos] == [("Boundless Ambition", 1)]
    assert (len(intrigue), sum(e.copies for e in IX_INTRIGUE_CARDS)) == (17, 17)


def test_the_epic_starting_card_is_not_an_imperium_card() -> None:
    # The app files Control the Spice under Rise of Ix as a Starter; it is
    # Uprising's Epic starting card already (``content.uprising``), and Rise
    # of Ix + Epic uses the same card (plan 17.2).
    starters = [
        archetype
        for short, archetype in ARCHETYPES.items()
        if short.startswith("ImperiumArchetypes.RiseOfIx.")
        and archetype.attributes.get("ImperiumType") != "Main"
    ]
    assert [_title(archetype) for archetype in starters] == ["Control The Spice"]
    assert starters[0].attributes.get("ImperiumType") == "Starter"
    assert "control_the_spice" in STARTING_CARDS_BY_ID
    assert "control_the_spice" not in {e.card.card_id for e in IX_IMPERIUM_CARDS}


def test_names_copies_and_costs_match_the_app() -> None:
    table = _imperium_archetypes()
    for entry in IX_IMPERIUM_CARDS:
        archetype = table[entry.card.card_id]
        assert entry.card.name == _title(archetype), entry.card.card_id
        assert entry.copies == archetype.attributes["CardCount"], entry.card.card_id
        assert entry.acquisition_cost == archetype.attributes.get(
            "PersuasionCost", 0
        ), entry.card.card_id
        assert entry.promo == (".Promo." in archetype.short), entry.card.card_id
    intrigue = _intrigue_archetypes()
    for card in IX_INTRIGUE_CARDS:
        archetype = intrigue[card.card.card_id]
        assert card.card.name == _title(archetype), card.card.card_id
        assert card.copies == archetype.attributes["CardCount"], card.card.card_id


def test_esmar_tuek_takes_the_card_suffix() -> None:
    # The Ix Imperium card and the Bloodlines Leader share a name; the Leader
    # keeps ``esmar_tuek`` and the card is ``esmar_tuek_card`` (plan 17.2).
    ids = {entry.card.card_id: entry for entry in IX_IMPERIUM_CARDS}
    assert "esmar_tuek" not in ids
    assert ids["esmar_tuek_card"].card.name == "Esmar Tuek"
    assert "esmar_tuek" in LEADERS_BY_ID
    assert "esmar_tuek_card" not in LEADERS_BY_ID
    # No other Rise of Ix card takes the suffix.
    assert {card_id for card_id in ids if card_id.endswith("_card")} == {
        "esmar_tuek_card"
    }
    assert not [
        entry.card.card_id
        for entry in IX_INTRIGUE_CARDS
        if entry.card.card_id.endswith("_card")
    ]


def test_no_ix_id_collides_with_an_existing_id() -> None:
    # An id names one printing across the merged lookup tables, so a
    # collision would silently replace a card in them (plan 4.2 7, 17.2).
    ix_imperium = [entry.card.card_id for entry in IX_IMPERIUM_CARDS]
    ix_intrigue = [entry.card.card_id for entry in IX_INTRIGUE_CARDS]
    existing_imperium = {
        entry.card.card_id for entry in (*IMPERIUM_CARDS, *IMPERIUM_BASE_CARDS)
    }
    existing_intrigue = {
        entry.card.card_id for entry in (*INTRIGUE_CARDS, *IMPERIUM_INTRIGUE_CARDS)
    }
    assert not existing_imperium.intersection(ix_imperium)
    assert not existing_intrigue.intersection(ix_intrigue)
    # Nor with a Leader or a starting card; and no id repeats inside the
    # Ix cards, whichever kind they are.
    others = {*LEADERS_BY_ID, *STARTING_CARDS_BY_ID}
    assert not others.intersection(ix_imperium)
    assert not others.intersection(ix_intrigue)
    assert len({*ix_imperium, *ix_intrigue}) == len(ix_imperium) + len(ix_intrigue)
    # The merged tables lost nothing to a collision.
    assert len(IMPERIUM_CARDS_BY_ID) == len(existing_imperium) + len(ix_imperium)
    assert len(INTRIGUE_CARDS_BY_ID) == len(existing_intrigue) + len(ix_intrigue)


def test_ix_cards_resolve_in_the_merged_tables_only() -> None:
    for entry in IX_IMPERIUM_CARDS:
        assert IMPERIUM_CARDS_BY_ID[entry.card.card_id] is entry
    for card in IX_INTRIGUE_CARDS:
        assert INTRIGUE_CARDS_BY_ID[card.card.card_id] is card
        for copy in range(card.copies):
            instance = f"intrigue:{card.card.card_id}:{copy}"
            assert INTRIGUE_CARDS_BY_INSTANCE[instance] is card
    # Code that lists Uprising's or the original game's own cards does not
    # see them: the observation, the slots, the server catalog and the decks
    # list those tuples (plan 17.1: they take Rise of Ix at v39).
    ix_ids = {e.card.card_id for e in IX_IMPERIUM_CARDS}
    ix_ids |= {e.card.card_id for e in IX_INTRIGUE_CARDS}
    listed = {e.card.card_id for e in (*IMPERIUM_CARDS, *IMPERIUM_BASE_CARDS)}
    listed |= {e.card.card_id for e in (*INTRIGUE_CARDS, *IMPERIUM_INTRIGUE_CARDS)}
    assert not ix_ids & listed


def test_ix_entries_are_identities_only() -> None:
    # Stage P4a lists the cards before their play data (plan 17.7); a
    # transcribed card replaces its entry and the deck then takes it.
    for entry in IX_IMPERIUM_CARDS:
        assert not entry.play_data_complete, entry.card.card_id
        assert entry.factions == () and entry.agent_icons == (), entry.card.card_id
    for card in IX_INTRIGUE_CARDS:
        assert not card.play_data_complete, card.card.card_id
        assert card.options == (), card.card.card_id


def test_ix_entries_cite_the_component_table() -> None:
    sources = (SourceRef(SourceDocument.RISE_OF_IX_RULEBOOK, (2,)),)
    for entry in (*IX_IMPERIUM_CARDS, *IX_INTRIGUE_CARDS):
        assert entry.card.sources == sources, entry.card.card_id
