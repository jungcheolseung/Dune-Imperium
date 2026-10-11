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
keeping the fold and the very same nodes, a new item opening it again, a
round without items having no card; the help's shortcut row; and a finished
all-AI game's review at a Scouts step.

Second request the same day: every revealed item comes up, not only those
with a choice, and the card stays at hand all round. All-AI games replayed
step by step (their rounds as a table sees them). Seed 21: round 4's choice
stays up after the step and through the turns, its tab reopens it, the
viewer's own Agent turn folds it once (reopened, it stays); round 5's
auction is on the card while the calls are open, and another seat's call
leaves it there; Unlikely Allies, revealed after the auction closed and
resolved with no Scouts decision, opens it by itself after the step as page
2 of 2 -- the counter, previous / next disabled at the ends, the arrows with
focus inside the card (not outside, not with Alt), the browsed page kept on
a refresh, the tab naming the page and how many more; a browser arriving
after the step opens the first unseen page and marks next "new" (mark and
title) without an update moving the card; round 6 has no card before its
reveal and Market Opening, also choice-less, opens it again. Seed 4's round
2 (Planetary Exploration with no decision, then Send for Aid): the card
stays on the item being decided, previous marked new, through another
seat's decision; the unseen item opens by itself once the step is over,
and not if the player paged to it meanwhile. The review pages a round of
two reveals and opens again at the next round's reveal. Korean and English
at 1366x768 and 1600x950, the pager inside the header, the kind word not
cut and the name clear.

Nothing is submitted: a UI callback records any index the page would send.
Screenshots per kind (Korean, 1600x950) go to E2E_SHOTS_DIR as
stage_<kind>.png, with stage_two_items.png, stage_choiceless_event.png,
stage_tab_agent_turn.png, stage_step_new.png and stage_next_new.png.
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
from dune_imperium.core.decisions import PlayerDecision
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

def snapshot(state, seat, game=None):
    game = game or game_id
    manager._get(game).state = state
    return {"summary": manager.summary(game), "view": manager.view(game, seat),
            "actions": manager.legal_actions(game, seat)}

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

# All-AI games replayed step by step: their rounds as a table sees them.
# Seed 21: round 4 resolves Bene Gesserit Treachery with choices; round 5
# reveals the Critical Moment auction (calls) and only after it closes
# Unlikely Allies, which resolves with no Scouts decision; round 6 reveals
# only Market Opening, also with none. Seed 4: round 2 reveals Planetary
# Exploration, resolved with no decision, and then Send for Aid, which every
# seat decides on -- an unseen page behind the step's item.
def replayed(seed):
    ai = manager._get(str(manager.create_game(
        ("heuristic",) * 4, game_seed=seed, arrakeen_scouts=True)["game_id"]))
    states = [ai.engine.reset(ai.config, ai.game_seed)]
    for recorded in ai.steps:
        states.append(ai.engine.apply(states[-1], recorded).state)
    return states

def this_round(state):
    return [i for r, i in state.scouts_revealed if r == state.round_number]

def owner(state):
    decision = state.decision_stack[-1].decision if state.decision_stack else None
    return decision.owner if isinstance(decision, PlayerDecision) else None

def scouts_choices(replay, round_number, item):
    # The step's states with a seat deciding on the item.
    return [s for s in replay if s.round_number == round_number
            and s.scouts_item == item and owner(s) is not None]

def turns(replay, round_number):
    # The round's Agent turns, after its Scouts step.
    return [s for s in replay if s.round_number == round_number
            and not s.scouts_opening and s.decision_stack
            and str(s.decision_stack[-1].kind) == "turn"]

def played(state, seat=None, game=None):
    # The seat whose decision it is, or the one given (then usually waiting).
    seat = owner(state) if seat is None else seat
    return dict(snapshot(state, seat, game), seat=seat)

def waiting(state):
    return played(state, (owner(state) + 1) % 4)

