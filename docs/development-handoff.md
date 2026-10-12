# 개발 인수인계

기준일: 2026-10-12 (코드 `adf6785a`, engine-speed-audit 엔진 수집 최적화)

새 개발 세션(Claude Code, Codex 등 어떤 도구든)이 저장소의 **지금 상태**를 빠르게 복구하는 문서다. 날짜별 작업
기록은 [`worklog/`](worklog/)의 월별 파일(이번 달 [`worklog/2026-10.md`](worklog/2026-10.md), 최신이 위)에 있다.
규칙의 규범 근거는 [`rules/README.md`](rules/README.md), 마일스톤과 완료 조건은
[`implementation-plan.md`](implementation-plan.md), 카드별 세부 동작은
[`implementation-audits/`](implementation-audits/)를 따른다.

**이 문서를 고치는 법.** 작업을 병합할 때 자세한 기록(요청, 바뀐 것, 검증, 남은 것)은 그달 worklog 맨 위에 쓴다.
이 문서는 기준선 숫자, 진행 중·다음 작업, 알아 둘 것이 바뀔 때만 고치고, 그때 기준일도 바꾼다. 날짜별 기록을
여기 쌓지 않는다(사용자 결정 2026-10-12: 기록이 783 KB까지 쌓여 세션이 기준선까지 읽지 못했다). 2026-10-12 정리
전의 이 문서 본문(옛 기준선·다음 구현 순서·원격 저장소 기록)은
[`worklog/handoff-core-before-2026-10-12.md`](worklog/handoff-core-before-2026-10-12.md)에 그대로 있다.

## 세션 시작 체크리스트

1. `AGENTS.md`(도구 중립 공통 지침), 도구별 진입점(Claude Code는 `CLAUDE.md`), `README.md`, 이 문서,
   [`lessons.md`](lessons.md)의 맨 위 "지금 지키는 규칙", 그리고 이번 달 worklog의 맨 위 기록 몇 개를 읽는다.
2. `git status --short`와 `git log --oneline -10`으로 작업 트리를 본다. 기존 변경은 사용자 작업으로 보고 덮어쓰지 않는다.
3. `git fetch origin` 뒤 `git log --oneline origin/master..master`와 `master..origin/master`를 둘 다 본다. 여러
   기기에서 작업하므로 원격이 앞서 있으면 먼저 맞춘다. 비공개 에셋 저장소(`assets` → `../Dune-Imperium-assets`)도 같다.
4. `uv sync --extra rl --extra ui --extra train` 뒤 `uv run pytest -q`, `uv run ruff check src tests`,
   `uv run mypy src tests`. 결과가 아래 기준선과 다르면 코드가 옳다. 이 문서를 같은 작업에서 고친다.

## 기준선

| 항목 | 값 |
| --- | --- |
| 코드 기준 | `adf6785a` (engine-speed-audit, 2026-10-12) |
| pytest | 7,519개 수집, WSL 전체 7,510 통과·9 skip(2026-10-12 엔진 수집 최적화) |
| Ruff · mypy | `src tests` 통과, mypy 485파일. `scripts/`에는 기존 Ruff 오류 68건이 있다(검사 대상 아님); 새 `compare_engine_collection.py`는 Ruff 통과 |
| 브라우저 E2E | `scripts/e2e/` 62종(+ 이름으로만 도는 `rehearsal`). 마지막 전체 실행은 2026-10-12 "접합 두 칸" 병합 |
| action codec | **v145** (다음 번호 v146) |
| 관측 | v31, 4,537 int |
| action catalog | 기본 4,413 · CHOAM 4,704 · 옵션 전부(CHOAM·프로모·Bloodlines·Tech·Immortality·Epic·Scouts) 35,972 |
| 로컬 서버 기본 AI | 앱 AI 어려움(`app_ai`). 원격 방의 좌석 기본값은 사람 |
| 탐색 AI 망 | Mac mini의 `checkpoints/play/search.pt` → `mix-v139-10081.pt`(X). 학습 계보의 머리는 Y@10881(v141 재적응) |
| 에셋 저장소 | `c4cf579` (2026-10-12 push) |

## 진행 중·다음 작업

출처는 worklog의 기록 제목(날짜)이다. **(결정)**은 착수 전에 사용자에게 물을 것.

**학습·AI**

