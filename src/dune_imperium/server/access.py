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

import base64
import hashlib
import hmac
import re
import secrets
import time
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

# What an admin key may be (2026-11 security review, finding 3b): long enough
# that it cannot be guessed, and only characters that travel unchanged in the
# admin link's ``#admin=`` fragment and in JSON. ``new_token`` keys have 32;
# the server launcher stores keys by the same rule; 200 is the most
# ``POST /auth/admin`` accepts.
ADMIN_KEY_PATTERN: Final = re.compile(r"[A-Za-z0-9_-]{16,200}")
# How long the admin cookie a login hands out stays valid; the browser drops
# the cookie at the same age.
ADMIN_SESSION_SECONDS: Final = 30 * 24 * 60 * 60
_ADMIN_SESSION_VERSION: Final = "v1"


class AccessMode(StrEnum):
    """How much a play server trusts the clients that reach it."""

    OPEN = "open"
    REMOTE = "remote"


@dataclass(frozen=True, slots=True)
class Credentials:
    """What one request proves about its sender.

    ``seat_tokens`` are the seat tokens the client presented for the game
    it addresses (any number: one browser may hold several seats);
    ``admin_key`` is the host key it presented, if any, and
    ``admin_session`` the admin cookie a login handed out
    (``admin_session_token``). All are claims until the session layer has
    compared them with what it minted. The play server's HTTP layer only
    ever fills ``admin_session``: the key itself travels once, in the login.
    """

    seat_tokens: frozenset[str] = frozenset()
    admin_key: str | None = None
    admin_session: str | None = None


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
        # A lone surrogate (JSON ``"\ud800"``) cannot be UTF-8; kept as its
        # own bytes it simply matches nothing instead of failing the request.
        if secrets.compare_digest(target, token.encode("utf-8", "surrogatepass")):
            matched = True
    return matched


def admin_key_problem(key: str) -> str | None:
    """Say why ``key`` may not be a remote server's admin key, or ``None``."""

    if ADMIN_KEY_PATTERN.fullmatch(key):
        return None
    if len(key) < 16:
        return (
            f"the admin key is {len(key)} characters long; it needs at least "
            "16 (leave it out and the server makes one)"
        )
    if len(key) > 200:
        return "the admin key is longer than 200 characters"
    return (
        "the admin key may only use the letters A-Z and a-z, the digits 0-9, "
        "'-' and '_'"
    )


def _admin_session_mac(admin_key: str, issued: int, nonce: str) -> str:
    message = f"dune-admin-session.{_ADMIN_SESSION_VERSION}.{issued}.{nonce}"
    digest = hmac.new(
        admin_key.encode("utf-8", "surrogatepass"),
        # A forged token's nonce may be any text a cookie can carry.
        message.encode("utf-8", "surrogatepass"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def admin_session_token(admin_key: str, *, now: float | None = None) -> str:
    """Mint the value of an admin cookie: proof of the key, not the key.

    2026-11 security review, finding 3c: a cookie goes to every port of its
    host, so the key itself must not be one. The token is signed with the
    key (HMAC-SHA256 over its issue time and a random nonce), which keeps
    the server free of session state: a token stays valid across restarts
    for as long as the key does, for ``ADMIN_SESSION_SECONDS``, and changing
    the key revokes every one. The server launcher, which holds the key,
    mints its own instead of logging in.
    """

    issued = int(time.time() if now is None else now)
    nonce = secrets.token_urlsafe(16)
    mac = _admin_session_mac(admin_key, issued, nonce)
    return f"{_ADMIN_SESSION_VERSION}.{issued}.{nonce}.{mac}"


def admin_session_matches(
    admin_key: str, token: str, *, now: float | None = None
) -> bool:
    """Return whether ``token`` was minted with ``admin_key`` and is current."""

    parts = token.split(".")
    if len(parts) != 4 or parts[0] != _ADMIN_SESSION_VERSION:
        return False
    _, issued_text, nonce, mac = parts
    # ASCII digits only: ``str.isdigit`` also takes "²", which ``int`` refuses.
    if not (issued_text.isascii() and issued_text.isdigit()) or len(issued_text) > 12:
        return False
    issued = int(issued_text)
    current = time.time() if now is None else now
    # A minute of grace for a launcher's clock read a moment before ours.
    if not current - ADMIN_SESSION_SECONDS <= issued <= current + 60:
        return False
    expected = _admin_session_mac(admin_key, issued, nonce)
    return secrets.compare_digest(
        expected.encode("ascii"), mac.encode("utf-8", "surrogatepass")
    )
