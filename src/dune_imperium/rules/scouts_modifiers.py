"""Arrakeen Scouts: the round-long rule changes, read by other modules.

Kept apart from ``rules.scouts`` so the modules that read them (Agent
placement, acquisition costs) import nothing of the Scouts step itself
(``docs/rules/arrakeen-scouts.md`` 6.1).
"""

from typing import Final

from dune_imperium.content.arrakeen_scouts import RoundModifier
from dune_imperium.content.uprising.board import BoardSpace
from dune_imperium.core.state import GameState


def round_modifier(state: GameState) -> RoundModifier | None:
    """Return this round's rule change, if an event set one."""

    if not state.scouts_round_modifier:
        return None
    return RoundModifier(state.scouts_round_modifier)


def ignores_influence_requirements_this_round(state: GameState) -> bool:
    """Unlikely Allies: board spaces' Influence requirements are waived.

    [Scouts event: Unlikely Allies] (docs/rules/arrakeen-scouts.md 6.1):
    only the requirement; cost and occupancy rules stand.
    """

    return round_modifier(state) is RoundModifier.IGNORE_INFLUENCE_REQUIREMENTS


SPICE_MUST_FLOW: Final = "the_spice_must_flow"
MARKET_OPENING_DISCOUNT: Final = 2


def reserve_discount(state: GameState, card_id: str) -> int:
    """Market Opening: the round's first The Spice Must Flow costs 2 less.

    [Scouts event: Market Opening] (docs/rules/arrakeen-scouts.md 6.1): the
    first copy acquired this round by anyone (OQ-081 (b)); the discount
    applies to the cost check and the payment alike.
    """

    if card_id != SPICE_MUST_FLOW or state.scouts_discount_used:
        return 0
    if round_modifier(state) is not RoundModifier.SPICE_MUST_FLOW_DISCOUNT:
        return 0
    return MARKET_OPENING_DISCOUNT


def discount_used_after(state: GameState, card_id: str) -> bool:
    """``scouts_discount_used`` once ``card_id`` has been acquired now."""

    return state.scouts_discount_used or reserve_discount(state, card_id) > 0


def space_is_combat(state: GameState, space: BoardSpace) -> bool:
    """Whether ``space`` counts as a Combat space this round.

    Eyes on Arrakis makes every Faction space a Combat space for the round
    [Scouts event: Eyes on Arrakis] (docs/rules/arrakeen-scouts.md 6.1).
    """

    if space.combat:
        return True
    return (
        space.faction is not None
        and round_modifier(state) is RoundModifier.FACTION_SPACES_ARE_COMBAT
    )
