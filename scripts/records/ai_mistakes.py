"""Freeze the AI seats' diagnosed mistakes as a problem suite (family ``ai_mistake``).

Each pick is a move an AI seat made in a saved game that people found
baffling and the diagnosis agreed was a mistake
(docs/evaluation/search-atomics-2026-10-12.md sections 1 and 7). The suite is
a yardstick for broad changes to the network (docs/entity-network-plan.md
section 4), scored like the human suite:

    uv run python scripts/records/ai_mistakes.py --saves-dir saves
    uv run dune-imperium-records problems score \\
        --suite local/records/ai-mistakes.json --agents checkpoint:<file>,search:<file>

An agent scores by not repeating the mistake: the summary's ``wrong`` share
is how often it does.

Left out: the two retreats of 2026-10-12, whose moves the search valued within
noise of the alternatives (no clear mistake), and the round-one Family
Atomics. That mistake is the round of use, not one decision: at the recorded
Agent-effect choice Y resolves another effect first and still spends the
token before the turn ends, so a single position scores it as right. Its
yardstick is the timing census (``evaluation.network_probes``).
"""

import argparse
from pathlib import Path

from dune_imperium.paths import SAVES_DIR
from dune_imperium.records.problems import (
    AI_MISTAKES_SUITE,
    build_mistake_suite,
    save_suite,
)
from dune_imperium.records.saves import saved_games

_LEAD = (
    "alone in the lead of the Combat Intrigue step, which ends only when every "
    "participant passes in a row [Main p. 14]: holding keeps the card and its cost"
)
_PLOT = (
    "plays Insider Information's 'ignore Influence requirements this turn' and then "
    "sends its Agent to a space without one; the plot buys nothing"
)

PICKS = (
    {
        "game": "885ed2f0",
        "step": 864,
        "right": {"id": "pass_combat_intrigue", "args": {}},
        "kind": "combat_intrigue_in_the_lead",
        "evidence": {
            "why": _LEAD,
            "strength": "12 against 6, 2 and 0; "
            "Spice is Power pays 3 spice for 6 swords",
        },
    },
    {
        "game": "c3adefb4",
        "step": 488,
        "right": {
            "id": "agent_turn",
            "args": {
                "card_id": "imperium:reliable_informant:0",
                "space_id": "deliver_supplies",
            },
        },
        "kind": "this_turn_plot_unused",
        "evidence": {"why": _PLOT, "space": "Deliver Supplies, the space it then took"},
    },
    {
        "game": "fb716981",
        "step": 861,
        "right": {
            "id": "agent_turn",
            "args": {
                "card_id": "player:1:starter:experimentation:0",
                "space_id": "imperial_basin",
            },
        },
        "kind": "this_turn_plot_unused",
        "evidence": {"why": _PLOT, "space": "Imperial Basin, the space it then took"},
    },
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--saves-dir", type=Path, default=SAVES_DIR)
    parser.add_argument("--out", type=Path, default=AI_MISTAKES_SUITE)
    arguments = parser.parse_args()
    games = saved_games(arguments.saves_dir)
    suite = build_mistake_suite(
        games,
        PICKS,
        note="AI seats' mistakes diagnosed 2026-10-12/13 "
        "(docs/evaluation/search-atomics-2026-10-12.md)",
    )
    save_suite(arguments.out, suite)
    print(
        f"{len(suite.problems)} problems from {len(suite.records)} games "
        f"-> {arguments.out}"
    )


if __name__ == "__main__":
    main()
