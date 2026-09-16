#!/bin/zsh
# The twelve baseline cells of docs/evaluation/baseline-2026-09-16.md sections 1-12, same commands.
# About 15 minutes on an M4 with 8 workers. Usage: scripts/ab/baseline_cells.sh [OUT_DIR]
set -u
cd "$(git rev-parse --show-toplevel)"
B="${1:-ab-runs/baseline}"
mkdir -p "$B"
LOG="$B/baseline.log"
echo "head=$(git rev-parse --short HEAD) dirty=$(git status --short | tr '\n' ' ') start=$(date '+%F %T')" >> "$LOG"
cell() {
  name="$1"; shift
  echo "cell=$name start=$(date '+%T')" >> "$LOG"
  uv run dune-imperium-tournament "$@" --rotate-leaders --workers 8 \
    --json "$B/$name.json" --markdown "$B/$name.md" > "$B/$name.out" 2>&1
  echo "exit=$? cell=$name end=$(date '+%T')" >> "$LOG"
}
cell b01 --agents heuristic,random,random,random --games 25 --ruleset base
cell b02 --agents heuristic --games 200 --ruleset both
cell b03 --agents random --games 200 --ruleset base
cell b05 --agents heuristic,random,random,random --games 200 --ruleset base
cell b06 --agents heuristic,random,random,random --games 200 --ruleset choam
cell b07 --agents heuristic,random,random,random --games 25 --ruleset base --bloodlines
cell b08 --agents heuristic,random,random,random --games 25 --ruleset base --bloodlines --tech-module
cell b09 --agents heuristic,random,random,random --games 25 --ruleset base --immortality
cell b10 --agents heuristic,random,random,random --games 25 --ruleset base --promo-cards --bloodlines --tech-module --immortality
cell b11 --agents heuristic --games 100 --ruleset both --promo-cards --bloodlines --tech-module --immortality
cell b04 --agents rollout,heuristic,heuristic,heuristic --games 25 --ruleset base
cell b12 --agents rollout,heuristic,heuristic,heuristic --games 15 --ruleset base --promo-cards --bloodlines --tech-module --immortality
echo "ALL_DONE end=$(date '+%F %T')" >> "$LOG"
uv run python scripts/ab/summarize_cells.py "$B"
