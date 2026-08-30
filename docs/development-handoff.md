# 개발 인수인계

기준일: 2026-08-31

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
3. `uv sync --extra rl --extra ui`로 Python 3.14 환경을 준비한다(`ui`는
   FastAPI 서버 의존성; 없으면 `tests/server/test_app.py`가 skip된다).
4. 아래 기준 검증을 실행한다.

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

2026-08-31의 기준 결과는 pytest 833개 통과, Ruff 통과, mypy 통과다. 현재 action
codec은 `ACTION_CODEC_VERSION = 79`(기본 4,152개, CHOAM 4,429개)이고, 관측은
`OBSERVATION_VERSION = 2`의 1,415-int 전체 게임 인코딩이다
([`rl-environment.md`](rl-environment.md)). `dune-imperium-sweep` 검증
sweep은 random policy 룰셋당 10,000판(총 20,000판), heuristic policy
룰셋당 1,000판, 그리고 `--leader-draft` 켠 두 policy 각 룰셋당 500판이
모두 실패 0으로 통과한 상태다.

## 현재 구현 기준선

마지막 기능 커밋은 `42be883`(브라우저 UI, M11 슬라이스 4)이고, 그 앞에
FastAPI 세션 서버 `4fbd751`, Leader draft `c0c1795`, Treacherous Maneuver
OQ-022 수정 `d70b353`, 슬라이스 1 묶음(`1a449f4`+`7a53c8f`+`ac4d6d4`)이
있다. 마일스톤 현황: **R0~M8 완료**(M6 콘텐츠, M7 완주 검증, M8 CHOAM),
**진행 중 M11**(계획 조정으로 M9·M10보다 선행, 슬라이스 1~4 완료, 남은
것은 슬라이스 5 저장/불러오기·replay 검토).

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
- 코어 상태 머신과 replay는 전체 게임을 지원한다. `dune-imperium-sweep`으로
  룰셋당 10,000판(총 20,000판) random 완주 sweep(매 전이 카드 보존·교착
  검사, 표본 주기 관측 누출 검사, 게임별 replay 검증)이 실패 0으로
  통과했다(2026-08-30, 400초/50 games/s).
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
     (AGENTS.md 이미지 정책). Leader 선택은 OQ-007의 **6종 공개 draft
     convention**(2026-08-30 확정: 합법 Leader 중 무작위 6종 즉시 공개 →
     First Player 확정 뒤 turn 역순 pick, First Player가 마지막, 전부 공개)
     을 ruleset option으로 구현한다. 현재 엔진 기본인 `DEFAULT_LEADER_IDS`
     4종 고정(`rules/engine.py`)은 테스트·sweep 재현성용으로 유지한다. web
     스택 선택과 `ui` optional extra 추가는 구현 시작 시 결정한다.
   - 제안 착수 슬라이스 순서(각각 검증·커밋 단위):
     1. ~~간단한 규칙 기반 heuristic agent + 단위 테스트~~ — **완료**
        (`1a449f4`, 2026-08-30). `agents/heuristic_agent.py`의
        `HeuristicAgent`(점수 기반 선택 + seeded tie-break, M9 baseline
        재사용을 docstring에 명시), `Agent` Protocol(`agents/base.py`),
        `run_policy_game` 러너 일반화, sweep `--policy {random,heuristic}`.
        heuristic soak이 엔진 잠복 버그 두 계열을 적발해 함께 수정했다
        (`7a53c8f`, `ac4d6d4`; 아래 세션 요약).
     2. ~~Leader draft convention을 엔진 setup에 구현~~ — **완료**
        (`c0c1795`, 2026-08-30). `RulesetConfig(leader_draft=True)` ruleset
        option, `FrameKind.LEADER_DRAFT` frame과 dispatcher 표, codec
        v79의 `pick_leader` 템플릿(두 catalog 상시 포함), 관측 v2의 공개
        pool 세그먼트, PettingZoo `leader_draft` 옵션, sweep
        `--leader-draft`. 세부는 OQ-007 구현 노트와 아래 세션 요약.
     3. ~~web 스택 결정 + 게임 세션 서버~~ — **완료**(`4fbd751`,
        2026-08-31). 스택은 **FastAPI + uvicorn**(`ui` optional extra,
        `dune-imperium-server` CLI). `server/sessions.py`의 프레임워크
        중립 `GameSessionManager`가 엔진 공개 API + seeded
        `ChanceResolver`만으로 세션을 구동하고(서버 자체 규칙 로직 없음),
        `server/app.py`가 JSON HTTP로 노출한다. 세부는 아래 세션 요약.
     4. ~~최소 브라우저 UI~~ — **완료**(`42be883`, 2026-08-31). 의존성
        없는 vanilla HTML/JS 단일 페이지(`server/static/`)를 서버 루트에서
        서빙하고, `/catalog`가 인쇄된 표시 데이터(카드 이름·비용·설득·검·
        Faction·아이콘, Intrigue timing, Leader 능력명, 공간 이름)를
        제공한다. 설정(좌석·CHOAM·draft·seed)부터 결정 frame kind별
        프롬프트, index 버튼 행동 적용, hot-seat 좌석 전환, 최종 순위까지
        실제 브라우저에서 완주 검증했다. 세부는 아래 세션 요약.
     5. **저장/불러오기 + 종료 후 replay 검토 화면 — 다음 작업.**
        시작점 사실관계:
        - 저장 대상은 `core/replay.py`의 `GameReplay`: `ruleset:
          RulesetConfig`(players·choam_module·leader_draft), `seed`,
          `steps: tuple[DomainAction | ChanceOutcome, ...]`,
          `expected_state_hash`, 버전 필드 3개. 주의 — 러너·세션은 버전
          필드를 기본값으로 두는데 `action_codec_version` 기본값 20은
          오래된 값이다. 직렬화 슬라이스에서 실제 `ACTION_CODEC_VERSION`
          스탬프와 불러오기 시 버전 검증을 같이 넣는 것이 자연스럽다.
        - 서버 세션(`server/sessions.py`)은 이미 모든 적용 step을
          `GameSession.steps`에 replay 형식으로 기록한다. 저장 = 그 시점
          steps + `canonical_state_hash(state)`로 `GameReplay` 구성 →
          JSON 직렬화. dataclass→JSON 변환 선례는 `core/state.py`의
          `_canonicalize`(hash용)와 `server/sessions.py`의 `_jsonify`.
          `DomainAction`/`ChanceOutcome` 구분 필드가 스키마에 필요하다.
        - 불러오기 = 역직렬화 → `replay_game(engine, replay)` 재현
          검증(불일치 시 `ReplayMismatchError`) → 새 `GameSession`으로
          계속. **미결 설계**: 이어하기의 chance 흐름. 원 세션의
          `ChanceResolver`는 seed에서 순차 소비된 RNG 스트림이므로 (a)
          `random.Random.getstate()`를 함께 저장해 복원하거나 (b) "불러온
          게임은 seed 기반 새 chance 스트림" convention을 명시(결정론은
          유지되나 저장 전과 이후 셔플이 달라질 수 있음) 중 하나를
          슬라이스에서 결정하고 문서화한다.
        - replay 검토 화면은 서버가 replay를 step 단위로 다시 적용해
          시점별 상태를 제공하는 방식이 자연스럽다(엔진 공개 API만).
          검토도 비공개 경계를 유지한다 — 사람 좌석의 `PlayerView` 시점
          재생으로 시작하고, 종료 후 전체 공개 여부는 별도 결정으로
          남긴다(OQ-010 열람 범위 질문과 연결됨).
        - 저장 위치(서버 로컬 파일 vs 브라우저 다운로드/업로드)는 구현
          시작 시 결정한다.
        슬라이스 5가 끝나면 M11 완료 조건(사람이 설정부터 최종 점수까지
        안정적으로 완전한 게임을 플레이)을 판정하고 M9로 넘어간다.
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

