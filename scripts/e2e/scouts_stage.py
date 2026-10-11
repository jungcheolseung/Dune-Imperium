"""The revealed Arrakeen Scouts item as a card over the board (2026-10-11).

User request after a real game: during the Scouts step the item should stay
up over the board as a big card, like Dire Wolf Game Room's reveal page, with
a toggle to see the board. #scouts-stage takes the board's grid cell; its
frame is the board square and the card sits inside it: a header band with
the kind in spaced capitals and the item's name, the kind's painting, the
item's lines on a parchment, and a "보드 보기" button; folded, nothing of
it is left over the board (third request, below) and a button beside the
Scouts panel's heading names the item and brings it back; `a` toggles it
too.

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
no sideways overflow, no Hangul in English; the button, the panel's button
and the shortcut (with the Hangul IME's key), Escape leaving it alone, a
refresh keeping the fold and the very same nodes, a new item opening it
again, a round without items having no card; the help's shortcut row; and a
finished all-AI game's review at a Scouts step.

Second request the same day: every revealed item comes up, not only those
with a choice, and the card stays at hand all round. All-AI games replayed
step by step (their rounds as a table sees them). Seed 21: round 4's choice
stays up after the step and through the turns, the panel's button reopens
it, the viewer's own Agent turn folds it once (reopened, it stays); round
5's auction is on the card while the calls are open, and another seat's
call leaves it there; Unlikely Allies, revealed after the auction closed
and resolved with no Scouts decision, opens it by itself after the step as
page 2 of 2 -- the counter, previous / next disabled at the ends, the
arrows with focus inside the card (not outside, not with Alt), the browsed
page kept on a refresh, the panel's button naming the page and how many
more; a browser arriving after the step opens the first unseen page and
marks next "new" (mark and title) without an update moving the card; round
6 has no card before its reveal and Market Opening, also choice-less, opens
it again. Seed 4's round
2 (Planetary Exploration with no decision, then Send for Aid): the card
stays on the item being decided, previous marked new, through another
seat's decision; the unseen item opens by itself once the step is over,
and not if the player paged to it meanwhile. The review pages a round of
two reveals and opens again at the next round's reveal. Korean and English
at 1366x768 and 1600x950, the pager inside the header, the kind word not
cut and the name clear.

Third request (2026-10-11, after a real game). One: the tab left on the
board's top edge while folded covered the board. Folded, #scouts-stage is
now hidden whole -- no point across the board hits it, and the tab is gone
from the page -- and the re-open control is a button beside the Scouts
panel's heading ("카드로 보기 ▸ <name> 외 N" / "Show card ▸ <name> +N",
named by its word and the item, "카드 접기" / "Hide card" while the card is
up), which keeps its node and focus across renders; clicking it, Enter and
Space on it, and `a` open and fold the card. Two: during a Scouts step that
revealed secret picks, the card listed the picks still waiting under "비밀
선택 공개", so players read them as revealed. Seed 2's Covert Operation
(round 6: seat 2 picks a next-round line, the other three two-round lines),
replayed with the log the table holds: at round 7's reveal a waiting seat's
card shows exactly seat 2's row with its line under "6라운드 작전 변경", the
other three apart as "아직 비공개: …" with none of their lines anywhere, and
the Scouts panel words them the same way; at round 8's the three rows and
nothing waiting; with no log reaching the step, the title says the reveal is
to come ("비밀 선택 공개 준비"). Korean and English at 1366x768 and
1600x950, and seed 2's review at round 7's reveal.

Nothing is submitted: a UI callback records any index the page would send.
Screenshots per kind (Korean, 1600x950) go to E2E_SHOTS_DIR as
stage_<kind>.png, with stage_two_items.png, stage_choiceless_event.png,
stage_folded_agent_turn.png, stage_folded_panel_button.png,
stage_step_new.png, stage_next_new.png, stage_sec_r7_reveal.png,
stage_sec_r8_reveal.png and stage_review_secrets.png.
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
from dune_imperium.rules.scouts_secrets import SECRET_ITEM, pick_delay
from dune_imperium.server.sessions import GameSessionManager, _log_entries_json

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

# Seed 2: round 6 reveals Covert Operation; seat 2 picks a next-round line,
# the other three two-round lines. Round 7's Scouts step reveals seat 2's
# pick alone (its Spy placement is being decided) while the other three wait;
# round 8's reveals those three. The table sees them with the log it would
# hold (the AI game's own, cut at that step, redacted for the seat).
ai2 = manager._get(str(manager.create_game(
    ("heuristic",) * 4, game_seed=2, arrakeen_scouts=True)["game_id"]))
g2 = [ai2.engine.reset(ai2.config, ai2.game_seed)]
for recorded in ai2.steps:
    g2.append(ai2.engine.apply(g2[-1], recorded).state)
assert len(ai2.log) == len(ai2.steps)
table2 = str(manager.create_game(("human",) * 4, game_seed=2,
                                 arrakeen_scouts=True)["game_id"])
picks2 = sorted({row for s in g2 for row in s.scouts_secret_picks})
assert {(r, e) for r, e, _, _ in picks2} == {(6, "covert_operation")}, picks2

def due(round_number):
    return sorted([seat, pick] for r, e, seat, pick in picks2
                  if r + pick_delay(e, pick) == round_number)

def secret_cursor(round_number):
    return next(i for i, s in enumerate(g2) if s.round_number == round_number
                and s.scouts_item == SECRET_ITEM and owner(s) is not None)

assert len(due(7)) == 1 and len(due(8)) == 3, (due(7), due(8))

def with_log(index, seat):
    state = g2[index]
    fixture = played(state, seat, table2)
    fixture["log"] = {"seat": seat, "epoch": "e2e", "count": index,
                      "entries": _log_entries_json(
                          tuple(ai2.log[:index]), seat, False, 0)}
    fixture["expect"] = {
        "event_round": 6, "event": "covert_operation",
        "revealed": due(state.round_number),
        "pending": sorted(seat for _, _, seat, _ in state.scouts_secret_picks),
        "hidden_picks": sorted({pick for _, _, _, pick in state.scouts_secret_picks}),
    }
    return fixture

r7 = secret_cursor(7)
r7_viewer = next(seat for _, _, seat, _ in g2[r7].scouts_secret_picks
                 if seat != owner(g2[r7]))
r8 = secret_cursor(8)
r8_viewer = next(seat for seat in range(4)
                 if seat != owner(g2[r8]) and seat not in {s for s, _ in due(8)})
sec_r7 = with_log(r7, r7_viewer)
sec_r7_nolog = dict(sec_r7, log={"seat": r7_viewer, "epoch": "e2e", "count": 0,
                                  "entries": []})

fixtures = {
    "sec_r7": sec_r7,
    "sec_r7_nolog": sec_r7_nolog,
    "sec_r8": with_log(r8, r8_viewer),
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
        pick: null, held: null, counts: {}, log: fixture.log || {entries: []}});
    window.sentIndexes = [];
    window.applyAction = (index) => window.sentIndexes.push(index);
    showScreen('game-screen');
    render();
}"""

