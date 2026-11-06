"""Show the auction's currency at the amount, buttons and Scouts panel.

Real engine/server payloads cover every auction -- Uprising's eleven on an
Uprising table, the original game's four (stage P8: Mentat's open auction,
Treachery's sealed one) on an original one -- a sealed zero-only bid, a
single open call and a pass-only open auction. Two open auctions after
another seat's call of 2: Critical Moment skips the amount already called
(docs/rules/arrakeen-scouts.md 8.3), Mentat takes only a higher call
(OQ-162), each saying so beside the stepper, and the Scouts panel lists the
calls in the auction's currency. No bids are submitted to the user's game;
a UI callback records which legal index was selected.
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
from dune_imperium.agents.agent_turn_steps import apply_whole
from dune_imperium.content.arrakeen_scouts import AUCTIONS, AuctionKind
from dune_imperium.core import DomainAction, Resources
from dune_imperium.rules.scouts_auctions import offer_bid, offer_call, reveal_market
from dune_imperium.server.sessions import GameSessionManager

manager = GameSessionManager()
tables = {}
for name, options in (
    ("uprising", {"choam_module": True}),
    ("imperium", {"base_game": "imperium"}),
):
    game = manager.create_game(("human",) * 4, game_seed=21, arrakeen_scouts=True,
                               immortality=True, **options)
    tables[name] = str(game["game_id"])

def snapshot(state, table):
    game_id = tables[table]
    manager._get(game_id).state = state
    return {"summary": manager.summary(game_id), "view": manager.view(game_id, 0),
            "actions": manager.legal_actions(game_id, 0)}

OPEN = (AuctionKind.OPEN_CARDS, AuctionKind.OPEN_MENTAT)
fixtures = []
for auction in AUCTIONS:
    # The original game's own auctions on an original table (stage P8).
    table = "uprising" if any(p.value.startswith("uprising") for p in auction.pools) \
        else "imperium"
    base = manager._get(tables[table]).state
    caps = (3, 1, 0) if auction.auction_id == "critical_moment_mid" else (3,)
    if auction.auction_id in ("highest_bidder_mid", "mercenaries", "mentat_mid"):
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
        elif auction.kind is AuctionKind.OPEN_MENTAT:
            state = offer_call(state, 0, source="test").state
        else:
            state = offer_bid(state, 0, auction.auction_id, source="test").state
            hidden = 3 if auction.kind is AuctionKind.MERCENARIES else 73
            state = replace(state, scouts_bids=((1, hidden, True),))
        record = {"id": auction.auction_id, "currency": auction.currency,
                  "cap": cap, "open": auction.kind in OPEN,
                  "initial": snapshot(state, table)}
        if auction.kind not in OPEN:
            count = min(2, cap)
            engine = manager._get(tables[table]).engine
            chosen = apply_whole(engine, state,
                DomainAction("scouts_bid", 0, (("count", count),))).state
            record["selected"] = snapshot(chosen, table)
        fixtures.append(record)

# After seat 3 has called 2. Critical Moment: "이미 나온 액수와 같은 액수는 부를
# 수 없다" (docs/rules/arrakeen-scouts.md 8.3), so seat 0's calls skip 2. The
# original game's Mentat: a call must be higher than the highest (OQ-162), so
# seat 0 may call 3 or pass.
for auction_id, table in (
    ("critical_moment_mid", "uprising"), ("mentat_mid", "imperium"),
):
    auction = next(a for a in AUCTIONS if a.auction_id == auction_id)
    base = manager._get(tables[table]).state
    state = replace(base, round_number=auction.rounds[0], first_player=3,
        players=tuple(replace(p, resources=Resources(solari=3, spice=3))
                      for p in base.players), decision_stack=(),
        scouts_item=auction.auction_id,
        scouts_revealed=((auction.rounds[0], auction.auction_id),), scouts_tasks=(),
        scouts_bids=(), scouts_calls=(),
    )
    # The market opens with no calls; seat 3's call of 2 comes before seat 0's.
    if auction.kind is AuctionKind.OPEN_CARDS:
        state = reveal_market(state).state
    state = offer_call(replace(state, scouts_calls=((3, 2),)), 0, source="test").state
    fixtures.append({"id": auction.auction_id, "currency": auction.currency, "cap": 3,
                     "open": True, "called": [2], "initial": snapshot(state, table)})
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
                if row.get("called"):
                    continue
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
                turn_end = page.locator("#decision-banner .turn-end-row button")
                check.ok(
                    stepper.count() == 1
                    and resource in stepper.locator(".stepper-value").inner_text()
                    and stepper.locator(".count-confirm").count() == 0
                    and turn_end.count() == 1
                    and resource in turn_end.inner_text(),
                    f"{where}: the stepper only sets the amount; the turn-end "
                    "press names the unit",
                )
                end_word = "턴 종료" if language == "ko" else "End turn"
                pass_word = "패스" if language == "ko" else "Pass"
                if row["open"] and row["cap"] == 0:
                    check.ok(
                        pass_word in turn_end.inner_text()
                        and end_word in turn_end.inner_text()
                        and all(
                            stepper.locator(".stepper button").nth(i).is_disabled()
                            for i in range(2)
                        ),
                        f"{where}: the zero-only call passes with the turn end",
                    )
                selected = 0
                if row["cap"] == 3:
                    while selected < 2:
                        stepper.locator(".stepper button").nth(1).click()
                        selected += 1
                    check.ok(
                        str(selected) in stepper.locator(".stepper-value").inner_text()
                        and str(selected) in turn_end.inner_text()
                        and resource in turn_end.inner_text(),
                        f"{where}: changing the amount keeps the resource",
                    )
                check.ok(
                    page.evaluate("window.bidRequests") == [],
                    f"{where}: setting the amount sends nothing",
                )
                turn_end.click()
                legal = row["initial"]["actions"]["actions"]
                action_id = "scouts_call" if row["open"] else "scouts_bid"
                if not row["open"] and selected == 0:
                    # Confirming with no bid chosen confirms 0 (the engine).
                    action_id = "confirm_scouts_bid"
                expected = next(
                    a["index"]
                    for a in legal
                    if a["action_id"] == action_id
                    and a["arguments"].get("count", 0) == selected
                )
                check.ok(
                    page.evaluate("window.bidRequests") == [expected],
                    f"{where}: the turn-end press sends the original legal index",
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
                        and end_word in button.inner_text()
                        and own.count() == 1
                        and resource in own.inner_text(),
                        f"{where}: final confirmation and own bid carry the unit",
                    )
                    button.click()
                    confirm = next(
                        a["index"]
                        for a in row["selected"]["actions"]["actions"]
                        if a["action_id"] == "confirm_scouts_bid"
                    )
                    check.ok(
                        page.evaluate("window.bidRequests") == [confirm],
                        f"{where}: the recorded bid is confirmed by one press",
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
            for row in (r for r in fixtures if r.get("called")):
                mentat = row["id"] == "mentat_mid"
                where = f"{language} {row['id']}"
                page.evaluate(RENDER, {"fixture": row["initial"], "language": language})
                stepper = page.locator("#actions .count-row")
                note = stepper.locator(".scouts-called-note")
                words = {
                    (False, "ko"): "부를 수 없음",
                    (False, "en"): "cannot be called again",
                    (True, "ko"): "더 높게만",
                    (True, "en"): "only a higher call",
                }[mentat, language]
                check.ok(
                    note.count() == 1
                    and "2" in note.inner_text()
                    and words in note.inner_text(),
                    f"{where}: the call stepper says which amounts are left",
                    note.all_inner_texts(),
                )
                seen = [stepper.locator(".stepper-value").inner_text().split()[0]]
                for _ in range(1 if mentat else 2):
                    stepper.locator(".stepper button").nth(1).click()
                    seen.append(stepper.locator(".stepper-value").inner_text().split()[0])
                check.ok(
                    seen == (["0", "3"] if mentat else ["0", "1", "3"])
                    and stepper.locator(".stepper button").nth(1).is_disabled(),
                    f"{where}: the stepper offers only the callable amounts",
                    seen,
                )
                resource = {
                    "ko": {"solari": "솔라리", "spice": "스파이스"},
                    "en": {"solari": "Solari", "spice": "spice"},
                }[language][row["currency"]]
                calls = page.locator("#scouts-panel .scouts-calls")
                check.ok(
                    calls.count() == 1
                    and "2" in calls.inner_text()
                    and resource in calls.inner_text()
                    and calls.locator(
                        f'.scouts-currency[data-resource="{row["currency"]}"]'
                    ).count()
                    == 1,
                    f"{where}: the Scouts panel lists the call in the auction's"
                    f" currency ({resource})",
                    calls.all_inner_texts(),
                )
                if not mentat:
                    rule = page.locator(
                        '#scouts-panel [data-item="critical_moment_mid"]'
                    )
                    rule_words = {
                        "ko": "이미 나온 액수는 부를 수 없다",
                        "en": "already called cannot be called again",
                    }[language]
                    check.ok(
                        rule_words in rule.inner_text(),
                        f"{where}: the auction's line states the rule",
                        rule.inner_text(),
                    )
                page.locator("#actions").screenshot(
                    path=str(SHOTS / f"auction_{language}_{row['id']}_called.png")
                )
        check.ok(not recorder.js_errors, "no JavaScript errors", recorder.js_errors)
        context.close()
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
