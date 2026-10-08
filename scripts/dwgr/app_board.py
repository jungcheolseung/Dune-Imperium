"""Board-space tiles for the play UI, drawn from the Steam app's 3D board.

The app keeps no picture of a board space. Its board is the Addressables scene
``Playmat`` (``SCENE_CAB`` inside ``SCENE_BUNDLE``), and each space is a small
tree of flat meshes lying in the XY plane under a top-down camera:

- ``Root/Frame``: the chamfered frame mesh (``G_frm_BoardSpace``, the shorter
  ``G_frm_BoardSpace_Track`` on Faction spaces, a wide one on High Council).
  Its URP Unlit material samples a 256x256 ``T_frm_BoardSpace*`` texture that
  holds two spaces, one per 108-row strip; the material's v offset (+/-
  ``STRIP_V_OFFSET``) picks the top or the bottom strip.
- ``G_icon_*`` meshes: every icon is its own silhouette mesh whose UVs cut the
  picture out of an icon atlas (``T_icon_BoardSpaces_1..4``).
- TextMeshPro 3D text for the numbers on the icons and the word "OR".

``inputs`` copies what that takes out of the app with UnityPy (it cannot open
a scene through the container, so it walks the scene's root Transforms):
the space subtrees, every referenced mesh in Unity coordinates, the textures
and the TMP fonts. ``render`` then rasterises a space without UnityPy:
combined affine transforms, painter's order by z, per-triangle UV sampling
with the material's tiling/offset, 2x supersampling and a LANCZOS downscale,
transparent around the frame (icons standing over its edge are kept).

The scene is a live game board, so some parts are switched by game state.
The tiles show the state the printed board shows (owner-approved reconcile,
2026-10-08; see ``fix_static_state``). Korean tiles change only the word "OR"
(to the Korean edition's "또는" in NanumBarunGothic Bold; the app's own Korean
translation is never used). Tuek's Sietch (Bloodlines) is not in the app; it
is composed from app parts in the layout of the app's Hagga Basin with the
printed tile's art (``tueks_sietch_tree``).

Inputs go to the assets checkout's git-ignored
``reference/dune-steam-app/<build-guid>/render/boardspaces/``; tiles go to
``assets/cards/app/<lang>/<manifest path>.webp`` with their sources in
``assets/cards/app/location_sources.json``.

    uv run --offline --with UnityPy python scripts/dwgr/app_board.py inputs
    uv run --offline --with pillow python scripts/dwgr/app_board.py render \\
        --lang en,ko
    uv run --offline --with pillow python scripts/dwgr/app_board.py compare \\
        --out DIR
"""

import argparse
import copy
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

# ---------------------------------------------------------------- the scene
SCENE_BUNDLE = "4b1af6fcaa9780cc69cd8fb2dcc293fd.bundle"
SCENE_CAB = "CAB-c16e07e19e68ccc303e2bfe48535d365"  # the Playmat scene
SPACES_PATH = (
    "Board",
    "Visible Objects Connected to Entities",
    "P_Spaces_Uprising_ChildOrderMattersForGamepad",
)
# The icon mesh library (G_icon_BoardSpaces_1.fbx) the scene's icons come from;
# it also holds icons the scene fills in at run time.
ICON_MESH_CAB = "CAB-046df7124d06112c0fd9107e63b7dcf0"
EXTRA_MESHES = ("G_icon_SwordMaster",)
# Unity's built-in Quad (unity default resources, path id 10210): 1x1, centred.
BUILTIN_QUAD_PID = 10210
STRIP_V_OFFSET = 0.2890625  # 74/256: the frame material's shift to one strip

# Manifest content id -> scene object. The CHOAM variants of Accept Contract and
# Dutiful Service are the ones the printed board shows (a Contract, not
# Solari); the Immortality overlay is the app's Research Station with the
# Research icon.
SPACE_OBJECTS = {
    "accept_contract": "P_Space_AcceptContract_CHOAM",
    "arrakeen": "P_Space_Arrakeen_Uprising",
    "assembly_hall": "P_Space_AssemblyHall",
    "deep_desert": "P_Space_DeepDesert",
    "deliver_supplies": "P_Space_DeliverSupplies",
    "desert_tactics": "P_Space_DesertTactics",
    "dutiful_service": "P_Space_DutifulService_CHOAM",
    "espionage": "P_Space_Espionage",
    "fremkit": "P_Space_Fremkit",
    "gather_support": "P_Space_GatherSupport",
    "hagga_basin": "P_Space_HaggaBasin_Uprising",
    "heighliner": "P_Space_Heighliner_Uprising",
    "high_council": "P_Space_HighCouncil_Uprising",
    "imperial_basin": "P_Space_ImperialBasin_Uprising",
    "imperial_privilege": "P_Space_ImperialPrivilege",
    "research_station": "P_Space_ResearchStation_Uprising",
    "sardaukar": "P_Space_Sardaukar",
    "secrets": "P_Space_Secrets",
    "shipping": "P_Space_Shipping",
    "sietch_tabr": "P_Space_SietchTabr_Uprising",
    "spice_refinery": "P_Space_SpiceRefinery",
    "swordmaster": "P_Space_Swordmaster_Uprising",
    "research_station_overlay": "P_Space_ResearchStation_Immo",
}
# Tile content id -> the engine board space whose rules it shows.
ENGINE_SPACE = {"research_station_overlay": "research_station"}
TUEK_ID = "tuek_sietch"


def build_guid():
    for line in open(STEAM_DATA / "boot.config"):
        if line.startswith("build-guid="):
            return line.strip().split("=", 1)[1]
    raise SystemExit("no build-guid in boot.config")


def render_dir():
    return ASSETS / "reference" / "dune-steam-app" / build_guid() / "render"


def inputs_dir():
    return render_dir() / "boardspaces"


# ---------------------------------------------------------------- inputs
def vec(d, keys="xyz"):
    return [float(d[k]) for k in keys]


