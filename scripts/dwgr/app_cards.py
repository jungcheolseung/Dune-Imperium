"""Card faces for the play UI, assembled from the Steam app's card templates.

The app keeps no finished card faces: it builds each card at run time from a
template prefab, the card's illustration, frame sprites, its icons and
TextMeshPro text. This draws the same thing offline (app_render.py) from the
inputs ``app_assets.py card-inputs`` left in the assets checkout's
``reference/dune-steam-app/<build-guid>/render/``:

- Uprising-era cards use the dynamic template ``UI_crd_Imperium_Dynamic``
  (``..._HasStatic`` when the card prints a "When this card is ..." line),
  filled from the app archetype (factions, Agent icons, cost; the public
  ``dune_imperium.agents.app_ai.data.archetypes``) and the app's English
  card strings (``card.imperium.<slug>.agent`` / ``.reveal`` / ``.static``).
- Text boxes follow the printed cards rather than the app where they differ
  (user decisions, 2026-10-07): the faction banner uses the title face in
  capitals, and icons that end or make up a text box are drawn large, beside
  the text, as on the card.
- Korean faces use the official Korean edition's words: card names from
  ``dune_imperium.display.names_ko``, card text from the private assets
  repository's ``cards/app/ko_text.json`` (read off the Korean retail cards);
  the app's own Korean translation is never used.

Output: ``assets/cards/app/<lang>/<manifest path>`` (WebP), next to the
scans the play UI already serves.

    uv run --with pillow python scripts/dwgr/app_cards.py render --ids tread_in_darkness
    uv run --with pillow python scripts/dwgr/app_cards.py render --all --lang en,ko
    uv run --with pillow python scripts/dwgr/app_cards.py compare --ids ... --out DIR
"""

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

import app_render as R
from PIL import Image

from dune_imperium.agents.app_ai import catalog
from dune_imperium.agents.app_ai.data.archetypes import ARCHETYPES
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.display.images import load_card_manifest
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES

REPO = Path(__file__).resolve().parents[2]
ASSETS = REPO / "assets"
STEAM_DATA = Path(
    "~/Library/Application Support/Steam/steamapps/common/Dune Imperium/"
    "DuneImperium.app/Contents/Resources/Data"
).expanduser()
# Korean faces: the retail cards print body text in a regular gothic and titles
# in a bold one; NanumBarunGothic at the text size matches both (checked against
# the photos).
KOREAN_FONT = Path("~/Library/Fonts/NanumBarunGothic.otf").expanduser()
KOREAN_FONT_BOLD = Path("~/Library/Fonts/NanumBarunGothicBold.otf").expanduser()
CANVAS = (556, 776)


def korean_face(latin_font):
    """The Korean face beside an app font: bold where the print sets the
    English in Gotham Medium (Intrigue, Conflict) or Interstate (labels),
    regular where it sets Gotham Book (the Imperium and Tleilaxu boxes)."""
    return (
        KOREAN_FONT_BOLD
        if re.search(r"Medium|Bold|Black|Interstate", latin_font or "")
        else KOREAN_FONT
    )


FACTIONS = {
    "Emperor": ("UI_crd_SubHeader_Emperor", "EMPEROR", "황제"),
    "SpacingGuild": (
        "UI_crd_SubHeader_SpacingGuild",
        "SPACING GUILD",
        "우주 항행 길드",
    ),
    "BeneGesserit": ("UI_crd_SubHeader_BeneGesserit", "BENE GESSERIT", "베네 게세리트"),
    "Fremen": ("UI_crd_SubHeader_Fremen", "FREMEN", "프레멘"),
}
AGENT_ICONS = {
    "Emperor": "UI_crd_ActionFaction_Emperor",
    "SpacingGuild": "UI_crd_ActionFaction_SpacingGuild",
    "BeneGesserit": "UI_crd_ActionFaction_BeneGesserit",
    "Fremen": "UI_crd_ActionFaction_Fremen",
    "Pentagon": "UI_crd_ActionAct_Landsraad",
    "Circle": "UI_crd_ActionAct_PopulationCenter",
    "Triangle": "UI_crd_ActionAct_Commerce",
    "Spy": "UI_crd_ActionFaction_Spy",
}
AGENT_FRAMES = [
    ("UI_crd_ActionFrame_S", 87),
    ("UI_crd_ActionFrame_M", 111),
    ("UI_crd_ActionFrame_L", 135),
    ("UI_crd_ActionFrame_XL", 161),
]
# Inline glyph -> the larger card-icon sprite of the same picture, for icons
# drawn big in print style.
HIRES = {
    "TrashCard": "UI_crd_ActionIcon_TrashCard",
    "DrawCard": "UI_crd_ActionIcon_DrawCard",
    "IntrigueCard": "UI_crd_ActionIcon_IntrigueCard",
    "Strength": "UI_crd_ActionIcon_Strength",
    "Spy": "UI_crd_ActionIcon_Spy",
    "RecallSpy": "UI_crd_ActionIcon_SpyRecall",
    "RecallAgent": "UI_crd_ActionIcon_AgentRecall",
    "SignetRing": "UI_crd_ActionIcon_SignetRing",
    "VictoryPoint": "UI_crd_ActionIcon_VictoryPoint",
    "Worm": "UI_crd_ActionIcon_Worm",
    "MakerHook": "UI_crd_ActionIcon_MakerHook",
    "Persuasion": "UI_crd_ActionIcon_Persuasion",
    "PlayAreaCard": "UI_crd_ActionIcon_PlayAreaCard",
    "IntrigueTrash": "UI_crd_ActionIcon_IntrigueTrash",
    "Trash an Intrigue": "UI_crd_ActionIcon_IntrigueTrash",
    "Discard": "UI_crd_Discard",
    "IfThenArrow": "UI_crd_CostIcon_IfThenArrow_Large",
    "EmperorRankUp": "UI_crd_ActionIcon_FactionEmperorUp",
    "SpacingGuildRankUp": "UI_crd_ActionIcon_FactionSpacingGuildUp",
    "BeneGesseritRankUp": "UI_crd_ActionIcon_FactionBeneGesseritUp",
    "FremenRankUp": "UI_crd_ActionIcon_FactionFremenUp",
    "EmperorRankUp2": "UI_crd_ActionIcon_FactionEmperorUp2",
    "SpacingGuildRankUp2": "UI_crd_ActionIcon_FactionSpacingGuildUp2",
    "BeneGesseritRankUp2": "UI_crd_ActionIcon_FactionBeneGesseritUp2",
    "FremenRankUp2": "UI_crd_ActionIcon_FactionFremenUp2",
    "WildRankUp": "UI_crd_ActionIcon_FactionWildUp",
    "WildRankUp2": "UI_crd_ActionIcon_FactionWildUp2",
    "WildRankDown": "UI_crd_ActionIcon_FactionWildDown",
}
SPRITE_TAG = r'<sprite name="?([^">]+)"?>'


# On-acquire bonus -> the picture the app's prefabs put under the cost.
ACQUIRE_ICONS = {
    "Troop": "UI_crd_ActionIcon_ResourceCube",
    "Water": "UI_crd_CostIcon_Water",
    "Research": "UI_crd_CostIcon_Research",
    "Dreadnought": "UI_crd_Icon_Dreadnought",
    "Freighter": "UI_Icon_crd_freighter",
    "VP": "UI_crd_ActionIcon_VictoryPoint",
    "RankE": "UI_crd_ActionIcon_FactionEmperorUp",
    "RankSG": "UI_crd_ActionIcon_FactionSpacingGuildUp",
    "RankBG": "UI_crd_ActionIcon_FactionBeneGesseritUp",
    "RankF": "UI_crd_ActionIcon_FactionFremenUp",
    "AnyRank": "UI_crd_ActionIcon_FactionWildUp",
    "Trash": "UI_crd_ActionIcon_TrashCard",
    "Intrigue": "UI_crd_ActionIcon_IntrigueCard",
    "PlaceSpy": "UI_crd_ActionIcon_Spy",
}
ACQUIRE_INLINE = {"Contract": "Contract", "Spice": "Spice_1", "Solari": "Solari_1"}
# Printed on-acquire bonuses the app archetype does not list (checked against the card).
ACQUIRE_OVERRIDES = {"arrakis_revolt": ("Troop",)}


