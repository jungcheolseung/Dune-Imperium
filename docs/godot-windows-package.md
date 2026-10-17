# Windows 설치 없는 Godot 시제품

사용자 결정(2026-10-14): 플레이 컴퓨터에 Python·uv가 없으며 앞으로도 설치를 전제로 하지 않는다.
개발용 Git bundle 대신 **ZIP 전체를 풀고 더블클릭하는 폴더 배포본**을 제공한다.
작업은 `docs/godot-client-plan` 브랜치에만 남긴다.

## 실행

1. ZIP 전체를 바탕 화면 등 쓰기 가능한 폴더에 압축 해제한다.
2. `Dune-Uprising-Prototype/Play Dune.cmd`를 더블클릭한다.
3. **새 게임**에서 좌석·규칙 옵션을 고른 뒤 **게임 시작**을 누른다.
   기본판 또는 기존 웹 기본 옵션을 선택할 수 있다.

Python·uv·Git·Godot의 설치, 터미널 명령, 첫 실행 다운로드가 필요하지 않다.
첫 실행은 포함된 한글 글꼴을 준비하고 게임 창을 연다. 콘솔은 계속 띄워 두지 않는다.
창을 닫으면 이 실행이 시작한 로컬 서버도 종료한다.

**저장 / 이어하기**는 배포 폴더의 `saves/`를 사용한다. 새 버전은 별도 폴더에 풀고 기존 폴더와
저장본을 보관한다. 저장본을 직접 열 수 있는지는 서버의 저장 codec 버전이 같은지에 달려 있다.
문제 기록은 같은 폴더의 `tmp/godot/start.log`, `process.log`, `client.log`, `import.log`, `server/`에 있다.
플레이 조작은 [시제품 안내](godot-prototype-guide.md)의 조작 절을 따른다.

## 2026-10-18 전체 패키지와 저장 호환

`dune-uprising-windows-personal-20261018-v148.zip`은 최신 master 뒤로 리베이스한 Godot
브랜치의 개인용 전체 패키지다. Python 게임 서버·Godot·서버 의존성과 소유자의 그림 캐시를
포함한다. 압축을 모두 풀고 `Dune-Uprising-Prototype/Play Dune.cmd`를 실행한다.
이 실행기가 서버를 먼저 시작하고 게임 창을 연결하며, 창을 닫으면 서버도 종료한다.

현재 서버의 저장 codec은 **v148**이다. 이전 Windows 패키지의 **v145 저장본은 직접 열리지
않으므로**, 이번 전체 패키지는 새 폴더에서 새 게임으로 시작한다. 이전 폴더와 `saves/`는
그대로 보관한다. 아래 작은 업데이트들과 그 검증 수치는 리베이스 전 v145 배포본의 기록이다.

소스 `37041aa1`(깨끗한 작업 트리), ZIP 244,857,809 bytes(**233.51 MiB**), 압축 해제 후
364,857,198 bytes(**347.95 MiB**). SHA-256:
`3c9fca6a9b7ff9b44aa60bb08aa035da50449ea6d8f1e6467793c4ebc7e86933`.
산출물은 메인 체크아웃의 `tmp/godot/`에 있으며 같은 이름의 `.zip.sha256`도 둔다.

ZIP CRC·manifest 2,412파일의 SHA-256·Windows x64 PE 35개·고정 서버 의존성 13개를
확인했다. 한글·공백 경로에 풀어 동봉한 Windows Python 3.14.7의 `pythonw.exe`로 실제
Godot을 headless 실행했다. Python·uv·pip·pytest·Torch·NumPy의 별도 설치 없이 서버 자동
시작→Agent 배치→undo→턴 진행→AI 차례 복귀(revision 18, undo 1)→stdin 정상 종료와 포트
반환을 통과했다. 같은 동봉 Godot의 모델 검사 137개·배율 검사 27개도 통과했다.
근거는 `tmp/godot/windows-v148-validation/`의 manifest 검증 JSON, Windows smoke JSON,
모델/배율 로그다. 이번에는 Windows 그래픽 화면·직접 조작·완주·LAN을 다시 검사하지 않았다.

## 작은 플레이 업데이트

