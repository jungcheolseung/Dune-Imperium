"""Name-level dump of an IL2CPP app: every type, field and method, per assembly.

usage: il2dump.py <out_dir> [assembly ...]     (app: $IL2CPP_APP, see il2meta.py)

Writes into <out_dir>:
  manifest.json      app path, build-guid, app and Unity versions, metadata
                     version, sha256 of global-metadata.dat and GameAssembly.dylib
  <assembly>.cs      C#-like listing: type headers with parent and flags, fields
                     with offsets and literal/enum defaults, methods with
                     signatures and code addresses (pass il2dis.py an address)
  methods.tsv        address, full method name, signature (all assemblies)
  strings.tsv        string literal index and text, as the code loads them

With assembly names (e.g. worm-canis.dll) only those get a .cs listing.
"""

import hashlib
import json
import os
import plistlib
import sys

from il2meta import (
    APP,
    BIN,
    DATA_DIR,
    IM,
    MD,
    METADATA_VERSION,
    MT,
    MT_FLAGS,
    SL,
    TD,
    TD_FIELD_START,
    TD_METHOD_COUNT,
    TD_METHOD_START,
    C,
    build_guid,
    field_default,
    fqn,
    method_addr,
    method_signature,
    mstr,
    strlit,
    type_fields,
    type_name,
)

TYPE_FLAGS = [(0x20, "interface"), (0x80, "abstract"), (0x100, "sealed")]
METHOD_FLAGS = [(0x10, "static"), (0x40, "virtual"), (0x400, "abstract")]


def flag_words(value, table):
    return [w for bit, w in table if value & bit]


def app_versions():
    info = {}
    try:
        with open(os.path.join(C, "Info.plist"), "rb") as f:
            plist = plistlib.load(f)
        info["app_version"] = plist.get("CFBundleShortVersionString")
        info["unity_player"] = plist.get("CFBundleGetInfoString")
    except OSError:
        pass
    return info


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def type_listing(ti):
    t = TD[ti]
    parent = type_name(t[4]) if t[4] >= 0 else None
    head = " ".join(flag_words(t[7], TYPE_FLAGS) + ["type", fqn(ti)])
    lines = [f"// typeIndex {ti}", head + (f" : {parent}" if parent else "") + " {"]
    for j, (off, fname, ftype) in enumerate(type_fields(ti)):
        dv = field_default(t[TD_FIELD_START] + j)
        lines.append(
            f"    field +{off if off is not None else '?'} {ftype} {fname}"
            + (f" = {dv!r}" if dv is not None else "")
        )
    for j in range(t[TD_METHOD_COUNT]):
        mi = t[TD_METHOD_START] + j
        words = flag_words(MT[mi][MT_FLAGS], METHOD_FLAGS)
        lines.append(
            f"    method {method_addr.get(mi, 0):#x} "
            + " ".join(words + [method_signature(mi)])
        )
    lines.append("}")
    return lines


def main(out_dir, only):
    os.makedirs(out_dir, exist_ok=True)
    metadata_path = os.path.join(
        DATA_DIR, "il2cpp_data", "Metadata", "global-metadata.dat"
    )
    manifest = {
        "app": APP,
        "contents": C,
        "build_guid": build_guid(),
        "metadata_version": METADATA_VERSION,
        "sha256": {
            "global-metadata.dat": sha256(metadata_path),
            "GameAssembly.dylib": sha256(
                os.path.join(C, "Frameworks", "GameAssembly.dylib")
            ),
        },
        "sizes": {"metadata": len(MD), "x86_64_vm_image": len(BIN)},
        **app_versions(),
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    with open(os.path.join(out_dir, "methods.tsv"), "w") as tsv:
        tsv.write("address\tmethod\tsignature\n")
        for im in IM:
            image = mstr(im[0])
            listing = []
            for ti in range(im[2], im[2] + im[3]):
                t = TD[ti]
                for j in range(t[TD_METHOD_COUNT]):
                    mi = t[TD_METHOD_START] + j
                    tsv.write(
                        f"{method_addr.get(mi, 0):#x}\t{fqn(ti)}::{mstr(MT[mi][0])}"
                        f"\t{method_signature(mi)}\n"
                    )
                if not only or image in only:
                    listing += type_listing(ti) + [""]
            if listing:
                with open(os.path.join(out_dir, image + ".cs"), "w") as f:
                    f.write(
                        f"// {image}  build {build_guid()}\n\n" + "\n".join(listing)
                    )

    with open(os.path.join(out_dir, "strings.tsv"), "w") as f:
        for i in range(len(SL)):
            f.write(f"{i}\t{strlit(i)!r}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1], set(sys.argv[2:]))
