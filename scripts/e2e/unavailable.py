"""E2E of the greyed-out choices of the whole game (user request 2026-09-29).

An option the seat cannot take right now is shown, not selectable, with the
reason, and becomes selectable as soon as it can be taken (and the reverse):
Arrakeen Scouts lines already did (scouts.py); the server's `unavailable`
payload (display/unavailable.py) does it for the rest of the game. One human
seat (0) plays seeded games against three heuristic seats until it has met
both of these, and the page must show:

- a Reveal with cards it cannot afford: one greyed-out row per `acquire`
  row of the payload, under the rows of exactly the legal acquisitions;
- an Intrigue card it holds but cannot play in an open Intrigue window: one
  greyed-out row per `intrigue` row of the payload;
- for each: every row says why (a badge), is announced as a disabled button
  and is not an action row, and a click on it changes nothing; no payload
  row is a legal action; in English the action list carries no Hangul;
- the table: every card the payload dims (`refs`) is dimmed wherever it is
  drawn, with the reason in its title, only those, and never a lit one.

The seat takes the first legal action (not a graft switch), so it buys what
the first row offers and plays along; the seeds were picked to meet an
unplayable Intrigue card early.
"""

from __future__ import annotations

import re
import sys
import time

from common import Check, chrome, open_context, server, set_rule_options
from open_mode import settled

check = Check()
SEEDS = (3, 8, 13, 21)
HANGUL = re.compile(r"[가-힣]")

CHOOSE_JS = """(() => {
  const actions = state.actions.actions;
  const other = actions.findIndex((a) => a.action_id !== "switch_graft_card");
  return other >= 0 ? other : 0;
})()"""

# The payload rows of one surface against the greyed-out rows on the page.
ROWS_JS = """(surface) => {
  const info = state.actions.unavailable;
  const rows = info ? info.rows.filter((r) => r.surface === surface) : [];
  const same = (a, b) => a.action_id === b.action_id
    && JSON.stringify(a.arguments) === JSON.stringify(b.arguments);
  const grey = [...document.querySelectorAll(
    `#actions .unavailable-item[data-surface="${surface}"]`)];
  return {
    payload: rows.map((r) => r.key),
    grey: grey.map((g) => g.dataset.key),
    badges: grey.map(
      (g) => (g.querySelector('.unavailable-badge') || {}).innerText || ''),
    aria: grey.every((g) => g.getAttribute('aria-disabled') === 'true'
      && g.getAttribute('role') === 'button' && !g.closest('.action-item')),
    legal: rows.filter((r) => state.actions.actions.some((a) => same(a, r.action)))
      .map((r) => r.key),
  };
}"""

# The legal acquisitions against their ordinary action rows.
BUYS_JS = """(() => {
  const legal = state.actions.actions.filter((a) => a.action_id.startsWith('acquire'))
    .map((a) => a.index).sort((a, b) => a - b);
  const rows = [...document.querySelectorAll('#actions .action-item')]
    .map((r) => Number(r.dataset.index)).filter((i) => legal.includes(i))
    .sort((a, b) => a - b);
  return { legal, rows };
})()"""

# The dimmed table cards against the payload's refs.
REFS_JS = """(() => {
  const refs = (state.actions.unavailable || {}).refs || {};
  const cards = [...document.querySelectorAll('.vcard')];
  const blocked = cards.filter((c) => c.classList.contains('blocked'));
  return {
    refs: Object.keys(refs),
    stray: blocked.filter((c) => !(c.dataset.instance in refs))
      .map((c) => c.dataset.instance),
    undimmed: cards.filter((c) => c.dataset.instance in refs
      && !c.classList.contains('blocked')).map((c) => c.dataset.instance),
    lit: blocked.filter((c) => c.classList.contains('legal')).length,
    untitled: blocked.filter((c) => !c.title.includes(' — ')).length,
    shown: blocked.length,
  };
})()"""


def create(page, base: str, seed: int) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, "choam", "immortality")
    page.set_checked("#opt-leader-draft", False)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")


