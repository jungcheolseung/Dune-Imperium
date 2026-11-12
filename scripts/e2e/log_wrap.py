"""Log text and icons must wrap as one sentence, not separate flex columns.

Reproduces the user's Family Atomics / Tuek's Sietch screenshot through the
real turnLine renderer. Character rectangles check reading order independently
of the renderer's DOM structure; a later fragment must not jump up a line.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from common import Check, chrome, open_context, server

check = Check()
shots = Path(os.environ.get("E2E_SHOTS_DIR", tempfile.mkdtemp(prefix="dune-log-wrap-")))

PROBE = """({width, language, thumbnail}) => {
    setLanguage(language, false);
    document.body.classList.add('in-game');
    document.getElementById('wrap-probe')?.remove();
    const host = document.createElement('section');
    host.id = 'wrap-probe';
    Object.assign(host.style, {
        position: 'fixed', left: '12px', top: '12px', zIndex: '9999',
        width: `${width}px`, fontSize: '0.8rem', background: 'var(--panel)',
    });
    const card = document.createElement('div');
    card.className = 'turn-card';
    card.style.borderLeftColor = SEAT_COLORS[3];
    const body = document.createElement('div');
    body.className = 'turn-body';
    const lines = document.createElement('div');
    lines.className = 'turn-lines';
    for (const [index, action_id, events] of [
        [15, 'use_family_atomics', [
            {kind: 'family_atomics_used', payload: {player: 3}},
        ]],
        [16, 'place_leader_bonus_spice', []],
        [17, 'decline_skill', []],
    ]) lines.appendChild(turnLine({index, action_id, arguments: {}, events}));
    body.appendChild(lines);
    if (thumbnail) {
        const cards = document.createElement('div');
        cards.className = 'turn-cards';
        cards.appendChild(visualCard(Object.keys(state.catalog.cards)[0],
            {className: 'small'}));
        body.appendChild(cards);
    }
    card.appendChild(body);
    host.appendChild(card);
    document.body.appendChild(host);
}"""

GEOMETRY = """() => {
    const host = document.getElementById('wrap-probe');
    const problems = [];
    let measured = 0;
    const rangeBox = (node, start, end) => {
        const range = document.createRange();
        range.setStart(node, start);
        range.setEnd(node, end);
        return [...range.getClientRects()].filter(r => r.width && r.height);
    };
    const rows = [...host.querySelectorAll('.turn-line-head, .logevent')];
    const words = TERM_LANGUAGE === 'ko'
        ? ['임페리움 열', '플레이어4', '보너스', '채우기']
        : ['Imperium Row', 'Family', 'Bonus'];
    const wordRects = [];
    for (const row of rows) {
        const walker = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
        let previous = null;
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
            if (node.parentElement.closest('.turn-index')) continue;
            const text = node.textContent;
            for (let i = 0; i < text.length; i++) {
                if (/\\s/.test(text[i])) continue;
                const rect = rangeBox(node, i, i + 1)[0];
                if (!rect) continue;
                measured++;
                if (previous && (rect.top < previous.top - 3 ||
                    (Math.abs(rect.top - previous.top) < 3 &&
                     rect.left < previous.left - 1))) {
                    problems.push({text, character: text[i],
                        previous: [previous.left, previous.top],
                        current: [rect.left, rect.top]});
                }
                previous = rect;
            }
            for (const word of words) {
                const start = text.indexOf(word);
                if (start >= 0) wordRects.push({word,
                    rows: rangeBox(node, start, start + word.length).length});
            }
        }
    }
    const overflows = rows.filter(r => r.scrollWidth > r.clientWidth + 1);
    const tuek = rows[2];
    const ring = tuek.querySelectorAll('.icon')[1]?.getBoundingClientRect();
    const parens = [];
    const walker = document.createTreeWalker(tuek, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        for (let i = 0; i < node.textContent.length; i++) {
            if ('()'.includes(node.textContent[i])) {
                const rect = rangeBox(node, i, i + 1)[0];
                if (rect) parens.push(rect);
            }
        }
    }
    return {measured, problems, wordRects, overflows: overflows.length,
        groupedRing: Boolean(ring) && parens.length === 2 &&
            parens.every(r => r.top < ring.bottom && r.bottom > ring.top)};
}"""


def main() -> None:
    shots.mkdir(parents=True, exist_ok=True)
    with server() as (base, _log), chrome() as browser:
        context, page, _rec = open_context(browser, "log-wrap")
        page.goto(base)
        page.wait_for_function("state.catalog !== null")
        for language in ("ko", "en"):
            for width, thumbnail in (
                (240, False), (300, False), (430, False),
                (240, True), (300, True), (430, True),
            ):
                page.evaluate(PROBE, {
                    "width": width, "language": language, "thumbnail": thumbnail,
                })
                page.wait_for_function("""() =>
                    [...document.querySelectorAll('#wrap-probe img')]
                        .every(img => img.complete && img.naturalWidth > 0)
                """)
                g = page.evaluate(GEOMETRY)
                suffix = "_card" if thumbnail else ""
                where = f"{language} {width}px{suffix}"
                check.ok(
                    g["measured"] > 30 and not g["problems"],
                    f"{where}: text reads left to right, then moves down",
                    g["problems"][:3],
                )
                check.ok(
                    len(g["wordRects"]) >= 3
                    and all(w["rows"] == 1 for w in g["wordRects"]),
                    f"{where}: words and named terms stay together",
                    g["wordRects"],
                )
                check.ok(
                    g["groupedRing"],
                    f"{where}: the Signet Ring icon stays inside its parentheses",
                )
                check.ok(not g["overflows"], f"{where}: text stays inside the log")
                page.locator("#wrap-probe").screenshot(
                    path=str(shots / f"log_wrap_{language}_{width}{suffix}.png")
                )
        context.close()
    print(f"Screenshots: {shots}")
    check.finish()


if __name__ == "__main__":
    main()
