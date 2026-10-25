"""Authoritative game state and deterministic state hashing."""

import dataclasses
import hashlib
import json
from collections.abc import Callable, KeysView
from copy import replace
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

from dune_imperium.config import RulesetConfig
from dune_imperium.core.dataclass_copy import positional_dataclass_replace
from dune_imperium.core.decisions import DecisionFrame
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState


class GamePhase(StrEnum):
    """Top-level Uprising round phases."""

    SETUP = "setup"
    ROUND_START = "round_start"
    PLAYER_TURNS = "player_turns"
    COMBAT = "combat"
    MAKERS = "makers"
    RECALL_OR_ENDGAME = "recall_or_endgame"
    ENDGAME = "endgame"
    FINISHED = "finished"


@positional_dataclass_replace
@dataclass(frozen=True, slots=True)
class GameState:
    """Minimal authoritative state shared by all later rule modules."""

    config: RulesetConfig
    seed: int
    phase: GamePhase = GamePhase.SETUP
    revision: int = 0
    round_number: int = 0
    first_player: int | None = None
    reveal_order: tuple[int, ...] = ()
    endgame_intrigue_complete: bool = False
    players: tuple[PlayerState, ...] = ()
    conflict_deck: tuple[str, ...] = ()
    unused_conflict_ids: tuple[str, ...] = ()
    current_conflict_ids: tuple[str, ...] = ()
    combat_intrigue_complete: bool = False
    combat_rewards_resolved: bool = False
    # Ranked Conflict reward recipients already paid in the current Combat.
    # Rewards are handed out one recipient at a time in rank order, each
    # recipient's choices answered before the next is paid (user ruling
    # 2026-10-07); ``combat_rewards_resolved`` follows the last one.
    combat_rewards_paid: int = 0
    # Whether the Conflict-end trigger windows have been offered for the
    # current Combat: after the rewards, on public facts only, to every seat
    # with three or more units in the Conflict and an Intrigue card, while
    # not both Harvest Cells are public (Immortality, OQ-057 (11), OQ-103).
    combat_end_triggers_offered: bool = False
    # Seats that played a Combat Intrigue card in the current Conflict
    # (Counterattack, Immortality); cleared when the Combat phase resets.
    combat_intrigue_players: tuple[int, ...] = ()
    imperium_deck: tuple[str, ...] = ()
    imperium_row: tuple[str, ...] = ()
    intrigue_deck: tuple[str, ...] = ()
    intrigue_discard: tuple[str, ...] = ()
    imperium_removed: tuple[str, ...] = ()
    contract_bank: tuple[str, ...] = ()
    face_up_contract_ids: tuple[str, ...] = ()
    # Contracts set aside during setup for Shaddam Corrino IV; only he can
    # acquire them [Shaddam Corrino IV card] [FAQ p. 3].
    sardaukar_contract_ids: tuple[str, ...] = ()
    # Contracts trashed by a card effect (Coercive Negotiation, Bloodlines):
    # out of the game, kept public for the population census.
    contract_trash: tuple[str, ...] = ()
    # Face-up six-Leader pool of the OQ-007 draft convention, in draw order.
    # Public for the whole game; Leaders picked from it appear on the seats
    # and the two unpicked Leaders stay unused.
    leader_draft_pool: tuple[str, ...] = ()
    reserve_stacks: tuple[tuple[str, int], ...] = ()
    shield_wall_present: bool = True
    # Pivotal Gambit (Uprising promo): "gain 1 Influence of your choice"
    # rewards pledged to the current Conflict's first-place reward, paid out
    # with that reward and cleared afterwards (OQ-025).
    conflict_first_place_influence_bonus: int = 0
    # Bloodlines: board spaces still holding a Sardaukar Commander, the
    # Commander kept in the bank for Sardaukar Standard, and the Skill tiles
    # (face-down stack in hidden order, face-up choices, trashed)
    # [Bloodlines pp. 3-4]. All empty without the ``bloodlines`` option.
    sardaukar_commander_space_ids: tuple[str, ...] = ()
    sardaukar_commanders_bank: int = 0
    skill_stack: tuple[str, ...] = ()
    skill_face_up: tuple[str, ...] = ()
    skill_trash: tuple[str, ...] = ()
    # Tech Module [Bloodlines pp. 6-7]: the Ixian Embassy's three stacks
    # (each in hidden order, index 0 the face-up top) and the trashed tiles.
    # Both empty without the ``tech_module`` option.
    tech_stacks: tuple[tuple[str, ...], ...] = ()
    tech_trash: tuple[str, ...] = ()
    # Immortality [Immortality pp. 4, 7, 9]: the face-down Tleilaxu deck
    # (hidden order), the face-up Tleilaxu Row (Reclaimed Forces is fixed
    # and not listed), and the setup spice waiting on the Tleilaxu track's
    # fourth space for the first player to reach it. All empty without the
    # ``immortality`` option.
    tleilaxu_deck: tuple[str, ...] = ()
    tleilaxu_row: tuple[str, ...] = ()
    tleilaxu_track_spice: int = 0
    maker_bonus_spice: tuple[tuple[str, int], ...] = (
        ("deep_desert", 0),
        ("hagga_basin", 0),
        ("imperial_basin", 0),
    )
    # Intrigue draws owed after the deck ran out mid-transition, resolved by the
    # dispatcher (reshuffling the discard through a chance decision) before the
    # next player decision: (player, count, event source).
    pending_intrigue_draws: tuple[tuple[int, int, str], ...] = ()
    # Sardaukar Standard: Commander acquisitions owed by a trash trigger
    # (player, card, source); each opens its Skill choice once the trashing
    # effect has finished with the decision stack. An Agent turn cannot
    # close over its owner's queued entries (OQ-095), so each one resolves
    # inside the turn that queued it.
    pending_skill_choices: tuple[tuple[int, str, str], ...] = ()
    # The shuffled Twisted Intrigue deck dealt at setup, waiting for Piter De
    # Vries' seat (the draft picks Leaders after the shuffle); empty once
    # assigned or when no seat plays him.
    twisted_deck_stock: tuple[str, ...] = ()
    # The shuffled Navigation deck dealt at setup, waiting for Steersman
    # Y'rkoon's seat; empty once assigned or when nobody plays him.
    navigation_stock: tuple[str, ...] = ()
    # Navigation plays owed by Influence gains that reached two
    # (player, faction, source), opened in order by the engine.
    pending_navigation_plays: tuple[tuple[int, str, str], ...] = ()
    # Spies owed by the Emperor track's Influence 4 bonus (player, source):
    # the engine opens each one's placement as soon as the gaining effect
    # has finished, before any other player decision.
    pending_track_spies: tuple[tuple[int, str], ...] = ()
    # Arrakeen Scouts (``arrakeen_scouts`` option, docs/rules/arrakeen-
    # scouts.md; ``rules.scouts``). All public, all empty without the
    # option. The five subcommittees revealed in round 1 (draw order); every
    # item revealed since, as (round, item id); the mission layout's rounds
    # and the mid and late auction rounds once drawn (0 until then).
    scouts_subcommittees: tuple[str, ...] = ()
    scouts_revealed: tuple[tuple[int, str], ...] = ()
    scouts_mission_rounds: tuple[int, ...] = ()
    scouts_mid_auction_round: int = 0
    scouts_late_auction_round: int = 0
    # Whether this round's Scouts step still runs before the first turn,
    # and its cursor: the item being resolved and its remaining tasks.
    scouts_opening: bool = False
    scouts_item: str = ""
    scouts_tasks: tuple[str, ...] = ()
    # The rule change an event made for the rest of this round ("" none),
    # and whether Market Opening's discount has been used up this round.
    scouts_round_modifier: str = ""
    scouts_discount_used: bool = False
    # Friends Everywhere: Influence 4 bonuses whose Faction the seat picks,
    # as (player, Faction reached, event source), opened in order.
    scouts_four_bonus_choices: tuple[tuple[int, str, str], ...] = ()
    # Subcommittee members as (subcommittee id, seat), in joining order, and
    # the choices open for a High Council seat taken through Corrinth City
    # during a Reveal turn (OQ-076), as (player, event source, space of the
    # Agent that took it: always ""); each lapses when its Reveal turn ends.
    # A board-space seat's choice is a pending icon of its Agent-turn frame
    # instead.
    scouts_subcommittee_members: tuple[tuple[str, int], ...] = ()
    scouts_subcommittee_offers: tuple[tuple[int, str, str], ...] = ()
    # Mission pieces (``rules.scouts_missions``): bank goods as (mission,
    # location, resource, amount, seat or -1 for anyone), face-down cards as
    # (mission, location, card id), and parked troops as (mission, seat,
    # location, troops). The cards are hidden from every seat.
    scouts_goods: tuple[tuple[str, str, str, int, int], ...] = ()
    scouts_goods_cards: tuple[tuple[str, str, str], ...] = ()
    scouts_parked: tuple[tuple[str, int, str, int], ...] = ()
    # Secret picks (``rules.scouts_secrets``) as (event round, event id,
    # seat, pick index), each known to its seat only until the round it is
    # due; and the last round whose Scouts step revealed the due picks.
    scouts_secret_picks: tuple[tuple[int, str, int, int], ...] = ()
    scouts_secrets_round: int = 0
    # The auction being run (``rules.scouts_auctions``): sealed bids as
    # (seat, amount, confirmed), each known to its seat only until the last
    # confirmation; Critical Moment's revealed Imperium cards and its open
    # calls as (seat, amount; 0 a pass).
    scouts_bids: tuple[tuple[int, int, bool], ...] = ()
    scouts_market_cards: tuple[str, ...] = ()
    scouts_calls: tuple[tuple[int, int], ...] = ()
    decision_stack: tuple[DecisionFrame, ...] = ()
    event_log: tuple[GameEvent, ...] = ()

    def __post_init__(self) -> None:
        # Only the checks: copy.replace builds copies without the constructor
        # and runs the checks they need (_check_copy), so any other work here
        # would be skipped on copies (tests/unit/test_state_checks.py).
        check_game_state(self)

    def _check_copy(self, previous: GameState, changed: KeysView[str]) -> None:
        """Run the checks a copy of ``previous`` with ``changed`` fields needs.

        ``copy.replace`` builds the copy without the constructor
        (``positional_dataclass_replace``) and calls this instead of
        ``__post_init__``: a check runs when a field it reads was replaced, or
        when ``players`` was and a seat field it reads is another object in
        some seat. Every other check reads only what ``previous`` already
        passed with. Two in three state copies only push a decision frame or
        log an event, which no check reads (2026-10-21).
        """

        seats: frozenset[str] | None = None
        for check in STATE_CHECKS:
            if not check.fields.isdisjoint(changed):
                check.run(self)
                continue
            if not check.seat_fields or "players" not in changed:
                continue
            if seats is None:
                seats = _changed_seat_fields(previous.players, self.players)
            if not check.seat_fields.isdisjoint(seats):
                check.run(self)

    def push_decision(self, frame: DecisionFrame) -> GameState:
        """Return a state with ``frame`` at the top of the stack."""

        return replace(self, decision_stack=(*self.decision_stack, frame))

    def pop_decision(self) -> GameState:
        """Return a state without the current decision frame."""

        if not self.decision_stack:
            raise IndexError("cannot pop an empty decision stack")
        return replace(self, decision_stack=self.decision_stack[:-1])


