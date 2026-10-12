"""Fast state copies must retain the standard constructor contract."""

import dataclasses
from copy import replace
from dataclasses import InitVar, dataclass, field
from typing import Any

import pytest

from dune_imperium.config import RulesetConfig
from dune_imperium.core.dataclass_copy import positional_dataclass_replace
from dune_imperium.core.player import PlayerState, Resources
from dune_imperium.core.state import GameState, canonical_state_hash
from dune_imperium.rules.engine import UprisingRulesEngine


def test_known_state_changes_bypass_metadata_but_run_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player = PlayerState(player_id=0)
    state = GameState(config=RulesetConfig(), seed=17)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("standard metadata walk was used")

    monkeypatch.setattr(dataclasses, "_replace", forbidden)
    assert replace(player, victory_points=3).victory_points == 3
    assert replace(state, round_number=2).round_number == 2
    with pytest.raises(ValueError):
        replace(player, troops_supply=8)
    with pytest.raises(ValueError):
        replace(state, round_number=-1)


def test_complete_expansion_state_copies_match_standard_replacement() -> None:
    config = RulesetConfig(
        choam_module=True,
        promo_cards=True,
        bloodlines=True,
        tech_module=True,
        immortality=True,
        epic_game=True,
        arrakeen_scouts=True,
    )
    state = UprisingRulesEngine().reset(config, 19)
    original_hash = canonical_state_hash(state)
    variants: tuple[dict[str, Any], ...] = (
        {}, {"revision": 13, "round_number": 4}, {"seed": 31}
    )
    for changes in variants:
        fast = replace(state, **changes)
        standard = dataclasses.replace(state, **changes)
        assert fast is not state
        assert fast == standard
        assert canonical_state_hash(fast) == canonical_state_hash(standard)
        for declared in dataclasses.fields(state):
            if declared.name not in changes:
                assert getattr(fast, declared.name) is getattr(state, declared.name)
    assert canonical_state_hash(state) == original_hash
    for player in state.players:
        assert replace(player, victory_points=7) == dataclasses.replace(
            player, victory_points=7
        )


def test_public_hand_normalization_still_runs_without_mutating_input() -> None:
    original = PlayerState(player_id=0, hand=("a", "b"), hand_public=("b",))
    played = replace(original, hand=("a",), in_play=("b",))
    assert played == dataclasses.replace(original, hand=("a",), in_play=("b",))
    assert played.hand_public == ()
    assert original.hand_public == ("b",)
    assert original.hand == ("a", "b")
    assert replace(played, hand=("a", "b"), in_play=()).hand_public == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"troops_supply": 8},
        {"spies_supply": 2},
        {"agents_available": 1},
        {"hand": ("a",), "discard_pile": ("a",)},
        {"hand": ("a",), "hand_public": ("a", "a")},
    ],
)
def test_player_invariant_errors_match_standard(changes: dict[str, Any]) -> None:
    original = PlayerState(player_id=0, resources=Resources(solari=7))
    with pytest.raises(ValueError) as standard:
        dataclasses.replace(original, **changes)
    with pytest.raises(ValueError) as fast:
        replace(original, **changes)
    assert str(fast.value) == str(standard.value)
    assert original == PlayerState(player_id=0, resources=Resources(solari=7))


@pytest.mark.parametrize(
    "changes",
    [
        {"round_number": -1},
        {"reveal_order": (0, 0)},
        {"contract_bank": ("a",), "face_up_contract_ids": ("a",)},
    ],
)
def test_game_invariant_errors_match_standard(changes: dict[str, Any]) -> None:
    original = GameState(config=RulesetConfig(choam_module=True), seed=5)
    with pytest.raises(ValueError) as standard:
        dataclasses.replace(original, **changes)
    with pytest.raises(ValueError) as fast:
        replace(original, **changes)
    assert str(fast.value) == str(standard.value)


@pytest.mark.parametrize(
    "original",
    [PlayerState(player_id=0), GameState(config=RulesetConfig(), seed=5)],
)
def test_unknown_fields_are_rejected_with_the_standard_error(
    original: PlayerState | GameState,
) -> None:
    changes: dict[str, Any] = {"missing_field": 5}
    with pytest.raises(TypeError) as standard:
        dataclasses.replace(original, **changes)
    with pytest.raises(TypeError) as fast:
        replace(original, **changes)
    assert str(fast.value) == str(standard.value)


def test_subclass_uses_its_own_constructor_and_extra_fields() -> None:
    @dataclass(frozen=True)
    class TaggedPlayer(PlayerState):
        tag: str = "extra"

    original = TaggedPlayer(player_id=0, tag="retained")
    # Also exercise the base's inherited fast method explicitly: it must
    # fall back when called on a subclass instead of producing PlayerState.
    fast = PlayerState.__replace__(original, victory_points=4)
    assert type(fast) is TaggedPlayer
    assert isinstance(fast, TaggedPlayer)
    assert fast == dataclasses.replace(original, victory_points=4)
    assert fast.tag == "retained"


def test_new_declared_fields_are_copied_without_a_manual_field_list() -> None:
    @positional_dataclass_replace
    @dataclass(frozen=True, slots=True)
    class Extended:
        seed: int
        added_later: tuple[int, ...] = ()

    original = Extended(7, (3, 4))
    assert replace(original, seed=9) == dataclasses.replace(original, seed=9)
    assert replace(original, seed=9).added_later is original.added_later


def test_init_false_keeps_standard_recalculation_and_rejection() -> None:
    @positional_dataclass_replace
    @dataclass(frozen=True)
    class Derived:
        value: int
        doubled: int = field(init=False)

        def __post_init__(self) -> None:
            object.__setattr__(self, "doubled", self.value * 2)

    original = Derived(3)
    assert replace(original, value=4) == Derived(4)
    with pytest.raises(TypeError, match="init=False"):
        replace(original, doubled=10)


def test_init_vars_and_keyword_only_constructor_keep_standard_behavior() -> None:
    @positional_dataclass_replace
    @dataclass(frozen=True)
    class WithInitVar:
        value: int
        extra: InitVar[int]
        total: int = field(init=False)

        def __post_init__(self, extra: int) -> None:
            object.__setattr__(self, "total", self.value + extra)

    original = WithInitVar(2, 3)
    with pytest.raises(TypeError, match="InitVar"):
        replace(original, value=4)
    assert replace(original, value=4, extra=5).total == 9

    @positional_dataclass_replace
    @dataclass(frozen=True, kw_only=True)
    class KeywordOnly:
        value: int

    assert replace(KeywordOnly(value=2), value=3) == KeywordOnly(value=3)
