"""E2E for ITEM 8c: a trash row names the zone when a same-named copy sits
in another one of the seat's own piles (2026-09-25).

The Feyd track trash (leader_abilities.py, Personal Training's paid/optional
trash), the Desert Tactics trash (board_effects.py) and the Combat reward
trash (combat.py) all offer the seat's own hand, then discard pile, then
in-play cards as trash candidates (`(*owner.hand, *owner.discard_pile,
*counted_in_play(owner))` in the engine now, all three call sites). Two
candidates of the same card
(a starter Dagger's two copies, a leader's own reserve card, ...) used to
render as identical rows -- "카드 {trash} (...) — 단검" twice -- with nothing
saying which pile a row means, even though trashing the hand copy costs
that card's play this round while a discard-pile or in-play copy does not.

`appendActionItems` (render.js) now finds, within one decision's own action
list, every group of rows that share an action_id and a card (same baseId)
but sit in different piles of the *viewing seat's own view* (`ownCardZone`);
each such row gets a suffix naming its pile through the TERMS glossary
word -- {hand}, {discard_pile}, or the new {in_play} ([Main p. 20]) --
appended by `zoneSuffixNode`/`actionItem`. Rows whose only same-named
sibling shares their own pile are untouched (interchangeable copies), and
`describeAction` itself (shared with the turn log, panels.js turnLine) is
never touched, so the log keeps reading the plain card name.

Reaching a real trash decision with a same-named duplicate split across two
piles needs a real game: a one-off raw-HTTP walk (no browser, not kept --
it was a throwaway script, not a committed one) replaying "confirm every
hold at once; otherwise take the seat's own first legal action" against
seed 0 with the Leader draft off (so seat 0 keeps its server-assigned
Leader) landed seat 0 on a `trash_leader_card` decision (Feyd Rautha
Harkonnen's Personal Training track) at its 106th decision, offering a
"Prepare the Way" reserve card from hand and its other copy from in play.
The same policy is replayed live against the browser below rather than
hard-coded to a step count, so a content or engine change that only shifts
*when* the decision appears still gets caught by this script; if the
decision moves out of the step budget entirely, re-running that same
walk (a fresh throwaway script against this policy) finds a new seed.

That happened on 2026-10-01: OQ-095 ends every Agent turn only through its
owner's `finish_agent_turn`, so the first-legal-action walk now also plays
the optional end-of-turn actions listed before it (troop deploys, Intrigue
cards) and seed 0 never offered such a pair again. The same walk, replayed
in-process over seeds 0-59, found seed 1: the same Leader and track
(`trash_leader_card`, Personal Training's paid trash) at its 19th decision,
offering a starter "Dune, the Desert Planet" from hand and its other copy
from in play. Seeds whose pair has two copies in one pile (several
"Prepare the Way" in the discard pile) are no use here: those copies are
interchangeable and rightly read the same, so "the rows differ" below
would fail on them.

Zone headings (user request 2026-10-05: "which rows are hand, which are the
discard pile"). `appendActionItems` also puts a heading over each run of
rows whose card sits in one of the seat's own piles -- the pile's word and
the number of rows under it ("핸드 · 4", "Hand · 4") -- whenever the list's
card rows span two or more piles, and a divider before the rows that follow
them (a decline). The per-row suffix above stays. Checked here:

* seed 1 (the decision above): hand then in play;
* seed 5 (Leader draft off, base ruleset), 57 decisions into the same walk:
  a `trash_leader_card` decision offering all three piles at once (found by
  an in-browser search of seeds 0-11; seeds 3, 9 and 11 also offer three);
  at 1366x768, both languages, with screenshots in E2E_SHOTS_DIR;
* a list with one pile (the full Agent-turn list: only hand cards) and
  synthetic subsets of the real three-pile decision (`appendActionItems`
  called on a detached box) get no headings, and an interleaved order gets
  one heading per run.
The expected headings, counts and zones are rebuilt here from
`state.actions` and the view's hand / discard_pile / in_play lists, never
from the rendered text.
"""

from __future__ import annotations

