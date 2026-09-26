# 카드·보드 전사 전수 감사 (2026-09-26)

2026-09-25 Chani·Fenring Signet 오독이 드러난 뒤 사용자 요청으로 **모든 카드·타일·보드·Leader**의 전사를 카드면과 전수 대조했다.
이 문서는 방법, 발견 목록과 처리, 남은 판정을 적는다. 발견 하나하나의 카드면 판독·엔진 동작·근거·수정안 전문은 세션 스크래치의
보고서(`AUDIT-REPORT.md`, 사용자에게 전달)에 있고, 각 수정의 근거 인용은 해당 커밋 메시지와 회귀 테스트 주석에 있다.

## 방법

- 대상 348개: 시작 카드 8, Reserve 2, Imperium 109, Tleilaxu 20, Intrigue 90(Twisted·Navigation 포함), Contract 28, Conflict 18,
  Tech 18, Skill 7, Leader 19(뒤집힌 면 포함), 보드 칸 23, 그리고 보드 항목 6(Influence 트랙, 관측소·Control·Maker, Bene Tleilax
  보드, Ixian Embassy, Research Station 덧판, 매수). 그림은 에셋 저장소 `cards/manifest.json`의 content id로 찾았다.
- 항목마다 세 단계: (1) 엔진 데이터·코드를 보지 않은 **블라인드 전사**(확대 도구, 공식 아이콘 가이드 [Main p. 20] [Bloodlines pp. 5, 12]
  [Immortality p. 16] [Board Guide p. 14], 닮은 아이콘 목록), (2) 엔진 정의·구현 코드·표시 문구와 카드면·블라인드 전사의 **대조**
  (블라인드와 엔진이 다른 곳은 반드시 확대해 판정), (3) 불일치마다 **검증자 3명의 반박 시도**(2명 이상이 반박하지 못해야 확정).
  에이전트 546개. 이어서 BGG 카드 인벤토리 시트와 소속·Agent 아이콘·비용·Reveal 수치·매수를 **기계 대조**했다 — 감사가 놓친 오류는
  없었고, 시트 쪽 오류 8건(Double Agent·Guild Spy·Reliable Informant·Spacing Guild's Favor·Experimentation·Chairdog·Scientific
  Breakthrough·Slig Farmer)은 카드 그림으로 판정했다. 파급이 큰 발견 8장은 main 세션이 직접 카드 그림으로 확인했다.
- 결과: 일치 258, 불일치 89, 불확실 1. 확정 발견 114건(규칙 80, 표시 32, 불확실 2), 반박 2건. 매수는 모두 맞다.

## 확정 발견과 처리

처리 열은 수정한 작업 단위다(`fix-s1` 카드 데이터, `s2` 새 Imperium 효과, `s3` Agent box 로직, `s4` Reveal 로직, `s5` Intrigue,
`s6` Spy·Conflict 보상·계약, `s7` Tech·Skill·Leader·Ixian Embassy, `s8` 표시 문구). 각 단위는 별도 worktree에서 구현하고 독립 검토자의
승인을 받은 뒤 `fix-integration`에서 병합했다.