class SceneDump:
    """Walks space subtrees with UnityPy and collects meshes, materials,
    textures and fonts by name as it goes."""

    def __init__(self, app, out):
        self.app = app
        self.out = out
        self.meshes = {}
        self.materials = {}
        self.textures = {}  # name -> Texture2D reader
        self.fonts = {}  # name -> TMP font asset reader
        self.shaders = {}

    # -- tree
    def node(self, tr_reader):
        tr = tr_reader.read_typetree()
        go_reader = self.app.deref(tr_reader, tr["m_GameObject"])
        go = go_reader.read_typetree()
        node = {
            "name": go["m_Name"],
            "active": bool(go["m_IsActive"]),
            "pos": vec(tr["m_LocalPosition"]),
            "rot": vec(tr["m_LocalRotation"], "xyzw"),
            "scale": vec(tr["m_LocalScale"]),
        }
        if "m_SizeDelta" in tr:
            # A RectTransform under a plain Transform sits at its anchored
            # position; its serialized local x, y stay 0.
            node["rect"] = {
                "size": vec(tr["m_SizeDelta"], "xy"),
                "pivot": vec(tr["m_Pivot"], "xy"),
                "anchored": vec(tr["m_AnchoredPosition"], "xy"),
            }
        comps = [self.app.deref(go_reader, c["component"]) for c in go["m_Component"]]
        text_material = False
        for c in comps:
            if c is None:
                continue
            kind = c.type.name
            if kind == "MeshFilter":
                node["mesh"] = self.mesh(c, c.read_typetree()["m_Mesh"])
            elif kind == "MeshRenderer":
                tt = c.read_typetree()
                node["renderer"] = bool(tt["m_Enabled"])
                node["materials"] = [self.material(c, p) for p in tt["m_Materials"]]
                text_material = any(
                    (self.materials.get(m) or {})
                    .get("shader", "")
                    .startswith("TextMeshPro")
                    for m in node["materials"]
                )
        if text_material:  # only text objects pay for reading MonoBehaviours
            for c in comps:
                if c is not None and c.type.name == "MonoBehaviour":
                    tt = c.read_typetree()
                    if self.app.script_name(c, tt) == "TextMeshPro":
                        node["text"] = self.text(c, tt)
        node["children"] = [
            self.node(self.app.deref(tr_reader, ch)) for ch in tr["m_Children"]
        ]
        return node

    def text(self, reader, tt):
        font = self.app.deref(reader, tt["m_fontAsset"])
        name = font.peek_name() if font is not None else None
        if font is not None:
            self.fonts.setdefault(name, font)
        return {
            "text": tt["m_text"],
            "font": name,
            "size": float(tt["m_fontSize"]),
            "color": vec(tt["m_fontColor"], "rgba"),
            "style": tt["m_fontStyle"],
            "halign": tt["m_HorizontalAlignment"],
            "valign": tt["m_VerticalAlignment"],
            "spacing": float(tt["m_characterSpacing"]),
        }

    # -- assets
    def mesh(self, owner, pptr):
        if pptr["m_PathID"] == 0:
            return None
        obj = self.app.deref(owner, pptr)
        if obj is None:  # a built-in resource outside every bundle
            return f"builtin:{pptr['m_PathID']}"
        key = f"{obj.peek_name()}#{obj.path_id}"
        if key not in self.meshes:
            self.meshes[key] = mesh_data(obj)
        return key

    def material(self, owner, pptr):
        obj = self.app.deref(owner, pptr)
        if obj is None:
            return None
        tt = obj.read_typetree()
        name = tt["m_Name"]
        if name in self.materials:
            return name
        props = tt.get("m_SavedProperties", {})
        info = {
            "shader": self.shader_name(obj, tt["m_Shader"]),
            "colors": {n: vec(c, "rgba") for n, c in props.get("m_Colors", [])},
            "floats": {n: float(v) for n, v in props.get("m_Floats", [])},
            "textures": {},
        }
        for slot, env in props.get("m_TexEnvs", []):
            if slot not in ("_BaseMap", "_MainTex") or not env["m_Texture"]["m_PathID"]:
                continue
            tex = self.app.deref(obj, env["m_Texture"])
            if tex is None or tex.type.name != "Texture2D":
                continue
            tex_name = tex.peek_name()
            if not info["shader"].startswith("TextMeshPro"):
                self.textures.setdefault(tex_name, tex)
            info["textures"][slot] = {
                "texture": tex_name,
                "scale": vec(env["m_Scale"], "xy"),
                "offset": vec(env["m_Offset"], "xy"),
            }
        self.materials[name] = info
        return name

    def shader_name(self, owner, pptr):
        key = (owner.assets_file.name, pptr["m_FileID"], pptr["m_PathID"])
        if key not in self.shaders:
            obj = self.app.deref(owner, pptr)
            try:
                self.shaders[key] = obj.read().m_ParsedForm.m_Name
            except Exception:  # a stripped shader still has its object name
                self.shaders[key] = obj.peek_name() if obj is not None else "?"
        return self.shaders[key]

    def extra_mesh(self, name):
        sf = self.app.serialized(ICON_MESH_CAB)
        for obj in sf.objects.values():
            if obj.type.name == "Mesh" and obj.peek_name() == name:
                key = f"{name}#{obj.path_id}"
                self.meshes[key] = mesh_data(obj)
                return key
        raise SystemExit(f"mesh {name} not in {ICON_MESH_CAB}")

    # -- writing
    def save_textures(self):
        folder = self.out / "textures"
        folder.mkdir(parents=True, exist_ok=True)
        for name, reader in sorted(self.textures.items()):
            save_texture(self.app, reader, folder / f"{name}.png")

    def save_fonts(self):
        folder = self.out / "fonts"
        folder.mkdir(parents=True, exist_ok=True)
        for name, reader in sorted(self.fonts.items()):
            save_font(self.app, reader, folder, name)


def mesh_data(obj):
    """Vertices (x, y, z), UV0 and one triangle list per submesh, as Unity
    stores them (Mesh.export() would mirror x for OBJ)."""
    from UnityPy.helpers.MeshHelper import MeshHandler

    m = obj.read()
    h = MeshHandler(m)
    h.process()
    return {
        "name": m.m_Name,
        "v": [[round(c, 6) for c in p[:3]] for p in h.m_Vertices],
        "uv": [[round(c, 6) for c in p[:2]] for p in (h.m_UV0 or [])],
        "tris": [[list(t) for t in sub] for sub in h.get_triangles()],
    }


