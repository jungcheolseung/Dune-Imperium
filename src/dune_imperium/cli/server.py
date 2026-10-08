"""CLI launching the local play server (requires the ``ui`` extra)."""

import argparse
import contextlib
import errno
import ipaddress
import os
import socket
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from importlib.util import find_spec
from pathlib import Path
from types import FrameType

from dune_imperium.paths import SAVES_DIR, SEARCH_CHECKPOINT
from dune_imperium.server.access import AccessMode, new_token
from dune_imperium.server.pacing import AI_PACES

ADMIN_KEY_ENVIRONMENT = "DUNE_IMPERIUM_ADMIN_KEY"
SEARCH_CHECKPOINT_ENVIRONMENT = "DUNE_IMPERIUM_SEARCH_CHECKPOINT"
# Where the search AI's network is looked for when nothing else names one:
# ``checkpoints/play/search.pt`` in the project checkout, usually a symlink
# to a weights-only copy beside it (``dune_imperium.paths``).
DEFAULT_SEARCH_CHECKPOINT = SEARCH_CHECKPOINT
_GRACEFUL_SHUTDOWN_SECONDS = 3
# How much of standard input the --exit-when-stdin-closes watch reads at a
# time; nothing is expected on it, so this only bounds a stray writer.
_STDIN_CHUNK = 64 * 1024


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
        "--ai-pace",
        choices=AI_PACES,
        default="normal",
        help=(
            "how the AI seats of a new game, and of a loaded save that "
            "records none, pace their answers: 'normal' gives the tables the "
            "time to show each AI turn and card, 'fast' 0.6 of it, "
            "'instant' answers inside the request (default: normal; the "
            "setup screen can choose another per game)"
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
    parser.add_argument(
        "--exit-when-stdin-closes",
        action="store_true",
        help=(
            "stop the server, as gracefully as Ctrl+C, once its standard "
            "input reaches end of file: a launcher keeps the write end of a "
            "pipe, so closing it, or the launcher dying, ends the server "
            "(docs/server-launcher-plan.md). Meant for a launcher's pipe: "
            "from /dev/null the server stops at once, on a terminal it stops "
            "at Ctrl+D, and as a background job of an interactive shell its "
            "first read of the terminal suspends it"
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


def bind_problem(
    host: str, port: int, *, platform: str = sys.platform
) -> str | None:
    """Say why the server could not listen on ``host:port``, or ``None``.

    Asked before anything is printed: uvicorn reports a failed bind among
    its own log lines and the process would already have shown an admin
    link for a server that never came up. The usual cause on a host's
    machine is a Tailscale address while Tailscale is not connected.

    The probe binds the way uvicorn's own bind does, which is asyncio's
    ``create_server``: every address ``host`` resolves to, all held at once
    (``localhost`` is 127.0.0.1 and ::1, and a server already on either
    stops it); ``IPV6_V6ONLY`` on IPv6; an address the machine lacks
    (EADDRNOTAVAIL) skipped unless none is left; and ``SO_REUSEADDR`` on
    POSIX only (so a port lingering in TIME_WAIT is no problem there),
    never on Windows, where that option would let the probe bind a port
    another socket is listening on and so miss the busy port.
    """

    try:
        candidates = socket.getaddrinfo(
            host, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE
        )
    except OSError as error:
        return f"cannot resolve --host {host}: {error}"
    # asyncio: reuse_address = os.name == "posix" and sys.platform != "cygwin"
    reuse = platform not in ("win32", "cygwin")
    failure: str | None = None
    unavailable: str | None = None
    bound = 0
    with contextlib.ExitStack() as held:
        for family, kind, protocol, _name, address in dict.fromkeys(candidates):
            try:
                probe = held.enter_context(socket.socket(family, kind, protocol))
            except OSError:
                continue  # a family the system cannot open; asyncio skips it
            try:
                if reuse:
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if family == socket.AF_INET6 and hasattr(socket, "IPPROTO_IPV6"):
                    probe.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                probe.bind(address)
                bound += 1
            except OSError as error:
                message = f"cannot listen on {host}:{port}: {error.strerror or error}"
                if error.errno == errno.EADDRNOTAVAIL:
                    unavailable = message
                    continue
                failure = message
                break
    if failure is not None:
        return failure
    if bound:
        return None
    problem = unavailable or f"no usable address for --host {host}"
    if not is_loopback_host(host) and host not in ("0.0.0.0", "::"):
        problem += (
            " (is that address up on this machine? a Tailscale address only "
            "exists while Tailscale is connected)"
        )
    return problem


def stop_when_stream_ends(descriptor: int, stop: Callable[[], None]) -> None:
    """Read file ``descriptor`` to its end, then call ``stop``.

    The body of the --exit-when-stdin-closes watch thread. A launcher holds
    the write end of the server's standard input; it closes it to stop the
    server, and the operating system closes it when the launcher dies, so
    either way the read ends here: a pipe whose writers are all gone reads
    as end of file on POSIX and on Windows alike (the C runtime turns the
    broken pipe into an empty read).

    It reads the descriptor itself, not ``sys.stdin.buffer``: a thread
    blocked in ``BufferedReader.read`` holds that buffer's lock, and when
    the process ends some other way (Ctrl+C with the pipe still open, a
    failed start) the interpreter's shutdown waits a second for the lock
    and then aborts ("Fatal Python error: _enter_buffered_busy", code -6).

    A read that fails means standard input was never readable (descriptor
    0 opened for writing only, as GNU nohup leaves a terminal): the watch
    cannot work, which is said on standard error, and the server stops.
    """

    try:
        while os.read(descriptor, _STDIN_CHUNK):
            pass
    except OSError as error:
        print(
            f"dune-imperium-server: cannot read standard input ({error}); "
            "--exit-when-stdin-closes stops the server",
            file=sys.stderr,
            flush=True,
        )
    stop()


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
            default_ai_pace=arguments.ai_pace,
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

        def shut_down(self) -> None:
            """Begin the same graceful shutdown as a signal, from any thread.

            Not through ``handle_exit``: uvicorn records the signal it was
            handed and raises it again once the server has stopped, which
            would end the process by that signal (code -15 for SIGTERM)
            instead of returning 0. The main loop polls ``should_exit``
            every 0.1 s, and ``hub.close`` is safe from any thread.
            """

            hub.close()
            self.should_exit = True

    server = PlayServer(
        uvicorn.Config(
            app,
            host=arguments.host,
            port=arguments.port,
            # The backstop, should a stream fail to end on the signal.
            timeout_graceful_shutdown=_GRACEFUL_SHUTDOWN_SECONDS,
        )
    )
    if arguments.exit_when_stdin_closes:
        try:
            descriptor = sys.stdin.fileno() if sys.stdin is not None else None
        except (OSError, ValueError):  # io.UnsupportedOperation is both
            descriptor = None
        if descriptor is None:
            # pythonw and some service managers start a process without one.
            print(
                "dune-imperium-server: no standard input to watch; "
                "--exit-when-stdin-closes is ignored",
                file=sys.stderr,
                flush=True,
            )
        else:
            threading.Thread(
                target=stop_when_stream_ends,
                args=(descriptor, server.shut_down),
                name="stdin-watch",
                daemon=True,
            ).start()
    try:
        server.run()
    except KeyboardInterrupt:
        # uvicorn re-raises the signal it shut down on; ``uvicorn.run``
        # swallows it the same way.
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
