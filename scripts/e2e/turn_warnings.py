"""E2E for the rows that say what a step costs the seat (2026-10-31).

User request 2026-10-31, after a real game: Dissecting Kit's trash of its
grafted Show of Strength lost Show of Strength's unused draw ("you can't
receive or activate an effect from a card that is already trashed",
OQ-022), and Arrakeen's draw then sealed the undo. The row's old mark, a
small suffix naming neither card nor effect, went unread. Now:

- a row whose dry run expires an unused Agent box of the seat's own card
  carries `forfeit` (server/forfeits.py) and shows its own ⚠ line naming the
  card and the lost effects (render.js appendForfeitNotes);
- the turn-end row lists the optional effects its press lapses (`lapses`,
  OQ-095 (2)), a Reveal's Persuasion left with a card it can still buy, and
  an Agent turn's units it could still deploy (appendTurnEndNotes), each a
  line under the button;
- the Reveal-turn row says an Agent turn is still open (appendRevealTurnNote,
  [Main p. 8]).

No press or confirmation is added: every line is text on its row (one-press
turn end, OQ-095). Five real positions (`fixtures/turn_warning_saves.py`,
four human seats with Immortality, seeded random play) are opened in Korean
and English; the expected payloads come from that script's own reading of
the engine, and the expected words are written here, not read off the
client's tables.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from common import (
    LAPTOP_VIEWPORT,
    REPO,
    Check,
    ServerProcess,
    chrome,
    open_context,
)
from lang import switch as switch_language
from open_mode import settled

check = Check()
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR")
    or tempfile.mkdtemp(prefix="dune-turn-warnings-")
)
HANGUL = re.compile("[가-힣]")
# What must never reach a player: an unexpanded term, an object, an id.
LEAKS = re.compile(r"\{[a-z_]+(?::\d+)?\}|\[object|\b[a-z]+_[a-z_]+\b")

FORFEIT = {
    "ko": "⚠ 아직 쓰지 않은 에이전트 칸 효과를 잃습니다 — {card}",
    "en": "⚠ Loses the unused Agent box effects of {card}",
}
LAPSES = {
    "ko": "⚠ 턴을 끝내면 쓰지 않은 효과가 사라집니다:",
    "en": "⚠ Ending the turn drops these unused effects:",
}
# The Persuasion icon sits between the words (its text is the image's).
PERSUASION = {
    "ko": r"^⚠ 남은\s+{left} — 획득할 수 있는 카드 {buys}장$",
    "en": r"^⚠ {left}\s+left — {buys} cards you can acquire$",
}
# The words the user chose (2026-10-31): "주둔지에 남음: 병력 N" and
# "에이전트 N 남음"; the unit words are the glossary's (docs/rules/
# glossary-ko.md: troop 병력; the Rise of Ix dreadnought 드레드노트).
DEPLOY = {"ko": "⚠ 주둔지에 남음: {units}", "en": "⚠ Stays in your garrison: {units}"}
UNIT_WORDS = {
    "deploy_troops": {"ko": "병력", "en": "troop"},
    "deploy_commanders": {"ko": "사다우카 지휘관", "en": "Sardaukar Commander"},
    "deploy_dreadnoughts": {"ko": "드레드노트", "en": "dreadnought"},
}
AGENTS = {
    "ko": "⚠ 에이전트 {count} 남음 — 공개 차례를 하면 이번 라운드에는 보낼 수 없습니다",
    "en": "⚠ {count} Agents left — a Reveal turn ends your Agent turns this round",
}

NOTES_JS = """(selector) => [...document.querySelectorAll(selector)].map((node) => {
  const item = node.closest('.action-item');
  return {
    note: node.dataset.note || null,
    card: node.dataset.card || null,
    text: node.innerText,
    images: [...node.querySelectorAll('img')].map((img) => img.alt),
    drawn: [...node.querySelectorAll('img')].every(
      (img) => img.complete && img.naturalWidth > 0),
    row: item ? Number(item.dataset.index) : 'turn-end',
  };
})"""


def open_save(browser, base: str, name: str):
    context, page, rec = open_context(browser, name, LAPTOP_VIEWPORT)
    page.goto(base + "/")
    page.locator(f"#save-list li:has-text('{name}') button").first.click()
    page.wait_for_function(
        "state.view !== null && refreshFlight === null"
        " && Boolean(state.actions && state.actions.actions.length)"
    )
    assert settled(page, 20)
    return context, page, rec


def offered(page, action_id: str) -> dict | None:
    """The seat's served row of ``action_id``, if it is offered."""

    rows = page.evaluate("state.actions.actions")
    return next((a for a in rows if a["action_id"] == action_id), None)


