"""Extract the Dune: Imperium companion ("spice") data from Dire Wolf Game Room.

usage: extract.py <out_dir>       (game location: $DWGR_APP or the default Steam path)

Writes into <out_dir>:
  manifest.json          build-guid, Unity version, sha256 of the source files
  spice_mb/<Class>.json  every grm.companions.spice MonoBehaviour / ScriptableObject
  schedules.json         the 8 Arrakeen Scouts ScheduleControllers, keyed by the
                         SpiceDataController field that holds each
  loc/<lang>.json        localisation: every "spice.*" key plus the keys the spice
                         prefabs use
  text_sprites.json      index -> sprite name of the TMP sprite asset behind
                         <sprite index=N>
  beat_prefabs.json      UI prefab tree of every ScheduledBeatBehavior and
                         SubcommitteeBehavior
  beats_bundle.txt       per definition: fields, schedules, EN/KO strings, prefab trees
"""

import collections
import hashlib
import json
import os
import re
import sys

import UnityPy
from il2meta import DATA_DIR, MD, RAW, C, build_guid
from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator
from UnityPy.helpers.TypeTreeNode import TypeTreeNode

LOC_BUNDLE = os.path.join(
    DATA_DIR, "StreamingAssets", "Localization", "osx", "localization"
)
DEF_CLASSES = [
    "SubcommitteeDefinition",
    "MissionDefinition",
    "EventDefinition",
    "AuctionDefinition",
    "SaleDefinition",
]
SCHEDULE_FIELDS = {  # SpiceDataController field -> schedule name
    "baseSchedule": "base",
    "basePlusIxSchedule": "base+Ix",
    "basePlusImmortalitySchedule": "base+Immortality",
    "basePlusIxPlusImmortalitySchedule": "base+Ix+Immortality",
    "uprisingSchedule": "Uprising",
    "uprisingPlusIxSchedule": "Uprising+Ix",
    "uprisingPlusImmortalitySchedule": "Uprising+Immortality",
    "uprisingPlusIxPlusImmortalitySchedule": "Uprising+Ix+Immortality",
}
SCHEDULE_LISTS = [
    "availableSubcommittees",
    "availableMissions",
    "availableEvents",
    "availableAuctions",
    "availableSales",
]
UI_NOISE = {
    "Button",
    "LayoutElement",
    "ContentSizeFitter",
    "HorizontalLayoutGroup",
    "VerticalLayoutGroup",
    "CanvasScaler",
    "GraphicRaycaster",
    "Mask",
    "RectMask2D",
    "Shadow",
    "Outline",
    "GridLayoutGroup",
    "AspectRatioFitter",
    "Toggle",
    "ScrollRect",
    "Scrollbar",
}


class Gen(TypeTreeGenerator):
    """UnityPy appends '.dll' to the assembly name; the generator wants it without."""

    def get_nodes_up(self, assembly, fullname):
        key = (assembly, fullname)
        if key not in self.cache:
            base = self.get_nodes(
                assembly[:-4] if assembly.endswith(".dll") else assembly, fullname
            )
            self.cache[key] = TypeTreeNode.from_list(
                [
                    TypeTreeNode(
                        b.m_Level, b.m_Type, b.m_Name, 0, 0, m_MetaFlag=b.m_MetaFlag
                    )
                    for b in base
                ]
            )
        return self.cache[key]


