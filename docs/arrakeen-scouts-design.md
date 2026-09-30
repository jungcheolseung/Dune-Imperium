# Arrakeen Scouts 모듈 설계 (M15)

상태: **구현 중** (2026-09-28 작성, 같은 날 착수). 사용자가 12절의 D1~D9를 정하고 시작을 지시했다(2026-09-28: "이제 계획한 거에 따라 아라킨 스카웃 구현해보자"). 사용자 요구는 "아라킨 스카웃을 확장팩이나 모듈처럼 시작 옵션으로 넣는다"(2026-09-28)이다. 이 문서는 그 옵션의 규칙 출처, 엔진·관측·codec·AI·서버·UI 설계, 구현 슬라이스와 사용자 결정 항목을 정한다. 기준선은 master `061df24`(action codec v111, 관측 v21 — 2026-09-28 실행으로 확인)이다. 진행 상태는 10절의 슬라이스 목록에 적는다.

## 1. 목표와 범위

**Arrakeen Scouts**(공식 한국어 "아라킨 스카웃")는 Dire Wolf Game Room(Steam)의 Dune: Imperium 컴패니언 앱이 제공하는 3-4인 모드다. 앱이 게임 시작 때 무작위 일정을 만들고, 라운드마다 "Scout"을 누르면 그 라운드의 **임무(mission)·이벤트·경매·판매(sale)**를 하나씩 공개한다. 게임 시작 때 공개되는 **소위원회(subcommittee)**에는 원로회 자리를 차지할 때 한 번 가입한다. 공식 룰북은 없다. 앱의 데이터가 유일한 출처이며 2026-09-27 설치본에서 전부 추출했다(2절).

**요구.**

- **R1 앱과 같은 게임.** 소위원회·임무·이벤트·경매·판매의 구성과 효과, 그리고 무엇이 언제 어떤 확률로 나오는지가 앱과 같다. 앱이 정하지 않은 지점은 `open-questions.md`의 project convention으로 정하고 테스트로 고정한다(9절).
- **R2 옵션을 끈 게임은 그대로.** `RulesetConfig(arrakeen_scouts=False)`(기본)인 모든 룰셋의 chance 흐름, 합법 행동, action catalog, 관측 벡터의 옛 칸, 기존 체크포인트의 행동은 바이트 단위로 같다. 버전 번호는 올라간다(8절).
- **R3 결정론과 replay.** 일정은 게임 seed의 chance로만 정해지고 replay·저장·되돌리기 재구성에서 똑같이 재생된다.
- **R4 비공개 정보.** 비밀 선택과 봉인 입찰은 공개 전까지 다른 좌석·로그·되돌리기·탐색 AI에 새지 않는다. 원격 모드(M14)의 신뢰 모델을 그대로 지킨다.
- **R5 사람이 할 수 있다.** 웹 UI에서 옵션을 켜고 한 판을 끝까지 할 수 있으며, 공식 한국어 용어로 보인다.
- **R6 AI가 할 수 있다.** random·heuristic·rollout 좌석이 새 결정을 모두 처리하고, 소크가 실패 0으로 완주한다.

**범위 밖.** 3인 플레이(앱은 3인 소위원회 4개; 엔진은 4인 전용이다), Rise of Ix 보드가 필요한 일정 풀(Uprising+Ix, 기본판 풀 넷), 앱 자체의 저장·이어하기·뒤로 가기 동작, Scouts 좌석을 넣은 M10 학습(12절 D6에서 따로 정한다).

## 2. 출처와 권리

- **원자료(로컬 전용, git 밖).** 추출 결과와 분석은 에셋 체크아웃의 `reference/dwgr-arrakeen-scouts/`에 둔다. 에셋 `.gitignore`가 이 폴더를 빼므로 그 기기(Mac mini)에만 있다. 에셋 저장소 이력에는 게임에 쓰이는 에셋만 남긴다(2026-09-28 사용자 결정).
  - 앱: Dire Wolf Game Room macOS, Unity 2022.3.62f2, build-guid `84d64e1237b54105aee1940811cd9e43`, 2026-09-26 설치.
  - 데이터: 정의 데이터 5종(`data/spice_mb/*Definition.json`), 일정 풀 8개(`data/schedules.json`), 13개 언어 문구(`data/loc/`, 공식 한국어 포함), UI 프리팹의 아이콘 트리(`data/beat_prefabs.json`).
  - 분석: 앱의 일정 생성·라운드 진행·경매 판정 코드 분석(`analysis/findings/`), 항목별 해석과 반박 검증(`analysis/verification/`), 한국어 요약(`analysis/report-ko.md`).
  - 도구: 이 저장소의 [`scripts/dwgr/`](../scripts/dwgr/README.md). `extract.py`가 설치된 앱에서 5초 만에 다시 추출한다. 다른 기기에서는 앱을 설치하고 다시 추출한다(분석 결과 `analysis/`는 Mac mini에만 있다).
- **공개 저장소에 넣는 것.** 항목 이름, 수치(비용·보상·라운드·가중치), 효과의 **의역**, 우리 말로 쓴 절차 설명, 그리고 추출 도구(`scripts/dwgr/`, 앱 내용은 담지 않는다). 앱 문구(영·한), 도움말 원문, 추출 결과는 넣지 않는다(`rules/sources.md`의 "옮겨 적지 않고 의역" 원칙과 같다). D7에서 확인한다.
- **규칙 권위의 순서.**
  1. 앱의 영어 문구와 아이콘(sprite 이름)이 항목의 효과를 정한다.
  2. 앱 도움말이 절차를 정한다.
  3. 항목이 부르는 기본 행동(recruit, 배치, Spy, Influence, contract, 획득)의 처리는 여전히 Main·Board Guide·FAQ가 정한다.
  4. 한국어 문구는 **용어**로만 쓴다. `sources.md:84`의 원칙과 같으며, 앱의 한국어에는 오역이 있다(9절).
- **인용 태그**(슬라이스 1에서 `rules/README.md`에 등록): `[Scouts help]`, `[Scouts subcommittee: <이름>]`, `[Scouts mission: …]`, `[Scouts event: …]`, `[Scouts auction: …]`, `[Scouts sale: …]`, `[Scouts schedule]`(일정 생성 절차 — 앱 코드의 동작을 재현한 것이다), 용어는 `[KO app: <loc key>]`.
  - `scripts/official-rule-sources.json`에는 넣지 않는다. PDF 전용 스키마라 `prepare_official_rules.py`가 깨진다.
  - 원본 파일 해시는 추출할 때마다 `data/manifest.json`에 남는다. `sources.md`에는 build-guid와 해시만 적는다.
  - 코드의 출처 표기는 `SourceDocument`에 앱 항목 하나를 더하고, `CARD_FACE`처럼 page 1 관례를 쓴다.
- **정체성과 계열.** 앱의 beatId는 식별자로 쓰지 않는다. Desert Riding과 Urban Surveillance가 같은 id(15.0)를 쓰는 충돌이 있다. 프로젝트의 안정 id(snake_case 이름)를 쓴다(`lessons.md` 2026-09-27).
  - beatId는 **계열(family)** 키로만 옮긴다. 일정 추첨은 한 항목을 뽑으면 같은 계열을 모두 빼므로, 계열이 추첨 결과를 정한다.
  - 이름으로는 계열을 알 수 없다. 예: Desert Riding과 Valued Informants 두 종은 한 계열이다. 셋 중 하나만 나오고, 이 계열은 단일 항목 계열보다 약 3배 자주 뽑힌다. Immortality 풀의 Coordinate With The Emperor는 Elite Sardaukar 계열이다.

## 3. 모드의 구조 (앱 기준, 4인)

| 시점 | 앱이 내놓는 것 | 생성 규칙 |
|---|---|---|
| 게임 시작(1라운드에 공개) | 소위원회 5개 | 비용 등급 0·1·2에서 하나씩 균등 추첨, 나머지 2개는 남은 전체에서 균등 추첨 |
| 2·3라운드 | 임무 3개 | 배치가 70%로 [2,2,3], 30%로 [2,3,3]. 각 자리는 그 라운드에 나올 수 있는 후보 중 균등 추첨. 마지막 임무는 바로 앞 임무와 `missionType`이 달라야 한다. 한 계열(변형 묶음)에서 하나만 |
| 4~7라운드 | 라운드마다 이벤트 1개 | 가중치 `baseWeight × subWeight`로 추첨하고, 라운드 창(`startRound..endRound`)에 맞는 것만 남긴다. 한 계열에서 하나만 |
| 5 또는 6라운드(각 50%) | 중간 경매 | 그 라운드에 맞는 경매 중 균등 추첨. 그 라운드의 이벤트보다 **먼저** 나온다 |
| 8 또는 9라운드(각 50%) | 후반 경매 | 그 라운드(8/9)에 맞는 경매 중 중간 경매 계열을 뺀 균등 추첨. 곧 _Late 판들과 Mercenaries: CHOAM 끔 3개, 켬 4개 |
| 8·9 중 나머지 | 판매 1개 | 풀 전체에서 균등 추첨(CHOAM·라운드 조건 없음) |
| 10라운드 | 없음 | — |

- **CHOAM 필터.**
  - 소위원회·임무·경매: CHOAM을 끄면 "CHOAM 전용"을 뺀다.
  - 이벤트: CHOAM을 켜면 "CHOAM 없을 때 전용"을 빼고, 끄면 "CHOAM 전용"을 뺀다.
