"""Korean text for personal-card enum tokens and automatic Reveal effects.

Korean twin of ``tokens.py`` (feature decided 2026-09-25, Step K2: the effect
text the engine *generates* gets a Korean version; printed card text stays
English). Every table here is keyed by the same enum members or card ids as
its ``tokens.py`` counterpart, so the same coverage test catches a missing
entry the way the English module's own tests do.

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
  native numerals 둘/넷 ``korean-card-style.md`` verified on a real card (Cargo
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

Conditions follow ``korean-card-style.md``'s style guide: time/location phrases
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
card print (``korean-card-style.md``, Branching Path: "동맹:", no genitive) and so
stays a bare compound, "<Faction> {alliance}이면:" — the two conditions look
parallel in English ("If X Bond"/"If X Alliance") but are not spelled the
same way in Korean, and inventing symmetry between them would be a real
term neither source uses.
"""

from typing import Final

from dune_imperium.content.core.effects import AgentOnSpaceWithIcon, RevealCountKind
from dune_imperium.content.core.icons import Faction, PersonalCardBond
from dune_imperium.display.effect_dsl_text_ko import condition_text_ko
from dune_imperium.display.names_ko import KOREAN_CARD_NAMES
from dune_imperium.display.tokens import reveal_line_conditions
from dune_imperium.rules.reveal_lines import RevealLine

_BOND_NAMES_KO: dict[PersonalCardBond, str] = {
    PersonalCardBond.EMPEROR: "황제",
    PersonalCardBond.SPACING_GUILD: "우주 항행 길드",
    PersonalCardBond.BENE_GESSERIT: "베네 게세리트",
    PersonalCardBond.FREMEN: "프레멘",
}


def _bond_name_ko(bond: PersonalCardBond) -> str:
    return _BOND_NAMES_KO[bond]


def _faction_name_ko(faction: Faction) -> str:
    return _bond_name_ko(PersonalCardBond(faction.value))


