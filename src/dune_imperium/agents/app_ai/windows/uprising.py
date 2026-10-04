"""Spy, contract and misc windows.

``spy_placement``, ``contract_market``, ``contract_reward_*``,
``opponent_card_discard``, ``long_live_fighters``.

``HANDLERS`` maps each decision kind this module answers to its handler; a
kind missing here (or a handler returning None) falls back to the heuristic.
"""

from dune_imperium.agents.app_ai.windows.run import Handler

HANDLERS: dict[str, Handler] = {}
