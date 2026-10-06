"""Search AI seats in the play UI (2026-10-06).

The policy-guided search (``search:<path>``, NetworkSearchAgent) thinks on
the server's worker thread, about 1.4s a searched decision (p90 3.3s) on the
UI's default rules, ringing the doorbell after every step. The browser picks
it as the bare kind ``search`` where the server was started with a network
(``--search-checkpoint``; ``/whoami`` search_ai), and shows which seat is
thinking. This script writes a tiny untrained network to a temp dir (the
same file the server tests use, ``tests/server/test_search_seats.py``) and
links it the way a host links ``checkpoints/play/search.pt``. With the full
default search (five candidates in eight worlds) one hand-over of three such
seats takes a few seconds, long enough to watch.

[N] A server whose --search-checkpoint names no file says so at startup,
    answers search_ai false, offers no "탐색 AI" row, and refuses a raw
    "search" seat with a pointer to the flag.
[S] With a network: the startup line names the file the link points at,
    the row "탐색 AI" / "Search AI" follows the three app AI rows (the
    defaults stay human + three app AI), picking it shows the note under the
    seats in both languages, and the start button posts "search".
[G] Human + three search seats with the setup screen's default rules, at
    1366x768 with a 1600x1000 page following the same game. Every hand-over
    to the search seats comes back to the human; while a seat thinks, both
    pages mark exactly that seat: its badge reads "생각 중…" / "Thinking…"
    and the banner says it is thinking; the help dialog opens and closes;
    and the badge keeps the seat card's and its head's height (a mark beside
    the badge cut the Leader name to 5px at 1366x768 and took a third line
    at 1600px).
    Badges and log heads say "탐색 AI" / "Search AI", never the path: the
    temp dir's name appears nowhere in either page's text or attributes.
[M] A missed ring: the page is held busy (rings dropped, as during its own
    request) until the server has finished every search step, then
    released; with no ring left to come, the thinking re-check alone must
    bring the page back to the human's turn.
[L] A save from the header, the lists naming the seats, a load that comes
    back within a few seconds at the same decision, and one more hand-over
    played on from it.
Every page: no JS errors; the server logs no Traceback, ERROR or failing
search. `E2E_SHOTS_DIR` keeps the seat column and the 1366x768 page while a
seat thinks (search_seats_thinking_<lang>.png, search_seats_table_<lang>.png).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from common import (
    DEFAULT_VIEWPORT,
    LAPTOP_VIEWPORT,
    REPO,
    SERVER_LOG_COPY,
    Check,
    chrome,
    now,
    open_context,
    server,
)
from open_mode import create_game, settled

check = Check()

SEED = 20261006
KINDS = ["human", "search", "search", "search"]
LABELS = {
    "ko": {"human": "사람", "search": "탐색 AI"},
    "en": {"human": "Human", "search": "Search AI"},
}
APP_AI_ROWS = {
    "ko": [
        ["human", "사람"],
        ["app_ai", "앱 AI·어려움"],
        ["app_ai_medium", "앱 AI·보통"],
        ["app_ai_easy", "앱 AI·쉬움"],
    ],
    "en": [
        ["human", "Human"],
        ["app_ai", "App AI·Hard"],
        ["app_ai_medium", "App AI·Medium"],
        ["app_ai_easy", "App AI·Easy"],
    ],
}
NOTE = {
    "ko": "탐색 AI는 학습한 망으로 몇 수 앞을 두어 보고 고릅니다. 한 결정에 보통 "
    "1–3초 걸리고, 생각하는 동안에도 화면은 움직입니다.",
    "en": "The Search AI tries a few moves ahead with its trained network before "
    "it picks one. A decision usually takes 1–3 seconds, and the page keeps "
    "responding while it thinks.",
}
THINKING_MARK = {"ko": "생각 중…", "en": "Thinking…"}
THINKING_PROMPT = {"ko": "생각 중…", "en": "is thinking…"}
# The longest seat label shipped before (app_ai_seats.py): the nowrap seat
# head at 1366x768 has carried it since 2026-09-27.
LONGEST_EARLIER = {
    "ko": "강한 롤아웃 탐색 AI (느림)",
    "en": "Strong Rollout Search AI (slow)",
}
SAVE_NAME = "SearchMidGame"
HANGUL = "[\\uac00-\\ud7a3]"
PHASE_TIMEOUT = 180.0

CHECKPOINT_PY = """
import sys
from pathlib import Path