AGENT_EFFECT_TEXT_KO: Final[dict[str, str]] = {
    "gain_two_visited_faction_influence_and_trash_self": (
        "방문한 팩션 {influence_any:2}, 이 카드 {trash}"
    ),
    "look_at_top_three": (
        "카드덱에 카드가 3장 이상 있다면: 맨 위 3장 확인, 뽑기 1장, "
        "{discard} 1장, {trash} 1장"
    ),
    "trash_self": "이 카드 {trash}",
    "trash_personal_card": "카드 1장 {trash} 가능",
    "trash_personal_card_to_draw_one": (
        "카드 1장 {trash} 가능 {arrow_right} {draw:1}"
    ),
    # Rise of Ix's Shai-Hulud (stage P4d).
    "trash_personal_card_to_recruit_two": (
        "카드 1장 {trash} 가능 {arrow_right} {troop:2}"
    ),
    # Tread in Darkness's own condition box reads "당신의 플레이 영역에 다른
    # 베네 게세리트 카드가 있다면:" [KO card: Tread in Darkness] rather than
    # the generic "유대감" glossary word, and its two icons (may-trash,
    # draw) print with no arrow between them (OQ-058) — the draw always
    # happens even if the trash is declined (agent_effects.py).
    "trash_personal_card_to_draw_one_if_bene_gesserit_bond": (
        "당신의 {in_play}에 다른 베네 게세리트 카드가 있다면: "
        "카드 1장 {trash} 가능, {draw:1}"
    ),
    (
        "may_trash_intrigue_for_intrigue_and_two_spice_if_bene_gesserit_alliance"
    ): (
        "베네 게세리트 {alliance}이면: {trash_intrigue} 가능 {arrow_right} "
        "{intrigue:1}, {spice:2}"
    ),
    "trash_self_and_emperor_from_hand_for_extra_influence": (
        "이 카드와 핸드의 황제 카드 {trash} 가능 {arrow_right} "
        "방문한 팩션 {influence_any:1} 대신 {influence_any:2}"
    ),
    "trash_self_and_gain_chosen_influence": (
        "이 카드 {trash}, {influence_any:1} 선택"
    ),
    "gain_chosen_influence_if_spy_recalled_this_turn": (
        "이번 차례에 {spy}를 소환했다면: {influence_any:1} 선택"
    ),
    # Per task instruction: this member always resolves through the
    # owner's Leader's Signet Ring ability data rather than typed text.
    "leader_signet": "당신 {leader}의 {signet_ring} 능력",
    "pay_two_water_to_draw_two": (
        "{water:2} 지불 가능 {arrow_right} {draw:2}"
    ),
    "may_pay_four_spice_for_vp": (
        "{spice:4} 지불 가능 {arrow_right} {victory_point:1}"
    ),
    # Rise of Ix's Sayyadina (stage P4d): the same generated icon line.
    "may_pay_three_water_for_vp": (
        "{water:3} 지불 가능 {arrow_right} {victory_point:1}"
    ),
    # Rise of Ix's Local Fence (stage P4d): the same arrows, joined as Guild
    # Ambassador's "하나 선택: ... / ...".
    (
        "may_pay_two_spice_for_five_solari_or_five_solari_for_four_spice"
    ): (
        "하나 선택: {spice:2} 지불 가능 {arrow_right} {solari:5} / "
        "{solari:5} 지불 가능 {arrow_right} {spice:4}"
    ),
    "may_discard_two_and_pay_five_solari_for_vp": (
        "카드 2장 {discard}·{solari:5} 지불 가능 {arrow_right} {victory_point:1}"
    ),
    (
        "may_trash_intrigue_and_pay_two_spice_for_vp_if_spacing_guild_alliance"
    ): (
        "우주 항행 길드 {alliance}이면: {trash_intrigue}·{spice:2} 지불 가능 "
        "{arrow_right} {victory_point:1}"
    ),
    "acquire_with_solari_to_hand": (
        "{imperium_row} 또는 {reserve} 1장을 {solari}로 지불해 "
        "핸드로 {acquire} 가능"
    ),
    "take_contract": "앞면 {contract} 1개 가져옴",
    "may_discard_to_take_contract": (
        "카드 1장 {discard} 가능 {arrow_right} 앞면 {contract} 1개 가져옴"
    ),
    "draw_per_two_completed_contracts_up_to_two": (
        "{contract} 둘 이상 완수했다면: {draw:1}, "
        "{contract} 넷 이상 완수했다면: 카드 1장 더 뽑음"
    ),
    "gain_chosen_influence": "{influence_any:1} 선택",
    "draw_one_and_recall_agent": "{draw:1}, {agent} 소환",
    # The original game's Foldspace (Reserve); TRASH_SELF's wording.
    "draw_one_and_trash_self": "{draw:1}, 이 카드 {trash}",
    "draw_personal_card": "{draw:1}",
    "draw_per_sandworm_in_conflict": (
        "{conflict}의 {sandworm}마다 {draw:1}"
    ),
    "discard_to_draw_one_or_two_if_spacing_guild": (
        "카드 1장 {discard} 가능 {arrow_right} {draw:1} "
        "(버린 카드가 우주 항행 길드 카드이면 2장)"
    ),
    # No arrow on the card face (engine audit 2026-10-22, P6).
    "discard_one_draw_two_if_spacing_guild": (
        "카드 1장 {discard}, 버린 카드가 우주 항행 길드 카드이면 {draw:2}"
    ),
    "may_discard_to_draw_intrigue_and_personal_card": (
        "카드 1장 {discard} 가능 {arrow_right} {intrigue:1}, {draw:1}"
    ),
    "may_discard_to_draw_one_and_intrigue_if_spacing_guild": (
        "카드 1장 {discard} 가능 {arrow_right} {draw:1} "
        "(버린 카드가 우주 항행 길드 카드이면 {intrigue:1} 추가)"
    ),
    "each_opponent_discards_personal_card": (
        "다른 플레이어 각자 카드 1장 버리기"
    ),
    "gain_spice_if_maker_space": (
        "메이커 장소에 있다면: {spice:1}"
    ),
    "gain_two_spice_if_maker_space": (
        "메이커 장소에 있다면: {spice:2}"
    ),
    "gain_two_solari": "{solari:2}",
    # Rise of Ix's Bounty Hunter (stage P4d).
    "gain_two_solari_if_enemy_agent_on_space": (
        "다른 플레이어의 {agent}가 있는 장소로 {agent}를 보냈다면: {solari:2}"
    ),
    "gain_one_spice": "{spice:1}",
    "place_spy": "{spy} 배치",
    # "Place a Spy on a post connected to the space you sent an Agent to
    # this turn (may share a post with another player's Spy)" — the post
    # is now the space the Agent visited, not wherever the player is
    # spying; "관측소" is the plain glossary word (TERMS.observation_post
    # has icon: null), matching this project's other "관측소" precedents
    # (``effect_dsl_text_ko.py``'s ``_place_spy_text_ko``).
    "place_spy_on_visited_space_may_share": (
        "이번 차례에 {agent}를 보낸 장소와 연결된 관측소에 {spy} 배치 "
        "(다른 플레이어의 {spy}와 공유 가능)"
    ),
    "recruit_three_if_spy_recalled_this_turn": (
        "이번 차례에 {spy}를 소환했다면: {troop:3}"
    ),
    "recruit_two_if_spy_recalled_this_turn": (
        "이번 차례에 {spy}를 소환했다면: {troop:2}"
    ),
    "draw_intrigue_if_spy_recalled_this_turn": (
        "이번 차례에 {spy}를 소환했다면: {intrigue:1}"
    ),
    "draw_intrigue_if_three_units_in_conflict": (
        "{conflict}에 부대가 3 이상 있다면: {intrigue:1}"
    ),
    "draw_one_and_place_spy_if_bene_gesserit_bond": (
        "베네 게세리트의 유대감이면: {draw:1}, {spy} 배치"
    ),
    # Overthrow's printed words (OQ-128), as Treacherous Maneuver's.
    "gain_visited_faction_influence": (
        "방문한 팩션 {influence_any:1} 대신 {influence_any:2}"
    ),
    "gain_water": "{water:1}",
    # Immortality (card faces).
    "research": "{research} (연구 트랙 전진)",
    "advance_tleilaxu": "{tleilaxu} (트랙 전진)",
    "advance_tleilaxu_if_one_marker": (
        "유전자 마커 1개에 도달했다면: {tleilaxu} (트랙 전진)"
    ),
    "advance_tleilaxu_if_grafted": (
        "{graft}했다면: {tleilaxu} (트랙 전진)"
    ),
    "draw_two_if_one_marker": (
        "유전자 마커 1개에 도달했다면: {draw:2}"
    ),
    "draw_one_and_intrigue_if_two_markers": (
        "이번 차례에 다른 플레이어의 {agent}가 당신의 {agent}를 막지 않음. "
        "{draw:1}, 유전자 마커 2개에 도달했다면: {intrigue:1}"
    ),
    "may_recall_agent_sent_this_turn": (
        "이번 차례에 보낸 {agent} 소환 가능"
    ),
    # Rise of Ix's Landing Rights (stage P4d), in the Korean Rise of Ix
    # rulebook's words for the Freighter icon ("운송 트랙에서 화물선을 1칸
    # 전진시킵니다 ... 화물선을 운송 트랙 맨 밑칸으로 귀환시키면서"
    # [IX-ko p. 12]), as the Freighter rows' labels say "화물선 1칸 전진" and
    # "화물선 귀환". Words, not the icon, as English's line is words.
    "may_move_freighter": (
        "운송 트랙에서 화물선 1칸 전진 또는 귀환 가능"
    ),
    # Rise of Ix's Embedded Agent: Landing Rights' line for each of its two
    # Freighter icons, behind the Bond.
    "may_move_freighter_twice_if_bene_gesserit_bond": (
        "베네 게세리트의 유대감이면: 운송 트랙에서 화물선 1칸 전진 또는 귀환 가능, "
        "운송 트랙에서 화물선 1칸 전진 또는 귀환 가능"
    ),
    # Rise of Ix's Weirding Way (stage P4d).
    "may_take_another_turn": (
        "이 차례 바로 뒤에 차례를 한 번 더 할 수 있음"
    ),
    # Rise of Ix's Ixian Engineer (stage P4d): the Acquire Tech icon, in the
    # words of ``effect_dsl_text_ko`` ("Acquire Tech | 기술 획득" [Bloodlines
    # p. 12]) with the "may" of [Rise of Ix p. 4].
    "may_acquire_tech": "{tech_tile} {acquire} 가능",
    # Rise of Ix's Appropriate (stage P4d): Web of Power's threshold words and
    # the Acquire Tech icon's, the price payable in Solari; the Solari stays a
    # word (솔라리, glossary-ko.md [Main p. 20]) as the English line's does.
    (
        "may_acquire_tech_with_spice_or_solari_if_emperor_influence_two"
    ): (
        "{influence_emperor} 2 이상이면: {tech_tile} {acquire} 가능, "
        "{spice} 대신 솔라리로 지불 가능"
    ),
    "generate_specimen": "표본 1개 생성",
    "gain_bene_gesserit_influence_and_intrigue": (
        "{influence_bene_gesserit:1}, {intrigue:1}"
    ),
    "gain_two_spice_if_grafted": "{graft}했다면: {spice:2}",
    "gain_two_spice_if_emperor_influence_two": (
        "{influence_emperor} 2 이상이면: {spice:2}"
    ),
    "gain_fremen_influence_if_bene_gesserit_bond": (
        "베네 게세리트의 유대감이면: {influence_fremen:1}"
    ),
    "draw_one_and_combat_icon": (
        "{draw:1}, {combat} (전투 장소에 보낸 것처럼 배치 가능)"
    ),
    "recruit_one_and_draw_one_if_grafted": (
        "{graft}했다면: {troop:1}, {draw:1}"
    ),
    "draw_two_cards": "{draw:2}",
    "gain_water_and_return_self_if_fremen_alliance": (
        "{water:1}, 프레멘 {alliance}: {in_play}에서 이 카드를 핸드로 되돌림"
    ),
    "recruit_one_and_may_trash": (
        "{troop:1}, 카드 1장 {trash} 가능"
    ),
    "gain_two_distinct_chosen_influence": (
        "팩션 둘 선택: 각각 {influence_any:1}"
    ),
    "may_pay_specimen_for_four_solari": (
        "표본 1개 지불 가능 {arrow_right} {solari:4}"
    ),
    "may_trash_other_grafted_for_specimen": (
        "다른 {graft} 카드 {trash} 가능 {arrow_right} 표본 1개 생성"
    ),
    (
        "draw_one_or_combat_icon_if_spacing_guild_influence_two"
    ): (
        "{influence_spacing_guild} 2 이상이면: 하나 선택: {draw:1} / "
        "{combat} (전투 장소에 보낸 것처럼 배치 가능)"
    ),
    "peek_two_intrigue_keep_one": (
        "{intrigue} 맨 위 2장 확인 후 1장 보관, 나머지는 맨 위로 되돌림"
    ),
    (
        "gain_spice_and_chosen_influence_if_grafted_with_emperor_or_guild"
    ): (
        "{spice:1}, 황제 또는 우주 항행 길드 카드와 {graft}했다면: "
        "{influence_any:1} 선택"
    ),
    "may_acquire_card_up_to_six_if_one_marker": (
        "유전자 마커 1개면: 비용 6 이하 카드 {acquire} 가능, "
        "유전자 마커 2개면: 핸드로 가져옴"
    ),
    "may_pay_two_specimens_for_two_tleilaxu": (
        "표본 2개 지불 가능 {arrow_right} {tleilaxu} 트랙 2회 전진"
    ),
    "draw_one_and_research_and_specimen_if_grafted": (
        "{draw:1}, {graft}했다면: {research}, 표본 1개 생성"
    ),
    "research_and_may_trash_self_for_vp_if_two_markers": (
        "{research}, 유전자 마커 2개면: 이 카드 {trash} 가능 "
        "{arrow_right} {victory_point:1}"
    ),
    (
        "gain_spacing_guild_influence_if_gained_spice_this_turn"
    ): "이번 차례에 {spice}를 얻었다면: {influence_spacing_guild:1}",
    (
        "gain_solari_per_partner_icon_and_may_pay_five_solari_for_tleilaxu"
    ): (
        "다른 {graft} 카드의 {agent} 아이콘마다 {solari:1}, "
        "{solari:5} 지불 가능 {arrow_right} {tleilaxu} 트랙 전진"
    ),
    "choose_two_of_water_troop_trash_tleilaxu": (
        "둘 선택: {water:1} / {troop:1} / 카드 1장 {trash} / {tleilaxu} 트랙 전진"
    ),
    (
        "trash_grafted_card_for_visited_faction_influence"
    ): (
        "이번 차례에 팩션 장소로 {agent}를 보냈다면: "
        "{graft}한 카드 중 하나 {trash}, 그 팩션 {influence_any:1}"
    ),
    "may_lose_troop_to_draw_two_and_research": (
        "{troop:1} 잃기 가능 {arrow_right} {draw:2}, {research}"
    ),
    "return_other_grafted_to_hand_at_reveal_start": (
        "{reveal_turn} 시작 시, 다른 {graft} 카드를 {in_play}에서 핸드로 되돌림"
    ),
    # Control the Spice: MAY_PAY_FOUR_SPICE_FOR_VP's arrow wording, then
    # RECRUIT_ONE_AND_MAY_TRASH's two rewards in the printed order.
    "may_pay_spice_to_trash_and_recruit": (
        "{spice:1} 지불 가능 {arrow_right} 카드 1장 {trash} 가능, {troop:1}"
    ),
    "gain_by_bene_gesserit_and_fremen_influence_two": (
        "{influence_bene_gesserit} 2 이상이면: {water:1}, "
        "{influence_fremen} 2 이상이면: {spice:1}"
    ),
    "gain_by_emperor_and_spacing_guild_influence_two": (
        "{influence_emperor} 2 이상이면: {solari:2}, "
        "{influence_spacing_guild} 2 이상이면: {spice:1}"
    ),
    # Rise of Ix's Web of Power (stage P4d).
    "gain_by_emperor_spacing_guild_and_fremen_influence_two": (
        "{influence_emperor} 2 이상이면: {solari:2}, "
        "{influence_spacing_guild} 2 이상이면: {draw:1}, "
        "{influence_fremen} 2 이상이면: {water:1}"
    ),
    # Uprising promo cards (card faces; OQ-024 to OQ-026).
    (
        "may_pay_two_spice_for_shield_wall_and_sandworm_if_maker_hooks"
    ): (
        "{maker_hooks}면: {spice:2} 지불 가능 {arrow_right} {shield_wall} 제거 "
        "가능, {sandworm}를 불러서 배치"
    ),
    "gain_rewards_per_face_up_battle_icon": (
        "앞면 {battle_icon}마다 보상 얻음: 크리스나이프: 카드 1장 {trash} 가능, "
        "사막쥐: {spice:1}, 오니솝터: {troop:1}"
    ),
    "may_trash_self_for_troop_and_first_place_influence": (
        "이 카드 {trash} 가능 {arrow_right} {troop:1}, "
        "1등 보상에 {influence_any:1} 선택 추가"
    ),
    "recruit_one_if_maker_space": (
        "메이커 장소에 있다면: {troop:1}"
    ),
    "recruit_two_troops": "{troop:2}",
    "recruit_two_if_bene_gesserit_bond": (
        "베네 게세리트의 유대감이면: {troop:2}"
    ),
    "return_self_if_bene_gesserit_bond": (
        "베네 게세리트의 유대감이면: 이 카드를 핸드로 되돌림"
    ),
    "draw_if_bene_gesserit_influence_two": (
        "{influence_bene_gesserit} 2 이상이면: {draw:1}"
    ),
    "recruit_one_and_draw_if_bene_gesserit_influence_two": (
        "{influence_bene_gesserit} 2 이상이면: {troop:1}, {draw:1}"
    ),
    # Bloodlines
    "draw_intrigue_card": "{intrigue:1}",
    "recruit_one_if_emperor_influence_two": (
        "{influence_emperor} 2 이상이면: {troop:1}"
    ),
    "may_discard_to_draw_one": (
        "카드 1장 {discard} 가능 {arrow_right} {draw:1}"
    ),
    # Rise of Ix's Court Intrigue (stage P4d): Sonic Snoopers' prompt words.
    "may_put_intrigue_on_bottom_to_draw_intrigue": (
        "{intrigue_card} 1장을 {intrigue} {deck} 맨 아래에 놓기 가능 "
        "{arrow_right} {intrigue:1}"
    ),
    # Rise of Ix's Guild Chief Administrator (stage P4d).
    "may_discard_to_trash_a_card": (
        "카드 1장 {discard} 가능 {arrow_right} 카드 1장 {trash} 가능"
    ),
    "draw_intrigue_if_sandworm_in_conflict": (
        "{conflict}에 {sandworm}가 1 이상 있다면: {intrigue:1}"
    ),
    "draw_one_if_gained_two_spice_this_turn": (
        "이번 차례에 {spice}를 2 이상 얻었다면: {draw:1}"
    ),
    (
        "recruit_one_and_draw_one_if_gained_two_spice_this_turn"
    ): "이번 차례에 {spice}를 2 이상 얻었다면: {troop:1}, {draw:1}",
    "take_contract_if_spy_recalled_this_turn": (
        "이번 차례에 {spy}를 소환했다면: {contract} 가져옴"
    ),
    "draw_intrigue_if_contract_completed_this_turn": (
        "이번 차례에 {contract}을 완수했다면: {intrigue:1}"
    ),
    "may_trash_hand_card_for_emperor_rewards": (
        "핸드에 있는 카드 1장 {trash} 가능. 황제 카드를 {trash}했다면: "
        "{intrigue:1}, {troop:1}, {combat}"
    ),
    "force_opponent_troop_retreat": (
        "다른 플레이어의 {troop} 강제 {retreat}"
    ),
    # Rise of Ix's Desert Ambush (stage P4d): Disruption Tactics' line, a
    # unit being "부대" (glossary-ko.md, [Main p. 10]).
    "may_force_enemy_unit_retreat_for_each_troop_deployed": (
        "이번 차례에 배치하는 {troop} 1마다 다른 플레이어의 부대 1 강제 "
        "{retreat} 가능"
    ),
    "may_trash_two_cards_if_commander_in_conflict": (
        "{conflict}에 {commander}이 1 이상 있다면: 카드 1장 {trash} 가능, "
        "카드 1장 {trash} 가능"
    ),
    "may_discard_for_deep_cover_spy": (
        "카드 1장 {discard} 가능 {arrow_right} {spy} 배치 (잠복 스파이); "
        "버린 카드가 우주 항행 길드 카드이면: {spice:2}"
    ),
    "may_discard_for_water": (
        "카드 1장 {discard} 가능 {arrow_right} {water:1}"
    ),
    # Rise of Ix's Satellite Ban (stage P4d).
    "may_discard_for_one_spice_and_one_water": (
        "카드 1장 {discard} 가능 {arrow_right} {spice:1}, {water:1}"
    ),
    # Rise of Ix's Spice Trader (stage P4d).
    "may_discard_for_two_spice_if_fremen_influence_two": (
        "{influence_fremen} 2 이상이면: 카드 1장 {discard} 가능 {arrow_right} {spice:2}"
    ),
    # Rise of Ix's Imperial Bashar (stage P4d).
    "recruit_one_or_may_trash_a_card": (
        "하나 선택: {troop:1} / 카드 1장 {trash} 가능"
    ),
    # Rise of Ix's Esmar Tuek (stage P4d).
    (
        "may_pay_one_spice_for_spacing_guild_influence_and_draw_one"
    ): "{spice:1} 지불 가능 {arrow_right} {influence_spacing_guild:1}, {draw:1}",
    # Rise of Ix's Ix-Guild Compact (stage P4d): the Dreadnought icon, as
    # ``effect_dsl_text_ko``'s CommissionDreadnought draws it ("당신의 드레드노트
    # 하나가 취역합니다" [IX-ko p. 12]).
    "may_discard_two_for_dreadnought": (
        "카드 2장 {discard} 가능 {arrow_right} {dreadnought}"
    ),
    # Rise of Ix's In The Shadows (stage P4d).
    (
        "may_discard_for_chosen_influence_if_bene_gesserit_influence_two"
    ): (
        "{influence_bene_gesserit} 2 이상이면: 카드 1장 {discard} 가능 "
        "{arrow_right} 하나 선택: {influence_emperor:1} / "
        "{influence_spacing_guild:1} / {influence_fremen:1}"
    ),
    "complete_one_contract": "당신의 계약 하나 완수",
    "each_opponent_loses_troop_and_moves_spy": (
        "다른 플레이어 각자 {troop} 하나 잃음. 이번 차례에 당신이 {agent}를 "
        "보낸 장소를 정탐 중인 다른 플레이어는 그 {spy}를 이동해야 함"
    ),
    "boost_next_bene_gesserit_card_this_round": (
        "이번 라운드에 다음으로 플레이하는 베네 게세리트 카드는 모든 {agent} "
        "아이콘을 가지며, 에이전트 칸에 {draw:1} 추가"
    ),
    "draw_one_or_bene_gesserit_influence_if_bond": (
        "하나 선택: {draw:1} / 베네 게세리트의 유대감이면: "
        "{influence_bene_gesserit:1}"
    ),
    "chosen_influence_or_two_troops_both_if_bond": (
        "하나 선택: {influence_any:1} 선택 / {troop:2}; "
        "베네 게세리트의 유대감이면 둘 다 얻음"
    ),
    # The original game's Imperium cards (stage P3): the effect text the
    # engine generates, glossary words only (no Korean card source yet).
    "recruit_one_troop": "{troop:1}",
    (
        "may_pay_two_spice_for_spacing_guild_influence_and_three_solari"
    ): "{spice:2} 지불 가능 {arrow_right} {influence_spacing_guild:1}, {solari:3}",
    "each_opponent_loses_garrison_troop": (
        "다른 플레이어 각자 {garrison}의 {troop} 하나 잃음"
    ),
    "gain_one_solari": "{solari:1}",
    "gain_three_solari": "{solari:3}",
    "may_pay_one_water_for_troop_and_draw_one": (
        "{water:1} 지불 가능 {arrow_right} {troop:1}, {draw:1}"
    ),
    "may_pay_two_spice_for_three_troops": (
        "{spice:2} 지불 가능 {arrow_right} {troop:3}"
    ),
    "draw_two_if_spacing_guild_influence_two": (
        "{influence_spacing_guild} 2 이상이면: {draw:2}"
    ),
    "gain_two_spice": "{spice:2}",
    "gain_spacing_guild_influence_or_two_spice": (
        "하나 선택: {influence_spacing_guild:1} / {spice:2}"
    ),
    "draw_one_or_bene_gesserit_card_from_discard": (
        "하나 선택: {draw:1} / {discard_pile}의 베네 게세리트 카드 1장을 {hand}로"
    ),
    "block_chosen_space_for_opponents_next_agent": (
        "게임판 장소 하나 선택. 다른 플레이어는 이번 라운드의 다음 {agent}를 "
        "그곳에 보낼 수 없음"
    ),
    "recruit_two_and_draw_one": "{troop:2}, {draw:1}",
    "may_trash_self_to_draw_intrigue": (
        "이 카드 {trash} 가능 {arrow_right} {intrigue:1}"
    ),
    "gain_chosen_influence_if_bene_gesserit_bond": (
        "베네 게세리트의 유대감이면: {influence_any:1} 선택"
    ),
    "may_trash_and_gain_two_spice_if_bene_gesserit_bond": (
        "카드 1장 {trash} 가능, 베네 게세리트의 유대감이면: {spice:2}"
    ),
    "each_opponent_discards_two_if_bene_gesserit_bond": (
        "베네 게세리트의 유대감이면: 다른 플레이어 각자 카드 2장 버리기"
    ),
    # Quotes ``effect_dsl_text_ko.py``'s DoubleBaseHarvestSpice line.
    "double_base_harvest_spice": (
        "이 {agent}로 수확하는 기본 {spice} 두 배 (보너스 제외)"
    ),
    # Quotes ``effect_dsl_text_ko.py``'s DoubleBonusHarvestSpice line.
    "double_bonus_harvest_spice": (
        "이 {agent}로 수확하는 보너스 {spice} 두 배"
    ),
    "draw_two_if_bene_gesserit_bond": (
        "베네 게세리트의 유대감이면: {draw:2}"
    ),
    "each_opponent_discards_or_loses_deployed_troop": (
        "다른 플레이어 각자 하나 선택: 카드 1장 {discard} 또는 "
        "{conflict}에 배치된 {troop} 하나 잃음"
    ),
    "may_pay_two_solari_for_chosen_influence": (
        "{solari:2} 지불 가능 {arrow_right} 하나 선택: "
        "{influence_spacing_guild:1} / {influence_bene_gesserit:1} / "
        "{influence_fremen:1}"
    ),
    "may_lose_influence_and_pay_two_spice_for_two_influence": (
        "{influence_any:1} 선택 잃기·{spice:2} 지불 가능 {arrow_right} "
        "{influence_any:2} 한 번 선택"
    ),
}

