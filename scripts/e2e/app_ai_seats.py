"""App AI seats in the play UI (2026-10-05).

사용자 요청 "이제 app ai를 플레이 ui에 넣자".

The Steam app's computer opponent (registry kinds ``app_ai`` = Hard,
``app_ai_medium``, ``app_ai_easy``; src/dune_imperium/agents/app_ai/) is
offered as three plain rows of the setup screen's seat list, right after
"human", and is the open server's default AI seat. It decides on the server
inside the human's own request, like every AI seat, so the browser sees it
only through its labels; those are what this checks, around a whole game.

[S] Setup: an open server defaults to human + three app_ai, every rule box
    the UI checks by default stays checked (leader draft, CHOAM, promo,
    Bloodlines, Tech, Immortality, Go to 11, Epic; Scouts off), the three
    rows follow "human" in both languages, and the start button posts
    exactly the chosen kinds.
[G] One human seat against app_ai / app_ai_medium / app_ai_easy with those
    default options and a fixed seed, played with applyAction(0) /
    confirmTurn(): one POST + one snapshot per human step, the seats echo the
    kinds, and the seat badges and log turn heads show the labels (never the
    raw ids) in Korean and in English. At 1366x768 the seat head is nowrap:
    every app AI badge must stay whole inside it and be no wider than the
    longest label shipped before (rollout_strong's). The width left to the
    leader name (cut with an ellipsis; its hover card has it whole) is only
    printed, beside the width the old default "Heuristic AI" would take.
[L] A mid-game save from the header, the game and save lists naming the
    labels in both languages, a load from the list that comes back at the
    same decision and is played to the end. Restore regenerates every app_ai
    step (memory and RNG with it), so that finish must equal the original
    game's, played on from the save point over raw HTTP the same way.
[E] The finished game: standings and the winner banner in both languages,
    and the review's seat select naming the labels in both languages.
[R] A --remote room created with app_ai seats shows the labels in the lobby
    in both languages, while a remote room's own defaults stay all human.
Every page: no JS errors; neither server logs a Traceback or ERROR, and the
open server's log holds nothing but uvicorn's INFO lines (an app AI fallback
warning would add one). `E2E_SHOTS_DIR` keeps the seat column at 1366x768 in
both languages (app_ai_seats_1366_ko.png / _en.png).
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Any

from common import (
    LAPTOP_VIEWPORT,
    SERVER_LOG_COPY,
    Check,
    chrome,
    client_state,
    now,
    open_context,
    server,
    set_rule_options,
)
from open_mode import create_game, settled

check = Check()

SEED = 20261005
KINDS = ["human", "app_ai", "app_ai_medium", "app_ai_easy"]
LABELS = {
    "ko": {
        "human": "사람",
        "app_ai": "앱 AI·어려움",
        "app_ai_medium": "앱 AI·보통",
        "app_ai_easy": "앱 AI·쉬움",
    },
    "en": {
        "human": "Human",
        "app_ai": "App AI·Hard",
        "app_ai_medium": "App AI·Medium",
        "app_ai_easy": "App AI·Easy",
    },
}
# The longest seat label shipped before the app AI rows: the nowrap seat head
# at 1366x768 has carried it since 2026-09-27 (style.css, max-height 960px).
LONGEST_EARLIER = {
    "ko": "강한 롤아웃 탐색 AI (느림)",
    "en": "Strong Rollout Search AI (slow)",
}
# The open server's default AI label before the app AI took its place.
PREVIOUS_DEFAULT = {"ko": "휴리스틱 AI", "en": "Heuristic AI"}
# The boxes index.html opens checked; Scouts opens unchecked.
DEFAULT_BOXES = (
    "leader-draft",
    "choam",
    "promo",
    "bloodlines",
    "tech",
    "immortality",
    "go-to-11",
    "epic-game",
)
SAVE_AT = 60  # human steps before the mid-game save
SAVE_NAME = "AppAIMidGame"
KEY = "e2e-admin-key"
HANGUL = "[\\uac00-\\ud7a3]"


def set_language(page, lang: str) -> None:
    if page.evaluate("document.documentElement.lang") != lang:
        page.click("#language-toggle")
    page.wait_for_function(f"document.documentElement.lang === '{lang}'")


def expected_list(lang: str) -> str:
    return ", ".join(LABELS[lang][kind] for kind in KINDS)


# Any raw registry id on screen means a label fell back to the kind string
# (core.js seatKindLabel). Visible text, option text and the names screen
# readers get (title / aria-label) all count.
RAW_ID_JS = """() => {
    const hits = [];
    const look = (text, where) => {
        if (String(text || '').includes('app_ai')) hits.push([where, String(text)]);
    };
    look(document.body.innerText, 'body');
    for (const el of document.querySelectorAll('option')) {
        look(el.textContent, 'option');
    }
    for (const el of document.querySelectorAll('[title], [aria-label]')) {
        look(el.getAttribute('title'), `${el.id || el.className || el.tagName}@title`);
        look(el.getAttribute('aria-label'),
             `${el.id || el.className || el.tagName}@aria-label`);
    }
    return hits.slice(0, 5);
}"""

SEAT_BADGES_JS = """() => [1, 2, 3].map((seat) => {
    const card = document.querySelector(`#seats article.seat[data-seat='${seat}']`);
    const badge = card && card.querySelector('.who .badge.ai');
    return badge ? [badge.textContent, badge.title] : null;
})"""

# Pairs of (seat, badge text) of every AI turn head in the log.
LOG_HEADS_JS = """() => [...document.querySelectorAll('#action-log .turn-head')]
    .map((head) => {
        const mark = head.querySelector('.seat-mark');
        const badge = head.querySelector('.badge.ai');
        return badge && mark ? [Number(mark.dataset.seat), badge.textContent] : null;
    })
    .filter((pair) => pair !== null)"""

# The seat head at 1366x768: nowrap, so a badge too long would squeeze the
# leader name or run out of the head. `longest` is the earlier longest label
# measured in the same place (a probe badge, removed again).
SEAT_HEAD_JS = """([longestLabel, previousDefault]) => [1, 2, 3].map((seat) => {
    const card = document.querySelector(`#seats article.seat[data-seat='${seat}']`);
    const who = card.querySelector('.who');
    const badge = who.querySelector('.badge.ai');
    const name = who.querySelector('.leader-name');
    const whoBox = who.getBoundingClientRect();
    const box = badge.getBoundingClientRect();
    const result = {
        seat,
        text: badge.textContent,
        wrap: getComputedStyle(who).flexWrap,
        width: Math.round(box.width),
        clipped: badge.scrollWidth > badge.clientWidth + 1,
        inside: box.left >= whoBox.left - 1 && box.right <= whoBox.right + 1,
        oneLine: box.height
            <= 2 * parseFloat(getComputedStyle(badge).lineHeight || '20'),
        overflow: who.scrollWidth > who.clientWidth + 1,
        name: name.textContent,
        nameWidth: Math.round(name.getBoundingClientRect().width),
    };
    const probe = badge.cloneNode();
    who.appendChild(probe);
    probe.textContent = longestLabel;
    result.longest = Math.round(probe.getBoundingClientRect().width);
    probe.textContent = previousDefault;
    result.previous = Math.round(probe.getBoundingClientRect().width);
    probe.remove();
    result.first = !!who.querySelector('.badge:not(.ai)');
    return result;
})"""


def api_json(base: str, path: str, body: dict[str, Any] | None = None) -> Any:
    request = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def finish_over_http(base: str, game_id: str) -> tuple[dict[str, Any], int]:
    """Play seat 0 the browser's way (index 0, or confirm) to the end."""
    summary = api_json(base, f"/games/{game_id}")
    steps = 0
    while not summary["finished"] and steps < 3000:
        body = {
            "seat": 0,
            "revision": summary["revision"],
            "undo_count": summary["undo_count"],
        }
        if summary["confirmation"] is not None:
            summary = api_json(base, f"/games/{game_id}/confirm", body)
        else:
            summary = api_json(base, f"/games/{game_id}/actions", {**body, "index": 0})
        steps += 1
    return summary, steps


