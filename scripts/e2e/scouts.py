"""E2E of the Arrakeen Scouts mode (docs/arrakeen-scouts-design.md slice 9).

One human seat (0) plays a seeded Scouts game against three heuristic seats
to the end, and on the way the page must show:

- the setup box, unchecked by default, and the header badge;
- the Scouts panel: the five subcommittees, each round's item with its
  lines, the mission pieces on the board, the secret picks waiting (and the
  seat's own pick), the running auction (its own bid, who confirmed);
- a secret pick's four buttons, each naming its line (not a bare index);
- a sealed bid as the count stepper plus the one turn-end row, which is the
  confirmation itself (D5);
- in English, no Hangul anywhere in the panel;
- after the game, the finished page without errors.

The seat picks each secret line and bids in turn so every kind is seen;
everything else takes the first legal action.
"""

from __future__ import annotations

import re
import sys
import time

from common import Check, chrome, open_context, server, set_rule_options
from open_mode import settled

check = Check()
SEEDS = (31, 44, 58)
HANGUL = re.compile(r"[가-힣]")

CHOOSE_JS = """(() => {
  const actions = state.actions.actions;
  const find = (id) => actions.findIndex((a) => a.action_id === id);
  const own = state.view.private || {};
  const bid = find("scouts_bid");
  if (bid >= 0) {
    if (own.scouts_bid >= 0) return find("confirm_scouts_bid");
    const bids = actions.filter((a) => a.action_id === "scouts_bid");
    const wanted = Math.min(2, bids.length - 1);
    return actions.findIndex(
      (a) => a.action_id === "scouts_bid" && a.arguments.count === wanted);
  }
  const pick = actions.filter((a) => a.action_id === "scouts_secret_pick");
  if (pick.length) return actions.indexOf(pick[state.view.round_number % pick.length]);
  const call = actions.findIndex(
    (a) => a.action_id === "scouts_call" && a.arguments.count === 1);
  if (call >= 0) return call;
  const join = actions.findIndex((a) => a.action_id === "scouts_join_mission");
  if (join >= 0) return join;
  const other = actions.findIndex((a) => a.action_id !== "switch_graft_card");
  return other >= 0 ? other : 0;
})()"""


def create(page, base: str, seed: int) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    check.ok(not page.is_checked("#opt-scouts"), "the Scouts box starts unchecked")
    set_rule_options(page, "choam")
    page.set_checked("#opt-leader-draft", False)
    page.set_checked("#opt-scouts", True)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")


def panel_text(page) -> str:
    return page.evaluate("document.getElementById('scouts-panel').innerText")


def play(page, seen: dict[str, bool], limit: int = 4000) -> bool:
    for _ in range(limit):
        assert settled(page, 30)
        if page.evaluate("state.summary.finished"):
            return True
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        inspect(page, seen)
        page.evaluate(f"applyAction({page.evaluate(CHOOSE_JS)})")
    return False


def inspect(page, seen: dict[str, bool]) -> None:
    ids = page.evaluate("state.actions.actions.map((a) => a.action_id)")
    text = panel_text(page)
    if not seen.get("subcommittees") and page.evaluate(
        "state.view.scouts_subcommittees.length === 5"
    ):
        rows = page.evaluate(
            "[...document.querySelectorAll('#scouts-panel .scouts-row[data-item]')]"
            ".map((r) => r.dataset.item)"
        )
        seen["subcommittees"] = check.ok(
            all(
                item in rows
                for item in page.evaluate("state.view.scouts_subcommittees")
            ),
            "the panel lists the five subcommittees",
            rows,
        )
    if "scouts_secret_pick" in ids and not seen.get("pick"):
        details = page.evaluate(
            "state.actions.actions.filter((a) => a.action_id === 'scouts_secret_pick')"
            ".map((a) => a.detail_ko || a.detail)"
        )
        buttons = page.evaluate("document.getElementById('actions').innerText")
        seen["pick"] = check.ok(
            len(details) == 4 and all(details) and "라운드" in buttons,
            "a secret pick's buttons name their lines",
            (details, buttons[:200]),
        )
    if "scouts_bid" in ids and not seen.get("bid"):
        stepper = page.evaluate(
            "Boolean(document.querySelector("
            "'#actions .count-row[data-action=\"scouts_bid\"]'))"
        )
        turn_end = page.evaluate(
            "Boolean(document.querySelector('#decision-banner .turn-end-row'))"
            " && turnEndAction(state.actions.actions)?.action_id"
            " === 'confirm_scouts_bid'"
        )
        seen["bid"] = check.ok(
            stepper and turn_end,
            "a sealed bid is a count stepper and the turn-end row confirms it",
            (stepper, turn_end),
        )
    if page.evaluate(
        "state.view.private && state.view.private.scouts_bid >= 0"
    ) and not seen.get("own_bid"):
        seen["own_bid"] = check.ok(
            "내 입찰액" in text, "the panel shows the seat's own bid", text[-300:]
        )
    if page.evaluate(
        "Boolean(state.view.private && state.view.private.scouts_secret_picks.length)"
    ) and not seen.get("own_pick"):
        seen["own_pick"] = check.ok(
            "내 선택" in text and "비밀 선택" in text,
            "the panel shows the seat's own waiting pick",
            text[-300:],
        )
    if page.evaluate("state.view.scouts_goods.length > 0") and not seen.get("pieces"):
        seen["pieces"] = check.ok(
            "임무 조각" in text, "the panel shows mission pieces", text[-300:]
        )
    if page.evaluate("state.view.scouts_market_cards.length > 0") and not seen.get(
        "market"
    ):
        seen["market"] = check.ok(
            "공개된 카드" in text, "the panel shows Critical Moment's cards"
        )
    if not seen.get("english") and page.evaluate("state.view.round_number >= 4"):
        page.evaluate("setLanguage('en')")
        assert settled(page, 10)
        english = panel_text(page)
        seen["english"] = check.ok(
            "Arrakeen Scouts" in english and not HANGUL.search(english),
            "in English the panel carries no Hangul",
            HANGUL.findall(english)[:10],
        )
        page.evaluate("setLanguage('ko')")
        assert settled(page, 10)


def main() -> None:
    wanted = (
        "subcommittees",
        "pick",
        "bid",
        "own_bid",
        "own_pick",
        "pieces",
        "english",
    )
    with server() as (base, _server_log), chrome() as browser:
        _, page, _ = open_context(browser, "scouts")
        seen: dict[str, bool] = {}
        for seed in SEEDS:
            print(f"[game] seed {seed}")
            create(page, base, seed)
            check.ok(
                "아라킨 스카웃" in page.evaluate("el('header-status').innerText"),
                "the header names the Scouts mode",
            )
            finished = play(page, seen)
            check.ok(finished, f"seed {seed} plays to the end")
            check.ok(
                page.evaluate("!document.getElementById('scouts-panel').hidden"),
                "the finished game still shows the panel",
            )
            if all(seen.get(name) for name in wanted):
                break
        for name in wanted:
            check.ok(bool(seen.get(name)), f"seen: {name}")
    check.finish()


if __name__ == "__main__":
    sys.exit(main())
