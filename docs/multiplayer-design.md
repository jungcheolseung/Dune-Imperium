# 원격 멀티플레이 설계 (M14)

상태: **확정** (2026-09-17 작성, 같은 날 사용자가 12절의 D1~D7을 제안대로 확정). 구현은 11절의 슬라이스 순서를 따른다. 사용자 요구는 "원격 친구들이랑 각자 PC에서"(2026-09-17)다. 이 문서는 M11 로컬 플레이 서버(`src/dune_imperium/server/`) 위에 원격 다인 플레이를 얹는 구조 결정과 구현 순서를 기록한다. 규칙 엔진·콘텐츠·codec·관측은 대상이 아니다.

## 1. 목표와 범위

**시나리오.** 호스트 한 명이 자기 PC에서 `dune-imperium-server`를 띄우고, 친구 1~3명이 각자 PC의 브라우저로 접속해 한 판을 끝까지 한다. 사람이 앉지 않은 좌석은 지금처럼 AI(heuristic·rollout·checkpoint)가 맡는다. 친구는 아무것도 설치하지 않는다(접속 수단인 Tailscale 제외, 8절).

**요구.**

- **R1 비공개 정보 경계.** 접속자는 자기 좌석의 `PlayerView`·합법 행동·로그만 받는다. URL이나 요청 본문을 바꾸는 것만으로 남의 손패를 보거나 남의 좌석으로 행동할 수 없다.
- **R2 실시간성.** 다른 좌석(사람·AI)의 변화가 1초 안에 내 화면에 반영된다.
- **R3 복원력.** 새로고침·네트워크 끊김·브라우저 재시작 뒤에도 같은 좌석으로 돌아온다. 서버 프로세스가 죽어도 자동 저장에서 이어 간다.
- **R4 기존 흐름 보존.** 옵션 없이 띄운 로컬 서버(혼자 + AI, 한 화면에서 돌려 하기, 저장·불러오기·검토·되돌리기)는 지금과 똑같이 동작하고 기존 `tests/server/` 테스트는 수정 없이 통과한다.
- **R5 엔진 불변.** `core/`·`rules/`·`content/`·`adapters/`·`agents/`·`training/`은 건드리지 않는다. `ACTION_CODEC_VERSION`·`OBSERVATION_VERSION`·저장 형식 버전이 그대로이므로 다른 머신에서 도는 M10 학습·체크포인트와 독립이다.

**비목표.** 공개 매치메이킹·계정·랭킹, 악의적인 호스트에 대한 방어(3절), 관전자, 채팅(Discord 음성을 전제), 턴 타이머, 모바일 레이아웃, 서버 다중 프로세스·수평 확장, 서버 자체 TLS.

## 2. 출발점: 지금 되는 것과 빠진 것

**이미 되는 것.**

- 4좌석 전부 `human`으로 만들 수 있고, 한 브라우저에서 결정 소유자를 따라 시점을 바꿔 가며 끝까지 둘 수 있다(`tests/server/test_app.py`의 4-human leader draft).
- 결정은 항상 한 좌석 소유다(`core/decisions.py`의 `PlayerDecision.owner`). 여러 좌석이 동시에 입력하는 구간이 없어서 "지금 누구 차례인가"가 값 하나다.
- 가시성의 단일 권위는 `core/observation.py`이고 서버는 좌석별 `PlayerView`, `visible_to`로 거른 이벤트, `hidden_arguments` 가림(`server/sessions.py`의 `_log_entry_json`)만 내보낸다.
- 낙관적 동시성(`revision` + `undo_count` → 409), 되돌리기 창(`server/session_log.py`의 `undo_window`), 턴 종료 확인(`awaiting_confirmation`)이 이미 다인 전제로 설계돼 있다 — 다른 좌석이 행동하면 창이 닫히고, 되돌릴 수 있는 동안은 턴이 넘어가지 않는다.
- 저장은 서버 디스크에만 있고 HTTP로는 메타데이터만 나간다(`server/persistence.py`).
- 누구나 받는 summary의 `decision.prompt`에는 비공개 정보가 없다. 2026-09-17에 `rules/`·`core/`의 prompt 55곳을 전수 확인했다: 전부 고정 문자열이거나 좌석 번호·비용·VP·Conflict tier만 보간한다. 새 `PlayerDecision` prompt에도 손패·덱의 카드 이름을 넣지 않는다(원격에서는 그대로 전원에게 보인다).

**빠진 것.** (코드 위치는 2026-09-17 HEAD `a12e894` 기준)

| # | 문제 | 근거 |
|---|---|---|
| G1 | 좌석 인증이 없다. "사람 좌석인가"만 확인하므로 원격에서는 누구나 `/games/{id}/seats/2/view`로 남의 손패를 읽고 `seat: 2`로 행동한다. | `sessions.py` `_require_human` |
| G2 | summary에 `game_seed`가 있다. 엔진이 결정론적이라 seed + 공개 행동이면 모든 덱 순서와 손패를 로컬에서 복원한다. 저장 목록 메타데이터에도 seed가 있다. | `_summary_locked`, `persistence.py` `save_metadata` |
| G3 | 저장→불러오기는 같은 비공개 상태의 복제 세션을 만든다. 복제본의 좌석을 전부 열어 볼 수 있으면 진행 중인 판의 손패가 보인다. 게임 생성·삭제·저장 목록도 누구에게나 열려 있다. `checkpoint:<경로>` 좌석은 서버 파일 경로를 받는다(`weights_only=True`라 실행 위험은 없지만 경로 탐색·CPU 점유가 된다). | `app.py`의 `/games`·`/saves` |
| G4 | 푸시가 없다. 클라이언트는 자기 POST의 응답으로만 갱신한다. | `app.js` `applySummary`·`refresh` |
| G5 | 클라이언트가 결정 소유자 좌석으로 시점을 자동 전환한다(한 화면 돌려 하기 전제). | `app.js` `applySummary` 앞부분 |
| G6 | 갱신 한 번이 순차 GET 3~4개(summary·view·actions·log)이고 서로 다른 revision을 볼 수 있다. 로그는 매번 **전체**를 받는다(`after=` 커서를 서버는 지원하지만 클라이언트가 안 쓴다). | `app.js` `applySummary`, 9절 실측 |
| G7 | `render()`가 매번 `closePopover()`를 부른다. 남의 행동으로 재렌더되면 내가 보던 카드 팝오버가 닫힌다. | `app.js` `render` |
| G8 | 참가 흐름(초대·좌석 고르기·이름·접속 표시)이 없다. | — |
| G9 | 서버가 죽으면 메모리의 세션이 전부 사라진다. 혼자 할 때보다 4명이 2~3시간 둔 판이 날아가는 비용이 훨씬 크다. | `GameSessionManager._sessions` |

AI 자동 진행이 요청 안에서 세션 lock을 잡고 도는 구조(`_advance_locked`)는 실측상 급한 문제가 아니다(4.8절).

