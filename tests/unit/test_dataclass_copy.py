"""Fast state copies must retain the standard constructor contract."""

import dataclasses
import inspect
import pickle
from copy import replace
from dataclasses import InitVar, dataclass, field
from enum import StrEnum
from typing import Any

import pytest

from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import DomainAction
from dune_imperium.core.dataclass_copy import (
    positional_dataclass_replace,
    slot_initializer,
)
from dune_imperium.core.decisions import (
    DecisionFrame,
    PlayerDecision,
    frame_with_dict_context,
)
from dune_imperium.core.observation import NO_IX_PENDING, IxPending, PrivatePlayerView
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
        {},
        {"revision": 13, "round_number": 4},
        {"seed": 31},
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


def test_player_copy_through_slots_runs_the_whole_constructor_check() -> None:
    # PlayerState's copy sets its slots and then runs all of __post_init__
    # (``PlayerState._check_copy``, 2026-11 engine speed): the public-hand
    # normalization and every check, as its constructor did.
    player = PlayerState(player_id=1, hand=("a", "b"), hand_public=("a", "b"))
    copied = replace(player, hand=("b",))
    assert copied.hand_public == ("b",)
    assert copied == dataclasses.replace(player, hand=("b",))
    for declared in dataclasses.fields(player):
        if declared.name not in ("hand", "hand_public"):
            assert getattr(copied, declared.name) is getattr(player, declared.name)
    with pytest.raises(ValueError, match="all 12 troops"):
        replace(player, troops_supply=player.troops_supply + 1)


def test_decision_frame_copies_keep_their_checks() -> None:
    frame = DecisionFrame(
        kind="turn",
        frame_id="turn:0",
        decision=PlayerDecision(owner=0, prompt="d"),
        context=(("a", 1),),
    )
    copied = replace(frame, context=(("a", 2), ("b", 3)))
    assert copied == dataclasses.replace(frame, context=(("a", 2), ("b", 3)))
    with pytest.raises(ValueError, match="sorted"):
        replace(frame, context=(("b", 1), ("a", 2)))


def _slotted_pair() -> tuple[type[Any], type[Any]]:
    """The same frozen slotted dataclass twice: as dataclasses builds it, and
    with ``slot_initializer``."""

    def build() -> type[Any]:
        @dataclass(frozen=True, slots=True)
        class Record:
            name: str
            items: tuple[str, ...] = ()
            count: int = 0
            mark: object = _MARK

        return Record

    return build(), slot_initializer(build())


_MARK = object()


def test_the_slot_initializer_builds_what_the_dataclass_one_builds() -> None:
    standard, fast = _slotted_pair()
    items = ("a", "b")
    calls: tuple[tuple[tuple[Any, ...], dict[str, Any]], ...] = (
        (("x",), {}),
        (("x", items), {}),
        (("x",), {"count": 3}),
        ((), {"name": "y", "items": items, "count": 4, "mark": None}),
    )
    for args, kwargs in calls:
        old, new = standard(*args, **kwargs), fast(*args, **kwargs)
        for declared in dataclasses.fields(standard):
            assert getattr(new, declared.name) is getattr(old, declared.name)
        assert replace(new, count=9).count == 9
        with pytest.raises(dataclasses.FrozenInstanceError):
            new.count = 1
    for bad_args, bad_kwargs in (((), {}), (("x",), {"name": "y"}), (("x",), {"z": 1})):
        with pytest.raises(TypeError) as old_error:
            standard(*bad_args, **bad_kwargs)
        with pytest.raises(TypeError) as new_error:
            fast(*bad_args, **bad_kwargs)
        assert str(new_error.value) == str(old_error.value)
    assert inspect.signature(fast) == inspect.signature(standard)
    assert (
        fast.__init__.__qualname__
        == "_slotted_pair.<locals>.build.<locals>.Record.__init__"
    )


def test_the_slot_initializer_runs_the_post_init_after_the_same_writes() -> None:
    """A class with a ``__post_init__`` (2026-11-11 engine speed, stage B):
    the writes, then the same ``__post_init__``, which sees every field and
    may refuse or normalise them as under the dataclass initializer."""

    def build() -> type[Any]:
        @dataclass(frozen=True, slots=True)
        class Checked:
            count: int
            items: tuple[int, ...] = ()

            def __post_init__(self) -> None:
                if self.count < 0:
                    raise ValueError(f"negative {self.items}")
                object.__setattr__(self, "items", tuple(sorted(self.items)))

        return Checked

    standard, fast = build(), slot_initializer(build())
    assert fast.__init__.__code__.co_filename.endswith(".__init__>")
    for args in ((1,), (2, (3, 1, 2)), (0, ())):
        old, new = standard(*args), fast(*args)
        assert (new.count, new.items) == (old.count, old.items)
    for bad in ((-1,), (-1, (5,))):
        with pytest.raises(ValueError) as old_error:
            standard(*bad)
        with pytest.raises(ValueError) as new_error:
            fast(*bad)
        assert str(new_error.value) == str(old_error.value)
    assert inspect.signature(fast) == inspect.signature(standard)


def test_the_slot_initializer_leaves_other_initializers_alone() -> None:
    @dataclass(frozen=True, slots=True)
    class Factory:
        items: list[int] = field(default_factory=list)

    @dataclass(frozen=True, slots=True)
    class KeywordOnly:
        count: int = field(kw_only=True)

    @dataclass(frozen=True, slots=True)
    class Derived:
        count: int
        total: int = field(init=False, default=0)

    @dataclass(frozen=True)
    class Unslotted:
        count: int

    for cls in (Factory, KeywordOnly, Derived, Unslotted):
        init = cls.__init__
        assert slot_initializer(cls) is cls
        assert cls.__init__ is init


