#!/bin/bash
# Event stream for a supervised M10 run: selected iterations from training.jsonl
# (flushed per iteration; train.log is block-buffered) -- the first, every
# REPORT_EVERY-th record, and every record carrying an in-loop evaluation (those
# fall on multiples of --eval-every in GLOBAL iterations, which a resumed run's
# record count does not line up with) -- restarts and the final line of
# supervisor.log, error signatures from train.log, the guard's memory-pressure
# changes and LOW MEMORY line. Polls; exits by itself when the supervisor ends.
# usage: watch_run.sh RUN_DIR [already_reported_iterations] [report_every]
HERE="$(cd "$(dirname "$0")" && pwd)"
RUN="$1"; last="${2:-0}"; every="${3:-25}"; errs=0; sup=0
# Report only pressure changes that happen after the watch starts.
pres=$(grep -c "memory pressure level" "$RUN/guard.log" 2>/dev/null); pres=${pres:-0}
while true; do
  n=0; [ -f "$RUN/training.jsonl" ] && n=$(wc -l < "$RUN/training.jsonl")
  i=$((last+1))
  while [ "$i" -le "$n" ]; do
    evaluated=$(sed -n "${i}p" "$RUN/training.jsonl" | grep -c '"eval_win_rate": [0-9]')
    if [ "$i" = 1 ] || [ $((i % every)) = 0 ] || [ "$evaluated" -gt 0 ]; then
      python3 "$HERE/fmt_iter.py" "$RUN/training.jsonl" "$i" || echo "iter $i recorded (format failed)"
    fi
    # A burst of games hitting the decision cap means a policy loop is forming.
    t=$(sed -n "${i}p" "$RUN/training.jsonl" | sed -E 's/.*"truncated": ([0-9]+).*/\1/')
    if [ "${t:-0}" -ge 3 ] 2>/dev/null; then
      echo "ALERT: iteration $i had $t truncated games: $(python3 "$HERE/fmt_iter.py" "$RUN/training.jsonl" "$i")"
    fi
    i=$((i+1))
  done
  last=$n
  e=$(grep -c -E "Traceback|Error|Killed|BrokenProcessPool" "$RUN/train.log" 2>/dev/null); e=${e:-0}
  if [ "$e" -gt "$errs" ]; then
    echo "ERROR in train.log: $(grep -E 'Traceback|Error|Killed|BrokenProcessPool' "$RUN/train.log" | tail -2 | cut -c1-240 | tr '\n' ' ')"
    errs=$e
  fi
  p=$(grep -c "memory pressure level" "$RUN/guard.log" 2>/dev/null); p=${p:-0}
  if [ "$p" -gt "$pres" ]; then
    grep "memory pressure level" "$RUN/guard.log" | tail -n $((p-pres)) | cut -c1-200 | sed 's/^/MEMORY: /'
    pres=$p
  fi
  s=0; [ -f "$RUN/supervisor.log" ] && s=$(grep -c -E "attempt ended|LOW MEMORY|supervisor-exit" "$RUN/supervisor.log")
  if [ "$s" -gt "$sup" ]; then
    grep -E "attempt ended|supervisor-exit" "$RUN/supervisor.log" | tail -n $((s-sup)) | cut -c1-240
    sup=$s
  fi
  if grep -q "supervisor-exit" "$RUN/supervisor.log" 2>/dev/null; then
    grep "LOW MEMORY" "$RUN/guard.log" 2>/dev/null | tail -1 | cut -c1-200
    echo "RUN ENDED after $n iterations"
    exit 0
  fi
  sleep 20
done