@dataclass(frozen=True, slots=True)
class StateCheck:
    """One ``GameState`` invariant and the fields it reads.

    ``fields`` are the ``GameState`` fields ``check`` reads; ``seat_fields``
    the ``PlayerState`` fields it reads in any seat (through ``players``).
    A copy that replaces none of them keeps the verdict its source had, so
    ``GameState._check_copy`` skips the check. ``tests/unit/test_state_checks.py``
    reads every check with recording proxies over real games and fails on a
    field the table does not name.
    """

    check: Callable[[GameState], None]
    fields: frozenset[str]
    seat_fields: frozenset[str] = frozenset()

    def run(self, state: GameState) -> None:
        self.check(state)


def _check_counters(state: GameState) -> None:
    if state.round_number < 0:
        raise ValueError("round_number must not be negative")
    if state.first_player is not None and not (
        0 <= state.first_player < state.config.players
    ):
        raise ValueError("first_player must identify a configured player")
    if len(state.reveal_order) != len(set(state.reveal_order)):
        raise ValueError("a player can appear in the Reveal order only once")
    if len(state.combat_intrigue_players) != len(set(state.combat_intrigue_players)):
        raise ValueError("a player is listed once among Combat Intrigue players")
    if any(not 0 <= player < state.config.players for player in state.reveal_order):
        raise ValueError("Reveal order must contain configured players")