def test_the_observation_views_use_the_slot_initializer() -> None:
    engine = UprisingRulesEngine()
    state = engine.reset(RulesetConfig(), 23)
    view = engine.observe(state, 2)
    records: tuple[Any, ...] = (view, view.private, view.players[0], NO_IX_PENDING)
    for record in records:
        cls: type[Any] = type(record)
        assert cls.__init__.__code__.co_filename.endswith(".__init__>")
        copy = cls(
            **{
                declared.name: getattr(record, declared.name)
                for declared in dataclasses.fields(cls)
            }
        )
        assert copy == record
        assert pickle.loads(pickle.dumps(record)) == record
    assert IxPending().shipping_rewards == ()
    assert PrivatePlayerView(deck_size=0, hand=(), intrigue_cards=()).ix_pending is (
        NO_IX_PENDING
    )


def test_a_subclass_constructs_through_the_dataclass_initializer() -> None:
    """Codex review r1: a subclass's own descriptor over a field sees the write,
    as under the dataclass initializer (none of the engine's records has one)."""

    class Pinned(DomainAction):
        __slots__ = ()

        @property
        def actor(self) -> int:
            return 0

    with pytest.raises(AttributeError):
        Pinned("gain", 1)

    class Plain(DomainAction):
        __slots__ = ()

    plain = Plain("gain", 1, (("count", 2),))
    assert (plain.action_id, plain.actor, plain.arguments) == (
        "gain",
        1,
        (("count", 2),),
    )


def test_a_frame_with_a_mutable_kind_is_copied_through_the_constructor() -> None:
    """Codex review r1: only an immutable kind and id keep what their checks
    found; a list kind emptied after construction fails as under master."""

    kind = ["reveal"]
    frame = DecisionFrame(kind, "f", PlayerDecision(0, "p"))  # type: ignore[arg-type]
    kind.clear()
    with pytest.raises(ValueError, match="frame kind must not be empty"):
        frame_with_dict_context(frame, {})


def test_a_frame_copy_checks_its_kind_and_id_as_the_constructor_does() -> None:
    """Codex review r2: the kind's truthiness is judged again at every copy,
    as the constructor does; only the context checks a str-named dict passes
    by construction are skipped."""

    class Flickering(StrEnum):
        ON = "on"

        def __bool__(self) -> bool:
            return _FLICKER["on"]

    _FLICKER["on"] = True
    frame = DecisionFrame(Flickering.ON, "f", PlayerDecision(0, "p"))
    _FLICKER["on"] = False
    try:
        with pytest.raises(ValueError, match="frame kind must not be empty"):
            frame_with_dict_context(frame, {"a": 1})
    finally:
        _FLICKER["on"] = True
    # Names that are not plain strings: through the constructor and its checks.
    odd = {_Late("b"): 1, _Late("a"): 2}
    built = frame_with_dict_context(frame, odd)  # type: ignore[arg-type]
    assert built == replace(frame, context=tuple(sorted(odd.items())))


_FLICKER = {"on": True}


class _Late(str):
    """A name that sorts after every other name, whatever it reads."""

    __slots__ = ()

    def __lt__(self, other: object) -> bool:
        return False


def test_a_mapping_that_poses_as_a_dict_goes_through_the_constructor() -> None:
    """Codex review r3: the exact type is read with ``type()``, which a
    ``__class__`` property cannot change."""

    class Posing(dict[str, int]):
        @property  # type: ignore[misc]
        def __class__(self) -> type:
            return dict

        def items(self) -> Any:
            return [("a", 1), ("a", 2)]

    frame = DecisionFrame("agent_effects", "f", PlayerDecision(0, "p"))
    with pytest.raises(ValueError, match="names must be unique"):
        frame_with_dict_context(frame, Posing(a=0))  # type: ignore[arg-type]


def test_the_engine_records_use_the_slot_initializer() -> None:
    from dune_imperium.adapters.action_codec import ActionTemplate
    from dune_imperium.core.decisions import ChanceDecision
    from dune_imperium.core.engine import RuleResult, Transition
    from dune_imperium.core.events import GameEvent
    from dune_imperium.rules.effect_steps import Step

    for cls in (
        DomainAction,
        GameEvent,
        PlayerDecision,
        ChanceDecision,
        DecisionFrame,
        RuleResult,
        Transition,
        Step,
        ActionTemplate,
    ):
        assert cls.__init__.__code__.co_filename.endswith(".__init__>"), cls


def test_a_hand_written_initializer_is_kept() -> None:
    """Codex review r4: only the initializer dataclasses generated, with the
    fields' own defaults, is replaced."""

    @dataclass(frozen=True, slots=True)
    class Record:
        count: int = 1

        def __init__(self, count: int = 2) -> None:
            object.__setattr__(self, "count", count)

        def __post_init__(self) -> None:
            pass

    init = Record.__init__
    assert slot_initializer(Record) is Record
    assert Record.__init__ is init
    assert Record().count == 2


def test_a_name_that_changes_the_dict_while_sorted_takes_the_constructor() -> None:
    """Codex review r4: the names checked are those of the items captured."""

    context: dict[str, int] = {}

    class Key(str):
        __slots__ = ()

        def __lt__(self, other: object) -> bool:
            context.clear()
            context["safe"] = 0
            return True

    context.update({Key("a"): 1, Key("b"): 2})
    frame = DecisionFrame("agent_effects", "f", PlayerDecision(0, "p"))
    with pytest.raises(ValueError, match="sorted by name"):
        frame_with_dict_context(frame, context)  # type: ignore[arg-type]