import torch

from dune_imperium import RulesetConfig
from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.training.checkpoint import save_checkpoint
from dune_imperium.training.network import PolicyValueNetwork

base = RulesetConfig()
codec = ActionCodec(base)
torch.manual_seed(0)
save_checkpoint(
    Path(sys.argv[1]),
    PolicyValueNetwork(codec.size, hidden=(32,)),
    ruleset=base.identifier,
    iteration=1,
    codec=codec,
)
"""


def write_checkpoint(workdir: Path) -> tuple[Path, Path]:
    """The network under checkpoints/, and a link to it like a host's."""
    real = workdir / "checkpoints" / "l3-e2e.pt"
    real.parent.mkdir()
    subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", CHECKPOINT_PY, str(real)],
        cwd=REPO,
        check=True,
    )
    link = workdir / "search.pt"
    link.symlink_to(real)
    return real.resolve(), link


def set_language(page, lang: str) -> None:
    if page.evaluate("document.documentElement.lang") != lang:
        page.click("#language-toggle")
    page.wait_for_function(f"document.documentElement.lang === '{lang}'")


def api(base: str, path: str, body: dict[str, Any] | None = None) -> Any:
    request = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


# Every place a path could leak: visible text, every attribute of every
# element, and form values. `needles` are the temp dir's name and the raw
# kind prefix.
LEAK_JS = """(needles) => {
    const hits = [];
    const look = (text, where) => {
        const value = String(text || '');
        for (const needle of needles) {
            if (value.includes(needle)) hits.push([where, value.slice(0, 120)]);
        }
    };
    look(document.body.innerText, 'body');
    for (const el of document.querySelectorAll('*')) {
        const where = `${el.tagName}.${el.id || el.className}`;
        for (const attribute of el.attributes) {
            look(attribute.value, `${where}@${attribute.name}`);
        }
        if ('value' in el && typeof el.value === 'string') {
            look(el.value, `${where}#value`);
        }
    }
    return hits.slice(0, 5);
}"""

SEAT_BADGES_JS = """() => [1, 2, 3].map((seat) => {
    const card = document.querySelector(`#seats article.seat[data-seat='${seat}']`);
    const badge = card && card.querySelector('.who .badge.ai');
    return badge ? [badge.textContent, badge.title] : null;
})"""

LOG_HEADS_JS = """() => [...document.querySelectorAll('#action-log .turn-head')]
    .map((head) => {
        const mark = head.querySelector('.seat-mark');
        const badge = head.querySelector('.badge.ai');
        return badge && mark ? [Number(mark.dataset.seat), badge.textContent] : null;
    })
    .filter((pair) => pair !== null)"""

# What the page shows of a thinking seat, read in one go. Only a page that is
# neither busy nor refreshing has drawn the summary it holds.
SHOWN_JS = """() => ({
    thinking: state.summary ? state.summary.thinking : null,
    mine: isMyTurn(state.summary),
    finished: state.summary ? state.summary.finished : null,
    confirmation: state.summary ? state.summary.confirmation : null,
    drawn: !state.busy && refreshFlight === null,
    marks: [...document.querySelectorAll('#seats article.seat .badge.thinking')].map(
        (mark) => [
            Number(mark.closest('article.seat').dataset.seat),
            mark.textContent,
        ]),
    prompt: (document.querySelector('#decision-info .prompt') || {}).textContent || '',
    label: state.summary && state.summary.thinking !== null
        ? playerLabel(state.summary.thinking) : null,
})"""

