"""E2E: one id, one thing per catalog section (2026-09-27).

An id is unique only inside its catalog section. `deliver_supplies` is both a
board space and the Uprising contract that pays for visiting it, and
"acquire" is both a contract and the engine's provenance verb
("…:acquire:imperium:interstellar_trade:0:…"). The client used to resolve
every id kind-blindly (core.js lookup() in section order, contracts before
spaces), so the Bloodlines Sardaukar Commander strip opened the contract for
the Deliver Supplies space; in Korean, where the contract has a Korean name
and the space none, the action list, the log, the seat panel (which listed the
placed Agents until 2026-10-26) and the staged Agent turn named the space
"보급품 배송"; a log turn card that completed the
Deliver Supplies contract lost its thumbnail; and a contract taken with
Interstellar Trade said it came from "Acquire" (docs/lessons.md 2026-09-27).

Every oracle reads the catalog section itself and never calls lookup(). The
last step checks the guard: a kind-blind lookup of a shared id is a console
error, which fails every e2e script (common.Check.finish).
"""

from __future__ import annotations

import shutil

from common import (
    RULE_OPTIONS,
    SERVER_LOG_COPY,
    Check,
    chrome,
    open_context,
    server,
    set_rule_options,
)
from open_mode import settled

check = Check()

SEED = 11
SPACE = "deliver_supplies"
CONTRACT = f"contract:{SPACE}"
ACQUIRE_SOURCE = (
    "round:3:player:1:acquire:imperium:interstellar_trade:0:acquisition_bonus"
)
# A Tech tile's Endgame line (rules/tech.py apply_endgame_tech_effects): its
# point arrives on the step that ends the last Combat, so a log line without
# the tile's name read as a Conflict reward (play feedback 2026-10-25).
ENDGAME_TECH_SOURCE = "round:9:player:0:endgame_tech:choam_transports"
ACQUIRE_CHANCE = (
    "round:9:player:2:acquire:imperium:spiritual_fervor:1:acquisition_bonus"
    ":research:c7r3:card:discard_shuffle"
)

# The oracle: names straight from the sections, in the page's language
# (localizeCatalog swaps name and image in place).
NAMES_JS = """() => {
  const c = state.catalog;
  return {
    space: c.spaces.deliver_supplies.name,
    spaceImage: entryImage(c.spaces.deliver_supplies) || null,
    contract: c.contracts.deliver_supplies.name,
    contractImage: c.contracts.deliver_supplies.image || null,
    acquire: c.contracts.acquire.name,
    trade: c.cards.interstellar_trade.name,
    fervor: c.cards.spiritual_fervor.name,
    transports: c.tech.choam_transports.name,
  };
}"""

STRIP_JS = """() => {
  const ids = state.view.sardaukar_commander_space_ids;
  const tags = [...document.querySelectorAll(
    "#market .strip[data-strip='Sardaukar Commander'] .strip-cards .tag")];
  return {
    ids,
    shown: tags.map((tag) => tag.textContent),
    wanted: ids.map((id) => state.catalog.spaces[id].name),
  };
}"""

POPOVER_JS = """() => {
  const pop = document.getElementById("card-popover");
  const title = pop.querySelector(".popover-title");
  return {
    open: !pop.hidden && pop.style.display !== "none",
    title: title ? title.textContent : null,
    options: pop.querySelectorAll(".option-line").length,
    images: [...pop.querySelectorAll("img")].map((img) => img.getAttribute("src")),
  };
}"""

# One Agent turn at Deliver Supplies that completes the contract of the same
# id: the log's step heads, event lines, the turn card's head (Agent icon +
# space) and its card row, built by the functions the live log uses. The
# placement's log entry is the space pick (`place_agent`, stage B1); the card
# pick before it names no space.
TURN_CARD_JS = """() => {
  const group = {
    actor: 0,
    entries: [
      {type: "action", index: 1, undone: false, action_id: "place_agent",
       arguments: {space_id: "deliver_supplies"},
       events: [{kind: "agent_placed",
                 payload: {player: 0, space_id: "deliver_supplies"}}]},
      {type: "action", index: 2, undone: false, action_id: "complete_contract",
       arguments: {instance_id: "contract:deliver_supplies"},
       events: [{kind: "contract_completed",
                 payload: {player: 0, contract_id: "contract:deliver_supplies"}}]},
    ],
  };
  const targets = logTargets(group);
  const card = turnCard(group, Infinity);
  const where = card.querySelector(".turn-where");
  return {
    spaces: targets.spaces,
    cards: targets.cards,
    where: where ? where.textContent : null,
    heads: [...card.querySelectorAll(".turn-line-head")].map((n) => n.textContent),
    events: [...card.querySelectorAll(".logevent")].map((n) => n.textContent),
    thumbnails: [...card.querySelectorAll(".turn-cards .vcard")]
      .map((n) => n.dataset.instance),
  };
}"""


