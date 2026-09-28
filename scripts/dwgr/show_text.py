"""Print the app's own wording for Arrakeen Scouts loc keys, from a local extraction.

The rules docs cite the companion app by loc key (``spice.mission.choamescort.desc``)
and keep only paraphrase: the app's text is Dire Wolf Digital's and stays out of
every repository (README, "출력은 어느 저장소에도 넣지 않는다"). This prints the
exact English (and, with ``--ko``, Korean) text on the machine that holds an
extraction, so a ruling can be checked against the original word for word.

    uv run --no-project python scripts/dwgr/show_text.py spice.mission.choamescort.desc
    uv run --no-project python scripts/dwgr/show_text.py contingencies --ko

An argument that is not a whole key matches every key containing it. Text
sprites print as ``<sprite=N>``; ``text_sprites.json`` in the same extraction
names them (for example the Helix).
"""

import argparse
import json
import sys
from pathlib import Path

_DEFAULT_DATA = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "reference"
    / "dwgr-arrakeen-scouts"
    / "data"
)


def _load(data: Path, language: str) -> dict[str, str]:
    path = data / "loc" / f"{language}.json"
    if not path.is_file():
        sys.exit(f"no extraction at {path}; run extract.py first (README)")
    loaded: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("keys", nargs="+", help="loc keys, or parts of keys")
    parser.add_argument("--ko", action="store_true", help="also print ko_KR")
    parser.add_argument("--data", type=Path, default=_DEFAULT_DATA)
    args = parser.parse_args()
    languages = ["en_US", *(["ko_KR"] if args.ko else [])]
    tables = {language: _load(args.data, language) for language in languages}
    english = tables["en_US"]
    for wanted in args.keys:
        matches = sorted(key for key in english if wanted in key)
        keys = [wanted] if wanted in english else matches
        if not keys:
            print(f"{wanted}: no such key")
            continue
        for key in keys:
            print(key)
            for language in languages:
                print(f"  [{language}] {tables[language].get(key, '(missing)')}")


if __name__ == "__main__":
    main()