- **비밀 선택의 공개.** 이벤트의 비밀 선택 보상은 1 또는 2라운드 뒤, 그 라운드의 Scout 직후(그 라운드 항목보다 먼저) 공개·해결된다.
- **풀.** 앱의 풀은 Uprising과 Uprising+Immortality 둘을 쓴다. Bloodlines는 풀에 영향이 없다. Tech만 쓰는 경우 앱은 Ix 풀이 아니라 Uprising 풀을 쓴다.
- **계열.**
  - 임무: {Desert Riding, Valued Informants 2종}, {Elite Sardaukar 2종}. Immortality 풀에서는 Prison Planet 대신 Coordinate With The Emperor가 들어간다.
  - 이벤트 변형 묶음 6개: 스파이스 획득, 책략 보너스, 영향력 증가, 영향력 축소, Covert Operation, Clear the Market.
  - 경매: 중간·후반 판이 한 계열이다.

| 종류 | Uprising 풀 | +Immortality 풀 |
|---|---|---|
| 소위원회 | 11 (CHOAM 전용 2) | 14 |
| 임무 | 12 | 15 |
| 이벤트 | 27 정의 / 15 계열 | 32 / 20 |
| 경매 | 9 정의 / 5 계열 | 11 / 6 |
| 판매 | 4 | 4 |

**결정 유형별 분류(Uprising 풀).** 설계가 다뤄야 하는 행동의 모양이다. 항목별 효과는 슬라이스 1의 규칙 명세에 의역으로 적는다.

| 유형 | 항목 |
|---|---|
| 차례 순서의 선택형 거래(대가 → 보상, 또는 패스/둘 중 하나) | 이벤트: Private Stock, Market Research, Smoke and Mirrors, Rotating Doors, Water Discipline, Royal Delegation, Guild Negotiation, Covert Assistance, Gift of Water, Share Intelligence, CHOAM Bargain, Moment of Revelation(spice 2로 Reserve의 Prepare the Way를 **손으로** 획득). 판매: Unravel the Future, Imperium Connections, Secrets for Sale |
| 반드시 하나를 잃는 양자택일 | Crackdown, Water for Spice Smugglers, Bene Gesserit Treachery, Funeral Rites |
| 전원 자동 | Political Equilibrium(가장 높은 Faction −1, 동률이면 선택), Mating Season, Clear the Market(CHOAM 판은 계약도 교체) |
| 이번 라운드 규칙 변경 | Unlikely Allies, Market Opening, Eyes on Arrakis, Friends Everywhere |
| 인원 제한 선택 | Rebuild Infrastructure(Shield Wall 토큰이 제거된 상태일 때, 두 명이 각 spice 1을 내고 토큰을 보드에 되돌린다. 한 명만으로 되는지는 OQ) |
| 라운드 시작의 교전 배치 | Mercenaries(입찰한 수만큼 병력을 교전에 배치, 최저 입찰자는 그 병력을 주둔지로 후퇴 가능), 판매 Shadow Warfare(Spy 회수 → 병력·spice, 이 판매로 모집한 병력은 곧바로 분쟁으로) |
| 비밀 선택 | Covert Operation(CHOAM 켬/끔 두 판) |
| 임무: 칸 위 보상 | Imperial Reserve, Desert Riding(Maker Hooks 토큰), CHOAM Research(계약 2), Emperor's Schemes(Intrigue 2) |
| 임무: 관측소 보상 | Valued Informants 2종 |
| 임무: 칸에 세워 둔 병력 | Security Detail, Fedaykin Assistance, Weirding Warfare, Send for Aid |
| 임무: 칸 위 지배 마커 | Prison Planet |
| 임무: 계약 위 보상 | CHOAM Escort |
| 임무 공개 때의 좌석별 참여 결정 | Security Detail, Fedaykin Assistance(spice 1), Weirding Warfare(Solari 2), Send for Aid(주둔 병력), Prison Planet(주둔 병력 1 잃기), CHOAM Escort(둘 중 하나). Immortality: Coordinate With The Emperor, Tleilaxu Offering |
| 봉인 입찰 경매 | Highest Bidder, Spies for Hire, CHOAM Negotiations, Mercenaries(0~3, 전원 지불) |
| 공개 경매(시계 방향 1회 입찰) | Critical Moment(임페리움 덱 위 2/3장. 이미 나온 액수와 같은 액수는 부를 수 없다. 후반 판은 2위도 한 장을 산다) |
| 소위원회 가입 | 원로회 자리를 차지할 때 한 번, 비어 있는 소위원회 하나에 **가입할 수 있다**(선택). 거절하면 그 기회는 사라진다(이후 방문에는 없다). 2026-09-30부터는 자리를 차지한 그 turn 안 아무 때나 가입한다(project convention, OQ-076 대안 C) |

Immortality 풀은 이 표의 유형에 표본·연구·Tleilaxu 트랙 보상을 더한다(소위원회 +3, 이벤트 +5, 경매 +1 계열). Offworld Operation은 비밀 선택이다.

임무는 상위집합이 아니다. Prison Planet이 빠지고 3라운드 전용 Coordinate With The Emperor(Sardaukar 칸에 표본)가 그 자리에 들어오며, Sponsored Research·Back Room Deal·Tleilaxu Offering이 더해진다(12 − 1 + 4 = 15). 그래서 `immortality=True`에서는 지배 마커 임무가 나오지 않는다.

## 4. 엔진 설계

### 4.1 옵션

- `RulesetConfig.arrakeen_scouts: bool = False`를 둔다. identifier 접미사 `+scouts`는 **맨 뒤**에 붙인다(`config.py:53-90`의 순서 tuple). 기존 identifier와 체크포인트 이름은 그대로다.
- 다른 옵션과의 관계(D1):
  - `immortality=True`이면 Uprising+Immortality 풀을 쓴다.
  - `choam_module`이 CHOAM 필터를 정한다.
  - `bloodlines`·`tech_module`·`promo_cards`·`leader_draft`는 풀에 영향이 없다.
- 옵션을 꿰어야 하는 곳은 Immortality와 같다.
  - 서버: `server/app.py:172-201`, `sessions.py:357-392,1349-1354`
  - 저장: `persistence.py:231-239,293`
  - CLI: `cli/sweep.py`(identifier substring 파서 포함)
  - 시뮬레이션: `simulation/sweep.py`, `simulation/coverage.py`
  - 평가·학습: `evaluation/tournament.py`, `cli/tournament.py`, `cli/train.py`, `cli/problems.py`, `training/loop.py`
  - PettingZoo: `adapters/pettingzoo_env.py`는 지금 CHOAM·draft만 받으므로 새 kwarg를 더한다.
  - A/B·소크·census 스크립트: `scripts/ab/`(`soak.sh`, `cells.py`, `census.py`, `tip_census.py`)가 확장별 플래그를 가진다.
- `training/expert.py:283-295`의 "전부" 룰셋에 Scouts를 넣을지는 D6에서 정한다.

### 4.2 콘텐츠

- 새 패키지 `content/arrakeen_scouts/`에 소위원회·임무·이벤트·경매·판매의 typed 정의를 둔다.
  - 필드: 안정 id, 이름, 계열(앱 beatId를 묶음 키로만), 풀 소속, 등급 또는 `missionType`, 라운드 창, CHOAM 플래그, 가중치, 비용·보상 효과(기존 effect DSL로 쓸 수 있는 것은 DSL로), 출처 표기.
  - 감사는 계열 소속도 beatId와 대조한다.
- 수치는 추출한 정의 JSON(`scripts/dwgr/extract.py`의 출력)과 **기계 대조**하는 감사 스크립트로 확인한다.
  - 추출 폴더가 없는 기기에서는 skip한다(`test_images.py`의 에셋 대조와 같은 방식).
  - 아이콘만 있는 항목(예: Shadow Warfare)은 sprite 이름과 화살표 좌우 배치로 정하고 감사 문서에 근거를 남긴다(`lessons.md` 2026-09-19, 2026-09-26).

### 4.3 일정: 라운드마다 추첨 (D2)

앱은 게임 시작 때 일정 전체를 만든다. 엔진은 **공개되는 그 라운드에 chance frame으로 뽑는다.**

- **분포가 같다.** 앱의 각 추첨은 앞선 추첨 결과(계열 제거, 앞 임무의 `missionType`, 중간 경매 계열)에만 의존하고 게임 상태와 무관하다. 그래서 같은 조건부 추첨을 공개 시점으로 미뤄도 분포가 정확히 같다.
  - 앱의 이벤트 추첨은 "가중 추첨 후 라운드 창이 안 맞으면 다시"이고, 이는 "그 라운드에 맞는 후보만의 가중 추첨"과 같다.
  - 중간 경매의 5/6라운드 50%, 후반 경매의 8/9라운드 50%, 임무 배치의 70/30도 공개 시점의 chance로 그대로 재현된다.
- **숨은 미래 상태가 없다.**
  - `GameState`에 미공개 일정이 없으므로 다음이 필요 없다: `PlayerView`·`known_card_seats`의 숨김, `determinize`의 재추첨, 비공개 scramble, 서버 dry run의 미리보기 누출(`sessions.py:1890-1935`).
  - 탐색 AI는 자기 resolver로 미래를 새로 뽑는다.
