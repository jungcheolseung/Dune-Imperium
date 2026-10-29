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
  lines, and asking for the owner's view, actions, snapshot or log is refused
  (403). That owner is every seat with a hidden value, a pending Ix choice
  alone included, or a hidden card;
- no other seat's payload (its own view, snapshot and log, the seatless
  snapshot, the VP ledger) carries an ``ix_pending`` field anywhere but its own
  empty private block: a pending choice is a number or a word, so it is looked
  for by its field names in the whole payload, not by its value;
- no other seat's payloads, and not the spectator's, and no other seat's page
  anywhere in its document (``outerHTML`` and ``textContent``), hold a tracked
  card it may not know: not its id, its English or Korean name or the path of
  either picture (a public copy of the same card would show the same name, so
  a find also names any copy the page's state holds);
- the spectator (no seat) is refused the same, its summary and the seatless
  snapshot have no such field or card, its page shows none of the lines and
  holds no view at all.

Step [4] plays table 3's twin (``Table.twin``): the same game where Ilesa sets
another card aside. At every action from her set-aside to the action before
the card comes back, every payload of the other three seats and of the
spectator must be the same in both games (the game id, clock and presence
aside), and none names her card's id: so neither the card nor its name, base
id or picture reaches them, even by a count.

Then, step [6], hot-seat hand-overs on an open server, where one page plays
every seat (``Table.handovers``: one each for tables 1 and 2, Hundro to Ilesa
and Ilesa to the first player on table 3): the page shows the owner and draws
its hidden lines, the owner's turn ends, and the page that now shows the next
seat holds none of the owner's lines or cards (the view replaced, the
containers emptied).

Three tables, each a fresh game on the same server:

