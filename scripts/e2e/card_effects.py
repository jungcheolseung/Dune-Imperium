"""Card-use cues: real human/AI turns, Plot/Combat Intrigue and lifecycle.

Checks the queue against independently selected public log events, including
several AI plays in one snapshot and a local table that switches human seats.
Also checks redacted draws/secret picks, undo, reload, language, fallback art,
reduced motion, click-through and AI replay playback versus manual seeks.
"""

from __future__ import annotations

import os
import tempfile

from common import Check, chrome, open_context, server
from open_mode import create_game, settled

check = Check()
SHOTS = os.environ.get("E2E_SHOTS_DIR") or tempfile.mkdtemp(
    prefix="dune-e2e-card-effects-"
)

PENDING = """() => [playEffects.current, ...playEffects.queue].filter(Boolean)
  .map((c) => ({index: c.index, card: c.cardId, seat: c.seat}))"""

EXPECTED = """(from) => state.log.entries.slice(from).flatMap((entry) =>
  entry.undone ? [] : entry.events.flatMap((event) =>
    ['agent_placed', 'turn_start_card_played', 'card_grafted',
     'intrigue_played', 'navigation_card_played'].includes(event.kind)
      ? [{index: entry.index, card: event.payload.card_id,
          seat: event.payload.player}] : []))"""

CHOOSE = """() => {
  const rows = state.actions.actions;
  const intrigue = rows.find((a) => a.action_id === 'play_intrigue');
  if (intrigue) return intrigue.index;
  const secrets = rows.find((a) => a.action_id === 'agent_turn'
    && a.arguments.space_id === 'secrets');
  return (secrets || rows[0]).index;
}"""


def freeze(page) -> None:
    page.evaluate("clearTimeout(playEffects.timer)")


def live(page, base: str) -> None:
    create_game(page, base, humans=(0, 1), seed=20260917)
    check.ok(page.is_hidden("#play-effects"), "joining establishes a quiet baseline")
    people: set[int] = set()
    kinds: set[str] = set()
    saw_batch = False
    for _ in range(1800):
        assert settled(page, 20)
        if page.evaluate("state.summary.finished"):
            break
        freeze(page)
        before = page.evaluate("state.log.count")
        pending = page.evaluate(PENDING)
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
        else:
            page.evaluate("applyAction", page.evaluate(CHOOSE))
        assert settled(page, 20)
        freeze(page)
        arrived = page.evaluate(EXPECTED, before)
        actual = page.evaluate(PENDING)
        # There are no undos in this walk; all newly arrived plays must remain
        # in order after the previous pending ones, even across a seat switch.
        if actual != pending + arrived:
            check.ok(
                False,
                "the queue preserves every new human/AI play",
                (actual, pending, arrived),
            )
            break
        people.update(c["seat"] for c in arrived)
        kinds.update(
            page.evaluate(
                """(from) => state.log.entries.slice(from)
          .flatMap((e) => e.events.filter((v) => v.kind === 'intrigue_played')
          .map((v) => entryOf(v.payload.card_id, 'intrigue')
            .text[v.payload.option || 0].split(' — ')[0].toLowerCase()))""",
                before,
            )
        )
        saw_batch |= len(arrived) > 1
        if len(people) == 4 and {"plot", "combat"} <= kinds and saw_batch:
            break
    check.ok(
        people == {0, 1, 2, 3},
        "both human seats and both AI seats emit card-use cues",
        people,
    )
    check.ok(
        {"plot", "combat"} <= kinds,
        "Plot and Combat Intrigue plays are included",
        kinds,
    )
    check.ok(saw_batch, "multiple plays arriving together remain ordered")
    before = page.evaluate(PENDING)
    page.evaluate("render(); render({foreign:true})")
    check.ok(page.evaluate(PENDING) == before, "ordinary renders never duplicate cues")
    # Show a real Combat Intrigue from the queue for visual checks.
    page.evaluate("""() => {
      const i = playEffects.queue.findIndex((c) => c.kind === 'intrigue'
        && c.timing === 'combat');
      playEffects.queue = playEffects.queue.slice(i);
      nextPlayEffect(); clearTimeout(playEffects.timer);
    }""")
    for lang, width in (("ko", 1600), ("en", 1366)):
        page.set_viewport_size({"width": width, "height": 900})
        page.evaluate("setLanguage", lang)
        page.wait_for_function("""() => {
          const img = el('play-effects').querySelector('img');
          return img && img.complete && img.naturalWidth > 0;
        }""")
        info = page.evaluate("""() => {
          const cue = playEffects.current, entry = entryOf(cue.cardId, cue.kind);
          const box = el('play-effects'), rect = box.getBoundingClientRect();
          return {image: box.querySelector('img').getAttribute('src') === entry.image,
            name: box.innerText.includes(entry.name),
            type: box.innerText.includes(t('effects.combat_intrigue')),
            fits: rect.left >= 0 && rect.right <= innerWidth
              && rect.bottom <= innerHeight,
            through: getComputedStyle(box).pointerEvents === 'none'};
        }""")
        check.ok(
            all(info.values()),
            f"Combat card image, caption, click-through and fit ({lang})",
            info,
        )
        page.locator(".play-effect").evaluate(
            "async (n) => Promise.all(n.getAnimations().map((a) => a.finished))"
        )
        page.screenshot(path=f"{SHOTS}/combat_card_{lang}_{width}.png")
    page.emulate_media(reduced_motion="reduce")
    check.ok(
        page.locator(".play-effect").evaluate(
            "(n) => getComputedStyle(n).animationName === 'none'"
        ),
        "reduced motion keeps the cue without moving it",
    )
    fallback = page.evaluate("""() => {
      const entry = entryOf(playEffects.current.cardId, playEffects.current.kind);
      const image = entry.image;
      try {
        entry.image = null; drawPlayEffect();
        return !el('play-effects').querySelector('img')
          && el('play-effects').querySelector('.textcard').innerText === entry.name;
      } finally { entry.image = image; drawPlayEffect(); }
    }""")
    check.ok(fallback, "missing art still names the played card")
    page.reload()
    page.wait_for_function("state.view !== null && refreshFlight === null")
    check.ok(
        page.is_hidden("#play-effects") and page.evaluate(PENDING) == [],
        "reload never replays old card uses",
    )
    page.evaluate("leaveGame()")
    check.ok(page.is_hidden("#play-effects"), "leaving clears cues and timers")


