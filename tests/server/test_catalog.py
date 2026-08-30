"""Tests for the static display catalog behind the web UI."""

import json

from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_ID
from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID
from dune_imperium.server.catalog import build_catalog


def test_catalog_is_json_serializable_and_covers_every_card() -> None:
    catalog = build_catalog()
    json.dumps(catalog)

    cards = catalog["cards"]
    assert isinstance(cards, dict)
    for card_id in (*STARTING_CARDS_BY_ID, "prepare_the_way", *IMPERIUM_CARDS_BY_ID):
        assert card_id in cards
    intrigue = catalog["intrigue"]
    assert isinstance(intrigue, dict)
    assert set(intrigue) == set(INTRIGUE_CARDS_BY_ID)


def test_catalog_names_and_details_match_the_manifests() -> None:
    catalog = build_catalog()
    cards = catalog["cards"]
    assert isinstance(cards, dict)

    soldier = cards["sardaukar_soldier"]
    assert isinstance(soldier, dict)
    assert soldier["name"] == "Sardaukar Soldier"
    assert isinstance(soldier["cost"], int)

    spice_must_flow = cards["the_spice_must_flow"]
    assert isinstance(spice_must_flow, dict)
    assert spice_must_flow["cost"] == 9

    dagger = cards["dagger"]
    assert isinstance(dagger, dict)
    assert dagger["cost"] is None
    assert dagger["swords"] == 1

    intrigue = catalog["intrigue"]
    assert isinstance(intrigue, dict)
    cunning = intrigue["cunning"]
    assert isinstance(cunning, dict)
    assert cunning["timings"] == ["plot"]

    leaders = catalog["leaders"]
    assert isinstance(leaders, dict)
    staban = leaders["staban_tuek"]
    assert isinstance(staban, dict)
    assert staban["name"] == "Staban Tuek"

    spaces = catalog["spaces"]
    assert isinstance(spaces, dict)
    assert "high_council" in spaces
