"""Tests for the static display catalog behind the web UI."""

import json
import re

from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_ID
from dune_imperium.content.uprising.starting_cards import STARTING_CARDS_BY_ID
from dune_imperium.display.board_layout import LEADER_TILE_BOXES, SPACE_BOXES
from dune_imperium.server.catalog import build_catalog
from dune_imperium.server.sessions import JsonValue


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


def test_catalog_serves_the_reserve_stacks_printed_factions() -> None:
    # Prepare the Way prints a purple "BENE GESSERIT" affiliation banner and
    # The Spice Must Flow a red "SPACING GUILD" one [card face]; the catalog
    # must expose each Reserve stack's own factions, not the empty tuple it
    # used to hard-code.
    catalog = build_catalog()
    cards = catalog["cards"]
    assert isinstance(cards, dict)

    prepare_the_way = cards["prepare_the_way"]
    assert isinstance(prepare_the_way, dict)
    assert prepare_the_way["factions"] == ["bene_gesserit"]

    spice_must_flow = cards["the_spice_must_flow"]
    assert isinstance(spice_must_flow, dict)
    assert spice_must_flow["factions"] == ["spacing_guild"]


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


def test_catalog_flags_every_graft_card_the_engine_knows() -> None:
    """Graft cards are in Immortality's Imperium deck as well as in the
    Tleilaxu deck [Immortality p. 10]. The browser reads the flag for the
    card's "Graft" mark and to tell which two hand cards may be played
    together; the Imperium ones were missing until 2026-09-19."""

    from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
    from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
    from dune_imperium.content.uprising.personal_cards import card_is_graft

    cards = build_catalog()["cards"]
    assert isinstance(cards, dict)
    flagged = {
        card_id
        for card_id, entry in cards.items()
        if isinstance(entry, dict) and entry.get("graft")
    }
    engine = {
        card_id
        for card_id, entry in (
            *IMPERIUM_CARDS_BY_ID.items(),
            *TLEILAXU_CARDS_BY_ID.items(),
        )
        if card_is_graft(entry)
    }
    assert flagged == engine
    assert "dissecting_kit" in flagged and "ghola" in flagged


def test_catalog_pairs_each_korean_picture_with_the_english_one() -> None:
    """The English UI's index prefers English pictures, the Korean UI's
    Korean ones; an entry whose two differ carries both, versioned, and the
    page shows the one of its language. One with the same picture in both
    (no Korean file) carries only ``image``."""

    english = frozenset(
        {
            ("imperium", "steersman", "en/uprising/imperium/Steersman.webp"),
            ("other", "dagger", "en/base/starting/Dagger.webp"),
            ("leader", "muad_dib", "en/uprising/leader/Muad'Dib.webp"),
        }
    )
    korean = frozenset(
        {
            ("imperium", "steersman", "ko/uprising/imperium/Steersman.webp"),
            ("other", "dagger", "en/base/starting/Dagger.webp"),
            ("leader", "muad_dib", "ko/uprising/leader/Muad'Dib.webp"),
        }
    )
    catalog = build_catalog(
        english,
        asset_versions=frozenset(
            {("/card-images/ko/uprising/imperium/Steersman.webp", "k1")}
        ),
        image_index_ko=korean,
    )
    cards = catalog["cards"]
    leaders = catalog["leaders"]
    assert isinstance(cards, dict) and isinstance(leaders, dict)
    steersman = cards["steersman"]
    dagger = cards["dagger"]
    muad_dib = leaders["muad_dib"]
    assert isinstance(steersman, dict) and isinstance(dagger, dict)
    assert isinstance(muad_dib, dict)
    assert steersman["image"] == "/card-images/en/uprising/imperium/Steersman.webp"
    assert steersman["image_ko"] == (
        "/card-images/ko/uprising/imperium/Steersman.webp?v=k1"
    )
    assert muad_dib["image_ko"] == "/card-images/ko/uprising/leader/Muad%27Dib.webp"
    assert "image_ko" not in dagger
    # Without a Korean index nothing gains a Korean picture.
    plain = build_catalog(english)["cards"]
    assert isinstance(plain, dict)
    plain_steersman = plain["steersman"]
    assert isinstance(plain_steersman, dict)
    assert "image_ko" not in plain_steersman


