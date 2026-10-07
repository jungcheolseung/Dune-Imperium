"""Pictures for the play UI from the installed Steam Dune: Imperium app.

The app keeps its pictures in Unity Addressables bundles
(``StreamingAssets/aa/StandaloneOSX/*.bundle``) and ``resources.assets``.
This tool indexes them, saves named sprites as PNG and writes the play UI's
icon set. Nothing it reads or writes goes into this repository: the index and
the render inputs stay in the assets checkout's git-ignored
``reference/dune-steam-app/<build-guid>/render/``; only the finished pictures
the play UI shows (``icons/``, ``tokens/``, card faces) go into the private
assets repository (user decision, 2026-10-07).

Usage (from ``scripts/dwgr``)::

    uv run --no-project --with UnityPy python app_assets.py index
    uv run --no-project --with UnityPy python app_assets.py icons
    uv run --no-project --with UnityPy python app_assets.py sprites OUT NAME...
    uv run --no-project --with UnityPy python app_assets.py prefabs OUT NAME...
    uv run --no-project --with UnityPy python app_assets.py fonts OUT

``IL2CPP_APP`` picks the app as for the other tools (default here: ``dune``).
"""

import argparse
import gc
import hashlib
import json
import os
import re
import struct
import sys

import UnityPy

STEAM = "~/Library/Application Support/Steam/steamapps/common/"
APPS = {"dune": STEAM + "Dune Imperium/DuneImperium.app/Contents"}
APP = os.environ.get("IL2CPP_APP") or "dune"
CONTENTS = os.path.expanduser(APPS.get(APP, APP))
DATA_DIR = os.path.join(CONTENTS, "Resources", "Data")
BUNDLE_DIR = os.path.join(DATA_DIR, "StreamingAssets", "aa", "StandaloneOSX")
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ASSETS = os.path.join(REPO, "assets")
# Files that are not bundles but hold sprites the cards use.
LOOSE_FILES = ("resources.assets", "globalgamemanagers.assets", "sharedassets0.assets")
# Bundles above this size hold only the challenge illustrations; skipping them
# keeps the index run under 2 GB of memory.
MAX_BUNDLE_BYTES = 100_000_000

# Play UI icon name (dune_imperium.display.icons.ICON_NAMES) -> app sprite.
# Same artwork as the rulebook icons, 2-3x the pixels. Names missing here keep
# the rulebook crop (scripts/extract_rulebook_icons.py).
APP_ICON_SOURCES = {
    "agent": "Agent",
    "battle_crysknife": "hud_Icon_Conflict_Knife",
    "battle_ornithopter": "hud_Icon_Conflict_Thopter",
    "battle_desert_mouse": "hud_Icon_Conflict_Mouse",
    "battle_wild": "hud_Icon_Conflict_Wild",
    "contract": "Contract",
    "control": "ControlMarkerNeutral",
    "discard": "UI_crd_Discard",
    "draw": "UI_crd_ActionIcon_DrawCard",
    "intrigue": "UI_crd_ActionIcon_IntrigueCard",
    "influence_emperor": "UI_crd_ActionIcon_FactionEmperorUp",
    "influence_spacing_guild": "UI_crd_ActionIcon_FactionSpacingGuildUp",
    "influence_bene_gesserit": "UI_crd_ActionIcon_FactionBeneGesseritUp",
    "influence_fremen": "UI_crd_ActionIcon_FactionFremenUp",
    "influence_any": "UI_crd_ActionIcon_FactionWildUp",
    "influence_any_two": "UI_crd_ActionIcon_FactionWildUp2",
    "influence_lose": "UI_crd_ActionIcon_FactionWildDown",
    "maker": "BonusSpice",
    "maker_hooks": "UI_crd_ActionIcon_MakerHook",
    "arrow_right": "UI_crd_CostIcon_IfThenArrow_Large",
    "arrow_down": "ArrowDown",
    "persuasion": "UI_crd_ActionIcon_Persuasion",
    "recall_agent": "UI_crd_ActionIcon_AgentRecall",
    "recall_spy": "UI_crd_ActionIcon_SpyRecall",
    "solari": "hud_Icon_ResourceCoin",
    "spice": "UI_crd_ActionIcon_Spice",
    "water": "UI_crd_CostIcon_Water",
    "sandworm": "UI_crd_ActionIcon_Worm",
    "shield_wall": "UI_crd_ActionIcon_BlowWall",
    "signet_ring": "UI_crd_ActionIcon_SignetRing",
    "spy": "UI_crd_ActionIcon_Spy",
    "sword": "UI_crd_ActionIcon_Strength",
    "trash_intrigue": "UI_crd_ActionIcon_IntrigueTrash",
    "trash": "UI_crd_ActionIcon_TrashCard",
    "troop": "Troop",
    "victory_point": "UI_crd_ActionIcon_VictoryPoint",
    "agent_icon_emperor": "UI_crd_ActionFaction_Emperor",
    "agent_icon_spacing_guild": "UI_crd_ActionFaction_SpacingGuild",
    "agent_icon_bene_gesserit": "UI_crd_ActionFaction_BeneGesserit",
    "agent_icon_fremen": "UI_crd_ActionFaction_Fremen",
    "agent_icon_landsraad": "UI_crd_ActionAct_Landsraad",
    "agent_icon_city": "UI_crd_ActionAct_PopulationCenter",
    "agent_icon_spice_trade": "UI_crd_ActionAct_Commerce",
    "agent_icon_spy": "UI_crd_ActionFaction_Spy",
    "specimen": "Specimen",
}


