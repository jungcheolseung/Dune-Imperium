# ruff: noqa: E501  (SVG markup reads best one element to a line)
"""Shared piece shapes for the tokens and icons, drawn in our own
lines after the game's pieces (proportions read off them on a grid).

Every shape is in a 100-unit box; callers scale it into their viewBox.
"""

from __future__ import annotations

import itertools
import math

_ids = itertools.count()


def f(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".")


def uid(prefix: str) -> str:
    return f"{prefix}{next(_ids)}"


def lin(gid: str, stops: list[tuple[float, str]], x2: float = 0, y2: float = 1) -> str:
    body = "".join(f'<stop offset="{f(o)}" stop-color="{c}"/>' for o, c in stops)
    return f'<linearGradient id="{gid}" x1="0" y1="0" x2="{f(x2)}" y2="{f(y2)}">{body}</linearGradient>'


def poly(points) -> str:
    return "M" + " L".join(f"{f(x)},{f(y)}" for x, y in points) + " Z"


# ------------------------------------------------------------------ sandworm

# The piece's visible side: under the sand line and down the tail's flick.
WORM_SIDE = "M6,77.5 L16,88 L84,88 L88.5,70.5 L93,77 L87.5,94 L18.5,94 L8.5,83 Z"

# The sandworm piece: a worm rising out of the sand and curling over like a
# 2, its blunt head at the top left, a splash where it leaves the sand at the
# lower left and a flick of sand at its tail on the right.
WORM = ("M9,21 C14,17.5 20,15.5 25,12.5 C32,8 40,6 47,6 C60,6.5 72,13 80,24 C86,32 90,40 89.5,48 "
        "C89,57 84,64 79,69 L78.5,72 L80.5,75.5 L88.5,70.5 L84,88 L16,88 L6,77.5 L17.5,79.5 L16,72 "
        "L24.5,75.5 L28.5,71.5 C33,64 41,54 52,44.5 C44,46.5 37,57.5 30.5,57.8 C23,58 14,44 10,33 Z")


def extrude(d: str, dx: float, dy: float, front: str, side: str, *, steps: int = 8,
            outline: str = "#0a0a0a", outline_w: float = 2.8, sticker: str | None = None,
            sticker_w: float = 9.0, extra: str = "") -> str:
    """A flat piece seen from above at a slant: its face `d`, swept by
    (dx, dy) for the visible side, a dark line round the whole and an
    optional pale sticker edge outside it. `extra` is drawn on the face."""
    copies = [(dx * k / steps, dy * k / steps) for k in range(steps, -1, -1)]

    def at(ox: float, oy: float, attrs: str) -> str:
        move = f' transform="translate({f(ox)} {f(oy)})"' if ox or oy else ""
        return f'<path d="{d}"{move} {attrs}/>'

    out = ""
    if sticker:
        out += "".join(at(ox, oy, f'fill="{sticker}" stroke="{sticker}" stroke-width="{f(sticker_w)}" stroke-linejoin="round"') for ox, oy in copies)
    out += "".join(at(ox, oy, f'fill="{outline}" stroke="{outline}" stroke-width="{f(outline_w)}" stroke-linejoin="round"') for ox, oy in copies)
    out += "".join(at(ox, oy, f'fill="{side}"') for ox, oy in copies[:-1])
    out += at(0, 0, f'fill="{front}"')
    return out + extra


def sandworm(light: str, base: str, side: str, *, sticker: str | None, outline: str = "#0a0a0a") -> tuple[str, str]:
    """The sandworm piece in the 100 box; returns (body, defs)."""
    face, clip, soft = uid("wf"), uid("wc"), uid("ws")
    defs = (lin(face, [(0, light), (0.55, base), (1, base)])
            + f'<clipPath id="{clip}"><path d="{WORM}"/></clipPath>'
            + f'<filter id="{soft}" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2.4"/></filter>')
    shade = (f'<g clip-path="url(#{clip})">'
             # The arch rounds off into the hollow under it and along the body's inner side.
             f'<path d="M14,40 C22,56 34,60 52,44.5 C40,52 30,52 22,44 Z" fill="#000" opacity=".38" filter="url(#{soft})"/>'
             # The inner side of the curl, seen through the slit under it.
             f'<path d="M26,54 C34,51 43,45.5 52,44.5 C47,38.5 38,36 31,40 C28,43 26.5,48 26,54 Z" fill="#000" opacity=".42"/>'
             f'<path d="M31,41 C37,37 46,38.5 51.5,44" fill="none" stroke="#fff" stroke-width="1.2" opacity=".2"/>'
             f'<path d="M72,36 C82,46 84,60 76,70" fill="none" stroke="#000" stroke-width="7" opacity=".16" filter="url(#{soft})"/>'
             # Light along the top of the arch and down the head.
             f'<path d="M14,22 C26,12 44,8 58,10 C68,12 76,18 82,28" fill="none" stroke="#fff" stroke-width="5" opacity=".22" filter="url(#{soft})"/>'
             # The base's front edge catches the light too.
             f'<path d="M20,86.5 H83" stroke="#fff" stroke-width="1.6" opacity=".18"/>'
             '</g>')
    out = ""
    for d in (WORM, WORM_SIDE):
        if sticker:
            out += f'<path d="{d}" fill="{sticker}" stroke="{sticker}" stroke-width="9" stroke-linejoin="round"/>'
    for d in (WORM, WORM_SIDE):
        out += f'<path d="{d}" fill="{outline}" stroke="{outline}" stroke-width="2.8" stroke-linejoin="round"/>'
    out += f'<path d="{WORM_SIDE}" fill="{side}"/>'
    out += '<path d="M84,88 L88.5,70.5 L93,77 L87.5,94 Z" fill="#000" opacity=".18"/>'
    out += f'<path d="{WORM}" fill="url(#{face})"/>'
    return out + shade, defs


