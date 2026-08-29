# 개발 인수인계

기준일: 2026-08-30

이 문서는 새 개발 세션(Claude Code, Codex 등 어떤 도구든)에서 저장소의 현재
위치를 빠르게 복구하기 위한 진입점이다. 규칙의 규범 근거는 [`rules/README.md`](rules/README.md),
장기 마일스톤과 구현 순서는 [`implementation-plan.md`](implementation-plan.md),
카드별 세부 동작은
[`implementation-audits/personal-cards.md`](implementation-audits/personal-cards.md),
Leader 능력은 [`implementation-audits/leaders.md`](implementation-audits/leaders.md),
계약 경계는
[`implementation-audits/contracts.md`](implementation-audits/contracts.md)를
따른다.

## 세션 시작 체크리스트

1. 저장소 루트의 `AGENTS.md`(도구 중립 공통 지침), `CLAUDE.md`(Claude Code
   진입점), `README.md`, 이 문서, 그리고 [`lessons.md`](lessons.md)를 읽는다.
2. `git status --short`와 `git log --oneline -10`으로 작업 트리와 최근 구현을
   확인한다. 기존 변경은 사용자 작업으로 취급하고 덮어쓰지 않는다.
3. `uv sync --extra rl`로 Python 3.14 환경을 준비한다.
4. 아래 기준 검증을 실행한다.

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

2026-08-30의 기준 결과는 pytest 770개 통과, Ruff 통과, mypy 통과다. 현재 action
codec은 `ACTION_CODEC_VERSION = 77`(기본 4,143개, CHOAM 4,419개)이고, 관측은
`OBSERVATION_VERSION = 1`의 1,409-int 전체 게임 인코딩이다
([`rl-environment.md`](rl-environment.md)). `dune-imperium-sweep` 검증
sweep은 룰셋당 10,000판(총 20,000판)이 실패 0으로 통과한 상태다.

## 현재 구현 기준선

마지막 기능 커밋은 `24b13e7 Advance the Agent turn after an acquisition Spy
placement`이고, 그 앞에 M7 sweep 도구와 sweep이 적발한 버그 수정 커밋들이
있다.

- R0-M4는 완료됐다. 공식 규칙 자료, 엔진 커널, 4인 setup, 한 라운드 수직 조각,
  actor-neutral action codec과 PettingZoo AEC 계약이 있다.
- M5의 주요 시스템은 연결돼 있다. Influence/Friendship/Alliance, Agent와 Reveal,
  Spy/Infiltrate/Gather Intelligence, 개인 덱 reshuffle chance, Combat 순위와 보상,
  sandworm·Shield Wall·control, Makers·Recall, Endgame window와 게임 종료까지
  실행할 수 있다.
- 시작 카드 7종, Reserve 2종, 기본 Imperium 50종, CHOAM 전용 Imperium 4종 모두에
  완전한 play data가 있다(`implementation-audits/personal-cards.md`).
- CHOAM standard contract 20장의 시장·완료·보상과 CHOAM 전용 Imperium 4종이
  연결돼 있다(`implementation-audits/contracts.md`).
- Intrigue 44장은 39개 identity 전부가 effect DSL로 전사돼 실제 play된다
  (Intrigue 덱 완결). Plot은 소유자의 `turn`/`agent_effects`/`reveal` frame에서, Combat은
  `combat_intrigue` frame의 priority 보유 참가자에게 제시된다. 선택이 필요한
  효과는 `intrigue_choice` frame의 슬롯으로 순차 해결한다. Impress와 Inspire
  Awe의 비용 상한 획득은 `AcquireCardUpTo` 슬롯으로 Row/Reserve에서 가져오며,
  acquire box의 Spy 배치는 카드 해결 후 `acquisition_spy` frame을 재사용한다.
  Call to Arms와 Distraction은 face-up trigger 카드로, play하면 공개
  `intrigue_faceup` 존에서 대기한다. Call to Arms는 소유자의 Reveal turn
  획득마다 발동하고 그 Reveal 종료 시 만료되며, Distraction은
  `PlayerState.units_deployed_turn` 카운터가 3에 닿은 뒤 매 전이 후
  dispatcher가 `intrigue_trigger_spy` frame으로 제시하고 거절하면 face up으로
  남는다(OQ-016, `rules/intrigue_triggers.py`,
  `implementation-audits/intrigue.md`).
