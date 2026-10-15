# Godot 화면 다듬기 인수인계

사용자 목표: Windows에서 설치 없이 게임을 완주하면서, 기존 웹과 익숙한 배치·조작을 유지하고
카드를 읽고 선택하기 편한 화면을 만든다. 사용자는 현재 결과물의 완성도에 만족하지 않는다.
Claude 토큰 대기 중 Codex가 기본 플레이 화면과 확장 패널/정보창의 1차 시각 개선을 반영했다. 이후 화면 다듬기도
이 기준에서 이어 간다. 기능 검사 통과를 좋은 플레이 경험의 증거로 대신하지 않는다.

## 작업 위치와 지켜야 할 동작

- `docs/godot-client-plan` 브랜치의 작업 트리에서만 작업한다. master에 커밋·병합하지 않는다.
- 업데이트 ZIP/전체 패키지는 사용자가 요청할 때만 만든다(2026-10-15 사용자 결정).
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

## 반영한 기본 플레이 화면

손패를 논리 창 높이에 맞춰 확대하고 기본 다섯 장의 폭을 조정한다. 손패가 없으면 카드 영역을
접는다. 시장에는 두 줄 이름과 인쇄된 설득력 비용을 붙였고, 선택·접목 상대·불가를 체크/+/×와
함께 표시한다. 공간이 부족하면 상태 문구만 기호로 줄이며 비용·이름 영역은 겹치지 않는다.
카드 그림·이름·fallback은 버튼의 실제 크기를 따라가므로 열 드래그·창 크기 변경에도 맞춘다.

플레이어 그림·자원/병력/시계·더미 버튼을 압축하고, 긴 좌석 이름이 승점 버튼을 밀어내지 않게
했다. 보드 도구는 손패 머리줄로 합쳤다. 수량 드롭다운과 확정 버튼을 세로로 배치해 긴 영어
문구가 선택 열을 밀어내지 않게 했다. 현재 선택은 한 번만 크게 보여주고, 유효한 턴 종료를
강조하며, 선택 해제 버튼의 이름이 0폭으로 줄던 문제를 고쳤다. 선택 행의 비용·효과 문구와
DTO/확정 흐름은 유지한다. 저장된 개인 열 너비는 존중하며 설정에서 초기화할 수 있다.

`tmp/godot/visual-polish/before-table.png`와 `tmp/godot/screenshots/table.png`는 같은 seed 11의
첫 Agent 국면 전후다(시계 차이는 있다). `card-selected.png`, `table-no-art.png`, `market.png`,
`market-en-narrow.png`와 FHD/QHD/4K의 두 언어 실제 플레이 캡처도 남겼다. 기본 입력 검사에
선택 표식/이름 버튼 해제·없는 그림·빈 손패·카드 이름/그림/비용/상태 경계를 보강했다.
모든 native 캡처에서 테이블·승점 버튼·시장 확대 버튼 경계도 검사한다. 마지막 시장 머리글
여백 조정 뒤 대표 두 언어 국면 2사례/56항목도 재확인했다. 기본 입력 5사례/34,
수량·경매 10사례/98과 선택창 16사례/404항목을 새 배치로 재실행했다.
Windows 실제 GPU·IME·스피커·모니터 이동은 별도 확인 범위다.

## 반영한 확장 패널과 정보창

카드 상세와 관련 카드/칸 효과 미리보기는 공통 `detail_entry.gd`로 그림 옆에 이름/본문을
배치한다. 그림의 실제 비율을 지키며 좁은 본문에서는 세로로 전환한다. 그림이 없으면 설명이
열 전체를 쓴다. 긴 효과는 기존 창 스크롤 안에서 읽는다. 선택한 보드/책략 옵션의 본문만
펼치는 동작과 영역/물리 복사본 표시는 유지한다. 긴 영어 지도자 능력이 popup 최소 너비를
키우지 않도록 줄바꿈을 먼저 설정하고 내용을 넣는다.

덱/버림 더미의 세로 카드를 키우고 계약·기술·스킬처럼 가로 카드만 있는 더미는 두 열로
보여준다. 오른쪽 확대 그림도 실제 비율에 맞춰 설명 공간을 돌려준다. 장수·알려진 맨 위
복사본·공개 순서와 개인 정보 갱신/닫기는 유지한다. 지도자 개인 슬롯과 확장 시장의 가로
카드도 확대했다. 시장 카드는 열 너비에 맞추고 긴 영어 시장 제목은 줄바꿈한다.

연구 창에는 보드 옆에 서버가 허용한 목적지 버튼과 네 플레이어의 공개 연구/표본 상태를
붙였다. 보드와 버튼은 같은 기존 선택 경로를 쓴다. Scouts overlay는 그림/본문을 함께 읽고
보드 경계 안에 머문다. 현황 창은 공개 정보와 허가된 자신의 비공개 선택을 구분한다.
없는 그림 때문에 새 정보를 추측하거나 클라이언트에서 합법 목적지를 만들지 않는다.

같은 저장본의 정보 4사례/32와 선택창 16사례/404를 새 상세 배치로 재검증했다. 새 확장
패널 검사는 ko/en 6사례/86항목과 좁은 창 포함 캡처 36장, headless 76항목을 통과했다.
연구 보드 클릭/텍스트 버튼 결과는 별도 복원본에서 서버가 실행한 같은 DTO와 hash가 같다.
`tmp/godot/visual-polish/before-detail.png`와
`tmp/godot/parity/screenshots/effect-detail-graft-boxes-ko.png`,
`tmp/godot/visual-polish/before-pile.png`와 `tmp/godot/parity/screenshots/deck-ko-glowglobes.png`에
같은 국면의 전후를 남겼다. 새 패널 화면은 `tmp/godot/panels/screenshots/`다.

