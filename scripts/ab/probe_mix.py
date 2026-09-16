"""Placement-mix and end-state probe for two agent kinds.

Mirrors ``simulation.runner._advance_one_decision`` but keeps the events, so
Conflict wins can be counted alongside the ``agent_turn`` placements and the
final seat state. Same specs as the tournament (``tournament_specs``), so seeds,
leaders and seat rotations match the A/B cells.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

from dune_imperium.content.uprising import BOARD_SPACES_BY_ID
from dune_imperium.evaluation import tournament as T
from dune_imperium.simulation import runner as R

LANDSRAAD = {
    "high_council",
    "imperial_privilege",
    "swordmaster",
    "assembly_hall",
    "gather_support",
}


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
    searchers = R._state_agents(agents)
    state = engine.reset(config, spec.game_seed)
    chance = R.ChanceResolver(seed=spec.game_seed)
    placements = [Counter() for _ in spec.seat_agents]
    conflict_wins = [0 for _ in spec.seat_agents]
    for _ in range(spec.max_steps):
        if state.phase is R.GamePhase.FINISHED:
            break
        decision = engine.current_decision(state)
        if isinstance(decision, R.ChanceDecision):
            result = engine.apply(state, chance.resolve(decision))
        else:
            actions = engine.legal_actions(state, decision.owner)
            observation = engine.observe(state, decision.owner)
            searcher = searchers[decision.owner]
            action = (
                searcher.choose_action_with_state(state, observation, actions)
                if searcher is not None
                else agents[decision.owner].choose_action(observation, actions)
            )
            if action.action_id == "agent_turn":
                placements[decision.owner][dict(action.arguments)["space_id"]] += 1
            result = engine.apply(state, action)
        for event in getattr(result, "events", ()):
            if event.kind == "conflict_won":
                conflict_wins[dict(event.payload)["player"]] += 1
        state = result.state
    else:
        raise RuntimeError("step limit")
    standings = {s.player: s for s in R.final_standings(state)}
    rows = []
    for seat, kind in enumerate(spec.seat_agents):
        p = state.players[seat]
        inf = p.influence
        rows.append(
            {
                "kind": kind,
                "win": standings[seat].rank == 1,
                "vp": standings[seat].victory_points,
                "influence": inf.emperor
                + inf.spacing_guild
                + inf.bene_gesserit
                + inf.fremen,
                "alliances": len(p.alliance_faction_ids),
                "spice": p.resources.spice,
                "solari": p.resources.solari,
                "swordmaster": int(p.swordmaster_acquired),
                "council": int(p.high_council),
                "control": len(p.control_space_ids),
                "garrison": p.troops_garrison,
                "conflict_wins": conflict_wins[seat],
                "placements": dict(placements[seat]),
            }
        )
    return spec.game_seed, config.identifier, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", default="heuristic,heuristic_space_demote3")
    ap.add_argument("--games", type=int, default=150)
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
        agents=tuple(a.agents.split(",")),
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
        results = list(pool.map(play, specs, chunksize=4))
    per_kind = defaultdict(list)
    for _, _, rows in results:
        for row in rows:
            per_kind[row["kind"]].append(row)
    summary = {}
    for kind, rows in per_kind.items():
        n = len(rows)
        place = Counter()
        for row in rows:
            place.update(row["placements"])
        total = sum(place.values())
        combat = sum(
            c
            for s, c in place.items()
            if s in BOARD_SPACES_BY_ID and BOARD_SPACES_BY_ID[s].combat
        )
        lands = sum(c for s, c in place.items() if s in LANDSRAAD)
        top3 = sum(c for _, c in place.most_common(3))

        def mean(key, rows=rows, n=n):
            return sum(r[key] for r in rows) / n

        summary[kind] = {
            "seat_games": n,
            "win_rate": sum(r["win"] for r in rows) / n,
            "vp": mean("vp"),
            "influence": mean("influence"),
            "alliances": mean("alliances"),
            "spice": mean("spice"),
            "solari": mean("solari"),
            "swordmaster": mean("swordmaster"),
            "council": mean("council"),
            "control": mean("control"),
            "garrison": mean("garrison"),
            "conflict_wins": mean("conflict_wins"),
            "placements_per_seat": total / n,
            "combat_share": combat / total if total else 0.0,
            "landsraad_share": lands / total if total else 0.0,
            "top3_share": top3 / total if total else 0.0,
            "per_space": {s: c / n for s, c in place.most_common()},
        }
    with open(a.out, "w") as fh:
        json.dump(
            {"args": vars(a), "matches": len(results), "summary": summary}, fh, indent=1
        )
    keys = [
        "win_rate",
        "vp",
        "influence",
        "alliances",
        "conflict_wins",
        "swordmaster",
        "council",
        "control",
        "garrison",
        "spice",
        "solari",
        "placements_per_seat",
        "combat_share",
        "landsraad_share",
        "top3_share",
    ]
    print(
        f"matches={len(results)} ruleset={a.ruleset} flags="
        + ",".join(
            k
            for k in ("bloodlines", "tech_module", "immortality", "promo_cards")
            if getattr(a, k)
        )
    )
    print("| 표 | " + " | ".join(keys) + " |")
    print("| --- |" + " ---: |" * len(keys))
    for kind, s in summary.items():
        print(
            f"| {kind} | "
            + " | ".join(
                (
                    f"{100 * s[k]:.1f}%"
                    if k
                    in ("win_rate", "combat_share", "landsraad_share", "top3_share")
                    else f"{s[k]:.2f}"
                )
                for k in keys
            )
            + " |"
        )
    for kind, s in summary.items():
        top = list(s["per_space"].items())[:10]
        print(
            f"{kind} top spaces per seat: "
            + ", ".join(f"{sp} {v:.2f}" for sp, v in top)
        )


if __name__ == "__main__":
    main()
