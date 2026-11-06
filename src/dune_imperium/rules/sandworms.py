"""One gate for every sandworm summon: when a summoned sandworm does something."""

from enum import StrEnum

from dune_imperium.core.state import GameState
from dune_imperium.rules.leader_abilities import units_deployment_blocked
from dune_imperium.rules.planetologist import replaces_sandworms
from dune_imperium.rules.shield_wall import current_conflict_is_shield_wall_protected


class SandwormBlock(StrEnum):
    """Why a summon now would do nothing."""

    MAKER_HOOKS = "maker_hooks"
    NO_CONFLICT = "no_conflict"
    DEPLOYMENT_BARRED = "deployment_barred"
    SHIELD_WALL = "shield_wall"


def sandworm_block(
    state: GameState, player: int, *, needs_hooks: bool = True
) -> SandwormBlock | None:
    """Why a sandworm summoned for ``player`` now would do nothing, or None.

    A summon needs the Maker Hooks it asks for ("with Maker Hooks, summon
    sandworms" [Board Guide pp. 1-2]), a Conflict to deploy into (a summoned
    sandworm is immediately deployed [Main p. 20], so Emperor of the Known
    Universe's deployment ban withholds it [Main p. 17]) and no Shield Wall
    protecting that Conflict [Main p. 20] -- except that Arrakis
    Planetologist replaces the sandworms "even when the Conflict is
    protected by the Shield Wall" [Liet Kynes card]. Checked in that order.
    The Maker spaces, Arrakis Revolt and the Intrigue cards read this; every
    input is public.
    """

    owner = state.players[player]
    if needs_hooks and not owner.maker_hooks:
        return SandwormBlock.MAKER_HOOKS
    if not state.current_conflict_ids:
        return SandwormBlock.NO_CONFLICT
    if units_deployment_blocked(state, player):
        return SandwormBlock.DEPLOYMENT_BARRED
    if not replaces_sandworms(owner) and current_conflict_is_shield_wall_protected(
        state
    ):
        return SandwormBlock.SHIELD_WALL
    return None
