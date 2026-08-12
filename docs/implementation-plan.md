# Dune: Imperium - Uprising 구현 계획

상태: 초안 2 — R0 규칙 명세 완료, M0 시작 전

이 문서는 규칙 엔진부터 강화학습 AI와 사람용 플레이 인터페이스까지의 구현
순서와 각 단계의 완료 조건을 정의한다. 구현 중 새 규칙을 발견하더라도 핵심
계층의 책임을 유지하고, 마일스톤별 검증을 통과한 뒤 다음 범위로 진행한다.

## 1. 확정된 방향

- 대상 게임은 **Dune: Imperium - Uprising 4인 플레이**다.
- **CHOAM 모듈을 끈 기본 게임**을 첫 완성 범위로 한다. 공식
  룰북이 계약을 선택형 미니 확장으로 분류하기 때문이다. 계약, Shaddam, CHOAM
  전용 Imperium/Intrigue 카드는 기본 게임 완성 직후 `choam_module=True` 규칙
  설정으로 추가한다.
- Python 3.14와 uv를 사용한다.
- 기존 `dune/` 코드는 참고 자료로만 두고 새 구조와의 호환성을 요구하지 않는다.
- 규칙 코어는 UI와 RL 라이브러리에 의존하지 않는 네이티브 Python 엔진으로
  만든다.
- 공식 Dire Wolf Digital 룰북, 보충 자료, FAQ를 규칙 판정의 우선 출처로
  사용한다. Dune Cards Hub는 카드와 이미지 식별 자료로 사용한다.
- 이미지 파일은 기본적으로 저장소에 복사하지 않고 출처 URL과 식별 정보만
  관리한다.

## 2. 최종 완료 기준

프로젝트의 최종 목표는 다음 세 가지 결과물이 같은 규칙 엔진을 사용하는 것이다.

1. 4인 Uprising을 끝까지 정확하게 실행하는 headless 게임 엔진
2. self-play 학습과 평가에 사용할 고처리량 다중 에이전트 환경
3. 한 명의 사람과 세 AI가 완전한 게임을 즐길 수 있는 플레이 인터페이스

기본 게임 엔진은 다음 조건을 모두 만족할 때 완료로 본다.

- CHOAM 모듈을 제외한 4인 기본 게임의 모든 구성물과 효과가 구현되어 있다.
- 모든 플레이어 결정에서 합법 행동을 열거하고 불법 행동은 명시적으로 거부한다.
- 공식 룰북 예제와 FAQ에서 파생한 시나리오 테스트가 통과한다.
- 같은 초기 seed와 행동·chance 기록은 같은 최종 상태와 이벤트 기록을 만든다.
- 플레이어 관측에 상대 손패, Intrigue, 덱 순서 등 비공개 정보가 새지 않는다.
- 무작위 합법 플레이가 교착 없이 완주하며 상태 불변식을 매 행동 뒤 만족한다.
- 저장된 replay로 게임을 재생하고 규칙 버전과 콘텐츠 버전을 확인할 수 있다.

## 3. 권장 아키텍처

TabletopGames의 `GameState / ForwardModel / Action` 분리는 채택하되, Dune 전용
Python 코어로 단순화한다. 특히 관측 복사, 탐색용 재결정화, 전체 상태 복사는
서로 다른 API로 둔다.

```text
사람 UI ───────────────┐
PettingZoo adapter ────┼──> GameSession ──> RulesEngine ──> GameState
batched self-play ─────┤                         │
평가/리플레이 도구 ────┘                         └──> ContentRegistry
```

### 핵심 객체

- `GameDefinition`: 규칙 설정과 불변 콘텐츠 레지스트리
- `GameState`: 모든 공개·비공개 정보를 가진 단일 권위 상태
- `RulesEngine`: 상태 없는 규칙 전이기
- `Decision`: `PlayerDecision`, `ChanceDecision`, 필요 시
  `SimultaneousDecision`의 합 타입