# 같은 sweep을 heuristic baseline으로 (M11 사람용 상대와 동일 정책)
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8 --policy heuristic

# OQ-007 6-Leader 공개 draft setup으로 완주 검사
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8 --leader-draft

# 로컬 플레이 서버 (ui extra 필요; 기본 http://127.0.0.1:8000)
uv run dune-imperium-server

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

2026-08-31 세션 마무리 기준 로컬 `master`와 `origin/master`는 동기화돼
있다(사용자 지시로 슬라이스 1~4와 이 핸드오프 정리까지 push함; 이후에도
push는 사용자 판단으로 한다). 새 세션은 `git log origin/master..master`로
확인하고, checkout이 `42be883`보다 이전이면 이 문서의 833개 테스트·codec
v79·관측 v2·서버·UI 기준선이 실제 코드와 일치하지 않는다.

## 2026-08-31 M11 슬라이스 4 세션 요약 (브라우저 UI)

- 의존성 없는 vanilla HTML/CSS/JS 단일 페이지를 `server/static/`에 두고
  FastAPI가 `/`(index)와 `/static/*`으로 서빙한다(`42be883`). 클라이언트는
  서버의 summary/`PlayerView`/actions/catalog payload만 렌더링하며 규칙
  지식을 갖지 않는다.
