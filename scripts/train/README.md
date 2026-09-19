# 학습 실행 도구 (`scripts/train/`)

M10 학습을 밤새 무인으로 돌리기 위한 스크립트다(2026-09-18, Windows PC WSL에서 첫 사용; 2026-09-19에 macOS로 옮겨
Mac mini에서 검증했다).
모두 표준 라이브러리만 쓰지만 문법은 프로젝트의 Python 3.14 기준이므로 `.venv/bin/python`으로
실행한다(시스템 `python3`가 3.12면 구문 오류가 난다). `ruff`/`mypy` 범위 밖이다. `uv sync --extra rl
--extra train`이 돼 있어야 한다.

| 스크립트 | 무엇을 하나 |
|---|---|
| `run_guard.py` | 명령을 자기 프로세스 그룹에서 띄우고 매초 메모리를 `mem.csv`에 기록한다(Linux는 `/proc`, macOS는 `vm_stat`·`sysctl`·`ps`). 메모리가 바닥나면 그룹 전체를 중단하고(규칙은 아래 "메모리 중단 규칙"), 메인이 끝나면 고아 worker를 정리하며 `guard.log`에 `exit=<code>` 표식과 `mem-summary.json`(최대값)을 남긴다. WSL에서 메모리 초과가 세션째 죽인 전례(handoff 2026-09-17)와 죽은 메인이 남긴 고아 worker(lessons 2026-09-06) 때문에 있다. |
| `train_overnight.py` | `run_guard.py` 아래에서 `dune-imperium-train`을 TOTAL iteration이 `training.jsonl`에 쌓일 때까지 돌린다. 예외로 죽으면 traceback 꼬리를 `crash_<n>.log`에 남기고 `--seed`를 1 올려 `latest.pt`에서 재개한다(같은 seed는 죽은 게임을 그대로 다시 밟는다). 메모리 중단, 수동 중지(`kill -TERM $(cat RUN/supervisor.pid)`), 두 번 연속 무진전, 8회 재시작 뒤에는 멈춘다. `--start-from CKPT`는 첫 시도를 다른 실행의 체크포인트에서 시작한다(새 폴더에서 이어 가는 실험용; `--total`은 이 폴더에 쌓인 iteration 수). `--detach`는 자기 세션을 가진 자식으로 넘어가고 띄운 명령은 바로 돌아온다(`nohup setsid ... &`가 필요 없고, `setsid(1)`이 없는 macOS에서는 이 방법뿐이다). macOS에서는 감독기가 사는 동안 `caffeinate -i -s -w <자기 pid>`를 함께 띄워 잠자기를 막는다 — 이 Mac mini의 `pmset sleep`은 1분이라 없으면 유휴 1분 뒤 실행째 멈춘다. 끝나면 `supervisor.log`에 `supervisor-exit: ...`를 적는다. |
| `watch_run.sh RUN [보고한 iteration] [간격]` | Monitor용 이벤트 스트림. `training.jsonl`(iteration마다 flush; `train.log`는 블록 버퍼링이라 늦다)에서 1번과 간격마다의 iteration을 한 줄로, 한 iteration에 잘린 판이 3개 이상이면 `ALERT`, `train.log`의 Traceback, 감독기의 재시작·종료를 낸다. 종료 표식을 보면 스스로 끝난다. |
| `fmt_iter.py LOG N` | `training.jsonl`의 N번째 기록을 한 줄로. |
| `loop_census.py CKPT ITER GAMES` | 체크포인트로 학습 seed 대역의 표본 self-play를 학습 러너 조건(되돌리기 제외)으로 돌려 가장 긴 게임의 행동 분포와 동일 관측 재방문 비율을 센다. 게임 길이가 늘거나 잘린 판이 나오면 먼저 돌린다. |

## 메모리 중단 규칙

- **Linux**: `MemAvailable`이 바닥(`run_guard.py --min-available-mib`, 기본 1,500; 감독기의 `--floor-mib`, 기본 2,000) 아래로 두 번
  연속 내려가면 중단한다.
