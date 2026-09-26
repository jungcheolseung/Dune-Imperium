"""Tests for Leader ability display text."""

import sys
from pathlib import Path

from dune_imperium.content.uprising.leaders import LEADERS
from dune_imperium.display.leaders import LEADER_FACE_TEXTS
from dune_imperium.display.leaders_ko import LEADER_FACE_TEXTS_KO

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/unit/display/test_struct_text.py's identical comment).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from ko_text import (  # type: ignore[import-not-found]  # noqa: E402
    assert_no_stray_latin,
    assert_placeholders_are_terms,
    assert_trash_and_discard_match,
    terms_keys,
)


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


# ---------- Korean twin (Step K5, 2026-09-25) ----------


def test_every_scanned_leader_face_has_korean_text() -> None:
    """Every face with a Korean scan has all four Korean fields.

    ``reverend_mother_jessica`` has no Korean scan (leaders-ko.md:
    "cards/ko/uprising/leader/ holds only 'Lady Jessica.webp'") and is the
    one printed face missing here; the catalog keeps her English.
    """

    face_ids = set(LEADER_FACE_TEXTS)
    assert set(LEADER_FACE_TEXTS_KO) == face_ids - {"reverend_mother_jessica"}
    for face_id, text in LEADER_FACE_TEXTS_KO.items():
        assert text.ability_name, face_id
        assert text.ability_text, face_id
        assert text.signet_name, face_id
        assert text.signet_text, face_id


def test_korean_leader_text_is_valid_korean() -> None:
    terms = terms_keys()
    for face_id, text in LEADER_FACE_TEXTS_KO.items():
        values = (
            text.ability_name,
            text.ability_text,
            text.signet_name,
            text.signet_text,
        )
        for value in values:
            assert_placeholders_are_terms(value, terms)
            assert_no_stray_latin(value)
        for note in text.notes:
            assert_placeholders_are_terms(note, terms)
            assert_no_stray_latin(note)
        english = LEADER_FACE_TEXTS[face_id]
        assert_trash_and_discard_match(english.ability_text, text.ability_text)
        assert_trash_and_discard_match(english.signet_text, text.signet_text)
        # display/leaders_ko.py's notes are a positional twin of the
        # English's, exactly like every other catalog notes/notes_ko pair
        # (server/static/core.js's popoverNodes zips them by index).
        assert len(text.notes) == len(english.notes), face_id


def test_staban_notes_ko_mirrors_the_limited_allies_note() -> None:
    staban = LEADER_FACE_TEXTS_KO["staban_tuek"]
    assert any("외교" in note for note in staban.notes)


def test_liet_kynes_ability_keeps_the_printed_summon_word() -> None:
    """The print's own word for summoning a sandworm is "소환" here, not

    ``docs/rules/glossary-ko.md``'s 부르다 (reserved for Agent/Spy recall):
    a deliberate exception to that policy for a *printed* Leader
    transcription (leaders_ko.py's own docstring), unlike every
    engine-*generated* Korean line elsewhere, which must never use 소환 for
    a sandworm (``ko_text.assert_no_summon_for_sandworm``).
    """

    liet = LEADER_FACE_TEXTS_KO["liet_kynes"]
    assert "모래벌레를 소환" in liet.ability_text


def test_chani_signet_ko_keeps_the_printed_draw_icons() -> None:
    """The Korean print shows two draw-card icons, not troops, for Chani's

    Signet Ring reward (leaders-ko.md finding 1) — kept faithful to the
    print, which now agrees with both the English display text
    ("Draw 2 cards") and the engine (rules/leader_abilities.py's
    ``_apply_chani_water_payment``): both were corrected to match this
    Korean transcription's earlier finding.
    """

    chani = LEADER_FACE_TEXTS_KO["chani"]
    assert "{draw}{draw}" in chani.signet_text
    assert "troop" not in chani.signet_text.lower()


def test_fenring_signet_ko_marks_the_deep_cover_spy() -> None:
    fenring = LEADER_FACE_TEXTS_KO["count_hasimir_fenring"]
    assert "{spy} (잠복 스파이)" in fenring.signet_text
