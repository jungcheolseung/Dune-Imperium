"""Tie-family census for the heuristic (scratch, not repository code).

Plays heuristic mirrors with the tournament's own specs and, at every decision of
every seat, scores the legal set with ``score_action`` exactly as ``HeuristicAgent``
does. Records where the seeded tie-break RNG still decides (top set size > 1) and,
for decided sets, which action family beat which runner-up family -- the two places
a new scoring term could have leverage (baseline-2026-09-10.md section 17(c): measure
how often a ranking is consulted before re-pricing it).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

from dune_imperium.agents.heuristic_agent import (
    score_action,
)
from dune_imperium.evaluation import tournament as T
from dune_imperium.simulation import runner as R


def _args(action):
    return dict(action.arguments)


def classify_tie(top):
    """Describe a top set of size > 1."""
    families = sorted({a.action_id for a in top})
    if len(families) > 1:
        return "cross:" + "+".join(families)
    family = families[0]
    keys = set()
    base = _args(top[0])
    for a in top[1:]:
        other = _args(a)
        for k in set(base) | set(other):
            if base.get(k) != other.get(k):
                keys.add(k)
    if family == "agent_turn":
        if "space_id" in keys:
            return "agent_turn:space"
        return (
            "agent_turn:" + "+".join(sorted(keys)) if keys else "agent_turn:identical"
        )
    return f"{family}:" + ("+".join(sorted(keys)) if keys else "identical")


def play(spec):
    config = spec.config
    engine = (
        T.UprisingRulesEngine(leader_ids=spec.leader_ids)
        if spec.leader_ids is not None
        else T.UprisingRulesEngine()
    )
    agents = tuple(
        T.make_agent(kind, spec.policy_seed + seat)
        for seat, kind in enumerate(spec.seat_agents)
    )
    state = engine.reset(config, spec.game_seed)
    chance = R.ChanceResolver(seed=spec.game_seed)
    ties = Counter()
    decided = Counter()  # (winner family, runner-up family)
    frame_kinds = Counter()  # decision kind -> tie count
    sets = 0
    forced = 0
    for _ in range(spec.max_steps):
        if state.phase is R.GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, R.ChanceDecision):
            state = engine.apply(state, chance.resolve(decision)).state
            continue
        actions = engine.legal_actions(state, decision.owner)
        observation = engine.observe(state, decision.owner)
        action = agents[decision.owner].choose_action(observation, actions)
        sets += 1
        if len(actions) == 1:
            forced += 1
        else:
            scored = [(score_action(a), a) for a in actions]
            best = max(s for s, _ in scored)
            top = [a for s, a in scored if s == best]
            if len(top) > 1:
                label = classify_tie(top)
                ties[label] += 1
                frame_kinds[(observation.decision_kind or "?", label)] += 1
            else:
                rest = [s for s, a in scored if a is not top[0]]
                runner = max(rest)
                runner_fams = sorted({a.action_id for s, a in scored if s == runner})
                decided[
                    (top[0].action_id, "|".join(runner_fams), round(best - runner, 2))
                ] += 1
        state = engine.apply(state, action, legal_actions=actions).state
    else:
        raise RuntimeError("step limit")
    return {
        "seed": spec.game_seed,
        "ruleset": config.identifier,
        "sets": sets,
        "forced": forced,
        "ties": dict(ties),
        "decided": {"|".join(map(str, k)): v for k, v in decided.items()},
        "frame_kinds": {"|".join(map(str, k)): v for k, v in frame_kinds.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--start-seed", type=int, default=0)
    ap.add_argument("--ruleset", choices=("base", "choam", "both"), default="both")
    ap.add_argument("--bloodlines", action="store_true")
    ap.add_argument("--tech-module", action="store_true")
    ap.add_argument("--immortality", action="store_true")
    ap.add_argument("--promo-cards", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rulesets = {"base": (False,), "choam": (True,), "both": (False, True)}[a.ruleset]
    specs = T.tournament_specs(
        agents=("heuristic", "heuristic", "heuristic", "heuristic"),
        games=a.games,
        rulesets=rulesets,
        start_seed=a.start_seed,
        rotate_leaders=True,
        promo_cards=a.promo_cards,
        bloodlines=a.bloodlines,
        tech_module=a.tech_module,
        immortality=a.immortality,
    )
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        results = list(pool.map(play, specs, chunksize=2))
    n = len(results)
    sets = sum(r["sets"] for r in results)
    forced = sum(r["forced"] for r in results)
    ties = Counter()
    decided = Counter()
    kinds = Counter()
    for r in results:
        ties.update(r["ties"])
        decided.update(r["decided"])
        kinds.update(r["frame_kinds"])
    total_ties = sum(ties.values())
    with open(a.out, "w") as fh:
        json.dump(
            {
                "args": vars(a),
                "games": n,
                "sets": sets,
                "forced": forced,
                "ties_total": total_ties,
                "ties": dict(ties.most_common()),
                "decided": dict(decided.most_common()),
                "frame_kinds": dict(kinds.most_common()),
            },
            fh,
            indent=1,
        )
    print(
        f"games={n} sets={sets} forced={forced} ({100 * forced / sets:.1f}%) "
        f"ties={total_ties} ({100 * total_ties / sets:.1f}% of sets, "
        f"{total_ties / n:.1f}/game)"
    )
    print("\n## Tie families (count, per game, share of ties)")
    for label, c in ties.most_common(40):
        print(f"{c:7d}  {c / n:7.2f}/game  {100 * c / total_ties:5.1f}%  {label}")
    print("\n## Decided sets: winner family | runner-up families | gap (top 40)")
    tot_dec = sum(decided.values())
    for label, c in decided.most_common(40):
        print(f"{c:7d}  {c / n:7.2f}/game  {100 * c / tot_dec:5.1f}%  {label}")


if __name__ == "__main__":
    main()
