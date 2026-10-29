"""Shared transitions for discarding personal cards and their discard triggers.

A card's "When this card is discarded" trigger fires when the card is
discarded from hand or straight from its owner's deck (Long Live the Fighters,
Controlled). The deck case is a project convention (OQ-013, user ruling
2026-10-04) that departs from the official sentence "Only discarding it from
your hand triggers the ability." [Main p. 17]. Moving cards from in play to the
discard pile during Clean Up is not a discard and never triggers it.
"""

from copy import replace

from dune_imperium.content.uprising.effect_dsl import GainResources
from dune_imperium.content.uprising.personal_cards import personal_card_for_instance
from dune_imperium.content.uprising.trigger_abilities import (
    discard_ability,
    single_resource,
)
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
    """Move one hand card to discard and resolve its discard trigger.

    Shared by arrow costs (Agent, Intrigue and Tech) and discard effects.
    Rise of Ix's future Unload continuation belongs at this boundary: finish
    the discarded card's Unload before the caller resumes its arrow reward
    (docs/rules/rise-of-ix.md 7). Clean Up must not use this transition.
    """

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
    # Spacing Guild's Favor's 2 spice, Corrupt Bureaucrat's 3 Solari: the
    # card's discard record (composed A4a).
    ability = discard_ability(personal_card_for_instance(card_id).discard_effect)
    if ability is None:
        return RuleResult(state=state, events=())
    (reward,) = ability.sections[0].rewards
    if not isinstance(reward, GainResources):
        raise TypeError(f"{reward!r} is not a discard box's gain")
    gained = single_resource(reward)
    next_owner = replace(
        owner,
        resources=replace(
            owner.resources,
            solari=owner.resources.solari + reward.solari,
            spice=owner.resources.spice + reward.spice,
            water=owner.resources.water + reward.water,
        ),
    )
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