def jsonable(x):
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, bytes):
        return x.hex()
    return x


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Extractor:
    def __init__(self):
        files = [
            os.path.join(DATA_DIR, f)
            for f in sorted(os.listdir(DATA_DIR))
            if (
                f.endswith(".assets")
                or f.startswith("level")
                or f == "globalgamemanagers"
            )
            and not f.endswith(".resS")
        ]
        self.env = UnityPy.load(*files)
        self.unity_version = next(iter(self.env.files.values())).unity_version
        gen = Gen(self.unity_version)
        gen.load_il2cpp(RAW, MD)
        self.env.typetree_generator = gen
        self.files = {os.path.basename(k): v for k, v in self.env.files.items()}
        self.scripts = {}

    def script_of(self, obj):
        key = (obj.assets_file.name, obj.path_id)
        if key not in self.scripts:
            try:
                s = obj.parse_monobehaviour_head().m_Script.deref_parse_as_object()
                self.scripts[key] = (s.m_Namespace, s.m_ClassName)
            except Exception:
                self.scripts[key] = (None, None)
        return self.scripts[key]

    def deref(self, obj, pptr):
        af = obj.assets_file
        if pptr["m_FileID"] == 0:
            return af.objects[pptr["m_PathID"]]
        return self.files[
            os.path.basename(af.externals[pptr["m_FileID"] - 1].path)
        ].objects[pptr["m_PathID"]]

    # ---- MonoBehaviours
    def spice_monobehaviours(self):
        out, errors = collections.defaultdict(list), collections.Counter()
        for obj in self.env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            ns, cls = self.script_of(obj)
            if not ns or "spice" not in ns.lower():
                continue
            try:
                d = obj.parse_as_dict()
            except Exception:
                errors[cls] += 1
                continue
            d["_file"], d["_path_id"] = (
                os.path.basename(obj.assets_file.name),
                obj.path_id,
            )
            out[cls].append(jsonable(d))
        return out, errors

    # ---- prefab trees
    def summarize_mb(self, o):
        _, cls = self.script_of(o)
        try:
            d = o.parse_as_dict()
        except Exception as e:
            return {"script": cls, "err": str(e)[:80]}
        s = {"script": cls}
        if cls in ("TextMeshProUGUI", "TextMeshPro"):
            s["text"] = d.get("m_text")
            return s
        if cls == "Image":
            sp = d.get("m_Sprite")
            if sp and sp["m_PathID"]:
                try:
                    s["sprite"] = self.deref(o, sp).read().m_Name
                except Exception:
                    s["sprite"] = str(sp)
            s["enabled"] = d.get("m_Enabled")
            return s
        for k, v in d.items():
            if k.startswith("m_"):
                continue
            if isinstance(v, str) and v:
                s[k] = v
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                s[k] = v
            elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
                s[k] = v
        return s

    def go_node(self, go_obj):
        go = go_obj.read()
        node = {"name": go.m_Name, "active": go.m_IsActive, "comps": [], "children": []}
        tr = None
        for c in go.m_Component:
            p = c.component if hasattr(c, "component") else c
            try:
                co = p.deref()
            except Exception:
                continue
            tn = co.type.name
            if tn in ("RectTransform", "Transform"):
                tr = co
            elif tn == "CanvasRenderer":
                continue
            elif tn == "MonoBehaviour":
                s = self.summarize_mb(co)
                if s.get("script") not in UI_NOISE:
                    node["comps"].append(s)
            elif tn == "MeshFilter":
                try:
                    node["comps"].append(
                        {"type": tn, "mesh": co.read().m_Mesh.deref().read().m_Name}
                    )
                except Exception:
                    node["comps"].append({"type": tn})
            elif tn == "MeshRenderer":
                try:
                    node["comps"].append(
                        {
                            "type": tn,
                            "mats": [
                                m.deref().read().m_Name
                                for m in co.read().m_Materials
                                if m.m_PathID
                            ],
                        }
                    )
                except Exception:
                    node["comps"].append({"type": tn})
            else:
                node["comps"].append({"type": tn})
        if tr is not None:
            t = tr.read()
            pos = getattr(t, "m_AnchoredPosition", None) or getattr(
                t, "m_LocalPosition", None
            )
            if pos is not None:
                node["pos"] = [round(pos.x), round(pos.y)]
            for ch in t.m_Children:
                node["children"].append(
                    self.go_node(ch.deref().read().m_GameObject.deref())
                )
        return node

    def root_of(self, go_obj):
        for c in go_obj.read().m_Component:
            co = (c.component if hasattr(c, "component") else c).deref()
            if co.type.name in ("RectTransform", "Transform"):
                t = co.read()
                if t.m_Father.m_PathID:
                    return self.root_of(t.m_Father.deref().read().m_GameObject.deref())
                return go_obj
        return go_obj

    def prefabs(self, mb_by_class):
        ra = self.files["resources.assets"].objects
        res = []
        for cls, key in (
            ("ScheduledBeatBehavior", "BeatDefinition"),
            ("SubcommitteeBehavior", "definition"),
        ):
            for it in mb_by_class.get(cls, []):
                if it["_file"] != "resources.assets":
                    continue
                go_obj = ra[it["m_GameObject"]["m_PathID"]]
                root = self.root_of(go_obj)
                res.append(
                    {
                        "behaviour": cls,
                        "definition_path_id": it[key]["m_PathID"],
                        "behaviour_path_id": it["_path_id"],
                        "root_prompt": root.read().m_Name,
                        "tree": self.go_node(go_obj),
                    }
                )
        return res

    def text_sprites(self):
        for obj in self.env.objects:
            if (
                obj.type.name == "MonoBehaviour"
                and self.script_of(obj)[1] == "TMP_SpriteAsset"
            ):
                d = obj.parse_as_dict()
                if d.get("m_Name") == "SPICE_icon_TextEmoticons":
                    return [
                        c.get("m_Name") for c in d.get("m_SpriteCharacterTable", [])
                    ]
        return []


