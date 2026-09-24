"""E2E for ITEM 8h: chained Combat/Endgame Intrigue passes fold into one log
card (panels.js logGroups/passesCard, 2026-09-25).

Bug this reproduces: a verified-decision sweep of finished all-AI games
found consecutive pass_combat_intrigue / pass_endgame_intrigue entries each
reading as their own full-weight turn card -- 14-19% of all log cards, 3-4
cards per round in a 448px log, and each card saying "pass" twice (the head
line from ACTION_LABELS plus the muted event line). The design folds a run
of chained passes of the same action_id into ONE compact .turn-card.passes:
the pass label once, then the passing seats in order.

The seat-order check below does NOT ask panels.js's own logGroups() what a
run is: a mutation that disables the fold-join branch (so every pass again
becomes its own one-seat card) or one that drops the "don't fold a pass that
closes the seat's own open card" guard both still pass a check built on
logGroups()'s own answer, because the check would just be re-deriving the
grouping from the same (broken) function. Instead, runs_of below walks the
raw log (state.review.meta.log) itself and decides independently which
consecutive pass_combat_intrigue / pass_endgame_intrigue entries chain into
one run, mirroring the same fold rule logGroups() documents for itself (see
its own comment in panels.js) rather than calling it. Matched the DOM's fold
cards exactly across five finished games (heuristic seeds 7 base/all-expansion
and 3 all-expansion, random seeds 25 base and 30 all-expansion): 70 runs, 52
of them multi-seat, 12 Endgame, and 25 passes that end a seat's own card.

A base-game and an all-expansion all-AI game (heuristic seats hold few
Intrigue cards, so most Combat/Endgame Intrigue windows end in a chain of
passes), both reviewed to the end, in both languages:

- for every run of consecutive foldable pass entries found by runs_of, there
  is exactly one .turn-card.passes whose seats, in DOM order, are exactly
  that run's actors, in order, with the same count;
- at least one fold holds two or more seats (a chain actually chained, not
  just a run of one-seat folds);
- no two DOM-adjacent fold cards (nothing else rendered between them) share
  an action_id (the shape a disabled join leaves: many one-seat folds of the
  same window back to back);
- the word for "pass" appears exactly once inside a fold card, not once per
  seat;
- no OTHER .turn-card (a seat's own turn) is left holding just a single pass
  line -- the old bug's shape;
- in Korean the card holds no stray Latin word (catalog names and the
  glossary's kept-English phrases aside); in English, no Hangul.

The games must actually reach chained passes, or this fails on an empty
corpus rather than passing vacuously.
"""

from __future__ import annotations

import re

from common import (
    RULE_OPTIONS,
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)

check = Check()

VIEWPORT = {"width": 1440, "height": 900}

# heuristic seed 7 with every expansion is the same game log_words.py already
# verified reaches a Combat/Endgame Intrigue pass (check_coverage there); the
# base game reuses it with every expansion box off.
GAMES = (
    {"label": "base game", "seed": 7, "expansions": ()},
    {"label": "all-expansion game", "seed": 7, "expansions": RULE_OPTIONS},
)

HANGUL = re.compile(r"[가-힣]")
LATIN = re.compile(r"[A-Za-z][A-Za-z'\-]*")
PASS_WORD = {"ko": "패스", "en": "Passed"}

# English on purpose in the Korean page (mirrors log_words.py's own list,
# docs/rules/glossary-ko.md, "아직 채우지 않은 것"): a stray Leader or card
# name is not what this check guards against.
KOREAN_KEEPS_ENGLISH = (
    "Other Memories",
    "Memories returned",
    "Memories",
    "Secret Project",
    "Wild card",
    "Immediate",
    "Usurp",
    "Feyd",
    "Into the Fray",
    "Fedaykin Maneuver",
)

# Mirrors PASS_ACTION_IDS (static/review.js) and QUIET_ACTIONS/SOLO_ACTIONS/
# PASS_MARKER_KINDS (static/panels.js) -- the same engine action/event ids
# logGroups() itself keys its fold decision on (log_words.py's own
# PASS_ACTION_IDS does the same kind of mirroring). Reimplemented here, not
# read off the page, so runs_of's idea of a "run" does not run through
# logGroups() at all -- see the module docstring.
PASS_ACTION_IDS = {"pass_combat_intrigue", "pass_endgame_intrigue"}
PASS_MARKER_KINDS = {"combat_intrigue_passed", "endgame_intrigue_passed"}
QUIET_ACTIONS = {"finish_agent_turn", "finish_reveal", *PASS_ACTION_IDS}
SOLO_ACTIONS = {"pick_leader"}


