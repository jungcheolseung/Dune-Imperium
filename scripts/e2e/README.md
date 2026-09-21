# 브라우저 E2E (`scripts/e2e/`)

플레이 서버의 브라우저 UI(`src/dune_imperium/server/static/`)를 실제 Chrome으로 검증하는 스크립트다.
`pytest`는 JavaScript를 실행하지 않으므로, `static/*.js`를 고친 뒤에는 이 스크립트들이 유일한 회귀 검사다.
2026-09-17 세션에서 스크래치로만 두었다가 다음 세션(다른 기기)에서 전부 다시 만들어야 했기 때문에
저장소에 둔다. **Playwright는 프로젝트 의존성이 아니다**(설계 문서 10절) — 저장소 밖 스크래치 환경으로 돌린다.

## 준비 (기기마다 한 번)

```bash
uv venv /tmp/dune-e2e-venv --python 3.12
uv pip install --python /tmp/dune-e2e-venv/bin/python playwright
```

브라우저는 시스템 Chrome(`channel="chrome"`)을 쓴다. Chrome이 없는 기기(WSL 등)는 실행 파일을 지정한다:
`E2E_CHROMIUM=~/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux/headless_shell`
(WSL에서는 버전 심볼을 갖춘 `libasound.so.2` stub을 `LD_LIBRARY_PATH`에 둬야 했다 — handoff 2026-09-17).
서버는 이 체크아웃의 `.venv/bin/dune-imperium-server`를 빈 포트에 직접 띄우고 끝나면 내린다(`common.ServerProcess`; `kill()`은 SIGKILL이다)
(`uv sync --extra ui`가 돼 있어야 한다). 다른 체크아웃을 검사하려면 `E2E_REPO=<경로>`.

## 실행

```bash
cd scripts/e2e
/tmp/dune-e2e-venv/bin/python remote.py        # 약 25초; `remote.py 120`이면 첫 구간을 120 스텝으로
/tmp/dune-e2e-venv/bin/python open_mode.py     # 약 40초; `open_mode.py game` / `open_mode.py bell`로 절반만
/tmp/dune-e2e-venv/bin/python races.py --ab    # 약 40초
/tmp/dune-e2e-venv/bin/python recovery.py      # 약 30초
/tmp/dune-e2e-venv/bin/python turn_controls.py # 약 20초; 병력 수 조절기와 Reveal 구매 패널
/tmp/dune-e2e-venv/bin/python staged_turn.py   # 1~2분; Agent turn의 단계별 선택(카드 → 칸 → 남은 선택, graft는 두 장 먼저)
/tmp/dune-e2e-venv/bin/python board_tokens.py  # 약 10초; 인쇄된 자리에 놓이는 조각(칸 hotspot의 흰 테두리·Agent·Spy 말·Control·bonus spice·Maker Hooks·Alliance)과 Reveal 미리보기·Intrigue 더미
/tmp/dune-e2e-venv/bin/python spectate.py      # 약 35초; 전 좌석 AI 게임의 관전(리플레이 검토의 자동 재생)
/tmp/dune-e2e-venv/bin/python endgame.py       # 약 40초; 끝난 판의 최종 순위·종료 후 공개, 노트북 1366x768
/tmp/dune-e2e-venv/bin/python narrow.py        # 약 30초; 1100px 미만 레이아웃(전 확장)
/tmp/dune-e2e-venv/bin/python columns.py       # 약 40초; 공용 카드 열 접기와 Bene Tleilax 크게 보기
/tmp/dune-e2e-venv/bin/python seats.py         # 약 35초; 좌석 패널의 자세히 접기
/tmp/dune-e2e-venv/bin/python help.py          # 약 30초; 도움말 창과 스크린 리더 알림(aria-live·role·이름)
/tmp/dune-e2e-venv/bin/python lang.py          # 약 1분; 한국어/English 전환 — 영어에서 한글 0, 왕복 동일, 새로고침 유지
/tmp/dune-e2e-venv/bin/python log_words.py     # 약 10초; 행동 로그·행동 목록·보드 title에 엔진 id가 없는지(두 언어)
E2E_HOST=100.x.y.z /tmp/dune-e2e-venv/bin/python rehearsal.py   # 약 1분; 실제 원격 판 전의 리허설
```

