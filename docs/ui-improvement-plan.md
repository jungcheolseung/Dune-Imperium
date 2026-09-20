# UI 개선 계획

기준일: 2026-09-20

브라우저 플레이 UI(`src/dune_imperium/server/static/`)의 개선 순서를 정리한다.
근거는 2026-09-20 세션의 10개 관점 감사(73 에이전트 → 반박 검증 32건 확정 /
29건 기각)와 같은 세션의 직접 실측이다. 규칙 근거는 [`rules/README.md`](rules/README.md),
마일스톤은 [`implementation-plan.md`](implementation-plan.md)를 따른다.

사용자 결정(2026-09-20):

- 1순위는 **`app.js` 구조 정리**.
- 화면 언어는 **혼용 없이 언어 설정(ko/en)을 따로** 둔다. 고유명사(카드·리더·
  공간 이름)는 영어를 유지하고, **룰북에 명시된 게임 용어**만 한글/영어를 가른다.
  용어는 KR·EN 룰북 대조로 만든 용어집에서만 가져온다.
- 카드 인쇄 텍스트는 **영어를 유지하고 용어 툴팁을 얹는다**(아래 "언어 정책").

## 실측 기준선 (2026-09-20)

`ui-verify` 서버(포트 8765), 시스템 Chrome, base 및 Immortality 판.

| 항목 | 1600×1000 | 1440×900 |
| --- | --- | --- |
| `#board` 폭 / 보드 스캔 축소 | 576px / **10.4배** | 470px / **12.8배** |
| `#action-log` 폭 | 529px (34%) | 475px |
| `#seats` 내용 대 칸 | 1082px / 752px → **넘침** | 933px / 652px → **넘침** |
| `#market` 내용 대 칸 (base) | 912px / 752px → **넘침** | 맞음 |
| `#market` 내용 대 칸 (전 확장) | **1630px / 751px (2.2배)** | 1630px / 519px |
| Bene Tleilax board | **167×119px, 33.3배 축소** | 화면 밖 |

- 전 확장에서 공용 카드 17장 중 **10장이 화면 밖**이고, 합법 목표를 화면 안으로
  스크롤해 주는 코드는 없다.
- Bene Tleilax board의 연구 칸은 19×21px, 좌석 토큰은 9.7px다.
- 좌석 패널은 어느 해상도에서도 4장이 다 들어가지 않는다(네 번째가 항상 밖).
- 좌석당 view 필드는 **67개**다. 데이터가 없는 게 아니라 고르지 않은 것이다.

## 계획을 바꾼 발견 3가지

### 1. 언어 문제는 문구가 아니라 아키텍처다

`ICON_RULES`(`static/render.js:51`)는 **영어 정규식 29개**를 렌더된 산문에 돌린다
(`solari`, `Draw N cards`, `troops`, `Persuasion`, `Trash`, `Discard`,
`Signet Ring` …). 결과가 둘이다.

- `trash → 폐기`, `draw → 뽑기`로 바꾸는 순간 전부 매칭 실패 → **아이콘이 통째로
  사라진다.** 언어 설정의 실질적 장벽이다.
- 규칙 27번 `/\bSignet Ring\b/`가 *카드 이름*에 발동해 로그가
  `배치 — [아이콘], Arrakeen`으로 렌더된다(아이콘에 `alt`는 있으므로 텍스트가
  사라지는 것은 아니지만, 카드 이름 자리에 그림이 온다).

**용어집과 아이콘 레이어는 같은 작업이다.**

### 2. 번역 질량은 결정 prompt가 아니라 카드 텍스트에 있다

기본 룰셋 카탈로그만으로 **549개 문자열 / 30,394자, 한글 0**이다(카드 능력 396 ·
Conflict 보상 54 · Contract condition/reward 56 · Leader ability/signet 38 ·
notes 5). 감사에서 세 관점이 "가장 많이 읽는 문자열"로 지목한 결정 prompt
(약 50개, `rules/*.py`의 `prompt=` 55개 자리 중 리터럴 36 · 동적 13)는 그중
**5%**뿐이다.