- `/catalog` endpoint(`server/catalog.py`, 프레임워크 중립)가 콘텐츠
  manifest의 인쇄된 공개 표시 데이터를 제공한다: 개인 카드 63종의
  이름·획득 비용·설득·검·Faction·Agent 아이콘, Intrigue 39종의 이름과
  option timing, Contract·Conflict·Leader(능력명 포함)·보드 공간·Objective
  이름. instance id → 카드 id 해석은 클라이언트의 접두사 파싱으로 한다.
- 화면: 설정(좌석별 사람/휴리스틱/랜덤, CHOAM, OQ-007 draft 기본 켬,
  seed, 진행 중 게임 이어서 열기) → 게임(결정 프롬프트 + frame kind +
  결정 좌석, index 기반 행동 버튼, 보드 존—draft pool·Conflict·Imperium
  Row·Reserve·Contract 시장·maker spice·Intrigue discard, 좌석 4개 공개
  패널, 내 hand/discard/Intrigue 비공개 패널) → 종료 시 최종 순위 표.
  여러 사람 좌석은 결정 좌석을 따라가는 hot-seat으로 처리한다.
- 검증: 실제 uvicorn + 브라우저에서 폼으로 draft 게임을 만들고(설정 화면
  → Leader pick 클릭 → 라운드 1 turn frame), UI 자체 행동 버튼 경로로
  103회 결정을 자동 구동해 10라운드 최종 순위까지 완주했다(서버 로그 오류
  0). `/catalog`·정적 서빙 테스트를 추가해 pytest 829→833, Ruff, mypy
  통과.

## 2026-08-31 M11 슬라이스 3 세션 요약 (FastAPI 게임 세션 서버)

- web 스택을 **FastAPI + uvicorn**으로 확정하고 `ui` optional extra와
  `dune-imperium-server` CLI(기본 127.0.0.1:8000)를 추가했다(`4fbd751`).
  개발 환경 준비 명령은 `uv sync --extra rl --extra ui`로 바뀌었다
  (TestClient용 `httpx2`는 dev group).
- `server/sessions.py`의 `GameSessionManager`는 프레임워크 중립이다. 게임
  생성은 좌석 배정(`human`/`heuristic`/`random`), `choam_module`,
  `leader_draft`, seed(미지정 시 SystemRandom, policy seed 기본은 sweep과
  같은 700,000+game_seed)를 받고, 엔진 공개 API(`reset`/
  `current_decision`/`legal_actions`/`apply`/`observe`)와 러너 패턴의
  seeded `ChanceResolver`만 사용한다. chance와 AI 좌석은 생성 직후와 사람
  행동 뒤 자동 진행되어 세션은 항상 사람 결정 또는 종료 순위에서 멈춘다.
  적용된 모든 step은 슬라이스 5(저장/불러오기)를 위해 replay 형식으로
  기록한다.
