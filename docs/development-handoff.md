# 개발 인수인계

기준일: 2026-10-16 (master, 효과 조각 엔진 전환 A2 병합 뒤)

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
| master | composed-a2 병합 (2026-10-16) |
| pytest | 7,747개 통과(에셋을 연결한 체크아웃; 에셋이 없으면 그중 일부가 skip) |
| Ruff · mypy | `src tests` 통과, mypy 509파일. `scripts/`에는 기존 Ruff 오류 68건이 있다(검사 대상 아님) |
| 브라우저 E2E | `scripts/e2e/` 67종(+ 이름으로만 도는 `rehearsal`). 마지막 전체 실행은 2026-10-16 효과 조각 엔진 전환 A1(67 모두 통과) |
| action codec | **v148** (다음 번호 v149) |
| 관측 | v32, 5,093 int (좌석별 덱+숨은 손패 구성, OQ-010 판정 6) |
| action catalog | 기본 4,553 · CHOAM 4,848 · 옵션 전부(CHOAM·프로모·Bloodlines·Tech·Immortality·Epic·Scouts) 36,379 |
| 로컬 서버 기본 AI | 앱 AI 어려움(`app_ai`). 원격 방의 좌석 기본값은 사람 |
| 탐색 AI 망 | Mac mini의 `checkpoints/play/search.pt` → `readapt-v147-4400.pt`(레시피 MLP를 v147에서 재학습, 2026-10-15; 탐색 좌석 1 대 앱 AI 어려움 3에서 81.8%). 되돌리기용 `recipe-mlp-1e5-800.pt`, X `mix-v139-10081.pt` |
| 에셋 저장소 | `c4cf579` (2026-10-12 push) |

## 진행 중·다음 작업

출처는 worklog의 기록 제목(날짜)이다. **(결정)**은 착수 전에 사용자에게 물을 것.

**엔진**

- **효과 조각 엔진 전환(진행 중):** 카드 효과를 능력 기록(공통 조각의 조합)과 실행기로 옮긴다. A단계는 행동·관측·사건을
  그대로 두고 단계마다 `scripts/ab/engine_equivalence.py` 200판 same을 관문으로 한다. 학습은 A단계 끝에 한 번(사용자: 병행
  학습 안 함). 그 앞의 따로 작업 둘(Agent 차례 선택 효과 codec v146, Reveal 선택 효과 codec v147), A0(능력 기록, 행동 모양
  표, 대기 능력 실행기 핵심), A1(책략 선택 frame을 실행기로, codec v148), A2(개인 카드 Agent 칸 44개를 능력 기록으로, codec 그대로)는
  끝났다. **다음은 A3**: Agent 칸의 비용→보상 22개·고르기 14개와 Tread in Darkness, 그리고 A2가 남긴 특이 흐름 7개(Seek Allies, Occupation,
  In High Places, Overthrow, Lisan al Gaib, Guild 영향력 칸, Clandestine Meeting)를 전용 hook 등록부로. 계획서 5절 "A2에서 만든 것".
  같음 확인 기록은 단계 시작 master로 다시 만들고, 속도는 `scripts/ab/time_legal.py`(Agent frame 값 포함)로도 잰다(6절 6번).
  [composed-effects-plan.md](composed-effects-plan.md) [2026-10-16 효과 조각 엔진 전환 A2]

**학습·AI**

- **readapt-v147(끝남) → 플레이 망 교체(2026-10-15):** 레시피 MLP를 v147 엔진에서 3,600 iteration 더 학습한 R(4,400)이
  시작 망과 1,400판에서 +5.6%p [+0.6, +10.4](확정), 탐색 좌석(1 대 앱 AI 어려움 3)에서는 81.8% 대 78.0%, +3.7%p
  [−1.8, +9.2](규칙상 비김, 지표 모두 R 쪽). 사용자 결정으로 `checkpoints/play/search.pt` → `readapt-v147-4400.pt`
  (되돌리기용 `recipe-mlp-1e5-800.pt`). 기록 `checkpoints/2026-10-14/readapt-v147/README.md`.
