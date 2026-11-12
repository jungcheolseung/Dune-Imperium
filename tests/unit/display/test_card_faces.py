"""The redrawn card faces' content (display.card_faces, docs/own-pictures-plan.md).

It is printed card-face content written in the project's own notation; the
private generator must leave nothing of the app in it, and every card the app
prints should have a face.
"""

import re

from dune_imperium.display.card_faces import (
    FACE_BOXES,
    FACE_LANGUAGES,
    INTRIGUE_TIMINGS,
    card_faces,
    conflict_faces,
    contract_faces,
    intrigue_faces,
    leader_faces,
    skill_faces,
    tech_faces,
)
from dune_imperium.display.icons import ICON_NAMES
from dune_imperium.server.catalog import build_catalog

# Pictures a face may name besides the icon set: the log's Research and
# Tleilaxu track pictures and Immortality's genetic markers.
FACE_ONLY_NAMES = frozenset(
    {
        "research",
        "tleilaxu",
        "conflict",
        "mentat",
        "flip",
        "genetic_marker_1",
        "genetic_marker_2",
        "foldspace",
        "spy_deep_cover",
    }
)
NUMBERED = frozenset({"persuasion", "solari", "spice"})


def _texts() -> list[tuple[str, str, str, str]]:
    cards = [
        (card_id, box, language, text)
        for card_id, face in card_faces().items()
        for box, texts in face.items()
        for language, text in texts.items()
    ]
    intrigue = [
        (card_id, f"part {index}", language, part[language])
        for card_id, face in intrigue_faces().items()
        for index, part in enumerate(face["parts"])
        for language in FACE_LANGUAGES
        if language in part
    ]
    conflicts = [
        (card_id, f"reward {index}", language, reward[language])
        for card_id, face in conflict_faces().items()
        for index, reward in enumerate(face["rewards"])
        for language in FACE_LANGUAGES
        if language in reward
    ]
    contracts = []
    for card_id, face in contract_faces().items():
        for box in ("condition", "reward"):
            texts = face[box]
            assert isinstance(texts, dict), (card_id, box)
            contracts += [
                (card_id, box, language, str(text)) for language, text in texts.items()
            ]
    tech = [
        (card_id, box, language, text)
        for card_id, face in tech_faces().items()
        for box in ("strip", "body")
        for language, text in face[box].items()
    ]
    leaders = []
    for card_id, leader in leader_faces().items():
        boxes = [*leader["abilities"], leader["signet"]]
        for index, box in enumerate(boxes):
            for part in ("title", "text"):
                leaders += [
                    (card_id, f"{part} {index}", language, text)
                    for language, text in box[part].items()
                ]
        for index, cell in enumerate(leader.get("track", {}).get("cells", [])):
            leaders.append((card_id, f"track {index}", "en", cell["en"]))
    skills = [
        (skill_id, "body", language, text)
        for skill_id, face in skill_faces().items()
        for language, text in face["body"].items()
    ]
    return cards + intrigue + conflicts + contracts + tech + leaders + skills


def test_faces_belong_to_catalog_cards_in_known_boxes_and_languages() -> None:
    cards = build_catalog()["cards"]
    assert isinstance(cards, dict)
    for card_id, face in card_faces().items():
        assert card_id in cards, card_id
        assert set(face) <= set(FACE_BOXES), card_id
        for box, texts in face.items():
            assert "en" in texts, (card_id, box)
            assert set(texts) <= set(FACE_LANGUAGES), (card_id, box)


def test_a_korean_face_has_every_box_in_korean() -> None:
    for card_id, face in card_faces().items():
        korean = {box for box, texts in face.items() if "ko" in texts}
        assert korean in (set(), set(face)), card_id


def test_faces_name_only_our_icons_and_keep_only_printed_emphasis() -> None:
    known = set(ICON_NAMES) | FACE_ONLY_NAMES
    for card_id, box, language, text in _texts():
        where = (card_id, box, language)
        assert "sprite" not in text.lower() and "UI_" not in text, where
        for name, number in re.findall(r"\{([a-z_0-9]+)(?::(\d+\+?))?\}", text):
            assert name in known, (where, name)
            assert not number or name in NUMBERED, (where, name)
        emphasis = set(re.findall(r"<[^>]*>", text))
        assert emphasis <= {"<i>", "</i>", "<b>", "</b>"}, where
        assert "{" not in re.sub(r"\{[a-z_0-9]+(?::\d+\+?)?\}", "", text), where


def test_every_card_has_a_face() -> None:
    cards = build_catalog()["cards"]
    assert isinstance(cards, dict)
    assert not set(cards) - set(card_faces())


def test_catalog_cards_carry_their_face() -> None:
    cards = build_catalog()["cards"]
    assert isinstance(cards, dict)
    guild_spy = cards["guild_spy"]
    assert isinstance(guild_spy, dict)
    face = guild_spy["face"]
    assert face == card_faces()["guild_spy"]
    assert isinstance(face, dict)
    agent = face["agent"]
    assert isinstance(agent, dict)
    assert "{discard} {arrow_right} {draw}" in str(agent["en"])


def test_intrigue_parts_have_timings_and_whole_korean() -> None:
    intrigue = build_catalog()["intrigue"]
    assert isinstance(intrigue, dict)
    for card_id, face in intrigue_faces().items():
        assert card_id in intrigue, card_id
        parts = face["parts"]
        assert parts, card_id
        assert all(part["timing"] in INTRIGUE_TIMINGS for part in parts), card_id
        assert all(part["en"] for part in parts), card_id
        korean = {("ko" in part) for part in parts}
        assert len(korean) == 1, card_id


