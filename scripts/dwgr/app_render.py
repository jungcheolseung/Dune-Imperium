"""Draw a Unity UI tree (a card prefab dumped by app_assets.py) with Pillow.

A small re-implementation of the parts of Unity UI and TextMeshPro the
Dune: Imperium app's card views use: RectTransform anchoring, Image (simple,
sliced, preserve aspect, tint), RectMask2D clipping, CanvasGroup alpha,
horizontal/vertical layout groups, and TextMeshPro text drawn from the app's
SDF font atlases with rich-text tags and inline <sprite> glyphs sized by the
app's TMP sprite asset metrics. app_cards.py binds card data into the trees.
"""

import json
import math
import os
import re

import numpy as np
from PIL import Image, ImageFont


# ---------------------------------------------------------------- assets
class Sprites:
    def __init__(self, folder):
        self.folder = folder
        meta = os.path.join(folder, "_meta.json")
        self.meta = json.load(open(meta)) if os.path.exists(meta) else {}
        self.cache = {}

    def get(self, name):
        if name not in self.cache:
            path = os.path.join(self.folder, name + ".png")
            self.cache[name] = (
                Image.open(path).convert("RGBA") if os.path.exists(path) else None
            )
        return self.cache[name]


class SDFFont:
    def __init__(self, path):
        d = json.load(open(path))
        folder = os.path.dirname(path)
        self.name = d["name"]
        f = d["face"]
        self.point = float(f["m_PointSize"])
        self.fscale = float(f.get("m_Scale", 1.0) or 1.0)
        self.line_h = float(f["m_LineHeight"])
        self.asc = float(f["m_AscentLine"])
        self.desc = float(f["m_DescentLine"])
        self.cap = float(f.get("m_CapLine", self.asc))
        self.pad = float(d["padding"])
        self.glyphs = {g["m_Index"]: g for g in d["glyphs"]}
        self.chars = {c["m_Unicode"]: c["m_GlyphIndex"] for c in d["chars"]}
        atl = Image.open(os.path.join(folder, d["atlas"][0][0])).convert("RGBA")
        a = np.asarray(atl).astype(np.float32) / 255.0
        self.atlas = a[..., 3] if a[..., 3].std() > 0.01 else a[..., 0]
        self.H = self.atlas.shape[0]
        self.kern = {}
        for r in d.get("kerning", []):
            try:
                a1 = r["m_FirstAdjustmentRecord"]
                a2 = r["m_SecondAdjustmentRecord"]
                self.kern[(a1["m_GlyphIndex"], a2["m_GlyphIndex"])] = a1[
                    "m_GlyphValueRecord"
                ]["m_XAdvance"]
            except KeyError, TypeError:
                pass

    def has(self, ch):
        return ord(ch) in self.chars

    def glyph(self, ch):
        gi = self.chars.get(ord(ch))
        return (gi, self.glyphs[gi]) if gi is not None else (None, None)


# ---------------------------------------------------------------- geometry
def resolve(parent, rt):
    px, py, pw, ph = parent
    ax0 = px + rt["amin"][0] * pw
    ax1 = px + rt["amax"][0] * pw
    ay0 = py + rt["amin"][1] * ph
    ay1 = py + rt["amax"][1] * ph
    w = (ax1 - ax0) + rt["size"][0]
    h = (ay1 - ay0) + rt["size"][1]
    refx = ax0 + rt["pivot"][0] * (ax1 - ax0)
    refy = ay0 + rt["pivot"][1] * (ay1 - ay0)
    cx = refx + rt["pos"][0]
    cy = refy + rt["pos"][1]
    return (cx - rt["pivot"][0] * w, cy - rt["pivot"][1] * h, w, h)


def comp(node, kind):
    for c in node["comps"]:
        if c["_"] == kind:
            return c
    return None


def intersect(a, b):
    if a is None:
        return b
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return (x0, y0, max(0, x1 - x0), max(0, y1 - y0))


# ---------------------------------------------------------------- rich text
TAG = re.compile(
    r"<(/?)([a-zA-Z\-]+)(?:=\"?([^\">]*)\"?)?(?:\s+name=\"?([^\">]*)\"?)?>"
)


