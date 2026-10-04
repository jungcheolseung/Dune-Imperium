"""What an app_ai seat may read, gathered in one place.

The app AI decides on the live match object but reads only information a
seat at the table has (``analysis/ai/10-information-fairness.md``). app_ai is a
``StateAgent`` for the same reason: the open frame contexts, the Reveal's
Persuasion pool and the deck multisets are not in ``PlayerView``. Every read
of ``GameState`` goes through this class so the honesty rules live in one
place:

- may read: everything in the seat's ``PlayerView``; ``state.config``; the
  seat's own hand, held Intrigue and the *multiset* of its own deck; each
  opponent's ``hand + deck`` *multiset* (the project's determinization
  convention, ``agents/determinize.py``: order and the hand/deck split stay
  hidden); counts of hidden zones; the seat's own open frame contexts; the
  per-turn counters on ``PlayerState``; events visible to the seat.
- must not read: any deck order (own or shared), the Imperium, Intrigue,
  Contract or Conflict deck contents, an opponent's hand, deck or Intrigue
  identities individually, another seat's frame context.

``tests/unit/agents/app_ai/test_honesty.py`` enforces this: the agent's
choice must not change when ``determinize`` re-deals every hidden zone.
"""

from collections import Counter
from collections.abc import Mapping
from functools import cached_property

from dune_imperium.config import RulesetConfig
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import revealer_persuasion

FACTIONS = ("emperor", "spacing_guild", "bene_gesserit", "fremen")


def card_id(instance_id: str) -> str:
    """The bare card id of a card instance id.

    ``imperium:<id>:<n>``, ``reserve:<id>:<n>``, ``intrigue:<id>:<n>``,
    ``contract:<id>`` and ``player:<seat>:starter:<id>:<n>``.
    """

    parts = instance_id.split(":")
    if parts[0] == "player":
        return parts[3]
    if len(parts) >= 2:
        return parts[1]
    return instance_id


class AppContext:
    """One decision's honest read access for seat ``seat``.

    Built fresh for every decision; cached properties are per decision, like
    the app profile's per-``MakeChoice`` caches.
    """

    def __init__(self, state: GameState, seat: int, view: PlayerView) -> None:
        self.state = state
        self.seat = seat
        self.view = view

    # -- game and table ------------------------------------------------------

    @property
    def config(self) -> RulesetConfig:
        return self.state.config

    @property
    def choam(self) -> bool:
        """The CHOAM module (the app's ``IsSetEnabled(CHOAMModule)``)."""

        return self.state.config.choam_module

    @property
    def round_number(self) -> int:
        """The app's ``Playmat.RoundNumber`` (1 in the first round)."""

        return self.state.round_number

    @property
    def endgame_trigger_score(self) -> int:
        """The app's ``EndgameTriggerScore``: 10, or 12 in Epic Game Mode."""

        return 12 if self.state.config.epic_game else 10

    @property
    def first_player(self) -> int | None:
        return self.state.first_player

    @property
    def decision_kind(self) -> str | None:
        return self.view.decision_kind

    # -- players ---------------------------------------------------------------

    @property
    def me(self) -> PlayerState:
        return self.state.players[self.seat]

    @property
    def players(self) -> tuple[PlayerState, ...]:
        """Every seat's state. Read only public fields of other seats."""

        return self.state.players

    @property
    def opponents(self) -> tuple[PlayerState, ...]:
        """The other seats in seat order (the app's ``Player.Opponents``)."""

        return tuple(p for p in self.state.players if p.player_id != self.seat)

    def player(self, seat: int) -> PlayerState:
        """A seat's state. Read only public fields unless ``seat == self.seat``."""

        return self.state.players[seat]

    # -- own private zones -------------------------------------------------------

    @property
    def hand(self) -> tuple[str, ...]:
        """Own hand (instance ids, hand order)."""

        return self.me.hand

    @property
    def intrigue_cards(self) -> tuple[str, ...]:
        """Own held Intrigue (instance ids)."""

        return self.me.intrigue_cards

    @cached_property
    def deck_multiset(self) -> Counter[str]:
        """Own draw pile as a multiset of card ids (never its order)."""

        return Counter(card_id(i) for i in self.me.deck)

    @property
    def deck_size(self) -> int:
        return len(self.me.deck)

    def hidden_pool(self, seat: int) -> Counter[str]:
        """An opponent's ``Hand ∪ Deck`` as a multiset of card ids.

        The app's ``EstOpponentStrength`` reads exactly this union; a
        perfect-memory player can rebuild it from public acquisitions.
        """

        if seat == self.seat:
            raise ValueError("hidden_pool is for opponents; use hand/deck_multiset")
        player = self.state.players[seat]
        return Counter(card_id(i) for i in (*player.hand, *player.deck))

    # -- board ------------------------------------------------------------------

    @property
    def current_conflict_id(self) -> str | None:
        """The face-up Conflict card, if any."""

        ids = self.state.current_conflict_ids
        return ids[-1] if ids else None

    @property
    def conflict_deck_size(self) -> int:
        return len(self.state.conflict_deck)

    @property
    def imperium_row(self) -> tuple[str, ...]:
        return self.state.imperium_row

    @property
    def reserve_stacks(self) -> tuple[tuple[str, int], ...]:
        return self.state.reserve_stacks

    @property
    def face_up_contract_ids(self) -> tuple[str, ...]:
        return self.state.face_up_contract_ids

    @property
    def shield_wall_present(self) -> bool:
        return self.state.shield_wall_present

    def space_occupants(self, space_id: str) -> tuple[int, ...]:
        """Seats with an Agent on ``space_id``, in seat order."""

        return tuple(
            p.player_id for p in self.state.players if space_id in p.agent_locations
        )

    def post_owner(self, post_id: str) -> int | None:
        """The seat whose Spy is on ``post_id``, if any."""

        for p in self.state.players:
            if post_id in p.spy_post_ids:
                return p.player_id
        return None

    # -- own open frames ------------------------------------------------------------

    def own_frame_context(self, kind: str) -> Mapping[str, ActionValue] | None:
        """The context of the topmost open frame of ``kind`` this seat owns.

        Frame ownership is the frame decision's owner. Another seat's frame is
        never returned.
        """

        for frame in reversed(self.state.decision_stack):
            if frame.kind != kind:
                continue
            owner = getattr(frame.decision, "owner", None)
            if owner != self.seat:
                return None
            return dict(frame.context)
        return None

    @property
    def top_frame_context(self) -> Mapping[str, ActionValue]:
        """The context of the decision being answered (always this seat's)."""

        frame = self.state.decision_stack[-1]
        return dict(frame.context)

    def reveal_persuasion(self) -> int | None:
        """The spendable Persuasion of this seat's open Reveal, if any."""

        return revealer_persuasion(self.state, self.seat)
