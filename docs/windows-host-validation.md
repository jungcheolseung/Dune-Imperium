# Windows 플레이 서버 검증

2026-10-12, WSL2에서 Windows PowerShell을 호출해 **Windows 네이티브 Python·Tk·Chrome**으로
검사했다. 서버와 런처는 Windows에서 실행했다. WSL 서버에 Windows 브라우저만 연결한 검사가 아니다.

## 현재 PC에서 실행

준비한 저장소는 `C:\Users\qwer\workspace\tabletop-ai\Dune-Imperium`이다. 이 폴더의
**Dune Imperium Server.lnk**를 더블클릭한다.

1. 혼자 두려면 **이 컴퓨터에서만 (로컬)** → **시작**을 누른다.
2. 열린 브라우저에서 사람 1명과 앱 AI 세 좌석으로 게임을 만든다. 어려움·보통·쉬움을 고를 수 있다.
3. 친구와 두려면 런처를 중지하고 **다른 사람과 (원격)**을 고른다. LAN 또는 Tailscale 주소를 선택한다.
4. 관리자 화면에서 사람·AI 좌석을 설정하고 게임을 만든 뒤 **방 링크**를 참가자에게 보낸다.
5. 끝낼 때는 게임을 저장하고 런처에서 **중지**한다. 런처 창을 닫아도 서버가 종료된다.

이 체크아웃의 Python·의존성은 Windows 폴더 안에 있어 서버 실행에 WSL이 필요하지 않다.
테스트용 uv·MinGit은 `tmp/windows-tools/`, Python은 `local/python/`, 의존성은 `.venv/`에 있다.
시스템 PATH나 방화벽 설정은 바꾸지 않았다. 이 테스트 환경에서 추가 동기화가 필요하면
PowerShell에서 다음처럼 명시적인 경로를 쓴다.

```powershell
cd C:\Users\qwer\workspace\tabletop-ai\Dune-Imperium
$env:UV_PYTHON_INSTALL_DIR = "$PWD\local\python"
$env:UV_CACHE_DIR = "$PWD\tmp\uv-cache"
& .\tmp\windows-tools\uv.exe sync --locked --extra ui --extra rl --extra train
```

다른 호스트 PC는 [호스트 가이드](remote-play-host-guide.md)의 uv 설치 → clone →
`Install Launcher.cmd` 순서로 준비한다. **참가자에게는 저장소·Python·AI 파일이 필요 없다.**
다른 장소에서 접속할 때는 Tailscale 준비와 호스트 공유가 필요하다
([참가자 가이드](remote-play-player-guide.md)).

검증용 체크아웃에는 이미지와 학습한 탐색 AI 체크포인트를 복사하지 않았다. 이미지는
[로컬 이미지 안내](local-images.md)에 따라 호스트의 그림 폴더를 선택한다. 이미지가 없으면 텍스트로
플레이할 수 있다. 앱 AI에는 체크포인트가 필요 없다.

## 확인한 범위

| 항목 | 결과 |
| --- | --- |
| 운영체제·런타임 | Windows 11 Pro 10.0.26100, uv 0.12.3, Python 3.14.7, Tk 9.0.4, PyTorch 2.14.0+cpu |
| 설치·주소 | `uv sync --locked --extra ui --extra rl --extra train` 성공. Tk 창 생성·torch import·LAN/Tailscale 후보 검색 성공 |
| GUI → 서버 | 실제 Tk 시작·중지 버튼으로 로컬·원격 서버 실행. 정상 종료 코드 0·포트 해제. 회귀 테스트 2개 추가 |
| 런처 실행 파일 | 설치된 GUI exe 실행 뒤 `Dune Imperium 서버` 창 제목 확인. exe → `.venv/Scripts/pythonw.exe` → `local/python/.../python.exe` 프로세스 사슬 관찰(외관·콘솔 노출은 직접 관찰하지 못함) |
| 런처·서버 pytest | 첫 실행 780 통과·10 skip·6 실패. 실패는 링크 권한 5건과 테스트의 HOME 설정 1건. 수정한 모듈 재검사 149 통과·8 skip |
| Windows 품질 검사 | `ruff check src tests`, `mypy src tests`(482파일) 통과 |
| 플랫폼 API 회귀 | Windows 31 통과·3 skip. 프로세스 감독·컨트롤러·기보 검사 우선순위 |
| 런처 링크 E2E | Windows Chrome 17 통과. 방 생성·다른 브라우저 좌석 참여·런처 게임 목록·stdin 종료·키 마스킹 |
| 앱 AI E2E | Windows Chrome 63 통과. 세 난이도 상대와 게임 완주·중간 저장/불러오기·한영 표시·1366×768 좌석 배지 |
| 원격 E2E | Windows Chrome 61 통과. 별도 브라우저의 참여·수 갱신·재접속·권한 검사 |
| 복구 E2E | Windows Chrome 33 통과. 서버 강제 종료·자동 저장 복구·다시 참여·후속 플레이 |
| Windows 주소 접속 | Windows 서버를 Tailscale 주소에 열고 WSL에서 `/whoami` HTTP 접속 성공. 종료 0.40초·코드 0·포트 해제 |
| POSIX 회귀 | WSL 전체 7,485 통과·9 skip. 추가/수정한 모듈 154 통과·3 skip, 플랫폼 API 관련 73 통과. 런처 링크 E2E 17 통과 |

전체 pytest는 GUI 회귀 2개를 더하기 전에 시작한 결과다. 최종 수집은 **7,496개**다.
Windows 전체 엔진 pytest나 E2E 전체 62종을 실행한 것은 아니다.

심볼릭 링크 전용 테스트는 Windows 계정에 권한이 없을 때만 skip한다(WinError 1314).
일반 파일 선택과 게임 플레이를 위해 관리자 실행이나 Developer Mode를 켤 필요는 없다.
홈 경로 테스트는 Windows의 `USERPROFILE`도 설정하고, Unix 전용 `os.nice`·`SIGKILL` 참조는
Windows 정적 검사에 맞게 정리했다. 게임 규칙·codec·저장 형식은 바뀌지 않았다.

Windows 결과 로그는 이 체크아웃의 `tmp/native-*.log`, 브라우저 산출물은 `tmp/e2e/`에 있다.
WSL 실행 결과는 WSL 체크아웃의 `tmp/windows-*.log`에 있다. 모두 git이 무시한다.

## 아직 필요한 실사용 확인

- 다른 **물리 PC**, 특히 다른 집의 참가자가 방 링크로 접속하는 것. 같은 PC의 WSL 접속은 WAN 검증을 대신하지 않는다.
- 런처 바로가기를 직접 더블클릭했을 때의 외관, 150% 배율, 한글 IME 입력, 키보드 탐색.
- 원격 시작 시 방화벽 안내와 실제 규칙의 Python 경로, `.venv` 재생성 뒤 동작.
- GUI 런처 자체를 강제 종료한 뒤 고아 서버가 남지 않는 것, 잠자기 방지 요청의 해제.
- 장시간 플레이·잠자기/네트워크 전환 뒤 복귀.
- 실제 학습 체크포인트로 탐색 AI를 두는 것(이번 검사에는 앱 AI만 사용).

따라서 서버 런처 계획 7단계는 **Windows 기능 검증 완료, 수동·외부 기기 확인 남음**으로 기록한다.
