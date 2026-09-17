"""Rehearsal for a real remote game (M14 slice 6): what a friend's browser gets.

Run it with the host's Tailscale address so the origin is the real one, a
plain-HTTP address that is not a secure context:

    E2E_HOST=100.x.y.z python rehearsal.py

1. what only shows on such an origin: no secure context, so the copy button
   must fall back to a selected field, the turn tone must not throw, and the
   seat cookie must be HttpOnly, SameSite=Strict, scoped to the game and NOT
   `Secure` (a Secure cookie is dropped on plain HTTP);
2. what the link costs: the guest's browser is throttled (Chrome DevTools
   network emulation) to a home line and to a poor one, and the first visit,
   a reload, and the step-to-step delay are measured on an all-expansions
   game. Numbers are printed, only hard failures fail.
"""

from __future__ import annotations

import sys
import time

from common import HOST, Check, chrome, open_context, server
from remote import KEY, converge

check = Check()

# (label, one-way latency ms, bytes per second down, up)
PROFILES = (
    ("home line: 100 Mbit/s, 20 ms RTT", 10, 12_500_000, 12_500_000),
    ("poor line: 10 Mbit/s, 120 ms RTT", 60, 1_250_000, 1_250_000),
)


def create_full_game(host, base: str) -> str:
    host.goto(f"{base}/#admin={KEY}")
    host.wait_for_selector("#setup-screen:not([hidden])")
    host.select_option("#seat-selects select[data-seat='1']", "human")
    for option in (
        "opt-choam",
        "opt-promo",
        "opt-bloodlines",
        "opt-tech",
        "opt-immortality",
    ):
        host.check(f"#{option}")
    host.click("#create-game")
    host.wait_for_selector("#lobby-screen:not([hidden])")
    game_id = host.evaluate("state.gameId")
    host.fill("#lobby-name", "호스트")
    host.click("#lobby-seats li[data-seat='0'] button")
    host.wait_for_selector("#game-screen:not([hidden])")
    return game_id


def throttle(context, page, latency_ms: int, down: int, up: int):
    session = context.new_cdp_session(page)
    session.send("Network.enable")
    session.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "latency": latency_ms,
            "downloadThroughput": down,
            "uploadThroughput": up,
        },
    )
    return session


def transferred(page) -> tuple[float, int]:
    """Megabytes over the wire and request count, by the Resource Timing API."""

    entries = page.evaluate(
        "performance.getEntriesByType('resource').map((e) => e.transferSize)"
    )
    return sum(entries) / 1_048_576, len(entries)


def images_done_js() -> str:
    """Every image the page asked for has arrived (off-screen lazy ones have
    not been asked for yet and do not count); the board scans are the bulk."""

    return (
        "[...document.images].filter((i) => i.src && i.loading !== 'lazy'"
        " && !i.complete).length === 0"
        " && [...document.images].some((i) => i.src.includes('/board-image')"
        " && i.complete && i.naturalWidth > 0)"
    )


def visit(browser, base: str, game_id: str, profile, name: str):
    label, latency, down, up = profile
    context, page, recorder = open_context(browser, name)
    throttle(context, page, latency, down, up)
    started = time.monotonic()
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_selector("#lobby-screen:not([hidden])", timeout=120_000)
    lobby_at = time.monotonic() - started
    page.fill("#lobby-name", name)
    page.click("#lobby-seats li[data-seat='1'] button")
    page.wait_for_selector("#game-screen:not([hidden])", timeout=120_000)
    page.wait_for_function(
        "state.view !== null && refreshFlight === null", timeout=120_000
    )
    table_at = time.monotonic() - started
    page.wait_for_function(images_done_js(), timeout=300_000)
    images_at = time.monotonic() - started
    megabytes, requests = transferred(page)
    print(
        f"  {label}\n"
        f"    first visit: seat picker {lobby_at:.1f}s, playable table {table_at:.1f}s,"
        f" every image {images_at:.1f}s, {megabytes:.1f} MB in {requests} requests"
    )
    return context, page, recorder, table_at, images_at, megabytes


