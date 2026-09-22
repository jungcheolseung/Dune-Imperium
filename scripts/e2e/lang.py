"""E2E of the language switch (2026-09-21).

The client speaks Korean or English, never a mix (user decision 2026-09-20).
Card, Leader, space, Conflict and Contract names and printed card text are
English in both, so in English the page must carry no Hangul at all — the one
exception is the switch itself, which names the other language in that
language. Every surface is walked in English: the live table after a few
steps, the help panel, a finished game's review and standings, the setup
screen. Then Korean must come back exactly as it was, the choice must survive
a reload, and in Korean the engine's English prompts must be translated.

Seats are all human or heuristic here, so no player name (someone else's
input, which may be Korean) is on screen.
"""

from __future__ import annotations

from common import SERVER_LOG_COPY, Check, chrome, client_state, open_context, server
from log_words import KOREAN_KEEPS_ENGLISH
from open_mode import settled

check = Check()

SEED = 7
EXPANSIONS = ("choam", "bloodlines", "tech", "immortality", "promo")

# Every Hangul run on the page: visible text and the attributes a person or a
# screen reader meets (title, alt, aria-label, placeholder), with where it is.
HANGUL_JS = """() => {
    const hangul = /[\\uac00-\\ud7a3]+/g;
    const found = [];
    const note = (text, where) => {
        for (const match of String(text || '').matchAll(hangul)) {
            found.push([match[0], where]);
        }
    };
    const toggle = document.getElementById('language-toggle');
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const host = node.parentElement;
        if (!host || host === toggle || host.closest('[hidden]')) continue;
        if (getComputedStyle(host).display === 'none') continue;
        note(node.textContent, host.id || host.className || host.tagName);
    }
    const named = '[title], [alt], [aria-label], [placeholder]';
    for (const el of document.querySelectorAll(named)) {
        if (el === toggle) continue;
        for (const name of ['title', 'alt', 'aria-label', 'placeholder']) {
            if (!el.hasAttribute(name)) continue;
            note(el.getAttribute(name), `${el.id || el.tagName}@${name}`);
        }
    }
    note(document.title, 'document.title');
    return found;
}"""


# The text of the main surfaces, to compare one position in two moments.
SNAPSHOT_JS = """() => Object.fromEntries(
    ['header-status', 'decision-banner', 'seats', 'market', 'private-zone',
     'action-log', 'setup-screen']
        .map((id) => [id, document.getElementById(id).innerText])
)"""


# In Korean, the chrome that carries no names — the header and review status,
# the column titles, the standings header, the seat stats' titles and the seat
# detail line names — must not show a rule term's English word (TERMS[x].en).
ENGLISH_TERMS_JS = r"""() => {
    const words = [...new Set(Object.values(TERMS).map((term) => term.en))]
        .sort((a, b) => b.length - a.length);
    const hit = (text) => {
        const lower = text.toLowerCase();
        for (const word of words) {
            const at = lower.indexOf(word.toLowerCase());
            if (at < 0) continue;
            const before = at === 0 ? " " : lower[at - 1];
            const after = lower[at + word.length] || " ";
            if (!/[a-z]/.test(before) && !/[a-z]/.test(after)) return word;
        }
        return null;
    };
    const texts = [];
    const add = (where, text) => { if (text) texts.push([where, text]); };
    add("header-status", document.getElementById("header-status").textContent);
    add("review-status", document.getElementById("review-status").textContent);
    const all = (selector) => [...document.querySelectorAll(selector)];
    for (const h of all("#market .strip h3")) add("strip", h.textContent);
    for (const th of all("#standings th")) add("standings", th.textContent);
    for (const stat of all("#seats .stat[title]")) add("stat", stat.title);
    for (const s of document.querySelectorAll("#seats .seat-detail strong")) {
        add("seat line", s.textContent);
    }
    return texts
        .map(([where, text]) => [where, text, hit(text)])
        .filter(([, , word]) => word);
}"""