- **macOS**: `MemAvailable`이 없다. `mem.csv`의 `available_mib`은 `vm_stat`의 free + file-backed + purgeable 쪽수(압축·스왑 없이
  내줄 수 있는 양)로, 할당을 따라 움직이기는 하지만(1 GiB를 잡는 작업에 1 GiB 내려간다) 어느 수준이 위험인지는 모른다 — 16 GB
  Mac mini는 가용 2.5 GiB·압축 3.8 GiB에서도 커널 압박 수준이 정상(1)인 채 전 확장 iteration을 돌렸다(2026-09-19). 그래서 바닥은
  기본 0(꺼짐)이고, 중단 신호는 커널의 판정 `kern.memorystatus_vm_pressure_level`(1 정상, 2 경고, 4 임계)이다: **임계가 두 번
  연속**이면 중단하고, 경고는 세기만 하며(`mem-summary.json`의 `pressure_warning_samples`), 수준이 바뀔 때마다 `guard.log`에 한 줄
  남는다. `mem.csv`에는 `compressed_mib`·`pressure_level` 두 열이 더 붙는다. `ps`의 RSS는 압축된 쪽을 빼므로 압축기가 바빠지면
  그룹 RSS는 실제보다 작게 나온다. **임계 분기는 실제 기기에서 일으켜 보지 않았다** — 검증한 것은 바닥 규칙으로 밟은 중단 경로
  (그룹 SIGTERM → `exit=-15` → 감독기가 재시작하지 않음), 고아 worker 정리, 정상 종료, 수동 중지다.

## 밤샘 실행 예

Linux(WSL):

```bash
nohup setsid .venv/bin/python scripts/train/train_overnight.py --dir checkpoints/2026-09-18/full-noundo --total 2000 --repo . --floor-mib 2000 -- --games-per-iteration 32 --workers 8 --minibatch 1024 --eval-every 25 --eval-games 20 --checkpoint-every 25 --choam --bloodlines --tech-module --immortality --promo-cards > /dev/null 2>&1 < /dev/null &
```

macOS(다른 실행의 체크포인트에서 새 폴더로 이어 가는 예; `--detach`는 Linux에서도 된다):

```bash
.venv/bin/python scripts/train/train_overnight.py --detach --dir checkpoints/2026-09-19/lr1e-4-mac --total 1000 --repo . --start-from checkpoints/2026-09-18/lr1e-4-long/latest.pt -- --learning-rate 1e-4 --games-per-iteration 32 --workers 4 --minibatch 1024 --eval-every 50 --eval-games 50 --checkpoint-every 25 --choam --bloodlines --tech-module --immortality --promo-cards
```

worker 수는 기기마다 잰다(같은 체크포인트에서 2~5 iteration씩, iteration당 수집 초): Windows PC는 8이 최적(16·24는 더 느림, 약 15초),
Mac mini M4(4P+6E, 16 GB)는 **4**(4·5·6·8·10 worker가 8.8·8.9·9.2·10.8·12.5초 — 적을수록 빠른 원인은 재지 않았다; 갱신은 6.5초로
Windows의 16.8초보다 빠르다). `--device mps`는 같은 배치에서 CPU와 수치가 일치하지만(파라미터 변화량의 상대 차이 1.4e-5) 갱신이 6.6 → 5.6초로
iteration의 5%쯤이라 쓰지 않는다.

실행 폴더에 `provenance.txt`(HEAD, `git status`, 명령)를 손으로 남긴다. 커밋하지 않은 트리로 돌린다면
`git diff > 실행폴더/uncommitted-changes.patch`도 함께 둔다. 진행은 `tail -n 2 RUN/training.jsonl`, 중지는
`kill -TERM $(cat RUN/supervisor.pid)`. 학습 중에는 이 체크아웃에 엔진·학습 코드 변경을 pull하지 않는다
(spawn worker와 지연 import가 작업 트리를 읽는다 — lessons 2026-09-16).

## 자원 스모크

빈 네트워크의 2 iteration은 8시간 실행을 대표하지 않는다(lessons 2026-09-17). 가장 최근 체크포인트에서
`--resume --iterations 2`로 `run_guard.py` 아래에서 돌리고 `mem-summary.json`의 최대값과 게임당 결정 수를 본다.
