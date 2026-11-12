# ruff: noqa: E501  (SVG markup reads best one element to a line)
"""The project's own icon drawings (stage 2, docs/own-pictures-plan.md).

Every shape here is drawn by hand in our own lines, looking at the game's
icons only for what each should resemble (no tracing, no sampling of
pixels). Each SVG keeps the original icon's proportions (height 100), so
the page lays it out exactly where the private icon sat.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

DRAWN = "2026-11-10"

# Width per icon (height 100), the original's aspect ratio.
WIDTH = {
    "acquire_tech": 170, "acquire_tech_minus1": 163, "acquire_tech_minus2": 163, "agent": 65,
    "agent_icon_bene_gesserit": 136, "agent_icon_city": 136, "agent_icon_emperor": 136,
    "agent_icon_fremen": 136, "agent_icon_landsraad": 136, "agent_icon_spacing_guild": 136,
    "agent_icon_spice_trade": 136, "agent_icon_spy": 136, "arrow_down": 89, "arrow_right": 114,
    "battle_crysknife": 176, "battle_desert_mouse": 176, "battle_ornithopter": 176, "battle_wild": 176,
    "contract": 149, "control": 87, "discard": 66, "draw": 66, "dreadnought": 109, "freighter": 83,
    "influence_any": 88, "influence_any_two": 76, "influence_bene_gesserit": 88, "influence_emperor": 88,
    "influence_fremen": 88, "influence_lose": 88, "influence_spacing_guild": 88, "intrigue": 66,
    "maker": 115, "maker_hooks": 111, "persuasion": 100, "recall_agent": 63, "recall_spy": 79,
    "sandworm": 105, "shield_wall": 88, "signet_ring": 113, "specimen": 94,
    "spice": 113, "spy": 70, "steal_intrigue": 110, "sword": 74, "tech_negotiation": 93,
    "trash": 66, "trash_intrigue": 66, "troop": 94, "unload": 151, "victory_point": 100, "water": 68,
}

ICONS: dict[str, tuple[str, str]] = {}  # name -> (svg body, note)
LOGS: dict[str, tuple[str, str]] = {}


def f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def pts(points) -> str:
    return " ".join(f"{f(x)},{f(y)}" for x, y in points)


def lin(gid: str, c1: str, c2: str, x2: float = 0, y2: float = 1) -> str:
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="{f(x2)}" y2="{f(y2)}">'
            f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>')


def rad(gid: str, c1: str, c2: str, cx: float = 0.4, cy: float = 0.35) -> str:
    return (f'<radialGradient id="{gid}" cx="{f(cx)}" cy="{f(cy)}" r="0.75">'
            f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></radialGradient>')


# ------------------------------------------------------------- symbols


# extras: Intrigue mark, victory point, signet ring, microscope; extras2:
# question mark, battle icons, blades, freighter, wall, steal, flip; marks:
# the four Faction marks, proportions measured off the game's icons; shapes:
# the piece shapes shared with the tokens.
from . import extras, extras2, marks, shapes  # noqa: E402

emperor, guild, bene_gesserit, fremen = marks.emperor, marks.guild, marks.bene_gesserit, marks.fremen


_GRAIN = [0]


def grain(cx: float, cy: float, r: float, color: str) -> str:
    """Faint wood-grain lines inside a circle of radius r (the plain Agent shapes' texture)."""
    _GRAIN[0] += 1
    gid = f"grain{_GRAIN[0]}"
    lines = "".join(
        f'<path d="M{f(cx - r * 1.2)},{f(cy + k * r * 0.24)} Q{f(cx - r * 0.1)},{f(cy + k * r * 0.24 - r * 0.42)} {f(cx + r * 1.2)},{f(cy + k * r * 0.24 + r * 0.12)}"/>'
        for k in range(-5, 6))
    return (f'<clipPath id="{gid}"><circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}"/></clipPath>'
            f'<g clip-path="url(#{gid})" fill="none" stroke="{color}" stroke-width="0.8" opacity=".22">{lines}</g>')


def eye(cx: float, cy: float, r: float, color: str = "#f4f4f4") -> str:
    """The Spy's eye with rays above and below."""
    rays = ""
    for k in (1.0, 1.32):
        rays += (f'<path d="M{f(cx - r * k)},{f(cy - r * .2 * k)} Q{f(cx)},{f(cy - r * .78 * k)} {f(cx + r * k)},{f(cy - r * .2 * k)}" fill="none" stroke="{color}" stroke-width="{f(r * .08)}"/>'
                 f'<path d="M{f(cx - r * k)},{f(cy + r * .2 * k)} Q{f(cx)},{f(cy + r * .78 * k)} {f(cx + r * k)},{f(cy + r * .2 * k)}" fill="none" stroke="{color}" stroke-width="{f(r * .08)}"/>')
    almond = (f"M{f(cx - r * .82)},{f(cy)} Q{f(cx)},{f(cy - r * .62)} {f(cx + r * .82)},{f(cy)} "
              f"Q{f(cx)},{f(cy + r * .62)} {f(cx - r * .82)},{f(cy)} Z")
    return (rays + f'<path d="{almond}" fill="{color}"/>'
            f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * .26)}" fill="#7d7d7d"/>'
            f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * .11)}" fill="#222"/>')


def intrigue_glyph(cx: float, cy: float, r: float, color: str = "", dark: str = "#3a2606") -> str:
    """The Intrigue mark (extras.intrigue_glyph), r = half its height."""
    body, defs = extras.intrigue_glyph(cx, cy, r, edge=dark)
    return f"<defs>{defs}</defs>{body}"


def gear(cx: float, cy: float, r: float, color: str = "#e8cf6a", hole: str = "#3a3a12") -> str:
    """The Tech mark: a plain gear (extras3.gear)."""
    from . import extras3
    return extras3.gear(cx, cy, r, color, hole)


def question(cx: float, cy: float, size: float, color: str = "", stroke: str = "#2a1a00") -> str:
    """The bold blocky question mark (extras2.question), about 1.1 size tall."""
    body, defs = extras2.question(cx, cy, size * 1.1, fill=color if color and color != "#f2c230" else "", edge=stroke)
    return f"<defs>{defs}</defs>{body}"


