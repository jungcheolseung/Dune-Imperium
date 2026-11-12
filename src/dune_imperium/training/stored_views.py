"""Stored encoded views and the observation layout they were written with.

An ``OBSERVATION_VERSION`` change moves columns: a segment that grows pushes
every later one along. A network moves its first layer by segment name as
it loads (``training.checkpoint._migrate``), but stored training data did
not record their layout, so every change meant copying them with an old
tree checked out (docs/value-model-plan.md 7: 3.1 GB of round shards on
2026-11-04).

Now every format that stores views records the layout it was written with
(``observation_layout``: version, size and segments), and every reader
moves the columns to this tree's layout by segment name as it loads
(``observation_column_map``, the checkpoint's rule):

- round shards and the dense playout test sets (``training.round_values``,
  ``load_dense_views``),
- teacher shards and their packed and compact copies (``training.teacher``),
- expert-iteration shards (``training.expert``),
- the value screen's leaves (``evaluation.value_screen``).

A collection's worker chunks (``training.collect``) are not stored data:
the same collection writes and reads them in one tree.

Data written before their format recorded a layout name it in a file
beside them, ``observation-layout.json`` (``LAYOUT_FILE``): the layout of
every file in that folder that records none. ``scripts/train/migrate_rounds.py
layout``, run with a tree of that version, writes one. Without it, data
whose header records today's observation version read as today's; any
other is refused, never read at shifted columns.

Moving by name keeps an old view's meaning only while every index table
the encoder numbers entities by grows at its end and an old column keeps
what it means. That was checked for v39 to v42 (docs/value-model-plan.md
7) and v42 to v43 (the set-aside slots' projected digests), so views older
than ``MOVABLE_FROM`` are refused. A version that renumbers a table or
changes what a column means raises ``MOVABLE_FROM`` to itself.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any, Final

import numpy as np

from dune_imperium.adapters.observation_encoding import (
    OBSERVATION_SEGMENTS,
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
)

# The ``.npz`` entry (and JSON header key) holding the layout.
LAYOUT_KEY: Final = "observation_layout"
# The file beside data that record no layout.
LAYOUT_FILE: Final = "observation-layout.json"
# The oldest observation version whose views move by segment name.
MOVABLE_FROM: Final = 39

Layout = dict[str, Any]


def observation_layout() -> Layout:
    """This tree's observation layout: its version, size and segments."""

    return {
        "version": OBSERVATION_VERSION,
        "size": OBSERVATION_SIZE,
        "segments": [
            [segment.name, segment.offset, segment.length]
            for segment in OBSERVATION_SEGMENTS
        ],
    }


def _normal(layout: Mapping[str, Any]) -> Layout:
    try:
        return {
            "version": int(layout["version"]),
            "size": int(layout["size"]),
            "segments": [
                [str(name), int(offset), int(length)]
                for name, offset, length in layout["segments"]
            ],
        }
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"not an observation layout: {error}") from error


@cache
def _current_json() -> str:
    return json.dumps(observation_layout())


def is_current(layout: Mapping[str, Any]) -> bool:
    """Whether ``layout`` is this tree's (its views need no move)."""

    return json.dumps(_normal(layout)) == _current_json()


def observation_column_map(old: Mapping[str, Any]) -> np.ndarray:
    """Each column of the ``old`` layout's views at its column here.

    A segment keeps its name; one that grew keeps its old columns at its
    front, as a checkpoint's first layer is moved
    (``training.checkpoint._migrate``). That reads an old view exactly as
    this tree would encode the same state only while every index table the
    encoder numbers entities by has grown at its end and never renumbered
    (docs/value-model-plan.md 7 checks it for v39 and v41 against v42), and
    the new columns of a state the old engine could make are zero. Refused
    when a segment was dropped, shrank or moved ahead of another, and for
    views older than ``MOVABLE_FROM``.
    """

    layout = _normal(old)
    if layout["version"] < MOVABLE_FROM:
        raise ValueError(
            f"views of observation v{layout['version']} do not move: only "
            f"v{MOVABLE_FROM} and later were checked to keep their meaning"
        )
    here = {segment.name: segment for segment in OBSERVATION_SEGMENTS}
    old_segments = layout["segments"]
    if sum(length for _, _, length in old_segments) != layout["size"]:
        raise ValueError("the old layout's segments do not add up to its size")
    target = np.full(layout["size"], -1, dtype=np.int64)
    previous = -1
    for name, offset, length in old_segments:
        segment = here.get(name)
        if segment is None:
            raise ValueError(f"segment {name} is gone; the old views cannot move")
        if segment.length < length:
            raise ValueError(f"segment {name} shrank from {length} to {segment.length}")
        if segment.offset <= previous:
            raise ValueError(f"segment {name} moved ahead of an older one")
        previous = segment.offset
        target[offset : offset + length] = np.arange(
            segment.offset, segment.offset + length
        )
    return target


def layout_entry(layout: Mapping[str, Any] | None = None) -> np.ndarray:
    """``layout`` (by default this tree's) as an ``.npz`` entry: JSON text."""

    return np.asarray(
        json.dumps(observation_layout() if layout is None else _normal(layout))
    )


