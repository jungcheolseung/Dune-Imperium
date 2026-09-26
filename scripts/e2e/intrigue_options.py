"""E2E for ITEM 8b: an Intrigue card's rendered option wording (2026-09-25).

Playing an Intrigue card that offers more than one option showed the
engine's numeric option index instead of what the option does: two rows for
the same card both read "Special Mission, 선택지: 0" / "선택지: 1", and only
the ⓘ popover told them apart. The catalog already carries each option's
printed wording (`catalog.intrigue[<card key>].text[option]`, one line per
engine option, always prefixed by its timing: "Plot — ", "Combat — ",
"Endgame — "). describeAction (core.js) now shows that line, prefix
stripped, through iconize() -- printed card wording, English in both
languages -- instead of the bare index; a single-option card shows nothing
for the option (the card name already says it), and a card the catalog
cannot resolve (redacted or unknown) falls back to the old numeric label.

Step K3 (2026-09-25) gave Intrigue its own Korean twin
(`catalog.intrigue[<card key>].text_ko`, `display.effect_dsl_text_ko`); the
Korean pass below (`check_dual_option_rows(page, "Korean", ...)`) now
expects each row against `text_ko`/`phrase()`, the line `intrigueOptionBody`
(core.js) actually renders once that field exists, instead of the pre-K3
`text`/`iconize()` fallback it was really checking before -- the English
pass keeps checking `text`/`iconize()` as before.

Reaching a real decision that offers two options of the same card at once
needs a real game, not a synthetic action list: with the base ruleset (no
expansions, no leader draft -- `open_mode.create_game`'s defaults), driving
seat 0 with a fixed random policy (`rng = random.Random(seed)`; `rng.choice()`
over the *current* legal actions each decision, confirming holds at once)
lands seat 0 on a Combat decision offering "Tactical Option" options 0 and 1
side by side. The policy is replayed live against the browser rather than
hard-coded to a step count, and the script tries the seeds in SEEDS in turn
until one reaches such a decision, so a rules change that moves or removes
the decision in one game does not break the check (seed 4 stopped reaching
it when master's 2026-09-26/27 rulings landed).
"""

from __future__ import annotations

import random
import re
import shutil
import time

from common import SERVER_LOG_COPY, Check, chrome, open_context, server
from lang import switch as switch_language
from open_mode import create_game, settled

check = Check()

# Seeds tried in order until one reaches a dual-option decision within the
# cap (base ruleset, no leader draft); the first that does is used.
SEEDS = tuple(range(12))
STEP_CAP = 150

# An Intrigue instance id, e.g. "intrigue:special_mission:0"; group 1 is the
# catalog key core.js's baseId() strips it to (copied from its "shared"
# branch, the one every non-starter, non-contract instance id matches).
INSTANCE_ID = re.compile(r"^(?:imperium|reserve|intrigue|tleilaxu|skill):(.+):\d+$")

# describeAction's new branch strips up to and including the first " — "
# (the option's printed timing prefix: "Plot — ", "Combat — ", "Endgame —
# "); mirrored here so the test derives its expectation independently of
# the branch it is checking.
STRIP_AND_ICONIZE_JS = """(text) => {
  const dash = text.indexOf(" — ");
  const stripped = dash === -1 ? text : text.slice(dash + 3);
  const box = document.createElement("span");
  box.appendChild(iconize(stripped));
  for (const n of box.querySelectorAll(".amount")) n.replaceWith(n.title);
  for (const n of box.querySelectorAll("img")) n.replaceWith(n.alt);
  return { stripped, rendered: box.textContent };
}"""