# ------------------------------------------------------------------- agent

# The Agent figure (half, x from its centre line at 50): a pointed hood with
# spurs where it meets the shoulders, the arms out to the elbows, a waist and
# a robe flaring to its foot.
AGENT_HALF = [(50, 1), (56, 2.6), (62, 7), (66, 12), (69, 16), (73.5, 17.2), (68.5, 21.6), (77, 24.5),
              (88, 38), (97, 53), (86, 60), (78, 64), (77.5, 72), (81.5, 82), (87, 92), (93.5, 100)]
AGENT_INNER = [(50, 6.5), (55, 8), (60.5, 12.5), (63.5, 18), (65, 21.5), (60.5, 24), (71, 28.5),
               (81, 41), (87.5, 52.5), (79.5, 57), (71.5, 61), (71, 72), (75, 83), (80, 95)]


def mirror(half: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """A symmetric outline from its right half (top to bottom)."""
    return half + [(100 - x, y) for x, y in reversed(half)][:-1]


def scaled(points, sx: float, sy: float, ox: float = 0, oy: float = 0) -> list[tuple[float, float]]:
    return [(ox + x * sx, oy + y * sy) for x, y in points]


def agent(rim: str, body: str, grain: str, *, sx: float, sy: float, ox: float = 0, oy: float = 0,
          outline: str = "#160808", line: str = "#1c0a0a", mark: str = "") -> tuple[str, str]:
    """The Agent figure scaled by (sx, sy): a dark outline, a pale rim, the
    body inside it with a wood grain. Returns (body, defs)."""
    outer = poly(scaled(mirror(AGENT_HALF), sx, sy, ox, oy))
    inner = poly(scaled(mirror(AGENT_INNER), sx, sy, ox, oy))
    rg, bg, clip = uid("ar"), uid("ab"), uid("ac")
    u = min(sx, sy)
    defs = (lin(rg, [(0, "#ffffff"), (0.08, rim), (1, rim)], 0.6, 1)
            + lin(bg, [(0, body), (1, body)])
            + f'<clipPath id="{clip}"><path d="{inner}"/></clipPath>')
    grain_lines = "".join(
        f'<path d="M{f(ox + (x0 - 40) * sx)},{f(oy + 104 * sy)} Q{f(ox + (x0 + 6) * sx)},{f(oy + 50 * sy)} {f(ox + (x0 + 58) * sx)},{f(oy - 4 * sy)}"/>'
        for x0 in range(-30, 110, 9))
    out = (f'<path d="{outer}" fill="url(#{rg})" stroke="{outline}" stroke-width="{f(2.4 * u)}" stroke-linejoin="round"/>'
           f'<path d="{inner}" fill="url(#{bg})" stroke="{line}" stroke-width="{f(1.5 * u)}" stroke-linejoin="round"/>'
           f'<g clip-path="url(#{clip})" fill="none" stroke="{grain}" stroke-width="{f(0.9 * u)}" opacity=".28">{grain_lines}</g>'
           + mark)
    return out, defs


# ------------------------------------------------------------- dreadnought

# The Dreadnought: a heavy hull seen from above at a slant; its deck and the
# front chain of edges whose side panels drop below it.
DREAD_TOP = [(5, 57), (8, 44), (14, 35), (34, 22), (42, 19), (47, 10), (51, 6), (67, 6), (71, 9), (72, 16),
             (76, 22), (85, 33), (91, 35), (95, 40), (95, 46), (82, 52), (68, 53), (40, 65), (25, 67), (11, 64)]
DREAD_FRONT = [(5, 57), (11, 64), (25, 67), (40, 65), (68, 53), (82, 52), (95, 46)]
DREAD_DROP = 25.0


def dreadnought(top: str, panels: list[str], *, outline: str = "#0a0a0a", sticker: str | None = None,
                sticker_w: float = 9.0, outline_w: float = 2.8, sticker_edge: str | None = None) -> str:
    """The hull in the 100 box; `panels` shades the side panels left to right."""
    sides = []
    for k, (a, b) in enumerate(zip(DREAD_FRONT, DREAD_FRONT[1:], strict=False)):
        sides.append((poly([a, b, (b[0], b[1] + DREAD_DROP), (a[0], a[1] + DREAD_DROP)]), panels[k % len(panels)]))
    deck = poly(DREAD_TOP)
    whole = [deck] + [d for d, _ in sides]
    out = ""
    if sticker_edge:
        out += "".join(f'<path d="{d}" fill="{sticker_edge}" stroke="{sticker_edge}" stroke-width="{f(sticker_w + 2.4)}" stroke-linejoin="round"/>' for d in whole)
    if sticker:
        out += "".join(f'<path d="{d}" fill="{sticker}" stroke="{sticker}" stroke-width="{f(sticker_w)}" stroke-linejoin="round"/>' for d in whole)
    out += "".join(f'<path d="{d}" fill="{outline}" stroke="{outline}" stroke-width="{f(outline_w)}" stroke-linejoin="round"/>' for d in whole)
    out += "".join(f'<path d="{d}" fill="{c}" stroke="{c}" stroke-width=".4" stroke-linejoin="round"/>' for d, c in sides)
    # Panel seams, then the deck.
    out += "".join(f'<path d="M{f(x)},{f(y + 0.6)} V{f(y + DREAD_DROP - 0.6)}" stroke="#000" stroke-width=".7" opacity=".35"/>'
                   for x, y in DREAD_FRONT[1:-1])
    out += f'<path d="{deck}" fill="{top}"/>'
    out += ('<path d="M8.5,50 L10,44 L15.5,37.5 L35,25 L43,22 L48,13 L52,9.5 L65.5,9.5" fill="none" stroke="#fff" '
            'stroke-width="1.4" opacity=".22" stroke-linejoin="round"/>')
    return out


# ---------------------------------------------------------------- worm body


def bezier(p0, p1, p2, p3, t: float) -> tuple[float, float]:
    u = 1 - t
    return (u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1])