- Intrigue deck 고갈 시 모든 draw 지점이 `pending_intrigue_draws` 큐를 거쳐
  replayable reshuffle chance로 해결된다.
- 인쇄된 Leader 9종(기본 8 + CHOAM 전용 Shaddam)의 능력과 Signet Ring이 모두
  play된다(`rules/leader_abilities.py`, `implementation-audits/leaders.md`).
  Lady Jessica의 flip 면은 `PlayerState.leader_face_id`, memory는
  `memories`(troop 12개 불변식 포함), Feyd token은 `feyd_track_space`,
  Shaddam의 set-aside contract는 `GameState.sardaukar_contract_ids`로 공개
  관측된다. 2026-08-30에 standard Contract manifest를 수정했다: Sardaukar II
  (Agent recall 보상)가 20장에 속하고, 이전에 있던 세 번째 High Council
  타일은 Rise of Ix Tech 보상 타일의 오전사였다(`contracts.md` audit).
- 규칙 dispatcher는 `LEGAL_ACTION_PROVIDERS[FrameKind]`와 `ACTION_HANDLERS`
  두 표로 동작한다(`refactoring-plan.md`).
- 코어 상태 머신과 replay는 전체 게임을 지원한다. 200게임×8라운드 random
  soak이 약 11초, random 4인 게임 60판의 FINISHED 완주(창 240개, replay 검증
  포함)가 약 30초에 통과한다.
- `run_random_game`이 FINISHED까지 실행해 `GameSimulation(state, standings,
  replay)`를 돌려주고, `dune_imperium_uprising_v1` PettingZoo adapter는 전체
  게임을 한 episode로 실행한다(chance 내부 해결, 승자독식 zero-sum 종료 보상,
  1,409-int 관측, `choam_module`/`max_steps` 옵션). `run_random_round`와 debug
  CLI는 의도적으로 한 라운드 단위를 유지한다. 설계 근거는
  [`rl-environment.md`](rl-environment.md).
- 공식 Main, Board Guide, FAQ는 2026-08-27에 공식 리소스 페이지에서 다시
  내려받아 `scripts/official-rule-sources.json`의 SHA-256과 모두 일치함을 확인했다.

## 아직 완성되지 않은 경계

- Reveal turn 중 card가 hand에 들어가는 Plot(개인 card draw, Inspire Awe의
  조건부 hand 획득)은 FAQ p. 3의 즉시 공개 규칙이 구현되지 않아 Reveal에서
  제시하지 않는다(OQ-015(c)).
- `secrets`, `desert_tactics` board space는 board effect가 미구현이라 dispatcher가
  숨긴다(`board_effect_is_implemented`). Reverend Mother의 board repeat와
  Other Memories도 그 공간들에서는 그래서 아직 발생하지 않는다.
- Agent 배치 시점 조건이 거짓이면 pending되지 않는 카드 효과는, 같은 frame의
  자유 순서 효과로 조건이 나중에 참이 되어도 제시되지 않는다(알려진 엔진
  경계; Prepare the Way 수정 커밋 `87a9300` 참고).
- Objective와 battle icon 상호작용은 2026-08-30에 재감사를 마쳤다
  (`implementation-audits/objectives.md`, OQ-005 RESOLVED). Combat 다중 후보
  guard는 미래 콘텐츠 대비 tripwire로 남는다.
- Shaddam Corrino IV의 set-aside Sardaukar Contract 경로는 Leader 능력과 함께
  남아 있다. OQ-010, OQ-011 경계를 유지한다.