- `DomainAction`: 안정된 ID와 작은 값만 가진 불변 행동
- `DecisionFrame`: 연속 선택과 중첩 효과를 표현하는 직렬화 가능한 결정 프레임
- `PlayerView`: 특정 플레이어에게 허용된 정보만 담은 불변 관측
- `GameEvent`: 공개 범위와 원인을 가진 replay·디버깅 이벤트
- `Transition`: 적용된 행동, 생성된 이벤트, 다음 결정과 종료 정보를 담은 결과

### 최소 코어 API

```text
reset(definition, seed) -> GameState
current_decision(state) -> Decision
legal_actions(state, player) -> tuple[DomainAction, ...]
apply(state, action_or_chance_outcome) -> Transition
observe(state, player) -> PlayerView
clone_full(state) -> GameState
is_terminal(state) -> bool
results(state) -> tuple[PlayerResult, ...]
```

탐색 AI가 필요해질 때 `sample_determinization(view, rng)`를 별도로 추가한다.
`observe()`는 순수하고 결정론적이어야 하며 무작위 재결정화를 수행하지 않는다.

### 상태와 규칙 전이

- 라운드 상태 머신은
  `ROUND_START -> PLAYER_TURNS -> COMBAT -> MAKERS -> RECALL_OR_ENDGAME`으로
  표현한다.
- 원래 턴의 주인인 `turn_owner`와 현재 선택권자인 `decision_owner`를 분리한다.
  상대의 discard 선택이나 전투 반응처럼 턴 밖에서 발생하는 선택을 이 구조로
  처리한다.
- 복합 행동의 가능한 조합을 한 번에 만들지 않는다. 카드, 공간, 자원 지불,
  배치 수량, 대상 등을 작은 원자적 선택으로 나누고 `DecisionFrame` 스택으로
  연결한다.
- 자동으로 확정되는 효과는 다음 실제 결정 지점까지 진행한다. 순서 선택이 규칙상
  의미가 있으면 자동 정렬하지 않고 플레이어에게 선택권을 준다.
- 불법 행동을 임의의 합법 행동으로 바꾸지 않는다. 예외와 진단 정보를 반환한다.

### 효과와 콘텐츠

- 카드, 리더, 보드 공간, Conflict, Objective에 영구적인 문자열 ID를 부여한다.
- 반복되는 효과는 `gain_resource`, `draw`, `recruit`, `deploy`,
  `change_influence`, `acquire`, `choose_target` 등의 typed effect로 표현한다.
- 일반 DSL로 명확히 표현되지 않는 소수의 카드와 리더만 ID 기반 custom hook을
  사용한다.
- 콘텐츠 레코드에는 출처, 확인 상태, 적용 규칙 버전을 함께 기록한다.
- 콘텐츠 로딩 시 ID 중복, 잘못된 참조, 카드 수량, 덱 구성, 효과 인자를 전부
  검증한다.

### 난수와 replay

- `random` 전역 함수는 사용하지 않는다.
- 셔플, Objective/Conflict 선택, 무작위 강탈 등 모든 우연은 중앙 chance
  인터페이스를 통과한다.
- seed뿐 아니라 실제 chance 결과를 이벤트 기록에 남긴다. replay에서는 기록된
  결과를 주입하므로 Python이나 RNG 구현이 바뀌어도 게임을 재현할 수 있다.
- replay에는 `ruleset_version`, `content_version`, `action_codec_version`, seed와
  행동·chance stream을 저장한다.

### 예상 패키지 구조

```text
src/dune_imperium/
  core/
    actions.py
    decisions.py
    engine.py
    events.py
    observation.py
    replay.py
    rng.py
    state.py
  rules/
    setup.py
    phases.py
    agent_turn.py
    reveal_turn.py
    combat.py
    makers.py
    scoring.py
    effects.py
  content/
    schema.py
    registry.py
    uprising/
  adapters/
    pettingzoo_env.py
    action_codec.py
    observation_codec.py
  agents/
    random_agent.py
    heuristic_agent.py
  simulation/
    runner.py
    evaluation.py
  cli/
tests/
  unit/
  scenarios/
  properties/
  integration/
  adapters/
```

`src` layout으로 옮길 때 배포 패키지 이름도 충돌 가능성이 큰 `dune` 대신
`dune_imperium`으로 바꾼다.

## 4. 구현 마일스톤

