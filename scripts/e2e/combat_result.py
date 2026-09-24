"""E2E of the Combat result line (UI ITEM 5, 2026-09-24).

Before this, nothing on screen said who won a Conflict or what the viewing
seat got: the last Combat Intrigue pass jumped straight to the next
decision (the next round's turn choice, or -- for the winner -- a reward
choice whose prompt never says it is a reward). The reward is a public log
event (combat_reward_gained, conflict_won); render.js's combatResultLine
now reads it and shows one muted line above the banner's prompt from the
moment a Conflict resolves until the viewing seat's own next turn-taking
step (`agent_turn` / `reveal_turn` / `play_turn_start_card`).

This drives a human seat 0 (three heuristic seats) to the first Combat
resolution in a base game and in an all-expansion game, and checks the
line against an INDEPENDENT reading of the raw log (not against the
client function under test) so a bug in that function's own bookkeeping
would still be caught: the Conflict's name, every rank's seats and, for
the viewing seat's own reward, its term icons (including Victory Points --
the field Step A of this change added to the event payload). It then
checks the line survives everything between the resolution and the
viewing seat's own next turn (including a reward choice of its own, when
the seed hands it one) and disappears the moment that next turn starts.
Finally it checks the line carries no Hangul in English and no stray
Latin in Korean.
"""

from __future__ import annotations

import json
import re
import time

from common import (
    RULE_OPTIONS,
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from lang import switch as switch_language
from open_mode import settled
from turn_controls import COMBAT

check = Check()
VIEWPORT = {"width": 1440, "height": 900}
SEAT = 0

# Found by trial (this script's own driving policy against seed 1..25):
# round 1 always draws the game's one Tier ONE Conflict [Main p. 7], so
# these are seeds where it is Skirmish (Crysknife) AND the viewing seat
# places first -- the only Tier ONE reward row with a decision frame of
# its own (choose an Influence), which is what actually exercises "still
# shown while the seat chooses a reward" below. Every Tier ONE Conflict
# grants no Victory Points by design, so the first resolution's
# victory_points is always 0 here; Step A's nonzero and sandworm-doubled
# cases are covered at the rules level (tests/unit/rules/test_combat.py).
BASE_SEED = 5
EXPANSION_SEED = 2

# Mirrors render.js's OWN_TURN_ACTION_IDS: the action ids that start the
# viewing seat's own next turn, at which point the line must be gone.
OWN_TURN_ACTION_IDS = {"agent_turn", "reveal_turn", "play_turn_start_card"}

HANGUL = re.compile("[가-힣]")
# "AI" is the heuristic seat kind's Korean label suffix (SEAT_KINDS,
# core.js) -- the same exception lang.py's KOREAN_CHROME_ENGLISH keeps.
KOREAN_KEEPS_ENGLISH = ("AI",)

REWARD_FIELDS = [
    ("victory_points", "victory_point"),
    ("solari", "solari"),
    ("spice", "spice"),
    ("water", "water"),
    ("troops", "troop"),
    ("intrigue", "intrigue"),
    ("contracts", "contract"),
]


def create_game(page, base: str, seed: int, expansions: bool) -> str:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == SEAT else "heuristic",
        )
    if expansions:
        set_rule_options(page, *RULE_OPTIONS)
    else:
        set_rule_options(page)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    return page.evaluate("state.gameId")


def find_resolution(entries: list[dict], seat: int) -> dict | None:
    """Independent re-derivation of render.js's latestCombatResolution,
    read straight off the raw log entries -- this checks the engine's
    public events, not the client function it is meant to cross-check."""
    conflict_id = None
    bundle: dict | None = None
    saw_rewards = False
    for entry in entries:
        if entry.get("undone"):
            continue
        for event in entry.get("events") or []:
            kind = event["kind"]
            payload = event.get("payload") or {}
            if kind == "conflict_revealed":
                conflict_id = payload["conflict_id"]
                saw_rewards = False
            elif kind == "combat_reward_gained":
                if not saw_rewards:
                    bundle = {"conflict_id": conflict_id, "rewards": []}
                    saw_rewards = True
                bundle["rewards"].append(payload)
            elif kind == "combat_cleaned_up" and not saw_rewards:
                bundle = None
        if (
            bundle is not None
            and entry.get("type") == "action"
            and entry.get("actor") == seat
            and entry.get("action_id") in OWN_TURN_ACTION_IDS
        ):
            bundle = None
    return bundle