def build_guid():
    for line in open(STEAM_DATA / "boot.config"):
        if line.startswith("build-guid="):
            return line.strip().split("=", 1)[1]
    raise SystemExit("no build-guid in boot.config")


def render_dir():
    return ASSETS / "reference" / "dune-steam-app" / build_guid() / "render"


# ---------------------------------------------------------------- specs
class Inputs:
    def __init__(self):
        rd = render_dir()
        if not (rd / "loc_en_US.json").exists():
            raise SystemExit("run `app_assets.py card-inputs` first")
        self.loc = json.loads((rd / "loc_en_US.json").read_text())
        self.prefab_dir = rd / "prefabs"
        self.sprites = R.Sprites(str(rd / "sprites"))
        self.inline = R.Sprites(str(rd / "inline"))
        self.inline.meta = {}
        assets = json.loads((rd / "fonts" / "sprite_assets.json").read_text())
        self.text = R.TextRenderer(
            str(rd / "fonts"), self.inline, assets, fallback_path=str(KOREAN_FONT)
        )
        self.art = {}
        for f in os.listdir(rd / "sprites"):
            if f.startswith("UI_ill_") and f.endswith(".png"):
                self.art.setdefault(f[7:-4].lower(), f[:-4])
        self.prefabs = {}
        for f in os.listdir(self.prefab_dir):
            m = re.match(r"UI_crd_(Imperium|Tleilaxu)_(.+)\.prefab\.json$", f)
            if m:
                self.prefabs[re.sub(r"[^a-z0-9]", "", m.group(2).lower())] = f
        # printed English where the app's wording differs, and the Korean edition's text
        en_path = ASSETS / "cards" / "app" / "en_text.json"
        ko_path = ASSETS / "cards" / "app" / "ko_text.json"
        self.en = json.loads(en_path.read_text()) if en_path.exists() else {}
        self.ko = json.loads(ko_path.read_text()) if ko_path.exists() else {}
        self.manifest = load_card_manifest(ASSETS / "cards" / "manifest.json")

    def tree(self, name):
        return json.loads((self.prefab_dir / name).read_text())

    def text_en(self, key):
        v = self.loc.get(key)
        return v.replace("\\n", "\n") if v else v


def imperium_spec(inp, content_id, catalog_kind="imperium"):
    short = catalog.CARD_ARCHETYPES[content_id]
    arch = ARCHETYPES[short]
    at = arch.attributes
    slug = at["Name"].rsplit(".", 1)[0]  # card.imperium.<slug>
    last = short.rsplit(".", 1)[1]
    art = inp.art.get(slug.rsplit(".", 1)[1]) or inp.art.get(last.lower())
    prefab = inp.prefabs.get(re.sub(r"[^a-z0-9]", "", last.lower()))
    path = next(
        (
            inp.manifest[(k, content_id)]
            for k in (catalog_kind, "other", "tleilaxu")
            if (k, content_id) in inp.manifest
        ),
        None,
    )
    return {
        "kind": "imperium",
        "id": content_id,
        "arch": short,
        "slug": slug,
        "prefab": prefab,
        "texts": prefab_texts(inp, prefab_text_nodes(inp.tree(prefab), prefab))
        if prefab
        else [],
        "title": {
            "en": inp.text_en(at["Name"]),
            "ko": KOREAN_CARD_NAMES["cards"].get(content_id),
        },
        "factions": list(at.get("FactionList", ())),
        "icons": list(at.get("IconList", ())),
        "infiltrate": list(at.get("InfiltrationIconList", ())),
        "cost": at.get("PersuasionCost"),
        "acquire": list(
            ACQUIRE_OVERRIDES.get(content_id, at.get("AcquireEffectList", ()))
        ),
        "choam": "CHOAMModule" in at.get("SetList", ()),
        "art": "UI_ill_" + art if art and not art.startswith("UI_ill_") else art,
        "agent": card_text(inp, slug, last, "agent"),
        "reveal": card_text(inp, slug, last, "reveal"),
        "static": card_text(inp, slug, last, "static"),
        "path": path,
    }


def text_key(inp, keys):
    """The card's own key: the first candidate the app or our tables know.

    Skirmish cards share a title key but each has its own reward keys, so the
    key must follow the text, not the title."""
    return next(
        (k for k in keys if k in inp.loc or k in inp.en or k in inp.ko), keys[0]
    )


def card_text(inp, slug, last, field):
    """English from the print overrides, else the app string (under the title's
    slug or the archetype's name); Korean from the Korean edition table."""
    keys = [f"{slug}.{field}", f"card.imperium.{last.lower()}.{field}"]
    en = next((inp.en[k] for k in keys if k in inp.en), None)
    if en is None:
        en = next((inp.text_en(k) for k in keys if inp.loc.get(k)), None)
    ko = next((inp.ko[k] for k in keys if k in inp.ko), None)
    return {"en": en, "ko": ko, "key": text_key(inp, keys)}


# -------------------------------------------------------- print-style text boxes
def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s)


SEPARATOR = re.compile(
    r"((?:<size=[^>]*>)?\s*[—-]+\s*(?:OR|AND|또는|그리고)\s*[—-]+\s*(?:</size>)?)"
)


def split_paragraphs(text):
    """Line breaks, plus a break after "-OR-"/"-AND-" when the clause after it
    opens with icons and goes on in words (printed on its own line)."""
    out = []
    for para in re.split(r"\n|<br>", text or ""):
        parts = SEPARATOR.split(para)
        cur = parts[0]
        for i in range(1, len(parts) - 1, 2):
            after = parts[i + 1]
            lead, rest = take_cluster(after.strip())
            if lead and len(words(rest)) >= 3:
                out.append(cur + parts[i])
                cur = after
            else:
                cur += parts[i] + after
        out.append(cur)
    return out


CLUSTER_ITEM = re.compile(
    r"\s*(?:<size=[^>]*>|</size>|<voffset=[^>]*>|</voffset>)*\s*"
    r'<sprite name="?([^">]+)"?>'
    r"\s*(?:</size>|</voffset>)*"
)


# Icons that read as words (a faction or board-space symbol before
# "Alliance:" or inside a sentence): always text sized, never a big cluster.
LABEL_ICONS = {
    "Emperor",
    "SpacingGuild",
    "BeneGesserit",
    "Fremen",
    "Landsraad",
    "PopulationCenter",
    "Commerce",
    "EmperorAlliance",
    "SpacingGuildAlliance",
    "BeneGesseritAlliance",
    "FremenAlliance",
}
# Tags that only steer the app's line breaking.
IGNORED_TAGS = re.compile(r"</?nobr>|<line-height=[^>]*>|</line-height>")


def take_cluster(s, from_end=False):
    """Split leading (or trailing) inline sprites off a paragraph."""
    names = []
    if not from_end:
        pos = 0
        while True:
            m = CLUSTER_ITEM.match(s, pos)
            if not m or m.group(1) in LABEL_ICONS:
                break
            names.append(m.group(1))
            pos = m.end()
        return names, s[pos:]
    rest = s
    while True:
        m = re.search(CLUSTER_ITEM.pattern + r"\s*$", rest)
        if not m or m.group(1) in LABEL_ICONS:
            break
        names.insert(0, m.group(1))
        rest = rest[: m.start()]
    return names, rest


def words(s):
    return re.findall(r"[A-Za-z가-힣]{2,}", strip_tags(s))


_TRIMMED = {}


def icon_picture(inp, name):
    """The icon's picture cropped to its visible pixels, so heights compare."""
    if name not in _TRIMMED:
        hi = HIRES.get(name)
        img = inp.sprites.get(hi) if hi else None
        img = img if img is not None else inp.inline.get(name)
        if img is not None:
            box = img.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
            img = img.crop(box) if box else img
        _TRIMMED[name] = img
    return _TRIMMED[name]


