"""Draw the project's own Uprising board (docs/own-pictures-plan.md stage 3).

The public build has no board scan, so the play page used to fall back to
the text board. This script draws a board of our own at the scan's
proportions (6012 x 6005) from the project's own tables: every place the
page puts a piece (``display.board_layout``) gets its printed mark, and each
space prints its name, Agent icon, cost and effects in our notation, the
icons being our own drawings (``static/pictures/icons``, embedded as
symbols so the file stands alone). Because the coordinates are the scan's,
the board screen draws Agents, Spies, cubes and cards on it unchanged.

It writes ``static/pictures/board/uprising.svg`` (English space names) and
``uprising_ko.svg``: the Korean edition's board prints only the space names
in Korean (every other word stays English), and so does ours. The original
board, Rise of Ix's pieces and the two board tiles get the same ``_ko``
twins (user 2026-11-11: the Korean names are official for every board).
``--check`` fails when any drawing is stale.

    uv run python scripts/own_pictures/board.py [--check]
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# Wrap each block of rows with its box, for an overflow check (not in the files).
FIT_DEBUG = bool(os.environ.get("BOARD_FIT_DEBUG"))
sys.path.insert(0, str(REPO / "src"))

from dune_imperium.content.uprising import OBSERVATION_POSTS  # noqa: E402
from dune_imperium.display import board_layout as L  # noqa: E402
from dune_imperium.display import board_layout_imperium as LI  # noqa: E402
from dune_imperium.server.catalog import build_catalog  # noqa: E402

PICTURES = REPO / "src/dune_imperium/server/static/pictures"
OUT = PICTURES / "board"
W, H = 6012, 6005

FONT = "Avenir Next, Segoe UI, Helvetica Neue, Arial, sans-serif"
FONT_KO = "Apple SD Gothic Neo, Malgun Gothic, Noto Sans KR, sans-serif"
SERIF = "Georgia, Times New Roman, serif"

FACTIONS = ("emperor", "spacing_guild", "bene_gesserit", "fremen")
FACTION_NAMES = {
    "emperor": "EMPEROR",
    "spacing_guild": "SPACING GUILD",
    "bene_gesserit": "BENE GESSERIT",
    "fremen": "FREMEN",
}
FACTION_PANEL = {
    "emperor": ("#3c3c40", "#262629"),
    "spacing_guild": ("#5c2024", "#3a1416"),
    "bene_gesserit": ("#4e2e72", "#311c4a"),
    "fremen": ("#2c4268", "#1c2a44"),
}
FACTION_TEXT = {
    "emperor": "#b9b9c2",
    "spacing_guild": "#e07a7e",
    "bene_gesserit": "#b590e0",
    "fremen": "#8fb4ea",
}
# The bonus each strip prints at Influence 4 [Main p. 7],
# docs/rules/uprising-systems.md.
FOUR_BONUS = {
    "emperor": "{spy}",
    "spacing_guild": "{solari:3}",
    "bene_gesserit": "{intrigue}",
    "fremen": "{water}",
}

# What each space prints beside its frame, in our notation: rows of icons
# ({icon}, {icon:N} for a number inside a resource), "|" separating rows.
# Our transcription of the printed board, checked against the rules'
# space table (docs/rules/board-spaces.md).
SPACE_PRINT = {
    "sardaukar": "{intrigue}|{troop}{troop}|{troop}{troop}",
    "dutiful_service": "{contract}",
    "heighliner": "{troop}{troop}|{troop}{troop}{troop}",
    "deliver_supplies": "{water}",
    "espionage": "{draw} {spy}",
    "secrets": "{intrigue}|{steal_intrigue}",
    "desert_tactics": "{troop} {trash}",
    "fremkit": "{draw}",
    "high_council": "",
    "imperial_privilege": (
        "{trash_intrigue} {arrow_right}"
        " {intrigue}|{recall_agent} {draw}"
    ),
    "swordmaster": "{agent}",
    "assembly_hall": "{intrigue} {persuasion:1}",
    "gather_support": (
        "{solari:0} {arrow_right}"
        " {troop}{troop}|{solari:2} {arrow_right} {troop}{troop}{water}"
    ),
    "shipping": "{solari:5}|{influence_any}",
    "accept_contract": "{contract}|{draw}",
    "research_station": "{troop}{troop}|{draw}{draw}",
    "spice_refinery": (
        "{spice:0} {arrow_right}"
        " {solari:2}|{spice:1} {arrow_right} {solari:4}"
    ),
    "arrakeen": "{troop} {draw}",
    "sietch_tabr": "{maker_hooks} {troop} {water}|OR|{water} {shield_wall}",
    "imperial_basin": "{spice:1} + {maker}",
    "hagga_basin": "{spice:2} OR {maker_hooks}: {sandworm}",
    "deep_desert": "{spice:4} OR {maker_hooks}: {sandworm}{sandworm}",
}
# Spaces that print many icons in a narrow panel, smaller (percent of height).
ROW_HEIGHT = {
    "heighliner": 2.0,
    "imperium_heighliner": 1.75,
    "sardaukar": 2.0,
    "sell_melange": 2.1,
    "deep_desert": 1.8,
    "hagga_basin": 2.0,
}
# Spaces whose printed requirement tag reads "<Faction> 2 Influence".
REQUIREMENT_TAG = {
    "imperial_privilege": "emperor",
    "sietch_tabr": "fremen",
    "shipping": "spacing_guild",
}
# How far right of its frame each space's icon panel runs (percent of width).
PANEL_RIGHT = {
    "sardaukar": 27.0,
    "dutiful_service": 27.0,
    "heighliner": 27.0,
    "deliver_supplies": 27.0,
    "espionage": 27.0,
    "secrets": 27.0,
    "desert_tactics": 27.0,
    "fremkit": 27.0,
    "high_council": 63.0,
    "imperial_privilege": 47.0,
    "swordmaster": 63.0,
    "assembly_hall": 81.0,
    "gather_support": 81.0,
    "shipping": 97.0,
    "accept_contract": 97.0,
    "research_station": 53.6,
    "spice_refinery": 74.4,
    "arrakeen": 91.0,
    "sietch_tabr": 46.0,
    "imperial_basin": 90.4,
    "hagga_basin": 66.6,
    "deep_desert": 48.4,
}
CONTROL_BONUS = {
    "arrakeen": "{solari:1}",
    "spice_refinery": "{solari:1}",
    "imperial_basin": "{spice:1}",
}


def X(p: float) -> float:
    return p / 100 * W


def Y(p: float) -> float:
    return p / 100 * H


def n(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def pts(points: Iterable[tuple[float, float]]) -> str:
    return " ".join(f"{n(x)},{n(y)}" for x, y in points)


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------ icon symbols

ICON_SIZE: dict[str, tuple[float, float]] = {}


def symbols(names: Iterable[str]) -> str:
    """Our icon drawings as <symbol>s, their ids prefixed so they stay apart."""

    out = []
    for name in sorted(set(names)):
        if name.startswith("log_"):
            source = PICTURES / "log" / f"{name[4:]}.svg"
        elif name.startswith("faction_") or name == "combat":
            # The Faction badges printed conditions use (the card faces' own).
            source = PICTURES / "faces" / f"{name}.svg"
        else:
            source = PICTURES / "icons" / f"{name}.svg"
        text = source.read_text()
        head = re.search(r"<svg[^>]*viewBox=\"([^\"]+)\"[^>]*>", text)
        assert head, name
        view = head.group(1)
        if name.startswith("agent_icon_"):
            # The icon set's Agent icons are the mark alone, cropped to it;
            # the board lays the mark in the stone plate's 136 x 100 box, as
            # its sizes and places were measured with the plate.
            view = "0 0 136 100"
        vw, vh = (float(v) for v in view.split()[2:])
        ICON_SIZE[name] = (vw, vh)
        inner = text[head.end() : text.rindex("</svg>")]
        inner = re.sub(r"<!--.*?-->", "", inner, flags=re.S)
        if name.startswith("agent_icon_"):
            # The board prints the Agent marks alone: no stone plate, no well.
            inner = re.sub(r'<g class="(?:plate|well)">.*?</g>', "", inner, flags=re.S)
        ids = re.findall(r'id="([^"]+)"', inner)
        for old in ids:
            inner = inner.replace(f'id="{old}"', f'id="{name}-{old}"').replace(
                f"url(#{old})", f"url(#{name}-{old})"
            )
        out.append(f'<symbol id="i-{name}" viewBox="{view}">{inner.strip()}</symbol>')
    return "\n".join(out)


def use(name: str, cx: float, cy: float, height: float) -> str:
    vw, vh = ICON_SIZE[name]
    width = height * vw / vh
    return (
        f'<use href="#i-{name}" x="{n(cx - width / 2)}" y="{n(cy - height / 2)}" '
        f'width="{n(width)}" height="{n(height)}"/>'
    )


def icon_width(name: str, height: float) -> float:
    vw, vh = ICON_SIZE[name]
    return height * vw / vh


def numbered(kind: str, value: str, cx: float, cy: float, size: float) -> str:
    """A resource with its number inside, as print draws it."""

    if kind == "solari":
        return (
            f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(size * 0.5)}" '
            f'fill="url(#g-coin)" stroke="#3a3a3a" stroke-width="{n(size * 0.05)}"/>'
            + num(value, cx, cy, size * 0.62, "#222")
        )
    if kind == "spice":
        hexagon = [
            (
                cx + size * 0.55 * math.cos(math.pi / 3 * k),
                cy + size * 0.48 * math.sin(math.pi / 3 * k),
            )
            for k in range(6)
        ]
        return (
            f'<polygon points="{pts(hexagon)}" fill="url(#g-spice)" stroke="#5a1a04" '
            f'stroke-width="{n(size * 0.05)}"/>'
            + num(value, cx, cy, size * 0.6, "#fff")
        )
    if kind == "persuasion":
        d = size * 0.55
        return (
            '<polygon '
            f'points="{pts([(cx, cy - d), (cx + d, cy), (cx, cy + d), (cx - d, cy)])}" '
            f'fill="url(#g-pz)" stroke="#f4f8ff" stroke-width="{n(size * 0.07)}"/>'
            + num(value, cx, cy, size * 0.6, "#fff")
        )
    raise ValueError(kind)


def num(value: str, cx: float, cy: float, size: float, color: str) -> str:
    return (
        f'<text x="{n(cx)}" y="{n(cy + size * 0.36)}" text-anchor="middle" '
        f'font-family="{FONT}" font-weight="800" '
        f'font-size="{n(size)}" fill="{color}">{esc(value)}</text>'
    )


TOKEN = re.compile(r"(\{[a-z_0-9]+(?::[0-9+]+)?\})")
NUMBERED = {"solari", "spice", "persuasion"}


def row_items(
    row: str, height: float, ko: bool
) -> list[tuple[float, Callable[[float, float], str]]]:
    """A printed row as (width, draw(x_left, cy)) items."""

    items: list[tuple[float, Callable[[float, float], str]]] = []
    for token in TOKEN.split(row):
        if not token.strip():
            if token:
                items.append((height * 0.25, lambda x, cy: ""))
            continue
        match = re.fullmatch(r"\{([a-z_0-9]+)(?::([0-9+]+))?\}", token)
        if match and match.group(1) in NUMBERED and match.group(2) is not None:
            kind, value = match.group(1), match.group(2)
            size = height * (1.0 if kind != "persuasion" else 1.1)
            items.append(
                (
                    size,
                    lambda x, cy, k=kind, v=value, s=size: numbered(
                        k, v, x + s / 2, cy, s
                    ),
                )
            )
        elif match and match.group(1) == "dna":
            # A genetic marker: a red diamond with a white twist, our shape.
            w = height * 0.8
            items.append(
                (
                    w,
                    lambda x, cy, ww=w, hh=height: (
                        f'<polygon points="{
                            pts(
                                [
                                    (x + ww / 2, cy - hh / 2),
                                    (x + ww, cy),
                                    (x + ww / 2, cy + hh / 2),
                                    (x, cy),
                                ]
                            )
                        }" fill="#c8243a" stroke="#f2d0d8" '
                        f'stroke-width="{n(hh * 0.05)}"/>'
                        f'<path d="M{n(x + ww * 0.36)},{n(cy - hh * 0.26)} '
                        f'C{n(x + ww * 0.7)},{n(cy - hh * 0.1)} '
                        f'{n(x + ww * 0.3)},{n(cy + hh * 0.1)} '
                        f'{n(x + ww * 0.64)},{n(cy + hh * 0.26)} '
                        f'M{n(x + ww * 0.64)},{n(cy - hh * 0.26)} '
                        f'C{n(x + ww * 0.3)},{n(cy - hh * 0.1)} '
                        f'{n(x + ww * 0.7)},{n(cy + hh * 0.1)} '
                        f'{n(x + ww * 0.36)},{n(cy + hh * 0.26)}" '
                        f'fill="none" stroke="#fff" stroke-width="{n(hh * 0.06)}"/>'
                    ),
                )
            )
        elif match and match.group(1) == "foldspace":
            # The Foldspace card: a red card with a whirl, our own shape.
            w = height * 0.66
            items.append(
                (
                    w,
                    lambda x, cy, ww=w, hh=height: (
                        f'<rect x="{n(x)}" y="{n(cy - hh / 2)}" width="{n(ww)}" '
                        f'height="{n(hh)}" rx="{n(hh * 0.08)}" fill="#1a1a1a" '
                        f'stroke="#f2f2f2" stroke-width="{n(hh * 0.04)}"/>'
                        f'<circle cx="{n(x + ww / 2)}" cy="{n(cy)}" r="{n(ww * 0.34)}" '
                        f'fill="none" stroke="#d8262c" stroke-width="{n(hh * 0.07)}"/>'
                        f'<circle cx="{n(x + ww / 2)}" cy="{n(cy)}" r="{n(ww * 0.16)}" '
                        'fill="#d8262c"/>'
                    ),
                )
            )
        elif match:
            name = match.group(1)
            h = height * (0.55 if name == "arrow_right" else 1.0)
            w = icon_width(name, h)
            items.append(
                (w, lambda x, cy, nm=name, hh=h, ww=w: use(nm, x + ww / 2, cy, hh))
            )
        else:
            word = token.strip()
            size = height * 0.42
            # Hangul and other wide letters take about a full em, Latin about half.
            w = sum(size * (0.95 if ord(c) > 0x2E7F else 0.56) for c in word)
            w += height * 0.1
            items.append(
                (
                    w,
                    lambda x, cy, t=word, s=size, ww=w: (
                        f'<text x="{n(x + ww / 2)}" y="{n(cy + s * 0.36)}" '
                        f'text-anchor="middle" font-family="{FONT}" '
                        f'font-weight="700" font-size="{n(s)}" fill="#f2ede2">'
                        f'{esc(t)}</text>'
                    ),
                )
            )
    return items


def rows(
    text: str,
    left: float,
    right: float,
    cy: float,
    height: float,
    ko: bool,
    gap: float,
    max_h: float | None = None,
) -> str:
    """Rows of printed icons centred in [left, right] around cy. Rows wider
    than the room, or a stack taller than ``max_h``, are drawn smaller so
    they stay inside the box (print never lets an effect spill out)."""

    lines = [r for r in text.split("|") if r]
    if not lines:
        return ""

    def widest(h: float) -> float:
        best = 0.0
        for line in lines:
            items = row_items(line, h, ko)
            best = max(best, sum(w for w, _ in items) + h * 0.12 * (len(items) - 1))
        return best

    room = (right - left) * 0.96
    scale = min(1.0, room / widest(height))
    total = len(lines) * height + (len(lines) - 1) * gap
    if max_h is not None and total * scale > max_h:
        scale = max_h / total
    height, gap = height * scale, gap * scale
    out = []
    total = len(lines) * height + (len(lines) - 1) * gap
    y = cy - total / 2 + height / 2
    for line in lines:
        items = row_items(line, height, ko)
        spacing = height * 0.12
        width = sum(w for w, _ in items) + spacing * (len(items) - 1)
        x = (left + right) / 2 - width / 2
        for w, draw in items:
            out.append(draw(x, y))
            x += w + spacing
        y += height + gap
    body = "".join(out)
    if FIT_DEBUG:
        half_h = max_h / 2 if max_h is not None else 0.0
        top, bottom = cy - half_h, cy + half_h
        body = f'<g data-fit="{n(left)} {n(right)} {n(top)} {n(bottom)}">{body}</g>'
    return body


# ----------------------------------------------------------------- pieces


def frame(
    box: tuple[float, float, float, float], square_bottom_left: bool = False
) -> str:
    left, top, width, height = X(box[0]), Y(box[1]), X(box[2]), Y(box[3])
    cx, cy = width * L.SPACE_FRAME_CUT[0] / 100, height * L.SPACE_FRAME_CUT[1] / 100
    outline = [
        (left, top),
        (left + width - cx, top),
        (left + width, top + cy),
        (left + width, top + height),
        *(
            [(left, top + height)]
            if square_bottom_left
            else [(left + cx, top + height), (left, top + height - cy)]
        ),
    ]
    return (
        f'<polygon points="{pts(outline)}" fill="url(#g-frame)" stroke="#f2f0ea" '
        'stroke-width="13" stroke-linejoin="round"/>'
    )


def post(x: float, y: float) -> str:
    r = X(L.POST_SIZE) / 2
    cx, cy = X(x), Y(y)
    return (
        f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r)}" fill="#4a4844" stroke="#cfcac0" '
        'stroke-width="10"/>'
        f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r * 0.72)}" fill="none" '
        'stroke="#8e8a82" stroke-width="5"/>'
        f'<path d="M{n(cx - r * 0.55)},{n(cy)} Q{n(cx)},{n(cy - r * 0.42)} '
        f'{n(cx + r * 0.55)},{n(cy)} Q{n(cx)},{n(cy + r * 0.42)} '
        f'{n(cx - r * 0.55)},{n(cy)} Z" fill="#e8e4dc"/>'
        f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(r * 0.17)}" fill="#3a3834"/>'
    )


def chevron_band(
    y: float,
    left: float,
    right: float,
    rise: float,
    half: float,
    fill: str,
    stroke: str,
) -> str:
    mid = (left + right) / 2
    p = [
        (left, y - half + rise),
        (mid, y - half),
        (right, y - half + rise),
        (right, y + half + rise),
        (mid, y + half),
        (left, y + half + rise),
    ]
    return (
        f'<polygon points="{pts(p)}" fill="{fill}" stroke="{stroke}" '
        'stroke-width="6" stroke-linejoin="round"/>'
    )


def faction_strip(faction: str, ko: bool) -> str:
    offset = L.INFLUENCE_STRIP_OFFSET_Y[faction]
    top, bottom = Y(offset + 0.3), Y(offset + 24.2)
    # Room under the bottom squares (the original board's sit lower).
    size = X(L.INFLUENCE_CUBE_SIZE)
    bottom = max(bottom, Y(L.INFLUENCE_LEVEL_Y[0] + offset) + size * 0.66)
    light, dark = FACTION_PANEL[faction]
    mid_x = sum(L.INFLUENCE_SEAT_X) / len(L.INFLUENCE_SEAT_X)
    out = [
        f'<rect x="{n(X(12.9))}" y="{n(top)}" width="{n(X(14.6))}" '
        f'height="{n(bottom - top)}" rx="40" fill="url(#g-{faction})" '
        'stroke="#00000066" stroke-width="8"/>',
        f'<rect x="{n(X(mid_x - 4.6))}" y="{n(top)}" width="{n(X(9.2))}" '
        f'height="{n(bottom - top)}" rx="24" fill="#16140f" stroke="#3a342a" '
        'stroke-width="8"/>',
    ]
    name = FACTION_NAMES[faction]
    mid = (top + bottom) / 2
    out.append(
        f'<text transform="translate({n(X(1.75))} {n(mid)}) rotate(-90)" '
        f'text-anchor="middle" font-family="{SERIF}" '
        f'font-size="{n(Y(1.45))}" letter-spacing="{n(Y(0.25))}" '
        f'fill="{FACTION_TEXT[faction]}">{esc(name)}</text>'
    )
    levels = L.INFLUENCE_LEVEL_Y
    # Centred on the four seat squares (each board measures its own).
    left, right = X(mid_x - 4.2), X(mid_x + 4.2)
    for level in range(1, 7):
        y = Y(levels[level] + offset)
        out.append(
            chevron_band(y, left, right, Y(0.45), Y(1.45), "url(#g-band)", "#5a4c34")
        )
    # The Alliance line between 3 and 4 [Main p. 7].
    y4 = Y((levels[3] + levels[4]) / 2 + offset)
    out.append(
        f'<polyline points="{
            pts(
                [
                    (left, y4 + Y(0.5)),
                    ((left + right) / 2, y4),
                    (right, y4 + Y(0.5)),
                ]
            )
        }" fill="none" stroke="#e8822a" stroke-width="22" stroke-linejoin="round"/>'
    )
    # Influence 2: a victory point; Influence 4: the strip's bonus.
    out.append(use("victory_point", X(mid_x), Y(levels[2] + offset), Y(2.6)))
    bonus = FOUR_BONUS[faction]
    out.append(
        rows(bonus, X(3.4), X(5.6), Y(levels[4] + offset), Y(2.3), ko, 0, max_h=Y(2.6))
    )
    # Influence 0: four squares, one per seat, in their frame as printed.
    xs = L.INFLUENCE_SEAT_X
    y0 = Y(levels[0] + offset)
    out.append(
        f'<rect x="{n(X(xs[0]) - size * 0.78)}" y="{n(y0 - size * 0.78)}" '
        f'width="{n(X(xs[-1]) - X(xs[0]) + size * 1.56)}" height="{n(size * 1.56)}" '
        'rx="14" fill="#221e17" stroke="#5a4c34" stroke-width="7"/>'
    )
    for sx in xs:
        out.append(
            f'<rect x="{n(X(sx) - size / 2)}" '
            f'y="{n(Y(levels[0] + offset) - size / 2)}" width="{n(size)}" '
            f'height="{n(size)}" rx="8" fill="#0c0b09" stroke="#4a4234" '
            'stroke-width="7"/>'
        )
    # The Alliance token's place: a dashed ring round the Faction's mark.
    ax, ay = X(L.ALLIANCE_POINT[0]), Y(L.ALLIANCE_POINT[1] + offset)
    r = X(L.ALLIANCE_TOKEN_SIZE) / 2
    out.append(
        f'<circle cx="{n(ax)}" cy="{n(ay)}" r="{n(r)}" fill="#c9a24a22" '
        'stroke="#c9a24a" stroke-width="10" stroke-dasharray="40 26"/>'
    )
    # Under it print shows the Faction's own emblem, large and faint gold.
    out.append(
        f'<g opacity=".42" filter="url(#f-gold)">'
        f'{use("agent_icon_" + faction, ax, ay, r * 1.5)}</g>'
    )
    return "".join(out)


def space(space_id: str, entry: dict, ko: bool) -> str:
    box = L.SPACE_BOXES[space_id]
    left, top, width, height = X(box[0]), Y(box[1]), X(box[2]), Y(box[3])
    right = X(PANEL_RIGHT[space_id])
    tag = REQUIREMENT_TAG.get(space_id)
    lift = Y(1.25) if tag else 0
    out = [
        f'<rect x="{n(left - X(1.0))}" y="{n(top - Y(2.35) - lift)}" '
        f'width="{n(right - left + X(1.0))}" height="{n(height + Y(3.0) + lift)}" '
        'rx="28" '
        f'fill="#0000004d" stroke="#ffffff1c" stroke-width="7"/>'
    ]
    name = entry.get("name_ko") if ko else entry["name"]
    # A name longer than its panel is set narrower to fit, as print does.
    room = right - left - X(0.4)
    guess = len(name) * Y(1.2) * (1.0 if ko else 0.8)
    fit = (
        f' textLength="{n(room)}" lengthAdjust="spacingAndGlyphs"'
        if guess > room
        else ""
    )
    out.append(
        f'<text x="{n(left)}" y="{n(top - Y(0.7) - lift)}" '
        f'font-family="{FONT_KO if ko else FONT}" font-weight="700" '
        f'font-size="{n(Y(1.2))}" letter-spacing="{n(0 if ko else Y(0.08))}" '
        f'fill="#ece6da"{fit}>{esc(name if ko else name.upper())}</text>'
    )
    if tag:
        # The requirement tag under the name, as print sets it.
        label = "2 Influence"
        out.append(
            f'<rect x="{n(left)}" y="{n(top - Y(1.6))}" width="{n(X(6.9))}" '
            f'height="{n(Y(1.3))}" rx="12" fill="#203a5a" stroke="#6a8ab0" '
            'stroke-width="5"/>'
        )
        # The Faction's mark on its dark badge, as printed conditions show it.
        out.append(use(f"faction_{tag}", left + X(0.62), top - Y(0.95), Y(1.08)))
        out.append(
            f'<text x="{n(left + X(1.45))}" y="{n(top - Y(0.62))}" '
            f'font-family="{FONT}" font-size="{n(Y(0.9))}" fill="#e8eef6" '
            f'textLength="{n(X(5.1))}" lengthAdjust="spacingAndGlyphs">'
            f'{label}</text>'
        )
    out.append(frame(box, space_id in getattr(L, "SQUARE_BOTTOM_LEFT", ())))
    if entry.get("combat"):
        # Combat: the crossed swords print sets in the frame's corner.
        out.append(
            use("combat", left + width * 0.85, top + height * 0.79, height * 0.34)
        )
    # The Agent mark inside the frame's top-left corner, as print sets it.
    out.append(
        use(f"agent_icon_{entry['agent_icon']}", left + X(0.95), top + Y(1.45), Y(2.6))
    )
    # The cost, under the Agent icon, as print stacks it.
    costs = []
    for option in entry["options"]:
        cost = option["cost"]
        for kind in ("spice", "solari", "water"):
            if cost.get(kind):
                costs.append((kind, cost[kind]))
    if space_id in ("gather_support", "spice_refinery", "sell_melange"):
        costs = []  # the choice of cost is printed with each row
    seen = []
    cy = top + Y(3.45)
    for kind, value in costs:
        if (kind, value) in seen:
            continue
        seen.append((kind, value))
        if kind == "water":
            for k in range(value):
                out.append(use("water", left + X(0.62) + k * X(0.7), cy, Y(1.5)))
        else:
            out.append(numbered(kind, str(value), left + X(0.95), cy, Y(1.75)))
        cy += Y(2.0)
    printed = SPACE_PRINT[space_id]
    if printed:
        out.append(
            rows(
                printed,
                left + width + X(0.4),
                right - X(0.4),
                top + height / 2 + Y(ROW_SHIFT.get(space_id, 0)),
                Y(ROW_HEIGHT.get(space_id, 2.35)),
                ko,
                Y(0.4),
                max_h=height + Y(1.6),
            )
        )
    if space_id in ONCE_PER_GAME:
        out.append(
            f'<text x="{n(left + width * 0.66)}" y="{n(top + height - Y(0.5))}" '
            f'text-anchor="middle" font-family="{FONT_KO if ko else FONT}" '
            f'font-size="{n(Y(0.9))}" fill="#f2ede2">Once/game</text>'
        )
    return "".join(out)


def high_council(ko: bool) -> str:
    box = L.SPACE_BOXES["high_council"]
    top = Y(box[1])
    first, later = "1st:", "2nd+:"
    seats = "".join(
        f'<circle cx="{n(X(x))}" cy="{n(Y(y))}" r="{n(X(L.SEAT_DISC_SIZE) / 2)}" '
        'fill="#1a1a18" stroke="#e8e4dc" stroke-width="9"/>'
        for x, y in L.COUNCIL_SEATS
    )
    font = FONT
    return (
        f'<text x="{n(X(38.8))}" y="{n(Y(5.55))}" font-family="{font}" '
        f'font-weight="700" font-size="{n(Y(0.9))}" fill="#f2ede2">{first}</text>'
        + seats
        + numbered("persuasion", "2", X(58.6), Y(5.22), Y(4.2))
        + f'<text x="{n(X(38.8))}" y="{n(top + Y(5.55))}" font-family="{font}" '
          f'font-weight="700" font-size="{n(Y(0.9))}" fill="#f2ede2">{later}</text>'
        + rows(
            "{spice:2}{intrigue}{troop}{troop}{troop}",
            X(41.0),
            X(51.5),
            top + Y(5.25),
            Y(1.9),
            ko,
            0,
        )
    )


def control_flag(space_id: str) -> str:
    left, top, width, height = (v for v in L.CONTROL_FLAG_BOXES[space_id])
    lx, ty, w, h = X(left), Y(top), X(width), Y(height)
    notch = h * L.CONTROL_FLAG_NOTCH
    flag = [
        (lx, ty),
        (lx + w, ty),
        (lx + w, ty + h),
        (lx + w / 2, ty + h - notch),
        (lx, ty + h),
    ]
    return (
        f'<polygon points="{pts(flag)}" fill="#2a2a2a" stroke="#e8e4dc" '
        'stroke-width="9" stroke-linejoin="round"/>'
        + rows(
            "{arrow_right} " + CONTROL_BONUS[space_id],
            lx + w,
            lx + w + X(3.6),
            ty + h * 0.55,
            Y(1.7),
            False,
            0,
            max_h=h * 0.9,
        )
    )


def maker_hex(space_id: str) -> str:
    cx, cy = X(L.MAKER_SPICE_POINTS[space_id][0]), Y(L.MAKER_SPICE_POINTS[space_id][1])
    w, h = X(L.MAKER_SPICE_SIZE[0]), Y(L.MAKER_SPICE_SIZE[1])
    hexagon = [
        (cx + w / 2 * math.cos(math.pi / 3 * k), cy + h / 2 * math.sin(math.pi / 3 * k))
        for k in range(6)
    ]
    return (
        f'<polygon points="{pts(hexagon)}" fill="#1c1a18" stroke="#f2f0ea" '
        'stroke-width="9"/>'
        + use("maker", cx, cy, h * 0.78)
    )


def card_slot(box: tuple[float, float, float, float], label: str = "") -> str:
    left, top, width, height = X(box[0]), Y(box[1]), X(box[2]), Y(box[3])
    return (
        f'<rect x="{n(left)}" y="{n(top)}" width="{n(width)}" height="{n(height)}" '
        'rx="30" fill="#ffffff10" stroke="#ffffff30" stroke-width="8" '
        'stroke-dasharray="36 22"/>'
        + label
    )


def conflict_area(ko: bool) -> str:
    rings = L.GARRISON_RINGS
    left = min(r[0] for r in rings) - 0.6
    right = max(r[0] + r[2] for r in rings) + 0.6
    top = min(r[1] for r in rings) - 0.6
    bottom = max(r[1] + r[3] for r in rings) + 0.6
    out = [
        f'<rect x="{n(X(left))}" y="{n(Y(top))}" width="{n(X(right - left))}" '
        f'height="{n(Y(bottom - top))}" rx="40" fill="#00000038" stroke="#ffffff22" '
        'stroke-width="8"/>'
    ]
    field_left, field_right = L._FIELD_LEFT, L._FIELD_RIGHT
    field_top, field_bottom = L._FIELD_TOP, L._FIELD_BOTTOM
    # The crossed blades the field prints under the units.
    cx, cy = X(L.CONFLICT_CROSS[0]), Y(L.CONFLICT_CROSS[1])
    out.append(
        f'<g opacity=".09">{use("sword", cx - X(2.5), cy, Y(18))}<g '
        f'transform="translate({n(2 * cx)} 0) scale(-1 1)">'
        f'{use("sword", cx - X(2.5), cy, Y(18))}</g></g>'
    )
    out.append(
        f'<path d="M{n(X(field_left))},{n(cy)} H{n(X(field_right))} '
        f'M{n(cx)},{n(Y(field_top))} V{n(Y(field_bottom))}" stroke="#ffffff30" '
        'stroke-width="8"/>'
    )
    for left, top, width, height in L.GARRISON_RINGS:
        rx, ry = X(left + width / 2), Y(top + height / 2)
        r = X(width) / 2
        out.append(
            f'<circle cx="{n(rx)}" cy="{n(ry)}" r="{n(r)}" fill="#00000030" '
            'stroke="#d8d2c4" stroke-width="10" opacity=".7"/>'
        )
    for x, y in getattr(L, "MAKER_HOOKS_POINTS", ()):
        w, h = X(L.MAKER_HOOKS_SIZE[0]), Y(L.MAKER_HOOKS_SIZE[1])
        out.append(
            f'<rect x="{n(X(x) - w / 2)}" y="{n(Y(y) - h / 2)}" width="{n(w)}" '
            f'height="{n(h)}" rx="18" fill="none" stroke="#d8d2c455" stroke-width="7" '
            'stroke-dasharray="22 16"/>'
        )
    return "".join(out)


def strength_track() -> str:
    out = []
    zl, zt, zw, zh = L.STRENGTH_ZERO_BOX
    out.append(
        f'<rect x="{n(X(zl))}" y="{n(Y(zt))}" width="{n(X(zw))}" height="{n(Y(zh))}" '
        'rx="24" fill="#3a1414" stroke="#a83232" stroke-width="9"/>'
    )
    zx, zy = getattr(L, "STRENGTH_ZERO_POINT", (zl + zw / 2, zt + zh / 2))
    radius = min(X(2.6), min(X(zw), Y(zh)) * 0.4)
    out.append(
        f'<circle cx="{n(X(zx))}" cy="{n(Y(zy))}" r="{n(radius)}" fill="none" '
        'stroke="#e8d0c0" stroke-width="9"/>'
    )
    pitch = L.STRENGTH_CELL_X[2] - L.STRENGTH_CELL_X[1]
    cell_w, cell_h = X(pitch * 0.94), Y(4.3)
    for index, row_y in enumerate(L.STRENGTH_ROW_Y):
        for column in range(1, 11):
            value = column + index * 10
            cx, cy = X(L.STRENGTH_CELL_X[column]), Y(row_y) - Y(1.7)
            out.append(
                f'<rect x="{n(cx - cell_w / 2)}" y="{n(cy - cell_h / 2)}" '
                f'width="{n(cell_w)}" height="{n(cell_h)}" rx="16" fill="#241a18" '
                'stroke="#5a3a34" stroke-width="7"/>'
            )
            out.append(
                f'<rect x="{n(cx - cell_w / 2)}" y="{n(Y(row_y) - Y(0.75))}" '
                f'width="{n(cell_w)}" height="{n(Y(1.5))}" fill="#8e2222"/>'
            )
            out.append(num(str(value), cx, Y(row_y), Y(1.25), "#f6e6e0"))
    return "".join(out)


def victory_track() -> str:
    out = []
    w, h = X(L.VICTORY_POINT_CELL[0]), Y(L.VICTORY_POINT_CELL[1])
    cx = X(L.VICTORY_POINT_X)
    out.append(
        f'<rect x="{n(cx - w / 2 - X(0.3))}" '
        f'y="{n(Y(L.VICTORY_POINT_Y[12]) - h / 2 - Y(0.3))}" width="{n(w + X(0.6))}" '
        f'height="{
            n(Y(L.VICTORY_POINT_Y[0]) - Y(L.VICTORY_POINT_Y[12]) + h + Y(0.6))
        }" rx="30" fill="#141210" stroke="#3a342a" stroke-width="8"/>'
    )
    for level, y in enumerate(L.VICTORY_POINT_Y):
        cy = Y(y)
        if level >= 10:
            out.append(
                f'<rect x="{n(cx - w / 2)}" y="{n(cy - h / 2)}" width="{n(w)}" '
                f'height="{n(h)}" fill="url(#g-goldcell)"/>'
            )
        out.append(
            f'<path d="M{n(cx - w * 0.32)},{n(cy + h / 2)} H{n(cx + w * 0.32)}" '
            'stroke="#ffffff33" stroke-width="6" stroke-dasharray="6 26"/>'
        )
        out.append(
            num(str(level), cx, cy, Y(2.0), "#f2ede2" if level < 10 else "#fff3c8")
        )
    out.append(use("victory_point", cx, Y(L.VICTORY_POINT_Y[12]) - h * 1.05, h * 1.0))
    one = Y(L.VICTORY_POINT_Y[1])
    out.append(
        f'<text x="{n(cx + w * 0.28)}" y="{n(one - h * 0.3)}" text-anchor="middle" '
        f'font-family="{FONT}" font-weight="800" font-size="{n(Y(0.9))}" '
        'fill="#f0c040">4P</text>'
    )
    return "".join(out)


def posts_and_lines() -> str:
    out = []
    by_space = {space_id: L.SPACE_BOXES[space_id] for space_id in L.SPACE_BOXES}
    for post_id, (x, y) in L.POST_POINTS.items():
        spaces = next(
            p.connected_space_ids for p in OBSERVATION_POSTS if p.post_id == post_id
        )
        for space_id in spaces:
            box = by_space.get(space_id)
            if not box:
                continue
            fx, fy = X(box[0] + box[2]), Y(box[1])
            out.append(
                f'<polyline points="{pts([(fx, fy + Y(0.2)), (X(x), Y(y))])}" '
                'fill="none" stroke="#e8e4dc" stroke-width="9" opacity=".75"/>'
            )
    for x, y in L.POST_POINTS.values():
        out.append(post(x, y))
    return "".join(out)


DEFS = (
    '<linearGradient id="g-frame" x1="0" y1="0" x2="1" y2="1"><stop offset="0" '
    'stop-color="#3a352c"/><stop offset="1" stop-color="#16130f"/></linearGradient>'
    '<linearGradient id="g-band" x1="0" y1="0" x2="0" y2="1"><stop offset="0" '
    'stop-color="#4a4030"/><stop offset="1" stop-color="#2a241a"/></linearGradient>'
    '<linearGradient id="g-goldcell" x1="0" y1="0" x2="0" y2="1"><stop offset="0" '
    'stop-color="#9a7a2a"/><stop offset="1" stop-color="#5a4410"/></linearGradient>'
    '<radialGradient id="g-coin" cx=".4" cy=".35" r=".75"><stop offset="0" '
    'stop-color="#fafafa"/><stop offset="1" stop-color="#9a9a9a"/></radialGradient>'
    '<linearGradient id="g-spice" x1="0" y1="0" x2="0" y2="1"><stop offset="0" '
    'stop-color="#f08a3a"/><stop offset="1" stop-color="#c2401a"/></linearGradient>'
    '<linearGradient id="g-pz" x1="0" y1="0" x2="1" y2="1"><stop offset="0" '
    'stop-color="#64aee6"/><stop offset="1" stop-color="#2a5f9e"/></linearGradient>'
    '<radialGradient id="g-desert" cx=".62" cy=".55" r=".75"><stop offset="0" '
    'stop-color="#9a6436"/><stop offset=".6" stop-color="#6e4222"/><stop offset="1" '
    'stop-color="#3e2614"/></radialGradient>'
    '<linearGradient id="g-landsraad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" '
    'stop-color="#34452f"/><stop offset="1" stop-color="#1f2a1c"/></linearGradient>'
    '<linearGradient id="g-choam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" '
    'stop-color="#8a4c26"/><stop offset="1" stop-color="#55301a"/></linearGradient>'
    '<linearGradient id="g-tanks" x1="0" y1="0" x2="1" y2="1"><stop offset="0" '
    'stop-color="#1c1428"/><stop offset=".6" stop-color="#26163a"/><stop offset="1" '
    'stop-color="#3a1a4a"/></linearGradient>'
    '<linearGradient id="g-tile" x1="0" y1="0" x2="1" y2="1"><stop offset="0" '
    'stop-color="#a8703a"/><stop offset="1" stop-color="#6a4020"/></linearGradient>'
    '<radialGradient id="g-planet" cx=".45" cy=".4" r=".7"><stop offset="0" '
    'stop-color="#5a6a4a"/><stop offset=".55" stop-color="#3a3a2a"/><stop offset="1" '
    'stop-color="#1a2028"/></radialGradient>'
    + "".join(
        f'<linearGradient id="g-{f}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" '
        f'stop-color="{FACTION_PANEL[f][0]}"/><stop offset="1" '
        f'stop-color="{FACTION_PANEL[f][1]}"/></linearGradient>'
        for f in FACTIONS
    )
    # White marks turned gold (the Alliance places' faint emblems).
    + '<filter id="f-gold"><feColorMatrix type="matrix" values="0.86 0 0 0 0 '
    '0.68 0 0 0 0 0.3 0 0 0 0 0 0 0 1 0"/></filter>'
)


def board(ko: bool) -> str:
    catalog = build_catalog()
    spaces = catalog["spaces"]
    assert isinstance(spaces, dict)
    names = {
        "victory_point",
        "maker",
        "sword",
        "water",
        "spy",
        "intrigue",
        "contract",
        "influence_any",
        "troop",
        "draw",
        "trash",
        "steal_intrigue",
        "trash_intrigue",
        "recall_agent",
        "agent",
        "maker_hooks",
        "shield_wall",
        "sandworm",
        "arrow_right",
    }
    names |= {
        f"agent_icon_{icon}"
        for icon in (
            "emperor",
            "spacing_guild",
            "bene_gesserit",
            "fremen",
            "landsraad",
            "city",
            "spice_trade",
        )
    }
    names |= {f"influence_{faction}" for faction in FACTIONS}
    names |= {f"faction_{faction}" for faction in FACTIONS} | {"combat"}
    body = [symbols(names)]
    parts = [
        f'<rect width="{W}" height="{H}" fill="#1c1916"/>',
        # Arrakis: the desert map under the spaces and the Conflict.
        f'<path d="M{n(X(28.2))},{n(Y(23.5))} H{n(X(93.6))} V{n(Y(99.4))} '
        f'H{n(X(28.2))} Z" fill="url(#g-desert)"/>',
    ]
    for k in range(9):
        parts.append(
            f'<ellipse cx="{n(X(64))}" cy="{n(Y(60))}" rx="{n(X(6 + k * 5.5))}" '
            f'ry="{n(Y(4 + k * 4))}" fill="none" stroke="#ffffff" stroke-width="6" '
            'opacity=".05"/>'
        )
    # Landsraad Council and CHOAM panels across the top.
    parts.append(
        f'<rect x="{n(X(28.4))}" y="{n(Y(0.9))}" width="{n(X(53.6))}" '
        f'height="{n(Y(19.8))}" rx="40" fill="url(#g-landsraad)" stroke="#5a6a50" '
        'stroke-width="10"/>'
    )
    parts.append(
        f'<text transform="translate({n(X(29.5))} {n(Y(10.8))}) rotate(-90)" '
        f'text-anchor="middle" font-family="{SERIF}" font-size="{n(Y(1.35))}" '
        f'letter-spacing="{n(Y(0.2))}" fill="#9aae8a">LANDSRAAD COUNCIL</text>'
    )
    parts.append(
        f'<rect x="{n(X(83.4))}" y="{n(Y(0.9))}" width="{n(X(14.4))}" '
        f'height="{n(Y(19.8))}" rx="40" fill="url(#g-choam)" stroke="#a8683a" '
        'stroke-width="10"/>'
    )
    parts.append(
        f'<text transform="translate({n(X(84.4))} {n(Y(15.5))}) rotate(-90)" '
        f'text-anchor="middle" font-family="{SERIF}" font-size="{n(Y(1.35))}" '
        f'letter-spacing="{n(Y(0.2))}" fill="#f0b48a">CHOAM</text>'
    )
    for faction in FACTIONS:
        parts.append(faction_strip(faction, ko))
    for box in L.CONTRACT_SLOTS:
        parts.append(card_slot(box))
    parts.append(
        rows("{contract} : {solari:2}", X(29.4), X(39.4), Y(24.8), Y(2.2), ko, 0)
    )
    parts.append(card_slot(L.CONFLICT_DECK_SLOT))
    parts.append(card_slot(L.CONFLICT_SLOT))
    parts.append(conflict_area(ko))
    parts.append(posts_and_lines())
    for space_id in SPACE_PRINT:
        parts.append(space(space_id, spaces[space_id], ko))
    parts.append(high_council(ko))
    for space_id in L.CONTROL_FLAG_BOXES:
        parts.append(control_flag(space_id))
    for space_id in ("imperial_basin", "hagga_basin", "deep_desert"):
        parts.append(maker_hex(space_id))
    sl, st, sw, sh = L.SHIELD_WALL_BOX
    parts.append(
        f'<rect x="{n(X(sl))}" y="{n(Y(st))}" width="{n(X(sw))}" height="{n(Y(sh))}" '
        'rx="30" fill="#00000030" stroke="#f2f0ea55" stroke-width="8" '
        'stroke-dasharray="30 20"/>'
    )
    parts.append(strength_track())
    parts.append(victory_track())
    # The strength legend [Main p. 14]: a sword 1, a troop 2, a sandworm 3.
    parts.append(
        rows(
            "{sword}: 1  {troop}: 2|{sandworm}: 3",
            X(29.0),
            X(37.6),
            Y(95.6),
            Y(2.2),
            ko,
            Y(0.6),
        )
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 '
        f'0 {W} {H}">\n'
        "<!-- The Uprising board, drawn by the project from its own layout tables "
        "(scripts/own_pictures/board.py); "
        f"no scan or app picture is used. -->\n<defs>{DEFS}\n"
        + "\n".join(body)
        + "</defs>\n"
        + "\n".join(parts)
        + "\n</svg>\n"
    )


# ------------------------------------------------- the original game's board

# The original board's Influence 4 bonuses [DI p. 7]
# (content.rulesets.IMPERIUM_INFLUENCE_FOUR_BONUSES): two troops stacked.
IMPERIUM_FOUR = {
    "emperor": "{troop}|{troop}",
    "spacing_guild": "{solari:3}",
    "bene_gesserit": "{intrigue}",
    "fremen": "{water}",
}
IMPERIUM_PRINT = {
    "conspire": "{solari:5}|{troop}{troop} {intrigue}",
    "wealth": "{solari:2}",
    "imperium_heighliner": "{troop}{troop}{troop}|{troop}{troop}|{water}{water}",
    "foldspace": "{foldspace}",
    "selective_breeding": "{trash} {arrow_right} {draw}{draw}",
    "secrets": "{intrigue}|{steal_intrigue}",
    "hardy_warriors": "{troop}{troop}",
    "stillsuits": "{water}",
    "imperium_high_council": "",
    "hall_of_oratory": "{troop}|{persuasion:1}",
    "mentat": "{draw}",
    "rally_troops": "{troop}{troop}|{troop}{troop}",
    "imperium_swordmaster": "{agent}",
    "sell_melange": (
        "{spice:2}{spice:3}{spice:4}{spice:5}|{solari:6}{solari:8}{solari:10}{solari:12}"
    ),
    "secure_contract": "{solari:3}",
    "arrakeen": "{troop} {draw}",
    "carthag": "{troop} {intrigue}",
    "imperium_research_station": "{draw}{draw}{draw}",
    "imperium_sietch_tabr": "{troop} {water}",
    "imperial_basin": "{spice:1} + {maker}",
    "imperium_hagga_basin": "{spice:2} + {maker}",
    "the_great_flat": "{spice:3} + {maker}",
}
IMPERIUM_PANEL_RIGHT = {
    "conspire": 26.8,
    "wealth": 26.8,
    "imperium_heighliner": 26.8,
    "foldspace": 26.8,
    "selective_breeding": 26.8,
    "secrets": 26.8,
    "hardy_warriors": 26.8,
    "stillsuits": 26.8,
    "imperium_high_council": 58.8,
    "hall_of_oratory": 75.6,
    "mentat": 46.8,
    "rally_troops": 61.6,
    "imperium_swordmaster": 75.6,
    "sell_melange": 97.6,
    "secure_contract": 92.0,
    "arrakeen": 90.0,
    "carthag": 72.6,
    "imperium_research_station": 57.2,
    "imperium_sietch_tabr": 47.6,
    "imperial_basin": 90.6,
    "imperium_hagga_basin": 71.2,
    "the_great_flat": 45.4,
}
IMPERIUM_TAGS = {"imperium_sietch_tabr": "fremen"}
IMPERIUM_CONTROL = {
    "arrakeen": "{solari:1}",
    "carthag": "{solari:1}",
    "imperial_basin": "{spice:1}",
}
ONCE_PER_GAME = ("swordmaster", "imperium_swordmaster", "imperium_high_council")


class _Board:
    """Draw with another board's tables (the helpers read module globals)."""

    def __init__(self, layout, size, printed, panel, tags, control, four) -> None:
        self.values = {
            "L": layout,
            "W": size[0],
            "H": size[1],
            "SPACE_PRINT": printed,
            "PANEL_RIGHT": panel,
            "REQUIREMENT_TAG": tags,
            "CONTROL_BONUS": control,
            "FOUR_BONUS": four,
        }

    def __enter__(self) -> None:
        self.saved = {name: globals()[name] for name in self.values}
        globals().update(self.values)

    def __exit__(self, *exc: object) -> None:
        globals().update(self.saved)