# The seat head at 1366x768 is nowrap: the badge must stay whole on it.
BADGE_HEAD_JS = """(longestLabel) => [1, 2, 3].map((seat) => {
    const card = document.querySelector(`#seats article.seat[data-seat='${seat}']`);
    const who = card.querySelector('.who');
    const badge = who.querySelector('.badge.ai');
    const whoBox = who.getBoundingClientRect();
    const box = badge.getBoundingClientRect();
    const probe = badge.cloneNode();
    who.appendChild(probe);
    probe.textContent = longestLabel;
    const longest = Math.round(probe.getBoundingClientRect().width);
    probe.remove();
    return {
        seat,
        text: badge.textContent,
        wrap: getComputedStyle(who).flexWrap,
        width: Math.round(box.width),
        longest,
        clipped: badge.scrollWidth > badge.clientWidth + 1,
        inside: box.left >= whoBox.left - 1 && box.right <= whoBox.right + 1,
        overflow: who.scrollWidth > who.clientWidth + 1,
    };
})"""

# The thinking badge of one seat: whole, inside its head, and the card, the
# head and the Leader name about as big with it as with the kind's label
# (measured by putting the label back for a moment; the title holds it).
MARK_LAYOUT_JS = """(seat) => {
    const card = document.querySelector(`#seats article.seat[data-seat='${seat}']`);
    const who = card && card.querySelector('.who');
    const badge = who && who.querySelector('.badge.ai.thinking');
    if (!badge) return null;
    const name = who.querySelector('.leader-name');
    const measure = () => ({
        card: card.getBoundingClientRect().height,
        head: who.getBoundingClientRect().height,
        name: Math.round(name.getBoundingClientRect().width),
        badge: Math.round(badge.getBoundingClientRect().width),
    });
    const whoBox = who.getBoundingClientRect();
    const box = badge.getBoundingClientRect();
    const result = {
        inside: box.left >= whoBox.left - 1 && box.right <= whoBox.right + 1,
        overflow: who.scrollWidth > who.clientWidth + 1,
        clipped: badge.scrollWidth > badge.clientWidth + 1,
        with: measure(),
    };
    const text = badge.textContent;
    badge.classList.remove('thinking');
    badge.textContent = badge.title;
    result.without = measure();
    badge.textContent = text;
    badge.classList.add('thinking');
    return result;
}"""


def no_leak(page, needles: list[str], label: str) -> None:
    hits = page.evaluate(LEAK_JS, needles)
    check.ok(not hits, f"{label}: no checkpoint path or raw search: kind", hits)


# --- [N] a server without a network -----------------------------------------


def scenario_without(browser, workdir: Path) -> None:
    print("[N] a server whose checkpoint is missing offers no search AI")
    missing = workdir / "missing.pt"
    with server("--search-checkpoint", str(missing)) as (base, server_log):
        startup = server_log.read_text()
        check.ok(
            f"search AI: off (no file at {missing.resolve()})" in startup,
            "the startup line says the search AI is off and why",
            [line for line in startup.splitlines() if "search AI" in line],
        )
        _, page, _ = open_context(browser, "without")
        page.goto(base + "/")
        page.wait_for_selector("#setup-screen:not([hidden])")
        page.wait_for_function(
            "state.server !== null"
            " && document.querySelectorAll('#seat-selects select').length === 4"
        )
        check.ok(
            page.evaluate("state.server.search_ai") is False,
            "/whoami: search_ai false",
        )
        offered = page.evaluate(
            "[...document.querySelectorAll('#seat-selects option')]"
            ".filter((o) => o.value === 'search').length"
        )
        check.ok(offered == 0, "no seat list offers the search AI", offered)
        try:
            api(base, "/games", {"seats": KINDS})
            refused = None
        except urllib.error.HTTPError as error:
            refused = (error.code, json.loads(error.read()).get("detail", ""))
        check.ok(
            refused is not None
            and refused[0] == 400
            and "--search-checkpoint" in refused[1],
            "a raw 'search' seat is refused with a pointer to the flag",
            refused,
        )
        page.context.close()


# --- [S] the setup screen ------------------------------------------------------


