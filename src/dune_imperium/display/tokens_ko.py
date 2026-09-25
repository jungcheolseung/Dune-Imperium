"""Korean text for personal-card enum tokens and automatic Reveal effects.

Korean twin of ``tokens.py`` (feature decided 2026-09-25, Step K2: the effect
text the engine *generates* gets a Korean version; printed card text stays
English). Every table here is keyed by the exact same enum members as its
``tokens.py`` counterpart, so ``set(map) == set(EnumClass)`` catches a
missing entry the same way the English module's own tests do.

Word choice follows only ``docs/rules/glossary-ko.md`` (game terms) or
ordinary Korean grammar (connectives, particles, conditions) for everything
else, per that file's "규칙" section — a game term neither source has stays
in English rather than being invented.

**Placeholder policy (icon parity with ``iconize(en)``).** A Korean line
names its icons with ``{term}``/``{term:count}`` (``static/labels.js``
``TERMS``, expanded client-side by ``phrase()``), never a literal English
word for ``iconize()``'s regex to catch. Which form to use follows what the
matching English line actually draws through ``render.js``'s ``ICON_RULES``,
not just whether a ``TERMS`` row happens to exist for the concept:

- A resource/count pair whose English wording has the number **directly**
  adjacent to the keyword (``"Gain 2 spice"``, ``"Recruit 1 troop"``,
  ``"Draw 2 Intrigue cards"``, ``"+3 swords"``, faction ``"Influence"`` with
  the count right before it) draws a *counted* icon in English, so the
  Korean twin uses ``{term:count}``. ``ICON_RULES`` drops the verb
  ("Gain"/"Recruit"/"Draw"/"Pay") when it matches, so no separate Korean
  verb is written either — the icon already carries it.
- ``Trash``/``Discard`` have **no counted rule at all** in ``ICON_RULES``
  (only the bare word matches); a numbered Korean icon here would be a
  render-parity regression, so these are always bare ``{trash}``/
  ``{discard}`` with the count written as a plain "N장" beside the noun
  ("카드 2장 {discard}"), mirroring ``display/structs.py``'s
  ``_spy_placed_text_ko``/``_recall_agent_text_ko`` precedent for the same
  reason (Spy/Agent recall icons are likewise always bare).
- ``Contract`` is *always* bare too — ``ICON_RULES`` has no counted
  "N Contracts" rule, ever.
- A threshold ("N or more X") never has the count directly adjacent to the
  keyword in English (the words "or more" sit in between), so English draws
  a *bare* icon there and leaves the number as plain trailing text; the
  Korean twin does the same (bare ``{term}`` + a plain digit/native numeral
  near "이상"). "2 or more/4 or more Contracts" specifically reuses the
  native numerals 둘/넷 ``cardstyle.md`` verified on a real card (Cargo
  Runner / CHOAM Profits, "계약을 둘/넷 이상 완수했다면:"); every other
  threshold defaults to a digit, per that same file's rule 5.
- "trash an Intrigue card" (singular, this *exact* adjacency) matches
  ``ICON_RULES``' own combined ``trash_intrigue`` rule, not two separate
  icons — the Korean twin uses the bare ``{trash_intrigue}`` term for that
  specific phrasing, and only that one.
- A ``TERMS`` row with ``icon: null`` (Research, Tleilaxu, Graft, Tech
  tile, Command, Combat, Commander, Alliance, Conflict, garrison, Imperium
  Row, Reserve, Leader, …) always renders as a plain word client-side
  (``termNode()``), so using its placeholder is safe regardless of whether
  ``ICON_RULES`` covers the English word — it can never draw a graphic
  either language doesn't already show.
- A ``TERMS`` row with a *real* icon that ``ICON_RULES`` never matches for
  the English wording in question (bare "Maker" — only "Maker Hooks" has a
  rule — and "specimen", which ``ICON_RULES`` never names at all) is
  written as the plain glossary word instead of the placeholder, so Korean
  never draws a graphic English's own rendering does not. This is not
  limited to concepts ``ICON_RULES`` never covers at all: an inflected verb
  form (``"discards"``, matched by no bare-word rule — only the exact word
  "discard"/"Discard" is), a lowercase noun (``"contracts"`` — the
  ``Contract`` rule is capital-only), or a count separated from its keyword
  by another word (``"Draw 1 more card"``, ``"Influence requirements"``)
  each leave the *specific English line* unmatched even though the bare
  word or a counted form would match elsewhere; ``phrase()`` (unlike
  ``iconize()``) draws an icon for *any* bare ``{term}`` whose ``TERMS`` row
  has one, with no such gate, so copying a placeholder in from a similar
  line is not safe — check the exact English wording's own match, every
  time (2026-09-25 review; a scratch sweep against the real client
  ``ICON_RULES``/``phrase()`` caught 17 lines this way — now a standing
  guard, ``scripts/e2e/effect_text.py``'s
  ``check_all_cards_icon_parity``, over every catalog card).
- "N Contract(s)" is bare-capital-only the same way: ``ICON_RULES``' rule
  requires literal capital "Contract"/"Contracts", so a card whose printed
  wording is the lowercase noun ("complete a contract", "4+ contracts")
  gets the plain glossary word "계약", not ``{contract}`` — only a
  capitalized "N or more Contracts" condition (Cargo Runner's own
  threshold, this module's own precedent two bullets up) draws the icon.
- "per other revealed sword card" (``strength_per_other_sword_card``) draws
  **two** sword icons in English — the counted "+N sword(s)" and a second,
  bare one for the literal word "sword" inside "sword card" — so the
  Korean twin names the card with the bare ``{sword}`` placeholder too
  ("다른 {sword} 카드마다"), not the plain word "검".
- "Command (6+ Persuasion)" draws Command as its plain ``TERMS`` word (icon:
  null) and a **bare** Persuasion icon — the "6+" itself never matches the
  counted Persuasion rule (which needs "N Persuasion" with no "+" between
  the digit and the space) — so the Korean twin is "{command} ({persuasion}
  6 이상)": a bare Persuasion placeholder, with "6 이상" as plain trailing
  text exactly like any other bare-icon threshold two bullets up, never a
  counted ``{persuasion:6}``.

Conditions follow ``cardstyle.md``'s style guide: time/location phrases
front the clause, the verb ends it, and a condition closes with
``-다면:``/``-(이)면:`` (rule 1) — this module uses ``-(이)면`` uniformly for
its own bare noun/threshold conditions (a Faction Bond/Alliance/Command
state, a resource or unit-count threshold), since every condition here is
of that shape. A non-conditional declarative line prefers the terse nominal
register (``-가능``/``-음``, rule 9) over a full ``-습니다`` sentence.

A Faction Bond condition ("If <Faction> Bond: …") always reads "<Faction>**의**
유대감이면:" — the genitive particle is part of ``docs/rules/glossary-ko.md``'s
own established row, not composed here (``Fremen Bond | 프레멘의 유대감 |
[Main p. 20]``; Northern Watermaster's Korean print pins it, "프레멘의
유대감:"). A Faction Alliance condition, by contrast, has no such
possessive in either its glossary row (``Alliance | 동맹``) or the sampled
card print (``cardstyle.md``, Branching Path: "동맹:", no genitive) and so
stays a bare compound, "<Faction> {alliance}이면:" — the two conditions look
parallel in English ("If X Bond"/"If X Alliance") but are not spelled the
same way in Korean, and inventing symmetry between them would be a real
term neither source uses.
"""

