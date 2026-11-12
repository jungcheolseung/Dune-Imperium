# ruff: noqa: E501  (SVG markup reads best one element to a line)
"""The fourth pass's simpler drawings (user 2026-11-11, 21 items).

Ornithopter (a dragonfly-winged craft), the research microscope, the signet
ring, the Tech gear, the Control banner's arches and Unload's two cards.
Each is our own construction of a few plain shapes; print is only the feel.
"""
import math

from .extras import lin, uid


def f(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def ornithopter(x0: float, y0: float, s: float, fill: str, edge: str) -> str:
    """Seen from above, nose to the upper right: a craft, not an insect. A
    stout cabin with its canopy, a long tail boom with a small tailplane,
    and two pairs of long straight wings (front pair swept forward, rear
    pair back), each a slender blade with a squared, rounded tip. Drawn
    along its own axis, then turned."""
    tail_x, tail_y = 14, 86
    angle = math.degrees(math.atan2(24 - tail_y, 90 - tail_x))
    sw = 2.4

    def wing(u: float, side: int, sweep: float, span: float, root: float, tip: float) -> str:
        a = math.radians(side * (90 - sweep))
        ux, vy = math.cos(a), math.sin(a)          # along the wing
        px, py = -vy, ux                            # across it
        x1, y1 = u + ux * 5, vy * 5
        x2, y2 = u + ux * span, vy * span
        pts = [(x1 + px * root, y1 + py * root), (x2 + px * tip, y2 + py * tip),
               (x2 - px * tip, y2 - py * tip), (x1 - px * root, y1 - py * root)]
        (ax, ay), (bx, by), (cx, cy), (dx, dy) = pts
        ex, ey = x2 + ux * tip * 1.3, y2 + vy * tip * 1.3
        return (f'<path d="M{f(ax)},{f(ay)} L{f(bx)},{f(by)} Q{f(ex)},{f(ey)} {f(cx)},{f(cy)} L{f(dx)},{f(dy)} Z"/>',
                f'<path d="M{f(x1)},{f(y1)} L{f(x2)},{f(y2)}"/>')

    wings, veins = "", ""
    for u, sweep, span, root, tip in ((60, 6, 46, 6.6, 4.8), (46, -24, 42, 6.2, 4.4)):
        for side in (-1, 1):
            w_, v_ = wing(u, side, sweep, span, root, tip)
            wings += w_
            veins += v_
    body = ("M0,-2.4 L44,-3.6 C52,-4 56,-8.8 66,-9.6 C80,-10.4 92,-6 94,0 "
            "C92,6 80,10.4 66,9.6 C56,8.8 52,4 44,3.6 L0,2.4 Z")
    tailplane = "M4,0 L-2,-11 L6,-11 L12,0 L6,11 L-2,11 Z"
    canopy = '<path d="M72,-6.4 C82,-6.6 89,-3.4 90,0 C89,3.4 82,6.6 72,6.4 C69,3 69,-3 72,-6.4 Z"'
    return (f'<g transform="translate({f(x0 + tail_x * s)} {f(y0 + tail_y * s)}) rotate({f(angle)}) scale({f(s * 0.97)})">'
            f'<g fill="{fill}" stroke="{edge}" stroke-width="{sw}" stroke-linejoin="round">{wings}</g>'
            f'<g stroke="{edge}" stroke-width="1.1" opacity=".4">{veins}</g>'
            f'<path d="{tailplane}" fill="{fill}" stroke="{edge}" stroke-width="{sw}" stroke-linejoin="round"/>'
            f'<path d="{body}" fill="{fill}" stroke="{edge}" stroke-width="{sw}" stroke-linejoin="round"/>'
            f'{canopy} fill="{edge}" opacity=".6"/>'
            f'<path d="M50,0 H66" stroke="{edge}" stroke-width="1.2" opacity=".35"/>'
            "</g>")


def microscope(x0: float, y0: float, s: float) -> tuple[str, str]:
    """Research: a chunky pale microscope on a dark slab, four plain blocks
    (foot, arm, stage, head), as the log's small tile needs."""
    slab, metal = uid("ms"), uid("mm")
    defs = lin(slab, [(0, "#5e5e66"), (1, "#26262c")]) + lin(metal, [(0, "#ffffff"), (1, "#cdbfe0")], 1, 1)

    def P(x: float, y: float) -> str:
        return f"{f(x0 + x * s)},{f(y0 + y * s)}"

    edge = "#1c1822"
    out = f'<path d="M{P(2, 74)} L{P(98, 74)} L{P(88, 96)} L{P(12, 96)} Z" fill="url(#{slab})" stroke="{edge}" stroke-width="{f(2.4 * s)}" stroke-linejoin="round"/>'
    parts = [
        f'<path d="M{P(20, 80)} L{P(27, 64)} L{P(73, 64)} L{P(80, 80)} Z"/>',
        f'<path d="M{P(50, 66)} C{P(74, 62)} {P(80, 34)} {P(66, 16)} L{P(52, 24)} C{P(62, 36)} {P(60, 50)} {P(42, 56)} Z"/>',
        f'<rect x="{f(x0 + 20 * s)}" y="{f(y0 + 49 * s)}" width="{f(38 * s)}" height="{f(9 * s)}" rx="{f(2 * s)}"/>',
        f'<rect x="{f(x0 + 30 * s)}" y="{f(y0 + 4 * s)}" width="{f(20 * s)}" height="{f(40 * s)}" rx="{f(4 * s)}" '
        f'transform="rotate(-30 {f(x0 + 40 * s)} {f(y0 + 24 * s)})"/>',
    ]
    out += f'<g fill="url(#{metal})" stroke="{edge}" stroke-width="{f(2.6 * s)}" stroke-linejoin="round">{"".join(parts)}</g>'
    return out, defs


def signet_ring(w: float, h: float) -> tuple[str, str]:
    """The signet ring at a slant, as print shows it: the broad seal face,
    dark and finely ridged, framed in gold and tilted toward us, with the
    band's thick gold edge curving away beneath it. In a w x h box."""
    gold, face, band = uid("rg"), uid("rf"), uid("rb")
    ridges = uid("rr")
    defs = (lin(gold, [(0, "#ffe7a0"), (0.45, "#e4a83a"), (1, "#8a5410")], 0.2, 1)
            + lin(face, [(0, "#5a3416"), (1, "#2a160a")], 0.3, 1)
            + lin(band, [(0, "#c8862a"), (1, "#6a3c0a")], 0, 1)
            + f'<pattern id="{ridges}" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(-38)">'
              '<rect width="7" height="2.4" fill="#7a4a22" opacity=".55"/></pattern>')
    sx, sy = w / 113, h / 100

    def P(x: float, y: float) -> str:
        return f"{f(x * sx)},{f(y * sy)}"

    edge = "#3a2006"
    # The band: a thick crescent under and behind the seal, its lit rim.
    out = (f'<path d="M{P(14, 46)} C{P(6, 70)} {P(24, 96)} {P(62, 96)} C{P(84, 96)} {P(98, 88)} {P(104, 74)} '
           f'L{P(88, 70)} C{P(80, 80)} {P(66, 84)} {P(52, 82)} C{P(34, 80)} {P(24, 66)} {P(30, 50)} Z" '
           f'fill="url(#{band})" stroke="{edge}" stroke-width="2.6" stroke-linejoin="round"/>'
           f'<path d="M{P(18, 58)} C{P(20, 78)} {P(36, 90)} {P(60, 91)}" fill="none" stroke="#ffd98a" stroke-width="2.4" '
           'stroke-linecap="round" opacity=".7"/>')
    # The seal: a gold-rimmed rounded slab tilted toward us, its dark ridged face.
    seal = f"rotate(-24 {f(60 * sx)} {f(44 * sy)})"
    out += (f'<g transform="{seal}">'
            f'<rect x="{f(14 * sx)}" y="{f(18 * sy)}" width="{f(92 * sx)}" height="{f(52 * sy)}" rx="{f(22 * sx)}" '
            f'fill="url(#{gold})" stroke="{edge}" stroke-width="2.8"/>'
            f'<rect x="{f(22 * sx)}" y="{f(24 * sy)}" width="{f(76 * sx)}" height="{f(38 * sy)}" rx="{f(16 * sx)}" fill="url(#{face})"/>'
            f'<rect x="{f(22 * sx)}" y="{f(24 * sy)}" width="{f(76 * sx)}" height="{f(38 * sy)}" rx="{f(16 * sx)}" fill="url(#{ridges})"/>'
            f'<path d="M{f(30 * sx)},{f(26.5 * sy)} H{f(88 * sx)}" stroke="#fff3c8" stroke-width="1.8" stroke-linecap="round" opacity=".55"/>'
            "</g>")
    return out, defs


def gear(cx: float, cy: float, r: float, color: str = "#e8cf6a", hole: str = "#3a3a12") -> str:
    """The Tech mark: a plain gear of eight square teeth and one hole."""
    teeth = 8
    points = []
    for k in range(teeth):
        mid = math.pi * 2 * k / teeth - math.pi / 2
        half_top, half_root = math.pi / teeth * 0.42, math.pi / teeth * 0.62
        for a, rr in ((mid - half_root, r * 0.76), (mid - half_top, r), (mid + half_top, r), (mid + half_root, r * 0.76)):
            points.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    poly = " ".join(f"{f(x)},{f(y)}" for x, y in points)
    return (f'<polygon points="{poly}" fill="{color}" stroke="{hole}" stroke-width="{f(r * 0.07)}" stroke-linejoin="round"/>'
            f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * 0.3)}" fill="{hole}"/>'
            f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{f(r * 0.56)}" fill="none" stroke="{hole}" stroke-width="{f(r * 0.06)}" opacity=".45"/>')


