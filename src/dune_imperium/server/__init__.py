"""Local web-UI game server built on the engine's public API."""

from dune_imperium.server.sessions import (
    GameSessionManager,
    SeatAccessError,
    SessionError,
    StaleRevisionError,
    UnknownGameError,
)

__all__ = [
    "GameSessionManager",
    "SeatAccessError",
    "SessionError",
    "StaleRevisionError",
    "UnknownGameError",
]
