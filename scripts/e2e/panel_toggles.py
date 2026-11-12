"""E2E of the header's panel toggles (user request 2026-11-06, after the
phone layout: "pc ui에서도 토글버튼으로 손패, 플레이어 상태, 공용카드, 로그를
on off 할 수 있으면 좋겠는데"; the user chose the header, folded when narrow,
and a hidden panel left hidden with a mark when the decision needs it).

layout.js keeps which panels are hidden in this browser (localStorage
dune.layout.panels.v1); panel_toggles.css hides them from 700px up. One
live game (seat 0 human, three heuristic seats, the setup screen's boxes,
no Leader draft), driven by applyAction:

A. 1440x900, inline toggles: each toggle hides its panel alone and marks
   itself not pressed, the page never scrolls sideways, and pressing it
   again gives back the exact layout; hiding the hand makes the board
   taller; with all four hidden the decisions still show; the choice
   survives a reload.
B. The hand and the shared cards hidden through the next decisions: at a
   staged Agent turn the hand's toggle is marked and the hand stays
   hidden; the open "① 카드" step is pressable and shows the hand; when a
   decision lights a shared card, the shared cards' toggle is marked.
C. 900x800, folded: only "보기 ▾" shows; it opens the four toggles under
   it, inside the window; a toggle pressed there acts and leaves the list
   open; a click elsewhere or Escape closes it; the folded button is
   marked while a hidden panel holds something the decision can take.
D. 650x800: no toggles and every panel shown, whatever is stored.
E. 390x844: the phone layout's tabs, untouched by the stored choice.
F. The seed and the ruleset badges (user 2026-11-06: not needed during a
   game, so off the header line): the help opens with them, and the status
   line's title names them; the line itself does not.

The header's own checks at 600-1920px are narrow.py's.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from common import SERVER_LOG_COPY, Check, chrome, client_state, open_context, server
from open_mode import settled

check = Check()
SEED = 11
SHOTS = Path(os.environ["E2E_SHOTS_DIR"]) if os.environ.get("E2E_SHOTS_DIR") else None
PANELS = ("hand", "seats", "market", "log")
ELEMENT = {
    "hand": "private-zone",
    "seats": "seats",
    "market": "market",
    "log": "side-log",
}
CUE = (
    "(panel) => document.querySelector("
    "`#panel-toggles-list [data-panel='${panel}']`).classList.contains('cue')"
)

GEOM = """() => {
  const rect = (id) => {
    const b = document.getElementById(id).getBoundingClientRect();
    return b.width > 0 && b.height > 0
      ? [Math.round(b.left), Math.round(b.top),
         Math.round(b.width), Math.round(b.height)]
      : null;
  };
  const stage = document.querySelector('#board .board-stage');
  const s = stage ? stage.getBoundingClientRect() : null;
  return {
    "private-zone": rect('private-zone'), seats: rect('seats'), market: rect('market'),
    "side-log": rect('side-log'), banner: rect('decision-banner'), board: rect('board'),
    stage: s ? [Math.round(s.width), Math.round(s.height)] : null,
    pressed: Object.fromEntries([...document.querySelectorAll(
      '#panel-toggles-list [data-panel]')].map((b) => [b.dataset.panel,
      b.getAttribute('aria-pressed')])),
    stored: localStorage.getItem('dune.layout.panels.v1'),
    sideways: document.documentElement.scrollWidth > innerWidth + 0.5,
  };
}"""
SHOWN = """(id) => {
  const e = document.getElementById(id);
  const b = e.getBoundingClientRect();
  return getComputedStyle(e).display !== 'none' && b.width > 0 && b.height > 0;
}"""


def in_place(g: dict) -> bool:
    """The board shows, the decision panel to its right."""
    board, banner = g["board"], g["banner"]
    return bool(
        board and banner and g["stage"][0] > 0 and banner[0] >= board[0] + board[2] - 1
    )


def shoot(page, name: str) -> None:
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"panel_toggles_{name}.png"))


def toggle(page, panel: str) -> None:
    page.click(f"#panel-toggles-list [data-panel='{panel}']")
    settled(page)
    page.wait_for_timeout(100)


def start_game(page, base: str) -> None:
    page.goto(base + "/")
    page.wait_for_function(
        "document.querySelectorAll('#seat-selects select').length === 4"
        " && state.server !== null"
    )
    for seat in range(1, 4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    page.uncheck("#opt-leader-draft")
    page.fill("#opt-seed", str(SEED))
    page.select_option("#opt-ai-pace", "instant")
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)


def check_settings(page) -> None:
    print("[F] the seed and options: in the help, not on the header line")
    found = page.evaluate(
        """() => {
          const status = document.getElementById('header-status');
          const badges = gameSettingBadges(state.summary);
          openHelp();
          const line = document.querySelector('#help-body .help-game-settings');
          const shown = line ? line.textContent : null;
          closeHelp();
          return {badges, shown, text: status.textContent, title: status.title,
                  seed: t('common.seed', {seed: state.summary.game_seed})};
        }"""
    )
    check.ok(
        found["seed"] in found["badges"] and len(found["badges"]) > 1,
        "the game has a seed and options to name",
        found,
    )
    check.ok(
        found["shown"] == " · ".join(found["badges"]),
        "the help's first lines name the seed and every option",
        found,
    )
    check.ok(
        not any(b in found["text"] for b in found["badges"])
        and all(b in found["title"] for b in found["badges"]),
        "the header line names none of them, its title all",
        found,
    )


def check_wide(page) -> None:
    print("[A] 1440x900: the inline toggles")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(200)
    check.ok(
        page.is_visible("#panel-toggles-list")
        and not page.is_visible("#panel-toggles-open"),
        "the four toggles are in the header, the folded button is not",
    )
    base = page.evaluate(GEOM)
    check.ok(
        all(base[ELEMENT[p]] for p in PANELS)
        and set(base["pressed"].values()) == {"true"},
        "every panel shows and every toggle is pressed",
        base,
    )
    for panel in PANELS:
        toggle(page, panel)
        g = page.evaluate(GEOM)
        others = [p for p in PANELS if p != panel]
        check.ok(
            g[ELEMENT[panel]] is None
            and all(g[ELEMENT[p]] for p in others)
            and g["pressed"][panel] == "false"
            and in_place(g)
            and not g["sideways"],
            f"the {panel} toggle hides the {panel} alone, the board and the"
            " decisions keep their places, the page does not scroll",
            g,
        )
        if panel == "hand":
            check.ok(
                g["stage"][1] > base["stage"][1] + 20,
                "with the hand hidden the board is taller",
                (base["stage"], g["stage"]),
            )
            shoot(page, "wide_no_hand")
        toggle(page, panel)
        back = page.evaluate(GEOM)
        check.ok(
            all(
                back[k] == base[k]
                for k in (*ELEMENT.values(), "board", "banner", "stage")
            )
            and back["pressed"] == base["pressed"]
            and back["stored"] is None,
            f"pressed again, the {panel} and the layout are as before",
            (base, back),
        )
    for panel in PANELS:
        toggle(page, panel)
    g = page.evaluate(GEOM)
    shoot(page, "wide_all_hidden")
    check.ok(
        all(g[ELEMENT[p]] is None for p in PANELS)
        and in_place(g)
        and not g["sideways"]
        and g["stage"][0] >= base["stage"][0],
        "with all four hidden the board and the decisions show, the board no smaller",
        (base["stage"], g),
    )
    page.reload()
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    g = page.evaluate(GEOM)
    check.ok(
        all(g[ELEMENT[p]] is None for p in PANELS)
        and set(g["pressed"].values()) == {"false"},
        "the choice survives a reload",
        g,
    )
    for panel in ("seats", "log"):
        toggle(page, panel)


def check_cues(page) -> None:
    print("[B] the hand and the shared cards hidden: marks, and the ① step")
    hand_marked = market_marked = False
    for _ in range(400):
        assert settled(page, 30)
        snap = client_state(page)
        if snap["finished"]:
            break
        mine = snap["owner"] == snap["viewSeat"] and snap["nActions"]
        if mine and page.evaluate("document.querySelector('#market .legal') !== null"):
            if not market_marked:
                market_marked = page.evaluate(CUE, "market")
        if mine and page.evaluate("stagedTurn() && !state.pick") and not hand_marked:
            hand_marked = page.evaluate(CUE, "hand")
            check.ok(hand_marked, "at a staged Agent turn the hand's toggle is marked")
            check.ok(
                not page.evaluate(SHOWN, "private-zone"), "and the hand stays hidden"
            )
            shoot(page, "hand_marked")
            check_folded(page)
            step = page.locator("#actions .pick-step:not(.done)").first
            check.ok(step.is_enabled(), "the open ① step can be pressed")
            step.click()
            settled(page)
            check.ok(
                page.evaluate(SHOWN, "private-zone")
                and page.evaluate("JSON.parse(localStorage.getItem("
                                  "'dune.layout.panels.v1') || '[]')") == ["market"],
                "it shows the hand (and only the hand)",
            )
        if hand_marked and market_marked:
            break
        if snap["confirmation"] == snap["viewSeat"]:
            page.evaluate("confirmTurn()")
        elif snap["nActions"]:
            page.evaluate("applyAction(0)")
        else:
            time.sleep(0.05)
    check.ok(hand_marked, "a staged Agent turn came with the hand hidden")
    check.ok(
        market_marked, "a decision lit a shared card, and its hidden toggle was marked"
    )


def check_folded(page) -> None:
    print("[C] 900x800: folded into one button")
    page.set_viewport_size({"width": 900, "height": 800})
    page.wait_for_timeout(200)
    check.ok(
        page.is_visible("#panel-toggles-open")
        and not page.is_visible("#panel-toggles-list"),
        "only the folded button shows",
    )
    check.ok(
        page.evaluate("document.getElementById('panel-toggles-open').classList.contains('cue')"),
        "the folded button is marked for the hidden hand",
    )
    page.click("#panel-toggles-open")
    box = page.evaluate(
        """() => { const r = document.getElementById('panel-toggles-list')
          .getBoundingClientRect();
          return [r.left, r.top, r.right, r.bottom, innerWidth, innerHeight,
            document.querySelectorAll('#panel-toggles-list [data-panel]').length]; }"""
    )
    shoot(page, "folded_open")
    check.ok(
        page.is_visible("#panel-toggles-list")
        and box[0] >= 0 and box[2] <= box[4] and box[3] <= box[5] and box[6] == 4,
        "it opens the four toggles under it, inside the window",
        box,
    )
    seats_before = page.evaluate(SHOWN, "seats")
    toggle(page, "seats")
    check.ok(
        seats_before and not page.evaluate(SHOWN, "seats")
        and page.is_visible("#panel-toggles-list"),
        "a toggle there acts, and the list stays open",
    )
    toggle(page, "seats")
    page.click("#header-status")
    check.ok(not page.is_visible("#panel-toggles-list"), "a click elsewhere closes it")
    page.click("#panel-toggles-open")
    page.keyboard.press("Escape")
    check.ok(not page.is_visible("#panel-toggles-list"), "Escape closes it")

    print("[D] 650x800: no toggles, every panel shown")
    page.set_viewport_size({"width": 650, "height": 800})
    page.wait_for_timeout(200)
    check.ok(not page.is_visible("#panel-toggles"), "no toggles in the header")
    check.ok(
        all(page.evaluate(SHOWN, ELEMENT[p]) for p in ("hand", "market")),
        "the hidden hand and shared cards show",
    )

    print("[E] 390x844: the phone's tabs")
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(200)
    page.evaluate("showPhoneView('hand')")
    check.ok(
        not page.is_visible("#panel-toggles") and page.evaluate(SHOWN, "private-zone"),
        "no toggles, and the hand tab shows the hand",
    )
    page.evaluate("showPhoneView('market')")
    check.ok(
        page.evaluate(SHOWN, "market"), "and the shared cards tab the shared cards"
    )
    page.evaluate("showPhoneView('board')")
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(200)


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            size = {"width": 1440, "height": 900}
            _, page, _ = open_context(browser, "panel-toggles", size)
            start_game(page, base)
            check_settings(page)
            check_wide(page)
            # [A] leaves the hand and the shared cards hidden for [B].
            check_cues(page)
        errors = [
            line
            for line in log_path.read_text().splitlines()
            if "ERROR" in line or "Traceback" in line
        ]
        check.ok(not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3])
        SERVER_LOG_COPY.write_text(log_path.read_text())
    check.finish()


if __name__ == "__main__":
    main()
