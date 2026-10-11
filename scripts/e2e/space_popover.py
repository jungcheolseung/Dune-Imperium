"""A board space's popover says the space in words (space_text.js, 2026-10-08).

The popover used to say what a space is only through its tile picture, and
the Swordmaster listed "8 Solari" and "6 Solari" without saying when 6
applies. This checks, in Korean and English:

- the meta line names the Agent icon the space takes, as the Board Guide
  heads each space ("Agent icon: Landsraad" [Board Guide pp. 1-2]), and
  whether it is a combat, Maker or Control space;
- the Swordmaster keeps both printed costs, in order, tags the one that
  applies now and dims the other: 8 Solari while no player has their
  Swordmaster, 6 once any player does [Board Guide p. 2]; its note says so;
- a Maker space shows the bonus spice lying on it now, the count the view
  holds;
- Sietch Tabr's note says what the Shield Wall does, with the Shield Wall
  and sandworm icons;
- the board list row (spaceRow) keeps its own flag words and tags the
  Swordmaster cost the same way.

Two real games: a new one (nobody has a Swordmaster, no bonus spice yet)
and a save from fixtures/space_popover_saves.py (a player has their
Swordmaster and bonus spice lies on Hagga Basin). Screenshots of the
Swordmaster, Hagga Basin and Sietch Tabr popovers in both languages go to
E2E_SHOTS_DIR (``space_popover_*``).
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
from lang import switch as switch_language
from open_mode import create_game, settled

check = Check()
VIEWPORT = {"width": 1440, "height": 900}

POPOVER_JS = """(spaceId) => {
  const entry = state.catalog.spaces[spaceId];
  const anchor = document.querySelector(`.hotspot[data-space='${spaceId}']`)
    || document.querySelector("header h1");
  openPopover(entry, anchor);
  const pop = document.getElementById("card-popover");
  const meta = pop.querySelector(".meta");
  const byUrl = new Map(Object.entries(state.catalog.icons || {}).map(
    ([name, url]) => [new URL(url, location.href).href, name]));
  const icons = (line) => [...line.querySelectorAll("img.icon")].map(
    (img) => byUrl.get(img.src) || img.src);
  const bonus = Object.fromEntries(state.view.maker_bonus_spice || []);
  return {
    meta: meta ? meta.textContent : "",
    options: [...pop.querySelectorAll(".option-line")].map((line) => ({
      now: line.classList.contains("space-cost-now"),
      later: line.classList.contains("space-cost-later"),
      tag: line.querySelector(".space-cost-tag")
        ? line.querySelector(".space-cost-tag").textContent : null,
      solari: line.querySelector(".cost .amount")
        ? line.querySelector(".cost .amount").firstChild.textContent : null,
    })),
    bonus: [...pop.querySelectorAll(".space-bonus")].map((line) => ({
      text: line.textContent, icons: icons(line),
    })),
    notes: [...pop.querySelectorAll(".popover-line.muted")].map((line) => ({
      text: line.textContent, icons: icons(line),
    })),
    viewBonus: spaceId in bonus ? bonus[spaceId] : null,
    anySwordmaster: state.view.players.some((p) => p.swordmaster_acquired),
  };
}"""

ROW_JS = """(spaceId) => {
  const row = spaceRow(spaceId, new Map(), new Map(), new Map());
  const flags = row.firstElementChild.querySelector(".muted");
  return {
    flags: flags ? flags.textContent : "",
    tags: [...row.querySelectorAll(".space-cost-tag")].map((tag) => tag.textContent),
    later: row.querySelectorAll(".space-cost-later").length,
  };
}"""

# The three spaces the Shield Wall guards, as each language names them (the
# Korean Board Space Guide's names since 2026-10-11).
CRITICAL_LOCATIONS = {
    "ko": ("아라킨", "스파이스 정제소", "제국 분지"),
    "en": ("Arrakeen", "Spice Refinery", "Imperial Basin"),
}

IMAGES_LOADED_JS = (
    "[...document.querySelectorAll('#card-popover img')]"
    ".every((img) => img.complete && img.naturalWidth > 0)"
)

WORDS = {
    "ko": {
        "landsraad": "에이전트 아이콘: 랜드스래드",
        "city": "에이전트 아이콘: 도시",
        "spice_trade": "에이전트 아이콘: 스파이스 거래",
        "combat": "⚔ 전투 장소",
        "maker": "메이커",
        "control": "지배",
        "now": "지금 적용",
        "swordmaster_note": "소드마스터",
    },
    "en": {
        "landsraad": "Agent icon: Landsraad",
        "city": "Agent icon: City",
        "spice_trade": "Agent icon: Spice Trade",
        "combat": "⚔ Combat space",
        "maker": "Maker",
        "control": "Control",
        "now": "applies now",
        "swordmaster_note": "Swordmaster",
    },
}


def popover(page, space_id: str) -> dict:
    result = page.evaluate(POPOVER_JS, space_id)
    page.wait_for_function(IMAGES_LOADED_JS)
    return result


def shoot(page, shots: Path | None, name: str) -> None:
    if shots is not None:
        page.locator("#card-popover").screenshot(path=str(shots / name))


def check_meta(
    lang: str, space_id: str, shown: dict, *, area: str, flags: tuple
) -> None:
    words = WORDS[lang]
    parts = [part.strip() for part in shown["meta"].split("·")]
    expected = [words[area], *(words[flag] for flag in flags)]
    check.ok(
        parts[: len(expected)] == expected,
        f"{lang} {space_id}: the meta line names its Agent icon and marks",
        (parts, expected),
    )


def check_swordmaster(lang: str, shown: dict, *, someone_has_one: bool) -> None:
    words = WORDS[lang]
    options = shown["options"]
    check.ok(
        shown["anySwordmaster"] == someone_has_one,
        f"{lang} Swordmaster: the table is the one this check expects",
        shown["anySwordmaster"],
    )
    check.ok(
        [option["solari"] for option in options] == ["8", "6"],
        f"{lang} Swordmaster: both printed costs stay listed, 8 then 6",
        options,
    )
    now = 1 if someone_has_one else 0
    check.ok(
        len(options) == 2
        and options[now]["now"]
        and options[now]["tag"] == words["now"]
        and options[1 - now]["later"]
        and options[1 - now]["tag"] is None,
        f"{lang} Swordmaster: the {options[now]['solari'] if options else '?'}"
        " Solari line is tagged as applying now, the other dimmed",
        options,
    )
    notes = shown["notes"]
    check.ok(
        len(notes) == 1
        and words["swordmaster_note"] in notes[0]["text"]
        and notes[0]["icons"].count("solari") == 2,
        f"{lang} Swordmaster: the note says when each cost applies",
        notes,
    )


def check_bonus(lang: str, space_id: str, shown: dict, *, at_least: int) -> None:
    lines = shown["bonus"]
    count = shown["viewBonus"]
    match = re.search(r"(\d+)\s*$", lines[0]["text"]) if lines else None
    check.ok(
        count is not None
        and count >= at_least
        and len(lines) == 1
        and match is not None
        and int(match.group(1)) == count
        and "spice" in lines[0]["icons"],
        f"{lang} {space_id}: the popover shows the bonus spice lying there ({count})",
        (lines, count),
    )


def check_sietch_tabr(lang: str, shown: dict) -> None:
    notes = shown["notes"]
    check.ok(
        len(notes) == 1
        and notes[0]["icons"].count("shield_wall") == 1
        and notes[0]["icons"].count("sandworm") == 2
        and all(name in notes[0]["text"] for name in CRITICAL_LOCATIONS[lang]),
        f"{lang} Sietch Tabr: the note says what the Shield Wall does",
        notes,
    )
    check.ok(
        not shown["bonus"], f"{lang} Sietch Tabr: no bonus line on a non-Maker space"
    )


def check_rows(page, lang: str) -> None:
    words = WORDS[lang]
    sword = page.evaluate(ROW_JS, "swordmaster")
    check.ok(
        sword["tags"] == [words["now"]]
        and sword["later"] == 1
        and sword["flags"] == "",
        f"{lang} board list: the Swordmaster row tags its cost the same way",
        sword,
    )
    hagga = page.evaluate(ROW_JS, "hagga_basin")
    check.ok(
        hagga["flags"] == f"{words['combat']} · {words['maker']}" and not hagga["tags"],
        f"{lang} board list: the Hagga Basin row keeps its flag words",
        hagga,
    )
    basin = page.evaluate(ROW_JS, "imperial_basin")
    check.ok(
        basin["flags"] == f"{words['combat']} · {words['maker']} · {words['control']}",
        f"{lang} board list: the Imperial Basin row keeps its Control word",
        basin,
    )


def new_game(browser, base: str) -> None:
    print("[1] a new game: nobody has a Swordmaster, no bonus spice yet")
    context, page, _rec = open_context(browser, "space-popover-new", VIEWPORT)
    create_game(page, base, humans=(0,))
    settled(page)
    for lang in ("ko", "en"):
        switch_language(page, lang)
        shown = popover(page, "swordmaster")
        check_meta(lang, "swordmaster", shown, area="landsraad", flags=())
        check_swordmaster(lang, shown, someone_has_one=False)
        hall = popover(page, "assembly_hall")
        check_meta(lang, "assembly_hall", hall, area="landsraad", flags=())
        check.ok(
            WORDS[lang]["combat"] not in hall["meta"] and not hall["bonus"],
            f"{lang} Assembly Hall: no combat mark and no bonus line",
            hall,
        )
        hagga = popover(page, "hagga_basin")
        check_meta(
            lang, "hagga_basin", hagga, area="spice_trade", flags=("combat", "maker")
        )
        check_bonus(lang, "hagga_basin", hagga, at_least=0)
        basin = popover(page, "imperial_basin")
        check_meta(
            lang,
            "imperial_basin",
            basin,
            area="spice_trade",
            flags=("combat", "maker", "control"),
        )
        sietch = popover(page, "sietch_tabr")
        check_meta(lang, "sietch_tabr", sietch, area="city", flags=("combat",))
        check_sietch_tabr(lang, sietch)
        check_rows(page, lang)
    context.close()


def saved_game(browser, base: str, shots: Path | None) -> None:
    print("[2] a saved game: a Swordmaster is out, bonus spice on Hagga Basin")
    context, page, _rec = open_context(browser, "space-popover-saved", VIEWPORT)
    page.goto(base + "/")
    page.locator("#save-list li:has-text('space-popover') button").first.click()
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page, 20)
    for lang in ("ko", "en"):
        switch_language(page, lang)
        shown = popover(page, "swordmaster")
        check_meta(lang, "swordmaster", shown, area="landsraad", flags=())
        check_swordmaster(lang, shown, someone_has_one=True)
        shoot(page, shots, f"space_popover_swordmaster_{lang}.png")
        hagga = popover(page, "hagga_basin")
        check_meta(
            lang, "hagga_basin", hagga, area="spice_trade", flags=("combat", "maker")
        )
        check_bonus(lang, "hagga_basin", hagga, at_least=1)
        shoot(page, shots, f"space_popover_hagga_basin_{lang}.png")
        sietch = popover(page, "sietch_tabr")
        check_meta(lang, "sietch_tabr", sietch, area="city", flags=("combat",))
        check_sietch_tabr(lang, sietch)
        shoot(page, shots, f"space_popover_sietch_tabr_{lang}.png")
        check_rows(page, lang)
    context.close()


def main() -> None:
    shots_dir = os.environ.get("E2E_SHOTS_DIR")
    shots = Path(shots_dir) if shots_dir else None
    if shots is not None:
        shots.mkdir(parents=True, exist_ok=True)
    saves = tempfile.mkdtemp(prefix="dune-space-popover-e2e-")
    found = json.loads(
        subprocess.run(
            [
                str(REPO / ".venv/bin/python"),
                str(Path(__file__).parent / "fixtures/space_popover_saves.py"),
                saves,
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    print(f"fixtures: {found}")
    server = ServerProcess(saves=saves).start()
    try:
        with chrome() as browser:
            new_game(browser, server.base)
            saved_game(browser, server.base, shots)
    finally:
        server.stop()
        shutil.copy(server.log_path, SERVER_LOG_COPY)
    text = server.log_path.read_text()
    check.ok(
        "Traceback" not in text and "ERROR" not in text,
        f"no server errors (see {SERVER_LOG_COPY})",
    )
    check.finish()


if __name__ == "__main__":
    main()