- **가중치는 추첨표로 표현한다.** `ChanceDecision`은 서로 다른 선택지의 균등 추첨이다(`core/decisions.py:22-48`). 가중치에 정수가 되는 배수를 곱해 추첨표로 만든다(Uprising·Immortality 풀은 × 10). 예: 영향력 계열의 변형 0.6 → 표 6장, 단일 이벤트 1.0 → 10장, 두 변형 계열 0.5 → 5장. 선택지는 `"<이벤트 id>#<n>"`이다. 코어는 바꾸지 않는다. 선택지는 콘텐츠 카탈로그 순서로 만든다(집합 순회 금지, `core/chance.py:85-92`).
- **소위원회 5개도 공개되는 1라운드 시작에 chance로 뽑는다.**
  - 앱은 리더를 고른 **뒤**에 일정을 만든다. setup resolver로 뽑으면 Leader draft(OQ-007)와 Navigation 선택 중에 소위원회가 보인다.
  - 1라운드 시작의 chance는 두 경로에 똑같이 걸린다: draft 경로(`create_draft_initial_state`, draft가 끝난 뒤 `_advance_automatic`으로 1라운드에 들어간다)와 고정 배정 경로(`reset()` 안의 1라운드).
  - setup chance를 쓰지 않으므로, 옵션을 켜든 끄든 setup 추첨 개수와 덱이 같다.
  - 추첨은 chance 넷이다: 등급 0·1·2에서 각 한 번, 나머지 전체에서 2개를 비복원으로.
- **chance 분기.** 새 chance 종류는 `_apply_chance`의 fallback `else` **앞에** 분기를 둔다(`rules/engine.py:769-781`).
- **일정 밖의 chance.** Clear the Market의 CHOAM 판은 앞면 계약 두 장을 뒷면 더미에 섞는다. 이 되섞기도 기록되는 chance frame(자기 FrameKind와 `_apply_chance` 분기)이고, 시장 보충은 그 뒤에 한다. replay 테스트를 둔다.
- **짧아진 게임.** 10 VP나 Conflict 덱 소진으로 끝나면 남은 항목은 나오지 않는다(앱과 같다). 아직 공개되지 않은 비밀 선택 보상은 사라진다(9절 OQ).

### 4.4 라운드 흐름

- `begin_round`(`rules/phases.py`)는 Conflict를 공개하고 CONTROL_DEFENSE를 열거나 곧바로 5장 드로우로 넘어간다(2026-09-29부터 규칙 순서: 공개 → 방어 배치 → 드로우, OQ-072). Scouts 단계는 **CONTROL_DEFENSE 뒤, 첫 TURN 전**에 둔다(D3).
  - 근거 1: 앱 도움말은 "패를 뽑고 Conflict를 공개한 뒤 Scout"이라고 한다.
  - 근거 2: Round Start의 순서는 공개 → 방어 배치 → 드로우다(`[Main p. 8]`, `[Main p. 20]`, `setup-and-game-flow.md` 5절).
- **라운드 안의 순서**(앱과 같다):
  1. 이번 라운드가 기한인 비밀 선택 보상
  2. 소위원회 발표(1라운드) 또는 임무(2~3) 또는 중간 경매 → 이벤트(4~7) 또는 후반 경매/판매(8~9)
  3. 첫 TURN
- **TURN frame 위에 쌓지 않는다.** Scouts frame은 CONTROL_DEFENSE처럼 TURN 없이 선다. TURN 위에 쌓으면 `turn_owner_of`(`rules/frames.py:255-272`)가 First Player를 턴 주인으로 보고 이득을 잘못 귀속한다. 걸리는 곳: Suspensor Suits, "이번 turn에 얻은 spice", Spy 회수 카운터, 동맹 계약 완료, recruit 집계, 서버의 턴 단위.
- **진행 커서로 이어 간다.** CONTROL_DEFENSE 방식(처리기가 자기 frame을 TURN으로 바꿔치기)만으로는 부족하다.
  - Scouts 결정은 기존 하위 frame을 부른다: Spy 배치, 계약 선택, 개인 덱·Intrigue 되섞기 chance, Influence 선택, Navigation.
  - 이들은 끝나면 스스로 pop한다. 돌아갈 곳이 없으면 PLAYER_TURNS에 빈 스택이 남아 교착한다. `_advance_automatic`에는 그 경우의 분기가 없다(`rules/engine.py:934-998`).
  - 해법: 공개 `GameState` 커서를 둔다(이번 라운드에 남은 비밀 보상, 현재 항목, 남은 좌석).
  - `_advance_automatic`에 `scouts_step_is_pending(state)` 분기를 `elif state.decision_stack: break` **앞에** 둔다. PLAYER_TURNS에서 스택이 비었을 때 다음 Scouts frame을 열거나, 끝났으면 First Player의 TURN frame을 연다.
  - CONTROL_DEFENSE(`phases.py:244-251`)와 `_round_opening_frame`(`:307`)이 하드코딩한 `_turn_frame`은 이 분기로 넘긴다.
  - 기존 하위 frame을 부르는 Scouts 선택마다(마지막 좌석 포함) 테스트를 둔다: 단계가 이어지고, 스택이 빈 뒤에야 TURN이 열리며, 그동안 `turn_owner_of`는 None이다.
- **첫 TURN의 카운터.** 첫 TURN을 열 때 `reset_turn_counters(players, first_player)`(`rules/frames.py:208-252`)로 turn 카운터를 전부 다시 찍는다.
  - `begin_round`의 초기화(`phases.py:38-64`)는 그 일부뿐이다. Scouts 단계가 바꿀 수 있는 계약 완료, Spy 회수, Commander recruit, Suspensor 카운터가 빠져 있다.
  - Scouts 단계의 Spy 회수나 계약 완료가 첫 턴에 세지지 않는 테스트를 둔다.
- **1라운드.** 고정 배정 게임의 1라운드 `begin_round`는 `reset()` 안에서 돈다(`rules/engine.py:756-767`).
  - 그래서 Scouts를 켠 게임은 `reset()` 직후 소위원회 추첨 chance가 대기한 상태가 된다.
  - 모든 드라이버(러너, 소크, PettingZoo, self-play, 서버)가 chance 결정을 처리하지만, reset 직후의 chance는 처음이므로 드라이버마다 테스트한다(PettingZoo의 `_MAX_CONSECUTIVE_CHANCE_STEPS = 64` 안).
  - 1라운드에는 플레이어 결정이 생기지 않는다.

### 4.5 결정 유형 → frame 모델

| 유형 | 선례 | 모델 |
|---|---|---|
| 차례 순서의 선택형 거래, 판매, 임무 공개 때의 참여 결정 | Endgame window(`rules/endgame.py:100-247`), Leader draft의 주인 교대 | frame 하나, 주인이 First Player부터 시계 방향으로 바뀐다. 각 좌석의 선택지는 자기 차례에 새로 계산한다. 차례 순서는 OQ-002의 "First Player부터"를 따른다(임무 문구는 "각 플레이어는"이라 순서가 OQ다) |
| 라운드 시작의 분쟁 투입(Mercenaries, Shadow Warfare) | 없음(새 경로) | 턴 밖에서 병력을 분쟁에 넣는다. 병력의 출처, 배치 한도, Combat 참가 자격, Mercenaries 최저 입찰자의 후퇴 결정을 명세하고, 턴 귀속이 없는지 테스트한다 |
| 양자택일 손실 | `rules/unit_loss.py:112-155` | 선택지가 하나면 자동, 없으면 공개 이벤트. 좌석별 frame |
| 전원 자동 효과·규칙 변경 | `resolve_makers`, round 한정 필드 초기화(`phases.py:38-64,94-98`) | 결정 없이 공개 상태만 바꾼다. 규칙 변경은 `GameState` 필드로 두고 다음 `begin_round`에서 지운다 |
| 비밀 선택 | Navigation setup(`rules/navigation.py:38-162`), Kota Odax의 Secret Project | 좌석별 순차 결정. 선택은 `PlayerState`의 좌석 한정 id로 보관(frame context에 두지 않는다). 기한 라운드에는 선택을 공개하는 것만 자동이고, 보상 해결은 차례 순서의 좌석별 결정이다: Spy를 놓을 관측소, 가져올 앞면 계약, 버릴 카드, 영향력 최저 Faction의 동률 선택, Offworld Operation의 Tleilaxu·Helix 조건. 앱처럼 같은 선택끼리 묶어 차례 순서로 처리한다 |
| 봉인 입찰 | 없음(새 유형) | 좌석별 순차 결정(First Player부터). 입찰액은 공개 전까지 숨긴다. 전원이 확정하면 자동 단계에서 공개·순위·지불. 순위는 앱 코드가 정한다(`[Scouts auction]`): 입찰액 내림차순의 공동 순위, 순위가 보상 칸 수 이내이고 입찰액이 0보다 커야 승자, 1위 동점이면 2위 보상 없음, 2위 동점자는 모두 2위 보상, 진 좌석은 지불하지 않음(Mercenaries만 전원 지불) |
| 공개 경매 | Combat Intrigue의 priority 순환(`rules/combat.py:129-250`, `:1771`) | First Player부터 시계 방향으로 한 번씩, 1..(자기 spice) 중 이미 나온 액수와 다른 액수를 부르거나 패스. 1위가 공개 카드 한 장을 손으로, 후반 판은 2위가 남은 것 중 한 장을 산다. 공개한 덱 카드는 `revealed_contract_ids`처럼 공개 존으로 두고 `determinize`·scramble이 제자리에 둔다 |
| 소위원회 가입 | Bloodlines Sardaukar Commander·Tech Module의 방문 효과(`BOARD_ICON_COMMANDER`, `BOARD_ICON_TECH`) | 2026-09-30 대안 C(OQ-076): High Council 칸의 자리 아이콘이 방문의 효과 하나(`BOARD_ICON_SUBCOMMITTEE`)를 더하고, Corrinth City는 그 Reveal turn 동안 기회(`scouts_subcommittee_offers`)를 연다. turn frame에 `choose_subcommittee`·`decline_subcommittee`, 고르면 `scouts_subcommittee` frame. (처음 구현은 Emperor 트랙 Spy 대기열처럼 자리를 얻는 즉시 `_advance_automatic`이 결정을 열었다.) |