from typing import Final

from dune_imperium.content.uprising.types import (
    PersonalCardAcquisitionEffect,
    PersonalCardAgentEffect,
    PersonalCardBond,
    PersonalCardDiscardEffect,
    PersonalCardRevealAcquisitionEffect,
    PersonalCardRevealChoiceEffect,
    PersonalCardRevealEffect,
    PersonalCardTrashEffect,
)

_BOND_NAMES_KO: dict[PersonalCardBond, str] = {
    PersonalCardBond.EMPEROR: "황제",
    PersonalCardBond.SPACING_GUILD: "우주 항행 길드",
    PersonalCardBond.BENE_GESSERIT: "베네 게세리트",
    PersonalCardBond.FREMEN: "프레멘",
}


def _bond_name_ko(bond: PersonalCardBond) -> str:
    return _BOND_NAMES_KO[bond]


AGENT_EFFECT_TEXT_KO: Final[dict[PersonalCardAgentEffect, str]] = {
    PersonalCardAgentEffect.GAIN_TWO_VISITED_FACTION_INFLUENCE_AND_TRASH_SELF: (
        "방문한 팩션 {influence_any:2}, 이 카드 {trash}"
    ),
    PersonalCardAgentEffect.LOOK_AT_TOP_THREE: (
        "카드덱에 카드가 3장 이상 있다면: 맨 위 3장 확인, 뽑기 1장, "
        "{discard} 1장, {trash} 1장"
    ),
    PersonalCardAgentEffect.TRASH_SELF: "이 카드 {trash}",
    PersonalCardAgentEffect.TRASH_PERSONAL_CARD: "카드 1장 {trash} 가능",
    PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE: (
        "카드 1장 {trash} 가능 {arrow_right} {draw:1}"
    ),
    PersonalCardAgentEffect.TRASH_PERSONAL_CARD_TO_DRAW_ONE_IF_BENE_GESSERIT_BOND: (
        "베네 게세리트의 유대감이면: 카드 1장 {trash} 가능 {arrow_right} {draw:1}"
    ),
    (
        PersonalCardAgentEffect
        .MAY_TRASH_INTRIGUE_FOR_INTRIGUE_AND_TWO_SPICE_IF_BENE_GESSERIT_ALLIANCE
    ): (
        "베네 게세리트 {alliance}이면: {trash_intrigue} 가능 {arrow_right} "
        "{intrigue:1}, {spice:2}"
    ),
    PersonalCardAgentEffect.TRASH_SELF_AND_EMPEROR_FROM_HAND_FOR_EXTRA_INFLUENCE: (
        "이 카드와 핸드의 황제 카드 {trash} 가능 {arrow_right} "
        "방문한 팩션 {influence_any} 1 추가"
    ),
    PersonalCardAgentEffect.TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE: (
        "이 카드 {trash}, {influence_any:1} 선택"
    ),
    PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE_IF_SPY_RECALLED_THIS_TURN: (
        "이번 차례에 {spy}를 소환했다면: {influence_any:1} 선택"
    ),
    # Per task instruction: this member always resolves through the
    # owner's Leader's Signet Ring ability data rather than typed text.
    PersonalCardAgentEffect.LEADER_SIGNET: "당신 {leader}의 {signet_ring} 능력",
    PersonalCardAgentEffect.PAY_TWO_WATER_TO_DRAW_TWO: (
        "{water:2} 지불 가능 {arrow_right} {draw:2}"
    ),
    PersonalCardAgentEffect.MAY_PAY_FOUR_SPICE_FOR_VP: (
        "{spice:4} 지불 가능 {arrow_right} {victory_point:1}"
    ),
    PersonalCardAgentEffect.MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP: (
        "카드 2장 {discard}·{solari:5} 지불 가능 {arrow_right} {victory_point:1}"
    ),
    (
        PersonalCardAgentEffect
        .MAY_TRASH_INTRIGUE_AND_PAY_TWO_SPICE_FOR_VP_IF_SPACING_GUILD_ALLIANCE
    ): (
        "우주 항행 길드 {alliance}이면: {trash_intrigue}·{spice:2} 지불 가능 "
        "{arrow_right} {victory_point:1}"
    ),
    PersonalCardAgentEffect.ACQUIRE_WITH_SOLARI_TO_HAND: (
        "{imperium_row} 또는 {reserve} 1장을 {solari}로 지불해 "
        "핸드로 {acquire} 가능"
    ),
    PersonalCardAgentEffect.TAKE_CONTRACT: "앞면 {contract} 1개 가져옴",
    PersonalCardAgentEffect.MAY_DISCARD_TO_TAKE_CONTRACT: (
        "카드 1장 {discard} 가능 {arrow_right} 앞면 {contract} 1개 가져옴"
    ),
    PersonalCardAgentEffect.DRAW_PER_TWO_COMPLETED_CONTRACTS_UP_TO_TWO: (
        "{contract} 둘 이상 완수했다면: {draw:1}, "
        "{contract} 넷 이상 완수했다면: 카드 1장 더 뽑음"
    ),
    PersonalCardAgentEffect.GAIN_CHOSEN_INFLUENCE: "{influence_any:1} 선택",
    PersonalCardAgentEffect.DRAW_ONE_AND_RECALL_AGENT: "{draw:1}, {agent} 소환",
    PersonalCardAgentEffect.DRAW_PERSONAL_CARD: "{draw:1}",
    PersonalCardAgentEffect.DRAW_PER_SANDWORM_IN_CONFLICT: (
        "{conflict}의 {sandworm}마다 {draw:1}"
    ),
    PersonalCardAgentEffect.DISCARD_TO_DRAW_ONE_OR_TWO_IF_SPACING_GUILD: (
        "카드 1장 {discard} 가능 {arrow_right} {draw:1} "
        "(버린 카드가 우주 항행 길드 카드이면 2장)"
    ),
    PersonalCardAgentEffect.DISCARD_ONE_DRAW_TWO_IF_SPACING_GUILD: (
        "카드 1장 {discard} {arrow_right} "
        "버린 카드가 우주 항행 길드 카드이면 {draw:2}"
    ),
    PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_INTRIGUE_AND_PERSONAL_CARD: (
        "카드 1장 {discard} 가능 {arrow_right} {intrigue:1}, {draw:1}"
    ),
    PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE_AND_INTRIGUE_IF_SPACING_GUILD: (
        "카드 1장 {discard} 가능 {arrow_right} {draw:1} "
        "(버린 카드가 우주 항행 길드 카드이면 {intrigue:1} 추가)"
    ),
    PersonalCardAgentEffect.EACH_OPPONENT_DISCARDS_PERSONAL_CARD: (
        "다른 플레이어 각자 카드 1장 버리기"
    ),
    PersonalCardAgentEffect.GAIN_SPICE_IF_MAKER_SPACE: (
        "메이커 장소에 있다면: {spice:1}"
    ),
    PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_MAKER_SPACE: (
        "메이커 장소에 있다면: {spice:2}"
    ),
    PersonalCardAgentEffect.GAIN_TWO_SOLARI: "{solari:2}",
    PersonalCardAgentEffect.GAIN_ONE_SPICE: "{spice:1}",
    PersonalCardAgentEffect.PLACE_SPY: "{spy} 배치",
    PersonalCardAgentEffect.PLACE_SPY_ALLOW_SHARED_IF_SPYING_ON_VISITED_SPACE: (
        "{spy} 배치 (방문한 장소를 정탐 중이면 다른 플레이어의 {spy}와 "
        "관측소 공유 가능)"
    ),
    PersonalCardAgentEffect.RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN: (
        "이번 차례에 {spy}를 소환했다면: {troop:3}"
    ),
    PersonalCardAgentEffect.RECRUIT_TWO_IF_SPY_RECALLED_THIS_TURN: (
        "이번 차례에 {spy}를 소환했다면: {troop:2}"
    ),
    PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SPY_RECALLED_THIS_TURN: (
        "이번 차례에 {spy}를 소환했다면: {intrigue:1}"
    ),
    PersonalCardAgentEffect.DRAW_INTRIGUE_IF_THREE_UNITS_IN_CONFLICT: (
        "{conflict}에 부대가 3 이상 있다면: {intrigue:1}"
    ),
    PersonalCardAgentEffect.GAIN_WATER_IF_BENE_GESSERIT_BOND: (
        "베네 게세리트의 유대감이면: {water:1}"
    ),
    PersonalCardAgentEffect.GAIN_VISITED_FACTION_INFLUENCE: (
        "방문한 팩션 {influence_any} 1 추가"
    ),
    PersonalCardAgentEffect.GAIN_WATER: "{water:1}",
    # Immortality (card faces).
    PersonalCardAgentEffect.RESEARCH: "{research} (연구 트랙 전진)",
    PersonalCardAgentEffect.ADVANCE_TLEILAXU: "{tleilaxu} (트랙 전진)",
    PersonalCardAgentEffect.ADVANCE_TLEILAXU_IF_ONE_MARKER: (
        "유전자 마커 1개에 도달했다면: {tleilaxu} (트랙 전진)"
    ),
    PersonalCardAgentEffect.ADVANCE_TLEILAXU_IF_GRAFTED: (
        "{graft}했다면: {tleilaxu} (트랙 전진)"
    ),
    PersonalCardAgentEffect.DRAW_TWO_IF_ONE_MARKER: (
        "유전자 마커 1개에 도달했다면: {draw:2}"
    ),
    PersonalCardAgentEffect.DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS: (
        "이번 차례에 다른 플레이어의 {agent}가 당신의 {agent}를 막지 않음. "
        "{draw:1}, 유전자 마커 2개에 도달했다면: {intrigue:1}"
    ),
    PersonalCardAgentEffect.MAY_RECALL_AGENT_SENT_THIS_TURN: (
        "이번 차례에 보낸 {agent} 소환 가능"
    ),
    PersonalCardAgentEffect.GENERATE_SPECIMEN: "표본 1개 생성",
    PersonalCardAgentEffect.GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE: (
        "{influence_bene_gesserit:1}, {intrigue:1}"
    ),
    PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_GRAFTED: "{graft}했다면: {spice:2}",
    PersonalCardAgentEffect.GAIN_TWO_SPICE_IF_EMPEROR_INFLUENCE_TWO: (
        "{influence_emperor} 2 이상이면: {spice:2}"
    ),
    PersonalCardAgentEffect.GAIN_FREMEN_INFLUENCE_IF_BENE_GESSERIT_BOND: (
        "베네 게세리트의 유대감이면: {influence_fremen:1}"
    ),
    PersonalCardAgentEffect.DRAW_ONE_AND_COMBAT_ICON: (
        "{draw:1}, {combat} (전투 장소에 보낸 것처럼 배치 가능)"
    ),
    PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED: (
        "{graft}했다면: {troop:1}, {draw:1}"
    ),
    PersonalCardAgentEffect.DRAW_TWO_CARDS: "{draw:2}",
    PersonalCardAgentEffect.GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE: (
        "{water:1}, 프레멘 {alliance}: {in_play}에서 이 카드를 핸드로 되돌림"
    ),
    PersonalCardAgentEffect.RECRUIT_ONE_AND_MAY_TRASH: (
        "{troop:1}, 카드 1장 {trash} 가능"
    ),
    PersonalCardAgentEffect.GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE: (
        "팩션 둘 선택: 각각 {influence_any:1}"
    ),
    PersonalCardAgentEffect.MAY_PAY_SPECIMEN_FOR_FOUR_SOLARI: (
        "표본 1개 지불 가능 {arrow_right} {solari:4}"
    ),
    PersonalCardAgentEffect.MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN: (
        "다른 {graft} 카드 {trash} 가능 {arrow_right} 표본 1개 생성"
    ),
    (
        PersonalCardAgentEffect
        .DRAW_ONE_OR_COMBAT_ICON_IF_SPACING_GUILD_INFLUENCE_TWO
    ): (
        "{influence_spacing_guild} 2 이상이면: 하나 선택: {draw:1} / "
        "{combat} (전투 장소에 보낸 것처럼 배치 가능)"
    ),
    PersonalCardAgentEffect.PEEK_TWO_INTRIGUE_KEEP_ONE: (
        "{intrigue} 맨 위 2장 확인 후 1장 보관, 나머지는 맨 위로 되돌림"
    ),
    (
        PersonalCardAgentEffect
        .GAIN_SPICE_AND_CHOSEN_INFLUENCE_IF_GRAFTED_WITH_EMPEROR_OR_GUILD
    ): (
        "{spice:1}, 황제 또는 우주 항행 길드 카드와 {graft}했다면: "
        "{influence_any:1} 선택"
    ),
    PersonalCardAgentEffect.MAY_ACQUIRE_CARD_UP_TO_SIX_IF_ONE_MARKER: (
        "유전자 마커 1개면: 비용 6 이하 카드 {acquire} 가능, "
        "유전자 마커 2개면: 핸드로 가져옴"
    ),
    PersonalCardAgentEffect.MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU: (
        "표본 2개 지불 가능 {arrow_right} {tleilaxu} 트랙 2회 전진"
    ),
    PersonalCardAgentEffect.DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED: (
        "{draw:1}, {graft}했다면: {research}, 표본 1개 생성"
    ),
    PersonalCardAgentEffect.RESEARCH_AND_MAY_TRASH_SELF_FOR_VP_IF_TWO_MARKERS: (
        "{research}, 유전자 마커 2개면: 이 카드 {trash} 가능 "
        "{arrow_right} {victory_point:1}"
    ),
    (
        PersonalCardAgentEffect
        .GAIN_SPACING_GUILD_INFLUENCE_IF_GAINED_SPICE_THIS_TURN
    ): "이번 차례에 {spice}를 얻었다면: {influence_spacing_guild:1}",
    (
        PersonalCardAgentEffect
        .GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU
    ): (
        "다른 {graft} 카드의 {agent} 아이콘마다 {solari:1}, "
        "{solari:5} 지불 가능 {arrow_right} {tleilaxu} 트랙 전진"
    ),
    PersonalCardAgentEffect.CHOOSE_TWO_OF_WATER_TROOP_TRASH_TLEILAXU: (
        "둘 선택: {water:1} / {troop:1} / 카드 1장 {trash} / {tleilaxu} 트랙 전진"
    ),
    (
        PersonalCardAgentEffect
        .MAY_TRASH_GRAFTED_CARD_FOR_VISITED_FACTION_INFLUENCE
    ): (
        "이번 차례에 팩션 장소로 {agent}를 보냈다면: {graft}한 카드 {trash} 가능 "
        "{arrow_right} 그 팩션 {influence_any:1}"
    ),
    PersonalCardAgentEffect.MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH: (
        "{troop:1} 잃기 가능 {arrow_right} {draw:2}, {research}"
    ),
    PersonalCardAgentEffect.RETURN_OTHER_GRAFTED_TO_HAND_AT_REVEAL_START: (
        "{reveal_turn} 시작 시, 다른 {graft} 카드를 {in_play}에서 핸드로 되돌림"
    ),
    PersonalCardAgentEffect.GAIN_BY_BENE_GESSERIT_AND_FREMEN_INFLUENCE_TWO: (
        "{influence_bene_gesserit} 2 이상이면: {water:1}, "
        "{influence_fremen} 2 이상이면: {spice:1}"
    ),
    PersonalCardAgentEffect.GAIN_BY_EMPEROR_AND_SPACING_GUILD_INFLUENCE_TWO: (
        "{influence_emperor} 2 이상이면: {solari:2}, "
        "{influence_spacing_guild} 2 이상이면: {spice:1}"
    ),
    # Uprising promo cards (card faces; OQ-024 to OQ-026).
    (
        PersonalCardAgentEffect
        .MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS
    ): (
        "{maker_hooks}면: {spice:2} 지불 가능 {arrow_right} {shield_wall} 제거 "
        "가능, {sandworm}를 불러서 배치"
    ),
    PersonalCardAgentEffect.GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON: (
        "앞면 {battle_icon}마다 보상 얻음: 크리스나이프: 카드 1장 {trash} 가능, "
        "사막쥐: {spice:1}, 오니솝터: {troop:1}"
    ),
    PersonalCardAgentEffect.MAY_TRASH_SELF_FOR_TROOP_AND_FIRST_PLACE_INFLUENCE: (
        "이 카드 {trash} 가능 {arrow_right} {troop:1}, "
        "1등 보상에 {influence_any:1} 선택 추가"
    ),
    PersonalCardAgentEffect.RECRUIT_ONE_IF_MAKER_SPACE: (
        "메이커 장소에 있다면: {troop:1}"
    ),
    PersonalCardAgentEffect.RECRUIT_TWO_TROOPS: "{troop:2}",
    PersonalCardAgentEffect.RECRUIT_TWO_IF_BENE_GESSERIT_BOND: (
        "베네 게세리트의 유대감이면: {troop:2}"
    ),
    PersonalCardAgentEffect.RETURN_SELF_IF_BENE_GESSERIT_BOND: (
        "베네 게세리트의 유대감이면: 이 카드를 핸드로 되돌림"
    ),
    PersonalCardAgentEffect.DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: (
        "{influence_bene_gesserit} 2 이상이면: {draw:1}"
    ),
    PersonalCardAgentEffect.RECRUIT_ONE_AND_DRAW_IF_BENE_GESSERIT_INFLUENCE_TWO: (
        "{influence_bene_gesserit} 2 이상이면: {troop:1}, {draw:1}"
    ),
    # Bloodlines
    PersonalCardAgentEffect.DRAW_INTRIGUE_CARD: "{intrigue:1}",
    PersonalCardAgentEffect.RECRUIT_ONE_IF_EMPEROR_INFLUENCE_TWO: (
        "{influence_emperor} 2 이상이면: {troop:1}"
    ),
    PersonalCardAgentEffect.MAY_DISCARD_TO_DRAW_ONE: (
        "카드 1장 {discard} 가능 {arrow_right} {draw:1}"
    ),
    PersonalCardAgentEffect.DRAW_INTRIGUE_IF_SANDWORM_IN_CONFLICT: (
        "{conflict}에 {sandworm}이 1 이상 있다면: {intrigue:1}"
    ),
    PersonalCardAgentEffect.DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN: (
        "이번 차례에 {spice}를 2 이상 얻었다면: {draw:1}"
    ),
    (
        PersonalCardAgentEffect
        .RECRUIT_ONE_AND_DRAW_ONE_IF_GAINED_TWO_SPICE_THIS_TURN
    ): "이번 차례에 {spice}를 2 이상 얻었다면: {troop:1}, {draw:1}",
    PersonalCardAgentEffect.TAKE_CONTRACT_IF_SPY_RECALLED_THIS_TURN: (
        "이번 차례에 {spy}를 소환했다면: {contract} 가져옴"
    ),
    PersonalCardAgentEffect.DRAW_INTRIGUE_IF_CONTRACT_COMPLETED_THIS_TURN: (
        "이번 차례에 {contract}을 완수했다면: {intrigue:1}"
    ),
    PersonalCardAgentEffect.MAY_TRASH_HAND_CARD_FOR_EMPEROR_REWARDS: (
        "핸드에 있는 카드 1장 {trash} 가능. 황제 카드를 {trash}했다면: "
        "{intrigue:1}, {troop:1}, {combat}"
    ),
    PersonalCardAgentEffect.FORCE_OPPONENT_TROOP_RETREAT: (
        "다른 플레이어의 {troop} 강제 {retreat}"
    ),
    PersonalCardAgentEffect.MAY_TRASH_TWO_CARDS_IF_COMMANDER_IN_CONFLICT: (
        "{conflict}에 {commander}가 1 이상 있다면: 카드 1장 {trash} 가능, "
        "카드 1장 {trash} 가능"
    ),
    PersonalCardAgentEffect.MAY_DISCARD_FOR_DEEP_COVER_SPY: (
        "카드 1장 {discard} 가능 {arrow_right} {spy} 배치 (잠복 스파이); "
        "버린 카드가 우주 항행 길드 카드이면: {spice:2}"
    ),
    PersonalCardAgentEffect.MAY_DISCARD_FOR_WATER: (
        "카드 1장 {discard} 가능 {arrow_right} {water:1}"
    ),
    PersonalCardAgentEffect.COMPLETE_ONE_CONTRACT: "당신의 계약 하나 완수",
    PersonalCardAgentEffect.EACH_OPPONENT_LOSES_TROOP_AND_MOVES_SPY: (
        "다른 플레이어 각자 {troop} 하나 잃음. 이번 차례에 당신이 {agent}를 "
        "보낸 장소를 정탐 중인 다른 플레이어는 그 {spy}를 이동해야 함"
    ),
    PersonalCardAgentEffect.BOOST_NEXT_BENE_GESSERIT_CARD_THIS_ROUND: (
        "이번 라운드에 다음으로 플레이하는 베네 게세리트 카드는 모든 {agent} "
        "아이콘을 가지며, 에이전트 칸에 {draw:1} 추가"
    ),
    PersonalCardAgentEffect.DRAW_ONE_OR_BENE_GESSERIT_INFLUENCE_IF_BOND: (
        "하나 선택: {draw:1} / 베네 게세리트의 유대감이면: "
        "{influence_bene_gesserit:1}"
    ),
    PersonalCardAgentEffect.CHOSEN_INFLUENCE_OR_TWO_TROOPS_BOTH_IF_BOND: (
        "하나 선택: {influence_any:1} 선택 / {troop:2}; "
        "베네 게세리트의 유대감이면 둘 다 얻음"
    ),
}

