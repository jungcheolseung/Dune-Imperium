"""Decision-window adapters: our engine's questions -> the app AI's answers."""

from dune_imperium.agents.app_ai.windows import (
    agent_effects,
    combat,
    intrigue,
    reveal,
    setup,
    turn,
    uprising,
)
from dune_imperium.agents.app_ai.windows.run import DecisionRun, Handler, Memory


def _merged() -> dict[str, Handler]:
    handlers: dict[str, Handler] = {}
    for module in (turn, agent_effects, reveal, combat, intrigue, uprising, setup):
        for kind, handler in module.HANDLERS.items():
            if kind in handlers:
                raise ValueError(f"two handlers for window {kind!r}")
            handlers[kind] = handler
    return handlers


def handler_for(kind: str | None) -> Handler | None:
    """The handler of decision kind ``kind`` (None: not mirrored yet)."""

    if kind is None:
        return None
    return _merged().get(kind)


__all__ = ["DecisionRun", "Handler", "Memory", "handler_for"]