def _check_seats(state: GameState) -> None:
    if state.players and len(state.players) != state.config.players:
        raise ValueError("state must contain every configured player")
    if state.players and tuple(player.player_id for player in state.players) != tuple(
        range(state.config.players)
    ):
        raise ValueError("players must be stored in seat order")


def _check_markets(state: GameState) -> None:
    if len(state.imperium_row) > 5:
        raise ValueError("Imperium Row cannot contain more than five cards")
    if len(state.face_up_contract_ids) > 2:
        raise ValueError("the Contract market cannot contain more than two tiles")


# Every module's zones are re-checked on each state copy that touches them,
# so the module flag gates the scan: with the module off the only legal
# contents are none at all, which an emptiness test settles without building
# tuples and sets.
def _check_contracts(state: GameState) -> None:
    if state.config.choam_module:
        contracts = (
            *state.contract_bank,
            *state.face_up_contract_ids,
            *state.sardaukar_contract_ids,
            # CHOAM Research's face-down pair (Arrakeen Scouts).
            *(
                card_id
                for _, location, card_id in state.scouts_goods_cards
                if card_id.startswith("contract:")
            ),
            *(
                contract_id
                for player in state.players
                for contract_id in (
                    *player.active_contract_ids,
                    *player.completed_contract_ids,
                )
            ),
        )
        if len(contracts) != len(set(contracts)):
            raise ValueError("a Contract cannot occupy two zones")
    elif (
        state.contract_bank
        or state.face_up_contract_ids
        or state.sardaukar_contract_ids
        or any(
            player.active_contract_ids or player.completed_contract_ids
            for player in state.players
        )
    ):
        raise ValueError("Contracts require the CHOAM Module")


