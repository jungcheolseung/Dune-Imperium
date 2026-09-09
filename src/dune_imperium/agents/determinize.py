"""Sample a full game state consistent with one seat's knowledge.

A search agent may only reason from what its seat can see [Main p. 7]:
its own hand and held Intrigue, every public zone, and the *sizes* of the
hidden zones. ``determinize`` keeps everything the observer knows and
re-deals every hidden card ordering with the supplied RNG — the observer's
deck order, each opponent's secret hand cards together with their deck, the
opponents' held Intrigue together with the Intrigue deck, the Imperium deck,
the Contract bank, and the Conflict deck — so the result is one plausible
world the observer cannot distinguish from the real one. The observer's own
``observe_state`` view of the sampled state equals its view of the real
state, which the tests pin.
"""

import random
from dataclasses import replace

from dune_imperium.core.observation import (
    peeked_card_id,
    peeked_intrigue_ids,
    resolving_intrigue_ids,
)
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import FrameKind, owned_top_frame


def secret_project_candidates(state: GameState, observer: int) -> tuple[str, ...]:
    """Return the bottom Tech tiles ``observer`` is currently choosing between.

    Empty unless a Secret Project frame owned by ``observer`` is open.
    """

    frame = owned_top_frame(state, FrameKind.TECH_SECRET_PROJECT, observer)
    if frame is None:
        return ()
    candidates = dict(frame.context).get("candidates")
    if not isinstance(candidates, str):
        return ()
    return tuple(tech_id for tech_id in candidates.split(",") if tech_id)


def determinize(state: GameState, observer: int, rng: random.Random) -> GameState:
    """Return ``state`` with every zone hidden from ``observer`` re-dealt."""

    if not 0 <= observer < state.config.players:
        raise ValueError("observer must identify a configured player")
    resolving = frozenset(resolving_intrigue_ids(state))
    players = list(state.players)
    # Imperium Ceremony's peek keeps the deck's top cards in place.
    peeked_intrigue = peeked_intrigue_ids(state, observer)
    intrigue_pool: list[str] = list(state.intrigue_deck[len(peeked_intrigue) :])

    for seat, player in enumerate(players):
        if seat == observer:
            # Glowglobes (and Controlled's peek) show the observer the top
            # card, which therefore stays in place.
            known_top = peeked_card_id(state, observer)
            top = list(player.deck[:1]) if known_top else []
            own_deck = list(player.deck[len(top) :])
            rng.shuffle(own_deck)
            players[seat] = replace(player, deck=(*top, *own_deck))
            continue
        # Hand cards that entered the hand publicly stay known (OQ-010);
        # the face-down draws and the deck are one unknown pool.
        known = frozenset(player.hand_public)
        secret_hand = [card for card in player.hand if card not in known]
        pool = [*secret_hand, *player.deck]
        rng.shuffle(pool)
        hand = (*player.hand_public, *pool[: len(secret_hand)])
        deck = tuple(pool[len(secret_hand) :])
        # A played Intrigue is public while its choices resolve; the rest of
        # an opponent's hand is indistinguishable from the deck.
        intrigue_pool.extend(
            card for card in player.intrigue_cards if card not in resolving
        )
        players[seat] = replace(player, hand=hand, deck=deck)

    rng.shuffle(intrigue_pool)
    cursor = 0
    for seat, player in enumerate(players):
        if seat == observer:
            continue
        original = state.players[seat].intrigue_cards
        kept = tuple(card for card in original if card in resolving)
        held = len(original) - len(kept)
        players[seat] = replace(
            player,
            intrigue_cards=(*kept, *intrigue_pool[cursor : cursor + held]),
        )
        cursor += held

    imperium_deck = list(state.imperium_deck)
    rng.shuffle(imperium_deck)
    contract_bank = list(state.contract_bank)
    rng.shuffle(contract_bank)
    conflict_deck = list(state.conflict_deck)
    rng.shuffle(conflict_deck)
    # Below each face-up top the Tech stacks are face down [Bloodlines p. 6].
    # Kota Odax's Secret Project is the exception while its frame is open:
    # "Game Start: 각 stack의 맨 아래 Tech tile을 본다" [Bloodlines p. 6], so
    # that seat knows the bottom tiles it is choosing between and they must
    # stay where the frame's recorded candidates say they are. Shuffling them
    # out of the bottom would leave the sampled world inconsistent with the
    # frame, and applying the choice would then leave the tile both on a
    # stack and on the Leader card. The knowledge is not carried past the
    # frame: OQ-041 keeps the two unchosen identities out of the observation.
    known_bottoms = frozenset(secret_project_candidates(state, observer))
    tech_stacks: list[tuple[str, ...]] = []
    for stack in state.tech_stacks:
        if len(stack) > 1 and stack[-1] in known_bottoms:
            middle = list(stack[1:-1])
            rng.shuffle(middle)
            tech_stacks.append((*stack[:1], *middle, stack[-1]))
            continue
        below = list(stack[1:])
        rng.shuffle(below)
        tech_stacks.append((*stack[:1], *below))
    return replace(
        state,
        players=tuple(players),
        intrigue_deck=(*peeked_intrigue, *intrigue_pool[cursor:]),
        imperium_deck=tuple(imperium_deck),
        contract_bank=tuple(contract_bank),
        conflict_deck=tuple(conflict_deck),
        tech_stacks=tuple(tech_stacks),
    )
