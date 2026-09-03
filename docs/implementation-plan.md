# Dune: Imperium - Uprising 구현 계획

상태: 초안 7 (2026-08-30) — R0 규칙 명세, M0 개발 골격, M1 엔진 커널, M2 4인 setup과 정적 보드, M3 한 라운드 수직 조각, M4 RL 인터페이스 조기 검증 완료. M5의 기본 시스템 경계는 대부분 연결됐고 콘텐츠 의존 항목이 남아 있다. M6는 Leader 9종 능력·Signet Ring과 Objective 상호작용 재감사까지 마쳐 완료됐고, M8도 Shaddam의 Sardaukar contract와 CHOAM 전용 콘텐츠까지 연결돼 완료됐다. 전체 게임 러너와 PettingZoo 전체 게임 episode ([rl-environment.md](rl-environment.md)), 그리고 M7의 `dune-imperium-sweep` 완주 검증(룰셋당 10,000판 실패 0)까지 끝났다. M11 사람용 플레이 인터페이스(2026-08-30 순서 변경으로 M9·M10보다 선행)는 2026-08-31에 저장/불러오기와 replay 검토까지, 2026-09-03에 슬라이스 7(보드 스캔 테이블 + 아이콘)까지 완료됐다. 다음 마일스톤은 M9 평가 환경이고 M10 강화학습이 그 뒤를 잇는다.

이 문서는 규칙 엔진부터 강화학습 AI와 사람용 플레이 인터페이스까지의 구현 순서와 각 단계의 완료 조건을 정의한다. 구현 중 새 규칙을 발견하더라도 핵심 계층의 책임을 유지하고, 마일스톤별 검증을 통과한 뒤 다음 범위로 진행한다.

## 1. 확정된 방향

- 대상 게임은 **Dune: Imperium - Uprising 4인 플레이**다.
- **CHOAM 모듈을 끈 기본 게임**을 첫 완성 범위로 한다. 공식 룰북이 계약을 선택형 미니 확장으로 분류하기 때문이다. 계약, Shaddam, CHOAM 전용 Imperium/Intrigue 카드는 기본 게임 완성 직후 `choam_module=True` 규칙 설정으로 추가한다.
- Python 3.14와 uv를 사용한다.
- 기존 `dune/` 코드는 참고 자료로만 두고 새 구조와의 호환성을 요구하지 않는다.
- 규칙 코어는 UI와 RL 라이브러리에 의존하지 않는 네이티브 Python 엔진으로 만든다.
- 공식 Dire Wolf Digital 룰북, 보충 자료, FAQ를 규칙 판정의 우선 출처로 사용한다. Dune Cards Hub는 카드와 이미지 식별 자료로 사용한다.
- 이미지 파일은 기본적으로 저장소에 복사하지 않고 출처 URL과 식별 정보만 관리한다.

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

TabletopGames의 `GameState / ForwardModel / Action` 분리는 채택하되, Dune 전용 Python 코어로 단순화한다. 특히 관측 복사, 탐색용 재결정화, 전체 상태 복사는 서로 다른 API로 둔다.

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
- `Decision`: `PlayerDecision`, `ChanceDecision`, 필요 시 `SimultaneousDecision`의 합 타입
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

탐색 AI가 필요해질 때 `sample_determinization(view, rng)`를 별도로 추가한다. `observe()`는 순수하고 결정론적이어야 하며 무작위 재결정화를 수행하지 않는다.

### 상태와 규칙 전이