def localisation():
    env = UnityPy.load(LOC_BUNDLE)
    out = {}
    for obj in env.objects:
        if obj.type.name == "TextAsset":
            d = obj.read()
            s = d.m_Script
            if isinstance(s, bytes):
                s = s.decode("utf-8", "surrogateescape")
            table = {}
            for line in s.split("\n"):
                if "=" in line:
                    k, v = line.split("=", 1)
                    table[k] = v
            out[d.m_Name] = table
    return out


def loc_keys_in(node, acc):
    for c in node["comps"]:
        if c.get("locKey"):
            acc.add(c["locKey"])
    for ch in node["children"]:
        loc_keys_in(ch, acc)


def schedules(mb):
    by_pid = {it["_path_id"]: it for it in mb["ScheduleController"]}
    defs = {it["_path_id"]: (cls, it) for cls in DEF_CLASSES for it in mb.get(cls, [])}
    dc = mb["SpiceDataController"][0]
    out = {}
    for field, name in SCHEDULE_FIELDS.items():
        sc = by_pid[dc[field]["m_PathID"]]
        out[name] = {
            "schedule_path_id": sc["_path_id"],
            **{lst: [p["m_PathID"] for p in sc[lst]] for lst in SCHEDULE_LISTS},
        }
        for lst in SCHEDULE_LISTS:
            for pid in out[name][lst]:
                if pid not in defs:
                    raise SystemExit(
                        f"{name}.{lst}: path_id {pid} is not a known definition"
                    )
    return out


def render_tree(n, ind, out):
    comps = []
    for c in n["comps"]:
        if "text" in c:
            comps.append("TEXT:" + repr(c["text"]))
        elif "sprite" in c:
            comps.append(
                "IMG:"
                + str(c["sprite"])
                + ("" if c.get("enabled", 1) else " (image disabled)")
            )
        elif "mesh" in c:
            comps.append("MESH:" + str(c["mesh"]))
        elif "mats" in c:
            comps.append("MAT:" + ",".join(c["mats"]))
        elif "script" in c:
            extra = {k: v for k, v in c.items() if k != "script"}
            comps.append(
                c["script"] + (json.dumps(extra, ensure_ascii=False) if extra else "")
            )
        else:
            comps.append(c.get("type", "?"))
    out.append(
        "  " * ind
        + ("(inactive) " if not n["active"] else "")
        + n["name"]
        + (" @" + str(n["pos"]) if "pos" in n else "")
        + "  "
        + " | ".join(comps)
    )
    for ch in n["children"]:
        render_tree(ch, ind + 1, out)


