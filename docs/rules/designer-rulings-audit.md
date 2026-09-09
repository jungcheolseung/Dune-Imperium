# 디자이너 커뮤니티 판정 대조 (2026-09-08)

상태: 대조 완료, 반영 미결정. 이 문서는 규범 규칙이 아니라 **감사 결과**다. 항목을 엔진에 반영할 때는 [open-questions.md](open-questions.md)에 OQ-022와 같은 방식(`DECIDED`, 출처는 공식 문서가 아닌 디자이너 포럼 판정)으로 등록하고, 규칙 문서·테스트를 같은 변경 단위로 고친다.

## 출처

- 커뮤니티 정리본 "DUNE IMPERIUM FAQ" (elessar, TTS Club Discord/BGG; 2026-06-07판). 공식 FAQ·룰북 항목에 더해 BGG 포럼·Direwolf Discord·Hidden Assets Discord에서 디자이너 Paul Dennen(BGG "Merakon")이 답한 판정을 모았다.
  - BGG 스레드: <https://boardgamegeek.com/thread/3005216/comprehensive-rules-faq-for-dune-imperium>
  - Google Docs: <https://docs.google.com/document/d/15FrreNVs2eAnEWlNCmChQuBr5LLg0HHgC7BqWGk7KYw/edit>
  - 플레인 텍스트 내보내기: 위 문서 ID에 `/export?format=txt`를 붙이면 받을 수 있다(약 157KB, 1,223줄). 저장소에는 넣지 않는다.
- 공식 문서와 겹치는 항목은 [official-rulings-index.md](official-rulings-index.md)가 이미 다룬다. 이 감사는 **공식 문서에 없는 판정**(출처가 "BGG Forum", "Discord", "Message from designer", "In person")에 집중했다.

## 범위

대조 대상: Uprising 4인 기본 + CHOAM + 프로모 + Immortality + Bloodlines/Tech Module에 존재하는 카드·메커니즘.

제외: Rise of Ix 전용(Appropriate, dreadnought, infiltration, Tech Negotiation, Tessia Vernius, Yuna Moritani, Ilesa Ecaz, Armand Ecaz, Helena Richese의 능력, Full Scale Assault, Second Wave, Imperial Bashar, Spaceport·Windtraps·Troop Transports·Spy Satellites·Chaumurky), 원본 Dune: Imperium 전용 카드(Bindu Suspension, Kwisatz Haderach, Power Play, Dispatch an Envoy, The Voice, Foldspace, Selective Breeding, Guild Bankers, Poison Snooper, Refocus, Test of Humanity, Reverend Mother Mohiam, Demand Respect, Staged Incident, Sort Through the Chaos, Calculated Hire, Mentat, Duke Leto 등), 3v3, Rivals·Solo, Auction variant.

## 일치 확인 항목 (코드로 직접 확인)