# Turn-start alternatives, printed in a red box in place of an Agent box
# (Litany Against Fear). Korean twin of ``tokens.py``'s
# ``TURN_START_EFFECT_TEXT``; ``display/cards.py`` prepends its own Korean
# "당신의 차례 시작 시: " the way it prepends the English "At the start of
# your turn: " prefix, matching Litany Against Fear's own scan: "당신의
# 차례 시작 시: 이 카드를 플레이 영역에 놓음 → [draw] 그리고 당신의 차례를
# 넘김." [KO card: Litany Against Fear].
TURN_START_EFFECT_TEXT_KO: Final[dict[str, str]] = {
    "litany_against_fear": (
        "이 카드를 {in_play}에 놓음 {arrow_right} {draw:1} 그리고 "
        "당신의 차례를 넘김"
    ),
}

TRASH_EFFECT_TEXT_KO: Final[dict[str, str]] = {
    "sardaukar_soldier": "{intrigue:1}",
    "eliminate_allies": "{troop:2}",
    "sardaukar_standard": (
        "은행의 {commander} {acquire} 후 {recruit}"
    ),
    "replacement_eyes": "{tleilaxu} (트랙 전진)",
    "assassination_mission": "{solari:4}",
}

# The printed condition that turns a card's greyed Agent icons on; Korean
# twin of ``tokens.py``'s ``ICON_CONDITION_TEXT``; ``display/cards.py``
# appends the icon list the same way. Both members quote their own card's
# Korean scan directly: Long Reach's "당신의 {in_play}에 다른 베네 게세리트
# 카드가 있다면, 이 카드는 [Landsraad], [City], [Spice Trade]를 보유." [KO
# card: Long Reach] and Show of Strength's "당신이 각각의 다른 플레이어보다
# 더 많은 [troops]을 배치했다면, 이 카드는 [Landsraad]와 [Spice Trade]를
# 보유." [KO card: Show of Strength] — "병력" on the print becomes the bare
# {troop} placeholder here for icon parity (English's own bare "troops"
# still draws ICON_RULES' bare troop icon).
ICON_CONDITION_TEXT_KO: Final[dict[str, str]] = {
    "bene_gesserit_bond": (
        "당신의 {in_play}에 다른 베네 게세리트 카드가 있다면"
    ),
    "more_deployed_troops_than_each_opponent": (
        "당신이 각각의 다른 플레이어보다 더 많은 {troop}을 배치했다면"
    ),
}

