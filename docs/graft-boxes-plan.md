# 접합 두 칸을 처음부터 따로 제시하기 (계획)

2026-10-12. 사용자 결정으로 진행한다. 이 문서는 단계별 작업자가 읽는 설계의 기준이다.

## 1. 배경

- 사용자 피드백(2026-10-11, 친구 판 뒤): "카드 효과 보기가 불편하다. '카드 효과 해결' 이거 일단 상당히 보기 불편해. … 접합했을 때도 왜 다른 접합한 카드 효과 보기를 또 눌러야 그렇게 되게 한거야."
- 화면만 고친 중간안(`fb12-graft` `0282fb48`: 버튼에 카드 이름과 효과)을 넘어 사용자가 고른 것: "엔진이 두 칸을 처음부터 따로 제시하게 바꾸는게 좀 더 근본적인 해결 아닐까?" → 비용 설명 뒤 "그럼 완전한 방식으로 진행하자" → 계획에 "그래 추천한 대로 진행해보자".
- 추천대로 정한 것: (1) 한 칸의 묶음 선택이 진행 중일 때는 다른 칸 버튼을 숨긴다, (2) Ghola + Stitched Horror 결함을 같이 고친다, (3) AI 관측에 두 칸의 카드 정보를 더한다(관측 v31).

## 2. 규칙 근거

- "You gain the effects on both cards, in addition to the board space effects, in any order you choose." `[Immortality pp. 10-11]` (`rules/graft.py` docstring, [rules/immortality.md](rules/immortality.md) 5절).
- 두 box는 space 효과와 같은 자유 순서 그룹에 든다(OQ-027, immortality.md 121행). 아이콘마다 해결(OQ-027 확장).
- 이 작업은 **규칙 결과를 바꾸지 않는다.** 바뀌는 것은 결정의 모양(어떤 행동이 언제 제시되나)뿐이다. 예외: 4.5절의 결함 수정(Ghola + Stitched Horror)은 결과가 바뀐다. 근거는 "Ghola는 상대 카드의 Agent box 전체를 복사한다" `[Immortality p. 14]`와 같은 원칙의 기존 처리(Ghola + Long Reach는 자기 영향력 둘을 따로 고른다, 코드 `graft.py`·AE:1123-1125, 테스트 `test_immortality_imperium.py:731`)다. 이 원칙을 OQ-057 (12)에 글로 남긴다(지금은 코드에만 있다).

## 3. 바뀐 뒤의 모습

접합한 Agent turn의 결정 창:

```
[실험 — 에이전트 칸]
   연구 트랙 1칸 전진
[계획된 교배 — 에이전트 칸]
   이 카드 폐기 → …
   카드 1장 뽑기
[보드 칸 효과]
   스파이스 수확 …
```

- `switch_graft_card`("다른 카드 칸 해결")가 없어진다. 두 칸의 행이 처음부터 함께 나오고, 어느 칸의 행이든 한 번 눌러 그 효과를 해결한다.
- 모든 행은 실제 효과로 이름 붙는다(중간안의 표시 작업을 그대로 쓴다).
- 한 칸에서 여러 단계가 한 묶음인 선택이 진행 중이면(4.3절), 그 묶음이 끝날 때까지 다른 칸의 행은 숨긴다.

## 4. 설계

### 4.1 고정된 두 칸

