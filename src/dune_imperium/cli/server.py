"""CLI launching the local play server (requires the ``ui`` extra)."""

import argparse
import ipaddress
import os
import socket
import sys
from collections.abc import Mapping, Sequence
from importlib.util import find_spec
from pathlib import Path
from types import FrameType

from dune_imperium.paths import SAVES_DIR, SEARCH_CHECKPOINT
from dune_imperium.server.access import AccessMode, new_token

ADMIN_KEY_ENVIRONMENT = "DUNE_IMPERIUM_ADMIN_KEY"
SEARCH_CHECKPOINT_ENVIRONMENT = "DUNE_IMPERIUM_SEARCH_CHECKPOINT"
# Where the search AI's network is looked for when nothing else names one:
# ``checkpoints/play/search.pt`` in the project checkout, usually a symlink
# to a weights-only copy beside it (``dune_imperium.paths``).
DEFAULT_SEARCH_CHECKPOINT = SEARCH_CHECKPOINT
_GRACEFUL_SHUTDOWN_SECONDS = 3


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
        "--public-url",
        default=None,
        help=(
            "with --remote: the address the other players reach this server "
            "at, e.g. http://100.101.102.103:8000; the host's page builds the "
            "room link from it (default: the address the host's browser uses)"
        ),
    )
    parser.add_argument(
        "--no-autosave",
        action="store_true",
        help=(
            "with --remote: do not keep the per-game autosave that is "
            "otherwise replaced in the saves directory whenever a turn "
            "passes on (a crashed server then loses the whole game)"
        ),
    )
    parser.add_argument(
        "--saves-dir",
        type=Path,
        default=None,
        help=f"save-file directory (default: {SAVES_DIR})",
    )
    parser.add_argument(
        "--search-checkpoint",
        default=None,
        help=(
            "trained policy file behind the search AI seat the browser "
            "offers (needs the train extra; default: the "
            f"{SEARCH_CHECKPOINT_ENVIRONMENT} environment variable, else "
            f"{SEARCH_CHECKPOINT} if it exists); a symlink is resolved "
            "at startup, so saves name the real file"
        ),
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


def resolve_public_url(arguments: argparse.Namespace) -> str | None:
    """Return the room-link base the host asked for, without a trailing slash."""

    url: str | None = arguments.public_url
    if url is None:
        return None
    if not arguments.remote:
        raise ValueError("--public-url only applies together with --remote")
    if not url.startswith(("http://", "https://")):
        raise ValueError("--public-url must start with http:// or https://")
    return url.rstrip("/")


def resolve_autosave(arguments: argparse.Namespace) -> bool:
    """Return whether games are autosaved: a remote server's default."""

    if arguments.no_autosave and not arguments.remote:
        raise ValueError("--no-autosave only applies together with --remote")
    return bool(arguments.remote and not arguments.no_autosave)


def resolve_search_checkpoint(
    arguments: argparse.Namespace, environment: Mapping[str, str]
) -> tuple[Path | None, str]:
    """Return the search AI's network file, or ``None``, and the startup line.

    The flag wins over the environment variable, which wins over
    ``checkpoints/play/search.pt`` in the project checkout
    (``DEFAULT_SEARCH_CHECKPOINT``). The path is resolved once, here: saves
    record the file a symlink named when the server started, so pointing
    the link at a newer checkpoint never changes an older save's network.
    The seat is offered only when that file exists and torch (the ``train``
    extra) is installed; the line says which, for the console.
    """

    named: str | None = arguments.search_checkpoint or environment.get(
        SEARCH_CHECKPOINT_ENVIRONMENT
    )
    if named:
        candidate = Path(named).expanduser().resolve()
        if not candidate.is_file():
            return None, f"search AI: off (no file at {candidate})"
    else:
        default = DEFAULT_SEARCH_CHECKPOINT
        if not default.is_file():
            return None, (
                "search AI: off (no checkpoint; --search-checkpoint or "
                f"{default})"
            )
        candidate = default.resolve()
    if find_spec("torch") is None:
        return None, "search AI: off (torch not installed: uv sync --extra train)"
    return candidate, f"search AI: {candidate}"


def bind_problem(host: str, port: int) -> str | None:
    """Say why the server could not listen on ``host:port``, or ``None``.

    Asked before anything is printed: uvicorn reports a failed bind among
    its own log lines and the process would already have shown an admin
    link for a server that never came up. The usual cause on a host's
    machine is a Tailscale address while Tailscale is not connected.
    """

    try:
        candidates = socket.getaddrinfo(
            host, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE
        )
    except OSError as error:
        return f"cannot resolve --host {host}: {error}"
    problem = f"no usable address for --host {host}"
    for family, kind, protocol, _name, address in candidates:
        try:
            with socket.socket(family, kind, protocol) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(address)
            return None
        except OSError as error:
            problem = f"cannot listen on {host}:{port}: {error.strerror or error}"
    if not is_loopback_host(host) and host not in ("0.0.0.0", "::"):
        problem += (
            " (is that address up on this machine? a Tailscale address only "
            "exists while Tailscale is connected)"
        )
    return problem


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
        public_url = resolve_public_url(arguments)
        autosave = resolve_autosave(arguments)
    except ValueError as error:
        parser.error(str(error))
    problem = bind_problem(arguments.host, arguments.port)
    if problem is not None:
        print(f"dune-imperium-server: {problem}", file=sys.stderr)
        return 1
    # Imported lazily so the CLI module stays importable without the extra.
    import uvicorn

    from dune_imperium.server.app import create_app
    from dune_imperium.server.persistence import default_saves_directory
    from dune_imperium.server.sessions import GameSessionManager

    search_checkpoint, search_line = resolve_search_checkpoint(arguments, os.environ)
    if admin_key is not None:
        print("Remote multiplayer access is on. Host admin link (keep it private):")
        print(f"  {admin_link(arguments.host, arguments.port, admin_key)}", flush=True)
        saves_dir = arguments.saves_dir or default_saves_directory()
        if autosave:
            print(f"Autosave is on: every game keeps one current save in {saves_dir}")
            print(
                "  (after a crash: restart, open the admin link, load that save "
                "and share the new room link)"
            )
        else:
            print("Autosave is off: a game lives only as long as this process.")
    print(search_line, flush=True)
    app = create_app(
        manager=GameSessionManager(
            access=access,
            admin_key=admin_key,
            search_checkpoint=search_checkpoint,
        ),
        saves_dir=arguments.saves_dir,
        card_images_dir=arguments.card_images_dir,
        public_url=public_url,
        autosave=autosave,
    )
    hub = app.state.doorbell_hub

    class PlayServer(uvicorn.Server):
        """End the doorbell streams as soon as the server is asked to stop.

        An event stream never ends by itself and uvicorn waits for open
        responses before it exits, so Ctrl+C would otherwise hang for as
        long as a browser tab stays open.
        """

        def handle_exit(self, sig: int, frame: FrameType | None) -> None:
            hub.close()
            super().handle_exit(sig, frame)

    server = PlayServer(
        uvicorn.Config(
            app,
            host=arguments.host,
            port=arguments.port,
            # The backstop, should a stream fail to end on the signal.
            timeout_graceful_shutdown=_GRACEFUL_SHUTDOWN_SECONDS,
        )
    )
    try:
        server.run()
    except KeyboardInterrupt:
        # uvicorn re-raises the signal it shut down on; ``uvicorn.run``
        # swallows it the same way.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