g21 = replayed(21)
assert this_round(turns(g21, 4)[0]) == ["bene_gesserit_treachery"]
assert scouts_choices(g21, 4, "bene_gesserit_treachery")
assert this_round(turns(g21, 5)[0]) == ["critical_moment_mid", "unlikely_allies"]
calls = scouts_choices(g21, 5, "critical_moment_mid")
assert calls and not scouts_choices(g21, 5, "unlikely_allies")
assert all(this_round(s) == ["critical_moment_mid"] for s in calls)
assert this_round(turns(g21, 6)[0]) == ["market_opening"]
assert not scouts_choices(g21, 6, "market_opening")
r6_start = next(s for s in g21 if s.round_number == 6 and not this_round(s))
# Another seat's call after the viewer's own: an update during the auction.
call_later = next(s for s in calls if owner(s) != owner(calls[0]))

g4 = replayed(4)
# A table of seed 4 to show them (its own game id and seed).
table4 = str(manager.create_game(("human",) * 4, game_seed=4,
                                 arrakeen_scouts=True)["game_id"])
aid = scouts_choices(g4, 2, "send_for_aid")
assert aid and not scouts_choices(g4, 2, "planetary_exploration")
assert this_round(aid[0]) == ["planetary_exploration", "send_for_aid"]
aid_later = next(s for s in aid if owner(s) != owner(aid[0]))
aid_turn = turns(g4, 2)[0]
# One seat that waits through all three.
watcher = next(seat for seat in range(4)
               if seat not in {owner(aid[0]), owner(aid_later), owner(aid_turn)})