## 반영한 선택 위계와 실행 결과

선택 행은 `action_choice.gd`의 한 버튼 안에서 제목·대상·지불/인쇄 비용·효과·예상·주의를
구분한다. 비용이나 경고를 눌러도 같은 기존 DTO callback을 사용한다. 제목과 설명은
접근성 이름/설명에도 넣는다. 수량 설명과 선택 불가 이유도 같은 구조를 쓴다.
지불 비용은 기존 `paid_cost`, 예고/부족/비가역 경고는 서버 DTO, 이번 턴 남은 효과 소실은
기존 `choice_zones`만 사용한다. 공개 기록의 `describe` 기본 결과는 바꾸지 않는다.

확정 대기는 선택됨/턴 종료 표식으로 표시한다. `action_feedback.gd`는 행동 기록 위에 마지막
실행 결과를 짧게 보인다. 서버 수락과 같은 좌석/게임/undo 세대의 새 snapshot을 확인해야
실행됨으로 표시하며, 거절/상태 확인 중은 따로 표시한다. 공개 자원/승점 순변화는 확인 때
고정하며 뒤의 poll/AI 변화를 이어 붙이지 않는다. 새 선택을 막거나 연출을 추가하지 않는다.
undo·좌석/권한 상실·게임 변경·다시보기에서는 결과와 캐시 문구를 지운다. 비공개 덱/뽑기를
추측하지 않는다. `_send_action`의 원래 응답/동기화 순서는 유지한다.

모델 105항목, 같은 저장본의 기본 5사례/61·정보 4사례/32·수량/경매 10사례/98·선택창
16사례/438항목을 통과했다. 기본 GUI에는 ko/en 비용·확정 대기·실행 결과 16캡처/60항목도
포함한다. `tmp/godot/parity/screenshots/payment-options-en-narrow.png`, `held-choice.png`,
`applied-multiple.png`와 수량/선택창 캡처에 새 화면을 남겼다(뒤 경로도 같은 screenshots 폴더).
이전 선택 화면 3장은 `tmp/godot/choice-polish/before-*.png`에 보존했다.

다음 시각 후보는 **보드·손패의 선택 안내와 hover/클릭 피드백**이다. Windows 실제 플레이
피드백도 확인해야 한다. 이번 개선을 전체 시각 마감이나 모든 카드 조합 감사의 완료로 읽지 않는다.

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
| 선택 읽기 구조·접목 효과·수량·폐기 영역 | `action_choice.gd`, `choices.gd` |
| 서버 확인 후 실행 결과 | `action_feedback.gd` |
| 계약/연구/기술/지도자/Scouts | `expansions.gd` |
| 상세 그림/본문·더미·큰 카드·검색 | `detail_entry.gd`, `pile_viewer.gd`, `portrait.gd`, `hand_card.gd` |
| 설정·좌석·팝업·다시보기·접힘 | `session_tools.gd` |
| 모니터/DPI·논리 좌표 | `display_scale.gd` |
| 공개 연출과 합성음 | `table_effects.gd` |
| 웹 기준 | `src/dune_imperium/server/static/`의 `render.js`, `turn.js`, `panels.js`, `board.js` |

위 경로는 저장소 루트 기준이다. GDScript 테스트는 실제 Godot 4.6.3으로 실행한다.

```bash
# 개발용: --godot에는 이 PC의 고정 Godot 실행 파일 절대 경로를 넣는다.
PYTHONPATH=src .venv/bin/python scripts/godot/verify_prototype.py --godot /path/to/godot
PYTHONPATH=src .venv/bin/python scripts/godot/verify_prototype.py --godot /path/to/godot --capture
PYTHONPATH=src .venv/bin/python scripts/godot/verify_panels.py --godot /path/to/godot --capture
PYTHONPATH=src .venv/bin/python scripts/godot/verify_prototype.py --godot /path/to/godot --full-game --rules all --seeds 22
# 개발용 Playwright/Chromium이 있는 환경에서 같은 저장본 직접 대조
PYTHONPATH=src .venv/bin/python scripts/godot/verify_parity.py --godot /path/to/godot --suite choices --chromium /path/to/chromium
PYTHONPATH=src .venv/bin/python scripts/godot/verify_parity.py --godot /path/to/godot --suite core --evidence --chromium /path/to/chromium
```

`verify_parity.py`는 `core`, `info`, `quantity`, `choices`를 지원한다. `choices`는 실제
접목 잠금/undo/다른 카드의 효과와 이번 턴·이전 턴 카드 폐기의 두 언어 대조다. `--evidence`는
화면이 있는 개발 환경에서 캡처와 좁은 창 경계를 검사한다. Playwright는 배포 의존성이 아니다.
`verify_panels.py`는 브라우저 없이 확장 저장본을 복원하고, `--capture`는 보드 클릭과 실제
두 크기 화면을, headless는 텍스트 연구 버튼을 검사한다(`panel_test.gd`).
실행 로그·합법 행 census·서버 결과 hash와 실제 캡처를 함께 확인한다. 현재 검증 범위와 남은
조합은 `godot-feature-parity.md`에 있다.

Windows 사용자는 Python·uv·Git·Godot·그림 폴더가 없어도 전달한 개인용 ZIP으로 실행할 수
있어야 한다. 다른 PC가 같은 이름으로 만든 ZIP은 hash와 구성 파일이 다를 수 있으므로,
업데이트는 이름만 보고 적용 가능하다고 쓰지 않는다. 정확한 기준 manifest로 overlay를 검증한다.
Windows IME·스피커·실제 모니터 이동·LAN 및 전수 카드/지도자 감사는 자동 검사와 구분한다.
