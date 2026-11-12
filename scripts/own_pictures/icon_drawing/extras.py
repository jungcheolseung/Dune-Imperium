# ruff: noqa: E501  (SVG markup reads best one element to a line)
"""The Intrigue mark, victory point, signet ring and research
microscope, drawn in our own lines (round 3, user 2026-11-11)."""

from __future__ import annotations

import math

from . import shapes

f, poly, uid, lin = shapes.f, shapes.poly, shapes.uid, shapes.lin


def rad(gid: str, stops: list[tuple[float, str]], cx: float = 0.4, cy: float = 0.35, r: float = 0.75) -> str:
    body = "".join(f'<stop offset="{f(o)}" stop-color="{c}"/>' for o, c in stops)
    return f'<radialGradient id="{gid}" cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}">{body}</radialGradient>'


def intrigue_glyph(cx: float, cy: float, r: float, *, fill: str | None = None, edge: str = "#3a2606") -> tuple[str, str]:
    """The Intrigue mark: a round eye held between two brush-stroke hooks,
    each running out into a long thin point, one up, one down (turned half
    round on each other). Unit r = half its height."""
    g = uid("ig")
    defs = lin(g, [(0, "#ffe7a0"), (0.5, "#f2b93a"), (1, "#c8861a")], 0.4, 1)
    paint = fill or f"url(#{g})"
    curves = [((-0.17, -0.98), (-0.19, -0.66), (-0.2, -0.44), (-0.3, -0.27)),
              ((-0.3, -0.27), (-0.46, -0.12), (-0.74, 0.1), (-0.52, 0.31)),
              ((-0.52, 0.31), (-0.36, 0.45), (-0.08, 0.47), (0.22, 0.4))]

    def width(t: float) -> float:
        return 0.012 + 0.22 * math.sin(math.pi * min(1.0, t * 1.05)) ** 1.4

    outline, _, _ = shapes.tube(curves, width, samples=30)
    one = [(cx + x * r, cy + y * r) for x, y in outline]
    two = [(cx - x * r, cy - y * r) for x, y in outline]
    out = ""
    for pts in (one, two):
        out += f'<path d="{poly(pts)}" fill="{edge}" stroke="{edge}" stroke-width="{f(r * 0.07)}" stroke-linejoin="round"/>'
    out += f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * 0.21)}" fill="{edge}"/>'
    for pts in (one, two):
        out += f'<path d="{poly(pts)}" fill="{paint}"/>'
    out += f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * 0.18)}" fill="{paint}"/>'
    return out, defs


def intrigue_card(x: float, y: float, w: float, h: float, *, mark: bool = True) -> tuple[str, str]:
    """An Intrigue card: a pale silver rim round a dark olive face with fine
    gold diagonal hatching, the Intrigue mark in the middle."""
    face, rim, hatch = uid("if"), uid("ir"), uid("ih")
    step = w * 0.11
    defs = (lin(face, [(0, "#3e3820"), (1, "#14120a")], 1, 1) + lin(rim, [(0, "#ffffff"), (1, "#a8a8a8")], 1, 1)
            + f'<pattern id="{hatch}" width="{f(step)}" height="{f(step)}" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">'
            f'<path d="M0,0 V{f(step)}" stroke="#d8b860" stroke-width="{f(w * 0.012)}" opacity=".22"/></pattern>')
    inner = f'x="{f(x + w * 0.14)}" y="{f(y + h * 0.09)}" width="{f(w * 0.72)}" height="{f(h * 0.82)}" rx="{f(w * 0.05)}"'
    out = (f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{f(w * 0.12)}" fill="#161616"/>'
           f'<rect x="{f(x + w * 0.05)}" y="{f(y + h * 0.035)}" width="{f(w * 0.9)}" height="{f(h * 0.93)}" rx="{f(w * 0.09)}" fill="url(#{rim})"/>'
           f'<rect {inner} fill="url(#{face})"/><rect {inner} fill="url(#{hatch})"/>')
    if mark:
        g, gdefs = intrigue_glyph(x + w / 2, y + h / 2, h * 0.3)
        out += g
        defs += gdefs
    return out, defs