- 비공개 경계: 사람은 자기 좌석의 직렬화된 `PlayerView`와 revision 가드가
  붙은 index 기반 합법 행동 목록만 받는다. 둘 다 비공개 카드 identity를
  담을 수 있으므로 AI 좌석 조회는 `SeatAccessError`(HTTP 403)로 거부하고,
  `state.event_log`는 PlayerView 밖이므로 노출하지 않는다(가시성 결정은
  계속 `core/observation.py` 단독).
- HTTP 매핑: 미존재 게임 404, 비인간 좌석 403, revision 불일치 409, 기타
  잘못된 요청 400, pydantic 형식 오류 422. endpoint는 게임
  생성/목록/요약/좌석 view/좌석 행동 목록/행동 적용/삭제다.
- 검증: 세션 단위 테스트 9건(전원 AI 생성 즉시 완주와 seed 재현, 사람
  좌석 정지, index 행동 2,000 step 완주, draft 시작 frame, 좌석·seed
  검증, 삭제)과 HTTP 테스트 7건(4인 사람 draft 게임을 API로 라운드 1까지
  진행 포함). 실제 uvicorn 기동 + curl 왕복도 확인했다. pytest 813→829,
  Ruff, mypy 통과.

## 2026-08-30 M11 슬라이스 2 세션 요약 (Leader draft)

- OQ-007의 6-Leader 공개 draft convention을 `RulesetConfig(leader_draft=
  True)` ruleset option으로 구현했다(`c0c1795`). reset이 pick과 무관한
  setup chance(Conflict tier, Objective→First Player, 공개 pool 6종,
  Imperium·Intrigue·Contract 전체 셔플, 시작 덱 전체 셔플)를 seeded로
  모두 해결한 뒤 `GamePhase.SETUP`의 `leader_draft` frame에서 멈춘다.
  pick은 라운드 1 turn 역순(First Player 마지막)의 player decision이고,
  pick마다 setup face 배정과 인쇄된 시작 카드 제거(이미 섞인 덱 필터링 —
  남은 순서 균등성 유지)를 적용하며, 마지막 pick이 Contract 시장을
  배분한다(Shaddam pick 시 Sardaukar 2장 set-aside). 고정
  `DEFAULT_LEADER_IDS` 경로는 그대로다.
- action 공간은 옵션과 무관하게 고정이다: `pick_leader` 템플릿을 두
  catalog에 상시 포함해 codec v79(기본 4,152, CHOAM 4,429). 관측은 v2로
  올려 공개 pool 6-슬롯 세그먼트를 추가했다(1,415-int; pick 결과는 기존
  좌석 Leader 슬롯). PettingZoo env에 `leader_draft` 옵션을 추가했고,
  draft episode는 pick 결정으로 시작한다.
- sweep은 census를 setup 종료 시점에 고정하도록 바꿨다(draft 중 Staban의
  Limited Allies가 시작 카드를 정당하게 제거하므로). `--leader-draft`
  플래그를 추가했다.
- draft soak(두 policy × 두 룰셋 × 500판)이 기존 엔진 버그를 하나 더
  적발해 수정했다(`d70b353`, CHOAM seed 198): Treacherous Maneuver를 낸 뒤
  Cunning의 자유 순서 trash slot으로 그 카드 자체가 trash되면 Agent box
  해결이 무조건 self-trash를 실행해 crash했다. 기록된 OQ-022 convention
  (self-trash는 이미 충족, 나머지 효과는 해결)을 `apply_agent_card_trash`
  에도 적용했다.
- 검증: 수정 후 draft soak 총 2,000판(heuristic 1,000 + random 1,000,
  모든 불변식·replay 검사) 실패 0, 비-draft heuristic 400판 회귀 통과.
  pytest 796→813, Ruff, mypy 통과.

## 2026-08-30 M11 슬라이스 1 세션 요약 (heuristic agent)

