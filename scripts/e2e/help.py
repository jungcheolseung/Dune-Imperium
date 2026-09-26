"""E2E of the help panel and of what a screen reader is told (2026-09-21).

Before this, the client had no live region at all, so neither a change of turn
nor an error was ever read out; icon-only controls (the review bar's ⏮ ◀ ▶ ⏭,
the seat tokens) had no accessible name; and no legend explained an icon
anywhere. A friend's first game (M14) is where that costs the most.

The legend check is a cross-check rather than a re-run of the renderer: every
icon actually drawn on the seat panels and in the hand must have a row in the
legend, so an icon added to the table without a legend row fails here.
"""

from __future__ import annotations

from common import (
    LAPTOP_VIEWPORT,
    SERVER_LOG_COPY,
    Check,
    chrome,
    client_state,
    open_context,
    server,
)
from open_mode import create_game, settled

check = Check()

# What the Hangul IME sends for Shift+/ : the key is "?" and the code "Slash".
QUESTION = (
    "document.dispatchEvent(new KeyboardEvent('keydown',"
    " {key: '?', code: 'Slash', shiftKey: true, bubbles: true}))"
)


def announced(page) -> str:
    return page.evaluate("document.getElementById('announcer').textContent")


def live_region(page) -> None:
    print("[1] the live region follows the turn")
    region = page.evaluate(
        """() => {
            const r = document.getElementById('announcer');
            if (!r) return null;
            const style = getComputedStyle(r);
            return {
                live: r.getAttribute('aria-live'),
                atomic: r.getAttribute('aria-atomic'),
                display: style.display,
                width: r.getBoundingClientRect().width,
            };
        }"""
    )
    check.ok(
        region is not None
        and region["live"] == "polite"
        and region["atomic"] == "true",
        "a polite, atomic live region exists",
        region,
    )
    # display:none would hide it from screen readers as well as from the eye.
    check.ok(
        region is not None and region["display"] != "none" and region["width"] <= 1,
        "it is visually hidden, not display:none",
        region,
    )
    if region is None:
        return
    page.wait_for_function(
        "document.getElementById('announcer').textContent !== ''", timeout=3000
    )
    owner = page.evaluate("state.summary.decision.owner")
    label = page.evaluate(f"playerLabel({owner})")
    check.ok(
        label in announced(page), "it names the seat to act on arrival", announced(page)
    )

    # Record every sentence handed to the region, in order. announce is a
    # global function of a classic script, so callers pick up the wrapper.
    page.evaluate(
        """() => {
            window.__said = [];
            const original = window.announce;
            window.announce = (text) => { window.__said.push(text); original(text); };
        }"""
    )
    # Step on until a turn has been held for its confirmation and handed over.
    # While it is held, decision.owner already names the NEXT seat; the region
    # must speak of the confirmation, and then of the next seat once confirmed.
    wrong = []
    held = handed = False
    for _ in range(150):
        snap = client_state(page)
        confirming = snap["confirmation"] is not None
        page.evaluate("confirmTurn()" if confirming else "applyAction(0)")
        settled(page)
        page.wait_for_timeout(120)  # announce() writes after 50 ms
        now_state = page.evaluate(
            """() => {
                const s = state.summary;
                const c = typeof s.confirmation === 'number' ? s.confirmation : null;
                return {
                    confirmation: c,
                    confirmLabel: c === null ? null : playerLabel(c),
                    owner: s.decision ? s.decision.owner : null,
                    ownerLabel: s.decision ? playerLabel(s.decision.owner) : null,
                    said: window.__said.slice(),
                };
            }"""
        )
        said = now_state["said"]
        last = said[-1] if said else ""
        if now_state["confirmation"] is not None:
            if not (now_state["confirmLabel"] in last and "턴 종료" in last):
                wrong.append(("held", now_state["confirmLabel"], last))
            held = True
        elif confirming and now_state["ownerLabel"]:
            # This step was the confirm itself: the hand-over must be said.
            if not (
                now_state["ownerLabel"] in last
                and "턴 종료" not in last
                and len(said) >= 2
                and "턴 종료" in said[-2]
            ):
                wrong.append(("handed", now_state["ownerLabel"], said[-2:]))
            handed = True
        if held and handed:
            break
    check.ok(
        held and handed, "the walk saw a turn held for confirmation and handed over"
    )
    check.ok(
        not wrong,
        "a held turn is announced as held, and its hand-over as the next seat's turn",
        wrong[:3],
    )


