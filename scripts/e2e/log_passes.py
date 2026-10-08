"""E2E for ITEM 8h: chained Combat/Endgame Intrigue passes fold into one log
card (panels.js logGroups/passesCard, 2026-09-25).

Bug this reproduces: a verified-decision sweep of finished all-AI games
found consecutive pass_combat_intrigue / pass_endgame_intrigue entries each
reading as their own full-weight turn card -- 14-19% of all log cards, 3-4
cards per round in a 448px log, and each card saying "pass" twice (the head
line from ACTION_LABELS plus the muted event line). The design folds a run
of chained passes of the same action_id into ONE compact .turn-card.passes:
the pass label once, then the passing seats in order. Since 2026-10-09 a
chain of declined Conflict-end windows (decline_conflict_end_intrigue) folds
the same way: that window opens on public facts, mostly with nothing to play
(OQ-103), and its per-seat "offered" lines are left out of the cards. A
chance step whose lines are all left out (the CONFLICT_END pause before the
windows) still closes the open turn card, so the last reward recipient's
decline right after it starts a fold instead of joining its reward card: a
third game reaches that shape (reward_then_decline).

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

A base-game and two all-expansion all-AI games (heuristic seats hold few
Intrigue cards, so most Combat/Endgame Intrigue windows end in a chain of
passes), all reviewed to the end, in both languages:

- for every run of consecutive foldable pass entries found by runs_of, there
  is exactly one .turn-card.passes whose seats, in DOM order, are exactly
  that run's actors, in order, with the same count;
- at least one fold holds two or more seats (a chain actually chained, not
  just a run of one-seat folds), and so do the Conflict-end declines of an
  Immortality game;
- in the third game, every decline right after its own seat's reward card
  and a pause that shows nothing is in a fold, and there is one;
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
# base game reuses it with every expansion box off. Of 60 seeds scanned with
# every expansion (2026-10-09, codec v141), 16, 36 and 41 have a seat's
# Conflict reward choice followed by the CONFLICT_END pause, which shows
# nothing, and then by that seat's own decline (reward_then_decline): the
# decline must start a fold, not join the reward card. 36 also folds two
# seats' declines (16 does not).
GAMES = (
    {"label": "base game", "seed": 7, "expansions": ()},
    {"label": "all-expansion game", "seed": 7, "expansions": RULE_OPTIONS},
    {
        "label": "all-expansion game, a decline after its own reward",
        "seed": 36,
        "expansions": RULE_OPTIONS,
        "reward_then_decline": True,
    },
)

HANGUL = re.compile(r"[가-힣]")
LATIN = re.compile(r"[A-Za-z][A-Za-z'\-]*")
# The word a fold card says once, by its action id; a declined Conflict-end
# window says "쓰지 않음" (OQ-103, 2026-10-09).
PASS_WORDS = {
    "pass_combat_intrigue": {"ko": "패스", "en": "Passed"},
    "pass_endgame_intrigue": {"ko": "패스", "en": "Passed"},
    "decline_conflict_end_intrigue": {"ko": "쓰지 않음", "en": "Declined"},
}
# What marks a lone pass line in a seat's own card: the fold words, except
# that many English event labels end in "Declined", so a declined window's
# line is told by its action label instead.
LONE_PASS_WORDS = {"ko": ["패스", "쓰지 않음"], "en": ["Passed", "Decline to use"]}

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
PASS_ACTION_IDS = {
    "pass_combat_intrigue",
    "pass_endgame_intrigue",
    "decline_conflict_end_intrigue",
}
PASS_MARKER_KINDS = {
    "combat_intrigue_passed",
    "endgame_intrigue_passed",
    "conflict_end_trigger_declined",
}
# Mirrors UNLOGGED_EVENT_KINDS (static/panels.js): left out of every card.
UNLOGGED_EVENT_KINDS = {"conflict_end_trigger_offered"}
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
        if event["kind"] in UNLOGGED_EVENT_KINDS:
            continue
        if not switched and event["kind"] in neutral_kinds:
            switched = True
        payload = event.get("payload")
        target = payload.get("player") if isinstance(payload, dict) else None
        is_seat = isinstance(target, int) and not isinstance(target, bool)
        about_other = is_seat and target != entry["actor"]
        (flow if switched or about_other else own).append(event)
    return own, flow


def shows_a_line(chance: dict) -> bool:
    """Whether a chance step puts anything in the log cards: its own line
    (every chance step but a pause, isPauseChance in static/core.js) or an
    event that is not left out -- mirrors logGroups()'s chance branch."""
    if not str(chance["decision_id"]).endswith(":pause"):
        return True
    return any(
        event["kind"] not in UNLOGGED_EVENT_KINDS
        for event in chance.get("events") or []
    )