# The staged Agent turn's other two places that name the picked space: the
# note when the halves of a pick cannot go together (card after space, and
# space after card) and the chooser a complete pick with several candidates
# opens. Both read the page's placements (placementActions: the server's
# `agent_placements`, each pointing at its `choose_agent_card` row), so a
# synthetic list stands in for this turn's and the page's own is put back.
STAGED_JS = """() => {
  const saved = {actions: state.actions, pick: state.pick};
  const pickRow = (index, card) => ({
    index, action_id: "choose_agent_card", arguments: {card_id: card},
  });
  const place = (placement, row, card, space, extra = {}) => ({
    index: row, placement,
    arguments: {card_id: card, space_id: space, ...extra},
  });
  const said = () => document.getElementById("game-note").textContent;
  const result = {};
  try {
    state.actions = {...(saved.actions || {}),
      actions: [
        pickRow(0, "imperium:guild_spy:0"),
        pickRow(1, "imperium:guild_spy:1"),
      ],
      agent_placements: [
        place(0, 0, "imperium:guild_spy:0", "arrakeen"),
        place(1, 1, "imperium:guild_spy:1", "deliver_supplies"),
        place(2, 1, "imperium:guild_spy:1", "deliver_supplies",
          {infiltrate_post_id: "x"}),
      ]};
    state.pick = {spaceId: "deliver_supplies"};
    pickStep("imperium:guild_spy:0", null, null);
    result.cardAfterSpace = said();
    state.pick = {cardId: "imperium:guild_spy:0"};
    pickStep("deliver_supplies", null, null);
    result.spaceAfterCard = said();
    state.pick = {cardId: "imperium:guild_spy:1", spaceId: "deliver_supplies"};
    openPlacementChooser(placementActions().filter(
      (a) => a.arguments.card_id === "imperium:guild_spy:1"));
    result.chooser = document.querySelector("#card-popover .popover-title").textContent;
  } finally {
    state.actions = saved.actions;
    state.pick = saved.pick;
    closePopover();
    render();
  }
  return result;
}"""


def create_game(page, base: str) -> None:
    page.goto(base + "/")
    page.wait_for_selector("#setup-screen:not([hidden])")
    for seat in range(4):
        page.select_option(
            f"#seat-selects select[data-seat='{seat}']",
            "human" if seat == 0 else "heuristic",
        )
    set_rule_options(page, *RULE_OPTIONS)
    page.fill("#opt-seed", str(SEED))
    page.click("#create-game")
    page.wait_for_selector("#game-screen:not([hidden])")
    page.wait_for_function("state.view !== null && refreshFlight === null")


def switch(page, lang: str) -> None:
    if page.evaluate("TERM_LANGUAGE") != lang:
        page.click("#language-toggle")
    page.wait_for_function("(lang) => document.documentElement.lang === lang", arg=lang)
    settled(page)


def close_popover(page) -> None:
    page.keyboard.press("Escape")
    page.mouse.click(5, 5)