fixtures = {
    "r4_choice": played(scouts_choices(g21, 4, "bene_gesserit_treachery")[0]),
    "r4_turn": waiting(turns(g21, 4)[0]),
    "r4_turn_own": played(turns(g21, 4)[0]),
    "r5_auction": played(calls[0]),
    "r5_auction_later": played(call_later, owner(calls[0])),
    "r5_turn": waiting(turns(g21, 5)[0]),
    "r5_later": waiting(turns(g21, 5)[2]),
    "r6_start": played(r6_start, 0),
    "r6_turn": waiting(turns(g21, 6)[0]),
    "r6_turn_own": played(turns(g21, 6)[0]),
    "aid_choice": played(aid[0], watcher, table4),
    "aid_later": played(aid_later, watcher, table4),
    "aid_turn": played(aid_turn, watcher, table4),
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
        + ' .scouts-stage-hide, .scouts-stage-tab, .scouts-stage-note,'
        + ' .scouts-stage-pager button, .scouts-stage-count, .scouts-stage-new')]
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
        pager: visible(stage.querySelector('.scouts-stage-pager')),
        pagerBox: box(stage.querySelector('.scouts-stage-pager')),
        kindBox: box(stage.querySelector('.scouts-stage-kind')),
        nameBox: box(stage.querySelector('.scouts-stage-name')),
        count: stage.querySelector('.scouts-stage-count').textContent,
        prevText: stage.querySelector('.scouts-stage-prev').textContent,
        nextText: stage.querySelector('.scouts-stage-next').textContent,
        prevDisabled: stage.querySelector('.scouts-stage-prev').disabled,
        nextDisabled: stage.querySelector('.scouts-stage-next').disabled,
        prevName: stage.querySelector('.scouts-stage-prev').getAttribute('aria-label'),
        nextName: stage.querySelector('.scouts-stage-next').getAttribute('aria-label'),
        prevNew: stage.querySelector('.scouts-stage-prev')
            .classList.contains('has-new'),
        nextNew: stage.querySelector('.scouts-stage-next')
            .classList.contains('has-new'),
        marks: [...stage.querySelectorAll('.scouts-stage-pager .scouts-stage-new')]
            .filter(visible).map((n) => n.textContent),
        prevTitle: stage.querySelector('.scouts-stage-prev').title,
        nextTitle: stage.querySelector('.scouts-stage-next').title,
        kindCut: (() => {
            const kind = stage.querySelector('.scouts-stage-kind');
            return kind.scrollWidth > kind.clientWidth + 1;
        })(),
        focusInCard: card.contains(document.activeElement),
        focusClass: document.activeElement ? document.activeElement.className : null,
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
        seat = CASES[name][0] if name in CASES else fixture.get("seat", 0)
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
    # Round 1 revealed nothing: no card, no tab, and `a` does nothing.
    stage = render(page, fixtures, "turn", language)
    check.ok(
        stage["hidden"] and not stage["tab"]
        and page.evaluate("toggleScoutsStage()") is False,
        f"{where}: no card in a round without items; the shortcut does nothing",
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


TAB_WORD = {"ko": "스카웃 카드", "en": "Scouts card"}
PAGER_WORDS = {"ko": ("◀ 이전", "다음 ▶"), "en": ("◀ Previous", "Next ▶")}


NEW_MARK = {"ko": "새", "en": "New"}
NEW_TITLE = {"ko": "아직 안 본 항목", "en": "not seen yet"}


def shot(page, name: str) -> None:
    """A screenshot without the turn banner a fixture swap may have raised
    over the card (phase_banner.js; it would pass on its own)."""
    page.evaluate("el('phase-banner').hidden = true")
    page.screenshot(path=str(SHOTS / name))


def fresh_browser(page) -> None:
    """A browser that has shown no page yet (the memory a reload clears)."""
    page.evaluate("scoutsStage.seen.clear(); scoutsStage.weighed.clear();")


def arrow(page, key: str) -> None:
    page.keyboard.press(key)
    settle(page)


def pager_fits(stage: dict) -> bool:
    """The pager inside the card, clear of the kind word (not cut) and the
    name."""
    return (
        inside(stage["pagerBox"], stage["card"])
        and stage["kindBox"]["right"] <= stage["pagerBox"]["left"] + 1
        and not stage["kindCut"]
        and stage["pagerBox"]["bottom"] <= stage["nameBox"]["top"] + 1
    )


def rounds(page, fixtures, language: str, viewport: dict) -> None:
    """Seed 21's rounds 4 to 6 as one table sees them (the replayed all-AI
    game): every revealed item comes up, a choice or not, the tab stays
    through the turns, two items page, a new round opens it again."""

    where = f"{language} {viewport['width']}x{viewport['height']} rounds"
    shots = language == "ko" and viewport["width"] == 1600

    def name(item: str) -> str:
        return page.evaluate("(id) => scoutsItem(id).name", item)

    render(page, fixtures, "turn", language)
    fresh_browser(page)

    # Round 4: a choice comes up; the step ends and the card stays.
    stage = render(page, fixtures, "r4_choice", language)
    check.ok(
        stage["open"] and stage["item"] == "bene_gesserit_treachery"
        and not stage["pager"],
        f"{where}: round 4's choice is up, one item, no pager",
        (stage["open"], stage["item"], stage["pager"]),
    )
    stage = render(page, fixtures, "r4_turn", language)
    check.ok(
        stage["open"] and stage["item"] == "bene_gesserit_treachery",
        f"{where}: the step is over and the card stays during the turns",
        (stage["open"], stage["item"]),
    )
    page.locator("#scouts-stage .scouts-stage-hide").click()
    page.evaluate("render({foreign: true})")
    stage = page.evaluate(STAGE_JS)
    treachery = name("bene_gesserit_treachery")
    check.ok(
        not stage["open"] and stage["tab"]
        and stage["tabText"] == f"{TAB_WORD[language]} · {treachery}",
        f"{where}: folded, the tab stays through another seat's turn",
        (stage["open"], stage["tab"], stage["tabText"]),
    )
    page.locator("#scouts-stage .scouts-stage-tab").click()
    check.ok(page.evaluate(STAGE_JS)["open"], f"{where}: the tab reopens it in a turn")
    # The viewer's own Agent turn is answered on the board: it folds, once.
    stage = render(page, fixtures, "r4_turn_own", language)
    check.ok(
        not stage["open"] and stage["tab"] and stage["legalOnBoard"] > 0,
        f"{where}: the viewer's own Agent turn folds it",
        (stage["open"], stage["tab"], stage["legalOnBoard"]),
    )
    if shots:
        shot(page, "stage_tab_agent_turn.png")
    page.locator("#scouts-stage .scouts-stage-tab").click()
    page.evaluate("render({foreign: true})")
    check.ok(
        page.evaluate(STAGE_JS)["open"],
        f"{where}: reopened during that turn, it does not fold again",
    )
    page.keyboard.press("a")
    check.ok(not page.evaluate(STAGE_JS)["open"], f"{where}: `a` folds it in a turn")

    # Round 5: the auction comes up while its calls are open, and another
    # seat's call (an update meanwhile) leaves the card on it.
    stage = render(page, fixtures, "r5_auction", language)
    check.ok(
        stage["open"] and stage["item"] == "critical_moment_mid" and not stage["pager"],
        f"{where}: the card is on the auction while the viewer calls",
        (stage["open"], stage["item"], stage["pager"]),
    )
    stage = render(page, fixtures, "r5_auction_later", language)
    check.ok(
        stage["open"] and stage["item"] == "critical_moment_mid",
        f"{where}: another seat's call leaves it on the auction",
        (stage["open"], stage["item"]),
    )
    page.keyboard.press("a")
    # Unlikely Allies, revealed only once the auction closed and resolved
    # with no Scouts decision, comes up by itself after the step, as the
    # second of two, even folded.
    stage = render(page, fixtures, "r5_turn", language)
    prev_word, next_word = PAGER_WORDS[language]
    check.ok(
        stage["open"] and stage["item"] == "unlikely_allies"
        and stage["kind"] == "event",
        f"{where}: the choice-less event opens the card by itself",
        (stage["open"], stage["item"]),
    )
    check.ok(
        stage["pager"] and stage["count"] == "2 / 2"
        and stage["prevText"] == prev_word and stage["nextText"] == next_word
        and not stage["prevDisabled"] and stage["nextDisabled"]
        and stage["prevName"] and stage["nextName"],
        f"{where}: two items: the counter, and next disabled at the end",
        (stage["pager"], stage["count"], stage["prevDisabled"], stage["nextDisabled"]),
    )
    check.ok(
        not stage["prevNew"] and not stage["nextNew"] and not stage["marks"],
        f"{where}: both seen, no button marked new",
        (stage["prevNew"], stage["nextNew"], stage["marks"]),
    )
    check.ok(
        pager_fits(stage) and stage["pageFits"] and stage["linesFit"]
        and stage["minFont"] >= 14,
        f"{where}: the pager fits the header, nothing overflows, text 14px+",
        (stage["pagerBox"], stage["kindBox"]["right"], stage["minFont"]),
    )
    covered = page.evaluate(COVER_JS)
    check.ok(not covered, f"{where}: the decision panel stays reachable", covered)
    if language == "en":
        leaks = HANGUL.findall(stage["text"] + stage["tabText"] + stage["attributes"])
        check.ok(not leaks, f"{where}: no Hangul in the English pager", leaks[:8])
    if shots:
        shot(page, "stage_two_items.png")
    page.locator("#scouts-stage .scouts-stage-prev").click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        stage["item"] == "critical_moment_mid" and stage["count"] == "1 / 2"
        and stage["prevDisabled"] and not stage["nextDisabled"]
        and stage["focusInCard"] and "scouts-stage-next" in stage["focusClass"],
        f"{where}: previous pages back; disabled at the start, focus on next",
        (stage["item"], stage["count"], stage["focusClass"]),
    )
    page.evaluate("render({foreign: true})")
    stage = page.evaluate(STAGE_JS)
    check.ok(
        stage["item"] == "critical_moment_mid" and stage["count"] == "1 / 2",
        f"{where}: the browsed page stays on a refresh",
        (stage["item"], stage["count"]),
    )
    arrow(page, "ArrowRight")
    stage = page.evaluate(STAGE_JS)
    check.ok(
        stage["item"] == "unlikely_allies" and stage["count"] == "2 / 2"
        and stage["focusInCard"],
        f"{where}: ArrowRight with focus in the card pages forward",
        (stage["item"], stage["count"], stage["focusClass"]),
    )
    arrow(page, "ArrowRight")
    check.ok(
        page.evaluate(STAGE_JS)["count"] == "2 / 2", f"{where}: and does not wrap"
    )
    arrow(page, "ArrowLeft")
    check.ok(
        page.evaluate(STAGE_JS)["count"] == "1 / 2",
        f"{where}: ArrowLeft pages back",
    )
    arrow(page, "Alt+ArrowRight")
    check.ok(
        page.evaluate(STAGE_JS)["count"] == "1 / 2",
        f"{where}: Alt with an arrow is not the card's",
    )
    # Focus elsewhere: the arrows are not the card's.
    page.evaluate("document.activeElement.blur()")
    arrow(page, "ArrowRight")
    check.ok(
        page.evaluate(STAGE_JS)["count"] == "1 / 2",
        f"{where}: with focus outside the card the arrows do not page",
    )
    # A click on the card itself gives it focus, and the arrows work.
    page.locator("#scouts-stage .scouts-stage-lines").click()
    arrow(page, "ArrowRight")
    check.ok(
        page.evaluate(STAGE_JS)["count"] == "2 / 2",
        f"{where}: a click on the card lets the arrows page",
    )
    arrow(page, "ArrowLeft")
    page.locator("#scouts-stage .scouts-stage-hide").click()
    stage = page.evaluate(STAGE_JS)
    more = {"ko": " 외 1", "en": " +1"}[language]
    check.ok(
        not stage["open"]
        and stage["tabText"]
        == f"{TAB_WORD[language]} · {name('critical_moment_mid')}{more}",
        f"{where}: the tab names the page shown and how many more",
        stage["tabText"],
    )
    stage = render(page, fixtures, "r5_later", language)
    check.ok(
        not stage["open"] and stage["tab"],
        f"{where}: folded, it stays folded through later turns",
    )
    page.locator("#scouts-stage .scouts-stage-tab").click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        stage["open"] and stage["item"] == "critical_moment_mid"
        and stage["count"] == "1 / 2",
        f"{where}: the tab brings back the page that was shown",
        (stage["item"], stage["count"]),
    )

    # A browser that first sees round 5 after its step (a reload, a late
    # spectator): the first unseen page opens, the next one waits behind a
    # "new" mark, and an update does not move the card to it.
    fresh_browser(page)
    stage = render(page, fixtures, "r5_later", language)
    check.ok(
        stage["open"] and stage["item"] == "critical_moment_mid"
        and stage["count"] == "1 / 2",
        f"{where}: arriving after the step, the first unseen page opens",
        (stage["open"], stage["item"], stage["count"]),
    )
    check.ok(
        stage["nextNew"] and not stage["prevNew"]
        and stage["marks"] == [NEW_MARK[language]]
        and NEW_TITLE[language] in stage["nextTitle"]
        and NEW_TITLE[language] not in stage["prevTitle"]
        and pager_fits(stage),
        f"{where}: next is marked new (mark and title), the pager still fits",
        (stage["nextNew"], stage["marks"], stage["nextTitle"], stage["kindBox"]),
    )
    if shots:
        shot(page, "stage_next_new.png")
    page.evaluate("render({foreign: true})")
    stage = page.evaluate(STAGE_JS)
    check.ok(
        stage["item"] == "critical_moment_mid" and stage["nextNew"],
        f"{where}: an update leaves the card where it is, still marked",
        (stage["item"], stage["nextNew"]),
    )
    page.locator("#scouts-stage .scouts-stage-next").click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        stage["item"] == "unlikely_allies" and not stage["marks"]
        and not stage["prevNew"],
        f"{where}: paged to, the unseen page is seen and the mark goes",
        (stage["item"], stage["marks"]),
    )

    # Round 6 starts with nothing revealed yet: no card, no tab.
    stage = render(page, fixtures, "r6_start", language)
    check.ok(
        stage["hidden"] and not stage["tab"]
        and page.evaluate("toggleScoutsStage()") is False,
        f"{where}: a round with no item yet takes it away",
    )
    # Market Opening resolves with no choice: it comes up by itself.
    stage = render(page, fixtures, "r6_turn", language)
    check.ok(
        stage["open"] and stage["item"] == "market_opening" and not stage["pager"]
        and stage["lineHtml"] == stage["panelLineHtml"] and stage["lineHtml"],
        f"{where}: round 6's choice-less event opens it, every line there",
        (stage["open"], stage["item"], stage["pager"]),
    )
    check.ok(
        stage["pageFits"] and stage["linesFit"] and stage["minFont"] >= 14,
        f"{where}: round 6's card fits",
    )
    if shots:
        shot(page, "stage_choiceless_event.png")
    stage = render(page, fixtures, "r6_turn_own", language)
    check.ok(
        not stage["open"] and stage["tab"],
        f"{where}: and folds for the viewer's own Agent turn",
    )
    reach = page.evaluate(
        """() => {
            const spot = document.querySelector('#board .hotspot.legal');
            if (!spot) return null;
            const r = spot.getBoundingClientRect();
            const hit = document.elementFromPoint(
                r.left + r.width / 2, r.top + r.height / 2);
            return Boolean(hit && spot.contains(hit));
        }"""
    )
    check.ok(reach, f"{where}: folded, a legal space takes the click", reach)
    check.ok(page.evaluate("window.sentIndexes") == [], f"{where}: nothing was sent")