def tube(curves: list[tuple], width, samples: int = 60) -> tuple[list, list, list]:
    """A body along joined cubic curves whose width follows width(t), t in
    0..1 over the whole length. Returns (outline points, centre points,
    normals)."""
    centre = []
    for k, c in enumerate(curves):
        for i in range(samples + (1 if k == len(curves) - 1 else 0)):
            centre.append(bezier(*c, i / samples))
    n = len(centre)
    left, right, normals = [], [], []
    for i, (x, y) in enumerate(centre):
        a = centre[max(i - 1, 0)]
        b = centre[min(i + 1, n - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(tx, ty) or 1
        nx, ny = -ty / ln, tx / ln
        w = width(i / (n - 1)) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
        normals.append((nx, ny))
    return left + list(reversed(right)), centre, normals


# ------------------------------------------------------------------ the Maker


def maker_worm(scale: float = 1.0, ox: float = 0, oy: float = 0, fill: str = "#f4f4f4",
               seam: str = "#5a5a5a", outline: str | None = None) -> str:
    """The Maker's worm in a 100 box: a ribbed body coiling from its thin
    tail at the top into a big head at the lower left, its maw open."""
    curves = [((63, 21), (52, 16), (38, 22), (40, 33)),
              ((40, 33), (42, 44), (66, 33), (72, 47)),
              ((72, 47), (78, 62), (62, 73), (50, 68))]
    outline_pts, centre, normals = tube(curves, lambda t: 6 + 30 * t ** 0.7, samples=40)
    pts = [(ox + x * scale, oy + y * scale) for x, y in outline_pts]
    body = poly(pts)
    out = ""
    if outline:
        out += f'<path d="{body}" fill="{outline}" stroke="{outline}" stroke-width="{f(3.2 * scale)}" stroke-linejoin="round"/>'
    out += f'<path d="{body}" fill="{fill}"/>'
    # The ribs: a curved seam across the body every few steps, wider apart towards the head.
    n = len(centre)
    marks = [int(n * t) for t in (0.1, 0.19, 0.29, 0.4, 0.52, 0.65, 0.78)]
    for i in marks:
        (x, y), (nx, ny) = centre[i], normals[i]
        w = (6 + 30 * (i / (n - 1)) ** 0.7) / 2 * 0.92
        bx, by = x - ny * w * 0.35, y + nx * w * 0.35
        out += (f'<path d="M{f(ox + (x + nx * w) * scale)},{f(oy + (y + ny * w) * scale)} '
                f'Q{f(ox + bx * scale)},{f(oy + by * scale)} {f(ox + (x - nx * w) * scale)},{f(oy + (y - ny * w) * scale)}" '
                f'fill="none" stroke="{seam}" stroke-width="{f(1.8 * scale)}" stroke-linecap="round"/>')
    # The head, its maw open to the left: a white rim of teeth round a dark mouth.
    hx, hy = 43, 68
    X = lambda x: f(ox + x * scale)  # noqa: E731
    Y = lambda y: f(oy + y * scale)  # noqa: E731
    if outline:
        out += f'<circle cx="{X(hx)}" cy="{Y(hy)}" r="{f(15.5 * scale)}" fill="{outline}"/>'
    out += f'<circle cx="{X(hx)}" cy="{Y(hy)}" r="{f(14 * scale)}" fill="{fill}"/>'
    mx, my = hx - 5, hy + 1
    out += (f'<ellipse cx="{X(mx)}" cy="{Y(my)}" rx="{f(7.5 * scale)}" ry="{f(10 * scale)}" fill="#2a2622" '
            f'transform="rotate(-18 {X(mx)} {Y(my)})"/>')
    teeth = ""
    for k in range(9):
        a = math.pi * (0.55 + k * 0.11)
        bx, by = mx + 8.5 * math.cos(a), my + 11 * math.sin(a)
        tx, ty = mx + 3.5 * math.cos(a + 0.05), my + 5 * math.sin(a + 0.05)
        sx_, sy_ = -math.sin(a) * 1.8, math.cos(a) * 1.8
        teeth += f'<path d="M{X(bx - sx_)},{Y(by - sy_)} L{X(tx)},{Y(ty)} L{X(bx + sx_)},{Y(by + sy_)} Z"/>'
    out += f'<g fill="{fill}">{teeth}</g>'
    out += f'<ellipse cx="{X(mx + 1)}" cy="{Y(my)}" rx="{f(3 * scale)}" ry="{f(4.5 * scale)}" fill="#0c0a08" transform="rotate(-18 {X(mx)} {Y(my)})"/>'
    # Ragged lips where the teeth stand out past the head.
    lips = "".join(f'<path d="M{X(mx + 9.5 * math.cos(a))},{Y(my + 12 * math.sin(a))} l{f(-2.6 * scale * math.cos(a + 0.4))},{f(-2.6 * scale * math.sin(a + 0.4))}" '
                   f'stroke="{fill}" stroke-width="{f(2.2 * scale)}" stroke-linecap="round"/>' for a in (math.pi * (0.6 + k * 0.16) for k in range(6)))
    return out + lips


def hexagon(cx: float, cy: float, r: float) -> list[tuple[float, float]]:
    """A hexagon with its points left and right."""
    return [(cx + r * math.cos(k * math.pi / 3), cy + r * math.sin(k * math.pi / 3)) for k in range(6)]


# ------------------------------------------------------------- Maker Hooks


def hook(x0: float, y0: float, x1: float, y1: float, s: float, metal: str = "#c4c8cc", edge: str = "#2a2e34") -> str:
    """A Maker hook: a pole from (x0, y0) with a grip, to (x1, y1) where it
    bends over into a curved hook."""
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy)
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    tip = (x1 + ux * 6 * s + nx * 22 * s, y1 + uy * 6 * s + ny * 22 * s)
    curl = f"M{f(x1)},{f(y1)} Q{f(x1 + ux * 16 * s)},{f(y1 + uy * 16 * s)} {f(tip[0])},{f(tip[1])}"
    grip = f"M{f(x0)},{f(y0)} L{f(x0 + ux * 14 * s)},{f(y0 + uy * 14 * s)}"
    pole = f"M{f(x0)},{f(y0)} L{f(x1)},{f(y1)}"
    return (f'<path d="{pole}" stroke="{edge}" stroke-width="{f(9 * s)}" stroke-linecap="round"/>'
            f'<path d="{curl}" fill="none" stroke="{edge}" stroke-width="{f(7.5 * s)}" stroke-linecap="round"/>'
            f'<path d="{grip}" stroke="{edge}" stroke-width="{f(13 * s)}" stroke-linecap="square"/>'
            f'<path d="{pole}" stroke="{metal}" stroke-width="{f(5 * s)}" stroke-linecap="round"/>'
            f'<path d="{curl}" fill="none" stroke="{metal}" stroke-width="{f(3.6 * s)}" stroke-linecap="round"/>'
            f'<path d="{grip}" stroke="#9aa0a8" stroke-width="{f(8.5 * s)}" stroke-linecap="square"/>')
