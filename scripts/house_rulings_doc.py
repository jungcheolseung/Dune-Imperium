"""Write docs/rules/house-rulings-ko.md from display.house_rulings.

    uv run scripts/house_rulings_doc.py          # rewrite the document
    uv run scripts/house_rulings_doc.py --check  # exit 1 if it is stale

Each entry links to its question through the anchor open-questions.md's own
index table gives it, so a renamed question heading shows up here as a
missing anchor rather than as a dead link.
"""

import argparse
import re
import sys
from pathlib import Path

from dune_imperium.display.house_rulings import house_rulings_markdown

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "docs" / "rules" / "open-questions.md"
DOCUMENT = ROOT / "docs" / "rules" / "house-rulings-ko.md"

# "| [OQ-113](#oq-113--...) | title | `DECIDED` |"
_INDEX_ROW = re.compile(r"^\| \[(OQ-\d{3})\]\(#([^)]+)\) \| .* \| `([A-Z]+)` \|$")


def question_index(text: str) -> dict[str, tuple[str, str]]:
    """Each question's (anchor, status) from the index table."""

    index: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        match = _INDEX_ROW.match(line)
        if match:
            index[match.group(1)] = (match.group(2), match.group(3))
    return index


def render() -> str:
    index = question_index(QUESTIONS.read_text(encoding="utf-8"))
    return house_rulings_markdown(
        {question: anchor for question, (anchor, _) in index.items()}
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only compare")
    args = parser.parse_args()
    text = render()
    if args.check:
        current = DOCUMENT.read_text(encoding="utf-8") if DOCUMENT.exists() else ""
        if current != text:
            print(f"{DOCUMENT.relative_to(ROOT)} is stale; rerun without --check")
            return 1
        return 0
    DOCUMENT.write_text(text, encoding="utf-8")
    print(f"wrote {DOCUMENT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