- 라운드 상태 머신은 `ROUND_START -> PLAYER_TURNS -> COMBAT -> MAKERS -> RECALL_OR_ENDGAME`으로 표현한다.
- 원래 턴의 주인인 `turn_owner`와 현재 선택권자인 `decision_owner`를 분리한다. 상대의 discard 선택이나 전투 반응처럼 턴 밖에서 발생하는 선택을 이 구조로 처리한다.
- 복합 행동의 가능한 조합을 한 번에 만들지 않는다. 카드, 공간, 자원 지불, 배치 수량, 대상 등을 작은 원자적 선택으로 나누고 `DecisionFrame` 스택으로 연결한다.
- 자동으로 확정되는 효과는 다음 실제 결정 지점까지 진행한다. 순서 선택이 규칙상 의미가 있으면 자동 정렬하지 않고 플레이어에게 선택권을 준다.
- 불법 행동을 임의의 합법 행동으로 바꾸지 않는다. 예외와 진단 정보를 반환한다.

### 효과와 콘텐츠

- 카드, 리더, 보드 공간, Conflict, Objective에 영구적인 문자열 ID를 부여한다.
- 반복되는 효과는 `gain_resource`, `draw`, `recruit`, `deploy`, `change_influence`, `acquire`, `choose_target` 등의 typed effect로 표현한다.
- 일반 DSL로 명확히 표현되지 않는 소수의 카드와 리더만 ID 기반 custom hook을 사용한다.
- 콘텐츠 레코드에는 출처, 확인 상태, 적용 규칙 버전을 함께 기록한다.
- 콘텐츠 로딩 시 ID 중복, 잘못된 참조, 카드 수량, 덱 구성, 효과 인자를 전부 검증한다.

### 난수와 replay

- `random` 전역 함수는 사용하지 않는다.
- 셔플, Objective/Conflict 선택, 무작위 강탈 등 모든 우연은 중앙 chance 인터페이스를 통과한다.
- seed뿐 아니라 실제 chance 결과를 이벤트 기록에 남긴다. replay에서는 기록된 결과를 주입하므로 Python이나 RNG 구현이 바뀌어도 게임을 재현할 수 있다.
- replay에는 `ruleset_version`, `content_version`, `action_codec_version`, seed와 행동·chance stream을 저장한다.

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

`src` layout으로 옮길 때 배포 패키지 이름도 충돌 가능성이 큰 `dune` 대신 `dune_imperium`으로 바꾼다.

## 4. 구현 마일스톤

마일스톤 번호는 안정된 참조를 위해 유지하고 재부여하지 않는다. 구현 순서는 이 절의 나열 순서를 따른다. 2026-08-30에 M11(사람용 플레이 인터페이스)을 M9·M10보다 앞으로 옮겼다. 엔진과 완주 검증이 끝난 지금 사람이 직접 플레이하며 규칙과 경험을 검증하는 가치가 크고, M11의 완료 조건은 강한 AI를 요구하지 않기 때문이다. AI 상대는 M11에서 random과 간단한 heuristic으로 시작하고, M9·M10이 끝나면 같은 agent 인터페이스로 강한 상대를 갈아끼운다.

### R0. 공식 규칙 명세 기준선

- 공식 Uprising Main Rulebook, Board Space Guide, 최신 FAQ의 문서 버전과 적용 범위를 고정한다.
- 공식 URL과 checksum을 machine-readable manifest로 관리하고, 저장소 밖의 working directory에 page-indexed text를 만드는 재현 가능한 도구를 유지한다.
- setup, Player Turns, Combat, Makers, Recall, Endgame, 공통 시스템, 보드 공간, CHOAM Module을 구현 단위로 요약하고 모든 규칙에 공식 페이지를 연결한다.
- FAQ에서 4인 Uprising에 적용되는 판정을 색인하고 다른 확장·Rivals·6인 규칙을 현재 범위와 분리한다.
- 공식 문서에 없는 순서와 정보 정책은 임의 판정하지 않고 `docs/rules/open-questions.md`에 기록한다.
- 문서 주제별 source coverage를 검산하고 규칙 명세에서 구현 테스트로 이어질 항목을 식별한다.

완료 조건: [규칙 명세](rules/README.md)의 source map에 Main pp. 3-17, 20, Board Guide pp. 1-2, 적용 가능한 FAQ pp. 1-4의 각 항목이 `covered`, 명시적인 `out of scope`, `deferred`, 또는 `open question`으로 분류되어 있다. 이 조건을 통과하기 전에는 규칙 엔진 구현을 시작하지 않는다.

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