def imperium_board(ko: bool = False) -> str:
    """The original Dune: Imperium board at its scan's 5000 x 4996; ``ko``
    sets the space names in the Korean edition's words, as uprising_ko."""

    with _Board(
        LI,
        (5000, 4996),
        IMPERIUM_PRINT,
        IMPERIUM_PANEL_RIGHT,
        IMPERIUM_TAGS,
        IMPERIUM_CONTROL,
        IMPERIUM_FOUR,
    ):
        catalog = build_catalog()
        spaces = catalog["spaces"]
        assert isinstance(spaces, dict)
        names = {
            "victory_point",
            "maker",
            "sword",
            "water",
            "intrigue",
            "troop",
            "draw",
            "trash",
            "steal_intrigue",
            "agent",
            "recall_agent",
            "arrow_right",
        }
        names |= {
            f"agent_icon_{icon}"
            for icon in (
                "emperor",
                "spacing_guild",
                "bene_gesserit",
                "fremen",
                "landsraad",
                "city",
                "spice_trade",
            )
        }
        names |= {f"influence_{faction}" for faction in FACTIONS}
        names |= {f"faction_{faction}" for faction in FACTIONS}
        names.add("combat")
        body = [symbols(names)]
        parts = [
            f'<rect width="{W}" height="{H}" fill="#1c1916"/>',
            f'<path d="M{n(X(28.2))},{n(Y(21.0))} H{n(X(93.6))} V{n(Y(99.4))} '
            f'H{n(X(28.2))} Z" fill="url(#g-desert)"/>',
        ]
        for k in range(9):
            parts.append(
                f'<ellipse cx="{n(X(66))}" cy="{n(Y(58))}" rx="{n(X(6 + k * 5.5))}" '
                f'ry="{n(Y(4 + k * 4))}" fill="none" stroke="#ffffff" stroke-width="6" '
                'opacity=".05"/>'
            )
        parts.append(
            f'<rect x="{n(X(28.6))}" y="{n(Y(1.4))}" width="{n(X(47.6))}" '
            f'height="{n(Y(18.2))}" rx="40" fill="url(#g-landsraad)" stroke="#5a6a50" '
            'stroke-width="10"/>'
        )
        parts.append(
            f'<text transform="translate({n(X(29.7))} {n(Y(10.5))}) rotate(-90)" '
            f'text-anchor="middle" font-family="{SERIF}" font-size="{n(Y(1.35))}" '
            f'letter-spacing="{n(Y(0.2))}" fill="#9aae8a">LANDSRAAD COUNCIL</text>'
        )
        parts.append(
            f'<rect x="{n(X(77.4))}" y="{n(Y(1.4))}" width="{n(X(20.8))}" '
            f'height="{n(Y(18.2))}" rx="40" fill="url(#g-choam)" stroke="#a8683a" '
            'stroke-width="10"/>'
        )
        parts.append(
            f'<text transform="translate({n(X(78.5))} {n(Y(14.8))}) rotate(-90)" '
            f'text-anchor="middle" font-family="{SERIF}" font-size="{n(Y(1.35))}" '
            f'letter-spacing="{n(Y(0.2))}" fill="#f0b48a">CHOAM</text>'
        )
        for faction in FACTIONS:
            parts.append(faction_strip(faction, ko))
        parts.append(card_slot(L.CONFLICT_DECK_SLOT))
        parts.append(card_slot(L.CONFLICT_SLOT))
        parts.append(conflict_area(ko))
        for space_id in IMPERIUM_PRINT:
            parts.append(space(space_id, spaces[space_id], ko))
        # High Council: four seats with the Persuasion between the pairs.
        for x, y in L.COUNCIL_SEATS:
            parts.append(
                f'<circle cx="{n(X(x))}" cy="{n(Y(y))}" '
                f'r="{n(X(L.SEAT_DISC_SIZE) / 2)}" fill="#1a1a18" stroke="#e8e4dc" '
                'stroke-width="9"/>'
            )
        mid = (L.COUNCIL_SEATS[1][0] + L.COUNCIL_SEATS[2][0]) / 2
        parts.append(
            numbered("persuasion", "2", X(mid), Y(L.COUNCIL_SEATS[1][1]), Y(3.5))
        )
        # The Mentat's own place on its space [DI p. 4].
        if L.MENTAT_POINT:
            mx, my = L.MENTAT_POINT
            parts.append(
                f'<g opacity=".3">{use("agent", X(mx), Y(my), Y(L.MENTAT_HEIGHT))}</g>'
            )
        for space_id in L.CONTROL_FLAG_BOXES:
            parts.append(control_flag(space_id))
        for space_id in ("imperial_basin", "imperium_hagga_basin", "the_great_flat"):
            parts.append(maker_hex(space_id))
        parts.append(strength_track())
        parts.append(victory_track())
        parts.append(
            rows("{troop}: 2  {sword}: 1", X(82.0), X(91.6), Y(86.6), Y(2.2), False, 0)
        )
        # The phase legend [DI p. 4 board].
        for index, (label, icon) in enumerate(
            (
                ("ROUND START", None),
                ("PLAYER TURNS", "draw"),
                ("COMBAT", "sword"),
                ("MAKERS", "maker"),
                ("RECALL", "recall_agent"),
            )
        ):
            y = Y(85.5 + index * 2.9)
            if icon:
                parts.append(use(icon, X(32.0), y, Y(2.1)))
            parts.append(
                f'<text x="{n(X(34.4))}" y="{n(y + Y(0.6))}" font-family="{SERIF}" '
                f'font-size="{n(Y(1.6))}" letter-spacing="{n(Y(0.15))}" fill="#e8dcc6">'
                f'{label}</text>'
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">\n'
            "<!-- The original Dune: Imperium board, drawn by the project from its "
            "own layout tables (scripts/own_pictures/board.py); "
            f"no scan or app picture is used. -->\n<defs>{DEFS}\n"
            + "\n".join(body)
            + "</defs>\n"
            + "\n".join(parts)
            + "\n</svg>\n"
        )


