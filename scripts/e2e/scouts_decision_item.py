"""Name the Arrakeen Scouts item in the decision panel (feedback item 8).

User request 2026-10-10: the item a Scouts decision belongs to (its kind,
its official name and its lines) was only in the Scouts panel, below the
subcommittees, so a seat had to look down to see what it was choosing for.
While the Scouts step resolves an item (the public view.scouts_item; the
seat's own scouts_lines.item_id first), #decision-info shows a header under
the prompt, above the turn-end or 확정 row, for the deciding seat and the
waiting ones. The lines are left out where the seat's own rows already are
those lines (its Scouts choice of that item, a secret pick).

Real engine/server payloads (GameSessionManager, the step run by
advance_scouts_step), drawn by the page in Korean and English at 1366x900.
Nothing is submitted: a UI callback records any index the page would send.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from common import REPO, Check, chrome, open_context, server

check = Check()
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-scouts-item-")
)
HANGUL = re.compile(r"[가-힣]")

FIXTURES = """
import json
from dataclasses import replace
from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS_BY_ID, EVENTS_BY_ID, MISSIONS_BY_ID)
from dune_imperium.rules.scouts import _item_tasks, advance_scouts_step
from dune_imperium.rules.scouts_effects import offer_secret_reward
from dune_imperium.rules.scouts_secrets import SECRET_ITEM
from dune_imperium.server.catalog import build_catalog
from dune_imperium.server.sessions import GameSessionManager

manager = GameSessionManager()
game_id = str(manager.create_game(("human",) * 4, game_seed=21,
                                  arrakeen_scouts=True)["game_id"])
session = manager._get(game_id)
turn = session.state
items = build_catalog()["scouts_items"]
lines = {key: len(item["lines"]) for key, item in items.items()}

def snapshot(state, seat):
    session.state = state
    return {"summary": manager.summary(game_id), "view": manager.view(game_id, seat),
            "actions": manager.legal_actions(game_id, seat)}

def step(item):
    # The real step: the item's tasks run until its first seat decides.
    entry = EVENTS_BY_ID.get(item) or AUCTIONS_BY_ID.get(item) or MISSIONS_BY_ID[item]
    round_number = entry.rounds[0]
    state = replace(turn, round_number=round_number, first_player=0,
                    decision_stack=(), scouts_opening=True, scouts_item=item,
                    scouts_revealed=((round_number, item),), scouts_tasks=())
    state = replace(state, scouts_tasks=_item_tasks(state, item))
    while not state.decision_stack:
        state = advance_scouts_step(state).state
    assert state.decision_stack[-1].decision.owner == 0, item
    return state

secrets = offer_secret_reward(
    replace(turn, round_number=6, first_player=0, decision_stack=(),
            scouts_opening=True, scouts_item=SECRET_ITEM,
            scouts_revealed=((4, "covert_operation"), (5, "private_stock")),
            scouts_tasks=()),
    0, "covert_operation", 2, source="round:6:scouts:secret:0").state

