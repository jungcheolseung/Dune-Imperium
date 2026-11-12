"""The canonical state hash is the same as before the 2026-11 engine speed work.

docs/evaluation/2026-11-engine-speed.md: ``core.state._canonicalize`` takes
shortcuts for plain values and reads each dataclass's fields once per type.
Saves and records keep their hashes only while it builds the very same
canonical form, so it is held here against the implementation it replaced,
kept verbatim, on played states of both boards.
"""

import dataclasses
import hashlib
import json
from enum import StrEnum
from typing import Any, NamedTuple

import pytest
from tests.unit.rules.test_kept_answers import FULL, IMPERIUM_IX, played_states

from dune_imperium.config import RulesetConfig
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState, _canonicalize, canonical_state_hash


def _reference_canonicalize(value: Any) -> Any:
    """``core.state._canonicalize`` before 2026-11, verbatim."""

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        omitted: frozenset[str] = getattr(
            type(value), "HASH_OMITTED_AT_DEFAULT", frozenset()
        )
        return {
            field.name: _reference_canonicalize(getattr(value, field.name))
            for field in dataclasses.fields(value)
            if not (
                field.name in omitted and getattr(value, field.name) == field.default
            )
        }
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_reference_canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _reference_canonicalize(item) for key, item in value.items()}
    if value is None or isinstance(value, bool | int | float | str):
        return value
    message = f"state contains unsupported canonical value: {type(value).__name__}"
    raise TypeError(message)


def _reference_hash(state: GameState) -> str:
    encoded = json.dumps(
        _reference_canonicalize(state),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


@pytest.mark.parametrize(("config", "seed"), [(FULL, 5), (IMPERIUM_IX, 6)])
def test_state_hash_matches_the_reference_canonical_form(
    config: RulesetConfig, seed: int
) -> None:
    for index, state in enumerate(played_states(config, seed, 240)):
        if index % 20 == 0:
            assert canonical_state_hash(state) == _reference_hash(state)
            assert _canonicalize(state) == _reference_canonicalize(state)


def test_canonical_form_keeps_subclasses_on_the_general_checks() -> None:
    class Colour(StrEnum):
        RED = "red"

    class Pair(NamedTuple):
        name: str
        amount: int

    class Text(str):
        pass

    value = (
        Colour.RED,
        Pair("a", 1),
        Text("t"),
        {3: (True, None, 1.5)},
        ((Colour.RED,), ("x", 2)),
    )
    assert _canonicalize(value) == _reference_canonicalize(value)
    assert json.dumps(_canonicalize(value)) == json.dumps(
        _reference_canonicalize(value)
    )
    for unsupported in ((object(),), [1], PlayerState):
        with pytest.raises(TypeError, match="unsupported canonical value"):
            _canonicalize(unsupported)
