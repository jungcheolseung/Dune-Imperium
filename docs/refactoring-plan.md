# Intrigue 착수 전 리팩토링 계획

기준일: 2026-08-28

M6 Imperium 54종을 구현하는 동안 `rules/` 층이 "카드 수에 비례해 자라는"
구조가 됐다. Intrigue 44장을 같은 방식으로 얹으면 문제가 두 배가 되므로,
Intrigue 공통 경계를 만들기 전에 아래 항목을 정리한다. `core/`
(`state`, `engine`, `decisions`, `chance`, `replay`)는 견고하므로 손대지 않는다.

## 유지할 것

- 불변 `GameState`와 `RuleResult`, 전이 후 canonical hash·revision 검증
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
| A | frame `kind` 도입, `rules/frames.py` helper 집약, `_replace_player` 통합 | 낮음 | 진행 중 |
| B | registry 기반 dispatch, 화이트리스트 제거, legal 우선순위 명시화 | 낮음 | 대기 |
| C | effect DSL 설계 → Intrigue를 DSL로 구현 → Imperium 점진 이관 | 중간 | Intrigue와 함께 |

A와 B는 codec version 변경 없이 기존 테스트로 검증한다. 각 단계는 작은 커밋
단위로 나누고, 상태 hash·replay 테스트가 깨지지 않는지 매 커밋에서 확인한다.
