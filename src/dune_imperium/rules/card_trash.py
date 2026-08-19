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
) -> RuleResult:
    """Remove one owned card from an eligible zone and resolve its trash trigger."""

    if not 0 <= player < state.config.players:
        raise ValueError("trash player must identify a configured seat")
    if not card_id or not source:
        raise ValueError("trash card and source IDs must not be empty")
    owner = state.players[player]
    eligible = (*owner.hand, *owner.discard_pile, *owner.in_play)
    if card_id not in eligible:
        raise ValueError("trash card is not in an eligible owned zone")

    reserve_card_id = _reserve_card_id(card_id)
    next_owner = replace(
        owner,
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
    if _trash_effect(card_id) is PersonalCardTrashEffect.DRAW_INTRIGUE_CARD:
        drawn = intrigue_deck[:1]
        intrigue_deck = intrigue_deck[len(drawn) :]
        next_owner = replace(
            next_owner,
            intrigue_cards=(*next_owner.intrigue_cards, *drawn),
        )
        events.append(
            GameEvent(
                event_id=f"{source}:trash:{card_id}:intrigue_draw",
                kind="intrigue_card_drawn",
                payload=(("count", len(drawn)), ("player", player)),
            )
        )

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