def _check_shared_cards(state: GameState) -> None:
    shared_cards = (
        *state.conflict_deck,
        *state.unused_conflict_ids,
        *state.current_conflict_ids,
        *(
            conflict_id
            for player in state.players
            for conflict_id in player.won_conflict_ids
        ),
    )
    if len(shared_cards) != len(set(shared_cards)):
        raise ValueError("a Conflict card cannot occupy two shared zones")
    held_alliances = tuple(
        faction_id
        for player in state.players
        for faction_id in player.alliance_faction_ids
    )
    if len(held_alliances) != len(set(held_alliances)):
        raise ValueError("a Faction Alliance can have only one owner")


def _check_reserve(state: GameState) -> None:
    reserve_ids = tuple(card_id for card_id, _ in state.reserve_stacks)
    if len(reserve_ids) != len(set(reserve_ids)):
        raise ValueError("Reserve stack IDs must be unique")
    if any(not card_id or count < 0 for card_id, count in state.reserve_stacks):
        raise ValueError("Reserve stacks require IDs and non-negative counts")


def _check_bloodlines(state: GameState) -> None:
    if state.sardaukar_commanders_bank < 0:
        raise ValueError("the Commander bank must not be negative")
    if state.config.bloodlines:
        if len(state.sardaukar_commander_space_ids) != len(
            set(state.sardaukar_commander_space_ids)
        ):
            raise ValueError("a board space holds at most one Sardaukar Commander")
        skills = (
            *state.skill_stack,
            *state.skill_face_up,
            *state.skill_trash,
            *(skill_id for player in state.players for skill_id in player.skill_ids),
        )
        if len(skills) != len(set(skills)):
            raise ValueError("a Skill tile cannot occupy two zones")
    elif (
        state.skill_stack
        or state.skill_face_up
        or state.skill_trash
        or state.sardaukar_commander_space_ids
        or state.sardaukar_commanders_bank
        or any(player.skill_ids or player.commanders_total for player in state.players)
    ):
        raise ValueError("Sardaukar Commanders require the Bloodlines expansion")


