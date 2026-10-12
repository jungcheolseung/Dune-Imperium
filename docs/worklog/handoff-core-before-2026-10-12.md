# 옛 인수인계 본문 (2026-10-12 정리 전)

2026-10-12에 [개발 인수인계](../development-handoff.md)를 현재 상태만 담게 다시 쓰면서, 그 전의 날짜 없는 절들을 그대로 옮겨 둔 것이다. 그때도 이미 일부는 낡아 있었다("기준 결과"는 2026-10-04, "현재 구현 기준선"은 2026-09-20 시점). 지금 상태는 인수인계 문서를 본다.

## 세션 시작 체크리스트

1. 저장소 루트의 `AGENTS.md`(도구 중립 공통 지침), `CLAUDE.md`(Claude Code 진입점), `README.md`, 이 문서, 그리고 [`lessons.md`](../lessons.md)를 읽는다.
2. `git status --short`와 `git log --oneline -10`으로 작업 트리와 최근 구현을 확인한다. 기존 변경은 사용자 작업으로 취급하고 덮어쓰지 않는다.
3. `uv sync --extra rl --extra ui --extra train`으로 Python 3.14 환경을 준비한다(`ui`는 FastAPI 서버 의존성; 없으면 `tests/server/test_app.py`가 skip된다. `train`은 PyTorch; 없으면 `tests/unit/training/test_torch_policy.py`가 skip된다).
4. 아래 기준 검증을 실행한다.

```bash
uv run pytest -q
uv run ruff check src tests
uv run mypy src tests
```

2026-10-04 늦은 밤(앱 대조 마무리 `app-rulings-4` 병합 `42228e41` 뒤, Mac mini, master)의 기준 결과는 **pytest 3,204개 통과**, Ruff·mypy(313파일) 통과, 브라우저 E2E 33종 녹색, 소크(병합 전 300판 + 검증 실행 800판) 실패 0. action codec **v133**(템플릿 무변경), 관측 v30 그대로; golden `base`·`choam`·`draft` 다시 고정(OQ-058 하나로 이동), tips-v1 다시 캐 122개. 그 앞 2026-10-04 밤(셋째 묶음 `app-rulings-3` 병합 `57d4d085` 뒤, Mac mini, master)의 기준 결과는 **pytest 3,181개 통과**, Ruff·mypy 통과, 브라우저 E2E 33종 녹색, 소크(셋째 묶음 검증 600판 + 병합 전 300판) 실패 0. action codec **v132**(템플릿 무변경), 관측 v30 그대로; golden digest 그대로, tips-v1은 다시 캐 126개(한 국면만 선택 번호 이동). 그 앞 2026-10-04 저녁(앱 방식 재판정 둘째 묶음 `app-rulings-2` 병합 `2ad7a262` 뒤, Mac mini, master)의 기준 결과는 **pytest 3,161개 통과**, Ruff 통과, mypy 311파일 통과, 브라우저 E2E **33종** 녹색(`unavailable.py`의 Holy War confirm seed 56 → 243), 소크 6개 구성 800판(`--soundness-interval 5 --privacy-interval 50`, random·heuristic, Epic·Go to 11·Scouts 포함) 실패 0. action codec **v131**(`place_track_spy` +1 템플릿, 모든 state hash 이동), 관측 **v30**(`intrigue_trash` 90칸 삭제, `track_spies_owed` 4칸 추가, 4,619→4,533). tips-v1은 다시 캐 126개, golden digest 여섯을 다시 고정했다(다섯은 배치만, scouts는 Spy 대기로 흐름 이동). 그 앞 2026-10-04(Steam 앱 방식 재판정 다섯 건의 `app-rulings` 병합 `a55836fc` 뒤, Mac mini, master)의 기준 결과는 **pytest 3,093개 통과**, Ruff 통과, mypy 310파일 통과, 브라우저 E2E **33종** 녹색(전체 실행에서 `log_words`만 seed가 비켜 실패해 seed를 다시 골랐고, 리뷰 수정 뒤 `log_words`·`scouts`를 다시 돌림), 소크 7개 구성 990판 + 리뷰 수정 뒤 Scouts 2개 구성 220판(`--soundness-interval 5 --privacy-interval 50`) 실패 0. action codec **v130**(Shaddam의 `take_exhausted_contract_solari` −1, Objective의 `flip_battle_card` +4, 좌석의 부족분 기록으로 모든 state hash 이동), 관측 **v29**(`shortfall` 구간, 4,611→4,619). tips-v1은 다시 캐 119개, golden `base`·`everything`을 다시 고정했다. 그 앞 2026-10-03(Distraction·Coercive Negotiation을 배치 뒤에만 내는 Plot으로 바꾼 뒤, Mac mini, 워크트리 `plot-deploy-condition`)의 기준 결과는 **pytest 3,073개 통과**, Ruff 통과, mypy 307파일 통과, 브라우저 E2E **33종** 녹색, 소크 6개 구성 660판(`--soundness-interval 5 --privacy-interval 50`) 실패 0. action codec **v129**(Distraction 발동 템플릿 27개 제거), 관측 v28 그대로(FrameKind 자리 유지). tips-v1은 다시 캐 99개, golden `choam`과 tip census 두 핀을 다시 고정했다. 그 앞 2026-10-02 저녁(Epic setup Intrigue를 Leader draft의 마지막 pick 뒤로 옮긴 뒤, Mac mini, master)의 기준 결과는 **pytest 3,069개 통과**, Ruff 통과, mypy 307파일 통과, 브라우저 E2E **33종** 녹색(`setup_options.py`가 옛 순서를 고정하고 있어 고침). action codec **v128**(템플릿 무변경 — draft 중 상태와 저장 해시만 바뀜), 관측 v28 그대로; golden 고정값·tips-v1은 그대로다. 그 앞 2026-10-02(Codex의 UI 11단계 `codex/ui-table-refresh` 병합 `c5e17ea2` 뒤, Mac mini, master)의 기준 결과는 **pytest 3,068개 통과**(실측 167초), Ruff 통과, mypy 307파일 통과, 브라우저 E2E **33종** 녹색(4개씩 129초; `table_layout`·`setup_layout` 추가). 화면만 바뀌어 codec·관측은 아래 L1·L2 기준 그대로다. 그 앞 2026-10-02(L1 "Agent 턴은 턴 종료로만" + L2 "자동 처리 → 결정 창"을 한 번에 병합한 뒤, Mac mini, master)의 기준 결과는 **pytest 3,068개 통과**(실측 약 180초; 병합 뒤 확인 셋과 codec v127의 Combat Intrigue 연속 pass 수정·순환이 비는 끝의 단계 종료 이벤트까지 — 그 앞 v126에서 3,061), Ruff 통과, mypy 통과, 브라우저 E2E **31종** 녹색(4개씩 약 130초), 소크(6개 구성, `--soundness-interval 5 --privacy-interval 50`) 실패 0, Agent 턴 닫힘 census 문제 0. action codec **v125**(L1·L2를 한 번호로 묶음: L1은 템플릿 무변경, L2가 확인 행동 템플릿을 더함 — 옛 저장은 버전 오류, 옛 체크포인트는 새 행 0으로 이관), 관측 **v28 그대로**. 병합(`8de414b8`)이 푸시된 뒤 같은 날 반영한 사용자 확인 셋이 카탈로그와 재생을 바꿔 **v126**이 되었다(CHOAM+Bloodlines에 `resolve_contract_icons_without_contract` 1개). tips-v1은 v125로 다시 캐 110개다(L1 뒤 106 → L2 A 107 → L2 B 110). 그 앞 L1만의 기준(브랜치, 병합 전): pytest 2,985. 그 앞 2026-09-30 저녁(epic-game-mode 병합 `8b3780e`, Scouts AI 좌석 `b7cf49c`, 보드 위 임무 조각 `a195676` 뒤, Mac mini, master `58049f9`)의 기준 결과는 **pytest 2,968개**(병합 master에서 2,967개 실측 통과 + 문구 가드 1), Ruff 통과, mypy 통과, 브라우저 E2E **31종** 녹색(4개씩 105초; `scouts.py`가 80초로 가장 길다), 자동 대전 1,150판(Epic·Scouts·Go to 11·전 확장 조합) 실패 0. action codec **v124**(Epic), 관측 **v28**(Epic, 길이 4,611), mlp_slots `SLOT_KEYS` 1,140(`conflict:economic_supremacy`). master의 v121~v123·v26~v27은 Scouts·Round Start·대안 C의 번호이고 Epic이 v124·v28이다(버전 주석에 둘 다 있다). 그 앞 2026-09-30(OQ-076 대안 C 뒤, Mac mini, master)의 기준 결과는 **pytest 2,851개 통과**(실측 약 145초), Ruff 통과, mypy 통과, 브라우저 E2E **31종** 녹색(4개씩 93초). action codec **v123**(`choose_subcommittee` 템플릿 추가), 관측 v27 그대로, mlp_slots `SLOT_KEYS` 1,139. **미병합 `epic-game-mode`(v121·v26)는 병합 때 v124·v28로 올린다.** 그 앞 2026-09-29 밤(Round Start 규칙 순서, Scouts D8 3차, 게임 전체 선택 불가 표시 1단계 뒤, Mac mini, master `cd479ba`)의 기준 결과는 **pytest 2,832개 통과**(실측 약 145초), Ruff 통과, mypy 통과, 브라우저 E2E **31종** 녹색(`unavailable.py` 추가; 4개씩 86초). action codec **v122**(Round Start 순서와 Scouts 변경으로 저장 재생이 달라짐, 템플릿 무변경), 관측 **v27**(`scouts_top_up` frame 종류 제거, 방어 결정의 벡터가 Round Start로), mlp_slots `SLOT_KEYS` 1,139. **미병합 `epic-game-mode`(v121·v26)는 병합 때 v123·v28로 올린다.** 그 앞 2026-09-29 저녁(Arrakeen Scouts D8 2차 반영 뒤, Mac mini, master `be826d9`)의 기준 결과는 **pytest 2,765개 통과**(실측 약 138초), Ruff 통과, mypy 통과, 브라우저 E2E **30종** 녹색(4개씩 86초); codec·관측은 아래와 같다. 그 앞 2026-09-29(Arrakeen Scouts D8 일괄 검토 1차 반영 뒤, Mac mini, master)의 기준 결과는 **pytest 2,734개 통과**(실측 약 138초), Ruff 통과, mypy 통과, 브라우저 E2E **30종** 녹색(4개씩 94초). action codec **v121**, 관측 **v26**(frame kind `scouts_top_up`을 끝에 덧붙였을 뿐이라 옵션을 끈 게임의 인코딩은 그대로), mlp_slots `SLOT_KEYS` 1,140. **미병합 브랜치 `epic-game-mode`도 codec v121·관측 v26을 쓴다: 병합할 때 한쪽을 v122·v27로 다시 올린다.** 그 앞 2026-09-28(Go to 11 옵션 병합 `1c86685` 뒤, Mac mini, master)의 기준 결과는 **pytest 2,714개 통과**(실측 약 140초), Ruff 통과, mypy 통과, 브라우저 E2E **30종** 녹색(`setup_options.py` 추가; 4개씩 94초). action codec **v120**(새 설정 필드가 모든 state hash를 바꿔 옛 저장이 버전 오류를 받게 한 것뿐, 카탈로그 무변경), 관측 v25 그대로. `ext-v111/C/iteration_07081.pt`는 v120에서도 열리고 Go to 11 게임을 불법 행동 0으로 둔다. 그 앞 2026-09-28(Arrakeen Scouts M15 슬라이스 1~10 뒤, Mac mini, master `01da380` + 문서 커밋)의 기준 결과는 **pytest 2,694개 통과**(실측 약 135초), Ruff 통과, mypy 통과, 브라우저 E2E **29종** 녹색(`scouts.py` 추가; 4개씩 99초). action codec **v119**, 관측 **v25**(길이 4,587; Scouts 칸은 옛 칸 뒤에 붙어 옵션을 끈 게임의 앞 4,327칸은 v21과 바이트 그대로), mlp_slots `SLOT_KEYS` 1,139(slot 관측 v25). 옵션을 끈 룰셋의 base 카탈로그는 4,425 그대로다. 실제 체크포인트 `ext-v111/C/iteration_07081.pt`와 `T/latest.pt`는 새 버전에서 그대로 열린다. 그 앞 2026-09-27 밤(garrison 토큰·배치 조절기 자리 `72fe33f` 뒤, Mac mini, master)의 기준 결과는 **pytest 2,550개 통과**(실측 약 119초), Ruff 통과, mypy 통과, 브라우저 E2E 28종 녹색(4개씩 77초). 그 앞 2026-09-27 저녁(카탈로그 종류 조회·CHOAM 계약 구성 정정·Tleilaxu UI 둘·Conflict 유닛 토큰 병합 `55beed1` 뒤, Mac mini, master)의 기준 결과는 **pytest 2,548개 통과**(실측 약 157초), Ruff 통과, mypy 통과, 브라우저 E2E **28종** 녹색(`catalog_kinds.py` 추가; 4개씩 80초). action codec **v111**, 관측 **v21**(계약 identity 넷 교체, 길이 4,327 불변; 아래 요약). 그 앞 2026-09-27 오후(`repr-slots`·`learner-legal` 병합 `35eb090` 뒤, Mac mini, master)의 기준 결과는 **pytest 2,542개 통과**(2,514 + slot 네트워크 18 + learner 10, 실측 약 119초), Ruff 통과, mypy 통과. 그 앞 2026-09-27 아침(`ui-work` 병합 `08b5003` 뒤, Mac mini, master)의 기준 결과는 **pytest 2,514개 통과**, Ruff 통과, mypy 통과, 브라우저 E2E **27종** 녹색(`rehearsal.py` 제외; UI 7~10단계가 10종을 더했다 — 아래 요약). 2026-09-27 새벽 늦게(Agent box Spy의 거절과 tips-v1 복원 가드 병합 뒤, Mac mini, master)의 기준 결과는 **pytest 2,379개 통과**(2,374 + 거절 3 + 복원 가드 2, 실측 약 110초), Ruff 통과, mypy 통과, 브라우저 E2E 5종(`log_words`·`turn_end`·`staged_turn`·`lang`·`board_tokens`) 녹색. 그 앞 2026-09-27 새벽(OQ-070 — recruit한 Commander의 배치 몫 — 병합 뒤, Mac mini, master)의 기준 결과는 **pytest 2,374개 통과**(실측 약 98초), Ruff 통과, mypy 통과. 그 앞 2026-09-26 밤 늦게(OQ-065 판정 고정과 자기 trash 경로의 recruit guard 병합 뒤, Mac mini, master)의 기준 결과는 **pytest 2,361개 통과**(2,350 + OQ-065 1 + guard 9 + Eliminate Allies 자기 trash 1, 실측 약 120초), Ruff 통과, mypy 통과. 그 앞 2026-09-26 밤(recruit 집계 전수 수정과 OQ-064 판정 병합 뒤, Mac mini, master)의 기준 결과는 **pytest 2,350개 통과**(실측 약 102초), Ruff 통과, mypy 통과. 그 앞 2026-09-26 저녁(OQ-066·068·069 사용자 판정 반영 뒤)은 **pytest 2,304개 통과**(실측 약 98초), Ruff 통과, mypy 통과. 그 앞 2026-09-26(카드·보드 전사 전수 감사와 통합 리뷰 수정 병합 뒤, Mac mini, master)의 기준 결과는 **pytest 2,279개 통과**(전사 정정 뒤의 1,975 + 감사·리뷰 수정 304, 실측 약 98초), Ruff 통과, mypy 통과. 그 앞 2026-09-25(Bloodlines 카드면 전사 정정 셋 — Chani·Fenring Signet, Storms in the South — 과 평가 문제집 재채굴 뒤, Mac mini, master)의 기준 결과는 **pytest 1,975개 통과**(expert iteration 병합 뒤의 1,972 + 이 세션 3, 실측 약 87초), Ruff 통과, mypy 통과. 그 앞 2026-09-24(확장 더미의 되돌리기 구멍 수정 뒤, Mac mini, master)의 기준 결과는 **pytest 1,950개 통과**(+12, 실측 약 84초), Ruff 통과, mypy 통과. 그 앞 2026-09-24 새벽(턴 종료 한 번 누르기 통일과 연속 되돌리기 저장 수정 뒤, Mac mini, master)의 기준 결과는 **pytest 1,938개 통과**(이 세션 +29, 실측 약 80초), Ruff 통과, mypy 통과, 브라우저 E2E 16종 녹색(`rehearsal.py` 제외; 새 `turn_end.py` 67). 그 앞 2026-09-24 저녁(expert iteration v1 병합과 탐색 후보 5개 뒤, Mac mini, master)의 기준 결과는 **pytest 1,972개 통과**(실측; 이 세션이 라벨·증류 테스트 20개와 탐색 테스트 2개를 더함), Ruff 통과, mypy 통과. 그 앞 2026-09-24 아침(밤샘 실행과 말단 척도 수정 뒤, Mac mini, master)의 기준 결과는 **pytest 1,939개 통과**(실측; 그 사이 다른 세션의 UI·저장 테스트와 이 세션의 말단 보상 테스트 1개가 더해짐), Ruff 통과, mypy 통과. 그 앞 2026-09-23 저녁(Mac mini의 탐색 비용 세션을 WSL 노트북의 tip census·평가 문제집 작업과 merge한 뒤, Mac mini, master)의 기준 결과는 **pytest 1,909개 통과**(실측, 약 80초; merge 전 Mac mini 쪽은 1,816개, WSL 쪽의 마지막 기록은 1,903개 — 그 뒤 WSL 커밋들과 이 세션의 잘린 head 읽기·효과 순서 스위치·순환 방지 테스트 3개가 더해졌다), Ruff 통과, mypy 통과. 그 앞 2026-09-23(tip census 뒤, WSL 노트북, master)의 기준 결과는 **pytest 1,885개 통과**(tip census 테스트 71개 + Influence 4 재도달 회귀 테스트 1개; 그 앞 `5bbad3a`까지는 1,813개), 실측. 이어서 비교 도구 테스트 1개로 1,886개, 평가 문제집 테스트 17개로 **1,903개 통과**(실측, 약 4분 40초) — 그 전체 실행에서 `tests/server/test_events_app.py::test_a_stream_closed_before_its_first_byte_is_not_a_server_error`가 한 번 실패했고(1,885 통과, 실패 메시지는 남기지 못함) 단독으로는 3회 모두 통과했다: 소켓을 곧바로 닫는 경합 테스트라 부하에서 흔들리는 후보다, Ruff 통과, mypy 통과. census 테스트가 스위트에 약 40초를 더한다(전체 약 4분). 2026-09-22 새벽(패널 문구의 용어집 잔재 뒤, Mac mini, 브랜치 `ui-glossary`)의 기준 결과는 **pytest 1,806개 통과**(같은 날 M10 평가 역전 수정 회귀 테스트 1개 추가, 실측)(한국어 텍스트의 용어집 영어 가드 1개), Ruff 통과, mypy 통과, 브라우저 E2E 15종 녹색. 그 앞 2026-09-21 밤(보드 위 사다우카 지휘관과 쌓인 Spy 뒤, Mac mini, 브랜치 `ui-commanders`)의 기준 결과는 **pytest 1,804개 통과**(카탈로그 테스트에 단언만 더함), Ruff 통과, mypy 통과, 브라우저 E2E 15종 녹색(`board_tokens.py` 187 → 203). 그 앞 2026-09-21 밤(UI 잔여 세 항목 세션 뒤, Mac mini, 워크트리 `ui-leftovers`)의 기준 결과는 **pytest 1,804개 통과**(라벨 표를 언어 전환에 등록했는지 보는 가드 1개 추가; 행동·이벤트 라벨 가드는 넓어졌지만 수는 그대로), Ruff 통과, mypy 통과, **브라우저 E2E 15종 녹색**(`log_words.py` 추가, `seats.py` 21 → 31, `remote.py` 57). 그 앞 2026-09-21 밤(Mac mini의 M10 순위 보상·대조군 세션 3커밋을 WSL 노트북의 UI 작업 위로 rebase한 뒤, Mac mini)의 기준 결과는 **pytest 1,803개 통과**(WSL의 1,802개 + 평가 seed 대역 테스트 1개), Ruff 통과, mypy 통과. rebase된 커밋은 UI 파일을 건드리지 않아 브라우저 E2E는 다시 돌리지 않았다. 그 앞 2026-09-21 저녁(보드 칸 테두리 세션 뒤, WSL 노트북)의 기준 결과는 **pytest 1,802개 통과**(칸 hotspot이 인쇄된 흰 테두리 하나의 크기, 관측소 원판이 칸 테두리와 겹치지 않음 — 레이아웃 테스트 2개 추가), Ruff 통과, mypy 통과, 브라우저 E2E 14종 녹색(`board_tokens.py`에 hotspot 테두리·Agent·Spy 말 검사 추가). 그 앞 2026-09-21 오후(UI 후속 세션 뒤, WSL 노트북)의 기준 결과는 **pytest 1,800개 통과**(언어 가드 `tests/server/test_i18n.py` 7개; supply 부족 `shortfall` 단언은 기존 테스트에 더함), Ruff 통과, mypy 통과, **브라우저 E2E 14종**(`help.py`·`lang.py` 추가). 그 앞 2026-09-21(UI 개선 세션 뒤)의 기준 결과는 **pytest 1,793개 통과**(UI 세션이 더한 7개: 용어 가드 3, event kind 가드 2, 지원하지 않는 룰셋의 400 1, action label 가드 1), Ruff 통과, mypy 통과. **브라우저 E2E는 8종 → 12종**이다(`endgame.py`·`narrow.py`·`columns.py`·`seats.py` 추가, `scripts/e2e/README.md`). 그 앞 2026-09-20(M10 자 만들기 세션 뒤)은 pytest 1,786개 통과이고 action codec은 **`ACTION_CODEC_VERSION = 107`**(기본 4,439개, CHOAM 4,729개, `promo_cards` 옵션 시 4,539/4,829개, `immortality` 옵션 시 9,324개, `promo_cards`+`bloodlines`는 10,580개, promo+Bloodlines+Tech는 13,828개, CHOAM+Bloodlines는 11,228개, 다섯 옵션을 다 켜면 32,987개 — v106은 Branching Path의 `trash_intrigue_for_agent_card`(Intrigue 사본마다)와 Imperial Privilege 행동의 이름 변경(`trash_intrigue_for_imperial_privilege`)·c7r3의 `trash_intrigue_for_research_bonus`, v107은 공용 `spy_placement` frame의 세 행동을 Bloodlines 없는 카탈로그에도 넣는다(+27); 형식 2 체크포인트는 행동 이름으로 이관된다 — 아래 세션 요약). 그 앞 기준선: 2026-09-19(두 기기의 2026-09-18 작업을 merge한 뒤)의 기준 결과는 pytest 1,768개 통과(같은 날 오후 학습률 재개 테스트 1개가 더해진 값; 그 앞 1,767은 Windows PC의 M10 PPO 슬라이스·A/B 세션 1,752개에 Mac mini의 보드 토큰·원판·보드 조각·에셋 버전 테스트 12개를 더한 값을 merge 뒤 실측했고, 같은 날 카탈로그의 Graft 표시 테스트 1개와 서버의 전투력 미리보기·남은 Persuasion 테스트 2개가 더해졌다; `assets` symlink가 없는 머신은 `tests/unit/display/test_images.py`의 에셋 대조 테스트 1개만 skip되어 1,767 통과 + 1 skip이다 — 2026-09-17 밤 symlink를 떼고 실측한 관계이며, 그 전 판들이 옛 기준선 1,489에 덧셈으로 유도해 적던 "1,6xx + 1 skip"은 실측과 맞지 않았다; `app.js`를 고쳤다면 pytest로는 부족하고 브라우저 E2E [`scripts/e2e/`](../../scripts/e2e/README.md)를 돌린다; `train` extra가 없으면 `tests/unit/training/test_torch_policy.py`가 추가로 skip된다), Ruff 통과, mypy 통과다. 현재 action codec은 `ACTION_CODEC_VERSION = 105`(기본 4,371개, CHOAM 4,657개, `promo_cards` 옵션 시 4,471/4,757개, `immortality` 옵션 시 9,326개 — graft 배치 변형과 카드 사본이 늘 때마다 커진다; `bloodlines`·`tech_module` 옵션은 별도 카탈로그로 훨씬 크고, `promo_cards`+`bloodlines`는 10,513개, promo+Bloodlines+Tech는 13,759개, CHOAM+Bloodlines는 11,156개, 다섯 옵션을 다 켜면 32,991개 — v105는 Chani의 Fedaykin Maneuver `retreat_leader_troops`의 Commander share count를 `retreat_intrigue_troops`처럼 19까지 늘려 Bloodlines 카탈로그마다 +28(2026-09-18, 아래 세션 요약; 옛 v104 체크포인트는 형식 2로 새겨 두면 이관된다), v98은 CHOAM+Bloodlines 카탈로그에만 contract token 8개의 행동과 `trash_intrigue_for_contract`를, v99는 `recall_conflict_agent_for_imperial_privilege`를, v100은 모든 카탈로그에 `skip_intrigue_acquisition`과 Change Allegiances의 세 번째 option을, v101은 Immortality 카탈로그에 `play_conflict_end_intrigue`(Harvest Cells 2장)·`decline_conflict_end_intrigue`를, v102는 Bloodlines+Immortality 카탈로그의 `give_intrigue_card`/`trash_intrigue_hand_card`/`trash_intrigue_for_contract`에 빠져 있던 Immortality Intrigue 사본을 더한다 — 소크가 적발; v103은 모든 카탈로그에 `use_intrigue_effect(section=0/1)`·`finish_intrigue_effects`를 더하고 Change Allegiances의 option을 하나로 되돌린다; v104는 Bloodlines 카탈로그의 `retreat_intrigue_troops` unit count를 12에서 12+7로 넓힌다 — Commander는 12개 병력과 별개 구성물이라 Conflict 유닛이 19까지 가고 Tactical Option이 그 전부를 제시하는데 카탈로그가 12에서 끊겨 있었다, 병렬 수집이 적발, 카탈로그마다 +28)이고, 관측은 `OBSERVATION_VERSION = 20`의 4,327-int 전체 게임 인코딩이다(v6~v9는 Bloodlines·Tech Module 세그먼트를 더한 것, v10은 Bloodlines 프로모 Ruthless Leadership의 identity 1개, v11은 Immortality 카탈로그의 Imperium 25·Intrigue 11 identity, v12는 Experimentation·Tleilaxu 19 identity와 Bene Tleilax board 세그먼트, v13은 round 한정 Reveal Persuasion과 Combat Intrigue 좌석, v14는 Imperium Ceremony가 peek한 Intrigue 두 장(소유자 전용), v15는 Chairdog의 반환 대기와 Usurp의 빌린 Row 카드(좌석 scalar 49→51), v16은 Bloodlines contract token 8개의 identity(contract 세그먼트 11개 × 8 = +88), v17은 frame 종류 `conflict_end_trigger`, v18은 `intrigue_effects` 추가로 decision kind index가 이동, v19는 Long Live the Fighters의 두 단계 pick이 전용 frame 종류 `LONG_LIVE_FIGHTERS`로 옮겨져 decision kind index가 다시 이동(v17~v19는 모두 길이 불변), v20은 OQ-059의 보류된 contract 아이콘 좌석 scalar 1개(좌석 scalar 51→52, +4 int); 옵션을 끈 룰셋에서는 새 칸이 전부 0이지만 길이가 달라져 v8 이전 체크포인트는 거부된다) ([`rl-environment.md`](../rl-environment.md)). 보드 22칸 완결 + 즉시 공개 + `fab266f`/`e6fc298` 수정 + sweep 확장(`853ecd4`) 반영 후의 교차 소크는 random 룰셋당 2,000판 + heuristic 룰셋당 1,000판(둘 다 `--rotate-leaders`) + draft 두 policy 각 룰셋당 500판, 전부 `--soundness-interval 25`를 켠 총 7,000판이 실패 0으로 통과한 상태다(2026-09-01, 아래 세션 요약. 그 전 단계에서는 random 룰셋당 3,000판 비회전 소크도 실패 0이었다).

