"""Influence cost/reward icons and an empty Gather Intelligence explanation.

The checkout's engine plays Tenuous Bond and places an Agent watched by a
Spy. Its real server payloads are rendered in both languages. Render-only
probes cannot change the user's live game or disclose a drawn card.
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
    os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-choices-")
)

FIXTURES = """
import json
from dataclasses import replace
from dune_imperium import RulesetConfig
from dune_imperium.core import (
    DecisionFrame, DomainAction, GamePhase, GameState, Influence,
    PlayerDecision, PlayerState,
)
from dune_imperium.server.sessions import GameSessionManager

manager = GameSessionManager()
game = manager.create_game(("human",) * 4, game_seed=21, bloodlines=True)
game_id = str(game["game_id"])
session = manager._get(game_id)
engine = session.engine

def state_for(owner):
    return GameState(
        config=RulesetConfig(bloodlines=True), seed=21, round_number=1,
        phase=GamePhase.PLAYER_TURNS,
        players=(owner, *(PlayerState(player_id=i) for i in range(1, 4))),
        decision_stack=(DecisionFrame(
            kind="turn", frame_id="round:1:turn:0",
            decision=PlayerDecision(owner=0, prompt="Choose a turn"),
        ),),
    )

def snapshot(state):
    session.state = state
    return {
        "summary": manager.summary(game_id),
        "view": manager.view(game_id, 0),
        "actions": manager.legal_actions(game_id, 0),
    }

card = "intrigue:tenuous_bond:0"
state = state_for(PlayerState(
    player_id=0, intrigue_cards=(card,), influence=Influence(fremen=2),
))
cost = engine.apply(state, DomainAction(
    "play_intrigue", 0, (("card_id", card), ("option", 0)),
)).state
loss_action = engine.legal_actions(cost, 0)[0]
loss = engine.apply(cost, loss_action)
gain = engine.apply(loss.state, engine.legal_actions(loss.state, 0)[0])

def log(action, transition):
    return {
        "index": 1, "actor": action.actor, "action_id": action.action_id,
        "arguments": dict(action.arguments),
        "events": [{"kind": event.kind, "payload": dict(event.payload)}
                   for event in transition.events],
    }

fixtures = {"cost": snapshot(cost), "reward": snapshot(loss.state)}
fixtures["logs"] = [
    log(loss_action, loss), log(engine.legal_actions(loss.state, 0)[0], gain),
]
post = "landsraad-assembly-hall-gather-support"
dagger = "player:0:starter:dagger:0"
for pile in ("empty", "deck", "discard_pile"):
    owner = PlayerState(
        player_id=0, hand=(dagger,), spies_supply=1,
        spy_post_ids=(post, "arrakis-hagga-basin"),
    )
    if pile != "empty":
        owner = replace(owner, **{pile: ("player:0:starter:diplomacy:0",)})
    placed = engine.apply(state_for(owner), DomainAction(
        "agent_turn", 0, (("card_id", dagger), ("space_id", "assembly_hall")),
    )).state
    fixtures[pile] = snapshot(placed)
