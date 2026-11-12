"""Sample a full game state consistent with one seat's knowledge.

A search agent may only reason from what its seat can see [Main p. 7]:
its own hand and held Intrigue, every public zone, and the *sizes* of the
hidden zones. ``determinize`` keeps everything the observer knows and
re-deals every hidden card ordering with the supplied RNG — the observer's
deck order, each opponent's secret hand cards together with their deck, the
opponents' held Intrigue together with the Intrigue deck, the Imperium deck,
the Contract bank, and the Conflict deck together with the boxed Conflict
cards of each tier — so the result is one plausible world the observer
cannot distinguish from the real one. What Rise of Ix lets a seat know stays
put (docs/rules/rise-of-ix.md 13): the Intrigue cards the observer knows
(``PlayerState.known_intrigue_ids``) keep their place in the deck or in
another seat's hand, and an opponent's face-down set-aside card (Ilesa Ecaz)
is dealt from the same pool as its hidden hand and deck. The observer's own
``observe_state`` view of the sampled state equals its view of the real
state, which the tests pin.

Bloodlines' standing secrets of another seat are re-dealt too: Steersman
Y'rkoon's face-down Navigation slots with every Navigation box and the
stock (only he may look at his slots [Bloodlines p. 12]), Kota Odax's
face-down Secret Project tile with every Tech tile below a stack's face-up
top, and which Twisted Intrigue cards have left Piter De Vries' face-down
Twisted deck (the held ones with the Twisted decks and the stock). The
observer keeps its own slots, its own Secret Project tile and its own held
Twisted cards; Piter's own Twisted deck keeps its cards, which he can
count, in a new order. The orders no seat sees are dealt again as well:
the Tleilaxu deck, the Skill stack, every Twisted deck, and which stack
each face-down Tech tile lies in (the tiles are shuffled face down into
the three stacks [Bloodlines p. 6; Rise of Ix p. 3]); only the bottom tiles the
observer is looking at for its Secret Project stay put. Every pool is
sorted before its shuffle and taken in a fixed order, so a sampled world
is a function of what the observer knows and ``rng`` alone: two states the
observer cannot tell apart give the same world (2026-11-08; before, the
search seats' playouts knew the real slots, tile, drawn Twisted cards and
these orders).

With no observer (``observer`` None) the world is one a spectator cannot
tell from the real one: every seat is re-dealt as an opponent is, nothing
anyone peeked at stays put, what a seat knows of another's cards (OQ-149)
is forgotten, and the standing secrets above are re-dealt for every seat.
Every pool is sorted before its shuffle and taken in a fixed order, so
the world is a function of the public information and ``rng`` alone; two
states that differ only in what no seat shows the table give the same
world's views. The open frames stay as they are, so a frame that records
its owner's private pick (an Agent card picked and not placed yet, rows
picked toward an effect, a peeked card) still shows it to its owner: a
caller that needs a world the whole table may see refuses such a state
(``evaluation.win_odds.private_choice_open``).
The win odds read every seat's value from such worlds
(``evaluation.win_odds``). The orders no seat's view shows (the Tleilaxu
deck, the Skill stack, the Twisted decks without a held Twisted card, the
Tech stacks' membership) keep theirs there: the win odds read views only
and play nothing out.
"""

import random
from dataclasses import replace

from dune_imperium.content.core.icons import ConflictTier, Faction
from dune_imperium.content.registry.conflicts import CONFLICTS_BY_ID
from dune_imperium.content.registry.contracts import contract_for_instance
from dune_imperium.content.registry.intrigue import is_twisted_intrigue
from dune_imperium.core.decisions import DecisionFrame, PlayerDecision
from dune_imperium.core.observation import (
    peeked_card_id,
    peeked_intrigue_ids,
    resolving_intrigue_ids,
    revealed_contract_ids,
)
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import (
    FrameKind,
    frame_context,
    owned_top_frame,
    with_context,
)
from dune_imperium.rules.scouts_auctions import bid_cap
from dune_imperium.rules.scouts_secrets import pick_alternatives, pick_names_faction

# The Factions a redealt secret pick may name (the original game's Covert
# Operation).
_FACTION_VALUES: tuple[str, ...] = tuple(faction.value for faction in Faction)


