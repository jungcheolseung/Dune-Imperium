# ruff: noqa: E501  (SVG markup reads best one element to a line)
"""The project's own piece and token drawings (stage 4).

Drawn by hand in our own lines, looking at the game's pieces only for what
each should resemble. Each SVG takes the private picture's pixel size so
the page lays it out as before; the seat pieces come in the four seat
colours (green, red, yellow, blue), as the private pictures do.
"""

from __future__ import annotations

import math

DRAWN = "2026-11-10"
COLORS = {
    "green": ("#1f8a5a", "#6fd8a4", "#0c5234"),
    "red": ("#c42838", "#ff8490", "#76101c"),
    "yellow": ("#e2a826", "#ffe28c", "#946410"),
    "blue": ("#2a5ccc", "#86b0ff", "#14378a"),
}
OUT: dict[str, tuple[str, str]] = {}


def f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def pts(points) -> str:
    return " ".join(f"{f(x)},{f(y)}" for x, y in points)


def svg(w: int, h: int, body: str, note: str, defs: str = "") -> str:
    head = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    parts = [head, f"  <!-- {note} Drawn by hand for the public build. -->"]
    if defs:
        parts.append(f"  <defs>{defs}</defs>")
    parts += ["  " + body, "</svg>"]
    return "\n".join(parts) + "\n"


