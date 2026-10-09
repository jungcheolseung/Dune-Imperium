"""Real saved-game E2E of separate Tech purchase and Influence choices.

The fixture producer plays legal actions through GameSessionManager, then
saves just before each purchase. No edited UI state or injected resources:
the browser loads those replays, buys the tile, resolves another effect,
refreshes, and chooses a specific faction in Korean and English.

Right after the Glowglobes purchase the seat sees its deck's top card
(``private.peeked_card_id``; user decision 2026-10-10, feedback item 3): it is
marked "맨 위" in the deck list, the count's title says so, and nothing is left
beside the Intrigue cards. The Navigation Chamber buyer's list marks nothing.
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


DECK_TOP_JS = """() => {
  const stat = document.querySelector('#private-zone .hand-counts .stat');
  const cards = state.view.private.deck_cards || [];
  const peeked = state.view.private.peeked_card_id || '';
  return {
    peeked,
    inDeck: cards.includes(peeked),
    size: cards.length,
    owns: (state.view.players[state.view.player].tech_ids || []).includes('glowglobes'),
    title: stat.getAttribute('title'),
    strip: [...document.querySelectorAll('#private-zone .vcard')]
      .filter((card) => {
        const badge = card.querySelector('.vcard-badge');
        return badge && badge.textContent === t('panels.deck_top_badge');
      })
      .map((card) => card.dataset.instance),
  };
}"""

DECK_LIST_JS = """() => {
  const key = (id) => { const ref = instanceRef(id); return `${ref.kind}:${ref.id}`; };
  const pop = document.getElementById('card-popover');
  return {
    hidden: pop.hidden,
    topKey: state.view.private.peeked_card_id
      ? key(state.view.private.peeked_card_id) : null,
    notes: [...pop.querySelectorAll('.popover-note')].map((node) => node.textContent),
    marked: [...pop.querySelectorAll('.vcard.deck-top')].map((card) => ({
      key: key(card.dataset.instance),
      badge: card.querySelector('.vcard-badge').textContent,
    })),
  };
}"""


def check_deck_top(page, tech_id):
    """The bought Glowglobes shows the top card in the deck list only."""
    top = page.evaluate(DECK_TOP_JS)
    glow = tech_id == "glowglobes"
    if glow:
        check.ok(top["owns"], f"{tech_id}: the seat owns the tile after the purchase")
        check.ok(
            top["strip"] == [],
            f"{tech_id}: no top card is left beside the Intrigue cards",
            top["strip"],
        )
        if not check.ok(
            top["size"] > 0 and top["inDeck"],
            f"{tech_id}: the view names a card of the deck as its top",
            top,
        ):
            return
        check.ok(
            top["title"] == "카드덱 구성 보기 (순서 비공개, 맨 위 카드 표시)",
            f"{tech_id}: the deck count's title says the top card is marked",
            top["title"],
        )
    else:
        check.ok(
            not top["owns"] and top["peeked"] == "",
            f"{tech_id}: no top card is named without Glowglobes",
            top,
        )
        if not top["size"]:
            print(f"  .. {tech_id}: the deck is empty, no list to open")
            return
    page.locator("#private-zone .hand-counts .stat").first.click()
    page.wait_for_function("!document.getElementById('card-popover').hidden")
    listing = page.evaluate(DECK_LIST_JS)
    if glow:
        marked = listing["marked"]
        check.ok(
            len(marked) == 1
            and marked[0]["key"] == listing["topKey"]
            and marked[0]["badge"].startswith("맨 위"),
            f"{tech_id}: exactly the top card's group is marked 맨 위",
            listing,
        )
        check.ok(
            len(listing["notes"]) == 2 and "발광구" in listing["notes"][1],
            f"{tech_id}: the second note names Glowglobes as 발광구",
            listing["notes"],
        )
    else:
        check.ok(
            listing["marked"] == [] and len(listing["notes"]) == 1,
            f"{tech_id}: the deck list marks nothing",
            listing,
        )
    page.keyboard.press("Escape")


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
                check_deck_top(page, tech_id)
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
                if before[faction] >= 6:
                    # The Tech icon still offers a Faction at the top (a gain
                    # there is lost, OQ-060); pick one that can rise so the
                    # check below still sees a single +1. The saved game is a
                    # heuristic replay, so rule changes move its Influence
                    # (the codec v138 Intrigue gate put Bene Gesserit on 6).
                    faction = next(
                        f
                        for f in ("emperor", "spacing_guild", "bene_gesserit", "fremen")
                        if before[f] < 6
                    )
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