| # | 항목 | 필드 | 종류 | 처리 |
|---|---|---|---|---|
| 0 | reserve `prepare_the_way` | factions (card affiliation) | 규칙 | s1-card-data |
| 1 | reserve `the_spice_must_flow` | reveal box | 규칙 | s1-card-data |
| 2 | reserve `the_spice_must_flow` | factions (card affiliation) | 규칙 | s1-card-data |
| 3 | imperium `bene_gesserit_operative` | factions (card affiliation) | 규칙 | s1-card-data |
| 4 | imperium `calculus_of_power` | agent_icons | 규칙 | s1-card-data |
| 5 | imperium `captured_mentat` | agent box arrow-cost legality (discard → Intrigue + card) | 규칙 | s3-agent-box-logic |
| 6 | imperium `chani_clever_tactician` | agent_icons[0] | 규칙 | s1-card-data |
| 7 | imperium `covert_operation` | reveal | 규칙 | s2-imperium-effects |
| 8 | imperium `covert_operation` | display reveal | 표시 | s2-imperium-effects |
| 9 | imperium `double_agent` | agent box: Spy placement (where it may go and when it may share a post); same misreading in display text to... | 규칙 | s3-agent-box-logic |
| 10 | imperium `guild_spy` | agent box: which hand cards may pay the discard | 규칙 | s3-agent-box-logic |
| 11 | imperium `imperial_spymaster` | agent box condition scope ('If you recalled a Spy this turn') | 규칙 | s3-agent-box-logic |
| 12 | imperium `in_high_places` | agent box reward | 규칙 | s2-imperium-effects |
| 13 | imperium `in_high_places` | reveal arrow reward | 규칙 | s2-imperium-effects |
| 14 | imperium `in_high_places` | affiliation (factions) | 규칙 | s1-card-data |
| 15 | imperium `leadership` | reveal: +1 sword per other revealed card that provides swords this turn | 규칙 | s4-reveal-logic |
| 16 | imperium `maker_keeper` | agent_icons | 규칙 | s1-card-data |
| 17 | imperium `overthrow` | factions (card affiliation) | 규칙 | s1-card-data |
| 18 | imperium `priority_contracts` | reveal choice (2 spice -OR- trash -> VP) when the 4th Contract completes during this Reveal turn | 규칙 | s4-reveal-logic |
| 19 | imperium `public_spectacle` | Agent box condition 'If you recalled a Spy this turn' | 규칙 | s3-agent-box-logic |
| 20 | imperium `public_spectacle` | Reveal Spy icon with an empty Spy supply | 규칙 | s4-reveal-logic |
| 21 | imperium `reliable_informant` | agent_spy_factions (Agent box Spy target posts) | 규칙 | s1-card-data |
| 22 | imperium `sardaukar_coordination` | reveal_persuasion | 규칙 | s1-card-data |
| 23 | imperium `sardaukar_coordination` | reveal_strength (base sword) | 규칙 | s1-card-data |
| 24 | imperium `spy_network` | reveal choice: Spy recall -> Intrigue draw | 규칙 | s4-reveal-logic |
| 25 | imperium `steersman` | Agent box Recall Agent target | 규칙 | s3-agent-box-logic |
| 26 | imperium `stilgar_the_devoted` | reveal_effects[0].per_revealed_faction (Fremen count scope) | 규칙 | s4-reveal-logic |
| 27 | imperium `strike_fleet` | agent_effect RECRUIT_THREE_IF_SPY_RECALLED_THIS_TURN (what counts as a recall) | 규칙 | s3-agent-box-logic |
| 28 | imperium `subversive_advisor` | reveal_effects / reveal_persuasion | 규칙 | s1-card-data |
| 29 | imperium `subversive_advisor` | agent_effect when the card is trashed before its box resolves | 불확실 | 제외 (아래) |
| 30 | imperium `tread_in_darkness` | display text (Agent box) | 표시 | s8-display |
| 31 | imperium `undercover_asset` | agent_icons | 규칙 | s1-card-data |
| 32 | imperium `unswerving_loyalty` | reveal_choice_effects (Fremen Bond line) | 규칙 | s2-imperium-effects |
| 33 | imperium `corrupt_bureaucrat` | agent_effect TAKE_CONTRACT_IF_SPY_RECALLED_THIS_TURN (condition scope) | 규칙 | s3-agent-box-logic |
| 34 | imperium `delivery_logistics` | display text / catalog agent icons | 표시 | s8-display |
| 35 | imperium `fremen_war_name` | agent box: mandatory conditional icons can be fizzled early | 규칙 | s3-agent-box-logic |
| 36 | imperium `intelligence_training` | Reveal box Command (6+) gate: judged on Persuasion left after spending, not Persuasion generated | 규칙 | s4-reveal-logic |
| 37 | imperium `litany_against_fear` | display text omits the red-box turn-start ability | 표시 | s8-display |
| 38 | imperium `blank_slate` | display text (Agent box 'If grafted' clause) | 표시 | s8-display |
| 39 | imperium `for_humanity` | reveal Alliance cost (lose Influence amount) | 규칙 | s2-imperium-effects |
| 40 | imperium `for_humanity` | display text of the Reveal Alliance line | 표시 | s2-imperium-effects |
| 41 | imperium `long_reach` | icon_condition with a Bene Gesserit graft partner | 규칙 | s3-agent-box-logic |
| 42 | imperium `long_reach` | display: conditional Agent icons | 표시 | s3-agent-box-logic |
| 43 | imperium `shadout_mapes` | Reveal choice: which units 'one of your troops' can move | 규칙 | s4-reveal-logic |
| 44 | tleilaxu `beguiling_pheromones` | Graft Agent box: trash optional vs mandatory | 규칙 | s3-agent-box-logic |
| 45 | tleilaxu `beguiling_pheromones` | display text | 표시 | s3-agent-box-logic |
| 46 | tleilaxu `ghola` | Graft box: copies the partner's Agent box, including a Spy placement restriction | 규칙 | s3-agent-box-logic |
| 47 | tleilaxu `ghola` | display text | 표시 | s3-agent-box-logic |
| 48 | tleilaxu `ghola` | OUT OF SCOPE, belongs to imperium__reliable_informant (found while checking Ghola's copy): Spy restriction ... | 규칙 | s1-card-data |
| 49 | tleilaxu `ghola` | OUT OF SCOPE, belongs to imperium__undercover_asset: Agent icons | 규칙 | s1-card-data |
| 50 | tleilaxu `scientific_breakthrough` | agent box: second-marker trash -> VP after the card's own Research | 규칙 | s3-agent-box-logic |
| 51 | tleilaxu `usurp` | display text (graft box) | 표시 | s8-display |
| 52 | tleilaxu `reclaimed_forces` | display text (acquire box) | 표시 | s8-display |
| 53 | intrigue `call_to_arms` | trigger scope: which acquisitions count as 'acquire a card' | 규칙 | s5-intrigue |
| 54 | intrigue `crysknife` | display text (Endgame option) | 표시 | s8-display |
| 55 | intrigue `desert_mouse` | display text, Endgame option | 표시 | s8-display |
| 56 | intrigue `detonation` | display text, option 2 | 표시 | s8-display |
| 57 | intrigue `devour` | display text condition | 표시 | s8-display |
| 58 | intrigue `distraction` | Spy placement target (plot trigger reward) | 규칙 | s5-intrigue |
| 59 | intrigue `distraction` | display text | 표시 | s5-intrigue |
| 60 | intrigue `leverage` | condition 'If you gained spice this turn' (spice-gained accounting) | 규칙 | s5-intrigue |
| 61 | intrigue `ornithopter` | display text (Endgame half) | 표시 | s8-display |
| 62 | intrigue `special_mission` | plot option 1: Spy placement target | 규칙 | s5-intrigue |
| 63 | imperium `reliable_informant` | agent box: Spy target factions | 규칙 | s1-card-data |
| 64 | intrigue `battlefield_research` | option 2 timing (VP section) | 규칙 | s5-intrigue |
| 65 | intrigue `coercive_negotiation` | optional vs mandatory trigger | 불확실 | s5-intrigue |
| 66 | intrigue `false_orders` | forced Spy move destination | 규칙 | s5-intrigue |
| 67 | intrigue `grasp_arrakis` | timing of the flip -> VP option | 규칙 | s5-intrigue |
| 68 | intrigue `ripples_in_the_sand` | display text (condition) | 표시 | s8-display |
| 69 | intrigue `tenuous_bond` | timing per half (Plot vs Combat) | 규칙 | s5-intrigue |
| 70 | intrigue `twisted_ambitious` | display text | 표시 | s8-display |
| 71 | intrigue `twisted_devious` | display text, option 1 | 표시 | s8-display |
| 72 | intrigue `twisted_devious` | display text, option 2 | 표시 | s8-display |
| 73 | intrigue `twisted_sinister` | display text (cost) | 표시 | s8-display |
| 74 | intrigue `navigation_card_1` | display text, option 2 reward | 표시 | s8-display |
| 75 | intrigue `navigation_card_1` | display timing label | 표시 | s8-display |
| 76 | intrigue `navigation_card_5` | display text | 표시 | s8-display |
| 77 | intrigue `navigation_card_8` | display timing prefix | 표시 | s8-display |
| 78 | intrigue `navigation_card_9` | display timing prefix | 표시 | s8-display |
| 79 | intrigue `navigation_card_10` | arrow cost optional (whole card) | 규칙 | s5-intrigue |
| 80 | intrigue `navigation_card_10` | display timing prefix | 표시 | s5-intrigue |
| 81 | intrigue `counterattack` | display text, Plot option | 표시 | s8-display |
| 82 | intrigue `gruesome_sacrifice` | display text, cost | 표시 | s8-display |
| 83 | intrigue `harvest_cells` | Conflict-end window (OQ-057 hand play): when the 2 specimens resolve | 규칙 | s5-intrigue |
| 84 | intrigue `tleilaxu_puppet` | Plot option played during the owner's own Reveal turn | 규칙 | s4-reveal-logic |
| 85 | contract `arrakeen_ii` | Spy reward when the Spy supply is empty | 규칙 | s6-spy-combat-contracts |
| 86 | contract `research_station_i` | Spy reward with an empty Spy supply (recall-first is optional) | 규칙 | s6-spy-combat-contracts |
| 87 | contract `sardaukar_ii` | Recall Agent target when the tile is completed by CHOAM Demands (Bloodlines + CHOAM) | 규칙 | s6-spy-combat-contracts |
| 88 | conflict `skirmish_crysknife` | 1st-place choose-Influence reward: which Factions can be chosen | 규칙 | s6-spy-combat-contracts |
| 89 | conflict `spice_freighters` | 1st-place choose-Influence reward: which Factions can be chosen | 규칙 | s6-spy-combat-contracts |
| 90 | conflict `seize_spice_refinery` | 1st-place Spy reward: empty supply | 규칙 | s6-spy-combat-contracts |
| 91 | conflict `test_of_loyalty` | 1st-place Spy reward: empty supply | 규칙 | s6-spy-combat-contracts |
| 92 | conflict `propaganda` | 1st place 'Choose two' Influence: legal factions | 규칙 | s6-spy-combat-contracts |
| 93 | conflict `storms_in_the_south` | 1st place Spy with Deep Cover when the Spy supply is empty | 규칙 | s6-spy-combat-contracts |
| 94 | tech `servo_receivers` | acquire effect | 규칙 | s7-tech-skill-leader-board |
| 95 | tech `servo_receivers` | acquire display text | 표시 | s7-tech-skill-leader-board |
| 96 | tech `suspensor_suits` | ability trigger coverage (Intrigue draws that bypass the Suspensor hook) | 규칙 | s7-tech-skill-leader-board |
| 97 | tech `training_depot` | Command (6+) late check uses unspent Persuasion, not Persuasion generated | 규칙 | s4-reveal-logic |
| 98 | skill `charismatic` | Reveal bonus when a Commander enters the Conflict during the Reveal turn | 규칙 | s4-reveal-logic |
| 99 | skill `driven` | Reveal bonus when a Commander enters the Conflict during the Reveal turn | 규칙 | s4-reveal-logic |
| 100 | skill `hardy` | reveal bonus (reveal_water=1) | 규칙 | s7-tech-skill-leader-board |
| 101 | skill `hardy` | display text | 표시 | s7-tech-skill-leader-board |
| 102 | leader `feyd_rautha_harkonnen` | Personal Training Spy stages (first_spy, second_spy, final): recall-first with an empty Spy supply | 규칙 | s6-spy-combat-contracts |
| 103 | leader `lady_margot_fenring` | signet (Arrakis Informant) — Spy placement when the Spy supply is empty | 규칙 | s6-spy-combat-contracts |
| 104 | leader `princess_irulan` | signet Chronicler's Insight: acquire option when the Imperium Deck is exhausted | 규칙 | s7-tech-skill-leader-board |
| 105 | leader `chani` | ability Tactician: troops returned to the supply at Combat cleanup | 규칙 | s7-tech-skill-leader-board |
| 106 | leader `chani` | ability Tactician: several troops lost from one source | 규칙 | s7-tech-skill-leader-board |
| 107 | leader `esmar_tuek` | signet (Smuggle Spice) optionality | 규칙 | s7-tech-skill-leader-board |
| 108 | leader `gaius_helen_mohiam` | ability Clandestine (granted Spy icon counted by icon-counting effects) | 규칙 | s7-tech-skill-leader-board |
| 109 | leader `steersman_y_rkoon` | Strange Form (starting water) under leader draft | 규칙 | s7-tech-skill-leader-board |
| 110 | leader `steersman_y_rkoon` | Hungry for Spice trigger scope ('in a single turn') | 규칙 | s7-tech-skill-leader-board |
| 111 | leader `liet_kynes` | Arrakis Planetologist + Arrakis Revolt under a Shield Wall-protected Conflict | 규칙 | s7-tech-skill-leader-board |
| 112 | board `ixian_embassy` | Acquire Tech on a Landsraad visit (header 'Landsraad : Acquire Tech') at High Council when the player does ... | 규칙 | s7-tech-skill-leader-board |
| 113 | board `ixian_embassy` | (adjacent, same root cause; not printed on this board) Sardaukar Commander on High Council at a first visit | 규칙 | s7-tech-skill-leader-board |

제외: #29(Subversive Advisor — 다른 효과가 이 카드를 먼저 trash해 box가 풀리지 않을 때 방문한 Faction의 기본 Influence 1도 사라지는지,
불확실·낮은 확신)는 공식 문서가 답하지 않는 드문 순서 문제라 고치지 않았다.

