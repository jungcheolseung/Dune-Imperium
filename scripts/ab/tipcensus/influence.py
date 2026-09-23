"""Influence-track, Landsraad, and Spy collectors for the tip census.

Tips: C1.6/C3.1/C3.2/C3.4 (Faction Influence and the Guild/Emperor-only win),
C1.8/C6.3/C6.4 (Swordmaster and High Council), C4.1/C4.2/C4.3 (Spy play).
See ``docs/player-tips-for-training.md`` and
``docs/evaluation/community-tips-2026-09-22.md``.
"""

from __future__ import annotations

from collections import Counter

from dune_imperium.content.immortality.tleilaxu import TLEILAXU_CARDS_BY_ID
from dune_imperium.content.uprising.imperium import IMPERIUM_CARDS_BY_ID
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.types import AgentIcon
from dune_imperium.core.state import GameState
from dune_imperium.evaluation.tournament import MatchSpec
from dune_imperium.rules.endgame import FinalStanding

from .base import Collector, Columns, Step, arguments, payload

FACTION_ICONS = frozenset(
    (
        AgentIcon.EMPEROR,
        AgentIcon.SPACING_GUILD,
        AgentIcon.BENE_GESSERIT,
        AgentIcon.FREMEN,
    )
)

# ---------------------------------------------------------------------------
# InfluenceCollector: where every point of Faction Influence comes from.
# ---------------------------------------------------------------------------
#
# ``gain_faction_influence``/``lose_faction_influence`` (rules/influence.py:15,
# :181) are the *only* places that emit ``influence_gained``/``influence_lost``
# events; every one of the ~30 call sites passes its own ``event_prefix``, and
# the resulting ``event_id`` is always ``f"{event_prefix}:influence"``. Two
# shapes cover every call site (checked against the source below):
#
#   "round:<r>:combat_reward:..."        -> a Conflict reward           (combat_reward)
#   "round:<r>:player:<p>:<word>:..."    -> <word> names the source
#
# The bare-visit gain -- Faction Influence for visiting its board space
# [Main p. 7] (rules/agent_effects.py:4284 ``resolve_faction_influence``,
# wired as the ``resolve_faction_influence`` action, rules/engine.py:330,
# :538) -- prints its prefix as exactly "round:<r>:player:<p>:influence:
# <faction>" (no extra word), so ``<word> == "influence"`` identifies it
# uniquely *only* at that exact length (7 tokens); every other site inserts
# a word first. Sources that thread a caller-supplied ``source`` through
# (acquisition-bonus Influence, Research bonus Influence, Endgame Tech) keep
# whatever root the caller built, so they fall out of this rule
# automatically -- e.g. a Research-track Influence choice reached through an
# Intrigue card's reward keeps the "intrigue:..." root, not a separate
# "research" bucket. The one site this leaves inaccurate is contracts.py:979
# (below): it is "contract" only when reached through the direct Contract
# completion or Reveal-turn action; through ``complete_acquire_contracts``
# (an acquisition's own auto-completion, acquisition.py's seven call sites)
# it inherits that acquisition's "acquisition" root instead, and through
# ``complete_contract_by_effect`` (agent_effects.py:1089, Bloodlines' CHOAM
# Demands) it inherits "agent_card".
#
# Steersman Y'rkoon's Navigation card is a further wrinkle: reaching 2
# Influence with a Faction queues its play, and Plot Course reopens the
# *triggering* gain's own event_prefix for the queue entry
# (rules/influence.py:74 ``f"{event_prefix}:navigation:{step}"``), then
# ``apply_intrigue_choice`` (rules/intrigue.py:997, shared with real
# Intrigue-card plays since Navigation reuses the same choice-frame
# machinery -- rules/navigation.py:236,314) threads that through unchanged
# as ``f"{source}:slot:{n}:gained:<faction>"``. So the Navigation card's own
# Influence gain keeps whatever shape the triggering gain had (visit,
# combat_reward, intrigue, ...) with ``":navigation:"`` spliced into the
# middle -- checked directly by playing seed 6 of the full ruleset, where
# ``round:5:player:1:influence:fremen:navigation:0:slot:1:gained:fremen:
# influence`` would otherwise misread as a bare visit. Every gain with a
# ``"navigation"`` token is bucketed "leader" instead, regardless of what
# triggered it.
#
# Call sites (file:line -> <word>, i.e. the ``sources`` category after the
# alias table below):
#   contracts.py:979              contract            (Contract's printed
#                                  reward, when reached directly -- inherited
#                                  "acquisition"/"agent_card" through its two
#                                  auto-completion callers, see above)
#   combat.py:314,953,982,1065    combat_reward        (Conflict reward)
#   leader_abilities.py:1348      leader_signet -> leader (Signet Ring choice)
#   acquisition.py:451            acquire_with_solari -> acquisition
#   acquisition.py:726            acquire -> acquisition
#   acquisition.py:1150           acquire_manipulated -> acquisition
#   acquisition.py:1443           inherited (acquire_imperium_for_intrigue's
#                                  caller: intrigue.py, leader_abilities.py or
#                                  acquisition.py's agent_acquisition -> agent_card)
#   immortality.py:506            inherited (Research bonus frame's opener)
#   reveal_turn.py:376,1335,
#     1417,1489,1885              reveal_card          (a Reveal card's Command)
#   reveal_turn.py:2261           reveal_gain           (Reveal's queued-gain choice)
#   intrigue.py:1127              intrigue
#   tech.py:438                   inherited (Acquire Tech's opener: board or
#                                  agent_card)
#   tech.py:855                   endgame_tech -> tech  (Panopticon, Endgame)
#   board_effects.py:916          board                 (Shipping's choice)
#   effect_interpreter.py:877     intrigue              (apply_rewards' only
#                                  caller is intrigue.py's card resolution)
#   agent_effects.py:972,983,
#     1681,2440,3165,3708,
#     3755,3814,3926              agent_card            (a personal card's
#                                  Agent-box effect)
#   agent_effects.py:2266         agent_card_payment -> agent_card (an
#                                  Agent-box paid resource choice, e.g.
#                                  Immortality's ``choose_research_influence``)
#   agent_effects.py:3153         agent_card, but see the Subversive Advisor
#                                  special case below (its Agent box replaces
#                                  the visit's own Influence)
#   agent_effects.py:4295         (bare visit, special-cased below)
#   influence.py:74 + intrigue.py:997 (via navigation.py:236,314)
#                                  leader                (Steersman Y'rkoon's
#                                  Navigation card, whatever triggered the
#                                  reach-2 that queued it; see above)
#
# Subversive Advisor (agent_effects.py:3153): "일반 Influence 1 대신 해당
# Faction Influence 2를 얻고 ... 총 3을 얻지 않는다" [player-turns.md:103-107,
# Main pp. 9, 11, 20] -- playing it clears the visit's own pending Influence
# (agent_turn.py:492-497, ``pending_faction_influence`` is False whenever the
# card's Agent effect is ``GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_
# SELF``), so its whole 2-point gain would otherwise land only in
# ``agent_card`` with nothing under ``visit:*``. One of those points is
# credited back to ``visit:bought`` below (the card always has an
# acquisition bonus, so it is never a starter card).
#
# ``sum(sources.values()) == gained`` by construction: every
# ``influence_gained`` event is added to exactly one of ``gained`` and one
# ``sources`` bucket, with the same ``amount`` (Subversive Advisor's gain is
# split between two buckets, but the two still sum to its ``amount``).
_SOURCE_ALIASES = {
    "endgame_tech": "tech",
    "leader_signet": "leader",
    "agent_acquisition": "agent_card",
    "agent_card_payment": "agent_card",
    "acquire": "acquisition",
    "acquire_with_solari": "acquisition",
    "acquire_manipulated": "acquisition",
}