# Icons drawn smaller than their neighbours, as printed (fraction of the row height).
SMALL_ICONS = {"IfThenArrow": 0.45}
BOTH_SIDES_H = 46.0  # icon height when a sentence has icons on both sides
ROW_GAP = 10.0  # between the pieces of an icon row (a lone ":" sits closer)
LABEL_SCALE = 0.62  # a faction symbol standing alone in an icon row ("<BG> Alliance:")


def row_gap(a, b):
    short = [i for i in (a, b) if i["kind"] == "text" and len(i["text"]) <= 2]
    return 3.0 if short else ROW_GAP


class PrintBox:
    """Lay out one text box the way the printed cards do.

    Each paragraph (split on line breaks) is one of
      - row: icons with at most two words of text (separators such as
        "-OR-", short labels such as "Fremen Bond:"): everything on one line,
        icons at the row height, the words small between them;
      - sentence: real text with icons before it (left), after it (right) or
        inside it (inline, text sized): the text wraps between the clusters.
    Rows share the box height; text shrinks first, then icons.
    """

    def __init__(
        self, inp, font, color, lang, icon_h, text_max, text_min=14.0, gap=10.0
    ):
        self.inp, self.font, self.color, self.lang = inp, font, color, lang
        self.korean = str(korean_face(font))
        self.icon_h, self.text_max, self.text_min, self.gap = (
            icon_h,
            text_max,
            text_min,
            gap,
        )

    def tmp(self, size, halign=2):
        return {
            "m_fontAsset": "MonoBehaviour:" + self.font,
            "m_fontSize": size,
            "m_fontSizeMin": self.text_min,
            "m_fontSizeMax": size,
            "m_enableAutoSizing": 0,
            "m_fontColor": self.color,
            "m_HorizontalAlignment": halign,
            "m_VerticalAlignment": 512,
            "m_characterSpacing": -1.5,
            "m_lineSpacing": 0.0,
            "m_paragraphSpacing": 0.0,
            "_fallback": self.korean,
            "_force_tt": self.lang == "ko",
        }

    def icon_size(self, name, H):
        img = icon_picture(self.inp, name)
        if img is None:
            return 0.0, 0.0
        h = H * SMALL_ICONS.get(name, LABEL_SCALE if name in LABEL_ICONS else 1.0)
        return h * img.size[0] / img.size[1], h

    def cluster_w(self, names, H):
        return sum(self.icon_size(n, H)[0] for n in names) + 3.0 * max(
            0, len(names) - 1
        )

    def plan(self, text, width, height, text_scale, icon_scale):
        paras = [
            # a "+" before an icon stays with the word before it, as printed
            re.sub(r" \+(?=<sprite)", "\u00a0+", p.strip())
            for p in split_paragraphs(IGNORED_TAGS.sub("", text))
            if strip_tags(p).strip() or re.search(SPRITE_TAG, p)
        ]
        fs = max(self.text_min, self.text_max * text_scale)
        self.inp.text.cur_fallback = self.korean
        self.inp.text.force_tt = self.lang == "ko"
        parsed = []
        for para in paras:
            lead, rest = take_cluster(para)
            if (
                lead
                and re.match(r"\s*[a-z]", strip_tags(rest))
                and len(words(rest)) > 2
            ):
                # "<2> for each ...": the icon is part of the sentence
                lead, rest = [], para
            trail, mid = take_cluster(rest, from_end=True)
            row = len(words(mid)) <= 2 and bool(
                lead or trail or re.search(SPRITE_TAG, mid)
            )
            parsed.append((para, lead, trail, mid.strip(), row))
        # rows of plain text keep their text height; icon rows share the rest
        plain_h = 0.0
        for _para, lead, trail, mid, row in parsed:
            if not row and not lead and not trail:
                plain_h += self.inp.text.fit(
                    mid, self.font, width, 9999, fs, fs, fs, False, char_spacing=-1.5
                )[3]
        n_icon = sum(1 for p in parsed if p[4] or p[1] or p[2])
        gaps = self.gap * 0.5 * max(0, len(parsed) - 1)
        H = min(self.icon_h, (height - plain_h - gaps) / max(1, n_icon)) * icon_scale
        # icons keep a floor next to long text; below it the text shrinks instead
        floor = min(self.icon_h, 0.36 * height) * icon_scale
        # only plain text can give way; with no text there is nothing to squeeze
        can_shrink = plain_h > 0 and self.text_max * text_scale > self.text_min + 0.5
        self.squeezed = n_icon > 0 and can_shrink and H < floor - 0.5
        H = max(H, floor if (n_icon and plain_h > 0) else H, 8.0)
        rows = []
        for para, lead, trail, mid, row in parsed:
            if row:
                items = self.row_items(para, H, fs)
                w = sum(i["w"] for i in items) + sum(
                    row_gap(a, b) for a, b in zip(items, items[1:], strict=False)
                )
                if w > width and len(items) > 2 and items[0]["kind"] == "text":
                    # a label too long to share the line ("Choose two:") goes above
                    label, rest_items = items[0], items[1:]
                    rows.append(
                        {
                            "kind": "row",
                            "items": [label],
                            "w": label["w"],
                            "h": label["h"],
                        }
                    )
                    w = sum(i["w"] for i in rest_items) + sum(
                        row_gap(a, b)
                        for a, b in zip(rest_items, rest_items[1:], strict=False)
                    )
                    rows.append({"kind": "row", "items": rest_items, "w": w, "h": H})
                    continue
                rows.append({"kind": "row", "items": items, "w": w, "h": H})
                continue
            Hs = (
                min(H, BOTH_SIDES_H) if (lead and trail) else H
            )  # icons on both sides sit smaller
            sep = None
            m = SEPARATOR.match(mid) if lead else None
            if m:
                # "<2> -OR- If ...": the separator stays beside the icons
                sep = self.text_item(m.group(1), Hs, fs)
                mid = mid[m.end() :].strip()
            lw = (
                self.cluster_w(lead, Hs)
                + (self.gap if lead else 0)
                + (sep["w"] + self.gap if sep else 0)
            )
            rw = self.cluster_w(trail, Hs) + (self.gap if trail else 0)
            avail = max(40.0, width - lw - rw)
            _s, _lines, tw, th = self.inp.text.fit(
                mid, self.font, avail, 9999, fs, fs, fs, False, char_spacing=-1.5
            )
            rows.append(
                {
                    "kind": "sentence",
                    "lead": lead,
                    "sep": sep,
                    "trail": trail,
                    "mid": mid,
                    "fs": fs,
                    "tw": tw,
                    "th": th,
                    "w": lw + tw + rw,
                    "h": max(th, Hs if (lead or trail) else 0),
                    "H": Hs,
                }
            )
        return rows

    def row_items(self, para, H, fs):
        items = []
        pos = 0
        for m in re.finditer(CLUSTER_ITEM.pattern, para):
            if strip_tags(para[pos : m.start()]).strip() or re.search(
                SPRITE_TAG, para[pos : m.start()]
            ):
                items.append(self.text_item(para[pos : m.start()], H, fs))
            w, h = self.icon_size(m.group(1), H)
            items.append({"kind": "icon", "name": m.group(1), "w": w, "h": h})
            pos = m.end()
        if strip_tags(para[pos:]).strip() or re.search(SPRITE_TAG, para[pos:]):
            items.append(self.text_item(para[pos:], H, fs))
        return items

    def text_item(self, raw, H, fs):
        rel = 1.0
        m = re.search(r"<size=(\d+)%>", raw)
        if m and SEPARATOR.search(raw):
            rel = int(m.group(1)) / 100.0
        size = max(self.text_min, min(fs, H * 0.62) * min(1.0, rel * 1.4))
        # keep label sprites, drop the app's size tags
        txt = re.sub(r"<(?!sprite)[^>]+>", "", raw).strip()
        _s, _lines, w, h = self.inp.text.fit(
            txt, self.font, 9999, 9999, size, size, size, False, char_spacing=-1.5
        )
        return {"kind": "text", "text": txt, "fs": size, "w": w + 4, "h": h}

    def fit(self, text, w, h):
        """Shrink text, then icons, until every row fits: rows, text and icon scale."""
        ts, isc = 1.0, 1.0
        for _ in range(80):
            rows = self.plan(text, w, h, ts, isc)
            total = sum(r["h"] for r in rows) + self.gap * 0.5 * max(0, len(rows) - 1)
            too_wide = any(r["w"] > w + 0.5 for r in rows)
            if total <= h + 0.5 and not too_wide and not self.squeezed:
                break
            # a row too wide for its icons shrinks the icons; tall text shrinks text,
            # and text squeezed between icon clusters shrinks both together
            wide_icons = too_wide and any(
                r["kind"] == "row" and r["w"] > w + 0.5 for r in rows
            )
            flanked = any(
                r["kind"] == "sentence"
                and (r["lead"] or r["trail"])
                and r["th"] > r["H"] + 0.5
                for r in rows
            )
            if self.text_max * ts > self.text_min + 0.5 and not wide_icons:
                ts *= 0.95
                if flanked:
                    isc *= 0.95
            else:
                isc *= 0.95
        return rows, ts, isc, total

    def draw(self, renderer, canvas, rect, text):
        x, y, w, h = rect
        rows, _ts, _isc, total = self.fit(text, w, h)
        S, top = renderer.S, renderer.top
        cur = y + h - (h - total) / 2.0  # unity top of the first row
        for r in rows:
            mid_y = cur - r["h"] / 2.0
            px = x + (w - r["w"]) / 2.0
            if r["kind"] == "row":
                for it in r["items"]:
                    if it["kind"] == "icon":
                        self.paste_icon(
                            renderer, canvas, it["name"], px, mid_y, it["w"], it["h"]
                        )
                    else:
                        self.inp.text.draw(
                            canvas,
                            S,
                            (px, mid_y - it["h"] / 2 - 2, it["w"], it["h"] + 4),
                            it["text"],
                            self.tmp(it["fs"]),
                            None,
                            top,
                        )
                    px += it["w"] + (
                        row_gap(it, r["items"][r["items"].index(it) + 1])
                        if it is not r["items"][-1]
                        else 0
                    )
            else:
                px = self.draw_cluster(renderer, canvas, r["lead"], px, mid_y, r["H"])
                if r["lead"]:
                    px += self.gap
                if r.get("sep"):
                    sp = r["sep"]
                    self.inp.text.draw(
                        canvas,
                        S,
                        (px, mid_y - sp["h"] / 2 - 2, sp["w"], sp["h"] + 4),
                        sp["text"],
                        self.tmp(sp["fs"]),
                        None,
                        top,
                    )
                    px += sp["w"] + self.gap
                self.inp.text.draw(
                    canvas,
                    S,
                    (px, mid_y - r["th"] / 2 - 1, r["tw"] + 1, r["th"] + 2),
                    r["mid"],
                    self.tmp(r["fs"]),
                    None,
                    top,
                )
                px += r["tw"] + (self.gap if r["trail"] else 0)
                self.draw_cluster(renderer, canvas, r["trail"], px, mid_y, r["H"])
            cur -= r["h"] + self.gap * 0.5

    def draw_cluster(self, renderer, canvas, names, px, mid_y, H):
        for n in names:
            w, h = self.icon_size(n, H)
            self.paste_icon(renderer, canvas, n, px, mid_y, w, h)
            px += w + 3.0
        return px - (3.0 if names else 0.0)

    def paste_icon(self, renderer, canvas, name, px, mid_y, w, h):
        img = icon_picture(self.inp, name)
        if img is not None:
            R.paste(
                canvas,
                renderer.S,
                img,
                (px, mid_y - h / 2, w, h),
                None,
                None,
                renderer.top,
            )


