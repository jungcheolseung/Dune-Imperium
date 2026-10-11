"""The revealed Arrakeen Scouts item as a card over the board (2026-10-11).

User request after a real game: during the Scouts step the item should stay
up over the board as a big card, like Dire Wolf Game Room's reveal page, with
a toggle to see the board. #scouts-stage takes the board's grid cell; its
frame is the board square and the card sits inside it: a header band with
the kind in spaced capitals and the item's name, the kind's painting, the
item's lines on a parchment, and a "보드 보기" button; folded, a tab on the
board's top edge names the item and brings it back; `a` toggles it too.

Real engine/server payloads (GameSessionManager, the step run by
advance_scouts_step, every seat given resources so nobody is skipped), drawn
by the page in Korean and English at 1366x768, 1600x950 and 1920x1080:
mission, event, auction, sale, the due secret picks (the seat's own reward
and a waiting seat), and the Spy placement a Scouts line leads to, which the
board answers (the card starts folded). Checked: the kind word, the name and
every line of the item (the Scouts panel's own rendering of the same lines,
and the count of catalog scouts_items), the app pictures when the catalog has
them and the CSS look without, the card inside the board square and nothing
of the decision panel, seats or market covered, Korean text at least 14px,
no sideways overflow, no Hangul in English; the button, the tab and the
shortcut (with the Hangul IME's key), Escape leaving it alone, a refresh
keeping the fold and the very same nodes, a new item opening it again, the
step's end removing it; the help's shortcut row; and a finished all-AI game's
review at a Scouts step. Nothing is submitted: a UI callback records any
index the page would send. Screenshots per kind (Korean, 1600x950) go to
E2E_SHOTS_DIR as stage_<kind>.png.
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
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-scouts-stage-")
)
HANGUL = re.compile(r"[가-힣]")
VIEWPORTS = (
    {"width": 1366, "height": 768},
    {"width": 1600, "height": 950},
    {"width": 1920, "height": 1080},
)

FIXTURES = """
import json
from dataclasses import replace
from dune_imperium.content.arrakeen_scouts import (
    AUCTIONS_BY_ID, EVENTS_BY_ID, MISSIONS_BY_ID, SALES_BY_ID)
from dune_imperium.core.player import Resources
from dune_imperium.rules.scouts import _item_tasks, advance_scouts_step
from dune_imperium.rules.scouts_effects import offer_secret_reward
from dune_imperium.rules.scouts_secrets import SECRET_ITEM
from dune_imperium.server.sessions import GameSessionManager

manager = GameSessionManager()
game_id = str(manager.create_game(("human",) * 4, game_seed=21,
                                  arrakeen_scouts=True)["game_id"])
session = manager._get(game_id)
turn = session.state
# Enough of everything that no seat is skipped for want of a cost.
turn = replace(turn, players=tuple(
    replace(p, resources=Resources(solari=6, spice=6, water=3))
    for p in turn.players))

def snapshot(state, seat):
    session.state = state
    return {"summary": manager.summary(game_id), "view": manager.view(game_id, seat),
            "actions": manager.legal_actions(game_id, seat)}

def step(item):
    # The real step: the item's tasks run until its first seat decides.
    entry = (EVENTS_BY_ID.get(item) or AUCTIONS_BY_ID.get(item)
             or MISSIONS_BY_ID.get(item) or SALES_BY_ID[item])
    round_number = getattr(entry, "rounds", (8,))[0]
    state = replace(turn, round_number=round_number, first_player=0,
                    decision_stack=(), scouts_opening=True, scouts_item=item,
                    scouts_revealed=((round_number, item),), scouts_tasks=())
    state = replace(state, scouts_tasks=_item_tasks(state, item))
    while not state.decision_stack:
        state = advance_scouts_step(state).state
    assert state.decision_stack[-1].decision.owner == 0, item
    return state

# Smoke and Mirrors' first line places a Spy: the post is the board's.
choice = step("smoke_and_mirrors")
place = next(a for a in session.engine.legal_actions(choice, 0)
             if dict(a.arguments).get("option") == 0)
spy = session.engine.apply(choice, place).state
while not spy.decision_stack:
    spy = advance_scouts_step(spy).state
assert str(spy.decision_stack[-1].kind) == "spy_placement", spy.decision_stack[-1].kind

