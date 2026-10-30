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
``E2E_SHOTS_DIR`` set, the script also leaves screenshots there: the
setup form (Korean), the Epic game's header and board, and the seat column
with the shuffle box checked.

The rules do not seat players: the First Player comes from the Objective
deal [Main p. 5] whatever the order. On the user's request (2026-10-10) the
setup screen shuffles the configured seats, and with them turn order and
colours, before ``POST /games`` when its "자리 무작위 배치" box is checked; the
server's ``--seating`` only says whether the box opens checked
(``server/seating.py``). On the e2e default server (``--seating fixed``,
``common.py``) the box opens cleared and row N plays seat N; on a
``--seating random`` server it opens checked, survives a language switch
either way, every posted seat list is a permutation of the rows, the human
does not always land on seat 0, and the table opens on the human's seat in
that seat's colour.
"""

from __future__ import annotations

import json
import os
import re
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


# The seat shuffle box, its note and the rows it leaves alone.
SEATING_JS = """() => {
  const box = document.getElementById("opt-shuffle-seats");
  const note = document.getElementById("opt-shuffle-seats-note");
  return {
    checked: box.checked,
    noteShown: !note.hidden,
    note: note.textContent.trim(),
    want: t("html.shuffle_seats_note"),
    label: box.parentElement.textContent.trim(),
    wantLabel: t("html.opt_shuffle_seats"),
    rows: [...document.querySelectorAll("#seat-selects label > span")].map(
      (span) => span.textContent),
    kinds: [...document.querySelectorAll("#seat-selects select")].map(
      (select) => select.value),
  };
}"""

# The seat the table opens on, and its panel's colour against the seat's.
TABLE_SEAT_JS = """() => {
  const rgb = (color) => {
    const probe = document.createElement("i");
    probe.style.color = color;
    document.body.appendChild(probe);
    const value = getComputedStyle(probe).color;
    probe.remove();
    return value;
  };
  const seat = state.viewSeat;
  const card = document.querySelector(`#seats article.seat[data-seat="${seat}"]`);
  return {
    seats: state.summary.seats,
    viewSeat: seat,
    mine: mySeats(),
    panel: card ? getComputedStyle(card).borderLeftColor : null,
    want: seat === null ? null : rgb(SEAT_COLORS[seat]),
  };
}"""

# One human against three heuristic AIs: a permutation moves the human.
SHUFFLE_KINDS = ["human", "heuristic", "heuristic", "heuristic"]
# Held-back creations sampled before one is let through; the human stays on
# seat 0 in all of them with probability (1/4)^8, about 1.5e-5.
SAMPLES = 8


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
                "(a) => a.action_id === 'finish_leader_draft' || (a.action_id === 'pick_leader'"
                " && a.arguments.leader_id !== 'piter_de_vries')).index)"
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


def open_rows(page, base: str) -> None:
    """The setup screen once its rows are drawn (after GET /whoami)."""
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_function(
        "document.querySelectorAll('#seat-selects select').length === 4"
    )


def seat_rows(page, kinds: list[str]) -> None:
    for seat, kind in enumerate(kinds):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", kind)


def table_seat(page, seats: list[str], label: str) -> None:
    """The table holds ``seats`` and opens on the human's, in its colour."""
    human = seats.index("human")
    table = page.evaluate(TABLE_SEAT_JS)
    check.ok(table["seats"] == seats, f"{label}: the game seats what was posted", table)
    check.ok(
        table["viewSeat"] == human and table["mine"] == [human],
        f"{label}: the table opens on the human's seat {human + 1}",
        table,
    )
    check.ok(
        table["panel"] is not None and table["panel"] == table["want"],
        f"{label}: the human's panel wears SEAT_COLORS[{human}]",
        table,
    )


def fixed_seating(base: str, browser) -> None:
    print("[5] --seating fixed: the box opens cleared and row N plays seat N")
    context, page, rec = open_context(browser, "setup-seating-fixed")
    open_rows(page, base)
    form = page.evaluate(SEATING_JS)
    check.ok(
        not form["checked"] and not form["noteShown"],
        "the shuffle box opens cleared and its note hidden",
        form,
    )
    # The human on row 2, so that a kept order is told from seat 0.
    kinds = ["heuristic", "human", "heuristic", "heuristic"]
    seat_rows(page, kinds)
    page.fill("#opt-seed", str(SEED))
    body = create(page)
    check.ok(body.get("seats") == kinds, "POST /games keeps the rows' order", body)
    table_seat(page, kinds, "fixed")
    context.close()


