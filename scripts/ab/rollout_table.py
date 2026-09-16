"""Rollout cell table: win rate, mean rank, VP margin, ms/decision, duration.

Usage: rollout_table.py DIR...
"""

import json
import sys
from pathlib import Path

print("| 셀 | rollout 승률 | 평균 순위 | VP margin | ms/decision | 판 | 소요 | 실패 |")
print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
for d in sys.argv[1:]:
    for path in sorted(Path(d).glob("*.json")):
        doc = json.loads(path.read_text())
        r = next((a for a in doc["agents"] if a["agent"].startswith("rollout")), None)
        if r is None:
            continue
        print(
            f"| {path.parent.name}/{path.stem} ({r['agent']}) | "
            f"{100 * r['win_rate']:.1f}% | {r['mean_rank']:.2f} | "
            f"{r['mean_vp_margin']:+.2f} | {r['mean_decision_ms']:.1f} | "
            f"{doc['matches']} | {doc['duration_seconds']:.0f}s | {doc['failures']} |"
        )