TRASH_EFFECT_TEXT_KO: Final[dict[PersonalCardTrashEffect, str]] = {
    PersonalCardTrashEffect.DRAW_INTRIGUE_CARD: "{intrigue:1}",
    PersonalCardTrashEffect.RECRUIT_TWO_TROOPS: "{troop:2}",
    PersonalCardTrashEffect.ACQUIRE_BANK_COMMANDER: (
        "은행의 {commander} {acquire} 후 {recruit}"
    ),
    PersonalCardTrashEffect.ADVANCE_TLEILAXU: "{tleilaxu} (트랙 전진)",
}

DISCARD_EFFECT_TEXT_KO: Final[dict[PersonalCardDiscardEffect, str]] = {
    PersonalCardDiscardEffect.GAIN_TWO_SPICE: "{spice:2}",
    PersonalCardDiscardEffect.GAIN_THREE_SOLARI: "{solari:3}",
}

ACQUISITION_EFFECT_TEXT_KO: Final[dict[PersonalCardAcquisitionEffect, str]] = {
    PersonalCardAcquisitionEffect.DRAW_INTRIGUE_CARD: "{intrigue:1}",
    PersonalCardAcquisitionEffect.GAIN_TWO_SOLARI: "{solari:2}",
    PersonalCardAcquisitionEffect.PLACE_SPY: "{spy} 배치",
    PersonalCardAcquisitionEffect.GAIN_SPACING_GUILD_INFLUENCE: (
        "{influence_spacing_guild:1}"
    ),
    PersonalCardAcquisitionEffect.TAKE_CONTRACT: "앞면 {contract} 1개 가져옴",
    PersonalCardAcquisitionEffect.RECRUIT_ONE_TROOP: "{troop:1}",
    PersonalCardAcquisitionEffect.GAIN_EMPEROR_INFLUENCE: "{influence_emperor:1}",
    PersonalCardAcquisitionEffect.GAIN_ONE_WATER: "{water:1}",
    PersonalCardAcquisitionEffect.RESEARCH: "{research} (연구 트랙 전진)",
    PersonalCardAcquisitionEffect.ADVANCE_TLEILAXU: "{tleilaxu} (트랙 전진)",
    PersonalCardAcquisitionEffect.GAIN_ONE_SPICE: "{spice:1}",
    PersonalCardAcquisitionEffect.RECRUIT_THREE_TROOPS: "{troop:3}",
}