완료 조건: 작은 테스트 규칙에서 동일 입력 replay의 canonical state hash가 항상 같고, 관측 생성이 원본 상태를 변경하지 않는다.

### M2. 4인 setup과 정적 보드

- 플레이어 자원·말·시작 덱, Imperium Row, Reserve, Intrigue, Objective와 단계별 Conflict deck setup을 구현한다.
- 22개 보드 공간과 공간 속성을 전사한다.
- Spy observation post 인접 그래프는 공식 보드 이미지에서 별도로 전사하고 상호 참조 테스트로 검증한다.
- 전체 상태와 네 플레이어의 redacted view를 구현한다.

완료 조건: 여러 seed의 setup이 공식 수량 불변식을 만족하고, 같은 seed가 같은 setup을 만들며, 숨겨야 할 덱 순서와 상대 비공개 카드가 관측에 나타나지 않는다.

### M3. 한 라운드 수직 조각

상태: **완료** (2026-08-14). 현재 전사된 시작 카드와 대표 공간·Conflict로 seeded random 4인 라운드를 실행하고 action replay로 최종 상태를 검증한다. 디버그 CLI와 Main pp. 11, 13, 15에서 파생한 4인 범위 golden scenario를 유지한다. 미전사 카드 효과는 이후 콘텐츠 마일스톤에서 확장한다.

- Round Start, Agent/Reveal 선택, 기본 공간 방문, 카드 구입, 전투, Makers, Recall을 한 흐름으로 연결한다.
- 시작 카드와 대표 공간·Conflict만으로도 규칙상 정확한 한 라운드를 실행한다.
- 사람이 상태와 합법 행동을 확인할 수 있는 디버그 CLI와 random agent를 만든다.
- 룰북 p.11, p.13, p.15의 예제를 golden scenario test로 옮긴다.

완료 조건: seed 기반 한 라운드를 random agent 네 명이 끝내고 replay할 수 있으며, 세 golden scenario가 통과한다.

### M4. RL 인터페이스 조기 검증

상태: **완료** (2026-08-14, 현황 갱신 2026-08-28). 기본 룰셋은 versioned actor-neutral 정수 action catalog와 같은 폭의 legal action mask를 사용한다. 현재 codec v71의 기본 룰셋은 3,923개 행동이며, CHOAM 룰셋은 contract 시장·완료·Spy·전용 Imperium·Intrigue 선택을 포함해 4,169개 행동이다. `dune_imperium_uprising_v0` AEC 환경은 한 라운드를 episode로 실행하며 PettingZoo `api_test`와 `seed_test`를 통과한다. 관측과 `info`에는 전체 `GameState`를 노출하지 않는다.

- 코어의 구조적 행동과 별도로 고정 정수 action catalog를 만든다.
- 복합 선택은 원자적 ID로 인코딩하고 합법 ID만 켜진 action mask를 제공한다.
- PettingZoo AEC adapter `dune_imperium_uprising_v0`를 optional `rl` 의존성으로 추가한다.
- PettingZoo API, seed, action mask 테스트를 통과시킨다.

완료 조건: 한 라운드 수직 조각을 AEC 루프로 실행할 수 있고, adapter가 전체 `GameState`를 정책의 observation이나 `info`에 노출하지 않는다.

### M5. 기본 게임 시스템 규칙