def victory_point(cx: float, cy: float, r: float) -> tuple[str, str]:
    """A victory point: a golden world under a white starburst, its two moons
    beside it. Unit r = the world's radius."""
    world, moon, shine = uid("vw"), uid("vm"), uid("vs")
    defs = (rad(world, [(0, "#fff8c8"), (0.35, "#ffd24a"), (0.8, "#e08a10"), (1, "#9a5206")], 0.36, 0.3, 0.8)
            + rad(moon, [(0, "#fff6c0"), (0.6, "#f2b42a"), (1, "#a86206")], 0.35, 0.3, 0.8)
            + rad(shine, [(0, "#ffffff"), (1, "#ffffff00")], 0.5, 0.5, 0.5))
    star = []
    for k in range(24):
        a = -math.pi / 2 + k * math.pi / 12
        rr = r * (1.42 if k % 2 == 0 else 1.18) * (1.0 if k % 4 else 1.08)
        star.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    out = (f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * 1.5)}" fill="url(#{shine})" opacity=".35"/>'
           f'<path d="{poly(star)}" fill="none" stroke="#fff" stroke-width="{f(r * 0.05)}" stroke-linejoin="round" opacity=".9"/>'
           f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r)}" fill="url(#{world})" stroke="#7a3e04" stroke-width="{f(r * 0.06)}"/>')
    # The world's lines of longitude and latitude, bowed as on a globe.
    lines = ""
    for k in (-0.62, -0.25, 0.25, 0.62):
        lines += f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(abs(k) * r)}" ry="{f(r)}" fill="none"/>'
    for k in (-0.55, 0, 0.55):
        y = cy + k * r
        half = math.sqrt(max(0.0, 1 - k * k)) * r
        lines += f'<path d="M{f(cx - half)},{f(y)} Q{f(cx)},{f(y + r * 0.16)} {f(cx + half)},{f(y)}" fill="none"/>'
    out += f'<g stroke="#a8600a" stroke-width="{f(r * 0.045)}" opacity=".75">{lines}</g>'
    out += (f'<path d="M{f(cx - r * 0.62)},{f(cy - r * 0.42)} A{f(r * 0.8)},{f(r * 0.8)} 0 0 1 {f(cx - r * 0.05)},{f(cy - r * 0.82)}" '
            f'fill="none" stroke="#fff" stroke-width="{f(r * 0.1)}" stroke-linecap="round" opacity=".55"/>')
    for mx, my, mr in ((cx - r * 0.98, cy - r * 0.86, r * 0.26), (cx + r * 0.86, cy + r * 0.78, r * 0.36)):
        out += (f'<circle cx="{f(mx)}" cy="{f(my)}" r="{f(mr)}" fill="url(#{moon})" stroke="#7a3e04" stroke-width="{f(r * 0.05)}"/>'
                f'<circle cx="{f(mx - mr * 0.3)}" cy="{f(my - mr * 0.32)}" r="{f(mr * 0.28)}" fill="#fff" opacity=".6"/>')
    return out, defs