import itertools
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from common import (
    LAPTOP_VIEWPORT,
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from lang import switch as switch_language
from open_mode import settled

check = Check()

# Found by the walk described above: base ruleset (open_mode's unchecked
# expansion boxes), Leader draft off (so this seed's server-assigned Leader
# for seat 0 -- Feyd Rautha Harkonnen -- is deterministic). Seed 0 until
# OQ-095's explicit Agent-turn end (2026-10-01).
SEED = 1
STEP_CAP = 200
# The same walk offers hand, discard pile and in-play cards together at its
# 57th decision on this seed (module docstring).
THREE_ZONE_SEED = 5

SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-trash-zones-")
)

# Every Hangul run, for the English-side check (mirrors turn_end.py / lang.py).
HANGUL = re.compile("[가-힣]")

# docs/rules/glossary-ko.md: hand 핸드, discard pile 버림 더미, In Play 플레이
# 영역 (all `[Main p. 20]`) -- the expected suffix wording, reconstructed
# independently of both clients (like combat_result.py) rather than read off
# either one's TERMS table, so this test does not depend on code this change
# adds (the old client has no `in_play` term at all).
ZONE_LABELS = {
    "hand": {"ko": "핸드", "en": "hand"},
    "discard_pile": {"ko": "버림 더미", "en": "discard pile"},
    "in_play": {"ko": "플레이 영역", "en": "in play"},
}
# The word over a run of rows: the same words, the English one capitalised.
ZONE_HEADINGS = {
    zone: {"ko": words["ko"], "en": words["en"][0].upper() + words["en"][1:]}
    for zone, words in ZONE_LABELS.items()
}
# The order the engine offers trash candidates in (card_trash.py,
# optional_trash.py, combat.py, board_effects.py, ...).
ZONE_ORDER = ("hand", "discard_pile", "in_play")

# Mirrors core.js's baseId(): strip a starter card's or a shared pile's
# per-instance suffix down to its catalog key.
STARTER_ID = re.compile(r"^player:\d+:starter:(.+):\d+$")
SHARED_ID = re.compile(r"^(?:imperium|reserve|intrigue|tleilaxu|skill):(.+):\d+$")
CONTRACT_ID = re.compile(r"^contract:(.+)$")


def base_id(card_id: str) -> str:
    for pattern in (STARTER_ID, SHARED_ID, CONTRACT_ID):
        match = pattern.match(card_id)
        if match:
            return match.group(1)
    return card_id


def zone_of(card_id: str, view: dict, seat: int) -> str | None:
    """The viewing seat's own pile holding a card instance: its hand in the
    private block, its discard pile and in-play list in its public player
    block (mirrors render.js's ownCardZone -- but reimplemented from
    `state.view` here, not by calling that new function, so this detection
    step also works against the old client)."""

    if card_id in view["private"]["hand"]:
        return "hand"
    own = view["players"][seat]
    if card_id in own["discard_pile"]:
        return "discard_pile"
    if card_id in own["in_play"]:
        return "in_play"
    return None


def find_zone_duplicate(page) -> list[dict[str, Any]] | None:
    """Within the *current* decision's action list, the first group of rows
    sharing an action_id and a card (same base_id) but sitting in different
    piles of the viewing seat -- the same grouping zoneSuffixes (render.js)
    uses, reimplemented in Python from plain state so it detects the
    decision on both clients; only the rendered *row text* checked below
    depends on the new code."""

    if not page.evaluate("Boolean(state.actions)"):
        return None
    actions = page.evaluate("state.actions.actions")
    view = page.evaluate("state.view")
    seat = page.evaluate("state.viewSeat")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for action in actions:
        card_id = action["arguments"].get("card_id")
        if not isinstance(card_id, str):
            continue
        zone = zone_of(card_id, view, seat)
        if zone is None:
            continue
        key = (action["action_id"], base_id(card_id))
        groups.setdefault(key, []).append(
            {"action": action, "zone": zone, "cardId": card_id}
        )
    for entries in groups.values():
        if len({e["zone"] for e in entries}) >= 2:
            return entries
    return None


def create_game_no_leader_draft(
    page, base: str, humans: tuple[int, ...], seed: int
) -> str:
    """open_mode.create_game's own steps, plus unchecking the Leader-draft
    box (its own checkbox, not one of RULE_OPTIONS -- default checked)."""

    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat in humans else "heuristic",
        )
    set_rule_options(page)
    page.set_checked("#opt-leader-draft", False)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    return page.evaluate("state.gameId")


