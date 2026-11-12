# ruff: noqa: E501  (SVG markup reads best one element to a line)
"""Round 5 drawings (user 2026-11-11 list): the question mark, the
battle icons and their bare marks, crossed blades for combat, the freighter,
the Shield Wall, Steal Intrigue and the Tech flip."""

from __future__ import annotations

from . import extras, shapes

f, poly, uid, lin = shapes.f, shapes.poly, shapes.uid, shapes.lin


def T(d: str, x0: float, y0: float, s: float) -> str:
    """A path in a 100 box, moved to (x0, y0) and scaled by s (numbers only)."""
    import re
    out, toggle = [], 0
    for token in re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", d):
        if token.isalpha():
            out.append(token)
            toggle = 0
            continue
        v = float(token)
        out.append(f(x0 + v * s) if toggle == 0 else f(y0 + v * s))
        toggle ^= 1
    return " ".join(out).replace(" ,", ",")


# ------------------------------------------------------------ question mark

QUESTION = ("M20,31 C20,12 35,3 52,3 C71,3 84,14 84,30 C84,43 76,50 65,56 C59,59 57,62 57,68 L57,72 "
            "L35,72 L35,64 C35,52 42,46 51,41 C58,37 61,35 61,30 C61,25 57,22 52,22 C46,22 43,26 43,33 Z")
QUESTION_DOT = "M35,79 L57,79 L57,98 L35,98 Z"


def question(cx: float, cy: float, h: float, fill: str = "", edge: str = "#2a1a00", glow: bool = True) -> tuple[str, str]:
    """A bold blocky question mark, h tall, centred on (cx, cy)."""
    g = uid("qm")
    defs = lin(g, [(0, "#fff0a0"), (0.45, "#f6c42a"), (1, "#c88a0c")])
    paint = fill or f"url(#{g})"
    s = h / 100
    x0, y0 = cx - 52 * s, cy - 50 * s
    body = T(QUESTION, x0, y0, s)
    dot = T(QUESTION_DOT, x0, y0, s)
    out = ""
    for d in (body, dot):
        out += f'<path d="{d}" fill="{edge}" stroke="{edge}" stroke-width="{f(9 * s)}" stroke-linejoin="round"/>'
    for d in (body, dot):
        out += f'<path d="{d}" fill="{paint}" stroke="{paint}" stroke-width="{f(1.5 * s)}" stroke-linejoin="round"/>'
    if glow:
        out += (f'<path d="{T("M27,30 C28,17 38,9 52,9", x0, y0, s)}" fill="none" stroke="#fff" stroke-width="{f(3.4 * s)}" '
                'stroke-linecap="round" opacity=".55"/>')
    return out, defs


# ------------------------------------------------------------------ battle

BATTLE_TILE = [(6, 5), (172, 5), (167, 95), (38, 95)]
BATTLE_COLORS = {
    "crysknife": ("#9ccd48", "#3c6e1a", "#e8f8a8", "#26440c"),
    "desert_mouse": ("#d4943a", "#6c3a10", "#f6dcaa", "#3e2006"),
    "ornithopter": ("#36aad6", "#0e4c6e", "#b4f2ff", "#0a3044"),
    "wild": ("#f0cc28", "#8c6a06", "#fff4b0", "#4a3800"),
}


