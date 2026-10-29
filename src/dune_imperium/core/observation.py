"""Player-scoped, immutable observations with explicit redaction."""

import json
from copy import replace
from dataclasses import dataclass
from functools import cache
from typing import Final

from dune_imperium.config import BaseGame
from dune_imperium.content.bloodlines.tech import (
    TECH_TILES_BY_ID,
    TechAbility,
    has_tech,
)
from dune_imperium.content.uprising.effect_dsl import RevealContractsTakeOne
from dune_imperium.content.uprising.intrigue import INTRIGUE_CARDS_BY_INSTANCE
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.core.actions import ActionValue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.player import Influence, PlayerState, Resources
from dune_imperium.core.state import GamePhase, GameState


@dataclass(frozen=True, slots=True)
class PublicPlayerView:
    """Public board and supply information for one seat.

    Hand, deck, and held-Intrigue identities deliberately have no field here,
    so adapter code cannot accidentally recover them from an opponent's view.
    The one summary of them is ``deck_pool``: which cards, and how many of
    each, are somewhere in the deck or the hidden part of the hand, without
    saying which copy or which of the two (see the field).
    """

    player: int
    leader_id: str | None
    leader_face_id: str | None
    victory_points: int
    resources: Resources
    influence: Influence
    # Zone sizes are public by project convention (OQ-010): the physical
    # game leaves every pile and hand count visible while identities stay
    # governed by the explicit visibility rules.
    hand_size: int
    deck_size: int
    intrigue_card_count: int
    # Hand cards every seat can identify because they entered the hand
    # through a public move (OQ-010); see ``PlayerState.hand_public``.
    hand_public: tuple[str, ...]
    # The cards in the deck and the hidden part of the hand together, as
    # card ids (never instance ids) sorted by id: every seat can work it out
    # from public moves alone -- a card enters a seat's deck or hand only
    # from a public source (the starting deck, a face-up Row, reserve or
    # Tleilaxu Row purchase, a face-up discard pile reshuffled) and leaves
    # them only to a public place (in play, a face-up discard pile, the
    # trash, or out of the game with a Leader's setup) -- so it is public
    # under OQ-010's "information once public stays checkable" (ruling 6,
    # user decision 2026-10-13). Which of the two zones a card is in stays
    # hidden; the pool prints no instance ids.
    deck_pool: tuple[str, ...]
    agents_available: int
    agent_locations: tuple[str, ...]
    swordmaster_acquired: bool
    troops_supply: int
    troops_garrison: int
    troops_conflict: int
    memories: int
    sandworms_conflict: int
    spies_supply: int
    spy_post_ids: tuple[str, ...]
    alliance_faction_ids: tuple[str, ...]
    control_space_ids: tuple[str, ...]
    # Kept current by the engine after every step: before the seat's
    # Reveal what its units in the Conflict provide, from the Reveal on the
    # marker with the revealed swords and every later change [Main p. 12].
    combat_strength: int
    has_revealed: bool
    high_council: bool
    maker_hooks: bool
    feyd_track_space: str
    # Bloodlines Sardaukar Commanders and the public Skill tiles.
    commanders_supply: int
    commanders_garrison: int
    commanders_conflict: int
    skill_ids: tuple[str, ...]
    commander_recruited_turn: bool
    contracts_completed_turn: int
    # Contract icons this turn that found nothing they could take, waiting for
    # the turn to end or for a token to become reachable (OQ-059).
    held_contract_icons: int
    # Recruit and specimen shortfalls waiting for troops to return to this
    # seat's supply this turn (OQ-030, OQ-049); the troops count includes the
    # Suspensor Suits troops owed to the Conflict (OQ-042).
    ungained_troops: int
    ungained_specimens: int
    commander_discount_turn: int
    ignores_influence_requirements_turn: bool
    granted_agent_icon_turn: str
    combat_icon_turn: bool
    bene_gesserit_boost_pending: bool
    tactics_track_space: int
    agent_in_conflict: int
    twisted_deck_size: int
    navigation_remaining: int
    navigation_played: tuple[str, ...]
    reveal_persuasion_bonus: int
    # Tech Module: the tiles in the supply (public), the ones flipped face
    # down this round, whether a Secret Project tile waits on the Leader
    # (its identity is the owner's) and the Spies returned to the box.
    tech_ids: tuple[str, ...]
    tech_flipped: tuple[str, ...]
    has_secret_project: bool
    spies_boxed: int
    spies_recalled_turn: int
    # Immortality: the tokens on the Bene Tleilax board, the specimens in
    # the Axolotl tanks and the unused Family Atomics token (all public).
    research_space: str
    tleilaxu_space: int
    specimens: int
    family_atomics: bool
    reveal_persuasion_round_bonus: int
    # Chairdog's pending returns and Usurp's borrowed Row card (public,
    # both cards are face up in play).
    chairdog_return_card_ids: tuple[str, ...]
    usurped_row_card_id: str
    in_play: tuple[str, ...]
    # Every card reaches a discard pile face up (acquired cards [Main p. 13],
    # played and revealed cards after Clean Up [Main pp. 9, 12, 20], cards
    # discarded from hand), so the pile stays re-checkable by everyone until a
    # reshuffle hides it again (OQ-010 ruling 1).
    discard_pile: tuple[str, ...]
    trashed: tuple[str, ...]
    intrigue_faceup: tuple[str, ...]
    imperium_set_aside: tuple[str, ...]
    objective_ids: tuple[str, ...]
    won_conflict_ids: tuple[str, ...]
    face_down_battle_card_ids: tuple[str, ...]
    active_contract_ids: tuple[str, ...]
    # A completed Contract was face up while active and its completion was
    # announced before it flipped [Main p. 16], so its identity stays public
    # like a flipped battle card (OQ-010 ruling 2).
    completed_contract_ids: tuple[str, ...]
    # Emperor track Influence 4 Spies this seat still has to place: during
    # its own turn each waits for the owner's ``place_track_spy`` and holds
    # the turn end back (user ruling 2026-10-04). Public: the track is.
    track_spies_owed: int = 0
    # The original game's Mentat on this seat's Leader, one of its Agents
    # this round [DI p. 18]; public, like every Agent.
    mentat: bool = False
    # The original game's Baron Harkonnen: whether he holds Masterstroke
    # Factions not yet revealed (that he chose is public, which is his alone,
    # docs/rules/imperium-base.md 14), and the Factions once revealed.
    masterstroke_secret: bool = False
    masterstroke_revealed_factions: tuple[str, ...] = ()
    # The deck's top cards every seat knows, top first (OQ-145): cards put
    # face up on top of the deck stay public until they are drawn or the deck
    # is shuffled; ``PlayerState.deck_public_top``.
    deck_public_top: tuple[str, ...] = ()
    # The original game's public markers: the spaces The Voice bars this seat's
    # next Agent from, Infiltrate's turn marker (its Agents ignore enemy Agents
    # this turn) and Recruitment Mission's round marker (cards it acquires may
    # go on top of its deck); ``PlayerState`` fields of the same names.
    voice_blocked_space_ids: tuple[str, ...] = ()
    enemy_agents_ignored_turn: bool = False
    acquire_to_deck_top_round: bool = False
    # Rise of Ix (observation v39, stage P4a; plan 17.8), all public
    # (docs/rules/rise-of-ix.md 13 "Snooper token, Negotiator, Freighter,
    # dreadnought | 모두"): the seat's dreadnoughts in its supply, garrison
    # and the Conflict, its Freighter's Shipping space, its Negotiators, the
    # tracks still holding Tessia Vernius' Snooper tokens, whether Ilesa Ecaz
    # has a card set aside (which card is hers alone,
    # ``PrivatePlayerView.set_aside_card_id``), whether it came back to the
    # hand this turn, and the turns finished this round; ``PlayerState``
    # fields of the same names.
    dreadnoughts_supply: int = 0
    dreadnoughts_garrison: int = 0
    dreadnoughts_conflict: int = 0
    freighter_space: int = 0
    negotiators: int = 0
    snooper_faction_ids: tuple[str, ...] = ()
    has_set_aside_card: bool = False
    set_aside_returned_turn: bool = False
    turns_finished_round: int = 0


