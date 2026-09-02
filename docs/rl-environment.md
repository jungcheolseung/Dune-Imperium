# 학습 환경 설계 (전체 게임 episode)

상태: 확정 (2026-08-30). 이 문서는 전체 게임 RL 환경의 세 가지 설계 결정—관측 인코딩, 종료 보상, episode 메커니즘—을 기록한다. 규칙 가시성의 규범 근거는 [`rules/information-visibility.md`](rules/information-visibility.md)와 OQ-010이고, 구현은 `adapters/observation_encoding.py`, `adapters/pettingzoo_env.py`, `simulation/runner.py`에 있다.

## 관측 인코딩 (v3)

- 인코더 `encode_player_view`는 **`PlayerView`의 순수 함수**다. 공개/비공개 경계는 `core/observation.py`가 단독으로 결정하며, 인코더는 view에 없는 정보를 만들 수 없다.
- 형태는 단일 평면 `int32` 벡터(현재 1,967개)다. `OBSERVATION_VERSION`(현재 3)과 이름 붙은 세그먼트 표 `OBSERVATION_SEGMENTS`(`name`, `offset`, `length`)를 함께 export하고, `segment_slice(name)`으로 조회한다. 학습 코드는 오프셋을 하드코딩하지 않는다. 레이아웃 변경은 반드시 `OBSERVATION_VERSION`을 올린다. v2는 OQ-007 leader draft option의 공개 6-Leader pool 세그먼트(`leader_draft_pool`, Leader identity 슬롯 6칸, 옵션 off면 0)를 추가했다; pick 결과는 기존 좌석별 Leader 슬롯으로 보인다. v3(2026-09-02, OQ-010 확정)은 좌석별 `seat{n}_hand_public`(공개 경로로 hand에 들어온 카드, 개인 카드 63종 카운트)·`seat{n}_discard`(63종 카운트)·`seat{n}_completed_contracts`(Contract 20종 multi-hot) 세그먼트와 전역 `intrigue_resolving`(play됐지만 선택 해결 중이라 아직 소유자 보유 존에 있는 Intrigue, 39종 카운트) 세그먼트를 추가하고, 중복이 된 `private_discard` 세그먼트와 좌석 scalar의 discard 장수·완료 contract 수를 제거했다(좌석 scalar 28→26).
- 인코딩 규칙 세 가지:
  - **순서 있는 슬롯**: `identity_index + 1`, 0은 빈칸(Imperium Row 5칸, 현재 Conflict, Agent 위치 3칸, reveal 순서 등).
  - **순서 없는 카드 존**: identity별 카운트 벡터(자기 hand, 각자의 discard/in_play/trashed, Intrigue discard/trash 등). identity 우주는 콘텐츠 정의 순서로 고정한다: 개인 카드 63종(시작 7 + Reserve 2 + Imperium 54), Intrigue 39종, Contract 20종.
  - **상태 존**: multi-hot(alliance 4, control 3, spy post 13, contract 20)과 battle card 21칸의 tri-state(0=없음, 1=face-up, 2=face-down).
- **egocentric 좌석 회전**: 상대 좌석 블록과 모든 좌석 참조 값(first player, 결정 소유자, reveal 순서)은 관측자를 상대 좌석 0으로 회전한 상대 인덱스다. self-play 가중치 공유를 위해서다.
- **결정 컨텍스트**: top frame kind(24종), 결정 소유자, turn 소유자를 공개한다. frame별 세부 컨텍스트는 비공개 정보를 담을 수 있어 kind별 화이트리스트를 검토한 뒤에만 추가한다(후속 작업).
- 상대 hand·deck·Intrigue **장수**는 OQ-010 convention으로 공개다(실물 테이블에서 항상 보이는 수량). 상대 **discard pile identity**와 **완료 contract identity**는 OQ-010 확정 판정(2026-09-02, "한 번 공개된 정보는 재확인 가능")으로 공개다: discard pile의 모든 카드는 face-up으로 들어왔고, 완료 contract는 활성 중 face-up이었으며 완료가 공지됐다. hand·deck·보유 Intrigue identity는 계속 비공개이되, 공개 경로로 hand에 들어온 카드(Corrinth City·Intrigue "put it in your hand"·Bond 반환)는 hand를 떠날 때까지 `hand_public`으로 공개되고, play돼 선택 해결 중인 Intrigue는 `intrigue_resolving`으로 공개된다([`rules/information-visibility.md`](rules/information-visibility.md)).

## 보상

- **종료 보상만** 사용한다: `final_standings` 기준 승자 +1, 나머지 각 −1/3(zero-sum, 승자독식). 공식 tiebreak 체인(자원 → FAQ의 최근 Reveal)이 순위를 항상 확정하므로 승자는 유일하다.
- 중간 보상(per-step VP delta 등)은 환경에서 제공하지 않는다. shaping은 학습 쪽 wrapper의 몫이며, 종료 시 `infos`에 각 좌석의 `rank`와 `victory_points`를 노출해 wrapper 작성을 지원한다.

## Episode 메커니즘 (`dune_imperium_uprising_v1`)

- 한 episode = 한 판. `FINISHED`에서 전원 termination과 종료 보상을 준다.
- **chance 자동 해결**: 덱 reshuffle 등 `ChanceDecision`은 env 내부의 `ChanceResolver`(reset seed에서 유도)로 해결한다. 같은 seed는 셔플까지 동일한 episode를 재현하고, agent는 항상 `PlayerDecision`에서만 행동한다.
- 옵션: `choam_module`(룰셋 선택), `leader_draft`(OQ-007 draft setup; episode가 pick `PlayerDecision`들로 시작한다), `max_steps`(truncation 안전장치, 기본 30,000; truncation 시 보상 0). `pick_leader` 템플릿은 draft 여부와 무관하게 두 catalog에 항상 포함되어 action 공간이 옵션에 따라 달라지지 않는다(codec v79).
- 러너: `run_random_game(engine, config, game_seed, policy_seed)`이 FINISHED까지 실행해 `GameSimulation(state, standings, replay)`를 돌려준다. 디버그 CLI와 `run_random_round`는 의도적으로 한 라운드 단위를 유지한다.
- 처리량 기준(2026-08-30, 로컬 측정, 관측 v1 시점): env 경유 masked random full episode 약 4,100 agent step/s(매 step 전체 관측 인코딩 포함), `run_random_game` 직접 실행 약 48ms/판(약 9,000 step/s).

## 검증 기준

- 레이아웃 pin 테스트(`tests/adapters/test_observation_encoding.py`): 크기, 세그먼트 연속성, 버전.
- 전체 게임 인코딩 sweep: 두 룰셋의 random 완주 전 상태를 4개 관측자 전원으로 인코딩한다.
- env 테스트(`tests/adapters/test_pettingzoo_env.py`): PettingZoo api/seed 테스트, 전체 게임 episode의 zero-sum 승자독식 보상, truncation.
- 관측 경계 테스트(`tests/unit/test_observation.py`): 상대 identity 부재와 장수 공개 convention.