def arrow_up(cx: float, top: float, bottom: float, w: float, color: str = "#fff", outline: str = "#2a2a2a") -> str:
    head = w * 1.0
    shaft = w * .42
    p = [(cx, top), (cx + head, top + head), (cx + shaft, top + head), (cx + shaft, bottom),
         (cx - shaft, bottom), (cx - shaft, top + head), (cx - head, top + head)]
    return f'<polygon points="{pts(p)}" fill="{color}" stroke="{outline}" stroke-width="{f(w * .16)}" stroke-linejoin="round"/>'


def chevron(cx: float, tip: float, half: float, depth: float, thick: float, fill: str, edge: str, down: bool = False) -> str:
    """A ^ (or v) band: the Influence step mark."""
    s = 1 if not down else -1
    p = [(cx, tip), (cx + half, tip + s * depth), (cx + half, tip + s * (depth + thick)),
         (cx, tip + s * thick), (cx - half, tip + s * (depth + thick)), (cx - half, tip + s * depth)]
    return f'<polygon points="{pts(p)}" fill="{fill}" stroke="{edge}" stroke-width="1.6" stroke-linejoin="round"/>'


# --------------------------------------------------------------- frames


PLATE_R, PLATE_B, PLATE_CUT = 127.5, 90.0, 12.0
PLATE_CX, PLATE_CY = 64.3, 45.6


def plate(w: float, symbol: str, well: bool = False) -> str:
    """The Agent-icon plate: a warm grey tile with a pale rim and its top
    right corner cut, on a soft shadow; a Faction's has a dark well. The
    board and the card faces drop the groups with class "plate" and "well"
    (scripts/own_pictures/board.py), showing the mark alone as print does."""
    R, B, c = PLATE_R, PLATE_B, PLATE_CUT
    outer = [(1.2, 1.2), (R - c, 1.2), (R, 1.2 + c), (R, B), (1.2, B)]
    rim = [(3.1, 3.1), (R - c - 0.8, 3.1), (R - 1.9, 1.2 + c + 0.8), (R - 1.9, B - 1.9), (3.1, B - 1.9)]
    out = (f'<g class="plate"><polygon points="{pts([(x + 2.4, y + 3.2) for x, y in outer])}" fill="#000" opacity=".6" filter="url(#psh)"/>'
           f'<polygon points="{pts(outer)}" fill="url(#plate)" stroke="#3e3b38" stroke-width="1.4" stroke-linejoin="round"/>'
           f'<polygon points="{pts(rim)}" fill="none" stroke="url(#prim)" stroke-width="2" stroke-linejoin="round"/></g>')
    if well:
        k = 8
        oct_ = [(15 + k, 12.4), (114 - k, 12.4), (114, 12.4 + k), (114, 76.3 - k), (114 - k, 76.3), (15 + k, 76.3), (15, 76.3 - k), (15, 12.4 + k)]
        inner = [(15 + k + 1.4, 15.6), (114 - k - 1.4, 15.6), (110.8, 12.4 + k + 1.4), (110.8, 76.3 - k - 1.4),
                 (114 - k - 1.4, 73.1), (15 + k + 1.4, 73.1), (18.2, 76.3 - k - 1.4), (18.2, 12.4 + k + 1.4)]
        out += (f'<g class="well"><polygon points="{pts(oct_)}" fill="url(#pwell)" stroke="#262626" stroke-width="1.6" stroke-linejoin="round"/>'
                f'<polygon points="{pts(inner)}" fill="none" stroke="#575553" stroke-width="1" stroke-linejoin="round" opacity=".7"/></g>')
    return out + f'<g filter="url(#msh)">{symbol}</g>'


PLATE_DEFS = (lin("plate", "#938a80", "#aca298", 1, 0.25) + lin("prim", "#d6d2cc", "#fbfaf8", 0.3, 1) + lin("pwell", "#2e2e2e", "#0f0f0f")
              + '<filter id="psh" x="-10%" y="-10%" width="120%" height="125%"><feGaussianBlur stdDeviation="1.6"/></filter>'
              + '<filter id="msh" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="1.2" stdDeviation="1" flood-color="#000" flood-opacity=".7"/></filter>')


def card(fill_defs: str, inner: str, extra: str = "", rim: str = "#f2f2f2") -> tuple[str, str]:
    body = (f'<rect x="3" y="3" width="60" height="94" rx="7" fill="#1b1b1b"/>'
            f'<rect x="5" y="5" width="56" height="90" rx="5.5" fill="{rim}"/>'
            f'<rect x="10" y="10" width="46" height="80" rx="3" fill="{inner}"/>' + extra)
    return body, fill_defs


def diamond_influence(w: float, symbol: str, cy: float = 56.7, chevrons: int = 1, lose: bool = False, half: float | None = None) -> str:
    """A black diamond with a grey edge; gold steps (^) stacked above it, or
    a red step down (v) laid over its lower half for a loss."""
    cx = w / 2
    half = half if half is not None else w / 2 - 2.3
    if lose:
        cy = 2 + half
    dia = [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)]
    inset = [(cx, cy - half + 3.2), (cx + half - 3.2, cy), (cx, cy + half - 3.2), (cx - half + 3.2, cy)]
    body = (f'<polygon points="{pts(dia)}" fill="url(#dia)" stroke="#050505" stroke-width="1.6" stroke-linejoin="round"/>'
            f'<polygon points="{pts(inset)}" fill="none" stroke="#6a6866" stroke-width="1.4" stroke-linejoin="round" opacity=".8"/>')
    steps = ""
    top = cy - half
    for k in range(chevrons if not lose else 0):
        apex = top - 12 - (chevrons - 1 - k) * 14
        end = apex + min(42.5, w / 2 - 3.5) if k == chevrons - 1 else apex + 35.5
        steps += step(cx, apex, end, "url(#gold)", "#4a2e00")
    body = steps + body
    body += f'<g filter="url(#msh)">{symbol}</g>'
    if lose:
        body += step(cx, 98.5, 56, "url(#red)", "#3a0408", down=True)
    return body