def _source_category(event_id: str) -> str:
    """Map an ``influence_gained``/``influence_lost`` event_id to a category.

    Returns the literal ``"visit"`` for the bare visit shape (the caller
    splits that further); ``"leader"`` for any gain routed through
    Steersman Y'rkoon's Navigation card, however it was triggered (see the
    enumeration above -- checked against a full seed-6 game where a
    Navigation card triggered by a bare visit's reach-2 would otherwise be
    misread as that visit); ``"other"`` only if none of the known shapes
    match (not expected to occur).
    """

    tokens = event_id.split(":")
    if "navigation" in tokens:
        return "leader"
    if len(tokens) >= 3 and tokens[0] == "round" and tokens[2] == "combat_reward":
        return "combat_reward"
    if len(tokens) >= 5 and tokens[0] == "round" and tokens[2] == "player":
        word = tokens[4]
        if word == "influence" and len(tokens) == 7:
            # Exactly "round:<r>:player:<p>:influence:<faction>:influence" --
            # any extra token (e.g. Navigation's own ":navigation:...", ruled
            # out above) means this word is not the bare-visit shape.
            return "visit"
        return _SOURCE_ALIASES.get(word, word)
    return "other"


def _visit_subcategory(card_id: str | None) -> str:
    """Split a bare-visit gain by the card played for that Agent turn.

    Instance-ID prefixes per the task brief: starter ids contain
    ``":starter:"``; Imperium/Reserve/Tleilaxu ids start with
    ``"imperium:"``/``"reserve:"``/``"tleilaxu:"``.
    """

    if card_id is None:
        return "other"
    if ":starter:" in card_id:
        return "starter"
    if card_id.startswith(("imperium:", "reserve:", "tleilaxu:")):
        return "bought"
    return "other"