## 3. 신뢰 모델

- **참가자(친구).** 막을 것은 "손쉬운 엿보기와 실수"다: URL·본문 조작으로 남의 view 읽기, 남의 좌석으로 행동, seed로 덱 복원, 저장→불러오기 복제, 이름 칸을 통한 스크립트 주입(7.6절). 서비스 거부나 트래픽 분석은 다루지 않는다.
- **호스트.** 서버 프로세스·메모리·저장 디렉터리(저장 문서에는 seed와 셔플 결과가 있다)를 가진 사람이므로 기술적으로 막을 수 없다. 원칙은 **"호스트도 UI로는 남의 비공개 정보에 닿지 못한다"**이다: 좌석 자격은 claim한 브라우저에만 생기고 호스트 화면에 나타나지 않으며(4.4절), seed는 끝날 때까지 어떤 응답에도 없다. 호스트가 일부러 디스크나 디버거를 여는 것은 친구 사이의 신뢰 문제로 남긴다.
- **네트워크.** 전송 암호화는 터널(Tailscale의 WireGuard, 또는 HTTPS 터널)에 맡기고 서버는 TLS를 직접 하지 않는다. 공유기 포트포워딩 + 평문 HTTP는 지원 대상이 아니다(쿠키와 view가 평문으로 나간다).

## 4. 구조 결정

### 4.1 서버 권위를 유지한다

지금의 구조(상태는 서버에만, 클라이언트는 자기 view만)를 그대로 쓴다. P2P·lockstep은 기각한다: 비공개 정보가 있는 게임에서 모든 피어가 전체 상태를 가지면 R1이 성립하지 않고, 엔진이 Python이라 브라우저에서 돌릴 수도 없다.

### 4.2 접근 모드 두 가지: open(기본)과 remote

- **open** — 지금 동작 그대로. 자격 증명 없이 모든 사람 좌석을 읽고 움직일 수 있고 seed가 보인다. `create_app()`의 기본값이라 기존 테스트가 그대로 돈다(R4).
- **remote** — `dune-imperium-server --remote`. 좌석 쿠키와 관리자 쿠키를 강제하고 seed를 숨긴다.

모드는 `GameSessionManager(access=...)`가 들고, 판정은 세션 계층에 둔다(`app.py`의 "모든 가시성 판정은 세션 계층에" 원칙 유지). `app.py`는 쿠키를 꺼내 `Credentials`로 넘기기만 한다.

안전장치: loopback이 아닌 `--host`는 `--remote` 없이는 시작을 거부한다. open 모드 API를 네트워크에 노출하는 실수(같은 망의 누구나 모든 손패를 읽고 게임을 지운다)를 막기 위해서다. 터널이나 `tailscale serve`는 loopback으로 접속하므로 bind 주소로 모드를 추론하지는 않는다 — 같은 이유로 **클라이언트 IP 기반 신뢰는 쓰지 않는다**(터널 뒤에서는 모든 요청이 127.0.0.1에서 온다).

### 4.3 자격 증명 세 가지

| 자격 | 형태 | 얻는 방법 | 허용하는 것 |
|---|---|---|---|
| 방 입장권 | game id 자체(uuid4 hex, 122 bit 무작위) | 호스트가 공유한 방 링크 `<공유 주소>/#game=<id>` | 공개 summary(seed 없음), 좌석 현황, 초인종 스트림, 빈 좌석 claim, 종료 후 검토 |
| 좌석 쿠키 | `dune_seat_<game_id>_<seat>` = `secrets.token_urlsafe(24)`; `HttpOnly; SameSite=Strict; Path=/games/<game_id>; Max-Age=30일` | 빈 사람 좌석을 claim | 그 좌석의 snapshot·view·actions·log, 행동·되돌리기·턴 확정, 자기 좌석 release |
| 관리자 쿠키 | `dune_admin` = 서버 시작 시 만든 키(`--admin-key`/`DUNE_IMPERIUM_ADMIN_KEY`로 고정 가능); `HttpOnly; SameSite=Strict; Path=/` | 서버가 콘솔에 찍는 관리자 링크 `http://<bind 주소>:8000/#admin=<키>`를 호스트가 연다 → `POST /auth/admin`. 링크의 주소는 실제로 listen하는 주소다: loopback·`0.0.0.0` bind면 `127.0.0.1`, Tailscale IP에만 bind했으면 그 IP(그때는 `127.0.0.1`로 열리지 않는다) | 게임 생성·목록·삭제, 저장·불러오기·저장 삭제, 좌석 release. **남의 view는 허용하지 않는다.** |

쿠키를 고른 이유(헤더 토큰 대비): `EventSource`는 헤더를 못 붙이지만 쿠키는 자동으로 간다. 토큰이 주소창·JS·접근 로그 어디에도 나타나지 않는다(친구들이 Discord로 화면을 공유하는 상황에서 주소창의 토큰은 그대로 유출이다). 좌석별 쿠키라 한 브라우저가 여러 좌석을 들 수 있어 한 PC에 두 명이 앉는 경우도 지금의 시점 전환 그대로 된다. 나중에 에셋 경로를 가려야 하면(8.4절) `<img>` 요청에도 쓸 수 있다. 쿠키가 `SameSite=Strict`라 다른 사이트에서 출발한 요청에는 실리지 않고 서버는 CORS를 열지 않으므로 CSRF 경로가 없다. 방 링크는 fragment(`#`)라 서버·프록시·Referer에 실리지 않는다. 비교는 `secrets.compare_digest`로 한다.

game id를 입장권으로 쓰므로 remote 모드의 `GET /games`(전체 목록)는 관리자 전용이다.

### 4.4 좌석은 링크 배포가 아니라 claim으로 정한다

호스트는 좌석별 링크 넷이 아니라 **방 링크 하나**를 Discord 채널에 올린다. 들어온 사람은 좌석 현황에서 빈 사람 좌석을 고르고 이름을 적어 claim한다. 서버는 그때 좌석 토큰을 만들어 그 브라우저의 쿠키로만 내려 준다.