def find_three_zones(page) -> list[dict[str, Any]] | None:
    """The current decision's card rows when they sit in all three of the
    viewing seat's own piles at once (hand, discard pile, in play)."""

    if not page.evaluate("Boolean(state.actions)"):
        return None
    actions = page.evaluate("state.actions.actions")
    view = page.evaluate("state.view")
    seat = page.evaluate("state.viewSeat")
    entries = []
    for action in actions:
        card_id = action["arguments"].get("card_id")
        zone = zone_of(card_id, view, seat) if isinstance(card_id, str) else None
        if zone is not None:
            entries.append({"action": action, "zone": zone, "cardId": card_id})
    return entries if {e["zone"] for e in entries} == set(ZONE_ORDER) else None


def drive_to_zone_duplicate(
    page, step_cap: int = STEP_CAP, find=find_zone_duplicate
) -> list[dict] | None:
    """Confirm every hold at once; otherwise take the seat's own first legal
    action -- the same deterministic policy the raw-HTTP search replayed --
    until `find` (default: a decision offering a same-named card from two of
    the seat's own piles at once) returns rows, or the step budget runs out."""

    for _ in range(step_cap):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            return None
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        entries = find(page)
        if entries:
            return entries
        page.evaluate("applyAction(state.actions.actions[0].index)")
    return None


def row_button(page, index: int):
    return page.locator(
        f"#actions .action-item[data-index='{index}'] > button:not(.action-info)"
    )


def check_rows(page, what: str, lang: str, entries: list[dict]) -> None:
    print(f"  {what}: {len(entries)} rows share an action and a card across piles")
    check.ok(len(entries) >= 2, f"{what}: at least two rows are offered", entries)

    action_id = entries[0]["action"]["action_id"]
    check.ok(
        all(e["action"]["action_id"] == action_id for e in entries),
        f"{what}: every row shares the one action_id ({action_id})",
        entries,
    )
    zones = {e["zone"] for e in entries}
    check.ok(len(zones) >= 2, f"{what}: the rows sit in different piles", sorted(zones))

    bare_texts = []
    for entry in entries:
        index = entry["action"]["index"]
        zone = entry["zone"]
        button = row_button(page, index)
        check.ok(button.count() == 1, f"{what}: {zone}'s row is on screen", index)
        if button.count() != 1:
            continue
        text = button.inner_text()
        suffix = f" ({ZONE_LABELS[zone][lang]})"
        check.ok(
            text.endswith(suffix),
            f"{what}: {zone}'s row ends with its pile ({suffix!r})",
            text,
        )
        bare_texts.append(text[: -len(suffix)] if text.endswith(suffix) else text)
        entry_name = page.evaluate("(id) => lookup(baseId(id)).name", entry["cardId"])
        check.ok(
            entry_name in text,
            f"{what}: {zone}'s row still names the card ({entry_name})",
            text,
        )

    check.ok(
        len({bt for bt in bare_texts}) == 1,
        f"{what}: without the pile suffix the rows would read identically "
        "(the bug ITEM 8c reports)",
        bare_texts,
    )
    shown_full = [row_button(page, e["action"]["index"]).inner_text() for e in entries]
    check.ok(
        len(set(shown_full)) == len(shown_full),
        f"{what}: the rows differ from each other on screen",
        shown_full,
    )


# What #actions holds, in order: the zone headings and dividers this change
# adds, and the rows (every row is an .action-item with its action's index).
LAYOUT_JS = """() => [...document.getElementById('actions').children].map((child) => ({
    kind: child.classList.contains('zone-heading') ? 'heading'
        : child.classList.contains('zone-divider') ? 'divider'
        : child.classList.contains('action-item') ? 'row' : 'other',
    index: child.dataset.index === undefined ? null : Number(child.dataset.index),
    text: child.innerText.trim(),
    ariaHidden: child.getAttribute('aria-hidden'),
    role: child.getAttribute('role'),
    focusable: child.matches('button, a, input, select, [tabindex]')
        || Boolean(child.querySelector('button, a, input, select, [tabindex]')),
}))"""