def recorded_layout(arrays: Mapping[str, Any]) -> Layout | None:
    """The layout an opened ``.npz`` records (``LAYOUT_KEY``), or None."""

    if LAYOUT_KEY not in arrays:
        return None
    return _normal(json.loads(str(arrays[LAYOUT_KEY])))


def read_layout_file(path: Path) -> Layout:
    return _normal(json.loads(path.read_text()))


def write_layout_file(folder: Path, layout: Mapping[str, Any] | None = None) -> Path:
    """Write ``layout`` (by default this tree's) as ``folder``'s ``LAYOUT_FILE``."""

    path = folder / LAYOUT_FILE
    chosen = observation_layout() if layout is None else _normal(layout)
    path.write_text(json.dumps(chosen) + "\n")
    return path


def stored_layout(
    source: Path,
    recorded: Mapping[str, Any] | None,
    *,
    layout: Mapping[str, Any] | None = None,
    version: int | None = None,
) -> Layout:
    """The layout ``source``'s views were written with.

    ``recorded`` is the layout the data record. Data that record none take
    ``layout`` if the caller gives one, else the ``LAYOUT_FILE`` beside
    ``source``, else today's when ``version`` (the observation version a
    header records without a layout) is today's. Anything else is refused,
    as is a ``version`` or a given ``layout`` that disagrees with the
    layout found.
    """

    found: Layout
    if recorded is not None:
        found, origin = _normal(recorded), "the layout it records"
        if layout is not None and _normal(layout) != found:
            raise ValueError(
                f"{source}: records observation v{found['version']}'s layout, "
                f"not the v{_normal(layout)['version']} layout given"
            )
    elif layout is not None:
        found, origin = _normal(layout), "the layout given"
    elif (source.parent / LAYOUT_FILE).exists():
        found = read_layout_file(source.parent / LAYOUT_FILE)
        origin = str(source.parent / LAYOUT_FILE)
    elif version == OBSERVATION_VERSION:
        return observation_layout()
    else:
        named = "no version" if version is None else f"observation v{version}"
        raise ValueError(
            f"{source}: its views record no observation layout ({named}), and "
            f"this tree is observation v{OBSERVATION_VERSION}. Write the layout "
            f"they were encoded with to {source.parent / LAYOUT_FILE} "
            "(scripts/train/migrate_rounds.py layout, run with a tree of that "
            "version); they are never read at today's columns."
        )
    if version is not None and version != found["version"]:
        raise ValueError(
            f"{source}: records observation v{version}, but {origin} "
            f"is v{found['version']}"
        )
    return found


def column_moves(source: Path, layout: Mapping[str, Any]) -> np.ndarray | None:
    """``layout``'s ``observation_column_map``, or None when it is this
    tree's (nothing moves)."""

    if is_current(layout):
        return None
    try:
        return observation_column_map(layout)
    except ValueError as error:
        raise ValueError(
            f"{source}: views of observation v{layout['version']} cannot move "
            f"to v{OBSERVATION_VERSION}: {error}"
        ) from error


def move_columns(
    columns: np.ndarray, layout: Mapping[str, Any], source: Path
) -> np.ndarray:
    """Sparse views' column numbers, written with ``layout``, at this tree's
    columns (in their own dtype)."""

    size = int(layout["size"])
    if columns.size and (int(columns.max()) >= size or int(columns.min()) < 0):
        raise ValueError(f"{source}: the views have columns outside their {size}")
    moves = column_moves(source, layout)
    if moves is None:
        return columns
    moved = moves[columns.astype(np.int64)]
    if moved.size and int(moved.max()) > np.iinfo(columns.dtype).max:
        raise ValueError(f"{source}: the moved columns overflow {columns.dtype}")
    return moved.astype(columns.dtype)


def move_dense(
    views: np.ndarray, layout: Mapping[str, Any], source: Path
) -> np.ndarray:
    """Dense views ``[rows, size]``, written with ``layout``, at this tree's
    columns ``[rows, OBSERVATION_SIZE]``; new columns are zero."""

    size = int(layout["size"])
    if views.ndim != 2 or views.shape[1] != size:
        raise ValueError(
            f"{source}: views of shape {views.shape}, but their layout "
            f"(observation v{layout['version']}) is {size} columns wide"
        )
    moves = column_moves(source, layout)
    if moves is None:
        return views
    moved = np.zeros((views.shape[0], OBSERVATION_SIZE), dtype=views.dtype)
    moved[:, moves] = views
    return moved


def save_dense_views(path: Path, views: np.ndarray, key: str = "observations") -> None:
    """Dense views at this tree's columns, compressed, with their layout."""

    if views.ndim != 2 or views.shape[1] != OBSERVATION_SIZE:
        raise ValueError(f"views of shape {views.shape} are not this tree's")
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {key: views, LAYOUT_KEY: layout_entry()}
    np.savez_compressed(path, **arrays)  # type: ignore[arg-type]


def load_dense_views(
    path: Path,
    key: str = "observations",
    *,
    layout: Mapping[str, Any] | None = None,
) -> np.ndarray:
    """A file of dense views (a playout test set's ``obs.npz``) at this
    tree's columns (``stored_layout``, ``move_dense``)."""

    with np.load(path) as arrays:
        views = arrays[key]
        recorded = recorded_layout(arrays)
    return move_dense(views, stored_layout(path, recorded, layout=layout), path)