def build_guid():
    for line in open(os.path.join(DATA_DIR, "boot.config")):
        if line.startswith("build-guid="):
            return line.strip().split("=", 1)[1]
    raise SystemExit("no build-guid in boot.config")


def cache_dir():
    return os.path.join(ASSETS, "reference", "dune-steam-app", build_guid(), "render")


def file_path(name):
    return (
        os.path.join(BUNDLE_DIR, name)
        if name.endswith(".bundle")
        else os.path.join(DATA_DIR, name)
    )


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_pptr(x):
    return type(x).__name__ == "PPtr"


# ---------------------------------------------------------------- index
def cmd_index(_args):
    """Scan every bundle once: CAB names, container paths, picture names, sizes."""
    files = sorted(f for f in os.listdir(BUNDLE_DIR) if f.endswith(".bundle"))
    files = [f for f in files if os.path.getsize(file_path(f)) <= MAX_BUNDLE_BYTES]
    files += [f for f in LOOSE_FILES if os.path.exists(file_path(f))]
    cab, containers, pictures = {}, {}, {}
    for n, f in enumerate(files, 1):
        env = UnityPy.load(file_path(f))
        if f.endswith(".bundle"):
            for bf in env.files.values():
                for name in getattr(bf, "files", {}):
                    if isinstance(name, str):
                        cab[name.lower()] = f
        for path in env.container.keys():
            containers[path] = f
        rows = []
        for obj in env.objects:
            t = obj.type.name
            if t not in ("Sprite", "Texture2D"):
                continue
            try:
                d = obj.read()
            except Exception:  # an odd object must not stop the index
                continue
            if t == "Sprite":
                rows.append(
                    ["S", d.m_Name, round(d.m_Rect.width), round(d.m_Rect.height)]
                )
            else:
                rows.append(["T", d.m_Name, d.m_Width, d.m_Height])
        pictures[f] = rows
        del env
        gc.collect()
        if n % 50 == 0:
            print(f"{n}/{len(files)}", flush=True)
    out = cache_dir()
    os.makedirs(out, exist_ok=True)
    json.dump(
        {
            "build_guid": build_guid(),
            "cab": cab,
            "containers": containers,
            "pictures": pictures,
        },
        open(os.path.join(out, "index.json"), "w"),
    )
    print("index:", os.path.join(out, "index.json"), len(files), "files")


def load_index():
    path = os.path.join(cache_dir(), "index.json")
    if not os.path.exists(path):
        raise SystemExit("run `app_assets.py index` first")
    return json.load(open(path))