def test_catalog_names_the_cards_whose_korean_print_was_read() -> None:
    """``name_ko`` comes from the Korean edition's card faces
    (``display.names_ko``); a card not read keeps only its English name.
    A distinguisher the engine's English name carries but the card does
    not print stays in the Korean name: a contract's numeral, a Skirmish's
    battle icon in the glossary's words [Main p. 20]."""

    from dune_imperium.display.names_ko import KOREAN_CARD_NAMES

    catalog = build_catalog()
    hangul = re.compile(r"[가-힣]")
    for section, names in KOREAN_CARD_NAMES.items():
        entries = catalog[section]
        assert isinstance(entries, dict), section
        for entry_id, name in names.items():
            entry = entries[entry_id]
            assert isinstance(entry, dict)
            assert entry["name_ko"] == name
            assert hangul.search(name), name
            # Latin only where the English has it too: a contract's numeral,
            # or printed on the Korean card as well ("실험체 X-137").
            english = entry["name"]
            assert isinstance(english, str)
            for latin in re.findall(r"[A-Za-z]+", name):
                assert latin in english, (name, english)
    cards = catalog["cards"]
    contracts = catalog["contracts"]
    conflicts = catalog["conflicts"]
    leaders = catalog["leaders"]
    assert isinstance(cards, dict) and isinstance(contracts, dict)
    assert isinstance(conflicts, dict) and isinstance(leaders, dict)

    def korean(entries: dict[str, JsonValue], entry_id: str) -> JsonValue:
        entry = entries[entry_id]
        assert isinstance(entry, dict)
        return entry.get("name_ko")

    assert korean(cards, "steersman") == "조타수"
    assert korean(cards, "treacherous_maneuver") == "기만적인 계책"
    assert korean(contracts, "arrakeen_i") == "아라킨 I"
    assert korean(contracts, "harvest_3_contract") == "채취 3+"
    assert korean(conflicts, "skirmish_crysknife") == "소규모 전투 (크리스나이프)"
    assert korean(leaders, "shaddam_corrino_iv") == "샤담 코리노 4세"
    # Bloodlines: its Skirmish's wild battle icon [Bloodlines p. 5], the
    # Commander Skills and the Tech tiles; Immortality's Tleilaxu deck.
    skills = catalog["skills"]
    tech = catalog["tech"]
    assert isinstance(skills, dict) and isinstance(tech, dict)
    assert korean(conflicts, "skirmish_wild") == "소규모 전투 (와일드)"
    assert korean(contracts, "bloodlines_harvest_4") == "채취 4+"
    assert korean(skills, "canny") == "영리함"
    assert korean(tech, "choam_transports") == "초암 수송선"
    assert korean(cards, "subject_x_137") == "실험체 X-137"
    # Not photographed: Lady Jessica's flip side and the Bloodlines Intrigue
    # cards that lay in a pile.
    intrigue = catalog["intrigue"]
    assert isinstance(intrigue, dict)
    assert korean(leaders, "reverend_mother_jessica") is None
    assert korean(intrigue, "adaptive_tactics") is None


