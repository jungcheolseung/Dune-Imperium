"""Deckbuilding collectors: buys, trashes, and Faction-Bond synergy.

Tips: C1.1/C1.2/C1.4/C1.5/C1.6/C1.7 and the owner's "thin strong deck" H-deck
(``docs/player-tips-for-training.md`` 6.1-6.4) for ``DeckCollector``; the
owner's tip 2 ("buy cards of the Faction your Bond cards pay off", doc 6.6)
for ``BondCollector``.

Engine facts this module relies on -- see the report handed back with this
slice for the full file:line enumeration; summarized here:

- A new personal card enters a seat's zones through exactly two event kinds:
  ``card_acquired`` (``rules/acquisition.py``, seven emit sites) and
  ``tleilaxu_card_acquired`` (``rules/tleilaxu_row.py``, one site). Every
  other zone-touching transition in ``rules/`` moves a card the seat already
  owns (draw, discard, reveal, return-to-hand); none of them add an instance
  ID that was not already in one of ``deck``/``hand``/``discard_pile``/
  ``in_play``. ``reclaimed_forces_acquired`` (Tleilaxu Row's evergreen slot)
  never puts a card in a zone at all -- the card stays in the Row -- so it is
  not a buy.
- ``card_acquired``'s payload carries the plain definitional ``card_id`` and,
  at four of seven sites, a separate ``instance_id``; three Reserve-only sites
  omit it -- ``_acquire_reserve_to_hand_with_solari`` (Agent-turn Solari),
  ``apply_reserve_acquisition`` (Reveal-turn Persuasion) and
  ``acquire_reserve_for_intrigue`` (a free Intrigue/leader/agent-card grant;
  ``rules/acquisition.py`` lines 387, 601, 1288) -- so it is reconstructed
  (see ``_resolve_instance_id``). All three still end their ``event_id`` with
  the new ``reserve:<card>:<copy>`` ID (``next_reserve_instance_id`` mints it
  before the event is built), which is the primary reconstruction path; the
  zone-delta scan is kept only as a fallback. A card acquired to hand during
  the owner's own Reveal turn can move straight to ``in_play`` in the same
  step (``reveal_late_arrivals``/``_late_reveal_one_card``), so the delta
  scan reads ``in_play`` too, not just ``hand``/``discard_pile``.
  ``card_trashed``'s payload names its card under the same ``card_id`` key,
  but there it is already the instance ID (``rules/card_trash.py`` matches it
  straight against ``hand``/``discard_pile``/``in_play``).
- A card's owner keeps it in exactly one of ``deck``, ``hand``,
  ``discard_pile``, ``in_play`` while it is owned; ``trashed`` records a
  history of departed instance IDs but is not itself an ownership zone
  (Reserve copies do not even appear there -- they return to the shared
  stack). ``imperium_set_aside`` (Manipulate's borrowed Row card, not yet
  paid for), ``twisted_deck``/``navigation_*`` (other card types entirely --
  Twisted Intrigue and Navigation cards, not personal Imperium/Reserve/
  Tleilaxu cards) and ``usurped_row_card_id`` (a borrowed Row card that
  "leaves the game when the Agent turn closes" [card face], never owned) are
  therefore excluded from "owned personal cards".
- Usurp (Immortality) grafts an Imperium Row card into play without
  acquiring it (``rules/graft.py``: ``card_grafted`` with ``from_row=True``,
  which also sets the owner's ``usurped_row_card_id``), then trashes it "as
  an ordinary trash" when the Agent turn closes (``resolve_usurp_trash``,
  OQ-054 user ruling 2026-09-08) -- a genuine ``card_trashed`` event on a
  card this seat never bought. The borrowed card can also trash itself
  earlier in the same Agent turn through its own "Trash this card." box
  (``resolve_usurp_trash``'s own docstring: "a card that already left every
  owned zone ... needs nothing more"), so the exclusion is keyed off the
  owner's ``usurped_row_card_id`` field (set at graft, cleared only when the
  turn closes) rather than off any one event pairing -- it catches the
  borrowed card's trash wherever in the turn it happens.
- A card's mandatory "Trash this card." (no arrow, not a chosen cost) is
  excluded from ``trash_chosen`` the same way: Seek Allies
  (``PersonalCardAgentEffect.TRASH_SELF`` [Main p. 20]), Dangerous Rhetoric
  (``TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE``; the trash is one of its two
  printed icons, resolved through the automatic ``trash_self`` icon key --
  player-turns.md / open-questions.md:164) and the Agent-effect variant that
  also gains visited-Faction Influence
  (``GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF``; Subversive
  Advisor -- player-turns.md:103-107, "의무"). The exclusion only fires when
  the trashed instance is the card whose own box is actively resolving (the
  ``card_id`` of the top ``FrameKind.AGENT_EFFECTS`` frame in
  ``s.pre.decision_stack``, which a Graft switch keeps pointed at whichever
  side is active): a Seek Allies (or Dangerous Rhetoric) trashed by an
  unrelated chosen effect -- a combat-reward trash, a Leader Signet trash
  from hand -- is a genuine thinning choice and is counted.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.imperium import (
    imperium_card_for_instance,
    imperium_deck_instance_ids,
)
from dune_imperium.content.uprising.personal_cards import (
    PersonalCardDefinition,
    personal_card_for_instance,
)
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon, PersonalCardAgentEffect
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.evaluation.tournament import MatchSpec
from dune_imperium.rules.card_bonds import has_faction_bond
from dune_imperium.rules.endgame import FinalStanding
from dune_imperium.rules.frames import FrameKind

from .base import Collector, Columns, Step, payload

FACTION_ICONS = frozenset(
    (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
)

# "Trash this card." printed as a sentence (no arrow) is mandatory, not a
# chosen thinning trash [Main p. 20] (docs/rules/open-questions.md:513):
# Seek Allies (TRASH_SELF), Dangerous Rhetoric
# (TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE) and Subversive Advisor
# (GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF, "의무" --
# docs/rules/player-turns.md:103-107).
MANDATORY_SELF_TRASH = frozenset(
    (
        PersonalCardAgentEffect.TRASH_SELF,
        PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE,
        PersonalCardAgentEffect.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF,
    )
)

# A Reserve card's freshly-minted instance ID always ends the event_id of the
# card_acquired event that grants it (see the module docstring): the three
# sites that omit a payload ``instance_id`` still name it in their own
# ``source``/event_id string, built before the event.
_INSTANCE_ID_SUFFIX = re.compile(r"((?:reserve|imperium|tleilaxu):[^:]+:\d+)$")


def _mean(values: list[float]) -> float | None:
    """Arithmetic mean of ``values``, or None for "mean over zero items"."""

    return sum(values) / len(values) if values else None


def _owned_ids(owner: PlayerState) -> tuple[str, ...]:
    """Every personal-card instance ID currently owned by ``owner``.

    Deliberately excludes ``owner.trashed`` (departed, not owned) and every
    other zone discussed in the module docstring.
    """

    return (*owner.deck, *owner.hand, *owner.discard_pile, *owner.in_play)


class DeckCollector(Collector):
    """Buys, trashes, and end-of-game deck composition, per seat."""

    name = "deck"

    def __init__(self, spec: MatchSpec, seats: int) -> None:
        super().__init__(spec, seats)
        self._payment: list[Counter[str]] = [Counter() for _ in range(seats)]
        self._buys_r1_3 = [0] * seats
        self._buys_r4_6 = [0] * seats
        self._buys_r7p = [0] * seats
        self._tleilaxu_buys = [0] * seats
        self._buy_costs: list[list[int]] = [[] for _ in range(seats)]
        self._faction_buys = [0] * seats
        self._faction_buys_r1_3 = [0] * seats
        # One record per acquisition event (not deduped by instance ID: a
        # trashed Reserve copy's ID can be re-issued to a later buy --
        # ``next_reserve_instance_id`` counts down over owned IDs, so a buy,
        # trash and re-buy of the same stack can reuse one ID for two
        # separate cards). Each record is (instance_id, acquired_round,
        # rounds seen in hand after the buy -- a mutable set, added to in
        # place); ``_live`` maps a currently-held instance ID to its open
        # record's index so the hand scan and a trash both find the right
        # one.
        self._buy_records: list[list[tuple[str, int, set[int]]]] = [
            [] for _ in range(seats)
        ]
        self._live: list[dict[str, int]] = [{} for _ in range(seats)]
        self._unresolved_buys = [0] * seats
        self._trash_chosen = [0] * seats
        self._trash_tally: list[Counter[str]] = [Counter() for _ in range(seats)]
        self._trash_starters = [0] * seats
        # Mandatory "Trash this card." resolutions (MANDATORY_SELF_TRASH),
        # excluded from trash_chosen; kept as its own column so the starter
        # count invariant (module docstring / test file) does not have to
        # guess how many occurred.
        self._self_trashes = [0] * seats
        self._first_trash_round: list[int | None] = [None] * seats
        self._prev_hand: list[tuple[str, ...] | None] = [None] * seats

    def step(self, s: Step) -> None:
        for event in s.events:
            if event.kind in ("card_acquired", "tleilaxu_card_acquired"):
                self._record_buy(s, event)
            elif event.kind == "card_trashed":
                self._record_trash(s, event)
        round_no = s.post.round_number
        for p, ps in enumerate(s.post.players):
            hand = ps.hand
            if hand is self._prev_hand[p]:
                continue
            self._prev_hand[p] = hand
            live = self._live[p]
            if not live:
                continue
            records = self._buy_records[p]
            for iid in hand:
                idx = live.get(iid)
                if idx is not None:
                    records[idx][2].add(round_no)

    def _record_buy(self, s: Step, event: GameEvent) -> None:
        data = payload(event)
        player = int(data["player"])
        owner_pre = s.pre.players[player]
        owner_post = s.post.players[player]
        is_tleilaxu = event.kind == "tleilaxu_card_acquired"
        iid = _resolve_instance_id(data, is_tleilaxu, owner_pre, owner_post, event)
        if is_tleilaxu:
            payment_label = "specimens"
            self._tleilaxu_buys[player] += 1
        else:
            payment = data.get("payment")
            if payment is not None:
                payment_label = str(payment)
            elif "destination" in data:
                # acquire_reserve_for_intrigue / acquire_imperium_for_intrigue:
                # a free acquisition granted by an Intrigue/leader/agent-card
                # effect (rules/acquisition.py) -- no Persuasion or Solari
                # changes hands.
                payment_label = "free"
            else:
                # apply_reserve_acquisition / apply_imperium_acquisition /
                # apply_manipulated_acquisition: paid from the Reveal turn's
                # Persuasion pool (rules/acquisition.py).
                payment_label = "persuasion"
        self._payment[player][payment_label] += 1
        round_no = s.pre.round_number
        if round_no <= 3:
            self._buys_r1_3[player] += 1
        elif round_no <= 6:
            self._buys_r4_6[player] += 1
        else:
            self._buys_r7p[player] += 1
        if iid is None:
            self._unresolved_buys[player] += 1
            return
        records = self._buy_records[player]
        records.append((iid, round_no, set()))
        self._live[player][iid] = len(records) - 1
        card = personal_card_for_instance(iid)
        if FACTION_ICONS & set(card.agent_icons):
            self._faction_buys[player] += 1
            if round_no <= 3:
                self._faction_buys_r1_3[player] += 1
        if not is_tleilaxu:
            cost = getattr(card, "acquisition_cost", None)
            if isinstance(cost, int):
                self._buy_costs[player].append(cost)

    def _record_trash(self, s: Step, event: GameEvent) -> None:
        data = payload(event)
        player = int(data["player"])
        iid = str(data["card_id"])  # the instance ID (see module docstring)
        self._live[player].pop(iid, None)
        if iid == s.pre.players[player].usurped_row_card_id:
            # Usurp's borrowed Row card leaving play (module docstring,
            # ``rules/graft.py``): never bought, so not a deckbuilding trash
            # choice either, wherever in the turn it happens.
            return
        card = personal_card_for_instance(iid)
        if card.agent_effect in MANDATORY_SELF_TRASH:
            # Only a mandatory exclusion when THIS card's own box is the one
            # actively resolving (a Graft switch keeps the effect frame's
            # ``card_id`` pointed at whichever side is active -- module
            # docstring): the same card trashed by an unrelated chosen
            # effect (a combat-reward trash, a Leader Signet trash from
            # hand) is a genuine thinning choice.
            resolving = {
                dict(frame.context).get("card_id")
                for frame in s.pre.decision_stack
                if frame.kind == FrameKind.AGENT_EFFECTS
            }
            if iid in resolving:
                self._self_trashes[player] += 1
                return
        self._trash_chosen[player] += 1
        self._trash_tally[player][card.card.card_id] += 1
        if ":starter:" in iid:
            self._trash_starters[player] += 1
        if self._first_trash_round[player] is None:
            self._first_trash_round[player] = s.pre.round_number

    def finish(
        self, final: GameState, standings: tuple[FinalStanding, ...]
    ) -> tuple[list[Columns], Columns]:
        per_seat: list[Columns] = []
        for p in range(self.seats):
            owned = _owned_ids(final.players[p])
            end_starters = sum(1 for iid in owned if ":starter:" in iid)
            end_bought = len(owned) - end_starters
            costs = self._buy_costs[p]
            records = self._buy_records[p]
            exposures: list[float] = [
                float(sum(1 for r in seen if r > acquired_round))
                for _iid, acquired_round, seen in records
            ]
            per_seat.append(
                {
                    # Every card_acquired/tleilaxu_card_acquired event this
                    # seat produced (module docstring): new personal cards
                    # gained by any means.
                    "buys": sum(self._payment[p].values()),
                    "buys_by_payment": dict(self._payment[p]),
                    "buys_r1_3": self._buys_r1_3[p],
                    "buys_r4_6": self._buys_r4_6[p],
                    "buys_r7p": self._buys_r7p[p],
                    # None without Immortality: the Tleilaxu Row does not
                    # exist, so 0 would misreport "bought nothing from a Row
                    # that was there" rather than "there was no Row".
                    "tleilaxu_buys": (
                        self._tleilaxu_buys[p] if self.spec.config.immortality else None
                    ),
                    "buy_cost_mean": _mean([float(c) for c in costs]),
                    "buys_cost5p": sum(1 for c in costs if c >= 5),
                    "faction_buys_r1_3": self._faction_buys_r1_3[p],
                    "faction_buys": self._faction_buys[p],
                    "end_cards": len(owned),
                    "end_starters": end_starters,
                    "end_bought": end_bought,
                    "trash_chosen": self._trash_chosen[p],
                    "trash_starters": self._trash_starters[p],
                    # Mandatory "Trash this card." resolutions this seat's
                    # own cards went through (MANDATORY_SELF_TRASH; module
                    # docstring), excluded from trash_chosen -- Seek Allies
                    # (a starter) and, when bought, Dangerous Rhetoric or
                    # Subversive Advisor (not starters). Every card this seat
                    # ever owned is either still owned or left through one of
                    # trash_chosen/self_trashes, so
                    # ``starting_deck_size + buys == end_cards + trash_chosen
                    # + self_trashes`` exactly (test file).
                    "self_trashes": self._self_trashes[p],
                    "trashed": dict(self._trash_tally[p]),
                    "first_trash_round": self._first_trash_round[p],
                    "exposure": _mean(exposures) if records else None,
                }
            )
        game: Columns = {
            # Buys whose instance ID could not be reconstructed (see
            # ``_resolve_instance_id``); expected to be 0 -- kept visible so
            # a real occurrence is not silently absorbed into "buys" without
            # a trace.
            "unresolved_buys": sum(self._unresolved_buys),
        }
        return per_seat, game


def _resolve_instance_id(
    data: dict[str, object],
    is_tleilaxu: bool,
    owner_pre: PlayerState,
    owner_post: PlayerState,
    event: GameEvent,
) -> str | None:
    """Return the bought instance ID, reconstructing it when the event omits it.

    Four of the seven ``card_acquired`` sites and the one
    ``tleilaxu_card_acquired`` site (unless it went to the deck top) already
    carry ``instance_id``. The exceptions:

    - Tleilaxu-to-deck-top (``rules/tleilaxu_row.py``: "the identity ... is
      named only while it stays public", OQ-010) puts the new card at
      ``deck[0]``; the deck grew by exactly one, so that is it.
    - The three Reserve-only sites without a payload ``instance_id``
      (``rules/acquisition.py::_acquire_reserve_to_hand_with_solari``,
      ``apply_reserve_acquisition``, ``acquire_reserve_for_intrigue`` --
      lines 387, 601, 1288) mint the new ``reserve:<card_id>:<copy>`` ID
      (``next_reserve_instance_id``) before building the event and always
      end its own ``event_id`` with that ID, which is read directly. The
      zone-delta scan (hand/discard/in_play before vs after) is kept only as
      a fallback for an event_id shape this does not recognize: a card
      acquired to hand during the owner's own Reveal turn can move straight
      to ``in_play`` in the same step (``_late_reveal_one_card``), which is
      why the scan reads ``in_play`` too, not just ``hand``/``discard_pile``.
    """

    iid = data.get("instance_id")
    if isinstance(iid, str):
        return iid
    if is_tleilaxu:
        if len(owner_post.deck) == len(owner_pre.deck) + 1:
            return owner_post.deck[0]
        return None
    match = _INSTANCE_ID_SUFFIX.search(event.event_id)
    if match is not None:
        return match.group(1)
    card_id = data["card_id"]
    prefix = f"reserve:{card_id}:"
    pre_ids = set(owner_pre.hand) | set(owner_pre.discard_pile) | set(owner_pre.in_play)
    post_ids = (
        set(owner_post.hand) | set(owner_post.discard_pile) | set(owner_post.in_play)
    )
    candidates = [i for i in post_ids - pre_ids if i.startswith(prefix)]
    return candidates[0] if len(candidates) == 1 else None


# ---------------------------------------------------------------------------
# BondCollector: cards whose value depends on owning ANOTHER card of the same
# Faction ("Faction Bond" [Main p. 20]; docs/rules/uprising-systems.md:94).
# ---------------------------------------------------------------------------
#
# The Bond table is built from content, not hand-picked: any personal card
# whose Agent box, Reveal box, or conditional Agent icon is gated on another
# same-Faction card in play. Two independent gates exist mechanically:
#
# - ``agent``: the card's ``agent_effect`` name contains "bond" (every such
#   member is resolved in ``rules/agent_effects.py`` through
#   ``has_faction_bond(..., Faction.BENE_GESSERIT)`` -- checked at every call
#   site; there is no Fremen/Emperor/Spacing-Guild Agent-effect Bond member in
#   the current catalog), or its ``icon_condition`` is
#   ``PersonalCardIconCondition.BENE_GESSERIT_BOND`` (Long Reach; also
#   Bene Gesserit, resolved in ``rules/agent_icons.py``).
# - ``reveal``: a ``PersonalCardRevealEffect`` in ``reveal_effects`` sets
#   ``required_faction_bond`` (resolved via ``has_faction_bond`` in
#   ``rules/reveal_turn.py::_eligible_reveal_effects``) or
#   ``per_revealed_faction`` (a *count* of revealed same-Faction cards
#   including the card itself, not a same/other gate -- Sardaukar
#   Coordination, Stilgar the Devoted; ``_reveal_effect_persuasion``/
#   ``_reveal_effect_strength``). The latter is not literally
#   ``has_faction_bond``, but it needs company of the same Faction to pay off
#   more than its own base value, matching doc 6.6's framing, so it is kept
#   in the table with a code-comment flag.
#
# Scanning the full catalog (every expansion) gives, by required Faction:
# Fremen 11, Bene Gesserit 8, Emperor 1, Spacing Guild 0. Doc 6.6 (owner's
# tip audit) counted Fremen 11, Bene Gesserit 7, Emperor 1, Spacing Guild 0
# -- see the report for the +1 (Long Reach's icon-condition Bond, which the
# doc's audit apparently did not count since it grants icons rather than a
# Reveal/Agent value).
_FactionTable = dict[str, Faction]


def _agent_bond_faction(entry: PersonalCardDefinition) -> Faction | None:
    effect = getattr(entry, "agent_effect", None)
    if effect is not None and "bond" in effect.value:
        return Faction.BENE_GESSERIT
    condition = getattr(entry, "icon_condition", None)
    if condition is not None and "bond" in condition.value:
        return Faction.BENE_GESSERIT
    return None


def _reveal_bond_faction(entry: PersonalCardDefinition) -> Faction | None:
    for effect in getattr(entry, "reveal_effects", ()) or ():
        if effect.required_faction_bond is not None:
            return Faction(effect.required_faction_bond.value)
        if effect.per_revealed_faction is not None:
            return Faction(effect.per_revealed_faction.value)
    return None


def _catalog_entries() -> Iterable[tuple[str, PersonalCardDefinition]]:
    """Every printed personal card across every expansion, keyed by card ID.

    Unavailable-expansion cards simply never get bought or played in a game
    whose ``RulesetConfig`` leaves that expansion off, so scanning the full
    catalog once (rather than per ``spec.config``) is safe and cheap.
    """

    seen: dict[str, PersonalCardDefinition] = {}
    for iid in imperium_deck_instance_ids(
        choam_module=True, bloodlines=True, tech_module=True, immortality=True
    ):
        entry = imperium_card_for_instance(iid)
        seen.setdefault(entry.card.card_id, entry)
    yield from seen.items()
    yield from RESERVE_STACKS_BY_ID.items()
    yield from TLEILAXU_CARDS_BY_ID.items()


def _build_bond_tables() -> tuple[_FactionTable, _FactionTable]:
    agent: _FactionTable = {}
    reveal: _FactionTable = {}
    for card_id, entry in _catalog_entries():
        agent_faction = _agent_bond_faction(entry)
        if agent_faction is not None:
            agent[card_id] = agent_faction
        reveal_faction = _reveal_bond_faction(entry)
        if reveal_faction is not None:
            reveal[card_id] = reveal_faction
    return agent, reveal


AGENT_BOND, REVEAL_BOND = _build_bond_tables()
BOND_CARD_IDS = frozenset(AGENT_BOND) | frozenset(REVEAL_BOND)

# Cards whose Reveal Bond is the "per revealed same-Faction card" count
# (Sardaukar Coordination, Stilgar the Devoted -- see ``_reveal_bond_faction``
# above). The engine judges these against the cards revealed THIS Reveal turn
# only, not the seat's whole ``in_play`` (docs/rules/player-turns.md:235-237
# [Sardaukar Coordination card]: "이전 Agent turn에 낸 Emperor card는 이 수에
# 포함하지 않는다"), so their activation check reads the Reveal frame's
# revealed set instead of ``in_play`` (see ``step``).
PER_REVEALED: frozenset[str] = frozenset(
    card_id
    for card_id, entry in _catalog_entries()
    if any(
        effect.per_revealed_faction is not None
        for effect in getattr(entry, "reveal_effects", ()) or ()
    )
)


def _agent_side(s: Step, p: int) -> bool:
    """Return whether seat ``p``'s new ``in_play`` card(s) this step are Agent-side.

    "agent_turn" is the placement action itself. A Graft partner is chosen
    under a separate action ID (``choose_graft_partner``), but it still
    enters play while seat ``p``'s ``FrameKind.AGENT_EFFECTS`` frame is open
    (``rules/agent_turn.py`` pushes it at placement, popped only when the
    Agent turn's effects are done; ``rules/graft.py::apply_graft_partner``
    keeps it open) -- checked here by ``turn_owner`` rather than assuming
    the placed card's own frame is always on top, since a chance or nested
    choice frame can sit above it.
    """

    if s.action is not None and s.action.action_id == "agent_turn":
        return True
    return any(
        frame.kind == FrameKind.AGENT_EFFECTS
        and dict(frame.context).get("turn_owner") == p
        for frame in (*s.pre.decision_stack, *s.post.decision_stack)
    )


def _revealed_ids(s: Step, p: int) -> tuple[str, ...]:
    """Return the instance IDs seat ``p`` revealed on the open Reveal frame.

    ``rules/reveal_turn.py`` writes ``revealed_card_000``, ``_001``, ... plus
    a ``revealed_card_count`` on the ``FrameKind.REVEAL`` frame's context
    (``begin_reveal_turn``, extended by ``_apply_late_reveal_frame_update``
    for a card that arrives mid-Reveal), so this reads those keys rather than
    ``in_play`` -- see ``PER_REVEALED``.
    """

    for frame in s.post.decision_stack:
        if frame.kind != FrameKind.REVEAL:
            continue
        context = dict(frame.context)
        if context.get("turn_owner") != p:
            continue
        return tuple(
            str(v)
            for k, v in context.items()
            if k.startswith("revealed_card_") and k != "revealed_card_count"
        )
    return ()


class BondCollector(Collector):
    """Faction-Bond card ownership, pairing, and how often Bond paid off."""

    name = "bond"

    def __init__(self, spec: MatchSpec, seats: int) -> None:
        super().__init__(spec, seats)
        self._prev_in_play: list[tuple[str, ...] | None] = [None] * seats
        # "plays": times a Bond-table card newly entered ``in_play`` on the
        # side (Agent/Reveal) its own Bond gate checks -- not every entry
        # into play, since a Reveal-Bond card sent as an Agent (or vice
        # versa) never has its Bond condition checked that turn.
        self._plays = [0] * seats
        self._activations = [0] * seats

    def step(self, s: Step) -> None:
        for p, ps in enumerate(s.post.players):
            in_play = ps.in_play
            prev = self._prev_in_play[p]
            if in_play is prev:
                continue
            new_ids = tuple(i for i in in_play if i not in prev) if prev else in_play
            self._prev_in_play[p] = in_play
            if not new_ids:
                continue
            agent_side = _agent_side(s, p)
            table = AGENT_BOND if agent_side else REVEAL_BOND
            revealed: tuple[str, ...] | None = None
            for iid in new_ids:
                card_id = personal_card_for_instance(iid).card.card_id
                faction = table.get(card_id)
                if faction is None:
                    continue
                self._plays[p] += 1
                if not agent_side and card_id in PER_REVEALED:
                    if revealed is None:
                        revealed = _revealed_ids(s, p)
                    if has_faction_bond(revealed, iid, faction):
                        self._activations[p] += 1
                elif has_faction_bond(in_play, iid, faction):
                    self._activations[p] += 1

    def finish(
        self, final: GameState, standings: tuple[FinalStanding, ...]
    ) -> tuple[list[Columns], Columns]:
        per_seat: list[Columns] = []
        for p in range(self.seats):
            owned = _owned_ids(final.players[p])
            # (printed card ID, printed Faction set) per owned instance, so
            # both the Bond-table lookup and the partner check below resolve
            # each instance exactly once.
            owned_cards: list[tuple[str, set[Faction]]] = []
            for iid in owned:
                entry = personal_card_for_instance(iid)
                owned_cards.append((entry.card.card_id, set(entry.factions)))
            cards_end = 0
            pairs_end = 0
            for i, (card_id, _own_factions) in enumerate(owned_cards):
                # The Faction that pays off THIS card's Bond, not its own
                # printed Factions: Southern Faith and Possible Futures print
                # Bene Gesserit + Fremen but their Bond needs another Bene
                # Gesserit card specifically (agent_effects.py:810-815, 833),
                # so an owned Fremen card must not count as their pair.
                required = {AGENT_BOND.get(card_id), REVEAL_BOND.get(card_id)} - {None}
                if not required:
                    continue
                cards_end += 1
                if any(
                    required & other_factions
                    for j, (_other_id, other_factions) in enumerate(owned_cards)
                    if j != i
                ):
                    pairs_end += 1
            plays = self._plays[p]
            activations = self._activations[p]
            per_seat.append(
                {
                    "cards_end": cards_end,
                    "pairs_end": pairs_end,
                    "plays": plays,
                    "activations": activations,
                    "activation_share": activations / plays if plays else None,
                }
            )
        game: Columns = {
            "table_fremen": sum(
                1
                for card_id in BOND_CARD_IDS
                if AGENT_BOND.get(card_id) is Faction.FREMEN
                or REVEAL_BOND.get(card_id) is Faction.FREMEN
            ),
            "table_bene_gesserit": sum(
                1
                for card_id in BOND_CARD_IDS
                if AGENT_BOND.get(card_id) is Faction.BENE_GESSERIT
                or REVEAL_BOND.get(card_id) is Faction.BENE_GESSERIT
            ),
            "table_emperor": sum(
                1
                for card_id in BOND_CARD_IDS
                if AGENT_BOND.get(card_id) is Faction.EMPEROR
                or REVEAL_BOND.get(card_id) is Faction.EMPEROR
            ),
            "table_spacing_guild": sum(
                1
                for card_id in BOND_CARD_IDS
                if AGENT_BOND.get(card_id) is Faction.SPACING_GUILD
                or REVEAL_BOND.get(card_id) is Faction.SPACING_GUILD
            ),
        }
        return per_seat, game


COLLECTORS: tuple[type[Collector], ...] = (DeckCollector, BondCollector)
