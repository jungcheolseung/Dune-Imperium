"""Draw the project's own icons, log icons, pieces and card backs
(docs/own-pictures-plan.md stages 2, 4 and 5).

The drawings are code in ``icon_drawing/``: ``draw`` makes the icon set
(``static/pictures/icons``), the action log's icons (``log``) and the marks
the card faces use (``faces``); ``pieces`` the pieces and tokens and
``backs`` the card backs (both ``tokens``). Each drawing's note goes into
``static/pictures/index.json``. To change a picture, change its code here
and run this script; never edit the SVG it writes. Two pictures are
hand-written SVG files instead (``icons/solari.svg``,
``faces/specimen_cube.svg``) and are edited as files. The boards come from
``board.py``, which embeds these icons, so rerun it after an icon changes.

``--check`` writes nothing and fails when a drawing or note is out of date.

    uv run python scripts/own_pictures/icons.py [--check]
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PICTURES = REPO / "src/dune_imperium/server/static/pictures"
PACKAGE = HERE / "icon_drawing"
# Each module draws from a fresh import of the package: the drawings number
# their gradient ids from counters in the shared modules, and the files keep
# the numbers each module's own run gave them.
MODULES = ("draw", "pieces", "backs")


def fresh(name: str) -> ModuleType:
    """``icon_drawing.<name>`` imported anew, its package with it (loaded
    from its path, so this folder never goes on ``sys.path``)."""
    for key in [k for k in sys.modules if k.split(".")[0] == "icon_drawing"]:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(
        "icon_drawing",
        PACKAGE / "__init__.py",
        submodule_search_locations=[str(PACKAGE)],
    )
    assert spec is not None and spec.loader is not None
    package = importlib.util.module_from_spec(spec)
    sys.modules["icon_drawing"] = package
    spec.loader.exec_module(package)
    return importlib.import_module(f"icon_drawing.{name}")


def drawings() -> dict[str, str]:
    """Every drawn file by its path under ``static/pictures``, index.json
    (with the drawings' notes merged in) included."""
    index = json.loads((PICTURES / "index.json").read_text())
    files: dict[str, str] = {}
    for name in MODULES:
        files.update(fresh(name).build(index))
    files["index.json"] = (
        json.dumps(dict(sorted(index.items())), indent=2, ensure_ascii=False) + "\n"
    )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="fail if a drawing is out of date"
    )
    args = parser.parse_args()
    stale = []
    files = drawings()
    for name, text in files.items():
        path = PICTURES / name
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(name)
        elif not path.exists() or path.read_text() != text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote {path.relative_to(REPO)}")
    if stale:
        print("out of date:", ", ".join(stale), file=sys.stderr)
        return 1
    print(f"{len(files)} files {'checked' if args.check else 'current'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
