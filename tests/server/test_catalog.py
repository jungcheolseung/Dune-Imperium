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


def test_catalog_serves_the_tleilaxu_deck_and_the_bene_tleilax_board() -> None:
    from dune_imperium.content.immortality.board import RESEARCH_SPACES
    from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID

    catalog = build_catalog()
    cards = catalog["cards"]
    assert isinstance(cards, dict)
    for card_id in (*TLEILAXU_CARDS_BY_ID, "reclaimed_forces"):
        assert card_id in cards
    ghola = cards["ghola"]
    assert isinstance(ghola, dict)
    # Tleilaxu cards cost specimens, never Persuasion [Immortality p. 8].
    assert ghola["cost"] is None and ghola["specimens"] == 3
    assert ghola["graft"] is True
    board = catalog["bene_tleilax"]
    assert isinstance(board, dict)
    spaces = board["research_spaces"]
    assert isinstance(spaces, list) and len(spaces) == len(RESEARCH_SPACES)
    assert board["genetic_marker_columns"] == [4, 8]
    assert board["research_start"] == "c0r3"
    track = board["tleilaxu_track"]
    assert isinstance(track, list) and len(track) == 8


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


def test_catalog_serves_generated_effect_text() -> None:
    catalog = build_catalog()

    cards = catalog["cards"]
    assert isinstance(cards, dict)
    for entry in cards.values():
        assert isinstance(entry, dict)
        assert isinstance(entry["text"], list)
        assert entry["text"]

    intrigue = catalog["intrigue"]
    assert isinstance(intrigue, dict)
    for card_id, entry in intrigue.items():
        assert isinstance(entry, dict)
        # Bloodlines / Immortality Intrigue awaiting transcription has no
        # option text yet and never enters a deck until it does.
        card = INTRIGUE_CARDS_BY_ID[card_id]
        if entry["text"] == [] and (card.bloodlines_only or card.immortality_only):
            continue
        assert entry["text"]

    contracts = catalog["contracts"]
    assert isinstance(contracts, dict)
    for entry in contracts.values():
        assert isinstance(entry, dict)
        assert entry["condition"]
        assert entry["reward"]
        assert isinstance(entry["immediate"], bool)

    conflicts = catalog["conflicts"]
    assert isinstance(conflicts, dict)
    for entry in conflicts.values():
        assert isinstance(entry, dict)
        rewards = entry["rewards"]
        assert rewards is None or (
            isinstance(rewards, list) and len(rewards) == 3
        )
        assert "shield_wall_protected" in entry
        assert "icon" in entry


def test_catalog_includes_leader_alternate_faces_with_text() -> None:
    catalog = build_catalog()
    leaders = catalog["leaders"]
    assert isinstance(leaders, dict)

    jessica = leaders["lady_jessica"]
    assert isinstance(jessica, dict)
    assert jessica["ability"] == "Other Memories"
    assert jessica["ability_text"]
    assert jessica["signet_text"]

    reverend_mother = leaders["reverend_mother_jessica"]
    assert isinstance(reverend_mother, dict)
    assert reverend_mother["name"] == "Reverend Mother Jessica"
    assert reverend_mother["ability"] == "Reverend Mother"
    assert reverend_mother["signet"] == "Water of Life"
    assert reverend_mother["ability_text"]


def test_catalog_spaces_carry_structured_board_data() -> None:
    catalog = build_catalog()
    spaces = catalog["spaces"]
    assert isinstance(spaces, dict)
    assert len(spaces) == 22 + 1  # Tuek's Sietch (Bloodlines)

    sardaukar = spaces["sardaukar"]
    assert isinstance(sardaukar, dict)
    assert sardaukar["agent_icon"] == "emperor"
    assert sardaukar["options"] == [
        {
            "cost": {"solari": 0, "spice": 4, "water": 0},
            "effect": (
                "Gain 1 Emperor Influence, Draw 1 Intrigue card, "
                "Recruit 4 troops"
            ),
        }
    ]
    assert sardaukar["choam_options"] is None
    assert sardaukar["implemented"] is True

    shipping = spaces["shipping"]
    assert isinstance(shipping, dict)
    assert shipping["requirement"] == {"faction": "spacing_guild", "amount": 2}
    assert shipping["implemented"] is True
    assert shipping["choam_implemented"] is True

    dutiful_service = spaces["dutiful_service"]
    assert isinstance(dutiful_service, dict)
    assert dutiful_service["implemented"] is True
    assert dutiful_service["choam_implemented"] is True
    assert dutiful_service["choam_options"] is not None

    imperial_basin = spaces["imperial_basin"]
    assert isinstance(imperial_basin, dict)
    assert imperial_basin["combat"] is True
    assert imperial_basin["maker"] is True
    assert imperial_basin["critical"] is True
    assert imperial_basin["notes"]

    swordmaster = spaces["swordmaster"]
    assert isinstance(swordmaster, dict)
    assert swordmaster["dynamic_cost"] == "swordmaster"
    options = swordmaster["options"]
    assert isinstance(options, list)
    assert len(options) == 2


