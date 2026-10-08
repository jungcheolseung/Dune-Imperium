# 플레이 서버 런처(GUI) 계획

기준일: 2026-10-08 계획(master `717f88be` 기준 코드 위치), 2026-10-09 1~6단계 구현(브랜치 `claude/server-gui-plan-aca18e`). 이 문서는 다른 세션에서 이어 작업하기 위한 인계서다. **남은 것은 7단계(Windows 네이티브 실기 검증)뿐이다.** 구현하면서 계획과 달라진 점은 13절에 모았다(아래 5절 본문은 계획 당시 그대로이고, 다른 곳은 13절이 우선한다). 조사 원자료(설계안 5건, 사실 검증 5묶음, 심사 3건, 초안 리뷰 4건과 반박 15건, 1·2단계 독립 리뷰)는 세션의 `tmp/claude/<세션>/panel/`에 남겼다(git 무시).

## 1. 목적과 원칙

사용자 요청(2026-10-08): "지금 서버를 킬 때 터미널에서 명령어로 실행해야 하잖아. 이거 좀 불편해서 GUI가 있으면 좋겠어. 일단 지금 환경은 Mac인데 Windows에서도 실행 가능하면 좋을 듯."

지금은 저장소 루트에서 `uv run dune-imperium-server --remote --host <주소> --public-url http://<주소>:8000 …`을 치고, 콘솔에 찍힌 관리자 링크를 복사해 브라우저에 붙이고, 끝나면 `Ctrl+C`로 끈다([호스트 가이드](remote-play-host-guide.md) 3~6절). 런처는 이 동작(옵션 고르기 → 띄우기 → 링크 얻기 → 끄기)을 창 하나로 바꾼다.

원칙:

1. **서버는 그대로 별도 프로세스다.** 런처는 `dune_imperium.cli.server`를 자식으로 띄우는 감독자일 뿐이고, 엔진·codec·관측·저장 형식·HTTP API는 건드리지 않는다. 서버 CLI 변경은 5.3절의 둘뿐이며 모두 옵트인이라 터미널 사용자에게는 아무 영향이 없다.
2. **새 런타임 의존성 0.** GUI는 표준 라이브러리 tkinter/ttk(uv가 받는 python-build-standalone 3.14.6에 macOS·Windows 모두 포함, 4절). 무거운 GUI 프레임워크를 들일 근거가 없다.
3. **프로젝트 파일은 프로젝트 폴더 안에**(사용자 결정 2026-10-06). 설정은 git 무시 `local/launcher.json`, 로그·pid는 `tmp/launcher/`, 더블클릭 산출물(.app/.lnk)도 저장소 폴더 안에 만든다. 홈 디렉터리·바탕화면에는 아무것도 쓰지 않는다. 런처는 체크아웃마다 하나다(`paths.PROJECT_ROOT`가 체크아웃별이라 worktree에서 띄우면 그 worktree의 `saves/`·`checkpoints/`·`assets`를 쓴다 — 기존 설계).
4. **GUI 아닌 모든 논리는 GUI 밖에 둔다.** 설정·명령 조립·주소 후보·프로세스 감독·오류 문구·상태→뷰 모델은 순수 모듈이라 디스플레이 없이 pytest로 돈다. tkinter 창은 그것을 그리기만 한다.
5. **종료는 한 길.** [중지]와 창 닫기는 양 OS에서 "서버의 stdin이 닫힌다"로 수렴한다(서버 플래그 `--exit-when-stdin-closes`). 런처 crash는 macOS에서만 같은 길(파이프 EOF → 정상 종료)이고, Windows에서는 Job Object가 런처 핸들과 함께 닫히며 서버를 즉시 끝낸다(정상 종료 아님; 자동 저장이 원자적이라 안전, 4절). 시그널은 예비, 하드 킬은 최후 백스톱.
6. **오류는 사람 말로.** 의존성 누락, 포트 사용 중, Tailscale 꺼짐, torch 없음, 방화벽 차단을 런처가 먼저 알아내거나 로그 꼬리를 번역해 보여 준다.
7. **숨은 정보 규칙 유지.** 서버는 체크포인트 경로를 어떤 클라이언트에게도 내보내지 않는다(`app.py` `/whoami` 주석 "never the path", `test_remote_app.py`). 런처가 필요한 정보는 자기가 넘긴 설정과 서버의 기존 순수 함수에서 얻는다.
8. **Windows 네이티브는 미검증이 현재 상태다**(호스트 가이드 1절). Windows 실기 검증 단계(7단계)를 필수로 넣고, 그 결과로 가이드 문구를 바꾼다. WSL2는 범위 밖(창이 안 뜨고 NAT 뒤).

## 2. 결론: 어떤 형태인가

```
[런처 프로세스]  macOS: .venv/bin/python(실제 인터프리터로 가는 링크)   Windows: dune-imperium-launcher.exe(gui 트램펄린) → .venv\Scripts\pythonw.exe(리디렉터) → 기반 pythonw(추정, 7단계에서 사슬 기록)
   tkinter 창 — 메인 스레드만 위젯을 만진다
   ├─ 스레드: 자식 stdout 리더 → queue → root.after() 폴링 → 로그 창 + tmp/launcher/server-<시각>.log
   ├─ 스레드: 준비 확인 폴러 (GET /whoami) → "켜짐" / 실패 문구
   ├─ 스레드: 조회·사전 검사 워커(주소 후보, Tailscale CLI, PowerShell, import torch 검사) → queue → root.after()
   ├─ 자식(macOS): .venv/bin/python -u -m dune_imperium.cli.server --exit-when-stdin-closes --host … --port …   (단일 프로세스)
   ├─ 자식(Windows): .venv\Scripts\python.exe = 리디렉터(Popen pid) → 기반 python.exe(uvicorn이 실제로 listen; 리디렉터의 Job에 묶여 함께 죽는다)
   │        stdin=PIPE: 런처가 쓰기 끝을 쥔다 → 닫으면 서버가 스스로 정상 종료
   └─ 자식(macOS, 선택): caffeinate -i -w <서버 pid>      (Windows: 런처가 SetThreadExecutionState)
```

창 하나(한국어 라벨, 코드 식별자는 영어; 언어는 9절 결정 15):

| 구역 | 내용 |
|---|---|
| 모드 | 로컬(이 컴퓨터만, `127.0.0.1` 고정) / 원격(같은 네트워크·Tailscale, `--remote`) |
| 주소·포트 | 라벨 붙은 후보 목록(Tailscale / LAN / 인터넷으로 나가는 주소 / 직접 입력) + "다시 찾기", 포트(기본 8000) + "빈 포트 찾기", 공개 주소(`--public-url`, 자동 채움·수정 가능) |
| 관리자 키 | 고정(설정에 저장) / 매번 새로, 마스킹 표시, "새로 만들기" |
| 저장 | 저장 폴더(기본 `saves/`), 자동 저장 체크(원격만) |
| AI | 탐색 AI 체크포인트 파일(기본 `checkpoints/play/search.pt`; 링크면 "search.pt → mix-v139-10081.pt"처럼 대상까지) + 상태 라벨("켜짐" / "꺼짐: torch 없음 — `uv sync --extra train`" / "링크가 가리키는 파일 없음: <대상>"), AI 속도(보통/빠르게/즉시) |
| 그림 | 에셋 폴더(비우면 기존 `assets` 링크 기본값; 하위 `cards/ icons/ tokens/ board/` 유무 표시) |
| 실행 | 잠자기 방지 체크(원격 기본 켬), 시작 뒤 브라우저 열기 체크, **[시작]** **[중지]**, 상태 줄(글자 + 색) |
| 링크 | 관리자 링크 [복사][열기], 방 링크 기준 주소, 진행 중 게임별 방 링크 목록 [복사] (5단계) |
| 로그 | 서버 출력(읽기 전용, 2,000줄 상한, `#admin=` 뒤는 `…`로 마스킹), [로그 폴더 열기] |
| 메뉴 | "바로가기 만들기", "설정 폴더 열기", "진단"(`--check`와 같은 내용: Python·Tk·uvicorn·torch 버전, `git rev-parse --short HEAD`, 저장 형식·codec 버전, 사전 검사 결과) |

호스트의 한 판: 더블클릭 → 지난 설정 그대로 → [시작] → 관리자 링크가 브라우저에 열림 → 게임 만들고 방 링크 복사해 전송 → 끝나면 [중지] 또는 창 닫기(확인 창). 터미널은 처음 설치(uv·clone·`uv sync`) 때만 쓴다. 런처 창을 닫으면 서버도 꺼진다(최소화는 괜찮다) — 가이드에 적는다(12절).

## 3. 검토한 다섯 안과 판정

독립 설계자 다섯이 각도 하나씩 맡아 안을 냈고, 사실 검증(4절) 뒤 심사위원 셋(호스트 사용자·저장소 유지보수자·크로스플랫폼 위험)이 네 축 0~10점으로 채점했다. 세 관점 모두 같은 순위였다.

| 안 | 호스트 | 유지보수 | 위험 | 합계(세 심사 평균) | 판정 |
|---|---|---|---|---|---|
| **tkinter 창**(표준 라이브러리, 새 의존성 0) | 8 | 9 | 8 | **31.7** | 채택 |
| 로컬 웹 페이지 런처(두 번째 작은 FastAPI 앱, 브라우저 탭) | 6~7 | 7 | 8 | 26.7 | 기각: 런처 자체가 `ui` extra를 요구해 **의존성이 없을 때 런처가 못 뜬다**(그 상황을 알리는 길이 tkinter messagebox로 돌아옴); 127.0.0.1 제어면은 토큰·Host 검사 없이는 같은 브라우저의 아무 사이트가 서버를 끄고 띄울 수 있음; 탭 닫기≠중지 |
| PySide6 + PyInstaller 번들 | 7~8 | 4~5 | 6~7 | 21.7 | 기각: 휠 82~116 MB를 표준 동기화에 추가, 서명·공증 없는 번들(Gatekeeper·SmartScreen), OS별 재빌드, torch 포함 시 0.5 GB+, 프로젝트 폴더 규칙과 긴장. 사용자 요구("터미널 대신 GUI")에 비해 과함 |
| 메뉴바/트레이 상주형(rumps·pystray) | 4~5 | 3~4 | 3 | 14.7 | 기각: rumps 0.4.0(2022, 릴리스 중단), pystray 0.19.5(2023)는 **macOS 26(이 Mac mini)에서 메뉴 갱신 중 SIGTRAP** 미해결; Windows 중지가 하드 킬뿐; 드문 설정은 JSON 손편집 |
| GUI 코드 최소안(.command/.cmd + 서버 웹 UI에 호스트 패널) | 5~6 | 4~6 | 6 | 20.7 | 기각: `.command`는 **Terminal 창을 연다**(사용자가 불편하다고 한 바로 그것); 서버가 "누가 띄웠는가"를 알게 되는 결합(`/host/*` 경로, 종료 코드 프로토콜)이 uvicorn의 시그널 재발신과 충돌 |