# In Korean, every English word a person or a screen reader meets (text,
# title, alt, aria-label, placeholder) must be a name or printed card text:
# every catalog string is stripped (card, Leader, space, Conflict, Contract
# names and printed text stay English by policy), and so is iconized card
# wording (.card-text, whose icons' tooltips are checked) and the help
# legend's muted English twins. What is left must be empty. The name-free
# check above missed "· seed … · CHOAM · Bloodlines" in the header, the
# Alliance and troop tooltips and "Family Atomics" (2026-09-22).
KOREAN_LATIN_JS = r"""({keep}) => {
    const names = new Set(keep);
    const walk = (value) => {
        if (typeof value === 'string') {
            if (/[A-Za-z]{2}/.test(value) && !value.includes('/')) names.add(value);
        } else if (Array.isArray(value)) {
            value.forEach(walk);
        } else if (value && typeof value === 'object') {
            Object.values(value).forEach(walk);
        }
    };
    walk(state.catalog);
    const sorted = [...names].sort((a, b) => b.length - a.length);
    const left = (text) => {
        let bare = String(text || '').replace(/\S*\/\S*|OQ-\d+/g, ' ');
        if (!/[A-Za-z]{2}/.test(bare)) return [];
        for (const name of sorted) {
            if (bare.includes(name)) bare = bare.split(name).join(' ');
        }
        return bare.match(/[A-Za-z]{2,}/g) || [];
    };
    const skip = '#language-toggle, .card-text, kbd, code, #help-body .muted';
    const found = [];
    const note = (text, where) => {
        const words = left(text);
        if (words.length) found.push([words.join(' '), String(text).slice(0, 80), where]);
    };
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const host = node.parentElement;
        if (!host || host.closest('[hidden]') || host.closest(skip)) continue;
        if (getComputedStyle(host).display === 'none') continue;
        note(node.textContent, host.id || host.className || host.tagName);
    }
    const named = '[title], [alt], [aria-label], [placeholder]';
    for (const el of document.querySelectorAll(named)) {
        if (el.closest('#language-toggle') || el.closest('[hidden]')) continue;
        for (const name of ['title', 'alt', 'aria-label', 'placeholder']) {
            if (!el.hasAttribute(name)) continue;
            const where = el.id || String(el.className.baseVal ?? el.className) || el.tagName;
            note(el.getAttribute(name), `${where}@${name}`);
        }
    }
    note(document.title, 'document.title');
    const seen = new Set();
    return found.filter(([words, text]) => {
        const key = words + '|' + text;
        return seen.has(key) ? false : (seen.add(key), true);
    });
}"""

# Chrome English on purpose: the product title (the user has not asked for
# the Korean edition's title), the uv extra the checkpoint field needs, the
# AI of the seat kinds, the Esc key the turn guide names, and Shaddam, a
# Leader's short name like log_words' Feyd.
KOREAN_CHROME_ENGLISH = ("Dune: Imperium — Uprising", "train extra", "AI", "Esc", "Shaddam")


def hangul(page) -> list:
    return page.evaluate(HANGUL_JS)


def english_left(page) -> list:
    keep = [*KOREAN_KEEPS_ENGLISH, *KOREAN_CHROME_ENGLISH]
    return page.evaluate(KOREAN_LATIN_JS, {"keep": keep})


def create(page, base: str, seats: tuple[str, str, str, str]) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat, kind in enumerate(seats):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", kind)
    for option in EXPANSIONS:
        page.check(f"#opt-{option}")
    page.fill("#opt-seed", str(SEED))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")


def switch(page, lang: str) -> None:
    if page.evaluate("TERM_LANGUAGE") != lang:
        page.click("#language-toggle")
    page.wait_for_function("(lang) => document.documentElement.lang === lang", arg=lang)
    settled(page)


