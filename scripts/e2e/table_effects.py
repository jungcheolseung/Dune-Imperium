"""Seat-panel changes and the Agent space glow (effects.js, 2026-10-08).

A: one human seat against three heuristic seats, base game, played for a
   stretch of steps. After every step the changes that rose over the seat
   panels (#stat-floats) add up, per seat and number, to the difference of
   that public number (Victory Points, Solari, spice, water) between the
   views before and after the step, each drawn over its own number. An
   undo draws none, and neither does a reload.
B: on every step, the board's glowing space (.hotspot.cue-space) is
   exactly the space of the Agent card cue on screen, in that seat's
   colour, also after a re-render; with no such cue nothing glows.
"""

from __future__ import annotations

from common import LAPTOP_VIEWPORT, Check, chrome, open_context, server
from open_mode import create_game, settled

check = Check()
SEED = 7

RECORDER = """
window.__floats = [];
document.addEventListener('DOMContentLoaded', () => {
  new MutationObserver((changes) => {
    for (const change of changes) for (const node of change.addedNodes) {
      if (!(node instanceof Element)) continue;
      const seat = `#seats .seat[data-seat="${node.dataset.seat}"]`;
      const stat = document.querySelector(
        `${seat} .stat[data-stat="${node.dataset.stat}"]`);
      const box = stat && stat.getBoundingClientRect();
      const left = parseFloat(node.style.left);
      window.__floats.push({seat: Number(node.dataset.seat), stat: node.dataset.stat,
        text: node.textContent,
        over: Boolean(box) && left >= box.left - 1 && left <= box.right + 1});
    }
  }).observe(document.getElementById('stat-floats'), {childList: true});
});
"""

VALUES = """() => state.view.players.map((p) => ({victory_point: p.victory_points,
  solari: p.resources.solari, spice: p.resources.spice, water: p.resources.water}))"""

GLOW = """() => {
  const c = playEffects.current;
  const glow = [...document.querySelectorAll('#board .hotspot.cue-space')].map((h) => ({
    space: h.dataset.space, color: h.style.getPropertyValue('--cue-color')}));
  return {cue: c && c.spaceId ? {space: c.spaceId, color: SEAT_COLORS[c.seat]} : null,
    glow};
}"""


def float_value(text: str) -> int:
    sign = -1 if text.startswith("−") else 1
    return sign * int(text.lstrip("+−"))


def check_glow(page, glows: list[int]) -> bool:
    seen = page.evaluate(GLOW)
    want = [seen["cue"]] if seen["cue"] else []
    if seen["cue"]:
        glows[0] += 1
    return seen["glow"] == want


def main() -> None:
    with server() as (base, _), chrome() as browser:
        context, page, rec = open_context(browser, "table-effects", LAPTOP_VIEWPORT)
        context.add_init_script(RECORDER)
        create_game(page, base, humans=(0,), seed=SEED)
        print("[A] seat-panel changes and [B] the Agent space glow, step by step")
        glows = [0]
        floats_seen = 0
        mismatches = 0
        glow_misses = 0
        undone = False
        for _ in range(160):
            assert settled(page, 30)
            if page.evaluate("state.summary.finished"):
                break
            before = page.evaluate(VALUES)
            page.evaluate("window.__floats = []")
            if page.evaluate("state.summary.confirmation === state.viewSeat"):
                page.evaluate("confirmTurn()")
            else:
                index = page.evaluate("""() => {
                  const rows = state.actions.actions;
                  const pick = (id) => rows.find((a) => a.action_id === id);
                  return (pick('agent_turn') || rows[0]).index;
                }""")
                page.evaluate(f"applyAction({index})")
            assert settled(page, 30)
            after = page.evaluate(VALUES)
            floats = page.evaluate("window.__floats")
            floats_seen += len(floats)
            sums: dict[tuple[int, str], int] = {}
            for item in floats:
                key = (item["seat"], item["stat"])
                sums[key] = sums.get(key, 0) + float_value(item["text"])
            want = {
                (seat, key): after[seat][key] - before[seat][key]
                for seat in range(4)
                for key in after[seat]
                if after[seat][key] != before[seat][key]
            }
            if sums != want or not all(item["over"] for item in floats):
                mismatches += 1
                check.ok(False, "the rising changes add up to the step", (sums, want))
                if mismatches > 3:
                    break
            if not check_glow(page, glows):
                glow_misses += 1
            page.evaluate("render(); render({foreign: true})")
            if not check_glow(page, glows):
                glow_misses += 1
            # Take one step back once, and see that the undo draws nothing.
            undo = page.evaluate(
                "(state.summary.undo || []).some((u) => u.seat === state.viewSeat)"
            )
            if undo and not undone and floats:
                undone = True
                page.evaluate("window.__floats = []")
                page.evaluate("submitUndo(state.viewSeat, 1)")
                assert settled(page, 30)
                check.ok(
                    page.evaluate("window.__floats.length") == 0,
                    "an undo draws no change",
                )
        check.ok(mismatches == 0, "every step's changes matched its numbers")
        check.ok(floats_seen >= 20, f"changes rose over the seats ({floats_seen})")
        check.ok(undone, "the walk took a step back")
        check.ok(
            glow_misses == 0, f"the glowing space follows the Agent cue ({glow_misses})"
        )
        check.ok(glows[0] >= 3, f"Agent spaces glowed during the walk ({glows[0]})")
        page.evaluate("window.__floats = []")
        page.reload()
        page.wait_for_function("state.view !== null && refreshFlight === null")
        page.evaluate("render(); render({foreign: true})")
        check.ok(
            page.evaluate("window.__floats.length") == 0,
            "a reload is a quiet baseline",
        )
        check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
        context.close()
    check.finish()


if __name__ == "__main__":
    main()