- **readapt-v147b(끝남, 2026-10-15):** R에서 1,500 iteration 더 학습한 R2(5,900)는 R과 1,400판에서 −0.3%p [−5.1, +4.6]로 비김 →
  플레이 망은 R 유지. 학습 중 평가도 추세 없음: 이 학습률에서 레시피가 정체했다. 다음 학습은 엔진 전환 A단계 끝의 재학습(구조 결정)으로.
  `checkpoints/2026-10-15/readapt-v147b/README.md`. 고정 worktree `train-v147`은 정리했다.
- **개체 기반 망(진행 중):** 망이 카드·칸·행동을 뜻(특성)으로 읽고 행동 점수를 조합으로 계산하게 다시 설계한다. 관측 v31·codec은
  그대로 두고 망만 바꾸며, 기존 망 파일로 플레이하는 길은 유지한다. 평가 도구(AI 실수 문제집, `scripts/ab/network_probes.py`)와
  X·Y·A·B 기준값, P1(`entity` 망), P2(Y 증류, 규칙상 불통과), P3(강화학습), P4 탐색 좌석 측정이 끝났다. 엔티티 E2v@800
  (`checkpoints/2026-10-13/entity-p3/E2v-800.pt`)이 Y를 +5.7%p 넘었지만, **학습률을 맞춘 MLP(Mv-1e5, `checkpoints/2026-10-14/overnight/`)와는
  같다(2026-10-14): 이득은 구조가 아니라 학습 방법(Y 증류 + Y 가치 목표 + PPO 1e-5)이다.** 탐색 좌석 E2v 대 X는 승률 비김, 순위·점수 차는
  E2v. 같은 방법의 MLP(Mv-1e5)도 Y를 +4.9%p(규칙상 비김, 순위·점수 차 확정)로 E2v와 같다. 플레이 서버 망은 같은 방법의 MLP로 바꿨다(2026-10-14). 다시 학습은 효과 조각 엔진 전환
  A단계 끝에 한 번 한다(위 엔진 항목); 구조(엔티티·MLP)는 그때 정한다.
  [entity-network-plan.md](entity-network-plan.md) 10절 [2026-10-13 개체 기반 망 P2·P3]
- **(결정) readapt-v143 판정.** 대조군 C(`C/iteration_11681.pt`)만 돌렸다. 점수 보상 갈래 S(`--score-rewards`)와
  판정 `judge.sh`(G1 S 대 C, G2 C 대 Y, G3 S 대 Y)는 안 돌렸다. C가 Y보다 나은지는 G2만 따로(1,400판, 약 25분)
  돌려도 안다. 판정 전이라 계보의 머리는 Y다. [2026-10-12 readapt-v143]
- **(결정) 다음 학습 후보:** ExIt v2 이어 하기(510판에서 멈춤; 옛 엔진으로 이어 갈지 새 codec으로 다시 할지),
  사람 판 국면의 ExIt 레이블(미룸). 사람 판이 쌓이면 진단을 다시 돌린다.
  [2026-10-09 학습 정리: expert iteration v2, 2026-10-10 사람 문제집·사람이 둔 판]
- **망이 가문 핵 시점을 배우게 하기(멈춤):** 탐색 좌석은 앱 AI 규칙으로 쓴다(`family_atomics="app"`). 토큰은 승률 약
  1.2%p의 값이고 1라운드에 바로 쓰면 그 값을 다 버리지만, 정책에 돌려준 800 iteration(B, `checkpoints/2026-10-13/
  atomics-step2/B/`)에서도 망은 160자리 모두 1라운드에 썼다. 남은 길(결정 대기): 앱 규칙 흉내 가르치기, 또는 탐색이
  게임 끝까지 두어 비교한 답 가르치기. A·B는 Y와 같은 강도의 v145 망이다(계보의 머리는 Y).
  [evaluation/search-atomics-2026-10-12.md](evaluation/search-atomics-2026-10-12.md) 6·7절