def secret_project_candidates(state: GameState, observer: int) -> tuple[str, ...]:
    """Return the bottom Tech tiles ``observer`` is choosing between.

    Empty unless a Secret Project frame owned by ``observer`` is open, on
    top or below another pick (with Rise of Ix and the CHOAM Module every
    seat's starting Contract pick sits above it at setup).
    """

    return tuple(
        tile
        for frame in state.decision_stack
        if frame.kind == FrameKind.TECH_SECRET_PROJECT
        and _frame_owner(frame) == observer
        for tile in _context_cards(frame, "candidates")
    )


def _frame_owner(frame: DecisionFrame) -> int | None:
    return frame.decision.owner if isinstance(frame.decision, PlayerDecision) else None


def _context_cards(frame: DecisionFrame, key: str) -> tuple[str, ...]:
    """The comma-separated card or tile ids a frame's context holds."""

    value = dict(frame.context).get(key)
    if not isinstance(value, str):
        return ()
    return tuple(card for card in value.split(",") if card)


def _rewritten(frame: DecisionFrame, key: str, cards: tuple[str, ...]) -> DecisionFrame:
    return with_context(frame, {**frame_context(frame), key: ",".join(cards)})


def known_top_card_count(state: GameState, observer: int) -> int:
    """Return how many of the observer's own top deck cards the observer has seen.

    Long Live the Fighters shows the owner the top three cards while its pick
    is open [Long Live the Fighters card]; Controlled's peek and Glowglobes
    show the top one. A sampled world must keep those cards where the open
    frame says they are, or the frame's own choices become unappliable
    (2026-09-16 baseline, rollout seat, base game seed 1).
    """

    if owned_top_frame(state, FrameKind.LONG_LIVE_FIGHTERS, observer) is not None:
        return 3
    return 1 if peeked_card_id(state, observer) else 0


def _keep_twisted_in_hands(
    pool: list[str], start: int, size: int, rng: random.Random
) -> None:
    """Move every Twisted card of a shuffled pool into the opponents' hands.

    Twisted Intrigue cards never join the shared deck (OQ-097, user ruling
    2026-10-04, "다른 사람이 twisted 카드를 뽑는 일은 없도록"), and the
    board's Scouts cards come off that deck, so a hidden Twisted card is in
    an opponent's hand: one the shuffle dealt to the deck or the board
    trades places with a random other card of the hand slots
    ``pool[start:start + size]``. Without a misplaced Twisted card no random
    number is drawn, so games without Piter De Vries sample as before.
    """

    hand = range(start, start + size)
    for index, card in enumerate(pool):
        if index in hand or not is_twisted_intrigue(card):
            continue
        slots = [slot for slot in hand if not is_twisted_intrigue(pool[slot])]
        if not slots:
            return
        slot = rng.choice(slots)
        pool[index], pool[slot] = pool[slot], card