def notes(page, selector: str) -> list[dict]:
    return page.evaluate(NOTES_JS, selector)


def card_name(page, card_id: str) -> str:
    return page.evaluate("(id) => lookup(baseId(id)).name", card_id)


def no_leaks(what: str, lang: str, texts: list[str]) -> None:
    check.ok(
        not any(LEAKS.search(text) for text in texts),
        f"{what}: no raw term, object or id in the lines",
        texts,
    )
    if lang == "en":
        check.ok(
            not any(HANGUL.search(text) for text in texts),
            f"{what}: no Hangul in English",
            texts,
        )


def check_forfeit(page, what: str, lang: str, case: dict) -> None:
    rows = page.evaluate("state.actions.actions")
    row = next(
        (
            a
            for a in rows
            if a["action_id"] == case["action_id"]
            and a["arguments"] == case["arguments"]
        ),
        None,
    )
    if not check.ok(row is not None, f"{what}: the trash row is offered", case):
        return
    check.ok(
        [entry["card_id"] for entry in row.get("forfeit") or []] == case["lost"],
        f"{what}: the row's forfeit names the card the engine expires",
        (row.get("forfeit"), case["lost"]),
    )
    found = notes(page, ".forfeit-note")
    mine = [note for note in found if note["row"] == row["index"]]
    expected = [
        FORFEIT[lang].format(card=card_name(page, card)) for card in case["lost"]
    ]
    check.ok(
        [note["card"] for note in mine] == case["lost"]
        and all(
            note["text"].startswith(start)
            for note, start in zip(mine, expected, strict=False)
        ),
        f"{what}: the row warns {expected!r}",
        mine,
    )
    # Every line belongs to a row whose payload forfeits, and back.
    flagged = {a["index"] for a in rows if a.get("forfeit")}
    check.ok(
        {note["row"] for note in found} == flagged,
        f"{what}: a line on exactly the rows that forfeit",
        ({note["row"] for note in found}, flagged),
    )
    no_leaks(what, lang, [note["text"] for note in found])
    # The effects are the row buttons' icons, drawn as pictures (coordinator
    # 2026-10-31: no token text such as "[draw]2" may show).
    check.ok(
        all(note["images"] and note["drawn"] for note in mine),
        f"{what}: the lost effects show as loaded icon pictures",
        mine,
    )
    title = page.evaluate(
        "(i) => document.querySelector("
        "`#actions .action-item[data-index='${i}'] .forfeit-note`).title",
        row["index"],
    )
    check.ok(bool(title), f"{what}: the line explains itself on hover", title)


def turn_end_notes(page) -> list[dict]:
    return notes(page, "#decision-info .turn-end-row .turn-end-note")


def check_lapses(page, what: str, lang: str, case: dict) -> None:
    end = offered(page, "finish_agent_turn")
    if not check.ok(end is not None, f"{what}: the turn end is offered"):
        return
    check.ok(
        end.get("lapses") == case["lapses"],
        f"{what}: the turn end's lapses are the engine's",
        (end.get("lapses"), case["lapses"]),
    )
    lines = [note for note in turn_end_notes(page) if note["note"] == "lapses"]
    check.ok(
        len(lines) == 1 and lines[0]["text"].startswith(LAPSES[lang]),
        f"{what}: one line under the button starts {LAPSES[lang]!r}",
        lines,
    )
    if lines:
        items = lines[0]["text"][len(LAPSES[lang]):].strip().split(" · ")
        check.ok(
            len(items) == len(case["lapses"]) and all(items),
            f"{what}: one item per lapsed effect",
            items,
        )
        for lapse in case["lapses"]:
            card = lapse["payload"].get("card_id")
            if card:
                check.ok(
                    card_name(page, card) in lines[0]["text"],
                    f"{what}: the lapsed box names its card",
                    lines[0]["text"],
                )
        no_leaks(what, lang, [lines[0]["text"]])
    button = page.locator("#decision-info .turn-end-row button")
    check.ok(
        button.count() == 1 and "⚠" not in button.inner_text(),
        f"{what}: the button keeps its own words (the line is under it)",
    )