def test_every_intrigue_card_has_a_face() -> None:
    intrigue = build_catalog()["intrigue"]
    assert isinstance(intrigue, dict)
    assert not set(intrigue) - set(intrigue_faces())


def test_navigation_faces_are_navigation_parts_with_korean() -> None:
    faces = {
        card_id: face
        for card_id, face in intrigue_faces().items()
        if card_id.startswith("navigation_card_")
    }
    assert len(faces) == 10
    for card_id, face in faces.items():
        assert face["parts"], card_id
        for part in face["parts"]:
            assert part["timing"] == "navigation", card_id
            assert part["en"] and part["ko"], card_id


def test_every_conflict_and_contract_has_a_face() -> None:
    catalog = build_catalog()
    conflicts, contracts = catalog["conflicts"], catalog["contracts"]
    assert isinstance(conflicts, dict) and isinstance(contracts, dict)
    assert set(conflicts) == set(conflict_faces())
    assert set(contracts) == set(contract_faces())
    for card_id, face in conflict_faces().items():
        assert len(face["rewards"]) == 3, card_id
        assert {("ko" in reward) for reward in face["rewards"]} in ({True}, {False})
    for card_id, contract in contract_faces().items():
        assert contract["tile"], card_id
        # Only a tile with no condition frame (Immediate) has no frame kind.
        condition = contract["condition"]
        assert isinstance(condition, dict)
        assert contract["frame"] or not condition["en"], card_id
        title = contract["title"]
        assert isinstance(title, dict) and title["en"], card_id
        # The tile prints the name alone (no copy number, no threshold).
        assert not re.search(r"\s(?:[IVX]+|\d\+)$", str(title["en"])), card_id


def test_every_tech_tile_has_a_face() -> None:
    tech = build_catalog()["tech"]
    assert isinstance(tech, dict)
    assert set(tech) == set(tech_faces())
    for card_id, face in tech_faces().items():
        assert set(face) - {"tone"} == {"strip", "body"}, card_id
        assert face.get("tone", "bloodlines") == "bloodlines", card_id
        body, strip = face["body"], face["strip"]
        assert isinstance(body, dict) and isinstance(strip, dict), card_id
        assert ("ko" in body) == ("ko" in strip), card_id


def test_every_leader_face_has_a_face_with_whole_korean() -> None:
    leaders = build_catalog()["leaders"]
    assert isinstance(leaders, dict)
    assert set(leaders) == set(leader_faces())
    for face_id, face in leader_faces().items():
        assert face["pips"] in (1, 2, 3, 4), face_id
        assert face.get("mark") in (None, "choam", "tech"), face_id
        boxes = [*face["abilities"], face["signet"]]
        assert 1 <= len(face["abilities"]) <= 2, face_id
        assert all(box["title"]["en"] and box["text"]["en"] for box in boxes), face_id
        # Korean on every box, or on none (Steersman Y'rkoon's two abilities
        # and Staban Tuek's Limited Allies included).
        korean = {("ko" in box["title"]) and ("ko" in box["text"]) for box in boxes}
        assert len(korean) == 1, face_id
        assert "ko" not in face.get("house", {}) or korean == {True}, face_id


def test_leader_tracks_match_the_token_spaces() -> None:
    """The face draws a cell for every space the token can stand on."""

    from dune_imperium.content.uprising.leaders import FEYD_TRAINING_TRACK
    from dune_imperium.rules.tactics import TACTICS_TRACK_END

    feyd = leader_faces()["feyd_rautha_harkonnen"]["track"]
    assert feyd["kind"] == "feyd"
    assert [cell["space"] for cell in feyd["cells"]] == [
        space.space_id for space in FEYD_TRAINING_TRACK
    ]
    chani = leader_faces()["chani"]["track"]
    assert [cell["space"] for cell in chani["cells"]] == list(
        range(TACTICS_TRACK_END + 1)
    )


def test_every_skill_tile_has_a_face_in_both_languages() -> None:
    """The seven Sardaukar Commander Skill tiles (Bloodlines) are drawn from
    what they print; the Korean comes from the official Korean tiles."""
    skills = build_catalog()["skills"]
    assert isinstance(skills, dict)
    assert set(skills) == set(skill_faces())
    for skill_id, face in skill_faces().items():
        assert face["kind"] == "skill", skill_id
        assert set(face["body"]) == {"en", "ko"}, skill_id
        entry = skills[skill_id]
        assert isinstance(entry, dict) and entry["face"] == face, skill_id



def test_every_objective_card_has_a_face_in_both_languages() -> None:
    """Uprising's Objective cards print one line under their battle icon
    [Objective cards]; the public build draws them from it."""

    from dune_imperium.display.card_faces import objective_faces

    objectives = build_catalog()["objectives"]
    assert isinstance(objectives, dict)
    faces = objective_faces()
    assert set(faces) == set(objectives)
    for face in faces.values():
        assert face["kind"] == "objective"
        assert face["text"]["en"] and face["text"]["ko"]
    assert faces["objective_desert_mouse"].get("first_player") is True
    assert faces["objective_ornithopter_1_3p"].get("players") == "1-3P"