- **탐색 AI의 이상한 수 후보:** "이번 턴" 책략(Insider Information)을 쓰고 그 효과가 필요 없는 칸으로 감(책략과
  Agent 턴을 따로 평가하는 탓; 묶어서 평가하기). 값이 거의 같은 수 사이를 세계 8개의 우연이 고르는 것(후퇴 장면;
  상위 두 후보가 잡음 안이면 세계 늘리기). 단독 1등의 전투 책략은 2026-10-13에 고쳤다.
  [evaluation/search-atomics-2026-10-12.md](evaluation/search-atomics-2026-10-12.md) 1·5절
- **엔진 수집 최적화(2026-10-12 병합):** 검사를 유지하는 상태 복사와 앱 AI 고정 메타데이터의 재사용. Mac에서
  학습 설정(Y, 32판, 작업 프로세스 4개) 수집이 8.65초에서 8.08초(−6.6%, 번갈아 9번씩)이고 결과는 비트 단위로 같다.
  셀프플레이 쪽은 거의 줄지 않았다. 다음 후보: Agent 효과 context 재구성(8판에 14만 번), 바뀌지 않은 불변식의
  재검사, 탐색 AI의 `determinize`가 아직 표준 복사를 쓰는 것. `PlayerState.__post_init__`는 검증과 함께
  `hand_public` 정규화도 하므로 비우면 관측이 바뀐다.
  [`evaluation/engine-throughput-2026-10-12.md`](evaluation/engine-throughput-2026-10-12.md)
- 작은 것: heuristic은 Harkonnen Advisor의 배치 못 하는 병력과 Emperor of the Known Universe의 막기를 모르고,
  Plot을 Agent 뒤에 내서 Emperor's Invitation #1·Insider Information #1·Twisted Resourceful을 못 쓴다.
  [2026-10-06 Steam 앱과 카드·보드 전수 대조]

**규칙·엔진**

- **"합법 행동 없음" 결함:** 약 4,000판에 한 판꼴로 나왔고 그 뒤 약 64,000판에서 재현되지 않았다. 다시 나오면
  `stalls/`에 남는 상태로 고친다. [2026-10-06 탐색 AI 좌석·L3 재학습, 2026-10-07 학습: 앱 AI 섞기 대 self-play만]
- Glowglobes·Navigation Chamber의 Tech 획득 아이콘이 여전히 6인 진영을 내놓는다(v137 경계). [2026-10-06 Steam 앱과 카드·보드 전수 대조]
- Ghola + Subversive Advisor의 2+2=4는 project convention이다(`rules/open-questions.md` OQ-022 보강의 남은 의문).

**플레이 화면**

- **미룬 연출:** ③ 카드 사기, ⑤ 동맹 띠·영향력 큐브, ⑦ Conflict 카드가 승자에게, ⑧ 라운드 정리, ⑩ 연출 끄기 설정.
  [2026-10-08 게임다운 연출 4~5단계, [`ui-improvement-plan.md`](ui-improvement-plan.md) 12단계]
- **한국어 화면에 남은 영어(작음):** ⑤⑧⑨는 2026-10-14에 끝났다(OQ 번호·경로·명령 인자는 플레이 화면에서 뺌, 서버 오류는
  `static/errors_ko.js`로 한국어, 런처 창 제목·로그 줄 한국어; 가드 테스트 `tests/server/test_i18n.py`). 남은 것: 런처 설정의
  안내 문구("비우면 checkpoints/play/search.pt", "Tailscale CLI 없음"), macOS 바로가기의 알림 제목 "Dune Imperium 서버"와 앱 이름
  "Dune Imperium Server"(`launcher/shortcuts.py`). ③ "AI"와 ⑥ 도움말 범례의 영어 병기는 사용자 결정으로 그대로 둔다.
  [2026-10-14 남은 영어·테스트 빈자리·선택 불가 표시]
- **(사용자) 한글판 카드 그림:** 한국어 사진이 없는 Uprising 책략 34장과 Bloodlines·Twisted 책략 23장은 한국어
  화면에서도 영어 앞면이다. 사용자가 한글판을 찍어 주기로 했다. [2026-10-07 Steam 앱 그림, 2026-10-11 Bloodlines 책략·Twisted 책략 앞면]