def _redeal_conflicts(
    state: GameState, rng: random.Random
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Re-deal the Conflict deck within each tier, the boxed cards included.

    The deck is built by back -- "Conflict 카드를 I, II, III 뒷면별로 나눈다",
    and the finished deck is "위에서부터 I 1장, II 5장, III 4장" [Main p. 4] --
    so the tier at each depth is public and stays put. Which card of that
    tier lies there is not, and the unused I and II cards go to the box
    "앞면을 보지 않고" [Main p. 4], so no seat knows which cards of a tier
    were boxed either: the deck's and the box's cards of one tier are one
    hidden pool (the observation-leak sweep's
    ``simulation.invariants._scramble_conflicts`` treats them the same way).
    A tier with no boxed card (Epic Game Mode's Conflict III, every card of
    which is in the deck [Rise of Ix p. 10]) only changes its order.
    The tiers are shuffled in their own order and each pool is sorted
    first: the order the tiers are met in follows the boxed cards once the
    deck holds one tier only, and the boxed order is hidden (Codex review
    2026-11-08).
    """

    pools: dict[ConflictTier, list[str]] = {}
    for conflict_id in (*state.conflict_deck, *state.unused_conflict_ids):
        pools.setdefault(CONFLICTS_BY_ID[conflict_id].tier, []).append(conflict_id)
    for tier in sorted(pools):
        pool = pools[tier]
        pool.sort()
        rng.shuffle(pool)
    deck = tuple(
        pools[CONFLICTS_BY_ID[conflict_id].tier].pop()
        for conflict_id in state.conflict_deck
    )
    unused = tuple(sorted(card for pool in pools.values() for card in pool))
    return deck, unused


def _intrigue_deck(
    deck: tuple[str, ...],
    peeked: int,
    known: frozenset[str],
    dealt: list[str],
) -> tuple[str, ...]:
    """The sampled Intrigue deck: its first ``peeked`` cards and the cards the
    observer knows where they are, every other place from ``dealt`` in
    order."""

    if not known:
        return (*deck[:peeked], *dealt)
    rest = iter(dealt)
    return tuple(
        card if index < peeked or card in known else next(rest)
        for index, card in enumerate(deck)
    )


def determinize(
    state: GameState, observer: int | None, rng: random.Random
) -> GameState:
    """Return ``state`` with every zone hidden from ``observer`` re-dealt.

    ``observer`` None re-deals what is hidden from a spectator (module
    docstring).
    """

    public = observer is None
    if observer is not None and not 0 <= observer < state.config.players:
        raise ValueError("observer must identify a configured player")
    resolving = frozenset(resolving_intrigue_ids(state))
    players = list(state.players)
    # Imperium Ceremony's peek keeps the deck's top cards in place, and so do
    # the Intrigue cards the observer knows (Rise of Ix): in the deck, at
    # their depth, and in another seat's hand. A spectator knows neither.
    peeked_intrigue: tuple[str, ...] = (
        () if observer is None else peeked_intrigue_ids(state, observer)
    )
    known_intrigue: frozenset[str] = (
        frozenset()
        if observer is None
        else frozenset(state.players[observer].known_intrigue_ids)
    )
    intrigue_pool: list[str] = [
        card
        for card in state.intrigue_deck[len(peeked_intrigue) :]
        if card not in known_intrigue
    ]

    for seat, player in enumerate(players):
        if seat == observer:
            # Glowglobes, Controlled's peek and an open Long Live the Fighters
            # pick show the observer the top card(s), and cards put face up
            # on top of the deck are known to every seat (OQ-145): they stay
            # in place.
            top = list(
                player.deck[
                    : max(
                        len(player.deck_public_top),
                        known_top_card_count(state, seat),
                    )
                ]
            )
            own_deck = sorted(player.deck[len(top) :])
            rng.shuffle(own_deck)
            players[seat] = replace(player, deck=(*top, *own_deck))
            continue
        # Hand cards that entered the hand publicly stay known (OQ-010) and
        # so do the deck's public top cards (OQ-145); the face-down draws and
        # the rest of the deck are one unknown pool.
        known = frozenset(player.hand_public)
        secret_hand = [card for card in player.hand if card not in known]
        public_top = player.deck_public_top
        pool = [*secret_hand, *player.deck[len(public_top) :]]
        # Rise of Ix: Ilesa Ecaz's face-down card came from that hidden hand.
        # Only a seat with one changes its pool, so no other game's sampling
        # moves.
        set_aside = player.set_aside_card_id
        if set_aside:
            pool.append(set_aside)
        pool.sort()
        rng.shuffle(pool)
        hand = (*player.hand_public, *pool[: len(secret_hand)])
        if set_aside:
            set_aside = pool.pop()
        deck = (*public_top, *pool[len(secret_hand) :])
        # A played Intrigue is public while its choices resolve; the rest of
        # an opponent's hand is indistinguishable from the deck, but for the
        # cards the observer knows it holds.
        intrigue_pool.extend(
            card
            for card in player.intrigue_cards
            if card not in resolving and card not in known_intrigue
        )
        players[seat] = replace(
            player, hand=hand, deck=deck, set_aside_card_id=set_aside
        )
        if player.masterstroke_factions and not player.masterstroke_revealed:
            # The original game's Baron: his unrevealed Masterstroke Factions
            # are his alone (docs/rules/imperium-base.md 14). Only such a seat
            # draws, so no other game's sampling moves.
            players[seat] = replace(
                players[seat],
                masterstroke_factions=tuple(
                    rng.sample(
                        [faction.value for faction in Faction],
                        len(player.masterstroke_factions),
                    )
                ),
            )

    # Arrakeen Scouts: the board's face-down cards are unknown to every seat,
    # so they are dealt from the same pools as the deck and the bank.
    board_intrigue = [
        row for row in state.scouts_goods_cards if row[2].startswith("intrigue")
    ]
    intrigue_pool.extend(row[2] for row in board_intrigue)
    twisted_stock = _redeal_twisted(
        players, intrigue_pool, state.twisted_deck_stock, rng, observer=observer
    )
    intrigue_pool.sort()
    rng.shuffle(intrigue_pool)
    hidden_held = sum(
        1
        for seat, player in enumerate(state.players)
        if seat != observer
        for card in player.intrigue_cards
        if card not in resolving and card not in known_intrigue
    )
    _keep_twisted_in_hands(intrigue_pool, len(board_intrigue), hidden_held, rng)
    board_cards = {
        row: intrigue_pool[index] for index, row in enumerate(board_intrigue)
    }
    cursor = len(board_intrigue)
    # Rise of Ix: another seat knows a card by its place (a deck depth, a
    # seat's hand), not by the identity the observer cannot see, so in the
    # sampled world it knows the card dealt to that place: which card now
    # stands in each re-dealt card's place. Only a game where another seat
    # knows one builds it.
    # A spectator does not know which card another seat knows, nor where
    # in a hand or the deck it lies (their order is hidden too): its worlds
    # forget the knowledge instead of carrying it to a card (below).
    remap = not public and any(
        player.known_intrigue_ids
        for seat, player in enumerate(state.players)
        if seat != observer
    )
    redealt: dict[str, str] = (
        {row[2]: card for row, card in board_cards.items()} if remap else {}
    )
    # A hand's order is hidden, so the cards another seat knows in it take
    # its first dealt cards, seat by seat in each seat's order of knowledge.
    known_elsewhere = tuple(
        dict.fromkeys(
            card
            for seat, player in enumerate(state.players)
            if seat != observer
            for card in player.known_intrigue_ids
        )
    )
    for seat, player in enumerate(players):
        if seat == observer:
            continue
        original = state.players[seat].intrigue_cards
        kept = tuple(
            card for card in original if card in resolving or card in known_intrigue
        )
        held = len(original) - len(kept)
        dealt = intrigue_pool[cursor : cursor + held]
        players[seat] = replace(player, intrigue_cards=(*kept, *dealt))
        if remap:
            redealt.update(
                zip(
                    (
                        card
                        for card in known_elsewhere
                        if card in original and card not in kept
                    ),
                    dealt,
                    strict=False,
                )
            )
        cursor += held
    intrigue_deck = _intrigue_deck(
        state.intrigue_deck,
        len(peeked_intrigue),
        known_intrigue,
        intrigue_pool[cursor:],
    )
    if remap:
        redealt.update(zip(state.intrigue_deck, intrigue_deck, strict=True))
    for seat, player in enumerate(players):
        if seat == observer or not player.known_intrigue_ids:
            continue
        players[seat] = replace(
            player,
            known_intrigue_ids=()
            if public
            else tuple(redealt.get(card, card) for card in player.known_intrigue_ids),
        )

    imperium_deck = sorted(state.imperium_deck)
    rng.shuffle(imperium_deck)
    # Coercive Negotiation reveals the bank's top Contracts to every seat
    # while its choice is open [card face; Main p. 7]; they stay in place, or
    # the frame's own choices become unappliable in the sampled world
    # (2026-09-16 rollout cells, CHOAM+Bloodlines+Tech, 16 of 200 games).
    revealed = list(revealed_contract_ids(state))
    board_contracts = [
        row for row in state.scouts_goods_cards if row[2].startswith("contract:")
    ]
    contract_bank = [
        *state.contract_bank[len(revealed) :],
        *(row[2] for row in board_contracts),
    ]
    contract_bank.sort()
    rng.shuffle(contract_bank)
    for row in board_contracts:
        # CHOAM Research never places Bloodlines' Immediate (OQ-090), so a
        # board row takes the last other Contract of the shuffle.
        index = max(
            position
            for position, card in enumerate(contract_bank)
            if not contract_for_instance(card).requires_intrigue_trash
        )
        board_cards[row] = contract_bank.pop(index)
    contract_bank = [*revealed, *contract_bank]
    conflict_deck, unused_conflicts = _redeal_conflicts(state, rng)
    tleilaxu_deck = state.tleilaxu_deck
    skill_stack = state.skill_stack
    if observer is None:
        # Below each face-up top the Tech stacks are face down [Bloodlines
        # p. 6]; no view reads which stack a tile is in.
        tech_stacks: list[tuple[str, ...]] = []
        for stack in state.tech_stacks:
            below = sorted(stack[1:])
            rng.shuffle(below)
            tech_stacks.append((*stack[:1], *below))
        tech_stacks = _redeal_secret_projects(players, tech_stacks, rng)
        navigation_stock, _ = _redeal_navigation(players, state.navigation_stock, rng)
        decision_stack = state.decision_stack
    else:
        # The Tech tiles are shuffled face down into the three stacks
        # [Bloodlines p. 6; Rise of Ix p. 3], so the tiles below the tops are
        # one pool with another seat's Secret Project. Kota Odax's own pick is
        # the exception while its frame is open: "Game Start: 각 stack의 맨
        # 아래 Tech tile을 본다" [Bloodlines p. 6], so that seat knows the
        # bottom tiles it is choosing between and they must stay where the
        # frame's recorded candidates say they are. Shuffling them out of the
        # bottom would leave the sampled world inconsistent with the frame,
        # and applying the choice would then leave the tile both on a stack
        # and on the Leader card. The knowledge is not carried past the
        # frame: OQ-041 keeps the two unchosen identities out of the
        # observation. Another seat's open pick names the bottoms it sees,
        # which are as hidden as the tiles: it names the world's bottoms.
        tech_stacks = _redeal_secret_projects(
            players,
            list(state.tech_stacks),
            rng,
            observer=observer,
            kept=frozenset(secret_project_candidates(state, observer)),
        )
        # Another seat's open Navigation setup pick shows it five cards
        # (``rules.navigation``), as hidden as its slots.
        setups = [
            index
            for index, frame in enumerate(state.decision_stack)
            if frame.kind == FrameKind.NAVIGATION_SETUP
            and _frame_owner(frame) != observer
        ]
        navigation_stock, hands = _redeal_navigation(
            players,
            state.navigation_stock,
            rng,
            observer=observer,
            playing=resolving,
            hands=tuple(
                _context_cards(state.decision_stack[index], "hand") for index in setups
            ),
        )
        frames = list(state.decision_stack)
        for index, hand in zip(setups, hands, strict=True):
            frames[index] = _rewritten(frames[index], "hand", hand)
        for index, frame in enumerate(frames):
            owner = _frame_owner(frame)
            if owner is None or owner == observer:
                continue
            if frame.kind == FrameKind.TECH_SECRET_PROJECT:
                frames[index] = _rewritten(
                    frame,
                    "candidates",
                    tuple(stack[-1] for stack in tech_stacks if stack),
                )
            elif frame.kind == FrameKind.NAVIGATION_CHOICE:
                # Another seat's next Navigation card, before it is played
                # (``rules.navigation.begin_navigation_play``): the card now
                # in its first slot.
                slots = players[owner].navigation_slots
                frames[index] = _rewritten(frame, "card_id", slots[:1])
        decision_stack = tuple(frames)
        # The Tleilaxu deck [Immortality p. 4] and the Skill stack
        # [Bloodlines p. 3] are face down to every seat and only ever
        # drawn from the top.
        shuffled = sorted(tleilaxu_deck)
        rng.shuffle(shuffled)
        tleilaxu_deck = tuple(shuffled)
        shuffled = sorted(skill_stack)
        rng.shuffle(shuffled)
        skill_stack = tuple(shuffled)
    # Uprising with Rise of Ix and the CHOAM Module: the box and the other
    # seats' two Rise of Ix tiles are one pool unknown to the observer [Main
    # p. 16] -- before the deal (during the Leader draft every tile is in
    # the box, and its order is the deal to come), while the seats choose,
    # and after (the unchosen ones are back face down). Each other seat is
    # dealt its two again and, if it has chosen, its sealed choice is
    # either. The pool is sorted before the shuffle, so the sample does not
    # depend on the hidden order. Only such a game draws, so no other
    # game's sampling moves.
    holders = [
        index
        for index, holder in enumerate(players)
        if index != observer and holder.starting_contract_ids
    ]
    if state.contract_box or holders:
        box = sorted(
            (
                *state.contract_box,
                *(
                    card
                    for index in holders
                    for card in players[index].starting_contract_ids
                ),
            )
        )
        rng.shuffle(box)
        for index in holders:
            holder = players[index]
            given = tuple(box[: len(holder.starting_contract_ids)])
            del box[: len(holder.starting_contract_ids)]
            players[index] = replace(
                holder,
                starting_contract_ids=given,
                starting_contract_pick=(
                    rng.choice(given) if holder.starting_contract_pick else ""
                ),
            )
        contract_box = tuple(box)
    else:
        contract_box = state.contract_box
    # Arrakeen Scouts: another seat's secret pick is any line it could still
    # be (``pick_alternatives``), and a line that names a Faction any Faction
    # (the original game's Covert Operation); the observer's own stay. No
    # draw without a pick, and a Faction only for a line that names one, so
    # games without them consume the same random numbers.
    named = {(row[0], row[1]): row[2] for row in state.scouts_secret_factions}
    picks: list[tuple[int, str, int, int]] = []
    factions: list[tuple[int, int, str]] = []
    for pick_row in state.scouts_secret_picks:
        event_round, event_id, seat, pick = pick_row
        faction = named.get((event_round, seat))
        if seat != observer:
            pick = rng.choice(pick_alternatives(state, pick_row))
            faction = (
                rng.choice(_FACTION_VALUES)
                if pick_names_faction(event_id, pick)
                else None
            )
        picks.append((event_round, event_id, seat, pick))
        if faction is not None:
            factions.append((event_round, seat, faction))
    secret_picks = tuple(picks)
    # An opponent's sealed bid is any amount it could have bid (``bid_cap``
    # reads only public counts: currency, and Mercenaries' troops, OQ-074).
    bids = tuple(
        (seat, rng.randint(0, bid_cap(state, seat)), confirmed)
        if seat != observer
        else (seat, amount, confirmed)
        for seat, amount, confirmed in state.scouts_bids
    )
    return replace(
        state,
        players=tuple(players),
        scouts_secret_picks=secret_picks,
        scouts_secret_factions=tuple(factions),
        scouts_bids=bids,
        scouts_goods_cards=tuple(
            (row[0], row[1], board_cards.get(row, row[2]))
            for row in state.scouts_goods_cards
        ),
        intrigue_deck=intrigue_deck,
        imperium_deck=tuple(imperium_deck),
        contract_bank=tuple(contract_bank),
        contract_box=contract_box,
        conflict_deck=conflict_deck,
        unused_conflict_ids=unused_conflicts,
        tech_stacks=tuple(tech_stacks),
        navigation_stock=navigation_stock,
        decision_stack=decision_stack,
        twisted_deck_stock=twisted_stock,
        tleilaxu_deck=tleilaxu_deck,
        skill_stack=skill_stack,
    )


def _redeal_twisted(
    players: list[PlayerState],
    intrigue_pool: list[str],
    stock: tuple[str, ...],
    rng: random.Random,
    *,
    observer: int | None = None,
) -> tuple[str, ...]:
    """Deal again which Twisted Intrigue cards have left the Twisted decks.

    Piter De Vries' Twisted deck is face down and only its size is public
    [Piter De Vries card], so which of its cards were drawn into hands is
    hidden: the held Twisted cards in ``intrigue_pool`` (the hidden held
    cards of every seat but the observer), every other seat's Twisted deck
    and the undealt stock are one pool. ``intrigue_pool`` gets the held
    ones' new identities (changed in place), the decks keep their sizes
    (``players`` changed in place), and the stock comes back with its share.

    Piter himself (``observer``) knows which Twisted cards he holds, has
    played and has given away, so he can count the cards left in his deck:
    it keeps them in a new order. With no observer and no held Twisted card
    nothing is drawn (no spectator view reads the orders).
    """

    held = [card for card in intrigue_pool if is_twisted_intrigue(card)]
    if not held and observer is None:
        return stock
    pool = sorted(
        (
            *held,
            *(
                card
                for seat, player in enumerate(players)
                if seat != observer
                for card in player.twisted_deck
            ),
            *stock,
        )
    )
    rng.shuffle(pool)
    intrigue_pool[:] = [
        *(card for card in intrigue_pool if not is_twisted_intrigue(card)),
        *pool[: len(held)],
    ]
    cursor = len(held)
    for seat, player in enumerate(players):
        if seat == observer:
            own = sorted(player.twisted_deck)
            rng.shuffle(own)
            players[seat] = replace(player, twisted_deck=tuple(own))
            continue
        size = len(player.twisted_deck)
        players[seat] = replace(
            player, twisted_deck=tuple(pool[cursor : cursor + size])
        )
        cursor += size
    return tuple(pool[cursor:])


def _redeal_secret_projects(
    players: list[PlayerState],
    stacks: list[tuple[str, ...]],
    rng: random.Random,
    *,
    observer: int | None = None,
    kept: frozenset[str] = frozenset(),
) -> list[tuple[str, ...]]:
    """Deal each Secret Project tile again from every face-down Tech tile.

    Kota Odax's Secret Project lies face down on his Leader card [Kota Odax
    of Ix card]; to the table it is any of the tiles nobody sees, which are
    those below each stack's face-up top [Bloodlines p. 6]. ``players`` is
    changed in place; the stacks come back with the tiles left over, in the
    places the face-down tiles were. The observer's own tile stays, and so
    does a stack's bottom tile in ``kept`` (the ones its open Secret
    Project pick shows it). With no observer and no Secret Project nothing
    is drawn: no view reads which stack a tile below a top is in. A seat's
    playouts do: the next tile of a stack is revealed when its top is
    acquired [Bloodlines p. 7].
    """

    holders = [
        seat
        for seat, player in enumerate(players)
        if seat != observer and player.secret_project_tech_id
    ]
    if not holders and observer is None:
        return stacks
    places = [
        (index, depth)
        for index, stack in enumerate(stacks)
        for depth in range(1, len(stack))
        if depth < len(stack) - 1 or stack[depth] not in kept
    ]
    pool = sorted(
        (
            *(players[seat].secret_project_tech_id for seat in holders),
            *(stacks[index][depth] for index, depth in places),
        )
    )
    rng.shuffle(pool)
    dealt = iter(pool)
    for seat in holders:
        players[seat] = replace(players[seat], secret_project_tech_id=next(dealt))
    rebuilt = [list(stack) for stack in stacks]
    for index, depth in places:
        rebuilt[index][depth] = next(dealt)
    return [tuple(stack) for stack in rebuilt]


def _redeal_navigation(
    players: list[PlayerState],
    stock: tuple[str, ...],
    rng: random.Random,
    *,
    observer: int | None = None,
    playing: frozenset[str] = frozenset(),
    hands: tuple[tuple[str, ...], ...] = (),
) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """Deal Steersman Y'rkoon's face-down Navigation slots again.

    Only he may look at them [Bloodlines p. 12]; the cards he did not slot
    went to the box face down (``rules.navigation``), so to the table each
    slot holds any Navigation card not yet played: the slots, the box and
    any stock are one pool, and so are ``hands``, the five cards an open
    setup pick of his shows him (``NAVIGATION_SETUP``). The observer's own
    slots stay, and its own box only changes order (the stock is empty once
    his cards are dealt). A card in ``playing`` stays in its slot: it is
    face up while it resolves and leaves the slot when it is done.
    ``players`` is changed in place and keeps every zone's size; the stock
    and the hands come back with their shares. With no observer and no
    slotted card nothing is drawn.
    """

    slotted = [
        seat
        for seat, player in enumerate(players)
        if seat != observer and player.navigation_slots
    ]
    if not slotted and observer is None:
        return stock, hands
    pool = sorted(
        (
            *(
                card
                for seat, player in enumerate(players)
                if seat != observer
                for card in player.navigation_slots
                if card not in playing
            ),
            *(card for player in players for card in player.navigation_box),
            *(card for hand in hands for card in hand),
            *stock,
        )
    )
    rng.shuffle(pool)
    dealt = iter(pool)
    for seat, player in enumerate(players):
        slots = (
            tuple(
                card if card in playing else next(dealt)
                for card in player.navigation_slots
            )
            if seat != observer
            else player.navigation_slots
        )
        players[seat] = replace(
            player,
            navigation_slots=slots,
            navigation_box=tuple(next(dealt) for _ in player.navigation_box),
        )
    new_hands = tuple(tuple(next(dealt) for _ in hand) for hand in hands)
    return tuple(dealt), new_hands