- **결정 소유는 여전히 한 좌석.** 엔진은 동시 결정 유형을 만들지 않는다. 앱도 사람이 한 명씩 자기 리더를 눌러 입찰을 확정한다. M14 설계 2절의 "결정은 항상 한 좌석 소유" 전제가 유지된다.
- **입찰 합법성은 자기 자원만 본다.** 앞선 입찰에 의존하면 action mask가 입찰을 누설한다. 범위는 `0..min(가진 자원, 경매 상한)`이다. 상한은 Mercenaries 3이고, 나머지는 앱의 99를 쓰거나 codec 크기를 위해 더 작은 상한을 둔다(D4). 입찰 템플릿의 인자 이름은 `count`로 해서 UI의 스테퍼(`render.js:1005-1012`의 `countFamilies`)를 그대로 쓴다. 공개 경매는 앞선 입찰이 공개이므로 이 제약이 없다.
- **지불은 공개 때 한다.** 확정 때 차감하면 공개 자원이 입찰을 누설한다.

### 4.6 보드 위의 임무 물품

- **칸 위 물품.** `GameState`에 공간별 물품 목록(spice·Solari·계약 id·Intrigue id·Maker Hooks 토큰·지배 마커)을 두고, 관측소별 물품을 따로 둔다.
  - `maker_bonus_spice`는 Maker 칸 전용 불변식이 있어 재사용하지 않는다(`core/state.py:297-307`).
  - 계약·Intrigue 카드가 칸 위에 있으면 카드 census(`simulation/invariants.py:62-263`)와 계약 존 고유성 검사(`state.py:169-194`)가 그 존을 세도록 한다.
  - **칸 위의 뒷면 카드는 비공개다.** CHOAM Research의 계약 두 장은 뒷면이고, Emperor's Schemes의 Intrigue 두 장도 가져가기 전까지는 누구도 모른다고 본다(`information-visibility.md`에 적는다).
    - `known_card_seats`는 등록되지 않은 id를 공개로 보므로, 이 존을 "아무도 모름"으로 등록한다.
    - `determinize`와 `_scramble_hidden_information`에서 계약 bank·Intrigue 덱과 함께 섞고, `disclose_hidden_zones`와 fuzz 존 목록에 넣는다.
- **세워 둔 병력.** `PlayerState`에 공간별 병력 수를 두고 12개 보존 불변식(`core/player.py:300-308`)에 넣는다.
- **방문 시 수령.** `board_icons_for`(`rules/board_effects.py:276-345`)에 Scouts 아이콘 키를 붙인다. 선례는 Bloodlines Commander 아이콘이다(`sardaukar.apply_sardaukar_commander_action`, `rules/sardaukar.py:150-283`).
  - 키는 기존 아이콘과 겹치지 않아야 한다.
  - Reverend Mother의 반복(`rearm_board_icons`, `effects.py:336-347`)에서 제외한다.
- **비전투 칸에서 recruit한 병력의 즉시 배치.** 그 병력만 배치할 수 있는 별도 카운터를 쓴다. OQ-070의 Commander 몫처럼 둔다. 공간의 인쇄 recruit나 garrison +2까지 풀어 주는 `grant_combat_icon`은 쓰지 않는다.
- **계약 위 보상**(CHOAM Escort). 계약 완료 세 경로 모두에서 지급한다: `contract_tiles.receive_contract`, `contracts._complete_contract_without_choices`, `apply_contract_intrigue_trash`.
- **관측소 보상**(Valued Informants). `place_spy`는 호출처가 11곳인 `PlayerState` 함수이고, Conflict 보상의 Spy(`rules/combat.py:818-874`)는 `place_spy`를 거치지 않고 직접 놓는다(`:870-874`).
  - 먼저 그 경로를 `place_spy`로 돌린다.
  - 그다음 `GameState` 단계의 배치 wrapper로 모든 경로를 모아 "그 관측소에 Spy를 놓을 때" 판정을 한곳에서 한다.
  - 회귀 테스트(Conflict 보상 Spy가 Valued Informants 관측소의 물품을 받는다)를 둔다. `spy_post_ids=(*`가 `spy_placement.py`에만 나오는지 보는 grep 가드도 둔다.
- **지배 마커**(Prison Planet). 도움말은 "세 번째 칸을 지배하게 되면 그 마커를 가져다 쓰고 임무는 끝난다(spice 없음)"고 한다.
  - 임무의 마커는 `control_space_ids`에 넣지 않는다. 그 필드는 지배 보너스(`agent_turn.py:1038-1050`), 방어 배치(`phases.py:284-290`), rollout 가치(`rollout_agent.py:93`)가 읽는다.
  - 대신 3개 한도 불변식에 함께 세는 별도 필드에 둔다.
  - "마커를 되가져와 임무를 끝내는" 규칙은 `combat._apply_control`(`combat.py:1547-1568`, 지금은 마커 3개면 조용히 무시한다)에 구현한다.
- **Desert Riding의 Maker Hooks 토큰.** 토큰은 네 개의 Maker Hooks 가운데 하나다(도움말). 그래서 두 가지가 필요하다.
  - Hagga Basin 옆 토큰이 남은 마지막 토큰이면, Sietch Tabr의 Maker Hooks 획득도 그 토큰을 가져간다.
  - 공개 때 네 개가 모두 주인이 있으면 어떻게 할지는 OQ로 정한다.

### 4.7 이번 라운드 규칙 변경

| 규칙 변경 | 읽는 곳 |
|---|---|
| Influence 요구 무시 | `agent_turn.py:262-273`. 턴 한정 플래그는 매 턴 지워지므로 쓰지 않는다 |
| 모든 Faction 칸이 전투 칸 | `space.combat`을 읽는 두 곳(`agent_turn.py:500,510`)을 `space_is_combat(state, space)`로 바꾼다. UI 표시(`server/catalog.py:632`)는 view의 변경자를 본다 |
| 처음 획득되는 The Spice Must Flow의 설득 −2 | 비용을 직접 읽는 다섯 곳 이상(`acquisition.py:282,418,658,694,1348`, `leader_abilities.py:1108`, heuristic 두 곳)을 중앙 `reserve_cost()`로 모은 뒤 할인한다. 한 곳이라도 빠지면 합법성과 지불이 어긋난다 |
| Influence 4 보너스를 아무 Faction 것으로 | `gain_faction_influence`는 동기 함수다(`influence.py:86,383-437`). 선택을 새 대기열로 열고, 대기열을 손으로 넘기는 Combat 보상(`combat.py:257-330`)에도 꿴다 |

### 4.8 비공개 정보

- **숨긴 값의 등록부.** `known_card_seats`(`core/observation.py:228-298`)는 카드 id만 다룬다. 비밀 선택과 봉인 입찰은 좌석 한정 id(예: `scouts_pick:<round>:<seat>`)로 같은 등록부에 넣는다.
- **봉인 frame의 행동 모양.** 봉인 frame은 행동 id를 **하나만** 내고 값은 인자에 싣는다(예: `scouts_secret_pick(option=…)`, `scouts_bid(count=n)`). 선택마다 행동 id를 달리하면 로그의 `action_id`가 그대로 누설한다(`sessions.py:1717-1731`는 `action_id`를 항상 내보낸다).
- **로그 가림.** 지금의 가림은 문자열 인자 중 숨은 카드 id만, 기록할 때 한 번 계산한다(`session_log.hidden_argument_values`, `:121-132`). 그래서 다음을 더한다.
  - `LoggedStep`에 "봉인" 표시를 두고, 공개 단계 전까지 행위자 밖의 좌석에는 인자를 전부 가린다.
  - 봉인 단계에서 나오는 이벤트는 모두 `visible_to=(행위자,)`로 두고 값을 싣지 않는다.
  - `check_event_visibility`(`simulation/invariants.py:308-329`)에 "봉인 frame의 공개 이벤트는 값을 싣지 않는다" 검사를 더한다.
  - 원격 두 브라우저 테스트로 `/games/{id}/log`의 비밀 선택과 입찰을 모두 확인한다.
