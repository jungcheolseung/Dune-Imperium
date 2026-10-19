"""The Agent turn's two steps for agents that judge whole placements.

Stage B1 (docs/stage-b-plan.md 3a, OQ-111) offers an Agent turn as a card
pick (``choose_agent_card``) and then a space pick (``place_agent``). The
heuristic and the app AI weigh a placement as a whole -- a card going to a
space -- so for them a step's rows are shown as the placements they stand
for (the card-and-space actions ``rules.agent_turn.executable_placements``
builds, action id ``agent_turn``), and the placement they choose is turned
back into the step's action. Everything a placement reads (the seat's hand,
resources and the board) is the seat's own view.

``PlacementMemory`` keeps the placement chosen at the card pick for the
space pick right after it, so a placement stays one decision of the agent:
it is not weighed again among the picked card's spaces, and an agent that
draws a random tie-break on every decision draws once per placement, as it
did when a placement was one action (its games stay the games it played
then).
"""

from collections.abc import Callable

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.engine import RuleResult
from dune_imperium.core.state import GameState
from dune_imperium.rules import UprisingRulesEngine
from dune_imperium.rules.agent_turn import (
    CARD_PICK_ACTION,
    SPACE_PICK_ACTION,
    agent_card_pick,
    agent_card_pick_actions,
    agent_space_pick_actions,
    executable_placements,
)

PLACEMENT_ACTION = "agent_turn"

type StepAnswer = Callable[[DomainAction], DomainAction]
type Decide = Callable[[tuple[DomainAction, ...]], DomainAction]


def placements_for_steps(
    state: GameState, player: int, legal_actions: tuple[DomainAction, ...]
) -> tuple[tuple[DomainAction, ...], StepAnswer] | None:
    """The legal list with an Agent-turn step's rows shown as placements,
    and how to turn the chosen action back into a legal one; None when the
    decision holds no Agent-turn step. Only the placements whose step is in
    ``legal_actions`` are shown (a caller may pass part of the list)."""

    pick = agent_card_pick(state, player)
    if pick is not None and any(
        action.action_id == SPACE_PICK_ACTION for action in legal_actions
    ):
        card, graft = pick
        offered = set(legal_actions)
        placements = tuple(
            placement
            for placement in executable_placements(state, player, card)
            if (dict(placement.arguments).get("graft") is True) == graft
            and agent_space_pick_actions(player, (placement,), card, graft)[0]
            in offered
        )

        def to_space(chosen: DomainAction) -> DomainAction:
            if chosen.action_id != PLACEMENT_ACTION:
                return chosen
            (step,) = agent_space_pick_actions(player, (chosen,), card, graft)
            return step

        return placements, to_space
    if any(action.action_id == CARD_PICK_ACTION for action in legal_actions):
        offered = set(legal_actions)
        placements = tuple(
            placement
            for placement in executable_placements(state, player)
            if agent_card_pick_actions(player, (placement,))[0] in offered
        )
        others = tuple(
            action for action in legal_actions if action.action_id != CARD_PICK_ACTION
        )

        def to_card(chosen: DomainAction) -> DomainAction:
            if chosen.action_id != PLACEMENT_ACTION:
                return chosen
            (step,) = agent_card_pick_actions(player, (chosen,))
            return step

        return (*placements, *others), to_card
    return None


def apply_placement(
    engine: UprisingRulesEngine, state: GameState, placement: DomainAction
) -> RuleResult:
    """Apply a whole placement (an ``agent_turn`` action as
    ``rules.agent_turn.executable_placements`` builds it) as the engine's two
    steps: its card pick, then its space pick. The result's events are both
    steps'. Raises ``ValueError`` when either step is not legal."""

    player = placement.actor
    (pick,) = agent_card_pick_actions(player, (placement,))
    legal = engine.legal_actions(state, player)
    if pick not in legal:
        raise ValueError(f"{pick} is not legal")
    picked = engine.apply(state, pick, legal_actions=legal)
    card, graft = agent_card_pick(picked.state, player) or ("", False)
    (space,) = agent_space_pick_actions(player, (placement,), card, graft)
    legal = engine.legal_actions(picked.state, player)
    if space not in legal:
        raise ValueError(f"{space} is not legal")
    placed = engine.apply(picked.state, space, legal_actions=legal)
    return RuleResult(state=placed.state, events=(*picked.events, *placed.events))


class PlacementMemory:
    """An agent's placement chosen at a card pick, for the space pick that
    follows it (module docstring)."""

    __slots__ = ("_kept",)

    def __init__(self) -> None:
        # (seat, revision after the card pick, the placement).
        self._kept: tuple[int, int, DomainAction] | None = None

    def choose(
        self,
        state: GameState,
        player: int,
        legal_actions: tuple[DomainAction, ...],
        decide: Decide,
    ) -> DomainAction:
        """``decide``'s answer to the decision, an Agent-turn step's rows
        shown to it as placements; the space pick of a placement it chose at
        the card pick just before is answered without asking again."""

        kept, self._kept = self._kept, None
        if kept is not None and kept[:2] == (player, state.revision):
            pick = agent_card_pick(state, player)
            if pick is not None:
                remembered = agent_space_pick_actions(player, (kept[2],), *pick)
                if remembered and remembered[0] in legal_actions:
                    return remembered[0]
        steps = placements_for_steps(state, player, legal_actions)
        if steps is None:
            return decide(legal_actions)
        placements, answer = steps
        chosen = decide(placements)
        step = answer(chosen)
        if step.action_id == CARD_PICK_ACTION:
            self._kept = (player, state.revision + 1, chosen)
        return step