# appendActionItems on a detached box, for the subsets of a real decision's
# rows (given in the order to render them in).
SUBSET_JS = """(indices) => {
    const byIndex = new Map(state.actions.actions.map((a) => [a.index, a]));
    const box = document.createElement('div');
    appendActionItems(box, indices.map((i) => byIndex.get(i)));
    return [...box.children].map((child) => ({
        kind: child.classList.contains('zone-heading') ? 'heading'
            : child.classList.contains('zone-divider') ? 'divider' : 'row',
        index: child.dataset.index === undefined ? null : Number(child.dataset.index),
        text: child.textContent.trim(),
    }));
}"""


def decision_state(page) -> tuple[list[dict], dict, int]:
    return (
        page.evaluate("state.actions.actions"),
        page.evaluate("state.view"),
        page.evaluate("state.viewSeat"),
    )


def row_zone(action: dict, view: dict, seat: int) -> str | None:
    card_id = action["arguments"].get("card_id")
    return zone_of(card_id, view, seat) if isinstance(card_id, str) else None


def expected_tokens(zones: list[str | None], lang: str) -> list[tuple]:
    """The headings, dividers and rows a list of rows with these piles (None:
    a row naming no card of the seat's own piles) must render as: one heading
    over each run of rows in one pile, a divider before a run of other rows
    that follows card rows -- and nothing at all when the card rows share one
    pile. Rebuilt here from the piles, not read off the rendered page."""

    if len({zone for zone in zones if zone}) < 2:
        return [("row",) for _ in zones]
    out: list[tuple] = []
    for position, (zone, run) in enumerate(itertools.groupby(zones)):
        length = len(list(run))
        if zone:
            out.append(("heading", f"{ZONE_HEADINGS[zone][lang]} · {length}"))
        elif position:
            out.append(("divider",))
        out.extend([("row",)] * length)
    return out


def check_zone_layout(
    page, what: str, lang: str, expected_zones: list[str]
) -> list[dict]:
    """The zone headings of the decision on screen: in engine order, each
    with the number of rows under it, every row under the heading of the pile
    its card is really in, a divider before the rows that follow the cards,
    and nothing in the headings a keyboard or screen reader would trip on."""

    actions, view, seat = decision_state(page)
    by_index = {action["index"]: action for action in actions}
    layout = page.evaluate(LAYOUT_JS)
    rows = [c for c in layout if c["kind"] == "row" and c["index"] in by_index]
    check.ok(
        [c["index"] for c in rows]
        == [a["index"] for a in actions if a["index"] in {c["index"] for c in rows}],
        f"{what}: the rows keep the engine's order",
    )
    zones = [row_zone(by_index[c["index"]], view, seat) for c in rows]
    totals = {zone: zones.count(zone) for zone in ZONE_ORDER}
    present = [zone for zone in ZONE_ORDER if totals[zone]]
    check.ok(
        present == expected_zones,
        f"{what}: the card rows sit in {expected_zones} (view's own lists)",
        present,
    )

    headings = [c for c in layout if c["kind"] == "heading"]
    check.ok(
        [h["text"] for h in headings]
        == [f"{ZONE_HEADINGS[z][lang]} · {totals[z]}" for z in present],
        f"{what}: headings in hand -> discard pile -> in play order with the "
        "number of rows in each pile",
        [h["text"] for h in headings],
    )

    section: str | None = None  # the pile of the heading the row is under
    under: dict[str, list[int]] = {}
    after_divider: list[int] = []
    divider_seen = False
    seen_heading = False
    next_heading = iter(present)
    for child in layout:
        if child["kind"] == "heading":
            section = next(next_heading, None)
            under[section] = []
            seen_heading = True
            divider_seen = False
        elif child["kind"] == "divider":
            divider_seen = True
            section = None
        elif child["kind"] == "row" and child["index"] in by_index:
            zone = row_zone(by_index[child["index"]], view, seat)
            if section is not None:
                under[section].append(child["index"])
                check.ok(
                    zone == section,
                    f"{what}: row {child['index']} under the {section} heading "
                    f"is a {section} card",
                    zone,
                )
            elif divider_seen:
                after_divider.append(child["index"])
            else:
                check.ok(
                    zone is None or seen_heading,
                    f"{what}: no card row sits above the first heading",
                    child,
                )
    for zone in present:
        check.ok(
            len(under.get(zone, [])) == totals[zone],
            f"{what}: {totals[zone]} {zone} rows sit under their heading",
            under.get(zone),
        )
        shown = int(
            next(h["text"] for h in headings
                 if h["text"].startswith(ZONE_HEADINGS[zone][lang] + " ·"))
            .rsplit(" ", 1)[1]
        )
        check.ok(
            shown == len(under.get(zone, [])),
            f"{what}: the {zone} heading counts the rows under it ({shown})",
        )
    # A row naming no pile card is first a decline, last the board effect; the
    # divider is only wanted where such a row follows card rows.
    expected = expected_tokens(zones, lang)
    expected_dividers = sum(1 for token in expected if token[0] == "divider")
    dividers = [c for c in layout if c["kind"] == "divider"]
    check.ok(
        len(dividers) == expected_dividers,
        f"{what}: {expected_dividers} divider(s) before the rows after the cards",
        len(dividers),
    )
    check.ok(
        all(d["ariaHidden"] == "true" and not d["focusable"] for d in dividers),
        f"{what}: dividers are hidden from screen readers and take no focus",
    )
    check.ok(
        all(not h["focusable"] and h["ariaHidden"] is None for h in headings),
        f"{what}: headings are plain text a screen reader reads, never a "
        "control (Tab skips them)",
    )
    actual = [
        (c["kind"], c["text"]) if c["kind"] == "heading" else (c["kind"],)
        for c in layout
        if c["kind"] in ("heading", "divider")
        or (c["kind"] == "row" and c["index"] in by_index)
    ]
    check.ok(actual == expected, f"{what}: the whole layout matches the piles", actual)
    return layout


