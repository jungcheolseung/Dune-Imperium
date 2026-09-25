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
    and the Korean images are shorter by a couple of pixels, so this is
    also what proves the boxes still fit them).
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
(d) Steersman Y'rkoon's four Navigation-card slots [Bloodlines p. 12]: a row
    above the leader image, not a token on it, and per-slot visibility
    instead of one shared box -- a played slot's card is public
    (`navigation_played`), an unplayed one is owner-only
    (`view.private.navigation_slots`, "may look at his face-down Navigation
    cards at any time" `docs/rules/bloodlines.md:142` [Bloodlines p. 12]).
    `navigation_geometry` edits every combination of 0-4 played/remaining
    (the technique of (a)) and checks, for both an owner's view (Y'rkoon at
    seat 0, this fixed game's own viewing seat) and a non-owner's (Y'rkoon
    at seat 1 instead, against the very same seat-0 viewer, `view.private`
    left as that viewer's own real, untouched private view rather than
    forced to `null` -- a real non-owner's `view.private` is always present,
    for the viewer's own seat, and simply never carries `navigation_slots`
    for a leader some other seat holds, `core/observation.py`): the right
    count of cards, each centred on its slot's measured x-span and the row
    itself sitting above the leader image, played ones face up for anyone,
    unplayed ones the owner's own muted face with a face-down badge but a
    non-owner's plain identity-free placeholder
    (no back art exists for a Navigation card).
    `navigation_option_wording` covers ITEM 8b's twin for `play_navigation`
    (`describeAction`'s new branch, core.js): the live row (only "option" in
    the action, the card read from the front of `view.private.
    navigation_slots`, gated on the action carrying no "type" key at all --
    server/sessions.py `_serialize_action` -- so neither a logged step nor a
    replay-review label can fall back to it), a logged step (the card read
    from its own `navigation_card_played` event instead), a replay-review
    label with no event and no "type"-gated live fallback (the plain
    bare-index text, never the wrong slot's own card), and the same
    bare-index fallback when nothing else resolves — with an edited action
    list rather than a real decision, `intrigue_options.py`'s technique for
    the same wording problem on `play_intrigue`. `live_yrkoon_navigation` is
    the real-game case analogous to (b), but on a `--remote` server with two
    browser contexts each holding a different seat (open-mode hides nothing
    from a second context sharing the same browser cookies, so only
    `--remote` proves the server itself, not just the client, keeps the
    other seat blind): seat 0's own page must show its unplayed slots'
    faces, seat 1's page must show placeholders only, and seat 1's own
    `view.private.navigation_slots` must stay empty throughout.
    `review_label_repro` is a real *replay-review* case reproducing the
    reviewer's own bug report exactly (2026-09-25): at `game_seed=2`
    (all-heuristic, Bloodlines + Leader Draft) Steersman Y'rkoon deterministically
    drafts to seat 3, and by replay-review cursor 121 (the view after log
    step 120, a `play_navigation`) the card that step actually played has
    already left `view.private.navigation_slots` for the next one -- so the
    review label must read the plain bare-index fallback, never that next
    card's name, while the turn log's own line for the very same step (it
    carries its own event) still correctly names the card that was played.

A bonus check (not asked for, cheap to add): without a card image (no local
asset, `catalog.leaders[id].image` null) the popover draws no stage and
instead plain text lines naming the state (`leaderFallbackLines`, core.js):
`panels.tactics_space` for Chani, `panels.feyd_track_space` (worded from the
same `FEYD_TRACK_LABELS` the turn log already uses) for Feyd-Rautha,
`panels.navigation_progress` (played/remaining counts) for Steersman
Y'rkoon, and `panels.secret_project` for Kota Odax while he still holds one.

STEP L3 (2026-09-25) moves two more pieces of state onto the leader popover
and removes their old homes:

(e) Kota Odax of Ix's kept Secret Project tile [Bloodlines p. 6]:
    `kota_secret_project` edits `has_secret_project` and (for the owner)
    `view.private.secret_project_tech_id` and checks the popover draws the
    tile below the leader image (`.popover-secret-project-row`) -- the
    owner's own muted face with the same "Face down" badge a face-down
    Navigation slot uses, a non-owner's identity-free `.tile-back`
    placeholder, and nothing at all once `has_secret_project` turns false
    (acquired). The private-zone "peeks" strip (`panels.js` `renderPrivate`)
    no longer carries a second copy of it.
(f) Shaddam Corrino IV's two set-aside Sardaukar contracts [Main p. 17]
    [FAQ p. 3]: `shaddam_sardaukar` checks the shared market column never
    draws a Sardaukar strip any more (regardless of who, if anyone, holds
    them), and that his own leader popover draws them face up below his
    image (`.popover-sardaukar-row`) from the same public
    `view.sardaukar_contract_ids`, shrinking as an edited view removes one.
(g) `status_line_drops_leader_flags` checks the seat panel's own folding
    status line (`panels.js` `renderSeats`) no longer repeats Chani's
    Tactics space, Y'rkoon's remaining Navigation count or Kota's Secret
    Project flag now that the popover carries them, while Piter's Twisted
    deck count and spies boxed still do.

A regression the screenshots for (e)/(f) caught, not asked for in the task
(2026-09-25): a popover's own leader image has no explicit CSS
`aspect-ratio`, so `placePopover` (called synchronously, before the image
has necessarily loaded) can measure a too-short popover and misplace it.
Fixed with a `load`-triggered reposition, which a scratch A/B verified is
what actually keeps a low popover from running off the viewport;
`visualCard`'s own default `loading="lazy"` on Kota's tile / Shaddam's
contracts was also forced eager (`eagerCard`, core.js) as a cheap
belt-and-suspenders guard against a mispositioned popover missing the
browser's lazy-load threshold, though the same A/B found the reposition
alone sufficient for every image to load.
`leader_popover_settles_within_viewport` opens both popovers
from the last seat on the 1366x768 laptop viewport (low enough that the
unfixed popover ran off the bottom) with no settling wait first, and
checks the extra row still ends up fully visible with every image loaded.

Must fail on the old client (A/B, `docs/lessons.md` 2026-09-21): none of
`.popover-leader-stage`, `.leader-token`, `.popover-navigation-row`,
`.leader-nav-card`/`.nav-card-back`, `.popover-secret-project-row`,
`.tile-back`, `.popover-sardaukar-row`, the seat-aware `openPopover(entry,
anchor, seatState)` signature, or `describeAction`'s `play_navigation`
branch exist there, so every token-in-box, Navigation-row, Secret-Project,
Sardaukar-row and option-wording assertion below fails cleanly (the old
popover draws a bare `<img>`, so the stage/token/row selectors simply find
nothing, a `play_navigation` row still reads "선택지: N", the old client's
seat status line still carries all three flags, and its market strip still
draws Shaddam's contracts whenever `view.sardaukar_contract_ids.length`).
"""

from __future__ import annotations

import json
import shutil
import time
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
from open_mode import settled

check = Check()

# The admin key for `live_yrkoon_navigation`'s throwaway --remote server
# (unique per script, like remote_fresh.py's own KEY, so a stray leftover
# process from another script's run is never mistaken for this one's).
YRKOON_ADMIN_KEY = "e2e-leader-card-admin-key"

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


NAVIGATION_JS = """() => {
  const row = document.querySelector("#card-popover .popover-navigation-row");
  const stage = document.querySelector("#card-popover .popover-leader-stage");
  if (!row) return { row: false, cards: [], rowBottom: null, stageTop: null };
  const rowRect = row.getBoundingClientRect();
  return {
    row: true,
    // Both measured in the same viewport frame, so a caller can compare
    // them directly to check the row sits above the leader image, not
    // overlaid on it (`.popover-navigation-row` is its own block above
    // `.popover-leader-stage`, core.js openPopover).
    rowBottom: rowRect.bottom,
    stageTop: stage ? stage.getBoundingClientRect().top : null,
    cards: [...row.children].map((card) => {
      const r = card.getBoundingClientRect();
      const img = card.querySelector("img");
      const badge = card.querySelector(".vcard-badge");
      return {
        cx: ((r.left + r.width / 2 - rowRect.left) / rowRect.width) * 100,
        flipped: card.classList.contains("flipped"),
        back: card.classList.contains("nav-card-back"),
        // The raw attribute, as TOKEN_JS reads it above.
        image: img ? img.getAttribute("src") : null,
        badge: badge ? badge.textContent : null,
      };
    }),
  };
}"""

# A pixel slack for comparing two independently measured
# getBoundingClientRect() edges (row bottom vs. stage top) in the same
# frame -- subpixel layout rounding only, not TOLERANCE's percent-of-stage
# slack above (a different, much coarser unit).
ROW_ABOVE_STAGE_SLACK = 1.0


def _x_in_span(box: list[float], cx: float) -> bool:
    left, _top, width, _height = box
    return left - TOLERANCE <= cx <= left + width + TOLERANCE


def _set_navigation(page, seat: int, *, played: list[str], remaining: int, hidden):
    """Edit Y'rkoon's own Navigation state on `seat` and open its popover
    (the view is the render's only input, as `_set_leader_and_open` uses
    it). `hidden` is the owner's own `view.private.navigation_slots`.

    Always resets `state.view.private` to a one-time-saved baseline first,
    then layers `navigation_slots` on top of it only when `hidden` is not
    `None` -- never to a bare `null`: a real non-owner's own `view.private`
    (hand, intrigue_cards, ...) is always present, for the *viewer's own*
    seat (`view.player`, this fixed game's own seat 0), and simply never
    carries `navigation_slots` for a leader some other seat holds
    (`core/observation.py`) -- the untouched baseline already is exactly
    that shape, for whichever seat Y'rkoon is NOT placed at this call
    (`navigation_geometry` below places him at seat 0 for the owner case,
    seat 1 for the non-owner one, both against the same seat-0 viewer).
    Resetting from the saved baseline on every call (not just when
    `hidden is None`) also clears whatever an earlier owner-case call left
    on it, so a later non-owner call is never checking stale leftover
    `navigation_slots` the `owner` gate merely happens to ignore
    (`leaderNavigationRow`, core.js)."""

    page.evaluate(
        """(args) => {
          const [seat, played, remaining, hidden] = args;
          const player = state.view.players[seat];
          player.leader_id = "steersman_y_rkoon";
          player.leader_face_id = null;
          player.navigation_played = played;
          player.navigation_remaining = remaining;
          window.__navPrivateBase = window.__navPrivateBase
            || JSON.parse(JSON.stringify(state.view.private));
          state.view.private = hidden === null
            ? JSON.parse(JSON.stringify(window.__navPrivateBase))
            : Object.assign({}, window.__navPrivateBase, { navigation_slots: hidden });
          render();
        }""",
        [seat, played, remaining, hidden],
    )
    page.click(f'.seat[data-seat="{seat}"] .leader-name')
    page.wait_for_function(
        "() => { const img = document.querySelector("
        "'#card-popover .popover-leader-stage img');"
        " return Boolean(img) && img.complete && img.naturalWidth > 0; }"
    )


def navigation_geometry(page, lang: str) -> None:
    """Every 0-4 played/remaining combination (played + remaining <= 4, the
    four printed slots), for both an owner's view and a non-owner's. Run
    once (English): the geometry and owner/non-owner logic do not depend on
    language, so exhausting all 15 combinations twice would only repeat the
    same proof; `navigation_geometry_language` below checks the image
    switches language instead, on a couple of representative combinations,
    the way `feyd_geometry`/`chani_geometry` do per space.

    The owner case places Y'rkoon at seat 0, this fixed game's own viewing
    seat (`view.player`); the non-owner case places him at seat 1 instead,
    against the very same seat-0 viewer -- the real shape a non-owner's
    view actually has (`_set_navigation`'s own docstring), not a `view.
    private` forced to `null`."""

    print(f"[6] Steersman Y'rkoon ({lang}): every played/remaining combination")
    catalog = page.evaluate("state.catalog")
    boxes = catalog["leaders"]["steersman_y_rkoon"]["layout"]["navigation_slots"]
    check.ok(len(boxes) == 4, "four printed Navigation slots", len(boxes))

    for played_count in range(5):
        for remaining_count in range(5 - played_count):
            played = [
                f"intrigue:navigation_card_{i + 1}:0" for i in range(played_count)
            ]
            hidden = [
                f"intrigue:navigation_card_{played_count + i + 1}:0"
                for i in range(remaining_count)
            ]
            total = played_count + remaining_count
            what = f"{played_count} played, {remaining_count} remaining ({lang})"

            for owner, hidden_arg, label, seat in (
                (True, hidden, "owner", 0),
                (False, None, "non-owner", 1),
            ):
                _set_navigation(
                    page,
                    seat,
                    played=played,
                    remaining=remaining_count,
                    hidden=hidden_arg,
                )
                shown = page.evaluate(NAVIGATION_JS)
                if total == 0:
                    check.ok(
                        not shown["row"], f"{what}: {label}: no row at all (0+0)", shown
                    )
                    continue
                check.ok(
                    shown["row"] and len(shown["cards"]) == total,
                    f"{what}: {label}: {total} card(s) drawn, none beyond "
                    "played + remaining",
                    shown,
                )
                check.ok(
                    shown["stageTop"] is not None
                    and shown["rowBottom"] <= shown["stageTop"] + ROW_ABOVE_STAGE_SLACK,
                    f"{what}: {label}: the row sits above the leader image "
                    "(row bottom <= stage top), not overlaid on it",
                    (shown["rowBottom"], shown["stageTop"]),
                )
                for index, card in enumerate(shown["cards"][:total]):
                    box = boxes[index]
                    check.ok(
                        _x_in_span(box, card["cx"]),
                        f"{what}: {label}: slot {index + 1} centred in its printed "
                        "x-span",
                        (box, card),
                    )
                    if index < played_count:
                        check.ok(
                            not card["flipped"] and not card["back"] and card["image"],
                            f"{what}: {label}: slot {index + 1} (played) shows its "
                            "face, for every viewer",
                            card,
                        )
                    elif owner:
                        check.ok(
                            card["flipped"]
                            and not card["back"]
                            and card["image"]
                            and card["badge"],
                            f"{what}: owner: slot {index + 1} (unplayed) shows the "
                            "owner's own face, muted, with a face-down badge",
                            card,
                        )
                    else:
                        check.ok(
                            card["back"] and not card["flipped"] and not card["image"],
                            f"{what}: non-owner: slot {index + 1} (unplayed) is a "
                            "plain placeholder with no identity",
                            card,
                        )


def navigation_geometry_language(page, lang: str) -> None:
    print(f"[7] Steersman Y'rkoon ({lang}): the unplayed cards' own {lang} image")
    played = ["intrigue:navigation_card_1:0", "intrigue:navigation_card_2:0"]
    hidden = ["intrigue:navigation_card_3:0", "intrigue:navigation_card_4:0"]
    _set_navigation(page, 0, played=played, remaining=2, hidden=hidden)
    shown = page.evaluate(NAVIGATION_JS)
    check.ok(
        shown["row"] and len(shown["cards"]) == 4, f"{lang}: four cards drawn", shown
    )
    for index, card in enumerate(shown["cards"]):
        check.ok(
            _is_language_image(card["image"], lang),
            f"{lang}: slot {index + 1}'s image is the {lang} file",
            card["image"],
        )


NAV_STRIP_JS = """(text) => {
  const dash = text.indexOf(" — ");
  const stripped = dash === -1 ? text : text.slice(dash + 3);
  const box = document.createElement("span");
  box.appendChild(iconize(stripped));
  for (const n of box.querySelectorAll(".amount")) n.replaceWith(n.title);
  for (const n of box.querySelectorAll("img")) n.replaceWith(n.alt);
  return box.textContent;
}"""

LOG_NAVIGATION_LINE_JS = """(payload) => {
  const box = document.createElement("span");
  box.appendChild(logEventLine({ kind: "navigation_card_played", payload }));
  for (const n of box.querySelectorAll(".amount")) n.replaceWith(n.title);
  for (const n of box.querySelectorAll("img")) n.replaceWith(n.alt);
  return box.textContent;
}"""


def navigation_option_wording(page) -> None:
    """ITEM 8b's twin for `play_navigation` (describeAction, core.js):
    unlike `play_intrigue`, this action carries only "option", no card_id
    (`rules/navigation.py` `legal_navigation_play_actions`), so
    `intrigue_options.py`'s technique (an edited action, not a real
    decision -- reaching a live multi-option Navigation decision needs a
    real Y'rkoon game and an Influence-2 trigger, well past what a seed
    search alone can promise) is used with a synthetic action rather than a
    real one."""

    print("[8] play_navigation rows name the card and its option, not a bare index")
    catalog = page.evaluate("state.catalog")
    entry = catalog["intrigue"]["navigation_card_1"]
    check.ok(
        len(entry["text"]) > 1,
        "navigation_card_1 offers more than one option (the catalog's own "
        "data, not this script's)",
        entry["text"],
    )

    print("  the live row: the card is the front of view.private.navigation_slots")
    page.evaluate(
        """() => {
          state.view.private = state.view.private || {};
          state.view.private.navigation_slots = ["intrigue:navigation_card_1:0"];
        }"""
    )
    for option in range(len(entry["text"])):
        action = {
            "action_id": "play_navigation",
            "arguments": {"option": option},
            "events": [],
        }
        shown = page.evaluate("(a) => describeActionText(a)", action)
        check.ok(
            "선택지:" not in shown and "Option:" not in shown,
            f"live row, option {option}: not a bare index",
            shown,
        )
        check.ok(
            entry["name"] in shown, f"live row, option {option}: names the card", shown
        )
        expected = page.evaluate(NAV_STRIP_JS, entry["text"][option])
        check.ok(
            shown.endswith(expected),
            f"live row, option {option}: ends with its printed line (timing "
            "prefix stripped, iconized)",
            (shown, expected),
        )

    print("  a logged step: the card is the step's own navigation_card_played event")
    page.evaluate("() => { state.view.private = null; }")
    action = {
        "action_id": "play_navigation",
        "arguments": {"option": 1},
        "events": [
            {
                "kind": "navigation_card_played",
                "payload": {
                    "card_id": "intrigue:navigation_card_1:0",
                    "faction": "emperor",
                    "option": 1,
                    "player": 0,
                    "slot": 2,
                },
            }
        ],
    }
    shown = page.evaluate("(a) => describeActionText(a)", action)
    check.ok(
        entry["name"] in shown and "선택지:" not in shown and "Option:" not in shown,
        "logged step: names the card from its own event, with view.private "
        "cleared (a spectator's page has none)",
        shown,
    )

    print("  neither resolves: the old fallback")
    action = {"action_id": "play_navigation", "arguments": {"option": 0}, "events": []}
    shown = page.evaluate("(a) => describeActionText(a)", action)
    check.ok(
        "선택지:" in shown or "Option:" in shown,
        "no card resolves (view.private cleared, no matching event): falls "
        "back to the plain numeric label",
        shown,
    )

    print(
        "  a review label (type: 'action', no events): never borrows the "
        "live view's own slot"
    )
    # Blocker repro (reviewer, 2026-09-25): a replay-review label
    # (server/sessions.py _review_step_label) carries type: "action" and no
    # "events" at all -- exactly like this action, deliberately built to
    # match its shape rather than a live legal action's (which carries no
    # "type" key, _serialize_action). By the time a review label is shown,
    # state.view is the view AFTER the step, so a live navigation_slots
    # fallback here would read the NEXT slot's own card, not the one this
    # step actually played, and print its name as if it were. Setting
    # navigation_slots here to a real, resolvable card (not just an absent
    # one, as "neither resolves" above already covers) is what makes this
    # check catch the bug: the old, ungated code found this card and named
    # it; the fix must fall back to the bare option index instead, the same
    # as when nothing resolves at all.
    page.evaluate(
        """() => {
          state.view.private = state.view.private || {};
          state.view.private.navigation_slots = ["intrigue:navigation_card_1:0"];
        }"""
    )
    action = {
        "type": "action",
        "actor": 0,
        "action_id": "play_navigation",
        "arguments": {"option": 0},
    }
    shown = page.evaluate("(a) => describeActionText(a)", action)
    check.ok(
        "선택지: 0" in shown or "Option: 0" in shown,
        "a review label falls back to the plain bare-index label even with "
        "a resolvable card sitting on view.private.navigation_slots",
        shown,
    )
    check.ok(
        entry["name"] not in shown,
        f"and never prints that live slot's own card name ({entry['name']!r})",
        shown,
    )

    print("  the log line under it (panels.js logEventPayload) skips the option too")
    log_line = page.evaluate(
        LOG_NAVIGATION_LINE_JS,
        {
            "card_id": "intrigue:navigation_card_1:0",
            "faction": "emperor",
            "option": 1,
            "player": 0,
            "slot": 2,
        },
    )
    check.ok(
        "선택지:" not in log_line and "Option:" not in log_line,
        "the log line a played row would draw agrees, like intrigue_played",
        log_line,
    )
    # Restore, rather than leave view.private cleared for whatever the
    # script checks next (renderPrivate(), panels.js, tolerates null, but
    # there is no reason to leave the private-hand panel hidden past this
    # function's own checks).
    page.evaluate(
        """() => {
          if (window.__navPrivateBase) {
            state.view.private = JSON.parse(JSON.stringify(window.__navPrivateBase));
            render();
          }
        }"""
    )


def _without_catalog_images(page, refs: list[tuple[str, str]], body) -> None:
    """Runs `body()` with each `(catalog group, id)` entry's image and
    image_ko nulled out -- e.g. `("leaders", "chani")`, or, for Kota's tile
    and Shaddam's contracts (catalog entries of their own, not the
    leader's, `core.js` `lookup`), `("tech", "navigation_chamber")` /
    `("contracts", "sardaukar_i")` -- then restores them. `no_image_fallback`
    uses this once per leader it covers."""

    saved = page.evaluate(
        "(refs) => refs.map(([group, id]) => ({"
        " image: state.catalog[group][id].image,"
        " image_ko: state.catalog[group][id].image_ko }))",
        refs,
    )
    page.evaluate(
        "(refs) => { for (const [group, id] of refs) {"
        " state.catalog[group][id].image = null;"
        " state.catalog[group][id].image_ko = null; } }",
        refs,
    )
    try:
        body()
    finally:
        page.evaluate(
            "(a) => { const [refs, saved] = a;"
            " refs.forEach(([group, id], i) => {"
            " state.catalog[group][id].image = saved[i].image;"
            " if (saved[i].image_ko) state.catalog[group][id].image_ko = saved[i].image_ko; }); }",
            [refs, saved],
        )


def _popover_stage_and_last_line(page) -> dict:
    # The last `.popover-line` (`termLine`, core.js), not the popover's own
    # last DOM child: Kota's and Shaddam's fallback rows
    # (`leaderSecretProjectBox`/`leaderSardaukarRow`) now draw *after* the
    # text lines even with no card image (STEP L3 fix review, 2026-09-25),
    # so the last child is one of those for those two leaders, not the
    # wording line this checks.
    return page.evaluate(
        """() => {
          const pop = document.getElementById("card-popover");
          const lines = pop.querySelectorAll(".popover-line");
          const last = lines[lines.length - 1];
          return {
            stage: Boolean(pop.querySelector(".popover-leader-stage")),
            lastText: last ? last.textContent.trim() : null,
          };
        }"""
    )


def no_image_fallback(page) -> None:
    """Run while the page is in English: the expected fallback wording is
    each leader's own UI_TEXT English text (`panels.tactics_space`, the new
    `panels.navigation_progress`, and `panels.secret_project`, reused from
    the seat status flag it used to carry before STEP L3). `kota` and
    `shaddam` also check that Kota's tile and Shaddam's two set-aside
    contracts still draw *something* below the fallback text line even
    with no card image loaded at all -- a fix review finding, 2026-09-25:
    `leaderSecretProjectBox`/`leaderSardaukarRow` were only appended in the
    `image && seatState` branch of `openPopover`, so without any image
    Shaddam's contracts appeared nowhere and Kota's owner lost the tile's
    own name (`visualCard`'s no-image fallback is a named textcard, the
    same one the old private-zone copy used to show)."""

    print("[3] without a card image: a text line, not a stage")

    def chani() -> None:
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
        shown = _popover_stage_and_last_line(page)
        check.ok(not shown["stage"], "chani: no stage without a card image", shown)
        check.ok(
            shown["lastText"] == "Tactics space 5",
            "chani: the fallback line names the printed space",
            shown["lastText"],
        )

    def yrkoon() -> None:
        page.evaluate(
            """(seat) => {
              const player = state.view.players[seat];
              player.leader_id = "steersman_y_rkoon";
              player.leader_face_id = null;
              player.navigation_played = ["intrigue:navigation_card_1:0"];
              player.navigation_remaining = 2;
              render();
            }""",
            0,
        )
        page.click('.seat[data-seat="0"] .leader-name')
        shown = _popover_stage_and_last_line(page)
        check.ok(not shown["stage"], "y'rkoon: no stage without a card image", shown)
        check.ok(
            shown["lastText"] == "1 Navigation card(s) played, 2 remaining",
            "y'rkoon: the fallback line names how many are played and remaining",
            shown["lastText"],
        )

    def kota() -> None:
        page.evaluate(
            """(seat) => {
              const player = state.view.players[seat];
              player.leader_id = "kota_odax_of_ix";
              player.leader_face_id = null;
              player.has_secret_project = true;
              if (state.view.private) {
                state.view.private.secret_project_tech_id = "navigation_chamber";
              }
              render();
            }""",
            0,
        )
        page.click('.seat[data-seat="0"] .leader-name')
        shown = _popover_stage_and_last_line(page)
        check.ok(not shown["stage"], "kota: no stage without a card image", shown)
        check.ok(
            shown["lastText"] == "Secret Project (face-down Tech tile)",
            "kota: the fallback line says he holds a Secret Project",
            shown["lastText"],
        )
        tile_name = page.evaluate(
            "() => { const row = document.querySelector("
            "'#card-popover .popover-secret-project-row');"
            " const name = row ? row.querySelector('.vcard-name') : null;"
            " return name ? name.textContent.trim() : null; }"
        )
        check.ok(
            bool(tile_name) and "navigation" in tile_name.lower(),
            "kota: the owner's tile still names itself (a textcard) below the fallback line",
            tile_name,
        )

    def shaddam() -> None:
        page.evaluate(
            """(seat) => {
              state.summary.choam_module = true;
              state.view.sardaukar_contract_ids = %s;
              const player = state.view.players[seat];
              player.leader_id = "shaddam_corrino_iv";
              player.leader_face_id = null;
              render();
            }"""
            % json.dumps(SARDAUKAR_CONTRACT_IDS),
            0,
        )
        page.click('.seat[data-seat="0"] .leader-name')
        cards = page.evaluate(
            "() => [...document.querySelectorAll("
            "'#card-popover .popover-sardaukar-row .vcard-name')]"
            ".map((n) => n.textContent.trim())"
        )
        check.ok(
            len(cards) == 2 and all(cards),
            "shaddam: both set-aside contracts still name themselves (textcards)"
            " below the fallback line",
            cards,
        )

    for leader_id, extra_refs, body in (
        ("chani", [], chani),
        ("steersman_y_rkoon", [], yrkoon),
        ("kota_odax_of_ix", [("tech", "navigation_chamber")], kota),
        (
            "shaddam_corrino_iv",
            [("contracts", "sardaukar_i"), ("contracts", "sardaukar_ii")],
            shaddam,
        ),
    ):
        _without_catalog_images(page, [("leaders", leader_id), *extra_refs], body)


def jessica_flip(page) -> None:
    """Run while the page is in English (Reverend Mother Jessica has no
    Korean art, so her English file is what any
    language shows; testing this while English keeps the check unambiguous
    -- it is not exercising the Korean-art gap, only the stage wrapper)."""

    print("[4] Lady Jessica: the flipped face's own picture in the popover")
    _set_leader_and_open(page, 0, "lady_jessica", face_id="reverend_mother_jessica")
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


# ---------- STEP L3: Kota Odax's tile and Shaddam's set-aside contracts ----------

KOTA_JS = """() => {
  const row = document.querySelector("#card-popover .popover-secret-project-row");
  if (!row) return { row: false, flipped: false, back: false, image: null, badge: null };
  const card = row.firstElementChild;
  const img = card ? card.querySelector("img") : null;
  const badge = card ? card.querySelector(".vcard-badge") : null;
  return {
    row: true,
    flipped: Boolean(card && card.classList.contains("flipped")),
    back: Boolean(card && card.classList.contains("tile-back")),
    // The raw attribute, as TOKEN_JS reads it above.
    image: img ? img.getAttribute("src") : null,
    badge: badge ? badge.textContent : null,
  };
}"""


def _set_kota(
    page, seat: int, *, has_secret_project: bool, tech_id: str | None
) -> None:
    """Edits Kota's own state on `seat` and opens its popover (the view is
    the render's only input, `_set_leader_and_open`'s technique). `tech_id`
    is the owner's own `view.private.secret_project_tech_id`; `None` keeps
    seat 0's own real, untouched `view.private` -- the shape a non-owner's
    view actually has for a leader some other seat holds
    (`_set_navigation`'s docstring covers the same technique for Y'rkoon)."""

    page.evaluate(
        """(args) => {
          const [seat, hasSecretProject, techId] = args;
          const player = state.view.players[seat];
          player.leader_id = "kota_odax_of_ix";
          player.leader_face_id = null;
          player.has_secret_project = hasSecretProject;
          window.__kotaPrivateBase = window.__kotaPrivateBase
            || JSON.parse(JSON.stringify(state.view.private));
          state.view.private = techId === null
            ? JSON.parse(JSON.stringify(window.__kotaPrivateBase))
            : Object.assign({}, window.__kotaPrivateBase, { secret_project_tech_id: techId });
          render();
        }""",
        [seat, has_secret_project, tech_id],
    )
    page.click(f'.seat[data-seat="{seat}"] .leader-name')
    page.wait_for_function(
        "() => { const img = document.querySelector("
        "'#card-popover .popover-leader-stage img');"
        " return Boolean(img) && img.complete && img.naturalWidth > 0; }"
    )


def kota_secret_project(page, lang: str) -> None:
    """Kota Odax of Ix's kept Secret Project tile [Bloodlines p. 6]: below
    the leader image, the owner's own muted face with the same "Face down"
    badge a face-down Navigation slot uses (`leaderNavigationRow`), a
    non-owner's identity-free `.tile-back` placeholder (no back art exists
    for a Tech tile either), and nothing at all once
    `has_secret_project` turns false (the tile acquired,
    `rules/tech.py` `_take_tile`). Owner/non-owner mirrors
    `navigation_geometry`'s own seat-0-viewer technique: Kota at seat 0 is
    the owner case, at seat 1 (against the very same seat-0 viewer's real,
    untouched `view.private`) the non-owner case."""

    print(f"[9] Kota Odax of Ix ({lang}): the kept Secret Project tile")

    _set_kota(page, 0, has_secret_project=True, tech_id="navigation_chamber")
    shown = page.evaluate(KOTA_JS)
    check.ok(
        shown["row"]
        and shown["flipped"]
        and not shown["back"]
        and shown["image"]
        and shown["badge"],
        f"{lang}: owner: the tile's own face, muted, with a face-down badge",
        shown,
    )
    check.ok(
        _is_language_image(shown["image"], lang),
        f"{lang}: owner: the {lang} card image",
        shown["image"],
    )

    _set_kota(page, 1, has_secret_project=True, tech_id=None)
    shown = page.evaluate(KOTA_JS)
    check.ok(
        shown["row"] and shown["back"] and not shown["flipped"] and not shown["image"],
        f"{lang}: non-owner: a plain placeholder with no identity",
        shown,
    )

    _set_kota(page, 0, has_secret_project=False, tech_id=None)
    shown = page.evaluate(KOTA_JS)
    check.ok(not shown["row"], f"{lang}: nothing once the tile is acquired", shown)


SARDAUKAR_CONTRACT_IDS = ["contract:sardaukar_i", "contract:sardaukar_ii"]

SARDAUKAR_JS = """() => {
  const row = document.querySelector("#card-popover .popover-sardaukar-row");
  if (!row) return { row: false, cards: [] };
  return {
    row: true,
    cards: [...row.children].map((card) => {
      const img = card.querySelector("img");
      const badge = card.querySelector(".vcard-badge");
      return {
        flipped: card.classList.contains("flipped"),
        image: img ? img.getAttribute("src") : null,
        badge: badge ? badge.textContent : null,
      };
    }),
  };
}"""


def _has_sardaukar_strip(page) -> bool:
    return page.evaluate(
        """() => Boolean(
          document.querySelector('#market .strip[data-strip="Sardaukar contract"]')
        )"""
    )


def _set_shaddam(page, seat: int, *, sardaukar_contract_ids: list[str]) -> None:
    """Edits the game to seat Shaddam Corrino IV on `seat` with CHOAM on,
    `view.sardaukar_contract_ids` (a top-level, fully public field, not
    per-player, `core/observation.py`) set to the given list, and opens his
    popover."""

    page.evaluate(
        """(args) => {
          const [seat, ids] = args;
          state.summary.choam_module = true;
          state.view.sardaukar_contract_ids = ids;
          const player = state.view.players[seat];
          player.leader_id = "shaddam_corrino_iv";
          player.leader_face_id = null;
          render();
        }""",
        [seat, sardaukar_contract_ids],
    )
    page.click(f'.seat[data-seat="{seat}"] .leader-name')
    page.wait_for_function(
        "() => { const img = document.querySelector("
        "'#card-popover .popover-leader-stage img');"
        " return Boolean(img) && img.complete && img.naturalWidth > 0; }"
    )


def shaddam_sardaukar(page, lang: str) -> None:
    """Shaddam Corrino IV's two set-aside Sardaukar contracts [Main p. 17]
    [FAQ p. 3]: no strip in the shared market column any more, regardless
    of who (if anyone) holds them -- the old client drew one whenever
    `view.sardaukar_contract_ids.length` (`board.js` `renderMarket`) -- and
    his own leader popover draws them face up below his image instead,
    from that same public `view.sardaukar_contract_ids`, shrinking as an
    edited view removes one."""

    print(f"[10] Shaddam Corrino IV ({lang}): the set-aside Sardaukar contracts")

    _set_shaddam(page, 0, sardaukar_contract_ids=list(SARDAUKAR_CONTRACT_IDS))
    check.ok(
        not _has_sardaukar_strip(page),
        f"{lang}: no Sardaukar strip in the shared market column",
    )
    shown = page.evaluate(SARDAUKAR_JS)
    check.ok(
        shown["row"] and len(shown["cards"]) == 2,
        f"{lang}: both contracts drawn face up below his leader image",
        shown,
    )
    for card in shown["cards"]:
        check.ok(
            card["image"] and not card["flipped"] and card["badge"],
            f"{lang}: each contract shows its face, with the set-aside badge",
            card,
        )

    # He takes one: the list shrinks and the popover follows.
    _set_shaddam(page, 0, sardaukar_contract_ids=[SARDAUKAR_CONTRACT_IDS[1]])
    shown = page.evaluate(SARDAUKAR_JS)
    check.ok(
        shown["row"] and len(shown["cards"]) == 1,
        f"{lang}: one left once he has taken the other",
        shown,
    )

    # No strip in the market when he is absent either, even with the
    # contracts still carried on the public view (the field the old market
    # strip read unconditionally).
    page.evaluate(
        """(args) => {
          const [seat, ids] = args;
          state.view.sardaukar_contract_ids = ids;
          const player = state.view.players[seat];
          player.leader_id = "chani";
          player.leader_face_id = null;
          render();
        }""",
        [0, SARDAUKAR_CONTRACT_IDS],
    )
    check.ok(
        not _has_sardaukar_strip(page),
        f"{lang}: still no Sardaukar strip in the market with Shaddam absent",
    )


POPOVER_LOAD_JS = """(sel) => {
  const pop = document.getElementById("card-popover");
  const row = pop.querySelector(sel);
  const images = [...pop.querySelectorAll("img")];
  return {
    popBottom: pop.getBoundingClientRect().bottom,
    rowHeight: row ? row.getBoundingClientRect().height : null,
    rowBottom: row ? row.getBoundingClientRect().bottom : null,
    allLoaded: images.length > 0 && images.every((img) => img.complete && img.naturalWidth > 0),
    viewportH: window.innerHeight,
  };
}"""


def leader_popover_settles_within_viewport(page) -> None:
    """Regression (found screenshotting this step, 2026-09-25; not asked
    for, cheap to guard): a popover's own leader image carries no explicit
    CSS `aspect-ratio`, so before it loads the browser measures a too-short
    popover (`placePopover`, called synchronously) and misplaces it. Fixed
    by having `placePopover` rerun once every popover image finishes
    loading (a scratch A/B confirmed this reposition alone is what keeps a
    low popover from running off the viewport); `visualCard`'s own default
    `loading="lazy"` on Kota's tile / Shaddam's contracts is also forced
    eager (`eagerCard`, core.js) as a cheap guard against a mispositioned
    popover missing the browser's lazy-load threshold, though that same A/B
    found every image still loaded without it. Opens both popovers
    from the LAST seat -- low enough on this 1366x768 laptop viewport that
    the unfixed popover would run off the bottom -- with no
    `wait_for_function` first (the point is to catch it exactly as a
    viewer's first click would, before anything has had a chance to
    settle), and checks that once it does settle, the popover and its
    extra row both end up fully inside the viewport with every image
    actually loaded."""

    print("[12] the popover settles within the viewport with every image loaded")
    for leader_id, edit, row_selector in (
        (
            "shaddam_corrino_iv",
            """(seat) => {
              state.summary.choam_module = true;
              state.view.sardaukar_contract_ids =
                ["contract:sardaukar_i", "contract:sardaukar_ii"];
              const player = state.view.players[seat];
              player.leader_id = "shaddam_corrino_iv";
              player.leader_face_id = null;
              render();
            }""",
            ".popover-sardaukar-row",
        ),
        (
            "kota_odax_of_ix",
            """(seat) => {
              const player = state.view.players[seat];
              player.leader_id = "kota_odax_of_ix";
              player.leader_face_id = null;
              player.has_secret_project = true;
              render();
            }""",
            ".popover-secret-project-row",
        ),
    ):
        page.evaluate(edit, 3)
        page.click('.seat[data-seat="3"] .leader-name')
        page.wait_for_timeout(500)
        shown = page.evaluate(POPOVER_LOAD_JS, row_selector)
        check.ok(
            shown["allLoaded"],
            f"{leader_id}: every popover image finished loading",
            shown,
        )
        check.ok(
            shown["rowHeight"] is not None and shown["rowHeight"] > 20,
            f"{leader_id}: the extra row has its real height, not a stalled lazy load",
            shown,
        )
        check.ok(
            shown["popBottom"] <= shown["viewportH"] + 1
            and shown["rowBottom"] is not None
            and shown["rowBottom"] <= shown["viewportH"] + 1,
            f"{leader_id}: the settled popover and its extra row fit the viewport",
            shown,
        )


def popover_stays_closed_after_late_image(base: str, browser) -> None:
    """Regression (blocker in the STEP L3 fix review, 2026-09-25): a closed
    popover reopened on its own once a slow image it was still holding
    finished loading. `openPopover`'s `load`-triggered reposition (added
    for `leader_popover_settles_within_viewport` above) checked only
    `loadingImage.isConnected` before calling `placePopover`, which itself
    sets `pop.hidden = false` -- but `closePopover` only sets
    `pop.hidden = true`, it never clears the popover's content
    (`pop.textContent = ""` happens only at the top of the *next*
    `openPopover`), so a closed popover's own images stay connected and a
    late `load` event on one of them silently un-hid it, without the
    `hover` class, so it sat over the seat panel and board catching pointer
    events until the next click. Fixed by also checking `!pop.hidden` in
    that handler. This needs its own throttled, cold-cache context (CDP
    `Network.emulateNetworkConditions`, 1500ms latency, cache disabled) so
    the leader image is still loading at the moment the popover closes --
    the shared `page` every other check in this file runs on has long since
    cached every leader image by the time this would run. Covers both ways
    of closing a popover whose image has not loaded yet: moving the mouse
    off a hovered (not pinned) one, and pinning one then pressing Escape.
    Checks it is still hidden 4.5s later, long enough for the throttled
    image to finish loading."""

    print("[13] a closed popover stays closed once a late image finishes loading")
    for how in ("mouseleave", "escape"):
        context, page, rec = open_context(
            browser, f"leader-card-ghost-{how}", LAPTOP_VIEWPORT
        )
        _open_fixed_game(page, base, seed=0, bloodlines=True)
        cdp = context.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        cdp.send(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": 1500,
                "downloadThroughput": -1,
                "uploadThroughput": -1,
            },
        )
        seat = 2  # a heuristic seat, so its leader image is not yet cached
        if how == "mouseleave":
            page.hover(f'.seat[data-seat="{seat}"] .leader-name')
        else:
            page.click(f'.seat[data-seat="{seat}"] .leader-name')
        # A hovered popover's own HOVER_DELAY_MS (120ms) is not the only
        # cost here -- a fresh context's very first popover open runs
        # several hundred ms slower than every later one (a one-time
        # warm-up cost measured separately, unrelated to the network
        # throttling below), so this waits for the actual state instead of
        # guessing a fixed delay.
        page.wait_for_function("!document.getElementById('card-popover').hidden")
        opened = page.evaluate("!document.getElementById('card-popover').hidden")
        if how == "mouseleave":
            page.mouse.move(700, 5)
        else:
            page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        closed = page.evaluate("document.getElementById('card-popover').hidden")
        page.wait_for_timeout(4500)
        later = page.evaluate(
            "() => { const p = document.getElementById('card-popover');"
            " return { hidden: p.hidden, hover: p.classList.contains('hover') }; }"
        )
        check.ok(opened, f"{how}: the popover opened")
        check.ok(closed, f"{how}: it closed")
        check.ok(
            later["hidden"],
            f"{how}: it is still closed after the late image load, not reopened behind the pointer",
            later,
        )
        check.ok(not rec.js_errors, f"{how}: no JS errors", rec.js_errors[:3])
        context.close()


POPOVER_RECT_JS = """() => {
  const pop = document.getElementById("card-popover");
  const rect = pop.getBoundingClientRect();
  const image = pop.querySelector("img");
  return {
    hidden: pop.hidden, top: rect.top, left: rect.left, pinned: popoverPinned,
    text: pop.textContent, complete: image ? image.complete : null,
  };
}"""


def card_click_inside_leader_popover(page) -> None:
    """Regression (L3 review, 2026-09-25): a card drawn inside a pinned
    leader popover (Shaddam's Sardaukar contracts, Y'rkoon's Navigation
    cards) pins its own popover with itself as the anchor, and
    `openPopover` clears the old content -- that anchor with it -- before
    `placePopover` measures it. A detached anchor's all-zero rect threw
    the popover into the top-left corner. `placePopover` now leaves the
    popover where it was when its anchor has left the page."""

    print("[14] a card clicked inside a pinned leader popover opens in place")
    _set_shaddam(page, 0, sardaukar_contract_ids=list(SARDAUKAR_CONTRACT_IDS))
    before = page.evaluate(POPOVER_RECT_JS)
    page.click("#card-popover .popover-sardaukar-row .vcard >> nth=0")
    page.wait_for_timeout(300)
    after = page.evaluate(POPOVER_RECT_JS)
    name = page.evaluate("(id) => lookup(baseId(id)).name", SARDAUKAR_CONTRACT_IDS[0])
    check.ok(
        not after["hidden"] and name in after["text"],
        "the contract's own popover is showing",
        {"name": name, "text": after["text"][:80]},
    )
    check.ok(
        abs(after["left"] - before["left"]) < 2 and after["top"] > 20,
        "it stays where the leader popover was, not in the top-left corner",
        (before, after),
    )
    page.keyboard.press("Escape")


def pinned_popover_survives_rerender(base: str, browser) -> None:
    """Regression (L3 re-review, 2026-09-25): a pinned card popover whose
    image was still loading when a foreign update re-rendered the seat
    panel (the doorbell's `refresh(null, {foreign: true})`) jumped to the
    top-left corner once the image arrived: the load-time reposition
    measured the detached chip. On a throttled, cold-cache link, pins a
    seat-detail card chip while such a refresh is already in flight and
    checks the popover has not moved 6 s later."""

    print("[15] a pinned popover stays put when the table re-renders under it")
    game = _api_post(
        base,
        "/games",
        {"seats": ["human", "heuristic", "heuristic", "heuristic"], "game_seed": 0},
    )
    context, page, rec = open_context(
        browser, "leader-card-rerender", {"width": 1440, "height": 900}
    )
    page.goto(f"{base}/#game={game['game_id']}")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")
    card = page.evaluate(
        """() => {
          const shown = new Set([...document.querySelectorAll("img")].map((i) => i.src));
          for (const [id, entry] of Object.entries(state.catalog.cards || {})) {
            const image = entry && entryImage(entry);
            if (image && !shown.has(new URL(image, location.href).href)) return id;
          }
          return null;
        }"""
    )
    check.ok(card is not None, "a card whose picture is not on screen yet", card)
    page.evaluate(
        """(card) => {
          state.view.players[1].in_play = [card];
          expandedSeats = new Set([1]);
          render();
        }""",
        card,
    )
    name = page.evaluate("(id) => state.catalog.cards[id].name", card)
    chip = page.locator(
        '.seat[data-seat="1"] .seat-detail .tag.clickable', has_text=name
    ).first
    cdp = context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    cdp.send(
        "Network.emulateNetworkConditions",
        {
            "offline": False,
            "latency": 2500,
            "downloadThroughput": -1,
            "uploadThroughput": -1,
        },
    )
    page.evaluate("() => { refresh(null, { foreign: true }); }")
    page.wait_for_timeout(800)
    chip.click()
    first = page.evaluate(POPOVER_RECT_JS)
    page.wait_for_timeout(6000)
    later = page.evaluate(POPOVER_RECT_JS)
    check.ok(
        first["pinned"] and not first["hidden"],
        "the chip's popover is pinned open",
        first,
    )
    check.ok(later["complete"], "its image has loaded by now", later)
    check.ok(
        not later["hidden"] and later["left"] > 20 and later["top"] > 20,
        "it did not jump to the top-left corner",
        (first, later),
    )
    check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    context.close()


def ability_names_once(page) -> None:
    """The Bloodlines Leaders' ability texts already open with the ability's
    own name ("Tactician: Whenever…", Y'rkoon's Signet "Plot Course (no
    Signet Ring): …"); the popover used to print the name again in front
    ("Tactician: Tactician: …")."""

    print("[16] a leader popover names each ability once")
    for leader_id, repeats in (
        ("chani", ("Tactician: Tactician",)),
        ("kota_odax_of_ix", ("Secret Project: Secret Project",)),
        (
            "steersman_y_rkoon",
            ("Strange Form / Hungry for Spice: Strange Form", "Plot Course: Plot Course"),
        ),
    ):
        _set_leader_and_open(page, 0, leader_id)
        text = page.evaluate("document.getElementById('card-popover').textContent")
        for repeat in repeats:
            check.ok(repeat not in text, f"{leader_id}: no {repeat!r}", text[:160])
        page.keyboard.press("Escape")


def status_line_drops_leader_flags(page) -> None:
    """The seat panel's own folding status line (`panels.js` `renderSeats`)
    no longer repeats what the leader popover now draws: Chani's Tactics
    space, Y'rkoon's remaining Navigation count and Kota's Secret Project
    flag. Piter's Twisted deck count is unrelated leader state (Kota's own
    field cannot carry it) and must still show, so this is not simply "the
    status line is empty"."""

    print("[11] the seat status line drops the three flags the popover now carries")
    page.evaluate(
        """(seat) => {
          const player = state.view.players[seat];
          player.leader_id = "chani";
          player.leader_face_id = null;
          player.tactics_track_space = 4;
          player.navigation_remaining = 3;
          player.navigation_played = ["intrigue:navigation_card_1:0"];
          player.has_secret_project = true;
          player.twisted_deck_size = 2;
          expandedSeats = new Set([seat]);
          render();
        }""",
        0,
    )
    status = page.evaluate(
        """() => {
          const lines = [...document.querySelectorAll(
            '.seat[data-seat="0"] .seat-detail .cardline')];
          const status = lines.find(
            (line) => (line.querySelector("strong")?.textContent || "").trim() === "Status");
          return status ? status.textContent : null;
        }"""
    )
    check.ok(
        status is not None, "the status line still exists (Twisted deck stays)", status
    )
    check.ok(
        status and "Tactics space" not in status, "no more Tactics-space flag", status
    )
    check.ok(
        status and "Navigation" not in status,
        "no more Navigation-remaining flag",
        status,
    )
    check.ok(
        status and "Secret Project" not in status, "no more Secret-Project flag", status
    )
    check.ok(
        status and "Twisted Intrigue" in status,
        "Piter's Twisted-deck flag is unrelated leader state and stays",
        status,
    )
    # Leaves nothing behind for whatever the script checks next.
    page.evaluate("() => { expandedSeats = new Set(); }")


POPOVER_TEXT_JS = """() => {
  const pop = document.getElementById("card-popover");
  return {
    koLineCount: pop.querySelectorAll(".effect-text-ko").length,
    text: pop.textContent,
  };
}"""


def leader_popover_korean_text(page, lang: str) -> None:
    """Step K5 (2026-09-25): a Leader face with a Korean scan shows its
    transcribed Korean ability/Signet Ring name and text in the Korean UI --
    through the same `.effect-text-ko` wrapper every other generated-text
    field draws its Korean line in (`effectNode`, render.js), never the
    printed-card `.card-text` wrapper -- and the English UI is unchanged.
    Chani and Kota Odax of Ix, named by the controlling task: Chani's own
    ability/Signet text has no generated-text precedent to compare against
    (a Leader's prose is hand-transcribed in both languages, unlike a
    card's engine-derived line) and her Signet is the one face whose
    printed reward is known to disagree with the English/engine (two draw
    icons, not troops, leaders_reconcile.md finding 1); Kota's own ability
    and Signet use no `{agent_icon_...}` token at all -- his printed
    Signet Ring ("폐기") and ability exercise the ordinary case.

    Fix review (2026-09-25) adds Steersman Y'rkoon: his Korean
    `signet_text_ko` ("게임 시작: 운항 카드를 …") never opens with its own
    Korean Signet name "항로 결정", unlike the English "Plot Course (no
    Signet Ring): …", which opens with its own English name "Plot Course".
    `popoverNodes`'s signet branch used to decide the named-vs-unnamed
    template from the ENGLISH text alone (`opensWithName(entry.signet_text,
    signetEn)`), so it picked the unnamed template for both languages and
    the Korean name never showed at all -- this case's own name assertions
    below catch that regression; the earlier Chani/Kota cases only checked
    for text substrings, never names, so they missed it.

    Must fail on the pre-K5 client: `ability_text_ko`/`signet_text_ko` did
    not exist on the catalog, so `effectNode` always fell back to
    `iconize(en)` and no `.effect-text-ko` node was ever drawn in this
    popover; the Korean substrings checked below would not appear at all."""

    print(
        f"[18] Leader popover Korean text ({lang}): Chani, Kota Odax of Ix, "
        "Steersman Y'rkoon"
    )
    cases = (
        ("chani", "전술 토큰을", "원하는 만큼 후퇴", "Tactician", "retreat"),
        (
            "kota_odax_of_ix",
            "각각의 기술 타일 더미",
            "기술 타일 1개 폐기",
            "Secret Project",
            "Tech tile",
        ),
        (
            "steersman_y_rkoon",
            "스파이스를 갈구하다",
            "운항 카드를 잘 섞고",
            "Hungry for Spice",
            "Plot Course",
        ),
    )
    for leader_id, ability_ko, signet_ko, ability_en, signet_en in cases:
        _set_leader_and_open(page, 0, leader_id)
        shown = page.evaluate(POPOVER_TEXT_JS)
        if lang == "ko":
            check.ok(
                shown["koLineCount"] >= 2,
                f"{leader_id} (ko): at least two Korean-wrapped lines "
                "(ability and Signet)",
                shown,
            )
            check.ok(
                ability_ko in shown["text"],
                f"{leader_id} (ko): the transcribed ability text shows",
                shown["text"][:200],
            )
            check.ok(
                signet_ko in shown["text"],
                f"{leader_id} (ko): the transcribed Signet Ring text shows",
                shown["text"][:400],
            )
            if leader_id == "steersman_y_rkoon":
                # Blocker fix regression check: the Korean NAMES themselves
                # must show, not just the texts the two checks above
                # already cover. The ability's own two printed sub-names
                # ("기이한 모습:", "스파이스를 갈구하다:") already open
                # their own halves of ability_text_ko
                # (leaders_ko.py's own "editorial name: prefixes"
                # convention), so namedEffectLine correctly does not print
                # the combined editorial header "기이한 모습 / 스파이스를
                # 갈구하다" a second time in front of them — this was never
                # the bug, opensWithName already ran per-language there.
                # The Signet Ring name is the actual regression: Korean
                # signet_text_ko never opens with its own name, so it never
                # showed at all before this fix (docstring above).
                check.ok(
                    "기이한 모습:" in shown["text"]
                    and "스파이스를 갈구하다:" in shown["text"],
                    f"{leader_id} (ko): both printed ability sub-names open "
                    "their own halves of the ability text",
                    shown["text"][:200],
                )
                check.ok(
                    "항로 결정" in shown["text"],
                    f"{leader_id} (ko): the Korean Signet Ring name shows "
                    "(opensWithName decided against the Korean text/name, "
                    "not the English's)",
                    shown["text"][:400],
                )
        else:
            check.ok(
                shown["koLineCount"] == 0,
                f"{leader_id} (en): no Korean-wrapped line at all",
                shown,
            )
            check.ok(
                ability_ko not in shown["text"] and signet_ko not in shown["text"],
                f"{leader_id} (en): no Korean leaks into the English popover",
                shown["text"][:200],
            )
            check.ok(
                ability_en in shown["text"] and signet_en in shown["text"],
                f"{leader_id} (en): the English text is unchanged",
                shown["text"][:200],
            )
        page.keyboard.press("Escape")


STABAN_SIGNET_LINE_JS = """() => {
  const lines = [...document.querySelectorAll("#card-popover .popover-line")];
  const line = lines.find((l) => l.textContent.includes("놓은 곳에 따라"));
  return line ? line.innerText : null;
}"""


def leader_popover_line_breaks(page) -> None:
    """Blocker fix (2026-09-25 review): four Korean fields carry a literal
    "\\n" for a printed line/column break with no punctuation of its own
    (`display/leaders_ko.py`'s own convention: Staban's and Liet's case
    lists, Esmar's two columns, Steersman's two boxes) -- `phrase()`
    (render.js) emits it as a plain text node, so nothing but a CSS
    `white-space` rule turns it back into a visible line break; with none,
    the browser collapsed every one of those four lines into a single run
    (confirmed in the browser, review-k5/popovers_new.json and
    review-k5/shots/staban_tuek_ko.png). `.effect-text-ko { white-space:
    pre-line; }` (style.css) is the fix, checked here with `innerText`
    (which reflects CSS layout) rather than `textContent` (which does not
    and would pass even with the bug still present).

    Staban Tuek's own Signet Ring line ("보이지 않는 망") is the one this
    checks directly -- it is found by a substring unique to it ("놓은 곳에
    따라", printed with no punctuation before or after the break) among
    every `.popover-line` in the open popover, so this does not depend on
    it being any particular line's position."""

    print("[19] a printed Korean line/column break renders as a real line break")
    _set_leader_and_open(page, 0, "staban_tuek")
    line = page.evaluate(STABAN_SIGNET_LINE_JS)
    check.ok(
        bool(line) and "\n" in line,
        "staban_tuek (ko): the Signet Ring line's innerText keeps its "
        "printed line break, not collapsed into one run",
        line,
    )
    page.keyboard.press("Escape")


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


def _find_yrkoon_first_pick_seed(base: str, *, limit: int = 500) -> int | None:
    """A `game_seed` where the Leader draft's First Player is seat 1, so
    seat 0 picks first (``draft_pick_order(1, 4) == (0, 3, 2, 1)``,
    `rules/leader_draft.py`) and can take Steersman Y'rkoon before any
    other seat, human or heuristic, gets a turn -- checked by whether seat
    0's very first legal actions already offer him, one raw-HTTP
    `POST /games` + `GET .../seats/0/actions` per candidate seed (open
    mode: unlike `--remote`, `/actions` needs no seat token yet, so this
    finds the seed without ever claiming anything)."""

    for seed in range(limit):
        summary = _api_post(
            base,
            "/games",
            {
                "seats": ["human", "human", "heuristic", "heuristic"],
                "leader_draft": True,
                "bloodlines": True,
                "game_seed": seed,
            },
        )
        game_id = summary["game_id"]
        actions = _api_get(base, f"/games/{game_id}/seats/0/actions")
        offered = {
            action["arguments"].get("leader_id")
            for action in actions.get("actions", [])
            if action["action_id"] == "pick_leader"
        }
        if "steersman_y_rkoon" in offered:
            return seed
    return None


def _api_post_admin(base: str, path: str, body: dict, key: str) -> dict:
    request = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        # The admin cookie IS the key (`server/app.py` ADMIN_COOKIE, set
        # verbatim by /auth/admin), so this skips that round trip.
        headers={"Content-Type": "application/json", "Cookie": f"dune_admin={key}"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        result: dict = json.loads(response.read())
    return result


def _claim(page, base: str, game_id: str, name: str, seat: int) -> None:
    page.goto(f"{base}/#game={game_id}")
    page.wait_for_selector("#lobby-screen:not([hidden])")
    page.fill("#lobby-name", name)
    page.click(f"#lobby-seats li[data-seat='{seat}'] button")
    page.wait_for_selector("#game-screen:not([hidden])")


def _has_actions(page) -> bool:
    return bool(page.evaluate("Boolean(state.actions && state.actions.actions.length)"))


def _apply_first(page, action_id: str, *, leader_id: str | None = None) -> bool:
    actions = page.evaluate("state.actions.actions")
    matching = [a for a in actions if a["action_id"] == action_id]
    if leader_id is not None:
        wanted = next(
            (a for a in matching if a["arguments"].get("leader_id") == leader_id), None
        )
        matching = [wanted] if wanted else matching
    if not matching:
        return False
    page.evaluate(f"applyAction({matching[0]['index']})")
    return settled(page)


def _confirm_if_held(page) -> bool:
    """A Leader pick is its own "unit" (`server/turn_end.py`'s doc comment:
    "its share of a phase outside them (a Leader pick, ...)"), so the
    server holds it for this seat's "턴 종료" press
    (`state.summary.confirmation`) before the next picker's turn opens --
    the same held-turn mechanic `turn_end.py` drives with `confirmTurn()`
    for a non-last leader-draft pick. Y'rkoon's own four
    `place_navigation_card` picks do not: they share one unit (the decision
    owner stays seat 0 throughout, `server/sessions.py`
    `_unit_ended_locked`), so nothing holds between them."""

    if not page.evaluate(
        "Boolean(state.summary) && state.summary.confirmation === state.viewSeat"
    ):
        return False
    page.evaluate("confirmTurn()")
    return settled(page)


def _drive_to_navigation_setup(owner, other, *, timeout: float = 30.0) -> bool:
    """Alternately drive whichever page has its own pending actions or held
    turn end -- owner's (seat 0) Leader pick, then, once the draft reaches
    it, other's (seat 1) -- letting the auto-resolved heuristic seats (3,
    2, between them in `draft_pick_order(1, 4)`) pass through inside each
    confirm, until Y'rkoon's own Navigation setup (`place_navigation_card`,
    owner's again) has been driven all four times."""

    navigation_done = 0
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _confirm_if_held(owner) or _confirm_if_held(other):
            continue
        if _has_actions(owner):
            if _apply_first(owner, "place_navigation_card"):
                navigation_done += 1
                if navigation_done == 4:
                    return True
                continue
            if _apply_first(owner, "pick_leader", leader_id="steersman_y_rkoon"):
                continue
        if _has_actions(other) and _apply_first(other, "pick_leader"):
            continue
        time.sleep(0.1)
    return False


def live_yrkoon_navigation(browser) -> None:
    """(b)'s twin for Steersman Y'rkoon, on a `--remote` server: seat 0's
    own page must show its four unplayed Navigation slots' own faces
    (muted, badged), seat 1's page must show placeholders only, with no
    identity to be found -- and this must hold with two real,
    cookie-separated browser contexts against `--remote`, not merely two
    `viewSeat`s of one open-mode session, since only `--remote` gates the
    server's own `/view` response per seat token
    (`server/sessions.py._authorize_seat_locked`: "The admin key
    deliberately opens nothing here ... must not reach another seat's view
    through the API"), which an open server does not exercise at all."""

    print("[9] a real remote game: Steersman Y'rkoon's own popover, seat by seat")
    with server() as (search_base, _search_log):
        seed = _find_yrkoon_first_pick_seed(search_base)
    if not check.ok(seed is not None, "a seed lets seat 0 draft Y'rkoon first"):
        return

    with server("--remote", "--admin-key", YRKOON_ADMIN_KEY) as (base, server_log):
        try:
            summary = _api_post_admin(
                base,
                "/games",
                {
                    "seats": ["human", "human", "heuristic", "heuristic"],
                    "leader_draft": True,
                    "bloodlines": True,
                    "game_seed": seed,
                },
                YRKOON_ADMIN_KEY,
            )
            game_id = summary["game_id"]
            owner_ctx, owner, owner_rec = open_context(browser, "yrkoon-owner")
            other_ctx, other, other_rec = open_context(browser, "yrkoon-other")
            _claim(owner, base, game_id, "요르콘", 0)
            _claim(other, base, game_id, "동료", 1)

            if not check.ok(
                _drive_to_navigation_setup(owner, other),
                "the draft finishes (Y'rkoon to seat 0) and all four "
                "Navigation slots are placed",
            ):
                owner_ctx.close()
                other_ctx.close()
                return
            check.ok(
                owner.evaluate("state.view.players[0].leader_id")
                == "steersman_y_rkoon",
                "seat 0 really holds Steersman Y'rkoon",
            )

            hidden = owner.evaluate("state.view.private.navigation_slots")
            check.ok(
                isinstance(hidden, list) and len(hidden) == 4,
                "the owner's own private view carries all four slots",
                hidden,
            )

            owner.click('.seat[data-seat="0"] .leader-name')
            owner.wait_for_function(
                "() => { const img = document.querySelector("
                "'#card-popover .popover-leader-stage img');"
                " return Boolean(img) && img.complete && img.naturalWidth > 0; }"
            )
            shown_owner = owner.evaluate(NAVIGATION_JS)
            check.ok(
                shown_owner["row"] and len(shown_owner["cards"]) == 4,
                "owner's own page: four cards drawn",
                shown_owner,
            )
            check.ok(
                all(
                    card["flipped"] and not card["back"] and card["image"]
                    for card in shown_owner["cards"]
                ),
                "owner's own page: every slot shows its own face, muted "
                "(none played yet)",
                shown_owner,
            )

            other.click('.seat[data-seat="0"] .leader-name')
            other.wait_for_function(
                "() => { const img = document.querySelector("
                "'#card-popover .popover-leader-stage img');"
                " return Boolean(img) && img.complete && img.naturalWidth > 0; }"
            )
            shown_other = other.evaluate(NAVIGATION_JS)
            check.ok(
                shown_other["row"] and len(shown_other["cards"]) == 4,
                "the other seat's own page: four cards drawn too",
                shown_other,
            )
            check.ok(
                all(
                    card["back"] and not card["flipped"] and not card["image"]
                    for card in shown_other["cards"]
                ),
                "the other seat's page: every slot is a placeholder, no "
                "identity for any of them",
                shown_other,
            )
            other_private_slots = other.evaluate(
                "(state.view.private && state.view.private.navigation_slots) || []"
            )
            check.ok(
                other_private_slots == [],
                "the other seat's own state.view has no navigation_slots for Y'rkoon",
                other_private_slots,
            )

            check.ok(
                not owner_rec.js_errors and not other_rec.js_errors,
                "no JS exceptions (live Y'rkoon game)",
                owner_rec.js_errors[:5] + other_rec.js_errors[:5],
            )
            owner_ctx.close()
            other_ctx.close()
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors on the remote server (see {SERVER_LOG_COPY})",
        )


REVIEW_STATUS_JS = "() => document.getElementById('review-status').textContent"

LOG_HEAD_FOR_INDEX_JS = """(index) => {
  const marker = `#${index}`;
  const line = [...document.querySelectorAll('#action-log .turn-index')]
    .find((node) => node.textContent === marker);
  return line ? line.closest('.turn-line').querySelector('.turn-line-head').textContent
    : null;
}"""


def _open_all_ai_bloodlines_game(page, base: str, *, seed: int) -> None:
    """All four seats AI, Bloodlines on, Leader Draft at its own default
    (checked, `index.html` `#opt-leader-draft`) -- `set_rule_options(page,
    "bloodlines")` leaves only Bloodlines checked among `RULE_OPTIONS`
    (`common.py`) and never touches `#opt-leader-draft`. A game of AI seats
    only is played to the end by the server as it is created
    (`server/sessions.py`, `spectate.py`'s own doc comment), so the client
    opens it straight into replay review."""

    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(f"#seat-selects select[data-seat='{seat}']", "heuristic")
    set_rule_options(page, "bloodlines")
    page.fill("#opt-seed", str(seed))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.review !== null && state.view !== null")


def review_label_repro(base, browser) -> None:
    """The reviewer's own blocker repro, reproduced exactly (2026-09-25): a
    real replay-review label must never borrow the live view's own
    `navigation_slots` -- `describeAction`'s `play_navigation` branch,
    core.js, must gate that fallback on the live action's own missing
    "type" key (`_serialize_action`, sessions.py), not merely on whether an
    `navigation_card_played` event resolved a card, since a replay-review
    label (`_review_step_label`) carries `type: "action"` and no `events`
    either.

    `game_seed=2` (all-heuristic, Bloodlines + Leader Draft) deterministically
    drafts Steersman Y'rkoon to seat 3 and, at log step 120 (`play_navigation`,
    option 0), resolves `navigation_card_9` into slot 1 -- but by review
    cursor 121 (the view after that step), the card has already left
    `view.private.navigation_slots` for the next one
    (`navigation_card_1` at its front by then). Confirmed directly over raw
    HTTP against this exact server and seed before writing this check (no
    seed search needed here, unlike `live_feyd_token`/
    `_find_yrkoon_first_pick_seed`): `GET /games/{id}/review?seat=3`'s
    `log[120]["events"][0]["payload"]` is `{"card_id":
    "intrigue:navigation_card_9:0", "option": 0, "player": 3, "slot": 1,
    ...}`, and `GET /games/{id}/review/121?seat=3`'s own `view["private"][
    "navigation_slots"][0]` is `"intrigue:navigation_card_1:0"`.

    `enterReview(3, {cursor: 121})` is called directly (a page-context
    global, review.js) rather than driven through the seat/slider controls:
    it opens review at exactly that seat and cursor in one step, with no
    risk of playback (already running, all-AI games open playing) racing a
    multi-step UI drive past the cursor this check needs."""

    print(
        "[10] a real review label: the fallback never borrows the live view's own slot"
    )
    context, page, rec = open_context(browser, "review-repro", LAPTOP_VIEWPORT)
    _open_all_ai_bloodlines_game(page, base, seed=2)
    # Korean is the page's own default (lang.py); English is not assumed,
    # it is switched to explicitly, as main()'s own primary context does.
    switch_language(page, "en")

    # The game opens playing from seat 0, cursor 0 (before the draft even
    # runs) -- state.view.players[3].leader_id is only meaningful once
    # enterReview has actually moved to seat 3's own cursor 121.
    page.evaluate("async () => { await enterReview(3, { cursor: 121 }); }")
    page.wait_for_function("state.review && state.review.cursor === 121")
    check.ok(
        page.evaluate("state.view.players[3].leader_id") == "steersman_y_rkoon",
        "seat 3 really drafted Steersman Y'rkoon at this seed",
        page.evaluate("state.view.players[3].leader_id"),
    )
    catalog = page.evaluate("state.catalog")
    played_name = catalog["intrigue"]["navigation_card_9"]["name"]
    front_name = catalog["intrigue"]["navigation_card_1"]["name"]

    status = page.evaluate(REVIEW_STATUS_JS)
    check.ok(
        "Option: 0" in status,
        "en: the review label falls back to the plain option index",
        status,
    )
    check.ok(
        played_name not in status and front_name not in status,
        "en: and names neither the card that step actually played nor the "
        "next slot's own card",
        status,
    )

    log_head = page.evaluate(LOG_HEAD_FOR_INDEX_JS, 120)
    check.ok(
        log_head is not None and played_name in log_head,
        "en: the turn log's own line for the very same step still "
        "correctly names the card that was played (it carries its own "
        "navigation_card_played event)",
        log_head,
    )

    switch_language(page, "ko")
    page.wait_for_function("state.review && state.review.cursor === 121")
    status_ko = page.evaluate(REVIEW_STATUS_JS)
    check.ok(
        "선택지: 0" in status_ko,
        "ko: the review label falls back to the plain option index too",
        status_ko,
    )

    check.ok(
        not rec.js_errors, "no JS exceptions (review label repro)", rec.js_errors[:5]
    )
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
            navigation_geometry(page, "en")
            navigation_geometry_language(page, "en")
            navigation_option_wording(page)
            no_image_fallback(page)
            jessica_flip(page)
            kota_secret_project(page, "en")
            shaddam_sardaukar(page, "en")
            leader_popover_settles_within_viewport(page)
            card_click_inside_leader_popover(page)
            ability_names_once(page)
            status_line_drops_leader_flags(page)
            leader_popover_korean_text(page, "en")

            switch_language(page, "ko")
            feyd_geometry(page, "ko")
            chani_geometry(page, "ko")
            navigation_geometry_language(page, "ko")
            kota_secret_project(page, "ko")
            shaddam_sardaukar(page, "ko")
            leader_popover_korean_text(page, "ko")
            leader_popover_line_breaks(page)

            check.ok(not rec.js_errors, "no JS exceptions", rec.js_errors[:5])
            context.close()

            live_feyd_token(base, browser)
            review_label_repro(base, browser)
            popover_stays_closed_after_late_image(base, browser)
            pinned_popover_survives_rerender(base, browser)
        finally:
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
        # A separate --remote server (its own two-context claim/draft
        # dance), so it runs after the main local server above is done with.
        live_yrkoon_navigation(browser)
    print(json.dumps({"passed": check.passed, "failed": check.failed}))
    check.finish()


if __name__ == "__main__":
    main()