DISCARD_EFFECT_TEXT_KO: Final[dict[str, str]] = {
    "spacing_guild_s_favor": "{spice:2}",
    "corrupt_bureaucrat": "{solari:3}",
}

ACQUISITION_EFFECT_TEXT_KO: Final[dict[str, str]] = {
    "overthrow": "{intrigue:1}",
    "price_is_no_object": "{solari:2}",
    "corrino_genes": "{solari:2}",
    "guild_spy": "{spy} 배치",
    "in_high_places": "{spy} 배치",
    "spy_network": "{spy} 배치",
    "strike_fleet": "{spy} 배치",
    "subversive_advisor": "{spy} 배치",
    "intelligence_training": "{spy} 배치",
    "steersman": "{influence_spacing_guild:1}",
    "interstellar_trade": "앞면 {contract} 1개 가져옴",
    "mercantile_affairs": "앞면 {contract} 1개 가져옴",
    "arrakis_revolt": "{troop:1}",
    "negotiated_withdrawal": "{troop:1}",
    "imperial_throneship": "{influence_emperor:1}",
    "liet_kynes_card": "{influence_emperor:1}",
    "possible_futures": "{water:1}",
    "chani_card": "{water:1}",
    "water_peddler": "{water:1}",
    "spiritual_fervor": "{research} (연구 트랙 전진)",
    "subject_x_137": "{tleilaxu} (트랙 전진)",
    "lisan_al_gaib": "{spice:1}",
    "occupation": "{troop:3}",
    "choam_directorship": (
        "{influence_emperor:1}, {influence_spacing_guild:1}, "
        "{influence_bene_gesserit:1}, {influence_fremen:1}"
    ),
    "lady_jessica_card": "{influence_any:1} (4개의 팩션 중 하나 선택)",
    "shai_hulud": "카드 1장 {trash}",
    "full_scale_assault": "{dreadnought}",
    "appropriate": "{freighter}을 1칸 전진시키거나 귀환시킴",
}