def check_subsets(page, what: str, lang: str) -> None:
    """appendActionItems on subsets of the three-pile decision's rows: one
    pile gets nothing added, two or three piles get their headings, an
    interleaved order gets one heading per run."""

    actions, view, seat = decision_state(page)
    by_pile: dict[str | None, list[int]] = {}
    for action in actions:
        by_pile.setdefault(row_zone(action, view, seat), []).append(action["index"])
    others = by_pile.get(None, [])
    hand, discard, play = (by_pile[z] for z in ZONE_ORDER)
    cases = {
        "hand rows and the decline (one pile)": [*others[:1], *hand],
        "discard-pile rows alone (one pile)": discard,
        "no card rows at all": others,
        "hand and in play, a decline first and a row after": [
            *others[:1], *hand[:2], *play[:1], *others[-1:],
        ],
        "all three piles, nothing else": [*hand[:1], *discard[:2], *play[:1]],
        "interleaved: hand, discard pile, hand, in play": [
            hand[0], discard[0], hand[1], play[0],
        ],
    }
    for name, indices in cases.items():
        by_index = {a["index"]: a for a in actions}
        zones = [row_zone(by_index[i], view, seat) for i in indices]
        got = page.evaluate(SUBSET_JS, indices)
        tokens = [
            (c["kind"], c["text"]) if c["kind"] == "heading" else (c["kind"],)
            for c in got
        ]
        want = expected_tokens(zones, lang)
        check.ok(tokens == want, f"{what}: {name}", {"got": tokens, "want": want})
        check.ok(
            [c["index"] for c in got if c["kind"] == "row"] == indices,
            f"{what}: {name}: every row keeps its own action index, in order",
        )


def check_row_clicks(page, what: str, layout: list[dict]) -> None:
    """A click on a row of each pile sends that card's own action (the
    request body's index), trashes that card, and an undo brings the same
    decision back with its headings."""

    actions, view, seat = decision_state(page)
    by_index = {action["index"]: action for action in actions}
    before = [c["index"] for c in layout if c["kind"] == "row"]
    for zone in ZONE_ORDER:
        target = next(
            c["index"]
            for c in layout
            if c["kind"] == "row"
            and c["index"] in by_index
            and row_zone(by_index[c["index"]], view, seat) == zone
        )
        card_id = by_index[target]["arguments"]["card_id"]
        with page.expect_request(
            lambda r: r.method == "POST" and r.url.endswith("/actions")
        ) as sent:
            row_button(page, target).click()
        check.ok(
            sent.value.post_data_json["index"] == target
            and by_index[sent.value.post_data_json["index"]]["arguments"]["card_id"]
            == card_id,
            f"{what}: clicking the {zone} row sends that card's own action",
            sent.value.post_data_json,
        )
        assert settled(page, 20)
        now_view = page.evaluate("state.view")
        check.ok(
            zone_of(card_id, now_view, seat) is None,
            f"{what}: the {zone} card ({card_id}) is gone from the seat's piles",
        )
        page.click("#decision-info .undo-row button")
        assert settled(page, 20)
        again = page.evaluate("state.actions.actions")
        check.ok(
            [a["index"] for a in again] == [a["index"] for a in actions],
            f"{what}: undo restores the same decision after the {zone} click",
        )
        restored = [c["index"] for c in page.evaluate(LAYOUT_JS) if c["kind"] == "row"]
        check.ok(restored == before, f"{what}: ... and the same rows on screen")


