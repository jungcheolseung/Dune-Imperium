# Intrigue 착수 전 리팩토링 계획

기준일: 2026-08-28

M6 Imperium 54종을 구현하는 동안 `rules/` 층이 "카드 수에 비례해 자라는"
구조가 됐다. Intrigue 44장을 같은 방식으로 얹으면 문제가 두 배가 되므로,
Intrigue 공통 경계를 만들기 전에 아래 항목을 정리한다. `core/`
(`state`, `engine`, `decisions`, `chance`, `replay`)는 견고하므로 손대지 않는다.

## 유지할 것

- 불변 `GameState`와 `RuleResult`, 전이 후 revision 검증(입력 state 불변 hash 검증은
  `verify_input_immutability`로 켜는 디버그 가드; 기본 off)
- chance outcome을 기록·주입하는 replay 설계와 `__post_init__` 불변식
- decision stack 개념과 `_advance_automatic`의 phase 루프
- 573개 테스트: 리팩토링의 안전망으로 codec version을 바꾸지 않고 통과시킨다

## 문제 1. Dispatcher의 수동 등록 (`rules/engine.py`)

- `_apply_legal`이 약 90개 `action_id -> handler` dict를 호출마다 새로 만든다.
- `legal_actions`가 25개 `legal_*` 함수를 손으로 나열하고, "contract 먼저,
  다음 Agent effect context, 다음 Reveal context"라는 우선순위가 코드 순서에
  암묵적으로 박혀 있다.
- 새 결정 종류마다 engine.py 두 곳, codec catalog, 모듈의 legal/apply 쌍 총
  네 곳을 고쳐야 한다.
- `_agent_action_is_supported`가 `PersonalCardAgentEffect` 멤버 전체를
  화이트리스트로 중복 나열한다. 모든 멤버가 구현됐으므로 죽은 코드다.

해결: 각 rules 모듈이 `(action_ids, legal_fn, apply_fn)`을 registry에 등록하고,
engine은 top frame의 kind로 담당 모듈을 찾는다. 우선순위는 명시적 상수로 둔다.

## 문제 2. DecisionFrame에 종류가 없음 (`core/decisions.py`)

- frame 식별을 `frame_id` 문자열 패턴(`":combat_reward_optional:" in frame_id`)
  이나 `current_agent_effect_context`의 `ValueError`를 try/except로 잡는 방식에
  의존한다.
- context가 `tuple[tuple[str, ActionValue], ...]`의 untyped dict라 `_context_int`,
  `_frame_context_int`, `_effect_subject`, `_reveal_frame_context` 같은 파싱
  helper가 모듈마다 흩어져 있고 `_replace_player`는 네 모듈에 복붙돼 있다.

해결: `DecisionFrame.kind` 필드를 추가하고(직렬화·hash 호환 유지), `rules/frames.py`
에 frame 생성·조회·context 파싱·player 교체 helper를 모은다. Intrigue는 "Agent
turn 중 Plot", "Combat priority", "Endgame" 등 새 frame kind가 여러 개 필요하다.

## 문제 3. 효과가 typed DSL이 아니라 카드당 enum 멤버 (`content/uprising/types.py`)

- `PersonalCardAgentEffect`에 조건×비용×효과 조합이 이름으로 굳어진 멤버가 약
  55개 있다(`MAY_DISCARD_TWO_AND_PAY_FIVE_SOLARI_FOR_VP` 등).
- `resolve_agent_card_effect`가 이 enum을 530줄 if/elif로 분기하고 Reveal도 같은
  패턴이다. `implementation-plan.md` §3의 "typed effect + 소수 custom hook"
  방향과 실제 코드가 어긋난다.
- Intrigue 44장은 대부분 "자원/병력/Influence + 조건" 조합이라 정확히 DSL이
  필요한 영역이다.

해결: `Condition`(bond, influence 임계, alliance, maker space, spy recalled 등) ×
`Cost`(pay, discard, trash) × `Effect`(gain, draw, recruit, influence, place spy 등)를
조합하는 작은 AST와 범용 해석기. rewrite에 가까우므로 Intrigue에서 먼저 DSL로
설계·검증하고, 기존 Imperium enum 멤버는 단순한 것부터 점진 이관한다.

## 부수 항목

- `begin_reveal_turn`의 Persuasion/strength 계산이 100줄 inline 식이다. Plot
  Intrigue가 Reveal 수치를 건드리려면 분리된 계산 함수가 필요하다.
- `tests/unit/rules/test_agent_effects.py`(3,439줄)와 `test_reveal_turn.py`
  (1,790줄)는 카드·경계별 파일로 나눈다.
- `rules/engine.py` docstring이 여전히 "M3 vertical slice"를 언급한다.

## 진행 순서

