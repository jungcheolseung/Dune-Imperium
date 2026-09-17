"""CLI launching the local play server (requires the ``ui`` extra)."""

import argparse
import ipaddress
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from dune_imperium.server.access import AccessMode, new_token

ADMIN_KEY_ENVIRONMENT = "DUNE_IMPERIUM_ADMIN_KEY"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dune-imperium-server",
        description="Serve the local Dune: Imperium - Uprising play API.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "bind address (default: 127.0.0.1, local only); any other "
            "address needs --remote"
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="TCP port (default: 8000)",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help=(
            "remote multiplayer access (docs/multiplayer-design.md): players "
            "claim their seats, only the admin link printed at startup may "
            "create, save, load or delete games, and the game seed stays "
            "hidden until the game ends"
        ),
    )
    parser.add_argument(
        "--admin-key",
        default=None,
        help=(
            "admin key for --remote (default: the DUNE_IMPERIUM_ADMIN_KEY "
            "environment variable, else a fresh random key per start)"
        ),
    )
    parser.add_argument(
        "--saves-dir",
        type=Path,
        default=None,
        help="save-file directory (default: ~/.dune-imperium/saves)",
    )
    parser.add_argument(
        "--card-images-dir",
        type=Path,
        default=None,
        help=(
            "local card-image checkout with manifest.json (default: "
            "DUNE_IMPERIUM_CARD_IMAGE_DIR or the repository's assets/cards)"
        ),
    )
    return parser


def is_loopback_host(host: str) -> bool:
    """Return whether a bind address only accepts this machine's clients."""

    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def resolve_access(
    arguments: argparse.Namespace, environment: Mapping[str, str]
) -> tuple[AccessMode, str | None]:
    """Decide the access mode and admin key, refusing unsafe combinations.

    An open server trusts every client that reaches it, so it may only bind
    a loopback address: exposing it would let anyone on the network read
    every hand and delete every game. Tunnels and ``tailscale serve``
    connect over loopback, which is why the mode is never inferred from the
    bind address (or from a client address) and has to be asked for.
    """

    if not arguments.remote:
        if arguments.admin_key is not None:
            raise ValueError("--admin-key only applies together with --remote")
        if not is_loopback_host(arguments.host):
            raise ValueError(
                f"--host {arguments.host} is reachable from the network; "
                "add --remote so seats and host operations are protected"
            )
        return AccessMode.OPEN, None
    key = arguments.admin_key or environment.get(ADMIN_KEY_ENVIRONMENT) or new_token()
    return AccessMode.REMOTE, key


def admin_link(host: str, port: int, admin_key: str) -> str:
    """Return the URL the host opens to become the admin.

    It names an address the server really listens on: bound to one
    address (a Tailscale IP, say, or ``::1``), 127.0.0.1 would not answer.
    Only the wildcard binds are swapped for their loopback address.
    """

    if host == "0.0.0.0":
        address = "127.0.0.1"
    elif host == "::":
        address = "[::1]"
    elif ":" in host:
        address = f"[{host}]"
    else:
        address = host
    return f"http://{address}:{port}/#admin={admin_key}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    arguments = parser.parse_args(argv)
    try:
        access, admin_key = resolve_access(arguments, os.environ)
    except ValueError as error:
        parser.error(str(error))
    # Imported lazily so the CLI module stays importable without the extra.
    import uvicorn

    from dune_imperium.server.app import create_app
    from dune_imperium.server.sessions import GameSessionManager

    if admin_key is not None:
        print("Remote multiplayer access is on. Host admin link (keep it private):")
        print(f"  {admin_link(arguments.host, arguments.port, admin_key)}")
    uvicorn.run(
        create_app(
            manager=GameSessionManager(access=access, admin_key=admin_key),
            saves_dir=arguments.saves_dir,
            card_images_dir=arguments.card_images_dir,
        ),
        host=arguments.host,
        port=arguments.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