def check_focus_hides_headings(page, what: str, layout: list[dict]) -> None:
    """focusActions moves the matching rows to the top, so the pile
    headings (which would no longer sit over their rows) step aside until
    the focus is cleared."""

    refs_js = (
        "(i) => JSON.parse(document.querySelector("
        "`#actions .action-item[data-index='${i}']`).dataset.refs)"
    )
    actions, view, seat = decision_state(page)
    by_index = {action["index"]: action for action in actions}
    target = next(
        c["index"]
        for c in layout
        if c["kind"] == "row"
        and c["index"] in by_index
        and row_zone(by_index[c["index"]], view, seat)
    )
    refs = page.evaluate(refs_js, target)
    if not refs:
        check.ok(False, f"{what}: a trash row names its card in data-refs", refs)
        return
    page.evaluate("(ref) => focusActions(ref, 'x')", refs[0])
    visible = page.evaluate(
        "document.querySelectorAll("
        "'#actions .zone-heading:not([hidden]), #actions .zone-divider:not([hidden])'"
        ").length"
    )
    check.ok(visible == 0, f"{what}: headings step aside while a card is focused")
    page.evaluate("clearActionFocus()")
    check.ok(
        page.evaluate(LAYOUT_JS) == layout,
        f"{what}: clearing the focus brings the same layout back",
    )


def check_geometry(page, what: str) -> None:
    """At 1366x768 the headings sit inside the action panel with no sideways
    overflow, and each heading's rule is drawn above its text."""

    box = page.evaluate(
        """() => {
            const list = document.getElementById('actions');
            const panel = list.getBoundingClientRect();
            const marks = [...list.querySelectorAll('.zone-heading')].map((h) => {
                const r = h.getBoundingClientRect();
                const style = getComputedStyle(h);
                return {left: r.left, right: r.right, height: r.height,
                        border: style.borderTopWidth, size: style.fontSize};
            });
            return {overflow: list.scrollWidth - list.clientWidth,
                    left: panel.left, right: panel.right, marks};
        }"""
    )
    check.ok(box["overflow"] <= 0, f"{what}: no sideways overflow", box["overflow"])
    check.ok(len(box["marks"]) == 3, f"{what}: three headings drawn", box["marks"])
    check.ok(
        all(m["left"] >= box["left"] - 1 and m["right"] <= box["right"] + 1
            and m["height"] > 8 for m in box["marks"]),
        f"{what}: every heading sits inside the panel",
        box,
    )


def check_one_pile_list(browser, base: str) -> None:
    """The full Agent-turn list offers hand cards only: no headings."""

    print("[4] a list whose card rows share one pile gets no headings")
    context, page, rec = open_context(browser, "trash-zone-one-pile")
    create_game_no_leader_draft(page, base, (0,), THREE_ZONE_SEED)
    assert settled(page, 20)
    page.click("#actions .action-list-toggle")
    assert settled(page, 20)
    actions, view, seat = decision_state(page)
    rows = [c for c in page.evaluate(LAYOUT_JS) if c["kind"] == "row"]
    zones = {
        row_zone(a, view, seat)
        for a in actions
        if a["index"] in {c["index"] for c in rows}
    }
    check.ok(len(rows) >= 2, "full Agent-turn list: several rows", len(rows))
    check.ok(
        zones - {None} == {"hand"},
        "full Agent-turn list: every card row is a hand card",
        zones,
    )
    check.ok(
        not page.locator("#actions .zone-heading, #actions .zone-divider").count(),
        "full Agent-turn list: no zone headings or dividers",
    )
    check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
    context.close()