def battle_symbol(kind: str, x0: float, y0: float, s: float, fill: str, edge: str) -> str:
    """The battle icon's mark in a 100 box at (x0, y0), scale s."""
    P = lambda x, y: f"{f(x0 + x * s)},{f(y0 + y * s)}"  # noqa: E731
    sw = f(2.6 * s)
    if kind == "crysknife":
        # A broad curved blade bellying out along its edge to a fine point,
        # a short guard and a wrapped grip.
        blade = (f"M{P(30, 76)} C{P(46, 60)} {P(62, 34)} {P(88, 8)} C{P(94, 36)} {P(78, 64)} {P(48, 77)} "
                 f"C{P(42, 80)} {P(36, 82)} {P(30, 76)} Z")
        guard = f"M{P(24, 70)} L{P(46, 84)} L{P(43, 89)} L{P(21, 75)} Z"
        grip = f"M{P(29, 81)} L{P(14, 95)} L{P(19, 100)} L{P(35, 86)} Z"
        return (f'<path d="{grip}" fill="{fill}" stroke="{edge}" stroke-width="{sw}" stroke-linejoin="round" opacity=".8"/>'
                f'<path d="{blade}" fill="{fill}" stroke="{edge}" stroke-width="{sw}" stroke-linejoin="round"/>'
                f'<path d="{guard}" fill="{fill}" stroke="{edge}" stroke-width="{sw}" stroke-linejoin="round"/>'
                f'<path d="M{P(38, 74)} C{P(54, 58)} {P(70, 36)} {P(86, 14)}" fill="none" stroke="{edge}" stroke-width="{f(1.4 * s)}" opacity=".4"/>'
                f'<path d="M{P(20, 92)} L{P(25, 87)} M{P(23, 95)} L{P(28, 90)}" stroke="{edge}" stroke-width="{f(1.2 * s)}" opacity=".6"/>')
    if kind == "desert_mouse":
        # A jerboa crouched mid-hop, facing right: a round body leaning
        # forward, long ears laid back, a big hind foot, a long tufted tail.
        parts = [
            f'<ellipse cx="{f(x0 + 50 * s)}" cy="{f(y0 + 62 * s)}" rx="{f(21 * s)}" ry="{f(15 * s)}" transform="rotate(-18 {f(x0 + 50 * s)} {f(y0 + 62 * s)})"/>',
            f'<ellipse cx="{f(x0 + 70 * s)}" cy="{f(y0 + 47 * s)}" rx="{f(12 * s)}" ry="{f(10 * s)}" transform="rotate(-10 {f(x0 + 70 * s)} {f(y0 + 47 * s)})"/>',
            f'<path d="M{P(78, 44)} L{P(88, 49)} L{P(78, 54)} Z"/>',
            f'<ellipse cx="{f(x0 + 58 * s)}" cy="{f(y0 + 28 * s)}" rx="{f(4.6 * s)}" ry="{f(14 * s)}" transform="rotate(-38 {f(x0 + 58 * s)} {f(y0 + 28 * s)})"/>',
            f'<ellipse cx="{f(x0 + 66 * s)}" cy="{f(y0 + 26 * s)}" rx="{f(4.6 * s)}" ry="{f(14 * s)}" transform="rotate(-18 {f(x0 + 66 * s)} {f(y0 + 26 * s)})"/>',
            f'<path d="M{P(40, 66)} C{P(34, 74)} {P(30, 80)} {P(28, 86)} L{P(54, 88)} L{P(54, 84)} L{P(40, 82)} C{P(44, 78)} {P(48, 74)} {P(50, 70)} Z"/>',
            f'<path d="M{P(66, 58)} L{P(72, 70)} L{P(76, 69)} L{P(71, 57)} Z"/>',
        ]
        tail = f"M{P(32, 64)} C{P(18, 66)} {P(10, 74)} {P(8, 86)}"
        tuft = f'<ellipse cx="{f(x0 + 8 * s)}" cy="{f(y0 + 88 * s)}" rx="{f(4 * s)}" ry="{f(6 * s)}"/>'
        shapes_ = "".join(parts) + tuft
        return (f'<path d="{tail}" fill="none" stroke="{edge}" stroke-width="{f(5.5 * s)}" stroke-linecap="round"/>'
                f'<g fill="{edge}" stroke="{edge}" stroke-width="{f(5 * s)}" stroke-linejoin="round">{shapes_}</g>'
                f'<path d="{tail}" fill="none" stroke="{fill}" stroke-width="{f(2.6 * s)}" stroke-linecap="round"/>'
                f'<g fill="{fill}">{shapes_}</g>'
                f'<circle cx="{f(x0 + 73 * s)}" cy="{f(y0 + 44 * s)}" r="{f(2.2 * s)}" fill="{edge}"/>'
                f'<path d="M{P(62, 38)} C{P(66, 42)} {P(64, 50)} {P(58, 54)}" fill="none" stroke="{edge}" stroke-width="{f(1.2 * s)}" opacity=".5"/>')
    if kind == "ornithopter":
        from . import extras3
        return extras3.ornithopter(x0, y0, s, fill, edge)
    if kind == "wild":
        q, _ = question(x0 + 50 * s, y0 + 52 * s, 86 * s, fill=fill, edge=edge, glow=False)
        return q
    raise KeyError(kind)


def battle_tile(kind: str) -> tuple[str, str]:
    """A battle icon: its colour's slanted tile, contour lines, its mark."""
    top, bottom, mark, edge = BATTLE_COLORS[kind]
    g, clip = uid("bt"), uid("bc")
    defs = lin(g, [(0, top), (1, bottom)], 0.6, 1) + f'<clipPath id="{clip}"><path d="{poly(BATTLE_TILE)}"/></clipPath>'
    lines = "".join(
        f'<ellipse cx="{f(120 + k * 3)}" cy="{f(78 - k * 2)}" rx="{f(16 + k * 13)}" ry="{f(9 + k * 7)}" fill="none"/>' for k in range(9))
    out = (f'<path d="{poly(BATTLE_TILE)}" fill="#141414" stroke="#141414" stroke-width="7" stroke-linejoin="round"/>'
           f'<path d="{poly(BATTLE_TILE)}" fill="url(#{g})" stroke="url(#{g})" stroke-width="2" stroke-linejoin="round"/>'
           f'<g clip-path="url(#{clip})" stroke="#fff" stroke-width="1.2" opacity=".14">{lines}</g>'
           f'<path d="M9,7 L170,7" stroke="#fff" stroke-width="1.6" opacity=".35"/>'
           + battle_symbol(kind, 58, 6, 0.88, mark, edge))
    return out, defs


