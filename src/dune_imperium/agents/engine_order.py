"""Decisions the scripted agents answer in the engine's older fixed order.

Stage B2 (OQ-112) lets a Conflict reward's recipient, and a completed
Contract's owner, resolve its icons in any order, a row each, where the
engine used to pay them in one fixed order
(``rules.combat.legacy_combat_reward_icon``,
``rules.contracts.legacy_contract_reward_icon``). The heuristic, the app AI and
the rollout agent answer such a window in that order and draw nothing from
their random streams for it, so their games stay the games they played
before the rows existed; a learning agent weighs the rows itself.

Stage B3c-2b lets the seat pick which waiting trash icon trashes a card,
where the engine used to pick it (``rules.optional_trash.legacy_trash_whole``):
those agents see only the older engine's pick of each card
(``older_engine_wholes``).
"""

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.rules.combat import legacy_combat_reward_icon
from dune_imperium.rules.contracts import (
    legacy_contract_icon_row,
    legacy_contract_reward_icon,
)
from dune_imperium.rules.effect_steps import first_step, presents_steps
from dune_imperium.rules.optional_trash import legacy_trash_whole


def engine_order_answer(
    state: GameState, player: int, legal_actions: tuple[DomainAction, ...]
) -> DomainAction | None:
    """The older engine's answer to this decision, when it is one of those
    (module docstring) and still legal; None otherwise. A Contract completed
    in the owner's turn waits on it as rows since stage B3b (OQ-112 (4));
    the older engine paid it at once, so its rows come first, in that order.
    Where the frame offers its effects effect first (stage B3), the answer
    is the step toward the whole action."""

    answer = (
        legacy_combat_reward_icon(state, player)
        or legacy_contract_reward_icon(state, player)
        or legacy_contract_icon_row(state, player)
    )
    if answer is None:
        return None
    if answer not in legal_actions and presents_steps(state):
        try:
            answer = first_step(state, answer)
        except ValueError:
            return None
    return answer if answer in legal_actions else None


def older_engine_wholes(
    state: GameState, player: int, wholes: tuple[DomainAction, ...]
) -> tuple[DomainAction, ...]:
    """``wholes`` as the older engine offered them: of the rows trashing a
    card with one of the trashes waiting on the turn (stage B3c-2b), only
    the one with the trash that engine picked itself (module docstring)."""

    picked: dict[str, DomainAction | None] = {}
    kept: list[DomainAction] = []
    for whole in wholes:
        arguments = dict(whole.arguments)
        if whole.action_id == "trash_optional_card" and "printed" in arguments:
            card = str(arguments["card_id"])
            if card not in picked:
                picked[card] = legacy_trash_whole(state, player, card)
            if whole != picked[card]:
                continue
        kept.append(whole)
    return tuple(kept)