def control_arches(cx: float, cy: float, rim: str, dark: str, edge: str) -> str:
    """The Control banner's sign, simply: two broad arches over a plain disc."""
    return (f'<path d="M{f(cx - 30)},{f(cy)} A30,30 0 0 1 {f(cx + 30)},{f(cy)}" fill="none" stroke="{rim}" stroke-width="8"/>'
            f'<path d="M{f(cx - 19)},{f(cy)} A19,19 0 0 1 {f(cx + 19)},{f(cy)}" fill="none" stroke="{rim}" stroke-width="4.5" opacity=".8"/>'
            f'<circle cx="{f(cx)}" cy="{f(cy - 7)}" r="7.5" fill="{dark}" stroke="{edge}" stroke-width="1.8"/>')


def unload_cards() -> tuple[str, str]:
    """Unload's two little cards, as its red tag prints them: a copper card
    with a white arrow down (draw), a dark one with a white cross (trash).
    In a 100 x 66 box."""
    copper, dark = uid("uc"), uid("ud")
    defs = lin(copper, [(0, "#f0a050"), (1, "#8a3a10")], 0.3, 1) + lin(dark, [(0, "#5a5e5e"), (1, "#1e2222")], 0.3, 1)
    out = (f'<rect x="4" y="3" width="42" height="60" rx="5" fill="url(#{copper})" stroke="#f2ede6" stroke-width="3.2"/>'
           '<path d="M19,15 H31 V33 H39 L25,51 L11,33 H19 Z" fill="#fff" stroke="#3a1606" stroke-width="1.6" stroke-linejoin="round"/>'
           f'<rect x="54" y="3" width="42" height="60" rx="5" fill="url(#{dark})" stroke="#f2ede6" stroke-width="3.2"/>'
           '<path d="M64,20 L86,46 M86,20 L64,46" stroke="#fff" stroke-width="7.5" stroke-linecap="round"/>')
    return out, defs
