# Godot 화면 다듬기 인수인계

사용자 목표: Windows에서 설치 없이 게임을 완주하면서, 기존 웹과 익숙한 배치·조작을 유지하고
카드를 읽고 선택하기 편한 화면을 만든다. 사용자는 현재 결과물의 완성도에 만족하지 않는다.
기능 대응 뒤 Claude에게 화면을 다듬는 작업을 맡길 예정이다. 기능 검사 통과를 좋은 플레이
경험의 증거로 대신하지 않는다.

## 작업 위치와 지켜야 할 동작

- `docs/godot-client-plan` 브랜치의 작업 트리에서만 작업한다. master에 커밋·병합하지 않는다.
- 시작할 때 `AGENTS.md`, `README.md`, `development-handoff.md`와 이번 달 worklog를 읽는다.
  다른 PC의 변경은 fetch 후 비교하고, 기존 사용자 파일과 전달한 ZIP은 보존한다.
- 게임 규칙·AI는 Python 서버의 책임이다. 클라이언트는 현재 서버가 제공한 합법 DTO의
  index/arguments/revision/undo_count로만 선택한다. 보기 좋게 합치더라도 서로 다른 선택을
  잃거나 자동으로 확정하지 않는다.
- 손패·엿보기·Scouts 비밀은 현재 좌석의 허가된 snapshot만 사용한다. 덱 구성의 표시 순서는
  실제 덱 순서가 아니다. 좌석/시점 변경과 권한 상실에서 개인 정보창을 닫는다.
- 카드→칸, 칸→카드 모두 가능하다. 유일한 배치는 즉시 보내고 복수 옵션은 선택을 기다린다.
  확정 대기 선택과 경매는 한 번의 턴 종료로 확정한다. 금액 변경만으로 서버에 보내지 않는다.
- 폐기에서 손패/버림/플레이 영역과 이번 턴/이전 턴의 물리 복사본을 구별한다. 남은 효과를
  잃는 경고는 서버의 `box_losing_trash`로만 판단한다. 접목의 잠긴 효과는 사라진 것처럼 보이지 않는다.
- 한국어/영어, 그림이 없는 경우, 1100×740 이상의 논리 테이블 영역과 FHD/QHD/4K 배율을
  유지한다. 폰트만 확대하고 클릭 좌표·팝업을 따로 두지 않는다.

## 시각 작업의 우선순위

1. **카드 가독성:** 손패·구매 시장·선택 후보에서 그림과 이름을 바로 읽게 한다. 작은
   썸네일의 나열만으로 끝내지 말고 큰 hover와 상세창까지 같은 정보 구조로 연결한다.
   긴 이름·효과·장수 배지가 카드 위에서 겹치지 않는지 실제 이미지로 본다.
2. **화면 위계:** 보드·손패·현재 선택·시장·기록의 관계를 유지하면서, 지금 해야 할 선택과
   확정 버튼이 먼저 보이게 한다. 테두리·패널·작은 버튼이 모두 같은 강도로 경쟁하지 않게 한다.
   처음 보는 사람도 접목 두 카드의 효과와 보드 효과를 구별할 수 있어야 한다.
3. **선택 상태:** 선택/가능/불가/확정 대기/잠김을 색만으로 구별하지 않는다. 카드·칸·선택
   행이 같은 상태를 가리키고, 경고·비용·예고를 행의 핵심 문구와 분리해 읽기 쉽게 한다.
4. **정보창:** 관련 카드와 보드 칸을 함께 읽되, 긴 설명은 창 안에서 스크롤한다. 작은 창에서
   닫기·검색·선택 버튼이 화면 밖으로 나가지 않고, 창을 닫으면 하던 선택으로 돌아온다.
5. **마감:** 글자 크기·간격·색·버튼 형태·아이콘과 효과음의 일관성. 새로운 그림이 필요하면
   먼저 출처와 허용 범위를 확인한다. 기존 개인 그림을 공개 저장소에 넣지 않는다.

이 항목들은 사용자 불만과 현재 화면 구조에 따른 작업 후보다. 대규모로 바꾸기 전에 같은
국면의 웹/현재 Godot/수정안 캡처를 비교하고, 작은 변경 단위로 실제 플레이를 확인한다.
웹을 픽셀 단위로 복제하는 것이 완료 조건은 아니다.

## 코드와 검증 입구

| 대상 | 위치 |
| --- | --- |
| 전체 테이블·손패·시장·hover·선택 행 | `src/dune_imperium/godot_client/project/main.gd` |
| 보드 칸·조각 | 같은 폴더 `board.gd` |
| 합법 선택·개인 정보·번역·표시 모델 | `model.gd` |
| 접목 효과·수량·폐기 영역 | `choices.gd` |
| 계약/연구/기술/지도자/Scouts | `expansions.gd` |
| 더미·큰 카드·검색 | `pile_viewer.gd`, `portrait.gd` |
| 설정·좌석·팝업·다시보기·접힘 | `session_tools.gd` |
| 모니터/DPI·논리 좌표 | `display_scale.gd` |
| 공개 연출과 합성음 | `effects.gd` |
| 웹 기준 | `src/dune_imperium/server/static/`의 `render.js`, `turn.js`, `panels.js`, `board.js` |

위 경로는 저장소 루트 기준이다. GDScript 테스트는 실제 Godot 4.6.3으로 실행한다.

```bash
# 개발용: --godot에는 이 PC의 고정 Godot 실행 파일 절대 경로를 넣는다.
PYTHONPATH=src .venv/bin/python scripts/godot/verify_prototype.py --godot /path/to/godot
PYTHONPATH=src .venv/bin/python scripts/godot/verify_prototype.py --godot /path/to/godot --capture
PYTHONPATH=src .venv/bin/python scripts/godot/verify_prototype.py --godot /path/to/godot --full-game --rules all --seeds 22
# 개발용 Playwright/Chromium이 있는 환경에서 같은 저장본 직접 대조
PYTHONPATH=src .venv/bin/python scripts/godot/verify_parity.py --godot /path/to/godot --suite choices --chromium /path/to/chromium
```

`verify_parity.py`는 `core`, `info`, `quantity`, `choices`를 지원한다. `choices`는 실제
접목 잠금/undo/다른 카드의 효과와 이번 턴·이전 턴 카드 폐기의 두 언어 대조다. `--evidence`는
화면이 있는 개발 환경에서 캡처와 좁은 창 경계를 검사한다. Playwright는 배포 의존성이 아니다.
실행 로그·합법 행 census·서버 결과 hash와 실제 캡처를 함께 확인한다. 현재 검증 범위와 남은
조합은 `godot-feature-parity.md`에 있다.

Windows 사용자는 Python·uv·Git·Godot·그림 폴더가 없어도 전달한 개인용 ZIP으로 실행할 수
있어야 한다. 다른 PC가 같은 이름으로 만든 ZIP은 hash와 구성 파일이 다를 수 있으므로,
업데이트는 이름만 보고 적용 가능하다고 쓰지 않는다. 정확한 기준 manifest로 overlay를 검증한다.
Windows IME·스피커·실제 모니터 이동·LAN 및 전수 카드/지도자 감사는 자동 검사와 구분한다.