그런데 이 텍스트는 `SourceDocument.CARD_FACE` **전사물**이고 감사 문서가 지킨다.
그래서 "언어 설정"은 단일 정책이 될 수 없고 아래처럼 갈라야 한다.

### 3. "구조" 문제의 체감 증상은 스크롤이다

`SCROLL_PANES`(`static/render.js:212`)는
`["seats", "side-main", "board", "market", "private-zone"]`으로 **`side`가 없다.**
그런데 `style.css:1127`의 `@media (max-width: 1700px)`가 `#side`를 스크롤러로
만들고(`overflow-y: auto`) `#side-main`을 `overflow: visible`로 바꾼다.

**1700px 미만 모든 화면에서 다른 좌석이 한 수 둘 때마다 사이드 칼럼이 맨 위로
점프한다.** [`multiplayer-design.md`](multiplayer-design.md)가 약속한 G7 위반이고,
`scripts/e2e/open_mode.py:282`의 검사는 자기 뷰포트가 넓어서 공허하게 통과한다.

## 언어 정책 (사용자 결정 2026-09-20)

| 대상 | 정책 |
| --- | --- |
| UI 크롬(버튼·패널 제목·상태 문구) | 언어 설정을 따른다 |
| 결정 prompt, 행동 로그 라벨 | 언어 설정을 따른다 |
| 카드·리더·공간·Conflict·Contract **이름** | **영어 고정**(정식 한글 번역본 대조 전) |
| 카드/Conflict/Contract/Leader **인쇄 텍스트** | **영어 고정 + 용어 툴팁** |
| 룰북에 명시된 게임 용어 | 용어집이 정하는 ko/en |

카드 인쇄 텍스트를 번역하지 않는 이유:

1. `SourceDocument.CARD_FACE` 전사물이라 번역하면 전사 원칙과 감사 문서가 깨진다.
2. 사용자가 가진 물리 카드와 화면이 어긋난다.
3. **한글 카드 이미지를 확보하면 그림은 코드 변경 없이 한글화된다** —
   `display/images.py:40`이 이미 `DEFAULT_LANGUAGES = ("ko", "en")`로 한글 스캔을
   먼저 찾고 영어로 폴백한다. 지금 카탈로그 URL이 `/card-images/en/...`인 것은
   한글 스캔이 없기 때문이지 코드가 영어에 묶여서가 아니다.

용어는 **발명하지 않는다.** [`lessons.md`](lessons.md)에 trash/discard를 넘겨짚어
생긴 실제 버그가 기록돼 있다. KR 룰북이 실제로 쓰는 단어만 쓴다.

## 0단계 — 발견된 결함 3건 (2026-09-20 완료)

| | 내용 | 위치 |
| --- | --- | --- |
| a | Tech Module만 켜고 게임 생성 시 **HTTP 500 `Internal Server Error`**. `RulesetConfig.__post_init__`의 `ValueError`가 `_http_errors`를 통과한다 → `ValueError → 400`으로 잡고 메시지를 실어 보낸다 | `server/app.py`의 `_http_errors` |
| b | 내부 frame 식별자 노출(`· frame: turn`) 제거 | `static/render.js`의 `renderBanner` |
| c | 로그의 복수형 id 목록이 raw로 샌다(`Leader Ids: staban_tuek,…`). `logEventPayload`가 단수 id 키만 처리한다 | `static/panels.js:370`의 `logEventPayload` |

(c)는 Leader draft가 기본값이라 **모든 게임의 첫 로그 줄**에 나온다.

검증: `scripts/e2e/`의 `open_mode.py`·`staged_turn.py`·`spectate.py` 재실행.
(a)는 `tests/server/`에 회귀 테스트를 더한다(pytest로 잡히는 유일한 항목).