def parse_rich(text, base_size):
    """-> list of tokens: ('ch', c, style) | ('sp', name, style) | ('br',)."""
    toks = []
    style = {
        "size": base_size,
        "bold": False,
        "italic": False,
        "color": None,
        "voffset": 0.0,
    }
    stack = {"size": [], "color": [], "voffset": []}
    i = 0
    text = text.replace("\r", "")
    while i < len(text):
        if text[i] == "<":
            m = TAG.match(text, i)
            if m:
                close, tag, val, name = (
                    m.group(1),
                    m.group(2).lower(),
                    m.group(3),
                    m.group(4),
                )
                i = m.end()
                if tag == "br":
                    toks.append(("br",))
                elif tag == "sprite":
                    nm = name or (val[5:] if val and val.startswith("name=") else val)
                    if val and not name and "name=" in (val or ""):
                        nm = val.split("name=")[-1]
                    toks.append(("sp", nm, dict(style)))
                elif tag == "size":
                    if close:
                        style["size"] = (
                            stack["size"].pop() if stack["size"] else base_size
                        )
                    else:
                        stack["size"].append(style["size"])
                        v = val.strip()
                        if v.endswith("%"):
                            style["size"] = style["size"] * float(v[:-1]) / 100.0
                        elif v.endswith("em"):
                            style["size"] = style["size"] * float(v[:-2])
                        else:
                            style["size"] = float(v)
                elif tag == "b":
                    style["bold"] = not close
                elif tag == "i":
                    style["italic"] = not close
                elif tag == "color":
                    if close:
                        style["color"] = (
                            stack["color"].pop() if stack["color"] else None
                        )
                    else:
                        stack["color"].append(style["color"])
                        style["color"] = val
                elif tag == "voffset":
                    if close:
                        style["voffset"] = (
                            stack["voffset"].pop() if stack["voffset"] else 0.0
                        )
                    else:
                        stack["voffset"].append(style["voffset"])
                        v = val.strip()
                        style["voffset"] = (
                            float(v[:-2])
                            if v.endswith("em")
                            else float(v) / max(1.0, base_size)
                        )
                # line-height, nobr: ignored
                continue
        ch = text[i]
        i += 1
        if ch == "\n":
            toks.append(("br",))
        else:
            toks.append(("ch", ch, dict(style)))
    return toks


