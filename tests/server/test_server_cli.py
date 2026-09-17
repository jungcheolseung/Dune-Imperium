"""Tests for the play-server CLI's access-mode resolution (M14 slice 1).

No server is started here: these exercise only the pure argument-resolution
helpers (``docs/multiplayer-design.md`` sections 4.2-4.4, 5, 6).
"""

import pytest

from dune_imperium.cli.server import (
    ADMIN_KEY_ENVIRONMENT,
    _build_parser,
    admin_link,
    is_loopback_host,
    main,
    resolve_access,
)
from dune_imperium.server.access import AccessMode


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("localhost", True),
        ("::1", True),
        ("0.0.0.0", False),
        ("100.101.102.103", False),
        ("192.168.0.5", False),
        ("example.com", False),
    ],
)
def test_is_loopback_host(host: str, expected: bool) -> None:
    assert is_loopback_host(host) is expected


# --- resolve_access ----------------------------------------------------


def test_default_arguments_resolve_to_open_access() -> None:
    arguments = _build_parser().parse_args([])

    assert resolve_access(arguments, {}) == (AccessMode.OPEN, None)


def test_a_non_loopback_host_without_remote_is_refused() -> None:
    arguments = _build_parser().parse_args(["--host", "0.0.0.0"])

    with pytest.raises(ValueError, match="--remote"):
        resolve_access(arguments, {})


def test_an_admin_key_without_remote_is_refused() -> None:
    arguments = _build_parser().parse_args(["--admin-key", "x"])

    with pytest.raises(ValueError, match="--remote"):
        resolve_access(arguments, {})


def test_remote_with_an_explicit_admin_key() -> None:
    arguments = _build_parser().parse_args(["--remote", "--admin-key", "x"])

    assert resolve_access(arguments, {}) == (AccessMode.REMOTE, "x")


def test_remote_falls_back_to_the_environment_key() -> None:
    arguments = _build_parser().parse_args(["--remote"])

    access, key = resolve_access(arguments, {ADMIN_KEY_ENVIRONMENT: "env-key"})

    assert (access, key) == (AccessMode.REMOTE, "env-key")


def test_remote_without_a_key_anywhere_mints_a_fresh_random_key() -> None:
    arguments = _build_parser().parse_args(["--remote"])

    _, first = resolve_access(arguments, {})
    _, second = resolve_access(arguments, {})

    assert first and second and first != second


def test_remote_is_allowed_on_a_non_loopback_host() -> None:
    arguments = _build_parser().parse_args(["--remote", "--host", "100.101.102.103"])

    access, key = resolve_access(arguments, {})

    assert access is AccessMode.REMOTE
    assert key


def test_an_explicit_admin_key_wins_over_the_environment() -> None:
    arguments = _build_parser().parse_args(["--remote", "--admin-key", "y"])

    access, key = resolve_access(arguments, {ADMIN_KEY_ENVIRONMENT: "env-key"})

    assert (access, key) == (AccessMode.REMOTE, "y")


# --- admin_link ----------------------------------------------------------


def test_admin_link_swaps_a_wildcard_bind_for_its_loopback_address() -> None:
    assert admin_link("0.0.0.0", 8000, "k") == "http://127.0.0.1:8000/#admin=k"
    assert admin_link("::", 8000, "k") == "http://[::1]:8000/#admin=k"


def test_admin_link_names_the_address_the_server_listens_on() -> None:
    # Bound to one address the server answers nowhere else: 127.0.0.1 would
    # be dead for a Tailscale IP, and equally for an IPv6-only ``::1``.
    assert admin_link("127.0.0.1", 8000, "k") == "http://127.0.0.1:8000/#admin=k"
    assert admin_link("localhost", 8000, "k") == "http://localhost:8000/#admin=k"
    assert (
        admin_link("100.101.102.103", 8000, "k")
        == "http://100.101.102.103:8000/#admin=k"
    )


def test_admin_link_brackets_an_ipv6_host() -> None:
    assert admin_link("::1", 9000, "k") == "http://[::1]:9000/#admin=k"
    assert admin_link("2001:db8::1", 8000, "k") == "http://[2001:db8::1]:8000/#admin=k"


# --- main ------------------------------------------------------------------


def test_main_refuses_a_non_loopback_host_without_remote() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--host", "0.0.0.0"])

    assert excinfo.value.code == 2
