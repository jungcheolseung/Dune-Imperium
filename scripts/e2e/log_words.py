"""E2E: the action log speaks words, not engine ids (2026-09-21).

An inventory of 19 finished all-AI games (every expansion mix, heuristic and
random seats) found the log printing the engine's own strings in 277 places:
a chance line read `chance: Round:2:Player:0:Discard Shuffle`, an action head
`Count: 2` or `Arrakis Hagga Basin` (a post id), a payload
`Skill:Desperate:0`, `mid_trash` (a Feyd track space), `c2r2` (a research
space) or a comma list of card instance ids. They came through prettify() —
the last resort for an id no table knows — or were printed as they came.

This renders every entry of a few finished games with the page's own
functions (turnLine, logEventLine, chanceLine, describeReviewStep) in both
languages, with prettify() wrapped, and asserts:

- prettify() is never called: every id resolves through a table;
- in Korean, no Latin word is left outside catalog names (proper nouns stay
  English by policy) and the phrases the glossary deliberately leaves English
  (docs/rules/glossary-ko.md has no row for them, e.g. Secret Project);
- in English, no Hangul, and nowhere an engine id's shape: snake_case, a
  colon path, a research coordinate, a post id.

Then the whole game screen at the end of the review, in both languages, with
its titles (a Spy's post read `Arrakis Hagga Basin`, a research hex `c2r2`),
holds no engine id either. The games must still reach the surfaces this
guards, or the check says so instead of passing on an empty corpus.
"""

from __future__ import annotations

import re

from common import SERVER_LOG_COPY, Check, chrome, open_context, server

check = Check()

EVERY_EXPANSION = {
    "choam_module": True,
    "bloodlines": True,
    "tech_module": True,
    "immortality": True,
    "promo_cards": True,
}
GAMES = (
    {"seats": ["heuristic"] * 4, "game_seed": 7, **EVERY_EXPANSION},
    # Random seats wander into what a heuristic never picks (Family Atomics,
    # the Feyd track, Secrets' random steal, an exchanged Influence).
    {"seats": ["random"] * 4, "game_seed": 25, "policy_seed": 25, **EVERY_EXPANSION},
    # Seed 47 (30 until the 2026-09-26 card-transcription audit, then 38
    # until OQ-070's Commander deploy slot moved that game off its Secrets
    # steal): Family Atomics, the Feyd track and research, and the only one
    # of the four with a Secrets steal.
    {"seats": ["random"] * 4, "game_seed": 47, "policy_seed": 47, **EVERY_EXPANSION},
    {
        "seats": ["random"] * 4,
        "game_seed": 23,
        "policy_seed": 23,
        "leader_draft": True,
        **EVERY_EXPANSION,
    },
)

# English on purpose in the Korean page: the glossary has no Korean for these
# yet (docs/rules/glossary-ko.md, "아직 채우지 않은 것"), or they are a
# Leader's name. Whole phrases, so a stray "card" or "set" is still caught.
# tests/server/test_i18n.py keeps the same list for the tables' Korean.
KOREAN_KEEPS_ENGLISH = (
    "Other Memories",
    "Memories returned",
    "Memories",
    "Secret Project",
    "Wild card",
    "Immediate",
    "Usurp",
    "Feyd",
    # A Leader's ability, named on the Leader card.
    "Into the Fray",
    "Fedaykin Maneuver",
)