def play(page, rec, label: str, stop_at: int | None = None) -> int:
    """Seat 0's steps until the game ends (or ``stop_at`` steps), checking
    the request count and the log length after every step."""
    since = now()
    steps = 0
    mismatches = []
    started = now()
    while True:
        snap = client_state(page)
        if snap["finished"] or steps >= 3000:
            break
        if stop_at is not None and steps >= stop_at:
            break
        if snap["confirmation"] is not None:
            page.evaluate("confirmTurn()")
        else:
            page.evaluate("applyAction(0)")
        if not settled(page, 20):
            print("  NOT SETTLED", json.dumps(client_state(page), ensure_ascii=False))
            rec.dump(since=now() - 12)
            check.ok(False, f"{label}: every step settles")
            check.finish()
        steps += 1
        after = client_state(page)
        if after["logLen"] != after["logCount"]:
            mismatches.append((steps, after["logLen"], after["logCount"]))
        if after["error"]:
            check.ok(False, f"{label}: no error banner", after["error"])
            check.finish()
    posts = rec.count("POST", "games/", since)
    snaps = rec.count("GET", "/snapshot", since)
    print(
        f"  .. {label}: {steps} steps in {now() - started:.1f}s,"
        f" POST {posts}, snapshot {snaps}"
    )
    check.ok(posts == steps, f"{label}: one POST per human step", (posts, steps))
    check.ok(snaps == steps, f"{label}: one snapshot per human step", (snaps, steps))
    check.ok(
        not mismatches,
        f"{label}: client log length == server log_count after every step",
        mismatches[:5],
    )
    return steps


