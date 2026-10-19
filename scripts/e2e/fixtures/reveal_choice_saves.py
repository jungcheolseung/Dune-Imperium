"""Save real Reveals whose card choices are rows of the Reveal list (codec v147).

User ruling 2026-10-14 (OQ-095 (7) addition): every choice effect of a
revealed card waits on the Reveal frame and is offered there beside the
purchases, gains and Plots, in any order [Main p. 12]; an optional choice
("may", an arrow cost, a black trash icon [FAQ p. 3]) offers no refusal and
lapses unused when the Reveal ends, a mandatory one keeps the Reveal's end
away while it offers something, and one that offers nothing now is a
greyed-out row with its reason. reveal_choices.py needs Reveals that show
all of it at once: an optional choice offered, a mandatory choice offered, a
card the seat can buy, and a choice waiting greyed out.

Four human seats, every expansion but Arrakeen Scouts (Bloodlines for the
Command (6+) choices); every seat plays ``random.Random(seed).randrange``
over the engine's legal actions and every hold is confirmed at once (the
seeds of today first, then 0-399). Two Reveals are saved, the first of each
kind the walks meet:

- "optional": the waiting choice is optional, so its greyed row says it
  lapses unused when the Reveal ends (seed 306 today: Public Spectacle's
  Spy icon and Arrakis Observer's recall offered, Unswerving Loyalty
  without its Fremen Bond waiting);
- "command": the waiting choice is a Command (6+) one, so its reason is
  the Persuasion the Reveal has generated (seed 167 today: Desert Power's
  branch and Unswerving Loyalty's troop offered, Intelligence Training
  waiting for Command; Desert Power's 2 Persuasion then opens it).

Prints {"optional": {...}, "command": {...}} as JSON, each {save_id, seed,
seat, round, revision, choices}: ``choices`` are the page's
``reveal_choices`` entries ({key, name, name_ko, effect, optional,
offered}).
"""

import json
import random
import sys
from pathlib import Path

from dune_imperium.display.actions import reveal_choice_headers
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

SEATS = ("human", "human", "human", "human")
OPTIONS = {
    "bloodlines": True,
    "choam_module": True,
    "immortality": True,
    "tech_module": True,
    "promo_cards": True,
}
# The seeds that meet the two Reveals today come first; the rest of the
# range follows, so an engine change that moves those games only moves the
# case to a later seed (a scan of 0-399 takes about a minute and a half).
# Seed 6 until codec v149 moved its game (Public Spectacle, Calculus of Power
# and Unswerving Loyalty); a scan of 0-399 then finds the "optional" Reveal at
# seeds 199, 306, 316 and 386 -- reveal_choices.py reads Public Spectacle's
# logged Spy step off the "optional" Reveal, and only seed 306 has that card
# among them.
KNOWN = (306, 167)
SEEDS = (*KNOWN, *(seed for seed in range(400) if seed not in KNOWN))
STEPS = 6_000

store = SaveStore(Path(sys.argv[1]))


def kind_of(choices: list[dict], buy: bool) -> str | None:
    """Which of the two Reveals this is, if it shows everything at once."""

    offered = [entry for entry in choices if entry["offered"]]
    waiting = [entry for entry in choices if not entry["offered"]]
    if not (
        buy
        and waiting
        and any(entry["optional"] for entry in offered)
        and any(not entry["optional"] for entry in offered)
    ):
        return None
    if any(str(entry["effect"]).startswith("command_") for entry in waiting):
        return "command"
    if any(entry["optional"] for entry in waiting):
        return "optional"
    return None


found: dict[str, dict] = {}
for seed in SEEDS:
    if len(found) == 2:
        break
    manager = GameSessionManager()
    summary = manager.create_game(SEATS, game_seed=seed, **OPTIONS)
    game_id = str(summary["game_id"])
    session = manager._get(game_id)
    rng = random.Random(seed)
    for _step in range(STEPS):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(game_id, held, summary["revision"])
            continue
        owner = summary["decision"]["owner"]
        actions = session.engine.legal_actions(session.state, owner)
        if session.state.decision_stack[-1].kind == FrameKind.REVEAL:
            # The page's own list (display.actions.reveal_choice_headers).
            choices = reveal_choice_headers(session.state, owner) or []
            buy = any(action.action_id.startswith("acquire") for action in actions)
            kind = kind_of(choices, buy)
            if kind is not None and kind not in found:
                document = manager.save_game(game_id, name=f"reveal-{kind}")
                found[kind] = {
                    "save_id": store.write(document)["save_id"],
                    "seed": seed,
                    "seat": owner,
                    "round": summary["round_number"],
                    "revision": summary["revision"],
                    "choices": [
                        {
                            key: entry[key]
                            for key in (
                                "key",
                                "name",
                                "name_ko",
                                "effect",
                                "optional",
                                "offered",
                            )
                        }
                        for entry in choices
                    ],
                }
                break
        index = rng.randrange(len(actions)) if actions else 0
        summary = manager.apply_action(game_id, owner, summary["revision"], index)

if len(found) < 2:
    raise RuntimeError(f"seeds 0-399 meet only {sorted(found)}")
print(json.dumps(found))