- 모든 미해결 규칙 질문과 프로젝트 convention(OQ-003, OQ-015 등)은
  [`rules/open-questions.md`](rules/open-questions.md)에 있으며, 공식 근거 없이
  코드로 임의 확정하면 안 된다. 규칙 동작을 바꾸기 전에는 반드시 `docs/rules/`의
  문장을 인용한다([`lessons.md`](lessons.md)).

따라서 현재 엔진을 "완전한 Uprising 게임"으로 간주하면 안 된다.

## 다음 구현 순서

1. **M11 사람용 플레이 인터페이스(로컬 웹 UI).** 2026-08-30에 M9·M10보다
   앞으로 순서를 바꿨다(`implementation-plan.md` 마일스톤 절 서두의 근거
   참고). 시작점 사실관계:
   - 형태는 로컬 웹 UI(로컬 서버 + 브라우저)로 확정했다. UI는 엔진 공개
     API(`reset`/`current_decision`/`legal_actions`/`apply`/`observe`)와
     `PlayerView`만 사용하고, 사람에게도 `PlayerView`만 보낸다(비공개 정보
     경계는 `core/observation.py`가 단독 결정, M7 sweep의 누출 검사로
     검증됨).
   - AI 상대는 `agents/random_agent.py`와 M11에서 새로 만드는 간단한 규칙
     기반 heuristic agent(같은 `choose_action(observation, legal_actions)`
     인터페이스)로 시작한다. 이 heuristic은 M9 baseline의 출발점으로
     재사용하고, M9·M10 뒤에 강한 agent로 갈아끼운다.
   - chance(덱 reshuffle)는 러너 패턴대로 seeded `ChanceResolver`로
     해결한다(`simulation/runner.py`). 저장/불러오기는 `GameReplay` 직렬화
     위에 만들고 불러오기는 `replay_game` 재현으로 검증한다. 직렬화 포맷은
     설계 결정으로 남아 있다.
   - 카드 이미지는 이용 조건 확정 전이므로 텍스트 표현을 기본으로 한다
     (AGENTS.md 이미지 정책). Leader 선택 UI는 OQ-007 미해결이라 ruleset
     option으로 명시한다. 현재 엔진 기본은 `DEFAULT_LEADER_IDS` 4종
     고정이다(`rules/engine.py`). web 스택 선택과 `ui` optional extra
     추가는 구현 시작 시 결정한다.
2. **M9 평가 러너와 baseline.** 여러 게임을 병렬 구동하고 정책 추론만
   batch하는 self-play 러너, random/heuristic(M11 상대에서 출발)/rollout
   baseline, 좌석·리더·first player·seed 교차 대회 도구
   (`implementation-plan.md`의 M9). 관측·보상 계약은
   [`rl-environment.md`](rl-environment.md)로 고정돼 있고, 병렬 실행 선례는
   `simulation/sweep.py`다.

각 묶음은 카드 이미지로 텍스트를 검증하고(`docs/card-data-sources.md`의 방법),
`Play ...` / `Document ...` 커밋 쌍을 유지하며, 새 결정 경계는
`FrameKind` → frame `kind` → dispatcher 표 → codec 순으로 추가한다.
핸드오프의 카드 요약은 이미지 검증 전 참고일 뿐이다(Impress 비용, Spring the
Trap 유형을 잘못 적었던 전례가 있다).

## 코드 탐색 지도