# Everything the checks read off the stage at once.
STAGE_JS = """() => {
    const stage = el('scouts-stage');
    const card = stage.querySelector('.scouts-stage-card');
    const opener = document.querySelector('#scouts-panel .scouts-stage-open');
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
        + ' .scouts-stage-hide, .scouts-stage-note, .scouts-stage-event,'
        + ' .scouts-stage-pager button, .scouts-stage-count, .scouts-stage-new')]
        .filter(visible)
        .map((node) => parseFloat(getComputedStyle(node).fontSize));
    const linesBox = stage.querySelector('.scouts-stage-lines');
    // What lies over the board: points across the board's box that hit
    // anything of the Scouts card.
    const over = [];
    const b = el('board').getBoundingClientRect();
    for (let i = 1; i < 10; i += 1) {
        for (let j = 1; j < 10; j += 1) {
            const hit = document.elementFromPoint(
                b.left + (b.width * i) / 10, b.top + (b.height * j) / 10);
            if (hit && stage.contains(hit)) over.push(hit.className);
        }
    }
    return {
        hidden: stage.hidden,
        open: visible(card),
        // The Scouts panel's button, and whether it would bring the card
        // back (aria-expanded false) or fold it.
        opener: Boolean(opener) && visible(opener),
        openerOpen: Boolean(opener) && opener.getAttribute('aria-expanded') === 'true',
        openerText: opener ? opener.textContent : '',
        openerTitle: opener ? opener.title : '',
        openerFont: opener && visible(opener)
            ? parseFloat(getComputedStyle(opener).fontSize) : null,
        openerInPanel: Boolean(opener)
            && opener.parentElement.classList.contains('scouts-panel-head')
            && Boolean(opener.parentElement.querySelector('h2')),
        openerFocused: Boolean(opener) && document.activeElement === opener,
        // Inside the Scouts panel, which does not scroll sideways for it.
        openerFits: Boolean(opener) && (() => {
            const panel = el('scouts-panel');
            const o = opener.getBoundingClientRect();
            const r = panel.getBoundingClientRect();
            return o.left >= r.left - 1 && o.right <= r.right + 1
                && panel.scrollWidth <= panel.clientWidth + 1;
        })(),
        // The board tab of before 2026-10-11 must be gone, and nothing of
        // the card over the board while it is folded.
        tabExists: Boolean(document.querySelector('.scouts-stage-tab')),
        over,
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
SECRETS_PENDING = {"ko": "비밀 선택 공개 준비", "en": "Secret picks: reveal to come"}
NOT_REVEALED = {"ko": "아직 비공개: ", "en": "Not revealed yet: "}
# The Scouts panel's button: folded, it names the page it brings back.
SHOW_WORD = {"ko": "카드로 보기", "en": "Show card"}
FOLD_WORD = {"ko": "카드 접기", "en": "Hide card"}

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


def folded(stage: dict) -> bool:
    """Folded: nothing of the card over the board, no tab, and the Scouts
    panel's button there to bring it back."""
    return (
        not stage["open"]
        and stage["hidden"]
        and not stage["over"]
        and not stage["tabExists"]
        and stage["opener"]
        and not stage["openerOpen"]
    )