1. Original game + Rise of Ix, four human seats (seed 4):
   a. ``ix_pending.tech_discount`` / ``tech_payment``: seat 2 sends an Agent
      to Tech Negotiation, and its Acquire Tech (Tech Discount 1, spice) is
      open.
   b. ``known_intrigue_bottom``: seat 2 buys Sonic Snoopers and puts an
      Intrigue card at the Intrigue deck's bottom, which only it then knows.
      (Checked again at the two later moments: still known, still hidden.)
   c. ``ix_pending.shipping_rewards``: seat 0 recalls its Freighter from
      Shipping step 1; the step-1 reward is owed.
   d. ``ix_pending.negotiators_returnable``: seat 0 sends an Agent to the
      Dreadnought space holding a Negotiator, and its Acquire Tech (spice,
      one Negotiator returnable) is open.
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
3. Original game + Rise of Ix with the leader draft (seed 4; without the draft
   the original game deals its own first four Leaders), seat 1 Viscount Hundro
   Moritani and seat 0 Ilesa Ecaz:
   a. ``peeked_intrigue_ids``: Hundro's Intelligence shows him the Intrigue
      deck's top two cards while he keeps one.
   b. ``known_intrigue_top``: he keeps one (his hand) and knows the other back
      on top, and the log shows other seats only that he kept one.
   c. ``set_aside_card_id``: Ilesa sets a card aside at Round Start (her turn
      end held). Other seats see ``has_set_aside_card`` (her panel's "one card
      set aside") and ``(비공개)`` in the log; she sees her card.
   d. Her second turn starts and the card comes back to her hand, public:
      her own ``private.hand`` and every seat's view of her ``hand_public``
      hold it, every seat's log has its ``card_returned_to_hand`` event, and
      every page says it came back; the set-aside's log entry stays
      ``(비공개)`` to the others (a project convention: the rules reveal the
      card, not old log lines; docs silent). A seatless spectator gets no
      table on a remote server, so the card reaches it nowhere.
   Checked also after each turn in between (20, 23, 26, 31). Her card is one
   of her starter cards, whose name and picture every seat's own starter
   cards share, so in one game it is looked for by its id; step [4]'s twin
   game covers its name, base id and picture.

Not reached, and named here so the gap stays visible: POST /games refuses
``base_game: "imperium"`` with ``immortality`` ("the original game takes
immortality from stage P7") and Rise of Ix on Uprising (also P7), so no table
combines the original game, Rise of Ix and Immortality; that is why table 2 is
Uprising. Step [5] asserts that the original game still refuses Immortality.

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
  seeds with three answer streams each and keeps a playout that reaches a
  Shipping reward owed, an Acquire Tech open with a returnable Negotiator and a
  bottom-known Intrigue card. Re-run after P4 4cdf1e99 was merged (its Ix card
  data changed the deal and the first plan, seed 41, missed at step 3): over
  seeds 1-119 (at most 220 actions) two playouts got there; the shorter was
  seed 4 with answer stream 4 * 1000 + 0 (178 actions). Re-run after P4
  c8a44cfd (new Ix Intrigue cards changed the deal; the plan missed at step
  48): seed 4 and the same answer stream got there again, in 184 actions, now
  ``IX_PLAN``; ``replay5.py`` printed its checkpoints.
- Table 2: ``find2.py`` weights Imperium Ceremony (to buy it, then to play it)
  up by 300, and, once a seat knows the top card, Intrigue-drawing spaces up
  for every seat but the knower. It was run over the eight seeds below 200
  whose opening Imperium Row holds Imperium Ceremony (44, 99, 107, 135, 143,
  147, 183, 198) with 25 answer streams each (at most 330 actions): 12 of the
  200 playouts reached a peek, a known top card and a known held card. The
  shortest, seed 143 with answer stream 143 * 1000 + 24, is ``CEREMONY_PLAN``
  (91 actions).
- Table 3: ``find4.py`` plays the leader draft taking Hundro and Ilesa when
  offered (never the Baron) and random answers after it, until Ilesa's card
  comes back; over seeds 1-5, seeds 3 and 4 dealt both, and seed 4 (answer
  stream 4) brings the card back at her second turn's start, not with a
  first-turn Reveal, with Ilesa not the first player (a first-player fix is
  still open in P4). ``show4.py`` prints every seat's private block step by
  step; the plan is ``LEADERS_PLAN`` (38 actions).
- ``emit_plan.py`` / ``emit_plan2.py`` / ``emit_plan4.py`` wrote the plans out,
  and ``replay.py`` replays the first and prints every seat's private block at
  its checkpoints. The checkpoint values below were read from the server's
  views.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field, replace
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
    # Tracked cards in a seat's own hand: an Intrigue card in its view's
    # ``private.intrigue_cards``, any other in ``private.hand``.
    hands: dict[int, list[str]] = field(default_factory=dict)
    # The seat whose turn end the server holds at the checkpoint, if any.
    held: int | None = None
    # Cards every seat now knows, by the seat whose public hand holds them (a
    # returned set-aside card): every seat's view has it in that seat's
    # ``hand_public``, and every seat's page state names it.
    public: dict[str, int] = field(default_factory=dict)
    # Events every seat's log holds: (kind, payload).
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    # Ilesa Ecaz's public set-aside flag per seat: "aside" (a card set aside)
    # or "returned" (it came back this turn).
    aside: dict[int, str] = field(default_factory=dict)
    # Sealed log entries: (action id, argument, value). Every seat's log holds
    # the entry once, naming the value to its actor and "(비공개)" to others.
    # That the set-aside's entry stays "(비공개)" to the others after the card
    # comes back is a project convention: docs/rules/rise-of-ix.md 13 and
    # OQ-119 say the card is revealed at her second turn, not whether old log
    # lines are opened then (docs silent; the coordinator asks the user).
    sealed: list[tuple[str, str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class Handover:
    """A hot-seat turn change: after ``shown`` actions (a checkpoint) the page
    shows ``owner`` and draws its hidden line; after ``passed`` actions, and
    the owner's turn-end press when it holds one (a turn that left nothing to
    take back holds none), ``viewer`` decides and the page shows it."""

    shown: int
    owner: int
    passed: int
    viewer: int


@dataclass(frozen=True)
class Twin:
    """A second game of the same table, where ``owner``'s secret pick at plan
    step ``index`` is ``step`` instead. From ``first`` to ``last`` actions
    every payload of every other seat and of the spectator must be the same
    in both games (``VOLATILE`` keys aside), so nothing of which card was
    picked reaches them: not its id, its name, its base id, its picture or a
    count that would give it away. In the first game no such payload names
    ``secret``, the card picked there, at any of those actions."""

    index: int
    step: Step
    owner: int
    first: int
    last: int
    secret: str


@dataclass(frozen=True)
class Table:
    name: str
    body: dict[str, Any]
    plan: list[Step]
    checkpoints: dict[int, Checkpoint]
    handovers: tuple[Handover, ...]
    twin: Twin | None = None


# Table 1: the original game with Rise of Ix, as the setup screen's boxes would
# send them (everything else off).
IX_BODY = {
    "seats": ["human", "human", "human", "human"],
    "base_game": "imperium",
    "rise_of_ix": True,
    "game_seed": 4,
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

# Table 3: the original game with Rise of Ix and the leader draft, the only way
# an original game deals Rise of Ix's Leaders (without the draft it deals the
# original game's first four, ``rules.engine.UprisingRulesEngine``).
LEADERS_BODY = {
    "seats": ["human", "human", "human", "human"],
    "base_game": "imperium",
    "rise_of_ix": True,
    "leader_draft": True,
    "game_seed": 4,
}

# (seat, action id, arguments), in order; the number after each is its index
# (the checkpoints count the actions applied).
IX_PLAN: list[Step] = [
    # Found on the engine as merged with P4 c8a44cfd (seed 4, answer stream
    # 4 * 1000 + 0): seat 2 opens an Acquire Tech at Tech Negotiation (25),
    # buys Sonic Snoopers and puts an Intrigue card at the bottom (29), seat 0
    # recalls its Freighter from step 1 (160), seat 0 opens an Acquire Tech at
    # the Dreadnought space holding a Negotiator (184).
    (3, "choose_masterstroke_faction", {"faction": "spacing_guild"}),  # 0
    (3, "choose_masterstroke_faction", {"faction": "bene_gesserit"}),  # 1
    (2, "choose_agent_card", {"card_id": "player:2:starter:diplomacy:0"}),  # 2
    (2, "place_agent", {"space_id": "stillsuits"}),  # 3
    (2, "resolve_faction_influence", {}),  # 4
    (2, "deploy_troops", {"count": 1}),  # 5
    (2, "resolve_board_effect", {"effect": "resources"}),  # 6
    (2, "finish_agent_turn", {}),  # 7
    (
        3,
        "choose_agent_card",
        {"card_id": "player:3:starter:dune_the_desert_planet:0"},
    ),  # 8
    (3, "place_agent", {"space_id": "smuggling"}),  # 9
    (3, "resolve_board_effect", {"effect": "resources"}),  # 10
    (3, "advance_board_freighter", {}),  # 11
    (3, "finish_agent_turn", {}),  # 12
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:0"},
    ),  # 13
    (0, "place_agent", {"space_id": "imperial_basin"}),  # 14
    (0, "deploy_troops", {"count": 2}),  # 15
    (0, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 16
    (0, "finish_agent_turn", {}),  # 17
    (1, "reveal_turn", {}),  # 18
    (1, "acquire_imperium", {"instance_id": "imperium:guild_ambassador:0"}),  # 19
    (1, "acquire_imperium", {"instance_id": "imperium:assassination_mission:1"}),  # 20
    (1, "finish_reveal", {}),  # 21
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:0"}),  # 22
    (2, "place_agent", {"space_id": "tech_negotiation"}),  # 23
    (2, "acquire_negotiation_tech", {}),  # 24
    (2, "acquire_tech", {"tech_id": "sonic_snoopers"}),  # 25
    (
        2,
        "resolve_tech_acquire_effect",
        {"effect": "intrigue", "tech_id": "sonic_snoopers"},
    ),  # 26
    (2, "trash_tech", {"tech_id": "sonic_snoopers"}),  # 27
    (2, "put_intrigue_on_bottom", {"card_id": "intrigue:ambush:1"}),  # 28
    (2, "finish_intrigue_bottom", {}),  # 29
    (2, "finish_agent_turn", {}),  # 30
    (3, "reveal_turn", {}),  # 31
    (3, "acquire_imperium", {"instance_id": "imperium:fremen_camp:0"}),  # 32
    (3, "finish_reveal", {}),  # 33
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:1"},
    ),  # 34
    (0, "place_agent", {"space_id": "imperium_hagga_basin"}),  # 35
    (0, "harvest_maker_spice", {"space_id": "imperium_hagga_basin"}),  # 36
    (0, "deploy_troops", {"count": 1}),  # 37
    (0, "finish_agent_turn", {}),  # 38
    (2, "reveal_turn", {}),  # 39
    (2, "acquire_imperium", {"instance_id": "imperium:sardaukar_infantry:1"}),  # 40
    (2, "acquire_imperium", {"instance_id": "imperium:imperial_shock_trooper:0"}),  # 41
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 42
    (2, "finish_reveal", {}),  # 43
    (0, "reveal_turn", {}),  # 44
    (0, "acquire_imperium", {"instance_id": "imperium:guild_administrator:1"}),  # 45
    (0, "finish_reveal", {}),  # 46
    (2, "pass_combat_intrigue", {}),  # 47
    (0, "pass_combat_intrigue", {}),  # 48
    (0, "resolve_combat_reward_icon", {"effect": "resources"}),  # 49
    (0, "resolve_combat_reward_icon", {"effect": "choose_influence"}),  # 50
    (0, "choose_combat_reward_influence", {"faction": "emperor"}),  # 51
    (0, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 52
    (2, "resolve_combat_reward_icon", {"effect": "resources"}),  # 53
    (3, "choose_agent_card", {"card_id": "player:3:starter:reconnaissance:0"}),  # 54
    (3, "place_agent", {"space_id": "carthag"}),  # 55
    (3, "deploy_troops", {"count": 2}),  # 56
    (3, "resolve_board_effect", {"effect": "intrigue"}),  # 57
    (3, "withdraw_troops", {"count": 1}),  # 58
    (3, "resolve_board_effect", {"effect": "troops"}),  # 59
    (3, "finish_agent_turn", {}),  # 60
    (0, "choose_agent_card", {"card_id": "player:0:starter:dagger:0"}),  # 61
    (0, "place_agent", {"space_id": "tech_negotiation"}),  # 62
    (0, "place_board_negotiator", {}),  # 63
    (0, "finish_agent_turn", {}),  # 64
    (1, "reveal_turn", {}),  # 65
    (1, "acquire_imperium", {"instance_id": "imperium:spice_smugglers:1"}),  # 66
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 67
    (1, "finish_reveal", {}),  # 68
    (
        2,
        "choose_agent_card",
        {"card_id": "player:2:starter:dune_the_desert_planet:0"},
    ),  # 69
    (2, "place_agent", {"space_id": "smuggling"}),  # 70
    (2, "advance_board_freighter", {}),  # 71
    (2, "resolve_board_effect", {"effect": "resources"}),  # 72
    (2, "finish_agent_turn", {}),  # 73
    (
        3,
        "choose_agent_card",
        {"card_id": "player:3:starter:dune_the_desert_planet:1"},
    ),  # 74
    (3, "place_agent", {"space_id": "imperial_basin"}),  # 75
    (3, "deploy_troops", {"count": 1}),  # 76
    (3, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 77
    (3, "deploy_troops", {"count": 1}),  # 78
    (3, "finish_agent_turn", {}),  # 79
    (0, "choose_agent_card", {"card_id": "player:0:starter:reconnaissance:0"}),  # 80
    (0, "place_agent", {"space_id": "arrakeen"}),  # 81
    (0, "resolve_board_effect", {"effect": "troops"}),  # 82
    (0, "resolve_board_effect", {"effect": "cards"}),  # 83
    (0, "finish_agent_turn", {}),  # 84
    (2, "choose_agent_card", {"card_id": "player:2:starter:seek_allies:0"}),  # 85
    (2, "place_agent", {"space_id": "secrets"}),  # 86
    (2, "resolve_board_effect", {"effect": "intrigue"}),  # 87
    (2, "resolve_faction_influence", {}),  # 88
    (2, "resolve_agent_card_effect", {}),  # 89
    (2, "finish_agent_turn", {}),  # 90
    (3, "reveal_turn", {}),  # 91
    (3, "finish_reveal", {}),  # 92
    (0, "reveal_turn", {}),  # 93
    (0, "finish_reveal", {}),  # 94
    (2, "reveal_turn", {}),  # 95
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 96
    (2, "finish_reveal", {}),  # 97
    (3, "play_intrigue", {"card_id": "intrigue:master_tactician:2", "option": 1}),  # 98
    (3, "retreat_intrigue_troops", {"count": 1}),  # 99
    (3, "pass_combat_intrigue", {}),  # 100
    (3, "resolve_combat_reward_icon", {"effect": "victory_points"}),  # 101
    (3, "resolve_combat_reward_icon", {"effect": "control"}),  # 102
    (3, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 103
    (0, "choose_agent_card", {"card_id": "imperium:guild_administrator:1"}),  # 104
    (0, "place_agent", {"space_id": "smuggling"}),  # 105
    (0, "trash_agent_card", {"card_id": "player:0:starter:dagger:0"}),  # 106
    (0, "advance_board_freighter", {}),  # 107
    (0, "resolve_board_effect", {"effect": "resources"}),  # 108
    (0, "finish_agent_turn", {}),  # 109
    (1, "reveal_turn", {}),  # 110
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 111
    (
        1,
        "gain_reveal_resources",
        {
            "printed": "assassination_mission",
            "solari": 1,
            "source": "reveal_card",
            "spice": 0,
            "water": 0,
        },
    ),  # 112
    (1, "finish_reveal", {}),  # 113
    (2, "reveal_turn", {}),  # 114
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 115
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 116
    (2, "finish_reveal", {}),  # 117
    (
        3,
        "choose_agent_card",
        {"card_id": "player:3:starter:dune_the_desert_planet:1"},
    ),  # 118
    (3, "place_agent", {"space_id": "imperium_hagga_basin"}),  # 119
    (3, "deploy_troops", {"count": 1}),  # 120
    (3, "harvest_maker_spice", {"space_id": "imperium_hagga_basin"}),  # 121
    (3, "finish_agent_turn", {}),  # 122
    (0, "choose_agent_card", {"card_id": "player:0:starter:seek_allies:0"}),  # 123
    (0, "place_agent", {"space_id": "foldspace"}),  # 124
    (0, "resolve_board_effect", {"effect": "foldspace"}),  # 125
    (0, "resolve_agent_card_effect", {}),  # 126
    (0, "resolve_faction_influence", {}),  # 127
    (0, "finish_agent_turn", {}),  # 128
    (3, "choose_agent_card", {"card_id": "player:3:starter:seek_allies:0"}),  # 129
    (3, "place_agent", {"space_id": "stillsuits"}),  # 130
    (3, "resolve_agent_card_effect", {}),  # 131
    (3, "resolve_faction_influence", {}),  # 132
    (3, "resolve_board_effect", {"effect": "resources"}),  # 133
    (3, "finish_agent_turn", {}),  # 134
    (0, "reveal_turn", {}),  # 135
    (0, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 136
    (0, "finish_reveal", {}),  # 137
    (3, "reveal_turn", {}),  # 138
    (3, "finish_reveal", {}),  # 139
    (3, "pass_combat_intrigue", {}),  # 140
    (3, "resolve_combat_reward_icon", {"effect": "resources"}),  # 141
    (3, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 142
    (1, "reveal_turn", {}),  # 143
    (1, "acquire_imperium", {"instance_id": "imperium:liet_kynes_card:0"}),  # 144
    (1, "finish_reveal", {}),  # 145
    (2, "choose_agent_card", {"card_id": "reserve:arrakis_liaison:7"}),  # 146
    (2, "place_agent", {"space_id": "carthag"}),  # 147
    (2, "resolve_board_effect", {"effect": "intrigue"}),  # 148
    (2, "deploy_troops", {"count": 1}),  # 149
    (2, "resolve_board_effect", {"effect": "troops"}),  # 150
    (2, "finish_agent_turn", {}),  # 151
    (3, "choose_agent_card", {"card_id": "player:3:starter:diplomacy:0"}),  # 152
    (3, "place_agent", {"space_id": "foldspace"}),  # 153
    (3, "resolve_board_effect", {"effect": "foldspace"}),  # 154
    (3, "resolve_faction_influence", {}),  # 155
    (3, "finish_agent_turn", {}),  # 156
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:1"},
    ),  # 157
    (0, "place_agent", {"space_id": "smuggling"}),  # 158
    (0, "recall_board_freighter", {}),  # 159
    (0, "resolve_board_effect", {"effect": "resources"}),  # 160
    (0, "resolve_shipping_reward", {"effect": "dividends"}),  # 161
    (0, "finish_agent_turn", {}),  # 162
    (2, "choose_agent_card", {"card_id": "reserve:arrakis_liaison:5"}),  # 163
    (2, "place_agent", {"space_id": "imperium_research_station"}),  # 164
    (2, "resolve_board_effect", {"effect": "cards"}),  # 165
    (2, "resolve_board_effect", {"effect": "cards"}),  # 166
    (2, "deploy_troops", {"count": 2}),  # 167
    (2, "resolve_board_effect", {"effect": "cards"}),  # 168
    (2, "withdraw_troops", {"count": 1}),  # 169
    (2, "finish_agent_turn", {}),  # 170
    (3, "choose_agent_card", {"card_id": "player:3:starter:signet_ring:0"}),  # 171
    (3, "place_agent", {"space_id": "imperial_basin"}),  # 172
    (3, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 173
    (3, "pay_leader_signet_solari", {}),  # 174
    (3, "play_intrigue", {"card_id": "intrigue:double_cross:0", "option": 0}),  # 175
    (3, "choose_opponent_troop_loss", {"player": 2}),  # 176
    (2, "lose_unit", {"zone": "conflict"}),  # 177
    (3, "finish_agent_turn", {}),  # 178
    (0, "choose_agent_card", {"card_id": "player:0:starter:signet_ring:0"}),  # 179
    (0, "place_agent", {"space_id": "dreadnought"}),  # 180
    (0, "resolve_agent_card_effect", {}),  # 181
    (0, "commission_board_dreadnought", {}),  # 182
    (0, "acquire_board_tech", {}),  # 183
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

# (seat, action id, arguments), in order; the number after each is its index.
LEADERS_PLAN: list[Step] = [
    # Found on the engine as merged with P4 c8a44cfd (seed 4, answer stream 4).
    # The draft: seat 1 Hundro, seat 0 Ilesa, seat 3 Paul, seat 2 Helena.
    (1, "pick_leader", {"leader_id": "viscount_hundro_moritani"}),  # 0
    (0, "pick_leader", {"leader_id": "ilesa_ecaz"}),  # 1
    (3, "pick_leader", {"leader_id": "paul_atreides"}),  # 2
    (2, "pick_leader", {"leader_id": "helena_richese"}),  # 3
    (2, "finish_leader_draft", {}),  # 4
    # Hundro's Intelligence (checkpoint 5: he sees the top two); he keeps Know
    # Their Ways
    (1, "keep_peeked_intrigue", {"instance_id": "intrigue:know_their_ways:0"}),  # 5
    # and Charisma goes back on top; Ilesa sets a card aside (checkpoint 7).
    (
        0,
        "set_aside_leader_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:1"},
    ),  # 6
    # Round 1: seat 2, seat 3, Ilesa's first turn, seat 1 (it plays Know Their
    # Ways), seat 2;
    (2, "choose_agent_card", {"card_id": "player:2:starter:reconnaissance:0"}),  # 7
    (2, "place_agent", {"space_id": "arrakeen"}),  # 8
    (2, "deploy_troops", {"count": 2}),  # 9
    (2, "withdraw_troops", {"count": 1}),  # 10
    (2, "resolve_board_effect", {"effect": "troops"}),  # 11
    (2, "deploy_troops", {"count": 1}),  # 12
    (2, "withdraw_troops", {"count": 1}),  # 13
    (2, "deploy_troops", {"count": 2}),  # 14
    (2, "withdraw_troops", {"count": 1}),  # 15
    (2, "resolve_board_effect", {"effect": "cards"}),  # 16
    (2, "withdraw_troops", {"count": 1}),  # 17
    (2, "deploy_troops", {"count": 2}),  # 18
    (2, "finish_agent_turn", {}),  # 19
    (3, "reveal_turn", {}),  # 20
    (3, "acquire_imperium", {"instance_id": "imperium:guild_administrator:1"}),  # 21
    (3, "finish_reveal", {}),  # 22
    (0, "choose_agent_card", {"card_id": "player:0:starter:dagger:1"}),  # 23
    (0, "place_agent", {"space_id": "tech_negotiation"}),  # 24
    (0, "finish_agent_turn", {}),  # 25
    (1, "reveal_turn", {}),  # 26
    (1, "acquire_imperium", {"instance_id": "imperium:spice_smugglers:1"}),  # 27
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 28
    (1, "play_intrigue", {"card_id": "intrigue:know_their_ways:0", "option": 0}),  # 29
    (1, "finish_reveal", {}),  # 30
    (2, "choose_agent_card", {"card_id": "player:2:starter:signet_ring:0"}),  # 31
    (2, "place_agent", {"space_id": "imperial_basin"}),  # 32
    (2, "set_aside_leader_imperium", {"instance_id": "imperium:fremen_camp:0"}),  # 33
    (2, "deploy_troops", {"count": 1}),  # 34
    (2, "withdraw_troops", {"count": 1}),  # 35
    (2, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 36
    # seat 2's turn ends and Ilesa's second turn starts: her card comes back
    # (checkpoint 38).
    (2, "finish_agent_turn", {}),  # 37
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
    "set_aside_card_id": "",
}
DISCOUNT_PENDING = {
    "shipping_rewards": [],
    "tech_discount": 1,
    "tech_payment": "spice",
    "negotiators_returnable": 0,
}
NEGOTIATOR_PENDING = {
    "shipping_rewards": [],
    "tech_discount": 0,
    "tech_payment": "spice",
    "negotiators_returnable": 1,
}
SHIPPING_PENDING = {**EMPTY_PENDING, "shipping_rewards": [1]}
SECRET_CARD = "intrigue:ambush:1"
KNOWN_BOTTOM = [[0, SECRET_CARD]]
PEEKED = ["intrigue:gruesome_sacrifice:1", "intrigue:imperium_politics:0"]
KEPT = "intrigue:gruesome_sacrifice:1"
TOP_CARD = "intrigue:imperium_politics:0"
HUNDRO_PEEKED = ["intrigue:know_their_ways:0", "intrigue:charisma:0"]
HUNDRO_KEPT = "intrigue:know_their_ways:0"
HUNDRO_TOP = "intrigue:charisma:0"
# The top card of a 55-card deck is 54 above the bottom one (as table 2's).
HUNDRO_KNOWS = {
    "known_intrigue_top": HUNDRO_TOP,
    "known_intrigue_bottom": [[54, HUNDRO_TOP]],
}
SET_ASIDE = "player:0:starter:dune_the_desert_planet:1"
TWIN_SET_ASIDE = "player:0:starter:reconnaissance:0"
# What differs between two games of one table whatever was picked: the game's
# id and log epoch, the play clock, who is online, the doorbell's sequence.
VOLATILE = frozenset({"game_id", "epoch", "clock", "clock_age_ms", "online", "seq"})

IX_TABLE = Table(
    "original + Rise of Ix",
    IX_BODY,
    IX_PLAN,
    {
        25: Checkpoint(
            "Acquire Tech open for seat 2 (Tech Negotiation, Tech Discount 1, spice)",
            {2: {"ix_pending": DISCOUNT_PENDING}},
        ),
        29: Checkpoint(
            "seat 2 put an Intrigue card at the deck's bottom (Sonic Snoopers)",
            {2: {"known_intrigue_bottom": KNOWN_BOTTOM}},
        ),
        160: Checkpoint(
            "seat 0 recalled its Freighter from step 1: the step-1 reward is"
            " owed (seat 2 still knows its bottom card)",
            {
                0: {"ix_pending": SHIPPING_PENDING},
                2: {"known_intrigue_bottom": KNOWN_BOTTOM},
            },
        ),
        184: Checkpoint(
            "Acquire Tech open for seat 0 (the Dreadnought space, spice, one"
            " Negotiator returnable; seat 2 still knows its bottom card)",
            {
                0: {"ix_pending": NEGOTIATOR_PENDING},
                2: {"known_intrigue_bottom": KNOWN_BOTTOM},
            },
        ),
    },
    # Seat 2 knows its bottom card; it ends its turn (30) and seat 3 reveals (31).
    (Handover(shown=29, owner=2, passed=31, viewer=3),),
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
    # Seat 0 knows the top card and holds the other; it ends its turn (86) and
    # seat 1 sends an Agent (87).
    (Handover(shown=84, owner=0, passed=87, viewer=1),),
)
LEADERS_TABLE = Table(
    "original + Rise of Ix, Hundro and Ilesa",
    LEADERS_BODY,
    LEADERS_PLAN,
    {
        5: Checkpoint(
            "Hundro's Intelligence: he sees the Intrigue deck's top two cards while"
            " he keeps one",
            {1: {"peeked_intrigue_ids": HUNDRO_PEEKED}},
        ),
        6: Checkpoint(
            "Hundro kept one and put the other back on top: he knows the top card;"
            " Ilesa is to set a card aside",
            {1: HUNDRO_KNOWS},
            {1: [HUNDRO_KEPT]},
            sealed=[("keep_peeked_intrigue", "instance_id", HUNDRO_KEPT)],
        ),
        7: Checkpoint(
            "Ilesa set a card aside (her turn end held): hers alone, the table"
            " sees one card aside and (비공개) in the log",
            {0: {"set_aside_card_id": SET_ASIDE}, 1: HUNDRO_KNOWS},
            {1: [HUNDRO_KEPT]},
            held=0,
            aside={0: "aside"},
            sealed=[
                ("keep_peeked_intrigue", "instance_id", HUNDRO_KEPT),
                ("set_aside_leader_card", "card_id", SET_ASIDE),
            ],
        ),
        # Between the set-aside and its return, at each turn's end: still hers
        # alone (the twin game below also compares every action in between).
        **{
            done: Checkpoint(
                f"after {what}: Ilesa's card still aside, Hundro still knows the"
                " top card",
                {0: {"set_aside_card_id": SET_ASIDE}, 1: HUNDRO_KNOWS},
                {1: [HUNDRO_KEPT]},
                aside={0: "aside"},
                sealed=[
                    ("keep_peeked_intrigue", "instance_id", HUNDRO_KEPT),
                    ("set_aside_leader_card", "card_id", SET_ASIDE),
                ],
            )
            for done, what in (
                (20, "seat 2's first Agent turn"),
                (23, "seat 3's Reveal turn"),
                (26, "Ilesa's first Agent turn"),
            )
        },
        # Hundro played Know Their Ways in his Reveal turn (29): public since.
        31: Checkpoint(
            "after Hundro's Reveal turn: Ilesa's card still aside, Hundro still"
            " knows the top card",
            {0: {"set_aside_card_id": SET_ASIDE}, 1: HUNDRO_KNOWS},
            aside={0: "aside"},
            sealed=[("set_aside_leader_card", "card_id", SET_ASIDE)],
        ),
        38: Checkpoint(
            "Ilesa's second turn starts: her card is back in her hand, public;"
            " Hundro still knows the top card",
            {1: HUNDRO_KNOWS},
            {0: [SET_ASIDE]},
            public={SET_ASIDE: 0},
            events=[("card_returned_to_hand", {"card_id": SET_ASIDE, "player": 0})],
            aside={0: "returned"},
            sealed=[("set_aside_leader_card", "card_id", SET_ASIDE)],
        ),
    },
    (
        # Hundro picks (5 -> 6) and Ilesa decides at once (the pick opens the
        # round, a reveal, so no turn end is held); Ilesa's set-aside holds her
        # turn end (7), and once it is pressed seat 2, the first player, acts.
        Handover(shown=5, owner=1, passed=6, viewer=0),
        Handover(shown=7, owner=0, passed=7, viewer=2),
    ),
    # Her hand then is Dune, the Desert Planet 1, Dagger 1, Reconnaissance 0
    # and two Convincing Arguments; the plan plays Dagger 1 before 38, so the
    # twin sets Reconnaissance 0 aside (another card, another name).
    Twin(
        index=6,
        step=(0, "set_aside_leader_card", {"card_id": TWIN_SET_ASIDE}),
        owner=0,
        first=7,
        last=37,
        secret=SET_ASIDE,
    ),
)

SECRET_KEYS = (
    "set_aside_card_id",
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
  // Everything the page holds in ``state`` (pick, held and counts too), the
  // catalog aside: Maps and Sets as lists, each object once.
  const wholeState = () => {
    const seen = new WeakSet();
    return JSON.stringify(state, (key, value) => {
      if (key === "catalog" || typeof value === "function") return undefined;
      if (typeof Node !== "undefined" && value instanceof Node) return undefined;
      if (value instanceof Map) return [...value.entries()];
      if (value instanceof Set) return [...value];
      if (value && typeof value === "object") {
        if (seen.has(value)) return undefined;
        seen.add(value);
      }
      return value;
    });
  };
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
    stateText: wholeState(),
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
    setAsideOwn: t("panels.set_aside_own", {card: name(args.setAside)}),
    setAsideOwnHead: head("panels.set_aside_own", {card: mark}),
    setAsideHidden: t("panels.set_aside_hidden"),
    setAsideReturned: t("panels.set_aside_returned"),
  };
}"""

# The heads of the lines a seat's own hidden fields draw: none may be on a page
# that does not show that seat.
HEADS = (
    "shippingHead",
    "techHead",
    "heldHead",
    "bottomHead",
    "topHead",
    "setAsideOwnHead",
)


# The event stream's first message as raw text (the doorbell every page
# listens to), read for at most three seconds.
EVENTS_JS = """async (path) => {
  const controller = new AbortController();
  const response = await fetch(path, {signal: controller.signal});
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let text = "";
  const deadline = Date.now() + 3000;
  while (!text.includes("\\n\\n") && Date.now() < deadline) {
    const chunk = await Promise.race([
      reader.read(),
      new Promise((resolve) => setTimeout(() => resolve(null), 500)),
    ]);
    if (chunk === null) continue;
    if (chunk.done) break;
    text += decoder.decode(chunk.value, {stream: true});
  }
  controller.abort();
  return {status: response.status, text};
}"""

# Each tracked card's marks: its id, its English and Korean names and the
# paths of its English and Korean pictures (the catalog's own entry). A tracked
# Imperium card (Ilesa's set-aside one) is a starter card, whose name and
# picture every seat's own starter cards share: its id alone marks it.
MARKS_JS = """(ids) => ids.map((id) => {
  if (!id.startsWith("intrigue:")) return [id];
  const entry = state.catalog.intrigue[baseId(id)];
  const path = (url) => (url ? url.split("?")[0] : null);
  return [id, entry.name, entry.name_ko || null, path(entry.image),
          path(entry.image_ko)];
})"""

# The whole document, hidden parts included: markup (attributes, pictures) and
# text.
DOCUMENT_JS = """() => [
  document.documentElement.outerHTML, document.documentElement.textContent,
]"""


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
        if fields.get("set_aside_card_id"):
            may[seat].add(fields["set_aside_card_id"])
        for holder, card in fields.get("known_intrigue_held", []):
            may[seat].add(card)
            may[holder].add(card)
    for seat, cards in point.hands.items():
        may[seat].update(cards)
    for cards in may.values():
        cards.update(point.public)
    return may


def tracked_cards(point: Checkpoint) -> list[str]:
    return sorted({card for cards in may_carry(point).values() for card in cards})


def hidden_cards(point: Checkpoint) -> list[str]:
    """The tracked cards some seat may not know (not the public ones)."""
    return [card for card in tracked_cards(point) if card not in point.public]


def shown_bottom(mine: dict[str, Any]) -> list[list[Any]]:
    """The known bottom entries a page names: its bottom line leaves out the
    known top card."""
    top = mine.get("known_intrigue_top", "")
    return [entry for entry in mine.get("known_intrigue_bottom", []) if entry[1] != top]


def word_args(mine: dict[str, Any]) -> dict[str, Any]:
    """``WORDS_JS``'s arguments for a seat's hidden fields ``mine``."""
    pending = mine.get("ix_pending", EMPTY_PENDING)
    bottom = shown_bottom(mine)
    return {
        "steps": ", ".join(str(step) for step in pending["shipping_rewards"]),
        "discount": pending["tech_discount"],
        "payment": pending["tech_payment"],
        "negotiators": pending["negotiators_returnable"],
        "bottom": bottom[0][1] if bottom else "",
        "depth": bottom[0][0] if bottom else 0,
        "top": mine.get("known_intrigue_top", ""),
        "held": [card for _holder, card in mine.get("known_intrigue_held", [])],
        "peeked": mine.get("peeked_intrigue_ids", []),
        "setAside": mine.get("set_aside_card_id", ""),
    }


def drawn_lines(mine: dict[str, Any], words: dict[str, Any]) -> list[str]:
    """Every line a page draws for its own seat's hidden fields ``mine``."""
    pending = mine.get("ix_pending", EMPTY_PENDING)
    return [
        *([words["shipping"]] if pending["shipping_rewards"] else []),
        *([words["tech"]] if pending["tech_payment"] else []),
        *(line for _kind, line in known_lines(mine, words)),
        *([words["held"]] if mine.get("known_intrigue_held") else []),
        *words["peeked"],
        *([words["setAsideOwn"]] if mine.get("set_aside_card_id") else []),
    ]


def known_lines(mine: dict[str, Any], words: dict[str, Any]) -> list[list[str]]:
    """The ``.known-intrigue`` lines a page draws for ``mine``: (kind, text)."""
    return [
        *([["top", words["top"]]] if mine.get("known_intrigue_top") else []),
        *([["bottom", words["bottom"]]] if shown_bottom(mine) else []),
    ]


def marks_found(page, cards: list[str], *texts: str) -> dict[str, list[str]]:
    """Each of ``cards`` whose marks (``MARKS_JS``: id, names, picture paths)
    are found in any of ``texts``, with the marks found."""
    if not cards:
        return {}
    found: dict[str, list[str]] = {}
    for card, *marks in page.evaluate(MARKS_JS, cards):
        hits = [
            mark for mark in (card, *marks) if mark and any(mark in t for t in texts)
        ]
        if hits:
            found[card] = hits
    return found


def document_leaks(page, cards: list[str], state_text: str) -> dict[str, list[str]]:
    """What ``page``'s document holds of ``cards``, cards it may not know: the
    marks of each found in its markup or text. A public copy of the same card
    would show the same name and picture, so any copy its state names is
    listed beside a find, to say why."""
    if not cards:
        return {}
    html, text = page.evaluate(DOCUMENT_JS)
    leaks = marks_found(page, cards, html, text)
    for card, hits in leaks.items():
        kind = card.rsplit(":", 1)[0]
        copies = set(re.findall(re.escape(kind) + r":\d+", state_text)) - {card}
        hits.extend(f"public copy {copy}" for copy in sorted(copies))
    return leaks


def steady(payload: Any) -> Any:
    """``payload`` without its ``VOLATILE`` keys, at any depth."""
    if isinstance(payload, dict):
        return {k: steady(v) for k, v in payload.items() if k not in VOLATILE}
    if isinstance(payload, list):
        return [steady(value) for value in payload]
    return payload


def first_difference(first: Any, second: Any, path: str = "") -> str | None:
    """Where two payloads first differ, or None."""
    if isinstance(first, dict) and isinstance(second, dict):
        for key in sorted(set(first) | set(second)):
            if key not in first or key not in second:
                return f"{path}.{key}: in one game only"
            found = first_difference(first[key], second[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(first, list) and isinstance(second, list):
        if len(first) != len(second):
            return f"{path}: {len(first)} vs {len(second)} items"
        for index, (one, two) in enumerate(zip(first, second, strict=True)):
            found = first_difference(one, two, f"{path}[{index}]")
            if found:
                return found
        return None
    return None if first == second else f"{path}: {first!r:.80} vs {second!r:.80}"


def pending_fields(payload: Any, path: str = "") -> list[tuple[str, Any]]:
    """Every ``ix_pending`` field (``EMPTY_PENDING``'s keys) anywhere in
    ``payload``, as (path, value), sorted by path."""
    found: list[tuple[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            where = f"{path}.{key}" if path else key
            if key in EMPTY_PENDING:
                found.append((where, value))
            found.extend(pending_fields(value, where))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(pending_fields(value, f"{path}[{index}]"))
    return sorted(found, key=lambda entry: entry[0])


def reader_payloads(page, game_id: str, seat: int | None) -> dict[str, Any]:
    """Every payload ``page`` fetches about the game with its own cookie, as
    (status, body) by name: a seat's own view, snapshot (with the log tail),
    log and actions; the spectator's summary; both, the seatless snapshot and
    the VP ledger."""
    game = f"/games/{game_id}"
    paths = (
        {
            "view": f"{game}/seats/{seat}/view",
            "snapshot": f"{game}/snapshot?seat={seat}",
            "log": f"{game}/log?seat={seat}",
            "actions": f"{game}/seats/{seat}/actions",
        }
        if seat is not None
        else {"summary": game}
    )
    paths |= {"seatless": f"{game}/snapshot", "ledger": f"{game}/vp-ledger"}
    return {name: api(page, "GET", path) for name, path in paths.items()}


def events_text(page, game_id: str) -> tuple[int, str]:
    """The raw first message of the game's event stream, fetched by ``page``."""
    result = page.evaluate(EVENTS_JS, f"/games/{game_id}/events")
    return result["status"], result["text"]


def log_events(log: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        event
        for entry in log["entries"]
        if not entry.get("undone")
        for event in entry.get("events", [])
    ]


def check_views(
    label: str,
    pages: dict[int, Any],
    spectator,
    game_id: str,
    point: Checkpoint,
    revision: int,
) -> None:
    """The HTTP side: each seat's own payloads, the spectator's, and the
    refusals."""
    may = may_carry(point)
    secrets = tracked_cards(point)
    for seat, page in pages.items():
        answers = reader_payloads(page, game_id, seat)
        statuses = {name: status for name, (status, _) in answers.items()}
        status, stream = events_text(page, game_id)
        statuses["events"] = status
        ok = all(status == 200 for status in statuses.values()) and bool(stream)
        check.ok(
            ok,
            f"{label}: seat {seat} reads its own view, snapshot, log and actions,"
            " the seatless snapshot, the VP ledger and the event stream",
            statuses,
        )
        if not ok:
            continue
        data = {name: body for name, (_, body) in answers.items()}
        view, snapshot = data["view"], data["snapshot"]
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
        for card in point.hands.get(seat, []):
            zone = "intrigue_cards" if card.startswith("intrigue:") else "hand"
            check.ok(
                card in view["private"][zone],
                f"{label}: seat {seat}'s own view holds {card} in private.{zone}",
                view["private"][zone],
            )
        for card, holder in point.public.items():
            shown = view["players"][holder]["hand_public"]
            check.ok(
                card in shown,
                f"{label}: seat {seat}'s view shows {card} in seat {holder}'s"
                " public hand",
                shown,
            )
        events = log_events(data["log"])
        for kind, payload in point.events:
            check.ok(
                any(
                    event["kind"] == kind
                    and all(event["payload"].get(k) == v for k, v in payload.items())
                    for event in events
                ),
                f"{label}: seat {seat}'s log holds the event {kind} {payload}",
            )
        own = expected["ix_pending"]
        fields = pending_fields(data)
        wanted = sorted(
            (f"{where}.private.ix_pending.{key}", value)
            for where in ("view", "snapshot.view")
            for key, value in own.items()
        )
        check.ok(
            fields == wanted,
            f"{label}: seat {seat}'s payloads carry the ix_pending fields only in"
            " its own private block"
            + (", with its pending choice" if own != EMPTY_PENDING else ", empty"),
            [entry for entry in fields if entry not in wanted][:6],
        )
        text = json.dumps(data, ensure_ascii=False) + stream
        for card in secrets:
            check.ok(
                (card in text) == (card in may[seat]),
                f"{label}: seat {seat}'s payloads (view, snapshot, log, actions,"
                " the seatless snapshot, the VP ledger, the event stream)"
                + (" name" if card in may[seat] else " do not name")
                + f" {card}",
            )
        unknown = [card for card in secrets if card not in may[seat]]
        named = marks_found(page, unknown, text)
        check.ok(
            not named and not any(key in stream for key in SECRET_KEYS),
            f"{label}: seat {seat}'s payloads hold no English or Korean name or"
            f" picture of {unknown or 'a card'} it may not know, and its event"
            " stream no hidden field",
            named,
        )
        for action_id, key, value in point.sealed:
            entries = [
                entry
                for entry in data["log"]["entries"]
                if entry.get("action_id") == action_id and not entry.get("undone")
            ]
            mine = len(entries) == 1 and entries[0]["actor"] == seat
            check.ok(
                len(entries) == 1
                and entries[0]["arguments"].get(key) == (value if mine else "(비공개)"),
                f"{label}: seat {seat}'s log shows {action_id}'s {key} as "
                + (value if mine else "(비공개)"),
                [entry["arguments"] for entry in entries],
            )
    answers = reader_payloads(spectator, game_id, None)
    statuses = {name: status for name, (status, _) in answers.items()}
    status, stream = events_text(spectator, game_id)
    statuses["events"] = status
    # The VP ledger opens to a seat cookie, or to the room link once the game
    # has finished; what it says when it opens is looked at all the same.
    data = {name: body for name, (status, body) in answers.items() if status == 200}
    text = json.dumps(data, ensure_ascii=False) + stream
    hidden = hidden_cards(point)
    named = marks_found(spectator, hidden, text)
    # A seatless spectator gets no table on a remote server (the seatless
    # snapshot has no view; the summary names the seats only), so a card that
    # turned public (point.public) reaches it nowhere either.
    check.ok(
        statuses["summary"] == statuses["seatless"] == statuses["events"] == 200
        and statuses["ledger"] in (200, 403)
        and data["summary"]["revision"] == revision
        and data["seatless"].get("view") is None
        and not any(key in text for key in SECRET_KEYS)
        and not pending_fields(data)
        and not any(card in text for card in tracked_cards(point))
        and not named,
        f"{label}: the spectator's summary, seatless snapshot, VP ledger and event"
        " stream carry no view, no hidden field and no tracked card (id, name or"
        " picture)",
        (statuses, [key for key in SECRET_KEYS if key in text], named),
    )
    readers = {
        **{f"seat {seat}": page for seat, page in pages.items()},
        "spectator": spectator,
    }
    refused: list[str] = []
    for owner in range(4):
        for name, page in readers.items():
            if name == f"seat {owner}":
                continue
            for path in (
                f"/games/{game_id}/seats/{owner}/view",
                f"/games/{game_id}/seats/{owner}/actions",
                f"/games/{game_id}/snapshot?seat={owner}",
                f"/games/{game_id}/log?seat={owner}",
            ):
                status, _ = api(page, "GET", path)
                if status != 403:
                    refused.append(f"{name} {path}: HTTP {status}")
    check.ok(
        not refused,
        f"{label}: every other seat and the spectator is refused (403) each seat's"
        " view, actions, snapshot and log",
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
        bottom = shown_bottom(mine)
        held = mine.get("known_intrigue_held", [])
        peeked = mine.get("peeked_intrigue_ids", [])
        words = page.evaluate(WORDS_JS, word_args(mine))
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
        expected_known = known_lines(mine, words)
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
        unknown = [card for card in secrets if card not in may[seat]]
        leaks = document_leaks(page, unknown, shown["stateText"])
        check.ok(
            not leaks,
            f"{tag}: seat {seat}'s document holds no id, name or picture of"
            f" {unknown or 'a card'} it may not know",
            leaks,
        )
        # Ilesa's set-aside, on every seat panel of this page: her own line on
        # her own page, "one card set aside" on the others, "came back this
        # turn" on all once it is back; nothing on any other panel.
        wrong = []
        for holder in range(4):
            panel = shown["panels"][str(holder)]
            flag = point.aside.get(holder)
            want = {
                "setAsideOwnHead": flag == "aside" and holder == seat,
                "setAsideHidden": flag == "aside" and holder != seat,
                "setAsideReturned": flag == "returned",
            }
            wrong += [
                f"seat {holder}'s panel: {key} {'missing' if expected else 'shown'}"
                for key, expected in want.items()
                if (words[key] in panel) != expected
            ]
        if flag_own := (point.aside.get(seat) == "aside"):
            if words["setAsideOwn"] not in own_panel:
                wrong.append(f"own panel lacks {words['setAsideOwn']}")
        check.ok(
            not wrong,
            f"{tag}: seat {seat}'s page shows the set-aside flags"
            + (f" {point.aside}" if point.aside else ": none")
            + (" with its own card" if flag_own else ""),
            wrong,
        )
    hidden = hidden_cards(point)
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
            "setAside": "",
        },
    )
    lines = [words[key] for key in HEADS]
    check.ok(
        shown["mine"] == []
        and shown["viewer"] is None
        and shown["known"] == []
        and shown["pending"] is None
        and not any(line in shown["body"] for line in lines)
        and not any(card in shown["stateText"] for card in hidden),
        f"{tag}: the spectator's page holds no view, shows none of the lines and"
        " holds no hidden tracked card",
        {key: shown[key] for key in ("mine", "viewer", "known", "pending")},
    )
    leaks = document_leaks(spectator, hidden, shown["stateText"])
    check.ok(
        not leaks,
        f"{tag}: the spectator's document holds no id, name or picture of {hidden}",
        leaks,
    )


def hand_over(base: str, browser, table: Table) -> None:
    """The hot-seat table: on an open server one page plays every seat and
    shows whichever must act (``session.js`` ``pickViewSeat``). At each of the
    table's hand-overs it shows the owner and draws its hidden lines; once the
    owner's turn is over (its turn-end press, when one is held) it shows the
    next seat, which holds nothing hidden of its own then, and must hold none
    of the owner's lines or cards."""
    names = ", ".join(f"{h.owner} -> {h.viewer}" for h in table.handovers)
    print(f"[{table.name}: hot seat] seats {names} on one page")
    context, page, recorder = open_context(browser, "hotseat", VIEWPORT)
    try:
        hot_seat(base, table, page, {"hotseat": (page, recorder)})
    finally:
        context.close()


def hot_seat(base: str, table: Table, page, table_page) -> None:
    page.goto(f"{base}/")
    wait_for_setup(page)
    status, created = api(page, "POST", "/games", table.body)
    if status != 200:
        raise PlanMissed(f"the open server refused the pinned table: {created}")
    game_id = created["game_id"]
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_selector("#game-screen:not([hidden])")
    check.ok(
        page.evaluate("state.server.access") == "open"
        and page.evaluate("state.me.seats") == [0, 1, 2, 3],
        "the hot-seat page plays all four seats",
    )
    pages = dict.fromkeys(range(4), page)
    done = 0
    for handover in table.handovers:
        point = table.checkpoints[handover.shown]
        unknown = [
            card
            for card in tracked_cards(point)
            if card not in may_carry(point)[handover.viewer]
        ]
        mine = point.private[handover.owner]
        while done < handover.passed:
            take_plan_step(table, pages, game_id, done)
            done += 1
            if done != handover.shown:
                continue
            check.ok(
                converge(table_page, game_id, f"hot seat {done}", timeout=15),
                "the hot-seat page has caught up to the server",
            )
            words = page.evaluate(WORDS_JS, word_args(mine))
            shown = page.evaluate(PAGE_JS)
            lines = drawn_lines(mine, words)
            check.ok(
                shown["viewer"] == handover.owner
                and bool(lines)
                and all(line in shown["body"] for line in lines),
                f"{table.name}: after {done} the hot-seat page shows seat"
                f" {handover.owner} and draws its hidden lines",
                (shown["viewer"], lines, shown["body"][:300]),
            )
        hand_on(table, page, table_page, game_id, handover)
        for language in ("ko", "en"):
            page.evaluate(f"setLanguage('{language}')")
            settled(page)
            words = page.evaluate(WORDS_JS, word_args(mine))
            shown = page.evaluate(PAGE_JS)
            heads = [words[key] for key in HEADS]
            check.ok(
                shown["viewer"] == handover.viewer
                and shown["known"] == []
                and not any(head in shown["body"] for head in heads)
                and not any(card in shown["stateText"] for card in unknown),
                f"{table.name} [{language}]: the hot-seat page now shows seat"
                f" {handover.viewer}, with none of seat {handover.owner}'s lines"
                " and no tracked card in its state",
                (shown["viewer"], shown["known"]),
            )
            leaks = document_leaks(page, unknown, shown["stateText"])
            check.ok(
                bool(unknown) and not leaks,
                f"{table.name} [{language}]: seat {handover.viewer}'s document holds"
                f" no trace of {unknown}",
                leaks,
            )
        page.evaluate("setLanguage('ko')")
        settled(page)


def hand_on(table: Table, page, table_page, game_id: str, handover: Handover) -> None:
    """End the owner's turn (pressing its held turn end, if any): the viewer
    must decide then, and the page catch up."""
    _, summary = api(page, "GET", f"/games/{game_id}")
    held = summary["confirmation"]
    if held == handover.owner:
        status, _ = api(
            page,
            "POST",
            f"/games/{game_id}/confirm",
            {
                "seat": handover.owner,
                "revision": summary["revision"],
                "undo_count": summary["undo_count"],
            },
        )
        if status != 200:
            raise PlanMissed(f"{table.name}: seat {held}'s turn end: HTTP {status}")
        _, summary = api(page, "GET", f"/games/{game_id}")
    decision = summary["decision"]
    deciding = decision["owner"] if decision else None
    if summary["confirmation"] is not None or deciding != handover.viewer:
        raise PlanMissed(
            f"{table.name}: after {handover.passed} actions seat {handover.viewer}"
            f" should decide, not {decision} (turn end held:"
            f" {summary['confirmation']})"
        )
    check.ok(
        converge(table_page, game_id, f"hot seat {handover.passed}", timeout=15),
        f"seat {handover.owner}'s turn is over"
        + (" (its turn end pressed)" if held == handover.owner else "")
        + f", seat {handover.viewer} decides, and the page catches up",
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
        summary["confirmation"] == point.held,
        "no turn end waits for a press at the checkpoint"
        if point.held is None
        else f"seat {point.held}'s turn end is held at the checkpoint",
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


def play_table(base: str, browser, table: Table) -> dict[int, dict[str, Any]]:
    """Play ``table`` on its own five contexts, checking it at its
    checkpoints; return, for each action of its twin's range, the payloads
    (``steady``) of every seat but the twin's owner and of the spectator."""
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
    try:
        return replay_table(base, table, pages, spectator, all_pages, contexts)
    finally:
        for context in [*contexts.values(), spectator_context]:
            context.close()


def replay_table(
    base: str,
    table: Table,
    pages: dict[int, Any],
    spectator,
    all_pages: dict[str, tuple[Any, Any]],
    contexts: dict[int, Any],
) -> dict[int, dict[str, Any]]:
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
    spectator_context = spectator.context
    check.ok(
        holds_only_its_own_cookie(contexts, spectator_context, game_id),
        "each context holds its own seat cookie and no other",
    )

    print(f"[{table.name}] replaying {len(table.plan)} pinned actions")
    twin = table.twin
    captured: dict[int, dict[str, Any]] = {}
    for index in range(len(table.plan)):
        take_plan_step(table, pages, game_id, index)
        done = index + 1
        if twin is not None and twin.first <= done <= twin.last:
            readers = {
                **{f"seat {seat}": (page, seat) for seat, page in pages.items()},
                "spectator": (spectator, None),
            }
            captured[done] = {
                name: steady(
                    {
                        key: [status, body]
                        for key, (status, body) in reader_payloads(
                            page, game_id, seat
                        ).items()
                    }
                )
                for name, (page, seat) in readers.items()
                if seat != twin.owner
            }
        if done in table.checkpoints:
            run_checkpoint(table, done, pages, spectator, game_id, all_pages)
        elif done % 20 == 0:
            print(f"  .. {done} actions")
    _, summary = api(pages[0], "GET", f"/games/{game_id}")
    check.ok(
        summary["revision"] > 0 and not summary["finished"],
        f"{table.name}: the plan ended inside the game, on its last checkpoint",
    )
    return captured


def compare_twin(base: str, browser, table: Table, first: dict[int, Any]) -> None:
    """Play ``table``'s twin game and compare it with the first one."""
    twin = table.twin
    assert twin is not None
    plan = list(table.plan)
    plan[twin.index] = twin.step
    second = play_table(
        base,
        browser,
        replace(table, name=f"{table.name}, twin", plan=plan, checkpoints={}),
    )
    leaks = [
        f"after {done}: {reader}"
        for done, readers in sorted(first.items())
        for reader, payload in readers.items()
        if twin.secret in json.dumps(payload)
    ]
    span = range(twin.first, twin.last + 1)
    check.ok(
        sorted(first) == list(span) and not leaks,
        f"{table.name}: no payload of another seat or of the spectator names"
        f" {twin.secret} at any action from {twin.first} to {twin.last}",
        leaks[:6],
    )
    differences = [
        f"after {done}, {reader}: {found}"
        for done in span
        for reader in first.get(done, {})
        if (found := first_difference(first[done][reader], second[done][reader]))
    ]
    check.ok(
        sorted(second) == list(span) and not differences,
        f"{table.name}: whichever card seat {twin.owner} picks ({twin.secret} or"
        f" {twin.step[2]}), every payload of the other seats and of the spectator"
        f" is the same at every action from {twin.first} to {twin.last}",
        differences[:6],
    )


TABLES = (IX_TABLE, CEREMONY_TABLE, LEADERS_TABLE)


def check_original_refuses_immortality(base: str, browser) -> None:
    """The original game takes no Immortality until stage P7, which is why the
    Imperium Ceremony table is an Uprising one."""
    print("[5] the original game still does not take Immortality (stage P7)")
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
            # A table whose plan is missed fails alone; the others still run.
            captured = {}
            for number, table in enumerate(TABLES, start=1):
                print(f"[{number}] {table.name}")
                try:
                    captured[table.name] = play_table(base, browser, table)
                except PlanMissed as missed:
                    check.ok(False, f"the pinned plan was missed: {missed}")
            print("[4] the twin games")
            for table in TABLES:
                if table.twin is None or table.name not in captured:
                    continue
                try:
                    compare_twin(base, browser, table, captured[table.name])
                except PlanMissed as missed:
                    check.ok(False, f"the twin's pinned plan was missed: {missed}")
            check_original_refuses_immortality(base, browser)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        log_text = server_log.read_text()
        bad = "Traceback" in log_text or "ERROR" in log_text
        check.ok(not bad, f"no server errors (see {SERVER_LOG_COPY})")
        print("[6] the hot-seat hand-overs, on an open server")
        with server() as (open_base, open_log):
            for table in TABLES:
                try:
                    hand_over(open_base, browser, table)
                except PlanMissed as missed:
                    check.ok(False, f"the pinned plan was missed: {missed}")
            log_text = open_log.read_text()
            check.ok(
                "Traceback" not in log_text and "ERROR" not in log_text,
                "no errors on the open server",
                log_text[-2000:],
            )
    check.finish()


if __name__ == "__main__":
    main()
