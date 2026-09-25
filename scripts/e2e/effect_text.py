"""E2E for the Korean effect-text feature, Steps K1-K3 (2026-09-25).

Feature decided 2026-09-25: the effect text the engine *generates* (as
opposed to a card's printed wording, which stays English in both languages)
gets a Korean version in the Korean UI. Step K1 wired the client path and
filled in the first generator (``display.structs``'s Contract condition/
reward and Conflict reward text, ``server/catalog.py``'s ``condition_ko``/
``reward_ko``/``rewards_ko``). Step K2 grows the same wiring to personal
cards (Imperium/starting/Reserve/Tleilaxu): ``cards[id].text_ko``
(``display.cards.personal_card_text_ko``) and a keyed Agent-box icon's own
``detail_ko`` (``display.actions.agent_card_icon_text_ko``,
``server/sessions.py`` ``_serialize_action``). Step K3 grows it to Intrigue
and Navigation cards: ``intrigue[id].text_ko``
(``display.effect_dsl_text_ko.intrigue_card_text_ko``, one Korean line per
printed option, same index as ``text``) and a ``play_intrigue``/
``play_navigation`` option row (``core.js`` ``describeAction()`` →
``intrigueOptionBody()``); later steps grow the same wiring to spaces and
Leaders.

This opens one Contract's, one Conflict's, one personal card's and one
Intrigue card's popover directly (``lookup()`` + ``openPopover()``, the way
``card_labels.py`` does, so it needs no real game decision to reach them)
and checks, in Korean:

- the condition/reward lines render through the new ``.effect-text-ko``
  class, not ``.card-text`` (the class printed English wording uses, and
  the one lang.py's/log_words.py's Korean-leak checks skip — this text must
  NOT be skipped, since it is not printed on any card);
- every ``{term}``/``{term:count}`` placeholder the catalog's ``_ko`` field
  carries is expanded to an icon or a word by the rendered line (no literal
  ``{`` left, and at least one line draws a real icon element);
- the rendered line holds no Latin-alphabet text beyond a board-space name
  (glossary "공간 이름" row: always English) or a card with no known Korean
  print;
- **icon parity**: each underlying field's ``phrase(ko)`` draws exactly the
  same multiset of icons as ``iconize(en)`` draws for the matching English
  field — not merely "at least one icon somewhere in the line" (2026-09-25
  review: that weaker check passed on 41 rows across the full catalog whose
  Korean drew a different icon set than English — a bare word instead of
  the Agent piece, a numbered Spy icon where English draws a bare one, the
  combined {trash_intrigue} icon where English draws Intrigue and Trash
  separately, a plain "→" character instead of the arrow icon, and the
  {control} icon where English draws none). ``check_icon_parity`` below is
  the reusable check; call it for every ``(en, ko)`` field pair a later
  generator adds, the same way ``check_korean`` already loops the fields
  this step covers.

Step K2 additionally checks a personal card's own ``text``/``text_ko``
lines through the same ``check_korean``/``check_english`` (generalized to
loop the catalog's generic ``text``/``text_ko`` array, not only the
Contract/Conflict-specific fields), and a keyed Agent-box icon's own
resolution row — the legal-action list row a live ``resolve_agent_card_effect``
decision shows (``render.js`` ``describeAction()``, the same function a real
row calls, ``render.js`` :1262). That check builds a **synthetic** action
object carrying real ``detail``/``detail_ko`` strings a Python test already
golden-checks against the live server pipeline
(``tests/server/test_sessions.py``
``test_serialized_actions_carry_the_agent_box_icon_detail_ko``), the same
"no real game decision needed" approach this script already uses for the
Contract/Conflict popovers — this script's job is only to check how the DOM
renders a string the Python side already verified is the right one.

Step K3 checks an Intrigue card's popover through the same generic
``text``/``text_ko`` loop (``lookup()`` resolves ``state.catalog.intrigue``
too), plus a **synthetic** two-option ``play_intrigue`` row for a real
two-option card (``describeAction()``'s ``play_intrigue`` branch resolves
``state.catalog.intrigue[baseId(card_id)].text_ko[option]`` the same way a
live row would; ``intrigue_options.py`` drives a *real* dual-option decision
end to end, so this script only needs the synthetic shortcut to also check
Korean, mirroring the resolution-row check above).

And, in English, that the same lines are pixel-for-pixel what they always
were: still ``.card-text``, no ``.effect-text-ko`` anywhere, matching
``iconize(entry.condition)``/``iconize(entry.reward)`` computed
independently of the popover under test.

Screenshots of the Contract/Conflict/personal-card/Intrigue popovers, the
resolution row and the Intrigue play row, Korean, 1440x900, go beside this
script's results for a human to look at.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from common import Check, chrome, open_context, server
from open_mode import create_game, settled

check = Check()
VIEWPORT = {"width": 1440, "height": 900}

# One Contract and one Conflict whose Korean text exercises a board-space
# name staying English, several resource/icon TERMS and a "may" clause —
# tests/unit/display/test_struct_text.py pins their exact English and
# Korean strings, so a change to either is caught there first; this script
# only checks how the DOM renders them.
# condition: BOARD_SPACE "Sardaukar" ({agent}); reward: Recall 1 Agent
# (bare {agent}, 2026-09-25 review: not the distinct {recall_agent} icon).
CONTRACT_ID = "sardaukar_ii"
# 1st reward: Victory Points + Control + an optional Spy-recall trade.
CONFLICT_ID = "battle_for_arrakeen"
# Guild Spy (Step K2): an Agent-box discard→draw line, an "On acquire:"
# Place-a-Spy line and a "Reveal, if you acquire The Spice Must Flow:"
# line — exercises both Korean box labels this step adds ("에이전트 칸:",
# "획득 시:") in one card. tests/unit/display/test_card_text.py's
# test_guild_spy_ko_reveal_acquisition_line_names_the_spice_must_flow pins
# its exact English/Korean text, so a change to either is caught there
# first; this script only checks how the DOM renders it.
PERSONAL_CARD_ID = "guild_spy"
# Backed by CHOAM (Step K3): two options, Plot (LoseInfluence -> Gain
# solari) and Combat (a CompletedContractsAtLeast condition -> Gain
# swords) -- exercises a cost/reward arrow and a condition line in one
# card. tests/unit/display/test_effect_dsl_text.py's
# test_option_text_ko_backed_by_choam_plot_option pins its exact Korean
# text (quoted from the card's own Korean scan, `[KO card: Backed by
# CHOAM]`), so a change to either is caught there first; this script only
# checks how the DOM renders it.
INTRIGUE_ID = "backed_by_choam"

OPEN_POPOVER_JS = """(id) => {
  const entry = lookup(id);
  if (!entry) return null;
  openPopover(entry, document.querySelector("header h1"));
  const pop = document.getElementById("card-popover");
  const lines = [...pop.querySelectorAll(".popover-line")];
  return {
    name: entry.name,
    condition: entry.condition || null,
    condition_ko: entry.condition_ko || null,
    reward: entry.reward || null,
    reward_ko: entry.reward_ko || null,
    rewards: entry.rewards || null,
    rewards_ko: entry.rewards_ko || null,
    text: entry.text || null,
    text_ko: entry.text_ko || null,
    lines: lines.map((line) => ({
      className: line.className,
      text: line.textContent,
      koSpans: line.querySelectorAll(".effect-text-ko").length,
      cardTextSpans: line.querySelectorAll(".card-text").length,
      icons: line.querySelectorAll("img, svg, .icon-text").length,
    })),
  };
}"""

# The icon signature of a rendered fragment: one entry per icon element, in
# document order — "Nxkey" for a counted `.amount` (key from its image
# filename, or "agent-piece" for the SVG piece with no image), or bare
# "key" for a standalone icon. Ported from the review's scratch
# icon_parity.py scan (41-row finding, 2026-09-25) so the same signature
# comparison runs as a standing check instead of a one-off script.
ICON_SIGNATURE_JS = r"""({en, ko}) => {
  const key = (n) => {
    if (!n) return "none";
    if (n.tagName === "IMG") return n.src.split("/").pop().replace(/\?.*$/, "");
    if (n.tagName.toLowerCase() === "svg") return "agent-piece";
    return "text:" + n.textContent;
  };
  const sig = (node) => {
    const out = [];
    const walk = (n) => {
      if (n.nodeType !== 1) return;
      if (n.classList && n.classList.contains("amount")) {
        const first = n.firstChild;
        const count = first && first.nodeType === 3 ? first.textContent : "?";
        out.push(`${count}x${key(n.querySelector("img, svg, .icon-text"))}`);
        return;
      }
      if (n.matches && n.matches("img, svg, .icon-text")) { out.push(key(n)); return; }
      for (const c of n.childNodes) walk(c);
    };
    const box = document.createElement("span");
    box.appendChild(node);
    walk(box);
    return out;
  };
  return { enIcons: sig(iconize(en)), koIcons: ko ? sig(phrase(ko)) : null };
}"""

# Independent of describeAction/popoverNodes: the same iconize() the English
# renderer always used, so the English check does not lean on the code path
# it is meant to catch a regression in.
ICONIZE_TEXT_JS = """(text) => {
  const box = document.createElement("span");
  box.appendChild(iconize(text));
  return box.textContent;
}"""

SPACE_NAMES_JS = "() => Object.values(state.catalog.spaces).map((s) => s.name)"

# The popover's icon <img>s load asynchronously; without this a screenshot
# taken right after openPopover() can catch one mid-load (board_tokens.py/
# leader_card.py hit the same race and wait on img.complete the same way).
POPOVER_IMAGES_LOADED_JS = (
    "[...document.querySelectorAll('#card-popover img')]"
    ".every((img) => img.complete && img.naturalWidth > 0)"
)


def _wait_for_popover_images(page) -> None:
    page.wait_for_function(POPOVER_IMAGES_LOADED_JS)


def _check_no_stray_latin(what: str, text: str, allowed: list[str]) -> None:
    bare = text
    for name in sorted(allowed, key=len, reverse=True):
        bare = bare.replace(name, " ")
    stray = sorted(set(re.findall(r"[A-Za-z][A-Za-z']*", bare)))
    check.ok(not stray, f"{what}: no stray Latin text", (stray, text))


def check_icon_parity(
    page, kind: str, field: str, en_text: str, ko_text: str | None
) -> None:
    """The rendered Korean line draws the same icon multiset as English.

    ``field`` is one raw catalog field (e.g. "condition", "reward",
    "rewards[0]"); a line with no Korean twin yet (a later step's field)
    checks nothing, the way the rest of this script already falls back to
    English for those. Order does not matter — a Korean line is free to
    say things in a different order than the English prose — but which
    icons appear, and how many times, must match exactly (2026-09-25
    review: the old check only asked for "at least one icon somewhere").
    """

    if ko_text is None:
        return
    result = page.evaluate(ICON_SIGNATURE_JS, {"en": en_text, "ko": ko_text})
    en_icons = sorted(result["enIcons"])
    ko_icons = sorted(result["koIcons"] or [])
    check.ok(
        en_icons == ko_icons,
        f"{kind} {field}: Korean draws the same icons as iconize(en)",
        {"en": en_text, "ko": ko_text, "en_icons": en_icons, "ko_icons": ko_icons},
    )


def check_korean(page, kind: str, entry_id: str, space_names: list[str]) -> None:
    result = page.evaluate(OPEN_POPOVER_JS, entry_id)
    check.ok(result is not None, f"Korean {kind}: {entry_id} resolves via lookup()")
    if result is None:
        return
    if result["condition"] is not None:
        check_icon_parity(
            page, kind, "condition", result["condition"], result["condition_ko"]
        )
    if result["reward"] is not None:
        check_icon_parity(page, kind, "reward", result["reward"], result["reward_ko"])
    if result["rewards"] is not None:
        rewards_ko = result["rewards_ko"] or [None] * len(result["rewards"])
        pairs = zip(result["rewards"], rewards_ko, strict=True)
        for index, (en_line, ko_line) in enumerate(pairs):
            check_icon_parity(page, kind, f"rewards[{index}]", en_line, ko_line)
    if result["text"] is not None:
        # A personal card's own text[]/text_ko[] (Step K2) — same shape as
        # rewards[]/rewards_ko[] above, one line per index.
        text_ko = result["text_ko"] or [None] * len(result["text"])
        pairs = zip(result["text"], text_ko, strict=True)
        for index, (en_line, ko_line) in enumerate(pairs):
            check_icon_parity(page, kind, f"text[{index}]", en_line, ko_line)
    lines = result["lines"]
    check.ok(bool(lines), f"Korean {kind}: the popover has lines", result)
    for line in lines:
        check.ok(
            line["koSpans"] > 0 and line["cardTextSpans"] == 0,
            f"Korean {kind}: '{line['text']}' renders through .effect-text-ko, "
            "not .card-text",
            line,
        )
        check.ok(
            "{" not in line["text"] and "}" not in line["text"],
            f"Korean {kind}: '{line['text']}' has no leftover {{placeholder}}",
            line,
        )
        _check_no_stray_latin(f"Korean {kind}", line["text"], space_names)
    check.ok(
        any(line["icons"] > 0 for line in lines),
        f"Korean {kind}: at least one line draws a real icon element",
        lines,
    )
    # At least one of the raw catalog fields actually carries a {term}
    # placeholder (otherwise the checks above would trivially pass on an
    # empty/plain string) -- condition_ko alone may not (a BOARD_SPACE
    # condition is plain words, no icon), so every field is joined rather
    # than picked by the first truthy one.
    rewards_ko = result["rewards_ko"] or []
    text_ko = result["text_ko"] or []
    fields = [result["condition_ko"], result["reward_ko"], *rewards_ko, *text_ko]
    raw = "|".join(filter(None, fields))
    check.ok(
        "{" in raw, f"Korean {kind}: the catalog field itself uses placeholders", raw
    )


ALL_CARDS_ICON_PARITY_JS = (
    "() => Object.entries(state.catalog.cards)"
    ".map(([id, e]) => [id, e.text || [], e.text_ko || []])"
)

ALL_INTRIGUE_ICON_PARITY_JS = (
    "() => Object.entries(state.catalog.intrigue)"
    ".map(([id, e]) => [id, e.text || [], e.text_ko || []])"
)

# One accepted exception (2026-09-25 review): Urgent Shigawire's Agent-box
# line is "The next Bene Gesserit card you play this round has all Agent
# icons and, added to its Agent box: Draw 1 card" — ICON_RULES' bare
# ``\bAgents?\b`` rule also iconizes the *label* word "Agent" inside "its
# Agent box" (an English-side quirk of iconize() scanning raw prose, not a
# rule this project chose), giving English a second Agent-piece icon the
# Korean print's own "에이전트 칸" (a plain box-label word, matching every
# other card's box label) correctly does not have. Narrowed to this one
# (card, line index) pair so any other card's mismatch still fails.
_ACCEPTED_ICON_PARITY_EXCEPTIONS: frozenset[tuple[str, int]] = frozenset(
    {("urgent_shigawire", 0)}
)


def check_all_cards_icon_parity(page) -> None:
    """Icon parity (``check_icon_parity``) for every catalog card's
    ``text``/``text_ko`` lines, not only ``PERSONAL_CARD_ID`` above.

    2026-09-25 review: ``check_korean``'s ``text[]``/``text_ko[]`` loop only
    ever ran against ``guild_spy``, so a Korean line drawing a different
    icon multiset than its English counterpart on any of the other 217
    catalog cards passed silently — a scratch sweep with the real
    ``iconize()``/``phrase()`` found 17 such lines (a missing Persuasion
    icon on 8 "Command (6+ Persuasion)" cards, a stray extra ``{draw}``/
    ``{discard}``/``{contract}``/``{influence_any}`` icon on others, a
    dropped count). The fixes live in ``display/tokens_ko.py`` and
    ``display/cards.py``, each pinned to the ``docs/rules/glossary-ko.md``
    word or the printed-icon shape that justifies it; this sweep is the
    standing guard so a future card regresses the same way here, not only
    in a one-off script.
    """

    rows = page.evaluate(ALL_CARDS_ICON_PARITY_JS)
    checked = 0
    for card_id, en_lines, ko_lines in rows:
        ko_padded = list(ko_lines) + [None] * (len(en_lines) - len(ko_lines))
        pairs = zip(en_lines, ko_padded, strict=True)
        for index, (en_line, ko_line) in enumerate(pairs):
            checked += 1
            if (card_id, index) in _ACCEPTED_ICON_PARITY_EXCEPTIONS:
                continue
            check_icon_parity(page, "Card", f"{card_id}.text[{index}]", en_line, ko_line)
    check.ok(
        checked > 0, "checked at least one card text[]/text_ko[] line", checked
    )


def check_all_intrigue_icon_parity(page) -> None:
    """Icon parity (``check_icon_parity``) for every Intrigue card's
    ``text``/``text_ko`` lines (Step K3), the Intrigue twin of
    ``check_all_cards_icon_parity`` above — that sweep found 17 mismatched
    personal-card lines the single-card ``PERSONAL_CARD_ID`` check missed,
    so Intrigue gets the same full-catalog sweep from the start rather than
    trusting the one hand-picked ``INTRIGUE_ID`` example.
    """

    rows = page.evaluate(ALL_INTRIGUE_ICON_PARITY_JS)
    checked = 0
    for card_id, en_lines, ko_lines in rows:
        ko_padded = list(ko_lines) + [None] * (len(en_lines) - len(ko_lines))
        pairs = zip(en_lines, ko_padded, strict=True)
        for index, (en_line, ko_line) in enumerate(pairs):
            checked += 1
            check_icon_parity(
                page, "Intrigue", f"{card_id}.text[{index}]", en_line, ko_line
            )
    check.ok(
        checked > 0, "checked at least one Intrigue text[]/text_ko[] line", checked
    )


def check_english(page, kind: str, entry_id: str) -> None:
    result = page.evaluate(OPEN_POPOVER_JS, entry_id)
    check.ok(result is not None, f"English {kind}: {entry_id} resolves via lookup()")
    if result is None:
        return
    for line in result["lines"]:
        check.ok(
            line["cardTextSpans"] > 0 and line["koSpans"] == 0,
            f"English {kind}: '{line['text']}' still renders through .card-text, "
            "not .effect-text-ko",
            line,
        )


# Hidden Missive's own two-icon Agent box (RECRUIT_ONE_AND_DRAW_IF_
# BENE_GESSERIT_INFLUENCE_TWO, OQ-027): the "troops" icon resolves as its
# own resolve_agent_card_effect action, condition suffix included.
# tests/server/test_sessions.py
# test_serialized_actions_carry_the_agent_box_icon_detail_ko pins this exact
# (detail, detail_ko) pair against the live server pipeline; this script
# only checks how the DOM renders it — the same "no real game decision
# needed" approach the Contract/Conflict/personal-card checks above use,
# via a synthetic action object describeAction() (render.js) accepts the
# same shape a live legal action's own serialization does.
RESOLUTION_ACTION = {
    "action_id": "resolve_agent_card_effect",
    "arguments": {"effect": "troops"},
    "detail": "Recruit 1 troop (at 2 Bene Gesserit Influence)",
    "detail_ko": "{troop:1} ({influence_bene_gesserit:2}일 때)",
}

ROW_JS = """(action) => {
  const box = document.createElement("span");
  box.appendChild(describeAction(action));
  return {
    text: box.textContent,
    icons: box.querySelectorAll("img, svg, .icon-text").length,
    koSpans: box.querySelectorAll(".effect-text-ko").length,
    cardTextSpans: box.querySelectorAll(".card-text").length,
  };
}"""


def check_resolution_row_korean(page) -> None:
    """The Agent-box icon's legal-action row (``describeAction()``,
    ``render.js`` :1262 — the same function a real row in the turn panel
    calls) reads the synthetic action's ``detail_ko`` in Korean."""

    check_icon_parity(
        page,
        "resolution row",
        "detail",
        RESOLUTION_ACTION["detail"],
        RESOLUTION_ACTION["detail_ko"],
    )
    shown = page.evaluate(ROW_JS, RESOLUTION_ACTION)
    check.ok(
        shown["koSpans"] > 0 and shown["cardTextSpans"] == 0,
        "Korean resolution row: renders through .effect-text-ko, not .card-text",
        shown,
    )
    check.ok(
        "{" not in shown["text"] and "}" not in shown["text"],
        "Korean resolution row: no leftover {placeholder}",
        shown,
    )
    _check_no_stray_latin("Korean resolution row", shown["text"], [])
    check.ok(
        shown["icons"] >= 2,
        "Korean resolution row: draws both the troop and the Influence icon",
        shown,
    )