### R0. 공식 규칙 명세 기준선

- 공식 Uprising Main Rulebook, Board Space Guide, 최신 FAQ의 문서 버전과
  적용 범위를 고정한다.
- 공식 URL과 checksum을 machine-readable manifest로 관리하고, 저장소 밖의
  working directory에 page-indexed text를 만드는 재현 가능한 도구를 유지한다.
- setup, Player Turns, Combat, Makers, Recall, Endgame, 공통 시스템, 보드 공간,
  CHOAM Module을 구현 단위로 요약하고 모든 규칙에 공식 페이지를 연결한다.
- FAQ에서 4인 Uprising에 적용되는 판정을 색인하고 다른 확장·Rivals·6인 규칙을
  현재 범위와 분리한다.
- 공식 문서에 없는 순서와 정보 정책은 임의 판정하지 않고
  `docs/rules/open-questions.md`에 기록한다.
- 문서 주제별 source coverage를 검산하고 규칙 명세에서 구현 테스트로 이어질
  항목을 식별한다.

완료 조건: [규칙 명세](rules/README.md)의 source map에 Main pp. 3-17, 20,
Board Guide pp. 1-2, 적용 가능한 FAQ pp. 1-4의 각 항목이 `covered`, 명시적인
`out of scope`, `deferred`, 또는 `open question`으로 분류되어 있다. 이 조건을
통과하기 전에는 규칙 엔진 구현을 시작하지 않는다.

### M0. 개발 골격과 규칙 추적 체계

- 새 `src/dune_imperium` 패키지와 테스트 디렉터리를 만든다.
- pytest, Ruff, mypy를 uv 개발 의존성으로 구성한다.
- `RulesetConfig(players=4, choam_module=False)`를 만든다.
- `docs/rules/open-questions.md`와 source map을 이후 변경에서도 유지한다.
- 기존 `dune/status.py`, `dune/cards.py`는 새 코드에서 import하지 않는다.

완료 조건: `uv run pytest`, lint, type check가 빈 골격에서 통과한다.

### M1. 엔진 커널

- ID, 상태, 행동, 결정 프레임, 이벤트, chance, replay의 기본 형식을 구현한다.
- `RulesEngine`의 reset, legal action, apply, observe 계약을 구현한다.
- clone 독립성, 불법 행동 거부, 결정 스택 push/pop을 테스트한다.

완료 조건: 작은 테스트 규칙에서 동일 입력 replay의 canonical state hash가 항상
같고, 관측 생성이 원본 상태를 변경하지 않는다.

### M2. 4인 setup과 정적 보드

- 플레이어 자원·말·시작 덱, Imperium Row, Reserve, Intrigue, Objective와
  단계별 Conflict deck setup을 구현한다.
- 22개 보드 공간과 공간 속성을 전사한다.
- Spy observation post 인접 그래프는 공식 보드 이미지에서 별도로 전사하고
  상호 참조 테스트로 검증한다.
- 전체 상태와 네 플레이어의 redacted view를 구현한다.

완료 조건: 여러 seed의 setup이 공식 수량 불변식을 만족하고, 같은 seed가 같은
setup을 만들며, 숨겨야 할 덱 순서와 상대 비공개 카드가 관측에 나타나지 않는다.

### M3. 한 라운드 수직 조각

- Round Start, Agent/Reveal 선택, 기본 공간 방문, 카드 구입, 전투, Makers,
  Recall을 한 흐름으로 연결한다.
- 시작 카드와 대표 공간·Conflict만으로도 규칙상 정확한 한 라운드를 실행한다.
- 사람이 상태와 합법 행동을 확인할 수 있는 디버그 CLI와 random agent를 만든다.
- 룰북 p.11, p.13, p.15의 예제를 golden scenario test로 옮긴다.

완료 조건: seed 기반 한 라운드를 random agent 네 명이 끝내고 replay할 수 있으며,
세 golden scenario가 통과한다.

### M4. RL 인터페이스 조기 검증

- 코어의 구조적 행동과 별도로 고정 정수 action catalog를 만든다.
- 복합 선택은 원자적 ID로 인코딩하고 합법 ID만 켜진 action mask를 제공한다.
- PettingZoo AEC adapter `dune_imperium_uprising_v0`를 optional `rl` 의존성으로
  추가한다.