상태: **진행 중** (현황 갱신 2026-08-27). Influence·Alliance, Spy의 Infiltrate와 Gather Intelligence, Shield Wall·Maker Hook·sandworm·critical location control, High Council·Swordmaster, 4인 Combat 순위와 기본 보상, Makers·Recall 및 Endgame 진입을 구현했다. 최종 순위는 공식 tiebreak 전체를 적용한다. Endgame은 First Player부터 시계 방향의 Endgame Intrigue window(OQ-001 convention)에서 Endgame play와 wild battle icon matching을 해결한 뒤 `FINISHED`로 진행하며, Intrigue 보유와 wild 쌍이 모두 없으면 window 없이 즉시 종료한다. random 4인 게임이 FINISHED까지 완주되고 replay로 재현된다. 개인 덱 draw는 부족할 때 discard를 replayable chance로 shuffle하며, 두 라운드와 세 번째 Round Start shuffle까지 같은 action/chance stream으로 재생한다.

- Influence, Friendship, Alliance 이동과 VP 경계를 구현한다.
- Spy의 Infiltrate, Gather Intelligence와 회수 제한을 구현한다.
- Shield Wall, Maker Hook, sandworm, critical location control을 구현한다.
- High Council, Swordmaster와 지속 효과를 구현한다.
- Combat Intrigue priority/pass loop, 모든 4인 동률 경우, 보상 배가와 battle icon을 구현한다.
- Maker 누적, 라운드 종료, Endgame 효과, 최종 동률 해소를 구현한다.

완료 조건: 각 시스템의 경계·예외 scenario와 상태 불변식 테스트가 통과한다.

### M6. Uprising 기본 콘텐츠 완성

상태: **완료** (2026-08-30).

완료된 범위:

- 시작 카드 7종, Reserve 2종(Prepare the Way, The Spice Must Flow), 기본 Imperium 50종, CHOAM 전용 Imperium 4종의 play data를 모두 전사해 실제 Agent·Reveal·acquire 경로에 연결했다. codec은 Reserve Agent 행동의 v7에서 시작해 카드 묶음마다 올라 현재 v64이다.
- 카드 구현 과정에서 다음 공통 경계를 확립했다. 개인 카드 resolver, typed Reveal 효과 schema, Faction Bond·Influence 조건 판정, 선택형 획득 보너스, Spy 배치·회수와 turn 범위 recall 조건, hand discard·trash·deck-top 선택과 카드별 trigger, Agent-card 결제·Solari 구매·Agent 회수, 상대 hand discard의 player-owned frame, Reveal 중첩 선택 frame, Influence 감소·Alliance 이전.
- 카드별 인쇄 효과와 규칙 민감 판정은 [personal-cards audit](implementation-audits/personal-cards.md)에, 묶음 단위 구현 이력은 git의 `Play ...` / `Document ...` 커밋 쌍에 기록돼 있다.
- 고정된 DIU `imperium.JSON`은 런타임 의존성 없이 63개 local identity와 대조하고 아이콘·Faction·효과 형태를 정규화하는 read-only audit에만 사용한다.
- Intrigue는 공통 play/discard 경계, effect DSL, 선택 슬롯 frame, Combat priority loop 안의 play가 있고 39개 identity(물리 44장) 전부가 실제 play 경로에 연결돼 Intrigue 덱이 완결됐다(목록은 [Intrigue audit](implementation-audits/intrigue.md)). Endgame window는 OQ-001 convention으로 동작한다.
- 인쇄된 Leader 9종의 능력과 Signet Ring이 모두 play된다 ([Leader audit](implementation-audits/leaders.md)).
- Objective는 setup·battle icon·Endgame wild·Intrigue flip 상호작용 재감사를 마쳤고 OQ-005를 해소했다 ([Objective audit](implementation-audits/objectives.md)).

마일스톤 범위:

- 기본 게임의 리더, 시작/Reserve/Imperium/Intrigue/Conflict/Objective 콘텐츠를 전사한다.
- 각 효과를 typed effect 또는 명시적 custom hook에 연결한다.
- 카드별 최소 한 개의 효과 테스트와 상호작용 회귀 테스트를 추가한다.
- 카드 이미지 자체 대신 출처 URL과 검증 메타데이터를 기록한다.

