"""Tests for Leader ability display text."""

from dune_imperium.content.uprising.leaders import LEADERS
from dune_imperium.display.leaders import LEADER_FACE_TEXTS


def test_every_printed_leader_face_has_text() -> None:
    face_ids = {leader.leader_id for leader in LEADERS} | {
        leader.alternate_face_id
        for leader in LEADERS
        if leader.alternate_face_id is not None
    }
    assert set(LEADER_FACE_TEXTS) == face_ids


def test_face_texts_are_non_empty() -> None:
    for face_id, text in LEADER_FACE_TEXTS.items():
        assert text.ability_text, face_id
        assert text.signet_text, face_id


def test_four_player_ability_values() -> None:
    gurney = LEADER_FACE_TEXTS["gurney_halleck"]
    assert "6 or more strength" in gurney.ability_text
    staban = LEADER_FACE_TEXTS["staban_tuek"]
    assert any("Diplomacy" in note for note in staban.notes)