def check_setup(base, browser) -> None:
    print("[S] setup screen: rows, defaults and the posted kinds")
    _, page, _ = open_context(browser, "setup")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_function(
        "state.server !== null"
        " && document.querySelectorAll('#seat-selects select').length === 4"
    )
    values = page.evaluate(
        "[...document.querySelectorAll('#seat-selects select')].map((s) => s.value)"
    )
    check.ok(
        values == ["human", "app_ai", "app_ai", "app_ai"],
        "the open server seats one human against three app AIs (Hard)",
        values,
    )
    boxes = page.evaluate(
        """() => Object.fromEntries([...document.querySelectorAll(
            '#rule-options input[type=checkbox]')].map(
            (box) => [box.id.slice(4), box.checked && !box.disabled]))"""
    )
    check.ok(
        all(boxes.get(name) for name in DEFAULT_BOXES) and boxes.get("scouts") is False,
        "every rule box but Scouts opens checked",
        boxes,
    )
    for lang in ("ko", "en"):
        set_language(page, lang)
        rows = page.evaluate(
            """() => [...document.querySelectorAll(
                "#seat-selects select[data-seat='1'] option")].map(
                (o) => [o.value, o.textContent])"""
        )
        check.ok(
            rows[:4] == [[kind, LABELS[lang][kind]] for kind in KINDS],
            f"{lang}: the three app AI rows follow 'human' in the seat list",
            rows[:5],
        )
        check.ok(
            page.evaluate(
                "[...document.querySelectorAll('#seat-selects select')]"
                ".map((s) => s.value).join()"
            )
            == "human,app_ai,app_ai,app_ai",
            f"{lang}: a language switch keeps the chosen seats",
        )
    set_language(page, "ko")
    check.ok(
        page.inner_text("#setup-summary") == "사람 1명 · AI 3명 · 규칙 옵션 8개 선택",
        "the summary counts the app AIs as AI and the eight default boxes",
        page.inner_text("#setup-summary"),
    )
    page.context.close()