- PettingZoo API, seed, action mask 테스트를 통과시킨다.

완료 조건: 한 라운드 수직 조각을 AEC 루프로 실행할 수 있고, adapter가 전체
`GameState`를 정책의 observation이나 `info`에 노출하지 않는다.

### M5. 기본 게임 시스템 규칙

- Influence, Friendship, Alliance 이동과 VP 경계를 구현한다.
- Spy의 Infiltrate, Gather Intelligence와 회수 제한을 구현한다.
- Shield Wall, Maker Hook, sandworm, critical location control을 구현한다.
- High Council, Swordmaster와 지속 효과를 구현한다.
- Combat Intrigue priority/pass loop, 모든 4인 동률 경우, 보상 배가와 battle
  icon을 구현한다.
- Maker 누적, 라운드 종료, Endgame 효과, 최종 동률 해소를 구현한다.

완료 조건: 각 시스템의 경계·예외 scenario와 상태 불변식 테스트가 통과한다.

### M6. Uprising 기본 콘텐츠 완성

- 기본 게임의 리더, 시작/Reserve/Imperium/Intrigue/Conflict/Objective 콘텐츠를
  전사한다.
- 각 효과를 typed effect 또는 명시적 custom hook에 연결한다.
- 카드별 최소 한 개의 효과 테스트와 상호작용 회귀 테스트를 추가한다.
- 카드 이미지 자체 대신 출처 URL과 검증 메타데이터를 기록한다.

완료 조건: 콘텐츠 manifest가 누락 없이 검증되고, 모든 콘텐츠가 실제 합법 행동
또는 효과 경로에서 도달 가능하다.

### M7. 기본 게임 완주 검증

- random legal self-play, property-based state machine test, 장시간 soak test를
  추가한다.
- CI에서는 고정된 소규모 seed 집합, 별도 로컬 작업에서는 최소 10,000개 seed를
  실행한다.
- 교착, 빈 합법 행동, 자원 음수, 말 총량 불일치, 비공개 정보 누출을 검사한다.
- headless games/sec와 clone/observe/step 비용의 기준선을 기록한다.

완료 조건: 기본 게임의 최종 완료 기준을 모두 만족한다. 절대 성능 목표는 이
기준선과 프로파일을 얻은 뒤 정한다.

### M8. CHOAM 계약 모듈

- 계약 deck/공개 시장, 계약 완료 조건, 완료 계약 기록을 구현한다.
- Shaddam과 CHOAM 전용 Imperium/Intrigue 카드를 추가한다.
- 모듈 OFF에서는 계약 아이콘의 대체 효과를 적용한다.
- 모듈 ON/OFF 양쪽 콘텐츠 manifest와 replay 호환성을 검증한다.

완료 조건: `choam_module` 설정만으로 두 규칙셋을 선택하고 양쪽 완주 테스트가
통과한다.

### M9. 평가 환경과 강한 baseline

- 여러 게임을 직접 구동하고 정책 추론만 batch하는 self-play runner를 만든다.
- random, 규칙 기반 heuristic, rollout/search baseline을 순서대로 만든다.
- 좌석, 리더, first-player, seed를 교차한 대회 도구를 만든다.
- 승률만이 아니라 평균 순위, VP 차이, 좌석별 성능, 불법 행동과 결정 시간도
  기록한다.

완료 조건: 버전이 다른 agent들의 재현 가능한 평가 행렬과 성능 보고서를 만들 수
있다.

### M10. 강화학습과 league self-play

- 관측 encoder와 action codec 버전을 고정하고 체크포인트에 저장한다.
- terminal reward를 기준선으로 masked multi-agent 학습을 시작한다.
- recurrent policy, centralized critic, reward shaping은 ablation으로 비교한다.
- 단일 최신 모델끼리만 학습하지 않고 과거 체크포인트와 heuristic/search agent를
  포함한 league를 운영한다.
- 과적합을 막기 위해 학습 seed와 평가 seed를 분리한다.

