"""Combat windows.

``combat_intrigue``, ``combat_reward_*``, ``control_defense``,
``endgame_intrigue``.

``HANDLERS`` maps each decision kind this module answers to its handler; a
kind missing here (or a handler returning None) falls back to the heuristic.
"""

from dune_imperium.agents.app_ai.windows.run import Handler

HANDLERS: dict[str, Handler] = {}