def up(stage: dict) -> bool:
    """The card is up, and the Scouts panel's button would fold it."""
    return (
        stage["open"]
        and not stage["hidden"]
        and stage["opener"]
        and stage["openerOpen"]
        and not stage["tabExists"]
    )


def show_label(language: str, name: str, more: int = 0) -> str:
    """The folded button's text: the word, the arrow and the page."""
    extra = {"ko": f" 외 {more}", "en": f" +{more}"}[language] if more else ""
    return f"{SHOW_WORD[language]} ▸ {name}{extra}"


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
        up(stage) and stage["openerText"] == FOLD_WORD[language]
        and stage["openerInPanel"],
        f"{where}: the card is up; the Scouts panel's button folds it",
        (stage["hidden"], stage["open"], stage["openerText"]),
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
    # The made-up "secrets" fixture has no log, so no reveal of this round's
    # step to show: the page says the reveal is to come (secret_reveals()
    # checks a real one).
    expected_name = (
        SECRETS_PENDING[language] if item_id == "secrets" else catalog_item["name"]
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
            and stage["dividers"] == len(pending) - 1
            and all(t.startswith(NOT_REVEALED[language]) for t in stage["lineText"]),
            f"{where}: one 'not revealed yet' line per event whose picks wait",
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
        leaks = HANGUL.findall(
            stage["text"] + stage["openerText"] + stage["openerTitle"]
            + stage["attributes"]
        )
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
    opener = page.locator("#scouts-panel .scouts-stage-open")
    check.ok(
        stage["hideText"] == {"ko": "보드 보기", "en": "Show board"}[language],
        f"{where}: the button says what it does",
        stage["hideText"],
    )
    check.ok(
        up(stage) and stage["openerText"] == FOLD_WORD[language]
        and stage["openerInPanel"] and stage["openerFont"] >= 14,
        f"{where}: beside the Scouts panel's heading, a button that folds it",
        (stage["openerText"], stage["openerInPanel"], stage["openerFont"]),
    )
    hide.click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        folded(stage) and stage["openerText"] == show_label(language, name)
        and stage["openerFits"],
        f"{where}: folded, nothing over the board; the panel's button names it",
        (stage["open"], stage["hidden"], stage["over"], stage["openerText"]),
    )
    check.ok(
        stage["openerFocused"],
        f"{where}: focus moves to the panel's button",
        stage["focusClass"],
    )
    # Its accessible name: the word and the item (the arrow is hidden).
    named = page.get_by_role(
        "button", name=re.compile(rf"^{re.escape(SHOW_WORD[language])}\s+"
                                  rf"{re.escape(name)}$")
    )
    check.ok(
        named.count() == 1,
        f"{where}: the panel's button is named by its word and the item",
    )
    check.ok(
        "(A)" in stage["openerTitle"],
        f"{where}: its title names the shortcut",
        stage["openerTitle"],
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
    # A refresh (another seat's move) keeps the fold, the card's nodes and
    # the panel's button with its focus, though the panel is drawn again.
    page.evaluate(
        "window.markedLine = document.querySelector('#scouts-stage .scouts-line');"
        " window.markedOpener = scoutsStage.opener;"
        " render({foreign: true});"
    )
    stage = page.evaluate(STAGE_JS)
    check.ok(
        folded(stage)
        and page.evaluate(
            "window.markedLine === document.querySelector('#scouts-stage .scouts-line')"
            " && window.markedOpener === document.querySelector("
            "'#scouts-panel .scouts-stage-open')"
        )
        and stage["openerFocused"],
        f"{where}: a refresh keeps the fold, the nodes and the focus",
    )
    opener.click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        up(stage) and stage["openerText"] == FOLD_WORD[language]
        and stage["openerFocused"],
        f"{where}: the panel's button brings it back and keeps the focus",
        (stage["open"], stage["openerText"], stage["focusClass"]),
    )
    opener.click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        folded(stage), f"{where}: pressed again, it folds the card", stage["over"]
    )
    # The keyboard: focused, Enter and Space press it.
    page.keyboard.press("Enter")
    opened = page.evaluate(STAGE_JS)
    page.keyboard.press("Space")
    shut = page.evaluate(STAGE_JS)
    check.ok(
        up(opened) and folded(shut),
        f"{where}: Enter and Space on the focused button open and fold it",
        (opened["open"], shut["open"]),
    )
    opener.click()
    # The shortcut, with the Hangul IME on (code KeyA, key ㅁ) and plain.
    page.evaluate(
        "document.dispatchEvent(new KeyboardEvent('keydown',"
        " {key: 'ㅁ', code: 'KeyA', bubbles: true}))"
    )
    shut = page.evaluate(STAGE_JS)
    page.keyboard.press("a")
    reopened = page.evaluate(STAGE_JS)
    check.ok(
        folded(shut) and shut["openerText"] == show_label(language, name)
        and up(reopened) and reopened["openerText"] == FOLD_WORD[language],
        f"{where}: `a` folds and unfolds it, and the panel's button follows",
        (shut["open"], reopened["open"], shut["openerText"]),
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
        up(stage) and stage["item"] == "highest_bidder_late",
        f"{where}: a new item opens it again",
    )
    # Round 1 revealed nothing: no card, no button, and `a` does nothing.
    stage = render(page, fixtures, "turn", language)
    check.ok(
        stage["hidden"] and not stage["opener"] and not stage["over"]
        and page.evaluate("toggleScoutsStage()") is False,
        f"{where}: no card nor button in a round without items; no shortcut",
    )

    # A decision the board answers starts folded: Smoke and Mirrors' choice
    # is up, its Spy placement (a post on the board) folds it.
    stage = render(page, fixtures, "choice", language, seat=0)
    check.ok(
        up(stage) and stage["legalOnBoard"] == 0,
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
        folded(stage) and stage["legalOnBoard"] > 0 and post,
        f"{where}: the Spy placement starts folded and its posts take the click",
        (stage["open"], stage["legalOnBoard"], post, stage["over"]),
    )
    page.evaluate("render({foreign: true})")
    check.ok(
        folded(page.evaluate(STAGE_JS)), f"{where}: and stays folded on a refresh"
    )
    opener.click()
    check.ok(
        up(page.evaluate(STAGE_JS)), f"{where}: the panel's button still opens it there"
    )
    # A board decision starting from a fresh item: folded from the start.
    render(page, fixtures, "turn", language)
    stage = render(page, fixtures, "spy", language, seat=0)
    check.ok(folded(stage), f"{where}: folded when the item opens on it")
    check.ok(page.evaluate("window.sentIndexes") == [], f"{where}: nothing was sent")


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
    game): every revealed item comes up, a choice or not, the button stays
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
        folded(stage) and stage["openerText"] == show_label(language, treachery),
        f"{where}: folded through another seat's turn, the panel's button stays",
        (stage["open"], stage["over"], stage["openerText"]),
    )
    page.locator("#scouts-panel .scouts-stage-open").click()
    check.ok(
        up(page.evaluate(STAGE_JS)), f"{where}: the panel's button reopens it in a turn"
    )
    # The viewer's own Agent turn is answered on the board: it folds, once.
    stage = render(page, fixtures, "r4_turn_own", language)
    check.ok(
        folded(stage) and stage["legalOnBoard"] > 0,
        f"{where}: the viewer's own Agent turn folds it, nothing over the board",
        (stage["open"], stage["over"], stage["legalOnBoard"]),
    )
    if shots:
        shot(page, "stage_folded_agent_turn.png")
    page.locator("#scouts-panel .scouts-stage-open").click()
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
        leaks = HANGUL.findall(
            stage["text"] + stage["openerText"] + stage["openerTitle"]
            + stage["attributes"]
        )
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
    check.ok(
        folded(stage)
        and stage["openerText"]
        == show_label(language, name("critical_moment_mid"), 1)
        and stage["openerFits"] and stage["openerFont"] >= 14,
        f"{where}: the panel's button names the page shown and how many more",
        stage["openerText"],
    )
    named = page.get_by_role(
        "button",
        name=re.compile(
            rf"^{re.escape(SHOW_WORD[language])}\s+"
            rf"{re.escape(name('critical_moment_mid'))}"
        ),
    )
    check.ok(named.count() == 1, f"{where}: and is named so")
    stage = render(page, fixtures, "r5_later", language)
    check.ok(
        folded(stage),
        f"{where}: folded, it stays folded through later turns",
        (stage["open"], stage["over"]),
    )
    if shots:
        shot(page, "stage_folded_panel_button.png")
    page.locator("#scouts-panel .scouts-stage-open").click()
    stage = page.evaluate(STAGE_JS)
    check.ok(
        up(stage) and stage["item"] == "critical_moment_mid"
        and stage["count"] == "1 / 2",
        f"{where}: the panel's button brings back the page that was shown",
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

    # Round 6 starts with nothing revealed yet: no card, no button.
    stage = render(page, fixtures, "r6_start", language)
    check.ok(
        stage["hidden"] and not stage["opener"]
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
        folded(stage),
        f"{where}: and folds for the viewer's own Agent turn",
        (stage["open"], stage["over"]),
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
        folded(stage),
        f"{where}: nothing unseen, so the step's end leaves it folded",
        (stage["open"], stage["over"]),
    )
    check.ok(page.evaluate("window.sentIndexes") == [], f"{where}: nothing was sent")


# The reveal page's rows against what the engine revealed (expect, from the
# fixture): the event headings, each revealed seat's row, the rows of picks
# still secret, and the rows the page must draw for them, made in the page
# with its own helpers.
SECRETS_JS = """(expect) => {
    const stage = el('scouts-stage');
    const lines = stage.querySelector('.scouts-stage-lines');
    const item = scoutsItem(expect.event);
    const effectHtml = (pick) => {
        const box = document.createElement('div');
        box.appendChild(effectNode(item.lines[pick] || '', item.lines_ko[pick]));
        return box.innerHTML;
    };
    const rowHtml = ([seat, pick]) => {
        const box = document.createElement('div');
        box.append(`${playerLabel(seat)}: `, effectNode(
            item.lines[pick] || '', item.lines_ko[pick]));
        return box.innerHTML;
    };
    const waitingText = expect.pending.length
        ? [t('panels.scouts_secret_waiting', {round: expect.event_round,
            name: item.name, seats: expect.pending.map(playerLabel).join(', ')})]
        : [];
    // The Scouts panel's "secret picks" section: the rows after its h3.
    const panelRows = [];
    for (const h3 of document.querySelectorAll('#scouts-panel h3')) {
        if (h3.textContent !== t('panels.scouts_secrets')) continue;
        for (const row of h3.nextElementSibling.querySelectorAll('.scouts-row')) {
            if (!row.classList.contains('scouts-own')) panelRows.push(row.textContent);
        }
    }
    return {
        events: [...lines.querySelectorAll('.scouts-stage-event')]
            .map((n) => n.textContent),
        wantEvents: expect.revealed.length
            ? [t('scouts_stage.secrets_event', {round: expect.event_round,
                name: item.name})]
            : [],
        revealed: [...lines.querySelectorAll('.scouts-stage-revealed')]
            .map((n) => [Number(n.dataset.seat), n.innerHTML]),
        wantRevealed: expect.revealed.map((row) => [row[0], rowHtml(row)]),
        waiting: [...lines.querySelectorAll('.scouts-stage-waiting')]
            .map((n) => n.textContent),
        wantWaiting: waitingText,
        // A pick still secret: its line is nowhere on the card.
        hiddenShown: expect.hidden_picks.filter(
            (pick) => lines.innerHTML.includes(effectHtml(pick))),
        panelRows,
    };
}"""


def secret_reveals(page, fixtures, language: str, viewport: dict) -> None:
    """Seed 2's Covert Operation (round 6) as a waiting seat sees its reveal
    (user report 2026-10-11: the page listed the picks still waiting, under
    "secret picks revealed", so they read as revealed). Round 7's step
    reveals seat 2's next-round pick only: the page shows exactly that row
    with its line, and the other three seats apart as not revealed, none of
    their lines anywhere. Round 8's reveals those three, nothing left. A
    log that does not reach the step: the page says the reveal is to come."""

    where = f"{language} {viewport['width']}x{viewport['height']} secrets"
    shots = language == "ko" and viewport["width"] == 1600
    render(page, fixtures, "turn", language)
    fresh_browser(page)
    for name in ("sec_r7", "sec_r8", "sec_r7_nolog"):
        expect = dict(fixtures[name]["expect"])
        logged = bool(fixtures[name]["log"]["entries"])
        if not logged:
            expect["revealed"] = []
        stage = render(page, fixtures, name, language)
        page.evaluate("clearPlayEffects()")
        got = page.evaluate(SECRETS_JS, expect)
        label = f"{where} {name}"
        check.ok(
            up(stage) and stage["item"] == "secrets" and stage["kind"] == "event",
            f"{label}: the reveal page is up",
            (stage["open"], stage["item"], stage["kind"]),
        )
        title = SECRETS_NAME if logged else SECRETS_PENDING
        check.ok(
            stage["name"] == title[language],
            f"{label}: titled {'as a reveal' if logged else 'as still to come'}",
            stage["name"],
        )
        check.ok(
            got["events"] == got["wantEvents"],
            f"{label}: the event the revealed picks belong to",
            (got["events"], got["wantEvents"]),
        )
        check.ok(
            sorted(got["revealed"]) == sorted(got["wantRevealed"])
            and len(got["revealed"]) == len(expect["revealed"]),
            f"{label}: exactly the picks this step revealed, each seat's line",
            (got["revealed"], got["wantRevealed"]),
        )
        check.ok(
            got["waiting"] == got["wantWaiting"]
            and all(t.startswith(NOT_REVEALED[language]) for t in got["waiting"]),
            f"{label}: the seats whose picks wait, worded as not revealed",
            (got["waiting"], got["wantWaiting"]),
        )
        check.ok(
            not got["hiddenShown"],
            f"{label}: no line of a pick still secret on the card",
            got["hiddenShown"],
        )
        check.ok(
            got["panelRows"] == got["wantWaiting"],
            f"{label}: the Scouts panel words the waiting picks the same way",
            (got["panelRows"], got["wantWaiting"]),
        )
        check.ok(
            stage["minFont"] >= 14 and stage["linesFit"] and stage["pageFits"]
            and not page.evaluate(COVER_JS),
            f"{label}: text 14px+, nothing overflows, the decision panel clear",
            (stage["minFont"], stage["linesFit"], stage["pageFits"]),
        )
        if language == "en":
            leaks = HANGUL.findall(
                stage["text"] + stage["openerText"] + stage["attributes"]
                + " ".join(got["panelRows"])
            )
            check.ok(not leaks, f"{label}: no Hangul in English", leaks[:8])
        if shots and name != "sec_r7_nolog":
            shot(page, f"stage_{name}_reveal.png")
    check.ok(page.evaluate("window.sentIndexes") == [], f"{where}: nothing was sent")


def secrets_review(browser, base: str) -> None:
    """Seed 2's finished all-AI game reviewed at round 7's reveal: the page
    reads the review's log up to its cursor."""

    context, page, _ = open_context(browser, "scouts-stage-secrets", VIEWPORTS[1])
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    # The fixture's game: Arrakeen Scouts and nothing else the form turns on
    # (a dependent option before the one it hangs on).
    for option in ("go-to-11", "tech", "epic-game", "leader-draft", "choam",
                   "promo", "immortality", "bloodlines"):
        page.set_checked(f"#opt-{option}", False)
    page.set_checked("#opt-scouts", True)
    page.fill("#opt-seed", "2")
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.review !== null && state.view !== null")
    # The steps that revealed secret picks, and the cursor right after each.
    found = page.evaluate(
        """() => {
            const review = state.review;
            const found = [];
            for (const entry of review.meta.log) {
                const picks = (entry.events || [])
                    .filter((ev) => ev.kind === 'scouts_secret_revealed')
                    .map((ev) => [ev.payload.player, ev.payload.pick]);
                const cursor = review.liveIndex.indexOf(entry.index) + 1;
                if (picks.length && cursor > 0) found.push([cursor, picks]);
            }
            return found;
        }"""
    )
    check.ok(
        [len(picks) for _, picks in found] == [1, 3],
        "secrets review: one pick revealed in round 7, three in round 8",
        found,
    )
    if not found:
        context.close()
        return
    cursor, picks = found[0]
    page.evaluate("async (c) => { stopPlayback(); await reviewGoto(c); }", cursor)
    settle(page)
    stage = page.evaluate(STAGE_JS)
    got = page.evaluate(
        """() => ({
            cursor: state.view.scouts_item,
            seats: [...document.querySelectorAll(
                '#scouts-stage .scouts-stage-revealed')]
                .map((n) => Number(n.dataset.seat)),
            waiting: [...document.querySelectorAll(
                '#scouts-stage .scouts-stage-waiting')].map((n) => n.textContent),
        })"""
    )
    check.ok(
        got["cursor"] == "secrets" and stage["open"] and stage["item"] == "secrets"
        and stage["name"] == SECRETS_NAME["ko"]
        and got["seats"] == [seat for seat, _ in picks]
        and len(got["waiting"]) == 1
        and got["waiting"][0].startswith(NOT_REVEALED["ko"]),
        "secrets review: the reveal page shows round 7's pick, the rest waiting",
        (got, stage["name"]),
    )
    page.screenshot(path=str(SHOTS / "stage_review_secrets.png"))
    context.close()


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
    check.ok(folded(page.evaluate(STAGE_JS)), "review: it folds there too")
    page.screenshot(path=str(SHOTS / "stage_review_folded.png"))
    page.evaluate("async () => { await reviewGoto(0); }")
    stage = page.evaluate(STAGE_JS)
    check.ok(
        stage["hidden"] and not stage["opener"], "review: no card before the step"
    )

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
            folded(page.evaluate(STAGE_JS)),
            "review: folded, a step on keeps it folded, the panel's button there",
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
                secret_reveals(page, fixtures, language, viewport)
                rounds(page, fixtures, language, viewport)
                step_mark(page, fixtures, language, viewport)
        help_row(page, fixtures)
        check.ok(not recorder.js_errors, "no JavaScript errors", recorder.js_errors)
        context.close()
        review(browser, base)
        secrets_review(browser, base)
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
