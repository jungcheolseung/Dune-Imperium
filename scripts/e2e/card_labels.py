"""A card line's box label stays words, not an icon (2026-09-25).

`iconize()` (render.js) turns the word "Agent" into the Agent icon, which is
right inside an effect ("Recall an Agent") but not for the label that opens a
personal card's Agent-box line ("Agent: Place a Spy …", display/cards.py), a
Tech tile's "Agent Turn: …" or a card's "On discard: …". Drawn as an icon the
label read like part of the card title above it: a player saw "Double Agent"
with "[Agent]:" under it and took the card's own name for iconized. The check
opens the popovers of cards whose lines start with those labels, in both
languages, and asserts each label is a text node while the same word inside
an effect still becomes the icon.

Since Step K2 (2026-09-25) gave personal cards a real ``text_ko`` twin
(``display.cards.personal_card_text_ko``), a "cards" section line with a
Korean twin now renders through the newer ``.effect-text-ko``/``phrase()``
path instead of ``.card-text``/``iconize()`` when the UI is in Korean — a
different code path the English-label bug this script guards against does
not even reach, because ``personal_card_text_ko``'s box-label prefixes
("에이전트 칸:", "버리면:") are hardcoded Korean words, never a
``{agent}``/``{discard}`` icon placeholder ``phrase()`` could turn into a
graphic (``display/cards.py``'s own module docstring says why). The Korean
check below follows whichever path a given entry's line actually takes:
``.effect-text-ko`` with the matching Korean label word when a ``text_ko``
twin exists for that exact line, ``.card-text`` with the English label
otherwise (a section this project hasn't translated yet, e.g. Tech tiles'
"Agent Turn:").
"""

from __future__ import annotations

from common import LAPTOP_VIEWPORT, Check, chrome, open_context, server
from open_mode import create_game, settled

check = Check()

# Korean twin of each English box label this script watches for, keyed by
# the same word FIND_JS captures — display/cards.py's own prefixes.
KOREAN_LABELS = {
    "Agent": "에이전트 칸",
    "On discard": "버리면",
    # Tech tiles' "Agent Turn:" (bloodlines.py/tech display) has no Korean
    # twin yet; left unmapped so the Korean check below falls back to the
    # English-label/.card-text path for it, same as before this change.
}

# Every catalog line that opens with one of the labels, and one effect line
# that says "Agent" mid-sentence (to prove the icon rule still works there).
# ``index`` is the line's position in ``entry.text``, so the Korean check
# can read the same position out of ``entry.text_ko`` when one exists.
FIND_JS = """() => {
  const found = {labels: [], inline: null};
  for (const [section, entries] of Object.entries(state.catalog)) {
    if (!entries || typeof entries !== "object") continue;
    for (const [id, entry] of Object.entries(entries)) {
      const lines = (entry && Array.isArray(entry.text)) ? entry.text : [];
      lines.forEach((line, index) => {
        const label = /^(Agent Turn|Agent|On discard):/.exec(line);
        if (label && !found.labels.some((f) => f.label === label[1])) {
          found.labels.push({section, id, index, label: label[1], line});
        }
        if (!found.inline && !label && /\\bAgents?\\b/.test(line)) {
          found.inline = {section, id, line};
        }
      });
    }
  }
  return found;
}"""

POPOVER_JS = """(args) => {
  const [id, line] = args;
  const entry = lookup(id);
  openPopover(entry, document.querySelector("header h1"));
  const pop = document.getElementById("card-popover");
  const texts = [...pop.querySelectorAll(".card-text")];
  const node = texts.find((t) => t.textContent === iconize(line).textContent)
    || texts[0];
  const first = node ? node.firstChild : null;
  return {
    firstIsText: Boolean(first) && first.nodeType === 3,
    firstText: first && first.nodeType === 3 ? first.textContent : null,
    agentIcons: node ? node.querySelectorAll(".agent-piece-icon, img[alt='Agent'], img[alt='에이전트']").length : 0,
    icons: node ? node.querySelectorAll("img, svg").length : 0,
    text: node ? node.textContent : null,
  };
}"""

# Korean twin of POPOVER_JS: reads entry.text_ko[index] (when it exists)
# and the .effect-text-ko lines instead of .card-text/iconize().
POPOVER_KO_JS = """(args) => {
  const [id, index] = args;
  const entry = lookup(id);
  openPopover(entry, document.querySelector("header h1"));
  const pop = document.getElementById("card-popover");
  const lineKo = entry.text_ko ? entry.text_ko[index] : undefined;
  if (lineKo === undefined) return {hasKoTwin: false};
  const texts = [...pop.querySelectorAll(".effect-text-ko")];
  const node = texts.find((t) => t.textContent === phrase(lineKo).textContent)
    || texts[0];
  const first = node ? node.firstChild : null;
  return {
    hasKoTwin: true,
    firstIsText: Boolean(first) && first.nodeType === 3,
    firstText: first && first.nodeType === 3 ? first.textContent : null,
    text: node ? node.textContent : null,
  };
}"""


def main() -> None:
    with server() as (base, _log), chrome() as browser:
        context, page, rec = open_context(browser, "card-labels", LAPTOP_VIEWPORT)
        create_game(page, base, humans=(0,))
        page.wait_for_selector("#game-screen:not([hidden])")
        settled(page)
        found = page.evaluate(FIND_JS)
        labels = {f["label"] for f in found["labels"]}
        check.ok(
            {"Agent", "Agent Turn", "On discard"} <= labels,
            "the catalog has lines opening with each box label",
            found["labels"],
        )
        check.ok(
            found["inline"] is not None, "and a line with Agent inside an effect", found
        )
        for lang in ("ko", "en"):
            page.evaluate(f"setLanguage('{lang}')")
            settled(page)
            for item in found["labels"]:
                korean_label = KOREAN_LABELS.get(item["label"])
                if lang == "ko" and korean_label is not None:
                    shown_ko = page.evaluate(
                        POPOVER_KO_JS, [item["id"], item["index"]]
                    )
                    if shown_ko["hasKoTwin"]:
                        check.ok(
                            shown_ko["firstIsText"]
                            and (shown_ko["firstText"] or "").startswith(
                                f"{korean_label}:"
                            ),
                            f"{lang}: {item['id']} opens its .effect-text-ko line "
                            f"with the words '{korean_label}:'",
                            shown_ko,
                        )
                        continue
                shown = page.evaluate(POPOVER_JS, [item["id"], item["line"]])
                check.ok(
                    shown["firstIsText"]
                    and (shown["firstText"] or "").startswith(f"{item['label']}:"),
                    f"{lang}: {item['id']} opens its line with the words '{item['label']}:'",
                    shown,
                )
            if found["inline"]:
                shown = page.evaluate(
                    POPOVER_JS, [found["inline"]["id"], found["inline"]["line"]]
                )
                check.ok(
                    shown["icons"] > 0,
                    f"{lang}: Agent inside an effect is still drawn as an icon",
                    shown,
                )
        check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
        context.close()
    check.finish()


if __name__ == "__main__":
    main()