def scenario_game(base, browser) -> None:
    print("[G] one human against app_ai / app_ai_medium / app_ai_easy")
    _, page, rec = open_context(browser, "table")
    with page.expect_request(
        lambda request: request.method == "POST" and request.url.endswith("/games")
    ) as sent:
        game_id = create_game(page, base, seed=SEED, kinds=KINDS, options=None)
    payload = sent.value.post_data_json
    check.ok(
        payload["seats"] == KINDS
        and payload["game_seed"] == SEED
        and all(
            payload[key]
            for key in (
                "leader_draft",
                "choam_module",
                "promo_cards",
                "bloodlines",
                "tech_module",
                "immortality",
                "go_to_11",
                "epic_game",
            )
        )
        and payload["arrakeen_scouts"] is False,
        "the start button posts the chosen kinds with the default options",
        payload,
    )
    check.ok(
        page.evaluate("state.summary.seats") == KINDS,
        "the summary echoes the seat kinds",
        page.evaluate("state.summary.seats"),
    )
    check.ok(
        page.evaluate("state.summary.players.map((p) => p.kind)") == KINDS,
        "the players carry the seat kinds",
    )
    check.ok(page.evaluate("state.me.seats") == [0], "this browser plays seat 0 only")

    play(page, rec, "before the save", stop_at=SAVE_AT)
    check_labels_on_table(page, "mid-game")
    check_laptop_head(browser, base, game_id)

    print("[L] save mid-game, the lists, load and continue")
    before = page.evaluate(
        """() => ({
            log: state.summary.log_count,
            round: state.summary.round_number,
            decision: state.summary.decision,
            confirmation: state.summary.confirmation,
            actions: state.actions ? state.actions.actions.map((a) => JSON.stringify(a))
                : null,
        })"""
    )
    page.once("dialog", lambda dialog: dialog.accept(SAVE_NAME))
    page.click("#save-game")
    page.wait_for_function(
        f"!document.getElementById('game-note').hidden"
        f" && document.getElementById('game-note').textContent.includes('{SAVE_NAME}')"
    )
    page.click("#leave-game")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_selector(f"#save-list li:has-text('{SAVE_NAME}')")
    page.wait_for_selector("#game-list li")
    for lang in ("ko", "en"):
        set_language(page, lang)
        listed = expected_list(lang)
        page.wait_for_function(
            """(want) => {
                const rows = (id) => [...document.querySelectorAll(`#${id} li`)]
                    .map((li) => li.textContent);
                return rows('game-list').some((t) => t.includes(want))
                    && rows('save-list').some((t) => t.includes(want));
            }""",
            arg=listed,
            timeout=5000,
        )
        check.ok(True, f"{lang}: the game and save lists name the seats ({listed})")
        check.ok(
            not page.evaluate(RAW_ID_JS),
            f"{lang}: no raw app_ai id on the setup screen",
            page.evaluate(RAW_ID_JS),
        )
    set_language(page, "ko")
    page.wait_for_selector(f"#save-list li:has-text('{SAVE_NAME}') button")
    page.click(f"#save-list li:has-text('{SAVE_NAME}') button:has-text('불러오기')")
    page.wait_for_function(
        f"state.gameId !== null && state.gameId !== '{game_id}'"
        " && state.view !== null && refreshFlight === null"
    )
    loaded_id = page.evaluate("state.gameId")
    after = page.evaluate(
        """() => ({
            log: state.summary.log_count,
            round: state.summary.round_number,
            decision: state.summary.decision,
            confirmation: state.summary.confirmation,
            actions: state.actions ? state.actions.actions.map((a) => JSON.stringify(a))
                : null,
        })"""
    )
    check.ok(
        after == before,
        "the loaded game rests on the saved decision with the same actions",
        (before["log"], after["log"], before["decision"], after["decision"]),
    )
    check.ok(
        page.evaluate("state.summary.seats") == KINDS,
        "the loaded game keeps the seat kinds",
    )
    play(page, rec, "after the load")
    check.ok(client_state(page)["finished"], "the loaded game finished")

    original, http_steps = finish_over_http(base, game_id)
    loaded = api_json(base, f"/games/{loaded_id}")
    print(f"  .. the original game played on over HTTP: {http_steps} steps")
    check.ok(
        original["finished"] and original["standings"] == loaded["standings"],
        "the loaded game ends exactly like the original played on",
        (original.get("standings"), loaded.get("standings")),
    )
    original_log = api_json(base, f"/games/{game_id}/log?seat=0")["entries"]
    loaded_log = api_json(base, f"/games/{loaded_id}/log?seat=0")["entries"]
    check.ok(
        original_log == loaded_log,
        "... and with the same log, every app AI step included",
        (len(original_log), len(loaded_log)),
    )

    check_finished(page)
    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])


