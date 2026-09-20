"""Open-mode E2E, the three checks of M14 slices 2 and 3, against the slice 4 client.

A. one screen plays 2 humans + 2 heuristic to the end: one POST + one
   snapshot per step, client log == server log at every step, an undo
   re-sends the log, the finished game swaps in the unmasked log.
B. review mode: the latest request wins, and a late answer after leaving
   review does not repaint the live table.
C. three contexts: the doorbell reflects another browser's step with one
   snapshot, a browser with the stream blocked falls back to polling, and a
   deleted game is announced to both.
"""

from __future__ import annotations

import json
import shutil
import sys
import time

from common import (
    SERVER_LOG_COPY,
    Check,
    chrome,
    client_state,
    now,
    open_context,
    server,
)

check = Check()
SEED = 20260917


def create_game(page, base: str, humans=(0, 1), seed: int | None = SEED) -> str:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat in humans else "heuristic",
        )
    if seed is not None:
        page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    return page.evaluate("state.gameId")


def settled(page, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if page.evaluate("!state.busy && refreshFlight === null"):
            return True
        time.sleep(0.01)
    return False


def scenario_full_game(base, browser) -> str:
    print("[A] one screen plays the whole game")
    _, page, rec = open_context(browser, "table")
    game_id = create_game(page, base)
    check.ok(page.evaluate("state.server.access") == "open", "whoami says open")
    check.ok(
        page.is_visible("#opt-seed-row") is False
        and page.evaluate("!document.getElementById('opt-seed-row').hidden"),
        "seed row is not hidden by the page on an open server",
    )
    check.ok(
        page.url.endswith(f"#game={game_id}"),
        "room hash set on an open server too",
        page.url,
    )
    check.ok(
        page.evaluate("state.me.seats") == [0, 1], "this browser plays both human seats"
    )
    check.ok(not page.is_visible("#open-lobby"), "no seat button on an open server")
    check.ok(not page.is_visible("#host-panel"), "no host panel on an open server")
    check.ok(page.is_visible("#save-game"), "save button shown")
    check.ok(
        f"seed {SEED}" in page.inner_text("#header-status"),
        "seed shown in the header on an open server",
    )

    steps = 0
    undone = False
    mismatches = []
    base_posts = sum(
        1 for r in rec.requests if r[1] == "POST" and r[2].startswith("games/")
    )
    base_snaps = rec.count("GET", "/snapshot")
    started = now()
    while True:
        snap = client_state(page)
        if snap["finished"]:
            break
        if steps > 3000:
            break
        if snap["confirmation"] is not None:
            act = "confirmTurn()"
        else:
            act = "applyAction(0)"
        if (
            not undone
            and steps == 25
            and snap["confirmation"] is None
            and page.evaluate(
                "(state.summary.undo || []).some((u) => u.seat === state.viewSeat"
                " && u.steps > 0)"
            )
        ):
            epoch_before = page.evaluate("state.log.epoch")
            page.evaluate("submitUndo(state.viewSeat, 1)")
            settled(page)
            epoch_after = page.evaluate("state.log.epoch")
            check.ok(
                epoch_before != epoch_after,
                "an undo changes the log epoch",
                (epoch_before, epoch_after),
            )
            undone = True
        else:
            page.evaluate(act)
            if not settled(page):
                print(
                    "  NOT SETTLED", json.dumps(client_state(page), ensure_ascii=False)
                )
                rec.dump(since=now() - 12)
                check.ok(False, "every step settles")
                return game_id
        steps += 1
        after = client_state(page)
        if after["logLen"] != after["logCount"]:
            mismatches.append((steps, after["logLen"], after["logCount"]))
        if after["error"]:
            check.ok(False, "no error banner", after["error"])
            return game_id
    posts = (
        sum(1 for r in rec.requests if r[1] == "POST" and r[2].startswith("games/"))
        - base_posts
    )
    snaps = rec.count("GET", "/snapshot") - base_snaps
    print(
        f"  .. {steps} steps in {now() - started:.1f}s, POST {posts}, snapshot {snaps}"
    )
    check.ok(client_state(page)["finished"], "the game finished")
    check.ok(undone, "an undo was exercised")
    check.ok(posts == steps, "one POST per step", (posts, steps))
    check.ok(
        snaps == posts, "one snapshot per POST (seat changes included)", (snaps, posts)
    )
    check.ok(
        not mismatches,
        "client log length == server log_count after every step",
        mismatches[:5],
    )
    # The log is rebuilt on every render. A reader who scrolled up to re-read
    # an earlier turn must keep their place; one sitting at the end keeps
    # following the game. Before this the list jumped to the newest entry on
    # every render, including renders caused by somebody else's move.
    log_follow = page.evaluate(
        """() => {
            const list = () => document.querySelector('#action-log .log-list');
            const start = list();
            if (!start || start.scrollHeight <= start.clientHeight + 1) return null;
            start.scrollTop = 0;
            render({ foreign: true });
            const kept = list().scrollTop;
            const end = list();
            end.scrollTop = end.scrollHeight;
            render({ foreign: true });
            return { kept, followed: list().scrollTop };
        }"""
    )
    if check.ok(
        log_follow is not None,
        "the finished game's log is long enough to scroll",
        log_follow,
    ):
        check.ok(
            log_follow["kept"] == 0,
            "a reader scrolled up keeps their place in the log",
            log_follow,
        )
        check.ok(
            log_follow["followed"] > 0,
            "a reader at the end keeps following the log",
            log_follow,
        )

    # Our own labels are built from term tokens, not by running English
    # regexes over a composed string, so a card name can never be eaten by an
    # icon. Before this, the Signet Ring placement rendered "배치 — , Arrakeen"
    # because ICON_RULES matched the card's own name.
    # Every step that names a card must show that card's name as text. This
    # is the invariant the old renderer broke: it joined our label and the
    # card name into one string and ran ICON_RULES over it, so the card
    # called "Signet Ring" became the Signet Ring icon and the line read
    # "배치 — , Arrakeen". A payload drawn purely as icons is fine and is why
    # this asks for the name rather than for any text at all.
    named = page.evaluate(
        """() => {
            const want = [];
            state.log.entries.forEach((entry) => {
                if (entry.type !== 'action' || entry.undone) return;
                const id = entry.arguments && entry.arguments.card_id;
                if (typeof id !== 'string') return;
                want.push({ index: entry.index, name: nameOf(id) });
            });
            return want.map((w) => {
                const head = [...document.querySelectorAll('#action-log .turn-line-head')]
                    .find((e) => {
                        const tag = e.querySelector('.turn-index');
                        return tag && tag.textContent.trim() === '#' + w.index;
                    });
                return { ...w, shown: head ? head.textContent : null };
            }).filter((w) => w.shown !== null);
        }"""
    )
    check.ok(len(named) >= 3, "the log has card-naming steps to check", len(named))
    lost = [w for w in named if w["name"] not in w["shown"]]
    check.ok(
        not lost,
        "every step that names a card shows that name as text",
        [(w["name"], w["shown"]) for w in lost[:3]],
    )
    # Any {term} on screen means a label was rendered as plain text instead of
    # through phrase()/phraseText(). Match the shape, not a list of tokens, so
    # a new term cannot slip past by not being in the list.
    leaked = page.evaluate(
        """() => {
            const hits = new Set();
            const add = (text) => {
                for (const m of String(text || '').matchAll(/\\{[a-z_]+(?::\\d+)?\\}/g)) {
                    hits.add(m[0]);
                }
            };
            add(document.getElementById('game-screen').innerText);
            for (const el of document.querySelectorAll('#game-screen [title], #game-screen img[alt]')) {
                add(el.getAttribute('title'));
                add(el.getAttribute('alt'));
            }
            return [...hits];
        }"""
    )
    check.ok(not leaked, "no unexpanded term markup reaches the screen", leaked)

    full = page.evaluate(f"fetch('/games/{game_id}/log?seat=0').then((r) => r.json())")
    local = page.evaluate("state.log.entries")
    check.ok(
        local == full["entries"], "the stitched client log equals the server's full log"
    )
    check.ok(
        page.is_visible("#standings")
        or page.evaluate("document.querySelector('.winner') !== null"),
        "standings shown",
    )
    rows = page.evaluate(
        "[...document.querySelectorAll('tr.winner td')].map((c) => c.textContent)"
    )
    check.ok(
        len(rows) == 7 and rows[1].startswith("좌석 "),
        "winner row drawn from text cells",
        rows,
    )
    check.ok(
        page.title() == "Dune: Imperium — Uprising",
        "tab title untouched on an open server",
        page.title(),
    )

    print("[B] review mode: the latest request wins")
    base_review = rec.count("GET", "/review/")
    page.click("#standings button:has-text('리플레이 검토')")
    page.click("#review-first")
    page.wait_for_function(
        "state.review && state.review.cursor === 0"
        " && document.getElementById('review-slider').value === '0'"
    )
    time.sleep(1.5)  # a late answer for the last step must not repaint step 0
    check.ok(
        page.evaluate("state.review.cursor") == 0,
        "the late answer for the last step did not overwrite step 0",
    )
    check.ok(
        "step 0/" in page.inner_text("#review-status"),
        "review status shows step 0",
        page.inner_text("#review-status"),
    )
    page.click("#review-last")
    page.click("#review-exit")
    time.sleep(1.5)
    check.ok(page.evaluate("state.review") is None, "review left")
    check.ok(
        page.evaluate("state.view !== null && state.summary.finished"),
        "live table back after review",
    )
    check.ok(not page.is_visible("#review-bar"), "review bar hidden again")
    print(f"  .. review requests: {rec.count('GET', '/review/') - base_review}")

    print("[A'] reload returns to the game; leaving clears the hash")
    page.reload()
    page.wait_for_selector("#game-screen:not([hidden])")
    check.ok(
        page.evaluate("state.gameId") == game_id, "reload comes back to the same game"
    )
    page.click("#leave-game")
    page.wait_for_selector("#setup-screen:not([hidden])")
    check.ok("#game=" not in page.url, "hash cleared after leaving", page.url)
    page.wait_for_selector("#game-list button")
    check.ok(page.is_visible("#game-list"), "game list shown on the setup screen")
    check.ok(
        not page.is_visible("#landing-resume"), "no resume offer where the game list is"
    )
    page.click("#game-list button")
    page.wait_for_selector("#game-screen:not([hidden])")
    check.ok(page.evaluate("state.gameId") == game_id, "'이어서' reopens the game")

    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])
    errors = [e for e in rec.js_errors]
    check.ok(not errors, "no JS errors", errors[:5])
    return game_id


