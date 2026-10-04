"""Shared transitions for discarding personal cards and their discard triggers.

A card's "When this card is discarded" trigger fires when the card is
discarded from hand or straight from its owner's deck (Long Live the Fighters,
Controlled). The deck case is a project convention (OQ-013, user ruling
2026-10-04) that departs from the official sentence "Only discarding it from
your hand triggers the ability." [Main p. 17]. Moving cards from in play to the
discard pile during Clean Up is not a discard and never triggers it.
"""

from dataclasses import replace

from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.types import PersonalCardDiscardEffect
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState


def discard_personal_card_from_hand(
    state: GameState,
    player: int,
    card_id: str,
    *,
    source: str,
) -> RuleResult:
    """Move one hand card to discard and resolve its discard trigger."""

    if not 0 <= player < state.config.players:
        raise ValueError("discard player must identify a configured seat")
    if not source:
        raise ValueError("discard source must not be empty")
    owner = state.players[player]
    if card_id not in owner.hand:
        raise ValueError("discarded personal card must be in hand")
    next_owner = replace(
        owner,
        hand=tuple(candidate for candidate in owner.hand if candidate != card_id),
        discard_pile=(*owner.discard_pile, card_id),
    )
    moved = replace(
        state,
        players=tuple(
            next_owner if candidate.player_id == player else candidate
            for candidate in state.players
        ),
    )
    discard_event = GameEvent(
        event_id=f"{source}:discard:{card_id}",
        kind="card_discarded",
        payload=(("card_id", card_id), ("player", player)),
    )
    triggered = resolve_personal_card_discard_trigger(
        moved, player, card_id, source=source
    )
    return RuleResult(
        state=triggered.state,
        events=(discard_event, *triggered.events),
    )


def resolve_personal_card_discard_trigger(
    state: GameState,
    player: int,
    card_id: str,
    *,
    source: str,
) -> RuleResult:
    """Resolve "When this card is discarded" for a card the seat just discarded.

    The caller has already moved the card from hand or deck into the seat's
    discard pile. A deck discard triggers too (OQ-013, user ruling 2026-10-04),
    although the official text reads "Only discarding it from your hand
    triggers the ability." [Main p. 17]; Clean Up must not call this. A card
    without a discard effect returns the state unchanged with no events.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("discard player must identify a configured seat")
    if not source:
        raise ValueError("discard source must not be empty")
    owner = state.players[player]
    if card_id not in owner.discard_pile:
        raise ValueError("discard trigger card must be in the discard pile")
    card = personal_card_for_instance(card_id)
    if card.discard_effect is PersonalCardDiscardEffect.GAIN_TWO_SPICE:
        resources = replace(owner.resources, spice=owner.resources.spice + 2)
        gained: tuple[str, int] = ("spice", 2)
    elif card.discard_effect is PersonalCardDiscardEffect.GAIN_THREE_SOLARI:
        # Corrupt Bureaucrat: "When this card is discarded: 3 Solari".
        resources = replace(owner.resources, solari=owner.resources.solari + 3)
        gained = ("solari", 3)
    else:
        return RuleResult(state=state, events=())
    next_owner = replace(owner, resources=resources)
    players = tuple(
        next_owner if candidate.player_id == player else candidate
        for candidate in state.players
    )
    return RuleResult(
        state=replace(state, players=players),
        events=(
            GameEvent(
                event_id=f"{source}:discard:{card_id}:effect",
                kind="personal_card_discard_effect_resolved",
                payload=(("card_id", card_id), ("player", player), gained),
            ),
        ),
    )