def save_texture(app, reader, path):
    """Texture2D -> PNG, loading the bundle that holds its pixel stream when
    the first try names a missing .resS (as app_assets.save_picture does)."""
    while True:
        try:
            reader.read().image.save(path)
            return
        except FileNotFoundError as e:
            m = re.search(r"(?:Resource )?[Ff]ile (\S+) not found", str(e))
            dep = app.index["cab"].get((m.group(1) if m else "").lower())
            if not dep or dep in app.loaded:
                raise
            app.load(dep)


def save_font(app, reader, folder, name):
    """A TMP font asset in app_assets.cmd_fonts' format (app_render.SDFFont)."""
    tt = reader.read_typetree()
    atlases = []
    for i, p in enumerate(tt["m_AtlasTextures"]):
        tex = app.deref(reader, p)
        fn = f"{name}_{i}.png"
        save_texture(app, tex, folder / fn)
        atlases.append([fn, tex.read().m_Width, tex.read().m_Height])
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
        open(folder / f"{name}.json", "w"),
        default=str,
    )


def scene_root(app, sf, name):
    for obj in sf.objects.values():
        if obj.type.name not in ("Transform", "RectTransform"):
            continue
        t = obj.read()
        if t.m_Father.m_PathID == 0 and t.m_GameObject.read().m_Name == name:
            return obj
    raise SystemExit(f"no scene root {name}")


def child(app, tr_reader, name):
    for ch in tr_reader.read_typetree()["m_Children"]:
        reader = app.deref(tr_reader, ch)
        go = app.deref(reader, reader.read_typetree()["m_GameObject"])
        if go.read_typetree()["m_Name"] == name:
            return reader
    raise SystemExit(f"no child {name}")


def cmd_inputs(_args):
    from app_assets import App  # needs UnityPy; render does not

    out = inputs_dir()
    out.mkdir(parents=True, exist_ok=True)
    app = App()
    app.load(SCENE_BUNDLE)
    sf = app.serialized(SCENE_CAB)
    container = scene_root(app, sf, SPACES_PATH[0])
    for name in SPACES_PATH[1:]:
        container = child(app, container, name)
    dump = SceneDump(app, out)
    spaces = {}
    for obj_name in sorted(set(SPACE_OBJECTS.values())):
        spaces[obj_name] = dump.node(child(app, container, obj_name))
        print("space", obj_name, flush=True)
    extra = {name: dump.extra_mesh(name) for name in EXTRA_MESHES}
    dump.save_textures()
    dump.save_fonts()
    json.dump(dump.meshes, open(out / "meshes.json", "w"))
    json.dump(
        {
            "build_guid": build_guid(),
            "scene": [SCENE_BUNDLE, SCENE_CAB, "/".join(SPACES_PATH)],
            "spaces": spaces,
            "materials": dump.materials,
            "extra_meshes": extra,
        },
        open(out / "scene.json", "w"),
        indent=0,
    )
    print(
        "inputs:",
        len(spaces),
        "spaces,",
        len(dump.meshes),
        "meshes,",
        len(dump.textures),
        "textures,",
        len(dump.fonts),
        "fonts ->",
        out,
    )


# ---------------------------------------------------------------- render
PX_PER_UNIT = 256  # tile pixels per Unity unit (a regular frame: 3.01 x 1.27)
SUPERSAMPLE = 2
OVERHANG_PX = 64  # tile px searched around the frame for icons standing over it
VISIBLE_ALPHA = 0.02  # what counts as drawn (the combat X's quad is clear around it)
# Animator-driven layers: present and active in the scene, drawn only while a
# hint, highlight, tutorial or effect animation runs.
SKIP_NODES = re.compile(
    r"FX|Hint|Outline|TheVoice|Gamepad|Tutorial|Darken|SpaceUnvisited|Glow"
)
TEXT_Z_BIAS = 0.0005  # TMP text (transparent queue) draws over its own icon
TMP_3D_SCALE = 0.1  # TextMeshPro (not UI) world units per point at font size 1
# Korean tiles: the Korean edition's word for the app's 3D "OR".
KOREAN_WORDS = {"OR": "또는"}
KOREAN_FONT_BOLD = Path("~/Library/Fonts/NanumBarunGothicBold.otf").expanduser()
# The Korean word's ink height over the Latin capitals' height. At the same em
# "또는" is half again as wide as "OR" and runs into the icons beside it; at
# exactly the capitals' height it reads smaller than "OR".
HANGUL_TO_CAP = 1.1
QUAD = {  # Unity's built-in Quad: 1x1 in XY, centred
    "name": "Quad",
    "v": [[-0.5, -0.5, 0], [0.5, -0.5, 0], [-0.5, 0.5, 0], [0.5, 0.5, 0]],
    "uv": [[0, 0], [1, 0], [0, 1], [1, 1]],
    "tris": [[[0, 3, 1], [3, 0, 2]]],
}

# Static state shown on the tiles (owner-approved reconcile, 2026-10-08):
# - the combat X shows where the engine says combat (the scene leaves it off
#   on the desert spaces; WormCombatSpaceDataRenderer switches it per game);
# - the worm slash (on while the Conflict is behind the Shield Wall) and the
#   bonus-spice counter (WormBonusSpiceRenderer) are game state, not print;
# - Swordmaster's Reward_Anchor is filled at run time with its icon, a mesh of
#   the icon library cut from the same atlas as the other reward icons.
COMBAT_ICON = "G_icon_Combat"
HIDDEN_NODES = frozenset({"G_icon_Reward_WormSlash", "UI_icon_Bonus_Spice"})
REWARD_ICON_MATERIAL = "M_icon_BoardSpaces_1"  # the reward icons' atlas


class Inputs:
    def __init__(self):
        d = inputs_dir()
        if not (d / "scene.json").exists():
            raise SystemExit("run `app_board.py inputs` first")
        self.dir = d
        self.scene = json.loads((d / "scene.json").read_text())
        self.meshes = json.loads((d / "meshes.json").read_text())
        self.meshes[f"builtin:{BUILTIN_QUAD_PID}"] = QUAD
        self.materials = self.scene["materials"]
        self.textures = {}
        self.fonts = {}
        self.manifest = location_manifest()

    def texture(self, name):
        if name not in self.textures:
            self.textures[name] = load_rgba(self.dir / "textures" / f"{name}.png")
        return self.textures[name]

    def font(self, name):
        import app_render as R

        if name not in self.fonts:
            self.fonts[name] = R.SDFFont(str(self.dir / "fonts" / f"{name}.json"))
        return self.fonts[name]

    def space(self, obj):
        return copy.deepcopy(self.scene["spaces"][obj])


