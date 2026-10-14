# Godot의 기존 웹 기능 대응

사용자 결정(2026-10-14): 비슷해진 테이블 배치를 유지하고 기존 기능 전체의 대응을 이어 간다.
작업은 `docs/godot-client-plan`에서만 한다. 이 표는 구현한 대응과 실제 검증 범위를 구분한다. Windows 실기와 전수 카드 감사는 별도다.
Python 규칙·AI·codec·저장 형식은 그대로 사용하고, 두 클라이언트의 표시와 입력을 대조한다.

| 영역 | 대응 내용 | 현재 검증 / 남은 것 | 웹 검증 기준 |
| --- | --- | --- | --- |
| 기본 게임 | 카드/칸 어느 순서든 선택, 유일한 배치 즉시 실행·복수 옵션·평면 목록, 공개·구매·책략·전투·확정·undo·최종 순위 | 기본판 기존 완주·배치/undo, 전 옵션 seed 22(10R/1128)·33(9R/1041) 완주 및 중간 복원. 아래 같은 국면 5종 직접 대조. 매 결정의 합법 행 전체를 컨트롤과 대조 | staged_turn, turn_end, held_choice, intrigue_options, combat_result |
| 게임 설정 | 좌석 종류·난이도, 검색 서버의 탐색 AI, 학습 경로, 무작위 좌석, 시드, AI 속도, 모든 규칙 옵션 | 설정 창 실제 클릭·드래프트 및 전 옵션 완주. 기본 Windows는 앱 AI, 탐색/학습은 서버가 제공하는 현재 런타임·망을 사용 | setup_options, setup_layout, app_ai_seats, search_seats, ai_pace |
| 좌석 / 원격 | 첫 좌석 이외의 사람, 로컬 좌석 교대, 이름·claim/release·관리자 인증, origin/path 쿠키 복귀, SSE·재접속 | 실제 open/remote 계약 검사: 쿠키 복귀·권한 상실·SSE 재접속·다른 좌석. 다음 실행 호스트 설정과 일회용 인증 파일 연결, 키는 argv/URL에 싣지 않음 | remote, open_mode, remote_fresh, launcher_link, races, recovery |
| 저장 / 게임 관리 | 모든 4인 저장 복원·이름, 수동/자동 저장 목록, 삭제 확인, 게임 목록 / 방 | 이름·복원 및 저장/게임 삭제의 취소·두 번째 확인 클릭을 실제 테스트 서버에서 검증 | save_delete, recovery, refresh_error |
| 관전 / 다시보기 | AI만 있는 판, 시점·좌석·처음/끝·내 수, 턴/수 단위 재생·속도, cursor까지의 로그 | AI 판 readonly 시점/좌석·재생·키보드/값 변경 seek·서버 불변, 종료 공개 덱 순서 보존 검사. 전 시점/조합 전수 검사는 아님 | spectate, endgame, log_passes, log_follow |
| 공개 / 개인 정보 | 승점 기록·로그 이동, 교전 이력, 덱/버림/폐기·공개 책략·목표·종료 공개 | 승점/로그 상세, 교전 이력, 검색·장수·창 안 큰 카드, 공개/종료 정보와 자신의 엿보기. live 덱 순서는 숨기고 disclosure에서만 원래 순서를 읽음 | vp_ledger, conflict_history, deck_contents, deck_piles, pile_viewer, intrigue_faceup |
| 확장 / 지도자 | CHOAM·프로모, Bloodlines·Tech, Immortality·Go to 11, Epic, Scouts, 지도자 트랙·개인 슬롯 | 계약/스킬/기술/틀레이락스 시장·연구 보드·지도자 트랙/슬롯·Scouts 단계/조각/자기 비밀·봉인 입찰 연결. 접목·연구·입찰·미션·비밀 선택을 전 옵션 완주에서 실행 | tech_acquire, graft_boxes, bene_tleilax_specimens, scouts, scouts_stage, leader_card |
| 플레이 편의 | 한국어/영어, 도움말, 게임/좌석/차례 시계, 열 너비·손패 순서·접힘 설정 | 555 UI 번역+native 문구·동적 prompt, 시계/도움말, 실제 손패/열 드래그와 설정 저장, 접힘·두 언어의 1440×900/1100×740 입력 검사. Windows IME 실기 남음 | lang, clock, help, layout_custom, columns, seats, narrow |
| 선택 불가 / 효과 | 이유·조건·비용, agent-box 구분·예고, 자원 변화·카드/단계/전투 연출·서로 다른 합성 효과음 | 서버 이유·예고·비용·shortfall·접목 box를 표현하고 합법 수량만 선택. 공개 변화/카드/단계 cue와 서로 다른 PCM 합성음·음량/끄기/움직임 줄이기. 실제 스피커 청취는 Windows 피드백 | unavailable, effect_text, card_hover, table_effects, phase_banner, scouts_decision_item |
| 설치 없는 배포 | Windows 런타임·개인 그림 동봉, 앱 종료·서버 정리, 작은 업데이트 | 이전 Windows 사용자 실행 확인. 전체 v3 243.73 MiB/업데이트 222.36 KiB, v1/v2 overlay 2,383파일 hash·최소 환경 시작/undo/종료 검증. 새 Windows 실기 피드백 남음 | native bootstrap/portable 회귀 및 실제 Windows 피드백 |