# Step K3 (2026-09-25): the catalog now carries intrigue[id].text_ko
# (display.effect_dsl_text_ko), so the Korean pass below renders a real
# Korean line through phrase() -- {term}/{term:count} expansion, our own
# labels' path -- rather than falling back to iconize(en) the way it did
# before Intrigue had a Korean twin. Same " — " timing-prefix strip as
# STRIP_AND_ICONIZE_JS above; kept as a separate function so each check
# derives its expectation independently of the branch it is checking.
STRIP_AND_PHRASE_JS = """(text) => {
  const dash = text.indexOf(" — ");
  const stripped = dash === -1 ? text : text.slice(dash + 3);
  const box = document.createElement("span");
  box.appendChild(phrase(stripped));
  for (const n of box.querySelectorAll(".amount")) n.replaceWith(n.title);
  for (const n of box.querySelectorAll("img")) n.replaceWith(n.alt);
  return { stripped, rendered: box.textContent };
}"""

# logEventLine() (panels.js) is what draws the log card under a played
# step; it never runs for an action still on screen, so this builds the
# same intrigue_played event the engine would emit for the row (payload
# shape from rules/intrigue.py: card_id, option, player) and renders it
# directly, the way describeActionText() below renders an action.
LOG_EVENT_LINE_JS = """(payload) => {
  const box = document.createElement("span");
  box.appendChild(logEventLine({ kind: "intrigue_played", payload }));
  for (const n of box.querySelectorAll(".amount")) n.replaceWith(n.title);
  for (const n of box.querySelectorAll("img")) n.replaceWith(n.alt);
  return box.textContent;
}"""


def find_dual_option(actions: list[dict]) -> tuple[str | None, list[dict]]:
    """The first card_id with two or more play_intrigue rows offered at
    once, in the order they appear in ``actions`` (state.actions.actions'
    own order)."""

    groups: dict[str, list[dict]] = {}
    for action in actions:
        if action["action_id"] != "play_intrigue":
            continue
        card_id = action["arguments"].get("card_id")
        if not isinstance(card_id, str):
            continue
        groups.setdefault(card_id, []).append(action)
    for card_id, rows in groups.items():
        if len(rows) >= 2:
            return card_id, rows
    return None, []


def drive_to_dual_option(page, seed: int) -> tuple[str | None, list[dict]]:
    """Replay ui-sweep's own random policy against the live page until a
    decision offers two options of the same Intrigue card at once, or the
    step budget runs out."""

    rng = random.Random(seed)
    for _ in range(STEP_CAP):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            return None, []
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        actions = page.evaluate("state.actions.actions")
        card_id, rows = find_dual_option(actions)
        if card_id:
            return card_id, rows
        choice = rng.choice(actions)
        page.evaluate(f"applyAction({choice['index']})")
    return None, []


def check_no_bare_option_index(page, actions: list[dict], what: str) -> None:
    """Every play_intrigue row in ``actions`` reads real wording, never the
    engine's bare option index -- in the step head (describeActionText) and
    in the log line a played row later draws under it (logEventLine)."""

    for action in actions:
        if action["action_id"] != "play_intrigue":
            continue
        shown = page.evaluate("(a) => describeActionText(a)", action)
        check.ok(
            "선택지:" not in shown and "Option:" not in shown,
            f"{what}: {action['arguments'].get('card_id')} option "
            f"{action['arguments'].get('option')} does not read a bare index",
            shown,
        )
        button = page.locator(
            f"#actions .action-item[data-index='{action['index']}']"
            " > button:not(.action-info)"
        )
        if button.count():
            live = button.inner_text()
            check.ok(
                "선택지:" not in live and "Option:" not in live,
                f"{what}: the rendered button for it agrees",
                live,
            )
        # logEventPayload (panels.js) skips the "option" key of an
        # intrigue_played event, so
        # the log card this row would draw once played never shows it
        # either -- build the intrigue_played event the engine would emit
        # (rules/intrigue.py) and render it the same way.
        payload = dict(action["arguments"])
        payload["player"] = 0
        log_line = page.evaluate(LOG_EVENT_LINE_JS, payload)
        check.ok(
            "선택지:" not in log_line and "Option:" not in log_line,
            f"{what}: the log line it would draw once played agrees",
            log_line,
        )


