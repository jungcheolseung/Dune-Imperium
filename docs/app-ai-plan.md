# 앱식 AI(app_ai) — 설계와 구현 계획

상태: **완료** (2026-10-05 작성·구현·A/B, master 병합). 브랜치 `app-ai`(worktree), 기준 master `60707f8b`(codec v133, 관측 v30).
뼈대 커밋 `279dffd8`.
확장판(Immortality·Epic·Go to 11·프로모·지도자 드래프트·Bloodlines·Arrakeen Scouts): **구현 완료**, 브랜치 `app-ai-expansions`(11절). 16개 선택지 조합 12판씩 오류 0·무작위 대체 0·미포팅 0.
원판 Dune: Imperium(base-game-and-ix-plan P6): **구현 완료**(무작위 대체 0), 브랜치 `claude/base-ix-p6-appai-b94c97`(12절), master `a4393427`. Rise of Ix는 준비만(13절), 이식은 P4 병합 뒤.

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
덤프를 다시 뜨고 세 스크립트를 다시 돌린다. 앱에 없는 Bloodlines·Scouts의 합성 아키타입은 `scripts/dwgr/app_ai_synth.py`가 우리 콘텐츠와
앱 데이터 규칙(11.3)으로 `agents/app_ai/data/synthetic.py`에 만든다(콘텐츠가 바뀌면 다시 돌린다; 테스트가 재현을 확인한다).

## 3. 구조 (`src/dune_imperium/agents/app_ai/`)