**완료** (`e119e46`, `9ad978f`). (a)는 `SessionError`가 이미 `ValueError`
하위 클래스라 핸들러를 넓히면 진짜 버그까지 400으로 가려지므로 config를 만드는
자리에서 변환했다. (c)는 계획보다 넓었다 — 감사는 복수형 `_ids`만 지목했으나
엔진의 payload id 키는 약 35종인데 허용 목록에 5종뿐이어서 `leader_id`·`tech_id`·
`contract_id`·`skill_id`가 전부 raw로 새고 있었다. `_id`/`_ids` 전체로 일반화하고
`action_id`는 `ACTION_LABELS`를 태운다.

## 1단계 — 구조 정리 (사용자 1순위)

- **1a. 스크롤·포커스 보존을 선언적으로 — 완료** (`5d2adbe`).
  실측으로 메커니즘을 확정했다: 1800px에서는 `#side-main`·`#side-log`가,
  1600·1366px에서는 `#side`가 스크롤러다 — 옛 목록은 1700px 초과에서만 맞았다.
  셋을 다 넣고 `keepScroll()`이 렌더 시점에 각 칸에 묻는다. 로그도 같은 증상이라
  (맨 위로 올려 둔 독자가 다음 렌더에 34,013px 끌려갔다) 끝에 있던 독자만 따라가게
  했다. e2e는 "스타일시트가 스크롤을 허용하는 모든 칸이 `SCROLL_PANES`에 있는가"로
  바꿔 **부류**를 잡고, 옛 클라이언트에 돌려 실제로 실패하는지 확인했다
  (`open_mode.py`의 옛 단언은 `#side-main`을 지목해 1600px에서 공허하게 통과했다).
- **1b. `app.js` 분할 — 완료** (`3485d25`). 섹션 배너를 따라 `core`·`screens`·
  `session`·`review`·`render`·`turn`·`board`·`panels`와 bootstrap만 남은 `app.js`
  아홉 개로 잘랐다(최대 `board.js` 1,271줄). 자르기 전후로 연속·무손실을 검증했고
  비어 있지 않은 5,064줄이 동일하다. 각 파일에 `"use strict"`를 둔다(스크립트 단위다).
  `races.py --ab`가 `**/static/app.js`를 route해 패치하고 있었는데 그 코드가
  `session.js`로 옮겨가 조용히 깨졌다(route handler의 assert는 `goto` 타임아웃으로만
  보인다) — route 대상을 옮기고 A/B가 다시 정직하게 동작함을 확인했다.
  아래는 착수 전 근거다.
  **classic script로 쪼개면 전역 계약이 그대로라 e2e 무변경·위험 0**이다
  (e2e가 `page.evaluate`로 잡는 것: `state` 76회, `applyAction`, `stagedTurn`,
  `playback`, `LIT_SPACES`, `refreshFlight`, `doorbell`). 빌드 도구가 없고
  `/static`은 단순 `StaticFiles` mount라 인프라 비용은 0이다. ES module은
  `window` 시험 표면을 따로 만들어야 하므로 지금은 하지 않는다.
- **1c. 라벨 테이블 통합 — 완료** (`7f333fa`). 일곱 개를 `static/labels.js`로
  바이트 동일하게 옮기고, 완전성 가드가 `app.js`를 지목하는 대신 `static/*.js`를
  훑도록 바꿔 이후 분할에도 꺼지지 않게 했다. 그 과정에서 확인: **엔진 event kind
  207개 중 177개에 한국어 라벨이 없다**(`prettify(kind)` 폴백) — 2단계 몫이다.
  아래는 착수 전 근거다. `PHASE_LABELS`(:56)·`FACTION_LABELS`(:67)·
  `ACTION_LABELS`(:76)·`EVENT_LABELS`(:308)·`EFFECT_ICON_LABELS`(:644)·
  `RESEARCH_BONUS_LABELS`(:4481)·`TLEILAXU_TRACK_LABELS`(:4495) 일곱 개를 한
  곳으로 모은다. 2단계의 토대다.