# ------------------------------------------------------- Rise of Ix pieces

IX_PRINT = {
    "imperium_high_council": "",
    "mentat": "{draw}",
    "imperium_swordmaster": "{agent}",
    "interstellar_shipping": "{freighter}|{freighter}",
    "smuggling": "{solari:1}|{freighter}",
    "tech_negotiation": "{persuasion:1}|{acquire_tech_minus1} / {tech_negotiation}",
    "dreadnought": "{dreadnought}|{acquire_tech}",
}
IX_PANEL_RIGHT = {
    "imperium_high_council": 62.6,
    "mentat": 48.6,
    "imperium_swordmaster": 62.6,
    "interstellar_shipping": 77.0,
    "smuggling": 77.0,
    "tech_negotiation": 17.4,
    "dreadnought": 17.4,
}
IX_TAGS = {"interstellar_shipping": "spacing_guild"}
# The Shipping track's rewards, bottom up [Rise of Ix p. 5]
# (docs/rules/rise-of-ix.md 5): Dividends or 2 spice; two troops and an
# Influence; a Tech tile 2 spice cheaper.
SHIPPING_REWARDS = (
    "{solari:5} / {spice:2}",
    "{troop}{troop}|{influence_any}",
    "{acquire_tech_minus2}",
)
# The Ix board, drawn at the original board's scale (IX_BOARD_SCALE).
IX_BOARD_SPAN = (
    LI.IX_BOARD_PICTURE[0] / LI.IX_BOARD_SCALE / 5000 * 100,
    LI.IX_BOARD_PICTURE[1] / LI.IX_BOARD_SCALE / 4996 * 100,
)


