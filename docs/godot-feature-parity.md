# Godot의 기존 웹 기능 대응

사용자 결정(2026-10-14): 비슷해진 테이블 배치를 유지하고 기존 기능 전체의 대응을 이어 간다.
작업은 `docs/godot-client-plan`에서만 한다. 이 표는 기능 검증 상태이며 전체 전환 완료 선언이 아니다.
Python 규칙·AI·codec·저장 형식은 그대로 사용하고, 두 클라이언트의 표시와 입력을 대조한다.

| 영역 | 대응 내용 | 현재 검증 / 남은 것 | 웹 검증 기준 |
| --- | --- | --- | --- |
| 기본 게임 | 카드→칸→배치, 모든 합법 선택, 공개·구매·책략·전투·확정·undo·최종 순위 | 기존 네 판 및 레이아웃 변경 뒤 두 판 완주. 새 세션 구조의 기본 스모크 통과 | staged_turn, turn_end, held_choice, intrigue_options, combat_result |
| 게임 설정 | 좌석 종류·난이도, 검색 서버의 탐색 AI, 학습 경로, 무작위 좌석, 시드, AI 속도, 모든 규칙 옵션 | 새 창 실제 클릭/드래프트 통과. 확장 전용 표시와 완주는 다음 단위 | setup_options, setup_layout, app_ai_seats, search_seats, ai_pace |
| 좌석 / 원격 | 첫 좌석 이외의 사람, 로컬 좌석 교대, 이름·claim/release·관리자 인증, origin/path 쿠키 복귀, SSE·재접속 | 실제 open 23항목 / remote 25항목. 원격 호스트 실행 설정과 재접속 확대 검사 남음 | remote, open_mode, remote_fresh, launcher_link, races, recovery |
| 저장 / 게임 관리 | 모든 4인 저장 복원·이름, 수동/자동 저장 목록, 삭제 확인, 게임 목록 / 방 | 이름·복원 계약 검사. 삭제 확인의 실제 UI 및 게임 삭제 검증 남음 | save_delete, recovery, refresh_error |
| 관전 / 다시보기 | AI만 있는 판, 시점·좌석·처음/끝·내 수, 턴/수 단위 재생·속도, cursor까지의 로그 | AI 전용 판의 readonly 시점/좌석/서버 불변 검증. 실제 재생·공개 정보 창 확대 검사 남음 | spectate, endgame, log_passes, log_follow |
| 공개 / 개인 정보 | 승점 기록·로그 이동, 교전 이력, 덱/버림/폐기·공개 책략·목표·종료 공개 | 승점 기록 연결. 교전 이력·더미 상세 개선·공개 정보 창·특수 엿보기 표시 남음 | vp_ledger, conflict_history, deck_contents, deck_piles, pile_viewer, intrigue_faceup |
| 확장 / 지도자 | CHOAM·프로모, Bloodlines·Tech, Immortality·Go to 11, Epic, Scouts, 지도자 트랙·개인 슬롯 | 서버 옵션과 일반 선택은 연결. 전용 보드·시장·지도자 상태·Scouts 카드/조각/비밀 표시 및 완주 남음 | tech_acquire, graft_boxes, bene_tleilax_specimens, scouts, scouts_stage, leader_card |
| 플레이 편의 | 한국어/영어, 도움말, 게임/좌석/차례 시계, 열 너비·손패 순서·접힘 설정 | 웹의 555 UI 번역과 시계 계산/도움말·기본 접힘 연결. 모든 문구/개인 배치·한글 입력 검증 남음 | lang, clock, help, layout_custom, columns, seats, narrow |
| 선택 불가 / 효과 | 이유·조건·비용, agent-box 구분·예고, 자원 변화·카드/단계/전투 연출·서로 다른 합성 효과음 | 서버의 표시 데이터는 재사용. 전용 표현과 연출/음량 설정 남음 | unavailable, effect_text, card_hover, table_effects, phase_banner, scouts_decision_item |
| 설치 없는 배포 | Windows 런타임·개인 그림 동봉, 앱 종료·서버 정리, 작은 업데이트 | 이전 Windows 사용자 실행 확인. 기능 확대 뒤 새 ZIP / overlay 해시 검사 남음 | native bootstrap/portable 회귀 및 실제 Windows 피드백 |

테스트 이름은 `scripts/e2e/<이름>.py`다. 기존 브라우저 E2E 전체 실행은 웹 기능의 기준이며,
Godot이 같은 기능을 지원한다는 증거는 Godot 모델/실제 서버/네이티브 입력 검사를 별도로 남긴다.
학습망은 서버가 제공할 때 선택하고 기본 Windows 묶음은 앱 AI를 유지한다. 임의의 옛 체크포인트를
배포용 망으로 바꾸지 않는다. 현재 기능 대응의 남은 항목을 종료 전에 숨기거나 완료로 적지 않는다.