**하지 않는 것**: 로그 증분 렌더. 실측 80ms/911엔트리인데 함정이 넷이다
(그룹 tail 병합, fresh 부기, undo epoch, 역방향 review seek). 수지가 맞지 않는다.

참고 수치: `app.js`의 문자열 리터럴 1,972개 중 한글 포함 462개이고 그중
**329개(71%)가 한·영 혼용**이다(`"Agent 배치"`, `"카드 획득 (Intrigue)"`,
`"Feyd token 전진"`).

## 2단계 — 언어 (용어집 + 언어 설정)

**진행 상황 (2026-09-20).** 2a·2b 완료, 2c의 완전성 가드 완료, **언어 토글은
착수하지 않았다**(아래 "언어 토글을 미룬 이유").

| | 상태 | 커밋 |
| --- | --- | --- |
| 2a 용어집 | 완료 — 117행, 확장 포함 | `f8cbfe4`, `227f853` |
| 2b 아이콘 레이어 → 용어 토큰 | 완료 | `a137f5e` |
| 2b' 라벨의 한·영 혼용 제거 | 완료 — 혼용 195행 → 0 | `dafbf6c` |
| 2c 완전성 가드 | 완료 — action id·event kind·용어 3중 | `a137f5e`, `c7574f5` |
| 2c 언어 토글(ko/en) | **미착수** | — |

실측으로 확인한 성과:

- 로그에서 영어로 나오던 event 줄이 **전 확장 3판 3,572줄 중 1,438줄(40%) → 0줄**.
- 라벨 테이블의 한·영 혼용 **195행 → 0행**. 남은 영어 32행은 전부 카드·공간·
  Leader 능력 이름이고 정책상 영어다(카탈로그와 대조해 확인).
- `배치 — , Arrakeen`처럼 카드 이름이 아이콘에 먹히던 버그 소멸. 한 판에서 3회
  나던 것으로, 옛 클라이언트에 새 e2e 단언을 돌려 실패를 확인했다.

### 언어 토글을 미룬 이유

토글 자체는 `TERM_LANGUAGE` 한 줄이지만, **바꿀 영어가 없다.** 실측:

| 대상 | 수 |
| --- | --- |
| 라벨 테이블 행(용어 기반, 이미 ko/en 가능) | 292 |
| 라벨 테이블 **밖**에 하드코딩된 한국어 문자열 | ~261 |
| `index.html`의 한국어 텍스트 노드 | 39 |

즉 진짜 영어 UI는 **약 600개 문자열**을 영어로 뽑아내야 하고, 그중 300개는
테이블이 아니라 코드 안에 박혀 있어 추출 기구부터 필요하다. 지금 토글을 노출하면
용어 몇 개만 바뀌고 나머지는 한국어로 남는 **반대 방향의 혼용**이 된다.

그래서 토글은 별도 결정 사항으로 남긴다. 토대(용어 테이블·`phrase()`·
`phraseText()`·`TERM_LANGUAGE`)는 이미 있으므로 착수하면 기계적인 작업이다.

### 착수 전 근거

- **2a. 용어집.** 공식 KR 룰북 4종이 Dire Wolf 리소스 페이지에 있고 로컬
  `assets/rulebooks/`에도 있다. KR·EN Uprising 룰북은 **둘 다 20쪽이고 페이지가
  정렬돼 있어** 항목마다 `[Main p. N]`을 양쪽으로 인용할 수 있다. 앵커는
  **EN p.20 용어집 페이지**(프로젝트가 이미 `용어집 [Main p. 20]`으로 인용 중).
  산출물은 `docs/rules/glossary-ko.md`와 `scripts/official-rule-sources.json`의
  KR 항목 추가다. **KR FAQ는 존재하지 않는다**(영어만).

  공식 KR URL과 로컬 사본의 SHA-256:

  | 문서 | SHA-256 |
  | --- | --- |
  | `KR_DUNE_IMPERIUM_UPRISING_Rulebook.pdf` | `b9fe3a4c4f9fd4b40c9573a9dc8242e268db35ef1fff753898087b234957b6b6` |
  | `KR_DUNE_IMPERIUM_UPRISING_Rulebook_Supplements.pdf` | `cd763a87485bbf795f556ed03e84f9191b7d7a10e9aedc6ef7b256717996b774` |
  | `KR_DUNE_IMPERIUM_BLOODLINES_Rulebook.pdf` | `d65509007618c81971e652d45e84fb2b36a2eb7ff38525214daaad03aac0fc21` |
  | `KR_DUNE_IMPERIUM_IMMORTALITY_Rulebook.pdf` | `b02ff637ee480d9e58ffc758f30c6bfc02bbfa88bb5d8491bc328be70d7a737b` |

  URL은 `https://d19y2ttatozxjp.cloudfront.net/pdfs/<파일명>`이고 2026-09-20에
  네 건 모두 응답을 확인했다.