def split_entry_events(entry: dict, neutral_kinds: set[str]) -> tuple[list, list]:
    """An entry's events split into "own" (about the acting seat) and "flow"
    (the game's own doing from here on, or about someone else) -- mirrors
    splitEntryEvents in panels.js, which logGroups()'s fold decision and the
    turn-card grouping both read."""
    own: list = []
    flow: list = []
    switched = False
    for event in entry.get("events") or []:
        if not switched and event["kind"] in neutral_kinds:
            switched = True
        payload = event.get("payload")
        target = payload.get("player") if isinstance(payload, dict) else None
        is_seat = isinstance(target, int) and not isinstance(target, bool)
        about_other = is_seat and target != entry["actor"]
        (flow if switched or about_other else own).append(event)
    return own, flow


def runs_of(entries: list[dict], neutral_kinds: set[str]) -> list[dict]:
    """Runs of consecutive foldable Combat/Endgame Intrigue passes in a raw
    log (state.review.meta.log), worked out independently of logGroups()
    (module docstring). A pass continues the run right before it exactly
    when nothing has closed a card since: the previous log entry is an
    action by the same actor, was not itself a card-closing (quiet or solo)
    step, and produced no flow events of its own -- same as the "no open
    turn card of the same actor" condition logGroups() folds on. Its own
    events must be only the pass's marker event(s) (PASS_MARKER_KINDS) or
    none. Runs break at an undo marker or a chance step (a log entry whose
    type isn't "action"), at any step with a flow event, and whenever the
    action id changes.
    """
    runs: list[dict] = []
    current: dict | None = None
    previous: dict | None = None
    for entry in entries:
        if entry["type"] != "action":
            current = None
            previous = None
            continue
        own, flow = split_entry_events(entry, neutral_kinds)
        continues_open_card = (
            previous is not None
            and previous["actor"] == entry["actor"]
            and previous["action_id"] not in QUIET_ACTIONS | SOLO_ACTIONS
        )
        foldable = (
            entry["action_id"] in PASS_ACTION_IDS
            and not continues_open_card
            and all(event["kind"] in PASS_MARKER_KINDS for event in own)
        )
        if foldable:
            if current is not None and current["action_id"] == entry["action_id"]:
                current["actors"].append(entry["actor"])
            else:
                current = {"action_id": entry["action_id"], "actors": [entry["actor"]]}
                runs.append(current)
        else:
            current = None
        if flow:
            current = None
            previous = None
        else:
            previous = entry
    return runs


def adjacent_fold_pairs(card_is_passes: list[bool]) -> list[int]:
    """Indices j such that the j-th and (j+1)-th `.turn-card.passes` (in DOM
    order, among fold cards only) sit back to back in the FULL card list --
    nothing else rendered between them."""
    positions = [i for i, is_passes in enumerate(card_is_passes) if is_passes]
    return [
        j for j in range(len(positions) - 1) if positions[j + 1] == positions[j] + 1
    ]


# Every non-undo-marker .turn-card in DOM order, tagged with whether it is a
# fold and (for a fold) its seats and full text; a non-fold, non-neutral card
# left holding a single pass-labelled line is the old bug's shape. `word` is
# the current language's word for "pass" (PASS_WORD), passed in so this stays
# text-based rather than reaching for an action id.
COLLECT_JS = """(word) => {
  const cards = [...document.querySelectorAll("#action-log .turn-card")].filter(
    (card) => !card.classList.contains("undo-marker")
  );
  const passCards = [];
  const lonelyPasses = [];
  const cardIsPasses = cards.map((card) => card.classList.contains("passes"));
  cards.forEach((card, i) => {
    if (cardIsPasses[i]) {
      const domSeats = [...card.querySelectorAll(".pass-seat .seat-mark")].map(
        (mark) => Number(mark.dataset.seat)
      );
      passCards.push({ domSeats, text: card.textContent });
    } else if (!card.classList.contains("neutral")) {
      const lines = card.querySelectorAll(".turn-line");
      if (lines.length === 1 && lines[0].textContent.includes(word)) {
        lonelyPasses.push(lines[0].textContent);
      }
    }
  });
  const names = new Set();
  for (const table of Object.values(state.catalog)) {
    if (!table || typeof table !== "object") continue;
    for (const entry of Object.values(table)) {
      if (entry && typeof entry.name === "string") names.add(entry.name);
    }
  }
  return {
    entries: state.review.meta.log,
    neutralKinds: [...NEUTRAL_EVENT_KINDS],
    passCards,
    cardIsPasses,
    lonelyPasses,
    names: [...names],
  };
}"""