| 단계 | 작업 | 위험 | 상태 |
| --- | --- | --- | --- |
| A | frame `kind` 도입, `rules/frames.py` helper 집약, `_replace_player` 통합 | 낮음 | 완료 (2026-08-28) |
| B | frame kind 표 기반 dispatch, 화이트리스트 제거, legal 우선순위 명시화 | 낮음 | 완료 (2026-08-28) |
| C | effect DSL 설계 → Intrigue를 DSL로 구현 → Imperium 점진 이관 | 중간 | 진행 중 (DSL·첫 Plot 묶음 2026-08-28) |

A와 B는 codec version 변경 없이 기존 테스트로 검증한다. 각 단계는 작은 커밋
단위로 나누고, 상태 hash·replay 테스트가 깨지지 않는지 매 커밋에서 확인한다.

## A·B 결과 (2026-08-28)

- `DecisionFrame.kind`가 필수 필드가 됐고 `rules/frames.py`의 `FrameKind`가 19개
  frame 종류를 열거한다. `frame_id` 문자열 검사와 context 키 존재 여부로 frame을
  식별하던 코드는 모두 `kind` 비교로 바뀌었다.
- `rules/engine.py`는 `LEGAL_ACTION_PROVIDERS[FrameKind]`와 `ACTION_HANDLERS[action_id]`
  두 표로만 dispatch한다. Agent-turn effect frame의 pending group 순서는
  `rules/agent_effect_frame.py`가 소유한다.
- 미구현 콘텐츠를 숨기는 규칙은 `UNIMPLEMENTED_AGENT_EFFECTS`(현재 `LEADER_SIGNET`)
  와 `board_effect_is_implemented`(현재 `secrets`, `desert_tactics`)로 명시했다.
  옛 화이트리스트는 구현된 Smuggler's Haven의 Agent 배치까지 숨기고 있었다.
- 옛 engine과 새 engine의 `legal_actions`를 random play 240게임(두 룰셋 × 120 seed,
  최대 5라운드, 약 16만 결정 지점)에서 비교해 위 Smuggler's Haven 차이 외에는
  동일함을 확인했다. 이 과정에서 Covert Operation이 마지막 pending group일 때
  turn이 끝나지 않는 기존 deadlock을 찾아 고쳤다.
- codec version은 v58 그대로이며 테스트는 577개다.

새 결정 경계를 추가할 때는 `FrameKind` 멤버, frame 생성 시 `kind`, 두 dispatch 표의
항목, codec catalog를 함께 추가한다. 다음은 C 단계(effect DSL)이며 Intrigue와 함께
진행한다.

## C 진행 (2026-08-28)

- `content/uprising/effect_dsl.py`에 Condition × Cost × Reward × Section × Option
  DSL을, `rules/effect_interpreter.py`에 범용 해석기를 두고 Intrigue Plot 14종을
  DSL만으로 전사했다. 선택이 필요한 primitive는 `INTRIGUE_CHOICE` frame의 슬롯으로
  순차 해결한다. 자세한 판정은
  [`implementation-audits/intrigue.md`](implementation-audits/intrigue.md)에 있다.
- `rules/intrigue_deck.py`가 Intrigue draw와 discard reshuffle의 공통 경계다.
  board effect·combat reward·card trigger의 기존 직접 draw 10곳은 아직 이 경계로
  옮기지 않았다(다음 정리 항목).
- Imperium enum 멤버의 DSL 이관은 Intrigue 전사가 끝난 뒤 단순한 것부터 시작한다.

## 코드 리뷰 후속 항목 (2026-08-28)

리뷰에서 나온 구조적 지적 중 아직 처리하지 않은 것:

- Intrigue draw 10곳(board effect, combat reward, card trigger, influence track
  bonus)을 `rules/intrigue_deck.draw_intrigue_cards`로 이관해 deck 고갈 시
  reshuffle chance frame을 공통 적용한다. 지금은 해당 경로가 빈 deck에서 draw를
  건너뛰거나 예외를 낸다.
- Reserve copy ID는 zone 스캔 대신 stack별 발급 카운터를 state에 두는 편이 안전하다.
- `ACTION_HANDLERS`를 `(FrameKind, action_id)`로 키잉하고 chance handler도 표로
  두면 `_apply_decline_combat_reward` 같은 kind 분기와 `_apply_chance`의 if/elif가
  사라진다.
- `PayResources`/`GainResources` 등 DSL 자원 record와 `rules/effects.py`·
  `board.ResourceCost`의 중복은 Imperium 효과를 DSL로 이관할 때 한쪽으로 합친다.
- Long Live the Fighters와 Corrinth City의 카드 전용 context flag는
  `INTRIGUE_CHOICE`와 같은 범용 슬롯 frame으로 대체할 수 있다.
- Covert Operation처럼 자식 frame을 쌓는 효과의 부모 frame 재개는 자식이 부모를
  들여다보는 대신 engine의 `_advance_automatic`에서 처리하는 편이 일반적이다.

