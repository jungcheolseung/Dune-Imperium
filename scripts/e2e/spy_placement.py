"""Board Spy destinations: live placement, restrictions and occupied posts.

Destinations must match the server's flat action list. Recall and Infiltrate
references cannot turn a post into a placement button. Render-only fixtures
exercise each placement source and Deep Cover, without changing rules.
"""

from __future__ import annotations

import os
import tempfile

from common import Check, chrome, open_context, server
from open_mode import create_game, settled
from turn_controls import play_until

check = Check()
SHOTS = os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(prefix="dune-e2e-spy-")
PLACEMENTS = [
    "place_acquisition_spy",
    "place_agent_card_spy",
    "place_combat_reward_spy",
    "place_contract_spy",
    "place_intrigue_spy",
    "place_leader_spy",
    "place_reveal_spy",
    "place_spy_on_space",
    "place_tech_spy",
    "resolve_espionage_place_spy",
    "move_spy",
]
RINGS = "[...document.querySelectorAll('.spy-post-hotspot')].map((n) => n.dataset.post)"


def live(page, base: str) -> None:
    create_game(page, base, humans=(0, 1, 2, 3))
    reached = play_until(
        page,
        "state.actions.actions.some((a) => "
        "a.action_id === 'resolve_espionage_place_spy')",
        """(() => {
          const rows = state.actions.actions;
          return (rows.find((a) => a.action_id === 'agent_turn'
            && a.arguments.space_id === 'espionage') || rows[0]).index;
        })()""",
        limit=400,
    )
    check.ok(reached, "a real Espionage turn offers Spy placement")
    assert reached
    expected = page.evaluate("""state.actions.actions
      .filter((a) => a.action_id === 'resolve_espionage_place_spy')
      .map((a) => a.arguments.post_id)""")
    for lang, width in (("ko", 1600), ("en", 1366)):
        page.set_viewport_size({"width": width, "height": 900})
        page.evaluate("setLanguage", lang)
        check.ok(
            sorted(page.evaluate(RINGS)) == sorted(expected),
            f"{lang}: exactly the offered posts glow",
        )
        geometry = page.evaluate("""() => {
          const board = document.querySelector('.board-stage').getBoundingClientRect();
          return [...document.querySelectorAll('.spy-post-hotspot')].every((node) => {
            const r = node.getBoundingClientRect();
            const p = state.catalog.posts[node.dataset.post];
            const x = (r.x + r.width / 2 - board.x) / board.width * 100;
            const y = (r.y + r.height / 2 - board.y) / board.height * 100;
            return Math.abs(x - p[0]) < .05 && Math.abs(y - p[1]) < .05
              && getComputedStyle(node).borderStyle === 'solid'
              && node.getAttribute('aria-label') === postName(node.dataset.post);
          });
        }""")
        check.ok(
            geometry, f"{lang}: rings sit on the printed discs and name their spaces"
        )
        page.locator(".board-stage").screenshot(path=f"{SHOTS}/spy_{lang}.png")

    chosen = page.evaluate(
        "state.actions.actions.find((a) => "
        "a.action_id === 'resolve_espionage_place_spy')"
    )
    seat = page.evaluate("state.viewSeat")
    requests = []
    page.on(
        "request",
        lambda r: (
            requests.append(r.post_data_json)
            if r.method == "POST" and r.url.endswith("/actions")
            else None
        ),
    )
    ring = page.locator(
        f".spy-post-hotspot[data-post='{chosen['arguments']['post_id']}']"
    )
    ring.focus()
    ring.press("Enter")
    assert settled(page, 20)
    check.ok(
        len(requests) == 1, "keyboard activation sends exactly one action", requests
    )
    check.ok(
        requests[0]["index"] == chosen["index"],
        "the request carries the offered destination's action index",
    )
    check.ok(
        page.evaluate(
            """([seat, post]) =>
      state.view.players[seat].spy_post_ids.includes(post)""",
            [seat, chosen["arguments"]["post_id"]],
        ),
        "the chosen Spy is placed on that post",
    )


def fixtures(page) -> None:
    page.evaluate("""() => {
      window.spySaved = {actions: state.actions,
        view: structuredClone(state.view), apply: applyAction};
      window.spyClicks = [];
      applyAction = (index) => window.spyClicks.push(index);
    }""")
    posts = page.evaluate("Object.keys(state.catalog.posts)")
    for action_id in PLACEMENTS:
        page.evaluate(
            """([kind, posts]) => {
          state.actions = {...window.spySaved.actions, actions: [
            {index: 901, action_id: kind, arguments: {post_id: posts[0]}},
            {index: 902, action_id: 'recall_spy_for_placement',
              arguments: {post_id: posts[1]}},
            {index: 903, action_id: 'agent_turn',
              arguments: {infiltrate_post_id: posts[2]}},
          ]};
          state.pick = null;
          render();
        }""",
            [action_id, posts],
        )
        check.ok(
            page.evaluate(RINGS) == [posts[0]],
            f"{action_id}: destination glows; recall and Infiltrate do not",
        )
    # Deep Cover shares a post: click where a stacked Spy covers the disc.
    page.evaluate(
        """(post) => {
      state.actions.actions = [{index: 904, action_id: 'place_spy_on_space',
        arguments: {post_id: post}}];
      state.view.players[1].spy_post_ids = [post];
      render();
    }""",
        posts[0],
    )
    page.locator(f".spy-post-hotspot[data-post='{posts[0]}']").click()
    check.ok(
        page.evaluate("window.spyClicks") == [904],
        "a Spy already on the post lets the destination click through",
    )
    page.evaluate("state.busy = true")
    page.locator(".spy-post-hotspot").click()
    check.ok(
        page.evaluate("window.spyClicks") == [904], "a busy table cannot submit twice"
    )
    page.evaluate(
        """(post) => {
      state.busy = false;
      state.actions.actions = [
        {index: 905, action_id: 'place_spy_on_space', arguments: {post_id: post}},
        {index: 906, action_id: 'resolve_espionage_place_spy',
          arguments: {post_id: post}},
      ];
      render();
    }""",
        posts[0],
    )
    page.locator(".spy-post-hotspot").click()
    check.ok(
        page.evaluate("window.spyClicks") == [904],
        "two placement sources focus their choices without submitting one",
    )
    page.evaluate("state.busy = false; state.review = {}")
    check.ok(
        page.evaluate("legalSpyPostActions", posts[0]) == [],
        "review never offers Spy actions",
    )
    page.evaluate("""() => {
      state.review = null; state.actions = window.spySaved.actions;
      state.view = window.spySaved.view; applyAction = window.spySaved.apply; render();
    }""")


def main() -> None:
    with server() as (base, _), chrome() as browser:
        _, page, _ = open_context(browser, "spy-placement")
        live(page, base)
        fixtures(page)
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
