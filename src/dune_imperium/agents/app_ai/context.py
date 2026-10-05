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
from typing import NamedTuple

from dune_imperium.config import RulesetConfig
from dune_imperium.content.arrakeen_scouts.types import RoundModifier
from dune_imperium.content.immortality.board import (
    RESEARCH_SPACES,
    genetic_markers_reached,
    research_next_space_ids,
)
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.observation import PlayerView
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.acquisition import revealer_persuasion
from dune_imperium.rules.agent_effects import spice_gained_this_turn
from dune_imperium.rules.sardaukar import commander_cost, eligible_face_up_skill_ids
from dune_imperium.rules.scouts_effects import (
    joinable_subcommittees as _joinable_subcommittees,
)
from dune_imperium.rules.scouts_effects import (
    pending_subcommittee_exclude as _pending_subcommittee_exclude,
)
from dune_imperium.rules.scouts_missions import (
    mission_collectable as _mission_collectable,
)
from dune_imperium.rules.scouts_modifiers import reserve_discount as _reserve_discount
from dune_imperium.rules.tech import face_up_tech_ids

FACTIONS = ("emperor", "spacing_guild", "bene_gesserit", "fremen")

#: Our research space ids in the app's ``ResearchTrack`` index order.
RESEARCH_SPACE_IDS: tuple[str, ...] = tuple(s.space_id for s in RESEARCH_SPACES)
#: The entity ref app_ai gives the fixed Reclaimed Forces card of the Tleilaxu
#: Row (our engine keeps it outside ``tleilaxu_row``, with no instance id).
RECLAIMED_FORCES_REF = "tleilaxu:reclaimed_forces:0"
#: ``GameState.scouts_round_modifier`` while Eyes on Arrakis makes the Faction
#: spaces Combat spaces (``Board.faction_spaces_combat``).
FACTION_SPACES_ARE_COMBAT = RoundModifier.FACTION_SPACES_ARE_COMBAT.value