# ---------------------------------------------------------------- loader
class App:
    """A UnityPy environment that loads dependency bundles when a PPtr needs one."""

    def __init__(self, index=None):
        self.index = index or load_index()
        self.env = UnityPy.load()
        self.loaded = set()
        self.scripts = {}

    def load(self, f):
        if f not in self.loaded:
            self.env.load_file(file_path(f))
            self.loaded.add(f)

    def serialized(self, cab_name):
        f = self.index["cab"].get(cab_name.lower())
        if f is None:
            return None
        self.load(f)
        for bf in list(self.env.files.values()):
            for name, sf in list(getattr(bf, "files", {}).items()):
                if name.lower() == cab_name.lower() and hasattr(sf, "objects"):
                    return sf
        return None

    def container(self, path):
        self.load(self.index["containers"][path])
        ptr = self.env.container[path]
        return ptr.deref() if is_pptr(ptr) else ptr

    def deref(self, owner, pptr):
        fid, pid = pptr["m_FileID"], pptr["m_PathID"]
        if pid == 0:
            return None
        sf = owner.assets_file
        if fid != 0:
            sf = self.serialized(sf.externals[fid - 1].path.split("/")[-1])
            if sf is None:
                return None
        return sf.objects.get(pid)

    def script_name(self, reader, tt):
        key = (
            reader.assets_file.name,
            tt["m_Script"]["m_FileID"],
            tt["m_Script"]["m_PathID"],
        )
        if key not in self.scripts:
            obj = self.deref(reader, tt["m_Script"])
            self.scripts[key] = obj.read().m_ClassName if obj else "?"
        return self.scripts[key]

    def picture(self, name, prefer=None):
        """(reader, kind) for a sprite (preferred) or texture called `name`."""
        hits = []
        for f, rows in self.index["pictures"].items():
            for kind, n, _w, _h in rows:
                if n == name:
                    hits.append((kind != "S", f != prefer, f, kind))
        want = {"S": "Sprite", "T": "Texture2D"}
        for _k, _p, f, kind in sorted(hits):
            self.load(f)
            for sf in self.serialized_files(f):
                for obj in sf.objects.values():
                    if obj.type.name == want[kind] and obj.peek_name() == name:
                        return obj, kind
        return None, None

    def serialized_files(self, f):
        for key, bf in list(self.env.files.items()):
            if os.path.basename(key) != f:
                continue
            if hasattr(bf, "objects"):
                yield bf
            for sf in list(getattr(bf, "files", {}).values()):
                if hasattr(sf, "objects"):
                    yield sf

    def save_picture(self, name, path, prefer=None):
        """Save one sprite/texture as PNG; return sprite meta (border etc.) or {}."""
        while True:
            obj, kind = self.picture(name, prefer)
            if obj is None:
                return None
            d = obj.read()
            try:
                d.image.save(path)
            except FileNotFoundError as e:
                m = re.search(r"(?:Resource )?[Ff]ile (\S+) not found", str(e))
                name_ = m.group(1) if m else ""
                dep = self.index["cab"].get(name_.lower())
                if dep is None and os.path.exists(os.path.join(DATA_DIR, name_)):
                    dep = name_  # a loose .resS beside resources.assets
                if dep and dep not in self.loaded:
                    self.load(dep)
                    continue
                raise
            return sprite_meta(d) if kind == "S" else {}


def sprite_meta(d):
    """What drawing a sprite needs besides its pixels. ``offset`` places the
    saved texture inside ``rect``: the atlas trims transparent margins, and
    Unity still lays the whole rect over the RectTransform (the Tleilaxu
    header mask is 808x1154 of a 955x1301 sprite, inset to the card border)."""
    b = d.m_Border
    off = d.m_RD.textureRectOffset
    return {
        "border": [b.x, b.y, b.z, b.w],
        "rect": [d.m_Rect.width, d.m_Rect.height],
        "pivot": [d.m_Pivot.x, d.m_Pivot.y],
        "offset": [off.x, off.y],
    }


