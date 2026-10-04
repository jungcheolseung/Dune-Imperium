# 앱식 AI(app_ai) — 설계와 구현 계획

상태: **완료** (2026-10-05 작성·구현·A/B, master 병합). 브랜치 `app-ai`(worktree), 기준 master `60707f8b`(codec v133, 관측 v30).
뼈대 커밋 `279dffd8`.

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
| `data/archetypes.py` (생성) | 4인 Uprising(±CHOAM)에 나오는 앱 아키타입 227개의 속성과 능력 목록 |
| `catalog.py` | 우리 id ↔ 앱 아키타입 대응표와 `Entity` 생성 |
| `entities.py` | `Entity`(우리 id + 앱 아키타입), `Kind`, `Attr` |
| `context.py` | `AppContext`: 좌석이 읽어도 되는 것만 읽는 상태 접근(정직성 규칙의 유일한 자리) |
| `summer.py` | `AIValueSummer` 포트(`add`, 누적합에만 곱하는 `multiply`), `app_round`(Convert.ToInt32 = 은행가 반올림) |
| `choice.py` | `MakeChoice`: 전부 섞고 → 0 초과만 → 값 내림차순 안정 정렬 → 첫째; 없으면 빈 답 |
| `profile/core.py` | `WormAIProfile` 메서드 선언 전부(계약). 구현은 `economy.py`·`influence.py`·`combat.py` 세 mixin |
| `abilities/` | 앱 능력 클래스 포트. `@port("<앱 전체 클래스명>")`로 등록, 앱 상속 구조를 그대로 따른다 |
| `windows/` | 우리 결정 창 → 앱 질문 → 우리 행동. 창별 `HANDLERS` |
| `agent.py` | `AppAIAgent(seed, level)`: `StateAgent`. 대응 안 된 창은 `HeuristicAgent`로 넘기고 `fallbacks`에 센다 |

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
