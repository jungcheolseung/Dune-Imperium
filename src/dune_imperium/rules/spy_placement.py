"""Shared Observation Post occupancy operations."""

from copy import replace
from dataclasses import dataclass

from dune_imperium.content.uprising.board import (
    BOARD_SPACES_BY_ID,
    OBSERVATION_POSTS,
    Faction,
)
from dune_imperium.content.uprising.effect_dsl import PlaceSpy
from dune_imperium.content.uprising.types import AgentIcon
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


def solo_occupied_post_ids(
    state: GameState,
    player: int,
    allowed_post_ids: frozenset[str] | None = None,
) -> tuple[str, ...]:
    """Return posts where ``player``'s Spy is the sole occupant.

    Recalling the Spy from such a post leaves it unoccupied, so it is the
    only kind of recall that can free a placement target; a post shared
    with another player's Spy stays occupied after the recall
    [Main pp. 11, 20].
    """

    others = {
        post_id
        for candidate in state.players
        if candidate.player_id != player
        for post_id in candidate.spy_post_ids
    }
    return tuple(
        post.post_id
        for post in OBSERVATION_POSTS
        if post.post_id in state.players[player].spy_post_ids
        and post.post_id not in others
        and (allowed_post_ids is None or post.post_id in allowed_post_ids)
    )


def spy_placement_posts(
    state: GameState,
    player: int,
    allowed_post_ids: frozenset[str] | None = None,
    *,
    shared_post: bool = False,
) -> tuple[str, ...]:
    """The posts a placement may use now: the empty allowed ones, or with
    ``shared_post`` any allowed post the owner's own Spy does not hold --
    "you also have the option to ignore any opponents' Spies ... (You can't
    place the Spy where you already have a Spy of your own.)" [Bloodlines
    p. 5] (Spy with Deep Cover, Distraction)."""

    if shared_post:
        own = set(state.players[player].spy_post_ids)
        return tuple(
            post.post_id
            for post in OBSERVATION_POSTS
            if post.post_id not in own
            and (allowed_post_ids is None or post.post_id in allowed_post_ids)
        )
    return empty_observation_post_ids(state, allowed_post_ids)


def spy_recall_posts(
    state: GameState,
    player: int,
    placements: tuple[str, ...],
    allowed_post_ids: frozenset[str] | None = None,
    *,
    shared_post: bool = False,
) -> tuple[str, ...]:
    """The owner's Spies a recall-first may take with an empty supply: "If
    you have no Spies in your supply when you need to place one, you may
    first recall one of your Spies" [Main pp. 11, 20] -- any while a
    placement post is free; otherwise only one whose recall frees an
    allowed post: with ``shared_post`` any of the owner's allowed posts,
    else a post the owner's Spy holds alone (a post shared with another
    player's Spy stays occupied, ``solo_occupied_post_ids``)."""

    owner = state.players[player]
    if placements:
        return owner.spy_post_ids
    if shared_post:
        return tuple(
            post_id
            for post_id in owner.spy_post_ids
            if allowed_post_ids is None or post_id in allowed_post_ids
        )
    return solo_occupied_post_ids(state, player, allowed_post_ids)


@dataclass(frozen=True, slots=True)
class SpyOptions:
    """What a Spy placement offers now (``spy_options``): posts to place on,
    Spies to recall first, and whether the pass-up row (first) is offered."""

    place: tuple[str, ...] = ()
    recall: tuple[str, ...] = ()
    pass_up: bool = False


def spy_options(
    state: GameState,
    player: int,
    allowed_post_ids: frozenset[str] | None = None,
    *,
    shared_post: bool = False,
    recalled: bool = False,
    stuck_passes: bool = True,
) -> SpyOptions:
    """One placement's choices, whatever offers it.

    Placing is mandatory while a Spy is in the supply and a post is free (the
    erratum to [Main p. 11], OQ-057 (14)). Without a Spy "you may first
    recall one of your Spies" [Main pp. 11, 20]: the pass-up comes first,
    then the recalls that open a post (``spy_recall_posts``, OQ-057 (14)
    addition 2026-10-14); once a recall-first was made (``recalled``) the
    placement is owed and the pass-up is gone. With nothing to place or
    recall a host either passes (``stuck_passes``) or waits for the turn's
    end and fizzles (an Agent box, a Leader Signet, OQ-057 (1)).
    """

    owner = state.players[player]
    posts = spy_placement_posts(
        state, player, allowed_post_ids, shared_post=shared_post
    )
    if owner.spies_supply > 0:
        if posts:
            return SpyOptions(place=posts)
        return SpyOptions(pass_up=stuck_passes)
    recalls = spy_recall_posts(
        state, player, posts, allowed_post_ids, shared_post=shared_post
    )
    if not recalls:
        return SpyOptions(pass_up=stuck_passes and not recalled)
    return SpyOptions(recall=recalls, pass_up=not recalled)


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


def observation_post_ids_for_agent_icons(
    icons: tuple[AgentIcon, ...],
) -> frozenset[str]:
    """Return posts connected to at least one space with a target Agent icon."""

    targets = frozenset(icons)
    return frozenset(
        post.post_id
        for post in OBSERVATION_POSTS
        if any(
            BOARD_SPACES_BY_ID[space_id].agent_icon in targets
            for space_id in post.connected_space_ids
        )
    )


def _refuse_visited_space(reward: PlaceSpy) -> None:
    # The space visited this turn is the Agent box's to know
    # (``agent_box_abilities.agent_spy_rows``, Double Agent).
    if reward.visited_space:
        raise TypeError(f"{reward!r} is judged with its Agent box")


def spy_placement_allowed_post_ids(reward: PlaceSpy) -> frozenset[str] | None:
    """Return the posts a limited placement may use; None when unlimited.

    "Some effects limit placement. For example: '[Spy] on [City]' means the
    observation post must connect to a [City] board space." [Main p. 20]
    """

    _refuse_visited_space(reward)
    if reward.factions is not None:
        return observation_post_ids_for_factions(reward.factions)
    if reward.agent_icons is not None:
        return observation_post_ids_for_agent_icons(reward.agent_icons)
    return None


def is_spying_on_space(player: PlayerState, space_id: str) -> bool:
    """Return whether one of the player's Spies connects to ``space_id``."""

    occupied = frozenset(player.spy_post_ids)
    return any(
        post.post_id in occupied and space_id in post.connected_space_ids
        for post in OBSERVATION_POSTS
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
        spies_recalled_turn=player.spies_recalled_turn + 1,
        spy_post_ids=tuple(
            candidate for candidate in player.spy_post_ids if candidate != post_id
        ),
    )
