# ruff: noqa: E501  (SVG markup reads best one element to a line)
"""The four Faction marks, drawn carefully after the game's icons
(which adapt the 2021 film's signs). Each mark is drawn in its own unit
space and placed with translate/scale; every piece is a gradient band or
shape over a dark outline, outlines first so joins stay clean."""

from __future__ import annotations

import itertools

_ids = itertools.count()
OUTLINE = "#0c0c0c"


def _f(x: float) -> str:
    return f"{x:.3f}".rstrip("0").rstrip(".")


def _grad(stops: list[tuple[float, str]], vertical: bool = True) -> tuple[str, str]:
    gid = f"mk{next(_ids)}"
    x2, y2 = ("0", "1") if vertical else ("1", "0")
    body = "".join(f'<stop offset="{_f(o)}" stop-color="{c}"/>' for o, c in stops)
    return gid, f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}">{body}</linearGradient>'


Tone = tuple[str, str, str]  # (top fill, bottom fill, outline)


def _fill(stops: list[tuple[float, str]], tone: Tone | None) -> tuple[str, str]:
    return _grad([(0, tone[0]), (1, tone[1])] if tone else stops)


def _place(cx: float, cy: float, scale: float, inner: str, defs: str) -> str:
    return f'<g transform="translate({_f(cx)} {_f(cy)}) scale({_f(scale)})"><defs>{defs}</defs>{inner}</g>'


def _ellipse_hit(angle: float, rx: float, ry: float, cy: float) -> tuple[float, float]:
    """Where the ray from the origin at angle meets the ellipse (0, cy, rx, ry)."""
    import math
    dx, dy = math.cos(angle), math.sin(angle)
    a = (dx / rx) ** 2 + (dy / ry) ** 2
    b = -2 * dy * cy / ry ** 2
    c = (cy / ry) ** 2 - 1
    t = (-b + (b * b - 4 * a * c) ** 0.5) / (2 * a)
    return dx * t, dy * t


def emperor(cx: float, cy: float, r: float, tone: Tone | None = None) -> str:
    """Unit = the dome's outer radius. The dome is a crescent, thick at the
    top and thin at its ends, open over the bottom 90 degrees. The bar's
    straight top runs past the dome to short points; its underside sweeps
    into the stem, and a dark split runs from the bar's top to the stem's
    two rounded feet, which fade to grey."""
    ol = tone[2] if tone else OUTLINE
    import math
    ring, rdef = _fill([(0, "#ffffff"), (1, "#f2f2f2")], tone)
    stem, sdef = _fill([(0, "#ffffff"), (0.55, "#f0f0f0"), (0.78, "#e4e4e4"), (1, "#8c8c8c")], tone)
    ang = math.radians(46)
    ox, oy = math.cos(ang), math.sin(ang)
    ix, iy = _ellipse_hit(ang, 0.915, 0.91, 0.06)
    dome = (f"M{_f(-ox)},{_f(oy)} A1,1 0 1 1 {_f(ox)},{_f(oy)} "
            f"L{_f(ix)},{_f(iy)} A0.915,0.91 0 1 0 {_f(-ix)},{_f(iy)} Z")
    half = ("M0.055,-0.09 L1.1,-0.09 C1.14,-0.085 1.165,-0.06 1.175,-0.03 "
            "C0.75,0.13 0.32,0.12 0.285,0.36 "
            "C0.27,0.7 0.215,1.2 0.2,1.45 C0.19,1.55 0.16,1.6 0.125,1.6 "
            "C0.085,1.6 0.055,1.56 0.055,1.5 Z")
    out = ""
    for d, t in ((dome, ""), (half, ""), (half, ' transform="scale(-1 1)"')):
        out += f'<path d="{d}"{t} fill="{ol}" stroke="{ol}" stroke-width="0.085" stroke-linejoin="round"/>'
    out += f'<path d="{dome}" fill="url(#{ring})"/>'
    out += f'<g fill="url(#{stem})"><path d="{half}"/><path d="{half}" transform="scale(-1 1)"/></g>'
    return _place(cx, cy, r, out, rdef + sdef)


def guild(cx: float, cy: float, r: float, tone: Tone | None = None) -> str:
    """Unit = half the width. A filled band, thick on the right loop's far
    end and on the small left loop's top; both eyes are almonds pointed at
    the crossing, which sits left of the centre and leans."""
    ol = tone[2] if tone else OUTLINE
    gid, gdef = _fill([(0, "#ff5a64"), (0.3, "#ff4450"), (0.7, "#ff2a2c"), (1, "#ff1414")], tone)
    outer = ("M-0.16,-0.16 C0.02,-0.42 0.2,-0.48 0.43,-0.48 C0.78,-0.48 1,-0.3 1,0 C1,0.3 0.78,0.48 0.45,0.48 "
             "C0.18,0.48 -0.04,0.38 -0.24,0.16 C-0.34,0.3 -0.46,0.34 -0.6,0.34 C-0.84,0.34 -1,0.2 -1,0.01 "
             "C-1,-0.22 -0.84,-0.4 -0.62,-0.4 C-0.42,-0.4 -0.28,-0.32 -0.16,-0.16 Z")
    right = ("M-0.07,0 C0.1,-0.22 0.25,-0.3 0.42,-0.3 C0.62,-0.3 0.73,-0.16 0.73,-0.01 "
             "C0.73,0.15 0.62,0.27 0.42,0.27 C0.25,0.27 0.1,0.2 -0.07,0 Z")
    left = ("M-0.33,0.03 C-0.4,-0.08 -0.5,-0.16 -0.6,-0.16 C-0.74,-0.16 -0.82,-0.08 -0.82,0.03 "
            "C-0.82,0.13 -0.74,0.21 -0.6,0.21 C-0.5,0.21 -0.4,0.14 -0.33,0.03 Z")
    d = outer + " " + right + " " + left
    out = (f'<path d="{d}" fill="url(#{gid})" fill-rule="evenodd" stroke="{ol}" stroke-width="0.05" stroke-linejoin="round"/>'
           + ('' if tone else '<path d="M0.22,-0.41 C0.42,-0.46 0.7,-0.43 0.85,-0.27" fill="none" stroke="#ffb4b0" stroke-width="0.028" stroke-linecap="round" opacity=".55"/>'))
    return _place(cx, cy, r, out, gdef)


