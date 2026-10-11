"""E2E of a grafted Agent turn's rows grouped by card (plan stage 4).

User request 2026-10-11: "그냥 선택지에 카드 효과가 바로 보여지는게 낫지
않나? 접합했을 때도 왜 다른 접합한 카드 효과 보기를 또 눌러야 그렇게 되게
한거야." Since codec v143 the engine offers both grafted cards' Agent boxes
from the start (no "switch" step); the decision panel sets each box's rows
under a header naming its card ("<card> — 에이전트 칸"), box 0 (the placed
card) first, then box 1 (its graft partner), then the turn's other rows
under "그 밖의 선택" (docs/graft-boxes-plan.md 3 and 4.11; render.js
appendDecisionItems). The server says which box a row is (``box``) and
which boxes the turn has (``agent_boxes``).

A real game (``fixtures/graft_box_saves.py``: four human seats, Immortality
on, Leader draft off, a seeded random walk) is saved at a grafted turn whose
two boxes both offer rows, one of which starts a bundled selection that
holds the other box back (plan 4.3). The page loaded from it must show:

- in Korean and in English, a header per box with the card's name, each
  box's rows right under it in the engine's order, then the other rows
  under their own header; every legal row exactly once;
- a box row's button shows only what it does: the card's name is in a
  span that is not drawn, so a screen reader still hears it (the button's
  accessible name is "<card>: …"), and the log keeps naming the card;
- headings are no controls (Tab passes them by), and the buttons come in
  the order they are drawn;
- no sideways overflow at 1366x768 and 1600x950 (screenshots of both
  languages at 1600x950 in E2E_SHOTS_DIR);
- the row that starts the bundled selection, clicked once: the other box's
  rows are gone, its header stays with the note "다른 칸의 선택을 마친 뒤
  해결할 수 있음" / "Available after the other box's choice"; undo brings
  both boxes back;
- a box 1 row, clicked once: one request, that very row (no switch step
  exists), and box 1's effect is resolved.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from common import (
    LAPTOP_VIEWPORT,
    REPO,
    Check,
    ServerProcess,
    chrome,
    open_context,
)
from lang import switch as switch_language
from open_mode import settled

check = Check()
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-graft-boxes-")
)
WIDE = {"width": 1600, "height": 950}
HANGUL = re.compile("[가-힣]")
HEADING = {"ko": "{name} — 에이전트 칸", "en": "{name} — Agent box"}
OTHERS = {"ko": "그 밖의 선택", "en": "Other choices"}
LOCKED = {
    "ko": "다른 칸의 선택을 마친 뒤 해결할 수 있음",
    "en": "Available after the other box's choice",
}

# The panel's children in order: a box header (its box, or "others"), its
# note, a row (its index and box), a greyed row, or anything else.
LAYOUT_JS = """() => [...document.getElementById('actions').children].map((c) => {
  const button = c.querySelector(':scope > button');
  let visible = null;
  if (button) {
    const copy = button.cloneNode(true);
    copy.querySelectorAll('.box-row-title, .irreversible-badge, .shortfall-badge')
      .forEach((n) => n.remove());
    visible = copy.textContent.trim();
  }
  const hidden = c.querySelector('.box-row-title');
  const rect = hidden ? hidden.getBoundingClientRect() : null;
  return {
    kind: c.classList.contains('agent-box-others') ? 'others'
      : c.classList.contains('agent-box-heading') ? 'heading'
      : c.classList.contains('agent-box-note') ? 'note'
      : c.classList.contains('action-item') ? 'row'
      : c.classList.contains('unavailable-item') ? 'grey' : 'other',
    box: c.dataset.box === undefined ? null : Number(c.dataset.box),
    index: c.dataset.index === undefined ? null : Number(c.dataset.index),
    text: c.innerText.trim(),
    visible,
    full: button ? button.textContent.trim() : null,
    hidden: hidden ? hidden.textContent : null,
    hiddenDrawn: rect ? rect.width > 1 || rect.height > 1 : null,
    role: c.getAttribute('role'),
    level: c.getAttribute('aria-level'),
    focusable: c.matches('button, a, input, select, [tabindex]'),
  };
})"""

GEOMETRY_JS = """() => {
  const list = document.getElementById('actions');
  const panel = list.getBoundingClientRect();
  const marks = [...list.querySelectorAll('.agent-box-heading, .agent-box-note')]
    .map((h) => { const r = h.getBoundingClientRect();
      return {left: r.left, right: r.right, height: r.height}; });
  return {overflow: list.scrollWidth - list.clientWidth,
    page: document.documentElement.scrollWidth - window.innerWidth,
    left: panel.left, right: panel.right, marks};
}"""


def actions(page) -> list[dict]:
    return page.evaluate("state.actions.actions")


def expected_layout(page, lang: str) -> list[tuple]:
    """The panel the payload calls for, rebuilt from it (not the page):
    each box with a row under its header, then the other rows."""

    payload = page.evaluate("state.actions")
    rows = [a for a in payload["actions"] if a["action_id"] != "finish_agent_turn"]
    out: list[tuple] = []
    for entry in payload["agent_boxes"]:
        own = [a["index"] for a in rows if a.get("box") == entry["box"]]
        if not own and not entry["locked"]:
            continue
        name = entry["name_ko" if lang == "ko" else "name"]
        out.append(("heading", entry["box"], HEADING[lang].format(name=name)))
        if entry["locked"] and not own:
            out.append(("note", entry["box"], LOCKED[lang]))
        out.extend(("row", entry["box"], index) for index in own)
    others = [a["index"] for a in rows if "box" not in a]
    if others:
        out.append(("others", None, OTHERS[lang]))
        out.extend(("row", None, index) for index in others)
    return out


def shown_layout(page) -> list[tuple]:
    out: list[tuple] = []
    for child in page.evaluate(LAYOUT_JS):
        if child["kind"] in ("heading", "others", "note"):
            out.append((child["kind"], child["box"], child["text"]))
        elif child["kind"] == "row":
            out.append(("row", child["box"], child["index"]))
    return out


def check_layout(page, what: str, lang: str) -> None:
    want = expected_layout(page, lang)
    got = shown_layout(page)
    check.ok(got == want, f"{what}: headers and rows in box order", (got, want))
    layout = page.evaluate(LAYOUT_JS)
    headings = [c for c in layout if c["kind"] in ("heading", "others")]
    check.ok(
        headings
        and all(
            c["role"] == "heading" and c["level"] == "4" and not c["focusable"]
            for c in headings
        ),
        f"{what}: headers are headings for a screen reader, never a control",
        headings,
    )
    by_index = {a["index"]: a for a in actions(page)}
    for child in layout:
        if child["kind"] != "row" or child["box"] is None:
            continue
        action = by_index[child["index"]]
        title = action["detail_title_ko" if lang == "ko" else "detail_title"]
        check.ok(
            child["hidden"] == f"{title}: " and child["hiddenDrawn"] is False,
            f"{what}: row {child['index']} keeps its card only for screen "
            "readers",
            child,
        )
        check.ok(
            title not in (child["visible"] or "") and child["visible"],
            f"{what}: row {child['index']} shows what it does, not the card",
            child,
        )
        check.ok(
            (child["full"] or "").startswith(f"{title}: "),
            f"{what}: row {child['index']}'s accessible text leads with its card",
            child,
        )
    if lang == "en":
        text = page.evaluate("document.getElementById('actions').innerText")
        check.ok(
            not HANGUL.search(text), f"{what}: no Hangul in the panel", text[:300]
        )


def check_order(page, what: str) -> None:
    """Tab walks the rows in the order they are drawn."""

    drawn = [
        c["index"] for c in page.evaluate(LAYOUT_JS) if c["kind"] == "row"
    ]
    page.locator(f"#actions .action-item[data-index='{drawn[0]}'] > button").focus()
    walked = [drawn[0]]
    for _ in range(4 * len(drawn)):
        page.keyboard.press("Tab")
        index = page.evaluate(
            "(() => { const item = document.activeElement"
            " && document.activeElement.closest('#actions .action-item');"
            " return item ? Number(item.dataset.index) : null; })()"
        )
        if index is None:
            break
        if index != walked[-1]:
            walked.append(index)
    check.ok(walked == drawn, f"{what}: Tab reaches the rows in drawn order", walked)


def check_names(page, what: str, case: dict, lang: str) -> None:
    """The accessible name of box 1's row leads with its card."""

    entry = next(e for e in case["boxes"] if e["box"] == 1)
    name = entry["name_ko" if lang == "ko" else "name"]
    found = page.get_by_role("button", name=re.compile("^" + re.escape(name + ": ")))
    check.ok(
        found.count() >= 1,
        f"{what}: a screen reader hears '{name}: …' on box 1's row",
        found.count(),
    )


