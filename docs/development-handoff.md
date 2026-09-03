# 개발 인수인계

기준일: 2026-09-03

이 문서는 새 개발 세션(Claude Code, Codex 등 어떤 도구든)에서 저장소의 현재 위치를 빠르게 복구하기 위한 진입점이다. 규칙의 규범 근거는 [`rules/README.md`](rules/README.md), 장기 마일스톤과 구현 순서는 [`implementation-plan.md`](implementation-plan.md), 카드별 세부 동작은 [`implementation-audits/personal-cards.md`](implementation-audits/personal-cards.md), Leader 능력은 [`implementation-audits/leaders.md`](implementation-audits/leaders.md), 계약 경계는 [`implementation-audits/contracts.md`](implementation-audits/contracts.md)를 따른다.

## 세션 시작 체크리스트

1. 저장소 루트의 `AGENTS.md`(도구 중립 공통 지침), `CLAUDE.md`(Claude Code 진입점), `README.md`, 이 문서, 그리고 [`lessons.md`](lessons.md)를 읽는다.
2. `git status --short`와 `git log --oneline -10`으로 작업 트리와 최근 구현을 확인한다. 기존 변경은 사용자 작업으로 취급하고 덮어쓰지 않는다.
3. `uv sync --extra rl --extra ui`로 Python 3.14 환경을 준비한다(`ui`는 FastAPI 서버 의존성; 없으면 `tests/server/test_app.py`가 skip된다).
4. 아래 기준 검증을 실행한다.

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

2026-09-03의 기준 결과는 pytest 1,011개 통과(카드 이미지 에셋이 없는 머신은 1,010 통과 + 1 skip), Ruff 통과, mypy 통과다. 현재 action codec은 `ACTION_CODEC_VERSION = 84`(기본 4,314개, CHOAM 4,600개)이고, 관측은 `OBSERVATION_VERSION = 3`의 1,967-int 전체 게임 인코딩이다 ([`rl-environment.md`](rl-environment.md)). 보드 22칸 완결 + 즉시 공개 + `fab266f`/`e6fc298` 수정 + sweep 확장(`853ecd4`) 반영 후의 교차 소크는 random 룰셋당 2,000판 + heuristic 룰셋당 1,000판(둘 다 `--rotate-leaders`) + draft 두 policy 각 룰셋당 500판, 전부 `--soundness-interval 25`를 켠 총 7,000판이 실패 0으로 통과한 상태다(2026-09-01, 아래 세션 요약. 그 전 단계에서는 random 룰셋당 3,000판 비회전 소크도 실패 0이었다).

## 현재 구현 기준선

마지막 기능 커밋 묶음은 2026-09-01 검증 강화 캠페인의 보드 공간 완결 슬라이스들이다: `d7703ef`(Dutiful Service CHOAM contract), `e141492` (Shipping, codec v80), `63a8994`(Desert Tactics, codec v81), `49a5bb6` (Imperial Privilege, codec v82, OQ-023), `78fa1a3`(Secrets chance 강탈, SECRETS_STEAL frame), `881d88b`(Reveal 중 hand 진입 카드의 FAQ p. 3 즉시 공개, OQ-015(c) 해소), `fab266f`·`e6fc298`(소크가 적발한 mid-frame trash 충돌 두 계열의 OQ-022 확장 수정). 이로써 **4인 보드 22칸 전부가 배치·해결 가능**하고 Reveal 중 draw/hand-acquire Plot 보류도 사라졌다. 그 앞은 `4c175d1`(카드 이미지 캐시 다운로드 스크립트)이고, 그 앞에 UI 효과 표시 작업의 `3e2ae8f`(행동 효과 미리보기 + 전체 행동 라벨), `d275a66`(보드 공간 패널·popover·카드 이미지), `d34a2d1`(/catalog 효과 텍스트·이미지), `a4befd4`(display 패키지), `3c1cc69`(정적 보드 효과 테이블), 그리고 M11의 `e44900a`(저장/불러오기/검토 브라우저 UI), 슬라이스 5 서버 API `8ab3cd2`, 브라우저 UI `42be883`, FastAPI 세션 서버 `4fbd751`, Leader draft `c0c1795`, Treacherous Maneuver OQ-022 수정 `d70b353`, 슬라이스 1 묶음(`1a449f4`+`7a53c8f`+`ac4d6d4`)이 있다. 마일스톤 현황: **R0~M8, M11 완료**(M6 콘텐츠, M7 완주 검증, M8 CHOAM, M11 사람용 로컬 웹 UI — 슬라이스 7까지, 완료 판정 근거는 `implementation-plan.md` M11 절), **다음은 M9**.

- R0-M4는 완료됐다. 공식 규칙 자료, 엔진 커널, 4인 setup, 한 라운드 수직 조각, actor-neutral action codec과 PettingZoo AEC 계약이 있다.
- M5의 주요 시스템은 연결돼 있다. Influence/Friendship/Alliance, Agent와 Reveal, Spy/Infiltrate/Gather Intelligence, 개인 덱 reshuffle chance, Combat 순위와 보상, sandworm·Shield Wall·control, Makers·Recall, Endgame window와 게임 종료까지 실행할 수 있다.
- 시작 카드 7종, Reserve 2종, 기본 Imperium 50종, CHOAM 전용 Imperium 4종 모두에 완전한 play data가 있다(`implementation-audits/personal-cards.md`).
- CHOAM standard contract 20장의 시장·완료·보상과 CHOAM 전용 Imperium 4종이 연결돼 있다(`implementation-audits/contracts.md`).
- Intrigue 44장은 39개 identity 전부가 effect DSL로 전사돼 실제 play된다 (Intrigue 덱 완결). Plot은 소유자의 `turn`/`agent_effects`/`reveal` frame에서, Combat은 `combat_intrigue` frame의 priority 보유 참가자에게 제시된다. 선택이 필요한 효과는 `intrigue_choice` frame의 슬롯으로 순차 해결한다. Impress와 Inspire Awe의 비용 상한 획득은 `AcquireCardUpTo` 슬롯으로 Row/Reserve에서 가져오며, acquire box의 Spy 배치는 카드 해결 후 `acquisition_spy` frame을 재사용한다. Call to Arms와 Distraction은 face-up trigger 카드로, play하면 공개 `intrigue_faceup` 존에서 대기한다. Call to Arms는 소유자의 Reveal turn 획득마다 발동하고 그 Reveal 종료 시 만료되며, Distraction은 `PlayerState.units_deployed_turn` 카운터가 3에 닿은 뒤 매 전이 후 dispatcher가 `intrigue_trigger_spy` frame으로 제시하고 거절하면 face up으로 남는다(OQ-016, `rules/intrigue_triggers.py`, `implementation-audits/intrigue.md`).
- Intrigue deck 고갈 시 모든 draw 지점이 `pending_intrigue_draws` 큐를 거쳐 replayable reshuffle chance로 해결된다.
- 인쇄된 Leader 9종(기본 8 + CHOAM 전용 Shaddam)의 능력과 Signet Ring이 모두 play된다(`rules/leader_abilities.py`, `implementation-audits/leaders.md`). Lady Jessica의 flip 면은 `PlayerState.leader_face_id`, memory는 `memories`(troop 12개 불변식 포함), Feyd token은 `feyd_track_space`, Shaddam의 set-aside contract는 `GameState.sardaukar_contract_ids`로 공개 관측된다. 2026-08-30에 standard Contract manifest를 수정했다: Sardaukar II (Agent recall 보상)가 20장에 속하고, 이전에 있던 세 번째 High Council 타일은 Rise of Ix Tech 보상 타일의 오전사였다(`contracts.md` audit).
- 규칙 dispatcher는 `LEGAL_ACTION_PROVIDERS[FrameKind]`와 `ACTION_HANDLERS` 두 표로 동작한다(`refactoring-plan.md`).
- 코어 상태 머신과 replay는 전체 게임을 지원한다. `dune-imperium-sweep`으로 룰셋당 10,000판(총 20,000판) random 완주 sweep(매 전이 카드 보존·교착 검사, 표본 주기 관측 누출 검사, 게임별 replay 검증)이 실패 0으로 통과했다(2026-08-30, 400초/50 games/s).
- `run_random_game`이 FINISHED까지 실행해 `GameSimulation(state, standings, replay)`를 돌려주고, `dune_imperium_uprising_v1` PettingZoo adapter는 전체 게임을 한 episode로 실행한다(chance 내부 해결, 승자독식 zero-sum 종료 보상, 1,409-int 관측, `choam_module`/`max_steps` 옵션). `run_random_round`와 debug CLI는 의도적으로 한 라운드 단위를 유지한다. 설계 근거는 [`rl-environment.md`](rl-environment.md).
- 공식 Main, Board Guide, FAQ는 2026-08-27에 공식 리소스 페이지에서 다시 내려받아 `scripts/official-rule-sources.json`의 SHA-256과 모두 일치함을 확인했다.

## 아직 완성되지 않은 경계