def custom_draw(inp):
    def draw(renderer, canvas, node, rect, clip, top):
        c = node["custom"]
        x, y, w, h = rect
        pad = c.get("pad", (10, 10, 10, 10))  # left, bottom, right, top
        box = (x + pad[0], y + pad[1], w - pad[0] - pad[2], h - pad[1] - pad[3])
        PrintBox(
            inp,
            c["font"],
            c["color"],
            c["lang"],
            c["icon_h"],
            c["text_max"],
            c.get("text_min", 14.0),
        ).draw(renderer, canvas, box, c["text"])

    return draw


# ---------------------------------------------------------------- binding
def set_sprite(node, name):
    """Show `name` in the node's Image, switching it on as the app's view code
    does (the Agent icon template ships with its Image off)."""
    image = R.comp(node, "Image", disabled=True)
    image["m_Sprite"] = "Sprite:" + name
    image.pop("enabled", None)


def bind_card_prefab(inp, spec, lang):
    """Cards the app lays out by hand (base set, Immortality, Tleilaxu): its own
    prefab, with the printed faction face, the Agent icons and our texts."""
    t = copy.deepcopy(inp.tree(spec["prefab"]))
    for n in R.find_all(t, "SubHeaderText"):
        n["tmp_patch"] = {
            "m_fontAsset": "MonoBehaviour:Gotham-Medium SDF",
            "m_fontStyle": 16,
            "m_fontSizeMax": 21.0,
            "m_fontSize": 21.0,
            "m_fontSizeMin": 10.0,
            "m_enableAutoSizing": 1,
            "m_characterSpacing": 1.0,
        }
        if lang == "ko":
            faction = next(
                (
                    f
                    for f, v in FACTIONS.items()
                    if v[1]
                    == (R.comp(n, "TextMeshProUGUI").get("m_text") or "").upper()
                ),
                None,
            )
            if faction:
                n["text"] = FACTIONS[faction][2]
    for off in ("SetIndicator", "EpicIcon"):
        for n in R.find_all(t, off):
            n["active"] = False
    agent = R.find(t, "Agent_Anchor")
    if agent is not None:
        rt = R.comp(agent, "RT")
        if rt["amin"][1] == 0 and rt["amax"][1] == 1 and rt["size"][1] > 0:
            # a few starter prefabs give the box its height as if top-anchored
            rt["size"][1] -= CANVAS[1]
    if lang == "ko":
        title = R.find(t, "TitleText")
        if title is not None and spec["title"].get("ko"):
            title["text"] = spec["title"]["ko"]
            title["fallback"] = str(KOREAN_FONT_BOLD)
    if R.find(t, "UI_crd_Element_ActionColumn_Dynamic") is not None:
        bind_icons(t, inp.tree("ActionIcon_obj.json"), spec)
    if spec.get("cost") is not None:
        # the prefab bakes a cost the app overwrites at run time
        # (Imperium Ceremony's says 5, the card 6)
        for n in R.find_all(t, "PersuasionText"):
            n["text"] = str(spec["cost"])
    return bind_prefab_texts(inp, t, lang, spec["prefab"])


def bind_dynamic(inp, spec, lang):
    if spec.get("prefab"):
        return bind_card_prefab(inp, spec, lang)
    has_static = bool(spec["static"]["en"])
    tree = inp.tree(
        "UI_crd_Imperium_Dynamic_HasStatic.prefab.json"
        if has_static
        else "UI_crd_Imperium_Dynamic.prefab.json"
    )
    icon_tpl = inp.tree("ActionIcon_obj.json")
    t = copy.deepcopy(tree)
    if spec["art"]:
        set_sprite(R.find(t, "CardImage"), spec["art"])
    else:
        R.find(t, "CardImage")["active"] = False
    title = spec["title"].get(lang) or spec["title"]["en"]
    tt = R.find(t, "TitleText")
    tt["text"] = ('<sprite name="CHOAMSet"> ' + title) if spec.get("choam") else title
    if lang == "ko":
        tt["fallback"] = str(KOREAN_FONT_BOLD)
    bind_factions(t, spec, lang)
    bind_cost(inp, t, spec)
    epic = R.find(t, "EpicIcon")
    if epic:
        epic["active"] = False
    R.find(t, "SetIndicator")["active"] = False
    bind_agent(inp, t, spec, lang, has_static)
    rv_anchor = R.find(t, "Reveal_Anchor")
    rv = R.find(rv_anchor, "UI_crd_Element_Reveal_Text")["children"][0]
    reveal = pick(spec["reveal"], lang)
    rv["active"] = False
    rv_anchor["children"].append(
        custom_node(
            "RevealBox",
            (0, 0, 0, 0),
            reveal,
            "Gotham-Book SDF",
            [1, 1, 1, 1],
            lang,
            icon_h=72,
            text_max=24,
            pad=(18, 4, 18, reveal_top_pad(t)),
        )
    )
    bind_icons(t, icon_tpl, spec)
    return t