종료 코드 0이 통과다. 실패하면 뒤처진 페이지의 상태와 요청·콘솔 타임라인을 출력하고, 서버 로그 사본을
`$TMPDIR/dune-e2e-server-last.log`에 남긴다.

| 스크립트 | 무엇을 보나 |
|---|---|
| `remote.py` | `--remote` 서버, 쿠키가 분리된 컨텍스트 둘(호스트·친구). 설계 10절 시나리오: `#admin=` 진입 → 방 생성 → 방 링크 → 좌석 고르기·claim → 교차 좌석 403 → 이름(마크업 주입 시도 포함)·접속 점 → **서버가 지목하는 좌석이 한 스텝씩 두고 매 스텝 뒤 두 페이지가 서버 상태로 수렴하는지**(revision·confirmation·players 일치, 둘 차례인 페이지는 그 revision의 actions 보유, 아닌 페이지는 actions 없음) → 대기 배너·탭 제목 → 새로고침 복귀 → 호스트의 release → 재claim → 되돌리기 → 자리 비우기 → claim 도중 나가기·"이어 하기" → 실패한 요청·JS 예외·서버 오류 0. |
| `open_mode.py` | 기본(open) 서버의 회귀. (A) 한 화면이 사람 2 + heuristic 2를 끝까지: 스텝마다 POST 1 + snapshot 1, 매 스텝 클라이언트 로그 길이 = 서버 `log_count`, 되돌리기의 epoch 변경, 이어 붙인 로그 == 서버 전체 로그, 순위표. (B) 검토 모드에서 늦게 온 옛 응답이 화면을 덮지 않는다. (C) 컨텍스트 셋: 초인종 반영 1초 안·snapshot 1개·자기 행동에는 추가 요청 0, 스트림을 막은 컨텍스트의 폴링 전환, 게임 삭제 통지. |
| `races.py` | 응답 순서를 강제로 뒤집는 개입 실험. (1) 기다리는 페이지의 좌석 snapshot을 0.7초 붙잡은 사이 상대가 두 번 더 바꾼다 → 낡은 응답을 채택한 뒤 single-flight의 다음 바퀴가 따라잡아야 한다. (2) 새로고침한 페이지의 스트림을 0.3초, 입장 snapshot을 0.9초 늦춘다(그 snapshot은 `online: false`로 읽혔다) → 비행 중에 온 players 초인종이 한 바퀴를 더 예약해야 한다. `--ab`는 그 예약을 끈 `session.js`로 먼저 돌려 **실제로 stale이 되는지**(검사가 실패할 수 있는지) 확인한다. |
| `recovery.py` | 자동 저장과 복구(슬라이스 5). 원격 한 판을 24 스텝 둔 뒤 서버를 **SIGKILL**하고 같은 포트·같은 저장 폴더로 다시 띄운다: 게임당 파일 하나·`.tmp` 잔재 없음·자동 저장이 live 상태보다 한 턴 이상 뒤처지지 않음, 호스트 패널의 저장 목록, 기다리던 친구의 "서버 연결 끊김" 표시 → 서버가 돌아오면 "새 방 링크로 들어오세요" landing(죽은 방의 "이어 하기"는 제안하지 않음), 호스트가 관리자 링크 → 저장 목록 → 불러오기(새 game id, revision = 자동 저장의 step 수, 좌석 전부 빔), 둘 다 새 링크로 복귀해 16 스텝 수렴, 불러온 게임은 자기 슬롯에 자동 저장. |
| `staged_turn.py` | 사람용 Agent turn UI(2026-09-19). 서버는 Agent turn을 `agent_turn` 행동의 평평한 목록으로 주고(코덱·학습용), 페이지는 그것을 **카드 → 보낼 칸 → 남은 선택** 단계로 보여 주다가 남은 행동 번호 하나를 POST한다. 매 단계에서 화면을 그 목록과 대조한다: 빛나는 카드·칸이 목록이 허용하는 것과 정확히 같은지, 고르는 동안은 요청이 없는지, Escape·단계 칩·다른 카드로 취소·교체가 되는지, 칸을 먼저 골라도 되는지, 다 고르면 **그 행동 하나가** 요청 한 번으로 실행되는지, 남은 placement가 여럿이면(비용 옵션·graft) 선택창과 패널이 정확히 그것들을 내놓는지, "전체 행동 목록 보기" 토글이 모든 합법 행동을 나열하고 새로고침 뒤에도 유지되는지. 선택지가 여럿인 (카드, 칸)은 고정 seed 판에서 찾고 없으면 건너뛴다. 마지막으로 Immortality 판에서 **graft는 두 장을 먼저** 고른다: 함께 낼 수 있는 카드의 ＋ 표시, 두 번째 카드의 합류(교체가 아니라), 빛나는 칸이 두 카드의 graft placement의 합집합인지, 칸을 누르면 placement와 파트너 선택이 요청 둘로 이어 실행돼 두 카드가 in play가 되는지(graft placement가 여섯 판 안에 안 나오면 건너뛴다; 약 1~2분). |
| `turn_controls.py` | 병력 수 조절기와 Reveal 구매 패널(2026-09-19). `deploy_troops` 1·2·…가 패널에서 **한 줄**로 접히고 같은 줄이 보드의 Conflict 구역(자기 사분면 옆)에도 서는지, 보드에서 숫자를 바꾸면 패널 숫자도 바뀌고 요청은 없는지, 확정 버튼의 "지금 → 뒤" 미리보기가 서버의 `strength_after`와 같고 **실행 뒤 실제 전투력과도 같은지**, 회수(`withdraw_troops`)가 count 하나여도 같은 조절기로 되는지. Reveal에서는 `summary.decision.persuasion`과 패널의 표시, 살 수 있는 카드마다의 비용, 출구("구매 끝 · Reveal 종료")가 패널의 마지막인지, 테이블의 빛나는 카드를 누르면 그 비용만큼 Persuasion이 줄고 "산 카드"에 오르는지. |
| `board_tokens.py` | 보드 스캔의 **인쇄된 자리**에 놓이는 조각(2026-09-20). 새 판에서 Alliance token 넷이 각 진영 strip의 점선 원을 정확히 덮는지(`catalog.tracks.influence.alliance`·`alliance_size`), Control·bonus spice·Maker Hooks는 아직 없는지. 칸 hotspot 22개가 카탈로그의 `box`(그 칸이 그림 둘레에 인쇄한 **흰 테두리**, 2026-09-21)와 같은 사각형이고 테두리 윤곽(`.space-frame`)이 `catalog.space_frame.cut`의 깎인 두 모서리를 갖는지, hover가 상자 전체를 칠하지 않고 윤곽만 밝히는지. 칸의 Agent가 공용 윤곽(`#agent-outline`, 문서에 하나)으로 그린 **Agent 아이콘 실루엣**이고 좌석 색·좌석 이름·번호 없음·아이콘 비율(52:81)을 지키며, 넷까지 테두리 안에 나란히 서는지. 관측소의 Spy가 공용 윤곽(`#spy-outline`)의 **Spy 아이콘 원통**(윗면 타원 포함)이고 좌석 색·이름·번호 없음·비율(56:80)을 지키며, 관측소 점(`catalog.posts`)에 가운데 맞춰 서고 혼자면 원판 너비(`catalog.post_size`)인지. 몇 라운드를 둬야 나오는 상태라 **페이지의 view를 고쳐** 다시 그린 뒤(그리기의 입력은 view뿐이다) 브라우저가 실제로 배치한 사각형을 카탈로그 표와 대조한다: Control marker가 세 칸 아래 인쇄된 깃발의 상자와 같고 좌석 색인지, bonus spice 육각형이 인쇄된 Maker 육각형을 덮고 수량을 적는지(0이면 없음), Maker Hooks token이 네 garrison의 슬롯을 채우는지(그림은 돌리고 뒤집어 놓는다), 보유된 Alliance token은 보드를 떠나 보유 좌석 패널에 뜨고 빈 원은 보유자 색 고리가 되는지. 살아 있는 판에서는 `reveal_turn`의 `reveal_preview`(서버 dry run)가 손패 옆 "지금 공개하면"과 Reveal 버튼에 뜨는지, Intrigue discard가 카드 줄 대신 **한 줄**이고 누르면 discard(최신 먼저)·trash 목록이 뜨는지. |
| `spectate.py` | 전 좌석 AI 게임의 관전(2026-09-20). 그런 게임은 앉을 좌석이 없고 서버가 생성 요청 안에서 끝까지 둬 버리므로, 페이지는 그것을 **첫 상태에서 시작하는 리플레이 검토 + 자동 재생**으로 연다(기본 한 턴씩 · 1초). 커서를 페이지의 turn stop 표(`state.review.stops`)와 대조한다: stop마다 두 턴 사이인지(앞 행동이 턴을 닫았거나 다음 행동의 좌석이 다름), 재생이 **모든 stop을 차례로, 약 1초 간격으로** 밟는지, 행동 로그가 커서까지만 보이고 방금 더해진 카드가 fresh인지, 상태 줄이 그 턴을 연 행동과 "외 N수"를 말하는지, 헤더가 최종이 아니라 화면의 라운드·phase를 말하는지. 이어 조작: 일시정지, 한 수씩 · 0.25초, 손으로 넘기면 재생이 멈추고 탐색(슬라이더)은 멈추지 않는지, 검토 좌석을 바꿔도 위치와 재생이 유지되는지(AI 좌석의 손패를 "내 손패"라 부르지 않는다), 끝에 닿으면 멈추고 최종 순위가 뜨며 재생 버튼이 "처음부터 재생"이 되는지, 검토 종료 뒤 "AI 대국 다시 보기"와 새로고침이 다시 처음부터 트는지. 사람 좌석이 있는 게임은 혼자 재생되지 않아야 한다. |
| `endgame.py` | 끝난 판(2026-09-20). 전 확장 + 전 좌석 AI 판은 생성 요청 안에서 끝나므로 그 상태가 싸다. **최종 순위표의 Garrison 칸이 동점 판정이 쓴 수와 같은지**(`rules/endgame.py`는 `troops_garrison + commanders_garrison`으로 순위를 매긴다 — OQ-047), 지휘관이 낀 행은 title에 내역을 적는지, 1등 행만 winner인지. 종료 후 공개(OQ-010 판정 4)가 좌석마다 절과 Hand·Deck 순서·Intrigue·공용 덱·Contract bank를 내놓는지. 마지막으로 같은 판을 **노트북 1366x768**에서 열어 결과에 스크롤로 닿는지 — 스크립트가 두 번째 뷰포트를 쓰는 첫 사례다. |
| `narrow.py` | 1100px 미만 레이아웃(2026-09-20). `#center`가 보드와 공용 카드를 위아래로 쌓고, `#market`이 행이 되고, strip의 카드 줄이 줄바꿈을 멈추는지. **일부러 남긴 비-발견**: 그 줄은 가로 스크롤이 허용되지만(`overflow-x: auto`) 1090·1000·820·700px 어디서도 실제로 넘치지 않는다(`#market`이 wrap이라 strip이 자연 너비를 갖는다). 그래서 보존할 오프셋이 없고, 검사는 그 상태가 **도달 불가**임을 단언한다 — 나중에 넘치게 되면 이 검사가 실패해 알려 준다. |
| `columns.py` | 공용 카드 열 접기(2026-09-20). 전 확장이면 열이 여덟 개다. 각 열이 자기 제목에서 접히는지, `c`가 전부 접었다 펴는지, 접힌 열이 여전히 목록에 남는지, 남이 한 수 둬도(=`#market` 재생성) 접힘이 풀리지 않는지, 새로고침 뒤에도 기억되는지, 입력란에 친 `c`는 그냥 글자인지. 다 접으면 열이 제 너비를 돌려주는지(190→170px; 보드는 그만큼만 큰다 — 보드 크기는 센터 그리드가 정한다). 그리고 **Bene Tleilax board를 크게 보기**: 열 안은 31배 축소지만 크게 열면 5.6배로 본 보드(10.4배)보다 덜 줄고, 연구 칸이 4배 이상 커지고, Escape·배경 클릭으로 닫히며, 남이 한 수 둬도 열린 채 유지되는지. |
| `seats.py` | 좌석 패널 접기(2026-09-20). 좌석 넷이 카드 줄을 "자세히"로 접는지, 접혀도 무엇이 들었는지 말하는지, 한 좌석만 펴도 나머지는 그대로인지, 재렌더·새로고침을 견디는지, `s`가 전부 펴고 접는지, 접은 상태가 실제로 칸 높이를 줄이는지(후반 2,189 → 936px). 존 수치 줄이 영어로 되돌아가지 않았는지도 본다. |
| `help.py` | 도움말과 접근성(2026-09-21). 전에는 클라이언트에 `aria-live` 영역이 하나도 없어 차례 변경도 오류도 스크린 리더에 읽히지 않았고, 아이콘만 있는 컨트롤(검토 막대의 ⏮ ◀ ▶ ⏭, 좌석 토큰)에 이름이 없었고, 아이콘을 설명하는 곳이 없었다. 알림 영역이 polite·atomic이고 `display:none`이 아니라 시각적으로만 숨었는지, 도착 때와 **결정 좌석이 바뀔 때마다** 그 좌석을 말하는지, 오류 줄이 `role="alert"`·연결 알림이 `status`인지, 검토 버튼과 좌석 토큰의 이름. 도움말은 한글 자판이 보내는 `?`(key `?`, code `Slash`)로 열리고 라벨 붙은 modal이며 포커스가 들어가는지, **좌석 패널과 손패에 실제로 그려진 모든 아이콘이 범례에 있는지**(렌더러를 다시 돌리는 게 아니라 교차 확인), 좌석 표시(`C2`·`1st`)와 단축키 넷, 열린 동안 `c`가 뒤에서 동작하지 않는지, Esc·배경 클릭으로 닫히고 포커스가 제자리로 돌아오는지, 입력란의 `?`는 글자인지. |
| `lang.py` | 언어 전환(2026-09-21). 카드·리더·공간 이름과 인쇄 텍스트는 두 언어 모두 영어이므로, 영어에서는 **페이지에 한글이 하나도 없어야** 한다(예외는 다른 언어를 그 언어로 부르는 전환 버튼뿐). 전 확장 seed 7 판에서 텍스트 노드와 title·alt·aria-label·placeholder·문서 제목을 전부 훑는다: live 테이블(몇 수 둔 뒤 포함), 도움말, 끝난 판의 검토 끝·열어 둔 disclosure·종료 배너, 설정 화면. 한국어 → 영어 → 한국어 왕복 뒤 같은 위치의 좌석·배너·로그·공용 카드 텍스트가 **그대로** 돌아오는지, 새로고침 뒤에도 영어인지, 한국어에서는 엔진의 영어 prompt가 번역되고 영어에서는 보낸 그대로인지, 라벨 테이블이 한국어로 되돌아오는지. 이 검사가 찾은 것: 전환 전 문장을 들고 있던 알림 영역, 검토 좌석 선택지, 숨은 설정 화면의 좌석 선택, 취소되지 않은 알림 타이머. |
| `log_words.py` | 행동 로그가 엔진 id가 아니라 말로 쓰이는지(2026-09-21). 끝난 판 넷(heuristic seed 7, random seed 25·30·23 — 영향력 교환·Secrets 훔치기·지도자 드래프트가 나오는 seed)의 로그 전체를 페이지 자신의 함수(`turnLine`·`logEventLine`·`chanceLine`·`describeReviewStep`)로 두 언어에 걸쳐 그리며 `prettify()`를 감싸 둔다: 표가 모르는 id의 마지막 수단이라 **한 번이라도 불리면 누출**이다. 한국어에서는 카탈로그 이름과 용어집이 일부러 영어로 둔 구(Gather Intelligence·set-aside 등, 스크립트의 `KOREAN_KEEPS_ENGLISH`) 밖에 라틴 낱말이 없는지, 영어에서는 한글이 없는지, 두 언어 모두 엔진 id의 모양(snake_case, `a:b:c` 경로, 연구 좌표 `c2r2`, 관측소 id와 그 prettify형)이 없는지 본다. 이어 첫 판의 검토 끝 화면 전체를 좌석 세부를 펴고 title까지 훑는다. 판들이 이 검사가 지키는 자리(무작위 섞기, 관측소 인자, 연구 칸, Feyd 트랙, 스킬 인스턴스, Family Atomics의 치운 카드, 영향력 교환, Secrets 훔치기)에 닿지 않으면 빈 말뭉치로 통과하지 않고 실패한다. 옛 클라이언트에서는 6개 검사가 실패한다(`Count: 2`, `c1r3`, `imperium:blank_slate:0,…`). |
| `rehearsal.py` | 실제 원격 판의 리허설(슬라이스 6). `E2E_HOST`에 **이 머신의 Tailscale 주소**를 주면 서버가 그 주소에만 bind하고 브라우저도 그 주소로 들어간다 — 친구들이 실제로 쓰는 origin, 곧 **보안 컨텍스트가 아닌 평문 HTTP**다(`remote.py`·`races.py`·`recovery.py`도 같은 변수로 그 주소에서 돈다; open 서버는 loopback만 되므로 `open_mode.py`는 아니다). (1) `isSecureContext === false`에서 복사 버튼이 링크를 선택해 두는지, 신호음이 예외를 내지 않는지, 좌석·관리자 쿠키가 HttpOnly·SameSite=Strict·게임 경로 한정이고 `Secure`가 **아닌지**(평문 HTTP에서는 Secure 쿠키가 버려진다). (2) 친구 쪽 브라우저를 DevTools 회선 에뮬레이션으로 조여(100 Mbit/s·RTT 20 ms, 10 Mbit/s·RTT 120 ms) 전 확장 게임의 첫 접속 시간·받은 양, 한 수가 상대 화면에 뜨기까지, 새로고침(캐시)을 잰다. 수치는 출력만 하고 실패 조건은 수렴·캐시·오류뿐이다. |

