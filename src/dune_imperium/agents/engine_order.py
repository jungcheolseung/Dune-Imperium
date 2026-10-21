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
(``older_engine_wholes``). Stage B3e-1 does the same for a research icon,
a triggered draw and a Reveal gain, now one action per entity that printed
it where the engine took the newest icon or the oldest draw or gain itself
(``legacy_research_icon_whole``, ``legacy_owed_draw_whole``,
``legacy_reveal_gain_whole``).
"""

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.state import GameState
from dune_imperium.rules.combat import legacy_combat_reward_icon
from dune_imperium.rules.contracts import (
    legacy_contract_icon_row,
    legacy_contract_reward_icon,
)
from dune_imperium.rules.effect_steps import first_step, picked_rows, presents_steps
from dune_imperium.rules.immortality import legacy_research_icon_whole
from dune_imperium.rules.optional_trash import legacy_trash_whole
from dune_imperium.rules.owed_draws import legacy_owed_draw_whole
from dune_imperium.rules.reveal_turn import legacy_reveal_gain_whole


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
    the one with the trash that engine picked itself; of the actions now
    one per entity that printed a research icon, a triggered draw or a
    Reveal gain (stage B3e-1), only the one that engine took (module
    docstring).

    Once an effect is picked these agents only finish it: their own pick
    goes on through ``PlacementMemory``, and a pick another chooser made (a
    network seat whose untrained rows fall back to them) is taken as it is
    -- the older engine's trash may be another one, and filtering by it
    could leave no card to pick (the 2026-10-20 review of B3c-2b)."""

    if picked_rows(state):
        return wholes
    picked: dict[object, DomainAction | None] = {}
    kept: list[DomainAction] = []
    for whole in wholes:
        key = _older_key(whole)
        if key is not None:
            if key not in picked:
                picked[key] = _older_pick(state, player, whole)
            if whole != picked[key]:
                continue
        kept.append(whole)
    return tuple(kept)


def _older_key(whole: DomainAction) -> object:
    """What the older engine offered one action for, where the action now
    names the entity that printed the effect (stage B3c-2b, B3e-1); None
    for any other action."""

    arguments = dict(whole.arguments)
    if "printed" not in arguments:
        return None
    if whole.action_id == "trash_optional_card":
        return whole.action_id, arguments["card_id"]
    if whole.action_id == "resolve_research_icon":
        return whole.action_id, arguments["effect"]
    if whole.action_id in _OWED_DRAWS:
        return whole.action_id
    if whole.action_id == "gain_reveal_resources":
        return whole.action_id, tuple(arguments[name] for name in _RESOURCES)
    if whole.action_id == "gain_reveal_faction_influence":
        return whole.action_id, arguments["faction"]
    if whole.action_id in _REVEAL_GAINS:
        return whole.action_id
    return None


def _older_pick(
    state: GameState, player: int, whole: DomainAction
) -> DomainAction | None:
    """The older engine's pick among the actions sharing ``whole``'s key."""

    arguments = dict(whole.arguments)
    if whole.action_id == "trash_optional_card":
        return legacy_trash_whole(state, player, str(arguments["card_id"]))
    if whole.action_id == "resolve_research_icon":
        return legacy_research_icon_whole(state, player, str(arguments["effect"]))
    if whole.action_id in _OWED_DRAWS:
        return legacy_owed_draw_whole(state, player, whole.action_id)
    unnamed = DomainAction(
        whole.action_id,
        player,
        tuple(
            (name, value)
            for name, value in whole.arguments
            if name not in ("printed", "source")
        ),
    )
    return legacy_reveal_gain_whole(state, player, unnamed)


_OWED_DRAWS = frozenset({"draw_owed_intrigue", "draw_owed_card"})
_REVEAL_GAINS = frozenset({
    "recruit_reveal_troops",
    "draw_reveal_intrigue",
    "generate_reveal_specimens",
    "advance_reveal_tleilaxu",
    "advance_reveal_research",
})
_RESOURCES = ("solari", "spice", "water")