class TextRenderer:
    def __init__(self, fonts_dir, sprites, sprite_assets, fallback_path=None):
        self.fonts_dir = fonts_dir
        self.sprites = sprites
        self.sa = {}
        for asset in sprite_assets.values():
            for k, v in asset.items():
                self.sa.setdefault(k, v)
        self.fonts = {}
        self.fallback_path = fallback_path

    def font(self, name):
        if name not in self.fonts:
            self.fonts[name] = SDFFont(os.path.join(self.fonts_dir, name + ".json"))
        return self.fonts[name]

    # one laid-out element
    def measure(self, tok, font, smallcaps, upper, char_spacing):
        kind = tok[0]
        st = tok[2]
        size = st["size"]
        if kind == "sp":
            g = self.sa.get(tok[1])
            if g is None:
                return None
            k = (font.asc / g["h"]) * g["cscale"] * g["scale"] * (size / font.point)
            return {
                "kind": "sp",
                "name": tok[1],
                "w": g["w"] * k,
                "adv": g["adv"] * k,
                "asc": g["by"] * k,
                "desc": (g["by"] - g["h"]) * k,
                "bx": g["bx"] * k,
                "h": g["h"] * k,
                "size": size,
                "st": st,
            }
        ch = tok[1]
        sz = size
        if upper:
            ch = ch.upper()
        elif smallcaps and ch.islower():
            ch = ch.upper()
            sz = size * 0.8
        s = sz / font.point
        if font.has(ch):
            gi, g = font.glyph(ch)
            m = g["m_Metrics"]
            adv = m["m_HorizontalAdvance"] * s + char_spacing * size * 0.01
            return {
                "kind": "ch",
                "ch": ch,
                "gi": gi,
                "g": g,
                "s": s,
                "adv": adv,
                "size": sz,
                "asc": font.asc * (size / font.point),
                "desc": font.desc * (size / font.point),
                "st": st,
                "space": ch == " ",
            }
        # TTF fallback (e.g. Hangul): size the em to the SDF font's cap height ratio
        fb = getattr(self, "cur_fallback", None) or self.fallback_path
        if fb:
            px = sz * 0.92
            f = ImageFont.truetype(fb, max(1, int(round(px * 4))))  # 4x for measuring
            adv = f.getlength(ch) / 4 + char_spacing * size * 0.01
            return {
                "kind": "tt",
                "ch": ch,
                "px": px,
                "adv": adv,
                "size": sz,
                "asc": font.asc * (size / font.point),
                "desc": font.desc * (size / font.point),
                "st": st,
                "space": ch == " ",
            }
        return None

    def layout(
        self,
        toks,
        font,
        width,
        smallcaps=False,
        upper=False,
        char_spacing=0.0,
        line_spacing=0.0,
        para_spacing=0.0,
        base_size=10.0,
        wrap=True,
    ):
        items = []
        for t in toks:
            if t[0] == "br":
                items.append({"kind": "br"})
                continue
            m = self.measure(t, font, smallcaps, upper, char_spacing)
            if m:
                items.append(m)
        # kerning between consecutive SDF chars
        for a, b in zip(items, items[1:], strict=False):
            if a.get("kind") == "ch" and b.get("kind") == "ch":
                kv = font.kern.get((a["gi"], b["gi"]))
                if kv:
                    a["adv"] += kv * a["s"]
        lines, cur, curw = [], [], 0.0
        word, wordw = [], 0.0

        def flush_word():
            nonlocal cur, curw, word, wordw
            if not word:
                return
            if wrap and cur and curw + wordw > width + 0.01:
                # drop trailing spaces of the current line
                while cur and cur[-1].get("space"):
                    curw -= cur[-1]["adv"]
                    cur.pop()
                lines.append(cur)
                cur, curw = [], 0.0
                while word and word[0].get("space"):
                    wordw -= word[0]["adv"]
                    word.pop(0)
            cur += word
            curw += wordw
            word, wordw = [], 0.0

        for it in items:
            if it["kind"] == "br":
                flush_word()
                lines.append(cur + [{"kind": "brk"}])
                cur, curw = [], 0.0
                continue
            if it.get("space"):
                flush_word()
                word, wordw = [it], it["adv"]
                flush_word()
                continue
            word.append(it)
            wordw += it["adv"]
        flush_word()
        lines.append(cur)
        # line metrics
        out = []
        y = 0.0
        prev_desc = None
        prev_brk = False
        maxw = 0.0
        for ln in lines:
            vis = [i for i in ln if i["kind"] in ("ch", "sp", "tt")]
            while vis and vis[-1].get("space"):
                vis.pop()
            asc = max(
                [i["asc"] + i["st"]["voffset"] * i["size"] for i in vis]
                + [font.asc * base_size / font.point]
            )
            desc = min(
                [i["desc"] + i["st"]["voffset"] * i["size"] for i in vis]
                + [font.desc * base_size / font.point]
            )
            w = sum(i["adv"] for i in vis)
            maxw = max(maxw, w)
            if prev_desc is None:
                base = asc
            else:
                step = max(font.line_h * base_size / font.point, asc - prev_desc)
                step += line_spacing * base_size * 0.01
                if prev_brk:
                    step += para_spacing * base_size * 0.01
                base = y + step
            out.append({"items": vis, "base": base, "asc": asc, "desc": desc, "w": w})
            y = base
            prev_desc = desc
            prev_brk = bool(ln and ln[-1].get("kind") == "brk")
        height = (out[-1]["base"] - out[-1]["desc"]) if out else 0.0
        return out, maxw, height

    def fit(self, text, font_name, rect_w, rect_h, size, smin, smax, autosize, **kw):
        font = self.font(font_name)
        sizes = [size]
        if autosize:
            s = smax
            sizes = []
            while s >= smin - 1e-6:
                sizes.append(s)
                s -= 0.5
        best = None
        for s in sizes:
            toks = parse_rich(text, s)
            lines, w, h = self.layout(toks, font, rect_w, base_size=s, **kw)
            best = (s, lines, w, h)
            if w <= rect_w + 0.5 and h <= rect_h + 0.5:
                break
        return best

    def draw(self, canvas, S, rect, text, tmp, clip, top_left_y, override_font=None):
        """rect in Unity coords; canvas top-left y = top_left_y - unity_y."""
        x, y, w, h = rect
        m = tmp.get("m_margin") or {}
        x += m.get("x", 0)
        w -= m.get("x", 0) + m.get("z", 0)
        h -= m.get("y", 0) + m.get("w", 0)
        y += m.get("w", 0)
        fname = override_font or tmp["m_fontAsset"].split(":", 1)[1]
        self.cur_fallback = tmp.get("_fallback") or self.fallback_path
        style = int(tmp.get("m_fontStyle", 0))
        kw = dict(
            smallcaps=bool(style & 32),
            upper=bool(style & 16),
            char_spacing=float(tmp.get("m_characterSpacing", 0.0)),
            line_spacing=float(tmp.get("m_lineSpacing", 0.0)),
            para_spacing=float(tmp.get("m_paragraphSpacing", 0.0)),
        )
        s, lines, tw, th = self.fit(
            text,
            fname,
            w,
            h,
            float(tmp["m_fontSize"]),
            float(tmp.get("m_fontSizeMin", 10)),
            float(tmp.get("m_fontSizeMax", 72)),
            bool(tmp.get("m_enableAutoSizing")),
            **kw,
        )
        font = self.font(fname)
        col = tmp.get("m_fontColor") or [1, 1, 1, 1]
        tint = tmp.get("m_Color") or [1, 1, 1, 1]
        color = [col[i] * tint[i] for i in range(4)]
        ha = int(tmp.get("m_HorizontalAlignment", 1))
        va = int(tmp.get("m_VerticalAlignment", 256))
        top = y + h  # unity top
        if va == 256:
            y0 = top
        elif va == 1024:
            y0 = y + th
        else:  # middle / geometry / capline
            y0 = top - (h - th) / 2.0
        bold_global = bool(style & 1)
        for ln in lines:
            if ha == 2:
                lx = x + (w - ln["w"]) / 2.0
            elif ha == 4:
                lx = x + w - ln["w"]
            else:
                lx = x
            base = y0 - ln["base"]  # unity y of baseline
            pen = lx
            for it in ln["items"]:
                st = it["st"]
                c = color
                if st.get("color"):
                    c = hex_color(st["color"], color[3])
                vo = st["voffset"] * it["size"]
                if it["kind"] == "ch":
                    if not it["space"]:
                        self._glyph(
                            canvas,
                            S,
                            font,
                            it,
                            pen,
                            base + vo,
                            c,
                            st["bold"] or bold_global,
                            clip,
                            top_left_y,
                        )
                elif it["kind"] == "tt":
                    self._ttf(canvas, S, it, pen, base + vo, c, clip, top_left_y)
                elif it["kind"] == "sp":
                    img = self.sprites.get(it["name"])
                    if img is not None:
                        bx = pen + it["bx"]
                        top_u = base + vo + it["asc"]
                        paste(
                            canvas,
                            S,
                            img,
                            (bx, top_u - it["h"], it["w"], it["h"]),
                            None,
                            clip,
                            top_left_y,
                        )
                pen += it["adv"]

    def _glyph(self, canvas, S, font, it, pen, base, color, bold, clip, top_left_y):
        g = it["g"]
        m, r = g["m_Metrics"], g["m_GlyphRect"]
        p = font.pad
        s = it["s"]
        # atlas crop (top-left origin), padded
        ax0 = r["m_X"] - p
        ay0 = font.H - (r["m_Y"] + r["m_Height"]) - p
        aw = r["m_Width"] + 2 * p
        ah = r["m_Height"] + 2 * p
        ux = pen + (m["m_HorizontalBearingX"] - p) * s
        utop = base + (m["m_HorizontalBearingY"] + p) * s
        uw, uh = aw * s, ah * s
        # target pixel box
        X0 = ux * S
        Y0 = (top_left_y - utop) * S
        W, H = uw * S, uh * S
        ix0, iy0 = int(math.floor(X0)), int(math.floor(Y0))
        iw, ih = int(math.ceil(X0 + W)) - ix0, int(math.ceil(Y0 + H)) - iy0
        if iw <= 0 or ih <= 0:
            return
        crop = font.atlas[int(ay0) : int(ay0 + ah), int(ax0) : int(ax0 + aw)]
        if crop.size == 0:
            return
        im = Image.fromarray((crop * 255).astype(np.uint8), "L")
        big = im.resize((max(1, int(round(W))), max(1, int(round(H)))), Image.BILINEAR)
        d = np.asarray(big).astype(np.float32) / 255.0
        spread = 2.0 * p * s * S  # px over which d goes 0..1
        edge = 0.5 - (0.07 if bold else 0.0)
        a = np.clip((d - edge) * spread + 0.5, 0, 1)
        layer = np.zeros((big.size[1], big.size[0], 4), np.float32)
        layer[..., 0] = color[0]
        layer[..., 1] = color[1]
        layer[..., 2] = color[2]
        layer[..., 3] = a * color[3]
        tile = Image.fromarray((layer * 255).astype(np.uint8), "RGBA")
        composite(canvas, tile, int(round(X0)), int(round(Y0)), clip, S, top_left_y)

    def _ttf(self, canvas, S, it, pen, base, color, clip, top_left_y):
        px = it["px"] * S
        f = ImageFont.truetype(
            getattr(self, "cur_fallback", None) or self.fallback_path,
            max(1, int(round(px))),
        )
        asc, _ = f.getmetrics()
        mask = f.getmask(it["ch"], mode="L")
        bbox = f.getbbox(it["ch"])
        im = Image.new("L", (max(1, bbox[2]), max(1, bbox[3])), 0)
        im.paste(Image.frombytes("L", mask.size, bytes(mask)), (bbox[0], bbox[1]))
        rgba = Image.new("RGBA", im.size, tuple(int(c * 255) for c in color[:3]) + (0,))
        rgba.putalpha(im.point(lambda v: int(v * color[3])))
        X0 = pen * S
        Y0 = (top_left_y - base) * S - asc
        composite(canvas, rgba, int(round(X0)), int(round(Y0)), clip, S, top_left_y)