def step_mark(page, fixtures, language: str, viewport: dict) -> None:
    """Seed 4's round 2 for a seat that waits: Planetary Exploration was
    resolved with no decision, Send for Aid is being decided. The card stays
    on the step's item, the way back marked new; after the step the unseen
    page opens by itself, unless the player already paged to it."""

    where = f"{language} {viewport['width']}x{viewport['height']} step"
    shots = language == "ko" and viewport["width"] == 1600
    render(page, fixtures, "turn", language)
    fresh_browser(page)
    stage = render(page, fixtures, "aid_choice", language)
    check.ok(
        stage["open"] and stage["item"] == "send_for_aid" and stage["count"] == "2 / 2",
        f"{where}: the card is on the item being decided, not the unseen one",
        (stage["open"], stage["item"], stage["count"]),
    )
    check.ok(
        stage["prevNew"] and not stage["nextNew"]
        and stage["marks"] == [NEW_MARK[language]]
        and NEW_TITLE[language] in stage["prevTitle"]
        and pager_fits(stage) and stage["pageFits"] and stage["minFont"] >= 14,
        f"{where}: previous is marked new, the pager fits",
        (stage["prevNew"], stage["marks"], stage["prevTitle"], stage["minFont"]),
    )
    if language == "en":
        leaks = HANGUL.findall(stage["text"] + stage["attributes"])
        check.ok(not leaks, f"{where}: no Hangul in English", leaks[:8])
    if shots:
        shot(page, "stage_step_new.png")
    stage = render(page, fixtures, "aid_later", language)
    check.ok(
        stage["open"] and stage["item"] == "send_for_aid" and stage["prevNew"],
        f"{where}: another seat's decision leaves the card on the item",
        (stage["open"], stage["item"], stage["prevNew"]),
    )
    stage = render(page, fixtures, "aid_turn", language)
    check.ok(
        stage["open"] and stage["item"] == "planetary_exploration"
        and stage["count"] == "1 / 2" and not stage["marks"],
        f"{where}: the step over, the unseen item opens by itself",
        (stage["open"], stage["item"], stage["count"], stage["marks"]),
    )

    # Paged to during the step, it is seen: the step's end opens nothing.
    render(page, fixtures, "turn", language)
    fresh_browser(page)
    render(page, fixtures, "aid_choice", language)
    page.locator("#scouts-stage .scouts-stage-prev").click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        stage["item"] == "planetary_exploration" and not stage["marks"],
        f"{where}: paging back shows it and takes the mark away",
        (stage["item"], stage["marks"]),
    )
    stage = render(page, fixtures, "aid_later", language)
    check.ok(
        stage["item"] == "planetary_exploration" and stage["count"] == "1 / 2",
        f"{where}: the browsed page stays while the step's item is the same",
        (stage["item"], stage["count"]),
    )
    page.locator("#scouts-stage .scouts-stage-next").click()
    page.locator("#scouts-stage .scouts-stage-hide").click()
    stage = render(page, fixtures, "aid_turn", language)
    check.ok(
        not stage["open"] and stage["tab"],
        f"{where}: nothing unseen, so the step's end leaves it folded",
        (stage["open"], stage["tab"]),
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

    # Every reveal of the game: (round, item, the cursor right after it).
    reveals = page.evaluate(
        """() => {
            const review = state.review;
            const found = [];
            for (const entry of review.meta.log) {
                for (const ev of entry.events || []) {
                    if (ev.kind !== 'scouts_item_revealed') continue;
                    const cursor = review.liveIndex.indexOf(entry.index) + 1;
                    if (cursor > 0) found.push(cursor);
                }
            }
            return found;
        }"""
    )
    rounds_seen: dict[int, list[tuple[str, int]]] = {}
    for cursor in reveals:
        page.evaluate("async (c) => { await reviewGoto(c); }", cursor)
        # The item just revealed: the last of its round's list (one that
        # resolves with no choice is already closed, scouts_item empty).
        round_number, item = page.evaluate(
            """() => {
                const round = state.view.round_number;
                const ids = state.view.scouts_revealed
                    .filter(([r]) => r === round).map(([, id]) => id);
                return [round, ids[ids.length - 1]];
            }"""
        )
        rounds_seen.setdefault(round_number, []).append((item, cursor))
    paired = next(
        (r for r, items in sorted(rounds_seen.items()) if len(items) >= 2), None
    )
    check.ok(paired is not None, "review: a round revealed two items", rounds_seen)
    if paired is None:
        context.close()
        return
    # Its first turn: the step's end, both items in the round's list.
    (first, _), (second, at) = rounds_seen[paired][:2]
    turn_cursor = page.evaluate(
        """async ({from, round}) => {
            const steps = state.review.meta.step_count;
            for (let c = from; c <= steps; c += 1) {
                await reviewGoto(c);
                if (state.view.round_number !== round) return null;
                if (!state.view.scouts_item) return c;
            }
            return null;
        }""",
        {"from": at, "round": paired},
    )
    check.ok(bool(turn_cursor), "review: the step ends in that round", turn_cursor)
    if turn_cursor:
        page.evaluate(
            "async () => { await reviewGoto(0);"
            " scoutsStage.seen.clear(); scoutsStage.weighed.clear(); }"
        )
        page.evaluate("async (c) => { await reviewGoto(c); }", turn_cursor)
        settle(page)
        stage = page.evaluate(STAGE_JS)
        check.ok(
            stage["open"] and stage["pager"] and stage["count"] == "1 / 2"
            and stage["item"] == first and stage["nextNew"],
            "review: arriving after two reveals opens the first, next marked new",
            (stage["open"], stage["count"], stage["item"], first, second),
        )
        page.locator("#scouts-stage .scouts-stage-next").click()
        stage = page.evaluate(STAGE_JS)
        check.ok(
            stage["item"] == second and stage["count"] == "2 / 2",
            "review: next pages to the second",
            (stage["item"], stage["count"]),
        )
        page.screenshot(path=str(SHOTS / "stage_review_two_items.png"))
        page.locator("#scouts-stage .scouts-stage-hide").click()
        page.evaluate("async (c) => { await reviewGoto(c + 1); }", turn_cursor)
        check.ok(
            page.evaluate(STAGE_JS)["tab"] and not page.evaluate(STAGE_JS)["open"],
            "review: folded, a step on keeps the tab",
        )
    # The next round with a reveal: its new page opens it again.
    later = next((r for r in sorted(rounds_seen) if r > paired), None)
    if later is not None:
        cursor = rounds_seen[later][0][1]
        page.evaluate("async (c) => { await reviewGoto(c); }", cursor)
        settle(page)
        stage = page.evaluate(STAGE_JS)
        check.ok(
            stage["open"] and stage["item"] == rounds_seen[later][0][0],
            "review: the next round's reveal opens it again",
            (later, stage["open"], stage["item"]),
        )
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
        for viewport in VIEWPORTS[:2]:
            page.set_viewport_size(viewport)
            for language in ("ko", "en"):
                rounds(page, fixtures, language, viewport)
                step_mark(page, fixtures, language, viewport)
        help_row(page, fixtures)
        check.ok(not recorder.js_errors, "no JavaScript errors", recorder.js_errors)
        context.close()
        review(browser, base)
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