- (2026-09-01 해소) 보드 22칸 미구현 4~5칸과 OQ-015(c)의 Reveal 중 Plot 보류는 모두 구현됐다. `board_effect_is_implemented`와 UI의 "미구현 · 배치 불가" 배지는 미래 콘텐츠 대비 메커니즘으로 남아 있고, `tests/unit/rules/test_board_effects.py`의 pinned 집합은 이제 양쪽 룰셋 모두 빈 집합이다. Imperial Privilege의 recall 판정은 OQ-023 convention, Secrets의 무작위 강탈은 seeded `SECRETS_STEAL` chance frame이다.
- Agent 배치 시점 조건이 거짓이면 pending되지 않는 카드 효과는, 같은 frame의 자유 순서 효과로 조건이 나중에 참이 되어도 제시되지 않는다(알려진 엔진 경계; Prepare the Way 수정 커밋 `87a9300` 참고).
- Objective와 battle icon 상호작용은 2026-08-30에 재감사를 마쳤다 (`implementation-audits/objectives.md`, OQ-005 RESOLVED). Combat 다중 후보 guard는 미래 콘텐츠 대비 tripwire로 남는다.
- Shaddam Corrino IV의 set-aside Sardaukar Contract 경로는 Leader 능력과 함께 남아 있다. OQ-010(2026-09-02 확정), OQ-011 경계는 확정 판정(`DECIDED`)으로 유지된다.
- 공식 문서가 침묵하는 규칙 판정은 [`rules/open-questions.md`](rules/open-questions.md)에 있다. 2026-09-01 확정 캠페인과 같은 날의 사용자 검토를 거쳐, 2026-09-02에 OQ-010까지 확정돼 `OPEN` 항목은 없고 전부 `DECIDED`/`RESOLVED`다. `DECIDED`는 확정 프로젝트 판정으로 새 공식 룰북·FAQ(또는 OQ-022처럼 명시된 상위 근거)가 답을 줄 때만 다시 연다. 새로 발견되는 규칙 공백은 여전히 코드로 임의 확정하지 않고 그 문서에 먼저 기록하며, 규칙 동작을 바꾸기 전에는 반드시 `docs/rules/`의 문장을 인용한다([`lessons.md`](lessons.md)).

콘텐츠(카드·리더·계약·Intrigue·보드 22칸)는 이제 4인 base+CHOAM 게임 범위에서 완결이다. 남은 경계는 공식 문서가 침묵하는 판정을 기록한 convention(open-questions.md)과 위의 엔진 경계·미래 콘텐츠 tripwire들이며, 이들은 "미구현 콘텐츠"가 아니라 문서화된 프로젝트 판정이다.

## 다음 구현 순서

2026-09-01의 **검증 강화 캠페인**(사용자 확정 범위: 전체 1→4)은 같은 날 완료했다: 1단계 보드 22칸 완결 + OQ-015(c), 2단계 sweep 확장 (`853ecd4`: 커버리지 census `--coverage-json`, 표본 주기 legal-action 전수 적용 + codec 왕복 `--soundness-interval`, seed별 리더 회전 `--rotate-leaders`), 3단계 교차 소크(아래), 4단계 대조(DIU 63종 전부 일치, open-questions 23건 재점검). 세부는 아래 세션 요약.

0. (2026-09-03 완료) M11 슬라이스 7 보드 스캔 테이블 + 룰북 아이콘 — 아래 세션 요약. (2026-09-02 완료) 슬라이스 6 행동 되돌리기 + 실시간 행동 로그.
1. **M9 평가 러너와 baseline.** 여러 게임을 병렬 구동하고 정책 추론만 batch하는 self-play 러너, random/heuristic(M11 상대에서 출발)/rollout baseline, 좌석·리더·first player·seed 교차 대회 도구 (`implementation-plan.md`의 M9). 관측·보상 계약은 [`rl-environment.md`](rl-environment.md)로 고정돼 있고, 병렬 실행 선례는 `simulation/sweep.py`다. 더 큰 야간 규모 재검증이 필요하면 `dune-imperium-sweep --games 50000 --ruleset both --workers 8 --rotate-leaders --soundness-interval 25 --coverage-json ...`을 커밋된 트리에서 돌린다.
2. **M10 강화학습과 league self-play.** M9의 평가 행렬 위에서 시작한다 (`implementation-plan.md`의 M10).

각 묶음은 카드 이미지로 텍스트를 검증하고(`docs/card-data-sources.md`의 방법), `Play ...` / `Document ...` 커밋 쌍을 유지하며, 새 결정 경계는 `FrameKind` → frame `kind` → dispatcher 표 → codec 순으로 추가한다. 핸드오프의 카드 요약은 이미지 검증 전 참고일 뿐이다(Impress 비용, Spring the Trap 유형을 잘못 적었던 전례가 있다).

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
| 로컬 플레이 서버·저장·검토 | `src/dune_imperium/server/` (`sessions.py`, `persistence.py`, `app.py`, `catalog.py`, `static/`) |
| 영문 효과 표시 텍스트·이미지 매핑 | `src/dune_imperium/display/` (DSL·구조체 렌더러, enum 토큰 맵, 공간·Leader 텍스트, 이미지 파일명) |
| 검증 sweep과 불변식 | `src/dune_imperium/simulation/sweep.py`, `simulation/invariants.py`, `cli/sweep.py` |
| 카드별 회귀 테스트 | `tests/unit/content/`, `tests/unit/rules/` |
| 통합·adapter 테스트 | `tests/integration/`, `tests/adapters/` |

개인 카드 draw·Spy·Combat·Endgame의 민감한 설계 결정은 `docs/implementation-audits/`의 주제별 문서를 먼저 확인한다.

## 처리량 메모

`RulesEngine.verify_input_immutability`는 매 전이마다 state 전체를 canonical hash하는 디버그 가드라 기본 off다(켜면 random play가 약 70 step/s, 끄면 약 3,000 step/s). 커널 테스트 엔진만 이를 켠다. 완주 soak은 이제 `run_random_game`(약 48ms/판, 9,000 step/s)이나, 불변식·누출 검사와 replay 검증까지 포함하는 `dune-imperium-sweep`(검사 전부 켠 단일 프로세스 약 175ms/판, `--workers 8`로 약 50 games/s)을 그대로 쓴다. env 경유 masked random full episode는 약 4,100 agent step/s다.

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

# UI 카드 이미지 캐시 (선택). 우선: 비공개 Dune-Imperium-assets 저장소를 형제
# 디렉터리에 clone하고 그 README대로 downloads/cards·downloads/icons·map.jpg를 symlink.
# 폴백/신규 카드 채움: 아래 fetch 스크립트 (빈 파일만 받는다)
uv run scripts/fetch_card_images.py

# 한 라운드 random 실행
uv run dune-imperium-debug --seed 2 --random-policy-seed 1002

# 대화형 한 라운드 실행
uv run dune-imperium-debug --seed 2

# 명시적으로 준비한 DIU working copy와 identity/effect shape 대조
uv run dune-imperium-audit-diu ../DIU/data/imperium.JSON