- 칸 0 = 놓은 카드(`agent_turn`의 `card_id`), 칸 1 = 접합 짝(`choose_graft_partner`). 이 배정은 그 turn 동안 바뀌지 않는다. "활성 칸"을 맞바꾸는 일은 없어진다.
- 엔진 안쪽은 기존 box 기계(`active_agent_card`, `_effect_subject`, 각 provider·apply)를 그대로 쓴다. 칸 1의 행동은 **가상 교환**으로 처리한다: 칸 1의 행 목록은 frame 문맥을 칸 0↔칸 1로 바꾼 사본으로 계산해 `box=1`을 붙이고, `box=1` 행동의 적용은 문맥을 바꿔 기존 apply를 부른 뒤 다시 바꾼다. 그래서 "다른 접합 카드"를 읽는 도우미(`other_grafted_card_id`, `_partner_icon_count`, Chairdog, Dissecting Kit, Pheromones, Stillsuit, `_bond_block`)는 의미가 그대로 맞는다.
- 가상 교환이 옳으려면 **칸에 딸린 문맥 키를 빠짐없이** 함께 바꿔야 한다. 4.2절 표의 키를 기준으로 하고, frame 문맥의 모든 키가 "칸별" 또는 "turn 전체"로 분류됐는지 확인하는 테스트를 둔다(새 키가 생기면 분류하지 않은 채로 지나가지 못하게).

### 4.2 문맥 키 분류 (조사 결과, master `5cb16976` 기준)

