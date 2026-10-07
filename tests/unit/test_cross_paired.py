"""cross_paired.py pairs two cells by seed and tested seats, one seat or two."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from dune_imperium.evaluation.tournament import seat_rotations

_TOOL = Path(__file__).resolve().parents[2] / "scripts" / "ab" / "cross_paired.py"

Row = dict[str, Any]


@pytest.fixture(scope="module")
def cross_paired() -> ModuleType:
    """Import ``scripts/ab/cross_paired.py`` (it puts ``scripts/ab`` on sys.path)."""

    if "cross_paired" in sys.modules:
        return sys.modules["cross_paired"]
    spec = importlib.util.spec_from_file_location("cross_paired", _TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cross_paired"] = module
    spec.loader.exec_module(module)
    return module


def _row(seed: int, agents: tuple[str, ...], winner: int) -> Row:
    """One match row: ``winner`` takes rank 1 with 12 VP, the rest 8 VP."""

    others = [seat for seat in range(4) if seat != winner]
    ranks = {winner: 1} | {seat: 2 + index for index, seat in enumerate(others)}
    return {
        "game_seed": seed,
        "seats": [
            {
                "agent": agent,
                "rank": ranks[seat],
                "seat": seat,
                "victory_points": 12 if seat == winner else 8,
            }
            for seat, agent in enumerate(agents)
        ],
    }


def _write(path: Path, rows: list[Row]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def _cell_rows(
    tested: str, other: str, lineup: tuple[int, ...], wins: bool
) -> list[Row]:
    """Two seeds of the tournament's rotations; ``tested`` wins iff ``wins``."""

    agents = tuple(tested if slot else other for slot in lineup)
    rows = []
    for seed in (10, 11):
        for rotation in seat_rotations(agents):
            mine = [seat for seat, agent in enumerate(rotation) if agent == tested]
            theirs = [seat for seat in range(4) if seat not in mine]
            rows.append(_row(seed, rotation, mine[-1] if wins else theirs[0]))
    return rows


def _run(
    module: ModuleType, a: Path, b: Path, capsys: pytest.CaptureFixture[str]
) -> str:
    old = sys.argv
    sys.argv = ["cross_paired.py", str(a), str(b), "--a", "A", "--b", "B"]
    sys.argv += ["--draws", "200"]
    try:
        assert module.main() == 0
    finally:
        sys.argv = old
    return capsys.readouterr().out


def test_one_against_three_cells_pair_by_seed_and_seat(
    cross_paired: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = _write(tmp_path / "a.jsonl", _cell_rows("A", "C", (1, 0, 0, 0), True))
    b = _write(tmp_path / "b.jsonl", _cell_rows("B", "C", (1, 0, 0, 0), False))

    keys = set(cross_paired.cell(a, "A"))
    assert keys == {(seed, (seat,)) for seed in (10, 11) for seat in range(4)}

    out = _run(cross_paired, a, b, capsys)
    assert "8 paired matches over 2 seeds (A has 8, B has 8)" in out
    assert "A win share 100.0%" in out
    assert "B win share   0.0%" in out
    assert "(1 seat, equal-strength share 25%)" in out
    assert "       win (higher)    1.000    0.000   +1.000" in out


def test_two_against_two_cells_pair_by_seed_and_both_seats(
    cross_paired: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # X,app_ai,X,app_ai has two distinct rotations: X in seats {0,2} and {1,3}.
    a = _write(tmp_path / "a.jsonl", _cell_rows("A", "app_ai", (1, 0, 1, 0), True))
    b = _write(tmp_path / "b.jsonl", _cell_rows("B", "app_ai", (1, 0, 1, 0), False))

    outcomes = cross_paired.cell(a, "A")
    assert set(outcomes) == {
        (seed, seats) for seed in (10, 11) for seats in ((0, 2), (1, 3))
    }
    # Either seat winning is a win for the pair; rank and VP average the two.
    assert outcomes[(10, (0, 2))]["win"] == 1.0
    assert outcomes[(10, (0, 2))]["vp"] == 10.0
    assert outcomes[(10, (0, 2))]["null"] == 0.5

    out = _run(cross_paired, a, b, capsys)
    assert "4 paired matches over 2 seeds (A has 4, B has 4)" in out
    assert "(2 seats, equal-strength share 50%)" in out
    assert "       win (higher)    1.000    0.000   +1.000" in out
