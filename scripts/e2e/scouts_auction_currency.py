"""Show the auction's currency at the amount, buttons and Scouts panel.

Real engine/server payloads cover all eleven auctions, a sealed zero-only
bid, a single open call and a pass-only open auction. No bids are submitted
to the user's game; a UI callback records which legal index was selected.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from common import REPO, Check, chrome, open_context, server

check = Check()
SHOTS = Path(
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-auctions-")
)

FIXTURES = """
import json
from dataclasses import replace
from dune_imperium.content.arrakeen_scouts import AUCTIONS, AuctionKind
from dune_imperium.core import DomainAction, Resources
from dune_imperium.rules.scouts_auctions import offer_bid, offer_call, reveal_market
from dune_imperium.server.sessions import GameSessionManager

manager = GameSessionManager()
game = manager.create_game(("human",) * 4, game_seed=21, arrakeen_scouts=True,
                           choam_module=True, immortality=True)
game_id = str(game["game_id"])
session = manager._get(game_id)
base = session.state

def snapshot(state):
    session.state = state
    return {"summary": manager.summary(game_id), "view": manager.view(game_id, 0),
            "actions": manager.legal_actions(game_id, 0)}

fixtures = []
for auction in AUCTIONS:
    caps = (3, 1, 0) if auction.auction_id == "critical_moment_mid" else (3,)
    if auction.auction_id in ("highest_bidder_mid", "mercenaries"):
        caps = (3, 0)
    for cap in caps:
        round_number = auction.rounds[0]
        state = replace(base, round_number=round_number, first_player=0,
            players=tuple(replace(p, resources=Resources(
                              solari=cap if p.player_id == 0 else 73,
                              spice=cap if p.player_id == 0 else 73))
                          for p in base.players), decision_stack=(),
            scouts_item=auction.auction_id,
            scouts_revealed=((round_number, auction.auction_id),), scouts_tasks=(),
            scouts_bids=(), scouts_calls=(),
        )
        if auction.kind is AuctionKind.OPEN_CARDS:
            state = offer_call(reveal_market(state).state, 0, source="test").state
        else:
            state = offer_bid(state, 0, auction.auction_id, source="test").state
            hidden = 3 if auction.kind is AuctionKind.MERCENARIES else 73
            state = replace(state, scouts_bids=((1, hidden, True),))
        record = {"id": auction.auction_id, "currency": auction.currency,
                  "cap": cap, "open": auction.kind is AuctionKind.OPEN_CARDS,
                  "initial": snapshot(state)}
        if auction.kind is not AuctionKind.OPEN_CARDS:
            count = min(2, cap)
            chosen = session.engine.apply(state,
                DomainAction("scouts_bid", 0, (("count", count),))).state
            record["selected"] = snapshot(chosen)
        fixtures.append(record)