def names(page) -> None:
    print("[2] roles and names")
    roles = page.evaluate(
        """() => ({
            gameError: document.getElementById('game-error').getAttribute('role'),
            setupError: document.getElementById('setup-error').getAttribute('role'),
            lobbyError: document.getElementById('lobby-error').getAttribute('role'),
            connection: document.getElementById('connection-note').getAttribute('role'),
            review: ['review-first', 'review-prev', 'review-next', 'review-last',
                     'review-slider']
                .map((id) => document.getElementById(id).getAttribute('aria-label')),
            seatMarks: [...document.querySelectorAll('#seats .seat-mark')]
                .map((m) => [m.getAttribute('role'), m.getAttribute('aria-label')]),
        })"""
    )
    check.ok(
        roles["gameError"] == roles["setupError"] == roles["lobbyError"] == "alert",
        "error lines are alerts",
        roles,
    )
    check.ok(roles["connection"] == "status", "the connection note is a status")
    check.ok(
        all(roles["review"]),
        "the review bar's icon buttons have names",
        roles["review"],
    )
    check.ok(
        len(roles["seatMarks"]) == 4
        and all(
            role == "img" and label == f"좌석 {seat}"
            for seat, (role, label) in enumerate(roles["seatMarks"])
        ),
        "seat tokens are named images",
        roles["seatMarks"],
    )


def help_panel(page) -> None:
    print("[3] the help panel")
    page.focus("#save-game")
    page.evaluate(QUESTION)
    shown = page.evaluate(
        """() => {
            const panel = document.getElementById('help');
            const body = document.getElementById('help-body');
            return {
                open: panel && !panel.hidden,
                role: body && body.getAttribute('role'),
                modal: body && body.getAttribute('aria-modal'),
                labelled: body && !!document.getElementById(
                    body.getAttribute('aria-labelledby')),
                focusInside: body && body.contains(document.activeElement),
            };
        }"""
    )
    check.ok(
        bool(shown["open"]), "? (as the Hangul IME sends it) opens the help", shown
    )
    check.ok(
        shown["role"] == "dialog" and shown["modal"] == "true" and shown["labelled"],
        "it is a labelled modal dialog",
        shown,
    )
    check.ok(bool(shown["focusInside"]), "focus moves into it")
    if not shown["open"]:
        return  # nothing below can be looked at

    agents = page.evaluate(
        """() => {
            const read = (node) => node && ({
                tag: node.tagName.toLowerCase(),
                viewBox: node.getAttribute('viewBox'),
                path: node.querySelector('path')?.getAttribute('d'),
                image: node.querySelector('image')?.getAttribute('href') || null,
            });
            return {
                status: read(document.querySelector('#seats .stat .agent-piece-icon')),
                help: read(document.querySelector(
                    '#help-body .agent-piece-icon[data-term="agent"]')),
                boardPath: PIECE_SHAPES.agent.outline,
            };
        }"""
    )
    check.ok(
        agents["status"] is not None
        and agents["status"] == agents["help"]
        and agents["status"]["tag"] == "svg"
        and agents["status"]["viewBox"] == "0 0 52 81"
        and agents["status"]["path"] == agents["boardPath"]
        and agents["status"]["image"] is None,
        "status and help use the plain Agent piece, not the +Agent image",
        agents,
    )
    # The Icon Guide's +Agent figure means gaining an Agent; no ordinary
    # mention (card text, Conflict chip, turn line) draws it any more.
    plus = page.evaluate(
        """() => [...document.querySelectorAll('img.icon')]
            .filter((img) => img.getAttribute('src') === state.catalog.icons.agent)
            .map((img) => img.title)"""
    )
    check.ok(not plus, "no +Agent image anywhere on the page", plus[:5])

    legend = page.evaluate(
        """() => {
            const drawn = new Set();
            const where = '#seats img.icon, #private-zone img.icon';
            for (const img of document.querySelectorAll(where)) {
                drawn.add(img.getAttribute('src'));
            }
            const explained = new Map();
            for (const img of document.querySelectorAll('#help-body img.icon')) {
                explained.set(img.getAttribute('src'),
                              img.closest('.help-mark').nextElementSibling.textContent);
            }
            return {
                drawn: [...drawn],
                missing: [...drawn].filter((src) => !explained.has(src)),
                rows: explained.size,
                text: document.getElementById('help-body').textContent,
            };
        }"""
    )
    check.ok(
        len(legend["drawn"]) >= 8 and not legend["missing"],
        "every icon drawn on the seats and in the hand has a legend row",
        (len(legend["drawn"]), legend["missing"]),
    )
    for want in ("C2", "시작", "시작 플레이어 마커", "사다우카 지휘관"):
        check.ok(want in legend["text"], f"the seat marks explain {want}")
    for key in ("c", "s", "Esc", "?"):
        check.ok(
            page.evaluate(
                "(key) => [...document.querySelectorAll('#help-body kbd')]"
                ".some((k) => k.textContent === key)",
                key,
            ),
            f"the shortcut {key} is listed",
        )

    # While it is open, the other shortcuts stay quiet.
    folded = page.evaluate("collapsedStrips.size")
    page.evaluate(
        "document.dispatchEvent(new KeyboardEvent('keydown',"
        " {key: 'ㅊ', code: 'KeyC', bubbles: true}))"
    )
    check.ok(
        page.evaluate("collapsedStrips.size") == folded,
        "c does nothing behind the open help",
    )

    page.keyboard.press("Escape")
    check.ok(
        page.evaluate("document.getElementById('help').hidden"), "Escape closes it"
    )
    check.ok(
        page.evaluate("document.activeElement.id === 'save-game'"),
        "focus goes back where it was",
    )

    page.click("#open-help")
    check.ok(
        page.evaluate("!document.getElementById('help').hidden"),
        "the header button opens it too",
    )
    page.mouse.click(5, 5)
    check.ok(
        page.evaluate("document.getElementById('help').hidden"),
        "a click on the backdrop closes it",
    )

    # A "?" typed into a field is a character, not the help.
    page.evaluate(
        """() => {
            const input = document.createElement('input');
            input.id = 'scratch-input';
            document.body.appendChild(input);
            input.focus();
            input.dispatchEvent(new KeyboardEvent('keydown',
                {key: '?', code: 'Slash', shiftKey: true, bubbles: true}));
        }"""
    )
    check.ok(
        page.evaluate("document.getElementById('help').hidden"),
        "? typed into a field does not open it",
    )
    page.evaluate("document.getElementById('scratch-input').remove()")