def _on_ix_board(box: tuple[float, ...]) -> tuple[float, ...]:
    """A box (or point) in percent of the Ix board, in board percent."""

    sx, sy = IX_BOARD_SPAN[0] / 100, IX_BOARD_SPAN[1] / 100
    return tuple(v * (sx if i % 2 == 0 else sy) for i, v in enumerate(box))


def _ix_layout() -> object:
    from types import SimpleNamespace

    names = {
        k: getattr(LI, k) for k in dir(LI) if k.isupper() or k.startswith("_FIELD")
    }
    layout = SimpleNamespace(**names)
    layout.SPACE_BOXES = {
        **LI.IX_SPACE_BOXES,
        **{k: _on_ix_board(v) for k, v in LI.IX_BOARD_SPACE_BOXES.items()},
    }
    return layout


def _crop(
    box: tuple[float, float, float, float],
    pixels: tuple[int, int],
    defs: str,
    parts: list[str],
    what: str,
) -> str:
    left, top, width, height = X(box[0]), Y(box[1]), X(box[2]), Y(box[3])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{pixels[0]}" '
        f'height="{pixels[1]}" viewBox="{n(left)} {n(top)} {n(width)} {n(height)}">\n'
        f"<!-- {what}, drawn by the project from its own layout tables "
        "(scripts/own_pictures/board.py); "
        f"no scan or app picture is used. -->\n<defs>{DEFS}\n{defs}</defs>\n"
        + "\n".join(parts)
        + "\n</svg>\n"
    )