REVEAL_TOP = 604  # the Reveal frame's top edge, from the card top
AGENT_TOP = 525


def reveal_top_pad(t):
    """Keep Reveal content below the Agent (or static) frame, which overlaps the
    Reveal frame's top edge: the taller the Agent box, the smaller the Reveal area."""
    bottom = 0.0
    agent = R.find(t, "Agent_Anchor")
    if agent and agent.get("active", True):
        bottom = AGENT_TOP + CANVAS[1] + R.comp(agent, "RT")["size"][1]
    trash = R.find(t, "Trash_Anchor")
    if trash and trash.get("active", True):
        bottom = max(bottom, 524 + 70)
    return max(22.0, bottom + 4 - REVEAL_TOP)


def pick(texts, lang):
    if lang == "ko":
        return texts.get("ko") or ""
    return texts.get("en") or ""


def custom_node(name, inset, text, font, color, lang, icon_h, text_max, pad):
    return {
        "name": name,
        "active": True,
        "children": [],
        "comps": [
            {
                "_": "RT",
                "pos": [0, 0],
                "size": [0, 0],
                "amin": [0, 0],
                "amax": [1, 1],
                "pivot": [0.5, 0.5],
            }
        ],
        "custom": {
            "text": text,
            "font": font,
            "color": color,
            "lang": lang,
            "icon_h": icon_h,
            "text_max": text_max,
            "pad": pad,
        },
    }


def bind_factions(t, spec, lang):
    subs = R.find(t, "SubHeader_Anchor")["children"]
    for i, n in enumerate(subs):
        n["active"] = i < len(spec["factions"])
        if not n["active"]:
            continue
        sprite, en, ko = FACTIONS[spec["factions"][i]]
        set_sprite(R.find(n, "SubHeaderImage_Top"), sprite)
        st = R.find(n, "SubHeaderText")
        st["text"] = ko if lang == "ko" else en
        # printed cards set the faction in the title face, in capitals
        st["tmp_patch"] = {
            "m_fontAsset": "MonoBehaviour:Gotham-Medium SDF",
            "m_fontStyle": 16,
            "m_fontSizeMax": 21.0,
            "m_fontSize": 21.0,
            "m_characterSpacing": 1.0,
        }
        R.comp(st, "RT")["pos"][0] = -16.0
        if lang == "ko":
            st["fallback"] = str(KOREAN_FONT_BOLD)


def bind_cost(inp, t, spec):
    acq = R.find(t, "AcquireFrame")
    if acq:
        acq["active"] = bool(spec["acquire"])
        if spec["acquire"]:
            bind_acquire(inp, acq, spec["acquire"])
    red = R.find(t, "PersuasionText_Reduced")
    if red:
        red["active"] = False
    if spec["cost"] is None:
        R.find(t, "PersuasionIcon")["active"] = False
    else:
        R.find(t, "PersuasionText")["text"] = str(spec["cost"])


def bind_acquire(inp, frame, effects):
    """The blue strip under the cost: arrow, then the bonus (repeats as a count)."""
    frame["no_layout"] = True
    R.comp(frame, "RT")["size"][1] = 194.0
    icon = R.find(frame, "AcquireIcon")
    kind = effects[0]
    if kind in ACQUIRE_INLINE:
        name = ACQUIRE_INLINE[kind]
        if len(effects) > 1 and name.endswith("_1"):
            name = name[:-1] + str(len(effects))
        set_sprite(icon, name)
        icon["inline"] = True
    else:
        set_sprite(icon, ACQUIRE_ICONS.get(kind, ACQUIRE_ICONS["Troop"]))
    icon["active"] = True


def bind_agent(inp, t, spec, lang, has_static):
    """The Agent box; printed cards keep an empty box when there is no Agent effect."""
    agent = R.find(t, "Agent_Anchor")
    el = R.find(agent, "UI_crd_Element_Agent_Text")
    txt = el["children"][0]
    text = pick(spec["agent"], lang)
    if has_static:
        # the red "When this card is ..." strip lies over the top of an L frame
        trash = R.find(t, "Trash_Anchor")
        R.find(trash, "UI_crd_Element_Agent_Text")["children"][0]["active"] = False
        trash["children"].append(
            custom_node(
                "StaticBox",
                None,
                pick(spec["static"], lang),
                "Gotham-Book SDF",
                [1, 1, 1, 1],
                lang,
                icon_h=44,
                text_max=22,
                pad=(30, 4, 30, 4),
            )
        )
        txt["active"] = False
        if text:
            el["children"].append(
                custom_node(
                    "AgentBox",
                    None,
                    text,
                    "Gotham-Book SDF",
                    [0, 0, 0, 1],
                    lang,
                    icon_h=46,
                    text_max=24,
                    pad=(14, 2, 14, 2),
                )
            )
        return
    if not text:
        set_sprite(agent, AGENT_FRAMES[0][0])
        R.comp(agent, "RT")["size"][1] = -(CANVAS[1] - AGENT_FRAMES[0][1])
        el["active"] = False
        return
    fname, fh = pick_frame(inp, text, lang)
    set_sprite(agent, fname)
    R.comp(agent, "RT")["size"][1] = -(CANVAS[1] - fh)
    el["active"] = False
    agent["children"].append(
        custom_node(
            "AgentBox",
            None,
            text,
            "Gotham-Book SDF",
            [0, 0, 0, 1],
            lang,
            icon_h=agent_icon_h(fh),
            text_max=24,
            pad=AGENT_PAD,
        )
    )


AGENT_PAD = (34, 8, 14, 8)  # left (clear of the Agent silhouette), bottom, right, top


def agent_icon_h(frame_h):
    return min(80.0, frame_h - 24.0)


def pick_frame(inp, text, lang):
    """Smallest Agent frame keeping text at 22.5 px and icons at 50 px."""
    box = PrintBox(inp, "Gotham-Book SDF", [0, 0, 0, 1], lang, 66.0, 24)
    avail_w = 512 - AGENT_PAD[0] - AGENT_PAD[2]
    has_icons = bool(re.search(SPRITE_TAG, text))
    for name, h in AGENT_FRAMES:
        if has_icons and h < 111:
            continue
        box.icon_h = agent_icon_h(h)
        rows, ts, isc, _total = box.fit(text, avail_w, h - AGENT_PAD[1] - AGENT_PAD[3])
        text_ok = box.text_max * ts >= 22.5 or not any(
            r["kind"] == "sentence" for r in rows
        )
        icons_ok = all(
            r["h"] >= 50
            for r in rows
            if r["kind"] == "row" or r.get("lead") or r.get("trail")
        )
        if text_ok and icons_ok:
            return name, h
    return AGENT_FRAMES[-1]


# The GRAFT tab as printed (Chairdog, Usurp, Ghola, Dissecting Kit scans at
# 556 px): its curved end stops at x 405 with or without a faction icon, and
# the label starts at x 110 beside an icon. The app's own layout (icon column
# 80 wide, label element 330) ends it at 432 beside an icon and at 352
# without one, so the renderer sets the printed widths instead.
PRINT_GRAFT_TAB_WIDTH = 383.0  # the tab from the box's left edge (x 22)
PRINT_GRAFT_ICON_COLUMN = 66.0


