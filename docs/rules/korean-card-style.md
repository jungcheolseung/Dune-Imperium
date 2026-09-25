# Korean card-print style: phrase table and style guide

Source: 30 Korean card scans read directly, each beside its English scan,
from the assets checkout (`Dune-Imperium-assets/cards/{ko,en}/...`,
2026-09-25). The generated Korean effect text in `src/dune_imperium/display/`
(`*_ko` twins) follows this guide; its game terms come only from
[`glossary-ko.md`](glossary-ko.md).

Spread: 12 Imperium cards (Agent-box + Reveal effects, Uprising +
Bloodlines), 8 Intrigue cards covering all three timings (Plot/Combat/
Endgame, including dual- and triple-timing cards), 3 Contracts, 2 Conflict
cards, 3 Tech tiles, 2 Navigation cards. Game terms below match
`docs/rules/glossary-ko.md`; nothing here introduces a new term outside
that glossary.

## Phrase table

| EN phrase | KO print phrase | Card |
| --- | --- | --- |
| "If you have two or more Spies on the board:" | "게임판에 당신의 스파이가 둘 이상 있다면:" | Bene Gesserit Operative |
| "If you have completed two or more contracts:" | "당신이 계약을 둘 이상 완수했다면:" | Cargo Runner |
| "If you have completed four or more contracts:" | "당신이 계약을 넷 이상 완수했다면:" | Cargo Runner / CHOAM Profits |
| "Alliance:" (header before an icon-only effect) | "동맹:" | Branching Path |
| "If you recalled a Spy this turn:" | "이번 차례에 스파이를 소환했다면:" | Imperial Spymaster / Spy Drones |
| "If you sent an Agent to a Maker board space this turn:" | "이번 차례에 메이커 게임판 장소로 에이전트를 보냈다면:" | Fedaykin Stilltent |
| "If you discarded a Spacing Guild card:" | "우주 항행 길드 카드를 버렸다면:" | Guild Spy / Guild Envoy / Arrakis Observer |
| "If you discarded a [Faction] card:" | "[팩션] 카드를 버렸다면:" | (general form, above) |
| "—AND—" | "—그리고—" | Arrakis Observer / Spy Drones |
| "—OR—" | "—또는—" | Backed by CHOAM / Navigation Card 1 |
| "You may trash a card from your hand." | "핸드에 있는 카드 1장 폐기 가능" | Elite Forces |
| "If you trash an Emperor card:" | "황제 카드를 폐기했다면:" | Elite Forces |
| "2 Influence:" / "3 Influence:" | "영향력 2:" / "영향력 3:" | Command Center / Depart For Arrakis |
| "Retreat two troops" | "병력 둘 후퇴" | Command Center |
| "Retreat one or two of your troops" | "당신의 병력 1 또는 2 후퇴" | Reach Agreement / Battlefield Research |
| "Retreat three of your troops" | "당신의 병력 3 후퇴" | Withdrawal Agreement |
| "PLOT" / "COMBAT" / "ENDGAME" (timing header) | "음모" / "전투" / "종료 단계" | all Intrigue cards |
| "COMBAT / ENDGAME" (dual timing) | "전투 / 종료 단계" | Battlefield Research |
| "PLOT / COMBAT" (dual timing) | "음모 / 전투" | Backed by CHOAM |
| "If you have completed two or more contracts:" header banner "—OR—" between a Plot and Combat option | "—또는—" | Backed by CHOAM |
| "If you gained spice this turn:" | "이번 차례에 당신이 스파이스를 얻었다면:" | Leverage |
| "If you have three or more Tech tiles:" | "당신이 가진 기술 타일이 3개 이상이면:" | Battlefield Research |
| "The card you play this turn has the [Agent icon] icon." | "이번 차례에 당신이 플레이하는 카드는 [아이콘] 아이콘 보유." | Emperor's Invitation |
| "To acquire this, you must trash one of your Spies from the board." | "이 타일을 획득하려면, 게임판에서 당신의 스파이 하나를 폐기해야 함." | Advanced Data Analysis (Tech tile) |
| "(Return it to the box.)" | "(게임 상자에 다시 넣음.)" | Advanced Data Analysis |
| "You may look at the top card of your deck at any time." | "언제든지 당신의 카드덱 맨 위 카드 1장 확인 가능." | Glowglobes (Tech tile) |
| "Gain 1 Influence with a different Faction where you have 2+ Influence." | "당신의 영향력이 2 이상인 다른 팩션 하나에서 영향력 1 얻음." | Navigation Card 1 |
| "If you trash a card that costs 1 or more:" | "비용이 1 이상인 카드를 폐기했다면:" | Navigation Card 5 |
| "1st" / "2nd" / "3rd" (Conflict reward rows) | "1등" / "2등" / "3등" | Battle for Arrakeen / Siege of Arrakeen |
| "HARVEST" + "4+" (Contract header + threshold) | "채취" + "4+" | Harvest 4+ (4 Solari) |