def step(cx: float, apex: float, end: float, fill: str, edge: str, down: bool = False) -> str:
    """One Influence step: a band 13 deep along a 45-degree roof, cut level at `end`."""
    s = -1 if down else 1
    d = abs(end - apex)
    inner = d - 13
    p = [(cx, apex), (cx + d, end), (cx + max(inner, 0), end), (cx, apex + s * 13), (cx - max(inner, 0), end), (cx - d, end)]
    shine = [(cx, apex + s * 1.6), (cx + d - 1.6, end - s * 0.8)]
    return (f'<polygon points="{pts(p)}" fill="{fill}" stroke="{edge}" stroke-width="1.6" stroke-linejoin="round"/>'
            f'<path d="M{f(cx - d + 1.6)},{f(end - s * 0.8)} L{f(shine[0][0])},{f(shine[0][1])} L{f(shine[1][0])},{f(shine[1][1])}" fill="none" stroke="#fff" stroke-width="1" opacity=".35" stroke-linejoin="round"/>')


DIA = lin("dia", "#2c2c2c", "#0c0c0c")
GOLD = lin("gold", "#ffd76a", "#c98612")
RED = lin("red", "#ff5250", "#a3121c")
# The Influence icons: a brighter gold step, the game's pinker red, the diamond and the mark shadow.
INF_GOLD = lin("gold", "#ffe27a", "#d08a10") + DIA + PLATE_DEFS
INF_RED = lin("red", "#ff5068", "#c0122c") + DIA + PLATE_DEFS


def battle(fill1: str, fill2: str, symbol: str) -> tuple[str, str]:
    p = [(24, 8), (172, 8), (152, 92), (4, 92)]
    body = (f'<polygon points="{pts(p)}" fill="url(#tile)" stroke="#1b1b1b" stroke-width="3" stroke-linejoin="round"/>'
            f'<polygon points="{pts([(30, 14), (164, 14), (147, 86), (12, 86)])}" fill="none" stroke="#ffffff33" stroke-width="1.6"/>'
            + symbol)
    return body, lin("tile", fill1, fill2, 1, 1)


# ---------------------------------------------------------------- icons


def add(name: str, body: str, defs: str, note: str) -> None:
    CURRENT[0] = name
    ICONS[name] = (svg(WIDTH[name], body, defs, note), note)


# The private icons' pixel sizes: each drawing takes the same intrinsic size,
# so a layout that does not size it lays it out as it did the picture.
PIXELS = json.loads((Path(__file__).parent / "pixels.json").read_text())
CURRENT = [""]


def svg(w: float, body: str, defs: str, note: str) -> str:
    pw, ph = PIXELS[CURRENT[0]]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw}" height="{ph}" viewBox="0 0 {f(w)} 100">',
           f"  <!-- {note} Drawn by hand for the public build. -->"]
    if defs:
        out.append(f"  <defs>{defs}</defs>")
    out.append("  " + body)
    out.append("</svg>")
    return "\n".join(out) + "\n"


CX, CY = PLATE_CX, PLATE_CY
for name, symbol, note in (
    ("agent_icon_emperor", lambda w: emperor(65.7, 37.4, 32.4), "Emperor Agent icon: the Emperor's mark on a dark well in a stone plate."),
    ("agent_icon_spacing_guild", lambda w: guild(63.4, 43.9, 48.6), "Spacing Guild Agent icon: a red infinity on a dark well in a stone plate."),
    ("agent_icon_bene_gesserit", lambda w: bene_gesserit(65.3, 44.3, 45), "Bene Gesserit Agent icon: the eye loops, spindle and brackets on a dark well in a stone plate."),
    ("agent_icon_fremen", lambda w: fremen(66.1, 44.7, 35), "Fremen Agent icon: the banded blue disc on a dark well in a stone plate."),
    ("agent_icon_landsraad", lambda w: f'<polygon points="{pts([(CX + 40 * math.cos(-math.pi / 2 + k * 2 * math.pi / 5), CY + 3 + 40 * math.sin(-math.pi / 2 + k * 2 * math.pi / 5)) for k in range(5)])}" fill="url(#green)" stroke="#123c12" stroke-width="2" stroke-linejoin="round"/>'
     + grain(CX, CY + 3, 32, "#b8ffb0"),
     "Landsraad Agent icon: a green pentagon on a stone plate."),
    ("agent_icon_city", lambda w: f'<circle cx="{f(CX)}" cy="{f(CY)}" r="37" fill="url(#blue)" stroke="#141c50" stroke-width="2"/>' + grain(CX, CY, 35, "#c8d0ff"),
     "City Agent icon: a blue disc on a stone plate."),
    ("agent_icon_spice_trade", lambda w: f'<polygon points="{pts([(CX, CY - 37), (CX + 41, CY + 34), (CX - 41, CY + 34)])}" fill="url(#yellow)" stroke="#5a3a00" stroke-width="2" stroke-linejoin="round"/>'
     + grain(CX, CY + 10.3, 23, "#fff0b0"),
     "Spice Trade Agent icon: a yellow triangle on a stone plate."),
):
    w = WIDTH[name]
    defs = PLATE_DEFS + lin("green", "#4ee05e", "#1b7a22") + rad("blue", "#8a9cff", "#2c3ab8") + lin("yellow", "#ffd84a", "#f08a00")
    faction = name in ("agent_icon_emperor", "agent_icon_spacing_guild", "agent_icon_bene_gesserit", "agent_icon_fremen")
    add(name, plate(w, symbol(w), well=faction), defs, note)

w = WIDTH["agent_icon_spy"]
add("agent_icon_spy", plate(w, "".join(f'<circle cx="{f(PLATE_CX)}" cy="{f(PLATE_CY)}" r="{rr}" fill="none" stroke="#f2f0ec" stroke-width="1.6" opacity="{op}"/>'
                                     for rr, op in ((40, ".35"), (34, ".5"))) + eye(PLATE_CX, PLATE_CY, 24)),
    PLATE_DEFS, "Spy Agent icon: an eye with rays on a stone plate.")


def pawn(w: float, inner: str = "") -> str:
    """The Agent figure, as the token's, in greys."""
    body, defs = shapes.agent("#a4a4a4", "#4c4c4c", "#4c4c4c", sx=w / 100, sy=0.97, oy=1.5, outline="#1a1a1a", line="#202020")
    return f"<defs>{defs}</defs>" + body + inner


