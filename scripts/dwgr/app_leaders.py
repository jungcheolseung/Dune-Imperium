"""Uprising leader card faces for the play UI, assembled from Steam app parts.

The app has no leader card. Its leader screens show the printed painting in
two layers, and both are the print's own art (checked by masked NCC against
the scans, 0.96-0.99):

- ``leader_ConflictWinner_<id>``: the figure cut out on a transparent ground,
  with 1.1-1.6x the scan's pixels;
- ``frame_DeferredAbility_BG<id>``: the painting without the figure, 256x139,
  scaled about 5.5-6x into place (soft at 1:1).

This script lays the two layers where the scan has them (``PLACEMENT``,
measured once with ``inputs --measure``) and draws the printed frame itself,
measured off the 1460x1020 scans so that the percentages in
``dune_imperium.display.leader_layout`` (Feyd's ``FEYD_TRACK_BOXES``) stay
valid: name band and complexity hexes, house band, DECK/DISCARD tabs, the
gold ability box, the black Signet box with the app's ring
(``UI_crd_ActionIcon_SignetRing``), Shaddam's red ring, Staban's red Limited
Allies box, Feyd's Training track, and the app's topographic lines
(``bg_TopoLines_1``) faint over the art as on the print. Icons are the app's
(the card renderer's ``HIRES`` pictures, else its TextMeshPro glyphs) and
are laid out as printed: icon rows, big icons beside text, small icons in
the text.

Text, as on the card:

- English: the app's ``worm.leader.<id>.*`` strings, with the assets
  repository's ``cards/app/en_text.json`` taking precedence where the print
  differs (Lady Jessica's flip sentence, Reverend Mother Jessica's ability,
  Gurney's 6* and its footnote);
- Korean: the official Korean edition only, never the app's translation:
  names from ``display.names_ko``, ability and Signet text from
  ``display.leaders_ko.LEADER_FACE_TEXTS_KO`` (a transcription of the Korean
  cards), and the house lines and tab words read off the Korean photos
  (``HOUSE_KO``, ``TABS_KO``). Reverend Mother Jessica has no Korean card, so
  only her English face is built (the Korean UI falls back to it).

Line breaks follow the print (``BREAKS``): they only replace spaces, never
words (``relayout`` checks it).

Inputs go to the assets checkout's git-ignored
``reference/dune-steam-app/<build-guid>/render/leaders/`` (with the card
renderer's ``render/sprites``, ``render/inline`` and ``render/fonts`` from
``app_assets.py card-inputs``); faces go to
``assets/cards/app/<lang>/uprising/leader/<Printed Name>.webp`` with their
sources in ``assets/cards/app/leader_sources.json``.

    uv run --offline --with UnityPy python scripts/dwgr/app_leaders.py inputs
    uv run --offline --with pillow --with numpy python \\
        scripts/dwgr/app_leaders.py inputs --measure-only
    uv run --offline --with pillow --with numpy python \\
        scripts/dwgr/app_leaders.py render [--lang en,ko] [--ids muad_dib,...]
    uv run --offline --with pillow --with numpy python \\
        scripts/dwgr/app_leaders.py compare --out DIR
"""

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
ASSETS = REPO / "assets"
CARDS = ASSETS / "cards"
STEAM_DATA = Path(
    "~/Library/Application Support/Steam/steamapps/common/Dune Imperium/"
    "DuneImperium.app/Contents/Resources/Data"
).expanduser()

# content id -> (app sprite id, app loc id)
APP_IDS = {
    "muad_dib": ("muaddib", "muaddib"),
    "shaddam_corrino_iv": ("shaddamcorrinoiv", "shaddamcorrinoiv"),
    "feyd_rautha_harkonnen": ("feydrauthaharkonnen", "feydrauthaharkonnen"),
    "gurney_halleck": ("gurneyhalleckleader", "gurneyhalleck"),
    "lady_amber_metulli": ("ladyambermetulli", "ladyambermetulli"),
    "lady_jessica": ("ladyjessicaleader", "ladyjessica"),
    "lady_margot_fenring": ("ladymargotfenring", "ladymargotfenring"),
    "princess_irulan": ("princessirulan", "princessirulan"),
    "reverend_mother_jessica": ("reverendmotherjessica", "reverendmotherjessica"),
    "staban_tuek": ("stabantuek", "stabantuek"),
}
FIGURE = "leader_ConflictWinner_{}"
BACKGROUND = "frame_DeferredAbility_BG{}"
SIGNET_RING = "UI_crd_ActionIcon_SignetRing"
# The print's thin contour lines over the art: the app's own topographic
# texture is the same drawing style (bundles of parallel wavy lines); the
# print's exact lines are not in the app.
TOPO_LINES = "bg_TopoLines_1"
TOPO_ALPHA = 0.22  # of the texture's own alpha (at most 102)
UNCOVERED_SHADE = 0.45
FRAME_SPRITES = (SIGNET_RING, TOPO_LINES)

# Figure and background placement against the 1460x1020 scan:
# (scale, left, top) of the saved texture, from `inputs --measure`
# (masked NCC: figures 0.97-0.99, backgrounds 0.92-0.99).
PLACEMENT = {
    "muad_dib": {"figure": (0.9162, 490, 158), "background": (6.0096, -32, 96)},
    "shaddam_corrino_iv": {
        "figure": (0.8117, 194, 176),
        "background": (5.9187, -30, 90),
    },
    "feyd_rautha_harkonnen": {
        "figure": (0.8558, -4, 168),
        "background": (5.4846, 28, 140),
    },
    "gurney_halleck": {"figure": (0.9162, 530, -2), "background": (5.6921, 4, 114)},
    "lady_amber_metulli": {
        "figure": (0.7874, 542, 134),
        "background": (5.6543, 8, 118),
    },
    "lady_jessica": {"figure": (0.7696, 162, 182), "background": (5.6921, 4, 118)},
    "lady_margot_fenring": {
        "figure": (0.9026, 606, 174),
        "background": (5.4846, 76, 138),
    },
    "princess_irulan": {
        "figure": (0.6564, 452, 116),
        "background": (5.5318, 22, 128),
    },
    "reverend_mother_jessica": {
        "figure": (0.9026, 672, 144),
        "background": (5.6921, 0, 116),
    },
    "staban_tuek": {"figure": (0.6416, 528, 124), "background": (5.6921, 4, 118)},
}

# ---------------------------------------------------------------- the frame
# Measured on the scans (card pixels, 1460x1020).
W, H = 1460, 1020
SS = 2  # the frame and the text are drawn at 2x and scaled down
CORNER = 38
ART = (30, 28, 1437, 995)  # the art window: left, top, right, bottom
NAME_LINE_Y = 126
HOUSE_BAND = ((30, 127), (772, 127), (706, 177), (30, 177))
DISCARD_TAB = ((1345, 28), (1437, 28), (1437, 407), (1345, 315))
DECK_TAB = ((30, 495), (122, 587), (122, 995), (30, 995))
BOX_LEFT, BOX_BOTTOM = 122, 995
SET_MARK = (1423, 979, 9)  # the small hexagon in the bottom right corner


def gold_edge(y):
    """x of the ability box's slanted right edge at height y."""
    return 806 - 0.571 * (BOX_BOTTOM - y)


def signet_edge(y):
    """x of the Signet box's slanted left edge at height y."""
    return 867 - 0.62 * (BOX_BOTTOM - y)


# Box tops and title strips: every leader but Staban Tuek, whose red
# Limited Allies box pushes the ability box down and the Signet box up.
# Box tops, title strips (the line under the title, from the box top), title
# baselines (from the box top) and the Signet badge: every leader but two.
# Staban Tuek's red Limited Allies box pushes the ability box down and the
# Signet box up; Feyd-Rautha's Training track pushes both boxes down.
LAYOUTS = {
    "normal": {
        "red_top": None,
        "gold_top": 778,
        "gold_title": 48,
        "gold_base": 36,
        "signet_top": 778,
        "signet_title": 46,
        "signet_base": 37,
        "signet_x": 884,
        "house": True,
        "octagon": (820, 834),
    },
    "staban": {
        "red_top": 604,
        "red_title": 58,
        "red_base": 39,
        "gold_top": 780,
        "gold_title": 48,
        "gold_base": 38,
        "signet_top": 663,
        "signet_title": 53,
        "signet_base": 43,
        "signet_x": 884,
        "house": False,
        "octagon": (752, 717),
    },
}
LAYOUTS["feyd"] = dict(
    LAYOUTS["normal"],
    gold_top=818,
    gold_title=56,
    gold_base=44,
    signet_top=818,
    signet_title=57,
    signet_base=44,
    signet_x=904,
    octagon=(840, 871),
)
LAYOUT_OF = {"staban_tuek": "staban", "feyd_rautha_harkonnen": "feyd"}

COLORS = {
    "card": (3, 3, 3),
    "band": (3, 3, 3),
    "name_line": (78, 80, 76),
    "discard": (89, 85, 72),
    "deck": (62, 57, 41),
    "gold": (97, 77, 43),
    "gold_line": (62, 47, 25),
    "gold_hi": (150, 128, 88),
    "signet": (3, 3, 3),
    "signet_line": (92, 96, 100),
    "edge_hi": (120, 132, 150),
    "red_title": (36, 16, 10),
    "red_top": (44, 22, 14),
    "red_bottom": (104, 32, 18),
    "red_line": (88, 32, 26),
    "octagon_line": (104, 114, 132),
    "hex": (242, 242, 240),
    "ring": (205, 30, 22),
    "set_mark": (74, 76, 80),
    "dots": (150, 148, 138),
    "name": (253, 252, 251),
    "house": (178, 177, 170),
    "tab_text": (206, 201, 188),
    "title": (255, 250, 245),
    "body": (255, 250, 245),
}


# Reverend Mother Jessica's card prints its tabs and ability box greyer.
FRAME_COLORS = {
    "reverend_mother_jessica": {
        "discard": (71, 71, 68),
        "deck": (62, 58, 50),
        "gold": (95, 76, 54),
    }
}


def build_guid():
    for line in open(STEAM_DATA / "boot.config"):
        if line.startswith("build-guid="):
            return line.strip().split("=", 1)[1]
    raise SystemExit("no build-guid in boot.config")


def render_dir():
    return ASSETS / "reference" / "dune-steam-app" / build_guid() / "render"


