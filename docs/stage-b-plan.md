# B단계 설계: 행동 이름·단위 교체

상태: **B1·B2·B3a·B3b 구현, B3c부터 남음** (2026-10-20, 브랜치 `stage-b`, 미병합·미푸시). 사용자 결정: B단계를 측정 실험 없이 한다 — "구조 상 B단계도 해야한다고 봐"
([composed-effects-plan.md](composed-effects-plan.md) 5절 "B단계"). 아래 1절의 숫자는 master `e7e9ad4f`(codec v149)에서 셌다.

## 0. 무엇을 바꾸나

A단계는 카드 효과를 능력 기록으로 옮기고 엔진이 기록을 실행하게 했지만, AI·화면·저장 파일이 주고받는 **행동**의 이름과 단위는
그대로 두었다. B단계는 그 행동을 바꾼다. 세 갈래다.

1. **`agent_turn` 나누기:** Agent 차례 행동 하나가 카드 × 칸 × 접합 × 잠입 초소 × 할인 × 비용 선택을 모두 담는다. 이것을 카드
   고르기와 칸 고르기로 나눈다.
2. **묶인 지급 풀기:** Conflict 보상·계약 완수·Reveal 자동 이득은 아이콘을 종류별로 더한 합계(`ConflictReward`, `ContractReward`,
   `PersonalCardRevealEffect`)로 한꺼번에 준다. 이것을 기록의 아이콘(조각) 하나씩 주게 바꾼다(정리-2e에서 미룬 일, OQ-027의
   "인쇄된 아이콘마다 독립"과 같은 원칙).
3. **이름 통일:** 같은 일을 하는데 출처마다 이름이 다른 행동(폐기 20종, 거절 41종, 빈 확인 15종 …)을 동사 하나로 합치고, 어느
   효과에 답하는지는 인자로 붙인다.

## 1. 지금 모습 (조사)

**행동 종류와 카탈로그.** 행동 id 280종(동사 45, 출처 20, 대상 25; `rules/action_shapes.py`의 행이 모두 서로 다르다). 옵션 전부
카탈로그 36,385행 가운데 **`agent_turn` 하나가 26,372행(72%)** 이다.

| `agent_turn` 인자 | 행 |
| --- | --- |
| 카드(`card_id`, 카드 종류 단위로 정규화) | 183종 |
| 칸 쪽(`space_id`·`cost_option`·`discount`·`infiltrate_post_id`의 조합) | 76종 |
| 접합(`graft`) 행 | 13,908 |
| 잠입 초소 행 | 13,880 |

카드와 칸을 나누면 `agent_turn`은 약 183 + 76행(접합 표시를 더해도 수백 행)이 되고, **카탈로그는 약 10,300행으로 72% 준다.**
접합 상대는 이미 따로 고른다(`choose_graft_partner`).

**출처만 다른 이름.** 출처를 빼고 (동사, 대상, 답하는 동사, 더 답하는 동사, 변형, 꼬리표)가 같은 id를 합치면 280종 → 210종(42묶음
112종이 합쳐진다). 동사별로는 거절 41종(56행), 폐기 20종(3,090행), 획득 19종, 고르기 17종, 지불 17종, Spy 회수 15종, 빈 확인 15종.

**행동 이름을 읽는 곳(문자열 등장 수, `.py`·`.js`).**

| 영역 | 등장 |
| --- | --- |
| 엔진 `rules/` | 1,289 |
| 테스트 | 5,375 |
| 앱 AI | 927 |
| 화면 JS | 747 |
| E2E | 441 |
| 어댑터·학습(codec 포함) | 435 |
| 그 밖의 AI | 239 |
| 표시(`display/`) | 173 |
| 기보(`records/`) | 149 |
| 그 밖의 스크립트 | 136 |
| 서버 py | 41 |
| **합계** | **9,952** (엔진 밖 8,663) |

묶음별: `agent_turn` 340곳(테스트 213), 폐기 20종 575곳, 거절 41종 1,048곳, 빈 확인 15종 301곳. 즉 **`agent_turn` 나누기는 손댈
곳이 적지만 엔진의 결정 구조가 바뀌고, 이름 통일은 엔진 구조는 거의 그대로인데 손댈 곳이 가장 많다.**

**여러 효과가 함께 기다리는 곳.** 지금 같은 결정에서 어느 효과에 답하는지는 대부분 id 자체(출처가 이름에 들어 있음)로 가른다.
인자로 가르는 곳은 둘이다: 접합 차례의 둘째 카드 `box=1`(꼬리표 `box`, 60종), 공개한 카드의 Reveal 선택 `source=<카드>`(꼬리표
`source`, 11종). 화면은 이미 이 둘로 행을 카드별 머리 아래 묶는다(`display.actions.agent_box_headers`·`reveal_choice_headers`).

## 2. 정할 것 셋 (사용자 결정)

