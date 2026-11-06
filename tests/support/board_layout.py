"""Helpers the board-layout tests share across the two boards' pictures.

``ring_unit_layout`` lays out a garrison as the client does (board.js
``ringUnitLayout``) from a board's ``garrison_units`` table, so the
Uprising scan's tests and the original board's run one port of it.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

Box = tuple[float, float, float, float]


def apart(first: Box, second: Box) -> bool:
    """Two boxes that do not overlap (touching edges allowed)."""

    epsilon = 1e-9
    return (
        first[0] + first[2] <= second[0] + epsilon
        or second[0] + second[2] <= first[0] + epsilon
        or first[1] + first[3] <= second[1] + epsilon
        or second[1] + second[3] <= first[1] + epsilon
    )


def centred(point: tuple[float, float], size: tuple[float, float]) -> Box:
    (x, y), (width, height) = point, size
    return (x - width / 2, y - height / 2, width, height)


@dataclass
class _Row:
    kind: str
    w: float
    h: float
    top: float = 0.0
    span: tuple[float, float] | None = None
    capacity: int = 0
    count: int = 0


def _row_splits(rows: int, parts: int) -> list[list[int]]:
    if parts == 1:
        return [[rows]]
    return [
        [first, *rest]
        for first in range(1, rows - parts + 2)
        for rest in _row_splits(rows - first, parts - 1)
    ]


def ring_unit_layout(
    counts: dict[str, int],
    ring: Box,
    units: Mapping[str, Any],
    avoid: tuple[Box, ...] = (),
) -> tuple[float, list[tuple[str, Box]]]:
    """The garrison's pieces as the client lays them (board.js ringUnitLayout).

    Rows inside the ring's inner circle, troops then Commanders, in the
    fewest rows that hold them, a kind's units shared evenly among its rows;
    the block centred, or moved just clear of a box to avoid, or else the rows
    that box cuts narrowed; every piece and gap shrinks in 0.05 steps down to
    the table's ``min_scale``. ``units`` is a board's ``garrison_units``
    table (``display.board_layout.marker_layout``). Returns the scale and
    each piece's box, or no pieces when nothing fits there (the client then
    closes the rows up).
    """

    gap, line, pad = units["gap"], units["line"], units["padding"]
    sizes, min_scale = units["sizes"], units["min_scale"]

    left, top, width, height = ring
    inset = line + pad
    cx, cy = left + width / 2, top + height / 2
    rx, ry = width / 2 - inset, height / 2 - inset
    kinds = [kind for kind in ("troop", "commander") if counts.get(kind)]
    total = sum(counts[kind] for kind in kinds)
    blocks = [
        (bl - pad, bt - pad, bl + bw + pad, bt + bh + pad) for bl, bt, bw, bh in avoid
    ]

    def free_span(
        row_top: float, row_bottom: float
    ) -> tuple[tuple[float, float] | None, bool]:
        edge = max(abs(row_top - cy), abs(row_bottom - cy))
        if edge >= ry:
            return None, False
        half = rx * math.sqrt(1 - (edge / ry) ** 2)
        spans = [(cx - half, cx + half)]
        cut = False
        for bx0, by0, bx1, by1 in blocks:
            if by1 <= row_top or by0 >= row_bottom:
                continue
            rest = []
            for a, b in spans:
                if bx1 <= a or bx0 >= b:
                    rest.append((a, b))
                    continue
                cut = True
                if bx0 > a:
                    rest.append((a, bx0))
                if bx1 < b:
                    rest.append((bx1, b))
            spans = rest
        best = None
        for span in spans:
            if best is None or span[1] - span[0] > best[1] - best[0]:
                best = span
        return best, cut

    def fill(rows: list[_Row]) -> bool:
        for kind in kinds:
            own = [row for row in rows if row.kind == kind]
            room = sum(row.capacity for row in own)
            if any(row.capacity < 1 for row in own) or room < counts[kind]:
                return False
            for _ in range(counts[kind]):
                pick = min(
                    (row for row in own if row.count < row.capacity),
                    key=lambda row: row.count,
                )
                pick.count += 1
        return True

    def arrange(split: list[int], scale: float) -> list[_Row] | None:
        between = gap * scale
        sized = [
            (
                kind,
                sizes[kind][0] * scale,
                sizes[kind][1] * scale,
            )
            for kind, count in zip(kinds, split, strict=True)
            for _ in range(count)
        ]
        depth = sum(h for _, _, h in sized) + between * (len(sized) - 1)
        if depth > 2 * ry + 1e-9:
            return None
        shifts = [0.0]
        for _, by0, _, by1 in blocks:
            for shift in (by0 - (cy + depth / 2), by1 - (cy - depth / 2)):
                if abs(shift) > 1e-9 and abs(shift) + depth / 2 <= ry + 1e-9:
                    shifts.append(shift)
        shifts.sort(key=abs)
        narrowed = None
        for shift in shifts:
            row_top = cy + shift - depth / 2
            cut = False
            rows = []
            for kind, w, h in sized:
                span, cuts = free_span(row_top, row_top + h)
                cut = cut or cuts
                room = span[1] - span[0] if span else 0.0
                capacity = (
                    math.floor((room + between + 1e-9) / (w + between)) if span else 0
                )
                rows.append(_Row(kind, w, h, row_top, span, capacity))
                row_top += h + between
            if not fill(rows):
                continue
            if not cut:
                return rows
            narrowed = narrowed or rows
        return narrowed

    scale = 1.0
    while True:
        for count in range(len(kinds), total + 1):
            for split in _row_splits(count, len(kinds)):
                arranged = arrange(split, scale)
                if arranged is None:
                    continue
                between = gap * scale
                pieces = []
                for row in arranged:
                    assert row.span is not None
                    length = row.count * row.w + (row.count - 1) * between
                    start = max(row.span[0], min(cx - length / 2, row.span[1] - length))
                    for index in range(row.count):
                        x = start + index * (row.w + between)
                        pieces.append((row.kind, (x, row.top, row.w, row.h)))
                return scale, pieces
        if scale <= min_scale + 1e-9:
            return scale, []
        scale = max(min_scale, round(scale - 0.05, 2))
