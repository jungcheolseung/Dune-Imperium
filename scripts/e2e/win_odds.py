"""E2E of the win odds course, shown only after the game (panels.js "the win
odds", server GET /games/{id}/win-odds).

A finished game's odds: at each round's opening the server reads each seat's
chance of first place. It refuses a running game (400 to a seated client, 403
to a seatless remote one); a finished game's room link is enough. The result
screen draws the course as a line chart under the result table, the review
bar as a compact one with a line at the cursor's round. A tiny entity network
with a value branch is written for the run (the way tests/server/test_win_odds.py
builds it): only the plumbing is checked here, not the numbers' quality.

[A] A finished game of four heuristic table seats (Uprising, CHOAM +
Bloodlines + Tech + Immortality, seed 3) on a server with the network. In
Korean and English at 1366x768 and 1600x950:

- the result screen (#standings, shown by this AI-only game when the review
  cursor reaches the end): one .win-odds-section, its h3 ("형세 흐름" / "How
  the game went"), one chart with an svg[role=img], four polylines (one
  .winner, whose data-seat is the rank-1 seat of summary.standings) each with
  one point per API round holding odds, rows x 4 points, four badges numbered
  1-4, a legend of four, a hidden table of rounds + 1 rows; hovering a
  rect.hit shows the tooltip with that rect's aria-label; nothing scrolls
  sideways; screenshot win_odds_result_<lang>_<width>.png;
- the review bar at the start, the middle and the end: #review-odds visible
  with exactly one compact chart and no legend; data-cursor-round is the round
  of the last API row whose index lies below the cursor's log count; a
  line.cursor exists exactly when that round is not empty, at the x of that
  round's points; screenshot win_odds_review_<lang>_<width>.png.

[B] A live game on the same server (seat 0 human, three heuristic seats,
seed 7): in round 2 not one /win-odds request, no chart, no visible
#review-odds, and a direct fetch answers 400. The game is then played to its
end (within a time limit): the result screen shows the chart and exactly one
/win-odds request was made.

[C] A remote server with the network: the seated host's page makes no
/win-odds request while the game runs and a direct fetch answers 400; a
browser holding no seat gets 403; a finished game opened with the room link
alone shows the chart in its review.

[D] No odds: (1) a server whose --search-checkpoint names no file: a finished
game shows no chart and no section, #review-odds stays hidden, exactly one
/win-odds request; (2) the server with the network, a finished original-board
game: the same.

Every page: no JS error, no failed request (but the 400/403 provoked on
purpose); no Traceback/ERROR in any server log. E2E_SHOTS_DIR names where the
screenshots go, otherwise a temporary folder.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from common import (
    E2E_TMP,
    PROJECT_PYTHON,
    REPO,
    REVIEW_LANDING,
    SERVER_LOG_COPY,
    Check,
    api_get,
    api_post,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from log_follow import take_step
from open_mode import create_game, settled

check = Check()

SHOTS = Path(os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-wo-"))
SHOTS.mkdir(parents=True, exist_ok=True)
KEY = "e2e-host-admin-key"  # 16+ characters: the server refuses shorter keys
VIEWPORTS = ({"width": 1366, "height": 768}, {"width": 1600, "height": 950})
OPTIONS = ("choam", "bloodlines", "tech", "immortality")
GAME_BODY = {
    "seats": ["heuristic_uprising_table"] * 4,
    "game_seed": 3,
    "choam_module": True,
    "bloodlines": True,
    "tech_module": True,
    "immortality": True,
}
ORIGINAL_BODY = {
    "seats": ["heuristic"] * 4,
    "game_seed": 3,
    "base_game": "imperium",
}
HEADING = {"ko": "형세 흐름", "en": "How the game went"}
LIVE_TIME_LIMIT = 420.0  # seconds to play [B]'s game to its end

NETWORK_SCRIPT = """
import sys
from pathlib import Path

import torch

from dune_imperium.adapters.action_codec import ActionCodec
from dune_imperium.config import RulesetConfig
from dune_imperium.training.checkpoint import save_checkpoint
from dune_imperium.training.entity_network import EntityNetwork, with_value_branch

