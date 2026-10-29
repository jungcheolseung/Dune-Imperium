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

Step [10] plays the twins of tables 3, 4 and 8 (``Table.twin``): the same game
where Ilesa sets another card aside, or where seat 2 puts its other Intrigue
card under the deck. At every action from her set-aside to the action before
the card turns public (from the put to the table's end), every payload of the
other three seats and of the spectator, their event stream's message and their
page's whole state (catalog aside, once every page has caught up) must be the
same in both games (the game id, clock and presence aside), and none names the
picked card's id: so neither the card nor its name, base id or picture reaches
them, even by a count.

Then, step [12], hot-seat hand-overs on an open server, where one page plays
every seat (``Table.handovers``: one each for tables 1, 2 and 8, Hundro to
Ilesa and Ilesa to the first player on table 3): the page shows the owner and
draws its hidden lines, the owner's turn ends, and the page that now shows the
next seat holds none of the owner's lines or cards (the view replaced, the
containers emptied).

Nine tables, each a fresh game on the same server:

1. Original game + Rise of Ix, four human seats (seed 23):
   a. ``ix_pending.shipping_rewards``: seat 0 recalls its Freighter from
      Shipping step 1; the step-1 reward is owed.
   b. ``ix_pending.tech_discount`` / ``tech_payment``: seat 2 sends an Agent
      to Tech Negotiation, and its Acquire Tech (Tech Discount 1, spice) is
      open; it takes Sonic Snoopers.
   c. ``known_intrigue_bottom``: seat 2 trashes Sonic Snoopers to put an
      Intrigue card at the Intrigue deck's bottom, which only it then knows
      (to the plan's end).
   d. ``ix_pending.negotiators_returnable``: seat 3 sends an Agent to Tech
      Negotiation holding a Negotiator, and its Acquire Tech (Tech Discount 1,
      spice, one Negotiator returnable) is open.
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
   Moritani and seat 0 Ilesa Ecaz (seat 2 Armand Ecaz, seat 3 Tessia Vernius):
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
   Checked also after each turn in between (20, 24, 27, 30). Her card is one
   of her starter cards, whose name and picture every seat's own starter
   cards share, so in one game it is looked for by its id; step [10]'s twin
   game covers its name, base id and picture.
4. The same with seed 1, where Ilesa is the first player (seat 0): she sets a
   card aside and her first turn starts at once, its start still open (P4
   2a8bc1ea); she reveals in that turn, and the card joins her revealed cards
   (``in_play``), public to every seat ("라운드 첫 turn에 Reveal을 하면 따로 둔
   카드를 공개 카드에 더한다", docs/rules/rise-of-ix.md 9.1). Its twin covers
   the set-aside moment.
5. Original game + Rise of Ix, seed 246 (seed 78 stopped the engine there
   until P4 b806b3db fixed it): seat 2 takes Disposal Facility with
   Machine Culture in its Reveal turn and both of its trashes are offered; it
   trashes a card with the acquire box, and the Reveal ability's trash is
   still offered. Nothing is hidden there; it stays as a regression table.
6. Original game + Rise of Ix, seed 9: seat 3 plays Strategic Push in the
   Combat; its pledge (``strategic_push_solari``, public since P4 f6d3e996)
   shows on its panel to every seat in both languages; it wins alone and its
   window offers the pledge's row ("승자의 창", docs/rules/rise-of-ix.md 12),
   which pays the 2 Solari and spends the pledge; once the Combat is over no
   panel shows one.
7. The same, seed 81: seat 3 plays Strategic Push and seat 0 wins; seat 3's
   pledge stays on its panel through seat 0's window and is gone once the
   Combat is cleaned up.
8. Original game + Rise of Ix, seed 59: seat 2 plays Court Intrigue holding
   two Intrigue cards and puts one under the Intrigue deck ("상대에게 보이지
   않는다", docs/rules/rise-of-ix.md 9.1; rise-of-ix.md 13, OQ-149): the rows
   naming the cards are its own, then ``known_intrigue_bottom`` is its own
   and the log shows the others ``(비공개)``; it draws the top card (its own
   step, OQ-106) and keeps knowing the bottom one through its turn's end. Its
   twin puts the other card under the deck.
9. Original game + Rise of Ix, seed 90: seat 0 plays Weirding Way and takes
   the extra turn ("You may take another turn immediately after this one"):
   every page's log shows the line in its language; when the turn ends the
   same seat's next turn opens at once (the snapshot's decision and the active
   seat panel are seat 0's, no card of that turn yet); it reveals in it, and
   the log shows seat 0's two turns as two cards in a row before seat 1's
   turn.

Tessia Vernius' Snooper reward 1 outside her turn (the ``OPTIONAL_DISCARD``
window over her hand) is covered by ``tests/server/test_tessia_window_remote.py``
instead: a real game played to her Combat reward, where she is given a hand
(the one change outside the rules) and takes the Influence that opens the
window over the reward frame, read over a live socket through four seat
cookies and a seatless client, the event stream included (her hand and rows
to her alone, twins with another starter card or without CHOAM Delegate, the
discard public only after it, the Delegate's Unload before the spice, the
reward going on). The page draws it as every other ``OPTIONAL_DISCARD``
window, whose browser side the e2e scripts cover. A real table does not
reach it here: in 61 random draft games her first token
fell in her own turn (a row, not the window) or in Combat with an empty hand
(no window, rise-of-ix.md 9.3); the only path is a Plot Intrigue that draws
(Glimpse the Path, Ixian Probe, Water of Life) played in her Reveal turn, then
a Combat Influence reaching her first token. About 200 steered games
(``find7.py``) did not get there: in the 40 counted, she held such a card in
4 but never played it in her Reveal turn.

Not reached, and named here so the gap stays visible: POST /games refuses
``base_game: "imperium"`` with ``immortality`` ("the original game takes
immortality from stage P7") and Rise of Ix on Uprising (also P7), so no table
combines the original game, Rise of Ix and Immortality; that is why table 2 is
Uprising. Step [11] asserts that the original game still refuses Immortality.

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
  48): seed 4 and the same answer stream got there again, in 184 actions.
  After P4 da3cd535 (Strategic Push joined the deck; the plan missed at step
  14) seed 4 no longer gets there and seed 48 with answer stream 48 * 1000 +
  1, the other playout of the first search, does; ``plan_t1.py`` plays it on
  until another seat decides (203 actions). After P4 e3cac948 (seven Ix
  Imperium cards joined the deck; the plan missed at step 3) one playout of
  seeds 1-40 got there, seed 23 with answer stream 23 * 1000 + 2 (its known
  bottom card now comes before the returnable Negotiator, so that checkpoint
  holds both); ``plan_t1b.py`` plays it on until another seat decides and
  prints every change of a hidden field: ``IX_PLAN`` (221 actions).
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
  first-turn Reveal, with Ilesa not the first player. ``show4.py`` prints
  every seat's private block step by step. Re-run after P4 6c6b747e put
  Tessia in the draft pool (the offers changed; the plan missed at step 4):
  seed 4 again, now 33 actions, ``LEADERS_PLAN``.
- Table 4: ``find5.py`` gives the first player's seat Ilesa and makes her
  reveal in her first turn; seed 1 (answer stream 1000), ``FIRST_PLAN``.
- Table 5: ``search.py``'s playout of seed 78 (answer stream 78 * 1000 + 1),
  the repro of the Disposal Facility stop (``crash_repro.py``; 177 actions).
  After P4 e3cac948 (the plan missed at step 7) the same weights found no
  game with both trashes in 180 playouts (``find11.py``): the tile's two
  trashes meet only when it is bought in a Reveal turn, which only Machine
  Culture's Plot does. ``find12.py`` plays Machine Culture in a Reveal turn
  only, takes Disposal Facility and its box's trash whenever offered and
  favours Intrigue rows; none of seeds 1-150 got there, and the runs over
  seeds 151-400 were stopped at their first hit, seed 246 (246 * 1000 + 2);
  ``pin_df.py`` adds the box's trash:
  ``DISPOSAL_PLAN`` (304 actions).
- Tables 6 and 7: ``find9.py`` plays Strategic Push at the first Combat
  Intrigue chance and deploys every troop of its holder from then on;
  ``find9_lose.py`` keeps the playouts where it does not win. Re-run after P4
  e3cac948 (the plans missed at steps 38 and 113): seed 9 (answer stream
  9 * 1000) won alone, seed 81 (81 * 1000 + 1) lost to a sole winner (seed 56
  lost to a tie for first instead). ``pin_sp.py`` plays each on into the next
  round: ``STRATEGIC_PLAN`` (62 actions), ``LOST_PUSH_PLAN`` (167).
- Tables 8 and 9: ``find10.py`` buys Court Intrigue and Weirding Way whenever
  offered, plays Court Intrigue once its seat holds two Intrigue cards and
  Weirding Way at once, puts a random card under the deck and takes the extra
  turn; over seeds 1-100 (three answer streams each) seed 59 (59 * 1000 + 1)
  is the shortest Court Intrigue game with two cards to choose from, and seed
  90 (90 * 1000 + 2) the shortest extra turn. ``show10b.py`` cuts each and
  prints every seat's private block at the checkpoints; ``twin10.py`` replays
  the Court Intrigue twin's plan through the server layer.
- ``emit_plan.py`` / ``emit_plan2.py`` / ``emit_plans7.py`` wrote the plans out,
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
    # Cards every seat now knows, by (seat, public zone): a returned set-aside
    # card in that seat's ``hand_public``, or one revealed in its ``in_play``.
    # Every seat's view has it there, and every seat's page state names it.
    public: dict[str, tuple[int, str]] = field(default_factory=dict)
    # What a seat's own actions response must offer at the checkpoint: an
    # action id, or (action id, the arguments the row must carry).
    offered: dict[int, list[str | tuple[str, dict[str, Any]]]] = field(
        default_factory=dict
    )
    # Strategic Push's public pledge (``strategic_push_solari``) by seat; every
    # other seat's is 0. Every view says so and every page draws the line on
    # that seat's panel only.
    pledges: dict[int, int] = field(default_factory=dict)
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
    # The seat whose turn it is, if pinned: the decision owner in every seat's
    # snapshot, and the one ``active`` seat panel on every page.
    turn: int | None = None
    # The open turn's played cards (``turn_card_ids``), if pinned: the same in
    # every seat's view, and as many "this turn" chips on every page.
    turn_cards: list[str] | None = None
    # Event kinds whose log line every page shows, in the page's language
    # (``EVENT_LABELS`` through ``phraseText``).
    log_lines: list[str] = field(default_factory=list)
    # The seats of the log's last turn cards, oldest first, on every page.
    log_tail: list[int] = field(default_factory=list)


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
    "game_seed": 23,
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
# Table 4: the same with seed 1, where Ilesa is the first player.
FIRST_BODY = {**LEADERS_BODY, "game_seed": 1}
# Table 5: original + Rise of Ix without the draft, seed 246 (Disposal Facility).
DISPOSAL_BODY = {**IX_BODY, "game_seed": 246}
# Table 6: the same, seed 9 (Strategic Push, won); table 7, seed 81 (lost).
STRATEGIC_BODY = {**IX_BODY, "game_seed": 9}
LOST_PUSH_BODY = {**IX_BODY, "game_seed": 81}
# Table 8: the same, seed 59 (Court Intrigue); table 9, seed 90 (Weirding Way).
COURT_BODY = {**IX_BODY, "game_seed": 59}
WEIRDING_BODY = {**IX_BODY, "game_seed": 90}

# (seat, action id, arguments), in order; the number after each is its index
# (the checkpoints count the actions applied).
IX_PLAN: list[Step] = [
    (3, "choose_masterstroke_faction", {"faction": "emperor"}),  # 0
    (3, "choose_masterstroke_faction", {"faction": "fremen"}),  # 1
    (1, "reveal_turn", {}),  # 2
    (1, "finish_reveal", {}),  # 3
    (2, "choose_agent_card", {"card_id": "player:2:starter:reconnaissance:0"}),  # 4
    (2, "place_agent", {"space_id": "arrakeen"}),  # 5
    (2, "resolve_board_effect", {"effect": "troops"}),  # 6
    (2, "deploy_troops", {"count": 3}),  # 7
    (2, "resolve_board_effect", {"effect": "cards"}),  # 8
    (2, "finish_agent_turn", {}),  # 9
    (3, "reveal_turn", {}),  # 10
    (3, "acquire_imperium", {"instance_id": "imperium:arrakis_recruiter:1"}),  # 11
    (3, "acquire_imperium", {"instance_id": "imperium:sayyadina:0"}),  # 12
    (3, "finish_reveal", {}),  # 13
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:0"},
    ),  # 14
    (0, "place_agent", {"space_id": "smuggling"}),  # 15
    (0, "advance_board_freighter", {}),  # 16
    (0, "resolve_board_effect", {"effect": "resources"}),  # 17
    (0, "finish_agent_turn", {}),  # 18
    (2, "reveal_turn", {}),  # 19
    (2, "finish_reveal", {}),  # 20
    (0, "choose_agent_card", {"card_id": "player:0:starter:reconnaissance:0"}),  # 21
    (0, "place_agent", {"space_id": "carthag"}),  # 22
    (0, "deploy_troops", {"count": 1}),  # 23
    (0, "resolve_board_effect", {"effect": "intrigue"}),  # 24
    (0, "resolve_board_effect", {"effect": "troops"}),  # 25
    (0, "deploy_troops", {"count": 1}),  # 26
    (0, "deploy_troops", {"count": 1}),  # 27
    (0, "finish_agent_turn", {}),  # 28
    (0, "reveal_turn", {}),  # 29
    (0, "finish_reveal", {}),  # 30
    (2, "pass_combat_intrigue", {}),  # 31
    (0, "play_intrigue", {"card_id": "intrigue:master_tactician:2", "option": 0}),  # 32
    (0, "pass_combat_intrigue", {}),  # 33
    (2, "pass_combat_intrigue", {}),  # 34
    (0, "pass_combat_intrigue", {}),  # 35
    (0, "resolve_combat_reward_icon", {"effect": "resources"}),  # 36
    (0, "resolve_combat_reward_icon", {"effect": "freighter"}),  # 37
    # Round 1: seat 0 recalls its Freighter from step 1 (checkpoint 39: the
    # step-1 reward is owed).
    (0, "recall_freighter", {}),  # 38
    (0, "resolve_shipping_reward", {"effect": "spice"}),  # 39
    (0, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 40
    (2, "resolve_combat_reward_icon", {"effect": "resources"}),  # 41
    (2, "reveal_turn", {}),  # 42
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 43
    (2, "acquire_imperium", {"instance_id": "imperium:spice_hunter:0"}),  # 44
    (2, "finish_reveal", {}),  # 45
    (3, "choose_agent_card", {"card_id": "player:3:starter:diplomacy:0"}),  # 46
    (3, "place_agent", {"space_id": "foldspace"}),  # 47
    (3, "resolve_board_effect", {"effect": "foldspace"}),  # 48
    (3, "resolve_faction_influence", {}),  # 49
    (3, "finish_agent_turn", {}),  # 50
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:1"},
    ),  # 51
    (0, "place_agent", {"space_id": "smuggling"}),  # 52
    (0, "resolve_board_effect", {"effect": "resources"}),  # 53
    (0, "finish_agent_turn", {}),  # 54
    (1, "reveal_turn", {}),  # 55
    (1, "acquire_imperium", {"instance_id": "imperium:spice_smugglers:1"}),  # 56
    (1, "finish_reveal", {}),  # 57
    (3, "choose_agent_card", {"card_id": "player:3:starter:signet_ring:0"}),  # 58
    (3, "place_agent", {"space_id": "tech_negotiation"}),  # 59
    (3, "finish_agent_turn", {}),  # 60
    (0, "choose_agent_card", {"card_id": "player:0:starter:diplomacy:0"}),  # 61
    (0, "place_agent", {"space_id": "wealth"}),  # 62
    (0, "resolve_faction_influence", {}),  # 63
    (0, "resolve_board_effect", {"effect": "resources"}),  # 64
    (0, "finish_agent_turn", {}),  # 65
    (3, "reveal_turn", {}),  # 66
    (3, "finish_reveal", {}),  # 67
    (0, "reveal_turn", {}),  # 68
    (0, "acquire_imperium", {"instance_id": "imperium:bene_gesserit_sister:0"}),  # 69
    (0, "finish_reveal", {}),  # 70
    (3, "choose_agent_card", {"card_id": "imperium:arrakis_recruiter:1"}),  # 71
    (3, "place_agent", {"space_id": "arrakeen"}),  # 72
    (3, "resolve_board_effect", {"effect": "troops"}),  # 73
    (3, "resolve_board_effect", {"effect": "cards"}),  # 74
    (3, "deploy_troops", {"count": 2}),  # 75
    (3, "resolve_agent_card_effect", {}),  # 76
    (3, "deploy_troops", {"count": 1}),  # 77
    (3, "finish_agent_turn", {}),  # 78
    (0, "choose_agent_card", {"card_id": "player:0:starter:seek_allies:0"}),  # 79
    (0, "place_agent", {"space_id": "secrets"}),  # 80
    (0, "resolve_board_effect", {"effect": "intrigue"}),  # 81
    (0, "resolve_faction_influence", {}),  # 82
    (0, "resolve_agent_card_effect", {}),  # 83
    (0, "finish_agent_turn", {}),  # 84
    (
        1,
        "choose_agent_card",
        {"card_id": "player:1:starter:dune_the_desert_planet:1"},
    ),  # 85
    (1, "place_agent", {"space_id": "smuggling"}),  # 86
    (1, "advance_board_freighter", {}),  # 87
    (1, "resolve_board_effect", {"effect": "resources"}),  # 88
    (1, "finish_agent_turn", {}),  # 89
    (2, "choose_agent_card", {"card_id": "player:2:starter:signet_ring:0"}),  # 90
    (2, "place_agent", {"space_id": "tech_negotiation"}),  # 91
    # Round 3: seat 2 at Tech Negotiation (93: Acquire Tech open, Tech Discount
    # 1, spice), takes Sonic Snoopers; later trashes it to put Private Army under
    # the Intrigue deck (115) and ends its turn (121: seat 3 decides).
    (2, "acquire_negotiation_tech", {}),  # 92
    (2, "acquire_tech", {"tech_id": "sonic_snoopers"}),  # 93
    (2, "resolve_agent_card_effect", {}),  # 94
    (
        2,
        "resolve_tech_acquire_effect",
        {"effect": "intrigue", "tech_id": "sonic_snoopers"},
    ),  # 95
    (2, "finish_agent_turn", {}),  # 96
    (3, "choose_agent_card", {"card_id": "player:3:starter:reconnaissance:0"}),  # 97
    (3, "place_agent", {"space_id": "carthag"}),  # 98
    (3, "resolve_board_effect", {"effect": "troops"}),  # 99
    (3, "deploy_troops", {"count": 3}),  # 100
    (3, "resolve_board_effect", {"effect": "intrigue"}),  # 101
    (3, "finish_agent_turn", {}),  # 102
    (0, "choose_agent_card", {"card_id": "imperium:bene_gesserit_sister:0"}),  # 103
    (0, "place_agent", {"space_id": "dreadnought"}),  # 104
    (0, "acquire_board_tech", {}),  # 105
    (0, "acquire_tech", {"tech_id": "detonation_devices"}),  # 106
    (0, "finish_agent_turn", {}),  # 107
    (1, "choose_agent_card", {"card_id": "player:1:starter:diplomacy:0"}),  # 108
    (1, "place_agent", {"space_id": "foldspace"}),  # 109
    (1, "resolve_board_effect", {"effect": "foldspace"}),  # 110
    (1, "resolve_faction_influence", {}),  # 111
    (1, "finish_agent_turn", {}),  # 112
    (2, "trash_tech", {"tech_id": "sonic_snoopers"}),  # 113
    (2, "put_intrigue_on_bottom", {"card_id": "intrigue:private_army:1"}),  # 114
    (2, "finish_intrigue_bottom", {}),  # 115
    (
        2,
        "choose_agent_card",
        {"card_id": "player:2:starter:dune_the_desert_planet:1"},
    ),  # 116
    (2, "place_agent", {"space_id": "imperial_basin"}),  # 117
    (2, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 118
    (2, "deploy_troops", {"count": 1}),  # 119
    (2, "finish_agent_turn", {}),  # 120
    (3, "reveal_turn", {}),  # 121
    (3, "acquire_imperium", {"instance_id": "imperium:space_travel:0"}),  # 122
    (3, "finish_reveal", {}),  # 123
    (0, "reveal_turn", {}),  # 124
    (0, "acquire_imperium", {"instance_id": "imperium:the_voice:1"}),  # 125
    (0, "acquire_imperium", {"instance_id": "imperium:spice_smugglers:0"}),  # 126
    (0, "finish_reveal", {}),  # 127
    (1, "reveal_turn", {}),  # 128
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 129
    (1, "finish_reveal", {}),  # 130
    (2, "reveal_turn", {}),  # 131
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 132
    (2, "finish_reveal", {}),  # 133
    (3, "pass_combat_intrigue", {}),  # 134
    (
        2,
        "play_intrigue",
        {"card_id": "intrigue:master_tactician:0", "option": 0},
    ),  # 135
    (2, "pass_combat_intrigue", {}),  # 136
    (3, "pass_combat_intrigue", {}),  # 137
    (2, "pass_combat_intrigue", {}),  # 138
    (3, "resolve_combat_reward_icon", {"effect": "freighter"}),  # 139
    (3, "decline_freighter", {}),  # 140
    (3, "resolve_combat_reward_icon", {"effect": "troops"}),  # 141
    (3, "resolve_combat_reward_icon", {"effect": "freighter"}),  # 142
    (3, "advance_freighter", {}),  # 143
    (3, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 144
    (2, "resolve_combat_reward_icon", {"effect": "resources"}),  # 145
    (2, "resolve_combat_reward_icon", {"effect": "intrigue"}),  # 146
    (0, "reveal_turn", {}),  # 147
    (
        0,
        "acquire_imperium",
        {"instance_id": "imperium:sietch_reverend_mother:0"},
    ),  # 148
    (0, "finish_reveal", {}),  # 149
    (
        1,
        "choose_agent_card",
        {"card_id": "player:1:starter:dune_the_desert_planet:0"},
    ),  # 150
    (1, "place_agent", {"space_id": "smuggling"}),  # 151
    (1, "resolve_board_effect", {"effect": "resources"}),  # 152
    (1, "advance_board_freighter", {}),  # 153
    (1, "finish_agent_turn", {}),  # 154
    (2, "choose_agent_card", {"card_id": "imperium:spice_hunter:0"}),  # 155
    (2, "place_agent", {"space_id": "hardy_warriors"}),  # 156
    (2, "resolve_faction_influence", {}),  # 157
    (2, "play_intrigue", {"card_id": "intrigue:calculated_hire:0", "option": 0}),  # 158
    (2, "resolve_board_effect", {"effect": "troops"}),  # 159
    (2, "deploy_troops", {"count": 1}),  # 160
    (2, "finish_agent_turn", {}),  # 161
    (3, "choose_agent_card", {"card_id": "reserve:foldspace_card:5"}),  # 162
    (3, "place_agent", {"space_id": "carthag"}),  # 163
    (3, "resolve_agent_card_effect", {"effect": "trash_self"}),  # 164
    (3, "deploy_troops", {"count": 1}),  # 165
    (3, "resolve_board_effect", {"effect": "intrigue"}),  # 166
    (3, "resolve_agent_card_effect", {"effect": "cards"}),  # 167
    (3, "resolve_board_effect", {"effect": "troops"}),  # 168
    (3, "finish_agent_turn", {}),  # 169
    (1, "choose_agent_card", {"card_id": "player:1:starter:seek_allies:0"}),  # 170
    (1, "place_agent", {"space_id": "foldspace"}),  # 171
    (1, "resolve_faction_influence", {}),  # 172
    (1, "resolve_board_effect", {"effect": "foldspace"}),  # 173
    (1, "resolve_agent_card_effect", {}),  # 174
    (1, "finish_agent_turn", {}),  # 175
    (
        2,
        "choose_agent_card",
        {"card_id": "player:2:starter:dune_the_desert_planet:1"},
    ),  # 176
    (2, "place_agent", {"space_id": "imperial_basin"}),  # 177
    (2, "deploy_troops", {"count": 2}),  # 178
    (2, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 179
    (2, "finish_agent_turn", {}),  # 180
    (3, "choose_agent_card", {"card_id": "player:3:starter:dagger:1"}),  # 181
    (3, "place_agent", {"space_id": "tech_negotiation"}),  # 182
    (3, "place_board_negotiator", {}),  # 183
    (3, "finish_agent_turn", {}),  # 184
    (1, "reveal_turn", {}),  # 185
    (1, "finish_reveal", {}),  # 186
    (2, "choose_agent_card", {"card_id": "reserve:arrakis_liaison:5"}),  # 187
    (2, "place_agent", {"space_id": "dreadnought"}),  # 188
    (2, "finish_agent_turn", {}),  # 189
    (3, "reveal_turn", {}),  # 190
    (3, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 191
    (3, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 192
    (3, "finish_reveal", {}),  # 193
    (2, "reveal_turn", {}),  # 194
    (2, "finish_reveal", {}),  # 195
    (2, "pass_combat_intrigue", {}),  # 196
    (3, "pass_combat_intrigue", {}),  # 197
    (2, "resolve_combat_reward_icon", {"effect": "mentat"}),  # 198
    (2, "resolve_combat_reward_icon", {"effect": "intrigue"}),  # 199
    (2, "resolve_combat_reward_icon", {"effect": "resources"}),  # 200
    (2, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 201
    (3, "resolve_combat_reward_icon", {"effect": "resources"}),  # 202
    (3, "resolve_combat_reward_icon", {"effect": "intrigue"}),  # 203
    (
        1,
        "choose_agent_card",
        {"card_id": "player:1:starter:dune_the_desert_planet:0"},
    ),  # 204
    (1, "place_agent", {"space_id": "interstellar_shipping"}),  # 205
    (1, "advance_board_freighter", {}),  # 206
    (1, "finish_agent_turn", {}),  # 207
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:0"}),  # 208
    (2, "place_agent", {"space_id": "mentat"}),  # 209
    (2, "play_intrigue", {"card_id": "intrigue:cull:0", "option": 0}),  # 210
    (2, "trash_intrigue_card", {"card_id": "imperium:spice_hunter:0"}),  # 211
    (2, "resolve_board_effect", {"effect": "cards"}),  # 212
    (2, "finish_agent_turn", {}),  # 213
    (3, "play_intrigue", {"card_id": "intrigue:bribery:0", "option": 0}),  # 214
    (3, "choose_intrigue_faction", {"faction": "emperor"}),  # 215
    (3, "choose_agent_card", {"card_id": "player:3:starter:dagger:0"}),  # 216
    (3, "place_agent", {"space_id": "tech_negotiation"}),  # 217
    # Round 5: seat 3 at Tech Negotiation with a Negotiator returnable (219),
    # declines the Tech and ends its turn (221: seat 0 decides).
    (3, "acquire_negotiation_tech", {}),  # 218
    (3, "decline_tech", {}),  # 219
    (3, "finish_agent_turn", {}),  # 220
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
    # Found on the engine as merged with P4 6c6b747e (seed 4, answer stream 4).
    # The draft: seat 1 Hundro, seat 0 Ilesa, seat 3 Tessia, seat 2 Armand.
    (1, "pick_leader", {"leader_id": "viscount_hundro_moritani"}),  # 0
    (0, "pick_leader", {"leader_id": "ilesa_ecaz"}),  # 1
    (3, "pick_leader", {"leader_id": "tessia_vernius"}),  # 2
    (2, "pick_leader", {"leader_id": "archduke_armand_ecaz"}),  # 3
    (2, "finish_leader_draft", {}),  # 4
    # Hundro's Intelligence (checkpoint 5: he sees the top two); he keeps Know
    # Their Ways and Charisma goes back on top (6).
    (1, "keep_peeked_intrigue", {"instance_id": "intrigue:know_their_ways:0"}),  # 5
    # Ilesa sets a card aside (checkpoint 7).
    (
        0,
        "set_aside_leader_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:1"},
    ),  # 6
    # Round 1: seat 2's Agent turn (20), seat 3's Reveal (24), Ilesa's Agent
    # turn (27), Hundro's Reveal (30), seat 2's Reveal; then Ilesa's second
    # turn starts and her card comes back (33).
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
    (3, "acquire_imperium", {"instance_id": "imperium:sardaukar_infantry:1"}),  # 21
    (3, "acquire_imperium", {"instance_id": "imperium:guild_administrator:1"}),  # 22
    (3, "finish_reveal", {}),  # 23
    (0, "choose_agent_card", {"card_id": "player:0:starter:dagger:1"}),  # 24
    (0, "place_agent", {"space_id": "tech_negotiation"}),  # 25
    (0, "finish_agent_turn", {}),  # 26
    (1, "reveal_turn", {}),  # 27
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 28
    (1, "finish_reveal", {}),  # 29
    (2, "reveal_turn", {}),  # 30
    (2, "acquire_imperium", {"instance_id": "imperium:fremen_camp:0"}),  # 31
    (2, "finish_reveal", {}),  # 32
]

# (seat, action id, arguments), in order; the number after each is its index.
FIRST_PLAN: list[Step] = [
    # Found on the engine as merged with P4 6c6b747e (seed 1, answer stream 1000).
    # The draft: seat 3 Tessia, seat 2 Yuna, seat 1 Memnon, seat 0 (the first
    # player) Ilesa.
    (3, "pick_leader", {"leader_id": "tessia_vernius"}),  # 0
    (2, "pick_leader", {"leader_id": "princess_yuna_moritani"}),  # 1
    (1, "pick_leader", {"leader_id": "earl_memnon_thorvald"}),  # 2
    (0, "pick_leader", {"leader_id": "ilesa_ecaz"}),  # 3
    (0, "finish_leader_draft", {}),  # 4
    # Ilesa sets a card aside (checkpoint 6: her first turn starts at once)
    # and reveals in that turn (7).
    (0, "set_aside_leader_card", {"card_id": "player:0:starter:dagger:1"}),  # 5
    (0, "reveal_turn", {}),  # 6
]

# (seat, action id, arguments), in order; the number after each is its index.
DISPOSAL_PLAN: list[Step] = [
    (3, "choose_masterstroke_faction", {"faction": "bene_gesserit"}),  # 0
    (3, "choose_masterstroke_faction", {"faction": "emperor"}),  # 1
    (0, "choose_agent_card", {"card_id": "player:0:starter:reconnaissance:0"}),  # 2
    (0, "place_agent", {"space_id": "carthag"}),  # 3
    (0, "resolve_board_effect", {"effect": "intrigue"}),  # 4
    (0, "resolve_board_effect", {"effect": "troops"}),  # 5
    (0, "finish_agent_turn", {}),  # 6
    (1, "choose_agent_card", {"card_id": "player:1:starter:dagger:0"}),  # 7
    (1, "place_agent", {"space_id": "tech_negotiation"}),  # 8
    (1, "acquire_negotiation_tech", {}),  # 9
    (1, "acquire_tech", {"tech_id": "artillery"}),  # 10
    (1, "finish_agent_turn", {}),  # 11
    (2, "choose_agent_card", {"card_id": "player:2:starter:diplomacy:0"}),  # 12
    (2, "place_agent", {"space_id": "secrets"}),  # 13
    (2, "resolve_board_effect", {"effect": "intrigue"}),  # 14
    (2, "resolve_faction_influence", {}),  # 15
    (2, "finish_agent_turn", {}),  # 16
    (3, "reveal_turn", {}),  # 17
    (3, "acquire_imperium", {"instance_id": "imperium:missionaria_protectiva:0"}),  # 18
    (3, "finish_reveal", {}),  # 19
    (0, "reveal_turn", {}),  # 20
    (0, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 21
    (0, "finish_reveal", {}),  # 22
    (1, "choose_agent_card", {"card_id": "player:1:starter:seek_allies:0"}),  # 23
    (1, "place_agent", {"space_id": "foldspace"}),  # 24
    (1, "resolve_faction_influence", {}),  # 25
    (1, "resolve_agent_card_effect", {}),  # 26
    (1, "resolve_board_effect", {"effect": "foldspace"}),  # 27
    (1, "finish_agent_turn", {}),  # 28
    (2, "reveal_turn", {}),  # 29
    (2, "acquire_imperium", {"instance_id": "imperium:dr_yueh:0"}),  # 30
    (2, "acquire_imperium", {"instance_id": "imperium:bene_gesserit_sister:1"}),  # 31
    (2, "finish_reveal", {}),  # 32
    (1, "reveal_turn", {}),  # 33
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 34
    (1, "finish_reveal", {}),  # 35
    (1, "choose_agent_card", {"card_id": "player:1:starter:reconnaissance:0"}),  # 36
    (1, "place_agent", {"space_id": "arrakeen"}),  # 37
    (1, "resolve_board_effect", {"effect": "cards"}),  # 38
    (1, "resolve_board_effect", {"effect": "troops"}),  # 39
    (1, "finish_agent_turn", {}),  # 40
    (2, "choose_agent_card", {"card_id": "player:2:starter:reconnaissance:0"}),  # 41
    (2, "place_agent", {"space_id": "carthag"}),  # 42
    (2, "resolve_board_effect", {"effect": "troops"}),  # 43
    (2, "resolve_board_effect", {"effect": "intrigue"}),  # 44
    (2, "deploy_troops", {"count": 1}),  # 45
    (2, "finish_agent_turn", {}),  # 46
    (
        3,
        "choose_agent_card",
        {"card_id": "player:3:starter:dune_the_desert_planet:0"},
    ),  # 47
    (3, "place_agent", {"space_id": "smuggling"}),  # 48
    (3, "resolve_board_effect", {"effect": "resources"}),  # 49
    (3, "advance_board_freighter", {}),  # 50
    (3, "finish_agent_turn", {}),  # 51
    (0, "reveal_turn", {}),  # 52
    (0, "acquire_imperium", {"instance_id": "imperium:space_travel:1"}),  # 53
    (0, "acquire_imperium", {"instance_id": "imperium:guild_administrator:1"}),  # 54
    (0, "finish_reveal", {}),  # 55
    (
        1,
        "choose_agent_card",
        {"card_id": "player:1:starter:dune_the_desert_planet:0"},
    ),  # 56
    (1, "place_agent", {"space_id": "imperium_hagga_basin"}),  # 57
    (1, "harvest_maker_spice", {"space_id": "imperium_hagga_basin"}),  # 58
    (1, "finish_agent_turn", {}),  # 59
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:1"}),  # 60
    (2, "place_agent", {"space_id": "tech_negotiation"}),  # 61
    (2, "finish_agent_turn", {}),  # 62
    (3, "reveal_turn", {}),  # 63
    (3, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 64
    (3, "finish_reveal", {}),  # 65
    (1, "reveal_turn", {}),  # 66
    (1, "finish_reveal", {}),  # 67
    (2, "reveal_turn", {}),  # 68
    (2, "acquire_imperium", {"instance_id": "imperium:assassination_mission:1"}),  # 69
    (2, "acquire_imperium", {"instance_id": "imperium:spice_smugglers:1"}),  # 70
    (2, "finish_reveal", {}),  # 71
    (2, "play_intrigue", {"card_id": "intrigue:ambush:1", "option": 0}),  # 72
    (2, "pass_combat_intrigue", {}),  # 73
    (2, "resolve_combat_reward_icon", {"effect": "victory_points"}),  # 74
    (2, "resolve_combat_reward_icon", {"effect": "resources"}),  # 75
    (2, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 76
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:1"}),  # 77
    (2, "place_agent", {"space_id": "tech_negotiation"}),  # 78
    (2, "acquire_negotiation_tech", {}),  # 79
    (2, "acquire_tech", {"tech_id": "windtraps"}),  # 80
    (
        2,
        "resolve_tech_acquire_effect",
        {"effect": "water", "tech_id": "windtraps"},
    ),  # 81
    (2, "finish_agent_turn", {}),  # 82
    (3, "choose_agent_card", {"card_id": "player:3:starter:reconnaissance:0"}),  # 83
    (3, "place_agent", {"space_id": "carthag"}),  # 84
    (3, "resolve_board_effect", {"effect": "troops"}),  # 85
    (3, "resolve_board_effect", {"effect": "intrigue"}),  # 86
    (
        3,
        "play_intrigue",
        {"card_id": "intrigue:rapid_mobilization:0", "option": 0},
    ),  # 87
    (3, "deploy_intrigue_troops", {"count": 4}),  # 88
    (3, "finish_agent_turn", {}),  # 89
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:0"},
    ),  # 90
    (0, "place_agent", {"space_id": "smuggling"}),  # 91
    (0, "advance_board_freighter", {}),  # 92
    (0, "resolve_board_effect", {"effect": "resources"}),  # 93
    (0, "finish_agent_turn", {}),  # 94
    (1, "choose_agent_card", {"card_id": "reserve:arrakis_liaison:6"}),  # 95
    (1, "place_agent", {"space_id": "arrakeen"}),  # 96
    (1, "resolve_board_effect", {"effect": "cards"}),  # 97
    (1, "deploy_troops", {"count": 1}),  # 98
    (1, "resolve_board_effect", {"effect": "troops"}),  # 99
    (1, "finish_agent_turn", {}),  # 100
    (
        2,
        "choose_agent_card",
        {"card_id": "player:2:starter:dune_the_desert_planet:1"},
    ),  # 101
    (2, "place_agent", {"space_id": "imperium_hagga_basin"}),  # 102
    (2, "harvest_maker_spice", {"space_id": "imperium_hagga_basin"}),  # 103
    (2, "finish_agent_turn", {}),  # 104
    (
        3,
        "choose_agent_card",
        {"card_id": "player:3:starter:dune_the_desert_planet:1"},
    ),  # 105
    (3, "place_agent", {"space_id": "imperial_basin"}),  # 106
    (3, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 107
    (3, "finish_agent_turn", {}),  # 108
    (0, "choose_agent_card", {"card_id": "imperium:guild_administrator:1"}),  # 109
    (0, "place_agent", {"space_id": "foldspace"}),  # 110
    (
        0,
        "trash_agent_card",
        {"card_id": "player:0:starter:convincing_argument:1"},
    ),  # 111
    (0, "resolve_board_effect", {"effect": "foldspace"}),  # 112
    (0, "resolve_faction_influence", {}),  # 113
    (0, "finish_agent_turn", {}),  # 114
    (1, "reveal_turn", {}),  # 115
    (1, "finish_reveal", {}),  # 116
    (2, "reveal_turn", {}),  # 117
    (2, "acquire_imperium", {"instance_id": "imperium:guild_administrator:0"}),  # 118
    (2, "gain_two_reveal_swords", {}),  # 119
    (2, "finish_reveal", {}),  # 120
    (3, "reveal_turn", {}),  # 121
    (3, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 122
    (3, "finish_reveal", {}),  # 123
    (0, "reveal_turn", {}),  # 124
    (0, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 125
    (0, "finish_reveal", {}),  # 126
    (3, "pass_combat_intrigue", {}),  # 127
    (1, "pass_combat_intrigue", {}),  # 128
    (3, "resolve_combat_reward_icon", {"effect": "victory_points"}),  # 129
    (3, "resolve_combat_reward_icon", {"effect": "control"}),  # 130
    (3, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 131
    (1, "resolve_combat_reward_icon", {"effect": "intrigue"}),  # 132
    (1, "resolve_combat_reward_icon", {"effect": "resources"}),  # 133
    (3, "choose_agent_card", {"card_id": "player:3:starter:signet_ring:0"}),  # 134
    (3, "place_agent", {"space_id": "smuggling"}),  # 135
    (3, "resolve_board_effect", {"effect": "resources"}),  # 136
    (3, "advance_board_freighter", {}),  # 137
    (3, "finish_agent_turn", {}),  # 138
    (0, "choose_agent_card", {"card_id": "player:0:starter:dagger:0"}),  # 139
    (0, "place_agent", {"space_id": "tech_negotiation"}),  # 140
    (0, "place_board_negotiator", {}),  # 141
    (0, "finish_agent_turn", {}),  # 142
    (1, "reveal_turn", {}),  # 143
    (
        1,
        "acquire_imperium",
        {"instance_id": "imperium:reverend_mother_mohiam:0"},
    ),  # 144
    (1, "finish_reveal", {}),  # 145
    (2, "choose_agent_card", {"card_id": "player:2:starter:seek_allies:0"}),  # 146
    (2, "place_agent", {"space_id": "selective_breeding"}),  # 147
    (
        2,
        "trash_card_for_desert_tactics",
        {"card_id": "player:2:starter:seek_allies:0"},
    ),  # 148
    (2, "resolve_faction_influence", {}),  # 149
    (2, "resolve_board_effect", {"effect": "cards"}),  # 150
    (2, "finish_agent_turn", {}),  # 151
    (3, "choose_agent_card", {"card_id": "player:3:starter:diplomacy:0"}),  # 152
    (3, "place_agent", {"space_id": "stillsuits"}),  # 153
    (3, "resolve_board_effect", {"effect": "resources"}),  # 154
    (3, "resolve_faction_influence", {}),  # 155
    (3, "finish_agent_turn", {}),  # 156
    (0, "choose_agent_card", {"card_id": "player:0:starter:signet_ring:0"}),  # 157
    (0, "place_agent", {"space_id": "arrakeen"}),  # 158
    (0, "deploy_troops", {"count": 1}),  # 159
    (0, "resolve_board_effect", {"effect": "troops"}),  # 160
    (0, "resolve_board_effect", {"effect": "cards"}),  # 161
    (0, "deploy_troops", {"count": 2}),  # 162
    (0, "resolve_agent_card_effect", {}),  # 163
    (0, "finish_agent_turn", {}),  # 164
    (2, "choose_agent_card", {"card_id": "player:2:starter:signet_ring:0"}),  # 165
    (2, "place_agent", {"space_id": "imperium_research_station"}),  # 166
    (2, "deploy_troops", {"count": 1}),  # 167
    (2, "resolve_board_effect", {"effect": "cards"}),  # 168
    (2, "resolve_agent_card_effect", {}),  # 169
    (2, "resolve_board_effect", {"effect": "cards"}),  # 170
    (2, "resolve_board_effect", {"effect": "cards"}),  # 171
    (2, "finish_agent_turn", {}),  # 172
    (3, "reveal_turn", {}),  # 173
    (3, "acquire_imperium", {"instance_id": "imperium:bene_gesserit_sister:2"}),  # 174
    (3, "acquire_imperium", {"instance_id": "imperium:court_intrigue:0"}),  # 175
    (3, "finish_reveal", {}),  # 176
    (0, "reveal_turn", {}),  # 177
    (0, "finish_reveal", {}),  # 178
    (2, "reveal_turn", {}),  # 179
    (2, "acquire_imperium", {"instance_id": "imperium:thufir_hawat:0"}),  # 180
    (
        2,
        "acquire_imperium",
        {"instance_id": "imperium:fedaykin_death_commando:1"},
    ),  # 181
    (
        2,
        "gain_reveal_resources",
        {
            "printed": "assassination_mission",
            "solari": 1,
            "source": "reveal_card",
            "spice": 0,
            "water": 0,
        },
    ),  # 182
    (2, "finish_reveal", {}),  # 183
    (0, "pass_combat_intrigue", {}),  # 184
    (2, "pass_combat_intrigue", {}),  # 185
    (0, "resolve_combat_reward_icon", {"effect": "resources"}),  # 186
    (0, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 187
    (2, "resolve_combat_reward_icon", {"effect": "resources"}),  # 188
    (0, "choose_agent_card", {"card_id": "player:0:starter:dagger:0"}),  # 189
    (0, "place_agent", {"space_id": "tech_negotiation"}),  # 190
    (0, "finish_agent_turn", {}),  # 191
    (1, "play_intrigue", {"card_id": "intrigue:refocus:0", "option": 0}),  # 192
    (1, "reveal_turn", {}),  # 193
    (1, "acquire_imperium", {"instance_id": "imperium:space_travel:0"}),  # 194
    (1, "acquire_imperium", {"instance_id": "imperium:gun_thopter:1"}),  # 195
    (1, "finish_reveal", {}),  # 196
    (2, "reveal_turn", {}),  # 197
    (2, "gain_two_reveal_swords", {}),  # 198
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 199
    (2, "finish_reveal", {}),  # 200
    (3, "choose_agent_card", {"card_id": "player:3:starter:dagger:0"}),  # 201
    (3, "place_agent", {"space_id": "mentat"}),  # 202
    (3, "resolve_board_effect", {"effect": "mentat"}),  # 203
    (3, "resolve_board_effect", {"effect": "cards"}),  # 204
    (3, "finish_agent_turn", {}),  # 205
    (
        0,
        "play_intrigue",
        {"card_id": "intrigue:advanced_weaponry:0", "option": 0},
    ),  # 206
    (0, "decline_intrigue_dreadnought", {}),  # 207
    (0, "choose_agent_card", {"card_id": "reserve:arrakis_liaison:7"}),  # 208
    (0, "place_agent", {"space_id": "carthag"}),  # 209
    (0, "resolve_board_effect", {"effect": "intrigue"}),  # 210
    (0, "deploy_troops", {"count": 1}),  # 211
    (0, "deploy_troops", {"count": 1}),  # 212
    (0, "resolve_board_effect", {"effect": "troops"}),  # 213
    (0, "finish_agent_turn", {}),  # 214
    (3, "choose_agent_card", {"card_id": "imperium:bene_gesserit_sister:2"}),  # 215
    (3, "place_agent", {"space_id": "selective_breeding"}),  # 216
    (
        3,
        "trash_card_for_desert_tactics",
        {"card_id": "player:3:starter:signet_ring:0"},
    ),  # 217
    (3, "resolve_faction_influence", {}),  # 218
    (3, "resolve_board_effect", {"effect": "cards"}),  # 219
    (3, "finish_agent_turn", {}),  # 220
    (0, "reveal_turn", {}),  # 221
    (0, "acquire_imperium", {"instance_id": "imperium:truthsayer:1"}),  # 222
    (0, "finish_reveal", {}),  # 223
    (3, "choose_agent_card", {"card_id": "player:3:starter:reconnaissance:0"}),  # 224
    (3, "place_agent", {"space_id": "imperium_research_station"}),  # 225
    (3, "resolve_board_effect", {"effect": "cards"}),  # 226
    (3, "resolve_board_effect", {"effect": "cards"}),  # 227
    (3, "resolve_board_effect", {"effect": "cards"}),  # 228
    (3, "finish_agent_turn", {}),  # 229
    (3, "reveal_turn", {}),  # 230
    (3, "acquire_imperium", {"instance_id": "imperium:landing_rights:0"}),  # 231
    (3, "finish_reveal", {}),  # 232
    (0, "pass_combat_intrigue", {}),  # 233
    (0, "resolve_combat_reward_icon", {"effect": "intrigue"}),  # 234
    (0, "resolve_combat_reward_icon", {"effect": "resources"}),  # 235
    (0, "resolve_combat_reward_icon", {"effect": "mentat"}),  # 236
    (0, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 237
    (1, "reveal_turn", {}),  # 238
    (1, "acquire_imperium", {"instance_id": "imperium:the_voice:1"}),  # 239
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 240
    (
        1,
        "gain_reveal_resources",
        {
            "printed": "reverend_mother_mohiam",
            "solari": 0,
            "source": "reveal_card",
            "spice": 2,
            "water": 0,
        },
    ),  # 241
    (1, "finish_reveal", {}),  # 242
    (2, "choose_agent_card", {"card_id": "imperium:thufir_hawat:0"}),  # 243
    (2, "place_agent", {"space_id": "carthag"}),  # 244
    (2, "resolve_agent_card_effect", {}),  # 245
    (2, "resolve_board_effect", {"effect": "intrigue"}),  # 246
    (2, "resolve_board_effect", {"effect": "troops"}),  # 247
    (2, "deploy_troops", {"count": 2}),  # 248
    (2, "finish_agent_turn", {}),  # 249
    (
        3,
        "choose_agent_card",
        {"card_id": "player:3:starter:dune_the_desert_planet:1"},
    ),  # 250
    (3, "place_agent", {"space_id": "imperial_basin"}),  # 251
    (3, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 252
    (3, "finish_agent_turn", {}),  # 253
    (0, "reveal_turn", {}),  # 254
    (0, "acquire_imperium", {"instance_id": "imperium:shifting_allegiances:1"}),  # 255
    (0, "acquire_imperium", {"instance_id": "imperium:spice_hunter:0"}),  # 256
    (0, "finish_reveal", {}),  # 257
    (2, "choose_agent_card", {"card_id": "player:2:starter:reconnaissance:0"}),  # 258
    (2, "place_agent", {"space_id": "arrakeen"}),  # 259
    (2, "resolve_board_effect", {"effect": "cards"}),  # 260
    (2, "resolve_board_effect", {"effect": "troops"}),  # 261
    (2, "deploy_troops", {"count": 3}),  # 262
    (2, "finish_agent_turn", {}),  # 263
    (3, "reveal_turn", {}),  # 264
    (3, "acquire_imperium", {"instance_id": "imperium:crysknife_card:0"}),  # 265
    (3, "acquire_imperium", {"instance_id": "imperium:arrakis_recruiter:1"}),  # 266
    (3, "finish_reveal", {}),  # 267
    (2, "reveal_turn", {}),  # 268
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 269
    (
        2,
        "gain_reveal_resources",
        {
            "printed": "assassination_mission",
            "solari": 1,
            "source": "reveal_card",
            "spice": 0,
            "water": 0,
        },
    ),  # 270
    (2, "finish_reveal", {}),  # 271
    (2, "pass_combat_intrigue", {}),  # 272
    (2, "resolve_combat_reward_icon", {"effect": "trash"}),  # 273
    (2, "trash_combat_reward_card", {"card_id": "reserve:arrakis_liaison:0"}),  # 274
    (2, "resolve_combat_reward_icon", {"effect": "windtraps"}),  # 275
    (2, "resolve_combat_reward_icon", {"effect": "victory_points"}),  # 276
    (2, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 277
    (
        2,
        "choose_agent_card",
        {"card_id": "player:2:starter:dune_the_desert_planet:1"},
    ),  # 278
    (2, "place_agent", {"space_id": "imperium_hagga_basin"}),  # 279
    (2, "harvest_maker_spice", {"space_id": "imperium_hagga_basin"}),  # 280
    (2, "finish_agent_turn", {}),  # 281
    (3, "choose_agent_card", {"card_id": "player:3:starter:seek_allies:0"}),  # 282
    (3, "place_agent", {"space_id": "stillsuits"}),  # 283
    (3, "resolve_faction_influence", {}),  # 284
    (3, "resolve_agent_card_effect", {}),  # 285
    (3, "resolve_board_effect", {"effect": "resources"}),  # 286
    (3, "finish_agent_turn", {}),  # 287
    (0, "choose_agent_card", {"card_id": "imperium:space_travel:1"}),  # 288
    (0, "place_agent", {"space_id": "foldspace"}),  # 289
    (0, "resolve_faction_influence", {}),  # 290
    (0, "resolve_agent_card_effect", {}),  # 291
    (0, "play_intrigue", {"card_id": "intrigue:reinforcements:0", "option": 0}),  # 292
    (0, "resolve_board_effect", {"effect": "foldspace"}),  # 293
    (0, "finish_agent_turn", {}),  # 294
    (1, "choose_agent_card", {"card_id": "player:1:starter:dagger:0"}),  # 295
    (1, "place_agent", {"space_id": "tech_negotiation"}),  # 296
    (1, "place_board_negotiator", {}),  # 297
    (1, "finish_agent_turn", {}),  # 298
    # Round 7, seat 2's Reveal: Machine Culture opens an Acquire Tech, it
    # takes Disposal Facility and its acquire box's trash (checkpoint 303: both
    # trashes on offer), then trashes a card with the box (304).
    (2, "reveal_turn", {}),  # 299
    (2, "play_intrigue", {"card_id": "intrigue:machine_culture:0", "option": 0}),  # 300
    (2, "acquire_tech", {"tech_id": "disposal_facility"}),  # 301
    (
        2,
        "resolve_tech_acquire_effect",
        {"effect": "trash", "tech_id": "disposal_facility"},
    ),  # 302
    (
        2,
        "trash_optional_card",
        {
            "card_id": "imperium:thufir_hawat:0",
            "printed": "disposal_facility",
            "source": "tech",
        },
    ),  # 303
]

# (seat, action id, arguments), in order; the number after each is its index.
STRATEGIC_PLAN: list[Step] = [
    (3, "choose_masterstroke_faction", {"faction": "bene_gesserit"}),  # 0
    (3, "choose_masterstroke_faction", {"faction": "spacing_guild"}),  # 1
    (2, "reveal_turn", {}),  # 2
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 3
    (2, "finish_reveal", {}),  # 4
    (3, "choose_agent_card", {"card_id": "player:3:starter:signet_ring:0"}),  # 5
    (3, "place_agent", {"space_id": "imperium_hagga_basin"}),  # 6
    (3, "deploy_troops", {"count": 1}),  # 7
    (3, "harvest_maker_spice", {"space_id": "imperium_hagga_basin"}),  # 8
    (3, "finish_agent_turn", {}),  # 9
    (0, "choose_agent_card", {"card_id": "player:0:starter:dagger:0"}),  # 10
    (0, "place_agent", {"space_id": "tech_negotiation"}),  # 11
    (0, "finish_agent_turn", {}),  # 12
    (1, "choose_agent_card", {"card_id": "player:1:starter:signet_ring:0"}),  # 13
    (1, "place_agent", {"space_id": "arrakeen"}),  # 14
    (1, "resolve_board_effect", {"effect": "cards"}),  # 15
    (1, "deploy_troops", {"count": 2}),  # 16
    (1, "resolve_board_effect", {"effect": "troops"}),  # 17
    (1, "finish_agent_turn", {}),  # 18
    (3, "choose_agent_card", {"card_id": "player:3:starter:reconnaissance:0"}),  # 19
    (3, "place_agent", {"space_id": "carthag"}),  # 20
    (3, "deploy_troops", {"count": 2}),  # 21
    (3, "withdraw_troops", {"count": 2}),  # 22
    (3, "deploy_troops", {"count": 1}),  # 23
    (3, "deploy_troops", {"count": 1}),  # 24
    (3, "resolve_board_effect", {"effect": "troops"}),  # 25
    (3, "withdraw_troops", {"count": 1}),  # 26
    (3, "deploy_troops", {"count": 2}),  # 27
    (3, "withdraw_troops", {"count": 1}),  # 28
    (3, "withdraw_troops", {"count": 2}),  # 29
    (3, "deploy_troops", {"count": 1}),  # 30
    (3, "resolve_board_effect", {"effect": "intrigue"}),  # 31
    (3, "deploy_troops", {"count": 2}),  # 32
    (3, "finish_agent_turn", {}),  # 33
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:0"},
    ),  # 34
    (0, "place_agent", {"space_id": "smuggling"}),  # 35
    (0, "resolve_board_effect", {"effect": "resources"}),  # 36
    (0, "finish_agent_turn", {}),  # 37
    (
        1,
        "choose_agent_card",
        {"card_id": "player:1:starter:dune_the_desert_planet:1"},
    ),  # 38
    (1, "place_agent", {"space_id": "imperial_basin"}),  # 39
    (1, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 40
    (1, "deploy_troops", {"count": 1}),  # 41
    (1, "finish_agent_turn", {}),  # 42
    (3, "reveal_turn", {}),  # 43
    (3, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 44
    (3, "finish_reveal", {}),  # 45
    (0, "reveal_turn", {}),  # 46
    (0, "acquire_imperium", {"instance_id": "imperium:gun_thopter:1"}),  # 47
    (0, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 48
    (0, "finish_reveal", {}),  # 49
    (1, "reveal_turn", {}),  # 50
    (1, "acquire_imperium", {"instance_id": "imperium:space_travel:1"}),  # 51
    (1, "finish_reveal", {}),  # 52
    # Round 1's Combat: seat 3 plays Strategic Push (checkpoint 54), wins alone
    # (57: its window offers the pledge's row), takes the row (58); round 2
    # starts (62).
    (3, "play_intrigue", {"card_id": "intrigue:strategic_push:0", "option": 0}),  # 53
    (3, "pass_combat_intrigue", {}),  # 54
    (1, "pass_combat_intrigue", {}),  # 55
    (3, "pass_combat_intrigue", {}),  # 56
    (3, "resolve_combat_reward_icon", {"effect": "strategic_push"}),  # 57
    (3, "resolve_combat_reward_icon", {"effect": "victory_points"}),  # 58
    (3, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 59
    (1, "resolve_combat_reward_icon", {"effect": "resources"}),  # 60
    (3, "choose_agent_card", {"card_id": "player:3:starter:diplomacy:0"}),  # 61
]

# (seat, action id, arguments), in order; the number after each is its index.
LOST_PUSH_PLAN: list[Step] = [
    (3, "choose_masterstroke_faction", {"faction": "emperor"}),  # 0
    (3, "choose_masterstroke_faction", {"faction": "spacing_guild"}),  # 1
    (0, "reveal_turn", {}),  # 2
    (0, "finish_reveal", {}),  # 3
    (1, "reveal_turn", {}),  # 4
    (1, "acquire_imperium", {"instance_id": "imperium:guild_ambassador:0"}),  # 5
    (1, "finish_reveal", {}),  # 6
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:1"}),  # 7
    (2, "place_agent", {"space_id": "tech_negotiation"}),  # 8
    (2, "finish_agent_turn", {}),  # 9
    (
        3,
        "choose_agent_card",
        {"card_id": "player:3:starter:dune_the_desert_planet:0"},
    ),  # 10
    (3, "place_agent", {"space_id": "smuggling"}),  # 11
    (3, "resolve_board_effect", {"effect": "resources"}),  # 12
    (3, "finish_agent_turn", {}),  # 13
    (2, "reveal_turn", {}),  # 14
    (2, "acquire_imperium", {"instance_id": "imperium:missionaria_protectiva:0"}),  # 15
    (2, "acquire_imperium", {"instance_id": "imperium:other_memory:0"}),  # 16
    (2, "acquire_imperium", {"instance_id": "imperium:sardaukar_infantry:0"}),  # 17
    (2, "finish_reveal", {}),  # 18
    (3, "choose_agent_card", {"card_id": "player:3:starter:seek_allies:0"}),  # 19
    (3, "place_agent", {"space_id": "hardy_warriors"}),  # 20
    (3, "resolve_faction_influence", {}),  # 21
    (3, "resolve_board_effect", {"effect": "troops"}),  # 22
    (3, "deploy_troops", {"count": 2}),  # 23
    (3, "deploy_troops", {"count": 1}),  # 24
    (3, "withdraw_troops", {"count": 1}),  # 25
    (3, "withdraw_troops", {"count": 1}),  # 26
    (3, "deploy_troops", {"count": 3}),  # 27
    (3, "resolve_agent_card_effect", {}),  # 28
    (3, "finish_agent_turn", {}),  # 29
    (3, "reveal_turn", {}),  # 30
    (3, "acquire_imperium", {"instance_id": "imperium:negotiated_withdrawal:0"}),  # 31
    (3, "finish_reveal", {}),  # 32
    (3, "pass_combat_intrigue", {}),  # 33
    (3, "resolve_combat_reward_icon", {"effect": "freighter"}),  # 34
    (3, "advance_freighter", {}),  # 35
    (3, "resolve_combat_reward_icon", {"effect": "resources"}),  # 36
    (3, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 37
    (1, "choose_agent_card", {"card_id": "player:1:starter:signet_ring:0"}),  # 38
    (1, "place_agent", {"space_id": "imperium_hagga_basin"}),  # 39
    (1, "harvest_maker_spice", {"space_id": "imperium_hagga_basin"}),  # 40
    (1, "deploy_troops", {"count": 2}),  # 41
    (1, "choose_leader_signet_influence", {"faction": "emperor"}),  # 42
    (1, "withdraw_troops", {"count": 1}),  # 43
    (1, "deploy_troops", {"count": 1}),  # 44
    (1, "finish_agent_turn", {}),  # 45
    (2, "choose_agent_card", {"card_id": "player:2:starter:diplomacy:0"}),  # 46
    (2, "place_agent", {"space_id": "wealth"}),  # 47
    (2, "resolve_board_effect", {"effect": "resources"}),  # 48
    (2, "resolve_faction_influence", {}),  # 49
    (2, "finish_agent_turn", {}),  # 50
    (3, "choose_agent_card", {"card_id": "player:3:starter:diplomacy:0"}),  # 51
    (3, "place_agent", {"space_id": "secrets"}),  # 52
    (3, "resolve_board_effect", {"effect": "intrigue"}),  # 53
    (3, "resolve_faction_influence", {}),  # 54
    (3, "finish_agent_turn", {}),  # 55
    (0, "choose_agent_card", {"card_id": "player:0:starter:diplomacy:0"}),  # 56
    (0, "place_agent", {"space_id": "hardy_warriors"}),  # 57
    (0, "resolve_board_effect", {"effect": "troops"}),  # 58
    (0, "deploy_troops", {"count": 2}),  # 59
    (0, "withdraw_troops", {"count": 2}),  # 60
    (0, "deploy_troops", {"count": 1}),  # 61
    (0, "deploy_troops", {"count": 3}),  # 62
    (0, "withdraw_troops", {"count": 4}),  # 63
    (0, "deploy_troops", {"count": 3}),  # 64
    (0, "withdraw_troops", {"count": 1}),  # 65
    (0, "withdraw_troops", {"count": 2}),  # 66
    (0, "deploy_troops", {"count": 1}),  # 67
    (0, "deploy_troops", {"count": 3}),  # 68
    (0, "resolve_faction_influence", {}),  # 69
    (0, "withdraw_troops", {"count": 3}),  # 70
    (0, "deploy_troops", {"count": 3}),  # 71
    (0, "withdraw_troops", {"count": 3}),  # 72
    (0, "withdraw_troops", {"count": 1}),  # 73
    (0, "deploy_troops", {"count": 3}),  # 74
    (0, "withdraw_troops", {"count": 3}),  # 75
    (0, "deploy_troops", {"count": 3}),  # 76
    (0, "withdraw_troops", {"count": 3}),  # 77
    (0, "deploy_troops", {"count": 3}),  # 78
    (0, "withdraw_troops", {"count": 2}),  # 79
    (0, "deploy_troops", {"count": 3}),  # 80
    (0, "withdraw_troops", {"count": 1}),  # 81
    (0, "withdraw_troops", {"count": 1}),  # 82
    (0, "deploy_troops", {"count": 2}),  # 83
    (0, "withdraw_troops", {"count": 1}),  # 84
    (0, "finish_agent_turn", {}),  # 85
    (1, "choose_agent_card", {"card_id": "player:1:starter:dagger:1"}),  # 86
    (1, "place_agent", {"space_id": "tech_negotiation"}),  # 87
    (1, "place_board_negotiator", {}),  # 88
    (1, "finish_agent_turn", {}),  # 89
    (2, "choose_agent_card", {"card_id": "player:2:starter:seek_allies:0"}),  # 90
    (2, "place_agent", {"space_id": "stillsuits"}),  # 91
    (2, "resolve_agent_card_effect", {}),  # 92
    (2, "deploy_troops", {"count": 2}),  # 93
    (2, "withdraw_troops", {"count": 2}),  # 94
    (2, "resolve_board_effect", {"effect": "resources"}),  # 95
    (2, "deploy_troops", {"count": 2}),  # 96
    (2, "withdraw_troops", {"count": 1}),  # 97
    (2, "deploy_troops", {"count": 1}),  # 98
    (2, "withdraw_troops", {"count": 1}),  # 99
    (2, "deploy_troops", {"count": 1}),  # 100
    (2, "resolve_faction_influence", {}),  # 101
    (2, "finish_agent_turn", {}),  # 102
    (3, "choose_agent_card", {"card_id": "player:3:starter:signet_ring:0"}),  # 103
    (3, "place_agent", {"space_id": "arrakeen"}),  # 104
    (3, "deploy_troops", {"count": 2}),  # 105
    (3, "withdraw_troops", {"count": 1}),  # 106
    (3, "deploy_troops", {"count": 1}),  # 107
    (3, "pay_leader_signet_solari", {}),  # 108
    (3, "withdraw_troops", {"count": 1}),  # 109
    (3, "deploy_troops", {"count": 1}),  # 110
    (3, "withdraw_troops", {"count": 2}),  # 111
    (3, "deploy_troops", {"count": 2}),  # 112
    (3, "withdraw_troops", {"count": 2}),  # 113
    (3, "deploy_troops", {"count": 2}),  # 114
    (3, "withdraw_troops", {"count": 2}),  # 115
    (3, "deploy_troops", {"count": 2}),  # 116
    (3, "resolve_board_effect", {"effect": "troops"}),  # 117
    (3, "deploy_troops", {"count": 1}),  # 118
    (3, "withdraw_troops", {"count": 1}),  # 119
    (3, "deploy_troops", {"count": 1}),  # 120
    (3, "resolve_board_effect", {"effect": "cards"}),  # 121
    (3, "withdraw_troops", {"count": 1}),  # 122
    (3, "deploy_troops", {"count": 1}),  # 123
    (3, "withdraw_troops", {"count": 2}),  # 124
    (3, "deploy_troops", {"count": 2}),  # 125
    (3, "finish_agent_turn", {}),  # 126
    (
        0,
        "choose_agent_card",
        {"card_id": "player:0:starter:dune_the_desert_planet:1"},
    ),  # 127
    (0, "place_agent", {"space_id": "imperial_basin"}),  # 128
    (0, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 129
    (0, "deploy_troops", {"count": 1}),  # 130
    (0, "withdraw_troops", {"count": 1}),  # 131
    (0, "deploy_troops", {"count": 2}),  # 132
    (0, "withdraw_troops", {"count": 1}),  # 133
    (0, "withdraw_troops", {"count": 1}),  # 134
    (0, "finish_agent_turn", {}),  # 135
    (1, "reveal_turn", {}),  # 136
    (1, "acquire_imperium", {"instance_id": "imperium:crysknife_card:0"}),  # 137
    (1, "finish_reveal", {}),  # 138
    (2, "reveal_turn", {}),  # 139
    (2, "finish_reveal", {}),  # 140
    (3, "reveal_turn", {}),  # 141
    (
        3,
        "acquire_imperium",
        {"instance_id": "imperium:bene_gesserit_initiate:1"},
    ),  # 142
    (3, "finish_reveal", {}),  # 143
    (0, "reveal_turn", {}),  # 144
    (0, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 145
    (0, "finish_reveal", {}),  # 146
    (1, "pass_combat_intrigue", {}),  # 147
    (2, "pass_combat_intrigue", {}),  # 148
    # Round 2's Combat: seat 3 plays Strategic Push (checkpoint 150); seat 0
    # wins alone (161: its window open); round 3 starts (167).
    (3, "play_intrigue", {"card_id": "intrigue:strategic_push:0", "option": 0}),  # 149
    (3, "pass_combat_intrigue", {}),  # 150
    (0, "pass_combat_intrigue", {}),  # 151
    (1, "pass_combat_intrigue", {}),  # 152
    (2, "pass_combat_intrigue", {}),  # 153
    (3, "play_intrigue", {"card_id": "intrigue:staged_incident:0", "option": 0}),  # 154
    (3, "lose_intrigue_troop", {"zone": "conflict"}),  # 155
    (3, "lose_intrigue_troop", {"zone": "conflict"}),  # 156
    (3, "lose_intrigue_troop", {"zone": "conflict"}),  # 157
    (0, "pass_combat_intrigue", {}),  # 158
    (1, "pass_combat_intrigue", {}),  # 159
    (2, "pass_combat_intrigue", {}),  # 160
    (0, "resolve_combat_reward_icon", {"effect": "victory_points"}),  # 161
    (0, "resolve_combat_reward_icon", {"effect": "control"}),  # 162
    (0, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 163
    (1, "resolve_combat_reward_icon", {"effect": "resources"}),  # 164
    (2, "resolve_combat_reward_icon", {"effect": "resources"}),  # 165
    (2, "choose_agent_card", {"card_id": "player:2:starter:reconnaissance:0"}),  # 166
]

# (seat, action id, arguments), in order; the number after each is its index.
COURT_PLAN: list[Step] = [
    # Seat 2 buys Court Intrigue in round 1 (12) and gets two Intrigue cards by
    # round 3.
    (3, "choose_masterstroke_faction", {"faction": "bene_gesserit"}),  # 0
    (3, "choose_masterstroke_faction", {"faction": "spacing_guild"}),  # 1
    (0, "choose_agent_card", {"card_id": "player:0:starter:signet_ring:0"}),  # 2
    (0, "place_agent", {"space_id": "smuggling"}),  # 3
    (0, "advance_board_freighter", {}),  # 4
    (0, "resolve_board_effect", {"effect": "resources"}),  # 5
    (0, "resolve_agent_card_effect", {}),  # 6
    (0, "finish_agent_turn", {}),  # 7
    (1, "choose_agent_card", {"card_id": "player:1:starter:dagger:1"}),  # 8
    (1, "place_agent", {"space_id": "tech_negotiation"}),  # 9
    (1, "finish_agent_turn", {}),  # 10
    (2, "reveal_turn", {}),  # 11
    (2, "acquire_imperium", {"instance_id": "imperium:court_intrigue:0"}),  # 12
    (2, "finish_reveal", {}),  # 13
    (3, "choose_agent_card", {"card_id": "player:3:starter:reconnaissance:0"}),  # 14
    (3, "place_agent", {"space_id": "arrakeen"}),  # 15
    (3, "resolve_board_effect", {"effect": "troops"}),  # 16
    (3, "deploy_troops", {"count": 2}),  # 17
    (3, "deploy_troops", {"count": 1}),  # 18
    (3, "resolve_board_effect", {"effect": "cards"}),  # 19
    (3, "finish_agent_turn", {}),  # 20
    (0, "reveal_turn", {}),  # 21
    (0, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 22
    (0, "acquire_imperium", {"instance_id": "imperium:the_voice:0"}),  # 23
    (0, "finish_reveal", {}),  # 24
    (1, "choose_agent_card", {"card_id": "player:1:starter:reconnaissance:0"}),  # 25
    (1, "place_agent", {"space_id": "carthag"}),  # 26
    (1, "deploy_troops", {"count": 2}),  # 27
    (1, "resolve_board_effect", {"effect": "intrigue"}),  # 28
    (1, "resolve_board_effect", {"effect": "troops"}),  # 29
    (1, "deploy_troops", {"count": 1}),  # 30
    (1, "finish_agent_turn", {}),  # 31
    (3, "reveal_turn", {}),  # 32
    (3, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 33
    (3, "finish_reveal", {}),  # 34
    (1, "reveal_turn", {}),  # 35
    (1, "acquire_imperium", {"instance_id": "imperium:jamis:0"}),  # 36
    (1, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 37
    (1, "finish_reveal", {}),  # 38
    (1, "pass_combat_intrigue", {}),  # 39
    (3, "pass_combat_intrigue", {}),  # 40
    (3, "resolve_combat_reward_icon", {"effect": "freighter"}),  # 41
    (3, "advance_freighter", {}),  # 42
    (3, "resolve_combat_reward_icon", {"effect": "troops"}),  # 43
    (3, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 44
    (1, "resolve_combat_reward_icon", {"effect": "resources"}),  # 45
    (1, "choose_agent_card", {"card_id": "player:1:starter:seek_allies:0"}),  # 46
    (1, "place_agent", {"space_id": "stillsuits"}),  # 47
    (1, "deploy_troops", {"count": 1}),  # 48
    (1, "resolve_board_effect", {"effect": "resources"}),  # 49
    (1, "resolve_faction_influence", {}),  # 50
    (1, "resolve_agent_card_effect", {}),  # 51
    (1, "finish_agent_turn", {}),  # 52
    (
        2,
        "choose_agent_card",
        {"card_id": "player:2:starter:dune_the_desert_planet:0"},
    ),  # 53
    (2, "place_agent", {"space_id": "smuggling"}),  # 54
    (2, "advance_board_freighter", {}),  # 55
    (2, "resolve_board_effect", {"effect": "resources"}),  # 56
    (2, "finish_agent_turn", {}),  # 57
    (3, "reveal_turn", {}),  # 58
    (3, "acquire_imperium", {"instance_id": "imperium:weirding_way:0"}),  # 59
    (3, "finish_reveal", {}),  # 60
    (0, "reveal_turn", {}),  # 61
    (0, "acquire_imperium", {"instance_id": "imperium:sardaukar_legion:1"}),  # 62
    (0, "finish_reveal", {}),  # 63
    (
        1,
        "choose_agent_card",
        {"card_id": "player:1:starter:dune_the_desert_planet:1"},
    ),  # 64
    (1, "place_agent", {"space_id": "imperial_basin"}),  # 65
    (1, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 66
    (1, "finish_agent_turn", {}),  # 67
    (2, "choose_agent_card", {"card_id": "player:2:starter:reconnaissance:0"}),  # 68
    (2, "place_agent", {"space_id": "carthag"}),  # 69
    (2, "resolve_board_effect", {"effect": "troops"}),  # 70
    (2, "deploy_troops", {"count": 3}),  # 71
    (2, "resolve_board_effect", {"effect": "intrigue"}),  # 72
    (2, "play_intrigue", {"card_id": "intrigue:urgent_mission:0", "option": 0}),  # 73
    (2, "recall_agent_for_intrigue", {"space_id": "smuggling"}),  # 74
    (2, "finish_agent_turn", {}),  # 75
    (1, "reveal_turn", {}),  # 76
    (1, "finish_reveal", {}),  # 77
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:1"}),  # 78
    (2, "place_agent", {"space_id": "mentat"}),  # 79
    (2, "resolve_board_effect", {"effect": "mentat"}),  # 80
    (2, "resolve_board_effect", {"effect": "cards"}),  # 81
    (2, "finish_agent_turn", {}),  # 82
    (2, "reveal_turn", {}),  # 83
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 84
    (2, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 85
    (2, "finish_reveal", {}),  # 86
    (1, "pass_combat_intrigue", {}),  # 87
    (2, "pass_combat_intrigue", {}),  # 88
    (2, "resolve_combat_reward_icon", {"effect": "intrigue"}),  # 89
    (2, "resolve_combat_reward_icon", {"effect": "choose_influence"}),  # 90
    (2, "choose_combat_reward_influence", {"faction": "spacing_guild"}),  # 91
    (2, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 92
    (1, "resolve_combat_reward_icon", {"effect": "intrigue"}),  # 93
    (1, "resolve_combat_reward_icon", {"effect": "resources"}),  # 94
    # Round 3: seat 2 sends Court Intrigue to Wealth holding Refocus and Quid
    # Pro Quo (checkpoint 97), puts Refocus under the Intrigue deck (98), draws
    # the top card (99), plays it and ends its turn; seat 3 decides (103).
    (2, "choose_agent_card", {"card_id": "imperium:court_intrigue:0"}),  # 95
    (2, "place_agent", {"space_id": "wealth"}),  # 96
    (
        2,
        "put_intrigue_on_bottom_for_agent_card",
        {"intrigue_card_id": "intrigue:refocus:0"},
    ),  # 97
    (2, "resolve_agent_card_effect", {"effect": "intrigue"}),  # 98
    (
        2,
        "play_intrigue",
        {"card_id": "intrigue:dispatch_an_envoy:0", "option": 0},
    ),  # 99
    (2, "resolve_faction_influence", {}),  # 100
    (2, "resolve_board_effect", {"effect": "resources"}),  # 101
    (2, "finish_agent_turn", {}),  # 102
]

# (seat, action id, arguments), in order; the number after each is its index.
WEIRDING_PLAN: list[Step] = [
    # Seat 0 buys Weirding Way in round 2 (20).
    (3, "choose_masterstroke_faction", {"faction": "bene_gesserit"}),  # 0
    (3, "choose_masterstroke_faction", {"faction": "spacing_guild"}),  # 1
    (2, "choose_agent_card", {"card_id": "player:2:starter:dagger:0"}),  # 2
    (2, "place_agent", {"space_id": "tech_negotiation"}),  # 3
    (2, "finish_agent_turn", {}),  # 4
    (3, "reveal_turn", {}),  # 5
    (3, "acquire_reserve", {"card_id": "arrakis_liaison"}),  # 6
    (3, "acquire_imperium", {"instance_id": "imperium:bene_gesserit_initiate:1"}),  # 7
    (3, "finish_reveal", {}),  # 8
    (0, "reveal_turn", {}),  # 9
    (0, "finish_reveal", {}),  # 10
    (1, "reveal_turn", {}),  # 11
    (1, "acquire_imperium", {"instance_id": "imperium:gun_thopter:1"}),  # 12
    (1, "finish_reveal", {}),  # 13
    (2, "reveal_turn", {}),  # 14
    (2, "acquire_imperium", {"instance_id": "imperium:sardaukar_legion:0"}),  # 15
    (2, "finish_reveal", {}),  # 16
    (3, "reveal_turn", {}),  # 17
    (3, "finish_reveal", {}),  # 18
    (0, "reveal_turn", {}),  # 19
    (0, "acquire_imperium", {"instance_id": "imperium:weirding_way:0"}),  # 20
    (0, "acquire_imperium", {"instance_id": "imperium:spice_hunter:0"}),  # 21
    (0, "finish_reveal", {}),  # 22
    (1, "choose_agent_card", {"card_id": "player:1:starter:dagger:0"}),  # 23
    (1, "place_agent", {"space_id": "tech_negotiation"}),  # 24
    (1, "place_board_negotiator", {}),  # 25
    (1, "finish_agent_turn", {}),  # 26
    (2, "choose_agent_card", {"card_id": "player:2:starter:diplomacy:0"}),  # 27
    (2, "place_agent", {"space_id": "hardy_warriors"}),  # 28
    (2, "deploy_troops", {"count": 2}),  # 29
    (2, "resolve_board_effect", {"effect": "troops"}),  # 30
    (2, "deploy_troops", {"count": 2}),  # 31
    (2, "resolve_faction_influence", {}),  # 32
    (2, "finish_agent_turn", {}),  # 33
    (1, "choose_agent_card", {"card_id": "player:1:starter:reconnaissance:0"}),  # 34
    (1, "place_agent", {"space_id": "carthag"}),  # 35
    (1, "deploy_troops", {"count": 1}),  # 36
    (1, "resolve_board_effect", {"effect": "intrigue"}),  # 37
    (1, "deploy_troops", {"count": 1}),  # 38
    (1, "resolve_board_effect", {"effect": "troops"}),  # 39
    (1, "deploy_troops", {"count": 1}),  # 40
    (1, "finish_agent_turn", {}),  # 41
    (
        2,
        "choose_agent_card",
        {"card_id": "player:2:starter:dune_the_desert_planet:0"},
    ),  # 42
    (2, "place_agent", {"space_id": "imperial_basin"}),  # 43
    (2, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 44
    (2, "finish_agent_turn", {}),  # 45
    (1, "reveal_turn", {}),  # 46
    (1, "acquire_imperium", {"instance_id": "imperium:desert_ambush:0"}),  # 47
    (1, "finish_reveal", {}),  # 48
    (2, "reveal_turn", {}),  # 49
    (2, "acquire_imperium", {"instance_id": "imperium:crysknife_card:0"}),  # 50
    (2, "finish_reveal", {}),  # 51
    (1, "pass_combat_intrigue", {}),  # 52
    (2, "pass_combat_intrigue", {}),  # 53
    (2, "resolve_combat_reward_icon", {"effect": "troops"}),  # 54
    (2, "resolve_combat_reward_icon", {"effect": "freighter"}),  # 55
    (2, "decline_freighter", {}),  # 56
    (2, "resolve_combat_reward_icon", {"effect": "freighter"}),  # 57
    (2, "decline_freighter", {}),  # 58
    (2, "resolve_combat_reward_icon", {"effect": "winning_intrigue"}),  # 59
    (1, "resolve_combat_reward_icon", {"effect": "resources"}),  # 60
    (1, "resolve_combat_reward_icon", {"effect": "intrigue"}),  # 61
    # Round 2: seat 0 sends Weirding Way to Imperial Basin and takes the extra
    # turn (checkpoint 65), ends its turn (68: its extra turn opens), reveals
    # in it, and seat 1 decides (70).
    (0, "choose_agent_card", {"card_id": "imperium:weirding_way:0"}),  # 62
    (0, "place_agent", {"space_id": "imperial_basin"}),  # 63
    (0, "take_agent_card_extra_turn", {}),  # 64
    (0, "deploy_troops", {"count": 1}),  # 65
    (0, "harvest_maker_spice", {"space_id": "imperial_basin"}),  # 66
    (0, "finish_agent_turn", {}),  # 67
    (0, "reveal_turn", {}),  # 68
    (0, "finish_reveal", {}),  # 69
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
NEGOTIATOR_PENDING = {**DISCOUNT_PENDING, "negotiators_returnable": 1}
SHIPPING_PENDING = {**EMPTY_PENDING, "shipping_rewards": [1]}
SECRET_CARD = "intrigue:private_army:1"
KNOWN_BOTTOM = [[0, SECRET_CARD]]
PEEKED = ["intrigue:gruesome_sacrifice:1", "intrigue:imperium_politics:0"]
KEPT = "intrigue:gruesome_sacrifice:1"
TOP_CARD = "intrigue:imperium_politics:0"
HUNDRO_PEEKED = ["intrigue:know_their_ways:0", "intrigue:charisma:0"]
HUNDRO_KEPT = "intrigue:know_their_ways:0"
HUNDRO_TOP = "intrigue:charisma:0"
# The top card of a 56-card deck is 55 above the bottom one (as table 2's).
HUNDRO_KNOWS = {
    "known_intrigue_top": HUNDRO_TOP,
    "known_intrigue_bottom": [[55, HUNDRO_TOP]],
}
SET_ASIDE = "player:0:starter:dune_the_desert_planet:1"
TWIN_SET_ASIDE = "player:0:starter:reconnaissance:0"
FIRST_SET_ASIDE = "player:0:starter:dagger:1"
COURT_ROW = "put_intrigue_on_bottom_for_agent_card"
COURT_PUT = "intrigue:refocus:0"
COURT_KEPT = "intrigue:quid_pro_quo:0"
WEIRDING_WAY = "imperium:weirding_way:0"
# What differs between two games of one table whatever was picked: the game's
# id (``gameId`` in a page's state) and log epoch, the play clock, who is
# online, the doorbell's sequence.
VOLATILE = frozenset(
    {"game_id", "gameId", "epoch", "clock", "clock_age_ms", "online", "seq"}
)

IX_TABLE = Table(
    "original + Rise of Ix",
    IX_BODY,
    IX_PLAN,
    {
        39: Checkpoint(
            "seat 0 recalled its Freighter from step 1: the step-1 reward is owed",
            {0: {"ix_pending": SHIPPING_PENDING}},
        ),
        93: Checkpoint(
            "Acquire Tech open for seat 2 (Tech Negotiation, Tech Discount 1, spice)",
            {2: {"ix_pending": DISCOUNT_PENDING}},
        ),
        115: Checkpoint(
            "seat 2 put an Intrigue card at the deck's bottom (Sonic Snoopers)",
            {2: {"known_intrigue_bottom": KNOWN_BOTTOM}},
        ),
        219: Checkpoint(
            "Acquire Tech open for seat 3 (Tech Negotiation, Tech Discount 1, spice,"
            " one Negotiator returnable); seat 2 still knows its bottom card",
            {
                2: {"known_intrigue_bottom": KNOWN_BOTTOM},
                3: {"ix_pending": NEGOTIATOR_PENDING},
            },
        ),
        221: Checkpoint(
            "seat 3 declined the Tech and ended its turn; seat 2 still knows its"
            " bottom card",
            {2: {"known_intrigue_bottom": KNOWN_BOTTOM}},
        ),
    },
    # Seat 2 knows its bottom card; it ends its turn (121) and seat 3 decides.
    (Handover(shown=115, owner=2, passed=121, viewer=3),),
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
                " top card and holds the other",
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
                (24, "seat 3's Reveal turn"),
                (27, "Ilesa's first Agent turn"),
                (30, "Hundro's Reveal turn"),
            )
        },
        33: Checkpoint(
            "Ilesa's second turn starts: her card is back in her hand, public;"
            " Hundro still knows the top card and holds the other",
            {1: HUNDRO_KNOWS},
            {0: [SET_ASIDE], 1: [HUNDRO_KEPT]},
            public={SET_ASIDE: (0, "hand_public")},
            events=[("card_returned_to_hand", {"card_id": SET_ASIDE, "player": 0})],
            aside={0: "returned"},
            sealed=[
                ("keep_peeked_intrigue", "instance_id", HUNDRO_KEPT),
                ("set_aside_leader_card", "card_id", SET_ASIDE),
            ],
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
    # and two Convincing Arguments; the plan plays Dagger 1 before 33, so the
    # twin sets Reconnaissance 0 aside (another card, another name).
    Twin(
        index=6,
        step=(0, "set_aside_leader_card", {"card_id": TWIN_SET_ASIDE}),
        owner=0,
        first=7,
        last=32,
        secret=SET_ASIDE,
    ),
)
FIRST_TABLE = Table(
    "original + Rise of Ix, Ilesa first",
    FIRST_BODY,
    FIRST_PLAN,
    {
        6: Checkpoint(
            "Ilesa, the first player, set a card aside: her first turn has started"
            " (its start still open, P4 2a8bc1ea); the card is hers alone",
            {0: {"set_aside_card_id": FIRST_SET_ASIDE}},
            aside={0: "aside"},
            sealed=[("set_aside_leader_card", "card_id", FIRST_SET_ASIDE)],
        ),
        # "라운드 첫 turn에 Reveal을 하면 따로 둔 카드를 공개 카드에 더한다"
        # (docs/rules/rise-of-ix.md 9.1, [Rise of Ix p. 10]).
        7: Checkpoint(
            "Ilesa revealed in her first turn: her set-aside card is among her"
            " revealed cards, public",
            {},
            public={FIRST_SET_ASIDE: (0, "in_play")},
            events=[
                ("card_returned_to_hand", {"card_id": FIRST_SET_ASIDE, "player": 0}),
                ("cards_revealed", {"player": 0}),
            ],
            sealed=[("set_aside_leader_card", "card_id", FIRST_SET_ASIDE)],
        ),
    },
    (),
    # Her hand then is Diplomacy 0, Reconnaissance 0, two Dune, the Desert
    # Planets and Dagger 1: the twin sets Reconnaissance 0 aside.
    Twin(
        index=5,
        step=(0, "set_aside_leader_card", {"card_id": TWIN_SET_ASIDE}),
        owner=0,
        first=6,
        last=6,
        secret=FIRST_SET_ASIDE,
    ),
)
DISPOSAL_TABLE = Table(
    "original + Rise of Ix, Disposal Facility",
    DISPOSAL_BODY,
    DISPOSAL_PLAN,
    {
        303: Checkpoint(
            "seat 2 took Disposal Facility with Machine Culture in its Reveal turn"
            " and chose the acquire box's trash: both of the tile's trashes are on"
            " offer (they shared their steps until P4 b806b3db)",
            {},
            offered={2: ["trash_optional_card", "trash_disposal_facility_card"]},
        ),
        304: Checkpoint(
            "seat 2 trashed a card with the acquire box; the Reveal ability's trash"
            " is still on offer",
            {},
            offered={2: ["trash_disposal_facility_card"]},
        ),
    },
    (),
)
STRATEGIC_TABLE = Table(
    "original + Rise of Ix, Strategic Push",
    STRATEGIC_BODY,
    STRATEGIC_PLAN,
    {
        # "+2 swords. If you win this Conflict: 2 Solari" [Strategic Push card,
        # Steam app text]; the pledge is public (P4 f6d3e996) and paid as a row
        # of the sole winner's window (docs/rules/rise-of-ix.md 12 "승자의 창",
        # OQ-121 ruling 6 (1)).
        54: Checkpoint(
            "seat 3 played Strategic Push: its 2 Solari pledge shows on its panel"
            " to every seat",
            {},
            pledges={3: 2},
        ),
        57: Checkpoint(
            "seat 3 won the Conflict alone: its window offers the pledge's row",
            {},
            offered={3: [("resolve_combat_reward_icon", {"effect": "strategic_push"})]},
            pledges={3: 2},
        ),
        58: Checkpoint(
            "seat 3 took the row: 2 Solari, and the pledge is spent",
            {},
            events=[
                (
                    "resources_gained",
                    {
                        "player": 3,
                        "solari": 2,
                        "source": "round:1:combat_reward:3:1:strategic_push",
                    },
                )
            ],
        ),
        62: Checkpoint(
            "the Combat is over and round 2 has started: no pledge anywhere", {}
        ),
    },
    (),
)
LOST_PUSH_TABLE = Table(
    "original + Rise of Ix, Strategic Push lost",
    LOST_PUSH_BODY,
    LOST_PUSH_PLAN,
    {
        150: Checkpoint(
            "seat 3 played Strategic Push: its 2 Solari pledge shows on its panel",
            {},
            pledges={3: 2},
        ),
        # The pledge is "If you win this Conflict:": another seat's win pays
        # nothing, and the pledge waits until the Combat is cleaned up
        # (``combat.finish_combat``).
        161: Checkpoint(
            "seat 0 won the Conflict: its window is open, seat 3's pledge still shows",
            {},
            pledges={3: 2},
        ),
        167: Checkpoint(
            "the Combat is cleaned up and round 3 has started: the pledge is gone",
            {},
        ),
    },
    (),
)
# Court Intrigue: "Intrigue를 덱 맨 아래에 놓을 때 상대에게 보이지 않는다"
# (docs/rules/rise-of-ix.md 9.1, [Rise of Ix p. 10]); the seat that put it
# there knows the card, the others do not (rise-of-ix.md 13, OQ-149); the
# draw from the top is its own step (OQ-106).
COURT_KNOWN = [[0, COURT_PUT]]
COURT_TABLE = Table(
    "original + Rise of Ix, Court Intrigue",
    COURT_BODY,
    COURT_PLAN,
    {
        97: Checkpoint(
            "seat 2 sent Court Intrigue to Wealth holding two Intrigue cards: the"
            " rows naming them are its own",
            {},
            hands={2: [COURT_PUT, COURT_KEPT]},
            offered={
                2: [
                    (COURT_ROW, {"intrigue_card_id": COURT_PUT}),
                    (COURT_ROW, {"intrigue_card_id": COURT_KEPT}),
                ]
            },
        ),
        98: Checkpoint(
            "seat 2 put one under the Intrigue deck: it alone knows the bottom"
            " card, the others see the count and (비공개) in the log",
            {2: {"known_intrigue_bottom": COURT_KNOWN}},
            hands={2: [COURT_KEPT]},
            offered={2: [("resolve_agent_card_effect", {"effect": "intrigue"})]},
            events=[("intrigue_put_on_bottom", {"player": 2, "count": 1})],
            sealed=[(COURT_ROW, "intrigue_card_id", COURT_PUT)],
        ),
        99: Checkpoint(
            "seat 2 drew the top card: the bottom one stays its own knowledge",
            {2: {"known_intrigue_bottom": COURT_KNOWN}},
            hands={2: [COURT_KEPT]},
            sealed=[(COURT_ROW, "intrigue_card_id", COURT_PUT)],
        ),
        103: Checkpoint(
            "seat 2 ended its turn and seat 3 decides: seat 2 still knows the"
            " bottom card",
            {2: {"known_intrigue_bottom": COURT_KNOWN}},
            hands={2: [COURT_KEPT]},
            sealed=[(COURT_ROW, "intrigue_card_id", COURT_PUT)],
            turn=3,
        ),
    },
    # Seat 2 knows its bottom card; it ends its turn (103) and seat 3 decides.
    (Handover(shown=98, owner=2, passed=103, viewer=3),),
    # The twin puts Quid Pro Quo under the deck and keeps Refocus.
    Twin(
        index=97,
        step=(2, COURT_ROW, {"intrigue_card_id": COURT_KEPT}),
        owner=2,
        first=98,
        last=103,
        secret=COURT_PUT,
    ),
)
# Weirding Way: "You may take another turn immediately after this one"
# [Weirding Way card, Steam app text]; the extra turn is an option of the Agent
# turn (OQ-095 (2)), and once its turn closes the same seat's next turn opens
# at once (P4 32198e3c).
WEIRDING_TABLE = Table(
    "original + Rise of Ix, Weirding Way",
    WEIRDING_BODY,
    WEIRDING_PLAN,
    {
        65: Checkpoint(
            "seat 0 sent Weirding Way to Imperial Basin and took the extra turn:"
            " every page's log says so, and the turn is still its first",
            {},
            events=[("extra_turn_taken", {"player": 0})],
            turn=0,
            turn_cards=[WEIRDING_WAY],
            log_lines=["extra_turn_taken"],
        ),
        68: Checkpoint(
            "seat 0 ended its turn: its extra turn opens at once, still seat 0's"
            " (an Agent card or its Reveal on offer), with no card of its own yet",
            {},
            offered={0: ["choose_agent_card", "reveal_turn"]},
            turn=0,
            turn_cards=[],
            log_lines=["extra_turn_taken"],
            log_tail=[0],
        ),
        70: Checkpoint(
            "seat 0 revealed in its extra turn and seat 1 decides: the log shows"
            " seat 0's two turns as two cards in a row",
            {},
            turn=1,
            turn_cards=[],
            log_lines=["extra_turn_taken"],
            log_tail=[0, 0],
        ),
    },
    (),
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
    pledge: t("panels.strategic_push", {solari: args.pledge}),
    pledgeHead: head("panels.strategic_push", {solari: mark}),
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


# Whose turn the page shows: the active seat panels, the "this turn" chips, the
# seat of each turn card of the log (by its border, ``turnCard``) with its
# event kinds, and the log lines of ``kinds`` with the words they must hold.
TURN_JS = """(kinds) => {
  const probe = document.createElement("div");
  const rgb = (color) => {
    probe.style.borderLeftColor = "";
    probe.style.borderLeftColor = color;
    return probe.style.borderLeftColor;
  };
  const seats = SEAT_COLORS.map(rgb);
  const norm = (s) => s.replace(/\\s+/g, " ").trim();
  return {
    active: [...document.querySelectorAll("#seats .seat.active")]
      .map((card) => card.dataset.seat),
    thisTurn: document.querySelectorAll("#seats .this-turn").length,
    cards: [...document.querySelectorAll("#action-log .turn-card:not(.neutral)")]
      .map((card) => ({
        seat: seats.indexOf(card.style.borderLeftColor),
        kinds: [...card.querySelectorAll(".logevent")]
          .map((line) => line.dataset.eventKind),
      })),
    lines: Object.fromEntries(kinds.map((kind) => [kind, {
      words: phraseText(EVENT_LABELS[kind] || ""),
      shown: [...document.querySelectorAll(
        `#action-log .logevent[data-event-kind="${kind}"]`,
      )].map((line) => norm(line.textContent)),
    }])),
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
        "pledge": 0,
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


def document_leaks(
    page, cards: list[str], state_text: str
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """What ``page``'s document holds of ``cards``, cards it may not know: the
    marks of each found in its markup or text, and apart from them the finds a
    copy explains. Another copy of the same card that the page's state names
    (one the seat holds, or a public one) shows the same name and picture, so
    a find of those alone says nothing of the tracked copy and is set apart
    with the copies named; a find of the tracked card's own id never is (the
    id checks, and a twin where the table has one, still cover it)."""
    if not cards:
        return {}, {}
    html, text = page.evaluate(DOCUMENT_JS)
    leaks: dict[str, list[str]] = {}
    explained: dict[str, list[str]] = {}
    for card, hits in marks_found(page, cards, html, text).items():
        kind = card.rsplit(":", 1)[0]
        copies = set(re.findall(re.escape(kind) + r":\d+", state_text)) - {card}
        if card in hits or not copies:
            leaks[card] = hits
        else:
            explained[card] = [*hits, *(f"copy {copy}" for copy in sorted(copies))]
    return leaks, explained


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


def stream_data(status: int, text: str) -> list[Any]:
    """An event stream message's status and data, parsed."""
    data = [line for line in text.splitlines() if line.startswith("data: ")]
    return [status, [json.loads(line.removeprefix("data: ")) for line in data]]


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
        for card, (holder, zone) in point.public.items():
            shown = view["players"][holder][zone]
            check.ok(
                card in shown,
                f"{label}: seat {seat}'s view shows {card} in seat {holder}'s {zone}",
                shown,
            )
        rows = data["actions"]["actions"]
        for wanted in point.offered.get(seat, []):
            action_id, arguments = (wanted, {}) if isinstance(wanted, str) else wanted
            check.ok(
                any(
                    row["action_id"] == action_id
                    and all(
                        (row["arguments"] or {}).get(k) == v
                        for k, v in arguments.items()
                    )
                    for row in rows
                ),
                f"{label}: seat {seat}'s own actions offer {action_id}"
                + (f" {arguments}" if arguments else ""),
                [(row["action_id"], row["arguments"]) for row in rows][:8],
            )
        pledged = [player["strategic_push_solari"] for player in view["players"]]
        check.ok(
            pledged == [point.pledges.get(holder, 0) for holder in range(4)],
            f"{label}: seat {seat}'s view shows the Strategic Push pledges"
            f" {point.pledges or 'none'}",
            pledged,
        )
        if point.turn is not None:
            decision = snapshot["summary"]["decision"]
            check.ok(
                decision is not None and decision["owner"] == point.turn,
                f"{label}: seat {seat}'s snapshot says it is seat {point.turn}'s turn",
                decision,
            )
        if point.turn_cards is not None:
            check.ok(
                view["turn_card_ids"] == point.turn_cards,
                f"{label}: seat {seat}'s view names the open turn's cards"
                f" {point.turn_cards or '(none)'}",
                view["turn_card_ids"],
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
        leaks, explained = document_leaks(page, unknown, shown["stateText"])
        check.ok(
            not leaks,
            f"{tag}: seat {seat}'s document holds no id, name or picture of"
            f" {unknown or 'a card'} it may not know"
            + (
                f" (the name and picture of {sorted(explained)} are also those of a"
                " copy it sees)"
                if explained
                else ""
            ),
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
        # Strategic Push's pledge, public: on the pledging seat's panel only.
        pledge_words = page.evaluate(
            WORDS_JS,
            {**word_args(mine), "pledge": max(point.pledges.values(), default=0)},
        )
        for holder in range(4):
            panel = shown["panels"][str(holder)]
            if point.pledges.get(holder):
                if pledge_words["pledge"] not in panel:
                    wrong.append(
                        f"seat {holder}'s panel lacks {pledge_words['pledge']}"
                    )
            elif pledge_words["pledgeHead"] in panel:
                wrong.append(f"seat {holder}'s panel shows a pledge")
        if flag_own := (point.aside.get(seat) == "aside"):
            if words["setAsideOwn"] not in own_panel:
                wrong.append(f"own panel lacks {words['setAsideOwn']}")
        check.ok(
            not wrong,
            f"{tag}: seat {seat}'s page shows the set-aside flags"
            f" {point.aside or 'none'}"
            + (" with its own card" if flag_own else "")
            + f" and the pledges {point.pledges or 'none'}",
            wrong,
        )
        if (
            point.turn is not None
            or point.turn_cards is not None
            or point.log_lines
            or point.log_tail
        ):
            turn = page.evaluate(TURN_JS, point.log_lines)
            tail = [card["seat"] for card in turn["cards"]][-len(point.log_tail) :]
            check.ok(
                (point.turn is None or turn["active"] == [str(point.turn)])
                and (
                    point.turn_cards is None
                    or turn["thisTurn"] == len(point.turn_cards)
                )
                and (not point.log_tail or tail == point.log_tail)
                and all(
                    line["words"]
                    and any(line["words"] in shown for shown in line["shown"])
                    for line in turn["lines"].values()
                ),
                f"{tag}: seat {seat}'s page shows "
                + ", ".join(
                    part
                    for part in (
                        f"seat {point.turn}'s panel as the active one"
                        if point.turn is not None
                        else "",
                        f"{len(point.turn_cards)} 'this turn' chips"
                        if point.turn_cards is not None
                        else "",
                        f"the log lines {point.log_lines}" if point.log_lines else "",
                        f"the last turn cards of seats {point.log_tail}"
                        if point.log_tail
                        else "",
                    )
                    if part
                ),
                {**turn, "tail": tail},
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
            "pledge": 0,
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
    leaks, explained = document_leaks(spectator, hidden, shown["stateText"])
    check.ok(
        not leaks and not explained,
        f"{tag}: the spectator's document holds no id, name or picture of {hidden}",
        (leaks, explained),
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
            leaks, explained = document_leaks(page, unknown, shown["stateText"])
            check.ok(
                bool(unknown) and not leaks,
                f"{table.name} [{language}]: seat {handover.viewer}'s document holds"
                f" no trace of {unknown}"
                + (
                    f" (the name and picture of {sorted(explained)} are also those"
                    " of a copy it sees)"
                    if explained
                    else ""
                ),
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
            # The pages first catch up, so that each one's state is of this
            # action: its whole state (catalog aside) and the event stream's
            # message are compared with the payloads.
            check.ok(
                converge(all_pages, game_id, f"twin capture {done}", timeout=15),
                f"after {done} every page has caught up before the capture",
            )
            captured[done] = {
                name: steady(
                    {
                        **{
                            key: [status, body]
                            for key, (status, body) in reader_payloads(
                                page, game_id, seat
                            ).items()
                        },
                        "events": stream_data(*events_text(page, game_id)),
                        "page": json.loads(page.evaluate(PAGE_JS)["stateText"]),
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


TABLES = (
    IX_TABLE,
    CEREMONY_TABLE,
    LEADERS_TABLE,
    FIRST_TABLE,
    DISPOSAL_TABLE,
    STRATEGIC_TABLE,
    LOST_PUSH_TABLE,
    COURT_TABLE,
    WEIRDING_TABLE,
)


def check_original_refuses_immortality(base: str, browser) -> None:
    """The original game takes no Immortality until stage P7, which is why the
    Imperium Ceremony table is an Uprising one."""
    print(f"[{len(TABLES) + 2}] the original game still does not take Immortality")
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
            print(f"[{len(TABLES) + 1}] the twin games")
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
        print(f"[{len(TABLES) + 3}] the hot-seat hand-overs, on an open server")
        with server() as (open_base, open_log):
            for table in (table for table in TABLES if table.handovers):
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