@dataclass(frozen=True, slots=True)
class IxPending:
    """The observer's own open Rise of Ix decision (observation v39's
    ``ix_pending``; plan 17.8 review item 4), read from the context of the
    frame it decides (``ix_pending_of``).

    ``shipping_rewards`` are the Shipping track spaces (1 to 3) whose reward
    a Freighter recall still owes, taken in any order [Rise of Ix p. 5];
    ``tech_discount`` the open Acquire Tech's Tech Discount (0 to 2) and
    ``tech_payment`` what it is paid with, "spice" or Appropriate's "solari"
    [Rise of Ix pp. 4, 10] ("" with no Acquire Tech open);
    ``negotiators_returnable`` the Negotiators the seat may still return
    toward it [Rise of Ix p. 4]. Stage P4c writes the context keys.
    """

    shipping_rewards: tuple[int, ...] = ()
    tech_discount: int = 0
    tech_payment: str = ""
    negotiators_returnable: int = 0


NO_IX_PENDING: Final = IxPending()


@dataclass(frozen=True, slots=True)
class PrivatePlayerView:
    """Card identities available only to the observing player."""

    deck_size: int
    hand: tuple[str, ...]
    intrigue_cards: tuple[str, ...]
    # The deck's top card when a card effect lets the owner see it: always
    # with Glowglobes (Tech tile, "look at the top card of your deck at any
    # time"), and with Controlled (Twisted Intrigue) while the owner decides
    # what to do with it; "" otherwise (``peeked_card_id`` below).
    peeked_card_id: str = ""
    # Imperium Ceremony: the Intrigue deck's top cards while the owner
    # keeps one of them; () otherwise.
    peeked_intrigue_ids: tuple[str, ...] = ()
    # Steersman Y'rkoon's face-down Navigation slots, which he may look at
    # any time [Bloodlines p. 12].
    navigation_slots: tuple[str, ...] = ()
    # Kota Odax's face-down Secret Project tile [Kota Odax of Ix card].
    secret_project_tech_id: str = ""
    # Arrakeen Scouts: the seat's own secret picks not yet due, as (event
    # round, event id, pick index).
    scouts_secret_picks: tuple[tuple[int, str, int], ...] = ()
    # The seat's own bid in the sealed auction running now (-1: none yet).
    scouts_bid: int = -1
    # Stage B1 (OQ-111): the card the seat picked for its Agent turn and has
    # not placed yet (seen by no other seat), and whether it is grafted.
    agent_card_pick: str = ""
    agent_card_pick_graft: bool = False
    # Stage B3 (OQ-111 (4)): the rows the seat picked toward one waiting
    # effect and has not finished (seen by no other seat), as (action id,
    # arguments) -- the effect row first (``rules.effect_steps``).
    effect_pick: tuple[tuple[str, tuple[tuple[str, ActionValue], ...]], ...] = ()
    # The original game's Baron Harkonnen: his own Masterstroke Factions,
    # chosen in secret before the first round [FAQ p. 1] (section 14).
    masterstroke_factions: tuple[str, ...] = ()
    # Rise of Ix (observation v39; docs/rules/rise-of-ix.md 13): Ilesa
    # Ecaz's own set-aside card; the Intrigue cards the seat knows
    # (``PlayerState.known_intrigue_ids``) by place -- the Intrigue deck's
    # top card, cards by depth from the deck's bottom as (depth, card), 0 the
    # bottom card, and cards another seat holds as (seat, card); and its own
    # open Rise of Ix decision.
    set_aside_card_id: str = ""
    known_intrigue_top: str = ""
    known_intrigue_bottom: tuple[tuple[int, str], ...] = ()
    known_intrigue_held: tuple[tuple[int, str], ...] = ()
    ix_pending: IxPending = NO_IX_PENDING