## 통합 리뷰 (2026-09-26)

여덟 단위를 `fix-integration`에 병합한 뒤, 단위 사이에서 생긴 문제를 찾는 독립 리뷰를 영역 여섯 개(Reveal, Leader·설정, Agent box,
Combat·Contract·Spy, Intrigue·Tech·보드, 콘텐츠·codec·관측)로 돌렸다. 병합 중에 이미 고친 교차 충돌 넷(Hardy의 `reveal_water` 제거를
s4가 계속 읽음, Commander 배치 템플릿이 Immortality 카탈로그에만 있음, 비공개 정보 섞기가 공개된 contract를 옮김, Servo 신호 card id가
로그에 샘)에 더해, 반박 검증을 통과한 발견 18건을 세 작업 단위(`fix2-r1-reveal` R0–R4, `fix2-r2-leaders` R5–R8,
`fix2-r3-agent-spy-intrigue` R9–R17)로 고치고 단위마다 독립 검토자의 승인을 받았다.

| R | 영역 | 발견 | 처리 |
|---|---|---|---|
| 0 | Reveal | Command Center의 troop 2 retreat가 strength를 줄이지 않음 | r1 |
| 1 | Reveal | Reveal 중 들어온 카드의 Command (6+) 자동 효과가 두 번 지급됨 | r1 |
| 2 | Reveal | Reveal 중 들어온 Holy War의 Fremen Bond Combat 아이콘이 열리지 않음 | r1 |
| 3 | Reveal | 카드의 Reveal retreat(Chani, Clever Tactician·Command Center)가 Chani의 Tactics token을 올리지 않음 | r1 |
| 4 | Reveal | Desert Power의 2 Persuasion을 쓴 뒤에도 sandworm을 살 수 있음(Persuasion −2) | r1 |
| 5 | Leader | Y'rkoon의 다음 turn이 곧바로 자기 turn이면 Hungry for Spice가 turn을 닫는 획득을 놓침 | r2 |
| 6 | Leader | 배치 전 TURN frame이나 Reveal에서 쓴 Servo Signet이 Harkonnen Advisor·Emperor의 금지와 Signet recruit를 잃음 | r2 |
| 7 | Leader | Fenring과 비용을 내지 않은 Mohiam이 recall-first 뒤 Spy를 놓지 않을 수 있음 | r2 |
| 8 | Leader | Signet으로 trash한 Eliminate Allies의 troop 2가 배치 몫에서 빠짐 | r2 |
| 9 | Agent box | Agent box Spy 아이콘이 빈 supply에서 recall-first를 강제함(거절 없음) | r3 |
| 10 | Agent box | Sardaukar Coordination의 "recruit한 troop 배치" box가 graft 짝일 때 무시됨 | r3 |
| 11 | Spy | Holy War의 강제 Spy 이동이 다음 좌석의 turn에 recall로 셈 | r3 |
| 12 | Contract | turn이 넘어간 뒤의 Contract Spy 보상 recall-first가 다음 turn에 셈 | r3 |
| 13 | 보드 | Into the Fray로 Conflict에 간 Agent를 Imperial Privilege가 되돌리게 함 | r3 |
| 14 | Intrigue | Distraction이 recall-first 뒤에도 거절을 허용함 | r3 |
| 15 | Tech | Tech 가격이 `spice_spent_after_placement`에 더해지는지 테스트가 없음 | r3 |
| 16 | 콘텐츠 | Agent box·획득 Spy 아이콘이 빈 supply recall을 여전히 강제함 | r3 |
| 17 | Intrigue | Distraction이 함께 face up이면 Coercive Negotiation의 대기(OQ-064)가 소모됨 | r3 |

