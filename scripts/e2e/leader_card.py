"""E2E of leader-specific state drawn on the leader card itself (2026-09-25).

Feyd-Rautha Harkonnen's Training track and Chani's Tactics track each hold a
per-seat token printed on the Leader's own card [Main p. 17] [Bloodlines
p. 12]; today the seat panel's leader popover (thumbnail or name, hover or
pin, `panels.js` `renderSeats`, `core.js` `openPopover`/`hoverPopover`/
`pinPopover`) shows only the card's static ability/signet text. This checks
that it now draws the seat's own live token on the card image, at the box
`display.leader_layout` measures for that state (served as
`catalog.leaders[id].layout`, checked at the unit level by
`tests/unit/display/test_leader_layout.py`):

(a) an edited view (the technique `board_tokens.py` uses: the view is the
    render's only input) steps Feyd's token through every
    `FEYD_TRAINING_TRACK` space id and Chani's through every printed index
    0..10, opens the seat's leader popover each time, and asserts the
    token's measured centre lies inside the printed box — in both Korean
    and English (the card image switches language; the box table does not,
    and the Korean images are shorter by a couple of pixels, report_assets.md
    §4, so this is also what proves the boxes still fit them).
(b) a real, unedited game: Feyd-Rautha Harkonnen dealt to seat 0 by a fixed
    (non-draft) setup, so the token's position comes from the live state the
    server actually sent, not the edited view. No seed is known ahead of
    time to deal a particular leader, so `_find_leader_seed` below does a
    one-off raw-HTTP search (`POST /games` + `GET .../seats/0/view`, no
    browser) over `game_seed` until seat 0's `leader_id` matches, the same
    technique `turn_end.py`'s `find_draft_seed` uses for a different search;
    the browser then replays that exact seed and ruleset.
(c) Lady Jessica's one-way flip [Main p. 17]: an edited view with
    `leader_face_id` set to `"reverend_mother_jessica"` shows that face's
    own picture in the popover (already wired end to end by
    `player.leader_face_id || player.leader_id`, `panels.js`; this only
    confirms the new stage wrapper does not disturb it).

A bonus check (not asked for, cheap to add): without a card image (no local
asset, `catalog.leaders[id].image` null) the popover draws no stage and
instead one plain text line naming the space, reusing `panels.tactics_space`
for Chani and the new `panels.feyd_track_space` (worded from the same
`FEYD_TRACK_LABELS` the turn log already uses) for Feyd-Rautha.

Must fail on the old client (A/B, `docs/lessons.md` 2026-09-21): none of
`.popover-leader-stage`, `.leader-token` or the seat-aware
`openPopover(entry, anchor, seatState)` signature exist there, so every
token-in-box assertion below fails cleanly (the old popover draws a bare
`<img>`, so the stage/token selectors simply find nothing).
"""

from __future__ import annotations

import json
import shutil
import urllib.request