@dataclass(frozen=True, slots=True)
class PlayerView:
    """Information safe to expose to a single player or policy."""

    player: int
    revision: int
    phase: GamePhase
    round_number: int = 0
    first_player: int | None = None
    # Public summary of the pending decision frame: its kind, the deciding
    # player (None for chance), and the acting turn owner when the frame
    # tracks one. Frame contexts stay unexposed until each kind's fields are
    # individually cleared for visibility.
    decision_kind: str | None = None
    decision_owner: int | None = None
    turn_owner: int | None = None
    reveal_order: tuple[int, ...] = ()
    endgame_intrigue_complete: bool = False
    players: tuple[PublicPlayerView, ...] = ()
    private: PrivatePlayerView | None = None
    current_conflict_ids: tuple[str, ...] = ()
    # Cards left in the face-down Conflict deck (their order and identity
    # stay hidden); the browser draws the deck in its printed frame.
    conflict_deck_size: int = 0
    combat_intrigue_complete: bool = False
    combat_rewards_resolved: bool = False
    imperium_row: tuple[str, ...] = ()
    # Cards left in the face-down Imperium deck and Intrigue deck: their
    # order and identity stay hidden, but every shared deck's count is public
    # ("개인 deck과 공용 deck·bank의 남은 장수는 언제나 공개한다."
    # docs/rules/information-visibility.md, a project convention; the decks
    # are face down [Main p. 4]). Shown to the server and the UI; not encoded.
    imperium_deck_size: int = 0
    intrigue_deck_size: int = 0
    imperium_removed: tuple[str, ...] = ()
    # Intrigue cards already played (hence revealed [Main p. 7]) whose
    # choices are still being resolved; they stay in the owner's held set
    # until the last slot resolves, so the public view names them here.
    intrigue_resolving: tuple[str, ...] = ()
    intrigue_discard: tuple[str, ...] = ()
    contract_bank_size: int = 0
    face_up_contract_ids: tuple[str, ...] = ()
    sardaukar_contract_ids: tuple[str, ...] = ()
    contract_trash: tuple[str, ...] = ()
    # The bank's top Contracts an open Coercive Negotiation has revealed,
    # face up to every seat while its owner chooses [Coercive Negotiation
    # card; Main p. 7]. Shown to the server and the UI; not encoded.
    revealed_contract_ids: tuple[str, ...] = ()
    # The face-up six-Leader pool of the OQ-007 draft option, public to
    # everyone for the whole game (empty without the option).
    leader_draft_pool: tuple[str, ...] = ()
    reserve_stacks: tuple[tuple[str, int], ...] = ()
    shield_wall_present: bool = True
    # Pivotal Gambit (promo): "gain 1 Influence" rewards pledged to this
    # Conflict's first-place reward (OQ-025).
    conflict_first_place_influence_bonus: int = 0
    maker_bonus_spice: tuple[tuple[str, int], ...] = ()
    # Bloodlines: Commanders still on the board and in the bank, and the
    # Skill tiles (the stack order stays hidden; only its size is shown).
    sardaukar_commander_space_ids: tuple[str, ...] = ()
    sardaukar_commanders_bank: int = 0
    skill_stack_size: int = 0
    skill_face_up: tuple[str, ...] = ()
    skill_trash: tuple[str, ...] = ()
    # Tech Module: the face-up top of each Ixian Embassy stack ("" for an
    # empty stack), the stack sizes (the order below the top is hidden) and
    # the trashed tiles.
    tech_face_up: tuple[str, ...] = ()
    tech_stack_sizes: tuple[int, ...] = ()
    tech_trash: tuple[str, ...] = ()
    # Immortality: the face-up Tleilaxu Row (Reclaimed Forces is fixed), the
    # face-down deck's size, and the setup spice still on the Tleilaxu track.
    tleilaxu_row: tuple[str, ...] = ()
    tleilaxu_deck_size: int = 0
    tleilaxu_track_spice: int = 0
    # Seats that played a Combat Intrigue card in this Conflict (public).
    combat_intrigue_players: tuple[int, ...] = ()
    # Arrakeen Scouts, all public (docs/rules/arrakeen-scouts.md): the five
    # subcommittees, every item revealed so far as (round, item id), the
    # mission layout's rounds, the auction rounds (0 until drawn), the item
    # being resolved and this round's rule change. Nothing unrevealed is in
    # the state to hide: each item is drawn in the round it appears.
    scouts_subcommittees: tuple[str, ...] = ()
    # (subcommittee id, member seat), in joining order.
    scouts_subcommittee_members: tuple[tuple[str, int], ...] = ()
    scouts_revealed: tuple[tuple[int, str], ...] = ()
    scouts_mission_rounds: tuple[int, ...] = ()
    scouts_mid_auction_round: int = 0
    scouts_late_auction_round: int = 0
    scouts_item: str = ""
    scouts_round_modifier: str = ""
    scouts_discount_used: bool = False
    # Mission pieces: goods rows, parked-troop rows, and how many face-down
    # cards each mission left on each location (their identities are hidden).
    scouts_goods: tuple[tuple[str, str, str, int, int], ...] = ()
    scouts_parked: tuple[tuple[str, int, str, int], ...] = ()
    scouts_board_card_counts: tuple[tuple[str, str, int], ...] = ()
    # Secret picks still hidden, as (event round, event id, seat): who has
    # picked in which event, never what; and the last round whose due picks
    # were revealed (a pick left after its event's next round is one of the
    # two-round lines).
    scouts_secret_pending: tuple[tuple[int, str, int], ...] = ()
    scouts_secrets_round: int = 0
    # The running auction: who has confirmed a sealed bid (never how much),
    # Critical Moment's revealed cards and its open calls (seat, amount).
    scouts_bids_confirmed: tuple[int, ...] = ()
    scouts_market_cards: tuple[str, ...] = ()
    scouts_calls: tuple[tuple[int, int], ...] = ()
    # Epic Game Mode (``RulesetConfig.epic_game``), public like every setup
    # option: the game ends at 12 instead of 10 [Rise of Ix p. 10].
    epic_game: bool = False
    # The base game (``RulesetConfig.base_game``), public like every setup
    # option (docs/base-game-and-ix-plan.md 4.2 item 8).
    base_game: BaseGame = BaseGame.UPRISING
    # The original game's Sort Through the Chaos winner, who takes the
    # Mentat at the next round's start [FAQ p. 4]; public, like the reward.
    mentat_owed_to: int | None = None
    # Rise of Ix (``RulesetConfig.rise_of_ix``), public like every setup
    # option, and the dreadnoughts on Control spaces as (space, seat,
    # leaving) (``GameState.dreadnought_control``), public.
    rise_of_ix: bool = False
    dreadnought_control: tuple[tuple[str, int, bool], ...] = ()
    # The open Agent turn's Agent boxes, as (card instance, still pending):
    # box 0 the placed card, then box 1 its graft partner (Immortality);
    # empty outside an Agent turn. Both cards lie face up in play and each
    # box's resolution is announced (``agent_box_cards``).
    agent_boxes: tuple[tuple[str, bool], ...] = ()
    public_data: tuple[tuple[str, ActionValue], ...] = ()
    private_data: tuple[tuple[str, ActionValue], ...] = ()


# A separate-lines card (OQ-058) stays in play under ``intrigue_effects``.
_RESOLVING_INTRIGUE_FRAME_KINDS = frozenset({"intrigue_choice", "intrigue_effects"})

# The Agent-turn effect frame's two boxes (``rules.graft_boxes``): the box
# being resolved sits in ``card_id``/``pending_agent_effect`` and the other
# in ``graft_card_id``/``graft_pending_effect``; ``graft_active_box`` says
# which of the two (box 0 the placed card, box 1 the partner) is in
# ``card_id`` (absent: box 0).
_AGENT_BOX_SLOTS: Final = (
    ("card_id", "pending_agent_effect"),
    ("graft_card_id", "graft_pending_effect"),
)
_ACTIVE_BOX_KEY: Final = "graft_active_box"