- **미리보기.** 서버는 합법 행동마다 실제 상태에서 dry run을 돌려 경고를 만든다(`sessions.py:1799-1817`). 그 경고(`shortfall_warning`·`shortfall_details`)는 결과의 **모든** 이벤트를 훑으므로, 마지막 입찰자의 목록이 공개 결과(다른 좌석의 보상, supply 부족)를 입찰액별로 다르게 보여 준다.
  - 봉인 값을 공개하는 결과의 행동에는 미리보기 필드(경고, shortfall, `strength_after`)를 싣지 않거나, 행위자 자신의 이벤트만 쓴다.
  - 상대 입찰만 다른 두 상태에서 마지막 입찰자의 행동 목록이 같음을 테스트한다.
- **되돌리기와 턴 종료(D5: 턴 종료를 따로).** 사람 좌석의 Scouts 결정은 CONTROL_DEFENSE처럼 그 좌석의 단위이며, 서버는 그 좌석이 "턴 종료"를 누를 때까지 다음 좌석으로 넘기지 않는다(`server/turn_end.py`). 누르기 전에는 자기 결정을 되돌릴 수 있다(2026-09-29부터 CONTROL_DEFENSE는 예외다: 방어 결정 뒤 곧바로 카드를 뽑아 숨은 정보가 드러나므로 되돌릴 수 없다).
  - **봉인 입찰은 두 행동이다.** `scouts_bid(count=n)`은 입찰액을 고르기만 하고(다시 고를 수 있다), `confirm_scouts_bid`가 확정한다. 확정 행동을 `EXPLICIT_TURN_ENDS`에 넣어 그것이 곧 그 좌석의 "턴 종료"가 된다(한 번 누르기 원칙). 그래서 확정 전에는 입찰을 바꿀 수 있고, 마지막 좌석의 확정이 처음으로 전원의 입찰을 공개한다. 공개하는 그 단계는 되돌릴 수 없는 공개로 표시한다(`session_log.reveals_hidden_information`). 앞 좌석의 확정은 아무것도 공개하지 않지만, 확정이 곧 턴 종료이므로 누른 뒤에는 되돌리지 않는다. 확정 전에는 입찰액을 몇 번이든 바꾸거나 되돌릴 수 있다(2026-09-28 슬라이스 8에서 이 문장의 앞뒤 모순을 바로잡음).
  - 비밀 선택은 한 행동이다. 마지막 좌석의 선택도 아무것도 공개하지 않으므로(공개는 1~2라운드 뒤) 턴 종료 전까지 되돌릴 수 있다. 기한 라운드의 공개 단계는 되돌릴 수 없다.
  - 거래·판매·임무 참여처럼 공개 결정은 한 행동이고, 턴 종료를 따로 누른다.
- **관측.** 소유자만 `PrivatePlayerView`로 자기 선택·입찰을 본다. 공개 view에는 "누가 이미 확정했는가"만 둔다. 다음을 모두 넣는다:
  - `check_observation_privacy`의 scramble(`invariants.py:371-460`)
  - `test_known_card_seats` fuzz의 존 목록
  - 종료 후 공개(`disclose_hidden_zones`)
- **탐색 AI.** `determinize`(`agents/determinize.py:58-148`)가 상대의 미공개 비밀 선택과 확정된 입찰을 다시 뽑는다. 옵션을 끈 게임에서는 난수를 소비하지 않는다(A/B 대조군의 동일성).
- **요약·초인종.** 누구나 읽는 `decision.prompt`와 SSE payload에 선택·입찰 값을 넣지 않는다(M14 R1).

### 4.9 관측·codec·체크포인트 (D6)

- **Action codec.** Scouts 행동 템플릿은 모두 `_scouts_templates(config)` 한 블록에 두고 옵션 뒤에 가린다(`adapters/action_codec.py:323-324`의 Immortality 선례).
  - 기본 카탈로그에 새는 공용 우주(`AUTOMATIC_BOARD_ICONS`, `_reveal_resource_templates`, `MAX_DEPLOYMENT_COUNT`)를 거치지 않는다.
  - `ACTION_CODEC_VERSION`은 옵션 골격(슬라이스 2)에서 111 → 112로 올린다. `RulesetConfig` 필드가 늘면 `canonical_state_hash`가 모든 상태에서 달라지므로, 옛 저장을 "hash 불일치"가 아니라 깨끗한 버전 오류로 거절하려면 같은 작업 단위에서 올린다.
  - **슬라이스마다 올린다.** 템플릿이 늘어나는 슬라이스는 codec을, 관측 칸이 늘어나는 슬라이스는 관측 버전을 매번 올린다. 저장소의 선례대로 v104 → v111이 며칠 새 올랐다. 관측 digest는 매번 문서화된 절차로 다시 핀한다. 최종 번호는 미리 정하지 않는다. 옵션이 UI에 드러나기 전(슬라이스 9)이라 중간 버전의 저장은 버려져도 된다.
  - 기본 카탈로그 크기(base 4,425 등)는 그대로임을 테스트로 고정한다.
- **관측.** 새 공개·비공개 필드를 `PlayerView`에 더하고, 이름 붙은 세그먼트를 끝에 더한다. `OBSERVATION_VERSION`은 슬라이스 3에서 21 → 22로 시작한다.
  - 새 필드: 소위원회와 가입자, 공개된 항목, 이번 라운드 변경자, 칸·관측소 물품, 세워 둔 병력, 경매 상태, 확정 여부.
  - 좌석별 공개 값은 `PlayerState`에서 온다. `PublicPlayerView` 캐시가 `id(PlayerState)`로 잡히기 때문이다(`observation.py:536-553`).
  - 골든 digest 다섯 개는 문서화된 절차로 다시 핀한다: 새 벡터에서 Scouts 칸을 빼면 옛 벡터와 같음을 확인한다(`tests/adapters/test_observation_encoding.py:218-325`).
  - Scouts 룰셋의 digest를 하나 더한다.
- **FrameKind와 GamePhase.** 새 `FrameKind`는 enum **끝에** 붙인다(관측이 index로 부호화한다, `rules/frames.py:79-82`). `GamePhase`는 더하지 않는다.
- **체크포인트.**
  - 형식 2 체크포인트는 행동 identity·세그먼트 이름으로 이관돼 기존 동작 그대로 쓸 수 있다(새 열은 0).
  - `mlp_slots` 형식 3은 `SLOT_KEYS`가 바뀌면(새 FrameKind) 거부된다(`training/checkpoint.py:222-243`). 같은 슬라이스에 **키 기반 embedding 행 이관**(새 행 0 = 기존 출력 보존)을 넣는다.
  - (옛 상태) 체크포인트는 자기 룰셋 카탈로그로 행동을 해석했다. 그래서 Scouts 게임에 `checkpoint:`·`search:` 좌석을 앉히면 첫 Scouts 행동에서 "action is not present in this codec version"으로 멈췄고, 슬라이스 2부터 서버 `create_game`과 대회 CLI가 그 좌석을 분명한 오류로 거절했다.
  - **2026-09-30 사용자 결정: 허용.** Epic Game Mode 병합(OQ-092)이 "룰셋 재지정" 이관을 들여왔다: `load_checkpoint(ruleset=...)`가 정책 head의 행을 행동 identity로 게임의 카탈로그에 옮기고, 파일이 본 적 없는 템플릿은 0에서 시작한다(`training/torch_policy.py` `load_network_agent(path, config)`). 그래서 거절을 풀었다. Scouts 게임의 좌석은 그 게임의 설정으로 만들어진다(서버 `_build_agents`, 대회 `play_match`의 `make_agent(kind, seed, config)`). Scouts의 숨은 정보(비밀 선택, 봉인 입찰, 뒷면 임무 카드)는 이미 `known_card_seats`에 등록돼 탐색 좌석의 `determinize`가 섞는다(규칙 명세 7·8·11절).
  - **학습하지 않은 템플릿만 있는 결정은 heuristic에게.** 지금까지의 체크포인트는 Scouts 없이 학습됐으므로 Scouts 템플릿의 logit이 모두 0으로 같다. 그러면 argmax는 카탈로그 순서의 첫 행이다. ext-v111/C/iteration_07081을 heuristic 셋과 200판씩 두어 보니(기본 +scouts, CHOAM·Immortality·Bloodlines·Tech +scouts) 좌석의 Scouts 결정 82~91%가 전부 새 템플릿이었고, 선택은 퇴화했다: 봉인 입찰은 언제나 0으로 확정, Critical Moment 호가는 언제나 0, 비밀 선택은 언제나 0번, 임무는 언제나 불참, 소위원회 가입 결정에서는 언제나 거절, 이벤트·판매는 거의 언제나 0번 줄. 그래서 `NetworkAgent`는 **합법 행동이 전부** 파일이 학습하지 않은 행(이관 보고의 `new_action_rows`)인 결정을 에이전트 seed로 만든 `HeuristicAgent`에게 넘긴다. 학습한 행동이 하나라도 섞인 결정은 그대로 네트워크가 고른다(새 템플릿은 logit 0으로 경쟁한다). 탐색 좌석은 그런 결정을 탐색하지 않고 같은 heuristic으로 답하며, playout 안에서는 playout의 chance seed로 만든 heuristic이 모든 좌석의 그런 결정에 답한다(후보들이 같은 답을 만나도록). Scouts 전용이 아니라 codec 이관이나 다른 룰셋 재지정으로 생긴 새 템플릿 전부에 적용된다. 그래서 현재 codec이 아닌 옛 파일은 자기 룰셋에서도 드물게 이 규칙을 탄다: M10의 고정 대조군 5081·5600은 학습하지 않은 행이 43·16개이고, 리뷰(2026-09-30)에서 10판에 2~3번 `take_contract` 결정이 heuristic에게 갔으며 고른 답은 네트워크와 같았다. 대조군을 쓰는 짝 A/B에서는 이 점을 알고 쓴다. 효과(같은 seed 200판씩 짝 비교, 좌석 0 대 heuristic 셋): 우승률 기본 46.0% → 45.5%(−0.5pp [−9.5, +8.5]), 확장 전부 84.5% → 90.5%(+6.0pp [0.0, +12.0]), 평균 순위 −0.06·−0.10; 같은 seed의 heuristic 좌석 0은 22.5%·24.5%. 즉 강도는 비슷하거나 약간 낫고, 좌석이 입찰하고 임무에 참여하고 소위원회에 가입하게 된다.
  - Scouts는 여전히 학습 설정(`train`, `problems`)에 없다. 학습에 넣는 것은 D6대로 따로 정한다.

