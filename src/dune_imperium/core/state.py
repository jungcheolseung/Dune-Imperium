"""Authoritative game state and deterministic state hashing."""

import dataclasses
import hashlib
import json
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from dune_imperium.config import RulesetConfig
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
    imperium_deck: tuple[str, ...] = ()
    imperium_row: tuple[str, ...] = ()
    intrigue_deck: tuple[str, ...] = ()
    intrigue_discard: tuple[str, ...] = ()
    intrigue_trash: tuple[str, ...] = ()
    imperium_removed: tuple[str, ...] = ()
    contract_bank: tuple[str, ...] = ()
    face_up_contract_ids: tuple[str, ...] = ()
    # Contracts set aside during setup for Shaddam Corrino IV; only he can
    # acquire them [Shaddam Corrino IV card] [FAQ p. 3].
    sardaukar_contract_ids: tuple[str, ...] = ()
    # Face-up six-Leader pool of the OQ-007 draft convention, in draw order.
    # Public for the whole game; Leaders picked from it appear on the seats
    # and the two unpicked Leaders stay unused.
    leader_draft_pool: tuple[str, ...] = ()
    reserve_stacks: tuple[tuple[str, int], ...] = ()
    shield_wall_present: bool = True
    # Pivotal Gambit (Uprising promo): a wild battle icon pledged to the
    # current Conflict's first-place reward; consumed when Combat finishes
    # (OQ-025 project ruling).
    conflict_wild_icon_bonus: bool = False
    # Won Conflict cards that carry that extra wild battle icon in addition
    # to their printed icon; they pair like a wild card during the Endgame.
    wild_icon_conflict_ids: tuple[str, ...] = ()
    maker_bonus_spice: tuple[tuple[str, int], ...] = (
        ("deep_desert", 0),
        ("hagga_basin", 0),
        ("imperial_basin", 0),
    )
    # Intrigue draws owed after the deck ran out mid-transition, resolved by the
    # dispatcher (reshuffling the discard through a chance decision) before the
    # next player decision: (player, count, event source).
    pending_intrigue_draws: tuple[tuple[int, int, str], ...] = ()
    decision_stack: tuple[DecisionFrame, ...] = ()
    event_log: tuple[GameEvent, ...] = ()

    def __post_init__(self) -> None:
        if self.round_number < 0:
            raise ValueError("round_number must not be negative")
        if self.first_player is not None and not (
            0 <= self.first_player < self.config.players
        ):
            raise ValueError("first_player must identify a configured player")
        if len(self.reveal_order) != len(set(self.reveal_order)):
            raise ValueError("a player can appear in the Reveal order only once")
        if any(not 0 <= player < self.config.players for player in self.reveal_order):
            raise ValueError("Reveal order must contain configured players")
        if self.players and len(self.players) != self.config.players:
            raise ValueError("state must contain every configured player")
        if self.players and tuple(player.player_id for player in self.players) != tuple(
            range(self.config.players)
        ):
            raise ValueError("players must be stored in seat order")
        if len(self.imperium_row) > 5:
            raise ValueError("Imperium Row cannot contain more than five cards")
        if len(self.face_up_contract_ids) > 2:
            raise ValueError("the Contract market cannot contain more than two tiles")

        contracts = (
            *self.contract_bank,
            *self.face_up_contract_ids,
            *self.sardaukar_contract_ids,
            *(
                contract_id
                for player in self.players
                for contract_id in (
                    *player.active_contract_ids,
                    *player.completed_contract_ids,
                )
            ),
        )
        if len(contracts) != len(set(contracts)):
            raise ValueError("a Contract cannot occupy two zones")
        if not self.config.choam_module and contracts:
            raise ValueError("Contracts require the CHOAM Module")

        shared_cards = (
            *self.conflict_deck,
            *self.unused_conflict_ids,
            *self.current_conflict_ids,
            *(
                conflict_id
                for player in self.players
                for conflict_id in player.won_conflict_ids
            ),
        )
        if len(shared_cards) != len(set(shared_cards)):
            raise ValueError("a Conflict card cannot occupy two shared zones")
        held_alliances = tuple(
            faction_id
            for player in self.players
            for faction_id in player.alliance_faction_ids
        )
        if len(held_alliances) != len(set(held_alliances)):
            raise ValueError("a Faction Alliance can have only one owner")

        reserve_ids = tuple(card_id for card_id, _ in self.reserve_stacks)
        if len(reserve_ids) != len(set(reserve_ids)):
            raise ValueError("Reserve stack IDs must be unique")
        if any(not card_id or count < 0 for card_id, count in self.reserve_stacks):
            raise ValueError("Reserve stacks require IDs and non-negative counts")

        maker_ids = tuple(space_id for space_id, _ in self.maker_bonus_spice)
        if maker_ids != ("deep_desert", "hagga_basin", "imperial_basin"):
            raise ValueError(
                "Maker bonus spice must use the three spaces in rules order"
            )
        if any(amount < 0 for _, amount in self.maker_bonus_spice):
            raise ValueError("Maker bonus spice must not be negative")

    def push_decision(self, frame: DecisionFrame) -> GameState:
        """Return a state with ``frame`` at the top of the stack."""

        return replace(self, decision_stack=(*self.decision_stack, frame))

    def pop_decision(self) -> GameState:
        """Return a state without the current decision frame."""

        if not self.decision_stack:
            raise IndexError("cannot pop an empty decision stack")
        return replace(self, decision_stack=self.decision_stack[:-1])


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
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in dataclasses.fields(value)
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