def random_seating(base: str, browser) -> None:
    print("[6] --seating random: the box opens checked and shuffles the seats")
    context, page, rec = open_context(browser, "setup-seating-random")
    open_rows(page, base)
    form = page.evaluate(SEATING_JS)
    check.ok(
        form["checked"] and form["noteShown"],
        "the shuffle box opens checked with its note shown",
        form,
    )
    check.ok(
        form["label"] == form["wantLabel"] == "자리 무작위 배치"
        and form["note"] == form["want"],
        "Korean: the box and its note are the table's text",
        form,
    )
    check.ok(
        form["rows"] == ["플레이어1", "플레이어2", "플레이어3", "플레이어4"],
        "the rows keep their 플레이어1-4 labels",
        form["rows"],
    )
    shot(page, "setup_seating_random_ko.png", ".setup-seats")
    page.uncheck("#opt-shuffle-seats")
    check.ok(
        page.is_hidden("#opt-shuffle-seats-note"), "clearing the box hides its note"
    )
    switch(page, "en")
    form = page.evaluate(SEATING_JS)
    check.ok(
        not form["checked"]
        and not form["noteShown"]
        and form["label"] == "Random seating",
        "English: the cleared box stays cleared across the switch",
        form,
    )
    page.check("#opt-shuffle-seats")
    form = page.evaluate(SEATING_JS)
    check.ok(
        form["checked"]
        and form["noteShown"]
        and form["note"] == form["want"]
        and not re.search("[\uac00-\ud7a3]", form["note"] + form["label"]),
        "English: the box and its note carry no Hangul",
        form,
    )
    switch(page, "ko")
    check.ok(
        page.is_checked("#opt-shuffle-seats"),
        "back in Korean the checked box stays checked",
    )

    seat_rows(page, SHUFFLE_KINDS)
    page.fill("#opt-seed", str(SEED))
    posted: list[list[str]] = []

    def hold(route) -> None:
        # Sample SAMPLES shuffles without creating a game, then let the first
        # one through that seats the human off seat 0.
        if route.request.method != "POST":
            route.continue_()
            return
        seats = route.request.post_data_json["seats"]
        posted.append(seats)
        if len(posted) <= SAMPLES or seats.index("human") == 0:
            route.fulfill(
                status=409,
                content_type="application/json",
                body=json.dumps({"detail": "held back by the e2e"}),
            )
        else:
            route.continue_()

    page.route(re.compile(r"/games$"), hold)
    created = False
    for _ in range(SAMPLES + 24):
        with page.expect_response(
            lambda r: r.request.method == "POST" and r.url.endswith("/games")
        ) as answer:
            page.click("#create-game")
        if answer.value.status == 200:
            created = True
            break
        page.wait_for_selector("#setup-error:not([hidden])")
    page.unroute(re.compile(r"/games$"))
    check.ok(
        bool(posted)
        and all(sorted(seats) == sorted(SHUFFLE_KINDS) for seats in posted),
        "every POST /games carries a permutation of the rows",
        posted,
    )
    sampled = [seats.index("human") for seats in posted[:SAMPLES]]
    check.ok(
        len(sampled) == SAMPLES and any(seat != 0 for seat in sampled),
        f"the human does not land on seat 1 in all {SAMPLES} shuffles",
        sampled,
    )
    check.ok(created, "a shuffled game seating the human off seat 1 starts", posted)
    if not created:
        context.close()
        return
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    table_seat(page, posted[-1], "random")
    form = page.evaluate(SEATING_JS)
    check.ok(
        form["kinds"] == SHUFFLE_KINDS,
        "the setup rows themselves keep the configured order",
        form["kinds"],
    )
    context.close()


FIRST_PLAYER_JS = """() => ({
  checked: el('opt-first-player-seat-zero').checked,
  label: el('opt-first-player-seat-zero').closest('label').textContent.trim(),
})"""