def location_manifest():
    """{content id: manifest entry} for the location tiles of indexed sets."""
    doc = json.loads((CARDS / "manifest.json").read_text())
    return {
        e["content_id"]: e
        for e in doc["entries"]
        if e["kind"] == "location" and e.get("content_id")
    }


def load_rgba(path):
    from PIL import Image

    return np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0


# -- geometry
def local_matrix(node):
    x, y, z = node["pos"]
    if "rect" in node:
        x, y = node["rect"]["anchored"]
    qx, qy, qz, qw = node["rot"]
    rot = np.array(
        [
            [
                1 - 2 * (qy * qy + qz * qz),
                2 * (qx * qy - qz * qw),
                2 * (qx * qz + qy * qw),
            ],
            [
                2 * (qx * qy + qz * qw),
                1 - 2 * (qx * qx + qz * qz),
                2 * (qy * qz - qx * qw),
            ],
            [
                2 * (qx * qz - qy * qw),
                2 * (qy * qz + qx * qw),
                1 - 2 * (qx * qx + qy * qy),
            ],
        ]
    )
    m = np.eye(4)
    m[:3, :3] = rot * np.array(node["scale"])
    m[:3, 3] = (x, y, z)
    return m


def transform(m, pts):
    """Unity-space points (n, 2 or 3) through a 4x4 matrix -> world (n, 3)."""
    pts = np.asarray(pts, np.float64)
    if pts.shape[1] == 2:
        pts = np.c_[pts, np.zeros(len(pts))]
    return (m @ np.c_[pts, np.ones(len(pts))].T).T[:, :3]


def walk(node, fn, path=""):
    path = f"{path}/{node['name']}"
    fn(node, path)
    for ch in node["children"]:
        walk(ch, fn, path)


def find_node(node, name):
    found = []
    walk(node, lambda n, _p: found.append(n) if n["name"] == name else None)
    return found


def collect(node, m, items, top=True):
    """(z, order, kind, node, matrix, submesh) for everything drawn. The
    space's own transform (its place on the board) is left out."""
    if not node["active"] or (not top and SKIP_NODES.search(node["name"])):
        return
    if not top:
        m = m @ local_matrix(node)
    if node.get("mesh") and node.get("renderer"):
        for i, material in enumerate(node.get("materials") or []):
            if material:
                items.append((m[2, 3], len(items), "mesh", node, m, i))
    if node.get("text"):
        items.append((m[2, 3] - TEXT_Z_BIAS, len(items), "text", node, m, 0))
    for ch in node["children"]:
        collect(ch, m, items, False)