| 목적 | 주요 위치 |
| --- | --- |
| 카드 manifest와 typed 효과 | `src/dune_imperium/content/uprising/` (Leader identity·Feyd track은 `leaders.py`) |
| Leader 능력과 Signet Ring | `src/dune_imperium/rules/leader_abilities.py`, reach-2 보너스는 `rules/influence.py`, Smuggle Spice는 `rules/agent_turn.py` |
| Agent 배치와 카드 효과 | `src/dune_imperium/rules/agent_turn.py`, `agent_effects.py` |
| Reveal과 acquire | `src/dune_imperium/rules/reveal_turn.py`, `acquisition.py` |
| phase·Combat·Endgame | `src/dune_imperium/rules/phases.py`, `combat.py`, `endgame.py` |
| dispatcher 표와 frame kind | `src/dune_imperium/rules/engine.py`, `frames.py`, `agent_effect_frame.py` |
| effect DSL과 Intrigue | `content/uprising/effect_dsl.py`, `intrigue.py`, `rules/effect_interpreter.py`, `rules/intrigue.py`, `rules/intrigue_deck.py`, `rules/intrigue_triggers.py` |
| 고정 action catalog | `src/dune_imperium/adapters/action_codec.py` |
| 관측과 PettingZoo | `src/dune_imperium/core/observation.py`, `adapters/observation_encoding.py`, `adapters/pettingzoo_env.py` |
| replay와 random 러너 | `src/dune_imperium/core/replay.py`, `simulation/runner.py` (한 라운드·전체 게임) |
| 검증 sweep과 불변식 | `src/dune_imperium/simulation/sweep.py`, `simulation/invariants.py`, `cli/sweep.py` |
| 카드별 회귀 테스트 | `tests/unit/content/`, `tests/unit/rules/` |
| 통합·adapter 테스트 | `tests/integration/`, `tests/adapters/` |

개인 카드 draw·Spy·Combat·Endgame의 민감한 설계 결정은
`docs/implementation-audits/`의 주제별 문서를 먼저 확인한다.

## 처리량 메모

`RulesEngine.verify_input_immutability`는 매 전이마다 state 전체를 canonical
hash하는 디버그 가드라 기본 off다(켜면 random play가 약 70 step/s, 끄면 약
3,000 step/s). 커널 테스트 엔진만 이를 켠다. 완주 soak은 이제
`run_random_game`(약 48ms/판, 9,000 step/s)이나, 불변식·누출 검사와 replay
검증까지 포함하는 `dune-imperium-sweep`(검사 전부 켠 단일 프로세스 약
175ms/판, `--workers 8`로 약 50 games/s)을 그대로 쓴다. env 경유 masked
random full episode는 약 4,100 agent step/s다.

## 유용한 명령

```bash
# 검증 sweep: 카드 보존·교착·관측 누출·replay 검사 (룰셋당 100판 기본)
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8

# 한 라운드 random 실행
uv run dune-imperium-debug --seed 2 --random-policy-seed 1002

# 대화형 한 라운드 실행
uv run dune-imperium-debug --seed 2

# 명시적으로 준비한 DIU working copy와 identity/effect shape 대조
uv run dune-imperium-audit-diu ../DIU/data/imperium.JSON

# 공식 PDF와 고정 checksum 재검증; 생성물은 /tmp에만 둔다
uv run scripts/prepare_official_rules.py
```

sandbox에서 uv cache 쓰기가 제한되면 명령 앞에
`UV_CACHE_DIR=/tmp/dune-uv-cache`를 붙인다.

## 원격 저장소 인계 주의

2026-08-30 Shaddam 세션 종료 시점 기준 `origin/master`는 `707392d`이고, 로컬
`master`에는 그 뒤 Intrigue 완결 슬라이스, 2026-08-29 Leader 묶음(기본 8종,
`e6539ee`~`5ffa1bf`), 그리고 2026-08-30 Shaddam 묶음(Contract manifest 수정
`5bfd2a5`, Shaddam `ac75530`, 문서 `4fc0e9d`)과 핸드오프 갱신 커밋들이
순서대로 있다. 그 뒤에 2026-08-30 Objective 감사 묶음(지불 frame 수정
`fa99359`, 감사 문서 `1d97903`), 전체 게임 RL 전환 묶음(러너 `636fe9e`,
관측 인코딩 `efc4a11`+`4b50412`, Espionage 수정 `4d9efb8`, env 전환
`95ad278`), 그리고 M7 sweep 묶음(도구 `3bafc67`, sweep이 적발한 수정
`f148c14`+`83aa4f5`+`24b13e7`, 문서 커밋)이 있다. 새 세션은
`git log origin/master..master`로 push 여부를 확인한다. checkout이 M7
묶음보다 이전이면 이 문서의 770개 테스트·sweep 기준선이 실제 코드와
일치하지 않는다.