def one_language(page, lang: str) -> None:
    print(f"[{lang}]")
    switch(page, lang)
    names = page.evaluate(NAMES_JS)
    # The space and the contract print the same name in both languages
    # ("Deliver Supplies"; "보급품 배송" on the Korean contract tile and, since
    # 2026-10-11, the Korean Board Space Guide's name for the space), so the
    # popover, the pictures and the log targets tell them apart; a text check
    # below discriminates only where the names differ.
    distinct = names["space"] != names["contract"]
    if lang == "ko":
        check.ok(
            names["space"] == "보급품 배송",
            "Korean names the space by the Korean Board Space Guide",
            names,
        )

    def names_space(text: str | None) -> bool:
        return bool(text) and names["space"] in text and (
            not distinct or names["contract"] not in text
        )

    strip = page.evaluate(STRIP_JS)
    check.ok(
        SPACE in strip["ids"],
        "a Commander waits on Deliver Supplies [Bloodlines p. 3]",
        strip["ids"],
    )
    check.ok(strip["shown"] == strip["wanted"],
             "the Commander strip names each chip as its board space", strip)

    index = strip["ids"].index(SPACE)
    chip = page.locator(
        "#market .strip[data-strip='Sardaukar Commander'] .strip-cards .tag"
    ).nth(index)
    chip.click()
    popover = page.evaluate(POPOVER_JS)
    check.ok(popover["title"] == names["space"] and popover["options"] > 0,
             "its popover is the space: its name and its option lines", popover)
    if names["contractImage"] and names["spaceImage"]:
        check.ok(names["contractImage"] not in popover["images"],
                 "and not the contract's picture", popover["images"])
        check.ok(names["spaceImage"] in popover["images"],
                 "it shows the space's own picture", popover["images"])
    else:
        print("  .. SKIP the picture checks: no local card pictures are served")
    close_popover(page)

    contract_chip = page.evaluate(
        "(id) => { const n = chip(id); return n.textContent; }", CONTRACT
    )
    check.ok(contract_chip == names["contract"],
             "a contract chip still names the contract", contract_chip)

    field = page.evaluate("fieldText('space_id', 'deliver_supplies', {})")
    check.ok(names_space(field), "a space_id field names the space", field)
    label = page.evaluate(
        "describeActionText({action_id: 'place_agent',"
        " arguments: {space_id: 'deliver_supplies'}})"
    )
    check.ok(names_space(label), "the action list names the space", label)
    # The staged turn lists a whole placement (card and space) under the
    # page's own name for it.
    label = page.evaluate(
        "describeActionText({action_id: 'agent_turn',"
        " arguments: {card_id: 'imperium:guild_spy:0',"
        " space_id: 'deliver_supplies'}})"
    )
    check.ok(names_space(label), "a staged placement names the space", label)

    turn = page.evaluate(TURN_CARD_JS)
    check.ok(turn["spaces"] == [SPACE] and turn["cards"] == [CONTRACT],
             "a turn card's targets keep the space and the contract apart", turn)
    check.ok(names_space(turn["where"]), "the turn card's head names the space", turn)
    check.ok(names_space(turn["heads"][0]), "the log step names the space", turn)
    check.ok(names_space(turn["events"][0]), "the log event names the space", turn)
    check.ok(turn["thumbnails"] == [CONTRACT],
             "the completed contract keeps its thumbnail", turn["thumbnails"])

    step = page.evaluate(
        "pickStepNode('②', t('turn.step_space'), 'deliver_supplies', 'spaceId')"
        ".textContent"
    )
    check.ok(names_space(step), "the staged Agent turn's step ② names the space", step)
    staged = page.evaluate(STAGED_JS)
    check.ok(names_space(staged["cardAfterSpace"]),
             "a card that cannot go there: the note names the picked space", staged)
    check.ok(names_space(staged["spaceAfterCard"]),
             "a space the card cannot go to: the note names that space", staged)
    check.ok(names_space(staged["chooser"]),
             "the placement chooser's title names the space", staged)

    # An Agent on the space: the seat panel listed the placed Agents until
    # the board's own pieces took that over (play feedback 2026-10-26), so
    # it names neither the space nor, taking it for the contract, the
    # contract. The view is the render's only input, so the page's copy is
    # edited and redrawn.
    seat_text = page.evaluate(
        """() => {
          const player = state.view.players[0];
          const saved = player.agent_locations;
          player.agent_locations = ["deliver_supplies"];
          render();
          const text = document.querySelector(".seat[data-seat='0']").textContent;
          player.agent_locations = saved;
          render();
          return text;
        }"""
    )
    check.ok(
        names["space"] not in seat_text
        and (not distinct or names["contract"] not in seat_text),
        "the seat panel leaves a placed Agent to the board",
        seat_text,
    )

    source = page.evaluate("(value) => sourceName(value)", ACQUIRE_SOURCE)
    check.ok(source == names["trade"],
             "a contract taken with Interstellar Trade names the card, not Acquire",
             (source, names["acquire"]))
    endgame = page.evaluate("(value) => sourceName(value)", ENDGAME_TECH_SOURCE)
    check.ok(endgame == names["transports"],
             "CHOAM Transports' Endgame point names the tile", endgame)
    chance = page.evaluate("(value) => describeChance(value)", ACQUIRE_CHANCE)
    check.ok(names["fervor"] in chance and names["acquire"] not in chance,
             "a reshuffle from Spiritual Fervor's research names the card", chance)


def main() -> None:
    with server() as (base, server_log), chrome() as browser:
        context, page, rec = open_context(browser, "catalog-kinds")
        try:
            create_game(page, base)
            for lang in ("ko", "en"):
                one_language(page, lang)
            check.ok(
                not rec.js_errors,
                "no JS errors, so no kind-blind lookup of a shared id",
                rec.js_errors[:5],
            )

            print("[guard]")
            typed = page.evaluate(
                "lookup('deliver_supplies', 'spaces')"
                " === state.catalog.spaces.deliver_supplies"
                " && lookup('deliver_supplies', 'contracts')"
                " === state.catalog.contracts.deliver_supplies"
            )
            check.ok(
                typed and not rec.js_errors, "a lookup that names the kind is quiet"
            )
            page.evaluate("lookup('deliver_supplies')")
            check.ok(
                len(rec.js_errors) == 1 and SPACE in rec.js_errors[0],
                "a kind-blind lookup of a shared id is a console error",
                rec.js_errors,
            )
            # Provoked on purpose: not one for Check.finish() to count.
            rec.js_errors.clear()
        finally:
            if check.failed:
                rec.dump()
            context.close()
            shutil.copy(server_log, SERVER_LOG_COPY)
        text = server_log.read_text()
        check.ok(
            "Traceback" not in text and "ERROR" not in text,
            f"no server errors (see {SERVER_LOG_COPY})",
        )
    check.finish()


if __name__ == "__main__":
    main()