## Style guide for writing new Korean effect lines

Grounded only in the 30 cards above and `docs/rules/glossary-ko.md`; where
the sample didn't cover a construction, that's flagged as open below
rather than invented.

**1. Conditions ("if").** The workhorse is `[조건절]-다면:`, always ending
in a colon before the reward: `있다면:`, `완수했다면:`, `얻었다면:`,
`보냈다면:`, `소환했다면:`, `폐기했다면:`, `버렸다면:`. When the condition
is a bare threshold with no verb (a copula, not an action — "if you have
three or more Tech tiles"), it contracts to `-이면:` instead of `-다면:`
(`3개 이상이면:`, not `3개 이상 있다면:` — both are attested in the wider
game, but *this* card's phrasing dropped the verb). Use `-다면` when the
condition names an action (완수하다, 얻다, 보내다, 소환하다, 폐기하다,
버리다, 있다); use `-(이)면` only when the condition is a bare
noun/threshold with the copula.

The rulebook's own "whenever" pattern (a repeating trigger, not a one-shot
condition) is different and wasn't in this card sample: Gather
Intelligence — "정보 수집: 당신이 게임판 장소에 에이전트를 보낼 때마다…"
(`docs/rules/glossary-ko.md`, `[Main p. 11]`) uses `-(ㄹ/을) 때마다`
("whenever/every time you..."), not `-다면`. Reserve `때마다` for a
recurring trigger and `-다면`/`-(이)면` for a one-time reveal-turn
condition; this project has no printed-card "whenever" example yet, so
flag any new one in `docs/rules/open-questions.md` before inventing the
phrasing.

**2. Word order: time/location fronts, verb ends the clause.** Korean
moves the "this turn" / "on the board" phrase to the FRONT of the
sentence, opposite of English's trailing position:
- EN "If you have two or more Spies **on the board**:" → KO "**게임판에**
  당신의 스파이가 둘 이상 있다면:" (board-location first).
- EN "If you recalled a Spy **this turn**:" → KO "**이번 차례에** 스파이를
  소환했다면:" (turn-phrase first).
- EN "If you sent an Agent to a Maker board space **this turn**:" → KO
  "**이번 차례에** 메이커 게임판 장소로 에이전트를 보냈다면:".

Standing order inside the clause is then: [time/location] → [subject, if
kept] → [object] → [verb-conditional]:. E.g. "이번 차례에 당신이
스파이스를 얻었다면" = this-turn / you / spice-OBJ / gained-if.

**3. Subject drop.** "당신이"/"당신의" (you/your) is often dropped when the
actor is unambiguous (효과 is always about the card's own owner):
"황제 카드를 폐기했다면:" (Elite Forces, no 당신이), "우주 항행 길드
카드를 버렸다면:" (Arrakis Observer, no 당신이). But it's just as often
kept: "당신이 계약을... 완수했다면:" (CHOAM Profits), "이번 차례에
당신이 스파이스를 얻었다면:" (Leverage). Treat it as optional/terse-style,
not a hard rule — drop it when the line is already unambiguous and short,
keep it when the sentence has multiple nouns and dropping it would read
ambiguously.

**4. "Term N:" reverses to "N Term" → put the term BEFORE the number.**
This is the one clean, consistently-observed reordering: "2 Influence:" →
"영향력 2:", "3 Influence:" → "영향력 3:" (Command Center, Depart For
Arrakis). Apply this to any `[Term] [count]:` construction in Korean:
term word first, digit after, colon last.

**5. Numerals: digits by default; native-Korean numerals ("하나", "둘",
"셋", "넷"...) appear but aren't universal.** The print is inconsistent
across cards/translators, so don't over-fit a single rule:
- Reward/cost numbers next to an icon are always Arabic digits: "영향력
  1 얻음", "1", "2", "4" on hex/circle icons, "1장" (a card), "3개"
  (Tech tiles) — anything paired with an explicit counter word (장, 개,
  등) or an abstract value (영향력, 비용) takes a digit: "영향력이 2
  이상인", "비용이 1 이상인 카드".
- A bare partitive "one of [a group]" (no counter word, standing in for
  a pronoun) is consistently "하나": "당신의 스파이 하나를 폐기해야 함"
  (Advanced Data Analysis), "다른 팩션 하나에서" (Navigation Card 1).
  Use 하나 for "select/spend one of these," not "1".
- Small counted-noun thresholds ("two or more Spies", "four or more
  contracts") mostly print as native numerals with no counter: "스파이가
  둘 이상", "계약을 넷 이상". But "Retreat three of your troops" printed
  as the digit "병력 3 후퇴", and "Retreat one or two of your troops" as
  "병력 1 또는 2 후퇴" — so troop-retreat counts lean digit. When unsure,
  default to the digit (it matches the official rulebook glossary's own
  examples, e.g. "병력 1을 소집합니다", and is never wrong); reserve a
  native numeral only for the "하나" partitive case above, which is
  unambiguous.

**6. "—OR—" / "—AND—" banners translate literally, dash-word-dash.**
"—OR—" → "—또는—"; "—AND—" → "—그리고—" (this "AND" means "then, also
resolve this," not logical AND — Korean still just says "그리고"). Keep
the em-dash-word-em-dash shape; don't turn it into a sentence connector.

**7. Timing headers.** "PLOT" → "음모", "COMBAT" → "전투", "ENDGAME" →
"종료 단계" (matches `docs/rules/glossary-ko.md`, "Plot / Combat / Endgame
Intrigue" → "음모 / 전투 / 종료 단계 책략 카드"). A dual-timing card joins
them with " / ", same as English: "COMBAT / ENDGAME" → "전투 / 종료 단계".

**8. Ordinal conflict-reward rows.** "1st"/"2nd"/"3rd" → "1등"/"2등"/"3등"
(confirms `docs/rules/glossary-ko.md`'s "first/second/third place" →
"1등 / 2등 / 3등 칸"). Always digit + 등, never spelled out.

**9. Sentence-final register: printed card text favors terse
noun/nominalized endings over full polite verb conjugation.** This is the
clearest register marker separating card print from rulebook prose:
- "확인 가능" not "확인할 수 있습니다" (Glowglobes: "may look at" →
  "noun+가능", not a full "can do" sentence).
- "폐기 가능" not "폐기할 수 있습니다" (Elite Forces).
- "아이콘 보유" not "아이콘을 보유하고 있습니다" (Emperor's Invitation).
- "폐기해야 함" not "폐기해야 합니다" (Advanced Data Analysis: -음
  nominalizer instead of -니다).
- "(게임 상자에 다시 넣음.)" not "...넣습니다." (parenthetical reminder
  text, same -음 nominalizer).

When writing new generated Korean effect lines for
`src/dune_imperium/display/`, prefer these terse nominal endings
(-음/-가능/-보유) over full `-습니다/-ㅂ니다` sentences — that's what reads
as "printed card," not "rulebook paragraph." Conditions still end in the
conjugated `-다면:`/`-(이)면:` from rule 1 (that part does need the verb
form); it's only the non-conditional, standalone declarative lines
(rewards/effects with no colon, and reminder text) that go nominal.

**10. Cost clauses ("in order to X, you must Y").** Tech tile acquisition
cost: "이 타일을 획득하려면, 게임판에서 당신의 스파이 하나를 폐기해야
함." — `[목표]를 획득하려면, [비용절]해야 함` (in-order-to clause with
`-(으)려면`, then the cost, ending in the nominal `-해야 함` from rule 9).

**11. Icons stay inline, mid-sentence, at the same position the
corresponding word would sit in English.** E.g. Emperor's Invitation's
"이번 차례에 당신이 플레이하는 카드는 [Agent-icon] 아이콘 보유." keeps the
icon exactly where "the [X]" sits in the English sentence, immediately
before "아이콘" (icon/의 label word). Arrows (→) are never translated or
replaced — they're printed identically in both languages on every card
checked (Branching Path, Captured Mentat, Guild Spy, Arrakis Observer,
Command Center, Elite Forces, Reach Agreement, Advanced Data Analysis,
Spy Drones, Battle for Arrakeen).

## Open items (not covered by this 30-card sample — verify against a real
card before relying on these)

- No printed-card "whenever" (때마다) trigger was in this sample; only
  the rulebook's Gather Intelligence example (§1 above) is confirmed.
- No explicit "this round" (vs. "this turn") phrase was in this sample —
  only "이번 차례에" (this turn) appeared. If a "this round" line is
  needed, check `docs/rules/glossary-ko.md`'s round/phase table ("1.
  라운드 시작" etc.) before inventing "이번 라운드에".
- Costs paid in resources (e.g. "Pay 3 spice") appeared only as icons on
  these 30 cards, never spelled out as Korean prose with an object
  particle (그 pattern is in the rulebook glossary itself: "병력 1을
  소집합니다" uses -을 뽑기/소집합니다, but no *card* in this sample paid a
  resource cost in words). Use the glossary's rulebook-prose form if a
  resource cost ever needs to be spelled out as text rather than an icon.