def bundle(mb, sched, prefabs, loc, sprites):
    en, ko = loc["en_US"], loc["ko_KR"]
    member = collections.defaultdict(list)
    for name, s in sched.items():
        for lst in SCHEDULE_LISTS:
            for pid in s[lst]:
                member[pid].append(name)
    trees = collections.defaultdict(list)
    for p in prefabs:
        trees[p["definition_path_id"]].append(p)

    def spr(s):
        return re.sub(
            r"<sprite index=(\d+)>",
            lambda m: f"<sprite index={m.group(1)} ={sprites[int(m.group(1))]}>",
            s,
        )

    out = []
    for cls in DEF_CLASSES:
        out.append(f"\n\n################ {cls}")
        items = sorted(
            mb.get(cls, []),
            key=lambda d: (
                d.get("beatId", d.get("subcommitteeId", 0)),
                d.get("beatSubId", 0),
            ),
        )
        for d in items:
            pid = d["_path_id"]
            out.append(
                f"\n=== {cls} path_id={pid}  in schedules: "
                f"{member.get(pid) or '(none: only reachable as returnReplacement)'}"
            )
            out.append(
                "definition: "
                + json.dumps(
                    {
                        k: v
                        for k, v in d.items()
                        if not k.startswith("m_") and k not in ("_file", "_path_id")
                    },
                    ensure_ascii=False,
                )
            )
            keys = [
                d[k]
                for k in ("name", "instructions", "subtitle", "reminder")
                if d.get(k)
            ]
            if d.get("instructions"):
                keys.append(d["instructions"] + ".uprising")
            if d.get("name", "").startswith("spice.subcommitte."):
                keys.append(
                    d["name"].replace("spice.subcommitte.", "spice.subcommittees.")
                )
            for ch in d.get("secretChoices", []):
                keys += [
                    ch[k]
                    for k in ("description", "completionTitle", "completionDescription")
                    if ch.get(k)
                ]
                for sc in ch.get("subChoices", []):
                    keys += [
                        sc[k]
                        for k in (
                            "description",
                            "completionTitle",
                            "completionDescription",
                        )
                        if sc.get(k)
                    ]
            tree_keys = set()
            for t in trees.get(pid, []):
                loc_keys_in(t["tree"], tree_keys)
            seen = set()
            for k in keys + sorted(tree_keys):
                if k in seen:
                    continue
                seen.add(k)
                out.append(
                    f"  loc {k}:\n"
                    f"     EN: {spr(en[k]) if k in en else '<MISSING KEY>'}\n"
                    f"     KO: {spr(ko[k]) if k in ko else '<MISSING KEY>'}"
                )
            for i, t in enumerate(trees.get(pid, [])):
                ui = "UPRISING UI" if "Uprising" in t["root_prompt"] else "BASE-GAME UI"
                out.append(
                    f"  prefab variant {i + 1} under prompt prefab "
                    f"{t['root_prompt']} ({ui})"
                )
                render_tree(t["tree"], 2, out)
    return "\n".join(out) + "\n"


def main(out_dir):
    os.makedirs(os.path.join(out_dir, "spice_mb"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "loc"), exist_ok=True)
    ex = Extractor()
    mb, errors = ex.spice_monobehaviours()
    for cls, items in mb.items():
        with open(os.path.join(out_dir, "spice_mb", f"{cls}.json"), "w") as f:
            json.dump(items, f, indent=1, ensure_ascii=False)
    sched = schedules(mb)
    prefabs = ex.prefabs(mb)
    sprites = ex.text_sprites()
    loc_all = localisation()
    wanted = set()
    for p in prefabs:
        loc_keys_in(p["tree"], wanted)
    loc = {}
    for lang, table in loc_all.items():
        loc[lang] = {
            k: v for k, v in table.items() if k.startswith("spice.") or k in wanted
        }
        with open(os.path.join(out_dir, "loc", f"{lang}.json"), "w") as f:
            json.dump(loc[lang], f, indent=0, ensure_ascii=False, sort_keys=True)
    for name, data in (
        ("schedules.json", sched),
        ("text_sprites.json", sprites),
        ("beat_prefabs.json", prefabs),
    ):
        with open(os.path.join(out_dir, name), "w") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
    with open(os.path.join(out_dir, "beats_bundle.txt"), "w") as f:
        f.write(bundle(mb, sched, prefabs, loc, sprites))
    sources = {
        rel: sha256(os.path.join(C, rel))
        for rel in (
            "Frameworks/GameAssembly.dylib",
            "Resources/Data/il2cpp_data/Metadata/global-metadata.dat",
            "Resources/Data/resources.assets",
            "Resources/Data/level9",
            "Resources/Data/StreamingAssets/Localization/osx/localization",
        )
    }
    manifest = {
        "build_guid": build_guid(),
        "unity_version": ex.unity_version,
        "source_sha256": sources,
        "counts": {cls: len(v) for cls, v in sorted(mb.items())},
        "parse_errors": dict(errors),
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(
        json.dumps(
            {k: manifest[k] for k in ("build_guid", "unity_version", "parse_errors")}
        )
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
