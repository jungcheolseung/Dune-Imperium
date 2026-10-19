"""Decisions the scripted agents answer in the engine's older fixed order.

Stage B2 (OQ-112) lets a Conflict reward's recipient, and a completed
Contract's owner, resolve its icons in any order, a row each, where the
engine used to pay them in one fixed order
(``rules.combat.legacy_combat_reward_icon``,
``rules.contracts.legacy_contract_reward_icon``). The heuristic, the app AI and
the rollout agent answer such a window in that order and draw nothing from
their random streams for it, so their games stay the games they played
before the rows existed; a learning agent weighs the rows itself.
"""

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.rules.combat import legacy_combat_reward_icon
from dune_imperium.rules.contracts import legacy_contract_reward_icon


def engine_order_answer(
    state: GameState, player: int, legal_actions: tuple[DomainAction, ...]
) -> DomainAction | None:
    """The older engine's answer to this decision, when it is one of those
    (module docstring) and still legal; None otherwise."""

    answer = legacy_combat_reward_icon(state, player) or legacy_contract_reward_icon(
        state, player
    )
    return answer if answer is not None and answer in legal_actions else None
