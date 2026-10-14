"""The server's error messages on the Korean page (user decision 2026-10-14).

The server answers a refused request with an English sentence in the HTTP
error's `detail` (server/sessions.py, persistence.py). The Korean page shows
Korean for it (static/errors_ko.js, i18n.js serverErrorText), the English
page shows the server's own words as before, and a message the page has no
Korean for stays as the server wrote it. A network failure (no answer at all)
is worded by the page, not the browser ("Failed to fetch"). The status code
stays in front of the text, and error.status is untouched.

[1] api() itself, both languages, against the real server.
[2] The whole chain a player meets: the setup screen's error line and a seat
    number in a message (the engine's zero-based id is the visible number
    minus one), with responses a route fulfils.
"""

from __future__ import annotations

import json
from pathlib import Path

from common import Check, chrome, open_context, server

check = Check()

# What api() throws, as [status, message] (status null with no answer).
CALL_JS = """async (path) => {
    try {
        await api(path);
        return null;
    } catch (error) {
        return [error.status ?? null, error.message];
    }
}"""

POST_JS = """async (body) => {
    try {
        await api("/games", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        return null;
    } catch (error) {
        return [error.status ?? null, error.message];
    }
}"""


def set_language(page, lang: str) -> None:
    if page.evaluate("TERM_LANGUAGE") != lang:
        page.click("#language-toggle")
    page.wait_for_function("(lang) => document.documentElement.lang === lang", arg=lang)


def api_messages(base: str, browser) -> None:
    print("[1] api() words an error in the page's language")
    context, page, rec = open_context(browser, "server-errors-api")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")

    set_language(page, "ko")
    got = page.evaluate(CALL_JS, "/games/missing")
    check.ok(
        got == [404, "404: 알 수 없는 게임입니다: missing"],
        "Korean: an unknown game",
        got,
    )
    got = page.evaluate(POST_JS, {"seats": ["human", "search", "app_ai", "app_ai"]})
    check.ok(
        got == [400, "400: 이 서버에는 탐색 AI가 없습니다"],
        "Korean: a search seat on a server without a search AI",
        got,
    )
    got = page.evaluate(POST_JS, {"seats": ["human", "nobody", "app_ai", "app_ai"]})
    check.ok(
        got is not None
        and got[0] == 400
        and got[1].startswith("400: 알 수 없는 플레이어 유형입니다: ")
        and "nobody" in got[1],
        "Korean: an unknown seat assignment keeps the offending value",
        got,
    )
    got = page.evaluate(POST_JS, {"seats": "not a list"})
    check.ok(
        got is not None and got[0] == 422 and got[1].startswith("422: ["),
        "Korean: a message the page has no Korean for stays as the server wrote it",
        got,
    )

    set_language(page, "en")
    got = page.evaluate(CALL_JS, "/games/missing")
    check.ok(
        got is not None
        and got[0] == 404
        and got[1].startswith('404: "unknown game: ')
        and not any("가" <= char <= "힣" for char in got[1]),
        "English: the server's own sentence, quoted as before",
        got,
    )
    got = page.evaluate(POST_JS, {"seats": ["human", "search", "app_ai", "app_ai"]})
    check.ok(
        got == [400, '400: "this server has no search AI"'],
        "English: the search AI refusal names no command-line flag",
        got,
    )

    # A network failure: the browser's own "Failed to fetch" is not shown.
    page.route("**/catalog**", lambda route: route.abort("internetdisconnected"))
    set_language(page, "ko")
    got = page.evaluate(CALL_JS, "/catalog")
    check.ok(
        got == [None, "서버에 연결하지 못했습니다"],
        "Korean: no answer from the server",
        got,
    )
    set_language(page, "en")
    got = page.evaluate(CALL_JS, "/catalog")
    check.ok(
        got == [None, "Could not reach the server"],
        "English: no answer from the server",
        got,
    )
    page.unroute("**/catalog**")

    own = [e for e in rec.js_errors if not e.startswith("Failed to load resource")]
    check.ok(not own, "no JS errors besides the refused requests' own", own[:3])
    context.close()


def player_chain(base: str, browser) -> None:
    print("[2] what a player sees on the setup screen")
    context, page, rec = open_context(browser, "server-errors-chain")

    refusal = {"detail": "seat 0 is already taken"}

    def refuse(route):
        if route.request.method == "POST":
            route.fulfill(
                status=409,
                content_type="application/json",
                body=json.dumps(refusal),
            )
        else:
            route.continue_()

    page.route("**/games", refuse)
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    set_language(page, "ko")
    page.click("#create-game")
    page.wait_for_selector("#setup-error:not([hidden])")
    shown = page.inner_text("#setup-error")
    check.ok(
        shown == "게임 생성 실패 (409: 플레이어1: 이미 다른 사람이 참여했습니다)",
        "Korean: the engine's seat 0 is 플레이어1 in the setup error line",
        shown,
    )

    refusal["detail"] = "the game advanced past the submitted revision"
    page.click("#create-game")
    page.wait_for_function(
        "document.getElementById('setup-error').textContent.includes('그 사이')"
    )
    shown = page.inner_text("#setup-error")
    check.ok(
        shown
        == "게임 생성 실패 (409: 그 사이 게임이 먼저 진행되어 화면이 최신 상태가 아닙니다)",
        "Korean: a stale-revision refusal",
        shown,
    )

    set_language(page, "en")
    page.click("#create-game")
    page.wait_for_function(
        "document.getElementById('setup-error').textContent.includes('Game creation failed')"
    )
    shown = page.inner_text("#setup-error")
    check.ok(
        shown
        == 'Game creation failed (409: "the game advanced past the submitted revision")',
        "English: the line is as it was",
        shown,
    )
    page.unroute("**/games", refuse)

    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400 and r[3] != 409]
    check.ok(not failed, "no failed requests other than the fulfilled 409", failed[:3])
    own = [e for e in rec.js_errors if not e.startswith("Failed to load resource")]
    check.ok(not own, "no JS errors besides the refused requests' own", own[:3])
    context.close()


def main() -> None:
    # The refusals above need a server with no search AI. A checkout with
    # checkpoints/play/search.pt would give the default server one, so name
    # a checkpoint that does not exist (as search_seats.py's [N] does).
    missing = Path(__file__).resolve().parents[2] / "tmp" / "e2e" / "no-search-ai.pt"
    with server("--search-checkpoint", str(missing)) as (base, _), chrome() as browser:
        api_messages(base, browser)
        player_chain(base, browser)
    check.finish()


if __name__ == "__main__":
    main()