**정해진 것(2026-10-19):**
1. **두 단계** — 사용자 "결정 단계나 학습 방법 상 두 단계로 나누는게 나을거 같은데" (처음 권고는 한 단계였다; 학습 면의 장점 —
   대상 수에 따른 쏠림이 없고, 효과의 가치와 대상의 가치를 따로 배운다 — 을 다시 따져 바꿨다). 규칙: 대상이 없는 효과는 한 번에;
   반쯤 고른 효과는 차례 안에서 되돌릴 수 있고(숨은 정보가 드러나지 않음), 그동안 턴 종료는 나오지 않는다; **대상이 하나뿐이어도
   둘째 단계를 연다**(사용자, 2026-09-30 원칙과 같음). [OQ-111](rules/open-questions.md#oq-111--두-단계-행동의-중간-상태)
2. **`agent_turn`을 카드 → 칸으로 나눈다** — 아래 결정 2의 규칙 1–3 그대로(OQ-111).
3. **인쇄한 것으로 가리킨다** — 출처 종류 + 인쇄한 개체 + 아이콘, 같은 카드의 두 칸만 `box`. 같은 카드 사본 둘이 같은 효과를
   함께 기다리면 이름표 하나로 보고 먼저 낸 사본부터 처리한다(예를 찾아 확인할 것).

**두 단계가 늘리는 판단(측정, 옵션 전부, 앱 AI·휴리스틱 각 8판):** 한 판 약 1,000번 가운데 `agent_turn` 나누기 +91, 기다리는 효과의
대상 고르기 +218 — 합쳐 약 +31%. 구매·책략 내기·접합 상대처럼 차례 행동의 대상까지 두 단계로 하면 +140이 더해져 약 +45%. 이미 "어느
아이콘을 처리할까"를 고르는 행동(`resolve_board_effect` 한 판 95번, `resolve_agent_card_effect` 48번)은 그 자체가 첫 단계라 늘지 않고,
병력 배치 수(`deploy_troops(count)`) 같은 수량은 대상이 아니다.

**범위(사용자 결정 2026-10-19, "그런 것들도 두 단계로 하자. 운항카드 같은 것도 체크하고"):** 차례 행동의 대상(Reveal 구매, 책략
내기, 접합 상대, 운항 카드 놓기 `place_navigation_card`, Scouts 시장 카드 가져오기 `scouts_take_card`)도 두 단계. 수량(유닛 조합의
`count`·`commanders`·`zone`, Scouts 입찰)은 한 행의 인자로 남는다. 한 행동에 독립된 선택이 둘 곱해진 것은 차례대로 나눈다 — 책략 내기
(카드 → 갈래), 영향력 교환(잃을 진영 → 얻을 진영), Spy 둘 회수(첫 초소 → 둘째 초소), 책략 주기(카드 → 받는 좌석), Endgame 와일드
맞추기(카드 → 와일드 카드), Tech 획득(타일 → Spy를 놓는 타일이면 초소). 운항 카드의 갈래 쓰기 `play_navigation(option)`는 효과 고르기
자체(첫 단계)다. 행동 280종 전부의 처리는 [stage-b-actions.md](stage-b-actions.md): B1 1, 두 단계 118, 첫 단계 그 자체 12, 한 단계 149.
**이 범위로 다시 잰 판단 증가:** 한 판 약 1,000번에 +413(약 +41%) — `agent_turn` 나누기 91, 대상 고르기 284, 곱해진 선택의 추가 단계 38.

(아래는 결정 전의 비교다.)

### 결정 1 — 행동 모양: 한 단계 대 두 단계

- **한 단계(권고):** 효과와 대상을 한 행동에 담는다. 예: 폐기할 수 있는 카드가 셋이면 `trash(card=A, …)`·`trash(card=B, …)`·
  `trash(card=C, …)` 세 행. 지금 엔진·화면·OQ-027("인쇄된 아이콘마다 한 행동")과 같은 모양이다.
- **두 단계:** "이 폐기 효과를 쓴다"를 고른 뒤 다음 결정에서 카드를 고른다. 목록은 짧아지지만 모든 효과에 결정이 하나씩 늘고,
  그 사이 상태를 되돌리기·턴 종료(OQ-057)·탐색 AI·화면이 모두 다뤄야 한다.
- **권고 이유:** 두 단계가 줄여 주는 목록 길이는 이미 문제가 아니다(엔티티 망은 행동을 부분으로 점수 매기고, 줄어들 큰 덩어리는
  `agent_turn`뿐인데 그것은 결정 2가 따로 다룬다). 반면 중간 상태는 지금까지 공들여 맞춘 한 번 누르는 턴 종료·되돌리기 원칙에
  새 경우를 모두 더한다.

### 결정 2 — `agent_turn`을 카드 → 칸으로 나눌지

- **나눈다(권고):** 차례가 "카드 고르기"(그리고 접합 카드면 지금처럼 상대 고르기)를 먼저 묻고, 다음 결정에서 "칸 고르기"(비용
  선택·할인·잠입 초소는 칸 행의 인자)를 묻는다. 카탈로그 −72%, 망은 "이 카드가 좋다"와 "이 칸이 좋다"를 따로 배운다(지금 MLP는
  26,372개 조합 행을 하나하나 따로 배운다). 화면은 이미 사람에게 카드 → 칸 → 나머지 순서로 보여 준다(서버 목록을 단계로 묶을
  뿐, 보내는 행동은 하나 — `staged_turn.py`).
- **그대로 둔다:** 결정 구조가 안 바뀐다. 카탈로그와 망의 큰 덩어리가 그대로다.
- **나눌 때 정해야 하는 규칙(설계 단계에서 OQ로 적고 판정을 받는다):**
  1. 카드만 고른 중간 상태는 **다른 좌석에게 보이지 않는다**(칸을 고르는 순간 카드와 칸이 함께 공개 — 실물에서 카드를 내며 Agent를
     놓는 한 동작과 같다). 그 좌석 자신의 화면·관측에만 보인다.
  2. 카드 고르기는 **차례 안에서 되돌릴 수 있다**(숨은 정보가 드러나지 않으므로). 칸을 고른 뒤의 규칙은 지금과 같다.
  3. 카드를 고를 수 있는 것은 **놓을 수 있는 칸이 하나라도 있는 카드**뿐이다(고른 뒤 막다른 길이 없게).
  4. 탐색 AI의 뿌리 결정은 "카드"가 된다(후보 5개가 카드 5장). 칸은 그 아래 결정으로 망이 고른다. 측정 대상(관문에서 확인).

### 결정 3 — 함께 기다리는 효과를 가리키는 방법 ("자리")

이름에서 출처를 빼면, 같은 결정에 기다리는 효과가 여럿일 때 행동이 어느 효과에 답하는지를 인자로 알려야 한다.

- **인쇄한 것으로 가리킨다(권고):** 출처 종류(`source=agent_card` 등, 지금의 출처 20종) + 그 효과를 인쇄한 개체(카드 사본, 칸, 지도자,
  Tech, 계약, Conflict 카드) + 같은 카드의 두 칸을 가를 때만 `box`. 지금의 `box`·`source` 꼬리표를 넓힌 것이다. 화면의 카드별 머리와
  그대로 맞고, 엔티티 망은 그 개체의 임베딩으로 읽는다.
- **자리 번호로 가리킨다:** 대기 목록의 k번째(`slot=k`). 짧지만 같은 번호가 판마다 다른 효과를 가리켜 망과 기보 다리가 헷갈리고,
  하나를 해결하면 번호를 당길지도 정해야 한다.
- **출처 종류를 이름에 남긴다:** 이름 통일을 하지 않는 것과 같다(아래 4절의 B3를 뺀다).

## 3. 순서와 관문 (제안)

| 단계 | 내용 | 손댈 곳 | 예상 |
| --- | --- | --- | --- |
| B1 | `agent_turn` 카드 → 칸 (결정 2) | 엔진 Agent 차례, 탐색 AI, 화면 단계 묶음, 기보 다리, 테스트 213 | 2–3일 |
| B2 | Conflict 보상·계약·Reveal 이득을 아이콘 하나씩 (정리-2e에서 미룬 것) | `combat.py`·`contracts.py`·`reveal_turn.py` 지급, 사건 payload, 화면 문구 | 1–2일 |
| B3 | 두 단계 효과 해결 + 이름 통일 + 인쇄한 것으로 가리키기 (결정 1·3) | 실행기의 제시 정책(효과 고르기 → 대상 고르기), 화면, 앱 AI, 엔진 밖 약 8,000곳(테스트 대부분, 에이전트에 맡김), 기보 다리 | 4–6일 |
| 학습 | B 전체 뒤 한 번(엔티티 계보: 증류 → PPO → 탐색 좌석 관문) | | 하룻밤 + 반나절 |

- 단계마다 지금까지의 관문을 넘긴다: 같음 확인 200판(옛 행동 → 새 행동 대응을 정해진 차이 모듈로), 기보 대조(옛 기록은 새 다리로),
  pytest·ruff·mypy, 소크, 속도, E2E. 행동이 바뀌는 곳마다 화면의 이름표(`labels*.js`)와 `action_shapes.py`를 같은 변경에서 고친다.
- **병합:** cleanup2 때 정한 대로(가) 단계별로 master에 병합할지, B 전체를 v150 하나로 병합할지는 B1이 끝날 때 다시 정한다(저장 호환이
  단계마다 끊기는 것과 브랜치가 오래 열리는 것 사이).
- **망:** B1부터 행동 공간이 바뀐다. 플레이 서버의 MLP는 B1 뒤 새 행을 0에서 시작해 쓰기 어렵다(`agent_turn`이 통째로 바뀜) —
  B1을 병합하려면 그 전에 재학습하거나, B 전체를 묶어 한 번에 병합하고 그 뒤 학습한다. 이것도 병합 방식과 함께 정한다.

## 3a. B1 설계 — `agent_turn`을 카드 → 칸으로

지금 흐름(`rules/agent_turn.py`): 차례 frame이 손패의 카드마다 접합 여부(접합 카드는 접합으로만, 짝이 있으면 접합으로도)를 갈라
`_placements_for_card`로 (칸, 비용 선택, 할인, 잠입 초소) 조합을 모두 만든다. 칸이 열리는지는 가능한 짝(Bond 짝, Usurp의 짝 아이콘,
Tleilaxu Infiltrator)에 달려 있고, 짝은 놓은 뒤 `choose_graft_partner`로 고른다. 화면은 이 행들을 받아 사람에게 카드 → 칸 → 나머지로
나눠 보여 준다(`static/turn.js` "staged Agent turn").

- **행동 둘(이름은 임시, B3에서 이름 통일):** `choose_agent_card(card_id[, graft])` — 놓을 수 있는 조합이 하나라도 있는 (카드, 접합 여부)만;
  `place_agent(space_id[, cost_option][, discount][, infiltrate_post_id])` — 고른 카드의 조합만. 놓은 뒤 접합 상대 고르기는 그대로.
  카탈로그는 `agent_turn` 26,372행 대신 카드 쪽 수백 행 + 칸 쪽 76행.
- **반쯤 고른 상태:** 고른 카드와 접합 여부는 차례 frame의 context에 둔다(frame context는 다른 좌석의 보기에 나가지 않는다,
  `core/observation.py`). 그 좌석의 보기와 관측에는 새 칸(고른 카드)을 둔다 — 관측 v33(새 segment, MLP·엔티티 모두 이름으로 옮기면
  새 입력은 0에서 시작). 공개 사건은 놓는 순간에만 내고, 카드 고르기에는 그 좌석에게만 보이는 사건을 낸다(로그).
- **사이에 낼 수 있는 것:** 카드를 고른 뒤에는 그 카드의 `place_agent` 행만 낸다(공개 차례로 바꾸기·Plot 책략은 카드를 고르기 전에).
  카드를 고를 때 놓을 곳이 있었으므로 막다른 길이 없다. 되돌리기는 서버의 되돌리기(숨은 정보도 우연도 없어 되돌릴 수 있는 수);
  AI는 되돌리지 않으므로 고른 카드는 놓는다. 그 사이 턴 종료는 나오지 않는다.
- **AI:** 앱 AI와 휴리스틱은 지금처럼 (카드, 칸) 쌍을 평가해 가장 좋은 쌍의 카드를 고르고, 칸 단계에서는 고른 카드의 칸을 다시
  평가한다(같은 계산이라 일관된다). 무작위 AI는 카드, 칸을 차례로 고른다(무작위 판의 분포가 바뀐다 — 같음 확인은 정해진 차이로).
  탐색 AI는 뿌리 결정이 카드가 된다(후보 = 카드). 관문에서 잰다.
- **기보:** 옛 `agent_turn(card, space, …, graft)` 한 수 앞에 `choose_agent_card(card, graft)`를 끼우고, 그 수를
  `place_agent(space, …)`로 고쳐 쓴다(구현: 다리 `agent_card_pick`·`agent_space_pick`, 아래 "B1 구현").
- **같음 확인:** 정해진 차이 — 옛 한 수를 새 두 수로, 그 좌석 보기의 새 칸은 정돈(구현: `stage_b.py`의 `agent_turn_steps`).
- **화면:** 손패 클릭이 `choose_agent_card`를 보내고, 판에는 고른 카드의 칸이 열린다. "뒤로"는 되돌리기. 카드를 고르기 전 칸
  미리보기(카드에 올렸을 때 갈 수 있는 칸)를 지키려면 서버가 카드별 놓을 곳 요약을 함께 보낸다(`reveal_preview` 같은 화면 전용 값).
- **병합:** B1 뒤에는 플레이 MLP의 Agent 차례 행이 모두 새 행이라(휴리스틱이 대신 둠) master에 따로 넣기 어렵다. **B를 브랜치에서
  마치고 v150 하나로 병합한 뒤 한 번 학습**하는 쪽을 권한다(B1이 끝날 때 다시 묻는다).

### B1 구현 (브랜치 `stage-b`, codec v150 · 관측 v33)

설계에서 바뀐 것과 구현하며 정한 것:

- **엔진:** `rules/agent_turn.py`에 `choose_agent_card`·`place_agent` 처리와 `executable_placements`(놓을 수 있는 배치 전체,
  예전 `agent_turn` 행; 구현 안 된 칸·인장 걸러내기를 `engine.py`에서 옮김). 고른 카드가 있으면 차례 frame은 그 카드의
  `place_agent`만 낸다. 고른 카드는 frame context에, 그 좌석의 보기는 `private.agent_card_pick`/`agent_card_pick_graft`.
  카탈로그는 모든 옵션 36,385 → 10,436행, 기본 4,551 → 2,917행.
- **AI 한 번 판단:** 휴리스틱·앱 AI는 배치 전체를 보고 고른다(`agents/agent_turn_steps.py`). 카드 단계에서 고른 배치를
  `PlacementMemory`가 기억해 칸 단계에서 다시 묻지 않는다 — 다시 물으면 매 결정의 무작위 동점 처리가 한 번 더 일어나 그 뒤
  수순이 옛 엔진과 갈렸다(처음 구현에서 테스트 시드 십여 개가 "판이 바뀌어" 다시 골라졌던 원인). 기억을 넣은 뒤 휴리스틱·앱 AI
  판은 master와 수순까지 같다(기본·전 확장 28판 대조). 상태를 받는 곳(서버, 소크, rollout, 탐색 대체 정책, E2E 저장본 만들기)은
  모두 `choose_action_with_state`를 쓴다. 무작위 AI는 카드, 칸을 차례로 고르므로 무작위 판은 달라진다.
- **화면:** 카드 고르기 결정에 서버가 그 카드들이 이어질 배치 전체를 보낸다(`agent_placements`: 카드 고르기 행 번호, 배치
  인자, 고유 키 `placement`, 그리고 두 단계를 함께 미리 돌린 되돌리기·부족·전투력·미리보기 값). 페이지는 예전처럼 카드·칸을
  어느 순서로든 고르게 하고, 다 고르면 카드 고르기와 맞는 칸 고르기를 차례로 보낸다(요청 둘). 새로고침·되돌리기로 카드만
  고른 상태에 오면 칸 고르기 행과 `private.agent_card_pick`로 같은 화면을 그린다. 로그에는 카드 고르기 줄이 따로 남고
  다른 좌석에는 그 카드가 "(비공개)"다.
- **기보:** 다리 `agent_card_pick`(기록된 배치 앞에 카드 고르기를 끼움)과 `agent_space_pick`(기록된 배치를 칸 고르기로
  고쳐 씀). 문제집(사람 판 문제)은 배치가 든 문제를 두 수가 처음 갈리는 단계에서 묻는다: 카드가 다르면 카드 고르기, 같으면
  그 카드를 고른 뒤 칸 고르기, 한쪽만 배치면 카드 고르기(`records/problems.py`).
- **같음 확인:** 정해진 차이 `scripts/ab/differences/stage_b.py`(`agent_turn_steps`) — 옛 한 수를 새 두 수로, 카드 고르기
  행·사건·빈 보기 칸을 옛 모양으로.
- **독립 리뷰에서 고친 것:** 서버 로그가 카드 고르기의 값만 가려 손에 공개된 카드와 `graft: true`가 다른 좌석에 보였다 → 카드
  고르기를 봉인하고 다른 좌석에는 `card_id` 한 칸만(OQ-111 (1)). 카드만 고른 상태(새로고침·칸 고르기 되돌리기)에서 화면이 ①을 비워
  두고 "에이전트 차례 또는 공개 차례 선택"을 띄웠다 → ①은 그 카드로 고정(✕는 되돌리기), 배너는 "{agent} 보낼 칸 선택". "되돌리기"
  한 번이 칸 고르기만 되돌려 카드만 고른 상태에 머물렀다 → 페이지가 한 번에 보낸 배치는 한 번에 되돌린다. 두 번째 요청은 카드
  고르기가 실제로 들어갔는지(그 좌석의 보기) 확인한 뒤에만 보낸다. rollout AI와 tie census도 배치 전체를 본다. 턴 시작 창이 열려
  있는 동안 배치 목록을 숨긴다(E2E가 잡음).
- **측정:** 같음 확인 200판 같음(192,672걸음, 배치 15,438번), 휴리스틱·앱 AI·rollout 판 master와 수순 동일, 소크 720판 실패 0,
  기록된 결정의 `legal_actions` 호출당 46.5µs(캐시 끔; master 54µs), 휴리스틱 판 전체 시간 +14%(결정이 약 41% 늘어서; 배치 목록은
  상태별 한 번만 만든다), 문제집 tips-v1 105개 재채굴, 사람 판 문제 279/285(master와 같은 6곳은 정리-2f 이전부터).
- **망에 대해 (리뷰):** 옛 체크포인트를 v150으로 불러오면 카드 고르기 결정에는 학습된 행(공개 차례, Plot 책략 등)이 함께 있어
  휴리스틱 대체가 일어나지 않고, 0 logit 사이에서 목록 첫 카드를 고른다(위 "병합"의 "휴리스틱이 대신 둠"은 칸 고르기에만 맞다).
  그래서 재학습 전에는 이 브랜치에서 옛 망을 평가하지 않는다; 재학습은 흉내(증류)부터 시작한다.

## 3b. B2 설계 — 묶인 지급을 아이콘 하나씩으로

### 지금 모습 (조사 2026-10-19)

- **Conflict 보상**(`ConflictReward`, `rules/combat.py` `_pay_next_combat_reward`): 기록 한 줄을 종류별 칸으로 더한 합계를 고정 순서로
  준다 — 책략 draw → 병력 → 자원·VP(한 번에) → 고정 진영 영향력 → 지배 → 그다음 선택 창(계약 → 영향력 고르기 → 선택 지불 화살표 →
  서로 다른 영향력 → 폐기 → Spy). 사건은 수령자마다 `combat_reward_gained` 하나에 합한 값(요청한 수, CHOAM 없을 때 계약 2 Solari
  섞임). 인쇄 순서와 지급 순서가 다른 1위 줄이 셋이다: CHOAM Security(병력·계약·Guild 영향력 → 영향력이 계약 창보다 먼저),
  Seize Spice Refinery(spice·Spy·지배 → 지배가 먼저), Test of Loyalty(Solari·Spy·황제 영향력 → 영향력이 먼저 — 황제 트랙의 Spy 아이콘이
  보상 Spy보다 먼저 나올 수 있어 결과가 달라질 수 있다).
- **계약 보상**(`ContractReward`, `rules/contracts.py`): 병력·Solari·water·고정 영향력을 한 번에 준 뒤 선택 창은 **하나만** 연다 —
  선택 아이콘이 둘 이상인 계약은 `NotImplementedError`(지금 계약에는 없다). 사건 `contract_completed` 하나에 합한 값.
- **Reveal 자동 이득**(`PersonalCardRevealEffect`, `rules/reveal_turn.py`): 이미 OQ-045대로 Persuasion·검만 시작 때 더하고, 병력·책략·
  자원 묶음(인쇄 한 줄의 자원)·영향력·표본·Tleilaxu·연구는 소유자가 순서를 골라 하나씩 받는다. 합계는 지급보다 "어느 줄이 조건을
  채웠는가"를 담는 데 쓰인다.
- **규칙 문서:** 한 보상 줄 안의 아이콘 순서는 어느 문서도 정하지 않는다(OQ-002·OQ-102는 수령자 사이 순서만). Agent 차례 효과는
  "원하는 순서" `[Main p. 9]`, Reveal 효과도 "원하는 순서" `[Main p. 12]`. 지금 Conflict·계약의 고정 순서는 구현 기본값이다.

### 정할 것 (사용자 결정)

- **결정 B2-1 — 보상 한 줄 안의 순서:** (가) 받는 좌석이 고른다 — 보상의 아이콘마다 줄 하나, 원하는 순서로(OQ-027 "인쇄된 아이콘은
  각각 독립, 소유자가 순서를 고른다"를 Conflict·계약에도; 차례 밖이면 연구 보너스 창처럼 순서 창, 차례 안이면 차례의 줄). (나) 인쇄
  순서대로 진행하고 선택 아이콘에서만 멈춘다(실행기가 Intrigue 카드를 처리하는 방식). **추천: (가)** — 원칙이 이미 Agent 칸·연구
  보너스·Reveal에 닿아 있다.
- **결정 B2-2 — 자동 아이콘만 남았을 때도 줄을 여나:** (가)를 고르면, 고를 것 없는 자원·병력·책략 아이콘도 줄로 내고 하나뿐이어도
  연다(2026-09-30 원칙, OQ-111 (2)) 대 고를 것이 하나뿐인 자동 아이콘은 바로 준다. **추천: 줄로 연다(원칙대로).** 대가: Conflict 보상마다
  사람 좌석이 한 번 이상 누른다(AI 결정은 판당 대략 수십 개 늘어난다).
- **결정 B2-3 — 자원 묶음:** 기록의 `GainResources` 하나(예: "2 Solari + 1 water")를 줄 하나로 둘지, 자원 아이콘마다 나눌지. **추천:
  줄 하나**(OQ-045가 Reveal에서 정한 "인쇄 한 줄의 자원은 한 묶음"과 같게; 자원끼리는 순서가 결과를 바꾸지 않는다).

**사용자 결정(2026-10-19, "그래 추천대로 진행하자"):** B2-1 (가) 받는 좌석이 순서를 고른다, B2-2 자동 아이콘도 줄로(하나뿐이어도),
B2-3 자원 묶음은 줄 하나. 기록은 [OQ-112](rules/open-questions.md#oq-112--보상-한-줄-안의-아이콘-순서).

### 정해진 것으로 두고 진행할 것

- **Conflict:** 수령자마다 보상 창 하나(순위·동률·수령자 순서는 OQ-002·OQ-102 그대로). 창의 줄은 그 줄의 기록 조각 하나씩 —
  자동 조각은 받기 줄, 선택 조각은 그 선택(영향력 고르기, 선택 지불, Spy, 폐기, 계약)으로 들어가는 줄. sandworm 두 배는 각 조각을 두
  번(자동 조각은 양 두 배의 줄 하나, 선택 조각은 두 줄). Pivotal Gambit의 1위 영향력 +1은 같은 창의 영향력 줄 하나로. 지배는 받기 줄.
  CHOAM 없을 때 계약 아이콘은 "2 Solari 받기" 줄로(같은 조각, 다른 효과 `[Main pp. 16, 20]`).
- **계약:** 완수 때 보상 조각마다 줄 — 차례 안이면 차례의 줄(Agent 칸 아이콘처럼 턴 종료를 막는다), 차례 밖(동맹 계약, Reveal 중
  획득 계약)이면 Conflict와 같은 보상 창. 선택 아이콘이 둘 이상인 계약도 받는다(`NotImplementedError` 없앰).
- **Reveal:** 합계 대신 기록 줄을 직접 읽는다. 조건 판정·늦은 지급·대기 목록은 그대로이고 행동은 바뀌지 않는다(대기 항목이 어느
  카드의 어느 줄인지 담는 것만 — 이름은 B3에서 "인쇄한 것"으로). **구현하며 바꾼 것(2026-10-19):** B3로 미룬다. Reveal 자동 이득은
  이미 OQ-045대로 종류별 행동을 소유자가 순서를 골라 받는다(결정 단위로는 이미 아이콘 하나씩이고, 자원 묶음은 OQ-112 (3)과 같다).
  남은 것은 `PersonalCardRevealEffect`를 기록 줄 읽기로 바꾸는 내부 정리뿐인데, `reveal_turn.py`에서만 117곳·카드 정의의 필드까지
  닿는 동작 변화 없는 큰 변경이라, 효과 해결 전체를 두 단계로 다시 짜는 B3에서 함께 한다.
- **계약 보상 창의 자리(구현하며 바꾼 것):** 위 "차례 안이면 차례의 줄"은 B3로 미룬다. B2의 계약 보상 창은 완수한 자리에 쌓이는 창
  (차례 안에서도 그 창의 줄을 먼저 다 받는다)이다 — 지금의 완수 흐름(선택 창 하나를 쌓음)과 같은 자리이고, 차례의 대기 목록에
  계약 조각을 넣는 일은 모든 효과를 두 단계 줄로 바꾸는 B3와 같은 곳을 고친다.
- **사건:** 조각마다 그 조각의 표준 사건(`resources_gained`, 병력 recruit, 책략 draw, `influence_gained`, VP는 그 사건의 키 — 정리-2c
  문법)에 출처 `combat_reward`/`contract`를 단다. `combat_reward_gained`는 수령자의 머리 사건(순위·배수)으로 남기고 합한 값은 뺀다;
  `contract_completed`도 완수 사실만. 화면의 전투 결과 줄은 그 수령자의 조각 사건들을 모아 쓴다.
- **망·기보:** codec과 관측이 바뀐다(새 줄, 사건) — B 전체 재학습에 포함. 옛 기록은 다리 하나가 옛 고정 순서로 조각 줄들을
  답한다(연구 보너스의 `research_icon_order`와 같은 방식).
- **같음 확인:** 정해진 차이 — 옛 수령자 한 단계를 새 조각 줄들로, 합한 사건을 조각 사건으로.

### B2 구현 (브랜치 `stage-b`, codec v150 · 관측 v33 그대로)

설계에서 바뀐 것과 구현하며 정한 것:

- **엔진:** Conflict 수령자마다 창 `combat_reward_icons`(행동 `resolve_combat_reward_icon`, 인자 `effect` — `rules/combat.py`
  `_reward_window`·`apply_combat_reward_icon`), 완수한 계약마다 창 `contract_reward_icons`(`resolve_contract_reward_icon` —
  `rules/contracts.py` `_contract_reward_window`·`apply_contract_reward_icon`). 줄은 기록(`CONFLICT_REWARD_ABILITIES`,
  `CONTRACT_ABILITIES`; 둘째 사본은 첫 사본의 기록)의 조각을 그대로 읽는다. 고를 것 있는 조각의 줄은 예전 선택 창(영향력 고르기,
  선택 지불, Spy 회수 지불, 서로 다른 영향력, 폐기, Spy, 계약 시장, 계약 Spy·회수)을 창 위에 연다. Immediate 계약은
  `contract_tiles.receive_contract`가 활성으로 두고 `contracts.complete_immediate_contract`가 완수와 창을 연다(Intrigue·Scouts 길도
  같다). 새 FrameKind 둘은 PAUSE 뒤에 붙여 관측 번호가 그대로다. 카탈로그는 기본 2,917 → 2,931행, 모든 옵션 10,436 → 10,460행.
- **사건:** `combat_reward_gained`는 머리(multiplier·player·rank), 줄마다 `combat_reward_icon_resolved`·
  `contract_reward_icon_resolved`(effect와 그 줄이 준 양)와 그 조각의 표준 사건(`resources_gained` 출처
  `round:R:combat_reward:P:RANK`, 계약은 `<완수 출처>:contract_reward`). `contract_completed`는 완수 사실만.
- **AI·기보는 옛 순서로:** 휴리스틱·앱 AI·rollout은 창을 옛 고정 순서로 답하고 무작위 흐름에서 아무것도 뽑지 않는다
  (`agents/engine_order.py`, `legacy_combat_reward_icon`·`legacy_contract_reward_icon`) — B1의 `PlacementMemory`와 같은 이유로, 그
  AI들의 판이 master와 수순까지 같게. 옛 기록은 다리 `combat_reward_icon_follow`(적힌 단계 바로 뒤, follows)와
  `combat_reward_icon`(다음 적힌 단계가 받아지지 않을 때)이 같은 순서로 답한다. E2E 저장본을 만드는 걸음(`fixtures/placement_walk.py`
  등)도 같은 순서로 답해 시드가 그대로다.
- **옛 순서를 지키려고 정한 것(OQ-112 구현 메모):** (a) 차례 밖에서 기다리는 Emperor track Spy와 Friends Everywhere 선택은 계약
  보상 창이 맨 위인 동안에도 기다린다(Conflict 보상 선택을 기다리듯) — 영향력 4가 동맹도 얻어 Earn Any Alliance를 완수하면 옛
  엔진은 그 보상을 그 단계 안에서 주고 Spy를 뒤에 열었다(`spy_moves.track_spy_is_queued`, `scouts.four_bonus_choice_is_queued`,
  불변식 `check_track_spy_queue`). 옛 기보 대조가 휴리스틱 판 8개에서 Spy를 잡았고, 독립 리뷰가 같은 모양의 Friends Everywhere를
  짚었다. (b) Agent 차례 중 Solari로 산 카드가 Acquire 계약을 완수하면 창을 효과 frame 기록 뒤 맨 위에 다시 얹는다
  (`acquisition._lift_contract_windows`; 처음 구현은 효과 frame이 맨 위가 아니라 멈췄다 — 문제집 재채굴과 테스트 이전이 잡음).
  (c) 게임이 끝나는 단계에서 동맹을 얻어 Earn Any Alliance가 완수되면(Endgame Navigation 카드의 Influence) 아무도 결정에 답하지
  않으므로 창을 옛 순서로 곧바로 받는다(`contracts._settle_finished_reward`; 독립 리뷰가 끝난 판에 남은 창을 잡음).
- **옛 순서와 달라지는 곳(원칙대로, 사용자 결정 2026-10-19 "A로 가자"):** 같은 단계에서 생긴 곧바른 draw(OQ-106 13·14: CHOAM
  Transports의 카드, Bene Gesserit 4의 책략, Imperial Birthright)는 그 계약 보상 창의 모든 줄보다 먼저다 — OQ-106의 "그 바로 다음,
  사이에 다른 행동이 들지 않는다"가 계약 보상 줄(OQ-112로 각자 독립 효과)에도 닿는다. 옛 엔진은 계약 보상의 자동 부분을 완수 단계
  안에서 주고 카드를 그 뒤에 뽑았다. 처음 구현은 옛 순서를 지키려고 Transports 카드만 자동 줄 뒤에 빚졌는데, 선택 줄을 먼저 고르면
  카드가 그 선택 뒤로 밀려 "미룰 수 없다"(디자이너 판정)를 어겼고(독립 리뷰), "자동 줄은 완수의 일부"로 보는 절충안도 원칙 문구와
  맞지 않아 사용자가 A(완수 바로 뒤, 모든 줄 앞)를 골랐다. 결과는 대개 같다: 계약 자신에게 카드 draw가 있고 덱이 그 순간 비면
  섞기를 요청하는 draw가 바뀔 뿐 같은 덱 순서에서 같은 카드를 뽑는다. Suspensor Suits가 있으면 Bene Gesserit 4 책략의 순서가 결과를
  바꾼다(아래 기보 1판).
- **옛 기보를 위한 다리(Transports 카드):** `transports_card_first`(codec 150 미만) — 기록의 단계가 카드 뒤에서 기다리면(기록은 계약의
  카드 draw와 그 reshuffle을 먼저 적었다) 카드를 먼저 뽑고, 기록된 카드 draw는 올 때 버린다(`TRANSPORTS_CARD_DROPPED`);
  `transports_reshuffle_renamed` — 두 draw 가운데 빈 덱을 만난 쪽이 바뀌어 다른 이름으로 묻는 같은 좌석·같은 버림 더미의 reshuffle을
  기록된 순서로 받는다(v142의 `reshuffle_renamed`와 같은 모양).
- **화면:** 사람 좌석은 줄을 누른다(`display/actions.py`의 줄 문구, `static/labels*.js`·`log_icons.js`·`panels.js`의 사건·VP 원인,
  `render.js`의 전투 결과 줄이 수령자의 조각 사건을 모은다 — 출처가 보상 자신인 `resources_gained`만; 보상의 계약으로 받은
  Immediate의 Solari는 넣지 않는다, 독립 리뷰). 차례 밖 보상의 마지막 줄 뒤에 멈춤·공개가 오면 예전처럼 "턴 종료 ▶"까지
  붙잡히고, 줄은 숨은 정보를 드러내지 않으면 되돌릴 수 있다(보상 Spy를 붙잡은 단위가 이제 줄 셋 + Spy 네 단계).
- **같음 확인:** 정해진 차이 `scripts/ab/differences/stage_b.py`의 `combat_reward_icons` — 옛 수령자 한 단계 뒤에 새 줄들을 옛
  순서로 답하고, 머리와 조각 사건을 다시 더해 옛 `combat_reward_gained`와 값까지 비교한다(Influence 고르기 수만 빼고 — sandworm의
  둘째 몫은 다음 기록 단계에서 답한다). 나머지 사건은 줄의 사건이 단계의 다른 사건 뒤에 오므로 순서 없이 비교한다. 곧바른 draw가
  창보다 먼저인 곳은 옛 단계의 보상 사건을 후보가 줄을 받는 단계로 옮겨 정확히 맞추고, 그 사이(많아야 세 단계) 상태 비교를 빼고
  보기는 보상 필드만 빼고 비교한다. Transports 카드가 먼저인 곳은 기보 다리와 같은 모양으로 후보의 수를 짠다: 카드 뒤에서 기다리는
  기록 단계 앞에 카드를 두고, 기록된 카드 draw는 없애고, 다른 draw의 이름으로 기록된 같은 버림 더미의 reshuffle은 후보의 이름으로
  묻는다(`_transports_moves`). 처음 판은 머리·조각 사건을 양쪽에서 버려 값을 비교하지 않았고, 그래서 CHOAM에서 계약 줄의 사건에
  계약 수가 빠진 것(전투 결과 줄에서 계약 아이콘이 사라짐)을 놓쳤다(독립 리뷰).
- **측정:** 같음 확인 200판 같음(192,672걸음; 줄 Conflict 9,456개·계약 1,280개를 옛 순서로 답함). 옛 기보 2,000판(v149-86086c6d)
  equal 1,574 · transient 425 · diverged 1. transient는 모두 곧바른 draw가 계약 창의 줄보다 먼저여서 생기는 한두 단계의 차이다 —
  기록은 완수 단계에서 보상을 받고 카드를 뒤에 뽑았는데 이 엔진은 카드를 먼저 뽑고 줄을 뒤에 받으므로, 그 사이 기록된 단계에서 보상
  필드(자원·병력·영향력·VP, 계약의 카드·책략 draw)와 Transports 카드의 owed_draws·덱·손이 다르고, 줄을 받는 즉시 같아진다(옛 순서를
  지키던 판은 51판이었다). diverged 1판(full.h4.98)은 Bene Gesserit 4의 책략을 계약(Earn Any Alliance) 병력 줄보다 먼저 뽑아 Suspensor
  Suits가 supply의 마지막 병력을 Conflict로 보내고, 병력 줄이 recruit할 병력이 없어 Conflict 순위가 바뀐다. 소크 무작위 700판·휴리스틱
  400판 실패 0(처음 돌림에서 (a)의 불변식을 잡음), pytest 8,119 통과, ruff·mypy 깨끗, E2E 68개 모두 통과.
  문제집 tips-v1 99개 재채굴(휴리스틱 82개는 같은 판·같은 자리, 줄이 끼어 선택 목록만 길다; 5081 망의 판은 망이 줄을 직접 골라
  달라짐), 사람 판 문제 279/285(B1과 같은 6곳).
- **테스트 이전:** 실패 226개를 옮겼다(돕는 함수 `tests/support/reward_windows.py`: 엔진으로 줄을 옛 순서로 답하는
  `answer_reward_windows`, 규칙 함수만으로 답하는 `settle_reward_window`). 무작위 걸음 시드를 다시 고른 테스트: 서버 셋(같은 좌석
  인계, Tleilaxu 구매 되돌리기, 연구 trash의 카드 칸), E2E 둘(`log_words` Scouts 짝 7·20, `turn_end`의 서버 거절 시드 —
  보상 받은 Conflict는 좌석이 직접 보게 되어 첫 사례가 8라운드로 늦어짐). 슬롯 망의 결정 종류 값이 PAUSE 뒤 종류에서 하나씩
  밀리던 것을 고쳤다(`training/slots.py`: 값은 PAUSE를 센 번호, 행은 PAUSE를 뺀 종류).
- **알아 둘 것:** B1 커밋(1d882c63)도 codec 150이라, 그 사이 이 브랜치에서 만든 저장본은 다리가 붙지 않아(다리는 150 미만만)
  첫 Conflict 보상·계약 완수에서 갈린다. 새 템플릿이 카탈로그 중간에 들어가 B1의 v150 행 번호도 밀린다. B1로 학습한 망이나 사람
  저장본은 없으므로 그대로 둔다(B 전체가 v150 하나로 병합된다).

## 3c. B3 설계 — 두 단계 효과 해결·이름 통일·인쇄한 것으로 가리키기

### 지금 모습 (조사 2026-10-19, 브랜치 `stage-b` 8467440c)

- **행동 283종**(동사 45, 출처 20). 분류표([stage-b-actions.md](stage-b-actions.md))의 "두 단계" 118종 가운데, 실제 판(옵션 전부,
  휴리스틱·무작위 각 12판)에서 본 105종을 어디서 내는지 셌다:
  - **이미 자기 frame에서만 나오는 것 26종(+ 그 frame의 거절·확인과만 함께 나오는 십여 종):** Conflict 보상 Spy·영향력, 계약 Spy,
    책략 선택 슬롯의 진영·Spy·버리기, Scouts 효과, 접합 상대, 지도자 고르기, 운항 카드 놓기 등. 첫 단계(보상 창의 줄, 책략 슬롯,
    아이콘 줄)가 이미 있어 **이름만 바뀐다.**
  - **차례 frame에 다른 효과의 줄과 섞여 나오는 것 약 65종:** Agent 효과 frame(카드 칸의 폐기·버리기·Spy·회수·영향력·계약 완수,
    보드 칸의 수확·소환·Imperial Privilege·Espionage, 지도자 인장, Tech 획득·뒤집기, 책략 내기), Reveal frame(구매 넷, Reveal
    선택의 Spy·회수·폐기·영향력, Tech 선택), 차례 frame(책략 내기, 차례 시작 카드). 이것들이 **새 첫 단계가 필요한 곳**이다.
- **이미 첫 단계인 행동 12종**(`resolve_board_effect(effect)`, `resolve_agent_card_effect(effect)`, `resolve_research_icon`,
  `use_intrigue_effect`, `play_navigation`, B2의 보상 창 줄 등)은 "어느 효과를 처리할까"를 고르는 줄이다. 이름이 출처마다 다르고
  (`resolve_*_effect`), 효과는 `effect` 인자의 낱말로만 안다.
- **중간 상태:** B1의 카드 고르기가 선례다 — 고른 것을 차례 frame에 두고, 그 좌석의 보기(`private.agent_card_pick`)로만 알리고,
  서버 로그는 봉인한다. 사람 화면은 서버가 보내는 미리보기로 두 단계를 한 번에 고르게 한다(`agent_placements`).

### 행동의 새 모양 (제안)

모든 행동 = **동사** + (기다리는 효과를 가리킬 때) **자리** + (대상을 고를 때) **대상** + (수량이면) **수량**.

- **자리(ref):** 결정 3(인쇄한 것으로 가리킨다)의 구체형. `source`(출처 종류: `agent_card`·`board_space`·`leader`·`tech`·`contract`·
  `conflict`·`intrigue`·`reveal_card`·`research`·`scouts`·`purchase` 등 지금의 20종) + `printed`(그 효과를 인쇄한 개체: 카드 종류, 칸,
  지도자, Tech, 계약, Conflict 카드, 시장) + `icon`(그 개체의 어느 아이콘·줄인가) + 접합 차례의 둘째 카드일 때만 `box=1`. 같은 카드
  사본 둘이 같은 효과를 기다리면 줄 하나로 보고 먼저 낸 사본부터 처리한다(결정 3; B3a에서 실제 예를 찾아 테스트로 고정).
- **효과 단계:** 기다리는 효과마다 줄 하나 — 이름은 그 효과가 하는 일의 동사: `trash(ref)`, `place_spy(ref)`, `recall_agent(ref)`,
  `gain_influence(ref)`, `recruit(ref)`, `draw(ref)`, `take_contract(ref)`, `acquire(ref)`, `play(ref)` … 대상이 없는 효과는 이 줄이
  곧바로 처리하고(지금의 `resolve_board_effect(effect=troops)` = `recruit(ref)`), 대상이 있으면 대상 단계를 연다. 출처별 이름
  (`trash_agent_card`·`trash_reveal_card`·… 17종)과 `resolve_*_effect` 묶음이 동사 하나로 합쳐진다.
- **대상 단계:** 열린 효과의 대상마다 줄 하나 — 대상 종류별 고르기: `choose_card(card)`, `choose_post(post)`,
  `choose_faction(faction)`, `choose_space(space)`, `choose_contract(contract)`, `choose_tech(tech)`, `choose_option(option)` …
  (지금 대상 종류 21가지). 어떤 효과의 대상인지는 그 frame(그리고 그 좌석의 보기)이 들고 있다. 대상이 하나여도 연다(OQ-111 (2)).
  수량(병력 수·유닛 조합·입찰)은 지금처럼 한 행의 인자다.
- **거절·빈 확인:** `decline(ref)`(지금 41종), `confirm_empty(ref)`(지금 `resolve_*_without_*` 15종). 차례 안의 선택 효과는 지금처럼
  거절 없이 턴 종료로 사라진다(OQ-095 (2)).
- **차례 행동의 대상**(사용자 범위 결정): 구매 `acquire(ref=시장)` → `choose_card`; 책략 내기 `play(ref=책략)` → `choose_card` →
  `choose_option`; 접합 상대, 운항 카드 놓기, Scouts 시장 카드도 같은 모양. 곱해진 선택은 차례대로(영향력 교환: 잃을 진영 → 얻을
  진영, Spy 둘 회수: 첫 초소 → 둘째 초소, 책략 주기: 카드 → 받는 좌석, Endgame 와일드: 카드 → 와일드 카드, Tech 획득: 타일 → 초소).
- **크기:** 행동 종류 283 → 약 60(동사 약 35, 대상 고르기 약 15, 차례·단계 행동). 판단 수는 앞서 잰 대로 한 판 약 +41%.

### 구현 방식 (제안)

- 실행기의 제시 정책 위에 **두 단계 제시층**을 둔다: 지금 공급자들이 내는 줄을 자리(ref)별로 묶어 효과 단계의 줄로 내고, 고른
  효과는 그 frame의 문맥에 둔다(B1의 고른 카드처럼). 대상 단계의 줄은 그 묶음의 줄을 대상 종류별 이름으로 다시 쓴 것이고,
  적용하면 지금의 처리기가 그대로 돈다. 그래서 규칙 처리는 바뀌지 않고, 바깥(AI·화면·codec·기보·관측)이 새 이름만 본다. 지금의
  id는 처리기 열쇠로만 남는다(`action_shapes` 표가 두 이름을 잇는다).
- **AI:** 휴리스틱·앱 AI는 B1의 `PlacementMemory`처럼 지금의 한 수(효과+대상)를 보고 고른 뒤 두 단계로 둔다 — 그래서 판이 지금과
  수순까지 같다. 망은 새 행동을 부분(동사·출처·대상 종류·개체)으로 읽는다(재학습).
- **관측:** 그 좌석의 보기에 고른 효과(동사·자리)를 더한다(B1의 `agent_card_pick`과 같은 자리).
- **기보·같음 확인:** 행동마다 옛 한 수 → 새 두 수(또는 이름만 바꿈)를 다리와 정해진 차이로(B1 방식). 옛 기록은 codec 150 미만이라
  다리로, B1·B2 사이 브랜치 기록은 없다.
- **화면:** 효과 줄을 누르면 대상이 판(카드·초소·칸)에서 고르게 열리고, 서버가 효과마다 대상 미리보기를 함께 보내 지금처럼 한 번에
  고를 수 있게 한다(B1의 `agent_placements`와 같은 방식).

### 하위 단계와 관문 (제안)

| 단계 | 내용 |
| --- | --- |
| B3a | 자리(ref)·두 단계 제시층·관측 칸·화면 틀; Agent 효과 frame(카드 칸·보드 칸·지도자 인장·Tech) |
| B3b | Reveal frame(구매·Reveal 선택·Tech 선택) + 차례 안 계약 보상을 차례의 줄로(B2에서 미룬 것) |
| B3c | 차례 frame과 Combat·Endgame(책략 내기 셋 단계, 차례 시작 카드, 와일드 맞추기) + 차례 줄 (접합 상대·운항·Scouts 시장은 B3d로, 아래 "B3c 세부 설계") |
| B3d | 이미 자기 frame인 선택들(보상 창·책략 슬롯·Scouts·지도자 frame)의 이름 바꾸기 + 거절·빈 확인 합치기 + 남은 출처별 이름 |
| B3e | Reveal 합계(`PersonalCardRevealEffect`)를 기록 줄 읽기로(동작 그대로, 내부 정리; B2에서 미룬 것) |

단계마다 같음 확인 200판·기보 2,000판·pytest·E2E를 넘기고 커밋한다. B 전체는 v150 하나로 병합하고 그 뒤 한 번 학습한다.

### 정할 것 (사용자 결정)

**사용자 결정(2026-10-19, "그래 모두 추천대로 가자"):** B3-1 (가) 효과 단계는 하는 일의 동사 + 자리, B3-2 (가) 대상 단계는
대상 종류별 고르기, B3-3 (가) 반쯤 고른 효과는 그 좌석에게만([OQ-111](rules/open-questions.md#oq-111--두-단계-행동의-중간-상태) (4)),
B3-4 (가) 차례 안에서 완수한 계약의 보상은 차례의 줄([OQ-112](rules/open-questions.md#oq-112--보상-한-줄-안의-아이콘-순서) (4)).

- **결정 B3-1 — 효과 단계의 이름:** (가) 그 효과가 하는 일의 동사 + 자리 — `trash(ref)`, `place_spy(ref)` …, 대상이 있으면 대상
  단계가 열린다. (나) 동사 하나 `use(ref)`로 고르고, 하는 일은 대상 단계의 이름에 둔다. **추천: (가)** — "어느 효과를 지금
  처리할까"가 실제 판단이고, 그 줄이 하는 일을 이름이 말한다(지금 `resolve_board_effect(effect=…)`의 낱말 인자를 동사로 올림).
- **결정 B3-2 — 대상 단계의 이름:** (가) 대상 종류별 고르기 — `choose_card(card)`, `choose_post(post)` …(무엇을 위한 대상인지는 열린
  효과가 말한다). (나) 동사를 되풀이 — `trash(card)`, `place_spy(post)`. **추천: (가)** — B3-1 (가)와 짝이고, 같은 일을 두 이름으로
  말하지 않는다.
- **결정 B3-3 — 반쯤 고른 효과를 누가 보나:** (가) 그 좌석에게만 — 대상을 고르는 순간 효과와 대상이 함께 공개된다(OQ-111 (1)의
  카드 고르기와 같다). (나) 모두에게. **추천: (가)** — 실물에 없는 중간 상태를 한 원칙으로 다룬다.
- **결정 B3-4 — 차례 안에서 완수한 계약의 보상:** (가) 차례의 줄로(Agent 칸 아이콘처럼 다른 효과와 함께, 턴 종료를 막는다) —
  B2에서 B3로 미룬 것. (나) 지금처럼 완수한 자리에 쌓이는 창. **추천: (가)** — 차례 안의 효과는 차례의 줄이라는 정리-2b·OQ-095 (2)의
  원칙과 같다. 차례 밖(Conflict 보상 중의 동맹 계약 등)은 지금처럼 창.

### B3a 세부 설계 (2026-10-19)

**제시층(`rules/effect_steps.py`).** 규칙 처리는 그대로 두고, 공급자들이 내는 옛 행동(이하 "온 행동")을 바깥에 두 단계로 보인다.

- **단계 표 `STEP_SPECS`:** 온 행동 id마다 (효과 동사, 출처, 인쇄한 개체를 읽는 법, 아이콘을 읽는 법, 대상 인자의 차례와 그 고르기
  이름, 남는 인자). 온 행동 하나 → 길(path) = [효과 줄, 대상 줄 …]. 효과 줄 = `동사(source, printed[, icon][, box])`, 대상 줄 =
  `choose_<대상 종류>(정해진 인자 이름)` — `choose_personal_card(card_id)`, `choose_intrigue_card(card_id)`,
  `choose_imperium_card(instance_id)`, `choose_reserve_card(card_id)`, `choose_post(post_id)`, `choose_space(space_id)`,
  `choose_faction(faction)`, `choose_contract(instance_id)`, `choose_tech(tech_id)`, `choose_seat(player)` …(대상 종류는
  `action_shapes.Target`). 옛 id마다 다르던 인자 이름(`intrigue_card_id`·`card_id` …)은 고르기 이름의 정해진 인자로 맞춘다. 수량
  인자(`count`·`commanders`·`zone`)는 마지막 줄에 붙는다(대상이 없으면 효과 줄에). 표에 없는 id(턴 종료, 병력 배치 등)는 그대로 낸다.
- **효과 단계를 쓰는 frame:** 여러 효과가 함께 기다리는 차례의 frame — B3a는 `agent_effects`, B3b `reveal`, B3c `turn`·책략 frame.
  한 효과를 위해 열린 frame(보상 Spy 창 등)은 효과 줄 없이 대상 줄만 낸다(B3d). frame 종류로 정하고, 기다리는 효과가 하나뿐이어도
  효과 줄을 연다(OQ-111 (2)).
- **고르기:** 효과 줄마다 길이 같은 온 행동끼리 묶는다(같은 효과 줄 = 같은 효과). 대상이 없는 효과의 줄은 곧바로 그 온 행동을
  적용한다. 대상이 있으면 고른 줄들(접두)을 그 frame의 context(`effect_pick`)에 두고, 다음 결정은 접두가 같은 길들의 다음 줄만 낸다
  (그 사이 다른 효과·턴 종료는 나오지 않는다; 바꾸려면 되돌리기 — B1과 같다). 길이 끝나는 줄을 고르면 `effect_pick`을 지운 상태에
  그 온 행동을 적용한다. 같은 줄들이 서로 다른 온 행동 둘을 가리키면 오류다(표에 아이콘을 더해 가른다; 테스트·소크가 잡는다).
- **보는 사람:** frame context는 다른 좌석의 보기에 나가지 않는다. 그 좌석의 보기에는 `private.effect_pick`(고른 줄들), 관측 v33에
  고른 효과의 동사·출처·인쇄한 개체(OQ-111 (4), B3-3 (가)). 고르기 단계는 그 좌석에게만 보이는 사건 `effect_picked`를 낸다; 공개
  사건은 길이 끝나 온 행동이 적용될 때 지금처럼 나온다.
- **엔진:** `legal_actions`는 지금 목록을 만든 뒤(`effect_pick`을 뺀 상태로) 제시층을 거친다; `apply`의 합법 확인은 제시한 목록으로,
  적용은 제시층이 고르기 단계(context만 바뀜)와 온 행동 적용으로 나눈다. 온 행동 목록은 `whole_actions`로 따로 낼 수 있다(AI·화면·
  테스트 도우미가 쓴다).

**AI.** B1의 `PlacementMemory`를 넓힌다: 휴리스틱·앱 AI·rollout은 효과 단계의 결정에서 온 행동(대상까지 정해진 것)을 보고 고르고,
고른 온 행동의 남은 줄은 기억했다가 묻지 않고 둔다. 그래서 무작위 동점 처리가 온 행동 하나에 한 번이고, 판이 지금과 수순까지 같다.
무작위 AI와 망은 줄을 그대로 고른다.

**codec·행동 모양.** 효과 줄 template은 출처별로 인쇄한 개체 × (동사, 아이콘)을 내용에서 센다(카드는 카드 종류의 Agent 칸, 칸은
보드의 칸 아이콘, 지도자·Tech·계약은 그 목록); 대상 줄 template은 대상 종류마다 한 벌(지금 출처마다 따로 있던 폐기 366행 × 여러 벌이
`choose_personal_card` 한 벌로). 옛 id의 template은 그 id를 내는 frame이 모두 넘어간 뒤(B3d 끝) 지운다. `action_shapes`에 새 줄의
모양(동사, 출처는 인자, 대상)을 더한다.

**기보·같음 확인.** 다리 하나(`effect_steps`)가 기록된 온 행동 한 수를 그 길의 줄들로 바꾼다(B1 `agent_card_pick`과 같은 방식, 표에서
만든다). 같음 확인은 정해진 차이로 옛 한 수 = 새 여러 수, 고르기 단계의 사건·보기 칸은 정돈.

**테스트.** 온 행동을 곧바로 적용하던 테스트는 도우미 `apply_whole(engine, state, action)`(길의 줄을 차례로 적용; B1의
`apply_placement`를 넓힘)과 `whole_actions(engine, state, player)`(목록 비교)로 옮긴다. 테스트 쪽 등장: `resolve_board_effect` 760,
`resolve_agent_card_effect` 406 등 — 기계적인 옮기기는 에이전트에 나눠 맡긴다. 새 테스트: 고르기 중엔 그 효과의 대상만·턴 종료 없음,
대상 하나여도 열림, 다른 좌석의 보기·관측에 고른 효과가 없음, 되돌리기, 접합 두 칸의 같은 효과가 `box`로 갈림.

### B3a 구현 (브랜치 `stage-b`, codec v150 · 관측 v33 그대로)

설계에서 바뀐 것과 구현하며 정한 것:

- **표(`rules/effect_steps.STEP_SPECS`)** — Agent 효과 frame의 온 행동 74종. 효과 줄의 `icon`은 인쇄된 아이콘 열쇠(보드 칸의
  `board_icons`, Agent 칸의 `icons`)이고, 같은 아이콘의 갈래가 같은 동사를 쓰면 `option`으로 가른다(Sietch Tabr의 셋, Arrakis Revolt의
  둘, 지도자 인장의 지불 셋, Reverend Mother Jessica의 반복 지불). 대상 값을 id가 정하는 것은 고정 대상(`recall_conflict_*`는
  `choose_space(space_id="conflict")`), 빈 값은 대상이 아니다(Scouts 임무의 `choice=""`). **인장 칸의 효과는 지도자가 인쇄했다**:
  Signet Ring 칸의 줄은 `source=leader, printed=<지도자 면>`(Reverend Mother Jessica는 그 면). 차례 줄(연구 보너스·선택 폐기·트리거
  뽑기·황제 트랙 Spy·Commander 모집·소위원회)은 차례·Reveal frame과 함께 B3c에서, 거절·빈 확인은 B3d에서 옮긴다(지금은 그대로).
- **엔진:** `legal_actions` = 제시층(`present`) ∘ 규칙의 목록(`_rules_actions`, 고르기를 뺀 상태); `_apply_legal`은 고르기 단계면 context만
  바꾸고(차례 시작 끝·자동 진행을 돌리지 않음), 길이 끝나면 온 행동을 지금처럼 적용. `whole_actions`(새 공개 메서드), `completed_whole`.
  같은 줄이 두 온 행동을 가리키거나 한 길이 다른 길 중간에서 끝나면 오류(소크가 잡는다).
- **보는 사람:** 고르기는 그 frame의 context(`effect_pick`, JSON); 보기 `private.effect_pick`; 관측 v33 `private_effect_pick_verb·source·
  card·box·targets`(엔티티 망은 카드 칸을 엔티티로); 사건 `effect_picked`는 그 좌석에게만; 서버 로그는 고르기 단계를 봉인한다.
  (2026-10-20 B3c-1 리뷰 뒤: 마지막 전에 고른 대상도 정체로 — `private_effect_pick_intrigue·faction·post·tech·battle`, 두 번째로 고른
  진영은 `private_effect_pick_second_faction`(Captured Mentat의 잃는 진영 → 얻는 진영 순서가 넘길 Alliance를 정한다); 5,440 → 5,593열.)
- **AI:** `PlacementMemory`가 효과 단계 결정을 온 행동으로 보여 주고(규칙의 순서 그대로) 고른 온 행동의 남은 줄을 기억한다 —
  휴리스틱·앱 AI 판이 효과 단계를 끈 엔진과 수순까지 같다(전 옵션 휴리스틱 4판·앱 AI 3판 대조, 다른 것은 고르기 사건뿐). 온
  행동 목록을 넘기는 호출자(온 행동을 `apply_whole`로 두는 걸음)에게는 온 행동 그대로 고른다. rollout AI는 후보를 `apply_whole`로
  적용한다. **망 AI(`NetworkAgent`)에 `choose_action_with_state`를 더했다:** 학습 안 된 행만 있는 결정을 휴리스틱에 넘길 때 상태를
  함께 넘겨, 대체 휴리스틱이 줄 이름 대신 온 행동을 보고 고른다(B1의 카드 고르기도 같은 덕을 본다). 탐색 AI는 효과 순서·학습 안 된
  결정을 이 길로 넘긴다.
- **codec:** 옛 template에서 만든다 — 대상 줄은 옛 template의 인자로, 효과 줄은 인쇄한 개체별로: 카드는 그 카드의 Agent 칸 기록이
  낼 수 있는 (동사, 아이콘)만(기록의 조각·아이콘·hook에서 읽음; 기록 없이 코드로 푸는 칸과 Ghola는 무엇이든; 모든 카드에 Urgent
  Shigawire의 더한 뽑기), 칸은 보드의 칸 전부, 지도자 줄은 그 행동을 가진 지도자 면만(`_LEADER_ROW_FACES`), 인장 칸의 일반 해결은
  모든 지도자 면. 효과 단계로만 나오는 옛 id의 template은 뺐다(`OFFERED_AS_WHOLE`가 다른 frame이 아직 그대로 내는 id). 카탈로그 기본
  2,931 → 3,103행, 옵션 전부 10,460 → 9,723행. `action_shapes`: 새 `Source.REF`·`Target.EFFECT`, 효과 줄 동사 23개·대상 줄 13종(`choose_skill`은 Commander 기술 frame의 옛 id와 같은 모양).
- **서버·화면:** 결정 payload는 온 행동 목록(화면·표시 도우미·미리보기는 그대로), `apply_action`은 고른 온 행동의 줄을 차례로
  적용, 되돌리기는 고르기 중간에 멈추지 않는다. 로그는 길이 끝난 단계에 그 온 행동을 보이고 고르기 단계는 `pick`으로 표시해 화면
  로그가 건너뛴다. 다 끝난 판 다시보기의 단계 이름표도 로그처럼(끝난 단계는 온 행동, 고르기 단계는 `pick`) 나오고, 커서는 고르기
  단계 바로 뒤에 멈추지 않는다(앞으로 가면 그 효과의 끝으로, 뒤로 가면 효과 앞으로).
- **기보·같음 확인·문제집:** 다리 `effect_step`·`effect_last_step`; 정해진 차이 `effect_steps`(옛 한 수 = 길, 고르기 사건·빈 보기 칸
  정돈, 효과 단계 결정의 줄·화면 메타는 온 행동에서); 문제집은 온 행동으로 감지·지문을 잡고, 답은 줄을 이어 고른 온 행동으로 채점,
  tip census도 온 행동 하나에 한 걸음. **옛 기록의 다리들은 옛 엔진의 온 행동으로 생각한다:** 다리 안의 "합법" 검사는
  `whole_actions`로, 다리가 답한 온 행동은 그 줄들로 펼쳐 그 다리 이름으로 기록(`_apply_answer`), `follows` 다리에는 마지막 효과
  단계가 끝낸 온 행동을 넘기고, 접합 둘째 칸의 `box=1` 붙이기는 칸 행동에만(에이전트가 기록 고정본 9개의 갈림으로 찾음).
  사람 판 문제는 B1처럼 두 수의 길이 처음 갈리는 단계에서 묻는다(다른 효과면 효과 고르기 앞, 같은 효과에 다른 대상이면 대상
  단계; 손으로 고른 AI 실수의 정답이 이 엔진의 줄이면 그 줄이 나오는 단계).
- **측정:** 같음 확인 200판 같음(192,672걸음, 온 행동 38,947번이 길로); 기보 2,000판 같음 1,574 · 일시 차이 425 · 갈림 1(B2와 같음,
  새 다리 `effect_last_step` 449,200걸음·`effect_step` 76,207걸음); 휴리스틱·앱 AI·rollout 판은 효과 단계를 끈 엔진과 수순 동일;
  소크 1,400판(전 옵션 무작위 600판은 매 결정의 모든 줄을 적용·codec 왕복) 실패 0; 휴리스틱 판 시간 +14%(규칙 목록을 상태별
  한 번만 만드는 캐시 뒤; 캐시 전 +35%); 문제집 tips-v1 90개 재채굴; 사람 판 문제 279/285·AI 실수 3/3(HEAD와 같은 집합); E2E 68개
  (`log_words`의 무작위 판 시드 197·Scouts 3·5로 다시 고름).
- **독립 리뷰에서 고친 것:** 사람 판 문제집이 효과 고르기 중간 상태에서 문제를 물어 260/285만 풀렸다 → 위의 "처음 갈리는 단계";
  옛 망(codec v150 이전 파일)은 효과 단계에서 모든 줄이 학습 안 된 행이라 tips 점수가 0.5로 고정 → 학습 안 된 행만 있으면 확률
  점수를 내지 않는다(사람 판 문제집과 같은 가드); 경로가 있는 온 행동을 한 번에 적용하는 길을 막고, `first_step`은 열린 고르기와
  맞지 않는 온 행동이면 오류. 다른 좌석의 로그에는 고르기 단계가 동사까지 가린 표지(`effect_picked`)로만 보인다(서버 테스트
  에이전트 지적). "모두 되돌리기" 버튼 숫자는 걸음이 아니라 수(배치·효과+대상이 한 수)로 센다.
- **남긴 것:** 옛 망을 새 줄로 옮길 때 효과 줄을 옛 온 행동 행에서 시작하게 하는 일은 하지 않았다(B 끝에 재학습, B1과 같음).
  Holy War 창의 옛 `lose_unit`과 Piter의 비용 효과 줄 `lose_unit`이 id를 함께 써 행동 모양 표가 하나만 말한다(B3d에서 Holy War 창을
  대상 줄로 옮길 때 정리). 사람 판 진단 도구
  (`records.saves.human_decisions`)는 기록된 걸음(마지막 단계)만 결정으로 내므로, 다시 채굴할 때는 효과·카드 고르기도 결정으로
  내게 고쳐야 한다(B1부터 같은 한계).

### B3b 세부 설계 (2026-10-20)

**차례 안에서 완수한 계약의 보상 = 차례의 줄(B3-4 (가), OQ-112 (4)).** 지금(B2)은 완수한 자리에 보상 창(`contract_reward_icons`)을
쌓는다. 계약을 그 주인의 차례 안에서(Agent 차례·Reveal·차례 frame이 열려 있을 때) 완수하면, 창 대신 보상의 아이콘마다 차례 줄
(`turn_rows`, 새 종류 `contract_icon`: 출처 = 완수의 사건 출처, 값 = 계약과 아이콘)을 그 차례 frame에 둔다. 차례 줄이므로 그 frame의
다른 효과와 함께 어느 순서로든 고르고(효과 단계: `gain`·`recruit`·`gain_influence`·`draw`·`take`·`place_spy`·`recall_agent`,
`source=contract`, `printed`=계약, `icon`=아이콘), 모두 의무라 다 받기 전엔 턴 종료가 막힌다(`turn_rows.holds_the_end`). 고르는
아이콘(계약·Spy·Agent 소환)은 지금처럼 제 frame을 연다. Agent 소환의 "이번 차례에 보낸 Agent 말고"[Main p. 20]는 줄을 받을 때 그 차례의
Agent 칸·Conflict 이동(OQ-068)으로 판단한다(줄은 그 Agent 차례 안에서만 받으므로 같다). CHOAM Transports의 카드는 지금처럼 완수
직후(OQ-106 13, A 순서). 차례 밖의 완수(Conflict 보상 중의 동맹 계약, Combat의 책략 등)는 지금처럼 창이다. 창을 효과 frame 위로
들어 옮기던 우회(`_lift_contract_windows`, Solari 구매 중 Acquire 계약)와 황제 트랙 Spy·Friends Everywhere가 창 밑에서 기다리던 예외는
차례 안에선 필요 없어진다(줄끼리는 순서가 자유).

- **AI·기보·같음 확인:** 휴리스틱·앱 AI·rollout은 옛 엔진이 하던 대로 완수 직후 아이콘을 옛 고정 순서로 받는다
  (`agents.engine_order`가 차례 줄의 계약 아이콘도 답함 — 효과 단계 frame이면 그 첫 단계로). 옛 기록은 B2의 다리처럼 완수 직후 줄을
  옛 순서로 받는 다리로, 같음 확인은 정해진 차이로 맞춘다. 창이 다른 frame 위에 쌓이던 경우(카드가 Spy도 놓는 구매의 획득 계약 등)는
  줄이 그 frame이 닫힌 뒤에 나오므로 순서가 달라진다 — 정해진 차이로 적는다.

**Reveal frame을 효과 → 대상으로(B3b-2).** `EFFECT_STEP_FRAMES`에 `reveal`을 더한다. 조사는 tmp(사실표)에, 대응은 이렇다:

- **구매**(`source=purchase`, `printed`=시장): `acquire_imperium`(Imperium Row)·`acquire_reserve`(Reserve)·`acquire_tleilaxu`(Tleilaxu Row,
  `to_deck_top`은 마지막 줄에)·`acquire_reclaimed_forces`(`choice`가 대상)·`acquire_manipulated_imperium`(그 좌석이 따로 둔 카드) — 시장마다
  효과 줄 `acquire` 하나, 대상 줄 `choose_imperium_card`·`choose_reserve_card`·`choose_tleilaxu_card`(새 종류)·`choose_option`.
- **Reveal 선택**(`source=reveal_card`, `printed`=카드 종류 — 지금의 `source` 인자 그대로, 한 카드만 내는 id는 그 카드를 고정값으로):
  Spy 놓기·회수(둘 회수는 첫 초소 → 둘째 초소), 폐기, 영향력(교환은 잃을 진영 → 얻을 진영 → 동맹 받을 좌석), 지불, 병력 이동·후퇴(수량은
  그 줄에), Corrinth City·Delivery Logistics·Desert Power·계약 Reveal의 갈래, Engineered Miracle의 Row 카드 획득. 같은 카드 두 장이 같은
  선택을 기다리면 줄 하나(먼저 낸 장부터, 지금처럼).
- **지도자·기술·Tech:** Lady Amber의 후퇴 둘(`option`), Feyd의 Spy 회수, Commander 기술 폐기(`printed`=기술), Forbidden Weapons(전투력 +
  영향력 잃기 → 진영, 또는 Tech 폐기), Panopticon의 Spy(초소는 열리는 Spy frame에서).
- **그대로 두는 것:** Reveal의 모은 이득(`gain_reveal_resources` 등 — B3e에서 카드별 기록 줄로 바꿀 때), 거절·빈 확인(B3d), 차례 줄
  (연구 보너스·선택 폐기·트리거 뽑기·트랙 Spy·Commander 모집·소위원회, B3c), 병력 배치·책략·표본·Family Atomics·턴 종료. Reveal 선택이
  제 frame(`reveal_choice`, 회수 먼저 뒤에)에서 나오는 행은 B3d(한 효과의 frame은 대상 줄만)까지 그대로라, 그 id들은 codec에 옛
  template도 남긴다(`OFFERED_AS_WHOLE`).

### B3b-1 구현 (브랜치 `stage-b`, codec v150 · 관측 v33 그대로)

- **엔진:** 계약을 완수하는 모든 자리(칸·카드 효과·획득·Immediate·책략 폐기 Immediate·동맹 계약)가 보상을 `_await_contract_reward`로
  넘긴다 — 주인의 차례 frame이 열려 있고(Scouts 줄 안이 아니고) 판이 끝나지 않았으면 아이콘마다 차례 줄 `contract_icon`(값 =
  `계약|아이콘`), 아니면 지금처럼 창. 줄은
  `resolve_contract_reward_icon(contract_id, effect)`(창의 줄은 `effect`만)로 차례·Agent 효과·Reveal frame이 맨 위일 때 나오고,
  Agent 효과 frame에선 효과 줄(`gain`·`recruit`·`place_spy`…, `source=contract`, `printed`=계약, `icon`=아이콘)이다. 모두 의무라
  `turn_rows.holds_the_end`가 턴 종료를 막는다(서버의 턴 종료 거울도 같은 함수). 한 계약의 여러 아이콘·여러 계약의 아이콘·차례의 다른
  효과가 어느 순서로든 섞인다. 사건 id(`<출처>:reward_icon:<남은 수>`)와 지급 함수(`_pay_contract_icon`)는 창과 같다.
  **Agent 소환 아이콘의 제외는 줄을 받을 때 판단한다**("not the Agent you sent during this turn" `[Main p. 20]`, OQ-068): 줄 사이에
  Into the Fray가 그 차례의 Agent를 Conflict로 옮길 수 있고, 차례 frame(Agent를 보내기 전)에서 완수한 줄은 Agent 효과 frame으로
  넘어가므로(`turn_rows.carried`) 완수 때 고정하면 방금 보낸 Agent를 데려올 수 있다(`_turn_agent_exclusion`, 회귀 테스트
  `test_graft.py::test_a_contract_recall_row_taken_after_into_the_fray_still_excludes_it`). 맨 차례 frame에서 완수한 줄은 Agent
  카드 고르기·Reveal과 함께 나오고 그 frame으로 넘어간다(연구 보너스 줄과 같다). 턴 종료 누름의 지불이 계약을 완수하면 줄이
  남으므로 누름이 바로 차례를 다시 연다(빚진 뽑기와 같다; 예전엔 창의 병력 줄 뒤에 다시 열렸다).
- **창을 위로 옮기던 우회 정리:** Agent 차례의 Solari 구매(`_acquire_*_to_hand_with_solari`)가 창을 떼었다 다시 얹던
  `_lift_contract_windows`는 차례 안이라 창이 생기지 않으므로 "창이 없음"을 확인하는 `_contract_rows_only`로 바꿨다.
  `advance_after_effect`는 frame에 지금 쌓인 차례 줄(`PENDING_KEY`)을 지킨다 — 효과가 해결되는 동안 완수된 계약의 줄을, 그 전에 읽은
  context가 덮어쓰지 않게(Solari 구매·CHOAM Demands 길). 황제 트랙 Spy·Friends Everywhere가 창 밑에서 기다리던 예외는 차례 밖 창에
  그대로 쓰인다(차례 안에선 창이 없다). **Scouts 줄은 맨 위가 아니어도 줄이다**(`turn_rows.waits_on_turn`): 차례 frame 위 어디에든
  Scouts frame이 있으면 창 — CHOAM Management의 두 장 받는 시장처럼 줄이 연 frame이 맨 위일 때 Immediate 타일의 보상이 고르는
  순서에 따라 줄·창으로 갈리던 것(독립 리뷰가 찾음)을 고쳤고, 정리-2b의 연구·폐기 줄도 같은 판정을 쓴다("turn 안의 Scouts
  줄"에서는 창, OQ-095 (2)).
- **다른 frame이 위에 있을 때:** 완수가 주인의 다른 frame 위에서 일어나면(획득 Spy 칸, Research 방향, 두 장 받는 계약 시장, 책략의
  선택) 줄은 그 frame이 닫힌 뒤 나온다 — 옛 엔진은 창을 그 위에 얹어 먼저 받게 했다. 정해진 차이다.
- **AI·기보·같음 확인:** `agents.engine_order`가 차례 줄의 계약 아이콘도 옛 순서로 답한다(`legacy_contract_icon_row`: 가장 먼저 완수한
  계약, 그 안은 창의 옛 순서; 효과 단계 frame이면 그 줄로). 옛 기록은 B2 다리(`combat_reward_icon`, `_follow`)가 줄을 같은 순서로
  받고, 새 다리 `contract_frame_first`(codec v150 이전)가 위 frame의 다음 고르기를 먼저 가져온다(옛 기록은 그 사이에 보상의
  섞기를 적었다). 같음 확인 `combat_reward_icons` 규칙의 답도 `engine_order_answer`로.
- **행동 모양:** `resolve_contract_reward_icon`에 tag `contract_id`(`Tag.CONTRACT`: 여러 계약의 아이콘 중 어느 것). codec은 계약 ×
  아이콘마다 온 template과 그 효과 줄(CHOAM 23 + 23, Bloodlines까지 37 + 37).
- **측정:** 같음 확인 200판 같음(같음 확인 도구가 CHOAM Transports 카드 뒤의 기회 걸음을 효과 단계 규칙에 넘기던 것 고침); 기보 2,000판
  같음 1,568 · 일시 차이 431 · 갈림 1(B2·B3a의 그 하나; 두 장 받는 시장 사이의 Immediate 1판은 새 다리로 일시 차이; Scouts 줄
  판정을 고친 뒤 8판이 일시 차이에서 같음으로); 휴리스틱
  30판·앱 AI 15판이 이전 커밋과 최종 상태·사건 종류·수 개수까지 같음; 계약 완수 1,425번(무작위 250판·휴리스틱 120판)의 아이콘이
  모두 지급(차례 줄로 1,354번, 창으로 71번); 관측 고정 digest 셋(choam·everything·scouts)은 첫 차례 안 완수 바로 다음 결정에서만
  갈려 다시 고정; 문제집 tips-v1 90곳 다시 채굴(같은 국면·지문, 선택 번호만 바뀜).

### B3b-2 구현 (브랜치 `stage-b`, codec v150 · 관측 v33 그대로)

- **표:** `EFFECT_STEP_FRAMES`에 Reveal frame. 구매는 시장마다 효과 줄 `acquire(source=purchase, printed=<시장>)` 하나 — 시장 이름은
  `imperium_row`·`set_aside`(Manipulate로 따로 둔 카드)·`reserve`·`tleilaxu_row`(Reclaimed Forces 포함, 그 갈래는 `choose_option`) —
  다음 대상 줄 `choose_imperium_card`·`choose_reserve_card`·`choose_tleilaxu_card`(새 종류, `to_deck_top`은 그 줄에). Reveal 선택은
  `source=reveal_card`, `printed`=카드 종류: `source` 인자가 있는 id는 그 값, 한 카드만 내는 id는 그 카드를 표에 고정(`"=<카드>"`;
  Undercover Asset·In High Places·Captured Mentat·Spacing Guild's Favor·For Humanity·Tleilaxu Surgeon·Corrinth City·Delivery
  Logistics·Desert Power·Engineered Miracle — 카드의 Reveal 선택 표와 맞는지 테스트가 지킨다). 동사는 행동 모양 표의 것
  (`place_spy`·`recall_spy`·`trash`·`gain_influence`·`exchange_influence`·`pay`·`lose_influence`·`retreat`·`deploy`·`lose_unit`·`gain`·
  `take`·`keep`·`acquire`), 둘 회수는 첫 초소 → 둘째 초소, 교환·영향력 잃기는 진영 → (잃을 진영 → 얻을 진영) → 동맹 받을 좌석
  (`choose_seat`), 유닛 섞임(`commanders`·`zones`)은 효과 줄에. 지도자: Lady Amber의 후퇴 둘(`option` troop/commander), Feyd의 Spy 회수;
  Commander 기술 폐기는 `source=commander, printed=<기술>`; Forbidden Weapons는 `choose(option=strength)` → 진영 → 좌석 또는
  `choose(option=trash)`, Panopticon은 `place_spy(printed=panopticon)`. Reveal 선택 id는 카드 자신의 선택 frame(`reveal_choice`)이 아직
  온 행동으로 내므로 codec에 옛 template도 남는다(`OFFERED_AS_WHOLE`); 구매·지도자·기술·Tech 줄은 Reveal에만 나와 옛 template이
  빠진다. 거절(`decline_reveal_sandworm`·`decline_reveal_spy_recall`)과 모은 이득(`gain_reveal_resources` 등)은 그대로(B3d·B3e).
- **codec:** 기본 2,985행(−146 온 template, +28 줄; 대상 줄은 B3a에서 이미 있던 것), CHOAM −154/+32, Bloodlines까지 −222/+53, 옵션 전부
  9,855 → 9,603. `action_shapes`: 효과 줄 동사 `exchange_influence`·`lose_influence`·`keep`, 대상 줄 `choose_tleilaxu_card`, 효과 줄
  인자 `zones`. 엔티티 망의 `printed` 힌트에 Skill(특징 digest 다시 고정); 시장 이름은 이름표.
- **기보:** 옛 기록의 Reveal 온 행동은 B3a의 다리(`effect_step`·`effect_last_step`)가 줄로 펼친다. 기록된 단계에 그 단계가 끝낸
  온 행동(`MigratedStep.whole`)과, v147 전 기록이면 그 온 행동에 카드를 붙인 다리(`reveal_source`·`reveal_source_by_order`, 처음 붙인
  대로; `MigratedStep.named_by`)를 함께 둔다 — 단계의 다리 이름은 `effect_last_step` 그대로라 문제집 도구가 효과의 마지막 단계를 찾는
  방식이 그대로다(독립 리뷰: 다리 이름을 이름 붙이기로 바꾼 첫 구현은 사람 판 문제 2곳을 잘못된 단계에서 물었다).
- **측정:** 같음 확인 200판 같음(온 행동 52,117번이 길로, B3b-1보다 Reveal 13,170번 더); 기보 2,000판 같음 1,568 · 일시 차이 431 ·
  갈림 1(B3b-1과 같음; 다리 `effect_last_step` 597,305걸음·`effect_step` 217,285걸음); 휴리스틱 20판·앱 AI 10판이 이전 커밋과
  최종 상태·사건이 같고 고르기 걸음만 늘었다; 소크 1,400판 실패 0; 관측 고정 digest 여섯은 첫 Reveal의 구매 여럿에서 갈려 다시
  고정; 문제집 tips-v1 다시 채굴(휴리스틱 82곳은 같은 국면·지문, 체크포인트 망이 캔 곳은 8 → 17로 99곳); E2E 다시보기 이동은
  고르기 걸음이 넘어가는 자리를 기다리고(`common.REVIEW_LANDING`), 시드를 다시 골랐다(탐색 좌석 40, `log_words` 3 · Scouts 1과 90).

### B3c 세부 설계 (2026-10-20)

사실표(tmp, `b3c/facts.md`: 420판, 결정 483,494번)를 바탕으로 범위를 다시 나눈다. **B3c = 여러 효과가 함께 기다리는 frame 중 남은 것과
차례 줄.** 한 효과를 위해 열린 frame(접합 상대 `choose_graft_partner`, 운항 카드 놓기·쓰기, Scouts 입찰·시장·임무, 책략 슬롯
`intrigue_choice`, 보상 창)은 효과 줄 없이 대상 줄만 내는 B3d의 방식이라 계획 표의 B3c에서 B3d로 옮긴다.

**B3c-1 — 카드 내기.** `EFFECT_STEP_FRAMES`에 차례 frame(`turn`), Combat 책략 창(`combat_intrigue`), Conflict 끝 책략 창
(`conflict_end_trigger`), Endgame 창(`endgame_intrigue`)을 더한다.

- **책략 내기**(계획 3c "`play(ref=책략)` → `choose_card` → `choose_option`"): `play_intrigue(card_id, option)` → 효과 줄
  `play(source=intrigue, printed=<창>)` → `choose_intrigue_card(card_id)` → `choose_option(option)`. 창은 그 frame이 정한다(차례·Agent
  효과·Reveal frame = `plot`, Combat = `combat`, Endgame = `endgame`; 이름표, 엔티티 아님). **갈래가 하나뿐이어도 갈래 단계를 연다**
  (OQ-111 (2), 2026-09-30 원칙 — 카드의 갈래는 카드에 인쇄된 별개의 효과다). 같은 카드 사본 둘은 카드 줄 둘(사본 id). 고른 카드는
  그 좌석만 안다(B3-3, 길 끝의 `intrigue_played`가 공개).
- **Conflict 끝 책략**(Harvest Cells): `play_conflict_end_intrigue(card_id)` → `play(source=intrigue, printed=conflict_end)` →
  `choose_intrigue_card` (갈래 없음: 그 창이 발동 갈래를 정한다).
- **차례 시작 카드**(Litany Against Fear): `play_turn_start_card(card_id)` → `play(source=turn, printed=turn_start)` →
  `choose_personal_card`.
- **Endgame 와일드**(계획 "카드 → 와일드 카드"): `match_endgame_wild_icon(matching_card_id, wild_card_id)` →
  `match(source=endgame, printed=wild_icon)` → `choose_conflict_card(card_id=맞출 카드)` → `choose_conflict_card(card_id=와일드 카드)`
  (새 대상 종류; Conflict·목표 카드).
- **그대로:** `reveal_turn`, B1의 카드·칸 고르기, 표본 반환·Family Atomics(가리킬 효과가 없는 차례 행동), 턴 종료·pass·거절·마침(B3d).
  차례 frame이 효과 단계 frame이 되므로 거기의 Tech 뒤집기·획득 아이콘·계약 줄도 효과 줄로 나오고, `flip_tech`는 온 행동으로 내는 frame이
  없어 codec에서 빠진다.

**B3c-2 세부 설계 (2026-10-20).** 아래 원래 메모를 조사(사실표 5절, 연구 칸 표, `optional_trash._take_turn_row`)로 정했다.

- **B3c-2a — 이름만(규칙 처리 그대로).** 연구 보너스는 셋 다 한 칸에만 인쇄돼 있다(`influence_any` c6r6, `trash_intrigue_for_card_and_intrigue`
  c7r3, `seven_solari_for_two_tleilaxu` c8r6): `choose_research_influence` → `gain_influence(source=research, printed=c6r6)` →
  `choose_faction`, `trash_intrigue_for_research_bonus` → `trash(source=research, printed=c7r3)` → `choose_intrigue_card`,
  `pay_research_bonus` → `pay(source=research, printed=c8r6)`. 연구 아이콘 `resolve_research_icon(effect)`은 `generate_specimens`/`advance`
  (`source=research`, `icon`=아이콘, `printed`=처리기가 집을 기다리는 효과의 연구 칸 — 같은 아이콘이 두 칸에서 함께 기다리면 결과가 같으므로
  결정 3대로 줄 하나, 지금처럼 새 것부터). Planetologist의 Intrigue `draw_planetologist_intrigue`는 그 능력을 가진 지도자가 인쇄했다
  (`draw(source=leader, printed=<지도자 면>, icon=intrigue)`). 이 id들은 창(`research_bonus`·`optional_trash`)도 온 행동으로 내므로 codec에
  옛 template이 남는다(B3d까지). 빚진 뽑기(`draw_owed_*`)와 황제 트랙 Spy(`place_track_spy`)는 대상 없는 "그 자체가 첫 단계"인 행이라
  그대로 둔다(B3d의 남은 출처별 이름에서).
- **B3c-2b — 선택 폐기가 쓰는 폐기 효과.** 선택 폐기 행 `trash_optional_card(card_id)`는 어느 폐기 아이콘을 쓰는지 말하지 않고, 처리기가
  "그 카드 자신의 칸에서 온 폐기를 먼저, 아니면 다른 카드 칸이 아닌 것 중 새 것, 아니면 새 것"으로 대신 고른다. 어느 아이콘으로 폐기하느냐는
  결과를 바꾼다 — 카드가 **자기 칸의 아이콘으로** 자신을 폐기하면 남은 아이콘이 계속 지급되고, 다른 효과로 폐기되면 아직 발동하지 않은
  칸이 만료된다(OQ-022, 2026-10-12 보강). 원칙(OQ-027 "인쇄된 아이콘은 각각 독립된 효과, 소유자가 순서를 고른다", 결정 3)대로 효과 줄이
  폐기 아이콘을 인쇄한 개체(카드 칸·Tech·지도자·연구 칸)를 말하고, 좌석이 그 효과를 고른 뒤 카드를 고르며, 처리기는 고른 효과를 쓴다.
  행동에 그 효과의 자리(`source`·`printed`)를 더하는 엔진 변경이다. AI 좌석·옛 기록은 옛 처리기의 고르기를 그대로 따른다(옛 순서 답,
  기보 다리).

**B3c-2 — 차례 줄(원래 메모).** 지금 차례 줄의 행(`choose_research_influence`, `trash_intrigue_for_research_bonus`, `pay_research_bonus`,
`resolve_research_icon`, `trash_optional_card`, `draw_planetologist_intrigue`, 빚진 뽑기, 황제 트랙 Spy, 소위원회)은 어느 기다리는 효과를
푸는지 말하지 않고, 처리기가 가장 오래된 것(연구 보너스·빚진 뽑기·트랙 Spy)이나 가장 새 것(연구 아이콘·선택 폐기 — 자기 칸의 것
먼저·Planetologist)을 고른다. 결정 3(인쇄한 것으로 가리킨다)대로라면 효과 줄이 그 효과를 낸 개체를 말해야 하고(연구 칸, 폐기 아이콘을
낸 카드·Tech·칸, Planetologist가 바꾼 칸, 뽑기를 빚게 한 것), 처리기도 고른 효과를 써야 한다 — 행동에 기다리는 효과의 자리를 더하는
엔진 변경이라 B3c-1 뒤에 따로 조사해 정한다(출처 문자열에서 개체를 읽는 규칙, 같은 종류 둘이 함께 기다릴 때, 처리기의 "자기 칸 먼저"가
규칙상 필요한지).

### B3c-1 구현 (브랜치 `stage-b`, codec v150 · 관측 v33 그대로)

- **표:** 설계대로 `play_intrigue`(창은 그 frame에서: `Printed.INTRIGUE_WINDOW` — 차례·Agent 효과·Reveal frame `plot`, Combat
  `combat`, Endgame `endgame`), `play_conflict_end_intrigue`, `play_turn_start_card`, `match_endgame_wild_icon`(새 대상 종류
  `choose_conflict_card`). `EFFECT_STEP_FRAMES`에 차례 frame·Combat·Conflict 끝·Endgame 창. `flip_tech`는 온 행동으로 내는 frame이
  없어 `OFFERED_AS_WHOLE`에서 빠졌다. 고르기 걸음은 차례 시작을 닫지 않는다(`_apply_legal`이 고르기 단계를 차례 시작 끝내기 전에
  돌려준다 — Withdrawn·Litany의 시작 전용 갈래가 고르는 도중에 사라지지 않는다).
- **AI:** `PlacementMemory`가 차례 frame의 B1 카드 고르기를 배치로 보일 때 함께 나오는 나머지 줄도 온 행동으로 보인다(빠뜨렸을 때
  앱 AI가 차례 frame의 `play` 줄을 몰라 무작위로 답했다). 앱 AI가 책략을 낼 때 남기는 "같은 판단" 표지(`intrigue_at`)는 고르기
  사건(`effect_picked`)을 뺀 사건 수로 센다(`app_ai.windows.intrigue.event_stamp`) — 카드·갈래 고르기 사건이 `intrigue_played` 앞에
  끼어 표지가 어긋났다. 탐색 AI의 "혼자 앞설 때 전투력만 더하는 책략은 아낀다"(`holds_combat_lead`)는 줄 뒤의 온 행동이 모두 그런
  책략인 줄(창의 `play`, 카드, 갈래)을 거른다.
- **codec:** 기본 2,938행(−73: `play_intrigue`·와일드 맞추기 온 template, +26: `play`·`match` 효과 줄과 Conflict·목표 카드 대상 줄),
  CHOAM −78/+26, Bloodlines까지 −159/+29, 옵션 전부 9,603 → 9,445. `action_shapes`: 효과 줄 동사 `play`·`match`, 대상 줄
  `choose_conflict_card`. 엔티티 망: `choose_conflict_card(card_id)`는 battle·Conflict 카드로 읽고(특징 digest 다시 고정), 창 이름은
  이름표.
- **도구:** 같음 확인의 B1 규칙이 차례 frame의 행을 효과 단계 표시(`present`)를 거쳐 비교하고 화면 정보를 온 행동으로 읽는다(서버처럼;
  안 하면 200판 모두 첫 차례 frame에서 달랐다).
- **측정:** 같음 확인 200판 같음(온 행동 57,629번이 길로, B3b-2보다 5,512번 더); 기보 2,000판 같음 1,568 · 일시 차이 431 · 갈림 1(B3b와
  같음); 휴리스틱 20판·앱 AI 10판이 이전 커밋과 최종 상태·사건이 같음(위 두 AI 수정 뒤); 소크 1,400판 실패 0; 관측 고정 digest 여섯은 첫
  책략 내기에서 갈려 다시 고정; 문제집 tips-v1 다시 채굴(휴리스틱 82곳 같음, 체크포인트 망 몫만 바뀌어 101곳); 무작위 걸음 시드 다시 고름
  (되돌리기 3, 턴 종료 7·3, 탐색 좌석 기존 그대로, `log_words` 283 · Scouts 2와 209); E2E 다시보기 이동(`deck_piles`)과 `unavailable`의
  내장 조각을 효과 단계에 맞춤.

### B3c-2a 구현 (브랜치 `stage-b`, codec v150 · 관측 v33 그대로)

- **표:** 설계대로 `choose_research_influence` → `gain_influence(source=research, printed=c6r6)` → `choose_faction`,
  `trash_intrigue_for_research_bonus` → `trash(source=research, printed=c7r3)` → `choose_intrigue_card`, `pay_research_bonus` →
  `pay(source=research, printed=c8r6)`, `resolve_research_icon(effect)` → `generate_specimens`/`advance`(`icon`=아이콘; 새 규칙
  `Printed.RESEARCH_SPACE` — 연구 창이면 창의 칸, 차례 frame이면 그 아이콘을 기다리는 가장 새 항목의 칸, `apply_research_icon`이 집는
  그것), `draw_planetologist_intrigue` → `draw(source=leader, printed=liet_kynes, icon=intrigue)`. 다섯 id 모두 창(`research_bonus`,
  `optional_trash`)이 온 행동으로도 내므로 `OFFERED_AS_WHOLE`에 남는다. 차례에서 연구 아이콘 행이 될 수 있는 칸은
  `immortality.research_icon_spaces`(표본 c3r3·c3r5·c7r5, 틀레이락스 c3r5 — 쌍의 선택 폐기는 자기 행, c7r3의 보상은 빚진 뽑기).
- **기보:** 주인의 차례가 위에 올 때까지 붙잡아 둔 옛 창의 걸음(`turn_row_held`)이 그 차례 frame에서 효과 먼저로 나오면 그 걸음들로
  옮긴다 — 고르기는 `effect_step`, 마지막 걸음은 `turn_row_held`로 붙잡힌 온 행동을 끝낸다(`MigratedStep.whole`). 문제집 도구는
  `effect_last_step` 대신 "온 행동을 끝내는 걸음"(`whole`이 있는 걸음)을 읽는다.
- **codec:** 기본 그대로 2,938행(이 행들은 Immortality에만), Immortality 5,088 → 5,095(`generate_specimens` 셋,
  `advance`·`gain_influence`·`trash`·`pay` 하나씩), 옵션 전부 9,475 → 9,482. Planetologist의 `draw` 행은 Signet 상자 줄과 같은 행이라
  이미 있었다. `action_shapes`: 효과 줄 동사 `generate_specimens`. 엔티티 망: `printed`가 연구 칸도 읽는다(특징 digest 다시 고정).
- **측정:** 같음 확인 200판 같음; 기보 2,000판 같음 1,568 · 일시 차이 431 · 갈림 1(그대로); 휴리스틱 20판·앱 AI 10판이 이전 커밋과
  최종 상태·사건이 같음(고르기 걸음만 늘어남); 소크 900판 실패 0; 문제집 tips-v1 다시 채굴(휴리스틱 82곳 같은 국면 — 24곳은 앞선
  고르기 걸음만큼 선택 기록이 길어짐, 체크포인트 망 몫 19 → 23곳, 모두 105곳).

## 4. 위험

- `agent_turn`의 중간 상태는 숨은 정보·되돌리기·한 번 누르는 턴 종료·탐색 AI·관측 인코딩에 모두 닿는다 — 결정 2의 규칙을 OQ로
  먼저 적고 테스트로 지킨다.
- 이름 통일은 기보 다리가 행동마다 필요하다(옛 기록의 `trash_agent_card` → 새 `trash(source=agent_card, …)`). 일반 인자 다시
  쓰기는 금지된 관례이므로(기보 다리는 codec 문턱별, 행동별) 다리 표를 행동 모양 표에서 만든다.
- 토큰: 지난 카드 전수 대조가 예상의 2배 넘게 2,200만 토큰을 썼다. B3의 테스트 옮기기는 에이전트에 나누어 맡기고 묶음마다 확인한다.