fixtures = {
    "event_own": snapshot(step("private_stock"), 0),
    "event_waiting": snapshot(step("private_stock"), 1),
    "auction_bid": snapshot(step("highest_bidder_late"), 0),
    "secret_pick": snapshot(step("covert_operation"), 0),
    "secret_pick_waiting": snapshot(step("covert_operation"), 1),
    "mission_join": snapshot(step("security_detail"), 0),
    "secrets_own": snapshot(secrets, 0),
    "secrets_waiting": snapshot(secrets, 1),
    "agent_turn": snapshot(turn, 0),
    "agent_turn_waiting": snapshot(turn, 1),
}
print(json.dumps({"fixtures": fixtures, "lines": lines}))
"""

RENDER = """({fixture, seat, language}) => {
    setLanguage(language, false);
    Object.assign(state, fixture, {viewSeat: seat, me: {seats: [0, 1, 2, 3]},
        gameId: fixture.summary.game_id, review: null, busy: false,
        pick: null, held: null, counts: {}, log: {entries: []}});
    window.sentIndexes = [];
    window.applyAction = (index) => window.sentIndexes.push(index);
    showScreen('game-screen');
    render();
}"""

# Where the header sits in #decision-info, and what it says.
LAYOUT_JS = """() => {
    const info = el('decision-info');
    const header = info.querySelector('.scouts-decision-item');
    const below = info.querySelector(':scope > .held-hint, :scope > .confirm-row');
    const prompt = info.querySelector(':scope > .prompt');
    const actions = el('actions');
    const follows = (a, b) => Boolean(a && b
        && (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING));
    return {
        count: info.querySelectorAll('.scouts-decision-item').length,
        item: header ? header.dataset.item : null,
        title: header ? header.querySelector('.scouts-decision-title').innerText : null,
        lines: header ? header.querySelectorAll('.scouts-line').length : 0,
        currencyInInfo: info.querySelectorAll('.scouts-auction-currency').length,
        currencyInActions: actions.querySelectorAll('.scouts-auction-currency').length,
        afterPrompt: !header || follows(prompt, header),
        beforeRow: !header || !below || (follows(header, below)
            && header.getBoundingClientRect().bottom
                <= below.getBoundingClientRect().top + 1),
        row: below ? below.className : null,
        parent: header ? header.parentElement.id : null,
        info: info.innerText,
        fitsActions: actions.scrollWidth <= actions.clientWidth + 1,
        fitsInfo: info.scrollWidth <= info.clientWidth + 1,
    };
}"""

KIND = {
    "event": {"ko": "이벤트", "en": "Event"},
    "auction": {"ko": "경매", "en": "Auction"},
    "mission": {"ko": "임무", "en": "Mission"},
}
# The KO-app official names (display/scouts.py SCOUTS_ITEM_NAMES_KO) and EN.
NAME = {
    "private_stock": {"ko": "개인 비축품", "en": "Private Stock"},
    "highest_bidder_late": {"ko": "최고 입찰자에게", "en": "To The Highest Bidder"},
    "covert_operation": {"ko": "작전 변경", "en": "Covert Operation"},
    "security_detail": {"ko": "경호 요원", "en": "Security Detail"},
}
HEADING = {"ko": "아라킨 스카웃", "en": "Arrakeen Scouts"}
SECRETS = {"ko": "비밀 선택 공개", "en": "Secret picks revealed"}

# name: (seat, item id shown, kind, whether the header lists the lines)
CASES = {
    "event_own": (0, "private_stock", "event", False),
    "event_waiting": (1, "private_stock", "event", True),
    "auction_bid": (0, "highest_bidder_late", "auction", True),
    "secret_pick": (0, "covert_operation", "event", False),
    "secret_pick_waiting": (1, "covert_operation", "event", True),
    "mission_join": (0, "security_detail", "mission", True),
    "secrets_own": (0, "covert_operation", "secrets", False),
    "secrets_waiting": (1, "secrets", "secrets", False),
    "agent_turn": (0, None, None, False),
    "agent_turn_waiting": (1, None, None, False),
}
SHOT_CASES = ("event_own", "event_waiting", "auction_bid", "secrets_own")


def expected_title(language: str, item: str, kind: str) -> str:
    if kind == "secrets":
        if item == "secrets":
            return f"{HEADING[language]} · {SECRETS[language]}"
        return f"{HEADING[language]} · {SECRETS[language]} · {NAME[item][language]}"
    return f"{HEADING[language]} · {KIND[kind][language]} · {NAME[item][language]}"


def check_case(page, language: str, name: str, fixture: dict, lines: dict) -> None:
    seat, item, kind, listed = CASES[name]
    where = f"{language} {name}"
    page.evaluate(RENDER, {"fixture": fixture, "seat": seat, "language": language})
    layout = page.evaluate(LAYOUT_JS)
    if item is None:
        check.ok(
            layout["count"] == 0,
            f"{where}: an ordinary turn of a Scouts game has no item header",
            layout["info"],
        )
        return
    title = expected_title(language, item, kind)
    check.ok(
        layout["count"] == 1
        and layout["parent"] == "decision-info"
        and layout["item"] == item
        and layout["title"] == title,
        f"{where}: the decision panel names the item",
        (layout["item"], layout["title"], title),
    )
    want = lines[item] if listed else 0
    if listed:
        label = f"{where}: the header lists the item's lines"
    elif item == "secrets":
        label = f"{where}: no single item to list, so only the title"
    else:
        label = f"{where}: the seat's own rows are the lines, so only the name"
    check.ok(
        layout["lines"] == want and (not listed or want > 0),
        label,
        (layout["lines"], want),
    )
    check.ok(
        layout["afterPrompt"] and layout["beforeRow"],
        f"{where}: under the prompt, above the turn-end / 확정 row",
        (layout["afterPrompt"], layout["beforeRow"], layout["row"]),
    )
    bidding = kind == "auction" and seat == 0
    check.ok(
        layout["currencyInInfo"] == 0
        and layout["currencyInActions"] == (1 if bidding else 0),
        f"{where}: the bid resource stays in #actions only",
        (layout["currencyInInfo"], layout["currencyInActions"]),
    )
    check.ok(
        layout["fitsActions"] and layout["fitsInfo"],
        f"{where}: the decision panel does not overflow sideways",
    )
    if language == "en":
        check.ok(
            not HANGUL.search(layout["info"]),
            f"{where}: no Hangul in the English decision panel",
            HANGUL.findall(layout["info"])[:10],
        )
    if name == "event_own":
        # Draw 1 card is irreversible: a click holds it for "확정 ▶", and
        # the header stays above the hint and that row.
        held = next(
            a["index"] for a in fixture["actions"]["actions"] if a["sent_by_turn_end"]
        )
        page.locator(f'#actions .action-item[data-index="{held}"]').click()
        layout = page.evaluate(LAYOUT_JS)
        check.ok(
            page.evaluate("Boolean(heldChoice())")
            and page.evaluate("window.sentIndexes") == []
            and layout["count"] == 1
            and layout["beforeRow"]
            and "held-hint" in (layout["row"] or ""),
            f"{where}: a held choice keeps the header above its hint and 확정 row",
            (layout["row"], layout["beforeRow"]),
        )
    if name in SHOT_CASES:
        page.locator("#decision-banner").screenshot(
            path=str(SHOTS / f"decision_item_{language}_{name}.png")
        )


def main() -> None:
    result = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", FIXTURES],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    loaded = json.loads(result.stdout)
    fixtures, lines = loaded["fixtures"], loaded["lines"]
    SHOTS.mkdir(parents=True, exist_ok=True)
    with server() as (base, _), chrome() as browser:
        context, page, recorder = open_context(browser, "scouts-decision-item")
        page.goto(base)
        page.wait_for_function("state.catalog !== null")
        page.set_viewport_size({"width": 1366, "height": 900})
        for language in ("ko", "en"):
            for name in CASES:
                check_case(page, language, name, fixtures[name], lines)
        check.ok(not recorder.js_errors, "no JavaScript errors", recorder.js_errors)
        context.close()
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