def hex_color(h, alpha):
    h = h.lstrip("#")
    if len(h) >= 6:
        return [
            int(h[0:2], 16) / 255,
            int(h[2:4], 16) / 255,
            int(h[4:6], 16) / 255,
            (int(h[6:8], 16) / 255 if len(h) >= 8 else alpha),
        ]
    return [1, 1, 1, alpha]


# ---------------------------------------------------------------- drawing
def composite(canvas, tile, X, Y, clip, S, top_left_y):
    if clip is not None:
        cx0 = int(round(clip[0] * S))
        cy0 = int(round((top_left_y - (clip[1] + clip[3])) * S))
        cx1 = int(round((clip[0] + clip[2]) * S))
        cy1 = int(round((top_left_y - clip[1]) * S))
        # crop tile to clip
        lft, t = max(X, cx0), max(Y, cy0)
        r, b = min(X + tile.size[0], cx1), min(Y + tile.size[1], cy1)
        if r <= lft or b <= t:
            return
        tile = tile.crop((lft - X, t - Y, r - X, b - Y))
        X, Y = lft, t
    lft, t = max(X, 0), max(Y, 0)
    r, b = min(X + tile.size[0], canvas.size[0]), min(Y + tile.size[1], canvas.size[1])
    if r <= lft or b <= t:
        return
    canvas.alpha_composite(tile.crop((lft - X, t - Y, r - X, b - Y)), (lft, t))


