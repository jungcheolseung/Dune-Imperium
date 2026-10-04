"""The pattern every window adapter follows, and helpers they share.

An app prompt is a list of *sources* (a card, an ability, a space…); the app
asks each source's ``Evaluate`` for its value and its answer, then
``MakeChoice`` picks among the sources. Our windows offer the same choices as
flat legal actions, so an adapter:

1. groups the legal actions into ``Source``s, one per app source, each with
   the app stage it belongs to (``Stage``);
2. answers the earliest *automatic* stage first, in app order, without
   comparing values: the app engine runs those without asking the AI
   (``spec/engine-order.md`` §3);
3. otherwise evaluates every prompt source (value + the legal action that
   realises the app's answer) and runs ``make_choice``; no positive source
   means the app's empty answer, i.e. the window's skip action (Reveal turn,
   End Turn, pass, decline); on a forced prompt with no positive source the
   app answers at random (``DefaultRandomChoice``).

``decide`` implements steps 2–3 for a list of sources.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import IntEnum

from dune_imperium.agents.app_ai.catalog import post_entity, spy_entity
from dune_imperium.agents.app_ai.choice import (
    Candidate,
    default_random_choice,
    make_choice,
)
from dune_imperium.agents.app_ai.windows.run import DecisionRun, arg
from dune_imperium.core.actions import DomainAction


class Stage(IntEnum):
    """Where the app engine resolves a source (lower runs first)."""

    # Agent turn (AgentTurnPhase states, spec/engine-order.md §3.1).
    COST_FIRST = 220  # Spice Refinery / Gather Support cost choice
    INFILTRATE = 240  # RecallSpyInfiltrate
    INTELLIGENCE = 260  # RecallSpyIntelligence (yes/no)
    SPACE = 400  # the space's own SpaceAbility (printed gains, no question)
    AGENT_BOX = 500  # the card's generic agent box (printed gains, no question)
    IMMEDIATE = 600  # deferred abilities that CanRunImmediately
    # Reveal turn (spec/engine-order.md §5).
    REVEAL_AUTO = 700  # reveal effects the engine resolves without asking
    # Everything the AI is actually asked to rank.
    PROMPT = 1000


@dataclass(frozen=True)
class Source:
    """One app prompt source realised by one or more of our legal actions.

    ``evaluate`` returns the app value and the legal action that realises
    the app's answer (None when the answer has no action here, e.g. the app
    would answer "nothing"). It is only called for PROMPT sources.
    ``order`` breaks the tie between automatic sources of the same stage
    (the app's list order); ``label`` is for traces.
    """

    label: str
    stage: Stage
    actions: tuple[DomainAction, ...]
    evaluate: Callable[[], tuple[float, DomainAction | None]] | None = None
    order: int = 0
    extra: dict[str, object] = field(default_factory=dict)


def decide(
    run: DecisionRun,
    sources: Sequence[Source],
    *,
    skip: DomainAction | None,
    forced: bool | None = None,
) -> DomainAction | None:
    """The app's answer among ``sources``; ``skip`` is the empty answer.

    Automatic stages go first (lowest stage, then ``order``; its first
    action). Otherwise prompt sources are evaluated and ranked with
    ``make_choice``. ``forced`` defaults to "no skip action is legal". With
    no source at all, return ``skip`` (None if there is none either, which
    makes the agent fall back).
    """

    automatic = [s for s in sources if s.stage < Stage.PROMPT and s.actions]
    if automatic:
        first = min(automatic, key=lambda s: (s.stage, s.order))
        return first.actions[0]
    candidates: list[Candidate] = []
    for source in sources:
        if source.stage != Stage.PROMPT or source.evaluate is None:
            continue
        value, action = source.evaluate()
        if action is None:
            continue
        candidates.append(Candidate(action, value, source.label))
    choice = make_choice(candidates, run.rng)
    if choice is not None:
        return choice.action
    if forced is None:
        forced = skip is None
    if not forced:
        return skip
    pool = [c.action for c in candidates] or [a for s in sources for a in s.actions]
    if not pool:
        return skip
    return default_random_choice(pool, run.rng)


# -- argument helpers ----------------------------------------------------------------


def str_arg(action: DomainAction, name: str) -> str | None:
    value = arg(action, name)
    return value if isinstance(value, str) else None


def int_arg(action: DomainAction, name: str) -> int | None:
    value = arg(action, name)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def with_arg(
    actions: Sequence[DomainAction], name: str, value: object
) -> DomainAction | None:
    """The first action whose argument ``name`` equals ``value``."""

    for action in actions:
        if arg(action, name) == value:
            return action
    return None


# -- spies (PlaceSpyEvaluator / RecallSpyEvaluator) ------------------------------------


def best_place_action(
    run: DecisionRun,
    actions: Sequence[DomainAction],
    post_arg: str = "post_id",
    *,
    unseen_network: bool = False,
) -> DomainAction | None:
    """``PlaceSpyEvaluator``: the legal placement on the app's best post."""

    posts = []
    for action in actions:
        post_id = str_arg(action, post_arg)
        if post_id is not None:
            posts.append(post_entity(post_id, run.ctx.seat))
    best, _value = run.profile.best_post(posts, unseen_network)
    return None if best is None else with_arg(actions, post_arg, best.ref)


def worst_recall_action(
    run: DecisionRun, actions: Sequence[DomainAction], post_arg: str = "post_id"
) -> DomainAction | None:
    """``RecallSpyEvaluator``: recall the own spy on the app's worst post."""

    spies = []
    for action in actions:
        post_id = str_arg(action, post_arg)
        if post_id is not None:
            spies.append(spy_entity(post_id, run.ctx.seat))
    spy, _value = run.profile.recall_spy(spies)
    return None if spy is None else with_arg(actions, post_arg, spy.ref)


def spy_answer(
    run: DecisionRun,
    place: Sequence[DomainAction],
    recall_first: Sequence[DomainAction],
    decline: DomainAction | None,
    post_arg: str = "post_id",
) -> DomainAction | None:
    """A spy placement window as the app answers it: it never declines.

    With a spy in supply the app places on its best post; with an empty
    supply it recalls the spy on its worst post first (then places). Only
    when neither is possible is the decline taken.
    """

    if place:
        return best_place_action(run, place, post_arg)
    if recall_first:
        return worst_recall_action(run, recall_first, post_arg)
    return decline
