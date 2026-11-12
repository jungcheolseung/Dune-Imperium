"""E2E of whole games played by taps alone on a phone (docs/mobile-ui-plan.md
M2; user decision 2026-11-06: a whole game on the phone alone).

mobile_layout.py checks the phone layout while applyAction() plays; here
every decision of the human seat is answered by tapping what a player
would tap, in a phone's Chrome (common.open_phone_context: touch, no mouse):

- A staged Agent turn: the hand tab, then a lit card. The card tap sends
  nothing and brings the board up; the decision panel then lists that
  card's spaces as buttons, exactly the spaces lit on the board. The space
  comes from those buttons on one turn and from the board's lit space,
  zoomed to twice the screen's width, on the next. A placement with more
  than one option for that card and space lists its options in the
  decision panel (no popover over the table on a phone), and the first is
  tapped. The page posts two steps, logged in order: that card picked,
  then a space pick on that space. A
  Graft card a hand card can join is not the one tapped: it waits in the
  hand for its partner. On the first turn, turned past 600px with the card
  picked, the panel is drawn for the narrow window, and back again.
- The banner's ▶ row when the seat is asked to confirm or its first legal
  action is a turn end, and its 확정 ▶ row when it holds a choice to send.
- Otherwise the row of the decision's first legal action (its data-index),
  or else the panel's first row.

A decision no tap answers (nothing to tap, or three taps that change
nothing) fails the run with its kind; the run then plays it with
applyAction() so the rest of the game is still checked. Two games: Uprising
with every expansion at 390x844, and the original board with Rise of Ix and
Arrakeen Scouts at 360x780, each to the end.

E2E_SHOTS_DIR optionally names where the screenshots go (mobile_turn_*.png).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from common import (
    EVERY_EXPANSION,
    ONE_HUMAN,
    ORIGINAL_EXPANSIONS,
    PHONE_SIZES,
    SERVER_LOG_COPY,
    Check,
    chrome,
    client_state,
    create_by_touch,
    open_phone_context,
    server,
)
from open_mode import settled

check = Check()
SHOTS = Path(os.environ["E2E_SHOTS_DIR"]) if os.environ.get("E2E_SHOTS_DIR") else None

# What a tap may change: the server's state, the seat's held choice, its
# staged pick, the open chooser.
PROGRESS = """() => JSON.stringify([
  state.summary.revision, state.summary.undo_count,
  heldChoice() ? heldChoice().index : null, state.pick,
  !document.getElementById('card-popover').hidden,
])"""
FIRST = """() => {
  const action = state.actions && state.actions.actions[0];
  return action ? {index: action.index, id: action.action_id,
                   turnEnd: EXPLICIT_TURN_END_IDS.has(action.action_id)} : null;
}"""
DIAGNOSE = """([x, y]) => {
  const hit = document.elementFromPoint(x, y);
  return {
    staged: stagedTurn(), window: turnStartWindowOpen(), pick: state.pick,
    kind: state.summary.decision && state.summary.decision.kind,
    view: document.getElementById('game-screen').dataset.phoneView,
    hit: hit && (hit.id || String(hit.className)).slice(0, 40),
    popover: document.getElementById('card-popover').hidden ? null
      : document.getElementById('card-popover').className,
    note: (document.getElementById('game-note') || {}).textContent,
    held: heldChoice(),
  };
}"""
PANEL = """() => {
  const first = state.actions && state.actions.actions[0];
  const row = first && document.querySelector(
    `#decision-banner .action-item[data-index='${first.index}']`);
  const button = row && row.querySelector(':scope > button');
  const rect = button && button.getBoundingClientRect();
  return {
    row: Boolean(row), button: Boolean(button),
    disabled: button ? button.disabled : null,
    rect: rect ? [rect.left, rect.top, rect.width, rect.height] : null,
    rows: [...document.querySelectorAll('#actions .action-item > button')]
      .slice(0, 3).map((b) => b.textContent.trim().slice(0, 40)),
    held: heldChoice() ? heldChoice().index : null,
    view: document.getElementById('game-screen').dataset.phoneView,
  };
}"""
ZOOMED = "document.getElementById('game-screen').classList.contains('board-zoomed')"
LIT_SPACES = """() => [...document.querySelectorAll('#board .hotspot.legal')]
  .map((n) => n.dataset.space).sort()"""
LISTED_SPACES = """() => [...document.querySelectorAll('.phone-space-list button')]
  .map((n) => n.dataset.space).sort()"""


def shoot(page, name: str) -> None:
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"mobile_turn_{name}.png"))


def watch_posts(page) -> None:
    page.evaluate("""() => {
      if (window.__posts) return;
      window.__posts = [];
      const send = window.fetch;
      window.fetch = (url, options) => {
        if (String(url).endsWith('/actions') && options && options.body) {
          window.__posts.push(JSON.parse(options.body));
        }
        return send(url, options);
      };
    }""")


class Player:
    """Seat 0, tapping."""

    def __init__(self, page, label: str) -> None:
        self.page = page
        self.label = label
        self.turns = 0
        self.decisions = 0
        self.fallbacks: list[tuple[str, str]] = []
        self.placement_faults: list = []
        self.kinds: set[str] = set()
        self.options = 0

    def cross_600(self) -> None:
        """Turned past 600px with a card picked, the panel is drawn again for
        the narrow window (no space buttons, the open step disabled), and
        back under 600px for the phone."""
        page = self.page
        size = page.viewport_size
        shape = (
            "({list: document.querySelectorAll('.phone-space-list').length,"
            " step: [...document.querySelectorAll('#actions .pick-step:not(.done)')]"
            ".map((b) => b.disabled)})"
        )
        # The redraw follows the media query's change event: wait for it.
        page.set_viewport_size({"width": 800, "height": 900})
        page.wait_for_function(
            "!phoneLayout() && !document.querySelector('.phone-space-list')",
            timeout=5000,
        )
        wide = page.evaluate(shape)
        page.set_viewport_size(size)
        try:
            page.wait_for_function(
                "phoneLayout() && document.querySelector('.phone-space-list')",
                timeout=5000,
            )
        except Exception:  # noqa: BLE001 - reported by the check below
            pass
        narrow = page.evaluate(shape)
        check.ok(
            wide == {"list": 0, "step": [True]}
            and narrow == {"list": 1, "step": [False]},
            f"{self.label}: across 600px the decision panel is drawn for each layout",
            (wide, narrow),
        )

    def tap(self, selector: str) -> bool:
        node = self.page.locator(selector).first
        if not node.count() or not node.is_visible() or not node.is_enabled():
            return False
        node.tap()
        return True

    def tap_turn_end(self) -> bool:
        """The banner's ▶ row: a held choice's 확정 ▶, or the turn end."""
        return self.tap("#decision-banner .held-send-row button") or self.tap(
            "#decision-banner .turn-end-row button"
        )

    def agent_turn(self) -> bool:
        page = self.page
        # A Graft card a hand card can join waits in the hand for its
        # partner; the turn here plays a card that goes alone.
        placements = page.evaluate(
            "placementActions().filter((a) => !isGraftCard(a.arguments.card_id))"
            ".map((a) => ({card: a.arguments.card_id, space: a.arguments.space_id}))"
        )
        if not placements:
            return False
        card = placements[0]["card"]
        if card is None:
            return False
        self.turns += 1
        posts_before = page.evaluate("window.__posts.length")
        # A pick left from an earlier try goes first, by its step's ✕.
        for _ in range(3):
            if not page.evaluate("state.pick !== null"):
                break
            self.tap("#actions .pick-step.done")
            assert settled(page, 30)
        self.tap("#phone-tabs [data-view='hand']")
        selector = f"#private-zone .hand-cards .vcard[data-instance='{card}']"
        page.wait_for_function(
            "(sel) => { const c = document.querySelector(sel);"
            " return c && [...c.querySelectorAll('img')].every((i) => i.complete); }",
            arg=selector,
        )
        box = page.locator(selector).first.bounding_box()
        if not self.tap(selector):
            return False
        try:
            page.wait_for_function("state.pick && state.pick.cardId", timeout=5000)
        except Exception:  # noqa: BLE001 - a fault to report, not a crash
            shoot(page, f"{self.label}_card_not_picked_{self.turns}")
            self.placement_faults.append(
                (
                    "the card tap picked nothing",
                    card,
                    page.evaluate(DIAGNOSE, [box["x"] + box["width"] / 2,
                                             box["y"] + box["height"] / 2]),
                )
            )
            return False
        view = page.evaluate("document.getElementById('game-screen').dataset.phoneView")
        sent = page.evaluate("window.__posts.length") != posts_before
        lit = page.evaluate(LIT_SPACES)
        listed = page.evaluate(LISTED_SPACES)
        if view != "board" or sent or lit != listed or not listed:
            fault = ("after the card", card, view, sent, lit, listed)
            self.placement_faults.append(fault)
        if self.turns == 1:
            shoot(page, f"{self.label}_card_picked")
            self.cross_600()
        space = sorted(
            {p["space"] for p in placements if p["card"] == card and p["space"]}
        )
        target = space[0] if space else None
        if target is None:
            return False
        on_board = not self.turns % 2
        if on_board:
            self.tap("#phone-board-zoom")
            if self.turns == 2:
                shoot(page, f"{self.label}_zoomed")
            done = self.tap(f"#board .hotspot.legal[data-space='{target}']")
        else:
            done = self.tap(f".phone-space-list .phone-space[data-space='{target}']")
        if not done:
            return False
        assert settled(page, 30)
        both = "Boolean(state.pick && state.pick.cardId && state.pick.spaceId)"
        if page.evaluate(both):
            # Several options for this card and space: on a phone they are the
            # decision panel's rows, with no popover over the table.
            if not page.evaluate("document.getElementById('card-popover').hidden"):
                self.placement_faults.append(("a chooser popover on a phone", card))
            self.options += 1
            if self.tap("#actions .action-item > button:has(.pick-option)"):
                assert settled(page, 30)
        if on_board:
            self.tap("#phone-board-zoom")
            zoomed = page.evaluate(ZOOMED)
            if zoomed:
                self.placement_faults.append(("zoom stays on", card))
        # The turn's two steps, in order: the tapped card picked, then a space
        # pick on the target space (staged_turn.py check_two_steps). Another
        # hand card that also fits the space must not stand in for it.
        posted = page.evaluate(f"window.__posts.slice({posts_before})")
        log = page.evaluate(
            "state.log.entries.filter((e) => e.type === 'action' && !e.undone)"
            ".slice(-2).map((e) => [e.action_id, e.arguments])"
        )
        two_steps = (
            len(posted) == 2
            and len(log) == 2
            and log[0][0] == "choose_agent_card"
            and log[0][1].get("card_id") == card
            and log[1][0] == "place_agent"
            and log[1][1].get("space_id") == target
        )
        if not two_steps:
            self.placement_faults.append(("the placement", card, target, posted, log))
        return True

    def answer(self) -> None:
        page = self.page
        snap = client_state(page)
        kind = snap["kind"] or "confirm"
        self.kinds.add(kind)
        self.decisions += 1
        for _attempt in range(3):
            before = page.evaluate(PROGRESS)
            snap = client_state(page)
            first = page.evaluate(FIRST)
            if (
                snap["confirmation"] == snap["viewSeat"]
                or page.evaluate("heldChoice() !== null")
                or (first and first["turnEnd"])
            ):
                tapped = self.tap_turn_end()
            elif page.evaluate("typeof stagedTurn === 'function' && stagedTurn()"):
                tapped = self.agent_turn()
            else:
                row = f".action-item[data-index='{first['index']}']" if first else ""
                tapped = first is not None and self.tap(
                    f"#decision-banner {row} > button"
                )
                if not tapped:
                    tapped = self.tap("#actions .action-item > button")
            assert settled(page, 30)
            if tapped and page.evaluate(PROGRESS) != before:
                return
        shoot(page, f"{self.label}_fallback_{len(self.fallbacks)}_{kind}")
        self.fallbacks.append(
            (kind, json.dumps(page.evaluate(FIRST)), page.evaluate(PANEL))
        )
        if client_state(page)["confirmation"] == client_state(page)["viewSeat"]:
            page.evaluate("confirmTurn()")
        else:
            page.evaluate("applyAction(0)")
        assert settled(page, 30)

    def play(self) -> None:
        page = self.page
        watch_posts(page)
        for _ in range(4000):
            assert settled(page, 30), "every step settles"
            snap = client_state(page)
            if snap["finished"]:
                break
            mine = snap["owner"] == snap["viewSeat"] and snap["nActions"]
            confirm = (
                snap["confirmation"] is not None
                and snap["confirmation"] == snap["viewSeat"]
            )
            if mine or confirm:
                self.answer()
            else:
                time.sleep(0.05)
        check.ok(
            client_state(page)["finished"], f"{self.label}: the game finished by taps"
        )
        check.ok(
            self.turns >= 8,
            f"{self.label}: Agent turns placed by taps",
            self.turns,
        )
        check.ok(
            not self.placement_faults,
            f"{self.label}: every tapped placement lit the card's spaces, listed them,"
            " and posted that card on that space",
            self.placement_faults[:3],
        )
        check.ok(
            not self.fallbacks,
            f"{self.label}: a tap answered all {self.decisions} decisions"
            f" ({len(self.kinds)} kinds)",
            self.fallbacks[:6],
        )
        print(f"  .. {self.options} placements chose among several options")
        shoot(page, f"{self.label}_end")


def run_game(base, browser, label, size, boxes, base_game=None) -> None:
    print(f"[{label}] a whole game by taps, {size['width']}x{size['height']}")
    _, page, _ = open_phone_context(browser, f"taps-{label}", size)
    create_by_touch(page, base, ONE_HUMAN, boxes, base_game=base_game)
    Player(page, label).play()
    page.context.close()


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    with server() as (base, log_path):
        with chrome() as browser:
            if only in (None, "uprising"):
                run_game(base, browser, "uprising", PHONE_SIZES[1], EVERY_EXPANSION)
            if only in (None, "original"):
                run_game(
                    base,
                    browser,
                    "original",
                    PHONE_SIZES[0],
                    ORIGINAL_EXPANSIONS,
                    "imperium",
                )
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