## 같은 국면의 직접 대조

`scripts/godot/verify_parity.py`는 합법 행동으로 만든 같은 저장본을 웹과 Godot용으로 각각
복원한다. 실제 Chromium DOM 클릭과 Godot 선택 컨트롤로 조작한 뒤, 서버가 반환한 개인 뷰·
합법 행동·결정·확정·revision/undo·실행 로그의 hash를 비교한다. 별도 판 ID와 시계만 제외한다.
원본 상태를 편집하거나 두 클라이언트에 새 행동을 만들어 주지 않는다. Playwright는 개발용 검사
의존성이며 플레이 배포본에는 포함하지 않는다.

| 직접 비교한 국면 | 확인한 동작 |
| --- | --- |
| 기본판 카드 먼저 | 첫 클릭은 상태 불변, 합법 칸 일치, 유일한 배치 즉시 실행 |
| 기본판 칸 먼저 | 합법 손패 카드 일치, 유일한 배치 즉시 실행 |
| Navigation Chamber / Spice Refinery | 복수 옵션 대기·행 번호 일치, 인쇄 비용과 할인 후 지불 비용, 실제 선택 결과 |
| Immortality 접목 | 손패 두 장 선택 후 유일한 옵션 실행, 다음 서버 질문에 그 상대 카드만 전송 |
| 전투 책략 획득의 확정 대기 | 테이블 두 번째 클릭은 유지, 목록 클릭은 해제, 확정 전 상태 불변·확정 후 동일 결과 |

5종 결과 hash와 native 30항목이 일치한다. 별도로 모델 57항목에서 잘못된 카드 교체의 칸 유지,
대칭 접목 행 dedup·두 카드 경로의 합집합·선택 해제·중첩 ref·할인 비용을 확인하고, 실제 전체
목록 토글도 검사했다. 수정 전 v3에서 즉시 배치와 확정 대기 재클릭 검사가 실패하는 것을 재현했다.

이 대조는 전수 카드/지도자·모든 결정창의 직접 비교를 완료했다는 뜻이 아니다. 다음 직접 대조는
Controlled/Glowglobes 엿보기와 더미 표시, 수량 선택·봉인 입찰, effect-box 잠금/예고,
undo·시점 변경·권한 상실 중 열린 창과 비공개 정보 경계다. Windows 실기 범위도 별도로 남는다.

테스트 이름은 `scripts/e2e/<이름>.py`다. 기존 브라우저 E2E 전체 실행은 웹 기능의 기준이며,
Godot이 같은 기능을 지원한다는 증거는 Godot 모델/실제 서버/네이티브 입력 검사를 별도로 남긴다.
학습망은 서버가 제공할 때 선택하고 기본 Windows 묶음은 앱 AI를 유지한다. 임의의 옛 체크포인트를
배포용 망으로 바꾸지 않는다. 현재 기능 대응의 남은 항목을 종료 전에 숨기거나 완료로 적지 않는다.

검증 범위를 넘겨 완료라고 쓰지 않는다. 최종 수치는 worklog와 handoff에 남기며,
Linux의 dummy audio 드라이버는 합성 스트림 생성/정리를 확인할 뿐 Windows 스피커 청취가 아니다.
카드/지도자 조합 전수 감사, Windows IME·그래픽/소리·여러 컴퓨터 LAN 실기는 다음 피드백 범위다.