STONE = lin("stone", "#b8b8b8", "#5e5e5e", 1, 1)
add("agent", pawn(65, '<path d="M32.5,40 V60 M22.5,50 H42.5" stroke="#1a1a1a" stroke-width="8.4" stroke-linecap="square"/>'
                    '<path d="M32.5,40 V60 M22.5,50 H42.5" stroke="#fff" stroke-width="5.6" stroke-linecap="square"/>'),
    STONE, "Agent: a hooded grey figure with a white cross.")
add("recall_agent", pawn(63, arrow_up(31.5, 30, 84, 11)), STONE, "Recall an Agent: the Agent figure with a white arrow up.")

add("arrow_right", f'<polygon points="{pts([(6, 34), (56, 34), (56, 8), (108, 50), (56, 92), (56, 66), (6, 66)])}" fill="#fff" stroke="#2a2a2a" stroke-width="3" stroke-linejoin="round"/>',
    "", "Arrow right: a white block arrow.")
add("arrow_down", f'<polygon points="{pts([(30, 6), (59, 6), (59, 48), (84, 48), (44.5, 94), (5, 48), (30, 48)])}" fill="#fff" stroke="#2a2a2a" stroke-width="3" stroke-linejoin="round"/>',
    "", "Arrow down: a white block arrow.")

for _kind, _note in (("crysknife", "Crysknife battle icon: a pale curved blade on a green slanted tile."),
                     ("desert_mouse", "Desert Mouse battle icon: a jerboa on an orange slanted tile."),
                     ("ornithopter", "Ornithopter battle icon: a winged craft on a blue slanted tile."),
                     ("wild", "Wild battle icon: a question mark on a yellow slanted tile.")):
    _b, _bd = extras2.battle_tile(_kind)
    add(f"battle_{_kind}", _b, _bd, _note)

add("contract",
    f'<polygon points="{pts([(14, 8), (141, 8), (141, 74), (123, 92), (8, 92), (8, 14)])}" fill="url(#leather)" stroke="#2a1608" stroke-width="3" stroke-linejoin="round"/>'
    '<circle cx="74.5" cy="50" r="28" fill="#1a0806" stroke="#e0322a" stroke-width="5"/>'
    '<circle cx="74.5" cy="50" r="17" fill="#000"/>',
    lin("leather", "#c26a3a", "#7a3414", 1, 1), "Contract: a black ring-sealed hole on a brown tile.")

from . import extras3  # noqa: E402

add("control",
    '<path d="M6,4 Q6,2 9,2 H78 Q81,2 81,4 V96 L43.5,79 L6,96 Z" fill="url(#flag)" stroke="#232323" stroke-width="3" stroke-linejoin="round"/>'
    '<rect x="14" y="8" width="59" height="11" fill="#000" opacity=".16"/>'
    + extras3.control_arches(43.5, 64, "#f4f4f4", "#5a5a5a", "#232323"),
    lin("flag", "#d0d0d0", "#8a8a8a"), "Control: a grey banner with two broad arches over a disc.")

sheen = "".join(f'<path d="M{10 + k * 9},90 L{10 + k * 9 + 26},10"/>' for k in range(-2, 5))
b, d = card("", "url(#cdraw)", f'<g clip-path="url(#cl)" stroke="#ffffff26" stroke-width="2">{sheen}</g>')
add("draw", b, lin("cdraw", "#3fbf4a", "#0e6a1c", 1, 1) + '<clipPath id="cl"><rect x="10" y="10" width="46" height="80" rx="3"/></clipPath>',
    "Draw a card: a green card with a sheen.")
b, d = card("", "url(#cdis)", f'<polygon points="{pts([(26, 26), (40, 26), (40, 50), (50, 50), (33, 74), (16, 50), (26, 50)])}" fill="#fff" stroke="#3a1a08" stroke-width="2" stroke-linejoin="round"/>')
add("discard", b, lin("cdis", "#d07a3a", "#7a3410", 1, 1), "Discard a card: a brown card with a white arrow down.")
b, d = card("", "url(#ctr)", '<path d="M21,32 L45,68 M45,32 L21,68" stroke="#fff" stroke-width="8" stroke-linecap="round"/>')
add("trash", b, lin("ctr", "#4a4a4a", "#141414", 1, 1), "Trash a card: a dark card with a white cross.")
_c, _cd = extras.intrigue_card(3, 2, 60, 96)
add("intrigue", _c, _cd, "Intrigue card: a dark olive card in a silver rim with the Intrigue mark.")
_c, _cd = extras.intrigue_card(3, 2, 60, 96, mark=False)
_g, _gd = extras.intrigue_glyph(33, 68, 17)
add("trash_intrigue", _c + '<path d="M22,20 L44,44 M44,20 L22,44" stroke="#111" stroke-width="10" stroke-linecap="round"/>'
    '<path d="M22,20 L44,44 M44,20 L22,44" stroke="#fff" stroke-width="6.4" stroke-linecap="round"/>' + _g, _cd + _gd,
    "Trash an Intrigue card: the Intrigue card with a white cross.")

_st, _std = extras2.steal_intrigue()
add("steal_intrigue", _st, _std, "Steal an Intrigue card: an Intrigue card drawn out of a dark hand of cards.")

add("dreadnought",
    '<g transform="translate(1.5 1.5) scale(1.06 0.97)">'
    + shapes.dreadnought("url(#hulltop)", ["#8a8a8a", "#a8a8a8", "#bcbcbc", "#8e8e8e", "#a4a4a4", "#868686"],
                         outline="#1e1e1e", sticker="#d4d4d4", sticker_w=7, sticker_edge="#2a2a2a") + "</g>",
    lin("hulltop", "#f6f6f6", "#c8c8c8", 0.3, 1), "Dreadnought: a heavy grey hull.")

_fr, _frd = extras2.freighter()
add("freighter", _fr, _frd, "Freighter: a ribbed slate shield with chevrons and a heavy pylon.")

any_q = question(44, 56, 40)
add("influence_any", diamond_influence(88, any_q), INF_GOLD, "Influence with any Faction: a gold step over a black diamond with a question mark.")
add("influence_any_two", diamond_influence(76, question(38, 64, 32), cy=63.3, chevrons=2), INF_GOLD,
    "Influence with any two Factions: two gold steps over the question diamond.")