def tint(img, color):
    if color is None or all(abs(c - 1) < 1e-3 for c in color):
        return img
    a = np.asarray(img).astype(np.float32)
    a[..., 0] *= color[0]
    a[..., 1] *= color[1]
    a[..., 2] *= color[2]
    a[..., 3] *= color[3]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def paste(canvas, S, img, urect, color, clip, top_left_y, preserve=False):
    x, y, w, h = urect
    if w <= 0 or h <= 0:
        return
    if preserve:
        iw, ih = img.size
        k = min(w / iw, h / ih)
        nw, nh = iw * k, ih * k
        x += (w - nw) / 2
        y += (h - nh) / 2
        w, h = nw, nh
    X = x * S
    Y = (top_left_y - (y + h)) * S
    W, H = max(1, int(round(w * S))), max(1, int(round(h * S)))
    im = img.resize((W, H), Image.LANCZOS)
    im = tint(im, color)
    composite(canvas, im, int(round(X)), int(round(Y)), clip, S, top_left_y)


def paste_sliced(canvas, S, img, border, urect, color, clip, top_left_y, ppu_mult=1.0):
    x, y, w, h = urect
    bl, bb, br, bt = border
    k = S / ppu_mult  # sprite px -> output px
    W, H = int(round(w * S)), int(round(h * S))
    if W <= 0 or H <= 0:
        return
    iw, ih = img.size
    L, R, T, B = (
        int(round(bl * k)),
        int(round(br * k)),
        int(round(bt * k)),
        int(round(bb * k)),
    )
    if L + R > W:
        L = R = W // 2
    if T + B > H:
        T = B = H // 2
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sx = [0, bl, iw - br, iw]
    sy = [0, bt, ih - bb, ih]
    dx = [0, L, W - R, W]
    dy = [0, T, H - B, H]
    for i in range(3):
        for j in range(3):
            s_box = (int(sx[i]), int(sy[j]), int(sx[i + 1]), int(sy[j + 1]))
            d_w, d_h = dx[i + 1] - dx[i], dy[j + 1] - dy[j]
            if s_box[2] <= s_box[0] or s_box[3] <= s_box[1] or d_w <= 0 or d_h <= 0:
                continue
            out.alpha_composite(
                img.crop(s_box).resize((d_w, d_h), Image.LANCZOS), (dx[i], dy[j])
            )
    out = tint(out, color)
    composite(
        canvas,
        out,
        int(round(x * S)),
        int(round((top_left_y - (y + h)) * S)),
        clip,
        S,
        top_left_y,
    )