def battle_mark(kind: str) -> str:
    """The battle mark alone (a Conflict card's corner), white, in a 100 box."""
    return battle_symbol(kind, 0, 0, 1, "#ffffff", "#1a1a1a")


# ----------------------------------------------------------- crossed blades


def crossed_blades(fill: str, edge: str, *, shade: str = "") -> str:
    """Two swords crossed in an X, in a 100 box: long blades narrowing to
    their points, a short guard, a grip and pommel each."""
    out_edge, out_fill = "", ""
    for side in (-1, 1):
        rot = ' transform="translate(100 0) scale(-1 1)"' if side > 0 else ""
        blade = "M18,10 L26,8 L84,76 L78,82 Z"
        guard = "M70,64 L86,80 L82,84 L66,68 Z"
        grip = "M80,78 L92,90 L88,94 L76,82 Z"
        pommel = "M90,90 m-5,0 a5,5 0 1,0 10,0 a5,5 0 1,0 -10,0"
        for d in (blade, guard, grip, pommel):
            out_edge += f'<path d="{d}"{rot} fill="{edge}" stroke="{edge}" stroke-width="5" stroke-linejoin="round"/>'
        out_fill += (f'<path d="{blade}"{rot} fill="{fill}"/>'
                     f'<path d="M22,10 L81,79"{rot} stroke="{shade or edge}" stroke-width="1.4" opacity=".35"/>'
                     f'<path d="{guard}"{rot} fill="{fill}"/><path d="{grip}"{rot} fill="{shade or fill}"/><path d="{pommel}"{rot} fill="{fill}"/>')
    return out_edge + out_fill


# --------------------------------------------------------------- freighter


def freighter() -> tuple[str, str]:
    """The freighter: a ribbed slate shield with chevrons round its rim and a
    heavy bevelled pylon down its middle (viewBox 83 x 100)."""
    g, rim, face = uid("fs"), uid("fr"), uid("ff")
    defs = (lin(g, [(0, "#6a8a86"), (1, "#24363a")]) + lin(rim, [(0, "#b8ccc8"), (1, "#4a625e")], 0.3, 1)
            + lin(face, [(0, "#e8f2f0"), (1, "#9ab4ae")]))
    shield = "M6,6 L77,6 L77,52 C77,74 60,88 41.5,96 C23,88 6,74 6,52 Z"
    inner = "M13,13 L70,13 L70,51 C70,69 56,81 41.5,88 C27,81 13,69 13,51 Z"
    chevrons = "".join(f'<path d="M15,{f(22 + k * 9)} L41.5,{f(34 + k * 9)} L68,{f(22 + k * 9)}" fill="none"/>' for k in range(5))
    pylon_l = "M18,22 L41.5,22 L41.5,80 L36,64 L35,34 L22,32 Z"
    pylon_r = "M41.5,22 L65,22 L61,32 L48,34 L47,64 L41.5,80 Z"
    out = (f'<path d="{shield}" fill="#141c1c" stroke="#141c1c" stroke-width="6" stroke-linejoin="round"/>'
           f'<path d="{shield}" fill="url(#{rim})"/>'
           f'<path d="{inner}" fill="url(#{g})" stroke="#141c1c" stroke-width="1.6" stroke-linejoin="round"/>'
           f'<g stroke="#a8c4be" stroke-width="2.2" opacity=".35" stroke-linejoin="round">{chevrons}</g>'
           f'<path d="M18,22 L65,22 L61,32 L48,34 L47,64 L41.5,80 L36,64 L35,34 L22,32 Z" fill="#141c1c" stroke="#141c1c" stroke-width="5" stroke-linejoin="round"/>'
           f'<path d="{pylon_l}" fill="url(#{face})"/><path d="{pylon_r}" fill="#7e9a94"/>'
           '<path d="M20,23.5 L63,23.5" stroke="#fff" stroke-width="1.4" opacity=".7"/>')
    return out, defs


# ------------------------------------------------------------- Shield Wall