def agent_box_cards(state: GameState) -> tuple[tuple[str, bool], ...]:
    """The open Agent turn's boxes: (card, pending) for box 0, then box 1."""

    for frame in state.decision_stack:
        if str(frame.kind) != "agent_effects":
            continue
        context = dict(frame.context)
        slots = (
            _AGENT_BOX_SLOTS[::-1]
            if context.get(_ACTIVE_BOX_KEY) == 1
            else _AGENT_BOX_SLOTS
        )
        boxes: list[tuple[str, bool]] = []
        for card_key, pending_key in slots:
            card_id = context.get(card_key)
            if isinstance(card_id, str) and card_id:
                boxes.append((card_id, context.get(pending_key) is True))
        return tuple(boxes)
    return ()


def resolving_intrigue_ids(state: GameState) -> tuple[str, ...]:
    """Return played Intrigue cards still held while their choices resolve."""

    resolving: list[str] = []
    for frame in state.decision_stack:
        if str(frame.kind) not in _RESOLVING_INTRIGUE_FRAME_KINDS:
            continue
        card_id = dict(frame.context).get("card_id")
        if isinstance(card_id, str) and card_id not in resolving:
            resolving.append(card_id)
    return tuple(resolving)


_SEALED_VALUE_PREFIXES: Final = ("scouts_pick:", "scouts_bid:", "masterstroke:")


def secret_pick_id(event_round: int, seat: int) -> str:
    """The registry id of ``seat``'s Arrakeen Scouts secret pick."""

    return f"{_SEALED_VALUE_PREFIXES[0]}{event_round}:{seat}"


def secret_bid_id(round_number: int, seat: int) -> str:
    """The registry id of ``seat``'s Arrakeen Scouts sealed bid."""

    return f"{_SEALED_VALUE_PREFIXES[1]}{round_number}:{seat}"


def masterstroke_id(seat: int) -> str:
    """The registry id of the Baron at ``seat``'s two Masterstroke Factions."""

    return f"{_SEALED_VALUE_PREFIXES[2]}{seat}"


def is_sealed_value_id(value: str) -> bool:
    """Whether a registry id is a seat's sealed choice rather than a card.

    Such a value is revealed by the rules when it falls due, never by its
    seat's own choice, so revealing even the actor's own is a reveal.
    """

    return value.startswith(_SEALED_VALUE_PREFIXES)


def known_card_seats(state: GameState) -> dict[str, frozenset[int]]:
    """Map every card that is not public to the seats that can identify it.

    Cards absent from the result are public to every seat. Face-down decks
    and the Contract bank are known to nobody [Main pp. 4-6, 16], and so are
    the expansions' face-down stacks: the Tleilaxu deck [Immortality p. 4],
    the Skill stack [Bloodlines p. 3] and each Tech stack below its face-up
    top [Bloodlines p. 6], as well as the Conflict cards set aside unused at
    setup. The bank Contracts an open Coercive Negotiation has revealed are
    public (``revealed_contract_ids``). A hand or a held Intrigue card is
    known to its owner only [Main p. 7], except the cards OQ-010 keeps
    public: publicly acquired hand cards (``PlayerState.hand_public``) and a
    played Intrigue whose choices are still resolving. The deck's top cards
    put there face up (Bypass Protocol, Recruitment Mission, a Tleilaxu
    card; ``PlayerState.deck_public_top``, OQ-145) are public until they
    are drawn or the deck is shuffled, and that wins over the owner-only
    peeks below. A hidden card its owner has been shown is known to that
    owner: a peeked deck top (Controlled, Glowglobes), Long Live the
    Fighters' top three, Imperium Ceremony's two Intrigue cards, Kota Odax's
    bottom Tech tiles and Secret Project. An Intrigue card a seat knows
    (``PlayerState.known_intrigue_ids``, OQ-149: the card Imperium Ceremony
    or Viscount Hundro Moritani put back on the deck's top, the cards Rise of
    Ix puts on its bottom, such a card another seat drew) adds that seat to
    its knowers (``rules.intrigue_knowledge``). Rise of Ix
    (docs/rules/rise-of-ix.md 13): Ilesa Ecaz's face-down set-aside card is
    hers alone. An Arrakeen Scouts
    secret pick is listed under ``secret_pick_id`` for its seat until it is
    due, and a sealed bid under ``secret_bid_id`` until every seat has
    confirmed, and the original game's Baron Harkonnen's Masterstroke
    Factions under ``masterstroke_id`` until he reveals them. This is the
    single source the
    server uses to decide what an event log may show and which steps an undo
    may take back, so every hidden zone and every private glimpse belongs
    here (``tests/unit/test_known_card_seats.py`` checks it against
    what each seat's view and choices show). It is knowledge of a card's
    place: a deck card below the public top stays known to nobody even
    though the play server
    shows the owner its deck's composition, sorted (OQ-010 ruling 5), and
    every seat each seat's deck pool (``PublicPlayerView.deck_pool``, card
    ids by identity only, OQ-010 ruling 6).
    """

    nobody: frozenset[int] = frozenset()
    known: dict[str, frozenset[int]] = {}
    for card_id in (
        *state.imperium_deck,
        *state.intrigue_deck,
        *state.contract_bank,
        *state.conflict_deck,
        *state.unused_conflict_ids,
        *state.twisted_deck_stock,
        *state.navigation_stock,
        *state.tleilaxu_deck,
        *state.skill_stack,
        # Arrakeen Scouts: the face-down cards missions put on the board
        # (CHOAM Research's Contracts, Emperor's Schemes' Intrigue cards) are
        # unknown to every seat until one takes them.
        *(card_id for _, _, card_id in state.scouts_goods_cards),
    ):
        known[card_id] = nobody
    for stack in state.tech_stacks:
        # Only the top tile of an Ixian Embassy stack is face up.
        for card_id in stack[1:]:
            known[card_id] = nobody
    for card_id in revealed_contract_ids(state):
        # Revealed from the bank to the whole table while the choice is open.
        known.pop(card_id, None)
    resolving = set(resolving_intrigue_ids(state))
    for player in state.players:
        owner = frozenset({player.player_id})
        for card_id in (*player.deck, *player.twisted_deck, *player.navigation_box):
            known[card_id] = nobody
        for card_id in player.navigation_slots:
            if card_id not in resolving:
                known[card_id] = owner
        public_hand = set(player.hand_public)
        for card_id in player.hand:
            if card_id not in public_hand:
                known[card_id] = owner
        for card_id in player.intrigue_cards:
            if card_id not in resolving:
                known[card_id] = owner
        if player.secret_project_tech_id:
            known[player.secret_project_tech_id] = owner
        if player.set_aside_card_id:
            # Ilesa Ecaz's One Step Ahead card, face down until it returns.
            known[player.set_aside_card_id] = owner
        for card_id in (
            # Imperium Ceremony's peek shows the deck's top cards to its owner.
            *peeked_intrigue_ids(state, player.player_id),
            peeked_card_id(state, player.player_id),
            *long_live_fighters_ids(state, player.player_id),
            *secret_project_candidate_ids(state, player.player_id),
        ):
            if card_id:
                known[card_id] = owner
        for card_id in player.deck_public_top:
            # Put on top face up for the whole table (OQ-145): the one deck
            # knowledge that wins over the owner's peeks above.
            known.pop(card_id, None)
    for player in state.players:
        for card_id in player.known_intrigue_ids:
            # Rise of Ix: an Intrigue card this seat knows in the deck or in
            # another seat's hand (rise-of-ix.md 13).
            seats = known.get(card_id)
            if seats is not None:
                known[card_id] = seats | {player.player_id}
    for event_round, _, seat, _ in state.scouts_secret_picks:
        # Arrakeen Scouts: a secret pick is its seat's alone until due. It
        # is no card, but the log redaction, the undo boundary and the
        # sweep's leak check all read this one registry, so the reveal step
        # is a reveal like any other.
        known[secret_pick_id(event_round, seat)] = frozenset({seat})
    for seat, _, _ in state.scouts_bids:
        # A sealed bid likewise, until the last seat confirms.
        known[secret_bid_id(state.round_number, seat)] = frozenset({seat})
    for player in state.players:
        # The Baron's two Factions are his alone until his deployment
        # reveals them (docs/rules/imperium-base.md 14).
        if player.masterstroke_factions and not player.masterstroke_revealed:
            known[masterstroke_id(player.player_id)] = frozenset({player.player_id})
    return known


