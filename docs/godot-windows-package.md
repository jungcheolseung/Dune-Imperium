# Windows 설치 없는 Godot 시제품

사용자 결정(2026-10-14): 플레이 컴퓨터에 Python·uv가 없으며 앞으로도 설치를 전제로 하지 않는다.
개발용 Git bundle 대신 **ZIP 전체를 풀고 더블클릭하는 폴더 배포본**을 제공한다.
작업은 `docs/godot-client-plan` 브랜치에만 남긴다.

## 실행

1. ZIP 전체를 바탕 화면 등 쓰기 가능한 폴더에 압축 해제한다.
2. `Dune-Uprising-Prototype/Play Dune.cmd`를 더블클릭한다.
3. **새 게임 → 게임 시작**을 누른다. 지도자 공개 드래프트는 선택 사항이다.

Python·uv·Git·Godot의 설치, 터미널 명령, 첫 실행 다운로드가 필요하지 않다.
첫 실행은 포함된 한글 글꼴을 준비하고 게임 창을 연다. 콘솔은 계속 띄워 두지 않는다.
창을 닫으면 이 실행이 시작한 로컬 서버도 종료한다.

**저장 / 이어하기**는 배포 폴더의 `saves/`를 사용한다. 새 버전도 별도 폴더에 풀고 기존 `saves/`를
복사하면 게임을 보존할 수 있다(저장 codec은 이번 작업에서 바꾸지 않았다).
문제 기록은 같은 폴더의 `tmp/godot/start.log`, `process.log`, `client.log`, `import.log`, `server/`에 있다.
플레이 조작은 [시제품 안내](godot-prototype-guide.md)의 조작 절을 따른다.

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