최신 `dune-uprising-windows-panels-update-20261015.zip`(2.83 MiB)은 확장 시장·연구·Scouts와
카드 상세/더미 보기를 개선한 누적 프로그램 업데이트다. 프로그램 전체를 포함하므로 앞선
작은 업데이트를 순서대로 적용할 필요가 없다. 기존 개인용 전체 묶음(Python 3.14.7 / Godot
4.6.3)에 적용한다. 게임을 닫고 ZIP 안의 `Dune-Uprising-Prototype`을 기존 같은 이름 폴더의
**상위 폴더**에 풀어 병합/덮어쓴 뒤 기존 `Play Dune.cmd`로 실행한다.
`runtime/assets/saves/local`은 포함하지 않으며, 처음 설치할 때는 전체 묶음이 필요하다.

소스 `3b602af2`, 2,962,531 bytes, SHA-256
`66ae294a46db6b76396a148d39d017bbf7b3a4e75438600093d1700428cb58f1`.
직전 화면 업데이트의 보존 복사본(`1e1ee943`)에서 프로그램 353파일 hash를 먼저 확인하고,
새 ZIP의 프로그램 357파일과 적용 후 복사본의 hash·저장/설정 보존·최소 환경 스모크를 검증했다.
기존 manifest에 overlay한 목표 파일 목록은 2,399개다. 이번에는 이전 전체 ZIP들이 작업 환경에
없어 아카이브 전체를 다시 검사하지 않았다. 다른 PC의 동명 재빌드본 전체 manifest와의 일치도
검증한 결과가 아니다. 근거는 `tmp/godot/panels-update-report.json`과 ZIP의 `update-manifest.json`이다.
새 화면의 Windows 실제 GPU/IME/소리는 후속 실기 범위다.

앞선 `dune-uprising-windows-visual-update-20261015.zip`(253.13 KiB)은 카드 가독성과
기본 테이블 배치를 개선한 누적 프로그램 업데이트다. 손패 크기·시장 이름/인쇄 비용·체크 표식,
빈 손패 접기·현재 선택/턴 종료 강조와 이전 기능·정보·배율/선택창 보완을 포함한다.
게임을 닫고 ZIP 안의 `Dune-Uprising-Prototype`을 기존 같은 이름 폴더의 **상위 폴더**에 풀어
병합/덮어쓴 뒤 기존 `Play Dune.cmd`로 실행한다. `runtime/assets/saves/local`은 포함하지 않는다.
처음 설치할 때는 전체 v3 ZIP이 필요하다. 저장한 열 너비가 있으면 **메뉴 → 플레이 설정 →
개인 배치 초기화**로 새 기본 배치를 적용한다(개인 손패 정렬도 초기화한다).

이 PC의 v1/v2/v3 전체본과 플레이·정보 업데이트에 적용한 2,395파일 hash를 검증했다.
소스 기준은 `1e1ee943`, ZIP SHA-256은 `2a1b68e6d8b910aa3abad26c54f4f6fe15c0d3f3cc515754994495d868b025c0`이다.
`tmp/godot/visual-update-report.json`에 검증한 각 기준 ZIP의 SHA-256도 기록했다.
다른 PC가 같은 파일명으로 다시 만든 전체본은 별도 기준이다. 이 결과를 그 ZIP의 전체
manifest 일치 검증으로 읽지 않는다. 전체본의 런타임·그림을 새로 복사하거나 공개 배포하지 않았다.

`dune-uprising-windows-scaling-update-20261014.zip`은 다른 PC에서 재빌드한
`dune-uprising-windows-personal-20261014.zip`(SHA-256
`2ca2e23e674ba8c09d1ad62bd260e28e2a2bb8e4fcedb410364b5c0c54fd8f53`)에 적용하는
화면 배율 업데이트다. 이 PC의 동명 이전 전체본과 구별한다.
모니터 해상도·시스템 배율에 따라 글씨·버튼·카드·팝업을 함께 확대한다.
시스템 배율 100% 기준 FHD 100% / QHD 125% / 4K 200%이며, 창 크기와 모니터 변경에도
다시 맞춘다. 게임을 닫고 업데이트 안의 `Dune-Uprising-Prototype`을 기존 같은 이름 폴더의
상위 폴더에 풀어 병합/덮어쓴 뒤 `Play Dune.cmd`로 실행한다. 저장·설정·그림은 보존한다.

