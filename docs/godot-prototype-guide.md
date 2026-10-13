# Godot 플레이 시제품 실행

상태: Windows x64용 시작 스크립트와 PC 2D 시제품. 작업 브랜치는
`docs/godot-client-plan`이며 master에는 반영하지 않는다.

## Windows에서 한 번 실행하기

기존 저장소와 `uv`를 쓰는 개발용 시제품이다. Godot 에디터를 직접 설치하거나 열 필요는 없다.

1. 이 브랜치의 파일을 연 작업 폴더에서 `scripts\godot\Play Prototype.cmd`를 더블클릭한다.
2. 첫 실행은 공식 Godot 4.6.3 Windows x64 다운로드·SHA-512 검증·폰트 준비를 한다.
3. 게임 창에서 **새 게임**을 누른다. 사람 1명과 앱 AI 어려움 3명의 기본 봉기 게임이 시작된다.
4. 창을 닫으면 이 실행이 띄운 Python 서버도 종료된다. 이미 쓰고 있던 서버는 건드리지 않는다.

시작 스크립트의 `uv run --inexact --extra ui`는 이 체크아웃의 기존 rl/train 패키지를 제거하지 않는다.
실행기·다운로드·로그는 이 작업 폴더의 `tmp/godot/`, 저장은 `saves/`에 둔다.
첫 다운로드에는 인터넷이 필요하고, 준비한 뒤 로컬 플레이에는 인터넷이 필요하지 않다.

터미널에서는 같은 작업 폴더에서 다음을 실행한다.

```powershell
uv run --inexact --extra ui python -m dune_imperium.godot_client.launch
```

다운로드가 막히거나 Godot이 이미 있으면 실행 파일을 지정한다.
검증된 기본 버전은 [Godot 4.6.3 standard](https://godotengine.org/download/archive/4.6.3-stable/)다.

```powershell
uv run --inexact --extra ui python -m dune_imperium.godot_client.launch --godot "C:\Tools\Godot_v4.6.3-stable_win64.exe"
```

이미 실행 중인 **로컬/open 모드** 서버에 연결할 수도 있다. 이 경우 그 서버는 종료하지 않는다.
원격 좌석 인증과 참가 화면은 이번 시제품의 범위가 아니다.

```powershell
uv run --inexact --extra ui python -m dune_imperium.godot_client.launch --server http://127.0.0.1:8000
```

## 조작

- 손패 카드 클릭 → 보드의 합법 칸 클릭 → 오른쪽 **에이전트 배치** 버튼.
- 공간·카드 효과와 추가 선택은 오른쪽 **선택**에서 처리한다. 선택 가능한 행동은 모두 서버가 제시한다.
- **턴 종료 ▶**로 차례를 끝낸다. 서버가 확정을 기다리는 선택은 **선택 확정 ▶**로 보낸다.
  확정 전에는 다른 선택으로 바꿀 수 있다. **되돌리기**는 서버가 허용하는 범위에서만 켜진다.
- 카드·칸 위에 마우스를 올리면 오른쪽 설명, 카드를 오른쪽 클릭하면 큰 그림과 설명 창.
- 보드에서 휠로 확대·축소, 가운데 버튼을 누르고 드래그하면 이동, **전체 보기**로 초기 위치.
- **시장**은 임페리움 열과 예비 더미, **기록**은 최근 공개 행동을 보여준다.
- **저장**은 기존 서버 형식으로 저장한다. 로컬 자동 저장도 켜며, 불러오기 화면은 후속 범위다.
- Esc는 현재 카드·칸·확정 전 선택을 해제한다. 게임을 종료하지 않는다.

현재 단계는 실제 턴을 진행하는 시제품이다. 확장 선택 화면, 원격 좌석, 다시보기,
완성된 전투/라운드 연출과 모든 지도자 전용 시각 표시는 이후 단계에서 추가한다.
기본 게임의 세부 선택은 서버 행동 목록을 표현하는 일반 선택창으로 진행한다.
기본 게임 전체의 카드/지도자별 화면 대응을 모두 검증했다고 주장하지 않는다.

## 그림과 글꼴

카드·보드·토큰 그림을 이 브랜치에 포함하거나 새로 내려받지 않는다.
기존 [로컬 이미지](local-images.md)를 Python 서버가 제공하고 Godot이 읽는다.
작업 트리에 `assets`가 없어도 같은 저장소의 메인 체크아웃에 있는 에셋 폴더를 찾는다.
Windows에서 시제품 때문에 새 에셋 심볼릭 링크를 만들 필요는 없다.
그림이 없는 환경은 카드 텍스트와 보드 칸으로 대신한다.

한글 표시는 나눔고딕 Regular를 포함한다. 출처는
[Google Fonts의 Nanum Gothic](https://github.com/google/fonts/tree/main/ofl/nanumgothic),
라이선스는 프로젝트 폰트 폴더에 함께 둔 SIL OFL 1.1이다. 글꼴은 수정하지 않았다.
용어·행동 이름·기본 결정 문구는 기존 웹 화면의 검수된 표에서 실행할 때 읽어 쓴다.

## Git bundle로 Windows에 옮기기

별도로 제공하는 `godot-prototype.bundle`은 `a6ea62dc` 이후의 이 브랜치 커밋이다.
기존 Windows 저장소가 이 기준 커밋을 가지고 있어야 한다. 메인 작업 폴더에서 다음을 실행하면
현재 브랜치를 옮기거나 master를 병합하지 않고 별도 미리보기 작업 트리를 만든다.

```powershell
git bundle verify "C:\Downloads\godot-prototype.bundle"
git fetch "C:\Downloads\godot-prototype.bundle" docs/godot-client-plan
git worktree add --detach tmp/godot-preview FETCH_HEAD
```

이후 `tmp\godot-preview\scripts\godot\Play Prototype.cmd`를 더블클릭한다.
이 미리보기 작업 트리는 실행용이며, 본 구현과 커밋은 `docs/godot-client-plan` 브랜치에서 한다.
에셋은 메인 체크아웃에서 찾아 읽고, 미리보기 판의 저장·로그는 미리보기 작업 폴더에 둔다.

## 검증

Python 런타임 준비·글꼴/용어 데이터·실패 시 서버 정리는
`tests/launcher/test_godot_prototype.py`로 확인한다. Godot의 카드 사본 구분, 합법 칸 필터,
확정 전 선택과 undo 세대는 `model_test.gd`가 실제 GDScript로 확인한다.

```powershell
uv run --inexact --extra ui python scripts/godot/verify_prototype.py
```

이는 실제 서버에서 새 게임→카드/칸 선택→배치→되돌리기→다시 배치/효과 해결→턴 종료→
앱 AI 진행→사람 차례 복귀를 확인한다. 화면이 있는 환경에서 `--capture`를 더하면
실제 마우스 입력으로 손패와 보드를 선택하고 화면 세 장을 `tmp/godot/screenshots/`에 저장한다.

개발 환경은 Linux x64이고, Godot 4.6.3의 실제 렌더링과 입력을 가상 X 디스플레이에서 확인한다.
Windows 시작 스크립트와 x64 다운로드 분기는 별도로 준비했으나 **Windows 실기 플레이는 사용자 검증이 남았다**.
문제가 있으면 `tmp/godot/process.log`, `client.log`, `import.log`, `server/`를 확인한다.
