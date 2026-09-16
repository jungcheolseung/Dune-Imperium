"""Print the twelve baseline cells as summary rows (win / rank / VP margin).

Usage: summarize_cells.py DIR
"""

import json
import sys
from pathlib import Path

D = Path(sys.argv[1])
LEAD = {2: "heuristic", 3: "random", 4: "rollout", 11: "heuristic", 12: "rollout"}
LABEL = {
    1: "heuristic vs random 3, base, 100판",
    2: "heuristic 미러, base+CHOAM, 400판",
    3: "random 미러, base, 200판",
    4: "rollout vs heuristic 3, base, 100판",
    5: "heuristic vs random 3, base, **800판**",
    6: "heuristic vs random 3, CHOAM, 800판",
    7: "heuristic vs random 3, Bloodlines, 100판",
    8: "heuristic vs random 3, Bloodlines+Tech, 100판",
    9: "heuristic vs random 3, Immortality, 100판",
    10: "heuristic vs random 3, 전 확장+프로모, 100판",
    11: "heuristic 미러, 전 확장+프로모, 200판",
    12: "rollout vs heuristic 3, 전 확장+프로모, 60판",
}
fails = 0
for n in range(1, 13):
    path = D / f"b{n:02d}.json"
    if not path.exists():
        print(f"| {LABEL[n]} | (missing) |")
        continue
    doc = json.loads(path.read_text())
    a = next(x for x in doc["agents"] if x["agent"] == LEAD.get(n, "heuristic"))
    fails += doc["failures"]
    print(
        f"| {LABEL[n]} | **{100 * a['win_rate']:.1f}% / {a['mean_rank']:.2f} / "
        f"{a['mean_vp_margin']:+.2f}** | {a['mean_decision_ms']:.1f} ms | "
        f"{doc['matches']} | {doc['failures']} |"
    )
print("failures total:", fails)