def _check_tech(state: GameState) -> None:
    if state.config.tech_module:
        tech = (
            *(tech_id for stack in state.tech_stacks for tech_id in stack),
            *state.tech_trash,
            *(
                tech_id
                for player in state.players
                for tech_id in (
                    *player.tech_ids,
                    *(
                        (player.secret_project_tech_id,)
                        if player.secret_project_tech_id
                        else ()
                    ),
                )
            ),
        )
        if len(tech) != len(set(tech)):
            raise ValueError("a Tech tile cannot occupy two zones")
    elif (
        any(state.tech_stacks)
        or state.tech_trash
        or any(
            player.tech_ids or player.secret_project_tech_id or player.spies_boxed
            for player in state.players
        )
    ):
        raise ValueError("Tech tiles require the Tech Module")


def _check_immortality(state: GameState) -> None:
    if state.tleilaxu_track_spice < 0:
        raise ValueError("the Tleilaxu track spice must not be negative")
    if state.config.immortality:
        tleilaxu_cards = (*state.tleilaxu_deck, *state.tleilaxu_row)
        if len(tleilaxu_cards) != len(set(tleilaxu_cards)):
            raise ValueError("a Tleilaxu card cannot occupy two zones")
    elif (
        state.tleilaxu_deck
        or state.tleilaxu_row
        or state.tleilaxu_track_spice
        or any(
            player.research_space
            or player.tleilaxu_space
            or player.specimens
            or player.family_atomics
            for player in state.players
        )
    ):
        raise ValueError("the Bene Tleilax board requires Immortality")