@dataclass(frozen=True, slots=True)
class DisclosedPlayerZones:
    """One seat's hidden zones, laid open after the game has finished."""

    player: int
    hand: tuple[str, ...]
    deck: tuple[str, ...]
    intrigue_cards: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HiddenZoneDisclosure:
    """Every hidden zone of a state, for post-game review only.

    OQ-010 ruling 4 (project convention, not an official rule): once a game
    has finished, review may show everything — each seat's hand, deck order,
    and held Intrigue, plus the face-down deck and bank orders. The caller
    is responsible for only producing this after ``GamePhase.FINISHED`` of
    the game being reviewed; the state passed in may be any earlier state
    of that finished game.
    """

    players: tuple[DisclosedPlayerZones, ...]
    imperium_deck: tuple[str, ...]
    intrigue_deck: tuple[str, ...]
    contract_bank: tuple[str, ...]
    conflict_deck: tuple[str, ...]
    # Arrakeen Scouts: the face-down cards still on the board, and the
    # secret picks never revealed (event round, event id, seat, pick).
    scouts_board_cards: tuple[str, ...] = ()
    scouts_secret_picks: tuple[tuple[int, str, int, int], ...] = ()
    scouts_bids: tuple[tuple[int, int, bool], ...] = ()


def disclose_hidden_zones(state: GameState) -> HiddenZoneDisclosure:
    """Return every hidden zone of ``state`` for post-game review (OQ-010)."""

    return HiddenZoneDisclosure(
        players=tuple(
            DisclosedPlayerZones(
                player=player.player_id,
                hand=player.hand,
                deck=player.deck,
                intrigue_cards=player.intrigue_cards,
            )
            for player in state.players
        ),
        imperium_deck=state.imperium_deck,
        intrigue_deck=state.intrigue_deck,
        contract_bank=state.contract_bank,
        conflict_deck=state.conflict_deck,
        scouts_board_cards=tuple(card for _, _, card in state.scouts_goods_cards),
        scouts_secret_picks=state.scouts_secret_picks,
        scouts_bids=state.scouts_bids,
    )


def _board_card_counts(state: GameState) -> tuple[tuple[str, str, int], ...]:
    counts: dict[tuple[str, str], int] = {}
    for mission_id, location, _ in state.scouts_goods_cards:
        counts[(mission_id, location)] = counts.get((mission_id, location), 0) + 1
    return tuple(
        (mission, location, count) for (mission, location), count in counts.items()
    )


