"""E2E of Rise of Ix's hidden values through the real remote server path.

The engine's own views (``core.observation``: ``PrivatePlayerView``'s
``ix_pending``, ``known_intrigue_top`` / ``_bottom`` / ``_held``) are covered
by unit tests, and ``imperium_game.py`` [7] draws the markers from a view it
edits by hand. This script asks the question the table cares about: what does
each seat's browser get from the server, and what does its page show? A
``--remote`` server, four contexts that each claim one seat through the lobby
(so each holds only its own HttpOnly seat cookie), and a fifth that claims
none (the spectator). Every fetch below runs in the page of the context that
asks, with that context's own cookie; the host's admin key opens no seat
(``_authorize_seat_locked``), and the host is seat 0's own context.

For each hidden value, at the moment it is real:

- the owner's view (``GET /games/{id}/seats/{seat}/view``) carries it, and the
  owner's page draws it: on its own seat panel (``panels.ix_pending_shipping``,
  ``panels.ix_pending_tech``), or in the Intrigue deck area
  (``.known-intrigue``);
- each other seat's own view carries the empty value (its private block is its
  own), no payload it can fetch (view, snapshot with the action log) names the
  secret card, its page shows none of the lines, and asking for the owner's
  view, actions or snapshot is refused (403);
- the spectator (no seat) is refused the same, its summary has no such field,
  its page shows none of the lines and holds no view at all.

Hidden values covered (Rise of Ix on the original game, four human seats):

1. ``ix_pending.shipping_rewards``: seat 1 recalls its Freighter from Shipping
   step 1 (Smuggling), the step-1 reward is owed.
2. ``ix_pending.tech_discount`` / ``tech_payment`` / ``negotiators_returnable``:
   seat 0 sends an Agent to Tech Negotiation holding a Negotiator, and its
   Acquire Tech (Tech Discount 1, spice, one Negotiator returnable) is open.
3. ``known_intrigue_bottom``: seat 0 buys Sonic Snoopers, and puts an Intrigue
   card at the Intrigue deck's bottom, which only it then knows. (Checked again
   at the end, when it is still known and still hidden.)

Not reachable, and named here so the gap stays visible:

- ``known_intrigue_top`` and ``known_intrigue_held`` (Immortality's Imperium
  Ceremony, OQ-149): POST /games refuses ``base_game: "imperium"`` with
  ``immortality`` ("the original game takes immortality from stage P7"; the
  step below checks that it still does), and Rise of Ix has no content with
  Uprising yet (stage P7), so no table combines the original game, Rise of Ix
  and Immortality. When the combination is accepted this script fails and says
  to add that scenario. Hundro Moritani's Intelligence (``known_intrigue_top``
  too) and Ilesa Ecaz's set-aside card (``set_aside_card_id``) are not in the
  engine yet either.

The plan is pinned, not searched: ``SEED``, the game options and ``PLAN``, the
exact whole actions to take (seat, action id, arguments) in order. A plan step
that is not on offer, or a checkpoint whose pinned values differ, FAILS the run
and names the step or state missed; nothing is skipped. Turn-end presses are
not choices: the script presses whichever seat the server says holds one.

How the constants were found: scratch finders in
``tmp/claude/5823a41d/ix-screens/`` (git-ignored; kept there, not in the
repository). ``find.py`` plays original + Rise of Ix games of four human seats
in-process through ``GameSessionManager`` (the layer the server itself uses, so
the answers are the same whole actions) with random answers weighted toward
Smuggling, Tech Negotiation, Dreadnought and Interstellar Shipping and away
from troop shuffling, and reads each state for the three targets above;
``search.py`` runs it over seeds 1-239 with three answer streams each (at most
220 actions) and keeps a game as soon as a Shipping reward is owed, an Acquire
Tech is open with a returnable Negotiator and a bottom-known Intrigue card
exists. Seven of the 717 playouts got there; the shortest, seed 41 with answer
stream 41 * 1000 + 2, is ``PLAN`` (88 actions). ``emit_plan.py`` wrote it
out and ``replay.py`` replays it and prints every seat's private block at the
three checkpoints, which are pinned below.
"""

