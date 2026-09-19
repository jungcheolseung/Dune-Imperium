# 학습 실행 도구 (`scripts/train/`)

M10 학습을 밤새 무인으로 돌리기 위한 스크립트다(2026-09-18, Windows PC WSL에서 첫 사용).
모두 표준 라이브러리만 쓰지만 문법은 프로젝트의 Python 3.14 기준이므로 `.venv/bin/python`으로
실행한다(시스템 `python3`가 3.12면 구문 오류가 난다). **`run_guard.py`는 `/proc/meminfo`와 `/proc/<pid>`를 읽으므로 Linux 전용이다** — macOS에서는
가용 메모리(`vm_stat`)와 프로세스 그룹 RSS(`ps`) 부분을 옮겨 그 기기에서 검증한 뒤 쓴다. `ruff`/`mypy` 범위 밖이다. `uv sync --extra rl
--extra train`이 돼 있어야 한다.

| 스크립트 | 무엇을 하나 |
|---|---|
| `run_guard.py` | 명령을 자기 프로세스 그룹에서 띄우고 매초 `/proc`을 `mem.csv`에 기록한다. 가용 메모리가 바닥(`--min-available-mib`, 기본 1,500) 아래로 두 번 연속 내려가면 그룹 전체를 중단하고, 메인이 끝나면 고아 worker를 정리하며 `guard.log`에 `exit=<code>` 표식과 `mem-summary.json`(최대값)을 남긴다. WSL에서 메모리 초과가 세션째 죽인 전례(handoff 2026-09-17)와 죽은 메인이 남긴 고아 worker(lessons 2026-09-06) 때문에 있다. |
| `train_overnight.py` | `run_guard.py` 아래에서 `dune-imperium-train`을 TOTAL iteration이 `training.jsonl`에 쌓일 때까지 돌린다. 예외로 죽으면 traceback 꼬리를 `crash_<n>.log`에 남기고 `--seed`를 1 올려 `latest.pt`에서 재개한다(같은 seed는 죽은 게임을 그대로 다시 밟는다). 메모리 중단, 수동 중지(`kill -TERM $(cat RUN/supervisor.pid)`), 두 번 연속 무진전, 8회 재시작 뒤에는 멈춘다. `--start-from CKPT`는 첫 시도를 다른 실행의 체크포인트에서 시작한다(새 폴더에서 이어 가는 실험용; `--total`은 이 폴더에 쌓인 iteration 수). 끝나면 `supervisor.log`에 `supervisor-exit: ...`를 적는다. |
| `watch_run.sh RUN [보고한 iteration] [간격]` | Monitor용 이벤트 스트림. `training.jsonl`(iteration마다 flush; `train.log`는 블록 버퍼링이라 늦다)에서 1번과 간격마다의 iteration을 한 줄로, 한 iteration에 잘린 판이 3개 이상이면 `ALERT`, `train.log`의 Traceback, 감독기의 재시작·종료를 낸다. 종료 표식을 보면 스스로 끝난다. |
| `fmt_iter.py LOG N` | `training.jsonl`의 N번째 기록을 한 줄로. |
| `loop_census.py CKPT ITER GAMES` | 체크포인트로 학습 seed 대역의 표본 self-play를 학습 러너 조건(되돌리기 제외)으로 돌려 가장 긴 게임의 행동 분포와 동일 관측 재방문 비율을 센다. 게임 길이가 늘거나 잘린 판이 나오면 먼저 돌린다. |

## 밤샘 실행 예

```bash
nohup setsid .venv/bin/python scripts/train/train_overnight.py --dir checkpoints/2026-09-18/full-noundo --total 2000 --repo . --floor-mib 2000 -- --games-per-iteration 32 --workers 8 --minibatch 1024 --eval-every 25 --eval-games 20 --checkpoint-every 25 --choam --bloodlines --tech-module --immortality --promo-cards > /dev/null 2>&1 < /dev/null &
```

실행 폴더에 `provenance.txt`(HEAD, `git status`, 명령)를 손으로 남긴다. 커밋하지 않은 트리로 돌린다면
`git diff > 실행폴더/uncommitted-changes.patch`도 함께 둔다. 진행은 `tail -n 2 RUN/training.jsonl`, 중지는
`kill -TERM $(cat RUN/supervisor.pid)`. 학습 중에는 이 체크아웃에 엔진·학습 코드 변경을 pull하지 않는다
(spawn worker와 지연 import가 작업 트리를 읽는다 — lessons 2026-09-16).

## 자원 스모크

빈 네트워크의 2 iteration은 8시간 실행을 대표하지 않는다(lessons 2026-09-17). 가장 최근 체크포인트에서
`--resume --iterations 2`로 `run_guard.py` 아래에서 돌리고 `mem-summary.json`의 최대값과 게임당 결정 수를 본다.