def check_labels_on_table(page, label: str) -> None:
    for lang in ("ko", "en"):
        set_language(page, lang)
        page.wait_for_function("refreshFlight === null")
        badges = page.evaluate(SEAT_BADGES_JS)
        want = [[LABELS[lang][k], LABELS[lang][k]] for k in KINDS[1:]]
        check.ok(
            badges == want,
            f"{label} {lang}: the seat panels badge each app AI seat by level",
            badges,
        )
        heads = page.evaluate(LOG_HEADS_JS)
        wrong = [
            (seat, text) for seat, text in heads if text != LABELS[lang][KINDS[seat]]
        ]
        check.ok(
            {seat for seat, _ in heads} == {1, 2, 3} and not wrong,
            f"{label} {lang}: every AI turn head in the log names its seat's level",
            (len(heads), wrong[:3]),
        )
        raw = page.evaluate(RAW_ID_JS)
        check.ok(not raw, f"{label} {lang}: no raw app_ai id on the table", raw)
    set_language(page, "ko")


def check_laptop_head(browser, base: str, game_id: str) -> None:
    """Measure the seat heads at 1366x768 in a second page on the game."""
    context, page, _ = open_context(browser, "laptop", LAPTOP_VIEWPORT)
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    for lang in ("ko", "en"):
        set_language(page, lang)
        page.wait_for_function("refreshFlight === null")
        heads = page.evaluate(
            SEAT_HEAD_JS, [LONGEST_EARLIER[lang], PREVIOUS_DEFAULT[lang]]
        )
        print(
            f"  .. 1366x768 {lang}: "
            + "; ".join(
                f"{h['text']} {h['width']}px (heuristic {h['previous']}px,"
                f" longest {h['longest']}px), name {h['name']!r} {h['nameWidth']}px"
                f"{' +first' if h['first'] else ''}"
                for h in heads
            )
        )
        if shots := os.environ.get("E2E_SHOTS_DIR"):
            Path(shots).mkdir(parents=True, exist_ok=True)
            page.locator("#seats").screenshot(
                path=str(Path(shots) / f"app_ai_seats_1366_{lang}.png")
            )
        check.ok(
            all(h["wrap"] == "nowrap" for h in heads),
            f"1366x768 {lang}: the seat head is the nowrap one",
            [h["wrap"] for h in heads],
        )
        check.ok(
            [h["text"] for h in heads] == [LABELS[lang][k] for k in KINDS[1:]],
            f"1366x768 {lang}: the badges name the levels",
        )
        bad = [
            h
            for h in heads
            if h["clipped"] or not h["inside"] or not h["oneLine"] or h["overflow"]
        ]
        check.ok(
            not bad,
            f"1366x768 {lang}: every app AI badge stays whole on the head's line",
            bad[:2],
        )
        check.ok(
            all(h["width"] <= h["longest"] for h in heads),
            f"1366x768 {lang}: no app AI badge is wider than the longest earlier label",
            [(h["width"], h["longest"]) for h in heads],
        )
    context.close()


