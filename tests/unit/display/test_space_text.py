"""Tests for board-space display text."""

import pytest

from dune_imperium.content.uprising.board import BOARD_SPACES
from dune_imperium.display.spaces import (
    automatic_effect_texts,
    space_is_implemented,
    space_notes,
    space_option_count,
    space_option_effects,
)
from dune_imperium.rules.board_effects import (
    CHOICE_DRIVEN_SPACE_IDS,
    static_board_effects,
)


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
    assert base_hidden == {
        "secrets",
        "desert_tactics",
        "imperial_privilege",
        "shipping",
    }
    assert choam_hidden == base_hidden | {"dutiful_service"}


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