def check_setup(base: str, browser, needles: list[str]) -> None:
    print("[S] setup screen: the search AI row and its note")
    _, page, _ = open_context(browser, "setup")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_function(
        "state.server !== null"
        " && document.querySelectorAll('#seat-selects select').length === 4"
    )
    check.ok(page.evaluate("state.server.search_ai") is True, "/whoami: search_ai true")
    values = page.evaluate(
        "[...document.querySelectorAll('#seat-selects select')].map((s) => s.value)"
    )
    check.ok(
        values == ["human", "app_ai", "app_ai", "app_ai"],
        "the defaults stay one human against three app AIs",
        values,
    )
    check.ok(page.is_hidden("#opt-search-note"), "the note waits for a search seat")
    page.select_option("#seat-selects select[data-seat='2']", "search")
    for lang in ("ko", "en"):
        set_language(page, lang)
        rows = page.evaluate(
            """() => [...document.querySelectorAll(
                "#seat-selects select[data-seat='1'] option")].map(
                (o) => [o.value, o.textContent])"""
        )
        check.ok(
            rows[:5] == [*APP_AI_ROWS[lang], ["search", LABELS[lang]["search"]]],
            f"{lang}: the search AI row follows the app AI rows",
            rows[:6],
        )
        check.ok(
            page.evaluate("document.querySelector(\"select[data-seat='2']\").value")
            == "search",
            f"{lang}: the chosen search seat survives the language switch",
        )
        note = (
            page.inner_text("#opt-search-note")
            if page.is_visible("#opt-search-note")
            else None
        )
        check.ok(note == NOTE[lang], f"{lang}: the note under the seats", note)
        no_leak(page, needles, f"setup {lang}")
    set_language(page, "ko")
    check.ok(
        page.inner_text("#setup-summary").startswith("사람 1명 · AI 3명"),
        "the summary counts the search seat as AI",
        page.inner_text("#setup-summary"),
    )
    page.select_option("#seat-selects select[data-seat='2']", "app_ai")
    check.ok(
        page.is_hidden("#opt-search-note"), "the note goes with the last search seat"
    )
    page.context.close()


# --- [G] [M] [L] a game ---------------------------------------------------------


class Watch:
    """What the AI phases have shown so far, over every check."""

    def __init__(self) -> None:
        self.phases = 0
        self.observed = 0
        self.wrong: list[object] = []
        self.help_done = False
        self.layout: dict[str, list[dict[str, Any]]] = {"laptop": [], "wide": []}
        self.langs: set[str] = set()


def observe(page, name: str, lang: str, watch: Watch) -> dict[str, Any]:
    shown = page.evaluate(SHOWN_JS)
    if shown["drawn"] and shown["thinking"] is not None:
        seat = shown["thinking"]
        watch.observed += 1
        watch.langs.add(lang)
        right_mark = shown["marks"] == [[seat, THINKING_MARK[lang]]]
        right_prompt = (
            shown["prompt"].startswith(shown["label"])
            and THINKING_PROMPT[lang] in shown["prompt"]
            and LABELS[lang]["search"] in shown["prompt"]
        )
        if not (right_mark and right_prompt):
            watch.wrong.append((name, lang, seat, shown["marks"], shown["prompt"]))
        if len(watch.layout[name]) < 3:
            layout = page.evaluate(MARK_LAYOUT_JS, seat)
            if layout is not None:
                watch.layout[name].append(layout)
    elif shown["drawn"] and shown["marks"]:
        watch.wrong.append((name, lang, None, shown["marks"], shown["prompt"]))
    return shown


def try_help(page, watch: Watch) -> None:
    """Open and close the help dialog while a search seat thinks."""
    if watch.help_done or page.evaluate("state.summary.thinking") is None:
        return
    started = now()
    page.click("#open-help")
    page.wait_for_selector("#help:not([hidden])", timeout=3000)
    page.keyboard.press("Escape")
    page.wait_for_selector("#help", state="hidden", timeout=3000)
    took = now() - started
    check.ok(
        took < 2.0,
        f"the help dialog opens and closes while a seat thinks ({took:.2f}s)",
        took,
    )
    watch.help_done = True


