"""Per-transition invariants for full-game verification sweeps.

``PlayerState`` and ``GameState`` already enforce their local invariants on
every construction (non-negative quantities, per-player component totals,
single-zone rules within one container). The checks here add what only a
sweep can see across containers and time:

- global card conservation: every tracked instance sits in exactly one zone
  and the game-wide set never changes after setup (Reserve copies instead
  satisfy a stack-plus-live-count equation because trashed Reserve cards
  return to their stacks and copy IDs are re-issued);
- progress: a pending player decision must offer at least one legal action;
- visibility: a player's observation must not depend on hidden information
  (deck orders, opponents' hand and Intrigue identities [Main p. 7], the
  face-down Contract bank [Main p. 16]);
- event visibility: a public event may only name cards that sit in a public
  zone once the transition is applied (OQ-010 ruling 3), so a live event log
  filtered by ``visible_to`` never leaks a hidden identity.
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace

from dune_imperium.core.events import GameEvent
from dune_imperium.core.observation import observe_state, resolving_intrigue_ids
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState


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


def _all_personal_instances(state: GameState) -> Iterator[str]:
    yield from state.imperium_deck
    yield from state.imperium_row
    yield from state.imperium_removed
    for player in state.players:
        yield from _personal_zone_instances(player)


def _all_intrigue_instances(state: GameState) -> Iterator[str]:
    yield from state.intrigue_deck
    yield from state.intrigue_discard
    yield from state.intrigue_trash
    for player in state.players:
        yield from player.intrigue_cards
        yield from player.intrigue_faceup


def _all_conflict_ids(state: GameState) -> Iterator[str]:
    yield from state.conflict_deck
    yield from state.unused_conflict_ids
    yield from state.current_conflict_ids
    for player in state.players:
        yield from player.won_conflict_ids


def _all_contract_ids(state: GameState) -> Iterator[str]:
    yield from state.contract_bank
    yield from state.face_up_contract_ids
    yield from state.sardaukar_contract_ids
    for player in state.players:
        yield from player.active_contract_ids
        yield from player.completed_contract_ids


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
        )


def _require_unique(instance_ids: Iterable[str], zone_name: str) -> tuple[str, ...]:
    instances = tuple(instance_ids)
    seen: set[str] = set()
    for instance in instances:
        if instance in seen:
            raise InvariantViolation(f"{zone_name} holds {instance} in two zones")
        seen.add(instance)
    return instances


def check_state_invariants(state: GameState, census: CardCensus) -> None:
    """Check global conservation of every tracked card population."""

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

    Decks and the Contract bank are face down [Main pp. 4-6, 16]; hands and
    held Intrigue are known only to their owner [Main p. 7]. Everything else
    (in play, discard piles, trash, face-up Intrigue, the Imperium Row,
    set-aside cards, active and completed Contracts, battle cards) has been
    face up at some point and stays re-checkable under OQ-010.
    """

    hidden: set[str] = set()
    hidden.update(state.imperium_deck)
    hidden.update(state.intrigue_deck)
    hidden.update(state.contract_bank)
    hidden.update(state.conflict_deck)
    for player in state.players:
        hidden.update(player.hand)
        hidden.update(player.deck)
        hidden.update(player.intrigue_cards)
        # Cards that reached the hand through a public move stay known.
        hidden.difference_update(player.hand_public)
    # A played Intrigue is revealed even while its choices still resolve.
    hidden.difference_update(resolving_intrigue_ids(state))
    return frozenset(hidden)


def _payload_strings(event: GameEvent) -> Iterator[tuple[str, str]]:
    for key, value in event.payload:
        if isinstance(value, str):
            yield key, value


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


def _scramble_hidden_information(state: GameState, observer: int) -> GameState:
    intrigue_pool: list[str] = list(state.intrigue_deck)
    players = list(state.players)
    resolving = set(resolving_intrigue_ids(state))

    for seat, player in enumerate(players):
        if seat == observer:
            players[seat] = replace(player, deck=tuple(reversed(player.deck)))
            continue
        # Publicly known hand cards stay in the hand; only the face-down
        # draws trade places with the deck.
        known = set(player.hand_public)
        secret_hand = tuple(card for card in player.hand if card not in known)
        secret, deck = _split_reversed((*secret_hand, *player.deck), len(secret_hand))
        hand = (*player.hand_public, *secret)
        intrigue_pool.extend(
            card for card in player.intrigue_cards if card not in resolving
        )
        players[seat] = replace(player, hand=hand, deck=deck)

    reordered_intrigue = tuple(reversed(intrigue_pool))
    cursor = 0
    for seat, player in enumerate(players):
        if seat == observer:
            continue
        kept = tuple(
            card for card in state.players[seat].intrigue_cards if card in resolving
        )
        held = len(state.players[seat].intrigue_cards) - len(kept)
        players[seat] = replace(
            player,
            intrigue_cards=(*kept, *reordered_intrigue[cursor : cursor + held]),
        )
        cursor += held

    return replace(
        state,
        players=tuple(players),
        intrigue_deck=reordered_intrigue[cursor:],
        imperium_deck=tuple(reversed(state.imperium_deck)),
        contract_bank=tuple(reversed(state.contract_bank)),
    )