def create_ai_game(page, base: str, seed: int, expansions: tuple[str, ...]) -> str:
    """A finished all-AI (heuristic) game, opened as a review at the end.

    Nobody can sit at an all-AI game, so the client opens it as a playing
    replay review at once (spectate.py); this stops that playback and seeks
    straight to the last step before reading anything.
    """
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    set_rule_options(page, *expansions)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.review !== null && state.view !== null")
    page.evaluate("stopPlayback(); reviewSeek(state.review.meta.step_count)")
    page.wait_for_function(
        "state.review.cursor === state.review.meta.step_count"
        " && !playback.playing && refreshFlight === null"
    )
    return page.evaluate("state.gameId")


def switch_language(page, lang: str) -> None:
    page.evaluate(f"setLanguage('{lang}')")
    page.wait_for_function("refreshFlight === null")
    # redrawForLanguage() re-seeks the review cursor, which is itself a
    # network round trip (reviewGoto); log_words.py's own check_page waits
    # the same way rather than polling a flag this path never sets.
    page.wait_for_timeout(300)


def strip(text: str, phrases: list[str]) -> str:
    for phrase in phrases:
        if phrase in text:
            text = text.replace(phrase, " ")
    return text


def check_game(page, label: str) -> None:
    for lang in ("ko", "en"):
        switch_language(page, lang)
        result = page.evaluate(COLLECT_JS, PASS_WORD[lang])
        tag = f"{label} [{lang}]"
        runs = runs_of(result["entries"], set(result["neutralKinds"]))
        pass_cards = result["passCards"]
        dom_seats = [card["domSeats"] for card in pass_cards]
        run_actors = [run["actors"] for run in runs]
        if not check.ok(
            dom_seats == run_actors,
            f"{tag}: each fold's seats, in order and count, equal an independent run",
            {"dom": dom_seats[:8], "runs": run_actors[:8]},
        ):
            continue
        check.ok(
            bool(pass_cards),
            f"{tag}: the game reaches a folded pass card",
            len(pass_cards),
        )
        check.ok(
            any(len(actors) >= 2 for actors in run_actors),
            f"{tag}: at least one fold holds two or more seats",
            [len(actors) for actors in run_actors][:8],
        )
        same_id_adjacent = [
            runs[j]["action_id"]
            for j in adjacent_fold_pairs(result["cardIsPasses"])
            if runs[j]["action_id"] == runs[j + 1]["action_id"]
        ]
        check.ok(
            not same_id_adjacent,
            f"{tag}: no two DOM-adjacent fold cards share an action id",
            same_id_adjacent[:4],
        )
        word = PASS_WORD[lang]
        miscounted = [
            card["text"][:80] for card in pass_cards if card["text"].count(word) != 1
        ]
        check.ok(
            not miscounted,
            f"{tag}: the pass word appears once per fold card",
            miscounted[:4],
        )
        check.ok(
            not result["lonelyPasses"],
            f"{tag}: no full-weight card is left holding a single pass line",
            result["lonelyPasses"][:4],
        )
        allowed = result["names"] + sorted(KOREAN_KEEPS_ENGLISH, key=len, reverse=True)
        if lang == "ko":
            stray = [
                (words, card["text"][:80])
                for card in pass_cards
                if (words := sorted(set(LATIN.findall(strip(card["text"], allowed)))))
            ]
            check.ok(
                not stray, f"{tag}: fold cards hold no stray Latin word", stray[:4]
            )
        else:
            stray = [
                card["text"][:80] for card in pass_cards if HANGUL.search(card["text"])
            ]
            check.ok(not stray, f"{tag}: fold cards hold no Hangul", stray[:4])
    switch_language(page, "ko")


def main() -> None:
    with server() as (base, log_path), chrome() as browser:
        for config in GAMES:
            print(f"[{config['label']}] seed {config['seed']}")
            _, page, _rec = open_context(browser, config["label"], VIEWPORT)
            create_ai_game(page, base, config["seed"], config["expansions"])
            check_game(page, config["label"])
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
