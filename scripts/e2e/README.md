# 브라우저 E2E (`scripts/e2e/`)

플레이 서버의 브라우저 UI(`src/dune_imperium/server/static/`)를 실제 Chrome으로 검증하는 스크립트다.
`pytest`는 JavaScript를 실행하지 않으므로, `app.js`를 고친 뒤에는 이 스크립트들이 유일한 회귀 검사다.
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
/tmp/dune-e2e-venv/bin/python staged_turn.py   # 1~2분; Agent turn의 단계별 선택(카드 → 칸 → 남은 선택, graft는 두 장 먼저)
E2E_HOST=100.x.y.z /tmp/dune-e2e-venv/bin/python rehearsal.py   # 약 1분; 실제 원격 판 전의 리허설
```

종료 코드 0이 통과다. 실패하면 뒤처진 페이지의 상태와 요청·콘솔 타임라인을 출력하고, 서버 로그 사본을
`$TMPDIR/dune-e2e-server-last.log`에 남긴다.

| 스크립트 | 무엇을 보나 |
|---|---|
| `remote.py` | `--remote` 서버, 쿠키가 분리된 컨텍스트 둘(호스트·친구). 설계 10절 시나리오: `#admin=` 진입 → 방 생성 → 방 링크 → 좌석 고르기·claim → 교차 좌석 403 → 이름(마크업 주입 시도 포함)·접속 점 → **서버가 지목하는 좌석이 한 스텝씩 두고 매 스텝 뒤 두 페이지가 서버 상태로 수렴하는지**(revision·confirmation·players 일치, 둘 차례인 페이지는 그 revision의 actions 보유, 아닌 페이지는 actions 없음) → 대기 배너·탭 제목 → 새로고침 복귀 → 호스트의 release → 재claim → 되돌리기 → 자리 비우기 → claim 도중 나가기·"이어 하기" → 실패한 요청·JS 예외·서버 오류 0. |
| `open_mode.py` | 기본(open) 서버의 회귀. (A) 한 화면이 사람 2 + heuristic 2를 끝까지: 스텝마다 POST 1 + snapshot 1, 매 스텝 클라이언트 로그 길이 = 서버 `log_count`, 되돌리기의 epoch 변경, 이어 붙인 로그 == 서버 전체 로그, 순위표. (B) 검토 모드에서 늦게 온 옛 응답이 화면을 덮지 않는다. (C) 컨텍스트 셋: 초인종 반영 1초 안·snapshot 1개·자기 행동에는 추가 요청 0, 스트림을 막은 컨텍스트의 폴링 전환, 게임 삭제 통지. |
| `races.py` | 응답 순서를 강제로 뒤집는 개입 실험. (1) 기다리는 페이지의 좌석 snapshot을 0.7초 붙잡은 사이 상대가 두 번 더 바꾼다 → 낡은 응답을 채택한 뒤 single-flight의 다음 바퀴가 따라잡아야 한다. (2) 새로고침한 페이지의 스트림을 0.3초, 입장 snapshot을 0.9초 늦춘다(그 snapshot은 `online: false`로 읽혔다) → 비행 중에 온 players 초인종이 한 바퀴를 더 예약해야 한다. `--ab`는 그 예약을 끈 `app.js`로 먼저 돌려 **실제로 stale이 되는지**(검사가 실패할 수 있는지) 확인한다. |
| `recovery.py` | 자동 저장과 복구(슬라이스 5). 원격 한 판을 24 스텝 둔 뒤 서버를 **SIGKILL**하고 같은 포트·같은 저장 폴더로 다시 띄운다: 게임당 파일 하나·`.tmp` 잔재 없음·자동 저장이 live 상태보다 한 턴 이상 뒤처지지 않음, 호스트 패널의 저장 목록, 기다리던 친구의 "서버 연결 끊김" 표시 → 서버가 돌아오면 "새 방 링크로 들어오세요" landing(죽은 방의 "이어 하기"는 제안하지 않음), 호스트가 관리자 링크 → 저장 목록 → 불러오기(새 game id, revision = 자동 저장의 step 수, 좌석 전부 빔), 둘 다 새 링크로 복귀해 16 스텝 수렴, 불러온 게임은 자기 슬롯에 자동 저장. |
| `staged_turn.py` | 사람용 Agent turn UI(2026-09-19). 서버는 Agent turn을 `agent_turn` 행동의 평평한 목록으로 주고(코덱·학습용), 페이지는 그것을 **카드 → 보낼 칸 → 남은 선택** 단계로 보여 주다가 남은 행동 번호 하나를 POST한다. 매 단계에서 화면을 그 목록과 대조한다: 빛나는 카드·칸이 목록이 허용하는 것과 정확히 같은지, 고르는 동안은 요청이 없는지, Escape·단계 칩·다른 카드로 취소·교체가 되는지, 칸을 먼저 골라도 되는지, 다 고르면 **그 행동 하나가** 요청 한 번으로 실행되는지, 남은 placement가 여럿이면(비용 옵션·graft) 선택창과 패널이 정확히 그것들을 내놓는지, "전체 행동 목록 보기" 토글이 모든 합법 행동을 나열하고 새로고침 뒤에도 유지되는지. 선택지가 여럿인 (카드, 칸)은 고정 seed 판에서 찾고 없으면 건너뛴다. 마지막으로 Immortality 판에서 **graft는 두 장을 먼저** 고른다: 함께 낼 수 있는 카드의 ＋ 표시, 두 번째 카드의 합류(교체가 아니라), 빛나는 칸이 두 카드의 graft placement의 합집합인지, 칸을 누르면 placement와 파트너 선택이 요청 둘로 이어 실행돼 두 카드가 in play가 되는지(graft placement가 여섯 판 안에 안 나오면 건너뛴다; 약 1~2분). |
| `rehearsal.py` | 실제 원격 판의 리허설(슬라이스 6). `E2E_HOST`에 **이 머신의 Tailscale 주소**를 주면 서버가 그 주소에만 bind하고 브라우저도 그 주소로 들어간다 — 친구들이 실제로 쓰는 origin, 곧 **보안 컨텍스트가 아닌 평문 HTTP**다(`remote.py`·`races.py`·`recovery.py`도 같은 변수로 그 주소에서 돈다; open 서버는 loopback만 되므로 `open_mode.py`는 아니다). (1) `isSecureContext === false`에서 복사 버튼이 링크를 선택해 두는지, 신호음이 예외를 내지 않는지, 좌석·관리자 쿠키가 HttpOnly·SameSite=Strict·게임 경로 한정이고 `Secure`가 **아닌지**(평문 HTTP에서는 Secure 쿠키가 버려진다). (2) 친구 쪽 브라우저를 DevTools 회선 에뮬레이션으로 조여(100 Mbit/s·RTT 20 ms, 10 Mbit/s·RTT 120 ms) 전 확장 게임의 첫 접속 시간·받은 양, 한 수가 상대 화면에 뜨기까지, 새로고침(캐시)을 잰다. 수치는 출력만 하고 실패 조건은 수렴·캐시·오류뿐이다. |

## 새 검사를 더할 때

- 클라이언트 상태는 `page.evaluate`로 읽는다(`app.js`는 classic script라 `state`·`refreshFlight`·`doorbell`·
  `applyAction` 등이 전역 어휘 범위에 있다). 화면 문구보다 상태를 단언하고, 문구는 사용자에게 보이는 약속일 때만 본다.
- "N초 기다린 뒤 확인"보다 **수렴 조건을 폴링**한다(`remote.converge`). 멈춤은 타임라인과 함께 실패로 드러난다.
- 경합을 의심하면 추측으로 고치지 말고 `page.route`로 그 순서를 강제해 재현한 뒤 고친다(`races.py`,
  `docs/lessons.md` 2026-09-10·2026-09-11). 동기 API의 route handler 안에서 `time.sleep`하면 그 동안 Playwright의
  다른 handler도 멈춘다 — 두 요청을 서로 다르게 늦추려면 async API를 쓴다(`races.py`의 둘째 실험).
- Playwright는 handler가 선언한 매개변수 개수만큼 인자를 넘긴다. 기본값 매개변수를 둔 handler는 둘째 인자로
  `Request`를 받는다.