def _check_scouts(state: GameState) -> None:
    if state.config.arrakeen_scouts:
        if len(state.scouts_subcommittees) != len(set(state.scouts_subcommittees)):
            raise ValueError("a subcommittee is revealed once")
        revealed = tuple(item_id for _, item_id in state.scouts_revealed)
        if len(revealed) != len(set(revealed)):
            raise ValueError("a Scouts item is revealed once")
        if state.scouts_tasks and not state.scouts_item:
            raise ValueError("Scouts tasks belong to an item being resolved")
        joined = tuple(item for item, _ in state.scouts_subcommittee_members)
        seats = tuple(seat for _, seat in state.scouts_subcommittee_members)
        if len(joined) != len(set(joined)) or len(seats) != len(set(seats)):
            raise ValueError("a subcommittee has one member; a seat joins once")
        if not set(joined) <= set(state.scouts_subcommittees):
            raise ValueError("members join a revealed subcommittee")
        parked: dict[int, int] = {}
        for _, seat, _, troops in state.scouts_parked:
            if troops < 1:
                raise ValueError("a parked row holds at least one troop")
            parked[seat] = parked.get(seat, 0) + troops
        for player in state.players:
            if parked.get(player.player_id, 0) != player.troops_parked:
                raise ValueError("parked troops must match their rows")
            markers = sum(
                1
                for row in state.scouts_goods
                if row[2] == "marker" and row[4] == player.player_id
            )
            if len(player.control_space_ids) + markers > 3:
                raise ValueError("a player has only three control markers")
        if any(row[3] < 1 for row in state.scouts_goods):
            raise ValueError("a goods row holds something")
        picked = tuple((row[0], row[2]) for row in state.scouts_secret_picks)
        if len(picked) != len(set(picked)):
            raise ValueError("a seat picks once per secret event")
        if any(
            not 0 <= seat < state.config.players or not 0 <= pick < 4
            for _, _, seat, pick in state.scouts_secret_picks
        ):
            raise ValueError("a secret pick names a seat and one of four lines")
        bidders = tuple(seat for seat, _, _ in state.scouts_bids)
        if len(bidders) != len(set(bidders)) or any(
            amount < 0 for _, amount, _ in state.scouts_bids
        ):
            raise ValueError("a seat holds one bid of 0 or more")
        callers = tuple(seat for seat, _ in state.scouts_calls)
        called = tuple(amount for _, amount in state.scouts_calls if amount)
        if len(callers) != len(set(callers)) or len(called) != len(set(called)):
            raise ValueError("a seat calls once, and no amount twice")
    elif (
        state.scouts_subcommittees
        or state.scouts_revealed
        or state.scouts_mission_rounds
        or state.scouts_mid_auction_round
        or state.scouts_late_auction_round
        or state.scouts_opening
        or state.scouts_item
        or state.scouts_tasks
        or state.scouts_round_modifier
        or state.scouts_discount_used
        or state.scouts_four_bonus_choices
        or state.scouts_subcommittee_members
        or state.scouts_subcommittee_offers
        or state.scouts_goods
        or state.scouts_goods_cards
        or state.scouts_parked
        or state.scouts_secret_picks
        or state.scouts_secrets_round
        or state.scouts_bids
        or state.scouts_market_cards
        or state.scouts_calls
        or any(player.troops_parked for player in state.players)
    ):
        raise ValueError("Scouts state requires the Arrakeen Scouts module")


def _check_makers(state: GameState) -> None:
    maker_ids = tuple(space_id for space_id, _ in state.maker_bonus_spice)
    if maker_ids not in (
        ("deep_desert", "hagga_basin", "imperial_basin"),
        # Tuek's Sietch joins the Makers while Esmar Tuek plays.
        ("deep_desert", "hagga_basin", "imperial_basin", "tuek_sietch"),
    ):
        raise ValueError("Maker bonus spice must use the three spaces in rules order")
    if any(amount < 0 for _, amount in state.maker_bonus_spice):
        raise ValueError("Maker bonus spice must not be negative")


_SCOUTS_FIELDS: Final = frozenset(
    {
        "scouts_subcommittees",
        "scouts_revealed",
        "scouts_mission_rounds",
        "scouts_mid_auction_round",
        "scouts_late_auction_round",
        "scouts_opening",
        "scouts_item",
        "scouts_tasks",
        "scouts_round_modifier",
        "scouts_discount_used",
        "scouts_four_bonus_choices",
        "scouts_subcommittee_members",
        "scouts_subcommittee_offers",
        "scouts_goods",
        "scouts_goods_cards",
        "scouts_parked",
        "scouts_secret_picks",
        "scouts_secrets_round",
        "scouts_bids",
        "scouts_market_cards",
        "scouts_calls",
    }
)

