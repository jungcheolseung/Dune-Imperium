"""The ``reveal``, ``reveal_choice`` and ``acquisition_spy`` windows.

Reveal choices and the buy loop.

``HANDLERS`` maps each decision kind this module answers to its handler; a
kind missing here (or a handler returning None) falls back to the heuristic.
"""

from dune_imperium.agents.app_ai.windows.run import Handler

HANDLERS: dict[str, Handler] = {}