## 2026-08-30 계획 조정

- M11(사람용 플레이 인터페이스)을 M9·M10보다 앞으로 옮겼다. 근거와 순서
  방침(번호 유지, 나열 순서 = 구현 순서)은 `implementation-plan.md` 마일스톤
  절 서두에 있다. UI 형태는 로컬 웹 UI로, 초기 AI 상대는 random + 간단
  heuristic(M9 재사용)으로 확정했다.

## 2026-08-30 M7 검증 sweep 세션 요약

- `dune-imperium-sweep`을 만들었다(`simulation/sweep.py`, `invariants.py`,
  `cli/sweep.py`): 매 전이의 전역 카드 census(개인 카드 instance 집합,
  Reserve 스택+생존 사본 방정식, Intrigue·Conflict·Contract·Objective 보존과
  단일 존), 교착 검출, 표본 주기의 관측 누출 검사(deck 순서·상대 hand·상대
  Intrigue `[Main p. 7]`·Contract bank `[Main p. 16]`만 뒤섞은 상태와 관측
  동일성; 뒤섞기가 실제로 상태를 바꾸는지도 테스트로 고정), replay 검증,
  multiprocessing 병렬화와 CLI. pytest에 고정 seed 테스트 8건을 추가했다.
- 첫 룰셋당 10,000판 sweep이 46판(0.23%)에서 잠복 버그 다섯 계열을
  적발했고, 모두 해결 시점 판정 원칙(`[Main pp. 9, 20]`, `[Main p. 12]`)으로
  수정했다: Spy Network recall 교착(`f148c14`), Maker Keeper·Wheels Within
  Wheels·Bond 3종 조건 drift와 Corrinth City 선택 소실과 self-trash 보류
  효과(`83aa4f5`, OQ-022 convention 신설), Price is No Object 획득 Spy
  frame 정지(`24b13e7`).
- 수정 후 재실행한 룰셋당 10,000판(총 20,000판, 모든 검사+replay 포함)이
  실패 0으로 통과했다: 400초, 50 games/s, 전이 약 879만 회, 라운드
  중앙값 10. M7을 완료로 표시했다.

## 2026-08-30 전체 게임 RL 전환 세션 요약

- 설계 확정([`rl-environment.md`](rl-environment.md)): 관측 v1은 PlayerView
  순수 함수인 1,409-int 평면 벡터(세그먼트 표 export, egocentric 좌석 회전,
  identity 카운트/슬롯/tri-state), 보상은 승자독식 zero-sum 종료 보상만,
  chance는 env 내부 seeded 해결. 상대 hand·deck·discard·Intrigue 장수 공개를
  OQ-010 부분 convention으로 기록했다.
- `run_random_game` 러너(`GameSimulation(state, standings, replay)`)와
  `dune_imperium_uprising_v1` env 전환을 구현했다. per-step VP delta 보상은
  제거했고 종료 `infos`에 rank·VP를 노출한다. codec은 v77 그대로다.
- PlayerView에 결정 frame 요약(kind·결정 소유자·turn 소유자)과 공개 존
  장수를 추가했다. frame별 세부 컨텍스트 공개는 kind별 화이트리스트 검토
  후로 미뤘다.
- random 전체 게임에서 기존 엔진 버그를 하나 더 수정했다(`4d9efb8`):
  Espionage recall 뒤 자유 순서 효과가 그 Spy를 소비하면 배치가 crash하던
  것을 해결 시점 supply 재확인과 recall 재개방으로 바꿨고(`[Main pp. 11,
  20]`, Agent-card Spy 경로와 동일 패턴), supply 0에서 decline이 빠져 있던
  것도 인쇄 효과의 선택성(`[Board Guide p. 1]`)에 따라 복원했다.