def first_player(base: str, browser, opens_checked: bool) -> None:
    """[7] "Player 1 starts" (OQ-132, user decision 2026-10-25): the server's
    --first-player sets how the box opens; checked, the game seats the First
    Player Objective at seat 0 (the e2e default server, "deal", keeps the
    printed deal [Main p. 5] its seeds were chosen for)."""
    flag = "player1" if opens_checked else "deal"
    print(f"[7] --first-player {flag}: the box opens {'checked' if opens_checked else 'cleared'}")
    context, page, rec = open_context(browser, f"setup-first-player-{flag}")
    open_setup(page, base)
    form = page.evaluate(FIRST_PLAYER_JS)
    check.ok(form["checked"] == opens_checked, f"{flag}: how the box opens", form)
    check.ok("플레이어1" in form["label"], f"{flag}: the Korean label names 플레이어1", form)
    body = create(page)
    check.ok(
        body.get("first_player_seat_zero") is opens_checked,
        f"{flag}: POST /games carries the box",
        body,
    )
    if opens_checked:
        check.ok(
            page.evaluate("state.summary.first_player") == 0,
            "the box checked: Player 1 is the First Player",
            page.evaluate("state.summary.first_player"),
        )
    context.close()


# The base-game select, the Uprising-only boxes it locks, its note and the
# AI seats' kinds (docs/base-game-and-ix-plan.md 18, P5a).
BASE_GAME_JS = """() => {
  const ids = ["opt-choam", "opt-bloodlines", "opt-tech", "opt-immortality",
               "opt-go-to-11", "opt-epic-game", "opt-scouts"];
  const note = document.getElementById("opt-base-game-note");
  return {
    base: document.getElementById("opt-base-game").value,
    boxes: Object.fromEntries(ids.map((id) => {
      const input = document.getElementById(id);
      return [id, {checked: input.checked, disabled: input.disabled}];
    })),
    noteShown: !note.hidden,
    note: note.textContent.trim(),
    want: t("html.base_game_imperium_note"),
    kinds: [...document.querySelectorAll("#seat-selects select")].map(
      (select) => select.value),
    offered: [...document.querySelectorAll("#seat-selects select")].map(
      (select) => [...select.options].map((option) => option.value)),
    table: state.server.seat_kinds,
    // The promo box's label as shown, and each base game's own.
    promo: [...document.querySelectorAll("#opt-promo ~ span")]
      .filter((span) => !span.hidden).map((span) => span.textContent.trim()),
    promoWant: {uprising: t("html.opt_promo"), imperium: t("html.opt_promo_imperium")},
    ix: (() => {
      const box = document.getElementById("opt-rise-of-ix");
      return {checked: box.checked, disabled: box.disabled};
    })(),
  };
}"""

# The original game's table as drawn: its own board picture (stage P5b), the
# spaces on it, and the header's badges.
ORIGINAL_TABLE_JS = """() => {
  const badges = document.querySelector("#header-status .status-badges");
  return {
    base: state.summary.base_game,
    view: state.view.base_game,
    scan: Boolean(document.querySelector("#board .board-stage")),
    spaces: [...document.querySelectorAll(
      "#board .board-stage .hotspot[data-space], #board .space-row")].map(
      (node) => node.dataset.space),
    badges: badges ? badges.textContent : "",
    badge: t("screens.base_game_imperium_badge"),
  };
}"""

UPRISING_ONLY_SPACES = {"deep_desert", "spice_refinery", "espionage", "sardaukar"}
ORIGINAL_SPACES = {"carthag", "conspire", "the_great_flat", "mentat", "hall_of_oratory"}


