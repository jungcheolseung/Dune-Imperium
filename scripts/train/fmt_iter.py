"""Print one compact line for the Nth record of a training.jsonl."""

import json
import sys

path, index = sys.argv[1], int(sys.argv[2])
with open(path) as handle:
    for number, line in enumerate(handle, 1):
        if number == index:
            record = json.loads(line)
            break
    else:
        raise SystemExit(f"no record {index}")
update = record["update"]
ppo = ""
if update.get("clip_fraction"):
    ppo = f" clip {update['clip_fraction']:.2f} kl {update['approx_kl']:+.4f}"
evaluation = ""
if record["eval_win_rate"] is not None:
    evaluation = (
        f" | EVAL vs heuristic x3: win {record['eval_win_rate']:.1%}"
        f" rank {record['eval_mean_rank']:.2f}"
    )
    if record.get("eval_failures"):
        evaluation += f" ({record['eval_failures']} eval matches FAILED)"
print(
    f"iter {record['iteration']}: steps {record['learner_steps']}"
    f" rounds {record['mean_rounds']:.1f} truncated {record['truncated']}"
    f" collect {record['collect_seconds']:.0f}s update {record['update_seconds']:.0f}s"
    f" entropy {update['entropy']:.3f} ev {update['explained_variance']:+.2f}"
    f"{ppo}{evaluation}"
)
