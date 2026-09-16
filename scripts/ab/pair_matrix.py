"""Variant x axis matrix of a mirror round from ``cells.py`` (variant - control, %p).

    uv run python scripts/ab/pair_matrix.py ab-runs/round1 v_space,v_spy

Cell files are ``<variant>_<axis>[_bN].json``; the variant names are the short forms
(``heuristic_`` / ``rollout_`` stripped). Differences of 3 points or more are bold; the
parentheses hold variant / control win rates and the variant's VP margin.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

D = Path(sys.argv[1])
VARS = sys.argv[2].split(",")
AX = [
    "base",
    "choam",
    "both",
    "bloodlines",
    "immortality",
    "tech_nochoam",
    "tech_choam",
    "cbt",
    "stack_cti",
    "all_promo",
]
LABEL = {
    "base": "base",
    "choam": "CHOAM",
    "both": "base+CHOAM",
    "bloodlines": "Bloodlines",
    "immortality": "Immortality",
    "tech_nochoam": "Tech, CHOAM 없음",
    "tech_choam": "Tech, CHOAM",
    "cbt": "CHOAM+Bloodlines+Tech",
    "stack_cti": "CHOAM+Tech+Imm",
    "all_promo": "전 확장+프로모",
}
pattern = re.compile(
    r"(" + "|".join(map(re.escape, VARS)) + r")_(" + "|".join(AX) + r")(?:_b(\d+))?"
)
cells: dict[str, dict[tuple[str, str], tuple]] = defaultdict(dict)
for path in D.glob("*.json"):
    match = pattern.fullmatch(path.stem)
    if not match:
        continue
    doc = json.loads(path.read_text())
    agents = doc["agents"]
    variant = next(a for a in agents if a["agent"].endswith(match.group(1)))
    control = next(a for a in agents if a is not variant)
    block = f"b{match.group(3)}" if match.group(3) else "b1"
    cells[match.group(1)][(match.group(2), block)] = (
        100 * (variant["win_rate"] - control["win_rate"]),
        variant["mean_vp_margin"],
        100 * variant["win_rate"],
        100 * control["win_rate"],
        doc["failures"],
    )
axes = [a for a in AX if any(a == key[0] for row in cells.values() for key in row)]
print("| 변형 (블록) | " + " | ".join(LABEL[a] for a in axes) + " |")
print("| --- |" + " ---: |" * len(axes))
for variant in VARS:
    blocks = sorted({key[1] for key in cells.get(variant, {})})
    for block in blocks:
        row = {a: v for (a, b), v in cells[variant].items() if b == block}
        out = []
        for a in axes:
            if a in row:
                d, margin, wv, wc, failures = row[a]
                text = f"{d:+.1f}%p ({wv:.1f} / {wc:.1f}, {margin:+.2f}"
                text += f", 실패 {failures})" if failures else ")"
                out.append(f"**{text}**" if abs(d) >= 3 else text)
            else:
                out.append("·")
        print(f"| {variant} ({block}) | " + " | ".join(out) + " |")
