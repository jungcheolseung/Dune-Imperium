"""Shared transitions for discarding personal cards from hand."""

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
    """Move one hand card to discard and resolve its hand-discard trigger."""

    if not 0 <= player < state.config.players:
        raise ValueError("discard player must identify a configured seat")
    if not source:
        raise ValueError("discard source must not be empty")
    owner = state.players[player]
    if card_id not in owner.hand:
        raise ValueError("discarded personal card must be in hand")
    card = personal_card_for_instance(card_id)
    next_owner = replace(
        owner,
        hand=tuple(candidate for candidate in owner.hand if candidate != card_id),
        discard_pile=(*owner.discard_pile, card_id),
    )
    events: list[GameEvent] = [
        GameEvent(
            event_id=f"{source}:discard:{card_id}",
            kind="card_discarded",
            payload=(("card_id", card_id), ("player", player)),
        )
    ]
    if card.discard_effect is PersonalCardDiscardEffect.GAIN_TWO_SPICE:
        next_owner = replace(
            next_owner,
            resources=replace(
                next_owner.resources,
                spice=next_owner.resources.spice + 2,
            ),
        )
        events.append(
            GameEvent(
                event_id=f"{source}:discard:{card_id}:effect",
                kind="personal_card_discard_effect_resolved",
                payload=(
                    ("card_id", card_id),
                    ("player", player),
                    ("spice", 2),
                ),
            )
        )
    players = tuple(
        next_owner if candidate.player_id == player else candidate
        for candidate in state.players
    )
    return RuleResult(state=replace(state, players=players), events=tuple(events))