- **2b. 아이콘 레이어를 정규식에서 구조적 토큰으로.** 지금 `iconize()`가 렌더된
  산문에 영어 정규식을 돌린다. 대신 서버나 라벨 계층이
  `{term: "trash", count: 1}` 같은 토큰을 내고, 렌더러가 용어집을 보고
  (아이콘, ko 라벨, en 라벨)로 푼다. 이것이 되면 Signet Ring류 충돌이 사라지고
  언어 전환이 가능해지며 용어집이 단일 진실 공급원이 된다.

- **2c. 언어 설정(ko/en)과 완전성 가드.**
  `tests/server/test_action_labels.py`가 이미 파이썬 소스를 스캔해 "모든
  `action_id`에 한국어 라벨이 있는가"를 강제한다. **그 패턴을 prompt와 용어에
  복제한다** — 테이블이 조용히 썩지 않게 하는 유일한 장치다.

  확인해 둔 것(추측이 아니라 검사함):
  - action codec은 prompt와 무관하다(`grep -rl prompt src/dune_imperium/rl/` 0건).
  - 어떤 테스트도 서버가 내보낸 prompt 문자열을 단언하지 않는다.
  - `tests/server/test_snapshot.py`는 최상위 키만 단언하므로 `decision` 안에
    `prompt_ko` 형제를 더해도 깨지지 않는다.

## 3단계 — 레이아웃 (카드 열 토글과 Bene Tleilax board)

**진행 상황 (2026-09-20).** 3a 카드 열 토글 완료(`6f39e39`). 3b Bene Tleilax
크기와 3c 좌석 패널은 남았다.

- **3a 완료.** 공용 카드 열 여덟 개가 각자의 제목에서 접히고, `c`가 전부
  접었다 편다. 선택은 브라우저에 기억된다. strip을 손으로 만들던 네 자리를
  `stripBox()` 하나로 모았고, 접힘 상태는 DOM이 아니라 Set + localStorage에
  둔다(`#market`은 매 렌더마다 비워지므로 DOM에 두면 남이 한 수 두는 순간
  풀린다).
  **실측한 이득**: 전부 접으면 열이 제 너비를 돌려준다(190px → 170px,
  `#market`의 min-width가 풀리면서). 보드는 그만큼만 커진다(576 → 596px) —
  보드 크기는 센터 그리드가 정하지 지금 이 열들이 정하지 않는다. 처음에
  "보드가 자리를 되찾는다"고 단언했다가 측정해 보고 틀렸음을 확인했다.
- **4단계와 함께 드러난 것**: ≤1100px에서 공용 카드가 보드를 밀어내
  `#board`가 468×0이 되던 결함을 `22b8d69`에서 45% 상한으로 막았다. 그 45%는
  보드를 존재하게 하는 하한이지 숙고한 비율이 아니다 — 3b에서 다시 본다.

- **3a. 공용 카드 열 토글.** Imperium Row · Reserve · Tleilaxu Row를 필요할 때만
  펼친다(단축키 포함). 근거는 위 기준선의 2.2배 넘침이다. 공식 디지털판도
  Imperium Row 접기 단축키를 쓴다.