def ai_phase(page, wide, lang: str, watch: Watch, label: str, shots: bool) -> None:
    """Watch the search seats until the decision is back with the human."""
    watch.phases += 1
    started = time.monotonic()
    shot = False
    while time.monotonic() - started < PHASE_TIMEOUT:
        shown = observe(page, "laptop", lang, watch)
        observe(wide, "wide", lang, watch)
        if shown["drawn"] and shown["thinking"] is not None:
            try_help(page, watch)
            if shots and not shot and (directory := os.environ.get("E2E_SHOTS_DIR")):
                Path(directory).mkdir(parents=True, exist_ok=True)
                page.locator("#seats").screenshot(
                    path=str(Path(directory) / f"search_seats_thinking_{lang}.png")
                )
                page.screenshot(
                    path=str(Path(directory) / f"search_seats_table_{lang}.png")
                )
                shot = True
        if shown["drawn"] and (shown["mine"] or shown["finished"]):
            print(
                f"  .. {label}: back to the human in {time.monotonic() - started:.1f}s"
            )
            return
        time.sleep(0.04)
    check.ok(
        False, f"{label}: the search seats hand the turn back", page.evaluate(SHOWN_JS)
    )
    check.finish()


def human_step(page) -> None:
    shown = page.evaluate(SHOWN_JS)
    if shown["confirmation"] is not None:
        page.evaluate("confirmTurn()")
    else:
        page.evaluate("applyAction(0)")
    if not settled(page, 30):
        check.ok(False, "every human step settles", page.evaluate(SHOWN_JS))
        check.finish()


def play_phases(
    page, wide, lang: str, watch: Watch, phases: int, shots: bool = False
) -> None:
    """Seat 0 plays action 0 until ``phases`` hand-overs have come back."""
    done = 0
    for _ in range(2000):
        if done >= phases:
            return
        shown = page.evaluate(SHOWN_JS)
        if shown["finished"]:
            return
        if shown["thinking"] is not None or not shown["mine"]:
            ai_phase(
                page, wide, lang, watch, f"{lang} hand-over {watch.phases + 1}", shots
            )
            done += 1
            continue
        human_step(page)
    check.ok(False, "the game reaches its hand-overs", page.evaluate(SHOWN_JS))
    check.finish()


def check_labels(page, lang: str, needles: list[str], where: str) -> None:
    page.wait_for_function("refreshFlight === null")
    badges = page.evaluate(SEAT_BADGES_JS)
    label = LABELS[lang]["search"]
    check.ok(
        badges == [[label, label]] * 3,
        f"{where} {lang}: every seat badge says {label}, its title too",
        badges,
    )
    heads = page.evaluate(LOG_HEADS_JS)
    wrong = [(seat, text) for seat, text in heads if text != label]
    check.ok(
        {seat for seat, _ in heads} == {1, 2, 3} and not wrong,
        f"{where} {lang}: every AI turn head in the log says {label}",
        (len(heads), wrong[:3]),
    )
    no_leak(page, needles, f"{where} {lang}")
    if lang == "en":
        hangul = page.evaluate(
            f"""() => [...document.querySelectorAll(
                '#seats .badge.ai, #seats .thinking, #action-log .badge.ai')]
                .map((e) => e.textContent).filter((t) => /{HANGUL}/.test(t))"""
        )
        check.ok(not hangul, f"{where} en: no Hangul in the AI labels", hangul[:3])


def check_badge_heads(page, lang: str) -> None:
    heads = page.evaluate(BADGE_HEAD_JS, LONGEST_EARLIER[lang])
    print(
        f"  .. 1366x768 {lang}: "
        + "; ".join(
            f"{h['text']} {h['width']}px (longest {h['longest']}px)" for h in heads
        )
    )
    check.ok(
        all(h["wrap"] == "nowrap" for h in heads),
        f"1366x768 {lang}: the seat head is the nowrap one",
    )
    bad = [h for h in heads if h["clipped"] or not h["inside"] or h["overflow"]]
    check.ok(not bad, f"1366x768 {lang}: every search AI badge stays whole", bad[:2])
    check.ok(
        all(h["width"] <= h["longest"] for h in heads),
        f"1366x768 {lang}: no badge is wider than the longest earlier label",
        [(h["width"], h["longest"]) for h in heads],
    )