리뷰 뒤 main 세션이 두 가지를 더 고쳤다: Agent box의 trash(Shishakli·Desert Survival 등)와 Long Live the Fighters로 trash한
Eliminate Allies의 troop 2도 R8과 같은 이유로 배치 몫에서 빠졌고, Rapid Engineering·Battlefield Research로 산 tile의 troop(Rapid
Dropships·Ornithopter Fleet 2, Forbidden Weapons 1)이 배치 전·Reveal에서는 그 turn의 recruit로 세이지 않았다("그 turn에 어떤 출처에서
recruit했든 새 troop은 Conflict에 deploy할 수 있다" `[Main p. 10]` `[FAQ p. 4]`). r1이 보고한 Desert Power와 Command (6+)의 순서 문제는
[OQ-069](../rules/open-questions.md#oq-069--desert-power의-선택-전-2-persuasion과-command-6)에 OPEN으로 적었다. (갱신: OQ-069는
2026-09-26 사용자 판정으로 DECIDED되어 반영되었다. 그 결과 위 R4의 수정(쓴 뒤에도 sandworm을 살 수 있던 것을 막는 "Persuasion −2"
게이트, `_unspent_reveal_persuasion`)은 전제 자체가 없어져 제거되었다: Desert Power의 2 Persuasion은 이제 Persuasion 갈래를 실제로
고르기 전까지 애초에 집계되지 않으므로, 고르기 전에 "쓴다"는 상황이 생기지 않는다.)

커밋 메시지 정정(기존 커밋은 고치지 않는다): e797452의 "13 of 107 positions moved"는 **20**개가 옮겨졌고, b6fa486의 마지막 항목(Influence·lands·Spy 열)
"full seed 158 seat 0 with base seed 3 seat 2"의 뒤쪽은 **full seed 3 seat 2**다(앞의 deck 열 "base seed 3 seat 2"는 맞다).

## 사용자 판정 (2026-09-26)

- Tenuous Bond·Grasp Arrakis·Battlefield Research: 칸의 색띠와 카드 아래의 시점 인쇄(COMBAT / ENDGAME, PLOT / COMBAT)대로 칸마다 한
  시점만 허용한다(두 시점을 모두 연 이전 전사는 오류).
- Coercive Negotiation: 조건이 되면 반드시 수행한다(거절 없음).
- False Orders: 공식 FAQ대로 영향을 받은 상대는 이번 turn에 Agent를 보낸 공간에 **연결되지 않은** 빈 post로 Spy를 옮긴다 `[FAQ p. 2]`.
  Holy War도 문구가 같아 같은 판정을 적용한다(프로젝트 판정). OQ-036 (b) 갱신.

## 사용자 판정 2차 (2026-09-26 저녁)

- OQ-066: Reclaimed Forces의 "acquire"도 acquire다 — 선택한 효과 뒤에 face-up Call to Arms가 발동한다("they choose one of its effects ...
  but leave the card in place" `[Immortality p. 9]`). 같은 작업에서 Call to Arms가 recruit한 troop이 어느 획득 경로에서든 그 Reveal의
  recruit로 세지 않던 결함도 고쳤다.
- OQ-068: 모든 Agent recall(Steersman의 Recall Agent 아이콘, Twisted Mentat, Sardaukar II·High Council contract token의 완료 보상, CHOAM
  Demands 경로)이 Imperial Privilege처럼 Conflict의 Into the Fray Agent를 되돌릴 수 있다(이번 turn의 Agent는 아니다; Twisted Mentat은
  이번 turn의 그 Agent를 되돌린다). Imperial Privilege와 한 helper(`rules/effects.py`)를 쓴다. 참고: 이 작업의 커밋 7afb22b는 두 새 행동을
  제시하지만 748a16a 전까지 처리기가 없어 그 커밋 단독으로는 엔진이 깨진다(bisect 때 건너뛴다; 기존 커밋은 고치지 않는다).
- OQ-069: 후보 (A) — Maker Hooks가 있으면 Desert Power의 2 Persuasion은 Persuasion 갈래를 고를 때까지 쓸 수도, Command (6+)에 셀 수도
  없다; 고르기 전에는 Reveal을 끝낼 수 없다. 오전의 "2를 쓰면 sandworm을 닫는다"(통합 리뷰 R4)는 없어졌다.
- OQ-064·065: 사용자가 사실 확인을 물었다(Coercive Negotiation은 contract bank가 3장 미만일 때만, 강제 Spy 이동은 Research Station·Spice
  Refinery에서 Spy 12개가 모두 놓였을 때만 생긴다). 판정 전까지 현재 convention을 유지한다.
- 버전: `ACTION_CODEC_VERSION` 108 → 109(`recall_conflict_agent_for_agent_card`는 Bloodlines 카탈로그, `recall_conflict_agent_for_contract`는
  CHOAM+Bloodlines 카탈로그). 카탈로그 기본 4,424·CHOAM 4,715·CHOAM+Bloodlines 11,252·전 확장 33,004 → 33,006. 5081 이관(v107 → v109): 유지
  32,980·새 26·삭제 7. `OBSERVATION_VERSION` 20 유지. 이 판정들이 닿는 판은 드물어 golden 인코딩·문제집·census 고정 판은 그대로 복원된다.

## 새 open question

OQ-062(Servo-Receivers의 Signet Ring 아이콘, DECIDED), OQ-063(Hungry for Spice의 "in a single turn", DECIDED), OQ-064(Coercive
Negotiation이 가져갈 contract가 없을 때, OPEN), OQ-065(강제 Spy 이동에 갈 곳이 없을 때, OPEN), OQ-066(Reclaimed Forces의 "acquire"와
Call to Arms, OPEN), OQ-067(두 Intrigue 더미가 빈 Captured Mentat·Guild Spy, DECIDED), OQ-068(Recall Agent와 Into the Fray Agent, OPEN),
OQ-069(Desert Power와 Command (6+), OPEN). OPEN 다섯은 현재 동작을 적은 채 사용자 판정을 기다린다.

## 버전과 학습

`ACTION_CODEC_VERSION` 107 → 108(새 거절·회수·선택 행동, Grasp Arrakis·Tenuous Bond의 시점 정리 등). `OBSERVATION_VERSION` 20 유지
(인코더 파일은 바이트 동일, `FrameKind.LEADER_SIGNET`은 끝에 붙어 기존 인덱스 불변). 형식 2 체크포인트는 v108로 이관된다(5081: 유지
32,980·새 24·삭제 7; 통합 리뷰 전에는 새 23 — 리뷰가 `decline_acquisition_spy`를 더했다). 규칙이 넓게 바뀌어(기본판 카드 포함) 기존 체크포인트와 대전 수치는 모두 옛 규칙의 것이다.