add("influence_emperor", diamond_influence(88, emperor(43.9, 50.4, 24.8)), INF_GOLD, "Emperor Influence: a gold step over the Emperor's mark in a black diamond.")
add("influence_spacing_guild", diamond_influence(88, guild(43.5, 56.3, 35.8)), INF_GOLD, "Spacing Guild Influence: a gold step over the infinity in a black diamond.")
add("influence_bene_gesserit", diamond_influence(88, bene_gesserit(43.8, 57.6, 29.3)), INF_GOLD, "Bene Gesserit Influence: a gold step over the Bene Gesserit mark.")
add("influence_fremen", diamond_influence(88, fremen(43.8, 54, 25.5)), INF_GOLD, "Fremen Influence: a gold step over the Fremen disc.")
add("influence_lose", diamond_influence(88, question(44, 40, 40), lose=True), INF_RED, "Lose Influence: the question diamond over a red step down.")

add("maker",
    f'<path d="{shapes.poly(shapes.hexagon(57.5, 50, 56))}" fill="none" stroke="#f2f2f2" stroke-width="1.2" opacity=".45" stroke-linejoin="round"/>'
    f'<path d="{shapes.poly(shapes.hexagon(57.5, 50, 52))}" fill="#3e3e3e" stroke="#f2f2f2" stroke-width="1.2" opacity=".9" stroke-linejoin="round"/>'
    f'<path d="{shapes.poly(shapes.hexagon(57.5, 50, 47))}" fill="url(#mk)" stroke="#f6f6f6" stroke-width="2.6" stroke-linejoin="round"/>'
    + shapes.maker_worm(0.82, 57.5 - 41 + 1, 50 - 41 + 1, fill="#f6f6f6", seam="#4a4a4a"),
    rad("mk", "#7a7a7a", "#2e2e2e", 0.5, 0.45), "Maker: a white sandworm coiled in a grey hexagon.")
add("maker_hooks",
    '<path d="M50.0,17.2 L62.6,26.0 L78.3,28.0 L80.5,42.4 L90.0,54.0 L80.5,65.6 L78.3,80.0 L62.6,82.0 L50.0,90.8 L37.4,82.0 L21.7,80.0 L19.5,65.6 L10.0,54.0 L19.5,42.4 L21.7,28.0 L37.4,26.0 Z" fill="url(#bd)" stroke="#1c1e24" stroke-width="7" stroke-linejoin="round"/>'
    '<path d="M50.0,17.2 L62.6,26.0 L78.3,28.0 L80.5,42.4 L90.0,54.0 L80.5,65.6 L78.3,80.0 L62.6,82.0 L50.0,90.8 L37.4,82.0 L21.7,80.0 L19.5,65.6 L10.0,54.0 L19.5,42.4 L21.7,28.0 L37.4,26.0 Z" fill="none" stroke="#a8acb4" stroke-width="3" stroke-linejoin="round"/>'
    '<path d="M16,90 L78,22" stroke="#1c1e24" stroke-width="12" stroke-linecap="round"/>'
    '<path d="M78,22 C90,10 104,18 104,32 C104,44 98,52 92,58" fill="none" stroke="#1c1e24" stroke-width="9" stroke-linecap="round"/>'
    '<path d="M14,92 L28,77" stroke="#1c1e24" stroke-width="17" stroke-linecap="square"/>'
    '<path d="M16,90 L78,22" stroke="url(#hk)" stroke-width="6.5" stroke-linecap="round"/>'
    '<path d="M78,22 C90,10 104,18 104,32 C104,44 98,52 92,58" fill="none" stroke="url(#hk)" stroke-width="4.6" stroke-linecap="round"/>'
    '<path d="M14,92 L28,77" stroke="#9aa0a8" stroke-width="11" stroke-linecap="square"/>',
    lin("hk", "#eef0f2", "#a0a6ae", 1, 1) + rad("bd", "#6e86b4", "#34466e", 0.45, 0.4), "Maker Hooks: a steel hook across a blue badge.")

add("persuasion", '<polygon points="50,4 96,50 50,96 4,50" fill="url(#pz)" stroke="#f4f8ff" stroke-width="4" stroke-linejoin="round"/>'
    '<polygon points="50,4 96,50 50,96 4,50" fill="none" stroke="#1d3b63" stroke-width="1.4" stroke-linejoin="round"/>',
    lin("pz", "#64aee6", "#2a5f9e", 1, 1), "Persuasion: a blue diamond with a white rim.")

_worm, _worm_defs = shapes.sandworm("#f8f8f8", "#d2d2d2", "#747474", sticker=None, outline="#1e1e1e")
add("sandworm", f'<g transform="translate(2.5 0)">{_worm}</g>', _worm_defs, "Sandworm: a grey worm rising out of the sand and curling over.")

_sw, _swd = extras2.shield_wall()
add("shield_wall", _sw, _swd, "Shield Wall: a stone wall split by a jagged crack over a red step down.")

_r, _rd = extras3.signet_ring(113, 100)
add("signet_ring", _r, _rd, "Signet Ring: a gold ring at a slant, its broad dark seal face toward us.")

add("specimen",
    '<polygon points="47,6 88,26 47,46 6,26" fill="#a6e86a" stroke="#1e3a0a" stroke-width="2.4" stroke-linejoin="round"/>'
    '<polygon points="6,26 47,46 47,94 6,74" fill="#6cb43a" stroke="#1e3a0a" stroke-width="2.4" stroke-linejoin="round"/>'
    '<polygon points="88,26 47,46 47,94 88,74" fill="#4a8a24" stroke="#1e3a0a" stroke-width="2.4" stroke-linejoin="round"/>'
    '<circle cx="38" cy="24" r="4" fill="#7ac24a"/><circle cx="58" cy="30" r="3" fill="#7ac24a"/>'
    '<circle cx="20" cy="54" r="4" fill="#4e9228"/><circle cx="66" cy="62" r="5" fill="#3a6e1a"/><circle cx="32" cy="74" r="3" fill="#4e9228"/>',
    "", "Specimen: a green, mottled cube.")

add("spice", f'<polygon points="{pts([(56.5 + 52 * math.cos(math.pi / 3 * k), 50 + 46 * math.sin(math.pi / 3 * k)) for k in range(6)])}" fill="url(#spi)" stroke="#7a2a06" stroke-width="3.4" stroke-linejoin="round"/>',
    lin("spi", "#f59a4a", "#c24a14"), "Spice: an orange hexagon.")

