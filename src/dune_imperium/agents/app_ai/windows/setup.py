"""Setup windows: the leader draft.

``leader_draft`` (``leader_draft=True``, OQ-007) has the shape of the app's
Draft mode: six shared leaders, picks in reverse seat order, leaders already
taken disabled (spec/epic-goto11-promo-draft.md §5). The app AI does not
evaluate leaders: ``ChooseStartingLeaderEvaluator::Evaluate @0x492f2e0``
takes the first enabled ``PreferredLeaders`` entry (never set in lobby games)
or else ``CanisRandom.Element`` over the enabled options (§5.5). So app_ai
answers ``pick_leader`` with a uniform pick among the legal ones, from its
seeded RNG (plan §4 rule 9). ``finish_leader_draft`` is offered alone, so the
agent takes it without a handler.

``HANDLERS`` maps each decision kind this module answers to its handler.
"""

from dune_imperium.agents.app_ai.choice import default_random_choice
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler
from dune_imperium.core.actions import DomainAction


def leader_draft(run: DecisionRun) -> DomainAction | None:
    """``ChooseStartingLeaderEvaluator``: a uniform pick of the open leaders."""

    picks = run.by_id("pick_leader")
    if not picks:
        return run.first("finish_leader_draft")
    return default_random_choice(picks, run.rng)


HANDLERS: dict[str, Handler] = {
    "leader_draft": leader_draft,
}
