"""E2E of a Reveal's card choices as rows of the Reveal list (codec v147).

User ruling 2026-10-14 (OQ-095 (7) addition): "You may resolve Reveal
effects in any order you like" [Main p. 12], so a revealed card's choice is
no longer a window of its own, answered or put off one card at a time.
Every choice waits on the Reveal frame and is offered beside the purchases,
gains and Plots; an optional one ("may", an arrow cost, a black trash icon
[FAQ p. 3]) offers no refusal and lapses unused when the Reveal ends
(``reveal_choice_lapsed``), a mandatory one keeps "턴 종료 ▶" (the explicit
``finish_reveal``) away while it offers something, and one that offers
nothing now is a greyed-out row with its reason.

The Reveals are real: ``fixtures/reveal_choice_saves.py`` walks seeded
four-human games with random steps and saves the first Reveal that shows an
optional choice and a mandatory one offered, a card to buy and a choice
waiting, twice: "optional" (the waiting choice is optional; seed 306: Public
Spectacle's Spy icon, Arrakis Observer's recall, Unswerving Loyalty without
its Fremen Bond) and "command" (a Command (6+) choice waits; seed 6270 since
codec v154, seed 167 before: Delivery Logistics' mandatory choice, whose
Persuasion then opens Intelligence Training waiting for Command, beside
Disruption Tactics' optional one). For each, on a page holding
every seat (open server):

- [1] Korean: each offered choice is a header naming its card and what the
  choice does, in the server's pending order, with a line saying whether it
  may be left (it then lapses unused when the Reveal ends) or must be
  chosen first; its rows sit under it and no other row does; a branch it
  cannot take now (Desert Power's sandworm) is greyed out under it; the
  cards to buy are ordinary rows under their own heading; a waiting choice
  is a greyed-out row led by its card, with what keeps it closed (Command:
  the Persuasion generated so far) and that it lapses when the Reveal ends;
  no turn-end row while a mandatory choice is offered; no engine id (a
  ``source`` card id among them) anywhere in the panel.
- [2] English: the same in English, no Hangul.
- [3] Answering the mandatory choices one at a time (clicking the first row
  under its header) keeps the turn end away until the last is answered; a
  waiting choice its answer opens (Intelligence Training) becomes a header
  of its own; then "턴 종료 ▶" is offered while an optional choice is still
  on offer.
- [4] Pressing it ends the Reveal: every choice still pending lapses, and
  the log says so in words with each card's name ("공개 차례 선택 쓰지 않음"
  / "Reveal turn Choice Unused"); the logged choice steps that name their
  card with ``source`` read the card's name, never its id.

Screenshots go to ``E2E_SHOTS_DIR`` (a temporary folder otherwise):
reveal_choices_{optional,command}_{ko,en}.png,
reveal_choices_{optional,command}_finish_ko.png and
reveal_choices_{optional,command}_log_ko.png.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from common import REPO, SERVER_LOG_COPY, Check, ServerProcess, chrome, open_context
from open_mode import settled

check = Check()

SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-reveal-choices-")
)
HANGUL = re.compile("[가-힣]")
# An engine id's shape: snake_case (a card's definition id, an effect).
ENGINE_ID = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")
NOTE = {
    "ko": {True: "쓰지 않은 채 사라짐", False: "끝낼 수 없음"},
    "en": {True: "lapses unused when the", False: "cannot end before you choose"},
}
LAPSE = {
    "ko": {True: "끝내면 쓰지 않은 채 사라짐", False: "끝낼 때까지 못 채우면 사라짐"},
    "en": {
        True: "it lapses unused when the Reveal turn ends",
        False: "it lapses if still unmet when the Reveal turn ends",
    },
}
LAPSED_LABEL = {"ko": "공개 차례 선택 쓰지 않음", "en": "Reveal turn Choice Unused"}
# The Reveal's own gains, which must be taken before it ends (OQ-045;
# rules/reveal_turn.py legal_reveal_gain_actions).
REVEAL_GAINS = {
    "recruit_reveal_troops",
    "draw_reveal_intrigue",
    "generate_reveal_specimens",
    "advance_reveal_tleilaxu",
    "advance_reveal_research",
    "gain_reveal_resources",
    "gain_reveal_faction_influence",
}

# The words of a node, each icon read as its name (an icon is an <img> whose
# alt is the term), so "{command}: ..." reads "통솔: ...".
WORDS_JS = """
  const words = (n) => n.nodeType === 3 ? n.textContent
    : n.tagName === 'IMG' ? n.alt
    : [...n.childNodes].map(words).join('');
  const read = (n) => n ? words(n).replace(/\\s+/g, ' ').trim() : null;
