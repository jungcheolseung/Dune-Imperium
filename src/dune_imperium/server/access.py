"""Access control vocabulary for the play server: open and remote modes.

The local play server (M11) trusts every client: whoever reaches it may
read and act for any human seat. Remote multiplayer (M14,
``docs/multiplayer-design.md``) cannot, so a client has to *prove* which
seats it holds. This module is the framework-neutral vocabulary of that
proof: the HTTP layer turns request cookies into ``Credentials`` and the
session layer judges them, which keeps every visibility judgment in one
place.

- ``AccessMode.OPEN`` (the default): today's behaviour; credentials are
  ignored, every human seat is readable, and nothing needs an admin.
- ``AccessMode.REMOTE``: a human seat is read or acted for only with the
  token minted when it was claimed, and host operations (creating, saving,
  loading and deleting games, releasing seats) need the admin key.
"""

import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class AccessMode(StrEnum):
    """How much a play server trusts the clients that reach it."""

    OPEN = "open"
    REMOTE = "remote"


@dataclass(frozen=True, slots=True)
class Credentials:
    """What one request proves about its sender.

    ``seat_tokens`` are the seat tokens the client presented for the game
    it addresses (any number: one browser may hold several seats);
    ``admin_key`` is the host key it presented, if any. Both are claims
    until the session layer has compared them with what it minted.
    """

    seat_tokens: frozenset[str] = frozenset()
    admin_key: str | None = None


ANONYMOUS: Final = Credentials()


def new_token() -> str:
    """Mint one unguessable seat token or admin key (192 random bits)."""

    return secrets.token_urlsafe(24)


def token_matches(expected: str, presented: Iterable[str]) -> bool:
    """Return whether ``expected`` is among the presented tokens.

    Every comparison is constant-time, and bytes are compared because
    ``compare_digest`` rejects non-ASCII text, which a cookie may carry.
    """

    target = expected.encode("utf-8")
    matched = False
    for token in presented:
        if secrets.compare_digest(target, token.encode("utf-8")):
            matched = True
    return matched