## 새 검사를 더할 때

- 클라이언트 상태는 `page.evaluate`로 읽는다(2026-09-20에 `app.js`를 `labels`·`core`·`screens`·`session`·
  `review`·`render`·`turn`·`board`·`panels`·`app`로 쪼갰지만 전부 classic script라 `state`·`refreshFlight`·
  `doorbell`·`applyAction` 등은 여전히 한 전역 어휘 범위에 있다. `index.html`의 로드 순서가 곧 옛 파일의
  위에서 아래 순서이고, 그 순서가 바뀌면 top-level const가 TDZ에 걸린다).
  화면 문구보다 상태를 단언하고, 문구는 사용자에게 보이는 약속일 때만 본다.
- `page.route`로 클라이언트를 패치하는 검사는 **그 코드가 지금 어느 파일에 있는지** 확인하고 그 파일을
  건다. route handler 안에서 assert가 터지면 요청이 fulfill되지 않아 `goto` 타임아웃으로만 보인다
  (2026-09-20 `races.py --ab`가 이 방식으로 조용히 깨졌다).
- "N초 기다린 뒤 확인"보다 **수렴 조건을 폴링**한다(`remote.converge`). 멈춤은 타임라인과 함께 실패로 드러난다.
- 경합을 의심하면 추측으로 고치지 말고 `page.route`로 그 순서를 강제해 재현한 뒤 고친다(`races.py`,
  `docs/lessons.md` 2026-09-10·2026-09-11). 동기 API의 route handler 안에서 `time.sleep`하면 그 동안 Playwright의
  다른 handler도 멈춘다 — 두 요청을 서로 다르게 늦추려면 async API를 쓴다(`races.py`의 둘째 실험).
- Playwright는 handler가 선언한 매개변수 개수만큼 인자를 넘긴다. 기본값 매개변수를 둔 handler는 둘째 인자로
  `Request`를 받는다.
