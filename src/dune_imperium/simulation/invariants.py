"""Per-transition invariants for full-game verification sweeps.

``PlayerState`` and ``GameState`` already enforce their local invariants on
every construction (non-negative quantities, per-player component totals,
single-zone rules within one container); a ``GameState`` copy runs only the
invariants whose fields it replaced (``GameState._check_copy``), so a sweep
re-runs every one of them after each transition (``check_game_state``),
which a wrong field table could otherwise let pass. The checks here add what
only a sweep can see across containers and time:

- global card conservation: every tracked instance sits in exactly one zone
  and the game-wide set never changes after setup (Reserve copies instead
  satisfy a stack-plus-live-count equation because trashed Reserve cards
  return to their stacks and copy IDs are re-issued, and Sardaukar Commanders
  are counters, so their total is conserved instead of a set), and Piter De
  Vries' Twisted Intrigue cards never sit in the shared Intrigue deck
  (OQ-097);
- progress: a pending player decision must offer at least one legal action,
  and an owed Emperor track Spy waits only inside its own seat's turn;
- visibility: a player's observation must not depend on hidden information
  (deck orders, opponents' hand and Intrigue identities [Main p. 7], the
  face-down Contract bank [Main p. 16]);
- event visibility: a public event may only name cards that sit in a public
  zone once the transition is applied (OQ-010 ruling 3), so a live event log
  filtered by ``visible_to`` never leaks a hidden identity.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from typing import Final

from dune_imperium.content.uprising.board import Faction
from dune_imperium.content.uprising.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.uprising.intrigue import is_twisted_intrigue
from dune_imperium.content.uprising.types import ConflictTier
from dune_imperium.core.decisions import ChanceDecision
from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import (
    known_card_seats,
    observe_state,
    peeked_card_id,
    peeked_intrigue_ids,
    resolving_intrigue_ids,
    revealed_contract_ids,
)
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState, check_game_state
from dune_imperium.rules.frames import FrameKind, turn_owner_of, turn_start_is_open
from dune_imperium.rules.scouts_auctions import bid_cap
from dune_imperium.rules.scouts_secrets import pick_alternatives


class InvariantViolation(AssertionError):
    """One violated conservation, progress, or visibility invariant."""


_RESERVE_PREFIX = "reserve:"


def _reserve_identity(instance_id: str) -> str | None:
    if not instance_id.startswith(_RESERVE_PREFIX):
        return None
    return instance_id.split(":", 2)[1]


def _personal_zone_instances(player: PlayerState) -> Iterator[str]:
    yield from player.deck
    yield from player.hand
    yield from player.discard_pile
    yield from player.in_play
    yield from player.trashed
    yield from player.imperium_set_aside
    # Rise of Ix: Ilesa Ecaz's face-down set-aside card.
    if player.set_aside_card_id:
        yield player.set_aside_card_id


def _all_personal_instances(state: GameState) -> Iterator[str]:
    yield from state.imperium_deck
    yield from state.imperium_row
    yield from state.imperium_removed
    yield from state.scouts_market_cards
    yield from state.tleilaxu_deck
    yield from state.tleilaxu_row
    for player in state.players:
        yield from _personal_zone_instances(player)


def _board_cards(state: GameState, prefix: str) -> Iterator[str]:
    """Arrakeen Scouts: face-down cards a mission put on the board."""

    for _, _, card_id in state.scouts_goods_cards:
        if card_id.startswith(prefix):
            yield card_id


def _all_intrigue_instances(state: GameState) -> Iterator[str]:
    yield from _board_cards(state, "intrigue")
    yield from state.intrigue_deck
    yield from state.intrigue_discard
    yield from state.twisted_deck_stock
    yield from state.navigation_stock
    for player in state.players:
        yield from player.intrigue_cards
        yield from player.intrigue_faceup
        yield from player.twisted_deck
        yield from player.navigation_slots
        yield from player.navigation_played
        yield from player.navigation_box


def _all_conflict_ids(state: GameState) -> Iterator[str]:
    yield from state.conflict_deck
    yield from state.unused_conflict_ids
    yield from state.current_conflict_ids
    for player in state.players:
        yield from player.won_conflict_ids


def _all_contract_ids(state: GameState) -> Iterator[str]:
    yield from _board_cards(state, "contract:")
    yield from state.contract_bank
    yield from state.face_up_contract_ids
    yield from state.sardaukar_contract_ids
    yield from state.contract_trash
    for player in state.players:
        yield from player.active_contract_ids
        yield from player.completed_contract_ids


def _all_tech_ids(state: GameState) -> Iterator[str]:
    """Yield every Tech tile in play: 18 tiles, 17 without CHOAM Transports.

    The Ixian Embassy's three stacks hold them face down below the top
    [Bloodlines pp. 2, 6]; a tile then sits on a player board, face down on
    Kota Odax's Leader as the Secret Project, or in the trash.
    """

    for stack in state.tech_stacks:
        yield from stack
    yield from state.tech_trash
    for player in state.players:
        yield from player.tech_ids
        if player.secret_project_tech_id:
            yield player.secret_project_tech_id


def _all_skill_ids(state: GameState) -> Iterator[str]:
    """Yield every one of the 14 Skill tiles, two per Skill [Bloodlines p. 3]."""

    yield from state.skill_stack
    yield from state.skill_face_up
    yield from state.skill_trash
    for player in state.players:
        yield from player.skill_ids


def _commander_count(state: GameState) -> int:
    """Count the seven Sardaukar Commanders [Bloodlines p. 3].

    Commanders are counters rather than identified tokens, so conservation is
    a total instead of a set: the bank, the board spaces still holding one,
    and every seat's supply, garrison and Conflict Commanders.
    """

    return (
        state.sardaukar_commanders_bank
        + len(state.sardaukar_commander_space_ids)
        + sum(player.commanders_total for player in state.players)
    )


def _reserve_totals(state: GameState) -> tuple[tuple[str, int], ...]:
    totals = dict(state.reserve_stacks)
    for instance_id in _all_personal_instances(state):
        identity = _reserve_identity(instance_id)
        if identity is not None:
            totals[identity] = totals.get(identity, 0) + 1
    return tuple(sorted(totals.items()))


@dataclass(frozen=True, slots=True)
class CardCensus:
    """Game-wide card populations captured right after setup."""

    fixed_personal: frozenset[str]
    reserve_totals: tuple[tuple[str, int], ...]
    intrigue: frozenset[str]
    conflicts: frozenset[str]
    contracts: frozenset[str]
    objectives: tuple[tuple[str, ...], ...]
    # Expansion components: Tech tiles and Skill tiles are identified
    # instances, Sardaukar Commanders only a count. All three are empty or
    # zero while their option is off.
    tech: frozenset[str]
    skills: frozenset[str]
    commanders: int

    @classmethod
    def from_state(cls, state: GameState) -> CardCensus:
        return cls(
            fixed_personal=frozenset(
                instance_id
                for instance_id in _all_personal_instances(state)
                if _reserve_identity(instance_id) is None
            ),
            reserve_totals=_reserve_totals(state),
            intrigue=frozenset(_all_intrigue_instances(state)),
            conflicts=frozenset(_all_conflict_ids(state)),
            contracts=frozenset(_all_contract_ids(state)),
            objectives=tuple(player.objective_ids for player in state.players),
            tech=frozenset(_all_tech_ids(state)),
            skills=frozenset(_all_skill_ids(state)),
            commanders=_commander_count(state),
        )


def _require_unique(instance_ids: Iterable[str], zone_name: str) -> tuple[str, ...]:
    instances = tuple(instance_ids)
    seen: set[str] = set()
    for instance in instances:
        if instance in seen:
            raise InvariantViolation(f"{zone_name} holds {instance} in two zones")
        seen.add(instance)
    return instances


def _ix_fields_absent(player: PlayerState) -> bool:
    """Whether every Rise of Ix seat field is at its default."""

    return not (
        player.dreadnoughts_supply
        or player.dreadnoughts_garrison
        or player.dreadnoughts_conflict
        or player.freighter_space
        or player.negotiators
        or player.snooper_faction_ids
        or player.set_aside_card_id
        or player.set_aside_returned_turn
        or player.turns_finished_round
    )


def _check_rise_of_ix(state: GameState) -> None:
    """Rise of Ix's seat fields (observation v39, stage P4a).

    A game without the option leaves every one at its default, so its state
    hashes are those of the engine before the fields existed
    (``PlayerState.HASH_OMITTED_AT_DEFAULT``). In a Rise of Ix game a seat
    owns two dreadnoughts at most, the one on a Control space included
    [Rise of Ix p. 6]. The Intrigue cards a seat knows are
    ``_check_known_intrigue``'s.
    """

    if not state.config.rise_of_ix:
        for player in state.players:
            if not _ix_fields_absent(player):
                raise InvariantViolation(
                    f"player {player.player_id} holds Rise of Ix state "
                    "outside a Rise of Ix game"
                )
        return
    for player in state.players:
        on_spaces = sum(
            1 for _, seat, _ in state.dreadnought_control if seat == player.player_id
        )
        owned = (
            player.dreadnoughts_supply
            + player.dreadnoughts_garrison
            + player.dreadnoughts_conflict
            + on_spaces
        )
        if owned > 2:
            raise InvariantViolation(
                f"player {player.player_id} owns {owned} dreadnoughts"
            )


def _check_known_intrigue(state: GameState) -> None:
    """The Intrigue cards a seat knows and another seat does not (OQ-149,
    ``rules.intrigue_knowledge``): only Imperium Ceremony (Immortality) and
    Rise of Ix record them, and every one is in the Intrigue deck or in
    another seat's held Intrigue -- a card that reached a public zone (a
    played one resolving included) or the seat's own hand has left the record
    by the end of the transition."""

    recorded = state.config.immortality or state.config.rise_of_ix
    deck = frozenset(state.intrigue_deck)
    resolving = frozenset(resolving_intrigue_ids(state))
    for player in state.players:
        if player.known_intrigue_ids and not recorded:
            raise InvariantViolation(
                f"player {player.player_id} records known Intrigue in a game "
                "without Immortality or Rise of Ix"
            )
        held_elsewhere = frozenset(
            card
            for other in state.players
            if other.player_id != player.player_id
            for card in other.intrigue_cards
        )
        stale = [
            card
            for card in player.known_intrigue_ids
            if card in resolving or (card not in deck and card not in held_elsewhere)
        ]
        if stale:
            raise InvariantViolation(
                f"player {player.player_id} still records known Intrigue {stale} "
                "played face up or outside the deck and the other seats' hands"
            )


def check_state_invariants(state: GameState, census: CardCensus) -> None:
    """Check every ``GameState`` invariant, then global conservation of every
    tracked card population."""

    check_game_state(state)
    for player in state.players:
        # OQ-145: the cards every seat knows on top of a deck really are its
        # top cards, in order (``rules.deck_top`` settles it after every
        # transition).
        top = player.deck_public_top
        if player.deck[: len(top)] != top:
            raise InvariantViolation(
                f"player {player.player_id}'s public deck top {top} is not "
                f"the top of the deck {player.deck[: len(top) + 1]}"
            )
    _check_rise_of_ix(state)
    _check_known_intrigue(state)
    personal = _require_unique(_all_personal_instances(state), "personal cards")
    fixed_personal = frozenset(
        instance_id
        for instance_id in personal
        if _reserve_identity(instance_id) is None
    )
    if fixed_personal != census.fixed_personal:
        raise InvariantViolation(
            "starting or Imperium instances changed: "
            f"missing={sorted(census.fixed_personal - fixed_personal)} "
            f"new={sorted(fixed_personal - census.fixed_personal)}"
        )
    if _reserve_totals(state) != census.reserve_totals:
        raise InvariantViolation(
            "Reserve stack counts plus live copies changed: "
            f"{_reserve_totals(state)} != {census.reserve_totals}"
        )

    intrigue = frozenset(_require_unique(_all_intrigue_instances(state), "Intrigue"))
    if intrigue != census.intrigue:
        raise InvariantViolation(
            "Intrigue instances changed: "
            f"missing={sorted(census.intrigue - intrigue)} "
            f"new={sorted(intrigue - census.intrigue)}"
        )
    # Twisted cards stay in the discard when it is reshuffled (OQ-097, user
    # ruling 2026-10-04, "다른 사람이 twisted 카드를 뽑는 일은 없도록"), so
    # neither the shared deck nor the Scouts board cards dealt from it ever
    # hold one.
    stray = sorted(
        card
        for card in (*state.intrigue_deck, *_board_cards(state, "intrigue"))
        if is_twisted_intrigue(card)
    )
    if stray:
        raise InvariantViolation(f"the shared Intrigue deck holds Twisted {stray}")

    conflicts = frozenset(_all_conflict_ids(state))
    if conflicts != census.conflicts:
        raise InvariantViolation("the Conflict card population changed")
    contracts = frozenset(_all_contract_ids(state))
    if contracts != census.contracts:
        raise InvariantViolation("the Contract population changed")
    for player, dealt in zip(state.players, census.objectives, strict=True):
        if player.objective_ids != dealt:
            raise InvariantViolation(
                f"player {player.player_id} Objectives changed from {dealt}"
            )

    tech = frozenset(_require_unique(_all_tech_ids(state), "Tech"))
    if tech != census.tech:
        raise InvariantViolation(
            "Tech tile instances changed: "
            f"missing={sorted(census.tech - tech)} "
            f"new={sorted(tech - census.tech)}"
        )
    skills = frozenset(_require_unique(_all_skill_ids(state), "Skill"))
    if skills != census.skills:
        raise InvariantViolation(
            "Skill tile instances changed: "
            f"missing={sorted(census.skills - skills)} "
            f"new={sorted(skills - census.skills)}"
        )
    commanders = _commander_count(state)
    if commanders != census.commanders:
        raise InvariantViolation(
            f"the Sardaukar Commander count changed: {commanders} "
            f"!= {census.commanders}"
        )


def check_track_spy_queue(state: GameState) -> None:
    """Fail when an owed Emperor track Spy is left waiting outside its turn.

    Only the turn owner's entries wait for its ``place_track_spy`` (user
    ruling 2026-10-04); every other entry opens at once, unless a chance
    frame, a Conflict's own reward choices or a completed Contract's reward
    window are on top (``spy_moves.track_spy_is_queued``). Checked at a
    player decision.
    """

    if not state.pending_track_spies:
        return
    top = state.decision_stack[-1] if state.decision_stack else None
    if top is not None and (
        isinstance(top.decision, ChanceDecision)
        or str(top.kind).startswith("combat_reward")
        or top.kind == FrameKind.CONTRACT_REWARD_ICONS
    ):
        return
    owner = turn_owner_of(state)
    stray = [seat for seat, _ in state.pending_track_spies if seat != owner]
    if stray:
        raise InvariantViolation(
            f"Emperor track Spies of seats {stray} wait outside their turn "
            f"(turn owner {owner})"
        )
    # Only an owner action can owe a Spy inside the turn, and any owner
    # action ends the turn start (OQ-095 (6)): the turn-passing cards are
    # never offered beside an owed Spy, so they need no hold of their own.
    if owner is not None and turn_start_is_open(state, owner):
        raise InvariantViolation(
            f"seat {owner} owes an Emperor track Spy while its turn start "
            "is still open"
        )


def check_owed_draws(state: GameState) -> None:
    """Fail when a triggered draw waits anywhere but in its seat's own turn.

    A draw a trigger earns waits as its seat's own step only inside that
    seat's Agent or Reveal turn (user ruling 2026-10-10, OQ-106,
    ``frames.draw_waits_for_owner``); the turn's end is not offered while
    one waits, and ``owed_draws.pay_stale_owed_draws`` would pay one left
    anywhere else. Only an owner action earns one, so it never waits while
    the turn's start is open (OQ-095 (6)). Checked at a player decision.
    """

    owner = turn_owner_of(state)
    stray = [
        seat.player_id
        for seat in state.players
        if seat.owed_draws and seat.player_id != owner
    ]
    if stray:
        raise InvariantViolation(
            f"triggered draws of seats {stray} wait outside their turn "
            f"(turn owner {owner})"
        )
    if (
        owner is not None
        and state.players[owner].owed_draws
        and turn_start_is_open(state, owner)
    ):
        raise InvariantViolation(
            f"seat {owner} has a triggered draw waiting while its turn start "
            "is still open"
        )


def check_observation_privacy(state: GameState) -> None:
    """Fail when any observation depends on hidden information.

    Every player's view must be identical on a state that differs only in
    hidden card positions: all deck orders, which identities sit in an
    opponent's hand versus their deck, an opponent's held Intrigue
    identities versus the Intrigue deck [Main p. 7], and the face-down
    Contract bank order [Main p. 16].
    """

    for observer in range(state.config.players):
        baseline = observe_state(state, observer)
        scrambled = observe_state(
            _scramble_hidden_information(state, observer), observer
        )
        if scrambled != baseline:
            raise InvariantViolation(
                f"player {observer}'s observation depends on hidden information"
            )


def _hidden_instances(state: GameState) -> frozenset[str]:
    """Card instances no seat may currently identify from the table.

    Exactly the cards ``known_card_seats`` lists: face-down decks, stacks and
    the Contract bank [Main pp. 4-6, 16], hands and held Intrigue [Main p. 7]
    and the other private glimpses it tracks. Everything else (in play,
    discard piles, trash, face-up Intrigue, the Imperium and Tleilaxu Rows,
    set-aside cards, active and completed Contracts, battle cards) has been
    face up at some point and stays re-checkable under OQ-010. One list
    serves the log, the undo boundary and this invariant, so a new hidden
    zone cannot be missed by one of them.
    """

    return frozenset(known_card_seats(state))


# Payload fields naming cards that left a face-up zone in the step: their
# identities were public up to then, so naming them reveals nothing even
# though they now sit in a hidden one (Clear the Market shuffles the old
# face-up Contracts into the bank, OQ-083).
_LEFT_FACE_UP_FIELDS: Final = frozenset({("scouts_contracts_cleared", "removed")})


def _payload_strings(event: GameEvent) -> Iterator[tuple[str, str]]:
    for key, value in event.payload:
        if (event.kind, key) in _LEFT_FACE_UP_FIELDS:
            continue
        if isinstance(value, str):
            yield key, value
        elif isinstance(value, tuple):
            # An id list (cleanup-2c-7): each id is checked like a string.
            for item in value:
                if isinstance(item, str):
                    yield key, item


# The only payload fields a secret choice's public event may carry.
_SEALED_EVENT_FIELDS: Final = {
    "scouts_secret_picked": frozenset({"item_id", "player"}),
    "scouts_bid_confirmed": frozenset({"item_id", "player"}),
}


def check_event_visibility(state: GameState, events: Iterable[GameEvent]) -> None:
    """Fail when a public event names a card that is hidden after the step.

    ``state`` is the state the events describe (after the transition). A
    public event (``visible_to=None``) feeds every seat's live log, so any
    card identity in its payload must sit in a public zone of ``state``; an
    identity that is still in a deck, the Contract bank, a hand, or a held
    Intrigue set would leak through the log even though the observation
    redacts it. Restricted events are the owner's business and are not
    checked here.
    """

    hidden = _hidden_instances(state)
    for event in events:
        if event.visible_to is not None:
            continue
        sealed = _SEALED_EVENT_FIELDS.get(event.kind)
        if sealed is not None and not {key for key, _ in event.payload} <= sealed:
            # A secret choice's public event says who chose, never what.
            raise InvariantViolation(
                f"public event {event.kind} ({event.event_id}) carries a sealed "
                f"value: {sorted(key for key, _ in event.payload)}"
            )
        for key, value in _payload_strings(event):
            if value in hidden:
                raise InvariantViolation(
                    f"public event {event.kind} ({event.event_id}) names hidden "
                    f"card {value!r} in payload field {key!r}"
                )


def _split_reversed(
    pool: tuple[str, ...],
    first_length: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    reordered = tuple(reversed(pool))
    return reordered[:first_length], reordered[first_length:]


def _scramble_conflicts(state: GameState) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Reshuffle the Conflict deck within each tier, boxed cards included.

    Tiers are printed on the Conflict backs and the deck is layered in the
    open -- "Conflict 카드를 I, II, III 뒷면별로 나눈다" and the finished deck
    is "위에서부터 I 1장, II 5장, III 4장" [Main p. 4] -- so which tier sits
    at each depth is public and must stay put. Which card of that tier sits
    there is not: the unused I and II cards go to the box "앞면을 보지 않고"
    [Main p. 4], so no seat has seen them either, and knowing that set is
    knowing the deck's contents. Both zones therefore share one hidden pool
    per tier.
    """

    def tier_of(conflict_id: str) -> ConflictTier:
        return CONFLICTS_BY_ID[conflict_id].tier

    # Each tier's pool lists the deck cards in depth order and then the boxed
    # ones, so dealing from its end hands the deck the boxed cards first and
    # reverses what is left: every position gets a different card of the same
    # tier whenever that tier holds more than one.
    pools: dict[ConflictTier, list[str]] = {}
    for conflict_id in (*state.conflict_deck, *state.unused_conflict_ids):
        pools.setdefault(tier_of(conflict_id), []).append(conflict_id)

    deck = tuple(
        pools[tier_of(conflict_id)].pop() for conflict_id in state.conflict_deck
    )
    unused = tuple(sorted(card for pool in pools.values() for card in pool))
    return deck, unused


