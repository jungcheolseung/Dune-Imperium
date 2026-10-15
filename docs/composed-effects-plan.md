# 효과 조각 엔진 전환 계획 (composed effects)

상태: **진행 중** — A0 끝남(2026-10-15, 5절 "A0에서 만든 것"), A1 끝남(2026-10-16, codec v148, 5절 "A1에서 만든 것"), A2 44개 끝남(2026-10-16, codec 그대로, 5절 "A2에서 만든 것"), A3a·A3b 끝남(2026-10-16, 5절 "A3a·A3b에서 만든 것"), A3c 끝남(2026-10-16, 5절 "A3c에서 만든 것"), A3d 9칸 끝남(2026-10-16, 5절 "A3d에서 만든 것"), A3e 폐기 칸 5개 끝남(2026-10-16, 5절 "A3e에서 만든 것"), A3f 중 선택 획득 2칸 끝남(2026-10-16, 5절 "A3f-1에서 만든 것"), 다음 A3f의 나머지. 계획은 2026-10-14(같은 날 효과 목록 조사 뒤 B단계를 "A단계 뒤
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
| A3 | 개인 카드 Agent 칸 비용→보상 22개, 고르기 14개, Tread in Darkness, A2가 남긴 특이 흐름 7개. 조사(2026-10-16, git 무시 `tmp/claude/4767ed6a/a3/agent-choice-survey.md`)에서 처리기마다 사건 출처·순서가 달라 모양별로 나눈다: A3a hook 등록부와 A2의 특이 흐름(끝남), A3b 대상 없는 선택 지불 S1(끝남), A3c 필수 대상 고르기 S5(진영·첩자 칸·상대 병력·계약, 끝남), A3d 대상을 고르는 선택 화살표 S2a·S2b(보상을 곧바로 주는 것, 비용 뒤에 아이콘으로 거는 것 — 기록에 "걸리는 보상 아이콘" 칸이 따로 필요; 버리기 7칸·책략 폐기 2칸 끝남, 개인 카드 폐기 3칸과 Piter는 A3e로), A3e 검은 폐기 아이콘·한 칸 안 연속 고르기 S3·S4(폐기 칸 5개 끝남; Arrakis Observer·Piter·Control the Spice는 A3f로), A3f 평범한 줄이 한쪽인 고르기 S6·고르기 아이콘이 섞인 칸 S7(Tread in Darkness)·선택 획득 S8(끝남) |
| A4 | Reveal 선택 26개와 Reveal 자동 이득, 획득·폐기·버림·차례 시작 효과 |
| A5 | 보드 칸, Conflict 보상, 계약 |
| A6 | 지도자(인장은 능력, 상시 효과는 유발), Tech |
| A7 | Immortality(접합, 연구, Tleilaxu, 표본), Arrakeen Scouts |
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