def bind_icons(t, icon_tpl, spec):
    col = R.find(t, "UI_crd_Element_ActionColumn_Dynamic")
    icons = spec["icons"] + spec["infiltrate"]
    n = len(icons)
    col["pref_w"], col["pref_h"] = 80, n * 58 + max(0, n - 1) * 5
    label = R.find_shown(t, "GraftTextElement")  # graft cards only
    if label is not None:
        if n:
            col["pref_w"] = PRINT_GRAFT_ICON_COLUMN
        le = R.comp(label, "LayoutElement")
        le["m_MinWidth"] = le["m_PreferredWidth"] = PRINT_GRAFT_TAB_WIDTH - (
            PRINT_GRAFT_ICON_COLUMN if n else 0.0
        )
        # the column's black backer stays dark between the icons, as printed,
        # but stops at the tab's top edge: hanging 7 px below the icons it
        # would cut a dark notch into the tab, which the print runs unbroken
        # (tab 43 px tall from the container's foot, the column 8 px above
        # it); it keeps the app column's 80 px width behind the narrower one
        backer = R.find(col, "BackerImage")
        if backer is not None and n:
            rt = R.comp(backer, "RT")
            rt["pos"][1], rt["size"][1] = 35.0, -42.0
            rt["size"][0] = 80.0 - PRINT_GRAFT_ICON_COLUMN
    for ic in icons:
        node = copy.deepcopy(icon_tpl)
        node["active"] = True
        set_sprite(R.find(node, "Icon"), AGENT_ICONS[ic])
        hl = R.find(node, "Highlight")
        if hl:
            hl["active"] = False
        col["children"].append(node)
    if n == 0:
        box = R.find(t, "ActionColumn_HorizontalContainer")
        if R.find_shown(box, "GraftTextElement") is None:
            box["active"] = False
        else:
            # Usurp grafts with no Agent icon: the GRAFT tab still prints, at
            # the box's left edge where the empty column ends
            col["active"] = False


# ---------------------------------------------------------------- intrigue
INTRIGUE_FRONT = {
    "Plot": "UI_crd_CardFront_IntriguePlot",
    "Combat": "UI_crd_CardFront_IntrigueCombat",
    "Endgame": "UI_crd_CardFront_IntrigueEndGame",
}
INTRIGUE_OR = {
    "Plot": "UI_crd_IntriguePlotOrFrame",
    "Combat": "UI_crd_IntrigueCombatOrFrame",
    "Endgame": "UI_crd_IntrigueEndGameOrFrame",
}
INTRIGUE_TYPE_COLOR = {"Plot": "#FDD5A7", "Combat": "#EC8B76", "Endgame": "#68A3C8"}
INTRIGUE_TYPE_WORD = {
    "en": {"Plot": "PLOT", "Combat": "COMBAT", "Endgame": "ENDGAME"},
    # official Korean terms [Main p. 7] (docs/rules/glossary-ko.md)
    "ko": {"Plot": "음모", "Combat": "전투", "Endgame": "종료 단계"},
}
INTRIGUE_TEXT = [1, 0.99, 0.92, 1]


def intrigue_spec(inp, content_id):
    short = catalog.INTRIGUE_ARCHETYPES[content_id]
    arch = ARCHETYPES[short]
    at = arch.attributes
    slug = at["Name"].rsplit(".", 1)[0]  # card.intrigue.<slug>
    texts = []
    for n in (1, 2):
        keys = [f"{slug}.text.{n}", f"{slug}.text{n}"]
        en = next((inp.en[k] for k in keys if k in inp.en), None)
        if en is None:
            en = next((inp.text_en(k) for k in keys if inp.loc.get(k)), None)
        ko = next((inp.ko[k] for k in keys if k in inp.ko), None)
        if en or ko:
            texts.append({"en": en, "ko": ko, "key": text_key(inp, keys)})
    prefab = f"UI_crd_Intrigue_{short.rsplit('.', 1)[1]}.prefab.json"
    if (inp.prefab_dir / prefab).exists():
        # the app lays this card out by hand
        texts = prefab_texts(inp, prefab_text_nodes(inp.tree(prefab), prefab))
    else:
        prefab = None
    return {
        "kind": "intrigue",
        "id": content_id,
        "arch": short,
        "slug": slug,
        "prefab": prefab,
        "title": {
            "en": inp.text_en(at["Name"]),
            "ko": KOREAN_CARD_NAMES["intrigue"].get(content_id),
        },
        "types": list(at.get("IntrigueTypeList", ("Plot",))),
        "texts": texts,
        "choam": "CHOAMModule" in at.get("SetList", ()),
        "art": "intrigue",  # no illustration: the frames are the face
        "path": inp.manifest.get(("intrigue", content_id)),
    }


def bind_intrigue_prefab(inp, spec, lang):
    t = copy.deepcopy(inp.tree(spec["prefab"]))
    title = spec["title"].get(lang) or spec["title"]["en"]
    head = R.find(t, "HeaderText")
    head["text"] = title
    head["tmp_patch"] = {
        "m_fontAsset": "MonoBehaviour:Gotham-Medium SDF",
        "m_fontStyle": 16,
        "m_fontSize": 40.0,
        "m_fontSizeMax": 40.0,
        "m_characterSpacing": 1.0,
    }
    R.comp(head, "RT")["size"][1] = 196.0
    words_ = INTRIGUE_TYPE_WORD[lang]
    for tnode in R.find_all(t, "CardTypeText_Anchor")[0]["children"]:
        tnode["text"] = " <color=#FFFCE7>/ ".join(
            f"<color={INTRIGUE_TYPE_COLOR[x]}>{words_[x]}" for x in spec["types"]
        )
        tnode["tmp_patch"] = {
            "m_fontAsset": "MonoBehaviour:Gotham-Medium SDF",
            "m_fontStyle": 16,
            "m_fontSize": 30.0,
            "m_fontSizeMax": 30.0,
            "m_enableAutoSizing": 0,
            "m_characterSpacing": 1.0,
        }
    R.comp(R.find(t, "CardTypeText_Anchor"), "RT")["size"][1] = 92.0
    for n in R.find_all(t, "FrameText"):
        n["text"] = "—또는—" if lang == "ko" else "—OR—"
    for n in R.find_all(t, "SetIndicator"):
        n["active"] = False
    if lang == "ko":
        head["fallback"] = str(KOREAN_FONT_BOLD)
        for n in (
            R.find_all(t, "FrameText")
            + R.find_all(t, "CardTypeText_Anchor")[0]["children"]
        ):
            n["fallback"] = str(KOREAN_FONT_BOLD)
    return bind_prefab_texts(inp, t, lang, spec["prefab"])