# The one transcribed member is specific to The Spice Must Flow; cards.py
# supplies that card-specific condition as the Korean display prefix too
# (mirroring _REVEAL_ACQUISITION_PREFIX), so this text is only the reward.
REVEAL_ACQUISITION_EFFECT_TEXT_KO: Final[
    dict[str, str]
] = {
    "guild_spy": "정탐 중인 각 팩션마다 {influence_any:1}",
}

REVEAL_CHOICE_EFFECT_TEXT_KO: Final[dict[str, str]] = {
    "recall_spy_to_draw_intrigue_if_two_placed": (
        "{spy}를 2 이상 배치했다면: {spy} 소환 가능 {arrow_right} {intrigue:1}"
    ),
    "may_recall_two_spies_for_three_persuasion": (
        "{spy} 2 소환 가능 {arrow_right} {persuasion:3}"
    ),
    "place_spy": "{spy} 배치",
    "place_two_spies": "{spy} 2 배치",
    "gain_chosen_influence_if_two_tech": (
        "{tech_tile} 2 이상이면: {influence_any:1} 선택"
    ),
    # Rise of Ix's Ixian Engineer (stage P4d): CHOAM Demands' arrow with a
    # Victory Point.
    (
        "may_trash_self_for_victory_point_if_three_tech_tiles"
    ): (
        "{tech_tile} 3 이상이면: 이 카드 {trash} {arrow_right} {victory_point:1}"
    ),
    # Rise of Ix's Ix-Guild Compact (stage P4d), in the Korean Rise of Ix
    # rulebook's words for the Tech Negotiation icon ("개인 공급처에서 병력
    # 하나를 가져와서 익스 게임판에 놓아도 됩니다. 이 병력은 협상가로
    # 사용됩니다" [IX-ko p. 12]), as the English line is words.
    "may_place_two_negotiators": (
        "{supply}의 {troop} 하나를 익스 게임판에 협상가로 놓기 가능, 두 번"
    ),
    "may_place_negotiator": (
        "{supply}의 {troop} 하나를 익스 게임판에 협상가로 놓기 가능"
    ),
    # Rise of Ix's promo Boundless Ambition (stage P4d): ``effect_dsl_text_ko``'s
    # words for its acquisition.
    "acquire_card_up_to_five": (
        "비용이 5 이하인 카드 {acquire}"
    ),
    # Rise of Ix's Web of Power (stage P4d).
    "gain_chosen_influence": "{influence_any:1} 선택",
    "place_spy_or_gain_two_strength": (
        "하나 선택: {spy} 배치 / {sword:2}"
    ),
    "may_lose_influence_to_gain_influence": (
        "{influence_any:1} 선택 잃기 가능 {arrow_right} {influence_any:1} 선택"
    ),
    "may_pay_three_spice_for_influence": (
        "{spice:3} 지불 가능 {arrow_right} {influence_any:1} 선택"
    ),
    "may_trash_other_emperor_for_three_strength": (
        "{in_play}의 다른 황제 카드 {trash} 가능 {arrow_right} {sword:3}"
    ),
    "may_retreat_two_troops_for_four_strength": (
        "{troop:2} {retreat} 가능 {arrow_right} {sword:4}"
    ),
    (
        "may_lose_influence_for_vp_if_bene_gesserit_alliance"
    ): (
        "베네 게세리트 {alliance}: 한 팩션과 {influence_any:2} 잃기 가능 "
        "{arrow_right} {victory_point:1}"
    ),
    "may_deploy_or_retreat_one_troop": (
        "{troop:1} 배치 또는 {retreat} 가능"
    ),
    (
        "may_deploy_or_retreat_one_troop_if_fremen_bond"
    ): "프레멘의 유대감: {troop:1} 배치 또는 {retreat} 가능",
    "may_lose_two_troops_for_two_specimens": (
        "{troop:2} 잃기 가능 {arrow_right} 표본 2개 생성"
    ),
    # The original game's Imperium cards (stage P3): glossary words only.
    "may_deploy_one_troop": (
        "{garrison}의 {troop:1}을 {conflict}에 배치 가능"
    ),
    "choose_two_persuasion_or_two_strength": (
        "하나 선택: {persuasion:2} / {sword:2}"
    ),
    "may_deploy_up_to_three_troops": (
        "{garrison}의 {troop:3}까지 {conflict}에 배치 가능"
    ),
    "may_retreat_up_to_two_troops": (
        "{troop:2}까지 {retreat} 가능"
    ),
    # Rise of Ix's Guild Chief Administrator (stage P4d): Landing Rights'
    # Freighter line.
    "may_move_freighter": (
        "운송 트랙에서 화물선 1칸 전진 또는 귀환 가능"
    ),
    # Rise of Ix's Negotiated Withdrawal (stage P4d): units are "부대"
    # (glossary-ko.md, [Main p. 10]).
    "may_retreat_three_units_for_influence": (
        "부대 3 {retreat} 가능 {arrow_right} {influence_any:1} 선택"
    ),
    "may_retreat_any_number_of_troops": (
        "원하는 수의 {troop} {retreat} 가능"
    ),
    (
        "may_trash_self_to_move_any_number_of_troops"
    ): (
        "이 카드 {trash} {arrow_right} 원하는 수의 {troop}을 {garrison}에서 "
        "{conflict}에 배치하거나 {retreat}"
    ),
    "may_pay_six_solari_for_victory_point": (
        "{solari:6} 지불 가능 {arrow_right} {victory_point:1}"
    ),
    (
        "may_pay_three_solari_for_two_troops_and_deploy"
    ): (
        "{solari:3} 지불 가능 {arrow_right} {troop:2}, "
        "이 {troop}을 {conflict}에 배치 가능"
    ),
    (
        "may_pay_three_spice_for_victory_point_if_spacing_guild_alliance"
    ): (
        "우주 항행 길드 {alliance}: {spice:3} 지불 가능 {arrow_right} "
        "{victory_point:1}"
    ),
    "gain_five_solari_or_take_high_council": (
        "하나 선택: {solari:5} / {solari:5} 지불 {arrow_right} 원로회 자리 차지"
    ),
    "may_pay_water_for_sandworm": (
        "하나 선택: {persuasion} 유지 / {maker_hooks}면: {water:1} 지불 "
        "{arrow_right} {sandworm}를 불러서 배치"
    ),
    (
        "keep_spice_or_trash_self_for_vp_if_four_contracts"
    ): (
        "{contract} 넷 이상 완수했다면: 하나 선택: {spice} 유지 / "
        "이 카드 {trash} {arrow_right} {victory_point:1}"
    ),
    # Bloodlines
    "command_may_trash_card": (
        "{command} ({persuasion} 6 이상): 카드 1장 {trash} 가능"
    ),
    "command_place_spy": (
        "{command} ({persuasion} 6 이상): {spy} 배치"
    ),
    "command_gain_chosen_influence": (
        "{command} ({persuasion} 6 이상): {influence_any:1} 선택"
    ),
    "may_retreat_two_troops_for_two_persuasion": (
        "{troop:2} {retreat} 가능 {arrow_right} {persuasion:2}"
    ),
    "may_trash_self_for_combat_icon": (
        "이 카드 {trash} {arrow_right} "
        "{combat} (전투 장소에 보낸 것처럼 배치 가능)"
    ),
    "may_recall_spy_for_three_strength": (
        "{spy} 소환 가능 {arrow_right} {sword:3}"
    ),
    (
        "may_trash_self_for_four_influence_if_four_contracts"
    ): (
        "계약 넷 이상 완수했다면: 이 카드 {trash} {arrow_right} "
        "각 팩션 {influence_any:1}"
    ),
    "persuasion_or_contract": (
        "하나 선택: {persuasion:1} / {contract}"
    ),
    "command_may_trash_self_to_acquire_row_card": (
        "{command} ({persuasion} 6 이상): 이 카드 {trash} {arrow_right} "
        "{imperium_row}에서 카드 {acquire}"
    ),
}