- 검증: env 경유 18판(기본 12+CHOAM 6) random full episode soak에서 승자독식
  zero-sum 보상 불변식을 확인했고(약 4,100 agent step/s), 두 룰셋의 random
  완주 전 상태 인코딩 sweep, PettingZoo api/seed 테스트, 755개 테스트·Ruff·
  mypy가 통과한다.

## 2026-08-30 Objective 감사 세션 요약

- 핸드오프의 "남은 Objective 상호작용 재감사"를 완료했다. setup 배정, Combat
  즉시 icon matching, Endgame wild matching, Endgame Intrigue의
  `FlipBattleCard`(Objective 제외, wild 대체 허용), 관측 공개 범위가 규칙
  문서와 일관됨을 확인하고 `implementation-audits/objectives.md`에 기록했다.
- OQ-005를 RESOLVED로 갱신했다: Combat 즉시 matching은 의무 pair가 도착
  즉시 해소되므로 공식 콘텐츠에서 printed icon당 face-up 한 장을 넘을 수
  없고(wild는 Propaganda 한 장뿐), Endgame wild의 복수 후보 선택은 OQ-001
  window의 소유자 행동으로 이미 구현돼 있다. Combat 다중 후보
  `NotImplementedError`는 미래 콘텐츠 tripwire로 유지한다.
- 감사 soak에서 기존 엔진 버그를 발견해 수정했다(`fa99359`): Junction
  Headquarters의 Intrigue+Spice 지불 frame이 `pending_agent_effect`를
  해제하지 않아 화살표를 반복 지불할 수 있었고(한 턴 한 번 규칙 위반
  `[Main p. 9]` `[FAQ p. 3]`), 지불 뒤 Spice가 2 미만이면 다음 legal-action
  열거가 RuntimeError로 crash했다(seed 20010). 아울러 세 지불 legal
  provider(Junction HQ, Ecological Testing Station/Smuggler's Haven,
  Corrinth City)가 큐 후 지불 불가 상태에서 raise하던 것을 자유 순서
  해결 시점 판정 `[Main pp. 9, 20]`에 따라 decline만 제시하도록 바꿨다
  (Prepare the Way `87a9300`과 같은 판정 방식, 회귀 테스트 4건).
- 검증: 기본 60판 + CHOAM 20판 random FINISHED 완주 soak(replay 검증,
  매 전이 face-up 불변식 assert)에서 즉시 pair 181/62회, Endgame wild
  32/8회, Endgame Intrigue flip 1/0회 발동을 확인했다. endgame·combat 감사
  문서의 창 이전 서술과 Combat Intrigue/Shield Wall 잔재 서술도 현재 구현에
  맞게 갱신했다.

## 2026-08-30 Shaddam 세션 요약

- standard Contract manifest를 교정했다: 6인 보충 규칙의 base-CHOAM setup이
  "두 Sardaukar contract"를 set aside하라고 지시하므로 Sardaukar 2장이 20장에
  속하고, 공간별 구성 합산과 타일 이미지의 Rise of Ix Tech 보상으로 이전
  세 번째 High Council 타일이 RoI jumpstart 타일의 오전사임을 확정했다.
  Sardaukar II의 Agent recall 보상(`[Main p. 20]`의 방금-보낸-Agent 제외)을
  `CONTRACT_REWARD_RECALL` frame으로 연결했다(codec v76).
- Shaddam Corrino IV를 구현해 인쇄된 Leader 9종을 완결했다: Sardaukar
  Commander의 setup set-aside와 시장 frame 내 전용 선택(시장 보충 없음,
  고갈 시 2 Solari 전환은 OQ-021 convention), Emperor of the Known
  Universe의 (Solari+troop | 3 Solari→Influence) 선택과 배치 즉시 발효되는
  turn 한정 unit 배치 차단(Combat 배치·Maker 소환·Intrigue 배치 option·
  SummonSandworm 무효)이다(codec v77).