def lin(gid: str, c1: str, c2: str, x2: float = 0, y2: float = 1) -> str:
    return (f'<linearGradient id="{gid}" x1="0" y1="0" x2="{f(x2)}" y2="{f(y2)}">'
            f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient>')


def add(name: str, w: int, h: int, body: str, note: str, defs: str = "") -> None:
    OUT[name] = (svg(w, h, body, note, defs), note)


from . import extras, shapes  # noqa: E402  (the sword; the shared piece shapes)

# Each seat's colours as the game's pieces show them: (lit face, face, dark face, side, pale rim, disc).
PALETTE = {
    "green": ("#12b088", "#00926c", "#004c2d", "#006c49", "#62d8b0", "#13996b"),
    "red": ("#e6304e", "#c1243d", "#7c0912", "#a61d30", "#f47680", "#812826"),
    "yellow": ("#f4c242", "#dba921", "#9a6309", "#b78316", "#ffdc78", "#916627"),
    "blue": ("#4278d4", "#305da9", "#0d2263", "#1e3d83", "#80a6ee", "#25447b"),
}
STICKER = "#d3d3d3"


def knife(cx: float, cy: float, s: float, fill: str = "#e2202a", edge: str = "#3a0408") -> str:
    """A crysknife pointing up-right: a curved blade with a ridge, a guard and a grip."""
    blade = (f"M{f(cx - 6 * s)},{f(cy + 26 * s)} C{f(cx - 2 * s)},{f(cy + 6 * s)} {f(cx + 12 * s)},{f(cy - 18 * s)} {f(cx + 34 * s)},{f(cy - 40 * s)} "
             f"C{f(cx + 30 * s)},{f(cy - 20 * s)} {f(cx + 22 * s)},{f(cy - 2 * s)} {f(cx + 8 * s)},{f(cy + 26 * s)} Z")
    ridge = f"M{f(cx + 1 * s)},{f(cy + 22 * s)} C{f(cx + 6 * s)},{f(cy + 4 * s)} {f(cx + 16 * s)},{f(cy - 16 * s)} {f(cx + 31 * s)},{f(cy - 36 * s)}"
    guard = f"M{f(cx - 12 * s)},{f(cy + 24 * s)} L{f(cx + 16 * s)},{f(cy + 30 * s)}"
    grip = f"M{f(cx - 1 * s)},{f(cy + 28 * s)} L{f(cx - 10 * s)},{f(cy + 52 * s)}"
    return (f'<path d="{grip}" stroke="{edge}" stroke-width="{f(13 * s)}" stroke-linecap="round"/>'
            f'<path d="{grip}" stroke="{fill}" stroke-width="{f(7 * s)}" stroke-linecap="round"/>'
            f'<path d="{blade}" fill="{fill}" stroke="{edge}" stroke-width="{f(3.4 * s)}" stroke-linejoin="round"/>'
            f'<path d="{ridge}" fill="none" stroke="#7a0a12" stroke-width="{f(1.6 * s)}" opacity=".8"/>'
            f'<path d="{guard}" stroke="{edge}" stroke-width="{f(10 * s)}" stroke-linecap="round"/>'
            f'<path d="{guard}" stroke="{fill}" stroke-width="{f(5 * s)}" stroke-linecap="round"/>')


for color, (light, base, dark, side, rim, disc) in PALETTE.items():
    # Agent: the hooded figure.
    body, defs = shapes.agent(rim, base, rim, sx=1.45, sy=2.32)
    add(f"agent_{color}", 145, 232, body, f"Agent ({color}): a hooded figure in the seat's colour.", defs)

    # Spy: a short cylinder seen from a little above.
    w, h = 67, 96
    add(f"spy_{color}", w, h,
        '<path d="M4,18 V78 A29.5,14 0 0 0 63,78 V18 A29.5,14 0 0 0 4,18 Z" fill="#0a0a0a"/>'
        '<path d="M7.5,19 V77 A26,11.5 0 0 0 59.5,77 V19 Z" fill="url(#c)"/>'
        '<ellipse cx="33.5" cy="19" rx="26" ry="11.5" fill="url(#t)" stroke="#0a0a0a" stroke-width="2"/>'
        '<ellipse cx="33.5" cy="19.6" rx="19" ry="7.4" fill="none" stroke="#000" stroke-width="1.6" opacity=".35"/>'
        '<path d="M14,30 V78" stroke="#fff" stroke-width="2.4" opacity=".12" stroke-linecap="round"/>',
        f"Spy ({color}): a cylinder in the seat's colour.",
        shapes.lin("c", [(0, dark), (0.35, side), (0.6, base), (1, dark)], 1, 0) + shapes.lin("t", [(0, base), (1, side)]))

    # Troop: a cube with a pale edge.
    w, h = 60, 63
    add(f"troop_{color}", w, h,
        f'<polygon points="30,1.5 58.5,16 58.5,47 30,61.5 1.5,47 1.5,16" fill="{STICKER}" stroke="#9a9a9a" stroke-width="1" stroke-linejoin="round"/>'
        '<polygon points="30,6.5 53.5,18.5 53.5,44.5 30,56.5 6.5,44.5 6.5,18.5" fill="#111"/>'
        f'<polygon points="30,8 52,19.2 30,30.4 8,19.2" fill="url(#ct)"/>'
        f'<polygon points="8,19.2 30,30.4 30,55 8,43.8" fill="{base}"/>'
        f'<polygon points="52,19.2 30,30.4 30,55 52,43.8" fill="{dark}"/>'
        '<path d="M8.6,19.6 L30,30.4 L51.4,19.6 M30,30.4 V54.4" fill="none" stroke="#fff" stroke-width=".9" opacity=".25"/>',
        f"Troop ({color}): a cube in the seat's colour.", shapes.lin("ct", [(0, light), (1, base)]))

    # Control marker: a banner with two broad arches over a disc.
    w, h = 84, 97
    from . import extras3
    add(f"control_{color}", w, h,
        '<polygon points="1.5,1.5 82.5,1.5 82.5,95.5 42,78 1.5,95.5" fill="#0a0a0a"/>'
        '<polygon points="4,4 80,4 80,91.5 42,74.5 4,91.5" fill="url(#cb)"/>'
        '<rect x="12" y="8" width="60" height="12" fill="#000" opacity=".18"/>'
        + extras3.control_arches(42, 66, rim, dark, "#0a0a0a"),
        f"Control marker ({color}): a banner with two broad arches over a disc.",
        shapes.lin("cb", [(0, light), (1, base)]))

    # Player disc and Councilor: a dark-rimmed disc with a lighter ring (the Councilor adds the seat).
    ring = (f'<circle cx="64" cy="64" r="62" fill="#0a0a0a"/><circle cx="64" cy="64" r="57" fill="url(#dk)"/>'
            f'<circle cx="64" cy="64" r="50" fill="none" stroke="{light}" stroke-width="5" opacity=".8"/>'
            '<circle cx="64" cy="64" r="56" fill="none" stroke="#fff" stroke-width="1.4" opacity=".14"/>')
    dk = shapes.lin("dk", [(0, disc), (1, disc)])
    add(f"disc_{color}", 128, 128, ring, f"Player disc ({color}).", dk)
    add(f"council_{color}", 128, 128,
        ring + '<path d="M52,34 L58,26 H70 L76,34 V60 H86 L80,92 H48 L42,60 H52 Z" fill="none" stroke="#000" stroke-width="5.5" stroke-linejoin="round" opacity=".5"/>'
        '<path d="M42,60 H86" stroke="#000" stroke-width="5.5" opacity=".5"/>',
        f"Councilor token ({color}): the disc with a seat.", dk)

    # Dreadnought: the heavy hull.
    hull = shapes.dreadnought("url(#dt)", [dark, side, base, dark, side, dark], sticker=STICKER)
    add(f"dreadnought_{color}", 254, 231, f'<g transform="scale(2.54 2.31)">{hull}</g>',
        f"Dreadnought ({color}): a heavy hull in the seat's colour.", shapes.lin("dt", [(0, base), (0.6, light), (1, light)], 0.3, 1))

    # Sandworm: the worm rising out of the sand.
    body, defs = shapes.sandworm(light, base, side, sticker=STICKER)
    add(f"sandworm_{color}", 247, 252, f'<g transform="scale(2.47 2.52)">{body}</g>',
        f"Sandworm ({color}): a worm rising out of the sand and curling over.", defs)

    # Combat marker: the seat's square with a crysknife, and its +20 face.
    plate = ('<rect x="3" y="3" width="250" height="250" rx="34" fill="#0a0a0a"/>'
             '<rect x="7" y="7" width="242" height="242" rx="31" fill="url(#sq)"/>'
             '<rect x="44" y="44" width="168" height="168" rx="24" fill="#231b1b" stroke="#0a0a0a" stroke-width="3"/>')
    sq = shapes.lin("sq", [(0, light), (1, base)])
    blade, blade_defs = extras.sword(58, 50, 140, 156)
    add(f"strength_{color}", 256, 256, plate + blade, f"Combat marker ({color}): its sword face.", sq + blade_defs)
    add(f"strength_{color}_plus20", 256, 256,
        plate + '<text x="128" y="152" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="74" fill="#fff">+20</text>',
        f"Combat marker ({color}): its +20 face.", sq)

# Alliance tokens: the Faction's colour and mark with the victory point.
from . import draw  # noqa: E402  (the icon drawing helpers)

FACTION_FILL = {"emperor": ("#5c5c5d", "#333334"), "spacing_guild": ("#763e3e", "#482726"),
                "bene_gesserit": ("#70508f", "#3e314e"), "fremen": ("#506886", "#323f51")}
# The marks as the tokens show them: one muted tone, embossed with a dark line.
MARKS = {
    "emperor": draw.emperor(119, 100, 48, ("#c4c4c4", "#9e9e9e", "#2a2a2c")),
    "spacing_guild": draw.guild(118, 121, 83, ("#bc3036", "#a02024", "#3a1212")),
    "bene_gesserit": draw.bene_gesserit(119, 117, 66, ("#a878c0", "#8c5ca8", "#281c36")),
    "fremen": draw.fremen(119, 119, 63.5, ("#7ea6c6", "#4c7eae", "#1e2c42")),
}
GLOBE = ('<circle cx="119" cy="182" r="25" fill="url(#vp)" stroke="#5a3200" stroke-width="2.6"/>'
         '<g fill="none" stroke="#9a5a08" stroke-width="1.8" opacity=".9"><ellipse cx="119" cy="182" rx="10" ry="25"/>'
         '<ellipse cx="119" cy="182" rx="19" ry="25"/><path d="M94,182 H144 M97,170 H141 M97,194 H141"/></g>'
         '<circle cx="112" cy="173" r="6" fill="#fff8d0" opacity=".55"/>'
         '<g fill="url(#vp)" stroke="#5a3200" stroke-width="1.6"><circle cx="146" cy="196" r="7"/><circle cx="94" cy="166" r="5"/></g>')
for faction, (light, dark) in FACTION_FILL.items():
    add(f"alliance_{faction}", 238, 238,
        '<circle cx="119" cy="119" r="117" fill="#0e0c0a"/>'
        '<circle cx="119" cy="119" r="111" fill="url(#f)"/>'
        '<circle cx="119" cy="119" r="109.5" fill="none" stroke="#fff" stroke-width="2" opacity=".12"/>'
        + MARKS[faction] + GLOBE,
        f"Alliance token ({faction.replace('_', ' ')}): the Faction's mark and a victory point.",
        lin("f", light, dark) + draw.rad("vp", "#fff2a0", "#d88a10"))

# First player marker: a sandworm coiled round on itself, its maw turned to us.
hx, hy = 51, 58
whiskers = "".join(
    f'<path d="M{f(hx + 12 * math.cos(t))},{f(hy + 12 * math.sin(t))} L{f(hx + 46 * math.cos(t))},{f(hy + 46 * math.sin(t))}"/>'
    for t in (math.pi * (0.62 + k * 0.055) for k in range(16)))
coil_pts, coil_c, coil_n = shapes.tube(
    [((24, 78), (22, 104), (52, 112), (74, 106)), ((74, 106), (100, 98), (110, 70), (102, 48)),
     ((102, 48), (94, 26), (72, 22), (60, 40))], lambda t: 24 - 4 * abs(t - 0.5), samples=26)
coil = shapes.poly(coil_pts)
ribs = ""
for i in range(2, len(coil_c) - 1, 3):
    (x, y), (nx, ny) = coil_c[i], coil_n[i]
    w = 11
    ribs += f'<path d="M{f(x + nx * w)},{f(y + ny * w)} Q{f(x + ny * 4)},{f(y - nx * 4)} {f(x - nx * w)},{f(y - ny * w)}"/>'
spine = "M" + " L".join(f"{f(x - nx * 3)},{f(y - ny * 3)}" for (x, y), (nx, ny) in zip(coil_c, coil_n, strict=False))
teeth = "".join(
    f'<path d="M{f(hx + 11 * math.cos(t))},{f(hy + 11 * math.sin(t))} L{f(hx + 6 * math.cos(t + 0.16))},{f(hy + 6 * math.sin(t + 0.16))} '
    f'L{f(hx + 11 * math.cos(t + 0.32))},{f(hy + 11 * math.sin(t + 0.32))} Z"/>'
    for t in (k * math.pi / 10 for k in range(20)))
add("first_player", 126, 126,
    '<defs><clipPath id="fp"><circle cx="63" cy="63" r="49"/></clipPath>'
    '<filter id="fs" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="1.8"/></filter></defs>'
    '<circle cx="63" cy="63" r="62.5" fill="#c07a3a"/><circle cx="63" cy="63" r="61" fill="#2e2a26"/>'
    '<circle cx="63" cy="63" r="50.5" fill="#1a1612"/>'
    '<g clip-path="url(#fp)"><circle cx="63" cy="63" r="49" fill="url(#m)"/>'
    f'<g stroke="#e0a868" stroke-width="1.1" opacity=".5">{whiskers}</g>'
    f'<path d="{coil}" fill="#000" opacity=".55" filter="url(#fs)" transform="translate(2 3)"/>'
    f'<path d="{coil}" fill="url(#cl)" stroke="#3a1806" stroke-width="1.8" stroke-linejoin="round"/>'
    f'<path d="{spine}" fill="none" stroke="#ffd8a0" stroke-width="5" opacity=".28" filter="url(#fs)"/>'
    f'<g fill="none" stroke="#4a2008" stroke-width="1.5" opacity=".75">{ribs}</g></g>'
    f'<circle cx="{hx}" cy="{hy}" r="17" fill="url(#hd)" stroke="#3a1806" stroke-width="1.8"/>'
    f'<circle cx="{hx}" cy="{hy}" r="12.5" fill="#1a0a04"/>'
    f'<g fill="#f0d2a0" stroke="#4a2408" stroke-width=".5">{teeth}</g>'
    f'<circle cx="{hx}" cy="{hy}" r="5.5" fill="#050302"/>',
    "First player marker: a sandworm coiled on itself, its maw turned to us.",
    draw.rad("m", "#6a3a1a", "#1e0e06", 0.4, 0.45) + draw.lin("cl", "#e8aa66", "#8a4618", 1, 1) + draw.rad("hd", "#f0b878", "#a05a24", 0.4, 0.35))

# Maker Hooks: a hook on a slate plate stepped up at the right.


def maker_hook() -> str:
    """The token's hook: a pole along the bottom with its grip at the left,
    and at its right end a long curved spike rising to a point."""
    pole = "M120,330 H462"
    grip = "M110,330 H196"
    spike = ("M448,346 C452,250 456,160 462,92 C466,62 478,44 500,34 C488,58 484,84 482,112 "
             "C478,190 480,270 484,346 Z")
    out = ""
    for d, w in ((pole, 30), (grip, 44)):
        out += f'<path d="{d}" fill="none" stroke="#1a1e24" stroke-width="{w}" stroke-linecap="round"/>'
    out += f'<path d="{spike}" fill="#1a1e24" stroke="#1a1e24" stroke-width="12" stroke-linejoin="round"/>'
    for d, w, c in ((pole, 18, "url(#mt)"), (grip, 32, "#9aa2ae")):
        out += f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{w}" stroke-linecap="round"/>'
    out += f'<path d="{spike}" fill="url(#mt)"/>'
    out += '<path d="M126,324 H452 M456,330 C459,240 462,160 468,98" fill="none" stroke="#fff" stroke-width="4" opacity=".4"/>'
    return out


plate_d = "M22,150 H230 C300,150 300,22 380,22 H612 Q624,22 624,34 V412 Q624,426 610,426 H34 Q22,426 22,412 Z"
waves = "".join(f'<path d="M30,{y} C180,{y - 60} 380,{y + 40} 620,{y - 70}" fill="none"/>' for y in range(180, 460, 46))
add("maker_hooks", 644, 449,
    '<defs><clipPath id="mh"><path d="' + plate_d + '"/></clipPath></defs>'
    f'<path d="{plate_d}" fill="#0c0e12" stroke="#0c0e12" stroke-width="12" stroke-linejoin="round"/>'
    f'<path d="{plate_d}" fill="url(#p)"/>'
    f'<g clip-path="url(#mh)" stroke="#c8d4ea" stroke-width="3" opacity=".16">{waves}</g>'
    f'<path d="{plate_d}" fill="none" stroke="#fff" stroke-width="4" opacity=".18" transform="translate(0 4)"/>'
    + maker_hook() +
    '',
    "Maker Hooks: a steel hook on a slate plate.", lin("p", "#8a9ab6", "#4c5a74", 1, 1) + lin("mt", "#e4e8ec", "#9aa2ac"))
# Sardaukar Commander: a soldier in a lunge, his blade raised across him, on a round base.
fig = ("M60,26 Q58,14 66,12 Q76,12 76,24 Q76,32 70,35 L80,40 Q90,44 92,56 L96,74 Q98,80 92,82 L88,70 L84,92 "
       "L96,120 L108,158 L98,162 L80,126 L68,110 L58,128 L44,162 L32,158 L44,120 L52,96 L50,70 Q46,60 40,64 "
       "L30,72 Q24,74 24,68 L36,52 Q44,42 56,38 Z")
add("sardaukar_commander", 130, 195,
    '<ellipse cx="66" cy="172" rx="46" ry="14" fill="url(#b)"/><ellipse cx="66" cy="168" rx="46" ry="12" fill="url(#bt)" stroke="#5a5a5a" stroke-width="1.4"/>'
    f'<path d="{fig}" fill="url(#g)" stroke="#3e3e3e" stroke-width="2.2" stroke-linejoin="round"/>'
    '<path d="M64,44 L72,60 L64,78 M60,92 L70,108" fill="none" stroke="#6a6a6a" stroke-width="1.6" opacity=".7"/>'
    '<path d="M28,70 L124,26" stroke="#3e3e3e" stroke-width="6" stroke-linecap="round"/>'
    '<path d="M28,70 L124,26" stroke="#e6e6e6" stroke-width="3" stroke-linecap="round"/>'
    '<path d="M30,62 L36,76" stroke="#3e3e3e" stroke-width="6" stroke-linecap="round"/>',
    "Sardaukar Commander: a soldier figure in a lunge with his blade raised.",
    lin("g", "#e8e8e8", "#8e8e8e", 1, 1) + lin("b", "#8a8a8a", "#4a4a4a") + lin("bt", "#d0d0d0", "#a0a0a0"))
# Shield Wall: a wide strip of sand running corner to corner, a rocky ridge along its lower side.
strip = "M10,10 H196 L970,764 V975 H246 L10,718 Z"
rocks = ""
for k in range(46):
    t = k / 45
    jit = math.sin(k * 2.39) * 0.5 + math.sin(k * 5.1) * 0.5
    x, y = 110 + t * 560 + jit * 60, 250 + t * 610 - jit * 40
    sz = (48 + 62 * math.sin(t * math.pi)) * (0.7 + 0.45 * abs(math.sin(k * 1.31)))
    a0 = k * 0.9
    pts_ = [(x + sz * (0.7 + 0.35 * math.sin(a0 + j * 2.1)) * math.cos(a0 + j * math.pi / 3),
             y + sz * (0.6 + 0.3 * math.cos(a0 + j * 1.7)) * math.sin(a0 + j * math.pi / 3)) for j in range(6)]
    rocks += "<path d=\"" + shapes.poly(pts_) + "\"/>"
add("shield_wall", 980, 985,
    '<defs><clipPath id="sw"><path d="' + strip + '"/></clipPath>'
    '<filter id="sr" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="3"/></filter></defs>'
    f'<path d="{strip}" fill="url(#w)" stroke="#5a3e1a" stroke-width="10" stroke-linejoin="round"/>'
    f'<g clip-path="url(#sw)"><g fill="#3a2c1a" opacity=".75" filter="url(#sr)" transform="translate(-14 10)">{rocks}</g>'
    f'<g fill="#7a6648" stroke="#2e2212" stroke-width="5" stroke-linejoin="round">{rocks}</g>'
    f'<g fill="#e8e0cc" opacity=".6" transform="translate(12 -10) scale(.97)">{rocks}</g></g>'
    '<path d="M10,82 H170 L900,812 V975" fill="none" stroke="#fffaf0" stroke-width="14" opacity=".75" stroke-linejoin="round"/>'
    '<path d="M10,122 H150 L862,834 V975" fill="none" stroke="#fffaf0" stroke-width="6" opacity=".7" stroke-linejoin="round"/>',
    "Shield Wall token: a strip of sand with a rocky ridge along it.", lin("w", "#e2c690", "#c09858", 1, 1))


def build(index: dict) -> dict[str, str]:
    """Every drawing this module makes, by path under ``static/pictures``;
    ``index`` (the folder's index.json) gets each drawing's note."""
    files: dict[str, str] = {}
    for name, (text, note) in OUT.items():
        files[f"tokens/{name}.svg"] = text
        index[f"tokens/{name}.svg"] = {"drawn": DRAWN, "note": note}
    return files

