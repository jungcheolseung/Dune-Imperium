"""Unit movements shared by several rule modules (leaf: no rule imports)."""

from collections.abc import Mapping
from copy import replace

from dune_imperium.core.actions import ActionValue
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import replace_player
from dune_imperium.rules.strength import dreadnought_strength
from dune_imperium.rules.tactics import advance_tactics_token


def retreat_units(
    state: GameState,
    player: int,
    step_source: str,
    *,
    troops: int,
    commanders: int = 0,
    advance_tactics: bool = True,
) -> RuleResult:
    """Return Conflict units of ``player`` to the garrison, adjusting strength.

    Each troop or Sardaukar Commander carried two strength; a player left
    without units keeps no strength at all [Main pp. 12, 14] [Bloodlines
    p. 4]. A dreadnought in the Conflict is a unit too and a card's
    "troop" does not retreat it [Rise of Ix p. 6]: it stays, and its 3
    strength stays in the running total, so a seat whose troops all retreat
    keeps the strength of its dreadnought (no effect retreats a dreadnought
    yet). ``advance_tactics=False`` leaves Chani's Tactics token to
    a caller that moves several units for one source and advances it once.
    """

    owner = state.players[player]
    if (
        troops < 0
        or commanders < 0
        or troops + commanders < 1
        or owner.troops_conflict < troops
        or owner.commanders_conflict < commanders
    ):
        raise RuntimeError("retreat exceeds the troops in the Conflict")
    retreated = troops + commanders
    remaining_units = owner.units_in_conflict - retreated
    next_strength = (
        max(owner.combat_strength - 2 * retreated, 0) if remaining_units else 0
    )
    next_owner = replace(
        owner,
        troops_garrison=owner.troops_garrison + troops,
        troops_conflict=owner.troops_conflict - troops,
        commanders_garrison=owner.commanders_garrison + commanders,
        commanders_conflict=owner.commanders_conflict - commanders,
        combat_strength=next_strength,
    )
    # Tactician: Chani's token advances one space per troop retreated or
    # lost from the Conflict; Commanders are troops here [Bloodlines p. 4].
    tactics_events: tuple[GameEvent, ...] = ()
    if advance_tactics:
        next_owner, tactics_events = advance_tactics_token(
            next_owner, retreated, round_number=state.round_number
        )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, next_owner)),
        events=(
            GameEvent(
                event_id=f"{step_source}:retreat",
                kind="troops_retreated",
                payload=(
                    *((("commanders", commanders),) if commanders else ()),
                    ("count", retreated),
                    ("player", player),
                ),
            ),
            *tactics_events,
        ),
    )


def retreat_dreadnought(
    state: GameState, player: int, step_source: str
) -> RuleResult:
    """Return one of ``player``'s Conflict dreadnoughts to its garrison.

    "Each opponent retreats one dreadnought." [Cannon Turrets card, Steam app
    text]: a dreadnought is a unit worth ``dreadnought_strength`` (3, 4 for
    Prince Rhombur Vernius) [Rise of Ix p. 6], so the seat's strength drops by
    that, and a seat left with no unit has no strength at all, swords or not
    [Main p. 12] (rise-of-ix.md 9.3: when the retreated dreadnought was the
    last unit, the seat plays no more Combat Intrigue in that Conflict). A
    card's "troop" does not retreat a dreadnought and this does not advance
    Chani's Tactics token: it counts troops. The seat's dreadnoughts are
    alike, so nothing is chosen.
    """

    owner = state.players[player]
    if owner.dreadnoughts_conflict < 1:
        raise RuntimeError("retreat exceeds the dreadnoughts in the Conflict")
    remaining_units = owner.units_in_conflict - 1
    next_strength = (
        max(owner.combat_strength - dreadnought_strength(owner), 0)
        if remaining_units
        else 0
    )
    next_owner = replace(
        owner,
        dreadnoughts_garrison=owner.dreadnoughts_garrison + 1,
        dreadnoughts_conflict=owner.dreadnoughts_conflict - 1,
        combat_strength=next_strength,
    )
    return RuleResult(
        state=replace(state, players=replace_player(state.players, next_owner)),
        events=(
            GameEvent(
                event_id=f"{step_source}:dreadnought_retreat",
                kind="dreadnought_retreated",
                payload=(("player", player),),
            ),
        ),
    )


def unit_count_arguments(
    *,
    minimum: int,
    maximum: int | None,
    troops: int,
    commanders: int,
) -> tuple[tuple[tuple[str, ActionValue], ...], ...]:
    """Enumerate ``count`` units split between troops and Commanders.

    ``count`` is the total; ``commanders`` (omitted when zero) is the share
    taken by Sardaukar Commanders [Bloodlines p. 4].
    """

    units = troops + commanders
    limit = units if maximum is None else min(maximum, units)
    return tuple(
        (("count", count),) if share == 0 else (("commanders", share), ("count", count))
        for count in range(minimum, limit + 1)
        for share in range(max(0, count - troops), min(count, commanders) + 1)
    )


def unit_counts(arguments: Mapping[str, ActionValue]) -> tuple[int, int]:
    """Return (troops, commanders) from a unit-count action's arguments."""

    count = arguments["count"]
    commanders = arguments.get("commanders", 0)
    assert isinstance(count, int) and isinstance(commanders, int)
    return count - commanders, commanders
