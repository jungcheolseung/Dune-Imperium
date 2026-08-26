"""Shared Observation Post occupancy operations."""

from dataclasses import replace

from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.core.player import PlayerState
from dune_imperium.core.state import GameState


def empty_observation_post_ids(
    state: GameState,
    allowed_post_ids: frozenset[str] | None = None,
) -> tuple[str, ...]:
    """Return empty Observation Posts in fixed board order."""

    occupied = {post_id for player in state.players for post_id in player.spy_post_ids}
    return tuple(
        post.post_id
        for post in OBSERVATION_POSTS
        if post.post_id not in occupied
        and (allowed_post_ids is None or post.post_id in allowed_post_ids)
    )


def observation_post_ids_for_factions(
    factions: tuple[Faction, ...],
) -> frozenset[str]:
    """Return posts connected to at least one space of a target Faction."""

    targets = frozenset(factions)
    return frozenset(
        post.post_id
        for post in OBSERVATION_POSTS
        if any(
            BOARD_SPACES_BY_ID[space_id].faction in targets
            for space_id in post.connected_space_ids
        )
    )


def spied_factions(player: PlayerState) -> tuple[Faction, ...]:
    """Return Factions with a space connected to one of the player's Spies."""

    occupied = frozenset(player.spy_post_ids)
    return tuple(
        faction
        for faction in Faction
        if any(
            post.post_id in occupied
            and any(
                BOARD_SPACES_BY_ID[space_id].faction is faction
                for space_id in post.connected_space_ids
            )
            for post in OBSERVATION_POSTS
        )
    )


def is_spying_on_maker_space(player: PlayerState) -> bool:
    """Return whether one of the player's Spies watches a Maker space."""

    occupied = frozenset(player.spy_post_ids)
    return any(
        post.post_id in occupied
        and any(
            BOARD_SPACES_BY_ID[space_id].maker
            for space_id in post.connected_space_ids
        )
        for post in OBSERVATION_POSTS
    )


def place_spy(player: PlayerState, post_id: str) -> PlayerState:
    """Move one of ``player``'s Spies from supply to an Observation Post."""

    known_posts = {post.post_id for post in OBSERVATION_POSTS}
    if post_id not in known_posts:
        raise ValueError("Spy placement requires a known Observation Post")
    if player.spies_supply == 0:
        raise ValueError("player has no Spy in supply")
    if post_id in player.spy_post_ids:
        raise ValueError("player already occupies this Observation Post")
    return replace(
        player,
        spies_supply=player.spies_supply - 1,
        spy_post_ids=(*player.spy_post_ids, post_id),
    )


def recall_spy(player: PlayerState, post_id: str) -> PlayerState:
    """Return one of ``player``'s placed Spies to supply."""

    if post_id not in player.spy_post_ids:
        raise ValueError("player does not occupy this Observation Post")
    return replace(
        player,
        spies_supply=player.spies_supply + 1,
        spy_post_ids=tuple(
            candidate for candidate in player.spy_post_ids if candidate != post_id
        ),
    )