# 공식 PDF와 고정 checksum 재검증; 생성물은 /tmp에만 둔다
uv run scripts/prepare_official_rules.py
```

sandbox에서 uv cache 쓰기가 제한되면 명령 앞에 `UV_CACHE_DIR=/tmp/dune-uv-cache`를 붙인다.

## 원격 저장소 인계 주의

2026-09-03 세션 시작 시점에 `origin/master`와 로컬은 `e4ac740`으로 일치했고, 이 날의 슬라이스 7 커밋들(`3d70e38`부터)은 로컬에만 있다(push는 사용자 판단으로 한다). 원격에는 병합하지 않은 `kyungtae` 브랜치가 있다. 새 세션은 `git log origin/master..master`와 반대 방향을 모두 확인하고, checkout이 `853ecd4`보다 이전이면 이 문서의 989개 테스트·codec v84 기준선이 실제 코드와 일치하지 않는다. **다른 머신에서 이어서 작업한다면 먼저 이 머신에서 push가 필요하다.** 새 머신의 UI 카드 이미지·아이콘·보드 스캔은 비공개 `Dune-Imperium-assets` 저장소를 clone해 symlink로 연결한다(그 README 참고; `downloads/cards`, `downloads/icons`, `map.jpg`). 카드 매핑은 그 저장소의 `cards/manifest.json`에만 있으므로 접근이 없으면 텍스트 UI로 동작한다.

## 2026-09-03 M11 슬라이스 7 세션 요약 (보드 스캔 테이블 + 룰북 아이콘)

- 친구의 원격 브랜치 `kyungtae`(`881849c`, timethinker-GoNe, 2026-09-01 "Build an immersive single-screen game table")를 검토했다. 방향(보드 이미지 위 hotspot, 좌석색 Agent 토큰, 카드 이미지 손패·Imperium Row)은 채택하되 base가 `af8ff7c`로 master보다 33커밋 뒤라 5개 파일 충돌, master의 v3 관측(`private.discard_pile` 제거)에서 런타임 오류, undo·로그·공개 패널이 들어갈 자리 없음 등이 있어 병합하지 않고 master 위에 새로 구현했다(사용자: "꼭 그대로 병합할 필요는 없다"). 브랜치는 원격에 그대로 남아 있다.
- 사용자 판정: 보드 원본은 저장소 루트 `map.jpg`(Tabletop Simulator에서 가져온 6012×6005 스캔, gitignore); 효과 텍스트는 카드·보드처럼 아이콘으로 표시하고 아이콘은 룰북·카드에서 추출한다.
- **`3d70e38` 서버·display**: `display/board_layout.py`(22칸 `SPACE_BOXES` + 관측소 13곳 `POST_POINTS`, 2% 격자 오버레이로 수측정, 테스트가 엔진 id 전수 커버와 비겹침을 고정), `display/icons.py`(공식 Uprising Main Rulebook 20쪽 Icon Guide + 9쪽 Agent 아이콘의 image xref 45개), `scripts/extract_rulebook_icons.py`(card-implementer 서브에이전트 구현: 공식 URL 다운로드·sha256 검증·PyMuPDF 추출·4-연결 flood fill 배경 키잉, `uv run --with pymupdf --with pillow`), 서버 `/board-image`(`map.jpg` 또는 `DUNE_IMPERIUM_BOARD_IMAGE`)·`/icons`(`downloads/icons` 또는 `DUNE_IMPERIUM_ICON_DIR`), catalog `spaces[id].box`·`posts`·`icons`·`board_image`. 없으면 null/빈 값.
- **`6b9eae2` UI**: 게임 화면을 viewport 고정 3열 테이블로 재구성(좌: 좌석 카드 — 리더 썸네일·자원/Influence/병력 아이콘 스탯; 중: 보드 스테이지 + 공용 카드 띠(Conflict·Imperium Row·Reserve·Contract·Intrigue discard·draft 중 Leader pool); 우: 결정 패널·undo·검토 바·순위·행동 로그·종료 후 공개; 하단: 내 손패·Intrigue 카드 이미지). hotspot은 합법이면 발광, 클릭 시 합법 행동 1개면 즉시 적용·여러 개면 우측 목록 강조(`data-refs`)·없으면 popover. Agent 토큰·Control 플래그·Maker bonus spice·Spy(관측소 좌표)를 겹쳐 그린다. `ICON_RULES` glossary가 서버의 영어 효과 텍스트를 아이콘으로 재렌더(원문은 tooltip). popover는 fixed 위치(열이 각자 스크롤). 스캔 없으면 텍스트 보드 목록, 이미지 없으면 텍스트 카드, 아이콘 없으면 단어.
- 에셋 저장소(`Dune-Imperium-assets` `c57fa72`)에 `icons/` 45장과 `board/map.jpg`를 추가했고 이 머신은 `downloads/icons`·(선택) `map.jpg` symlink로 연결한다. 새 머신 설정은 그 README.
- 검증: pytest 1,015, Ruff(`src tests`), mypy. headless Chromium E2E(스크래치 Playwright + ALSA stub): 게임 생성 → hotspot 22개·보드 이미지 로드·아이콘 65개 → popover(아이콘 4개) → 손패/hotspot 클릭으로 12단계 진행 → 토큰 4개·로그 19건, JS 오류 0·서버 오류 0. 스크린샷 검토로 hotspot 좌표가 스캔과 일치함을 확인했다.
- 후속 수정: 손패의 Dagger·Diplomacy·Dune the Desert Planet·Reconnaissance가 텍스트 카드로 보인다는 사용자 지적 → Uprising판 이미지가 Dune Cards Hub에 없어 `KNOWN_MISSING`이던 네 장을 동일 인쇄물인 기본판 `dune-imperium-other-*.webp`로 매핑(`required_images` 170장, `KNOWN_MISSING`은 빈 집합으로 유지).
- **에셋 정비(사용자 요청, `Dune-Imperium-assets` + 메인 `display/images.py` 재작성)**: 사용자 확인 — 캐시 600장은 Dune Cards Hub에서 받은 그대로(파일명·바이트 동일)였고, `uprising-other-*-emperor/-muad-dib`는 6인 Commander 덱(Rules Supplements p. 7, 14)이라 4인 시작 카드 7장은 기본판 스캔이 맞다. 새 규칙: `cards/<언어>/<세트>/<종류>/<인쇄 카드명>.<확장자>`(공백·아포스트로피·`+` 유지, 동명 카드는 인쇄된 구별 요소를 괄호로 — Skirmish 3장은 battle icon, Harvest 3+/4+ 두 쌍은 보상), 세트 7개(uprising, base, rise-of-ix, immortality, bloodlines, conspiracy, promo)로 600장 전부 분류(안 쓰는 확장팩은 slug 유도 이름 + `name_source: "upstream-slug"` 미검증 표시), 매핑은 에셋 저장소의 `cards/manifest.json` 하나(607항목·파일 607: Uprising 시작 카드 7장은 세트별 자기 완결을 위해 기본판 스캔의 사본을 `uprising/starting/`에 둔다 — 사용자 결정). 메인 저장소: `display/images.py`는 manifest 로더(`load_card_manifest`·`resolve_card_images`: ko 우선·en fallback·존재 파일만, `required_image_keys` 170)로 교체하고 오타 보정표·`KNOWN_MISSING` 제거, catalog URL은 percent-encoding, 서버 기본 경로 `downloads/cards`(에셋 `cards/` symlink), `fetch_card_images.py`는 manifest 출처로 빠진 파일만 받는 스크립트로 재작성. 검증: pytest 1,011(캐시 없는 머신은 skip 1), ruff, mypy, headless Chromium E2E 오류 0(손패 7장 전부 이미지).
- 남은 개선: Influence·VP 트랙 마커를 보드 위에 그리기, 아이콘 키잉 tolerance(프레임형 Agent 아이콘 모서리의 잔여 베이지), 같은 카드 2장으로 생기는 중복 행동 라벨 구분.

## 2026-09-02 M11 슬라이스 6 세션 요약 (행동 되돌리기 + 실시간 행동 로그)

- **`0e76131` 서버**: `server/session_log.py` — append-only 세션 로그(`LoggedStep`: 단계 + 이벤트 + `reveals` + `hidden_arguments` + `undone`, `LoggedUndo` 마커). `reveals_hidden_information(before, after, actor)`는 새 `core.observation.known_card_seats`(카드별로 identity를 아는 좌석 집합; deck·bank는 아무도, hand·보유 Intrigue는 소유자만, `hand_public`·`intrigue_resolving`은 전원)로 "어떤 좌석이 전에 몰랐던 카드를 알게 됐는가"를 판정하되, 행동자만 알던 카드를 행동자가 스스로 공개한 경우(Intrigue play, hand discard/trash, Reveal)는 예외(사용자 판정). `undo_window`는 뒤에서부터 자기 행동이면서 `reveals`가 아닌 연속 단계 수 — chance·다른 좌석 행동·공개 단계에서 닫힌다. 따라서 되돌리는 구간에는 chance·AI 단계가 없어 RNG 스트림을 건드리지 않고, 복원 상태는 다시 그 좌석의 결정이다. `GameSessionManager.undo(seat, revision, steps)`는 `steps[:keep]`을 reset부터 재적용해 복원하고 로그의 해당 항목을 `undone`으로 표시한 뒤 마커를 붙인다. `log(seat, after)`는 이벤트를 `visible_to`로 거르고, 비공개 카드를 가리키는 행동 인수는 다른 좌석에게 `(비공개)`, chance 값은 종료 전 숨김(종료 후 전부 공개). 저장 형식 v2: `log` 필드(되돌린 단계·마커 포함), 복원 시 되돌린 가지를 분기 상태에서 재적용해 이벤트를 복구·검증; v1 저장도 읽는다(되돌림 이력 없음). 검토 메타 `undo_history`. HTTP `POST /games/{id}/undo`, `GET /games/{id}/log`. summary에 `undo`(좌석별 창)·`log_count`. 테스트 `tests/server/test_undo.py` 9건 + HTTP 1건.
- **UI**(card-implementer 서브에이전트 구현, 메인 세션 검토): 결정 배너의 "되돌리기 (1단계)"/"N단계 모두 되돌리기" 버튼, `#action-log` 패널(이벤트별 한국어 라벨 `EVENT_LABELS`, 되돌린 항목 취소선, 마커 강조), 검토 상태줄의 되돌림 마커. headless Chromium E2E(스크래치 Playwright)로 되돌리기 → 로그 갱신 → 완주 → 검토 마커까지 JS 오류 0 확인.
- 되돌린 뒤 다른 선택으로 같은 revision 번호에 다시 도달할 수 있으므로, summary의 `undo_count`(되돌리기 세대 번호)를 행동·되돌리기 요청이 함께 보내면 revision과 둘 다 맞아야 통과한다(`StaleRevisionError`, HTTP 409). 브라우저 UI는 항상 보내고, 매니저·HTTP API에서는 선택 인수라 생략한 호출은 revision만 검사한다. 저장 복원 시 로그의 마커 수로 복구한다.

## 2026-09-02 OQ-010 확정 세션 요약 (관측 v3, 이벤트 가시성 불변식, 종료 후 전체 공개, 되돌리기 설계)

- 사용자와 OQ-010의 네 범위를 결정했다(전부 추천안 채택, 세부는 `rules/open-questions.md`): (1) 상대 discard identity 공개, (2) 완료 contract identity 공개, (3) 실시간 로그는 `event_log`를 `visible_to`로 걸러 표시하되 공개 이벤트는 공개 존의 카드만 이름을 담는다, (4) 종료 후 전체 공개(검토 편의 convention).
- **`8bb3bfe` 관측 v3 1차**: `PublicPlayerView.discard_pile`·`completed_contract_ids` 추가, `PrivatePlayerView.discard_pile`과 좌석 scalar 2개 제거, `seat{n}_discard`/`seat{n}_completed_contracts` 세그먼트. UI 좌석 카드에 완료 contract 표시.
- **`7a52c17` 이벤트 가시성**: 새 sweep 불변식 `check_event_visibility`(매 전이, 공개 이벤트 payload의 card id가 비공개 존에 있으면 실패)를 넣고 random 24판 전수 조사로 세 가지 누출을 찾아 고쳤다. Secrets 강탈 이벤트를 공개/한정 두 이벤트로 분리, `cards_drawn`·`personal_discard_shuffled`는 공개로 전환(장수만 담음). 선택 해결 중인 played Intrigue는 `PlayerView.intrigue_resolving`으로, 공개 경로로 hand에 들어온 카드(Corrinth City·Intrigue to-hand·BG Bond 반환)는 새 `PlayerState.hand_public`(construction 시 hand 밖 항목 자동 제거) → `PublicPlayerView.hand_public`으로 공개. 관측 v3 최종 1,967-int(`seat{n}_hand_public` 63, 전역 `intrigue_resolving` 39 추가). privacy scramble이 두 공개 집합을 보존하도록 수정.
- **`8087e9b` 종료 후 전체 공개**: `disclose_hidden_zones`(각 좌석 hand·deck 순서·Intrigue + Imperium/Intrigue/Conflict deck·bank 순서). 서버는 종료된 게임의 live view와 검토 모든 step에 `disclosure`를 붙이고, 검토 라벨은 전 좌석 상세 + chance 값, AI 좌석 검토 허용. UI에 "종료 후 공개" 패널과 전 좌석 검토 선택. headless Chromium E2E(스크래치 Playwright + ALSA stub, 메모리의 recipe)로 종료 화면·검토 화면 JS 오류 0 확인.
- 되돌리기 기능은 설계를 확정해 `implementation-plan.md` M11 슬라이스 6으로 기록했고, 같은 날 뒤이어 구현했다(위 세션 요약).
- 검증: pytest 993, Ruff, mypy. 커밋 트리 소크(`7a52c17` 기준) — 회전 리더 random 룰셋당 150판 + heuristic 룰셋당 80판(soundness 25) + draft random 룰셋당 40판, 실패 0.
- 교훈(프로세스): `ruff format`은 이 저장소의 검사 항목이 아니며 실행하면 무관한 60여 파일이 바뀐다. 이 세션에서 한 번 실행했다가 파일별로 되돌렸다. `ruff check`만 쓴다.