def check_finished(page) -> None:
    print("[E] the finished game: standings, banner, review seat select")
    page.wait_for_function("state.summary.finished && refreshFlight === null")
    for lang in ("ko", "en"):
        set_language(page, lang)
        page.wait_for_function("refreshFlight === null")
        standings = page.inner_text("#standings")
        check.ok(
            all(LABELS[lang][kind] in standings for kind in KINDS[1:]),
            f"{lang}: the standings name the three app AI seats by level",
            standings[:200],
        )
        winner = page.evaluate(
            "playerLabel(state.summary.standings.find((e) => e.rank === 1).player)"
        )
        banner = page.inner_text("#decision-info .prompt").strip()
        check.ok(
            winner in banner, f"{lang}: the finished banner names the winner", banner
        )
        raw = page.evaluate(RAW_ID_JS)
        check.ok(not raw, f"{lang}: no raw app_ai id on the finished table", raw)
    set_language(page, "ko")
    page.click("#standings button:has-text('리플레이 검토')")
    page.wait_for_function("state.review !== null && state.review.phase !== null")
    for lang in ("ko", "en"):
        set_language(page, lang)
        options = page.evaluate(
            "[...document.querySelectorAll('#review-seat option')]"
            ".map((o) => [o.value, o.textContent])"
        )
        want = [
            [str(seat), f"({LABELS[lang][kind]})"] for seat, kind in enumerate(KINDS)
        ]
        check.ok(
            len(options) == 4
            and all(
                value == wv and text.endswith(wt)
                for (value, text), (wv, wt) in zip(options, want, strict=True)
            ),
            f"{lang}: the review seat select names every seat's kind",
            options,
        )
        raw = page.evaluate(RAW_ID_JS)
        check.ok(not raw, f"{lang}: no raw app_ai id in the review", raw)
        if lang == "en":
            hangul = page.evaluate(
                f"""() => [...document.querySelectorAll(
                    '#review-seat option, #seats .badge.ai')]
                    .map((e) => e.textContent).filter((t) => /{HANGUL}/.test(t))"""
            )
            check.ok(not hangul, "en: no Hangul in the AI labels", hangul[:3])
    set_language(page, "ko")
    page.click("#review-exit")
    page.wait_for_function("state.review === null && refreshFlight === null")


def scenario_remote(browser) -> None:
    print("[R] a --remote room with app AI seats: the lobby badges")
    with server("--remote", "--admin-key", KEY) as (base, server_log):
        _, host, rec = open_context(browser, "host")
        host.goto(f"{base}/#admin={KEY}")
        host.wait_for_selector("#setup-screen:not([hidden])")
        host.wait_for_function(
            "state.server !== null"
            " && document.querySelectorAll('#seat-selects select').length === 4"
        )
        defaults = host.evaluate(
            "[...document.querySelectorAll('#seat-selects select')].map((s) => s.value)"
        )
        check.ok(
            defaults == ["human"] * 4,
            "a remote room still starts with four human seats",
            defaults,
        )
        for seat, kind in enumerate(KINDS):
            host.select_option(f"#seat-selects select[data-seat='{seat}']", kind)
        set_rule_options(host)
        host.click("#create-game")
        host.wait_for_selector("#lobby-screen:not([hidden])")
        check.ok(
            host.evaluate("state.summary.players.map((p) => p.kind)") == KINDS,
            "the remote room publishes the app AI kinds unchanged",
        )
        for lang in ("ko", "en"):
            set_language(host, lang)
            badges = host.evaluate(
                """() => [1, 2, 3].map((seat) => {
                    const badge = document.querySelector(
                        `#lobby-seats li[data-seat='${seat}'] .badge.ai`);
                    return badge ? badge.textContent : null;
                })"""
            )
            check.ok(
                badges == [LABELS[lang][kind] for kind in KINDS[1:]],
                f"{lang}: the lobby badges name the app AI levels",
                badges,
            )
            raw = host.evaluate(RAW_ID_JS)
            check.ok(not raw, f"{lang}: no raw app_ai id in the lobby", raw)
        failed = [r for r in rec.requests if r[3] >= 400]
        check.ok(not failed, "no failed requests in the remote room", failed[:5])
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            "no server errors on the remote server",
        )


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            check_setup(base, browser)
            scenario_game(base, browser)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
        # The server configures no handler for its own loggers, so an app AI
        # fallback warning or error reaches the log through logging's last
        # resort as a bare message line: anything but uvicorn's INFO lines
        # and the CLI's own startup line about the search AI.
        stray = [
            line
            for line in text.splitlines()
            if not line.startswith(("INFO:", "search AI:"))
        ]
        check.ok(
            not stray,
            "the server log holds only uvicorn's INFO lines (no app AI warning)",
            stray[:3],
        )
        scenario_remote(browser)
    check.finish()


if __name__ == "__main__":
    main()
