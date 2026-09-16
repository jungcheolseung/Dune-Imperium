"""Summarize a soak directory: per sweep the tool's result line and the census
dimensions with zero-count content. Usage: soak_summary.py OUT_DIR"""

import json
import sys
from pathlib import Path

B = Path(sys.argv[1])
for out in sorted(B.glob("*.out")):
    lines = [
        line for line in out.read_text(errors="replace").splitlines() if line.strip()
    ]
    if not lines:
        print(f"== {out.stem}: (running)")
        continue
    markers = ("games finished", "FAIL", "Error", "violation", "Traceback")
    result = [line for line in lines if any(marker in line for marker in markers)]
    print(f"== {out.stem}: " + (result[-1][:160] if result else lines[-1][:160]))
    cov = B / f"{out.stem}.coverage.json"
    if cov.exists():
        doc = json.loads(cov.read_text())
        for ruleset, entry in doc.items():
            zero = entry.get("zero", {})
            nonempty = (
                {dim: items for dim, items in zero.items() if items}
                if isinstance(zero, dict)
                else {"?": zero}
            )
            desc = "; ".join(
                f"{dim}({len(items)}): {', '.join(items[:6])}"
                f"{'…' if len(items) > 6 else ''}"
                for dim, items in nonempty.items()
            )
            print(f"    {ruleset}: {desc if desc else 'no zero-count content'}")
