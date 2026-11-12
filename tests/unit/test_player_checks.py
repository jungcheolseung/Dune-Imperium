"""The PlayerState invariants' field table (``core.player.PLAYER_CHECKS``).

A copy runs only the checks whose fields it replaced, and the public-hand
normalization only when it replaced the hand (``PlayerState._check_copy``,
2026-11-11 engine speed, stage B). So each row must name exactly the fields
its check reads: the tests read every check's source for its ``self.<field>``
reads, read every check through a recording proxy over real seats, break
each check through a copy and expect the constructor's own error, and count
the checks a copy runs.
"""

import ast
import dataclasses
import functools
import inspect
import textwrap
from collections import OrderedDict as _OrderedDict
from copy import replace
from typing import Any

import pytest
from tests.unit.rules.test_kept_answers import FULL, IMPERIUM_IX, played_states

from dune_imperium.core import player as player_module
from dune_imperium.core import state as state_module
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import (
    DecisionFrame,
    PlayerDecision,
    frame_with_dict_context,
)
from dune_imperium.core.player import (
    NORMALIZED_FIELDS,
    PLAYER_CHECKS,
    PlayerCheck,
    PlayerState,
    _normalize_hand_public,
)

SEAT_FIELDS = frozenset(field.name for field in dataclasses.fields(PlayerState))


def _self_reads(function: Any) -> set[str]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }


@pytest.mark.parametrize("check", PLAYER_CHECKS, ids=lambda c: c.check.__name__)
def test_a_rows_fields_are_the_fields_its_check_reads(check: PlayerCheck) -> None:
    assert _self_reads(check.check) == check.fields
    assert check.fields <= SEAT_FIELDS


def test_the_normalization_reads_the_hand_and_its_public_cards() -> None:
    assert _self_reads(_normalize_hand_public) == NORMALIZED_FIELDS


class _Reads:
    __slots__ = ("_player", "_seen")

    def __init__(self, player: PlayerState, seen: set[str]) -> None:
        self._player = player
        self._seen = seen

    def __getattr__(self, name: str) -> Any:
        self._seen.add(name)
        return getattr(self._player, name)


@functools.cache
def _played_seats() -> tuple[PlayerState, ...]:
    seats: list[PlayerState] = []
    for config, seed in ((FULL, 31), (IMPERIUM_IX, 32)):
        for step, state in enumerate(played_states(config, seed, 1200)):
            if step % 7 == 0:
                seats.extend(state.players)
    return tuple(seats)


def _seats() -> list[PlayerState]:
    """Every seventh state's seats of two seeded games. The games are seeded
    and a PlayerState is frozen, so they are played once per process and
    each test gets its own list of the same seats."""

    return list(_played_seats())


def test_a_check_reads_only_its_rows_fields_on_real_seats() -> None:
    seats = _seats()
    for check in PLAYER_CHECKS:
        seen: set[str] = set()
        for seat in seats:
            check.check(_Reads(seat, seen))  # type: ignore[arg-type]
        assert seen <= check.fields, (check.check.__name__, sorted(seen - check.fields))


# Master's ``PlayerState.__post_init__`` (7bd1effb) raised these, in this order
# in its source; the table's checks must raise the same, in the same order, so
# a seat that breaks several checks fails with the same first error.
_MASTER_MESSAGES = (
    "player_id must not be negative",
    "player component quantities must not be negative",
    "a Skill tile cannot be held twice",
    "a player cannot hold two copies of one Skill",
    "a Tech tile cannot be held twice",
    "flipped Tech tiles must be held tiles",
    "a player has only two dreadnoughts",
    "the Freighter's top space is the third",
    "a track holds one Snooper token",
    "an Intrigue card is known once",
    "available and placed agents must equal active agents",
    "Leader token positions must be non-negative",
    "a space cannot be blocked twice for a player",
    "a player must always account for all 12 troops",
    "a player must always account for all three spies",
    "a player cannot place two spies on one post",
    "a player cannot hold one Faction Alliance twice",
    "Alliance faction IDs must not be empty",
    "a player has only three control markers",
    "control marker locations must be unique",
    "battle cards in a player's supply must be unique",
    "face-down battle cards must be in the player's supply",
    "a battle card cannot be face-down twice",
    "a Contract cannot be active and completed",
    "an Imperium card instance cannot occupy two zones",
    "an Intrigue card cannot be both held and face up",
    "an owed draw is from the Intrigue deck or the deck",
    "a hand card cannot be publicly known twice",
    "a deck card cannot be publicly known twice",
)