- **3b. Bene Tleilax board를 strip에서 꺼낸다.** 190px 칼럼의 네 번째 항목이라
  어느 뷰포트에서도 화면 밖이고 33.3배로 줄어 있다. 토글 오버레이로 본 보드급
  크기에 놓는다. 덧붙여 **한글 라벨이 달린 fallback 그리드가 도달 불가능한 죽은
  코드**다 — `renderBeneTleilax`가 `layout.image`가 있으면 `board.js:1093`에서 먼저
  반환하므로 `RESEARCH_BONUS_LABELS`·`TLEILAXU_TRACK_LABELS`가 화면에 오지 않는다.
- **3c. 좌석 패널 curation.** 67개 필드에서 "항상 보이는 줄"과 "펼치면 보이는 줄"을
  가른다. 보드 조각 규약(단색 `SEAT_COLORS`, 인쇄된 자리)은 그대로 둔다.

## 4단계 — e2e 그물 넓히기 (3단계의 전제)

지금 `scripts/e2e/`는 **확장을 켠 판도, 끝난 판도, 두 번째 뷰포트도** 보지 않는다
(`common.py:252`가 단일 뷰포트). `disclosure`·`tleilax`·`contract`·`최종 순위`는
검색 결과가 없다. `app.js`를 고치는 작업의 유일한 회귀 검사이므로 3단계 전에
넓혀야 한다.

곁가지로 확인된 종료 화면 결함 둘(별도 슬라이스 후보):

- 종료 배너가 **승자를 말하지 않는다**(`render.js:338`의 "게임이 끝났습니다."뿐).
- `#disclosure` 패널이 전 확장 종료 판에서 1844px·카드 칩 276개로 사이드 칼럼의
  92%를 차지하고, 같은 화면의 리플레이 검토를 스포일한다. e2e 검사는 0건이다.

## 감사에서 기각된 것 (다시 꺼내지 않기 위해)

61건 중 29건이 반박 검증에서 기각됐다. 되풀이하기 쉬운 것만 적는다.

- **AI "생각 중" 표시**: M14 실전 판은 친구 4명이라 AI 좌석이 없다. 그 대기는
  일어나지 않는다.
- **용어 일괄 통일 스윕**: 위험하다. trash/discard/draw/recruit는 현재 100%
  영어이고, 넘겨짚은 번역이 실제 버그를 만든 기록이 [`lessons.md`](lessons.md)에
  있다. 용어집 없이 손대지 않는다.
- **모바일 레이아웃**: [`multiplayer-design.md`](multiplayer-design.md)가 명시한
  비목표다. 다만 600~900px(친구가 Discord 옆에 반쪽 창으로 띄우는 폭)은 실제
  사례라 3단계에서 함께 본다.
- **창 크기 변경 대응**: 이미 안전하다. 보드 조각이 전부 `.board-stage` 기준
  퍼센트라 resize 리스너가 필요 없다.
- **차례 알림**: 이미 구현돼 있고 설계와 맞는다(탭 제목 + WebAudio 880Hz,
  `isRemote()` 게이트). 평문 HTTP에서 Notification API를 쓰지 않는 것은 설계 결정이다.

## 작업 규약

- 학습이 도는 동안 이 체크아웃의 `src/`를 고치지 않는다(spawn worker와 지연
  import가 작업 트리를 읽는다 — [`lessons.md`](lessons.md) 2026-09-16).
  **UI 작업은 워크트리에서 한다.** 문서와 `scripts/`는 괜찮다.
- `app.js`를 고쳤으면 pytest로는 부족하다. [`scripts/e2e/`](../scripts/e2e/README.md)를
  돌린다(스크래치 Playwright venv + 시스템 Chrome).
- 규칙 동작을 바꾸는 항목은 이 계획에 없다. 이 계획이 규칙 공백에 닿으면
  [`rules/open-questions.md`](rules/open-questions.md)에 먼저 적는다.