def check_geometry(page, what: str) -> None:
    box = page.evaluate(GEOMETRY_JS)
    check.ok(
        box["overflow"] <= 0 and box["page"] <= 0,
        f"{what}: no sideways overflow",
        box,
    )
    check.ok(
        box["marks"]
        and all(
            m["left"] >= box["left"] - 1 and m["right"] <= box["right"] + 1
            and m["height"] > 8
            for m in box["marks"]
        ),
        f"{what}: every header sits inside the panel",
        box,
    )


def check_focus_shows_card(page, what: str) -> None:
    """A row lifted out of its group by a table click shows its card."""

    ref = page.evaluate(
        """() => { for (const item of document.querySelectorAll(
              '#actions .action-item[data-box]')) {
            const refs = JSON.parse(item.dataset.refs || '[]');
            if (refs.length) return refs[0]; } return null; }"""
    )
    if ref is None:
        print("  .. no box row names a table object here; focus check skipped")
        return
    page.evaluate("(ref) => focusActions(ref, 'x')", ref)
    drawn = page.evaluate(
        """() => [...document.querySelectorAll(
            '#actions .action-item.action-match .box-row-title')].map(
            (n) => n.getBoundingClientRect().width > 1)"""
    )
    check.ok(
        drawn and all(drawn),
        f"{what}: a box row lifted by focus shows its card again",
        drawn,
    )
    page.evaluate("clearActionFocus()")


