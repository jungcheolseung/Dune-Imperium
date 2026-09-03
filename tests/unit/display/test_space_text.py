"""Tests for board-space display text."""

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.content.uprising.board import BOARD_SPACES
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
    automatic_effect_texts,
    board_effect_action_text,
    board_icon_text,
    space_is_implemented,
    space_notes,
    space_option_count,
    space_option_effects,
)
from dune_imperium.rules.agent_turn import apply_agent_action, legal_agent_actions
from dune_imperium.rules.board_effects import (
    CHOICE_DRIVEN_SPACE_IDS,
    HIGH_COUNCIL_REVISIT_EFFECTS,
    legal_board_effect_actions,
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