def ix_pictures(ko: bool = False) -> dict[str, str]:
    """Rise of Ix's Landsraad and CHOAM pieces and its board, each a crop of
    the original board's drawing space at its picture's pixels."""

    with _Board(
        _ix_layout(), (5000, 4996), IX_PRINT, IX_PANEL_RIGHT, IX_TAGS, {}, IMPERIUM_FOUR
    ):
        catalog = build_catalog()
        spaces = catalog["spaces"]
        assert isinstance(spaces, dict)
        names = {
            "agent",
            "draw",
            "freighter",
            "troop",
            "influence_any",
            "acquire_tech",
            "acquire_tech_minus1",
            "acquire_tech_minus2",
            "tech_negotiation",
            "dreadnought",
            "arrow_right",
        }
        names |= {
            f"agent_icon_{icon}"
            for icon in ("landsraad", "spice_trade", "spacing_guild")
        }
        names |= {f"faction_{faction}" for faction in FACTIONS}
        names.add("combat")
        defs = symbols(names)
        out: dict[str, str] = {}

        # The Landsraad piece: High Council, Mentat, Swordmaster.
        box = LI.IX_OVERLAY_BOXES["landsraad"]
        parts = [
            f'<rect x="{n(X(box[0]))}" y="{n(Y(box[1]))}" width="{n(X(box[2]))}" '
            f'height="{n(Y(box[3]))}" fill="#1c1916"/>',
            f'<rect x="{n(X(box[0] + 0.3))}" y="{n(Y(box[1] + 0.3))}" '
            f'width="{n(X(box[2] - 0.6))}" height="{n(Y(box[3] - 0.6))}" rx="40" '
            'fill="url(#g-landsraad)" stroke="#5a6a50" stroke-width="10"/>',
            f'<text transform="translate({n(X(box[0] + 1.3))} '
            f'{n(Y(box[1] + box[3] / 2))}) rotate(-90)" text-anchor="middle" '
            f'font-family="{SERIF}" '
            f'font-size="{n(Y(1.35))}" letter-spacing="{n(Y(0.2))}" fill="#9aae8a">'
            'LANDSRAAD COUNCIL</text>',
        ]
        for space_id in ("imperium_high_council", "mentat", "imperium_swordmaster"):
            parts.append(space(space_id, spaces[space_id], ko))
        for x, y in LI.IX_COUNCIL_SEATS:
            parts.append(
                f'<circle cx="{n(X(x))}" cy="{n(Y(y))}" '
                f'r="{n(X(LI.SEAT_DISC_SIZE) / 2)}" fill="#1a1a18" stroke="#e8e4dc" '
                'stroke-width="9"/>'
            )
        mid = (LI.IX_COUNCIL_SEATS[1][0] + LI.IX_COUNCIL_SEATS[2][0]) / 2
        parts.append(
            numbered("persuasion", "2", X(mid), Y(LI.IX_COUNCIL_SEATS[1][1]), Y(3.5))
        )
        mx, my = LI.IX_MENTAT_POINT
        parts.append(
            f'<g opacity=".3">{use("agent", X(mx), Y(my), Y(LI.MENTAT_HEIGHT))}</g>'
        )
        out["ix_landsraad.svg"] = _crop(
            box, (2100, 1328), defs, parts, "Rise of Ix's Landsraad piece"
        )

        # The CHOAM piece: Interstellar Shipping, Smuggling, the Shipping track.
        box = LI.IX_OVERLAY_BOXES["choam"]
        parts = [
            f'<rect x="{n(X(box[0]))}" y="{n(Y(box[1]))}" width="{n(X(box[2]))}" '
            f'height="{n(Y(box[3]))}" fill="#1c1916"/>',
            f'<rect x="{n(X(box[0] + 0.3))}" y="{n(Y(box[1] + 0.3))}" '
            f'width="{n(X(box[2] - 0.6))}" height="{n(Y(box[3] - 0.6))}" rx="40" '
            'fill="url(#g-choam)" stroke="#a8683a" stroke-width="10"/>',
            f'<text transform="translate({n(X(box[0] + 1.3))} '
            f'{n(Y(box[1] + box[3] * 0.82))}) rotate(-90)" text-anchor="middle" '
            f'font-family="{SERIF}" '
            f'font-size="{n(Y(1.35))}" letter-spacing="{n(Y(0.2))}" fill="#f0b48a">'
            'CHOAM</text>',
        ]
        for space_id in ("interstellar_shipping", "smuggling"):
            parts.append(space(space_id, spaces[space_id], ko))

        def on_piece(x: float, y: float) -> tuple[float, float]:
            return X(box[0]) + x / 100 * X(box[2]), Y(box[1]) + y / 100 * Y(box[3])

        rows_y = [row[0][1] for row in LI.IX_CHOAM_FREIGHTER_ON_PIECE]
        band_left, band_right = on_piece(47.5, 0)[0], on_piece(79.0, 0)[0]
        reward_left, reward_right = on_piece(80.0, 0)[0], on_piece(98.0, 0)[0]
        half = Y(box[3]) * 0.095
        for level, row_y in enumerate(rows_y):
            cy = on_piece(0, row_y)[1]
            fill = "#3a2410" if level else "#22160c"
            parts.append(
                chevron_band(
                    cy,
                    band_left,
                    band_right,
                    -half * 0.25 if level else 0,
                    half,
                    fill,
                    "#e0a24a",
                )
            )
            if level:
                parts.append(
                    f'<rect x="{n(reward_left)}" y="{n(cy - half)}" '
                    f'width="{n(reward_right - reward_left)}" height="{n(half * 2)}" '
                    'rx="22" fill="#5a3418" stroke="#e0a24a" stroke-width="8"/>'
                )
                parts.append(
                    rows(
                        SHIPPING_REWARDS[level - 1],
                        reward_left,
                        reward_right,
                        cy,
                        Y(1.9),
                        False,
                        Y(0.3),
                        max_h=half * 1.84,
                    )
                )
            else:
                parts.append(use("freighter", band_left + X(2.0), cy, half * 1.5))
        out["ix_choam.svg"] = _crop(
            box, (2100, 1324), defs, parts, "Rise of Ix's CHOAM piece"
        )

        # The Ix board: Tech Negotiation, Dreadnought, the Tech stacks and
        # the Negotiators' place.
        span = (0.0, 0.0, IX_BOARD_SPAN[0], IX_BOARD_SPAN[1])
        cx, cy, radius = X(span[2] * 0.62), Y(span[3] * 0.55), X(span[2] * 0.52)
        parts = [
            f'<rect width="{n(X(span[2]))}" height="{n(Y(span[3]))}" fill="#141820"/>',
            f'<circle cx="{n(cx)}" cy="{n(cy)}" r="{n(radius)}" fill="url(#g-planet)" '
            'stroke="#7aa0a8" stroke-width="10" opacity=".85"/>',
            f'<text transform="translate({n(X(1.3))} {n(Y(span[3] * 0.78))}) '
            f'rotate(-90)" text-anchor="middle" font-family="{SERIF}" '
            f'font-size="{n(Y(1.35))}" letter-spacing="{n(Y(0.3))}" fill="#a8c0b0">'
            'IX</text>',
            f'<rect x="{n(X(0.6))}" y="{n(Y(0.6))}" width="{n(X(16.9))}" '
            f'height="{n(Y(20.6))}" rx="36" fill="url(#g-landsraad)" stroke="#5a6a50" '
            'stroke-width="10"/>',
        ]
        for space_id in ("tech_negotiation", "dreadnought"):
            parts.append(space(space_id, spaces[space_id], ko))
        for slot in LI.IX_TECH_SLOTS:
            parts.append(card_slot(_on_ix_board(slot)))  # type: ignore[arg-type]
        nl, nt, nw, nh = _on_ix_board(LI.IX_NEGOTIATOR_BOX)
        parts.append(
            f'<rect x="{n(X(nl))}" y="{n(Y(nt))}" width="{n(X(nw))}" '
            f'height="{n(Y(nh))}" rx="26" fill="#1e2a26" stroke="#9ab0a0" '
            'stroke-width="9"/>'
        )
        parts.append(
            f'<g opacity=".5">{
                use(
                    "tech_negotiation",
                    X(nl + nw / 2),
                    Y(nt + nh * 0.32),
                    Y(nh * 0.42),
                )
            }</g>'
        )
        for point in LI.IX_NEGOTIATOR_SEATS:
            px, py = _on_ix_board(point)
            parts.append(
                f'<rect x="{n(X(px) - X(0.6))}" y="{n(Y(py + 1.6) - X(0.6))}" '
                f'width="{n(X(1.2))}" height="{n(X(1.2))}" rx="6" fill="#0c0b09" '
                'stroke="#6a7a70" stroke-width="5"/>'
            )
        out["ix_board.svg"] = _crop(
            span, LI.IX_BOARD_PICTURE, defs, parts, "Rise of Ix's board"
        )
        return out