def _card_has_faction_icon(card_id: str) -> bool:
    """Whether the personal card ``card_id`` prints a Faction Agent icon.

    ``card_id`` is a plain, non-instance id: ``card_acquired``/
    ``tleilaxu_card_acquired`` payloads carry the plain definitional id
    (e.g. ``definition.card.card_id``, or the Reserve stack id), not an
    instance id, across every acquisition.py/tleilaxu_row.py emit site -- so
    this looks the id up directly in the three plain-id-keyed catalogs
    instead of ``personal_card_for_instance``.
    """

    entry = (
        IMPERIUM_CARDS_BY_ID.get(card_id)
        or RESERVE_STACKS_BY_ID.get(card_id)
        or TLEILAXU_CARDS_BY_ID.get(card_id)
    )
    return entry is not None and bool(FACTION_ICONS & set(entry.agent_icons))


class InfluenceCollector(Collector):
    """Per-seat Faction Influence: final tracks, sources, and timing."""

    name = "infl"

    def __init__(self, spec: MatchSpec, seats: int) -> None:
        super().__init__(spec, seats)
        self._last_agent_card: list[str | None] = [None] * seats
        self._gained = [0] * seats
        self._lost = [0] * seats
        self._sources: list[Counter[str]] = [Counter() for _ in range(seats)]
        self._fremen2_round: list[int | None] = [None] * seats
        self._hooks_round: list[int | None] = [None] * seats
        self._pending_fremen2 = set(range(seats))
        self._pending_hooks = set(range(seats))
        self._reveal_open = [False] * seats
        self._early_reveals = [0] * seats
        self._early_reveal_faction_buys = [0] * seats

    def step(self, s: Step) -> None:
        if s.owner is not None and s.action is not None:
            # A new top-level turn choice closes the previous Reveal's
            # "early Reveal" window for this seat [player-turns.md:6, Main
            # p. 8: the Agent turn is optional, so a Reveal turn is legal
            # with Agents still unplaced].
            if s.action.action_id == "reveal_turn":
                # An Agent turn is only a real choice when some ``agent_turn``
                # is legal; otherwise Reveal is forced (no Agent placement was
                # affordable/legal), which is not the tip's "choose to Reveal
                # early" [player-turns.md:6, Main p. 8].
                if s.pre.players[s.owner].agents_available > 0 and any(
                    a.action_id == "agent_turn" for a in s.legal
                ):
                    self._reveal_open[s.owner] = True
                    self._early_reveals[s.owner] += 1
                else:
                    self._reveal_open[s.owner] = False
            elif s.action.action_id == "agent_turn":
                self._reveal_open[s.owner] = False

        for event in s.events:
            data = payload(event)
            player = data.get("player")
            if not isinstance(player, int) or not 0 <= player < self.seats:
                continue
            if event.kind == "agent_placed":
                card_id = data.get("card_id")
                self._last_agent_card[player] = (
                    card_id if isinstance(card_id, str) else None
                )
            elif event.kind == "influence_gained":
                amount = int(data["amount"])
                self._gained[player] += amount
                category = _source_category(event.event_id)
                if category == "visit":
                    category = "visit:" + _visit_subcategory(
                        self._last_agent_card[player]
                    )
                    self._sources[player][category] += amount
                elif category == "agent_card" and ":subversive_advisor:" in (
                    event.event_id
                ):
                    # Subversive Advisor replaces the visit's own Influence
                    # with its Agent box's 2 [player-turns.md:103-107]: credit
                    # 1 back to the visit (the card is always bought) and the
                    # rest to the card effect.
                    self._sources[player]["visit:bought"] += 1
                    self._sources[player]["agent_card"] += amount - 1
                else:
                    self._sources[player][category] += amount
            elif event.kind == "influence_lost":
                self._lost[player] += int(data["amount"])
            elif event.kind == "reveal_finished":
                # The Reveal turn itself is over: later acquisitions (Combat,
                # Makers, ...) are not "during" it even if this seat's next
                # top-level turn choice is still a round away.
                self._reveal_open[player] = False
            elif event.kind in ("card_acquired", "tleilaxu_card_acquired"):
                if self._reveal_open[player]:
                    card_id = data.get("card_id")
                    if isinstance(card_id, str) and _card_has_faction_icon(card_id):
                        self._early_reveal_faction_buys[player] += 1

        if self._pending_fremen2 or self._pending_hooks:
            # The last Combat-reward decision of a round can advance through
            # Makers, Recall and Round Start to the next round within this
            # same ``engine.apply`` (``round_number`` only increases at the
            # round-start conflict-reveal chance step, rules/phases.py:35,
            # which never itself changes Influence) -- so the round this
            # transition happened *in* is ``s.pre``'s, matching
            # LandsraadCollector's convention below.
            round_number = s.pre.round_number
            for seat in tuple(self._pending_fremen2):
                if s.post.players[seat].influence.fremen >= 2:
                    self._fremen2_round[seat] = round_number
                    self._pending_fremen2.discard(seat)
            for seat in tuple(self._pending_hooks):
                if s.post.players[seat].maker_hooks:
                    self._hooks_round[seat] = round_number
                    self._pending_hooks.discard(seat)

    def finish(
        self, final: GameState, standings: tuple[FinalStanding, ...]
    ) -> tuple[list[Columns], Columns]:
        rows: list[Columns] = []
        for seat in range(self.seats):
            influence = final.players[seat].influence
            tracks = (
                influence.emperor,
                influence.spacing_guild,
                influence.bene_gesserit,
                influence.fremen,
            )
            rows.append(
                {
                    # Final position on each Faction's Influence track (start
                    # is 0 for every player [uprising-systems.md:37]).
                    "emperor": influence.emperor,
                    "guild": influence.spacing_guild,
                    "bene_gesserit": influence.bene_gesserit,
                    "fremen": influence.fremen,
                    # Faction tracks ending at 0 or 1 / at least 2 / at least
                    # 4, out of the 4 Factions (tip C3.2: "focus 1-2
                    # Factions, some tracks end at 0-1").
                    "tracks_0_1": sum(1 for t in tracks if t <= 1),
                    "tracks_ge2": sum(1 for t in tracks if t >= 2),
                    "tracks_ge4": sum(1 for t in tracks if t >= 4),
                    # Alliance tokens held at game end.
                    "alliances": len(final.players[seat].alliance_faction_ids),
                    # Total Influence gained/lost across the whole game, all
                    # 4 Factions combined.
                    "gained": self._gained[seat],
                    "lost": self._lost[seat],
                    # Influence gained, by source category (see the
                    # enumeration above); "visit:starter"/"visit:bought"/
                    # "visit:other" split the bare visit gain by the card
                    # played for that Agent turn.
                    "sources": dict(self._sources[seat]),
                    # First round (the round the *decision* was taken in,
                    # ``s.pre.round_number``) this seat's Fremen Influence
                    # reached >= 2 (owner's tip: Fremen 2 grants Maker Hooks),
                    # None if never.
                    "fremen2_round": self._fremen2_round[seat],
                    # First round (same convention) this seat held Maker
                    # Hooks, None if never.
                    "hooks_round": self._hooks_round[seat],
                    # Reveal turns chosen while this seat still had an
                    # unplaced Agent *and* some Agent turn was legal (tip
                    # C3.4: early Reveal to grab Faction cards) -- excludes a
                    # Reveal forced because no Agent placement was legal.
                    "early_reveals": self._early_reveals[seat],
                    # Cards with a Faction Agent icon acquired between one of
                    # those Reveal turns starting and its own
                    # ``reveal_finished`` event.
                    "early_reveal_faction_buys": self._early_reveal_faction_buys[seat],
                }
            )
        return rows, {}