def check_three_zones(browser, base: str) -> None:
    print("[3] hand, discard pile and in play together, at 1366x768")
    context, page, rec = open_context(browser, "trash-zone-three", LAPTOP_VIEWPORT)
    create_game_no_leader_draft(page, base, (0,), THREE_ZONE_SEED)
    entries = drive_to_zone_duplicate(page, find=find_three_zones)
    if entries is None:
        check.ok(
            False,
            f"seed {THREE_ZONE_SEED} (Leader draft off) reached a decision "
            f"with cards in all three piles within {STEP_CAP} steps (it did "
            "when this script was written)",
        )
        context.close()
        return
    SHOTS.mkdir(parents=True, exist_ok=True)
    layouts = {}
    for lang in ("ko", "en"):
        switch_language(page, lang)
        what = {"ko": "Korean", "en": "English"}[lang]
        layouts[lang] = check_zone_layout(page, what, lang, list(ZONE_ORDER))
        check_geometry(page, what)
        page.locator("#actions .zone-heading").first.scroll_into_view_if_needed()
        page.screenshot(path=str(SHOTS / f"trash_zones_{lang}.png"))
        print(f"  screenshot: {SHOTS / f'trash_zones_{lang}.png'}")
        page.evaluate(
            "document.getElementById('actions').scrollTop ="
            " document.getElementById('actions').scrollHeight"
        )
        page.screenshot(path=str(SHOTS / f"trash_zones_{lang}_end.png"))
        print(f"  screenshot: {SHOTS / f'trash_zones_{lang}_end.png'}")
        page.evaluate("document.getElementById('actions').scrollTop = 0")
        if lang == "en":
            texts = [c["text"] for c in layouts[lang] if c["kind"] == "heading"]
            check.ok(
                not any(HANGUL.search(t) for t in texts),
                "English: no Hangul in the headings",
                texts,
            )
        check_subsets(page, what, lang)
    # Last, so the screenshots above show the untouched decision: the click
    # and undo walk (the engine and request body do not depend on language).
    check_focus_hides_headings(page, "English", layouts["en"])
    check_row_clicks(page, "English", layouts["en"])
    check.ok(
        page.evaluate(LAYOUT_JS) == layouts["en"],
        "English: the layout is unchanged after the clicks and undos",
    )
    switch_language(page, "ko")
    check.ok(
        [c["text"] for c in page.evaluate(LAYOUT_JS) if c["kind"] == "heading"]
        == [h["text"] for h in layouts["ko"] if h["kind"] == "heading"],
        "Korean: the headings come back after the walk and the language switch",
    )
    failed = [r for r in rec.requests if r[3] >= 400]
    check.ok(not failed, "no failed requests (three piles)", failed[:5])
    check.ok(not rec.js_errors, "no JS exceptions (three piles)", rec.js_errors[:5])
    context.close()


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            print("[1] a real game reaches a trash decision with a same-named "
                  "card split across two of the seat's own piles")
            context, page, rec = open_context(browser, "trash-zone")
            create_game_no_leader_draft(page, base, (0,), SEED)
            entries = drive_to_zone_duplicate(page)
            if entries is None:
                check.ok(
                    False,
                    f"seed {SEED} (Leader draft off) reached a same-pile "
                    f"trash duplicate within {STEP_CAP} steps (it did when "
                    "this script was written)",
                )
            else:
                check_rows(page, "Korean", "ko", entries)
                check_zone_layout(page, "Korean", "ko", ["hand", "in_play"])

                print("[2] the same rows in English")
                switch_language(page, "en")
                entries_en = find_zone_duplicate(page)
                same_indices = entries_en is not None and {
                    e["action"]["index"] for e in entries_en
                } == {e["action"]["index"] for e in entries}
                check.ok(
                    same_indices,
                    "the same decision (same action indices) is still on "
                    "screen after switching language",
                    entries_en,
                )
                if entries_en:
                    check_rows(page, "English", "en", entries_en)
                    check_zone_layout(page, "English", "en", ["hand", "in_play"])
                    texts_en = [
                        row_button(page, e["action"]["index"]).inner_text()
                        for e in entries_en
                    ]
                    check.ok(
                        not any(HANGUL.search(t) for t in texts_en),
                        "English: no Hangul in the rows",
                        texts_en,
                    )

            failed = [r for r in rec.requests if r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()
            check_three_zones(browser, base)
            check_one_pile_list(browser, base)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    check.finish()


if __name__ == "__main__":
    main()
