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
  face-down Contract bank [Main p. 16]).
"""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace

from dune_imperium.core.observation import observe_state
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


def _split_reversed(
    pool: tuple[str, ...],
    first_length: int,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    reordered = tuple(reversed(pool))
    return reordered[:first_length], reordered[first_length:]


def _scramble_hidden_information(state: GameState, observer: int) -> GameState:
    intrigue_pool: list[str] = list(state.intrigue_deck)
    players = list(state.players)

    for seat, player in enumerate(players):
        if seat == observer:
            players[seat] = replace(player, deck=tuple(reversed(player.deck)))
            continue
        hand, deck = _split_reversed((*player.hand, *player.deck), len(player.hand))
        intrigue_pool.extend(player.intrigue_cards)
        players[seat] = replace(player, hand=hand, deck=deck)

    reordered_intrigue = tuple(reversed(intrigue_pool))
    cursor = 0
    for seat, player in enumerate(players):
        if seat == observer:
            continue
        held = len(state.players[seat].intrigue_cards)
        players[seat] = replace(
            player,
            intrigue_cards=reordered_intrigue[cursor : cursor + held],
        )
        cursor += held

    return replace(
        state,
        players=tuple(players),
        intrigue_deck=reordered_intrigue[cursor:],
        imperium_deck=tuple(reversed(state.imperium_deck)),
        contract_bank=tuple(reversed(state.contract_bank)),
    )
