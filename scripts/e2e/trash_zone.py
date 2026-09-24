"""E2E for ITEM 8c: a trash row names the zone when a same-named copy sits
in another one of the seat's own piles (2026-09-25).

The Feyd track trash (leader_abilities.py, Personal Training's paid/optional
trash), the Desert Tactics trash (board_effects.py) and the Combat reward
trash (combat.py) all offer the seat's own hand, then discard pile, then
in-play cards as trash candidates (`(*owner.hand, *owner.discard_pile,
*owner.in_play)`, all three call sites). Two candidates of the same card
(a starter Dagger's two copies, a leader's own reserve card, ...) used to
render as identical rows -- "카드 {trash} (...) — 단검" twice -- with nothing
saying which pile a row means, even though trashing the hand copy costs
that card's play this round while a discard-pile or in-play copy does not.

`appendActionItems` (render.js) now finds, within one decision's own action
list, every group of rows that share an action_id and a card (same baseId)
but sit in different piles of the *viewing seat's own view* (`ownCardZone`);
each such row gets a suffix naming its pile through the TERMS glossary
word -- {hand}, {discard_pile}, or the new {in_play} ([Main p. 20]) --
appended by `zoneSuffixNode`/`actionItem`. Rows whose only same-named
sibling shares their own pile are untouched (interchangeable copies), and
`describeAction` itself (shared with the turn log, panels.js turnLine) is
never touched, so the log keeps reading the plain card name.

Reaching a real trash decision with a same-named duplicate split across two
piles needs a real game: a raw-HTTP walk (no browser, see
find_zone_dup_seed.py in git history of this file / the session scratchpad)
replaying "confirm every hold at once; otherwise take the seat's own first
legal action" against seed 0 with the Leader draft off (so seat 0 keeps
its server-assigned Leader) landed seat 0 on a `trash_leader_card` decision
(Feyd Rautha Harkonnen's Personal Training track) at its 106th decision,
offering a "Prepare the Way" reserve card from hand and its other copy from
in play. The same policy is replayed live against the browser below rather
than hard-coded to a step count, so a content or engine change that only
shifts *when* the decision appears still gets caught by this script; if the
decision moves out of the step budget entirely, re-running that raw-HTTP
search (see this file's git history) finds a new seed.
"""

from __future__ import annotations

import re
import shutil
import time
from typing import Any

from common import SERVER_LOG_COPY, Check, chrome, open_context, server, set_rule_options
from lang import switch as switch_language
from open_mode import settled

check = Check()

# Found by the raw-HTTP walk described above: base ruleset (open_mode's
# unchecked expansion boxes), Leader draft off (so this seed's server-
# assigned Leader for seat 0 -- Feyd Rautha Harkonnen -- is deterministic).
SEED = 0
STEP_CAP = 200

# Every Hangul run, for the English-side check (mirrors turn_end.py / lang.py).
HANGUL = re.compile("[가-힣]")

# docs/rules/glossary-ko.md: hand 핸드, discard pile 버림 더미, In Play 플레이
# 영역 (all `[Main p. 20]`) -- the expected suffix wording, reconstructed
# independently of both clients (like combat_result.py) rather than read off
# either one's TERMS table, so this test does not depend on code this change
# adds (the old client has no `in_play` term at all).
ZONE_LABELS = {
    "hand": {"ko": "핸드", "en": "hand"},
    "discard_pile": {"ko": "버림 더미", "en": "discard pile"},
    "in_play": {"ko": "플레이 영역", "en": "in play"},
}

# Mirrors core.js's baseId(): strip a starter card's or a shared pile's
# per-instance suffix down to its catalog key.
STARTER_ID = re.compile(r"^player:\d+:starter:(.+):\d+$")
SHARED_ID = re.compile(r"^(?:imperium|reserve|intrigue|tleilaxu|skill):(.+):\d+$")
CONTRACT_ID = re.compile(r"^contract:(.+)$")


def base_id(card_id: str) -> str:
    for pattern in (STARTER_ID, SHARED_ID, CONTRACT_ID):
        match = pattern.match(card_id)
        if match:
            return match.group(1)
    return card_id


def zone_of(card_id: str, view: dict, seat: int) -> str | None:
    """The viewing seat's own pile holding a card instance: its hand in the
    private block, its discard pile and in-play list in its public player
    block (mirrors render.js's ownCardZone -- but reimplemented from
    `state.view` here, not by calling that new function, so this detection
    step also works against the old client)."""

    if card_id in view["private"]["hand"]:
        return "hand"
    own = view["players"][seat]
    if card_id in own["discard_pile"]:
        return "discard_pile"
    if card_id in own["in_play"]:
        return "in_play"
    return None


