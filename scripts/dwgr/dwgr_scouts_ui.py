"""Pictures for the play UI's Arrakeen Scouts card from Dire Wolf Game Room.

The Game Room companion shows each revealed Arrakeen Scouts item as a page:
a blue header band (the item's kind and name), a painting per kind on the
left and an orange-brown parchment holding the item on the right. The play
UI draws the revealed item as a card over the board in the same look
(``static/scouts_stage.js``), so it needs those pictures: the five paintings,
the parchment, the two header bars, the bar behind a divider and the
starfield behind the header.

This tool reads them from the installed app (``il2meta.DATA_DIR``, the
``dwgr`` alias by default) and writes them as WebP into the private assets
checkout's ``cards/app/scouts/`` (user decision 2026-10-07: pictures the play
UI shows are game assets), with ``scouts_sources.json`` recording each
picture's sprite, asset file, path id, size and sha256 and the app's
build-guid. Only pictures are taken: no text, prefab or layout data of the
app goes anywhere (the layout notes stay in the git-ignored
``reference/dwgr-arrakeen-scouts/ui/``).

Usage (from ``scripts/dwgr``)::

    uv run --no-project --with UnityPy --with pillow python dwgr_scouts_ui.py
    uv run --no-project --with UnityPy --with pillow python dwgr_scouts_ui.py \
        --out DIR

Running it again over the same app build writes the same bytes.
"""

import argparse
import hashlib
import json
import os

import UnityPy
from il2meta import DATA_DIR, build_guid
from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_OUT = os.path.join(REPO, "assets", "cards", "app", "scouts")
SOURCE_FILE = "resources.assets"
SOURCES_JSON = "scouts_sources.json"

# Play UI name (display.scouts_art.SCOUTS_ART_NAMES) -> app sprite. The five
# paintings are the left-hand illustrations of the app's reveal pages, one per
# kind; the rest are the pieces every page shares.
SCOUTS_UI_SOURCES = {
    "mission": "SPICE_ill_MESAS_M_Announcement",
    "event": "SPICE_ill_MESAS_E_Announcement",
    "auction": "SPICE_ill_MESAS_A_Announcement1",
    "sale": "SPICE_ill_MESAS_S_Announcement1",
    "subcommittee": "SPICE_ill_MESAS_SubAnnouncement",
    # the parchment the item stands on, its left edge slanted
    "back": "SPICE_frm_Back",
    # the header band: the dark upper strip (kind) and the blue lower one
    # (name), which steps up to the top on the right
    "header_upper": "SPICE_frm_HeaderBar3",
    "header_lower": "SPICE_frm_HeaderBar2",
    # the translucent bar the app puts between alternatives
    "or_backer": "SPICE_frm_HorizontalBacker",
    # the page's background, seen through and around the header
    "starfield": "SPICE_tex_Starfield",
}
# The big pictures are shown at most about 700 CSS pixels wide (the board is
# at most about 900), so a long side of 1400 keeps them sharp on a 2x screen.
# The thin bars keep the app's pixels.
MAX_SIDE = 1400
DOWNSCALED = frozenset(
    {"mission", "event", "auction", "sale", "subcommittee", "back", "starfield"}
)
WEBP_QUALITY = 85


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_sprites(env, names):
    """Return ``{sprite name: object reader}`` for the wanted sprites."""

    wanted = set(names)
    found = {}
    for asset in env.files.values():
        objects = getattr(asset, "objects", None)
        if not objects:
            continue
        for reader in objects.values():
            if reader.type.name != "Sprite":
                continue
            name = reader.peek_name()
            if name in wanted:
                if name in found:
                    raise SystemExit(f"two sprites named {name}")
                found[name] = reader
    missing = sorted(wanted - set(found))
    if missing:
        raise SystemExit(f"sprites not found in {SOURCE_FILE}: {missing}")
    return found


def picture(sprite, name):
    """The sprite's pixels, downscaled where the play UI needs fewer.

    A sprite whose every pixel is opaque loses its alpha channel; one with
    any transparency (a slanted edge, a fading bar, the starfield) keeps it.
    """

    image = sprite.image.convert("RGBA")
    if name in DOWNSCALED and max(image.size) > MAX_SIDE:
        scale = MAX_SIDE / max(image.size)
        size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(size, Image.Resampling.LANCZOS)
    if image.getchannel("A").getextrema() == (255, 255):
        image = image.convert("RGB")
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=DEFAULT_OUT, help="output folder")
    args = parser.parse_args()
    out = args.out
    os.makedirs(out, exist_ok=True)
    env = UnityPy.load(os.path.join(DATA_DIR, SOURCE_FILE))
    sprites = find_sprites(env, SCOUTS_UI_SOURCES.values())
    rows = {}
    for name, sprite_name in SCOUTS_UI_SOURCES.items():
        reader = sprites[sprite_name]
        sprite = reader.read()
        image = picture(sprite, name)
        filename = f"{name}.webp"
        path = os.path.join(out, filename)
        image.save(path, "WEBP", quality=WEBP_QUALITY, method=6)
        rect = sprite.m_Rect
        offset = sprite.m_RD.textureRectOffset
        rows[name] = {
            "file": filename,
            "sprite": sprite_name,
            "asset_file": os.path.basename(reader.assets_file.name),
            "path_id": reader.path_id,
            # the sprite's rect in the app and where its stored pixels sit
            # in it (a trimmed sprite stores less than its rect)
            "sprite_rect": [round(rect.width), round(rect.height)],
            "texture_offset": [round(offset.x, 2), round(offset.y, 2)],
            "size": list(image.size),
            "alpha": image.mode == "RGBA",
            "sha256": sha256(path),
        }
        print(f"{filename}: {sprite_name} {image.size} {os.path.getsize(path)} bytes")
    sources = {"build_guid": build_guid(), "pictures": rows}
    with open(os.path.join(out, SOURCES_JSON), "w") as f:
        json.dump(sources, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    print(f"{len(rows)} pictures -> {out}")


if __name__ == "__main__":
    main()
