"""The setup form's Go to 11 and Epic Game Mode boxes (2026-09-28).

The Immortality rulebook's "Go to 11" variant starts every Score marker at 0
instead of 1 and keeps the Endgame score [Immortality p. 12]. The user chose
to offer it only with Immortality and to check its box by default (the
digital game and tournaments play it that way, OQ-091), while the engine
and the CLI keep it off. So the box must:

- open checked, and follow the Immortality box the way the Tech Module box
  follows Bloodlines: disabled and cleared while its parent is off, enabled
  again (still cleared, like Tech) when the parent comes back;
- reach the server as ``go_to_11`` in the POST /games body, come back in the
  summary, and show a header badge;
- put all four seats' score discs on the Score track's printed 0 at the
  first decision, and on 1 when the box is cleared (the contrast shows the
  geometry check can fail).

Rise of Ix's Epic Game Mode plays to 12 with a Conflict deck of II over III,
Control the Spice, one Intrigue card and five garrison troops each
[Rise of Ix p. 10] (docs/rules/epic-game-mode.md). The user chose to check
its box by default too and to make it depend on nothing (OQ-092), so it
must open checked and enabled whatever the other boxes do, reach the server
as ``epic_game``, show a badge, and start every seat with five troops in
its garrison ring while the Score discs keep their start (0 with Go to 11,
1 without); cleared, the table is the retail setup (three troops, no
Intrigue card). Epic's Intrigue card is drawn once every Leader is known
[Rise of Ix p. 10], so no seat holds one during the Leader draft and each
holds one after the four picks (2026-10-02, codec v128).

Four human seats keep the table at its first decision (the Leader draft,
which the draft box leaves on), before any seat could score; one scenario
then makes the four picks. With
``E2E_SHOTS_DIR`` set, the script also leaves two screenshots there: the
setup form (Korean) and the Epic game's header and board.
"""

from __future__ import annotations

import os
from pathlib import Path

from common import Check, chrome, open_context, server
from lang import switch
from open_mode import settled

check = Check()

SEED = 11
SHOTS = os.environ.get("E2E_SHOTS_DIR")

BOXES_JS = """() => {
  const box = (id) => {
    const input = document.getElementById(id);
    return {checked: input.checked, disabled: input.disabled};
  };
  return {
    bloodlines: box("opt-bloodlines"), tech: box("opt-tech"),
    immortality: box("opt-immortality"), go11: box("opt-go-to-11"),
    epic: box("opt-epic-game"),
  };
}"""

LABEL_JS = """(id) => ({
  shown: document.getElementById(id).parentElement.textContent.trim(),
  want: t({"opt-go-to-11": "html.opt_go_to_11",
           "opt-epic-game": "html.opt_epic_game"}[id]),
})"""

# The boxes in the form's order, to show the Epic box sits between Go to 11
# and Arrakeen Scouts.
ORDER_JS = """() => [...document.querySelectorAll(
  "#setup-form input[type=checkbox]")].map((input) => input.id)"""

# Each seat's score disc as drawn: its centre in percent of the board stage,
# with the Score track's printed levels (catalog.tracks.victory_points); the
# troop pieces in each seat's garrison ring and the Intrigue count on each
# seat card, as drawn; and the numbers behind them.
TABLE_JS = """() => {
  const stage = document.querySelector(".board-stage").getBoundingClientRect();
  const track = state.catalog.tracks.victory_points;
  const discs = [...document.querySelectorAll(".board-stage .vp-token")].map((disc) => {
    const r = disc.getBoundingClientRect();
    return {
      seat: Number(disc.dataset.seat),
      x: ((r.left + r.width / 2 - stage.left) / stage.width) * 100,
      y: ((r.top + r.height / 2 - stage.top) / stage.height) * 100,
    };
  });
  const garrisons = [0, 1, 2, 3].map((seat) => document.querySelectorAll(
    `.board-stage .garrison-units[data-seat="${seat}"]`
    + ` .garrison-unit[data-kind="troop"]`
  ).length);
  const intrigueLabel = phraseText("{intrigue}");
  const intrigue = [0, 1, 2, 3].map((seat) => {
    const card = document.querySelector(`#seats article.seat[data-seat="${seat}"]`);
    const stat = card && [...card.querySelectorAll(".stat")].find(
      (node) => node.title === intrigueLabel);
    return stat ? Number(stat.lastChild.textContent.trim()) : null;
  });
  const badges = document.querySelector("#header-status .status-badges");
  return {
    discs, x: track.x, levels: track.levels, cell: track.cell,
    scores: state.view.players.map((player) => player.victory_points),
    garrisons,
    garrisonData: state.view.players.map((player) => player.troops_garrison),
    intrigue,
    intrigueData: state.view.players.map((player) => player.intrigue_card_count),
    goTo11: state.summary.go_to_11,
    epic: state.summary.epic_game,
    badges: badges ? badges.textContent : "",
    badge: t("render.badge_go_to_11"),
    epicBadge: t("render.badge_epic_game"),
  };
}"""


