"""Face-up Intrigue cards are drawn in every seat's panel, for every viewer.

An Intrigue card that does nothing yet stays face up in front of its owner
([FAQ p. 2]: Call to Arms until the Conflict ends; a Reveal-turn Plot such as
Manipulate or Tleilaxu Puppet until the owner's Reveal turn ends). The engine
keeps it in the seat's public `intrigue_faceup`, and the seat panel shows it
as a card chip line outside the folded detail, so an opponent can see what
is pending. The two positions are real: `fixtures/intrigue_faceup_saves.py`
plays heuristic seats through the session manager (a base game, and an
Immortality game) and saves the first moment a seat holds the card face up.
Expected owners and cards come from that fixture's own output, never from the
rendered text. Checked in Korean and English (card names stay as printed in both), from
every viewer seat's own snapshot, with a 1366x768 window.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from common import LAPTOP_VIEWPORT, REPO, Check, ServerProcess, chrome, open_context
from open_mode import settled

check = Check()

ENGLISH_NAMES = {
    "call_to_arms": "Call to Arms",
    "manipulate": "Manipulate",
    "tleilaxu_puppet": "Tleilaxu Puppet",
}
# The Korean glossary calls the rule term "책략 카드"; card names stay as printed.
LABELS = {"ko": "공개 대기 책략 카드", "en": "Face-up Intrigue"}

LINES = """() => [...document.querySelectorAll('#seats .seat')].map((seat) => {
    const line = seat.querySelector('.faceup-intrigue');
    return {
        seat: Number(seat.dataset.seat),
        present: line !== null,
        shown: line !== null && line.getBoundingClientRect().height > 0
            && !line.closest('.seat-detail[hidden]'),
        label: line ? line.querySelector('strong').textContent.trim() : '',
        chips: line ? [...line.querySelectorAll('.tag')].map((t) => t.textContent) : [],
        clickable: line ? [...line.querySelectorAll('.tag.clickable')].length : 0,
        overflow: seat.scrollWidth > seat.clientWidth + 1,
    };
})"""


def check_lines(page, name: str, lang: str, faceup: dict, viewer: int) -> None:
    rows = page.evaluate(LINES)
    tag = f"{name}/{lang}/viewer {viewer}"
    check.ok([r["seat"] for r in rows] == [0, 1, 2, 3], f"{tag}: four seat panels")
    for row in rows:
        ids = faceup[str(row["seat"])]
        where = f"{tag}/seat {row['seat']}"
        if not ids:
            check.ok(not row["present"], f"{where}: no line when nothing is face up")
            continue
        check.ok(row["present"] and row["shown"], f"{where}: line shown", row)
        check.ok(row["label"] == LABELS[lang], f"{where}: label", row["label"])
        check.ok(len(row["chips"]) == len(ids), f"{where}: one chip per card", row)
        check.ok(row["clickable"] == len(ids), f"{where}: chips are card chips", row)
        expected = [ENGLISH_NAMES[i.split(":")[1]] for i in ids]
        check.ok(row["chips"] == expected, f"{where}: printed card names", row["chips"])
        check.ok(not row["overflow"], f"{where}: panel does not overflow", row)


def render_for(page, seat: int) -> None:
    """Draw the panels from `seat`'s own snapshot, as that seat's viewer."""
    page.evaluate(
        """async (seat) => {
            const response = await fetch(
                `/games/${state.gameId}/snapshot?seat=${seat}`);
            const snapshot = await response.json();
            state.viewSeat = seat;
            state.view = snapshot.view;
            renderSeats();
        }""",
        seat,
    )


def check_popover(page, owner: int, lang: str, tag: str) -> None:
    chip = page.locator(f".seat[data-seat='{owner}'] .faceup-intrigue .tag").first
    text = chip.text_content()
    chip.hover()
    page.wait_for_function(
        "document.getElementById('card-popover').classList.contains('hover')"
    )
    title = page.locator("#card-popover .popover-title").text_content()
    check.ok(title == text, f"{tag}: hover opens the card's popover", (title, text))
    chip.click()
    page.wait_for_function("popoverPinned === true")
    check.ok(
        page.locator("#card-popover .popover-title").text_content() == text,
        f"{tag}: click pins the card's popover",
    )
    page.keyboard.press("Escape")
    page.wait_for_function("popoverPinned === false")


def main() -> None:
    saves = tempfile.mkdtemp(prefix="dune-intrigue-faceup-e2e-")
    found = json.loads(
        subprocess.run(
            [
                str(REPO / ".venv/bin/python"),
                str(Path(__file__).parent / "fixtures/intrigue_faceup_saves.py"),
                saves,
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )
    server = ServerProcess(saves=saves).start()
    shots = os.environ.get("E2E_SHOTS_DIR")
    try:
        with chrome() as browser:
            for name, fixture in found.items():
                faceup = fixture["faceup"]
                owner = fixture["owner"]
                print(f"[{name}] {fixture['card_id']} face up for seat {owner}")
                for lang in ("ko", "en"):
                    _, page, _rec = open_context(
                        browser, f"{name}-{lang}", LAPTOP_VIEWPORT
                    )
                    page.goto(server.base + "/")
                    page.wait_for_function(
                        "document.querySelectorAll('#save-list li').length === 2"
                    )
                    page.locator(
                        f"#save-list li:has-text('{name}') button"
                    ).first.click()
                    page.wait_for_function(
                        "state.view !== null && refreshFlight === null"
                    )
                    page.evaluate("lang => setLanguage(lang)", lang)
                    assert settled(page, 20)
                    check.ok(
                        page.evaluate(
                            "state.view.players.map((p) => p.intrigue_faceup.length)"
                        )
                        == [len(faceup[str(s)]) for s in range(4)],
                        f"{name}/{lang}: the server view carries the fixture's cards",
                    )
                    for viewer in range(4):
                        render_for(page, viewer)
                        check_lines(page, name, lang, faceup, viewer)
                    render_for(page, owner)
                    check_popover(page, owner, lang, f"{name}/{lang}")
                    if shots:
                        Path(shots).mkdir(parents=True, exist_ok=True)
                        page.locator("#seats").screenshot(
                            path=str(Path(shots) / f"intrigue_faceup_{name}_{lang}.png")
                        )
    finally:
        server.stop()
    check.finish()


if __name__ == "__main__":
    main()
