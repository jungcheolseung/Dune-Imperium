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

Stage B3 (``rules.effect_steps``) shows a waiting effect the same way: a
frame that offers its effects effect first is shown to these agents as the
whole actions its rows stand for -- an effect with its target, as the rules
resolve it -- and the memory takes the rest of the chosen whole action's
steps without asking again.
"""

from collections.abc import Callable

from dune_imperium.core.actions import DomainAction
from dune_imperium.core.chance import ChanceOutcome
from dune_imperium.core.engine import RuleResult, Transition
from dune_imperium.core.events import GameEvent
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
from dune_imperium.rules.effect_steps import (
    first_step,
    path_of,
    picked_rows,
    presents_steps,
    without_pick,
)

PLACEMENT_ACTION = "agent_turn"
# The whole actions of a decision come from the rules' providers alone, so
# any engine instance gives the same list.
_ENGINE = UprisingRulesEngine()

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
    return _effect_wholes(state, player, legal_actions)


def _effect_wholes(
    state: GameState, player: int, legal_actions: tuple[DomainAction, ...]
) -> tuple[tuple[DomainAction, ...], StepAnswer] | None:
    """A decision's rows shown as the whole actions they stand for, in the
    rules' order (stage B3); None where the frame shows no effect steps."""

    if not presents_steps(state):
        return None
    offered = set(legal_actions)
    every = _ENGINE.whole_actions(state, player)
    if any(whole in offered and whole != first_step(state, whole) for whole in every):
        # The caller lists the whole actions themselves (a walk applying
        # them with ``apply_whole``): the choice is one of them, as it is.
        return tuple(whole for whole in every if whole in offered), _same
    wholes = tuple(whole for whole in every if first_step(state, whole) in offered)
    shown = set(wholes)

    def to_step(chosen: DomainAction) -> DomainAction:
        if chosen not in shown:
            return chosen
        return first_step(state, chosen)

    return wholes, to_step


def _same(chosen: DomainAction) -> DomainAction:
    return chosen


def steps_after(state: GameState, whole: DomainAction) -> int:
    """How many steps of ``whole`` follow the one ``first_step`` names."""

    if not presents_steps(state):
        return 0
    path = path_of(without_pick(state), whole)
    if path is None:
        return 0
    return len(path) - len(picked_rows(state)) - 1


def apply_whole(
    engine: UprisingRulesEngine,
    state: GameState,
    action: DomainAction | ChanceOutcome,
    *,
    legal_actions: tuple[DomainAction, ...] | None = None,
) -> Transition:
    """Apply ``action`` as the engine's steps: a whole action of
    ``engine.whole_actions`` as the steps that stand for it, a placement
    (``agent_turn``) as its card pick and space pick, and anything else --
    a legal row, a chance outcome, an illegal action -- as ``engine.apply``
    takes it (which raises ``IllegalActionError`` for an illegal one). The
    result is the last step's transition with every step's events.
    ``legal_actions``, the legal rows of ``state`` when the caller has them,
    are passed on to a single ``engine.apply`` (the whole actions' steps
    enumerate their own)."""

    if isinstance(action, ChanceOutcome):
        return engine.apply(state, action)
    if action.action_id == PLACEMENT_ACTION:
        placed = apply_placement(engine, state, action)
        return Transition(
            state=placed.state,
            action=action,
            events=placed.events,
            next_decision=engine.current_decision(placed.state),
        )
    if not presents_steps(state):
        return engine.apply(state, action, legal_actions=legal_actions)
    if action in engine.legal_actions(state, action.actor) or (
        action not in engine.whole_actions(state, action.actor)
    ):
        return engine.apply(state, action)
    events: list[GameEvent] = []
    while True:
        left = steps_after(state, action)
        result = engine.apply(state, first_step(state, action))
        events.extend(result.events)
        state = result.state
        if left == 0:
            return Transition(
                state=state,
                action=action,
                events=tuple(events),
                next_decision=result.next_decision,
            )


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
        # (seat, revision after the step, the placement or whole action).
        self._kept: tuple[int, int, DomainAction] | None = None

    def choose(
        self,
        state: GameState,
        player: int,
        legal_actions: tuple[DomainAction, ...],
        decide: Decide,
    ) -> DomainAction:
        """``decide``'s answer to the decision, an Agent-turn step's rows
        shown to it as placements and a waiting effect's as whole actions;
        the later steps of a placement or whole action it chose just before
        are answered without asking again."""

        kept, self._kept = self._kept, None
        if kept is not None and kept[:2] == (player, state.revision):
            remembered = self._remembered_step(state, player, kept[2])
            if remembered is not None and remembered in legal_actions:
                self._keep(state, player, kept[2], remembered)
                return remembered
        steps = placements_for_steps(state, player, legal_actions)
        if steps is None:
            return decide(legal_actions)
        shown, answer = steps
        chosen = decide(shown)
        step = answer(chosen)
        self._keep(state, player, chosen, step)
        return step

    def _remembered_step(
        self, state: GameState, player: int, chosen: DomainAction
    ) -> DomainAction | None:
        if chosen.action_id == PLACEMENT_ACTION:
            pick = agent_card_pick(state, player)
            if pick is None:
                return None
            remembered = agent_space_pick_actions(player, (chosen,), *pick)
            return remembered[0] if remembered else None
        if not presents_steps(state) or not picked_rows(state):
            return None
        try:
            return first_step(state, chosen)
        except (IndexError, KeyError, ValueError):
            return None

    def _keep(
        self, state: GameState, player: int, chosen: DomainAction, step: DomainAction
    ) -> None:
        if step.action_id == CARD_PICK_ACTION:
            self._kept = (player, state.revision + 1, chosen)
        elif step != chosen and steps_after(state, chosen) > 0:
            self._kept = (player, state.revision + 1, chosen)