## 2026-09-02 오픈 퀘스천 재판정 세션 요약 (OQ-015(d) 아이콘 순서 선택, OQ-021 Shaddam 선택)

- **OQ-015(d) 재판정 (`446e6dc`, codec v83)**: 사용자 판정 — 한 효과 줄의 여러 아이콘은 독립 효과이고 인쇄가 순서를 강제하지 않으므로 소유자가 순서를 고른다(화살표 비용→보상은 인쇄 순서 유지, 비용 슬롯 먼저). INTRIGUE_CHOICE frame에 `resolve_intrigue_rewards` 행동을 추가해 비용 지불 뒤 자동 보상 묶음을 원하는 시점에 해결할 수 있게 했다. Cunning은 draw 먼저 → 뽑은 카드 trash 가능. 전수 스캔 결과 순서가 결과를 바꾸는 조합은 Cunning뿐이고(Unexpected Allies는 기존 고정이 유일 합리 순서), Devour/Impress/Leverage는 순서 무관, 화살표 비용 카드들(Questionable Methods 등)은 영향 없음.
- **소크 적발 수정 (`f0f77eb`)**: 회전 리더 소크가 base seed 485/563에서 choice frame 복제(이중 discard·이중 draw)를 적발 — mid-frame draw가 reshuffle chance frame을 push했는데 top 교체가 그것을 덮어썼다. acquire 슬롯과 같은 advance-before-move 패턴(보상 적용 전 frame 갱신)으로 수정하고 두 seed를 회귀로 고정했다.
- **OQ-021 재판정 (`2d2e237`, codec v84)**: 사용자 판정 — 시장·bank가 모두 소진돼도 set-aside Sardaukar contract가 남아 있으면 Shaddam은 아이콘마다 2 Solari와 set-aside 획득 중 선택한다(`take_exhausted_contract_solari`, CHOAM 전용 템플릿). 다른 플레이어와 set-aside 소진 후의 Shaddam은 기존 자동 2 Solari 전환 유지. 이전의 "Shaddam도 자동 전환" 판정 폐기.
- 검증: pytest 989(988+skip 1), Ruff, mypy. 커밋 트리 소크 — 회전 리더 random 룰셋당 700판 + heuristic 룰셋당 400판, 모두 soundness 25, 실패 0(첫 회전 소크가 위 frame 복제 버그를 적발한 뒤 재실행 통과).

## 2026-09-01 오픈 퀘스천 후속 세션 요약 (사용자 피드백: OQ-022 디자이너 판정 채택, OQ-023 재판정, OQ-010 재개)

- 사용자 피드백 6건을 반영했다. OQ-003은 사용자가 기존 판정을 그대로 재확인했고, OQ-015·OQ-021은 설명만 제공했다(판정 불변).
- **OQ-022 (동작 변경, `76dbbf7`)**: 사용자 지시로 외부 커뮤니티·공식 디지털 구현을 조사했다. BGG thread 3031484에서 디자이너 Paul Dennen(계정 "Merakon")의 2023-02-19 판정을 확인했다 — 이미 trash된 카드의 효과는 받지도 발동하지도 않는다(기존 pooled-effects 판정의 공식 번복; Esmar Tuek/Cull, Foldspace 사례). 2025 FAQ의 Imperial Spy·Beguiling Pheromones named 항목이 같은 원칙이라 현재도 유효하다. 이에 따라 dispatcher 훅 `expire_trashed_card_effects`가 미발동 Agent box 전체(의무 부분·Bond·선택 슬롯)를 만료시키는 모델로 교체하고, 충족 간주·잔여 해결 경로와 `agent_card_self_trash_satisfied` 이벤트를 제거했다. 이미 지급된 Reveal 기여분과 설치형 trigger는 유지(후속 답글). BGG 페이지는 Cloudflare 사람 확인이라 열지 않고 공개 geekdo API로 본문을 확인했다(CAPTCHA 우회 없음). codec 불변.
- **OQ-023 (동작 변경, `bce829e`)**: 사용자 재판정 — Imperial Privilege의 recall과 draw는 별개 효과이므로, recall 대상이 없으면 recall만 건너뛰고(`imperial_privilege_recall_skipped`) card draw는 그대로 해결한다. 이전의 절 전체 무효 판정을 교체했다.
- **OQ-010 (재개)**: "한 번 공개된 정보는 재확인 가능해야 한다"는 방향을 사용자가 확정, 구체 범위(상대 discard identity, 완료 contract identity, 종료 후 열람 등)는 후속 논의로 남기고 `OPEN`으로 되돌렸다. 관측 v2 구현은 논의 전까지 현행 유지.
- **OQ-012 (보강)**: Faction 공간의 Influence 상승 시점은 Main p. 9 자유 순서 원문("You may carry out all these effects in any order")이 직접 답한다 — 방문자가 시점을 고르며 엔진의 `resolve_faction_influence`도 그렇게 제시함을 확인. Bloodlines 도입 시 이 항목을 다시 열기로 재개 조건을 명시했다.
- 검증: pytest 986(985+skip 1), Ruff, mypy. 커밋 트리 소크 — OQ-022 반영 후 룰셋당 700판(soundness 25), 두 커밋 반영 후 룰셋당 700판(`--rotate-leaders` + soundness 25) 모두 실패 0.

## 2026-09-01 오픈 퀘스천 확정 세션 요약 (19건 전부 DECIDED)

- 사용자 지시로 open-questions의 미해결 항목 전부에 확정 결정을 내렸다. 먼저 공식 리소스 페이지를 재확인해 Main/Supplements 23-10-12판과 FAQ 2025-01-13판이 여전히 최신임을 확정한 뒤(새 공식 판정 없음), `DECIDED` 상태(확정 프로젝트 판정 — 새 공식 문서가 답을 줄 때만 재검토)를 도입해 `OPEN`/`CONTENT` 19건 전부를 전환했다. RESOLVED 4건(OQ-005/009/013/014)은 그대로다.
- 동작이 바뀐 유일한 항목은 OQ-006이다(`5baac89`): Main p. 11 원문의 Infiltrate는 "다른 플레이어가 점유 중"이라는 술어를 발동 조건으로, 연결된 Spy **하나**의 recall을 비용으로 두므로, opponent Agent가 2개 이상인 공간을 배치 불가로 막던 임시 guard를 제거하고 recall 하나로 진입을 허용했다. codec 불변(기존 `infiltrate_post_id` 인자 그대로).
- OQ-002는 콘텐츠 검산으로 닫았다(`5e34522`): 동률 그룹이 받는 보상은 항상 2·3위 줄이고 그 줄에는 상호작용 보상이 없으므로(Influence 선택·contract·Spy·VP·optional 지불·control은 전부 1위 줄 전용), 좌석 번호 오름차순 해결(First Player 위치 무관)을 tied-order 테스트 2건으로 pin했다.
- 나머지는 분석·문서 확정이다: OQ-001(완결 Endgame Intrigue 6종 전수 — 어떤 효과도 다른 window의 조건 입력을 바꾸지 못해 단일 순회 근거 유효), OQ-003(완결 Intrigue 39종 재검산 — Combat 중 유닛 증가 카드 없음), OQ-008(Main p. 11 공식 예시가 controller 보너스의 배치 즉시 해결을 직접 보여주고, Agent turn 중 상대 자원 총량을 읽는 효과가 전무함을 DSL 조건 전수로 확인), OQ-011(Main p. 11 원문 "immediately after placing your Agent (before receiving any effects...)"), OQ-012(자유 순서 밖 동시 의무 효과는 획득 이벤트 계열뿐 — 획득 카드 보상 → in-play trigger → Acquire Contract → Call to Arms 고정 순서 확정, 전부 같은 획득자의 가환 이득), OQ-010(관측 v2의 identity 공개 경계와 종료 후 비공개 검토를 최종 판정으로 승격), OQ-004/007/015~023(기존 convention을 확정 판정으로 채택; OQ-021은 FAQ "in place of" 근거 유지).
- 규칙 문서의 미확정 절들을 확정 판정 참조로 갱신했다: `combat-and-round-end.md`, `player-turns.md`, `information-visibility.md`, 감사 문서 `spies.md`·`combat-conflicts.md`, 그리고 `open-questions.md`의 상태 정의(intro)와 2026-09-01 확정 캠페인 서문.
- 검증: pytest 986(985+skip 1), Ruff, mypy 통과. 공식 PDF 텍스트는 `scripts/prepare_official_rules.py`로 /tmp에만 생성해 원문 대조에 사용했다.

## 2026-09-01 검증 강화 캠페인 세션 요약 (보드 22칸 완결 + 검증 도구 + 교차 소크)

