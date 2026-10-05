"""Real saved-game E2E of separate Tech purchase and Influence choices.

The fixture producer plays legal actions through GameSessionManager, then
saves just before each purchase. No edited UI state or injected resources:
the browser loads those replays, buys the tile, resolves another effect,
refreshes, and chooses a specific faction in Korean and English.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from common import REPO, Check, ServerProcess, chrome, open_context
from open_mode import settled

check = Check()


def rows(page, action_id):
    return page.evaluate(
        "id => state.actions.actions.filter(a => a.action_id === id)", action_id
    )


def click_action(page, action):
    page.locator(f".action-item[data-index='{action['index']}'] > button").first.click()
    assert settled(page, 20)


def main():
    saves = tempfile.mkdtemp(prefix="dune-tech-acquire-e2e-")
    subprocess.run(
        [
            str(REPO / ".venv/bin/python"),
            str(Path(__file__).parent / "fixtures/tech_acquire_saves.py"),
            saves,
        ],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    server = ServerProcess(saves=saves).start()
    try:
        with chrome() as browser:
            for tech_id, lang, faction in (
                ("glowglobes", "ko", "fremen"),
                ("navigation_chamber", "en", "bene_gesserit"),
            ):
                _, page, rec = open_context(browser, tech_id)
                page.goto(server.base + "/")
                page.wait_for_function(
                    "document.querySelectorAll('#save-list li').length === 2"
                )
                page.locator(
                    f"#save-list li:has-text('{tech_id}') button"
                ).first.click()
                page.wait_for_function("state.view !== null && refreshFlight === null")
                page.evaluate("lang => setLanguage(lang)", lang)
                assert settled(page, 20)
                before = page.evaluate("state.view.players[state.viewSeat].influence")
                offers = [
                    a
                    for a in rows(page, "acquire_tech")
                    if a["arguments"]["tech_id"] == tech_id
                ]
                check.ok(len(offers) == 1, f"{tech_id}: exactly one purchase button")
                click_action(page, offers[0])
                check.ok(
                    page.evaluate("state.view.players[state.viewSeat].influence")
                    == before,
                    f"{tech_id}: purchase leaves every Influence unchanged",
                )
                rewards = [
                    a
                    for a in rows(page, "resolve_tech_acquire_effect")
                    if a["arguments"]["tech_id"] == tech_id
                ]
                check.ok(
                    {a["arguments"].get("faction") for a in rewards}
                    == {"emperor", "spacing_guild", "bene_gesserit", "fremen"},
                    f"{tech_id}: four explicit faction choices",
                )
                texts = [
                    page.locator(
                        f".action-item[data-index='{a['index']}']"
                    ).inner_text()
                    for a in rewards
                ]
                check.ok(
                    len(set(texts)) == 4, f"{tech_id}: distinct visible labels", texts
                )
                check.ok(
                    all("{" not in t for t in texts),
                    f"{tech_id}: no raw placeholders",
                    texts,
                )
                check.ok(
                    not rows(page, "finish_agent_turn"),
                    f"{tech_id}: reward blocks turn end",
                )
                others = rows(page, "resolve_board_effect")
                check.ok(
                    bool(others), f"{tech_id}: another board effect remains selectable"
                )
                if others:
                    click_action(page, others[0])
                    check.ok(
                        page.evaluate("state.view.players[state.viewSeat].influence")
                        == before,
                        f"{tech_id}: another effect runs before Influence",
                    )
                page.reload()
                page.wait_for_function("state.view !== null && refreshFlight === null")
                assert settled(page, 20)
                rewards = rows(page, "resolve_tech_acquire_effect")
                selected = next(
                    a for a in rewards if a["arguments"].get("faction") == faction
                )
                check.ok(
                    bool(selected.get("detail_ko")),
                    f"{tech_id}: localized reward description",
                )
                shots = os.environ.get("E2E_SHOTS_DIR")
                if shots:
                    Path(shots).mkdir(parents=True, exist_ok=True)
                    page.screenshot(
                        path=str(Path(shots) / f"tech_{tech_id}_{lang}.png"),
                        full_page=True,
                    )
                click_action(page, selected)
                after = page.evaluate("state.view.players[state.viewSeat].influence")
                expected = {**before, faction: before[faction] + 1}
                check.ok(
                    after == expected,
                    f"{tech_id}: only the selected faction gains one",
                    after,
                )
                check.ok(
                    not rows(page, "resolve_tech_acquire_effect"),
                    f"{tech_id}: reward is used once",
                )
                check.ok(
                    not rec.js_errors, f"{tech_id}: no JavaScript errors", rec.js_errors
                )
                page.close()
        check.ok("Traceback" not in server.log_path.read_text(), "no server exceptions")
    finally:
        server.stop()
    check.finish()


if __name__ == "__main__":
    main()