def inputs_dir():
    return render_dir() / "leaders"


def input_names():
    names = []
    for sprite_id, _loc in APP_IDS.values():
        names += [FIGURE.format(sprite_id), BACKGROUND.format(sprite_id)]
    return names + list(FRAME_SPRITES)


def manifest_entries():
    doc = json.loads((CARDS / "manifest.json").read_text())
    return {
        e["content_id"]: e
        for e in doc["entries"]
        if e["kind"] == "leader" and e.get("content_id") in APP_IDS
    }


def layout(cid):
    return LAYOUTS[LAYOUT_OF.get(cid, "normal")]


def gold_polygon(top):
    return (
        (BOX_LEFT, top),
        (gold_edge(top), top),
        (gold_edge(BOX_BOTTOM), BOX_BOTTOM),
        (BOX_LEFT, BOX_BOTTOM),
    )


def signet_polygon(top):
    return (
        (signet_edge(top), top),
        (ART[2], top),
        (ART[2], BOX_BOTTOM),
        (signet_edge(BOX_BOTTOM), BOX_BOTTOM),
    )


def frame_polygons(cid):
    """The printed frame parts that hide the art."""
    lay = layout(cid)
    polys = [DISCARD_TAB, DECK_TAB]
    if lay["house"]:
        polys.append(HOUSE_BAND)
    polys.append(gold_polygon(lay["red_top"] or lay["gold_top"]))
    polys.append(signet_polygon(lay["signet_top"]))
    return polys


def frame_mask(cid, pad=6):
    """True where the print's frame (or Feyd's track) hides the art."""
    from PIL import Image, ImageDraw, ImageFilter

    m = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(m)
    d.rectangle((ART[0] + pad, 130 + pad, ART[2] - pad, ART[3] - pad), fill=0)
    for poly in frame_polygons(cid):
        d.polygon([(round(x), round(y)) for x, y in poly], fill=255)
    if cid == "feyd_rautha_harkonnen":
        d.rectangle((595, 580, ART[2], 815), fill=255)
    m = m.filter(ImageFilter.MaxFilter(2 * pad + 1))
    return np.asarray(m) > 127


# ---------------------------------------------------------------- measuring
def _corr(a, b, fh, fw):
    return np.fft.irfft2(
        np.fft.rfft2(a, (fh, fw)) * np.fft.rfft2(b[::-1, ::-1], (fh, fw)), (fh, fw)
    )