def bene_gesserit(cx: float, cy: float, r: float, tone: Tone | None = None) -> str:
    """Unit = half the width. Two C brackets with rounded ends, bowed out
    a little above and below the middle, where the eye loops leave them;
    the loops meet at the centre, crossed by an upright spindle."""
    ol = tone[2] if tone else OUTLINE
    gid, gdef = _fill([(0, "#f4c4ff"), (0.45, "#dc9cfa"), (1, "#c672ea")], tone)
    bands = []
    for s in (-1, 1):
        for v in (-1, 1):
            bands.append(f"M{_f(s * 0.4)},{_f(v * 0.73)} C{_f(s * 0.7)},{_f(v * 0.78)} {_f(s * 0.9)},{_f(v * 0.6)} {_f(s * 0.9)},0")
    loops = [f"M{_f(s * 0.9)},0 Q{_f(s * 0.48)},-0.43 {_f(s * 0.05)},0 Q{_f(s * 0.48)},0.43 {_f(s * 0.9)},0 Z" for s in (-1, 1)]
    spindle = ("M0,-0.39 C0.045,-0.39 0.062,-0.36 0.062,-0.3 C0.062,-0.18 0.08,-0.07 0.13,0 "
               "C0.08,0.07 0.062,0.19 0.062,0.33 C0.062,0.39 0.045,0.42 0,0.42 C-0.045,0.42 -0.062,0.39 -0.062,0.33 "
               "C-0.062,0.19 -0.08,0.07 -0.13,0 C-0.08,-0.07 -0.062,-0.18 -0.062,-0.3 C-0.062,-0.36 -0.045,-0.39 0,-0.39 Z")
    bw, lw, o = 0.15, 0.13, 0.05
    out = ""
    for d in bands:
        out += f'<path d="{d}" fill="none" stroke="{ol}" stroke-width="{_f(bw + o)}" stroke-linecap="round"/>'
    for d in loops:
        out += f'<path d="{d}" fill="none" stroke="{ol}" stroke-width="{_f(lw + o)}" stroke-linejoin="round"/>'
    knobs = [(s * 0.4, v * 0.73) for s in (-1, 1) for v in (-1, 1)]
    kr = bw * 0.6
    for x, y in knobs:
        out += f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(kr + o / 2)}" fill="{ol}"/>'
    out += f'<path d="{spindle}" fill="{ol}" stroke="{ol}" stroke-width="{_f(o)}" stroke-linejoin="round"/>'
    for x, y in knobs:
        out += f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(kr)}" fill="url(#{gid})"/>'
    for d in bands:
        out += f'<path d="{d}" fill="none" stroke="url(#{gid})" stroke-width="{bw}" stroke-linecap="round"/>'
    for d in loops:
        out += f'<path d="{d}" fill="none" stroke="url(#{gid})" stroke-width="{lw}" stroke-linejoin="round"/>'
    out += f'<path d="{spindle}" fill="url(#{gid})"/>'
    return _place(cx, cy, r, out, gdef)


def fremen(cx: float, cy: float, r: float, tone: Tone | None = None) -> str:
    """Unit = the disc's radius. A dark band as tall as the centre disc
    crosses the disc; the centre disc sits in it touching both caps, and a
    dark line splits the whole mark, the centre disc too."""
    ol = tone[2] if tone else OUTLINE
    top, tdef = _fill([(0, "#b6eeff"), (1, "#8cd0ff")], tone)
    core, cdef = _fill([(0, "#7ac6ff"), (0.85, "#62b4f8"), (1, "#72d2ff")], tone)
    bottom, bdef = _fill([(0, "#56acf2"), (1, "#3690da")], tone)
    h = 0.4
    c = (1 - h * h) ** 0.5
    top_cap = f"M{_f(-c)},{_f(-h)} A1,1 0 0 1 {_f(c)},{_f(-h)} Z"
    bottom_cap = f"M{_f(-c)},{_f(h)} A1,1 0 0 0 {_f(c)},{_f(h)} Z"
    w = 0.05
    out = (f'<path d="{top_cap}" fill="url(#{top})" stroke="{ol}" stroke-width="{w}" stroke-linejoin="round"/>'
           f'<path d="{bottom_cap}" fill="url(#{bottom})" stroke="{ol}" stroke-width="{w}" stroke-linejoin="round"/>'
           f'<circle r="0.42" fill="url(#{core})" stroke="{ol}" stroke-width="{w}"/>'
           f'<path d="M0,-1 V1" stroke="{ol}" stroke-width="0.065"/>'
           + ('' if tone else '<path d="M-0.66,-0.6 A0.9,0.9 0 0 1 -0.14,-0.86" fill="none" stroke="#fff" stroke-width="0.03" stroke-linecap="round" opacity=".45"/>'))
    return _place(cx, cy, r, out, tdef + cdef + bdef)