완료 조건: 콘텐츠 manifest가 누락 없이 검증되고, 모든 콘텐츠가 실제 합법 행동 또는 효과 경로에서 도달 가능하다.

### M7. 기본 게임 완주 검증

상태: **완료** (2026-08-30). `run_random_game` 러너와 전체 게임 PettingZoo episode 위에 `dune-imperium-sweep` 검증 도구를 만들었다. 매 전이마다 전역 카드 보존(개인 카드 instance 집합, Reserve 스택+생존 사본, Intrigue·Conflict·Contract·Objective), 교착(빈 합법 행동·미종료), 그리고 표본 주기로 관측 누출(숨은 정보만 뒤섞은 상태와의 관측 동일성)을 검사하고 replay를 검증한다. 고정 소규모 seed 집합은 pytest에 있고, 룰셋당 10,000판(총 20,000판) 로컬 sweep이 실패 0으로 통과했다(50 games/s, 8 workers, 전이 약 879만 회). 첫 20,000판 실행은 잠복 버그 다섯 계열(Spy Network recall 교착, Price is No Object 획득 Spy frame 정지, Maker Keeper·Bond 조건 drift, Corrinth City 선택 소실, self-trash 카드의 보류 효과)을 46판에서 적발했고 모두 해결 시점 판정으로 수정했다. 시나리오 커버리지는 카드·규칙별 FAQ 인용 테스트 770개가 담당하며, 절대 성능 목표는 원계획대로 이 기준선 위에서 따로 정한다.

- random legal self-play, property-based state machine test, 장시간 soak test를 추가한다.
- CI에서는 고정된 소규모 seed 집합, 별도 로컬 작업에서는 최소 10,000개 seed를 실행한다.
- 교착, 빈 합법 행동, 자원 음수, 말 총량 불일치, 비공개 정보 누출을 검사한다.
- headless games/sec와 clone/observe/step 비용의 기준선을 기록한다.

완료 조건: 기본 게임의 최종 완료 기준을 모두 만족한다. 절대 성능 목표는 이 기준선과 프로파일을 얻은 뒤 정한다.

### M8. CHOAM 계약 모듈

상태: **완료** (2026-08-30). standard contract 20장의 identity·조건·보상과 출처 URL을 전사하고, `choam_module=True` setup의 replayable shuffle·공개 2장·face-down bank 18장을 구현했다. 시장 take/refill·고갈과 Immediate뿐 아니라 board-space 방문, Harvest의 turn Spice 합계, The Spice Must Flow acquire 완료 trigger도 연결돼 있다. 같은 조건의 여러 contract는 모두 의무 완료하며, 각 보상은 board·Agent 효과와 직렬 자유 순서로 처리한다. CHOAM 전용 Imperium 4종도 완료 Contract 수와 같은 시장 transition에 연결했다. Cargo Runner는 효과 해결 시점의 완료 수로 최대 두 장을 draw하고, Delivery Agreement와 Priority Contracts는 기본 Spice와 4개 완료 시 self-trash·VP 선택을 정확히 구분한다. Interstellar Trade는 acquire 시 Contract를 가져가고 Reveal 시작 시점의 완료 수만 Persuasion으로 센다. 당시 codec v58은 기본 룰셋 3,377개를 유지하고 CHOAM 룰셋의 전용 Agent 목적지와 Reveal 선택까지 3,598개다. 이후 CHOAM 전용 Intrigue 3종, Shaddam의 set-aside Sardaukar contract와 Leader 능력(2026-08-30, codec v76~77), CHOAM 룰셋의 random 완주+replay 테스트까지 연결돼 완료 조건을 만족한다.

- 계약 deck/공개 시장, 계약 완료 조건, 완료 계약 기록을 구현한다.
- Shaddam과 CHOAM 전용 Imperium/Intrigue 카드를 추가한다.
- 모듈 OFF에서는 계약 아이콘의 대체 효과를 적용한다.
- 모듈 ON/OFF 양쪽 콘텐츠 manifest와 replay 호환성을 검증한다.