- **(결정) readapt-v143 판정.** 대조군 C(`C/iteration_11681.pt`)만 돌렸다. 점수 보상 갈래 S(`--score-rewards`)와
  판정 `judge.sh`(G1 S 대 C, G2 C 대 Y, G3 S 대 Y)는 안 돌렸다. C가 Y보다 나은지는 G2만 따로(1,400판, 약 25분)
  돌려도 안다. 판정 전이라 계보의 머리는 Y다. [2026-10-12 readapt-v143]
- **(결정) 플레이 서버 망을 X에서 Y로 바꿀지.** 망끼리는 Y가 X보다 낫다. 탐색 좌석으로 쟀을 때도 그런지
  (`search:Y` 대 `search:X`)를 재고 사용자가 정한다. [2026-10-11 v142 재적응 Z@11681]
- **(결정) 다음 학습 후보:** ExIt v2 이어 하기(510판에서 멈춤; 옛 엔진으로 이어 갈지 새 codec으로 다시 할지),
  사람 판 국면의 ExIt 레이블(미룸). 사람 판이 쌓이면 진단을 다시 돌린다.
  [2026-10-09 학습 정리: expert iteration v2, 2026-10-10 사람 문제집·사람이 둔 판]
- **탐색 AI의 첫 턴 가문 핵:** 분석만 했다(사용자 "다음에 다루기"). 탐색 없이 망이 바로 답하는 Agent 효과 순서
  결정에서 가문 핵 로짓이 상황과 무관하게 높다. Y도 같다. [2026-10-10 플레이 피드백 10항목]
- **tips-v1의 5081 행 다시 캐기:** v144에서 heuristic 행만 다시 캤고 5081 행은 이어받았다. [2026-10-12 OQ-107]
- **수집 작업 프로세스 수 다시 재기:** 좌석 구성별로 고르게 나눈 뒤라 2026-09-19의 "4가 가장 빠름"이 바뀌었을
  수 있다. [2026-10-12 학습 수집 약 2배 빠르게]
- **엔진 수집 최적화:** 검사 유지 상태 복사와 앱 AI 고정 메타데이터의 순수 함수 재사용을 구현했다.
  WSL/5081/8판 Collector 대조의 감소 중앙값은 self-play 1.2%, 혼합 13.0%, 2 worker 혼합 11.6%
  (마지막은 pool 시작·전송 포함)다. 공개 좌석 캐시는 이득이 일관되지 않아 적용하지 않았다.
  최신 Y·Mac의 실제 32판/4 worker와
  이미 열린 수집 pool에서 효과·worker 수를 다시 재야 한다(이번 기기에는 5081 망만 있다).
  `PlayerState.__post_init__`는 검증과 함께 `hand_public` 정규화도 하므로 비우면 관측이 바뀐다.
  [`evaluation/engine-throughput-2026-10-12.md`](evaluation/engine-throughput-2026-10-12.md)
- 작은 것: heuristic은 Harkonnen Advisor의 배치 못 하는 병력과 Emperor of the Known Universe의 막기를 모르고,
  Plot을 Agent 뒤에 내서 Emperor's Invitation #1·Insider Information #1·Twisted Resourceful을 못 쓴다.
  [2026-10-06 Steam 앱과 카드·보드 전수 대조]

**규칙·엔진**

- **"합법 행동 없음" 결함:** 약 4,000판에 한 판꼴로 나왔고 그 뒤 약 64,000판에서 재현되지 않았다. 다시 나오면
  `stalls/`에 남는 상태로 고친다. [2026-10-06 탐색 AI 좌석·L3 재학습, 2026-10-07 학습: 앱 AI 섞기 대 self-play만]
- Glowglobes·Navigation Chamber의 Tech 획득 아이콘이 여전히 6인 진영을 내놓는다(v137 경계). [2026-10-06 Steam 앱과 카드·보드 전수 대조]
- Ghola + Subversive Advisor의 2+2=4는 project convention이다(`rules/open-questions.md` OQ-022 보강의 남은 의문).
- 테스트 빈자리(낮음): 여러 칸 Influence 잃기(OQ-014)의 직접 테스트, 0-supply Control 방어 frame의 서버·E2E 테스트.
  [2026-10-07 Steam 앱과 일반 규칙 대조, 2026-10-04 Steam 앱 대조와 앱 방식 재판정]

**플레이 화면**

- **미룬 연출:** ③ 카드 사기, ⑤ 동맹 띠·영향력 큐브, ⑦ Conflict 카드가 승자에게, ⑧ 라운드 정리, ⑩ 연출 끄기 설정.
  [2026-10-08 게임다운 연출 4~5단계, [`ui-improvement-plan.md`](ui-improvement-plan.md) 12단계]