def scenario_doorbell(base, browser) -> None:
    print("[C] three contexts: doorbell, polling fallback, deletion")
    _, actor, actor_rec = open_context(browser, "actor")
    _, watcher, watcher_rec = open_context(browser, "watcher")
    blocked_ctx, blocked, blocked_rec = open_context(browser, "blocked")
    blocked_ctx.route("**/events", lambda route: route.abort())

    game_id = create_game(actor, base, humans=(0, 1), seed=SEED + 1)
    for page in (watcher, blocked):
        page.goto(f"{base}/#game={game_id}")
        page.wait_for_selector("#game-screen:not([hidden])")
        page.wait_for_function("state.view !== null && refreshFlight === null")
    polling_started = now()
    blocked.wait_for_function("doorbell && doorbell.pollTimer !== 0", timeout=15000)
    print(
        f"  .. blocked context fell back to polling after "
        f"{now() - polling_started:.1f}s"
    )

    # Pin a popover and scroll a pane on the watcher: a foreign refresh keeps both.
    # Which pane scrolls depends on the viewport -- `@media (max-width: 1700px)`
    # moves the side column's scrolling from #side-main up to #side -- and this
    # browser runs at 1600px, so the old check named #side-main, set a scrollTop
    # that a non-scrolling element discards, and then excused itself with
    # `or scroll_before == 0`. Ask the page which pane really takes an offset.
    # Two checks. The structural one catches the whole class: a pane the
    # stylesheet lets scroll but the client forgot to list is a silent
    # regression at that viewport, which is how #side was dropped.
    unlisted = watcher.evaluate(
        """() => {
            const ids = ['table', 'seats', 'center', 'board', 'market', 'side',
                         'side-main', 'side-log', 'private-zone', 'action-log'];
            return ids.filter((id) => {
                const pane = document.getElementById(id);
                if (!pane) return false;
                const flow = getComputedStyle(pane).overflowY;
                if (flow !== 'auto' && flow !== 'scroll') return false;
                return !SCROLL_PANES.includes(id);
            });
        }"""
    )
    check.ok(
        unlisted == [],
        "SCROLL_PANES names every pane the stylesheet lets scroll",
        unlisted,
    )
    scroll_before = watcher.evaluate(
        """() => {
            const out = {};
            for (const id of SCROLL_PANES) {
                const pane = document.getElementById(id);
                if (!pane) continue;
                pane.scrollTop = 120;
                if (pane.scrollTop > 0) out[id] = pane.scrollTop;
            }
            return out;
        }"""
    )
    if not check.ok(
        bool(scroll_before),
        "some pane holds a scroll offset to preserve",
        scroll_before,
    ):
        check.finish()

    time.sleep(0.5)
    actor_before = len(actor_rec.requests)
    watcher_snaps = watcher_rec.count("GET", "/snapshot")
    log_count = actor.evaluate("state.summary.log_count")
    sent = now()
    actor.evaluate("applyAction(0)")
    watcher.wait_for_function(
        f"state.summary.log_count > {log_count} && refreshFlight === null", timeout=5000
    )
    heard = now() - sent
    check.ok(heard < 1.0, "another browser's step shows within a second", heard)
    print(f"  .. doorbell reflected in {heard * 1000:.0f} ms")
    time.sleep(0.4)
    check.ok(
        watcher_rec.count("GET", "/snapshot") - watcher_snaps == 1,
        "the watcher asked for exactly one snapshot",
        watcher_rec.count("GET", "/snapshot") - watcher_snaps,
    )
    own = [r for r in actor_rec.requests[actor_before:] if r[2].startswith("games/")]
    check.ok(
        len(own) == 2,
        "the actor's own step costs POST + snapshot and nothing for its own doorbell",
        own,
    )
    scroll_after = watcher.evaluate(
        """(ids) => Object.fromEntries(
            ids.map((id) => [id, document.getElementById(id).scrollTop]))""",
        list(scroll_before),
    )
    check.ok(
        scroll_after == scroll_before,
        "a foreign refresh keeps every scrolled pane's position",
        (scroll_before, scroll_after),
    )
    blocked.wait_for_function(
        f"state.summary.log_count > {log_count} && refreshFlight === null", timeout=6000
    )
    print(f"  .. polling context reflected in {now() - sent:.1f}s")
    check.ok(
        now() - sent < 4.5,
        "the polling browser catches up within its poll period",
        now() - sent,
    )

    actor.evaluate(f"fetch('/games/{game_id}', {{method: 'DELETE'}})")
    # The stream says "closed" (deleted); a poll only sees a 404, which a
    # restarted server gives as well, so its message covers both.
    told = (("watcher", watcher, "삭제"), ("blocked", blocked, "더 이상 없습니다"))
    for name, page, words in told:
        page.wait_for_selector("#setup-screen:not([hidden])", timeout=8000)
        text = page.inner_text("#setup-error")
        check.ok(words in text, f"{name} is told the game is gone", text)
        check.ok(
            page.evaluate("state.gameId") is None and page.evaluate("doorbell") is None,
            f"{name} left the game and closed its doorbell",
        )

    for rec in (actor_rec, watcher_rec):
        failed = [r for r in rec.requests if r[3] >= 400]
        check.ok(not failed, f"no failed requests on {rec.name}", failed[:5])
    polled_404 = [r for r in blocked_rec.requests if r[3] >= 400]
    check.ok(
        all(r[3] == 404 for r in polled_404),
        "the polling browser only ever failed with the 404 of the deleted game",
        polled_404[:5],
    )
    errors = [
        e
        for rec in (actor_rec, watcher_rec, blocked_rec)
        for e in rec.js_errors
        if "Failed to load resource" not in e and "ERR_FAILED" not in e
    ]
    check.ok(not errors, "no JS exceptions in the three contexts", errors[:5])


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    with server() as (base, server_log), chrome() as browser:
        try:
            if which in ("all", "game"):
                scenario_full_game(base, browser)
            if which in ("all", "bell"):
                scenario_doorbell(base, browser)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    check.finish()


if __name__ == "__main__":
    main()