def check_persuasion(page, what: str, lang: str, case: dict) -> None:
    if "rows" in case:
        # The original game's Recruitment Mission: a card offered twice, to
        # the discard pile and onto the deck; the line counts cards, not rows.
        rows = page.evaluate(
            """() => state.actions.actions.filter(
              (a) => ['acquire_imperium', 'acquire_reserve'].includes(a.action_id))"""
        )
        cards = {
            r["arguments"].get("instance_id") or r["arguments"].get("card_id")
            for r in rows
        }
        check.ok(
            len(rows) == case["rows"] > len(cards) == case["buys"],
            f"{what}: a card is offered twice ({len(rows)} rows, {len(cards)} cards)",
            rows,
        )
    lines = [note for note in turn_end_notes(page) if note["note"] == "persuasion"]
    pattern = PERSUASION[lang].format(left=case["persuasion"], buys=case["buys"])
    check.ok(
        len(lines) == 1 and re.match(pattern, lines[0]["text"]) is not None,
        f"{what}: the Reveal's end says {pattern!r}",
        lines,
    )
    check.ok(
        bool(lines) and len(lines[0]["images"]) == 1,
        f"{what}: the Persuasion icon names the resource",
        lines,
    )


def check_deploy(page, what: str, lang: str, case: dict) -> None:
    lines = [note for note in turn_end_notes(page) if note["note"] == "deploy"]
    units = " · ".join(
        f"{UNIT_WORDS[deploy][lang]} {count}"
        if lang == "ko"
        else f"{count} {UNIT_WORDS[deploy][lang]}{'' if count == 1 else 's'}"
        for deploy, count in case["units"].items()
    )
    expected = DEPLOY[lang].format(units=units)
    check.ok(
        [line["text"] for line in lines] == [expected],
        f"{what}: the turn end says {expected!r}",
        lines,
    )


def check_reveal_agents(page, what: str, lang: str, case: dict) -> None:
    reveal = offered(page, "reveal_turn")
    if not check.ok(reveal is not None, f"{what}: the Reveal turn is offered"):
        return
    lines = [
        note
        for note in notes(page, "#actions .turn-end-note")
        if note["note"] == "agents"
    ]
    expected = AGENTS[lang].format(count=case["agents"])
    check.ok(
        [(line["row"], line["text"]) for line in lines]
        == [(reveal["index"], expected)],
        f"{what}: the Reveal row says {expected!r}",
        lines,
    )


def check_case(browser, base: str, name: str, case: dict) -> None:
    print(f"[{name}] seed {case['seed']}, seat {case['seat']}")
    context, page, rec = open_save(browser, base, name)
    check.ok(
        page.evaluate("state.viewSeat") == case["seat"]
        and page.evaluate("state.summary.decision.owner") == case["seat"],
        f"{name}: the save rests on seat {case['seat']}'s choice",
    )
    for lang in ("ko", "en"):
        switch_language(page, lang)
        what = f"{name} ({lang})"
        if name == "warn-forfeit":
            check_forfeit(page, what, lang, case)
        elif name == "warn-lapses":
            check_lapses(page, what, lang, case)
        elif name in ("warn-persuasion", "warn-deck-top-buys"):
            check_persuasion(page, what, lang, case)
        elif name == "warn-deploy":
            check_deploy(page, what, lang, case)
        elif name == "warn-reveal-agents":
            check_reveal_agents(page, what, lang, case)
        page.screenshot(path=str(SHOTS / f"{name}_{lang}.png"))
        print(f"  screenshot: {SHOTS / f'{name}_{lang}.png'}")
    # Nothing was pressed: the lines are words only.
    check.ok(
        page.evaluate("state.summary.decision.owner") == case["seat"],
        f"{name}: reading the lines sent nothing",
    )
    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not failed, f"{name}: no failed requests", failed[:5])
    check.ok(not rec.js_errors, f"{name}: no JS exceptions", rec.js_errors[:5])
    context.close()


def main() -> None:
    saves = tempfile.mkdtemp(prefix="dune-turn-warnings-e2e-")
    found = json.loads(
        subprocess.run(
            [
                str(REPO / ".venv/bin/python"),
                str(Path(__file__).parent / "fixtures/turn_warning_saves.py"),
                saves,
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    print(f"fixtures: {sorted(found)}")
    SHOTS.mkdir(parents=True, exist_ok=True)
    process = ServerProcess(saves=saves).start()
    try:
        with chrome() as browser:
            for name, case in found.items():
                check_case(browser, process.base, name, case)
    finally:
        process.stop()
    text = process.log_path.read_text()
    check.ok(
        "Traceback" not in text and "ERROR" not in text,
        f"no server errors with the saved games (see {process.log_path})",
    )
    check.finish()


if __name__ == "__main__":
    main()
