"""Tests for board-space display text."""

import sys
from pathlib import Path

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import BOARD_SPACES, BOARD_SPACES_BY_ID
from dune_imperium.content.uprising.starting_cards import starting_deck_instance_ids
from dune_imperium.core import (
    DecisionFrame,
    DomainAction,
    GamePhase,
    GameState,
    PlayerDecision,
    PlayerState,
)
from dune_imperium.display.spaces import (
    _AUTHORED_OPTION_EFFECTS,
    _AUTHORED_OPTION_EFFECTS_KO,
    _ICON_TEXTS,
    _ICON_TEXTS_KO,
    SPACE_NOTES,
    SPACE_NOTES_KO,
    automatic_effect_texts,
    automatic_effect_texts_ko,
    board_effect_action_text,
    board_effect_action_text_ko,
    board_icon_text,
    board_icon_text_ko,
    space_is_implemented,
    space_notes,
    space_notes_ko,
    space_option_count,
    space_option_effects,
    space_option_effects_ko,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    CHOICE_DRIVEN_SPACE_IDS,
    HIGH_COUNCIL_REVISIT_EFFECTS,
    legal_board_effect_actions,
    static_board_effects,
)

# tests/support isn't a package pytest or mypy resolve from a dotted import
# (see tests/unit/display/test_struct_text.py's identical comment).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "support"))
from ko_text import (  # type: ignore[import-not-found]  # noqa: E402
    assert_no_stray_latin,
    assert_no_summon_for_sandworm,
    assert_placeholders_are_terms,
    assert_trash_and_discard_match,
    terms_keys,
)

# Every board space's own English name may appear, untranslated, inside a
# Korean effect/note line (glossary "공간 이름" row). Esmar Tuek (the
# leader tuek_sietch's flavor line names) has a confirmed Korean-print
# transcription in names_ko.py and is rendered from it, so it is not an
# allowed-Latin exception here.
_SPACE_NAMES = frozenset(space.name for space in BOARD_SPACES_BY_ID.values())
_ALLOWED_LATIN = _SPACE_NAMES


@pytest.mark.parametrize("choam_module", (False, True))
def test_every_space_option_renders_non_empty_text(choam_module: bool) -> None:
    for space in BOARD_SPACES:
        effects = space_option_effects(
            space.space_id,
            choam_module=choam_module,
        )
        assert len(effects) == space_option_count(space.space_id)
        assert all(effects), space.space_id


def test_implemented_flags_mirror_the_engine_gate() -> None:
    base_hidden = {
        space.space_id
        for space in BOARD_SPACES
        if not space_is_implemented(space.space_id, choam_module=False)
    }
    choam_hidden = {
        space.space_id
        for space in BOARD_SPACES
        if not space_is_implemented(space.space_id, choam_module=True)
    }
    assert base_hidden == set()
    assert choam_hidden == base_hidden


def test_automatic_text_derives_from_the_engine_effect_table() -> None:
    for choam_module in (False, True):
        for space in BOARD_SPACES:
            if space.space_id in CHOICE_DRIVEN_SPACE_IDS:
                continue
            for option in range(space_option_count(space.space_id)):
                try:
                    effects = static_board_effects(
                        space.space_id,
                        option,
                        choam_module=choam_module,
                    )
                except NotImplementedError:
                    continue
                text = space_option_effects(
                    space.space_id,
                    choam_module=choam_module,
                )[option]
                for effect in effects:
                    for fragment in automatic_effect_texts(effect):
                        assert fragment in text, (
                            space.space_id,
                            option,
                            choam_module,
                            fragment,
                        )


def test_simple_space_goldens() -> None:
    assert space_option_effects("sardaukar", choam_module=False) == (
        "Gain 1 Emperor Influence, Draw 1 Intrigue card, Recruit 4 troops",
    )
    assert space_option_effects("gather_support", choam_module=False) == (
        "Recruit 2 troops",
        "Recruit 2 troops, Gain 1 water",
    )
    assert space_option_effects("accept_contract", choam_module=False) == (
        "Draw 1 card, Gain 2 solari",
    )
    assert space_option_effects("accept_contract", choam_module=True) == (
        "Draw 1 card. Take a face-up Contract"
        " (Gain 2 solari if none is available)",
    )


def test_the_research_station_overlay_text_follows_the_immortality_table() -> None:
    # "Draw two cards and research" [Immortality pp. 5, 16]: the overlay
    # replaces the printed troops with Research, and only there.
    assert space_option_effects("research_station", choam_module=False) == (
        "Recruit 2 troops, Draw 2 cards",
    )
    assert space_option_effects(
        "research_station", choam_module=False, immortality=True
    ) == ("Draw 2 cards, Research (advance your research token)",)
    from dune_imperium.content.uprising.board import BOARD_SPACES

    differing = [
        space.space_id
        for space in BOARD_SPACES
        if space_option_effects(space.space_id, choam_module=False, immortality=True)
        != space_option_effects(space.space_id, choam_module=False)
    ]
    assert differing == ["research_station"]
    # No space differs under both modules, so the client needs no combined
    # CHOAM + Immortality variant.
    for space_id in differing:
        assert space_option_effects(
            space_id, choam_module=True
        ) == space_option_effects(space_id, choam_module=False)


