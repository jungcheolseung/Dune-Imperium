"""The #game-error banner outlives a refresh failure it no longer describes
(ITEM 8g, 2026-09-25 -- reproduced: one snapshot GET is aborted while another
seat moves over HTTP, the page shows "게임 상태 조회 실패 (Failed to fetch)",
and that line never goes away even once a later refresh lands and the page
has fresh choices on screen).

screens.js showRefreshError now marks the banner it writes
(`dataset.source = "refresh"`); session.js adoptSnapshot clears the banner on
a successful snapshot only when it still carries that mark, so a refresh
failure that has since been overtaken by a later refresh is wiped, while an
error the player caused themselves (their own action, turn end, undo, or a
review request -- none of which set the mark) stays up exactly as before.

[1] is the reproduction, driven the way it was first shown to fail: a
snapshot GET aborted while another seat moves over raw HTTP, then a second,
unblocked foreign move. This is the assertion an A/B run (README, 새 검사를
더할 때) must show failing against the last commit before this fix -- the old
client's adoptSnapshot never touches #game-error at all, so the banner from
the aborted GET is still on screen once the page has caught up.

[2] checks the other half of the design on its own: an error from the
player's own action (a POST failed by a route, not a refresh) must not be
wiped by an unrelated foreign refresh that succeeds right after it.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import time
import urllib.request

from common import SERVER_LOG_COPY, Check, chrome, client_state, open_context, server
from open_mode import create_game, settled

check = Check()

ACTIONS_OR_CONFIRM = re.compile(r"/(actions|confirm)$")


def wait_ok(page, js: str, timeout: int = 10000) -> bool:
    """`wait_for_function` without raising: a condition the old client can
    never reach (it never marks or clears the banner) should read as a
    failed check here, not abort the whole run."""
    try:
        return bool(page.wait_for_function(js, timeout=timeout))
    except Exception:
        return False


def _post(base: str, path: str, body: dict) -> dict:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        result: dict = json.loads(response.read())
    return result


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path) as response:
        result: dict = json.loads(response.read())
    return result


def foreign_step(base: str, game_id: str) -> dict:
    """One raw-HTTP step for whichever seat is next, driven outside the
    browser: from the page's point of view this is another player's move,
    exactly what the doorbell's SSE 'change' event announces."""
    summary = _get(base, f"/games/{game_id}")
    if summary.get("confirmation") is not None:
        return _post(
            base,
            f"/games/{game_id}/confirm",
            {
                "seat": summary["confirmation"],
                "revision": summary["revision"],
                "undo_count": summary["undo_count"],
            },
        )
    owner = summary["decision"]["owner"]
    return _post(
        base,
        f"/games/{game_id}/actions",
        {
            "seat": owner,
            "revision": summary["revision"],
            "undo_count": summary["undo_count"],
            "index": 0,
        },
    )


def scenario_refresh_error_clears(base, browser) -> None:
    print("[1] a refresh-failure banner clears itself once a later refresh lands")
    _, page, rec = open_context(browser, "blip")
    game_id = create_game(page, base, humans=(0, 1), seed=3)
    assert settled(page, 20)

    # One network blip: the next snapshot GET fails, the way an aborted
    # request or a dropped WAN packet would.
    fail = {"n": 1}

    def handler(route):
        if fail["n"] > 0:
            fail["n"] -= 1
            route.abort("internetdisconnected")
        else:
            route.continue_()

    page.route("**/snapshot**", handler)
    foreign_step(base, game_id)
    # The leader-draft screen this seed opens on is loading a wall of card
    # images at the same time, so the queued snapshot GET can take a few
    # seconds to even start (Chrome's per-origin connection limit) -- a
    # polling wait rather than a fixed sleep (README, 새 검사를 더할 때).
    shown = wait_ok(page, "!document.getElementById('game-error').hidden", timeout=15000)
    page.unroute("**/snapshot**", handler)
    blipped = client_state(page)
    check.ok(
        shown and blipped["error"] is not None and "게임 상태 조회 실패" in blipped["error"],
        "the aborted refresh leaves the game-state-fetch error on screen",
        blipped["error"],
    )

    # A second, unblocked foreign move: the page's own doorbell asks for a
    # refresh and this one lands.
    res = foreign_step(base, game_id)
    page.wait_for_function(
        f"state.summary && state.summary.revision === {res['revision']}", timeout=15000
    )
    assert settled(page, 10)
    caught_up = client_state(page)
    check.ok(
        caught_up["error"] is None,
        "the error is gone once a later refresh has landed",
        caught_up["error"],
    )

    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests other than the aborted snapshot", failed[:5])


def scenario_action_error_persists(base, browser) -> None:
    print("[2] an action error is not wiped by an unrelated foreign refresh")
    _, page, _ = open_context(browser, "action-error")
    create_game(page, base, humans=(0,), seed=5)
    assert settled(page, 20)

    # Fail the player's own next request (whichever of the two turn-taking
    # POSTs is due) once, the way a dropped connection would.
    fail = {"n": 1}

    def handler(route):
        if fail["n"] > 0:
            fail["n"] -= 1
            route.abort("internetdisconnected")
        else:
            route.continue_()

    page.route(ACTIONS_OR_CONFIRM, handler)
    confirmation = client_state(page)["confirmation"]
    call = "confirmTurn()" if confirmation is not None else "applyAction(0)"
    page.evaluate(call)
    assert settled(page, 10)
    page.unroute(ACTIONS_OR_CONFIRM, handler)

    after_fail = client_state(page)
    check.ok(
        after_fail["error"] is not None,
        "the failed request leaves its own error banner up",
        after_fail["error"],
    )

    # A foreign refresh that succeeds right after: nothing changed on the
    # server (the POST never reached it), so this is the "someone else moved,
    # the page caught up" case with no state change of its own -- the action
    # error must survive it exactly as it did before this fix.
    page.evaluate("async () => { await refresh(null, { foreign: true }); }")
    assert settled(page, 10)
    after_refresh = client_state(page)
    check.ok(
        after_refresh["error"] == after_fail["error"],
        "an unrelated foreign refresh leaves the action error untouched",
        (after_fail["error"], after_refresh["error"]),
    )


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            scenario_refresh_error_clears(base, browser)
            scenario_action_error_persists(base, browser)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    check.finish()


if __name__ == "__main__":
    started = time.monotonic()
    try:
        main()
    finally:
        print(f"({time.monotonic() - started:.1f}s)", file=sys.stderr)