## 5. AI

- **heuristic.**
  - 새 행동 id마다 `_ACTION_SCORES` 항목을 둔다. 접두사 기본값에 맡기면 `pay_*`를 항상 받고 입찰이 전부 0점 동률이 된다(`heuristic_agent.py:959-971`).
  - 거래·입찰·소위원회·비밀 선택은 view가 필요하므로 `HeuristicAgent.choose_action`의 선행 단계에서 판단한다(graft 전환 선례 `:1064-1074`).
  - "자원 잃기 vs Influence 잃기"는 `_faction_tie`의 손실 경로를 쓴다.
  - 옵션을 끈 게임의 점수는 바이트 그대로 둔다.
  - 방법은 사용자 규칙을 따른다: census 먼저, 레지스트리 고정 대조군과의 짝 A/B, `score_action`에 tie-break를 더하지 않는다.
- **rollout.** `player_value`에 세워 둔 병력(garrison에 준함)과 대기 중인 비밀 보상을 더한다. 옵션을 끄면 0이다. 한 라운드 horizon이라 다음 라운드의 항목은 보지 못한다(수용).
- **무작위·소크.** `RandomAgent`는 그대로 돈다. 소크의 codec 왕복 검사(`simulation/sweep.py:203-236`)를 Scouts로 돌려 범위 누락(입찰 상한 등)을 잡는다.

## 6. 서버·UI

- **옵션.** 게임 만들기 화면에 체크박스를 둔다. **기본은 꺼짐**이다: e2e 스크립트 약 20개가 "모든 확장 켜짐" 폼으로 게임을 만들고 seed를 고정하기 때문이다(`scripts/e2e/common.py:190-212`). 요약 배지와 저장 문서의 ruleset 키도 더한다.
- **카탈로그.** 게임과 무관한 `scouts` 절에 모든 소위원회·임무·이벤트·경매·판매의 비용→보상 표시(영·한)를 둔다(`server/catalog.py`). id는 다른 절과 겹치지 않게 접두사를 붙인다(`test_catalog.py:859-891`).
- **화면.**
  - Scouts 띠: 소위원회 5개와 가입 좌석 색, 이번 라운드 항목, 규칙 변경자.
  - 보드: 칸·관측소 위의 물품과 세워 둔 병력을 그리고, 스캔이 없으면 텍스트 목록으로 보인다(`display/board_layout.py`의 새 좌표 표, `commanderPiece` 선례).
  - 경매: 봉인 입찰은 `{count}` 스테퍼(`render.js:1009-1088`)로, 공개 경매는 매물 카드 띠로 보인다.
  - 비밀 선택: 선택 패널.
- **턴 종료(D5).** "사람 좌석의 모든 턴 끝은 턴 종료 한 번" 규칙을 지킨다. Scouts 결정은 CONTROL_DEFENSE처럼 좌석의 단위다. 공개 결정(수락·패스·참여)은 행동 뒤에 "턴 종료"를 따로 누른다. 봉인 입찰은 입찰액 선택 뒤의 확정 행동이 곧 "턴 종료"다(4.8절).
- **말.**
  - 공식 한국어는 앱의 ko_KR 문구에서 가져온다: 아라킨 스카웃, 소위원회, 임무, 이벤트, 경매, 판매, 남아있는 소위원회 자리.
  - `glossary-ko.md`에 새 출처 종류 `[KO app: <loc key>]`와 절을 더한다.
  - 앱 한국어의 오역(9절)은 영어 뜻을 따르고 차이를 적는다.
  - 규칙 변경자처럼 인쇄된 값(전투 칸 여부, 요구 조건, 카드 비용)을 바꾸는 효과는 view의 변경자를 보고 화면에 반영한다.
- **복기.** 종료 후 공개 패널에 비밀 선택·입찰 내역을 더한다.
- **e2e.** 전용 `scripts/e2e/scouts.py`를 둔다: 옵션을 켠 게임, 띠·보드 물품의 위치, 입찰 스테퍼, 두 브라우저 원격에서 입찰·비밀 선택의 가림, 종료 후 공개. `log_words.py`·`lang.py`에 Scouts 게임을 더한다.

## 7. 문서·출처 작업 (슬라이스 1)

- `docs/rules/arrakeen-scouts.md`(한국어, `rules/immortality.md` 형식): 옵션 이름과 기본값, 4인 전용, 조합 방침, 범위 밖, 구성·setup·라운드 흐름·소위원회·임무·이벤트·경매·판매, 기존 명세와의 관계, 구현 상태.
- `docs/rules/sources.md`: 새 절 "Arrakeen Scouts (Dire Wolf Game Room 컴패니언 앱)". 빌드 고정, 권위 순서, 비공개 원자료 위치, 의역 원칙, 앱 업데이트 때의 재추출 절차를 적는다.
- `docs/rules/source-map.md`: 정의 계열(도움말, 일정, 소위원회, 임무, 이벤트, 경매, 판매)별 표.
- `docs/rules/README.md`: 범위 문장, 문서 목록, 인용 태그.
- `docs/rules/information-visibility.md`: 비밀 선택, 봉인 입찰, 공개 경매 매물의 가시성.
- `docs/rules/glossary-ko.md`: `[KO app]` 출처 종류와 절.
- `docs/rules/open-questions.md`: OQ-071부터(9절). 머리말에 "앱 데이터가 침묵하는 지점"을 더한다.
- `docs/implementation-audits/arrakeen-scouts.md`: 정의별 전사 표(정의 | 구현 | 규칙 민감 메모). 검증 방법은 blind 전사 → 엔진 대조 → 반박 3인 + 정의 JSON·sprite 이름과의 기계 대조(`transcription-audit-2026-09-26.md:7-17`)다.

## 8. 테스트·검증

- **옵션을 끈 동일성.**
  - 기본·기존 룰셋의 setup chance 개수(`tests/unit/rules/test_setup.py:187,231`)와 카탈로그 크기가 그대로다.
  - 골든 관측 digest는 "새 칸을 빼면 같음"으로 다시 핀한다.
  - `test_ruleset_gates.py`에 모든 Scouts provider를 더한다.
- **일정 분포.** 확률은 표본이 아니라 **chance frame의 선택지 다중집합**으로 고정한다. 예:
  - 4라운드 이벤트의 추첨표가 CHOAM 켬에서 총 170장이고(풀 190장에서 라운드 창 밖의 Friends Everywhere·Rebuild Infrastructure 20장 제외), 영향력 증가·축소 계열이 30장씩이다.
  - 로컬 분석 폴더의 확률 스크립트(`analysis/probability/`)가 계산한 한 게임 등장 확률을 작은 열거 테스트로 재현한다. 예: Rebuild Infrastructure 켬 0.0712 / 끔 0.0774, 영향력 증가 계열 0.5681 / 0.5959.
- **규칙 단위.** 항목마다 대표 시나리오를 둔다. 앱이 정하지 않은 판정은 OQ 번호를 docstring에 적는다.
- **비공개.**
  - 봉인 입찰·비밀 선택의 로그 가림과 되돌리기 경계(`tests/server/test_undo.py` 형식)
  - `known_card_seats` fuzz
  - 관측 privacy scramble
  - `determinize` 불변식(`tests/unit/agents/test_rollout_agent.py:193-225`)
- **완주.** Scouts 단독과 CHOAM·Bloodlines·Tech·Immortality·leader draft 교차에서 random·heuristic 소크를 `--soundness-interval 25`로 돌려 실패 0을 확인한다. census에 "나온 항목·가입한 소위원회"를 새 차원으로 더한다.
- **UI.** `scripts/e2e/scouts.py`와 기존 e2e 전체(`run_all.py`)를 묶음 끝에 한 번 돌린다.

## 9. 앱이 정하지 않은 지점 (OQ 후보)

슬라이스 1에서 OQ-071부터 등록하고, 각 슬라이스를 시작하기 전에 사용자 판정을 받는다. 괄호 안은 제안하는 convention이다.

