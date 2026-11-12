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
  lapses unused when the Reveal ends (seed 1571 today: Public Spectacle's
  Spy icon and Engineered Miracle offered, Unswerving Loyalty
  without its Fremen Bond waiting);
- "command": the waiting choice is a Command (6+) one, so its reason is
  the Persuasion the Reveal has generated (seed 133 today: Delivery
  Logistics' Persuasion-or-Contract choice and Shadout Mapes' optional
  one offered, Intelligence Training waiting for Command; Delivery Logistics'
  Persuasion then opens it).

Prints {"optional": {...}, "command": {...}} as JSON, each {save_id, seed,
seat, round, revision, choices}: ``choices`` are the page's
``reveal_choices`` entries ({key, name, name_ko, effect, optional,
offered}).
"""

import json
import random
import sys
from pathlib import Path

from placement_walk import keep_specimen_holders_asked, walk_step

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
# Seed 167 until codec v154 moved the AI-free walks (a cost-free Intrigue line
# is played even when it fizzles, OQ-113 (C); the Planetary Array card is a
# row of the Conflict winner's reward window, OQ-121; Suspensor Suits' missing
# troop is made up later, OQ-042): the "command" Reveal is rare (a scan of
# 0-7805 meets one in about 700 seeds: 766, 3241, 4106, 4477, 5853, 5941,
# 6198, 6270, 6355, 6522 and 6983), and reveal_choices.py's step [3] needs a
# mandatory choice that generates the Persuasion to open the waiting Command
# choice (Desert Power's or Delivery Logistics') and an optional choice still
# on offer at the end; of those only seed 6270 has it (seed 766 and the
# others wait on a Command choice no mandatory answer opens). The "optional"
# Reveal stays at seed 306 (seeds 22, 199, 458, 500, 639, 662, 667 and 941
# also meet one in 0-999, and 306, 458, 639 and 941 have Public Spectacle
# among them). A fallback scan of 0-399 therefore finds no "command" Reveal.
# The Agent box lock (OQ-167, 2026-11-07) changes the legal lists of an Agent
# turn, so every walk takes other paths from the first Agent turn with a box
# part way (seed 306 at its walk step 103, seed 6270 at step 63: the box's own
# rows only, where the visited space's icons were offered too); the Reveal
# turn's own rows are unchanged. A scan of 0-1570 finds the "command" Reveal
# at seeds 118 (Wheels Within Wheels, whose Spy opens no Command choice) and
# 133 (Delivery Logistics' Persuasion opens Intelligence Training, Shadout
# Mapes' optional choice beside it: the old shape), and the "optional" one
# with Public Spectacle's Spy first at seed 1571 (Unswerving Loyalty's Fremen
# Bond choice waiting). So seeds 1571 and 133 then.
# The printed-effects audit (user rulings 2026-11-09: Forbidden Weapons',
# Disposal Facility's and Planetary Array's optional icons, Lady Jessica's,
# Princess Yuna's, Feyd-Rautha's, Throne Room Politics' and Control the
# Spice's steps) moves both games again: neither seed reaches its Reveal. A
# scan of seeds 0-12000 (2026-11-09) finds the "optional" Reveal at seeds 8,
# 297, 462, 535, 549, 605, 1037, 1295, 1478 and more, of which only 549 and
# 1478 have Public Spectacle (reveal_choices.py reads its logged Spy step;
# seed 8 lacks it), and the "command" one at seeds 899, 4113 and 10047 (and
# others without the shape): 899 (Delivery Logistics' first row leaves the
# Persuasion short of Command 6+) and 4113 (Delivery Agreement, no Persuasion
# at all) never open the waiting Command choice in reveal_choices.py's step
# [3]; seed 10047 (Delivery Logistics beside Engineered Miracle waiting, and
# Unswerving Loyalty) does. So seeds 549 and 10047 now.
# The play server passes Combat Intrigue for a seat with no Intrigue card
# even when it holds specimens since 2026-11-09 (their return waits for the
# seat's Conflict reward window, OQ-050): the walk drew over the pass and a
# return there before, and sometimes returned one, so the server's pass
# moved both games. The walk keeps answering those opportunities itself
# (``keep_specimen_holders_asked``) and the seeds keep their games; the
# rest of the server is as it plays.
# The two merged (2026-11-09): the same scan of seeds 0-10100 on the merged
# engine finds the "optional" Reveal with Public Spectacle first at seed 549
# again, and the "command" one at seeds 899, 8965, 9670 and 10047 (4113 no
# longer has it); reveal_choices.py's step [3] opens the waiting Command
# choice at 9670 and 10047 but not at 899 or 8965. So seeds 549 and 9670.
KNOWN = (549, 9670)
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
    keep_specimen_holders_asked(manager)
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
        actions = session.engine.whole_actions(session.state, owner)
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
        # An Agent placement is drawn as one choice, as before stage B1
        # (``placement_walk``), so the seeds keep their games.
        # ``choice`` draws as ``randrange`` over the list did.
        summary, _ = walk_step(manager, game_id, owner, summary, rng.choice)

if len(found) < 2:
    raise RuntimeError(f"seeds 0-399 meet only {sorted(found)}")
print(json.dumps(found))
