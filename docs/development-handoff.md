# 개발 인수인계

기준일: 2026-10-21 (엔진은 B단계 병합 codec v150 뒤 Reveal 상태 이름 정리로 codec v151; 재학습 (가) 선생 어댑터 병합; 합계 정리(Reveal·Conflict·계약) 끝 — 효과 조각 엔진 전환 끝)

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
4. `uv sync --extra rl --extra ui --extra train` 뒤 `uv run pytest -q -n 8`(pytest-xdist; 직렬은 Mac mini에서 약 10분, 8개로 2분 19초), `uv run ruff check src tests`,
   `uv run mypy src tests`. 결과가 아래 기준선과 다르면 코드가 옳다. 이 문서를 같은 작업에서 고친다.

## 기준선

| 항목 | 값 |
| --- | --- |
| master | B단계 병합 `c133be07` (2026-10-20, 효과 조각 엔진 B단계, codec v150) 뒤 2026-10-21 `codex/windows-validation` 병합 `dbfcb793`·pytest-xdist·`retrain-v150` 병합(옛 codec 망 선생 어댑터)·`reveal-totals` 병합(① Reveal 합계 정리, codec 그대로)·문제집 검사 복구·`reward-totals` 병합(Conflict·계약 합계 정리)·`reveal-line-names` 병합(Reveal 상태 이름, codec v151, `bb05c259`) |
| pytest | 8,198개 통과(에셋을 연결한 체크아웃; 에셋이 없으면 그중 일부가 skip). `-n 8` 2분 23초, 직렬 약 10분(Mac mini, 2026-10-21) |
| Ruff · mypy | `src tests` 통과, mypy 553파일. `scripts/`에는 기존 Ruff 오류가 있다(검사 대상 아님) |
| 브라우저 E2E | `scripts/e2e/` 68종(+ 이름으로만 도는 `rehearsal`). 마지막 전체 실행은 2026-10-21 `reveal-line-names` 브랜치(68종 모두 통과, 427초) |
| action codec | **v151** (다음 번호 v152). v151은 상태 이름만 바꿨고 행동 줄은 v150과 같다(망·증류 자료·체크포인트 그대로) |
| 관측 | v33, 5,732 int (B단계: 고른 카드·효과·대상 칸 추가) |
| action catalog | 기본 1,434 · CHOAM 1,555 · 옵션 전부(CHOAM·프로모·Bloodlines·Tech·Immortality·Epic·Scouts) 4,311 |
| 엔티티 망 특성 | `FEATURE_VERSION` 2(능력 기록에서, 행동은 `ACTION_SHAPES` 부분), 지문 `0098fbb6…`; 특성 표가 바뀌어도 파일을 이름으로 옮긴다 |
| 로컬 서버 기본 AI | 앱 AI 어려움(`app_ai`). 원격 방의 좌석 기본값은 사람 |
| 탐색 AI 망 | Mac mini의 `checkpoints/play/search.pt` → `readapt-v147-4400.pt`(레시피 MLP를 v147에서 재학습, 2026-10-15; 탐색 좌석 1 대 앱 AI 어려움 3에서 81.8%). **v150 이후(지금 v151)에는 4,311줄 가운데 84줄만 학습한 줄**(나머지 결정은 휴리스틱으로) — v150을 플레이 서버에 올리기 전에 재학습. 되돌리기용 `recipe-mlp-1e5-800.pt`, X `mix-v139-10081.pt` |
| 에셋 저장소 | `c4cf579` (2026-10-12 push) |

## 기기 분담 (사용자 결정 2026-10-21)

