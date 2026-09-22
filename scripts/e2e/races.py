"""Interventions on response ordering (M14 slice 4).

Both force an order of arrival that a WAN produces by itself now and then,
and check that the page still ends up where the server is.

1. late seat snapshot: the waiting page's seat snapshot is read, then held
   0.7 s while the acting seat makes two more changes. The stale answer is
   adopted and the queued pass of the single-flight refresh must follow.
2. presence bell during entry: the guest reloads; its stream is delayed 0.3 s
   and its entering snapshot (read before the stream connected, so it says
   `online: false`) is handed over 0.9 s late. With `--ab` the same run is
   first made against an app.js whose extra pass is disabled, which must end
   stale: that is what shows the check can fail.
"""

from __future__ import annotations

import asyncio
import re
import sys
import time

from common import chrome, launch_options, open_context, rule_option_steps, server
from playwright.async_api import async_playwright
from remote import CONVERGED_JS, KEY, converge, drive, seat_two_players

SEAT_SNAPSHOT = re.compile(r"/snapshot\?seat=")


def _hold_first(held: dict[str, object], seconds: float):
    """A route handler that reads the first matching answer at once and hands
    it to the page `seconds` later; every later request passes untouched.

    (Playwright calls a handler with as many arguments as it declares, so
    the shared `held` record is closed over, not a defaulted parameter.)
    """

    def hold(route) -> None:
        if held["done"]:
            route.continue_()
            return
        held["done"] = True
        response = route.fetch()
        held["read"] = response.json()["summary"]["revision"]
        time.sleep(seconds)
        route.fulfill(response=response)

    return hold


def late_seat_snapshot(trials: int = 5) -> bool:
    print("[1] a seat snapshot that answers late, under two further changes")
    with server("--remote", "--admin-key", KEY) as (base, _), chrome() as browser:
        _, host, host_rec = open_context(browser, "host")
        _, guest, guest_rec = open_context(browser, "guest")
        pages = {"host": (host, host_rec), "guest": (guest, guest_rec)}
        seat_pages = {0: host, 1: guest}
        game_id = seat_two_players(base, host, guest)
        assert converge(pages, game_id, "setup")
        outcomes = []
        for trial in range(trials):
            for _ in range(60):
                summary = host.evaluate(
                    f"fetch('/games/{game_id}').then((r) => r.json())"
                )
                owner = summary["decision"]["owner"]
                if summary["confirmation"] is None and owner in seat_pages:
                    break
                assert drive(pages, seat_pages, game_id, 1, "search") == 1
            acting, waiting = seat_pages[owner], seat_pages[1 - owner]
            waiting.evaluate(
                "() => { window.__revs = []; window.__watch = setInterval(() => {"
                " const r = `${state.summary.revision}/${state.summary.confirmation}`;"
                " if (r !== window.__revs[window.__revs.length - 1])"
                " window.__revs.push(r); }, 2); }"
            )
            held: dict[str, object] = {"done": False, "read": None}
            waiting.route(SEAT_SNAPSHOT, _hold_first(held, 0.7))
            acting.evaluate(
                "async () => { await applyAction(0); setTimeout(() => {"
                " if (typeof state.summary.confirmation === 'number') confirmTurn();"
                " else applyAction(0); }, 100); }"
            )
            waiting.wait_for_timeout(2200)
            waiting.unroute(SEAT_SNAPSHOT)
            verdict = waiting.evaluate(CONVERGED_JS, game_id)
            history = waiting.evaluate(
                "() => { clearInterval(window.__watch); return window.__revs; }"
            )
            print(
                f"  trial {trial}: held answer read at rev {held['read']}; "
                f"history {history}; converged={verdict['ok']}"
            )
            outcomes.append(bool(verdict["ok"]))
            assert converge(pages, game_id, "between trials")
    return all(outcomes)


async def _presence_bell_during_entry(patched: bool) -> bool:
    label = "extra pass disabled" if patched else "as committed"
    with server("--remote", "--admin-key", KEY) as (base, _):
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(**launch_options())
            host = await (await browser.new_context()).new_page()
            guest_context = await browser.new_context()
            guest = await guest_context.new_page()
            if patched:

                async def patch(route) -> None:
                    response = await route.fetch()
                    body = (await response.text()).replace(
                        "} else if (refreshFlight) {", "} else if (false) {"
                    )
                    # An assertion here would surface as a goto timeout, since
                    # a throwing route handler never fulfills the request.
                    if "} else if (false) {" not in body:
                        print("  !! session.js changed shape: refresh() not patched")
                    await route.fulfill(response=response, body=body)

                # The single-flight refresh lives in session.js since the
                # client was split; routing app.js patched nothing.
                await guest_context.route("**/static/session.js", patch)
            await host.goto(f"{base}/#admin={KEY}")
            await host.wait_for_selector("#setup-screen:not([hidden])")
            await host.select_option("#seat-selects select[data-seat='1']", "human")
            for selector, checked in rule_option_steps():
                await host.set_checked(selector, checked)
            await host.click("#create-game")
            await host.wait_for_selector("#lobby-screen:not([hidden])")
            game_id = await host.evaluate("state.gameId")
            await host.fill("#lobby-name", "호스트")
            await host.click("#lobby-seats li[data-seat='0'] button")
            await host.wait_for_selector("#game-screen:not([hidden])")
            await guest.goto(f"{base}/#game={game_id}")
            await guest.wait_for_selector("#lobby-screen:not([hidden])")
            await guest.fill("#lobby-name", "친구")
            await guest.click("#lobby-seats li[data-seat='1'] button")
            await guest.wait_for_selector("#game-screen:not([hidden])")
            await guest.wait_for_timeout(500)

            async def late_stream(route) -> None:
                await asyncio.sleep(0.3)
                await route.continue_()

            held = {"done": False}

            async def late_snapshot(route) -> None:
                if held["done"]:
                    await route.continue_()
                    return
                held["done"] = True
                response = await route.fetch()
                body = await response.json()
                online = body["summary"]["players"][1]["online"]
                print(f"  [{label}] held snapshot was read with online={online}")
                await asyncio.sleep(0.9)
                await route.fulfill(response=response)

            await guest.route("**/events", late_stream)
            await guest.route(SEAT_SNAPSHOT, late_snapshot)
            await guest.reload()
            await guest.wait_for_selector("#game-screen:not([hidden])")
            await guest.wait_for_timeout(3000)
            verdict = await guest.evaluate(CONVERGED_JS, game_id)
            local = await guest.evaluate("state.summary.players[1].online")
            print(
                f"  [{label}] 3 s later the page says online={local}; "
                f"converged={verdict['ok']}"
            )
            await browser.close()
            return bool(verdict["ok"])


def main() -> int:
    failed = []
    if not late_seat_snapshot():
        failed.append("late seat snapshot")
    print("[2] a presence bell that rings while the entering snapshot is in flight")
    if "--ab" in sys.argv:
        if asyncio.run(_presence_bell_during_entry(patched=True)):
            failed.append("the patched page converged: the check cannot fail")
    if not asyncio.run(_presence_bell_during_entry(patched=False)):
        failed.append("presence bell during entry")
    print("RESULT:", "all converged" if not failed else f"FAILED: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