def cmd_sprite_meta(args):
    """Refresh _meta.json for the sprites already saved in a folder, without
    decoding any texture."""
    app = App()
    meta_path = os.path.join(args.out, "_meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    done = 0
    for f in sorted(os.listdir(args.out)):
        name = f[:-4]
        if not f.endswith(".png") or name.startswith("_"):
            continue
        obj, kind = app.picture(name)
        if obj is not None and kind == "S":
            meta[name] = sprite_meta(obj.read())
            done += 1
    json.dump(meta, open(meta_path, "w"), indent=0)
    print("sprite meta:", done)


def cmd_sprites(args):
    app = App()
    os.makedirs(args.out, exist_ok=True)
    meta_path = os.path.join(args.out, "_meta.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    names = list(args.names)
    for lst in args.list or []:
        names += json.load(open(lst))
    missing = []
    for name in names:
        m = app.save_picture(name, os.path.join(args.out, name + ".png"), args.prefer)
        if m is None:
            missing.append(name)
        elif m:
            meta[name] = m
    json.dump(meta, open(meta_path, "w"), indent=0)
    print("saved", len(names) - len(missing), "missing", missing)


def cmd_icons(args):
    app = App()
    out = args.out or os.path.join(ASSETS, "icons")
    os.makedirs(out, exist_ok=True)
    rows = {}
    for name, sprite in APP_ICON_SOURCES.items():
        path = os.path.join(out, name + ".png")
        if app.save_picture(sprite, path) is None:
            print("missing", name, sprite)
            continue
        rows[name] = {"sprite": sprite, "sha256": sha256(path)}
    json.dump(
        {"build_guid": build_guid(), "icons": rows},
        open(os.path.join(out, "app_sources.json"), "w"),
        indent=1,
        sort_keys=True,
    )
    print("icons:", len(rows), "->", out)


# Seat pieces on the board (dune_imperium.display.token_images.SEAT_PIECE_KINDS)
# -> app sprite, {C} = the app's colour name. The Agent is the Swordmaster
# sprite: the same figure as hud_Icon_Player_Agent_{C} (mask overlap 98 %) at
# three times the pixels. The app has no coloured Spy, only its grey cylinder,
# which is tinted with that colour's troop cube (the "tint" column).
APP_PIECE_SOURCES = {
    "agent": "SwordMasterIcon_{C}",
    "spy": "Spy",
    "control": "ControlMarker{C}",
    "troop": "Icon_Resource_Cube_{C}",
    "sandworm": "Icon_Resource_Worm_{C}",
}
# Seat order of display.token_images.STRENGTH_TOKEN_COLORS -> app colour name.
APP_PIECE_COLORS = {"blue": "Blue", "red": "Red", "green": "Green", "yellow": "Yellow"}


def cube_color(path):
    """The saturated colour of a troop cube picture (median of its coloured pixels)."""
    from PIL import Image

    raw = Image.open(path).convert("RGBA").tobytes()
    px = [raw[i : i + 4] for i in range(0, len(raw), 4)]
    px = [p for p in px if p[3] > 200 and max(p[:3]) - min(p[:3]) > 60]
    return tuple(sorted(c[i] for c in px)[len(px) // 2] for i in range(3))


def cmd_pieces(args):
    from PIL import Image, ImageChops

    app = App()
    out = args.out or os.path.join(ASSETS, "tokens")
    os.makedirs(out, exist_ok=True)
    rows = {}
    for kind, pattern in APP_PIECE_SOURCES.items():
        for color, app_color in APP_PIECE_COLORS.items():
            sprite = pattern.format(C=app_color)
            path = os.path.join(out, f"{kind}_{color}.png")
            if app.save_picture(sprite, path) is None:
                print("missing", kind, sprite)
                continue
            im = Image.open(path).convert("RGBA")
            row = {"sprite": sprite}
            if "{C}" not in pattern:
                cube = os.path.join(out, f"troop_{color}.png")
                if not os.path.exists(cube):
                    app.save_picture(f"Icon_Resource_Cube_{app_color}", cube)
                tint = cube_color(cube)
                alpha = im.getchannel("A")
                im = ImageChops.multiply(im, Image.new("RGBA", im.size, tint + (255,)))
                im.putalpha(alpha)
                row["tint"] = "#{:02x}{:02x}{:02x}".format(*tint)
            im = im.crop(im.getchannel("A").getbbox())  # the figure fills its box
            im.save(path)
            row["sha256"] = sha256(path)
            rows[f"{kind}_{color}"] = row
    json.dump(
        {"build_guid": build_guid(), "pieces": rows},
        open(os.path.join(out, "app_sources.json"), "w"),
        indent=1,
        sort_keys=True,
    )
    print("pieces:", len(rows), "->", out)


# ---------------------------------------------------------------- prefabs
SKIP_KEYS = {
    "m_GameObject",
    "m_Enabled",
    "m_EditorHideFlags",
    "m_EditorClassIdentifier",
    "m_Script",
    "m_Name",
    "m_OnCullStateChanged",
    "m_RaycastPadding",
    "m_RaycastTarget",
    "m_Maskable",
    "m_Material",
    "m_fontSharedMaterials",
    "m_fontMaterial",
    "m_fontMaterials",
    "m_spriteAsset",
    "m_StyleSheet",
    "m_TextStyleHashCode",
    "m_ActiveFontFeatures",
    "m_havePropertiesChanged",
    "m_isUsingLegacyAnimationComponent",
    "m_VertexBufferAutoSizeReduction",
    "m_isInputParsingRequired",
    "m_inputSource",
    "m_hasFontAssetChanged",
    "m_baseMaterial",
    "m_maskOffset",
    "m_renderer",
    "m_subTextObjects",
    "m_isVolumetricText",
    "m_IsTextObjectScaleStatic",
    "m_isRightToLeft",
    "m_isOrthographic",
    "m_isCullingEnabled",
    "m_horizontalMapping",
    "m_verticalMapping",
    "m_uvLineOffset",
    "m_geometrySortingOrder",
    "m_parseCtrlCharacters",
    "m_ignoreCulling",
    "m_EmojiFallbackSupport",
    "m_isAlignmentEnumConverted",
    "m_enableExtraPadding",
    "checkPaddingRequired",
    "m_isRichText",
    "m_overrideHtmlColors",
    "m_tintAllSprites",
    "m_faceColor",
    "m_outlineColor",
    "m_fontColor32",
    "m_enableVertexGradient",
    "m_colorMode",
    "m_fontColorGradient",
    "m_fontColorGradientPreset",
    "m_TextProcessingMode",
}


def dump_component(app, c):
    t = c.type.name
    if t == "RectTransform":
        r = c.read()
        return {
            "_": "RT",
            "pos": [r.m_AnchoredPosition.x, r.m_AnchoredPosition.y],
            "size": [r.m_SizeDelta.x, r.m_SizeDelta.y],
            "amin": [r.m_AnchorMin.x, r.m_AnchorMin.y],
            "amax": [r.m_AnchorMax.x, r.m_AnchorMax.y],
            "pivot": [r.m_Pivot.x, r.m_Pivot.y],
            "scale": [r.m_LocalScale.x, r.m_LocalScale.y],
            "rot": [
                r.m_LocalRotation.x,
                r.m_LocalRotation.y,
                r.m_LocalRotation.z,
                r.m_LocalRotation.w,
            ],
        }
    if t == "CanvasGroup":
        tt = c.read_typetree()
        out = {"_": "CanvasGroup", "alpha": tt.get("m_Alpha")}
        if tt.get("m_Enabled") == 0:
            out["enabled"] = False
        return out
    if t != "MonoBehaviour":
        return {"_": t}
    tt = c.read_typetree()
    out = {"_": app.script_name(c, tt)}
    if tt.get("m_Enabled") == 0:
        # a switched-off component draws, masks and lays out nothing
        # (Tleilaxu cards switch off the Imperium title band)
        out["enabled"] = False
    for k, v in tt.items():
        if k in SKIP_KEYS:
            continue
        if isinstance(v, dict) and set(v) == {"m_FileID", "m_PathID"}:
            if v["m_PathID"] == 0:
                continue
            o = app.deref(c, v)
            out[k] = f"{o.type.name}:{o.peek_name()}" if o is not None else "?ext"
            continue
        if isinstance(v, dict) and {"r", "g", "b", "a"} <= set(v):
            out[k] = [round(v[x], 3) for x in "rgba"]
            continue
        if isinstance(v, (dict, list)) and len(json.dumps(v, default=str)) > 300:
            continue
        out[k] = v
    return out


def dump_tree(app, go_reader):
    go_reader = go_reader.deref() if is_pptr(go_reader) else go_reader
    go = go_reader.read()
    node = {
        "name": go.m_Name,
        "active": bool(go.m_IsActive),
        "comps": [],
        "children": [],
    }
    transform = None
    for cp in go.m_Component:
        c = cp.component if hasattr(cp, "component") else cp
        c = c.deref() if is_pptr(c) else c
        try:
            node["comps"].append(dump_component(app, c))
        except Exception as e:  # keep the tree even if one component fails
            node["comps"].append({"_": "ERR", "e": repr(e)[:120]})
        if c.type.name in ("RectTransform", "Transform"):
            transform = c.read()
    if transform:
        for ch in transform.m_Children:
            node["children"].append(dump_tree(app, ch.read().m_GameObject))
    return node


def cmd_prefabs(args):
    app = App()
    os.makedirs(args.out, exist_ok=True)
    names = list(args.names)
    if args.all_cards:
        names += sorted(
            p
            for p in app.index["containers"]
            if p.startswith("UI_crd_") and p.endswith(".prefab")
        )
    for name in names:
        root = app.container(name)
        json.dump(
            dump_tree(app, root),
            open(os.path.join(args.out, name + ".json"), "w"),
            indent=1,
            default=str,
        )
        # nested element templates the dynamic card views instantiate
        if name == "UI_crd_Imperium_Dynamic.prefab":
            col = find_go(root, "UI_crd_Element_ActionColumn_Dynamic")
            for cp in col.read().m_Component:
                c = cp.component.deref() if is_pptr(cp.component) else cp.component
                if c.type.name != "MonoBehaviour":
                    continue
                tt = c.read_typetree()
                for item in tt.get("list", [])[:1]:
                    for key in ("obj", "infiltrateObj"):
                        go = app.deref(c, item[key])
                        json.dump(
                            dump_tree(app, go),
                            open(os.path.join(args.out, f"ActionIcon_{key}.json"), "w"),
                            indent=1,
                            default=str,
                        )
    print("prefabs:", len(names), "->", args.out)


def find_go(go_reader, name):
    go_reader = go_reader.deref() if is_pptr(go_reader) else go_reader
    go = go_reader.read()
    if go.m_Name == name:
        return go_reader
    for cp in go.m_Component:
        c = cp.component.deref() if is_pptr(cp.component) else cp.component
        if c.type.name == "RectTransform":
            for ch in c.read().m_Children:
                r = find_go(ch.read().m_GameObject, name)
                if r:
                    return r
    return None


# ---------------------------------------------------------------- card inputs
INLINE_BUNDLE = "bfceeebef0fc453d153f5c466493ae23.bundle"  # TMP sprite glyph pictures
CARD_SPRITE_PREFIXES = (
    "UI_ill_",
    "UI_crd_",
    "Icon_cost_",
    "UI_icon_Research",
    "hud_Icon_Conflict",
    "hud_Icon_ShieldWall",
)


def cmd_card_inputs(_args):
    """Everything app_cards.py reads: prefab trees, fonts, loc, sprites."""
    out = cache_dir()
    app = App()
    prefabs = os.path.join(out, "prefabs")
    cmd_prefabs(argparse.Namespace(out=prefabs, names=[], all_cards=True))
    cmd_fonts(argparse.Namespace(out=os.path.join(out, "fonts")))
    cmd_loc(None)
    names = set()
    for f in os.listdir(prefabs):
        walk_sprites(json.load(open(os.path.join(prefabs, f))), names)
    for rows in app.index["pictures"].values():
        for kind, n, _w, _h in rows:
            if kind == "S" and n.startswith(CARD_SPRITE_PREFIXES):
                names.add(n)
    assets = json.load(open(os.path.join(out, "fonts", "sprite_assets.json")))
    cmd_sprites(
        argparse.Namespace(
            out=os.path.join(out, "sprites"),
            names=sorted(names),
            list=None,
            prefer=None,
        )
    )
    # Inline glyph pictures, cut from each sprite asset's sheet by glyph rect
    # and saved under the glyph (character) name the card strings use.
    from PIL import Image  # UnityPy depends on Pillow

    inline_dir = os.path.join(out, "inline")
    os.makedirs(inline_dir, exist_ok=True)
    sheets = {}
    missing = []
    for asset in assets.values():
        for char, glyph in asset.items():
            sheet = glyph["sheet"]
            if sheet not in sheets:
                path = os.path.join(out, f"_sheet_{sheet}.png")
                saved = app.save_picture(sheet, path, "resources.assets")
                sheets[sheet] = Image.open(path) if saved is not None else None
            img = sheets[sheet]
            if img is None:
                missing.append(char)
                continue
            x, y, w, h = glyph["rect"]
            box = (x, img.height - y - h, x + w, img.height - y)
            img.crop(box).save(os.path.join(inline_dir, char + ".png"))
    print("inline glyphs missing:", missing)


def walk_sprites(node, acc):
    for c in node["comps"]:
        v = c.get("m_Sprite")
        if isinstance(v, str) and v.startswith("Sprite:"):
            acc.add(v.split(":", 1)[1])
    for ch in node["children"]:
        walk_sprites(ch, acc)


# ---------------------------------------------------------------- loc
def cmd_loc(args):
    """The app's English strings (key=value TextAssets) as render/loc_en_US.json.

    Only English: the app's Korean translation differs from the official
    Korean edition and is not used (user decision, 2026-10-07).
    """
    env = UnityPy.load(
        os.path.join(DATA_DIR, "StreamingAssets", "Localization", "osx", "localization")
    )
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        d = obj.read()
        if d.m_Name != "en_US":
            continue
        text = (
            d.m_Script
            if isinstance(d.m_Script, str)
            else bytes(d.m_Script).decode("utf-8")
        )
        table = {}
        for line in text.splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                table[k.strip()] = v
        out = os.path.join(cache_dir(), "loc_en_US.json")
        json.dump(table, open(out, "w"), ensure_ascii=False, indent=0)
        print("loc:", len(table), "strings ->", out)


# ---------------------------------------------------------------- fonts
FONTS = (
    "Gotham-Book SDF",
    "Gotham-Medium SDF",
    "Gotham-Bold SDF",
    "Overpass-Medium SDF",
    "InterstateCondensed-Light SDF",
    "TrajanPro-Bold SDF",
)


def cmd_fonts(args):
    """TextMeshPro SDF fonts (tables, atlas) and TMP sprite asset glyph metrics."""
    app = App()
    os.makedirs(args.out, exist_ok=True)
    readers = {}
    app.load(INLINE_BUNDLE)
    for sf in app.serialized_files(INLINE_BUNDLE):
        for obj in sf.objects.values():
            if obj.type.name == "MonoBehaviour" and obj.peek_name() in FONTS:
                readers[obj.peek_name()] = obj
    for name in FONTS:
        reader = readers[name]
        tt = reader.read_typetree()
        atlases = []
        for i, p in enumerate(tt["m_AtlasTextures"]):
            tex = app.deref(reader, p).read()
            fn = f"{name}_{i}.png"
            tex.image.save(os.path.join(args.out, fn))
            atlases.append([fn, tex.m_Width, tex.m_Height])
        json.dump(
            {
                "name": name,
                "face": tt["m_FaceInfo"],
                "padding": tt.get("m_AtlasPadding"),
                "atlas": atlases,
                "glyphs": tt["m_GlyphTable"],
                "chars": tt["m_CharacterTable"],
                "kerning": (tt.get("m_FontFeatureTable") or {}).get(
                    "m_GlyphPairAdjustmentRecords", []
                ),
            },
            open(os.path.join(args.out, name + ".json"), "w"),
            default=str,
        )
        print("font", name, len(tt["m_GlyphTable"]), "glyphs")
    json.dump(
        sprite_assets(),
        open(os.path.join(args.out, "sprite_assets.json"), "w"),
        indent=0,
    )


def sprite_assets():
    """Parse the TMP sprite assets in resources.assets by hand.

    resources.assets carries no type trees and the IL2CPP type tree generator
    cannot read metadata v39, so the serialized TMP_SpriteAsset layout is read
    directly: name, version "1.1.0", then the sprite character table
    (elementType, unicode, glyphIndex, scale, name) and the glyph table
    (index, metrics x5, rect x4, scale, atlasIndex, classDefinitionType,
    sprite PPtr = 64 bytes).
    """
    env = UnityPy.load(file_path("resources.assets"))
    out = {}
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        b = obj.get_raw_data()
        if len(b) < 0x60:
            continue
        o = 0x1C
        ln = struct.unpack_from("<I", b, o)[0]
        if ln > 64:
            continue
        name = b[o + 4 : o + 4 + ln].decode("utf-8", "replace")
        o = (o + 4 + ln + 3) & ~3
        if struct.unpack_from("<I", b, o)[0] != 5 or b[o + 4 : o + 9] != b"1.1.0":
            continue
        i = b.find(bytes.fromhex("02000000feff0000"))
        if i < 0:
            continue
        o = i - 4
        n = struct.unpack_from("<I", b, o)[0]
        o += 4
        chars = []
        for _ in range(n):
            _et, _uni, gi, sc, nl = struct.unpack_from("<IIIfI", b, o)
            o += 20
            chars.append((b[o : o + nl].decode(), gi, sc))
            o = (o + nl + 3) & ~3
        g = struct.unpack_from("<I", b, o)[0]
        o += 4
        glyphs = {}
        for _ in range(g):
            idx, w, h, bx, by, adv, rx, ry, rw, rh, gs, _ai, _cd, _fid, _pid = (
                struct.unpack_from("<I5f4ifiiiq", b, o)
            )
            o += 64
            # The picture is the glyph rect on the asset's sprite sheet (a
            # texture of the asset's own name); the sprite PPtr is often a
            # placeholder shared by many glyphs.
            glyphs[idx] = {
                "w": w,
                "h": h,
                "bx": bx,
                "by": by,
                "adv": adv,
                "scale": gs,
                "rect": [rx, ry, rw, rh],
                "sheet": name,
            }
        out[name] = {
            nm: dict(glyphs[gi], cscale=sc) for nm, gi, sc in chars if gi in glyphs
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index").set_defaults(fn=cmd_index)
    p = sub.add_parser("sprites")
    p.add_argument("out")
    p.add_argument("names", nargs="*")
    p.add_argument("--list", action="append", help="JSON file with a list of names")
    p.add_argument("--prefer", help="bundle to prefer when several hold the name")
    p.set_defaults(fn=cmd_sprites)
    p = sub.add_parser("icons")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_icons)
    p = sub.add_parser("sprite-meta")
    p.add_argument("out")
    p.set_defaults(fn=cmd_sprite_meta)
    p = sub.add_parser("pieces")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_pieces)
    p = sub.add_parser("prefabs")
    p.add_argument("out")
    p.add_argument("names", nargs="*")
    p.add_argument("--all-cards", action="store_true")
    p.set_defaults(fn=cmd_prefabs)
    sub.add_parser("loc").set_defaults(fn=cmd_loc)
    sub.add_parser("card-inputs").set_defaults(fn=cmd_card_inputs)
    p = sub.add_parser("fonts")
    p.add_argument("out")
    p.set_defaults(fn=cmd_fonts)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