# The turn walkthrough (ITEM 8e): it used to be the last section openHelp
# built, so on a laptop it sat below the fold -- offsetTop 752 in a 689px
# #help-body at 1366x768, with the last line cut at 1440x900. It is now the
# first section after the panel heading, so it must fit unscrolled here.
FIT_JS = """() => {
    const body = document.getElementById('help-body');
    const list = document.querySelector('#help-body ul.help-turn');
    const heading = list ? list.previousElementSibling : null;
    const firstGrid = document.querySelector('#help-body .help-grid');
    const bodyBox = body.getBoundingClientRect();
    const listBox = list ? list.getBoundingClientRect() : null;
    return {
        clientHeight: body.clientHeight,
        scrollTop: body.scrollTop,
        headingTag: heading ? heading.tagName : null,
        listBottom: listBox ? listBox.bottom - bodyBox.top + body.scrollTop : null,
        itemCount: list ? list.children.length : 0,
        turnBeforeIcons: !!(
            list && firstGrid &&
            (list.compareDocumentPosition(firstGrid) & Node.DOCUMENT_POSITION_FOLLOWING)
        ),
    };
}"""


def help_fits_laptop(page) -> None:
    print("[4] the turn walkthrough fits a laptop screen")
    page.set_viewport_size(LAPTOP_VIEWPORT)
    where = f"{LAPTOP_VIEWPORT['width']}x{LAPTOP_VIEWPORT['height']}"
    for language in ("ko", "en"):
        if page.evaluate("TERM_LANGUAGE") != language:
            page.click("#language-toggle")
            page.wait_for_function(f"TERM_LANGUAGE === '{language}'")
        page.click("#open-help")
        page.wait_for_selector("#help:not([hidden])")
        g = page.evaluate(FIT_JS)
        label = f"{where} {language}"
        check.ok(
            g["headingTag"] == "H3" and g["itemCount"] > 0,
            f"{label}: the turn walkthrough heading and list are present",
            g,
        )
        check.ok(g["scrollTop"] == 0, f"{label}: the panel opens unscrolled", g["scrollTop"])
        check.ok(
            g["listBottom"] is not None and g["listBottom"] <= g["clientHeight"] + 0.5,
            f"{label}: the whole turn walkthrough is inside the visible help body",
            g,
        )
        check.ok(
            g["turnBeforeIcons"],
            f"{label}: the turn walkthrough comes before the icon legend",
            g,
        )
        page.keyboard.press("Escape")
        page.wait_for_function("document.getElementById('help').hidden")


def run(base: str, browser) -> None:
    context, page, rec = open_context(browser, "help")
    create_game(page, base, humans=(0, 1))
    live_region(page)
    names(page)
    help_panel(page)
    help_fits_laptop(page)
    bad = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not bad, "no failed requests", bad[:3])
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    if check.failed:
        rec.dump()
    context.close()


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            run(base, browser)
        errors = [
            line
            for line in log_path.read_text().splitlines()
            if "ERROR" in line or "Traceback" in line
        ]
        check.ok(not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3])
        SERVER_LOG_COPY.write_text(log_path.read_text())
    check.finish()


if __name__ == "__main__":
    main()