class Board(NamedTuple):
    """The enabled sets that decide which space archetypes the app deals.

    CHOAM swaps Accept Contract and Dutiful Service for their ``…CHOAM``
    archetypes; Immortality swaps Research Station for
    ``ResearchStationImmortality`` (``RemovedFromSetList``, spec
    immortality.md §1.1). Every space lookup takes one of these instead of a
    bare CHOAM flag so no caller can forget Immortality.

    The app-style options add abilities to the app's space archetypes
    (``catalog.space_entity``): ``bloodlines`` (Commander spaces),
    ``tech_module`` (Landsraad Acquire Tech), ``scouts`` (mission pieces,
    subcommittee offer, Desert Riding) and ``faction_spaces_combat`` (this
    round's Eyes on Arrakis modifier; public, set by ``AppContext.board``).
    All four are False without their option, so such games keep the app's
    archetypes unchanged.
    """

    choam: bool
    immortality: bool = False
    bloodlines: bool = False
    tech_module: bool = False
    scouts: bool = False
    faction_spaces_combat: bool = False
    #: Esmar Tuek is in the game, so Tuek's Sietch is a board space (plan
    #: §11.8: appended after the app's spaces, as the app appends an
    #: expansion's spaces). Public (leaders are public); set by
    #: ``AppContext.board``.
    tueks_sietch: bool = False

    @staticmethod
    def of(config: RulesetConfig) -> Board:
        return Board(
            config.choam_module,
            config.immortality,
            bloodlines=config.bloodlines,
            tech_module=config.tech_module,
            scouts=config.arrakeen_scouts,
        )


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
    def board(self) -> Board:
        """The space-archetype key of this game (see ``Board``), with this
        round's public Scouts modifier (Eyes on Arrakis, scouts.md §4.8)."""

        board = Board.of(self.state.config)
        if self.state.scouts_round_modifier == FACTION_SPACES_ARE_COMBAT:
            board = board._replace(faction_spaces_combat=True)
        if self.state.config.bloodlines and any(
            player.leader_id == "esmar_tuek" for player in self.state.players
        ):
            board = board._replace(tueks_sietch=True)
        return board

    @property
    def round_number(self) -> int:
        """The app's ``Playmat.RoundNumber`` (1 in the first round)."""

        return self.state.round_number

    @property
    def vp_offset(self) -> int:
        """App VP minus ours: 1 under Go to 11, else 0.

        The app's Go to 11 keeps every seat's starting VP at 1 and moves the
        end to 11 (``spec/epic-goto11-promo-draft.md`` §2); our Go to 11 starts
        at 0 and ends at 10 (OQ-091). Reading every VP as ours + 1 puts the
        app's absolute thresholds (the literal 10 of GetVictoryPointValue, the
        decisive-conflict test) at the same distance from the end as in the
        app. Epic + Go to 11 (ours 0 to 12) has no app counterpart; the same
        offset gives it a trigger of 13 (app-style extension, plan §11).
        """

        return 1 if self.state.config.go_to_11 else 0

    def vp(self, player: PlayerState) -> int:
        """``player``'s victory points on the app's scale (see ``vp_offset``)."""

        return player.victory_points + self.vp_offset

    @property
    def endgame_trigger_score(self) -> int:
        """The app's ``EndgameTriggerScore`` on the app's VP scale.

        10, 12 in Epic Game Mode, plus ``vp_offset`` under Go to 11.
        """

        return self.state.config.endgame_victory_points + self.vp_offset

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

    # ===========================================================================
    # Immortality — spec/immortality.md §1.6 "Player state the AI reads"
    # ===========================================================================
    #
    # Everything here is public table state (the Bene Tleilax board, the
    # Axolotl tanks, the face-up Tleilaxu Row, the Family Atomics token) or
    # this seat's own open frame. ``seat`` defaults to this seat. Without
    # the Immortality option every read is the empty board: research rank
    # 0, no markers, no specimens, an empty row (the app's board always
    # builds the tracks, ``WormBoard::.ctor @0x48267c0``; only the
    # abilities that move on them are gated).

    @property
    def immortality(self) -> bool:
        """``M.IsSetEnabled(Immortality = 3)``."""

        return self.state.config.immortality

    def _seat_state(self, seat: int | None) -> PlayerState:
        return self.state.players[self.seat if seat is None else seat]

    def research_space_id(self, seat: int | None = None) -> str:
        """Our id of the seat's research-token space (``"c0r3"`` at start).

        ``""`` without Immortality.
        """

        return self._seat_state(seat).research_space

    def research_rank(self, seat: int | None = None) -> int:
        """``Board.ResearchTrack.CurrentRank(P)``: the app's space index 0..21.

        The app's ``WormResearchTrack::get_SpaceDefs @0x49b4e40`` lists the
        22 spaces in the order of our ``RESEARCH_SPACES`` (spec
        immortality.md §1.5: "The table matches our transcription space for
        space"), so the index is the position in that tuple. 0 without
        Immortality.
        """

        space_id = self.research_space_id(seat)
        if not space_id:
            return 0
        return RESEARCH_SPACE_IDS.index(space_id)

    def research_next_space_ids(self, seat: int | None = None) -> tuple[str, ...]:
        """``SpaceDefs[RR].NextIndices``: the spaces one research step away.

        In the app's order (lower index first; ``GainResearchAbility``'s
        ``Targets``, spec §3.1). Empty at the end of the track or without
        Immortality.
        """

        space_id = self.research_space_id(seat)
        if not space_id:
            return ()
        nxt = research_next_space_ids(space_id)
        return tuple(sorted(nxt, key=RESEARCH_SPACE_IDS.index))

    def genetic_markers(self, seat: int | None = None) -> int:
        """``WormPlayer::get_GeneticMarkers @0x48358f0`` (0, 1 or 2).

        The app adds a marker when the token enters index 7..9 or 19..21
        (``WormResearchTrack::ChangeRank @0x49ba0d0``): our columns 4 and 8,
        ``genetic_markers_reached``.
        """

        space_id = self.research_space_id(seat)
        if not space_id:
            return 0
        return genetic_markers_reached(space_id)

    def tleilaxu_influence(self, seat: int | None = None) -> int:
        """``WormPlayer::GetTleilaxuInfluence @0x48446a0``: rank 0..7."""

        return self._seat_state(seat).tleilaxu_space

    def specimens(self, seat: int | None = None) -> int:
        """``P.GetSpecimens().Count()`` (``@0x482e900``): troops in the tanks.

        Not the player's ``Specimen`` attribute, which the app never writes
        (spec §2.3; ``GetAbundanceLevel(Specimen)`` reads that one).
        """

        return self._seat_state(seat).specimens

    def ungained_troops(self, seat: int | None = None) -> int:
        """``P.UngainedTroops``: a recruit's shortfall from an empty supply."""

        return self._seat_state(seat).ungained_troops

    def ungained_specimens(self, seat: int | None = None) -> int:
        """``P.UngainedSpecimens``: a specimen gain's shortfall."""

        return self._seat_state(seat).ungained_specimens

    def family_atomics(self, seat: int | None = None) -> bool:
        """``P.FamilyAtomics``: true while the once-per-game token is unused."""

        return self._seat_state(seat).family_atomics

    @property
    def tleilaxu_row(self) -> tuple[str, ...]:
        """``Playmat.TleilaxuRow.children`` in the app's order.

        Reclaimed Forces first (built into the row before the two dealt
        cards, ``SetupPhase/<CreateDecks>d__10 @0x4a4a8a0``), then the dealt
        cards; our refill appends like the app's. Reclaimed Forces has no
        instance id in our engine: it is ``RECLAIMED_FORCES_REF``. Empty
        without Immortality.
        """

        if not self.immortality:
            return ()
        return (RECLAIMED_FORCES_REF, *self.state.tleilaxu_row)

    @property
    def tleilaxu_deck_size(self) -> int:
        return len(self.state.tleilaxu_deck)

    def chairdog_return_card_ids(self, seat: int | None = None) -> tuple[str, ...]:
        """``P.ChairdogReturnCards``: in-play cards Chairdog returns to hand."""

        return self._seat_state(seat).chairdog_return_card_ids

    def usurped_row_card_id(self, seat: int | None = None) -> str:
        """The Imperium Row card Usurp grafted this turn (``""`` if none)."""

        return self._seat_state(seat).usurped_row_card_id

    def graft_cards(self) -> tuple[str, str] | None:
        """This seat's open Agent turn's two grafted cards, if it grafted.

        ``(active box card, partner)`` from the own ``agent_effects`` frame
        (``card_id`` / ``graft_card_id``; the engine swaps them as boxes
        resolve). None outside a grafted Agent turn.
        """

        context = self.own_frame_context("agent_effects")
        if context is None:
            return None
        partner = context.get("graft_card_id", "")
        card = context.get("card_id", "")
        if not isinstance(partner, str) or not partner:
            return None
        if not isinstance(card, str):
            return None
        return (card, partner)

    # ===========================================================================
    # Arrakeen Scouts — docs/app-ai/scouts.md §6 (app-style extension)
    # ===========================================================================
    #
    # The public Scouts table state (what the seat's ``PlayerView`` shows),
    # the seat's own sealed bid, and the engine's own predicates evaluated
    # for this seat (they read public state and this seat's own hand,
    # Intrigue, resources, Spies and Agents). Read from ``self.state`` like
    # every other accessor, so a context built on a hypothetical state
    # (``AppContext(new_state, seat, old_view)``) sees that state's goods,
    # parked troops and bids (plan §11.8). Never read: another seat's secret
    # picks or sealed bids, and the identities of the face-down mission
    # cards (``state.scouts_goods_cards``: only their per-location counts,
    # as the view's ``scouts_board_card_counts``). Everything is empty /
    # False without the ``arrakeen_scouts`` option, so no game without it
    # reads a Scouts value.

    @property
    def scouts(self) -> bool:
        """The ``arrakeen_scouts`` option."""

        return self.state.config.arrakeen_scouts

    @property
    def scouts_round_modifier(self) -> str:
        """This round's rule change (``RoundModifier`` value, ``""`` none)."""

        return self.state.scouts_round_modifier

    @property
    def scouts_discount_used(self) -> bool:
        """Whether Market Opening's discount was used up this round."""

        return self.state.scouts_discount_used

    @property
    def scouts_item(self) -> str:
        """The Scouts item being resolved (``""`` outside the Scouts step)."""

        return self.state.scouts_item

    @property
    def scouts_subcommittees(self) -> tuple[str, ...]:
        """The five subcommittees revealed in round 1 (draw order)."""

        return self.state.scouts_subcommittees

    @property
    def scouts_subcommittee_members(self) -> tuple[tuple[str, int], ...]:
        """``(subcommittee id, seat)`` in joining order."""

        return self.state.scouts_subcommittee_members

    def joinable_subcommittees(self, exclude_space: str = "") -> tuple[str, ...]:
        """The engine's ``joinable_subcommittees`` for this seat now.

        Unclaimed, payable and able to do something
        (``rules/scouts_effects.py``); ``exclude_space`` is the space of the
        Agent that takes the seat (``"high_council"``, ``"conflict"``) or
        ``""`` (Corrinth City). Empty once the seat has joined one.
        """

        return _joinable_subcommittees(
            self.state, self.seat, exclude_space=exclude_space
        )

    def pending_subcommittee_exclude(self) -> str | None:
        """The ``exclude_space`` of this seat's open subcommittee choice in its
        own turn frame, or None while that frame offers none."""

        return _pending_subcommittee_exclude(self.state, self.seat)

    @property
    def scouts_goods(self) -> tuple[tuple[str, str, str, int, int], ...]:
        """Bank goods on the board: ``(mission, location, resource, amount,
        seat or -1)`` (public)."""

        return self.state.scouts_goods

    @property
    def scouts_parked(self) -> tuple[tuple[str, int, str, int], ...]:
        """Parked mission troops: ``(mission, seat, location, troops)``."""

        return self.state.scouts_parked

    @property
    def scouts_board_card_counts(self) -> tuple[tuple[str, str, int], ...]:
        """``(mission, location, count)`` of the face-down mission cards.

        The public view's rows (``core/observation.py``
        ``_board_card_counts``: first-seen order of each mission and
        location): only the mission and location of each card are read,
        never its hidden identity.
        """

        counts: dict[tuple[str, str], int] = {}
        for mission_id, location, _hidden in self.state.scouts_goods_cards:
            counts[(mission_id, location)] = counts.get((mission_id, location), 0) + 1
        return tuple(
            (mission_id, location, count)
            for (mission_id, location), count in counts.items()
        )

    def desert_riding_token(self) -> tuple[str, str, str, int, int] | None:
        """Desert Riding's Maker Hooks goods row while the token is out
        (``rules/scouts_missions.py`` ``desert_riding_token``)."""

        return next((row for row in self.scouts_goods if row[2] == "maker_hooks"), None)

    @property
    def scouts_market_cards(self) -> tuple[str, ...]:
        """Critical Moment's revealed Imperium cards (instance ids)."""

        return self.state.scouts_market_cards

    @property
    def scouts_calls(self) -> tuple[tuple[int, int], ...]:
        """Critical Moment's open calls, ``(seat, amount)`` (0 a pass)."""

        return self.state.scouts_calls

    def own_scouts_bid(self) -> int:
        """This seat's own bid in the running sealed auction (-1: none yet;
        the private view's ``scouts_bid``). No other seat's bid is read."""

        return next(
            (amount for seat, amount, _ in self.state.scouts_bids if seat == self.seat),
            -1,
        )

    def mission_collectable(self, space_id: str) -> bool:
        """Whether this seat's visit to ``space_id`` collects mission pieces
        (``rules/scouts_missions.py`` ``mission_collectable``)."""

        return _mission_collectable(self.state, self.seat, space_id)

    def market_opening_discount(self, card_id: str) -> int:
        """Market Opening's Reserve discount on ``card_id`` now (0 or 2;
        ``rules/scouts_modifiers.py`` ``reserve_discount``; public)."""

        return _reserve_discount(self.state, card_id)

    # ===========================================================================
    # Bloodlines — docs/app-ai/bloodlines-systems.md §1.6 "Private information"
    # ===========================================================================
    #
    # Public table state (the Commander spaces, the face-up Skills, the face-up
    # Tech tiles, every seat's Skills, Tech tiles, Commanders and played
    # Navigation cards) for any seat; the private Bloodlines items only for
    # this seat: Kota Odax's Secret Project tile and Steersman Y'rkoon's
    # Navigation slots (``PlayerView.secret_project_tech_id`` /
    # ``navigation_slots`` are the owner's only). The Navigation box and the
    # Twisted deck order are read by nobody. Without the options every read
    # is empty (the fields stay at their defaults).

    @property
    def bloodlines(self) -> bool:
        """The Bloodlines option (app-style extension, plan §11)."""

        return self.state.config.bloodlines

    @property
    def tech_module(self) -> bool:
        """The Bloodlines Tech Module option."""

        return self.state.config.tech_module

    @property
    def commander_space_ids(self) -> tuple[str, ...]:
        """The board spaces still holding a Sardaukar Commander (public)."""

        return self.state.sardaukar_commander_space_ids

    @property
    def skill_face_up(self) -> tuple[str, ...]:
        """The face-up Skill tiles (instance ids ``skill:<id>:<copy>``, public)."""

        return self.state.skill_face_up

    def eligible_skill_ids(self, seat: int | None = None) -> tuple[str, ...]:
        """Face-up Skill ids the seat may still choose (row order, public).

        ``rules/sardaukar.py`` ``eligible_face_up_skill_ids``: one entry per
        distinct face-up Skill the seat does not already hold.
        """

        return eligible_face_up_skill_ids(self.state, self._seat_state(seat))

    def skill_ids(self, seat: int | None = None) -> tuple[str, ...]:
        """The bare Skill ids the seat holds, in gain order (public)."""

        return tuple(
            instance.split(":")[1] for instance in self._seat_state(seat).skill_ids
        )

    def commander_cost(self, seat: int | None = None) -> int:
        """The Solari a Commander costs the seat now (``rules`` ``commander_cost``:
        2 − Honor Guard − Sardaukar High Command, floor 0)."""

        return commander_cost(self._seat_state(seat))

    @property
    def tech_face_up_ids(self) -> tuple[str, ...]:
        """The face-up Tech tile on top of each non-empty stack, stack order."""

        return face_up_tech_ids(self.state)

    def tech_ids(self, seat: int | None = None) -> tuple[str, ...]:
        """The seat's Tech tiles (public, acquisition order)."""

        return self._seat_state(seat).tech_ids

    def tech_flipped(self, seat: int | None = None) -> tuple[str, ...]:
        """The seat's Tech tiles flipped this round (public)."""

        return self._seat_state(seat).tech_flipped

    def has_tech(self, tech_id: str, seat: int | None = None) -> bool:
        """Whether the seat owns the Tech tile ``tech_id`` (public)."""

        return tech_id in self._seat_state(seat).tech_ids

    @property
    def secret_project_tech_id(self) -> str:
        """This seat's own Secret Project tile (``""`` if none). Owner only."""

        return self.me.secret_project_tech_id

    @property
    def navigation_slots(self) -> tuple[str, ...]:
        """This seat's face-down Navigation slots in play order (card ids;
        owner only)."""

        return self.me.navigation_slots

    def navigation_played(self, seat: int | None = None) -> tuple[str, ...]:
        """The Navigation cards the seat has played (public)."""

        return self._seat_state(seat).navigation_played

    @property
    def navigation_active_slot(self) -> int:
        """The slot (1-4) of this seat's Navigation card being played, else 0."""

        return self.me.navigation_active_slot

    @property
    def navigation_trigger_faction(self) -> str:
        """The Faction whose 2nd Influence triggered the card being played."""

        return self.me.navigation_trigger_faction

    def spice_gained_this_turn(self) -> int:
        """This seat's spice gained since its turn opened (``rules``
        ``spice_gained_this_turn``; own counters)."""

        return spice_gained_this_turn(self.me)