def bind_intrigue(inp, spec, lang):
    if spec.get("prefab"):
        return bind_intrigue_prefab(inp, spec, lang)
    types = spec["types"]
    if len(types) > 1:
        name = "UI_crd_Intrigue_Dynamic_SplitTypes.prefab.json"
    elif len(spec["texts"]) > 1:
        name = "UI_crd_Intrigue_Dynamic_SplitText.prefab.json"
    else:
        name = "UI_crd_Intrigue_Dynamic.prefab.json"
    t = copy.deepcopy(inp.tree(name))
    R.comp(t, "Image")["m_Sprite"] = "Sprite:" + INTRIGUE_FRONT[types[0]]
    alt = R.find(t, "AltFrame")
    if alt and len(types) > 1:
        set_sprite(alt, INTRIGUE_FRONT[types[1]])
    orf = R.find(t, "ORFrame")
    if orf:
        orf["active"] = len(spec["texts"]) > 1
        set_sprite(orf, INTRIGUE_OR[types[-1]])
        ft = R.find(orf, "FrameText")
        ft["text"] = "—또는—" if lang == "ko" else "—OR—"
        if lang == "ko":
            ft["fallback"] = str(KOREAN_FONT_BOLD)
    title = spec["title"].get(lang) or spec["title"]["en"]
    head = R.find(t, "HeaderText")
    head["text"] = (
        ('<size=70%><sprite name="CHOAMSet"></size> ' + title)
        if spec["choam"]
        else title
    )
    # printed Intrigue cards set the title and the type in a wide face, in capitals
    head["tmp_patch"] = {
        "m_fontAsset": "MonoBehaviour:Gotham-Medium SDF",
        "m_fontStyle": 16,
        "m_fontSize": 40.0,
        "m_fontSizeMax": 40.0,
        "m_characterSpacing": 1.0,
    }
    if lang == "ko":
        head["fallback"] = str(KOREAN_FONT_BOLD)
    R.comp(head, "RT")["size"][1] = (
        196.0  # centre the title in the black band, as printed
    )
    R.comp(R.find(t, "CardTypeText_Anchor"), "RT")["size"][1] = (
        92.0  # type line nearer the edge
    )
    words_ = INTRIGUE_TYPE_WORD[lang]
    label = " <color=#FFFCE7>/ ".join(
        f"<color={INTRIGUE_TYPE_COLOR[x]}>{words_[x]}" for x in types
    )
    tnode = R.find(t, "UI_crd_Element_IntrigueType")
    tnode["text"] = label
    tnode["tmp_patch"] = {
        "m_fontAsset": "MonoBehaviour:Gotham-Medium SDF",
        "m_fontStyle": 16,
        "m_fontSize": 30.0,
        "m_fontSizeMax": 30.0,
        "m_enableAutoSizing": 0,
        "m_characterSpacing": 1.0,
    }
    if lang == "ko":
        tnode["fallback"] = str(KOREAN_FONT_BOLD)
    set_ind = R.find(t, "SetIndicator")
    if set_ind:
        set_ind["active"] = False
    for i, n in enumerate(
        ("UI_crd_Element_Intrigue_Text1", "UI_crd_Element_Intrigue_Text2")
    ):
        el = R.find(t, n)
        if el is None:
            continue
        txt = el["children"][0]
        txt["active"] = False
        el["no_layout"] = True  # the print-style box fills the whole text area
        if i >= len(spec["texts"]):
            el["active"] = False
            continue
        icon_h = 128 if len(spec["texts"]) == 1 else 84
        el["children"].append(
            custom_node(
                f"IntrigueBox{i}",
                None,
                pick(spec["texts"][i], lang),
                "Gotham-Medium SDF",
                INTRIGUE_TEXT,
                lang,
                icon_h=icon_h,
                text_max=34,
                pad=(30, 22, 30, 22),
            )
        )
    if len(spec["texts"]) > 1 and name.endswith("SplitText.prefab.json"):
        # the split-text template stacks its parts with a layout group: place by hand
        area = R.find(t, "GameTextArea_Anchor")
        area["no_layout"] = True
        t1, t2 = (
            R.find(t, "UI_crd_Element_Intrigue_Text1"),
            R.find(t, "UI_crd_Element_Intrigue_Text2"),
        )
        for node, pos in ((t1, 148.5), (t2, -138.5)):
            rt = R.comp(node, "RT")
            rt.update(
                {
                    "pos": [0.0, pos],
                    "size": [0.0, -287.0],
                    "amin": [0, 0],
                    "amax": [1, 1],
                }
            )
        rt = R.comp(orf, "RT")
        rt.update(
            {
                "pos": [0.0, 10.0],
                "size": [496.0, 47.0],
                "amin": [0.5, 0.5],
                "amax": [0.5, 0.5],
            }
        )
    return t


# ---------------------------------------------------------------- conflict
BATTLE_ICONS = {
    "Crysknife": "hud_Icon_Conflict_Knife",
    "Ornithopter": "hud_Icon_Conflict_Thopter",
    "DesertMouse": "hud_Icon_Conflict_Mouse",
    "Wildcard": "hud_Icon_Conflict_Wild",
}
PLACE_WORDS = {"en": ("st", "nd", "rd"), "ko": ("등", "등", "등")}


def conflict_spec(inp, content_id):
    # the printed card is the CHOAM version (contract icons)
    short = catalog.CONFLICT_ARCHETYPES[content_id][1]
    arch = ARCHETYPES[short]
    at = arch.attributes
    slug = at["Name"]  # card.conflict.<slug>
    last = short.rsplit(".", 1)[1].lower()
    rewards = []
    for n in (1, 2, 3):
        keys = [f"{slug}.reward.{n}", f"card.conflict.{last}.reward.{n}"]
        en = next((inp.en[k] for k in keys if k in inp.en), None)
        if en is None:
            en = next((inp.text_en(k) for k in keys if inp.loc.get(k)), None)
        ko = next((inp.ko[k] for k in keys if k in inp.ko), None)
        rewards.append({"en": en, "ko": ko, "key": text_key(inp, keys)})
    ours = CONFLICTS_BY_ID.get(content_id)
    return {
        "kind": "conflict",
        "id": content_id,
        "arch": short,
        "slug": slug,
        "title": {
            "en": inp.text_en(slug),
            # our names add the battle icon in brackets; the card prints only the name
            "ko": re.sub(
                r"\s*\(.*\)$", "", KOREAN_CARD_NAMES["conflicts"].get(content_id) or ""
            )
            or None,
        },
        "level": at.get("ConflictLevel"),
        "battle": at.get("BattleIcon"),
        "shield": bool(ours and ours.shield_wall_protected),
        "texts": [r for r in rewards if r["en"] or r["ko"]],
        "rewards": rewards,
        "art": "conflict",
        "path": inp.manifest.get(("conflict", content_id)),
    }


def bind_conflict(inp, spec, lang):
    t = copy.deepcopy(inp.tree("UI_crd_Conflict_Dynamic.prefab.json"))
    # cards about a board space ("Battle for ...") print on the orange front
    first = spec["rewards"][0]["en"] or ""
    front = (
        "UI_crd_CardFront_Conflict_Orange"
        if "ControlNeutral" in first
        else "UI_crd_CardFront_Conflict"
    )
    R.comp(t, "Image")["m_Sprite"] = "Sprite:" + front
    head = R.find(t, "Conflict Header")
    head["text"] = spec["title"].get(lang) or spec["title"]["en"]
    if lang == "ko":
        head["fallback"] = str(KOREAN_FONT_BOLD)
    token = R.find(t, "ConflictRewardToken")
    if spec["battle"] in BATTLE_ICONS:
        set_sprite(R.find(token, "Icon"), BATTLE_ICONS[spec["battle"]])
    else:
        token["active"] = False
    nw = R.find(t, "NoWormsIcon")
    if nw:
        nw["active"] = spec["shield"]
    for off in ("crd_3rd_greyout", "Crd_Flash", "NoWormVFX", "SetIndicator"):
        n = R.find(t, off)
        if n:
            n["active"] = False
    places = PLACE_WORDS[lang]
    for i, anchor_name in enumerate(("1st_Anchor", "2nd_Anchor", "3rd_Anchor")):
        a = R.find(t, anchor_name)
        text = pick(spec["rewards"][i], lang)
        suffix = R.find(a, ("stText", "ndText", "rdText")[i])
        suffix["text"] = places[i]
        if lang == "ko":
            suffix["fallback"] = str(KOREAN_FONT_BOLD)
        num = R.find(a, f"{i + 1}Text")
        num["text"] = str(i + 1)
        rw = R.find(a, "RewardText")
        rw["active"] = False
        if not text:
            continue
        a["children"].append(
            custom_node(
                f"Reward{i}",
                None,
                text,
                "Gotham-Medium SDF",
                [1, 1, 1, 1],
                lang,
                icon_h=92,
                text_max=34,
                pad=(12, 8, 12, 42),
            )
        )
    return t


# ---------------------------------------------------------------- whole prefabs
# names come from names_ko and type lines from INTRIGUE_TYPE_WORD, not the text table
TITLE_NODES = ("TitleText", "HeaderRoot", "HeaderText")


def prefab_text_nodes(t, prefab):
    """[(key, node)] for the texts a per-card prefab shows: its loc key, or
    ``<prefab>#<node path>`` for baked text; bare numbers and marks are skipped."""
    out = []

    def walk(n, path, active):
        active = active and n.get("active", True)
        p = f"{path}/{n['name']}" if path else n["name"]
        tmp = R.comp(n, "TextMeshProUGUI")
        if (
            tmp is not None
            and active
            and n["name"] not in TITLE_NODES
            and not n["name"].startswith("UI_crd_Element_IntrigueType")
        ):
            text = tmp.get("m_text") or ""
            if re.search(r"[A-Za-z]{2,}", strip_tags(text)):
                key = next(
                    (c.get("locKey") for c in n["comps"] if c.get("locKey")), None
                )
                out.append((key or f"{prefab}#{p}", n))
        for ch in n["children"]:
            walk(ch, p, active)

    walk(t, "", True)
    return out


