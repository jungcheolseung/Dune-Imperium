# 앱식 AI(app_ai) — 설계와 구현 계획

상태: **완료** (2026-10-05 작성·구현·A/B, master 병합). 브랜치 `app-ai`(worktree), 기준 master `60707f8b`(codec v133, 관측 v30).
뼈대 커밋 `279dffd8`.
확장판(Immortality·Epic·Go to 11·프로모·지도자 드래프트·Bloodlines·Arrakeen Scouts): **진행 중**, 브랜치 `app-ai-expansions`(11절).

## 1. 사용자 결정

2026-10-05, 앱 AI 분석(`assets/reference/dune-steam-app/dad97e20…/analysis/ai/ai-policy-report-ko.md`) 직후:

> "앱식 heuristic 만들어서 A/B 돌려보자. 앱의 ai와 최대한 동일하게 동작하게끔 구현해야해. 분석한 앱ai의 정책, 설정 등을
> 최대한 똑같게. 내가 새로 ai를 만드려는 이유가 앱ai보다 더 좋은 ai, 난이도 높은 ai와 게임하고 싶어서이고, 나보다 더 잘 하는
> ai에게 배우고 싶기도 하기 때문이야."

- **충실도 우선.** 앱 AI의 정책·상수·카드별 판단을 그대로 옮긴다. 앱의 버그로 보이는 동작(High Council 이중 계산, Shaddam 배치
  반전, Smuggler's Haven·Arrakis Revolt 지불 조건 반전, Sietch Ritual 세력 혼동 등)도 **그대로 재현**한다. 더 강한 AI는 이것과
  별개로 만든다.
- **위치: 모두 공개 저장소**(사용자 선택, 비공개 플러그인 안을 제시한 뒤). 2026-10-03의 "앱 코드·AI 상수를 저장소에 옮기지 않는다"는
  결정은 이 agent에 한해 사용자가 바꿨다. 앱은 여전히 규칙 출처가 아니다(`AGENTS.md`).
- 목표는 A/B: app_ai 대 우리 heuristic, 그리고 우리 학습 망·search agent 대 app_ai.

## 2. 출처

모두 로컬 에셋 체크아웃 `reference/dune-steam-app/dad97e2021144d45b5b4f022e07bd3b3/`(git 추적 밖). 앱 4.1.2.1808.

- `analysis/ai/01…18-*.md`: 앱 AI 분석(2회, 각 파일 끝의 Errata가 본문보다 우선).
- `analysis/ai/spec/`: 구현용 사양. 앱 쪽 11갈래, 각 갈래를 독립 agent가 역어셈블로 재검증(반박 0, 무작위 대조 230건 중 오류 1건).
  - `generic-abilities.md`, `imperium-a.md`, `imperium-b.md`, `intrigues.md`, `board.md`, `leaders.md`
  - `profile-economy.md`, `profile-influence-uprising.md`, `profile-combat.md`
  - `engine-order.md`: 앱 엔진이 어떤 순서로 무엇을 AI에게 묻는가(이 설계의 중심)
  - `archetypes.json`/`.md`, `constants.json`/`.md`: 추출 스크립트 출력
- 우리 엔진 지도(세션 scratchpad, 필요한 내용은 이 문서 5절에 옮김): R1 turn·agent_effects, R2 reveal, R3 combat, R4 intrigue,
  R5 콘텐츠·관측, R6 Spy·계약·지도자.

재현: `scripts/dwgr/app_archetypes.py`, `scripts/dwgr/app_ai_constants.py`가 덤프에서 JSON을 만들고,
`scripts/dwgr/app_ai_emit.py`가 `agents/app_ai/data/{constants,archetypes}.py`를 만든다(그 뒤 `ruff format`). 앱이 업데이트되면
덤프를 다시 뜨고 세 스크립트를 다시 돌린다.

## 3. 구조 (`src/dune_imperium/agents/app_ai/`)

| 모듈 | 내용 |
|---|---|
| `data/constants.py` (생성) | `AIConstants` 437필드(앱 getter 이름 그대로), `HARD`/`MEDIUM`/`EASY`, `TABLES` (AILevel → 표) |
| `data/archetypes.py` (생성) | 앱이 정의한 아키타입 508개 전부의 속성과 능력 목록. `in_uprising`/`in_uprising_choam`은 4인 Uprising(±CHOAM)에서 앱이 실제로 나눠 주는지 |
| `catalog.py` | 우리 id ↔ 앱 아키타입 대응표와 `Entity` 생성 |
| `entities.py` | `Entity`(우리 id + 앱 아키타입), `Kind`, `Attr` |
| `context.py` | `AppContext`: 좌석이 읽어도 되는 것만 읽는 상태 접근(정직성 규칙의 유일한 자리) |
| `summer.py` | `AIValueSummer` 포트(`add`, 누적합에만 곱하는 `multiply`), `app_round`(Convert.ToInt32 = 은행가 반올림) |
| `choice.py` | `MakeChoice`: 전부 섞고 → 0 초과만 → 값 내림차순 안정 정렬 → 첫째; 없으면 빈 답 |
| `profile/core.py` | `WormAIProfile` 메서드 선언 전부(계약). 구현은 `economy.py`·`influence.py`·`combat.py` 세 mixin |
| `abilities/` | 앱 능력 클래스 포트. `@port("<앱 전체 클래스명>")`로 등록, 앱 상속 구조를 그대로 따른다 |
| `windows/` | 우리 결정 창 → 앱 질문 → 우리 행동. 창별 `HANDLERS` |
| `agent.py` | `AppAIAgent(seed, level)`: `StateAgent`. 대응 안 된 결정은 앱의 `DefaultRandomChoice`처럼 합법 행동 중 무작위로 답하고 `fallbacks`에 센다(heuristic은 섞지 않는다, 11절) |

registry: `app_ai`(Hard), `app_ai_medium`, `app_ai_easy`.

## 4. 충실도 원칙

1. **앱이 묻는 질문은 앱의 평가로 답한다.** 우리 창의 합법 행동을 앱 질문의 후보로 바꾸고, 앱 능력의 `Evaluate`/`ValueForPlayer`
   값으로 `make_choice`를 돌린다.
2. **앱이 엔진 고정 순서로 처리하는 것은 그 순서를 따른다.** 우리 엔진은 Agent 턴 효과 순서를 플레이어가 고르게 한다(OQ-027).
   app_ai는 앱 단계 순서대로 고른다: 칸 효과(앱 state 400) → 카드의 기본 Agent 상자(500) → 즉시 처리 능력(600, `CanRunImmediately`)
   → 행동 뒤 질문(Optional/Warn/Explicit 지연 능력, Plot, 지도자 능력, 병력 투입 0.5 등을 값으로 경쟁) → 0 초과가 없으면
   `finish_agent_turn`. `engine-order.md` §3–4.
3. **`DeferredThresholdReached`를 재현한다.** 이번 턴 카드·칸·손의 책략·해당 계약의 `DeferValue` 합이 3 이상이면, 뽑기·칸 영향력·
   계약 획득이 자동 처리에서 행동 뒤 질문으로 넘어가 값으로 순서가 정해진다(`engine-order.md` §4.1–4.2).
4. **Plot은 앱의 세 창에서만 쓴다.** 턴 시작, Agent 행동 뒤(우리 `agent_effects`에서는 `finish_agent_turn`이 합법일 때만), Reveal 뒤.
5. **우리 엔진만 묻는 질문은 앱 엔진이 실제로 하는 쪽으로 답한다.** `withdraw_troops`는 쓰지 않고, Reveal 선택 미루기
   (`defer_reveal_choice`)는 앱의 Reveal 효과 순서가 요구할 때만 쓴다. 효과 순서 결정도 2번에 따른다.
6. **앱이 한 번에 답하는 것을 우리가 여러 단계로 물으면**, 첫 단계에서 앱 답을 계산해 `Memory.intents`에 두고 이어지는 단계에서 쓴다.
7. **동점은 앱처럼 무작위**로 깨되 agent의 시드 RNG로 한다(앱은 시계 시드). 한 출처 안의 동점은 앱 목록 순서상 "먼저 나온 엄격한
   최댓값"(`first_strictly_best`).
8. **정직성**: `AppContext`만 거쳐 상태를 읽는다. 자기 덱 구성과 상대의 손패∪덱 구성(순서·분할 제외)은 프로젝트 관례상 아는 정보다
   (`agents/determinize.py`). `test_choices_ignore_hidden_zones`가 숨은 영역을 다시 섞어도 같은 답을 내는지 검사한다.
9. **결정성**: 무작위는 agent의 `random.Random(seed)`에서만 뽑고, 문자열 set 순회 순서에 기대지 않는다(저장 재생이 다시 묻는다).
10. **앱 숫자 그대로**: 상수는 `data/constants.py`, 카드 값은 `data/archetypes.py`에서만 읽는다. 코드에 숫자를 옮겨 적는 것은 앱
    코드 안의 리터럴(예: 10 VP 두 배, Swordmaster 50 같은 상수가 아닌 리터럴)뿐이며, 그때는 주석에 출처 메서드를 적는다.

## 5. 결정 창 대응 (요약; 자세한 것은 `engine-order.md`와 엔진 지도)

| 우리 창 | 앱의 대응 | 핵심 |
|---|---|---|
| `turn` | `DetermineTurn`(강제 아님) | 손패 카드×칸 쌍의 `AgentAbility.Evaluate`(칸 능력들의 `ValueForPlayer(me,[card])` + 카드 `ValueForPlayer(me,[space])`, 카드 Reveal 가치 ×−0.5 포함), Plot `Evaluate`, 지도자 능력. 0 초과 없음 → `reveal_turn`. Infiltrate의 Spy와 Gather Support·Spice Refinery 비용 선택은 앱이 배치 뒤 자기 `Evaluate`로 정하므로, 같은 판단으로 `agent_turn` 인자를 고른다 |
| `agent_effects` | state 220–700 + 행동 뒤 질문 | 4절 2–4번 |
| `reveal` / `reveal_choice` | Reveal 효과 순서 + 구매 루프 | `AcquireValue` 최댓값(0 초과, 최소 가치 미만은 0)을 한 장씩; Plot·지연 능력과 같은 목록; 0 초과 없음 → `finish_reveal` |
| `acquisition_spy`, `spy_placement`, `*_spy` | `PlaceSpyEvaluator`, `RecallSpyEvaluator` | 최고 관측소; 공급이 비면 거절하지 않고 가장 나쁜 관측소의 Spy를 회수한 뒤 배치 |
| `combat_intrigue` | 교전 책략 루프(강제 아님) | `StrengthIntrigueAbility.Evaluate`와 카드별 재정의; 빈 답 → `pass_combat_intrigue` |
| `combat_reward_*` | 보상 처리 창 | 앱이 묻는 보상만 평가(지불 VP, Spy 2개 회수 VP, Trash); 나머지는 자동 처리와 같은 쪽 |
| `control_defense` | 자동(앱은 묻지 않음) | 앱 엔진 동작대로 |
| `endgame_intrigue` | 자동 플레이 | 쓸 수 있는 종료 책략은 모두 쓴다; battle icon 짝은 앱의 `ScoreBattleIconsPairs` 순서 |
| `intrigue_choice`, `intrigue_effects` | 책략 `Evaluate`의 하위 답 | 4절 6번(의도 기억) |
| `contract_market`, `contract_reward_*` | `GetBestContract`, 계약 `Evaluate` | |
| `opponent_card_discard`, `long_live_fighters` | `ChooseDiscardEvaluator`, `LongLiveTheFightersEvaluator` | |

## 6. 알려진 차이 (재현할 수 없거나 규칙이 다른 곳)

- 앱 Reserve의 Foldspace ×6이 우리 엔진에 없다(앱의 구매 도우미도 Foldspace를 뺀다). Desert Power의 `Persuasion` 속성은 앱 0, 우리 2.
- 우리 계약 완료는 즉시·의무다. 앱은 일부 계약(Spy 배치, Agent 회수, Draw-2/TSMF/BG 문턱 초과)을 행동 뒤 질문에 둔다.
- 앱에는 턴 시작 지도자 능력(OtherMemories 등, timing None)이 있지만 우리 `turn` 창에는 없다.
- Irulan의 Imperial Birthright: 우리는 Emperor 2 도달 시 자동, 앱은 지연 능력.
- 교전 책략 루프에서 앱은 마지막으로 낸 사람에게 한 번 더 묻는다(상태가 같으므로 결정적 정책에는 차이 없음).
- 앱 AI는 지도자를 무작위로 고른다. 우리 대전은 지도자를 돌려 배정하므로(`--rotate-leaders`) AI 결정이 아니다.
- 각 창 구현에서 새로 찾은 차이는 이 절에 적는다.

Immortality·Epic·프로모(2026-10-05, 창 단계):

- Graft: 앱은 배치 전(AgentTurnPhase state 50)에 상대 카드를 묻고 우리는 배치 뒤에 묻는다. app_ai는 턴 창에서 앱 답을 계산해
  `graft_partner` 창으로 넘긴다. 두 Agent 상자의 순서(`switch_graft_card`)는 앱의 `chosenAgentAbilities` 순서를 따른다.
- Research에서 앱이 "칸 없음"으로 답하면(다음 칸 값이 모두 0 이하) 앱은 카드를 뽑고 움직이지 않는다. 우리 창은 반드시 움직이므로
  값이 가장 높은 칸을 고른다. c7r3·c8r6 보너스와 연구 칸 Trash는 앱에서는 행동 뒤 질문에 남아 나중에 쓸 수 있지만 우리 엔진은 바로
  묻는다.
- 표본 반환은 앱이 묻는 자리(턴 시작, 행동 뒤 질문, 병력 부족)에서만 하고, 우리 엔진이 효과 중간·교전 책략 우선순위에서 더 묻는
  것은 앱 엔진처럼 넘긴다.
- Pivotal Gambit + Economic Supremacy: 앱은 추가 영향력을 조용히 잃지만 우리 엔진은 묻는다. `GainAnyInfluenceConflictAbility`의 답
  (가장 좋은 진영)으로 답한다. Arrakis Revolt(OQ-026): 앱의 "내고 벽 유지" 답에 대응하는 합법 행동이 없으면 거절한다.
- Harvest Cells: 앱은 교전 해결 창에서, 우리는 보상 뒤 `conflict_end_trigger`에서 묻는다. 교전 때 정한 답을 다시 쓴다.
- Economic Supremacy의 두 지불은 앱이 한 질문에서 섞은 순서로, 우리는 인쇄 순서의 두 질문으로 묻는다. 자원이 달라 결과는 같다.
- 창이 모르는 카드·행동 id는 조용한 기본값 대신 대체(무작위, `fallbacks`에 셈)로 넘긴다. 그래야 census가 빈 곳을 보여 준다.

## 7. 구현 순서와 진행 상태

| 단계 | 작업 | 상태 |
|---|---|---|
| 0 | 뼈대·생성 데이터·registry·기반 테스트 | 완료 `279dffd8`, `8b741c18` |
| 1 | `catalog.py` 대응표 + 검사 | 완료 `e4643ff3` |
| 2 | 프로필 3묶음(economy, influence, combat) + 범용 능력 포트 | 완료 `0dc83504` |
| 3 | 카드별 능력 포트(Imperium a/b, 책략, 보드·Conflict·계약, 지도자) — 포트 245개 | 완료 `23feb286` |
| 4 | 결정 창 어댑터(turn, agent_effects, reveal, combat, intrigue, uprising) | 완료 `3f868f60` |
| 5 | 통합: app_ai 4좌석 100판(base·CHOAM 각 50, 지도자 회전) — 예외 0, 대체 0, 미포팅 0, 앱 로직 결정 60,361개, 판당 0.9초 | 완료 |
| 6 | A/B (9절) | 완료: [`evaluation/app-ai-2026-10-05.md`](evaluation/app-ai-2026-10-05.md) |

각 단계는 구현 agent가 코드와 테스트를 쓰고, 다른 agent가 역어셈블과 사양에 대조해 충실도를 반박 검증한 뒤, 메인 세션이 diff를 읽고
커밋한다. 수식마다 사양의 계산 예(예: `03`의 자원 가치 예)를 단위 테스트로 고정한다.

## 8. 검증

- 단위: 프로필 메서드·능력 포트마다 사양의 분기와 상수를 고정하는 테스트(`tests/unit/agents/app_ai/`).
- 통합: 4좌석 app_ai 게임 완주(CHOAM 유무), 같은 시드 재현, 숨은 영역 재배치 불변.
- 범위: `AppAIAgent.fallbacks`와 `abilities.UNPORTED`가 Uprising 기본·CHOAM 게임에서 0이어야 한다(목표). 대전 도구로 몇백 판 세어 본다.
- 전체 pytest·ruff·mypy와 E2E는 병합 전에 한 번.

## 9. A/B 계획

`dune-imperium-tournament --matches <rows> --rotate-leaders`와 `scripts/ab/paired.py`(시드 묶음 부트스트랩).

1. app_ai(Hard) 대 heuristic, 2:2 거울, base와 CHOAM 각각 500 시드, 두 번째 시드 묶음으로 확인.
2. app_ai 난이도끼리(Hard 대 Medium/Easy) — 난이도 차이가 실제로 나는지.
3. 학습 망(greedy, `checkpoint:…ext-v111/C/iteration_07081.pt`)과 search(`search:…`) 대 app_ai: 1 대 3과 2:2.

## 10. 열린 문제

- 앱 PlaceSpy가 공급이 빈 상태에서 회수한 Spy가 `HasRecalledSpyThisTurn`에 잡히는가(우리는 잡힌다, OQ-044 (d)).
- Feyd의 Pay-to-Trash를 빈 선택으로 쓰는 앱 동작(1 Solari만 내고 아무것도 안 버림)을 우리 엔진이 표현하지 못한다: 거절로 대응.
- 이 밖의 미추적 항목은 각 사양 파일의 UNTRACED 절.

## 11. 확장판과 앱에 없는 선택지 (2026-10-05~)

### 11.1 사용자 결정

app_ai가 Bloodlines·Arrakeen Scouts에서 heuristic으로 넘어간다는 보고 뒤:

> "아냐 휴리스틱의 결정이 섞이는 ai면 어차피 그걸로 플레이할 생각은 없어. 2,3으로 가자"

- **(2) 앱에 있는 것은 충실 포팅**: Immortality, Epic Game Mode, Go to 11, Uprising 프로모 3장(과 Immortality 프로모 Piter), 지도자
  드래프트. 사양은 `analysis/ai/spec/immortality.md`, `spec/epic-goto11-promo-draft.md`(각 파일 끝 Errata 우선).
- **(3) 앱에 없는 것은 앱식 확장**: Bloodlines 전체(Tech 모듈, Twisted Intrigue, Navigation, Sardaukar Commander와 Skill, 지도자와
  Signet, 계약 토큰, 프로모 Ruthless Leadership)와 Arrakeen Scouts.
- 새 카드의 값(AcquireValue·DeferValue·CombatValue 등): **"앱 데이터 규칙으로 자동"** — 앱 자신의 카드 데이터에 맞춘 규칙으로 만든다.
- 새 결정 종류: **"앱식 단순 판단"** — 얻는 것 − 내는 것 > 0이면 하고, 입찰은 남는 값까지, 상대 모형 없음.
- **heuristic을 섞지 않는다.** 대응 안 된 결정은 앱 엔진의 `DefaultRandomChoice`(합법 행동 중 무작위)로 답하고 `fallbacks`에 센다.
  목표는 모든 선택지 조합에서 `fallbacks` 0, `UNPORTED` 0.

### 11.2 충실 포팅 쪽의 매핑 결정

- **Go to 11의 VP 눈금.** 앱의 Go to 11은 1에서 시작해 11에서 끝나고(시작 VP는 4인에서 늘 1), 우리는 0에서 10이다(OQ-091). 순 10점은
  같으므로 app_ai는 모든 좌석의 VP를 우리 값 + 1로 읽고(`AppContext.vp`, `vp_offset`), 종료 점수를 `endgame_victory_points + 1`로
  본다. 이렇게 하면 앱 코드의 절대값(GetVictoryPointValue의 리터럴 10, 결정적 교전 판단 등)이 끝에서 앱과 같은 거리에 놓인다.
- **Epic + Go to 11**(우리 0→12)은 앱 로비가 막는 조합이라 앱 동작이 없다. 같은 +1 규칙으로 종료 점수 13(앱식 확장).
- **Immortality 보드.** 칸 조회는 `Board(choam, immortality)`를 받는다. Immortality에서 Research Station은
  `ResearchStationImmortality`이고, 앱의 칸 순서(`board_space_order`)에서는 다른 확장 칸들 뒤(CHOAM 칸 다음, typeIndex 649)로 간다.
- **Tleilaxu 카드**는 `CARD_ARCHETYPES`에 함께 둔다(인스턴스 id `tleilaxu:<id>:<n>`). Piter, Genius Advisor와 Uprising 프로모는
  앱의 `Promo` 아키타입 그대로다. 앱은 프로모를 나눠 주지 않아 `AcquireValue`가 비어 있으므로(0), 충실 포팅은 Hard에서 거의 사지 않는다.
  이것도 그대로 둔다.
- **Economic Supremacy**는 앱의 Rise of Ix 카드 그대로(`VictoryPoints` 4, battle icon 없음). VictoryPoints를 가진 유일한 Conflict라
  후퇴 종료 분기와 책략 "버리기" 판단이 달라지는 것도 그대로 재현한다.
- **지도자 드래프트**: 앱 AI는 남은 지도자 중 균등 무작위로 고른다. 그대로.
- 앱 엔진은 한 번에 묻고 우리는 여러 단계로 묻는 곳(Graft: 카드 쌍 + 칸을 한 번에 → 우리 `agent_turn(graft=True)` + `graft_partner`,
  Control the Spice: 지불 + 선택 trash)은 4절 6번(`Memory.intents`)으로 잇는다.

### 11.3 앱식 확장: 값 (앱 데이터 규칙)

앱 데이터에 없는 카드·타일·토큰은 **합성 아키타입**으로 만든다. 앱 아키타입과 같은 속성 이름(`PersuasionCost`, `AcquireValue`,
`DeferValue`, `IconList`, `FactionList`, `Persuasion`, `Strength`, `Tags`, `WormAbilityIDs` …)을 쓰고, 생성 스크립트가 우리 콘텐츠
정의에서 인쇄 숫자를 옮기고 아래 규칙으로 앱이 손으로 적는 값을 채운다. 생성 데이터는 앱 추출(`data/archetypes.py`)과 섞지 않고 따로
둔다. 짧은 이름은 `…Archetypes.AppStyle.<Name>`처럼 앱 이름과 겹치지 않게 한다(R8: Chani·Duncan·Piter·Liet·Esmar Tuek은 앱의 다른
카드다).

| 값 | 규칙 | 앱 데이터 근거 |
|---|---|---|
| Imperium `AcquireValue` | `PersuasionCost` + 비용별 앱 중앙값 차 {1: 0.0, 2: −0.1, 3: 0.0, 4: −0.2, 5: −0.2, 6: −0.2, 7: −0.2, 8: 0.0} | 앱 Main 카드 151장(BaseSet·Uprising·RoI·Immortality)의 `AcquireValue − PersuasionCost` 중앙값 |
| Tech 타일 `AcquireValue` | `2 × SpiceCost` | 앱 RoI 타일 18장 모두 정확히 2배(`spec/rix-tech.md`) |
| Tech 타일 `EarlyMod`/`LateMod`, 획득 효과 | 획득 효과가 같은 RoI 타일이 있으면 그 값(`rix-tech.md` §1.2 대응표), 없으면 없음(1.0) | |
| 그 밖의 값(`DeferValue`, 책략 `CombatValue`·`DeferValue`, `Tags` 등) | 앱 데이터에 맞춘 가장 단순한 규칙을 고르고, 규칙과 맞음 정도를 이 표에 적는다. 맞음이 나쁘면 같은 효과를 가진 앱 카드(가장 가까운 대응)의 값을 쓴다 | 생성 스크립트가 맞춘 결과 |

능력: 새 카드의 효과는 가능한 한 앱의 **범용 능력 클래스**(자원 획득, 뽑기, 병력, 영향력, Spy, 책략 획득, Strength 책략 등 — 이미
포팅된 `abilities/generic.py`)를 조합해 표현한다. 범용 클래스로 안 되는 효과만 `AppStyle` 능력 클래스를 새로 만들고, 값은 아래 11.4의
판단과 프로필의 기존 가격(`GetResourceValue`, `CardDrawValue`, `IntrigueValue`, `SpyValue`, 영향력 가치, 병력 가치 …)으로 매긴다.

### 11.4 앱식 확장: 새 결정 (앱식 단순 판단)

- **선택적 효과·지불**: 얻는 것의 가치 − 내는 것의 가치 > 0이면 한다. 가치는 프로필의 기존 가격으로만 잰다.
- **여러 보기 중 하나**: 각 보기의 가치로 `make_choice`(섞기 → 0 초과 → 내림차순 안정 정렬 → 첫째). 강제 결정에서 0 초과가 없으면
  `DefaultRandomChoice`.
- **강제 손실**(Scouts 손실 사건, 피해자 쪽 `opponent_unit_loss`·`opponent_spy_move` 등): 앱 자신의 손실 평가기
  (`ChooseDiscardEvaluator`, 책략 손실 칸)처럼 **잃는 가치가 가장 작은 것**을 고른다. 동점은 무작위.
- **입찰**(Scouts 경매): 상품 가치 − 입찰액의 자원 가치 > 0인 가장 큰 입찰액까지(남는 값까지). 상대 입찰 추정 없음. 0 초과인 입찰액이
  없으면 0을 낸다.
- **나중에 받는 것**(Scouts 비밀 선택, 임무 물품, 다음 라운드 보상): 지금 받는 것과 같은 가치로 보되, 게임이 그 전에 끝날 수 있으면
  (`is_final_round` 등 앱의 종료 판단) 0.
- **Commander**: 병력 가치(`troop_value`)에 Strength 비율을 곱해 병력처럼 보고, 붙은 Skill은 해당 효과의 가격으로 더한다. 재구매
  (2 Solari)는 위의 지불 규칙.
- **순서 질문**(우리 엔진만 묻는 효과 순서 등)은 4절 2번처럼 앱 엔진이 하는 순서, 앱에 없으면 우리 엔진이 주는 순서의 첫째.
- **앱에 판단 기계가 없는 효과**: 같은 종류의 효과를 앱이 다른 카드에서 값 매긴 선례가 있으면 그 계산을 그대로 쓴다(선례를 사양에
  적는다). 선례가 없으면 그 효과가 지금 주는 것의 1회 가격으로 본다. 상대에게 주는 손해와 정보(덱 엿보기)는 선례가 없으면 0.
  오래 가는 효과(Navigation의 영구 Persuasion 등)는 앱의 남은 라운드 판단(국면·종료 예측)으로 횟수를 셀 수 있으면 1회 가격 × 그
  횟수, 아니면 1회 가격.

### 11.5 R8·R9 지도의 열린 문제에 대한 결정

Bloodlines (R8):

- **Tech**: Rise of Ix 타일 기계(`spec/rix-tech.md`)를 충실 포팅해 바탕으로 쓰고(2단계), Bloodlines 타일은 11.3의 합성 아키타입으로
  그 위에서 값을 매긴다. 효과가 같은 RoI 타일 능력 클래스가 있으면 그대로 쓴다.
- **Commander**: 병력 1의 `troop_value` + 병력보다 높은 Strength 몫의 `strength_value` + 붙은 Skill 효과의 가격. 다시 사 오기
  (2 Solari)는 얻는 것 − 2 Solari 가치 > 0.
- **획득 효과의 0 가격**: 앱의 `GetAcquireEffectsValue`는 Intrigue·Trash·PlaceSpy·Contract 획득 효과를 0으로 본다. 앱은 같은 경우
  카드별 `SpecificAcquireBonus`로 값을 더했다(Chaumurky: Intrigue 하나당 `IntrigueValue`). 앱식 확장도 그 선례대로 카드별 보너스로
  그 효과의 가격을 더한다.
- **Agent 상자의 Bond**(Southern Faith, Possible Futures): In High Places의 Agent 상자 처리 방식을 쓴다.
- **Desert Scouts 후퇴**: 앱처럼 병력이 있으면 병력을 뺀다(Commander는 병력이 없을 때만).
- **피해자 쪽 결정**(`opponent_unit_loss`, `opponent_spy_move`): 11.4의 강제 손실 규칙(잃는 가치가 가장 작은 것).
- **한 번도 합법이 아니었던 id**(`hold_contract_icons` 등): 빈 답 또는 강제 단일 선택이라는 앱 엔진의 처리.
- **Command(6+)**: 우리 엔진은 Reveal에서 생긴 Persuasion으로 판정하므로(OQ-033) 구매가 Command를 깨지 않는다. Command 선택은 다른
  Reveal 효과처럼 활성 카드 순서대로 구매 전에 처리한다.
- **Twisted Intrigue**는 버림 더미에서 다시 섞이지 않으므로(OQ-097) Intrigue 덱 구성 추정에서 뺀다.
- Kota의 Secret Project와 Y'rkoon의 Navigation 칸은 주인에게만 보인다(`AppContext`가 주인에게만 노출).

Arrakeen Scouts (R9): 앱에 없으므로 모든 결정이 앱식 확장이다.

- 강제 손실 사건과 Political Equilibrium 동점: 잃는 가치가 가장 작은 것(11.4).
- 경매: 남는 값까지 입찰, 상대 입찰 추정 없음. 규칙의 동점 처리(1위 동점이면 2위 없음, 0 입찰은 이기지 못함)는 엔진이 한다.
- 지연 보상: 할인 없음. 그 전에 게임이 끝날 수 있으면 0(11.4).
- 하위 위원회(유일 자리 포함): 가장 좋은 줄이 0 초과면 참여. 상대에게서 자리를 빼앗는 가치는 보지 않는다.
- `scouts_lose_influence_to`(동맹 받는 이): 기존 app_ai 선례대로 먼저 제시된 이.
- Rebuild Infrastructure: 자원 가격으로 본다. 자원봉사 규칙은 자기 순이익 > 0이면 동의.
- Scouts 단계에서 뽑은 카드는 이번 라운드에 쓸 수 있으므로 앱의 `CardDrawValue`를 그대로 쓴다.

### 11.6 진행

| 단계 | 작업 | 상태 |
|---|---|---|
| 기반 | 모든 앱 아키타입 추출, Go to 11 VP 눈금, heuristic 대체 제거, `Board`, Immortality·Epic·Tleilaxu·프로모 대응표; 지도자 드래프트 창(균등 무작위, 앱 그대로) | 완료 `fca021f2`, `b244047a` |
| 2 | 충실 포팅: Immortality 프로필(§2)·능력(§3–7), Epic·프로모 능력, Bloodlines Tech의 바탕인 RoI Tech 기계 | 완료 `8f7b6ba0` |
| 2' | 앱식 사양: `docs/app-ai/bloodlines-cards.md`, `bloodlines-systems.md`, `scouts.md` | 완료 `38a2e0d6` |
| 3 | Bloodlines 합성 아키타입 생성기와 능력(카드·책략·Twisted·Navigation·지도자·Skill·Commander·Tech·계약 토큰·Conflict), Scouts 가격 | 완료: 아키타입 204 + Scouts 줄 85, 능력 89 + 57 + Scouts; 미포팅 0 |
| 4 | 결정 창: Immortality·Epic·Go to 11·프로모·드래프트(새 창 6개 포함) | 완료 `e88edff4`: 7개 조합 6판씩 대체 0·미포팅 0 |
| 4' | 결정 창: Bloodlines 10, Scouts 10과 기존 창의 새 id | |
| 5 | 선택지 조합 전부에서 통합 census(대체 0), 축별 A/B, 문서 | |

검증: 충실 포팅은 지금까지처럼 사양·역어셈블에 대한 독립 반박 검증. 앱식 확장은 앱과 대조할 것이 없으므로 이 절의 규칙에 대한 대조로
검증한다.

### 11.7 앱식 사양 검토 결정 (2026-10-05)

`docs/app-ai/bloodlines-cards.md`, `bloodlines-systems.md`, `scouts.md`(각각 작성 agent + 독립 검증 agent)가 남긴 판단 중 아래만
바꾸고 나머지는 승인한다. 이 절이 세 문서보다 우선한다.

- **Tech 타일 `EarlyMod`/`LateMod`**: 11.3의 "획득 효과가 같은 RoI 타일" 규칙은 Bloodlines 타일 17/18장을 1–3라운드에 0점으로
  만든다(앱의 "Not early tech" 절단). 앱 RoI에서 초반 가산은 경제·덱 엔진 타일 8/18장에 붙어 있다. 그래서 **지속 능력이 가장 가까운
  RoI 타일**(`rix-tech.md` §1.2의 nearest 열; 같거나 같은 꼴의 능력) 것을 먼저 쓰고, 없을 때만 획득 효과가 같은 타일 것을 쓴다:
  Planetary Array = Windtraps(Conflict 승리 trigger, 1.5/0.5), Self-Destroying Messages = Minimic Film(Reveal +1 Persuasion,
  1.5/—), Delivery Bay = Disposal Facility(6+ Persuasion 조건, 1.5/0.0), Rapid Dropships = Training Drones(뒤집어 배치,
  1.1/0.75), CHOAM Transports = Holtzman Engine(조건부 종료 VP, 1.2/—). 나머지는 그대로.
- **가진 타일의 값(`HeldTileValue`)**: 사는 판단의 두 절단("Game Arc Min", "Not early tech")과 획득 효과 항은 사는 순간의 것이므로
  빼고, `AcquireValue` × 국면 배율([EarlyMod, 1, LateMod][arc])로 본다.
- **Urgent Shigawire의 아이콘 부여**: 0이 아니라 대안(손의 가장 좋은 Bene Gesserit 카드의 0.75 × UnlockValue)을 쓴다. 11.4의 "1회
  가격"에 맞는 쪽이다.
- **Scouts 강제 Trash(Funeral Rites, Termination Request)**: 손에 쓸모없는 카드(`TrashValue` > 0)가 있으면 그대로(`TrashCardValue`),
  없으면 `AcquireValue`가 가장 작은 카드를 고르고 그 카드의 `−AcquireValue`를 값으로 본다. 앱의 `TrashValue`는 음수가 없어 좋은
  카드를 영구히 잃는 것을 값 매기지 못한다. 그 카드를 갖는 값(`AcquireValue`)이 가장 가까운 앱 숫자다.
- 승인하고 구현 때 지킬 것: 지도자 미리보기(`GetRevealPreviewValue`) 재정의는 만든다. 구현자는 Southern Elders·BG Operative의 앱
  미리보기 본문을 역어셈블로 읽고 그 꼴을 따른다. 오래 가는 효과(Skill, Navigation 3)는 1회 가격으로 본다(11.4; 앱에 횟수를 세는
  도우미가 없다). Mohiam의 강제 Gather Intelligence는 회수가 원치 않는 것일 때 `CardDrawValueWithBuyGains − SpyValue`(음수)를 더한다(앱이 회수를 원하는지 가르는 바로 그 비교). Plasteel Blades의
  추가 Skill(`max(0, SkillValue − HeldTileValue)`)은 Commander 구매·재구매 순이익에 더한다. Into the Fray의 Conflict Agent를
  `RecallAgentValue`가 배치된 것으로 세는 변경은 Bloodlines 게임에서만 켠다.

### 11.8 3단계 검토 결정 (2026-10-05)

Bloodlines·Scouts 데이터와 능력(구현 agent 4 + 검증 agent 4)이 넘긴 판단:

- **Tuek's Sietch**는 Esmar Tuek이 있는 게임에서 보드 순회(칸 순서, `_board_spaces`, 계약 칸, `find_space`)에 넣는다. 앱이 확장
  칸을 넣는 방식(기본 칸 뒤에 덧붙임)대로 맨 뒤에 둔다.
- **Commander 값**은 병력 공급 상한을 거치지 않는 병력 값(`uncapped_troop_value(1)`)으로 본다. Commander는 병력 공급에서 오지 않으므로
  공급이 비었다고 0이 되면 안 된다.
- **High Council 첫 방문**의 Tech 값은 자리 할인(−1)을 가정한다(`bloodlines-systems.md` §3.1, `abilities/tech.py`에 Tech 모듈일 때만).
- **Commander를 병력으로 세는 규칙**(D1)은 카드 포트와 창에도 적용한다(Bloodlines일 때만).
- 승인: Urgent Shigawire의 `UnlockValue` 하한 0, 피해자 쪽 손실은 systems §1.4의 최소 손실, Scouts 병력 수를 줄 속성
  `AbilityTroops`로 싣는 것, 강제 Trash의 쓸모없는 카드 판정은 앱의 `GetCardToTrash(hand, 1.0)`, B1이 목록 밖에서 고친
  `ARCHETYPES[...]` 직접 조회 두 곳.
- 창 단계에서 할 것: Scouts 게임에서 Corrinth City의 Reveal을 `CorrinthCityRevealScoutsAbility`로 바꿔 평가, Market Opening의
  할인된 Reserve 카드를 나머지 자리(창·카드 포트)에도 쓰기, Hagga Basin의 Desert Riding 선택, 두 단계 입찰, Litany의
  `play_turn_start_card`, `AppContext`의 Scouts 읽기를 `view` 대신 `state`에서(가정 상태로 만든 문맥에서도 맞도록).