# ----------------------------------------------------- the Bene Tleilax board

# Each research bonus as printed in its hex [Immortality p. 3 board artwork]
# (content.immortality.board.ResearchBonus).
RESEARCH_PRINT = {
    "none": "",
    "specimen": "{specimen}",
    "tleilaxu": "{log_tleilaxu}",
    "research": "{log_research}",
    "trash_and_specimen": "{trash}{specimen}",
    "tleilaxu_and_specimen": "{log_tleilaxu}{specimen}",
    "solari_one": "{solari:1}",
    "spice_one": "{spice:1}",
    "spice_two": "{spice:2}",
    "influence_any": "{influence_any}",
    "trash_intrigue_for_card_and_intrigue": (
        "{trash_intrigue} {arrow_right}"
        " {draw}{intrigue}"
    ),
    "seven_solari_for_two_tleilaxu": (
        "{solari:7} {arrow_right}"
        " {log_tleilaxu}{log_tleilaxu}"
    ),
}
# The Tleilaxu track's spaces [Immortality p. 7] (TleilaxuBonus).
TRACK_PRINT = {
    "none": "",
    "intrigue": "{intrigue}",
    "victory_point_and_first_spice": "{victory_point}",
    "victory_point": "{victory_point}",
}


def bene_tleilax_board() -> str:
    """The Bene Tleilax board at its scan's 5551 x 3952."""

    from dune_imperium.display import bene_tleilax_layout as BT

    with _Board(BT, (5551, 3952), {}, {}, {}, {}, {}):
        tleilax = build_catalog()["bene_tleilax"]
        assert isinstance(tleilax, dict)
        names = {
            "intrigue",
            "victory_point",
            "specimen",
            "trash",
            "trash_intrigue",
            "draw",
            "influence_any",
            "arrow_right",
            "log_tleilaxu",
            "log_research",
        }
        body = [symbols(names)]
        parts = [f'<rect width="{W}" height="{H}" fill="url(#g-tanks)"/>']
        for x, y, r in ((70, 40, 18), (88, 70, 14), (30, 85, 12), (55, 60, 22)):
            parts.append(
                f'<ellipse cx="{n(X(x))}" cy="{n(Y(y))}" rx="{n(X(r))}" '
                f'ry="{n(Y(r * 1.2))}" fill="#c070d0" opacity=".07"/>'
            )
        # The Tleilaxu track along the top: its start box and seven spaces.
        top, height = BT.TRACK_BAND
        parts.append(
            f'<rect x="{n(X(1.6))}" y="{n(Y(top))}" width="{n(X(96.8))}" '
            f'height="{n(Y(height))}" rx="30" fill="#1e1a20" stroke="#6a5a70" '
            'stroke-width="10"/>'
        )
        track = tleilax["tleilaxu_track"]
        assert isinstance(track, list)
        for index, (left, width) in enumerate(BT.TRACK_CELLS):
            x0, x1 = X(left), X(left + width)
            y0, y1 = Y(top + 0.6), Y(top + height - 0.6)
            notch = X(1.2)
            shape = [
                (x0, y0),
                (x1 - notch, y0),
                (x1, (y0 + y1) / 2),
                (x1 - notch, y1),
                (x0, y1),
                (x0 + notch, (y0 + y1) / 2),
            ]
            if index == 0:
                shape = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            parts.append(
                f'<polygon points="{pts(shape)}" '
                f'fill="{"#3a3440" if index == 0 else "#2a2430"}" stroke="#a89060" '
                'stroke-width="7"/>'
            )
            printed = TRACK_PRINT[str(track[index])]
            if printed:
                parts.append(
                    rows(
                        printed,
                        x0 + notch,
                        x1 - notch,
                        Y(top + height / 2),
                        Y(6.5),
                        False,
                        0,
                        max_h=Y(height) * 0.86,
                    )
                )
        for x, y in BT.TRACK_START_DISCS:
            parts.append(
                f'<circle cx="{n(X(x))}" cy="{n(Y(y))}" r="{n(X(BT.DISC_SIZE) / 2)}" '
                'fill="#141016" stroke="#6a5a70" stroke-width="7"/>'
            )
        # The first to reach the fourth space also takes the 2 spice set there.
        sx, sy = BT.SPICE_POINT
        parts.append(numbered("spice", "2", X(sx), Y(sy), Y(BT.SPICE_SIZE[1])))
        parts.append(
            f'<text x="{n(X(sx))}" y="{n(Y(sy - BT.SPICE_SIZE[1] * 0.75))}" '
            f'text-anchor="middle" font-family="{FONT}" font-weight="800" '
            f'font-size="{n(Y(2.6))}" fill="#f2ede2">1st</text>'
        )
        parts.append(
            f'<text x="{n(X(1.8))}" y="{n(Y(27.2))}" font-family="{SERIF}" '
            f'font-size="{n(Y(2.6))}" letter-spacing="{n(Y(0.3))}" fill="#e6dcef">BENE '
            'TLEILAX</text>'
        )
        # The research hexes, the token's place dark above the bonus.
        # The printed hex sits inside the layout's hotspot (HEX_SIZE), with
        # a gap and a connector to each neighbour.
        w, h = X(BT.HEX_SIZE[0] * 0.86), Y(BT.HEX_SIZE[1] * 0.86)
        spaces = tleilax["research_spaces"]
        assert isinstance(spaces, list)
        places = {
            (int(str(e["column"])), int(str(e["row"]))): BT.RESEARCH_POINTS[
                str(e["id"])
            ]
            for e in spaces
            if isinstance(e, dict)
        }
        for (column, row), (x, y) in places.items():
            for step in (-1, 1):
                other = places.get((column + 1, row + step))
                if other is None:
                    continue
                mx, my = X((x + other[0]) / 2), Y((y + other[1]) / 2)
                angle = math.degrees(math.atan2(Y(other[1]) - Y(y), X(other[0]) - X(x)))
                parts.append(
                    f'<g transform="translate({n(mx)} {n(my)}) rotate({n(angle)})">'
                    f'<rect x="{n(-X(0.9))}" y="{n(-Y(0.9))}" width="{n(X(1.8))}" '
                    f'height="{n(Y(0.5))}" rx="8" fill="#f0e6f6"/>'
                    f'<rect x="{n(-X(0.9))}" y="{n(Y(0.4))}" width="{n(X(1.8))}" '
                    f'height="{n(Y(0.5))}" rx="8" fill="#f0e6f6"/></g>'
                )
        for entry in spaces:
            assert isinstance(entry, dict)
            if entry["id"] == tleilax["research_start"]:
                continue
            x, y = BT.RESEARCH_POINTS[str(entry["id"])]
            cx, cy = X(x), Y(y)
            hexagon = [
                (cx, cy - h / 2),
                (cx + w / 2, cy - h / 4),
                (cx + w / 2, cy + h / 4),
                (cx, cy + h / 2),
                (cx - w / 2, cy + h / 4),
                (cx - w / 2, cy - h / 4),
            ]
            lower = [
                (cx + w / 2, cy + h * 0.06),
                (cx + w / 2, cy + h / 4),
                (cx, cy + h / 2),
                (cx - w / 2, cy + h / 4),
                (cx - w / 2, cy + h * 0.06),
            ]
            bright = int(str(entry["column"])) >= 3
            parts.append(
                f'<polygon points="{pts(hexagon)}" fill="#160e1c" '
                f'stroke="{"#c58ad8" if bright else "#8a6a98"}" stroke-width="16" '
                'stroke-linejoin="round"/>'
            )
            parts.append(
                f'<polygon points="{pts(lower)}" '
                f'fill="{"#7a4290" if bright else "#4e3a5a"}"/>'
            )
            printed = RESEARCH_PRINT[str(entry["bonus"])]
            if printed:
                parts.append(
                    rows(
                        printed,
                        cx - w * 0.42,
                        cx + w * 0.42,
                        cy + h * 0.25,
                        Y(4.6),
                        False,
                        0,
                        max_h=h * 0.42,
                    )
                )
        # The start: a tall box at the left edge with the four tokens' places.
        start = [
            (0, Y(32)),
            (X(6.6), Y(32)),
            (X(10.2), Y(51.9)),
            (X(6.6), Y(71.6)),
            (0, Y(71.6)),
        ]
        parts.append(
            f'<polygon points="{pts(start)}" fill="#7a4290" stroke="#c58ad8" '
            'stroke-width="12"/>'
        )
        for x, y in BT.RESEARCH_START_DISCS:
            parts.append(
                f'<circle cx="{n(X(x))}" cy="{n(Y(y))}" r="{n(X(BT.DISC_SIZE) / 2)}" '
                'fill="#3a2048" stroke="#d8a8e8" stroke-width="7"/>'
            )
        # The Axolotl tanks, where each seat's specimens lie.
        bl, bt, bw, bh = BT.SPECIMEN_BOX
        parts.append(
            f'<rect x="{n(X(bl))}" y="{n(Y(bt))}" width="{n(X(bw))}" '
            f'height="{n(Y(bh))}" rx="40" fill="#2a2a2e" stroke="#8a8a90" '
            'stroke-width="10"/>'
        )
        parts.append(
            '<g opacity=".18">'
            f'{use("specimen", X(bl + bw / 2), Y(bt + bh / 2), Y(bh * 0.7))}</g>'
        )
        for left, top_, width, height_ in BT.SPECIMEN_PLAYER_BOXES:
            parts.append(
                f'<rect x="{n(X(left))}" y="{n(Y(top_))}" width="{n(X(width))}" '
                f'height="{n(Y(height_))}" rx="20" fill="none" stroke="#ffffff22" '
                'stroke-width="6"/>'
            )
        # The genetic markers under columns 4 and 8 [Immortality p. 6].
        columns = tleilax["genetic_marker_columns"]
        assert isinstance(columns, list)
        first, last = int(str(columns[0])), int(str(columns[1]))
        line_y = Y(92.6)
        parts.append(
            f'<path d="M{n(X(BT._COLUMN_X[first]))},{n(line_y)} '
            f'H{n(X(BT._COLUMN_X[last]))}" stroke="#e8e0f0" stroke-width="14"/>'
        )
        for column in range(first + 1, last):
            cx = X(BT._COLUMN_X[column])
            node = [
                (
                    cx + Y(2.2) * math.cos(math.pi / 3 * k + math.pi / 6),
                    line_y + Y(2.2) * math.sin(math.pi / 3 * k + math.pi / 6),
                )
                for k in range(6)
            ]
            parts.append(
                f'<polygon points="{pts(node)}" fill="#7a4290" stroke="#e8e0f0" '
                'stroke-width="8"/>'
            )
        for column, printed, half in (
            (first, "{dna}", X(4.6)),
            (last, "{dna}{dna} {log_research} {arrow_right} {draw}", X(7.0)),
        ):
            cx = X(BT._COLUMN_X[column])
            left = min(cx - half, X(98.4) - 2 * half)
            parts.append(
                f'<rect x="{n(left)}" y="{n(line_y - Y(3.8))}" width="{n(2 * half)}" '
                f'height="{n(Y(7.6))}" rx="26" fill="#2a1a30" stroke="#e8e0f0" '
                'stroke-width="9"/>'
            )
            parts.append(
                rows(
                    printed,
                    left,
                    left + 2 * half,
                    line_y,
                    Y(5.0),
                    False,
                    0,
                    max_h=Y(7.0),
                )
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">\n'
            "<!-- The Bene Tleilax board (Immortality), drawn by the project from its "
            "own tables (scripts/own_pictures/board.py); "
            f"no scan or app picture is used. -->\n<defs>{DEFS}\n"
            + "\n".join(body)
            + "</defs>\n"
            + "\n".join(parts)
            + "\n</svg>\n"
        )


