"""E2E for the Korean effect-text feature, Step K1 (2026-09-25).

Feature decided 2026-09-25: the effect text the engine *generates* (as
opposed to a card's printed wording, which stays English in both languages)
gets a Korean version in the Korean UI. Step K1 wires the client path and
fills in the first generator (``display.structs``'s Contract condition/
reward and Conflict reward text, ``server/catalog.py``'s ``condition_ko``/
``reward_ko``/``rewards_ko``); later steps grow the same wiring to cards,
Intrigue, spaces and Leaders.

This opens one Contract's and one Conflict's popover directly (``lookup()``
+ ``openPopover()``, the way ``card_labels.py`` does, so it needs no real
game decision to reach them) and checks, in Korean:

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

And, in English, that the same lines are pixel-for-pixel what they always
were: still ``.card-text``, no ``.effect-text-ko`` anywhere, matching
``iconize(entry.condition)``/``iconize(entry.reward)`` computed
independently of the popover under test.

Screenshots of both popovers, Korean, 1440x900, go beside this script's
results for a human to look at.
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
    fields = [result["condition_ko"], result["reward_ko"], *rewards_ko]
    raw = "|".join(filter(None, fields))
    check.ok(
        "{" in raw, f"Korean {kind}: the catalog field itself uses placeholders", raw
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

        print("[3] English: the same two popovers are unchanged")
        page.evaluate("setLanguage('en')")
        settled(page)
        check_english(page, "Contract", CONTRACT_ID)
        check_english(page, "Conflict", CONFLICT_ID)
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
