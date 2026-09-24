"""Two-press delete on the saved-game list (ITEM 8d, 2026-09-25).

The setup screen's "삭제" button used to delete a save at once, sitting right
next to an identical "불러오기" button -- in the remote first game the host
restores from the autosave entry in this list after a crash, so one misclick
there loses the only recovery point. A first click now only arms the button
(text -> "정말 삭제?"/"Delete for good?", its own .save-delete.armed style); a
second click on the *same* button within a few seconds (screens.js
SAVE_DELETE_ARM_MS) deletes for good. Anything else -- the timeout, a click
on a different target, or the list being redrawn -- reverts it, and only one
button is armed at a time.

An open (local) server is enough: /saves needs no admin key there
(sessions.is_admin: "An open server has no admin: every caller may do
everything").
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any

from common import Check, ServerProcess, chrome, client_state, open_context

check = Check()

# Every Hangul run: the English side of the confirm text must have none.
HANGUL = re.compile("[가-힣]")

# screens.js: a second click within this window (SAVE_DELETE_ARM_MS) deletes;
# waited out a little past it so the revert is unambiguous.
ARM_MS = 4000

STATE_JS = """(name) => {
  const li = [...document.querySelectorAll('#save-list li')]
    .find((row) => row.textContent.includes(name));
  if (!li) return null;
  const buttons = [...li.querySelectorAll('button')];
  const load = buttons[0];
  const del = buttons[buttons.length - 1];
  return {
    delete: del ? { text: del.textContent, className: del.className,
                     armed: del.classList.contains('armed') } : null,
    load: load ? { text: load.textContent, className: load.className } : null,
  };
}"""

CLICK_DELETE_JS = """(name) => {
  const li = [...document.querySelectorAll('#save-list li')]
    .find((row) => row.textContent.includes(name));
  const btn = li ? [...li.querySelectorAll('button')].pop() : null;
  if (!btn) return false;
  btn.click();
  return true;
}"""


def _api_post(base: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        result: dict[str, Any] = json.loads(response.read())
    return result


def make_save(base: str, name: str) -> tuple[str, str]:
    """A fresh game (one human seat, resting on its first decision) saved
    under `name`; returns (game_id, save_id)."""
    summary = _api_post(
        base, "/games", {"seats": ["human", "heuristic", "heuristic", "heuristic"]}
    )
    saved = _api_post(base, f"/games/{summary['game_id']}/save", {"name": name})
    return str(summary["game_id"]), str(saved["save_id"])


def state(page, name: str) -> dict | None:
    return page.evaluate(STATE_JS, name)


# state() can return None (row not found at all); these read through that
# gap instead of letting every later check crash on the first missing field
# (an A/B run against the old client should report failing checks, not one
# traceback).
def delete_of(s: dict | None) -> dict:
    if s and s.get("delete"):
        return s["delete"]
    return {"text": None, "armed": None, "className": ""}


def load_of(s: dict | None) -> dict:
    if s and s.get("load"):
        return s["load"]
    return {"text": None, "className": ""}


def click_delete(page, name: str) -> bool:
    return page.evaluate(CLICK_DELETE_JS, name)


def row_count(page) -> int:
    return page.evaluate("document.querySelectorAll('#save-list li').length")


def click_elsewhere(page) -> None:
    """A neutral spot far from the save list -- not any armed button."""
    page.click("#setup-screen h2")


def wait_ok(page, js: str, timeout: int = 5000) -> bool:
    """`wait_for_function` without raising: a condition the old client can
    never reach (no .save-delete class to switch over) should read as a
    failed check here, not crash the whole A/B run."""
    try:
        return bool(page.wait_for_function(js, timeout=timeout))
    except Exception:
        return False


def main() -> None:
    saves_dir = tempfile.mkdtemp(prefix="dune-e2e-save-delete-")
    server = ServerProcess(saves=saves_dir).start()
    try:
        with chrome() as browser:
            _, page, rec = open_context(browser, "saves")

            _, alpha_id = make_save(server.base, "SaveAlpha")
            _, bravo_id = make_save(server.base, "SaveBravo")
            _, charlie_id = make_save(server.base, "SaveCharlie")

            page.goto(server.base + "/")
            page.wait_for_selector("#setup-screen:not([hidden])")
            page.wait_for_function("document.querySelectorAll('#save-list li').length === 3")

            print("[1] the delete button has its own class, apart from Load")
            alpha = delete_of(state(page, "SaveAlpha"))
            check.ok(alpha["text"] is not None, "delete button found")
            # Found by position (last button in the row) above, so this checks
            # the .save-delete class itself rather than assuming it (the old
            # client's identical-looking delete button carries no such class).
            check.ok("save-delete" in alpha["className"], "delete button carries the save-delete class", alpha)
            check.ok(alpha["text"] == "삭제", "starts unarmed, reading 삭제", alpha)
            check.ok(alpha["armed"] is False, "not armed at rest", alpha)
            alpha_load = load_of(state(page, "SaveAlpha"))
            check.ok(
                alpha_load["text"] == "불러오기" and "save-delete" not in alpha_load["className"],
                "Load keeps its own class and text",
                alpha_load,
            )

            print("[2] one click arms it but does not delete; it reverts on its own")
            check.ok(click_delete(page, "SaveAlpha"), "clicked SaveAlpha's delete once")
            armed = delete_of(state(page, "SaveAlpha"))
            check.ok(armed["armed"] is True, "armed after one click", armed)
            check.ok(armed["text"] == "정말 삭제?", "button reads the confirm text", armed)
            page.wait_for_timeout(700)
            check.ok(row_count(page) == 3, "one click alone has not deleted the entry")
            page.wait_for_timeout(ARM_MS - 700 + 400)
            reverted = delete_of(state(page, "SaveAlpha"))
            check.ok(reverted["armed"] is False, "armed reverts after the timeout", reverted)
            check.ok(reverted["text"] == "삭제", "text is back to 삭제", reverted)
            check.ok(row_count(page) == 3, "still three saves after the timeout")

            print("[3] only one button is armed at a time; a click elsewhere reverts it")
            check.ok(click_delete(page, "SaveAlpha"), "armed SaveAlpha again")
            check.ok(click_delete(page, "SaveBravo"), "then clicked SaveBravo's delete")
            after_bravo = delete_of(state(page, "SaveAlpha"))
            check.ok(
                after_bravo["armed"] is False,
                "arming a different button disarms SaveAlpha",
                after_bravo,
            )
            bravo_armed = delete_of(state(page, "SaveBravo"))
            check.ok(
                bravo_armed["armed"] is True, "SaveBravo is the one now armed", bravo_armed
            )
            click_elsewhere(page)
            bravo_after = delete_of(state(page, "SaveBravo"))
            check.ok(
                bravo_after["armed"] is False,
                "a click elsewhere reverts the armed button",
                bravo_after,
            )
            check.ok(row_count(page) == 3, "nothing was deleted by any of this")

            print("[4] a double-click only arms; a second click after it deletes for good")
            page.dblclick('#save-list li:has-text("SaveCharlie") button:last-of-type')
            page.wait_for_timeout(700)
            check.ok(row_count(page) == 3, "a double-click alone has not deleted the entry")
            check.ok(
                delete_of(state(page, "SaveCharlie"))["armed"] is True,
                "and it left the button armed",
            )
            check.ok(click_delete(page, "SaveCharlie"), "clicked it once more")
            ok = wait_ok(page, "document.querySelectorAll('#save-list li').length === 2")
            check.ok(ok, "the list drops to two entries")
            check.ok(state(page, "SaveCharlie") is None, "SaveCharlie is gone from the list")
            saves_now = json.loads(
                page.evaluate("fetch('/saves').then((r) => r.text())")
            )
            check.ok(
                all(entry.get("save_id") != charlie_id for entry in saves_now),
                "and gone from the server's own listing",
                saves_now,
            )
            check.ok(
                not (Path(saves_dir) / f"{charlie_id}.json").exists(),
                "and its file is off disk",
            )
            check.ok(
                (Path(saves_dir) / f"{alpha_id}.json").exists()
                and (Path(saves_dir) / f"{bravo_id}.json").exists(),
                "the other two saves are untouched",
            )

            print("[5] English: the confirm text has no Hangul")
            page.click("#language-toggle")
            # Not just the count (unchanged by a language switch): the list is
            # rebuilt asynchronously (loadSaveList awaits /saves), so wait for
            # the button text itself to have turned over to English. (On the
            # old client there is no .save-delete button to find, so this
            # times out and reads false -- still no crash.)
            switched = wait_ok(
                page,
                "() => {"
                " const li = [...document.querySelectorAll('#save-list li')]"
                "   .find((row) => row.textContent.includes('SaveAlpha'));"
                " const btn = li && li.querySelector('button.save-delete');"
                " return document.documentElement.lang === 'en'"
                "   && Boolean(btn) && btn.textContent === 'Delete';"
                " }",
            )
            check.ok(switched, "the list turned over to English")
            resting = delete_of(state(page, "SaveAlpha"))
            resting_load = load_of(state(page, "SaveAlpha"))
            check.ok(
                resting["text"] == "Delete" and resting_load["text"] == "Load",
                "English at rest: Delete / Load, no Hangul",
                (resting, resting_load),
            )
            check.ok(click_delete(page, "SaveAlpha"), "clicked SaveAlpha's delete in English")
            confirm = delete_of(state(page, "SaveAlpha"))
            check.ok(confirm["text"] == "Delete for good?", "English confirm text", confirm)
            check.ok(
                confirm["text"] is not None and not HANGUL.search(confirm["text"]),
                "no Hangul in the English confirm text",
                confirm,
            )
            page.wait_for_timeout(ARM_MS + 400)
            settled = delete_of(state(page, "SaveAlpha"))
            check.ok(settled["armed"] is False, "reverts in English too", settled)
            check.ok(row_count(page) == 2, "SaveAlpha and SaveBravo remain")

            print("[6] errors")
            page_errors = [
                e for e in rec.js_errors if "Failed to load resource" not in e
            ]
            check.ok(not page_errors, "no JS exceptions", page_errors)
            bad = "Traceback" in server.log_path.read_text()
            check.ok(not bad, f"no errors in the server log ({server.log_path})")
            if check.failed:
                print(json.dumps(client_state(page), ensure_ascii=False))
    finally:
        server.stop()
    check.finish()


if __name__ == "__main__":
    started = time.monotonic()
    try:
        main()
    finally:
        print(f"({time.monotonic() - started:.1f}s)", file=sys.stderr)