def test_catalog_image_urls_follow_the_resolved_index() -> None:
    with_images = build_catalog(
        frozenset(
            {
                (
                    "imperium",
                    "sardaukar_soldier",
                    "en/uprising/imperium/Sardaukar Soldier.webp",
                ),
                ("location", "arrakeen", "ko/uprising/location/Arrakeen.webp"),
                ("other", "dagger", "en/base/starting/Dagger.webp"),
            }
        )
    )
    cards = with_images["cards"]
    assert isinstance(cards, dict)
    soldier = cards["sardaukar_soldier"]
    assert isinstance(soldier, dict)
    # Printed names carry spaces: the URL is percent-encoded for the mount.
    assert soldier["image"] == (
        "/card-images/en/uprising/imperium/Sardaukar%20Soldier.webp"
    )
    dagger = cards["dagger"]
    assert isinstance(dagger, dict)
    assert dagger["image"] == "/card-images/en/base/starting/Dagger.webp"
    spice_must_flow = cards["the_spice_must_flow"]
    assert isinstance(spice_must_flow, dict)
    assert spice_must_flow["image"] is None
    spaces = with_images["spaces"]
    assert isinstance(spaces, dict)
    arrakeen = spaces["arrakeen"]
    assert isinstance(arrakeen, dict)
    assert arrakeen["image"] == "/card-images/ko/uprising/location/Arrakeen.webp"

    without_images = build_catalog()
    cards = without_images["cards"]
    assert isinstance(cards, dict)
    soldier = cards["sardaukar_soldier"]
    assert isinstance(soldier, dict)
    assert soldier["image"] is None


def test_catalog_carries_board_overlay_layout_and_optional_icons() -> None:
    catalog = build_catalog()
    spaces = catalog["spaces"]
    assert isinstance(spaces, dict)
    for entry in spaces.values():
        assert isinstance(entry, dict)
        box = entry["box"]
        assert isinstance(box, list) and len(box) == 4
    posts = catalog["posts"]
    assert isinstance(posts, dict)
    assert len(posts) == 13
    assert catalog["icons"] == {}
    assert catalog["board_image"] is None

    with_assets = build_catalog(
        frozenset(),
        frozenset({"troop.png", "spice.png", "not-an-icon.png"}),
        True,
    )
    assert with_assets["icons"] == {
        "troop": "/icons/troop.png",
        "spice": "/icons/spice.png",
    }
    assert with_assets["board_image"] == "/board-image"


def test_catalog_cross_section_id_overlaps_are_pinned() -> None:
    """Sections share one namespace in the client's lookup(); overlapping
    ids are legal content (a Contract named after a space) but each one
    must be a conscious, pinned decision because the client resolves space
    ids explicitly against the spaces section to disambiguate."""

    catalog = build_catalog()
    sections = [
        "cards",
        "intrigue",
        "contracts",
        "conflicts",
        "leaders",
        "spaces",
        "skills",
        "tech",
    ]
    overlaps: dict[tuple[str, str], set[str]] = {}
    for index, first in enumerate(sections):
        first_section = catalog[first]
        assert isinstance(first_section, dict)
        for second in sections[index + 1 :]:
            second_section = catalog[second]
            assert isinstance(second_section, dict)
            shared = set(first_section) & set(second_section)
            if shared:
                overlaps[(first, second)] = shared
    assert overlaps == {("contracts", "spaces"): {"deliver_supplies"}}


def test_catalog_serves_bloodlines_skills_and_tech_tiles() -> None:
    from dune_imperium.content.bloodlines.sardaukar import SKILLS_BY_ID
    from dune_imperium.content.bloodlines.tech import TECH_TILES_BY_ID

    catalog = build_catalog()
    skills = catalog["skills"]
    assert isinstance(skills, dict)
    assert set(skills) == set(SKILLS_BY_ID)
    hardy = skills["hardy"]
    assert isinstance(hardy, dict)
    assert hardy["name"] == "Hardy"
    assert hardy["kind"] in ("reveal", "combat", "passive")
    assert isinstance(hardy["text"], list) and hardy["text"][0]
    assert hardy["image"] is None or isinstance(hardy["image"], str)

    tech = catalog["tech"]
    assert isinstance(tech, dict)
    assert set(tech) == set(TECH_TILES_BY_ID)
    high_command = tech["sardaukar_high_command"]
    assert isinstance(high_command, dict)
    assert high_command["name"] == "Sardaukar High Command"
    assert high_command["cost"] == 7
    assert high_command["acquire"] == "Gain 1 VP"
    assert high_command["text"] == [
        "Acquire: Gain 1 VP",
        str(high_command["ability"]),
    ]
    assert high_command["flips"] is False
    plain = tech["training_depot"]
    assert isinstance(plain, dict)
    assert plain["acquire"] == ""
    assert plain["text"] == [plain["ability"]]
    embassy = catalog["embassy_image"]
    assert embassy is None or isinstance(embassy, str)
    json.dumps(catalog)


def test_catalog_bene_tleilax_layout_covers_the_board() -> None:
    """The scan overlay names every research space and all eight track
    spaces, and the image URL appears only when the scan is present."""

    from dune_imperium.content.immortality.board import RESEARCH_SPACES_BY_ID

    without = build_catalog()["bene_tleilax"]
    assert isinstance(without, dict)
    assert without["image"] is None
    layout = without["layout"]
    assert isinstance(layout, dict)
    points = layout["research_points"]
    assert isinstance(points, dict)
    assert set(points) == set(RESEARCH_SPACES_BY_ID)
    for point in points.values():
        assert isinstance(point, list) and len(point) == 2
        for value in point:
            assert isinstance(value, float) and 0 <= value <= 100
    cells = layout["track_cells"]
    assert isinstance(cells, list) and len(cells) == 8
    with_scan = build_catalog(bene_tleilax_image=True)["bene_tleilax"]
    assert isinstance(with_scan, dict)
    assert with_scan["image"] == "/bene-tleilax-image"
