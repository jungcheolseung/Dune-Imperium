"""E2E for ITEM 8a: the action log's glow boundary in remote play
(panels.js renderLog / ownGlowFrom, 2026-09-25).

Bug this reproduces: the log used one number, "entries that arrived since
the previous render", for two different jobs -- which turn cards get the
.fresh class, and where the list auto-scrolls to. Locally a whole AI batch
arrives in one render, so the two jobs never disagreed; in remote play
every opponent step triggers its own refresh+render, so by the time seat
0's turn comes back around only the LAST opponent's step is marked fresh,
even though three seats acted since seat 0 last moved (reproduced by
freshActors: [3] while actorsSinceMyLastAction was [1, 2, 3]).

The fix splits the number in two: arrivedFrom keeps the old "since the
previous render" bookkeeping and decides only the scroll target; glowFrom
is computed fresh every render from the viewing seat's own last live entry
(ownGlowFrom) and decides .fresh, so it does not matter how many separate
renders happened in between.

(a) is the scenario above: a --remote server, seat 0 in a real browser,
seats 1-3 driven over raw HTTP (their own seat cookies, no browser --
that's what makes each of their steps arrive as a doorbell push and a
render of its own on seat 0's page) with a pause between their steps. At
several of seat 0's turn starts, the set of glowing cards must be exactly
the cards holding a log entry after seat 0's own last action -- all of
seats 1-3's steps since then, plus any neutral card in that range, none
before. This is the one assertion the A/B run (README.md) must show
failing on the client before this fix.

(b) is the "Consequences to keep" case from the same design: on a plain
open server (one render covers a whole AI batch, so the old bug never
showed here), human seat 0 + three heuristic seats. Right after seat 0
hands its turn to the AI seats, seat 0's own card is not fresh anymore
(it used to glow at its own last move) but the AI cards that answered it,
landing in that same render, are.
"""

from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.request

