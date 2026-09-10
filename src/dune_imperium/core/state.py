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
    # Whether the Conflict-end trigger window (Harvest Cells gained as a
    # reward, OQ-057) has been offered for the current Combat.
    combat_end_triggers_offered: bool = False
    # Seats that played a Combat Intrigue card in the current Conflict
    # (Counterattack, Immortality); cleared when the Combat phase resets.
    combat_intrigue_players: tuple[int, ...] = ()
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
    # effect has finished with the decision stack.
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
        if len(self.combat_intrigue_players) != len(set(self.combat_intrigue_players)):
            raise ValueError("a player is listed once among Combat Intrigue players")
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

        # Every module's zones are re-checked on each state copy, and a copy
        # happens several times per engine step, so the module flag gates the
        # scan: with the module off the only legal contents are none at all,
        # which an emptiness test settles without building tuples and sets.
        if self.config.choam_module:
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
        elif (
            self.contract_bank
            or self.face_up_contract_ids
            or self.sardaukar_contract_ids
            or any(
                player.active_contract_ids or player.completed_contract_ids
                for player in self.players
            )
        ):
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

        if self.sardaukar_commanders_bank < 0:
            raise ValueError("the Commander bank must not be negative")
        if self.config.bloodlines:
            if len(self.sardaukar_commander_space_ids) != len(
                set(self.sardaukar_commander_space_ids)
            ):
                raise ValueError("a board space holds at most one Sardaukar Commander")
            skills = (
                *self.skill_stack,
                *self.skill_face_up,
                *self.skill_trash,
                *(skill_id for player in self.players for skill_id in player.skill_ids),
            )
            if len(skills) != len(set(skills)):
                raise ValueError("a Skill tile cannot occupy two zones")
        elif (
            self.skill_stack
            or self.skill_face_up
            or self.skill_trash
            or self.sardaukar_commander_space_ids
            or self.sardaukar_commanders_bank
            or any(
                player.skill_ids or player.commanders_total for player in self.players
            )
        ):
            raise ValueError("Sardaukar Commanders require the Bloodlines expansion")
        if self.config.tech_module:
            tech = (
                *(tech_id for stack in self.tech_stacks for tech_id in stack),
                *self.tech_trash,
                *(
                    tech_id
                    for player in self.players
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
            any(self.tech_stacks)
            or self.tech_trash
            or any(
                player.tech_ids or player.secret_project_tech_id or player.spies_boxed
                for player in self.players
            )
        ):
            raise ValueError("Tech tiles require the Tech Module")

        if self.tleilaxu_track_spice < 0:
            raise ValueError("the Tleilaxu track spice must not be negative")
        if self.config.immortality:
            tleilaxu_cards = (*self.tleilaxu_deck, *self.tleilaxu_row)
            if len(tleilaxu_cards) != len(set(tleilaxu_cards)):
                raise ValueError("a Tleilaxu card cannot occupy two zones")
        elif (
            self.tleilaxu_deck
            or self.tleilaxu_row
            or self.tleilaxu_track_spice
            or any(
                player.research_space
                or player.tleilaxu_space
                or player.specimens
                or player.family_atomics
                for player in self.players
            )
        ):
            raise ValueError("the Bene Tleilax board requires Immortality")

        maker_ids = tuple(space_id for space_id, _ in self.maker_bonus_spice)
        if maker_ids not in (
            ("deep_desert", "hagga_basin", "imperial_basin"),
            # Tuek's Sietch joins the Makers while Esmar Tuek plays.
            ("deep_desert", "hagga_basin", "imperial_basin", "tuek_sietch"),
        ):
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