def original_game(base: str, browser) -> None:
    """[8] The base-game select (P5a): the original game locks the options it
    cannot take yet and gives them back on a return to Uprising, names its
    own promo cards on the promo box, keeps the picked kinds its table takes
    (the app AI since P6) and seats the default app AI elsewhere, and starts
    a game drawn on its own board picture with the original spaces only."""
    print("[8] the base-game select: the original game")
    context, page, rec = open_context(browser, "setup-original-game")
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.wait_for_function(
        "state.server !== null"
        " && document.querySelectorAll('#seat-selects select').length === 4"
    )
    before = page.evaluate(BASE_GAME_JS)
    check.ok(before["base"] == "uprising", "the select opens on Uprising", before)
    check.ok(not before["noteShown"], "Uprising: no note", before)
    check.ok(
        before["promo"] == [before["promoWant"]["uprising"]],
        "Uprising: the promo box names Uprising's promos",
        before["promo"],
    )
    page.select_option("#seat-selects select[data-seat='1']", "random")
    page.select_option("#seat-selects select[data-seat='2']", "app_ai_easy")
    page.select_option("#seat-selects select[data-seat='3']", "rollout")
    page.select_option("#opt-base-game", "imperium")
    original = page.evaluate(BASE_GAME_JS)
    check.ok(
        all(box == {"checked": False, "disabled": True}
            for box in original["boxes"].values()),
        "the original game clears and locks every Uprising-only box",
        original["boxes"],
    )
    check.ok(
        original["noteShown"] and original["note"] == original["want"],
        "the original game shows its note",
        original,
    )
    check.ok(
        before["ix"] == {"checked": False, "disabled": True}
        and original["ix"] == {"checked": False, "disabled": False},
        "Rise of Ix is offered on the original game only, unchecked",
        {"uprising": before["ix"], "original": original["ix"]},
    )
    check.ok(
        original["promo"] == [original["promoWant"]["imperium"]],
        "the original game: the promo box names its own three promos",
        original["promo"],
    )
    check.ok(
        original["kinds"] == ["human", "random", "app_ai_easy", "app_ai"],
        "picked random and app AI seats stay (the app AI plays the original game"
        " since P6); a rollout seat the original table refuses becomes the"
        " default app AI",
        original["kinds"],
    )
    allowed = sorted(original["table"]["imperium"])
    check.ok(
        allowed == ["app_ai", "app_ai_easy", "app_ai_medium", "heuristic", "human",
                    "random"]
        and all(sorted(kinds) == allowed for kinds in original["offered"]),
        "every seat offers just the original table's kinds (GET /whoami seat_kinds)",
        {"table": original["table"], "offered": original["offered"][0]},
    )
    page.select_option("#opt-base-game", "uprising")
    back = page.evaluate(BASE_GAME_JS)
    check.ok(
        back["boxes"] == before["boxes"] and back["kinds"] == [
            "human", "random", "app_ai_easy", "app_ai"]
        and back["promo"] == before["promo"]
        and back["ix"] == {"checked": False, "disabled": True},
        "back on Uprising: the boxes come back, the picked seats stay and the"
        " refused one keeps the default",
        {"before": before, "back": back},
    )
    open_setup(page, base)
    page.select_option("#opt-base-game", "imperium")
    with page.expect_request(
        lambda r: r.method == "POST" and r.url.endswith("/games")
    ) as sent:
        page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    settled(page)
    body = sent.value.post_data_json
    check.ok(
        body.get("base_game") == "imperium"
        and not any(body.get(key) for key in (
            "choam_module", "bloodlines", "tech_module", "immortality",
            "go_to_11", "epic_game", "arrakeen_scouts")),
        "POST /games carries the original game without Uprising-only options",
        body,
    )
    table = page.evaluate(ORIGINAL_TABLE_JS)
    spaces = set(table["spaces"])
    check.ok(
        table["base"] == "imperium" and table["view"] == "imperium",
        "the summary and the view name the original game",
        table,
    )
    check.ok(
        table["scan"], "the original game is drawn on its own board picture", table
    )
    check.ok(
        ORIGINAL_SPACES <= spaces and not (UPRISING_ONLY_SPACES & spaces)
        and len(spaces) == 22,
        "the board carries the original game's 22 spaces only",
        sorted(spaces),
    )
    check.ok(
        table["badges"].startswith(" · ") and table["badge"] in table["badges"],
        "the header names the original game",
        table,
    )
    check.ok(not rec.js_errors, "no page errors", rec.js_errors)
    context.close()


# What the original + Rise of Ix Epic table shows beyond TABLE_JS: the
# Leaders, each seat's public deck pool, and the original board's Score track.
EPIC_TABLE_JS = """() => ({
  leaders: state.view.players.map((player) => player.leader_id),
  pools: state.view.players.map((player) => player.deck_pool),
  levels: boardLayout(state.view).tracks.victory_points.levels.length,
  ix: state.summary.rise_of_ix,
  base: state.summary.base_game,
})"""