# ---------------------------------------------------------------------------
# LandsraadCollector: Swordmaster vs. High Council and their Reveal effect.
# ---------------------------------------------------------------------------


class LandsraadCollector(Collector):
    """Swordmaster/High Council timing and their Reveal-turn Persuasion."""

    name = "lands"

    def __init__(self, spec: MatchSpec, seats: int) -> None:
        super().__init__(spec, seats)
        self._swordmaster_round: list[int | None] = [None] * seats
        self._council_round: list[int | None] = [None] * seats
        self._pending_sm = set(range(seats))
        self._pending_hc = set(range(seats))
        self._reveal_n = [0] * seats
        self._reveal_cards_sum = [0] * seats
        self._reveal_pers_sum = [0] * seats
        # state -> [count, cards_sum, persuasion_sum], one dict per seat.
        self._by_state: list[dict[str, list[int]]] = [
            {"none": [0, 0, 0], "sm": [0, 0, 0], "hc": [0, 0, 0], "both": [0, 0, 0]}
            for _ in range(seats)
        ]

    def step(self, s: Step) -> None:
        if self._pending_sm or self._pending_hc:
            # "cost 8 Solari, 한 명이라도 얻은 뒤에는 6 Solari ... 세 번째 Agent"
            # [board-spaces.md:56, Board Guide p. 2]; PlayerState.
            # swordmaster_acquired flips True the step the space resolves
            # (board_effects.py:527); no dedicated event, so this watches
            # the state transition directly.
            for seat in tuple(self._pending_sm):
                if s.post.players[seat].swordmaster_acquired:
                    self._swordmaster_round[seat] = s.pre.round_number
                    self._pending_sm.discard(seat)
            # High Council: cost 5 Solari, then +2 Persuasion on every later
            # Reveal turn [board-spaces.md:54, Board Guide p. 2].
            for seat in tuple(self._pending_hc):
                if s.post.players[seat].high_council:
                    self._council_round[seat] = s.pre.round_number
                    self._pending_hc.discard(seat)

        for event in s.events:
            if event.kind != "reveal_started":
                continue
            data = payload(event)
            player = data.get("player")
            if not isinstance(player, int) or not 0 <= player < self.seats:
                continue
            cards = int(data["cards"])
            persuasion = int(data["persuasion"])
            self._reveal_n[player] += 1
            self._reveal_cards_sum[player] += cards
            self._reveal_pers_sum[player] += persuasion
            owner = s.pre.players[player]
            key = (
                "both"
                if owner.swordmaster_acquired and owner.high_council
                else "sm"
                if owner.swordmaster_acquired
                else "hc"
                if owner.high_council
                else "none"
            )
            bucket = self._by_state[player][key]
            bucket[0] += 1
            bucket[1] += cards
            bucket[2] += persuasion

    def finish(
        self, final: GameState, standings: tuple[FinalStanding, ...]
    ) -> tuple[list[Columns], Columns]:
        rows: list[Columns] = []
        for seat in range(self.seats):
            sm = self._swordmaster_round[seat]
            hc = self._council_round[seat]
            n = self._reveal_n[seat]
            row: Columns = {
                # Round Swordmaster/High Council was acquired, None if never.
                "swordmaster_round": sm,
                "council_round": hc,
                # Order the two Landsraad seats were taken in (tip C6.3/C6.4).
                "sm_first": sm is not None and (hc is None or sm < hc),
                "hc_first": hc is not None and (sm is None or hc < sm),
                "same_round": sm is not None and hc is not None and sm == hc,
                # Mean cards revealed / Persuasion available over this
                # seat's Reveal turns ('reveal_started' payload).
                "reveal_cards": (self._reveal_cards_sum[seat] / n) if n else None,
                "reveal_persuasion": (self._reveal_pers_sum[seat] / n) if n else None,
            }
            for key, bucket in self._by_state[seat].items():
                count = bucket[0]
                row[f"reveal_cards_{key}"] = (bucket[1] / count) if count else None
                row[f"reveal_persuasion_{key}"] = (bucket[2] / count) if count else None
            rows.append(row)
        return rows, {}