def test_catalog_appends_the_version_of_every_asset_it_knows() -> None:
    versions = frozenset(
        {
            ("/card-images/en/uprising/location/Arrakeen.webp", "c1"),
            ("/icons/troop.png", "i1"),
            ("/tokens/shield_wall.png", "t1"),
            ("/board-image", "b1"),
            ("/bene-tleilax-image", "s1"),
        }
    )
    catalog = build_catalog(
        frozenset(
            {
                ("location", "arrakeen", "en/uprising/location/Arrakeen.webp"),
                ("other", "dagger", "en/base/starting/Dagger.webp"),
            }
        ),
        frozenset({"troop.png", "spice.png"}),
        True,
        bene_tleilax_image=True,
        token_files=frozenset({"shield_wall.png"}),
        asset_versions=versions,
    )
    spaces = catalog["spaces"]
    cards = catalog["cards"]
    wall = catalog["shield_wall"]
    scan = catalog["bene_tleilax"]
    assert isinstance(spaces, dict) and isinstance(cards, dict)
    assert isinstance(wall, dict) and isinstance(scan, dict)
    arrakeen = spaces["arrakeen"]
    dagger = cards["dagger"]
    assert isinstance(arrakeen, dict) and isinstance(dagger, dict)
    assert arrakeen["image"] == (
        "/card-images/en/uprising/location/Arrakeen.webp?v=c1"
    )
    # An asset without a known version keeps its plain URL.
    assert dagger["image"] == "/card-images/en/base/starting/Dagger.webp"
    assert catalog["icons"] == {
        "troop": "/icons/troop.png?v=i1",
        "spice": "/icons/spice.png",
    }
    assert wall["image"] == "/tokens/shield_wall.png?v=t1"
    assert catalog["board_image"] == "/board-image?v=b1"
    assert scan["image"] == "/bene-tleilax-image?v=s1"


def test_catalog_lays_the_pieces_the_scan_does_not_print() -> None:
    bare = build_catalog()
    # The Shield Wall token on its marked position [Main p. 4]: always a
    # place, a picture only with the local file.
    wall = bare["shield_wall"]
    assert isinstance(wall, dict)
    assert wall["image"] is None
    assert wall["rotation"] == 180
    box = wall["box"]
    assert isinstance(box, list) and len(box) == 4
    with_wall = build_catalog(token_files=frozenset({"shield_wall.png"}))
    pictured = with_wall["shield_wall"]
    assert isinstance(pictured, dict)
    assert pictured["image"] == "/tokens/shield_wall.png"

    # A Sardaukar Commander stands on the top-right corner of its space's
    # frame, leaving the frame to the Agents [Bloodlines p. 3]: always a spot,
    # the rulebook figure only with the local picture.
    assert bare["commander_token"] is None
    spot = bare["commander_spot"]
    assert isinstance(spot, dict)
    assert spot["anchor"] == [0.89, 0.13]
    assert spot["height"] == 0.95
    assert spot["base"] == [0.434, 0.873]
    with_commander = build_catalog(
        token_files=frozenset({"sardaukar_commander.png"})
    )
    assert with_commander["commander_token"] == "/tokens/sardaukar_commander.png"

    spaces = bare["spaces"]
    assert isinstance(spaces, dict)
    # Immortality's Research Station overlay: "Draw two cards and research"
    # [Immortality pp. 5, 16] over the printed "Recruit 2 troops, Draw 2
    # cards", with its own picture and the box it covers.
    station = spaces["research_station"]
    assert isinstance(station, dict)
    assert station["options"] == [
        {
            "cost": {"solari": 0, "spice": 0, "water": 2},
            "effect": "Recruit 2 troops, Draw 2 cards",
        }
    ]
    overlay = station["immortality"]
    assert isinstance(overlay, dict)
    assert overlay["options"] == [
        {
            "cost": {"solari": 0, "spice": 0, "water": 2},
            "effect": "Draw 2 cards, Research (advance your research token)",
        }
    ]
    assert overlay["image"] is None
    tile_box = overlay["tile_box"]
    assert isinstance(tile_box, list) and len(tile_box) == 4
    overlays = [
        space_id
        for space_id, entry in spaces.items()
        if isinstance(entry, dict) and entry["immortality"] is not None
    ]
    assert overlays == ["research_station"]

    with_overlay = build_catalog(
        frozenset(
            {
                (
                    "location",
                    "research_station_overlay",
                    "en/immortality/location/Research Station.jpg",
                ),
                ("location", "research_station", "en/uprising/location/RS.webp"),
            }
        )
    )["spaces"]
    assert isinstance(with_overlay, dict)
    station = with_overlay["research_station"]
    assert isinstance(station, dict)
    assert station["image"] == "/card-images/en/uprising/location/RS.webp"
    overlay = station["immortality"]
    assert isinstance(overlay, dict)
    assert overlay["image"] == (
        "/card-images/en/immortality/location/Research%20Station.jpg"
    )

    # A Leader's own tile is on the table only while that Leader plays
    # [Bloodlines p. 12]; the scan has no print, so its picture is drawn,
    # around the frame its hotspot follows.
    tuek = spaces["tuek_sietch"]
    assert isinstance(tuek, dict)
    assert tuek["required_leader_id"] == "esmar_tuek"
    assert tuek["tile_box"] == list(LEADER_TILE_BOXES["tuek_sietch"])
    assert tuek["box"] == list(SPACE_BOXES["tuek_sietch"])
    printed = [
        space_id
        for space_id, entry in spaces.items()
        if isinstance(entry, dict) and entry["required_leader_id"] is None
    ]
    assert len(printed) == len(spaces) - 1
    arrakeen = spaces["arrakeen"]
    assert isinstance(arrakeen, dict)
    assert arrakeen["tile_box"] is None


