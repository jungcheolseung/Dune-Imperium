"""Stored views record their observation layout and move as they load.

docs/value-model-plan.md 8: every format that stores encoded views -- round
shards, dense playout test sets, teacher shards (and their packed and
compact copies), expert shards and the value screen's leaves -- is read at
this tree's columns, moved by segment name from the layout it was written
with: the one it records, or for data from before, ``observation-layout.json``
beside it. Each format written at an older layout (a middle segment that
has since grown, a segment that is new here) loads to the views the copy
path (``migrate_rounds``) gives; a layout that cannot move, or no layout at
another version, is refused instead of read at shifted columns.
"""

import gc
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from tests.support.observation_growth import v42_layout

pytest.importorskip("torch")

from dune_imperium.adapters.observation_encoding import (  # noqa: E402
    OBSERVATION_SIZE,
    OBSERVATION_VERSION,
)
from dune_imperium.adapters.pettingzoo_env import (  # noqa: E402
    LOSER_REWARD,
    WINNER_REWARD,
)
from dune_imperium.evaluation.value_screen import (  # noqa: E402
    Leaves,
    load_leaves,
    save_leaves,
)
from dune_imperium.training.expert import (  # noqa: E402
    ANCHOR,
    LabelConfig,
    LabelledGame,
    LabelRow,
    read_shards,
    run_meta,
    write_game,
)
from dune_imperium.training.round_values import (  # noqa: E402
    RoundData,
    load_round_shards,
    load_rounds,
    migrate_rounds,
    save_rounds,
)
from dune_imperium.training.stored_views import (  # noqa: E402
    LAYOUT_FILE,
    LAYOUT_KEY,
    MOVABLE_FROM,
    Layout,
    layout_entry,
    load_dense_views,
    observation_column_map,
    observation_layout,
    save_dense_views,
    write_layout_file,
)
from dune_imperium.training.teacher import (  # noqa: E402
    COMPACT_MANIFEST,
    PACK_MANIFEST,
    TeacherData,
    compact_teacher_data,
    load_teacher_data,
    pack_teacher_data,
    save_teacher_data,
)

# The older layout: a segment near the front is 10 columns shorter (Rise of
# Ix's Contracts at its end), so every later segment sits 10 columns earlier,
# and a segment near the end (Rise of Ix's starting Contracts) is missing.
_GROWN = ("face_up_contracts", 10)
_NEW = "private_starting_contracts"
_ROWS = 24


def _older() -> tuple[Layout, np.ndarray]:
    """The older layout and, for each column here, its column there (-1:
    none)."""

    segments = []
    back = np.full(OBSERVATION_SIZE, -1, dtype=np.int64)
    offset = 0
    for name, start, length in observation_layout()["segments"]:
        if name == _NEW:
            continue
        kept = length - _GROWN[1] if name == _GROWN[0] else length
        segments.append([name, offset, kept])
        back[start : start + kept] = np.arange(offset, offset + kept)
        offset += kept
    return {
        "version": OBSERVATION_VERSION - 1,
        "size": offset,
        "segments": segments,
    }, back


def _v42() -> tuple[Layout, np.ndarray]:
    """Observation v42's layout (each seat's set-aside Imperium slots, in the
    middle of the vector, grew from two to five in v43) and the columns."""

    back = np.full(OBSERVATION_SIZE, -1, dtype=np.int64)
    here = {name: start for name, start, _ in observation_layout()["segments"]}
    for name, offset, length in v42_layout():
        back[here[name] : here[name] + length] = np.arange(offset, offset + length)
    segments = [[name, offset, length] for name, offset, length in v42_layout()]
    size = sum(length for _, _, length in v42_layout())
    return {"version": 42, "size": size, "segments": segments}, back


_OLDER = {"grown segment, new segment": _older, "v42": _v42}


def _views(back: np.ndarray, seed: int = 0) -> np.ndarray:
    """Views at today's columns, zero where the older layout has no column
    (a state the older engine could make), values 1-30."""

    generator = np.random.default_rng(seed)
    shape = (_ROWS, OBSERVATION_SIZE)
    views = (generator.random(shape) < 0.05) * generator.integers(1, 31, shape)
    views[:, back < 0] = 0
    return views.astype(np.int16)


def _at(views: np.ndarray, layout: Layout, back: np.ndarray) -> np.ndarray:
    """``views`` written at ``layout``'s columns."""

    out = np.zeros((views.shape[0], int(layout["size"])), dtype=views.dtype)
    out[:, back[back >= 0]] = views[:, back >= 0]
    return out