# The one transcribed member is specific to The Spice Must Flow; cards.py
# supplies that card-specific condition as the Korean display prefix too
# (mirroring _REVEAL_ACQUISITION_PREFIX), so this text is only the reward.
REVEAL_ACQUISITION_EFFECT_TEXT_KO: Final[
    dict[PersonalCardRevealAcquisitionEffect, str]
] = {
    (
        PersonalCardRevealAcquisitionEffect
        .GAIN_INFLUENCE_FOR_EACH_SPIED_FACTION_ON_SPICE_MUST_FLOW
    ): "정탐 중인 각 팩션마다 {influence_any:1}",
}

REVEAL_CHOICE_EFFECT_TEXT_KO: Final[dict[PersonalCardRevealChoiceEffect, str]] = {
    PersonalCardRevealChoiceEffect.RECALL_SPY_TO_DRAW_INTRIGUE_IF_TWO_PLACED: (
        "{spy}를 2 이상 배치했다면: {spy} 소환, {intrigue:1}"
    ),
    PersonalCardRevealChoiceEffect.MAY_RECALL_TWO_SPIES_FOR_TWO_PERSUASION: (
        "{spy} 2 소환 가능 {arrow_right} {persuasion:2}"
    ),
    PersonalCardRevealChoiceEffect.PLACE_SPY: "{spy} 배치",
    PersonalCardRevealChoiceEffect.GAIN_CHOSEN_INFLUENCE_IF_TWO_TECH: (
        "{tech_tile} 2 이상이면: {influence_any:1} 선택"
    ),
    PersonalCardRevealChoiceEffect.PLACE_SPY_OR_GAIN_TWO_STRENGTH: (
        "하나 선택: {spy} 배치 / {sword:2}"
    ),
    PersonalCardRevealChoiceEffect.MAY_LOSE_INFLUENCE_TO_GAIN_INFLUENCE: (
        "{influence_any:1} 선택 잃기 가능 {arrow_right} {influence_any:1} 선택"
    ),
    PersonalCardRevealChoiceEffect.MAY_PAY_THREE_SPICE_FOR_INFLUENCE: (
        "{spice:3} 지불 가능 {arrow_right} {influence_any:1} 선택"
    ),
    PersonalCardRevealChoiceEffect.MAY_TRASH_OTHER_EMPEROR_FOR_THREE_STRENGTH: (
        "{in_play}의 다른 황제 카드 {trash} 가능 {arrow_right} {sword:3}"
    ),
    PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_FOUR_STRENGTH: (
        "{troop:2} {retreat} 가능 {arrow_right} {sword:4}"
    ),
    (
        PersonalCardRevealChoiceEffect
        .MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE
    ): (
        "베네 게세리트 {alliance}: {influence_any:1} 잃기 가능 "
        "{arrow_right} {victory_point:1}"
    ),
    PersonalCardRevealChoiceEffect.MAY_DEPLOY_OR_RETREAT_ONE_TROOP: (
        "{troop:1} 배치 또는 {retreat} 가능"
    ),
    PersonalCardRevealChoiceEffect.MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS: (
        "{troop:2} 잃기 가능 {arrow_right} 표본 2개 생성"
    ),
    PersonalCardRevealChoiceEffect.GAIN_FIVE_SOLARI_OR_TAKE_HIGH_COUNCIL: (
        "하나 선택: {solari:5} / {solari:5} 지불 {arrow_right} 원로회 자리 차지"
    ),
    PersonalCardRevealChoiceEffect.MAY_PAY_WATER_FOR_SANDWORM: (
        "하나 선택: {persuasion} 유지 / {maker_hooks}면: {water:1} 지불 "
        "{arrow_right} {sandworm}를 불러서 배치"
    ),
    (
        PersonalCardRevealChoiceEffect
        .KEEP_SPICE_OR_TRASH_SELF_FOR_VP_IF_FOUR_CONTRACTS
    ): (
        "{contract} 넷 이상 완수했다면: 하나 선택: {spice} 유지 / "
        "이 카드 {trash} {arrow_right} {victory_point:1}"
    ),
    # Bloodlines
    PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_CARD: (
        "{command} ({persuasion} 6 이상): 카드 1장 {trash} 가능"
    ),
    PersonalCardRevealChoiceEffect.COMMAND_PLACE_SPY: (
        "{command} ({persuasion} 6 이상): {spy} 배치"
    ),
    PersonalCardRevealChoiceEffect.COMMAND_GAIN_CHOSEN_INFLUENCE: (
        "{command} ({persuasion} 6 이상): {influence_any:1} 선택"
    ),
    PersonalCardRevealChoiceEffect.MAY_RETREAT_TWO_TROOPS_FOR_TWO_PERSUASION: (
        "{troop:2} {retreat} 가능 {arrow_right} {persuasion:2}"
    ),
    PersonalCardRevealChoiceEffect.MAY_TRASH_SELF_FOR_COMBAT_ICON: (
        "이 카드 {trash} {arrow_right} "
        "{combat} (전투 장소에 보낸 것처럼 배치 가능)"
    ),
    PersonalCardRevealChoiceEffect.MAY_RECALL_SPY_FOR_THREE_STRENGTH: (
        "{spy} 소환 가능 {arrow_right} {sword:3}"
    ),
    (
        PersonalCardRevealChoiceEffect
        .MAY_TRASH_SELF_FOR_FOUR_INFLUENCE_IF_FOUR_CONTRACTS
    ): (
        "계약 넷 이상 완수했다면: 이 카드 {trash} {arrow_right} "
        "각 팩션 {influence_any:1}"
    ),
    PersonalCardRevealChoiceEffect.PERSUASION_OR_CONTRACT: (
        "하나 선택: {persuasion:1} / {contract}"
    ),
    PersonalCardRevealChoiceEffect.COMMAND_MAY_TRASH_SELF_TO_ACQUIRE_ROW_CARD: (
        "{command} ({persuasion} 6 이상): 이 카드 {trash} {arrow_right} "
        "{imperium_row}에서 카드 {acquire}"
    ),
}