"""

# The decision panel, read in one go. A row's group is the Reveal choice
# header above it, up to any other heading.
PANEL_JS = (
    """() => {"""
    + WORDS_JS
    + """
  const box = document.getElementById('actions');
  const isHeading = (n) => ['pick-others', 'unavailable-heading', 'agent-box-heading']
    .some((name) => n.classList.contains(name));
  const groupOf = (node) => {
    for (let n = node.previousElementSibling; n; n = n.previousElementSibling) {
      if (n.classList.contains('reveal-choice-heading')) return n.dataset.choice;
      if (isHeading(n)) return null;
    }
    return null;
  };
  const headingOf = (node) => {
    for (let n = node.previousElementSibling; n; n = n.previousElementSibling) {
      if (isHeading(n)) return read(n);
    }
    return null;
  };
  const legal = state.actions ? state.actions.actions : [];
  return {
    kind: state.summary.decision ? state.summary.decision.kind : null,
    seat: state.viewSeat,
    revision: state.summary.revision,
    choices: (state.actions && state.actions.reveal_choices) || [],
    legal: legal.map((a) => ({
      index: a.index, action_id: a.action_id, reveal_choice: a.reveal_choice || null,
      arguments: a.arguments,
    })),
    finish: legal.some((a) => a.action_id === 'finish_reveal'),
    headings: [...box.querySelectorAll('.reveal-choice-heading')].map((h) => ({
      key: h.dataset.choice, text: read(h),
      note: read(h.nextElementSibling),
      noteOptional: h.nextElementSibling ? h.nextElementSibling.dataset.optional : null,
    })),
    rows: [...box.querySelectorAll('.action-item[data-index]')].map((r) => ({
      index: Number(r.dataset.index), group: groupOf(r), heading: headingOf(r),
      text: read(r.querySelector('button:not(.action-info)')),
    })),
    greyed: [...box.querySelectorAll('.unavailable-item')].map((r) => ({
      key: r.dataset.key, surface: r.dataset.surface, group: groupOf(r),
      heading: headingOf(r),
      body: read(r.querySelector('.unavailable-body')),
      badge: read(r.querySelector('.unavailable-badge')),
    })),
    turnEnd: [...document.querySelectorAll('#decision-info .turn-end-row button')]
      .map((b) => b.textContent),
    text: read(box) + ' ' + read(document.getElementById('decision-info')),
  };
}"""
)

# The log lines of the Reveal's lapsed choices (its finish_reveal step's
# events) and of the steps since its start that name their card with
# ``source``.
LOG_JS = (
    """([seat, since]) => {"""
    + WORDS_JS
    + """
  const entries = ((state.log && state.log.entries) || [])
    .filter((e) => e.actor === seat && !e.undone && e.index >= since);
  const finish = entries.filter((e) => e.action_id === 'finish_reveal').pop();
  const events = finish ? (finish.events || [])
    .filter((e) => e.kind === 'reveal_choice_lapsed')
    .map((e) => e.payload.card_id) : [];
  const line = (entry) => document.querySelector(
    `#action-log .turn-line[data-log-index="${entry.index}"]`);
  const lapsed = finish && line(finish) ? [...line(finish).querySelectorAll(
    '.logevent[data-event-kind="reveal_choice_lapsed"]')].map(read) : [];
  const sourced = entries
    .filter((e) => e.arguments && typeof e.arguments.source === 'string')
    .map((e) => line(e)).filter(Boolean)
    .map((n) => read(n.querySelector('.turn-action')));
  const shown = !document.getElementById('action-log').hidden;
  return { lapsed, events, sourced, shown };
}"""
)


def run_fixture(saves: str) -> dict:
    output = subprocess.run(
        [
            str(REPO / ".venv/bin/python"),
            str(Path(__file__).parent / "fixtures/reveal_choice_saves.py"),
            saves,
        ],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(output)


def open_save(browser, base: str, save_id: str, label: str):
    """A fresh game from the save, on a page holding every seat (open
    server): the page follows the seat to move, the revealing seat here."""

    context, page, rec = open_context(browser, label)
    page.goto(base + "/")
    page.wait_for_function("state.catalog !== null && state.server !== null")
    page.evaluate(
        """async (id) => {
          const summary = await api(`/saves/${id}/load`, { method: 'POST' });
          await openGame(summary.game_id);
        }""",
        save_id,
    )
    page.wait_for_function("state.view !== null && state.actions !== null")
    assert settled(page, 20), label
    return context, page


def panel(page) -> dict:
    return page.evaluate(PANEL_JS)


def set_language(page, lang: str) -> None:
    page.evaluate(f"setLanguage('{lang}')")
    assert settled(page, 10)


def click_row(page, index: int) -> None:
    page.locator(
        f"#actions .action-item[data-index='{index}'] > button:not(.action-info)"
    ).click()
    assert settled(page, 20)


def name_of(choice: dict, lang: str) -> str:
    return choice["name_ko"] if lang == "ko" else choice["name"]


def check_panel(page, label: str, lang: str) -> dict:
    """[1]/[2]: the headers, their rows, the buys, the waiting rows."""

    shown = panel(page)
    choices = shown["choices"]
    offered = [c for c in choices if c["offered"]]
    waiting = [c for c in choices if not c["offered"]]
    check.ok(
        [h["key"] for h in shown["headings"]] == [c["key"] for c in offered],
        f"{label}: one header per offered choice, in pending order",
        (shown["headings"], [c["key"] for c in offered]),
    )
    headed = {h["key"]: h for h in shown["headings"]}
    texts = []
    for choice in offered:
        heading = headed.get(choice["key"]) or {}
        text, note = heading.get("text") or "", heading.get("note") or ""
        texts.append((text, note))
        check.ok(
            text.startswith(name_of(choice, lang) + " — ")
            and NOTE[lang][choice["optional"]] in note
            and heading.get("noteOptional") == str(choice["optional"]).lower(),
            f"{label}: {choice['name']}'s header names the card and what it does,"
            f" and says it is {'optional' if choice['optional'] else 'mandatory'}",
            (text, note),
        )
    rows = {row["index"]: row for row in shown["rows"]}
    choice_rows = [a for a in shown["legal"] if a["reveal_choice"]]
    misplaced = [
        (a["index"], a["reveal_choice"], rows.get(a["index"], {}).get("group"))
        for a in choice_rows
        if rows.get(a["index"], {}).get("group") != a["reveal_choice"]
    ]
    strays = [
        row
        for row in shown["rows"]
        if row["group"] is not None
        and row["group"] != next(
            (a["reveal_choice"] for a in shown["legal"] if a["index"] == row["index"]),
            None,
        )
    ]
    check.ok(
        choice_rows and not misplaced and not strays,
        f"{label}: every choice row sits under its card's header, and only those",
        (misplaced, strays),
    )
    keys = {c["key"] for c in offered}
    check.ok(
        all(any(a["reveal_choice"] == key for a in choice_rows) for key in keys),
        f"{label}: every offered choice has a row",
        choice_rows,
    )
    buys = [a["index"] for a in shown["legal"] if a["action_id"].startswith("acquire")]
    check.ok(
        buys
        and all(i in rows and rows[i]["group"] is None for i in buys)
        and len({rows[i]["heading"] for i in buys if i in rows}) == 1,
        f"{label}: the cards to buy are ordinary rows under their own heading,"
        " beside the choices",
        [rows.get(i) for i in buys],
    )
    for choice in waiting:
        row = next(
            (g for g in shown["greyed"] if g["key"] == f"waiting:{choice['key']}"), None
        )
        body, badge = (row or {}).get("body") or "", (row or {}).get("badge") or ""
        check.ok(
            row is not None
            and row["group"] is None
            and body.startswith(name_of(choice, lang) + ": ")
            and badge.endswith(LAPSE[lang][choice["optional"]]),
            f"{label}: {choice['name']} waits greyed out, led by its card, with its"
            " reason and that it lapses when the Reveal ends",
            row,
        )
        if str(choice["effect"]).startswith("command_"):
            # {persuasion:6} is an amount: its number, then the icon's name.
            reason = (
                ("통솔: 이번 공개 차례에 만든 6설득 비용 필요", "(지금 ")
                if lang == "ko"
                else (
                    "Command: needs 6Persuasion generated this Reveal turn",
                    "(you have ",
                )
            )
            check.ok(
                badge.startswith(reason[0]) and reason[1] in badge,
                f"{label}: {choice['name']}'s reason is the Persuasion generated"
                " so far (Command 6+)",
                badge,
            )
    mandatory = any(not c["optional"] for c in offered)
    check.ok(
        not mandatory or (not shown["finish"] and not shown["turnEnd"]),
        f"{label}: no turn-end row while a mandatory choice is offered",
        (shown["finish"], shown["turnEnd"]),
    )
    ids = sorted(set(ENGINE_ID.findall(shown["text"])))
    check.ok(
        not ids and "출처" not in shown["text"] and "Source:" not in shown["text"],
        f"{label}: no engine id (a source card's id) in the panel",
        ids,
    )
    if lang == "en":
        check.ok(
            not HANGUL.search(shown["text"]),
            f"{label}: in English the panel holds no Hangul",
            HANGUL.findall(shown["text"])[:10],
        )
    return shown


def check_sandworm(page, label: str, lang: str) -> None:
    """Desert Power without Maker Hooks: its sandworm branch is greyed out
    under its header, beside the Persuasion branch (option (B))."""

    shown = panel(page)
    desert = next((c for c in shown["choices"] if "desert_power" in c["key"]), None)
    if desert is None:
        return
    row = next((g for g in shown["greyed"] if g["surface"] == "choice"), None)
    branch = next(
        (
            r
            for r in shown["rows"]
            if r["group"] == desert["key"]
            and any(
                a["index"] == r["index"] and a["action_id"] == "decline_reveal_sandworm"
                for a in shown["legal"]
            )
        ),
        None,
    )
    # The icon read as its name: {persuasion} is 설득 비용 in Korean.
    want = ("설득 비용 2 받기", "메이커 작살 없음") if lang == "ko" else (
        "Gain 2 Persuasion",
        "No Maker Hooks",
    )
    check.ok(
        row is not None
        and row["group"] == desert["key"]
        and row["badge"] == want[1]
        and branch is not None
        and branch["text"].endswith(": " + want[0]),
        f"{label}: Desert Power's Persuasion branch reads '{want[0]}' and its"
        " sandworm greys out under its header",
        (row, branch),
    )


def reveal_case(browser, base: str, fixture: dict, kind: str) -> None:
    print(f"[{kind}] seed {fixture['seed']}, seat {fixture['seat']}, round"
          f" {fixture['round']}: {[c['name'] for c in fixture['choices']]}")
    context, page = open_save(browser, base, fixture["save_id"], f"reveal-{kind}")
    since = page.evaluate(
        "((state.log && state.log.entries) || [])"
        ".reduce((n, e) => Math.max(n, e.index + 1), 0)"
    )
    shown = panel(page)
    facts = ("key", "effect", "optional", "offered")
    check.ok(
        shown["kind"] == "reveal"
        and shown["seat"] == fixture["seat"]
        and [[c[k] for k in facts] for c in shown["choices"]]
        == [[c[k] for k in facts] for c in fixture["choices"]],
        f"{kind} [1]: the page opens seat {fixture['seat']}'s Reveal with the"
        " fixture's choices",
        (shown["kind"], shown["seat"], shown["choices"]),
    )
    check_panel(page, f"{kind} [1] ko", "ko")
    check_sandworm(page, f"{kind} [1] ko", "ko")
    page.screenshot(path=str(SHOTS / f"reveal_choices_{kind}_ko.png"))

    set_language(page, "en")
    check_panel(page, f"{kind} [2] en", "en")
    check_sandworm(page, f"{kind} [2] en", "en")
    page.screenshot(path=str(SHOTS / f"reveal_choices_{kind}_en.png"))
    set_language(page, "ko")

    # [3] The mandatory choices, one at a time, and the gains the Reveal
    # must take anyway (a troop recruit, an Intrigue draw: OQ-045).
    answered: list[str] = []
    taken: list[str] = []
    held: list[bool] = []
    seen: set[str] = {c["key"] for c in panel(page)["choices"] if c["offered"]}
    for _ in range(12):
        shown = panel(page)
        seen |= {c["key"] for c in shown["choices"] if c["offered"]}
        if shown["finish"]:
            break
        mandatory = [c for c in shown["choices"] if c["offered"] and not c["optional"]]
        if mandatory:
            held.append(not shown["turnEnd"])
            first = next(r for r in shown["rows"] if r["group"] == mandatory[0]["key"])
            answered.append(mandatory[0]["name"])
            click_row(page, first["index"])
            continue
        gain = next(
            (a for a in shown["legal"] if a["action_id"] in REVEAL_GAINS), None
        )
        if gain is None:
            break
        taken.append(gain["action_id"])
        click_row(page, gain["index"])
    shown = panel(page)
    check.ok(
        held and all(held),
        f"{kind} [3]: no turn-end row while {answered} is offered",
        held,
    )
    check.ok(
        answered and shown["finish"] and shown["turnEnd"]
        and "턴 종료" in shown["turnEnd"][0],
        f"{kind} [3]: once {answered} answered (and {taken} taken), '턴 종료 ▶'"
        " is offered",
        (shown["finish"], shown["turnEnd"], shown["legal"]),
    )
    waiting = [c for c in fixture["choices"] if not c["offered"]]
    opened = [c["name"] for c in waiting if c["key"] in seen]
    if kind == "command":
        check.ok(
            opened == [c["name"] for c in waiting],
            f"{kind} [3]: the waiting Command choice opened as its own header once"
            " Desert Power's 2 Persuasion counted",
            (opened, waiting),
        )
    still = [c for c in shown["choices"] if c["offered"] and c["optional"]]
    check.ok(
        still and all(h["key"] in {c["key"] for c in still} for h in shown["headings"]),
        f"{kind} [3]: the optional choice is still on offer beside the turn end",
        shown["headings"],
    )
    pending = list(shown["choices"])
    page.locator("#decision-banner").screenshot(
        path=str(SHOTS / f"reveal_choices_{kind}_finish_ko.png")
    )

    # [4] The turn end: what is still pending lapses, in words.
    page.locator("#decision-info .turn-end-row button").click()
    assert settled(page, 30)
    log = page.evaluate(LOG_JS, [fixture["seat"], since])
    check.ok(
        sorted(log["events"]) == sorted(c["card_id"] for c in pending),
        f"{kind} [4]: every choice still pending lapsed with the Reveal",
        (log["events"], [c["card_id"] for c in pending]),
    )
    names_ko = sorted(c["name_ko"] for c in pending)
    shown_names = sorted(
        name for name in names_ko for line in log["lapsed"] if name in line
    )
    check.ok(
        log["shown"]
        and len(log["lapsed"]) >= len(pending)
        and all(line.startswith(LAPSED_LABEL["ko"]) for line in log["lapsed"])
        and set(shown_names) == set(names_ko)
        and not any(ENGINE_ID.search(line) for line in log["lapsed"]),
        f"{kind} [4]: the log says '{LAPSED_LABEL['ko']}' with each card's name",
        log["lapsed"],
    )
    plain = all(
        not ENGINE_ID.search(line) and "출처" not in line for line in log["sourced"]
    )
    check.ok(
        plain
        and (kind != "optional" or any(
            line.startswith("대중의 구경거리: ") for line in log["sourced"]
        )),
        f"{kind} [4]: a logged step naming its card reads the card's name, no id",
        log["sourced"],
    )
    page.locator(
        '#action-log .logevent[data-event-kind="reveal_choice_lapsed"]'
    ).last.scroll_into_view_if_needed()
    page.locator("#action-log").screenshot(
        path=str(SHOTS / f"reveal_choices_{kind}_log_ko.png")
    )
    set_language(page, "en")
    log = page.evaluate(LOG_JS, [fixture["seat"], since])
    names = {c["name"] for c in pending}
    check.ok(
        log["lapsed"]
        and all(line.startswith(LAPSED_LABEL["en"]) for line in log["lapsed"])
        and all(any(name in line for line in log["lapsed"]) for name in names)
        and not any(HANGUL.search(line) for line in (*log["lapsed"], *log["sourced"])),
        f"{kind} [4]: in English the log says '{LAPSED_LABEL['en']}' with each name",
        log["lapsed"],
    )
    set_language(page, "ko")
    context.close()


def main() -> None:
    saves = tempfile.mkdtemp(prefix="dune-reveal-choices-e2e-")
    fixtures = run_fixture(saves)
    SHOTS.mkdir(parents=True, exist_ok=True)
    with chrome() as browser:
        server = ServerProcess(saves=saves).start()
        try:
            for kind in ("optional", "command"):
                reveal_case(browser, server.base, fixtures[kind], kind)
        finally:
            server.stop()
    shutil.copy(server.log_path, SERVER_LOG_COPY)
    text = Path(server.log_path).read_text()
    check.ok(
        "Traceback" not in text and "ERROR" not in text,
        f"no server errors (see {SERVER_LOG_COPY})",
    )
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
