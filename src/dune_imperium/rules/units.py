"""Unit movements shared by several rule modules (leaf: no rule imports)."""

from dataclasses import replace

from dune_imperium.core.engine import RuleResult
from dune_imperium.core.events import GameEvent
from dune_imperium.core.state import GameState
from dune_imperium.rules.frames import replace_player


def retreat_units(
    state: GameState,
    player: int,
    step_source: str,
    *,
    troops: int,
    commanders: int = 0,
) -> RuleResult:
    """Return Conflict units of ``player`` to the garrison, adjusting strength.

    Each troop or Sardaukar Commander carried two strength; a player left
    without units keeps no strength at all [Main pp. 12, 14] [Bloodlines
    p. 4].
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
        ),
    )