def signet_ring(cx: float, cy: float, r: float) -> tuple[str, str]:
    """A signet ring seen from above at a slant: the gold band, the dark
    hole through it, and the flat oval seal on top with its engraved mark.
    Unit r = half the band's width."""
    band, inner, seal, cut = uid("sb"), uid("si"), uid("ss"), uid("sc")
    defs = (lin(band, [(0, "#ffe9a0"), (0.45, "#e8a628"), (1, "#8a5208")], 0.2, 1)
            + lin(inner, [(0, "#5a3608"), (1, "#c88a26")])
            + lin(seal, [(0, "#fff2c0"), (0.5, "#f0bc40"), (1, "#a86a10")], 0.3, 1)
            + lin(cut, [(0, "#6a3e06"), (1, "#3a2204")]))
    bx, by = cx, cy + r * 0.18
    rx, ry = r, r * 0.62
    out = (f'<ellipse cx="{f(bx)}" cy="{f(by)}" rx="{f(rx)}" ry="{f(ry)}" fill="url(#{band})" stroke="#4a2c04" stroke-width="{f(r * 0.05)}"/>'
           # The hole, and the band's inner wall seen through it.
           f'<ellipse cx="{f(bx)}" cy="{f(by + r * 0.05)}" rx="{f(rx * 0.7)}" ry="{f(ry * 0.6)}" fill="url(#{inner})" stroke="#4a2c04" stroke-width="{f(r * 0.04)}"/>'
           f'<ellipse cx="{f(bx)}" cy="{f(by + r * 0.13)}" rx="{f(rx * 0.62)}" ry="{f(ry * 0.47)}" fill="#1a1006"/>'
           f'<path d="M{f(bx - rx * 0.8)},{f(by + ry * 0.3)} A{f(rx * 0.85)},{f(ry * 0.8)} 0 0 0 {f(bx + rx * 0.5)},{f(by + ry * 0.72)}" '
           f'fill="none" stroke="#fff6d0" stroke-width="{f(r * 0.06)}" stroke-linecap="round" opacity=".6"/>')
    # The seal: a raised oval on the band's top, its rim and its mark.
    sx, sy, srx, sry = cx, cy - r * 0.42, r * 0.5, r * 0.28
    out += (f'<ellipse cx="{f(sx)}" cy="{f(sy + r * 0.1)}" rx="{f(srx * 1.06)}" ry="{f(sry * 1.08)}" fill="#6a4006" stroke="#4a2c04" stroke-width="{f(r * 0.04)}"/>'
            f'<ellipse cx="{f(sx)}" cy="{f(sy)}" rx="{f(srx)}" ry="{f(sry)}" fill="url(#{seal})" stroke="#4a2c04" stroke-width="{f(r * 0.04)}"/>'
            f'<ellipse cx="{f(sx)}" cy="{f(sy)}" rx="{f(srx * 0.72)}" ry="{f(sry * 0.66)}" fill="url(#{cut})"/>'
            # The engraved crest: a four-pointed star in a ring of our own.
            f'<path d="M{f(sx)},{f(sy - sry * 0.5)} L{f(sx + srx * 0.1)},{f(sy - sry * 0.08)} L{f(sx + srx * 0.42)},{f(sy)} '
            f'L{f(sx + srx * 0.1)},{f(sy + sry * 0.08)} L{f(sx)},{f(sy + sry * 0.5)} L{f(sx - srx * 0.1)},{f(sy + sry * 0.08)} '
            f'L{f(sx - srx * 0.42)},{f(sy)} L{f(sx - srx * 0.1)},{f(sy - sry * 0.08)} Z" fill="#f6cf6a"/>')
    return out, defs


def microscope(x0: float, y0: float, s: float) -> tuple[str, str]:
    """Research: a pale microscope standing on a dark slab. (x0, y0) is the
    top-left of a 100 box, s its scale."""
    slab, metal = uid("ms"), uid("mm")
    defs = lin(slab, [(0, "#6a6a72"), (1, "#2e2e34")]) + lin(metal, [(0, "#ffffff"), (1, "#c8bcd4")], 1, 1)

    def P(x: float, y: float) -> str:
        return f"{f(x0 + x * s)},{f(y0 + y * s)}"

    edge = "#1e1a24"
    out = (f'<path d="M{P(4, 78)} L{P(96, 78)} L{P(86, 96)} L{P(14, 96)} Z" fill="url(#{slab})" stroke="{edge}" stroke-width="{f(2.4 * s)}" stroke-linejoin="round"/>'
           f'<path d="M{P(12, 80)} L{P(88, 80)}" stroke="#a8a8b4" stroke-width="{f(1.6 * s)}" opacity=".6"/>')
    parts = [
        # The foot.
        f'<path d="M{P(26, 76)} L{P(30, 66)} L{P(66, 66)} L{P(72, 76)} Z"/>',
        # The arm, curving up behind the tube.
        f'<path d="M{P(56, 66)} C{P(70, 60)} {P(74, 40)} {P(64, 26)} L{P(56, 30)} C{P(62, 42)} {P(60, 54)} {P(48, 60)} Z"/>',
        # The stage.
        f'<path d="M{P(30, 52)} L{P(58, 52)} L{P(58, 57)} L{P(30, 57)} Z"/>',
    ]
    tube = f'<g transform="rotate(-28 {P(46, 34).replace(",", " ")})">' \
           f'<rect x="{f(x0 + 40 * s)}" y="{f(y0 + 10 * s)}" width="{f(12 * s)}" height="{f(36 * s)}" rx="{f(2 * s)}"/>' \
           f'<rect x="{f(x0 + 38 * s)}" y="{f(y0 + 6 * s)}" width="{f(16 * s)}" height="{f(7 * s)}" rx="{f(2 * s)}"/>' \
           f'<rect x="{f(x0 + 42.5 * s)}" y="{f(y0 + 44 * s)}" width="{f(7 * s)}" height="{f(8 * s)}" rx="{f(1.5 * s)}"/></g>'
    shapes_ = "".join(parts) + tube
    out += f'<g fill="url(#{metal})" stroke="{edge}" stroke-width="{f(2.2 * s)}" stroke-linejoin="round">{shapes_}</g>'
    return out, defs