from __future__ import annotations

import json
import shutil
from typing import Any

from common import SERVER_LOG_COPY, Check, chrome, open_context, server
from open_mode import settled
from remote import converge, holds_seats, wait_for_setup

check = Check()

KEY = "e2e-ix-admin-key"
VIEWPORT = {"width": 1600, "height": 1000}
SEED = 41
# Four human seats, the original game with Rise of Ix, as the setup screen's
# boxes would send them (everything else off).
GAME = {
    "seats": ["human", "human", "human", "human"],
    "base_game": "imperium",
    "rise_of_ix": True,
    "game_seed": SEED,
}

# (seat, action id, arguments), in order; the number after each is its index
# (CHECKPOINTS counts the actions applied).
PLAN: list[tuple[int, str, dict[str, Any]]] = [
    # Setup: seat 3's Masterstroke, two Factions picked in secret.
    (3, "choose_masterstroke_faction", {"faction": "fremen"}),  # 0
    (3, "choose_masterstroke_faction", {"faction": "spacing_guild"}),  # 1
    # Round 1, first Agent turns. Seat 0: Tech Negotiation, a Negotiator on the
    # Ix board.
    (0, "choose_agent_card", {"card_id": "player:0:starter:dagger:0"}),  # 2
    (0, "place_agent", {"space_id": "tech_negotiation"}),  # 3
    (0, "place_board_negotiator", {}),  # 4
    (0, "finish_agent_turn", {}),  # 5
    # Seat 1: Hardy Warriors.
    (1, "choose_agent_card", {"card_id": "player:1:starter:seek_allies:0"}),  # 6
    (1, "place_agent", {"space_id": "hardy_warriors"}),  # 7
    (1, "resolve_board_effect", {"effect": "troops"}),  # 8
    (1, "deploy_troops", {"count": 3}),  # 9
    (1, "resolve_faction_influence", {}),  # 10
    (1, "resolve_agent_card_effect", {}),  # 11
    (1, "finish_agent_turn", {}),  # 12
    # Seat 2: Foldspace.
    (2, "choose_agent_card", {"card_id": "player:2:starter:diplomacy:0"}),  # 13
    (2, "place_agent", {"space_id": "foldspace"}),  # 14
    (2, "resolve_faction_influence", {}),  # 15
    (2, "resolve_board_effect", {"effect": "foldspace"}),  # 16
    (2, "finish_agent_turn", {}),  # 17
    # Seat 3: Smuggling, its Freighter moves up to Shipping step 1.
    (
        3,
        "choose_agent_card",
        {"card_id": "player:3:starter:dune_the_desert_planet:1"},
    ),  # 18
    (3, "place_agent", {"space_id": "smuggling"}),  # 19
    (3, "advance_board_freighter", {}),  # 20
    (3, "resolve_board_effect", {"effect": "resources"}),  # 21
    (3, "finish_agent_turn", {}),  # 22
    # Round 1, second Agent turns, seats 0 to 3.
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:1"},
    ),  # 23
    (0, "place_agent", {"space_id": "imperium_hagga_basin"}),  # 24
    (0, "deploy_troops", {"count": 2}),  # 25
    (0, "harvest_maker_spice", {"space_id": "imperium_hagga_basin"}),  # 26
    (0, "finish_agent_turn", {}),  # 27
    (
        1,
        "choose_agent_card",
        {"card_id": "player:1:starter:dune_the_desert_planet:0"},
    ),  # 28
    (1, "place_agent", {"space_id": "imperial_basin"}),  # 29
    (1, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 30
    (1, "deploy_troops", {"count": 1}),  # 31
    (1, "finish_agent_turn", {}),  # 32
    (2, "choose_agent_card", {"card_id": "player:2:starter:seek_allies:0"}),  # 33
    (2, "place_agent", {"space_id": "wealth"}),  # 34
    (2, "resolve_faction_influence", {}),  # 35
    (2, "resolve_agent_card_effect", {}),  # 36
    (2, "resolve_board_effect", {"effect": "resources"}),  # 37
    (2, "finish_agent_turn", {}),  # 38
    (3, "choose_agent_card", {"card_id": "player:3:starter:reconnaissance:0"}),  # 39
    (3, "place_agent", {"space_id": "carthag"}),  # 40
    (3, "resolve_board_effect", {"effect": "intrigue"}),  # 41
    (3, "resolve_board_effect", {"effect": "troops"}),  # 42
    (3, "deploy_troops", {"count": 3}),  # 43
    (3, "finish_agent_turn", {}),  # 44
    # Reveal turns, then Combat: seat 1 wins, and a Freighter reward moves its
    # Freighter.
    (0, "reveal_turn", {}),  # 45
    (0, "finish_reveal", {}),  # 46
    (1, "reveal_turn", {}),  # 47
    (1, "finish_reveal", {}),  # 48
    (2, "reveal_turn", {}),  # 49
    (
        2,
        "acquire_imperium",
        {"instance_id": "imperium:fedaykin_death_commando:0"},
    ),  # 50
    (2, "finish_reveal", {}),  # 51
    (3, "reveal_turn", {}),  # 52
    (3, "acquire_imperium", {"instance_id": "imperium:space_travel:0"}),  # 53
    (3, "finish_reveal", {}),  # 54
    (0, "pass_combat_intrigue", {}),  # 55
    (1, "pass_combat_intrigue", {}),  # 56
    (3, "pass_combat_intrigue", {}),  # 57
    (1, "resolve_combat_reward_icon", {"effect": "freighter"}),  # 58
    (1, "advance_freighter", {}),  # 59
    (1, "resolve_combat_reward_icon", {"effect": "resources"}),  # 60
    (1, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 61
    (3, "resolve_combat_reward_icon", {"effect": "resources"}),  # 62
    (0, "resolve_combat_reward_icon", {"effect": "resources"}),  # 63
    # Round 2: seats 1 and 2 send an Agent (Stillsuits, Dreadnought), seat 3 reveals.
    (1, "choose_agent_card", {"card_id": "player:1:starter:diplomacy:0"}),  # 64
    (1, "place_agent", {"space_id": "stillsuits"}),  # 65
    (1, "resolve_board_effect", {"effect": "resources"}),  # 66
    (1, "resolve_faction_influence", {}),  # 67
    (1, "finish_agent_turn", {}),  # 68
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:1"}),  # 69
    (2, "place_agent", {"space_id": "dreadnought"}),  # 70
    (2, "finish_agent_turn", {}),  # 71
    (3, "reveal_turn", {}),  # 72
    (3, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 73
    (3, "acquire_imperium", {"instance_id": "imperium:sardaukar_infantry:1"}),  # 74
    (3, "finish_reveal", {}),  # 75
    # Seat 0, Tech Negotiation again: Acquire Tech returning its Negotiator (action 79:
    (0, "choose_agent_card", {"card_id": "player:0:starter:dagger:1"}),  # 76
    (0, "place_agent", {"space_id": "tech_negotiation"}),  # 77
    (0, "acquire_negotiation_tech", {}),  # 78
    (0, "acquire_tech", {"negotiators": 1, "tech_id": "sonic_snoopers"}),  # 79
    # the Acquire Tech is open), then Sonic Snoopers' Acquire effect and its trash: an
    (
        0,
        "resolve_tech_acquire_effect",
        {"effect": "intrigue", "tech_id": "sonic_snoopers"},
    ),  # 80
    (0, "trash_tech", {"tech_id": "sonic_snoopers"}),  # 81
    # Intrigue card goes to the Intrigue deck's bottom (action 83: seat 0 knows it).
    (0, "put_intrigue_on_bottom", {"card_id": "intrigue:master_tactician:1"}),  # 82
    (0, "finish_intrigue_bottom", {}),  # 83
    (0, "finish_agent_turn", {}),  # 84
    # Seat 1, Smuggling: its Freighter, at step 1, is recalled (action 88).
    (
        1,
        "choose_agent_card",
        {"card_id": "player:1:starter:dune_the_desert_planet:1"},
    ),  # 85
    (1, "place_agent", {"space_id": "smuggling"}),  # 86
    (1, "recall_board_freighter", {}),  # 87
]

SECRET_CARD = "intrigue:master_tactician:1"
EMPTY_PENDING = {
    "shipping_rewards": [],
    "tech_discount": 0,
    "tech_payment": "",
    "negotiators_returnable": 0,
}
TECH_PENDING = {
    "shipping_rewards": [],
    "tech_discount": 1,
    "tech_payment": "spice",
    "negotiators_returnable": 1,
}
SHIPPING_PENDING = {**EMPTY_PENDING, "shipping_rewards": [1]}
KNOWN_BOTTOM = [[0, SECRET_CARD]]

# After this many actions: (what is true, {seat: the private fields that seat
# holds, every other field and seat being empty}).
CHECKPOINTS: dict[int, tuple[str, dict[int, dict[str, Any]]]] = {
    79: (
        "Acquire Tech open for seat 0 (Tech Negotiation, Tech Discount 1, spice,"
        " one Negotiator returnable)",
        {0: {"ix_pending": TECH_PENDING}},
    ),
    83: (
        "seat 0 put an Intrigue card at the deck's bottom (Sonic Snoopers)",
        {0: {"known_intrigue_bottom": KNOWN_BOTTOM}},
    ),
    88: (
        "seat 1 recalled its Freighter from step 1: the step-1 reward is owed"
        " (seat 0 still knows its bottom card)",
        {
            0: {"known_intrigue_bottom": KNOWN_BOTTOM},
            1: {"ix_pending": SHIPPING_PENDING},
        },
    ),
}
EMPTY_PRIVATE = {
    "ix_pending": EMPTY_PENDING,
    "known_intrigue_top": "",
    "known_intrigue_bottom": [],
    "known_intrigue_held": [],
}
SECRET_KEYS = (
    "ix_pending",
    "shipping_rewards",
    "tech_payment",
    "negotiators_returnable",
)

FETCH_JS = """async ([method, path, body]) => {
  const response = await fetch(path, {
    method,
    headers: {"Content-Type": "application/json"},
    body: body === null ? undefined : JSON.stringify(body),
  });
  let data = null;
  try { data = await response.json(); } catch (error) { data = null; }
  return {status: response.status, data};
}"""

# What a page shows: its own seat panels and Intrigue deck lines, whose view it
# holds, and the revision of that view.
PAGE_JS = """() => {
  const norm = (s) => s.replace(/\\s+/g, " ").trim();
  const view = state.view;
  return {
    mine: state.me ? state.me.seats : null,
    viewer: view ? view.player : null,
    viewRevision: view ? view.revision : null,
    summaryRevision: state.summary ? state.summary.revision : null,
    held: view && view.private ? view.private.known_intrigue_held : null,
    pending: view && view.private ? view.private.ix_pending : null,
    bottom: view && view.private ? view.private.known_intrigue_bottom : null,
    panels: Object.fromEntries([...document.querySelectorAll("#seats .seat")]
      .map((card) => [card.dataset.seat, norm(card.textContent)])),
    known: [...document.querySelectorAll(".known-intrigue")]
      .map((el) => [el.dataset.known, norm(el.textContent)]),
    body: norm(document.body.innerText),
  };
}"""

# The page's own words for each line, in the language it speaks now, so that
# the script reads the lines out of ui_text.js and not out of its own copy.
WORDS_JS = """(args) => {
  const mark = "\\u0001";
  const head = (key, vars) => t(key, vars).split(mark)[0];
  return {
    shipping: t("panels.ix_pending_shipping", {steps: args.steps}),
    shippingHead: head("panels.ix_pending_shipping", {steps: mark}),
    tech: t("panels.ix_pending_tech", {
      discount: args.discount,
      payment: phraseText(args.payment === "solari" ? "{solari}" : "{spice}"),
      negotiators: args.negotiators,
    }),
    techHead: head("panels.ix_pending_tech", {
      discount: mark, payment: mark, negotiators: mark,
    }),
    heldHead: head("panels.known_intrigue_held", {cards: mark}),
    bottom: t("board.known_intrigue_bottom", {
      cards: t("board.known_intrigue_at_bottom", {card: nameOf(args.card)}),
    }),
    bottomHead: head("board.known_intrigue_bottom", {cards: mark}),
    topHead: head("board.known_intrigue_top", {card: mark}),
  };
}"""


class PlanMissed(Exception):
    """A pinned step or state is not what the server has."""


def api(page, method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
    """One request from ``page``: its own cookies, nobody else's."""
    result = page.evaluate(FETCH_JS, [method, path, body])
    return result["status"], result["data"]


def step_label(index: int) -> str:
    seat, action_id, arguments = PLAN[index]
    return f"step {index + 1}/{len(PLAN)} (seat {seat} {action_id} {arguments})"


def take_plan_step(pages: dict[int, Any], game_id: str, index: int) -> None:
    """Take PLAN[index] as its seat, from that seat's own page."""
    seat, action_id, arguments = PLAN[index]
    while True:
        _, summary = api(pages[0], "GET", f"/games/{game_id}")
        held = summary["confirmation"]
        if not isinstance(held, int):
            break
        status, _ = api(
            pages[held],
            "POST",
            f"/games/{game_id}/confirm",
            {
                "seat": held,
                "revision": summary["revision"],
                "undo_count": summary["undo_count"],
            },
        )
        if status != 200:
            raise PlanMissed(
                f"{step_label(index)}: seat {held}'s turn end: HTTP {status}"
            )
    decision = summary["decision"]
    if summary["finished"] or decision is None or decision["owner"] != seat:
        raise PlanMissed(
            f"{step_label(index)}: the server's decision is {decision},"
            f" not seat {seat}'s"
        )
    status, listed = api(pages[seat], "GET", f"/games/{game_id}/seats/{seat}/actions")
    if status != 200:
        raise PlanMissed(f"{step_label(index)}: seat {seat}'s actions: HTTP {status}")
    rows = [
        row
        for row in listed["actions"]
        if row["action_id"] == action_id and (row["arguments"] or {}) == arguments
    ]
    if len(rows) != 1:
        offered = [(row["action_id"], row["arguments"]) for row in listed["actions"]]
        raise PlanMissed(
            f"{step_label(index)}: not on offer exactly once; offered {offered[:12]}"
        )
    status, _ = api(
        pages[seat],
        "POST",
        f"/games/{game_id}/actions",
        {
            "seat": seat,
            "revision": summary["revision"],
            "undo_count": summary["undo_count"],
            "index": rows[0]["index"],
        },
    )
    if status != 200:
        raise PlanMissed(f"{step_label(index)}: HTTP {status}")


def secret_cards(private: dict[int, dict[str, Any]]) -> list[str]:
    return [
        card
        for held in private.values()
        for _depth, card in held.get("known_intrigue_bottom", [])
    ]


def check_views(
    label: str,
    pages: dict[int, Any],
    spectator,
    game_id: str,
    private: dict[int, dict[str, Any]],
    revision: int,
) -> None:
    """The HTTP side: each seat's own view and snapshot, the spectator's
    summary, and the refusals."""
    secrets = secret_cards(private)
    for seat, page in pages.items():
        status, view = api(page, "GET", f"/games/{game_id}/seats/{seat}/view")
        status_s, snapshot = api(page, "GET", f"/games/{game_id}/snapshot?seat={seat}")
        ok = status == 200 and status_s == 200
        check.ok(
            ok,
            f"{label}: seat {seat} reads its own view and snapshot",
            (status, status_s),
        )
        if not ok:
            continue
        expected = {**EMPTY_PRIVATE, **private.get(seat, {})}
        found = {key: view["private"][key] for key in EMPTY_PRIVATE}
        check.ok(
            found == expected and view["player"] == seat,
            f"{label}: seat {seat}'s own view carries"
            + (" its hidden value" if seat in private else " no hidden value"),
            {"found": found, "expected": expected},
        )
        check.ok(
            view["revision"] == revision == snapshot["summary"]["revision"],
            f"{label}: seat {seat}'s view is of the checkpoint's revision",
            (view["revision"], revision, snapshot["summary"]["revision"]),
        )
        text = json.dumps([view, snapshot])
        owned = set(secret_cards({seat: private.get(seat, {})}))
        for card in secrets:
            check.ok(
                (card in text) == (card in owned),
                f"{label}: seat {seat}'s view and snapshot (with the action log)"
                + (" name" if card in owned else " do not name")
                + f" {card}",
            )
    status, summary = api(spectator, "GET", f"/games/{game_id}")
    text = json.dumps(summary)
    check.ok(
        status == 200
        and summary["revision"] == revision
        and not any(key in text for key in SECRET_KEYS)
        and not any(card in text for card in secrets),
        f"{label}: the spectator's summary carries no hidden field or card",
        (status, [key for key in SECRET_KEYS if key in text]),
    )
    readers = {
        **{f"seat {seat}": page for seat, page in pages.items()},
        "spectator": spectator,
    }
    refused: list[str] = []
    for owner in private:
        for name, page in readers.items():
            if name == f"seat {owner}":
                continue
            for path in (
                f"/games/{game_id}/seats/{owner}/view",
                f"/games/{game_id}/seats/{owner}/actions",
                f"/games/{game_id}/snapshot?seat={owner}",
            ):
                status, _ = api(page, "GET", path)
                if status != 403:
                    refused.append(f"{name} {path}: HTTP {status}")
    check.ok(
        not refused,
        f"{label}: every other seat and the spectator is refused (403) the owner's"
        " view, actions and snapshot",
        refused[:4],
    )


def check_pages(
    label: str,
    pages: dict[int, Any],
    spectator,
    private: dict[int, dict[str, Any]],
    revision: int,
    language: str,
) -> None:
    """The page side, in one language: what each browser draws."""
    secrets = secret_cards(private)
    for page in [*pages.values(), spectator]:
        page.evaluate(f"setLanguage('{language}')")
        settled(page)
    tag = f"{label} [{language}]"
    for seat, page in pages.items():
        shown = page.evaluate(PAGE_JS)
        check.ok(
            shown["mine"] == [seat]
            and shown["viewer"] == seat
            and shown["viewRevision"] == revision == shown["summaryRevision"],
            f"{tag}: seat {seat}'s page holds its own view of the checkpoint's"
            " revision",
            {
                key: shown[key]
                for key in ("mine", "viewer", "viewRevision", "summaryRevision")
            },
        )
        mine = private.get(seat, {})
        pending = mine.get("ix_pending", EMPTY_PENDING)
        words = page.evaluate(
            WORDS_JS,
            {
                "steps": ", ".join(str(step) for step in pending["shipping_rewards"]),
                "discount": pending["tech_discount"],
                "payment": pending["tech_payment"],
                "negotiators": pending["negotiators_returnable"],
                "card": (secrets or [""])[0] or SECRET_CARD,
            },
        )
        own_panel = shown["panels"][str(seat)]
        every_panel = " ".join(shown["panels"].values())
        shipping = bool(pending["shipping_rewards"])
        tech = bool(pending["tech_payment"])
        check.ok(
            (words["shipping"] in own_panel) == shipping
            and (words["shippingHead"] in every_panel) == shipping,
            f"{tag}: seat {seat}'s page "
            + ("draws" if shipping else "does not draw")
            + " the owed Shipping reward line"
            + (" on its own panel only" if shipping else ""),
            (words["shipping"], own_panel[:300]),
        )
        check.ok(
            (words["tech"] in own_panel) == tech
            and (words["techHead"] in every_panel) == tech
            and ((words["techHead"] in shown["body"]) == tech),
            f"{tag}: seat {seat}'s page "
            + ("draws" if tech else "does not draw")
            + " the open Acquire Tech line"
            + (" on its own panel only" if tech else ""),
            (words["tech"], own_panel[:300]),
        )
        bottom = mine.get("known_intrigue_bottom", [])
        expected_known = [["bottom", words["bottom"]]] if bottom else []
        check.ok(
            shown["known"] == expected_known
            and (words["bottomHead"] in shown["body"]) == bool(bottom)
            and words["topHead"] not in shown["body"],
            f"{tag}: seat {seat}'s page "
            + (
                "draws its known bottom card on the Intrigue deck"
                if bottom
                else "has no known-Intrigue line"
            )
            + ", and none at the top",
            (shown["known"], expected_known),
        )
        check.ok(
            words["heldHead"] not in shown["body"] and shown["held"] == [],
            f"{tag}: seat {seat}'s page marks no seat as holding a known Intrigue card",
            shown["held"],
        )
    shown = spectator.evaluate(PAGE_JS)
    words = spectator.evaluate(
        WORDS_JS,
        {
            "steps": "1",
            "discount": 1,
            "payment": "spice",
            "negotiators": 1,
            "card": SECRET_CARD,
        },
    )
    lines = [
        words[key]
        for key in ("shippingHead", "techHead", "heldHead", "bottomHead", "topHead")
    ]
    check.ok(
        shown["mine"] == []
        and shown["viewer"] is None
        and shown["known"] == []
        and shown["pending"] is None
        and not any(line in shown["body"] for line in lines),
        f"{tag}: the spectator's page holds no view and shows none of the lines",
        {key: shown[key] for key in ("mine", "viewer", "known", "pending")},
    )
    if secrets:
        for card in secrets:
            title = spectator.evaluate("(id) => nameOf(id)", card)
            check.ok(
                title not in shown["body"],
                f"{tag}: the spectator's page does not name the known card ({title})",
            )


def run_checkpoint(
    done: int,
    pages: dict[int, Any],
    spectator,
    game_id: str,
    all_pages: dict[str, tuple[Any, Any]],
) -> None:
    label, private = CHECKPOINTS[done]
    print(f"[checkpoint after {done} actions] {label}")
    _, summary = api(pages[0], "GET", f"/games/{game_id}")
    check.ok(
        not isinstance(summary["confirmation"], int),
        "no turn end waits for a press at the checkpoint",
        summary["confirmation"],
    )
    check.ok(
        converge(all_pages, game_id, f"checkpoint {done}", timeout=15),
        "every page, the spectator's too, has caught up to the server",
    )
    revision = summary["revision"]
    check_views(f"after {done}", pages, spectator, game_id, private, revision)
    for language in ("ko", "en"):
        check_pages(f"after {done}", pages, spectator, private, revision, language)
    for page in [*pages.values(), spectator]:
        page.evaluate("setLanguage('ko')")
        settled(page)


def scenario(base: str, browser) -> None:
    contexts = {}
    pages: dict[int, Any] = {}
    all_pages: dict[str, tuple[Any, Any]] = {}
    for seat in range(4):
        context, page, recorder = open_context(browser, f"seat{seat}", VIEWPORT)
        contexts[seat], pages[seat] = context, page
        all_pages[f"seat{seat}"] = (page, recorder)
    spectator_context, spectator, spectator_recorder = open_context(
        browser, "spectator", VIEWPORT
    )
    all_pages["spectator"] = (spectator, spectator_recorder)

    print(
        "[1] the host (seat 0's context) creates the table; each context claims"
        " its seat"
    )
    host = pages[0]
    host.goto(f"{base}/#admin={KEY}")
    wait_for_setup(host)
    check.ok(
        host.evaluate("state.server.admin") is True, "the host's context is the admin"
    )
    status, created = api(host, "POST", "/games", GAME)
    check.ok(
        status == 200,
        "POST /games takes original + Rise of Ix, four human seats",
        (status, created),
    )
    if status != 200:
        raise PlanMissed(f"the pinned table was refused: {created}")
    game_id = created["game_id"]
    check.ok(
        created["game_seed"] is None and created["rise_of_ix"] is True,
        "the remote summary hides the seed and says Rise of Ix is on",
        {key: created.get(key) for key in ("game_seed", "rise_of_ix")},
    )
    link = f"{base}/#game={game_id}"
    for seat in range(4):
        page = pages[seat]
        page.goto(link)
        page.wait_for_selector("#lobby-screen:not([hidden])")
        page.fill("#lobby-name", f"P{seat}")
        page.click(f"#lobby-seats li[data-seat='{seat}'] button")
        page.wait_for_selector("#game-screen:not([hidden])")
        check.ok(
            holds_seats(page, [seat], f"seat {seat} held"),
            f"context {seat} holds seat {seat} only",
        )
    spectator.goto(link)
    spectator.wait_for_selector("#lobby-screen:not([hidden])")
    check.ok(
        spectator.evaluate("state.me.seats.length") == 0,
        "the spectator's context holds no seat",
    )
    check.ok(
        holds_only_its_own_cookie(contexts, spectator_context, game_id),
        "each context holds its own seat cookie and no other",
    )

    print(f"[2] replaying {len(PLAN)} pinned actions (seed {SEED})")
    for index in range(len(PLAN)):
        take_plan_step(pages, game_id, index)
        done = index + 1
        if done in CHECKPOINTS:
            run_checkpoint(done, pages, spectator, game_id, all_pages)
        elif done % 20 == 0:
            print(f"  .. {done} actions")
    _, summary = api(pages[0], "GET", f"/games/{game_id}")
    check.ok(
        summary["revision"] > 0 and not summary["finished"],
        "the plan ended inside the game, on its last checkpoint",
    )

    print(
        "[3] the original game does not take Immortality yet"
        " (known top/held unreachable)"
    )
    status, refused = api(host, "POST", "/games", {**GAME, "immortality": True})
    check.ok(
        status == 400 and "immortality" in json.dumps(refused),
        "POST /games refuses original + Rise of Ix + Immortality (stage P7); if it is"
        " accepted now, add the Imperium Ceremony scenario (known_intrigue_top/held)",
        (status, refused),
    )
    for context in [*contexts.values(), spectator_context]:
        context.close()


def holds_only_its_own_cookie(
    contexts: dict[int, Any], spectator_context, game_id: str
) -> bool:
    """Each seat context holds exactly one cookie of this game (its own seat's,
    named by ``seat_cookie_name``), the spectator none: the contexts share
    nothing, so the fetches above prove what that one cookie allows."""
    held = {}
    for seat, context in contexts.items():
        names = sorted(c["name"] for c in context.cookies() if game_id in c["name"])
        held[seat] = names
    spectator = [c["name"] for c in spectator_context.cookies() if game_id in c["name"]]
    flat = [name for names in held.values() for name in names]
    return (
        all(len(names) == 1 for names in held.values())
        and len(set(flat)) == 4
        and not spectator
    )


def main() -> None:
    with (
        server("--remote", "--admin-key", KEY) as (base, server_log),
        chrome() as browser,
    ):
        try:
            scenario(base, browser)
        except PlanMissed as missed:
            check.ok(False, f"the pinned plan was missed: {missed}")
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        log_text = server_log.read_text()
        bad = "Traceback" in log_text or "ERROR" in log_text
        check.ok(not bad, f"no server errors (see {SERVER_LOG_COPY})")
    check.finish()


if __name__ == "__main__":
    main()