# ------------------------------------------------------------ board tiles

# Pieces laid over a board: Esmar Tuek's own space (Bloodlines) and
# Immortality's Research Station overlay, each a crop of the Uprising
# board's drawing space at its picture's pixels (the same picture serves
# the original board).
TILE_PRINT = {
    "tuek_sietch": "{spice:1} OR {draw}",
    "research_station": "{draw}{draw} {log_research}",
}
TILE_PANEL_RIGHT = {"tuek_sietch": 90.0, "research_station": 54.0}
# Rows printed above the middle of their frame (Tuek's Sietch: above its
# bonus spice hexagon), percent of height.
ROW_SHIFT = {"tuek_sietch": -1.4}


def tile_pictures(ko: bool = False) -> dict[str, str]:
    from types import SimpleNamespace

    layout = SimpleNamespace(
        **{k: getattr(L, k) for k in dir(L) if k.isupper() or k.startswith("_FIELD")}
    )
    with _Board(layout, (6012, 6005), TILE_PRINT, TILE_PANEL_RIGHT, {}, {}, FOUR_BONUS):
        spaces = build_catalog()["spaces"]
        assert isinstance(spaces, dict)
        names = {"draw", "maker", "water", "log_research", "arrow_right"}
        names |= {f"agent_icon_{icon}" for icon in ("spice_trade", "city")}
        defs = symbols(names)
        out: dict[str, str] = {}
        box = L.LEADER_TILE_BOXES["tuek_sietch"]
        parts = [
            f'<rect x="{n(X(box[0]))}" y="{n(Y(box[1]))}" width="{n(X(box[2]))}" '
            f'height="{n(Y(box[3]))}" rx="40" fill="url(#g-tile)" stroke="#e0b070" '
            'stroke-width="10"/>',
            space("tuek_sietch", spaces["tuek_sietch"], ko),
            maker_hex("tuek_sietch"),
        ]
        out["tuek_sietch.svg"] = _crop(
            box, (550, 310), defs, parts, "Esmar Tuek's Tuek's Sietch board space"
        )
        box = L.RESEARCH_STATION_OVERLAY_BOX
        overlay = spaces["research_station"]["immortality"]
        assert isinstance(overlay, dict)
        entry = {**spaces["research_station"], "options": overlay["options"]}
        parts = [
            f'<rect x="{n(X(box[0]))}" y="{n(Y(box[1]))}" width="{n(X(box[2]))}" '
            f'height="{n(Y(box[3]))}" rx="40" fill="#24201c" stroke="#8a7a6a" '
            'stroke-width="10"/>',
            space("research_station", entry, ko),
        ]
        out["research_station_overlay.svg"] = _crop(
            box, (782, 425), defs, parts, "Immortality's Research Station overlay"
        )
        return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="fail if a drawing is out of date"
    )
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    stale = []
    drawings = {
        "uprising.svg": lambda: board(False),
        "uprising_ko.svg": lambda: board(True),
        "imperium.svg": imperium_board,
        "imperium_ko.svg": lambda: imperium_board(True),
        **{name: (lambda text=text: text) for name, text in ix_pictures().items()},
        **{
            name.replace(".svg", "_ko.svg"): (lambda text=text: text)
            for name, text in ix_pictures(True).items()
        },
        "bene_tleilax.svg": bene_tleilax_board,
        **{name: (lambda text=text: text) for name, text in tile_pictures().items()},
        **{
            name.replace(".svg", "_ko.svg"): (lambda text=text: text)
            for name, text in tile_pictures(True).items()
        },
    }
    for name, draw in drawings.items():
        text = draw()
        path = OUT / name
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(name)
        else:
            path.write_text(text)
            print(f"wrote {path.relative_to(REPO)} ({len(text) // 1024} KiB)")
    if stale:
        print("out of date:", ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
