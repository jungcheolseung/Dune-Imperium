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

from common import SERVER_LOG_COPY, Check, chrome, client_state, open_context, server
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

    # Step until the seat to act changes; the region must follow it.
    changes = 0
    for _ in range(80):
        before = page.evaluate("state.summary.decision && state.summary.decision.owner")
        snap = client_state(page)
        confirming = snap["confirmation"] is not None
        page.evaluate("confirmTurn()" if confirming else "applyAction(0)")
        settled(page)
        after = page.evaluate("state.summary.decision && state.summary.decision.owner")
        if after is None or after == before:
            continue
        label = page.evaluate(f"playerLabel({after})")
        try:
            page.wait_for_function(
                "(label) => document.getElementById('announcer')"
                ".textContent.includes(label)",
                arg=label,
                timeout=2000,
            )
        except Exception:
            pass
        check.ok(
            label in announced(page),
            f"a change of turn to {label} is announced",
            announced(page),
        )
        changes += 1
        if changes >= 2:
            break
    check.ok(changes >= 2, "the walk saw the turn change twice", changes)


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
    for want in ("C2", "1st", "시작 플레이어 마커", "사다우카 지휘관"):
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


def run(base: str, browser) -> None:
    context, page, rec = open_context(browser, "help")
    create_game(page, base, humans=(0, 1))
    live_region(page)
    names(page)
    help_panel(page)
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