# Rise of Ix's six Leaders (content.rise_of_ix.leaders).
IX_LEADERS = {
    "princess_yuna_moritani",
    "prince_rhombur_vernius",
    "archduke_armand_ecaz",
    "viscount_hundro_moritani",
    "ilesa_ecaz",
    "tessia_vernius",
}


def original_ix_epic(base: str, browser) -> None:
    """[9] Epic Game Mode on the original game (P4 d88c6a7d): it is the Rise
    of Ix rulebook's mode [Rise of Ix p. 10], so the original game takes it
    with Rise of Ix only (docs/rules/rise-of-ix.md 11; Uprising plays it alone,
    OQ-092). The box stays locked while the original game has no Rise of Ix,
    opens checked with it and locks again without it. The game starts with
    five garrison troops a seat, each seat's Intrigue card once the Leaders
    are drafted, Control the Spice in each deck for one of its two Dune, the
    Desert Planet ("좌석마다 Dune, the Desert Planet 하나를 Control the Spice로
    바꾸고, 모두 Intrigue 1장을 뽑고 ... garrison troop 5로 시작한다", rise-of-ix.md
    11), the Rise of Ix Leaders in the draft, and a Score track that holds the
    12 points the mode plays to."""
    print("[9] Epic Game Mode on the original game with Rise of Ix")
    context, page, rec = open_context(browser, "setup-original-epic")
    open_setup(page, base)
    page.select_option("#opt-base-game", "imperium")
    without = page.evaluate(BOXES_JS)["epic"]
    page.check("#opt-rise-of-ix")
    opened = page.evaluate(BOXES_JS)["epic"]
    page.uncheck("#opt-rise-of-ix")
    again = page.evaluate(BOXES_JS)["epic"]
    page.check("#opt-rise-of-ix")
    check.ok(
        without == again == {"checked": False, "disabled": True}
        and opened == {"checked": True, "disabled": False}
        and page.evaluate(BOXES_JS)["epic"] == opened,
        "the original game's Epic box is locked without Rise of Ix and opens,"
        " checked, with it",
        {"without": without, "opened": opened, "again": again},
    )
    body = create(page)
    check.ok(
        body.get("base_game") == "imperium"
        and body.get("rise_of_ix") is True
        and body.get("epic_game") is True,
        "POST /games carries the original game, Rise of Ix and epic_game",
        body,
    )
    board = page.evaluate(TABLE_JS)
    check.ok(board["epic"] is True, "the summary says epic_game", board["epic"])
    check.ok(board["epicBadge"] in board["badges"], "the Epic Game Mode badge", board)
    setup_pieces(board, troops=5, intrigue=0)
    offered = page.evaluate(
        "state.actions.actions.filter((a) => a.action_id === 'pick_leader')"
        ".map((a) => a.arguments.leader_id)"
    )
    check.ok(
        bool(set(offered) & IX_LEADERS),
        "the Leader draft offers Rise of Ix's Leaders",
        offered,
    )
    finish_draft(page)
    setup_pieces(page.evaluate(TABLE_JS), troops=5, intrigue=1)
    table = page.evaluate(EPIC_TABLE_JS)
    check.ok(
        all(table["leaders"]) and table["base"] == "imperium" and table["ix"],
        "every seat has its Leader once the draft is over",
        table["leaders"],
    )
    check.ok(
        all(
            pool.count("control_the_spice") == 1
            and pool.count("dune_the_desert_planet") == 1
            for pool in table["pools"]
        ),
        "every deck holds Control the Spice and one Dune, the Desert Planet",
        table["pools"],
    )
    check.ok(
        table["levels"] == 13,
        "the original board's Score track prints 0 to 12, the Epic goal",
        table["levels"],
    )
    check.ok(not rec.js_errors, "no page errors", rec.js_errors)
    context.close()


def main() -> None:
    with chrome() as browser:
        with server() as (base, _log):
            original_game(base, browser)
            original_ix_epic(base, browser)
            go_to_11_epic_game(base, browser)
            epic_game(base, browser)
            retail_game(base, browser)
            fixed_seating(base, browser)
            first_player(base, browser, opens_checked=False)
        with server("--seating", "random") as (base, _log):
            random_seating(base, browser)
        with server("--first-player", "player1") as (base, _log):
            first_player(base, browser, opens_checked=True)
    check.finish()


if __name__ == "__main__":
    main()