완료 조건: `choam_module` 설정만으로 두 규칙셋을 선택하고 양쪽 완주 테스트가 통과한다.

### M11. 사람용 플레이 인터페이스

상태: **완료** (2026-08-31). 형태는 **로컬 웹 UI**(FastAPI + uvicorn 로컬 서버 + 의존성 없는 vanilla HTML/JS 브라우저 페이지)다. 규칙 코어는 UI에 의존하지 않는 기존 경계를 유지하고, UI는 엔진의 공개 API(`reset`/`current_decision`/`legal_actions`/`apply`/`observe`)와 `PlayerView`만 사용한다. 완료 조건(사람이 설정부터 최종 점수까지 완전한 게임을 안정적으로 플레이)은 슬라이스 4의 브라우저 완주와 슬라이스 5의 저장→불러오기→완주→replay 검토 E2E(실제 headless Chromium + uvicorn, 서버 오류 0)로 판정했다. 저장은 `GameReplay` 직렬화 위의 버전 스탬프된 로컬 JSON 파일이고, 불러오기는 기록 steps를 seed 기반 chance·agent 스트림으로 재생성 대조해 RNG 위치까지 복원하므로 불러온 게임은 저장하지 않은 세션과 동일하게 진행된다. 종료 후 replay 검토는 2026-09-02 OQ-010 확정에 따라 모든 좌석 시점·모든 행동 라벨·chance 값과 함께 모든 비공개 존을 공개한다(`disclosure`).

**슬라이스 6(완료, 2026-09-02): 행동 되돌리기 + 실시간 행동 로그.** 서버는 모든 단계를 기록하고 상태는 불변이므로, 되돌리기는 기록을 특정 단계까지 잘라내고 검토와 같은 방식으로 상태를 복원하는 서버·UI 작업이다(엔진 변경 없음). 구현: `server/session_log.py`(append-only 세션 로그 = 단계 + 그 단계의 이벤트 + 되돌림 마커, `reveals_hidden_information`은 `core.observation.known_card_seats`로 정보 흐름을 판정), `GameSessionManager.undo`/`log`, 저장 형식 v2(로그와 되돌린 구간 보관; v1도 읽음), `POST /games/{id}/undo`·`GET /games/{id}/log`, 검토 메타의 `undo_history`, UI의 되돌리기 버튼·행동 로그 패널·검토 마커. headless Chromium E2E로 확인했다. 허용 경계는 OQ-010의 정보 흐름 세 가지로 정한다: (1) 숨겨진 더미에서 누군가에게 흘러간 정보 — 자기 덱 draw(덱 맨 위를 본 뒤 다른 선택을 막기 위해 자기 draw 포함), Intrigue draw, Imperium Row 보충, Conflict 공개, contract bank 뒤집기, Secrets 강탈 — 는 되돌릴 수 없다; (2) 자기 비공개 존에서 공개 존으로 스스로 옮긴 정보(Intrigue play, hand discard·trash, Reveal)는 손해를 감수하고 되돌릴 수 있다; (3) 다른 좌석(AI 포함)이 행동한 뒤에는 그 이전으로 되돌릴 수 없다. 즉 되돌리기 창은 "마지막 무작위 결과 또는 다른 좌석의 행동 이후 자신이 연속으로 한 행동들"이고, 판정은 단계 적용 전후 상태 비교(비공개 존의 card id가 어느 좌석에게든 보이는 존에 나타났는지)로 구현해 새 콘텐츠에서도 자동으로 잡는다. 요청자는 되돌려지는 행동의 좌석 본인으로 한정하고, 되돌린 행동은 세션 로그(엔진 `event_log`가 아닌 서버 보관 로그)에 "되돌림"으로 공개 기록하며, 저장 파일에도 되돌린 구간을 보관해 검토 화면에서 보여 준다. 실시간 행동 로그(같은 세션 로그를 `visible_to`로 걸러 표시)도 이 슬라이스에서 함께 만든다.

