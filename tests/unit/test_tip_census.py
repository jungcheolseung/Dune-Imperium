"""The tip-census driver plays the tournament's games and keeps its columns apart."""

import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from dune_imperium.evaluation import tournament as T

_TOOL = Path(__file__).resolve().parents[2] / "scripts" / "ab" / "tip_census.py"


def load_tip_census() -> ModuleType:
    """Import ``scripts/ab/tip_census.py`` (it puts ``scripts/ab`` on sys.path)."""

    if "tip_census" in sys.modules:
        return sys.modules["tip_census"]
    spec = importlib.util.spec_from_file_location("tip_census", _TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["tip_census"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tip_census() -> Iterator[ModuleType]:
    yield load_tip_census()


def _spec(full: bool, seed: int = 3) -> T.MatchSpec:
    return T.tournament_specs(
        agents=("heuristic",),
        games=1,
        rulesets=(full,),
        start_seed=seed,
        rotate_leaders=True,
        bloodlines=full,
        tech_module=full,
        immortality=full,
    )[0]


@pytest.mark.parametrize("full", [False, True])
def test_the_census_plays_the_tournament_game(
    tip_census: ModuleType, full: bool
) -> None:
    spec = _spec(full)
    census = tip_census.play(spec, ("deck",))
    match = T.play_match(spec)
    assert census["ruleset"] == match.ruleset
    assert [(s["rank"], s["vp"]) for s in census["seats"]] == [
        (s.rank, s.victory_points) for s in match.seats
    ]
    assert [s["decisions"] for s in census["seats"]] == [
        s.decisions for s in match.seats
    ]


def test_every_collector_module_loads_and_prefixes_its_columns(
    tip_census: ModuleType,
) -> None:
    classes = tip_census.collector_classes()
    names = [cls.name for cls in classes]
    assert len(names) == len(set(names)), "collector names must be unique"
    result = tip_census.play(_spec(False), ())
    prefixes = {name + "." for name in names}
    for row in result["seats"]:
        for column in row:
            if "." in column:
                assert any(column.startswith(p) for p in prefixes), column
    for column in result["game"]:
        if column != "rounds":
            assert any(column.startswith(p) for p in prefixes), column


def test_the_summary_averages_numbers_and_tallies(tip_census: ModuleType) -> None:
    rows = [
        {"g": "a", "x": 1, "flag": True, "t": {"c": 2}, "maybe": None},
        {"g": "a", "x": 3, "flag": False, "t": {"c": 1, "d": 1}, "maybe": 4},
    ]
    summary = tip_census.summarize(rows, "g")["a"]
    assert summary["n"] == 2
    assert summary["x"] == (2.0, 2)
    assert summary["flag"] == (0.5, 2)
    assert summary["t"] == {"c": 1.5, "d": 0.5}
    assert summary["maybe"] == (4.0, 1)


def _load_compare() -> ModuleType:
    path = _TOOL.with_name("tip_compare.py")
    spec = importlib.util.spec_from_file_location("tip_compare", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_comparison_pairs_seeds_and_reads_tallies_and_nones(
    tmp_path: Path,
) -> None:
    tip_compare = _load_compare()

    def seat(
        kind: str, x: float, tally: dict[str, int], maybe: int | None
    ) -> dict[str, object]:
        return {"kind": kind, "seat": 0, "win": False, "x": x, "t": tally, "m": maybe}

    games = [
        {"seed": 0, "seats": [seat("a", 1, {"k": 1}, None), seat("b", 3, {}, 2)]},
        {"seed": 1, "seats": [seat("a", 2, {}, 5), seat("b", 6, {"k": 2}, None)]},
    ]
    (tmp_path / "rows.jsonl").write_text("".join(json.dumps(g) + "\n" for g in games))
    a_rows = tip_compare.load_arm(f"{tmp_path}::a")
    b_rows = tip_compare.load_arm(f"{tmp_path}::b")
    rows = {
        r["column"]: r
        for r in tip_compare.compare(a_rows, b_rows, paired=True, resamples=200)
    }
    assert (rows["x"]["a"], rows["x"]["b"], rows["x"]["diff"]) == (1.5, 4.5, 3.0)
    # Every resample keeps the difference within the per-seed differences.
    assert 2.0 <= rows["x"]["low"] <= rows["x"]["high"] <= 4.0
    # A tally key a seat never hit counts as 0 for that seat.
    assert (rows["t[k]"]["a"], rows["t[k]"]["b"]) == (0.5, 1.0)
    # None is left out of the mean and shows up in the share column.
    assert (rows["m"]["a"], rows["m"]["n_a"]) == (5.0, 1)
    assert (rows["has:m"]["a"], rows["has:m"]["b"]) == (0.5, 0.5)