RENDER_JS = r"""
async ({gameId}) => {
  const meta = await api(`/games/${gameId}/review?seat=0`);
  const out = [];
  const calls = [];
  const realPrettify = window.prettify;
  window.prettify = (id) => { calls.push(String(id)); return realPrettify(id); };
  const take = () => calls.splice(0, calls.length);
  const events = (lang, entry) => {
    for (const event of entry.events || []) {
      for (const [key, value] of Object.entries(event.payload)) {
        take();
        const text = logEventPayload({[key]: value});
        out.push({lang, src: `payload ${event.kind}.${key}`, value, text,
                  pretty: take()});
      }
      take();
      out.push({lang, src: `event ${event.kind}`, text: logEventLine(event).textContent,
                pretty: take()});
    }
  };
  try {
    for (const lang of ["ko", "en"]) {
      setLanguage(lang, false);
      for (const entry of meta.log) {
        if (entry.type === "chance") {
          take();
          const label = {type: "chance", decision_id: entry.decision_id,
                         values: entry.values || []};
          const text =
            chanceLine(entry).textContent + " | " + describeReviewStep(label);
          out.push({lang, src: `chance ${entry.decision_id}`, text, pretty: take()});
          events(lang, entry);
        } else if (entry.type === "action") {
          take();
          const text = turnLine({...entry, events: []}).textContent;
          out.push({lang, src: `action ${entry.action_id}`, text, pretty: take(),
                    args: entry.arguments});
          events(lang, entry);
        }
      }
    }
  } finally {
    window.prettify = realPrettify;
    setLanguage("ko", false);
  }
  const names = new Set();
  for (const table of Object.values(state.catalog)) {
    if (!table || typeof table !== "object") continue;
    for (const entry of Object.values(table)) {
      if (entry && typeof entry.name === "string") names.add(entry.name);
    }
  }
  return {out, names: [...names], posts: Object.keys(state.catalog.posts)};
}
"""

# Text and the attributes a person or a screen reader meets, on the game screen.
PAGE_TEXT_JS = """() => {
    const found = [];
    const screen = document.getElementById('game-screen');
    const walker = document.createTreeWalker(screen, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const host = node.parentElement;
        if (!host || host.closest('[hidden]')) continue;
        found.push([node.textContent, host.id || host.className || host.tagName]);
    }
    for (const el of screen.querySelectorAll('[title], [alt], [aria-label]')) {
        for (const name of ['title', 'alt', 'aria-label']) {
            if (el.hasAttribute(name)) {
                const where = `${el.className || el.tagName}@${name}`;
                found.push([el.getAttribute(name), where]);
            }
        }
    }
    return found;
}"""

SNAKE = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")
COLON_PATH = re.compile(r"\b[a-z]+(?::[a-z0-9_]+)+\b", re.I)
RESEARCH_ID = re.compile(r"\bc\d+r\d+\b")
HANGUL = re.compile(r"[가-힣]+")
LATIN = re.compile(r"[A-Za-z][A-Za-z'\-]*")


def engine_ids(text: str, posts: list[str]) -> list[str]:
    found = SNAKE.findall(text) + COLON_PATH.findall(text) + RESEARCH_ID.findall(text)
    # A post id as it came, or through prettify() ("Arrakis Hagga Basin").
    return found + [
        post
        for post in posts
        if post in text or post.replace("-", " ").title() in text
    ]


def strip(text: str, phrases: list[str]) -> str:
    for phrase in phrases:
        if phrase in text:
            text = text.replace(phrase, " ")
    return text


def render_games(page) -> tuple[list[dict], list[str], list[str], list[str]]:
    records: list[dict] = []
    names: set[str] = set()
    posts: list[str] = []
    game_ids: list[str] = []
    for config in GAMES:
        created = page.evaluate(
            """async (body) => {
              const r = await fetch('/games', {method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)});
              return {status: r.status, body: await r.json()};
            }""",
            config,
        )
        check.ok(created["status"] == 200, f"created {config['game_seed']}", created)
        if created["status"] != 200:
            continue
        game_id = created["body"]["game_id"]
        game_ids.append(game_id)
        result = page.evaluate(RENDER_JS, {"gameId": game_id})
        records.extend(result["out"])
        names.update(result["names"])
        posts = result["posts"]
    return records, sorted(names, key=len, reverse=True), posts, game_ids