재학습은 Mac mini에서 작업하고 돌린다. 그 밖의 작업은 Mac mini의 CPU 부하에 영향을 주지 않도록 다른 PC에서 한다. 단 ① Reveal 합계
정리는 관문이 Mac mini에만 있는 git 밖 자료를 읽으므로 Mac mini에서 한다(사용자 결정 2026-10-21 둘째: "자료를 옮겨야 다른 pc에서 가능한거면
그냥 이 mac mini에서"). ②의 다음 학습은 아직 띄우지 않는다(같은 날 사용자). ①은 같은 날 끝났다(아래 "엔진").

| 기기 | 맡는 일 |
| --- | --- |
| Mac mini (`CS-Mac-mini`, 10코어·16 GB) | ② 재학습과 그 측정, 플레이 서버, git 밖 자료(아래)를 읽는 엔진 관문. 학습은 시작 커밋에 고정한 worktree에서 돌리고 메인 체크아웃은 master에 둔다. 학습이 도는 동안 이 기기에서는 ②와 상관없는 무거운 검사(전체 pytest·E2E·소크)를 돌리지 않는다 |
| 다른 PC (Windows 11 Pro + WSL2) | Godot 클라이언트(아래 "플레이 화면"), 서버 런처 7단계의 남은 Windows 확인, 그 밖의 엔진·화면 작업. 엔진 관문은 WSL 체크아웃에서 돌린다(2026-10-12 WSL 전체 pytest 통과) |

- **엔진 관문이 읽는 git 밖 자료**(Mac mini에 있다): `local/records-corpus/v151-bb05c259/`(기보 묶음, exact 2,000의 기준),
  `local/records/`(사람 판 문제 285곳·AI 실수), `saves/`(사람 저장본), `checkpoints/2026-09-22/exploit/champion-5081.pt`(문제집 tips-v1
  재채굴의 망 몫). 다른 기기에서 관문을 돌리려면 이것을 옮긴다(`tmp/transfer/gate-data-2026-10-21.tar.gz`에 2026-10-21판을 묶어 두었다).
- **②의 망을 플레이 서버에 올릴 때:** 새 이름으로 `checkpoints/play/`에 복사하고 `search.pt` 링크만 바꾼 뒤 서버를 다시 띄운다(아래
  "원격 저장소 인계 주의").

## 진행 중·다음 작업

출처는 worklog의 기록 제목(날짜)이다. **(결정)**은 착수 전에 사용자에게 물을 것.

**엔진**

- **효과 조각 엔진 전환 — B단계 끝(codec v150, 2026-10-20 병합 `c133be07`, 2026-10-21 원격 반영):** Agent 차례는 카드 → 칸, 보상·계약은 아이콘마다,
  기다리는 효과는 효과 줄 → 대상 줄, 효과는 인쇄한 것마다 한 줄, Reveal은 능력 기록을 직접 읽는다. 옛 저장본은 못 불러오고 옛 기보는 v150
  다리로 옮긴다. 세부는 [stage-b-plan.md](stage-b-plan.md) 3a~3c절. **다음 둘(사용자 결정 2026-10-21):** ① Reveal 합계 정리 —
  끝(아래), ② 재학습 (가) — 선생 어댑터와 첫 사슬은 끝났고(아래) 다음 학습은 사용자가 정할 때 띄운다. [2026-10-20 효과 조각 엔진 B단계 병합(codec v150)]
- **① Reveal 합계 정리 끝(2026-10-21, codec 그대로 v150):** 카드 문구(영·한)와 codec도 Reveal 능력 기록 줄(`rules.reveal_lines`)을 읽고,
  합계 자료형 `PersonalCardRevealEffect`와 manifest의 `reveal_effects` 칸(51곳)이 없어졌다. 합계가 하던 기록 검사는
  `content/uprising/reveal_abilities.check_reveal_gain_line`이 import 때 모든 기록에 돈다. 카드 140장 문구·브라우저 카드 표 전체·codec 144개 조합의
  행 목록·`FEATURE_DIGEST`가 바이트까지 같다. [2026-10-21 ① Reveal 합계 정리]
- **Conflict·계약 합계 정리 끝(2026-10-21, codec 그대로 v150):** Conflict 정의는 보상 기록 행(`reward_rows`), 계약 정의는 자기 기록(`terms`)을
  그대로 들고, 규칙·codec·화면 문구·app 스크립트가 그 기록을 읽는다(계약은 `requirement`·`reward_line`·`board_space`·`harvest_spice`·
  `acquire_card`·`earns_alliance`, Conflict는 `control_space_id`; 문구는 `display/structs.conflict_row_parts`·`contract_reward_parts`). 기록에서 만든
  사본 `ConflictReward`·`ContractCondition`·`ContractReward`와 `ContractConditionKind`가 없어졌고, 검사는 `check_conflict_reward_row`·
  `check_contract_terms`가 한다. 브라우저 카드 표 전체·codec 144개 조합·`FEATURE_DIGEST`·app 스크립트 기록이 바이트까지 같다. 이로써 효과 조각
  엔진 전환 계획([composed-effects-plan.md](composed-effects-plan.md))의 B단계 "함께 할 일"(합계 대신 기록 조각)까지 끝났다; 남은 것은 C단계(새
  콘텐츠)와 ② 재학습. [2026-10-21 Conflict·계약 합계 정리]
- **Reveal 상태 이름 정리 끝(2026-10-21, codec v151):** 합계 정리 뒤 게임 상태에 남은 옛 이름 셋이 코드의 "Reveal 기록 줄"을 따른다 —
  Reveal frame의 `granted_reveal_lines`, 사건 `reveal_line_granted_late`와 그 `line_index`. 행동 줄은 그대로이고 상태 해시만 바뀌어 codec
  번호만 올렸다(계획 6절 3번). [2026-10-21 Reveal 상태 이름 정리]
- **문제집 검사(2026-10-21 복구):** `dune-imperium-records problems check`가 사람 판 문제집 285곳 가운데 279곳(v149와 같음, 원래부터 안 풀리는
  6곳: 대응 없는 사람의 거절 2·옛 엔진의 거절인 망의 수 4), AI 실수 문제집 3곳 모두를 푼다. B단계 이후 멈추던 두 원인은
  [2026-10-21 문제집 검사 복구]에.
- **② 재학습 (가) — 선생 어댑터 병합, 첫 사슬의 망은 선생보다 약함(2026-10-21):** 플레이 망 `checkpoints/play/readapt-v147-4400.pt`(MLP,
  v147)를 v150에서 쓰는 어댑터 `training/older_teacher.py`: 결정마다 휴리스틱이 보는 온 행동(`agents.agent_turn_steps.placements_for_steps`:
  카드+칸 `agent_turn`, 효과+대상, 옛 엔진의 고르기)에 파일의 v147 행 번호를 붙여(그대로 → `printed` 떼고 → `source`도 떼고) 파일 자신의 정책
  머리로 점수를 매기고, softmax를 각 온 행동의 지금 줄로 모은다. 옛 엔진이 묻지 않던 결정(B2 아이콘 순서)은 그 고정 답, 번호가 하나도 안 붙으면
  휴리스틱. 대회 좌석 `older:<path>`(탐욕, 같은 관측에서 같은 수 반복 금지 — 없으면 Scouts 입찰을 끝없이 다시 함; 플레이 서버 좌석은 아님),
  증류 데이터 `distill_entity.py data --older`(`training/older_distill.py`), 학생 학습률 `--schedule cosine`.
  - **될지 확인(통과):** 1 대 앱 AI 어려움 3, 1,000판씩, 옵션 전부+드래프트: 옛 망 v149(`52d0a6cc`) 54.7%, 어댑터 v150 54.8%, 같은 시드
    **996/1,000판이 최종 VP·순위까지 같다**. 번호가 붙는 결정 94.7%, 옛 엔진 고정 답 4.8%, 휴리스틱 0.5%.
  - **첫 사슬**(`checkpoints/2026-10-21/retrain-v150/`, `chain.sh`·`README.md`): 데이터 80 iteration 2,599,119행 17분 → 엔티티 학생 4 epoch(일치
    87.5%, A8 95.2%) → PPO 1e-5 800회 3.6시간 → 예비 비교 **B-800 대 어댑터 선생 −7.0%p [−12.1, −1.7] 확정** → 설치 안 함. 같은 400판 단독
    승률: 선생 56.8%, 선생 분포를 줄마다 탐욕("완벽한 학생") 57.5%, 학생 4 epoch 47.5%, 학생 cosine 12 epoch(`student12`) 52.0%, PPO 300·600·800
    52.2%·49.0%·51.5%. 실력은 증류에서 샌다: 선생이 확신하는 수(최고 확률 > 0.9)는 99.2% 따라 하지만 선생도 갈린 수(< 0.6, 32%)에서 21%를
    다르게 고른다.
  - **(결정) 다음:** (1) 탐색 좌석이 어댑터로 옛 망을 쓰게 하기(망 단독은 이미 옛 실력; `NetworkSearchAgent`는 v150 행으로 망을 부르니 설계 필요),
    (2) `student12`에서 PPO 다시(`chain2.sh` 준비됨, 약 3.5시간), (3) 증류 키우기(데이터 2배·엔티티 폭·PPO 3e-5). 고정 worktree
    `.claude/worktrees/retrain-v150`(`chain2.sh`가 이 경로를 쓴다)과 탐색 좌석 관문 대조용 `.claude/worktrees/v149-ref`(`52d0a6cc`)를 남겼다.
- **플레이 서버 주의:** Mac mini의 메인 체크아웃은 이미 v150 이후다(B단계 병합을 이 기기에서 했다; 지금 v151). 그래서 지금 서버를 다시 띄우면
  ②의 망을 `checkpoints/play/search.pt`에 설치하기 전까지 탐색 AI 좌석이 약하다(앱 AI·휴리스틱 좌석은 그대로). 그 사이 강한 탐색
  좌석이 필요하면 B단계 직전 커밋 `52d0a6cc`(v149)의 worktree에서 서버를 띄운다(그 판의 저장본은 v150 이후에서 열리지 않는다).

**학습·AI**

- **readapt-v147(끝남) → 플레이 망 교체(2026-10-15):** 레시피 MLP를 v147 엔진에서 3,600 iteration 더 학습한 R(4,400)이
  시작 망과 1,400판에서 +5.6%p [+0.6, +10.4](확정), 탐색 좌석(1 대 앱 AI 어려움 3)에서는 81.8% 대 78.0%, +3.7%p
  [−1.8, +9.2](규칙상 비김, 지표 모두 R 쪽). 사용자 결정으로 `checkpoints/play/search.pt` → `readapt-v147-4400.pt`
  (되돌리기용 `recipe-mlp-1e5-800.pt`). 기록 `checkpoints/2026-10-14/readapt-v147/README.md`.
- **readapt-v147b(끝남, 2026-10-15):** R에서 1,500 iteration 더 학습한 R2(5,900)는 R과 1,400판에서 −0.3%p [−5.1, +4.6]로 비김 →
  플레이 망은 R 유지. 학습 중 평가도 추세 없음: 이 학습률에서 레시피가 정체했다. 다음 학습은 엔진 전환 A단계 끝의 재학습(구조 결정)으로.
  `checkpoints/2026-10-15/readapt-v147b/README.md`. 고정 worktree `train-v147`은 정리했다.
- **개체 기반 망 — 계보는 엔티티(사용자 결정 2026-10-18), 재학습은 위 엔진 ②(방법 (가) 결정 2026-10-21):** A8 입력(능력 기록 특성, 행동 부분, 이름 기준 파일
  옮기기)을 넣고 한 번 학습했다: 선생 = 플레이 망, 증류 197만 행 → 학생(일치 95.2%) → PPO 1e-5 800회(학습 중 평가 약 53%) → 예비
  비교 700판: 플레이 MLP와 비김(승률 +1.3%p [−3.9, +6.4]). 탐색 좌석 관문은 사용자 결정으로 건너뛰었다(B단계 뒤 다시 학습) — 플레이 서버 망은 MLP 그대로. 고정 worktree
  `a8-train`은 정리했고 기록은 `checkpoints/2026-10-19/a8/`(`chain.sh`가 사슬). 이전 기록: 엔티티와 같은 학습 방법의 MLP는 실력이 같다(2026-10-14),
  `docs/entity-network-plan.md` 10절.
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

- **Godot PC 클라이언트(다른 PC; 브랜치 `docs/godot-client-plan`에만 두고 master에는 넣지 않음, 사용자 결정):** 2026-10-18에 v148
  위로 리베이스한 커밋 48개라 B단계(v150) 병합보다 앞이다(2026-10-21 master보다 264커밋 뒤). 먼저 v150에 맞춰야 한다. 클라이언트(`main.gd`·`model.gd`·
  `playthrough.gd`)가 옛 한 걸음 Agent 행 `agent_turn`을 20곳에서 읽는데, v150의 Agent 차례는 `choose_agent_card` → `place_agent` 두
  걸음이다. 기다리는 효과도 효과 줄 → 대상 줄로 바뀌었다(B3). master와 같이 고친 파일은 인수인계·worklog 둘뿐이다(2026-10-21 시험
  병합). 계획과 상태는 그 브랜치의 `docs/godot-client-plan.md`와 인수인계에 있다.
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

- **프로젝트 웹사이트:** `website/`의 Hugo 0.168.0 사이트를 Pages에 공개했다(master `b7787979`, build·deploy와 공개 URL 확인).
  담백한 문구를 사용하고, 커밋·문서를 묶은 과거 개발일지 16편과 월별 목록·앞뒤 글·검색·RSS를 추가했다(master `89a96258` 반영).
  한국어 기본 URL·영어 `/en/`, 본문 36개 번역(개발일지 16편 포함)·언어별 검색/RSS·다크/라이트와 자체 샌드웜 SVG를 추가했다.
  테마는 시스템 기본값과 수동 선택 저장·탭 동기화를 지원한다. 이번 변경은 로컬 검증·커밋 후 원격 반영 대기.
  작성 양식·검증·배포는 [`website/README.md`](../website/README.md), 문구 원칙은 `website/AGENTS.md`.
  **다음:** 작업별 개발일지 이어 쓰기, 게임 설치·OS 실기 확인과 릴리스·선택 모델 준비.
  [project-site-plan.md](project-site-plan.md)
- **서버 런처 7단계:** Windows 11 기능 검증 완료(2026-10-12 v145, 실제 Tk 시작·중지, Chrome E2E 174개; 브랜치
  `codex/windows-validation`, 2026-10-21 master 병합). 다른 물리 PC의 접속, 배율·IME·방화벽·GUI 강제 종료·잠자기 복귀,
  학습한 탐색 AI 망 사용 확인이 남았다. Windows 전체 엔진 pytest와 `run_all.py` 전체는 Windows에서 돌린 적 없다(POSIX
  전용 경로가 남은 E2E가 있다). [`windows-host-validation.md`](windows-host-validation.md), [`server-launcher-plan.md`](server-launcher-plan.md)
- **기보 묶음:** codec이 오를 때마다 다시 만든다. 최신 묶음은 **v151-bb05c259**(2026-10-21, 2,000판, Reveal 상태 이름 정리 병합 master에서
  만듦; 같은 엔진으로 되돌려 exact 2,000)이고 다음 엔진 변경의 기준이다. 그 앞은 v150-14c08062(v151 엔진에서도 exact 2,000 — 상태 비교가
  결정 단계와 사건 기록을 빼므로), v149-86086c6d(B단계 관문의 기준, v150 다리로 1,568 · 431 · 1),
  v148-02e203ce, v147-2af1d9f5, v145-afea63de이며 v144·v146 묶음은 없다.
  [2026-10-20 효과 조각 엔진 B단계 병합(codec v150), [`human-records.md`](human-records.md)]
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
- 원격의 `docs/godot-client-plan`은 다른 PC에서 하는 Godot 작업 브랜치다(위 "플레이 화면", master에 넣지 않음).
  `codex/windows-validation`은 2026-10-21에 master에 병합했다.

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
