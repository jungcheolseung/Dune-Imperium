"""Sanity checks before an A/B round.

The null variants must equal the committed agents decision for decision, every
variant must play a game on every ruleset, and each ``prefer`` hook must fire.

    uv run python scripts/ab/sanity.py            # heuristic variants (seconds)
    uv run python scripts/ab/sanity.py --rollout  # also the rollout nulls (a minute)
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "pypath"))
import hvariants  # noqa: E402

from dune_imperium.agents import HeuristicAgent, registry  # noqa: E402
from dune_imperium.config import RulesetConfig  # noqa: E402
from dune_imperium.evaluation import tournament as T  # noqa: E402
from dune_imperium.rules import UprisingRulesEngine  # noqa: E402
from dune_imperium.simulation import runner as R  # noqa: E402
from dune_imperium.simulation.runner import run_policy_game  # noqa: E402

hvariants.register(registry)
hvariants.register_rollout(registry)


def play(spec, hook_counter=None):
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
    if hook_counter is not None:
        for agent in agents:
            if isinstance(agent, hvariants.VariantAgent):
                original = agent.prefer

                def counting(top, view, _orig=original, _c=hook_counter):
                    out = tuple(_orig(top, view))
                    if len(out) < len(top):
                        _c[top[0].action_id] += 1
                    return out

                agent.prefer = counting
    state = engine.reset(config, spec.game_seed)
    chance = R.ChanceResolver(seed=spec.game_seed)
    taken = []
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
        taken.append(action)
        state = engine.apply(state, action, legal_actions=actions).state
    else:
        raise RuntimeError("step limit")
    return taken


def specs_for(kind, games, **flags):
    return T.tournament_specs(
        agents=(kind,) * 4,
        games=games,
        rulesets=(False, True),
        rotate_leaders=True,
        **flags,
    )


ALL = {
    "bloodlines": True,
    "tech_module": True,
    "immortality": True,
    "promo_cards": True,
}

for spec_h, spec_n in zip(
    specs_for("heuristic", 3), specs_for("heuristic_v_null", 3), strict=True
):
    assert play(spec_h) == play(spec_n), (
        f"null variant diverged on seed {spec_h.game_seed}"
    )
print("heuristic_v_null == heuristic on 6 base+CHOAM games: OK")

for name in hvariants.VARIANTS:
    if name == "heuristic_v_null":
        continue
    counter: Counter[str] = Counter()
    games = 0
    for flags in ({}, ALL):
        for spec in specs_for(name, 2, **flags):
            play(spec, counter)
            games += 1
    total = sum(counter.values())
    hooks = ", ".join(f"{k} {v}" for k, v in counter.most_common(6))
    print(
        f"{name}: {games} games OK; narrowed {total} ties "
        f"({total / games:.1f}/game): {hooks}"
    )

if "--rollout" in sys.argv:
    engine = UprisingRulesEngine()
    for flags in ({}, {"choam_module": True, "bloodlines": True, "tech_module": True}):
        config = RulesetConfig(**flags)
        seats = lambda kind: [  # noqa: E731
            registry.make_agent(kind, 11),
            HeuristicAgent(seed=12),
            HeuristicAgent(seed=13),
            HeuristicAgent(seed=14),
        ]
        committed = run_policy_game(engine, config, 0, seats("rollout"))
        null = run_policy_game(engine, config, 0, seats("rollout_v_null"))
        assert committed.replay.steps == null.replay.steps, (
            flags,
            "rollout_v_null diverged",
        )
        pinned = run_policy_game(engine, config, 0, seats("rollout_count_max"))
        scratch = run_policy_game(engine, config, 0, seats("rollout_v_count_max"))
        assert pinned.replay.steps == scratch.replay.steps, (
            flags,
            "count_max diverged",
        )
        print(f"rollout nulls equal the committed agents on {flags or 'base'} seed 0")