def check_watch(watch: Watch) -> None:
    print(
        f"  .. {watch.phases} hand-overs, {watch.observed} thinking frames observed"
        f" in {sorted(watch.langs)}"
    )
    check.ok(
        watch.observed > 0 and watch.langs == {"ko", "en"},
        "a thinking seat was observed in both languages",
        (watch.observed, watch.langs),
    )
    check.ok(
        not watch.wrong,
        "every thinking frame marks exactly the thinking seat, and the banner says so",
        watch.wrong[:3],
    )
    check.ok(watch.help_done, "the help dialog was tried while a seat thought")
    for name in ("laptop", "wide"):
        layouts = watch.layout[name]
        print(
            f"  .. {name}: "
            + "; ".join(
                f"card {m['with']['card']:.1f}/{m['without']['card']:.1f}px,"
                f" badge {m['with']['badge']}/{m['without']['badge']}px,"
                f" name {m['with']['name']}/{m['without']['name']}px"
                for m in layouts
            )
        )
        bad = [
            m
            for m in layouts
            if not m["inside"]
            or m["overflow"]
            or m["clipped"]
            or abs(m["with"]["card"] - m["without"]["card"]) > 0.5
            or abs(m["with"]["head"] - m["without"]["head"]) > 0.5
            or abs(m["with"]["name"] - m["without"]["name"]) > 16
        ]
        check.ok(
            bool(layouts) and not bad,
            f"{name}: the thinking badge stays whole and moves no seat card",
            (len(layouts), bad[:2]),
        )


def scenario_missed_ring(page, base: str, game_id: str, rec) -> None:
    """Hold the page busy through a whole AI phase, then let it go."""
    print("[M] rings dropped while busy: the thinking re-check catches up")
    for _ in range(400):
        shown = page.evaluate(SHOWN_JS)
        if shown["finished"]:
            check.ok(False, "[M] the game still runs", shown)
            return
        if shown["thinking"] is not None:
            break
        human_step(page)
    page.evaluate("state.busy = true")
    held_at = now()
    deadline = time.monotonic() + PHASE_TIMEOUT
    while api(base, f"/games/{game_id}")["thinking"] is not None:
        if time.monotonic() > deadline:
            check.ok(False, "[M] the server finishes the search steps")
            check.finish()
        time.sleep(0.1)
    page.wait_for_function("refreshFlight === null")
    time.sleep(0.5)
    stale = page.evaluate("state.summary.thinking")
    check.ok(
        stale is not None,
        "[M] held busy, the page still shows the seat thinking when the server is done",
        stale,
    )
    released = time.monotonic()
    page.evaluate("state.busy = false")
    page.wait_for_function(
        "!state.busy && refreshFlight === null && state.summary.thinking === null"
        " && isMyTurn(state.summary)",
        timeout=8000,
    )
    took = time.monotonic() - released
    check.ok(
        took < 4.0, f"[M] released, the page is back at the human's turn ({took:.1f}s)"
    )
    # No ring was left to come: the summary GET is the re-check's.
    asked = sum(
        1
        for at, verb, url, _ in rec.requests
        if verb == "GET" and url == f"games/{game_id}" and at >= held_at
    )
    check.ok(asked > 0, "[M] the re-check asked for the summary", asked)


