"""Ornithopter Fleet: every battle icon of its owner is an Ornithopter.

"Each battle icon you have, including wild battle icons, must be treated as
an Ornithopter instead. This can cause you to immediately match battle
icons when you acquire it" [Bloodlines p. 12] [Ornithopter Fleet Tech
tile]. With one icon on every card, any two face-up battle cards match, so
the matching needs no choice: the face-up cards pair off in a fixed order
and each pair flips for one Victory Point [Main p. 14]. A leaf module so
both ``combat`` and ``tech`` can use it.
"""

from dataclasses import replace

from dune_imperium.content.bloodlines.tech import TechAbility, has_tech
from dune_imperium.core.events import GameEvent
from dune_imperium.core.player import PlayerState


def has_ornithopter_fleet(player: PlayerState) -> bool:
    """Return whether the seat's battle icons are all Ornithopters."""

    return has_tech(player.tech_ids, TechAbility.ORNITHOPTER_ICONS)


def face_up_battle_card_ids(player: PlayerState) -> tuple[str, ...]:
    """Return the seat's face-up Objective and won Conflict cards, in order."""

    face_down = set(player.face_down_battle_card_ids)
    return tuple(
        card_id
        for card_id in (*player.objective_ids, *player.won_conflict_ids)
        if card_id not in face_down
    )


def match_all_battle_icons(
    player: PlayerState,
    *,
    source: str,
) -> tuple[PlayerState, tuple[GameEvent, ...]]:
    """Pair every face-up battle card of an Ornithopter Fleet owner.

    Cards pair in their zone order (Objective first, then won Conflicts in
    the order won); each pair flips face down and scores one Victory Point.
    An odd card stays face up for the next match.
    """

    face_up = face_up_battle_card_ids(player)
    pairs = tuple(
        (face_up[index], face_up[index + 1]) for index in range(0, len(face_up) - 1, 2)
    )
    if not pairs:
        return player, ()
    matched = replace(
        player,
        victory_points=player.victory_points + len(pairs),
        face_down_battle_card_ids=(
            *player.face_down_battle_card_ids,
            *(card_id for pair in pairs for card_id in pair),
        ),
    )
    events = tuple(
        GameEvent(
            event_id=f"{source}:ornithopter_match:{index}",
            kind="battle_icons_matched",
            payload=(
                ("first_card_id", first),
                ("player", player.player_id),
                ("second_card_id", second),
            ),
        )
        for index, (first, second) in enumerate(pairs)
    )
    return matched, events