def reveal_effect_text_ko(line: RevealLine) -> str:
    """Korean twin of ``reveal_effect_text``.

    Mirrors its structure exactly (the same conditions read the same way,
    ``tokens.reveal_line_conditions``, and the same gains in the same order).
    Each condition becomes one complete clause, already ending in the
    conditional appropriate to its shape — ``docs/rules/korean-card-style.md`` rule 1's
    ``-다면`` for a condition naming an action (있다/배치하다/도달하다, …)
    versus ``-(이)면`` for a bare nominal state (a Faction Bond, Command);
    no card in the current catalog combines more than one of these (the
    one case that reads like two, "High Council and Swordmaster," is
    already a single combined requirement, exactly as the English
    ``elif`` treats it), so joining several completed clauses with "그리고
    " only has to be grammatical, not attested. A count per Faction card
    (revealed or in play) is folded into whichever gain (Persuasion or
    strength) it scales, exactly as the English does. Persuasion/strength
    keep the printed Reveal-diamond "+N" prefix in front of their
    ``{term:count}`` icon.
    """

    held = reveal_line_conditions(line)
    conditions: list[str] = []
    if held.bond is not None:
        conditions.append(f"{_faction_name_ko(held.bond)}의 유대감이면")
    if held.swordmaster:
        conditions.append("원로회 자리와 소드마스터를 보유했다면")
    elif held.high_council:
        conditions.append("원로회 자리를 보유했다면")
    if held.spies:
        conditions.append(f"{{spy}}를 {held.spies} 이상 배치했다면")
    if held.maker:
        conditions.append("메이커 장소를 정탐 중이라면")
    if held.commander:
        conditions.append("{conflict}에 {commander}이 1 이상 있다면")
    if held.markers:
        conditions.append(f"유전자 마커 {held.markers}개에 도달했다면")
    if held.garrison:
        conditions.append(f"{{garrison}}에 부대가 {held.garrison} 이상 있다면")
    if held.command:
        conditions.append("{command} ({persuasion} 6 이상)이면")
    if held.influence is not None:
        faction, amount = held.influence
        conditions.append(f"{{influence_{faction.value}}} {amount} 이상이면")
    if held.alliance is not None:
        conditions.append(f"{_faction_name_ko(held.alliance)} {{alliance}}이면")
    if held.agent_on_space is not None:
        # The Canny line's words (``effect_dsl_text_ko``): "황제 게임판 장소에
        # {agent}가 있다면" (Imperial Shock Trooper).
        conditions.append(
            condition_text_ko(AgentOnSpaceWithIcon(held.agent_on_space))
        )

    count = line.faction_count
    per_faction = (
        ""
        if count is None or count.faction is None
        else f" (공개한 {_faction_name_ko(count.faction)} 카드마다)"
        if count.kind is RevealCountKind.REVEALED_FACTION_CARD
        else f" ({{in_play}}에 있는 {_faction_name_ko(count.faction)} 카드마다)"
    )

    gains: list[str] = []
    if line.printed_persuasion:
        gains.append(f"+{{persuasion:{line.printed_persuasion}}}{per_faction}")
    if line.printed_strength:
        gains.append(f"+{{sword:{line.printed_strength}}}{per_faction}")
    if line.strength_per_other_sword_card:
        n = line.strength_per_other_sword_card
        gains.append(f"+{{sword:{n}}} (공개한 다른 {{sword}} 카드마다)")
    if line.strength_per_dreadnought:
        # Rise of Ix's Full-Scale Assault, the piece in the Korean Rise of Ix
        # rulebook's word (드레드노트 [IX-ko pp. 2, 6]).
        n = line.strength_per_dreadnought
        gains.append(f"+{{sword:{n}}} ({{conflict}}의 내 드레드노트마다)")
    if line.persuasion_per_completed_contract:
        n = line.persuasion_per_completed_contract
        gains.append(f"+{{persuasion:{n}}} (완수한 {{contract}}마다)")
    if line.solari:
        gains.append(f"{{solari:{line.solari}}}")
    if line.spice:
        gains.append(f"{{spice:{line.spice}}}")
    if line.water:
        gains.append(f"{{water:{line.water}}}")
    if line.draw_intrigue:
        gains.append(f"{{intrigue:{line.draw_intrigue}}}")
    if line.recruit_troops:
        gains.append(f"{{troop:{line.recruit_troops}}}")
    if line.supply_deployments:
        # Treachery: Double Cross's words (``effect_dsl_text_ko``).
        n = line.supply_deployments
        gains.append(f"{{supply}}의 {{troop:{n}}}을 {{conflict}}에 배치")
    influence = line.influence
    if influence is not None and influence[1]:
        faction, times = influence
        gains.append(f"{{influence_{faction.value}:{times}}}")
    if line.trashes_self:
        gains.append("이 카드 {trash}")
    if line.grants_combat_icon:
        gains.append("{combat} (전투 장소에 보낸 것처럼 배치 가능)")
    if line.specimens:
        gains.append(f"표본 {line.specimens}개 생성")
    if line.tleilaxu:
        gains.append("{tleilaxu} (트랙 전진)")
    if line.research:
        gains.append(
            "{research} (연구 트랙 전진)"
            if line.research == 1
            else f"{{research}} ×{line.research} (연구 트랙 {line.research}회 전진)"
        )
    for discount in line.reserve_discounts:
        # Guild Bankers: ``effect_dsl_text_ko``'s ``ReserveCostDiscount``
        # line (the Reserve card's Korean print name, no card text of its own).
        name = KOREAN_CARD_NAMES["cards"].get(
            discount.card_ids[0], discount.card_ids[0]
        )
        gains.append(
            f"이번 {{reveal_turn}}에 {name}의 {{acquire}} 비용 "
            f"{{persuasion:{discount.amount}}} 감소"
        )

    text = ", ".join(gains)
    if conditions:
        return f"{' 그리고 '.join(conditions)}: {text}"
    return text