def _raised_messages(function: Any) -> list[str]:
    messages: list[str] = []

    class Raises(ast.NodeVisitor):
        def visit_Raise(self, node: ast.Raise) -> None:
            if (
                isinstance(node.exc, ast.Call)
                and node.exc.args
                and isinstance(node.exc.args[0], ast.Constant)
            ):
                messages.append(str(node.exc.args[0].value))

    Raises().visit(ast.parse(textwrap.dedent(inspect.getsource(function))))
    return messages


def test_the_checks_raise_masters_messages_in_masters_order() -> None:
    raised = [
        message for check in PLAYER_CHECKS for message in _raised_messages(check.check)
    ]
    assert raised == list(_MASTER_MESSAGES)
    assert _raised_messages(_normalize_hand_public) == []


def test_the_table_keeps_the_constructors_order_and_every_check() -> None:
    names = [check.check.__name__ for check in PLAYER_CHECKS]
    assert len(names) == len(set(names))
    source = inspect.getsource(player_module)
    defined = [
        line.split("(")[0].removeprefix("def ")
        for line in source.splitlines()
        if line.startswith("def _check_")
    ]
    assert names == defined


_BREAKS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("player_id must not be negative", {"player_id": -1}),
    ("quantities must not be negative", {"victory_points": -1}),
    ("quantities must not be negative", {"strategic_push_solari": -2}),
    ("Skill tile cannot be held twice", {"skill_ids": ("skill:a:0", "skill:a:0")}),
    ("two copies of one Skill", {"skill_ids": ("skill:a:0", "skill:a:1")}),
    ("Tech tile cannot be held twice", {"tech_ids": ("t", "t")}),
    ("flipped Tech tiles", {"tech_flipped": ("x",)}),
    ("only two dreadnoughts", {"dreadnoughts_supply": 3}),
    ("Freighter's top space", {"freighter_space": 4}),
    ("one Snooper token", {"snooper_faction_ids": ("emperor", "emperor")}),
    ("Intrigue card is known once", {"known_intrigue_ids": ("i", "i")}),
    ("placed agents must equal", {"agents_available": "+1"}),
    ("Leader token positions", {"tactics_track_space": -1}),
    ("cannot be blocked twice", {"voice_blocked_space_ids": ("s", "s")}),
    ("all 12 troops", {"troops_supply": "+1"}),
    ("all three spies", {"spies_supply": "+1"}),
    ("one Faction Alliance twice", {"alliance_faction_ids": ("f", "f")}),
    ("must not be empty", {"alliance_faction_ids": ("",)}),
    ("only three control markers", {"control_space_ids": ("a", "b", "c", "d")}),
    ("control marker locations", {"control_space_ids": ("a", "a")}),
    ("battle cards in a player's supply", {"objective_ids": ("o", "o")}),
    ("face-down battle cards must be", {"face_down_battle_card_ids": ("z",)}),
    ("cannot be active and completed", {"active_contract_ids": ("c", "c")}),
    ("cannot occupy two zones", {"discard_pile": ("d", "d")}),
    ("both held and face up", {"intrigue_cards": ("q", "q")}),
    ("owed draw is from", {"owed_draws": (("nowhere", "x", 0),)}),
    ("publicly known twice", {"hand_public": ("h", "h")}),
    ("deck card cannot be publicly known twice", {"deck_public_top": ("k", "k")}),
)