- 호스트가 남의 좌석 자격을 한 번도 손에 쥐지 않는다(3절의 원칙). 좌석별 링크 방식은 호스트 화면에 네 좌석의 열쇠가 다 떠 있게 된다.
- 링크가 하나라 다시 모일 때(저장 불러오기 뒤 새 game id) 다시 올릴 것도 하나다. 그래서 토큰을 저장 파일에 보존할 필요가 없다.
- **사전 로비 단계는 두지 않는다.** 게임은 지금처럼 생성 즉시 시작하고, claim되지 않은 좌석의 결정이 오면 그냥 기다린다. 늦게 들어온 사람은 로그로 그동안의 진행을 본다. 생성 전 상태 기계가 하나 줄고, 엔진·seed·AI 좌석 구성은 지금과 똑같이 생성 시점에 정해진다.
- 경합: 같은 좌석을 두 명이 누르면 먼저 온 요청이 이기고 나머지는 409를 받아 다른 좌석을 고른다. 자기 쿠키가 이미 유효한 좌석에 다시 claim하면 이름만 바꾸는 멱등 요청이다.
- **release**: 관리자 또는 그 좌석 본인이 좌석을 비운다(토큰 폐기, 이름 삭제, 그 좌석의 presence 소멸 — 스트림 자체는 공개 필드뿐이라 닫지 않는다). 쿠키를 잃었거나(다른 브라우저·기기로 옮김) 자리를 영영 뜬 경우의 복구 수단이다. 빈 좌석은 방에 있는 누구나 다시 claim할 수 있으므로, 떠난 친구의 좌석을 남은 사람이 두 번째 좌석으로 이어 두는 것도 된다(그 좌석의 손패를 보게 되는 것은 일행이 합의할 일).
- 한 브라우저의 다중 claim을 막지 않는다(한 PC에 두 명). 좌석 현황에 이름이 보이므로 몰래 두 좌석을 잡을 수는 없다.

### 4.5 푸시는 SSE "초인종", 데이터는 기존 인증 경로

`GET /games/{id}/events`(`text/event-stream`)는 **공개 필드만 담은 작은 알림**을 보낸다. 클라이언트는 알림의 `revision`·`undo_count`·좌석 현황이 자기가 가진 것과 다르면 인증된 snapshot(4.6절)을 다시 받는다.

```
event: change
id: <seq>
data: {"seq": 41, "revision": 312, "undo_count": 2, "log_count": 318,
       "decision_owner": 1, "confirmation": null, "finished": false,
       "players": [{"seat": 0, "kind": "human", "name": "호스트", "claimed": true, "online": true}, ...]}
```

