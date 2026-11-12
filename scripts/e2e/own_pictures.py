"""The public build's pictures: `--pictures own` (docs/own-pictures-plan.md stage 0).

The server leaves every private-assets picture out, so the owner's machine
shows what a friend's install shows: the catalog lists only the project's own
drawings (server/static/pictures), the page asks for no private picture, and
the own Solari coin is drawn on the seat panel, and a card without a
picture is drawn as its redrawn face (stage 1).
"""

from __future__ import annotations

import os
import tempfile
from urllib.parse import urlparse

from common import Check, api_get, chrome, open_context, server
from open_mode import create_game

check = Check()
SHOTS = os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(
    prefix="dune-e2e-own-pictures-"
)
# URL prefixes the private assets are served under (server/app.py).
PRIVATE = (
    "/card-images/",
    "/icons/",
    "/tokens/",
    "/board-image",
    "/bene-tleilax-image",
)
OWN_SOLARI = "/static/pictures/icons/solari.svg"
COINS = (
    "(src) => [...document.querySelectorAll('img')]"
    ".filter((i) => i.getAttribute('src') === src)"
)


def main() -> None:
    with server("--pictures", "own") as (base, _), chrome() as browser:
        catalog = api_get(base, "/catalog")
        icons = catalog["icons"]
        check.ok(icons.get("solari") == OWN_SOLARI, "catalog: own Solari drawing")
        check.ok(
            all(url.startswith("/static/pictures/") for url in icons.values()),
            "catalog: every icon is an own drawing",
        )
        log_icons = catalog["log_icons"]
        check.ok(
            len(icons) >= 53
            and len(log_icons) >= 26
            and all(
                url.startswith("/static/pictures/log/") for url in log_icons.values()
            ),
            f"catalog: every icon ({len(icons)}) and log picture ({len(log_icons)}) "
            "is an own drawing",
        )
        check.ok(
            catalog["board_image"] == "/static/pictures/board/uprising.svg"
            and catalog["board_image_ko"] == "/static/pictures/board/uprising_ko.svg",
            "catalog: no board scan, our own board drawing instead",
        )
        check.ok(
            all(entry["image"] is None for entry in catalog["cards"].values()),
            "catalog: no card face picture",
        )
        check.ok(
            catalog["first_player_token"] == "/static/pictures/tokens/first_player.svg",
            "catalog: no token picture, our own drawing instead",
        )

        _, page, _ = open_context(browser, "own-pictures")
        requested: list[str] = []
        page.on("request", lambda request: requested.append(request.url))
        create_game(page, base, humans=(0, 1, 2, 3))
        page.wait_for_function(
            f"""(src) => {{
              const coins = ({COINS})(src);
              return coins.length > 0
                && coins.every((img) => img.complete && img.naturalWidth > 0);
            }}""",
            arg=OWN_SOLARI,
        )
        drawn = page.evaluate(f"(src) => ({COINS})(src).length", OWN_SOLARI)
        check.ok(drawn >= 4, f"seat panels draw the own Solari coin ({drawn} found)")
        # The drawn board is the board screen's picture: the seats' Influence
        # cubes and score discs stand on it as on a scan.
        page.wait_for_function(
            "document.querySelector('#board .board-map')?.complete"
            " && document.querySelector('#board .board-map').naturalWidth > 0"
        )
        board = page.evaluate(
            """() => ({
              src: document.querySelector('#board .board-map').getAttribute('src'),
              cubes: document.querySelectorAll('#board .track-cube').length,
              discs: document.querySelectorAll('#board .seat-disc').length,
            })"""
        )
        check.ok(
            "/static/pictures/board/" in board["src"]
            and board["cubes"] >= 16
            and board["discs"] >= 4,
            f"the drawn board carries the live pieces ({board})",
        )
        # The Imperium row's cards have no picture: each is a redrawn face
        # (card_faces.js), none of whose boxes overflows, and a hover shows
        # the face large in the popover.
        page.wait_for_selector(".vcard.faced .card-face")
        faced = page.evaluate(
            "document.querySelectorAll('.vcard.faced .card-face').length"
        )
        check.ok(faced >= 5, f"the Imperium row draws redrawn faces ({faced})")
        overflow = page.evaluate(
            "[...document.querySelectorAll('.cf-agent, .cf-reveal')]"
            ".filter((b) => b.scrollHeight > b.clientHeight + 1).length"
        )
        check.ok(overflow == 0, f"no face box overflows ({overflow})")
        # An Intrigue card's face (War Chest: Combat "—OR—" Endgame), drawn
        # at the hand's Intrigue width, keeps both parts inside the card.
        war_chest = page.evaluate(
            """() => {
              const holder = document.createElement('div');
              holder.style.cssText = 'position:fixed;left:0;top:0;width:170px';
              const entry = state.catalog.intrigue.war_chest;
              const face = cardFace({ ...entry, image: null });
              holder.appendChild(face);
              document.body.appendChild(holder);
              const result = {
                parts: face.querySelectorAll('.cf-half').length,
                ors: face.querySelectorAll('.cf-or').length,
                fits: face.scrollHeight <= face.clientHeight + 1,
              };
              holder.remove();
              return result;
            }"""
        )
        check.ok(
            war_chest == {"parts": 2, "ors": 1, "fits": True},
            f"War Chest's face: two parts, one OR band, inside the card ({war_chest})",
        )
        # A Conflict's and a contract's faces: three reward boxes; a frame
        # with the space's icon and the reward (Harvest's "3+" on one row).
        others = page.evaluate(
            """() => {
              const holder = document.createElement('div');
              holder.style.cssText = 'position:fixed;left:0;top:0;width:280px';
              document.body.appendChild(holder);
              const face = (kind, id) => {
                const f = cardFace({ ...state.catalog[kind][id], image: null });
                holder.appendChild(f);
                return f;
              };
              const conflict = face('conflicts', 'battle_for_arrakeen');
              const harvest = face('contracts', 'harvest_3');
              const rows = harvest.querySelectorAll('.cf-on .cf-line');
              const windtraps = face('tech', 'windtraps');
              const drones = face('tech', 'spy_drones');
              const result = {
                rewards: conflict.querySelectorAll('.cf-reward').length,
                orange: conflict.classList.contains('cf-orange'),
                frame: Boolean(harvest.querySelector('.cf-send')),
                conditionRows: rows.length,
                techCost: windtraps.querySelector('.cf-hex')?.textContent,
                loneIcon: Boolean(windtraps.querySelector('.cf-body.few .cf-line.one')),
                // One green for every Tech tile, Bloodlines' too (2026-11-11).
                oneGreen: !drones.classList.contains('cf-bl'),
                techFits: [windtraps, drones].every(
                  (f) => f.querySelector('.cf-body').scrollHeight
                    <= f.querySelector('.cf-body').clientHeight + 1),
              };
              holder.remove();
              return result;
            }"""
        )
        check.ok(
            others
            == {
                "rewards": 3,
                "orange": True,
                "frame": True,
                "conditionRows": 1,
                "techCost": "2",
                "loneIcon": True,
                "oneGreen": True,
                "techFits": True,
            },
            f"Conflict, contract and Tech faces ({others})",
        )
        # A seat's own redrawn leader: the face is the popover's stage and
        # the seat's token sits on the face's own track cell (Feyd-Rautha's
        # first Spy space, Chani's sixth space).
        tokens = page.evaluate(
            """() => {
              const anchor = document.querySelector('.seat .leader-name');
              const result = {};
              for (const [id, extra, cell] of [
                ['feyd_rautha_harkonnen', { feyd_track_space: 'first_spy' }, 2],
                ['chani', { tactics_track_space: 5 }, 5],
              ]) {
                const seat = {
                  ...state.view.players[0], leader_id: id, leader_face_id: id, ...extra,
                };
                openPopover(state.catalog.leaders[id], anchor, seat);
                const pop = document.getElementById('card-popover');
                const face = pop.querySelector('.popover-leader-stage > .cf-leader');
                const token = pop.querySelector('.popover-leader-stage .leader-token');
                const cells = face ? face.querySelectorAll('.cf-lcell') : [];
                const inside = (a, b) => {
                  const r = a.getBoundingClientRect(), c = b.getBoundingClientRect();
                  const x = r.left + r.width / 2, y = r.top + r.height / 2;
                  return x > c.left && x < c.right && y > c.top && y < c.bottom;
                };
                result[id] = Boolean(face && token && cells[cell])
                  && inside(token, cells[cell])
                  && pop.scrollWidth <= pop.clientWidth + 1;
                closePopover();
              }
              return result;
            }"""
        )
        check.ok(
            tokens == {"feyd_rautha_harkonnen": True, "chani": True},
            f"a redrawn leader carries the seat's token on its track ({tokens})",
        )
        page.locator(".vcard.faced").first.hover()
        page.wait_for_selector("#card-popover .popover-face")
        check.ok(True, "the popover shows the face large")
        private = [url for url in requested if urlparse(url).path.startswith(PRIVATE)]
        check.ok(not private, f"the page asks for no private picture ({private[:3]})")
        page.screenshot(path=f"{SHOTS}/own_pictures_table.png")
        print(f"screenshot: {SHOTS}/own_pictures_table.png")
    check.finish()


if __name__ == "__main__":
    main()