# Every GameState invariant, in the order the constructor runs them, with
# what each reads (``StateCheck``).
STATE_CHECKS: Final[tuple[StateCheck, ...]] = (
    StateCheck(
        _check_counters,
        frozenset(
            {
                "config",
                "round_number",
                "first_player",
                "reveal_order",
                "combat_intrigue_players",
            }
        ),
    ),
    StateCheck(
        _check_seats, frozenset({"config", "players"}), frozenset({"player_id"})
    ),
    StateCheck(_check_markets, frozenset({"imperium_row", "face_up_contract_ids"})),
    StateCheck(
        _check_contracts,
        frozenset(
            {
                "config",
                "contract_bank",
                "face_up_contract_ids",
                "sardaukar_contract_ids",
                "scouts_goods_cards",
            }
        ),
        frozenset({"active_contract_ids", "completed_contract_ids"}),
    ),
    StateCheck(
        _check_shared_cards,
        frozenset({"conflict_deck", "unused_conflict_ids", "current_conflict_ids"}),
        frozenset({"won_conflict_ids", "alliance_faction_ids"}),
    ),
    StateCheck(_check_reserve, frozenset({"reserve_stacks"})),
    StateCheck(
        _check_bloodlines,
        frozenset(
            {
                "config",
                "sardaukar_commanders_bank",
                "sardaukar_commander_space_ids",
                "skill_stack",
                "skill_face_up",
                "skill_trash",
            }
        ),
        # ``commanders_total`` adds the three Commander counts.
        frozenset(
            {
                "skill_ids",
                "commanders_supply",
                "commanders_garrison",
                "commanders_conflict",
            }
        ),
    ),
    StateCheck(
        _check_tech,
        frozenset({"config", "tech_stacks", "tech_trash"}),
        frozenset({"tech_ids", "secret_project_tech_id", "spies_boxed"}),
    ),
    StateCheck(
        _check_immortality,
        frozenset({"config", "tleilaxu_track_spice", "tleilaxu_deck", "tleilaxu_row"}),
        frozenset({"research_space", "tleilaxu_space", "specimens", "family_atomics"}),
    ),
    StateCheck(
        _check_scouts,
        frozenset({"config", *_SCOUTS_FIELDS}),
        frozenset({"player_id", "troops_parked", "control_space_ids"}),
    ),
    StateCheck(_check_makers, frozenset({"maker_bonus_spice"})),
)
_SEAT_FIELDS: Final = frozenset().union(*(check.seat_fields for check in STATE_CHECKS))


def check_game_state(state: GameState) -> None:
    """Run every ``GameState`` invariant on ``state``, as its constructor does
    (sweeps re-run them after each transition, ``simulation.invariants``)."""

    for check in STATE_CHECKS:
        check.run(state)


def _changed_seat_fields(
    before: tuple[PlayerState, ...], after: tuple[PlayerState, ...]
) -> frozenset[str]:
    """The checked seat fields some seat holds another object for."""

    if len(before) != len(after):
        return _SEAT_FIELDS
    changed: set[str] = set()
    for old, new in zip(before, after, strict=True):
        if old is new:
            continue
        for name in _SEAT_FIELDS - changed:
            if getattr(old, name) is not getattr(new, name):
                changed.add(name)
    return frozenset(changed)


def canonical_state_hash(state: GameState) -> str:
    """Hash state using a canonical representation independent of object identity."""

    encoded = json.dumps(
        _canonicalize(state),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _canonicalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # A field added after hashes were recorded is left out at its
        # default (``RulesetConfig.HASH_OMITTED_AT_DEFAULT``), so the states
        # of every game without it hash as they did before it existed.
        omitted: frozenset[str] = getattr(
            type(value), "HASH_OMITTED_AT_DEFAULT", frozenset()
        )
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in dataclasses.fields(value)
            if not (
                field.name in omitted and getattr(value, field.name) == field.default
            )
        }
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return [_canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if value is None or isinstance(value, bool | int | float | str):
        return value
    message = f"state contains unsupported canonical value: {type(value).__name__}"
    raise TypeError(message)