## 현재 구현 기준선

다음은 2026-09-20 당시의 범위 요약이며, 최신 병합·검증 기준은 문서 상단을 따른다. 그날 마지막 커밋은 **전 좌석 AI 게임 관전**(`ac8cdeb`, 리플레이 검토의 자동 재생; 아래 세션 요약)이고, 그 앞이 같은 날의 **Staban Tuek draft pick 되돌리기 수정**(`8b6454e`, 서버 되돌리기 경계만; 아래 세션 요약)이고, 그 앞의 커밋 묶음은 같은 날 새벽의 **보드 조각의 인쇄 자리 배치·아이콘 전사 정정**(master 직접 커밋 4건 + 문서; 아래 세션 요약: Control·bonus spice·Maker Hooks·Alliance token의 인쇄 자리, Trash-Intrigue 아이콘 세 곳, Spy 배치 의무, Influence 4 보너스 — codec v107)이고, 그 앞의 엔진 커밋 묶음은 2026-09-16의 **공간 표 강등 마감 측정·수준 0.6 채택·OQ-060 확정**(master 직접 커밋 5건; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](../evaluation/baseline-2026-09-10.md) 18절(g)·(h))이고, 그 앞이 2026-09-11의 **보드 공간 표 상위 세 칸 강등 + OQ-060**(master 직접 커밋 2건: `94545a0` OQ-060 Influence 선택 소멸, 그리고 표 강등·Tech 특례 제거·문서; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](../evaluation/baseline-2026-09-10.md) 18절; **커밋 트리 확인 셀과 강등 수준 맞대결은 미완**)이고, 그 앞이 같은 날의 **Tech tile 가치표 A/B(기각)**(master 직접 커밋 1건; 코드 변경은 `HeuristicAgent`·`score_action`의 `tech_bonuses` A/B 슬롯과 테스트 1건뿐이고 `_TECH_BONUSES` 표는 그대로다; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](../evaluation/baseline-2026-09-10.md) 17절)이고, 그 앞이 같은 날의 **Tech Module 공간 표 A/B(기각)**(master 직접 커밋 1건; 코드 변경은 `heuristic_agent.py`·`registry.py`의 주석과 docstring뿐이고 배선은 그대로다; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](../evaluation/baseline-2026-09-10.md) 16절)이고, 그 앞이 2026-09-10 심야의 **확장 공간 순위·엔진 결함 3건**(master 직접 커밋 `2fa94d1`/`86c634b`/`aa46132`와 문서; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](../evaluation/baseline-2026-09-10.md) 15절)이고, 그 앞이 같은 날 심야의 **`agent_turn` spent-card 동점**(master 직접 커밋 `69bf880`와 문서; 아래 세션 요약, 수치는 [evaluation/baseline-2026-09-10.md](../evaluation/baseline-2026-09-10.md) 14절)이고, 그 앞이 같은 날 심야의 **처리량 회귀 귀인**(master 직접 커밋 `ab48e0c`/`88c0ef7`/`615e7ed`와 문서; 아래 세션 요약, 수치는 [evaluation/throughput-2026-09-10.md](../evaluation/throughput-2026-09-10.md))이고, 그 앞이 같은 날 밤의 **보드 공간 재정비·잠재 결함 3건**(master 직접 커밋 4건, codec v103→v104; 아래 세션 요약)이고, 그 앞이 2026-09-10의 **문서 정정·학습 룰셋 배선·Long Live frame**(master 직접 커밋 `e0e364b`/`8b039dc`/`6c89a56`; 아래 세션 요약)이고, 그 앞이 2026-09-09 저녁의 **baseline agent Immortality 가치·엔진 교착 수정**(master 직접 커밋 3건 `21b5318`/`85bd179`/`3987126`; 아래 세션 요약, 세부는 [implementation-audits/immortality.md](../implementation-audits/immortality.md) "baseline agent의 Immortality 가치" 절)이고, 그 앞이 같은 날의 **Bloodlines contract token 8개**(master 직접 커밋 `Play`/`Document` 쌍; 아래 세션 요약, 세부는 [implementation-audits/bloodlines.md](../implementation-audits/bloodlines.md) "Contract token" 절)이고, 그 앞이 2026-09-08의 **M13 Immortality**(master 직접 커밋, 슬라이스 1~6의 `Play`/`Document` 쌍과 UI·소크 수정; 아래 세션 요약, 세부는 [implementation-audits/immortality.md](../implementation-audits/immortality.md))이고, 그 앞이 같은 날의 **구현 마감 슬라이스**(master 직접 커밋 5건 + 문서)이다: OQ-047(Endgame tiebreaker에 garrison Commander 포함), Bloodlines 프로모 Ruthless Leadership(`promo_cards`+`bloodlines`, 관측 v10·codec v95), 서버 AI 좌석의 `rollout`/`checkpoint:` 연결, UI의 Agent 토큰 이동 애니메이션과 1700px 이하 오른쪽 패널 1열, Bloodlines+Tech 커버리지 census. 그 앞이 2026-09-07 밤의 **M12 슬라이스 7 마감**(master 직접 커밋 5건; 아래 세션 요약)이다: 웹 UI의 Commander·Skill·Ixian Embassy·Tech tile 표시, heuristic의 tile별 가중치와 rollout 자산 가치, `--bloodlines --tech-module` 교차 소크 7,000판 실패 0(적발한 결함 3계열 수정, OQ-046), 관측 v9 기준 학습 smoke, 저장 문서의 모듈 플래그 수정 — 이로써 **M12 완료**. 그 앞이 같은 날 저녁의 **M12 슬라이스 6 Tech Module**(master 직접 커밋 4건 + Navigation 대기열 수정 1건; 아래 세션 요약)이다: Ixian Embassy와 Tech tile 18장의 획득·할인·Flip·획득 효과·능력, Tech 전용 Imperium 2장·Intrigue 2장, Kota Odax of Ix(관측 v9, codec v91→같은 날 밤 사용자 검토로 v94, 판정 OQ-040~045). 그 앞이 같은 날의 **Bloodlines 확장 슬라이스 1~5**(`bloodlines` 브랜치를 master 쪽에서 머지, `dbd9b73`; 아래 세션 요약)이다: `RulesetConfig(bloodlines=True, tech_module=True)` 옵션 골격, Sardaukar Commander와 Skill 7종, Bloodlines Conflict 2장, Imperium 25종·Intrigue 16장, Leader 8종(Tuek's Sietch board space, Twisted Intrigue 12장, Navigation 10장 포함). 이로써 Bloodlines 구성물 전부가 play된다. 그 앞이 2026-09-06 밤의 **전투력 단일 값·표시 정리**(`rules/strength.py`의 매 step 갱신, 관측 v5, 전투력 토큰의 0 네모·`+20` 면, 좌석 패널의 검=전투력; 아래 세션 요약)이고, 그 앞이 같은 날 저녁의 **M11 UI 개선 묶음**(`ui-work` 워크트리 브랜치 12건: 호버 팝오버, 정적 파일 재검증, Conflict·Contract·Conflict 덱의 보드 슬롯 표시, garrison·Conflict 병력 칩, 공용 카드 열의 세로 배치, 행동 목록 포커스 정렬, 행동 로그 턴 카드·중립 카드, 오른쪽 패널 2열; 아래 세션 요약)이고, 그 앞이 같은 날의 **M10 슬라이스 1 학습 루프**(`train` extra, `training/network.py`·`torch_policy.py`·`checkpoint.py`·`learner.py`·`loop.py`, `dune-imperium-train`; 아래 세션 요약)이고, 그 앞이 같은 날의 **M9 슬라이스 3 lockstep self-play 러너**(`training/selfplay.py`·`training/policy.py`, `dune-imperium-selfplay`)이며, 그 앞이 같은 날의 **M9 슬라이스 2 rollout baseline**(`agents/rollout_agent.py`, `agents/determinize.py`, `StateAgent` 계약)이며, 그 앞이 같은 날의 **M9 슬라이스 1 대회 도구**(`dune-imperium-tournament`, `evaluation/` 패키지, `agents/registry.py`)이며, 그 앞이 2026-09-05의 **OQ-029 판정 구현**(Combat 배치의 회수·분할과 명시적 Agent turn 종료, codec v89; 아래 세션 요약)이고, 그 앞이 2026-09-04의 **조건 판정 시점 정리**(OQ-028: 미룬 Reveal 선택의 조건 재성립, Agent box 조건의 해결 시점 판정, Reveal 자동 조건부 이득의 늦은 지급; 아래 세션 요약)이고, 그 앞이 같은 날의 Reveal 선택형 효과 순서 자유화(`defer_reveal_choice`/`resume_reveal_choice`, codec v88)이며, 그 앞이 2026-09-03 심야의 자율 작업 5건(카드 Agent box 아이콘 분리 codec v87, 턴 종료 확인·되돌리기 가능 표시·보드 마커 UI)이며, 그 앞이 같은 날 밤의 **보드 공간 아이콘 분리**(인쇄 아이콘마다 `resolve_board_effect(effect=<key>)` 행동 하나, codec v86, OQ-027)이며, 그 앞의 기능 커밋 묶음은 2026-09-01 검증 강화 캠페인의 보드 공간 완결 슬라이스들이다: `d7703ef`(Dutiful Service CHOAM contract), `e141492` (Shipping, codec v80), `63a8994`(Desert Tactics, codec v81), `49a5bb6` (Imperial Privilege, codec v82, OQ-023), `78fa1a3`(Secrets chance 강탈, SECRETS_STEAL frame), `881d88b`(Reveal 중 hand 진입 카드의 FAQ p. 3 즉시 공개, OQ-015(c) 해소), `fab266f`·`e6fc298`(소크가 적발한 mid-frame trash 충돌 두 계열의 OQ-022 확장 수정). 이로써 **4인 보드 22칸 전부가 배치·해결 가능**하고 Reveal 중 draw/hand-acquire Plot 보류도 사라졌다. 그 앞은 `4c175d1`(카드 이미지 캐시 다운로드 스크립트)이고, 그 앞에 UI 효과 표시 작업의 `3e2ae8f`(행동 효과 미리보기 + 전체 행동 라벨), `d275a66`(보드 공간 패널·popover·카드 이미지), `d34a2d1`(/catalog 효과 텍스트·이미지), `a4befd4`(display 패키지), `3c1cc69`(정적 보드 효과 테이블), 그리고 M11의 `e44900a`(저장/불러오기/검토 브라우저 UI), 슬라이스 5 서버 API `8ab3cd2`, 브라우저 UI `42be883`, FastAPI 세션 서버 `4fbd751`, Leader draft `c0c1795`, Treacherous Maneuver OQ-022 수정 `d70b353`, 슬라이스 1 묶음(`1a449f4`+`7a53c8f`+`ac4d6d4`)이 있다. 마일스톤 현황: **R0~M8, M11 완료, M9 완료(대회 도구·rollout baseline·self-play 러너, 2026-09-06)**(M6 콘텐츠, M7 완주 검증, M8 CHOAM, M11 사람용 로컬 웹 UI — 슬라이스 7까지, 완료 판정 근거는 `implementation-plan.md` M11 절; Uprising 프로모 3장은 2026-09-03 저녁 `promo_cards` 옵션으로 구현 완료), **M10 진행 중(슬라이스 1 학습 루프 완료)**, **M12 완료(2026-09-07 밤, 슬라이스 7까지)**.

- R0-M4는 완료됐다. 공식 규칙 자료, 엔진 커널, 4인 setup, 한 라운드 수직 조각, actor-neutral action codec과 PettingZoo AEC 계약이 있다.
- M5의 주요 시스템은 연결돼 있다. Influence/Friendship/Alliance, Agent와 Reveal, Spy/Infiltrate/Gather Intelligence, 개인 덱 reshuffle chance, Combat 순위와 보상, sandworm·Shield Wall·control, Makers·Recall, Endgame window와 게임 종료까지 실행할 수 있다.
- 시작 카드 7종, Reserve 2종, 기본 Imperium 50종, CHOAM 전용 Imperium 4종 모두에 완전한 play data가 있다(`implementation-audits/personal-cards.md`).
- CHOAM standard contract 20장(18종; Espionage I·Harvest 3+는 두 장)의 시장·완료·보상과 CHOAM 전용 Imperium 4종이 연결돼 있다(`implementation-audits/contracts.md`). 2026-09-27 전까지는 Rise of Ix 전용 타일 4장이 Spice Refinery I·II와 두 번째 사본 둘 대신 들어 있었다(아래 요약).
- Intrigue 44장은 39개 identity 전부가 effect DSL로 전사돼 실제 play된다 (Intrigue 덱 완결). Plot은 소유자의 `turn`/`agent_effects`/`reveal` frame에서, Combat은 `combat_intrigue` frame의 priority 보유 참가자에게 제시된다. 선택이 필요한 효과는 `intrigue_choice` frame의 슬롯으로 순차 해결한다. Impress와 Inspire Awe의 비용 상한 획득은 `AcquireCardUpTo` 슬롯으로 Row/Reserve에서 가져오며, acquire box의 Spy 배치는 카드 해결 후 `acquisition_spy` frame을 재사용한다. Call to Arms는 face-up trigger 카드로, play하면 공개 `intrigue_faceup` 존에서 대기하다 소유자의 Reveal turn 획득마다 발동하고 그 Reveal 종료 시 만료된다(OQ-016, `rules/intrigue_triggers.py`, `implementation-audits/intrigue.md`). Distraction과 Coercive Negotiation은 2026-10-03부터(codec v129) face-up trigger가 아니라 "이번 turn에 unit 3개 이상 배치"를 조건으로 내는 Plot이다(`UnitsDeployedThisTurnAtLeast`, turn의 배치 최고치 `units_deployed_peak`; OQ-016 재판정).
- Intrigue deck 고갈 시 모든 draw 지점이 `pending_intrigue_draws` 큐를 거쳐 replayable reshuffle chance로 해결된다.
- 인쇄된 Leader 9종(기본 8 + CHOAM 전용 Shaddam)의 능력과 Signet Ring이 모두 play된다(`rules/leader_abilities.py`, `implementation-audits/leaders.md`). Lady Jessica의 flip 면은 `PlayerState.leader_face_id`, memory는 `memories`(troop 12개 불변식 포함), Feyd token은 `feyd_track_space`, Shaddam의 set-aside contract는 `GameState.sardaukar_contract_ids`로 공개 관측된다. 2026-08-30에 standard Contract manifest를 수정했다: Sardaukar II (Agent recall 보상)가 20장에 속하고, 이전에 있던 세 번째 High Council 타일은 Rise of Ix Tech 보상 타일의 오전사였다(`contracts.md` audit).
- 규칙 dispatcher는 `LEGAL_ACTION_PROVIDERS[FrameKind]`와 `ACTION_HANDLERS` 두 표로 동작한다(`refactoring-plan.md`).
- 코어 상태 머신과 replay는 전체 게임을 지원한다. `dune-imperium-sweep`으로 룰셋당 10,000판(총 20,000판) random 완주 sweep(매 전이 카드 보존·교착 검사, 표본 주기 관측 누출 검사, 게임별 replay 검증)이 실패 0으로 통과했다(2026-08-30, 400초/50 games/s).
- `run_random_game`이 FINISHED까지 실행해 `GameSimulation(state, standings, replay)`를 돌려주고, `dune_imperium_uprising_v1` PettingZoo adapter는 전체 게임을 한 episode로 실행한다(chance 내부 해결, 승자독식 zero-sum 종료 보상, 4,327-int 관측(v21), `choam_module`/`max_steps` 옵션). `run_random_round`와 debug CLI는 의도적으로 한 라운드 단위를 유지한다. 설계 근거는 [`rl-environment.md`](../rl-environment.md).
- 공식 Main, Board Guide, FAQ는 2026-08-27에 공식 리소스 페이지에서 다시 내려받아 `scripts/official-rule-sources.json`의 SHA-256과 모두 일치함을 확인했다. Bloodlines 룰북은 2026-09-07에 같은 방식으로 등록했다(`bloodlines`, 12쪽; 카드면은 비공개 에셋 저장소 `cards/en/bloodlines/`).
- Bloodlines(`RulesetConfig(bloodlines=True)`, 2026-09-07): 규범 근거 [`rules/bloodlines.md`](../rules/bloodlines.md), 구현 노트 [`implementation-audits/bloodlines.md`](../implementation-audits/bloodlines.md)와 [`implementation-audits/leaders.md`](../implementation-audits/leaders.md)의 Bloodlines 절. Sardaukar Commander(`rules/sardaukar.py`, `rules/strength.py`), 새 아이콘(Command (6+), Combat 아이콘, Spy with Deep Cover, Trash an Intrigue card), 상대 결정 frame(`rules/spy_moves.py`, `rules/unit_loss.py`), Leader 전용 모듈(`rules/tactics.py`, `rules/planetologist.py`, `rules/optional_trash.py`, `rules/navigation.py`), Leader 전용 board space(`tuek_sietch`, `BoardSpace.required_leader_id`), Twisted Intrigue·Navigation 카드는 Intrigue 스키마의 `twisted`/`navigation` 항목(공용 덱에는 절대 들어가지 않음). Tech Module(`tech_module=True`, 2026-09-07 저녁): `content/bloodlines/tech.py`의 tile 18장, `rules/tech.py`(Acquire Tech·Flip·Forbidden Weapons 선택·Suspensor/빚진 draw hook·Endgame 효과·Kota의 Secret Project)와 `rules/ornithopter.py`, Tech 전용 카드 3종(`tech_only`), Kota Odax of Ix(`LeaderDefinition.tech_only`). 공식 문서가 침묵하는 판정은 OQ-031~046(사용자 판정 OQ-031·032·035·036·037·038·043·045 포함)과 OQ-012 재검토에 있다. 슬라이스 7(같은 날 밤): UI 표시(`server/catalog.py`의 `skills`·`tech` 절, `display/bloodlines.py`, `app.js`의 좌석 패널·공용 열·보드 칩), heuristic `_TECH_BONUSES`, rollout `player_value`의 Bloodlines 자산, 교차 소크 7,000판 실패 0, 학습 smoke.

## 아직 완성되지 않은 경계

- (2026-09-01 해소) 보드 22칸 미구현 4~5칸과 OQ-015(c)의 Reveal 중 Plot 보류는 모두 구현됐다. `board_effect_is_implemented`와 UI의 "미구현 · 배치 불가" 배지는 미래 콘텐츠 대비 메커니즘으로 남아 있고, `tests/unit/rules/test_board_effects.py`의 pinned 집합은 이제 양쪽 룰셋 모두 빈 집합이다. Imperial Privilege의 recall 판정은 OQ-023 convention, Secrets의 무작위 강탈은 seeded `SECRETS_STEAL` chance frame이다.
- (2026-09-04 해소, OQ-028) 배치 시점 조건이 거짓이면 pending되지 않던 카드 효과 경계는 사라졌다. 이제 space 속성·Bond를 제외한 모든 인쇄 조건은 해결 시점에 판정한다.
- Objective와 battle icon 상호작용은 2026-08-30에 재감사를 마쳤다 (`implementation-audits/objectives.md`, OQ-005 RESOLVED). Combat 다중 후보 guard는 미래 콘텐츠 대비 tripwire로 남는다.
- Shaddam Corrino IV의 set-aside Sardaukar Contract 경로는 Leader 능력과 함께 남아 있다. OQ-010(2026-09-02 확정), OQ-011 경계는 확정 판정(`DECIDED`)으로 유지된다.
- 공식 문서가 침묵하는 규칙 판정은 [`rules/open-questions.md`](../rules/open-questions.md)에 있다. 2026-09-01 확정 캠페인과 같은 날의 사용자 검토를 거쳐, 2026-09-02에 OQ-010까지 확정돼 `DECIDED`/`RESOLVED`만 남았다가, 2026-09-04에 OQ-029(Conflict에 배치한 troop의 임의 회수·배치 분할)가 사용자 요청으로 `OPEN`으로 올라왔다가 2026-09-05 사용자 판정으로 `DECIDED`(회수·분할 허용, 소비된 조건은 예외)됐고 같은 날 구현했다. 2026-09-06에는 OQ-030(supply 부족으로 못 한 recruit의 소급 여부)이 `OPEN`으로 올라왔다가 같은 날 사용자 판정으로 `DECIDED`(해결 시점에 있는 만큼만 recruit, 부족분 소멸·소급 없음, `troops_recruit_short` 이벤트로 표시)됐다. 현재 콘텐츠에는 turn 중 troop을 supply로 돌려보내는 효과가 없고, Immortality의 lose a troop·specimen이 들어올 때도 같은 판정을 적용한다. `DECIDED`는 확정 프로젝트 판정으로 새 공식 룰북·FAQ(또는 OQ-022처럼 명시된 상위 근거)가 답을 줄 때만 다시 연다. 새로 발견되는 규칙 공백은 여전히 코드로 임의 확정하지 않고 그 문서에 먼저 기록하며, 규칙 동작을 바꾸기 전에는 반드시 `docs/rules/`의 문장을 인용한다([`lessons.md`](../lessons.md)).

콘텐츠(카드·리더·계약·Intrigue·보드 22칸)는 이제 4인 base+CHOAM 게임 범위에서 완결이다. Uprising 프로모 Imperium 3장(Arrakis Revolt, The Beast's Spoils, Pivotal Gambit)은 같은 날 저녁 `RulesetConfig(promo_cards=True)` 옵션 콘텐츠로 구현됐고(기본은 꺼짐), 공식 문서가 침묵하는 판정은 OQ-024~026 project convention이다. 남은 경계는 공식 문서가 침묵하는 판정을 기록한 convention(open-questions.md)과 위의 엔진 경계·미래 콘텐츠 tripwire들이며, 이들은 "미구현 콘텐츠"가 아니라 문서화된 프로젝트 판정이다.

## 다음 구현 순서

**현재 위치(2026-10-06 아침).** 탐색 AI 좌석·대회 `--leader-draft`·L3 재학습을 모두 병합했다(`9a03ac3e`, `8de02791`, `3e064dd9`; 위 2026-10-06 첫 요약). L3의 8081이 망 혼자서 앱 AI 어려움을 이기고(2:2 +17.9%p), 탐색 좌석으로는 앱 AI 셋을 상대로 72%를 이긴다. 이 Mac의 플레이 서버는 이 망을 탐색 AI로 쓴다. 학습이 찾은 엔진 결함(합법 행동 없는 결정)은 재현되지 않아 열려 있다. 병합한 master에서 **pytest 6,488개 통과**, Ruff·mypy(411파일) 통과(UI 변경은 탐색 좌석 병합 뒤 E2E 46종으로 확인했고, L3 병합은 학습 코드뿐).

**현재 위치(2026-10-05 밤).** 플레이 UI 좌석에 앱 AI(어려움·보통·쉬움)를 넣고 로컬 서버의 AI 기본값으로 삼았다(`e5a2b0d5`, 위 "플레이 UI에 앱 AI 좌석"). pytest 6,421개.

**현재 위치(2026-10-05 저녁).** app_ai를 모든 선택지(Immortality·Go to 11·Epic·프로모·드래프트는 충실 포팅, Bloodlines·Tech·Scouts는 앱식 확장)로 넓혀 heuristic 없이 두게 했고 master에 병합했다(`89f57fc5`, 위 2026-10-05 "app_ai를 모든 선택지로 확장"). 16개 조합에서 무작위 대체 0, pytest 6,389개. codec v135·관측 v30 그대로.

**현재 위치(2026-10-05).** 사용자 요청("앱식 heuristic 만들어서 A/B 돌려보자. 앱의 ai와 최대한 동일하게")으로 Steam 앱의 컴퓨터
상대를 그대로 옮긴 **`app_ai`**(`agents/app_ai/`, registry `app_ai`=Hard·`app_ai_medium`·`app_ai_easy`)를 만들어 master에 병합했다
(브랜치 `app-ai`; 설계·근거 [`app-ai-plan.md`](../app-ai-plan.md), 결과 [`evaluation/app-ai-2026-10-05.md`](../evaluation/app-ai-2026-10-05.md)).
사용자 결정: 로직·상수 437개·카드표까지 **모두 공개 저장소**에 둔다(2026-10-03의 "앱 상수 금지"를 이 agent에 한해 바꿈), 앱의 버그로
보이는 동작도 그대로 재현한다. 상수·아키타입 데이터는 `scripts/dwgr/app_ai_constants.py`·`app_archetypes.py`·`app_ai_emit.py`가 로컬
덤프에서 생성한다. 엔진·codec·관측은 바뀌지 않았다(v133·v30). 병합한 master(`776ac574`) 기준: **pytest 4,579개 통과**, Ruff·mypy(363파일) 통과. A/B(2:2, base·CHOAM,
지도자 회전): app_ai Hard가 heuristic을 좌석당 46.5% 대 3.5%로 이기고(시드 두 묶음 같음), Hard > Medium > Easy, 학습 망 greedy(7081)는
Hard에 13.5% 대 36.5%로 지고(규칙 변경 전 체크포인트, L3 재적응 안 함), search 1석은 Hard 셋을 상대로 48.5%를 낸다. 다음 후보: UI 좌석에
app_ai·search 넣기, 학습 상대에 app_ai 넣기(L3와 함께).

**현재 위치(2026-10-04).** 사용자가 Steam 디지털판 Dune: Imperium(4.1.x, IL2CPP v39)을 열어 OQ를 대조하자고 해서 `scripts/dwgr`로 읽고 OQ 77건을 대조했다(결과는 에셋 체크아웃의 `reference/dune-steam-app/`에만, git 무시; 앱은 공식 규칙이 아니라 보조 증거). 사용자는 다섯 건을 앱 방식으로 재판정했고(OQ-021·OQ-005·OQ-030·OQ-049·OQ-050) 이를 `app-rulings`로 구현해 master에 병합했다(`a55836fc`, 아래 2026-10-04 요약). 브라우저의 Go to 11·Epic 기본값은 그대로 둔다(사용자: "지금 세팅 유지"). 같은 날 저녁 둘째 묶음을 `app-rulings-2`로 구현해 병합했다(`2ad7a262`, 아래 2026-10-04 저녁 요약): OQ-013(deck discard도 발동), OQ-057 (15)(Emperor track Spy는 자기 turn 안의 의무 행동 `place_track_spy`), OQ-057 (2)(Interstellar Trade 증분 복원), OQ-012(Call to Arms는 카드 자신의 선택 뒤), OQ-061(Intrigue trash는 공용 버림 더미로). Usurp는 앱처럼 열에 남기는 안을 검토했지만 사용자가 원래 구현 유지를 골랐다(OQ-054). 밤에 셋째 묶음을 `app-rulings-3`로 병합했다(`57d4d085`): Litany Against Fear·Withdrawn은 turn의 첫 행동으로만(OQ-095 (6) 보강), Twisted 카드는 공용 버림 더미에 남고 다시 섞이지 않는다(OQ-097 확정). 이어서 앱 대조 마무리 점검(OQ 30건 재대조 + 적대 검증)으로 남은 차이를 정리하고 사용자 판정 셋(OQ-029: 효과 retreat·손실은 배치 한도를 돌려주지 않음, OQ-054: Usurp로 빌린 카드는 어디서도 in play가 아님, OQ-058: 줄이 나뉜 Intrigue는 한 줄 이상 써야 끝남)과 오래된 문서를 `app-rulings-4`로 병합했다(`42228e41`). **처음 목적(Steam 앱과 OQ 대조)은 끝났다.** 남은 선택: 앱의 카드·보드 정의와 우리 전사를 전수 대조할지(예상 약 3시간·subagent 토큰 500만~1,000만, 사용자 결정 대기). 다음 codec 번호는 **v134**, 관측은 **v30**. 아직 푸시하지 않았다(사용자 몫). 2026-10-02의 남은 일(C1·C2, L3 재적응)은 그대로다.

**현재 위치(2026-10-02).** 작업 배분 표의 **L1(Agent 턴은 "턴 종료"로만 닫기)과 L2(자동 처리 → 결정 창)를 이 Mac의 Claude 세션이 끝내 한 번에 master에 병합했다**(사용자 2026-10-02: "병합은 L2 끝내고 한 번에"; 아래 "2026-10-02 L2" 요약). L1은(워크트리 `explicit-turn-end`, 아래 "2026-10-01~02 L1" 요약; [OQ-095](../rules/open-questions.md)). 착수 때의 사용자 답: Q1 턴 넘기기 카드는 카드가 턴을 끝낸다("카드 효과로 턴 넘김 버튼을 눌렀다면 그건 턴 종료를 누른거랑 같으니까"; 서버도 추가 누름 없이 넘긴다), Q2 v111 재적응은 **병합 뒤 돌린다**(L3; 몇 시간 실행 전에 다시 묻는다). 다음 codec 번호는 **v130**(2026-10-03 Distraction·Coercive Negotiation의 play 조건 재판정이 v129를, 같은 날 저녁 Epic setup Intrigue의 draft 시점 수정이 v128을 썼다; 그 앞 병합 뒤 확인 셋이 v126을, 그 리뷰가 찾은 원래 결함 — Combat Intrigue 카드가 창을 남기면 연속 pass를 다시 세지 않던 것 — 의 수정이 v127을 썼다, [OQ-003](../rules/open-questions.md)), 관측은 v28. L2 끝에 물은 확인 셋은 같은 날 반영했다(아래 L2 요약의 "병합 뒤 사용자 확인"). C1·C2(클라우드 몫)는 아직 아무도 시작하지 않았다(2026-10-02 `git fetch` 기준 원격 브랜치 없음). 같은 날 Codex 세션의 UI 11단계(보드 중심 테이블·행동/기록 따로 스크롤·시작 화면, `codex/ui-table-refresh`)를 master에 병합했다(화면만, 아래 "UI 11단계" 요약).

**현재 위치(2026-09-30 저녁).** Arrakeen Scouts D8 검토 1~3차와 OQ-076 대안 C(소위원회 가입은 원로회 자리를 차지한 turn 안 아무 때나 — 원로회 진입 → "소위원회 선택" → 종류 고르기, 되돌릴 수 있음; Corrinth City는 가입하거나 거절해야 Reveal이 끝남), 기본 엔진의 Round Start 규칙 순서, 게임 전체 선택 불가 표시 1단계를 반영했고, 같은 날 저녁 **epic-game-mode를 병합**했으며(codec v124·관측 v28, OQ-092~094), Scouts 게임에 **체크포인트·탐색 AI 좌석**을 허용했고(학습하지 않은 템플릿만 있는 결정은 heuristic이 답한다), **보드 위 임무 조각**과 Scouts 로그 라벨(`8b8e8b6`)도 들어왔다(아래 요약). **다른 세션에서 할 일(문서와 작업 제안이 있다):** (1) [`explicit-turn-end-plan.md`](../explicit-turn-end-plan.md) — 모든 Agent 턴을 "턴 종료"로만 닫는다(사용자 2026-09-30, 세 번째 지적; 지금 엔진은 마지막 효과와 함께 턴을 닫아 그 뒤의 Plot·Family Atomics·표본 반환이 막히고 OQ-076의 spice 한계가 생긴다). (2) [`unavailable-options-plan.md`](../unavailable-options-plan.md) — 선택 불가 표시 3단계(18곳 전부; 영향력 6인 진영과 다 떨어진 Reserve 줄도 보인다), 자동 처리 없애기(사막의 힘 (B); 신성한 전쟁은 선택지가 하나여도 잃는 좌석에게 묻는다 — OQ-036 (a) 뒤집음), Harvest Cells 숨은 정보 문제(고위험). **(1)과 (2)의 자동 처리 없애기는 둘 다 턴 흐름과 codec을 바꾸므로 동시에 하지 말고 (1)을 먼저 한다**(다음 codec 번호는 v125). 사용자 결정(2026-09-29): 보드 칸은 갈 수 있는 칸을 이미 밝히므로 갈 수 없는 칸에는 따로 표시하지 않는다. Mercenaries의 단독 양수 입찰자는 전부 후퇴할 수 있다(OQ-074 확인). 2026-09-30 밤 사용자가 푸시했다(`79b14b9`까지). 그 뒤 교전 결과 줄의 "Null" 수정 `127ad51`(지도자 드래프트 없는 게임에서 setup이 공개한 첫 Conflict의 이름을 로그 대신 `conflict_won`·보드에서 읽는다)을 병합했다(`1222dd8`). 아래 "작업 배분"을 적은 커밋까지 푸시했고, 병합을 마친 worktree·브랜치는 모두 정리했다(`epic-game-mode`, `merge-epic-game-mode`, `scouts-ai-seats`, `exciting-brahmagupta-1753f3`, `keen-pasteur-e698d0`). 원문은 `scripts/dwgr/show_text.py <loc 키>`(`--para`로 문단 거르기)로 본다. 푸시는 사용자가 말할 때만 한다(D9).

### 작업 배분 — 다음 세션들 (2026-09-30 사용자 결정)

사용자는 남은 일을 둘로 나눠 진행한다: **로컬 자료가 필요한 일은 이 Mac mini에서 Codex로, 필요 없는 일은 Claude 클라우드 세션으로.**
새 세션은 이 절에서 자기 몫을 고르고, 해당 계획 문서를 처음부터 읽은 뒤 시작한다. 두 계획 문서는 도구 중립이다
("subagent", "독립 리뷰 agent"는 Codex에서는 별도 검토 단계로 읽는다).

로컬에만 있는 것: 학습 체크포인트(`checkpoints/`, git 밖 — 예: `checkpoints/2026-09-27/ext-v111/C/iteration_07081.pt`, 평가 문제집을
다시 캐는 5081 champion), 비공개 에셋 저장소(`assets` symlink → `Dune-Imperium-assets`; 보드 스캔·카드 그림 — 없으면 UI는 합성 grid로
그리고 보드 조각 E2E가 제대로 돌지 않는다), 몇 시간짜리 자동 대전·학습을 돌릴 기계, DWGR 앱 설치본(`scripts/dwgr/`).

| 순서 | 작업 | 어디서 | 문서 | 비고 |
|---|---|---|---|---|
| ~~L1~~ | Agent 턴은 "턴 종료"로만 닫기 — **완료(2026-10-02, 로컬 Claude 세션, OQ-095)** | 로컬 | [`explicit-turn-end-plan.md`](../explicit-turn-end-plan.md) | 게임 흐름이 바뀌어 tips-v1을 다시 캐야 한다(5081 체크포인트, [`evaluation/problem-set.md`](../evaluation/problem-set.md) "다시 캐는 명령"). 착수 때 사용자에게 8절의 Q1(Withdrawn·Litany Against Fear로 넘긴 턴에서도 누르기 전에 Plot 등을 할 수 있나), Q2(v111 재적응 실행 여부)를 묻는다. |
| ~~L2~~ | 자동 처리 → 결정 창 — **완료(2026-10-02, 로컬 Claude 세션, L1과 함께 병합)** | 로컬 | [`unavailable-options-plan.md`](../unavailable-options-plan.md) 5절 | L1과 같이 턴 흐름·codec을 바꾸므로 동시에 하지 않는다. 사막의 힘은 (B), 신성한 전쟁은 선택지가 하나여도 묻는다(OQ-036 (a), 다시 묻지 않는다). tips-v1 재채굴. |
| ~~L3~~ | v111 재적응, Scouts를 학습 설정에 — **완료(2026-10-06, 로컬 Claude 세션; UI 기본 + Scouts, 반은 앱 AI 상대, [evaluation/m10-2026-10-06.md](../evaluation/m10-2026-10-06.md))** | 로컬 | 이 문서 M10 절 | 몇 시간짜리 실행은 착수 전에 사용자에게 묻는다. |
| C1 | 선택 불가 표시 3단계(18곳) | **Claude 클라우드** | [`unavailable-options-plan.md`](../unavailable-options-plan.md) 1~4·7절 | 화면만(합법 행동·codec·관측·저장 불변)이라 pytest로 검증된다. 보드 스캔이 필요한 E2E·스크린샷 확인은 병합 전에 로컬에서 한 번. |
| C2 | Harvest Cells 숨은 정보 문제 | **Claude 클라우드** | [`unavailable-options-plan.md`](../unavailable-options-plan.md) 6절 | 고위험(숨은 정보·제시 행동): 독립 리뷰, `--privacy-interval` 소크. tips-v1 테스트가 깨지면 재채굴만 로컬로 넘긴다. |

병행 규칙:

- **codec 번호.** L1·L2·C2는 `ACTION_CODEC_VERSION`을 올릴 수 있다(지금 v135, 다음 v136). **나중에 master에 합치는 쪽이 번호를 다시 올린다**
  (epic 병합 때와 같다: 버전 주석에 양쪽 뜻을 모두 남기고 golden digest는 문서화된 절차로 다시 핀한다). 관측 버전도 같다(지금 v30).
- **충돌.** C1은 여러 `rules/` 공급자 함수에 막힘 판정을 드러내고, L1은 `rules/effects.py`·`combat_deployment.py`·`agent_effect_frame.py`·
  `engine.py`·`server/sessions.py`를 고친다. 함께 진행하면 작게 자주 master에 합친다. 합칠 때는 master 쪽에서 `--no-ff`로 합친다.
- **시작 전.** 어느 도구든 세션 시작 체크리스트(위)대로 `git fetch origin` 후 양방향 비교를 먼저 한다 — 여러 기계·도구가 같은 master에 쓴다.
- 이 Mac의 Claude 앱에 만들어 둔 작업 제안 카드(같은 작업들)는 쓰지 않아도 된다; 위 표와 계획 문서가 같은 내용을 담는다.

급하지 않은 사용자 결정 거리(보드 위 임무 조각, `a195676`): 관측소 위 Solari 동전이 인쇄된 아이콘처럼 보인다; CHOAM Escort 물품은
좌석 세부를 펼쳐야 Contract 옆에 보인다(Scouts 패널 목록에는 늘 있다).

**현재 위치(2026-09-26 저녁).** 카드·보드 전사 전수 감사로 규칙 약 130건(기본판 카드 포함)이 바뀌었고(아래 "2026-09-26 카드·보드
전사 전수 감사" 세션 요약), 저녁에 OQ-066·068·069를 사용자 판정대로 반영했다(codec **v109**, 관측 v20; 아래 "2026-09-26 저녁 OQ 판정" 요약).
밤에 recruit 집계 전수 수정과 OQ-064 판정(Coercive Negotiation은 contract bank 3장 미만이면 아예 사용 불가)도 병합했다.
OQ-065(강제 Spy 이동 순서와 갈 곳이 없는 Spy)도 밤에 사용자 판정으로 확정했고, 자기 자신을 trash하는 경로 9곳에 trash-recruit guard를 예방적으로 넣었다(아래 요약). 그 뒤(2026-09-27
새벽) OQ-070으로 이번 turn에 recruit한 Commander의 배치 몫은 Commander만 쓰게 고쳤다(아래 요약). 이로써 이 날 사용자에게 물은 판정은
모두 정해졌다(OPEN 없음). 같은 새벽 Agent box의 Spy도 supply가 비면 box를 해결하는 그 시점에 선행 recall을 거절할 수 있게 했다
(`decline_agent_card_spy`, codec **v110**; 이제 모든 Spy 경로가 그렇다). 또 pytest가 평가 문제집 tips-v1의 **모든** 포지션을 복원해 본다 —
규칙을 바꿔 국면이 움직이면 그 커밋에서 곧바로 실패하므로, 같은 작업 단위에서 [evaluation/problem-set.md](../evaluation/problem-set.md)의
"다시 캐는 명령"으로 다시 캔다(아래 요약). 학습·비교는 새 규칙에서 다시 시작하면 된다. 그 뒤 M10은 새 규칙에서 기준선(heuristic·5081·탐색 좌석)부터 다시 잰다. 아래 UI·학습 항목은 그대로다.

**현재 위치(2026-09-27).** UI 개선 0~10단계가 끝났다([`ui-improvement-plan.md`](../ui-improvement-plan.md)의
7~10단계: 실전 감사 두 번과 선택지 36판 전수 점검에서 나온 항목, 리더 카드 위의 상태, 효과 문구와 리더 능력의
한국어 — 워크트리 `ui-work`를 master `08b5003`로 병합, 아래 요약). 학습 쪽 현재 위치는 아래 0번(M10)이 그대로다. UI에서 남은 것은 아래이며, **사용자가 고르기
전에는 시작하지 않는다**.

### UI 다음 후보 (2026-09-27)

1. **첫 친구 판(M14의 남은 것) — 가장 값어치가 크다.** 원격 흐름·자동 저장·도움말·스크린 리더 알림·언어
   전환·노트북 화면의 좌석까지 준비됐다. 남은 것은 다른 집의 친구와 실제로 하는 한 판과 그 피드백이다([`remote-play-guide.md`](../remote-play-guide.md)).
2. **아직 영어인 낱말.** Wild card·Immediate·Usurp는 용어집 행이 먼저다(한국어 룰북이나 한글판 카드
   `[KO card: …]` 인용). Other Memories·Secret Project·Fedaykin Maneuver·Into the Fray·Feyd는 리더 카드 팝오버가
   이미 한글판 인쇄 이름(다른 기억들·비밀 프로젝트·페다이킨의 책략·전투 속으로·페이드 토큰)을 쓰지만 행동 목록·로그
   라벨(`labels.js`)은 영어라, 둘을 맞출지는 사용자 결정이다. 바꾸면 `test_i18n.py`와 `log_words.py`의 허용
   목록에서도 뺀다.
3. ~~한글 카드 스캔~~ — **2026-09-23 적용**(아래 "2026-09-23 한글 카드 이름·그림"과 "혈통·불멸 한글 카드"
   세션 요약): 봉기 138·혈통 90·불멸 58장이 `cards/ko/`에, 한국어 화면은 한글 그림·한글 이름(인쇄 확인분
   251개). 남은 것은 빠진 카드 62장 — 봉기 책략 34·혈통 책략 12·뒤틀린 책략 11·교전 2(Secure Imperial
   Basin, Test of Loyalty)·대모 제시카·프로모 2 — 이고, 58장은 한글 이름도 없다. 2026-09-27 사용자가 가진
   한글판을 직접 찍기로 했다(사진이 오면 크롭해 `cards/ko/`에 넣고 이름은 두 번 따로 읽어 `names_ko.py`에).

**UI를 이어갈 때의 규칙**(세 세션이 값을 치른 것들):
- `static/*.js`를 고치면 pytest로는 부족하다. [`scripts/e2e/`](../../scripts/e2e/README.md)에 **27종**이 있다(2026-09-27 UI 7~10단계의 10종 추가; `rehearsal.py`는 Tailscale 주소가 있을 때만). 항목마다는 관련 스크립트만, 전부는 병합·handoff 전에 `run_all.py`로 한 번 돌린다(4개씩 병렬, Mac mini 76초). 리뷰를 얼마나 둘지는 [`CLAUDE.md`](../../CLAUDE.md)의 "Verifying UI changes"(2026-09-27 사용자 결정 — 위험도별).
- 화면에 새 효과 문구를 더하면 영어 생성기 옆의 한국어 쌍둥이(`display/*_ko`, `personal_card_text_ko` 등)도 같은 순서로 더한다 — 짝 테스트가 빠진 줄을 잡는다. 한국어 낱말은 [`rules/glossary-ko.md`](../rules/glossary-ko.md), 문체는 [`rules/korean-card-style.md`](../rules/korean-card-style.md).
- 턴 흐름을 건드리면 "사람 좌석의 모든 턴 끝은 그 좌석이 `턴 종료 ▶`를 정확히 한 번 누른다"를 지킨다([`lessons.md`](../lessons.md) 2026-09-23; 판정은 `server/turn_end.py`와 `sessions.py`의 `_settle_locked`, 엔진에 명시적 종료 행동이 늘면 서버 `EXPLICIT_TURN_ENDS`와 `render.js`의 `EXPLICIT_TURN_END_IDS`에 함께 넣는다).
- 엔진 값을 화면에 낼 때는 `fieldText`(`core.js`)를 거친다. 새 종류의 id(관측소·연구 칸·Feyd 칸 같은)가
  생기면 거기에 한 가지를 더하고, `log_words.py`가 `prettify()` 호출과 id 모양을 잡는다.
- 목록 가드는 소스의 한 표기가 아니라 **실행되는 표**를 기준으로 한다(`ACTION_HANDLERS`), 화면 검사는 접힌
  것을 펴고 훑는다([`lessons.md`](../lessons.md) 2026-09-21).
- 새 단언은 **옛 코드에 돌려 실패를 확인**한다(A/B). 앞 세션은 제안 30건 중 27건이 공허했고, 이번 세션은
  "필요한 조각이 들어 있다"만 보던 단언 셋이 결함을 통과시키고 있었다([`lessons.md`](../lessons.md) 2026-09-21).
- 문자열은 `UI_TEXT` + `t()`/`tNode()`로만 쓴다. 한글 리터럴을 테이블 밖에 두면 `test_i18n.py`가 막고,
  한국어 모드의 영어 잔재와 영어 모드의 한글은 `lang.py`가 막는다. 규칙 낱말은 용어집(`TERMS`)에서만 —
  용어 낱말이 이미 명사를 품고 있으면(`{intrigue}` = 책략 카드) 뒤에 "카드"를 또 붙이지 않는다.
- 레이아웃·스크롤 주장은 **재 본 뒤에** 코드를 쓴다. 이번에는 CSS 주입으로 배치안 다섯을 먼저 쟀다.
- 키 입력은 `event.key`가 아니라 **`event.code`**로 맞춘다([`lessons.md`](../lessons.md) 2026-09-20).
- 경합은 기기 속도에 맡기지 않고 `page.route`로 응답을 늦춰 강제한다(`spectate.py`).
- 학습이 도는 동안 이 체크아웃의 `src/`를 고치지 않는다 — **워크트리에서** 한다. 워크트리에는 git 밖의
  `assets` symlink와 `.venv`가 없으니 둘 다 걸고 `PYTHONPATH=<wt>/src E2E_REPO=<wt>`로 그 클라이언트를 띄운다.

### Arrakeen Scouts (M15) — 구현 완료, D8 일괄 검토 끝 (2026-09-30)

Dire Wolf Game Room 컴패니언 앱의 3-4인 모드 "Arrakeen Scouts"(아라킨 스카웃)가 시작 옵션
`RulesetConfig(arrakeen_scouts=True)`(새 게임 화면의 체크박스, 기본 꺼짐)로 들어갔다. 설계 12절의 D1~D9를 사용자가 정했고 슬라이스 1~10을 모두 끝냈다.
- 규범 명세 [`rules/arrakeen-scouts.md`](../rules/arrakeen-scouts.md)(11절에 슬라이스별 구현 상태), 설계 [`arrakeen-scouts-design.md`](../arrakeen-scouts-design.md), 감사 [`implementation-audits/arrakeen-scouts.md`](../implementation-audits/arrakeen-scouts.md).
- **D8 일괄 검토는 끝났다(2026-09-29~30).** OQ-071~OQ-090을 사용자와 1~3차로 검토해 바뀐 판정을 규칙 변경으로 반영했고(명세 인용·회귀 테스트), 마지막으로 OQ-076 대안 C(소위원회 가입을 자리를 차지한 turn 안 아무 때나)를 넣었다. 판정과 근거는 각 OQ 항목과 아래 세션 요약에 있다. 남은 Scouts 관련 일은 게임 전체의 선택 불가 표시·자동 처리 없애기 계획([`unavailable-options-plan.md`](../unavailable-options-plan.md))에 들어 있다.
- **푸시.** 2026-09-30 밤 푸시했다. 앞으로도 사용자가 말할 때만 푸시한다(D9). 남은 일의 배분은 위 "작업 배분" 절.
- 2026-09-30 저녁: 보드 그림 위의 임무 조각(`a195676`)과 Scouts 게임의 `checkpoint:`·`search:` 좌석(`b7cf49c`, D6 변경)을 끝냈다. 후속 후보: 학습 배선(Scouts를 M10 학습 설정에 넣기 — D6대로 아직 안 함; 지금 체크포인트는 Scouts 결정의 82~91%가 학습하지 않은 템플릿뿐이라 heuristic에게 넘긴다), 앱 업데이트 시 `scripts/dwgr/extract.py` 재추출과 `diff -r`.
- 숨은 정보: 비밀 선택과 봉인 입찰은 좌석 한정 id로 `known_card_seats`에 들어가 로그 가림·되돌리기 경계·소크 누출 검사·탐색 AI 재추첨이 모두 같은 등록부를 읽는다. 슬라이스 7·8은 독립 리뷰를 거쳤다(7에서 누출 두 건을 고쳤다).

### 학습(M10) 쪽 순서

**현재 위치(2026-10-09 밤, v141 재적응).** [evaluation/m10-2026-10-09.md](../evaluation/m10-2026-10-09.md). X@10081을 v140/v141 규칙에서 800 iteration 이어(mix-v139와 같은 설정) Y@10881(`checkpoints/2026-10-09/readapt-v141/Y/iteration_10881.pt`, 옵티마이저 포함, 쓰기 금지)을 얻었다. 같은 v141 엔진에서 2:2 1,400판 Y − X = **+10.1%p [+5.0, +15.3]**(순위·마진도 분해). 학습 계보의 머리는 Y다. 플레이 서버 망(지금 X)을 Y로 바꿀지는 탐색 좌석 측정(`search:Y` 대 `search:X`, 1 대 앱 AI 3석)을 거쳐 사용자가 정한다. 같은 실행에서 찾은 앱 AI의 Spice Refinery 비용 시뮬레이션 결함(Navigation Chamber 할인 누락)은 `f20d26d9`에서 고쳤다.

**현재 위치(2026-10-09, 학습 일시 정리).** 플레이 서버 탐색 망은 X@10081(`mix-v139-10081.pt`)이다. 다음 학습 후보였던 expert iteration v2는 c0 수집 510판에서 사용자 결정으로 멈췄고, 코드와 기록은 master에 있다([evaluation/exit-v2-2026-10-08.md](../evaluation/exit-v2-2026-10-08.md) 5절에 이어 하는 두 길). 학습을 다시 시작할 때는 그 사이 올라간 codec(v141~)으로 X를 이관해야 한다.

**현재 위치(2026-10-08 오후, 플레이 서버 망 교체).** [evaluation/m10-2026-10-07.md](../evaluation/m10-2026-10-07.md) 7절. 새 시드로 다시 잰 탐색(X) − 탐색(8081)은 +8.5%p [+0.5, +16.5], 앞 묶음과 합친 100시드는 +11.3%p [+5.3, +17.3](순위·마진도 분해)이다. 사용자 결정으로 `checkpoints/play/search.pt`가 X의 가중치 사본 `mix-v139-10081.pt`를 가리킨다(8081 파일은 옛 저장용으로 남김). 다음 학습 후보는 expert iteration v2(설계·시범은 git 무시 `checkpoints/2026-10-08/exit-v2/`, 코드는 브랜치 `exit-v2`).

**현재 위치(2026-10-08, 탐색 반전 확인과 v139 연장 끝).** [evaluation/m10-2026-10-07.md](../evaluation/m10-2026-10-07.md) 6절. 탐색 반전은 시드 운이었다(150시드 합산 M − 8081 −0.5%p). M 방식 연장 X@10081(v139, `checkpoints/2026-10-07/mix-v139/X/iteration_10081.pt`, 옵티마이저 포함)은 M@9081보다 greedy +2.0%p(잡음 안)로 이 설정의 이득은 거의 끝났고, 탐색 좌석으로는 같은 시드의 8081보다 +14.1%p [+4.5, +23.1](그 묶음의 8081이 낮았다는 단서). 플레이 서버 망을 X로 바꿀지는 사용자 결정. 같은 측정에서 Long Reach 턴 종료 지급이 track Spy를 남겨 턴이 닫히지 않는 엔진 결함을 찾았다.

**현재 위치(2026-10-07, 섞기 대 self-play 두 팔 끝).** 결론과 근거는 **[evaluation/m10-2026-10-07.md](../evaluation/m10-2026-10-07.md)**. 8081에서 1,000 iteration: 앱 AI 섞기(M)가 self-play만(S)을 직접 +5.9%p로 이기고 8081을 +13.1%p로 이긴다. 탐색 좌석으로는 M이 8081보다 −10.5%p라 플레이 서버는 8081을 계속 쓴다. 학습 계보의 머리는 M@9081이다. 다음 후보(사용자 결정): (a) 탐색 반전 확인 — 새 시드로 탐색(M)·탐색(8081)을 다시 재고 탐색(S)을 더함, (b) 정책 M + 가치 8081 탐색으로 가치 head 가설 시험(코드 필요), (c) M 연장, (d) v139 규칙 재적응.

**현재 위치(2026-10-06, L3 끝).** 결론과 근거는 **[evaluation/m10-2026-10-06.md](../evaluation/m10-2026-10-06.md)**. 요지:
- **새 기준선은 `checkpoints/2026-10-06/l3-appai/judge/l3-08081.pt`**(룰셋 `uprising-4p-choam+promo+bloodlines+tech+immortality+go11+epic+scouts`, 드래프트로 학습, 옵티마이저 포함). 7081에서 `--retarget`로 이어 1,000 iteration을 돌렸다. 판의 반은 학습 2석 대 앱 AI 어려움 2석이었다.
- **같은 시드에서 앱 AI 어려움을 상대로 망 혼자 −22.4%p → +17.9%p**(2:2), 탐색 좌석은 49.0% → 72.0%(1대3). 이 설계로는 앱 AI 상대 섞기의 효과와 새 규칙 적응의 효과를 나눌 수 없다. 나누려면 self-play만 쓴 대조 팔이 필요하다.
- 다음 후보(사용자 결정):
  - (a) self-play만 쓴 대조 팔로 섞기 효과 분리
  - (b) 같은 설정 연장: 학습 중 1대3 평가가 뒤 400 iteration에 37.5%로 아직 오르는 듯하다
  - (c) 탐색 대 탐색 2:2
  - (d) 앱 AI 대신 탐색 좌석을 학습 상대로(비쌈)

**먼저 볼 것(2026-09-27 저녁) — CHOAM 계약 구성이 바뀌었다(codec v111, 관측 v21).** 아래 요지의 모든 학습·사다리·문제집 수치는
Rise of Ix 전용 계약 타일 4장이 든 CHOAM 판에서 잰 것이다(학습 룰셋은 CHOAM 포함 전 확장). 기준 체크포인트 `readapt-v110/iteration_05600.pt`는
불러올 때 이관된다: 행동 32,991개 유지·16개 신규(새 계약 4장 × 템플릿 4)·16개 폐기, 관측 4,305열 유지·22열 신규(Spice Refinery I·II × 11구간,
0에서 시작)·44열 폐기(Ix 4장 × 11). 두 번째 사본은 첫 사본의 열을 받는다(`training/checkpoint.py`의 identity 재연결). 새 계약에 대한 행동은
학습된 적이 없으니, **이 체크포인트로 무엇을 재기 전에 재적응(v110 때처럼 약 500~1,000 iteration)을 돌릴지 사용자에게 먼저 묻는다.**
tips-v1은 새 규칙으로 다시 캤다(118개; [evaluation/problem-set.md](../evaluation/problem-set.md)). → **2026-09-28 밤샘에 재적응을 끝냈다(아래).**

**현재 위치(2026-09-28 아침, v111 밤샘 마감).** 결론과 근거는 **[evaluation/m10-2026-09-28.md](../evaluation/m10-2026-09-28.md)**. 사용자가
"C·T 두 팔 7081까지"를 골랐다(판정 규칙은 결과 전에 git 무시 `checkpoints/2026-09-27/ext-v111/README.md`에). 요지:
- **v111 기준선은 `checkpoints/2026-09-27/ext-v111/C/iteration_07081.pt`**(쓰기 금지, 옵티마이저 있음). v110 기준 6081에서 v111로
  1,000 iteration을 더 돌린 MLP다. 5600(v110 기준, 이관)을 2:2 1,400판에서 **+18.3%p [+13.1, +23.4]**로 이겼고(순위·마진도 분해),
  중간점 6600은 +7.0%p [+1.7, +12.3]였다. 7081 대 6600을 직접 잰 L3도 **+11.7%p [+6.6, +16.9]**라, 세 점이 맞고 이번에는 1,000 iteration 내내 올랐다(v110 때는 500에서 끝). 5600은 새 계약 4장을 배운 적이 없으니 +18%p를 모두
  일반 실력 차로 읽지는 않는다.
- **slot 입력(`mlp_slots`) RL 팔은 끝났다.** 선언된 연장(두 팔 7081까지) 뒤 J1' T@7081 대 C@7081 2,800판 **−4.2%p [−7.8, −0.6]** →
  선언 규칙의 "무익". T는 Row·Conflict에 C보다 3.6~7배 반응하지만(M') 결과 신호 self-play는 그것을 강도로 바꾸지 못했다. 표현 문제는
  expert iteration(탐색 레이블) 쪽으로 넘긴다.
- 합법 행 learner로 1,000 iteration이 약 3시간(9.5초/it), 메모리 압박 경고 0. heuristic 3명 상대 89%로 포화.
- **다음 후보(사용자 결정)**: (a) 탐색 좌석(`search:`)을 7081로 다시 재기 — 게임에서 쓰는 가장 강한 AI, (b) slot 네트워크로 expert
  iteration 재시도, (c) 같은 설정으로 C 연장(L3로 보아 아직 정체 전; 약 3시간 + 사다리), (d) iteration당 64판 메모리 시험.

**현재 위치(2026-09-27 오후, 밤샘 세션 마감).** 결론과 근거는 **[evaluation/m10-2026-09-27.md](../evaluation/m10-2026-09-27.md)**. 요지:
- **새 규칙(codec v110) 재적응 — 이득은 첫 500 iteration에 다 왔다.** 5081에서 long-2k 설정으로 1,000 iteration(`checkpoints/2026-09-27/readapt-v110`,
  4.5시간, 실패 0). 사다리(각 2:2 1,400판): 5600 대 5081 **+8.1%p [+3.0, +13.4]**(순위·마진도 분해), 6081 대 5600 −3.6%p(마진 −0.165 분해),
  6081 대 5081 +3.1%p(잡음 안). **새 규칙의 기준 체크포인트는 `checkpoints/2026-09-27/readapt-v110/iteration_05600.pt`**(쓰기 금지, 옵티마이저 없음 —
  이어 학습하면 Adam이 새로 시작; 옵티마이저까지 있는 것은 `iteration_06081.pt`). heuristic 3명 상대는 86~87%로 포화.
- **표현력 가설(H1) — 반응은 생겼지만 강해지지는 않았다.** 네트워크가 `log1p`로 읽는 정체 칸(Row, Conflict, 결정 종류, Agent 위치…)을 가르지 못하는
  것은 측정으로 확인됐다(Row 교체 가치 변화 0.0013, 손패 0.039). 처방 `mlp_slots`(`5044080`, **master 병합 `c5fe7bc`** — 새 실행의 기본은 여전히 MLP이고 `dune-imperium-checkpoint widen --arch mlp_slots`로만 쓴다)로 C와 짝지은 T 팔
  (`checkpoints/2026-09-27/slots-v1`, 판정 규칙은 결과 전에 그 `README.md`에): Row·Conflict 민감도는 2.4배·6.3배가 됐지만 **J1 T@6081 대 C@6081
  2,800판 +1.3%p [−2.3, +4.9] → 불확정**(5600에서도 승률 −0.3%p, 마진은 T가 나쁨). 선언한 연장(두 팔 7081까지, 약 9.4시간)은 띄우지 않았다.
- **합법 행만 쓰는 learner**: `930eac5`, **master 병합 `35eb090`**. 미니배치 합법 합집합(33,007 중 690~795개)만 계산 — dense 경로와
  수학적으로 같다(테스트로 대조). 실제 크기 3 iteration 스모크끼리 update 6.5 → **1.3초**, group RSS 최대 6.0 → 5.3 GiB(`mlp_slots` 6.1 GiB) → **iteration 약 15.5 → 10초**.
  이제 모든 학습이 이 learner로 돈다(옛 실행과는 float 합산 순서만 다르다). learner의 미니배치 logit 텐서는 사라졌지만 배치 자체(관측)는 그대로라
  iteration당 64판이 16 GB에 들어가는지는 재 봐야 한다.
- **다음 후보(사용자 결정)**: (a) ~~두 브랜치 병합~~ — 2026-09-27 오후 병합·push, (b) T 연장
  (선언된 유일한 연장), (c) 표현 변화가 빨리 드러나는 경로 — slot 네트워크로 expert iteration 재시도(15절의 "선명한 뒤집기 18.5%"가 오르는지)나
  탐색 좌석 위 비교, (d) 탐색 좌석(`search:`)의 새 규칙 표를 5600으로 다시 재기, (e) 재적응이 500 iteration에 끝나므로 같은 설정의 긴 실행은
  기대값이 낮다(9-22 결론과 같음). 두 워크트리와 로컬 브랜치는 병합 뒤 지웠다(git 무시 `checkpoints/2026-09-27/slots-v1/judge.sh`는 저장소 루트와 `scripts/ab/value_swap_probe.py`를 쓰도록 고쳐 두었다).

**현재 위치(2026-09-22).** 결론과 근거는 한 곳에 모았다 — **[evaluation/m10-2026-09-22.md](../evaluation/m10-2026-09-22.md)**(원자료는
git 무시 `checkpoints/2026-09-22/m10-evidence/`). 요지:
- **판정은 사후 대회 + `scripts/ab/paired.py`로만 한다**(2:2 미러, `--matches`, seed 군집 CI). 600경기의 분해능은 약 ±7.7%p,
  3%p를 보려면 약 15,800경기다. 학습 중 평가는 트립와이어다(이 주에 결함 둘을 고쳤다 — seed 반복 `f8e5a5f`, 역전 `fe2196c`).
- **가장 좋은 체크포인트**: `checkpoints/2026-09-21/long-2k/latest.pt`(iteration 5081; 쓰기 금지 복사본 `checkpoints/2026-09-22/exploit/champion-5081.pt`) — 출발점 2081 대비 2:2 미러 **+15.0%p**,
  heuristic 3명 상대 88.5%. 3081(`control-1k`)과는 잡음 안이다(+4.6%p 누적, 두 단계 모두 잡음 안).
- **현재 설정은 다시 정체했다.** 규칙 정정 직후 1,000 iteration의 +19%p는 옛 규칙 정책의 재적응으로 보이고(정황), 그 뒤
  2,000 iteration은 +3.0·+1.6%p로 잡음 안이다. **같은 설정을 더 돌리는 것은 기대값이 낮다.**
- **기각된 것**: 순위 보상(대조군과 직접 A/B 잡음 안), 학습률 조정(2026-09-19), 구매 강제(−17%p).
- **정책은 카드를 거의 사지 않고 그것이 옳다**(구매 강제 탐침). 저장소의 두 baseline(heuristic, heuristic playout의 rollout)은
  "많이 산다"는 같은 사전을 공유하고 둘 다 이 정책에 진다 — **배울 상대가 없다**.
- **착취자 실험(2026-09-22, 상대 다양화의 첫 단계) — 음성**: 얼린 5081만을 이기도록 2,000 iteration(학습 행 약 2,500만 =
  self-play 1,000 iteration 한 단계어치) 학습한 전용 정책이 1대3에서 **25.4% [23.1, 27.7]**(귀무 25%)다. 세 점 25.0 → 26.9 →
  25.4로 추세가 없고, 학습자 좌석 승률이 내내 평평하며 entropy는 오히려 올랐다. **5081은 제 분지 안에서 착취되지 않는다 —
  이 계보는 국소 최적이다.** 과거 체크포인트나 그 착취자로 짠 리그는 가르칠 것이 거의 없다([evaluation/m10-2026-09-22.md](../evaluation/m10-2026-09-22.md) 11절).
  배치 상대와 `--learner-seats`(`3d8917c`)는 이 실험을 위해 들어갔다(1대3 수집 28.9 → 10.8초, 결정 단위 동일성 테스트).
- **정책 유도 탐색 — 성공(2026-09-23)**: 결정화는 그대로 두고 후보·플레이아웃·말단 평가를 네트워크로 바꾼 스크래치 변형
  `net_search_value`(`checkpoints/2026-09-22/search/tools/netsearch.py`)가 얼린 5081 셋을 상대로 **58.0% [48.3, 67.7]**(100판,
  귀무 25%, +6.7 SE), 평균 순위 1.740, VP 9.39 대 7.46이다. 3,000 iteration 학습이 1대3으로 약 +6%p를 냈는데 **탐색 하나가
  같은 네트워크로 +33%p**다. 숨은 정보 누출은 없다(결정화 30세계 확인). 비용은 결정당 2.0초
  ([evaluation/m10-2026-09-22.md](../evaluation/m10-2026-09-22.md) 12절).
- **(a) 정식 편입 — 완료(`4b52b9e`)**: `agents/network_search_agent.py`의 `NetworkSearchAgent`와 registry의 `SEARCH_PREFIX`로
  **`search:<파일경로>`** 좌석이 생겼다. 서버는 좌석 종류를 `is_agent_kind()`로만 검증하므로 **플레이 서버 AI 좌석과 대회 도구가
  그대로 받는다**(원격 테이블에는 체크포인트처럼 파일 이름만 보인다). 스크래치 변형과 탐색 결정마다 같은 수를 두는 것을 확인했다.
  쓰는 법: `--agents "search:checkpoints/2026-09-22/exploit/champion-5081.pt,heuristic,heuristic,heuristic"`.
- **(b) 비용 줄이기 — 완료(2026-09-23)**: 판당 **405초 → 18초(약 22배)**, 강도는 잡음 안([evaluation/m10-2026-09-22.md](../evaluation/m10-2026-09-22.md) 13절).
  - **합법 행만 읽기(`45dc9a3`)** — 시간의 65%가 네트워크, 그 대부분이 32,987행 정책 head였다. 탐색은 몸통을 지난 뒤 제시된
    행동의 head 행만 읽는다. 12절 확인 셀과 같은 100판이 순위·VP까지 100/100 같고 판당 405 → 76초. 병목은 이제 엔진이다
    (`apply`·`legal_actions` 56%) — 플레이아웃 배치 추론은 최대 약 20%라 미뤘다.
  - **순환 방지(`c50614f`)** — 탐색 좌석이 `switch_graft_card`를 영원히 반복해 한 판이 1시간+ 멈췄다(switch 플레이아웃이 상한에서
    잘리고 value head가 그 턴 한가운데 상태를 높게 침). `NetworkAgent`와 같은 가드(같은 라운드·관측·합법 목록에서 이미 둔 수 제외)를
    실제 결정과 플레이아웃마다 넣었다. **무변화가 아니다**: 같은 100판 중 38판이 달라지고 판당 71 → 46초, 강도는 +1%p [−3, +5].
    12절의 58%와 13절 앞쪽 변형 표는 가드 전 값이다.
  - **효과 순서는 네트워크에 맡김(`430d1ae`, 지금 `search:` 기본)** — census에서 Agent 턴 효과 순서 결정이 탐색 시간의 63%인데
    뒤집는 비율은 10%로 가장 낮았다. 새 seed 300판을 같은 버전(가드 적용)끼리 짝지으니 출하 좌석 **61.7%** 대 전체 탐색 64.3%,
    차이 −2.7%p [−10.0, +5.0], 순위 +0.06 [−0.08, +0.20], 판당 18초 대 45초. 전체 탐색은 `search_effect_order=True`.
    판정은 frame 종류(`decision_stack[-1].kind == AGENT_EFFECTS`)로 한다.
  - 도구: 셀 두 개를 seed·좌석으로 짝짓는 `scripts/ab/cross_paired.py`; census·프로파일·멈춘 판 찾기·한 수씩 추적 스크립트는
    `checkpoints/2026-09-22/search/tools/`(git 무시), 셀 원자료는 `.../search/cost/`.
  - 덤으로 드러난 것: 관측 인코딩이 Graft 짝 중 어느 카드가 앞인지 구분하지 못한다(switch 전후 관측이 같다). 네트워크가 두 상태를
    가를 수 없으므로, 관측을 다시 손볼 때 후보.
- **밤샘 실행(2026-09-24 03:07~09:11) — (c) M10 표 완료, 말단 척도 결함 수정**([evaluation/m10-2026-09-22.md](../evaluation/m10-2026-09-22.md) 14절;
  원자료·판정 규칙 `checkpoints/2026-09-24/night/`). 약 4,900판에서 멈춤·실패 0.
  - **M10 표**(탐색 좌석 1명 대 상대 3명, seed 80000~ = 고정 평가 대역 v1, 귀무 25%): random 100%, heuristic **97.7%**,
    rollout **88.0%**, 2081(이전 champion) **64.0%**, 5081 **57.0%**(1,400판) — 모든 하한이 25% 위. 탐욕 5081 자체는 heuristic
    90.0%, 2081 33.7%. 탐색은 실제 상대가 제 상대 모델(5081)과 다른 2081일 때도 +30%p를 더한다.
  - **말단 척도 결함(`294d143`)**: 끝난 플레이아웃을 순위 사다리(100/70/40/10)로, 끝나지 않은 것을 value head(+1 / −1/3)로
    읽어서 게임을 끝내는 수가 4등이라도 과대평가됐다. 끝난 판을 head의 보상으로 읽으니 새 seed 1,400판 짝 비교에서 **+5.2%p
    [+3.4, +7.1]**, 순위 −0.06, 마진 +0.21(미리 정한 규칙 통과). 출하 좌석은 같은 판에서 게임을 더 일찍 끝낸 쌍이 170 대 50이었다.
    어제 seed 300판에서는 −0.3%p라 대가는 대역마다 다르다. M10 표의 행은 수정 **전** 좌석 값이다.
  - 밤에 쓴 도구(스크래치): 마감·프로세스 그룹 종료 실행기 `deadline.py`, 대기열 `queue.sh`(청크별 행 수로 완료 판정, 마감 시각 절단,
    STOP 파일), 요약 `summarize.py`, 메커니즘 `mechanism.py`.
- **Expert iteration v1(2026-09-24 낮) — 강해지지 않음**([evaluation/m10-2026-09-22.md](../evaluation/m10-2026-09-22.md) 15절;
  코드 `training/expert.py`·`training/distill.py`·`cli/expert.py`, 원자료·드라이버·선언 규칙 `checkpoints/2026-09-24/exit/`).
  탐욕 5081 자가대국의 결정 절반에 탐색이 후보 값을 라벨로 달고(1,392판, 라벨 약 18만), 사전을 기울인 목표로 5081에서 학습했다.
  it1·it2가 오프라인 관문은 통과했지만 대 5081 ×3 **25.2%·24.4%**(각 1,400판, 귀무 25%)로 강해지지 않았고, 선명한 라벨만 hard로
  가르친 후보는 **20.9%**로 약해졌다. 가치 head만 재적합해 탐색에 쓰는 것도 순위를 나쁘게 했다. 네트워크가 "탐색이 뒤집는 상태"를
  비슷한 상태와 가르지 못한다(선명한 뒤집기의 18.5%만 배움) — 표현력이 다음 병목이다.
- **탐색 기본은 후보 5 × 세계 8(2026-09-25 새벽)**(16절): 손잡이 비교(각 400판, 같은 판의 `search:5081`과 짝)에서 후보 5개
  +9.5%p, 세계 8개 +5.8%p, 후보 8개는 5개와 같음, 지평 2라운드는 비용 3.4배에 이득 없음. 새 판 1,000판(80100~80349) 확인에서 후보 5개
  66.1%(대 후보 3 × 세계 4 +4.1%p [+0.1, +8.1]), **후보 5 × 세계 8 76.1%(대 후보 5개 +10.0%p [+6.4, +13.7], 대 출하 좌석 +14.1%p)**.
  `DEFAULT_CANDIDATES = 5`, `DEFAULT_ROLLOUTS = 8`, 판당 18 → 58초(결정당 약 0.27초). 새 좌석의 M10 표: random 100%, heuristic 99.3%,
  rollout 89.5%, 2081 81.3%, 5081 76.1%. **탐색끼리 2:2에서도 옛 좌석을 60% 대 40%로 이긴다**(+20%p [+11, +29], 400판).
  세계 16은 새 판 1,000판에서 세계 8보다 +2.2%p [−1.6, +5.8](규칙 미달, 합계 1,400판 +3.0%p [+0.0, +6.1])에 비용 2배 — 기본은 세계 8.
- **다음 후보(사용자 결정)**: (1) 새 기본 좌석의 M10 표·후보 5 × 세계 16 시험 결과 반영(`checkpoints/2026-09-24/exit/knobs/queue4.sh`가
  돌렸다), (2) 탐색 좌석으로 M10 표 전체를 1,400판 셀로 굳히기, (3) 표현력 — 행동·카드 임베딩이나 분해된 policy head(15절의 병목), 그 위에서 expert iteration 재시도, (4) 탐색끼리 2:2.
  M10의 "모델"에 탐색 래퍼를 포함할지는 사용자 결정이다. 남은 옛 후보: 처음부터 다른 seed, 구매 전문가 B1.
- **판정 비용 메모**: 출하 `search:` 좌석의 1대3 셀은 4 worker로 100판에 약 8분, 1,400판에 약 1.8시간이다. 전체 탐색
  (`search_effect_order=True`)은 약 2.5배.
- **논의 중(2026-09-22, 코드 변경 없음): 사용자의 실전 팁을 학습에 쓰는 법** — [player-tips-for-training.md](../player-tips-for-training.md).
  팁은 측정할 가설로 다루고 보상이 아니라 진단·평가 문제집·league 상대·입력 표현에 넣는다는 결론까지 왔다. 같은 날 밤
  Mac mini에서 이어 갔다(그 문서 6절, **이어갈 때는 6.8부터**; 저장소 코드 변경 없음, 원자료 git 무시
  `ab-runs/2026-09-22-thin/`): 사용자 답은 "안 사는 게 아니라 비싼 카드로 시작 카드를 대체한 얇고 강한 덱"이고, census로
  보니 5081의 덱은 **얇은 시작 덱**(판 끝 시작 카드 7.31장, 산 카드는 막판의 싼 카드)이다. 팁 1(Fremen 2 → Hooks →
  sandworm)은 정책이 이미 배웠다. 비용 문턱으로 거르는 얇은 덱은 heuristic 틀에서 단조롭게 진다(같은 조건 직접 −17.8%p).
  **옆길 발견: heuristic이 Tleilaxu 카드를 사지 않기만 해도 평소 구성에서 +21.8%p [+18.4, +25.1]** — 채택은 별도 작업
  단위·사용자 결정(6.5).
  **2026-09-23(WSL 노트북, 그 문서 7절, 이어갈 때는 7.8부터)**: 커뮤니티 팁 38개를 규칙 확인·측정 경로로 분류했다(엔진 불일치
  0, 테스트 공백 1건 메움). 그 측정을 한 명령으로 내는 **`scripts/ab/tip_census.py`**(수집기 `deck`·`combat`·`influence`·
  `endgame`)와 비교 도구 `scripts/ab/tip_compare.py`를 넣고, heuristic 기준값(3구성 × 100 seed)과, 사용자가 노트북에 가져온 5081의
  census를 냈다(7.7): 정책은 Swordmaster 초반(79~94%)·Heighliner·sandworm·초반 폐기에서 팁과 같고, 초반 Faction 접근 카드
  (1~3라운드 0.67장, 팁 1~2장)·작게 이기기·tier III용 garrison·이른 Reveal(0번)·Espionage에서 다르다. 1+3 표는 Mac 스크래치 수치와
  0.2 안으로 맞는다. 초반 Faction 카드 강제 구매 탐침(`scripts/ab/pypath/netprobes.py`)은 파일럿에서 0.67 → 1.00장만 올라 용량이
  작다 — A/B는 아직 안 돌렸다(7.8에 명령).
  **평가 문제집 틀(같은 날)**: `evaluation/problem_set.py` + `dune-imperium-problems mine|score|check` + 문제집
  `evaluation/problem_sets/tips-v1.json`(110개, 3문항) — [evaluation/problem-set.md](../evaluation/problem-set.md). 포지션은 seed와
  선택 번호로 저장해 엔진만으로 복원하고, 규칙이 바뀌어 포지션이 움직이면 복원이 "re-mine" 오류를 낸다(**규칙을 고친 뒤에는
  `dune-imperium-problems check`**). 5081은 세 문항에서 1.00·1.00·0.85.

아래는 그 앞의 기록이다(시간 역순이 아니라 적힌 순서 그대로 남긴다).

**이전 현재 위치(2026-09-17).** 전 확장 구성의 학습 전 최종 점검(파이프라인·heuristic·소크·open questions)이 끝났고 다음은 아래 0번의 **M10 학습 시작**이다. 그 앞 2026-09-16 심야에 M10 학습 전 마무리 세션이 끝났다. (1) `dune-imperium-train`은 관측 v20·codec v104에서
pure self-play(3 iteration × 32판, 8 worker, `--eval-every`)와 `--opponent rollout`/`--eval-opponent rollout`(StateAgent 경로)
모두 정상이다. (2) heuristic의 표 밖 항: 동점 census(게임당 228개 legal 집합이 RNG로 정해짐)로 지렛대를 찾아 세 가족 안
tie-break(Influence 진영·trash/discard 카드·같은 비용 구매)를 채택했고, 고정 변형 `heuristic_uniform_ties` 상대 전 축·두
seed 블록에서 **+5.1 ~ +9.1%p**다([evaluation/baseline-2026-09-16.md](../evaluation/baseline-2026-09-16.md) 14절; 배치를 참는
규칙과 Plot 선출은 손해로 기각). (3) M10 수집 경로를 처음 프로파일해 관측 인코더(31%)를 바이트 동일하게 다시 써 수집
벽시계 **−16 ~ −18%**, 배치 handler의 guard 축소로 대회 경로 −3 ~ −4%([evaluation/throughput-2026-09-10.md](../evaluation/throughput-2026-09-10.md)
8절). (4) A/B가 찾은 엔진 결함 1건(Reveal 중 Intrigue 비용으로 Conflict가 비면 Reveal frame의 전투력 집계가 stale, `a1c3f94`)을
고쳤다. rollout `player_value` 가중치 A/B·tie-break heuristic의 소크·기준선 12셀 재측정은 이 세션 요약(아래)에 적힌 대로다.
남은 것은 **M10 학습 재개**(사용자 결정)와 아래 0번의 학습 밖 후보다.

0. (**2026-09-26 주의 — 규칙이 다시 넓게 바뀌었다**: 카드·보드 전수 감사의 규칙 수정 약 130건(The Spice Must Flow·Covert Operation·Subversive Advisor 등 기본판 카드 포함), codec v108(저녁 판정 뒤 v109). 5081을 포함한 모든 체크포인트·대전 표·탐색 비교·문제집 채점은 옛 규칙의 것이다. 형식 2 체크포인트는 v109로 이관된다(5081: 유지 32,980·새 26·삭제 7).)
   (**2026-09-20 주의 — 환경의 규칙이 바뀌었다**: Influence 4 보너스(Emperor Spy·Guild 3 Solari)·Spy 배치 의무·Branching Path·Imperial Privilege·c7r3, codec v107. 아래의 승률·대전 수치와 1650·2050 체크포인트는 전부 옛 규칙의 것이다. 형식 2 체크포인트는 v107로 이관되지만 **이어 학습하기 전에 새 규칙에서 다시 잰다**; 세션 요약 "보드 조각·아이콘 전사 정정"의 "M10에 미치는 영향".)
   (2026-09-19 저녁, **1650 출발 학습률 A/B 완료 — lr 1e-4와 3e-5는 구별되지 않고, 두 팔 모두 400 iteration 뒤에도 출발점 1650과
   같은 수준이다: 1400 무렵부터의 정체는 실재하고 학습률은 이번에는 지렛대가 아니다. 지금 도는 학습은 없다**;
   그 앞 2026-09-19 아침: 정체 해소 — 학습률 1e-4로 1650 iteration까지 상승)
   **M10 학습 — 전 확장 구성(codec v105, 32,991).** 경과(세션 요약 넷: "M10 첫 학습·되돌리기 루프·이관·codec v105",
   "M10 PPO 슬라이스·A/B", "학습률 실험·밤샘 실행 2", "M10 Mac mini 이관·실행 3"): (1) 첫 실행은 정책이 OQ-029의 `deploy_troops`/`withdraw_troops` 왕복을
   학습해 죽었고, 학습 수집·체크포인트 플레이에서 되돌리기 두 행동을 정책에 제시하지 않게 고쳤다([rl-environment.md](../rl-environment.md)).
   (2) 학습률 3e-4의 첫 밤샘 실행은 400~550 iteration에서 정체했다(550: heuristic 3명 상대 200판 76.5%). (3) PPO(clip 0.2·3 epoch·
   32판 배치)는 A/B에서 43.0%로 무너져 기각, REINFORCE도 같은 학습률로는 평평했다. 가설: 배치의 독립 표본이 32판의 승패뿐이라
   갱신이 잡음에 끌려다닌다. (4) **학습률만 1e-4로 낮추자 정체가 풀렸다**: 550 → 650(100 iteration A/B)에서 81.0%, 이어진 밤샘
   1,000 iteration(9시간 50분, 재시작·예외·평가 실패·잘린 판 0)에서 학습 중 200판 평가가 74.7%(처음 다섯 평균) → 82.7%(마지막
   다섯 평균, 최고 1400의 87.5%). 대전(seed 1000+): 4자 400판 — 550 9.2%, 1000 21.8%, 1300 32.0%, 1650 37.0%; heuristic 3명 상대
   200판 — 550 76.5, 1000 79.5, 1300 84.5, 1650 83.0%. **1400 이후는 상승이 작다**(1400·1500·1600·1650의 4자 대전 24.2·24.8·23.0·
   28.0%, 표준오차 약 2.2%p). 한 계보·한 seed라 방향은 분명하지만 수치는 재현 전이다.

   **가장 좋은 체크포인트**: Windows PC의 `checkpoints/2026-09-18/lr1e-4-long/latest.pt`(iteration 1650, 옵티마이저 포함, 형식 2·codec
   v105, 235,035,727 bytes, sha256 `1a479e8e671095130d6602983a46aa8a44b290fdc6830b1db8e95642f691d2dc`)와 같은 시점의 번호
   체크포인트 `iteration_01650.pt`(79,799,975 bytes, sha256 `c32af167f1fd32288b7e46c49abcdc5c15ef9b21f572352a18e7c2e1bc128947`).
   `checkpoints/`는 git 무시라 **파일을 직접 복사한다**(Windows에서는 `\\wsl$\Ubuntu-24.04\home\cs\workspace\tabletop-ai\Dune-Imperium\checkpoints\2026-09-18\lr1e-4-long\`).
   복사 뒤 `uv run dune-imperium-checkpoint inspect <파일>`로 iteration 1650·codec v105·optimizer yes를 확인한다. 기록은 그 폴더의
   `SUMMARY.md`와 `checkpoints/2026-09-18/ab-550/SUMMARY.md`. **2026-09-19 오후 Mac mini에 복사돼 있고**(같은 경로), 두 파일의 sha256 일치와
   `inspect` 결과를 확인했다.

   **학습률 A/B(1650 출발, 사용자 결정 2026-09-19 15:40 — 후보 (b)) — 완료**, 기록은 `checkpoints/2026-09-19/ab-1650/SUMMARY.md`. 실행 3을
   2,081에서 손으로 멈춰 **(a) lr 1e-4 대조군**으로 삼고(비교는 `iteration_02050.pt`까지), 같은 `latest.pt`(1650, Adam 상태 포함)·같은 seed 0·같은
   설정에서 `--learning-rate 3e-5`만 바꾼 **(b)**를 `checkpoints/2026-09-19/lr3e-5-mac`에서 400 iteration 돌렸다(15:46~17:45; 첫 iteration은 두
   팔이 같은 게임을 수집했고, (b)의 `latest.pt`에서 Adam의 lr 3e-05와 이어진 step을 확인했다). 두 팔 모두 재시작·예외·평가 실패·잘린 판 0.
   - 학습 중 평가(200판, 1700~2050): (a) 84.5·87.5·81.0·81.0·80.5·79.5·81.0·86.0 = **82.6%**, (b) 87.5·84.0·78.0·82.5·83.5·85.0·87.0·86.5 =
     **84.2%**(평균 차 +1.6%p, 표준오차 약 1.5%p).
   - 대전(`ab-1650/evaluate.sh`; seed 1000+, `--rotate-leaders`, 실패 0): 4자 400판 — (b)2050 **27.8%**, 출발점 1650 **26.0%**, (a)2050
     **24.5%**, (b)1850 21.8%(표준오차 약 2.2%p, 두 행의 차는 약 3.6%p); heuristic 3명 상대 200판 — 출발점 1650 **83.0%**(Windows PC의 실측과
     같은 값 — 같은 seed가 두 기기에서 같은 판을 낸다), (a)2050 **88.0%**, (b)2050 **83.5%**.
   - **읽기**: 세 지표가 순서조차 일치하지 않고((b) +1.6, (b) +3.3, (a) +4.5) 전부 잡음 안이다 — 두 학습률은 구별되지 않는다. 그리고 **어느
     팔도 출발점보다 강해지지 않았다**: Windows 실행의 late 테이블(1400·1500·1600·1650 = 24.2·24.8·23.0·28.0%)과 합치면 1400 → 2050의 650
     iteration 동안 대전으로 잴 수 있는 상승이 없다. 3e-4 → 1e-4(550에서 100 iteration 만에 4자 33.0 대 24.5%)와 달리 이번에는 학습률이
     지렛대가 아니다. 한 계보·한 seed·팔당 400 iteration이라 몇 %p짜리 작은 효과는 배제하지 못한다.
   - **남은 가설과 다음 후보**(아래 "다음 후보"를 이 결과로 다시 읽는다): ① 배치 잡음 가설(ab-550의 "배치의 독립 표본은 32판의 승패뿐")은
     **개입으로 확인된 적이 없다** — 후보 (c) iteration당 64판이 그 개입인데, 이 Mac(16 GB)에는 지금 구조로는 들어가지 않는다(32판의 그룹 RSS
     최대 8.6 GiB: 메인 4.6 + worker 4개; 어림으로 64판은 16 GiB를 넘는다 — 재지 않았다). Windows PC(24 GB)에서 돌리거나, 메인이 mask를
     bit-pack한 채 들고 minibatch 때만 푸는 메모리 작업이 먼저다. ② **잣대의 해상도**: 1300 이후 모든 체크포인트가 heuristic 3명에게 83~88%를
     이겨 학습 중 평가는 더 가르지 못한다 — 평가 상대를 rollout이나 과거 체크포인트 테이블로 바꾸는 것(2번 항목의 league·평가 상대 교체)이
     정체를 "정체"라고 부르기 위해서도 필요하다. ③ 표현력(512-512 MLP)·탐험(entropy 0.01)은 아직 건드린 적이 없다. ④ 같은 설정으로 더
     돌리는 것((a)·(b) 어느 쪽이든 `--total`만 키우면 된다)은 기대값이 가장 낮다.
   **학습률 덮어쓰기 버그(`61b09df`)**: 옵티마이저 상태가 든 체크포인트에서 `--resume`하면 `--learning-rate`가 무시되고 저장된 rate로
   학습했다(`restore_optimizer`가 Adam의 `param_groups`를 통째로 복원) — 고치지 않았다면 (b)는 같은 seed의 1e-4 대 1e-4였다. 이제 인자가
   이기고 모멘트·step은 이어진다. 이전 실행들은 무관하다(실험 1은 옵티마이저 없는 `iteration_00550.pt`에서 시작, 밤샘 2는 저장값과 인자가
   둘 다 1e-4). **rate를 바꿔 재개하는 실험은 시작 직후 `latest.pt`의 `optimizer_state.param_groups[0].lr`을 읽어 확인한다.**

   **Mac mini 실행 3 = A/B의 (a)**(2026-09-19 13:36 시작, 15:42 중지; 세션 요약 "M10 Mac mini 이관·실행 3"): `scripts/train/`의 가드·감독기를 macOS로 옮겨
   검증한 뒤(커밋 `bd8732f`) lr1e-4-long과 같은 설정으로 1650에서 이어 띄웠다. 다른 것은 worker 수(8 → 4)뿐이다.

   ```bash
   .venv/bin/python scripts/train/train_overnight.py --detach --dir checkpoints/2026-09-19/lr1e-4-mac --total 1000 --repo . --start-from checkpoints/2026-09-18/lr1e-4-long/latest.pt -- --learning-rate 1e-4 --games-per-iteration 32 --workers 4 --minibatch 1024 --eval-every 50 --eval-games 50 --checkpoint-every 25 --choam --bloodlines --tech-module --immortality --promo-cards
   ```

   - **진행 확인**: `tail -n 2 checkpoints/2026-09-19/lr1e-4-mac/training.jsonl`(한 줄 요약은 `python3 scripts/train/fmt_iter.py <jsonl> <N번째 줄>`),
     끝나면 `supervisor.log`에 `supervisor-exit: finished: 1000 iterations`. **중지**: `kill -TERM $(cat checkpoints/2026-09-19/lr1e-4-mac/supervisor.pid)`.
     **더 돌리기**: 같은 명령의 `--total`만 키워 다시 띄우면 그 폴더의 `latest.pt`에서 잇는다(`--start-from`은 폴더에 기록이 없을 때만 쓰인다).
     실행은 세션과 분리돼(`--detach`) Claude 앱을 닫아도 돌고, 감독기가 `caffeinate`를 쥐고 있어 잠들지 않는다(이 Mac의 `pmset sleep`은 1분이다).
   - **학습 중에는 이 체크아웃의 `src/`를 고치거나 pull하지 않는다**(spawn worker와 지연 import가 작업 트리를 읽는다 — lessons 2026-09-16).
     문서와 `scripts/`는 괜찮다. 엔진·학습 코드 작업이 필요하면 워크트리에서 한다.
   - **이 Mac(M4 4P+6E, 16 GB)의 실측**: iteration당 약 16.5초(수집 8.9초 + 갱신 6.6초 + 235 MB `latest.pt` 저장; Windows PC는 약 33초) →
     1,000 iteration에 4시간 반쯤 + 평가 20회. worker는 **4가 최적**(같은 체크포인트에서 4·5·6·8·10 worker의 수집이 8.8·8.9·9.2·10.8·12.5초 —
     적을수록 빠른 원인은 재지 않았다). 8 worker 스모크의 그룹 RSS 최대 8.2 GiB·가용 최소 2.9 GiB, 4 worker는 8.6 GiB·2.6 GiB(worker당 최대
     1.4 GiB), 커널 메모리 압박 수준은 내내 정상이고 스왑은 늘지 않았다. `--resume`은 iteration 번호와 Adam 상태를 잇고, `--eval-games 50`은
     seed 수(좌석 회전 4배 = 200판, 오차 약 ±3%p)다.
   - **`--device mps`는 쓰지 않는다**(시험 완료): 같은 배치·가중치·옵티마이저 상태의 갱신 한 번이 CPU와 수치로 일치하고(통계 6자리 동일,
     파라미터 변화량의 상대 차이 1.4e-5, 다음 iteration이 같은 게임을 표본한다) 체크포인트는 어느 쪽이든 CPU 텐서로 저장되지만, 갱신이
     6.6 → 5.6초로 iteration의 5%쯤이라 무인 장시간 실행에서 검증 안 된 경로를 쓸 값어치가 없다.
   - **첫 50 iteration(1651~1700)의 실측**: 13분 19초, 수집 평균 9.0초·갱신 6.6초, 잘린 판 0, 게임당 765 step, 그룹 RSS 최대 8.7 GiB·가용 최소
     2.6 GiB·압박 수준 정상·스왑 증가 없음. 학습 중 평가(1700, 200판)는 **84.5%**(평균 순위 1.20, 실패 0; Windows 실행의 1600·1650은 85.5·84.5%)이고
     한 번에 약 95초다 → 전체는 5시간쯤, 18:40 무렵에 끝난다.
   - macOS의 메모리 중단은 가용 메모리 바닥이 아니라 커널 압박 수준(임계 두 번 연속)으로 한다 — 근거와 검증 범위는
     [`scripts/train/README.md`](../../scripts/train/README.md) "메모리 중단 규칙". **임계 분기 자체는 실제로 일으켜 보지 않았다.**
   - **끝난 뒤 할 일**: lr1e-4-long의 `SUMMARY.md`와 같은 형식으로 대전 평가를 돌려 그 폴더에 `SUMMARY.md`를 남긴다. 그 조건(seed 1000+,
     `--rotate-leaders`, 4자 400판·heuristic 3명 상대 200판)으로 재구성한 명령은 아래와 같다(Windows PC 세션의 원 명령은 기록에 없다):
     `uv run dune-imperium-tournament --agents checkpoint:<A>,checkpoint:<B>,checkpoint:<C>,checkpoint:<D> --games 100 --start-seed 1000 --ruleset choam --rotate-leaders --promo-cards --bloodlines --tech-module --immortality --workers 4 --markdown <출력>`,
     heuristic 상대는 `--agents checkpoint:<X>,heuristic,heuristic,heuristic --games 50`. 계보를 잇는 비교가 되도록 1650(출발점)을 테이블에 넣는다.

   **다음 후보**(2026-09-19 아침에 적은 넷 가운데 (a) 같은 설정으로 계속과 (b) 학습률 3e-5는 위 A/B로 **끝났다 — 둘 다 1650에서 더 오르지
   않는다**): (c) iteration당 64판(128판은 24 GB에도 안 들어간다; 이 Mac에는 64판도 지금 구조로는 안 들어간다 — 위 "남은 가설" ①); (d) 두 번째
   seed로 재현; 그리고 위 ②~③(평가 상대 교체, 표현력·탐험). PPO는 큰 배치에서만 다시 볼 가치가 있다. 학습 밖 후보 (a)에 전 확장 census가 남긴 RNG 가족(graft 변형·partner, Commander skill,
   `take_contract`, Spy post, Engineered Miracle의 `command_acquire_row_card`)을 더한다. 열린 관찰: 첫 밤샘 실행 808 iteration의 잘린
   게임 1판은 재현되지 않았고, 16·24 worker가 8 worker보다 느린 원인은 재지 않았다.
0. (2026-09-17 자정 무렵, **M14는 실제 친구와의 한 판만 남았다 — 사용자 몫**) 슬라이스 1~5와 슬라이스 6의 리허설·운영 문서가 master에 있다(아래 세션 요약 셋). **판을 여는 법과 친구에게 보낼 안내는 [remote-play-guide.md](../remote-play-guide.md)** 한 장에 있다: `caffeinate -i uv run dune-imperium-server --remote --host <이 Mac의 100.x 주소>` → 콘솔의 관리자 링크 → 방 생성 → 방 링크를 보낸다(이 Mac mini의 Tailscale 주소는 2026-09-17 현재 `100.87.236.12`; Tailscale 머신 공유 초대는 아직 보내지 않았다). 그 문서 끝의 **첫 실전 판 점검표**(친구 쪽에서 호스트 주소가 같은지, 보드 그림·한 수의 체감 지연, 신호음, 몇 시간짜리 연결, rollout AI 좌석의 멈춤 체감, 되돌리기·확정 흐름, 검토·순위표, WSL2)를 한 판 하면서 채우고, 나온 피드백이 다음 작업이다. **`app.js`를 고치면 [`scripts/e2e/`](../../scripts/e2e/README.md)의 스크립트를 돌린다**(`remote.py`·`open_mode.py`·`races.py --ab`·`recovery.py`, 실전 전에는 `E2E_HOST=<100.x> rehearsal.py`; 스크래치 venv + 시스템 Chrome, 합쳐 3분쯤; pytest는 JavaScript를 실행하지 않는다). 설계 11절의 후속 후보(AI worker와 단계별 푸시, AI 대타, 관전자, 공개 터널용 에셋 게이트, 이름의 저장 파일 보존)는 실전 피드백이 요구할 때만 연다.
0. (2026-09-17, **슬라이스 1~5 완료 + 슬라이스 6의 리허설·운영 문서 완료, 실제 한 판만 남음**, 학습과 병행 가능) **M14 원격 멀티플레이.** 사용자 요구:
   "원격 친구들이랑 각자 PC에서". 설계는 [multiplayer-design.md](../multiplayer-design.md)(같은 날 사용자가 D1~D7을 제안대로
   확정), 마일스톤은 [implementation-plan.md](../implementation-plan.md) M14. 끝난 것: **슬라이스 1**(접근 계층: `server/access.py`,
   좌석 claim/release·관리자 쿠키·진행 중 seed 숨김·CLI `--remote`), **슬라이스 2**(`GET /games/{id}/snapshot` + 서버가 정하는
   로그 `epoch` + gzip, `app.js`의 single-flight `refresh`), **슬라이스 3**(초인종: `add_change_listener`·`DoorbellHub`·
   `GET /games/{id}/events`, 토큰 대조 presence `players[].online`, `EventSource` + 2초 폴링 fallback, 종료 신호에서 스트림을
   끝내는 CLI). **슬라이스 4 — 클라이언트 원격 UX**(설계 7절; **완료**, 위 항목과 아래 세션 요약 — 이하는 착수 전에 적은 작업 목록이다): (1) 진입 — `location.hash`의 `admin=`은
   `POST /auth/admin` 뒤 `history.replaceState`로 지우고, `game=`이면 `/me`(= snapshot의 `you`, 이미 `state.me`에 있다)로 내
   좌석을 보고 게임 화면 또는 좌석 고르기 화면으로; (2) `humanSeats()` 자리에 `mySeats()`(= `state.me.seats`; open 모드는 모든
   사람 좌석이라 지금과 같다); (3) claim 뒤 **스트림을 다시 연다**(스트림은 요청 시점의 쿠키로 presence에 등록된다);
   (4) 대기 배너("좌석 2 (이름) 결정 대기 중"·접속 끊김), 좌석 패널의 이름·접속 점, 내 차례 알림(탭 제목 + WebAudio —
   Notification·clipboard는 보안 컨텍스트 전용이라 Tailscale 평문 HTTP에서는 안 된다); (5) 이름은 `textContent`로만 그리고
   최종 순위표의 `innerHTML` 보간을 없앤다; (6) 남의 행동으로 인한 재렌더가 팝오버·스크롤을 끊지 않게(`render()`의
   `closePopover()`); (7) 호스트 패널(방 링크·좌석 현황·release, CLI `--public-url`), remote에서 설정 화면은 관리자만·Seed 입력
   숨김; (8) 403(좌석을 잃음)·`closed` 처리. 검증은 스크래치 Playwright의 브라우저 컨텍스트 여러 개(쿠키 분리)로 `--remote`
   서버에 대해: 방 생성 → 입장 → claim → 몇 턴 → 새로고침 복귀 → release → 재claim. 범위는 `server/static/`·`cli/server.py`·
   `tests/server/`뿐이라 codec·관측·저장 형식 버전은 그대로다. 브라우저 UI는 슬라이스 4부터 `--remote` 서버에서 동작한다.
   브라우저 E2E 스크립트는 [`scripts/e2e/`](../../scripts/e2e/README.md)에 있고 실행 환경만 저장소 밖 스크래치다(WSL 박스: `uv venv` + `playwright` 모듈,
   캐시된 `~/.cache/ms-playwright/chromium_headless_shell-1234`를 `executable_path`로, 버전 심볼을 갖춘 `libasound.so.2`
   stub을 `LD_LIBRARY_PATH`에). 설계의 수치는 `uv run python scripts/measure_server_payloads.py --seed 20260917`로 재현한다.
0. (2026-09-16 심야, 완료 → 2026-09-17 0번) **M10 학습 재개**(관측 v20·codec v104라 체크포인트 전부 새로; pure self-play로 시작해
   25 iteration마다 재정비된 heuristic·rollout과 대회 평가; 첫 슬라이스 후보는 PPO 전환·league·평가 상대 교체 — 위 2번 항목).
   학습 밖 후보: (a) heuristic 표 밖 항의 나머지(14절(c) 끝: Spy post 규칙 재설계, `take_contract`, Intrigue option,
   확장의 graft partner·Commander skill; 같은 절차 — 스크래치 변형 → `heuristic_uniform_ties`류 **고정 대조군** 상대 축별
   2:2 → 채택), (b) rollout `player_value` 가중치(아래 세션 요약의 결과에 따라), (c) 처리량(throughput 8절(c): 상태 복사 구조
   변경, `_placements_for_card` 루프, provider fan-out), (d) 리팩토링 후속 4건([refactoring-plan.md](../refactoring-plan.md); 이득
   대비 위험으로 보류), (e) 사람 플레이 피드백.
   **다른 세션에서 이어갈 때.** A/B·소크·프로파일 도구는 저장소의 [`scripts/ab/`](../../scripts/ab/README.md)에 있다
   (2026-09-17 정리: census → `pypath/hvariants.py` 변형 → `sanity.py` → `cells.py` 축별 셀 → `pair_matrix.py`/
   `rollout_table.py` → `probe_mix.py` → 채택·고정 → `soak.sh`·`baseline_cells.sh`; 출력은 git 무시 폴더 `ab-runs/`).
   셀 하나(2:2 미러 500 seed)는 이 Mac에서 약 30초, rollout 셀(200판)은 약 6.5분, WSL2 8코어에서는 각 3.5분·30분쯤 잡는다.
   **대조군은 반드시 registry에 고정된 이름**으로 지정하고 셀이 도는 동안 `src/`를 편집하지 않는다([lessons.md](../lessons.md)
   2026-09-16 둘째 항목). 2026-09-16의 원본 스크래치(측정 JSON·로그 포함)는 이 Mac의 세션 scratchpad
   `/private/tmp/claude-501/-Users-cs-Workspace-tabletop-ai-Dune-Imperium/d75b926e-.../scratchpad/`에 남아 있지만 재부팅·정리 시
   사라지며, 수치는 전부 [evaluation/baseline-2026-09-16.md](../evaluation/baseline-2026-09-16.md)와
   [evaluation/throughput-2026-09-10.md](../evaluation/throughput-2026-09-10.md)에 옮겨 적었다.
0. (2026-09-16 저녁, **완료**) 보드 공간 표의 좌표 하강은 18절(m)에서 멈췄다(상위 네 칸 소거 전부 ≤ 0).
   (a) **rollout 정비는 완료**(위 세션 요약; 원인은 playout 노이즈, 기본값 세계 4·후보 3·CRN).
   (b) **상향 소거 완료**(18절(n)): 내린 세 칸을 되돌리면 전부 손해, 낮은 칸(Research Station·Accept Contract·
   Gather Support·Shipping·Secrets)을 올려도 전부 손해이거나 잡음 — 표는 양방향 국소 최적이라 표 작업은 닫는다.
   (c) 아침 목록의 나머지: 처리량 후보([evaluation/throughput-2026-09-10.md](../evaluation/throughput-2026-09-10.md)
   5·7절), 리팩토링 후속([refactoring-plan.md](../refactoring-plan.md)), M10(최후순위).
0. (2026-09-16 **완료**) **Espionage 소거 후속.** 18절(l)의 소거가 Espionage(0.8)를 0.3으로 내리면 base +4.6·
   CHOAM +2.9·Tech +5.5·Immortality +5.2%p라고 했다. 같은 절차: (1) 0.3과 중간 수준 하나를 축별·둘째 블록으로
   `heuristic` 상대 재고, (2) 이기면 채택(이전 표를 registry에 고정하고 **모든 고정 표에 그 항목을 명시**), (3)
   채택한 표의 상위 항목을 다시 소거하고 probe로 mix를 적고, (4) 기준선 12셀을 다시 잰다. 스크래치
   `space-table-closeout/`의 `run_level9.sh`·`adopt_ds.py`·`run_round3.sh`·`write_l.py`가 이 순서의 본이다
   (다른 머신이면 18절의 정의로 재작성; 셀당 3.5분을 잡는다).
0. (2026-09-16 **완료**) **Deliver Supplies 소거 후속.** 18절(k)의 소거가 Deliver Supplies(0.7)를 0.3으로
   내리면 base +9.0·CHOAM +4.3·Tech +4.9·Immortality +4.2%p라고 했다. 이 절의 규칙대로 (1) 그 표를 축별(base·
   CHOAM·Bloodlines·Immortality·Tech 양쪽·CHOAM+Tech+Imm)·둘째 seed 블록으로 `heuristic` 상대 재고, (2) 이기면
   채택(0.3 아래 어디에 둘지 — 0.35 묶음 위/아래 — 두 수준), (3) 채택한 표의 상위 항목을 다시 소거하고 probe로
   배치 mix를 적는다(스크래치 `space-table-closeout/run_round2.sh`·`make_variants.py`가 이 순서를 자동화한다).
   Hagga Basin(+2.7, 경계)은 둘째 블록으로 판정한다.
0. (2026-09-16 **완료**) **공간 표 강등의 마감 측정.** 커밋된 표(Imperial
   Basin·Secrets·Arrakeen 0.3, 전 룰셋 공통)는 스크래치 변형 셀로만 검증됐다(18절). 할 일 순서:
   (1) (2026-09-16 완료 → 18절(g): Tech·Bloodlines·Immortality 소수점까지 재현, base+CHOAM 4,000판 중 4승 차) **커밋 트리 확인 셀** 6개 — 아래 명령을 그대로 돌려 18절(b)·(d)와 맞춘다(Tech CHOAM 없음
   셀은 `demote3_low` 행 28.1%/21.9%와 결정 수까지 같아야 한다); 결과를 18절에 "커밋 트리 확인"
   표로 붙인다. (2) (2026-09-16 완료 → 18절(h); **0.6 채택**, 사용자 판정 — 평소 구성인 CHOAM+Tech에서 0.6이 동률~+2.8%p라 Tech 특례 없이 표 하나: 0.6이 base +4.5·CHOAM +8.2·Immortality +5.6/+7.4%p, Bloodlines·CHOAM Tech는 동률, Tech CHOAM 없음은 −4.9/−5.9%p; 0.45는 0.3과 구분되지 않고 0.75는 전 축 손해; 0.6도 Tech에서 두 칸 표는 +3.4/+2.2%p로 넘는다) **강등 수준 맞대결** — 0.6(`demote3`)이 base+CHOAM에서 재정비 표 상대
   +15.8%p, 0.3은 +9.8%p였다(서로 다른 셀). `HeuristicAgent(space_bonuses={**UPRISING_SPACE_BONUSES,
   "imperial_basin": 0.6, "secrets": 0.6, "arrakeen": 0.6})`를 스크래치 registry에 등록해(17절
   방식; 스크립트는 이 머신의 `/tmp/dune-heuristic-space-table-2026-09-11/tech_ab.py`, 다른
   머신이면 18절의 정의로 재작성) `heuristic` 상대로 base+CHOAM·Bloodlines·Immortality seed
   0~499를 잰다. 0.6이 세 곳에서 이기면 표를 0.6으로 올리고 Tech 두 블록(seed 0~499·500~999)을
   다시 재서 두 칸 표를 여전히 넘는지 확인한 뒤 채택한다. (3) (2026-09-16 완료) OQ-060은 사용자 판정으로
   (a) 소멸을 `DECIDED`했다 — 문서만, 구현 불변. 명령:

   ```bash
   uv run dune-imperium-tournament --agents heuristic,heuristic_untuned,heuristic,heuristic_untuned --games 500 --ruleset base --bloodlines --tech-module --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_untuned,heuristic,heuristic_untuned --games 500 --ruleset choam --bloodlines --tech-module --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_uprising_table,heuristic,heuristic_uprising_table --games 500 --ruleset both --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_uprising_table,heuristic,heuristic_uprising_table --games 500 --ruleset base --bloodlines --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_uprising_table,heuristic,heuristic_uprising_table --games 500 --ruleset base --immortality --rotate-leaders --workers 7
   uv run dune-imperium-tournament --agents heuristic,heuristic_untuned,heuristic,heuristic_untuned --games 500 --ruleset choam --bloodlines --tech-module --immortality --promo-cards --rotate-leaders --workers 7
   ```

   셀 하나는 8코어에서 약 3.5분(1,000 match)이다. 세 작업을 동시에 띄우면 서로 2~3배 느려지니
   순차로 돌린다.
1. (2026-09-11 **기각**) **Tech tile 가치표(`_TECH_BONUSES`) 재정비.** 18장 전체를 효과로 매긴 표와
   비용 가중 세 종(효과±0.15×비용, 비용만)을 Bloodlines+Tech(CHOAM 없음)에서 현행 표와 맞붙였고 전부
   ±2.2%p 안(`net` 두 블록 +0.8/+0.8%p, `effects` −0.4/+2.2%p), 일부러 싼 tile을 고르게 한 대조만
   −4.8%p였다(17절). tile별 구매 분포가 거의 균일해 순위표가 갈리는 결정 자체가 드물다 — 순위는
   지렛대가 아니다. 표는 그대로고 `HeuristicAgent(tech_bonuses=...)` 슬롯과 테스트 1건만 남겼다.
   다음 순위표 항목은 후보 2개 이상인 결정의 비율부터 잰다.
2. (2026-09-11 **기각**) **Tech Module의 공간 표.** 재정비 표 위에 Landsraad 다섯 칸의 Acquire
   Tech 값을 네 가지 방식(정적 δ, 살 수 있을 때만, 값 있는 tile일 때만, 여유 spice)으로 매겨
   Bloodlines+Tech에서 두 칸 표와 맞붙였고 **어느 것도 두 칸 표를 넘지 못했다**(16절). 정적
   δ는 클수록 나쁘고(−17 → −32%p), 게이트는 대조군(−13.6%p)과 같은 자리이며, 최선인 가치
   게이트는 대조군보다 일관되게 낫지만(차 기준 평균 +3.4%p) 네 블록에서 −7.3/−9.9/−1.1/−4.7%p로
   두 칸 표에 진다. 진단: tile 수는 회복되지만(좌석당 최대 4.07장, 두 칸 표 2.27장) 변형의
   Conflict 승수·VP는 움직이지 않고(2.04 → 2.12, 6.77 → 6.81), 두 칸 표는 Tech 없이 놀리던
   spice 11.7과 Landsraad 방문으로 tile을 얻어 득점한다(+0.5 VP); 그 기제는 미확정이다. 15절(b)의 "Landsraad를 끊어 tile을 못 산다"는 손실과 함께 움직인 지표였지
   원인이 아니었다([lessons.md](../lessons.md) 2026-09-11). 배선은 그대로(Tech면 두 칸 표).
   **다음 후보**: (1) Tech 전용 표를 overlay가 아니라 **균형 재설계**로 — 재정비 표의 상위 세 칸
   집중(Imperial Basin 4.5·Secrets 3.9·Arrakeen 3.4/좌석, Combat 배치 53%)을 줄이고 Solari 공간을
   올려 tile을 여유 배치로 사게 하는 표; "값 있는 tile을 살 수 있을 때만 Landsraad" 조건은 단서로 남긴다;
   CHOAM off/on을 **따로** 잰다(재정비 표의 Tech 손실은 CHOAM 없음 −13.6/−9.9%p, CHOAM
   −6.2/−6.9%p로 갈린다). (2) `_TECH_BONUSES` 재정비(Forbidden Weapons·Rapid Dropships가
   0)는 별도 항목. (3) 이 룰셋의 진짜 답은 M10 학습 정책이다.
2. (2026-09-10 완료) **[OQ-059](../rules/open-questions.md#oq-059--시장에-face-up-contract가-남았지만-아무것도-가져갈-수-없을-때의-contract-아이콘)**
   — 판정(보류 후 불발)과 구현을 같은 날 끝냈다. 관측이 v20으로 올라갔다.

**`agent_turn`의 카드 동점**은 끝났다(14절) — 다만 앞 세션이 "남은 동점 995개"로 적은 값은
**재정비 표를 전 확장에 강제 적용한** probe의 수치이고 그 배선은 저장소에 없었다.

**완료(2026-09-08, 사용자 지시 "Immortality 확장 구현"): M13 Immortality.** 슬라이스 1(출처·명세·옵션 골격·board 전사·카탈로그)과 슬라이스 2(Bene Tleilax board의 상태·행동, specimen, 개정 Research Station, Experimentation, Family Atomics; OQ-048~051; 관측 v12, codec v96), 슬라이스 3(Tleilaxu Row 획득·Reclaimed Forces·획득 box의 Research/Tleilaxu·첫 Tleilaxu 카드 3장), 슬라이스 4(Graft: `agent_turn`의 `graft` 인자 + `graft_partner` frame + `switch_graft_card`; Graft 카드 8장), 슬라이스 5a(Intrigue 11장 전부, 관측 v13), 슬라이스 5b-1(Imperium 15종: 조건부 Agent 아이콘·획득 box·trash trigger·Reveal Tleilaxu/Research·specimen 지불; codec v97), 슬라이스 5b-2(남은 Imperium 8종 — Intrigue peek frame·Reveal choice 3종·조건부 획득; 관측 v14, OQ-052~053)는 완료했고, 슬라이스 5c-1(Tleilaxu 6종 + 프로모 Piter), 슬라이스 5c-2(Ghola·Chairdog·Usurp; 관측 v15, OQ-054~055)도 완료해 **Immortality의 카드 play data는 전부 끝났다**. 슬라이스 6(UI 표시·대규모 소크 830판 실패 0·census)도 끝나 **M13은 완료**다. 남은 후속은 [implementation-audits/immortality.md](../implementation-audits/immortality.md)의 "미완 경계"(board 스캔 오버레이, heuristic/rollout 가중치, 관측 v15로 학습 재개). 다음 작업은 아래 목록의 M10(학습, 사용자 결정으로 최후순위) 또는 사용자가 정하는 새 항목이다. 전사는 [implementation-audits/immortality.md](../implementation-audits/immortality.md)에 있다. 설계 메모: Ghola는 활성 카드의 `agent_effect`를 읽는 41곳(`agent_effects.py`)을 접근자(`active_agent_effect(context)`)로 모아 상대 카드의 box를 돌려주게 하고, Usurp는 `choose_graft_partner`에 Imperium Row instance를 허용하고 좌석에 `usurped_row_card_id`를 두어 turn이 닫힐 때 자동으로 trash하며(트리거 발동, OQ-054 사용자 판정), Chairdog는 좌석에 `chairdog_return_card_id`를 두어 `begin_reveal_turn` 앞에서 hand로 되돌린다. Harvest Cells는 Combat 중 Tleilaxu 획득 진입점(DSL 보상 `AcquireTleilaxuCard`)이 필요하다. 그 뒤 6(UI·heuristic·소크). 세부는 [implementation-plan.md](../implementation-plan.md)의 M13 절. 공식 문서가 침묵하는 판정은 구현할 때 open-questions에 등록한다(후보는 audit 문서의 "미완 경계").

2026-09-01의 **검증 강화 캠페인**(사용자 확정 범위: 전체 1→4)은 같은 날 완료했다: 1단계 보드 22칸 완결 + OQ-015(c), 2단계 sweep 확장 (`853ecd4`: 커버리지 census `--coverage-json`, 표본 주기 legal-action 전수 적용 + codec 왕복 `--soundness-interval`, seed별 리더 회전 `--rotate-leaders`), 3단계 교차 소크(아래), 4단계 대조(DIU 63종 전부 일치, open-questions 23건 재점검). 세부는 아래 세션 요약.

0. (2026-09-10 완료) **문서 정정 + 학습 룰셋 배선 + Long Live frame** — 아래 세션 요약. 이로써 M10의 코드 전제조건이 없어졌다: `dune-imperium-train`이 `--promo-cards`/`--bloodlines`/`--tech-module`/`--immortality`를 받는다. **다음 작업 후보**: (a) 기준선 리포트 재측정(`dune-imperium-tournament`가 확장 플래그를 이미 지원하므로 코드 작업 없이 실행만), (b) M10 학습 재개(관측 v19라 새로 시작), (c) `refactoring-plan.md`의 남은 코드 리뷰 후속.
0. (2026-09-08 저녁, **다음 작업 후보**) **디자이너 커뮤니티 판정 대조 후속** — 사용자가 가져온 BGG/Discord 판정 정리본(elessar의 "DUNE IMPERIUM FAQ", 2026-06-07판)을 구현과 대조해 [rules/designer-rulings-audit.md](../rules/designer-rulings-audit.md)에 남겼다(아래 세션 요약). 불일치 13건은 **반영 미결정**이며 사용자가 항목을 고르면 OQ 등록 → 규칙 문서 → 테스트 → 엔진 순으로 진행한다. 가장 큰 묶음은 "효과는 발동 시점을 하나 고르고, 조건이 거짓이면 turn 종료까지 보류"(OQ-028(a)·(c), OQ-002, Guild Spy·Interstellar Trade)이고, 그 밖에 Choose Two 원자성(Propaganda·Stitched Horror·Rapid Engineering), Impress·Change Allegiances의 play 조건, Usurp+Stillsuit, Tech Intrigue의 decline, Ceremony+Suspensor, Harvest Cells 보상 즉시 play, Ghola+Long Reach, Tleilaxu Master가 있다. 콘텐츠 공백이던 **Bloodlines contract token 8개**는 2026-09-09에 전사·구현했다(아래 세션 요약). 사용자 결정(2026-09-09): 불일치 13건은 **디자이너 판정을 무조건 따라** 반영한다 — 추가 확인 2건과 5·6·7·8·9·10·12·13은 반영했고(OQ-057, OQ-002·OQ-054·OQ-037 보강), 13건 전부 반영했고(OQ-057), Intrigue 줄의 개별 사용·지불(OQ-058)도 구현했다. 다음 후속 후보 중 (a) 대규모 소크 재실행과 (b) heuristic/rollout의 Immortality 가치는 2026-09-09 저녁 세션으로 끝났다(아래 세션 요약; 소크 1,300판 실패 0, A/B로 엔진 교착 1건 적발·수정). 남은 것은 (c) M10 학습 재개다(2026-09-10 기준 관측 **v19**·codec v103이라 체크포인트 전부 새로. 확장 룰셋 배선은 2026-09-10 세션으로 끝났다).
0. (2026-09-08 완료) **구현 마감 슬라이스** — 아래 세션 요약. 사용자 결정(2026-09-08): **학습(M10)은 최후순위**로 미루고 구현을 먼저 완결한다. 이 세션으로 핸드오프에 남아 있던 구현 항목 네 가지(OQ-047 판정, 서버 AI 좌석 연결, UI 후보 2건, census 재점검)와 사용자가 추가한 Bloodlines 프로모 카드가 끝났다. 남은 구현 후보: (a) 학습 루프의 `--bloodlines`/`--tech-module`/`--promo-cards` 옵션(아래 (b))은 M10에 속하므로 학습 재개 때 함께; (b) 사람 플레이에서 발견되는 UI·규칙 이슈(사용자 플레이 피드백 대기); (c) 새 공식 FAQ가 나오면 `DECIDED` 항목 재점검. 그 다음이 M10 계속(관측 v10·codec v95라 기존 체크포인트는 전부 거부되므로 새로 시작).
0. (2026-09-07 밤 완료) **M12 슬라이스 7 마감** — 아래 세션 요약. M12는 완료다. 당시 다음 후보: (a) **M10 계속**(아래 2번; 관측 v9·codec v94라 기존 체크포인트는 전부 거부되므로 새로 시작한다 — 이 세션의 smoke `--iterations 3 --games-per-iteration 32 --workers 4`가 정상 동작을 확인했다); (b) 학습 루프의 `--bloodlines`/`--tech-module` 옵션(`training/collect.py`·`loop.py`·`torch_policy.py`의 룰셋 표기가 `choam` 하나뿐이고 체크포인트 룰셋 문자열도 그렇다; Bloodlines 카탈로그는 크기가 달라 별도 네트워크가 필요하다); (c) `implementation-audits/bloodlines.md` 미완 경계의 Endgame tiebreaker Commander 계수 판정(OQ 등록 필요); (d) 서버 AI 좌석의 `rollout`/`checkpoint:` 연결. 원래 슬라이스 7 계획 항목(참고): (a) 서버·UI의 Bloodlines·Tech 표시 마감 — 보드 위 Commander 토큰·Skill·Ixian Embassy(세 stack의 face-up tile)·보유 Tech tile(Flip 면)·Secret Project 표시, Tech tile 이미지 키(`display/images.py`의 required keys에 `tech` 종류 추가 + 비공개 에셋 manifest의 `bloodlines/tech/*.webp` content id), 새 frame(`tech_acquisition`·`tech_choice`·`tech_secret_project`·`skill_choice`)의 프롬프트·카드 표시; (b) heuristic agent의 가중치 정비(현재 `acquire_tech` 2.5로 비용 무관, `flip_tech` 1.5, Forbidden Weapons 검 우선; tile 비용·잔여 spice·능력별 가치 반영), rollout의 `position_value`에 Tech tile 가치 추가; (c) `--bloodlines --tech-module` 대규모 소크(random 룰셋당 2,000판 + heuristic 1,000판 `--rotate-leaders`, draft 500판, `--soundness-interval 25`); (d) 관측 v9 기준 학습 재개(v8 이전 체크포인트는 로더가 거부하므로 새로 시작하거나 옛 가중치 이어 쓰기 로더를 먼저 만든다). 열린 판정 후보: Endgame tiebreaker의 garrison troop 수에 Commander를 세는지(`implementation-audits/bloodlines.md` 미완 경계).
0. (2026-09-07 완료) **M12 Bloodlines 슬라이스 1~5** — 아래 세션 요약.
0. (2026-09-06 밤 완료) 전투력 단일 값(`combat_strength`를 Agent turn부터 매 step 갱신, 관측 v5) + 전투력 토큰·좌석 패널 표시 정리 — 아래 세션 요약. 학습 재개 시 v4 체크포인트는 못 읽으므로 새로 시작하거나 옛 가중치 이어 쓰기 로더를 먼저 만든다.
0. (2026-09-06 저녁 완료) M11 UI 개선 묶음(호버 팝오버, 보드 슬롯의 Conflict·Contract·덱, 병력 칩, 카드 열 세로 배치, 행동 로그 턴 카드) — 아래 세션 요약. 열린 UI 후보: 보드 위 Agent 토큰 이동 애니메이션, 1600px급 화면에서의 오른쪽 패널 2열 기준 조정, 서버 AI 좌석에 `rollout`/`checkpoint:` 연결.
0. (2026-09-03 완료) M11 슬라이스 7 보드 스캔 테이블 + 룰북 아이콘 — 아래 세션 요약. (2026-09-02 완료) 슬라이스 6 행동 되돌리기 + 실시간 행동 로그.
0. (2026-09-06 완료) M10 슬라이스 1 학습 루프(`train` extra, 네트워크·learner·체크포인트·`dune-imperium-train`) + 첫 체크포인트(heuristic 3명 상대 56%) + Imperial Privilege 교착 수정 — 아래 세션 요약.
0. (2026-09-06 완료) M9 슬라이스 3 lockstep self-play 러너(`training/`, `dune-imperium-selfplay`) — 아래 세션 요약. 이로써 M9 완료.
0. (2026-09-06 완료) M9 슬라이스 2 rollout baseline(`RolloutAgent`, determinization, `StateAgent`) — 아래 세션 요약.
0. (2026-09-06 완료) M9 슬라이스 1 대회 도구(`dune-imperium-tournament`) + 첫 기준선 보고서 — 아래 세션 요약.
0. (2026-09-06 완료) OQ-029 구현 검토 + recruit 부족분 이벤트 + OQ-030 판정(해결 시점·소급 없음) — 아래 세션 요약.
0. (2026-09-05 완료) OQ-029 판정 구현 — Combat 배치의 회수·분할과 `finish_agent_turn`(codec v89). 아래 세션 요약.
0. (2026-09-04 완료) 조건 판정 시점 정리(OQ-028) — 아래 세션 요약. 같은 날 병력 회수 규칙은 OQ-029 `OPEN`으로 등록했고 2026-09-05에 판정·구현했다.
0. (2026-09-04 완료) Reveal 선택형 효과 순서 자유화(codec v88) — 아래 세션 요약. 이로써 2026-09-03 심야의 사용자 5건이 모두 끝났다.
0. (2026-09-03 심야 완료) 사용자 5건 중 4건 완료 + 1건 부분: 카드 Agent box 아이콘 분리(codec v87), 되돌리기 가능 표시, 턴 종료 확인, retreat 규칙 확인(문서), 보드 마커.
0. (2026-09-03 밤 완료) 보드 공간 아이콘 분리(OQ-027, codec v86) — 아래 세션 요약.
0. (2026-09-03 저녁 완료) Uprising 프로모 Imperium 3장 — 아래 세션 요약.
1. **M9 평가 러너와 baseline — 2026-09-06 완료.** (1) 대회 도구 + 지표(`dune-imperium-tournament`; 기준선 `docs/evaluation/baseline-2026-09-06.md`), (2) rollout/search baseline(`RolloutAgent`, registry 이름 `rollout`; heuristic 3명 상대 48% 승률, 결정당 약 25ms), (3) lockstep self-play 러너(`training.SelfPlayRunner`: 게임 여러 판을 한 번에 돌리며 좌석별 정책 이름으로 요청을 묶어 정책당 한 번 `act`; `Episode`/`stack_episodes`가 관측·mask·행동·좌석·종료 보상 배열을 내놓는다; `dune-imperium-selfplay` 처리량 약 4,900 decisions/s). 선택 과제(필요할 때): rollout 강화(후보·determinization 수, 2라운드 horizon, 값 함수 가중치)와 M11 서버 AI 좌석에 `rollout` 추가(서버 `sessions.py`는 아직 `choose_action`만 호출하므로 `StateAgent` 경로를 연결해야 한다).
2. **M10 강화학습과 league self-play(진행 중).** 슬라이스 1(2026-09-06 완료): PyTorch `train` extra(사용자 결정: 이 Mac에서 시작, 코드는 `--device cpu|mps|cuda|auto`로 장치 독립, 규모 확장은 RTX 3080 PC에서), masked policy/value MLP(`training/network.py`), 체크포인트(관측 v4·codec v89·룰셋 기록, 불일치 거부), `TorchBatchPolicy`(표본/greedy + 순환 방지)와 `NetworkAgent`(`checkpoint:<경로>`로 대회 참가), REINFORCE + value baseline learner, `dune-imperium-train` 루프(수집 → 갱신 → JSONL 로그 → 체크포인트 → 주기적 대회 평가). 첫 smoke(같은 날, `docs/evaluation/baseline-2026-09-06.md` 5절): pure self-play 30 iteration × 32판(약 6분, CPU)으로 만든 체크포인트가 random 3명 상대 100%, heuristic 3명 상대 56%(rollout 48%보다 높음). `--opponent heuristic`으로 시작하면 초기 정책이 한 판도 못 이겨 신호가 없으니(승률 0%로 20 iteration 정체) pure self-play로 시작한다. 슬라이스 2(같은 날): `--workers N` 병렬 수집(`training/collect.py`; 8 worker로 약 8,500 decisions/s, 단일 3,600), learner의 값 계산 minibatch 분할(메모리 상한), `--step-penalty`(기본 0.0005/결정, 학습 쪽 shaping)와 학습 게임 상한 4,000 결정 — 150 iteration 실행이 41 iteration에서 정책의 되돌리기 반복 학습(게임당 결정 680→1,793)으로 메모리 부족사한 사건의 수정(`lessons.md` 2026-09-06 항목). 두 번째 체크포인트(100 iteration × 64판, 14분): heuristic 3명 상대 89%, 첫 체크포인트 상대 61%, rollout 상대 67%(`baseline-2026-09-06.md` 6절) — 현재 champion. 그 뒤 sampling에도 순환 방지를 적용(`cf24f35`; 이 체크포인트에는 미적용). 비교 실험(사용자 지시, 같은 날 밤): sampling 순환 방지를 켠 제로부터 재학습은 25 iteration에 entropy 0.20·게임당 1,301 결정으로 붕괴해 중단했고(`baseline-2026-09-06.md` 7절; 가려진 행동 대신 다른 되돌리기 변형으로 반복, learner에 off-policy 보정이 없음) sampling 쪽 순환 방지는 되돌렸다(greedy 전용 유지). latest.pt에 optimizer 상태를 실어 `--resume`가 Adam moment까지 잇는다(`2b5dfc3`). 체크포인트 보관 위치: 저장소 루트의 git 무시 폴더 `checkpoints/2026-09-06/`(`.gitignore`)의 `champion_6min_iter30.pt`(5절), `champion_iter100.pt`(6절), `champion_iter200.pt`(8절, 현재 champion, optimizer 상태 포함)와 각 구간의 `training_*.jsonl`. git에는 넣지 않으며(14~40MB), 다른 머신으로는 파일을 복사해 `checkpoint:<경로>` / `--resume <경로>`로 쓴다. 이어서 학습(사용자 지시): 200 iteration 체크포인트가 100 iteration champion 3명 상대 35%(동률 기대 25%), heuristic 상대 91%(`baseline-2026-09-06.md` 8절) — 현재 champion. 그 대회에서 학습 정책이 두 번째 엔진 결함(recall-first Spy 배치의 supply 판정 시점, `[Main pp. 11, 20]`)을 찾아 수정했다. 다음 슬라이스 후보: (a) **3080 PC에서 300+ iteration** — `--resume`으로 잇고 champion과 25 iteration마다 대전; 개선 폭이 줄고 있으니(61% → 35%) 정체하면 (b) 학습률 낮추기·entropy 조정·hidden 확대·PPO(수집 시 log-prob 기록 + clip + 여러 epoch)를 차례로 시험한다. (c) heuristic 상대 승률은 90%대로 포화했으므로 평가 기준 상대를 rollout과 직전 champion으로 바꾼다. (b) 정체하면 학습률·entropy·표본 온도·value 가중치·hidden 크기 조정, PPO 전환. 원래 후보 (a)였던 **더 길게 학습하고 champion 비교** — 100~300 iteration을 돌리며 `dune-imperium-tournament`로 이전 체크포인트·rollout과 직접 대전(3080 PC로 옮겨도 된다; 코드는 `--device auto`); 정체하면 학습률·entropy·표본 온도·value 가중치·hidden 크기를 조정하고, 필요하면 PPO(clip + 여러 epoch; 수집 시 log-prob 기록 필요)로 바꾼다. (b) 수집 병렬화 — `SelfPlayRunner`는 단일 프로세스라 학습 시간의 대부분이 수집이다; worker 프로세스마다 네트워크 사본을 두고 episode를 모으는 방식이 가장 단순하다. (c) league — lineup에 과거 체크포인트(`checkpoint:` 이름은 `AgentBatchPolicy`로 바로 쓸 수 있다)와 rollout을 섞는다. (d) 관측 전처리 개선(카드 identity 임베딩 등)은 (a)가 안정된 뒤. 학습 seed(2,000,000 + seed×1,000,000부터)와 평가 seed(대회 기본 0부터, policy offset 900,000)는 분리돼 있다.

각 묶음은 카드 이미지로 텍스트를 검증하고(`docs/card-data-sources.md`의 방법), `Play ...` / `Document ...` 커밋 쌍을 유지하며, 새 결정 경계는 `FrameKind` → frame `kind` → dispatcher 표 → codec 순으로 추가한다. 핸드오프의 카드 요약은 이미지 검증 전 참고일 뿐이다(Impress 비용, Spring the Trap 유형을 잘못 적었던 전례가 있다).

## 코드 탐색 지도

| 목적 | 주요 위치 |
| --- | --- |
| 카드 manifest와 typed 효과 | `src/dune_imperium/content/uprising/` (Leader identity·Feyd track은 `leaders.py`) |
| Leader 능력과 Signet Ring | `src/dune_imperium/rules/leader_abilities.py`, reach-2 보너스와 Navigation trigger는 `rules/influence.py`, Staban의 Smuggle Spice와 Esmar의 Tuek's Sietch 방문은 `rules/agent_turn.py`; Bloodlines 전용은 `rules/tactics.py`(Chani), `rules/planetologist.py`(Kynes), `rules/navigation.py`(Y'rkoon) |
| Bloodlines 구성물 | `content/bloodlines/sardaukar.py`(Commander·Skill), `content/uprising/imperium.py`·`intrigue.py`의 `bloodlines_only`/`tech_only`/`twisted`/`navigation` 항목, `rules/sardaukar.py`, `rules/spy_moves.py`·`rules/unit_loss.py`(상대 결정 frame), `rules/optional_trash.py` |
| Immortality 구성물 | `content/immortality/board.py`(research·Tleilaxu track), `content/immortality/tleilaxu.py`(Tleilaxu deck·Reclaimed Forces·프로모 Piter), `content/uprising/imperium.py`·`intrigue.py`의 `immortality_only` 항목; 규칙 명세 `docs/rules/immortality.md`, 전사표 `docs/implementation-audits/immortality.md` |
| Tech Module | `content/bloodlines/tech.py`(tile 18장·`TechAbility`), `rules/tech.py`(Acquire Tech·Flip·Forbidden Weapons 선택·Suspensor/빚진 draw hook·Endgame 효과·Secret Project), `rules/ornithopter.py`(Fleet 매칭); 상시 능력은 `agent_turn.py`(Navigation Chamber·Servo-Receivers)·`sardaukar.py`(High Command·Plasteel Blades)·`board_effects.py`(Gene-Locked Vault)·`core/observation.py`(Glowglobes)·`reveal_turn.py`(Command tile·Panopticon·Forbidden Weapons frame)·`contract_tiles.py`(CHOAM Transports)·`combat.py`(Planetary Array·Fleet); Kota의 Signet은 `leader_abilities.py` |
| Agent 배치와 카드 효과 | `src/dune_imperium/rules/agent_turn.py`, `agent_effects.py` |
| Reveal과 acquire | `src/dune_imperium/rules/reveal_turn.py`, `acquisition.py` |
| phase·Combat·Endgame | `src/dune_imperium/rules/phases.py`, `combat.py`, `endgame.py` |
| dispatcher 표와 frame kind | `src/dune_imperium/rules/engine.py`, `frames.py`, `agent_effect_frame.py` |
| effect DSL과 Intrigue | `content/uprising/effect_dsl.py`, `intrigue.py`, `rules/effect_interpreter.py`, `rules/intrigue.py`, `rules/intrigue_deck.py`, `rules/intrigue_triggers.py` |
| 고정 action catalog | `src/dune_imperium/adapters/action_codec.py` |
| 관측과 PettingZoo | `src/dune_imperium/core/observation.py`, `adapters/observation_encoding.py`, `adapters/pettingzoo_env.py` |
| replay와 random 러너 | `src/dune_imperium/core/replay.py`, `simulation/runner.py` (한 라운드·전체 게임) |
| 로컬 플레이 서버·저장·검토 | `src/dune_imperium/server/` (`sessions.py`, `persistence.py`, `app.py`, `catalog.py`, `static/`) |
| 원격 멀티플레이 접근 계층(M14) | `src/dune_imperium/server/access.py`(모드·`Credentials`·토큰), `sessions.py`의 `claim_seat`·`release_seat`·`identify`·`_authorize_seat_locked`·`require_admin`, `app.py`의 쿠키 ↔ `Credentials`, `cli/server.py`의 `--remote`; 설계는 [multiplayer-design.md](../multiplayer-design.md) |
| 영문 효과 표시 텍스트·이미지 매핑 | `src/dune_imperium/display/` (DSL·구조체 렌더러, enum 토큰 맵, 공간·Leader 텍스트, 이미지 파일명) |
| 검증 sweep과 불변식 | `src/dune_imperium/simulation/sweep.py`, `simulation/invariants.py`, `cli/sweep.py` |
| M9 대회 도구와 보고서 | `src/dune_imperium/evaluation/tournament.py`(spec·러너·계측), `evaluation/report.py`(집계·Markdown/JSON), `agents/registry.py`(이름 붙인 baseline), `cli/tournament.py`; 기준선 `docs/evaluation/` |
| M9 search baseline | `src/dune_imperium/agents/rollout_agent.py`(후보 가지치기·determinized rollout·값 함수), `agents/determinize.py`(관측자 지식과 일치하는 세계 표본), `agents/base.py`의 `StateAgent`(러너가 상태를 넘기는 확장 계약) |
| M10 self-play 데이터 | `src/dune_imperium/training/selfplay.py`(lockstep 러너·Episode·stack_episodes), `training/policy.py`(`BatchPolicy`·`PolicyRequest`·random/agent 어댑터), `cli/selfplay.py` |
| M10 학습 | `src/dune_imperium/training/network.py`(masked policy/value MLP), `training/torch_policy.py`(`TorchBatchPolicy`·`NetworkAgent`·순환 방지·체크포인트 로더), `training/checkpoint.py`(버전 고정 저장/로드), `training/learner.py`(REINFORCE + baseline), `training/loop.py`(`TrainConfig`·`train`·평가), `cli/train.py`; `agents/registry.py`의 `checkpoint:` 이름 |
| 카드별 회귀 테스트 | `tests/unit/content/`, `tests/unit/rules/` |
| 통합·adapter 테스트 | `tests/integration/`, `tests/adapters/` |

개인 카드 draw·Spy·Combat·Endgame의 민감한 설계 결정은 `docs/implementation-audits/`의 주제별 문서를 먼저 확인한다.

## 처리량 메모

`RulesEngine.verify_input_immutability`는 매 전이마다 state 전체를 canonical hash하는 디버그 가드라 기본 off다(켜면 random play가 약 70 step/s, 끄면 약 3,000 step/s). 커널 테스트 엔진만 이를 켠다. 완주 soak은 이제 `run_random_game`(약 48ms/판, 9,000 step/s)이나, 불변식·누출 검사와 replay 검증까지 포함하는 `dune-imperium-sweep`(검사 전부 켠 단일 프로세스 약 175ms/판, `--workers 8`로 약 50 games/s)을 그대로 쓴다. env 경유 masked random full episode는 약 4,100 agent step/s다.

2026-09-10에 **처리량 회귀를 측정으로 귀인했다**([evaluation/throughput-2026-09-10.md](../evaluation/throughput-2026-09-10.md)). 요지: 09-06 → 09-10의 59.25 → 38.71 games/s는 **step당 엔진 CPU 약 1.6배**이고, 콘텐츠(확장 4종)가 엔진 전반을 무겁게 만든 결과다. 성능을 재는 절차도 그 문서에 있다 — **CPU 경합에 면역인 지표(cProfile의 호출 횟수, step 수)를 먼저 잡고**, 소요 시간은 기계가 조용할 때 트리를 번갈아 잰다. cProfile의 *누적 시간*은 호출 수에 비례해 부풀므로 트리 간 비교에 쓰지 않는다. 리포트의 `duration`은 worker 기동·import를 포함하고 `ms/decision`은 `_MeteredAgent` 안쪽만 재므로 두 열의 의미가 다르다. 두 기준선 리포트의 `ms/decision` 열은 harness 상수(좌석당 +0.005 ms)를 포함하고 있었고 `ab48e0c`로 없앴으므로, **09-06·09-10 리포트의 그 열은 이후 실행과 직접 비교할 수 없다**.

2026-09-19(Mac mini, M10 실행 3): **학습 수집은 이 Mac의 E코어 6개를 쓰지 못한다.** `Collector`는 게임을 worker 수만큼의 chunk로 정적 분할하므로(`training/collect.py`의 `specs[index::self.workers]`) iteration의 수집 시간은 가장 느린 chunk가 정하고, 4 worker(수집 8.8초)에서 P코어 4개는 99.5%·E코어는 0~25%였다(코어별 부하 실측). worker를 8·10으로 늘리면 오히려 10.8·12.5초다. **후보**: chunk 수를 worker 수와 떼어(예: 2판짜리 chunk 16개를 worker 8~10개가 `pool.map`의 대기열에서 가져가게) 빠른 코어가 더 많은 chunk를 맡게 한다. 8 worker의 수치로 어림하면 E코어 하나는 P코어의 0.4배쯤이라 이론 상한은 수집 −3초(iteration의 약 20%)지만, **어림일 뿐 잰 값이 아니고** chunk가 작아지면 lockstep 추론 배치가 줄고 job마다 가중치를 다시 읽는다 — 워크트리에서 A/B로 잰 뒤에 채택한다(`src/` 변경이므로 학습이 도는 체크아웃에서는 하지 않는다; chunk seed가 바뀌므로 재현성 문서도 함께 고친다). 덧붙여 `latest.pt`(235 MB)를 매 iteration 다시 쓰므로 1,000 iteration에 SSD 쓰기가 약 235 GB다.

## 유용한 명령

```bash
# A/B 도구(census → 변형 → 축별 셀 → 요약; 자세한 절차는 scripts/ab/README.md)
uv run python scripts/ab/census.py --games 40 --ruleset both --out ab-runs/census.json
uv run python scripts/ab/cells.py --name round1 --variants heuristic_v_space --control heuristic_uniform_ties --axes base,choam --seeds 0,500
uv run python scripts/ab/pair_matrix.py ab-runs/round1 v_space

# 사람 팁 census와 비교 (docs/player-tips-for-training.md 7절)
uv run python scripts/ab/tip_census.py --agents heuristic --games 100 --ruleset choam --bloodlines --tech-module --immortality --promo-cards --out ab-runs/tips/h
uv run python scripts/ab/tip_compare.py ab-runs/tips/h ab-runs/tips/other

# 평가 문제집 (docs/evaluation/problem-set.md); 규칙을 고친 뒤에는 check부터 (pytest의 복원 가드와 같은 검사;
# 깨지면 problem-set.md "구조"의 "다시 캐는 명령"으로 다시 캔다)
uv run dune-imperium-problems check
uv run dune-imperium-problems score --agents heuristic,checkpoint:<path>

# 검증 sweep: 카드 보존·교착·관측 누출·replay 검사 (룰셋당 100판 기본)
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8

# 같은 sweep을 heuristic baseline으로 (M11 사람용 상대와 동일 정책)
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8 --policy heuristic

# OQ-007 6-Leader 공개 draft setup으로 완주 검사
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8 --leader-draft

# Immortality의 Go to 11 변형(4인: 승점 0에서 시작, 10점 종료 조건은 그대로)으로 완주 검사
uv run dune-imperium-sweep --games 100 --ruleset both --workers 8 --immortality --go-to-11

# 로컬 플레이 서버 (ui extra 필요; 기본 http://127.0.0.1:8000)
uv run dune-imperium-server

# 원격 멀티플레이 서버 (M14): 콘솔에 찍히는 관리자 링크로 들어가 방을 만들고 방 링크를 보낸다
caffeinate -i uv run dune-imperium-server --remote --host <tailscale 주소>   # 절차 전체: docs/remote-play-guide.md

# 브라우저 E2E (app.js를 고친 뒤; Playwright는 스크래치 venv에만 — scripts/e2e/README.md)
uv venv /tmp/dune-e2e-venv --python 3.12 && uv pip install --python /tmp/dune-e2e-venv/bin/python playwright
(cd scripts/e2e && /tmp/dune-e2e-venv/bin/python run_all.py)   # 27종을 4개씩(약 76초); 고른 것만: run_all.py lang narrow
# 실제 원격 판 전의 리허설: 이 머신의 Tailscale 주소에 bind해서 (docs/remote-play-guide.md)
(cd scripts/e2e && E2E_HOST=100.x.y.z /tmp/dune-e2e-venv/bin/python rehearsal.py)

# UI 카드 이미지 캐시 (선택). 우선: 비공개 Dune-Imperium-assets 저장소를 형제
# 디렉터리에 clone하고 그 README대로 저장소 루트에 assets symlink 하나를 만든다.
# 폴백/신규 카드 채움: 아래 fetch 스크립트 (빈 파일만 받는다)
uv run scripts/fetch_card_images.py

# 한 라운드 random 실행
uv run dune-imperium-debug --seed 2 --random-policy-seed 1002

# 대화형 한 라운드 실행
uv run dune-imperium-debug --seed 2

# 명시적으로 준비한 DIU working copy와 identity/effect shape 대조
uv run dune-imperium-audit-diu ../DIU/data/imperium.JSON

# 공식 PDF와 고정 checksum 재검증; 생성물은 /tmp에만 둔다
uv run scripts/prepare_official_rules.py
```

sandbox에서 uv cache 쓰기가 제한되면 명령 앞에 `UV_CACHE_DIR=/tmp/dune-uv-cache`를 붙인다.

## 원격 저장소 인계 주의

2026-09-28(Mac mini, Arrakeen Scouts 추출·M15 계획 세션, **에셋 저장소 이력 재작성**): 두 저장소 모두 push했다.
- 에셋 저장소에 한 번 push했던 `35752c5`(`reference/dwgr-arrakeen-scouts/`의 도구·추출 데이터·분석, 약 3.9 MB)를 사용자 지시("assets 레포에는 게임에 쓰이는 에셋만 이력에", "원격에 올렸던 커밋도 없애기")로 이력에서 뺐다.
  - `a82825b`로 `--mixed` reset(파일은 유지)한 뒤, 그 폴더를 `.gitignore`에 넣는 **`b2c53eb`**를 만들어 `--force-with-lease`로 push했다. 원격과 로컬의 어떤 ref도 `35752c5`를 가리키지 않는다.
  - **다른 기기**에서 그 사이 에셋 저장소를 pull했다면 `git status`로 로컬 변경이 없는지 본 뒤 `git fetch origin && git reset --hard origin/master`로 맞춘다. 옛 커밋을 가진 채 push하면 지운 커밋이 되살아난다.
- 추출 도구는 메인 저장소 `scripts/dwgr/`로 옮겼다. 추출 결과·분석은 Mac mini의 에셋 체크아웃에 git 밖으로만 남는다.
- 메인 저장소: `ffbf2ae`(계획 문서)와 도구 이관·문서 갱신 커밋.

2026-09-23 저녁(WSL 노트북, **에셋 저장소 이력 정리** — 사용자 지시 "진짜 게임에 쓰이는 asset만 git 이력에"):
전날 다른 기기로 넘기려고 커밋·push한 블로그 사진·크롭·`best/`·매칭 표·도구(`reference/naver-vampmiyu-*`,
854개·354 MB)를 에셋 저장소 이력에서 뺐다. `3fcf62f` 위의 세 커밋을 둘로 다시 만들어 `--force-with-lease`로
push했다: `d01e9d9`(참조 폴더뿐) **삭제**, `ddd34ec` → **`949009a`**(`cards/ko/uprising` 138장),
`85f037c` → **`301fdd0`**(`cards/ko` 혈통 90·불멸 58장, `.gitignore`, README). `cards/ko` 286장은 바이트 그대로,
그 밖의 파일은 `README.md`·`.gitignore`만 다르다. 참조 폴더는 **이 WSL 노트북의 에셋 체크아웃에만** 있고
`.gitignore`(`/reference/naver-vampmiyu-*/`)로 추적에서 빠졌다. 옛 이력은 이 기기의 로컬 브랜치
`backup/pre-cleanup-2026-09-23`에만 있다(push하지 않았다; 필요 없으면 `git branch -D` 뒤 `git gc`). 아래 문단과
세션 요약의 옛 해시(`d01e9d9`·`ddd34ec`·`85f037c`)는 이 정리 전의 것이다. **다른 기기**에서 에셋 저장소를 이미
pull했다면 로컬 변경이 없는지 `git status`로 본 뒤 `git fetch origin && git reset --hard origin/master`로 맞춘다 —
옛 커밋을 가진 채 push하면 지운 커밋이 되살아난다. 메인 저장소 이력은 건드리지 않았다(이미지·중간 산출물 없음).

2026-09-23(WSL 노트북, 한글 카드 이름·그림 세션): 앞 세션의 커밋(에셋 `d01e9d9`, 메인 `18a45ed`)은 사용자가 push해 `origin/master`에 있다. 이 세션은 에셋 저장소에 `cards/ko/` 138장(`ddd34ec`)을, 메인 저장소에 코드·문서 커밋을 더했다 — push 여부는 두 저장소에서 `git log origin/master..master`로 확인한다. 에셋이 없는 기기도 한글 **이름**은 보인다(메인 저장소의 표); 한글 **그림**은 에셋 저장소를 pull해야 보인다.

2026-09-22(WSL 노트북, 한글판 카드 사진 크롭 세션): 비공개 에셋 저장소에 미push 커밋 3건 — `b8784f4`(앞 세션의 Immortality specimen 아이콘), `3fcf62f`(`origin/master`의 `1574241` merge), `d01e9d9`(`reference/naver-vampmiyu-223464306472/`, 약 190 MB). 메인 저장소에는 이 문서 커밋 1건. 이 세션에서는 자동 모드 권한 검사가 push를 막아 **두 저장소 모두 push하지 않았다** — 사용자가 이 기기에서 push한 뒤 다른 기기에서 두 저장소를 pull한다. 새 세션은 `git log origin/master..master`와 반대 방향을 두 저장소에서 모두 확인한다.

2026-09-20 새벽(Mac mini, 보드 조각·아이콘 전사 정정 세션): 이 세션의 커밋(`82a0423`·`c9aec0a`·`7188523`·`2c967b7`와 문서 커밋)은 master에만 있고 **push하지 않았다**. 비공개 에셋 저장소에도 커밋 1건(`e7f7741`: `tokens/maker_hooks.png`·`alliance_<faction>.jpg` + README)이 있고 역시 push하지 않았다 — 다른 기기에서 후크·동맹 토큰 그림을 보려면 두 저장소를 모두 push·pull한다(에셋이 없으면 룰북 아이콘으로 그릴 뿐 동작은 같다). **`src/`의 규칙이 바뀌었으므로 학습이 도는 기기에서는 pull하지 않는다**; pull한 뒤의 학습은 새 규칙의 환경이다(세션 요약의 "M10에 미치는 영향"). 떠 있던 플레이 서버는 재시작해야 새 규칙·새 카탈로그 필드가 적용된다(정적 파일은 즉시 반영).

2026-09-19 오후~저녁(Mac mini, M10 실행 3·학습률 A/B 세션): 이 세션의 앞 커밋 넷(`bd8732f` 학습 가드·감독기의 macOS 이식, `7935740` 문서, `61b09df` 재개 시 학습률 수정, `41e9a7a` 문서)은 16:43에 **push돼 있다**(사용자 쪽에서 한 push다 — reflog의 `update by push`). 그 뒤의 A/B 결과 문서 커밋들은 master에만 있다 — `git log origin/master..master`로 확인한다. `src/` 변경은 `61b09df` 하나이고(옵티마이저 상태에서 재개할 때 `--learning-rate`가 이긴다) 체크포인트 형식과는 무관하다. Windows PC는 pull하면 새 `scripts/train/`(Linux 경로의 동작은 그대로)과 그 수정을 얻는다. **학습이 도는 기기에서는 `src/`가 바뀌는 pull을 하지 않는다.** 체크포인트 폴더는 git 무시라 기기 간에는 여전히 파일을 복사한다(실행 3의 산출물은 이 Mac의 `checkpoints/2026-09-19/lr1e-4-mac/`).

2026-09-19(Mac mini, 사용자 지시 "두 저장소 다 push"): 메인 저장소 `f3b91fb..3b5f4c5`(아래의 merge 커밋을 포함한 21건)와 비공개 에셋 저장소 `02bac8a..f9924b4`(Combat marker 토큰, Shield Wall 토큰·위치 타일 2건)를 push했고, 두 곳 모두 `origin/master`와 로컬이 일치한다. 바로 아래 두 문단의 "push하지 않았다"는 그 시점의 기록이다. 다른 기기는 **두 저장소를 모두 pull**해야 그림 토큰·타일이 보인다(에셋이 없어도 동작은 같다).

2026-09-19(Mac mini): `git fetch`에서 원격이 12건 앞서 있었다(Windows PC의 M10 첫 학습·codec v105·체크포인트 이관·PPO 슬라이스). 이 기기의 미푸시 15건(보드 토큰·원판·보드 조각·에셋 버전)과 겹치는 파일은 `README.md`·이 문서·`lessons.md`뿐이라 **master에서 `origin/master`를 `--no-ff`로 merge**했다(기존 커밋은 고치지 않는다). 충돌은 양쪽 내용을 모두 살려 풀었고, merge한 트리에서 pytest 1,764 · ruff · mypy를 실측했다. merge 커밋과 그 뒤의 작업은 아직 push하지 않았다.

2026-09-18(Mac mini): Combat marker 그림 세션의 커밋(`e54e035` 코드·테스트, `f24eb52` 문서, 그리고 같은 날 Score marker·Councilor token 원판과 공용 player disc 커밋들)은 master에만 있고 **push하지 않았다**. 비공개 에셋 저장소에도 같은 날 커밋 1건(`tokens/` 8장 + README)이 있고 역시 push하지 않았다 — 다른 기기에서 그림 토큰을 보려면 두 저장소를 모두 push·pull해야 한다(에셋이 없으면 그린 토큰으로 돌아갈 뿐 동작은 같다).

2026-09-17 밤~심야(Mac mini): `m14-slice4-client` 브랜치(WIP 커밋 `b319081` + 그 세션의 커밋)를 master 쪽에서 `--no-ff`로 머지했고(`de70942`), 사용자 지시로 슬라이스 5(`657f60c`)까지 `origin/master`에 push했다. 원격의 WIP 브랜치는 사용자가, 로컬 워크트리와 브랜치 `m14-slice4-client`는 2026-09-17 자정 무렵 세션이 지웠다. 그 뒤 슬라이스 6의 커밋들은 master 직접 커밋이다 — push 여부는 `git log origin/master..master`로 확인한다.

2026-09-17 학습 전 최종 점검 세션(WSL 노트북) 종료 시점에 문서 커밋 3건(테스트 수 1,539 정정, 전 확장 학습 전 점검 요약과 0번 다음 작업, 이 문단)을 `git push git@github.com:jungcheolseung/Dune-Imperium.git master`로 push했다. 학습은 Mac mini 또는 14700K PC에서 진행하기로 했으므로, 그 기기에서는 `git pull` 뒤 이 문서의 0번 명령을 그대로 쓴다(체크포인트 폴더 `checkpoints/`는 git 무시이며 기기 간에는 파일을 복사한다).

2026-09-08 M13 세션 종료 시점에 이 세션의 master 커밋 전부(Immortality 슬라이스 1~6의 `Play`/`Document` 쌍, UI, 소크 수정)를 `git push git@github.com:jungcheolseung/Dune-Imperium.git master`로 push했고, 에셋 저장소의 3개 커밋(Ruthless Leadership·Immortality·Experimentation의 `content_id`)도 같은 ssh URL 방식으로 push했다. 새 세션은 `git fetch origin` 뒤 양방향 차이를 확인하고 일치하면 이 문서의 기준선을 그대로 쓴다.

2026-09-07: `bloodlines` 브랜치(35 커밋)를 master 쪽에서 `--no-ff`로 머지했고(`dbd9b73`), 같은 날 저녁 슬라이스 6 커밋 5건과 이 문서 갱신을 master에 직접 올렸다. 아직 push하지 않았다면 `git log origin/master..master`로 확인한다. 비공개 에셋 저장소(`assets` symlink → `Dune-Imperium-assets`)에도 같은 날 manifest 커밋 6건(Bloodlines 카드 44장 content id, Leader 8종, Tuek's Sietch 타일 이미지, Twisted·Navigation 카드 키, Kota Odax의 content id `43c25fc`)이 있으니 다른 머신에서는 그쪽도 pull한다.

2026-09-04 세션 종료 시점에 이 세션의 커밋 전부(보드·카드 아이콘 분리 v86/v87, 서버·UI 확인 흐름과 마커, Reveal 순서 v88, OQ-028 조건 판정 시점, OQ-029 등록)를 `origin/master`에 push했다. 새 세션은 `git fetch origin` 뒤 `git log origin/master..master`와 반대 방향을 확인하고, 일치하면 이 문서의 기준선을 그대로 쓴다. 에셋 저장소(`Dune-Imperium-assets`)의 `5b55e45` 1개 미push 여부는 그 저장소에서 확인한다. 원격에는 병합하지 않은 `kyungtae` 브랜치가 있다. 새 세션은 `git log origin/master..master`와 반대 방향을 모두 확인하고, checkout이 `853ecd4`보다 이전이면 이 문서의 989개 테스트·codec v84 기준선이 실제 코드와 일치하지 않는다. **다른 머신에서 이어서 작업한다면 먼저 이 머신에서 push가 필요하다.** 새 머신의 UI 카드 이미지·아이콘·보드 스캔은 비공개 `Dune-Imperium-assets` 저장소를 clone해 symlink로 연결한다(그 README 참고; 루트의 `assets` symlink 하나로 cards·icons·board·rulebooks를 모두 연결). 카드 매핑은 그 저장소의 `cards/manifest.json`에만 있으므로 접근이 없으면 텍스트 UI로 동작한다.