def _sparse(views: np.ndarray, dtype: Any) -> tuple[np.ndarray, ...]:
    owner, columns = np.nonzero(views)
    offsets = np.zeros(views.shape[0] + 1, dtype=np.int64)
    np.cumsum(np.bincount(owner, minlength=views.shape[0]), out=offsets[1:])
    return columns.astype(dtype), views[owner, columns].astype(np.int16), offsets


def _restamp(path: Path, recorded: Layout | None) -> None:
    """Rewrite an ``.npz`` as a tree whose layout was ``recorded`` wrote it,
    or (None) as one from before the format recorded its layout."""

    with np.load(path) as arrays:
        kept = {name: arrays[name] for name in arrays.files if name != LAYOUT_KEY}
    if recorded is not None:
        kept[LAYOUT_KEY] = layout_entry(recorded)
    np.savez(path, **kept)


# -- one writer and one reader per format ----------------------------------------
def _round_data(views: np.ndarray) -> RoundData:
    columns, values, offsets = _sparse(views, np.int16)
    rows = views.shape[0]
    return RoundData(
        ruleset="r",
        leader_names=("a",),
        obs_columns=columns,
        obs_values=values,
        obs_offsets=offsets,
        games=np.arange(rows, dtype=np.int64) // 4,
        seats=(np.arange(rows) % 4).astype(np.int8),
        rounds=np.ones(rows, dtype=np.int16),
        ranks=(np.arange(rows) % 4 + 1).astype(np.int8),
        victory_points=np.zeros((rows, 4), dtype=np.int16),
        tables=np.zeros(rows, dtype=np.int8),
        leaders=np.zeros(rows, dtype=np.int16),
        dealt=np.zeros(rows, dtype=np.int8),
    )


def _write_rounds(folder: Path, views: np.ndarray, recorded: Layout | None) -> Path:
    path = folder / "rounds-000000001.npz"
    save_rounds(_round_data(views), path)
    _restamp(path, recorded)
    return path


def _read_rounds(path: Path) -> np.ndarray:
    return load_rounds(path).observations(np.arange(_ROWS))


def _write_dense(folder: Path, views: np.ndarray, recorded: Layout | None) -> Path:
    path = folder / "obs.npz"
    arrays = {"observations": views}
    if recorded is not None:
        arrays[LAYOUT_KEY] = layout_entry(recorded)
    folder.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)  # type: ignore[arg-type]
    return path


def _read_dense(path: Path) -> np.ndarray:
    return load_dense_views(path)