def bind_prefab_texts(inp, t, lang, prefab=""):
    """A per-card prefab carries its own texts: draw them, printed English and
    Korean from the text tables by the node's key."""
    keyed = {id(n): k for k, n in prefab_text_nodes(t, prefab)}

    def walk(n):
        tmp = R.comp(n, "TextMeshProUGUI")
        if tmp is not None and n.get("text") is None:
            key = keyed.get(id(n))
            text = tmp.get("m_text") or ""
            if lang == "ko":
                n["fallback"] = str(korean_face(tmp.get("m_fontAsset")))
                if key and key in inp.ko:
                    text = inp.ko[key]
            elif key and key in inp.en:
                text = inp.en[key]
            n["text"] = text
        for ch in n["children"]:
            walk(ch)

    walk(t)
    return t


def prefab_texts(inp, nodes):
    return [
        {
            "key": k,
            "en": inp.en.get(k) or R.comp(n, "TextMeshProUGUI").get("m_text"),
            "ko": inp.ko.get(k),
        }
        for k, n in nodes
    ]


def contract_spec(inp, content_id):
    short = catalog.CONTRACT_ARCHETYPES[content_id]
    number = short.rsplit("_", 1)[1]
    prefab = f"UI_crd_Contract_Base_{number}.prefab.json"
    tree = inp.tree(prefab) if (inp.prefab_dir / prefab).exists() else None
    nodes = prefab_text_nodes(tree, prefab) if tree else []
    return {
        "kind": "contract",
        "id": content_id,
        "arch": short,
        "prefab": prefab if tree else None,
        # our names number the copies (원로회 I/II); the card prints only the name
        "title": {
            "en": None,
            "ko": re.sub(
                r"\s+[IVX]+$", "", KOREAN_CARD_NAMES["contracts"].get(content_id) or ""
            )
            or None,
        },
        "texts": prefab_texts(inp, nodes),
        "art": "contract" if tree else None,
        "path": inp.manifest.get(("contract", content_id)),
    }


def bind_contract(inp, spec, lang):
    t = copy.deepcopy(inp.tree(spec["prefab"]))
    if lang == "ko" and spec["title"]["ko"]:
        head = R.find(t, "HeaderRoot")
        if head:
            head["text"] = spec["title"]["ko"]
            head["fallback"] = str(KOREAN_FONT_BOLD)
    return bind_prefab_texts(inp, t, lang, spec["prefab"])


# ---------------------------------------------------------------- render
BINDERS = {
    "imperium": lambda inp, spec, lang: bind_dynamic(inp, spec, lang),
    "intrigue": lambda inp, spec, lang: bind_intrigue(inp, spec, lang),
    "conflict": lambda inp, spec, lang: bind_conflict(inp, spec, lang),
    "contract": lambda inp, spec, lang: bind_contract(inp, spec, lang),
}
SPECS = {
    "imperium": lambda inp, cid: imperium_spec(inp, cid),
    "intrigue": lambda inp, cid: intrigue_spec(inp, cid),
    "conflict": lambda inp, cid: conflict_spec(inp, cid),
    "contract": lambda inp, cid: contract_spec(inp, cid),
}
KIND_IDS = {
    "imperium": lambda: [
        cid
        for cid, short in catalog.CARD_ARCHETYPES.items()
        if short.split(".")[1] in ("Uprising", "Promo", "Immortality", "BaseSet")
    ],
    "intrigue": lambda: [
        cid
        for cid, short in catalog.INTRIGUE_ARCHETYPES.items()
        if short in ARCHETYPES
        and short.split(".")[1] in ("Uprising", "Promo", "Immortality")
    ],
    "conflict": lambda: [
        cid
        for cid, (short, _six) in catalog.CONFLICT_ARCHETYPES.items()
        if short in ARCHETYPES and ".Uprising." in short
    ],
    "contract": lambda: [
        cid
        for cid, short in catalog.CONTRACT_ARCHETYPES.items()
        if ".Uprising." in short
    ],
}


def render_card(inp, spec, lang, scale):
    tree = BINDERS[spec["kind"]](inp, spec, lang)
    size = R.comp(tree, "RT")["size"]
    r = R.CardRenderer(inp.sprites, inp.text, scale, custom=custom_draw(inp))
    r.alt = inp.inline
    return r.render(tree, int(size[0]), int(size[1]))


def card_ids(args):
    """[(kind, content id)] from --kind and --all / --ids."""
    kinds = list(KIND_IDS) if args.kind == "all" else args.kind.split(",")
    out = []
    for kind in kinds:
        ids = KIND_IDS[kind]() if args.all else [i for i in args.ids.split(",") if i]
        out += [(kind, cid) for cid in ids]
    return out


def text_fields(spec):
    if spec["kind"] == "imperium" and not spec.get("prefab"):
        return [spec[f] for f in ("agent", "reveal", "static")]
    return spec["texts"]


def korean_complete(spec):
    """Every English text of the card has its Korean-edition counterpart."""
    return all(t.get("ko") for t in text_fields(spec) if t.get("en"))


def cmd_render(args):
    inp = Inputs()
    langs = args.lang.split(",")
    out_root = Path(args.out) if args.out else ASSETS / "cards" / "app"
    done, skipped = 0, []
    for kind, cid in card_ids(args):
        spec = SPECS[kind](inp, cid)
        if not spec["art"] or not spec["path"]:
            skipped.append((cid, "no art" if not spec["art"] else "no manifest path"))
            continue
        for lang in langs:
            if lang == "ko" and not korean_complete(spec) and not args.allow_missing_ko:
                skipped.append((cid, "no Korean text"))
                continue
            img = render_card(inp, spec, lang, args.scale)
            dest = out_root / lang / Path(spec["path"]).with_suffix(".webp")
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, "WEBP", quality=92, method=6)
            done += 1
    print("rendered", done, "skipped", len(skipped))
    for s in skipped:
        print("  ", *s)


def cmd_compare(args):
    """Rendered face next to the scan (and Korean photo) for review."""
    inp = Inputs()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for kind, cid in card_ids(args):
        spec = SPECS[kind](inp, cid)
        if not spec["art"] or not spec["path"]:
            continue
        ims = []
        for p in (
            ASSETS / "cards" / "en" / spec["path"],
            None,
            ASSETS / "cards" / "ko" / spec["path"],
            "ko",
        ):
            if p is None or p == "ko":
                lang = "ko" if p == "ko" else "en"
                if lang == "ko" and not korean_complete(spec):
                    continue
                ims.append(render_card(inp, spec, lang, 1.0).convert("RGB"))
            elif p.exists():
                ims.append(Image.open(p).convert("RGB"))
        h = 700
        ims = [
            im.resize((int(im.width * h / im.height), h), Image.LANCZOS) for im in ims
        ]
        sheet = Image.new(
            "RGB", (sum(i.width for i in ims) + 16 * (len(ims) - 1), h), "white"
        )
        x = 0
        for im in ims:
            sheet.paste(im, (x, 0))
            x += im.width + 16
        sheet.save(out / f"{kind}-{cid}.jpg", quality=88)
    print("compare sheets ->", out)


def cmd_specs(args):
    inp = Inputs()
    print(
        json.dumps(
            [SPECS[kind](inp, cid) for kind, cid in card_ids(args)],
            ensure_ascii=False,
            indent=1,
        )
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (
        ("render", cmd_render),
        ("compare", cmd_compare),
        ("specs", cmd_specs),
    ):
        p = sub.add_parser(name)
        p.add_argument("--ids", default="")
        p.add_argument("--all", action="store_true")
        p.add_argument(
            "--kind", default="imperium", help="imperium, intrigue, ... or all"
        )
        p.set_defaults(fn=fn)
        if name == "render":
            p.add_argument("--lang", default="en")
            p.add_argument("--scale", type=float, default=1.5)
            p.add_argument("--out")
            p.add_argument("--allow-missing-ko", action="store_true")
        if name == "compare":
            p.add_argument("--out", required=True)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