print(json.dumps(fixtures))
"""

RENDER = """({fixture, language}) => {
    setLanguage(language, false);
    Object.assign(state, fixture, {viewSeat: 0, me: {seats: [0, 1, 2, 3]},
        gameId: fixture.summary.game_id, review: null, busy: false,
        pick: null, counts: {}, log: {entries: []}});
    window.bidRequests = [];
    window.applyAction = (index) => window.bidRequests.push(index);
    showScreen('game-screen');
    render();
}"""


def main() -> None:
    result = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", FIXTURES],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    fixtures = json.loads(result.stdout)
    SHOTS.mkdir(parents=True, exist_ok=True)
    with server() as (base, _), chrome() as browser:
        context, page, recorder = open_context(browser, "auction-currency")
        page.goto(base)
        page.wait_for_function("state.catalog !== null")
        for language in ("ko", "en"):
            page.set_viewport_size({"width": 1366, "height": 900})
            for row in fixtures:
                currency = row["currency"]
                resource = {
                    "ko": {"solari": "솔라리", "spice": "스파이스"},
                    "en": {"solari": "Solari", "spice": "spice"},
                }[language]
                resource = resource[currency]
                where = f"{language} {row['id']} cap {row['cap']}"
                page.evaluate(RENDER, {"fixture": row["initial"], "language": language})
                icon_url = page.evaluate("key => state.catalog.icons[key]", currency)
                control = page.locator("#actions .scouts-auction-currency")
                description = page.locator(
                    f'#scouts-panel [data-item="{row["id"]}"] .scouts-auction-currency'
                )
                check.ok(
                    control.count() == 1
                    and resource in control.inner_text()
                    and control.locator(f'img[src="{icon_url}"]').count() == 1
                    and description.count() == 1
                    and resource in description.inner_text(),
                    f"{where}: controls and prize description name the bid resource",
                )
                stepper = page.locator("#actions .count-row")
                check.ok(
                    stepper.count() == 1
                    and resource in stepper.locator(".stepper-value").inner_text()
                    and resource in stepper.locator(".count-confirm").inner_text(),
                    f"{where}: amount and submit button both show the unit",
                )
                if row["open"] and row["cap"] == 0:
                    check.ok(
                        ("패스" if language == "ko" else "Pass")
                        in stepper.locator(".count-confirm").inner_text()
                        and all(
                            stepper.locator(".stepper button").nth(i).is_disabled()
                            for i in range(2)
                        ),
                        f"{where}: the zero-only call says pass and cannot increase",
                    )
                selected = 0
                if row["cap"] == 3:
                    while selected < 2:
                        stepper.locator(".stepper button").nth(1).click()
                        selected += 1
                    check.ok(
                        str(selected) in stepper.locator(".stepper-value").inner_text()
                        and resource in stepper.locator(".count-confirm").inner_text(),
                        f"{where}: changing the amount keeps the resource",
                    )
                stepper.locator(".count-confirm").click()
                expected = row["initial"]["actions"]["actions"]
                action_id = "scouts_call" if row["open"] else "scouts_bid"
                expected = next(
                    a["index"]
                    for a in expected
                    if a["action_id"] == action_id
                    and a["arguments"]["count"] == selected
                )
                check.ok(
                    page.evaluate("window.bidRequests") == [expected],
                    f"{where}: the control sends the original legal index",
                )
                if not row["open"]:
                    page.evaluate(
                        RENDER,
                        {
                            "fixture": row["selected"],
                            "language": language,
                        },
                    )
                    count = min(2, row["cap"])
                    button = page.locator("#decision-banner .turn-end-row button")
                    own = page.locator("#scouts-panel .scouts-own")
                    check.ok(
                        resource in button.inner_text()
                        and str(count) in button.inner_text()
                        and own.count() == 1
                        and resource in own.inner_text(),
                        f"{where}: final confirmation and own bid carry the unit",
                    )
                    check.ok(
                        "73" not in page.locator("#scouts-panel").inner_text(),
                        f"{where}: another player's sealed amount stays hidden",
                    )
                check.ok(
                    page.evaluate("""() => {
                    const box = document.getElementById('actions');
                    return box.scrollWidth <= box.clientWidth + 1;
                }"""),
                    f"{where}: the controls fit the laptop action panel",
                )
                if row["cap"] == 3 and row["id"] in (
                    "highest_bidder_mid",
                    "mercenaries",
                    "critical_moment_mid",
                ):
                    page.locator("#decision-banner").screenshot(
                        path=str(SHOTS / f"auction_{language}_{row['id']}.png")
                    )
            # Resource names remain visible without the private icon assets.
            page.evaluate(
                "window.auctionIcons = state.catalog.icons; "
                "state.catalog.icons = {}; render();"
            )
            check.ok(
                resource in page.locator("#actions").inner_text(),
                f"{language}: text remains when resource art is absent",
            )
            page.evaluate("state.catalog.icons = window.auctionIcons; render();")
        check.ok(not recorder.js_errors, "no JavaScript errors", recorder.js_errors)
        context.close()
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
