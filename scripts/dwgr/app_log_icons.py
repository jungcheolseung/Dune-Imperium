"""Action-log pictures for the play UI from the installed Steam Dune: Imperium app.

The app's Action Log shows one icon per entry on a dark navy tile
(``UI_frm_ActionLogEntry_IconContainer``). Most of those icons are the same
artwork as the play UI's rulebook-icon set (``app_assets.py icons``), which
the log reuses. This tool writes the ones the set lacks to the assets
checkout's ``icons/log_<key>.png`` (``dune_imperium.display.log_icons``) and
their sources to ``icons/log_sources.json``. That file is separate from
``icons/app_sources.json`` because ``app_assets.py icons`` rewrites the latter
with its own names only.

Every picture is trimmed to its drawn pixels and padded to a square, so it
fills the log's small tile. Two families get more:

- the Round numerals (``round_1`` ... ``round_10``) keep the app's sprite
  frame and share one crop, so the numerals keep one height and baseline;
- the troop deploy and retreat badges are cut to the opaque hex badge: the
  glow ring around it took most of the 64 px sprite and left the arrow
  unreadable at log size.

The table names the app's own sprites, spelling slips included
(``SpaceGuildDown``). Where a 128 px version of the same picture exists it is
used instead of the 64 px log sprite. Nothing from the app goes into this
repository; the pictures go into the private assets repository like the other
play-UI pictures (user decision, 2026-10-07).

Usage (from ``scripts/dwgr``)::

    uv run --no-project --with UnityPy python app_log_icons.py [--out DIR]

It needs ``app_assets.py index`` first (the index in the assets checkout's
``reference/dune-steam-app/<build-guid>/render/``).
"""

import argparse
import json
import os
import sys

# Play-UI log picture (dune_imperium.display.log_icons.LOG_ICON_NAMES)
# -> app sprite. tests/unit/display/test_log_icons.py keeps the two in step.
LOG_ICON_SOURCES = {
    "conflict": "UI_icon_Conflict",
    **{f"round_{n}": f"UI_icon_ActionLog_Round{n}" for n in range(1, 11)},
    "reshuffle": "UI_icon_ActionLog_Reshuffle",
    "card_trashed": "UI_icon_ActionLog_CardTrashed",
    "intrigue_played": "UI_icon_ActionLog_IntriguePlayed",
    "intrigue": "UI_icon_ActionLog_Intrigue",
    "troop_deploy": "UI_icon_ActionLog_TroopDeploy",
    "troop_retreat": "UI_icon_ActionLog_TroopRetreat",
    "vp_winner": "UI_icon_ActionLog_VPWinner",
    "influence_down_emperor": "UI_icon_ActionLog_EmperorDown",
    "influence_down_spacing_guild": "UI_icon_ActionLog_SpaceGuildDown",
    "influence_down_bene_gesserit": "UI_icon_ActionLog_BeneGesseritDown",
    "influence_down_fremen": "UI_icon_ActionLog_FremenDown",
    "tleilaxu": "UI_icon_Tleilaxu",
    "research": "UI_icon_Research",
    "family_atomics": "UI_icon_FamilyAtomics",
    "tech": "UI_icon_ActionLog_Tech",
}

# The badges whose glow ring is cut away: the badge is the opaque part.
BADGES = ("troop_deploy", "troop_retreat")
BADGE_ALPHA = 200
ROUNDS = tuple(f"round_{n}" for n in range(1, 11))


def filename(key):
    return f"log_{key}.png"


def square(im):
    """`im` centred on a transparent square of its longer side."""
    from PIL import Image

    side = max(im.size)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.alpha_composite(im, ((side - im.width) // 2, (side - im.height) // 2))
    return out


def trimmed(im, alpha=1, margin=0):
    """`im` cut to the box of its pixels with at least `alpha` opacity, plus
    `margin` pixels (the anti-aliased edge under that opacity)."""
    mask = im.getchannel("A").point(lambda a: 255 if a >= alpha else 0)
    box = mask.getbbox()
    if box is None:
        raise SystemExit("an empty picture")
    left, top, right, bottom = box
    return im.crop(
        (
            max(left - margin, 0),
            max(top - margin, 0),
            min(right + margin, im.width),
            min(bottom + margin, im.height),
        )
    )


def in_frame(im, meta):
    """`im` back on its sprite's whole rect: the atlas trims the transparent
    margins, ``offset`` (from the rect's lower left) says where it sat."""
    from PIL import Image

    width, height = (round(v) for v in meta["rect"])
    x, y = (round(v) for v in meta["offset"])
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out.alpha_composite(im, (x, height - y - im.height))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", help="folder to write (default: assets icons/)")
    args = ap.parse_args()

    from app_assets import ASSETS, App, build_guid, sha256
    from PIL import Image

    out = args.out or os.path.join(ASSETS, "icons")
    os.makedirs(out, exist_ok=True)
    app = App()
    raw = {}
    for key, sprite in LOG_ICON_SOURCES.items():
        path = os.path.join(out, filename(key))
        meta = app.save_picture(sprite, path)
        if meta is None:
            raise SystemExit(f"missing app sprite {sprite} for {key}")
        raw[key] = (Image.open(path).convert("RGBA"), meta)

    pictures = {}
    for key, (im, _meta) in raw.items():
        if key in BADGES:
            pictures[key] = square(trimmed(im, BADGE_ALPHA, margin=1))
        elif key not in ROUNDS:
            pictures[key] = square(trimmed(im))
    # The numerals share one box so that they keep one size and baseline.
    framed = {key: in_frame(*raw[key]) for key in ROUNDS}
    boxes = [im.getchannel("A").getbbox() for im in framed.values()]
    union = (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
    for key, im in framed.items():
        pictures[key] = square(im.crop(union))

    rows = {}
    for key, im in pictures.items():
        path = os.path.join(out, filename(key))
        im.save(path)
        rows[key] = {
            "sprite": LOG_ICON_SOURCES[key],
            "size": list(im.size),
            "sha256": sha256(path),
        }
    json.dump(
        {"build_guid": build_guid(), "icons": rows},
        open(os.path.join(out, "log_sources.json"), "w"),
        indent=1,
        sort_keys=True,
    )
    print("log icons:", len(rows), "->", out)


if __name__ == "__main__":
    sys.exit(main())