| 판정 | 구현 위치 |
| --- | --- |
| Agent 배치 직후 Gather Intelligence 결정을 먼저 하고, 그 뒤 space·Agent box·Faction 효과 자유 순서 | `rules/agent_effect_frame.py`(Gather Intelligence 행동이 단독 제시), OQ-011 |
| space 비용은 어떤 효과보다 먼저 지불(Spice Refinery·Gather Support: 카드로 얻은 spice로 1 spice 업그레이드 불가) | `rules/agent_turn.py`(`_pay_cost`가 effect frame 생성보다 앞) |
| trash된 카드의 효과는 발동 불가, 이미 pool에 들어간 Persuasion·검은 유지 | OQ-022(같은 Paul 판정을 이미 채택), `expire_trashed_card_effects` |
| Imperium Row 보충이 획득 효과보다 먼저 | `rules/acquisition.py`(`take_imperium_row_card` 뒤 획득 보너스) |
| Corrinth City: 비용 전액을 먼저 확보해야 하며 discard한 카드의 효과로 충당 불가 | `rules/agent_effects.py` `apply_corrinth_city_payment`(Solari 검사 뒤 discard) |
| Command (6+)·Fremen Bond는 의무 | `rules/reveal_turn.py`, `rules/card_bonds.py`, OQ-033·043 |
| Spy 배치는 supply에 Spy가 있으면 의무(룰북 p. 11 errata) | `rules/spy_moves.py`(`decline_spy_placement`는 놓을 곳이 없을 때만) |
| 같은 post에 자기 Spy 둘 금지, supply가 비면 recall 뒤 재배치(같은 자리 포함) | `rules/spy_placement.py`, `rules/spy_moves.py` |
| Combat 아이콘은 중첩되지 않음(garrison 2개 상한) | `rules/combat_deployment.py` `grant_combat_icon`(`max(limit, 2)`) |
| 검은 unit이 없으면 0이지만, 같은 Reveal에서 unit이 들어오면 기록된 `sword_strength`가 합산됨 | `rules/reveal_turn.py`(`sword_strength`와 `strength` 분리 기록) |
| Call to Arms: Intrigue draw는 세지 않고, 소급하지 않으며, Agent turn에 play해 face-up 대기 | `rules/intrigue_triggers.py` `fire_reveal_acquisition_intrigue`(personal card 획득 경로에서만 호출) |
| Leverage는 실제 spice 획득 필요, Counterattack은 supply 0이어도 play, Shield Wall 제거는 선택, Unexpected Allies는 hooks 없이 worm | `rules/effect_interpreter.py`, `tests/unit/rules/test_intrigue.py` |
| False Orders는 상대 Spy가 없어도 play 가능(Spy 배치 부분만) | `rules/intrigue.py`, `tests/unit/rules/test_bloodlines_cards.py` |
| Strategic Stockpiling: 조건이 성립한 section만 발동 | `tests/unit/rules/test_intrigue.py` |
| Sietch Ritual: Reveal 중에는 hand가 비어 play 불가 | `rules/reveal_turn.py`(`hand=()`) |
| Coercive Negotiation·Distraction: 한 turn 배치 3+는 순배치 기준 | OQ-029, `units_deployed_turn` |
| Urgent Shigawire의 boost는 배치 시 소비되며 Litany의 turn 시작 pass는 소비하지 않음; Weirding Woman이 hand로 돌아오면 boost 흔적 없음 | `rules/agent_turn.py:324`, `rules/agent_effects.py:3231` |
| Long Live the Fighters·Imperium Ceremony는 하나의 원자 효과 | `rules/agent_effect_frame.py`, `rules/intrigue_peek.py`, OQ-052 |
| CHOAM Demands: 이번 turn에 받은 contract도 Agent box로 완료 가능 | `rules/agent_effects.py`(`active_contract_ids` 전부 제시) |
| CHOAM Transports: 완료 즉시 draw(미룰 수 없음) | `rules/contract_tiles.py` `owe_contract_completion_draw` |
| Sardaukar II contract: recall 대상이 없으면 불발 | `rules/contracts.py`(`contract_recall_unavailable`) |
| Harvest contract: contract를 받기 전 같은 turn에 얻은 spice도 셈 | `docs/lessons.md` 2026-08-28 |
| Rapid Dropships는 Agent 배치 뒤에만 | `rules/tech.py` `legal_tech_flip_actions` |
| Suspensor Suits: 구매 전 draw는 troop 없음, Shaddam Signet turn에는 garrison | `rules/intrigue_deck.py`, OQ-042 |
| Forbidden Weapons: Influence가 있으면 반드시 잃음 | `rules/tech.py` `legal_tech_reveal_actions` |
| Ornithopter Fleet: Crysknife·Desert Mouse VP 불가, 획득 즉시 매칭 | `rules/effect_interpreter.py:149`, `rules/ornithopter.py` |
| wild 두 개끼리 Endgame 매칭 | `rules/endgame.py` `_endgame_wild_matches` |
| Chairdog: graft 시점에 좌석에 기록되므로 Chairdog가 먼저 trash돼도 되돌림 | `rules/agent_effects.py:3389`, `rules/reveal_turn.py` `_return_chairdog_cards` |
| Usurp: hand 카드와도 graft 가능, Row 카드는 turn 종료 시 trash(트리거 발동) | `rules/graft.py`, OQ-054 |
| Count Hasimir Fenring: Intrigue trash에는 Solari 없음 | `rules/card_trash.py:85` |
| Feyd(track 끝), Lady Jessica(Spice Agony 1 spice에 둘 다, Reverend Mother 비용 1회·Combat 아이콘 중복 없음), Chani, Esmar Tuek, Y'rkoon(Navigation 자동 trigger), Shaddam(Signet play 시점부터 제한), Kota | `rules/leader_abilities.py`, `rules/navigation.py`, `rules/tactics.py`; `tests/unit/rules/test_leader_abilities.py`, `test_bloodlines_leaders.py`, `test_navigation.py` |