- **한국어 화면에 남은 영어:** ③ "AI", ⑤ 설정 화면의 OQ 번호·경로·명령 인자, ⑧ 서버 오류 문구, ⑨ 런처 로그·창 제목.
  ⑥ 도움말 범례의 영어 병기는 사용자 결정으로 그대로 둔다. [2026-10-11 공식 한국어가 있는 남은 영어를 한국어로]
- **(사용자) 한글판 카드 그림:** 한국어 사진이 없는 Uprising 책략 34장과 Bloodlines·Twisted 책략 23장은 한국어
  화면에서도 영어 앞면이다. 사용자가 한글판을 찍어 주기로 했다. [2026-10-07 Steam 앱 그림, 2026-10-11 Bloodlines 책략·Twisted 책략 앞면]
- 화면에 없는 정보: 빚진 Spy 수(관측·뷰에는 있음), Harvest Cells 선택 화면의 Reclaimed Forces specimen 비용(Reveal
  패널에만 있음). [2026-10-04 저녁 앱 방식 재판정 둘째 묶음, 2026-10-06 Steam 앱과 카드·보드 전수 대조]
- 플레이 시계 후속 후보: 접속이 끊긴 동안 멈춤, 수마다 시각(검토 화면에 시계), 저장 목록의 플레이 시간.
  작은 흠: 끼어든 답 뒤 배너의 "이번 차례"가 0에서 다시 시작, 멈춘 동기 AI 동안 시계가 흐름. [2026-10-11 플레이 시계]
- **선택 불가 표시 3단계(옛 C1, 18곳):** 일부만 됐다. 2026-10-12 대조에서 다 된 곳 3, 일부 5, 없음 10이다(행 번호는
  [`unavailable-options-plan.md`](unavailable-options-plan.md) 머리말). 사용자 결정(2026-09-30)은 "3단계는 전부 한다"이다.
- 정리 후보: `display/board_layout.py`가 내는 `tracks.garrisons`·`tracks.conflict_quadrants`를 클라이언트가 더 읽지 않는다.

**도구·인프라**

- **서버 런처 7단계:** Windows 실기 검증. [`server-launcher-plan.md`](server-launcher-plan.md)
- **기보 묶음:** codec이 오를 때마다 다시 만든다. 최신 묶음은 v143-944bb1b7이고 v144·v145 묶음은 없다. v145의 새 다리
  `boost_draw_at_turn_end`를 쓰는 장면이 묶음에 없다. [2026-10-12 Ghola, [`human-records.md`](human-records.md)]
- 부하에서만 깨지는 검사: E2E `table_layout`의 "the last card remains visible", 런처 supervisor 테스트의 2초 단언
  (`test_a_local_server_stops_on_its_closed_input_with_a_stream_open`). 둘 다 혼자 돌리면 통과한다.

## 알아 둘 것

- **저장본과 codec.** 플레이 서버는 저장본의 ruleset·content 버전과 `ACTION_CODEC_VERSION`이 정확히 같아야
  불러온다(`server/persistence.py`). codec을 올리면 그 전의 저장은 서버에서 열리지 않는다. 사람이 둔 판은
  `dune-imperium-records`가 지금 엔진의 기보로 옮긴다. 엔진이 묻는 결정을 바꾸면 그 codec 문턱의 다리를
  `records/`에 더하고 `uv run dune-imperium-records check`로 확인한다([`human-records.md`](human-records.md)).
- **상태 해시.** 이벤트를 상태의 `event_log`에 새로 넣으면 그 뒤 모든 상태 해시가 바뀌어 옛 저장이 열리지 않는다.
  화면에만 필요한 이벤트는 `report_only_event_kinds`(`rules/engine.py`)로 보고만 한다.
- **측정 비교.** 엔진이나 수집 코드가 바뀌면 같은 시드라도 다른 판이 나온다. 수집은 `85a51097`(2026-10-12) 전후,
  heuristic은 v143(접합 turn) 전후가 그렇다. 비교는 같은 코드에서 대조군을 registry에 고정해 번갈아 잰다.
- **학습·측정과 체크아웃.** 몇 시간짜리 학습·측정은 고정 worktree(`measure-vNNN`)에서 돌린다. 학습이 도는
  체크아웃에서는 `src/`가 바뀌는 pull을 하지 않는다. 몇 시간 걸리는 실행은 착수 전에 사용자에게 묻는다.
