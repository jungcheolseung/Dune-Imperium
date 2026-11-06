"""Local web-UI game server built on the engine's public API."""

from dune_imperium.server.access import AccessMode, Credentials
from dune_imperium.server.sessions import (
    AdminAccessError,
    GameSessionManager,
    SeatAccessError,
    SeatTakenError,
    SessionError,
    StaleRevisionError,
    UnknownGameError,
)

__all__ = [
    "AccessMode",
    "AdminAccessError",
    "Credentials",
    "GameSessionManager",
    "SeatAccessError",
    "SeatTakenError",
    "SessionError",
    "StaleRevisionError",
    "UnknownGameError",
]