이전 `dune-uprising-windows-information-update-20261014.zip`은 개인용 v1/v2/v3의 프로그램을
갱신한다. 앞서 받은 `dune-uprising-windows-play-update-20261014.zip` 적용 여부와 관계없이 쓴다.
실행 중인 창을 닫고 ZIP 안의 `Dune-Uprising-Prototype`을 기존 같은 이름 폴더의 **상위 폴더**에
복사해 같은 파일을 덮어쓴다. 기존 `Play Dune.cmd`로 다시 실행한다.
`Dune-Uprising-Prototype` 안에 같은 이름 폴더를 한 번 더 만들지 않는다.

이번 업데이트는 앞선 배치·접목·확정 선택 개선에 덱 맨 위 표시·Controlled 그림/이름,
병력 수량 기본값·경매 턴 종료 확정과 정보창의 갱신/닫기·좁은 화면 보정을 더한다.
`runtime/`, `assets/`, `saves/`, `local/`은 포함하지 않는다.
처음 설치할 때는 전체 v3를 먼저 풀고 최신 업데이트를 적용한다.

## 새 기능 사용

**메뉴 → 플레이 설정**에서 한국어/영어, AI 속도, 연출·효과음·음량을 고른다.
손패/책략 순서는 드래그로, 열 너비는 열 사이 드래그로 저장한다.
초암·Bloodlines·Tech·Immortality·Epic·Scouts는 새 게임의 규칙 옵션에서 설정한다.
공용 카드 열과 테이블 상세에서 확장 시장·연구 보드·지도자 상태·교전 이력·더미를 연다.
플레이어 승점을 누르면 승점 기록, 행동 기록을 누르면 공개 이벤트 상세를 본다.
끝난 판은 메뉴의 다시보기에서 시점·좌석·재생을 고른다.

친구의 서버에 들어가려면 **메뉴 → 원격 서버 연결**에 방 링크를 붙여 넣고 로비에서 앉는다.
이 컴퓨터로 호스트하려면 **플레이 설정 → 다음 실행의 서버 설정**에서 친구 초대 서버와
수신 주소·포트·친구에게 보낼 접근 가능한 서버 주소를 저장한 뒤 앱을 다시 실행한다.
개인 설정과 좌석 쿠키는 `local/`에 남는다. 업데이트에는 이 폴더와 `saves/`를 포함하지 않는다.

## 구성과 범위

- 공식 Windows x64 Python 3.14.7 embeddable 배포판과 표준 라이브러리, VC 런타임 DLL.
- `uv.lock`의 `ui` extra에 해당하는 Windows용 서버 의존성 13개. Torch·NumPy·pytest·uv·pip는 넣지 않는다.
- Godot 4.6.3 standard Windows x64 실행 파일, GDScript 프로젝트와 한글 글꼴(OFL).
- 게임 Python 소스·표시 데이터·앱 AI. 규칙·AI·codec·기존 웹 동작은 그대로다.
- Python·Godot·의존 라이브러리의 라이선스 고지, 파일별 체크섬과 소스 커밋을 담은 manifest.

현재는 release export 대신 공식 Godot 실행 파일을 포함한 시제품이다. 릴리스 export·설치 프로그램·
실행 아이콘과 서명은 후속 패키징 범위다. 대상은 Windows 10 이상 x64다.

이미지는 기본 빌드에 포함하지 않는다. 사용자가 자신의 Windows에도 그림 폴더가 없다고 알려 준 이번
**개인 테스트 묶음**에는 소유자의 기존 비공개 캐시에서 `cards/`, `board/`, `icons/`, `tokens/`만 복사한다.
캐시 README의 "personal use across the owner's machines only" 범위다. 다른 사람/공개 배포용 이미지 팩이
아니며 Git에 그림을 추가하지 않는다. `rulebooks/` PDF와 `reference/`는 읽거나 포함하지 않는다.

## 개발자 빌드