- **공유 체크아웃.** 여러 세션이 같은 메인 체크아웃을 쓴다. 메인 체크아웃은 master에 두고 작업은 worktree에서 한다.
  2026-10-11에 한 세션의 병합이 메인 체크아웃에 걸려 있던 다른 세션의 브랜치에 들어갔다.
- **떠 있는 서버.** 규칙이나 카탈로그가 바뀐 뒤에는 떠 있는 플레이 서버를 다시 띄워야 적용된다(정적 파일은 즉시).

## 원격 저장소 인계 주의

- 메인 저장소와 비공개 에셋 저장소를 함께 push·pull한다. 에셋이 없는 기기도 동작은 같다(그림 대신 텍스트).
- 에셋 저장소의 이력에는 게임이 실제로 읽는 파일만 둔다. 참조 자료·중간 산출물은 `.gitignore`로 git 밖에 둔다
  ([`lessons.md`](lessons.md) 2026-09-23·09-28).
- 에셋 저장소를 push하기 전에 안 올린 커밋을 하나로 합쳐(`git reset --soft origin/master` 뒤 한 커밋, 본문에 원래
  제목 목록) 다시 그린 그림의 옛 판이 이력에 남지 않게 한다. 합치기 전 커밋은 로컬 백업 브랜치로 남긴다(사용자
  결정 2026-10-12, `c4cf579`).
- 에셋 저장소의 이력은 2026-09-23과 09-28에 다시 썼다. 그 전에 pull한 기기는 로컬 변경이 없는지 본 뒤
  `git fetch origin && git reset --hard origin/master`로 맞춘다. 옛 커밋을 가진 채 push하면 지운 커밋이 되살아난다.
- `checkpoints/`는 git 무시라 기기 사이에는 파일을 복사한다. 탐색 AI 망을 바꿀 때는 새 이름으로 복사한 뒤
  `search.pt` 링크만 바꾼다. 저장 파일은 그 망 파일에 묶여 있어 옛 파일을 지우거나 덮어쓰면 그 저장을 못 연다.
- 원격의 `kyungtae` 브랜치는 병합하지 않은 다른 사람의 브랜치다. 건드리지 않는다.

## 코드 탐색 지도