def _choose_action_js() -> str:
    combat = json.dumps(COMBAT)
    return f"""(() => {{
      if (!state.actions || !state.actions.actions.length) return null;
      const A = state.actions.actions;
      const deploy = A.filter((a) => a.action_id === 'deploy_troops');
      if (deploy.length) return deploy[0].index;
      const combat = {combat};
      const toCombat = A.find((a) => a.action_id === 'agent_turn'
        && combat.includes(a.arguments.space_id));
      if (toCombat) return toCombat.index;
      return A[0].index;
    }})()"""


CHOOSE_ACTION_JS = _choose_action_js()


def step_toward_combat(page) -> None:
    """One step of a blind driving policy for seat 0 (open_mode.py's own
    pattern), biased to actually deploy troops into a Combat space -- it
    is not enough to just reach a resolution, the viewing seat needs a
    chance to be ranked in it for the reward half of the check to mean
    anything."""
    if page.evaluate("state.summary.confirmation === state.viewSeat"):
        page.evaluate("confirmTurn()")
    else:
        index = page.evaluate(CHOOSE_ACTION_JS)
        if index is None:
            time.sleep(0.05)
            return
        page.evaluate(f"applyAction({index})")
    assert settled(page, 20)


def drive_to_resolution(page, limit: int = 500) -> bool:
    for _ in range(limit):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            return False
        entries = page.evaluate("state.log.entries")
        if find_resolution(entries, SEAT) is not None:
            return True
        step_toward_combat(page)
    return False


def combat_result_dom(page) -> dict | None:
    return page.evaluate(
        """() => {
            const line = document.querySelector('#decision-info .combat-result');
            if (!line) return null;
            return {
                text: line.textContent,
                amountTitles: [...line.querySelectorAll('.amount')].map((el) => el.title),
                iconLabels: [...line.querySelectorAll('.icon, .icon-text')].map(
                    (el) => el.title || el.getAttribute('alt') || el.textContent
                ),
            };
        }"""
    )


def expected_reward_terms(reward: dict) -> list[tuple[str, int | None]]:
    terms = [(term, reward[key]) for key, term in REWARD_FIELDS if reward.get(key)]
    if reward.get("faction_influence") and reward.get("faction"):
        terms.append((f"influence_{reward['faction']}", reward["faction_influence"]))
    if reward.get("choose_influence"):
        terms.append(("influence_any", reward["choose_influence"]))
    if reward.get("control_space_id"):
        terms.append(("control", None))
    return terms


def check_resolution_content(page, label: str) -> dict:
    """The line's content against an independent read of the raw log."""
    entries = page.evaluate("state.log.entries")
    bundle = find_resolution(entries, SEAT)
    if not check.ok(bundle is not None, f"{label}: a Conflict has resolved"):
        return {}
    dom = combat_result_dom(page)
    if not check.ok(dom is not None, f"{label}: the combat result line is on screen"):
        return bundle
    conflict_name = page.evaluate(
        f"state.catalog.conflicts[{json.dumps(bundle['conflict_id'])}].name"
    )
    check.ok(
        conflict_name in dom["text"],
        f"{label}: the line names the resolved Conflict",
        (conflict_name, dom["text"]),
    )
    by_rank: dict[int, list[int]] = {}
    for reward in bundle["rewards"]:
        by_rank.setdefault(reward["rank"], []).append(reward["player"])
    for rank, players in by_rank.items():
        rank_label = page.evaluate(f"t('render.combat_result_rank_{rank}')")
        names = [page.evaluate(f"playerLabel({p})") for p in players]
        segment = f"{rank_label}: " + ", ".join(names)
        check.ok(
            segment in dom["text"],
            f"{label}: rank {rank} lists {names} exactly as the reward events say",
            (segment, dom["text"]),
        )
    own = next((r for r in bundle["rewards"] if r["player"] == SEAT), None)
    if own is None:
        unranked = page.evaluate("t('render.combat_result_unranked')")
        check.ok(
            unranked in dom["text"] and not dom["amountTitles"],
            f"{label}: the viewing seat placed nowhere and the line says so",
            dom,
        )
    else:
        expected_amounts = []
        expected_icons = []
        for term, count in expected_reward_terms(own):
            term_label = page.evaluate(f"termLabel('{term}')")
            if count is None:
                expected_icons.append(term_label)
            else:
                expected_amounts.append(f"{count} {term_label}")
        check.ok(
            sorted(dom["amountTitles"]) == sorted(expected_amounts),
            f"{label}: the viewing seat's own reward matches its event payload "
            "(including Victory Points)",
            {"shown": dom["amountTitles"], "expected": expected_amounts, "payload": own},
        )
        for term_label in expected_icons:
            check.ok(
                term_label in dom["iconLabels"],
                f"{label}: the viewing seat's Control reward is shown",
                dom["iconLabels"],
            )
    return bundle