def shot(page, name: str, selector: str | None = None) -> None:
    if not SHOTS:
        return
    path = Path(SHOTS) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if selector:
        page.locator(selector).screenshot(path=str(path))
    else:
        page.screenshot(path=str(path))
    print(f"  shot {path}")


def open_setup(page, base: str) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "human")
    page.fill("#opt-seed", str(SEED))


def create(page) -> dict:
    """Start the game from the form; return the POST /games body it sent."""
    with page.expect_request(
        lambda r: r.method == "POST" and r.url.endswith("/games")
    ) as sent:
        page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    page.wait_for_function(
        "[...document.querySelectorAll('.board-stage img')].every((i) => i.complete)"
    )
    settled(page)
    return sent.value.post_data_json


def on_level(board: dict, level: int) -> tuple[bool, object]:
    """Whether all four discs cluster on the printed ``level`` of the track."""
    discs = board["discs"]
    levels = board["levels"]
    nearest = [
        min(range(len(levels)), key=lambda i: abs(levels[i] - disc["y"]))
        for disc in discs
    ]
    mean_x = sum(disc["x"] for disc in discs) / max(len(discs), 1)
    mean_y = sum(disc["y"] for disc in discs) / max(len(discs), 1)
    half_width, half_height = board["cell"][0] / 2, board["cell"][1] / 2
    good = (
        sorted(disc["seat"] for disc in discs) == [0, 1, 2, 3]
        and nearest == [level] * 4
        and abs(mean_y - levels[level]) < 0.2
        and abs(mean_x - board["x"]) < 0.2
        and all(abs(disc["y"] - levels[level]) <= half_height for disc in discs)
        and all(abs(disc["x"] - board["x"]) <= half_width for disc in discs)
    )
    detail = {
        "nearest": nearest,
        "mean": (round(mean_x, 2), round(mean_y, 2)),
        "want": (board["x"], levels[level]),
    }
    return good, detail


def finish_draft(page) -> None:
    """Make the four Leader picks from one screen.

    A pick waits on the seat's confirmation like a turn end (open_mode.py).
    Each seat takes the first offered Leader but Piter de Vries, whose
    Round Start adds a Twisted Intrigue card to the one Epic deals.
    """
    for _ in range(12):
        if page.evaluate("state.summary.phase !== 'setup'"):
            break
        if page.evaluate("state.summary.confirmation !== null"):
            page.evaluate("confirmTurn()")
        else:
            page.evaluate(
                "applyAction(state.actions.actions.find("
                "(a) => a.action_id === 'pick_leader'"
                " && a.arguments.leader_id !== 'piter_de_vries').index)"
            )
        settled(page)
    check.ok(
        page.evaluate("state.summary.phase") != "setup",
        "the four picks finish the Leader draft",
        page.evaluate("state.summary.phase"),
    )