def scenario_game(base: str, browser, needles: list[str]) -> None:
    print("[G] human + three search seats, default rules, 1366x768")
    _, page, rec = open_context(browser, "table", LAPTOP_VIEWPORT)
    with page.expect_request(
        lambda request: request.method == "POST" and request.url.endswith("/games")
    ) as sent:
        game_id = create_game(page, base, seed=SEED, kinds=KINDS, options=None)
    payload = sent.value.post_data_json
    check.ok(
        payload["seats"] == KINDS, "the start button posts 'search'", payload["seats"]
    )
    seats = page.evaluate("state.summary.seats")
    check.ok(
        seats[0] == "human"
        and all(
            kind.startswith("search:") and kind.endswith("l3-e2e.pt")
            for kind in seats[1:]
        ),
        "the server seats its network's real file",
        seats,
    )
    _, wide, _ = open_context(browser, "wide", DEFAULT_VIEWPORT)
    wide.goto(f"{base}/#game={game_id}")
    wide.wait_for_selector("#game-screen:not([hidden])")
    wide.wait_for_function("state.view !== null")

    watch = Watch()
    play_phases(page, wide, "ko", watch, 3, shots=True)
    check_labels(page, "ko", needles, "mid-game")
    check_badge_heads(page, "ko")

    for each in (page, wide):
        set_language(each, "en")
    play_phases(page, wide, "en", watch, 1, shots=True)
    check_labels(page, "en", needles, "mid-game")
    check_badge_heads(page, "en")
    check_labels(wide, "en", needles, "follower")
    for each in (page, wide):
        set_language(each, "ko")
    check_watch(watch)

    scenario_missed_ring(page, base, game_id, rec)

    print("[L] save mid-game, the lists, load and play on")
    before = page.evaluate(
        """() => ({
            log: state.summary.log_count,
            decision: state.summary.decision,
            confirmation: state.summary.confirmation,
        })"""
    )
    page.once("dialog", lambda dialog: dialog.accept(SAVE_NAME))
    page.click("#save-game")
    page.wait_for_function(
        "!document.getElementById('game-note').hidden"
        f" && document.getElementById('game-note').textContent.includes('{SAVE_NAME}')"
    )
    page.click("#leave-game")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_selector(f"#save-list li:has-text('{SAVE_NAME}')")
    page.wait_for_selector("#game-list li")
    for lang in ("ko", "en"):
        set_language(page, lang)
        listed = ", ".join(LABELS[lang][kind] for kind in KINDS)
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
        no_leak(page, needles, f"lists {lang}")
    set_language(page, "ko")
    started = time.monotonic()
    page.click(f"#save-list li:has-text('{SAVE_NAME}') button:has-text('불러오기')")
    page.wait_for_function(
        f"state.gameId !== null && state.gameId !== '{game_id}'"
        " && state.view !== null && refreshFlight === null",
        timeout=30000,
    )
    took = time.monotonic() - started
    check.ok(took < 5.0, f"the load is back within a few seconds ({took:.1f}s)", took)
    after = page.evaluate(
        """() => ({
            log: state.summary.log_count,
            decision: state.summary.decision,
            confirmation: state.summary.confirmation,
        })"""
    )
    check.ok(
        after == before, "the loaded game rests on the saved decision", (before, after)
    )
    loaded = page.evaluate("state.summary.seats")
    check.ok(loaded == seats, "the loaded game keeps the same network file", loaded)
    loaded_id = page.evaluate("state.gameId")
    wide.goto(f"{base}/#game={loaded_id}")
    wide.wait_for_function(
        f"state.gameId === '{loaded_id}'"
        " && state.view !== null && refreshFlight === null"
    )
    play_phases(page, wide, "ko", watch, 1)
    check.ok(
        watch.phases >= 5, "the loaded game plays on through a hand-over", watch.phases
    )
    check_labels(page, "ko", needles, "after the load")
    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests", failed[:5])


def main() -> None:
    workdir = Path(tempfile.mkdtemp(prefix="dune-e2e-search-"))
    try:
        real, link = write_checkpoint(workdir)
        # The temp dir's name is in every form of the path (the link's, the
        # resolved one); "search:/" is the raw kind ("Research:" holds
        # "search:" itself).
        needles = [workdir.name, "search:/"]
        with chrome() as browser:
            scenario_without(browser, workdir)
            with server("--search-checkpoint", str(link)) as (base, server_log):
                try:
                    startup = server_log.read_text()
                    check.ok(
                        f"search AI: {real}" in startup,
                        "the startup line names the file the link points at",
                        [line for line in startup.splitlines() if "search AI" in line],
                    )
                    check_setup(base, browser, needles)
                    scenario_game(base, browser, needles)
                finally:
                    shutil.copy(server_log, SERVER_LOG_COPY)
                text = server_log.read_text()
                check.ok(
                    "Traceback" not in text and "ERROR" not in text,
                    f"no server errors (see {SERVER_LOG_COPY})",
                )
                check.ok(
                    "failed to answer" not in text,
                    "no search seat fell back from a failing search",
                )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    check.finish()


if __name__ == "__main__":
    main()