| 분류 | 키 |
|---|---|
| 칸별(칸 0 / 칸 1 쌍) | `card_id`/`graft_card_id`, `pending_agent_effect`/`graft_pending_effect`, `pending_agent_icons`/`graft_pending_icons`, `agent_card_self_trashed`/`graft_card_self_trashed`, `influence_chosen`/`graft_influence_chosen`(지금은 두 칸이 모두 "Choose two"일 때만 교환 — 늘 칸별로), 그리고 지금 쌍이 없는 것: `rewards_chosen`(Stitched Horror, 4.5절 결함), `trashes_remaining`(Ruthless Leadership·The Beast's Spoils), `corrinth_first_card_id`, `agent_card_spy_pending`·`agent_card_spy_recalled`(Arrakis Observer), Signet 단계 키(`feyd_track_stage`, `feyd_spy_recalled`, `leader_spy_recalled`, `staban_bonus_post`, `listeners_paid`, `signet_rewards`), 화살표 지불 뒤 대기하는 보상 아이콘(Piter, Branching Path, Captured Mentat, Guild Spy, Elite Forces, Pivotal Gambit) |
| 카드에 묶임(칸과 무관) | `BOOST_DRAW_KEY`(Urgent Shigawire의 추가 뽑기 — 그 카드를 이름으로 가리킨다), `research_resolved_card_ids` |
| turn 전체 | `turn_owner`, space 관련 키, `space_influence_replaced`, `partner_waives_influence` 등 |

작업자는 이 표를 출발점으로 삼되 코드에서 모든 키를 다시 확인한다. 표에 없는 키를 찾으면 분류해 이 문서에 더한다.

구현에서 확인한 최종 분류(2026-10-12, `rules/graft_boxes.py`):

- 칸별 쌍(16): `card_id`/`graft_card_id`, `pending_agent_effect`/`graft_pending_effect`, `pending_agent_icons`/`graft_pending_icons`(화살표 비용 뒤의 보상 아이콘도 여기 대기한다), `agent_card_self_trashed`/`graft_card_self_trashed`, `influence_chosen`/`graft_influence_chosen`, 그리고 새 쌍 `rewards_chosen`, `trashes_remaining`, `corrinth_first_card_id`, `agent_card_spy_pending`, `agent_card_spy_recalled`, `feyd_track_stage`, `feyd_spy_recalled`, `leader_spy_recalled`, `staban_bonus_post`, `listeners_paid`, `signet_rewards`(각각 `graft_` 접두의 짝).
- 카드에 묶임: `boost_draw_card_id`, `research_resolved_card_ids`.
- turn 전체: `graft_active_box`(새 키: 지금 `card_id` 쪽에 있는 칸 번호, 없으면 0), `turn_agent_recalled`, `space_influence_replaced`, 배치·회수 키(`combat_*`, `existing_troop_deployment_limit`, `undeployable_troops`, `units_deploy_blocked`, `pending_combat_deployment`), 턴 종료 키(`finishing`, `finish_*`), space·board 키, `troops_recruited`, `commanders_recruited`, `pending_*` 그룹 플래그, `cost_option`, `turn_owner`, `imperial_privilege_intrigue_resolved`, `espionage_spy_recalled`, `pending_tech_acquire_effects`.
- `partner_waives_influence`·`occupied`·`placed_reaches`·`infiltrate_post_id`는 effect frame이 아니라 graft 상대 frame의 키다.
- 지키는 장치: `swap_boxes`는 분류되지 않은 키를 만나면 멈추고(`RuntimeError`), `tests/unit/rules/test_graft_boxes.py`가 rules/의 모든 문맥 키(정적 스캔)와 무작위 전 옵션 판의 effect frame 키를 분류와 대조한다.

### 4.1a 구현 메모: 교환을 되돌리지 않는다

4.1의 "적용 뒤 다시 바꾼다"를 그대로 하면, 칸 1의 행동이 올린 하위 frame(Long Live the Fighters, Research 방향, Spy 배치, 계약 등)이 끝나며 effect frame에 쓰는 값이 칸 0으로 간다. 그래서 행동한 칸을 `card_id` 쪽에 그대로 두고(`graft_active_box`로 기록), 다른 칸의 행동이 올 때 다시 바꾼다. 칸 번호(0 = 놓은 카드, 1 = 짝)와 행의 `box=1`은 바뀌지 않고, 행 목록·관측·화면은 언제나 고정 번호로 읽는다(`agent_effect_frame.agent_box_rows`, `route_box_action`, `core.observation.agent_box_cards`). 옛 엔진의 "switch 뒤 행동"과 새 엔진의 "`box=1` 행동"이 같은 상태를 만들므로 결과가 그대로라는 근거도 된다. 잠금(4.3)은 활성 칸만 진행 중일 수 있다는 불변식 위에서 한 술어(`agent_effects.box_in_progress`)로 판정한다.


### 4.3 묶음 진행 중 잠금

다음이 진행 중이면 그 칸의 행만 내고 다른 칸의 행(과 칸에 속하지 않는 다른 행은 지금처럼)을 숨긴다: "Choose two"의 첫 선택 뒤(Long Reach, Stitched Horror — OQ-057 (4) 원자성), Corrinth City의 고르기→지불, Arrakis Observer의 버리기→Spy, Ruthless Leadership·The Beast's Spoils의 남은 폐기, Signet 단계, 화살표를 지불한 뒤의 보상 아이콘 대기. 지금 `legal_graft_switch_actions`의 docstring은 이 제한을 말하지만 코드는 검사하지 않는다(조사 결과 함정 5). 이 판정을 한 곳(예: `box_in_progress(context, box)`)에 모은다.

### 4.4 턴 종료와 소멸 판정

- `agent_card_effect_is_unavailable`(활성 칸만, 상태 id로 캐시), `graft_boxes_are_stalled`(교환을 흉내 냄), `apply_agent_turn_finish`의 교환 반복(`combat_deployment.py:752-779`), `legal_agent_turn_finish_actions`(활성 칸의 막힘만 무시)를 두 칸을 각각 보는 방식으로 바꾼다. 결과(언제 턴 종료가 열리는지, 무엇이 소멸하는지)는 지금과 같아야 한다.

### 4.5 기존 결함과 확인할 것

1. **Ghola + Stitched Horror**: `rewards_chosen`이 칸별로 나뉘지 않아, 두 번째 칸이 남은 2개만 제시받고 한 번 고르면 첫 칸의 보상을 다시 준다(조사에서 메모리로 재현: water 3→4, Tleilaxu 1→2). 칸별 키로 고친다. 회귀 테스트와 OQ-057 (12) 문구.
2. **Urgent Shigawire + 베네 게세리트 접합 짝**: 짝 카드가 BG일 때 any-icon은 쓰지만(`graft.py:155-164`) 추가 뽑기를 기록하지 않는 것으로 보인다(`agent_turn.py:449-452, 518`은 놓은 카드만). 먼저 [rules/](rules/)의 Urgent Shigawire 문구·판정과 대조한다. 문서가 답하지 않으면 고치지 말고 `open-questions.md`에 OQ로 올려 사용자 판정을 받는다.

### 4.6 행동 목록 (codec v143)

- 칸에 따라 뜻이 달라지는 행동(조사 결과 1,987 템플릿: `resolve_agent_card_effect` ±`effect` 12, 지불 748, 선택 735, Signet 492)에 **`box=1` 변형**을 더한다. 인자가 없는 기존 행동은 칸 0을 뜻한다(Servo-Receivers의 Signet 창과 Kota의 보상, Shigawire 추가 뽑기 같은 칸 밖 출처도 그대로 쓴다).
- Immortality 카탈로그에만 더한다(접합이 없는 카탈로그는 그대로, base 4,413 고정 테스트 유지). 전 옵션 33,986 → 약 35,973, Immortality만 9,261 → 약 10,639.
- `switch_graft_card`를 뺀다. `ACTION_CODEC_VERSION` 142 → 143.
- 엔진 디스패처(`engine.py:403`)가 `effect` 키 유무로 아이콘/box를 가르고, 기록 다리(`migration.py:436`)가 인자 키가 정확히 `("effect",)`인지 본다 — `box` 키를 더할 때 둘 다 맞춘다.
- 칸 1의 `trash_grafted_card_for_influence(card_id)`·`trash_grafted_card_for_specimen`·`trash_agent_card_self_for_vp`는 칸에 상대적인 뜻이므로 가상 교환으로 그대로 맞는다.

### 4.7 관측 v31

- 지금 관측에는 "어느 카드가 칸 0/칸 1인지"가 없다(조사 결과 함정 10). 끝에 작은 구간을 붙인다: 열린 Agent turn의 칸 0·칸 1 카드 identity(개인 카드 우주 index+1, 없으면 0), 각 칸의 대기 여부. `OBSERVATION_VERSION` 30 → 31, golden digest 다시 고정, [rl-environment.md](rl-environment.md)에 버전 줄.

### 4.8 체크포인트 이관

- 지금 `_migrate`(`training/checkpoint.py:463-531`)는 `(action_id, arguments)`가 정확히 같을 때만 행을 옮긴다. 별칭 표를 더한다: 새 `box=1` 행은 같은 행동의 칸 표시 없는 행에서 복사해 시작한다(`_gather_rows`는 중복 원본을 허용하고, `_migrate_optimizer`가 같은 원본을 쓰므로 Adam 모멘트도 따라온다). 복사한 행은 학습된 행으로 센다(heuristic 대체 대상이 아니다).
- `switch_graft_card` 행은 버린다. 새 관측 열은 0에서 시작한다.

### 4.9 AI

- heuristic(`agents/heuristic_agent.py`): switch 점수(164, 263-276, 1162-1175)를 없애고 `box=1` 행을 칸 표시 없는 행과 같은 기준으로 점수 매긴다. 같은 행동이 두 칸에 있을 때(Ghola) 끝없는 반복이 없어야 한다.
- 앱 AI(`agents/app_ai/windows/agent_effects.py` 외): 지금은 복사한 상태에서 교환해 짝 칸을 평가한다(`_Partner`·`_partner_box`·`_decide_with_partner` 3861-4135). `box=1` 행을 직접 평가하도록 바꾼다. 결정 결과가 지금과 같은지 기존 테스트(877, 908 등)로 확인한다.
- 탐색 AI(`agents/network_search_agent.py`): 순환 방지(`_Taken` 135-175)와 효과 순서 greedy(508-520)를 점검한다.

### 4.10 기록 변환 (codec 143 미만)

- 옛 기록에서 같은 Agent turn 안의 `switch_graft_card`는 지우고, 그 뒤 활성이던 칸이 짝(칸 1)인 동안의 칸 행동에 `box=1`을 붙인다. 행동 순서는 그대로라 새 엔진에서 같은 상태로 이어져야 한다. 단, 옛 엔진이 한 칸의 묶음 선택 도중에 switch한 순서는 4.3의 잠금 때문에 이어지지 않는다(v142 묶음 2,000판 중 3판, [human-records.md](human-records.md) 2절). 순서를 바꾸는 다리는 두지 않았다.
- 지금의 다리는 상태 없고 수를 지울 수 없다(`records/migration.py` `Bridge` 77-104). "지금 어느 칸이 활성인가"를 따라가는 새 변환이 필요하다: 기록 단계에서 하는 다시 쓰기(옛 수 → 새 수, 또는 없음)로, 옛 엔진의 활성 칸을 추적한다. 같은 `effect=cards`가 짝의 아이콘인지 Shigawire 추가 뽑기인지처럼 모호한 경우는 옛 엔진의 라우팅(AE:3777: 추가 뽑기를 먼저)을 따라 판정한다.
- 같이 고칠 다리: `_named_card_effect`(407-438), `_shigawire_draw`(567-607), `_reward_icon`·`_piter_reward`(675-743), `_reverse_engineering_reward`(749-797), `rewrite_step`(문제집의 망 후보).
- 판정 수 자체가 `switch_graft_card`인 문제집 포지션은 새 엔진에 같은 수가 없다. 개수를 세고 이유를 적어 뺀다.
- 기록 fixture(`tests/unit/records/data/v141-*.json`: switch 1~6회)를 새 다리로 옮겨지는지 확인한다.

### 4.11 화면

- 결정 창의 행을 카드별 머리글("<카드> — 에이전트 칸")로 묶는다(지금 행은 평평하다). 행 이름은 중간안의 `detail_title`·`detail` 그대로.
- `server/turn_cards.py`(이번 차례 카드·`box_losing_trash`), `server/turn_end.py`(`_only_blocked_icons_wait`), `display/actions.py`, `display/unavailable.py`(행 키 `agent_box:{card}` 등), labels를 칸별로 맞춘다.

## 5. 단계와 검증

| 단계 | 내용 | 확인 |
|---|---|---|
| 1 | 엔진(4.1~4.5) + codec v143(4.6) + 관측 v31(4.7) + 체크포인트 별칭(4.8) | 접합·Immortality 규칙 테스트 전부(OQ-022·OQ-027·OQ-054·OQ-055·OQ-057·Ghola·Chairdog·Usurp·Pheromones·Dissecting Kit·Subversive Advisor·Stillsuit·Long Reach), 문맥 키 분류 테스트, 두 칸 행 동시 제시와 잠금 테스트, codec·관측·이관 테스트 |
| 2 | AI 셋(4.9) | 자동 대전 소크: Immortality 포함 구성에서 random·heuristic·app_ai 수백 판, `--soundness-interval`·`--privacy-interval`, 막힘·불법 0 |
| 3 | 기록 변환(4.10) | `dune-imperium-records check`(로컬 저장본), `problems check`(285곳, 빠지는 곳은 이유), `corpus check local/records-corpus/v142-c29f79d1`(2,000판, 갈라짐 0이 목표) |
| 4 | 화면(4.11) | e2e: 접합 차례의 카드별 묶음, 칸 1 행 한 번 클릭 해결, 잠금 중 숨김, 기존 e2e 전부 |
| 5 | 독립 리뷰(엔진·기록), 전체 pytest·ruff·mypy·e2e, 병합 | |
| 6 | 재적응(대조군 승자독식 / 실험 갈래 `--score-rewards`) | 시작 전 사용자 확인 |

- 2·3·4단계는 1단계 뒤 서로 독립이라 함께 진행할 수 있다.
- 궤적에 묶인 테스트(중간안 작업에서 확인): tips-v1 문제집 다시 캐기, tip census 4개, `test_turn_end`의 Harvest Cells 경로(seed), `test_record_migration`의 seed-1 fixture가 다시 고정해야 할 수 있다. 다시 고정할 때는 왜 바뀌었는지(결정 모양)를 커밋에 적는다.
- 병합 뒤 v142 저장본은 서버가 불러오지 못한다(진행 중인 판은 병합 전에 끝낸다). 끝난 판의 기보는 4.10의 변환으로 계속 쓴다.