def observe_state(state: GameState, player: int) -> PlayerView:
    """Return a pure view that omits every hidden card ordering and opponent secret."""

    if not 0 <= player < state.config.players:
        raise ValueError("observer must identify a configured player")
    if len(state.players) != state.config.players:
        raise ValueError("cannot observe a state without every configured player")

    owner = state.players[player]
    decision_kind: str | None = None
    decision_owner: int | None = None
    turn_owner_value: int | None = None
    if state.decision_stack:
        frame = state.decision_stack[-1]
        decision_kind = str(frame.kind)
        if isinstance(frame.decision, PlayerDecision):
            decision_owner = frame.decision.owner
        context_owner = dict(frame.context).get("turn_owner")
        if isinstance(context_owner, int) and not isinstance(context_owner, bool):
            turn_owner_value = context_owner
    intrigue_top, intrigue_bottom, intrigue_held = known_intrigue_places(state, owner)
    return PlayerView(
        player=player,
        revision=state.revision,
        phase=state.phase,
        round_number=state.round_number,
        first_player=state.first_player,
        decision_kind=decision_kind,
        decision_owner=decision_owner,
        turn_owner=turn_owner_value,
        reveal_order=state.reveal_order,
        endgame_intrigue_complete=state.endgame_intrigue_complete,
        players=tuple(_public_view_of(state, seat) for seat in state.players),
        private=PrivatePlayerView(
            deck_size=len(owner.deck),
            hand=owner.hand,
            intrigue_cards=owner.intrigue_cards,
            peeked_card_id=peeked_card_id(state, player),
            peeked_intrigue_ids=peeked_intrigue_ids(state, player),
            agent_card_pick=agent_card_pick_of(state, player)[0],
            agent_card_pick_graft=agent_card_pick_of(state, player)[1],
            effect_pick=effect_pick_of(state, player),
            navigation_slots=owner.navigation_slots,
            secret_project_tech_id=owner.secret_project_tech_id,
            masterstroke_factions=owner.masterstroke_factions,
            set_aside_card_id=owner.set_aside_card_id,
            known_intrigue_top=intrigue_top,
            known_intrigue_bottom=intrigue_bottom,
            known_intrigue_held=intrigue_held,
            ix_pending=ix_pending_of(state, player),
            scouts_secret_picks=tuple(
                (event_round, event_id, pick)
                for event_round, event_id, seat, pick in state.scouts_secret_picks
                if seat == player
            ),
            scouts_bid=next(
                (amount for seat, amount, _ in state.scouts_bids if seat == player),
                -1,
            ),
        ),
        current_conflict_ids=state.current_conflict_ids,
        conflict_deck_size=len(state.conflict_deck),
        combat_intrigue_complete=state.combat_intrigue_complete,
        combat_rewards_resolved=state.combat_rewards_resolved,
        imperium_row=state.imperium_row,
        imperium_deck_size=len(state.imperium_deck),
        intrigue_deck_size=len(state.intrigue_deck),
        imperium_removed=state.imperium_removed,
        intrigue_resolving=resolving_intrigue_ids(state),
        intrigue_discard=state.intrigue_discard,
        contract_bank_size=len(state.contract_bank),
        face_up_contract_ids=state.face_up_contract_ids,
        sardaukar_contract_ids=state.sardaukar_contract_ids,
        contract_trash=state.contract_trash,
        revealed_contract_ids=revealed_contract_ids(state),
        leader_draft_pool=state.leader_draft_pool,
        reserve_stacks=state.reserve_stacks,
        shield_wall_present=state.shield_wall_present,
        conflict_first_place_influence_bonus=(
            state.conflict_first_place_influence_bonus
        ),
        maker_bonus_spice=state.maker_bonus_spice,
        sardaukar_commander_space_ids=state.sardaukar_commander_space_ids,
        sardaukar_commanders_bank=state.sardaukar_commanders_bank,
        skill_stack_size=len(state.skill_stack),
        skill_face_up=state.skill_face_up,
        skill_trash=state.skill_trash,
        tech_face_up=tuple(stack[0] if stack else "" for stack in state.tech_stacks),
        tech_stack_sizes=tuple(len(stack) for stack in state.tech_stacks),
        tech_trash=state.tech_trash,
        tleilaxu_row=state.tleilaxu_row,
        tleilaxu_deck_size=len(state.tleilaxu_deck),
        tleilaxu_track_spice=state.tleilaxu_track_spice,
        combat_intrigue_players=state.combat_intrigue_players,
        scouts_subcommittees=state.scouts_subcommittees,
        scouts_subcommittee_members=state.scouts_subcommittee_members,
        scouts_revealed=state.scouts_revealed,
        scouts_mission_rounds=state.scouts_mission_rounds,
        scouts_mid_auction_round=state.scouts_mid_auction_round,
        scouts_late_auction_round=state.scouts_late_auction_round,
        scouts_item=state.scouts_item,
        scouts_round_modifier=state.scouts_round_modifier,
        scouts_discount_used=state.scouts_discount_used,
        scouts_goods=state.scouts_goods,
        scouts_parked=state.scouts_parked,
        scouts_board_card_counts=_board_card_counts(state),
        scouts_secret_pending=tuple(
            (event_round, event_id, seat)
            for event_round, event_id, seat, _ in state.scouts_secret_picks
        ),
        scouts_secrets_round=state.scouts_secrets_round,
        scouts_bids_confirmed=tuple(
            seat for seat, _, confirmed in state.scouts_bids if confirmed
        ),
        scouts_market_cards=state.scouts_market_cards,
        scouts_calls=state.scouts_calls,
        epic_game=state.config.epic_game,
        base_game=state.config.base_game,
        mentat_owed_to=state.mentat_owed_to,
        rise_of_ix=state.config.rise_of_ix,
        dreadnought_control=state.dreadnought_control,
        agent_boxes=agent_box_cards(state),
    )


KnownIntriguePlaces = tuple[
    str, tuple[tuple[int, str], ...], tuple[tuple[int, str], ...]
]
_NO_KNOWN_INTRIGUE: Final[KnownIntriguePlaces] = ("", (), ())


def known_intrigue_places(state: GameState, owner: PlayerState) -> KnownIntriguePlaces:
    """The Intrigue cards ``owner`` knows (``known_intrigue_ids``) by place:
    the Intrigue deck's top card ("" when unknown), (depth from the deck's
    bottom, card) and (holding seat, card), sorted. A card in a public zone
    or in the owner's own hand is in none of them."""

    known = owner.known_intrigue_ids
    if not known:
        return _NO_KNOWN_INTRIGUE
    cards = frozenset(known)
    deck = state.intrigue_deck
    return (
        deck[0] if deck and deck[0] in cards else "",
        tuple(
            (depth, card) for depth, card in enumerate(reversed(deck)) if card in cards
        ),
        tuple(
            sorted(
                (seat.player_id, card)
                for seat in state.players
                if seat.player_id != owner.player_id
                for card in seat.intrigue_cards
                if card in cards
            )
        ),
    )


# The context keys of the open Rise of Ix decision's state (stage P4c writes
# them in the frame the seat decides; ``ix_pending_of`` reads them): the
# Shipping track spaces whose recall reward is still owed, as "1,3"; the open
# Acquire Tech's Tech Discount, its payment ("spice" or "solari") and the
# Negotiators the seat may still return toward it.
SHIPPING_REWARDS_KEY: Final = "shipping_rewards"
TECH_DISCOUNT_KEY: Final = "tech_discount"
TECH_PAYMENT_KEY: Final = "tech_payment"
NEGOTIATORS_RETURNABLE_KEY: Final = "negotiators_returnable"


def ix_negotiators_returnable(state: GameState, player: int, discount: int) -> int:
    """The most Negotiators ``player`` could still return toward an Acquire
    Tech at ``discount``: those it holds, but no more than the dearest
    face-up tile still costs ("any number" of them, each one spice off,
    [Rise of Ix p. 4]; one beyond the price lowers nothing). Read from the
    state each time: an acquisition stacked under another that spent
    Negotiators or took a tile must not show the count it opened with
    (Codex review of 82b2bf2e)."""

    prices = (
        max(TECH_TILES_BY_ID[stack[0]].cost - discount, 0)
        for stack in state.tech_stacks
        if stack
    )
    return min(state.players[player].negotiators, max(prices, default=0))


def ix_pending_of(state: GameState, player: int) -> IxPending:
    """The open Rise of Ix decision ``player`` is making (``IxPending``),
    from the context of its own top frame; ``NO_IX_PENDING`` otherwise, and
    always outside a Rise of Ix game. An open Ix Tech acquisition's
    returnable Negotiators are counted now (``ix_negotiators_returnable``),
    not taken from the context."""

    if not state.config.rise_of_ix or not state.decision_stack:
        return NO_IX_PENDING
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return NO_IX_PENDING
    context = dict(frame.context)
    rewards = context.get(SHIPPING_REWARDS_KEY)
    discount = context.get(TECH_DISCOUNT_KEY)
    payment = context.get(TECH_PAYMENT_KEY)
    returnable = (
        ix_negotiators_returnable(state, player, discount)
        if isinstance(discount, int)
        else 0
    )
    pending = IxPending(
        shipping_rewards=tuple(
            int(space) for space in rewards.split(",") if space
        )
        if isinstance(rewards, str)
        else (),
        tech_discount=discount if isinstance(discount, int) else 0,
        tech_payment=payment if isinstance(payment, str) else "",
        negotiators_returnable=returnable,
    )
    return NO_IX_PENDING if pending == NO_IX_PENDING else pending