@pytest.mark.parametrize(("message", "changes"), _BREAKS)
def test_a_copy_fails_as_the_constructor_does(
    message: str, changes: dict[str, Any]
) -> None:
    seat = _seats()[-1]
    changes = {
        name: getattr(seat, name) + 1 if value == "+1" else value
        for name, value in changes.items()
    }
    with pytest.raises(ValueError) as copied:
        replace(seat, **changes)
    fields = {
        field.name: getattr(seat, field.name) for field in dataclasses.fields(seat)
    }
    with pytest.raises(ValueError) as built:
        PlayerState(**{**fields, **changes})
    assert message in str(copied.value)
    assert str(copied.value) == str(built.value)


def test_a_copy_equals_the_constructors_object_on_real_seats() -> None:
    seats = _seats()
    for old, new in zip(seats, seats[4:], strict=False):
        if old.player_id != new.player_id:
            continue
        changes = {
            field.name: getattr(new, field.name)
            for field in dataclasses.fields(new)
            if getattr(new, field.name) is not getattr(old, field.name)
        }
        copied = replace(old, **changes)
        built = PlayerState(
            **{
                field.name: getattr(new, field.name)
                for field in dataclasses.fields(new)
            }
        )
        assert copied == built


def test_a_copy_normalizes_the_public_hand_when_the_hand_changes() -> None:
    seat = next(s for s in _seats() if len(s.hand) >= 2)
    public = replace(seat, hand_public=seat.hand[:2])
    assert public.hand_public == seat.hand[:2]
    played = replace(public, hand=public.hand[1:])
    assert played.hand_public == seat.hand[1:2]


def test_a_copy_runs_only_the_checks_of_what_it_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seat = _seats()[-1]
    runs: list[str] = []

    def counting(check: PlayerCheck) -> PlayerCheck:
        def run(state: PlayerState) -> None:
            runs.append(check.check.__name__)
            check.check(state)

        return PlayerCheck(run, check.fields)

    monkeypatch.setattr(
        player_module, "PLAYER_CHECKS", tuple(counting(c) for c in PLAYER_CHECKS)
    )
    replace(seat, leader_face_id=seat.leader_face_id)
    assert runs == []
    replace(seat, troops_supply=seat.troops_supply)
    assert runs == ["_check_quantities", "_check_troops"]
    runs.clear()
    PlayerState(**{f.name: getattr(seat, f.name) for f in dataclasses.fields(seat)})
    assert runs == [check.check.__name__ for check in PLAYER_CHECKS]


def _reference_changed_seat_fields(
    before: tuple[PlayerState, ...], after: tuple[PlayerState, ...]
) -> frozenset[str]:
    """``core.state._changed_seat_fields`` as it was before stage B."""

    if len(before) != len(after):
        return state_module._SEAT_FIELDS
    changed: set[str] = set()
    for old, new in zip(before, after, strict=True):
        if old is new:
            continue
        for name in state_module._SEAT_FIELDS - changed:
            if getattr(old, name) is not getattr(new, name):
                changed.add(name)
    return frozenset(changed)


def test_the_changed_seat_fields_are_the_ones_compared_one_by_one() -> None:
    states = [
        state
        for config, seed in ((FULL, 33), (IMPERIUM_IX, 34))
        for state in played_states(config, seed, 600)
    ]
    differing = 0
    for before, after in zip(states, states[1:], strict=False):
        found = state_module._changed_seat_fields(before.players, after.players)
        assert found == _reference_changed_seat_fields(before.players, after.players)
        differing += bool(found)
    assert differing > 20
    assert state_module._changed_seat_fields((), states[0].players) == (
        state_module._SEAT_FIELDS
    )


def test_a_frame_with_a_dict_context_is_the_constructors_copy() -> None:
    frame = DecisionFrame(
        "agent_effects", "f", PlayerDecision(1, "p"), (("a", 1), ("c", "x"))
    )
    context: dict[str, ActionValue] = {"c": "y", "b": True, "a": 1}
    built = frame_with_dict_context(frame, context)
    expected = replace(frame, context=tuple(sorted(context.items())))
    assert built == expected
    assert repr(built) == repr(expected)
    assert built.decision is frame.decision and built.kind is frame.kind
    assert type(built) is DecisionFrame
    # Not an exact dict: through the constructor, which checks the context.
    assert frame_with_dict_context(frame, _OrderedDict(context)) == expected