def setup_pieces(board: dict, troops: int, intrigue: int) -> None:
    """Every seat's garrison ring and Intrigue count as the setup left them."""
    check.ok(
        board["garrisonData"] == [troops] * 4 and board["garrisons"] == [troops] * 4,
        f"every garrison ring holds {troops} troop pieces",
        (board["garrisonData"], board["garrisons"]),
    )
    check.ok(
        board["intrigueData"] == [intrigue] * 4
        and board["intrigue"] == [intrigue] * 4,
        f"every seat card shows {intrigue} Intrigue card(s)",
        (board["intrigueData"], board["intrigue"]),
    )


def form_boxes(page) -> None:
    print("[1] the boxes on the setup form")
    boxes = page.evaluate(BOXES_JS)
    check.ok(
        boxes["go11"] == {"checked": True, "disabled": False},
        "Go to 11 opens checked and enabled (Immortality is on by default)",
        boxes,
    )
    check.ok(
        boxes["epic"] == {"checked": True, "disabled": False},
        "Epic Game Mode opens checked and enabled",
        boxes,
    )
    order = page.evaluate(ORDER_JS)
    check.ok(
        order.index("opt-epic-game") == order.index("opt-go-to-11") + 1
        and order.index("opt-scouts") == order.index("opt-epic-game") + 1,
        "the Epic box sits after Go to 11 and before Arrakeen Scouts",
        order,
    )
    for box in ("opt-go-to-11", "opt-epic-game"):
        label = page.evaluate(LABEL_JS, box)
        check.ok(
            label["shown"] == label["want"],
            f"{box}: Korean label is the table's text",
            label,
        )
    # Epic moves the end score to 12 (OQ-093), so Go to 11 no longer names 10.
    go11 = page.evaluate(LABEL_JS, "opt-go-to-11")["shown"]
    check.ok("10" not in go11, "the Go to 11 label names no end score", go11)
    shot(page, "setup_form_ko.png", "#setup-form")

    page.uncheck("#opt-immortality")
    boxes = page.evaluate(BOXES_JS)
    check.ok(
        boxes["go11"] == {"checked": False, "disabled": True},
        "Immortality off: Go to 11 is disabled and cleared",
        boxes,
    )
    check.ok(
        boxes["epic"] == {"checked": True, "disabled": False},
        "Immortality off: Epic stays checked and enabled",
        boxes,
    )
    page.check("#opt-immortality")
    boxes = page.evaluate(BOXES_JS)
    check.ok(
        boxes["go11"] == {"checked": False, "disabled": False},
        "Immortality back on: Go to 11 is enabled again and stays cleared",
        boxes,
    )

    # The same round trip on Bloodlines: Go to 11 must end where Tech does.
    page.uncheck("#opt-bloodlines")
    tech_off = page.evaluate(BOXES_JS)["tech"]
    epic_off = page.evaluate(BOXES_JS)["epic"]
    page.check("#opt-bloodlines")
    tech_back = page.evaluate(BOXES_JS)["tech"]
    check.ok(
        tech_off == {"checked": False, "disabled": True}
        and tech_back == boxes["go11"],
        "Go to 11 mirrors the Tech box through its parent's round trip",
        (tech_off, tech_back, boxes["go11"]),
    )
    check.ok(
        epic_off == {"checked": True, "disabled": False},
        "Bloodlines off: Epic stays checked and enabled",
        epic_off,
    )

    switch(page, "en")
    label = page.evaluate(LABEL_JS, "opt-go-to-11")
    check.ok(
        label["shown"] == label["want"]
        and "Immortality" in label["shown"]
        and "10" not in label["shown"],
        "English Go to 11 label is the table's text",
        label,
    )
    label = page.evaluate(LABEL_JS, "opt-epic-game")
    check.ok(
        label["shown"] == label["want"] and label["shown"].startswith("Epic Game Mode"),
        "English Epic label is the table's text",
        label,
    )
    switch(page, "ko")


