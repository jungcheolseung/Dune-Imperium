"""Shared personal-card trash transition and card-specific triggers."""

from dataclasses import replace

from dune_imperium.content.uprising.imperium import imperium_card_for_instance
from dune_imperium.content.uprising.reserve import RESERVE_STACKS_BY_ID
from dune_imperium.content.uprising.types import PersonalCardTrashEffect
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState


def trash_personal_card(
    state: GameState,
    player: int,
    card_id: str,
    *,
    source: str,
    allow_deck: bool = False,
) -> RuleResult:
    """Remove one owned card from an eligible zone and resolve its trash trigger.

    Deck trashing is an explicit exception used by card effects such as Long
    Live the Fighters; ordinary trash callers remain limited to hand, discard,
    and in-play cards.
    """

    if not 0 <= player < state.config.players:
        raise ValueError("trash player must identify a configured seat")
    if not card_id or not source:
        raise ValueError("trash card and source IDs must not be empty")
    if not isinstance(allow_deck, bool):
        raise TypeError("allow_deck must be a boolean")
    owner = state.players[player]
    eligible = (*owner.hand, *owner.discard_pile, *owner.in_play)
    if allow_deck:
        eligible = (*owner.deck, *eligible)
    if card_id not in eligible:
        raise ValueError("trash card is not in an eligible owned zone")

    reserve_card_id = _reserve_card_id(card_id)
    next_owner = replace(
        owner,
        deck=(
            tuple(candidate for candidate in owner.deck if candidate != card_id)
            if allow_deck
            else owner.deck
        ),
        hand=tuple(candidate for candidate in owner.hand if candidate != card_id),
        discard_pile=tuple(
            candidate for candidate in owner.discard_pile if candidate != card_id
        ),
        in_play=tuple(candidate for candidate in owner.in_play if candidate != card_id),
        trashed=(
            owner.trashed if reserve_card_id is not None else (*owner.trashed, card_id)
        ),
    )
    reserve_stacks = state.reserve_stacks
    if reserve_card_id is not None:
        if reserve_card_id not in dict(reserve_stacks):
            raise RuntimeError("trashed Reserve card has no matching stack")
        reserve_stacks = tuple(
            (
                candidate_id,
                count + 1 if candidate_id == reserve_card_id else count,
            )
            for candidate_id, count in reserve_stacks
        )

    intrigue_deck = state.intrigue_deck
    events = [
        GameEvent(
            event_id=f"{source}:trash:{card_id}",
            kind="card_trashed",
            payload=(("card_id", card_id), ("player", player)),
        )
    ]
    pending_intrigue_draws = state.pending_intrigue_draws
    if _trash_effect(card_id) is PersonalCardTrashEffect.DRAW_INTRIGUE_CARD:
        draw_source = f"{source}:trash:{card_id}:intrigue_draw"
        if intrigue_deck:
            next_owner = replace(
                next_owner,
                intrigue_cards=(*next_owner.intrigue_cards, intrigue_deck[0]),
            )
            intrigue_deck = intrigue_deck[1:]
            events.append(
                GameEvent(
                    event_id=draw_source,
                    kind="intrigue_card_drawn",
                    payload=(("count", 1), ("player", player)),
                )
            )
        else:
            pending_intrigue_draws = (*pending_intrigue_draws, (player, 1, draw_source))

    players = tuple(
        next_owner if candidate.player_id == player else candidate
        for candidate in state.players
    )
    return RuleResult(
        state=replace(
            state,
            players=players,
            reserve_stacks=reserve_stacks,
            intrigue_deck=intrigue_deck,
            pending_intrigue_draws=pending_intrigue_draws,
        ),
        events=tuple(events),
    )


def _trash_effect(card_id: str) -> PersonalCardTrashEffect | None:
    if not card_id.startswith("imperium:"):
        return None
    return imperium_card_for_instance(card_id).trash_effect


def _reserve_card_id(instance_id: str) -> str | None:
    parts = instance_id.split(":", 2)
    if len(parts) != 3 or parts[0] != "reserve":
        return None
    card_id = parts[1]
    return card_id if card_id in RESERVE_STACKS_BY_ID else None
