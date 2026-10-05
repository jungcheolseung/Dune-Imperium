"""Objective battle-card popovers load the correct English/Korean crop."""

from __future__ import annotations

import os
import tempfile

from common import Check, chrome, open_context, server
from open_mode import create_game
from turn_controls import play_until

check = Check()
SHOTS = os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(
    prefix="dune-e2e-objective-"
)


def main() -> None:
    with server() as (base, _), chrome() as browser:
        _, page, rec = open_context(browser, "objective-images")
        create_game(page, base, humans=(0, 1, 2, 3))
        assert play_until(
            page,
            "state.view.players.every((p) => p.objective_ids.length === 1)",
            "state.actions.actions[0].index",
        )
        dealt = page.evaluate("state.view.players.map((p) => p.objective_ids[0])")
        check.ok(len(set(dealt)) == 4, "setup deals the four distinct Objective faces")
        ids = page.evaluate("Object.keys(state.catalog.objectives)")
        check.ok(len(ids) == 5, "all five Objective faces have catalog entries")
        page.evaluate("""() => {
          for (const player of state.view.players) setSeatExpanded(player.player, true);
        }""")
        for lang, width in (("ko", 1600), ("en", 1366)):
            page.set_viewport_size({"width": width, "height": 900})
            page.evaluate("setLanguage", lang)
            for card_id in ids:
                entry = page.evaluate("(id) => state.catalog.objectives[id]", card_id)
                language = "en" if card_id == "objective_ornithopter_1_3p" else lang
                check.ok(
                    f"/card-images/{language}/uprising/objective/" in entry["image"],
                    f"{lang}: {card_id} uses its language or fallback",
                )
                # Use the actual battle tag when dealt, otherwise the same tag
                # renderer for the 1-3P face outside this four-player setup.
                page.evaluate(
                    """(id) => {
                  closePopover();
                  const entry = state.catalog.objectives[id];
                  let tag = [...document.querySelectorAll('#seats .tag')]
                    .find((n) => n.textContent === entry.name);
                  if (!tag) {
                    tag = chip(id);
                    el('private-zone').appendChild(tag);
                  }
                  tag.dataset.objective = id;
                }""",
                    card_id,
                )
                tag = page.locator(f".tag[data-objective='{card_id}']")
                tag.hover()
                page.wait_for_function("""() => {
                  const img = el('card-popover').querySelector('img');
                  return img && img.complete && img.naturalWidth > 0;
                }""")
                tag.click()
                page.wait_for_function("""(expected) => {
                  const img = el('card-popover').querySelector('img');
                  return img && img.getAttribute('src') === expected
                    && img.complete && img.naturalWidth > 0;
                }""", arg=entry["image"])
                image = page.locator("#card-popover img").first
                check.ok(
                    image.get_attribute("src") == entry["image"],
                    f"{lang}: battle-card popover shows {card_id}",
                )
                check.ok(
                    image.evaluate(
                        "(n) => n.naturalWidth === 440 && n.naturalHeight === 680"
                    ),
                    f"{lang}: crop loads at the standardized card size",
                )
            page.evaluate("""() => pinPopover(
              state.catalog.objectives.objective_desert_mouse,
              document.querySelector('#seats .tag'))""")
            page.locator("#card-popover").screenshot(
                path=f"{SHOTS}/objective_{lang}.png"
            )
        page.evaluate("""() => {
          closePopover();
          const entry = {...state.catalog.objectives.objective_desert_mouse,
            image: null};
          pinPopover(entry, document.querySelector('#seats .tag'));
        }""")
        check.ok(
            page.locator("#card-popover img").count() == 0,
            "a missing image keeps the text popover usable",
        )
        check.ok(
            not any(
                status == 404 and "card-images/" in url
                for _, _, url, status in rec.requests
            ),
            "no Objective image request returns 404",
        )
    print(f"Screenshots: {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