- 화면에 없는 정보: 빚진 Spy 수(관측·뷰에는 있음), Harvest Cells 선택 화면의 Reclaimed Forces specimen 비용(Reveal
  패널에만 있음). [2026-10-04 저녁 앱 방식 재판정 둘째 묶음, 2026-10-06 Steam 앱과 카드·보드 전수 대조]
- 플레이 시계 후속 후보: 접속이 끊긴 동안 멈춤, 수마다 시각(검토 화면에 시계), 저장 목록의 플레이 시간.
  작은 흠: 끼어든 답 뒤 배너의 "이번 차례"가 0에서 다시 시작, 멈춘 동기 AI 동안 시계가 흐름. [2026-10-11 플레이 시계]
- **선택 불가 표시 3단계(옛 C1, 18곳):** 2026-10-14 기준 다 됨 10(1·3·6·8·9·12·13·14·16·17), 일부 6(2·4·5·7·10·11), 없음 2(15·18).
  남은 순서(재대조의 값어치 순): 2 Tech 타일별 이유, 15 Intrigue 선택의 0인·최고치 진영, 7 여러 줄 책략, 그 밖의 긴 꼬리(5 샤담, 11의
  두 가지, 4의 세 가지, 10의 카드별 줄, 14의 Agent 카드·Intrigue·Reveal 진영 선택), 18 배치 비용 변형(설계를 사용자에게 물을 것).
  선택지 제공 코드를 바꾸므로 고위험이다(등가성 테스트 + 독립 리뷰). [`unavailable-options-plan.md`](unavailable-options-plan.md) 머리말.
  사용자 결정(2026-09-30)은 "3단계는 전부 한다"이다.
- 정리 후보: `display/board_layout.py`가 내는 `tracks.garrisons`·`tracks.conflict_quadrants`를 클라이언트가 더 읽지 않는다.

**도구·인프라**

- **서버 런처 7단계:** Windows 실기 검증. [`server-launcher-plan.md`](server-launcher-plan.md)
- **기보 묶음:** codec이 오를 때마다 다시 만든다. 최신 묶음은 v148-02e203ce(2026-10-16, 2,000판; A1의 Play 커밋으로 만듦,
  v147-2af1d9f5와 판마다 수순이 같다)이고 A2 관문의 기준이다. 그 앞은 v147-2af1d9f5(A0·A1 관문), v145-afea63de(v146 다리 대조)이며
  v144·v146 묶음은 없다. v145의 새 다리 `boost_draw_at_turn_end`를 쓰는 장면이 묶음에 있는지는 아직 세지 않았다.
  [2026-10-12 Ghola, 2026-10-14 자기 차례 안의 선택 효과, [`human-records.md`](human-records.md)]
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
| 효과 조각 엔진(전환 중) | 능력 기록 `content/uprising/abilities.py`, 행동 모양 표(동사·출처·대상) `rules/action_shapes.py`, 대기 능력 실행기 `rules/ability_executor.py`; Agent 칸 기록 `content/uprising/agent_abilities.py`와 그 해결 `rules/agent_box_abilities.py`; 계획 [composed-effects-plan.md](composed-effects-plan.md) |
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
작업 프로세스마다 판 묶음 하나를 받는 구조(묶음 수 = 작업 프로세스 수)는 그대로다. 고르게 나눈 뒤 작업 프로세스 수를 다시 쟀다(2026-10-12):
32판 수집이 4개 6.78초, 5개 6.86초, 6개 6.69초, 8개 6.31초, 10개 6.64초(각 9번의 중앙값)이고, 작업 프로세스 메모리는
4개 2.0 GB, 8개 3.9 GB다. 8개가 7% 빠를 뿐이라 학습은 계속 `--workers 4`로 돈다. 작업 프로세스마다 판을 lockstep으로
두어 가장 긴 판이 끝나야 수집이 끝나므로, 작업 프로세스를 늘려도 그 판은 짧아지지 않는다.
엔진 내부의 계측과 상태 복사·앱 AI 메타데이터 개선은
[engine-throughput-2026-10-12](evaluation/engine-throughput-2026-10-12.md)에 있다(WSL·5081 측정과 Mac·Y 확인).

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