다른 안에서 가져온 것(채택안에 반영됨): 관리자 키는 argv가 아니라 환경 변수로(`ps`에 안 보임); `--check`·헤드리스 `--start` 서브커맨드; 이전 런처가 남긴 서버 감지; "이전 설정으로 다시 시도" 버튼; Windows Job Object 백스톱; 로그 꼬리 → 사람 말 표; 주소는 "정답 하나"가 아니라 라벨 붙은 후보 목록; 첫 설치용 더블클릭 스크립트.

## 4. 확인한 사실 (2026-10-08; 설계를 묶는 것만)

| 사실 | 근거 | 설계에 미치는 것 |
|---|---|---|
| uv의 python-build-standalone 3.14.6에 tkinter가 macOS·Windows 모두 들어 있다. macOS는 Tk 9.0.3; Windows는 uv 0.11.x가 받는 빌드가 **Tk 8.6.14**, PBS 20260804 이후(uv ≥ 0.12.2)는 9.0.4 | 이 Mac `import tkinter` → 9.0; PBS `cpython-windows/build.py`의 `tk-windows-bin-8614`/`-904` 분기 | 런처는 Tk 8.6과 9.0 둘 다에서 돌아야 한다(Tk 9 전용 기능 금지). 시작 로그에 `tkinter.TkVersion` 기록 |
| uvicorn 0.52.4는 잡은 시그널을 종료 뒤 `signal.raise_signal`로 **다시 올린다** (`uvicorn/server.py` 339~347행, `capture_signals`/`handle_exit`) | 설치된 소스 확인 | SIGTERM으로 끝낸 서버의 종료 코드는 -15, Windows CTRL_BREAK는 3(추정). **종료 코드로 성공을 판정하지 않는다.** stdin EOF 감시 스레드는 `handle_exit`를 부르지 말고 `hub.close()` + `server.should_exit = True`를 직접 세운다(재발신이 없어 코드 0; uvicorn 메인 루프가 0.1초마다 `should_exit`를 본다) |
| Windows `Popen.terminate()`는 `TerminateProcess`(핸들러·graceful 대기 없음); `CTRL_BREAK_EVENT`는 **같은 콘솔을 공유하는** 프로세스에만 닿는다(pythonw 런처는 콘솔이 없음) | Python/MS 문서 | Windows에서 시그널로 정상 종료시킬 길이 없다 → stdin EOF가 1차 수단이어야 한다 |
| **Windows에서 uv venv의 `python.exe`·`pythonw.exe`는 실제 인터프리터가 아니라 리디렉터다**(uv 관리 Python이면 uv 트램펄린, 아니면 CPython `venvlauncher.exe`). 둘 다 기반 `python.exe`를 자식으로 띄워 자기 Job(`KILL_ON_JOB_CLOSE\|SILENT_BREAKAWAY_OK`)에 넣고 기다렸다가 종료 코드를 그대로 돌려준다; uv 트램펄린은 Job 배정 실패를 경고만 한다 | uv `uv-virtualenv/src/virtualenv.rs`, `uv-trampoline/src/bounce.rs`, `uv-windows/src/job.rs`; CPython `PC/launcher.c` | Windows 자식은 어차피 2단(리디렉터 → 기반). Popen pid·`server.pid`·`terminate()`는 리디렉터에 닿고 기반 프로세스는 리디렉터의 Job으로 따라 죽는다. 그래서 `uv run`·스크립트 exe로 층을 더 얹지 않고 `sys.executable -m`을 쓴다. macOS는 `.venv/bin/python`이 심볼릭 링크라 단일 프로세스 |
| 표준 빌드의 uv venv에는 `pythonw.exe`가 항상 생긴다(`uv sync`가 성공했으면 있다) | uv `virtualenv.rs`(셤 복사, 없으면 베이스의 `pythonw.exe` 복사; 둘 다 없으면 venv 생성 실패), CPython `PC/layout`이 항상 포함 | 콘솔 없는 런처가 가능하다. 7단계의 `dir .venv\Scripts\pythonw.exe`는 확인용 |
| 자동 저장은 `<id>.json.tmp` → `os.replace`라 하드 킬에도 반쯤 쓰인 파일이 남지 않는다. 서버에 종료 시 저장 훅은 없다 | `server/persistence.py` 507~511행, `test_a_killed_server_recovers_from_its_autosave` | 백스톱 하드 킬은 저장을 깨지 않는다. 잃는 것은 진행 중 턴뿐이니 중지 확인 창에 "지금 저장"을 권한다 |
| Windows Job Object `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`는 **마지막 핸들이 닫히는 순간**(= 런처 사망 즉시) 자식을 `TerminateProcess`한다; macOS에는 부모 사망 시그널이 없다 | MS 문서, `man prctl`(Linux 전용) | Windows 고아 방지는 ctypes Job Object. 단 런처가 죽으면 이것이 가장 먼저 작동해 서버를 즉시 끝내므로(정상 종료 유예 없음) stdin EOF 경로는 [중지]·창 닫기에서만 밟힌다. macOS는 부모 사망 시그널이 없어 자식 쪽 감시가 필요하다 — stdin EOF를 고른다(kqueue `NOTE_EXIT`·`getppid` 폴링도 가능하나 OS 공통 경로가 아님) |
| uv는 `[project.gui-scripts]`를 Windows에서 pythonw 트램펄린으로 깐다(PR #4409). 단 `uv run <gui-script>`는 Windows에서 **즉시 종료**(uv 이슈 #20100) | uv 소스·이슈 | Windows 더블클릭 대상은 `.venv\Scripts\dune-imperium-launcher.exe` 직접. 검증도 `uv run`으로 하지 말 것. pythonw 아래서는 `sys.stdout`이 `None`이라 이 exe로 `--check`를 쳐도 출력이 없다(콘솔용 플래그는 `python -m dune_imperium.launcher.cli`) |
| macOS Finder에서 띄운 프로세스는 셸 PATH가 없다(launchd 기본만; `uv`는 `~/.local/bin`, App Store판 Tailscale CLI는 앱 번들 안). Windows 탐색기는 레지스트리 PATH를 받지만 터미널과 다를 수 있다 | 이 Mac `launchctl getenv PATH` 빈 값 | 서버는 `sys.executable -m …`로 띄우고, uv·tailscale은 PATH 다음에 후보 경로에서 직접 찾는다(설치·동기화·조회 용도에만) |
| `.command` 더블클릭은 Terminal.app이 새 창을 열어 실행한다 | Terminal `Info.plist` UTI | 본선은 `.app` 번들(plistlib로 생성), `.command`는 첫 설치용만 |
| 로컬에서 만든 `.app`에는 quarantine 속성이 없어 Gatekeeper가 막지 않는다 | Apple DTS | 서명·공증 불필요(다른 Mac에 복사하는 시나리오는 범위 밖) |
| Windows 방화벽은 프로그램이 listen할 때 한 번 묻고, **취소하면 차단 규칙 2개가 영구로 남아** 다시 묻지 않는다; 규칙은 exe 전체 경로 기준. listen하는 프로세스는 `.venv\Scripts\python.exe`(리디렉터, 소켓을 열지 않음)가 아니라 **uv가 설치한 기반 `python.exe`**(`uv python dir` 아래 `cpython-3.14-windows-x86_64-none\python.exe` junction 경로; 규칙에 junction 경로가 적히는지 풀린 패치 폴더가 적히는지는 7단계에서 확인) | MS 문서, uv `bounce.rs` | 원격 첫 시작 전에 안내; 친구가 못 들어오면 `wf.msc`에서 uv 기반 인터프리터 `python.exe`의 차단 규칙 삭제 안내. `.venv` 재생성은 규칙에 영향이 없고, 기반 Python 폴더가 바뀔 때(`uv python upgrade`, 다른 minor)만 다시 물을 수 있다(미확인) |
| `bind_problem`의 `SO_REUSEADDR` 프로브는 Windows에서 LISTEN 중인 포트도 통과시킬 수 있다. uvicorn의 실제 bind(asyncio `create_server`)는 Windows에서 `SO_REUSEADDR`를 켜지 않는다 | Windows 소켓 의미론, asyncio 기본값 | win32에서는 **옵션 없이 bind**해 프로브(서버의 bind와 같은 의미; 5.3절), 7단계에서 기존 `test_a_port_somebody_listens_on_is_a_bind_problem`으로 확인 |
| UDP connect 트릭(`8.8.8.8`)은 이 Mac에서 **VPN utun 주소 10.1.0.4**를 돌려준다; LAN 주소 192.168.0.64는 `getaddrinfo(gethostname())`에서 나온다. Tailscale은 `100.100.100.100`에 connect하면 100.x가 나온다(꺼져 있으면 기본 경로 주소가 나오므로 100.64/10 검사 필수) | 이 Mac 실측 | 후보는 라벨 붙은 목록: LAN은 `getaddrinfo`/`ifconfig`/`Get-NetIPAddress`, Tailscale은 CLI 우선 + UDP 트릭 보조, 8.8.8.8 결과는 "인터넷으로 나가는 주소" |
| Tailscale CLI: macOS App Store판 `/Applications/Tailscale.app/Contents/MacOS/Tailscale`(env `TAILSCALE_BE_CLI=1`), 독립판 `/usr/local/bin/tailscale`; Windows `%ProgramFiles%\Tailscale\tailscale.exe`. `status --json`에 `BackendState`·`Self.TailscaleIPs` | 공식 문서, 이 Mac 실측(1.102.4) | 탐색 순서 고정, `Running`이 아니면 "Tailscale 연결이 꺼져 있음" |
| `caffeinate -i -w <pid>`는 그 pid가 끝나면 assertion을 놓고, 런처가 죽어도 새지 않는다. Windows `SetThreadExecutionState(ES_CONTINUOUS\|ES_SYSTEM_REQUIRED)`는 런처 수명 스레드에서 걸고 명시 해제 | `man caffeinate`, MS 문서, 이 Mac `pmset -g assertions` 실측 | 잠자기 방지는 새 의존성 없이 OS별 두 구현 |
| 이 저장소에 git 추적 심볼릭 링크는 0개; `assets`·`checkpoints/play/search.pt`는 사람이 만드는 로컬 링크 | `git ls-files -s`에 mode 120000 없음 | Windows에 링크를 요구하지 않는다: 에셋 폴더 → 환경 변수 5개, 체크포인트 → 실제 `.pt` 파일 선택 |
| torch 2.14.0 cp314 win_amd64 휠 124 MB, CUDA 의존성은 Linux 마커뿐 | `uv.lock` | Windows도 `uv sync --extra train` 그대로; 첫 설치 때 "약 125 MB" 안내 |
| `[WinError 126]`(torch DLL 누락)은 `find_spec("torch")`로 못 잡는다 | 서버 `resolve_search_checkpoint` | 런처 사전 검사는 별도 프로세스로 `import torch`를 실제로 돌린다 |
| `dune_imperium.cli.server`는 `ui` extra 없이도 import된다(fastapi·uvicorn은 `main()` 안에서 지연 import); `resolve_search_checkpoint`·`bind_problem`·`admin_link`·`resolve_access`는 순수 함수 | `cli/server.py` | 런처가 같은 venv에서 같은 함수를 불러 탐색 AI 상태·포트 문제·링크를 얻는다. 서버 API를 늘릴 이유가 없다 |
| py2app 0.28.9+·PyInstaller 6.15+는 3.14를 지원한다 | PyPI | 가능은 하지만 1차 범위 밖(10절) |

## 5. 설계

### 5.1 모듈 배치 (`src/dune_imperium/launcher/`, 새 패키지)

| 파일 | 역할 | tkinter |
|---|---|---|
| `__main__.py` | `python -m dune_imperium.launcher` → `cli.main()`(두 OS가 같은 플래그를 받는다) | 없음 |
| `cli.py` | 콘솔 진입점(`python -m dune_imperium.launcher.cli`, `.venv/bin/python`·`.venv\Scripts\python.exe`로 실행): 플래그 없으면 창(`gui.main()`); `--check`(사전 검사·진단을 표준 출력에 쓰고 종료 코드로 알림); `--make-shortcut`(5.10); `--start --print-link [--settings <path>]`(창 없이 `supervisor`로 서버를 띄워 준비되면 `{"admin_url": …, "base_url": …, "pid": …}` JSON 한 줄을 stdout에 쓰고 자기 stdin EOF까지 기다렸다가 중지 사다리로 끝냄 — E2E·Windows 콘솔 검증용); `--settings <path>`, `--no-browser`. 콘솔 출력은 `print`가 아니라 `sys.stdout is not None`일 때만 `sys.stdout.write` | 없음 |
| `settings.py` | `LauncherSettings`(frozen dataclass) + `load()`/`save()`(JSON, 모르는 키 보존, 깨지면 `launcher.json.broken-<시각>`으로 옮기고 기본값), 모드별 검증은 `cli.server.resolve_*`와 같은 규칙 | 없음 |
| `command.py` | 설정 → `(argv, env)`; `preflight(settings) -> list[Problem]`(의존성·포트·주소·체크포인트·에셋); `explain_failure(log_tail, exit_code) -> str` 표 | 없음 |
| `addresses.py` | 후보 목록(`Candidate(label, ip, source)`): 순수 파서(`parse_tailscale_status`, `parse_ifconfig`, `parse_get_netipaddress_json`, `classify(ip)`)와 조회 함수 분리 | 없음 |
| `supervisor.py` | `ServerProcess`: `start()`, `wait_ready()`, `stop()`, `is_alive()`, `admin_url`, `games()`; 로그 리더 스레드 → `queue.Queue[str]` + 파일 tee; **공통 스폰 헬퍼**(Windows `CREATE_NO_WINDOW`, `stdin=DEVNULL`, timeout — 서버·Tailscale·PowerShell·torch 검사·.lnk 생성이 모두 이 한 곳을 거친다); Windows Job Object | 없음 |
| `keepawake.py` | macOS `caffeinate -i -w <pid>` 자식 / Windows `SetThreadExecutionState` / 그 외 no-op | 없음 |
| `shortcuts.py` | `.app` 번들(plistlib + 셸 스크립트)과 `.lnk`(PowerShell COM) 생성; 텍스트 생성과 파일 쓰기 분리 | 없음 |
| `texts.py` | 한국어 라벨·문구 표(영어 열은 나중에 더할 수 있게 표로) | 없음 |
| `gui.py` | ttk 창. `import tkinter`는 `main()` 안에서만. 상태→뷰 모델(`LauncherState` → 버튼 활성·라벨·링크 목록)은 순수 데이터 | 있음 |

`pyproject.toml`: `[project.gui-scripts] dune-imperium-launcher = "dune_imperium.launcher.cli:main"` — 창을 띄우는 용도뿐(Windows exe는 pythonw라 콘솔 출력이 없다; 콘솔용 플래그는 `python -m dune_imperium.launcher.cli`로만 문서화). `paths.py`에 `LOCAL_DIR = PROJECT_ROOT / "local"`. `.gitignore`에 `/local/`, `/*.app/`, `/*.lnk`. `tests/launcher/` 파일 이름은 `tests/` 관례대로 전체에서 유일하게.

### 5.2 서버 띄우기와 내리기

**명령.** `[python, "-u", "-m", "dune_imperium.cli.server", "--exit-when-stdin-closes", "--host", host, "--port", port, "--ai-pace", pace, (--saves-dir는 설정이 있을 때만; --remote, --public-url, --no-autosave, --search-checkpoint <resolve()한 실제 파일>)]`, `cwd=PROJECT_ROOT`, `stdin=PIPE, stdout=PIPE, stderr=STDOUT`. `python`은 `sys.executable`이되 Windows에서 그것이 `pythonw.exe`면 같은 폴더의 `python.exe`로 바꾼다(`CREATE_NO_WINDOW`). `uv run`이나 `.venv\Scripts\dune-imperium-server.exe`(스크립트 트램펄린)는 쓰지 않는다: Windows에서는 `.venv\Scripts\python.exe` 자체가 리디렉터라(4절) `sys.executable -m`도 2단이고, 그 위에 `uv run`은 uv.exe(CTRL_BREAK 미전달, gui-scripts는 #20100), 스크립트 exe는 트램펄린 한 층을 더 얹는다. 층이 가장 적고 종료 코드가 그대로 올라오는 `sys.executable -m`을 쓴다(기존 `tests/server/test_server_cli.py::_server_process`와 같은 방식). `scripts/e2e/common.py`의 POSIX 전용 `.venv/bin/…` 패턴은 런처에 들이지 않는다. 카드·아이콘·토큰·보드 그림은 argv가 아니라 환경 변수 한 길로만 넘긴다.

**환경.** 부모 환경을 복사하되 `DUNE_IMPERIUM_*`는 **모두 지운 뒤** 런처가 정한 것만 넣는다(설정의 `null`이 정말 서버 기본값이 되게; 터미널에서 띄운 런처가 부모의 `DUNE_IMPERIUM_SEARCH_CHECKPOINT`를 조용히 물려주지 않게). + `PYTHONUNBUFFERED=1`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`; 관리자 키는 `DUNE_IMPERIUM_ADMIN_KEY`(argv에 두면 작업 관리자·`ps`에 보인다; `resolve_access`가 이미 읽는다); 에셋 폴더가 있으면 `DUNE_IMPERIUM_CARD_IMAGE_DIR=<폴더>/cards`, `…_ICON_DIR=<폴더>/icons`, `…_TOKEN_DIR=<폴더>/tokens`, `…_BOARD_IMAGE=<폴더>/board/map.jpg`, `…_BENE_TLEILAX_IMAGE=<폴더>/board/bene_tleilax.jpg`(`server/app.py` 기본값과 같은 상대 경로; 서버 무변경).

**준비 확인.** `GET http://<접속 주소>:<port>/whoami`를 0.2초 간격 최대 30초(`admin_link()`와 같은 규칙으로 `0.0.0.0`→`127.0.0.1`). 200이면 `access`·`search_ai`·`autosave`·`ai_pace`를 상태 줄에 반영(런처의 사전 판정과 다르면 서버 쪽을 믿고 "서버 로그 보기"를 안내). 그 전에 프로세스가 죽으면 종료 코드와 로그 마지막 30줄을 `explain_failure`로 번역해 보인다. 원격 모드면 추가로 고른 주소에 `socket.create_connection`을 해 본다 — 이것은 "서버가 그 주소에서 응답한다"까지만 말한다(자기 주소로의 접속은 방화벽을 재현하지 못할 수 있음). 방화벽 판정의 유일한 근거는 **다른 기기에서의 접속**이고, 그 문구는 상태 줄 옆 도움말에 둔다(5.8).

**중지 사다리.** `stdin.close()` → 최대 10초 → `terminate()`(POSIX SIGTERM) → 5초 → `kill()`. Windows는 `terminate()`/`kill()`이 Popen pid인 리디렉터만 `TerminateProcess`하고 기반 `python.exe`는 리디렉터의 Job으로 따라 죽는다(uv 트램펄린이 Job 배정에 실패하면 드물게 남을 수 있다). 그래서 Windows 하드 단계는 런처 자신의 Job에 `TerminateJobObject`(리디렉터와 그 뒤에 생겨 Job에 든 기반 프로세스를 함께)로 하고, 그래도 포트가 안 풀리면 `server.pid`를 부모로 둔 프로세스(`Win32_Process.ParentProcessId`)를 찾아 끝낸다. 성공 판정은 "제한 시간 안에 프로세스가 끝났고 포트가 풀렸는가"이며 종료 코드는 보지 않는다(4절). Windows는 시작 직후 Job Object(`KILL_ON_JOB_CLOSE`, 상속 불가 핸들, 런처 수명 동안 핸들 유지)에 리디렉터를 넣는다(Popen 뒤에 넣으므로 그보다 먼저 생긴 기반 프로세스는 런처 Job 밖일 수 있다 — 리디렉터의 Job이 덮는다). "시작 중"(시그널 핸들러 설치 전)의 중지는 하드 종료임을 전제하고 UI는 "시작 중…"으로 둔다.

**창 닫기.** 서버가 꺼져 있으면 설정 저장 후 종료. 켜져 있으면 진행 중 게임 수를 보이며 "서버를 끄고 닫을까요? (자동 저장 N개, 진행 중이던 턴은 사라질 수 있음 — 먼저 '지금 저장'을 권함)" 확인 → 중지 사다리 → 종료. 최소화는 서버를 유지한다.

**런처 crash.** macOS: OS가 파이프 쓰기 끝을 닫아 서버가 stdin EOF로 스스로 정상 종료한다. Windows: 런처의 핸들 테이블이 닫히며 Job Object(`KILL_ON_JOB_CLOSE`)가 서버를 즉시 하드 킬한다 — 파이프 EOF가 먼저 닿더라도 `hub.close()` → `should_exit` → uvicorn 종료가 끝날 시간은 없다. 자동 저장이 원자적이라 잃는 것은 진행 중 턴뿐이다. 두 OS 모두 런처가 죽으면 로그 tee도 멈추므로 crash 뒤의 서버 로그는 남지 않는다.

**이전 서버·다른 점유자.** 시작 전 `bind_problem`이 포트 사용 중이라 하고 `/whoami`가 200이면 "이 포트에 서버가 떠 있음". `tmp/launcher/server.pid`가 살아 있는 pid를 가리키면(Windows에서는 리디렉터 pid) "끄기"를 제안하고, 설정의 관리자 키가 "고정"이고 그 키로 `/whoami`의 `admin: true`가 확인될 때만 "붙기(링크만 보기)"도 제안한다("매번 새로"면 이전 키를 모른다). pid가 없거나 다르면(다른 체크아웃의 런처, 터미널 서버, `.claude/launch.json`의 `ui-server`도 8000이다) "이 런처가 띄운 서버가 아님" + [빈 포트 찾기]만. pid가 살아 있으나 `PermissionError`(다른 계정)면 "다른 사용자가 띄운 서버" + [빈 포트 찾기]. 더블클릭을 두 번 하면 `tmp/launcher/launcher.pid`가 살아 있는 pid를 가리킬 때 "이미 실행 중입니다" 안내 후 종료(창을 앞으로 올리는 소켓 노크는 두지 않는다 — 10절).

### 5.3 서버 쪽 변경 (전부 옵트인·하위 호환, 1단계)

1. `cli/server.py` `--exit-when-stdin-closes`: `server` 객체를 만든 뒤 데몬 스레드가 `sys.stdin.buffer.read()`를 EOF까지 기다렸다가 `hub.close()`(`events.py` `close`는 "Safe to call from any thread") 후 `server.should_exit = True`를 세운다. `PlayServer.handle_exit`를 부르지 않는다(uvicorn이 `_captured_signals`에 넣어 종료 뒤 재발신하므로 코드가 0이 아니게 된다). `sys.stdin is None`이면 플래그를 무시하고 경고 한 줄. 도움말·호스트 가이드 옵션 표에 "(stdin이 파이프여야 한다; `/dev/null`·`nohup` 아래에서는 뜨자마자 종료됨)"을 포함한 한 줄.
2. `bind_problem`: `sys.platform == "win32"`에서는 `SO_REUSEADDR`를 켜지 않고 bind한다(asyncio `create_server`의 Windows 기본과 같아 서버의 bind와 의미가 같다). 그 외 OS는 그대로.

`GET /whoami`에는 손대지 않는다. 탐색 AI가 꺼진 까닭은 런처가 자기가 조립한 argv·env로 `cli.server.resolve_search_checkpoint(_build_parser().parse_args(argv), env)`를 직접 불러 얻는다(서버 콘솔 줄과 글자까지 같다; `[WinError 126]`은 5.7의 별도 프로세스 `import torch` 검사가 덮는다). 서버 `--assets-dir` 플래그도 넣지 않는다(환경 변수 5개로 충분; 9절 결정 10).

### 5.4 설정 파일

`local/launcher.json`(`paths.LOCAL_DIR`; `tmp/`는 "아무것도 안 돌 때 지워도 되는" 폴더라 설정에 부적합, `saves/`는 서버가 `*.json`을 저장 목록으로 글롭한다). 예:

```json
{"version": 1, "mode": "remote", "host": "100.101.102.103", "port": 8000,
 "public_url": "http://100.101.102.103:8000", "admin_key_mode": "fixed", "admin_key": "…",
 "saves_dir": null, "autosave": true, "search_checkpoint": null, "ai_pace": "normal",
 "assets_dir": null, "keep_awake": true, "open_browser": true,
 "last_good": {…}, "last_error": null, "window": {"x": 120, "y": 80, "w": 720, "h": 640}}
```

- `null`은 서버 기본값. PROJECT_ROOT 아래 경로는 상대 경로로 저장(Mac·Windows 체크아웃 사이에 복사해도 쓰이게). 사용자가 고른 경로는 그대로(링크면 링크) 저장하고 argv에만 `resolve()`한 실제 파일을 넘긴다.
- `version`이 없으면 1로, 1보다 크면 읽되 모르는 키를 보존하고 상태 줄에 "새 형식의 설정"을 알린다. 기기 고유 키(`host`, `public_url`, `last_good`, `window`): 다른 기기에서 복사한 설정의 `host`가 사전 검사에서 "이 PC에 없는 주소"면 후보 1순위로 바꾸고 `last_good`은 비운다.
- 원자적 쓰기(`.tmp` → `os.replace`), [시작]과 창 닫기 때 저장. 관리자 키는 "고정"일 때만 평문 저장(git 무시, POSIX 0o600; Windows는 ACL을 바꾸지 않고 체크아웃을 사용자 프로필 아래에 두는 것으로 대신한다고 가이드에 적는다; 공유 PC에서는 "매번 새로"를 권한다).
- `last_good`은 마지막으로 뜬 설정이다. 새 설정으로 안 뜨면 **자동으로 되돌리지 않는다**(호스트가 친구에게 보낼 링크가 몰래 바뀌면 안 된다). 실패 문구와 함께 "이전 설정(<주소>:<포트>)으로 다시 시도" 버튼을 보이고 누를 때만 쓴다.
- `window`는 복원 전에 `winfo_screenwidth/height`로 화면 안으로 clamp, 실패하면 기본 크기·중앙.

### 5.5 관리자 링크·방 링크·상태

stdout을 파싱하지 않는다. 런처가 키를 정하고(고정 키 또는 `server.access.new_token()`), 링크는 이미 테스트된 `cli.server.admin_link(host, port, key)`로 계산한다(콘솔 출력과 글자까지 같다). 뜬 뒤 `/whoami`의 `access == "remote"`와, `Cookie: dune_admin=<key>` 헤더로 다시 부른 `/whoami`의 `admin: true`·`public_url`로 "링크가 맞다"를 확인한다(`app.py` `_credentials`가 그 쿠키 값을 키로 읽으므로 `POST /auth/admin` 왕복이 필요 없다). 방 링크 기준은 설정의 `public_url`(없으면 `http://<host>:<port>`), 게임별 `<base>/#game=<id>`는 같은 쿠키로 `GET /games`를 3초마다 읽어 목록으로(5단계). 로컬(open) 모드는 쿠키 없이 같은 호출. 탐색 AI 상태는 5.3절대로 런처가 `resolve_search_checkpoint`로 얻고, 뜬 뒤 `/whoami.search_ai`와 다르면 서버 쪽을 믿는다.

### 5.6 주소 후보 (`addresses.py`)

| 라벨 | 출처 | 분류 |
|---|---|---|
| 로컬 | `127.0.0.1` 고정 | 로컬 모드 유일 |
| Tailscale | CLI `status --json`(`BackendState == "Running"`일 때 `Self.TailscaleIPs`의 IPv4; 탐색 순서 `shutil.which` → macOS 두 경로 → Windows `%ProgramFiles%`, env `TAILSCALE_BE_CLI=1`, timeout 3초) / 보조: UDP connect `100.100.100.100` 결과가 100.64/10이면 "Tailscale(추정)" | 원격 기본 1순위 |
| LAN | `getaddrinfo(gethostname(), AF_INET)` + macOS `ifconfig` / Windows `powershell -NoProfile Get-NetIPAddress -AddressFamily IPv4 \| ConvertTo-Json` 파싱 → 10/8·172.16/12·192.168/16 | 원격 2순위 |
| 인터넷으로 나가는 주소 | UDP connect `8.8.8.8` → `getsockname()` | 표시만(VPN 주소일 수 있음) |
| 직접 입력 | Combobox 편집 | 마지막 선택을 기억 |

127/8·169.254/16 제외, 모든 조회는 예외를 삼키고 빈 목록. 조회(CLI 3초, PowerShell 기동 수 초)와 [시작]의 사전 검사(`import torch` 수 초)는 **Tk 메인 스레드에서 기다리지 않는다**: 데몬 워커 스레드에서 돌리고 결과만 `queue` → `root.after()`로 반영하며 그동안 상태 줄은 "주소 찾는 중…"/"검사 중…", [시작]은 비활성. 고른 주소는 시작 전에 `bind_problem`으로 다시 검사해 "그 주소가 지금 이 PC에 없음(Tailscale 꺼짐?)"을 먼저 말한다. 인터넷 없는 LAN(모임 장소 공유기만)에서는 LAN 후보만 뜨고 "인터넷으로 나가는 주소" 줄이 비는 것이 정상 — 상태 줄에 "인터넷 없음(LAN 플레이 가능)". 런처·서버 자체는 인터넷이 필요 없다.

### 5.7 오류를 사람 말로 (`command.py`)

사전 검사(스폰 전): `find_spec("fastapi"/"uvicorn")` 없음 → "서버 의존성이 없습니다: 터미널에서 `uv sync --locked --inexact --extra ui`"; 탐색 AI 체크포인트가 있는데 별도 프로세스 `python -c "import torch"`가 실패 → "탐색 AI 사용 불가(<오류 첫 줄>): 탐색 AI 없이 시작합니다 / Visual C++ 재배포 패키지 확인"; 체크포인트가 링크인데 대상이 없으면 "링크가 가리키는 파일 없음: <대상>"(`os.readlink`); `bind_problem` 문구 → 포트 사용 중 / 이 PC에 없는 주소; 로컬 모드 + non-loopback → `resolve_access`와 같이 거절; **원격 모드 + loopback은 거절하지 않고 경고**("이 주소로는 친구가 들어올 수 없습니다(이 PC에서만 접속). 계속할까요?" — 서버와 가이드가 허용하는 정상 구성); 저장 폴더 없으면 mkdir; 에셋 폴더에 하위 폴더가 없으면 "그림 없이 시작"(오류 아님).

`explain_failure(log_tail, exit_code)` 표: `cannot listen on` → 포트/주소·Tailscale 안내; `[Errno 10048]`/`[WinError 10048]`/`error while attempting to bind` → 포트 사용 중; `No module named '(\w+)'` → "`uv sync --locked --inexact --extra ui`(탐색 AI는 `--extra train`)"(업데이트 뒤 `uv.lock`이 바뀐 경우를 덮는다); `torch` DLL → 재배포 패키지; 그 외 → 로그 그대로 + [로그 폴더 열기]. 요청하지 않았는데 서버가 끝나면 "서버가 예기치 않게 종료됨 — 로그 보기"; 요청한 중지 뒤의 종료 코드(0, -15, 3 등)는 모두 정상으로 표시.

### 5.8 Windows 손질

- `tkinter` import **전에** `ctypes.OleDLL("shcore").SetProcessDpiAwareness(1)`(IDLE과 같음; Per-Monitor V2는 Tk가 `WM_DPICHANGED`를 안 다룬다). IDLE처럼 `try/except (ImportError, AttributeError, OSError)`로 감싸고 실패는 로그에만.
- `font.families()`에 `Malgun Gothic`이 있으면 `TkDefaultFont`·`TkTextFont`를 그 가족으로. F1/F3/F5/F10 전역 바인딩 금지(IME 확정 문자가 기능키 keysym을 달고 오는 Tk 버그 f492c3, 8.6.14·9.0.4 모두).
- pythonw 아래에서는 `sys.stdout`이 `None`이라 `print`가 조용히 사라진다 — 런처 패키지는 `print` 대신 로그 파일·상태 줄을 쓴다(소스 검사 테스트로 가드; 유일한 콘솔 출력은 `cli.py`의 `sys.stdout is not None` 가드를 단 `write`). 예외는 `tmp/launcher/launcher.log` + `messagebox.showerror`.
- 런처가 Windows에서 띄우는 **모든** 자식 — 서버(`python.exe`), Tailscale CLI, PowerShell(`Get-NetIPAddress`, `.lnk` 생성), `python -c "import torch"` — 는 `supervisor`의 공통 스폰 헬퍼를 거쳐 `creationflags=CREATE_NO_WINDOW`를 받는다(콘솔 자식은 부모에 콘솔이 없으면 새 콘솔 창을 만들어 번쩍이고, CPython은 `shell=True`일 때만 `SW_HIDE`를 붙인다). 조회·검사 호출은 `stdin=DEVNULL, capture_output=True, timeout=…`으로 통일. `close_fds=True` 기본. Job Object 백스톱(ctypes; `sys.platform == "win32"` 분기 안에 두어 mypy strict 통과).
- 원격 모드 첫 시작 전 안내: "처음 한 번 'Windows 보안 경고'가 뜨면 **개인 네트워크를 체크하고 액세스 허용**(취소하면 영구 차단)". 친구가 못 들어오면: `wf.msc`에서 Program 경로가 uv 기반 인터프리터(`uv python dir` 아래 `…\cpython-3.14…\python.exe`)인 `python.exe` 차단 규칙(TCP·UDP 2개) 삭제 — `.venv` 아래 경로가 아니다(4절). 활성 프로필이 Public이면 진단에 표시(`Get-NetConnectionProfile`).
- 경로에 한글·공백이 있어도 `Path`·리스트 argv만 쓰고 `shell=True` 금지.
- `[WinError 64]`(ProactorEventLoop의 listening 소켓 닫힘, CPython #93821 미해결)에 대비해 `/whoami` 주기 폴링 n회 실패 → "서버 응답 없음" + [다시 시작].
- (양 OS 공통) 접근성 최저선: Tab 순서는 표의 위→아래, [시작]은 Enter·창 닫기 확인은 Esc로 취소, 상태는 색과 함께 글자로, 글꼴 크기는 시스템 설정을 따름(Tk에는 스크린 리더 지원이 없다).

### 5.9 macOS 손질

- Tk 9.0 aqua: HiDPI·다크 모드 자동. 색을 하드코딩하지 않는다. `tk scaling`을 손대지 않는다(9.0.3·9.0.4 버그).
- 창은 기본으로 앞에 온다(Tk가 `activateIgnoringOtherApps`를 호출). 혹시 뒤에 열리면 `root.lift()` 후 `-topmost` 토글.
- 잠자기 방지는 `caffeinate -i -w <서버 pid>`를 별도 자식으로(서버를 caffeinate로 감싸면 시그널·pid 처리에 끼어든다). 토글 끄기 = caffeinate `terminate()`.
- Dock 이름·아이콘이 "Python"으로 보일 수 있다(.app이 셸 스크립트로 python을 exec). 창 제목·`iconphoto`로 창 쪽만 꾸미고 한계는 문서에 적는다.
- 친구가 못 들어오면: 시스템 설정 > 네트워크 > 방화벽과 "로컬 네트워크" 허용 확인(도움말 문구).

### 5.10 더블클릭 산출물 (`shortcuts.py`)

- **macOS**: 메뉴 "바로가기 만들기" → `PROJECT_ROOT/Dune Imperium Server.app`(`Contents/Info.plist`: `CFBundleExecutable=launch`, `CFBundleName`, `CFBundleIdentifier=local.dune-imperium.launcher`, `CFBundlePackageType=APPL`; `Contents/MacOS/launch`: `#!/bin/zsh`, 자기 위치 기준 `cd "$(dirname "$0")/../../.."` 후 `exec .venv/bin/python -m dune_imperium.launcher`, chmod 755). 폴더를 옮겨도 깨지지 않는다. Dock에 끌어다 놓기는 사용자 몫.
- **Windows**: 더블클릭 대상은 `.venv\Scripts\dune-imperium-launcher.exe`(gui 트램펄린, 콘솔 없음; `pythonw.exe`는 `uv sync`가 성공했으면 있다, 4절). 메뉴 "바로가기 만들기" → `PROJECT_ROOT\Dune Imperium Server.lnk`(PowerShell `WScript.Shell` COM; 스크립트 본문은 `-EncodedCommand`(UTF-16LE base64)로 넘기고 대상 exe·시작 폴더는 환경 변수 `DUNE_LNK_TARGET`·`DUNE_LNK_WORKDIR`로 전달해 한글·공백·따옴표 인용을 없앤다).
- **처음 한 번(추적 파일)**: `scripts/launcher/Install Launcher.command`(100755) / `Install Launcher.cmd`(새 파일 `.gitattributes`에 `*.cmd text eol=crlf`; `.cmd`는 ASCII만 쓰거나 첫 줄 `chcp 65001`). 더블클릭하면 터미널이 한 번 열려 — PATH의 `uv`를 먼저 쓰고(`.command`는 로그인 셸, `.cmd`는 레지스트리 PATH) 없을 때만 후보 경로(macOS `~/.local/bin/uv`·`/opt/homebrew/bin/uv`; Windows `%USERPROFILE%\.local\bin\uv.exe`·winget 링크 폴더)를 보고, 그래도 없으면 가이드 2절의 설치 명령을 보여 준다 — `uv sync --locked --inexact --extra ui`(탐색 AI를 쓰려면 `--extra train`, 물어봄; 인터넷 필요, 탐색 AI면 약 125 MB)를 돌린 뒤 `.venv/bin/python -m dune_imperium.launcher.cli --make-shortcut`(Windows는 `.venv\Scripts\python.exe -m …`; 콘솔 python이라 결과·오류가 설치 터미널에 보인다; gui exe나 `uv run`으로 부르지 않는다)를 실행하고 런처를 띄운다. 이후에는 .app/.lnk만 쓴다. `uv sync`를 좁은 extra 집합으로 **exact** 실행하면 이미 깔린 rl/train이 지워지므로 반드시 `--inexact`.

### 5.11 잠자기 방지 (`keepawake.py`)

macOS: 서버 Popen 직후 `subprocess.Popen(["caffeinate", "-i", "-w", str(pid)])`, 핸들만 보관. Windows: 런처의 Tk 메인 루프 스레드에서 `kernel32.SetThreadExecutionState(0x80000001)`(`ES_CONTINUOUS|ES_SYSTEM_REQUIRED`; 디스플레이는 끄게 둔다), 중지·창 닫기·`atexit`에서 `0x80000000`으로 해제. 0 반환은 로그에만. 기본값: 원격 모드 켬. 노트북 배터리에서는 macOS `-s`가 무효라는 점을 문구에.

### 5.12 로그

시작마다 `tmp/launcher/server-<시각>.log`를 새로 만들고 최근 10개만 남긴다; `launcher.log`는 1 MB를 넘으면 `.1`로 한 번 회전. 서버가 시작 때 찍는 관리자 링크의 `#admin=` 뒤는 파일·창 모두 `…`로 마스킹(링크는 링크 구역에서 복사), 로그 파일은 POSIX 0o600.

## 6. 단계별 작업 (독립 병합 단위)

| 단계 | 범위 | 지키는 테스트 | 검증 등급 | 추정 |
|---|---|---|---|---|
| 1. 서버 CLI 두 가지 | `--exit-when-stdin-closes`(감시 스레드는 `hub.close()` + `should_exit`; 도움말에 파이프 조건), win32는 `SO_REUSEADDR` 없이 프로브; 호스트 가이드 옵션 표 | `test_server_cli.py`: 플래그로 띄우고 SSE 스트림을 연 채 stdin 닫기 → 2초 안 종료·**코드 0**·Traceback 없음(기존 `test_the_server_exits_at_once_while_an_event_stream_is_open` 복제); 플래그 없으면 기존 동작 불변; `stdin=DEVNULL`로 띄우면 즉시 종료(문서화된 조건) | **고위험(서버 종료·자동 저장 경로)** — 독립 리뷰 1회 | 2h |
| 2. 런처 코어(GUI 없음) | `__main__`·`cli`(`--check`, `--start --print-link`, `--settings`, `--no-browser`)·`settings`·`command`·`addresses`·`supervisor`(공통 스폰 헬퍼·Job Object)·`texts`, `paths.LOCAL_DIR`, `.gitignore` `/local/` | `tests/launcher/`: 설정 왕복·모르는 키·깨진 파일·버전 규칙·상대 경로·기기 고유 키·모드별 검증·`git check-ignore`(기존 `test_the_project_keeps_its_local_files_inside_the_checkout` 패턴); 설정→argv/env 스냅샷이 `_build_parser().parse_args()`와 `resolve_*`를 통과, 부모 환경에 `DUNE_IMPERIUM_SEARCH_CHECKPOINT`가 있어도 같은 argv/env; `preflight`(find_spec monkeypatch)·`explain_failure` 표; 주소 파서 고정 입력; `sys.platform`을 `"win32"`로·`subprocess`를 가짜로 monkeypatch해 서버·Tailscale·PowerShell·torch 검사 네 호출이 모두 `CREATE_NO_WINDOW`와 `stdin=DEVNULL`을 넘기는지; 실프로세스(`pytest.importorskip("uvicorn")`): 원격 시작→`/whoami.admin`·`public_url`·계산한 링크가 로그 줄과 같음·런처의 `resolve_search_checkpoint` 줄이 서버 stdout 줄과 같음, SSE 연 채 `stop()`이 2초 안 끝나고 포트가 풀림, 점유 포트→`StartupFailed` 문구에 포트 번호, 로그 tee·마스킹, `--start --print-link`가 JSON 한 줄을 내고 stdin EOF로 끝남; `tests/launcher/fake_server.py --stubborn`으로 사다리 3단 각각 | 낮음 — 주 세션이 diff 확인 | 5h |
| 3. tkinter 창·entry point | `gui.py`, `[project.gui-scripts]`, 폼·시작/중지·상태 줄·링크 복사(`clipboard_append`)/열기(`webbrowser`)·로그 창·창 닫기 확인·오류 대화상자·워커 스레드·창 위치 clamp | `test_gui.py`: 세션 범위 fixture 하나(`root = tkinter.Tk(); root.withdraw()`, `TclError`면 `pytest.skip("no display")`, `DUNE_IMPERIUM_SKIP_GUI_TESTS=1`이면 skip), 테스트는 `Toplevel`을 만들어 `root.update()`만으로 폼↔설정 왕복·모드 전환 활성/비활성·로그 큐 반영·preflight 실패 문구(supervisor 가짜 주입)·화면 밖 좌표 복원; `print` 금지 소스 가드; 상태→뷰 모델은 헤드리스 | 낮음 — macOS에서 터미널로 띄워 수동 확인 | 5h |
| 4. 잠자기 방지·더블클릭·첫 설치 | `keepawake.py`·`shortcuts.py`·`--make-shortcut`·메뉴·`scripts/launcher/Install Launcher.{command,cmd}`·`.gitignore` `/*.app/` `/*.lnk`·`.gitattributes`(새 파일) | plist를 `plistlib`로 읽어 검증, 셸 스크립트 텍스트(상대 경로·exec), `.lnk` PowerShell 명령·환경 변수 스냅샷(한글·공백·작은따옴표 경로), caffeinate argv(실행은 monkeypatch), Windows 분기 skipif; macOS Finder 더블클릭 리허설 | 낮음 | 3h |
| 5. 방 링크·게임 목록·이전 서버·다시 시도 | 관리자 쿠키로 `GET /games`·`GET /saves`, 게임별 방 링크 목록·복사·3초 갱신, 창 닫기 확인 창의 진행 중 게임 수, `server.pid`로 이전 서버 감지(붙기/끄기/다른 서버 규칙), "이미 실행 중입니다", "이전 설정으로 다시 시도" 버튼 | `test_supervisor`에 쿠키 호출·pid 감지(고정 키/새 키/다른 pid/PermissionError)·다시 시도 시나리오 | 낮음 — `/games`·`/saves` 호출 코드는 주 세션이 직접 읽는다 | 3h |
| 6. 문서·macOS 리허설·E2E | 12절 문서; `scripts/e2e/launcher_link.py` — e2e 환경(`scripts/e2e/.venv`, Python 3.12, Playwright만)에는 `dune_imperium`이 없고 소스는 3.14 전용이라 런처 모듈을 import하지 않는다. 기존 패턴(`influence_spies.py`·`scouts.py`가 엔진 코드를 `REPO/.venv/bin/python -c`로 돌리는 것)대로 `[REPO/".venv/bin/python", "-m", "dune_imperium.launcher.cli", "--start", "--print-link", "--settings", <임시 json>]`을 `stdin=PIPE`로 자식으로 띄워 첫 줄 JSON의 관리자 링크를 Playwright로 열어 호스트 패널·두 번째 컨텍스트의 방 링크 입장을 확인하고, 자식의 stdin을 닫아 서버가 내려가고 `saves/`에 자동 저장이 남는지 본다(`--remote`는 `127.0.0.1`에서도 되므로 `E2E_HOST` 불필요). `run_all.py`는 폴더의 `*.py`를 자동 발견하므로 등록은 없다(`SECONDS`는 순서 표; 측정 뒤 한 줄); 8절 macOS 체크리스트 | 낮음 | 2h |
| 7. Windows 네이티브 검증·수정 | 14700K PC(PowerShell 네이티브)에서 8절 Windows 체크리스트; 발견 수정; 가이드 1절의 "미검증" 문구를 "검증됨(날짜)"으로; `mypy --platform win32`도 Mac에서 한 번 | 결과에 따라 | 4h + 사용자의 PC 시간 |

합계 약 24 agent-시간. 1~4단계가 끝나면 목적은 달성된다(5는 편의, 6·7은 마무리). 단계 사이에 master와의 병합은 master 쪽에서 `--no-ff`(기존 규약). 인수인계 문서는 병합 때만 갱신한다. 검증 등급은 CLAUDE.md의 둘(낮음: 주 세션이 diff를 읽음 / 고위험: 독립 리뷰)만 쓴다.

## 7. 테스트·품질 전략

- **헤드리스 원칙**: `tkinter.Tk()`를 만드는 테스트는 디스플레이가 없거나 `DUNE_IMPERIUM_SKIP_GUI_TESTS=1`이면 skip. 세션 범위 루트 하나를 `withdraw()`해 두고 테스트는 `Toplevel`만 만든다(`uv run pytest -q` 중 창이 떴다 사라지며 포커스를 빼앗지 않게; 한 프로세스에서 `Tk()`를 반복 생성·파괴하는 것은 macOS에서 불안정하다는 보고가 있다 — 추측). 그 밖의 모든 논리(설정·명령·주소·감독·문구·뷰 모델)는 Tk 없이 pytest로 돈다. 기준 pytest 수에 "+N skip" 주석.
- **실프로세스 테스트**는 기존 `tests/server/test_server_cli.py`의 두 테스트 방식(`sys.executable -u -m dune_imperium.cli.server`, `importorskip("uvicorn")`, `/catalog` 폴링)을 따른다. 성공 판정은 종료 시간·포트 해제이고 종료 코드는 stdin EOF 경로에서만 0을 단언한다. 포트는 `_free_port()`를 쓰되 bind 실패(체크아웃 둘에서 동시에 돌릴 때의 충돌)는 한 번 다시 고른다; "빈 포트 찾기"는 포트 0으로 bind한 번호를 쓴다.
- **E2E**: `scripts/e2e/launcher_link.py`(6단계)는 런처 모듈을 직접 import하지 않고 프로젝트 `.venv`의 python을 `--start --print-link`로 자식으로 쓴다(e2e venv는 Playwright만). GUI 자체의 E2E는 자동화하지 않고 8절 체크리스트로 대신한다.
- **mypy --strict**: tkinter·ttk는 typeshed 스텁이 있다. `ctypes.windll`·`subprocess.CREATE_NO_WINDOW`·Job Object는 `if sys.platform == "win32":` 분기 안; `Popen[bytes]`·`queue.Queue[str]` 제네릭. 7단계에서 Windows의 `uv run mypy src tests`와 Mac의 `mypy --platform win32 src/dune_imperium/launcher`.
- **ruff**: 기존 규칙(B,E,F,I,UP). `print` 금지는 테스트 하나로 가드(`cli.py`의 가드된 `sys.stdout.write`만 허용).
- **검증 등급**(CLAUDE.md "scale the checks to the risk"): 1단계만 독립 리뷰(서버 종료·자동 저장 경로). 나머지는 주 세션이 diff를 읽는다. 전체 pytest·ruff·mypy·`run_all.py`는 묶음 끝(병합 전)에 한 번.

## 8. 검증 체크리스트

**macOS(Mac mini, 6단계)**: `.app` 더블클릭 → 창이 앞에 뜸(Dock 이름 확인) → 원격 모드, Tailscale 후보가 `/Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4`(또는 앱 메뉴의 주소)와 같음 → [시작] → 관리자 링크가 브라우저에서 열리고 호스트 패널이 보임 → 게임 생성 → **다른 기기**에서 방 링크 입장(방화벽 판정은 이것뿐) → `pmset -g assertions`에 caffeinate → 창 닫기 확인 창 → `saves/`에 자동 저장 → 재시작 후 불러오기 → `tmp/launcher/`에 로그(링크 마스킹 확인). 런처를 `kill -9`한 뒤 서버가 몇 초 안에 스스로 내려가는지. 한글 라벨 표시와 Entry에 한글 2벌식 입력. 다크 모드. 마우스 없이 시작~링크 복사~중지.

**Windows(14700K, PowerShell 네이티브, 7단계)**: `uv --version`(≥ 0.12.2 권장 → Tk 9.0.4; 아니면 8.6.14도 지원), `uv python install 3.14`, `uv sync --locked --inexact --extra ui --extra train`; `uv run python -m tkinter`와 `tkinter.TkVersion`; `dir .venv\Scripts\pythonw.exe`와 `dune-imperium-launcher.exe`(확인용); exe 더블클릭으로 콘솔 없이 창이 뜸(**`uv run`으로 띄우지 말 것**); `.venv\Scripts\python.exe -m dune_imperium.launcher.cli --check`가 콘솔에 출력하고 `dune-imperium-launcher.exe --check`는 출력 없이 종료 코드만 주는지 기록; 150% 배율에서 선명함; 한글 라벨·IME 입력; `import torch`; 서버 시작 뒤 `Get-CimInstance Win32_Process | ? ParentProcessId -eq <server.pid>`로 리디렉터 → 기반 `python.exe` 사슬과 `sys.executable` 값을 기록, 리디렉터만 `Stop-Process`했을 때 기반 프로세스가 따라 죽는지; 로컬 모드 시작 때 방화벽 팝업 없음(예상)·원격 모드 첫 시작 때 팝업 → 허용 후 **다른 기기** 접속; `Get-NetFirewallRule -Direction Inbound | Get-NetFirewallApplicationFilter`로 규칙의 Program 경로 기록(`.venv`가 아니라 `uv python dir` 아래여야 함; junction 경로인지 풀린 패치 폴더인지), `.venv`를 지우고 `uv sync`한 뒤 팝업이 다시 뜨지 않는지(예상: 안 뜸); `where tailscale`과 후보 목록이 `Get-NetIPAddress`와 맞는지, 보조 자식 호출 때 콘솔이 번쩍이지 않는지; [중지]가 3초 안에 끝나고 포트가 풀림, 실제 종료 코드 기록; SSE 탭이 열린 채 중지; 작업 관리자로 런처 `pythonw.exe`를 강제 종료 → 몇 초 안에 서버 두 프로세스가 사라지고(Job Object 하드 킬; 정상 종료 메시지는 기대하지 않는다) 포트가 풀리며 `saves/`에 `*.tmp`가 없음, 재시작 후 자동 저장을 불러올 수 있음; `powercfg /requests`에 SYSTEM 항목, 중지 뒤 사라짐; `test_a_port_somebody_listens_on_is_a_bind_problem`이 Windows에서 통과; 한글·공백이 든 체크아웃 경로; 비관리자 프롬프트에서 `mklink /J assets ..\Dune-Imperium-assets`가 되는지(가이드용); `uv run pytest -q`, `ruff`, `mypy`; 브라우저 탭 여러 개 열고 닫기·잠자기 복귀 뒤 재접속(`[WinError 64]` 재현 여부).

## 9. 사용자 결정 (2026-10-09 확정: "추천대로 가자" — 아래 15개 모두 추천안)

1. **형태**: tkinter 창(추천, 3절). 트레이·웹 런처·Qt 번들·GUI 없는 안은 기각 사유와 함께 10절에 남긴다.
2. **설정 파일 위치**: `local/launcher.json`(추천; 기기별 파일 한 폴더, `.gitignore` 한 줄) vs `settings/launcher.json`.
3. **관리자 키 기본값**: "고정"(추천 — 매번 같은 관리자 링크를 즐겨찾기할 수 있다; 평문은 git 무시 폴더 안, 0o600) vs "매번 새로"(공유 PC).
4. **창 닫기**: 서버가 켜져 있을 때만 확인 창(진행 중 게임 수·"지금 저장" 권고)(추천) vs 묻지 않고 종료.
5. **더블클릭 산출물**: macOS `.app` 번들, Windows gui-scripts exe + `.lnk`, 모두 프로젝트 폴더 안(추천). 바탕화면 복사는 규칙 예외라 하지 않는다(사용자가 끌어다 놓는다).
6. **첫 설치 스크립트**(`scripts/launcher/Install Launcher.{command,cmd}`) 포함 여부 — 추천: 포함(4단계; 터미널은 처음 한 번만).
7. **잠자기 방지 기본값**: 원격 모드 자동 켬(추천).
8. **브라우저 자동 열기**: 로컬 모드는 테이블, 원격 모드는 관리자 링크(호스트 자기 브라우저)(추천) vs 복사만.
9. **5단계(방 링크 목록·이전 서버·다시 시도) 포함** — 추천: 포함(원격 운영에서 가장 잦은 동작이 "방 링크 보내기").
10. **에셋 경로 전달**: 런처가 환경 변수 5개를 파생(서버 무변경, 추천) vs 서버에 `--assets-dir` 추가.
11. **런처 안 [환경 준비] 버튼**(uv를 찾아 `uv sync`를 돌리고 출력을 로그 창에) — 추천: 1차 범위 밖(첫 설치는 어차피 터미널; 10절 "나중 선택지"). 대신 사전 검사가 정확한 명령을 보여 준다.
12. **Windows 검증 방식**: 14700K PC에서 Claude 세션을 열어 7단계를 맡김(추천) vs 사용자가 체크리스트를 직접 수행하고 결과만 넘김.
13. **표시 이름**: `Dune Imperium Server`(ASCII, 추천) vs 한글 이름.
14. **Windows에서 런처가 crash했을 때의 서버**: Job Object `KILL_ON_JOB_CLOSE` 유지(추천 — 런처가 어떻게 죽어도 고아가 없고, 자동 저장이 원자적이라 잃는 것은 진행 중 턴뿐) vs `KILL_ON_JOB_CLOSE`를 빼고 Job은 [중지] 사다리의 `TerminateJobObject` 용도로만 두어 crash 때도 stdin EOF 정상 종료를 기다림(감시 스레드가 멈추면 고아가 남는다).
15. **런처 언어**: 한국어만(추천; `texts.py`가 표라 영어 열을 나중에 더할 수 있음) vs 웹 UI처럼 한국어/English 전환.

## 10. 범위 밖·나중 선택지·기각 (다시 꺼내지 않기 위해)

| 항목 | 상태 | 까닭 |
|---|---|---|
| 메뉴바/트레이 상주(rumps·pystray) | 기각 | 유지보수 중단 라이브러리, pystray는 macOS 26에서 SIGTRAP(#195). 정말 필요해지면 pyobjc `NSStatusItem` 직접 호출로 재검토 |
| PySide6·pywebview 창 | 기각 | PySide6-Essentials 82~116 MB; pywebview는 Windows pythonnet·macOS pyobjc를 끌어오고 3.14 classifier 없음 |
| PyInstaller/py2app 독립 번들 | 나중 선택지 | 3.14 지원은 있으나(PyInstaller 6.15+, py2app 0.28.9+) OS별 빌드·서명 없음·torch 포함 시 0.5 GB+. "탐색 AI 없는 경량 번들"만 후보 |
| `.command`를 본선 더블클릭으로 | 기각 | Terminal 창이 뜬다(사용자가 불편하다고 한 것) |
| 서버 웹 UI 안의 호스트 설정 패널·`/host/*`·종료 코드 재시작 프로토콜 | 기각 | 서버가 "누가 띄웠는가"를 알게 되는 결합; 이미 빽빽한 시작 화면(2026-10-06 플레이 피드백); 종료 코드 프로토콜은 uvicorn 재발신과 충돌 |
| `/whoami`에 탐색 AI 사유 문자열(`search_ai_note`) | 기각 | 콘솔 문자열은 켜졌을 때도 꺼졌을 때도 호스트의 절대 경로를 담아 경로 비노출 약속(`test_remote_app.py`)을 깬다. 런처가 `resolve_search_checkpoint`를 직접 부른다 |
| 런타임 프로세스 트리에 `uv run` 끼우기 | 기각 | 중간 프로세스(Windows uv.exe는 CTRL_BREAK를 전달하지 않음, gui-scripts는 #20100으로 즉시 종료) |
| 서버 `--print-admin-link-json` 같은 기계용 출력 | 서버에는 불필요 | 키·주소·포트를 런처가 정하고 `/whoami`로 확인하므로. E2E·검증용 기계 출력은 런처 CLI의 `--start --print-link`가 맡는다 |
| 새 설정으로 안 뜨면 `last_good`으로 자동 재시작 | 기각 | 호스트가 친구에게 보낼 링크가 몰래 바뀐다. 버튼으로만(5.4) |
| 두 번째 더블클릭 때 기존 창을 앞으로(127.0.0.1 소켓 노크) | 나중 선택지 | 창 올리기만을 위해 제어 포트·프로토콜·테스트가 든다. "이미 실행 중입니다" 안내로 대신 |
| 런처 [환경 준비] 버튼(uv sync 대행) | 나중 선택지 | 결정 11 |
| 런처가 `git pull`·업데이트 확인 | 범위 밖 | 저장소 업데이트는 터미널(가이드 6절: 판 중에는 업데이트하지 않는다). 업데이트 뒤 옛 저장 호환은 가이드 6절 그대로(런처가 미리 알 수 없다) |
| WSL2 호스트 | 범위 밖 | 창이 안 뜨고 NAT 뒤(호스트 가이드 1절) |
| 심볼릭 링크 만들어 주기 버튼 | 기각 | Windows 권한 문제; 경로 설정으로 대체 |
| 공개 인터넷 노출·터널 자동화 | 범위 밖 | 멀티플레이 설계 8절(비공개 망만) |

## 11. 위험

- Windows 쪽 추정(DPI·글꼴, 방화벽 팝업 조건과 규칙 경로, 리디렉터 사슬의 실제 모습, CTRL_BREAK 종료 코드)은 7단계 전에는 알 수 없고, 7단계는 사용자가 Windows PC를 열어 주어야 진행된다. 대체 경로는 모두 적어 두었다.
- Windows에서 런처가 crash하면 서버는 정상 종료가 아니라 Job Object 하드 킬로 끝난다. 자동 저장의 원자성(`os.replace`)에 기대며, 진행 중 턴은 사라진다(macOS는 stdin EOF로 정상 종료).
- GUI 코드는 헤드리스에서 skip된다. 폼·버튼 회귀는 Mac mini의 pytest와 체크리스트에만 걸린다. 그래서 뷰 모델을 순수 데이터로 분리한다.
- tkinter에는 트레이·알림·스크린 리더 지원이 없어 창을 닫으면 서버도 끝난다(최소화만 가능). 외관은 네이티브 앱보다 투박하다.
- `[WinError 64]`(CPython #93821)는 3.14에서도 재현될 수 있다. "다시 시작" 버튼과 자동 저장 복구 절차가 대응이다.
- 관리자 키 "고정"은 프로젝트 폴더 안 JSON에 평문으로 남는다(git 무시).
- `.app`/`.lnk`는 `.venv` 경로에 기대므로 Python 버전 변경 등으로 venv가 재생성되는 동안 깨진다(재동기화 후 정상). 방화벽 규칙은 uv 기반 인터프리터 경로 기준이라 `.venv` 재생성은 영향이 없지만 기반 Python 폴더가 바뀌면 다시 물을 수 있다(미확인).
- 런처는 체크아웃마다 하나라, worktree에서 띄우면 그 worktree의 빈 `saves/`·없는 체크포인트·없는 에셋으로 뜬다(기존 설계; 상태 줄이 "탐색 AI 꺼짐·그림 없음"을 말한다). 기본 포트 8000은 `.claude/launch.json`의 `ui-server`와 같으니 "다른 서버가 떠 있음" 안내와 [빈 포트 찾기]가 대응이다.
- 서버 1단계 변경은 작지만 종료·자동 저장 경로라 독립 리뷰를 둔다.

## 12. 갱신할 문서 (6단계)

- [`remote-play-host-guide.md`](remote-play-host-guide.md): 2절 뒤에 "런처로 실행" 절(설치 스크립트 더블클릭 → 바로가기 → 창 설명 → 링크 복사; 업데이트 뒤 옛 저장은 6절 그대로), 1절 "서버 터미널을 열어 두고" → "런처 창(또는 터미널)을 열어 두고; 런처 창을 닫으면 서버도 꺼지고 최소화는 괜찮다", 3·4절의 명령은 "터미널로 실행할 때"로 유지, `caffeinate` 문장은 체크박스로, 5절 옵션 표에 `--exit-when-stdin-closes`(파이프 조건), 6절 종료 절차에 [중지]/창 닫기 확인 창, 7절 문제 해결 표에 런처 문구와 "서버 연결 끊김" 행에 "호스트가 런처 창을 닫지 않았는지", Windows 절에 `mklink /J`·사용자 프로필 아래 체크아웃·방화벽 규칙 경로, 1절의 Windows 미검증 문장은 7단계 결과로.
- [`remote-play-guide.md`](remote-play-guide.md): 역할 표의 호스트 안내 내용에 "런처".
- `README.md` 개발 환경 항목에 `dune-imperium-launcher` 한 줄, `local/`·`tmp/launcher/` 설명.
- `scripts/e2e/README.md`: `launcher_link.py` 설명·소요 시간(`run_all.py` `SECONDS`는 선택).
- `CLAUDE.md` "Verifying UI changes" 절에 런처 한 줄(tkinter 런처는 낮음, `supervisor`의 서버 종료 경로는 고위험).
- [`multiplayer-design.md`](multiplayer-design.md) 8.3 호스트 머신에 런처 한 줄.
- [`implementation-plan.md`](implementation-plan.md) M14 뒤에 "M14+ 런처" 항목(병합 때), [`development-handoff.md`](development-handoff.md)는 병합 때만.

## 13. 구현 기록 (2026-10-09)

1~6단계를 이 순서로 커밋했다. 테스트는 `tests/launcher/`(175개; 창 테스트는 디스플레이가 없거나 `DUNE_IMPERIUM_SKIP_GUI_TESTS=1`이면 skip)와 `tests/server/test_server_cli.py`, 브라우저 E2E는 `scripts/e2e/launcher_link.py`(16개 확인).

| 단계 | 커밋 | 검증 |
|---|---|---|
| 1. 서버 CLI | `7f546a71` | 독립 리뷰(3관점 + 반박) — 아래 1 |
| 2. 런처 코어 | `58e09008`, 리뷰 반영 `ec60096c` | 독립 리뷰(2관점 + 반박) — 아래 2 |
| 3. 창 | `4f70c976`, `fa4019c3` | 숨긴 창으로 실제 기동·중지; 화면 캡처는 이 기기에 화면 기록 권한이 없어 못 함 |
| 4. 잠자기 방지·바로가기·설치 스크립트 | `f69f8f76` | `.app`을 LaunchServices(`open`)로 열어 이 체크아웃의 창이 뜨는 것까지 확인 |
| 5. 게임 목록·다시 시도·중복 실행 | `b70039c6` | — |
| 6. 문서·E2E | 이 문서와 같은 커밋 | `launcher_link.py` 16/16 |
| 7. Windows 실기 검증 | **남음** | 8절 체크리스트(아래 추가 항목 포함) |

**계획과 달라진 점:**

1. **1단계 리뷰가 잡은 결함.** 감시 스레드가 `sys.stdin.buffer.read()`로 막혀 있으면 BufferedReader 락을 쥔 채라, 파이프가 열린 채 Ctrl+C·시작 실패로 끝날 때 인터프리터가 종료 중 `Fatal Python error: _enter_buffered_busy`로 abort했다(-6, 재현함). 감시는 `os.read(fd)`로 읽는다. bind 프로브는 `SO_REUSEADDR`만이 아니라 asyncio `create_server`와 같은 방식(이름의 모든 주소를 한꺼번에, IPv6는 `V6ONLY`, 없는 주소는 건너뜀)으로 바꿨다: `localhost`는 127.0.0.1과 ::1 중 하나만 비어 있어도 통과했었다.
2. **2단계 리뷰가 잡은 결함.** 런처의 HTTP 요청이 `http_proxy`·시스템 프록시를 따라 관리자 키 쿠키가 프록시로 갈 수 있었다 → 모든 요청을 프록시 없이(`ProxyHandler({})`). 준비 확인이 같은 포트의 다른 서버(macOS는 0.0.0.0 bind가 127.0.0.1 서버 옆에서도 된다)를 자기 서버로 믿을 수 있었다 → 쿠키 없이 먼저 묻고 `access`가 모드와 맞을 때만 키를 보낸다. 서버가 띄운 손자 프로세스가 출력 파이프를 쥐면 중지가 끝나지 않았다 → 파이프는 리더 스레드만 닫는다. stderr를 읽지 않는 호출자 아래서 `--start`가 멈출 수 있었다 → 서버 줄은 로그 파일로만. 그 밖에 BOM 붙은 설정 파일, HTTP가 아닌 응답, 동시 `stop()`, Windows 가상 어댑터를 LAN으로 보이는 문제를 고쳤다. 커밋 `ec60096c`에 목록이 있다.
3. **`/whoami`는 바꾸지 않았다.** 탐색 AI가 꺼진 까닭은 런처가 같은 venv에서 `resolve_search_checkpoint`를 불러 얻는다(계획 리뷰가 경로 노출을 막았다).
4. **콘솔 옵션**: `--check`, `--start`(준비되면 `{"open_url", "room_base", "pid", "port", "access", "search_ai", "log"}` JSON 한 줄, stdin이 끝나면 `{"stopped", "seconds", "port_free"}` 한 줄; `--print-link`는 따로 두지 않았다), `--make-shortcut`, `--settings`, 숨은 `--log-dir`(테스트·E2E가 호스트의 `tmp/launcher`를 건드리지 않게). `--no-browser`는 두지 않았다.
5. **모듈**: 계획의 표에 `controller.py`(작업 스레드·상태 전이·이벤트; Tk 없이 테스트), `view.py`(무엇을 켜고 무엇이라 말할지; 순수 함수), `instance.py`(중복 실행 잠금)가 더해졌고, `texts.py`는 만들지 않았다(문구는 각 모듈 안에 한국어로).
6. **"이전 서버에 붙기/끄기"와 `server.pid`는 뺐다.** 런처가 띄운 서버는 런처보다 오래 살 수 없다(stdin 파이프, Windows Job Object). 그래서 포트에 떠 있는 서버는 남의 것이고, 시작 전 검사가 그렇게 말한다. 두 번째 더블클릭은 `tmp/launcher/launcher.lock`의 배타 잠금(프로세스가 어떻게 끝나든 시스템이 푼다)으로 막는다. pid 파일은 재사용된 pid를 가리킬 수 있고, Windows의 `os.kill(pid, 0)`은 그 프로세스를 끝내 버린다.
7. **서버 자식은 POSIX에서 자기 세션**(`start_new_session`)을 갖는다: 터미널의 Ctrl+C·창 닫기(SIGHUP; uvicorn은 처리하지 않는다)는 런처만 받고, 서버는 stdin이 닫히는 한 길로만 끝난다.
8. **잠자기 방지 기본값**은 두 모드 모두 켬(원격만이 아니라).
9. **창 배치**: 한 열로는 요구 높이가 945px라 1280×800 노트북에서 로그 칸이 사라졌다. 설정은 왼쪽, 실행·링크·게임 목록·로그는 오른쪽의 두 열, 기본 1000×640.
10. **`last_good`**은 버튼("이전 설정(주소:포트)으로 다시 시도")으로만 쓴다. 방 링크가 몰래 바뀌면 안 된다(계획 리뷰).
11. **Windows `pythonw` 확인**: uv venv에는 `pythonw.exe`가 늘 생기므로 `ShowWindow` 대체 경로는 만들지 않았다.

**7단계에 더할 확인(8절 Windows 체크리스트에 덧붙임):** 파이프를 연 채 서버 콘솔에 Ctrl+C/CTRL_BREAK가 가도 `Fatal Python error` 없이 끝나는지; 시스템 프록시를 켠 채 런처가 시작·게임 목록을 정상으로 하는지; `mypy --platform win32 src/dune_imperium/launcher`(이 Mac에서는 통과); Job Object 구조체가 실제로 붙는지(`AssignProcessToJobObject` 실패 시 로그에 "Job Object를 만들지 못했습니다"); `Install Launcher.cmd`가 CRLF로 체크아웃되는지; `.lnk`가 한글·공백 경로에서 만들어지는지.