- 동기: M9/M10 전에 엔진에서 "학습이 변형 게임을 배우는" 원인을 제거한다. 미구현 보드 칸은 codec을 바꾸는 작업이라 M9 이후로 미루면 평가 행렬과 체크포인트가 무효화되므로 지금이 유일하게 싼 시점이었다. 사용자 확정 범위는 "전체 1→4"(보드 구현 → 검증 도구 → 대규모 soak → 대조).
- 슬라이스는 모두 `docs/rules/board-spaces.md`의 전사·인용을 근거로 하고, Sonnet `card-implementer` 서브에이전트에 위임한 뒤 본 세션이 diff를 리뷰하고 pytest/ruff/mypy를 재실행해 커밋했다.
- `d7703ef` Dutiful Service(CHOAM): `accept_contract`의 `begin_contract_gain` 경로 재사용(빈 시장 2 Solari 폴백은 OQ-021). codec 불변.
- `e141492` Shipping: choice-driven 공간으로 5 Solari + 선택 Faction Influence 1(`choose_shipping_influence` 4종, codec v80, `gain_faction_influence` 경유로 friendship VP 경로 공유).
- `63a8994` Desert Tactics: troop 1 recruit(`troops_recruited` counter로 Combat 배치 연동) + 선택적 trash(hand/discard/in play, `trash_personal_card` 공유로 OQ-022 self-trash convention 승계). codec v81.
- `49a5bb6` Imperial Privilege: 2단계 슬롯 — 선택적 Intrigue discard→reshuffle-safe draw, 그다음 의무 recall(방금 보낸 Agent 제외) + card 1 draw. 다른 배치 Agent가 없으면 절 전체 무효(신규 OQ-023 convention). codec v82.
- `78fa1a3` Secrets: 정적 Intrigue draw + `SECRETS_STEAL` chance frame으로 4장+ 보유 opponent마다 무작위 1장 강탈(held Intrigue만, intrigue_faceup 제외). draw의 reshuffle 부족분은 steal frame 위로 승격해 인쇄 순서(draw → steal)를 유지. FrameKind는 enum 끝에 추가해 관측 인덱스 안정. codec 불변(chance 전용).
- `881d88b` 즉시 공개(OQ-015(c) 해소): Reveal 중 hand에 들어간 카드는 즉시 in play로 옮겨 도착 시점 자격 판정으로 자신의 기여(설득·검·자원·선택 frame)를 얻고, 이미 지급된 금액은 확정 유지한 채 교차 효과 증분만 더한다. `begin_reveal_turn`의 카드별 계산을 순수 헬퍼로 추출해 양 경로가 동일 판정. 훅은 hand 진입 지점 2곳(개인 draw 완료 — reshuffle 후 경로 포함 — 과 Inspire Awe의 to-hand 획득). 교차 효과 3종(Stilgar, Sardaukar Coordination, Leadership)이 모두 무조건부임을 pin 테스트로 고정. 보류 필터 제거로 Reveal 중 해당 Plot이 제시된다.
- 소크가 실전 버그 두 계열을 적발했다 — 둘 다 "새 board trash가 해결 대기 중인 카드를 mid-frame에 잡는" 가족이다.
  - `fab266f`: Dangerous Rhetoric을 Spy 아이콘으로 Desert Tactics에 내고 board trash가 그 카드 자체를 잡으면 `TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE` Agent box가 무조건 self-trash를 실행해 crash(random CHOAM seed 2735). OQ-022 convention(이미 trash됐으면 충족 간주, 의무 잔여 효과는 해결)을 `apply_agent_card_influence`로 확장. 반대 성격인 Delivery Agreement의 "trash해서 VP"는 비용이므로 카드가 사라졌으면 해결 시점 판정으로 선택지를 제시하지 않게 했다.
  - `e6fc298`: BG Bond 카드가 Bond box 해결 전에 trash되면 `has_faction_bond`가 source의 in-play 존재를 요구해 crash(random seeds 2934/2590). 인쇄된 Bond 조건은 "다른 해당 Faction card가 in play"만 세므로(`[Main p. 20]`) source의 존 요구를 제거했다.
  - 회귀: 단위 3건 + 실패 seed 3개 완주(`tests/integration/test_sweep.py`).