def check_resolution_row_english(page) -> None:
    shown = page.evaluate(ROW_JS, RESOLUTION_ACTION)
    expected = page.evaluate(ICONIZE_TEXT_JS, RESOLUTION_ACTION["detail"])
    check.ok(
        shown["cardTextSpans"] > 0
        and shown["koSpans"] == 0
        and expected in shown["text"],
        "English resolution row: still .card-text, matching an independent "
        "iconize() reading",
        (shown, expected),
    )


# A synthetic play_intrigue action for each of INTRIGUE_ID's two options
# (Step K3): describeAction() resolves state.catalog.intrigue[card_id]
# itself from the live catalog (no server round trip needed), the same
# "no real game decision needed" shortcut RESOLUTION_ACTION uses above.
# intrigue_options.py drives an actual dual-option decision end to end (and
# checks English); this only adds the Korean row check that needs no real
# decision.
PLAY_INTRIGUE_ACTIONS = [
    {
        "action_id": "play_intrigue",
        "arguments": {"card_id": INTRIGUE_ID, "option": option},
        "index": option,
    }
    for option in (0, 1)
]


def check_play_intrigue_rows_korean(page) -> None:
    """Both of ``INTRIGUE_ID``'s option rows read their own Korean option
    line (``core.js`` ``intrigueOptionBody()``), not each other's and not
    the bare numeric index."""

    entry = page.evaluate("(id) => lookup(id)", INTRIGUE_ID)
    check.ok(entry is not None, f"{INTRIGUE_ID} resolves via lookup()")
    if entry is None:
        return
    shown_rows = []
    for action in PLAY_INTRIGUE_ACTIONS:
        option = action["arguments"]["option"]
        shown = page.evaluate(ROW_JS, action)
        shown_rows.append(shown["text"])
        check.ok(
            shown["koSpans"] > 0 and shown["cardTextSpans"] == 0,
            f"Korean play_intrigue row (option {option}): renders through "
            ".effect-text-ko, not .card-text",
            shown,
        )
        check.ok(
            "{" not in shown["text"] and "}" not in shown["text"],
            f"Korean play_intrigue row (option {option}): no leftover "
            "{placeholder}",
            shown,
        )
        check.ok(
            "선택지:" not in shown["text"] and "Option:" not in shown["text"],
            f"Korean play_intrigue row (option {option}): not the bare "
            "numeric index",
            shown,
        )
        check.ok(
            entry["name"] in shown["text"],
            f"Korean play_intrigue row (option {option}): still names the card",
            shown,
        )
        _check_no_stray_latin(
            f"Korean play_intrigue row (option {option})", shown["text"], []
        )
    check.ok(
        shown_rows[0] != shown_rows[1],
        "Korean play_intrigue rows: the two options read differently",
        shown_rows,
    )