- 알림에 비공개 정보가 없으므로 모든 구독자에게 같은 payload를 보낸다. 좌석별 필터가 필요한 데이터는 전부 기존 경로로만 나간다 — 가시성 판정 지점이 늘지 않는다. 클라이언트는 `revision`·`undo_count`·`log_count`·`confirmation`·`finished` 중 하나라도 자기 summary와 다를 때만 snapshot을 다시 받는다. 그래서 자기 행동이 울린 초인종은 요청을 만들지 않고(POST 뒤의 snapshot으로 이미 최신), `players`만 바뀐 알림(이름·claim·접속)은 payload의 공개 `players`를 그대로 채택해 요청 없이 끝난다.
- 상태 기반이라 놓친 이벤트를 재전송할 필요가 없다. 재연결하면 `hello`(현재 알림)를 받고 필요하면 새로 고친다. `EventSource`의 자동 재연결을 그대로 쓴다. 게임이 삭제되면 `closed`를 보내고 스트림을 닫는다.
- 구독자마다 큐 대신 **"최신 payload + `asyncio.Event`"**를 둔다. 밀린 알림은 최신 하나로 합쳐지고 느린 클라이언트가 메모리를 키우지 못한다. `seq`가 더 큰 payload만 덮어쓰므로 lock 밖에서 publish 순서가 뒤집혀도 안전하다.
- 세션 계층은 asyncio를 모른다. `GameSessionManager(on_change=callback)`가 변경마다 **lock 안에서 payload를 만들고 lock을 푼 뒤** callback을 부른다(`threading.Lock`은 재진입이 안 되므로 callback이 세션을 다시 읽으면 교착한다). `server/events.py`의 hub가 `loop.call_soon_threadsafe`로 asyncio 쪽에 넘긴다. SSE endpoint는 `async def`라 threadpool(anyio 기본 40)을 점유하지 않는다.
- 15초마다 주석 heartbeat(`: ping`)를 보낸다. 유휴 연결을 끊는 프록시를 넘기고 죽은 연결을 그 주기 안에 감지한다. 헤더는 `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- **presence**: 열린 스트림은 세션에 "연결"로 등록되고(연결 ID → 그 요청이 내민 좌석 토큰들), 사람 좌석은 **어떤 연결이 그 좌석의 지금 토큰을 들고 있는 동안** `online`이다(open 서버에서는 연결이 하나라도 있는 동안 모든 사람 좌석). 좌석별 카운터가 아니라 토큰 대조라서 release 즉시 offline이 되고, 다른 사람이 다시 claim해 접속한 뒤 옛 연결이 끊겨도 꺼지지 않는다. 연결·해제는 `online`이 실제로 바뀔 때만 초인종을 울린다. 스트림은 요청 시점의 쿠키로 등록되므로 claim 직후에는 클라이언트가 스트림을 다시 열어야 그 좌석이 켜진다(슬라이스 4).
- **폴링 fallback**: `EventSource`가 3번 연속 실패하거나 5초 안에 `hello`가 없으면 스트림을 닫고 2초 간격으로 summary(약 0.9 KB)를 폴링한다 — summary에는 알림과 비교할 필드가 전부 있어서 같은 판정 함수를 쓴다. 폴링이 404를 받으면 게임이 사라진 것이다. Cloudflare Quick Tunnel은 SSE를 지원하지 않으므로(8.2절) 이 경로가 실제로 쓰인다.
- 서버 종료: 스트림은 스스로 끝나지 않고 uvicorn은 열린 응답을 기다리므로, CLI의 `uvicorn.Server` 하위 클래스가 종료 신호(`handle_exit`)에서 `hub.close()`를 불러 모든 스트림을 즉시 끝낸다(실측: 스트림 3개가 열린 채 SIGINT → 0.32초에 exit 0; 이 처리 전에는 `timeout_graceful_shutdown` 3초를 다 기다리고 "Cancel 1 running task(s)" ERROR를 남겼다). lifespan shutdown은 uvicorn이 연결을 기다린 **뒤에** 돌기 때문에 쓸 수 없다. 이때는 `closed`를 보내지 않는다 — 서버가 다시 뜨면 게임이 돌아올 수 있으므로 "게임이 삭제됐다"고 알리면 안 된다. `timeout_graceful_shutdown`은 백스톱으로 남긴다.

SSE를 고른 이유: 서버→클라이언트 한 방향이면 충분하고(행동은 기존 POST), Starlette의 `StreamingResponse`만으로 되어 **새 의존성이 0**이다. WebSocket은 지금 lock 파일에 구현 패키지(`websockets`·`wsproto`)가 없어 의존성 추가가 필요하고 재연결을 직접 짜야 하는데 얻는 것이 없다. 브라우저의 HTTP/1.1 origin당 6연결 제한 때문에 같은 게임을 한 브라우저에서 여섯 탭 이상 열면 요청이 막힌다(알려진 SSE 제약, 대응하지 않음).

### 4.6 snapshot endpoint: 갱신 한 번 = 요청 한 번

`GET /games/{id}/snapshot?seat=<n>&log_after=<k>&log_epoch=<e>`가 한 번의 lock 안에서 `{summary, you, view, actions|null, log: {seat, epoch, from, count, entries}}`를 돌려준다. 좌석이 없는 입장자는 `seat` 없이 `{summary, you}`만 받는다. `actions`는 그 좌석이 지금의 결정을 소유할 때만 있다.

- WAN에서 순차 GET 3~4개(G6)를 1 RTT로 줄이고, 네 조각이 같은 revision임을 보장한다.
- 로그는 증분으로 받는다. 이미 받은 항목이 뒤늦게 바뀌는 경우가 둘 있다: 되돌리기는 앞선 항목의 `undone` 표시를 소급해 바꾸고(`mark_undone`), 게임 종료는 가림을 전부 푼다(마지막 step을 되돌리면 다시 가린다). 클라이언트는 요청을 보내는 시점에 그 일이 있었는지 알 수 없으므로 **판단은 서버가 한다**: 서버가 로그마다 `epoch`(좌석·`undo_count`·종료 여부로 만든 불투명한 문자열)를 주고, 클라이언트는 가진 개수(`log_after`)와 그 `epoch`를 그대로 되돌려 보낸다. epoch가 지금 것과 같으면 `from = log_after`부터의 꼬리를, 다르면 `from = 0`으로 전체를 보낸다. 클라이언트 규칙은 "`from`이 0이면 교체, 아니면 덧붙임" 하나뿐이고, 좌석을 바꿔 보는 한 화면 플레이도 epoch에 좌석이 들어 있어 같은 규칙으로 처리된다.
- 어느 좌석을 요청할지는 summary에 달려 있다(결정 소유자를 따라 시점을 바꾸는 한 화면 플레이). 자기 POST의 응답 summary가 있으면 그것으로 좌석을 골라 한 번에 받고, 없으면 지금 보던 좌석으로 요청한 뒤 답이 다른 좌석을 가리킬 때만 한 번 더 요청한다. 좌석이 하나인 원격 브라우저는 항상 한 번이다.
- `GZipMiddleware(minimum_size=1024)`를 켠다(Starlette 내장, 새 의존성 없음). 고정된 Starlette 1.6.0은 `text/event-stream`을 기본 제외 목록에 두므로 초인종 스트림은 압축·버퍼링되지 않는다(`.venv`의 `middleware/gzip.py`에서 확인).
- 기존 개별 endpoint(`/seats/{seat}/view`·`/actions`·`/log`)는 JSON API 호환을 위해 남기고 같은 인증을 적용한다.
- open 모드에서도 쓰므로 혼자 하는 판의 갱신도 빨라진다.

### 4.7 저장·불러오기·자동 저장

- remote 모드에서 저장·불러오기·저장 목록·삭제·게임 생성·삭제는 **관리자 전용**이다(G3). 호스트도 플레이어이므로 remote 모드의 저장 목록은 끝나지 않은 저장의 `game_seed`를 `null`로 내보낸다(3절의 원칙; 저장 문서 자체는 지금처럼 디스크에만 있다).
- 불러오기는 지금처럼 새 game id의 새 세션을 만든다. 좌석은 전부 비어 있고 호스트가 새 방 링크 하나를 다시 올린다. 저장 형식은 v2 그대로다(좌석 토큰·이름을 저장하지 않는다 — 12절 D4).
- **자동 저장**(remote 기본 켬, `--no-autosave`): 턴이 다른 좌석으로 넘어간 요청(행동 또는 턴 확정)의 끝과 게임 종료 때, 세션이 사람 결정(또는 종료)에 멈춘 상태에서 게임당 한 슬롯(`save_id` = game id, `os.replace`로 원자적 덮어쓰기, 이름 "자동 저장 · R<n>")에 쓴다. 세션이 쉬는 지점에서만 쓰므로 `save_game`의 기존 불변식("기록된 steps는 불러오기가 이어 갈 수 있는 상태에서 끝난다")을 그대로 지킨다. 비용은 작다: 끝난 전 확장 한 판(888 step)의 저장 문서가 267 KB이고 만드는 데 33 ms, 직렬화에 2 ms다(2026-09-17, 이 WSL 노트북). open 모드는 저장 디렉터리 동작을 바꾸지 않기 위해 끈 채로 둔다.
- 서버가 죽었을 때: 서버 재시작 → 관리자 링크 → 자동 저장 불러오기 → 새 방 링크 공유 → 각자 claim. 잃는 것은 진행 중이던 한 턴이다.

### 4.8 AI 진행은 당분간 지금 구조(요청 안 동기 실행)

`apply_action`·`confirm_turn`은 세션 lock을 잡은 채 다음 사람 결정까지 chance와 AI 좌석을 진행한다. 그동안 다른 사람의 GET도 같은 lock에서 기다린다. 실측으로는 급하지 않다.

- heuristic 좌석: 요청당 서버 시간 중앙값 0.6 ms, 최대 8.9 ms(9절).
- rollout 좌석: `docs/evaluation/baseline-2026-09-16.md`의 대회 측정(Mac, `--workers 8` 경합 포함)으로 결정당 58 ms(4절, base, 재정비 전 기본값)·86 ms(13절, base, 현행 기본값인 세계 4 · 후보 3)·93 ms(12절, 전 확장, 재정비 전 기본값), 두 배 예산은 약 152 ms다. 9절 실측에서 한 턴의 결정은 많아야 5개 안팎(사람 결정 547개, 확정이 필요했던 턴 종료만 116회)이므로 rollout 좌석 한 턴의 lock 점유는 0.3~0.8초, AI 세 좌석이 연달아 두면 1~2.5초 자릿수다. 현행 기본값의 전 확장 수치는 따로 잰 것이 없다. checkpoint 좌석은 결정당 MLP forward 한 번이다.

그래서 MVP는 구조를 바꾸지 않고, 자동 진행이 끝난 뒤 초인종을 한 번 울린다. AI의 수를 한 단계씩 보여 주고 싶어지면 후속으로 세션별 worker 스레드로 옮긴다. 그때 지킬 불변식을 미리 적어 둔다: (1) worker가 도는 동안 세션에 `advancing` 표시를 두고 `undo`·`apply_action`·`confirm_turn`을 409로 거절한다 — 턴 확정과 AI의 첫 수 사이에 되돌리기가 끼어들면 AI가 되감긴 상태에 수를 둔다. (2) agent에게 물은 수는 반드시 적용한다 — 물어 놓고 버리면 agent의 RNG 스트림이 기록과 어긋나 `restore_game`의 "재생성 == 기록" 검증이 깨진다. (3) 탐색은 lock 밖에서(상태는 불변 객체), 적용은 lock 안에서 revision을 확인하고 한다.

## 5. HTTP API

| Endpoint | open | remote |
|---|---|---|
| `GET /`, `/static/*`, `/catalog`, `/board-image`, `/bene-tleilax-image`, `/card-images/*`, `/icons/*` | 공개 | 공개(비공개 망 전제, 8.4절) |
| `POST /auth/admin` `{key}` **(신규)** | 400 (필요 없음) | 키가 맞으면 관리자 쿠키 |
| `POST /games`, `GET /games`, `DELETE /games/{id}` | 누구나 | 관리자 |
| `POST /games/{id}/save`, `GET /saves`, `POST /saves/{id}/load`, `DELETE /saves/{id}` | 누구나 | 관리자 |
| `GET /games/{id}` | 누구나 | 입장권. 진행 중에는 `game_seed: null` |
| `GET /games/{id}/me` **(신규)** | 모든 사람 좌석 + `admin: true` | 쿠키가 증명하는 좌석들, 관리자 여부 |
| `POST /games/{id}/seats/{seat}/claim` `{name}` **(신규)** | 400 | 입장권 + 빈 사람 좌석 → 좌석 쿠키. 이미 찬 좌석 409, AI 좌석 403 |
| `POST /games/{id}/seats/{seat}/release` **(신규)** | 400 | 관리자 또는 그 좌석 쿠키 |
| `GET /games/{id}/snapshot` **(신규)** | 사람 좌석 | 그 좌석 쿠키(좌석 없이 부르면 입장권) |
| `GET /games/{id}/seats/{seat}/view`·`/actions`, `GET /games/{id}/log?seat=` | 사람 좌석 | 그 좌석 쿠키 |
| `POST /games/{id}/actions`·`/undo`·`/confirm` | 사람 좌석 | 본문 `seat`의 좌석 쿠키 |
| `GET /games/{id}/events` **(신규)** | 누구나 | 입장권. 좌석 쿠키가 있으면 presence에 반영 |
| `GET /games/{id}/review`, `/review/{step}` | 종료 후 | 입장권 + 종료 후(OQ-010 판정 4: 종료 후 전면 공개) |

오류 코드는 지금 규약을 따른다: 모르는 게임·저장 404, 자격 없는 좌석·관리자 아님 403, 낡은 revision·이미 찬 좌석 409, 그 밖의 잘못된 요청 400.

summary에는 두 모드 공통으로 `access`(`"open"`/`"remote"`)와 `players`(좌석별 `kind`·`name`·`claimed`·`online`)가 추가된다. `seats`(좌석 종류 문자열 배열)는 호환을 위해 남긴다. remote 모드에서는 `checkpoint:<경로>`를 파일 이름만 남기고 내보낸다(호스트 디스크의 경로가 친구에게 보일 이유가 없다).

## 6. 세션 계층 변경

- `server/access.py`(신규): `AccessMode`, `Credentials(seat_tokens: frozenset[str], admin_key: str | None)`, 토큰 발급·비교. 프레임워크 중립.
- `GameSession`: `seat_tokens: dict[int, str]`, `seat_names: dict[int, str]`, `connections: dict[int, int]`, `event_seq: int`. 전부 기존 `lock` 아래에서만 바뀐다.
- `GameSessionManager`: 생성자에 `access`, `admin_key`, `on_change`. 신규 `claim_seat`·`release_seat`·`identify`(→ `/me`)·`snapshot`·`doorbell`·`connect`/`disconnect`(presence). 좌석을 받는 기존 메서드는 keyword-only `credentials`를 받고, `_require_human` 뒤에 `_authorize_seat`를 부른다. open 모드에서는 `_authorize_seat`가 아무것도 하지 않는다.
- `_summary_locked`: `access`·`players` 추가, remote이고 진행 중이면 `game_seed`를 `None`으로.
- `server/events.py`(신규): asyncio hub(구독·publish·heartbeat·종료). `create_app(heartbeat_seconds=...)`로 테스트가 주기를 줄일 수 있게 한다.
- `server/persistence.py`: `SaveStore.write_autosave(game_id, document)`와, 끝나지 않은 저장의 seed를 가리는 메타데이터 옵션을 추가. 문서 스키마와 `SAVE_FORMAT_VERSION`은 그대로.
- `cli/server.py`: `--remote`, `--admin-key`, `--public-url`, `--no-autosave`, loopback 검사, 관리자 링크 출력.

## 7. 클라이언트 변경 (`server/static/app.js`)

1. **진입.** `location.hash`의 `admin=`은 `POST /auth/admin` 뒤 주소창에서 지운다(`history.replaceState`). `game=`이 있으면 그 게임의 `/me`와 summary를 받아, 내 좌석이 있으면 게임 화면으로, 없으면 좌석 고르기 화면으로 간다. 마지막 game id는 localStorage에 기억해 "이어 하기"를 제안한다(뷰어별 편의 기능일 뿐, 자격은 쿠키다).
2. **내 좌석.** `humanSeats()`가 하던 역할(시점 후보)을 `mySeats()`(= `/me`의 좌석)가 맡는다. open 모드에서는 `/me`가 모든 사람 좌석을 돌려주므로 지금과 똑같이 결정 소유자를 따라 전환한다. 좌석이 하나면 시점이 고정된다.
3. **갱신.** `applySummary`의 순차 GET을 snapshot 한 번으로 바꾸고, 갱신을 single-flight 루프(도는 중에 온 요청은 "한 번 더" 표시만)로 직렬화한다. 자기 POST가 진행 중일 때 온 초인종은 무시한다(POST 응답 뒤에 어차피 갱신한다).
4. **초인종.** 게임 화면에 들어갈 때 `EventSource`를 열고 나갈 때 닫는다. 실패 시 폴링 fallback(4.5절).
5. **기다리는 화면.** 결정 소유자가 내가 아니면 배너에 "좌석 2 (이름) 결정 대기 중", 미접속이면 "(접속 끊김)"을 보인다. 좌석 패널에 이름과 접속 점을 표시한다. 내 차례가 오면 탭 제목(`▶ 내 차례`)과 짧은 WebAudio 신호음으로 알린다. Notification API와 `navigator.clipboard`는 보안 컨텍스트(HTTPS·localhost)에서만 되므로 Tailscale의 평문 HTTP 주소에서는 기대하지 않는다.
6. **이름은 `textContent`로만 그린다.** 지금 `innerHTML`은 세 곳뿐이고 그중 최종 순위표 행이 좌석 문자열을 보간한다. 이름을 넣는 모든 자리는 `textContent`를 쓰고 그 행도 바꾼다. 서버는 이름을 1~20자, 제어 문자 제거로 검증한다. 이름에 든 스크립트가 다른 친구의 브라우저에서 돌면 그 친구의 쿠키로 view를 읽어 갈 수 있으므로 장난 수준의 문제가 아니다.
7. **남의 행동으로 인한 재렌더가 내 조작을 끊지 않는다(G7).** 초인종발 갱신에서는 열린 팝오버·행동 목록과 로그의 스크롤 위치를 보존한다.
8. **호스트 패널**(관리자만): 방 링크(공유 주소는 `--public-url`, 없으면 입력 칸 + localStorage), 좌석 현황, release 버튼, 저장·자동 저장 목록. 설정 화면(새 게임·저장 목록)은 remote 모드에서 관리자에게만 보이고, 그 모드에서는 Seed 입력 칸을 숨긴다(호스트가 seed를 알면 3절의 원칙이 깨진다; JSON API의 `game_seed`는 테스트·재현용으로 남긴다).
9. **내 좌석 비우기** 버튼(다른 기기로 옮길 때).

## 8. 접속과 호스팅

### 8.1 권장: Tailscale

호스트와 친구가 Tailscale을 설치하고, 호스트가 서버 머신 **한 대만** 친구 계정에 공유한다(machine sharing). 공식 문서 확인(2026-09-17, tailscale.com/kb/1084/sharing): 모든 플랜에서 가능하고, 받는 사람은 아무 Tailscale 계정으로 수락하며, 공유된 머신은 기본 격리(quarantine) 상태라 들어오는 연결에 응답만 한다 — 게임 서버에 필요한 것이 정확히 그것이다.

```bash
uv run dune-imperium-server --remote --host <호스트의 100.x Tailscale IP> --public-url http://<같은 IP>:8000
```

Tailscale 인터페이스에만 bind하므로 집 LAN에도 열리지 않는다. 전 구간 WireGuard 암호화이고 공개 인터넷에 노출되지 않아 카드·보드 스캔이 초대한 기기에만 서빙된다(8.4절). 친구 쪽 주소는 `http://100.x.y.z:8000/#game=<id>`다.

### 8.2 대안

- **Cloudflare Tunnel.** 친구 쪽 설치가 없고 HTTPS(보안 컨텍스트)가 된다. 다만 계정 없는 Quick Tunnel은 공식 문서가 "Quick Tunnels do not support Server-Sent Events (SSE)"와 동시 요청 200개 제한을 명시한다(2026-09-17 확인, developers.cloudflare.com의 TryCloudflare 문서). 이 경우 폴링 fallback으로 동작한다. 그리고 URL을 아는 누구에게나 에셋이 열린다(8.4절).
- **`tailscale serve`**(tailnet 안 HTTPS): 보안 컨텍스트가 필요해지면 검토한다. 공유받은 사용자 쪽에서의 이름 해석·인증서 동작은 확인하지 않았다.
- **공유기 포트포워딩·공개 VPS**: 지원하지 않는다(3절·8.4절).

### 8.3 호스트 머신

- Mac mini 또는 14700K PC. 서버 부하는 heuristic·checkpoint 좌석이면 무시할 수준이다(9절). rollout 좌석은 결정당 CPU 60~90 ms를 쓰므로 같은 머신에서 M10 학습(worker 8개)이 돌면 서로 느려진다.
- **WSL2 주의.** WSL2 안에서 띄운 서버는 NAT 뒤라 다른 기기에서 들어오는 연결을 기본으로는 받지 못한다. 가장 단순한 호스트는 이미 네이티브로 쓰고 있는 Mac mini다. Windows PC라면 WSL 안에 Tailscale을 설치해 WSL 인스턴스를 tailnet 노드로 만들거나 WSL의 mirrored networking을 쓴다(둘 다 이 프로젝트에서 아직 해 보지 않았다 — 슬라이스 6에서 확인).
- 호스트 자신은 콘솔에 찍힌 관리자 링크로 들어가 자기 좌석도 방 링크에서 claim한다. Tailscale IP에만 bind했으면 호스트의 주소도 `http://100.x.y.z:8000`이라 보안 컨텍스트가 아니므로, 호스트 패널의 링크 복사는 `navigator.clipboard` 대신 선택 가능한 입력 칸으로 만든다.

### 8.4 에셋(카드·보드 스캔)

서버가 호스트의 비공개 에셋 체크아웃을 그대로 서빙한다. `AGENTS.md`의 "이미지를 재배포하기 전에 범위와 이용 조건을 확인한다"에 따라 **비공개 망(Tailscale) 안의 초대한 일행에게만** 서빙하는 것을 기본으로 하고, 공개 URL(터널·VPS)로는 열지 않는다. 공개 터널을 꼭 써야 하면 에셋 경로에 멤버 쿠키 검사를 거는 후속 항목(11절)을 먼저 한다. 에셋이 없는 호스트는 지금처럼 텍스트 UI로 동작한다.

첫 접속 때 받는 양: 보드 스캔 11.6 MB, Bene Tleilax 스캔 6.3 MB, 카드 이미지는 장당 중앙값 45 KB(전체 606장 48 MB 중 화면에 나온 것만). 국내 가정 회선 업로드로는 문제가 없을 크기라 웹용 축소본은 실전 점검에서 느릴 때만 만든다.

## 9. 실측 (2026-09-17)

```bash
uv run python scripts/measure_server_payloads.py --seed 20260917
```

HEAD `a12e894`, WSL 노트북(i5-8250U). 전 확장 + 프로모 + leader draft, 좌석 `human ×3 + heuristic`. 사람 좌석은 heuristic이 대신 답해 실제 판과 비슷한 길이를 만들고, 매 사람 결정 직전에 브라우저가 받을 것을 잰다. raw 바이트는 seed로 결정된다.

| 항목 | 값 |
|---|---|
| 게임 | 9 라운드, 726 step, 사람 결정 547 + 턴 확정 116 = 상태를 바꾸는 요청 663 |
| summary | 약 0.6 KB |
| view | 중앙값 12.0 KB(최대 14.5 KB), gzip 2.7 KB; 서버 0.8 ms |
| actions | 결정당 합법 행동 중앙값 4개(p95 18, 최대 44); 0.6 KB(최대 8.8 KB); 서버(dry run 포함) 중앙값 1.8 ms, p95 13 ms, 최대 48 ms |
| 로그 전체(지금 방식) | 중앙값 108 KB, 최대 206 KB; gzip 최대 16.7 KB; 서버 중앙값 4 ms |
| 로그 증분 | 중앙값 0.4 KB, p95 5.5 KB |
| 행동·턴 확정 요청의 서버 시간(heuristic AI 진행 포함) | 중앙값 0.6 ms, 최대 8.9 ms; 요청당 적용 step 중앙값 1, 최대 10 |
| 한 클라이언트가 한 판 동안 받는 로그(사람 결정마다 1회 기준) | 전체 재전송 **57.3 MB**(gzip 4.9 MB) vs 증분 **0.66 MB** |

읽는 법: (1) 갱신 한 번의 크기는 작다 — summary + view + actions + 증분 로그가 약 14 KB, gzip 뒤 3~4 KB. WAN에서 체감을 정하는 것은 크기가 아니라 **순차 요청 수**이고 snapshot이 그것을 1로 만든다. (2) 유일한 낭비는 로그 전체 재전송이다. 원격에서는 남의 행동에도 갱신하므로 클라이언트마다 위 표보다 더 자주 받는다. 증분 + gzip으로 두 자릿수 MB가 1 MB 아래로 내려간다. (3) heuristic 좌석 구성에서는 서버 계산이 병목이 아니다.

**슬라이스 2 뒤(같은 명령, 같은 seed, 같은 머신).** 스크립트가 같은 시점에 두 방식을 나란히 잰다.

| 갱신 한 번(사람 결정 547회 기준) | 이전: 네 번의 호출(summary + view + actions + 로그 전체) | 이후: snapshot 한 번(증분 로그) |
|---|---|---|
| 요청 수 | 4 (결정 소유자가 아니면 3) | **1** |
| 크기 중앙값(최대) | 120.7 KB (221.6 KB) | **14.6 KB** (28.6 KB) |
| gzip 뒤 중앙값(최대) | 12.3 KB (20.6 KB) | **3.3 KB** (4.9 KB) |
| 한 판 누적 | 64.8 MB (gzip 6.7 MB) | **8.3 MB (gzip 1.81 MB)** |
| 서버 시간 | view 0.8 + actions 1.7 + 로그 3.9 ms(중앙값) | 2.7 ms(중앙값), 최대 47.5 ms(합법 행동 44개의 dry run) |

남은 크기는 거의 전부 view(12 KB)다. 브라우저 E2E(headless Chromium, 사람 2 + heuristic 2, 한 화면에서 좌석을 바꿔 가며 293 단계를 끝까지)로 확인한 것: 행동 하나에 POST 1 + snapshot 1(좌석이 바뀌는 턴 넘김에서도 1), 매 단계 클라이언트 로그 개수 = 서버 `count`, 되돌리기 뒤 epoch 변경과 전체 재수신, 종료 뒤 가림 없는 로그로 교체, 끝난 뒤 클라이언트가 이어 붙인 로그 == 서버의 전체 로그, 검토 모드 중의 갱신이 검토 화면을 덮지 않음.

## 10. 테스트 전략

- **세션 계층**(`tests/server/test_access.py`): claim·release·멱등 재claim·경합 409, 좌석 교차 접근 거부(view·actions·log·행동·되돌리기·확정), 관리자 전용 메서드, 진행 중 seed 숨김과 종료 후 공개, open 모드에서 `credentials` 없이 기존 동작.
- **HTTP**(`tests/server/test_remote_app.py`): 플레이어마다 `TestClient`를 따로 만들어 쿠키 jar를 분리한다. 네 jar로 4-human leader draft를 1라운드까지, 쿠키 없는 클라이언트와 남의 쿠키의 403, 관리자 아닌 클라이언트의 생성·저장·불러오기 403, 잘못된 관리자 키.
- **초인종**: hub 단위 테스트(스레드에서 publish, 합치기, `seq` 역전 무시, 종료), 스트리밍 `TestClient`로 "다른 클라이언트의 행동 → `change` 도착" smoke(짧은 heartbeat, 타임아웃), presence 증감, 알림 payload의 **필드 화이트리스트** 테스트(공개 필드 밖의 키가 생기면 실패).
- **snapshot**: 네 조각의 revision 일치, 증분 커서, 되돌리기·종료 뒤의 전체 재요청 규칙, 그리고 예산 테스트 — 고정 seed 한 판에서 증분 로그 누적이 상한(예: 1 MB) 아래.
- **자동 저장**: 턴이 넘어갈 때마다 쓰되 게임당 파일은 하나로 유지, 불러온 세션의 state hash 일치와 이어 두기, open 모드에서는 파일이 생기지 않음.
- **회귀**: 기존 `tests/server/` 전부 무수정 통과(R4). 엔진·codec·관측 테스트는 영향 없음(R5).
- **E2E**(슬라이스 4): headless Chromium의 브라우저 컨텍스트 둘(쿠키 분리)로 방 생성 → 입장 → claim → 몇 턴 → 새로고침 복귀 → release → 재claim, JS·서버 오류 0. M11 때처럼 저장소 밖 스크래치 Playwright로 돌린다(저장소에 Playwright 의존성을 넣지 않는다).
- **실전 점검**(슬라이스 6): Tailscale로 실제 원격 한 판.

## 11. 구현 슬라이스

각 슬라이스는 코드와 테스트를 한 커밋에, 문서 갱신은 별도 커밋에 둔다. 전부 `server/`·`cli/server.py`·`tests/server/` 안이다.

1. **접근 계층과 좌석 claim(서버).** `server/access.py`, 세션의 토큰·이름, claim/release/`me`, 관리자 쿠키와 관리자 전용 경로, summary의 `access`·`players`·seed 숨김, CLI `--remote`·`--admin-key`와 loopback 검사. 완료 조건: remote 모드에서 자격 없는 모든 좌석 접근이 403, 네 쿠키 jar로 1라운드 진행, 기존 테스트 무수정 통과. **완료(2026-09-17).** 구현 메모: (a) 자격 판정은 `GameSessionManager._authorize_seat_locked`·`require_admin` 두 곳뿐이고 `app.py`는 쿠키를 `Credentials`로 옮기기만 한다 — 어느 토큰이 어느 좌석 것인지는 쿠키 이름이 아니라 값 비교로 정한다. (b) 관리자 키는 좌석 view를 열지 않는다(호스트도 플레이어). (c) `players`의 `online`은 presence가 생기는 슬라이스 3에서, CLI `--public-url`·`--no-autosave`는 각각 슬라이스 4·5에서 더한다. (d) 저장 메타데이터의 seed 가림은 `save_metadata(hide_unfinished_seed=...)`이고 remote 서버의 저장·목록 응답이 켠다. (e) 이 슬라이스는 서버만 바꾸므로 브라우저 UI는 슬라이스 4 전까지 `--remote` 서버에서 동작하지 않는다(403) — open 모드는 그대로다.
2. **snapshot + 증분 로그 + gzip.** 서버 endpoint와 미들웨어, 클라이언트 갱신 경로 교체(single-flight). 완료 조건: 갱신이 요청 하나, 예산 테스트 통과, 9절 스크립트로 개선 확인. **완료(2026-09-17).** 구현 메모: (a) `GameSessionManager.snapshot`이 summary·`you`·view·actions·로그 꼬리를 한 lock 안의 한 상태에서 읽고, `legal_actions`·`log`·`identify`와 직렬화 helper를 공유한다. (b) 로그 증분의 기준은 클라이언트가 아니라 서버의 `epoch`가 정한다(4.6절; 설계 초안의 "클라이언트가 `undo_count`를 보고 판단"은 요청 시점에 알 수 없어서 버렸다). (c) `app.js`의 `applySummary`(순차 GET)를 `refresh(summary?)` → `loadSnapshot` → `adoptSnapshot`으로 바꿨고, 갱신은 겹치지 않는다(single-flight: 도는 중에 온 요청은 한 바퀴 더). 검토 모드 중에 온 갱신은 summary만 받고 검토 화면을 건드리지 않는다. (d) `GZipMiddleware(minimum_size=1024)`; 이미지·`text/event-stream`은 Starlette 기본 제외 목록이 거른다. (e) 같은 날 E2E가 드러낸 기존 결함을 따로 고쳤다 — 검토 화면의 응답이 순서가 뒤바뀌어 도착하면(서버가 cursor까지 모든 step을 재생하므로 마지막 step이 가장 느리다) 늦게 온 옛 요청이 화면을 덮었다; 이제 가장 최근 요청만 그린다.
3. **초인종(SSE) + presence + 폴링 fallback.** `server/events.py`, `on_change`, `/events`, 클라이언트 `EventSource`. 완료 조건: 두 브라우저에서 한쪽 행동이 1초 안에 다른 쪽에 반영, SSE를 막아도 3초 안에 반영. **완료(2026-09-17).** 구현 메모: (a) `GameSessionManager.add_change_listener`; 바뀌는 메서드는 전부 "lock 안에서 payload를 만들고(`_ring_locked`, `event_seq` 증가) lock을 푼 뒤 `_publish`"한다 — listener가 세션을 다시 읽어도 교착하지 않는다(테스트로 고정). (b) `server/events.py`의 `DoorbellHub`: 구독자마다 "최신 payload + `asyncio.Event`", `seq`가 큰 것만 덮어씀, 구독 등록을 인사말(`hello`)을 읽기 **전에** 해서 그 사이의 변경을 잃지 않는다. `publish`는 어느 스레드에서든 부를 수 있고 절대 예외를 내지 않는다. (c) 세션 호출은 lock을 잡으므로 SSE endpoint(`async def`)에서 `run_in_threadpool`로 부르고, 연결 등록·해제는 generator 안의 `try/finally`(취소 shield)로 짝을 맞춘다. (d) Starlette `TestClient`는 끝나지 않는 응답을 스트리밍하지 못해서(본문을 전부 버퍼링) HTTP 테스트는 스레드에서 띄운 실제 uvicorn + `httpx2`로 한다. (e) 실측(브라우저 E2E, 컨텍스트 3개): 초인종으로 241 ms(Playwright 폴링 오차 포함)에 반영·snapshot 요청 1개·자기 행동에는 추가 요청 0개, 스트림을 막은 브라우저는 2.2초 만에 폴링으로 전환해 1.6초에 반영, 게임 삭제는 `closed`와 폴링 404로 양쪽에 통지. 서버에서 잰 POST → `change` 도착은 4 ms.
4. **클라이언트 원격 UX.** 좌석 고르기·이름, 내 좌석 고정, 대기 배너·접속 표시·차례 알림, 팝오버·스크롤 보존, 호스트 패널, 설정 화면의 관리자 제한, `textContent` 점검, E2E. 완료 조건: 10절의 E2E 시나리오 통과. **여기까지가 첫 원격 한 판의 최소 구성이다.**
5. **자동 저장과 복구.** `write_autosave`, 턴이 넘어갈 때의 저장, 복구 절차. 완료 조건: 서버 강제 종료 → 재시작 → 자동 저장에서 이어 가기.
6. **실전 점검과 운영 문서.** README의 호스트 절차(Tailscale, `--remote` 명령, WSL 주의), 실제 친구와 한 판, 피드백 반영, 필요하면 보드 스캔 축소본.

후속(필요해질 때): AI worker와 단계별 푸시(4.8절의 불변식), AI 대타(좌석이 사람→AI로 바뀐 시점을 기록하는 저장 형식 v3가 필요 — 지금의 불러오기는 AI 좌석의 모든 step을 agent로 재생성해 대조하므로 도중에 주인이 바뀐 좌석을 재생할 수 없다), 관전자(공개 전용 view가 `core/observation.py`에 필요하므로 R5 밖), 공개 터널용 에셋 게이트, 이름의 저장 파일 보존, 행동 POST가 snapshot을 바로 반환.

## 12. 사용자 결정 (2026-09-17 확정)

사용자가 아래 일곱 항목을 전부 "제안" 열대로 확정했다("제안대로 확정하고 슬라이스 1 시작"). 대안 열은 기각한 선택과 그 비용의 기록이다.

| # | 결정 | 확정(제안대로) | 기각한 대안과 비용 |
|---|---|---|---|
| D1 | 좌석 배정 방식 | **방 링크 하나 + claim**(4.4절) | 좌석별 링크 4개: 구현이 조금 작지만 호스트 화면에 모든 좌석의 열쇠가 뜬다 |
| D2 | 접속 수단 | **Tailscale machine sharing**(8.1절) | Cloudflare Tunnel: 친구 설치 없음, 대신 에셋이 공개 URL에 열리고 Quick Tunnel은 SSE 불가 |
| D3 | 되돌리기 | **지금 규칙 그대로**(자기 연속 행동만, 정보 공개·다른 좌석 행동 뒤 불가, 되돌린 행동은 로그에 남음) | 원격에서는 끄기: 실수 복구가 불가능해짐 |
| D4 | 저장 파일에 좌석 이름·토큰 보존 | **안 함**(형식 v2 유지, 불러오면 새 방 링크 하나) | 보존: 같은 링크로 복귀하지만 형식 v3와 "원본 세션이 살아 있을 때의 토큰 중복" 처리가 필요 |
| D5 | loopback 아닌 `--host`를 `--remote` 없이 거부 | **거부**(4.2절) | 허용: 지금 동작 유지, 대신 open API가 망에 노출될 수 있음 |
| D6 | 자동 저장 | **remote에서만 기본 켬, 턴이 넘어갈 때마다**(문서 최대 약 270 KB·35 ms라 비용이 작고 잃는 진행이 한 턴이다) | 라운드 경계만: 쓰기가 판당 100여 회에서 10회로 줄지만 최대 한 라운드(4명의 여러 턴)를 잃는다 |
| D7 | 진행 순서 | **슬라이스 1~4를 먼저**(첫 원격 한 판), 5~6은 그 뒤 | — |

## 13. 기각한 대안

- **P2P·lockstep**: 비공개 정보 경계 불가, 엔진을 브라우저에서 못 돌림(4.1절).
- **WebSocket**: 양방향이 필요 없고 의존성 추가(4.5절).
- **폴링만**: 가장 단순하고 턴제라 쓸 만하지만 1~2초 지연과 presence 부재. fallback으로만 둔다.
- **헤더 토큰 + localStorage**: `EventSource`·`<img>`에 못 붙고 주소창·JS·로그에 토큰이 드러난다(4.3절).
- **클라이언트 IP로 호스트 식별**: 터널 뒤에서는 모든 요청이 loopback에서 온다(4.2절).
- **사전 로비 단계(전원 입장 뒤 호스트가 시작)**: 미claim 좌석의 결정에서 기다리는 것으로 충분하고 상태 기계가 하나 준다(4.4절).
- **계정·비밀번호**: 친구 네 명에게 과하다.