**슬라이스 7(완료, 2026-09-03): 보드 스캔 위의 한 화면 테이블 + 룰북 아이콘.** 방향은 친구의 `kyungtae` 브랜치(`881849c`, 보드 이미지 위 hotspot·좌석색 토큰·카드 이미지 손패)에서 가져오되, 그 브랜치가 master보다 33커밋 뒤처져 v3 관측·undo·로그·공개 패널과 충돌하므로 병합하지 않고 master 위에 새로 구현했다(사용자 결정). 사용자 판정 두 가지: 보드 원본은 `images/`가 아니라 저장소 루트의 `map.jpg`(gitignore)로 두고, 효과는 텍스트 대신 카드·보드처럼 아이콘으로 보여주되 아이콘은 룰북·카드에서 뽑아 만든다. 구현: `display/board_layout.py`(22칸 박스 + 관측소 13곳의 퍼센트 좌표, 소유자 스캔 기준 수측정), `display/icons.py` + `scripts/extract_rulebook_icons.py`(고정 공식 룰북 PDF의 image xref 45개를 sha256 검증 후 추출·배경 키잉), 서버 `/board-image`·`/icons`와 catalog의 `box`·`posts`·`icons`·`board_image`, 브라우저의 3열 고정 테이블(좌석/보드+공용 카드/결정·로그·공개)과 하단 손패, 아이콘 glossary(`ICON_RULES`)로 서버 효과 텍스트를 인쇄 아이콘으로 재렌더. 스캔·이미지·아이콘이 없으면 각각 텍스트 보드 목록·텍스트 카드·단어로 대체된다. headless Chromium E2E(JS·서버 오류 0)로 확인했다. 열린 항목: Influence·VP 트랙 마커의 보드 위 표시, 아이콘 키잉 tolerance 미세 조정(일부 프레임 아이콘 모서리의 잔여 베이지).

- 한 사람과 세 AI, 좌석·리더 선택, 저장/불러오기, undo가 아닌 replay 검토를 지원한다. 저장/불러오기는 `GameReplay` 직렬화 위에 만든다.
- AI 상대는 `RandomAgent`와 이 마일스톤에서 만드는 간단한 규칙 기반 heuristic agent로 시작한다. agent 교체 인터페이스를 유지해 M9·M10의 강한 baseline과 학습 모델로 갈아끼울 수 있게 한다.
- 사람에게도 `PlayerView`만 전달해 비공개 정보가 UI에 새지 않게 한다.
- 카드 이미지를 표시할 경우 이용 조건과 배포 방식을 먼저 확정한다. 확정 전에는 카드 텍스트 표현을 기본으로 한다.
- AI 결정 설명은 실제 관측과 합법 행동만 사용하도록 한다.
- Leader 선택은 OQ-007의 6종 공개 draft convention(합법 Leader 중 무작위 6종을 공개로 뽑고, First Player 확정 뒤 turn 역순으로 pick, First Player가 마지막)을 ruleset option으로 구현한다. 공식 규칙이 아님을 명시하고, 고정 배정 경로는 테스트·재현성용으로 유지한다.

완료 조건: 사람이 설정부터 최종 점수까지 완전한 게임을 안정적으로 플레이할 수 있다.

### M9. 평가 환경과 강한 baseline

- 여러 게임을 직접 구동하고 정책 추론만 batch하는 self-play runner를 만든다.
- random, 규칙 기반 heuristic, rollout/search baseline을 순서대로 만든다. heuristic은 M11의 사람용 상대로 먼저 구현한 agent에서 출발한다.
- 좌석, 리더, first-player, seed를 교차한 대회 도구를 만든다.
- 승률만이 아니라 평균 순위, VP 차이, 좌석별 성능, 불법 행동과 결정 시간도 기록한다.

완료 조건: 버전이 다른 agent들의 재현 가능한 평가 행렬과 성능 보고서를 만들 수 있다.