def runs_of(entries: list[dict], neutral_kinds: set[str]) -> list[dict]:
    """Runs of consecutive foldable Combat/Endgame Intrigue passes in a raw
    log (state.review.meta.log), worked out independently of logGroups()
    (module docstring). A pass continues the run right before it exactly
    when nothing has closed a card since: the previous log entry is an
    action by the same actor, was not itself a card-closing (quiet or solo)
    step, and produced no flow events of its own -- same as the "no open
    turn card of the same actor" condition logGroups() folds on. Its own
    events must be only the pass's marker event(s) (PASS_MARKER_KINDS) or
    none. Runs break at an undo marker, at a chance step that shows a line,
    at any step with a flow event, and whenever the action id changes.

    A chance step always closes the open card, also one that shows nothing
    (a pause whose only events are UNLOGGED_EVENT_KINDS, like the
    CONFLICT_END pause before the windows): the seat whose reward card came
    right before it starts a new card with its decline, which so folds. It
    breaks a run only when it shows a line, as logGroups() puts a card
    between the passes only then.
    """
    runs: list[dict] = []
    current: dict | None = None
    previous: dict | None = None
    for entry in entries:
        if entry["type"] == "chance":
            previous = None
            if shows_a_line(entry):
                current = None
            continue
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
                current["indexes"].append(entry["index"])
            else:
                current = {
                    "action_id": entry["action_id"],
                    "actors": [entry["actor"]],
                    "indexes": [entry["index"]],
                }
                runs.append(current)
        else:
            current = None
        if flow:
            current = None
            previous = None
        else:
            previous = entry
    return runs


def reward_then_decline(entries: list[dict]) -> list[int]:
    """Log indexes of the Conflict-end declines that come right after a
    pause showing nothing (only UNLOGGED_EVENT_KINDS) that itself comes
    right after the same seat's step that leaves its card open (not quiet
    or solo): a Conflict reward choice before the CONFLICT_END pause. Such
    a decline must fold (runs_of); a pause that did not close the card
    left it as the reward card's last line and split the decline chain
    (2026-10-09 review)."""

    found = []
    for before, pause, after in zip(entries, entries[1:], entries[2:], strict=False):
        if (
            pause["type"] == "chance"
            and not shows_a_line(pause)
            and before["type"] == "action"
            and after["type"] == "action"
            and after["action_id"] == "decline_conflict_end_intrigue"
            and before["actor"] == after["actor"]
            and before["action_id"] not in QUIET_ACTIONS | SOLO_ACTIONS
        ):
            found.append(after["index"])
    return found


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
# left holding a single pass-labelled line is the old bug's shape. `words`
# are the current language's words for "pass" (LONE_PASS_WORDS), passed in so
# this stays text-based rather than reaching for an action id.
COLLECT_JS = """(words) => {
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
      const text = lines.length === 1 ? lines[0].textContent : "";
      if (words.some((word) => text.includes(word))) {
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


def check_game(page, config: dict) -> None:
    label = config["label"]
    immortality = "immortality" in config["expansions"]
    for lang in ("ko", "en"):
        switch_language(page, lang)
        result = page.evaluate(COLLECT_JS, LONE_PASS_WORDS[lang])
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
        if immortality:
            declines = [
                run["actors"]
                for run in runs
                if run["action_id"] == "decline_conflict_end_intrigue"
            ]
            check.ok(
                any(len(actors) >= 2 for actors in declines),
                f"{tag}: Conflict-end declines fold too, two seats or more",
                declines[:4],
            )
        if config.get("reward_then_decline"):
            shaped = reward_then_decline(result["entries"])
            folded = {index for run in runs for index in run["indexes"]}
            check.ok(
                bool(shaped) and all(index in folded for index in shaped),
                f"{tag}: a decline right after its own reward card and a pause"
                " that shows nothing starts a fold",
                {"declines": shaped, "folded": sorted(folded)[:12]},
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
        miscounted = [
            card["text"][:80]
            for card, run in zip(pass_cards, runs, strict=True)
            if card["text"].count(PASS_WORDS[run["action_id"]][lang]) != 1
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
            check_game(page, config)
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