def sword(x0: float, y0: float, w: float, h: float) -> tuple[str, str]:
    """The sword: a broad red blade, its spine curving to a cut-off point at
    the top right, a stepped guard and a ridged grip at the lower left, over
    a dark square stood on its corner. Laid out in a w x h box at (x0, y0)."""
    blade, back = uid("sb"), uid("sq")
    defs = (lin(blade, [(0, "#ff6a5a"), (0.45, "#f0222a"), (1, "#b00a14")], 1, 0.3)
            + lin(back, [(0, "#3a0408"), (1, "#160204")], 0.3, 1))

    def P(x: float, y: float) -> str:
        return f"{f(x0 + x / 100 * w)},{f(y0 + y / 100 * h)}"

    u = min(w, h) / 100
    square = f"M{P(50, 29)} L{P(89, 55)} L{P(51, 83)} L{P(12, 56)} Z"
    outline = (f"M{P(84, 4)} L{P(95, 27)} C{P(88, 35)} {P(76, 43)} {P(66, 49)} L{P(60, 57)} L{P(52, 59)} "
               f"L{P(48, 65)} L{P(40, 68)} L{P(31, 76)} L{P(26, 85)} L{P(15, 97)} L{P(5, 91)} L{P(12, 80)} "
               f"L{P(20, 72)} L{P(25, 63)} L{P(33, 59)} L{P(37, 55)} C{P(50, 42)} {P(66, 24)} {P(84, 4)} Z")
    grip = "".join(f'<path d="M{P(14 + k * 4.2, 85 - k * 5.4)} L{P(19 + k * 4.2, 89 - k * 5.4)}"/>' for k in range(4))
    shine = (f"M{P(81, 10)} C{P(66, 26)} {P(52, 40)} {P(41, 53)} M{P(88, 25)} C{P(76, 36)} {P(64, 44)} {P(56, 51)}")
    out = (f'<path d="{square}" fill="#0a0a0a" stroke="#0a0a0a" stroke-width="{f(9 * u)}" stroke-linejoin="round"/>'
           f'<path d="{square}" fill="url(#{back})" stroke="#f01c22" stroke-width="{f(4.2 * u)}" stroke-linejoin="round"/>'
           f'<path d="{outline}" fill="#0a0a0a" stroke="#0a0a0a" stroke-width="{f(7 * u)}" stroke-linejoin="round"/>'
           f'<path d="{outline}" fill="url(#{blade})"/>'
           f'<path d="{shine}" fill="none" stroke="#ffb0a8" stroke-width="{f(1.6 * u)}" stroke-linecap="round" opacity=".55"/>'
           f'<path d="M{P(47, 52)} C{P(58, 43)} {P(70, 33)} {P(84, 18)}" fill="none" stroke="#7a0408" stroke-width="{f(1.4 * u)}" opacity=".6"/>'
           f'<g stroke="#5a0206" stroke-width="{f(2 * u)}" stroke-linecap="round">{grip}</g>')
    return out, defs


def faction_badge(faction: str) -> tuple[str, str]:
    """A Faction's mark on the small dark rounded square card text prints it
    on (Influence and Alliance conditions), in a 100 box."""
    from . import marks
    plate, rim = uid("fb"), uid("fr")
    defs = lin(plate, [(0, "#3e3e3e"), (1, "#121212")]) + lin(rim, [(0, "#e2e2e2"), (1, "#8a8a8a")], 0.3, 1)
    mark = {
        "emperor": marks.emperor(50, 41, 26.5),
        "spacing_guild": marks.guild(50, 50, 38),
        "bene_gesserit": marks.bene_gesserit(50, 50, 37),
        "fremen": marks.fremen(50, 50, 34),
    }[faction]
    out = (f'<rect x="4" y="4" width="92" height="92" rx="20" fill="url(#{plate})" stroke="url(#{rim})" stroke-width="5"/>'
           '<rect x="9.5" y="9.5" width="81" height="81" rx="15" fill="none" stroke="#000" stroke-width="2" opacity=".6"/>'
           + mark)
    return out, defs