# -- rasteriser
def sample(img, u, v):
    """Bilinear, clamped; v runs up the texture as in Unity."""
    h, w = img.shape[:2]
    x = np.clip(u * w - 0.5, 0, w - 1.001)
    y = np.clip((1 - v) * h - 0.5, 0, h - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = x - x0, y - y0
    if img.ndim == 3:
        fx, fy = fx[:, None], fy[:, None]
    top = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    bottom = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return top * (1 - fy) + bottom * fy


def triangle_pixels(p, tri, w, h):
    """Pixel centres inside one triangle: (rows, cols, barycentric (k, 3))."""
    xs, ys = p[list(tri), 0], p[list(tri), 1]
    x0, x1 = max(int(np.floor(xs.min())), 0), min(int(np.ceil(xs.max())), w - 1)
    y0, y1 = max(int(np.floor(ys.min())), 0), min(int(np.ceil(ys.max())), h - 1)
    d = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
    if x1 < x0 or y1 < y0 or abs(d) < 1e-12:
        return None
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    gx, gy = gx.ravel(), gy.ravel()
    w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / d
    w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / d
    w2 = 1 - w0 - w1
    inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    if not inside.any():
        return None
    bary = np.stack([w0[inside], w1[inside], w2[inside]], 1)
    return gy[inside].astype(int), gx[inside].astype(int), bary


def over(canvas, rows, cols, rgba):
    """Straight-alpha source over a premultiplied canvas."""
    a = rgba[:, 3:4]
    canvas[rows, cols] = np.c_[rgba[:, :3] * a, a] + canvas[rows, cols] * (1 - a)


def draw_tris(canvas, p, tris, uv, shade):
    """Rasterise triangles (canvas pixels p, texture coords uv) as one layer,
    so edges shared inside a mesh are not blended twice, and lay it over."""
    h, w = canvas.shape[:2]
    x0, x1 = (
        max(int(np.floor(p[:, 0].min())), 0),
        min(int(np.ceil(p[:, 0].max())), w - 1),
    )
    y0, y1 = (
        max(int(np.floor(p[:, 1].min())), 0),
        min(int(np.ceil(p[:, 1].max())), h - 1),
    )
    if x1 < x0 or y1 < y0:
        return
    layer = np.zeros((y1 - y0 + 1, x1 - x0 + 1, 4), np.float32)
    done = np.zeros(layer.shape[:2], bool)
    for tri in tris:
        tri = list(tri)
        hit = triangle_pixels(p, tri, w, h)
        if hit is None:
            continue
        rows, cols, bary = hit
        r, c = rows - y0, cols - x0
        new = ~done[r, c]
        r, c, bary = r[new], c[new], bary[new]
        if len(r):
            layer[r, c] = shade(bary @ uv[tri, 0], bary @ uv[tri, 1])
            done[r, c] = True
    rr, cc = np.nonzero(done)
    if len(rr):
        over(canvas, rr + y0, cc + x0, layer[rr, cc])


def shader(inp, material):
    """(u, v) -> straight RGBA for a URP Unlit or Core Unlit material."""
    mat = inp.materials[material]
    slot = mat["textures"].get("_BaseMap") or mat["textures"].get("_MainTex")
    img = inp.texture(slot["texture"]) if slot else None
    scale, offset = (slot["scale"], slot["offset"]) if slot else ([1, 1], [0, 0])
    core = mat["shader"].startswith("Core/")  # tinted by _Color, alpha-blended
    color = np.array(
        mat["colors"].get("_Color" if core else "_BaseColor") or [1, 1, 1, 1],
        np.float32,
    )
    opaque = not core and mat["floats"].get("_Surface", 0) == 0

    def shade(u, v):
        if img is None:
            rgba = np.tile(color, (len(u), 1))
        else:
            rgba = sample(img, u * scale[0] + offset[0], v * scale[1] + offset[1])
            rgba = rgba * color
        if opaque:  # URP opaque ignores texture alpha: the mesh is the outline
            rgba[:, 3] = 1.0
        return rgba

    return shade


def draw_mesh(canvas, inp, item, to_px):
    _z, _o, _k, node, m, sub = item
    mesh = inp.meshes[node["mesh"]]
    if sub < len(mesh["tris"]):
        p = to_px(transform(m, mesh["v"]))
        uv = np.asarray(mesh["uv"], np.float64)
        draw_tris(canvas, p, mesh["tris"][sub], uv, shader(inp, node["materials"][sub]))


# -- text
HALIGN = {1: "left", 2: "center", 4: "right", 32: "geometry"}
VALIGN = {256: "top", 512: "middle", 1024: "bottom", 4096: "geometry", 8192: "cap"}


def text_origin(t, rect, width, ink, asc, desc, cap):
    """Pen start and baseline in the RectTransform's local units, by the TMP
    alignment (ink = (left, right, top, bottom) of the glyphs)."""
    (rw, rh), (px, py) = rect["size"], rect["pivot"]
    left, bottom = -rw * px, -rh * py
    halign = HALIGN.get(t["halign"], "left")
    x = {
        "left": left,
        "center": left + (rw - width) / 2,
        "right": left + rw - width,
        "geometry": left + rw / 2 - (ink[0] + ink[1]) / 2,
    }[halign]
    mid = bottom + rh / 2
    base = {
        "top": bottom + rh - asc,
        "middle": mid - (asc + desc) / 2,
        "bottom": bottom - desc,
        "geometry": mid - (ink[2] + ink[3]) / 2,
        "cap": mid - cap / 2,
    }[VALIGN.get(t["valign"], "middle")]
    return x, base


def draw_text(canvas, inp, item, to_px, lang):
    _z, _o, _k, node, m, _s = item
    t = node["text"]
    text = t["text"]
    if not text or text.startswith("_"):  # unlocalised placeholder keys
        return
    font = inp.font(t["font"])
    k = t["size"] / font.point * font.fscale * TMP_3D_SCALE
    if lang == "ko" and text.strip() in KOREAN_WORDS:
        word = KOREAN_WORDS[text.strip()]
        draw_hangul(canvas, node, m, to_px, word, font.cap * k)
        return
    glyphs, pen, prev = [], 0.0, None
    for ch in text:
        gi, g = font.glyph(ch)
        if g is None:
            continue
        pen += font.kern.get((prev, gi), 0) if prev is not None else 0
        glyphs.append((pen, g))
        pen += g["m_Metrics"]["m_HorizontalAdvance"] + t["spacing"]
        prev = gi
    if not glyphs:
        return
    mets = [(x, g["m_Metrics"]) for x, g in glyphs]
    ink = (
        min(x + mt["m_HorizontalBearingX"] for x, mt in mets) * k,
        max(x + mt["m_HorizontalBearingX"] + mt["m_Width"] for x, mt in mets) * k,
        max(mt["m_HorizontalBearingY"] for _x, mt in mets) * k,
        min(mt["m_HorizontalBearingY"] - mt["m_Height"] for _x, mt in mets) * k,
    )
    x0, base = text_origin(
        t, node["rect"], pen * k, ink, font.asc * k, font.desc * k, font.cap * k
    )
    scale = math.sqrt(abs(np.linalg.det(m[:2, :2])))
    pad, aw, ah = font.pad, font.atlas.shape[1], font.atlas.shape[0]
    for gx, g in glyphs:
        mt, r = g["m_Metrics"], g["m_GlyphRect"]
        lx0 = x0 + (gx + mt["m_HorizontalBearingX"] - pad) * k
        ly1 = base + (mt["m_HorizontalBearingY"] + pad) * k
        lx1 = lx0 + (r["m_Width"] + 2 * pad) * k
        ly0 = ly1 - (r["m_Height"] + 2 * pad) * k
        quad = [[lx0, ly0], [lx1, ly0], [lx0, ly1], [lx1, ly1]]
        p = to_px(transform(m, quad))
        u0, u1 = (r["m_X"] - pad) / aw, (r["m_X"] + r["m_Width"] + pad) / aw
        v0, v1 = (r["m_Y"] - pad) / ah, (r["m_Y"] + r["m_Height"] + pad) / ah
        uv = np.array([[u0, v0], [u1, v0], [u0, v1], [u1, v1]])
        # SDF: 0.5 on the outline, 0..1 spanning 2 * padding atlas pixels
        spread = 2 * pad * k * scale * to_px.scale
        draw_tris(canvas, p, QUAD["tris"][0], uv, sdf_shade(font.atlas, spread, t))


def sdf_shade(atlas, spread, t):
    color = np.asarray(t["color"], np.float32)

    def shade(u, v):
        a = np.clip((sample(atlas, u, v) - 0.5) * spread + 0.5, 0, 1) * color[3]
        return np.c_[np.tile(color[:3], (len(a), 1)), a]

    return shade


def draw_hangul(canvas, node, m, to_px, word, cap_height):
    """A Korean word in NanumBarunGothic Bold with the TMP text's alignment
    (Hangul is not in the app's SDF atlases), sized by HANGUL_TO_CAP."""
    from PIL import Image, ImageDraw, ImageFont

    t = node["text"]
    em_px = 256
    font = ImageFont.truetype(str(KOREAN_FONT_BOLD), em_px)
    left, top, right, bottom = font.getbbox(word, anchor="ls")
    asc, desc = font.getmetrics()
    tile = Image.new("L", (right - left + 4, bottom - top + 4), 0)
    ImageDraw.Draw(tile).text(
        (2 - left, 2 - top), word, font=font, fill=255, anchor="ls"
    )
    unit = HANGUL_TO_CAP * cap_height / (bottom - top)  # local units per font px
    ink = (left * unit, right * unit, -top * unit, -bottom * unit)
    x0, base = text_origin(
        t,
        node["rect"],
        font.getlength(word) * unit,
        ink,
        asc * unit,
        -desc * unit,
        -top * unit,
    )
    lx0, lx1 = x0 + (left - 2) * unit, x0 + (right + 2) * unit
    ly1, ly0 = base + (2 - top) * unit, base - (bottom + 2) * unit
    p = to_px(transform(m, [[lx0, ly0], [lx1, ly0], [lx0, ly1], [lx1, ly1]]))
    alpha = np.asarray(tile).astype(np.float32) / 255.0
    color = np.asarray(t["color"], np.float32)

    def shade(u, v):
        a = sample(alpha, u, v) * color[3]
        return np.c_[np.tile(color[:3], (len(a), 1)), a]

    uv = np.array([[0, 0], [1, 0], [0, 1], [1, 1]], np.float64)
    draw_tris(canvas, p, QUAD["tris"][0], uv, shade)


# -- tiles
class PixelMap:
    """World XY -> supersampled canvas pixels (y down), from the frame's box."""

    def __init__(self, box, scale):
        self.x0, self.y1 = box[0], box[3]
        self.scale = scale

    def __call__(self, world):
        return np.c_[
            (world[:, 0] - self.x0) * self.scale, (self.y1 - world[:, 1]) * self.scale
        ]


def frame_item(items):
    for it in items:
        if it[2] == "mesh" and it[3]["name"] == "Frame":
            return it
    raise SystemExit("space without Root/Frame")


def render_tile(inp, tree, lang):
    """One space tree -> RGBA tile at PX_PER_UNIT: the frame's box, grown
    where icons overhang the frame (Imperial Privilege's and Shipping's cost
    stand over its lower edge, as on the app's board); transparent around
    the frame."""
    from PIL import Image

    items = []
    collect(tree, np.eye(4), items)
    frame = frame_item(items)
    fv = transform(frame[4], inp.meshes[frame[3]["mesh"]]["v"])
    fw = round((fv[:, 0].max() - fv[:, 0].min()) * PX_PER_UNIT)
    fh = round((fv[:, 1].max() - fv[:, 1].min()) * PX_PER_UNIT)
    m, ss = OVERHANG_PX, SUPERSAMPLE
    grow = m / PX_PER_UNIT
    box = (
        fv[:, 0].min() - grow,
        fv[:, 1].min() - grow,
        fv[:, 0].max() + grow,
        fv[:, 1].max() + grow,
    )
    to_px = PixelMap(box, PX_PER_UNIT * ss)
    canvas = np.zeros(((fh + 2 * m) * ss, (fw + 2 * m) * ss, 4), np.float32)
    for it in sorted(items, key=lambda it: (-it[0], it[1])):
        if it[2] == "mesh":
            draw_mesh(canvas, inp, it, to_px)
        else:
            draw_text(canvas, inp, it, to_px, lang)
    rows, cols = np.nonzero(canvas[..., 3] > VISIBLE_ALPHA)
    x0, x1 = min(m, cols.min() // ss), max(m + fw, -(-(cols.max() + 1) // ss))
    y0, y1 = min(m, rows.min() // ss), max(m + fh, -(-(rows.max() + 1) // ss))
    canvas = canvas[y0 * ss : y1 * ss, x0 * ss : x1 * ss]
    out_w, out_h = x1 - x0, y1 - y0
    chans = [
        Image.fromarray(canvas[..., i]).resize((out_w, out_h), Image.LANCZOS)
        for i in range(4)
    ]
    prem = np.stack([np.asarray(c) for c in chans], -1)
    a = np.clip(prem[..., 3:4], 0, 1)
    rgb = np.where(a > 1e-4, prem[..., :3] / np.maximum(a, 1e-4), 0)
    out = np.clip(np.c_[rgb.reshape(-1, 3), a.reshape(-1, 1)], 0, 1)
    return Image.fromarray(
        (out.reshape(out_h, out_w, 4) * 255 + 0.5).astype(np.uint8), "RGBA"
    )


def engine_space(content_id):
    from dune_imperium.content.uprising.board import BOARD_SPACES_BY_ID

    return BOARD_SPACES_BY_ID[ENGINE_SPACE.get(content_id, content_id)]


def fix_static_state(inp, tree, content_id):
    """The printed board's state of a live space (see COMBAT_ICON above)."""
    combat = engine_space(content_id).combat

    def fix(node, _path):
        if node["name"] == COMBAT_ICON:
            node["active"] = combat
        if node["name"] in HIDDEN_NODES:
            node["active"] = False

    walk(tree, fix)
    if content_id == "swordmaster":
        for anchor in find_node(tree, "Reward_Anchor"):
            if not anchor["children"]:
                anchor["children"].append(
                    {
                        "name": "G_icon_SwordMaster",
                        "active": True,
                        "pos": [0.0, 0.0, 0.0],
                        "rot": [0.0, 0.0, 0.0, 1.0],
                        "scale": [1.0, 1.0, 1.0],
                        "mesh": inp.scene["extra_meshes"]["G_icon_SwordMaster"],
                        "renderer": True,
                        "materials": [REWARD_ICON_MATERIAL],
                        "children": [],
                    }
                )
    return tree


def frame_source(inp, tree):
    """(frame texture, strip) of a space: the frame material's v offset picks
    the texture's top or bottom strip; 0 is a frame that uses the whole."""
    frame = next(n for n in find_node(tree, "Frame") if n.get("mesh"))
    slot = inp.materials[frame["materials"][0]]["textures"]
    slot = slot.get("_BaseMap") or slot.get("_MainTex")
    halves = {STRIP_V_OFFSET: "top", -STRIP_V_OFFSET: "bottom", 0.0: "whole"}
    off = slot["offset"][1]
    half = next((h for o, h in halves.items() if abs(off - o) < 1e-4), str(off))
    return slot["texture"], half


# ---------------------------------------------------------------- Tuek's Sietch
# Esmar Tuek (Bloodlines) brings his own Spice Trade space: Maker, combat,
# "1 spice OR draw 1 card", no cost (engine content tuek_sietch). The app has
# no Bloodlines content, so the tile is composed from app parts (owner's
# choice, 2026-10-08):
# - frame: the regular frame mesh with the Spice Trade strip of
#   T_frm_BoardSpace_HaggaBasin. The printed tile's brown ground is the board's
#   Spice Trade colour (as on the printed Accept Contract and Shipping), which
#   the app draws on every Spice Trade space as this yellow frame with a brown
#   left band; no app strip has the printed tile's white art border, the app
#   dropped it on all spaces;
# - art: the printed tile's art, cropped below the printed Spice Trade icon to
#   the strip's window shape, with the printed combat X painted out (the app's
#   X is drawn at that spot), under the brown band as on the app's strips;
# - icons: the app's Hagga Basin, the app space of the same structure (Spice
#   Trade, Maker socket, combat, an "x OR y" reward row), without its water
#   cost and with the row "1 spice OR draw a card".
TUEK_LAYOUT = "P_Space_HaggaBasin_Uprising"
TUEK_FRAME = ("T_frm_BoardSpace_HaggaBasin", "top")
TUEK_TEXTURE = "T_frm_TuekSietch_composed"
TUEK_MATERIAL = "M_frm_TuekSietch_composed"
TUEK_ART_BOX = (46, 118, 289, 218)  # printed tile px: art below the icon's shadow
TUEK_X_BOX = (244, 196, 289, 218)  # printed tile px: the combat X in that crop
STRIP_ROWS = 108  # texture rows of one space's strip
STRIP_BORDER = 2  # texture px of frame colour around the art window
BAND_COLUMNS = 58  # texture px from the left edge under the brown band
# The band is art * (1 - a) + colour * a; a and the colour are a least-squares
# fit across the band edge of the app's six Spice Trade strips.
BAND_ALPHA = 0.61
BAND_COLOR = (114 / 255, 54 / 255, 15 / 255)
TEXTURE_UPSCALE = 4  # the composed strip has 4x the app's texel density
# Hagga Basin's other reward row puts a 0.9 card beside a 0.8 spice hex.
CARD_TO_SPICE_SCALE = 0.9 / 0.8


def resize(arr, size):
    from PIL import Image

    img = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8))
    return np.asarray(img.resize(size, Image.LANCZOS)).astype(np.float32) / 255.0


def paint_out(img, mask, iterations=400):
    """Fill the masked pixels from their surroundings (heat diffusion)."""
    out = img.copy()
    out[mask] = img[~mask].mean(0)
    for _ in range(iterations):
        p = np.pad(out, ((1, 1), (1, 1), (0, 0)), mode="edge")
        avg = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 4
        out[mask] = avg[mask]
    return out


def tuek_art(inp, size):
    """The printed tile's art for the composed strip's window."""
    path = CARDS / "en" / inp.manifest[TUEK_ID]["path"]
    x0, y0, x1, y1 = TUEK_ART_BOX
    crop = load_rgba(path)[y0:y1, x0:x1, :3]
    # the printed X: pale, unsaturated strokes on the sand, grown by 2 px to
    # take their soft edges
    rgb = crop[TUEK_X_BOX[1] - y0 :, TUEK_X_BOX[0] - x0 :]
    stroke = (rgb.max(-1) - rgb.min(-1) < 40 / 255) & (rgb.min(-1) > 120 / 255)
    mask = np.zeros(crop.shape[:2], bool)
    mask[TUEK_X_BOX[1] - y0 :, TUEK_X_BOX[0] - x0 :] = stroke
    for _ in range(2):
        p = np.pad(mask, 1)
        mask = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return resize(paint_out(crop, mask), size)


def tuek_texture(inp):
    """The Hagga Basin frame texture with the printed art in its top strip."""
    name, half = TUEK_FRAME
    base = inp.texture(name)
    k = TEXTURE_UPSCALE
    full = resize(base, (base.shape[1] * k, base.shape[0] * k))
    top = 0 if half == "top" else base.shape[0] - STRIP_ROWS
    rows = slice(top * k, (top + STRIP_ROWS) * k)
    strip = full[rows]
    border_rgb = base[top, base.shape[1] // 2, :3]
    # 1 on the frame's border colour, 0 in the art window
    frame = np.clip(1 - np.abs(strip[..., :3] - border_rgb).max(-1) / 0.3, 0, 1)
    b = STRIP_BORDER * k
    layer = strip[..., :3].copy()
    layer[b:-b, b:-b] = tuek_art(inp, (strip.shape[1] - 2 * b, strip.shape[0] - 2 * b))
    band = BAND_COLUMNS * k
    layer[:, :band] = (
        layer[:, :band] * (1 - BAND_ALPHA) + np.array(BAND_COLOR) * BAND_ALPHA
    )
    strip[..., :3] = strip[..., :3] * frame[..., None] + layer * (1 - frame[..., None])
    full[rows] = strip
    return full


def mesh_key(inp, name):
    return next(k for k in inp.meshes if k.split("#")[0] == name)


def mesh_box(inp, node):
    """(x0, y0, x1, y1) of a node's mesh in its parent's coordinates."""
    v = transform(local_matrix(node), inp.meshes[node["mesh"]]["v"])
    return v[:, 0].min(), v[:, 1].min(), v[:, 0].max(), v[:, 1].max()


def text_width(inp, node):
    t = node["text"]
    font = inp.font(t["font"])
    k = t["size"] / font.point * font.fscale * TMP_3D_SCALE
    return (
        sum(font.glyph(c)[1]["m_Metrics"]["m_HorizontalAdvance"] for c in t["text"]) * k
    )


def tueks_sietch_tree(inp):
    tree = inp.space(TUEK_LAYOUT)
    frame = next(n for n in find_node(tree, "Frame") if n.get("mesh"))
    material = copy.deepcopy(inp.materials[frame["materials"][0]])
    for slot in material["textures"].values():
        slot["texture"] = TUEK_TEXTURE
    inp.materials[TUEK_MATERIAL] = material
    inp.textures[TUEK_TEXTURE] = tuek_texture(inp)
    frame["materials"] = [TUEK_MATERIAL]
    for node in find_node(tree, "UI_icon_Cost_Water_Bottom"):
        node["active"] = False  # no cost
    row = next(n for n in find_node(tree, "Default"))
    kids = {n["name"]: n for n in row["children"]}
    spice, word = kids["UI_icon_Cost_Spice"], kids["OR"]
    find_node(spice, "SpiceText_3D")[0]["text"]["text"] = "1"
    card_scale = spice["scale"][0] * CARD_TO_SPICE_SCALE
    card = {
        "name": "UI_icon_Reward_DrawCard",
        "active": True,
        "pos": [0.0, 0.0, spice["pos"][2]],
        "rot": [0.0, 0.0, 0.0, 1.0],
        "scale": [card_scale] * 3,
        "mesh": mesh_key(inp, "G_icon_DrawCard"),
        "renderer": True,
        "materials": [REWARD_ICON_MATERIAL],
        "children": [],
    }
    # spice, OR, card with Hagga Basin's gap between the hex and the word,
    # centred over the Maker socket (x 0 in the row)
    sx0, sy0, sx1, sy1 = mesh_box(inp, spice)
    cx0, cy0, cx1, cy1 = mesh_box(inp, card)
    w_or = text_width(inp, word)
    gap = (word["rect"]["anchored"][0] - w_or / 2) - sx1
    total = (sx1 - sx0) + gap + w_or + gap + (cx1 - cx0)
    left = -total / 2
    spice["pos"][0] += left - sx0
    word["rect"]["anchored"][0] = left + (sx1 - sx0) + gap + w_or / 2
    card["pos"][0] = left + (sx1 - sx0) + gap + w_or + gap - cx0
    card["pos"][1] = (sy0 + sy1) / 2 - (cy0 + cy1) / 2
    row["children"] = [spice, word, card, kids["UI_icon_Reward_SpiceSocket"]]
    return fix_static_state(inp, tree, TUEK_ID)


# ---------------------------------------------------------------- commands
def tile_ids(args):
    ids = [*SPACE_OBJECTS, TUEK_ID]
    return [i for i in args.ids.split(",") if i] if args.ids else ids


def tile_tree(inp, content_id):
    """(tree, source record) of one tile."""
    if content_id == TUEK_ID:
        tree = tueks_sietch_tree(inp)
        art = inp.manifest[TUEK_ID]["path"]
        return tree, {
            "object": f"project composition from cards/en/{art} art",
            "layout": TUEK_LAYOUT,
            "frame_texture": TUEK_FRAME[0],
            "half": TUEK_FRAME[1],
        }
    obj = SPACE_OBJECTS[content_id]
    tree = fix_static_state(inp, inp.space(obj), content_id)
    texture, half = frame_source(inp, tree)
    return tree, {"object": obj, "frame_texture": texture, "half": half}


def tile_path(inp, content_id, lang, root=None):
    rel = Path(inp.manifest[content_id]["path"]).with_suffix(".webp")
    return (Path(root) if root else CARDS / "app") / lang / rel


def cmd_render(args):
    import hashlib

    inp = Inputs()
    sources_path = CARDS / "app" / "location_sources.json"
    doc = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    tiles = doc.get("tiles", {})
    for cid in tile_ids(args):
        tree, source = tile_tree(inp, cid)
        # the tile's own path under app/<lang>/ (the manifest names the scan)
        source["path"] = tile_path(inp, cid, "").relative_to(CARDS / "app").as_posix()
        source["sha256"] = {}
        for lang in args.lang.split(","):
            img = render_tile(inp, tree, lang)
            dest = tile_path(inp, cid, lang, args.out)
            dest.parent.mkdir(parents=True, exist_ok=True)
            img.save(dest, "WEBP", quality=92, method=6)
            source["sha256"][lang] = hashlib.sha256(dest.read_bytes()).hexdigest()
            print(cid, lang, img.size, "->", dest, flush=True)
        tiles[cid] = source
    if not args.out:
        sources_path.write_text(
            json.dumps(
                {"build_guid": build_guid(), "tiles": dict(sorted(tiles.items()))},
                indent=1,
                ensure_ascii=False,
            )
            + "\n"
        )


# Compare sheets: one per Agent icon group, in the board's order.
GROUP_ORDER = (
    "emperor",
    "spacing_guild",
    "bene_gesserit",
    "fremen",
    "landsraad",
    "city",
    "spice_trade",
)


def cmd_compare(args):
    """Scan | app tile (en, ko) | approved prototype render, per group."""
    from PIL import Image, ImageDraw

    inp = Inputs()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    groups = {}
    for cid in tile_ids(args):
        icon = str(engine_space(cid).agent_icon.value)
        group = "overlays" if cid in ENGINE_SPACE or cid == TUEK_ID else icon
        groups.setdefault(group, []).append(cid)
    h, pad, label = 230, 12, 22
    for group, ids in sorted(
        groups.items(), key=lambda g: (GROUP_ORDER + ("overlays",)).index(g[0])
    ):
        rows = []
        for cid in ids:
            cells = []
            scan = CARDS / "en" / inp.manifest[cid]["path"]
            if scan.exists():
                cells.append(("scan", Image.open(scan).convert("RGBA")))
            for lang in ("en", "ko"):
                path = tile_path(inp, cid, lang)
                if path.exists():
                    cells.append((f"app {lang}", Image.open(path).convert("RGBA")))
            proto = Path(args.prototype or "") / f"{SPACE_OBJECTS.get(cid, '')}.png"
            if args.prototype and proto.exists():
                cells.append(("prototype", Image.open(proto).convert("RGBA")))
            cells = [
                (n, im.resize((round(im.width * h / im.height), h), Image.LANCZOS))
                for n, im in cells
            ]
            rows.append((cid, cells))
        width = max(sum(im.width + pad for _n, im in cells) for _c, cells in rows)
        sheet = Image.new("RGBA", (width + pad, len(rows) * (h + label + pad) + pad))
        sheet.paste((44, 44, 52, 255), (0, 0, *sheet.size))
        draw = ImageDraw.Draw(sheet)
        y = pad
        for cid, cells in rows:
            x = pad
            for name, im in cells:
                draw.text((x, y), f"{cid}: {name}", fill=(255, 230, 120, 255))
                sheet.alpha_composite(im, (x, y + label))
                x += im.width + pad
            y += h + label + pad
        sheet.convert("RGB").save(out / f"{group}.jpg", quality=90)
        print("sheet", out / f"{group}.jpg")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inputs").set_defaults(fn=cmd_inputs)
    p = sub.add_parser("render")
    p.add_argument("--lang", default="en,ko")
    p.add_argument("--ids", default="", help="content ids (default: every tile)")
    p.add_argument("--out", help="write here instead of assets/cards/app")
    p.set_defaults(fn=cmd_render)
    p = sub.add_parser("compare")
    p.add_argument("--ids", default="")
    p.add_argument("--out", required=True)
    p.add_argument("--prototype", help="folder of earlier renders named by object")
    p.set_defaults(fn=cmd_compare)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