# The turn frame's context keys of a picked Agent card (stage B1,
# ``rules.agent_turn``).
AGENT_CARD_PICK_KEY = "agent_card_pick"
AGENT_CARD_PICK_GRAFT_KEY = "agent_card_pick_graft"


def agent_card_pick_of(state: GameState, player: int) -> tuple[str, bool]:
    """The Agent card ``player`` picked and has not placed yet ("" if none),
    and whether it is grafted: it waits in the seat's own turn frame, on top
    until the space is picked."""

    if not state.decision_stack:
        return "", False
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return "", False
    context = dict(frame.context)
    card = context.get(AGENT_CARD_PICK_KEY)
    if not isinstance(card, str):
        return "", False
    return card, context.get(AGENT_CARD_PICK_GRAFT_KEY) is True


# The top frame's context key of the rows picked toward one waiting effect
# (stage B3, ``rules.effect_steps``).
EFFECT_PICK_KEY = "effect_pick"


# Long Live the Fighters' frame and the card to draw it keeps
# (``rules.agent_effects``).
_LONG_LIVE_FRAME: Final = "long_live_fighters"
_LONG_LIVE_DRAW_KEY: Final = "long_live_fighters_draw_card_id"


def effect_pick_of(
    state: GameState, player: int
) -> tuple[tuple[str, tuple[tuple[str, ActionValue], ...]], ...]:
    """The rows ``player`` picked toward one waiting effect and has not
    finished (() if none): they wait in the context of the seat's own frame,
    on top until the effect's last row. Long Live the Fighters picks its one
    effect's two cards in two decisions of its own frame, which keeps the
    card to draw: that card is the seat's first picked target (stage B3d-2a,
    the 2026-10-20 review)."""

    if not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    encoded = dict(frame.context).get(EFFECT_PICK_KEY)
    if not isinstance(encoded, str):
        drawn = dict(frame.context).get(_LONG_LIVE_DRAW_KEY)
        if str(frame.kind) == _LONG_LIVE_FRAME and isinstance(drawn, str):
            return (("choose_personal_card", (("card_id", drawn),)),)
        return ()
    rows: list[tuple[str, tuple[tuple[str, ActionValue], ...]]] = []
    for action_id, arguments in json.loads(encoded):
        rows.append(
            (str(action_id), tuple((str(name), value) for name, value in arguments))
        )
    return tuple(rows)


def peeked_card_id(state: GameState, player: int) -> str:
    """Return the deck card the owner may see: Controlled's peek, Glowglobes,
    or Paul Atreides' Prescience.

    Controlled shows the top card while its choice is up; Glowglobes lets
    the owner "look at the top card of your deck at any time" [Glowglobes
    Tech tile], as Prescience lets the original game's Paul Atreides: "자기
    덱 맨 위 카드를 언제든 볼 수 있다", never while the deck is empty (the
    discard pile is not shuffled for it) [DI p. 13] (docs/rules/
    imperium-base.md 12, 14).
    """

    owner = state.players[player]
    if owner.deck and (
        has_tech(owner.tech_ids, TechAbility.PEEK_TOP_CARD)
        or owner.leader_id == "paul_atreides"
    ):
        return owner.deck[0]
    if not state.decision_stack:
        return ""
    frame = state.decision_stack[-1]
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ""
    peeked = dict(frame.context).get("peeked_card_id")
    if not isinstance(peeked, str) or not peeked:
        return ""
    return peeked if owner.deck and owner.deck[0] == peeked else ""


def peeked_intrigue_ids(state: GameState, player: int) -> tuple[str, ...]:
    """Return the Intrigue deck cards the owner may see (Imperium Ceremony).

    The keep-one choice shows the deck's top two cards to its owner only;
    they are reported while they still sit on top of the deck.
    """

    if not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if str(frame.kind) != "intrigue_peek":
        return ()
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return ()
    value = dict(frame.context).get("peeked_intrigue_ids")
    if not isinstance(value, str) or not value:
        return ()
    peeked = tuple(value.split(","))
    return peeked if state.intrigue_deck[: len(peeked)] == peeked else ()


def long_live_fighters_ids(state: GameState, player: int) -> tuple[str, ...]:
    """Return the deck's top three cards while Long Live the Fighters picks.

    Its draw-then-discard choice names them to the owner only [Long Live the
    Fighters card]; they stay in the deck until the second pick.
    """

    frame = _own_top_frame(state, "long_live_fighters", player)
    return state.players[player].deck[:3] if frame is not None else ()


def secret_project_candidate_ids(state: GameState, player: int) -> tuple[str, ...]:
    """Return the bottom Tech tiles Kota Odax looks at for the Secret Project.

    "Game Start: Look at the bottom Tech tile of each stack" [Kota Odax of Ix
    card]: the choice shows them to the owner only.
    """

    frame = _own_top_frame(state, "tech_secret_project", player)
    if frame is None:
        return ()
    value = dict(frame.context).get("candidates")
    return tuple(value.split(",")) if isinstance(value, str) and value else ()


def revealed_contract_ids(state: GameState) -> tuple[str, ...]:
    """Return the bank Contracts an open Coercive Negotiation has revealed.

    "Reveal three contracts from the bank. Take one and trash the other
    two." [Coercive Negotiation card]: they stay on top of the bank while
    the owner chooses, and they are face up to the whole table -- a card is
    revealed "to your opponents" [Main p. 7], as a Conflict card is revealed
    and placed "face up" [Main p. 8]. All of them count, including one the
    owner cannot take (the Bloodlines Immediate without an Intrigue card to
    trash [Bloodlines p. 2]).
    """

    if not state.decision_stack:
        return ()
    frame = state.decision_stack[-1]
    if str(frame.kind) != "intrigue_trigger_contract":
        return ()
    card_id = dict(frame.context).get("card_id")
    entry = INTRIGUE_CARDS_BY_INSTANCE.get(str(card_id))
    counts = (
        reward.count
        for option in (entry.options if entry is not None else ())
        for section in option.sections
        for reward in section.rewards
        if isinstance(reward, RevealContractsTakeOne)
    )
    return state.contract_bank[: next(counts, 0)]


def _own_top_frame(state: GameState, kind: str, player: int) -> DecisionFrame | None:
    if not state.decision_stack:
        return None
    frame = state.decision_stack[-1]
    if str(frame.kind) != kind:
        return None
    if not isinstance(frame.decision, PlayerDecision) or frame.decision.owner != player:
        return None
    return frame


# One public view per ``PlayerState`` object. A seat's state is immutable and
# most seats do not change between two consecutive decisions, so the view
# built for a state object is reused while that object is alive; the entry
# keeps the object alive so its id cannot be recycled under it. Bounded so a
# long self-play run does not grow it (throughput report, section 7).
_PUBLIC_VIEW_CACHE: dict[int, tuple[PlayerState, PublicPlayerView]] = {}
_PUBLIC_VIEW_CACHE_LIMIT = 512