def test_faction_influence_appears_only_on_faction_icon_spaces() -> None:
    for choam_module in (False, True):
        for space in BOARD_SPACES:
            text = " ".join(
                space_option_effects(
                    space.space_id,
                    choam_module=choam_module,
                )
            )
            has_visit_influence = (
                "Gain 1 Emperor Influence" in text
                or "Gain 1 Spacing Guild Influence" in text
                or "Gain 1 Bene Gesserit Influence" in text
                or "Gain 1 Fremen Influence" in text
            )
            assert has_visit_influence == (space.faction is not None), (
                space.space_id
            )


def test_board_icon_text_reads_amounts_from_the_visit_effects() -> None:
    research = static_board_effects("research_station", 0, choam_module=False)
    assert board_icon_text("troops", research) == "Recruit 2 troops"
    assert board_icon_text("cards", research) == "Draw 2 cards"
    assert board_icon_text("resources", HIGH_COUNCIL_REVISIT_EFFECTS) == (
        "Gain 2 spice"
    )
    assert board_icon_text("intrigue", HIGH_COUNCIL_REVISIT_EFFECTS) == (
        "Draw 1 Intrigue card"
    )
    assert board_icon_text("contract", ()) == (
        "Take a face-up Contract (Gain 2 solari if none is available)"
    )
    assert board_icon_text("high_council", ()).startswith("Seat your Councilor")
    assert board_icon_text("swordmaster", ()).startswith("Take your third Agent")
    with pytest.raises(KeyError):
        board_icon_text("maker", ())