1. 차례 순서 거래·판매의 순서(First Player부터 시계 방향, OQ-002 선례)와 각 좌석이 차례에 본 자원으로 판단하는지(그렇다).
2. Scouts 단계와 Control 방어 배치의 순서(방어 배치 뒤).
3. 봉인 입찰. 순위 규칙은 앱 코드가 정한다(4.5). 남은 것은 동점 승자들의 보상 처리 순서(First Player부터, 앱의 "차례 순서대로")와 입찰 상한(D4)이다.
4. Mercenaries와 Shadow Warfare의 라운드 시작 분쟁 투입: 병력의 출처(supply), Mercenaries 최저 입찰 동점일 때 후퇴(동점자 모두 가능), 입찰 0, 투입할 병력이 모자랄 때(있는 만큼), 턴 밖 투입의 배치 한도.
5. Contingencies의 "다른 에이전트"(방금 원로회에 보낸 Agent가 아닌 자기 Agent).
6. 소위원회 가입 시점: 원로회 칸 방문의 자유 순서 아이콘 묶음(OQ-027) 안에서 가입하는지, 같은 방문에서 얻은 자원으로 비용을 낼 수 있는지. Corrinth City로 자리를 얻어도 가입하는지(앱 문구는 "자리를 차지할 때"). 가입은 선택이다. 비용을 낼 수 있는 빈 소위원회가 없거나 거절하면 기회가 사라진다(Uprising 도움말: 이후 방문에는 가입할 수 없다). → OQ-076: 2026-09-30 사용자 판정으로 자리를 차지한 turn 안 아무 때나(대안 C, project convention).
7. 세워 둔 병력: garrison에서 옮긴 병력을 다시 "recruit"하는 것과 FAQ의 garrison 재모집 금지(`[FAQ p. 4]`)의 관계, 비전투 칸에서의 즉시 배치 한도.
8. 칸 위 물품의 남은 것.
   - Imperial Reserve와 Desert Riding은 도움말이 정한다: 다음 방문자 몫.
   - CHOAM Research와 Emperor's Schemes는 임무 문구의 "방문마다 하나"에서 온다(project convention).
   - Emperor's Schemes의 영어는 의무, 한국어는 선택이다.
9. Desert Riding.
   - 토큰은 네 개의 Maker Hooks 가운데 하나다. 마지막 남은 토큰이면 Sietch Tabr로도 가져갈 수 있다(도움말).
   - 공개 때 네 개가 모두 주인이 있으면 임무 물품이 없다(제안).
   - 이미 Maker Hooks가 있는 좌석은 가져갈 수 없다(제안).
   - 같은 방문에서 sandworm 소환이 되는지.
10. Valued Informants: "관측소에 Spy를 놓을 때"가 모든 배치 경로를 포함하는지(포함).
11. Friends Everywhere의 대체 보너스(Emperor Spy 배치 포함), Market Opening의 "처음"이 탁자 전체 기준인지, 획득 비용 상한 계산에도 할인이 드는지.
12. Mating Season에 Bloodlines의 Tuek's Sietch가 포함되는지(앱은 Bloodlines를 모른다).
13. Clear the Market에서 치운 카드의 행방(`imperium_removed`, OQ-051 선례).
14. Rebuild Infrastructure: 한 명의 spice 1로 되돌리는지, 두 명이 모두 내야 하는지. 둘이 필요하면 한 명만 수락했을 때 지불하는지 돌려받는지. 제안: 차례 순서로 먼저 수락한 두 좌석이 각 1을 내야 되돌리고, 한 명뿐이면 지불하지 않는다.
15. 비밀 선택 보상의 기한 전에 게임이 끝나면 소멸한다. "카드 1장을 버리고 병력 3"은 선택형이다. 앱은 비밀 선택 이벤트가 한 게임에 두 번 나오면(Immortality 조합) 묶인 좌석을 빠뜨리는 버그가 있다. 엔진은 따라 하지 않고 모든 보상을 해결한다.
16. 앱 한국어 오역·누락. 영어를 따른다.
   - Investigations의 "1 스파이스"(영어·아이콘은 솔라리 1)
   - Critical Moment의 "같은 액수 금지" 누락
   - 각 플레이어 선택의 "차례 순서대로" 누락
   - Uprising 도움말의 "원로회 재방문 때 가입 불가" 문장 누락
17. Critical Moment.
   - 모두 패스하면 매물은 버린다.
   - 버린 매물의 행방은 `imperium_removed`(13번과 같음).
   - 덱에 2/3장이 없으면 있는 만큼 공개한다.
18. 임무 공개 때 참여 결정의 순서(First Player부터 시계 방향)와 낼 수 없는 좌석(참여 불가).
19. Immortality 풀.
   - Tleilaxu Offering의 "세 번째 칸"을 어떻게 세는지.
   - Offworld Operation 선택 B의 Helix 조건이 무엇인지.
   - Coordinate With The Emperor의 표본 이동.

## 10. 구현 슬라이스

각 슬라이스는 코드와 테스트를 한 커밋에(`Play …`), 문서·감사 갱신을 따로(`Document …`) 낸다.

0. **설계·계획 문서.** 이 문서와 구현 계획 M15. **완료(2026-09-28).**
1. **출처 등록·규칙 명세·콘텐츠 카탈로그.**
   - 7절의 문서 전부와 OQ 등록(사용자 판정 요청).
   - `SourceDocument` 항목.
   - `content/arrakeen_scouts/`의 typed 정의(Uprising·Immortality 풀)와 추출 데이터 대조 감사.
   - 엔진 동작 변경 없음.
   - **완료(2026-09-28).**
2. **옵션 골격.** **완료(2026-09-28).**
   - `RulesetConfig(arrakeen_scouts)`와 `+scouts`, 4.1절의 모든 배선.
   - module-off 불변식, codec v112(템플릿 0개).
   - 옵션을 끈 동일성 테스트, config 왕복 48조합, 저장 키.
   - Scouts 게임의 `checkpoint:`·`search:` 좌석 거절(4.9; 2026-09-30에 풀었다).
3. **일정과 라운드 흐름.**
   - 1라운드 시작의 소위원회 추첨, 라운드별 chance(임무 배치, 임무·이벤트 추첨표, 경매 라운드·계열, 판매), 공개 이벤트. 고정 배정과 draft 두 경로 모두, 각 드라이버의 reset 직후 chance를 테스트한다.
   - Scouts 진행 커서와 `_advance_automatic` 분기(4.4), 첫 TURN의 `reset_turn_counters`.
   - 전원 자동 이벤트(Clear the Market의 계약 되섞기 chance 포함)와 규칙 변경 네 개(4.7). The Spice Must Flow 비용을 중앙 `reserve_cost()`로 모으는 리팩터는 이 슬라이스 안의 별도 커밋으로 먼저 낸다.
   - 관측 v22 세그먼트, FrameKind 추가, slot 행 이관.
   - 이 슬라이스의 미구현 항목은 공개만 하고 `scouts_item_unimplemented` 공개 이벤트를 남긴다. 옵션은 UI에 아직 드러내지 않는다.
   - **3a 완료(2026-09-28)**: 일정·흐름·자동 이벤트·규칙 변경의 설정과 해제·관측 v22·slot 행 이관. **3b 완료(2026-09-28)**: 규칙 변경 네 개를 읽는 곳(`reserve_cost()` 리팩터는 별도 커밋), Friends Everywhere의 선택 frame, codec v113.
4. **소위원회.** 원로회 자리 두 경로의 가입 대기열, 가입 frame, 비용·보상(Uprising 11 + Immortality 3). **완료(2026-09-28)**: 좌석별 줄을 푸는 `scouts_effect` frame(자동 칸은 `effect_interpreter.apply_rewards`, 선택 칸은 이 frame의 `scouts_*` 행동, Spy 배치·선택 trash·Contract는 기존 frame)을 여기서 만들었다. codec v114.
5. **차례 순서 거래·양자택일·판매.** 주인 교대 frame, 양자택일 손실, Political Equilibrium의 동률 선택, Rebuild Infrastructure, 판매 4종, Immortality 거래 이벤트. **완료(2026-09-28)**: 좌석 차례는 Scouts 커서의 과제(`offer:<seat>`)로 이어 가고, 각 좌석의 `scouts_choice` frame이 고른 줄을 `scouts_effect`에 넘긴다. codec v115.
6. **임무.** **6a 완료(2026-09-28)**: 참여, 물품·뒷면 카드, 세워 둔 병력, 방문 수령(9종), Prison Planet의 세 번째 지배, 비공개 처리, 관측 v23, codec v116. **6b 완료(2026-09-28)**: Desert Riding, Valued Informants, CHOAM Escort 완료 보상, Sponsored Research, Back Room Deal, Tleilaxu Offering, codec v117. 계획: 공개 때 좌석별 참여 결정, 칸·관측소 물품(뒷면 카드의 비공개 처리 포함), 세워 둔 병력(12개 불변식), 방문 아이콘, 즉시 배치 카운터, 계약 위 보상의 세 완료 경로, Conflict 보상 Spy 경로 정리, Maker Hooks 토큰, 지배 마커, Immortality 임무 4종.
7. **비밀 선택.** **완료(2026-09-28)**: 선택·공개·해결, 봉인 장치(등록부, 로그 가림, 이벤트 검사, 미리보기 억제, `determinize`와 scramble), 관측 v24, codec v118. 계획: Covert Operation 두 판과 Offworld Operation, 기한 라운드의 공개와 좌석별 해결(묶음은 차례 순서), 종료 후 공개. 첫 숨긴 값이 여기서 생기므로 **봉인 장치 전부**를 이 슬라이스에서 만든다: 숨긴 값 등록부, 로그의 봉인 표시와 가림, 이벤트 가시성 검사, 되돌리기 경계, 미리보기 억제, `determinize`와 scramble.
8. **경매.** **완료(2026-09-28)**: 봉인 입찰(고르기·확정·공개·순위·지불, 봉인 장치 확장), Mercenaries의 전원 지불·투입·최저 입찰자 후퇴, Critical Moment(공개·호가·구매·남은 카드 제거), 관측 v25, codec v119. 계획: 봉인 입찰(확정·공개·순위·지불, 7의 봉인 장치를 입찰로 넓힌다), Mercenaries와 Shadow Warfare의 라운드 시작 분쟁 투입, 공개 경매(Critical Moment의 매물 공개와 시계 방향 입찰).
9. **서버·UI.** **완료(2026-09-28)**: 체크박스(기본 꺼짐)·배지, Scouts 패널, 선택지 설명(한/영), 입찰 스테퍼와 턴 종료 줄, 종료 후 공개, 도움말 한 줄, `scripts/e2e/scouts.py`. 계획: 패널·보드 물품·스테퍼·비밀 선택 패널·복기·도움말과 `scripts/e2e/scouts.py`. 옵션을 UI에 드러낸다(기본 꺼짐). 행동·이벤트 라벨과 한국어 prompt는 여기서 몰아 넣지 않는다: `test_action_labels.py`·`test_i18n.py`가 전체 pytest를 막으므로 3~8의 각 `Play` 슬라이스가 자기 id·event·prompt의 `labels.js`·`labels_en.js`·`prompts_ko.js` 항목을 함께 낸다(CLAUDE.md의 낮은 위험 UI 문구).
10. **AI와 완주.** **완료(2026-09-28)**: heuristic의 입찰(한 번 고르고 확정)·호가(1~3), 교차 소크 실패 0. 학습 배선은 D6대로 하지 않았다. heuristic·rollout 처리, census, 단독·교차 소크 실패 0. 필요하면 짝 A/B. 학습 배선은 D6 결정대로 한다.

