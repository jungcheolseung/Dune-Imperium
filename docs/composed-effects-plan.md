# 효과 조각 엔진 전환 계획 (composed effects)

상태: **진행 중** — A0 끝남(2026-10-15, 5절 "A0에서 만든 것"), A1 끝남(2026-10-16, codec v148, 5절 "A1에서 만든 것"), A2 44개 끝남(2026-10-16, codec 그대로, 5절 "A2에서 만든 것"), A3a·A3b 끝남(2026-10-16, 5절 "A3a·A3b에서 만든 것"), A3c 끝남(2026-10-16, 5절 "A3c에서 만든 것"), A3d 9칸 끝남(2026-10-16, 5절 "A3d에서 만든 것"), A3e 폐기 칸 5개 끝남(2026-10-16, 5절 "A3e에서 만든 것"), A3f 중 선택 획득 2칸·Arrakis Observer·Piter·Control the Spice·S6·S7 끝남 — **A3 끝남**(2026-10-16, 5절 "A3f-1에서 만든 것"~"A3f-5에서 만든 것"), A3g 표에 없던 Agent 칸 15개 끝남 — 개인 카드 Agent 칸 모두 기록(2026-10-16, 5절 "A3g에서 만든 것"), A4 끝남(2026-10-16, 5절 "A4a·A4c에서 만든 것"·"A4d~A4h에서 만든 것": 획득·폐기·버림 효과, Reveal 자동 이득, Reveal 선택 26개 — 개인 카드의 효과가 모두 기록), A5 끝남(2026-10-16, 5절 "A5에서 만든 것": 계약·Conflict 보상·보드 칸), A6 끝남(2026-10-17, 5절 "A6에서 만든 것": Tech·지도자), A7 끝남(2026-10-17, 5절 "A7에서 만든 것": 기술 타일·Immortality·Arrakeen Scouts) — **A단계 옮기기 끝**, 다음은 5절 "정리 단계"(A8과 함께). 계획은 2026-10-14(같은 날 효과 목록 조사 뒤 B단계를 "A단계 뒤
측정으로 정할 선택"으로 고침, 4.3·5절). 사용자 결정:

- "제대로 하는 방법으로 가야한다고 생각해. 사실 애초에 구현부터 행동이 하나로 묶이지 않고 분리된 행동의 집합으로
  구현되었어야 한다고 생각하는데"
- "1. 엔진 교체 전에, 지금 플레이할 수 있는 가장 강한 모델을 플레이에 설정해놓자. 2. 엔진 수정 중에도 플레이할 수
  있는 상태는 유지해야해. 3. 학습과 병행하는거는 별로인 듯? (…) 4. 어쨌든 엔진 전환 바로 들어가는게 좋다고
  생각한다. 5. 전환할 때, 듄 임페리움 게임 앱에는 어떻게 구현되어 있는지 참고하면 좋지 않을까?"

1번은 끝났다. 플레이 서버 망은 레시피 MLP(`checkpoints/play/recipe-mlp-1e5-800.pt`, Y 증류 + Y 가치 목표 +
1e-5 강화학습)다(worklog 2026-10-14).

## 1. 왜 바꾸나

- 카드 효과가 카드마다 이름 붙은 enum 멤버와 전용 코드로 묶여 있다. 새 카드 하나가 새 enum, 새 처리 코드, 새 행동
  종류, 망의 새 행동 줄을 부른다. Rise of Ix·기본판 Imperium·Conspiracy를 더하면 이것이 카드 수만큼 늘어난다.
- 개체 기반 망(docs/entity-network-plan.md)은 카드를 "얻기·뽑기·폐기·사기" 같은 공통 조각의 묶음으로 읽을 때 새
  카드에 일반화한다. 지금 개인 카드 139장 중 116장은 그 카드만 가진 효과 특성 하나로 읽힌다.
- [refactoring-plan.md](refactoring-plan.md) C의 남은 일("Imperium enum DSL 이관", 미착수)을 끝내고, 행동
  인터페이스까지 조각 단위로 바꾼다.

## 2. 지금 상태 (codec v145, 관측 v32)

| 항목 | 값 |
| --- | --- |
| `rules/` | 45,518줄. `agent_effects.py` 5,533, `reveal_turn.py` 4,904, `leader_abilities.py` 2,719, `intrigue.py` 2,430, `combat.py` 2,337, `acquisition.py` 1,796, `scouts_effects.py` 1,798, `board_effects.py` 1,702, `effect_interpreter.py` 1,646, `contracts.py` 1,565, `tech.py` 1,211 |
| 개인 카드 Agent 칸 효과 | `PersonalCardAgentEffect` 104개, 카드 116장이 쓰고 둘 이상의 카드가 쓰는 것은 9개, `rules/`에서 219번 참조 |
| 개인 카드 Reveal 선택 효과 | `PersonalCardRevealChoiceEffect` 26개(카드 28장, 둘 이상의 카드가 쓰는 것은 2개) |
| 개인 카드 기타 효과 | 획득 12, 폐기 4, 버림 2, 차례 시작 1, 아이콘 조건 2, Reveal 중 획득 1 |
| 개인 카드 Reveal 자동 이득 | `PersonalCardRevealEffect` 데이터(이미 조각 모양) |
| 책략 | 90 identity가 `effect_dsl.py`의 조건 × 비용 × 보상 × 구역 × 선택지로 적혀 있다(2026-08-29 전사 완료) |
| 지도자·Tech·보드 칸·Conflict·계약·Scouts | 지도자 18명, `TechAbility` 18개, 나머지는 각 모듈의 전용 코드 |
| 행동 종류(전 옵션) | 279종, 35,972줄. 같은 조각이 출처별로 갈라져 있다: 폐기 18종, 회수 19종, 획득 17종, 지불 17종, 놓기 12종, 고르기 17종, 거절 43종 |
| 결정 frame 종류 | `FrameKind` 56종 |

## 3. 앱은 어떻게 하나 (보조 증거, 공식 규칙 아님)

로컬 분석(에셋 체크아웃 `reference/dune-steam-app/<빌드>/analysis/effect-model-2026-10-14.md`, git 무시)에서
읽은 것:

- 인쇄된 아이콘 값(Agent 칸 자원, Reveal 자원·설득·검, 칸 비용·보상)은 카드 속성 데이터이고, 공통 능력 넷(Agent,
  Reveal, Space, Acquire)이 처리한다. 글로 된 효과만 따로 능력을 가진다.
- **앱도 글 효과를 데이터만으로 적지 않는다.** 능력 클래스 603종 중 554종을 카드 하나만 쓰고, Imperium·Tleilaxu
  카드 194장 중 150장이 자기만의 능력 클래스를 가진다. 대신 모든 능력이 같은 틀을 따른다: 선택(Targets) → 요건
  검사(Cost, 그리고·또는·아님으로 조합) → 실행(공통 helper로 지불·얻기·뽑기·폐기·사기).
- 글 효과는 차례마다 "미뤄 둔 능력" 목록에 오른다. "you may"(선택), 의무(남아 있으면 차례를 못 끝냄), 숨김, 선택이
  없으면 바로 실행의 네 가지 표시가 있다. 보상이 능력을 플레이어에게 주면(Conflict 보상 등) 쓸 때까지 목록에 남는다.
- 유발 효과는 한 곳의 사건 반응기가 고정 순서로 돌리고, 플레이어에게 순서를 묻지 않는다.

여기서 가져올 것은 **틀**이다: 인쇄 값은 데이터, 글 효과는 공통 모양의 능력 기록, 결정과 상태 변화는 공통 조각만
지난다. "모든 카드를 데이터로"는 앱보다 높은 목표이므로, 흔한 모양은 데이터로 적고 나머지는 공통 조각만 쓰는 전용
hook으로 두되 그 수를 세어 줄여 간다.

## 4. 설계

### 4.1 능력 기록

카드(개인 카드, 책략, 지도자, Tech, 계약, Conflict, 보드 칸, Scouts 카드)는 **인쇄 값 + 능력 목록**이다. 능력 하나는
`effect_dsl.EffectSection`/`IntrigueOption`을 넓힌 기록이다.

| 칸 | 뜻 | 예 |
| --- | --- | --- |
| 시점 | Agent 칸, Reveal, 획득할 때, 폐기할 때, 버릴 때, 차례 시작, Plot, Combat, Endgame, 사건 유발 | Reveal |
| 표시 | 의무 / 선택("you may") / 자동(선택이 없으면 바로) | 선택 |
| 요건 | 조건 나무(그리고·또는·아님; "또는·아님"은 처음 인쇄한 카드와 함께 더한다, A0): 동맹, 영향력 n, 다른 진영 카드(Bond), 첩자 n, 계약 n, 표지 n… | Bene Gesserit Bond |
| 비용 | 지불(자원), 영향력 잃기, 버리기, 폐기, 병력 잃기, 첩자 회수, 에이전트 회수… | 스파이스 4 |
| 효과 | 얻기(자원·VP·영향력·설득·검), 뽑기(카드·책략), 모집·배치·후퇴, 첩자 놓기·옮기기, 사기, 폐기, 계약 받기·완수, 연구·Tleilaxu·표본, 모래벌레·방패벽… | VP 1 |
| 구조 | 순서대로 / 택일(—OR—) / 서로 다른 k개 / 개수만큼(for each) / 최대 n | 택일 |

- 지금 `effect_dsl.py`의 조건 20종·비용 11종·보상 34종·유발 2종이 출발점이다. 같은 일을 하는 `rules/effects.py`·
  `board.ResourceCost`와의 중복은 이때 합친다(refactoring-plan.md 부수 항목).
- **전용 hook**: 데이터로 적으면 더 복잡해지는 효과는 `Custom(<id>)`로 둔다. hook은 공통 결정과 공통 상태 함수만 쓸
  수 있다. 목록과 수를 계획서에 적고 단계마다 줄인다.

### 4.2 실행기

- 열린 차례(Agent 차례, Reveal, Combat 우선권, Endgame…)마다 **대기 능력 목록**을 둔다. 지금의 Agent 효과 frame이
  여러 묶음(카드 효과, 칸 효과, 영향력, 계약, 배치)을 한 번에 들고 "아무 순서로나" 내는 것을 일반화한 것이다.
- 제시는 지금 엔진의 방식을 차례 종류별 정책으로 둔다. Agent 차례는 대기 능력마다 첫 선택의 행을 한꺼번에 낸다.
  Reveal도 2026-10-14(codec v147)부터 대기 선택의 행을 구매·이득과 함께 한꺼번에 낸다(그 전에는 선택 하나씩 frame을 쌓고
  미루기·다시 열기를 두었다). 책략은 비용 슬롯 뒤 보상 슬롯을 인쇄 순서로 낸다. 의무
  능력이 남으면 차례 종료가 보류된다(OQ-057, 한 번 누르는 턴 종료). 선택이 없는 자동 능력은 결정 없이 실행된다.
- 해결: 요건 확인 → 비용 선택 → 보상 선택(인쇄 순서) → 적용. 책략 해석기(`effect_interpreter.choice_slots`)의 순서를
  그대로 쓴다.
- 유발: 사건 하나에 붙은 유발 능력을 한 곳에서 정해진 순서로 연다. 순서는 지금 엔진의 순서를 그대로 둔다(규칙 문서와
  OQ가 정한 것).

### 4.3 결정(행동)

- 실행기의 결정 **모양**은 지금 엔진이 쓰는 것들이다: 인쇄된 아이콘마다 한 행동(OQ-027), 선택 화살표는 "거절" 한 줄 +
  "비용과 보상을 한 번에" 한 줄(지불할 대상·고를 진영이 인자로 붙는다), 비용·보상 선택 슬롯(책략), 택일, 미뤄 둔 Reveal
  선택. 행동 template은 (모양, 출처) → template 표로 낸다. 이 표는 A단계 뒤에도 쓰는 실행기의 일부다(버리는 흉내 층이
  아니다).
- 행동 이름과 단위를 바꾸는 것(출처별 `trash_*` 18종을 동사 하나로, 묶인 행동을 조각 행동 여럿으로)은 B단계이고, A단계
  뒤에 측정으로 할지 정한다(5절). 행동 이름은 엔진 밖 약 5,300곳이 읽는다(2026-10-14 셈: AI 810, 화면 JS 361·표시 68·
  서버 27, 테스트 3,930, E2E 183, 기보 36).

### 4.4 망

- 카드 특성: 능력 목록에서 만든다(시점별로 조각 종류·양, 요건 종류, 비용 종류, 구조). 그 카드만 가진 효과 특성은
  전용 hook 카드에만 남는다.
- 행동 특성: template마다 (동사, 출처, 대상 종류)를 적은 표에서 만든다. `trash_agent_card`와 `trash_reveal_card`는
  "폐기" 동사를 공유하고 출처만 다르다. 행동 이름을 바꾸지 않고도 망이 같은 조각을 같은 것으로 읽는다.
- 둘 다 망의 입력이 바뀌므로 A단계가 끝난 뒤 한 번 다시 학습한다(레시피: 레시피 MLP 증류 + 1e-5 강화학습).

## 5. 단계

### 조사 결과 (2026-10-14, `tmp/claude/<세션>/composed/`의 두 목록)

- Agent 칸 104개: 단순 이득 17, 조건부 이득 35(아이콘 여럿 11 포함), 비용→보상 22, 고르기 14, **특이 흐름 16**
  (Signet Ring의 지도자별 상태, Subversive Advisor·Treacherous Maneuver가 칸의 영향력 단계를 붙잡음, Long Reach·Stitched
  Horror의 "둘 다 고른 뒤 지급", Scientific Breakthrough의 진행 상태, Slig Farmer의 순변화 지불, Corrinth City의 두 단계
  지불, Long Live the Fighters, 상대에게 frame을 여는 Covert Operation·Holy War, 다른 접합 칸을 지우는 Dissecting Kit·
  Beguiling Pheromones, Chairdog).
- Reveal 선택 26개(카드 28장), Reveal 자동 이득 25칸, 획득 12·폐기 4·버림 2·차례 시작 1·아이콘 조건 2: **특이 흐름 21**
  (Desert Power의 설득 보류, Priority Contracts의 자동 spice 억제, Covert Operation의 frame 교체, 빈 첩자 공급의 회수 후
  배치, Spy Network의 즉시 뽑기, Command (6+)의 두 번 계산, 미루기·효과 종류별 다시 열기(codec v147에서 없어짐), 소유자가
  시점을 정하는 이득 묶음 등).
- 책략 90 identity는 이미 데이터다. 그중 약 20장이 카드 하나만 쓰는 조각에 기댄다(Call to Arms, Harvest Cells, Coercive
  Negotiation, Manipulate, Twisted 카드들, Navigation 등).
- 특이 흐름은 A단계에서 전용 hook으로 옮긴다. 둘 이상의 카드가 같은 모양을 쓰면 실행기의 모양으로 올린다.

### A단계 — 내부 교체 (행동·관측·사건 그대로)

| 단계 | 내용 |
| --- | --- |
| A0 | 능력 기록, 대기 능력 실행기, (모양, 출처) → template 표, 같음 확인 도구(6절) — 끝남(2026-10-15, 아래 "A0에서 만든 것") |
| A1 | 책략 90 identity를 실행기로(이미 데이터라 실행기 검증용) — 끝남(2026-10-16, codec v148, 아래 "A1에서 만든 것") |
| A2 | 개인 카드 Agent 칸 단순·조건부 이득 52개 — 44개 끝남(2026-10-16, 아래 "A2에서 만든 것"), 7개는 hook으로·1개는 A3로 |
| A3 | 개인 카드 Agent 칸 비용→보상 22개, 고르기 14개, Tread in Darkness, A2가 남긴 특이 흐름 7개. 조사(2026-10-16, git 무시 `tmp/claude/4767ed6a/a3/agent-choice-survey.md`)에서 처리기마다 사건 출처·순서가 달라 모양별로 나눈다: A3a hook 등록부와 A2의 특이 흐름(끝남), A3b 대상 없는 선택 지불 S1(끝남), A3c 필수 대상 고르기 S5(진영·첩자 칸·상대 병력·계약, 끝남), A3d 대상을 고르는 선택 화살표 S2a·S2b(보상을 곧바로 주는 것, 비용 뒤에 아이콘으로 거는 것 — 기록에 "걸리는 보상 아이콘" 칸이 따로 필요; 버리기 7칸·책략 폐기 2칸 끝남, 개인 카드 폐기 3칸과 Piter는 A3e로), A3e 검은 폐기 아이콘·한 칸 안 연속 고르기 S3·S4(폐기 칸 5개 끝남; Arrakis Observer·Piter·Control the Spice는 A3f로), A3f 평범한 줄이 한쪽인 고르기 S6·고르기 아이콘이 섞인 칸 S7(Tread in Darkness)·선택 획득 S8 — 모두 끝남(2026-10-16) |
| A3g | A2·A3 목록에 없던 개인 카드 Agent 칸 15개(Treacherous Maneuver, The Beast's Spoils, Long Reach, Holy War, Arrakis Revolt, Immortality 접합·연구 칸 6개, 그 밖 4개 — 아래 "A3f-5에서 만든 것" 끝). 사용자 결정(2026-10-16): A7로 미루지 않고 A3에 이어 지금 — 끝남(2026-10-16, 아래 "A3g에서 만든 것") |
| A4 | Reveal 선택 26개와 Reveal 자동 이득, 획득·폐기·버림·차례 시작 효과. 조사(2026-10-16, git 무시 `tmp/claude/4767ed6a/a4/reveal-survey.md`)의 하위 단계 A4a~A4h — 끝남(2026-10-16, 아래 "A4a·A4c에서 만든 것", "A4d~A4h에서 만든 것") |
| A5 | 보드 칸, Conflict 보상, 계약. 조사(2026-10-16, git 무시 `tmp/claude/4767ed6a/a5/a5-survey.md`)의 하위 단계 A5a(계약 28장)·A5b(Conflict 19장, 보상 57줄)·A5c(보드 칸 인쇄 아이콘)·A5d(보드 선택 아이콘과 특수 흐름 — 조사의 A5d+A5e) — 끝남(2026-10-16, 아래 "A5에서 만든 것") |
| A6 | 지도자(인장은 능력, 상시 효과는 유발), Tech. 조사(2026-10-16, git 무시 `tmp/claude/4767ed6a/a6/a6-survey.md`)의 하위 단계 A6a(Tech 획득 효과)·A6b(Tech 능력 18개)·A6c(인장 18개)·A6e(지도자 왼쪽 칸 21개, Tech 유발 둘) — 조사의 A6d·A6f는 A6c·A6e에 들어감, A6g(규칙 변경·설정·지휘관 제안)는 판단으로 정리 — 끝남(2026-10-17, 아래 "A6에서 만든 것") |
| A7 | Immortality(접합, 연구, Tleilaxu, 표본), Arrakeen Scouts, 그리고 사용자 결정(2026-10-17)으로 Sardaukar 기술 타일 7개. 조사(2026-10-17, git 무시 `tmp/claude/4767ed6a/a7/a7-survey.md`)의 하위 단계 A7a(기술 타일)·A7b(Scouts 77개)·A7c(연구·Tleilaxu 트랙 보너스, Reclaimed Forces)·A7d(Immortality 규칙 변경 넷) — A7e(장치)는 판단으로 정리 — 끝남(2026-10-17, 아래 "A7에서 만든 것") |
| 정리 | 옮기기(A0~A7)가 끝난 뒤 옛 코드에서 물려받은 처리기별 차이를 하나의 규칙으로 통일: 사건 이름, "칸 해결" 사건, 시험 해결의 답, hook. 아래 "정리 단계". codec은 A8과 함께 한 번만 올린다 |
| A8 | 망 특성(4.4)과 한 번의 재학습, 관문 뒤 플레이 서버 교체 |

- 단계마다 worktree에서 하고, 6절의 관문을 넘은 것만 master에 병합한다. 행동 이름이 그대로라 AI·화면·테스트·E2E는
  손대지 않는다.
- A8의 관문: 탐색 좌석 1 대 앱 AI 어려움 3, play-mlp 측정과 같은 시드(`checkpoints/2026-10-14/play-mlp`)에서 레시피
  MLP보다 승리 몫이 판정상 나쁘지 않을 것.

### A0에서 만든 것 (2026-10-15)

엔진에 연결하지 않은 기반이다. 엔진이 내놓는 것·하는 것은 바뀌지 않았다(관문 결과는 6절 표 아래).

- **능력 기록** `content/uprising/abilities.py`: `Ability(timing, sections, mark, structure, requirement, trigger,
  at_turn_start, hook)`. 시점 10종(`AbilityTiming`), 표시 셋(의무·선택·자동), 구조 셋(순서대로·택일·따로 쓰는 줄,
  OQ-058). "서로 다른 k개·개수만큼·최대 n"은 DSL처럼 보상에 남는다(`GainInfluence.distinct`/`times`,
  `GainSolariPerUnitType`, `DeployFromGarrison.up_to`). 요건의 "또는·아님"은 넣지 않았다: 화면이 DSL 조건마다 두 언어
  문구를 요구하고(`display/effect_dsl_text*.py`), 지금 DSL로 적힌 카드(책략·Navigation)에는 그런 조건이 없어 넣으면 쓰이지
  않는 일반 문구를 지어내야 한다. 인쇄한 카드는 있다: Interstellar Conspiracy의 "If grafted with an Emperor or Spacing Guild
  card"(카드 전용 코드, 문구 "황제 또는 우주 항행 길드 카드와 접합했다면"은 `display/tokens_ko.py`에 있음). 그 Agent 칸을 기록으로
  옮길 때 그 문구와 함께 더한다(진영 집합 하나를 받는 조건이면 일반 "또는"이 필요 없을 수도 있다). Twisted 카드의 "if it is not a
  Twisted card"는 줄의 조건이 아니라 비용 조각의 인자라(`GiveIntrigueToOpponent`·`TrashIntrigueCard`) 이미 데이터로 적혀 있다. hook은 이름만 두었다(지금 0개). 책략·Navigation 선택지 124개는 `intrigue_ability`/`intrigue_option`으로
  손실 없이 왕복한다(A1은 전사를 그대로 두고 실행기로 푼다).
- **(모양, 출처) → template 표** `rules/action_shapes.py`: 전 옵션 카탈로그의 행동 279종마다 동사(45종)·출처(20종)·대상
  (25종), 거절·빈 확인이 무엇에 답하는지(`of`), 한 id가 답하는 다른 동사(`also`: `choose_intrigue_faction`은 영향력을
  내기도 얻기도 한다), 같은 동사·출처·대상의 갈래(`variant`), 위치 꼬리표(`box`·`source`). 양방향으로 쓴다:
  `ACTION_SHAPES[id]`는 망의 행동 특성(4.4), `template_id(동사, 출처, …)`는 실행기가 낼 id(정확히 하나가 아니면
  `LookupError`). 테스트가 id 집합을 전 옵션 카탈로그와, 인자 이름을 대상과, 꼬리표를 카탈로그와 맞댄다.
- **실행기 핵심** `rules/ability_executor.py`:
  - `PendingAbility(source, ref, sections, step, chosen, rewards_applied, shield_wall)`과 frame context에 넣는 문자열
    꼴(`encode_pending`/`decode_pending`). 적용할 줄은 열 때 판정해 둔다(책략은 낼 때).
  - 출처별 능력 찾기(`ability_of`, 지금은 책략만), 한 능력의 선택 순서는 해석기의 것(`choice_slots`: 비용 선택 전부,
    그다음 보상 선택을 인쇄 순서로).
  - 선택 조각(piece) 19종마다 줄을 만드는 `piece_rows(…, source, refusals, chosen, played_card_id, tag_value)`: 대상과
    순서는 엔진의 것이고, id는 표에서 출처로 고른다. 같은 trash가 책략이면 `trash_intrigue_card`, Agent 칸이면
    `trash_agent_card`(접합 둘째 카드면 `box=1`), 공개한 카드면 `trash_reveal_card`(`source=카드`).
  - 제시 방식 `Presentation(refusals, rewards_row)`: 차례 위에 쌓인 frame(책략 선택)은 선택 조각의 거절 줄과 자동 보상
    줄(OQ-015)을 내고(`STACKED`), 자기 차례(Agent·Reveal)는 둘 다 없다(`IN_TURN`, OQ-095 (2)·(7)). Spy 배치를 할 수
    없을 때의 넘기기는 어느 차례든 남는다(OQ-057).
  - 대기 목록 정책(항목 꼴을 가리지 않는 일반 함수): 모든 항목의 줄을 항목 순서로 한꺼번에(같은 줄은 한 번),
    행동이 고르는 항목은 그 줄을 내는 첫 항목, 의무 항목이 무언가를 낼 때만 차례 종료가 보류된다.
- **엔진과 맞댄 증거**: 시드 판의 매 상태에서 실행기가 연 책략 선택의 줄이 `legal_intrigue_choice_actions`와 같고,
  대기 목록 정책이 Reveal frame의 줄·`finish_reveal` 보류·고른 항목과 같다. 무작위 200판·휴리스틱 40판에서 조각 19종이
  모두 나왔고 차이 0(Reveal 상태 5,380개, 고르기 10,866번). pytest에는 무작위 12판을 둔다
  (`tests/unit/rules/test_ability_executor.py`; 변이 8개를 잡는다). 책략 쪽 비교는 A1에서 엔진이 실행기를 쓰면 의미가
  없어지므로 그때 같음 확인 관문으로 넘긴다. Reveal 쪽은 A4까지 둔다.
- **A1이 할 일**: `INTRIGUE_CHOICE` frame의 진행 상태(`sections`·`slot`·`chosen_factions`·`rewards_applied`·
  `shield_wall_at_play`)를 `PendingAbility` 하나로 바꾸고(관측이 읽는 `card_id`·`peeked_card_id` 키는 그대로),
  `legal_intrigue_choice_actions`를 `ability_rows`로, `apply_intrigue_choice`의 조각별 처리를 실행기의 적용 함수로
  옮긴다(사건 id·내용 그대로). 따로 쓰는 줄(`INTRIGUE_EFFECTS`)도 같은 항목으로. 이 단계부터 결정 stack 모양이 바뀌므로
  codec을 올린다(6절 3번).

### A1에서 만든 것 (2026-10-16, codec v148)

책략(Navigation 카드 포함)의 선택 해결을 실행기로 옮겼다. 제시하는 행동·사건·관측은 그대로이고 결정 stack의 꼴만 바뀌었다(관문 결과는
6절 표 아래).

- **frame이 들고 있는 것:** 책략 선택 frame(`INTRIGUE_CHOICE`)은 진행 상태 키(`option`·`sections`·`slot`·`chosen_factions`·
  `rewards_applied`·`shield_wall_at_play`·`deferred_factions`·`tactics_lost`) 대신 `pending_ability` 하나(`PendingAbility`의 문자열
  꼴)를 든다. 남은 키는 관측이 읽는 `card_id`·`peeked_card_id`와 `source`·`separate_effect`. 따로 쓰는 줄 frame(`INTRIGUE_EFFECTS`,
  OQ-058)은 `used` 대신 **아직 쓰지 않은 줄마다 항목 하나**(그 줄 하나를 해결하는 항목)의 대기 목록 `pending_lines`를 든다
  (`encode_pending`; `card_id`·`option`·`player`·`source`는 그대로). 낼 때 바로 해결한 비용 없는 줄은 쓴 줄이다. 줄 하나를 쓰면 그 항목이
  목록에서 빠져 선택 frame을 연다. 그래서 저장된 항목은 어디서나 "그 줄들을 해결하는 항목"이라는 같은 뜻이다(처음엔 줄 frame에 남은 줄
  전체를 항목 하나로 두었는데, 같은 칸이 frame마다 다른 뜻이 되어 리뷰 지적으로 바꿨다). 바깥에서 읽는 도우미는
  `intrigue.pending_intrigue_ability`(선택 frame, 출처가 책략인 항목만)·`intrigue_lines_used`(줄 frame)이고 앱 AI와 테스트가 쓴다.
- **`PendingAbility`에 더한 칸 둘:** `held`(나중 단계에서 효과가 나는 값: "Choose two"가 둘 다 고를 때까지 미뤄 둔 진영, OQ-057)와
  `tally`(한 조각씩 내지만 출처 하나인 비용의 누계: "lose N troops"가 Conflict에서 뺀 병력, Chani의 Tactics 토큰은 마지막 조각에서 한 번
  움직인다 `[FAQ p. 1]` `[Bloodlines p. 12]`). 문자열 꼴은 칸 9개(A0의 7칸 꼴은 거절한다).
- **실행기의 적용 함수**(`rules/ability_executor.py`): `apply_piece`(조각 하나의 답을 적용하고 다음 항목을 돌려줌; 빈 supply에서 배치
  전 회수처럼 조각을 준비만 한 답은 `stays`), `acquire_by_piece`(획득 조각은 카드가 끝난 뒤 따라오는 frame 때문에 frame 쪽이 순서를
  쥔다; "손으로" 조건은 frame이 나아가기 전 상태에서 `acquires_to_hand`로 판정), `apply_automatic_rewards`(자동 보상과 차례 장부, 옛
  `_apply_section_rewards`), `rewards_wait`(OQ-106의 draw 단계). 답이 무엇을 하는지는 행동 id가 아니라 모양 표로 읽는다(거절·빈 확인·
  회수·대상). 거절과 빈 확인의 사건 이름은 행동 template별 표 `_PASSED_EVENTS`에 있다(다른 출처를 이 함수로 보내는 단계가 자기 template을
  더한다; 페이지 이름표 테스트는 `table_event_kinds()`로 읽는다). 획득 조각의 빈 확인 사건은 카드를 함께 적으므로 frame 쪽이 낸다. 조각의
  사건 id는 `<출처>:slot:<단계>:…` 그대로.
- **`rules/intrigue.py`에 남은 것:** 카드 내기·비용, 두 frame 열기, 조각이 쌓은 frame을 들어 올렸다 다시 얹기, 획득 조각의 순서,
  카드 끝내기(버림 더미·앞면 보관·Navigation). `legal_intrigue_choice_actions`는 `ability_rows(…, STACKED, played_card_id=…)`다.
- **속도:** 실행기가 매 줄 `template_id`(표 279행 훑기)를 불러 책략 frame의 합법 행동 계산이 처음엔 2.3배 느렸다. `template_id`와 능력
  찾기, 문자열 해독을 캐시해 시작 master보다 조금 빠르다(6절 표 아래). 캐시가 기대는 모양 표는 읽기 전용(`MappingProxyType`)이다.
- **테스트:** 실행기 줄 == 엔진 줄 비교(책략 쪽)는 엔진이 실행기를 쓰게 되어 지웠다(Reveal 쪽은 A4까지 둔다). 대신 저장 꼴(`held`·`tally`
  포함), "Choose two"의 미룸과 둘째 진영이 없을 때의 빈 확인, Tactics 토큰 한 번 이동, 거절 사건 이름을 실행기 단위로 지키고, 시드 판에서
  두 frame의 저장 꼴을 본다. frame 키를 직접 읽던 테스트 둘은
  `intrigue_lines_used`로 읽게 했다(기대값 그대로). 옮긴 도우미 하나(`_trash_intrigue_hand_card`)는 import 경로만 바꿨다.
- **hook:** 0개 그대로.
- **A2가 할 일:** 개인 카드 Agent 칸의 단순·조건부 이득 52개를 능력 기록(`AbilityTiming.AGENT_BOX`)으로 적고 Agent 효과 frame의 대기
  항목으로 옮긴다. 설계는 A2를 시작할 때 정한다. A1까지 실행기에 있는 것: 자기 차례 제시 `IN_TURN`(거절 줄·자동 보상 줄 없음), 접합
  둘째 칸의 꼬리표(`tag_value=1`), 대기 목록 정책(`pending_rows`·`entry_taking`·`holds_turn_end`), 거절·빈 확인 사건 이름 표. 아직 없는
  것: Agent 칸은 인쇄된 아이콘마다 행동 하나(`resolve_agent_card_effect(effect=…)`, OQ-027)인데 실행기의 자동 보상은 한 줄로 한꺼번에
  내므로, 아이콘별 줄을 내는 제시가 필요하다.

### A2에서 만든 것 (2026-10-16, codec 그대로 v148)

개인 카드 Agent 칸 52개 중 44개를 능력 기록으로 옮겼다. 결정 stack의 꼴(frame 키)은 그대로라 codec을 올리지 않았다. 제시하는 행동·
사건·관측도 그대로다(관문 결과는 6절 표 아래).

- **조사:** 52개가 지금 어떻게 도는지 칸마다 정리했다(git 무시 `tmp/claude/4767ed6a/a2/agent-gain-survey.md`, 무작위 4,400판 탐침으로
  확인). 코드 경로가 8묶음이고, 사건 순서·출처 문자열은 묶음마다 다르다. 하지만 규칙적인 묶음은 "보상 종류별로 정해진 자리"로
  설명된다.
- **기록** `content/uprising/agent_abilities.py`: 44개. 한 번에 해결하는 칸 35개, 아이콘별 칸 9개(`Ability.icons`, OQ-027). 배치 때
  정해지는 조건(메이커 칸, 이미 플레이된 카드 사이의 유대감)은 `requirement`로 카드를 낼 때 판정하고(거짓이면 칸이 대기하지 않음,
  OQ-028 (a)), 나머지 조건은 줄의 `condition`으로 해결할 때 판정한다(거짓이면 기다렸다가 턴 끝에 사라짐, OQ-057 (1)). 유대감 칸은 둘
  다 한다(같은 차례의 폐기로 깨질 수 있음).
- **DSL 추가:** 조건 6개(`AtMakerSpace`, `FactionBond`, `SpyRecalledThisTurn`, `UnitsInConflictAtLeast`, `ContractCompletedThisTurn`,
  `Grafted`)와 진영을 지정하는 `HasAlliance(faction)`, 보상 4개(`ReturnThisCardToHand`, `BoostNextBeneGesseritCard`,
  `DrawPerSandwormInConflict`, `LookAtIntrigueKeepOne`). 두 언어 표시 문구는 모두 `tokens_ko.py`의 카드 문장과 용어집에서 가져왔다.
  "이 카드가 플레이 중"(Usurp로 빌린 카드는 아님, OQ-054)은 인쇄 조건이 아니므로 조건으로 두지 않고 "핸드로 되돌림" 보상의 성립
  판정으로 두었다.
- **실행** `rules/agent_box_abilities.py`: 한 번에 해결(`resolve_box`)과 아이콘별 해결(`resolve_box_icon`) 두 규칙. 한 번에: 소유자 이득·
  책략 뽑기(`<칸>:intrigue_draw`)를 frame 쓰기 전에, 칸의 사건, 그다음 frame을 쌓을 수 있는 후속(계약·연구·Tleilaxu·표본·책략 엿보기·
  선택 폐기 frame, 출처 `<칸>`)과 카드 정의 id로 이름 붙인 카드 뽑기, 병력 부족 사건은 맨 뒤. 아이콘별: 이득·부족(`<칸>:<아이콘>`)·
  책략 뽑기를 쓰기 전에, 표본(`<칸>:specimen`)→연구→카드 뽑기를 쓴 뒤, 아이콘 사건은 맨 뒤. 배치 판정(`opens_at_placement`)과
  아이콘이 막힌 이유(`box_icon_block`; 화면이 읽는 `AgentIconBlock`은 이 모듈로 옮겼다)도 기록에서 나온다. `agent_effects.py`는 해당
  분기를 지워 754줄 줄었다.
- **남긴 것:** 사건이 없거나 출처 문자열이 제각각인 7개(Seek Allies, Occupation, In High Places, Overthrow, Lisan al Gaib, Guild 영향력
  칸 #52, Clandestine Meeting)는 아직 자기 분기로 돈다. 전용 hook 등록부를 만들어 옮길 차례다(A3에서 특이 흐름과 함께). Tread in
  Darkness는 칸 안에 고르기(선택 폐기)가 있어 A3로 넘긴다. hook 0개.
- **테스트** `tests/unit/rules/test_agent_box_abilities.py`: 기록 표(44개, 아이콘 키와 순서, 배치 조건 종류), 막힌 이유 값, 아이콘·한 번
  해결의 사건 순서와 출처, Throne Room Politics의 폐기 frame 출처, 200판에 안 나온 Pointing the Way. 화면 일관성 테스트
  (`test_unavailable_consistency`)는 모든 효과×모든 키를 옛 답과 맞대는데, 칸이 인쇄하지 않은 키는 새 함수 대신 옛 공통 규칙이 답하게
  해서 기대값을 바꾸지 않았다.

### A3a·A3b에서 만든 것 (2026-10-16, codec 그대로 v148)

- **hook 등록부(A3a):** 사건이나 출처가 어떤 공통 규칙에도 안 맞는 Agent 칸은 기록에 `hook=<이름>`만 두고 해결은
  `agent_effects._BOX_HOOKS`의 함수가 한다(옛 분기를 옮긴 것). 지금 6개: Seek Allies(폐기 사건만), Overthrow(방문 진영 영향력, 칸 사건 없음),
  Lisan al Gaib(영향력 사건만), Clandestine Meeting(책략 뽑기 출처 `<칸>:intrigue`), Occupation(전투 아이콘이 frame을 다시 씀, 뽑기
  `<칸>:draw`), In High Places(스파이 frame 밑에 뽑기). 기록의 줄은 DSL이 가진 조각을 적어 망의 카드 특성에 쓴다(Overthrow·Seek
  Allies는 아직 비어 있음). 등록부와 기록이 서로 맞는지 테스트가 지킨다. Overthrow의 "방문한 진영 칸" 배치 조건은 인쇄 조건이 아닌
  엔진 규칙이라 기록 검사 앞에서 판정한다. Guild Impersonator는 hook 없이 기록이 됐다: 한 번 해결 규칙에 고정 진영 영향력
  (`<칸>:influence:<진영>`, frame 쓰기 전)을 더했다.
- **대상 없는 선택 지불(A3b):** Ecological Testing Station, Smuggler's Haven, Organ Merchants, Tleilaxu Surgeon을 선택(OPTIONAL) 기록
  "비용 → 보상"으로. 실행기의 지불 모양이 원시 줄(거절, 그다음 비용 이름의 지불 줄 — 낼 수 있고 무언가를 살 때만, OQ-071), 화면이
  읽는 비용·보상 막힘, 답의 사건(`round:R:player:P:agent_card_payment:paid`, 카드 id 없음, 자원과 쓴 양)과 후속(뽑기 출처
  `…:agent_card_payment`, Tleilaxu `…:agent_card_payment:tleilaxu`)을 낸다. DSL 비용 `SpendSpecimens`를 더했다(표시 문구는
  `tokens_ko.py`의 "표본 1개 지불"). 일반 해결은 이 넷에 옛 시험 해결 답을 그대로 낸다(Surgeon은 "해결 불가", 나머지는 예외 =
  "가능") — 선택 칸이라 화면·턴 종료가 그 답을 먼저 거르지만, 달라지지 않게 두었다.
- **남은 것:** A3c~A3f(위 표). 조사가 짚은 함정: 처리기별 사건 출처(폐기 `round:R:player:P:agent_card:trash:…`, 버리기
  `…:agent_card_discard`, 지불 `…:agent_card_payment`), 해결 사건이 없는 답이 많음, 화살표 보상을 아이콘으로 거는 칸은
  `Ability.icons`가 아닌 별도 칸이 필요(아니면 배치 때 걸리고 "진행 중" 판정이 바뀜), A1 실행기의 Spy·영향력·획득 줄은 Agent 칸
  제공자와 세 곳에서 다름.

### A3c에서 만든 것 (2026-10-16, codec 그대로 v148)

- **필수 대상 고르기:** 줄 하나가 대상 하나를 고르는 필수 칸 6개를 기록으로 — 선택 진영 영향력(Interstellar Trade·For Humanity,
  Public Spectacle은 "이번 차례 스파이 소환" 조건), Spy 칸(Bene Gesserit Operative·Reliable Informant, Double Agent), Disruption
  Tactics, CHOAM Demands. 실행기의 대상 모양(`agent_box_abilities.target_piece`·`target_rows`)이 줄을 내고, 고를 것이 없으면 확인 줄 없이
  기다렸다가 턴 끝에 무산된다(OQ-057 (1), OQ-060). 한 번 해결(`resolve_box`)은 줄이 있는 동안 예외를 낸다 — 예외 종류도 옛 것 그대로
  (시험 해결이 셋 다 "가능"으로 읽는다).
- **줄의 출처:** 영향력은 A1 실행기의 고르기 줄(`piece_rows`)을 처음 다시 쓴다 — 새 인자 `empty_confirm=False`로 쌓인 책략 frame의
  빈 확인 줄만 뺐다. Spy는 Agent 칸 규칙(공급에 Spy가 없을 때 먼저 소환과 그 넘기기)이 A1 실행기와 달라 `agent_spy_rows`로 옮겼고,
  Arrakis Observer의 Deep Cover Spy(`PlaceSpy(shared_post=True)`)도 이것을 쓴다. Reliable Informant의 관측소 제한은 카드에 인쇄된
  진영 표시(`agent_spy_factions`)에서 온다(기록은 제한 없는 `PlaceSpy`). 답은 Spy·후퇴·계약이 옛 처리기 그대로, 영향력만 실행기에서.
- **DSL:** `PlaceSpy.visited_space`(이번 차례 Agent를 보낸 칸에 연결된 관측소, 공유 가능 — Double Agent), 보상 `ForceEnemyRetreat`·
  `CompleteContract`. 표시 문구는 `tokens.py`·`tokens_ko.py`의 카드 문장과 같다(테스트가 지킨다). 일반 Spy 판정은 `visited_space`를
  알 수 없어 예외를 낸다.
- **남은 것:** A3d(대상을 고르는 선택 화살표), A3e, A3f.

### A3d에서 만든 것 (2026-10-16, codec 그대로 v148)

- **버리기 화살표 7칸:** Delivery Agreement, I Believe, Engineered Miracle, Space-time Folding, Guild Envoy(필수), Captured Mentat,
  Guild Spy. 기록은 "[You may] discard a card → …": 비용은 첫 줄에, 뒤 줄의 조건 `DiscardedCardHasFaction`(버린 카드의 진영 — Space-time
  Folding의 두 번째 카드, Guild Envoy의 두 장, Guild Spy의 책략)은 비용을 낸 카드로 판정한다(일반 해석기는 예외를 낸다). 실행기의 버리기
  모양(`discard_box`·`discard_rows`·`apply_discard`)은 선택 화살표의 거절, 그다음 손패마다 한 줄; 답은 버리기 처리기의 출처
  (`round:R:player:P:agent_card_discard`, 카드 id 없음) 그대로 — 자원은 frame 쓰기와 함께, 계약 `…:contract_reward`, 뽑기
  `…:<버린 카드>:draw`. 필수인 Guild Envoy는 손패가 비면 기다렸다가 무산된다.
- **비용 뒤에 거는 보상 아이콘:** 기록에 `Ability.armed_icons`를 더했다 — 줄마다 키 하나, 배치 때가 아니라 비용의 답이 건다
  (`effects.arm_agent_icons`). 버린 카드가 조건을 못 맞춘 줄은 걸지 않는다. 걸린 아이콘은 옛 아이콘 경로가 키별로 해결한다(OQ-027).
  `icons`(배치 때 거는 인쇄 아이콘)와 따로 두어 "진행 중"·화면 막힘 판정이 바뀌지 않는다(조사가 짚은 함정).
- **책략 폐기 화살표 2칸:** Branching Path(보상을 아이콘으로 검), Junction Headquarters(2 스파이스도 내고 1 VP). 동맹 조건은 비용을
  낼 때 판정(OQ-028). 실행기의 책략 모양(`intrigue_box`·`intrigue_rows`·`intrigue_cost_block`·`apply_intrigue_payment`)이 거절과
  책략마다 한 줄(`trash_intrigue_for_agent_card` 또는 `pay_agent_card_intrigue_and_spice`), 사건은 `<칸>:intrigue_payment` 아래.
- 선택 화살표는 여전히 줄로만 해결된다: 일반 해결은 옛 시험 해결 답(예외 = "가능")을 그대로 낸다(`optional_arrow`).
- **남은 것:** 개인 카드 폐기 화살표(Shishakli/Replacement Eyes, Pivotal Gambit, Elite Forces)와 Piter(병력 잃기)는 DSL에 개인 카드
  폐기·병력 잃기 "비용"을 정해야 해서 A3e(검은 폐기 아이콘·한 칸 안 연속 고르기)와 함께.

### A3e에서 만든 것 (2026-10-16, codec 그대로 v148)

- **폐기 칸 5개:** 검은 폐기 아이콘이 칸 전부인 Calculus of Power·Desert Survival·Eliminate Allies(#1)와 Ruthless Leadership(아이콘 둘,
  "분쟁에 사다우카 지휘관이 있다면" 조건은 폐기할 때마다 판정, OQ-028), 폐기 화살표 Shishakli/Replacement Eyes(→ 카드 1장),
  Pivotal Gambit(이 카드 폐기 → 병력·1등 보상 영향력 약속을 아이콘으로 검), Elite Forces(손패 폐기 → 황제 카드면 책략·병력을 아이콘으로
  걸고 Combat은 곧바로).
- **DSL:** 비용 `TrashCard`(손패·버린 더미·플레이 중 카드; `hand_only`, `this_card`), 조건 `TrashedCardHasFaction`(폐기한 카드의 진영,
  Agent 칸만 판정), 보상 `PledgeFirstPlaceInfluence`(OQ-025). 표시 문구는 `tokens.py`·`tokens_ko.py`의 카드 문장에서. 검은 폐기 아이콘은
  보상 `TrashPersonalCard()` 줄로 적는다(선택 칸).
- **실행기의 폐기 모양**(`trash_box`·`trash_rows`·`trash_block`·`apply_trash`): 거절, 그다음 폐기할 수 있는 카드마다 한 줄(Usurp로 빌린
  카드는 플레이 중이 아님, OQ-054); 조건이 안 맞으면 줄이 없다. 답은 폐기 처리기의 출처(`round:R:player:P:agent_card`, 카드 id 없음)
  그대로, 폐기 효과의 병력을 frame 쓰기에 남기고(`keep_trash_recruits`), 아이콘이 남으면 `trashes_remaining`을 frame에 직접 쓴다.
  `Ability.armed_icons`는 앞쪽 줄만 열쇠로 가질 수 있다(뒤 줄은 비용과 함께 — Elite Forces의 Combat).
- **일반 해결:** 조건 없는 폐기 칸은 선택 화살표처럼 줄로만 해결된다(옛 시험 해결 답 = 예외). Ruthless Leadership만 한 번 해결로
  가서 조건이 맞으면 예외, 안 맞으면 "해결 불가" 사건(옛 그대로).
- **남은 것(A3f):** Arrakis Observer(버리기 → Deep Cover Spy 연속 단계, 길드 카드면 사건 있는 스파이스), Piter(병력 잃기 → 아이콘),
  Control the Spice, 평범한 줄이 한쪽인 고르기 S6(Southern Faith, Possible Futures, High Priority Travel, Interstellar Conspiracy),
  고르기 아이콘이 섞인 칸 S7(Dangerous Rhetoric, Steersman, Twisted Mentat, Tread in Darkness), 선택 획득 S8(Price is No Object,
  Tleilaxu Master).

### A3f-1에서 만든 것 (2026-10-16, codec 그대로 v148)

- **선택 획득 2칸(S8):** Price is No Object(새 DSL 보상 `AcquireCardForSolari` — Solari로 내고 핸드로, 자기 Manipulate 카드 포함)와
  Tleilaxu Master(`AcquireCardUpTo(6, 핸드로 = 유전 표지 2)`, 줄 조건 유전 표지 1). 획득 모양(`acquisition.agent_box_acquisition`)은
  `rules/acquisition.py`에 둔다 — 실행기 쪽에 두면 `agent_box_abilities → ability_executor → acquisition`의 순환 import가 생겨서,
  기록은 content 모듈에서 읽는다. 줄·막힘(`NOTHING_TO_ACQUIRE`의 needed/held, `GENETIC_MARKERS`)·출처·후속 frame은 그대로.
- **일반 해결:** Price is No Object는 선택 화살표처럼 줄로만(옛 답 = 예외), Tleilaxu Master는 한 번 해결에서 옛 답 그대로 "해결 불가".
- **남은 것(A3f의 나머지):** Arrakis Observer, Piter, Control the Spice, S6 4칸, S7 4칸 — 위 "A3e에서 만든 것"의 목록.

### A3f-2에서 만든 것 (2026-10-16, codec 그대로 v148)

- **Arrakis Observer(S4):** 버리기 화살표 기록 "카드 1장 버리기 가능 → 잠복 스파이 배치; 길드 카드를 버렸다면 스파이스 2". 버리기 모양이
  버린 카드에 달린 이득을 사건으로 알리고(`…:agent_card_discard:<버린 카드>:spice`, 옛 id·내용 그대로), Spy 줄이 있으면 칸을 그 Spy
  단계에 남긴다(`agent_card_spy_pending`; Spy 배치는 필수, OQ-057 (14)). Spy 단계의 줄은 기록의 `PlaceSpy(shared_post=True)`로
  `agent_spy_rows`가, 한 번 해결은 `resolve_box`가 옛 분기처럼 답한다(줄이 있으면 예외, 없으면 Spy 표시를 지우고 "해결 불가").
  선택 화살표는 비용 뒤 필수 단계에서만 한 번 해결로 간다.
- **남은 것(A3f의 나머지):** Piter, Control the Spice, S6 4칸, S7 4칸.

### A3f-3에서 만든 것 (2026-10-16, codec 그대로 v148)

- **Piter, Genius Advisor:** 병력 잃기 화살표 기록 "병력 1 잃기 가능 → 카드 2장, 연구" — 비용 `LoseTroops()`, 두 보상은 비용 뒤 아이콘으로
  건다(OQ-106). 실행기의 병력 잃기 모양(`lose_box`·`lose_rows`·`lose_cost_block`·`apply_lose`)이 옛 줄(수비대·분쟁마다 병력, 지휘관 —
  OQ-105)·막힘(`NO_UNIT`)·순서(아이콘 걸고, frame 먼저 쓰고, 잃고, 분쟁 배치 정리)를 그대로 낸다. 걸린 아이콘 표는 이제 열쇠마다 받는
  보상들을 둔다(Piter의 `cards`는 2장, `research`). 한 번 해결은 옛 답 그대로 "해결 불가".
- **Control the Spice:** 지불 사건이 칸의 카드를 이름에 넣고 병력 수를 싣고 폐기가 따로 frame이라 어떤 공통 규칙에도 안 맞아, 기록은 줄
  ("스파이스 1 지불 가능 → 카드 1장 폐기 가능, 병력 1")과 hook `control_the_spice`만 두고 흐름은 코드로(A3a의 hook 규칙). 제공자·처리기·
  막힘은 효과 이름 대신 기록의 hook으로 고른다.
- **남은 것(A3f의 나머지):** S6 4칸, S7 4칸.

### A3f-4에서 만든 것 (2026-10-16, codec 그대로 v148)

- **평범한 줄 + 고르는 줄(S6):** Southern Faith("하나 선택: 카드 1장 / 베네 게세리트의 유대감이면: 베네 게세리트 영향력 1"), High Priority
  Travel("우주 항행 길드 영향력 2 이상이면: 하나 선택: 카드 1장 / Combat"), Interstellar Conspiracy("스파이스 1, 황제 또는 우주 항행 길드
  카드와 접합했다면: 선택 영향력 1")를 두 줄 기록으로 — 앞 둘은 `ONE_OF`, 뒤는 `SEQUENCE`. 평범한 줄은 A2의 한 번 해결 규칙
  (`resolve_box`: 칸 사건, 카드 정의 이름의 뽑기, 모자란 병력 맨 뒤)과 정확히 같아 그대로 쓴다. 실행기의 "둘 중" 모양(`either_box`·
  `either_rows`·`apply_either_influence`)이 고르는 줄의 조건이 맞고 대상이 있을 때만 그 줄을 내고 — "하나 선택"이면 평범한 줄 옆에,
  `SEQUENCE`면 혼자(그 답이 평범한 줄의 이득도 뒤에 준다) —, 아니면 frame이 평범한 줄만 낸다. DSL 조건 `GraftedWithFaction`
  ("황제 또는 우주 항행 길드 카드와 접합") — A0에서 미룬 "또는"을 진영 묶음 하나로.
- **Possible Futures:** 유대감이 있으면 고르기가 "둘 다"로 바뀌고 모자란 병력 사건 이름도 달라(`<칸>:troops:recruit_short`) hook
  `possible_futures`로(평범한 해결 = 옛 병력 2 분기).
- **남은 것(A3f의 나머지):** S7 4칸.

### A3f-5에서 만든 것 (2026-10-16, codec 그대로 v148)

- **고르는 아이콘이 섞인 칸(S7):** Dangerous Rhetoric(아이콘 `influence`, `trash_self`), Steersman(`cards`, `recall`), Twisted Mentat
  (`recall` 하나 — 아이콘 하나짜리 칸을 허용), Tread in Darkness(`trash`, `cards`, 줄마다와 배치 조건에 베네 게세리트의 유대감)를 아이콘
  기록으로. 이제 배치 때 거는 아이콘·아이콘 조건(막힘)·Tread의 배치 조건이 기록에서 나오고, 옛 `_PLACEMENT_ICONS` 표와 Tread 분기가
  없어졌다. 자동 아이콘(`cards`, `trash_self`)은 `resolve_box_icon`이 푼다 — DSL 보상 `TrashThisCard`("이 카드 폐기", 자기 폐기 표시,
  `<칸>` 출처, 폐기 효과의 병력 보존, 이미 플레이를 떠났으면 해결 불가)를 읽게 했다. 고르는 아이콘(영향력·Agent 소환·Tread의 폐기)은
  옛 제공자·처리기가 그대로 답한다. DSL 보상 `RecallAgent`(이번 차례 Agent 말고 / 이번 차례 Agent). Seek Allies의 hook 기록도 줄에
  `TrashThisCard`를 적었다(해결은 그대로 hook).
- **A3 끝:** 계획 표의 A3 대상 44칸(비용→보상 22, 고르기 14, Tread in Darkness, A2가 남긴 특이 흐름 7)이 모두 기록이 됐다(기록 88개,
  hook 8개). Agent 칸이 있는 효과 중 기록이 없는 것은 15개로, 표의 어느 단계에도 안 적혀 있다: Treacherous Maneuver, The Beast's Spoils,
  Long Reach, Holy War, Arrakis Revolt, Immortality의 접합·연구 칸 6개(Dissecting Kit, Beguiling Pheromones, Stitched Horror, Scientific
  Breakthrough, Slig Farmer, Chairdog), 그리고 효과 문장으로 "방문한 진영 영향력 2, 이 카드 폐기", "덱 맨 위 3장을 보고 뽑기·버리기·폐기
  1장씩", "카드 2장 버리고 5 Solari 지불 → 1 VP", "각 상대가 카드 1장 버림". A7(Immortality) 또는 새 단계로 정할 일이다 — 사용자 결정(2026-10-16)으로 A3g에서 옮겼다(아래).

### A3g에서 만든 것 (2026-10-16, codec 그대로 v148)

조사(git 무시 `tmp/claude/4767ed6a/a3g/agent-rest-survey.md`: 칸마다 행·사건·시험 해결 답·막힘과 2,000판 탐침, 묶음 G1~G7)를 따라 공통
모양과 정확히 같은 칸만 모양으로, 나머지는 hook으로 옮겼다.

- **한 번 해결 + 상대의 결정(3칸):** Covert Operation("각 상대가 카드 1장 버림"), Holy War("각 상대가 병력 1을 잃음. 이번 차례 Agent를
  보낸 칸을 정탐하는 상대는 그 Spy를 옮겨야 함"), Chairdog("Reveal 차례 시작 때 다른 접합 카드를 플레이에서 핸드로")를 `resolve_box`의
  한 번 해결 기록으로. DSL 보상 `EachOpponentDiscardsCard`·`EachOpponentLosesTroop`·`OpponentsMoveSpiesFromVisitedSpace`·
  `ReturnOtherGraftedCardAtRevealStart`(문구는 카드 문장에서). 한 번 해결 모양에 "상대의 결정" 규칙을 더했다: 칸의 다른 후속 뒤에,
  인쇄 순서의 마지막부터 쌓아(스택은 나중 것이 먼저 답한다) 인쇄 순서대로 답하게 — Holy War는 잃기 전부 다음 Spy 옮기기(OQ-036).
  Chairdog의 되돌림은 접합 때 좌석에 적히고(채택된 디자이너 판정) Reveal 시작에 일어나므로, 칸은 그 카드가 아직 플레이에 있는지만
  본다(없으면 기다렸다가 턴 끝에 무산, OQ-057 (1)) — `ReturnThisCardToHand`의 "플레이에 있어야"와 같은 자리.
- **hook 12개:** 나머지 칸은 행·사건·frame이 어느 공통 규칙과도 맞지 않아 흐름을 코드로 둔다(옛 해결 분기를 그대로 `_hook_*`로).
  기록은 DSL로 칸 전체를 말할 수 있을 때만 줄을 적고, 아니면 줄 없이 주석에 인쇄 문장을 둔다(A3a의 Overthrow 선례; 일부만 적으면
  나중에 기록을 일반적으로 읽는 코드가 그것을 칸 전체로 읽는다 — 리뷰 지적).
  - Subversive Advisor(방문 진영 영향력 2가 칸의 1을 대신, 칸 사건 없음), Long Live the Fighters(덱 위 3장을 보는 자기 고르기 frame —
    숨은 정보), Treacherous Maneuver(폐기 둘 + "1 대신 2", 출처에 카드 없음), Corrinth City(버리기 두 장을 하나씩, 자기 행·사건 이름),
    Arrakis Revolt(지불 행 두 갈래 + Planetologist), The Beast's Spoils(앞면 전투 아이콘별 보상, 사건 모양 둘), Long Reach(둘 다 고른 뒤
    지급, 지급하는 무산), Dissecting Kit·Beguiling Pheromones(접합 카드 폐기 — 상대 칸을 사건 없이 지우고 frame을 먼저 되쓴 뒤 폐기), Scientific
    Breakthrough(Research 뒤 남는 폐기 줄), Slig Farmer(평범한 줄 옆 지불 행이 둘 다 준다), Stitched Horror(넷 중 둘을 먼저 고름).
  - 선택인 넷(Treacherous Maneuver, Corrinth City, Arrakis Revolt, Dissecting Kit)은 기록에 선택 표시 — 옛 `OPTIONAL_AGENT_BOXES` 표를
    지웠다.
  - hook의 제공자·처리기 코드(효과 이름으로 고르는)는 그대로 두었다. 정리 단계에서 사건이 통일되면 공통 모양으로 바꿀 후보다(아래).
- **결과:** 개인 카드의 Agent 칸은 모두 기록이 됐다(103개; 기록이 없는 효과는 지도자 Signet Ring뿐), hook 20개.
  `resolve_agent_card_effect`에 남은 옛 분기는 선택 화살표 기록의 시험 해결 답(Tleilaxu Surgeon "해결 불가", 나머지 "구현 안 됨")뿐이다.

### A4a·A4c에서 만든 것 (2026-10-16, codec 그대로 v148)

조사(git 무시 `tmp/claude/4767ed6a/a4/reveal-survey.md`: 시점별 흐름 O.1~O.9, 멤버별 C·D·E, 묶음 G, 위험 R, 2,000판 탐침과 그
결과 파일 — 브랜치에서 같은 탐침을 돌려 바이트 단위로 비교한다)를 따라, 처리 코드를 거의 건드리지 않는 두 묶음을 먼저 했다.

- **A4a — 획득·폐기·버림 효과 18개:** `content/uprising/trigger_abilities.py`에 자동 기록(시점 ACQUIRE/TRASH/DISCARD, 선택 없음,
  한 줄 한 조각). 획득 효과는 구매 경로가 7개라(Reveal 줄, 따로 둔 카드, Agent 칸, 책략·지도자·Scouts 등) 세 조각 — 주인의 이득과
  Overthrow의 뽑기(`resolve_acquisition_bonus`), 고정 진영 영향력, 카드가 자리에 간 뒤의 트랙 — 이 각각 기록을 읽고, 순서는 경로마다
  옛 그대로다. Spy·계약은 경로가 그 선택을 연다(기록의 `PlaceSpy`·`TakeContract`가 그 표시). 폐기 효과는 `trash_personal_card`,
  버림 효과는 `resolve_personal_card_discard_trigger`가 기록을 읽는다. Overthrow와 Sardaukar Soldier가 따로 갖던 같은 "책략 카드
  1장" 처리를 `intrigue_deck.triggered_intrigue_draw` 하나로(자기 차례 안이면 주인의 단계로 미룸 — 출처가 바로 다음인지 정한다,
  OQ-106·OQ-042; 밖이면 바로 뽑거나 덱이 비면 대기열). DSL 보상 `AcquireBankCommander`(Sardaukar Standard).
- **A4c — Reveal 자동 이득(카드 51장, 인쇄 줄 55개):** `content/uprising/reveal_abilities.py`에 카드 id별 자동 기록(줄마다 따로).
  카드 목록(`imperium.py` 등 넷)은 `reveal_effects`를 이 기록에서 받는다(`reveal_effects_of` — 기록 줄을 처리 코드가 읽는
  `PersonalCardRevealEffect`로 옮긴다). 그래서 `rules/reveal_turn.py`(시작·늦은 지급·늦게 온 카드·Leadership·주인의 단계)는 그대로다.
  140장 모두 옮기기 전과 같은 값임을 확인했다. DSL 조건 `HasSwordmaster`·`SpyingOnMakerSpace`·`GarrisonedUnitsAtLeast`·
  `CommandReached`, 보상 `RevealPersuasion`·`RevealSwords`와 그 셈(`RevealCount`: 공개한 진영 카드마다, 플레이 중인 진영 카드마다,
  완수한 계약마다, 다른 검 카드마다) — 문구는 `tokens.reveal_effect_text(_ko)`에서.
- **남은 것:** A4d~A4h(아래). 처리 코드가 기록을 직접 읽게 하는 것(옮기는 함수 없이)은 정리 단계 후보다.

### A4d~A4h에서 만든 것 (2026-10-16, codec 그대로 v148)

- **A4d 1단계 — Reveal 선택 26개의 기록:** `content/uprising/reveal_choice_abilities.py`(효과 값별). 기록의 표시가 선택/의무를
  정한다(옛 `OPTIONAL_REVEAL_CHOICES`·`MANDATORY_REVEAL_CHOICES` 표를 지우고 읽는 곳 — 의무 선택이 차례 끝을 막는지, 화면의
  "선택" 표시와 "쓰지 않으면 사라짐" 문구 — 이 `reveal_choice_is_optional`을 읽는다). 흐름을 코드로 두는 10개는 기록에 hook 이름을
  단다(`reveal_turn.REVEAL_CHOICE_HOOKS`): In High Places의 Spy 둘, Captured Mentat의 영향력 맞바꿈, Spacing Guild's Favor의
  스파이스→영향력, Chani·Command Center의 병력 둘 후퇴, Engineered Miracle의 구매, For Humanity의 한 진영 영향력 둘, Shadout
  Mapes·Unswerving Loyalty의 병력 하나 배치/후퇴, Tleilaxu Surgeon의 병력 둘, Desert Power(인쇄 설득 보류, OQ-069), Priority
  Contracts(인쇄 스파이스는 이 선택으로만). 한 행에 비용과 대상을 함께 이름 붙이거나 칸 밖 상태를 건드려 공통 모양이 없다 —
  이것이 조사의 A4g(더 할 일 없음). DSL `TrashCard.other_in_play`(Calculus of Power), `TakeHighCouncilSeat`(Corrinth City).
- **A4d 2단계 — "대상 → 보상" 8개:** Spy Network, Arrakis Observer(Spy 소환), Calculus of Power, Disruption Tactics, CHOAM
  Demands(카드 폐기), Shrouded Counsel(보상이 폐기), Pointing the Way, Ixian Ambassador(진영 고르기). 행(대상마다 하나, 카드 이름
  `source`), 열림 판정(인쇄 조건 + 낼 대상 — 자기 폐기는 카드가 플레이에 있어야, Disruption Tactics는 조건이 없어 늘 열림), 해결이
  기록을 읽는다(`reveal_turn.target_reward_*`, `resolve_target_reward`). 사건과 frame 순서는 카드마다 옛 그대로다(고른 진영
  영향력은 얻은 뒤 frame을 닫고, CHOAM Demands는 닫은 뒤 넷을 얻는다 — 정리 단계 목록).
- **결함과 교훈:** 처음 판은 Spy 제공 함수가 "대상 → 보상" 기록 전부에 행을 내서, 대기 선택 하나의 행 목록(`pending_choice_entries`
  — 화면의 선택 머리글·행 주인, 앱 AI가 읽음)에 같은 행이 두 번 들어갔다. 합친 합법 행동은 같아 200판 같음 확인은 통과했고, 칸별
  행까지 적는 조사 탐침이 잡았다. 제공 함수 탐침 테스트가 이제 두 제공 함수가 낸 같은 행을 막는다. `engine_equivalence.py`가 대기
  선택의 행을 비교하지 않는 빈틈은 6절에 적고, 그때까지 조사 탐침 비교를 관문에 넣는다.
- **A4e — Spy 아이콘 4개:** Public Spectacle·Wheels within Wheels, Covert Operation(둘째 아이콘 = 기록의 둘째 Spy 줄, 목록 끝에 다시
  넣음), Intelligence Training(Command 조건), Undercover Asset(—OR—의 검 줄이 "+2 swords" 행)이 기록을 읽는다. 공급이 비었을 때의
  먼저 소환·넘기기 규칙(OQ-057 (14))은 그대로.
- **A4f — 둘 중 하나:** Corrinth City(5 Solari / 5 Solari 내고 원로회 자리 — Scouts 소위원회 제안까지), Delivery Logistics(설득 1 /
  계약)가 줄마다 한 행(`reveal_turn.either_rows`, 줄의 보상 → 행 이름 표)으로. 계약 줄이 있는 선택은 CHOAM 모듈에서만 열린다(옛 판정,
  CHOAM 전용 카드). Desert Power·Priority Contracts는 hook(A4d 1단계).
- **A4h:** Guild Spy(The Spice Must Flow 구매에 반응하는 Reveal 효과)와 Litany Against Fear(차례 시작의 대체 차례)를 hook 기록으로
  (`trigger_abilities.py`). 아이콘 조건 둘(Long Reach, Show of Strength)은 능력이 아니라 카드를 낼 때 인쇄 아이콘을 거는 조건이라
  카드 속성으로 둔다(정리 단계에서 DSL 조건으로 바꿀 수 있다).
- **결과:** 개인 카드의 효과가 모두 기록이 됐다 — Agent 칸 103, Reveal 선택 26, Reveal 자동 이득 카드 51, 획득 12·폐기 4·버림 2,
  Reveal 획득 1, 차례 시작 1. hook은 Agent 칸 20, Reveal 선택 10, 기타 2.

### A5에서 만든 것 (2026-10-16, codec 그대로 v148)

조사(git 무시 `tmp/claude/4767ed6a/a5/a5-survey.md`: 보드 칸 23개, Conflict 19장 57줄, 계약 28장의 흐름·사건·위험, 2,000판 탐침과
비교용 결과 파일·수마다 추적판)를 따랐다.

- **같음 확인 도구 보강(먼저):** `engine_equivalence.py`가 수마다 플레이 서버가 결정과 함께 보내는 것 — 회색 행과 이유
  (`display.unavailable`), Agent 칸·Reveal 선택 묶음과 행의 주인(`display.actions`), Scouts 줄 — 과 Reveal 대기 선택마다의 행
  (`pending_choice_entries`, 앱 AI가 읽음)도 비교한다(`page`). A4d의 첫 판 결함(대기 선택 안의 행 중복)을 일부러 넣으면 잡고, 그대로인
  엔진에서는 헛차이를 내지 않는다. 기준 기록은 `bdef8c76`로 다시 만들었다(옛 기록과 수 하나까지 같음). 6절 "빈틈"은 이것으로 닫혔다.
- **A5a — 계약 28장:** `content/uprising/contract_abilities.py`(타일 id별, 둘째 복사본은 첫째 것을 공유). `requirement`가 완수 조건 —
  칸 방문(`AtBoardSpace`, 배치 때의 기록으로 판정), Maker 칸 방문 + 그 차례 스파이스(`AtMakerSpace`+`GainedSpiceThisTurn`), 카드
  획득(`AcquiredCard`), 가져옴(`ContractTaken`; Bloodlines Immediate는 비용 `TrashIntrigueCard`), 동맹 얻음(`AllianceTaken`) — 이고
  줄이 보상이다. `contracts.py`가 기록을 `ContractCondition`·`ContractReward`로 옮기므로 완수 경로 여섯과 보상 처리는 그대로다.
- **A5b — Conflict 보상 57줄:** `content/uprising/conflict_abilities.py`(카드 id별 세 줄). 첫 줄이 주는 것, 선택 화살표("3 spice →
  1 VP")는 한 줄씩. `conflicts.py`가 `ConflictReward`로 옮기므로 지급 순서(종류별, OQ-002·OQ-102)와 frame은 그대로다. DSL 보상
  `TakeControl`.
- **A5c — 보드 칸 인쇄 아이콘:** `content/uprising/board_abilities.py`(칸 × 비용 선택지 × 변형: CHOAM 없음, Immortality 덧판, 원로회 착석).
  `static_board_effects`와 원로회 재방문이 기록의 이득을 읽는다(원로회 자리·Swordmaster·계약은 자기 아이콘 키). 829가지 조합 모두
  옮기기 전과 같다. DSL 보상 `TakeSwordmaster`, 시점 `BOARD_SPACE`·`CONTRACT`·`CONFLICT_REWARD`.
- **A5d — 보드 선택 아이콘과 특수 흐름:** Espionage의 Spy, Desert Tactics의 폐기, Shipping의 영향력, Imperial Privilege의 책략
  맞바꿈과 소환, Sietch Tabr, Maker 칸 셋, Tuek's Sietch, Secrets의 훔치기를 (칸, 아이콘 키)별 hook 기록으로
  (`board_effects.BOARD_SPACE_HOOKS`, 표시는 `OPTIONAL_BOARD_ICONS`와 같음). 앞의 다섯은 행이 공통 모양과 같지만 사건 이름이 처리
  코드마다 달라, 공통 모양으로 합치는 일은 사건을 통일하는 정리 단계로 넘긴다(조사의 A5d 제안과 다름 — 카드별 예외를 단 공통
  모양은 만들지 않는다는 판단).
- **옮기지 않은 것(판단):** 칸에 인쇄되지 않은 방문 규칙(진영 영향력, 장악 보너스, Gather Intelligence, 계약 기록, Esmar의 방문,
  Maker 보너스 스파이스, 장악 방어)과 계약 시장 기계(가져오기·채우기·보류·재개·소멸·Shaddam)는 게임 규칙이라 엔진 코드로 둔다.
  보드 칸에서 Bloodlines 지휘관을 받는 제안은 A6(Bloodlines·Tech)에서.
- **결과:** 보드·Conflict·계약의 인쇄 효과가 모두 기록이다. hook은 Agent 칸 20 + Reveal 선택 10 + 기타 2 + 보드 9 = 41.

### A6에서 만든 것 (2026-10-17, codec 그대로 v148)

조사(git 무시 `tmp/claude/4767ed6a/a6/a6-survey.md`: 지도자 18명 19면의 능력 38개와 설정 10개, Tech 타일 18장, 지휘관 제안; 2,000판
탐침과 비교용 결과 파일, 수마다 추적판, 시나리오 7개)를 따랐다. 같음 확인 기준 기록은 시작 master `0c58e583`로 다시 만들었다.

- **A6a — Tech 획득 효과:** `content/bloodlines/tech_abilities.py` `TECH_ACQUIRE_ABILITIES`(타일 id별, 아이콘마다 한 줄; Gene-Locked
  Vault는 —OR— 두 줄). `content/bloodlines/tech.py`가 기록을 `TechTile`의 `acquire_*` 칸으로 옮기므로(엄격한 옮김: 두 번 인쇄·담을 칸
  없는 조각이면 멈춤) 획득 처리와 망 특성 digest는 그대로다. Advanced Data Analysis의 "획득하려면 Spy 하나를 폐기" 전제는 hook 기록.
  DSL 보상 `UseSignetAbility`.
- **A6b — Tech 능력:** `TECH_ABILITIES`(타일 id별). 뒤집기 셋은 `rules/tech.py`가 기록에서 행·해결을 읽고(Rapid Dropships의
  "Agent Turn"은 기록의 요건 `DuringAgentTurn`), 자동 Reveal 줄 셋(Command 둘, Self-Destroying Messages)은 `tech.TECH_REVEAL_GAINS`로
  옮겨 Reveal이 읽으며, Endgame 줄 둘(CHOAM Transports·Panopticon, OQ-040)은 Endgame 처리가 읽는다. 흐름이 남는 넷(Forbidden
  Weapons, Panopticon의 Reveal, Plasteel Blades, Suspensor Suits)은 hook. 갖고 있는 동안 규칙을 바꾸는 여섯(Gene-Locked Vault,
  Glowglobes, Navigation Chamber, Ornithopter Fleet, Sardaukar High Command, Servo-Receivers)은 새 시점 `STANDING` 기록(줄 없이 엔진
  분기 이름). 새 시점 `FLIP`·`STANDING`, 보상 `GainInfluenceWhereAtMost`.
- **A6c — 인장 18개:** `content/uprising/leader_abilities.py` `SIGNET_ABILITIES`(지도자 면별; Y'rkoon은 인장 없음). 고를 것이 없는
  넷(Warmaster, Lead the Way, Harkonnen Advisor, Judge of the Change)과 Servo-Receivers로 쓰는 Fill Coffers는 한 모양
  (`_resolve_automatic_signet`)이 두 곳(인장 반지 칸, Servo 칸) 모두에서 기록으로 해결한다 — 사건 하나에 줄마다의 값(조건이 안 맞으면
  0). Fill Coffers의 인장 반지 칸 아이콘(OQ-027·OQ-028), Spice Agony·Water of Life의 지불, Arrakis Informant의 관측소는 기록에서 읽고,
  선택 표시도 기록에서(단계마다 바뀌는 넷 — Unseen Network, Corrino Liaison, Listeners, Personal Training — 은 단계 키가 정함).
  나머지 열은 hook(`SIGNET_HOOKS`). 조건 `VisitedSpaceHasIcon`, 보상 `RecruitUndeployableTroops`·`TroopToMemory`.
- **A6e — 지도자 왼쪽 칸 21개:** `LEADER_ABILITIES`(면별). 보상이 정해진 유발 여덟(Loyalty, Imperial Birthright, Staban의 Smuggle
  Spice, Esmar의 방문 둘, Assassin, Twisted Genius의 라운드 시작 뽑기, Hungry for Spice)은 새 유발 조각(`OnReachInfluence`,
  `OnOpponentAgentAtSpiedMakerSpace`, `OnCardTrashed`, `OnAgentSentTo`, `OnRoundStart`, `OnSpiceGainedInTurnAtLeast`)과 보상 줄로
  적고, **유발 자리는 그대로 두고 그 자리에서 기록의 보상을 읽는다**(한 곳에서 돌리면 공용 처리 안의 사건 순서가 바뀐다: Assassin은
  `card_trashed` 바로 뒤, 도달 보너스는 한 번의 얻기 안에서 단계마다). 자동 Reveal 줄 둘(Always Smiling: `StrengthInConflictAtLeast`,
  Unpredictable Foe)도 데이터. 흐름 여섯(Devious Strength, Desert Scouts, Other Memories, Reverend Mother, Tactician, Plot Course)은
  hook(`LEADER_HOOKS`), 규칙 변경 다섯(Shaddam의 따로 둔 계약, Ginaz Swordmaster, Clandestine, Arrakis Planetologist, Secret
  Project)은 `STANDING`. 같은 방식으로 CHOAM Transports·Planetary Array의 뽑기도 유발 기록(`OnContractCompleted`, `OnConflictWon`)이
  됐다. 보류·미룬 뽑기 기계는 한 장씩이라 기록의 뽑기 수가 1인지 불러올 때 확인한다. 보상 `DrawTwistedIntrigueCards`.
- **옮기지 않은 것(판단):** 설정 차이 10개(시작 물, 시작 카드 제외, 전술 토큰 칸, 앞면, Feyd 토큰, Twisted 덱 등)는
  `LeaderDefinition` 칸 그대로(칸을 더하면 망 특성 digest가 바뀐다). Feyd의 훈련 트랙 칸 보상(`FeydTrackReward`)도 트랙 자료로 둔다.
  보드 칸에서 지휘관을 받는 제안은 칸에 인쇄된 효과가 아니라 모듈이 칸에 놓은 지휘관의 규칙이라, A5가 방문 규칙을 엔진 코드로 둔
  판단과 같이 엔진 코드로 둔다(A5의 "A6에서"를 이것으로 닫음). Sardaukar 기술 타일 7개(`SkillDefinition`)는 표의 어느 단계에도 없다
  — 어디서 할지 사용자 결정 필요(2026-10-17 결정: A7a로 옮김, 아래 "A7에서 만든 것").
- **결과:** Tech와 지도자의 인쇄 능력이 모두 기록이다(규칙 변경은 이름만 적은 `STANDING` 기록 11개). hook은 A5까지 41 + Tech 5 +
  인장 10 + 지도자 6 = 62.

### A7에서 만든 것 (2026-10-17, codec 그대로 v148)

조사(git 무시 `tmp/claude/4767ed6a/a7/a7-survey.md`: 기술 타일 7개, 연구 칸 22개·Tleilaxu 트랙 8칸·Reclaimed Forces·Tleilaxu 카드 18장,
접합·표본·Family Atomics, Scouts 항목 77개; 2,000판 탐침·추적판·시나리오)를 따랐다. 기준 기록은 시작 master `9234a14a`로 다시
만들었다(옛 기록과 수 하나까지 같음).

- **A7a — Sardaukar 기술 타일 7개(사용자 결정 2026-10-17):** `content/bloodlines/skill_abilities.py`(기술 id별). Reveal 줄 넷
  (Charismatic, Driven, Hardy, Desperate의 "이 타일 폐기 → 칼 3")과 전투력 줄(Canny, Fierce 둘, Loyal; 새 시점 `IN_CONFLICT` —
  지휘관이 교전에 있는 동안)을 `content/bloodlines/sardaukar.py`가 `SkillDefinition` 칸(종류 포함)으로 옮긴다. 조건
  `AgentOnSpaceWithIcon`·`OpponentSandwormInConflict`, Desperate의 비용은 기존 `TrashCard(this_card=True)`.
- **A7c — Immortality 트랙 보너스와 Reclaimed Forces:** `content/immortality/track_abilities.py`. 연구 칸 21개의 보너스(칸 id별)와
  Tleilaxu 트랙 4칸의 보상을 `ResearchSpace.bonus`·`TLEILAXU_TRACK`으로, Reclaimed Forces의 두 선택을 선택지와 수(병력 2,
  Tleilaxu 1)로 옮긴다 — `rules/tleilaxu_row.py`가 옮긴 값을 읽고, 해결 순서(표본이 폐기보다, 책략이 카드보다 먼저)는 처리 코드
  그대로. 새 시점 `TRACK_SPACE`, 보상 `TakeSetupSpice`(넷째 칸의 첫 도달 스파이스).
- **A7d — Immortality의 인쇄된 규칙 변경 넷:** Ghola의 같은 Agent 칸, Usurp의 Row 접합, Tleilaxu Infiltrator의 "적 Agent가 막지 않음",
  Family Atomics를 `content/immortality/rule_abilities.py`의 `STANDING` 기록으로(엔진 분기 이름).
- **A7b — Arrakeen Scouts 77개:** `content/arrakeen_scouts/abilities.py`(항목 id별, 새 시점 `SCOUTS`). 위원회 14, 고르기·공유·비밀
  이벤트, 판매 4, 봉인 경매 8의 줄 75개를 내용 표에서 글자 그대로 옮겼고(AST로 옮긴 뒤 77개 항목의 repr이 같음), 내용 표가 기록을
  `ScoutsOption`·`rank_rewards`로 다시 옮긴다 — Scouts 단계와 줄 실행기(`SCOUTS_EFFECT`)는 그대로. 미션 16, 자동 이벤트 4, 라운드
  효과 4, Mercenaries, Critical Moment 둘은 모듈의 장치라 줄 없는 hook 기록(이름만)이고, Rebuild Infrastructure는 자원자가 내는 줄과
  hook을 함께 적었다. CHOAM Escort의 두 선택, 참가 비용 셋(Prison Planet, Fedaykin Assistance, Weirding Warfare), Political
  Equilibrium의 좌석별 줄은 그 장치의 자료로 미션 표·규칙 코드에 남는다(판단: 장치와 떼어 적으면 반쪽 기록이 된다). Scouts 전용 조각 9개는 효과 DSL로 옮기고(`content.arrakeen_scouts.types`가 그대로 다시 내보냄) `Cost`·`Reward`에
  넣었으며(손패 폐기는 비용 쪽에도), `EffectSection`은 무언가를 잃기만 하는 줄(Crackdown)을 받는다 — 이 셋(전용 조각, 비용 쪽 손패 폐기, 잃기만 하는 줄)은 `SCOUTS` 기록에만
  허용한다(`Ability`가 확인). 문구는 `display/scouts.py`의 것을
  옮겼다.
- **옮기지 않은 것(판단, 조사의 A7e):** 표본(만들기·쓰기·되돌리기 창), 접합 기계, Tleilaxu Row 상점·채우기·덱 위, 유전 표지 규칙,
  연구 이동·창, Tleilaxu 루프·끝·보류 뽑기, Scouts의 일정·뽑기·경매 기계는 게임 규칙이라 엔진 코드로 둔다(A5의 방문 규칙, A6의
  지휘관 제안과 같은 판단). Tleilaxu 카드 18장의 효과와 Research Station 덧판은 A2~A5에서 이미 기록이다.
- **결과: A단계 옮기기가 끝났다.** 모든 카드·타일·보드·트랙·모듈 항목의 인쇄 효과가 기록이다(규칙 변경은 이름만 적은 `STANDING`
  기록 15개, 모듈 장치는 줄 없는 hook 기록). hook은 A6까지 62 + Scouts 28 = 90.

### 정리 단계 — 물려받은 차이 통일 (A단계 옮기기 뒤, A8과 함께; 사용자 결정 2026-10-16)

A단계는 "옛 엔진과 같음"(6절)을 관문으로 삼아, 옛 코드가 칸마다 따로 짜면서 생긴 차이까지 그대로 옮긴다. 이 차이는 규칙이 아니라
코드의 우연이고, 특수 처리(hook, 처리기별 출처)를 남긴다. 사용자 질문("엥간하면 공통으로 통일하는게 좋지 않을까")에 대한 결정: 통일한다.
다만 옮기기와 섞으면 의도한 차이와 실수를 가려낼 수 없으므로, 모든 효과를 옮긴 뒤 한 번에 한다.

- **통일할 것(A3까지 찾은 것):**
  - 사건 이름(출처): 폐기 `round:R:player:P:agent_card`(카드 없음), 버리기 `…:agent_card_discard`, 지불 `…:agent_card_payment`, 책략 폐기
    `…:agent_card:<카드>:intrigue_payment`, Control the Spice의 `…:agent_card_payment:<카드>:paid`(병력 수를 실음), 카드 정의 이름의 뽑기
    (`…:agent_card:<정의>`) 대 칸 이름의 뽑기(`<칸>:cards`) 등.
  - "칸 해결" 사건(`agent_card_effect_resolved`): 어떤 답은 내고 어떤 답은 내지 않는다.
  - Spy 넘기기 줄의 자리: 책략은 소환 줄들 뒤, Agent 칸은 앞(아래 "예외"의 확인 결과 (1)).
  - 시험 해결(`resolve_agent_card_effect`의 답): 선택 칸에 따라 예외(가능으로 읽힘), "해결 불가" 사건, 다른 예외가 섞여 있다.
  - hook 20개(Seek Allies, Overthrow, Lisan al Gaib, Clandestine Meeting, Occupation, In High Places, Control the Spice, Possible Futures,
    그리고 A3g의 12개): 사건이 공통 규칙에 맞게 되면 공통 모양으로. 조사 G1~G7의 묶음이 출발점이다 — Subversive Advisor·Treacherous
    Maneuver(방문 진영 영향력이 칸의 1을 대신), Dissecting Kit·Beguiling Pheromones(접합 카드 폐기 모양 하나), Long Reach·Stitched
    Horror("서로 다른 k개" 고르기, 4.1), Corrinth City·Arrakis Revolt·Slig Farmer(지불 모양의 변형). 효과 이름으로 고르는 hook의
    제공자·처리기 코드도 함께 없앤다.
  - Reveal 처리 코드는 기록을 옮긴 `PersonalCardRevealEffect`를 읽는다(A4c). 기록을 직접 읽게 하면 그 옮김이 없어진다. 공유 조각
    `TakeContract`의 문구는 "Take 1 Contract"인데 카드는 "face-up"을 인쇄한다(A4a 테스트에 예외로 적음).
  - Reveal 선택의 frame 닫는 순서: 고른 진영 영향력은 얻은 뒤, CHOAM Demands·폐기·Spy 소환은 닫은 뒤 보상(A4d). 계약 줄이 있는
    선택은 CHOAM에서만 열린다는 판정(Delivery Logistics, A4f)은 인쇄 조건이 아니라 모듈 판정이다.
  - Reveal 선택 hook 10개와 기타 hook 2개(A4d, A4h).
  - 보드·Conflict·계약의 사건(A5 조사 G.4): 보드 사건 id에 아이콘 키가 붙기도 안 붙기도, Imperial Privilege 맞바꿈은 보드 사건
    없음, 계약 완수 사건 모양 셋·출처 다섯, Conflict 보상의 책략 카드는 뽑기 사건 없이 줌, 영향력 사건이 보상 사건 앞(Conflict)과 뒤
    (계약), 폐기 보상 frame은 낼 카드가 없으면 확인 없이 건너뜀, Shipping은 모든 큐브가 6이어도 네 진영을 냄(Agent 칸 영향력은
    기다림), 지운 거절 행동의 codec 템플릿 둘. 보드 hook 9개(A5d) 중 행이 공통 모양과 같은 다섯(Espionage의 Spy, Desert Tactics의
    폐기, Shipping의 영향력, Imperial Privilege의 맞바꿈과 소환)은 사건 통일 뒤 공통 모양으로. 계약·Conflict·보드 표는 기록을 옮긴
    `ContractCondition`·`ContractReward`·`ConflictReward`·`static_board_effects`를 읽는다(A4c의 Reveal과 같음).
  - 지도자·Tech(A6 조사 G.4): 인장 사건의 `card_id`가 자동 인장에만 있음, 해결 사건이 뽑기·영향력 사건보다 앞(Lead the Way,
    Fedaykin, Kota, Shaddam)인데 지불 사건보다는 뒤(Spice Agony, Staban), Fill Coffers는 칸에 따라 사건 모양 둘, Staban의 유발 사건
    id는 주인을·Esmar는 방문자를 이름, Assassin·Tactician 사건 id에 유발한 효과의 출처가 붙음, 주지 않는 거절 행동 셋
    (`decline_other_memories`, `decline_leader_board_repeat`, `decline_sardaukar_commander`, codec·옛 기보 다리에 남음), 의무 단계에 "막히지
    않게" 남긴 거절, 닿지 않는 `acquire_leader_reserve`(비용 1인 Reserve 더미 없음)와 Esmar의 거절만 있는 인장. Tech 획득·Reveal은
    기록을 옮긴 `TechTile`·`TECH_REVEAL_GAINS`를 읽는다(A4c와 같음).
  - 기술 타일·Immortality·Scouts(A7 조사 G.4-6): 연구 이동 사건 id가 부른 곳마다 다름(`…:research:<칸>` / `…:research:#:research:<칸>`
    / `…:acquisition_bonus:research:<칸>`), Scouts 줄과 책략 보상의 자원 얻기는 사건이 없는데 연구 보너스·획득 보너스는 있음,
    Tleilaxu VP·스파이스가 `tleilaxu_advanced`의 payload(따로 `victory_points_gained` 없음), Family Atomics와 Clear the Market은 같은
    효과에 다른 사건, `skill_reveal_bonus`가 0인 양도 실음, 연구 창은 차례 안에서도 거절을 따로 냄(OQ-095 (2)와 다름),
    `scouts_choice_skipped`는 결정 없는 사건, 연구 보너스 셋의 해결 순서가 인쇄 순서와 다름, `scm._PARKING`이
    `Mission.parked_troops/troop_source`를 되풀이, Scouts의 `PaySpecimens`가 DSL `SpendSpecimens`와, 비용 쪽
    `TrashPersonalCard(hand_only=True, mandatory=True)`가 `TrashCard(hand_only=True)`와 같은 일(합칠 후보), 고르기 이벤트의 거절 가능
    여부가 `ScoutsEvent.passable`과 기록의 표시 두 곳(테스트가 맞춤), Scouts 장치
    hook 이름(`scouts_<항목>`)은 엔진의 등록부가 아니라 항목 id.
  - A3g~A7에서 찾는 같은 종류의 차이도 이 목록에 더한다.
- **방법:**
  1. 차이 목록을 만들고 종류마다 규칙 하나를 정한다(예: 사건 이름 `<칸>:<무엇>`, 칸이 끝나면 언제나 "칸 해결" 사건 하나).
  2. 한 번에 바꾼다.
  3. 같음 확인을 "정해진 차이 목록"과 함께 돌린다: 도구가 옛 사건 이름·모양을 새 것으로 옮겨 놓고 비교해, 목록에 없는 차이는
     여전히 잡는다.
  4. codec을 올리고 기보 다리(records)를 더한다(옛 저장·기보 묶음이 새 엔진으로 옮겨지게). 화면(로그·연출이 읽는 사건)과 E2E도 함께
     맞춘다. A8(망 재학습, 플레이 서버 교체)과 같은 때에 해서 저장 호환을 한 번만 끊는다.
- **예외 — 규칙 차이는 기다리지 않는다:** 겉으로 드러나는 규칙 구현 차이는 이름 문제가 아니라 같은 규칙의 두 구현일 수 있어, 규칙
  문서와 대조해 따로 먼저 정한다.
  - 확인함(2026-10-16): Agent 칸 Spy(`agent_box_abilities.agent_spy_rows`)와 책략 Spy(`ability_executor.piece_rows`의 `PlaceSpy`)의
    차이 셋은 규칙 위반이 아니다. 둘 다 "공급에 Spy가 있고 놓을 칸이 있으면 배치 의무"(OQ-057 (14), [uprising-systems.md](rules/uprising-systems.md)
    "Spy 배치는 supply에 Spy가 하나라도 있으면 의무다"), "공급이 비면 먼저 소환은 선택" `[Main pp. 11, 20]`, "놓을 칸이 없으면 Spy 없이
    해결"을 지킨다. (1) 넘기기 줄의 자리: 책략은 소환 줄들 뒤, Agent 칸은 앞 — 보여 주는 순서뿐이라 위 통일 목록에 넣는다. (2) 아무것도
    할 수 없을 때: 책략은 넘기기 줄 하나(쌓인 frame이라 지금 답해야 한다), Agent 칸은 줄 없이 기다렸다가 턴 끝에 무산(OQ-057 (1) — 자유
    순서라 그 사이 칸이 생길 수 있다) — 두 맥락의 사용자 판정이 다른 것으로 둘 다 유지. (3) 먼저 소환한 Spy를 Espionage가 써 버리면
    Agent 칸은 넘기기 없이 다시 소환해 놓아야 한다 — OQ-057 (14)에 적힌 판정(책략 frame에는 이런 끼어듦이 없다).

### B단계 — 행동 이름·단위 교체 (선택, A단계 뒤에 정한다)

- 내용: 행동을 `동사(대상, slot=k)`로 바꾸고 묶인 행동을 조각 행동으로 나눈다. `slot`은 대기 능력 목록의 자리다(지금
  접합 차례의 `box=1`을 일반화). 엔진 밖 약 5,300곳을 함께 옮긴다.
- 정하는 기준: A8 뒤 확장 하나를 빼고 학습한 망이 그 확장에 얼마나 빨리 적응하는지(entity-network-plan.md의 남은
  실험)를 행동 특성 표만으로 잰다. 충분하면 B단계는 하지 않는다. 모자라면 그때 8절의 두 질문과 함께 정한다.

### C단계 — 새 내용

Rise of Ix, 기본판 Imperium, Conspiracy 카드를 능력 기록으로 더한다.

## 6. 같음을 확인하는 법 (A단계 관문)

1. `scripts/ab/engine_equivalence.py`: 단계를 시작한 master(`git archive`로 푼 옛 소스)에서 200판(무작위 120, 휴리스틱
   40, 앱 AI·휴리스틱·무작위 섞음 40; 전 옵션·Immortality·CHOAM·기본)을 두어 기록하고, 단계 브랜치에서 같은 수순을
   다시 두어 **매 단계** 비교한다: chance 결정, 결정 주인과 합법 행동(순서까지), 네 좌석의 `PlayerView`, 사건(내용·공개
   범위까지), 결정 stack을 뺀 상태. **200판 모두 same**이어야 한다. 출력의 행동 id별 횟수로 그 단계의 효과가 실제로
   불렸는지 본다(2026-10-14 시험: 20판에 229종; 합법 행동 순서·사건 내용을 바꾼 변이는 잡고, frame id만 바꾼 변이는
   통과).
2. 기보 corpus(`scripts/records/corpus_generate.py --standard`, AI 판 2,000개)를 단계 시작 master로 만들어
   `dune-imperium-records corpus check`가 2,000판 모두 exact인지 본다.
3. 결정 stack의 모양이 바뀐 단계는 저장본의 상태 hash가 달라지므로 `ACTION_CODEC_VERSION`만 올린다(행동 template은
   그대로라 망은 그대로 쓰이고, 옛 저장본은 버전 검사에서 거절된다. 지금까지의 codec 올림과 같다).
4. 기존 테스트의 기대값은 바꾸지 않는다. 기대값을 바꿔야 한다면 동작이 바뀐 것이므로 멈추고 원인을 본다. 테스트를
   옮기거나 새 단위 테스트를 더하는 것은 된다.
5. pytest·ruff·mypy, `scripts/e2e/run_all.py`, 소크(soundness·privacy).
6. 속도: `scripts/ab/profile_legal.py`로 합법 행동 계산 시간을 단계 전후에 잰다. 10% 넘게 느려지면 병합 전에 고친다
   (탐색 좌석이 매 결정 이것을 수천 번 부른다). `profile_legal.py`는 기본 룰셋 10판이라 옮긴 효과가 거의 안 나오므로, 1번의 기록을 다시
   두며 `legal_actions`만 재는 `scripts/ab/time_legal.py`(전체와 옮긴 frame만 따로, 시작 master와 번갈아)도 돌린다(A1부터).

A0 관문(2026-10-15, 시작 master `8dcf302d`): 1번 200판 모두 same(191,836단계, 행동 241종 재생). 2번 v147 묶음
(`local/records-corpus/v147-2af1d9f5`, 2,000판) 모두 exact(시작 master보다 앞선 `2af1d9f5`로 만든 묶음이고, 그 사이 엔진 변경은 선택 불가 표시 첫 묶음뿐). 3번 codec 그대로(v147, 결정 stack 그대로). 4번 기존 기대값
바꾼 것 없음(옮긴 도우미의 import 한 줄만). 5번 pytest·ruff·mypy 통과. E2E·소크·6번 속도는 건너뛰었다: A0는 엔진에
연결하지 않았고 바뀐 실행 경로는 옮긴 도우미 하나라, 1번의 매 단계 비교가 그보다 강한 증거다. A1부터는 모두 돈다.

A1 관문(2026-10-16, 시작 master `259e8ee8`, 리뷰 반영 뒤 최종 코드로): 1번 200판 모두 same(191,836단계, 행동 241종). 같은 200판을 브랜치에서
에이전트가 다시 두어도 기록과 수 하나까지 같다(앱 AI가 frame을 읽는 곳이 바뀌어 더 돌렸다). 2번 v147 묶음(`v147-2af1d9f5`) 2,000판 모두
exact, 다리 0(로컬 사람 저장본 9판도 두 엔진에서 같은 결과). 브랜치로 만든 v148 묶음(`v148-02e203ce`)도 v147 묶음과 2,000판 모두 수순이
같다. 3번 codec v148. 4번 기존 기대값 바꾼 것 없음(codec 번호 고정, frame 키 목록,
frame 키를 직접 읽던 테스트 둘의 읽는 법, 옮긴 도우미의 import 경로만). 5번 pytest 7,738개·ruff·mypy 통과, E2E 67종 통과, 소크 360판 실패 0.
6번 `time_legal.py` 100판 번갈아 세 번씩: 전체 호출당 48.3–48.9 µs(시작) 대 48.5 µs, 책략 frame 12.9–13.0 µs 대 12.4–12.6 µs;
`profile_legal.py` 잡음 안. 독립 리뷰: 막는 문제 없음, 지적 7개 고침(worklog 2026-10-16).

A2 관문(2026-10-16, 시작 master `7ba624ad`): 1번 200판 모두 same(191,836단계; 옛 분기를 지우기 전과 뒤 두 번). 200판에서 기록 칸 43개가
해결됐고 안 나온 Pointing the Way는 단위 테스트로 지킨다. 같은 200판을 브랜치에서 에이전트가 다시 두어도 수 하나까지 같다. 2번 v148 묶음
(`v148-02e203ce`) 2,000판 모두 exact. 3번 codec 그대로 v148(결정 stack 꼴 그대로). 4번 기존 기대값 바꾼 것 없음. 5번 pytest 7,747개·ruff·mypy
통과, E2E 67종 통과, 소크 720판 실패 0. 6번 `time_legal.py` Agent frame 호출당 1~2% 느림(관문 10% 안). 독립 리뷰: 막는 문제·중간 없음. 옛·새 엔진 차등 탐침 330판(Agent 효과 상태 172,999곳에서 합법 행동·사건·상태·네 좌석 보기와 모든 효과×키의
막힘 이유·대기 판정까지)과 강제 탐침 2,665곳이 모두 같았다. 낮은 지적 3개(아이콘 조건이 막힘 이유를 늘 낼 것, 두 곳에 복사된 조건 판정,
화면 비교 범위)와 사소한 지적들을 반영했다(worklog 2026-10-16 A2).

A7 관문(2026-10-17, 시작 master `9234a14a`로 기준 기록을 다시 만듦): 1번 200판 모두 same — `page`까지(A7a·A7c·A7b 뒤, 리뷰
반영 뒤). 에이전트 재기록 같음. A7 조사 탐침 2,000판 결과 파일이 시작 master와 바이트 단위로 같음(하위 단계마다; A7a는 A6 탐침도
같음), 조사 시나리오 같음. 기술 타일·연구 칸·Tleilaxu 트랙·Reclaimed Forces·Scouts 77개의 repr, 망 특성 digest 같음. 2번 v148·v147
묶음 각 2,000판 exact. 3번 codec 그대로. 4번 기존 기대값 그대로. 5번 pytest 7,865개·ruff·mypy, E2E 67종, 소크 720판 실패 0.
6번 호출당 합법 행동 50.0→49.7µs(중앙값 셋), Agent frame 65.9→65.6µs — 잡음 안. 독립 리뷰: 막는 문제·중간 없음 — 카탈로그, 코덱 11개 설정, 관측 표, 기술 타일·Scouts·Immortality 문구 두 언어, 망 특성 digest가 같고, 앱 AI 좌석으로 직접 둔 300판(26만여 단계)이 같았다. 낮은 지적 다섯(전용 조각·잃기만 하는 줄이 모든 기록에 열림, 옮기는 함수가 hook·구조를 안 봄, 미션 줄 범위, 거절 가능 여부 두 곳, 사소한 문구) 반영 — 이제 Scouts 전용 것은 `SCOUTS` 기록에만 허용하고 옮기는 함수가 모르는 모양을 거부.

A6 관문(2026-10-17, 시작 master `0c58e583`로 기준 기록을 다시 만듦): 1번 200판 모두 same — `page`까지(A6a·A6b 뒤, A6c 뒤, A6e 뒤,
리뷰 반영 뒤). 에이전트 재기록 같음. A6 조사 탐침 2,000판 결과 파일이 시작 master와 바이트 단위로 같음(하위 단계마다), 조사 시나리오
7개 같음. Tech 타일 18장의 repr·획득 키, 망 특성 digest 같음. 2번 v148·v147 묶음 각 2,000판 exact. 3번 codec 그대로. 4번 기존 기대값
그대로. 5번 pytest 7,837개·ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 호출당 합법 행동 50.5→50.0µs(중앙값 셋), Agent frame 67.0→65.8µs — 잡음 안. 독립 리뷰: 막는 문제·중간 없음 — 카탈로그, 코덱 6개 설정, 지도자·Tech 문구 두 언어, 망 특성 digest가 같고, 300판 차등 탐침(앱 AI 좌석 포함, Servo 인장 284회·Jessica 뒤집기 133회 등 23만여 단계)과 Servo 시나리오 2,184개가 같았다. 낮은 지적 다섯(불러올 때의 검사가 처리 코드보다 느슨함 — 이제 처리 코드가 못 다루는 조건·보상·면·뒤집기 모양을 거부)과 한국어 기억 문구 반영. 전체 pytest가 새 테스트 파일 이름 겹침과, 로그의 EVENT_IMPLIED_LEADER 표가 기대하는 Smuggle Spice의 Staban 이름 빠짐을 잡아 고쳤다.

A5 관문(2026-10-16, 시작 master `bdef8c76`, 보강한 도구로 기준 기록을 다시 만듦): 1번 200판 모두 same — `page`까지(A5a·A5b 뒤,
A5c 뒤, A5d 뒤, 리뷰 반영 뒤). 에이전트 재기록 같음(두 번). A5 조사 탐침 2,000판 결과 파일이 시작 master와 바이트 단위로 같음(세 번),
조사 시나리오 5개 같음. 옮긴 표: 계약·Conflict 정의 75개의 repr, 보드 829가지 조합이 옮기기 전과 같음. 2번 v148·v147 묶음 각 2,000판
exact. 3번 codec 그대로. 4번 기존 기대값 그대로. 5번 pytest 7,793개·ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 호출당 합법 행동 49.5→50.7µs(중앙값 셋, 약 +2%), Agent frame 66.0→67.0µs — 잡음 안.
독립 리뷰: 막는 문제·중간 없음 — 망 특성 digest·관측 id 표·카탈로그·코덱 10개 설정·문구 599개가 같고, 150판 차등 탐침(행 문구까지)
12만여 단계가 같았으며, 도구의 `page` 비교가 실제 차이를 잡고 헛차이를 내지 않음을 확인. 낮은 지적(옮기는 함수가 표현 못 하는
기록을 조용히 넘김 — 이제 멈춤; 문서 인용 두 곳; 키 겹침)과 사소한 것들 반영.

A4d~A4h 관문(2026-10-16, 시작 master `3979c06a`, 같음 확인 기록은 `26b41eca` 것 그대로): 1번 200판 모두 same(여러 번: 1단계 뒤,
2단계 뒤, 결함 고친 뒤, A4e·A4f·A4h 뒤). 에이전트 재기록 같음. 조사 탐침 2,000판의 결과 파일이 시작 master와 바이트 단위로 같음(2단계
첫 판은 달라 결함을 찾음 — 위 "결함과 교훈"; 고친 뒤와 최종), 탐침 40판의 수마다 추적(합법 행동, 대기 선택의 행, 고른 행동, 사건 id)도
같음, 조사 시나리오 7개 같음. 2번 v148 묶음 2,000판 exact, 옛 기보를 옮기는 길로 v147 묶음 2,000판도 exact. 3번 codec 그대로. 4번 기존
기대값 그대로(옛 선택/의무 표 테스트를 기록 표시 테스트로 바꿈, 제공 함수 탐침 테스트에 같은 행 금지를 더함). 5번 pytest 7,785개·
ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 호출당 49.6~49.7 µs(시작) 대 49.8~50.1 µs — 잡음 안. 독립 리뷰: 막는 문제·중간 없음 — 옛·새 엔진 차등 탐침 300판 32만여 단계(대기 선택마다의 행, 화면의 선택 머리글·행 주인·회색 행까지)와 열림 판정 약 5,700만 번 호출, 옛 기보 v141·v143·v145 각 2,000판 옮김이 모두 같았다. 낮은 지적 1개(모양 판정이 처리하지 못하는 조각까지 받아들임 — 받는 조각을 좁힘)와 사소한 것들(같은 이름 함수, Agent 칸 폐기 모양의 새 필드)을 반영했다.

**빈틈(2026-10-16, A5 시작 때 닫음 — 도구가 `page`를 비교):** `engine_equivalence.py`는 합법 행동(합친 목록)을 비교하고 Reveal 대기 선택마다의 행은 비교하지 않는다. 그 목록은
화면과 앱 AI가 읽으므로, 다음 단계부터 도구에 넣을 일이다(시작 master로 기록을 다시 만들어야 한다). 그때까지는 조사 탐침의 칸별 행
비교를 관문에 넣는다.

A4a·A4c 관문(2026-10-16, 시작 master `26b41eca`, 같음 확인 기록을 이 master로 다시 만듦 — 옛 기록과 수 하나까지 같음): 1번 200판
모두 same(네 번: A4a 뒤, A4c 뒤, 리뷰 반영 뒤 등). 에이전트 재기록 같음. 조사 탐침 2,000판(카드를 손·줄에 넣어 모든 멤버를 봄)의 결과
파일이 시작 master와 바이트 단위로 같음(A4a 뒤, A4c 뒤), 조사 시나리오 7개도 같음. 2번 v148 묶음 2,000판 exact. 3번 codec 그대로.
4번 기존 기대값 그대로. 5번 pytest 7,781개·ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 호출당 49.3~49.9 µs(시작) 대 49.3~50.6 µs —
잡음 안. 독립 리뷰: 막는 문제·중간 없음(차등 탐침 292판 약 39만 단계 — 구매 경로 전부, 덱이 빈 Overthrow, 차례 밖, 은행이 빈
Sardaukar Standard, Fenring·Suspensor Suits, Scouts 시장 280갈래 — 와 카드 문구·카탈로그·코덱 4설정 출력, 모든 모듈 단독 import
모두 같음), 낮은 지적 1개(나중 기록의 조각이 조용히 무시될 수 있음 — 모양이 모르는 조각에서 멈추게)와 사소한 것들 반영.

A3g 관문(2026-10-16, 시작 master `45cf88e6`): 1번 200판 모두 same(세 번: 모양 3칸 뒤, hook 12칸 뒤, 리뷰 반영 뒤). 에이전트 재기록 같음. 2번 v148 묶음
2,000판 exact. 3번 codec 그대로. 4번 기존 기대값 그대로(기록 수 테스트만 88→103). 5번 pytest 7,774개·ruff·mypy, E2E 67종, 소크 720판 실패 0.
6번 Agent frame 호출당 65.3·63.7·64.7 µs(시작) 대 67.9·65.0·65.8 µs — 관문 안. 더해서 조사 탐침(15칸을 손에 넣고 Ghola·접합 짝까지)을 옛·새
엔진에서 1,000판씩 돌려 기록한 값 2,219종이 모두 같았다. 독립 리뷰: 막는 문제·중간 없음(차등 탐침 120판 — 상태 52,847곳, 적용한 행동
236,812번, 턴이 내지 않는 원래 행 10,455번 — 과 시나리오 75개 13,609곳, 조사 시나리오 22개 모두 같음; 일부러 넣은 변이 둘은 첫 30판에서 잡힘),
낮은 지적 1개(hook 기록에 칸의 일부만 적힌 줄 — 칸 전체를 말할 수 있을 때만 적게)와 사소한 것 3개 반영.

A3f-5 관문(2026-10-16, 시작 master `c28b8346`): 1번 200판 모두 same(두 번: 구현 뒤, 리뷰 반영과 A3f-4 받은 뒤). 에이전트 재기록 같음. 2번 v148 묶음 2,000판 exact. 3번 codec
그대로. 4번 기존 기대값 그대로(기록 수·아이콘 표 테스트만). 5번 pytest 7,770개·ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 A3f-3~5를 모두 쌓은
코드로 Agent frame 호출당 65.5~66.4 µs(시작) 대 66.5~67.8 µs — 관문 안. 독립 리뷰: 막는 문제·중간 없음(차등 탐침 200판 + 줄에 놓은 카드·
Usurp 100판, 상자 탐침 12,000여 곳, 사람 저장본 9개의 기보 옮김까지 모두 같음), 낮은 지적 2개(Twisted Mentat의 소환이 선택임을 기록에 —
`RecallAgent.optional`, 아이콘 순서 주석)와 사소한 것 반영.

A3f-4 관문(2026-10-16, 시작 master `b5ba7bfa`): 1번 200판 모두 same(두 번: 구현 뒤, 리뷰 반영과 A3f-3 받은 뒤). 에이전트 재기록 같음. 2번 v148 묶음 2,000판 exact. 3번 codec
그대로. 4번 기존 기대값 그대로(기록 수 테스트만). 5번 pytest 7,767개·ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 Agent frame 호출당 65.5~66.4 µs
(시작) 대 67.0~68.9 µs — 관문 안. 독립 리뷰: 막는 문제·중간 없음(차등 탐침 210판 — 고르기 영향력 636번, Combat 193번 — 과 만든 상황 206개
두 수 깊이 모두 같음), 낮은 지적 2개(고르는 줄에 조건이 있어야 "둘 중" 모양; 평범한 줄 행은 그 줄이 맞을 때만)와 사소한 것 반영.

A3f-3 관문(2026-10-16, 시작 master `925a814a`): 1번 200판 모두 same(두 번: 구현 뒤, 리뷰 반영 뒤). 에이전트 재기록 같음. 2번 v148 묶음 2,000판 exact. 3번 codec 그대로.
4번 기존 기대값 그대로(기록 수 테스트만). 5번 pytest 7,765개·ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 Agent frame 호출당 63.5·65.1 µs(시작) 대
65.6·65.8 µs — 관문 안. 독립 리뷰: 막는 문제·중간·낮은 지적 없음(차등 탐침 300판 268,141단계 — Piter 손실 695번, Control the Spice 지불
1,067번, Smuggler's Haven의 같은 지불 줄 포함 — 과 깊이 9까지의 탐색 159,386곳 모두 같음), 사소한 것 1개(죽은 별칭) 반영.

A3f-2 관문(2026-10-16, 시작 master `12732498`): 1번 200판 모두 same(두 번: 구현 뒤, 리뷰 반영 뒤). 에이전트 재기록 같음. 2번 v148 묶음 2,000판 exact. 3번 codec 그대로.
4번 기존 기대값 그대로(기록 수 테스트만). 5번 pytest 7,763개·ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 Agent frame 호출당 64.9·65.5 µs(시작) 대
65.3·66.4 µs — 관문 안. 독립 리뷰: 막는 문제·중간 없음(차등 탐침 150판 — Observer 버리기 1,962번, 길드 스파이스 119번, Spy 배치 2,108번 중
먼저 소환 뒤 766번 — 과 시나리오 2,626줄 모두 같음), 낮은 지적 1개(Spy 단계 한 번 해결의 테스트)와 사소한 것들 반영.

A3f-1 관문(2026-10-16, 시작 master `fa9a2b1d`): 1번 200판 모두 same(두 번: 구현 뒤, A3e 브랜치 받은 뒤). 에이전트 재기록 같음. 2번 v148 묶음 2,000판 exact. 3번 codec
그대로. 4번 기존 기대값 그대로(기록 수 테스트만). 5번 pytest 7,762개·ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 A3c~A3f-1을 모두 쌓은
코드로 Agent frame 호출당 67.2·68.3·67.0 µs(시작) 대 67.3·67.3·65.6 µs — 차이 없음. 독립 리뷰: 막는 문제·중간 없음(차등 탐침 230판
262,400단계 — 획득 4,196번, Tleilaxu Master 표지 0·1·2 상태 모두, Ghola 사본 포함 — 모두 같음; v141·v143·v147 기보 각 400판 대조도 옛
엔진과 같음; 모든 모듈 단독 import 확인), 낮은 지적 1개와 사소한 것들 반영(주석).

A3e 관문(2026-10-16, 시작 master `ffb1205e`): 1번 200판 모두 same(네 번: 폐기 칸 4개 뒤, Elite Forces 뒤, 리뷰 반영 뒤, A3d 브랜치 받은 뒤). 에이전트 재기록 같음.
2번 v148 묶음 2,000판 exact. 3번 codec 그대로. 4번 기존 기대값 그대로(기록 수 테스트만). 5번 pytest 7,761개·ruff·mypy, E2E 67종, 소크 720판
실패 0. 6번 Agent frame 호출당 93.9·94.6·95.5 µs(시작, 부하 중) 대 95.6·96.9·94.5 µs — 관문 안. 독립 리뷰: 막는 문제·중간 없음(차등 탐침 360판,
대상 상태 46,616곳 — Ruthless 두 폐기 사이 427, Elite Forces 황제 106·아닌 것 269, Usurp 사본 포함 — 모두 같음), 낮은 지적 2개(아이콘 하나짜리
검은 폐기는 세는 값을 건드리지 않게; 버리기·책략 모양은 모든 줄이 걸릴 때만)와 사소한 것 3개 반영.

A3d 관문(2026-10-16, 시작 master `70153b51`): 1번 200판 모두 same(다섯 번: 버리기 5칸 뒤, 7칸 뒤, 책략 2칸 뒤, A3c 받은 뒤 리뷰 반영 뒤 등). 에이전트 재기록 같음.
2번 v148 묶음 2,000판 exact. 3번 codec 그대로. 4번 기존 기대값 그대로(기록 수 테스트만). 5번 pytest 7,759개·ruff·mypy, E2E 67종, 소크 720판
실패 0. 6번 Agent frame 호출당 64.6 µs(시작) 대 65.1 µs(조용할 때), 부하 때 96.5 대 99.3 µs — 관문 안. 독립 리뷰: 막는 문제·중간 없음(차등
탐침 400판 두 번 — Junction 지불 844번·Branching Path 1,151번 포함 — 과 상황 탐침 221,744줄 모두 같음), 잠재적 낮은 지적 2개(걸린 아이콘
열쇠를 그 길이 받는 칸에만 — 테스트로; 책략 화살표의 동맹은 진영을 이름)와 사소한 것들 반영.

A3c 관문(2026-10-16, 시작 master `e3a0b618`): 1번 200판 모두 same(네 번: 영향력 2칸 뒤, 6칸 뒤, 최종, 리뷰 반영 뒤). 에이전트 재기록 같음. 2번 v148 묶음
2,000판 exact. 3번 codec 그대로. 4번 기존 기대값 그대로(기록 수 테스트만). 5번 pytest 7,756개·ruff·mypy, E2E 67종, 소크 720판 실패 0.
6번 Agent frame 호출당 64.6 µs(시작) 대 67.3 µs(조용할 때 한 번), 부하 때 96.5 대 97.6 µs — 관문 안. 독립 리뷰: 막는 문제·중간 없음(차등
탐침 300판, 상황 탐침 367,779줄, Arrakis Observer 75,562줄 모두 같음), 낮은 지적 2개(화면의 "영향력을 올릴 진영 없음" 판정이 기록을 읽게,
Deep Cover가 카드 진영 표시를 읽지 않는 이유 주석)와 사소한 것 1개 반영.

A3a·A3b 관문(2026-10-16, 시작 master `926b679d`): 1번 200판 모두 same(세 번). 에이전트 재기록 같음. 2번 v148 묶음 2,000판 exact. 3번 codec
그대로. 4번 기존 기대값 그대로(기록 수 테스트만). 5번 pytest 7,751개·ruff·mypy, E2E 67종, 소크 720판 실패 0. 6번 Agent frame 잡음 안. 독립 리뷰:
막는 문제 없음(차등 탐침 369판, 강제 탐침 188,220곳), 낮은 지적 1개 반영.

## 7. 플레이 유지

- 지금: 레시피 MLP가 플레이 서버 망이다. 확인 측정(400판, X와 비교)이 끝나면 결과를 worklog에 적는다.
- A단계: 병합마다 master가 그대로 플레이된다(망·행동·관측 그대로; 결정 stack 모양이 바뀐 단계만 옛 저장본이
  거절된다, 6절 3번).
- A8: 새 망은 관문을 넘은 뒤에만 플레이 서버에 올린다.
- 다른 세션의 엔진 수정: A단계 동안 규칙 수정이 master에 들어오면 다음 단계 브랜치가 그것을 받아 실행기로 옮긴다.
  같음 확인의 기록은 단계 시작 때의 master로 다시 만든다.

## 8. 정할 것

1. **정해짐(2026-10-14, codec v146):** 자기 차례 안의 선택 효과("may", 화살표 비용, 검은 trash 아이콘 `[FAQ p. 3]`)는 거절 없이 제시되고 턴 종료를 막지 않으며, 쓰지 않으면 턴 종료 누름에 사라진다(OQ-095 (2) 보강, 사용자 "선택행동의 경우 거절 버튼이 왜 따로 있는거야 그럼?"). 실행기의 Agent 차례 정책도 이것을 따른다. Reveal 선택 창은 바로 다음 작업에서 같은 원칙으로 고치고, 차례 위에 따로 뜨는 창(선택 trash, 연구 보너스, Intrigue 슬롯 등)은 엔진 전환 때 다시 본다. 정해진 순간에만 쓸 수 있는 선택(Gather Intelligence 등)은 그 순간 단독 창으로 묻는다(사용자 "이와 비슷한 행동이 있다면 무조건 먼저 단독으로 선택하게 하는게 필요해").
2. (B단계를 한다면) 행동 모양: `동사(대상, slot)` 한 단계(권고) 대 "능력 고르기 → 대상 고르기" 두 단계.
3. (B단계를 한다면) `agent_turn`(카드 × 칸 × 접합 × 잠입 초소 × 할인, 26,372줄)을 카드 → 칸으로 나눌지. 권고: 따로
   잰 뒤 정한다.

## 9. 규모와 위험

- A단계는 `rules/`의 절반 남짓(약 25,000줄)을 지난다. 세션 10회 안팎으로 본다. 카드 묶음의 옮겨 적기는 subagent에
  맡기고, 실행기 설계·관문 판정·리뷰는 주 세션이 한다.
- 위험: (1) 특이 흐름 약 57개(Agent 16, Reveal 21, 책략 약 20) → 전용 hook으로 옮기고 수를 단계마다 적는다. (2) 속도 →
  6절 6번. (3) 같은 시기 다른 세션의 엔진 수정과의 충돌 → 7절. (4) A8 망이 레시피 MLP보다 약할 수 있음 → 관문을 넘기
  전에는 플레이 서버를 바꾸지 않는다.
