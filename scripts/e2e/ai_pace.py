"""AI pace (server/pacing.py, user decision 2026-10-08).

A: a server started with --ai-pace normal (the play server's default; the
   e2e servers start with instant). The setup screen preselects "보통". In a
   game of one human seat against three heuristic seats, the AI decisions
   go to the game's worker, so after seat 0 ends its turn the page sees the
   AI seats move one refresh at a time: summary.thinking names each AI seat
   in turn, each AI turn banner ("플레이어N 차례") is drawn while the summary
   still names that seat's turn start, and the steps are spread over
   seconds instead of arriving in one snapshot. (At least three in four
   banners must land while their seat waits: a loaded machine can delay a
   refresh past the 1.6s the server gives the banner.)
B: the header's AI pace select switches the running game to "즉시" (the
   summary says so on both the response and the next refresh), and the
   next turn end comes back with no seat thinking and seat 0 to act.
C: an instant server (the e2e default) preselects "즉시", and a turn end
   comes back with no seat thinking.
"""

from __future__ import annotations

import time

from common import (
    LAPTOP_VIEWPORT,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from open_mode import settled

check = Check()
SEED = 5

# Every band drawn, with the summary the page held at that moment.
RECORDER = """
window.__banners = [];
document.addEventListener('DOMContentLoaded', () => {
  const box = document.getElementById('phase-banner');
  new MutationObserver((changes) => {
    for (const change of changes) for (const node of change.addedNodes) {
      if (!(node instanceof Element)) continue;
      if (!node.classList.contains('phase-banner')) continue;
      const s = state.summary || {};
      const d = s.decision || {};
      window.__banners.push({cue: node.dataset.cue, seat: node.dataset.seat ?? null,
        title: (node.querySelector('.phase-banner-title') || {}).textContent || '',
        thinking: s.thinking ?? null, owner: d.owner ?? null, kind: d.kind ?? null,
        at: performance.now()});
    }
  }).observe(box, {childList: true});
});
"""

SAMPLE_JS = """() => ({
  thinking: state.summary.thinking, owner: state.summary.decision
    ? state.summary.decision.owner : null,
  log: state.log ? state.log.count : 0, pace: state.summary.ai_pace,
  at: performance.now()})"""


def create(page, base: str, kinds=("human", "heuristic", "heuristic", "heuristic")):
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_function(
        "document.querySelectorAll('#seat-selects select').length === 4"
    )
    for seat, kind in enumerate(kinds):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", kind)
    # The base game: no Leader draft, so the first decisions are turns.
    set_rule_options(page)
    page.fill("#opt-seed", str(SEED))
    pace = page.input_value("#opt-ai-pace")
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    return pace


def own_turn(page, timeout: float = 90.0) -> bool:
    """Wait until seat 0 acts and no seat thinks."""
    try:
        page.wait_for_function(
            """() => !state.busy && refreshFlight === null && state.summary
              && state.summary.thinking === null && state.summary.decision
              && state.summary.decision.owner === 0
              && state.actions && state.actions.actions.length > 0""",
            timeout=timeout * 1000,
        )
        return True
    except Exception:  # noqa: BLE001
        return False


def play_own_turn(page) -> None:
    """Send an Agent (or reveal) and end the turn: the steps of one turn.

    An Agent is two steps, a card pick (`choose_agent_card`) and then a space
    pick (`place_agent`), so the walk takes the first row of each in turn."""
    taken = []
    for _ in range(40):
        assert settled(page, 20)
        summary = page.evaluate("state.summary")
        if summary["confirmation"] == 0:
            page.evaluate("confirmTurn()")
            assert settled(page, 20)
            return
        if summary["thinking"] is not None or summary["decision"]["owner"] != 0:
            return
        index = page.evaluate("""() => {
          const rows = state.actions.actions;
          const pick = (id) => rows.find((a) => a.action_id === id);
          const row = pick('finish_agent_turn') || pick('finish_reveal')
            || pick('choose_agent_card') || pick('place_agent')
            || pick('reveal_turn') || rows[0];
          return row.index;
        }""")
        taken.append(page.evaluate(f"state.actions.actions[{index}].action_id"))
        page.evaluate(f"applyAction({index})")
        if taken[-1] in ("finish_agent_turn", "finish_reveal"):
            assert settled(page, 20)
            return
    raise AssertionError(f"seat 0's turn did not end: {taken}")


def paced(browser) -> None:
    print("[A] a normal-paced server: the AI seats move one refresh at a time")
    with server("--ai-pace", "normal") as (base, _):
        context, page, rec = open_context(browser, "ai-pace", LAPTOP_VIEWPORT)
        context.add_init_script(RECORDER)
        pace = create(page, base)
        check.ok(pace == "normal", "the setup screen preselects the server pace", pace)
        check.ok(
            page.evaluate("state.summary.ai_pace") == "normal",
            "the game runs at the chosen pace",
        )
        check.ok(own_turn(page), "seat 0 gets its first turn")
        page.evaluate("window.__banners = []")
        play_own_turn(page)
        samples = []
        started = time.monotonic()
        while time.monotonic() - started < 90:
            sample = page.evaluate(SAMPLE_JS)
            samples.append(sample)
            if sample["thinking"] is None and sample["owner"] == 0:
                break
            time.sleep(0.1)
        took = time.monotonic() - started
        thinkers = {s["thinking"] for s in samples if s["thinking"] is not None}
        counts = sorted({s["log"] for s in samples})
        check.ok(len(thinkers) >= 2, "several AI seats think in turn", thinkers)
        check.ok(len(counts) >= 4, "the log grows over several refreshes", counts)
        banners = page.evaluate("window.__banners")
        turns = [b for b in banners if b["cue"] == "turn" and b["seat"] != "0"]
        live = [
            b for b in turns
            if b["thinking"] == int(b["seat"]) and b["owner"] == int(b["seat"])
            and b["kind"] == "turn"
        ]
        check.ok(turns, "the AI seats' turns are announced", banners)
        # The server gives each AI turn start its banner's 1.6s; a refresh
        # slowed by a loaded machine may land a little late now and then.
        check.ok(
            len(live) >= max(1, 3 * len(turns) // 4),
            f"the AI turn banners are drawn while that seat stands at its turn "
            f"({len(live)} of {len(turns)})",
            turns,
        )
        check.ok(
            took >= 1.2 * len(turns),
            f"the AI turns are spread out ({took:.1f}s for {len(turns)} turns)",
        )
        print("[B] switching the running game to instant")
        page.wait_for_selector("#ai-pace:not([hidden])")
        page.select_option("#ai-pace", "instant")
        page.wait_for_function("state.summary.ai_pace === 'instant'")
        check.ok(own_turn(page, 30), "seat 0 acts again")
        play_own_turn(page)
        page.wait_for_function("!state.busy && refreshFlight === null")
        check.ok(
            page.evaluate("state.summary.thinking === null")
            and own_turn(page, 3),
            "an instant game hands the turn back at once",
            page.evaluate("state.summary"),
        )
        check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
        context.close()


def instant(browser) -> None:
    print("[C] an instant server keeps the AI inside the request")
    with server() as (base, _):
        context, page, _ = open_context(browser, "ai-pace-instant", LAPTOP_VIEWPORT)
        pace = create(page, base)
        check.ok(pace == "instant", "the e2e server preselects instant", pace)
        check.ok(own_turn(page), "seat 0 gets its first turn")
        play_own_turn(page)
        check.ok(
            page.evaluate("state.summary.thinking === null") and own_turn(page, 3),
            "the turn comes back with every AI seat answered",
        )
        context.close()


def main() -> None:
    with chrome() as browser:
        paced(browser)
        instant(browser)
    check.finish()


if __name__ == "__main__":
    main()