def main() -> None:
    if HOST == "127.0.0.1":
        print("note: E2E_HOST is loopback, which IS a secure context; set it to the")
        print("      machine's Tailscale address to rehearse the real origin.\n")
    with (
        server("--remote", "--admin-key", KEY) as (base, server_log),
        chrome() as browser,
    ):
        _, host, host_rec = open_context(browser, "host")
        game_id = create_full_game(host, base)

        print("[1] the origin friends will use")
        secure = host.evaluate("window.isSecureContext")
        print(f"  .. {base} isSecureContext = {secure}")
        if HOST != "127.0.0.1":
            check.ok(
                secure is False, "a Tailscale address over HTTP is not a secure context"
            )
        host.click("#host-panel > summary")
        host.click("#host-panel-body .room-link button")
        selected = host.evaluate(
            "() => { const f = document.querySelector("
            "'#host-panel-body .room-link-value');"
            " return document.activeElement === f && f.selectionStart === 0"
            " && f.selectionEnd === f.value.length && f.value.length > 0; }"
        )
        check.ok(
            selected, "the copy button leaves the room link selected for a manual copy"
        )
        check.ok(
            host.evaluate(
                "() => { try { turnTone(); return true; } catch (e) { return false; } }"
            ),
            "the turn tone never throws",
        )
        cookies = [c for c in host.context.cookies() if c["name"].startswith("dune_")]
        print(
            "  .. cookies:",
            [
                (c["name"][:22], c["path"], c["httpOnly"], c["sameSite"], c["secure"])
                for c in cookies
            ],
        )
        check.ok(len(cookies) == 2, "an admin cookie and a seat cookie", len(cookies))
        check.ok(all(c["httpOnly"] for c in cookies), "both HttpOnly")
        check.ok(
            all(c["sameSite"] == "Strict" for c in cookies), "both SameSite=Strict"
        )
        check.ok(
            not any(c["secure"] for c in cookies),
            "neither is Secure (it would be dropped over HTTP)",
        )
        seat_cookie = next(c for c in cookies if c["name"].startswith("dune_seat_"))
        check.ok(
            seat_cookie["path"] == f"/games/{game_id}",
            "the seat cookie is scoped to its game",
            seat_cookie["path"],
        )
        check.ok(
            host.evaluate("document.cookie") == "", "scripts cannot read either cookie"
        )

        print("[2] what the link costs a friend (all expansions, cold cache)")
        for index, profile in enumerate(PROFILES):
            context, guest, guest_rec, table_at, images_at, megabytes = visit(
                browser, base, game_id, profile, f"친구{index}"
            )
            pages = {"host": (host, host_rec), "guest": (guest, guest_rec)}
            check.ok(
                converge(pages, game_id, profile[0], timeout=20),
                "host and guest converge",
            )

            # One step by whoever must act; how long until the OTHER page shows it.
            delays = []
            for _ in range(8):
                summary = host.evaluate(
                    f"fetch('/games/{game_id}').then((r) => r.json())"
                )
                held = isinstance(summary["confirmation"], int)
                seat = summary["confirmation"] if held else summary["decision"]["owner"]
                actor, other = (host, guest) if seat == 0 else (guest, host)
                mark = other.evaluate(
                    "state.summary.revision + ':' + state.summary.confirmation"
                )
                sent = time.monotonic()
                actor.evaluate("confirmTurn()" if held else "applyAction(0)")
                other.wait_for_function(
                    "(state.summary.revision + ':' + state.summary.confirmation)"
                    f" !== '{mark}'"
                    " && refreshFlight === null",
                    timeout=30_000,
                )
                delays.append((time.monotonic() - sent) * 1000)
                converge(pages, game_id, "step", timeout=20)
            delays.sort()
            print(
                "    a step reaches the other browser in"
                f" {delays[len(delays) // 2]:.0f} ms"
                f" (median of {len(delays)}; max {delays[-1]:.0f} ms)"
            )

            started = time.monotonic()
            guest.reload()
            guest.wait_for_selector("#game-screen:not([hidden])", timeout=120_000)
            guest.wait_for_function(
                "state.view !== null && refreshFlight === null", timeout=120_000
            )
            reload_table = time.monotonic() - started
            guest.wait_for_function(images_done_js(), timeout=300_000)
            reload_images = time.monotonic() - started
            warm_mb, warm_requests = transferred(guest)
            print(
                f"    reload (warm cache): playable table {reload_table:.1f}s,"
                " every image"
                f" {reload_images:.1f}s, {warm_mb:.2f} MB in {warm_requests} requests"
            )
            check.ok(
                warm_mb < megabytes / 4,
                "a reload re-downloads little",
                (warm_mb, megabytes),
            )
            # Free seat 1 for the next profile's visitor.
            guest.click("#open-lobby")
            guest.wait_for_selector("#lobby-screen:not([hidden])")
            guest.click("#lobby-seats li[data-seat='1'] button:has-text('자리 비우기')")
            guest.wait_for_function("state.me.seats.length === 0")
            context.close()

        errors = [e for e in host_rec.js_errors if "Failed to load resource" not in e]
        check.ok(not errors, "no JS exceptions on the host", errors)
        text = server_log.read_text()
        check.ok("Traceback" not in text and "ERROR" not in text, "no server errors")
    check.finish()


if __name__ == "__main__":
    sys.exit(main())