# ---------------------------------------------------------------------------
# SpyCollector: every Spy movement path.
# ---------------------------------------------------------------------------
#
# Emit sites (a Spy always starts in supply -- PlayerState defaults
# ``spy_post_ids=()`` and no ``setup.py`` seat overrides it, so ``placed``
# needs no "starts on the board" adjustment):
#   spy_placed                  -> onto the board, from supply.
#     agent_turn.py (Infiltrate's own placement is folded into its recall,
#     see below), acquisition.py, agent_effects.py, board_effects.py,
#     combat.py, contracts.py, intrigue_triggers.py, leader_abilities.py
#     (x2), reveal_turn.py, spy_moves.py (forced relocation's second half,
#     and the Deep-Cover placement rule via ``spy_placement_frame``).
#   spy_recalled                -> off the board, to supply, for any reason
#     other than Infiltrate or Gather Intelligence: a forced relocation's
#     first half (spy_moves.py, Bloodlines' Holy War/False Orders), the
#     "recall one for no effect" when placing without a Spy in supply
#     (spy_placement.py's ``recall_spy_for_placement``), and card/board/
#     leader effects that recall a Spy directly (acquisition.py,
#     agent_effects.py, board_effects.py, contracts.py, intrigue_triggers.py,
#     leader_abilities.py (x3), reveal_turn.py).
#   spies_recalled (plural)     -> off the board, to supply, *two at once*:
#     the optional "recall 2 Spies for N VP" Conflict reward (combat.py:623,
#     ``apply_combat_reward_spy_recall``; its ``kind`` is chosen at runtime,
#     ``"spies_recalled" if paid else "combat_reward_declined"``, so it does
#     not show up in a plain ``kind="..."`` search -- found by diffing
#     ``spy_post_ids`` across a step instead of trusting the enumeration).
#     ``spy_count`` is hard-coded to 2 (``NotImplementedError`` otherwise);
#     the two posts are the accepting action's own ``first_post_id``/
#     ``second_post_id`` arguments, not the event payload (which only
#     carries a count).
#   spy_recalled_for_infiltrate -> off the board, to supply, as Infiltrate's
#     cost (agent_turn.py:612; `[Main p. 11]` `[FAQ p. 4]`, uprising-
#     systems.md:79).
#   gather_intelligence          -> off the board, to supply, as Gather
#     Intelligence's cost (spies.py:91).
#   spy_trashed                  -> off the board, out of the game (boxed):
#     a Tech tile's own acquisition cost (tech.py:365, the only site).
#
# Conservation: every placement is exactly one ``spy_placed``; every
# departure is exactly one ``spy_recalled``/``spy_recalled_for_infiltrate``/
# ``gather_intelligence``/``spy_trashed``, or two at once via
# ``spies_recalled`` (the engine's own invariant, ``spies_supply +
# len(spy_post_ids) + spies_boxed == 3``, ties them together) -- so per
# seat, ``placed == used_infiltrate + used_gather + recalled_other +
# trashed + on_board_end``.
class SpyCollector(Collector):
    """Per-seat Spy placement, use, and the round-lag between them."""

    name = "spy"

    def __init__(self, spec: MatchSpec, seats: int) -> None:
        super().__init__(spec, seats)
        self._placed = [0] * seats
        self._used_infiltrate = [0] * seats
        self._used_gather = [0] * seats
        self._recalled_other = [0] * seats
        self._trashed = [0] * seats
        self._gather_offered = [0] * seats
        self._gather_taken = [0] * seats
        self._infiltrate_offered = [0] * seats
        self._infiltrate_taken = [0] * seats
        self._espionage_visits = [0] * seats
        # seat -> {post_id: round placed}, consumed on every departure.
        self._placement_round: list[dict[str, int]] = [dict() for _ in range(seats)]
        self._lag_sum = [0] * seats
        self._lag_n = [0] * seats

    def _consume_lag(self, player: int, post_id: object, round_number: int) -> None:
        if not isinstance(post_id, str):
            return
        placed_round = self._placement_round[player].pop(post_id, None)
        if placed_round is not None:
            self._lag_sum[player] += round_number - placed_round
            self._lag_n[player] += 1

    def step(self, s: Step) -> None:
        if s.owner is not None and s.legal:
            if any(a.action_id == "gather_intelligence" for a in s.legal):
                self._gather_offered[s.owner] += 1
                if s.action is not None and s.action.action_id == "gather_intelligence":
                    self._gather_taken[s.owner] += 1
            infiltrate_offered = any(
                a.action_id == "agent_turn"
                and arguments(a).get("infiltrate_post_id") is not None
                for a in s.legal
            )
            if infiltrate_offered:
                self._infiltrate_offered[s.owner] += 1
                if (
                    s.action is not None
                    and s.action.action_id == "agent_turn"
                    and arguments(s.action).get("infiltrate_post_id") is not None
                ):
                    self._infiltrate_taken[s.owner] += 1

        for event in s.events:
            data = payload(event)
            player = data.get("player")
            if not isinstance(player, int) or not 0 <= player < self.seats:
                continue
            round_number = s.pre.round_number
            if event.kind == "agent_placed":
                if data.get("space_id") == "espionage":
                    self._espionage_visits[player] += 1
            elif event.kind == "spy_placed":
                self._placed[player] += 1
                post_id = data.get("post_id")
                if isinstance(post_id, str):
                    self._placement_round[player][post_id] = round_number
            elif event.kind == "spy_recalled_for_infiltrate":
                self._used_infiltrate[player] += 1
                self._consume_lag(player, data.get("post_id"), round_number)
            elif event.kind == "gather_intelligence":
                self._used_gather[player] += 1
                self._consume_lag(player, data.get("post_id"), round_number)
            elif event.kind == "spy_recalled":
                self._recalled_other[player] += 1
                post_id = data.get("post_id")
                if isinstance(post_id, str):
                    self._placement_round[player].pop(post_id, None)
            elif event.kind == "spies_recalled":
                # combat.py:623: the optional 2-Spy Conflict reward. The
                # event payload only carries a count; the two posts are the
                # accepting action's own arguments.
                self._recalled_other[player] += int(data["spies"])
                if (
                    s.action is not None
                    and s.action.action_id == "recall_spies_for_combat_reward"
                ):
                    args = arguments(s.action)
                    for key in ("first_post_id", "second_post_id"):
                        post_id = args.get(key)
                        if isinstance(post_id, str):
                            self._placement_round[player].pop(post_id, None)
            elif event.kind == "spy_trashed":
                self._trashed[player] += 1
                post_id = data.get("post_id")
                if isinstance(post_id, str):
                    self._placement_round[player].pop(post_id, None)

    def finish(
        self, final: GameState, standings: tuple[FinalStanding, ...]
    ) -> tuple[list[Columns], Columns]:
        rows: list[Columns] = []
        for seat in range(self.seats):
            rows.append(
                {
                    # Every Spy placement/use/departure this seat's Spies
                    # went through over the whole game (see the enumeration
                    # above).
                    "placed": self._placed[seat],
                    "used_infiltrate": self._used_infiltrate[seat],
                    "used_gather": self._used_gather[seat],
                    "recalled_other": self._recalled_other[seat],
                    "trashed": self._trashed[seat],
                    "on_board_end": len(final.players[seat].spy_post_ids),
                    # Decisions offering Gather Intelligence, and how often
                    # it was taken (tip C4.2: time Gather Intelligence).
                    "gather_offered": self._gather_offered[seat],
                    "gather_taken": self._gather_taken[seat],
                    # Agent-turn decisions where an Infiltrate placement was
                    # legal, and how often it was taken (tip C4.1).
                    "infiltrate_offered": self._infiltrate_offered[seat],
                    "infiltrate_taken": self._infiltrate_taken[seat],
                    # Agents sent to the Espionage board space.
                    "espionage_visits": self._espionage_visits[seat],
                    # Mean rounds between a Spy's placement and its use by
                    # Infiltrate or Gather Intelligence (tip C4.3: place
                    # Spies where you will use them), None if it never used
                    # one.
                    "use_lag": (
                        (self._lag_sum[seat] / self._lag_n[seat])
                        if self._lag_n[seat]
                        else None
                    ),
                }
            )
        return rows, {}


COLLECTORS: tuple[type[Collector], ...] = (
    InfluenceCollector,
    LandsraadCollector,
    SpyCollector,
)