add("spy",
    '<path d="M5,18 V82 A30,13.5 0 0 0 65,82 V18 A30,13.5 0 0 0 5,18 Z" fill="#232323"/>'
    '<path d="M10,19 V81 A25,10 0 0 0 60,81 V19 Z" fill="url(#cyl)"/>'
    '<ellipse cx="35" cy="19" rx="25" ry="10" fill="url(#cyltop)" stroke="#232323" stroke-width="2"/>'
    '<path d="M17,30 V80" stroke="#fff" stroke-width="3" opacity=".35" stroke-linecap="round"/>',
    lin("cyl", "#8e8e8e", "#dadada", 1, 0) + lin("cyltop", "#fafafa", "#c4c4c4"), "Spy: a grey cylinder.")
add("recall_spy",
    '<path d="M6,26 V84 A24,11 0 0 0 54,84 V26" fill="url(#cyl)" stroke="#222" stroke-width="2.6"/>'
    '<ellipse cx="30" cy="26" rx="24" ry="11" fill="url(#cyltop)" stroke="#222" stroke-width="2.6"/>' + arrow_up(56, 6, 74, 16),
    lin("cyl", "#9a9a9a", "#d8d8d8", 1, 0) + lin("cyltop", "#f2f2f2", "#bdbdbd"), "Recall a Spy: the Spy cylinder with a white arrow up.")

_s, _sd = extras.sword(0, 0, 74, 100)
add("sword", _s, _sd, "Sword (strength): a broad red blade over a dark square stood on its corner.")

add("tech_negotiation",
    f'<polygon points="{pts([(46.5 + 44 * math.cos(math.pi / 3 * k + math.pi / 6), 50 + 47 * math.sin(math.pi / 3 * k + math.pi / 6)) for k in range(6)])}" fill="#262614" stroke="url(#gold)" stroke-width="6" stroke-linejoin="round"/>'
    + gear(46.5, 50, 26),
    GOLD, "Tech Negotiation: a gold gear in a gold-rimmed hexagon.")

TILE = lin("tile", "#8a9a3a", "#3e4a14", 1, 1)
add("acquire_tech",
    '<rect x="6" y="10" width="158" height="80" rx="6" fill="url(#tile)" stroke="#e2cf6a" stroke-width="4"/>'
    '<path d="M30,10 L60,90 M70,10 L100,90" stroke="#ffffff1c" stroke-width="10"/>' + gear(85, 50, 26),
    TILE, "Acquire a Tech tile: a gear on an olive tile.")
for n in (1, 2):
    add(f"acquire_tech_minus{n}",
        '<rect x="44" y="30" width="114" height="64" rx="5" fill="url(#tile)" stroke="#e2cf6a" stroke-width="3.6"/>' + gear(101, 62, 20)
        + f'<polygon points="{pts([(10 + 26 + 24 * math.cos(math.pi / 3 * k), 30 + 24 * math.sin(math.pi / 3 * k)) for k in range(6)])}" fill="url(#hx)" stroke="#fff" stroke-width="3"/>'
        + f'<text x="36" y="39" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="26" fill="#fff">-{n}</text>',
        TILE + lin("hx", "#f08a3a", "#c24a14"), f"Acquire a Tech tile for {n} spice less: the Tech tile under an orange -{n} hexagon.")

add("troop",
    '<polygon points="47,2 91,25 91,75 47,98 3,75 3,25" fill="#2a2a2a" stroke="#2a2a2a" stroke-width="2" stroke-linejoin="round"/>'
    '<polygon points="47,7 86,27.5 86,72.5 47,93 8,72.5 8,27.5" fill="#d8d8d8"/>'
    '<polygon points="47,11 82,29 47,47 12,29" fill="#f6f6f6"/>'
    '<polygon points="12,29 47,47 47,89 12,71" fill="#c2c2c2"/>'
    '<polygon points="82,29 47,47 47,89 82,71" fill="#8e8e8e"/>'
    '<path d="M12,29 L47,47 L82,29 M47,47 V89" fill="none" stroke="#5a5a5a" stroke-width="1.2" opacity=".6"/>',
    "", "Troop: a grey cube.")

add("unload",
    '<polygon points="6,12 128,12 146,50 128,88 6,88" fill="url(#ul)" stroke="#2a0606" stroke-width="3" stroke-linejoin="round"/>'
    '<rect x="22" y="22" width="36" height="56" rx="4" fill="#1a1a1a" stroke="#f2f2f2" stroke-width="2.6"/>'
    f'<polygon points="{pts([(36, 34), (44, 34), (44, 48), (50, 48), (40, 62), (30, 48), (36, 48)])}" fill="#fff"/>'
    '<rect x="70" y="22" width="36" height="56" rx="4" fill="#1a1a1a" stroke="#f2f2f2" stroke-width="2.6"/>'
    '<path d="M80,38 L96,62 M96,38 L80,62" stroke="#fff" stroke-width="5.4" stroke-linecap="round"/>',
    lin("ul", "#c2302a", "#6a0e0e"), "Unload: a discard card and a trash card on a red tag.")

_v, _vd = extras.victory_point(50, 50, 30)
add("victory_point", _v, _vd, "Victory point: a golden world with its two moons under a white starburst.")

add("water", '<path d="M34,4 Q46,30 58,48 Q72,72 56,88 Q34,104 14,88 Q-2,72 10,48 Q22,30 34,4 Z" fill="url(#wt)" stroke="#123a5a" stroke-width="3" stroke-linejoin="round"/>'
    '<path d="M18,64 Q16,78 28,86" fill="none" stroke="#e8f6ff" stroke-width="4" stroke-linecap="round" opacity=".8"/>',
    lin("wt", "#a8dcff", "#3a8ed0"), "Water: a blue drop.")

# ------------------------------------------------------------- log icons


def logadd(name: str, body: str, defs: str, note: str) -> None:
    CURRENT[0] = "log_" + name
    LOGS[name] = (svg(100, body, defs, note), note)


logadd("card_trashed", '<path d="M18,18 L82,82 M82,18 L18,82" stroke="#5a0a0a" stroke-width="22" stroke-linecap="round"/>'
       '<path d="M18,18 L82,82 M82,18 L18,82" stroke="#d8302c" stroke-width="15" stroke-linecap="round"/>', "", "Log: a card trashed, a red cross.")