def open_save(browser, base: str, viewport: dict):
    context, page, rec = open_context(browser, "graft-boxes", viewport)
    page.goto(base + "/")
    page.locator("#save-list li:has-text('graft-boxes') button").first.click()
    page.wait_for_function(
        "state.view !== null && refreshFlight === null"
        " && Boolean(state.actions && state.actions.actions.length)"
    )
    assert settled(page, 20)
    return context, page, rec


def click_row(page, index: int) -> dict:
    with page.expect_request(
        lambda r: r.method == "POST" and r.url.endswith("/actions")
    ) as sent:
        page.locator(f"#actions .action-item[data-index='{index}'] > button").click()
    assert settled(page, 20)
    return sent.value.post_data_json


def check_lock(page, case: dict) -> None:
    print("[3] the row that starts a bundled selection holds the other box back")
    before = [a["index"] for a in actions(page)]
    row = next(a for a in actions(page) if a["index"] == case["lock_index"])
    body = click_row(page, case["lock_index"])
    check.ok(body["index"] == case["lock_index"], "the click sends that row", body)
    held = case["locked_box"]
    boxes = page.evaluate("state.actions.agent_boxes")
    check.ok(
        [e["box"] for e in boxes if e["locked"]] == [held],
        f"the server holds box {held} back",
        boxes,
    )
    check.ok(
        not any(a.get("box") == held for a in actions(page)),
        f"box {held} offers no row now",
    )
    for lang in ("ko", "en"):
        switch_language(page, lang)
        check_layout(page, f"held ({lang})", lang)
        notes = [
            c for c in page.evaluate(LAYOUT_JS)
            if c["kind"] == "note" and c["box"] == held
        ]
        check.ok(
            len(notes) == 1 and notes[0]["text"] == LOCKED[lang],
            f"held ({lang}): box {held}'s header says when it comes back",
            notes,
        )
        page.screenshot(path=str(SHOTS / f"graft_boxes_held_{lang}_1600.png"))
    switch_language(page, "ko")
    check.ok(row.get("undoable") is True, "the first pick can be taken back", row)
    page.click("#decision-info .undo-row button")
    assert settled(page, 20)
    check.ok(
        [a["index"] for a in actions(page)] == before,
        "undo brings both boxes' rows back",
    )
    check_layout(page, "after the undo (ko)", "ko")