## 불일치 항목 (영향 큰 순, 반영 여부는 사용자 결정)

| # | 판정(출처) | 엔진 현재 동작 | 위치 | 비고 |
| --- | --- | --- | --- | --- |
| 1 | 조건이 거짓인 동안 의무 효과를 "발동해 불발"시킬 수 없다. Guild Envoy가 유일한 손패여도 그 turn에 카드를 뽑으면 discard해야 하며, turn이 끝날 때까지 불가능할 때만 불발(Hidden Assets Discord, Guiding Principles) | OQ-028(a): Agent box는 소유자가 고른 시점에 해결하고 조건이 거짓이면 `agent_card_effect_unavailable`로 종료. 먼저 해결한 뒤 draw하면 discard를 피할 수 있다 | `rules/agent_effects.py:3961`(Guild Envoy), Leadership 등 같은 경로 | Reveal 쪽 (b)·(c)는 미루기/늦은 지급이라 이미 판정과 같은 방향. Agent box도 "turn 종료까지 보류"로 바꾸면 일관됨 |
| 2 | Interstellar Trade로 The Spice Must Flow를 사서 contract가 완료돼도 Persuasion을 더 받지 않는다 — "한 번만 trigger"(In person) | OQ-028(c): Reveal 중 완료된 contract만큼 증분 지급 | `tests/unit/rules/test_reveal_turn.py:2480` | 디자이너 모델은 "발동 시점을 하나 고른다"(Leadership 항목도 동일). OQ-028(c) 전체를 재검토할 사안 |
| 3 | Guild Spy: SMF를 두 장 사도 bump는 한 번(In person); Reveal 중 늦게 뽑힌 Guild Spy도 이미 산 SMF에 반응(In person); Emperor bump로 얻은 Spy는 같은 발동에 못 셈; Sleeper Unit로 나중에 놓은 Spy도 못 셈 | SMF 획득마다 in-play Guild Spy가 매번 발동(1회 가드 없음); 늦게 뽑힌 Guild Spy는 이후 SMF 획득에만 반응; Emperor Spy·Sleeper Unit 쪽은 일치 | `rules/acquisition.py:603` `_resolve_reveal_acquisition_triggers` | 두 방향 모두 어긋남 |
| 4 | (2026-09-09 반영: OQ-057, 두 선택을 먼저 받고 해결) "Choose Two"(Propaganda, Stitched Horror, Rapid Engineering)는 둘을 먼저 정하고 나서 해결. BG 4단계 Intrigue를 보고 두 번째를 고를 수 없다(Message from designer) | 첫 선택의 Influence·Tleilaxu 전진이 즉시 해결된 뒤 두 번째 선택 | `rules/combat.py:832` `apply_distinct_combat_reward_influence`, `rules/agent_effects.py` `_apply_stitched_horror_reward`, `rules/intrigue.py:416` | 두 선택을 한 frame에 모아 받은 뒤 순서대로 적용하면 됨. Propaganda를 worm으로 이기면 두 세트 사이에는 다른 효과 허용 |
| 5 | (2026-09-09 반영: OQ-002 재판정, `rank_combat(first_player=)`) Combat 보상 순서가 결과에 영향을 주면 First Player부터 턴 순서(Message from designer); Harvest Cells 두 명은 턴 순서 | OQ-002: 좌석 번호순 convention(당시 "순서가 관측 불가" 전제) | `rules/combat.py` `rank_combat`/`_rewards` | Immortality의 Imperium Ceremony(Intrigue 덱 상단 열람)와 Harvest Cells로 전제가 깨짐. OQ-002 재개 조건 충족 |
| 6 | (2026-09-09 반영: OQ-057, `skip_intrigue_acquisition`) Impress는 3 이하 카드가 없어도 play 가능, 획득 부분만 불발(Message from designer) | 획득 대상이 없으면 play 자체 불가(검 2도 못 받음) | `rules/effect_interpreter.py:522` `AcquireCardUpTo` 가드 | Inspire Awe 등 같은 가드를 쓰는 카드도 재검토 |
| 7 | (2026-09-09 반영: OQ-057, 세 번째 option; Loyalty/Navigation 자원으로 두 번째 비용 지불은 잔여 경계) Change Allegiances는 한 효과만 또는 둘 다 사용 가능; 첫 효과로 얻은 자원(Margot Loyalty spice, Y'rkoon Navigation)으로 두 번째 비용 지불 가능(Message from designer) | 두 효과가 배타 `_plot` 옵션 | `content/uprising/intrigue.py:292` | Strategic Stockpiling처럼 한 옵션 안의 두 section으로 바꾸면 됨 |
| 8 | (2026-09-09 반영: OQ-054 보강) Usurp로 빌린 Stillsuit Manufacturer는 "in play"가 아니므로 hand로 돌아올 수 없다(BGG) | 빌린 Row 카드가 `in_play`에 들어가 Fremen Alliance면 hand로 이동 | `rules/graft.py:135`, `rules/agent_effects.py:3606` | OQ-054 보강 |
| 9 | (2026-09-09 반영: OQ-057) Battlefield Research·Rapid Engineering(·Machine Culture)은 play했으면 반드시 Tech 획득(Message from designer) | Tech 획득 frame에 항상 `decline_tech` | `rules/tech.py:237` | Intrigue 출처 frame에서만 decline 제거 |
| 10 | (2026-09-09 반영: OQ-057) Imperium Ceremony의 "keep one"은 draw 1 → Suspensor Suits troop 1(Message from designer) | peek keep 경로는 `suspensor_owed`를 올리지 않음 | `rules/intrigue_peek.py:114` | Tech+Immortality 조합 |
| 11 | (2026-09-09 반영: OQ-057, `conflict_end_trigger` 창) Combat 보상으로 받은 Harvest Cells는 즉시 play 가능(BGG) | trigger는 face-up 카드만 보고, Combat Intrigue 창은 보상 지급보다 앞이라 그 Combat에서는 불가 | `rules/combat.py:1461` `_fire_troop_loss_triggers` | 보상 지급 뒤 troop 손실 전 hand의 Harvest Cells를 play할 창이 필요 |
| 12 | (2026-09-09 반영: OQ-057, `ghola_partner`) Ghola를 Long Reach와 graft하면 세 아이콘(Landsraad·City·Spice Trade)을 모두 얻는다(Email, TTS Discord) | Long Reach 아이콘은 BG Bond 조건이고 Ghola는 BG가 아니라 City만 접근 | `rules/agent_icons.py:36` | Planned Coupling(BG)과의 graft는 일치 |
| 13 | (2026-09-09 반영: OQ-057) Tleilaxu Master의 research 2개는 따로 해결 가능(BGG) | 한 행동에서 연속 처리(방향 선택 frame만 끼어듦) | `rules/reveal_turn.py:2231` | 영향 작음 |

## 대조하지 못한 항목 (콘텐츠 공백)

- (2026-09-09 해소) **Bloodlines contract token 8개**를 전사·구현했다([bloodlines.md](bloodlines.md) 1절, [implementation-audits/bloodlines.md](../implementation-audits/bloodlines.md) "Contract token" 절). 두 판정을 대조한 결과 모두 일치한다: "이미 Alliance가 있으면 완료되지 않음" — `_update_alliance`는 이미 보유한 진영에서는 Alliance 이벤트를 내지 않아 hook이 완료하지 않는다(`test_earn_any_alliance_waits_for_a_new_alliance_token`); "같은 turn에 contract를 받고 bump로 완료 가능" — 완료는 Agent 방문 snapshot이 아니라 Alliance 이벤트 후속 hook이라 같은 turn에 성립한다(`test_earn_any_alliance_taken_this_turn_completes_on_this_turns_bump`). 공식 문서가 침묵하는 "상대의 Influence 손실로 넘어온 token"은 OQ-056 convention(완료로 본다).

## 추가 확인이 필요한 항목

- (2026-09-09 해소) Leadership + Calculus of Power + Sardaukar Soldier: "Leadership은 한 순간에 세고 trash된 카드는 못 센다"(In person). 엔진은 Reveal 시작에 한 번 세고(Sardaukar 1장 → +1) Calculus가 Sardaukar를 trash해도 다시 세지 않는다 — trash 뒤에 세어도 Calculus가 검 카드가 되고 Sardaukar가 빠져 같은 +1이므로 어느 순간에 세든 결과가 같다. Sardaukar의 이미 모인 검 1은 OQ-022대로 남는다. `tests/unit/rules/test_reveal_turn.py::test_leadership_counts_sword_cards_once_and_ignores_a_later_trash`(총 8, 9가 아님).
- (2026-09-09 반영) Duncan Idaho(Bloodlines) Into the Fray의 Agent를 Imperial Privilege로 recall 가능(Message from designer): 엔진은 `agent_locations`만 후보로 봐 불가능했다. `recall_conflict_agent_for_imperial_privilege` 행동을 더해 Conflict의 Agent를 Leader로 되돌리고(OQ-037(d), codec v99), 다른 Agent가 없어도 recall을 불발시키지 않는다. `tests/unit/rules/test_bloodlines_leaders.py::test_imperial_privilege_may_recall_the_into_the_fray_agent`.
- Combat 보상으로 Tech를 얻는 Conflict는 현재 카탈로그에 없어 "Trade Monopoly" 계열 판정은 해당 없음(확인만).

## 반영 현황 (2026-09-09)

사용자 결정: 13건 전부 디자이너 판정을 따른다. 4·5·6·7·8·9·10·11·12·13은 반영했다(표의 각 행 앞 표시; 판정 등록은 [OQ-057](open-questions.md#oq-057--디자이너-커뮤니티-판정의-일괄-채택-2026-09-09), OQ-002·OQ-054 보강). 1·2·3 묶음은 진행 중이다.

## 다음 단계 제안

1. 사용자가 반영할 항목을 고른다. 1·2·3은 OQ-028·OQ-002·OQ-022의 연장이라 하나의 판정("효과는 발동 시점을 하나 고르며, 조건이 거짓이면 turn 종료까지 보류")으로 묶어 OQ 항목 하나로 등록하는 편이 낫다.
2. 각 항목은 OQ 등록 → 규칙 문서 인용 → 테스트 → 엔진 수정 순서로, `Play`/`Document` 커밋 쌍을 따른다. 출처가 포럼·Discord이므로 상태는 `DECIDED`로 두고 공식 문서에 인쇄되면 `RESOLVED`로 올린다.
3. Bloodlines contract token 8개는 별도 전사 슬라이스(카드면은 Dune Cards Hub, 수량은 BGG 인벤토리 시트).
