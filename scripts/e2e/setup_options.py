"""The setup form's Go to 11 box (2026-09-28, OQ-091).

The Immortality rulebook's "Go to 11" variant starts every Score marker at 0
instead of 1 and still ends the game at 10 [Immortality p. 12]. The user
chose to offer it only with Immortality and to check its box by default (the
digital game and tournaments play it that way), while the engine and the
CLI keep it off. So the box must:

- open checked, and follow the Immortality box the way the Tech Module box
  follows Bloodlines: disabled and cleared while its parent is off, enabled
  again (still cleared, like Tech) when the parent comes back;
- reach the server as ``go_to_11`` in the POST /games body, come back in the
  summary, and show a header badge;
- put all four seats' score discs on the Score track's printed 0 at the
  first decision, and on 1 when the box is cleared (the contrast shows the
  geometry check can fail).

Four human seats keep the table at its first decision (the Leader draft,
which the draft box leaves on), before any seat could score.
"""

from __future__ import annotations

from common import Check, chrome, open_context, server
from lang import switch
from open_mode import settled

check = Check()

SEED = 11

BOXES_JS = """() => {
  const box = (id) => {
    const input = document.getElementById(id);
    return {checked: input.checked, disabled: input.disabled};
  };
  return {
    bloodlines: box("opt-bloodlines"), tech: box("opt-tech"),
    immortality: box("opt-immortality"), go11: box("opt-go-to-11"),
  };
}"""

LABEL_JS = """() => ({
  shown: document.getElementById("opt-go-to-11").parentElement.textContent.trim(),
  want: t("html.opt_go_to_11"),
})"""

# Each seat's score disc as drawn: its centre in percent of the board stage,
# with the Score track's printed levels (catalog.tracks.victory_points).
DISCS_JS = """() => {
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
  const badges = document.querySelector("#header-status .status-badges");
  return {
    discs, x: track.x, levels: track.levels, cell: track.cell,
    scores: state.view.players.map((player) => player.victory_points),
    goTo11: state.summary.go_to_11,
    badges: badges ? badges.textContent : "",
    badge: t("render.badge_go_to_11"),
  };
}"""


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


def form_boxes(page) -> None:
    print("[1] the box on the setup form")
    boxes = page.evaluate(BOXES_JS)
    check.ok(
        boxes["go11"] == {"checked": True, "disabled": False},
        "Go to 11 opens checked and enabled (Immortality is on by default)",
        boxes,
    )
    label = page.evaluate(LABEL_JS)
    check.ok(label["shown"] == label["want"], "Korean label is the table's text", label)

    page.uncheck("#opt-immortality")
    boxes = page.evaluate(BOXES_JS)
    check.ok(
        boxes["go11"] == {"checked": False, "disabled": True},
        "Immortality off: Go to 11 is disabled and cleared",
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
    page.check("#opt-bloodlines")
    tech_back = page.evaluate(BOXES_JS)["tech"]
    check.ok(
        tech_off == {"checked": False, "disabled": True}
        and tech_back == boxes["go11"],
        "Go to 11 mirrors the Tech box through its parent's round trip",
        (tech_off, tech_back, boxes["go11"]),
    )

    switch(page, "en")
    label = page.evaluate(LABEL_JS)
    check.ok(
        label["shown"] == label["want"] and "Immortality" in label["shown"],
        "English label is the table's text",
        label,
    )
    switch(page, "ko")


def go_to_11_game(base: str, browser) -> None:
    print("[2] a game with the box checked")
    context, page, rec = open_context(browser, "setup-go-to-11")
    open_setup(page, base)
    form_boxes(page)
    page.check("#opt-tech")
    page.check("#opt-go-to-11")
    body = create(page)
    check.ok(
        body.get("go_to_11") is True and body.get("immortality") is True,
        "POST /games carries go_to_11 true (with Immortality)",
        body,
    )
    board = page.evaluate(DISCS_JS)
    check.ok(board["goTo11"] is True, "the summary says go_to_11", board["goTo11"])
    scores = board["scores"]
    check.ok(scores == [0, 0, 0, 0], "every seat starts at 0 VP", scores)
    good, detail = on_level(board, 0)
    check.ok(good, "four score discs sit on the Score track's 0", detail)
    check.ok(
        board["badge"] in board["badges"], "the header shows the Go to 11 badge", board
    )
    switch(page, "en")
    badges = page.evaluate(DISCS_JS)["badges"]
    check.ok("Go to 11" in badges, "English header badge", badges)
    context.close()


def plain_game(base: str, browser) -> None:
    print("[3] the same game with the box cleared")
    context, page, rec = open_context(browser, "setup-plain")
    open_setup(page, base)
    page.uncheck("#opt-go-to-11")
    body = create(page)
    check.ok(
        body.get("go_to_11") is False and body.get("immortality") is True,
        "POST /games carries go_to_11 false",
        body,
    )
    board = page.evaluate(DISCS_JS)
    check.ok(board["goTo11"] is False, "the summary says no go_to_11", board["goTo11"])
    scores = board["scores"]
    check.ok(scores == [1, 1, 1, 1], "every seat starts at 1 VP", scores)
    good, detail = on_level(board, 1)
    check.ok(good, "four score discs sit on the Score track's 1", detail)
    badges = board["badges"]
    check.ok(board["badge"] not in badges, "no Go to 11 badge", badges)
    context.close()


def main() -> None:
    with server() as (base, _log), chrome() as browser:
        go_to_11_game(base, browser)
        plain_game(base, browser)
    check.finish()


if __name__ == "__main__":
    main()