완료 조건: 고정 평가 대회에서 이전 champion과 모든 baseline보다 유의미하게
강한 모델을 재현할 수 있다.

### M11. 사람용 플레이 인터페이스

- 한 사람과 세 AI, 좌석·리더 선택, 저장/불러오기, undo가 아닌 replay 검토를
  지원한다.
- 사람에게도 `PlayerView`만 전달해 비공개 정보가 UI에 새지 않게 한다.
- 카드 이미지를 표시할 경우 이용 조건과 배포 방식을 먼저 확정한다.
- AI 결정 설명은 실제 관측과 합법 행동만 사용하도록 한다.

완료 조건: 사람이 설정부터 최종 점수까지 완전한 게임을 안정적으로 플레이할 수
있다.

## 5. 테스트 전략

- **콘텐츠 검증:** ID·수량·참조·덱 구성·출처의 정적 검사
- **규칙 단위 테스트:** 비용 선지불, 효과 순서, influence 2/4 경계 등 작은 규칙
- **Golden scenario:** 룰북 예시와 공식 FAQ 판정 재현
- **Property test:** 자원·말 보존, 합법 행동 soundness, clone 독립성
- **State-machine fuzz:** random legal action으로 다수 게임 진행
- **관측 보안 테스트:** 상대 비공개 정보만 다른 두 상태의 `PlayerView`가 같은지
  비교
- **Replay 테스트:** 상태 snapshot과 event hash의 완전 재현
- **Adapter contract:** PettingZoo API/seed/mask 검사
- **성능 회귀:** setup, step, legal action, observe, clone, games/sec 측정

규칙이 불명확할 때는 임의 판정을 조용히 구현하지 않는다. 공식 근거와 질문을
`rules_open_questions.md`에 남기고, 판정이 확정된 뒤 source citation과 회귀
테스트를 함께 추가한다.

## 6. RL 경계 결정

첫 표준 환경은 PettingZoo **AEC**로 한다. Uprising은 순차 턴과 반응 선택이
중심이므로 모든 살아 있는 agent가 한꺼번에 행동하는 Parallel API보다 적합하다.

- 코어: 구조적 `DomainAction`
- AEC adapter: 고정 `Discrete(A)`와 `action_mask`
- 학습 처리량: PettingZoo를 우회해 여러 코어 게임을 직접 batch 실행
- Gymnasium: 한 좌석 대 opponent pool 환경이 필요할 때 보조 adapter로 추가
- OpenSpiel: action codec 안정 후 ISMCTS나 게임이론 실험이 필요할 때 검토

보상 shaping은 규칙 코어에 넣지 않는다. 코어는 실제 VP, 순위, 승패를 반환하고
학습 실험이 reward 변환을 소유한다.

## 7. 주요 위험과 대응

- **카드 효과 수와 예외:** 공통 typed effect와 검증된 custom hook으로 분리한다.
- **선택 순서 폭발:** Cartesian action 대신 serializable decision stack을 쓴다.
- **비공개 정보 누출:** authoritative state와 `PlayerView` 타입/API를 분리한다.
- **규칙 오해:** 공식 출처, open question, scenario test를 한 단위로 관리한다.
- **Python 처리량:** 정확한 mutable state 코어로 시작하고 M7에서 측정한 hot path만
  최적화한다.
- **RL 프레임워크 종속:** 코어와 adapter를 분리하고 codec/schema에 버전을 둔다.
- **이미지 권리와 저장소 크기:** URL/메타데이터를 기본으로 하고 배포 결정 전에는
  원본 이미지를 저장소에 포함하지 않는다.

## 8. 바로 다음 작업

R0 규칙 명세의 coverage 검산이 끝난 뒤 M0를 시작한다. 첫 구현 PR/작업 단위는
다음으로 제한한다.

1. `src/dune_imperium` 골격과 개발 도구 설정
2. 핵심 Protocol/dataclass의 타입 계약
3. `RulesetConfig(players=4, choam_module=False)`
4. 규칙 명세와 연결된 콘텐츠 manifest 문서 골격
5. 커널 계약을 검증하는 첫 테스트

이 단계에서는 실제 카드 효과나 UI, RL 패키지를 아직 구현하지 않는다.