def find_zone_duplicate(page) -> list[dict[str, Any]] | None:
    """Within the *current* decision's action list, the first group of rows
    sharing an action_id and a card (same base_id) but sitting in different
    piles of the viewing seat -- the same grouping zoneSuffixes (render.js)
    uses, reimplemented in Python from plain state so it detects the
    decision on both clients; only the rendered *row text* checked below
    depends on the new code."""

    if not page.evaluate("Boolean(state.actions)"):
        return None
    actions = page.evaluate("state.actions.actions")
    view = page.evaluate("state.view")
    seat = page.evaluate("state.viewSeat")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for action in actions:
        card_id = action["arguments"].get("card_id")
        if not isinstance(card_id, str):
            continue
        zone = zone_of(card_id, view, seat)
        if zone is None:
            continue
        key = (action["action_id"], base_id(card_id))
        groups.setdefault(key, []).append({"action": action, "zone": zone, "cardId": card_id})
    for entries in groups.values():
        if len({e["zone"] for e in entries}) >= 2:
            return entries
    return None


def create_game_no_leader_draft(page, base: str, humans: tuple[int, ...], seed: int) -> str:
    """open_mode.create_game's own steps, plus unchecking the Leader-draft
    box (its own checkbox, not one of RULE_OPTIONS -- default checked)."""

    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat in humans else "heuristic",
        )
    set_rule_options(page)
    page.set_checked("#opt-leader-draft", False)
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    return page.evaluate("state.gameId")


def drive_to_zone_duplicate(page, step_cap: int = STEP_CAP) -> list[dict] | None:
    """Confirm every hold at once; otherwise take the seat's own first legal
    action -- the same deterministic policy the raw-HTTP search replayed --
    until a decision offers a same-named card from two of the seat's own
    piles at once, or the step budget runs out."""

    for _ in range(step_cap):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            return None
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
            continue
        if not page.evaluate("Boolean(state.actions && state.actions.actions.length)"):
            time.sleep(0.05)
            continue
        entries = find_zone_duplicate(page)
        if entries:
            return entries
        page.evaluate("applyAction(state.actions.actions[0].index)")
    return None


def row_button(page, index: int):
    return page.locator(f"#actions .action-item[data-index='{index}'] > button:not(.action-info)")


def check_rows(page, what: str, lang: str, entries: list[dict]) -> None:
    print(f"  {what}: {len(entries)} rows share an action and a card across piles")
    check.ok(len(entries) >= 2, f"{what}: at least two rows are offered", entries)

    action_id = entries[0]["action"]["action_id"]
    check.ok(
        all(e["action"]["action_id"] == action_id for e in entries),
        f"{what}: every row shares the one action_id ({action_id})",
        entries,
    )
    zones = {e["zone"] for e in entries}
    check.ok(len(zones) >= 2, f"{what}: the rows sit in different piles", sorted(zones))

    bare_texts = []
    for entry in entries:
        index = entry["action"]["index"]
        zone = entry["zone"]
        button = row_button(page, index)
        check.ok(button.count() == 1, f"{what}: {zone}'s row is on screen", index)
        if button.count() != 1:
            continue
        text = button.inner_text()
        suffix = f" ({ZONE_LABELS[zone][lang]})"
        check.ok(
            text.endswith(suffix),
            f"{what}: {zone}'s row ends with its pile ({suffix!r})",
            text,
        )
        bare_texts.append(text[: -len(suffix)] if text.endswith(suffix) else text)
        entry_name = page.evaluate("(id) => lookup(baseId(id)).name", entry["cardId"])
        check.ok(
            entry_name in text,
            f"{what}: {zone}'s row still names the card ({entry_name})",
            text,
        )

    check.ok(
        len({bt for bt in bare_texts}) == 1,
        f"{what}: without the pile suffix the rows would read identically "
        "(the bug ITEM 8c reports)",
        bare_texts,
    )
    shown_full = [row_button(page, e["action"]["index"]).inner_text() for e in entries]
    check.ok(
        len(set(shown_full)) == len(shown_full),
        f"{what}: the rows differ from each other on screen",
        shown_full,
    )


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            print("[1] a real game reaches a trash decision with a same-named "
                  "card split across two of the seat's own piles")
            context, page, rec = open_context(browser, "trash-zone")
            create_game_no_leader_draft(page, base, (0,), SEED)
            entries = drive_to_zone_duplicate(page)
            if entries is None:
                check.ok(
                    False,
                    f"seed {SEED} (Leader draft off) reached a same-pile "
                    f"trash duplicate within {STEP_CAP} steps (it did when "
                    "this script was written)",
                )
            else:
                check_rows(page, "Korean", "ko", entries)

                print("[2] the same rows in English")
                switch_language(page, "en")
                entries_en = find_zone_duplicate(page)
                same_indices = entries_en is not None and {
                    e["action"]["index"] for e in entries_en
                } == {e["action"]["index"] for e in entries}
                check.ok(
                    same_indices,
                    "the same decision (same action indices) is still on "
                    "screen after switching language",
                    entries_en,
                )
                if entries_en:
                    check_rows(page, "English", "en", entries_en)
                    texts_en = [
                        row_button(page, e["action"]["index"]).inner_text()
                        for e in entries_en
                    ]
                    check.ok(
                        not any(HANGUL.search(t) for t in texts_en),
                        "English: no Hangul in the rows",
                        texts_en,
                    )

            failed = [r for r in rec.requests if r[3] >= 400]
            check.ok(not failed, "no failed requests", failed[:5])
            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    check.finish()


if __name__ == "__main__":
    main()