from common import (
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from open_mode import settled
from remote import wait_for_setup, wait_until

check = Check()

KEY = "e2e-fresh-admin-key"
VIEWPORT = {"width": 1440, "height": 900}
# How many of seat 0's own turn starts (a) checks the glowing set at.
MY_TURNS = 3
# Safety cap on opponents' raw-HTTP steps overall, so a stuck game fails
# fast instead of hanging.
MAX_OPPONENT_STEPS = 300
# Paced like real humans acting seconds apart, and long enough that each
# opposing step reliably lands as its own doorbell push and render on seat
# 0's idle page rather than being coalesced with the next one.
PAUSE = 0.3
# A generous game-play seed for (b): any seed works, this one just keeps
# the run fast and reaches the AI hand-off within a few of seat 0's steps.
LOCAL_SEED = 20260924
# Mirrors EXPLICIT_TURN_END_IDS in render.js / EXPLICIT_TURN_ENDS in
# server/turn_end.py (turn_end.py's own copy of the same set): applying one
# of these ends seat 0's turn and lets the heuristic seats play out inside
# that SAME POST/response -- the "own action and the AI's reply land in one
# render" case (b) is about. A turn that closes by a *hold* instead (a
# separate confirmTurn() press) is a render of its own with no new entry of
# seat 0's own in it, which is not that case, so (b) prefers one of these
# whenever a legal action offers it.
EXPLICIT_TURN_END_IDS = {
    "finish_agent_turn",
    "finish_reveal",
    "pass_combat_intrigue",
    "pass_endgame_intrigue",
}


class HttpSeat:
    """One remote seat driven by raw HTTP with its own cookie jar -- a
    second browser tab without a UI, and without the render-coalescing a
    real one would give the OTHER open tab watching it. Adapted from the
    scratch reproduction that found this bug (freshActors: [3] while
    actorsSinceMyLastAction was [1, 2, 3]; see the remote_fresh row in
    scripts/e2e/README.md for the finished scenario)."""

    def __init__(self, base: str) -> None:
        self.base = base
        self.cookies: dict[str, str] = {}

    def _req(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.cookies:
            cookie_header = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
            req.add_header("Cookie", cookie_header)
        with urllib.request.urlopen(req) as resp:
            for header in resp.headers.get_all("Set-Cookie") or []:
                pair = header.split(";", 1)[0]
                key, value = pair.split("=", 1)
                self.cookies[key] = value
            return json.loads(resp.read())

    def get(self, path: str):
        return self._req("GET", path)

    def post(self, path: str, body: dict):
        return self._req("POST", path, body)


# The expected/actual comparison is worked out independently of panels.js's
# own ownGlowFrom (straight from state.log.entries), so the test is not
# just replaying the production code against itself; logGroups() is reused
# only to find card boundaries (which entries share a card), which is not
# what this bug is about. logGroups() renders cards in this same order, so
# a positional zip against the DOM is exact.
GLOW_CHECK_JS = """(seat) => {
  const entries = state.log.entries;
  let lastOwn = -1;
  for (const e of entries) {
    if (e.type === "action" && e.actor === seat && !e.undone) lastOwn = e.index;
    else if (e.type === "undo" && e.seat === seat) lastOwn = e.index;
  }
  const groups = logGroups(entries).filter((g) => g.kind !== "undo");
  const expected = groups.map((g) =>
    g.kind === "neutral"
      ? g.lastIndex > lastOwn
      : g.entries.some((entry) => entry.index > lastOwn)
  );
  const cards = [...document.querySelectorAll("#action-log .turn-card")].filter(
    (card) => !card.classList.contains("undo-marker")
  );
  const actual = cards.map((card) => card.classList.contains("fresh"));
  return {
    lastOwn, expected, actual,
    entryCount: entries.length, cardCount: cards.length,
  };
}"""


def glow_matches(page, seat: int, label: str) -> None:
    result = page.evaluate(GLOW_CHECK_JS, seat)
    check.ok(
        result["expected"] == result["actual"],
        f"{label}: exactly the cards holding entries after seat {seat}'s own "
        "last action glow, none before",
        result,
    )


def active_actor(summary: dict) -> int | None:
    confirmation = summary.get("confirmation")
    if isinstance(confirmation, int):
        return confirmation
    decision = summary.get("decision")
    return decision["owner"] if decision else None


def play_seat0_turn(page) -> None:
    """Play out seat 0's whole turn in the browser, exactly like the
    reproduction and log_follow.py's take_step: a hold confirms, a
    decision takes the first legal action, until neither is seat 0's to
    make anymore."""
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            return
        if page.evaluate("state.summary.confirmation === 0"):
            page.evaluate("confirmTurn()")
        elif page.evaluate(
            "Boolean(state.actions && state.actions.actions.length) "
            "&& state.summary.decision && state.summary.decision.owner === 0"
        ):
            index = page.evaluate("state.actions.actions[0].index")
            page.evaluate(f"applyAction({index})")
        else:
            return
        assert settled(page, 20)
    raise AssertionError("seat 0's turn did not finish within the time budget")


def scenario_remote() -> None:
    print("[a] --remote server, seat 0 in a browser, seats 1-3 over raw HTTP")
    with (
        server("--remote", "--admin-key", KEY) as (base, server_log),
        chrome() as browser,
    ):
        context, page, rec = open_context(browser, "seat0", VIEWPORT)
        try:
            page.goto(f"{base}/#admin={KEY}")
            wait_for_setup(page)
            # A remote room already defaults every seat to human (remote.py
            # [1]); leader draft off keeps this scenario to plain turns.
            set_rule_options(page)
            page.set_checked("#opt-leader-draft", False)
            page.click("#create-game")
            page.wait_for_selector("#lobby-screen:not([hidden])")
            game_id = page.evaluate("state.gameId")
            page.fill("#lobby-name", "Seat0")
            page.click("#lobby-seats li[data-seat='0'] button")
            page.wait_for_selector("#game-screen:not([hidden])")
            page.wait_for_function("state.view !== null && refreshFlight === null")

            opponents = {}
            for seat in (1, 2, 3):
                client = HttpSeat(base)
                client.post(
                    f"/games/{game_id}/seats/{seat}/claim", {"name": f"P{seat}"}
                )
                opponents[seat] = client
            # Let the claims themselves settle before driving steps.
            check.ok(
                wait_until(
                    page,
                    "state.summary && state.summary.players.slice(1)"
                    ".every((p) => p.claimed)",
                    5,
                    "seat 0's page sees all three opponents claimed",
                ),
                "seat 0's page sees all three opponents claimed",
            )

            my_turns_seen = 0
            opponent_steps = 0
            while my_turns_seen < MY_TURNS and opponent_steps < MAX_OPPONENT_STEPS:
                summary = opponents[1].get(f"/games/{game_id}")
                if summary["finished"]:
                    break
                actor = active_actor(summary)
                if actor == 0:
                    check.ok(
                        wait_until(
                            page,
                            "typeof state.summary.confirmation === 'number'"
                            " ? state.summary.confirmation === 0"
                            " : (state.summary.decision"
                            " && state.summary.decision.owner === 0)",
                            5,
                            "seat 0's page has caught up to its own turn",
                        ),
                        "seat 0's page has caught up to its own turn",
                    )
                    glow_matches(page, 0, f"seat 0 turn start #{my_turns_seen + 1}")
                    my_turns_seen += 1
                    play_seat0_turn(page)
                    continue
                if actor is None:
                    time.sleep(0.1)
                    continue
                client = opponents[actor]
                body = {
                    "seat": actor,
                    "revision": summary["revision"],
                    "undo_count": summary["undo_count"],
                }
                try:
                    if summary.get("confirmation") == actor:
                        client.post(f"/games/{game_id}/confirm", body)
                    else:
                        actions = client.get(f"/games/{game_id}/seats/{actor}/actions")
                        client.post(
                            f"/games/{game_id}/actions",
                            {**body, "index": actions["actions"][0]["index"]},
                        )
                except urllib.error.HTTPError as err:
                    print(f"  .. http error {err.code} {err.read()[:200]!r}")
                    time.sleep(0.2)
                    continue
                opponent_steps += 1
                time.sleep(PAUSE)
            check.ok(
                my_turns_seen == MY_TURNS,
                f"checked the glowing set at {MY_TURNS} of seat 0's turn starts",
                my_turns_seen,
            )

            failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
            check.ok(not failed, "no failed requests on seat 0's page", failed[:5])
            check.ok(
                not rec.js_errors,
                "no JS exceptions on seat 0's page",
                rec.js_errors[:5],
            )
        finally:
            context.close()
            shutil.copy(server_log, SERVER_LOG_COPY)
        log_text = server_log.read_text()
        bad = "Traceback" in log_text or "ERROR" in log_text
        check.ok(not bad, f"no server errors (see {SERVER_LOG_COPY})")


OWN_CARD_CHECK_JS = """(seat) => {
  const groups = logGroups(state.log.entries).filter((g) => g.kind !== "undo");
  let lastOwnGroup = -1;
  groups.forEach((g, i) => {
    if (g.kind === "turn" && g.actor === seat) lastOwnGroup = i;
  });
  const cards = [...document.querySelectorAll("#action-log .turn-card")].filter(
    (card) => !card.classList.contains("undo-marker")
  );
  const ownFresh =
    lastOwnGroup >= 0 ? cards[lastOwnGroup].classList.contains("fresh") : null;
  const later = cards.slice(lastOwnGroup + 1);
  const allLaterFresh =
    later.length > 0 && later.every((card) => card.classList.contains("fresh"));
  return {
    lastOwnGroup, ownFresh, allLaterFresh,
    laterCount: later.length, cardCount: cards.length,
  };
}"""


def scenario_local() -> None:
    print("[b] open server, seat 0 human + three heuristic seats")
    with server() as (base, log_path):
        with chrome() as browser:
            context, page, rec = open_context(browser, "local-fresh", VIEWPORT)
            try:
                page.goto(base + "/")
                wait_for_setup(page)
                for seat in range(4):
                    page.select_option(
                        f"#seat-selects select[data-seat='{seat}']",
                        "human" if seat == 0 else "heuristic",
                    )
                set_rule_options(page)
                page.set_checked("#opt-leader-draft", False)
                page.fill("#opt-seed", str(LOCAL_SEED))
                page.click("#create-game")
                page.wait_for_selector("#game-screen:not([hidden])")
                page.wait_for_function("state.view !== null && refreshFlight === null")

                # A local (open) server resolves every heuristic seat's whole
                # turn synchronously as part of settling seat 0's own step,
                # but only when that step ends the turn without a separate
                # confirmTurn() press (a hold's confirm carries no new
                # entry of seat 0's own, so its render would not test the
                # "same render" case (b) is about) -- so an explicit
                # turn-end action is preferred whenever one is legal, and
                # "handed off" requires seat 0's own entry and an AI seat's
                # entry to both be new in that one response.
                ends_js = json.dumps(sorted(EXPLICIT_TURN_END_IDS))
                pick_action_js = (
                    "(() => { const acts = state.actions.actions;"
                    " const ends = new Set(" + ends_js + ");"
                    " const explicit = acts.find((a) => ends.has(a.action_id));"
                    " return (explicit || acts[0]).index; })()"
                )
                deadline = time.monotonic() + 60.0
                handed_off = False
                while time.monotonic() < deadline:
                    assert settled(page, 20)
                    if page.evaluate("state.summary.finished"):
                        break
                    if page.evaluate("state.summary.confirmation === 0"):
                        before = page.evaluate("state.log.entries.length")
                        page.evaluate("confirmTurn()")
                    elif page.evaluate(
                        "Boolean(state.actions && state.actions.actions.length) "
                        "&& state.summary.decision"
                        " && state.summary.decision.owner === 0"
                    ):
                        index = page.evaluate(pick_action_js)
                        before = page.evaluate("state.log.entries.length")
                        page.evaluate(f"applyAction({index})")
                    else:
                        time.sleep(0.02)
                        continue
                    assert settled(page, 20)
                    added = page.evaluate(f"state.log.entries.slice({before})")
                    added_by_self = any(
                        e["type"] == "action" and e["actor"] == 0 for e in added
                    )
                    added_by_ai = any(
                        e["type"] == "action" and e["actor"] not in (0, None)
                        for e in added
                    )
                    if added_by_self and added_by_ai:
                        handed_off = True
                        break
                check.ok(
                    handed_off,
                    "seat 0 handed its turn to the AI seats within the time budget",
                )
                if handed_off:
                    result = page.evaluate(OWN_CARD_CHECK_JS, 0)
                    if check.ok(
                        result["lastOwnGroup"] >= 0,
                        "seat 0's own turn card is in the log",
                        result,
                    ):
                        check.ok(
                            result["ownFresh"] is False,
                            "seat 0's own card is no longer marked fresh right "
                            "after its own step",
                            result,
                        )
                        check.ok(
                            result["allLaterFresh"] is True,
                            "every AI card that answered it, in the same render, "
                            "is marked fresh",
                            result,
                        )

                failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
                check.ok(not failed, "no failed requests", failed[:5])
                check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            finally:
                context.close()
            errors = [
                line
                for line in log_path.read_text().splitlines()
                if "ERROR" in line or "Traceback" in line
            ]
            check.ok(
                not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3]
            )
            SERVER_LOG_COPY.write_text(log_path.read_text())


def main() -> None:
    scenario_remote()
    scenario_local()
    check.finish()


if __name__ == "__main__":
    main()