# ---------------------------------------------------------------- tree walk
class CardRenderer:
    """Walks a tree; a node with a "custom" key is drawn by
    `custom(renderer, canvas, node, rect, clip, top)` after its image
    (app_cards.py's print-style text boxes)."""

    def __init__(self, sprites, text, S=1.0, custom=None):
        self.sp = sprites
        self.tx = text
        self.S = S
        self.custom = custom

    def render(self, tree, W=556, H=776):
        S = self.S
        canvas = Image.new("RGBA", (int(round(W * S)), int(round(H * S))), (0, 0, 0, 0))
        root_rect = (0, 0, W, H)
        rt = comp(tree, "RT")
        rect = resolve(root_rect, rt)
        self.top = rect[1] + rect[3]
        self.walk(canvas, tree, rect, None, self.top, 1.0)
        return canvas

    def walk(self, canvas, node, rect, clip, top, alpha):
        if not node.get("active", True):
            return
        cg = comp(node, "CanvasGroup")
        if cg and cg.get("alpha") is not None:
            alpha *= cg["alpha"]
        if alpha <= 0.001:
            return
        img = comp(node, "Image")
        if img and img.get("m_Sprite") and not node.get("hide_image"):
            name = img["m_Sprite"].split(":", 1)[1]
            source = (
                self.alt
                if node.get("inline") and getattr(self, "alt", None)
                else self.sp
            )
            sprite = source.get(name)
            col = list(img.get("m_Color") or [1, 1, 1, 1])
            col[3] *= alpha
            if sprite is not None and col[3] > 0.001:
                if img.get("m_Type") == 1:
                    meta = self.sp.meta.get(name, {})
                    paste_sliced(
                        canvas,
                        self.S,
                        sprite,
                        meta.get("border", [0, 0, 0, 0]),
                        rect,
                        col,
                        clip,
                        top,
                        img.get("m_PixelsPerUnitMultiplier", 1.0) or 1.0,
                    )
                else:
                    paste(
                        canvas,
                        self.S,
                        sprite,
                        rect,
                        col,
                        clip,
                        top,
                        preserve=bool(img.get("m_PreserveAspect")),
                    )
        if node.get("custom") and self.custom:
            self.custom(self, canvas, node, rect, clip, top)
        tmp = comp(node, "TextMeshProUGUI")
        if tmp and node.get("text") is not None and not node.get("custom"):
            t2 = dict(tmp)
            if node.get("fallback"):
                t2["_fallback"] = node["fallback"]
            if node.get("font_override"):
                t2["m_fontAsset"] = "MonoBehaviour:" + node["font_override"]
            t2.update(node.get("tmp_patch") or {})
            if t2.get("m_Color"):
                t2["m_Color"] = list(t2["m_Color"])
                t2["m_Color"][3] *= alpha
            self.tx.draw(canvas, self.S, rect, node["text"], t2, clip, top)
        if comp(node, "RectMask2D"):
            clip = intersect(clip, rect)
        kids = [ch for ch in node["children"] if ch.get("active", True)]
        rects = self.layout_children(node, rect, kids)
        for ch, r in zip(kids, rects, strict=False):
            self.walk(canvas, ch, r, clip, top, alpha)

    def layout_children(self, node, rect, kids):
        out = [resolve(rect, comp(ch, "RT")) for ch in kids]
        hl = comp(node, "HorizontalLayoutGroup")
        vl = comp(node, "VerticalLayoutGroup")
        lg = hl or vl
        if not lg or node.get("no_layout"):
            return out
        horiz = hl is not None
        pad = lg["m_Padding"]
        x0 = rect[0] + pad["m_Left"]
        x1 = rect[0] + rect[2] - pad["m_Right"]
        y1 = rect[1] + rect[3] - pad["m_Top"]  # unity top
        y0 = rect[1] + pad["m_Bottom"]
        avail_w, avail_h = x1 - x0, y1 - y0
        parts = []
        for ch, r in zip(kids, out, strict=False):
            le = comp(ch, "LayoutElement")
            if le and le.get("m_IgnoreLayout"):
                parts.append(None)
                continue
            w, h = r[2], r[3]
            if lg["m_ChildControlWidth"]:
                pw = le.get("m_PreferredWidth", -1) if le else -1
                w = (
                    pw
                    if pw and pw > 0
                    else (ch.get("pref_w") or (avail_w if horiz else avail_w))
                )
            if lg["m_ChildControlHeight"]:
                ph = le.get("m_PreferredHeight", -1) if le else -1
                h = ph if ph and ph > 0 else (ch.get("pref_h") or avail_h)
            parts.append([w, h])
        sp = lg["m_Spacing"]
        live = [p for p in parts if p]
        if horiz:
            total = sum(p[0] for p in live) + sp * max(0, len(live) - 1)
        else:
            total = sum(p[1] for p in live) + sp * max(0, len(live) - 1)
        al = lg["m_ChildAlignment"]  # 0 UL,1 UC,2 UR,3 ML,4 MC,5 MR,6 LL,7 LC,8 LR
        col, row = al % 3, al // 3
        if horiz:
            start = x0 + (avail_w - total) * [0, 0.5, 1][col]
        else:
            start = y1 - (avail_h - total) * [0, 0.5, 1][row]
        cur = start
        res = []
        for (_ch, r), p in zip(zip(kids, out, strict=False), parts, strict=False):
            if p is None:
                res.append(r)
                continue
            w, h = p
            if horiz:
                cy = y1 - (avail_h - h) * [0, 0.5, 1][row]
                res.append((cur, cy - h, w, h))
                cur += w + sp
            else:
                cx = x0 + (avail_w - w) * [0, 0.5, 1][col]
                res.append((cx, cur - h, w, h))
                cur -= h + sp
        # nested rects of a re-laid child must be recomputed relative to its new rect
        return res


def find(node, name):
    if node["name"] == name:
        return node
    for ch in node["children"]:
        r = find(ch, name)
        if r:
            return r
    return None


def find_all(node, name, acc=None):
    acc = [] if acc is None else acc
    if node["name"] == name:
        acc.append(node)
    for ch in node["children"]:
        find_all(ch, name, acc)
    return acc