def check_language(page, conflict_name: str, label: str) -> None:
    dom = combat_result_dom(page)
    if not check.ok(dom is not None, f"{label}: the line is on screen to check language"):
        return
    text = dom["text"]
    if page.evaluate("TERM_LANGUAGE") == "en":
        check.ok(not HANGUL.search(text), f"{label}: English has no Hangul in the line", text)
        return
    bare = text.replace(conflict_name, " ")
    for word in KOREAN_KEEPS_ENGLISH:
        bare = bare.replace(word, " ")
    latin = re.findall(r"[A-Za-z]{2,}", bare)
    check.ok(not latin, f"{label}: Korean has no stray Latin in the line", (latin, text))


def check_persistence(page, label: str) -> None:
    """The line survives everything between the resolution and the seat's
    own next turn-taking step (including its own reward choices, when the
    seed hands it any), and is gone right after that step."""
    for _ in range(400):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            check.ok(
                True,
                f"{label}: the game ended at the resolution (no next turn to check)",
            )
            return
        dom = combat_result_dom(page)
        if not check.ok(dom is not None, f"{label}: the line is still shown", dom):
            return
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            assert settled(page, 20)
            continue
        actions = page.evaluate("state.actions ? state.actions.actions : []")
        if not actions:
            time.sleep(0.05)
            continue
        ids = {action["action_id"] for action in actions}
        starting = ids & OWN_TURN_ACTION_IDS
        if starting:
            action_id = next(iter(starting))
            index = next(a["index"] for a in actions if a["action_id"] == action_id)
            check.ok(
                True, f"{label}: still shown right up to the seat's own next {action_id}"
            )
            page.evaluate(f"applyAction({index})")
            assert settled(page, 20)
            after = combat_result_dom(page)
            check.ok(after is None, f"{label}: gone after the seat's own {action_id}", after)
            return
        # A decision that is not the seat's own next turn -- most often one
        # of its own reward choices (an Influence pick, an optional cost, a
        # trash, a Spy) -- exercises "still shown while choosing a reward".
        page.evaluate(f"applyAction({actions[0]['index']})")
        assert settled(page, 20)
    check.ok(False, f"{label}: reached the seat's own next turn within the step budget")


def scenario(base, browser, *, seed: int, expansions: bool, label: str) -> None:
    kind = "all expansions" if expansions else "base game"
    print(f"[{label}] {kind}, seed {seed}")
    context, page, rec = open_context(browser, label, VIEWPORT)
    create_game(page, base, seed, expansions)
    reached = drive_to_resolution(page)
    if not check.ok(reached, f"{label}: reached the first Combat resolution"):
        context.close()
        return
    bundle = check_resolution_content(page, f"{label}/ko")
    conflict_name = (
        page.evaluate(f"state.catalog.conflicts[{json.dumps(bundle['conflict_id'])}].name")
        if bundle
        else None
    )
    if conflict_name:
        check_language(page, conflict_name, f"{label}/ko")
    switch_language(page, "en")
    check_resolution_content(page, f"{label}/en")
    if conflict_name:
        check_language(page, conflict_name, f"{label}/en")
    check_persistence(page, label)
    failed = [r for r in rec.requests if r[3] is not None and r[3] >= 400]
    check.ok(not failed, f"{label}: no failed requests", failed[:5])
    check.ok(not rec.js_errors, f"{label}: no JS exceptions", rec.js_errors[:5])
    context.close()


def main() -> None:
    with server() as (base, log_path):
        with chrome() as browser:
            scenario(base, browser, seed=BASE_SEED, expansions=False, label="base")
            scenario(base, browser, seed=EXPANSION_SEED, expansions=True, label="expansions")
        errors = [
            line
            for line in log_path.read_text().splitlines()
            if "ERROR" in line or "Traceback" in line
        ]
        check.ok(not errors, f"no server errors (see {SERVER_LOG_COPY})", errors[:3])
        SERVER_LOG_COPY.write_text(log_path.read_text())
    check.finish()


if __name__ == "__main__":
    main()