secrets = offer_secret_reward(
    replace(turn, round_number=6, first_player=0, decision_stack=(),
            scouts_opening=True, scouts_item=SECRET_ITEM,
            scouts_revealed=((4, "covert_operation"), (5, "private_stock")),
            scouts_tasks=(),
            scouts_secret_picks=((4, "covert_operation", 0, 2),
                                 (4, "covert_operation", 1, 0))),
    0, "covert_operation", 2, source="round:6:scouts:secret:0").state

fixtures = {
    "mission": snapshot(step("security_detail"), 1),
    "mission_own": snapshot(step("security_detail"), 0),
    "event": snapshot(step("private_stock"), 1),
    "event_own": snapshot(step("private_stock"), 0),
    "auction": snapshot(step("highest_bidder_late"), 1),
    "sale": snapshot(step("imperium_connections"), 1),
    "secrets_own": snapshot(secrets, 0),
    "secrets": snapshot(secrets, 1),
    "choice": snapshot(choice, 0),
    "spy": snapshot(spy, 0),
    "turn": snapshot(turn, 0),
}
print(json.dumps({"fixtures": fixtures}))
"""

RENDER = """({fixture, seat, language}) => {
    if (TERM_LANGUAGE !== language) setLanguage(language, false);
    Object.assign(state, fixture, {viewSeat: seat, me: {seats: [0, 1, 2, 3]},
        gameId: fixture.summary.game_id, review: null, busy: false,
        pick: null, held: null, counts: {}, log: {entries: []}});
    window.sentIndexes = [];
    window.applyAction = (index) => window.sentIndexes.push(index);
    showScreen('game-screen');
    render();
}"""

# Everything the checks read off the stage at once.
STAGE_JS = """() => {
    const stage = el('scouts-stage');
    const card = stage.querySelector('.scouts-stage-card');
    const tab = stage.querySelector('.scouts-stage-tab');
    const box = (node) => {
        const r = node.getBoundingClientRect();
        return {left: r.left, top: r.top, right: r.right, bottom: r.bottom,
                width: r.width, height: r.height};
    };
    const visible = (node) => !node.closest('[hidden]')
        && getComputedStyle(node).display !== 'none' && box(node).width > 0;
    const lines = [...stage.querySelectorAll('.scouts-stage-lines .scouts-line')];
    const art = stage.querySelector('.scouts-stage-art img');
    const panel = stage.querySelector('.scouts-stage-panel');
    const id = stage.dataset.item;
    const row = document.querySelector(`#scouts-panel .scouts-row[data-item="${id}"]`);
    const sizes = [...stage.querySelectorAll(
        '.scouts-stage-lines .scouts-line, .scouts-stage-name, .scouts-stage-kind,'
        + ' .scouts-stage-hide, .scouts-stage-tab, .scouts-stage-note')]
        .filter(visible)
        .map((node) => parseFloat(getComputedStyle(node).fontSize));
    const linesBox = stage.querySelector('.scouts-stage-lines');
    return {
        hidden: stage.hidden,
        open: visible(card),
        tab: visible(tab),
        folded: stage.classList.contains('folded'),
        item: id || null,
        kind: stage.dataset.kind || null,
        kindWord: stage.querySelector('.scouts-stage-kind').textContent,
        kindTransform: getComputedStyle(stage.querySelector('.scouts-stage-kind'))
            .textTransform,
        kindSpacing: parseFloat(getComputedStyle(
            stage.querySelector('.scouts-stage-kind')).letterSpacing),
        kindFont: getComputedStyle(stage.querySelector('.scouts-stage-kind'))
            .fontFamily,
        name: stage.querySelector('.scouts-stage-name').textContent,
        tabText: tab.textContent,
        hideText: stage.querySelector('.scouts-stage-hide').textContent,
        lineHtml: lines.map((n) => n.innerHTML),
        lineText: lines.map((n) => n.textContent),
        // The Scouts panel's rendering of the same lines; an item the panel
        // lists without them (an earlier round's) is drawn the panel's way.
        panelLineHtml: row && row.querySelector('.scouts-line')
            ? [...row.querySelectorAll('.scouts-line')].map((n) => n.innerHTML)
            : (() => {
                const box = document.createElement('div');
                scoutsItemLines(scoutsItem(id), box, {currency: false});
                return [...box.querySelectorAll('.scouts-line')]
                    .map((n) => n.innerHTML);
            })(),
        currency: [...stage.querySelectorAll('.scouts-auction-currency')]
            .map((n) => n.textContent),
        note: (stage.querySelector('.scouts-stage-note') || {}).textContent || null,
        dividers: stage.querySelectorAll('.scouts-stage-divider').length,
        art: art ? art.getAttribute('src') : null,
        artLoaded: art ? art.complete && art.naturalWidth > 0 : null,
        hasArt: stage.classList.contains('has-art'),
        panelBackground: getComputedStyle(panel).backgroundImage,
        upperBackground: getComputedStyle(
            stage.querySelector('.scouts-stage-bar.upper')).backgroundImage,
        lowerBackground: getComputedStyle(
            stage.querySelector('.scouts-stage-bar.lower')).backgroundImage,
        cardBackground: getComputedStyle(card).backgroundImage,
        dividerBackground: stage.querySelector('.scouts-stage-divider')
            ? getComputedStyle(stage.querySelector('.scouts-stage-divider'))
                .backgroundImage : null,
        card: box(card),
        tabBox: box(tab),
        frame: box(stage.querySelector('.scouts-stage-frame')),
        board: box(el('board')),
        boardStage: el('board').querySelector('.board-stage')
            ? box(el('board').querySelector('.board-stage')) : null,
        side: box(el('side')),
        seats: box(el('seats')),
        market: box(el('market')),
        minFont: sizes.length ? Math.min(...sizes) : null,
        linesFit: linesBox.scrollWidth <= linesBox.clientWidth + 1,
        linesScroll: linesBox.scrollHeight > linesBox.clientHeight + 1,
        pageFits: document.documentElement.scrollWidth
            <= document.documentElement.clientWidth,
        text: stage.innerText,
        attributes: [...stage.querySelectorAll('[title], [aria-label], [alt]')]
            .map((n) => [n.getAttribute('title'), n.getAttribute('aria-label'),
                         n.getAttribute('alt')].join(' ')).join(' '),
        legalOnBoard: el('board').querySelectorAll('.legal, .force-stepper').length,
    };
}"""

# What lies at the centre of each decision panel row, the banner, the seats
# and the market: never the stage.
COVER_JS = """() => {
    const stage = el('scouts-stage');
    const targets = [el('decision-banner'), el('decision-info'), el('seats'),
        el('market'),
        ...document.querySelectorAll('#actions .action-item, #actions button')];
    const covered = [];
    for (const node of targets) {
        const r = node.getBoundingClientRect();
        if (!r.width || !r.height) continue;
        const x = Math.min(r.right - 2, Math.max(r.left + 2, r.left + r.width / 2));
        const y = Math.min(r.bottom - 2, Math.max(r.top + 2, r.top + r.height / 2));
        if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
        const hit = document.elementFromPoint(x, y);
        if (hit && stage.contains(hit)) covered.push(node.id || node.className);
    }
    return covered;
}"""

KIND_WORD = {
    "mission": {"ko": "임무", "en": "Mission"},
    "event": {"ko": "이벤트", "en": "Event"},
    "auction": {"ko": "경매", "en": "Auction"},
    "sale": {"ko": "판매", "en": "Sale"},
}
SECRETS_NAME = {"ko": "비밀 선택 공개", "en": "Secret picks revealed"}

# name: (seat, item id on the card, kind)
CASES = {
    "mission": (1, "security_detail", "mission"),
    "event": (1, "private_stock", "event"),
    "auction": (1, "highest_bidder_late", "auction"),
    "sale": (1, "imperium_connections", "sale"),
    "secrets_own": (0, "covert_operation", "event"),
    "secrets": (1, "secrets", "event"),
}
SHOT_CASES = ("mission", "event", "auction", "sale", "secrets_own")


def render(page, fixtures, name: str, language: str, seat: int | None = None) -> dict:
    fixture = fixtures[name]
    if seat is None:
        seat = CASES[name][0] if name in CASES else 0
    page.evaluate(RENDER, {"fixture": fixture, "seat": seat, "language": language})
    settle(page)
    return page.evaluate(STAGE_JS)


def settle(page) -> None:
    """The pictures decoded and the slide-in over (it moves the card)."""
    page.evaluate(
        "() => Promise.all([...document.querySelectorAll('#scouts-stage img')]"
        ".map((i) => i.decode().catch(() => null)))"
    )
    page.wait_for_function("!document.querySelector('#scouts-stage .entering')")


def inside(inner: dict, outer: dict, slack: float = 1.0) -> bool:
    return (
        inner["left"] >= outer["left"] - slack
        and inner["top"] >= outer["top"] - slack
        and inner["right"] <= outer["right"] + slack
        and inner["bottom"] <= outer["bottom"] + slack
    )


def apart(a: dict, b: dict) -> bool:
    return (
        a["right"] <= b["left"] + 1
        or b["right"] <= a["left"] + 1
        or a["bottom"] <= b["top"] + 1
        or b["bottom"] <= a["top"] + 1
    )


def check_case(page, fixtures, items, art, language, viewport, name) -> None:
    seat, item_id, kind = CASES[name]
    where = f"{language} {viewport['width']}x{viewport['height']} {name}"
    stage = render(page, fixtures, name, language)
    catalog_item = page.evaluate("(id) => scoutsItem(id)", item_id)
    check.ok(
        not stage["hidden"] and stage["open"] and not stage["tab"],
        f"{where}: the card is up over the board",
        (stage["hidden"], stage["open"], stage["tab"]),
    )
    check.ok(
        stage["item"] == item_id and stage["kind"] == kind,
        f"{where}: the card is the item the step resolves",
        (stage["item"], stage["kind"]),
    )
    check.ok(
        stage["kindWord"] == KIND_WORD[kind][language]
        and stage["kindTransform"] == "uppercase"
        and stage["kindSpacing"] > 2
        and "serif" in stage["kindFont"],
        f"{where}: the kind word in spaced serif capitals",
        (stage["kindWord"], stage["kindTransform"], stage["kindSpacing"]),
    )
    expected_name = (
        SECRETS_NAME[language] if item_id == "secrets" else catalog_item["name"]
    )
    check.ok(
        stage["name"] == expected_name,
        f"{where}: the item's name in the header",
        (stage["name"], expected_name),
    )
    if item_id == "secrets":
        rows = fixtures[name]["view"]["scouts_secret_pending"]
        pending = {(r, e) for r, e, _ in rows}
        check.ok(
            len(stage["lineText"]) == len(pending) and len(pending) > 0
            and stage["dividers"] == len(pending) - 1,
            f"{where}: one line per event whose picks are revealed",
            (stage["lineText"], pending),
        )
    else:
        want = len(items[item_id]["lines"])
        check.ok(
            len(stage["lineHtml"]) == want and want > 0
            and stage["lineHtml"] == stage["panelLineHtml"],
            f"{where}: every line of the item, as the Scouts panel draws them",
            (len(stage["lineHtml"]), want),
        )
        check.ok(
            stage["dividers"] == want - 1,
            f"{where}: a divider between each two lines",
            stage["dividers"],
        )
    if kind == "auction":
        currency = page.evaluate("(c) => termLabel(c)", items[item_id]["currency"])
        check.ok(
            len(stage["currency"]) == 1 and currency in stage["currency"][0],
            f"{where}: the auction's bid currency line",
            stage["currency"],
        )
    else:
        check.ok(not stage["currency"], f"{where}: no currency line", stage["currency"])
    if name == "secrets_own":
        check.ok(
            stage["note"] == SECRETS_NAME[language],
            f"{where}: the seat's own reward is marked as a revealed secret pick",
            stage["note"],
        )
    painting = art.get(kind)
    if painting:
        check.ok(
            stage["art"] == painting and stage["artLoaded"] and stage["hasArt"]
            and "scouts/back" in stage["panelBackground"]
            and "scouts/header_lower" in stage["lowerBackground"]
            and "scouts/header_upper" in stage["upperBackground"]
            and "scouts/starfield" in stage["cardBackground"]
            and (
                stage["dividers"] == 0
                or "scouts/or_backer" in stage["dividerBackground"]
            ),
            f"{where}: the app's painting, parchment, header bars, divider and stars",
            (stage["art"], stage["panelBackground"][:80]),
        )
    # Inside the board square, clear of every other column.
    reference = stage["boardStage"] or stage["board"]
    check.ok(
        inside(stage["frame"], stage["board"]) and inside(stage["card"], reference)
        and (stage["boardStage"] is None
             or abs(stage["frame"]["width"] - stage["boardStage"]["width"]) < 2),
        f"{where}: the card lies inside the board square",
        (stage["frame"], stage["boardStage"], stage["card"]),
    )
    check.ok(
        all(
            apart(stage["card"], stage[other])
            for other in ("side", "seats", "market")
        ),
        f"{where}: nothing of the decision panel, seats or market under the card",
    )
    covered = page.evaluate(COVER_JS)
    check.ok(not covered, f"{where}: every decision row is reachable", covered)
    check.ok(
        stage["minFont"] is not None and stage["minFont"] >= 14,
        f"{where}: text at least 14px",
        stage["minFont"],
    )
    check.ok(
        stage["linesFit"] and stage["pageFits"],
        f"{where}: no sideways overflow",
        (stage["linesFit"], stage["pageFits"]),
    )
    if language == "en":
        leaks = HANGUL.findall(stage["text"] + stage["tabText"] + stage["attributes"])
        check.ok(not leaks, f"{where}: no Hangul in English", leaks[:8])
    if language == "ko" and name in SHOT_CASES:
        if viewport["width"] == 1600:
            page.screenshot(path=str(SHOTS / f"stage_{name}.png"))
        elif viewport["width"] == 1366 and name in ("mission", "event"):
            page.screenshot(path=str(SHOTS / f"stage_{name}_1366.png"))


def toggles(page, fixtures, language: str) -> None:
    where = f"{language} toggle"
    stage = render(page, fixtures, "event", language)
    name = page.evaluate("scoutsItem('private_stock').name")
    hide = page.locator("#scouts-stage .scouts-stage-hide")
    check.ok(
        stage["hideText"] == {"ko": "보드 보기", "en": "Show board"}[language],
        f"{where}: the button says what it does",
        stage["hideText"],
    )
    hide.click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        not stage["open"]
        and stage["tab"]
        and stage["folded"]
        and name in stage["tabText"]
        and stage["tabText"].startswith(
            {"ko": "스카웃 카드", "en": "Scouts card"}[language]
        ),
        f"{where}: the button folds it to a tab naming the item",
        (stage["open"], stage["tab"], stage["tabText"]),
    )
    check.ok(
        page.evaluate("document.activeElement.classList.contains('scouts-stage-tab')"),
        f"{where}: focus moves to the tab",
    )
    check.ok(
        abs(stage["tabBox"]["top"] - stage["frame"]["top"]) < 2
        and stage["tabBox"]["height"] < 40,
        f"{where}: a small tab on the board's top edge",
        stage["tabBox"],
    )
    # Folded, the board takes clicks again: the hotspot under a space's
    # centre is the board's own.
    reach = page.evaluate(
        """() => {
            const spot = document.querySelector(
                '#board .hotspot[data-space="arrakeen"]');
            const r = spot.getBoundingClientRect();
            const hit = document.elementFromPoint(
                r.left + r.width / 2, r.top + r.height / 2);
            return Boolean(hit && spot.contains(hit));
        }"""
    )
    check.ok(reach, f"{where}: folded, the board's spaces are reachable")
    # A refresh (another seat's move) keeps the fold and the very nodes.
    page.evaluate(
        "window.markedLine = document.querySelector('#scouts-stage .scouts-line');"
        " render({foreign: true});"
    )
    stage = page.evaluate(STAGE_JS)
    check.ok(
        not stage["open"] and stage["tab"]
        and page.evaluate(
            "window.markedLine === document.querySelector('#scouts-stage .scouts-line')"
        ),
        f"{where}: a refresh keeps the fold and rebuilds nothing",
    )
    page.locator("#scouts-stage .scouts-stage-tab").click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        stage["open"] and not stage["tab"]
        and page.evaluate(
            "document.activeElement.classList.contains('scouts-stage-hide')"
        ),
        f"{where}: the tab brings it back",
    )
    # The shortcut, with the Hangul IME on (code KeyA, key ㅁ) and plain.
    page.evaluate(
        "document.dispatchEvent(new KeyboardEvent('keydown',"
        " {key: 'ㅁ', code: 'KeyA', bubbles: true}))"
    )
    folded = page.evaluate(STAGE_JS)
    page.keyboard.press("a")
    reopened = page.evaluate(STAGE_JS)
    check.ok(
        not folded["open"] and folded["tab"] and reopened["open"],
        f"{where}: `a` folds and unfolds it",
        (folded["open"], reopened["open"]),
    )
    page.keyboard.press("Escape")
    check.ok(page.evaluate(STAGE_JS)["open"], f"{where}: Escape leaves it alone")
    # Typing in a field is no shortcut.
    page.evaluate(
        """() => {
            const input = document.createElement('input');
            input.id = 'stage-probe';
            document.body.appendChild(input);
            input.focus();
        }"""
    )
    page.keyboard.press("a")
    check.ok(page.evaluate(STAGE_JS)["open"], f"{where}: `a` in a text field types")
    page.evaluate("document.getElementById('stage-probe').remove()")

    # Folded, a new item opens it again; the step's end takes it away.
    hide.click()
    stage = render(page, fixtures, "auction", language)
    check.ok(
        stage["open"] and stage["item"] == "highest_bidder_late",
        f"{where}: a new item opens it again",
    )
    stage = render(page, fixtures, "turn", language)
    check.ok(
        stage["hidden"] and page.evaluate("toggleScoutsStage()") is False,
        f"{where}: gone once the step ends; the shortcut does nothing",
    )

    # A decision the board answers starts folded: Smoke and Mirrors' choice
    # is up, its Spy placement (a post on the board) folds it.
    stage = render(page, fixtures, "choice", language, seat=0)
    check.ok(
        stage["open"] and stage["legalOnBoard"] == 0,
        f"{where}: a line choice opens it",
    )
    stage = render(page, fixtures, "spy", language, seat=0)
    post = page.evaluate(
        """() => {
            const spot = document.querySelector('#board .spy-post-hotspot.legal');
            if (!spot) return null;
            const r = spot.getBoundingClientRect();
            const hit = document.elementFromPoint(
                r.left + r.width / 2, r.top + r.height / 2);
            return Boolean(hit && spot.contains(hit));
        }"""
    )
    check.ok(
        not stage["open"] and stage["tab"] and stage["legalOnBoard"] > 0 and post,
        f"{where}: the Spy placement starts folded and its posts take the click",
        (stage["open"], stage["legalOnBoard"], post),
    )
    page.evaluate("render({foreign: true})")
    check.ok(
        not page.evaluate(STAGE_JS)["open"], f"{where}: and stays folded on a refresh"
    )
    page.locator("#scouts-stage .scouts-stage-tab").click()
    check.ok(page.evaluate(STAGE_JS)["open"], f"{where}: the tab still opens it there")
    # A board decision starting from a fresh item: folded from the start.
    render(page, fixtures, "turn", language)
    stage = render(page, fixtures, "spy", language, seat=0)
    check.ok(
        not stage["open"] and stage["tab"],
        f"{where}: folded when the item opens on it",
    )
    check.ok(page.evaluate("window.sentIndexes") == [], f"{where}: nothing was sent")


def no_pictures(page, fixtures, language: str) -> None:
    where = f"{language} no pictures"
    page.evaluate("state.catalog.saved_scouts_art = state.catalog.scouts_art;"
                  " state.catalog.scouts_art = {};")
    try:
        for name in ("event", "auction"):
            stage = render(page, fixtures, name, language)
            check.ok(
                stage["open"] and stage["art"] is None and not stage["hasArt"]
                and "url(" not in stage["panelBackground"]
                and "gradient" in stage["panelBackground"]
                and "gradient" in stage["lowerBackground"]
                and "url(" not in stage["cardBackground"]
                and stage["lineHtml"] == stage["panelLineHtml"],
                f"{where}: {name} in the CSS look, every line still there",
                (stage["panelBackground"][:60], stage["lowerBackground"][:60]),
            )
            check.ok(
                stage["card"]["width"] > 0 and stage["minFont"] >= 14
                and stage["linesFit"],
                f"{where}: {name} readable",
            )
            if language == "ko":
                page.screenshot(path=str(SHOTS / f"stage_{name}_css.png"))
        # Nor a board scan: the card covers the text board's cell.
        page.evaluate("state.catalog.saved_board = state.catalog.board_image;"
                      " state.catalog.board_image = null; render();")
        settle(page)
        stage = page.evaluate(STAGE_JS)
        check.ok(
            stage["open"]
            and abs(stage["frame"]["width"] - stage["board"]["width"]) < 2,
            f"{where}: without the board scan the card fills the board's cell",
            (stage["frame"], stage["board"]),
        )
    finally:
        page.evaluate(
            "state.catalog.scouts_art = state.catalog.saved_scouts_art;"
            " if ('saved_board' in state.catalog)"
            " state.catalog.board_image = state.catalog.saved_board; render();"
        )


def help_row(page, fixtures) -> None:
    render(page, fixtures, "event", "ko")
    page.evaluate("openHelp()")
    listed = page.evaluate(
        "() => [...document.querySelectorAll('#help-body kbd')]"
        ".map((k) => k.textContent)"
    )
    check.ok("a" in listed, "the help lists `a` in a Scouts game", listed)
    page.evaluate("closeHelp()")
    page.evaluate("state.summary.arrakeen_scouts = false; openHelp()")
    listed = page.evaluate(
        "() => [...document.querySelectorAll('#help-body kbd')]"
        ".map((k) => k.textContent)"
    )
    check.ok("a" not in listed, "and not in another game", listed)
    page.evaluate("closeHelp(); state.summary.arrakeen_scouts = true;")


def review(browser, base: str) -> None:
    """A finished all-AI Scouts game's review, at the first revealed item."""

    context, page, _ = open_context(browser, "scouts-stage-review", VIEWPORTS[1])
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    page.set_checked("#opt-scouts", True)
    page.fill("#opt-seed", "21")
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.review !== null && state.view !== null")
    cursor = page.evaluate(
        """() => {
            const review = state.review;
            const entry = review.meta.log.find((e) => (e.events || [])
                .some((ev) => ev.kind === 'scouts_item_revealed'));
            return entry ? review.liveIndex.indexOf(entry.index) + 1 : null;
        }"""
    )
    check.ok(bool(cursor), "review: the game revealed a Scouts item", cursor)
    if not cursor:
        context.close()
        return
    page.evaluate("async (c) => { stopPlayback(); await reviewGoto(c); }", cursor)
    settle(page)
    stage = page.evaluate(STAGE_JS)
    item = page.evaluate("state.view.scouts_item")
    check.ok(
        bool(item) and not stage["hidden"] and stage["open"] and stage["item"] == item,
        "review: the card shows the item at that step",
        (item, stage["item"], stage["open"]),
    )
    page.screenshot(path=str(SHOTS / "stage_review.png"))
    page.locator("#scouts-stage .scouts-stage-hide").click()
    check.ok(page.evaluate(STAGE_JS)["tab"], "review: it folds there too")
    page.screenshot(path=str(SHOTS / "stage_review_folded.png"))
    page.evaluate("async () => { await reviewGoto(0); }")
    check.ok(page.evaluate(STAGE_JS)["hidden"], "review: no card before the step")
    context.close()


def main() -> None:
    result = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", FIXTURES],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    fixtures = json.loads(result.stdout)["fixtures"]
    SHOTS.mkdir(parents=True, exist_ok=True)
    with server() as (base, _), chrome() as browser:
        context, page, recorder = open_context(browser, "scouts-stage", VIEWPORTS[0])
        page.goto(base)
        page.wait_for_function("state.catalog !== null")
        items = page.evaluate("state.catalog.scouts_items")
        art = page.evaluate("state.catalog.scouts_art")
        print(f"app pictures in the catalog: {sorted(art)}")
        for viewport in VIEWPORTS:
            page.set_viewport_size(viewport)
            for language in ("ko", "en"):
                for name in CASES:
                    check_case(page, fixtures, items, art, language, viewport, name)
        for language in ("ko", "en"):
            page.set_viewport_size(VIEWPORTS[0])
            toggles(page, fixtures, language)
            no_pictures(page, fixtures, language)
        help_row(page, fixtures)
        check.ok(not recorder.js_errors, "no JavaScript errors", recorder.js_errors)
        context.close()
        review(browser, base)
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