logadd("conflict", extras2.crossed_blades("#e8242c", "#3a0406", shade="#a80c14"), "", "Log: the Conflict, two crossed red swords.")
logadd("family_atomics",
       '<path d="M12,10 H88 V50 Q88,82 50,96 Q12,82 12,50 Z" fill="url(#fa)" stroke="#2a1606" stroke-width="3" stroke-linejoin="round"/>'
       '<g fill="none" stroke="#f0d8b0" stroke-width="3"><ellipse cx="50" cy="50" rx="28" ry="10"/>'
       '<ellipse cx="50" cy="50" rx="28" ry="10" transform="rotate(60 50 50)"/><ellipse cx="50" cy="50" rx="28" ry="10" transform="rotate(-60 50 50)"/></g>'
       '<circle cx="50" cy="50" r="6" fill="#f0d8b0"/>',
       lin("fa", "#a8582a", "#5a2a10"), "Log: Family Atomics, an atom on a brown shield.")
for faction, symbol in (("emperor", emperor(49, 37, 24.3)), ("spacing_guild", guild(49, 41.7, 38)),
                        ("bene_gesserit", bene_gesserit(49, 41.8, 29.5)), ("fremen", fremen(49, 42.6, 26.5))):
    logadd(f"influence_down_{faction}", diamond_influence(98, symbol, lose=True, half=42),
           INF_RED, f"Log: {faction.replace('_', ' ').title()} Influence lost, its mark over a red step down.")
_g, _gd = extras.intrigue_glyph(50, 50, 46)
logadd("intrigue", _g, _gd, "Log: the Intrigue mark.")
_c, _cd = extras.intrigue_card(24, 8, 52, 84)
logadd("intrigue_played", f'<g transform="rotate(14 50 50)">{_c}</g>', _cd, "Log: an Intrigue card played, a tilted Intrigue card.")
_m, _md = extras3.microscope(0, 0, 1)
logadd("research", _m, _md, "Log: research, a chunky pale microscope on a dark slab.")
logadd("reshuffle", "".join(
    f'<rect x="{26 + k * 9}" y="{12 + k * 7}" width="40" height="62" rx="5" fill="url(#rs)" stroke="#f2f2f2" stroke-width="2.6"/>' for k in range(3)),
    lin("rs", "#3fbf4a", "#0e6a1c", 1, 1), "Log: the deck reshuffled, three green cards.")
for n in range(1, 11):
    logadd(f"round_{n}", f'<text x="50" y="82" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="900" '
           f'font-size="{84 if n < 10 else 68}" fill="#fff" stroke="#1a1a1a" stroke-width="2.4" paint-order="stroke">{n}</text>',
           "", f"Log: Round {n}, the numeral.")
logadd("tech", '<rect x="6" y="6" width="88" height="88" rx="10" fill="url(#tile)" stroke="#e2cf6a" stroke-width="3"/>' + gear(50, 50, 30),
       TILE, "Log: Tech, a plain gear on an olive tile.")
beetle = ('<polygon points="50,4 96,50 50,96 4,50" fill="#141414" stroke="#d9a62a" stroke-width="2.6" stroke-linejoin="round"/>'
          '<ellipse cx="50" cy="56" rx="20" ry="25" fill="url(#gold)" stroke="#5a3a00" stroke-width="2"/>'
          '<path d="M50,34 V80" stroke="#5a3a00" stroke-width="2"/>'
          '<ellipse cx="50" cy="30" rx="11" ry="8" fill="url(#gold)" stroke="#5a3a00" stroke-width="2"/>'
          '<path d="M30,44 L20,36 M30,58 L18,58 M32,72 L22,80 M70,44 L80,36 M70,58 L82,58 M68,72 L78,80 M44,22 L38,14 M56,22 L62,14" stroke="#e2b23a" stroke-width="3" stroke-linecap="round"/>')
logadd("tleilaxu", beetle, GOLD, "Log: Tleilaxu, a gold beetle on a black diamond.")
for name, up in (("troop_deploy", True), ("troop_retreat", False)):
    arrow = arrow_up(50, 22, 80, 18) if up else arrow_up(50, 22, 80, 18).replace("<polygon", '<polygon transform="rotate(180 50 51)"', 1)
    logadd(name, f'<polygon points="{pts([(50 + 44 * math.cos(math.pi / 3 * k + math.pi / 6), 50 + 44 * math.sin(math.pi / 3 * k + math.pi / 6)) for k in range(6)])}" fill="url(#tb)" stroke="#2a2a2a" stroke-width="3"/>' + arrow,
           lin("tb", "#9a9a9a", "#4a4a4a"), f"Log: troops {'deployed' if up else 'retreated'}, a white arrow {'up' if up else 'down'} on a grey hexagon.")
wreath = ""
for k in range(7):
    a = 100 + k * 20  # degrees, from the bottom up the left side
    x = 50 + 42 * math.cos(math.radians(a))
    y = 50 + 42 * math.sin(math.radians(a))
    for lx, rot in ((x, a), (100 - x, -a)):
        wreath += f'<ellipse cx="{f(lx)}" cy="{f(y)}" rx="4.6" ry="10" transform="rotate({f(rot)} {f(lx)} {f(y)})" fill="#d89a1a" stroke="#5a3a00" stroke-width="1.4"/>'
_v, _vd = extras.victory_point(50, 47, 20)
logadd("vp_winner", wreath + _v, _vd, "Log: the winner, the golden world in a gold laurel.")