| 목적 | 주요 위치 |
| --- | --- |
| 카드 manifest와 typed 효과 | `src/dune_imperium/content/uprising/` (Leader identity·Feyd track은 `leaders.py`) |
| Leader 능력과 Signet Ring | `rules/leader_abilities.py`, reach-2 보너스와 Navigation trigger는 `rules/influence.py`, Staban의 Smuggle Spice와 Esmar의 Tuek's Sietch 방문은 `rules/agent_turn.py`; Bloodlines 전용은 `rules/tactics.py`(Chani), `rules/planetologist.py`(Kynes), `rules/navigation.py`(Y'rkoon) |
| Bloodlines 구성물 | `content/bloodlines/sardaukar.py`(Commander·Skill), `content/uprising/imperium.py`·`intrigue.py`의 `bloodlines_only`/`tech_only`/`twisted`/`navigation` 항목, `rules/sardaukar.py`, `rules/spy_moves.py`·`rules/unit_loss.py`(상대 결정 frame), `rules/optional_trash.py` |
| Immortality 구성물 | `content/immortality/board.py`(research·Tleilaxu track), `content/immortality/tleilaxu.py`(Tleilaxu deck·Reclaimed Forces·프로모 Piter), `content/uprising/imperium.py`·`intrigue.py`의 `immortality_only` 항목, 접합 두 칸은 `rules/graft_boxes.py`; 규칙 명세 `docs/rules/immortality.md`, 전사표 `docs/implementation-audits/immortality.md` |
| Tech Module | `content/bloodlines/tech.py`(tile 18장·`TechAbility`), `rules/tech.py`(Acquire Tech·Flip·Forbidden Weapons 선택·Suspensor/빚진 draw hook·Endgame 효과·Secret Project), `rules/ornithopter.py`(Fleet 매칭); 상시 능력은 `agent_turn.py`(Navigation Chamber·Servo-Receivers)·`sardaukar.py`(High Command·Plasteel Blades)·`board_effects.py`(Gene-Locked Vault)·`core/observation.py`(Glowglobes)·`reveal_turn.py`(Command tile·Panopticon·Forbidden Weapons frame)·`contract_tiles.py`(CHOAM Transports)·`combat.py`(Planetary Array·Fleet); Kota의 Signet은 `leader_abilities.py` |
| Agent 배치와 카드 효과 | `rules/agent_turn.py`, `agent_effects.py` |
| Reveal과 acquire | `rules/reveal_turn.py`, `acquisition.py` |
| phase·Combat·Endgame | `rules/phases.py`, `combat.py`, `endgame.py` |
| dispatcher 표와 frame kind | `rules/engine.py`(`LEGAL_ACTION_PROVIDERS`·`ACTION_HANDLERS`·`report_only_event_kinds`), `frames.py`, `agent_effect_frame.py` |
| effect DSL과 Intrigue | `content/uprising/effect_dsl.py`, `intrigue.py`, `rules/effect_interpreter.py`, `rules/intrigue.py`, `rules/intrigue_deck.py`, `rules/intrigue_triggers.py` |
| 고정 action catalog | `adapters/action_codec.py` |
| 관측과 PettingZoo | `core/observation.py`, `adapters/observation_encoding.py`, `adapters/pettingzoo_env.py` |
| replay와 random 러너 | `core/replay.py`, `simulation/runner.py` (한 라운드·전체 게임) |
| 플레이 서버·저장·검토 | `server/` (`sessions.py`, `persistence.py`, `autosave.py`, `app.py`, `catalog.py`, `turn_end.py`, `play_clock.py`, `static/`) |
| 원격 멀티플레이 접근 계층(M14) | `server/access.py`(모드·`Credentials`·토큰), `sessions.py`의 `claim_seat`·`release_seat`·`identify`·`_authorize_seat_locked`·`require_admin`, `app.py`의 쿠키 ↔ `Credentials`, `cli/server.py`의 `--remote`; 설계는 [multiplayer-design.md](multiplayer-design.md) |
| 서버 런처 | `launcher/` (`gui.py`·`view.py` 창, `supervisor.py` 서버 기동·종료, `cli.py`); 계획 [server-launcher-plan.md](server-launcher-plan.md) |
| 표시 텍스트·이미지 매핑 | `display/` (DSL·구조체 렌더러, 한국어 쌍둥이 `*_ko.py`·`names_ko.py`, 공간·Leader 텍스트, 이미지 파일명, 선택 불가 이유 `unavailable.py`) |
| 검증 sweep과 불변식 | `simulation/sweep.py`, `simulation/invariants.py`, `cli/sweep.py` |
| 대회 도구와 보고서 | `evaluation/tournament.py`(spec·러너·계측), `evaluation/report.py`(집계·Markdown/JSON), `agents/registry.py`(이름 붙인 baseline), `cli/tournament.py`; 기록 `docs/evaluation/` |
| AI 좌석 | `agents/heuristic_agent.py`, `agents/rollout_agent.py`, `agents/determinize.py`(관측자 지식과 일치하는 세계 표본), `agents/app_ai/`(Steam 앱식 AI, [app-ai-plan.md](app-ai-plan.md)), `agents/network_search_agent.py`(탐색 AI, [search-ai.md](search-ai.md)) |
| self-play와 학습 | `training/selfplay.py`, `collect.py`(작업 프로세스에 판 나누기 `deal`), `policy.py`, `network.py`, `torch_policy.py`(`TorchBatchPolicy`·`NetworkAgent`·체크포인트 로더), `checkpoint.py`, `learner.py`, `loop.py`, `expert.py`·`distill.py`(ExIt), `cli/selfplay.py`·`cli/train.py` |
| 사람 기보와 문제집 | `records/`(`migration.py` 다리, `saves.py`, `corpus.py`, `problems.py`), `cli/records.py`; `evaluation/problem_set.py`, `cli/problems.py`([evaluation/problem-set.md](evaluation/problem-set.md)) |
| 카드별 회귀 테스트 | `tests/unit/content/`, `tests/unit/rules/` |
| 통합·adapter·서버 테스트 | `tests/integration/`, `tests/adapters/`, `tests/server/` |

모든 경로는 `src/dune_imperium/` 아래다(테스트 제외). 개인 카드 draw·Spy·Combat·Endgame의 민감한 설계 결정은
`docs/implementation-audits/`의 주제별 문서를 먼저 확인한다.

## 처리량 메모