| 모듈 | 내용 |
|---|---|
| `data/constants.py` (생성) | `AIConstants` 437필드(앱 getter 이름 그대로), `HARD`/`MEDIUM`/`EASY`, `TABLES` (AILevel → 표) |
| `data/synthetic.py` (생성) | 앱식 확장의 합성 아키타입 204개(Bloodlines 카드·책략·Twisted·Navigation·Conflict·계약 토큰·지도자·Commander·Skill·Tech 타일·Tuek's Sietch)와 Scouts 줄 85개. 앱 속성 이름 그대로 |
| `data/archetypes.py` (생성) | 앱이 정의한 아키타입 508개 전부의 속성과 능력 목록. `in_uprising`/`in_uprising_choam`은 4인 Uprising(±CHOAM)에서 앱이 실제로 나눠 주는지 |
| `catalog.py` | 우리 id ↔ 앱 아키타입 대응표와 `Entity` 생성 |
| `entities.py` | `Entity`(우리 id + 앱 아키타입), `Kind`, `Attr` |
| `context.py` | `AppContext`: 좌석이 읽어도 되는 것만 읽는 상태 접근(정직성 규칙의 유일한 자리) |
| `summer.py` | `AIValueSummer` 포트(`add`, 누적합에만 곱하는 `multiply`), `app_round`(Convert.ToInt32 = 은행가 반올림) |
| `choice.py` | `MakeChoice`: 전부 섞고 → 0 초과만 → 값 내림차순 안정 정렬 → 첫째; 없으면 빈 답 |
| `profile/core.py` | `WormAIProfile` 메서드 선언 전부(계약). 구현은 `economy.py`·`influence.py`·`combat.py` 세 mixin과 확장 mixin `immortality.py`·`tech.py`(충실 포팅), `bloodlines.py`·`scouts.py`(앱식 확장) |
| `abilities/` | 앱 능력 클래스 포트. `@port("<앱 전체 클래스명>")`로 등록, 앱 상속 구조를 그대로 따른다. 확장: `immortality.py`, `epic_promo.py`, `tech.py`(충실 포팅), `bloodlines_cards.py`, `bloodlines_systems.py`, `scouts.py`(앱식 확장, `worm.canis.abilities.AppStyle.*`) |
| `windows/` | 우리 결정 창 → 앱 질문 → 우리 행동. 창별 `HANDLERS`. 확장 전용 창: `setup.py`(지도자 드래프트), `immortality.py`, `bloodlines.py`, `scouts.py`. 모르는 카드·행동 id는 기본값 없이 대체로 넘긴다 |
| `agent.py` | `AppAIAgent(seed, level)`: `StateAgent`. 대응 안 된 결정은 앱의 `DefaultRandomChoice`처럼 합법 행동 중 무작위로 답하고 `fallbacks`에 센다(heuristic은 섞지 않는다, 11절). 창이 예외를 내거나 불법 행동을 고르면 같은 방식으로 답하고 `error:<결정 종류>`로 세며 로그를 남긴다(플레이 UI에서 게임이 멈추지 않게; 자기 RNG라 저장 복원도 같은 수를 만든다). 테스트는 `conftest.py`가 `error:` 대체를 실패로 만든다 |

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
5. **우리 엔진만 묻는 질문은 앱 엔진이 실제로 하는 쪽으로 답한다.** `withdraw_troops`는 쓰지 않는다. (Reveal 선택 미루기
   `defer_reveal_choice`는 codec v147에서 없어졌다: Reveal 선택은 Reveal 창의 행으로 구매와 함께 나와 앱의 Reveal 뒤
   질문처럼 값으로 경쟁하고, 쓰지 않은 Optional 선택은 `finish_reveal`에서 사라진다.) 효과 순서 결정도 2번에 따른다.
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

Bloodlines·Scouts(앱식 확장, 창 단계에서 정한 것):

- Endgame: 앱의 `ScoreBattleIconsPairs`는 와일드 둘을 짝짓지 않는다. Bloodlines 규칙([Bloodlines p. 5])대로 앱의 짝을 매긴 뒤
  남은 와일드끼리 짝짓고, Grasp Arrakis의 Endgame 뒤집기는 짝을 매긴 뒤에 쓴다(cards 사양 D17).
- Command(6+) 선택은 그 선택 창에서 바로 답한다(구매 전, 11.5). 늦게 열린 Command는 Reveal 자동 단계로 이어 처리한다.
- Disruption Tactics: 이미 Combat 아이콘이 열려 있거나 배치 여유가 없으면 자기 Trash로 얻는 배치는 0이다(Rapid Dropships D24와 같은 판단).
- Navigation Chamber의 할인 변형은 변형마다 칸 값을 다시 매겨 가장 좋은 것을 고른다. Spice Refinery에서는 1-spice 교환이 공짜가 된다. 할인은 의무라(OQ-104, codec v142) 비용이 있는 칸에는 할인한 변형 하나만 있고, 둘이 함께 있는 곳은 Spice Refinery·Gather Support의 무료 option 0과 할인한 option 1뿐이다.
- Scouts 입찰은 두 단계(`scouts_bid`, `confirm_scouts_bid`) 모두 같은 결정적 평가기로 답한다(의도 기억 없이도 같은 값).
- 피해자 쪽 결정(`opponent_unit_loss`, `opponent_spy_move`)은 잃는 가치가 가장 작은 것(11.4).
- 알려진 엔진 차이 아닌 한계: `agents/determinize.py`는 상대의 Navigation 칸·Secret Project를 다시 섞지 않으므로 정직성 테스트가 이
  부분을 보지 못한다(창 검증 agent가 따로 섞어 본 확인에서는 차이 없음).

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
| 4' | 결정 창: Bloodlines 10, Scouts 10과 기존 창의 새 id; 11.8의 창 밖 결정 | 완료 `6fbe8037`, `110fa5bf`: 16개 조합 12판씩 대체 0·미포팅 0 |
| 5 | 선택지 조합 전부에서 통합 census(대체 0), 축별 A/B, 문서 | 완료: [`evaluation/app-ai-expansions-2026-10-05.md`](evaluation/app-ai-expansions-2026-10-05.md) |

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

## 12. 원판 Dune: Imperium (base-game-and-ix-plan P6, 2026-10-29~)

### 12.1 범위와 결정

2026-10-29 사용자(P5가 원판 좌석을 heuristic으로만 열자고 했을 때): "steam 앱 AI를 가져올 수 있지 않니? 원판, ix 게임도 이제
가져오면 될거 같은데". 앱은 원판을 직접 두므로 원판 AI(아키타입 값·능력 클래스·프로필 분기)가 모두 앱 안에 있다. 그래서 원판은
11절의 앱식 확장이 아니라 **충실 포팅**(1·4절 원칙 그대로)이다.

- 범위: 원판 보드(P2, 칸 22·Mentat·Reserve), 원판 카드(P3, Imperium 43종·프로모 3·책략 34·Conflict 18), 지도자 8, 지도자
  드래프트. Rise of Ix는 P4(`claude/base-ix-p4`)가 병합된 뒤 다음 단계.
- 출처: 11절과 같은 앱 빌드 dad97e20. 원판 능력 클래스는 P3d 대조가 만든 자료를 쓴다: 에셋
  `analysis/p3d-compare-2026-10-28/dossiers/{imperium,intrigue,conflict,leader,space}.json`(항목마다 우리 id ↔ 앱
  아키타입, 능력 클래스의 메서드별 디컴파일 C와 주석 단 역어셈블)과 `ghidra/p3d/<addr>.c`. **C를 먼저 읽고 판단이 걸린 줄은
  역어셈블로 확인한다.** 프로필의 BaseSet 분기는 2절의 사양(`spec/profile-*.md`)에 이미 적혀 있다(Uprising에서 "absent"로 둔 곳).
- 엔진은 바꾸지 않는다(P4 세션 소유). 엔진 고리가 필요하면 조정 세션에 묻는다.
- 완료 조건: 원판(드래프트 포함) 게임에서 세 난이도 모두 `fallbacks` 0·`UNPORTED` 0, Uprising app_ai 수는 고정 시드에서 그대로,
  원판 app_ai soak 오류 0, 원판 Hard 대 heuristic 소규모 측정 보고(관문 아님). 그 뒤 P5에 원판 좌석을 열어도 된다고 알린다.

### 12.2 census (2026-10-29, 원판 4좌석 app_ai 20판씩, 지도자 드래프트·프로모 포함)

포팅 전(master `0672a8b5`): 6판 Hard에서 결정 2,644개 중 2,076개가 무작위였다. 대부분(1,076개)은 `error:` — catalog에 원판
카드·Conflict·칸이 없어 창이 `KeyError`로 실패했다(`arrakis_liaison`, `imperium_secure_imperial_basin`, `gun_thopter` …).

슬라이스 1(catalog·보드) 뒤 오류 0. 남은 무작위 대체:

| 난이도 | 앱 판단 | 무작위 | agent_effects | reveal | intrigue_choice | combat_reward_* | masterstroke_setup |
|---|---|---|---|---|---|---|---|
| Hard | 7,471 | 2,841 (28%) | 2,314 | 421 | 32 | 56 | 18 |
| Medium | 7,727 | 3,091 (29%) | 2,588 | 383 | 43 | 59 | 18 |
| Easy | 7,768 | 2,683 (26%) | 2,275 | 297 | 39 | 54 | 18 |

`agent_effects`의 원인(Hard 20판, 창의 `unmapped` 사유):

- 칸: 원판 Maker 칸(Hagga Basin·The Great Flat의 수확, 542), Foldspace(50), 칸 draw(5). 칸 능력 미포팅 8:
  `ConspireSpaceAbility`, `FoldspaceDeferredAbility`, `SelectiveBreedingDeferredAbility`, `HallOfOratorySpaceAbility`·
  `HallOfOratoryAbility2`, `MentatSpaceAbility`, `SwordmasterSpaceAbility`(BaseSet), `SellMelangeSpaceAbility`.
- 지도자 Signet: Paul 165, Ariana 111, Ilban 109, Rabban 106, Memnon 62; 미포팅 18 클래스(Prescience, Masterstroke 1·2·Scheme,
  Connections·Spice Hoard, Manipulate, Manufacturing·Ruthless Negotiator, Hidden Reservoir·Spice Addict 1·2, Brutality·Arrakis
  Fiefdom, Prudent Diplomacy·Landsraad Popularity, `LeaderDrawAbility`); 창 밖 결정 `masterstroke_setup`,
  `choose_connections_influence`, `set_aside_leader_imperium`(Helena).
- 카드 Agent 상자(창 표에 원판 카드가 없음): Worm Riders 165, BG Initiate 147, Power Play 122, Arrakis Recruiter 97, Gurney 161,
  Space Travel 80, Thufir 77, Foldspace 70, Duncan Idaho 105, Spice Smugglers 47, Jessica of Arrakis 74, Stilgar 38, Other Memory 36,
  Guild Administrator 35, Lady Jessica 30, Dr. Yueh 29, Sardaukar Legion 28, Fedaykin 27, Sietch RM 25, Duncan Loyal Blade 25,
  Crysknife 24, Opulence 23, Piter 23, Imperial Spy 24, Firm Grip 13, Fremen Camp 12, Smuggler's Thopter 19, Guild Ambassador 14,
  Shifting Allegiances 1; 모르는 행동 id `pay_agent_card_solari`, `block_agent_card_space`, `take_agent_card_from_discard`,
  `lose_agent_card_influence`.
- `reveal`: Reserve 구매(Arrakis Liaison 277, TSMF 80), 획득 아이콘(CHOAM Directorship 81, Lady Jessica 63), 원판 Reveal 선택
  (`deploy_reveal_card_troop(s)`, `gain_two_reveal_persuasion/swords`, `retreat_reveal_card_troops`, `pay_reveal_solari_for_vp`
  …), 원판 책략의 Plot.
- 그 밖: `combat_reward_influence`·`combat_reward_distinct_influence`·`combat_reward_trash`(원판 Conflict 보상),
  `intrigue_choice`(Poison Snooper의 `draw_top_card`/`trash_top_card`, `choose_opponent_troop_loss`).

미포팅 앱 능력 클래스 160(앱 판단으로 센 결정도 이 능력은 값 0으로 본다): Conflict 54(18장 × 1·2·3등), Imperium 45, 책략 35,
지도자 18, 칸 8.

프로필에서 Uprising이라 건너뛴 BaseSet 분기(사양에 있음): `GetHeighlinerPotentialPlayer`의 Infiltrate·Urgent Mission·Dispatch an
Envoy, Rapid Mobilization·Staged Incident·Reinforcements의 교전 항, 영향력의 "+1 influence intrigue"·"Abilities Bonus"·Plans
Within Plans, `DeferredThresholdReached`의 Baron·Ariana·Ilban 항 등(`profile/*.py`의 "cannot be held"·"dead here" 주석).

### 12.3 슬라이스

각 슬라이스: 앱 클래스 포트(C → 역어셈블 확인) + 창 대응 + 사양의 분기·상수를 고정하는 단위 테스트 + 원판 census의 해당 사유 0 +
Uprising 고정 시드 수 그대로(`tmp/claude/523fa7a8/same_moves.py`: 7개 선택지 조합 21판).

| # | 슬라이스 | 내용 | 상태 |
|---|---|---|---|
| 1 | catalog·보드 | 원판 표 5개(`ORIGINAL_*`), `Board.original`, BaseSet 칸 순서, 앱의 `Is…Space` 판별(`swordmaster_space_id` 등), Maker 칸이 없는 보드의 worm potential, Hall of Oratory의 Reveal 미리보기 | 완료 `7919f867` |
| 2 | 칸 | 칸 능력 8클래스(`abilities/original_board.py`), Mentat·Foldspace·Selective Breeding·Sell Melange(턴 창이 앱의 판매량으로 비용 선택)·Hall of Oratory·Conspire 창 대응, 원판 Maker 칸 수확 | 완료 `51816b4c` |
| 3 | Conflict | 54클래스(`original_conflicts.py`), 교전 보상 창(영향력·서로 다른 영향력·Trash·-OR-·"둘 고르기"), `RelativeConflictValue`의 원판 경로(레벨별 고정표) | 완료 `9b8d9e1d`–`9dc7c096` (agent) |
| 4 | 지도자 | 18클래스(`original_leaders.py`), Signet 상자·Prudent Diplomacy·Scheme·Manipulate·Connections, `masterstroke_setup`, Baron의 Masterstroke 배치 보정 | 완료 `cbe2640c` (agent), `41346d40`, `1b6e4c4a`, `a0462cb0` |
| 5–6 | Imperium·프로모·Reserve | 47클래스(`original_imperium.py`), Agent 상자·지불·-OR-·Shifting Allegiances·Firm Grip·The Voice 창, Reveal 선택 9종, 획득 아이콘, Kwisatz Haderach의 출발 Agent | 완료 `aaa6fb91`, `33c83f09`…(agent), `58d3bf07`, `8aff86df`, `2ba5a23d` |
| 7–8 | 책략 | 36클래스(`original_intrigue.py`), Poison Snooper·Bindu Suspension 선택, Test of Humanity 피해자 선택 | 완료 `33c83f09` (agent), `1b6e4c4a` |
| 9 | 프로필 BaseSet 분기 | `AppContext.uprising`(`IsSetEnabled(4)`)의 거짓 경로(Emperor 4칸 보상 3.0, 칸 가치·영향력의 Uprising 블록, 종료 점수 등), 원판 책략·지도자 분기(Heighliner potential, Rapid Mobilization 등) | 완료 `92d7dafd`, `e89c7834` (agent) |
| 10 | 마무리 | 세 난이도 census 0, Uprising 같은 수, 원판 soak, Hard 대 heuristic 측정, 문서·P5 알림 | 완료 (결과 12.4) |

### 12.4 결과와 알려진 차이

- census: 원판(드래프트·프로모 포함) 30판씩 세 난이도 모두 앱 판단 약 16,300개, 무작위 대체 0, 미포팅 0(시드 7000–7029); 드래프트 없는
  판·프로모만 켠 판도 0. Uprising app_ai 수는 고정 시드 21판(선택지 조합 7개)에서 슬라이스마다 master와 같았다
  (`tmp/claude/523fa7a8/same_moves.py`).
- soak: 원판(드래프트·프로모) app_ai 네 좌석, 난이도 섞어(좌석마다 0/1/2) 300판(시드 50000–50299): 예외 0, 미완료 0, 무작위 대체
  0, 6–10라운드(평균 925걸음), 원판 지도자 8명 모두 141–165번.
- 측정(관문 아님): Hard 대 heuristic 2:2 거울(ABAB·BABA), 원판·드래프트·프로모 300시드 600판(시드 60000–60299): 좌석당 승률 Hard
  49.5%, heuristic 0.5%(Hard 쪽 99.0% ± 0.8), 좌석당 평균 VP 9.43 대 4.65; 예외·대체·오류 0. Uprising의 46.5% 대 3.5%(11절)보다
  벌어진 것은 heuristic이 원판에 약하기 때문으로 보인다: heuristic 네 좌석 원판 20판은 우승 VP 평균 9.55·9.7라운드(대개 10라운드
  끝까지), 같은 시드의 Uprising은 10.8·9.5라운드.
- Helena Richese의 Manipulate: 앱은 살 수 있는 Row 카드가 없으면 0.5의 빈 답으로 아무것도 놓지 않지만, 우리 엔진은 Signet을 쓰면
  set-aside를 요구한다(그 밖에 낼 행동이 없다). 그때는 앱이 채울 수 없는 강제 프롬프트의 답인 `DefaultRandomChoice`(Row 카드 중
  무작위)로 답한다(턴을 끝낼 수 있으면 쓰지 않은 채 둔다).
- Gurney Halleck의 Reveal: 앱은 3 Solari 지불과 배치할 병력 수를 한 답으로 정한다. 우리는 지불만 그 답으로 하고, 배치는 Reveal의
  일반 배치 키(`DeployUnitsAbility`, 0.5)가 정한다.
- Kwisatz Haderach: 앱의 Agent 목록(`GetAgentTargets`, 놀이판의 자손 순서)은 추적하지 않았다. 아직 놓지 않은 Agent를 먼저, 놓인
  Agent를 보드 순서로 둔다(같은 값일 때만 차이).
- Baron의 Masterstroke 배치 보정: 앱의 "이번 턴 소진된 유닛"(`IsExhausted`)을 우리 `units_deployed_turn`으로 읽는다(앱이 언제
  다시 세우는지는 추적하지 않음).
- Test of Humanity·Reverend Mother Mohiam의 지연 능력: `CanRunImmediately`의 ClientVersion 검사(최소 3.0.0.0)는 컴퓨터 좌석을
  "클라이언트 없음"으로 보아 곧바로 실행한다(agent 판단, `original_imperium._client_runs_immediately`).
- Private Army의 결정적 교전 값 50.0, Bypass Protocol 세 번째 응답, Bindu Suspension 100.0 등 agent가 추정으로 읽은 값은 각
  클래스 docstring에 주소와 함께 적었다.

## 13. Rise of Ix (원판 위) — 준비 (2026-10-29; 이식은 P4 병합·setup이 원판 + Ix를 연 뒤)

### 13.1 범위와 결정

- 12.1과 같은 사용자 결정("원판, ix 게임도 이제 가져오면 될거 같은데")의 둘째 몫. 앱이 Rise of Ix를 직접 두므로 **충실 포팅**이다.
- 범위: 원판 + Ix(Epic·프로모 Boundless Ambition·지도자 드래프트 포함) — P4(`claude/base-ix-p4`)가 여는 판. Uprising + Ix(CHOAM의
  Ix 계약 10장 `ROIContractAbility`·`ROIHarvest3/4ContractAbility`, Ix + Bloodlines Tech 36장)는 base-game-and-ix-plan의 P7 몫이라 뺀다.
- 시작 조건: P4가 master에 병합되고 setup이 원판 + Ix를 연다(P4c-5). P4c~P4e가 아직 행동 id를 만들지 않은 결정(Tech·Freighter·
  카드·지도자)은 13.3의 대응표를 그때 행동 id로 다듬는다. 12.2처럼 원판 + Ix 판의 census부터 한다.
- 출처: 11·12절과 같은 앱 빌드 dad97e20.
  - 사양: `spec/rix-tech.md`(Tech 타일 값, `TechTileToAcquire`·`BuyTechValue`·`get_NegotiateTechValue`, `get_FreighterValue`·
    `GetFreighterSelections` §4.6–4.7, Dreadnought 칸 §6.7, 엔진 순서 §7)와 `spec/profile-*.md`의 `SetOn(2)` 분기.
  - 클래스: 역어셈블 `dump/asm/worm-canis.dll/*.RiseOfIx.*.asm` 284개. **디컴파일 C는 아직 없다**(`ghidra/p3d-types`는 원판 180개뿐).
    P4f(Ix 전부의 앱 행동 대조)가 같은 클래스를 P3d 방법으로 디컴파일하므로, 그 결과를 함께 쓴다(디컴파일은 한 번 — 조정 세션이
    순서를 정한다). 12절처럼 C를 먼저 읽고 판단이 걸린 줄은 역어셈블로 확인한다.
- 엔진은 바꾸지 않는다. 완료 조건은 12.1과 같고 판만 원판 + Ix다. 여기에 **원판 단독 판의 app_ai 수도 고정 시드에서 그대로**를 더한다:
  Ix 분기는 모두 `IsSetEnabled(2)`·`HasTech`·Ix 카드로 갈리므로 Ix가 꺼진 판의 수는 바뀌면 안 된다(Uprising 같은 수 21판과 같은 방법).

### 13.2 앱 클래스 목록 (`data/archetypes.py`의 `RiseOfIx` 아키타입 90, 능력 칸 255; 2026-10-29 `PORTS` 대조)

| 묶음 | 아키타입 | 이미 있는 포트(재사용) | 새로 필요한 클래스 |
|---|---|---|---|
| 칸 | 4 | `AcquireTechAbility`, `TechNegotiationDeferredAbility`(11절 Bloodlines Tech 때 `abilities/tech.py`) | 6: `DreadnoughtSpaceAbility`, `InterstellarShippingSpaceAbility`, `SmugglingSpaceAbility`, `TechNegotiationSpaceAbility`, `TechNegotiationTriggeredAbility`, `FreighterAgentAbility` |
| Tech 타일 | 18 | 8: `ChaumurkyAbility`, `MinimicFilmAbility`, `DisposalFacilityAcquiredAbility`, `MemocordersAcquiredAbility`, `ShuttleFleetAcquiredAbility`, `GainIntrigueAcquiredAbility`, `DrawImperiumAcquiredAbility`(Spaceport ×2) | 17: Artillery, Disposal Facility(+Triggered), Flagship, Holoprojectors, Holtzman Engine(+Endgame), Invasion Ships, Memocorders(종료), Restricted Ordnance, Shuttle Fleet(Round Start), Sonic Snoopers, Spy Satellites(+Endgame), Training Drones, Troop Transports, Windtraps. Detonation Devices는 클래스가 없다(프로필 `tech.py`의 "Detonation Devices" 항 + `DreadnoughtControlAbility`) |
| 지도자 | 6 | `IxianTechnologyAbility`(Rhombur) | 20: Armand(`Coordination`, `Conscript`), Ilesa(`GuildContacts`, `OneStepAheadRound/Turn/Send`), Rhombur(`HeavyLasgunCannons`), Yuna(`FinalDelivery`, `SmugglingOperationSolari/Water`), Tessia(`CarefulObeservationSetup`[앱 철자], `CarefulObservation` Emperor·SpacingGuild·BeneGesserit·Fremen·Triggered·OppTriggered, `Duplicity`), Hundro(`Couriers`, `Intelligence`) |
| Imperium | 30 (29 + Boundless Ambition) + Control the Spice | 공용 Agent·Reveal·Acquire, `ThufirHawatRevealAbility`, `RevealGainIntrigueAbility`, `TrashAgentAbility`, `PowerPlayAgentAbility`, `ImperialBasharRevealAbility`, `InTheShadowsRevealAbility`, `AcquireTechAgentAbility`, `ControlTheSpiceAbility`(Epic) | 48(서로 다른 클래스). 공용인 것: `UnloadAbility`(CHOAM Delegate·Esmar Tuek·Ix Guild Compact·Treachery·Water Peddler), `FreighterAgentAbility`(Landing Rights), `FreighterRevealAbility`(Freighter Fleet·Guild Chief Administrator) |
| 책략 | 17 | – | 21 (Plot·Combat·Endgame 둘씩인 카드: Advanced Weaponry, Finesse, Machine Culture, War Chest) |
| Conflict | 4 | Economic Supremacy 5(Epic) | 9: Skirmish E·F, Trade Monopoly × 1·2·3등 |
| 아키타입 밖(엔진이 만드는 능력) | – | `AcquireTechAbilityShippingTrack2` | `FreighterAbility`·`FreighterCustomAbility`, `ShippingTrackAbility1/2/3`, `ConflictAbilities.RiseOfIx.DreadnoughtControlAbility`, `ai.evaluators.ChooseDiscardEvaluator`(Discard 비용) |

합: 새 클래스 약 126(서로 다른 것; 원판 이식의 160보다 적다). Hagal(`HagalAbilities.RiseOfIx.*`)·Challenge·Tutorial 클래스는 4인 판에 없다.

프로필·문맥(12.2의 "dead here"와 같은 자리):

- `AppContext.ix`(`IsSetEnabled(RiseOfIx=2)`)와 `Board`: 덮인 칸 넷(Hall of Oratory, Rally Troops, Secure Contract, Sell Melange)을 빼고
  Ix 칸 넷의 아키타입·앱 칸 순서(`_SPACE_ARCHETYPE_ORDER`의 RiseOfIx 보드 세트)를 더한다.
- `SetOn(2)`·Ix 카드·`HasTech`로 죽여 둔 자리 18곳: `profile/economy.py` 9(Quid Pro Quo·Machine Culture·Diversion·Training Drones·
  Dreadnought `CapacityMod`·Sonic Snoopers·Grand Conspiracy·Memocorders·Invasion Ships 등), `profile/tech.py` 3, `abilities/generic.py` 2,
  `profile/influence.py` 2(Spy Satellites·Memocorders), `profile/combat.py` 1(`ConflictInterestGarrisonDreadnoughtValue` #259, 유닛당
  1.5), `abilities/board.py` 1. 그 밖에 `profile-combat.md`의 Strategic Push·Windtraps·Diversion 항, Rhombur의 dreadnought strength 4.
- `profile/tech.py`의 0으로 둔 값 둘: `tech_negotiator_count`(협상가), `tech_dreadnoughts_in_supply`. 새 메서드: `get_FreighterValue`,
  `GetFreighterSelections`(Shipping track 칸; 레벨 2의 `M.Random.Next(2)`는 앱의 판 RNG — agent의 시드 RNG로, 4절 9 "결정성"과 같이).

### 13.3 P4 결정 ↔ 앱 클래스 대응

P4 브랜치(`51884e8f`)가 지금 가진 결정은 dreadnought 셋(P4b)과 예약된 frame 일곱(`rules/frames.py`의 `IX_FRAME_KINDS`, 관측 v39)이다.
나머지 행동 id는 P4c~P4e가 만든다.

| 우리 결정 (frame·행동) | P4 단계 | 앱 클래스·프로필 | app_ai 창 |
|---|---|---|---|
| `dreadnought_control_choice`: `place_combat_reward_dreadnought`(Control 칸 셋 중 빈 칸), Detonation Devices의 "VP 대신" | P4b-1 (있음) | `DreadnoughtControlAbility` E; Detonation Devices 값(`tech.py`, #305·#307) | `windows/combat.py` 승자의 창 줄 |
| `commission_intrigue_dreadnought` / `decline_intrigue_dreadnought`, 칸·Tech의 commission 줄 | P4b-2 (책략 출처 있음), P4c-4 | `GetDreadnoughtValue`(`economy.dreadnought_value`, #247–249, `CapacityMod`), `DreadnoughtSpaceAbility` V(+ 칸의 `AcquireTechAbility` `BuyTechValue(0)`) | 책략 줄, `agent_effects`(칸) |
| `deploy_dreadnoughts` / `withdraw_dreadnoughts` (배치 몫: garrison 둘을 troop·Commander·dreadnought가 함께) | P4b-2 (있음) | `profile/combat.py` `units_to_deploy`의 dreadnought 항(앱 `DeployUnits`; #259) | 배치 키(지금 troop만) |
| `freighter_move`(차례 밖 Freighter: Conflict 보상·Skirmish·Trade Monopoly·Hundro) | P4c-3 | `FreighterAbility` E = `IntTargetResponse(GetFreighterSelections(-1).Item1)`(1 회수, 0 전진; rix-tech §4.7, §6.6); 출처 V: Trade Monopoly·Skirmish E 1등, `Couriers`, Diversion, Expedite, Embedded Agent | 새 창 |
| 자기 차례의 Freighter 줄(Agent 상자·Reveal 상자·Interstellar Shipping·Smuggling) | P4c-3·4, P4d | `FreighterAgentAbility`, `FreighterRevealAbility`, `InterstellarShippingSpaceAbility`, `SmugglingSpaceAbility` | `agent_effects`, `reveal` |
| `shipping_reward_icons`(회수 보상, 원하는 순서) | P4c-3 | `ShippingTrackAbility1/2/3`, `AcquireTechAbilityShippingTrack2`; `GetFreighterSelections`의 Item2(사양이 "UNTRACED" — 디컴파일로 확인) | 새 창 |
| Tech 획득·할인·협상가(`tech_payment`, `tech_discount`, `negotiators_returnable`) | P4c-1 | `AcquireTechAbility`(+`Discount1`, `AcquireTechAgentAbility`), `TechTileToAcquire`·`BuyTechValue`·`get_NegotiateTechValue`, `PayTechNegotiators`, `TechNegotiation*` | `windows/bloodlines.py`의 Tech 창을 Ix 타일 실제 아키타입으로(11절의 합성 아키타입 대신) |
| Tech 뒤집기·사용(Flagship, Holoprojectors, Invasion Ships, Training Drones, Spy Satellites, Troop Transports) | P4c-2 | 각 타일 클래스(`SelectionMode` Optional: E > 0이고 가장 좋을 때만, rix-tech §7.4) | `turn`·`agent_effects` |
| `intrigue_bottom_pick`(Sonic Snoopers) | P4c-2 | `SonicSnoopersAbility` | 새 창 |
| 종료 타일(Chaumurky·Holtzman·Memocorders·Spy Satellites) | P4c-2 | 앱은 묻지 않는다(rix-tech §7.4) — 우리 엔진이 묻는 곳이 있으면 그 클래스 E | – |
| `unload_icons`(남의 효과로 버려지거나 보상으로 trash될 때의 Unload 상자) | P4d | `UnloadAbility`, `FreighterFleetUnloadAbility`, `GuildAccordUnloadAbility`, `InTheShadowsUnloadAbility`, `BoundlessAmbitionUnload(Opp)Ability` | 새 창(계약 보상 아이콘 창과 같은 꼴) |
| 자기 차례의 Discard 비용 아이콘 | P4d | `ChooseDiscardEvaluator`와 카드 클래스 | `agent_effects`, `reveal` |
| 잠입(Infiltration) 아이콘 | P4d | 선택 없음(칸 합법성) | `turn`의 칸 목록 |
| `round_start_set_aside`(Ilesa One Step Ahead) | P4e | `OneStepAheadRoundAbility`(+ Turn·Send) | 새 창 |
| `optional_discard`(Tessia의 첫 Snooper 보상 "discard → 1 spice") | P4e | `CarefulObservation*`, `ChooseDiscardEvaluator` | 새 창 |
| 지도자 Signet·setup(Tessia의 Snooper 진영, Hundro의 Intrigue 맨 위) | P4e | 13.2 지도자 줄 | `agent_effects`, `windows/setup.py` |

### 13.4 슬라이스 (12.3과 같은 방식: 클래스 포트 + 창 대응 + 분기·상수를 고정하는 단위 테스트 + census 사유 0 + 같은 수 확인)

| # | 슬라이스 | 내용 | 상태 |
|---|---|---|---|
| 1 | 틀 | `AppContext.ix`, `Board`의 Ix 칸 넷·덮인 칸 넷, catalog의 Ix 표(카드·책략·Conflict·지도자·Tech 실제 아키타입), 원판 + Ix census(오류 0까지) | 완료 `0afb1705` |
| 2 | 프로필 | `SetOn(2)` 자리 18곳, `tech.py`의 협상가·supply dreadnought, `get_FreighterValue`·`GetFreighterSelections` | Freighter·협상가·dreadnought 완료 `f94e850b`; Tech 항은 Codex(`codex-p6ix-tech`) |
| 3 | 유닛 | dreadnought 지배·commission·배치(13.3 첫 세 줄) | 완료 `318b7c13`(`GetUnitsToDeploy`의 강한 유닛 먼저·Baron 교체·Diversion, `DeployValue` Ix 항), `3880c3e3`(지배) |
| 4 | 칸과 Shipping | Ix 칸 6클래스, `FreighterAbility`·`ShippingTrackAbility1/2/3`, `freighter_move`·`shipping_reward_icons` 창 | 완료 `f94e850b`, `de9ffbed`; Tech 획득 창(할인별 앱 클래스, 협상가 먼저) `3880c3e3` |
| 5 | Tech | 타일 17클래스, Tech 창을 실제 Ix 타일로, Sonic Snoopers 창 | 완료: 클래스 `0fc758b1`(Codex), 창 `f5ad13ce`, Troop Transports 배치 `fcd538be` |
| 6 | Imperium | 48클래스, Unload·Discard·잠입 | 완료: 클래스 `43035f7d`(Opus agent), `beb1328b`, 창 `63b24e7f`, Boundless Ambition `5a195063` |
| 7 | 책략 | 21클래스 | 완료: 클래스 `af6341ea`(Opus agent), `4689a8ec`(`GetBestOption`·Glimpse·Ixian Probe), 창 `63c94da4`, `2ec3f1d1` |
| 8 | Conflict | 9클래스 | 완료 `c2838e5d` |
| 9 | 지도자 | 20클래스, `round_start_set_aside`·`optional_discard`, Tessia·Hundro의 setup | 완료: 다섯 명 클래스 12개, Tessia 9개(agent 둘, `abilities/ix_leaders.py`), 창 연결·Rhombur의 dreadnought 힘 4 |
| 10 | 마무리 | 세 난이도 census 0, Uprising·원판 같은 수, 원판 + Ix soak, Hard 대 heuristic 측정, 문서·P5 알림 | census 0·같은 수 완료; 문서 `docs/app-ai/rise-of-ix.md`; soak·측정은 P4e 뒤 |

- 진행(2026-10-29 밤, 브랜치 `claude/base-ix-p6-ix` = P4 `7a0c50e4` + P6 브랜치 `e7af766f` 병합, 그 뒤 P4 `87581ad9`를 따라
  병합): 원판 + Ix Hard 10판 census에서 남은 무작위는 Tech 타일 자체의 줄과 P4d가 덱에 넣기 시작한 Ix 카드뿐이다. Ix 클래스
  디컴파일(127클래스·3,406함수와 프로필 함수 7)은 assets `ghidra/p6ix/`(색인 `targets-named.tsv`, `targets2-named.tsv`).
- 같은 브랜치에서 고친 Uprising 건(대규모 소크 2026-10-29의 쉬움 무작위 6번, `b8eb54a4`): Possible Futures 상자가 영향력 고르기
  없이 나올 때, Sardaukar II 회수에 Into the Fray의 Conflict Agent가 있을 때(bloodlines-systems §8 D55와 같이 마지막 후보).
- Codex 몫(클래스 + 단위 테스트만, 창 연결은 이 세션): Tech 17, Imperium 46, 책략 21. 지시문은 `tmp/coordination/codex-p6ix-*.md`.
- agent: 원판 이식은 Sonnet 셋이 약 1.7M 토큰(Conflict 662k, 책략 + 지도자 119k, Imperium 955k)을 썼다. Ix 6~9는 크기가 비슷해
  둘이면 약 1.5M로 본다. 띄우기 전에 조정 세션을 거쳐 사용자 승인을 받는다(동시 상한은 승인이 아니다).
- P4와 병합: P4는 `6352199d`(P6 병합 전)에서 땄고 `windows/turn.py`의 `_after_send`(dreadnought가 칸의 controller, `space_controller`)를
  고쳤다. 2026-10-29 `git merge-tree`로는 이 파일이 자동으로 합쳐지고, 충돌은 P4·master 몫(`docs/base-game-and-ix-plan.md`,
  `display/effect_dsl_text_ko.py`)뿐이다. 슬라이스 1에서 합쳐진 `_after_send`가 원판 보드에서 맞는지 본다.

### 13.5 결과와 알려진 차이 (2026-10-30)

- census: 원판 + Ix(드래프트·프로모) 세 난이도 15판씩(시드 8100–8114) 무작위 0·미포팅 0, 원판 단독 Hard 10판 0. app_ai 테스트
  3,882개. Uprising·원판 고정 시드 24판의 수는 조각마다 같았다(Spice Smugglers 순서 수정 `e49c1568` 뒤의 기준선, 그 카드가 나오는 원판
  2판만 그 수정으로 바뀜).
- 결정마다 어느 앱 클래스가 답하는지와 판단 사항은 [docs/app-ai/rise-of-ix.md](app-ai/rise-of-ix.md)에 있다.
- P4 책략 묶음 d(`3b8cd83c`, 병합 `284628a9`): Advanced Weaponry의 commission은 앱처럼 묻지 않고 받는다. Second Wave의 배치는
  `SecondWaveAbility`가 고른 유닛 수와 dreadnought 수가 같은 행이다. Cannon Turrets는 고를 것이 없다. Endgame의 Plans Within
  Plans·Grand Conspiracy는 넷을 채우면 2 VP 선택지를 낸다(앱 `CountTotalPoints`: 셋 1 VP, 넷 2 VP). 전에는 첫 선택지(1 VP)를
  냈고, 이 수정으로 원판 고정 시드 1판(`original:501:L1`)이 그 한 수만 바뀐다.
- Tessia Vernius(`6c6b747e`, 병합 `23231f15`): 클래스 8개와 추상 베이스를 agent 하나(약 449k 토큰)가 이식했고, Duplicity의
  두 단계(잃기 → 얻기)는 한 번의 답을 나눠 쓴다. Quid Pro Quo의 진영별 Influence 행(OQ-153)은 앱의 보드 순서로 먼저 받는다.
  Disposal Facility의 두 trash(`b806b3db`)는 행 id가 그대로라 연결이 바뀌지 않는다.
- P4e 지도자 다섯(`137d582f`, 병합 `22876e87`): 앱 클래스 12개를 agent 하나(세션 모델, 약 477k 토큰)가 이식했고, 창은 이
  세션이 이었다(Signet 다섯, Armand의 Reveal trash, Ilesa의 Round Start 따로 두기, Hundro의 Intelligence). 병합 직후 Hard 20판의
  무작위 285번이 0이 됐다.
- P4 책략 묶음 e(`0d65eb9c`, 병합 `8aee4447`): Machine Culture는 앱처럼 `GetAcquireTechTileTargets(0, false)`를 대상으로
  받아(전에는 대상이 없어 내지 않았다) 고른 타일을 Tech 창이 그대로 산다(엔진은 Intrigue가 연 Tech 프레임에 거절 행을 두지 않는다).
  War Chest·Diversion은 고를 것 없이 이식된 클래스로 답한다. Double Cross를 앱의 `DefaultRandomChoice`가 냈을 때(평가가 상대를
  고르지 않음) 대상도 `DefaultRandomChoice`로 고른다.
- Interstellar Shipping에서 Shipping 회수로 recruit한 병력의 배치(시드 8100): P4 판정으로 Troop Transports가 허락하는 합법 배치
  (rise-of-ix.md 15)라, 앱의 `TroopTransportsAbility`로 답한다(`fcd538be`).
- agent 토큰: Opus 둘(Imperium 약 862k, 책략 약 537k), Codex Tech 하나(Codex 쪽 한도). 독립 검토는 Codex 5시간 창이 차서
  읽기 전용 리뷰 agent 하나(세션 모델)로 했다.
- P4d 마지막 Unload 카드 셋(`claude/p4d-imperium-b` `5a006d95`, P4의 Unload 보류 `976aa6a1` 포함, 시험 병합으로 미리 연결):
  Freighter Fleet의 Reveal·Unload Freighter는 `FreighterRevealAbility`·`FreighterCustomAbility`가, Ix-Guild Compact의 두 장
  버리기는 `IxGuildCompactAgentAbility`의 한 번의 답(두 번째 카드는 이어서)이, Negotiator 둘은 앱이 묻지 않고 놓으므로 자동 단계가,
  Boundless Ambition의 카드 얻기(Reveal·Unload 창)는 `BoundlessAmbitionCustomAbility`가 답한다. 이 클래스의 응답 순서는 디컴파일한
  C로 바로잡았다(카드 먼저, 그다음 목적지 0). Signet 상자는 카드 이름 대신 카드의 `LEADER_SIGNET` 효과로 알아본다. 보류 중에는
  새 결정이 없다. 시험 트리에서 세 난이도·Epic·원판 단독 census 무작위 0, 같은 수 24/24.
- P4 마지막 Imperium 묶음(`e3cac948`, 병합 `6c88b68f`): Guild Chief Administrator(버리기 + `EvaluateTrash`), Weirding Way(선택지 1이면
  추가 턴), Embedded Agent(`FreighterCustomAbility` 둘), Full-Scale Assault(일반 상자), Court Intrigue(Intrigue를 덱 밑에, 뽑기는 이어서),
  Desert Ambush(한 번의 답에 유닛 여럿, 나머지는 이어서), Negotiated Withdrawal(진영 + 앱이 빈 답 뒤에 하는 troop 먼저 셋, `Cost`
  이식). 병합 직후 Hard 20판의 무작위 97번이 0이 됐다.
- 남은 것: 원판 + Ix soak과 Hard 대 heuristic 측정(P4d 카드가 다 들어온 뒤).