from common import (
    LAPTOP_VIEWPORT,
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from lang import switch as switch_language

check = Check()

# Percent of the leader-card popover stage: the token is small relative to
# it (~340px wide at most, core.js's LEADER_TOKEN_SIZE), so a subpixel
# rounding slack that would be invisible on the ~900px board stage
# (board_tokens.py's TOLERANCE) is worth a little more room here.
TOLERANCE = 0.35

TOKEN_JS = """() => {
  const stage = document.querySelector("#card-popover .popover-leader-stage");
  if (!stage) return { stage: false, image: null, token: null };
  const stageRect = stage.getBoundingClientRect();
  const image = stage.querySelector("img");
  const token = stage.querySelector(".leader-token");
  return {
    stage: true,
    // The raw attribute (a catalog-relative path, e.g. "/card-images/ko/..."),
    // not the DOM's auto-resolved absolute .src: this is compared against
    // the language folder in the URL, not against an origin-prefixed one.
    image: image ? image.getAttribute("src") : null,
    token: token
      ? (() => {
          const t = token.getBoundingClientRect();
          return {
            cx: ((t.left + t.width / 2 - stageRect.left) / stageRect.width) * 100,
            cy: ((t.top + t.height / 2 - stageRect.top) / stageRect.height) * 100,
          };
        })()
      : null,
  };
}"""


def _open_fixed_game(page, base: str, *, seed: int, bloodlines: bool) -> None:
    """A single-human game with leaders assigned at setup, not drafted, so
    the seat's leader (and, for (b), which one) is fixed by the seed alone."""

    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    page.select_option("#seat-selects select[data-seat='0']", "human")
    for seat in range(1, 4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    set_rule_options(page, *(("bloodlines",) if bloodlines else ()))
    page.uncheck("#opt-leader-draft")
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")


def _set_leader_and_open(page, seat: int, leader_id: str, *, face_id=None, **fields):
    """Edit the seat's leader state in the page and open its popover
    (the view is the render's only input, as `board_tokens.py` uses it)."""

    page.evaluate(
        """(args) => {
          const [seat, leaderId, faceId, fields] = args;
          const player = state.view.players[seat];
          player.leader_id = leaderId;
          player.leader_face_id = faceId;
          Object.assign(player, fields);
          render();
        }""",
        [seat, leader_id, face_id, fields],
    )
    page.click(f'.seat[data-seat="{seat}"] .leader-name')
    page.wait_for_function(
        "() => { const img = document.querySelector("
        "'#card-popover .popover-leader-stage img');"
        " return Boolean(img) && img.complete && img.naturalWidth > 0; }"
    )


def _box_contains(box: list[float], point: dict) -> bool:
    left, top, width, height = box
    return (
        left - TOLERANCE <= point["cx"] <= left + width + TOLERANCE
        and top - TOLERANCE <= point["cy"] <= top + height + TOLERANCE
    )


def _is_language_image(image: str | None, lang: str) -> bool:
    # The catalog's relative image path carries the language folder
    # (server.catalog._image_url -> display.images.resolve_card_images):
    # "/card-images/en/..." or "/card-images/ko/...". This is what actually
    # proves the switch took effect, rather than trusting a value computed
    # ahead of time from a catalog snapshot `localizeCatalog` may since have
    # mutated in place.
    return bool(image) and f"/card-images/{lang}/" in image


def feyd_geometry(page, lang: str) -> None:
    print(f"[1] Feyd-Rautha ({lang}): the token centres inside every track box")
    catalog = page.evaluate("state.catalog")
    boxes = catalog["leaders"]["feyd_rautha_harkonnen"]["layout"]["track"]
    for space_id, box in boxes.items():
        _set_leader_and_open(
            page, 0, "feyd_rautha_harkonnen", feyd_track_space=space_id
        )
        shown = page.evaluate(TOKEN_JS)
        check.ok(
            shown["stage"] and shown["token"] and _box_contains(box, shown["token"]),
            f"feyd {space_id} ({lang}): token centred in its printed box",
            shown,
        )
        check.ok(
            _is_language_image(shown["image"], lang),
            f"feyd {space_id} ({lang}): the {lang} card image",
            shown["image"],
        )


def chani_geometry(page, lang: str) -> None:
    print(f"[2] Chani ({lang}): the token centres inside every track box")
    catalog = page.evaluate("state.catalog")
    boxes = catalog["leaders"]["chani"]["layout"]["track"]
    check.ok(len(boxes) == 11, "eleven printed Tactics spaces", len(boxes))
    for index, box in enumerate(boxes):
        _set_leader_and_open(page, 0, "chani", tactics_track_space=index)
        shown = page.evaluate(TOKEN_JS)
        check.ok(
            shown["stage"] and shown["token"] and _box_contains(box, shown["token"]),
            f"chani space {index + 1} ({lang}): token centred in its printed box",
            shown,
        )
        check.ok(
            _is_language_image(shown["image"], lang),
            f"chani space {index + 1} ({lang}): the {lang} card image",
            shown["image"],
        )


def no_image_fallback(page) -> None:
    """Run while the page is in English: the expected fallback wording
    below ("Tactics space 5") is `panels.tactics_space`'s English text."""

    print("[3] without a card image: a text line, not a stage")
    catalog = page.evaluate("state.catalog")
    saved = {
        "image": catalog["leaders"]["chani"].get("image"),
        "image_ko": catalog["leaders"]["chani"].get("image_ko"),
    }
    page.evaluate(
        """() => {
          state.catalog.leaders.chani.image = null;
          state.catalog.leaders.chani.image_ko = null;
        }"""
    )
    page.evaluate(
        """(seat) => {
          const player = state.view.players[seat];
          player.leader_id = "chani";
          player.leader_face_id = null;
          player.tactics_track_space = 4;
          render();
        }""",
        0,
    )
    page.click('.seat[data-seat="0"] .leader-name')
    shown = page.evaluate(
        """() => {
          const pop = document.getElementById("card-popover");
          const last = pop.lastElementChild;
          return {
            stage: Boolean(pop.querySelector(".popover-leader-stage")),
            lastText: last ? last.textContent.trim() : null,
          };
        }"""
    )
    check.ok(not shown["stage"], "no stage without a card image", shown)
    check.ok(
        shown["lastText"] == "Tactics space 5",
        "the fallback line names the printed space",
        shown["lastText"],
    )
    page.evaluate(
        """(saved) => {
          state.catalog.leaders.chani.image = saved.image;
          if (saved.image_ko) state.catalog.leaders.chani.image_ko = saved.image_ko;
        }""",
        saved,
    )


def jessica_flip(page) -> None:
    """Run while the page is in English (Reverend Mother Jessica has no
    Korean art, report_assets.md §1, so her English file is what any
    language shows; testing this while English keeps the check unambiguous
    -- it is not exercising the Korean-art gap, only the stage wrapper)."""

    print("[4] Lady Jessica: the flipped face's own picture in the popover")
    _set_leader_and_open(
        page, 0, "lady_jessica", face_id="reverend_mother_jessica"
    )
    shown = page.evaluate(TOKEN_JS)
    check.ok(
        shown["stage"]
        and _is_language_image(shown["image"], "en")
        and "Reverend" in (shown["image"] or ""),
        "the popover shows Reverend Mother Jessica's own image",
        shown,
    )
    check.ok(shown["token"] is None, "no on-card token for a leader with no layout")
    title = page.evaluate(
        "document.querySelector('#card-popover .popover-title').textContent"
    )
    check.ok(title == "Reverend Mother Jessica", "and her own name as the title", title)


def _api_post(base: str, path: str, body: dict) -> dict:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        result: dict = json.loads(response.read())
    return result


def _api_get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path) as response:
        result: dict = json.loads(response.read())
    return result


def _find_leader_seed(base: str, leader_id: str, *, limit: int = 250) -> int | None:
    """A `game_seed` where a fixed (non-draft) setup deals `leader_id` to
    seat 0, found with raw HTTP (no browser: one `POST /games` + one
    `GET .../seats/0/view` per candidate seed, discarding the session
    either way — the server keeps every one open, but this is a short-lived
    local e2e server torn down right after)."""

    for seed in range(limit):
        summary = _api_post(
            base,
            "/games",
            {
                "seats": ["human", "heuristic", "heuristic", "heuristic"],
                "leader_draft": False,
                "game_seed": seed,
            },
        )
        game_id = summary["game_id"]
        view = _api_get(base, f"/games/{game_id}/seats/0/view")
        if view["players"][0]["leader_id"] == leader_id:
            return seed
    return None


def live_feyd_token(base: str, browser) -> None:
    print("[5] a real game: Feyd-Rautha's token at the server's own live space")
    seed = _find_leader_seed(base, "feyd_rautha_harkonnen")
    if not check.ok(seed is not None, "a seed deals Feyd-Rautha to seat 0"):
        return
    context, page, rec = open_context(browser, "feyd-live")
    _open_fixed_game(page, base, seed=seed, bloodlines=False)
    leader_id = page.evaluate("state.view.players[0].leader_id")
    space_id = page.evaluate("state.view.players[0].feyd_track_space")
    if not check.ok(
        leader_id == "feyd_rautha_harkonnen",
        "the replayed seed deals the same leader",
        leader_id,
    ):
        context.close()
        return
    page.click('.seat[data-seat="0"] .leader-name')
    page.wait_for_function(
        "() => { const img = document.querySelector("
        "'#card-popover .popover-leader-stage img');"
        " return Boolean(img) && img.complete && img.naturalWidth > 0; }"
    )
    shown = page.evaluate(TOKEN_JS)
    catalog = page.evaluate("state.catalog")
    box = catalog["leaders"]["feyd_rautha_harkonnen"]["layout"]["track"][space_id]
    check.ok(
        shown["stage"] and shown["token"] and _box_contains(box, shown["token"]),
        f"the live state's own space ({space_id}) matches the token drawn",
        shown,
    )
    check.ok(not rec.js_errors, "no JS exceptions (live Feyd game)", rec.js_errors[:5])
    context.close()


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        try:
            context, page, rec = open_context(browser, "leader-card", LAPTOP_VIEWPORT)
            # Bloodlines only widens the setup form to include Chani; the
            # catalog carries every leader's layout regardless of ruleset
            # (build_catalog is not filtered by config), so nothing below
            # depends on it beyond letting a live Chani game exist too.
            _open_fixed_game(page, base, seed=0, bloodlines=True)
            # Korean is the page's own default (lang.py); English is not
            # assumed, it is switched to explicitly.
            switch_language(page, "en")

            feyd_geometry(page, "en")
            chani_geometry(page, "en")
            no_image_fallback(page)
            jessica_flip(page)

            switch_language(page, "ko")
            feyd_geometry(page, "ko")
            chani_geometry(page, "ko")

            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()

            live_feyd_token(base, browser)
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