def go_to_11_epic_game(base: str, browser) -> None:
    print("[2] a game with both boxes checked")
    context, page, rec = open_context(browser, "setup-go-to-11-epic")
    open_setup(page, base)
    form_boxes(page)
    page.check("#opt-tech")
    page.check("#opt-go-to-11")
    body = create(page)
    check.ok(
        body.get("go_to_11") is True
        and body.get("immortality") is True
        and body.get("epic_game") is True,
        "POST /games carries go_to_11 and epic_game true (with Immortality)",
        body,
    )
    board = page.evaluate(TABLE_JS)
    check.ok(board["goTo11"] is True, "the summary says go_to_11", board["goTo11"])
    check.ok(board["epic"] is True, "the summary says epic_game", board["epic"])
    scores = board["scores"]
    # Go to 11 moves the start, Epic the end score (OQ-093).
    check.ok(scores == [0, 0, 0, 0], "every seat starts at 0 VP", scores)
    good, detail = on_level(board, 0)
    check.ok(good, "four score discs sit on the Score track's 0", detail)
    # Drawn once every Leader is known [Rise of Ix p. 10]: none in the draft.
    setup_pieces(board, troops=5, intrigue=0)
    check.ok(
        board["badge"] in board["badges"] and board["epicBadge"] in board["badges"],
        "the header shows the Go to 11 and Epic Game Mode badges",
        board,
    )
    shot(page, "epic_game_header_ko.png", "body > header")
    shot(page, "epic_game_board_ko.png")
    switch(page, "en")
    badges = page.evaluate(TABLE_JS)["badges"]
    check.ok(
        "Go to 11" in badges and "Epic Game Mode" in badges,
        "English header badges",
        badges,
    )
    context.close()


def epic_game(base: str, browser) -> None:
    print("[3] Epic Game Mode with the Go to 11 box cleared")
    context, page, rec = open_context(browser, "setup-epic")
    open_setup(page, base)
    page.uncheck("#opt-go-to-11")
    body = create(page)
    check.ok(
        body.get("go_to_11") is False
        and body.get("immortality") is True
        and body.get("epic_game") is True,
        "POST /games carries go_to_11 false and epic_game true",
        body,
    )
    board = page.evaluate(TABLE_JS)
    check.ok(board["goTo11"] is False, "the summary says no go_to_11", board["goTo11"])
    check.ok(board["epic"] is True, "the summary says epic_game", board["epic"])
    scores = board["scores"]
    check.ok(scores == [1, 1, 1, 1], "every seat starts at 1 VP", scores)
    good, detail = on_level(board, 1)
    check.ok(good, "four score discs sit on the Score track's 1", detail)
    setup_pieces(board, troops=5, intrigue=0)
    badges = board["badges"]
    check.ok(board["badge"] not in badges, "no Go to 11 badge", badges)
    check.ok(board["epicBadge"] in badges, "the Epic Game Mode badge", badges)
    finish_draft(page)
    setup_pieces(page.evaluate(TABLE_JS), troops=5, intrigue=1)
    context.close()


def retail_game(base: str, browser) -> None:
    print("[4] the same game with both boxes cleared")
    context, page, rec = open_context(browser, "setup-plain")
    open_setup(page, base)
    page.uncheck("#opt-go-to-11")
    page.uncheck("#opt-epic-game")
    body = create(page)
    check.ok(
        body.get("go_to_11") is False
        and body.get("immortality") is True
        and body.get("epic_game") is False,
        "POST /games carries go_to_11 and epic_game false",
        body,
    )
    board = page.evaluate(TABLE_JS)
    check.ok(board["epic"] is False, "the summary says no epic_game", board["epic"])
    scores = board["scores"]
    check.ok(scores == [1, 1, 1, 1], "every seat starts at 1 VP", scores)
    good, detail = on_level(board, 1)
    check.ok(good, "four score discs sit on the Score track's 1", detail)
    # The retail setup [Main p. 5]: the contrast shows both counts can fail.
    setup_pieces(board, troops=3, intrigue=0)
    badges = board["badges"]
    check.ok(
        board["badge"] not in badges and board["epicBadge"] not in badges,
        "no Go to 11 or Epic Game Mode badge",
        badges,
    )
    context.close()


def main() -> None:
    with server() as (base, _log), chrome() as browser:
        go_to_11_epic_game(base, browser)
        epic_game(base, browser)
        retail_game(base, browser)
    check.finish()


if __name__ == "__main__":
    main()