- 검증: Shaddam 포함 CHOAM 조합 30판 random FINISHED 완주 soak에서 set-aside
  take 27회, signet 선택 85회, contract Agent recall 발동을 확인했고 기본
  조합 25판 회귀와 replay 검증을 통과했다.

## 2026-08-29 Leader 세션 요약

- 기본 게임 Leader 8종의 능력과 Signet Ring을 카드 이미지로 검증해 모두
  구현했다(codec v72→v75, 테스트 668→727). space 유형 아이콘(City 파란 원,
  Landsraad 초록 오각형)은 Board Space Guide artwork로 확정했다.
- Gurney(Warmaster recruit, Always Smiling 문턱 6), Amber(Fill Coffers,
  Desert Scouts retreat), Feyd(분기형 Personal Training 트랙과 Devious
  Strength), Jessica 양면(Spice Agony memory, Other Memories flip,
  Water of Life, Reverend Mother board repeat), Margot(Loyalty, City Spy),
  Muad'Dib(Lead the Way, Unpredictable Foe), Irulan(Imperial Birthright,
  Chronicler's Insight), Staban(Limited Allies 9장 덱, Smuggle Spice,
  Unseen Network)이다. 세부와 근거는 `implementation-audits/leaders.md`.
- 새 convention 4건을 OQ-017~OQ-020으로 기록했다(Feyd 맨 오른쪽 칸 무보상,
  memory 0개 flip 허용, Reverend Mother 반복의 Influence 제외
  `[Main p. 7]`, Always Smiling 미회수).
- 기존 버그 수정: Prepare the Way(그리고 Hidden Missive)의 조건부 Agent
  효과가 배치와 해결 사이 Influence 하락 시 legal로 제시된 뒤 실패하던 것을
  해결 시점 판정의 우아한 무효(no-op)로 바꿨다(`87a9300`,
  docs/rules/player-turns.md의 자유 순서 조건 판정 문장 인용).
- 검증: Leader 4종 기본 조합 60판 + 신규 4종 조합 25판 random FINISHED 완주
  soak(replay 검증 포함)에서 모든 신규 경로의 발동을 이벤트 수로 확인했다.

## 2026-08-29 세션 요약

- Impress(Combat: 검 2 + 비용 3 이하 획득)와 Inspire Awe(Plot: 비용 3 이하 획득,
  sandworm이 Conflict에 있으면 hand로)를 카드 이미지로 검증해 전사했다. 이전
  핸드오프의 "Impress 비용 4"는 오기였다.
- `AcquireCardUpTo(max_cost, to_hand_if)` DSL 보상과 `acquire_intrigue_imperium`
  / `acquire_intrigue_reserve` 선택 슬롯을 추가했다. Row 보충, acquire box 즉시
  처리, Spy 배치 box의 `acquisition_spy` frame 재사용(카드 해결 후 push),
  Contract 완료 확인을 기존 획득 경로와 공유한다. codec v65.
- Reveal 중 hand로 들어가는 획득은 OQ-015(c)를 확장해 draw와 동일하게 보류한다.
- Call to Arms를 첫 face-up trigger로 전사했다: `IntrigueOption.trigger`,
  공개 `PlayerState.intrigue_faceup` 존, `rules/intrigue_triggers.py`의
  Reveal 획득 발동과 Reveal 종료 만료(OQ-016), codec v66. Distraction과
  Leverage의 카드 이미지 검증도 마쳤다(Leverage 보상에 대한 DIU의 "덱 draw"
  기록은 Contract 아이콘 오독이며, Reach Agreement 아이콘과 대조해 확정).
- Distraction을 배치 trigger로 전사했다: `PlayerState.units_deployed_turn`
  카운터(6개 배치 지점, Control defense 제외), dispatcher 전이 후
  `intrigue_trigger_spy` frame 제시, 다른 플레이어 Spy가 있는 post에의 공유
  배치와 recall-first, 거절 시 face-up 유지(OQ-016(c)), codec v67.
