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

## 사용자 판정 (2026-09-26)

- Tenuous Bond·Grasp Arrakis·Battlefield Research: 칸의 색띠와 카드 아래의 시점 인쇄(COMBAT / ENDGAME, PLOT / COMBAT)대로 칸마다 한
  시점만 허용한다(두 시점을 모두 연 이전 전사는 오류).
- Coercive Negotiation: 조건이 되면 반드시 수행한다(거절 없음).
- False Orders: 공식 FAQ대로 영향을 받은 상대는 이번 turn에 Agent를 보낸 공간에 **연결되지 않은** 빈 post로 Spy를 옮긴다 `[FAQ p. 2]`.
  Holy War도 문구가 같아 같은 판정을 적용한다(프로젝트 판정). OQ-036 (b) 갱신.

## 새 open question

OQ-062(Servo-Receivers의 Signet Ring 아이콘, DECIDED), OQ-063(Hungry for Spice의 "in a single turn", DECIDED), OQ-064(Coercive
Negotiation이 가져갈 contract가 없을 때, OPEN), OQ-065(강제 Spy 이동에 갈 곳이 없을 때, OPEN), OQ-066(Reclaimed Forces의 "acquire"와
Call to Arms, OPEN), OQ-067(두 Intrigue 더미가 빈 Captured Mentat·Guild Spy, DECIDED), OQ-068(Recall Agent와 Into the Fray Agent, OPEN).
OPEN 넷은 구현 convention을 적용한 채 사용자 판정을 기다린다.

## 버전과 학습

`ACTION_CODEC_VERSION` 107 → 108(새 거절·회수·선택 행동, Grasp Arrakis·Tenuous Bond의 시점 정리 등). `OBSERVATION_VERSION` 20 유지
(인코더 파일은 바이트 동일, `FrameKind.LEADER_SIGNET`은 끝에 붙어 기존 인덱스 불변). 형식 2 체크포인트는 v108로 이관된다(5081: 유지
32,980·새 23·삭제 7). 규칙이 넓게 바뀌어(기본판 카드 포함) 기존 체크포인트와 대전 수치는 모두 옛 규칙의 것이다.