config = RulesetConfig(
    choam_module=True, promo_cards=True, bloodlines=True, tech_module=True,
    immortality=True, go_to_11=True, epic_game=True, arrakeen_scouts=True,
    leader_draft=True,
)
torch.manual_seed(0)
plain = EntityNetwork(
    config, hidden=(16,), entity_width=8, seat_width=16, action_width=8
)
branched = with_value_branch(plain, reward_step=1 / 6)
save_checkpoint(Path(sys.argv[1]), branched, ruleset=config.identifier,
                iteration=1, codec=ActionCodec(config))
"""


CHART_JS = """(root) => {
  const box = document.querySelector(root);
  if (!box) return null;
  const sections = [...box.querySelectorAll('.win-odds-section')];
  const charts = [...box.querySelectorAll('.win-odds-chart')];
  const chart = charts[0];
  const info = {
    sections: sections.length,
    heading: sections.length ? sections[0].querySelector('h3')?.textContent : null,
    note: sections.length ? Boolean(sections[0].querySelector('.win-odds-note')) : null,
    charts: charts.length,
    compact: charts.map((c) => c.classList.contains('compact')),
    page: [document.documentElement.scrollWidth, innerWidth],
  };
  if (!chart) return info;
  const svg = chart.querySelector('svg[role=img]');
  info.svg = Boolean(svg);
  info.polylines = [...chart.querySelectorAll('polyline.series')].map((p) => ({
    seat: Number(p.dataset.seat),
    winner: p.classList.contains('winner'),
    xs: p.getAttribute('points').split(' ').map((pt) => Number(pt.split(',')[0])),
  }));
  info.points = chart.querySelectorAll('circle.point').length;
  info.badges = [...chart.querySelectorAll('text.badge-text')]
    .map((b) => b.textContent);
  info.badgeCircles = chart.querySelectorAll('circle.badge').length;
  info.hits = [...chart.querySelectorAll('rect.hit')].map((r) => ({
    label: r.getAttribute('aria-label'),
    tab: r.getAttribute('tabindex'),
  }));
  info.legend = chart.querySelectorAll('.win-odds-legend > span').length;
  info.legends = chart.querySelectorAll('.win-odds-legend').length;
  const table = chart.querySelector('table.visually-hidden');
  info.tableRows = table ? table.querySelectorAll('tr').length : null;
  info.cursors = [...chart.querySelectorAll('line.cursor')].map((l) =>
    Number(l.getAttribute('x1')));
  info.tip = chart.querySelector('.win-odds-tip') !== null;
  return info;
}"""

STANDING_WINNER_JS = "(state.summary.standings.find((e) => e.rank === 1) || {}).player"

FETCH_JS = """async (id) => {
  const response = await fetch(`/games/${id}/win-odds`);
  return { status: response.status, body: await response.json() };
}"""

CREATE_AI_GAME_JS = """async (body) => {
  const response = await fetch('/games', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return response.json();
}"""


def make_network() -> Path:
    path = E2E_TMP / "win-odds-network.pt"
    subprocess.run(
        [str(PROJECT_PYTHON), "-c", NETWORK_SCRIPT, str(path)],
        cwd=REPO,
        check=True,
    )
    return path


def chart_info(page: Any, root: str) -> dict[str, Any] | None:
    info: dict[str, Any] | None = page.evaluate(CHART_JS, root)
    return info


def expected_round(rows: list[dict[str, Any]], count: int) -> int | None:
    shown = None
    for row in rows:
        if row["index"] < count and row["odds"]:
            shown = row["round"]
    return shown


def open_review(page: Any, base: str, game_id: str) -> int:
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_function(
        "(id) => state.gameId === id && state.review !== null && state.view !== null",
        arg=game_id,
    )
    page.evaluate("stopPlayback()")
    end: int = page.evaluate("state.review.meta.step_count")
    seek(page, end)
    return end


def seek(page: Any, target: int) -> None:
    landing = page.evaluate(REVIEW_LANDING, target)
    page.evaluate("(cursor) => reviewSeek(cursor)", target)
    page.wait_for_function(
        "(c) => state.review.cursor === c && !state.review.seek"
        " && refreshFlight === null",
        arg=landing,
    )


def failed_requests(rec: Any, allowed: tuple[int, ...] = ()) -> list[Any]:
    """Failed responses, but the 400/403 of a win-odds read provoked on
    purpose (``allowed`` statuses)."""
    return [
        r
        for r in rec.requests
        if r[3] is not None
        and r[3] >= 400
        and not (r[3] in allowed and "win-odds" in r[2])
    ]


def check_log(log_path: Path, label: str) -> None:
    text = log_path.read_text()
    check.ok(
        "Traceback" not in text and "ERROR" not in text,
        f"{label}: no server errors ({log_path.name})",
    )


def check_result(
    page: Any,
    rows: list[dict[str, Any]],
    lang: str,
    label: str,
) -> None:
    info = chart_info(page, "#standings")
    check.ok(
        info is not None and info["sections"] == 1 and info["charts"] == 1,
        f"{label}: the result screen holds one win-odds section with one chart",
        info and (info["sections"], info["charts"]),
    )
    if not info or info["charts"] != 1:
        return
    check.ok(
        info["heading"] == HEADING[lang] and info["note"],
        f"{label}: the heading reads {HEADING[lang]!r}, with its note",
        info["heading"],
    )
    check.ok(info["compact"] == [False], f"{label}: the chart is full size")
    check.ok(info["svg"], f"{label}: the chart is an svg[role=img]")
    lines = info["polylines"]
    winner = page.evaluate(STANDING_WINNER_JS)
    check.ok(
        len(lines) == 4 and all(len(line["xs"]) == len(rows) for line in lines),
        f"{label}: four polylines with {len(rows)} points each (the API's rounds)",
        [len(line["xs"]) for line in lines],
    )
    check.ok(
        info["points"] == len(rows) * 4,
        f"{label}: {len(rows)} x 4 points",
        info["points"],
    )
    check.ok(
        sorted(info["badges"]) == ["1", "2", "3", "4"] and info["badgeCircles"] == 4,
        f"{label}: four badges numbered 1-4",
        info["badges"],
    )
    winners = [line["seat"] for line in lines if line["winner"]]
    check.ok(
        winners == [winner],
        f"{label}: one winner polyline, the rank-1 seat ({winner})",
        winners,
    )
    check.ok(info["legend"] == 4, f"{label}: the legend has 4 items", info["legend"])
    check.ok(
        info["tableRows"] == len(rows) + 1,
        f"{label}: the hidden table has {len(rows) + 1} rows",
        info["tableRows"],
    )
    check.ok(
        len(info["hits"]) == len(rows)
        and all(h["tab"] == "0" and h["label"] for h in info["hits"]),
        f"{label}: a focusable hit area per round, each with an aria-label",
        info["hits"][:2],
    )
    # Hover: the first and the last round's hit area.
    hits = page.locator("#standings .win-odds-chart rect.hit")
    for which in (0, len(rows) - 1):
        hits.nth(which).hover()
        shown = page.evaluate(
            """() => {
              const tip = document.querySelector('#standings .win-odds-tip');
              return { hidden: tip.hidden, text: tip.textContent };
            }"""
        )
        want = info["hits"][which]["label"]
        check.ok(
            not shown["hidden"] and shown["text"] == want,
            f"{label}: hovering round {rows[which]['round']} shows its tooltip",
            (shown, want),
        )
    page.mouse.move(2, 2)
    width, inner = info["page"]
    check.ok(width == inner, f"{label}: nothing scrolls sideways", (width, inner))


def check_review_bar(
    page: Any,
    rows: list[dict[str, Any]],
    cursor_label: str,
    label: str,
) -> int | None:
    count = page.evaluate("reviewLog(state.review).count")
    want = expected_round(rows, count)
    want_text = "" if want is None else str(want)
    page.wait_for_function(
        "(w) => { const b = document.getElementById('review-odds');"
        " return b && !b.hidden && b.dataset.cursorRound === w; }",
        arg=want_text,
    )
    info = chart_info(page, "#review-odds")
    visible = page.evaluate("!document.getElementById('review-odds').hidden")
    check.ok(
        visible and info is not None and info["charts"] == 1,
        f"{label} {cursor_label}: #review-odds visible with one chart",
        info and info["charts"],
    )
    if not info or info["charts"] != 1:
        return want
    check.ok(
        info["compact"] == [True] and info["legends"] == 0,
        f"{label} {cursor_label}: the chart is compact, with no legend",
        (info["compact"], info["legends"]),
    )
    check.ok(
        info["svg"] and info["sections"] == 0,
        f"{label} {cursor_label}: an svg chart, no section",
    )
    round_attr = page.evaluate(
        "document.getElementById('review-odds').dataset.cursorRound"
    )
    check.ok(
        round_attr == want_text,
        f"{label} {cursor_label}: data-cursor-round is {want_text!r}"
        f" (log count {count})",
        round_attr,
    )
    if want is None:
        check.ok(
            info["cursors"] == [],
            f"{label} {cursor_label}: no cursor line before any round",
            info["cursors"],
        )
    else:
        position = [r["round"] for r in rows].index(want)
        xs = info["polylines"][0]["xs"]
        check.ok(
            len(info["cursors"]) == 1 and abs(info["cursors"][0] - xs[position]) < 0.01,
            f"{label} {cursor_label}: one cursor line at round {want}'s x",
            (info["cursors"], xs[position]),
        )
    width, inner = info["page"]
    check.ok(
        width == inner,
        f"{label} {cursor_label}: nothing scrolls sideways",
        (width, inner),
    )
    return want


def scenario_review(base: str, browser: Any, game_id: str) -> None:
    print("[A] the finished game: result screen and review bar")
    context, page, rec = open_context(browser, "review", VIEWPORTS[0])
    end = open_review(page, base, game_id)
    payload = api_get(base, f"/games/{game_id}/win-odds")
    check.ok(payload["available"] is True, "[A] the server offers odds", payload)
    check.ok(
        payload["step_count"] == end,
        "[A] the payload's step_count is the review's",
        (payload["step_count"], end),
    )
    rows = [r for r in payload["rounds"] if r["odds"]]
    check.ok(len(rows) >= 2, f"[A] the API has {len(rows)} rounds with odds", rows[:2])
    check.ok(
        all(abs(sum(r["odds"]) - 1) < 1e-4 and len(r["odds"]) == 4 for r in rows),
        "[A] every row's four odds add up to 1",
    )
    for lang in ("ko", "en"):
        if page.evaluate("TERM_LANGUAGE") != lang:
            page.click("#language-toggle")
            page.wait_for_function(f"TERM_LANGUAGE === '{lang}'")
        for viewport in VIEWPORTS:
            width = viewport["width"]
            page.set_viewport_size(viewport)
            page.wait_for_timeout(150)
            label = f"[A {lang} {width}]"
            seek(page, end)
            page.wait_for_selector("#standings:not([hidden]) .win-odds-chart")
            page.wait_for_function(
                f"document.querySelector('#standings .win-odds-section h3')"
                f".textContent === {HEADING[lang]!r}"
            )
            check_result(page, rows, lang, label)
            page.locator("#standings").screenshot(
                path=str(SHOTS / f"win_odds_result_{lang}_{width}.png")
            )
            for where, cursor in (("start", 0), ("middle", end // 2), ("end", end)):
                seek(page, cursor)
                check_review_bar(page, rows, f"cursor {where} ({cursor})", label)
            page.locator("#review-bar").screenshot(
                path=str(SHOTS / f"win_odds_review_{lang}_{width}.png")
            )
    check.ok(
        rec.count("GET", "/win-odds") == 1,
        "[A] the win odds were fetched once for the game",
        rec.count("GET", "/win-odds"),
    )
    check.ok(
        not failed_requests(rec), "[A] no failed requests", failed_requests(rec)[:5]
    )
    context.close()


def play_to_round(page: Any, target: int) -> None:
    for _ in range(800):
        if page.evaluate(f"state.view.round_number >= {target}"):
            return
        if page.evaluate("state.summary.finished"):
            return
        take_step(page)
        assert settled(page, 20)


def check_none_while_running(page: Any, rec: Any, game_id: str, label: str) -> None:
    page.wait_for_timeout(500)
    check.ok(
        rec.count("GET", "/win-odds") == 0,
        f"{label}: no /win-odds request while the game runs",
        rec.count("GET", "/win-odds"),
    )
    check.ok(
        page.evaluate("document.querySelectorAll('.win-odds-chart').length") == 0,
        f"{label}: no chart on the page",
    )
    check.ok(
        page.evaluate("document.getElementById('review-odds').hidden"),
        f"{label}: #review-odds is hidden",
    )
    refused = page.evaluate(FETCH_JS, game_id)
    check.ok(
        refused["status"] == 400,
        f"{label}: a direct fetch by the seated page answers 400",
        refused,
    )


def scenario_live(base: str, browser: Any) -> None:
    print("[B] a live game on the server with the network")
    context, page, rec = open_context(browser, "live", VIEWPORTS[1])
    game_id = create_game(page, base, humans=(0,), seed=7, options=OPTIONS)
    play_to_round(page, 2)
    check.ok(
        page.evaluate("state.view.round_number") >= 2
        and not page.evaluate("state.summary.finished"),
        "[B] the live game is in round 2 or later",
        page.evaluate("state.view.round_number"),
    )
    check_none_while_running(page, rec, game_id, "[B]")
    # The one request so far is this script's own provoked fetch (the page
    # made none: check_none_while_running counted 0 before it).
    provoked = rec.count("GET", "/win-odds")
    check.ok(provoked == 1, "[B] only the provoked fetch so far", provoked)
    print("  .. /win-odds requests in [B] while running: 0 by the page")
    started = time.monotonic()
    steps = 0
    while not page.evaluate("state.summary.finished"):
        if time.monotonic() - started > LIVE_TIME_LIMIT:
            break
        take_step(page)
        steps += 1
    finished = bool(page.evaluate("state.summary.finished"))
    print(
        f"  .. [B] finished={finished} after {steps} more steps"
        f" in {time.monotonic() - started:.0f}s"
    )
    if finished:
        page.wait_for_selector(
            "#standings:not([hidden]) .win-odds-chart", timeout=30000
        )
        info = chart_info(page, "#standings")
        check.ok(
            info is not None
            and info["sections"] == 1
            and info["charts"] == 1
            and len(info["polylines"]) == 4,
            "[B] the finished game's result screen shows the chart",
            info and (info["sections"], info["charts"]),
        )
        page.wait_for_timeout(500)
        total = rec.count("GET", "/win-odds") - provoked
        check.ok(
            total == 1,
            f"[B] exactly one /win-odds request by the page in all ({total})",
            total,
        )
        print(f"  .. /win-odds requests in [B] in all: {total}")
    else:
        print("  .. [B] SKIPPED the end of the game: not finished within the limit")
    check.ok(
        not failed_requests(rec, (400,)),
        "[B] no failed requests but the 400",
        failed_requests(rec, (400,))[:5],
    )
    context.close()


def finished_page_without_odds(
    browser: Any, base: str, game_id: str, name: str, label: str
) -> None:
    context, page, rec = open_context(browser, name, VIEWPORTS[1])
    end = open_review(page, base, game_id)
    page.wait_for_selector("#standings:not([hidden])")
    page.wait_for_timeout(1000)
    for where, cursor in (("end", end), ("start", 0)):
        seek(page, cursor)
        page.wait_for_timeout(200)
        check.ok(
            page.evaluate("document.querySelectorAll('.win-odds-chart').length") == 0
            and page.evaluate("document.querySelectorAll('.win-odds-section').length")
            == 0,
            f"{label}: no chart or section at the {where} cursor",
        )
        check.ok(
            page.evaluate("document.getElementById('review-odds').hidden"),
            f"{label}: #review-odds stays hidden at the {where} cursor",
        )
    requests = rec.count("GET", "/win-odds")
    check.ok(
        requests == 1, f"{label}: exactly one /win-odds request ({requests})", requests
    )
    print(f"  .. /win-odds requests in {label}: {requests}")
    payload = api_get(base, f"/games/{game_id}/win-odds")
    check.ok(
        payload["available"] is False and payload["reason"],
        f"{label}: the API says unavailable and why",
        (payload["available"], payload.get("reason")),
    )
    check.ok(
        not failed_requests(rec),
        f"{label}: no failed requests",
        failed_requests(rec)[:5],
    )
    context.close()


def scenario_no_network(browser: Any) -> None:
    print("[D1] a server whose --search-checkpoint names no file")
    missing = E2E_TMP / "win-odds-missing.pt"
    missing.unlink(missing_ok=True)
    with server("--search-checkpoint", str(missing)) as (base, log_path):
        try:
            game_id = api_post(base, "/games", GAME_BODY)["game_id"]
            finished_page_without_odds(browser, base, game_id, "plain", "[D1]")
        finally:
            shutil.copy(log_path, SERVER_LOG_COPY.with_name("dune-e2e-wo-plain.log"))
        check_log(log_path, "[D1]")


def scenario_original(base: str, browser: Any) -> None:
    print("[D2] an original-board game on the server with the network")
    done = api_post(base, "/games", ORIGINAL_BODY)
    check.ok(done.get("finished") is True, "[D2] the original-board game finished")
    finished_page_without_odds(browser, base, done["game_id"], "original", "[D2]")
    payload = api_get(base, f"/games/{done['game_id']}/win-odds")
    check.ok(
        payload.get("reason") == "base_game",
        "[D2] the reason is base_game",
        payload.get("reason"),
    )


def scenario_remote(browser: Any, network: Path) -> None:
    print("[C] a remote server with the network")
    with server(
        "--remote", "--admin-key", KEY, "--search-checkpoint", str(network)
    ) as (base, log_path):
        context, host, rec = open_context(browser, "host", VIEWPORTS[0])
        guest_context, guest, guest_rec = open_context(browser, "guest", VIEWPORTS[0])
        try:
            host.goto(f"{base}/#admin={KEY}")
            host.wait_for_selector("#setup-screen:not([hidden])")
            host.wait_for_function(
                "state.server !== null"
                " && document.querySelectorAll('#seat-selects select').length === 4"
            )
            for seat in (1, 2, 3):
                host.select_option(
                    f"#seat-selects select[data-seat='{seat}']", "heuristic"
                )
            set_rule_options(host, *OPTIONS)
            host.click("#create-game")
            host.wait_for_selector("#lobby-screen:not([hidden])")
            game_id = host.evaluate("state.gameId")
            host.fill("#lobby-name", "호스트")
            host.click("#lobby-seats li[data-seat='0'] button")
            host.wait_for_selector("#game-screen:not([hidden])")
            host.wait_for_function("state.view !== null && refreshFlight === null")
            play_to_round(host, 2)
            check_none_while_running(host, rec, game_id, "[C] seated host")
            guest.goto(f"{base}/#game={game_id}")
            guest.wait_for_selector("#lobby-screen:not([hidden])")
            guest.wait_for_timeout(1000)
            check.ok(
                guest_rec.count("GET", "/win-odds") == 0,
                "[C] the seatless browser makes no /win-odds request",
                guest_rec.count("GET", "/win-odds"),
            )
            refused = guest.evaluate(FETCH_JS, game_id)
            check.ok(
                refused["status"] == 403,
                "[C] a direct read by the seatless browser answers 403",
                refused["status"],
            )
            done = host.evaluate(CREATE_AI_GAME_JS, GAME_BODY)
            check.ok(done.get("finished") is True, "[C] the host made a finished game")
            allowed = guest.evaluate(FETCH_JS, done["game_id"])
            check.ok(
                allowed["status"] == 200 and allowed["body"]["available"] is True,
                "[C] the room link reads a finished game's odds",
                allowed["status"],
            )
            end = open_review(guest, base, done["game_id"])
            rows = [r for r in allowed["body"]["rounds"] if r["odds"]]
            guest.wait_for_selector("#standings:not([hidden]) .win-odds-chart")
            check_result(guest, rows, "ko", "[C] finished, room link")
            check_review_bar(guest, rows, f"cursor end ({end})", "[C] finished")
            seek(guest, 0)
            check_review_bar(guest, rows, "cursor start (0)", "[C] finished")
            for name, recorder, allow in (
                ("host", rec, (400,)),
                ("guest", guest_rec, (403,)),
            ):
                failed = failed_requests(recorder, allow)
                check.ok(
                    not failed, f"[C] {name}: no other failed requests", failed[:5]
                )
        finally:
            context.close()
            guest_context.close()
            shutil.copy(log_path, SERVER_LOG_COPY.with_name("dune-e2e-wo-remote.log"))
        check_log(log_path, "[C]")


def main() -> None:
    network = make_network()
    with chrome() as browser:
        with server("--search-checkpoint", str(network)) as (base, log_path):
            try:
                game_id = api_post(base, "/games", GAME_BODY)["game_id"]
                scenario_review(base, browser, game_id)
                scenario_live(base, browser)
                scenario_original(base, browser)
            finally:
                shutil.copy(log_path, SERVER_LOG_COPY)
            check_log(log_path, "network server")
        scenario_no_network(browser)
        scenario_remote(browser, network)
    print(f"screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