빌드 머신은 저장소와 uv를 사용한다. 플레이 머신은 사용하지 않는다.
`docs/godot-client-plan` 브랜치의 저장소 루트에서 실행한다. Windows PowerShell에서도
아래 한 줄로 같은 Windows x64 ZIP을 만든다(Linux/WSL에서도 교차 빌드 가능).

```powershell
uv run --inexact --extra ui python -m dune_imperium.godot_client.package_windows --output tmp/godot/dune-windows.zip
```

완료하면 `tmp/godot/dune-windows.zip` 전체를 플레이 컴퓨터에 옮겨 압축을 풀고
`Dune-Uprising-Prototype/Play Dune.cmd`를 더블클릭한다. 동봉한 Windows `.exe`들과
Python 규칙 서버를 함께 시작하는 진입점이므로 배포 폴더 전체를 유지한다.
아래는 같은 명령의 Bash 표기다.

```bash
uv run --inexact --extra ui python -m dune_imperium.godot_client.package_windows \
  --output tmp/godot/dune-windows.zip
```

소유자 개인용 이미지 묶음을 만들 때만 `--personal-assets assets`를 더한다.
출력은 기존 파일을 덮어쓰지 않는 새 경로를 지정한다.

공식 Python ZIP의 SHA-256, Godot ZIP의 SHA-512와 고지 파일의 해시를 검증한다.
`uv export --locked --no-dev --extra ui --no-emit-project`의 해시 요구사항에서 Windows cp314 x64
wheel만 설치하며 소스 빌드는 금지한다. 빌드 파일과 다운로드는 `tmp/godot/portable-build-cache/`에 둔다.
그림을 넣은 산출물도 git 무시 폴더에만 두고 공개로 게시하지 않는다.

Python의 `python314._pth`는 표준 라이브러리·동봉 의존성·`../../src`만 지정한다. 환경과 다른 Python
설치에 기대지 않는다. `import site`와 동봉 `sitecustomize.py`는 리디렉션된 서버 출력의 한글을 UTF-8로
맞춘다(embedded의 격리 모드에서는 환경 변수의 인코딩 지정을 신뢰할 수 없다).
Pythonw 진입점은 시작 로그를 열고 동봉 Godot 경로를 명시하므로 런타임 다운로드를 하지 않는다.
기존 서버 프로세스 감독·stdin 종료·Windows Job Object를 그대로 재사용한다.

## 검증의 한계

패키지 경로·아카이브 탈출 거부·다운로드 체크섬·기존 게임 보존·한글 출력·콘솔 없는 시작 로그·
개발 의존성 배제·개인 이미지 폴더 제한은 Python 회귀로 확인한다. 실제 Windows wheel과 runtime의
내용·라이선스·ZIP CRC·파일별 체크섬도 점검한다.

Linux에서는 배포본과 같은 프로그램 복사본을 한글·공백 경로에 두고, 서버 의존성 13개만 설치한
별도 환경에서 실제 Godot 시작과 한 판 완주·중간 저장 복원·서버 종료를 확인한다.
이 결과는 **Windows PE 실행·더블클릭·그래픽 드라이버·한글 경로의 실기 검증을 대신하지 않는다**.
사용자가 이전 ZIP으로 Windows 시작·플레이 가능을 확인했다(2026-10-14).
이번 UI 변경의 Windows 조작감·완주와 그래픽 드라이버/한글 경로별 확인은 남았다.
화면은 웹의 플레이어·보드/손패·공용 카드·선택/기록 배치를 기준으로 조정했다.
카드 hover 확대, 직접 시장 구매, 1440×900·1100×740의 버튼 가시성은 Linux의 실제 입력으로 확인한다.

근거: [Python 공식 내장 배포 안내](https://docs.python.org/3.14/using/windows.html#the-embeddable-package),
[Python 3.14.7 배포 파일과 체크섬](https://www.python.org/downloads/release/python-3147/),
[Godot 4.6.3 공식 배포](https://godotengine.org/download/archive/4.6.3-stable/),
[Godot 라이선스](https://github.com/godotengine/godot/blob/4.6.3-stable/LICENSE.txt).
