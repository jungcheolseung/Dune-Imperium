"""The action log's card pictures: every card of a turn, each with why.

Play feedback 2026-10-26: "활동 로그에 사용하거나 획득한 카드 이미지가 일부만
나오는 듯 ... 이미지가 떠있을 때 이게 왜 뜨는 이미지인지(구매했는지,
폐기했는지, 사용했는지) 구분이 안 된달까." A turn card showed its first four
pictures only, so a Tech tile flipped late in a busy Agent turn lost its
picture, and no picture said why it was there.

On a real table (all options, the setup screen's Tech tile ids) a turn card
built from a synthetic group (panels.js turnCard, render.js logTargets):
[1] the reasons follow the events and actions that name each card, in both
    languages: a Tech tile flipped (action and tech_flipped event), a card
    acquired, a card trashed, an Agent card played, an Intrigue card played,
    and a card named by a waiting effect's `printed` argument;
[2] up to eight pictures stand two abreast, the rest as "+N";
[3] a picture whose card no event explains carries no mark; an undone
    step and the market's next Tech tile (tech_revealed) give no picture.
The pictures come from the log entries alone, which the server has already
filtered for this seat, so nothing here reads another seat's hidden cards.
"""

from __future__ import annotations

from common import Check, chrome, open_context, server
from open_mode import create_game

check = Check()

GROUP_JS = """({ids, undone, market}) => {
  const [agent, acquired, trashed, tech, intrigue, printed, ...rest] = ids;
  const action = (action_id, args, events) => ({type: 'action', actor: 0, index: 1,
    action_id, arguments: args, events, undone: false});
  const entries = [
    action('choose_agent_card', {card_id: agent},
      [{kind: 'agent_card_picked', payload: {card_id: agent, player: 0}}]),
    action('acquire', {printed: acquired, source: 'purchase'},
      [{kind: 'card_acquired', payload: {card_id: acquired, player: 0}}]),
    action('trash_optional_card',
      {card_id: trashed, printed: agent, source: 'agent_card'},
      [{kind: 'card_trashed', payload: {card_id: trashed, player: 0}}]),
    action('flip', {printed: tech, source: 'tech'},
      [{kind: 'tech_flipped', payload: {tech_id: tech, player: 0}},
       // The stack's next tile, face up after a purchase: the market's.
       {kind: 'tech_revealed', payload: {stack: 0, tech_id: market}}]),
    // A purchase taken back named nothing that stayed.
    {...action('acquire', {printed: undone, source: 'purchase'},
      [{kind: 'card_acquired', payload: {card_id: undone, player: 0}}]), undone: true},
    action('play_intrigue', {card_id: intrigue, option: 0},
      [{kind: 'intrigue_played', payload: {card_id: intrigue, player: 0}}]),
    action('gain', {icon: 'resources', printed: printed, source: 'reveal_card'}, []),
    ...rest.map((id) => action('card_returned', {}, [
      {kind: 'card_returned_to_hand', payload: {card_id: id, player: 0}}])),
  ];
  const group = {actor: 0, entries};
  const card = turnCard(group, Infinity);
  const row = card.querySelector('.turn-cards');
  return {
    marks: [...row.querySelectorAll('.vcard')].map((v) => ({
      id: v.dataset.instance,
      mark: (v.querySelector('.vcard-badge') || {}).textContent || null,
    })),
    many: row.classList.contains('many'),
    more: (row.querySelector('.turn-cards-more') || {}).textContent || null,
  };
}"""

IDS_JS = """() => {
  const c = state.catalog;
  const cards = Object.keys(c.cards).filter((id) => c.cards[id].image).slice(0, 12);
  return {
    cards,
    tech: Object.keys(c.tech)[0],
    market: Object.keys(c.tech)[1],
    intrigue: Object.keys(c.intrigue)[0],
  };
}"""

MARKS = {
    "ko": ["사용", "획득", "폐기", "뒤집기", "사용", "사용"],
    "en": ["Used", "Acquired", "Trashed", "Flipped", "Used", "Used"],
}


def main() -> None:
    with server() as (base, _log), chrome() as browser:
        _, page, rec = open_context(browser, "log-card-reasons")
        create_game(page, base, humans=(0,), options=None)
        found = page.evaluate(IDS_JS)
        cards = found["cards"]
        ids = [cards[0], cards[1], cards[2], found["tech"], found["intrigue"], cards[3],
               *cards[4:9]]
        extra = {"undone": cards[10], "market": found["market"]}
        for lang in ("ko", "en"):
            page.evaluate("lang => setLanguage(lang)", lang)
            result = page.evaluate(GROUP_JS, {"ids": ids, **extra})
            marks = result["marks"]
            print(f"[{lang}]")
            check.ok(
                [m["mark"] for m in marks[:6]] == MARKS[lang],
                f"{lang}: each picture says why the turn names it",
                marks[:6],
            )
            check.ok(
                len(marks) == 8 and result["many"] and result["more"] is not None
                and "3" in result["more"],
                f"{lang}: eight pictures two abreast, the other three as +3",
                result,
            )
            check.ok(
                all(m["mark"] is None for m in marks[6:]),
                f"{lang}: a card no event explains carries no mark",
                marks[6:],
            )
            shown = {m["id"] for m in marks}
            check.ok(
                extra["undone"] not in shown and extra["market"] not in shown,
                f"{lang}: no picture for an undone step or the market's next Tech tile",
                (extra, sorted(shown)),
            )
        check.ok(not rec.js_errors, "no JS errors", rec.js_errors[:3])
    check.finish()


if __name__ == "__main__":
    main()