### M10. 강화학습과 league self-play

- 관측 encoder와 action codec 버전을 고정하고 체크포인트에 저장한다.
- terminal reward를 기준선으로 masked multi-agent 학습을 시작한다.
- recurrent policy, centralized critic, reward shaping은 ablation으로 비교한다.
- 단일 최신 모델끼리만 학습하지 않고 과거 체크포인트와 heuristic/search agent를 포함한 league를 운영한다.
- 과적합을 막기 위해 학습 seed와 평가 seed를 분리한다.

완료 조건: 고정 평가 대회에서 이전 champion과 모든 baseline보다 유의미하게 강한 모델을 재현할 수 있다.

## 5. 테스트 전략

- **콘텐츠 검증:** ID·수량·참조·덱 구성·출처의 정적 검사
- **규칙 단위 테스트:** 비용 선지불, 효과 순서, influence 2/4 경계 등 작은 규칙
- **Golden scenario:** 룰북 예시와 공식 FAQ 판정 재현
- **Property test:** 자원·말 보존, 합법 행동 soundness, clone 독립성
- **State-machine fuzz:** random legal action으로 다수 게임 진행
- **관측 보안 테스트:** 상대 비공개 정보만 다른 두 상태의 `PlayerView`가 같은지 비교
- **Replay 테스트:** 상태 snapshot과 event hash의 완전 재현
- **Adapter contract:** PettingZoo API/seed/mask 검사
- **성능 회귀:** setup, step, legal action, observe, clone, games/sec 측정

규칙이 불명확할 때는 임의 판정을 조용히 구현하지 않는다. 공식 근거와 질문을 [`rules/open-questions.md`](rules/open-questions.md)에 남기고, 판정이 확정된 뒤 source citation과 회귀 테스트를 함께 추가한다.

## 6. RL 경계 결정

첫 표준 환경은 PettingZoo **AEC**로 한다. Uprising은 순차 턴과 반응 선택이 중심이므로 모든 살아 있는 agent가 한꺼번에 행동하는 Parallel API보다 적합하다.

- 코어: 구조적 `DomainAction`
- AEC adapter: 고정 `Discrete(A)`와 `action_mask`
- 학습 처리량: PettingZoo를 우회해 여러 코어 게임을 직접 batch 실행
- Gymnasium: 한 좌석 대 opponent pool 환경이 필요할 때 보조 adapter로 추가
- OpenSpiel: action codec 안정 후 ISMCTS나 게임이론 실험이 필요할 때 검토

보상 shaping은 규칙 코어에 넣지 않는다. 코어는 실제 VP, 순위, 승패를 반환하고 학습 실험이 reward 변환을 소유한다.

## 7. 주요 위험과 대응

- **카드 효과 수와 예외:** 공통 typed effect와 검증된 custom hook으로 분리한다.
- **선택 순서 폭발:** Cartesian action 대신 serializable decision stack을 쓴다.
- **비공개 정보 누출:** authoritative state와 `PlayerView` 타입/API를 분리한다.
- **규칙 오해:** 공식 출처, open question, scenario test를 한 단위로 관리한다.
- **Python 처리량:** 정확한 mutable state 코어로 시작하고 M7에서 측정한 hot path만 최적화한다.
- **RL 프레임워크 종속:** 코어와 adapter를 분리하고 codec/schema에 버전을 둔다.
- **이미지 권리와 저장소 크기:** URL/메타데이터를 기본으로 하고 배포 결정 전에는 원본 이미지를 저장소에 포함하지 않는다.

## 8. 바로 다음 작업

R0~M8과 M11(슬라이스 7까지)이 완료된 2026-09-03 기준으로 다음 작업은 **M9 평가 러너와 baseline**이다(마일스톤 절의 M9 완료 조건을 따른다). 최신 기준선과 세부 착수점은 [개발 인수인계](development-handoff.md)가 관리한다.
