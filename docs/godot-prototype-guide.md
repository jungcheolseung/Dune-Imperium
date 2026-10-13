# Godot 플레이 시제품 실행

상태: Windows x64용 시작 스크립트와 PC 2D 시제품. 작업 브랜치는
`docs/godot-client-plan`이며 master에는 반영하지 않는다.

## Windows에서 한 번 실행하기

기존 저장소와 `uv`를 쓰는 개발용 시제품이다. Godot 에디터를 직접 설치하거나 열 필요는 없다.

1. 이 브랜치의 파일을 연 작업 폴더에서 `scripts\godot\Play Prototype.cmd`를 더블클릭한다.
2. 첫 실행은 공식 Godot 4.6.3 Windows x64 다운로드·SHA-512 검증·폰트 준비를 한다.
3. 게임 창에서 **새 게임 → 게임 시작**을 누른다. 사람 1명과 앱 AI 어려움 3명의 기본 봉기 게임이
   시작된다. 원하면 **지도자 공개 드래프트**를 켜고 지도자를 선택한다.
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
  선택 버튼에도 같은 조작을 적용한다. 드래프트 지도자는 고르기 전에 능력을 읽을 수 있다.
- 보드에서 휠로 확대·축소, 가운데 버튼을 누르고 드래그하면 이동, **전체 보기**로 초기 위치.
- **시장**은 임페리움 열과 예비 더미, **기록**은 최근 공개 행동을 보여준다.
- 공개 차례에는 **남은 설득력**이 표시된다. 구매 뒤 추가 효과가 있으면 **선택**에서 해결한다.
- **테이블**에서 교전 보상, 각 좌석의 영향력·동맹·지배·병력·모래벌레·스파이, 지도자 능력,
  플레이한 카드·버린 카드·목표·전투 카드를 살펴본다. 내 덱 구성은 순서를 숨겨 보여준다.
  더미 안의 카드는 살펴보기용이며 누른다고 게임 행동을 보내지 않는다.
- 전투·종료 책략 차례도 **선택**에서 진행하고, 오른쪽 아래 버튼으로 패스한다.
  판이 끝나면 서버가 판정한 **최종 순위**와 승점·동점 판정 자원을 보여준다.
- **저장**은 기존 서버 형식으로 저장한다. **이어하기**에서 수동·자동 저장을 다시 연다.
  첫 좌석이 사람이고 나머지 셋이 AI인 기본판 저장만 목록에 나오며 확장 저장은 제외한다.
- Esc는 현재 카드·칸·확정 전 선택을 해제한다. 게임을 종료하지 않는다.

현재 단계는 기본 게임 완주를 검증한 개발용 시제품이다. 확장 선택 화면, 원격 좌석, 다시보기,
완성된 전투/라운드 연출과 모든 지도자 전용 시각 표시는 이후 단계에서 추가한다.
기본 게임의 세부 선택은 서버 행동 목록을 표현하는 일반 선택창으로 진행한다.
기본 게임 전체의 카드/지도자 조합을 전수 검증한 것은 아니다. 보드 배치·가독성과 연출도
후속 작업이며 Windows 실기 플레이 확인은 남았다.

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
git worktree add --detach tmp/godot-complete-preview FETCH_HEAD
```

이후 `tmp\godot-complete-preview\scripts\godot\Play Prototype.cmd`를 더블클릭한다.
이 미리보기 작업 트리는 실행용이며, 본 구현과 커밋은 `docs/godot-client-plan` 브랜치에서 한다.
에셋은 메인 체크아웃에서 찾아 읽고, 미리보기 판의 저장·로그는 미리보기 작업 폴더에 둔다.
기존 `tmp/godot-preview`의 저장을 유지하며 업데이트하려면 새 작업 트리를 만들지 않고,
fetch 직후 다음을 실행해 그 미리보기 작업 트리만 새 커밋으로 옮긴다(master는 그대로다).

```powershell
$godotCommit = git rev-parse FETCH_HEAD
git -C tmp/godot-preview switch --detach $godotCommit
```

## 검증

Python 런타임 준비·글꼴/용어 데이터·실패 시 서버 정리는
`tests/launcher/test_godot_prototype.py`로 확인한다. Godot의 카드 사본 구분, 합법 칸 필터,
확정 전 선택과 undo 세대는 `model_test.gd`가 실제 GDScript로 확인한다.

```powershell
uv run --inexact --extra ui python scripts/godot/verify_prototype.py
```

이는 실제 서버에서 새 게임→카드/칸 선택→배치→되돌리기→다시 배치/효과 해결→턴 종료→
앱 AI 진행→사람 차례 복귀를 확인한다. 화면이 있는 환경에서 `--capture`를 더하면
실제 마우스 입력으로 손패·보드·새 게임 창·드래프트 설정을 선택하고, 더미 창 등을
`tmp/godot/screenshots/`에 저장한다.

완주 검증은 다음처럼 실행한다.

```powershell
uv run --inexact --extra ui python scripts/godot/verify_prototype.py --full-game
```

기본 시드 11·22·33·44 중 두 판은 지도자 드래프트를 켠다. 실제 Godot 선택·턴 종료 버튼의
콜백으로 사람 좌석을 조작하며, 매 결정에서 제시된 행동이 선택창 또는 카드/칸/종료 버튼으로
도달 가능한지 확인한다. 네 판 모두 중간에 저장 목록에서 복원하여 관측과 확정 대기를 비교하고,
전투·종료 책략을 거쳐 최종 순위가 표시되는지 검증한다. 테스트에서는 AI의 연출 대기만
`instant`로 생략하고 규칙·앱 AI는 그대로 사용한다. 일반 실행의 AI 대기는 앞의 스모크가 확인한다.
보고서는 `tmp/godot/playthrough-report.json`에 쓴다. `--seeds 11`로 판 수를 줄일 수 있고
상한은 여덟 판이다. 화면이 있으면 `--full-game --seeds 11 --capture`로 전투·종료·저장 화면도 찍는다.

2026-10-13 검증: 네 판 모두 8~9라운드 종료, 사람 결정 49종 행동·12종 결정창 실행,
저장 복원 4회 통과. 이 판들에서 실제 선택한 확정 전 보류 행동은 0개이며, 그 동작은
GDScript 모델 회귀로 별도 확인한다. 모든 카드/지도자 효과의 전수 감사 결과로 확대하지 않는다.

개발 환경은 Linux x64이고, Godot 4.6.3의 실제 렌더링과 입력을 가상 X 디스플레이에서 확인한다.
Windows 시작 스크립트와 x64 다운로드 분기는 별도로 준비했으나 **Windows 실기 플레이는 사용자 검증이 남았다**.
문제가 있으면 `tmp/godot/process.log`, `client.log`, `import.log`, `server/`를 확인한다.
