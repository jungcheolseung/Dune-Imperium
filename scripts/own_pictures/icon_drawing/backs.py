# ruff: noqa: E501  (SVG markup reads best one element to a line)
"""The project's own card backs (stage 5), drawn by hand, no logo."""

from __future__ import annotations

import math

from . import draw  # noqa: E402

f, pts, lin, rad = draw.f, draw.pts, draw.lin, draw.rad
OUT: dict[str, tuple[str, str]] = {}


def svg(w: int, h: int, body: str, note: str, defs: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f"  <!-- {note} Drawn by hand for the public build; no logo. -->\n  <defs>{defs}</defs>\n  {body}\n</svg>\n")


def contours(w: int, h: int, cx: float, cy: float, color: str, count: int = 9) -> str:
    return "".join(
        f'<ellipse cx="{f(cx)}" cy="{f(cy)}" rx="{f(w * (0.12 + k * 0.09))}" ry="{f(h * (0.08 + k * 0.06))}" fill="none" stroke="{color}" stroke-width="2" opacity=".18"/>'
        for k in range(count))


def blade(cx: float, cy: float, length: float, angle: float) -> str:
    """A red crysknife, centred, tilted by angle degrees."""
    L = length
    d = (f"M{f(-L * .06)},{f(L * .5)} L{f(-L * .02)},{f(-L * .38)} L{f(L * .05)},{f(-L * .5)} "
         f"L{f(L * .07)},{f(-L * .34)} L{f(L * .04)},{f(L * .5)} Z")
    guard = f'<path d="M{f(-L * .12)},{f(L * .3)} H{f(L * .12)}" stroke="#d61a1a" stroke-width="{f(L * .035)}" stroke-linecap="round"/>'
    return (f'<g transform="translate({f(cx)} {f(cy)}) rotate({f(angle)})"><path d="{d}" fill="#d61a1a" stroke="#4a0606" stroke-width="{f(L * .012)}"/>{guard}</g>')


for tier, (top, bottom, size) in {1: ("#2a0a0c", "#120406", 0.42), 2: ("#5a1014", "#240608", 0.5), 3: ("#8a1418", "#3a0608", 0.58)}.items():
    w, h = 510, 776
    numeral = "I" * tier
    body = (f'<rect width="{w}" height="{h}" rx="22" fill="url(#bg)"/>'
            + contours(w, h, w * .5, h * .45, "#ff9a8a")
            + f'<rect x="30" y="60" width="{w - 60}" height="{h - 120}" fill="none" stroke="#ff6a5a" stroke-width="3" opacity=".35"/>'
            + f'<polygon points="{pts([(w / 2, h * .34), (w / 2 + 64, h * .42), (w / 2, h * .5), (w / 2 - 64, h * .42)])}" fill="none" stroke="#d61a1a" stroke-width="5" opacity=".6"/>'
            + blade(w / 2, h * .42, h * size, -24) + blade(w / 2, h * .42, h * size, 24)
            + f'<text x="{w / 2}" y="{h * .9}" text-anchor="middle" font-family="Georgia, Times New Roman, serif" font-size="96" fill="#f2e4c8">{numeral}</text>')
    OUT[f"back_conflict_{tier}"] = (svg(w, h, body, f"Conflict {numeral} card back: crossed red blades over its tier.",
                                       lin("bg", top, bottom)), f"Conflict {numeral} card back: crossed red blades and the tier numeral.")

w, h = 512, 734
stars = "".join(f'<circle cx="{f((k * 97) % w)}" cy="{f((k * 61) % (h * .7))}" r="{f(1 + (k % 3) * .6)}" fill="#fff" opacity="{f(.35 + (k % 4) * .12)}"/>' for k in range(70))
body = (f'<rect width="{w}" height="{h}" rx="22" fill="url(#bg)"/>' + stars
        + f'<circle cx="{w * .62}" cy="{h * 1.02}" r="{h * .52}" fill="url(#planet)"/>'
        + f'<circle cx="{w * .62}" cy="{h * 1.02}" r="{h * .52}" fill="none" stroke="#f2c890" stroke-width="3" opacity=".5"/>'
        + contours(w, h, w * .62, h * 1.02, "#3a2410", 6)
        + f'<circle cx="{w * .2}" cy="{h * .2}" r="{w * .1}" fill="url(#moon)"/><circle cx="{w * .8}" cy="{h * .44}" r="{w * .055}" fill="url(#moon)"/>')
OUT["back_imperium"] = (svg(w, h, body, "Imperium card back: Arrakis and its two moons against the stars.",
                            lin("bg", "#1a2448", "#3a1a40") + rad("planet", "#e6a868", "#7a3e16", .4, .2) + rad("moon", "#e8e8e8", "#5a5a5a")),
                        "Imperium card back: Arrakis and its two moons against the stars.")

w, h = 510, 776
body = (f'<rect width="{w}" height="{h}" rx="22" fill="url(#bg)"/>' + contours(w, h, w * .5, h * .5, "#e8c060")
        + f'<rect x="30" y="60" width="{w - 60}" height="{h - 120}" fill="none" stroke="#e8c060" stroke-width="3" opacity=".3"/>'
        + draw.intrigue_glyph(w / 2, h / 2, 250, "", "#3a2606"))
OUT["back_intrigue"] = (svg(w, h, body, "Intrigue card back: the gold Intrigue mark.", lin("bg", "#2a2418", "#0e0c08")),
                        "Intrigue card back: the gold Intrigue mark on dark gold.")

w, h = 794, 520
beads = "".join(
    f'<circle cx="{f(w / 2 + 150 * math.cos(math.pi * 2 * k / 10))}" cy="{f(h / 2 + 150 * math.sin(math.pi * 2 * k / 10))}" r="36" fill="url(#gold)" stroke="#5a3a08" stroke-width="4"/>'
    for k in range(10))
body = (f'<rect width="{w}" height="{h}" rx="34" fill="url(#bg)"/>' + contours(w, h, w * .5, h * .5, "#d8c060")
        + f'<rect x="24" y="24" width="{w - 48}" height="{h - 48}" rx="60" fill="none" stroke="#d8b040" stroke-width="4" opacity=".6"/>'
        + f'<circle cx="{w / 2}" cy="{h / 2}" r="150" fill="none" stroke="#c99a30" stroke-width="22"/>' + beads
        + draw.gear(w / 2, h / 2, 74, "#e8c060", "#3a3a12"))
OUT["back_tech"] = (svg(w, h, body, "Tech tile back: a ring of gold beads round a gear.", lin("bg", "#4a5a24", "#1e2a10", 1, 1) + draw.lin("gold", "#ffd76a", "#b07a12")),
                    "Tech tile back: a ring of gold beads round a gear on olive.")


def build(index: dict) -> dict[str, str]:
    """Every drawing this module makes, by path under ``static/pictures``;
    ``index`` (the folder's index.json) gets each drawing's note."""
    files: dict[str, str] = {}
    for name, (text, note) in OUT.items():
        files[f"tokens/{name}.svg"] = text
        index[f"tokens/{name}.svg"] = {"drawn": "2026-11-10", "note": note}
    return files

