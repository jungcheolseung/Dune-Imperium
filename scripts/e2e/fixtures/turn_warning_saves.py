"""Save real games where a row warns what it costs the seat (2026-10-31).

User request 2026-10-31, after a real game: Dissecting Kit's trash of its
grafted Show of Strength lost Show of Strength's unused draw (OQ-022), and
Arrakeen's draw then sealed the undo. Each save rests on the deciding human
seat's choice where one of the warnings shows:

- ``warn-forfeit``: a trash row whose engine step expires another card's
  unused Agent box (``agent_card_effect_expired``), the graft partner's
  when the walk meets one (Dissecting Kit, Beguiling Pheromones);
- ``warn-lapses``: an Agent turn's end whose press lapses an optional
  effect (``*_lapsed``, OQ-095 (2)), a board icon or a card's box among
  them;
- ``warn-persuasion``: a Reveal's end with Persuasion left and a card it
  can pay for with Persuasion still offered;
- ``warn-deploy``: an Agent turn's end with units it could still deploy,
  the most of each kind its deploy rows offer;
- ``warn-reveal-agents``: a Reveal turn offered beside an Agent turn, with
  the seat's Agents not sent yet;
- ``warn-deck-top-buys``: a Reveal's end like ``warn-persuasion`` where a
  card is offered twice, to the discard pile and onto the deck
  (``to_deck_top``: the original game's Recruitment Mission, Rise of Ix's
  Spaceport), so the line's count of cards differs from its rows' (2026-10-31
  re-review). The original game is walked for it once the Uprising walk has
  met every other case.

Four human seats, Immortality on (the graft; the original game without
it for ``warn-deck-top-buys``), Leader draft off; every seat
plays ``random.Random(seed).choice`` over its engine legal actions, an Agent
placement drawn as one choice (``placement_walk``), and every hold is
confirmed at once. Seeds are walked in order until each case is met.

The expectations are read off the engine here (the dry run's events, the
Reveal frame's Persuasion, the legal rows), not through the server's
``forfeits``, so the e2e checks the server's payload rather than repeating
it.

Prints {name: {save_id, seed, seat, ...}} as JSON.
"""

import json
import random
import sys
from pathlib import Path

from placement_walk import walk_step

from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

SEATS = ("human", "human", "human", "human")
SEEDS = range(0, 60)
STEPS = 6_000
GRAFT_TRASHES = ("trash_grafted_card_for_specimen", "trash_grafted_card_for_influence")
PERSUASION_BUYS = ("acquire_imperium", "acquire_reserve")
DEPLOYS = ("deploy_troops", "deploy_commanders", "deploy_dreadnoughts")
# The lapses the page names by their board icon or card (render.js
# lapseItem); the walk's first turn end lapses a Leader ability, which the
# page names by its log label only.
NAMED_LAPSES = ("board_effect_lapsed", "agent_card_effect_lapsed")
CASES = (
    "warn-forfeit",
    "warn-lapses",
    "warn-persuasion",
    "warn-deploy",
    "warn-reveal-agents",
    "warn-deck-top-buys",
)
# The case only the original game's walk meets.
ORIGINAL_ONLY = ("warn-deck-top-buys",)

store = SaveStore(Path(sys.argv[1]))
found: dict[str, dict[str, object]] = {}
# A forfeit that is not a graft partner's, kept in case no seed meets one.
fallback: dict[str, object] | None = None


def card_of(action) -> object:
    """The card an acquisition row buys, whichever pile it goes to."""

    arguments = dict(action.arguments)
    return arguments.get("instance_id") or arguments.get("card_id")


def ids(actions) -> set[str]:
    return {action.action_id for action in actions}


def expired_cards(engine, state, owner, action) -> list[str]:
    """The cards of ``owner`` whose Agent box the row's own step expires."""

    return [
        str(dict(event.payload)["card_id"])
        for event in apply_whole(engine, state, action).events
        if event.kind == "agent_card_effect_expired"
        and dict(event.payload).get("player") == owner
    ]


def lapsed(engine, state, owner, action) -> list[dict[str, object]]:
    return [
        {"kind": event.kind, "payload": dict(event.payload)}
        for event in apply_whole(engine, state, action).events
        if event.kind.endswith("_lapsed")
        and event.visible_to is None
        and dict(event.payload).get("player") == owner
    ]