`RulesEngine.verify_input_immutability`는 매 전이마다 state 전체를 canonical hash하는 디버그 가드라 기본 off다(켜면
random play가 약 70 step/s, 끄면 약 3,000 step/s). 커널 테스트 엔진만 이를 켠다. 완주 soak은 `run_random_game`이나,
불변식·누출 검사와 replay 검증까지 하는 `dune-imperium-sweep`을 쓴다.

성능을 재는 절차는 [evaluation/throughput-2026-09-10.md](evaluation/throughput-2026-09-10.md)에 있다. **CPU 경합에
면역인 지표(cProfile의 호출 횟수, step 수)를 먼저 잡고**, 소요 시간은 기계가 조용할 때 트리를 번갈아 잰다.
cProfile의 *누적 시간*은 호출 수에 비례해 부풀므로 트리 간 비교에 쓰지 않는다.

학습 수집(2026-10-12, `fast-collect`): 표본 경로가 합법 행동의 정책 머리 행만 읽고, 판을 좌석 구성별로 고르게
나눠 수집이 약 2배 빨라졌다. 새 병목은 셀프플레이 판의 엔진(규칙 진행·관측 만들기, 76%)과 앱 AI 판의 앱 AI(46%)다.
작업 프로세스마다 판 묶음 하나를 받는 구조(묶음 수 = 작업 프로세스 수)는 그대로다.
엔진 내부의 후속 계측과 실제 구현·수집 대조는
[engine-throughput-2026-10-12](evaluation/engine-throughput-2026-10-12.md)에 있다.
WSL·5081, 위 Mac·Y 측정과 직접 전후 비교하지 않는다. 병렬 대조 도구의 값은 pool 시작·전송까지 포함한다.

## 유용한 명령

```bash
# 플레이 서버 (기본 http://127.0.0.1:8000); 원격 방은 docs/remote-play-host-guide.md
uv run dune-imperium-server
caffeinate -i uv run dune-imperium-server --remote --host <tailscale 주소>

# 서버 런처 진단(창 없이)
uv run python -m dune_imperium.launcher.cli --check

# 브라우저 E2E (Playwright는 scripts/e2e/.venv에만; scripts/e2e/README.md)
(cd scripts/e2e && .venv/bin/python run_all.py)              # 62종을 4개씩; 고른 것만: run_all.py lang narrow
(cd scripts/e2e && E2E_HOST=100.x.y.z .venv/bin/python rehearsal.py)   # 실제 원격 판 전 리허설

# 검증 sweep: 카드 보존·교착·관측 누출·replay 검사
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8 --policy heuristic --leader-draft
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8 --immortality --go-to-11

# 대회: 이름 붙인 상대들의 교차 대전 (도움말: --help)
uv run dune-imperium-tournament --agents app_ai,heuristic --games 100 --ruleset both --markdown report.md   # 이름은 네 좌석에 돌려 앉힌다

# 사람 기보·평가 문제집; 규칙을 고친 뒤에는 check부터
uv run dune-imperium-records check
uv run dune-imperium-problems check
uv run dune-imperium-problems score --agents heuristic,checkpoint:<path>

# A/B 도구(census → 변형 → 축별 셀 → 요약; scripts/ab/README.md)
uv run python scripts/ab/census.py --games 40 --ruleset both --out ab-runs/census.json
uv run python scripts/ab/cells.py --name round1 --variants heuristic_v_space --control heuristic_uniform_ties --axes base,choam --seeds 0,500
uv run python scripts/ab/pair_matrix.py ab-runs/round1 v_space

# 사람 팁 census와 비교 (docs/player-tips-for-training.md 7절)
uv run python scripts/ab/tip_census.py --agents heuristic --games 100 --ruleset choam --bloodlines --tech-module --immortality --promo-cards --out ab-runs/tips/h
uv run python scripts/ab/tip_compare.py ab-runs/tips/h ab-runs/tips/other

# 한 라운드 random 실행 / 대화형 한 라운드
uv run dune-imperium-debug --seed 2 --random-policy-seed 1002
uv run dune-imperium-debug --seed 2

# 카드 그림 중 빠진 것만 받기 (에셋 저장소가 우선; docs/local-images.md)
uv run scripts/fetch_card_images.py

# 공식 PDF와 고정 checksum 재검증; 생성물은 git 무시 tmp/official-rules/
uv run scripts/prepare_official_rules.py
```

sandbox에서 uv cache 쓰기가 막히면 명령 앞에 `UV_CACHE_DIR=tmp/uv-cache`를 붙인다(프로젝트 파일은 저장소 안에 둔다).
