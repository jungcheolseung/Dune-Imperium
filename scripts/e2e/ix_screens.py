"""E2E of Rise of Ix's and Immortality's hidden values through the real remote
server path.

The engine's own views (``core.observation``: ``PrivatePlayerView``'s
``ix_pending``, ``peeked_intrigue_ids``, ``known_intrigue_top`` / ``_bottom`` /
``_held``) are covered by unit tests, and ``imperium_game.py`` [7] draws the
markers from a view it edits by hand. This script asks the question the table
cares about: what does each seat's browser get from the server, and what does
its page show? A ``--remote`` server, four contexts that each claim one seat
through the lobby (so each holds only its own HttpOnly seat cookie), and a
fifth that claims none (the spectator). Every fetch below runs in the page of
the context that asks, with that context's own cookie; the host's admin key
opens no seat (``_authorize_seat_locked``), and the host is seat 0's own
context.

For each hidden value, at the moment it is real:

- the owner's view (``GET /games/{id}/seats/{seat}/view``) carries it, and the
  owner's page draws it: on its own seat panel (``panels.ix_pending_shipping``,
  ``panels.ix_pending_tech``), in the Intrigue deck area (``.known-intrigue``),
  on the holder's panel (``panels.known_intrigue_held``) or among its action
  rows (the two peeked cards);
- each other seat's own view carries the empty value (its private block is its
  own), no payload it can fetch (view, snapshot with the action log) and no
  state its page holds names a tracked card unless that seat may know it (its
  own known cards, or the card it holds in hand), its page shows none of the
  lines, and asking for the owner's view, actions or snapshot is refused (403);
- the spectator (no seat) is refused the same, its summary has no such field or
  card, its page shows none of the lines and holds no view at all.

Two tables, each a fresh game on the same server:

1. Original game + Rise of Ix, four human seats (seed 41):
   a. ``ix_pending.tech_discount`` / ``tech_payment`` /
      ``negotiators_returnable``: seat 0 sends an Agent to Tech Negotiation
      holding a Negotiator, and its Acquire Tech (Tech Discount 1, spice, one
      Negotiator returnable) is open.
   b. ``known_intrigue_bottom``: seat 0 buys Sonic Snoopers and puts an
      Intrigue card at the Intrigue deck's bottom, which only it then knows.
      (Checked again at the end: still known, still hidden.)
   c. ``ix_pending.shipping_rewards``: seat 1 recalls its Freighter from
      Shipping step 1 (Smuggling); the step-1 reward is owed.
2. Uprising + Immortality, four human seats (seed 143), sent as the setup
   screen sends it with only the Immortality box checked:
   a. ``peeked_intrigue_ids``: seat 0 plays Imperium Ceremony and sees the
      Intrigue deck's top two cards while it keeps one (owner only).
   b. ``known_intrigue_top``: it keeps one, puts the other back on top and
      knows it there.
   c. ``known_intrigue_held``: seat 1 draws that top card at Secrets; seat 0's
      view says seat 1 holds it, and seat 0's page marks seat 1's panel. Seat 1
      holds the card in its own hand, and the other two seats and the
      spectator carry its id nowhere.

Not reachable, and named here so the gap stays visible: Hundro Moritani's
Intelligence (``known_intrigue_top`` too) and Ilesa Ecaz's set-aside card
(``set_aside_card_id``) are not in the engine yet. POST /games refuses
``base_game: "imperium"`` with ``immortality`` ("the original game takes
immortality from stage P7") and Rise of Ix on Uprising (also P7), so no table
combines the original game, Rise of Ix and Immortality; that is why table 2 is
Uprising. Step [3] asserts that the original game still refuses Immortality.

The plans are pinned, not searched: each table's seed, its POST body and its
``PLAN``, the exact whole actions to take (seat, action id, arguments) in
order. A plan step that is not on offer, or a checkpoint whose pinned values
differ, FAILS the run and names the step or state missed; nothing is skipped.
Turn-end presses are not choices: the script presses whichever seat the server
says holds one.

How the constants were found: scratch finders in
``tmp/claude/5823a41d/ix-screens/`` (git-ignored; kept there, not in the
repository). Both play four-human games in-process through
``GameSessionManager`` (the layer the server itself uses, so the answers are
the same whole actions) with random answers whose weights favour the goal,
and read each state for the targets.

- Table 1: ``find.py`` weights Smuggling, Tech Negotiation, Dreadnought and
  Interstellar Shipping up and troop shuffling down; ``search.py`` runs it over
  seeds 1-239 with three answer streams each (at most 220 actions). Seven of
  the 717 playouts reached a Shipping reward owed, an Acquire Tech open with a
  returnable Negotiator and a bottom-known Intrigue card; the shortest, seed 41
  with answer stream 41 * 1000 + 2, is ``IX_PLAN`` (88 actions).
- Table 2: ``find2.py`` weights Imperium Ceremony (to buy it, then to play it)
  up by 300, and, once a seat knows the top card, Intrigue-drawing spaces up
  for every seat but the knower. It was run over the eight seeds below 200
  whose opening Imperium Row holds Imperium Ceremony (44, 99, 107, 135, 143,
  147, 183, 198) with 25 answer streams each (at most 330 actions): 12 of the
  200 playouts reached a peek, a known top card and a known held card. The
  shortest, seed 143 with answer stream 143 * 1000 + 24, is ``CEREMONY_PLAN``
  (91 actions).
- ``emit_plan.py`` / ``emit_plan2.py`` wrote the plans out, and ``replay.py``
  replays the first and prints every seat's private block at its checkpoints.
  The checkpoint values below were read from the server's views.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from typing import Any

from common import SERVER_LOG_COPY, Check, chrome, open_context, server
from open_mode import settled
from remote import converge, holds_seats, wait_for_setup

check = Check()

KEY = "e2e-ix-admin-key"
VIEWPORT = {"width": 1600, "height": 1000}

Step = tuple[int, str, dict[str, Any]]


@dataclass(frozen=True)
class Checkpoint:
    """What is true after some number of plan actions: the hidden fields each
    seat's own view carries (every other field, and every other seat, empty),
    and the tracked Intrigue cards sitting in a seat's own hand."""

    what: str
    private: dict[int, dict[str, Any]]
    hands: dict[int, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Table:
    name: str
    body: dict[str, Any]
    plan: list[Step]
    checkpoints: dict[int, Checkpoint]


# Table 1: the original game with Rise of Ix, as the setup screen's boxes would
# send them (everything else off).
IX_BODY = {
    "seats": ["human", "human", "human", "human"],
    "base_game": "imperium",
    "rise_of_ix": True,
    "game_seed": 41,
}
# Table 2: Uprising with Immortality alone, with every box of the setup screen's
# payload spelled out (the Go to 11 box stays unchecked; ``--first-player deal``
# of the e2e server leaves "Player 1 starts" unchecked too).
CEREMONY_BODY = {
    "seats": ["human", "human", "human", "human"],
    "base_game": "uprising",
    "choam_module": False,
    "leader_draft": False,
    "promo_cards": False,
    "bloodlines": False,
    "tech_module": False,
    "immortality": True,
    "arrakeen_scouts": False,
    "first_player_seat_zero": False,
    "go_to_11": False,
    "epic_game": False,
    "rise_of_ix": False,
    "game_seed": 143,
}

# (seat, action id, arguments), in order; the number after each is its index
# (the checkpoints count the actions applied).
IX_PLAN: list[Step] = [
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

# (seat, action id, arguments), in order; the number after each is its index.
CEREMONY_PLAN: list[Step] = [
    # Round 1: seat 0 reveals and buys Imperium Ceremony (6 Persuasion).
    (0, "reveal_turn", {}),  # 0
    (0, "acquire_imperium", {"instance_id": "imperium:imperium_ceremony:0"}),  # 1
    (
        0,
        "generate_reveal_specimens",
        {"printed": "experimentation", "source": "reveal_card"},
    ),  # 2
    (0, "return_specimen", {}),  # 3
    (0, "finish_reveal", {}),  # 4
    # Seat 1 reveals; seat 2 plays Assembly Hall (an Intrigue card); seat 3 reveals.
    (1, "reveal_turn", {}),  # 5
    (1, "acquire_reserve", {"card_id": "prepare_the_way"}),  # 6
    (1, "acquire_imperium", {"instance_id": "imperium:reliable_informant:0"}),  # 7
    (1, "use_family_atomics", {}),  # 8
    (
        1,
        "generate_reveal_specimens",
        {"printed": "experimentation", "source": "reveal_card"},
    ),  # 9
    (
        1,
        "generate_reveal_specimens",
        {"printed": "experimentation", "source": "reveal_card"},
    ),  # 10
    (1, "finish_reveal", {}),  # 11
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:1"}),  # 12
    (2, "place_agent", {"space_id": "assembly_hall"}),  # 13
    (2, "use_family_atomics", {}),  # 14
    (2, "resolve_board_effect", {"effect": "intrigue"}),  # 15
    (2, "finish_agent_turn", {}),  # 16
    (3, "reveal_turn", {}),  # 17
    (3, "use_family_atomics", {}),  # 18
    (3, "acquire_imperium", {"instance_id": "imperium:desert_survival:0"}),  # 19
    (
        3,
        "generate_reveal_specimens",
        {"printed": "experimentation", "source": "reveal_card"},
    ),  # 20
    (
        3,
        "generate_reveal_specimens",
        {"printed": "experimentation", "source": "reveal_card"},
    ),  # 21
    (3, "acquire_imperium", {"instance_id": "imperium:sardaukar_coordination:0"}),  # 22
    (3, "return_specimen", {}),  # 23
    (3, "finish_reveal", {}),  # 24
    # Seat 2, Gather Support, and a reveal; seat 1, Deliver Supplies.
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:0"}),  # 25
    (2, "place_agent", {"cost_option": 0, "space_id": "gather_support"}),  # 26
    (2, "resolve_board_effect", {"effect": "troops"}),  # 27
    (2, "finish_agent_turn", {}),  # 28
    (2, "reveal_turn", {}),  # 29
    (2, "acquire_reserve", {"card_id": "prepare_the_way"}),  # 30
    (2, "acquire_imperium", {"instance_id": "imperium:maker_keeper:0"}),  # 31
    (2, "finish_reveal", {}),  # 32
    (1, "choose_agent_card", {"card_id": "player:1:starter:diplomacy:0"}),  # 33
    (1, "place_agent", {"space_id": "deliver_supplies"}),  # 34
    (1, "resolve_faction_influence", {}),  # 35
    (1, "return_specimen", {}),  # 36
    (1, "return_specimen", {}),  # 37
    (1, "resolve_board_effect", {"effect": "resources"}),  # 38
    (1, "finish_agent_turn", {}),  # 39
    # Seat 2 reveals again; seat 3 reveals.
    (2, "reveal_turn", {}),  # 40
    (
        2,
        "generate_reveal_specimens",
        {"printed": "experimentation", "source": "reveal_card"},
    ),  # 41
    (2, "acquire_imperium", {"instance_id": "imperium:paracompass:0"}),  # 42
    (2, "acquire_imperium", {"instance_id": "imperium:unswerving_loyalty:1"}),  # 43
    (2, "return_specimen", {}),  # 44
    (
        2,
        "generate_reveal_specimens",
        {"printed": "experimentation", "source": "reveal_card"},
    ),  # 45
    (2, "finish_reveal", {}),  # 46
    (3, "reveal_turn", {}),  # 47
    (3, "finish_reveal", {}),  # 48
    # Seat 0's Agent turns (Hagga Basin, Dutiful Service) and its reveal, then Combat.
    (0, "use_family_atomics", {}),  # 49
    (0, "choose_agent_card", {"card_id": "player:0:starter:experimentation:0"}),  # 50
    (0, "place_agent", {"space_id": "hagga_basin"}),  # 51
    (0, "resolve_agent_card_effect", {}),  # 52
    (0, "return_specimen", {}),  # 53
    (0, "harvest_maker_spice", {"space_id": "hagga_basin"}),  # 54
    (0, "deploy_troops", {"count": 1}),  # 55
    (0, "finish_agent_turn", {}),  # 56
    (1, "reveal_turn", {}),  # 57
    (1, "finish_reveal", {}),  # 58
    (0, "choose_agent_card", {"card_id": "player:0:starter:seek_allies:0"}),  # 59
    (0, "place_agent", {"space_id": "dutiful_service"}),  # 60
    (0, "resolve_board_effect", {"effect": "resources"}),  # 61
    (0, "resolve_agent_card_effect", {}),  # 62
    (0, "resolve_faction_influence", {}),  # 63
    (0, "finish_agent_turn", {}),  # 64
    (0, "reveal_turn", {}),  # 65
    (0, "acquire_reserve", {"card_id": "prepare_the_way"}),  # 66
    (0, "finish_reveal", {}),  # 67
    (0, "pass_combat_intrigue", {}),  # 68
    (0, "resolve_combat_reward_icon", {"effect": "control"}),  # 69
    (0, "resolve_combat_reward_icon", {"effect": "resources"}),  # 70
    (0, "resolve_combat_reward_icon", {"effect": "troops"}),  # 71
    # Round 2: seats 2 and 3 send an Agent (Assembly Hall, Gather Support).
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:1"}),  # 72
    (2, "place_agent", {"space_id": "assembly_hall"}),  # 73
    (2, "resolve_board_effect", {"effect": "intrigue"}),  # 74
    (2, "finish_agent_turn", {}),  # 75
    (3, "choose_agent_card", {"card_id": "player:3:starter:dagger:0"}),  # 76
    (3, "place_agent", {"cost_option": 0, "space_id": "gather_support"}),  # 77
    (3, "resolve_board_effect", {"effect": "troops"}),  # 78
    (3, "finish_agent_turn", {}),  # 79
    # Seat 0 plays Imperium Ceremony at Deliver Supplies and looks at the Intrigue
    (0, "choose_agent_card", {"card_id": "imperium:imperium_ceremony:0"}),  # 80
    (0, "place_agent", {"space_id": "deliver_supplies"}),  # 81
    (0, "resolve_agent_card_effect", {}),  # 82
    # deck's top two (checkpoint 83: seat 0 sees both); it keeps Gruesome Sacrifice and
    (0, "keep_peeked_intrigue", {"instance_id": "intrigue:gruesome_sacrifice:1"}),  # 83
    # Imperium Politics goes back on top (checkpoint 84: seat 0 knows the top card).
    (0, "resolve_board_effect", {"effect": "resources"}),  # 84
    (0, "resolve_faction_influence", {}),  # 85
    (0, "finish_agent_turn", {}),  # 86
    # Seat 1, Secrets, draws an Intrigue card: the top card (checkpoint 91: seat 0 knows
    (1, "choose_agent_card", {"card_id": "player:1:starter:seek_allies:0"}),  # 87
    (1, "place_agent", {"space_id": "secrets"}),  # 88
    (1, "resolve_faction_influence", {}),  # 89
    # that seat 1 holds it).
    (1, "resolve_board_effect", {"effect": "intrigue"}),  # 90
]

EMPTY_PENDING = {
    "shipping_rewards": [],
    "tech_discount": 0,
    "tech_payment": "",
    "negotiators_returnable": 0,
}
EMPTY_PRIVATE = {
    "ix_pending": EMPTY_PENDING,
    "known_intrigue_top": "",
    "known_intrigue_bottom": [],
    "known_intrigue_held": [],
    "peeked_intrigue_ids": [],
}
TECH_PENDING = {
    "shipping_rewards": [],
    "tech_discount": 1,
    "tech_payment": "spice",
    "negotiators_returnable": 1,
}
SHIPPING_PENDING = {**EMPTY_PENDING, "shipping_rewards": [1]}
SECRET_CARD = "intrigue:master_tactician:1"
KNOWN_BOTTOM = [[0, SECRET_CARD]]
PEEKED = ["intrigue:gruesome_sacrifice:1", "intrigue:imperium_politics:0"]
KEPT = "intrigue:gruesome_sacrifice:1"
TOP_CARD = "intrigue:imperium_politics:0"

IX_TABLE = Table(
    "original + Rise of Ix",
    IX_BODY,
    IX_PLAN,
    {
        79: Checkpoint(
            "Acquire Tech open for seat 0 (Tech Negotiation, Tech Discount 1,"
            " spice, one Negotiator returnable)",
            {0: {"ix_pending": TECH_PENDING}},
        ),
        83: Checkpoint(
            "seat 0 put an Intrigue card at the deck's bottom (Sonic Snoopers)",
            {0: {"known_intrigue_bottom": KNOWN_BOTTOM}},
        ),
        88: Checkpoint(
            "seat 1 recalled its Freighter from step 1: the step-1 reward is"
            " owed (seat 0 still knows its bottom card)",
            {
                0: {"known_intrigue_bottom": KNOWN_BOTTOM},
                1: {"ix_pending": SHIPPING_PENDING},
            },
        ),
    },
)
CEREMONY_TABLE = Table(
    "Uprising + Immortality",
    CEREMONY_BODY,
    CEREMONY_PLAN,
    {
        83: Checkpoint(
            "seat 0 plays Imperium Ceremony and sees the Intrigue deck's top two"
            " cards while it keeps one",
            {0: {"peeked_intrigue_ids": PEEKED}},
        ),
        84: Checkpoint(
            "seat 0 kept one card and put the other back on top: it knows the top card",
            {
                0: {
                    "known_intrigue_top": TOP_CARD,
                    # The view lists every known card still in the deck by its
                    # depth from the bottom (``known_intrigue_places``): the top
                    # card of a 52-card deck is 51 above the bottom one. The
                    # page names it once, on top (``board.js``).
                    "known_intrigue_bottom": [[51, TOP_CARD]],
                }
            },
            {0: [KEPT]},
        ),
        91: Checkpoint(
            "seat 1 drew the top card at Secrets: seat 0 knows seat 1 holds it",
            {0: {"known_intrigue_held": [[1, TOP_CARD]]}},
            {0: [KEPT], 1: [TOP_CARD]},
        ),
    },
)

SECRET_KEYS = (
    "ix_pending",
    "shipping_rewards",
    "tech_payment",
    "negotiators_returnable",
    "peeked_intrigue_ids",
    "known_intrigue",
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

# What a page shows: its own seat panels, Intrigue deck lines and action rows,
# whose view it holds, the revision of that view, and the state it holds.
PAGE_JS = """() => {
  const norm = (s) => s.replace(/\\s+/g, " ").trim();
  const view = state.view;
  const private_ = view && view.private ? view.private : null;
  const actions = document.getElementById("actions");
  return {
    mine: state.me ? state.me.seats : null,
    viewer: view ? view.player : null,
    viewRevision: view ? view.revision : null,
    summaryRevision: state.summary ? state.summary.revision : null,
    held: private_ ? private_.known_intrigue_held : null,
    peeked: private_ ? private_.peeked_intrigue_ids : null,
    pending: private_ ? private_.ix_pending : null,
    panels: Object.fromEntries([...document.querySelectorAll("#seats .seat")]
      .map((card) => [card.dataset.seat, norm(card.textContent)])),
    known: [...document.querySelectorAll(".known-intrigue")]
      .map((el) => [el.dataset.known, norm(el.textContent)]),
    actionRows: actions ? norm(actions.innerText) : "",
    body: norm(document.body.innerText),
    stateText: JSON.stringify([state.view, state.log, state.summary, state.actions]),
  };
}"""

# The page's own words for each line, in the language it speaks now, so that
# the script reads the lines out of ui_text.js and not out of its own copy.
WORDS_JS = """(args) => {
  const mark = "\\u0001";
  const head = (key, vars) => t(key, vars).split(mark)[0];
  const name = (id) => (id ? nameOf(id) : "");
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
    held: t("panels.known_intrigue_held", {cards: args.held.map(name).join(", ")}),
    bottom: t("board.known_intrigue_bottom", {
      cards: args.depth
        ? t("board.known_intrigue_above", {card: name(args.bottom), depth: args.depth})
        : t("board.known_intrigue_at_bottom", {card: name(args.bottom)}),
    }),
    bottomHead: head("board.known_intrigue_bottom", {cards: mark}),
    top: t("board.known_intrigue_top", {card: name(args.top)}),
    topHead: head("board.known_intrigue_top", {card: mark}),
    peeked: args.peeked.map(name),
  };
}"""


class PlanMissed(Exception):
    """A pinned step or state is not what the server has."""


def api(page, method: str, path: str, body: dict | None = None) -> tuple[int, Any]:
    """One request from ``page``: its own cookies, nobody else's."""
    result = page.evaluate(FETCH_JS, [method, path, body])
    return result["status"], result["data"]


def step_label(table: Table, index: int) -> str:
    seat, action_id, arguments = table.plan[index]
    return (
        f"{table.name}: step {index + 1}/{len(table.plan)}"
        f" (seat {seat} {action_id} {arguments})"
    )


def take_plan_step(
    table: Table, pages: dict[int, Any], game_id: str, index: int
) -> None:
    """Take ``table.plan[index]`` as its seat, from that seat's own page."""
    seat, action_id, arguments = table.plan[index]
    label = step_label(table, index)
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
            raise PlanMissed(f"{label}: seat {held}'s turn end: HTTP {status}")
    decision = summary["decision"]
    if summary["finished"] or decision is None or decision["owner"] != seat:
        raise PlanMissed(
            f"{label}: the server's decision is {decision}, not seat {seat}'s"
        )
    status, listed = api(pages[seat], "GET", f"/games/{game_id}/seats/{seat}/actions")
    if status != 200:
        raise PlanMissed(f"{label}: seat {seat}'s actions: HTTP {status}")
    rows = [
        row
        for row in listed["actions"]
        if row["action_id"] == action_id and (row["arguments"] or {}) == arguments
    ]
    if len(rows) != 1:
        offered = [(row["action_id"], row["arguments"]) for row in listed["actions"]]
        raise PlanMissed(f"{label}: not on offer exactly once; offered {offered[:12]}")
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
        raise PlanMissed(f"{label}: HTTP {status}")


def may_carry(point: Checkpoint) -> dict[int, set[str]]:
    """The tracked cards each seat may carry an id of: those in its own hidden
    fields, the one it holds in hand, and, for a card another seat knows it
    holds, the card itself."""
    may: dict[int, set[str]] = {seat: set() for seat in range(4)}
    for seat, fields in point.private.items():
        if fields.get("known_intrigue_top"):
            may[seat].add(fields["known_intrigue_top"])
        may[seat].update(
            card for _depth, card in fields.get("known_intrigue_bottom", [])
        )
        may[seat].update(fields.get("peeked_intrigue_ids", []))
        for holder, card in fields.get("known_intrigue_held", []):
            may[seat].add(card)
            may[holder].add(card)
    for seat, cards in point.hands.items():
        may[seat].update(cards)
    return may


def tracked_cards(point: Checkpoint) -> list[str]:
    return sorted({card for cards in may_carry(point).values() for card in cards})


def check_views(
    label: str,
    pages: dict[int, Any],
    spectator,
    game_id: str,
    point: Checkpoint,
    revision: int,
) -> None:
    """The HTTP side: each seat's own view and snapshot, the spectator's
    summary, and the refusals."""
    may = may_carry(point)
    secrets = tracked_cards(point)
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
        expected = {**EMPTY_PRIVATE, **point.private.get(seat, {})}
        found = {key: view["private"][key] for key in EMPTY_PRIVATE}
        check.ok(
            found == expected and view["player"] == seat,
            f"{label}: seat {seat}'s own view carries"
            + (" its hidden value" if seat in point.private else " no hidden value"),
            {"found": found, "expected": expected},
        )
        check.ok(
            view["revision"] == revision == snapshot["summary"]["revision"],
            f"{label}: seat {seat}'s view is of the checkpoint's revision",
            (view["revision"], revision, snapshot["summary"]["revision"]),
        )
        text = json.dumps([view, snapshot])
        for card in secrets:
            check.ok(
                (card in text) == (card in may[seat]),
                f"{label}: seat {seat}'s view and snapshot (with the action log)"
                + (" name" if card in may[seat] else " do not name")
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
    for owner in (seat for seat, cards in may.items() if cards):
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
        f"{label}: every other seat and the spectator is refused (403) the"
        " view, actions and snapshot of a seat that holds a hidden value or card",
        refused[:4],
    )


def check_pages(
    label: str,
    pages: dict[int, Any],
    spectator,
    point: Checkpoint,
    revision: int,
    language: str,
) -> None:
    """The page side, in one language: what each browser draws."""
    may = may_carry(point)
    secrets = tracked_cards(point)
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
        mine = point.private.get(seat, {})
        pending = mine.get("ix_pending", EMPTY_PENDING)
        top = mine.get("known_intrigue_top", "")
        # The page's bottom line leaves out the known top card.
        bottom = [
            entry for entry in mine.get("known_intrigue_bottom", []) if entry[1] != top
        ]
        held = mine.get("known_intrigue_held", [])
        peeked = mine.get("peeked_intrigue_ids", [])
        words = page.evaluate(
            WORDS_JS,
            {
                "steps": ", ".join(str(step) for step in pending["shipping_rewards"]),
                "discount": pending["tech_discount"],
                "payment": pending["tech_payment"],
                "negotiators": pending["negotiators_returnable"],
                "bottom": bottom[0][1] if bottom else "",
                "depth": bottom[0][0] if bottom else 0,
                "top": top,
                "held": [card for _holder, card in held],
                "peeked": peeked,
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
        expected_known = [
            *([["top", words["top"]]] if top else []),
            *([["bottom", words["bottom"]]] if bottom else []),
        ]
        check.ok(
            shown["known"] == expected_known
            and (words["topHead"] in shown["body"]) == bool(top)
            and (words["bottomHead"] in shown["body"]) == bool(bottom),
            f"{tag}: seat {seat}'s page "
            + (
                "draws its known " + " and ".join(kind for kind, _ in expected_known)
                if expected_known
                else "has no known-Intrigue line"
            )
            + " on the Intrigue deck",
            (shown["known"], expected_known),
        )
        holders = sorted({holder for holder, _card in held})
        marked = [
            other
            for other, text in shown["panels"].items()
            if words["heldHead"] in text
        ]
        check.ok(
            shown["held"] == held
            and marked == [str(holder) for holder in holders]
            and all(words["held"] in shown["panels"][str(holder)] for holder in holders)
            and (words["heldHead"] in shown["body"]) == bool(held),
            f"{tag}: seat {seat}'s page "
            + (
                f"marks seat {holders} as holding a known Intrigue card"
                if held
                else "marks no seat as holding a known Intrigue card"
            ),
            {"held": shown["held"], "marked": marked, "words": words["held"]},
        )
        check.ok(
            shown["peeked"] == peeked
            and all(name in shown["actionRows"] for name in words["peeked"])
            and (not peeked or len(set(words["peeked"])) == len(peeked)),
            f"{tag}: seat {seat}'s page "
            + (
                "lists the two peeked cards among its action rows"
                if peeked
                else "holds no peeked card"
            ),
            (shown["peeked"], words["peeked"], shown["actionRows"][:200]),
        )
        for card in secrets:
            check.ok(
                (card in shown["stateText"]) == (card in may[seat]),
                f"{tag}: seat {seat}'s page state"
                + (" holds" if card in may[seat] else " does not hold")
                + f" {card}",
            )
    shown = spectator.evaluate(PAGE_JS)
    words = spectator.evaluate(
        WORDS_JS,
        {
            "steps": "1",
            "discount": 1,
            "payment": "spice",
            "negotiators": 1,
            "bottom": SECRET_CARD,
            "depth": 0,
            "top": TOP_CARD,
            "held": [TOP_CARD],
            "peeked": [],
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
        and not any(line in shown["body"] for line in lines)
        and not any(card in shown["stateText"] for card in secrets),
        f"{tag}: the spectator's page holds no view, shows none of the lines and"
        " holds no tracked card",
        {key: shown[key] for key in ("mine", "viewer", "known", "pending")},
    )


def run_checkpoint(
    table: Table,
    done: int,
    pages: dict[int, Any],
    spectator,
    game_id: str,
    all_pages: dict[str, tuple[Any, Any]],
) -> None:
    point = table.checkpoints[done]
    label = f"{table.name}, after {done}"
    print(f"[{table.name}: checkpoint after {done} actions] {point.what}")
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
    check_views(label, pages, spectator, game_id, point, revision)
    for language in ("ko", "en"):
        check_pages(label, pages, spectator, point, revision, language)
    for page in [*pages.values(), spectator]:
        page.evaluate("setLanguage('ko')")
        settled(page)


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


def play_table(base: str, browser, table: Table) -> None:
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
        f"[{table.name}] the host (seat 0's context) creates the table; each"
        " context claims its seat"
    )
    host = pages[0]
    host.goto(f"{base}/#admin={KEY}")
    wait_for_setup(host)
    check.ok(
        host.evaluate("state.server.admin") is True, "the host's context is the admin"
    )
    status, created = api(host, "POST", "/games", table.body)
    check.ok(
        status == 200,
        f"POST /games takes {table.name}, four human seats",
        (status, created),
    )
    if status != 200:
        raise PlanMissed(f"the pinned table was refused: {created}")
    game_id = created["game_id"]
    check.ok(
        created["game_seed"] is None
        and created["rise_of_ix"] is table.body.get("rise_of_ix", False)
        and created["immortality"] is table.body.get("immortality", False)
        and created["base_game"] == table.body["base_game"],
        "the remote summary hides the seed and says which boxes are on",
        {
            key: created.get(key)
            for key in ("game_seed", "base_game", "rise_of_ix", "immortality")
        },
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

    print(f"[{table.name}] replaying {len(table.plan)} pinned actions")
    for index in range(len(table.plan)):
        take_plan_step(table, pages, game_id, index)
        done = index + 1
        if done in table.checkpoints:
            run_checkpoint(table, done, pages, spectator, game_id, all_pages)
        elif done % 20 == 0:
            print(f"  .. {done} actions")
    _, summary = api(pages[0], "GET", f"/games/{game_id}")
    check.ok(
        summary["revision"] > 0 and not summary["finished"],
        f"{table.name}: the plan ended inside the game, on its last checkpoint",
    )
    for context in [*contexts.values(), spectator_context]:
        context.close()


def check_original_refuses_immortality(base: str, browser) -> None:
    """The original game takes no Immortality until stage P7, which is why the
    Imperium Ceremony table is an Uprising one."""
    print("[3] the original game still does not take Immortality (stage P7)")
    context, page, _ = open_context(browser, "host", VIEWPORT)
    page.goto(f"{base}/#admin={KEY}")
    wait_for_setup(page)
    status, refused = api(page, "POST", "/games", {**IX_BODY, "immortality": True})
    check.ok(
        status == 400 and "immortality" in json.dumps(refused),
        "POST /games refuses base_game imperium with Immortality (HTTP 400, stage P7)",
        (status, refused),
    )
    context.close()


def main() -> None:
    with (
        server("--remote", "--admin-key", KEY) as (base, server_log),
        chrome() as browser,
    ):
        try:
            for number, table in enumerate((IX_TABLE, CEREMONY_TABLE), start=1):
                print(f"[{number}] {table.name}")
                play_table(base, browser, table)
            check_original_refuses_immortality(base, browser)
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