def check_box_one_click(page, case: dict) -> None:
    print("[4] one click on a box 1 row resolves that card's box")
    target = next(a for a in actions(page) if a["index"] == case["box_one_index"])
    check.ok(target["arguments"].get("box") == 1, "the row is box 1's", target)
    check.ok(
        not any(a["action_id"] == "switch_graft_card" for a in actions(page)),
        "no switch step is offered",
    )
    log_before = page.evaluate("state.summary.log_count")
    body = click_row(page, case["box_one_index"])
    check.ok(body["index"] == case["box_one_index"], "the click sends that row", body)
    logged = page.evaluate(
        "(n) => state.log.entries.filter((e) => e.type === 'action').slice(-1)[0]",
        log_before,
    )
    check.ok(
        logged is not None
        and logged["action_id"] == target["action_id"]
        and logged["arguments"] == target["arguments"],
        "the log's last step is that box 1 row",
        logged,
    )
    check.ok(
        page.evaluate("state.summary.log_count") == log_before + 1,
        "exactly one step was taken",
        (log_before, page.evaluate("state.summary.log_count")),
    )
    now = actions(page)
    check.ok(
        not any(
            a["action_id"] == target["action_id"]
            and a["arguments"] == target["arguments"]
            for a in now
        ),
        "box 1's row is gone once resolved",
        [(a["action_id"], a["arguments"]) for a in now],
    )
    if now:
        check_layout(page, "after box 1 (ko)", "ko")


def main() -> None:
    saves = tempfile.mkdtemp(prefix="dune-graft-boxes-e2e-")
    found = json.loads(
        subprocess.run(
            [
                str(REPO / ".venv/bin/python"),
                str(Path(__file__).parent / "fixtures/graft_box_saves.py"),
                saves,
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    case = found["graft-boxes"]
    print(f"fixture: seed {case['seed']}, seat {case['seat']}: "
          f"{' + '.join(e['name'] for e in case['boxes'])}")
    SHOTS.mkdir(parents=True, exist_ok=True)
    process = ServerProcess(saves=saves).start()
    try:
        with chrome() as browser:
            print("[1] both cards' headers and rows from the start, 1600x950")
            context, page, rec = open_save(browser, process.base, WIDE)
            check.ok(
                page.evaluate("state.viewSeat") == case["seat"]
                and page.evaluate("state.summary.decision.kind") == "agent_effects",
                "the save rests on the grafted turn's effects",
            )
            served = page.evaluate("state.actions.agent_boxes")
            check.ok(
                [
                    {k: e[k] for k in ("box", "card_id", "name", "name_ko")}
                    for e in served
                ]
                == case["boxes"]
                and not any(e["locked"] for e in served),
                "the server names both boxes' cards",
                served,
            )
            for lang in ("ko", "en"):
                switch_language(page, lang)
                what = f"start ({lang}, 1600x950)"
                check_layout(page, what, lang)
                check_names(page, what, case, lang)
                check_geometry(page, what)
                shot = SHOTS / f"graft_boxes_{lang}_1600.png"
                page.screenshot(path=str(shot))
                print(f"  screenshot: {shot}")
            switch_language(page, "ko")
            check_order(page, "start (ko)")
            check_focus_shows_card(page, "start (ko)")
            check_lock(page, case)
            check_box_one_click(page, case)
            failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            context.close()

            print("[2] the same at 1366x768")
            context, page, rec = open_save(browser, process.base, LAPTOP_VIEWPORT)
            for lang in ("ko", "en"):
                switch_language(page, lang)
                what = f"start ({lang}, 1366x768)"
                check_layout(page, what, lang)
                check_geometry(page, what)
            page.screenshot(path=str(SHOTS / "graft_boxes_en_1366.png"))
            context.close()
    finally:
        process.stop()
    text = process.log_path.read_text()
    check.ok(
        "Traceback" not in text and "ERROR" not in text,
        f"no server errors (see {process.log_path})",
    )
    check.finish()


if __name__ == "__main__":
    main()