**완료 조건.**

- `arrakeen_scouts` 룰셋(단독, CHOAM, Bloodlines·Tech·Immortality·leader draft 교차)의 random·heuristic 소크가 실패 0으로 완주한다.
- 모든 정의가 추출 데이터 대조를 거쳐 감사 문서에 기록된다.
- 일정 분포 테스트가 앱의 확률과 맞는다.
- 비공개 정보 테스트가 통과한다.
- 옵션을 끈 룰셋의 동일성 테스트가 통과한다.
- 앱이 침묵하는 판정은 open-questions에 convention으로 남는다.

## 11. 위험과 대응

| 위험 | 대응 |
|---|---|
| 옵션을 끈 게임이 미세하게 바뀜(chance 순서, 카탈로그, 관측 칸) | setup chance를 쓰지 않고(소위원회도 1라운드 chance), 템플릿은 가린 블록에, 관측은 끝에 붙인다. 동일성 테스트를 슬라이스 2에서 먼저 세운다 |
| 이득의 턴 귀속 오류 | Scouts frame을 TURN 위에 쌓지 않는다(4.4). 턴 카운터를 첫 TURN에서 `reset_turn_counters`로 다시 찍는다 |
| 하위 frame이 끝난 뒤 교착(빈 스택) | Scouts 진행 커서와 `_advance_automatic` 분기(4.4), 하위 frame을 부르는 선택마다 테스트 |
| 라벨·한국어 가드가 중간 슬라이스의 pytest를 막음 | 각 `Play` 슬라이스가 자기 라벨과 prompt를 함께 낸다(10절 9) |
| 봉인 입찰·비밀 선택 누출(행동 id, 로그 인자, 공개 이벤트, 미리보기, 되돌리기, mask, 탐색 AI) | 4.8의 단일 행동 id, 봉인 표시와 가림, 이벤트 검사, 미리보기 억제, 공개 표시, `determinize`. 슬라이스 7에서 한꺼번에. 원격 두 브라우저 e2e |
| 규칙 변경자의 부분 적용(The Spice Must Flow 비용을 여러 곳에서 읽음) | 중앙 `reserve_cost()`로 먼저 모으는 리팩터를 슬라이스 3 안의 별도 커밋으로 둔다 |
| 계약 위 보상의 완료 경로 누락 | 세 경로 모두에 hook, 경로별 테스트 |
| mlp_slots 체크포인트가 새 FrameKind로 거부됨 | 슬라이스 3에서 키 기반 행 이관 |
| 앱 업데이트로 내용이 바뀜 | `scripts/dwgr/extract.py`로 새 폴더에 재추출 → 이전 추출과 `diff -r` → 바뀐 정의는 규칙 변경으로 다룬다 |
| 아이콘만 있는 항목의 오독 | sprite 이름·배치로 정하고, 반박 검증 결과(로컬 `analysis/verification/`)를 감사에 요약한다 |

## 12. 사용자 결정 (2026-09-28 결정)

| # | 결정 | 제안 | 결정 (2026-09-28) |
|---|---|---|---|
| D1 | 풀과 옵션 조합 | 앱과 같게: `immortality`면 Uprising+Immortality 풀, 아니면 Uprising 풀. CHOAM 필터는 `choam_module`. Bloodlines·Tech·프로모·draft는 풀에 무관. 모든 조합 허용 | 제안대로 |
| D2 | 일정 추첨 방식 | 공개되는 라운드에 chance로 추첨(분포 동일, 숨은 미래 상태 없음). 소위원회도 1라운드 시작의 chance(리더 draft 뒤, setup 추첨 무변경) | 제안대로 |
| D3 | 라운드 안 순서 | Round Start(공개·방어 배치·드로우) 뒤, 첫 턴 전. 비밀 보상 → 그 라운드 항목 순(앱과 같음) | 제안대로 |
| D4 | 봉인 입찰 | First Player부터 한 좌석씩 비공개 확정, 전원 확정 뒤 공개. 순위·지불은 앱 코드대로. 입찰 범위는 `0..min(보유, 상한)`. 상한 99 또는 20 | **99(앱과 같음).** 사용자는 나중에 학습에 넣을 계획이다. 입찰 100칸은 학습 룰셋 행동 32,131개의 0.3%이고, 합법 행 learner라 계산은 보유 자원만큼뿐이며, 체크포인트는 행동 이름으로 열을 잇기 때문에 상한을 나중에 바꿔도 된다(2026-09-28 설명) |
| D5 | 사람 좌석의 턴 종료 | 수락·패스·입찰 확정을 명시적 종료 행동으로(되돌리기 불가) | **턴 종료를 따로.** 다음 좌석이 행동하기 전까지 자기 결정을 되돌릴 수 있다. 봉인 입찰은 선택과 확정을 나누고 확정이 곧 턴 종료다(4.8절) |
| D6 | 버전·학습 | codec은 v112부터, 관측은 v22부터 슬라이스마다 올린다. mlp_slots 행 이관. Scouts 게임의 체크포인트·탐색 좌석은 거절. Scouts는 M10 학습 설정에 넣지 않음 | 제안대로. 학습에는 언젠가 넣을 예정이다(그때 따로 정한다). **2026-09-30 변경: 체크포인트·탐색 좌석 허용**(정책 head 재지정; 학습하지 않은 템플릿만 있는 결정은 heuristic이 답한다, 4.9절). 학습 설정에는 여전히 넣지 않음 |
| D7 | 공개 저장소의 서술 범위 | 이름·수치·의역·절차와 추출 도구만 공개 저장소에 | 제안대로 |
| D8 | 9절 OQ의 판정 | 제안 convention으로 등록하고, 각 슬라이스 시작 전에 확인 | **제안대로 구현하고 끝에 한꺼번에 검토.** OQ-071~OQ-089를 `DECIDED`(잠정)로 등록했다(6a에서 OQ-090 추가) |
| D9 | 슬라이스 순서와 착수 시점 | 10절 순서. 착수는 사용자 지시 뒤 | 제안대로. 커밋은 슬라이스마다, **푸시는 사용자가 말할 때만** |

## 13. 기각한 대안

- **게임 시작 때 일정 전체를 미리 뽑아 숨겨 두기**(앱 방식). 분포는 같지만, 숨은 미래 상태가 생겨 `PlayerView`·등록부·scramble·`determinize`·서버 미리보기를 모두 고쳐야 한다. 라운드별 추첨이 더 작고 안전하다.
- **소위원회를 setup resolver로 뽑기.** 덱은 같게 유지되지만 리더 draft·Navigation 선택 중에 소위원회가 보인다(앱은 리더를 고른 뒤 만든다).
- **동시 결정 타입을 코어에 추가.** 한 좌석 소유 전제(M14)와 서버 턴 단위를 전부 흔든다. 순차 비공개 확정으로 같은 게임을 만들 수 있다.
- **새 `GamePhase`로 Scouts 단계 만들기.** 관측이 phase를 index로 부호화하고 여러 곳이 phase tuple을 가진다. CONTROL_DEFENSE처럼 PLAYER_TURNS 안의 독립 frame이면 충분하다.
- **"모든 Faction 칸이 전투 칸"을 보드 표에서 바꾸기.** 정적 불변식(Maker ⇒ Combat)과 UI 캐시 카탈로그가 깨진다. 동적 판정 함수로 둔다.
- **가중 추첨을 위한 새 chance 타입.** 추첨표(가중치 × 10의 중복 선택지)로 기존 균등 chance가 정확히 같은 분포를 낸다.
