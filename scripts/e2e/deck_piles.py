"""E2E of the face-down decks drawn with the Steam app's card backs.

The Conflict deck is built by back, I on II on III, and lies face down
[Main p. 4], so the back of its top card is public: the server's view
names its tier (`conflict_deck_top_tier`, 0 once the deck is empty) and
the board's printed deck slot shows that tier's back with the count, in
the same `.slot-deck` box as before. The Imperium Row and the Tleilaxu Row
start with an Imperium-back pile, and the Intrigue deck line with an
Intrigue-back pile, each with its deck's count; Kota Odax's face-down
Secret Project tile shows the Tech back. The pictures come from the
private assets (`catalog.card_backs`); without them every deck keeps its
earlier drawing, which the script checks by taking the pictures away.

A drafted game shows the whole deck before round 1 (Conflict I on top),
the first round the second tier, and Epic Game Mode Conflict II on top of
the whole deck [Rise of Ix p. 10]; deeper states are made by editing the
view in the page (the view is the render's only input). The live round
is also checked after an undo and in English ("Conflict II"), and a
finished all-AI game under review shows each step's own tier and counts,
not the last step's.
"""

from __future__ import annotations

import json
import shutil

from common import (
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from lang import switch
from turn_controls import play_until

check = Check()
TOLERANCE = 0.06  # percent of the stage

PILES_JS = """() => {
  const stage = document.querySelector('.board-stage').getBoundingClientRect();
  const image = (node) => node ? {
    src: node.getAttribute('src'),
    loaded: node.complete && node.naturalWidth > 0,
  } : null;
  const pile = (node) => node ? {
    back: node.dataset.back,
    first: node === node.parentElement.firstElementChild,
    count: node.querySelector('.deck-pile-count').textContent,
    image: image(node.querySelector('img')),
    vcard: node.classList.contains('vcard'),
    empty: node.classList.contains('empty'),
    hidden: node.getAttribute('aria-hidden'),
    title: node.title,
  } : null;
  const deck = document.querySelector('.board-stage .slot-deck');
  const icon = deck && deck.querySelector('.icon');
  const r = deck && deck.getBoundingClientRect();
  const line = document.querySelector("#market [data-pile='intrigue-deck']");
  return {
    conflict: deck ? {
      tier: deck.dataset.tier ?? null,
      pictured: deck.classList.contains('pictured'),
      image: image(deck.querySelector('img.slot-deck-back')),
      iconShown: Boolean(icon) && getComputedStyle(icon).display !== 'none',
      count: deck.querySelector('.slot-deck-count').textContent,
      title: deck.title,
      box: [
        (r.left - stage.left) / stage.width * 100,
        (r.top - stage.top) / stage.height * 100,
        r.width / stage.width * 100,
        r.height / stage.height * 100,
      ],
    } : null,
    imperium: pile(document.querySelector(
      "#market .strip[data-strip='Imperium Row'] .strip-cards > .deck-pile")),
    tleilaxu: pile(document.querySelector(
      "#market .strip[data-strip='Tleilaxu Row'] .strip-cards > .deck-pile")),
    intrigue: pile(line && line.querySelector(':scope > .deck-pile')),
    intrigueText: line ? line.textContent : null,
    piles: document.querySelectorAll('.deck-pile').length,
  };
}"""

# The view's public deck fields (the server's session JSON).
DECKS_JS = """() => ({
  tier: state.view.conflict_deck_top_tier,
  size: state.view.conflict_deck_size,
  imperium: state.view.imperium_deck_size,
  tleilaxu: state.view.tleilaxu_deck_size,
  intrigue: state.view.intrigue_deck_size,
})"""

# The pictures loaded and the board stage laid out: under load (run_all -j 4)
# the stage could still be 0 px when the slot was measured (NaN box).
LOADED_JS = (
    "[...document.querySelectorAll('.deck-pile img, .slot-deck img, .tile-back img')]"
    ".every((i) => i.complete)"
    " && (() => { const s = document.querySelector('.board-stage');"
    " if (!s) return true; const r = s.getBoundingClientRect();"
    " return r.width > 0 && r.height > 0; })()"
)


def new_game(page, base: str, options: tuple[str, ...], draft: bool) -> None:
    """Seat 0 human, the others heuristic, seed 11, exactly `options` kept."""
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        kind = "human" if seat == 0 else "heuristic"
        page.select_option(f"#seat-selects select[data-seat='{seat}']", kind)
    set_rule_options(page, *options)
    page.set_checked("#opt-leader-draft", draft)
    page.fill("#opt-seed", "11")
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")


def piles(page) -> dict:
    page.wait_for_function(LOADED_JS)
    return page.evaluate(PILES_JS)


def edit_view(page, fields: dict) -> dict:
    page.evaluate(
        "(fields) => { Object.assign(state.view, fields); render(); }", fields
    )
    return piles(page)


def tier_text(page, tier: int) -> str:
    return page.evaluate(
        "(tier) => t('core.conflict_tier', {tier: ['I', 'II', 'III'][tier - 1]})", tier
    )


def check_conflict(page, label: str, backs: dict, tier: int, size: int) -> None:
    """The Conflict deck slot for a deck of `size` with `tier` on top."""
    shown = piles(page)["conflict"]
    if size == 0:
        check.ok(shown is None, f"{label}: an empty deck leaves the slot empty", shown)
        return
    if not check.ok(shown is not None, f"{label}: the deck in its slot"):
        return
    slot = page.evaluate("state.catalog.tracks.conflict_deck_slot")
    check.ok(
        all(abs(a - b) <= TOLERANCE for a, b in zip(shown["box"], slot, strict=True)),
        f"{label}: the deck fills its printed slot",
        (shown["box"], slot),
    )
    check.ok(
        shown["count"] == str(size) and shown["tier"] == str(tier),
        f"{label}: the count {size} and tier {tier}",
        shown,
    )
    check.ok(
        tier_text(page, tier) in shown["title"] and str(size) in shown["title"],
        f"{label}: the title names the tier and the count",
        shown["title"],
    )
    url = backs.get(f"conflict_{tier}")
    if url:
        check.ok(
            shown["pictured"]
            and shown["image"] == {"src": url, "loaded": True}
            and not shown["iconShown"],
            f"{label}: the Conflict {tier} back",
            shown,
        )
    else:
        check.ok(
            not shown["pictured"] and shown["image"] is None and shown["iconShown"],
            f"{label}: the drawn box without the picture",
            shown,
        )


def check_view_piles(page, label: str, backs: dict) -> dict:
    """Every deck as `state.view` (the live or the reviewed step) counts it."""
    view = page.evaluate(DECKS_JS)
    check_conflict(page, label, backs, view["tier"], view["size"])
    shown = piles(page)
    check_pile(
        f"{label}: Imperium Row",
        shown["imperium"],
        backs.get("imperium"),
        view["imperium"],
    )
    if view["tleilaxu"] is not None:
        check_pile(
            f"{label}: Tleilaxu Row",
            shown["tleilaxu"],
            backs.get("imperium"),
            view["tleilaxu"],
        )
    check_pile(
        f"{label}: Intrigue deck",
        shown["intrigue"],
        backs.get("intrigue"),
        view["intrigue"],
    )
    return view


def check_pile(label: str, pile: dict | None, url: str | None, count: int) -> None:
    if url is None:
        check.ok(pile is None, f"{label}: no pile without the picture", pile)
        return
    check.ok(
        pile is not None
        and pile["first"]
        and pile["image"] == {"src": url, "loaded": True}
        and pile["count"] == str(count)
        and pile["empty"] == (count == 0)
        and not pile["vcard"]
        and pile["hidden"] == "true"
        and str(count) in pile["title"],
        f"{label}: the pile first, its back and the count {count}",
        pile,
    )


def standard_game(base: str, browser) -> None:
    print("[1] a drafted game: Conflict I on the whole deck, then II")
    context, page, rec = open_context(browser, "deck-piles")
    new_game(page, base, ("immortality",), draft=True)
    backs = page.evaluate("state.catalog.card_backs || {}")
    view = page.evaluate(DECKS_JS)
    check.ok(
        view["size"] == 10 and view["tier"] == 1,
        "the draft shows the whole deck, Conflict I on top [Main p. 4]",
        view,
    )
    check_conflict(page, "draft", backs, 1, 10)
    shown = piles(page)
    check_pile(
        "Imperium Row", shown["imperium"], backs.get("imperium"), view["imperium"]
    )
    check_pile(
        "Tleilaxu Row (Imperium back)",
        shown["tleilaxu"],
        backs.get("imperium"),
        view["tleilaxu"],
    )
    check_pile(
        "Intrigue deck", shown["intrigue"], backs.get("intrigue"), view["intrigue"]
    )
    count_text = page.evaluate(
        "(n) => { const line = document.createElement('div');"
        " line.appendChild(tNode('board.intrigue_deck_count', {count: n}));"
        " return line.textContent; }",
        view["intrigue"],
    )
    check.ok(
        shown["intrigueText"].endswith(count_text),
        "the Intrigue deck line keeps its count text",
        (shown["intrigueText"], count_text),
    )

    for tier, size in ((2, 9), (2, 5), (3, 4), (3, 1), (0, 0)):
        edit_view(page, {"conflict_deck_top_tier": tier, "conflict_deck_size": size})
        check_conflict(page, f"edited deck of {size}", backs, tier, size)
    shown = edit_view(page, {"imperium_deck_size": 0, "intrigue_deck_size": 0})
    check_pile("an empty Imperium deck", shown["imperium"], backs.get("imperium"), 0)
    check_pile("an empty Intrigue deck", shown["intrigue"], backs.get("intrigue"), 0)

    print("[2] the Intrigue discard stays a line beside the deck")
    ids = page.evaluate(
        "Object.keys(state.catalog.intrigue || {}).slice(0, 2).map((id) => `${id}:1`)"
    )
    edit_view(page, {"intrigue_discard": ids})
    check.ok(
        page.locator(".pile-button[data-pile='intrigue']").count() == 1,
        "the discard button is still there",
    )
    check.ok(
        page.locator("#market .vcard.intrigue").count() == 0,
        "no Intrigue card faces in the column",
    )

    print("[3] round 1 reveals Conflict I: the live deck shows Conflict II")
    # The first step taken brings the server's view back over the edits.
    reached = play_until(page, "state.view.conflict_deck_size === 9", "0", limit=60)
    if check.ok(reached, "the draft ends and round 1 reveals its Conflict"):
        live = page.evaluate("state.view.conflict_deck_top_tier")
        check.ok(live == 2, "the server names tier II for the deck of 9", live)
        check_conflict(page, "round 1", backs, 2, 9)

    print("[3b] an undo keeps the deck the server names")
    if reached:
        before = page.evaluate(DECKS_JS)
        page.evaluate("applyAction(0)")
        page.wait_for_function("!state.busy && refreshFlight === null")
        undo = page.locator(".undo-row button").first
        if check.ok(undo.count() == 1, "seat 0's first step can be taken back"):
            count = page.evaluate("state.summary.undo_count")
            undo.click()
            page.wait_for_function(
                f"state.summary.undo_count === {count + 1}"
                " && !state.busy && refreshFlight === null"
            )
            after = check_view_piles(page, "after the undo", backs)
            check.ok(
                after == before,
                "the undo is back at the same decks (an undo never crosses a reveal)",
                (before, after),
            )

    print("[3c] in English the title names Conflict II")
    switch(page, "en")
    check_conflict(page, "English", backs, 2, 9)
    title = piles(page)["conflict"]["title"]
    check.ok("Conflict II" in title, "the English title says 'Conflict II'", title)
    switch(page, "ko")

    print("[4] the same table without the pictures: the earlier drawing")
    page.evaluate("state.catalog.card_backs = {}; render();")
    check_conflict(page, "no pictures", {}, 2, 9)
    shown = piles(page)
    check.ok(shown["piles"] == 0, "no pile anywhere", shown["piles"])
    imperium_heading = page.evaluate(
        "document.querySelector(\"#market .strip[data-strip='Imperium Row'] h3\")"
        ".textContent"
    )
    check.ok(
        str(page.evaluate("state.view.imperium_deck_size")) in imperium_heading,
        "the Imperium Row heading still counts the deck",
        imperium_heading,
    )
    check.ok(
        page.locator("#market [data-pile='intrigue-deck'] .deck-pile-label").count()
        == 0,
        "the Intrigue deck line is plain text again",
    )
    check.ok(not rec.js_errors, "no JS errors (standard)", rec.js_errors[:3])
    context.close()


def seek(page, step: int) -> None:
    page.evaluate(f"stopPlayback(); reviewSeek({step})")
    page.wait_for_function(f"state.review.cursor === {step} && refreshFlight === null")


def review_game(base: str, browser) -> None:
    print("[7] a finished all-AI game under review: each step's own decks")
    context, page, rec = open_context(browser, "deck-piles-review")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    set_rule_options(page, "immortality")
    page.set_checked("#opt-leader-draft", False)
    page.fill("#opt-seed", "11")
    page.click("#create-game")
    page.wait_for_function("state.review !== null && state.view !== null")
    backs = page.evaluate("state.catalog.card_backs || {}")
    steps = page.evaluate("state.review.meta.step_count")
    seek(page, steps)
    last = check_view_piles(page, "the last step", backs)
    tiers = set()
    differs = 0
    for fraction in (0.0, 0.15, 0.4, 0.7):
        step = int(steps * fraction)
        seek(page, step)
        shown = check_view_piles(page, f"step {step} of {steps}", backs)
        tiers.add(shown["tier"])
        differs += shown != last
    check.ok(
        differs == 4 and len(tiers) >= 2,
        "the reviewed steps show their own decks, more than one tier",
        (sorted(tiers), differs, last),
    )
    check.ok(not rec.js_errors, "no JS errors (review)", rec.js_errors[:3])
    context.close()


def epic_game(base: str, browser) -> None:
    print("[5] Epic Game Mode: Conflict II on top of the whole deck")
    context, page, rec = open_context(browser, "deck-piles-epic")
    new_game(page, base, ("epic-game",), draft=True)
    backs = page.evaluate("state.catalog.card_backs || {}")
    view = page.evaluate(DECKS_JS)
    check.ok(
        (view["tier"], view["size"]) == (2, 10),
        "no Conflict I: II on top of a deck of ten [Rise of Ix p. 10]",
        view,
    )
    check_conflict(page, "epic draft", backs, 2, 10)
    check.ok(not rec.js_errors, "no JS errors (epic)", rec.js_errors[:3])
    context.close()


KOTA_JS = """() => {
  const tile = document.querySelector('#card-popover .popover-secret-project-row > *');
  const img = tile && tile.querySelector('img');
  return tile ? {
    back: tile.classList.contains('tile-back'),
    pictured: tile.classList.contains('pictured'),
    src: img ? img.getAttribute('src') : null,
    loaded: img ? img.complete && img.naturalWidth > 0 : null,
  } : null;
}"""


def open_kota(page) -> dict | None:
    page.evaluate(
        """() => {
          const player = state.view.players[1];
          player.leader_id = 'kota_odax_of_ix';
          player.leader_face_id = null;
          player.has_secret_project = true;
          render();
        }"""
    )
    page.click('.seat[data-seat="1"] .leader-name')
    page.wait_for_selector("#card-popover .popover-secret-project-row")
    page.wait_for_function(LOADED_JS)
    return page.evaluate(KOTA_JS)


def kota_tile(base: str, browser) -> None:
    print("[6] another seat's face-down Secret Project tile shows the Tech back")
    context, page, rec = open_context(browser, "deck-piles-kota")
    new_game(page, base, ("bloodlines", "tech"), draft=False)
    url = page.evaluate("(state.catalog.card_backs || {}).tech || null")
    shown = open_kota(page)
    if url:
        check.ok(
            shown == {"back": True, "pictured": True, "src": url, "loaded": True},
            "the Tech back on the face-down tile",
            shown,
        )
    page.keyboard.press("Escape")
    page.evaluate("state.catalog.card_backs = {}; render();")
    shown = open_kota(page)
    check.ok(
        shown == {"back": True, "pictured": False, "src": None, "loaded": None},
        "without the picture, the plain placeholder",
        shown,
    )
    check.ok(not rec.js_errors, "no JS errors (Kota)", rec.js_errors[:3])
    context.close()


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            standard_game(base, browser)
            epic_game(base, browser)
            kota_tile(base, browser)
            review_game(base, browser)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    print(json.dumps({"passed": check.passed, "failed": check.failed}))
    check.finish()


if __name__ == "__main__":
    main()