print(json.dumps(fixtures))
"""

RENDER = """({fixture, language, logs}) => {
    setLanguage(language, false);
    Object.assign(state, {summary: fixture.summary, view: fixture.view,
        actions: fixture.actions, viewSeat: 0, playSeat: 0, review: null,
        busy: false, pick: null});
    document.getElementById('choice-probe')?.remove();
    const host = document.createElement('section');
    host.id = 'choice-probe';
    Object.assign(host.style, {position: 'fixed', left: '12px', top: '12px',
        width: '340px', padding: '12px', background: 'var(--panel)',
        zIndex: '9999'});
    renderActionPanel(host, null);
    if (logs) {
        const log = document.createElement('div');
        log.id = 'choice-log';
        for (const entry of logs) log.appendChild(turnLine(entry));
        host.appendChild(log);
    }
    document.body.appendChild(host);
}"""


def main() -> None:
    result = subprocess.run(
        [str(REPO / ".venv/bin/python"), "-c", FIXTURES],
        cwd=REPO, text=True, capture_output=True, check=True,
    )
    fixtures = json.loads(result.stdout)
    SHOTS.mkdir(parents=True, exist_ok=True)
    with server() as (base, _), chrome() as browser:
        context, page, recorder = open_context(browser, "influence-spies")
        page.goto(base)
        page.wait_for_function("state.catalog !== null")
        for language in ("ko", "en"):
            for name, icon, word in (
                ("cost", "influence_lose", "하락" if language == "ko" else "Lose"),
                (
                    "reward", "influence_any",
                    "상승" if language == "ko" else "Influence",
                ),
            ):
                page.evaluate(RENDER, {
                    "fixture": fixtures[name], "language": language,
                    "logs": fixtures["logs"],
                })
                buttons = page.locator("#choice-probe > .action-item")
                check.ok(buttons.count() > 0, f"{language} {name}: choices render")
                icon_url = page.evaluate("key => state.catalog.icons[key]", icon)
                wrong_url = page.evaluate(
                    "key => state.catalog.icons[key]",
                    "influence_any" if name == "cost" else "influence_lose",
                )
                for index in range(buttons.count()):
                    button = buttons.nth(index)
                    accessible = button.inner_text() + " " + " ".join(
                        button.locator("img").evaluate_all(
                            "nodes => nodes.map(node => node.alt)"
                        )
                    )
                    check.ok(
                        button.locator(f'img.icon[src="{icon_url}"]').count() == 1
                        and button.locator(f'img.icon[src="{wrong_url}"]').count() == 0
                        and word in accessible,
                        f"{language} {name}: icon and accessible text match",
                    )
                check.ok(
                    ("프레멘" if language == "ko" else "Fremen")
                    in buttons.first.inner_text() if name == "cost"
                    else ("황제" if language == "ko" else "Emperor")
                    in buttons.first.inner_text(),
                    f"{language} {name}: the Faction remains on the choice",
                )
                loss_url = page.evaluate(
                    "state.catalog.icons.influence_lose"
                )
                gain_url = page.evaluate("state.catalog.icons.influence_any")
                check.ok(
                    page.locator('#choice-log .turn-line-head').nth(0).locator(
                        f'img.icon[src="{loss_url}"]'
                    ).count() == 1
                    and page.locator('#choice-log .logevent').nth(0).locator(
                        f'img.icon[src="{loss_url}"]'
                    ).count() == 1
                    and page.locator('#choice-log .turn-line-head').nth(1).locator(
                        f'img.icon[src="{gain_url}"]'
                    ).count() == 1,
                    f"{language}: log directions do not depend on the live slot",
                )
                page.locator("#choice-probe").screenshot(
                    path=str(SHOTS / f"influence_{language}_{name}.png")
                )

            for pile in ("empty", "deck", "discard_pile"):
                page.evaluate(RENDER, {
                    "fixture": fixtures[pile], "language": language, "logs": None,
                })
                grey = page.locator("#choice-probe .unavailable-item")
                if pile == "empty":
                    reason = ("덱과 버린 카드 더미가 모두 비었음" if language == "ko"
                              else "your deck and discard pile are both empty")
                    check.ok(
                        grey.count() == 1
                        and grey.get_attribute("aria-disabled") == "true"
                        and reason in grey.inner_text(),
                        f"{language}: the Spy's draw explains both empty piles",
                    )
                    check.ok(
                        len(fixtures[pile]["actions"]["actions"]) == 1
                        and page.locator(
                            "#choice-probe > .action-item:not(.unavailable-item)"
                        )
                        .count() == 1,
                        f"{language}: only Decline remains selectable",
                    )
                    posts = page.evaluate("""state.actions.unavailable.rows.map(
                        row => row.action.arguments.post_id)""")
                    check.ok(
                        posts == ["landsraad-assembly-hall-gather-support"],
                        f"{language}: the unrelated Spy is not offered",
                    )
                    before = len(recorder.requests)
                    grey.click(force=True)
                    check.ok(
                        len(recorder.requests) == before,
                        f"{language}: the disabled choice sends no request",
                    )
                else:
                    check.ok(
                        grey.count() == 0
                        and page.locator("#choice-probe > .action-item").count() == 2,
                        f"{language} {pile}: Gather returns with a card in either pile",
                    )
                page.locator("#choice-probe").screenshot(
                    path=str(SHOTS / f"gather_{language}_{pile}.png")
                )
        check.ok(not recorder.js_errors, "no JavaScript errors", recorder.js_errors)
        context.close()
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