def _public_view_of(state: GameState, player: PlayerState) -> PublicPlayerView:
    """The seat's public view plus what the game state holds for it.

    The cache is keyed by the ``PlayerState`` object alone, so the owed
    Emperor track Spies (a ``GameState`` queue) are added on top of it.
    """

    view = _cached_public_player_view(player)
    owed = sum(1 for seat, _ in state.pending_track_spies if seat == player.player_id)
    return replace(view, track_spies_owed=owed) if owed else view


def _cached_public_player_view(player: PlayerState) -> PublicPlayerView:
    key = id(player)
    entry = _PUBLIC_VIEW_CACHE.get(key)
    if entry is not None and entry[0] is player:
        return entry[1]
    view = _public_player_view(player)
    if len(_PUBLIC_VIEW_CACHE) >= _PUBLIC_VIEW_CACHE_LIMIT:
        _PUBLIC_VIEW_CACHE.clear()
    _PUBLIC_VIEW_CACHE[key] = (player, view)
    return view


@cache
def _card_identity(instance_id: str) -> str:
    """A deck or hand card's card id. An id that names no personal card (the
    hand-made states of unit tests) reads ``unknown``: the pool never carries
    an instance id. A real card whose play data is not transcribed still
    raises, as every other zone's encoding would."""

    try:
        return personal_card_for_instance(instance_id).card.card_id
    except KeyError, ValueError:
        return "unknown"


def _deck_pool(player: PlayerState) -> tuple[str, ...]:
    # Ilesa Ecaz's face-down set-aside card stays in the pool: leaving it
    # out would tell every seat which card it is (plan 17.8 review item 1).
    public = set(player.hand_public)
    return tuple(
        sorted(
            _card_identity(card_id)
            for card_id in (
                *player.deck,
                *(card_id for card_id in player.hand if card_id not in public),
                *((player.set_aside_card_id,) if player.set_aside_card_id else ()),
            )
        )
    )


def _public_player_view(player: PlayerState) -> PublicPlayerView:
    return PublicPlayerView(
        player=player.player_id,
        leader_id=player.leader_id,
        leader_face_id=player.leader_face_id,
        victory_points=player.victory_points,
        resources=player.resources,
        influence=player.influence,
        hand_size=len(player.hand),
        deck_size=len(player.deck),
        intrigue_card_count=len(player.intrigue_cards),
        hand_public=player.hand_public,
        deck_pool=_deck_pool(player),
        agents_available=player.agents_available,
        agent_locations=player.agent_locations,
        swordmaster_acquired=player.swordmaster_acquired,
        troops_supply=player.troops_supply,
        troops_garrison=player.troops_garrison,
        troops_conflict=player.troops_conflict,
        memories=player.memories,
        sandworms_conflict=player.sandworms_conflict,
        spies_supply=player.spies_supply,
        spy_post_ids=player.spy_post_ids,
        alliance_faction_ids=player.alliance_faction_ids,
        control_space_ids=player.control_space_ids,
        combat_strength=player.combat_strength,
        has_revealed=player.has_revealed,
        high_council=player.high_council,
        maker_hooks=player.maker_hooks,
        feyd_track_space=player.feyd_track_space,
        commanders_supply=player.commanders_supply,
        commanders_garrison=player.commanders_garrison,
        commanders_conflict=player.commanders_conflict,
        skill_ids=player.skill_ids,
        commander_recruited_turn=player.commander_recruited_turn,
        contracts_completed_turn=player.contracts_completed_turn,
        held_contract_icons=player.held_contract_icons,
        # Troops owed to the Conflict (Suspensor Suits, OQ-042) wait like a
        # recruit shortfall; the encoding keeps one troop slot per seat.
        ungained_troops=player.ungained_troops + player.ungained_conflict_troops,
        ungained_specimens=player.ungained_specimens,
        commander_discount_turn=player.commander_discount_turn,
        ignores_influence_requirements_turn=player.ignores_influence_requirements_turn,
        granted_agent_icon_turn=player.granted_agent_icon_turn,
        combat_icon_turn=player.combat_icon_turn,
        bene_gesserit_boost_pending=player.bene_gesserit_boost_pending,
        tactics_track_space=player.tactics_track_space,
        agent_in_conflict=player.agent_in_conflict,
        twisted_deck_size=len(player.twisted_deck),
        navigation_remaining=len(player.navigation_slots),
        navigation_played=player.navigation_played,
        reveal_persuasion_bonus=player.reveal_persuasion_bonus,
        tech_ids=player.tech_ids,
        tech_flipped=player.tech_flipped,
        has_secret_project=bool(player.secret_project_tech_id),
        spies_boxed=player.spies_boxed,
        spies_recalled_turn=player.spies_recalled_turn,
        research_space=player.research_space,
        tleilaxu_space=player.tleilaxu_space,
        specimens=player.specimens,
        family_atomics=player.family_atomics,
        reveal_persuasion_round_bonus=player.reveal_persuasion_round_bonus,
        chairdog_return_card_ids=player.chairdog_return_card_ids,
        usurped_row_card_id=player.usurped_row_card_id,
        in_play=player.in_play,
        discard_pile=player.discard_pile,
        trashed=player.trashed,
        intrigue_faceup=player.intrigue_faceup,
        imperium_set_aside=player.imperium_set_aside,
        objective_ids=player.objective_ids,
        won_conflict_ids=player.won_conflict_ids,
        face_down_battle_card_ids=player.face_down_battle_card_ids,
        active_contract_ids=player.active_contract_ids,
        completed_contract_ids=player.completed_contract_ids,
        mentat=player.mentat,
        masterstroke_secret=bool(player.masterstroke_factions)
        and not player.masterstroke_revealed,
        masterstroke_revealed_factions=(
            player.masterstroke_factions if player.masterstroke_revealed else ()
        ),
        deck_public_top=player.deck_public_top,
        voice_blocked_space_ids=player.voice_blocked_space_ids,
        enemy_agents_ignored_turn=player.enemy_agents_ignored_turn,
        acquire_to_deck_top_round=player.acquire_to_deck_top_round,
        dreadnoughts_supply=player.dreadnoughts_supply,
        dreadnoughts_garrison=player.dreadnoughts_garrison,
        dreadnoughts_conflict=player.dreadnoughts_conflict,
        freighter_space=player.freighter_space,
        negotiators=player.negotiators,
        snooper_faction_ids=player.snooper_faction_ids,
        has_set_aside_card=bool(player.set_aside_card_id),
        set_aside_returned_turn=player.set_aside_returned_turn,
        turns_finished_round=player.turns_finished_round,
    )