def test_catalog_carries_board_overlay_layout_and_optional_icons() -> None:
    catalog = build_catalog()
    spaces = catalog["spaces"]
    assert isinstance(spaces, dict)
    for entry in spaces.values():
        assert isinstance(entry, dict)
        box = entry["box"]
        assert isinstance(box, list) and len(box) == 4
    assert catalog["space_frame"] == {"cut": [11.8, 15.3]}
    posts = catalog["posts"]
    assert isinstance(posts, dict)
    assert len(posts) == 13
    # Every drawn post can be named after the spaces it watches.
    post_spaces = catalog["post_spaces"]
    assert isinstance(post_spaces, dict)
    assert set(post_spaces) == set(posts)
    for watched in post_spaces.values():
        assert isinstance(watched, list) and watched
        assert all(space_id in spaces for space_id in watched)
    assert post_spaces["arrakis-hagga-basin"] == ["hagga_basin"]
    assert catalog["post_size"] == 1.93
    assert catalog["icons"] == {}
    assert catalog["board_image"] is None
    assert catalog["strength_tokens"] == [None, None, None, None]

    with_assets = build_catalog(
        frozenset(),
        frozenset({"troop.png", "spice.png", "not-an-icon.png"}),
        True,
        token_files=frozenset(
            {
                "strength_red.png",
                "strength_red_plus20.png",
                # A lone face does not make a token (display.token_images).
                "strength_yellow.png",
            }
        ),
    )
    assert with_assets["icons"] == {
        "troop": "/icons/troop.png",
        "spice": "/icons/spice.png",
    }
    assert with_assets["board_image"] == "/board-image"
    # One entry per seat, in seat order (seat 1 is red).
    assert with_assets["strength_tokens"] == [
        None,
        {
            "front": "/tokens/strength_red.png",
            "plus20": "/tokens/strength_red_plus20.png",
        },
        None,
        None,
    ]


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
    # The tokens are the common player disc at this board's printed size
    # (tests/unit/display/test_bene_tleilax_layout.py pins the geometry).
    assert layout["disc_size"] == 5.84
    for key in ("track_start_discs", "research_start_discs"):
        spots = layout[key]
        assert isinstance(spots, list) and len(spots) == 4
    with_scan = build_catalog(bene_tleilax_image=True)["bene_tleilax"]
    assert isinstance(with_scan, dict)
    assert with_scan["image"] == "/bene-tleilax-image"