def check_coverage(records: list[dict]) -> None:
    """The games still reach what this guards; otherwise it would pass empty."""
    sources = [r["src"] for r in records if r["lang"] == "ko"]
    wanted = {
        "a discard pile shuffle": lambda s: s.startswith("chance ")
        and s.endswith(":discard_shuffle"),
        "a post argument": lambda s: s.startswith("payload ") and s.endswith("post_id"),
        "a research space": lambda s: s == "payload research_advanced.space_id",
        "a Feyd track step": lambda s: s == "payload feyd_token_advanced.to_space",
        "a Skill instance": lambda s: s.endswith(".skill_instance_id"),
        "Family Atomics' removed cards": lambda s: s
        == "payload family_atomics_used.removed",
        "an exchanged Influence": lambda s: s == "action exchange_reveal_influence",
        "a Secrets steal": lambda s: s.startswith("chance ") and ":secrets:steal:" in s,
    }
    missing = [label for label, test in wanted.items() if not any(map(test, sources))]
    check.ok(not missing, "the games reach every surface this guards", missing)


def check_log(records, names, posts) -> None:
    pretty = [(r["src"], r["pretty"]) for r in records if r["pretty"]]
    check.ok(
        not pretty,
        "prettify() never reaches the log: every engine id resolves through a table",
        pretty[:4],
    )

    korean = [r for r in records if r["lang"] == "ko"]
    allowed = names + sorted(KOREAN_KEEPS_ENGLISH, key=len, reverse=True)
    latin = [
        (r["src"], words, r["text"][:90])
        for r in korean
        if (words := sorted(set(LATIN.findall(strip(r["text"], allowed)))))
    ]
    check.ok(
        not latin,
        "Korean log: no English outside names and the glossary's kept phrases",
        latin[:4],
    )

    english = [r for r in records if r["lang"] == "en"]
    hangul = [(r["src"], r["text"][:90]) for r in english if HANGUL.search(r["text"])]
    check.ok(not hangul, "English log: no Hangul", hangul[:4])
    for lang, rows in (("Korean", korean), ("English", english)):
        ids = [
            (r["src"], found, r["text"][:90])
            for r in rows
            if (found := engine_ids(strip(r["text"], names), posts))
        ]
        check.ok(not ids, f"{lang} log: no engine id's shape", ids[:4])


def check_page(page, base: str, game_id: str, posts: list[str], names) -> None:
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_function("state.review !== null && state.view !== null")
    page.evaluate("stopPlayback(); reviewSeek(state.review.meta.step_count)")
    page.wait_for_function(
        "state.review.cursor === state.review.meta.step_count"
        " && !playback.playing && refreshFlight === null"
    )
    # Folded seat detail is [hidden] and skipped below; open it (the research
    # flag there printed a coordinate, `c5r1`).
    page.evaluate(
        "if (!state.view.players.every((p) => expandedSeats.has(p.player)))"
        " toggleAllSeats()"
    )
    for lang in ("ko", "en"):
        page.evaluate(f"setLanguage('{lang}')")
        page.wait_for_function("refreshFlight === null")
        page.wait_for_timeout(300)
        texts = page.evaluate(PAGE_TEXT_JS)
        titled = [text for text, where in texts if "@title" in where]
        ids = [
            (where, found, text[:80])
            for text, where in texts
            if (found := engine_ids(strip(text, names), posts))
        ]
        check.ok(
            bool(titled) and not ids,
            f"{lang}: the finished game's screen, titles included, shows no engine id",
            ids[:4] or len(titled),
        )
    page.evaluate("setLanguage('ko')")


def main() -> None:
    with server() as (base, log_path), chrome() as browser:
        _, page, _rec = open_context(browser, "log-words")
        page.goto(base + "/")
        page.wait_for_function("state.catalog !== null")
        print(f"[1] render the logs of {len(GAMES)} finished games in both languages")
        records, names, posts, game_ids = render_games(page)
        print(f"  .. {len(records)} rendered lines")
        check_coverage(records)
        check_log(records, names, posts)
        print("[2] the whole screen at the end of the first game's review")
        if game_ids:
            check_page(page, base, game_ids[0], posts, names)
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
