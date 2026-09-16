#!/bin/zsh
# Verification soak across every ruleset axis with the heuristic (one random pass), soundness
# checks every 25 decisions, coverage census per configuration. About 30 minutes on an M4 with
# 8 workers. Usage: scripts/ab/soak.sh [OUT_DIR]   (default ab-runs/soak)
set -u
cd "$(git rev-parse --show-toplevel)"
B="${1:-ab-runs/soak}"
mkdir -p "$B"
LOG="$B/soak.log"
echo "head=$(git rev-parse --short HEAD) dirty=$(git status --short | tr '\n' ' ') start=$(date '+%F %T')" >> "$LOG"
sweep() {
  name="$1"; shift
  echo "sweep=$name start=$(date '+%T')" >> "$LOG"
  uv run dune-imperium-sweep "$@" --workers 8 --soundness-interval 25 --coverage-json "$B/$name.coverage.json" > "$B/$name.out" 2>&1
  echo "exit=$? sweep=$name end=$(date '+%T') $(grep -E 'games finished|failure|Traceback' "$B/$name.out" | tail -1)" >> "$LOG"
}
sweep h_base_choam      --policy heuristic --games 1000 --ruleset both --rotate-leaders
sweep h_bloodlines      --policy heuristic --games 1000 --ruleset both --rotate-leaders --bloodlines
sweep h_tech            --policy heuristic --games 1000 --ruleset both --rotate-leaders --bloodlines --tech-module
sweep h_immortality     --policy heuristic --games 1000 --ruleset both --rotate-leaders --immortality
sweep h_all_promo       --policy heuristic --games 1000 --ruleset both --rotate-leaders --promo-cards --bloodlines --tech-module --immortality
sweep h_all_promo_draft --policy heuristic --games 500  --ruleset both --leader-draft   --promo-cards --bloodlines --tech-module --immortality
sweep r_all_promo       --policy random    --games 500  --ruleset both --rotate-leaders --promo-cards --bloodlines --tech-module --immortality
echo "ALL_DONE end=$(date '+%F %T')" >> "$LOG"
uv run python scripts/ab/soak_summary.py "$B"