def reveal_persuasion(state, owner) -> int:
    for frame in reversed(state.decision_stack):
        if frame.kind == FrameKind.REVEAL:
            value = dict(frame.context).get("persuasion")
            return value if isinstance(value, int) else 0
    return 0


def forfeit_case(engine, state, owner, actions) -> dict[str, object] | None:
    """A trash row expiring another of the turn's boxes; the graft partner's
    first."""

    global fallback
    for action in actions:
        if "trash" not in action.action_id:
            continue
        cards = expired_cards(engine, state, owner, action)
        if not cards:
            continue
        case = {
            "action_id": action.action_id,
            "arguments": dict(action.arguments),
            "lost": cards,
            "graft": action.action_id in GRAFT_TRASHES,
        }
        if case["graft"]:
            return case
        if fallback is None:
            fallback = case
    return None


def check(manager, gid, session, summary, owner, actions, seed) -> None:
    """Save the position under every case it meets that is still open."""

    engine, state = session.engine, session.state
    names = ids(actions)
    met: dict[str, dict[str, object]] = {}
    if "warn-forfeit" not in found and any("trash" in name for name in names):
        case = forfeit_case(engine, state, owner, actions)
        if case is not None:
            met["warn-forfeit"] = case
    end = next((a for a in actions if a.action_id == "finish_agent_turn"), None)
    if end is not None and "warn-lapses" not in found:
        lapses = lapsed(engine, state, owner, end)
        if {lapse["kind"] for lapse in lapses} & set(NAMED_LAPSES):
            met["warn-lapses"] = {"lapses": lapses}
    if end is not None and "warn-deploy" not in found and names & set(DEPLOYS):
        units = {
            deploy: max(
                int(dict(action.arguments)["count"])
                for action in actions
                if action.action_id == deploy
            )
            for deploy in DEPLOYS
            if deploy in names
        }
        met["warn-deploy"] = {"units": units}
    if "finish_reveal" in names and "warn-persuasion" not in found:
        left = reveal_persuasion(state, owner)
        # Distinct cards: Recruitment Mission and Spaceport offer each one
        # to the discard pile and onto the deck (``to_deck_top``).
        buys = len({card_of(a) for a in actions if a.action_id in PERSUASION_BUYS})
        if left > 0 and buys > 0:
            met["warn-persuasion"] = {"persuasion": left, "buys": buys}
    if "finish_reveal" in names and "warn-deck-top-buys" not in found:
        left = reveal_persuasion(state, owner)
        rows = [a for a in actions if a.action_id in PERSUASION_BUYS]
        cards = {card_of(a) for a in rows}
        if left > 0 and len(rows) > len(cards):
            met["warn-deck-top-buys"] = {
                "persuasion": left,
                "buys": len(cards),
                "rows": len(rows),
            }
    agents = state.players[owner].agents_available
    if (
        "warn-reveal-agents" not in found
        and "reveal_turn" in names
        and "choose_agent_card" in names
        and agents > 0
    ):
        met["warn-reveal-agents"] = {"agents": agents}
    for name, case in met.items():
        saved = store.write(manager.save_game(gid, name=name))
        found[name] = {"save_id": saved["save_id"], "seed": seed, "seat": owner, **case}


def walk(seed: int, original: bool) -> None:
    manager = GameSessionManager()
    summary = manager.create_game(
        SEATS,
        game_seed=seed,
        leader_draft=False,
        **({"base_game": "imperium"} if original else {"immortality": True}),
    )
    gid = str(summary["game_id"])
    session = manager._get(gid)
    rng = random.Random(seed)
    for _step in range(STEPS):
        if summary["finished"] or len(found) == len(CASES):
            return
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(gid, held, summary["revision"])
            continue
        owner = summary["decision"]["owner"]
        actions = session.engine.whole_actions(session.state, owner)
        check(manager, gid, session, summary, owner, actions, seed)
        summary, _ = walk_step(manager, gid, owner, summary, rng.choice)


for original in (False, True):
    for seed in SEEDS:
        walk(seed, original)
        wanted = [name for name in CASES if original or name not in ORIGINAL_ONLY]
        if all(name in found for name in wanted):
            break
if "warn-forfeit" not in found and fallback is not None:
    raise RuntimeError(f"no graft forfeit in seeds {SEEDS}; first other: {fallback}")
missing = [name for name in CASES if name not in found]
if missing:
    raise RuntimeError(f"no position for {missing} in seeds {SEEDS}")
print(json.dumps(found))
