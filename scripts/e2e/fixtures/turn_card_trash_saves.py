"""Save two real games at a trash choice naming this Agent turn's card.

User feedback 2026-10-11: with two copies of one card in play, the page did
not say which one the open Agent turn played, and Arrakis Planetologist's
optional trash took this turn's grafted Experimentation, whose Agent box
was then lost (OQ-022). Both saves rest on such a choice: a
``trash_optional_card`` decision (the same optional trash, here a Research
track space's trash bonus [Immortality]) offering a card the open Agent turn
played and an earlier copy of the same card, also in play.

Four human seats, Immortality on, Leader draft off; every seat plays
``random.Random(seed).randrange`` over its engine legal actions and every
hold is confirmed at once (the walk of held_choice_saves.py, all seats):

- ``turn-card-pending`` (seed 596, round 10, seat 0): the Research Station
  board space's Research offers the trash while this turn's Prepare the Way
  still has its Agent box to resolve;
- ``turn-card-done`` (seed 6, round 3, seat 3): this turn's Experimentation
  resolved its Agent box (Research), whose track space offers the trash.

Codec v147 changed every seat's legal list in a Reveal (a Reveal choice is a
row of the Reveal), so seed 111 (codec v146) lost the pending shape; seeds
1-340 walked in order met it first at seed 243. Codec v149 moved seed 243's
game again; seeds 1-900 walked in order (2026-10-19) meet the pending shape
at seeds 144, 538, 596, 603, 782 and 805, and seed 6 still meets the done one
first. Seed 144 (the same Research Station trash, this turn's Prepare the
Way) also offers its grafted Planned Coupling, whose box that trash expires
as well, so the server flags two rows where this script lists only the
pair; seed 538 has Prepare the Way as the grafted partner of a Bene Tleilax
Researcher, not the played card; seed 596 is the first with the shape above
and only the pair flagged (603 is the next, Research Station, round 8).

The expected lists are read off the Agent turn's effect frame here, not
through the server's ``turn_cards``, and the rows that lose a box
(``box_losing_trash``) are the ones whose own engine step expires the box
(``agent_card_effect_expired``), so the script checks the server's payload
rather than repeating it.

Prints {name: {save_id, seat, action_id, this_turn, earlier, pending,
turn_card_ids, pending_box_card_ids, box_losing_trash}} as JSON.
"""

import json
import random
import re
import sys
from pathlib import Path

from dune_imperium.core.actions import DomainAction
from dune_imperium.rules.frames import FrameKind
from dune_imperium.server.persistence import SaveStore
from dune_imperium.server.sessions import GameSessionManager

SEATS = ("human", "human", "human", "human")
TRASH = "trash_optional_card"
STEPS = 6_000
CASES = (("turn-card-pending", 596, True), ("turn-card-done", 6, False))

STARTER_ID = re.compile(r"^player:\d+:starter:(.+):\d+$")
SHARED_ID = re.compile(r"^(?:imperium|reserve|intrigue|tleilaxu|skill):(.+):\d+$")

store = SaveStore(Path(sys.argv[1]))
found: dict[str, dict[str, object]] = {}


def base_id(card_id: str) -> str:
    for pattern in (STARTER_ID, SHARED_ID):
        match = pattern.match(card_id)
        if match:
            return match.group(1)
    return card_id


def frame_lists(state) -> tuple[list[str], list[str]]:
    """The open Agent turn's played cards still in play, and the ones whose
    Agent box still waits, straight from the effect frame's context."""

    played: list[str] = []
    pending: list[str] = []
    for frame in state.decision_stack:
        if frame.kind != FrameKind.AGENT_EFFECTS:
            continue
        context = dict(frame.context)
        in_play = state.players[context["turn_owner"]].in_play
        for key, flag in (
            ("card_id", "pending_agent_effect"),
            ("graft_card_id", "graft_pending_effect"),
        ):
            card = context.get(key)
            if not card or card not in in_play:
                continue
            played.append(card)
            boosted = str(context.get("boost_draw_card_ids", "")).split(",")
            if context.get(flag) is True or card in boosted:
                pending.append(card)
        order = list(in_play)
        played.sort(key=order.index)
        pending.sort(key=order.index)
    return played, pending


def expires_box(engine, state, owner, card_id) -> bool:
    """Whether trashing ``card_id`` with the fixture's action expires an
    Agent box of that card in the engine's own step."""

    action = DomainAction(
        action_id=TRASH, actor=owner, arguments=(("card_id", card_id),)
    )
    return any(
        event.kind == "agent_card_effect_expired"
        and dict(event.payload).get("card_id") == card_id
        for event in engine.apply(state, action).events
    )


def twin_rows(state, owner, actions) -> tuple[str, str] | None:
    """(this turn's card, the earlier copy) offered by one trash choice."""

    played, _ = frame_lists(state)
    in_play = state.players[owner].in_play
    offered = [
        dict(action.arguments)["card_id"]
        for action in actions
        if action.action_id == TRASH
    ]
    for card in offered:
        if card not in played:
            continue
        for other in offered:
            if (
                other != card
                and other in in_play
                and other not in played
                and base_id(other) == base_id(card)
            ):
                return card, other
    return None


for name, seed, want_pending in CASES:
    manager = GameSessionManager()
    summary = manager.create_game(
        SEATS, game_seed=seed, immortality=True, leader_draft=False
    )
    gid = str(summary["game_id"])
    session = manager._get(gid)
    rng = random.Random(seed)
    for _step in range(STEPS):
        if summary["finished"]:
            break
        held = summary["confirmation"]
        if isinstance(held, int):
            summary = manager.confirm_turn(gid, held, summary["revision"])
            continue
        owner = summary["decision"]["owner"]
        actions = session.engine.legal_actions(session.state, owner)
        pair = twin_rows(session.state, owner, actions)
        if pair is not None:
            played, pending = frame_lists(session.state)
            if (pair[0] in pending) == want_pending:
                saved = store.write(manager.save_game(gid, name=name))
                found[name] = {
                    "save_id": saved["save_id"],
                    "seat": owner,
                    "action_id": TRASH,
                    "this_turn": pair[0],
                    "earlier": pair[1],
                    "pending": want_pending,
                    "turn_card_ids": played,
                    "pending_box_card_ids": pending,
                    "box_losing_trash": [
                        {"action_id": TRASH, "card_id": card}
                        for card in pair
                        if expires_box(session.engine, session.state, owner, card)
                    ],
                }
                break
        summary = manager.apply_action(
            gid, owner, summary["revision"], rng.randrange(len(actions))
        )

missing = {name for name, _, _ in CASES} - set(found)
if missing:
    raise RuntimeError(f"Could not find every fixture: {sorted(missing)} ({found})")
print(json.dumps(found))