def boundaries(page, base: str) -> None:
    create_game(page, base, humans=(0, 1), seed=0)
    while page.evaluate("state.view.decision_kind === 'leader_draft'"):
        if page.evaluate("state.summary.confirmation === state.viewSeat"):
            page.evaluate("confirmTurn()")
        else:
            page.evaluate("applyAction", page.evaluate(CHOOSE))
        assert settled(page)
    # Explicit fixtures exercise a private draw and sealed choice with real
    # catalog ids. A scan of arbitrary payloads would wrongly show both.
    fixtures = page.evaluate("""() => {
      const id = state.view.private.hand[0];
      const hidden = [{index: 0, type: 'action', actor: 1, events: [
        {kind: 'personal_card_drawn', payload: {card_id: id, player: 1}},
        {kind: 'scouts_secret_picked', payload: {card_id: id, player: 1}}]}];
      const undone = [{index: 1, type: 'action', undone: true, events: [
        {kind: 'agent_placed', payload: {card_id: id, player: 0}}]}];
      return cardPlayCues(hidden).length === 0 && cardPlayCues(undone).length === 0;
    }""")
    check.ok(fixtures, "private draws, secret choices and undone plays emit no cue")
    mixed = page.evaluate("""() => {
      const labels = [0, 1].map((option) => {
        playEffects.current = cardPlayCues([{index: 0, type: 'action', events: [
          {kind: 'intrigue_played', payload: {
            card_id: 'intrigue:contingency_plan:0', player: 0, option}}]}])[0];
        drawPlayEffect();
        return el('play-effects').querySelector('.play-effect-type').innerText;
      });
      clearPlayEffects();
      return labels[0] === t('effects.intrigue')
        && labels[1] === t('effects.combat_intrigue');
    }""")
    check.ok(mixed, "a dual Plot/Combat card names the option actually played")
    # The first play can be undone before any effects draw hidden information.
    page.evaluate("applyAction", page.evaluate(CHOOSE))
    assert settled(page)
    freeze(page)
    check.ok(page.is_visible("#play-effects"), "a human Agent card floats immediately")
    if page.evaluate("state.summary.undo.some((u) => u.seat === state.viewSeat)"):
        page.evaluate("submitUndo(state.viewSeat, 1)")
        assert settled(page)
        check.ok(
            page.is_hidden("#play-effects") and page.evaluate(PENDING) == [],
            "undo removes the active cue and its pending plays",
        )
    else:
        raise AssertionError("the scenario must reach an undoable Agent play")
    page.evaluate("applyAction", page.evaluate(CHOOSE))
    assert settled(page)
    check.ok(page.is_visible("#play-effects"), "replaying after undo emits a fresh cue")
    page.wait_for_function("el('play-effects').hidden", timeout=5000)
    check.ok(
        page.evaluate(PENDING) == [], "a cue expires without another server update"
    )


def replay(page, base: str) -> None:
    create_game(page, base, humans=(), seed=11)
    page.wait_for_function("state.review !== null && playback.playing")
    page.wait_for_selector("#play-effects:not([hidden])", timeout=20000)
    check.ok(
        page.evaluate("playEffects.current !== null"),
        "AI-only playback shows played cards",
    )
    page.evaluate("stopPlayback()")
    check.ok(page.is_hidden("#play-effects"), "pausing playback clears pending effects")
    page.evaluate("reviewSeek(state.review.meta.step_count)")
    page.wait_for_function("state.review.cursor === state.review.meta.step_count")
    check.ok(
        page.is_hidden("#play-effects"), "manual review seeks do not replay past cues"
    )


def main() -> None:
    with server() as (base, _), chrome() as browser:
        _, page, _ = open_context(browser, "card-effects")
        live(page, base)
        boundaries(page, base)
        replay(page, base)
    print(f"screenshots in {SHOTS}")
    check.finish()


if __name__ == "__main__":
    main()