- Leverage를 play 시점 조건으로 전사했다: `spice_at_turn_start` 스냅샷 +
  `spice_spent_turn` 카운터(지출 5지점)로 "이번 turn 총 획득 spice"를
  계산하고, 조건 성립 시 Contract 1 + Solari 1을 준다. Harvest의 placement
  기준 회계와는 분리 유지. codec v68.
- Endgame Intrigue window(OQ-001 convention)를 열었다: First Player부터
  시계 방향 1회 순회, window 안에서 Endgame play와 wild matching 자유 순서,
  pass가 창을 닫고 마지막 pass가 게임을 끝낸다. 기존 단일 무모호 wild 자동
  경로와 `declined_endgame_wild_card_ids`를 대체했다(codec v69). 이어서
  Endgame 6종(Crysknife, Desert Mouse, Ornithopter의 spice/flip 이중 절반,
  CHOAM Profits, Secure Spice Trade, Shadow Alliance)을 전사했다(codec v70).
  Shadow Alliance의 "상대가 Alliance를 보유한 트랙" 조건을 DIU가 누락한 것을
  카드 이미지로 확인해 기록했고, 조건 DSL이 전체 상태를 읽도록 바꿨다.
  random 4인 게임 60판이 처음으로 FINISHED까지 완주됐다(창 240개, wild 27회,
  replay 검증 통과).
- Manipulate와 Spring the Trap을 전사해 Intrigue 39개 identity(44장)를
  완결했다. Spring the Trap은 Spy 2 recall → 검 7(기존 primitive), Manipulate는
  `SetAsideImperiumRowCard` 슬롯 + 공개 `imperium_set_aside` 존 + Reveal 한정
  할인 획득 + Reveal 종료 시 `imperium_removed`로 게임 제거(FAQ p. 3).
  codec v71. random 완주 60판에서 set-aside 21회 = 획득 2 + 만료 19로 보존이
  검산됐다. 참고: 기존 Prepare the Way 버그(별도 작업)는 신규 카드로 legal
  action 목록이 바뀌며 최신 soak의 seed 10146 궤적에서는 더 이상 나타나지
  않지만, `ed16d93`에서 그대로 재현된다.
- 알려진 기존 버그(이번 슬라이스와 무관, HEAD `ed16d93`에서 재현): 4인 기본
  룰셋 seed 10146 random play에서 Prepare the Way를 Agent 카드로 낼 때
  `resolve_agent_card_effect`가 legal로 제시된 뒤 적용 시
  "conditional Agent effect is not available"로 실패한다. legal 제공자와
  `rules/agent_effects.py:1523` resolver의 조건 판정 불일치로 보이며, 별도
  수정 작업으로 분리했다.

## 2026-08-28 세션 요약

- Codex → Claude Code 전환. `AGENTS.md`를 도구 중립으로, `CLAUDE.md`를 진입점으로.
- 리팩토링 A·B: `DecisionFrame.kind`, `rules/frames.py`, 표 기반 dispatcher. 그
  과정에서 Covert Operation deadlock, Reserve copy ID 재발급, Spy 공급 판정 버그
  수정.
- effect DSL(C 단계)과 Intrigue: Plot 19종·Combat 10종, 선택 슬롯 frame, Intrigue
  draw 공통 reshuffle 경계, OQ-003·OQ-015 convention.
- 처리량: 입력 불변 hash 가드를 opt-in으로 바꿔 random play 약 45배 가속.
- 코드 리뷰(`/code-review`) 후속 항목은 `refactoring-plan.md` 끝에 있다.
- 교훈: 리뷰 지적을 규칙 문서 확인 없이 반영해 Harvest 계약 판정을 잘못 바꿨다가
  되돌림 → `lessons.md`, `AGENTS.md` 규칙 인용 의무.