def has_rows(page, surface: str) -> bool:
    return page.evaluate(
        "(surface) => Boolean(state.actions.unavailable"
        " && state.actions.unavailable.rows.some((r) => r.surface === surface))",
        surface,
    )


def inspect_surface(page, surface: str, label: str) -> bool:
    """The greyed-out rows of `surface` are the payload's, each says why,
    none is legal, a click changes nothing, English has no Hangul."""

    rows = page.evaluate(ROWS_JS, surface)
    ok = check.ok(
        rows["grey"] == rows["payload"] and rows["payload"] and rows["aria"],
        f"{label}: one greyed-out row per payload row, a disabled button",
        rows,
    )
    ok &= check.ok(
        all(badge.strip() for badge in rows["badges"]),
        f"{label}: each greyed-out row says why",
        rows["badges"],
    )
    ok &= check.ok(not rows["legal"], f"{label}: no greyed-out row is legal", rows)
    revision = page.evaluate("state.summary.revision")
    # force: the row is announced as a disabled button (aria-disabled), so
    # Playwright would wait for it to be enabled; the click must still land.
    page.click(
        f'#actions .unavailable-item[data-surface="{surface}"] >> nth=0', force=True
    )
    time.sleep(0.3)
    assert settled(page, 10)
    ok &= check.ok(
        page.evaluate("state.summary.revision") == revision
        and page.evaluate("document.getElementById('game-error').hidden"),
        f"{label}: a click on a greyed-out row changes nothing",
    )
    page.evaluate("setLanguage('en')")
    assert settled(page, 10)
    english = page.evaluate("document.getElementById('actions').innerText")
    count = page.evaluate(
        "(surface) => document.querySelectorAll("
        "`#actions .unavailable-item[data-surface=\"${surface}\"]`).length",
        surface,
    )
    ok &= check.ok(
        not HANGUL.search(english) and count == len(rows["grey"]),
        f"{label}: in English the greyed-out rows carry no Hangul",
        HANGUL.findall(english)[:10],
    )
    page.evaluate("setLanguage('ko')")
    assert settled(page, 10)
    return ok


def inspect_refs(page, label: str) -> bool:
    refs = page.evaluate(REFS_JS)
    return check.ok(
        refs["shown"] > 0
        and not refs["stray"]
        and not refs["undimmed"]
        and refs["lit"] == 0
        and refs["untitled"] == 0,
        f"{label}: the table dims exactly the payload's cards, each with its reason",
        refs,
    )


def inspect(page, seen: dict[str, bool]) -> None:
    if not seen.get("acquire") and has_rows(page, "acquire"):
        buys = page.evaluate(BUYS_JS)
        ok = check.ok(
            buys["legal"] == buys["rows"],
            "Reveal: the cards it can buy are the rows of exactly the legal buys",
            buys,
        )
        ok &= inspect_surface(page, "acquire", "Reveal")
        ok &= inspect_refs(page, "Reveal")
        seen["acquire"] = ok
    if not seen.get("intrigue") and has_rows(page, "intrigue"):
        ok = inspect_surface(page, "intrigue", "Intrigue")
        ok &= inspect_refs(page, "Intrigue")
        seen["intrigue"] = ok


def play(page, seen: dict[str, bool], limit: int = 1500) -> None:
    for _ in range(limit):
        assert settled(page, 30)
        if page.evaluate("state.summary.finished") or all(
            seen.get(key) for key in ("acquire", "intrigue")
        ):
            return
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        inspect(page, seen)
        page.evaluate(f"applyAction({page.evaluate(CHOOSE_JS)})")


def main() -> None:
    with server() as (base, _server_log), chrome() as browser:
        _, page, _ = open_context(browser, "unavailable")
        seen: dict[str, bool] = {}
        for seed in SEEDS:
            if all(seen.get(key) for key in ("acquire", "intrigue")):
                break
            print(f"[game] seed {seed}")
            create(page, base, seed)
            play(page, seen)
        for key in ("acquire", "intrigue"):
            check.ok(seen.get(key, False), f"met and checked: {key}")
    check.finish()


if __name__ == "__main__":
    sys.exit(main())
