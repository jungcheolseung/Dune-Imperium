"""Intrigue follow-up windows: ``intrigue_choice`` and ``intrigue_effects``.

``HANDLERS`` maps each decision kind this module answers to its handler; a
kind missing here (or a handler returning None) falls back to the heuristic.
"""

from collections.abc import Sequence

from dune_imperium.agents.app_ai.windows.common import Source
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler
from dune_imperium.core.actions import DomainAction

HANDLERS: dict[str, Handler] = {}


def intrigue_play_sources(
    run: DecisionRun, actions: Sequence[DomainAction], *, combat: bool
) -> list[Source]:
    """One PROMPT ``Source`` per intrigue card offered by ``play_intrigue``.

    Shared by every window that offers intrigue plays (``turn``,
    ``agent_effects``, ``reveal`` for Plots; ``combat_intrigue`` with
    ``combat=True``). Each source evaluates the card's ability named by
    ``abilities.intrigue.ability_for_prompt(card, combat)`` on a request built
    from the current state (encoding in ``abilities/intrigue.py``), maps the
    app's answer to the matching ``play_intrigue(card_id, option)`` action and
    records the answer in ``run.memory.intents[("intrigue", card_id)]`` so the
    follow-up ``intrigue_choice`` / ``intrigue_effects`` windows can replay it.
    """

    raise NotImplementedError