def ncc_search(scan, valid, templ, alpha, scales, step):
    """Best (ncc, scale, left, top) of a template over a grey scan.

    Zero-mean NCC over the scan pixels ``valid`` marks (and the template
    pixels its ``alpha`` keeps), searched at 1/``step`` resolution."""
    from PIL import Image

    h, w = scan.shape
    img = Image.fromarray((scan * 255).astype(np.uint8))
    small = np.asarray(img.resize((w // step, h // step), Image.LANCZOS), float) / 255
    keep = Image.fromarray(valid.astype(np.uint8) * 255).resize(
        (w // step, h // step), Image.BILINEAR
    )
    v = (np.asarray(keep, float) > 250).astype(float)
    best = None
    for s in scales:
        tw = max(4, round(templ.width * s / step))
        th = max(4, round(templ.height * s / step))
        t = np.asarray(templ.resize((tw, th), Image.LANCZOS), float) / 255
        if alpha is None:
            m = np.ones_like(t)
        else:
            a = np.asarray(alpha.resize((tw, th), Image.LANCZOS), float)
            m = (a > 230).astype(float)
        fh, fw = small.shape[0] + th, small.shape[1] + tw
        n = _corr(v, m, fh, fw)
        s_i, s_ii = _corr(v * small, m, fh, fw), _corr(v * small * small, m, fh, fw)
        s_t, s_tt = _corr(v, m * t, fh, fw), _corr(v, m * t * t, fh, fw)
        s_it = _corr(v * small, m * t, fh, fw)
        nn = np.maximum(n, 1)
        ok = n > 0.3 * m.sum()
        cov = s_it - s_i * s_t / nn
        vi, vt = s_ii - s_i**2 / nn, s_tt - s_t**2 / nn
        ncc = np.where(
            ok & (vi > 1e-4) & (vt > 1e-4),
            cov / np.sqrt(np.maximum(vi * vt, 1e-12)),
            -1,
        )
        iy, ix = np.unravel_index(np.argmax(ncc), ncc.shape)
        if best is None or ncc[iy, ix] > best[0]:
            best = (
                float(ncc[iy, ix]),
                float(s),
                int((ix - (tw - 1)) * step),
                int((iy - (th - 1)) * step),
            )
    return best


def measure(cid, scan_path):
    """NCC placement of the app figure, then the background, on the scan."""
    from PIL import Image

    sprite_id = APP_IDS[cid][0]
    d = inputs_dir()
    fig = Image.open(d / f"{FIGURE.format(sprite_id)}.png").convert("RGBA")
    bg = Image.open(d / f"{BACKGROUND.format(sprite_id)}.png").convert("RGBA")
    scan = np.asarray(Image.open(scan_path).convert("L").resize((W, H)), float) / 255
    valid = ~frame_mask(cid)
    grey, alpha = fig.convert("L"), fig.getchannel("A")
    f = ncc_search(scan, valid, grey, alpha, np.geomspace(0.5, 1.5, 30), 4)
    f = ncc_search(
        scan, valid, grey, alpha, np.geomspace(f[1] * 0.97, f[1] * 1.03, 9), 2
    )
    fw, fh = round(fig.width * f[1]), round(fig.height * f[1])
    fa = np.asarray(alpha.resize((fw, fh)), float) > 20
    figmask = np.zeros((H, W), bool)
    x0, y0 = f[2], f[3]
    ys = slice(max(0, y0), min(H, y0 + fh))
    xs = slice(max(0, x0), min(W, x0 + fw))
    figmask[ys, xs] = fa[ys.start - y0 : ys.stop - y0, xs.start - x0 : xs.stop - x0]
    bvalid = valid & ~figmask
    bgrey = bg.convert("L")
    b = ncc_search(scan, bvalid, bgrey, None, np.geomspace(4.5, 7.0, 30), 4)
    b = ncc_search(
        scan, bvalid, bgrey, None, np.geomspace(b[1] * 0.98, b[1] * 1.02, 7), 2
    )
    return {"figure": f, "background": b}


def cmd_inputs(args):
    if not args.measure_only:
        from app_assets import App  # needs UnityPy; render does not

        out = inputs_dir()
        out.mkdir(parents=True, exist_ok=True)
        meta_path = out / "_meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        app = App()
        missing = []
        names = input_names() + list(args.extra or ())
        for name in names:
            m = app.save_picture(name, str(out / f"{name}.png"))
            if m is None:
                missing.append(name)
            elif m:
                meta[name] = m
        meta_path.write_text(json.dumps(meta, indent=0) + "\n")
        print("inputs:", len(names) - len(missing), "saved, missing", missing)
    if args.measure or args.measure_only:
        entries = manifest_entries()
        for cid in args.ids.split(",") if args.ids else list(APP_IDS):
            r = measure(cid, CARDS / "en" / entries[cid]["path"])
            print(
                cid,
                json.dumps({k: [round(v, 4) for v in t] for k, t in r.items()}),
                flush=True,
            )


# ---------------------------------------------------------------- the leaders
# Printed details that are not text: complexity hexes after the name, the red
# ring before Shaddam's name, the house (none on Staban Tuek's card).
LEADERS = {
    "muad_dib": {"house": "atreides", "hexes": 1},
    "shaddam_corrino_iv": {"house": "corrino", "hexes": 2, "ring": True},
    "feyd_rautha_harkonnen": {"house": "harkonnen", "hexes": 1, "track": True},
    "gurney_halleck": {"house": "atreides", "hexes": 1},
    "lady_amber_metulli": {"house": "metulli", "hexes": 1},
    "lady_jessica": {"house": "atreides", "hexes": 2},
    "lady_margot_fenring": {"house": "fenring", "hexes": 1},
    "princess_irulan": {"house": "corrino", "hexes": 2},
    "reverend_mother_jessica": {"house": "atreides", "hexes": 2},
    "staban_tuek": {"house": None, "hexes": 3},
}
# Korean words read off the Korean edition's leader cards (photos in
# cards/ko/uprising/leader/): the house lines and the two side tabs.
HOUSE_KO = {
    "atreides": "아트레이드 가문",
    "corrino": "코리노 가문",
    "harkonnen": "하코넨 가문",
    "metulli": "메툴리 가문",
    "fenring": "펜링 가문",
}
TABS_EN = {"deck": "DECK", "discard": "DISCARD"}
# (DISCARD, DECK) word centres on the tabs, as printed
TAB_CENTRES = {"en": ((1391, 189), (76, 788)), "ko": ((1384, 191), (77, 779))}
TABS_KO = {"deck": "카드 덱", "discard": "버림 더미"}
# Where a cut-out ends in a hard edge above the boxes, its last rows are
# carried down behind the gap between the two boxes.
EXTEND_FIGURE_BOTTOM = {"princess_irulan", "staban_tuek"}

# Icon tokens of display.leaders_ko -> the app's sprite names.
KO_TOKENS = {
    "persuasion": "Persuasion",
    "solari": "Solari",
    "spice": "Spice",
    "troop": "Troop",
    "recall_spy": "RecallSpy",
    "sword": "Strength",
    "agent_icon_bene_gesserit": "BeneGesserit",
    "agent_icon_emperor": "Emperor",
    "agent_icon_spacing_guild": "SpacingGuild",
    "agent_icon_fremen": "Fremen",
    "agent_icon_landsraad": "Landsraad",
    "agent_icon_city": "PopulationCenter",
    "intrigue": "IntrigueCard",
    "draw": "DrawCard",
    "spy": "Spy",
    "influence_any": "WildRankUp",
    "water": "Water",
}
# Larger app pictures of glyphs the card renderer's HIRES table lacks.
HIRES_EXTRA = {"Water": "UI_crd_CostIcon_Water"}
# Icons drawn smaller than their neighbours, as printed (fraction of the height).
ICON_SCALE = {"IfThenArrow": 0.62}

DEBUG = False
# The Korean edition's Feyd sets his box titles higher.
KO_TITLE_RAISE = {"feyd_rautha_harkonnen": 6}
# The print's names leave more room between words than the tracking gives.
NAME_WORD_GAP = {"en": 8.0, "ko": 9.0}
KO_BODY_SPACING = -3.0  # the Korean edition sets its text a little tight
LINE = "\u2028"  # a printed line break inside a paragraph ("\n" ends one)

# Printed line and paragraph breaks: (lang, content id, box) -> [(anchor,
# break)]; the whitespace before each anchor becomes the break.
BREAKS = {
    ("en", "muad_dib", "ability"): [("one or more", LINE), ("in the Conflict", LINE)],
    ("en", "shaddam_corrino_iv", "ability"): [
        ("contracts.", LINE),
        ("them during", LINE),
    ],
    ("en", "shaddam_corrino_iv", "signet"): [("Conflict this", LINE)],
    ("en", "feyd_rautha_harkonnen", "signet"): [
        ("right on your", LINE),
        ("the reward", LINE),
    ],
    ("en", "gurney_halleck", "ability"): [("6* or more", LINE), ("the Conflict", LINE)],
    ("en", "lady_amber_metulli", "ability"): [("one of your", LINE)],
    ("en", "lady_jessica", "ability"): [
        ("space, you may", LINE),
        ("to your supply", LINE),
        ("Then flip", LINE),
    ],
    ("en", "lady_jessica", "signet"): [("your supply to", LINE), ("area of the", LINE)],
    ("en", "lady_margot_fenring", "ability"): [('<sprite name="BeneGesserit">', LINE)],
    ("en", "princess_irulan", "ability"): [('<sprite name="Emperor">', LINE)],
    ("en", "princess_irulan", "signet"): [
        ("costs <sprite", LINE),
        ("card from your", LINE),
        ('<sprite name="Persuasion_1"> or more', LINE),
    ],
    ("en", "reverend_mother_jessica", "ability"): [
        ("send an Agent", LINE),
        ("space, you may", LINE),
        ("the effects", LINE),
    ],
    ("en", "staban_tuek", "ability"): [
        ("sends an Agent", LINE),
        ("board space you", LINE),
        ("spying on", LINE),
    ],
    ("en", "staban_tuek", "limited"): [("Diplomacy in", LINE)],
    ("ko", "muad_dib", "ability"): [("모래벌레가", LINE)],
    ("ko", "shaddam_corrino_iv", "ability"): [("이 계약들은", LINE)],
    ("ko", "shaddam_corrino_iv", "signet"): [('<sprite name="Solari_1">', "\n")],
    ("ko", "feyd_rautha_harkonnen", "signet"): [("오른쪽으로", LINE), ("보상을", LINE)],
    ("ko", "gurney_halleck", "ability"): [("전투력 총합이", LINE), ("(*6인", "\n")],
    ("ko", "lady_jessica", "ability"): [
        ("당신은 모든", LINE),
        ("보낸 기억 1당", LINE),
        ("보냈을 경우", LINE),
    ],
    ("ko", "lady_jessica", "signet"): [("게임판의 베네", LINE), ("옮김.", LINE)],
    ("ko", "lady_margot_fenring", "ability"): [("도달할 때", LINE)],
    ("ko", "princess_irulan", "ability"): [("도달할 때", LINE)],
    ("ko", "princess_irulan", "signet"): [
        ("당신의 핸드로", LINE),
        ("당신의 핸드에서", LINE),
        ('<sprite name="Persuasion_1"> 이상이라면', LINE),
    ],
    ("ko", "staban_tuek", "ability"): [("게임판 장소로", LINE), ("에이전트를", LINE)],
    ("ko", "staban_tuek", "limited"): [("채로 게임을", LINE)],
}
# English print corrections the app's strings need (kept in the assets
# repository's cards/app/en_text.json, like the card renderer's).
EN_PRINT_KEYS = (
    "worm.leader.gurneyhalleck.staticability.desc",
    "worm.leader.ladyjessica.staticability.desc",
    "worm.leader.reverendmotherjessica.staticability.desc",
)

# Box layout, card pixels (see Box): defaults per box and language, then
# per leader. size: text px; pitch: line distance in ems; icon: big icon
# height; inline: icon height in the text, in ems; align: "left" keeps
# paragraphs at x0, "center" centres them on cx.
BOX_DEFAULTS = {
    "ability": {
        "size": 37.5,
        "pitch": 1.147,
        "icon": 80,
        "inline": 1.1,
        "x0": 141,
        "cx": 423,
        "x1": 720,
        "align": "center",
        "squeeze": 0.94,
    },
    "signet": {
        "size": 31,
        "pitch": 1.32,
        "icon": 78,
        "inline": 1.3,
        "x0": 881,
        "cx": 1156,
        "x1": 1430,
        "align": "center",
        "squeeze": 0.94,
        "dy": 8,
    },
    "limited": {
        "size": 36,
        "pitch": 1.14,
        "icon": 60,
        "inline": 1.1,
        "x0": 142,
        "cx": 380,
        "x1": 640,
        "align": "left",
        "squeeze": 0.94,
    },
}
BOX_DEFAULTS_KO = {
    "ability": {"size": 33, "pitch": 1.53, "squeeze": 1.0},
    "signet": {"size": 30.5, "pitch": 1.3, "squeeze": 1.0},
    "limited": {"size": 34.7, "pitch": 1.41, "squeeze": 1.0},
}
# Per leader: (content id, box) for both languages, (content id, box, lang)
# for one; measured on the scans (English) and the photos (Korean).
BOXES = {
    ("muad_dib", "ability"): {"trail_cx": 651},
    ("muad_dib", "ability", "en"): {"align": "left"},
    ("muad_dib", "ability", "ko"): {"pitch": 1.65, "cx": 376},
    ("shaddam_corrino_iv", "ability"): {"align": "left", "x0": 139},
    ("shaddam_corrino_iv", "signet"): {
        "align": "left",
        "icon": 62,
        "gap": 22,
        "row_gap": 21,
        "sep": 0.75,
    },
    ("shaddam_corrino_iv", "signet", "ko"): {
        "size": 31,
        "gap": 30,
        "x0": 874,
        "icon": 64,
        "sep": 0.9,
        "dy": -2,
    },
    ("feyd_rautha_harkonnen", "ability"): {"align": "left", "icon": 84},
    ("feyd_rautha_harkonnen", "ability", "ko"): {"icon": 84, "dy": -8},
    ("feyd_rautha_harkonnen", "signet", "en"): {
        "size": 29,
        "pitch": 1.22,
        "align": "left",
        "x0": 902,
    },
    ("feyd_rautha_harkonnen", "signet", "ko"): {
        "size": 31.4,
        "pitch": 1.23,
        "align": "left",
        "x0": 898,
        "dy": -6,
    },
    ("gurney_halleck", "ability"): {
        "trail_cx": 640,
        "align": "left",
        "note_indent": 31,
        "trail_over_notes": True,
    },
    ("lady_amber_metulli", "ability"): {"align": "left"},
    ("lady_amber_metulli", "ability", "ko"): {"size": 32.5},
    ("lady_amber_metulli", "signet"): {
        "icon": 80,
        "label_above": True,
        "join": True,
        "row": True,
        "sep": 0.75,
        "row_gap": 16,
        "label": 0.84,
        "dy": 26,
    },
    ("lady_amber_metulli", "signet", "ko"): {"row_gap": 30, "label": 0.9, "dy": 20},
    ("lady_jessica", "ability"): {"x1": 790},
    ("lady_jessica", "ability", "en"): {
        "dy": 9,
        "size": 31.5,
        "pitch": 1.06,
        "align": "left",
        "inline": 1.25,
    },
    ("lady_jessica", "ability", "ko"): {
        "size": 26.3,
        "pitch": 1.48,
        "align": "left",
        "inline": 1.45,
    },
    ("lady_jessica", "signet", "en"): {
        "size": 31.4,
        "pitch": 1.32,
        "align": "left",
        "inline": 1.75,
    },
    ("lady_jessica", "signet", "ko"): {
        "size": 30,
        "pitch": 1.5,
        "align": "left",
        "inline": 1.6,
        "trail": False,
    },
    ("lady_margot_fenring", "ability"): {"icon": 82, "trail_cx": 585, "cx": 346},
    ("lady_margot_fenring", "ability", "ko"): {"pitch": 1.57, "cx": 348, "inline": 1.4},
    ("lady_margot_fenring", "signet"): {"icon": 86, "row_text": 1.1, "row_gap": 14},
    ("princess_irulan", "ability"): {"icon": 84, "trail_cx": 585, "cx": 345},
    ("princess_irulan", "ability", "ko"): {"pitch": 1.57, "cx": 348, "inline": 1.4},
    ("princess_irulan", "signet"): {"align": "left", "trail": False},
    ("princess_irulan", "signet", "en"): {"size": 30.2, "pitch": 1.16, "inline": 1.15},
    ("princess_irulan", "signet", "ko"): {"size": 29.9, "pitch": 1.3, "inline": 1.15},
    ("reverend_mother_jessica", "ability"): {
        "squeeze": 0.97,
        "size": 32.5,
        "pitch": 1.23,
        "align": "left",
        "x0": 137,
        "inline": 1.35,
    },
    ("reverend_mother_jessica", "signet"): {"icon": 84},
    ("staban_tuek", "ability"): {"align": "left", "icon": 86, "trail_cx": 663},
    ("staban_tuek", "ability", "en"): {"size": 36, "pitch": 1.13},
    ("staban_tuek", "ability", "ko"): {"size": 34.6, "pitch": 1.42},
    ("staban_tuek", "signet"): {
        "icon": 46,
        "x0": 886,
        "gap": 14,
        "dy": 10,
        "colon_gap": 30,
        "paras": {
            0: {"icon": 76, "cx": 1117},
            1: {"align": "left", "x0": 818},
            2: {"align": "left"},
            3: {"align": "left"},
        },
    },
}


# ---------------------------------------------------------------- inputs
class Inputs:
    def __init__(self):
        import app_render as R
        from app_cards import KOREAN_FONT, PRINT_STRETCHED_SPRITES

        rd, ld = render_dir(), inputs_dir()
        if not (rd / "loc_en_US.json").exists():
            raise SystemExit("run `app_assets.py card-inputs` first")
        missing = [n for n in input_names() if not (ld / f"{n}.png").exists()]
        if missing:
            raise SystemExit(f"run `app_leaders.py inputs` first (missing {missing})")
        self.loc = json.loads((rd / "loc_en_US.json").read_text())
        self.sprites = R.Sprites(str(rd / "sprites"), PRINT_STRETCHED_SPRITES)
        self.inline = R.Sprites(str(rd / "inline"))
        self.inline.meta = {}
        self.leader_sprites = R.Sprites(str(ld))
        assets = json.loads((rd / "fonts" / "sprite_assets.json").read_text())
        self.text = text_renderer(R)(
            str(rd / "fonts"), self.inline, assets, fallback_path=str(KOREAN_FONT)
        )
        en_path = CARDS / "app" / "en_text.json"
        self.en = json.loads(en_path.read_text()) if en_path.exists() else {}
        missing = [k for k in EN_PRINT_KEYS if k not in self.en]
        if missing:
            raise SystemExit(f"cards/app/en_text.json lacks the print text {missing}")
        self.entries = manifest_entries()
        self.pictures = {}

    def leader_picture(self, name):
        return self.leader_sprites.get(name, stretch=True)

    def icon(self, name):
        """The icon's picture cropped to its visible pixels."""
        if name not in self.pictures:
            from app_cards import HIRES

            hi = HIRES_EXTRA.get(name) or HIRES.get(name)
            img = self.sprites.get(hi) if hi else None
            img = img if img is not None else self.inline.get(name)
            if img is None:
                raise SystemExit(f"no picture for icon {name}")
            box = img.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
            self.pictures[name] = img.crop(box) if box else img
        return self.pictures[name]

    def en_text(self, key):
        v = self.en.get(key) or self.loc.get(key)
        return v.replace("\\n", "\n") if v else v


def text_renderer(R):
    """app_render's TextRenderer with a weight: SDF glyphs move their edge
    (positive bolder, negative thinner) and Hangul glyphs get a stroke."""
    from PIL import Image, ImageChops, ImageFont

    class Text(R.TextRenderer):
        weight = 0.0
        tt_stroke = 0.0

        def _glyph(self, canvas, S, font, it, pen, base, color, bold, clip, top):
            g = it["g"]
            m, r = g["m_Metrics"], g["m_GlyphRect"]
            p, s = font.pad, it["s"]
            ax0 = r["m_X"] - p
            ay0 = font.H - (r["m_Y"] + r["m_Height"]) - p
            aw, ah = r["m_Width"] + 2 * p, r["m_Height"] + 2 * p
            x0 = (pen + (m["m_HorizontalBearingX"] - p) * s) * S
            y0 = (top - (base + (m["m_HorizontalBearingY"] + p) * s)) * S
            gw, gh = aw * s * S, ah * s * S
            if gw < 1 or gh < 1:
                return
            crop = font.atlas[int(ay0) : int(ay0 + ah), int(ax0) : int(ax0 + aw)]
            if crop.size == 0:
                return
            im = Image.fromarray((crop * 255).astype(np.uint8), "L")
            big = im.resize((max(1, round(gw)), max(1, round(gh))), Image.BILINEAR)
            d = np.asarray(big).astype(np.float32) / 255.0
            edge = 0.5 - self.weight - (0.07 if bold else 0.0)
            a = np.clip((d - edge) * (2.0 * p * s * S) + 0.5, 0, 1)
            layer = np.zeros((big.size[1], big.size[0], 4), np.float32)
            layer[..., :3] = color[:3]
            layer[..., 3] = a * color[3]
            tile = Image.fromarray((layer * 255).astype(np.uint8), "RGBA")
            R.composite(canvas, tile, round(x0), round(y0), clip, S, top)

        def _ttf(self, canvas, S, it, pen, base, color, clip, top):
            f = ImageFont.truetype(
                self.cur_fallback or self.fallback_path, max(1, round(it["px"] * S))
            )
            sw = max(0, round(self.tt_stroke * S))
            asc, _ = f.getmetrics()
            x0, y0, x1, y1 = f.getbbox(it["ch"], stroke_width=sw)
            ox, oy = -min(0, x0), -min(0, y0)
            im = Image.new("L", (max(1, x1 + ox), max(1, y1 + oy)), 0)
            # a stroked mask holds only the outline: lay the glyph under it
            fx0, fy0, _fx1, _fy1 = f.getbbox(it["ch"])
            fill = f.getmask(it["ch"], mode="L")
            im.paste(Image.frombytes("L", fill.size, bytes(fill)), (fx0 + ox, fy0 + oy))
            if sw:
                ring = f.getmask(it["ch"], mode="L", stroke_width=sw)
                outline = Image.new("L", im.size, 0)
                outline.paste(
                    Image.frombytes("L", ring.size, bytes(ring)), (x0 + ox, y0 + oy)
                )
                im = ImageChops.lighter(im, outline)
            rgba = Image.new("RGBA", im.size, tuple(int(c * 255) for c in color[:3]))
            rgba.putalpha(im.point(lambda v: int(v * color[3])))
            R.composite(
                canvas,
                rgba,
                round(pen * S) - ox,
                round((top - base) * S - asc) - oy,
                clip,
                S,
                top,
            )

    return Text


# ---------------------------------------------------------------- texts
SPRITE = re.compile(r'<sprite name="?([^">]+)"?>')


def normalize(text):
    """App or table markup -> paragraphs split by "\\n", sprites unified,
    size and line-breaking tags dropped (the layout sets sizes)."""
    t = (text or "").replace("\\n", "\n").replace("\r", "")
    t = re.sub(r"<br\s*/?>", "\n", t)
    t = re.sub(r"</?(?:size|nobr|line-height|voffset)[^>]*>", "", t)
    t = SPRITE.sub(lambda m: f'<sprite name="{m.group(1)}">', t)
    t = t.replace("\xa0", " ")
    paras = [re.sub(r"[ \t]+", " ", p).strip() for p in t.split("\n")]
    return "\n".join(p for p in paras if p)


def korean_markup(text):
    """display.leaders_ko text -> sprite markup ({spice:1} -> Spice_1)."""

    def token(m):
        name, count = m.group(1), m.group(2)
        sprite = KO_TOKENS[name]
        return (
            f'<sprite name="{sprite}_{count}">'
            if count
            else (f'<sprite name="{sprite}">')
        )

    t = re.sub(r"\{([a-z_]+)(?::(\d+))?\}", token, text)
    t = t.replace("→", '<sprite name="IfThenArrow">')
    return re.sub(r"(공개 차례:)", r"<b>\1</b>", t)


def relayout(text, breaks):
    """Insert printed breaks before anchors; only whitespace may change."""
    out = text
    for anchor, brk in breaks:
        i = out.find(anchor)
        if i < 0 or out.find(anchor, i + 1) >= 0:
            raise SystemExit(f"break anchor {anchor!r} not found once in {out!r}")
        j = i
        while j > 0 and out[j - 1] == " ":
            j -= 1
        out = out[:j] + brk + out[i:]
    if re.sub(r"\s", "", out) != re.sub(r"\s", "", text):
        raise SystemExit(f"relayout changed words: {text!r}")
    return out


def face_texts(inp, cid, lang):
    """{name, house, ability_title, ability, signet_title, signet, (limited)}."""
    from dune_imperium.display.leaders_ko import LEADER_FACE_TEXTS_KO
    from dune_imperium.display.names_ko import KOREAN_CARD_NAMES

    loc = APP_IDS[cid][1]
    spec = LEADERS[cid]
    key = f"worm.leader.{loc}"
    signet_key = f"{key}.signetability.desc"
    if f"{signet_key}.modified" in inp.loc:
        # Staban: the variant whose line breaks match the card
        signet_key += ".modified"
    if lang == "en":
        out = {
            "name": inp.entries[cid]["name"],
            "house": inp.en_text(f"worm.leader.house.{spec['house']}")
            if spec["house"]
            else None,
            "ability_title": inp.en_text(f"{key}.staticability.title"),
            "ability": normalize(inp.en_text(f"{key}.staticability.desc")),
            "signet_title": inp.en_text(f"{key}.signetability.title"),
            "signet": normalize(inp.en_text(signet_key)),
            "tabs": TABS_EN,
        }
        if inp.loc.get(f"{key}.staticability.title2"):
            out["limited_title"] = inp.en_text(f"{key}.staticability.title2")
            out["limited"] = normalize(inp.en_text(f"{key}.staticability.desc2"))
    else:
        ko = LEADER_FACE_TEXTS_KO.get(cid)
        name = KOREAN_CARD_NAMES["leaders"].get(cid)
        if ko is None or name is None:
            return None
        out = {
            "name": name,
            "house": HOUSE_KO[spec["house"]] if spec["house"] else None,
            "ability_title": ko.ability_name,
            "ability": normalize(korean_markup(ko.ability_text)),
            "signet_title": ko.signet_name,
            "signet": normalize(korean_markup(ko.signet_text)),
            "tabs": TABS_KO,
        }
        for note in ko.notes:
            title, _, body = note.partition(":")
            out["limited_title"] = title.strip()
            out["limited"] = normalize(korean_markup(body.strip()))
    if lang == "en":
        # the print's box titles and texts set a typographic apostrophe
        for key in ("ability_title", "ability", "signet_title", "signet"):
            out[key] = re.sub(r"(?<=\w)'(?=\w)", "\u2019", out[key])
    for box in ("ability", "signet", "limited"):
        if box in out and (lang, cid, box) in BREAKS:
            out[box] = relayout(out[box], BREAKS[(lang, cid, box)])
    return out


# ---------------------------------------------------------------- drawing
class Painter:
    """A 2x RGBA canvas with text runs (app SDF fonts, Hangul from the Korean
    edition's face) and icons placed by baseline or centre, in card pixels."""

    def __init__(self, inp, lang, size=(W, H)):
        from PIL import Image

        self.inp, self.lang, self.tx = inp, lang, inp.text
        self.h = size[1]
        self.canvas = Image.new("RGBA", (size[0] * SS, size[1] * SS), (0, 0, 0, 0))

    def style(self, **kw):
        from app_cards import KOREAN_FONT, KOREAN_FONT_BOLD

        st = {
            "font": "Gotham-Medium SDF",
            "size": 30.0,
            "color": COLORS["body"],
            "spacing": 0.0,
            "weight": 0.0,
            "upper": False,
            "bold": False,
            "ko_spacing": KO_BODY_SPACING,
            "ko_stroke": 0.0,
            "squeeze": 1.0,
        }
        st.update(kw)
        st["korean"] = self.lang == "ko"
        st["ko_face"] = str(KOREAN_FONT_BOLD if st["bold"] else KOREAN_FONT)
        if st["bold"] and not st["korean"]:
            st["font"] = "Gotham-Bold SDF"
        return st

    def _tmp(self, st):
        c = st["color"]
        return {
            "m_fontAsset": "MonoBehaviour:" + st["font"],
            "m_fontSize": st["size"],
            "m_fontSizeMin": st["size"],
            "m_fontSizeMax": st["size"],
            "m_enableAutoSizing": 0,
            "m_fontStyle": 16 if st["upper"] else 0,
            "m_HorizontalAlignment": 1,
            "m_VerticalAlignment": 256,
            "m_characterSpacing": st["ko_spacing"] if st["korean"] else st["spacing"],
            "m_lineSpacing": 0.0,
            "m_paragraphSpacing": 0.0,
            "m_fontColor": [c[0] / 255, c[1] / 255, c[2] / 255, 1.0],
            "_fallback": st["ko_face"],
            "_force_tt": st["korean"],
        }

    def _prepare(self, st):
        tmp = self._tmp(st)
        self.tx.cur_fallback = tmp["_fallback"]
        self.tx.force_tt = tmp["_force_tt"]
        self.tx.weight = st["weight"]
        self.tx.tt_stroke = st["ko_stroke"] if st["korean"] else 0.0
        return tmp

    def _fit(self, text, st):
        tmp = self._prepare(st)
        return self.tx.fit(
            text,
            st["font"],
            99999,
            99999,
            st["size"],
            st["size"],
            st["size"],
            False,
            upper=st["upper"],
            char_spacing=tmp["m_characterSpacing"],
        )

    def width(self, text, st):
        if not text.strip():
            return self.space(st) * len(text)
        w = self._fit(text, st)[2]
        trailing = len(text) - len(text.rstrip(" "))
        return (w + trailing * self.space(st)) * st["squeeze"]

    def space(self, st):
        return self._fit("x x", st)[2] - self._fit("xx", st)[2]

    def run(self, x, baseline, text, st):
        """Draw one line of text with its baseline at `baseline`."""
        if not text.strip():
            return
        _s, lines, w, _h = self._fit(text, st)
        if st["squeeze"] != 1.0:
            # the print's narrower letters: drawn apart, then pressed sideways
            from PIL import Image

            pad, th = 8, st["size"] * 2.2
            sub = Painter(self.inp, self.lang, (round(w + 2 * pad), round(th)))
            sub.run(pad, st["size"] * 1.5, text, dict(st, squeeze=1.0))
            k = st["squeeze"]
            im = sub.canvas.resize(
                (max(1, round(sub.canvas.width * k)), sub.canvas.height), Image.LANCZOS
            )
            blit(
                self.canvas, im, (x - pad * k) * SS, (baseline - st["size"] * 1.5) * SS
            )
            return
        top = baseline - lines[0]["base"]
        tmp = self._prepare(st)
        rect = (x, self.h - top - 600, 99999, 600)
        self.tx.draw(self.canvas, SS, rect, text, tmp, None, self.h)

    def icon_size(self, name, h):
        img = self.inp.icon(name)
        h *= ICON_SCALE.get(name, 1.0)
        return h * img.width / img.height, h

    def icon(self, name, cx, cy, h):
        from PIL import Image

        img = self.inp.icon(name)
        w, h = self.icon_size(name, h)
        im = img.resize((max(1, round(w * SS)), max(1, round(h * SS))), Image.LANCZOS)
        blit(self.canvas, im, (cx - w / 2) * SS, (cy - h / 2) * SS)

    def picture(self, img, cx, cy, w):
        from PIL import Image

        h = w * img.height / img.width
        im = img.resize((round(w * SS), round(h * SS)), Image.LANCZOS)
        blit(self.canvas, im, (cx - w / 2) * SS, (cy - h / 2) * SS)


# -- a box of print-style text
SEPARATOR = re.compile(r"^\s*[—-]+\s*\S+\s*[—-]+\s*$")


def parse_line(markup):
    """[{"kind": "text", "text", "bold"} | {"kind": "icon", "name"}]."""
    items, bold = [], False
    for part in re.split(r"(<sprite name=\"[^\"]+\">|</?b>)", markup):
        if not part:
            continue
        if part == "<b>":
            bold = True
        elif part == "</b>":
            bold = False
        elif part.startswith("<sprite"):
            items.append({"kind": "icon", "name": SPRITE.match(part).group(1)})
        else:
            items.append({"kind": "text", "text": part, "bold": bold})
    return items


def words(items):
    return [
        w
        for it in items
        if it["kind"] == "text"
        for w in re.findall(r"[A-Za-z가-힣]{2,}", it["text"])
    ]


class Box:
    """One printed text box: paragraphs ("\\n") of lines (LINE).

    A paragraph is an icon row (icons and at most two words, one line: big
    icons, small words between), or text lines with icons in the text at
    `inline` ems and, when the paragraph ends in icons, those icons big to
    the right of the text (centred on it). Paragraphs stack centred in the
    box; text shrinks if a line is too wide or the box too full."""

    def __init__(self, painter, text, rect, opts):
        if opts.get("join"):
            text = text.replace("\n", " ")
        rect = (opts.get("x0", rect[0]), rect[1], opts.get("x1", rect[2]), rect[3])
        self.p, self.text, self.rect, self.o = painter, text, rect, opts

    def para_opts(self, i):
        o = dict(self.o)
        o.update(self.o.get("paras", {}).get(i, {}))
        return o

    def plan(self, k):
        paras = []
        for i, para in enumerate(self.text.split("\n")):
            o = self.para_opts(i)
            lines = [parse_line(line.strip()) for line in para.split(LINE)]
            flat = [it for ln in lines for it in ln]
            note = bool(re.match(r"\s*\(\*", para))
            size = o["size"] * k * (0.64 if note else 1.0)
            st = self.p.style(size=size, squeeze=o.get("squeeze", 1.0))
            st["sep"] = o.get("sep", 0.62)
            icons = [it for it in flat if it["kind"] == "icon"]
            if len(lines) == 1 and icons and (len(words(flat)) <= 2 or o.get("row")):
                paras.append(self.plan_row(lines[0], o, k, i))
                continue
            trail = []
            last = lines[-1]
            while last and (
                last[-1]["kind"] == "icon"
                or (last[-1]["kind"] == "text" and not last[-1]["text"].strip())
            ):
                it = last.pop()
                if it["kind"] == "icon":
                    trail.insert(0, it["name"])
            if trail and (len(words(flat)) < 3 or o.get("trail") is False):
                last += [{"kind": "icon", "name": n} for n in trail]
                trail = []
            widths = [self.line_width(ln, st, o) for ln in lines]
            block_w = max(widths)
            icon_h = o["icon"] * k
            trail_w = sum(self.p.icon_size(n, icon_h)[0] for n in trail) + 6 * max(
                0, len(trail) - 1
            )
            pitch = size * o["pitch"]
            height = size * 0.74 + pitch * (len(lines) - 1) + size * 0.2
            paras.append(
                {
                    "kind": "text",
                    "lines": lines,
                    "widths": widths,
                    "st": st,
                    "o": o,
                    "note": note,
                    "trail": trail,
                    "icon_h": icon_h,
                    "w": block_w + (o.get("trail_gap", 30) + trail_w if trail else 0),
                    "block_w": block_w,
                    "h": max(height, icon_h if trail else 0),
                    "text_h": height,
                    "pitch": pitch,
                }
            )
        return paras

    def plan_row(self, line, o, k, i):
        icon_h = o["icon"] * k
        size = o["size"] * k * o.get("row_text", 1.0)
        items = []
        pieces = []
        for it in line:
            if it["kind"] == "text":
                # a separator ("-AND-") stands apart from the words around it
                for part in re.split(r"([—-]+\s*\S+?\s*[—-]+)", it["text"]):
                    pieces.append({**it, "text": part})
            else:
                pieces.append(it)
        for it in pieces:
            if it["kind"] == "icon":
                w, h = self.p.icon_size(it["name"], icon_h)
                items.append({**it, "w": w, "h": h})
            elif it["text"].strip():
                sep = bool(SEPARATOR.match(it["text"]))
                st = self.p.style(
                    size=size * (o.get("sep", 0.62) if sep else 1.0),
                    bold=it["bold"],
                    squeeze=o.get("squeeze", 1.0),
                )
                txt = it["text"].strip()
                items.append({**it, "text": txt, "st": st, "w": self.p.width(txt, st)})

        def gap(a, b):
            if a.get("text", "").endswith(":") and len(a["text"]) == 1:
                return o.get("colon_gap", 4)  # Staban's rows open up after ":"
            if min(len(a.get("text", "xxx")), len(b.get("text", "xxx"))) <= 1:
                return 4
            return o.get("row_gap", 12)

        gaps = [gap(a, b) for a, b in zip(items, items[1:], strict=False)]
        label = None
        if o.get("label_above"):
            # "If you have an Alliance:" printed small above the icon after it
            for j, it in enumerate(items):
                if (
                    it["kind"] == "text"
                    and it["text"].endswith(":")
                    and j + 1 < len(items)
                ):
                    label = (j, it)  # the icon after it moves into its place
                    items.pop(j)
                    gaps.pop(min(j, len(gaps) - 1))
                    it["st"] = self.p.style(size=o["size"] * k * o.get("label", 0.8))
                    it["w"] = self.p.width(it["text"], it["st"])
                    # the icon sits centred under its label
                    items[j]["slot"] = max(items[j]["w"], it["w"])
                    break
        w = sum(it.get("slot", it["w"]) for it in items) + sum(gaps)
        return {
            "kind": "row",
            "items": items,
            "gaps": gaps,
            "w": w,
            "h": icon_h,
            "o": o,
            "label": label,
            "text_h": icon_h,
        }

    def line_width(self, items, st, o):
        w = 0.0
        for it in items:
            if it["kind"] == "icon":
                w += self.p.icon_size(it["name"], st["size"] * o["inline"])[0]
                w += 0.12 * st["size"]
            else:
                w += self.p.width(it["text"], self.text_style(it, st))
        return w

    def text_style(self, it, st):
        sep = SEPARATOR.match(it["text"])
        size = st["size"] * (st.get("sep", 0.62) if sep else 1.0)
        out = self.p.style(size=size, bold=it["bold"], squeeze=st["squeeze"])
        out["sep"] = st.get("sep", 0.62)
        return out

    def fit(self):
        x0, y0, x1, y1 = self.rect
        k = 1.0
        for _ in range(40):
            paras = self.plan(k)
            gap = self.o.get("gap", 12) * k
            total = sum(p["h"] for p in paras) + gap * max(0, len(paras) - 1)
            wide = any(p["w"] > self.room(p) + 1 for p in paras)
            if total <= y1 - y0 + 1 and not wide:
                break
            k *= 0.97
        if DEBUG and k < 1:
            print(
                "  shrink",
                round(k, 3),
                "total",
                round(total),
                "room h",
                y1 - y0,
                [(round(p["w"]), round(self.room(p))) for p in paras],
            )
        return paras, total, gap

    def room(self, para):
        x0, _y0, x1, _y1 = self.rect
        o = para["o"]
        return x1 - (o.get("x0", x0) if o["align"] == "left" else x0)

    def draw(self):
        x0, y0, x1, y1 = self.rect
        paras, total, gap = self.fit()
        y = y0 + (y1 - y0 - total) / 2 + self.o.get("dy", 0)
        trail_note = None
        for para in paras:
            o = para["o"]
            if o["align"] == "left":
                px = o.get("x0", x0)
            elif para.get("trail") and o.get("trail_cx"):
                px = o.get("cx", (x0 + x1) / 2) - para["block_w"] / 2  # text alone
            else:
                px = o.get("cx", (x0 + x1) / 2) - para["w"] / 2
            if para["kind"] == "row":
                self.draw_row(para, px, y + para["h"] / 2)
            else:
                if para["note"]:
                    px = o.get("x0", x0) + o.get("note_indent", 0)
                self.draw_text(para, px, y)
                if para["trail"] and o.get("trail_over_notes"):
                    trail_note = (para, px, y)
            y += para["h"] + gap
        if trail_note:
            # the big icon centred on the whole box (Gurney's footnote under it)
            para, px, _y = trail_note
            cy = y0 + (y1 - y0) / 2 + self.o.get("dy", 0)
            self.draw_trail(
                para, px + para["block_w"] + para["o"].get("trail_gap", 30), cy
            )

    def draw_row(self, row, px, cy):
        centres = []
        for j, it in enumerate(row["items"]):
            slot = it.get("slot", it["w"])
            centres.append(px + slot / 2)
            if it["kind"] == "icon":
                self.p.icon(it["name"], px + slot / 2, cy, row["h"])
            else:
                self.p.run(px, cy + 0.36 * it["st"]["size"], it["text"], it["st"])
            px += slot + (row["gaps"][j] if j < len(row["gaps"]) else 0)
        if row["label"]:
            j, it = row["label"]
            self.p.run(
                centres[j] - it["w"] / 2, cy - row["h"] / 2 - 18, it["text"], it["st"]
            )

    def draw_text(self, para, px, top):
        st, o = para["st"], para["o"]
        y_text = top + (para["h"] - para["text_h"]) / 2
        baseline = y_text + st["size"] * 0.74
        for ln, lw in zip(para["lines"], para["widths"], strict=False):
            x = px + ((para["block_w"] - lw) / 2 if o.get("lines") == "center" else 0)
            for it in ln:
                if it["kind"] == "icon":
                    h = st["size"] * o["inline"]
                    w, _ = self.p.icon_size(it["name"], h)
                    x += 0.06 * st["size"]
                    self.p.icon(it["name"], x + w / 2, baseline - 0.36 * st["size"], h)
                    x += w + 0.06 * st["size"]
                else:
                    ts = self.text_style(it, st)
                    self.p.run(x, baseline, it["text"], ts)
                    x += self.p.width(it["text"], ts)
            baseline += para["pitch"]
        if para["trail"] and not o.get("trail_over_notes"):
            self.draw_trail(
                para, px + para["block_w"] + o.get("trail_gap", 30), top + para["h"] / 2
            )

    def draw_trail(self, para, x, cy):
        if para["o"].get("trail_cx"):
            # the print sets a box's big icon at one place in both languages
            w = sum(self.p.icon_size(n, para["icon_h"])[0] for n in para["trail"])
            x = para["o"]["trail_cx"] - (w + 6 * (len(para["trail"]) - 1)) / 2
        for n in para["trail"]:
            w, _h = self.p.icon_size(n, para["icon_h"])
            self.p.icon(n, x + w / 2, cy, para["icon_h"])
            x += w + 6


def box_opts(cid, box, lang):
    o = dict(BOX_DEFAULTS[box])
    if lang == "ko":
        o.update(BOX_DEFAULTS_KO.get(box, {}))
    o.update(BOXES.get((cid, box), {}))
    o.update(BOXES.get((cid, box, lang), {}))
    return o


# -- the frame
def poly2x(pts):
    return [(x * SS, y * SS) for x, y in pts]


def octagon(cx, cy, r, turn=0.0):
    return [
        (
            cx + r * math.cos(math.radians(22.5 + 45 * i + turn)),
            cy + r * math.sin(math.radians(22.5 + 45 * i + turn)),
        )
        for i in range(8)
    ]


def hexagon(cx, cy, r):
    return [
        (
            cx + r * math.cos(math.radians(-90 + 60 * i)),
            cy + r * math.sin(math.radians(-90 + 60 * i)),
        )
        for i in range(6)
    ]


def dots(d, a, b, step=9.0, r=1.3, color=COLORS["dots"]):
    (ax, ay), (bx, by) = a, b
    n = max(1, int(math.hypot(bx - ax, by - ay) / step))
    for i in range(n + 1):
        x, y = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
        d.ellipse(
            ((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS),
            fill=color + (170,),
        )


def draw_frame(p, cid):
    from PIL import Image, ImageDraw

    lay = layout(cid)
    colors = {**COLORS, **FRAME_COLORS.get(cid, {})}
    d = ImageDraw.Draw(p.canvas)
    # name band and house band
    band_bottom = NAME_LINE_Y if lay["house"] else 128
    d.rectangle(
        (ART[0] * SS, ART[1] * SS, 1345 * SS, band_bottom * SS),
        fill=COLORS["band"] + (255,),
    )
    if lay["house"]:
        d.rectangle(
            (ART[0] * SS, (NAME_LINE_Y - 1) * SS, 1345 * SS, (NAME_LINE_Y + 1) * SS),
            fill=COLORS["name_line"] + (255,),
        )
        d.polygon(poly2x(HOUSE_BAND), fill=COLORS["band"] + (238,))
    # side tabs and their dotted edges
    d.polygon(poly2x(DISCARD_TAB), fill=colors["discard"] + (255,))
    d.polygon(poly2x(DECK_TAB), fill=colors["deck"] + (244,))
    dots(d, (1339, 36), (1339, 312))
    dots(d, (1341, 323), (1433, 415))
    dots(d, (34, 488), (126, 580))
    dots(d, (127, 590), (127, 770))
    # boxes: Staban's red box, the gold ability box, the black Signet box
    top = lay["gold_top"]
    if lay["red_top"]:
        rt = lay["red_top"]
        grad = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        t0 = rt + lay["red_title"]
        for y in range(t0 * SS, top * SS):
            f = (y / SS - t0) / max(1, top - t0)
            c = tuple(
                round(a + (b - a) * f)
                for a, b in zip(COLORS["red_top"], COLORS["red_bottom"], strict=False)
            )
            gd.line([(0, y), (W * SS, y)], fill=c + (255,))
        gd.rectangle((0, rt * SS, W * SS, t0 * SS), fill=COLORS["red_title"] + (255,))
        mask = Image.new("L", grad.size, 0)
        ImageDraw.Draw(mask).polygon(
            poly2x(
                (
                    (BOX_LEFT, rt),
                    (gold_edge(rt), rt),
                    (gold_edge(top), top),
                    (BOX_LEFT, top),
                )
            ),
            fill=255,
        )
        p.canvas.paste(grad, (0, 0), mask)
        d.line(
            [(BOX_LEFT * SS, (t0 + 1) * SS), (gold_edge(t0) * SS, (t0 + 1) * SS)],
            fill=COLORS["red_line"] + (255,),
            width=3 * SS // 2,
        )
    d.polygon(poly2x(gold_polygon(top)), fill=colors["gold"] + (250,))
    ty = top + lay["gold_title"]
    d.line(
        [(BOX_LEFT * SS, ty * SS), (gold_edge(ty) * SS, ty * SS)],
        fill=COLORS["gold_line"] + (255,),
        width=3 * SS // 2,
    )
    d.line(
        [(BOX_LEFT * SS, (ty + 2) * SS), (gold_edge(ty + 2) * SS, (ty + 2) * SS)],
        fill=COLORS["gold_hi"] + (110,),
        width=SS,
    )
    gtop = lay["red_top"] or top
    d.line(
        [
            (gold_edge(gtop) * SS, gtop * SS),
            (gold_edge(BOX_BOTTOM) * SS, BOX_BOTTOM * SS),
        ],
        fill=COLORS["edge_hi"] + (150,),
        width=2 * SS // 2,
    )
    st = lay["signet_top"]
    d.polygon(poly2x(signet_polygon(st)), fill=COLORS["signet"] + (255,))
    # the art shows between the box's dark corner wedge and the badge
    cx, cy = lay["octagon"]
    d.polygon(
        poly2x(
            (
                (signet_edge(st) + 56, st),
                (cx, st),
                (cx, cy),
                (signet_edge(st + 46), st + 46),
            )
        ),
        fill=(0, 0, 0, 0),
    )
    d.line(
        [(signet_edge(st) * SS, st * SS), (ART[2] * SS, st * SS)],
        fill=COLORS["signet_line"] + (200,),
        width=SS,
    )
    sy = st + lay["signet_title"]
    d.line(
        [(signet_edge(sy) * SS, sy * SS), (ART[2] * SS, sy * SS)],
        fill=COLORS["signet_line"] + (255,),
        width=3 * SS // 2,
    )
    d.line(
        [
            (signet_edge(st + 90) * SS, (st + 90) * SS),
            (signet_edge(BOX_BOTTOM) * SS, BOX_BOTTOM * SS),
        ],
        fill=COLORS["edge_hi"] + (170,),
        width=2 * SS // 2,
    )
    # the Signet badge: an octagon on the box's corner with the app's ring
    d.polygon(
        poly2x(octagon(cx, cy, 57, 4)),
        fill=(4, 4, 4, 255),
        outline=COLORS["octagon_line"] + (255,),
        width=3,
    )
    ring = p.inp.leader_picture(SIGNET_RING)
    p.picture(ring, cx + 1, cy, 89)
    # the small hexagon in the corner
    x, y, r = SET_MARK
    d.polygon(poly2x(hexagon(x, y, r)), fill=COLORS["set_mark"] + (255,))


# Header, tab and title type, measured on the scans and the Korean photos.
# spacing: TextMeshPro character spacing; squeeze: horizontal scale (the
# print's titles are narrower than the app's Gotham); weight: SDF edge shift.
TYPE = {
    "en": {
        "name": {"font": "Gotham-Medium SDF", "size": 55, "spacing": 16.0},
        "name_small": {"font": "Gotham-Medium SDF", "size": 47},
        "house": {
            "font": "Gotham-Book SDF",
            "size": 33,
            "spacing": 20.0,
            "upper": True,
        },
        "tab": {
            "font": "TrajanPro-Bold SDF",
            "size": 37,
            "spacing": 22.0,
            "weight": -0.07,
        },
        "title": {
            "font": "Gotham-Medium SDF",
            "size": 35,
            "spacing": 1.0,
            "upper": True,
            "squeeze": 0.89,
        },
    },
    "ko": {
        "name": {"size": 51, "bold": True, "ko_spacing": 18.0, "ko_stroke": 0.5},
        "house": {"size": 30.5, "ko_spacing": 22.0},
        "tab": {"size": 35, "ko_spacing": 20.0, "ko_stroke": 0.4},
        "title": {"size": 34, "bold": True},
    },
}


def type_style(p, kind, **kw):
    t = dict(TYPE[p.lang][kind])
    t.update(kw)
    return p.style(**t)


def draw_header(p, cid, texts):
    from PIL import ImageDraw

    spec = LEADERS[cid]
    d = ImageDraw.Draw(p.canvas)
    x = 50
    if spec.get("ring"):
        cx, cy, r = 68, 78, 17
        d.ellipse(
            ((cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS),
            outline=COLORS["ring"] + (255,),
            width=6 * SS,
        )
        x = 100
    baseline = 100 if cid != "staban_tuek" else 103
    end = x
    if p.lang == "ko":
        st = type_style(p, "name", color=COLORS["name"])
        tracking = st["ko_spacing"] * st["size"] / 100
        for word in texts["name"].split(" "):
            p.run(end + 4, baseline - 9, word, st)
            end += p.width(word, st) + p.space(st) + NAME_WORD_GAP["ko"]
        end -= p.space(st) + NAME_WORD_GAP["ko"] + tracking
    else:
        # small capitals: lower-case letters as smaller capitals
        big = type_style(p, "name", color=COLORS["name"])
        small = type_style(
            p,
            "name_small",
            color=COLORS["name"],
            spacing=big["spacing"] * big["size"] / TYPE["en"]["name_small"]["size"],
        )
        tracking = big["spacing"] * big["size"] / 100
        for word in texts["name"].split(" "):
            for part in re.findall(r"[a-z]+|[^a-z]+", word):
                st = small if part.islower() else big
                p.run(end, baseline, part.upper(), st)
                end += p.width(part.upper(), st)
            end += p.space(big) + NAME_WORD_GAP["en"]
        end -= p.space(big) + NAME_WORD_GAP["en"] + tracking
    hx = end + (46 if p.lang == "en" else 36) + 15
    for i in range(spec["hexes"]):
        d.polygon(
            poly2x(hexagon(hx + i * 55, 82, 17.5)),
            fill=COLORS["hex"] + (255,),
            outline=(150, 150, 146, 255),
            width=SS,
        )
    if texts["house"]:
        st = type_style(p, "house", color=COLORS["house"])
        p.run(
            50 if p.lang == "en" else 51,
            167 if p.lang == "en" else 159,
            texts["house"],
            st,
        )


def draw_tabs(p, texts):
    from PIL import Image

    for word, (cx, cy), angle in (
        (texts["tabs"]["discard"], TAB_CENTRES[p.lang][0], 90),
        (texts["tabs"]["deck"], TAB_CENTRES[p.lang][1], -90),
    ):
        sub = Painter(p.inp, p.lang, (420, 80))
        st = type_style(sub, "tab", color=COLORS["tab_text"])
        w = sub.width(word, st)
        if p.lang == "en":
            w -= st["spacing"] * st["size"] / 100
        sub.run((420 - w) / 2, 54, word, st)
        turned = sub.canvas.rotate(angle, expand=True, resample=Image.BICUBIC)
        blit(p.canvas, turned, cx * SS - turned.width / 2, cy * SS - turned.height / 2)


def draw_titles(p, cid, texts):
    lay = layout(cid)
    for key, x, baseline, max_w in (
        ("ability_title", 143, lay["gold_top"] + lay["gold_base"], 520),
        (
            "signet_title",
            lay["signet_x"],
            lay["signet_top"] + lay["signet_base"],
            1430 - lay["signet_x"],
        ),
        ("limited_title", 143, (lay.get("red_top") or 0) + lay.get("red_base", 0), 440),
    ):
        if not texts.get(key):
            continue
        st = type_style(p, "title", color=COLORS["title"])
        while p.width(texts[key], st) > max_w and st["size"] > 20:
            st = dict(st, size=st["size"] - 0.5)
        if p.lang == "ko":
            baseline -= 4 + KO_TITLE_RAISE.get(cid, 0)
        p.run(x - 3, baseline, texts[key], st)


def blit(canvas, im, x, y):
    """alpha_composite at (x, y), clipped to the canvas."""
    x, y = round(x), round(y)
    left, top = max(0, -x), max(0, -y)
    right = min(im.width, canvas.width - x)
    bottom = min(im.height, canvas.height - y)
    if right > left and bottom > top:
        canvas.alpha_composite(im.crop((left, top, right, bottom)), (x + left, y + top))


def draw_boxes(p, cid, texts):
    lay = layout(cid)
    gt, st = lay["gold_top"], lay["signet_top"]
    rects = {
        "ability": (141, gt + lay["gold_title"] + 6, 720, BOX_BOTTOM - 6),
        "signet": (881, st + lay["signet_title"] + 6, 1430, BOX_BOTTOM - 6),
    }
    if lay["red_top"]:
        rects["limited"] = (142, lay["red_top"] + lay["red_title"] + 6, 640, gt - 6)
    for box, rect in rects.items():
        if texts.get(box):
            Box(p, texts[box], rect, box_opts(cid, box, p.lang)).draw()


# -- Feyd's Training track
def track_px(box):
    left, top, w, h = box
    return (left * W / 100, top * H / 100, (left + w) * W / 100, (top + h) * H / 100)


TRACK_ICONS = {  # space -> [(icon, x offset from the box centre, height)]
    "paid_trash": [
        ("Solari_1", -62, 64),
        ("IfThenArrow", 5, 64),
        ("TrashCard", 63, 66),
    ],
    "first_spy": [("Spy", 0, 62)],
    "mid_trash": [("TrashCard", 0, 66)],
    "late_trash": [("TrashCard", 0, 66)],
    "second_spy": [("Spy", 0, 62)],
    "double_spice": [("Spice_2", 0, 64)],
    "final": [("Troop", 11, 62), ("Spy", 70, 58)],
}
TRACK_LINKS = (  # (from, to, y offset of the link from the source box centre)
    ("start", "paid_trash", -37),
    ("start", "first_spy", 33),
    ("paid_trash", "mid_trash", 15),
    ("first_spy", "mid_trash", -7),
    ("mid_trash", "late_trash", -41),
    ("mid_trash", "second_spy", 39),
    ("second_spy", "double_spice", 2),
    ("late_trash", "final", -5),
    ("double_spice", "final", 6),
)


def draw_track(p):
    """Feyd's Training track exactly at leader_layout.FEYD_TRACK_BOXES, so the
    play UI's token lands on the printed spaces."""
    from PIL import ImageDraw

    from dune_imperium.display.leader_layout import FEYD_TRACK_BOXES

    d = ImageDraw.Draw(p.canvas)
    boxes = {k: track_px(v) for k, v in FEYD_TRACK_BOXES.items()}
    # the final space: a plate with a blunt point towards the track
    x0, y0, x1, y1 = boxes["final"]
    cy, right = (y0 + y1) / 2, ART[2]
    outer = [(x0, cy), (x0 + 47, y0), (right, y0), (right, y1), (x0 + 47, y1)]
    inner = [
        (x0 + 21, cy),
        (x0 + 59, y0 + 27),
        (right, y0 + 27),
        (right, y1 - 27),
        (x0 + 59, y1 - 27),
    ]

    def plate_edge(y):
        """x of the plate's pointed left side at height y."""
        return x0 + 47 * abs(y - cy) / (cy - y0)

    for a, b, dy in TRACK_LINKS:
        ax0, ay0, ax1, ay1 = boxes[a]
        bx0, by0, bx1, by1 = boxes[b]
        y = (ay0 + ay1) / 2 + dy
        y = min(max(y, by0 + 14), by1 - 14)
        end = plate_edge(y) if b == "final" else bx0
        d.rounded_rectangle(
            ((ax1 - 4) * SS, (y - 4) * SS, (end + 4) * SS, (y + 4) * SS),
            radius=4 * SS,
            fill=(236, 238, 240, 255),
        )
    for k, (bx0, by0, bx1, by1) in boxes.items():
        if k == "final":
            continue
        d.rounded_rectangle(
            (bx0 * SS, by0 * SS, bx1 * SS, by1 * SS),
            radius=17 * SS,
            fill=(13, 19, 30, 245),
            outline=(96, 106, 118, 255),
            width=3 * SS,
        )
    # the start square
    bx0, by0, bx1, by1 = boxes["start"]
    scx, scy = (bx0 + bx1) / 2, (by0 + by1) / 2
    d.rectangle(
        ((scx - 20) * SS, (scy - 20) * SS, (scx + 20) * SS, (scy + 20) * SS),
        fill=(52, 57, 63, 255),
    )
    d.polygon(poly2x(outer), fill=(16, 24, 38, 255))
    d.line(
        poly2x([outer[2], outer[1], outer[0], outer[4], outer[3]]),
        fill=(96, 106, 118, 255),
        width=4 * SS,
        joint="curve",
    )
    d.polygon(poly2x(inner), fill=(132, 147, 178, 255))
    # the light area's dark teeth along its edge
    for a, b in zip(inner, inner[1:] + inner[:1], strict=False):
        if a[0] < right - 1 or b[0] < right - 1:
            dots(d, a, b, step=7.0, r=2.2, color=(16, 24, 38))
    for k, icons in TRACK_ICONS.items():
        x0, y0, x1, y1 = boxes[k]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if k == "final":
            cx = x0 + 40  # the icons sit in the plate's point
        for name, dx, h in icons:
            p.icon(name, cx + dx, cy, h)


# -- the art
def art_layer(inp, cid):
    """The app's background scaled into place (its uncovered edges carried
    out and blurred), the cut-out figure over it, the topographic lines."""
    from PIL import Image, ImageFilter

    sprite_id = APP_IDS[cid][0]
    pl = PLACEMENT[cid]
    bg = inp.leader_picture(BACKGROUND.format(sprite_id)).convert("RGB")
    s, x, y = pl["background"]
    bw, bh = round(bg.width * s), round(bg.height * s)
    big = np.asarray(bg.resize((bw, bh), Image.LANCZOS))
    pad = ((max(0, y), max(0, H - (y + bh))), (max(0, x), max(0, W - (x + bw))), (0, 0))
    full = np.pad(big, pad, mode="edge")
    ox, oy = pad[1][0] - x, pad[0][0] - y
    full = full[oy : oy + H, ox : ox + W]
    covered = np.zeros((H, W), np.uint8)
    covered[max(0, y) : y + bh, max(0, x) : x + bw] = 255
    # where the app's picture stops short of the window (Lady Margot's left
    # strip) its edge is carried out, blurred, and darkened like the print's
    soft = Image.fromarray(full).filter(ImageFilter.GaussianBlur(10))
    soft = Image.eval(soft, lambda v: int(v * UNCOVERED_SHADE))
    keep = Image.fromarray(covered).filter(ImageFilter.GaussianBlur(14))
    art = Image.composite(Image.fromarray(full), soft, keep).convert("RGBA")
    fig = inp.leader_picture(FIGURE.format(sprite_id))
    s, fx, fy = pl["figure"]
    fw, fh = round(fig.width * s), round(fig.height * s)
    fig = fig.resize((fw, fh), Image.LANCZOS)
    if cid in EXTEND_FIGURE_BOTTOM and fy + fh < BOX_BOTTOM:
        fig = extend_bottom(fig, BOX_BOTTOM - (fy + fh) + 4)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    layer.paste(fig, (fx, fy), fig)
    art.alpha_composite(layer)
    topo = inp.leader_picture(TOPO_LINES)
    topo = topo.resize((W, round(topo.height * W / topo.width)), Image.LANCZOS)
    alpha = np.asarray(topo.getchannel("A"), float)[:H] * TOPO_ALPHA
    lines = np.zeros((H, W, 4), np.uint8)
    lines[..., :3] = 235
    lines[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)
    art.alpha_composite(Image.fromarray(lines, "RGBA"))
    return art


def extend_bottom(fig, rows, band=48):
    """Continue a cut-out that ends in a hard edge: its last `band` rows,
    mirrored back and forth, below it. The cloth's texture goes on; repeating
    one row draws streaks, and a taller band brings Staban's hand down too."""
    from PIL import Image, ImageFilter, ImageOps

    a = np.asarray(fig)
    filled = np.where(a[..., 3].max(1) > 200)[0]
    last = int(filled.max()) if len(filled) else a.shape[0] - 1
    strip = fig.crop((0, max(0, last + 1 - band), fig.width, last + 1))
    out = Image.new("RGBA", (fig.width, last + 1 + rows), (0, 0, 0, 0))
    out.paste(fig.crop((0, 0, fig.width, last + 1)), (0, 0))
    # softened and shaded a little: it lies in the shadow between the boxes
    rgb = strip.convert("RGB").filter(ImageFilter.GaussianBlur(1.5))
    strip = Image.merge(
        "RGBA",
        (*Image.eval(rgb, lambda v: int(v * 0.85)).split(), strip.getchannel("A")),
    )
    y, flip = last + 1, True
    while y < out.height:
        out.paste(ImageOps.flip(strip) if flip else strip, (0, y))
        y += strip.height
        flip = not flip
    return out


# ---------------------------------------------------------------- render
def render_face(inp, cid, lang):
    from PIL import Image, ImageDraw

    texts = face_texts(inp, cid, lang)
    if texts is None:
        return None
    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shape = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shape).rounded_rectangle((0, 0, W - 1, H - 1), CORNER, fill=255)
    card.paste(Image.new("RGBA", (W, H), COLORS["card"] + (255,)), (0, 0), shape)
    art = art_layer(inp, cid)
    window = Image.new("L", (W, H), 0)
    ImageDraw.Draw(window).rectangle((ART[0], ART[1], ART[2] - 1, ART[3] - 1), fill=255)
    card.paste(art, (0, 0), window)
    p = Painter(inp, lang)
    draw_frame(p, cid)
    if LEADERS[cid].get("track"):
        draw_track(p)
    draw_header(p, cid, texts)
    draw_tabs(p, texts)
    draw_titles(p, cid, texts)
    draw_boxes(p, cid, texts)
    top = p.canvas.resize((W, H), Image.LANCZOS)
    card.alpha_composite(top)
    card.putalpha(
        Image.fromarray(np.minimum(np.asarray(card.getchannel("A")), np.asarray(shape)))
    )
    return card


def leader_ids(args):
    return [i for i in args.ids.split(",") if i] if args.ids else list(APP_IDS)


def face_path(inp, cid, lang, root=None):
    rel = Path(inp.entries[cid]["path"]).with_suffix(".webp")
    return (Path(root) if root else CARDS / "app") / lang / rel


def cmd_render(args):
    inp = Inputs()
    sources_path = CARDS / "app" / "leader_sources.json"
    doc = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    faces = doc.get("faces", {})
    for cid in leader_ids(args):
        sprite_id = APP_IDS[cid][0]
        source = {
            "figure": FIGURE.format(sprite_id),
            "background": BACKGROUND.format(sprite_id),
            "frame": [SIGNET_RING, TOPO_LINES],
            "placement": {k: list(v) for k, v in PLACEMENT[cid].items()},
            "path": Path(inp.entries[cid]["path"]).with_suffix(".webp").as_posix(),
            # the scans' size, which display.leader_layout's percentages assume
            "size": [W, H],
            "sha256": dict(faces.get(cid, {}).get("sha256", {})),
        }
        if LEADERS[cid].get("track"):
            from dune_imperium.display.leader_layout import FEYD_TRACK_BOXES

            # the boxes the Training track was drawn at (a test compares them
            # with the play UI's table: change one, re-render the face)
            source["track_boxes"] = {k: list(v) for k, v in FEYD_TRACK_BOXES.items()}
        for lang in args.lang.split(","):
            img = render_face(inp, cid, lang)
            if img is None:
                print(cid, lang, "skipped: no Korean card")
                source["sha256"].pop(lang, None)
                continue
            dest = face_path(inp, cid, lang, args.out)
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, "WEBP", quality=92, method=6)
            source["sha256"][lang] = hashlib.sha256(dest.read_bytes()).hexdigest()
            print(cid, lang, "->", dest, flush=True)
        faces[cid] = source
    if not args.out:
        sources_path.write_text(
            json.dumps(
                {"build_guid": build_guid(), "faces": dict(sorted(faces.items()))},
                indent=1,
                ensure_ascii=False,
            )
            + "\n"
        )


def cmd_compare(args):
    """Scan | app face, English and Korean, one sheet per leader."""
    from PIL import Image, ImageDraw

    inp = Inputs()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for cid in leader_ids(args):
        rows = []
        for lang in ("en", "ko"):
            scan = CARDS / lang / inp.entries[cid]["path"]
            face = face_path(inp, cid, lang, args.faces)
            if not scan.exists() and not face.exists():
                continue
            cells = []
            for name, path in ((f"scan {lang}", scan), (f"app {lang}", face)):
                if path.exists():
                    cells.append((name, Image.open(path).convert("RGBA")))
            rows.append(cells)
        h, pad, label = int(args.height), 10, 20
        width = (
            max(
                sum(round(im.width * h / im.height) + pad for _n, im in r) for r in rows
            )
            + pad
        )
        sheet = Image.new(
            "RGBA", (width, len(rows) * (h + label + pad) + pad), (44, 44, 52, 255)
        )
        d = ImageDraw.Draw(sheet)
        y = pad
        for r in rows:
            x = pad
            for name, im in r:
                im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
                d.text((x, y), f"{cid}: {name}", fill=(255, 230, 120, 255))
                sheet.alpha_composite(im, (x, y + label))
                x += im.width + pad
            y += h + label + pad
        sheet.convert("RGB").save(out / f"leader-{cid}.jpg", quality=90)
        print("sheet", out / f"leader-{cid}.jpg")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inputs")
    p.add_argument("--extra", nargs="*", help="further sprite names to save")
    p.add_argument("--measure", action="store_true", help="then print PLACEMENT")
    p.add_argument("--measure-only", action="store_true")
    p.add_argument("--ids", default="")
    p.set_defaults(fn=cmd_inputs)
    p = sub.add_parser("render")
    p.add_argument("--lang", default="en,ko")
    p.add_argument("--ids", default="", help="content ids (default: all ten)")
    p.add_argument("--out", help="write here instead of assets/cards/app")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("compare")
    p.add_argument("--ids", default="")
    p.add_argument("--out", required=True)
    p.add_argument("--faces", help="faces rendered with render --out DIR")
    p.add_argument("--height", default=700)
    p.set_defaults(fn=cmd_compare)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
