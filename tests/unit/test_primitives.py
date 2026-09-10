"""Validation tests for serializable engine primitives."""

from collections.abc import Callable

import pytest

from dune_imperium import RulesetConfig
from dune_imperium.core import DecisionFrame, DomainAction, GameState, PlayerDecision
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import canonical_state_hash


def test_action_arguments_require_a_canonical_order() -> None:
    with pytest.raises(ValueError, match="sorted"):
        DomainAction(
            action_id="choose",
            actor=0,
            arguments=(("z", 1), ("a", 2)),
        )


def test_decision_stack_is_last_in_first_out() -> None:
    first = DecisionFrame("test", "first", PlayerDecision(0, "First"))
    second = DecisionFrame("test", "second", PlayerDecision(1, "Second"))
    state = GameState(config=RulesetConfig(), seed=1)

    stacked = state.push_decision(first).push_decision(second)

    assert stacked.decision_stack[-1] == second
    assert stacked.pop_decision().decision_stack[-1] == first
    assert state.decision_stack == ()


def test_state_hash_changes_with_replay_relevant_state() -> None:
    state = GameState(config=RulesetConfig(), seed=1)

    assert canonical_state_hash(state) != canonical_state_hash(
        GameState(config=RulesetConfig(), seed=2)
    )


def test_decision_frame_requires_kind() -> None:
    with pytest.raises(ValueError, match="frame kind"):
        DecisionFrame("", "frame", PlayerDecision(0, "Prompt"))


def test_player_state_forgets_public_hand_cards_that_leave_the_hand() -> None:
    from dataclasses import replace

    from dune_imperium.core import PlayerState

    player = PlayerState(player_id=0, hand=("a", "b"), hand_public=("b",))
    assert player.hand_public == ("b",)

    played = replace(player, hand=("a",))
    assert played.hand_public == ()
    # Drawing the same card again face down does not make it public.
    redrawn = replace(played, hand=("a", "b"))
    assert redrawn.hand_public == ()

    with pytest.raises(ValueError, match="publicly known twice"):
        PlayerState(player_id=0, hand=("a",), hand_public=("a", "a"))


# Each module's zones are only scanned for duplicates when the module is on;
# with it off the state must instead hold nothing at all. Both halves of that
# gate are pinned here, because a copy of the state runs these checks several
# times per engine step and the cheap half is the one a base game takes.
_MODULE_ZONES: tuple[
    tuple[
        RulesetConfig,
        Callable[[RulesetConfig], GameState],
        Callable[[RulesetConfig], GameState],
        str,
        str,
    ],
    ...,
] = (
    (
        RulesetConfig(choam_module=True),
        lambda config: GameState(config=config, seed=1, contract_bank=("choam_a",)),
        lambda config: GameState(
            config=config,
            seed=1,
            contract_bank=("choam_a",),
            face_up_contract_ids=("choam_a",),
        ),
        "Contracts require the CHOAM Module",
        "a Contract cannot occupy two zones",
    ),
    (
        RulesetConfig(bloodlines=True),
        lambda config: GameState(config=config, seed=1, skill_stack=("skill_a",)),
        lambda config: GameState(
            config=config,
            seed=1,
            skill_stack=("skill_a",),
            skill_face_up=("skill_a",),
        ),
        "Sardaukar Commanders require the Bloodlines expansion",
        "a Skill tile cannot occupy two zones",
    ),
    (
        RulesetConfig(bloodlines=True, tech_module=True),
        lambda config: GameState(config=config, seed=1, tech_trash=("tech_a",)),
        lambda config: GameState(
            config=config,
            seed=1,
            tech_stacks=(("tech_a",),),
            tech_trash=("tech_a",),
        ),
        "Tech tiles require the Tech Module",
        "a Tech tile cannot occupy two zones",
    ),
    (
        RulesetConfig(immortality=True),
        lambda config: GameState(config=config, seed=1, tleilaxu_deck=("tleilaxu_a",)),
        lambda config: GameState(
            config=config,
            seed=1,
            tleilaxu_deck=("tleilaxu_a",),
            tleilaxu_row=("tleilaxu_a",),
        ),
        "the Bene Tleilax board requires Immortality",
        "a Tleilaxu card cannot occupy two zones",
    ),
)


@pytest.mark.parametrize(
    ("enabled", "content", "duplicate", "off_message", "on_message"),
    _MODULE_ZONES,
    ids=[row[3].split()[0] for row in _MODULE_ZONES],
)
def test_module_zones_are_rejected_when_off_and_deduplicated_when_on(
    enabled: RulesetConfig,
    content: Callable[[RulesetConfig], GameState],
    duplicate: Callable[[RulesetConfig], GameState],
    off_message: str,
    on_message: str,
) -> None:
    with pytest.raises(ValueError, match=off_message):
        content(RulesetConfig())

    with pytest.raises(ValueError, match=on_message):
        duplicate(enabled)

    # The same contents are legal once the module is on and nothing repeats.
    content(enabled)


def test_a_flipped_tech_tile_must_be_a_held_tile_even_with_none_held() -> None:
    with pytest.raises(ValueError, match="flipped Tech tiles must be held tiles"):
        PlayerState(player_id=0, tech_flipped=("tech_a",))