- 주의(재발 방지): 백그라운드 sweep을 서브에이전트의 작업 트리 편집과 겹치면 반쪽 편집 상태의 판별 불가한 실패가 섞인다(heuristic seed 236 실패가 그 사례 — 완성 트리에서 그 seed·그 배치 1,000판 전체는 통과했지만, 같은 오류 계열이 다른 seed에서 실제 버그로 재등장했다). 소크는 커밋된 트리에서만 돌리고, 실패는 반드시 완성 트리에서 재현해 판별한다.
- 검증: pytest 934→973, Ruff, mypy. 수정 커밋 후 소크 — heuristic 룰셋당 1,000판, draft 두 policy 각 룰셋당 500판 실패 0, random 룰셋당 3,000판은 두 수정 반영 후 재실행 통과(위 기준선 절 수치).
- 2단계 sweep 확장(`853ecd4`, pytest 973→984): `--soundness-interval N` (표본 결정마다 제시된 모든 합법 행동을 실제 적용 + `ActionCodec` 인코딩 왕복 — sweep이 codec을 처음으로 검증), `--coverage-json PATH` (replay·이벤트 기반 룰셋별 콘텐츠 커버리지 census + 카탈로그 대비 0회 보고), `--rotate-leaders`(seed 결정적 4종 추출, draft와 배타).
- 3단계 교차 소크(커밋된 트리, 전 기능 on, 총 7,000판 실패 0): random 룰셋당 2,000판 + heuristic 룰셋당 1,000판(둘 다 리더 회전) + draft 두 policy 각 룰셋당 500판, 모두 `--soundness-interval 25`. 네 구성의 커버리지 합집합에서 0회 경로는 정확히 세 종뿐이며 전부 구조적이다: 기본 룰셋의 contracts 20개(CHOAM 전용), 기본 룰셋의 Shaddam 시그넷 액션 2개(`choose_leader_signet_influence`, `gain_leader_signet_troop` — Shaddam은 CHOAM 전용), 그리고 양 룰셋의 `acquire_leader_reserve`(Irulan Chronicler's Insight의 Reserve 분기 — 현재 콘텐츠에 비용 1 Reserve 카드가 없어 죽은 일반화 코드, `implementation-audits/leaders.md`의 "비용 1은 Imperium 5종" 기록과 일치). 비구조적 0 커버리지는 없다 — 강제 시나리오 테스트 추가 불요.
- 4단계 대조: `dune-imperium-audit-diu ../DIU/data/imperium.JSON` 재실행 — 63종 전부 일치(copy 수 차이 48건은 기존 방침대로 로컬 manifest 우선). open-questions 23건 재점검 — OQ-007의 codec 버전 표기 모호 1건만 명확화(도입 시점 표기), 나머지 전부 현행과 일치.

## 2026-08-31 UI 효과 표시 세션 요약 (텍스트 자동 생성 + 로컬 이미지)

- 문제: M11 UI가 이름만 보여줘 배치·플레이 결정 시 칸/카드 효과를 외워야 했다. 사용자 확정: 영어 효과 텍스트를 엔진 데이터에서 자동 생성해 전면 표시하고, gitignore된 `downloads/dunecardshub/cards/` 로컬 캐시(Uprising 189장)의 이미지를 병용한다(로컬 서빙 한정 승인, 저장소 커밋 금지 유지). 표시 전용 변경으로 codec·관측은 v79/v2 그대로다.
- `3c1cc69`: `board_effects_for`의 match를 순수 함수 `static_board_effects(space_id, cost_option, choam_module)`로 추출(동작 불변). pin 테스트가 전 공간×옵션×룰셋 도메인과 미구현 집합(기본 4칸 + CHOAM dutiful_service)을 고정 — 이 과정에서 이전 핸드오프의 "미구현 2칸" 서술이 부정확했음을 확인하고 위 경계 절을 정정했다.
- `a4befd4`: 프레임워크 중립 `dune_imperium.display` 패키지. Intrigue DSL(union별 exhaustive match + `assert_never`)·Contract·Conflict·정적 보드 테이블은 기계적 렌더, 개인 카드 enum 토큰(~50개)·선택형 공간·Leader 10면은 이미지 검증된 감사 문서(`personal-cards.md`, `leaders.md`, `board-spaces.md`) 문구로 수작성. 커버리지 테스트가 모든 enum 멤버·DSL primitive·reveal 필드·카드·공간·Leader 면을 고정해, 텍스트 없는 신규 콘텐츠는 스위트가 실패한다. 이미지 파일명 오타 override 9건과 이미지 없는 시작 카드 4종도 실측으로 고정했다. 구현은 Sonnet 서브에이전트 2개에 위임하고 본 세션이 감사 문서 대조로 리뷰했다.
- `d34a2d1`: `/catalog` 확장 — 카드·Intrigue·Contract·Conflict·Leader(대체 면 `reverend_mother_jessica` 항목 신설)·공간(비용·요구·플래그·옵션별 효과·계산된 implemented·notes) + `image` URL. `create_app`이 `--card-images-dir`/`DUNE_IMPERIUM_CARD_IMAGE_DIR`/기본 downloads 순으로 캐시를 찾아 존재할 때만 `/card-images` mount, 없으면 image 전부 null로 텍스트만 동작. contracts/spaces의 `deliver_supplies` id 충돌은 테스트로 고정하고 클라이언트가 space id를 spaces 섹션에 명시 조회해 해소한다.
- `d275a66`: 보드 공간 패널(아이콘 그룹별 22칸: 비용·효과·요구·점유·컨트롤·maker spice·미구현 배지)과 모든 chip의 상세 popover(효과 텍스트 + 이미지, Esc/바깥 클릭 닫기). hot-seat·replay 검토도 chip 공용이라 자동 적용.
- `3e2ae8f`: 행동 버튼 "ⓘ" 효과 미리보기(대상 공간의 해당 cost option + 카드 텍스트, play_intrigue는 해당 option만)와 `ACTION_LABELS` 111개 전체 커버(`tests/server/test_action_labels.py`가 rules 소스의 action_id 리터럴을 스캔해 누락·잔존 라벨 모두 실패 처리).
- 검증: pytest 842→933, Ruff, mypy 통과. 실제 uvicorn + headless Chromium E2E를 기본/CHOAM 두 룰셋에서 실행 — 22칸 렌더, 미구현 배지 4/5개, popover 텍스트·이미지 로드, ⓘ 미리보기 토글, 행동 버튼 6결정 진행, 페이지 오류 0. (WSL에 libasound가 없어 스크래치의 versioned stub을 `LD_LIBRARY_PATH`로 주입해 Playwright Chromium을 구동했다.)
- `4c175d1`(후속): `scripts/fetch_card_images.py` — 이미지 캐시가 없는 다른 개발 머신용 1회 다운로드 스크립트. 대상 목록은 `display.images.required_images()`(카탈로그가 참조 가능한 정확히 166장, 이미지 없는 시작 카드 4종 제외)에서 열거하고, UA+referer 헤더(직접 요청은 403), WebP 매직 검증, 기존 파일 skip/`--force`/`--dry-run`을 지원한다. 빈 디렉터리로 실다운로드 166/166 성공·기존 캐시와 전 파일 체크섬 동일을 확인했다. pytest 933→934.

## 2026-08-31 M11 슬라이스 5 세션 요약 (저장/불러오기 + replay 검토)

- 저장(`8ab3cd2`): `server/persistence.py`가 세션의 기록 steps를 `GameReplay` 위의 버전 있는 JSON 문서로 직렬화한다(`format_version` 1, 실제 `ACTION_CODEC_VERSION`·ruleset/content 버전 스탬프, step은 `type: action|chance` 판별자). 저장 파일은 서버 로컬 디스크의 `SaveStore`(`--saves-dir`, 기본 `~/.dune-imperium/saves`, 원자적 쓰기, save_id 패턴 검증)에 두고, HTTP로는 metadata만 내보낸다 — 기록된 셔플 결과가 비공개 덱 순서를 그대로 담기 때문이다.
- 불러오기의 chance 흐름은 핸드오프의 미결 설계 (a)의 변형으로 확정했다: RNG 상태를 저장하는 대신, `restore_game`이 기록 steps를 fresh seeded `ChanceResolver`(game seed)와 fresh seeded agents(policy seed + 좌석)로 재생하며 chance와 AI 결정을 **재생성해 기록과 대조**하고(사람 행동은 기록대로 적용), 마지막에 canonical state hash를 `replay_game`처럼 검증한다. 모든 RNG 스트림이 저장 시점 위치로 복원되므로 **불러온 게임은 저장하지 않은 세션과 동일하게 진행된다**(회귀 테스트로 고정: 저장 후 이어간 게임과 원본의 최종 순위·revision 일치). 대가로 저장본은 저장 당시의 엔진·agent 코드에 결속되며, 불일치·조작·버전 차이는 step 번호를 명시한 `SaveError`로 즉시 실패한다.
- 종료 후 replay 검토: `review`(step 라벨 타임라인)와 `review_state`(fresh 엔진으로 기록 steps를 k개 재적용한 시점의 좌석 `PlayerView`)를 추가했다. 검토는 종료된 게임의 사람 좌석만 허용하고 OQ-010 경계를 유지한다(자기 행동만 상세, 타 좌석은 행동 주체만, chance는 decision id만; open-questions.md에 convention 추가). 라이브 세션의 RNG는 건드리지 않는다.
- HTTP: `POST /games/{id}/save`, `GET /saves`, `POST /saves/{id}/load`, `DELETE /saves/{id}`, `GET /games/{id}/review`(+`/{step}`)를 추가했고 미존재 저장은 404, 형식·재생 오류는 400이다.
- 브라우저 UI(`e44900a`): 설정 화면의 저장 목록(불러오기/삭제), 게임 헤더의 저장 버튼(슬롯 이름 프롬프트), 종료 화면의 "리플레이 검토" — step 슬라이더·이전/다음·내 행동 점프·검토 좌석 선택이 기존 보드/좌석/비공개 렌더러로 시점 상태를 그린다.
- 검증: 실제 headless Chromium + uvicorn E2E로 draft 게임 생성 → 중간 저장 → 불러오기 → UI 버튼으로 79회 추가 결정 완주 → 종료 저장 → 491-step 검토 탐색 → 저장 삭제까지 서버 오류 0으로 확인했다. pytest 833→842(저장 문서 스탬프, 불러오기 동일 진행, 조작 거부 5종, SaveStore, 검토 경계·라벨, HTTP 왕복), Ruff, mypy 통과. M11 완료로 판정했다.

## 2026-08-31 M11 슬라이스 4 세션 요약 (브라우저 UI)

- 의존성 없는 vanilla HTML/CSS/JS 단일 페이지를 `server/static/`에 두고 FastAPI가 `/`(index)와 `/static/*`으로 서빙한다(`42be883`). 클라이언트는 서버의 summary/`PlayerView`/actions/catalog payload만 렌더링하며 규칙 지식을 갖지 않는다.
- `/catalog` endpoint(`server/catalog.py`, 프레임워크 중립)가 콘텐츠 manifest의 인쇄된 공개 표시 데이터를 제공한다: 개인 카드 63종의 이름·획득 비용·설득·검·Faction·Agent 아이콘, Intrigue 39종의 이름과 option timing, Contract·Conflict·Leader(능력명 포함)·보드 공간·Objective 이름. instance id → 카드 id 해석은 클라이언트의 접두사 파싱으로 한다.
- 화면: 설정(좌석별 사람/휴리스틱/랜덤, CHOAM, OQ-007 draft 기본 켬, seed, 진행 중 게임 이어서 열기) → 게임(결정 프롬프트 + frame kind + 결정 좌석, index 기반 행동 버튼, 보드 존—draft pool·Conflict·Imperium Row·Reserve·Contract 시장·maker spice·Intrigue discard, 좌석 4개 공개 패널, 내 hand/discard/Intrigue 비공개 패널) → 종료 시 최종 순위 표. 여러 사람 좌석은 결정 좌석을 따라가는 hot-seat으로 처리한다.
- 검증: 실제 uvicorn + 브라우저에서 폼으로 draft 게임을 만들고(설정 화면 → Leader pick 클릭 → 라운드 1 turn frame), UI 자체 행동 버튼 경로로 103회 결정을 자동 구동해 10라운드 최종 순위까지 완주했다(서버 로그 오류 0). `/catalog`·정적 서빙 테스트를 추가해 pytest 829→833, Ruff, mypy 통과.

## 2026-08-31 M11 슬라이스 3 세션 요약 (FastAPI 게임 세션 서버)

- web 스택을 **FastAPI + uvicorn**으로 확정하고 `ui` optional extra와 `dune-imperium-server` CLI(기본 127.0.0.1:8000)를 추가했다(`4fbd751`). 개발 환경 준비 명령은 `uv sync --extra rl --extra ui`로 바뀌었다 (TestClient용 `httpx2`는 dev group).
- `server/sessions.py`의 `GameSessionManager`는 프레임워크 중립이다. 게임 생성은 좌석 배정(`human`/`heuristic`/`random`), `choam_module`, `leader_draft`, seed(미지정 시 SystemRandom, policy seed 기본은 sweep과 같은 700,000+game_seed)를 받고, 엔진 공개 API(`reset`/`current_decision`/`legal_actions`/`apply`/`observe`)와 러너 패턴의 seeded `ChanceResolver`만 사용한다. chance와 AI 좌석은 생성 직후와 사람 행동 뒤 자동 진행되어 세션은 항상 사람 결정 또는 종료 순위에서 멈춘다. 적용된 모든 step은 슬라이스 5(저장/불러오기)를 위해 replay 형식으로 기록한다.
- 비공개 경계: 사람은 자기 좌석의 직렬화된 `PlayerView`와 revision 가드가 붙은 index 기반 합법 행동 목록만 받는다. 둘 다 비공개 카드 identity를 담을 수 있으므로 AI 좌석 조회는 `SeatAccessError`(HTTP 403)로 거부하고, `state.event_log`는 PlayerView 밖이므로 노출하지 않는다(가시성 결정은 계속 `core/observation.py` 단독).
- HTTP 매핑: 미존재 게임 404, 비인간 좌석 403, revision 불일치 409, 기타 잘못된 요청 400, pydantic 형식 오류 422. endpoint는 게임 생성/목록/요약/좌석 view/좌석 행동 목록/행동 적용/삭제다.
- 검증: 세션 단위 테스트 9건(전원 AI 생성 즉시 완주와 seed 재현, 사람 좌석 정지, index 행동 2,000 step 완주, draft 시작 frame, 좌석·seed 검증, 삭제)과 HTTP 테스트 7건(4인 사람 draft 게임을 API로 라운드 1까지 진행 포함). 실제 uvicorn 기동 + curl 왕복도 확인했다. pytest 813→829, Ruff, mypy 통과.

## 2026-08-30 M11 슬라이스 2 세션 요약 (Leader draft)

- OQ-007의 6-Leader 공개 draft convention을 `RulesetConfig(leader_draft=True)` ruleset option으로 구현했다(`c0c1795`). reset이 pick과 무관한 setup chance(Conflict tier, Objective→First Player, 공개 pool 6종, Imperium·Intrigue·Contract 전체 셔플, 시작 덱 전체 셔플)를 seeded로 모두 해결한 뒤 `GamePhase.SETUP`의 `leader_draft` frame에서 멈춘다. pick은 라운드 1 turn 역순(First Player 마지막)의 player decision이고, pick마다 setup face 배정과 인쇄된 시작 카드 제거(이미 섞인 덱 필터링 — 남은 순서 균등성 유지)를 적용하며, 마지막 pick이 Contract 시장을 배분한다(Shaddam pick 시 Sardaukar 2장 set-aside). 고정 `DEFAULT_LEADER_IDS` 경로는 그대로다.
- action 공간은 옵션과 무관하게 고정이다: `pick_leader` 템플릿을 두 catalog에 상시 포함해 codec v79(기본 4,152, CHOAM 4,429). 관측은 v2로 올려 공개 pool 6-슬롯 세그먼트를 추가했다(1,415-int; pick 결과는 기존 좌석 Leader 슬롯). PettingZoo env에 `leader_draft` 옵션을 추가했고, draft episode는 pick 결정으로 시작한다.
- sweep은 census를 setup 종료 시점에 고정하도록 바꿨다(draft 중 Staban의 Limited Allies가 시작 카드를 정당하게 제거하므로). `--leader-draft` 플래그를 추가했다.
- draft soak(두 policy × 두 룰셋 × 500판)이 기존 엔진 버그를 하나 더 적발해 수정했다(`d70b353`, CHOAM seed 198): Treacherous Maneuver를 낸 뒤 Cunning의 자유 순서 trash slot으로 그 카드 자체가 trash되면 Agent box 해결이 무조건 self-trash를 실행해 crash했다. 기록된 OQ-022 convention (self-trash는 이미 충족, 나머지 효과는 해결)을 `apply_agent_card_trash`에도 적용했다.
- 검증: 수정 후 draft soak 총 2,000판(heuristic 1,000 + random 1,000, 모든 불변식·replay 검사) 실패 0, 비-draft heuristic 400판 회귀 통과. pytest 796→813, Ruff, mypy 통과.

## 2026-08-30 M11 슬라이스 1 세션 요약 (heuristic agent)

- M11 슬라이스 1을 완료했다(`1a449f4`): `HeuristicAgent`는 RandomAgent와 같은 `choose_action(observation, legal_actions)` 계약으로, 합법 행동을 정적 전략 점수(직접 VP > 영구 업그레이드 > 비용 비례 획득 > 최대 배치, decline/pass 최하)로 순위 매기고 동점은 seeded RNG로 깬다. 미지의 action id는 0점이라 새 콘텐츠에서 seeded random으로 degrade한다. 점수는 규칙 판정이 아니라 전략 선호이며 공개 카드 비용만 참조한다. `agents/base.py`의 `Agent` Protocol, `run_policy_game`(좌석별 agent 주입, `run_random_game`이 위임), sweep/CLI의 `--policy {random,heuristic}`을 함께 추가했다.
- heuristic soak(룰셋당 1,000판)이 random 10,000판이 못 가던 궤적에서 잠복 버그 두 계열을 적발했고, 공식 문서 확인 뒤 수정했다:
  - **Special Mission PlaceSpy slot 교착**(`7a53c8f`, CHOAM seed 97·901): play 시점 판정이 "자기 Spy recall = post 해방"으로 계산했지만 다른 플레이어 Spy가 공유한 post는 recall해도 비지 않고, slot은 도움 안 되는 recall만 무한 제시하다 행동 0개로 좌초했다. `[Main p. 11]`의 "비어 있는 post", "먼저 자기 Spy **하나**를 recall**할 수 있다**"(둘 다 선택)에 따라 slot 전 분기에 `decline_intrigue_spy`를 추가하고, recall은 배치로 이어질 수 있는 것만(빈 target이 있으면 아무 Spy, 없으면 allowed post의 단독 점유 Spy) 제시하며, play 시점 판정도 단독 점유 기준으로 고쳤다. codec v78. Distraction trigger가 slot 루프 중간에 끼어들어 조건이 drift하는 실제 사례를 확인했다(해결 시점 판정 원칙 유지).
  - **Imperium Deck 고갈 tripwire**(`ac4d6d4`, 기본 룰셋 6판): heuristic이 카드를 충분히 사서 공유 덱이 실제로 바닥났다. 공식 문서는 덱 위에서 보충한다고만 하므로(`[Main p. 13]`, OQ-004) 물리적으로 강제되는 유일한 진행을 convention으로 기록했다: 덱이 비면 Row는 보충 없이 남은 장수로 운영한다. 네 제거 지점이 `take_imperium_row_card` 헬퍼를 공유하고, 관측의 5-슬롯 Row 세그먼트는 빈자리를 0으로 둔다.
- 검증: 수정 후 heuristic 룰셋당 1,000판(총 2,000판)과 random 300판×2가 모든 불변식·replay 검사 포함 실패 0으로 통과했다. 교착 seed 97·901은 invariant-checked 회귀 테스트로 고정했다(`tests/integration/test_sweep.py`). pytest 770→796, Ruff, mypy 통과.

## 2026-08-30 계획 조정

- M11(사람용 플레이 인터페이스)을 M9·M10보다 앞으로 옮겼다. 근거와 순서 방침(번호 유지, 나열 순서 = 구현 순서)은 `implementation-plan.md` 마일스톤 절 서두에 있다. UI 형태는 로컬 웹 UI로, 초기 AI 상대는 random + 간단 heuristic(M9 재사용)으로 확정했다.
- Leader 선택 절차를 OQ-007의 구현 convention으로 확정했다: 합법 Leader 중 무작위 6종을 즉시 공개로 뽑고, First Player 확정 뒤 turn 역순으로 한 명씩 공개 pick(First Player가 마지막), 미선택 2종은 미사용. 공식 setup의 Leader 단계(`[Main p. 4]`)를 First Player 결정 뒤로 옮기는 ruleset option이며 공식 규칙이 아니다. 세부와 구현 지침은 [`rules/open-questions.md`](rules/open-questions.md#oq-007--leader-선택-절차)에 있다.

## 2026-08-30 M7 검증 sweep 세션 요약

- `dune-imperium-sweep`을 만들었다(`simulation/sweep.py`, `invariants.py`, `cli/sweep.py`): 매 전이의 전역 카드 census(개인 카드 instance 집합, Reserve 스택+생존 사본 방정식, Intrigue·Conflict·Contract·Objective 보존과 단일 존), 교착 검출, 표본 주기의 관측 누출 검사(deck 순서·상대 hand·상대 Intrigue `[Main p. 7]`·Contract bank `[Main p. 16]`만 뒤섞은 상태와 관측 동일성; 뒤섞기가 실제로 상태를 바꾸는지도 테스트로 고정), replay 검증, multiprocessing 병렬화와 CLI. pytest에 고정 seed 테스트 8건을 추가했다.
- 첫 룰셋당 10,000판 sweep이 46판(0.23%)에서 잠복 버그 다섯 계열을 적발했고, 모두 해결 시점 판정 원칙(`[Main pp. 9, 20]`, `[Main p. 12]`)으로 수정했다: Spy Network recall 교착(`f148c14`), Maker Keeper·Wheels Within Wheels·Bond 3종 조건 drift와 Corrinth City 선택 소실과 self-trash 보류 효과(`83aa4f5`, OQ-022 convention 신설), Price is No Object 획득 Spy frame 정지(`24b13e7`).
- 수정 후 재실행한 룰셋당 10,000판(총 20,000판, 모든 검사+replay 포함)이 실패 0으로 통과했다: 400초, 50 games/s, 전이 약 879만 회, 라운드 중앙값 10. M7을 완료로 표시했다.

## 2026-08-30 전체 게임 RL 전환 세션 요약

- 설계 확정([`rl-environment.md`](rl-environment.md)): 관측 v1은 PlayerView 순수 함수인 1,409-int 평면 벡터(세그먼트 표 export, egocentric 좌석 회전, identity 카운트/슬롯/tri-state), 보상은 승자독식 zero-sum 종료 보상만, chance는 env 내부 seeded 해결. 상대 hand·deck·discard·Intrigue 장수 공개를 OQ-010 부분 convention으로 기록했다.
- `run_random_game` 러너(`GameSimulation(state, standings, replay)`)와 `dune_imperium_uprising_v1` env 전환을 구현했다. per-step VP delta 보상은 제거했고 종료 `infos`에 rank·VP를 노출한다. codec은 v77 그대로다.
- PlayerView에 결정 frame 요약(kind·결정 소유자·turn 소유자)과 공개 존 장수를 추가했다. frame별 세부 컨텍스트 공개는 kind별 화이트리스트 검토 후로 미뤘다.
- random 전체 게임에서 기존 엔진 버그를 하나 더 수정했다(`4d9efb8`): Espionage recall 뒤 자유 순서 효과가 그 Spy를 소비하면 배치가 crash하던 것을 해결 시점 supply 재확인과 recall 재개방으로 바꿨고(`[Main pp. 11, 20]`, Agent-card Spy 경로와 동일 패턴), supply 0에서 decline이 빠져 있던 것도 인쇄 효과의 선택성(`[Board Guide p. 1]`)에 따라 복원했다.
- 검증: env 경유 18판(기본 12+CHOAM 6) random full episode soak에서 승자독식 zero-sum 보상 불변식을 확인했고(약 4,100 agent step/s), 두 룰셋의 random 완주 전 상태 인코딩 sweep, PettingZoo api/seed 테스트, 755개 테스트·Ruff·mypy가 통과한다.

## 2026-08-30 Objective 감사 세션 요약

- 핸드오프의 "남은 Objective 상호작용 재감사"를 완료했다. setup 배정, Combat 즉시 icon matching, Endgame wild matching, Endgame Intrigue의 `FlipBattleCard`(Objective 제외, wild 대체 허용), 관측 공개 범위가 규칙 문서와 일관됨을 확인하고 `implementation-audits/objectives.md`에 기록했다.
- OQ-005를 RESOLVED로 갱신했다: Combat 즉시 matching은 의무 pair가 도착 즉시 해소되므로 공식 콘텐츠에서 printed icon당 face-up 한 장을 넘을 수 없고(wild는 Propaganda 한 장뿐), Endgame wild의 복수 후보 선택은 OQ-001 window의 소유자 행동으로 이미 구현돼 있다. Combat 다중 후보 `NotImplementedError`는 미래 콘텐츠 tripwire로 유지한다.
- 감사 soak에서 기존 엔진 버그를 발견해 수정했다(`fa99359`): Junction Headquarters의 Intrigue+Spice 지불 frame이 `pending_agent_effect`를 해제하지 않아 화살표를 반복 지불할 수 있었고(한 턴 한 번 규칙 위반 `[Main p. 9]` `[FAQ p. 3]`), 지불 뒤 Spice가 2 미만이면 다음 legal-action 열거가 RuntimeError로 crash했다(seed 20010). 아울러 세 지불 legal provider(Junction HQ, Ecological Testing Station/Smuggler's Haven, Corrinth City)가 큐 후 지불 불가 상태에서 raise하던 것을 자유 순서 해결 시점 판정 `[Main pp. 9, 20]`에 따라 decline만 제시하도록 바꿨다 (Prepare the Way `87a9300`과 같은 판정 방식, 회귀 테스트 4건).
- 검증: 기본 60판 + CHOAM 20판 random FINISHED 완주 soak(replay 검증, 매 전이 face-up 불변식 assert)에서 즉시 pair 181/62회, Endgame wild 32/8회, Endgame Intrigue flip 1/0회 발동을 확인했다. endgame·combat 감사 문서의 창 이전 서술과 Combat Intrigue/Shield Wall 잔재 서술도 현재 구현에 맞게 갱신했다.

## 2026-08-30 Shaddam 세션 요약

- standard Contract manifest를 교정했다: 6인 보충 규칙의 base-CHOAM setup이 "두 Sardaukar contract"를 set aside하라고 지시하므로 Sardaukar 2장이 20장에 속하고, 공간별 구성 합산과 타일 이미지의 Rise of Ix Tech 보상으로 이전 세 번째 High Council 타일이 RoI jumpstart 타일의 오전사임을 확정했다. Sardaukar II의 Agent recall 보상(`[Main p. 20]`의 방금-보낸-Agent 제외)을 `CONTRACT_REWARD_RECALL` frame으로 연결했다(codec v76).
- Shaddam Corrino IV를 구현해 인쇄된 Leader 9종을 완결했다: Sardaukar Commander의 setup set-aside와 시장 frame 내 전용 선택(시장 보충 없음, 고갈 시 2 Solari 전환은 OQ-021 convention), Emperor of the Known Universe의 (Solari+troop | 3 Solari→Influence) 선택과 배치 즉시 발효되는 turn 한정 unit 배치 차단(Combat 배치·Maker 소환·Intrigue 배치 option·SummonSandworm 무효)이다(codec v77).
- 검증: Shaddam 포함 CHOAM 조합 30판 random FINISHED 완주 soak에서 set-aside take 27회, signet 선택 85회, contract Agent recall 발동을 확인했고 기본 조합 25판 회귀와 replay 검증을 통과했다.

## 2026-08-29 Leader 세션 요약

- 기본 게임 Leader 8종의 능력과 Signet Ring을 카드 이미지로 검증해 모두 구현했다(codec v72→v75, 테스트 668→727). space 유형 아이콘(City 파란 원, Landsraad 초록 오각형)은 Board Space Guide artwork로 확정했다.
- Gurney(Warmaster recruit, Always Smiling 문턱 6), Amber(Fill Coffers, Desert Scouts retreat), Feyd(분기형 Personal Training 트랙과 Devious Strength), Jessica 양면(Spice Agony memory, Other Memories flip, Water of Life, Reverend Mother board repeat), Margot(Loyalty, City Spy), Muad'Dib(Lead the Way, Unpredictable Foe), Irulan(Imperial Birthright, Chronicler's Insight), Staban(Limited Allies 9장 덱, Smuggle Spice, Unseen Network)이다. 세부와 근거는 `implementation-audits/leaders.md`.
- 새 convention 4건을 OQ-017~OQ-020으로 기록했다(Feyd 맨 오른쪽 칸 무보상, memory 0개 flip 허용, Reverend Mother 반복의 Influence 제외 `[Main p. 7]`, Always Smiling 미회수).
- 기존 버그 수정: Prepare the Way(그리고 Hidden Missive)의 조건부 Agent 효과가 배치와 해결 사이 Influence 하락 시 legal로 제시된 뒤 실패하던 것을 해결 시점 판정의 우아한 무효(no-op)로 바꿨다(`87a9300`, docs/rules/player-turns.md의 자유 순서 조건 판정 문장 인용).
- 검증: Leader 4종 기본 조합 60판 + 신규 4종 조합 25판 random FINISHED 완주 soak(replay 검증 포함)에서 모든 신규 경로의 발동을 이벤트 수로 확인했다.

## 2026-08-29 세션 요약

- Impress(Combat: 검 2 + 비용 3 이하 획득)와 Inspire Awe(Plot: 비용 3 이하 획득, sandworm이 Conflict에 있으면 hand로)를 카드 이미지로 검증해 전사했다. 이전 핸드오프의 "Impress 비용 4"는 오기였다.
- `AcquireCardUpTo(max_cost, to_hand_if)` DSL 보상과 `acquire_intrigue_imperium` / `acquire_intrigue_reserve` 선택 슬롯을 추가했다. Row 보충, acquire box 즉시 처리, Spy 배치 box의 `acquisition_spy` frame 재사용(카드 해결 후 push), Contract 완료 확인을 기존 획득 경로와 공유한다. codec v65.
- Reveal 중 hand로 들어가는 획득은 OQ-015(c)를 확장해 draw와 동일하게 보류한다.
- Call to Arms를 첫 face-up trigger로 전사했다: `IntrigueOption.trigger`, 공개 `PlayerState.intrigue_faceup` 존, `rules/intrigue_triggers.py`의 Reveal 획득 발동과 Reveal 종료 만료(OQ-016), codec v66. Distraction과 Leverage의 카드 이미지 검증도 마쳤다(Leverage 보상에 대한 DIU의 "덱 draw" 기록은 Contract 아이콘 오독이며, Reach Agreement 아이콘과 대조해 확정).
- Distraction을 배치 trigger로 전사했다: `PlayerState.units_deployed_turn` 카운터(6개 배치 지점, Control defense 제외), dispatcher 전이 후 `intrigue_trigger_spy` frame 제시, 다른 플레이어 Spy가 있는 post에의 공유 배치와 recall-first, 거절 시 face-up 유지(OQ-016(c)), codec v67.
- Leverage를 play 시점 조건으로 전사했다: `spice_at_turn_start` 스냅샷 + `spice_spent_turn` 카운터(지출 5지점)로 "이번 turn 총 획득 spice"를 계산하고, 조건 성립 시 Contract 1 + Solari 1을 준다. Harvest의 placement 기준 회계와는 분리 유지. codec v68.
- Endgame Intrigue window(OQ-001 convention)를 열었다: First Player부터 시계 방향 1회 순회, window 안에서 Endgame play와 wild matching 자유 순서, pass가 창을 닫고 마지막 pass가 게임을 끝낸다. 기존 단일 무모호 wild 자동 경로와 `declined_endgame_wild_card_ids`를 대체했다(codec v69). 이어서 Endgame 6종(Crysknife, Desert Mouse, Ornithopter의 spice/flip 이중 절반, CHOAM Profits, Secure Spice Trade, Shadow Alliance)을 전사했다(codec v70). Shadow Alliance의 "상대가 Alliance를 보유한 트랙" 조건을 DIU가 누락한 것을 카드 이미지로 확인해 기록했고, 조건 DSL이 전체 상태를 읽도록 바꿨다. random 4인 게임 60판이 처음으로 FINISHED까지 완주됐다(창 240개, wild 27회, replay 검증 통과).
- Manipulate와 Spring the Trap을 전사해 Intrigue 39개 identity(44장)를 완결했다. Spring the Trap은 Spy 2 recall → 검 7(기존 primitive), Manipulate는 `SetAsideImperiumRowCard` 슬롯 + 공개 `imperium_set_aside` 존 + Reveal 한정 할인 획득 + Reveal 종료 시 `imperium_removed`로 게임 제거(FAQ p. 3). codec v71. random 완주 60판에서 set-aside 21회 = 획득 2 + 만료 19로 보존이 검산됐다. 참고: 기존 Prepare the Way 버그(별도 작업)는 신규 카드로 legal action 목록이 바뀌며 최신 soak의 seed 10146 궤적에서는 더 이상 나타나지 않지만, `ed16d93`에서 그대로 재현된다.
- 알려진 기존 버그(이번 슬라이스와 무관, HEAD `ed16d93`에서 재현): 4인 기본 룰셋 seed 10146 random play에서 Prepare the Way를 Agent 카드로 낼 때 `resolve_agent_card_effect`가 legal로 제시된 뒤 적용 시 "conditional Agent effect is not available"로 실패한다. legal 제공자와 `rules/agent_effects.py:1523` resolver의 조건 판정 불일치로 보이며, 별도 수정 작업으로 분리했다.

## 2026-08-28 세션 요약

- Codex → Claude Code 전환. `AGENTS.md`를 도구 중립으로, `CLAUDE.md`를 진입점으로.
- 리팩토링 A·B: `DecisionFrame.kind`, `rules/frames.py`, 표 기반 dispatcher. 그 과정에서 Covert Operation deadlock, Reserve copy ID 재발급, Spy 공급 판정 버그 수정.
- effect DSL(C 단계)과 Intrigue: Plot 19종·Combat 10종, 선택 슬롯 frame, Intrigue draw 공통 reshuffle 경계, OQ-003·OQ-015 convention.
- 처리량: 입력 불변 hash 가드를 opt-in으로 바꿔 random play 약 45배 가속.
- 코드 리뷰(`/code-review`) 후속 항목은 `refactoring-plan.md` 끝에 있다.
- 교훈: 리뷰 지적을 규칙 문서 확인 없이 반영해 Harvest 계약 판정을 잘못 바꿨다가 되돌림 → `lessons.md`, `AGENTS.md` 규칙 인용 의무.