- M11 슬라이스 1을 완료했다(`1a449f4`): `HeuristicAgent`는 RandomAgent와
  같은 `choose_action(observation, legal_actions)` 계약으로, 합법 행동을
  정적 전략 점수(직접 VP > 영구 업그레이드 > 비용 비례 획득 > 최대 배치,
  decline/pass 최하)로 순위 매기고 동점은 seeded RNG로 깬다. 미지의 action
  id는 0점이라 새 콘텐츠에서 seeded random으로 degrade한다. 점수는 규칙
  판정이 아니라 전략 선호이며 공개 카드 비용만 참조한다.
  `agents/base.py`의 `Agent` Protocol, `run_policy_game`(좌석별 agent 주입,
  `run_random_game`이 위임), sweep/CLI의 `--policy {random,heuristic}`을
  함께 추가했다.
- heuristic soak(룰셋당 1,000판)이 random 10,000판이 못 가던 궤적에서 잠복
  버그 두 계열을 적발했고, 공식 문서 확인 뒤 수정했다:
  - **Special Mission PlaceSpy slot 교착**(`7a53c8f`, CHOAM seed 97·901):
    play 시점 판정이 "자기 Spy recall = post 해방"으로 계산했지만 다른
    플레이어 Spy가 공유한 post는 recall해도 비지 않고, slot은 도움 안 되는
    recall만 무한 제시하다 행동 0개로 좌초했다. `[Main p. 11]`의 "비어 있는
    post", "먼저 자기 Spy **하나**를 recall**할 수 있다**"(둘 다 선택)에
    따라 slot 전 분기에 `decline_intrigue_spy`를 추가하고, recall은 배치로
    이어질 수 있는 것만(빈 target이 있으면 아무 Spy, 없으면 allowed post의
    단독 점유 Spy) 제시하며, play 시점 판정도 단독 점유 기준으로 고쳤다.
    codec v78. Distraction trigger가 slot 루프 중간에 끼어들어 조건이
    drift하는 실제 사례를 확인했다(해결 시점 판정 원칙 유지).
  - **Imperium Deck 고갈 tripwire**(`ac4d6d4`, 기본 룰셋 6판): heuristic이
    카드를 충분히 사서 공유 덱이 실제로 바닥났다. 공식 문서는 덱 위에서
    보충한다고만 하므로(`[Main p. 13]`, OQ-004) 물리적으로 강제되는 유일한
    진행을 convention으로 기록했다: 덱이 비면 Row는 보충 없이 남은 장수로
    운영한다. 네 제거 지점이 `take_imperium_row_card` 헬퍼를 공유하고,
    관측의 5-슬롯 Row 세그먼트는 빈자리를 0으로 둔다.
- 검증: 수정 후 heuristic 룰셋당 1,000판(총 2,000판)과 random 300판×2가
  모든 불변식·replay 검사 포함 실패 0으로 통과했다. 교착 seed 97·901은
  invariant-checked 회귀 테스트로 고정했다(`tests/integration/test_sweep.py`).
  pytest 770→796, Ruff, mypy 통과.

## 2026-08-30 계획 조정

- M11(사람용 플레이 인터페이스)을 M9·M10보다 앞으로 옮겼다. 근거와 순서
  방침(번호 유지, 나열 순서 = 구현 순서)은 `implementation-plan.md` 마일스톤
  절 서두에 있다. UI 형태는 로컬 웹 UI로, 초기 AI 상대는 random + 간단
  heuristic(M9 재사용)으로 확정했다.
- Leader 선택 절차를 OQ-007의 구현 convention으로 확정했다: 합법 Leader 중
  무작위 6종을 즉시 공개로 뽑고, First Player 확정 뒤 turn 역순으로 한
  명씩 공개 pick(First Player가 마지막), 미선택 2종은 미사용. 공식 setup의
  Leader 단계(`[Main p. 4]`)를 First Player 결정 뒤로 옮기는 ruleset
  option이며 공식 규칙이 아니다. 세부와 구현 지침은
  [`rules/open-questions.md`](rules/open-questions.md#oq-007--leader-선택-절차)에
  있다.

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