def _keep_known_intrigue(
    deck: tuple[str, ...],
    peeked: int,
    known: frozenset[str],
    dealt: tuple[str, ...],
) -> tuple[str, ...]:
    """The scrambled Intrigue deck: the first ``peeked`` cards and the cards
    the observer knows stay where they are, every other place takes the
    next card of ``dealt``."""

    if not known:
        return (*deck[:peeked], *dealt)
    rest = iter(dealt)
    return tuple(
        card if index < peeked or card in known else next(rest)
        for index, card in enumerate(deck)
    )


def _scramble_hidden_information(state: GameState, observer: int) -> GameState:
    # Imperium Ceremony shows the observer the deck's top cards, which
    # therefore stay in place, and so do the Intrigue cards the observer
    # knows (Rise of Ix, ``PlayerState.known_intrigue_ids``): in the deck at
    # their depth, and in another seat's hand.
    peeked_intrigue = peeked_intrigue_ids(state, observer)
    known_intrigue = frozenset(state.players[observer].known_intrigue_ids)
    revealed_contracts = revealed_contract_ids(state)
    intrigue_pool: list[str] = [
        card
        for card in state.intrigue_deck[len(peeked_intrigue) :]
        if card not in known_intrigue
    ]
    scrambled_conflict_deck, scrambled_unused_conflicts = _scramble_conflicts(state)
    players = list(state.players)
    resolving = set(resolving_intrigue_ids(state))

    for seat, player in enumerate(players):
        # A face-down Twisted Intrigue deck only shows its size; the
        # Navigation box is hidden to everyone, the slots to opponents.
        twisted = tuple(reversed(player.twisted_deck))
        box = tuple(reversed(player.navigation_box))
        player = replace(player, navigation_box=box)
        if seat != observer:
            player = replace(
                player, navigation_slots=tuple(reversed(player.navigation_slots))
            )
        if seat == observer:
            # Controlled lets the owner see the top card while deciding: it
            # stays put and the rest of the deck reorders. So do the deck's
            # public top cards (OQ-145), known to every seat.
            peeked = peeked_card_id(state, observer)
            fixed = max(
                len(player.deck_public_top),
                1 if peeked and player.deck and player.deck[0] == peeked else 0,
            )
            deck = (*player.deck[:fixed], *reversed(player.deck[fixed:]))
            players[seat] = replace(player, deck=deck, twisted_deck=twisted)
            continue
        # Publicly known hand cards stay in the hand, and the deck's public
        # top cards (OQ-145) stay on top; only the face-down draws trade
        # places with the rest of the deck, and with Ilesa Ecaz's face-down
        # set-aside card (Rise of Ix), which came from that hand.
        known = set(player.hand_public)
        secret_hand = tuple(card for card in player.hand if card not in known)
        public_top = player.deck_public_top
        aside = player.set_aside_card_id
        pool = (*secret_hand, *player.deck[len(public_top) :])
        secret, rest = _split_reversed(
            (*pool, aside) if aside else pool, len(secret_hand)
        )
        if aside:
            aside, rest = rest[-1], rest[:-1]
        hand = (*player.hand_public, *secret)
        deck = (*public_top, *rest)
        intrigue_pool.extend(
            card
            for card in player.intrigue_cards
            if card not in resolving and card not in known_intrigue
        )
        players[seat] = replace(
            player,
            hand=hand,
            deck=deck,
            twisted_deck=twisted,
            set_aside_card_id=aside,
        )

    # Arrakeen Scouts: the board's face-down Intrigue cards are as unknown
    # as the deck, so they join the pool and take its first cards back.
    board_intrigue = [
        row for row in state.scouts_goods_cards if row[2].startswith("intrigue")
    ]
    intrigue_pool.extend(row[2] for row in board_intrigue)
    reordered_intrigue = tuple(reversed(intrigue_pool))
    board_cards = {
        row: reordered_intrigue[index] for index, row in enumerate(board_intrigue)
    }
    cursor = len(board_intrigue)
    for seat, player in enumerate(players):
        if seat == observer:
            continue
        kept = tuple(
            card
            for card in state.players[seat].intrigue_cards
            if card in resolving or card in known_intrigue
        )
        held = len(state.players[seat].intrigue_cards) - len(kept)
        players[seat] = replace(
            player,
            intrigue_cards=(*kept, *reordered_intrigue[cursor : cursor + held]),
        )
        cursor += held

    scouts_goods_cards = tuple(
        (row[0], row[1], board_cards.get(row, row[2]))
        for row in state.scouts_goods_cards
    )
    # Arrakeen Scouts: another seat's secret pick moves to the next line it
    # could as well be (``pick_alternatives``).
    secret_picks = []
    for row in state.scouts_secret_picks:
        alternatives = pick_alternatives(state, row)
        if row[2] != observer and len(alternatives) > 1:
            index = alternatives.index(row[3])
            row = (*row[:3], alternatives[(index + 1) % len(alternatives)])
        secret_picks.append(row)
    # The original game's Baron: another seat's unrevealed Masterstroke
    # Factions become Factions it did not choose (docs/rules/imperium-base.md
    # 14).
    for seat, player in enumerate(players):
        if seat != observer and player.masterstroke_factions and not (
            player.masterstroke_revealed
        ):
            others = tuple(
                faction.value
                for faction in Faction
                if faction.value not in player.masterstroke_factions
            )
            players[seat] = replace(
                player,
                masterstroke_factions=others[: len(player.masterstroke_factions)],
            )
    # A sealed bid moves to another amount its seat could have bid.
    bids = tuple(
        (seat, (amount + 1) % (bid_cap(state, seat) + 1), confirmed)
        if seat != observer
        else (seat, amount, confirmed)
        for seat, amount, confirmed in state.scouts_bids
    )
    return replace(
        state,
        players=tuple(players),
        scouts_goods_cards=scouts_goods_cards,
        scouts_secret_picks=tuple(secret_picks),
        scouts_bids=bids,
        intrigue_deck=_keep_known_intrigue(
            state.intrigue_deck,
            len(peeked_intrigue),
            known_intrigue,
            reordered_intrigue[cursor:],
        ),
        imperium_deck=tuple(reversed(state.imperium_deck)),
        # The Contracts an open Coercive Negotiation revealed are face up to
        # the whole table [Coercive Negotiation card] and stay on top of the
        # bank; only the face-down rest reorders.
        contract_bank=(
            *state.contract_bank[: len(revealed_contracts)],
            *reversed(state.contract_bank[len(revealed_contracts) :]),
        ),
        navigation_stock=tuple(reversed(state.navigation_stock)),
        # Each Tech stack is face down below its top [Bloodlines p. 6].
        tech_stacks=tuple(
            (*stack[:1], *reversed(stack[1:])) for stack in state.tech_stacks
        ),
        # The Conflict deck's tier layering is public but its contents are
        # not, so the scramble permutes within each tier band and across the
        # boxed cards of that tier (see ``_scramble_conflicts``).
        conflict_deck=scrambled_conflict_deck,
        unused_conflict_ids=scrambled_unused_conflicts,
        # The Skill stack is face down below the four face-up tiles
        # [Bloodlines p. 3]; ``skill_face_up`` is the public counterpart.
        skill_stack=tuple(reversed(state.skill_stack)),
        # The Tleilaxu deck sits face down on the Imperium deck
        # [Immortality p. 4]; ``tleilaxu_row`` is the public counterpart.
        tleilaxu_deck=tuple(reversed(state.tleilaxu_deck)),
        # The undealt Twisted Intrigue stock is the last global zone
        # ``hidden_card_owners`` maps to nobody, so it moves too; the
        # per-seat ``twisted_deck`` is reversed above.
        twisted_deck_stock=tuple(reversed(state.twisted_deck_stock)),
    )