def _teacher_data(views: np.ndarray) -> TeacherData:
    columns, values, offsets = _sparse(views, np.int16)
    rows = views.shape[0]
    return TeacherData(
        ruleset="r",
        action_size=5,
        obs_columns=columns,
        obs_values=values,
        obs_offsets=offsets,
        legal_indices=np.tile(np.asarray([1, 3], dtype=np.int32), rows),
        legal_offsets=np.arange(0, 2 * rows + 1, 2, dtype=np.int64),
        teacher=np.full(2 * rows, 0.5, dtype=np.float16),
        actions=np.ones(rows, dtype=np.int32),
        returns=np.zeros(rows, dtype=np.float32),
        victory_points=np.zeros((rows, 4), dtype=np.int16),
        games=(np.arange(rows) // 6).astype(np.int32),
        values=np.zeros(rows, dtype=np.float32),
    )


def _write_teacher(folder: Path, views: np.ndarray, recorded: Layout | None) -> Path:
    path = folder / "teacher-0.npz"
    folder.mkdir(parents=True, exist_ok=True)
    save_teacher_data(_teacher_data(views), path)
    _restamp(path, recorded)
    return path


def _read_teacher(path: Path) -> np.ndarray:
    return load_teacher_data(path).observations(np.arange(_ROWS))


def _row(observation: np.ndarray, index: int) -> LabelRow:
    return LabelRow(
        kind=ANCHOR,
        seat=1,
        round_number=2,
        decision_index=index,
        observation=observation.astype(np.uint8),
        legal=np.asarray([2, 5], dtype=np.int32),
        prior_logits=np.zeros(2, dtype=np.float32),
        candidates=np.full(3, -1, dtype=np.int32),
        values=np.full((2, 3), np.nan, dtype=np.float32),
        played=5,
        frame="turn",
    )


def _write_expert(
    folder: Path, views: np.ndarray, recorded: Layout | None, seed: int = 40
) -> Path:
    """A shard written at ``views``' width; its header records ``recorded``,
    or (None) only the observation version of the older layout."""

    path = folder / f"g{seed}.npz"
    game = LabelledGame(
        game_seed=seed,
        rows=tuple(_row(view, index) for index, view in enumerate(views)),
        rewards=(LOSER_REWARD, WINNER_REWARD, LOSER_REWARD, LOSER_REWARD),
        ranks=(2, 1, 3, 4),
        victory_points=(9, 11, 7, 5),
        leader_ids=("a", "b", "c", "d"),
        rounds=9,
        decisions=(100, 120, 110, 90),
        seconds=1.0,
        guard_skips=0,
        played_is_first=0,
    )
    meta = run_meta("teacher.pt", LabelConfig(rollouts=2), 50, "r")
    meta.pop(LAYOUT_KEY)
    older = OBSERVATION_VERSION - 1
    meta["observation_version"] = older if recorded is None else recorded["version"]
    meta["observation_size"] = views.shape[1]
    if recorded is not None:
        meta[LAYOUT_KEY] = recorded
    write_game(path, game, meta)
    return path


def _read_expert(path: Path) -> np.ndarray:
    return read_shards([path]).observations.astype(np.int16)


def _leaves(views: np.ndarray) -> Leaves:
    columns, values, offsets = _sparse(views, np.uint16)
    rows = views.shape[0]
    return Leaves(
        shapes=np.asarray([[2, rows // 2]], dtype=np.int64),
        offsets=np.asarray([0, rows], dtype=np.int64),
        finished=np.zeros(rows, dtype=bool),
        rewards=np.full(rows, np.nan),
        recorded=np.zeros(rows),
        obs_columns=columns,
        obs_values=values,
        obs_offsets=offsets,
        chosen=np.zeros(1, dtype=np.int64),
        games=np.zeros(1, dtype=np.int64),
    )


def _write_leaves(folder: Path, views: np.ndarray, recorded: Layout | None) -> Path:
    path = folder / "leaves.npz"
    save_leaves(_leaves(views), path)
    _restamp(path, recorded)
    return path


def _read_leaves(path: Path) -> np.ndarray:
    return load_leaves([path]).observations(np.arange(_ROWS))


Writer = Callable[[Path, np.ndarray, Layout | None], Path]
Reader = Callable[[Path], np.ndarray]
_FORMATS: dict[str, tuple[Writer, Reader]] = {
    "round shard": (_write_rounds, _read_rounds),
    "dense test set": (_write_dense, _read_dense),
    "teacher shard": (_write_teacher, _read_teacher),
    "expert shard": (_write_expert, _read_expert),
    "value-screen leaves": (_write_leaves, _read_leaves),
}


# -- an older layout loads as the copy path ---------------------------------------
@pytest.mark.parametrize("recorded", [True, False], ids=["recorded", "file beside"])
@pytest.mark.parametrize("older", list(_OLDER))
@pytest.mark.parametrize("name", list(_FORMATS))
def test_each_format_loads_an_older_layout_as_the_copy_path(
    tmp_path: Path, name: str, older: str, recorded: bool
) -> None:
    write, read = _FORMATS[name]
    old, back = _OLDER[older]()
    views = _views(back)
    old_views = _at(views, old, back)
    if recorded:
        path = write(tmp_path, old_views, old)
    else:
        path = write(tmp_path, old_views, None)
        write_layout_file(tmp_path, old)
    # The copy path of scripts/train/migrate_rounds.py ``dense``.
    copied = np.zeros((_ROWS, OBSERVATION_SIZE), dtype=old_views.dtype)
    copied[:, observation_column_map(old)] = old_views
    loaded = read(path)
    np.testing.assert_array_equal(loaded, copied)
    np.testing.assert_array_equal(loaded, views)


def test_a_round_shard_folder_loads_as_migrate_rounds_copies_it(
    tmp_path: Path,
) -> None:
    old, back = _older()
    first, second = _views(back, 1), _views(back, 2)
    folder = tmp_path / "rounds"
    for number, views in ((1, first), (2, second)):
        save_rounds(_round_data(_at(views, old, back)), folder / f"rounds-{number}.npz")
        _restamp(folder / f"rounds-{number}.npz", None)
    write_layout_file(folder, old)
    loaded = load_round_shards(folder)
    stored = [
        _round_data(_at(views, old, back)) for views in (first, second)
    ]  # what the shards hold, read as stored
    copies = [migrate_rounds(data, observation_column_map(old)) for data in stored]
    np.testing.assert_array_equal(
        loaded.obs_columns,
        np.concatenate([copy.obs_columns for copy in copies]),
    )
    rows = np.arange(2 * _ROWS)
    np.testing.assert_array_equal(
        loaded.observations(rows), np.concatenate([first, second])
    )


def test_today_s_data_record_today_s_layout_and_load_as_written(
    tmp_path: Path,
) -> None:
    views = _views(_older()[1])
    rounds = tmp_path / "rounds-000000001.npz"
    save_rounds(_round_data(views), rounds)
    dense = tmp_path / "obs.npz"
    save_dense_views(dense, views)
    teacher = tmp_path / "teacher.npz"
    save_teacher_data(_teacher_data(views), teacher)
    leaves = tmp_path / "leaves.npz"
    save_leaves(_leaves(views), leaves)
    for path in (rounds, dense, teacher, leaves):
        with np.load(path) as arrays:
            assert json.loads(str(arrays[LAYOUT_KEY])) == observation_layout()
    np.testing.assert_array_equal(_read_rounds(rounds), views)
    np.testing.assert_array_equal(_read_dense(dense), views)
    np.testing.assert_array_equal(_read_teacher(teacher), views)
    np.testing.assert_array_equal(_read_leaves(leaves), views)
    assert run_meta("t.pt", LabelConfig(rollouts=2), 5, "r")[LAYOUT_KEY] == (
        observation_layout()
    )


def test_an_expert_header_of_today_s_version_reads_as_today_s(tmp_path: Path) -> None:
    """A shard from before headers recorded a layout, of today's version."""

    views = _views(_older()[1])
    path = _write_expert(tmp_path, views, observation_layout())
    with np.load(path) as arrays:
        stored = {name: arrays[name] for name in arrays.files}
    meta = json.loads(str(stored["meta_json"]))
    del meta[LAYOUT_KEY]
    stored["meta_json"] = np.asarray(json.dumps(meta))
    np.savez_compressed(path, **stored)
    np.testing.assert_array_equal(_read_expert(path), views)


def test_expert_shards_of_two_layouts_stack(tmp_path: Path) -> None:
    old, back = _older()
    views, newer = _views(back, 3), _views(back, 4)
    old_path = _write_expert(tmp_path / "old", _at(views, old, back), None)
    write_layout_file(tmp_path / "old", old)
    new_path = _write_expert(tmp_path, newer, observation_layout(), seed=41)
    data = read_shards([old_path, new_path])
    np.testing.assert_array_equal(
        data.observations.astype(np.int16), np.concatenate([views, newer])
    )


# -- the packed and compact copies of teacher shards --------------------------------
@pytest.mark.parametrize("copy", ["pack", "compact"])
def test_teacher_copies_move_and_a_copy_of_another_layout_is_rebuilt(
    tmp_path: Path, copy: str
) -> None:
    old, back = _older()
    views = _views(back, 5)
    shard = _write_teacher(tmp_path / "shards", _at(views, old, back), None)
    write_layout_file(tmp_path / "shards", old)
    build = pack_teacher_data if copy == "pack" else compact_teacher_data
    manifest = tmp_path / copy / (PACK_MANIFEST if copy == "pack" else COMPACT_MANIFEST)
    data = build([shard], tmp_path / copy)
    np.testing.assert_array_equal(data.observations(np.arange(_ROWS)), views)
    del data  # a pack's arrays map its files, which are rewritten below
    gc.collect()
    written = json.loads(manifest.read_text())
    assert written[LAYOUT_KEY] == observation_layout()
    # A copy made by a tree of another layout (here: its manifest from
    # before copies recorded one, over columns that are not today's) is
    # rebuilt from the shards, not read.
    del written[LAYOUT_KEY]
    manifest.write_text(json.dumps(written))
    columns = tmp_path / copy / "obs_columns.npy"
    np.save(columns, np.zeros_like(np.load(columns)))
    again = build([shard], tmp_path / copy)
    np.testing.assert_array_equal(again.observations(np.arange(_ROWS)), views)
    assert json.loads(manifest.read_text())[LAYOUT_KEY] == observation_layout()


# -- refused ---------------------------------------------------------------------
def _dropped() -> Layout:
    layout = observation_layout()
    layout["version"] -= 1
    layout["segments"].append(["no_such_segment", layout["size"], 3])
    layout["size"] += 3
    return layout


def _shrunk() -> Layout:
    layout = observation_layout()
    layout["version"] -= 1
    layout["segments"][0][2] += 1
    layout["size"] += 1
    for later in layout["segments"][1:]:
        later[1] += 1
    return layout


def _reordered() -> Layout:
    layout = observation_layout()
    layout["version"] -= 1
    first, second = layout["segments"][0], layout["segments"][1]
    first[0], second[0] = second[0], first[0]
    first[2], second[2] = second[2], first[2]
    second[1] = first[2]
    return layout


def _too_old() -> Layout:
    layout = observation_layout()
    layout["version"] = MOVABLE_FROM - 1
    return layout


_CANNOT_MOVE = {
    "dropped": (_dropped, "gone"),
    "shrunk": (_shrunk, "shrank"),
    "reordered": (_reordered, "ahead"),
    "too old": (_too_old, "do not move"),
}


@pytest.mark.parametrize("recorded", [True, False], ids=["recorded", "file beside"])
@pytest.mark.parametrize("kind", list(_CANNOT_MOVE))
@pytest.mark.parametrize("name", list(_FORMATS))
def test_a_layout_that_cannot_move_is_refused(
    tmp_path: Path, name: str, kind: str, recorded: bool
) -> None:
    write, read = _FORMATS[name]
    make, match = _CANNOT_MOVE[kind]
    layout = make()
    views = np.zeros((_ROWS, int(layout["size"])), dtype=np.int16)
    views[:, :5] = 1
    if recorded:
        path = write(tmp_path, views, layout)
    else:
        if name == "expert shard":  # the header's version must match the file
            path = write(tmp_path, views, layout)
            _drop_expert_layout(path)
        else:
            path = write(tmp_path, views, None)
        write_layout_file(tmp_path, layout)
    with pytest.raises(ValueError, match=match):
        read(path)


def _drop_expert_layout(path: Path) -> None:
    with np.load(path) as arrays:
        stored = {name: arrays[name] for name in arrays.files}
    meta = json.loads(str(stored["meta_json"]))
    del meta[LAYOUT_KEY]
    stored["meta_json"] = np.asarray(json.dumps(meta))
    np.savez_compressed(path, **stored)


@pytest.mark.parametrize("name", list(_FORMATS))
def test_no_layout_at_another_version_is_refused(tmp_path: Path, name: str) -> None:
    """No layout recorded, no file beside: the expert shard's header records
    an older version; the others record none. Never read as today's."""

    write, read = _FORMATS[name]
    old, back = _older()
    path = write(tmp_path, _at(_views(back), old, back), None)
    assert not (tmp_path / LAYOUT_FILE).exists()
    with pytest.raises(ValueError, match="record no observation layout"):
        read(path)


def test_a_layout_file_that_disagrees_is_refused(tmp_path: Path) -> None:
    old, back = _older()
    # The expert header records the older version; the file says today's.
    path = _write_expert(tmp_path, _at(_views(back), old, back), None)
    write_layout_file(tmp_path)
    with pytest.raises(ValueError, match=f"records observation v{old['version']}"):
        _read_expert(path)
    # A dense set wider or narrower than its layout.
    dense = _write_dense(tmp_path / "dense", _at(_views(back), old, back), None)
    write_layout_file(tmp_path / "dense")
    with pytest.raises(ValueError, match="columns wide"):
        load_dense_views(dense)
    # A layout given for data that record another.
    shard = _write_rounds(tmp_path / "rounds", _views(back), observation_layout())
    with pytest.raises(ValueError, match="not the"):
        load_rounds(shard, layout=old)


def test_a_shard_folder_with_one_unmovable_shard_is_refused(tmp_path: Path) -> None:
    """``load_round_shards`` names the shard it cannot move."""

    old, back = _older()
    folder = tmp_path / "rounds"
    save_rounds(_round_data(_views(back)), folder / "rounds-1.npz")
    bad = folder / "rounds-2.npz"
    save_rounds(_round_data(_at(_views(back), old, back)), bad)
    _restamp(bad, None)
    with pytest.raises(ValueError, match="rounds-2.npz: its views record no"):
        load_round_shards(folder)
    write_layout_file(folder, {**old, "version": MOVABLE_FROM - 1})
    with pytest.raises(ValueError, match="rounds-2.npz: views of observation"):
        load_round_shards(folder)