_HANDLED_REVEAL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "solari",
        "spice",
        "water",
        "persuasion",
        "recruit_troops",
        "strength",
        "strength_per_other_sword_card",
        "draw_intrigue",
        "influence",
        "influence_faction",
        "required_faction_bond",
        "requires_high_council",
        "requires_swordmaster",
        "minimum_spies_placed",
        "requires_spying_on_maker_space",
        "per_revealed_faction",
        "persuasion_per_completed_contract",
        "requires_commander_in_conflict",
        "minimum_garrisoned_units",
        "requires_command",
        "trashes_self",
        "grants_combat_icon",
        "specimens",
        "minimum_genetic_markers",
        "tleilaxu",
        "research",
    }
)


def reveal_effect_text_ko(effect: PersonalCardRevealEffect) -> str:
    """Korean twin of ``reveal_effect_text``.

    Mirrors its field-by-field structure exactly (same
    ``_HANDLED_REVEAL_FIELDS``) so a field the English renderer grows and
    this one misses fails the same coverage test. Each requirement field
    becomes one complete condition clause, already ending in the
    conditional appropriate to its shape — ``cardstyle.md`` rule 1's
    ``-다면`` for a condition naming an action (있다/배치하다/도달하다, …)
    versus ``-(이)면`` for a bare nominal state (a Faction Bond, Command);
    no card in the current catalog combines more than one of these (the
    one case that reads like two, "High Council and Swordmaster," is
    already a single combined requirement, exactly as the English
    ``elif`` treats it), so joining several completed clauses with "그리고
    " only has to be grammatical, not attested. ``per_revealed_faction``
    is folded into whichever gain (Persuasion or strength) it scales,
    exactly as the English does. Persuasion/strength keep the printed
    Reveal-diamond "+N" prefix in front of their ``{term:count}`` icon.
    """

    conditions: list[str] = []
    if effect.required_faction_bond is not None:
        conditions.append(f"{_bond_name_ko(effect.required_faction_bond)}의 유대감이면")
    if effect.requires_swordmaster:
        conditions.append("원로회 자리와 소드마스터를 보유했다면")
    elif effect.requires_high_council:
        conditions.append("원로회 자리를 보유했다면")
    if effect.minimum_spies_placed:
        conditions.append(f"{{spy}}를 {effect.minimum_spies_placed} 이상 배치했다면")
    if effect.requires_spying_on_maker_space:
        conditions.append("메이커 장소를 정탐 중이라면")
    if effect.requires_commander_in_conflict:
        conditions.append("{conflict}에 {commander}가 1 이상 있다면")
    if effect.minimum_genetic_markers:
        n_markers = effect.minimum_genetic_markers
        conditions.append(f"유전자 마커 {n_markers}개에 도달했다면")
    if effect.minimum_garrisoned_units:
        n = effect.minimum_garrisoned_units
        conditions.append(f"{{garrison}}에 부대가 {n} 이상 있다면")
    if effect.requires_command:
        conditions.append("{command} ({persuasion} 6 이상)이면")

    per_faction = (
        f" (공개한 {_bond_name_ko(effect.per_revealed_faction)} 카드마다)"
        if effect.per_revealed_faction is not None
        else ""
    )

    gains: list[str] = []
    if effect.persuasion:
        gains.append(f"+{{persuasion:{effect.persuasion}}}{per_faction}")
    if effect.strength:
        gains.append(f"+{{sword:{effect.strength}}}{per_faction}")
    if effect.strength_per_other_sword_card:
        n = effect.strength_per_other_sword_card
        gains.append(f"+{{sword:{n}}} (공개한 다른 {{sword}} 카드마다)")
    if effect.persuasion_per_completed_contract:
        n = effect.persuasion_per_completed_contract
        gains.append(f"+{{persuasion:{n}}} (완수한 {{contract}}마다)")
    if effect.solari:
        gains.append(f"{{solari:{effect.solari}}}")
    if effect.spice:
        gains.append(f"{{spice:{effect.spice}}}")
    if effect.water:
        gains.append(f"{{water:{effect.water}}}")
    if effect.draw_intrigue:
        gains.append(f"{{intrigue:{effect.draw_intrigue}}}")
    if effect.recruit_troops:
        gains.append(f"{{troop:{effect.recruit_troops}}}")
    if effect.influence:
        assert effect.influence_faction is not None
        gains.append(f"{{influence_{effect.influence_faction.value}:{effect.influence}}}")
    if effect.trashes_self:
        gains.append("이 카드 {trash}")
    if effect.grants_combat_icon:
        gains.append("{combat} (전투 장소에 보낸 것처럼 배치 가능)")
    if effect.specimens:
        gains.append(f"표본 {effect.specimens}개 생성")
    if effect.tleilaxu:
        gains.append("{tleilaxu} (트랙 전진)")
    if effect.research:
        gains.append(
            "{research} (연구 트랙 전진)"
            if effect.research == 1
            else f"{{research}} ×{effect.research} (연구 트랙 {effect.research}회 전진)"
        )

    text = ", ".join(gains)
    if conditions:
        return f"{' 그리고 '.join(conditions)}: {text}"
    return text
