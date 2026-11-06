"""Setup windows: the leader draft and the Baron's Masterstroke Factions.

``leader_draft`` (``leader_draft=True``, OQ-007) has the shape of the app's
Draft mode: six shared leaders, picks in reverse seat order, leaders already
taken disabled (spec/epic-goto11-promo-draft.md §5). The app AI does not
evaluate leaders: ``ChooseStartingLeaderEvaluator::Evaluate @0x492f2e0``
takes the first enabled ``PreferredLeaders`` entry (never set in lobby games)
or else ``CanisRandom.Element`` over the enabled options (§5.5). So app_ai
answers ``pick_leader`` with a uniform pick among the legal ones, from its
seeded RNG (plan §4 rule 9). ``finish_leader_draft`` is offered alone, so the
agent takes it without a handler.

``masterstroke_setup`` (the original game's Baron Harkonnen): the app asks
his two secret Factions in one prompt, ``MasterstrokeAbility1::Evaluate``
(the four tracks shuffled, the first two); our engine asks them one at a
time, so the second is the stored rest of that answer (plan §4 rule 6).

``HANDLERS`` maps each decision kind this module answers to its handler.
"""

from dune_imperium.agents.app_ai.abilities.base import Request, TargetInfo
from dune_imperium.agents.app_ai.abilities.original_leaders import (
    MasterstrokeAbility1,
)
from dune_imperium.agents.app_ai.catalog import leader_entity, track_entity
from dune_imperium.agents.app_ai.choice import default_random_choice
from dune_imperium.agents.app_ai.context import FACTIONS
from dune_imperium.agents.app_ai.windows.common import str_arg, with_arg
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler
from dune_imperium.core.actions import DomainAction

#: ``Memory.intents`` key of the second Masterstroke Faction:
#: ``(MASTERSTROKE_INTENT, seat)`` -> faction.
MASTERSTROKE_INTENT = "masterstroke_second_faction"


def leader_draft(run: DecisionRun) -> DomainAction | None:
    """``ChooseStartingLeaderEvaluator``: a uniform pick of the open leaders."""

    picks = run.by_id("pick_leader")
    if not picks:
        return run.first("finish_leader_draft")
    return default_random_choice(picks, run.rng)


def masterstroke_setup(run: DecisionRun) -> DomainAction | None:
    """The Baron's secret Factions, one ``choose_masterstroke_faction`` at a
    time: the first of ``MasterstrokeAbility1``'s two (its shuffled track
    order), then the stored second."""

    picks = run.by_id("choose_masterstroke_faction")
    if not picks:
        return None
    key = (MASTERSTROKE_INTENT, run.ctx.seat)
    stored = run.memory.intents.pop(key, None)
    if isinstance(stored, str):
        second = with_arg(picks, "faction", stored)
        if second is not None:
            return second
    offered = {str_arg(a, "faction") for a in picks}
    tracks = tuple(track_entity(f) for f in FACTIONS if f in offered)
    leader = run.ctx.me.leader_id or ""
    ability = MasterstrokeAbility1(leader_entity(leader))
    answer = ability.evaluate(run.profile, Request((TargetInfo(entities=tracks),)))
    chosen = answer.response[0] if answer.response else ()
    if not chosen:
        return default_random_choice(picks, run.rng)
    if len(chosen) > 1 and isinstance(chosen[1], str):
        run.memory.intents[key] = chosen[1]
    return with_arg(picks, "faction", chosen[0]) or picks[0]


HANDLERS: dict[str, Handler] = {
    "leader_draft": leader_draft,
    "masterstroke_setup": masterstroke_setup,
}