def test_board_effect_action_text_names_the_icon_of_the_current_visit() -> None:
    reconnaissance = next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if ":reconnaissance:" in instance_id
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        players=(
            PlayerState(player_id=0, hand=(reconnaissance,)),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    to_arrakeen = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = apply_agent_action(state, to_arrakeen).state
    actions = legal_board_effect_actions(placed, 0)

    assert [board_effect_action_text(placed, action) for action in actions] == [
        "Recruit 1 troop",
        "Draw 1 card",
    ]
    other = DomainAction(action_id="resolve_faction_influence", actor=0)
    assert board_effect_action_text(placed, other) is None
    # Outside an Agent-turn effect frame there is no visit to describe.
    assert board_effect_action_text(state, actions[0]) is None


def test_notes_cover_the_persuasion_and_control_passives() -> None:
    noted = {
        space.space_id for space in BOARD_SPACES if space_notes(space.space_id)
    }
    assert noted == {
        "assembly_hall",
        "arrakeen",
        "spice_refinery",
        "imperial_basin",
    }
    assert "Persuasion" in space_notes("assembly_hall")[0]
    assert "controller" in space_notes("imperial_basin")[0]


# ---------- Korean twins (Step K4, 2026-09-25) ----------


def test_authored_ko_tables_cover_the_same_keys_as_english() -> None:
    assert set(_AUTHORED_OPTION_EFFECTS_KO) == set(_AUTHORED_OPTION_EFFECTS)
    for key, english in _AUTHORED_OPTION_EFFECTS.items():
        assert len(_AUTHORED_OPTION_EFFECTS_KO[key]) == len(english), key
    assert set(SPACE_NOTES_KO) == set(SPACE_NOTES)
    for space_id, english in SPACE_NOTES.items():
        assert len(SPACE_NOTES_KO[space_id]) == len(english), space_id
    assert set(_ICON_TEXTS_KO) == set(_ICON_TEXTS)


@pytest.mark.parametrize("choam_module", (False, True))
def test_every_space_option_ko_renders_valid_korean(choam_module: bool) -> None:
    terms = terms_keys()
    for space in BOARD_SPACES:
        effects = space_option_effects(space.space_id, choam_module=choam_module)
        effects_ko = space_option_effects_ko(space.space_id, choam_module=choam_module)
        assert len(effects_ko) == len(effects) == space_option_count(space.space_id)
        for english, korean in zip(effects, effects_ko, strict=True):
            assert isinstance(korean, str) and korean.strip(), space.space_id
            assert_placeholders_are_terms(korean, terms)
            assert_no_stray_latin(korean, _ALLOWED_LATIN)
            assert_trash_and_discard_match(english, korean)
            assert_no_summon_for_sandworm(english, korean)


def test_the_research_station_overlay_text_ko_follows_the_immortality_table() -> None:
    assert space_option_effects_ko("research_station", choam_module=False) == (
        "{troop:2}, {draw:2}",
    )
    assert space_option_effects_ko(
        "research_station", choam_module=False, immortality=True
    ) == ("{draw:2}, {research} (연구 토큰 전진)",)


def test_faction_influence_ko_appears_only_on_faction_icon_spaces() -> None:
    for choam_module in (False, True):
        for space in BOARD_SPACES:
            text = " ".join(
                space_option_effects_ko(space.space_id, choam_module=choam_module)
            )
            has_visit_influence = (
                "{influence_emperor:1}" in text
                or "{influence_spacing_guild:1}" in text
                or "{influence_bene_gesserit:1}" in text
                or "{influence_fremen:1}" in text
            )
            assert has_visit_influence == (space.faction is not None), (
                space.space_id
            )


def test_automatic_text_ko_derives_from_the_engine_effect_table() -> None:
    for choam_module in (False, True):
        for space in BOARD_SPACES:
            if space.space_id in CHOICE_DRIVEN_SPACE_IDS:
                continue
            for option in range(space_option_count(space.space_id)):
                try:
                    effects = static_board_effects(
                        space.space_id,
                        option,
                        choam_module=choam_module,
                    )
                except NotImplementedError:
                    continue
                text = space_option_effects_ko(
                    space.space_id,
                    choam_module=choam_module,
                )[option]
                for effect in effects:
                    for fragment in automatic_effect_texts_ko(effect):
                        assert fragment in text, (
                            space.space_id,
                            option,
                            choam_module,
                            fragment,
                        )


def test_simple_space_goldens_ko() -> None:
    assert space_option_effects_ko("sardaukar", choam_module=False) == (
        "{influence_emperor:1}, {intrigue:1}, {troop:4}",
    )
    assert space_option_effects_ko("gather_support", choam_module=False) == (
        "{troop:2}",
        "{troop:2}, {water:1}",
    )
    assert space_option_effects_ko("accept_contract", choam_module=False) == (
        "{draw:1}, {solari:2}",
    )
    assert space_option_effects_ko("accept_contract", choam_module=True) == (
        "{draw:1}. {contract} 가져옴 (없으면 {solari:2})",
    )


def test_board_icon_text_ko_reads_amounts_from_the_visit_effects() -> None:
    research = static_board_effects("research_station", 0, choam_module=False)
    assert board_icon_text_ko("troops", research) == "{troop:2}"
    assert board_icon_text_ko("cards", research) == "{draw:2}"
    assert board_icon_text_ko("resources", HIGH_COUNCIL_REVISIT_EFFECTS) == (
        "{spice:2}"
    )
    assert board_icon_text_ko("intrigue", HIGH_COUNCIL_REVISIT_EFFECTS) == (
        "{intrigue:1}"
    )
    assert board_icon_text_ko("contract", ()) == (
        "{contract} 가져옴 (없으면 {solari:2})"
    )
    assert "원로회" in board_icon_text_ko("high_council", ())
    assert board_icon_text_ko("swordmaster", ()).startswith("세 번째 {agent}")
    with pytest.raises(KeyError):
        board_icon_text_ko("maker", ())


def test_board_effect_action_text_ko_names_the_icon_of_the_current_visit() -> None:
    reconnaissance = next(
        instance_id
        for instance_id in starting_deck_instance_ids(0)
        if ":reconnaissance:" in instance_id
    )
    state = GameState(
        config=RulesetConfig(),
        seed=1,
        phase=GamePhase.PLAYER_TURNS,
        players=(
            PlayerState(player_id=0, hand=(reconnaissance,)),
            *(PlayerState(player_id=seat) for seat in range(1, 4)),
        ),
        decision_stack=(
            DecisionFrame(
                kind="turn",
                frame_id="round:1:turn:0",
                decision=PlayerDecision(owner=0, prompt="Choose a turn"),
            ),
        ),
    )
    to_arrakeen = next(
        action
        for action in legal_agent_actions(state, 0)
        if dict(action.arguments)["space_id"] == "arrakeen"
    )
    placed = apply_agent_action(state, to_arrakeen).state
    actions = legal_board_effect_actions(placed, 0)

    assert [
        board_effect_action_text_ko(placed, action) for action in actions
    ] == ["{troop:1}", "{draw:1}"]
    other = DomainAction(action_id="resolve_faction_influence", actor=0)
    assert board_effect_action_text_ko(placed, other) is None
    # Outside an Agent-turn effect frame there is no visit to describe.
    assert board_effect_action_text_ko(state, actions[0]) is None


def test_notes_ko_cover_the_same_spaces_as_english() -> None:
    terms = terms_keys()
    noted = {
        space.space_id for space in BOARD_SPACES if space_notes_ko(space.space_id)
    }
    assert noted == {
        space.space_id for space in BOARD_SPACES if space_notes(space.space_id)
    }
    for space in BOARD_SPACES:
        for english, korean in zip(
            space_notes(space.space_id), space_notes_ko(space.space_id), strict=True
        ):
            assert isinstance(korean, str) and korean.strip(), space.space_id
            assert_placeholders_are_terms(korean, terms)
            assert_no_stray_latin(korean, _ALLOWED_LATIN)
            assert_trash_and_discard_match(english, korean)
    assert "{persuasion:1}" in space_notes_ko("assembly_hall")[0]
    assert "지배권을 가진 플레이어" in space_notes_ko("imperial_basin")[0]