def build(index: dict) -> dict[str, str]:
    """Every drawing this module makes, by path under ``static/pictures``;
    ``index`` (the folder's index.json) gets each drawing's note."""
    files: dict[str, str] = {}
    for name, (text, note) in ICONS.items():
        files[f"icons/{name}.svg"] = text
        index[f"icons/{name}.svg"] = {"drawn": DRAWN, "note": note}
    for name, (text, note) in LOGS.items():
        files[f"log/{name}.svg"] = text
        index[f"log/{name}.svg"] = {"drawn": DRAWN, "note": note}
    # The card faces' Agent icons: the mark alone, no plate or well (the faces
    # need not copy print's grey plates, user 2026-11-11).
    for icon in ("emperor", "spacing_guild", "bene_gesserit", "fremen", "landsraad", "city", "spice_trade", "spy"):
        text, _ = ICONS[f"agent_icon_{icon}"]
        text = re.sub(r'<g class="(?:plate|well)">.*?</g>', "", text, flags=re.S)
        text = re.sub(r'<svg [^>]*>', '<svg xmlns="http://www.w3.org/2000/svg" width="102" height="86" viewBox="14 4 102 86">', text, count=1)
        text = re.sub(r"<!--.*?-->", f"<!-- The {icon.replace('_', ' ')} Agent mark alone, for the redrawn card faces. Drawn by hand for the public build. -->", text, count=1, flags=re.S)
        files[f"faces/agent_mark_{icon}.svg"] = text
        index[f"faces/agent_mark_{icon}.svg"] = {"drawn": DRAWN, "note": f"The {icon.replace('_', ' ')} Agent mark alone (no plate), for the card faces."}
        # The icon set's Agent icons are the mark alone too (the action log,
        # Lady Jessica's memories, leader text: user 2026-11-11 "Yes, all of
        # them"); the board script still lays them in the plate's 136 x 100 box.
        word = icon.replace("_", " ")
        bare = re.sub(r"<!--.*?-->", f"<!-- The {word} Agent mark alone, no stone plate. Drawn by hand for the public build. -->", text, count=1, flags=re.S)
        files[f"icons/agent_icon_{icon}.svg"] = bare
        index[f"icons/agent_icon_{icon}.svg"] = {"drawn": DRAWN, "note": f"The {word} Agent icon: its mark alone, no stone plate."}
    # The Faction badges card text prints its Faction marks on (Influence and
    # Alliance conditions): the mark on a small dark rounded square.
    for faction in ("emperor", "spacing_guild", "bene_gesserit", "fremen"):
        body, defs = extras.faction_badge(faction)
        files[f"faces/faction_{faction}.svg"] = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">\n'
            f"  <!-- The {faction.replace('_', ' ')} badge card text prints: its mark on a dark rounded square. Drawn by hand for the public build. -->\n"
            f"  <defs>{defs}</defs>\n  {body}\n</svg>\n")
        index[f"faces/faction_{faction}.svg"] = {"drawn": DRAWN, "note": f"The {faction.replace('_', ' ')} mark on the dark badge card text prints it on."}
    def face_svg(name: str, w: float, h: float, body: str, defs: str, note: str, box: str = "") -> None:
        files[f"faces/{name}.svg"] = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{f(w)}" height="{f(h)}" viewBox="{box or f'0 0 {f(w)} {f(h)}'}">\n'
            f"  <!-- {note} Drawn by hand for the public build. -->\n" + (f"  <defs>{defs}</defs>\n" if defs else "") + f"  {body}\n</svg>\n")
        index[f"faces/{name}.svg"] = {"drawn": DRAWN, "note": note}

    # Combat: two white swords crossed, as card text and the board print it.
    face_svg("combat", 100, 100, extras2.crossed_blades("#f4f4f4", "#1e1e1e", shade="#b8b8b8"), "",
             "Combat: two white swords crossed (card text, the board's combat spaces).")
    # A Conflict card's corner prints its battle icon's mark alone.
    for kind in extras2.BATTLE_COLORS:
        face_svg(f"battle_mark_{kind}", 100, 100, extras2.battle_mark(kind), "",
                 f"The {kind.replace('_', ' ')} battle mark alone, for a Conflict card's corner.")
    # The Mentat (a Conflict reward, Sort Through the Chaos): the Agent's
    # hooded figure as a dark silhouette, as print draws it.
    _mb = pawn(65, "")
    for _old, _new in (("#ffffff", "#7a7a7a"), ("#a4a4a4", "#2c2c2c"), ("#4c4c4c", "#0e0e0e"), ("#b8b8b8", "#3a3a3a"), ("#5e5e5e", "#141414")):
        _mb = _mb.replace(_old, _new)
    _md = STONE.replace("#b8b8b8", "#3a3a3a").replace("#5e5e5e", "#141414")
    face_svg("mentat", 65, 100, _mb, _md, "The Mentat: the Agent's hooded figure as a dark silhouette (a Conflict reward).")
    _uc, _ucd = extras3.unload_cards()
    face_svg("unload_cards", 100, 66, _uc, _ucd, "Unload's two cards (draw, trash), for the red tag down a Reveal box's left edge.")
    _fl, _fld = extras2.tech_flip()
    face_svg("flip", 100, 80, _fl, _fld, "Flip a Tech tile: a gold-rimmed tile tipping over, a white arrow round it.")
    # A genetic marker (Immortality): a red diamond with a white twist, as
    # the board's {dna}; the faces print one or two of them.
    helix = "".join(
        f'<path d="M{f(30 + 9 * math.sin(t))},{f(16 + t / math.pi * 12)} L{f(30 - 9 * math.sin(t))},{f(16 + t / math.pi * 12)}" stroke="#fff" stroke-width="1.6" opacity=".7"/>'
        for t in (k * math.pi / 4 for k in range(1, 16, 2)))
    strand = lambda sign: "M" + " L".join(  # noqa: E731
        f"{f(30 + sign * 9 * math.sin(k * math.pi / 8))},{f(16 + k * 1.5)}" for k in range(0, 33))
    dna = ('<svg xmlns="http://www.w3.org/2000/svg" width="60" height="80" viewBox="0 0 60 80">\n'
           "  <!-- A genetic marker: a red diamond with a white twist. Drawn by hand for the public build. -->\n"
           '  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f04a5c"/><stop offset="1" stop-color="#a60e26"/></linearGradient></defs>\n'
           '  <polygon points="30,2 58,40 30,78 2,40" fill="url(#g)" stroke="#fff3f4" stroke-width="3" stroke-linejoin="round"/>'
           '<polygon points="30,2 58,40 30,78 2,40" fill="none" stroke="#5a0614" stroke-width="1" stroke-linejoin="round"/>'
           + helix + f'<path d="{strand(1)}" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/>'
           f'<path d="{strand(-1)}" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/>\n</svg>\n')
    files["faces/genetic_marker.svg"] = dna
    index["faces/genetic_marker.svg"] = {"drawn": DRAWN, "note": "A genetic marker: a red diamond with a white twist, for the card faces."}
    return files

