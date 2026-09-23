# A/B·프로파일 도구 (`scripts/ab/`)

heuristic·rollout 변경을 측정으로 채택하는 데 쓰는 스크립트다. 저장소 어느 체크아웃에서든
`uv run python scripts/ab/<도구>`로 돌아가고, 출력은 기본으로 저장소 루트의 git 무시 폴더
`ab-runs/`에 쓴다. 절차와 근거는 [`docs/evaluation/baseline-2026-09-16.md`](../../docs/evaluation/baseline-2026-09-16.md)
14~15절과 [`docs/lessons.md`](../../docs/lessons.md)에 있다.

## 절차

1. **census** — 순위를 손보기 전에 그 순위가 갈리는 결정이 얼마나 자주 오는지 잰다.
   `uv run python scripts/ab/census.py --games 40 --ruleset both --out ab-runs/census.json`
   (동점 가족과 "이긴 가족 | 차점 가족 | 간격"을 게임당 빈도로 출력).
2. **변형** — `pypath/hvariants.py`에 `HeuristicAgent`/`RolloutAgent` 서브클래스를 적는다.
   `prefer(top, view)`는 점수가 고정한 동점 집합 **안에서만** 좁히고(점수에 항을 더하지 않는다,
   `docs/lessons.md` 2026-09-10), `adjust(action, score, view)`는 점수를 바꾼다. `VARIANTS` /
   `ROLLOUT_VARIANTS`에 registry 이름으로 등록하면 `pypath/sitecustomize.py`가 worker마다 얹는다.
3. **sanity** — `uv run python scripts/ab/sanity.py [--rollout]`: null 변형이 커밋된 agent와
   결정까지 같고, 모든 변형이 전 룰셋에서 완주하고, 훅이 실제로 발동하는지 본다.
4. **셀** — 대조군은 **registry에 고정된 이름**(`heuristic_uniform_ties`, `heuristic_untuned`,
   `rollout_count_max` 등)으로 지정한다. 현행 `heuristic`을 대조군으로 쓰면 셀이 도는 중에 작업
   트리를 고쳤을 때 대조군이 함께 바뀐다(2026-09-16 사고). 셀이 도는 동안 `src/`를 편집하지 않는다.
   ```bash
   uv run python scripts/ab/cells.py --name round1 --variants heuristic_v_space,heuristic_v_spy \
       --control heuristic_uniform_ties \
       --axes base,choam,bloodlines,immortality,tech_nochoam,tech_choam,stack_cti --seeds 0,500 --games 500
   uv run python scripts/ab/pair_matrix.py ab-runs/round1 v_space,v_spy
   ```
   룰셋 축은 **하나씩** 잰다(조합 하나의 ≈0은 "효과 없음"과 "상쇄"를 구분 못 한다). 셀 하나(2:2 미러
   500 seed = 1,000 match)는 M4 10코어에서 약 30초, WSL2 8코어에서 약 3.5분. 둘째 seed 블록(`--seeds
   0,500`)까지 이긴 것만 채택한다. rollout은 미러가 느리므로 `--lineup single`(변형 1 + 대조군 3, 50 seed
   × 4 회전 = 200판, 표준오차 약 3.5%p, 셀당 6~8분)로 잰 뒤 `rollout_table.py`로 요약한다.
5. **probe** — 채택 전에 `probe_mix.py --agents heuristic_uniform_ties,heuristic_v_x`로 배치 mix·종료
   자산·Conflict 승을 적어 기제를 확인한다(상관은 개입으로 확정, `docs/lessons.md` 2026-09-11).
6. **채택** — 저장소 agent로 옮기고 이전 동작을 registry 변형으로 **고정**한다(고정 표는 바뀌는 칸을
   전부 명시). 옮긴 것이 스크래치 변형과 결정까지 같은지 `sanity.py`류로 확인하고, `soak.sh`(12,000판
   실패 0)와 `baseline_cells.sh`(12셀)를 다시 돌려 문서의 수치를 갱신한다. A/B 실행의 "N failed"는
   엔진 결함 신호다 — 반드시 읽고 재현한다.

## 도구

| 파일 | 용도 |
| --- | --- |
| `census.py` | heuristic 미러의 legal 집합 전수 채점: 동점 가족·결정 가족 빈도 |
| `pypath/hvariants.py`, `pypath/sitecustomize.py` | 스크래치 변형과 registry 등록 (`PYTHONPATH=scripts/ab/pypath`) |
| `sanity.py` | null 변형 = 커밋 agent, 완주, 훅 발동 확인 |
| `cells.py` | 축별·seed 블록별 셀 실행기(HEAD·dirty 기록, `ALL_DONE` 센티널) |
| `pair_matrix.py` / `rollout_table.py` | 미러 라운드 / 단일 좌석 라운드 요약 표 |
| `paired.py` | 대회의 `--matches` 행으로 두 에이전트를 **짝지어** 비교(승률·평균 순위·VP 마진, seed 군집 부트스트랩 CI) |
| `probe_mix.py` | 배치 분포·종료 자산·Conflict 승 probe |
| `tip_census.py`, `tipcensus/` | 사람 팁 가설용 좌석별 통계(덱·전투·영향력·Landsraad·Spy·끝내기·Bloodlines/Tech·Bond). 대회와 같은 게임, 판마다 JSONL + 종류별·승자 평균표; 어떤 registry 종류든(`checkpoint:` 포함) 돈다 — [`docs/player-tips-for-training.md`](../../docs/player-tips-for-training.md) 7절 |
| `tip_compare.py` | census 출력 둘(또는 `dir::kind`로 한 표의 두 종류, `--split-winners`로 승자 대 나머지)을 열마다 비교: 평균과 seed 군집 부트스트랩 95% 구간 |
| `profile_run.py`, `profile_legal.py`, `profile_guards.py` | 대회 경로 cProfile(전체 / legal·관측 / handler guard 비용) |
| `profile_selfplay.py` | M10 수집 경로(`SelfPlayRunner`) cProfile |
| `soak.sh`, `soak_summary.py` | 전 룰셋 검증 소크와 census 요약 |
| `baseline_cells.sh`, `summarize_cells.py` | 기준선 12셀 재측정과 요약 행 |

처리량 측정은 CPU 경합에 면역인 지표(cProfile 호출 횟수, step 수)를 먼저 잡고, 시간은 조용한 기계에서
옛/새를 한 실행 안에서 번갈아 잰다(`docs/evaluation/throughput-2026-09-10.md` 2절).

두 에이전트의 차이를 판정할 때는 요약표의 두 승률을 빼지 말고 `--matches`가 쓴 경기별 행에
`paired.py`를 돌린다. 한 seed의 회전들은 같은 Leader·덱·선공을 쓰는 같은 게임이므로 한 군집이고,
독립 표본으로 세면 구간이 실제보다 좁아진다. **VP 마진과 평균 순위는 승률보다 같은 판 수에서 더
작은 차이를 가른다** — 2026-09-20 실측: 2:2 미러 60경기에서 VP 마진은 +0.644 [+0.122, +1.189]로
갈렸고 같은 경기의 승률은 +13.3%p [-10.0, +36.7]로 잡음 안이었다.