def shield_wall() -> tuple[str, str]:
    """The Shield Wall broken: a red step down, and over it a stone wall
    split by a jagged crack, its right end falling away with rubble (viewBox
    88 x 100)."""
    red, stone, side = uid("sr"), uid("ss"), uid("sd")
    defs = (lin(red, [(0, "#ff4a40"), (1, "#a80a14")], 0.4, 1) + lin(stone, [(0, "#ffe2a8"), (1, "#d09848")], 0.3, 1)
            + lin(side, [(0, "#b47a32"), (1, "#7a4a16")]))
    v = "M2,26 L86,22 L56,99 Z"
    left_top = "M6,10 L40,4 L48,12 L44,20 L50,24 L45,30 L14,34 Z"
    left_side = "M14,34 L45,30 L50,24 L52,36 L46,44 L18,48 L6,24 L6,10 Z"
    right = "M56,30 L70,24 L80,30 L70,92 L58,96 L54,84 L60,74 L52,64 L58,54 L52,44 Z"
    right_side = "M70,24 L80,30 L70,92 L66,90 L74,32 Z"
    bricks = ("M8,22 L46,17 M10,30 L44,26 M24,6 L26,32 M38,5 L40,30 M17,34 L20,47 M32,32 L34,46 "
              "M56,44 L76,40 M56,56 L74,52 M58,70 L72,66 M58,82 L70,79 M64,28 L62,93")
    out = (f'<path d="{v}" fill="url(#{red})" stroke="#3a0408" stroke-width="2.6" stroke-linejoin="round"/>'
           '<path d="M10,29 L77,26 L56,88" fill="none" stroke="#ff9a90" stroke-width="1.4" opacity=".5" stroke-linejoin="round"/>'
           f'<path d="{left_side}" fill="url(#{side})" stroke="#2a1806" stroke-width="2.2" stroke-linejoin="round"/>'
           f'<path d="{left_top}" fill="url(#{stone})" stroke="#2a1806" stroke-width="2.2" stroke-linejoin="round"/>'
           f'<path d="{right}" fill="url(#{stone})" stroke="#2a1806" stroke-width="2.2" stroke-linejoin="round"/>'
           f'<path d="{right_side}" fill="url(#{side})" stroke="#2a1806" stroke-width="1.4" stroke-linejoin="round"/>'
           f'<path d="{bricks}" fill="none" stroke="#9a6a2a" stroke-width="1.2" opacity=".7"/>'
           # The crack's rubble.
           + "".join(f'<path d="M{f(x)},{f(y)} l{f(r)},{f(-r * 0.6)} l{f(r * 0.5)},{f(r * 0.9)} l{f(-r)},{f(r * 0.4)} Z" fill="url(#{stone})" stroke="#2a1806" stroke-width="1"/>'
                     for x, y, r in ((50, 50, 4), (47, 58, 3), (52, 70, 3.4), (48, 78, 2.6))))
    return out, defs


# ---------------------------------------------------------- Steal Intrigue


def steal_intrigue() -> tuple[str, str]:
    """Steal Intrigue: an opponent's dark hand of cards fanned behind, an
    Intrigue card drawn out of it (viewBox 110 x 100)."""
    back = uid("hb")
    defs = lin(back, [(0, "#3a3a3a"), (1, "#0e0e0e")], 1, 1)
    out = ""
    for rot, x in ((-24, 22), (-10, 34)):
        out += (f'<g transform="rotate({rot} {x + 20} 86)"><rect x="{x}" y="18" width="40" height="64" rx="5" fill="#0a0a0a"/>'
                f'<rect x="{x + 2}" y="20" width="36" height="60" rx="4" fill="url(#{back})" stroke="#6a6a6a" stroke-width="1.2"/></g>')
    card, cdefs = extras.intrigue_card(48, 6, 44, 70)
    out += f'<g transform="rotate(14 70 76)">{card}</g>'
    return out, defs + cdefs


# -------------------------------------------------------------- Tech flip


def tech_flip() -> tuple[str, str]:
    """Flip a Tech tile: a gold-rimmed tile tipping over, a white arrow
    curling round its edge (viewBox 100 x 80)."""
    face = uid("tf")
    defs = lin(face, [(0, "#2a2a1a"), (0.55, "#3a3a20"), (1, "#c8a238")], 1, 0.4)
    tile = "M34,8 L92,10 L90,48 L32,46 Z"
    out = (f'<path d="{tile}" fill="#0e0e0a" stroke="#0e0e0a" stroke-width="5" stroke-linejoin="round"/>'
           f'<path d="{tile}" fill="url(#{face})" stroke="#e8c050" stroke-width="2.6" stroke-linejoin="round"/>'
           '<path d="M40,14 L86,15.5" stroke="#fff6c0" stroke-width="1.2" opacity=".5"/>')
    arrow = "M34,24 C14,24 8,40 14,52 C20,64 38,66 48,60"
    out += (f'<path d="{arrow}" fill="none" stroke="#141414" stroke-width="11" stroke-linecap="round"/>'
            f'<path d="{arrow}" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round"/>'
            '<path d="M44,50 L60,58 L46,72 Z" fill="#fff" stroke="#141414" stroke-width="2.4" stroke-linejoin="round"/>')
    return out, defs