def check_play_intrigue_rows_english(page) -> None:
    for action in PLAY_INTRIGUE_ACTIONS:
        option = action["arguments"]["option"]
        shown = page.evaluate(ROW_JS, action)
        check.ok(
            shown["cardTextSpans"] > 0 and shown["koSpans"] == 0,
            f"English play_intrigue row (option {option}): still .card-text, "
            "not .effect-text-ko",
            shown,
        )


def main() -> None:
    # E2E_SHOTS_DIR: where the screenshots below go (no default committed
    # here, since a session scratchpad path is not portable); falls back to
    # a scratch tempdir so the script still runs standalone.
    default_shots = tempfile.mkdtemp(prefix="dune-e2e-shots-")
    shots = Path(os.environ.get("E2E_SHOTS_DIR") or default_shots)
    shots.mkdir(parents=True, exist_ok=True)
    with server() as (base, _log), chrome() as browser:
        context, page, rec = open_context(browser, "effect-text", VIEWPORT)
        create_game(page, base, humans=(0,))
        page.wait_for_selector("#game-screen:not([hidden])")
        settled(page)
        space_names = page.evaluate(SPACE_NAMES_JS)

        print(f"[1] Korean: {CONTRACT_ID} (Contract) popover")
        check_korean(page, "Contract", CONTRACT_ID, space_names)
        _wait_for_popover_images(page)
        page.screenshot(path=str(shots / "effect_text_contract_ko.png"))

        print(f"[2] Korean: {CONFLICT_ID} (Conflict) popover")
        check_korean(page, "Conflict", CONFLICT_ID, space_names)
        _wait_for_popover_images(page)
        page.screenshot(path=str(shots / "effect_text_conflict_ko.png"))

        print(f"[2b] Korean: {PERSONAL_CARD_ID} (personal card) popover (Step K2)")
        check_korean(page, "Card", PERSONAL_CARD_ID, space_names)
        _wait_for_popover_images(page)
        page.screenshot(path=str(shots / "effect_text_card_ko.png"))

        print(f"[2b2] Korean: {INTRIGUE_ID} (Intrigue) popover (Step K3)")
        check_korean(page, "Intrigue", INTRIGUE_ID, space_names)
        _wait_for_popover_images(page)
        page.screenshot(path=str(shots / "effect_text_intrigue_ko.png"))

        print("[2c] Korean: the Agent-box icon's resolution row (Step K2)")
        check_resolution_row_korean(page)
        row_shot = page.evaluate(
            """(action) => {
              const box = document.getElementById("card-popover");
              box.classList.add("hover");
              box.textContent = "";
              const line = document.createElement("div");
              line.className = "popover-line";
              line.appendChild(describeAction(action));
              box.appendChild(line);
              return true;
            }""",
            RESOLUTION_ACTION,
        )
        if row_shot:
            _wait_for_popover_images(page)
            page.screenshot(path=str(shots / "effect_text_resolution_row_ko.png"))

        print("[2d] Korean: icon parity across every catalog card (2026-09-25 review)")
        check_all_cards_icon_parity(page)

        print("[2e] Korean: icon parity across every Intrigue card (Step K3)")
        check_all_intrigue_icon_parity(page)

        print(f"[2f] Korean: {INTRIGUE_ID}'s two play_intrigue option rows (Step K3)")
        check_play_intrigue_rows_korean(page)
        row_shot = page.evaluate(
            """(actions) => {
              const box = document.getElementById("card-popover");
              box.classList.add("hover");
              box.textContent = "";
              for (const action of actions) {
                const line = document.createElement("div");
                line.className = "popover-line";
                line.appendChild(describeAction(action));
                box.appendChild(line);
              }
              return true;
            }""",
            PLAY_INTRIGUE_ACTIONS,
        )
        if row_shot:
            _wait_for_popover_images(page)
            page.screenshot(path=str(shots / "effect_text_play_intrigue_rows_ko.png"))

        print("[3] English: the same popovers and rows are unchanged")
        page.evaluate("setLanguage('en')")
        settled(page)
        check_english(page, "Contract", CONTRACT_ID)
        check_english(page, "Conflict", CONFLICT_ID)
        check_english(page, "Card", PERSONAL_CARD_ID)
        check_english(page, "Intrigue", INTRIGUE_ID)
        check_resolution_row_english(page)
        check_play_intrigue_rows_english(page)
        # ... and match iconize(condition/reward) computed independently.
        contract = page.evaluate("(id) => lookup(id)", CONTRACT_ID)
        expected_condition = page.evaluate(ICONIZE_TEXT_JS, contract["condition"])
        expected_reward = page.evaluate(ICONIZE_TEXT_JS, contract["reward"])
        shown = page.evaluate(OPEN_POPOVER_JS, CONTRACT_ID)
        texts = [line["text"] for line in shown["lines"]]
        check.ok(
            any(expected_condition in t for t in texts)
            and any(expected_reward in t for t in texts),
            "English Contract: lines match an independent iconize() reading",
            (expected_condition, expected_reward, texts),
        )
        _wait_for_popover_images(page)
        page.screenshot(path=str(shots / "effect_text_contract_en.png"))

        check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:5])
        context.close()
    check.finish()


if __name__ == "__main__":
    main()