def check_dual_option_rows(page, what: str, card_id: str, rows: list[dict]) -> None:
    print(f"  {what}: {card_id} offers {len(rows)} options at once")
    check.ok(len(rows) >= 2, f"{what}: at least two options are offered", len(rows))

    match = INSTANCE_ID.match(card_id)
    check.ok(match is not None, f"{what}: {card_id} parses as a catalog instance id")
    base_id = match.group(1) if match else card_id
    entry = page.evaluate("(id) => state.catalog.intrigue[id]", base_id)
    check.ok(entry is not None, f"{what}: the catalog has an entry for {base_id}")
    # Step K3: the Korean pass now checks against text_ko/phrase(), the
    # line the page actually renders once entry.text_ko exists (core.js
    # intrigueOptionBody() prefers it) -- text/iconize() would be checking
    # the pre-K3 fallback, not what is really on screen.
    korean = what == "Korean"
    texts = (entry.get("text_ko") if korean else entry["text"]) if entry else []
    strip_js = STRIP_AND_PHRASE_JS if korean else STRIP_AND_ICONIZE_JS
    check.ok(
        len(texts or []) > 1,
        f"{what}: the catalog gives more than one option line for {base_id}",
        texts,
    )

    shown_rows = []
    for row in rows[:2]:
        option = row["arguments"]["option"]
        button = page.locator(
            f"#actions .action-item[data-index='{row['index']}']"
            " > button:not(.action-info)"
        )
        check.ok(button.count() == 1, f"{what}: option {option}'s row is on screen")

        shown = page.evaluate("(a) => describeActionText(a)", row)
        shown_rows.append(shown)
        check.ok(
            "선택지:" not in shown and "Option:" not in shown,
            f"{what}: option {option}'s row reads real wording, not a bare index",
            shown,
        )

        expected = page.evaluate(strip_js, texts[option])
        check.ok(
            shown.endswith(expected["rendered"]),
            f"{what}: option {option}'s row ends with the catalog's option "
            "wording (prefix stripped, iconized)",
            (shown, expected),
        )
        check.ok(
            entry["name"] in shown,
            f"{what}: option {option}'s row still names the card",
            shown,
        )

    check.ok(
        shown_rows[0] != shown_rows[1],
        f"{what}: the two rows differ",
        shown_rows,
    )

    # Every play_intrigue row currently offered, not just this card's --
    # matches check_no_bare_option_index's own claim about what it covers.
    all_actions = page.evaluate("state.actions.actions")
    check_no_bare_option_index(page, all_actions, what)


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            print("[1] a real game reaches a decision offering two options of one card")
            context, page, rec = open_context(browser, "intrigue-options")
            card_id, rows = None, []
            for seed in SEEDS:
                create_game(page, base, humans=(0,), seed=seed)
                card_id, rows = drive_to_dual_option(page, seed)
                if card_id is not None:
                    print(f"  .. seed {seed} reaches {card_id}")
                    break
            if card_id is None:
                check.ok(
                    False,
                    f"one of seeds {SEEDS[0]}-{SEEDS[-1]} reached a dual-option "
                    f"Intrigue decision within {STEP_CAP} steps",
                )
            else:
                check_dual_option_rows(page, "Korean", card_id, rows)

                print("[2] the same rows in English")
                switch_language(page, "en")
                # Re-read: the action list itself does not change with language,
                # but re-evaluating keeps this independent of [1]'s snapshot.
                actions = page.evaluate("state.actions.actions")
                _, rows_en = find_dual_option(actions)
                check.ok(
                    len(rows_en) >= 2 and rows_en[0]["arguments"]["card_id"] == card_id,
                    "the dual-option decision is still on screen after switching "
                    "language",
                )
                if len(rows_en) >= 2:
                    check_dual_option_rows(page, "English", card_id, rows_en)

            failed = [r for r in rec.requests if r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    check.finish()


if __name__ == "__main__":
    main()