def live_table(base: str, browser) -> None:
    print("[1] the live table")
    context, page, rec = open_context(browser, "lang-live")
    create(page, base, ("human", "human", "heuristic", "heuristic"))
    check.ok(page.is_visible("#language-toggle"), "the switch is on the page")
    check.ok(page.evaluate("TERM_LANGUAGE") == "ko", "Korean is the default")
    left = english_left(page)
    check.ok(not left, "Korean: no English outside names on the new table", left[:8])

    # In Korean the engine's English prompt is translated.
    prompt = page.evaluate("state.summary.decision.prompt")
    shown = page.inner_text("#decision-info .prompt")
    check.ok(
        prompt not in shown and bool(hangul(page)),
        "in Korean the engine's prompt is shown in Korean",
        (prompt, shown),
    )
    # A round trip at one position must give back exactly the Korean it left.
    before = page.evaluate(SNAPSHOT_JS)
    switch(page, "en")
    switch(page, "ko")
    after = page.evaluate(SNAPSHOT_JS)
    changed = [name for name in before if before[name] != after[name]]
    check.ok(not changed, "Korean → English → Korean gives back the same page", changed)

    switch(page, "en")
    stray = hangul(page)
    check.ok(not stray, "English: no Hangul on the live table", stray[:8])
    check.ok(
        page.inner_text("#decision-info .prompt").strip() == prompt,
        "English: the engine's prompt is shown as sent",
        page.inner_text("#decision-info .prompt"),
    )

    # A few steps in English: new log lines, prompts and panels.
    for _ in range(12):
        snap = client_state(page)
        if snap["finished"]:
            break
        page.evaluate(
            "confirmTurn()" if snap["confirmation"] is not None else "applyAction(0)"
        )
        settled(page)
    stray = hangul(page)
    check.ok(not stray, "English: still no Hangul after a dozen steps", stray[:8])

    page.click("#open-help")
    stray = hangul(page)
    check.ok(not stray, "English: no Hangul in the help panel", stray[:8])
    page.keyboard.press("Escape")

    page.reload()
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    check.ok(
        page.evaluate("TERM_LANGUAGE") == "en"
        and page.evaluate("document.documentElement.lang") == "en",
        "the choice survives a reload",
    )
    stray = hangul(page)
    check.ok(not stray, "English after the reload: no Hangul", stray[:8])

    switch(page, "ko")
    check.ok(
        page.inner_text("#language-toggle").strip() == "English",
        "the switch offers English again",
    )
    check.ok(bool(hangul(page)), "Korean comes back")
    left = english_left(page)
    check.ok(not left, "Korean: no English outside names after a dozen steps", left[:8])
    page.click("#open-help")
    left = english_left(page)
    check.ok(not left, "Korean: no English outside names in the help panel", left[:8])
    page.keyboard.press("Escape")
    check.ok(
        page.evaluate("ACTION_LABELS.pick_leader") == page.evaluate(
            "LABELS_KO.ACTION_LABELS.pick_leader"
        ),
        "the label tables are Korean again",
    )

    bad = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not bad, "no failed requests", bad[:3])
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    if check.failed:
        rec.dump()
    context.close()


def finished_game(base: str, browser) -> None:
    print("[2] a finished game, its review and the setup screen")
    context, page, rec = open_context(browser, "lang-finished")
    create(page, base, ("heuristic",) * 4)
    page.wait_for_function("state.review !== null && state.view !== null")
    switch(page, "en")
    page.evaluate("stopPlayback(); reviewSeek(state.review.meta.step_count)")
    page.wait_for_function(
        "state.review.cursor === state.review.meta.step_count && refreshFlight === null"
    )
    page.wait_for_function(
        "document.getElementById('review-status').textContent !== ''"
    )
    stray = hangul(page)
    check.ok(not stray, "English: no Hangul at the end of a review", stray[:8])
    switch(page, "ko")
    english = page.evaluate(ENGLISH_TERMS_JS)
    check.ok(
        not english,
        "Korean: no rule term left in English in the name-free chrome",
        english[:6],
    )
    # No wait: the switch rewrites the review's status line at once (it read
    # "step 832/832 · Round 10 · Game Over" until the re-fetch landed).
    left = english_left(page)
    check.ok(not left, "Korean: no English outside names at the end of a review", left[:8])
    switch(page, "en")
    check.ok(page.is_visible("#standings"), "the standings are on screen")
    page.click("#disclosure h2 button")
    stray = hangul(page)
    check.ok(not stray, "English: no Hangul in the opened disclosure", stray[:8])

    page.evaluate("exitReview()")
    page.wait_for_function("state.review === null && refreshFlight === null")
    stray = hangul(page)
    check.ok(not stray, "English: no Hangul on the finished banner", stray[:8])

    page.click("#leave-game")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_selector("#game-list button")
    stray = hangul(page)
    check.ok(not stray, "English: no Hangul on the setup screen", stray[:8])

    bad = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not bad, "no failed requests", bad[:3])
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    if check.failed:
        rec.dump()
    context.close()


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            live_table(base, browser)
            finished_game(base, browser)
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
