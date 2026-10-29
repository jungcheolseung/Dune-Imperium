# 원판 Dune: Imperium과 Rise of Ix 구현 계획

상태: **P0 산출물 끝, 판정 모두 끝** (2026-10-22~25, 브랜치 `claude/base-ix-p0-57d7eb`; 13절). OQ-113 ~ OQ-127과 결정 D1 ~ D5는 모두
사용자가 확정했다. OQ-113은 통일 기준 (C) "비용을 낸 것만 보장", OQ-121은 세 판 공통으로 순위마다 "보상 + 그 좌석의 창"(13.5절). 이 둘의
Uprising 엔진 구현은 codec v154로 병합했고(`e9e992eb`, 2026-10-26), 일반 규칙 감사의 남은 공백은 v155다(`2efb8832`). **P1(판 축)을 2026-10-27에
시작했다**(브랜치 `claude/base-ix-p1-6a418f`, master `b964e08f`에서).
계획의 결정은 2026-10-21에 끝났다. 9절과 10.4절의 결정은 모두 사용자가 내렸다(미룬 것은 9절 7 보드 그림). 숫자는 master `0425224a`(codec v150)와 Steam 앱 4.1.2.1808(build `dad97e20`, 2026-10-21에도 설치된 빌드가 같음)의 로컬
추출에서 셌다.

## 1. 목표와 범위

- **원판**(Dune: Imperium, 2020)을 Uprising과 나란한 두 번째 기본 판으로 4인 게임에서 둔다. 보드·덱·지도자가 다르다.
- **Rise of Ix**(2021)를 원판 위의 확장으로 둔다: Ix 보드와 CHOAM 덮개, Tech 타일 18장, Dreadnought, Shipping 트랙,
  Unload·Infiltrate, 카드·지도자. Epic Game Mode(Ix p. 10)는 이미 Uprising 위에 있고(`epic_game`), 원판 + Ix에서도 쓰게 한다(9절 9).
  원판·Ix 프로모 4장은 `promo_cards` 옵션 뒤에(9절 8).
- **범위 밖:** House Hagal(솔로·2인 자동 상대, 원판 pp. 19–20, Ix pp. 8–9). 이 프로젝트의 대상은 4인 게임이다.
- **마지막 단계:** 원판의 Arrakeen Scouts(P8, 10.4절 3).
- **공식 조합(나중 단계):** Uprising Main p. 18은 Uprising + Rise of Ix(CHOAM 덮개를 반만 펴서 Assembly Hall·Gather Support를
  덮고, Ix·CHOAM 보드에 관측 초소를 하나씩 있는 것으로 친다)와 Uprising + 원판 카드 섞기(Calculated Hire 제외)를 공식으로 허용한다.
  Immortality는 원래 원판의 확장이다. 이 셋은 원판과 Ix가 선 뒤의 작은 단계로 둔다.

## 2. 카드 자료의 출처: 그림 대신 앱 자료

### 2.1 지난 방식과 그 값

Uprising·Bloodlines·Immortality 카드는 DIU JSON(`docs/card-data-sources.md`)으로 시작하고 Dune Cards Hub 카드면 그림을 읽어
전사했다. 전사 자체는 빨랐다(Bloodlines 카드·규칙이 2026-09-07 하루에 모두 play됐다). 비용은 나중에 왔다.

- **2026-09-26 전수 감사:** 348항목을 블라인드로 다시 읽어 **확정 114건**(규칙 80·표시 32)을 고쳤다. 기본판 카드도 틀려 있었다
  (The Spice Must Flow의 Reveal, Covert Operation의 Reveal, Agent 아이콘·소속 여럿). 2026-08부터의 모든 판과 학습이 옛 값으로
  돌았다. 114건에는 그림 오독과 구현 결함이 섞여 있고, 위 예와 Servo-Receivers의 Signet Ring, Hardy가 그림 오독이다.
- **2026-10-06 앱과 전수 대조:** 243항목에서 **확인된 차이 52건**. agent 107개, subagent 토큰 약 2,200만, 2시간 8분. 그 가운데
  상당수는 전사가 아니라 규칙 해석(Agent box의 독립 효과, "up to"의 0 등)이었다.

### 2.2 앱에서 얻는 것 (네 층)

Steam 앱(`com.direwolfdigital.dune`)에는 원판(`BaseSet`) 150개, Rise of Ix(`RiseOfIx`) 85개 정의가 들어 있다. 종류 수가 에셋의
Dune Cards Hub 카드면과 모두 맞고, 장수(`CardCount`)가 룰북의 구성물 수와 맞는다(원판 Imperium 덱 67장·Reserve 24장·House Hagal
31장 `[DI p. 3]`, Ix Imperium 35장·House Hagal 9장 `[Rise of Ix p. 2]`).

| 종류 (종류 수, 장수) | 원판 | Rise of Ix |
| --- | --- | --- |
| Imperium 덱 | 43종 67장 | 29종 35장 |
| 스타터·Reserve | 스타터 7종, Reserve 3종 24장 | Control the Spice(Epic용 스타터) |
| Intrigue | 34종 40장 | 17종 17장 |
| Conflict | 18 | 4 |
| 지도자 | 8 | 6 |
| 보드 칸 | 22 | 4 (Dreadnought, Tech Negotiation, Interstellar Shipping, Smuggling) |
| Tech 타일 | – | 18 |
| House Hagal (범위 밖) | 15 | 6 |

1. **속성 표 (싸고 정확함).** 아키타입 생성자를 표로 뽑는 도구가 이미 있다(로컬 `analysis/card-compare-2026-10-06/extract_app.py`
   → `archetypes.json`). 장수(`CardCount`), 비용, 진영, Agent 아이콘, Reveal 설득력·검, 획득 보너스, 영향력, Conflict 단계·VP, 칸 비용·
   보상, 지배 보너스, Tech 비용이 숫자와 enum으로 나온다. 2026-10-06에 Uprising 카드 110장이 이 표와 모두 같았다(감사 뒤의 값과).
   Ix가 원판에서 빼는 칸도 표에 있다(`RemovedFromSetList`: Hall of Oratory, Rally Troops, Secure Contract, Sell Melange).
2. **영어 문구 (그림 읽기를 대신함).** `loc/en_US.json`에 카드마다 `card.<종류>.<이름>.agent`·`.reveal` 문구가 있고, 아이콘이
   `<sprite name="...">` 태그로 들어 있다. 아이콘을 픽셀로 읽지 않고 이름으로 읽으므로 2.1의 오독이 구조적으로 줄어든다.
3. **능력 클래스 (읽는 값이 큼, 필요한 곳만).** 글로 된 효과는 대부분 카드 전용 클래스이고, 앱에는 그 코드가 기계어(x86-64
   디스어셈블)로만 남아 있다. 카드 하나를 알려면 그 클래스의 메서드 여럿(대상·비용·실행·시점)과 그것이 부르는 공용 helper를 따라
   읽어야 한다. 2026-10-06 대조는 243항목에 subagent 토큰 약 2,200만(항목당 평균 약 9만, agent당 약 20만), 2시간 8분이 들었다.
   영어 문구는 카드당 수십 토큰이다. 그래서 순서·"may/must"·시점을 문구가 정하지 않을 때만 그 클래스를 읽는다.
4. **카드별 화면 조각 (2026-10-23 찾음; 원판·Ix 전사의 중심).** 앱이 카드 앞면을 그리는 UI prefab(`render/prefabs/UI_crd_<종류>_<이름>.prefab.json`,
   `scripts/dwgr/app_assets.py prefabs`로 꺼냄)에 인쇄 배치가 그대로 있다: 칸마다 아이콘 스프라이트 이름(`m_Sprite`), 숫자(`m_text`), 켜고 끈
   요소(`active`), "Choose two:" 같은 글과 화살표. 예: Guild Chief Administrator의 Reveal은 Persuasion "1"과 `UI_Icon_crd_freighter`, Agent box는
   discard → 화살표 → trash; Battle for Arrakeen 2위 보상은 "Choose two:"와 Solari 3·spice 2·Intrigue. 원판·Ix의 Imperium·스타터·Reserve·Intrigue·
   Conflict·Tech에 모두 있고(이름으로 바로 짝이 안 맞는 것은 Imperium 셋 — Duncan Loyal Blade·Jessica of Arrakis·Thumper — 과 Conflict 둘이라 P3에서
   짝을 확인한다), 지도자는 `P_ui_PlayerInformation_*`에 있다. 카드 칸에 쓰인 스프라이트는 264종이다. 2층(문구)이 덮지 못하는 아이콘뿐인 칸
   (13.2 1)을 이것이 카드면 그림 없이 덮는다.

### 2.3 조심할 것

- **규칙 출처가 아니다.** 공식 룰북·FAQ가 먼저이고 앱은 보조 증거다(2026-10-03 사용자 결정). 앱이 공식 문서와 다르면 공식을
  따르고, 공식이 답하지 않으면 OQ로 남기고 "앱 구현"으로 적는다.
- **디지털판은 인쇄판과 다를 수 있다**(에라타 반영, 버그). 카드면 그림은 버리지 않고 **확인용**으로 한 번 본다: 전사가 아니라
  "앱 값과 그림이 같은가"만 보는 일이라 훨씬 가볍다.
- **저장소에 넣지 않는다.** 앱의 문구·정의·추출 결과는 Dire Wolf Digital의 저작물이다. 공개 저장소에는 이름·수치·우리 DSL·
  우리가 만든 표시 문구만 둔다(`scripts/dwgr/README.md`). 예외는 앱 AI의 속성 표(`agents/app_ai/data/archetypes.py`, 2026-10-05
  사용자 결정)이고, 숫자 대조 테스트는 그것을 읽는다(9절 4). 앱 문구를 읽는 대조는 로컬 분석 폴더에서 돈다.
- **스프라이트 이름을 믿지 않는다.** `IntrigueTrash`가 실제로는 훔치기 그림이었다(2026-10-08). 문구에 나오는 스프라이트 이름 →
  우리 아이콘의 대응표를 처음 한 번 픽셀로 확인하고 고정한다.
- **한국어는 공식 한글판에서만 온다.** 앱 번역(2026-10-07 사용자 결정: 공식 한글판과 다르다)과 TTS 한글화 모드(2026-10-21 사용자
  결정: 앱 번역보다 더 비공식이다)는 이름·문구·그림 어디에도 쓰지 않는다. 쓸 수 있는 것은 공식 한국어 룰북(원판·Ix 한국어판이 Dire
  Wolf 공식 리소스에 있다)과 공식 한글판 실물 카드의 사진이다. 사진은 지난번처럼 블로그 리뷰에 올라온 실물 카드 사진에서 찾는다
  (Uprising·Bloodlines·Immortality는 네이버 블로그 리뷰 세 편에서 읽었다, `display/names_ko.py`). 찾는 일은 나중으로 미룬다(9절 6).

### 2.4 카드 한 장의 전사 흐름 (2026-10-23 D1·D2로 고침)

1. 속성 표에서 숫자·아이콘·장수·진영을 생성한다(도구 1; 손으로 쓰지 않는다).
2. 효과는 **앱 자료만으로** 쓴다: 카드별 화면 조각(2.2 4)의 칸·아이콘·숫자와 영어 문구를 읽어 능력 기록(DSL)으로 쓴다. 기록에 없는 모양이면
   hook을 둔다(Uprising과 같은 기준). 카드면 스캔은 새로 읽지 않는다.
3. 스프라이트 이름 → 우리 아이콘 대응(카드 칸의 264종)은 처음 한 번 앱 그림으로 픽셀 확인하고 고정한다(2.3).
4. 기계 대조: 우리 카드 정의 ↔ 앱 AI의 `data/archetypes.py`가 모든 칸에서 같다(pytest, 9절 4; 인쇄와 다른 값은 근거를 단 예외 목록). 우리
   표시 문구 ↔ 앱 문구의 아이콘 순서 대조는 앱 문구가 로컬에만 있으므로 로컬에서 돈다.
5. 디지털판·인쇄판 차이(D2): 화면 조각을 P0의 카드면 블라인드 읽기 181장(에셋 `…/analysis/base-ix-2026-10-22/p0-readings/faces`)과 스크립트로
   **한 번** 대조하고, 다른 카드만 사람(나)이 본다. 필요하면 그 카드만 duneimperiumassets.com 실물 스캔을 본다(내려받기는 그때 그 카드만, 허락을
   받고). 다르면 FAQ 에라타·인쇄판을 따르고 근거를 예외 목록에 적는다.
6. 순서·may/must·시점이 화면 조각과 문구로 정해지지 않을 때만 능력 클래스를 읽는다. 공식 문서가 답하지 않으면 OQ.
7. 한국어 이름·문구는 공식 한글판 카드 사진에서(두 번 읽어 맞추는 기존 방식, `docs/rules/korean-card-style.md`). 사진이 없는 카드는
   한국어 화면에서도 영어 이름·영어 앞면을 보인다(지금과 같은 처리, 9절 6).

## 3. 규칙 출처

- **원판 룰북:** `DUNE_IMPERIUM_Rules_2020_10_26.pdf`(20쪽, sha256 `a689f19e…`)와 한국어판 `KR_Dune_Imperium_Rulebook.pdf`를
  `scripts/official-rule-sources.json`·`docs/rules/sources.md`에 등록한다. 인용 이름은 Uprising의 `Main`과 구분해 `[DI p. N]`.
- **Rise of Ix 룰북:** 이미 등록돼 있고(`[Rise of Ix p. N]`) 지금은 p. 10(Epic)만 쓴다. pp. 3–7, 11–12를 규범으로 넓힌다.
- **원판 Player Aid:** `DUNE_IMPERIUM_Player_Aid_Icons_and_Board_Spaces.pdf`(2쪽, sha256 `b191bffe…`, 아이콘과 보드 칸 설명). Uprising의
  Board Guide 자리다. 함께 등록한다.
- **FAQ 2025-01-13:** 원판·Ix 항목을 새로 읽는다(지금은 Uprising 4인에 적용되는 항목만 반영). 항목 57개 가운데 원판 카드·지도자가 23개,
  Ix가 4개다(카드 이름으로 센 값; 나머지는 일반 규칙). 에라타도 있다: Missionaria Protectiva의 진영(첫 영어판 오인쇄, 2장), Ix 룰북 p. 4
  (Tech 뒤집기는 Agent·Reveal turn 모두 — 첫 영어판은 Agent만). 받아 둔 Ix 룰북 PDF는 이미 고친 문구다. 카드면·앱·룰북이 에라타와
  다르면 에라타를 따른다.
- 새 규칙 명세: `docs/rules/imperium-base.md`(원판), `docs/rules/rise-of-ix.md`. Uprising 명세와 같은 규칙은 다시 쓰지 않고
  "Uprising과 같다 `[DI p. N]`"로 잇는다.

## 4. 엔진: 두 번째 기본 판

[composed-effects-plan.md](composed-effects-plan.md) 5절의 "C단계 — 새 내용"(Rise of Ix·원판 카드를 능력 기록으로 더한다)이 이
계획의 카드 부분이다. 카드보다 큰 일은 보드와 판이다.

### 4.1 지금 모습 (조사, master `0425224a`)

- **옵션:** `RulesetConfig`(`config.py`)는 Uprising 위에 얹는 스위치 묶음이다. 식별자가 `uprising-4p-…`로 고정이고, 체크포인트와
  저장본이 이 식별자로 codec을 다시 만든다. 콘텐츠 등록부는 없다: 함수마다 옵션을 인자로 받고(`imperium_cards_for_choam(...)`),
  카드 항목은 확장마다 불 칸(`choam_only`, `bloodlines_only`, `immortality_only` …)을 가진다. `rules/setup.py`에 옵션 읽기 약 45곳,
  `action_codec.py`에 약 159곳.
- **콘텐츠:** 확장 카드도 모두 `content/uprising/*.py` 안에 있고, 규칙 코드는 `BOARD_SPACES`·`CONFLICTS`·`LEADERS` 같은 모듈 상수를
  import 시점에 읽는다(`uprising.board`를 쓰는 파일이 `src/`에 약 70개, rules·core·adapters에 약 30개).
- **Uprising 전용 체계(rules·core의 줄 수):** Spy 약 1,460줄·40파일, 계약 약 1,200줄·37파일, 모래벌레·Maker Hooks 약 250줄,
  Shield Wall 약 90줄, 전투 아이콘 33줄. 칸 id 글자는 약 125곳(지배 보너스 `agent_turn.py`, Maker 칸 표 `board_effects.py`·
  `core/state.py`, 관측의 `CONTROL_SPACE_IDS`·`MAKER_SPACE_IDS`). 영향력 4칸 보너스가 `rules/influence.py`에 Uprising 값으로 박혀 있다
  (원판은 보드에 인쇄된 다른 보너스, `[DI p. 7]`). `PlayerState`에 Dreadnought 칸은 없다.
- **codec·관측:** 카탈로그는 옵션에서 만들지만 Uprising 전용 행(Sietch Tabr, 모래벌레, Shield Wall, Spy 거절)은 늘 들어간다. 관측은
  옵션과 무관한 한 가지 배치(v33, 5,732 int)로 모든 콘텐츠 id의 합집합이다.
- **도움이 되는 것:** 능력 기록은 Scouts를 빼면 약 430개 중 약 11%만 hook이고 개인 카드는 약 97%가 데이터다. 형식 2 체크포인트는
  행동 행을 이름으로 옮기고, 엔티티 망은 능력 기록에서 특성을 읽는다. Bloodlines Tech Module(Ix와 다른 타일 18장)의 세 더미·획득
  창·할인·뒤집기·획득 효과가 이미 있다. 앱 AI 포팅(`agents/app_ai`)에는 원판·Ix 아키타입 속성(`data/archetypes.py`, 공개 저장소)과
  Ix Tech 기계 일부가 이미 있다. Dreadnought는 어디에도 없다.

### 4.2 판 축의 모양 (추천)

1. **식별자:** `RulesetConfig`에 기본 판 칸(`uprising`·`imperium`)을 더하고 원판은 새 접두사 `imperium-4p-…`. Uprising 식별자는 한
   글자도 바꾸지 않는다(옛 저장본·체크포인트·기보가 그대로). **확장은 판을 가리지 않는다(사용자 결정 2026-10-27, P1 중):** "모든 확장은
   서로 서로 다양한 조합으로 결합될 수 있어야해. 다만 base나 uprising 둘 중 하나는 꼭 있어야 하고". 그래서 설정은 어느 기본 판에든 어느
   확장 조합이든 받는다(확장 안의 부속만 제 확장을 요구한다: Tech Module은 Bloodlines, Go to 11은 Immortality). 처음 추천한 "판마다 허용
   목록"(CHOAM·Bloodlines·Scouts는 Uprising만, Rise of Ix는 원판만)은 버렸다. 콘텐츠가 아직 없는 조합은 엔진이 setup에서 거절한다(원판 보드는
   P2, Ix는 P4, Uprising + Ix는 P7, 원판의 Scouts는 P8 — 10.4절 3).
2. **콘텐츠 조회:** 모듈 상수 import를 판에서 고르는 조회(`content_for(config).board` 같은 꼴)로 바꾼다. 먼저 Uprising 표만 돌려주는
   순수 리팩터로 넣어 같음 관문을 통과시키고, 그 뒤에 `content/imperium/`·`content/rise_of_ix/`를 더한다.
3. **Uprising 전용 체계는 지우지 않는다.** 원판에서는 Spy 아이콘·초소·계약·Maker Hooks가 없어서 그 길에 닿지 않는다. 손볼 곳은
   Uprising 값을 검사하거나 박아 둔 곳뿐이다(Maker 칸 검사, 지배 칸, 영향력 보너스, 늘 들어가는 codec 행). 원판의 Maker 칸 셋에도
   보너스 spice가 쌓이므로(`[DI p. 13]` Phase 4) 그 체계는 판의 칸 목록만 바꿔 쓴다.
4. **codec:** 원판은 자기 카탈로그(새 행 묶음)를 갖는다. Uprising의 행 목록은 그대로여야 한다(받아들일 조건).
5. **관측: 두 판의 합집합 배치 하나(사용자 결정 2026-10-21, 플레이 망은 다시 학습).** 망 하나가 두 판을 다 본다. Uprising 관측이
   바뀌므로 관측 버전이 오른다. 원판·Ix id는 각 segment의 **끝에 붙이거나 새 segment로** 둔다. 그러면 형식 2 체크포인트 옮기기
   (`training/checkpoint.py`: 입력 열을 (segment, offset)으로 옮기고 새 열은 0에서 시작, 0인 열은 출력을 바꾸지 않음)가 지금 망을
   새 배치로 옮겨도 Uprising 판에서 같은 수를 둔다 — P1에서 같은 출력으로 확인한다. 원판에서 두려면 학습이 필요하다.
   **이 조건에는 옛 codec 파일을 어댑터로 두는 탐색 좌석도 든다**(2026-10-22, 이 계획을 띄운 AI 세션과의 약속): 플레이 서버의
   `search:checkpoints/play/readapt-v147-4400.pt`(v147 망을 지금 codec에 맞춰 두는 좌석, 브랜치 `search-adapter` `84e7c547`, 측정 셀 A를
   통과하면 master에 병합 예정)가 관측 배치를 바꾼 뒤에도 Uprising 판에서 같은 수를 둬야 한다. 어댑터가 옛 관측·행동 줄을 새 것으로
   옮기는 곳(`training/older_teacher.py` 계열)이 새 합집합 배치를 알아야 하므로, P1의 관측 변경은 그 어댑터와 함께 고치고 같은 시드의
   판으로 같은 수를 확인한다. 관측 변경을 master에 병합하기 전에 AI 세션과 사용자에게 확인한다(플레이 서버가 그 좌석을 쓴다).
6. **Ix 기계는 보드에 묶지 않는다.** Dreadnought의 지배 칸, Ix 보드, Shipping은 판의 칸 목록을 받게 짜서 7단계의 Uprising + Ix가
   덧붙이기만으로 되게 한다.
7. **이름이 같아도 인쇄가 다르면 다른 id.** 앱 표로 본 예: Heighliner(원판 spice 6 → 병력 5·물 2 / Uprising spice 5 → 병력 5),
   Sietch Tabr(원판 병력 1·물 1 / Uprising 고르기·Shield Wall), Research Station, Hagga Basin, High Council, Swordmaster, 그리고 Conflict
   Battle for Arrakeen·Battle for Imperial Basin·Secure Imperial Basin·Siege of Arrakeen(보상이 다르고 원판엔 전투 아이콘이 없다). 엔진
   표와 엔티티 망의 어휘가 id로 묶여 있어서, 같은 id를 쓰면 두 칸이 한 개체로 합쳐진다. 인쇄가 같은 것(스타터 카드는 Uprising이 원판
   그대로다)은 같은 id를 써서 배운 것을 나눈다. 같은지 다른지는 능력 기록이 같은지로 가리고 테스트로 고정한다.
8. **관측에 판 표시 열.** 카드·칸에 드러나지 않는 규칙 차이(Spy 없음, 영향력 4칸 보너스, 지배 칸, Mentat, 유닛 규칙)는 망이 판을
   알아야 가를 수 있다. 지금 `epic_game` 표시 열 하나가 있는 것처럼 판 표시를 합집합 배치에 둔다.

## 5. 원판이 Uprising과 다른 것 (구현 목록, 명세 단계에서 쪽수로 다시 확인)

- **보드 22칸:** Conspire·Wealth(Emperor), Heighliner·Foldspace(Guild), Selective Breeding·Secrets(Bene Gesserit),
  Hardy Warriors·Stillsuits(Fremen), Hall of Oratory·Rally Troops·Mentat·Swordmaster·High Council(Landsraad), Arrakeen·Carthag·
  Research Station·Sietch Tabr, Imperial Basin·Hagga Basin·The Great Flat, Sell Melange·Secure Contract(CHOAM). 관측 초소·Spy 없음.
- **없는 것:** Spy, 모래벌레·Maker Hooks, Shield Wall, 계약(CHOAM 모듈), 전투 아이콘·Objective 카드.
- **새 것:** Mentat(한 라운드 빌려 쓰는 Agent, `[DI p. 6]`, Calculated Hire·Sort Through the Chaos), 지배 칸이 Arrakeen·Carthag·
  Imperial Basin(`[DI p. 10]`), Reserve 세 더미(Arrakis Liaison, The Spice Must Flow, Foldspace — Foldspace는 칸으로만,
  `[DI pp. 4, 11]`), The Voice(상대별 다음 Agent 배치 봉쇄, 별도 마커/UI 표시 — OQ-116), Kwisatz Haderach류의 Agent 이동.
- **숨은 정보를 새로 다루는 것(앱 문구로 찾은 목록, 명세에서 다시 확인):** Paul Atreides(덱 맨 위를 언제든 본다 — 주인만 아는 카드가
  계속 생긴다), Baron Vladimir Harkonnen(게임 시작에 진영 둘을 비밀로 고르고 나중에 공개), Viscount Hundro Moritani(시작에 Intrigue 맨
  위 둘을 보고 하나를 갖고 하나를 위에 되돌림, Ix), Ilesa Ecaz(라운드 시작에 손의 카드를 따로 두었다가 둘째 turn에 되돌림, Ix),
  Poison Snooper(덱 맨 위를 보고 뽑거나 trash), Tech 더미의 다음 타일, 상대가 고르는 버림(Reverend Mother Mohiam, Test of Humanity).
  모두 `known_card_seats`·관측·되돌리기 경계에 들어가야 한다(lessons 2026-09-24, 10-09).
- **같은 것:** 스타터 덱(Uprising 스타터가 원판 그대로다; 앱도 스타터 7장을 `BaseSet` 하나로 둔다. The Spice Must Flow는 앱에서 원판·
  Uprising 정의가 따로 있다), 진영 넷과 동맹(`[DI p. 7]`), 라운드 흐름, 10점 또는 Conflict 덱
  소진으로 끝(`[DI p. 6]`), Intrigue 세 종류.

## 6. Rise of Ix (원판 위)

- 덮개: Hall of Oratory·Rally Troops·Secure Contract·Sell Melange 대신 Dreadnought·Tech Negotiation·Interstellar Shipping·
  Smuggling(`[Rise of Ix pp. 3, 12]`).
- **Tech 타일 18장**(`[Rise of Ix p. 4]`): 세 더미, Acquire Tech 아이콘만이 얻는 길, 아이콘의 −1·−2 할인(둘을 합치지 못함), 뒤집는
  능력은 라운드에 한 번. Bloodlines Tech Module의 틀(세 더미, 획득 창, 할인, 뒤집기)을 다시 쓴다. Ix에만 있는 것: **협상가** —
  Tech Negotiation 아이콘마다 supply의 병력 하나를 Ix 보드에 놓고, 나중에 Acquire Tech 때 원하는 만큼 돌려받아 하나에 spice 1씩
  깎는다(아이콘 할인과 합칠 수 있다).
- **Shipping 트랙**(`[Rise of Ix p. 5]`): Freighter 아이콘마다 한 칸 전진 또는 맨 아래로 회수. 회수하면 지금 칸과 그 아래 칸의
  보상을 모두, 원하는 순서로 받는다(Acquire Tech 2 할인 / 병력 둘 + 영향력 하나 / Solari 5(상대마다 1) 또는 spice 2). 보상 순서를
  고르고 그 사이에 얻은 spice로 Tech를 사는 흐름이라 "아이콘 하나씩, 순서 자유"인 지금 엔진 모양과 맞는다.
- **Dreadnought**(`[Rise of Ix p. 6]`): 아이콘마다 하나를 garrison으로(좌석당 2대까지), Conflict에서 전투력 3(병력이 없어도 힘이
  0이 되지 않음), 전투가 끝나도 supply로 가지 않고 진 쪽은 garrison으로. Dreadnought가 있던 승자는 Arrakeen·Carthag·Imperial Basin
  가운데 Dreadnought가 없는 칸 하나를 다음 Combat 단계 끝까지 지배한다(지배 표식을 덮음). "유닛"이라는 말이 생기고, 원판 카드의
  "troop"은 Dreadnought에 작용하지 않는다. 배치 규칙도 "이번 turn에 모은 유닛 + garrison에서 둘까지"로 바뀐다.
- **Discard·Unload·Infiltrate**(`[Rise of Ix p. 7]`): Discard 아이콘(손의 카드 하나를 버림), Unload 표시가 있는 Reveal 상자는 그
  카드를 버리거나 trash할 때도 얻는다, 잠입 아이콘은 그 아이콘의 칸에서 남의 Agent를 무시한다(The Voice는 무시 못 함). 새 아이콘과
  칸은 `[Rise of Ix p. 12]`.
- Conflict 덱: Ix 카드 4장을 섞되 덱은 I 1·II 5·III 4장이고 III 하나가 남는다(`[Rise of Ix p. 3]`).

## 7. 화면과 AI

- **화면:** 원판 보드 그림과 칸 좌표(지금은 Uprising `board/map.jpg`뿐; 원판·Ix 보드의 고화질 그림은 TTS 모드 파일에서 찾는다, 나중에, 9절 7), Ix 보드와 CHOAM 덮개, Mentat·Dreadnought·Freighter 말,
  보드 칸 타일은 앱 3D Playmat에서(`app_board.py`).
- **카드 그림은 다른 확장처럼 앱 조각으로 그린다**(2026-10-07 사용자 결정 "앱 그림 우선"). 앱에는 완성된 카드면이 없고 틀 프리팹·
  삽화·아이콘·문구로 그때그때 조립하므로, 지금처럼 `app_cards.py`가 그 조립을 오프라인으로 따라 그린다(`app_leaders.py`는 지도자).
  - 원판·Ix 카드는 앱에 원래 들어 있다. 이번에 앱 그림 색인(`render/index.json`)에서 본 것: Imperium·Reserve·스타터 삽화
    (`UI_ill_KwisatzHaderach`·`UI_ill_TheVoice`·`UI_ill_ShaiHulud`·`UI_ill_ChoamDelegate`·`UI_ill_ArrakisLiaison`·`UI_ill_Foldspace` 등),
    원판 Conflict 보상 그림(`UI_crd_ConflictReward_GrandVision_` 등), Ix Tech 타일 18장(`UI_crd_TechTile_*`), 원판·Ix 지도자의
    `P_ui_PlayerInformation_<지도자>` 프리팹. Bloodlines처럼 앱에 없는 카드를 앱 틀로 새로 짜는 것보다 쉬울 것으로 본다.
  - 확인할 것(P5): 원판·Ix 카드가 Uprising 카드와 같은 틀(`UI_crd_Imperium_Dynamic`)을 쓰는지, 지도자 그림 두 겹을 원판·Ix 지도자에서도
    꺼낼 수 있는지(지금 `render/leaders/`에는 Uprising 지도자만 꺼내 두었다), 렌더가 카드면 스캔과 맞는지(지금까지처럼 나란히 비교).
  - 한국어 앞면은 공식 한글판 사진에서 읽은 이름(`names_ko`)·문구(에셋 `cards/app/ko_text.json`)로 그리고, 사진이 없는 카드는 영어
    앞면을 보인다(9절 6). 앱 그림을 못 쓰는 카드는 에셋에 이미 있는 Dune Cards Hub 스캔으로 대신한다.
  - 새 아이콘(Dreadnought, Freighter, Tech Negotiation, Unload, Infiltration, Discard)과 말(Mentat, Dreadnought, Freighter)도 앱 그림에서
    찾는다(`app_assets.py icons`·`pieces`; 스프라이트는 이름이 아니라 픽셀로 확인).
- **AI:** 앱 AI 포팅(`agents/app_ai`)은 앱의 원판·Ix 아키타입 값(AcquireValue, Rating 등)을 그대로 읽을 수 있어 원판에서 가장 먼저
  쓸 만한 상대가 된다(앱 AI는 공개 저장소에 둔다, 2026-10-05 사용자 결정). 휴리스틱은 새 칸·카드 가중치가 필요하다. 탐색 AI와 학습
  망은 새 판의 codec 행으로 새로 학습한다. 엔티티 망은 능력 기록을 읽으므로 일부 옮겨 배울 수 있는지 실험해 볼 만하다(나중).
- **망이 두 판의 규칙 차이를 가르는 법.**
  - MLP(지금 플레이 서버 망)는 칸·카드를 열 번호와 행동 줄로만 본다. 효과는 입력에 없어서(`docs/entity-network-plan.md` 1절) 판마다
    따로 외워야 하고, 원판 학습에는 맞지 않는다.
  - 엔티티 망(계보, 2026-10-18 사용자 결정)은 칸·카드·지도자·Tech·Conflict를 능력 기록에서 읽은 특성(비용, 아이콘, 보상과 그 수,
    조건, 전투 칸·Maker 칸, 영향력 조건)으로 본다. 이름·id는 특성이 아니다. 그래서 이름이 같아도 인쇄가 다르면 다르게, 인쇄가 비슷하면
    비슷하게 읽고, Uprising에서 배운 것을 원판의 비슷한 카드에 나눠 쓸 수 있다(4.2절 7의 id 분리가 조건). 특성이 놓친 차이는 개체마다
    학습되는 고유 벡터가 메운다.
  - 특성으로 못 읽는 것: hook으로 남은 효과(지금 기록의 약 11%; 원판에서는 Mentat·The Voice·Kwisatz Haderach류가 hook이 될 수
    있다)는 hook 이름 열 하나뿐이라 경험으로 배운다. 카드·칸 밖의 규칙 차이는 판 표시 열(4.2절 8)과 그 판의 학습 판으로 배운다.
  - Spy가 없는 판에서는 Spy 행동이 합법 목록에 아예 나오지 않으므로 망이 고를 일이 없다. 남는 위험은 가치 판단이 Uprising의 Spy 있는
    판에서 배운 값을 섞는 것이고, 판 표시와 원판 학습 판으로 가른다.
  - 탐색 AI는 엔진을 돌려 수를 두어 보므로 규칙은 엔진이 정확히 적용한다. 망은 후보 고르기와 끝 평가만 한다.

## 8. 단계 (초안)

각 엔진 단계는 엔진 하위 단계 관문 전체를 돌린다(CLAUDE.md, 2026-10-20 사용자 결정). Uprising 쪽은 바이트까지 그대로여야 한다.

| 단계 | 내용 | 끝의 모습 |
| --- | --- | --- |
| P0 출처 | 원판 룰북·Player Aid 등록, 원판·Ix 규칙 명세(FAQ 원판·Ix 항목, 디자이너 판정 감사의 남은 몫, 숨은 정보 절, 구성표, 결정 단위·선택지 근거 표 — 10절), 앱 속성 표·문구 추출(로컬), 스프라이트 대응표, OQ-107 기록 정정, 새 OQ 모아 정하기, 시범 전사 5장으로 비용 재기, 시간 줄이는 도구 1~6번 시범(11절) | 명세 두 개, 정한 OQ, 시범 측정, 도구별 채택 여부 |
| P1 판 축 | 엔진에 기본 판(Uprising/원판) 축. Uprising 전용 체계를 그 축 뒤로 | Uprising 같음 확인 200판·기보 2,000 exact, codec 행 그대로, 지금 망과 옛 codec 어댑터 탐색 좌석(`readapt-v147-4400.pt`)이 Uprising 판에서 같은 수(4.2절 5) |
| P2 원판 보드·흐름 | 22칸, Mentat, 지배 셋, Reserve 셋, Conflict 18장, 지도자 8 | 원판 4인 판이 휴리스틱으로 끝까지 돈다(소크) |
| P3 원판 카드 | Imperium 43종·Intrigue 34종, 프로모 3장(`promo_cards`), card-implementer 묶음(첫 묶음에서 시범 전사 5장·갈래 나누기·화면 조각 변환기 시범, D4·D5); 끝에 원판 전부의 앱 행동 대조(10.4절 1) | 앱 속성 표와 기계 대조 0 차이, 행동 대조의 차이 모두 판정 |
| P4 Rise of Ix | 덮개·Tech·Shipping·Dreadnought·Unload·Infiltrate, 카드 30·17·4, 지도자 6, 프로모 1장, 원판+Ix의 Epic; 끝에 Ix 전부의 앱 행동 대조 | 원판+Ix 소크(Epic 포함), 대조 0 차이, 행동 대조의 차이 모두 판정 |
| P5 화면 | 원판·Ix 보드, 말·아이콘, 앱 조각으로 그린 카드·Tech·지도자 앞면(영·한), 선택 화면 | E2E에 원판·Ix 판, 렌더와 스캔 비교 |
| P6 AI | 앱 AI·휴리스틱 확장, 서버 좌석 | 앱 AI 어려움이 원판에서 둠 |
| P7 조합 | Uprising+Ix(Main p. 18), Uprising+원판 카드, 원판+Immortality | 옵션별 소크 |
| P8 원판의 Scouts | Game Room 앱의 원판·Ix 일정 풀(어느 풀인지는 P8에서 정함), 관측 초소 없는 항목의 처리(OQ) | 원판 Scouts 소크, E2E |

크기 비교: Bloodlines(Imperium 32·Intrigue 18·Conflict 2·지도자 9·Tech 18·Skill 14)는 엔진이 이미 있을 때 하루에 전부 play됐다
(화면·휴리스틱·소크는 그 뒤).
P3·P4는 그 두세 배이고, P1·P2(새 보드와 판 축)가 그보다 크고 위험하다. 정식 견적은 P0의 시범 뒤에 낸다(지난 견적은 실제의
절반이었다: 2026-10-06 예상 500만~1,000만 토큰 → 실제 2,200만).

**어림(2026-10-21, 시범 전).** 이 저장소에서 비슷했던 일의 실제 기간(작업한 날 기준)을 잣대로 삼았다: Uprising 엔진·카드·글자 화면
첫 판까지 약 20일(2026-08-12~31), Bloodlines 카드·규칙 하루(09-07), Immortality 하루(09-08), Arrakeen Scouts 추출·설계·구현·검토 사흘
(09-28~30), 효과 조각 A단계 사흘(10-15~17), 정리 단계 이틀(10-17~19), B단계 이틀(10-19~20), UI 7~10단계 나흘(09-24~27).

| 단계 | 어림 | 잣대 |
| --- | --- | --- |
| P0 출처·명세·시범 | 3~5일 | 확장 규칙 명세 한 편이 반나절 안팎. 10절의 점검(FAQ 27항목·디자이너 감사·숨은 정보·구성표)과 OQ 모아 정하기, 11절 도구 시범(하루 안팎)을 더함 |
| P1 판 축 | 3~5일 | B단계·정리 단계(관문 전체 포함). 가장 위험 |
| P2 원판 보드·흐름 | 3~5일 | 새 칸 22·Mentat·지배·지도자 8(지도자는 hook이 많다) |
| P3 원판 카드 | 2~3일 | Bloodlines 하루의 1.5~2배 |
| P4 Rise of Ix | 4~6일 | Bloodlines + Tech Module + Immortality에 Dreadnought(유닛 규칙이 전투·지배·배치를 가로지름) |
| P5 화면 | 4~7일 | UI 7~10단계 나흘, 앱 틀 렌더 묶음 하루씩. 보드 그림 찾기는 따로(미룸) |
| P6 AI | 3~5일 | 앱 AI 포팅 하루(10-05) + 휴리스틱 가중치. 망 학습의 계산 시간은 따로 |
| P7 조합 | 2~4일 | |
| P8 원판의 Scouts | 2~4일 | Scouts 추출·설계·구현·검토 사흘(09-28~30)에서 일정 풀만 새로 |

합치면 작업한 날로 P0~P8이 약 26~44일이고, P3·P4 끝의 앱 행동 대조와 고치기(10.4절 1, 정함)에 하루 이틀을 더해 **약 27~46일**이다.
11절 도구가 P0 시범에서 효과를 보이면 P3~P5가 그만큼 줄지만, 아직 재지 않았으므로 빼지 않았다. 더 늘 수 있는 것: 지난 견적은 실제의 절반쯤이었다. 사용자 판정이 필요한 OQ와 검토 왕복이
있다(Scouts는 검토 세 번). Mac mini에서 ② 학습과 무거운 관문을 차례로 돌리므로 달력 기간은 이보다 길다. 원판용 망 학습(증류 →
강화학습)은 들어 있지 않다(10-21의 첫 사슬은 하룻밤).

**관문 한 바퀴의 기계 시간은 약 30분이다**(2026-10-21 ① Reveal 합계 정리의 기록 `tmp/claude/698323f0/reveal/gates/gates.log`: 같음 확인
200판 check·record·compare 약 3분, 소크 900판 약 3분, 문제집 재채굴 약 5분, E2E 68종 448초 — 08:20~08:39; 그 밖에 pytest `-n 8` 약
2분 반, 기보 2,000판 약 6분). 하위 단계마다 돌려도 단계당 몇 시간이라, 오래 걸리는 것은 관문이 아니라 관문이 찾은 것을 고치는 일과
판정 왕복이다. 다만 ② 학습이 도는 동안에는 관문을 돌리지 않으므로 그만큼 기다린다. 같은 날 뒤의 속도 개선으로 더 짧아졌다: 기보
2,000판 대조 381초 → 184초(작업 프로세스 4)·약 2분(8), 엔진의 판 두기 −16~18%, 앱 AI 판 −6%(worklog 2026-10-21 "반복 작업 속도"·"엔진
속도").

## 9. 결정할 것

1. **범위와 순서 — 정함(2026-10-21 사용자, "추천대로"):** 원판 판을 먼저 세우고 Ix를 그 위에 올린다. Uprising + Ix(와 원판 카드
   섞기, 원판 + Immortality)는 마지막 단계 P7. (고르지 않은 길: Ix를 Uprising 위에 먼저, 원판 카드만 Uprising에 섞기.)
2. **카드 출처 정책 — 정함(2026-10-21 사용자, "추천대로"):** 앱 속성 표·영어 문구를 1차 전사 자료로, 카드면 그림은 확인용으로
   (2.4절). 규칙 근거는 그대로 공식 룰북·FAQ다. `AGENTS.md`의 "Card and image sources"와 `docs/card-data-sources.md`는 P0에서 고친다.
3. **판 축의 모양 — 정함(2026-10-21 사용자):** 4.2절대로(새 식별자 접두사, 콘텐츠 조회 리팩터 먼저, Uprising 전용 체계는 두기, 원판
   codec 따로, Ix 기계는 보드에 묶지 않기) 하되 **관측은 두 판의 합집합 하나**(플레이 망은 다시 학습). 관측 변경이 들어가는 때는
   Mac mini의 ② 재학습 일정과 겹치지 않게 정한다(② 망도 새 배치로 옮기거나 다시 학습해야 한다).
4. **기계 대조를 저장소 테스트로 — 정함(2026-10-21 사용자, "추천대로"):** 앱 AI의 `agents/app_ai/data/archetypes.py`(이미 공개
   저장소)와 카드 정의의 기계 대조를 보통의 pytest로 둔다. 인쇄와 다른 값은 근거(카드면·공식 문서 인용)를 단 예외 목록으로.
5. **House Hagal — 정함(2026-10-21 사용자, "추천대로"):** 범위 밖.
6. **한국어 카드 출처 — 정함(2026-10-21 사용자):** 공식 한글판 실물 카드 사진을 지난번처럼 블로그에서 찾는다(나중에). 한글판 그림이
   없는 카드는 이전처럼 영어판을 보인다. TTS 한글화 모드는 쓰지 않는다(2.3).
7. **보드 그림 출처 — 미룸(2026-10-21 사용자):** 원판 보드·Ix 보드·CHOAM 덮개의 고화질 그림은 TTS 모드 파일에서 찾아본다. 나중에 한다.
8. **원판·Ix 프로모 카드 — 정함(2026-10-21 사용자, "추천대로"):** Duncan Loyal Blade·Jessica of Arrakis·Thumper(원판, P3),
   Boundless Ambition(Ix, P4)을 Uprising 프로모처럼 `promo_cards` 옵션 뒤에 넣는다. 앱 정의와 에셋 카드면이 있다.
9. **원판 + Ix의 Epic Game Mode — 정함(2026-10-21 사용자, "추천대로"):** Ix 룰북 p. 10의 원래 자리다. 지금 Uprising 위의 `epic_game`을
   다시 써서 P4에 넣는다. Hundro Moritani의 셋업 순서(`[Rise of Ix p. 10]`, Uprising 위에서는 범위 밖)도 함께.
10. **기기 — 정함(2026-10-21 사용자):** 앱 자료·관문 자료가 필요한 P0~P4는 Mac mini에서 한다. 앱 추출 결과는 이 기기에만 있고
    추출 도구는 macOS 앱(Mach-O)만 읽으며, 관문 자료(기보 묶음·사람 저장본 등)도 여기 있다. ② 학습과 무거운 관문(전체 pytest·
    같음 확인·기보 대조·소크·E2E)은 겹치지 않게 차례로 돌린다.

## 10. 지난 시행착오를 막는 점검표

Uprising·Bloodlines·Immortality·Epic·Scouts와 효과 조각 엔진 전환에서 겪은 일을 `docs/lessons.md`(사례 61개와 맨 위 "지금 지키는
규칙"), 전사 감사(`implementation-audits/transcription-audit-2026-09-26.md`), worklog에서 모았다(2026-10-21). 원판·Ix에서 다시 생길
자리와, 그 자리에서 손이 가는 절차를 적는다("하지 말라"가 아니라 절차로, lessons 요약 "보고·소통"). 날짜는 lessons의 사례다.

### 10.1 다시 생길 가능성이 큰 열 가지

| # | 지난 일 | 원판·Ix에서 생길 곳 | 막는 법 (단계) |
| --- | --- | --- | --- |
| 1 | 숨은 정보가 되돌리기·창·이벤트로 샜다: 확장 더미가 `known_card_seats`에 없어 되돌리기로 다음 카드를 봄(09-24), 마지막 지도자 고르기에 비공개 배분을 묶음(10-05), 숨은 손패로 창을 엶(10-09) | Paul의 덱 맨 위, Baron의 비밀 진영, Hundro·Ilesa(Ix), Poison Snooper, Tech 더미, 상대가 고르는 버림 | P0 명세에 "숨은 정보" 절: 효과마다 누가 무엇을 언제 아는지. 새 더미·엿보기마다 `known_card_seats`·관측·되돌리기 경계 테스트와 "그 카드가 있든 없든 똑같이 보인다" 테스트(P2·P4) |
| 2 | 유닛 종류마다 세지 않았다: Commander가 troop으로 세여 codec 범위를 넘음, 출처마다 recruit 셈 전수 정정(09-26 감사, OQ-070·105) | Dreadnought(유닛이지 troop이 아님), 원판 카드의 "troop"은 Dreadnought에 안 듦, 배치 규칙이 "유닛"으로 바뀜 | P0: 카드마다 troop/유닛/Dreadnought 표기를 앱 문구 태그와 인쇄로 표에 적음. P4: 출처마다 종류별 셈 테스트, 유닛 수 조합 전부의 codec 왕복 |
| 3 | id를 종류 없이 찾아 보드 칸에 같은 id의 계약 그림이 뜸(09-27) | 원판 칸·Conflict가 Uprising 이름을 다시 씀, Uprising의 Infiltrate(Spy)·원판 Intrigue "Infiltrate"·Ix 잠입 아이콘 | P1: id 규칙(4.2절 7) + "종류 안에서 유일, 종류 사이 겹침은 목록으로" 테스트. 화면 조회는 늘 종류와 함께 |
| 4 | 아이콘을 색·모양·기대로 읽음(09-08, 09-09, 09-19, 09-25), 블라인드 감사 114건(09-26), 앱 대조 52건(10-06) | Ix 새 아이콘 여섯, 이름이 틀린 앱 스프라이트, 앱과 인쇄의 차이·에라타 | P0: 스프라이트 → 아이콘 대응표를 픽셀로 확인. P3·P4: 앱 표 기계 대조 pytest(9절 4), 카드면 확인, 단계 끝 앱 행동 대조(10.3 결정) |
| 5 | 구성을 합계로만 확인해 Ix 계약 타일 넷이 한 달 들어감(09-27), Epic의 비공개 setup 카드를 draft 전에 나눔 — Hundro 문장을 "범위 밖"으로 버림(10-02) | Ix Conflict 덱(I 1·II 5·III 4, III 하나 남음), Ix가 빼는 칸 넷, Reserve 24장(8·10·6), Hundro·Baron·Ilesa의 setup, 고정·draft 두 길 | P0: 구성표(룰북 합계·BGG 시트·앱 `CardCount` 셋이 종류별로 같아야)를 테스트로. setup 순서는 문장을 인용하고, "범위 밖"으로 둔 문장도 시점을 정하는지 적음. 고정·draft 두 길 모두 테스트 |
| 6 | 묶인 결정을 나중에 나눔(보드 아이콘, Agent box 9개, Reveal 이득, Intrigue 줄, OQ-106, B단계 — codec v86~v150), 새 제공자를 턴 종료 검사가 몰라 의무 아이콘 곁에 "턴 종료"(10-18) | Shipping 회수 보상(아래 칸 모두, 순서 자유), 협상가 돌려받기, Dreadnought 지배 칸 고르기, Unload | P0 명세에서 OQ-027(아이콘마다 독립)·OQ-106(공개 선택과 숨은 뽑기는 별개)을 처음부터 적용한 결정 목록. 새 제공자는 제공자 목록을 든 곳을 이름으로 모두 찾고, 제공자 목록 테스트에 넣음 |
| 7 | 허락 문장 없이 선택지를 만듦: Navigation Chamber "할인 없이"(10-10), 거절이 없어야 할 Beguiling Pheromones에 거절 | Tech 할인 아이콘(둘을 못 합침), 협상가 "원하는 만큼", Freighter 전진/회수 | 명세의 선택지마다 "근거" 칸(loc 키와 조건어 may/must, 또는 룰북 쪽). 근거 없는 선택지는 만들지 않음 |
| 8 | 판정을 다른 카드로 넓혀 효과 없는 Intrigue play를 열었다가 같은 날 되돌림(10-06), 앱 문구 의역으로 뜻이 바뀐 채 판정을 물음(09-29), 재판정이 다른 문서에 안 퍼짐(10-07) | FAQ의 원판·Ix 항목 27개, 앱 1차 전사 | P0에서 FAQ 원판·Ix 항목을 먼저 읽어 명세에 반영. 사용자에게 물을 때는 원문(loc 키·룰북 문장)을 보임. 재판정 때 옛 판정의 핵심 말로 `docs/` 전체 검색 |
| 9 | 조건을 판정하는 시점, trash된 카드의 효과(OQ-022 세 번 바뀜, 감사 #29) | Unload(버리거나 trash할 때 Reveal 상자), 상대 차례에 상대 효과로 버려질 때(Mohiam) | P4 명세에서 Unload가 열리는 모든 길(자기·상대 효과, 내 차례·남의 차례)을 목록으로, 길마다 테스트 |
| 10 | Uprising 값이 코드에 박혀 있음(영향력 4칸 보너스를 작은 그림에서 읽어 틀림, 09-19), codec·관측·체크포인트 변경, 학습 안 된 행(v150에서 4,311줄 중 84줄) | 칸 id 글자 약 125곳, 영향력 보너스·지배 칸·Maker 칸 표, 합집합 관측, 원판 행 전부 미학습 | P1에서 판 값 표로 옮기고 같음 관문. 관측은 끝에 붙이기(4.2절 5). 원판 AI는 앱 AI·휴리스틱으로 시작하고 망 학습은 따로 계획 |

### 10.2 그 밖에 단계 관문에 넣을 것

- **턴 종료(다섯 번 다시 고침, 09-23~10-18):** 원판·Ix가 더하는 턴 안 의무(Shipping, 뒤집는 Tech, Ilesa의 둘째 turn 공개 등)를 "턴 종료는
  한 번 누른다"와 턴 종료 census로 확인한다. 옛 흐름의 거절·확인 행동이 생기지 않았는지 codec에서 이름으로 찾는다.
- **중간에 연 frame이 덮임(09-26 감사):** Shipping 보상 안의 Acquire Tech처럼 해결 도중에 여는 결정은 A단계의 대기 능력 실행기로 줄
  세운다. 같은 꼴의 버그는 저장소 전체에서 찾는다.
- **"동작 그대로" 주장(09-23, 10-08):** P1은 같음 확인 200판·기보 2,000판 exact·실제 `saves/` 불러오기로만 말한다.
- **저장본(10-08):** 저장 문서에 판 식별자를 싣고, 엔진 이벤트를 더하면 화면용은 `report_only_event_kinds`.
- **앱 AI 포팅(10-05):** 모르는 카드·id에 기본값 대신 None을 돌려 census가 빈 곳을 세게 한다.
- **되돌리기 고리(09-06):** 협상가·Freighter를 오가는 고리를 AI 행동 가리개와 판 길이 상한으로 막는다.
- **화면(09-18~09-21, 10-11):** 한글 IME·캐시 든 브라우저에서 확인, `[object`·snake_case id·`{term}`이 없는지, 용어 문장을 두 언어로 펼쳐
  읽기. 앱 렌더는 꺼진 컴포넌트·잘린 스프라이트를 먼저 의심한다(10-07).
- **에셋 저장소(09-23, 09-28):** 나중에 TTS에서 찾는 보드 그림은 게임이 읽는 파일만 넣고, 참조·중간 산출물은 git 밖에 둔다.
- **도구 습관:** `ruff format` 금지, `pgrep -f` 대기 금지, ledger, 고아 worker 확인, workflow 디스크·메모리 상한(lessons 요약 그대로).

### 10.3 규칙 질문(OQ)에서 배운 것

`docs/rules/open-questions.md`의 OQ 112개(2026-10-21, 모두 DECIDED·RESOLVED)를 다시 보았다.

- **약 40%(45개)가 처음 판정 뒤에 바뀌었다.** 22개는 2026-10-04~08 앱 대조 때 사용자가 "앱 방식으로"를 골라서, 8개는 디자이너 판정을
  받아들여서, 약 20개는 그 밖의 사용자 판정이다. 2026-09-30 "자동으로 넘어가는 곳도 모두 결정 창을 연다"와 2026-10-06 "아무것도 바꾸지
  않는 Intrigue play 금지" 두 원칙이 열 개 넘게씩을 다시 고쳤다. 흔한 이유는 **아무도 묻지 않은 엔진 기본값**을 판정으로 굳힌 것, 일반
  원칙과 맞추기, 전사 오류, 소크가 찾은 교착이다.
- **질문의 종류:** 독립 효과의 순서·조건 판정 시점 26, "무엇이 X로 세이나"(어느 유닛·아이콘·recall이 해당하나) 19, 할 수 있는 것이
  없는 효과·공급 부족 15, 구역 사이 이동 8, 전투·유닛 셈 7. 두 모듈을 함께 쓸 때만 생긴 질문이 약 20개다.
- **이미 정한 원칙으로 바로 정해지는 것**(원판·Ix에 다시 묻지 않는다; 예는 내 추정): 아이콘마다 독립·순서 자유(OQ-027), 보상 줄 안의
  순서(OQ-112), 조건은 해결 때 판정(OQ-028·057 (1)), trash된 카드의 효과는 안 남(OQ-022, 디자이너 예가 Foldspace), Intrigue 줄은 따로·
  적어도 한 줄(OQ-058), 선택 효과는 거절 없이 턴 종료에 사라짐(OQ-095 (2)), 공개 선택과 숨은 뽑기는 별개(OQ-106), 6칸 진영은 안 냄
  (OQ-060), "each opponent"는 다음 좌석부터 시계 방향(OQ-036, 원판 Test of Humanity), 공급 부족은 같은 turn 안에 채움(OQ-030), "your
  turn"은 자기 Agent·Reveal turn(OQ-042·063), 모든 recall은 Conflict의 Agent도(OQ-068), Tech 할인은 "may"가 없으면 의무·하한 0
  (OQ-104·041), 끝 칸의 트랙은 아무것도 안 줌(OQ-048), 디자이너 판정 일괄 채택(OQ-057).
- **디자이너 판정 감사의 남은 몫:** `designer-rulings-audit.md` 17행이 원판·Ix 전용이라 건너뛴 판정 목록(Appropriate, dreadnought,
  infiltration, Tech Negotiation, Kwisatz Haderach, Mentat, Ix 지도자 …)을 갖고 있다. OQ-057의 일괄 채택대로라면 이것은 새 질문이 아니라
  감사할 몫이다(P0). `official-rulings-index.md` 102~116행에도 아직 분류하지 않은 FAQ 원판·Ix 항목이 있다.
- **고칠 기록 하나:** OQ-107(`open-questions.md` 1786행)이 Power Play를 "Rise of Ix 카드"라고 적었는데 원판 카드다(앱 정의 `BaseSet`,
  에셋 `base/imperium/Power Play.webp`, `designer-rulings-audit.md` 17행도 원판). 그 근거를 원판 카드에 다시 쓰기 전에 P0에서 고친다.
- **기존 원칙이 정하지 못할 질문(내 추정, P0 명세에서 확인):**
  1. Dreadnought가 있는 칸과 Control 방어(Round Start의 공개 → 방어 → 뽑기 순서, OQ-072), 그리고 Dreadnought가 떠나는 때.
  2. Shipping 보상의 Acquire Tech에서 협상가 돌려받기가 비용인지(OQ-058) 할인인지(OQ-104), 자기 turn 밖일 때.
  3. Unload: 다른 효과로 trash되거나 정리 때 옮겨질 때도 열리는지(OQ-022·035·054와의 관계).
  4. Dreadnought가 "troop"인지 "유닛"인지가 갈리는 모든 곳: troop 잃기, "유닛 셋", 동점 깨기, garrison에서 "둘까지"의 몫.
  5. 원판 Mentat이 "다른 Agent"·"이번 turn에 보낸 Agent"에 드는지, Swordmaster의 셋째 Agent와 함께.
  6. (P7) Uprising Spy의 잠입과 Ix 잠입 아이콘이 한 보드에 있을 때. 두 "Infiltrate"는 용어집에서 이름을 갈라야 한다.
  7. (P7) Bloodlines Tech Module과 Ix Tech가 함께일 때(더미·할인 합치기).
  8. 판마다 영향력 트랙 값(원판 4칸 보너스, 2칸 VP).
- **절차:** 새 질문은 구현 전에 모은다. 사용자에게는 공식 원문(룰북 쪽·FAQ·loc 키와 조건어), 앱의 처리, 기존 원칙이 가리키는 쪽을 함께
  보이고 묻는다. 엔진 기본값으로 먼저 정하고 나중에 묻지 않는다.

### 10.4 이 점검표에서 새로 생긴 결정

1. **앱 행동 대조 — 정함(2026-10-21 사용자, "추천대로"):** P3·P4 끝(화면·학습 전)에 원판·Ix의 카드·칸·지도자 **전부**를 앱의 카드 전용
   코드와 대조한다. 2026-10-06 대조(243항목에서 차이 52건, 학습·플레이가 한참 돈 뒤였다)를 앞당기는 것이다. 비용은 10-06 기준 약
   2,000만 토큰이고, 지난 견적이 절반이었으니 그 이상일 수 있다. 방법은 10-06과 같다: 묶음별 대조 → 차이마다 반박 위주 재확인 →
   공식 문서 인용으로 판정, 공식이 침묵하면 OQ(10.3 절차). 결과는 로컬 분석 폴더에만 둔다.
2. **새 OQ는 P0에서 한꺼번에 — 정함(2026-10-21 사용자, "추천대로"):** P0 명세를 쓰며 나온 질문을 모두 모아 한 번에 정한 뒤 P1에
   들어간다(10.3 절차대로 공식 원문·앱 처리·기존 원칙을 함께 보이고 묻는다). 뒤 단계에서 새로 나오는 질문은 그때 묻되, 엔진 기본값으로
   먼저 정해 두지 않는다.
3. **원판의 Arrakeen Scouts — 정함(2026-10-21 사용자): 나중 단계(P8)로 넣는다.** (설정은 2026-10-27 사용자 결정으로 처음부터 원판 + Scouts를
   받는다, 4.2절 1; 그 콘텐츠·판정이 P8이다.) 원판에는 관측 초소가 없어 초소를 쓰는 Scouts 항목(OQ-080 등)은 뜻을 잃는다. 지금 Scouts 설계가 범위 밖으로 둔 일정
   풀(`arrakeen-scouts-design.md` 1절: Rise of Ix 보드가 필요한 풀 — Uprising+Ix, 기본판 풀 넷)이 출처다. 어느 풀을 넣을지는 P8에서
   Game Room 앱 추출(Mac mini)을 다시 읽고 정한다.

## 11. 시간을 줄이는 방법 (후보, 2026-10-21)

pytest를 `-n 8`로 돌려 10분 16초를 2분 19초로 줄인 것(2026-10-21)처럼 시간을 줄일 후보다. 기계 시간보다 사람·agent의 시간이 큰
쪽부터 적는다. 효과는 모두 아직 재지 않았다.

**정함(2026-10-21 사용자):** 1~6번을 P0 시범에 넣어 잰 뒤 단계마다 쓸지 정한다. 3번 (나) 디컴파일러는 내려받기 전에 사용자에게 다시
묻는다(도구 이름·출처·크기와 함께). 7·8번은 시범에 넣지 않는다(7번은 9절 10의 기기 결정 뒤에, 8번은 작아서 필요할 때).
시범에서 잴 것: 1·2번은 Uprising 카드에서 그대로 맞힌 장수와 고친 칸 수, 3번은 답을 아는 10-06 사례에서 agent 토큰과 맞힌 판정,
4번은 시범 전사를 두 갈래로 나눴을 때의 시간과 합칠 때의 충돌, 5번은 지난 관문 실패 사례를 몇 개 잡는지, 6번은 이미 그린 Uprising
앞면에서 사람이 고른 이상한 카드를 몇 개 잡는지.

1. **카드 정의를 앱 표에서 생성:** 숫자·아이콘·장수·진영을 사람이 옮기지 않고 `agents/app_ai/data/archetypes.py`에서 만들어 낸다. 기계 대조
   pytest(9절 4)와 같은 표를 쓰므로 그 칸은 처음부터 맞는다. 줄어드는 것: 전사와, 지난번 감사 114건 같은 오독 고치기.
2. **앱 문구에서 능력 기록 초안 생성:** 앱 문구의 아이콘 태그(`<sprite name=…>`)와 흔한 모양(얻기, 비용 → 보상, 조건, 택일)을 DSL 초안으로
   바꾸는 변환기. agent는 초안 검토와 hook만 맡는다. **먼저 Uprising 카드로 정확도를 잰다**: 이미 맞춰 둔 Uprising 기록이 정답이라, 변환기가
   몇 장을 그대로 맞히는지 셀 수 있다. **결정(D4, 2026-10-23):** 문구 대신 화면 조각(2.2 4)을 입력으로 바꿔 P3 첫 묶음에서 시범한다.
3. **앱 코드 읽기를 짧게:** 10-06 대조는 묶음마다 카드 능력 클래스의 asm 파일을 통째로 읽었다(예: Cargo Runner 한 능력은 225줄이지만
   Kwisatz Haderach는 3,334줄, helper는 따로). 두 길이 있다. (가) 카드마다 쓰는 메서드와 부르는 helper만 뽑고, 공용 helper는 한 번 요약한
   설명서로 대신하는 묶음 도구. (나) IL2CPP 디컴파일러(예: Ghidra, Cpp2IL)로 asm 대신 C 비슷한 코드를 읽기. (나)는 도구를 내려받아야 해서
   사용자 허락이 필요하다. 답을 아는 10-06 사례 몇 개로 토큰과 정확도를 재고 고른다. 줄어드는 것: P3·P4 끝 행동 대조의 2,000만 토큰.
   **결정(D4, 2026-10-23):** (가) 만들지 않는다. (나)는 P3 끝의 앱 행동 대조 전에 다시 묻는다(그날 시범 제안 — Ghidra 12.2 569.7 MB와 JDK 21
   199.8 MB — 은 사용자가 그만뒀다).
4. **카드 묶음을 여러 갈래로:** card-implementer agent를 갈래마다 따로 worktree에서 돌리고(10-08 화면 작업의 네 갈래처럼), 관문은 합친
   뒤 한 번. 갈래는 파일이 겹치지 않게 종류로 나눈다(lessons: 같은 작업 트리를 둘이 고친 사고). 줄어드는 것: P3·P4의 달력 시간.
   **결정(D5, 2026-10-23):** P3 첫 묶음에서 시범 전사 5장과 함께 잰다.
5. **관문 전에 몇 초짜리 검사:** 종류 안 id 유일, 구성표, 새 숨은 더미의 `known_card_seats` 포함, 제공자 목록, 몇 판의 codec 왕복을 한 명령으로.
   30분 관문이 늦게 찾던 것을 먼저 잡아 관문을 다시 도는 횟수를 줄인다. **결정(D4, 2026-10-23):** 명령은 만들지 않고 구성표·`known_card_seats`
   등록·제공자 목록 셋을 P1~P4의 보통 테스트로 둔다(13.3 5).
6. **렌더와 스캔 비교를 수치로:** P5에서 앱 조각으로 그린 앞면 약 200장을 스캔과 이미지 거리로 비교해 벗어난 카드만 사람이 본다
   (lessons 2026-09-22 "기하는 눈이 아니라 측정으로"). **결정(D4, 2026-10-23):** 지금 방식은 쓰지 않는다(13.3 6); 필요하면 P5에서 칸별 정렬
   비교로 다시 판단한다.
7. **학습과 관문을 다른 기기로:** 원판 망 학습(P6 이후)이 Mac mini를 오래 잡으면 그동안 관문을 못 돈다. 그때 학습이나 관문 가운데 하나를
   다른 PC에서 돌리면 서로 기다리지 않는다(관문 자료는 그때 다시 묶어 옮긴다 — 2026-10-21의 v150 묶음은 낡아서 지웠다). 지금의 기기
   결정(9절 10)은 P0~P4라 그 뒤에 정한다.
8. **작은 것 — 끝(2026-10-21):** 기보 대조의 작업 프로세스 상한을 8로 올렸고(niceness 10 그대로), pytest `--durations`로 찾은 가장 긴
   테스트를 나눴다(worklog "반복 작업 속도"). 이미 병렬인 관문(같음 확인 6, 소크 8, E2E 4 — E2E는 8개씩이
   4개씩보다 조금만 빨랐다, 2026-09-27)은 더 쪼개도 얻을 것이 적다.

## 12. P0 착수 순서 (2026-10-21)

P0는 문서와 측정이 대부분이라 Mac mini에서 ② 학습과 겹쳐도 되지만, 시범 측정(아래 6)은 ② 학습이 돌지 않을 때 한다(9절 10). 새 세션은
`AGENTS.md`·`CLAUDE.md`의 시작 점검 뒤 이 문서 전체와 `docs/lessons.md` 맨 위를 읽고 시작한다.

1. **공식 출처 등록:** 원판 룰북 `DUNE_IMPERIUM_Rules_2020_10_26.pdf`, Player Aid, 한국어판 `KR_Dune_Imperium_Rulebook.pdf`를
   `scripts/official-rule-sources.json`과 `docs/rules/sources.md`에 같은 작업으로 등록하고(인용 이름 `[DI p. N]`), Rise of Ix의 규범 범위를
   넓힌다(3절). `scripts/prepare_official_rules.py`로 받아 쪽 번호를 확인한다.
2. **기록 정정:** OQ-107의 Power Play(원판 카드, 10.3절).
3. **카드 출처 정책:** `AGENTS.md` "Card and image sources"와 `docs/card-data-sources.md`를 9절 2대로 고친다(규칙 근거는 그대로 공식 문서).
4. **규칙 명세 두 편:** `docs/rules/imperium-base.md`·`docs/rules/rise-of-ix.md`. 넣을 것: Uprising과 다른 것(5·6절), FAQ의 원판·Ix 항목
   (27개), 디자이너 판정 감사의 남은 몫(`designer-rulings-audit.md` 17행), 숨은 정보 절, 구성표(룰북 합계·BGG 시트·앱 장수), 결정 단위와
   선택지마다 근거(10.1절 6·7), 이미 정한 원칙으로 정해지는 것(10.3절).
5. **앱 자료(로컬):** 원판·Ix 아키타입 표와 영어 문구 추출(`analysis/card-compare-2026-10-06/extract_app.py`), 문구의 스프라이트 이름 →
   우리 아이콘 대응표를 픽셀로 확인해 고정(2.3절).
6. **시범:** 11절 1~6번 도구 시범(재는 것은 11절), 시범 전사 5장으로 카드 한 장의 시간·토큰을 잰다. 3번 (나) 디컴파일러는 내려받기 전에
   사용자에게 묻는다.
7. **새 OQ 한꺼번에:** 4~6에서 나온 질문을 모아 공식 원문·앱 처리·기존 원칙을 붙여 사용자에게 한 번에 묻는다(10.4절 2). 판정이 끝나면
   8절 어림을 시범 측정으로 고치고 P1로 간다.

## 13. P0 결과 (2026-10-22)

12절 1~5와 7은 끝났고, 6(시범)은 아래처럼 일부만 잴 수 있었다. 기록은 worklog 2026-10-22 "원판·Rise of Ix P0", 자료는 git 밖(에셋
`reference/dune-steam-app/dad97e20…/analysis/base-ix-2026-10-22/`, 이 체크아웃의 `tmp/claude/d0c52597/`).

### 13.1 산출물

- 공식 출처 등록: 원판 룰북 `[DI p. N]`·Player Aid `[DI Aid p. N]`·한국어판(manifest 키 `imperium`·`imperium-player-aid`·`imperium-ko`), Rise of Ix
  규범 범위 pp. 2-7, 10, 12. Player Aid는 룰북 pp. 16-18과 같은 글이다(낱말 대조).
- 규칙 명세 두 편: [rules/imperium-base.md](rules/imperium-base.md), [rules/rise-of-ix.md](rules/rise-of-ix.md). Uprising Main이 원판과 다르다고 표시한 일곱
  자리(이미지 xref 98)를 차이표가 모두 덮는다. FAQ의 원판·Ix 항목, 디자이너 판정 감사의 남은 몫(57개 읽음), 숨은 정보 절, 구성표, 결정 단위표.
- 기록 정정: OQ-107의 Power Play(원판 카드). 카드 출처 정책: `AGENTS.md`·`card-data-sources.md`.
- 새 OQ: **OQ-113 ~ OQ-127**(원판 쪽 9, Ix 쪽 6). 질문마다 공식 원문, Steam 앱의 처리(보조 증거; 앱 코드 확인 agent 둘과 카드별 조사가 읽음), 가장 가까운
  기존 판정, 추천을 붙였다. P0가 앱과 룰북의 차이로 분류한 넷 중 The Voice의 막힘 길이는 앱 분석 재검증 대상으로, Bindu의 turn 계속은
  사용자 제공 공식 문장의 선택형 pass로 정정했다(OQ-116·117, 2026-10-22). dreadnought 복귀의 앱 분석도 OQ-121에서 재검증하며,
  공식 다음 Combat 끝 복귀와 미확정 엔진 순서를 구분한다. Sort Through the Chaos의 Mentat 시점은 해당 명세를 따른다.
- 카드별 조사(agent 넷, 2026-10-22 사용자 결정 "하위 에이전트로 동시에"): 카드 181장·보드 칸 26·체계 셋을 한 장씩 보고 전사 자료(앱 속성·문구·카드면·능력
  클래스를 합친 것, P3·P4의 입력)와 질문 후보를 남겼다(`tmp/claude/d0c52597/sweep/`, 약 230 KB). 후보 13건 가운데 5건이 OQ-123 ~ OQ-127이 됐고, 1건(The Voice가 풀리는 때)은
  OQ-116을 넓혔고, 나머지는 기존 원칙으로 정해져 명세의 "이미 정한 원칙" 절에 적었다. 정해진 것으로 본 점 약 170개는 그 파일에 근거와 함께 있다.
- 앱 자료(로컬): 원판·Ix 정의 228개 표와 영어 문구(`cards.json`, `cards-compact.md`). 카드면 181장 블라인드 읽기(agent 넷, 약 57만 토큰).
  worktree를 지워도 남도록 카드면 읽기·카드별 전사 자료·앱 확인·DSL 분류를 에셋 `…/analysis/base-ix-2026-10-22/p0-readings/`에 복사했다(2026-10-23).

### 13.2 계획을 바꿀 측정 둘

1. **원판·Ix 카드는 앱 문구가 칸을 다 덮지 않는다.** Uprising 계열 Imperium 82장은 72장에 문구가 있고 62장의 문구에 아이콘 태그가 있다(앱이 문구로
   카드면을 그린다). 원판·Ix Imperium 76장은 35장만 문구가 있고 아이콘 태그가 든 것은 14장이다; Intrigue 51장은 31장·4장. 아이콘뿐인 칸(Conflict 보상
   전부, Agent box 다수, Tech 셋, Leader Signet)은 문구에 없고 능력 클래스와 카드면에만 있다. 2.2절 2층("영어 문구가 그림 읽기를 대신함")은 원판·Ix에서
   성립하지 않는다. 대신 쓸 수 있는 것: **카드면 블라인드 읽기 + 앱 속성 기계 대조**(13.3). 2.4절 흐름을 이것으로 고치는 것은 사용자 결정 D1.
   **2026-10-23 보강:** 판정 중에 카드별 화면 조각(2.2 4)이 아이콘뿐인 칸까지 인쇄 배치로 갖고 있음을 찾았다. 그래서 D1은 블라인드 읽기 대신
   앱 자료만으로 전사하는 쪽으로 정해졌고, 블라인드 읽기는 디지털판·인쇄판 차이를 찾는 한 번의 대조(D2)에 쓴다.
2. **Dune Cards Hub 그림이 틀린 것이 섞여 있다.** Duncan Idaho의 Reveal 검: 앱 2, Dune Cards Hub 스캔 3, 사용자가 찾은 실물 스캔(duneimperiumassets.com) 2
   (2026-10-22). 카드면 확인의 그림 출처는 사용자 결정 D2.

### 13.3 도구 시범 (11절 1~6)

| # | 잰 것 | 결과 | 추천 |
| --- | --- | --- | --- |
| 1 | Uprising 계열 Imperium 82장의 앱 표 여섯 칸(비용·장수·진영·Agent 아이콘·Persuasion·검) 대 감사 뒤 우리 값 | 79장 그대로, 3장은 값이 아니라 자리가 다름(Long Reach·Show of Strength의 `ConditionalIconList`, Desert Power의 Persuasion은 능력 클래스) — 틀린 값 0. 원판·Ix 94장(Imperium 76, Tech 18)의 블라인드 카드면 대 앱: 다른 값 1(Duncan Idaho, 그림 쪽이 틀림) | 채택. 생성 규칙 둘(조건부 아이콘, 능력 클래스 안의 값)과 예외 목록 |
| 2 | 앱 문구 → 능력 기록 초안 변환기 | 만들기 전에 덮는 범위를 쟀다(13.2 1): 원판·Ix Imperium 76장 중 아이콘 태그 문구 14장 | 만들지 않음. 대신 블라인드 읽기 + 앱 속성 대조(이번 P0에서 181장, 장당 약 3천 토큰; 한 agent가 이름 모르는 Ix 아이콘 하나를 잘못 짚었고 룰북 아이콘 쪽·앱 태그로 잡았다) |
| 3 | 앱 코드 읽기 줄이기 | (가) 원판·Ix 능력 클래스 323개의 asm 39만 줄 가운데 AI 평가 메서드는 19%, 생성자 11% — 메서드를 걸러도 30% 안팎. 기준선: 이번 P0의 앱 확인 두 agent — 원판 5문항 45.5만 토큰(문항당 약 9만, 2026-10-06 대조와 같음), Ix 4문항 62.2만(문항당 약 15.5만) | (가) 효과 작음. (나) 디컴파일러는 내려받기 허락이 필요(사용자 결정 D4) |
| 4 | 카드 묶음을 여러 갈래로 | 엔진에 원판 콘텐츠 자리가 없어(P1 전) 실제 전사를 잴 수 없다 | P3 첫 묶음에서 재고 그때 어림을 고친다(D5) |
| 5 | 관문 전 몇 초짜리 검사 | 만들기 전에, 제안한 검사 여섯(종류 안 id 유일, 구성표, `known_card_seats` 등록, 제공자 목록, 몇 판의 codec 왕복, 표시 문구)이 지난 사건을 잡았을지 worklog 2026-09·10과 lessons에서 61건을 골라 분류했다(agent, 판단이지 측정은 아님): 분명히 일찍 잡았을 것 3건(5% — 구성표: Ix 계약 타일 넷이 한 달 섞임 09-27, `known_card_seats`: 확장 더미·엿보기 누락 09-24, 제공자 목록: 턴 종료 판정이 다섯째 제공자를 모름 10-18), 그럴 수도 있는 것 13건(21%). 늦게 찾은 대부분은 규칙 판단·아이콘 전사·숨은 정보 시점·되돌리기 흐름이었다 | 따로 명령으로 만들지 않음. 구성표·`known_card_seats` 등록·제공자 목록 셋은 P1~P4의 보통 테스트로(계획 10.1절 1·5·6과 같은 자리), 실행되는 표를 기준으로(lessons 2026-09-21 "소스 문자열이 아니라 실행되는 표") |
| 6 | 렌더와 스캔의 이미지 거리 | 단순 거리(정규화 픽셀 + 윤곽, 4×4 블록 최댓값)로 처음 렌더(에셋 `8809558`) 194장을 순위 매기니, 사람이 짚어 고친 25장(`9155440`의 Tleilaxu·접합 24장, `7c3956e`의 Signet Ring) 가운데 상위 25위 안 0장, 중앙 순위 116~120위 | 지금 방식은 채택하지 않음. 쓰려면 칸별 정렬 비교가 필요(P5에서 다시 판단) |

표의 "추천"은 P0 때의 것이다. 사용자 결정은 13.5 D4·D5(2026-10-23): 2는 입력을 화면 조각(2.2 4)으로 바꿔 P3 첫 묶음에서 시범한다.

### 13.4 크기 다시 어림

카드면 블라인드 읽기를 지금의 능력 기록(DSL) 모양에 맞춰 칸마다 분류했다(agent, 판단이지 구현이 아님; `tmp/claude/d0c52597/dsl-coverage.md`).
181장 332칸 가운데 **기존 모양으로 되는 칸 240(72%)**, 원판·Ix의 새 체계 조각이 필요하지만 한 번 만들면 데이터로 다시 쓰는 칸 82(25%),
카드 한 장만을 위한 hook 10(3%; 위험하게 본 11칸이 hook이 되면 21, 6%). 카드로는 98장(54%)이 기존 모양만으로 된다. Conflict는 66줄 중 61줄이
기존 모양이고, 새 일은 Ix Imperium·Intrigue·Leader에 몰려 있다(Leader 28칸 중 hook 7). 새 조각의 큰 것: Freighter 11칸, Unload 9장, Infiltration 7장,
dreadnought 묶음 9칸(+hook 3), Influence track 조건 5칸, 이긴 뒤 내는 Combat Intrigue 창 4칸. 기존 모양이라도 엔진 연결 일이 있다: Reveal 이득 줄의
조건 목록 넓히기, Agent box·Plot에서 Acquire Tech 열기, Conflict 보상의 고르기 줄(ONE_OF·CHOOSE_TWO — 지금 엔진은 SEQUENCE만 지급), 획득 효과의
고르기, Foldspace 더미, Round Start·승리 trigger가 일반 보상을 읽기, 새 시점 두 개(`OWN_TURN`, `GAME_START`).

어림에 주는 것: P3(원판 카드)는 카드의 약 3/4이 기존 모양이라 8절 어림(2~3일)의 아래쪽, P4(Ix)는 새 조각이 몰려 있어 어림(4~6일) 그대로 둔다.
Leader 14명은 hook이 많아 P2·P4에서 지도자마다 따로 잰다. 정식 고친 어림은 P3 첫 묶음(D5) 뒤에 낸다(지난 견적이 실제의 절반이었다).

### 13.5 사용자 결정 (P1 착수 전)

- **OQ-113 ~ OQ-127 판정**(10.4절 2: 남은 판정 전에는 P1에 들어가지 않는다). 2026-10-22 사용자 결정:
  - OQ-113: **확정(2026-10-24) 통일 기준 (C) "비용을 낸 것만 보장"** — 디자이너와 앱이 카드마다 엇갈려 어느 출처도 일괄로 따르지 않는다. 비용이
    있는 줄은 보상 하나가 살아 있어야 내고(OQ-071 그대로), 비용 없는 효과는 불발해도 낸다(Know Their Ways·Illicit Dealings가 손에 묶이지 않음).
    원판·Ix 다섯: Know Their Ways·Dispatch an Envoy·Infiltrate 낸다, Water of Life(두 더미가 빔)·Advanced Weaponry Plot(dreadnought 둘) 막음.
    G3 같음, G4는 Emperor 4 Spy만 다르고 2026-10-04 판정 유지(앱도 같음, 10-24 재확인). AI는 거르지 않고 사람에게 클릭 전 경고, 효과 없는 play는
    되돌릴 수 있어야 한다. 디자이너·앱과 다른 곳은 공지 대상. **Uprising 엔진 변경(10-06 막기 중 비용 없는 경우 풀기, codec)은 별도 작업 — 구현
    전에 AI 세션과 사용자 확인**(구현 목록은 OQ-113).
  - OQ-114: **확정** — 기존 동작대로 서로 다른 두 항목을 먼저 정하고 해결한다.
  - OQ-115: **확정** — 첫 조건 달성 시 의무 공개; 기존 "이번 turn에 3개 이상 배치" 조건의 계산·회수 판정을 따르고 문턱만 4.
    troop에 Sardaukar Commander를 포함하며 dreadnought는 제외한다. 세부는 OQ-115.
  - OQ-116: **확정 B** — 상대별 이번 라운드 다음 Agent 배치까지. Bindu·Litany 등의 Agent 없는 pass는 봉쇄를 소비하지 않는다.
    Control marker는 조건·비용이 아니고 별도 마커/UI로 표시한다. 앱의 라운드 전체 봉쇄 주장은 재검증한다.
  - OQ-117: **확정 C** — 다른 행동 전 차례 시작에만 사용, 공개해야 하는 차례도 사용 가능. 뽑은 뒤 pass 여부는 선택.
    사용자가 공식 문장으로 제시한 근거에 따라 의무 종료 추천을 폐기한다(고정 PDF와의 출처 차이는 OQ-117에 명시).
  - OQ-118: **확정 A** — 두 장 강제 버리기는 가능한 만큼 수행, 한 장뿐이면 한 장. 비용 지불과 구분한다.
  - OQ-119: **확정** — Ilesa의 둘째 turn 계산에 Agent 없는 pass와 Weirding Way 추가 turn 모두 포함한다.
  - OQ-120: **확정** — Unload 카드를 공개해 보상을 받은 뒤 같은 Reveal turn에 trash하면 다시 받는다.
  - OQ-121: 앱 재검증 끝(2026-10-23): dreadnought가 있는 칸은 못 고르고, 지난 dreadnought는 다음 라운드 Recall에 돌아간다(P0 분석은 틀림). 사용자
    방향: 앱처럼 순위마다 "보상 → 그 좌석의 창" — Combat 단계의 관련 문제(battle icon 시점은 공식대로, 선택형 보상 조각, Conflict 끝 Intrigue 창)를
    정한 뒤 확정. **복귀 시점은 확정(2026-10-24, 부분 확정)**: 지난 지배 dreadnought는 룰북대로 Combat 단계의 마지막 일로 garrison에(앱의
    Recall이 아님), Conflict에 남은 dreadnought(진 쪽, 이긴 쪽의 두 번째)는 troop을 supply로 돌리는 정리 때, Detonation Devices는 지배하러 갈
    Conflict의 것만 supply로. 지금 원판·Ix 카드로는 앱과 결과가 같지만 공식 문장과 "원칙대로" 지시로 골랐다.
    **Combat 순서 확정(2026-10-24~25, 하나씩 여섯)**: 세 판(Uprising·원판·Ix)이 같은 순서를 쓴다. 순위마다 "보상 + 그 좌석의 창" → (Uprising)
    battle icon(공식대로 마지막 창 뒤) → troop·Commander는 supply로, Conflict에 남은 dreadnought는 garrison으로 → 좌석별 Conflict 끝 창(Harvest Cells,
    셈은 지금 엔진) → marker 0 → 지난 dreadnought 복귀(다른 세션 판정).
    - 창 안에서는 보상 아이콘과 창 능력(지배·Detonation·Windtraps·Planetary Array·Strategic Push 몫·승리 책략)을 좌석이 원하는 순서로 처리한다.
    - 승리 책략은 승자의 창에서만 낸다.
    - Uprising에서 바뀌는 것은 Planetary Array의 자리(승자의 창, OQ-108 재판정) 하나이고, 구현 전이다. codec·기보가 바뀌므로 AI 세션과
      사용자 확인 뒤에 한다.
    - 세부는 OQ-121 "판정 — Combat 단계 순서".
  - OQ-122: **확정(2026-10-23)** — 앱과 같은 순서: 공개 → Control 방어 → 각자 5장(Tech 되돌리기 함께) → 결정 없는 Round Start 효과(Twisted·
    Holtzman Engine·Shuttle Fleet) → Ilesa의 따로 두기(Holtzman으로 뽑은 카드까지 든 손에서) → Scouts/첫 turn. 좌석은 First Player부터.
  - OQ-123: **확정** — 현재 조건처럼 전체 보유 The Spice Must Flow를 센다(덱·손·discard·in play, trash 제외).
  - OQ-124: **확정 A** — Mentat을 제 칸에 보낼 수 있으나 카드 1장만 뽑고 Agent로 남으며 다시 가져오지 않는다.
  - OQ-125: **확정(2026-10-23)** — Row와 Reserve에서 고르고 Foldspace는 뺀다(지금 Uprising 엔진 그대로, 앱과 다름).
  - OQ-126: **확정(2026-10-23)** — 그 Reveal turn에 얻은 Persuasion 합계(쓴 것 포함). 앱과 같고, Command (6+)의 계수를 쓴다.
  - OQ-127: **확정(2026-10-23)** — 문장대로 Conflict에 배치하고 다음 단계에서 supply로(앱 코드도 같음).
  - 이 결정들은 P1 착수·병합·push·학습 또는 측정 재시작을 승인한 것이 아니다.
- **D1 — 원판·Ix 전사 흐름: 확정(2026-10-23) 앱 데이터만.** 속성 표 + 카드별 화면 조각(2.2 4) + 영어 문구로 전사하고 카드면 스캔은 새로 읽지
  않는다. 스프라이트 → 아이콘 대응은 앱 그림으로 한 번 픽셀 확인, 능력 클래스는 순서·may/must·시점이 모호할 때만(2.4절). 처음 낸 추천(카드면 블라인드
  읽기 + 앱 속성 대조)은 화면 조각을 찾기 전의 것이라 사용자가 다시 정했다.
- **D2 — 디지털판·인쇄판 차이: 확정(2026-10-23) P0 읽기와 한 번 기계 대조.** 화면 조각을 P0의 카드면 블라인드 읽기 181장과 스크립트로 대조하고, 다른
  카드만 사람이 본다(필요하면 그 카드만 duneimperiumassets.com 실물 스캔). 다르면 FAQ 에라타·인쇄판을 따른다(2.4절 5).
- **D3 — 보드에만 인쇄된 값: 확정(2026-10-23) 앱 데이터, 그림은 확인용.** Influence 4칸 보너스, Sell Melange 교환표, Alliance token의 VP는 P2 직전에
  앱 코드·보드 장면에서 읽고, 고화질 보드 그림(9절 7, 미룸)을 찾으면 확인한다. 룰북 p. 4의 작은 그림으로는 읽지 않는다(lessons 2026-09-19).
- **D4 — 도구 채택(11절): 확정(2026-10-23), 하나씩 정함.**
  - 1 앱 속성 표에서 정의 생성: **채택.** 인쇄와 다른 값은 근거를 단 예외 목록.
  - 2 능력 기록 초안 변환기: **P3 첫 묶음에서 시범.** 입력을 문구에서 화면 조각으로 바꿔 만들고, P0 카드별 전사 자료와 맞춰 정확도를 잰 뒤 쓸지 정한다.
  - 3 (가) 묶음 도구: **만들지 않음**(줄어드는 양 30% 안팎; 필요할 때 `il2dis`·덤프 grep). (나) 디컴파일러: 사용자가 "지금 시범"을 골랐다가 내려받을
    파일(Ghidra 12.2 569.7 MB + JDK 21 199.8 MB)을 보고 **그만둠** — P3 끝의 앱 행동 대조 전에 다시 묻는다. Cpp2IL은 출력이 C 비슷한 코드가 아니라
    가짜 DLL·ISIL이라 후보에서 뺐다(이름 덤프는 `il2dump.py`가 이미 한다).
  - 5 관문 전 검사: **명령은 만들지 않고** 구성표·`known_card_seats` 등록·제공자 목록 셋을 P1~P4의 보통 테스트로.
  - 6 렌더·스캔 이미지 거리: **채택 안 함**(사람이 고친 25장을 못 잡음). 필요하면 P5에서 칸별 정렬 비교로 다시 판단.
- **D5 — 4번 시범과 시범 전사 5장: 확정(2026-10-23) P3 첫 묶음으로 미룸.** P1 전에는 엔진에 원판 콘텐츠 자리가 없어 실제 전사의 시간·토큰을 잴 수 없다.

## 14. P1 결과 (2026-10-27, 브랜치 `claude/base-ix-p1-6a418f`)

4.2절의 모양대로 세 커밋으로 넣었다. 하위 단계마다 관문 전체(pytest·ruff·mypy, 같음 확인 200판 check·compare, 소크 900판, 기보
v155 2,000판, 저장본·문제집, tips-v1 재채굴, E2E)를 돌렸다.

1. **콘텐츠 조회(순수 리팩터, `9671a015`):** `content/rulesets.py`의 `content_for(config)`가 그 판이 **쓰는 것**을 돌려준다 — 보드 칸,
   관측 초소, Conflict(전체와 이 설정의 단계별 더미), Reserve, 지도자, Imperium·Intrigue 덱, 계약, Objective, 스타터 덱 — 와 보드에
   **인쇄된 값**: 영향력 4칸 보너스(능력 기록 `PlaceSpy`·`GainResources`·`DrawIntrigueCards`로; `rules/influence.py`가 진영 대신 기록을
   읽는다), Maker 칸과 모래벌레 칸, 지배 칸의 방문 보너스. setup·Agent 칸 목록·codec·Maker 검사·소크 도구가 이것을 읽는다.
   **id로 찾는 표는 하나로 둔다**(`BOARD_SPACES_BY_ID`, `personal_card_for_instance` 등): 4.2절 7대로 id 하나가 인쇄 하나라, 두 판의
   것을 한 표에 넣어도 섞이지 않는다(관측·엔티티 망 어휘도 이미 합집합이다). Uprising에만 있는 체계의 속(Spy·모래벌레·계약의 모듈 표)은
   그대로 두었다 — 원판은 그 길에 닿지 않는다(4.2절 3).
2. **판 축(`4729b583`, 확장 조합 열기 뒤에 이어짐):** `RulesetConfig.base_game`(`BaseGame.UPRISING` 기본 / `IMPERIUM`)과 `rise_of_ix`.
   처음에는 판마다 허용 확장 목록을 두었으나 사용자가 고쳤다(4.2절 1, 2026-10-27): 모든 확장이 어느 기본 판과도, 서로와도 결합된다(두 판 ×
   288 조합). 원판 식별자 `imperium-4p-…`(예: `imperium-4p-choam+promo+ix+epic`), Uprising + Ix는 `uprising-4p-base+ix…`, Ix 없는 Uprising
   식별자는 한 글자도 그대로. 새 칸 둘은 기본값일 때 상태 해시에서 빠져(`HASH_OMITTED_AT_DEFAULT`) 옛 저장·기보·체크포인트가
   그대로 읽힌다. 저장 문서는 `base_game`·`rise_of_ix`를 싣고, 없으면 Uprising이다. 원판 콘텐츠는 아직 비어 있고(스타터 덱만 Uprising과
   같은 인쇄, `[DI p. 3]`), 콘텐츠가 없는 조합의 setup은 `NotImplementedError`(보드가 없는 판은 P2, Rise of Ix는 P4·P7에서 풀린다). codec은 원판 카탈로그(지금 73줄)를 그 콘텐츠로
   만들고, 보드가 인쇄하지 않는 Uprising 체계의 줄(Spy·모래벌레·Sietch Tabr 고르기, Uprising 카드 한 장이 인쇄한 Reveal 줄, Uprising
   Conflict의 지배 칸, Uprising 카드의 미룬 Reveal 고르기)은 넣지 않는다. Uprising 144개 조합의 행 목록은 시작 커밋과 바이트까지 같다.
   테스트: 두 판 × 288 조합의 식별자 왕복, 576 카탈로그가 모두 만들어짐(Uprising + Ix는 Ix 콘텐츠 전이라 Ix 없는 것과 같다), 원판 카탈로그에 Uprising id·체계가 새지 않음, **종류 안에서 id 유일·종류 사이 겹침은 목록으로**
   (10.1절 3; 지금 겹침은 `deliver_supplies` 하나 — 보드 칸과 계약).
3. **관측 v34(`6bb72629`):** `PlayerView.base_game`과 맨 끝의 `base_game` 1칸(원판이면 1). Uprising 관측은 v33 벡터 뒤에 0 하나다.
   형식 2 이관은 새 열을 0에서 시작하므로(MLP 구간 이름, `mlp_slots` 행 열쇠, 엔티티 입력 이름 `raw:base_game:0`) 옮긴 망이 Uprising
   판에서 같은 출력을 낸다. 같음 확인의 정해진 차이는 `scripts/ab/differences/base_game_axis.py`(설정의 새 칸 둘과 보기의 `base_game`).

P2가 할 일(이 축 위에서): `content/imperium/`에 보드 22칸·Conflict 18·지도자 8·Reserve 셋을 넣고 `rulesets._imperium_content`가
돌려주게 한다. 보드에 인쇄된 원판 값(영향력 4칸 보너스, Maker 칸 셋, 지배 칸 Arrakeen·Carthag·Imperial Basin의 방문 보너스)은 D3대로
앱 자료에서 읽어 같은 자리에 채운다. 영향력 보너스에 새 모양(예: 병력)이 있으면 `_apply_track_bonus`에 그 기록을 더한다. 이름이 같아도
인쇄가 다른 칸·카드는 새 id(4.2절 7)로 하고, id 테스트의 겹침 목록이 그것을 지킨다.

## 15. P2 계획과 결과 (2026-10-27, 브랜치 `jungcheolseung/base-ix-p2`, master `12294215`에서; 결과는 15.8·15.9)

**승인(2026-10-27, 조정자 경유 사용자 확인):** 15.7의 1~6 모두. 4는 조건을 더했다: Uprising 개체의 `feature_tables()` 행은 열 척도까지
시작 커밋 `12294215`와 바이트로 같아야 한다(척도가 원판 값으로 바뀌면 이관 보정에 기대지 않고 Uprising 값으로 고정하거나 먼저 묻는다). 5는
사용자 판정 (가)로 OQ-139 `DECIDED`.

8절 표의 P2(원판 보드·흐름)를 두 하위 단계로 나눈다. 끝의 모습은 원판 4인 판(확장 없음)이 휴리스틱 좌석으로 끝까지 도는 소크이고,
그동안 Uprising은 바이트까지 그대로다(14절의 관문). 규칙 근거는 [rules/imperium-base.md](rules/imperium-base.md)의 절과 인용,
보드에만 인쇄된 값은 D3대로 앱 자료(로컬 `reference/dune-steam-app/dad97e20…/`)에서 읽는다.

### 15.1 하위 단계

| 단계 | 내용 | codec | 관측 |
| --- | --- | --- | --- |
| **P2a 보드와 흐름** | 22칸(능력 기록과 고르기 흐름), Mentat 말, 지배 칸 셋, Maker 칸 셋, Reserve 셋(Arrakis Liaison, 원판 The Spice Must Flow, Foldspace 카드와 Foldspace 칸의 획득), 영향력 4칸 보너스, Conflict 18장(보상 줄), 원판 판 흐름(무작위 시작 플레이어, Objective·Shield Wall·Spy·모래벌레 없음, Conflict 카드는 보드에 쌓임), 지도자 8명의 정의(이름·가문·셋업 값)와 그 가운데 **넷**(Glossu Rabban, Count Ilban Richese, Earl Memnon Thorvald, Countess Ariana Thorvald)의 능력 | v155 그대로(15.4) | **v35**(합집합 끝에 붙임, 15.4) |
| **P2b 지도자 넷** | Duke Leto Atreides, Helena Richese, Paul Atreides, Baron Vladimir Harkonnen의 능력. 지도자마다 커밋 하나와 그 회귀 테스트, 지도자마다 든 시간·hook 수를 잰다(13.4절) | v155 그대로 | Paul(덱 맨 위)·Baron(비밀 진영)의 숨은 정보 칸이 필요하면 v36 |

P2a에 지도자 넷을 넣는 까닭: 4인 판을 차리려면 서로 다른 지도자 넷이 필요하다(`_validate_leader_selection`). 넷은 hook이 적고(셋업 자원,
비용 뒤 뽑기, 원로회 trigger, harvest 조정) 숨은 정보가 없다. 나머지 넷은 막힘 예외(Helena), 비용 할인(Leto), 계속되는 숨은 정보(Paul),
비밀 셋업 결정과 배치 trigger(Baron)라 따로 잰다. P2a 동안 원판 판의 지도자 목록(`content_for(...).leaders`)은 능력이 들어간 넷이고, P2b가
하나씩 더한다. 정의 여덟은 P2a에 모두 넣어 관측의 지도자 어휘가 한 번만 바뀌게 한다.

### 15.2 id (4.2절 7: 같은 인쇄는 같은 id, 다른 인쇄는 새 id)

- **Uprising과 같은 인쇄(같은 정의를 그대로 쓴다):** 칸 `arrakeen`, `imperial_basin`, `secrets`(앱도 두 판이 한 정의를 쓴다, imperium-base.md 8절),
  스타터 덱 10장(P1).
- **이름은 같고 인쇄가 다른 것 → `imperium_` 접두사:** 칸 `imperium_heighliner`, `imperium_hagga_basin`, `imperium_sietch_tabr`,
  `imperium_research_station`, `imperium_high_council`, `imperium_swordmaster`; Conflict `imperium_battle_for_arrakeen`,
  `imperium_battle_for_imperial_basin`, `imperium_secure_imperial_basin`, `imperium_siege_of_arrakeen`; Reserve `imperium_the_spice_must_flow`.
- **원판에만 있는 이름 → 이름 그대로:** 칸 `conspire`, `wealth`, `foldspace`, `selective_breeding`, `hardy_warriors`, `stillsuits`,
  `hall_of_oratory`, `rally_troops`, `mentat`, `carthag`, `the_great_flat`, `secure_contract`, `sell_melange`; Conflict `battle_for_carthag`,
  `cloak_and_dagger`, `desert_power_conflict`(`desert_power`는 Uprising 카드 id라 종류 사이 겹침을 피함), `grand_vision`, `guild_bank_raid`, `machinations`, `raid_stockpiles`, `siege_of_carthag`,
  `skirmish_a`~`skirmish_d`(앱 `SkirmishA`~`D`, 카드면 파일 이름과의 짝은 P0 sweep), `sort_through_the_chaos`, `terrible_purpose`; Reserve
  `arrakis_liaison`; 지도자 `paul_atreides`, `duke_leto_atreides`, `glossu_rabban`, `baron_vladimir_harkonnen`, `count_ilban_richese`,
  `helena_richese`, `earl_memnon_thorvald`, `countess_ariana_thorvald`.
- **종류 사이 겹침을 새로 만들지 않는다:** Foldspace는 칸 `foldspace`, 카드 `foldspace_card`(2026-09-27 사례; `CROSS_KIND_IDS`는 그대로
  `deliver_supplies` 하나).
- 테스트: P1의 `test_content_ids.py`(종류 안 유일·종류 사이 겹침 목록)가 원판 표까지 읽고, 원판 카탈로그에 Uprising 전용 id가 새지 않는다는
  `test_base_game_catalog.py`는 같은 인쇄 셋을 예외로 둔다(`sietch_tabr` 낱말 검사는 Uprising의 고르기 줄 이름으로 좁힌다).

### 15.3 앱에서 읽은 보드 값 (D3)

| 값 | 앱 출처 (로컬) | 값 |
| --- | --- | --- |
| 영향력 4칸 보너스 | `WormFactionTrack::FactionTrackBonusAction`(진영 enum 1~4로 갈림; Emperor는 Uprising 판이 켜져 있으면 Spy, 아니면 `GainUnits<WormTroop>(2)`) | Emperor: troop 2 recruit, Spacing Guild: 3 Solari, Bene Gesserit: Intrigue 1, Fremen: water 1 |
| Alliance token VP | `WormPlayerMatchInitData::.ctor`(`AllianceTokenVP` = 1) | 1 VP(Uprising과 같다) |
| Sell Melange 교환표 | `SellMelangeSpaceAbility`(`2 × spice + 2`, P0 sweep) | spice 2·3·4·5 → 6·8·10·12 Solari |
| Reserve 셋 | `ImperiumArchetypes.BaseSet.*`(`cards-compact.md`) | Arrakis Liaison: 비용 2, Fremen, 아이콘 Landsraad·City, Reveal Persuasion 2, 8장. 원판 The Spice Must Flow: 비용 9, 획득 1 VP, Reveal spice 1, 10장. Foldspace: 아이콘 7개 모두, Agent box 카드 1장 뽑기 + 이 카드 trash, 6장, Persuasion으로 사지 않음 `[FAQ p. 2]` |
| 22칸 값 | `SpaceArchetypes.BaseSet.*` | imperium-base.md 8절 표와 같다(P0 대조) |

카드 셋의 칸 배치는 D1대로 화면 조각(`UI_crd_Imperium_*` prefab)과 한 번 맞춰 본다. 고화질 보드 그림(9절 7, 미룸)을 찾으면 이 표를 그림과
대조한다.

### 15.4 엔진·codec·관측

- **콘텐츠:** `content/imperium/`(보드·보드 능력 기록·Conflict와 보상 기록·Reserve·지도자 정의와 능력 기록). `rulesets._imperium_content`가
  돌려주고, id로 찾는 표(`BOARD_SPACES_BY_ID` 등)는 두 판을 하나로 둔다(14절 1).
- **새 상태(기본값이면 상태 해시에서 빠짐, 옛 저장·기보 그대로):** 좌석의 Mentat 보유(`PlayerState`; 그 라운드 Agent 하나 더 —
  "this round, you may use it as one of your Agents" `[DI p. 18]`), Sort Through the Chaos 승자가 다음 라운드 시작에 받을 Mentat `[FAQ p. 4]`.
  Recall은 Mentat을 먼저 제 칸으로 돌린다 `[DI p. 13]`. Conflict 카드는 승자가 가져가지 않고 보드에 쌓인다 `[DI pp. 8, 12]`(Uprising의 동률과 같은
  자리, OQ-137).
- **새 흐름:** Conflict 보상의 고르기 줄 — "-OR-"(Cloak and Dagger 3위)와 "Choose two"(Battle for Arrakeen 2위, Machinations 1위; 서로 다른 둘을
  먼저 정하고 해결, OQ-114). 지금 지급기는 SEQUENCE만 준다(13.4절). Mentat 보상 아이콘(Sort Through the Chaos). 칸: Mentat(뽑기 + 있으면 가져오기,
  OQ-124), Hall of Oratory(Reveal turn에 그 칸에 Agent가 있으면 Persuasion 1 `[DI p. 17]`), 원판 High Council·Swordmaster(게임에 한 번
  `[DI pp. 17-18]`), Sell Melange(비용 넷), Selective Breeding(trash 비용 → 2장, 공개 선택과 숨은 뽑기는 별개 단계 OQ-106), Foldspace 칸(Foldspace
  카드 획득, 더미가 비면 불발), 원판 Maker 칸(모래벌레 고르기 없음), 무작위 시작 플레이어 `[DI p. 5]`(`first_player_seat_zero`면 좌석 0, OQ-132).
- **원판 + 확장은 P2에서 아직 거절한다:** CHOAM·Bloodlines·Tech·Immortality·Go to 11·Epic·Scouts·Rise of Ix·프로모(P3~P8 몫)를 켠 원판 설정은
  setup이 지금처럼 `NotImplementedError`로 거절한다. 지도자 draft(OQ-007의 6장 풀)는 지도자 여덟이 다 들어오는 P2b 끝부터 연다.
- **codec: v155 그대로.** Uprising 144개 조합의 행 목록은 바이트까지 같다(관문에서 P1의 `catalog_digest.py`로 확인). 원판 카탈로그(지금 73줄)는
  늘어난다. P1이 원판 카탈로그를 만들 때도 번호를 올리지 않았고, 원판 판은 P2 전에 setup이 거절했으므로 원판 저장·기보·체크포인트가 없다. 번호를
  올리면 Uprising 저장(플레이 서버의 진행 중인 판 포함)을 서버가 못 열고 기보에 다리가 필요해 비용만 생긴다. 원판 저장은 화면(P5) 전에는 만들지
  않는다는 전제다(15.7 질문 3).
- **관측: v35 한 번(P2a).** 두 판의 합집합 배치(4.2절 5, 사용자 결정 2026-10-21)에 원판 id를 각 구간 **끝에** 붙인다: 개인 카드(+3), 칸(+19), Conflict
  (+18), 지도자(+8), Reserve 더미(+3), Maker 칸(+2: `imperium_hagga_basin`, `the_great_flat`), 지배 칸(+1: `carthag`), 좌석의 Agent 자리 칸 3 → 4
  (Swordmaster + Mentat), 새 구간 `mentat`(쥔 좌석·제 칸에 있음·다음 라운드에 받을 좌석). Uprising 판의 벡터는 길어지지만 늘어난 열은 0이다.
  형식 2 체크포인트 이관이 (구간, offset)으로 옮기고 새 열은 0에서 시작하므로 옮긴 망은 Uprising 판에서 같은 수를 둬야 한다 — P1과 같은
  방법(`same_moves.py`: older 어댑터·MLP X·엔티티·탐색 좌석)으로 확인한다.
- **`FEATURE_DIGEST`는 바뀐다(지시와 다른 점).** 엔티티 망 어휘가 합집합(`SPACE_IDS`·`PERSONAL_CARD_IDS`·`CONFLICT_IDS`·`LEADER_IDS`)이라 원판 개체가
  들어오면 지문이 반드시 바뀐다. 지킬 것은 "Uprising 개체 하나하나의 특성 행이 그대로이고(열 척도 포함) 옮긴 엔티티 망이 Uprising 판에서 같은 수를
  둔다"이다. 열 척도(열마다 최댓값으로 나눔)가 원판 값으로 바뀌는 열이 있으면(예: 칸 비용 spice 6) 그 열의 Uprising 값이 달라지므로, 관문 전에
  `feature_tables()`의 Uprising 행을 시작 커밋과 대조하고 이관(`retarget_entities`)이 척도 차이를 보정하는지 같은 수 확인으로 본다.
- **같음 확인(200판):** 상태에 새 칸이 기본값으로 생기고 보기(`PlayerView`)에 Mentat 칸이 생기면 P1처럼 선언 차이 파일
  (`scripts/ab/differences/imperium_board.py`)로 적는다. 그 밖의 차이는 0이어야 한다.
- **휴리스틱:** 새 보상(Mentat, Foldspace 획득, Sell Melange 등)의 점수는 원판 콘텐츠에서만 닿는 가지로 두어 Uprising 판의 수가 바뀌지 않게 한다.
  앱 AI는 P6이다(원판 판에서는 쓰지 않음).

### 15.5 규칙 출처와 남은 질문

규칙 동작은 imperium-base.md의 문장으로 정한다: 칸(8절 `[DI pp. 17-18]`), Mentat(9절 `[DI pp. 6, 13, 16, 18]`, OQ-124), 지배(7절 `[DI pp. 10, 16]`),
Combat·Makers·Recall(10절 `[DI pp. 11-13]`), 영향력(6절 `[DI p. 7]`, 값은 15.3), setup(4절 `[DI pp. 4-5]`), 결정 단위(15절), 숨은 정보(14절),
지도자(12절, 판정은 OQ-115·116 등). 커밋 메시지와 테스트에 그 줄을 인용한다.

- **OQ-139(새, 엔진 이유) — Mentat이 어느 말인가.** 쥔 좌석이 Agent를 보낼 때 "Mentat을 보냈는지, 자기 Agent를 보냈는지"를 엔진이 가르지 않고
  그 라운드 Agent 수만 하나 늘린다. P2의 칸·Conflict·지도자에는 이 구분이 드러나는 곳이 없다(Recall은 Mentat부터 제 칸으로 돌리고 나머지를 거둔다;
  Mentat을 제 칸에 보내도 OQ-124대로 뽑기만 한다; 막힘·Maker 보너스는 어느 말이든 같은 그 좌석의 Agent다). 구분이 드러나는 것은 P3 카드
  (Kwisatz Haderach의 Agent 옮기기, Urgent Mission의 Agent recall)이고 그때 이 OQ를 다시 연다. 공식 문장이 정하지 않는 엔진 모델이라 OQ로
  적는다(lessons "엔진 이유").
- 그 밖에 P0 sweep이 "정한 점"으로 남긴 것(Control 보상 marker 부족 C13·OQ-116, Sort Through the Chaos의 Round Start 안 자리 C7, Ariana의 −1 L4,
  Rabban의 "-OR-" L7 등)은 그 근거대로 구현하고 테스트에 적는다. 구현 중 문서가 정하지 않는 것이 나오면 OQ-140부터 적고 묻는다.

### 15.6 소크와 관문

- **원판 소크(P3 전):** 원판 Imperium·Intrigue 덱은 P3 몫이라 비어 있다. 추천은 **빈 덱 그대로** 돌리는 것이다: Imperium Row가 비어 Persuasion은
  Reserve(Arrakis Liaison, The Spice Must Flow)에만 쓰이고, Intrigue 뽑기는 빈 덱·빈 버림 더미에서 아무것도 주지 않는다. 판은 Conflict 덱(10장)이
  다하거나 10점에서 끝난다. 시험 전용 임시 덱은 원판에 없는 카드를 원판 판에 넣는 일이라(스타터·Reserve 복제는 Row 채우기만 시험하고, Uprising
  카드는 Spy·계약 아이콘을 들여온다) 쓰지 않는다. 판 수: 휴리스틱 150 + 무작위 150(지도자 돌려 앉기, codec 왕복 25수마다), 실패 0.
  `dune-imperium-sweep`에 `--base-game imperium`을 더한다.
- **관문(하위 단계마다, AGENTS.md 1층):** pytest `-n 8`·ruff·mypy, 같음 확인 200판 check·record·compare(시작 커밋 `12294215` 기록), 소크 Uprising
  900판(P1과 같은 세 묶음) + 원판(위), 기보 v155 2,000판 exact, 저장본·문제집, tips-v1 재채굴(같은 파일), E2E 전부(메인 체크아웃의
  `scripts/e2e`, `E2E_REPO`), Uprising 144개 조합 codec 행 목록 대조, AI 좌석 같은 수(older·MLP·엔티티·탐색). P1의 `gates_snap.sh`를 이 worktree의
  `tmp/claude/6eb14265/`로 옮겨 쓴다.

### 15.7 조정자에게 묻는 것

1. 15.1의 나눔(P2a에 지도자 넷, P2b에 넷)과 15.2의 id 규칙.
2. 원판 소크를 빈 덱으로 돌리기(15.6).
3. codec v155 그대로 두기(원판 카탈로그만 늘어남, 원판 저장은 P5 전에 만들지 않음).
4. `FEATURE_DIGEST`가 바뀌는 것(지시의 "그대로" 대신 "Uprising 행 그대로 + 같은 수", 15.4).
5. OQ-139(Mentat 말 구분 없음, 엔진 이유, P3에서 다시 엶).
6. P2 동안 원판 + 확장 설정은 거절(15.4).

### 15.8 P2a 결과와 P2b 진행 (2026-10-27, Claude Desktop 세션 `local_7d968935`)

Orca 작업자가 멈춘 P2a(커밋 안 된 30파일)를 이어 받아 끝냈다. 커밋은 브랜치 `jungcheolseung/base-ix-p2`에 있다.

- **P2a `56c8e8c9`:** 15.1의 P2a 행 전부. 원판 4인 판(확장 없음)이 보드 22칸, Mentat, Conflict 18장, Reserve 셋, 지도자 넷(Rabban·Ilban·Memnon·
  Ariana)으로 끝까지 돈다. 이어 받으며 고친 것: codec 카탈로그가 원판 칸에 Uprising 아이콘(계약·연구)을 붙이던 것, Selective Breeding의 trash가
  화살표 비용이 아니던 것(Desert Tactics에 엉뚱한 뽑기를 붙일 뻔함), Foldspace 카드가 엔진의 Reveal 구매에 남아 있던 것(`[DI p. 11]`·`[FAQ p. 2]`,
  OQ-125), 합친 id 표를 도는 Uprising 코드(서버 카탈로그, 관측 id, Esmar Tuek의 codec 행)가 원판을 읽던 것, Reserve 정의의 새 필드가 Uprising
  특성 행을 바꾸던 것(기본값 `False`인 `icon_only`로).
- **지도자 넷의 능력:** Rabban의 Brutality는 "-OR-"가 고르기가 아니다(동맹이 있으면 2, P0 L7) — 자동 Signet의 `ONE_OF`는 조건이 맞는 첫 줄. Ilban의
  Ruthless Negotiator와 Ariana의 Spice Addict는 빚진 뽑기(OQ-106). Memnon의 Connections는 원로회 자리를 얻은 방문의 아이콘 하나(새 행동
  `choose_connections_influence`, 6칸 진영 제외 OQ-060).
- **codec v155 그대로:** Uprising 144개 조합 행이 `12294215`와 바이트까지 같다. 원판 `imperium-4p-base` 카탈로그 580줄(P2b 셋 뒤; P2b 끝 599줄).
- **관측 v35(5,827 int):** 15.4대로. Uprising 판에서 새 열은 모두 0이고, 골든 다이제스트 여섯은 v34 열에서 그대로다. slot 열쇠 1,467(열쇠로 다시
  잇는다), v31 엔티티 파일의 이름은 v35 열쇠·필드를 뺀다. 엔티티 특성의 열 척도는 Uprising 개체로 정한다(`entity_features._table`) — Uprising 405행이
  `12294215`와 열 척도까지 같다(승인 조건). `FEATURE_DIGEST`는 바뀐다(P2b 지도자마다 다시).
- **P2a 관문(15.6, `56c8e8c9` 스냅숏, 2026-10-27 22:05~):** pytest 8,667·ruff·mypy 585, 같음 확인 200판 check(선언한 차이 `imperium_board.py`의
  Mentat 칸만)·compare 200 같음, 소크 Uprising 900 + 원판 300(휴리스틱 150·무작위 150, 지도자 돌려 앉기, codec 왕복 25수마다) 실패 0, Uprising 카탈로그
  144/144, 특성 행 405 차이 0, 기보 v155 2,000판, 저장본 11, 문제집 281·3, tips-v1 재채굴 118곳 같음(머리말의 판 번호만 다름), E2E 70/70(`-j 4`),
  같은 수(시작 커밋 대 `56c8e8c9`) older 12/12·MLP X 12/12·엔티티 12/12·탐색 좌석 4/4. 22:38에 모두 끝.
- **P2b(지도자마다 커밋, 13.4의 측정 — 앞 커밋에서 그 커밋까지의 벽시계; 커밋 메시지의 분 어림은 틀렸다):** Duke Leto `cc5e1962`(약 7분, Signet
  hook 하나·standing 하나), Helena Richese `99dd5ced`(약 6분, Signet hook 하나·standing 하나·행동 하나; P3 전에는 Row가 비어 Manipulate는 빈 확인),
  Paul Atreides `a05a2789`(약 2분, hook 없음; Prescience는 Glowglobes의 덱 맨 위 보기와 같은 경로라 관측 v36이 필요 없다). 독립 리뷰(조정자의 Codex)가 찾은 결함 하나를 `83cf2b1d`에서 고쳤다: 원판 Emperor 4칸의 병력 둘이
  그 turn의 recruit에 들지 않았다(7절 "이번 turn에 recruit한 troop 전부", `[FAQ p. 4]`). 남은 것: Baron Harkonnen(비밀 진영 결정, 의무 공개 OQ-115,
  관측 칸), 지도자 draft(여덟이 모이면), P2b 관문, 문서의 "P2 결과".

### 15.9 P2b 결과 (2026-10-27)

- **Baron Harkonnen `efb1784c`(관측 v36):** Masterstroke — 모든 setup 뒤(draft 뒤에도) 첫 라운드 전에 SETUP에서 멈추고(새 frame `MASTERSTROKE_SETUP`,
  Kota Odax의 Secret Project와 같은 틀) 서로 다른 진영 둘을 비밀로 고른다(`[FAQ p. 1]`, `[DI p. 13]`). 고른 수는 공개, 정체는 본인만(14절). 매 전이 뒤
  배치 최고치를 적은 다음, 자기 turn에 이번 turn 배치한 병력이 동시에 넷 이상이면(Distraction과 같은 최고치, OQ-016; turn 밖은 세지 않음, OQ-063)
  의무 공개, 게임에 한 번, 각 진영 Influence 1(6칸은 불발, OQ-060), 그 뒤 회수는 넷 아래로 못 함(OQ-029) — OQ-115. P2의 원판 판에는 모래벌레·dreadnought가
  없어 그 turn의 유닛 최고치가 곧 병력 수다. **P4(Rise of Ix의 dreadnought)·P7(조합의 모래벌레·Commander)에서 병력·Commander만 따로 세야 한다**(모듈
  `rules/masterstroke.py`에 적음). Scheme은 Solari 1 → Intrigue 1, 뽑을 Intrigue가 없으면 내지 않는다(16절, OQ-071; P3 전 원판 Intrigue 덱은 빔). 숨은
  정보: 보기는 "비밀을 쥠"과 공개 뒤의 진영만, 본인 보기에 진영; 숨은 정보 검사(scramble)는 다른 좌석의 미공개 진영을 바꾸고, AI 정보 표본은 다시 뽑는다
  (그런 좌석만 난수를 써서 다른 판의 표본은 그대로). 관측 v36(5,835): 좌석별 미공개 비밀 4칸, 본인의 진영 4칸, 맨 끝; 새 frame 종류는 `decision_kind`
  slot 필드 끝. 걸린 시간: 앞 문서 커밋에서 약 58분(사용자 답을 기다린 시간 포함; 커밋 메시지의 35분 어림은 틀림).
- **지도자 draft `04f4f0f5`:** 원판 판에서 draft를 연다(여덟 가운데 여섯, OQ-007). draft 전 상태가 그 판의 Maker 장부를 갖게 했다(Uprising은 기본값과 같은
  튜플이라 그대로).
- **지도자 목록:** 원판 판이 여덟 모두를 인쇄 순서로 둔다(Paul, Leto, Rabban, Baron, Ilban, Helena, Memnon, Ariana). 관측의 지도자 어휘는 P2a에서 한 번
  바뀌었고, 특성 지문은 지도자 기록이 들어올 때마다 바뀌었다(Uprising 405행은 늘 그대로).
- **P2b 관문(15.6 + draft한 원판 소크 150, `04f4f0f5` 스냅숏):** pytest를 뺀 모든 단계 통과(같음 확인 200, 소크 Uprising 900·원판 450, 카탈로그
  144/144, 특성 405행, 기보 2,000, 저장본·문제집, tips, E2E 70/70, 같은 수 4종). pytest 20개 실패는 모두 테스트 쪽이라 `4885be0f`에서 고쳤다(worklog).
  병합 후보는 그 뒤의 HEAD다.
- **P3에 넘기는 것:** 원판 Imperium·Intrigue 덱(빈 덱 동안 Helena의 Manipulate는 빈 확인, Baron의 Scheme은 내지 않음), OQ-139(Kwisatz Haderach·Urgent
  Mission에서 Mentat 말 구분), Masterstroke의 병력 셈(P4·P7), 화면(P5)의 Mentat·Masterstroke 표시와 공개의 되돌리기 경계, AI(P6)의 원판 판 점수.


## 16. P3 계획 초안 (2026-10-28, 브랜치 `claude/base-ix-p3`, master `60c2fcfb`에서)

**상태: 초안.** 사용자 지시(조정자 경유, 2026-10-28 00:5x) "P3는 계획 초안·도구 시범·시범 전사 5장까지만". 이 절의 결정은 모두 추천이고 16.8의
질문에 사용자가 답하기 전에는 카드 묶음 전사를 시작하지 않는다. 범위는 8절 표의 P3: 원판 Imperium 43종 67장, Intrigue 34종 40장, 프로모 3장
(Duncan, Loyal Blade·Jessica of Arrakis·Thumper, `promo_cards` 뒤, 9절 8). 끝의 모습: 원판 판이 두 덱으로 끝까지 돌고(소크), 앱 속성 표와 기계 대조
0 차이, P3 끝 앱 행동 대조(10.4절 1)의 차이를 모두 판정.

### 16.1 하위 단계

| 단계 | 내용 | codec | 관측 |
| --- | --- | --- | --- |
| **P3a 틀** | 80장(Imperium 43·프로모 3·Intrigue 34)의 정의를 앱 속성 표에서 생성(도구 1: 이름·장수·비용·진영·Agent 아이콘·Reveal 값·획득 보너스), id, 덱 연결(`play_data_complete`인 카드만 덱에 — 정의는 다 있어도 효과가 없는 카드는 덱에 안 넣는다), `archetypes.py`와 기계 대조 pytest(9절 4), 화면 조각과 P0 카드면 읽기의 한 번 대조(D2), 시범 5장(16.7) | v155 그대로(원판 카탈로그만 늘어남, 15.4와 같은 이유) | **v37 한 번**: 개인 카드 +46, Intrigue +34를 구간 끝에(P2a의 지도자처럼 정의를 한 번에 넣어 어휘가 한 번만 바뀌게) |
| **P3b Imperium** | 나머지 Imperium 41장 + 프로모 3. 갈래 둘(16.7 측정으로 정함)에 card-implementer, 합친 뒤 관문 | 그대로 | **v38(2026-10-28):** 덱 위 공개 카드(OQ-145)·The Voice 봉쇄·Infiltrate·Recruitment Mission 표시를 끝에 |
| **P3c Intrigue** | 나머지 Intrigue 32장. Endgame 셋·Combat 창·Plot 시점 | 그대로 | 그대로 |
| **P3d 끝** | 원판 두 덱 소크, 원판 전부의 앱 행동 대조(10.4절 1; 디컴파일러는 그 전에 다시 묻는다, D4-3 (나)), P2에서 넘어온 확인(16.5) | – | – |

**병합 시점(2026-10-28 사용자, 조정자 경유 "B. E7 AI 가치망 측정 / 이거 빼고 나머지는 추천대로"):** 남은 여섯 장(Mentat 셋, 프로모 셋), 화면 둘(덱 위
공개 카드; Mentat 말 모양은 사용자 답 뒤), P3d까지 끝낸 뒤 master에 한 번 합치고, 그 병합 커밋에서 codec을 v156으로 올린다(16.4). 옛 기록(사람 판
저장, 문제집)을 새 버전으로 바꿔 쓰고 옛 다리를 지우는 정리는 P3 병합 뒤 따로 한다 — P3에서는 `records/migration.py`에 다리를 더하지 않는다.

단계마다 엔진 관문 전체를 돈다(2026-10-20 사용자 결정, 15.6과 같은 묶음). E7b 같은 학습이 CPU를 잡는 동안은 표적 테스트만 `-n 2`로 돌리고
관문은 게시판에 예약한다(2026-10-28 조정자 제한).

### 16.2 id (4.2절 7)

- 원판 Imperium·Intrigue 80장의 이름은 지금 어느 Imperium·Intrigue 카드 id와도 같은 종류 안에서 겹치지 않는다(2026-10-28 스크립트) — 모두 이름
  그대로(`arrakis_recruiter`, `bribery` …).
- **종류 사이 겹침을 새로 만들지 않는다**(15.2의 `foldspace_card`): 다른 종류가 쓰는 이름 일곱은 `_card`를 붙인다 — Uprising Intrigue `crysknife`와
  겹치는 `crysknife_card`, Uprising·Bloodlines 지도자와 겹치는 `chani_card`, `duncan_idaho_card`, `gurney_halleck_card`, `lady_jessica_card`, `liet_kynes_card`,
  `piter_de_vries_card`. 생성기(`scripts/dwgr/imperium_entries.py`의 `ID_OVERRIDES`)가 정하고, 덱이 연결되면 `test_content_ids.py`가 지킨다.

### 16.3 출처 (D1·D2, 2.4절)

- **앱 자료만.** 숫자·아이콘·장수·진영은 속성 표(도구 1, 생성), 효과는 카드별 화면 조각(2.2 4)과 영어 문구. 카드면 스캔은 새로 읽지 않는다.
  화면 조각을 초안으로 바꾸는 변환기(D4-2)를 16.6에서 시범했다.
- **화면 조각이 없는 카드:** 원판 프로모 셋은 카드 전용 prefab이 없다(일반 `UI_crd_Imperium` 틀이 문구로 그린다). 셋은 속성 표 + 영어 문구로 쓴다.
  **예외(2026-10-28 사용자, 조정자 경유):** "앱 자료로 부족하면 dunecardshub의 이미지를 직접 읽어야지" — 이 셋에 한해, 속성 표와 영어 문구로
  정해지지 않는 부분은 https://dunecardshub.com 의 카드 이미지를 직접 읽어 정한다(AGENTS.md "원판·Ix는 카드면을 읽지 않는다"(2026-10-21)의 예외).
  Intrigue는 34장 모두 전용 prefab이 있다.
- **D2 한 번 대조:** 화면 조각을 P0 블라인드 읽기(에셋 `…/p0-readings/faces/`)와 스크립트로 한 번 대조하고 다른 카드만 사람이 본다. 변환기 시범의
  나란히 표(16.6)가 그 대조의 첫 판이다: 아이콘·숫자가 다른 카드 0장(Duncan Idaho의 검은 P0가 이미 앱 쪽 2로 고쳐 둠).
- **규칙 근거는 공식 문서.** 순서·may/must·시점이 화면 조각과 문구로 정해지지 않을 때만 능력 클래스를 읽고, 공식 문서가 답하지 않으면 OQ-140부터.
  P0 sweep(`…/p0-readings/sweep/base-imperium.md`, `intrigue.md`)이 카드마다 근거를 단 "merged effect"를 이미 갖고 있어 전사 agent의 입력이 된다.
- **한국어:** 공식 한글판 카드 사진이 있는 카드만(9절 6, 찾기는 미룸). 없으면 영어 이름·영어 앞면.

### 16.4 엔진·codec·관측

- **콘텐츠:** `content/imperium/imperium.py`(Imperium·프로모 정의), `content/imperium/intrigue.py`, 능력 기록은 Uprising과 같은 표(`agent_abilities`·
  `reveal_abilities`·`trigger_abilities`·Intrigue의 `IntrigueOption`)에 원판 항목을 더한다. `rulesets._imperium_content`가 `imperium_cards`·
  `imperium_deck_instance_ids`·`intrigue_deck_instance_ids`를 채운다(지금 빈 튜플).
- **P0 분류(dsl-coverage):** 원판 Imperium 86칸 중 기존 모양 74(값만 19), 새 조각 12(변형 5), hook 0; 원판 Intrigue 41절 중 기존 24, 새 17(변형 5).
  hook이 될 위험 칸(The Voice, Kwisatz Haderach, Mentat, harvest 조정, 적 Agent 무시)은 P2에서 엔진 쪽 일부가 이미 생겼다(Mentat, Helena의 막힘 예외).
  새 조각 후보: 버려질 때 trigger(Assassination Mission), harvest 두 배(Carryall 기본·Thumper 보너스), "다른 Bene Gesserit 카드가 in play"(Bond와 같은지
  P3a에서 대조), Fremen 카드 수만큼 Persuasion(Liet Kynes), TSMF 할인(Guild Bankers), 상대마다 고르기(Test of Humanity), Endgame 셋(Corner the Market은
  OQ-123, Plans Within Plans, Tiebreaker의 Combat/Endgame 나뉜 카드), 덱 맨 위 보고 뽑거나 버리기(Poison Snooper, 숨은 정보), 버림 더미를 덱에 섞고 뽑기
  (Refocus, chance).
- **codec v155 그대로:** 원판 카탈로그만 늘어난다(15.4의 이유 그대로: 원판 저장·기보·체크포인트가 아직 없음). Uprising 144개 조합 행은 바이트까지 같다.
  **2026-10-28 사용자 판정 "병합 때 한 번":** OQ-145가 Uprising + Immortality 판의 상태(덱 위 Tleilaxu 카드의 `deck_public_top`·`hand_public`)를 바꿔, v155에서 만든
  그런 판의 저장은 해시가 맞지 않게 된다. 그래서 브랜치 안에서는 v155 그대로 두고, P3를 master에 합칠 때 v156으로 한 번 올린다(상수, 버전 고정 테스트,
  필요하면 v155 기록을 받는 경로를 한 커밋으로; 병합한 트리의 pytest·ruff·mypy로 확인). 카탈로그는 그대로다.
- **관측 v37 한 번(P3a):** 개인 카드·Intrigue 구간 끝에 원판 id. Uprising 열은 그대로(늘어난 열 0), 형식 2 이관으로 옮긴 망이 Uprising 판에서 같은 수
  (P2처럼 `same_moves.py`). 엔티티 특성은 Uprising 개체로 척도를 고정해 Uprising 405행이 그대로(P2a의 `entity_features._table`). 숨은 정보가 새로
  생기는 카드(Poison Snooper의 엿보기)는 `known_card_seats`·scramble·결정 표본에 함께 넣는다(10.1).
- **같음 확인:** 상태에 새 칸이 생기면 선언 차이 파일(`scripts/ab/differences/`). Uprising 판의 그 밖의 차이는 0.
- **휴리스틱:** 새 효과의 점수는 원판 콘텐츠에서만 닿는 가지(15.4와 같은 방식). 앱 AI는 P6.

### 16.5 P2에서 넘어온 것 (15.9)

- **Helena의 Manipulate:** 덱이 비어 있던 동안은 빈 확인이었다. Row가 차면 Row 카드 따로 두기·나중에 사기를 확인하는 테스트를 더한다.
- **Baron의 Scheme:** Intrigue 덱이 비면 내지 않았다(16절, OQ-071). 덱이 생기면 Solari 1 → Intrigue 1 지급과 버림 더미 섞기 경로를 테스트한다.
- **OQ-139(Mentat 말 구분 없음):** Kwisatz Haderach(Agent 하나를 아무 칸으로), Urgent Mission(Agent recall), Calculated Hire(Mentat 가져오기)에서 다시
  연다. 엔진은 Mentat을 따로 세지 않으므로 "Mentat을 옮기거나 recall할 수 있는가"를 사용자에게 묻는다(16.8 4).
- **Masterstroke의 병력 셈:** P4(dreadnought)·P7(모래벌레·Commander) 몫. P3 카드(Gun Thopter·Sardaukar Legion·Rapid Mobilization·Reinforcements의 garrison에서
  배치, Double Cross의 공급에서 배치)가 "이번 turn 배치"에 드는지만 확인한다(OQ-115: 배치한 병력을 셈).
- **끝(2026-10-28 오후, `33e27918`):** 위 셋을 원판 덱으로 확인했다 — Helena의 따로 두기·채우기·1 적게 사기·안 사면 제거, Scheme의 덱 맨 위·빈 덱의
  버림 더미 섞기, Masterstroke가 Reinforcements 3 + Gun Thopter 1, Rapid Mobilization 4로 공개(Legion·Double Cross는 이미 셈 테스트). 엔진 변경 없음.
- **화면(P5)·AI(P6)** 몫은 그대로 넘긴다.

### 16.6 도구 시범: 화면 조각 → 능력 기록 초안 (D4-2, 2026-10-28)

`scripts/dwgr/app_pieces.py`: 카드 prefab의 활성 노드에서 칸(Agent·Reveal·획득·버려질 때·Intrigue 본문)마다 아이콘 스프라이트·숫자·화살표·글을
읽어 우리 DSL 이름으로 초안을 쓴다. 모르는 조각과 문장은 `TEXT(...)`로 넘긴다(추측하지 않음). 앱이 실행 중에 문구에 넣는 아이콘(Gene Manipulation의
"in play: {Spice_2}")은 영어 문구에서 채운다. 출력은 git 밖(`tmp/`).

**정확도(P0 카드별 전사 자료의 face·merged effect와 한 장씩 대조, 80장):**

| | 그대로 맞음 | 문장이 남음(TEXT, 사람·agent 몫) | 고쳐야 함 | prefab 없음 |
| --- | --- | --- | --- | --- |
| 첫 판 Imperium 43 | 21 | 16 | 6 | – |
| 첫 판 Intrigue 34 | 12 | 21 | 1 | – |
| 둘째 판 Imperium 43 | 25 | 18 | 0 | – |
| 둘째 판 Intrigue 34 | 12 | 21 | 1 | – |
| 프로모 3 | – | – | – | 3 |

- 첫 판의 "고쳐야 함" 7장은 모두 구조였다: 맨 진영 아이콘을 Alliance로만 읽음(Smuggler's Thopter·Worm Riders의 "2 Influence :"), "Alliance :" 글이
  남음(Firm Grip·Guild Ambassador), 실행 중에 문구에 들어가는 아이콘이 빠짐(Gene Manipulation의 spice 2, Guild Bankers의 Persuasion 3), Combat/Endgame으로
  나뉜 카드를 고르기로 읽음(Tiebreaker). **아이콘·숫자를 잘못 읽은 것은 0.** 둘째 판에서 앞의 셋을 고쳤고 Tiebreaker만 남았다. 둘째 판은 같은 80장으로
  고친 것이라 과적합일 수 있다 — P4의 Ix 카드가 처음 보는 시험이 된다.
- "그대로 맞음"은 초안이 P0 기록과 같은 조각·숫자·구조(비용 화살표, -OR-, 조건)를 가진다는 뜻이다. may/must·별도 단계·OQ 같은 규칙 쪽 표시는 초안이
  아니라 기록 helper(`_pay`·`_trash`·`_icons`)와 전사 agent가 붙인다.
- 문장이 남는 카드는 대부분 새 조각 후보(16.4)와 같은 카드다: 초안이 덮는 것은 아이콘 칸이고, 새 규칙은 어차피 사람이 쓴다.
- **Rise of Ix(P4 몫) 미리 보기:** 같은 도구를 Ix 46장에 돌리면 40장에 TEXT가 남고, 원판 카드에 없던 스프라이트 이름 10종이 모르는 조각으로 나온다
  (Discard 9, `UI_Icon_crd_freighter` 8, Unload 7, Troop 5, Water 4, `Icon_Dreadnought` 3, `Icon_buytech` 2, `Icon_TechCost_Reduce` 2, WildRankUp 1, VictoryPoint 1 —
  Ix prefab은 `ActionIcon_` 없는 이름을 쓴다). P4에서 어휘를 넓힌 뒤 처음 보는 시험으로 잰다.
- 들인 것: 벽시계로 약 7분(00:59 worktree 준비 ~ 01:06, 계획 읽기 포함 — 도구 호출이 빠른 일), 대조 표 읽기 약 2.4만 토큰.
- **추천:** 채택. 전사 agent에게 그 카드의 초안 줄을 P0 merged effect와 함께 준다. 고친 수를 16.7에서 잰다.

### 16.7 시범 전사 5장과 갈래 나누기 (D5, 11절 4; 2026-10-28 01:15~01:44)

틀(`5cbfcca1`: 빈 원판 카드 표, 합친 조회 표, 관측·덱은 그대로)에서 card-implementer(Sonnet) 둘을 갈래마다 worktree 하나씩 동시에 돌렸다.
갈래는 종류로 나눴다: Imperium 셋(`claude/base-ix-p3-imperium`), Intrigue 둘(`claude/base-ix-p3-intrigue`). agent마다 그 카드의 변환기 초안 줄,
P0 merged effect의 자리, 규칙 인용을 줬다.

| 카드 | 벽시계 | 변환기 초안과의 차이 |
| --- | --- | --- |
| Arrakis Recruiter | 11.4분(첫 카드, 틀 읽기 포함) | 조각·숫자 그대로. Agent box 효과 값 하나(`RECRUIT_ONE_TROOP`)를 enum 끝에 더함 |
| Spice Smugglers | 5.4분 | 조각 그대로 + 화살표의 OPTIONAL 표시. 지불 실행기가 Influence 보상을 몰라 `apply_payment`에 더함(공유 코드) |
| Gun Thopter | 10.5분 | TEXT 둘을 기존 조각의 변형으로: `EachOpponentLosesTroop(garrison_only=True)`(손실 창이 garrison만 보임, garrison이 빈 상대는 영향 없음 `[FAQ p. 2]`)과 Reveal 고르기 `MAY_DEPLOY_ONE_TROOP`(Shadout Mapes 기록의 배치 반쪽). 손실 창·Reveal 고르기·codec 행(원판 카탈로그에서 아직 뺌)을 고침 |
| Bribery | 8.5분(첫 카드) | 그대로(감싸기만) |
| Master Tactician | 3.8분 | ONE_OF → 배타 option 둘(OQ-058), TEXT → `RetreatTroops(0, 3)`("up to"는 0 허용 `[FAQ p. 3]`), 표시 문구 "Retreat up to 3 troops" |

- **토큰:** Imperium agent 39.2만(도구 162번, 28.7분), Intrigue agent 19.1만(64번, 12.7분). 카드당 평균 약 11.7만(Imperium 약 13만, Intrigue 약
  9.5만). 계정 주간 사용량은 시범 앞뒤로 58% 그대로(5시간 창 2→4%) — Sonnet agent 토큰은 주간 한도에 거의 닿지 않았다.
- **변환기 초안을 고친 횟수:** 5장 가운데 아이콘·숫자를 고친 것 0. 초안을 그대로 쓴 것 3(감싸기·표시만), TEXT를 조각으로 바꾼 것 2(Gun Thopter 둘,
  Master Tactician 하나). 구조를 바꾼 것 1(Master Tactician의 ONE_OF를 배타 option으로 — 같은 뜻).
- **갈래 합치기(11절 4):** 충돌 **0**. Imperium 갈래 19파일, Intrigue 갈래 3파일, 둘 다 고친 파일은 `display/effect_dsl_text.py` 하나(다른 자리라 자동
  합침). Imperium agent가 미리 짚은 위험: 같은 종류 갈래 둘이면 enum 끝과 기록 수를 고정한 테스트(`test_agent_box_abilities.py`)에서 충돌한다 — 그래서
  갈래는 종류로 나누고 같은 종류 둘을 동시에 돌리지 않는다.
- **합친 뒤 내가 본 것:** Uprising codec 카탈로그 144개 차이 0, Uprising 특성 405행 차이 0, 관측 구간·`FEATURE_DIGEST`가 P2 끝과 같음(`catalog_digest.py`·
  `compare_features.py`). 표적 테스트 1,404개 통과(`-n 2`). 실수로 전체 테스트를 `-n 2`로 돌려(10분, 8,704개) agent가 못 본 실패 둘을 찾았다: 서버 카탈로그
  테스트가 합친 표를 돌던 것, Gun Thopter의 새 안내 문구 둘에 한국어가 없던 것(`de488de7`). 교훈: agent의 표적 테스트에 `tests/server`의 카탈로그·i18n을
  넣는다.
- **리뷰에서 남긴 것:** Spice Smugglers의 지불이 Solari 사건을 Influence 사건보다 먼저 낸다(인쇄는 Influence 먼저). 결과는 서로 기대지 않으나 원칙대로라면
  인쇄 순서다 — 다음 묶음 전에 실행기를 인쇄 순서로 고칠지 본다. Gun Thopter의 Reveal 배치 "may"는 카드 문구(앱)가 근거이고 규칙 문서에 따로 줄이 없다.
- **어림(남은 69장: 80 − 시범 5 − 프로모 3 − OQ-139 셋):** 카드당 약 7분·12만 토큰이면 agent 둘로 약 4~5시간, agent 토큰 약 800만. 새 조각이 필요한
  카드(16.4)는 이보다 길다.
- **추천:** 변환기 채택(초안 줄을 agent 입력에), 갈래 나누기 채택(종류별 둘), 첫 카드의 틀 읽기 비용을 줄이려고 agent 하나가 같은 종류 카드 여러 장을
  이어서 맡는다.

### 16.8 사용자에게 묻는 것

1. **하위 단계(16.1):** P3a 틀(80장 정의 생성·관측 v37 한 번·덱은 효과가 들어간 카드만) → P3b Imperium → P3c Intrigue → P3d 끝.
2. **codec v155 그대로·관측 v37 한 번(16.4).** v37은 플레이 서버의 망·어댑터 좌석이 Uprising 판에서 같은 수를 두는지 P2처럼 확인한 뒤 병합한다. **바뀜(2026-10-28 사용자 "병합 때 한 번"):** codec은 master 병합 때 v156으로 한 번 올린다(16.4). 관측은 v37 뒤 v38 한 번 더(덱 위 공개 카드·The Voice·Infiltrate·Recruitment Mission, 16.1).
3. **프로모 셋은 prefab이 없어 속성 표 + 영어 문구로 전사(16.3).** D1(앱 자료만) 안이지만 화면 조각 확인이 없는 카드라 따로 묻는다.
4. **OQ-139 다시 열기(16.5):** Kwisatz Haderach·Urgent Mission·Calculated Hire에서 Mentat을 옮기기·recall할 수 있는가. 공식 문장과 앱 처리를 붙여 OQ로 묻는다.
5. **변환기 채택(16.6)과 갈래 나누기(16.7의 측정 뒤).**
6. **P3d의 앱 행동 대조 전에 디컴파일러(D4-3 (나)) 내려받기를 다시 묻는다.**
7. **관문 일정:** E7b 같은 학습이 끝난 뒤 P3a 관문을 돈다(게시판 예약).

### 16.9 카드 묶음이 멈춘 곳: 새 엔진 조각 (2026-10-28 밤, 조정자 경유 "설계하고 OQ마다 적고 16에 기록")

card-implementer는 기존 조각으로 안 되는 카드를 건너뛰고 빠진 것을 보고한다(멈춤 규칙). 조각마다 근거와 상태:

| 조각 | 카드 | 근거 | 상태 |
| --- | --- | --- | --- |
| `DeployTheseTroops`(Reveal turn에 이 줄이 recruit한 병력 배치) | Reinforcements, Gurney Halleck | 카드 문구, `[DI p. 10]` `[FAQ p. 4]`, OQ-030 | 구현 `ce6deec6`, 2026-10-28 사용자 판정으로 고침: 그 카드로 소집한 병력과 뒤에 채워진 그 카드의 부족분(이 카드들 몫 먼저)만 배치, 다른 효과의 recruit는 안 듦 — OQ-140 DECIDED |
| `DeployFromGarrison(up_to=None)`("any number") | Rapid Mobilization | 카드 문구, `[FAQ p. 3]` | 구현(Intrigue 묶음 2); garrison의 Commander도 배치한다(`DeployFromGarrison`의 기존 처리, `[Bloodlines p. 4]`) |
| 조건 `MoreSpiceMustFlowThanEachOpponent`, `InfluenceAtLeastOnTracks` | Corner the Market, Plans Within Plans | imperium-base.md 13.2, OQ-123, `[FAQ p. 2]` | 구현(명세는 내가; `SpiceMustFlowCardsAtLeast`가 원판의 The Spice Must Flow도 세게 고침) |
| 획득 상자 아이콘 줄(아이콘마다 차례의 줄, 순서는 소유자) | CHOAM Directorship(고정 진영 넷), Lady Jessica(고른 진영 하나) | OQ-027·OQ-112 원칙의 확장 — OQ-141(판정 2026-10-28 사용자: 구현대로) | 구현(`rules/acquire_icons.py`, 행동 `resolve_acquire_icon`): 자기 차례 안에서는 차례의 줄(OQ-112 (4) 선례), 고를 진영이 모두 6이면 회색으로 기다리다 누름에 사라짐(차례 안 선례), 고정 진영 6은 얻는 것 없는 의무 줄. 자기 차례 밖 획득(Scouts의 Critical Moment: Uprising + 원판 카드 + Scouts는 P7, 원판의 Scouts는 P8)은 OQ-141 조합대로 획득한 자리의 창 — 그 조합을 열 때 구현, 그때까지 `NotImplementedError` |
| 승자의 창에서 내는 Intrigue("When you win a Conflict:") | To the Victor..., Demand Respect | OQ-121 판정 6("쥐고 있고 조건·비용을 갖췄을 때 낼 수 있는 줄이다. 안 내도 창이 닫힌다"), `[DI p. 13]`(보상 spice로 낼 수 있음) | 구현; 닫기 줄의 숨은 정보 처리는 OQ-142(사용자 확인 대기; 숨김은 카드를 읽어 섞인 덱·어느 판에서든 같음). 휴리스틱·앱 AI는 이 카드를 내지 않는다(P6) |
| 덱 맨 위로 획득 | Bypass Protocol(B), Recruitment Mission(획득마다 위/버림) | 카드 문구, `[FAQ p. 3]`, OQ-125, OQ-145(판정 2026-10-28 사용자 (나)) | 구현 `92b5046b`(`AcquireCardUpTo.to_deck_top`, Reveal turn 획득마다 `to_deck_top` 쌍둥이 행, Tleilaxu 덱 위 조건 확장; 놓은 뒤 획득 상자). 덱 위 카드는 모두가 앎·뽑은 뒤 손에서 공개(OQ-145) — 관측 v38과 함께 |
| 상대 하나 지정 Conflict 손실 + supply에서 배치 | Double Cross | 카드 문구, `[FAQ p. 2]`(상대 troop이 있어야 낸다) | 구현(`OpponentHasTroopInConflict`, `OpponentLosesTroop`, `DeployFromSupply`; 빈 supply는 OQ-042 (2)의 부족분 기록). 잃는 쪽엔 Commander가 든다(`[Bloodlines p. 4]`); supply 배치는 troop만 — OQ-144(사용자 확인 대기) |
| 덱 맨 위 보고 뽑기·trash | Poison Snooper | 카드 문구, `[FAQ p. 3]`, imperium-base.md 14 | 구현(`PeekTopCard(draw_or_trash=True)`, Controlled의 `peeked_card_id` 길) |
| 버림 더미를 덱에 섞고 뽑기 | Refocus | 카드 문구, `[FAQ p. 3]` | 구현(`ShuffleDiscardIntoDeck`, 뽑기 섞기 frame을 다시 씀) |
| 이번 turn 적 Agent가 막지 않음 | Infiltrate | 카드 문구, OQ-113 (C), P0 sweep S15 | 구현 `a80be9ca`(`enemy_agents_ignored_turn`, Eyes Everywhere와 같은 자리 — Spy 회수 행 없음, 자기 Agent·요구·The Voice는 그대로 막음); 관측 v38 |
| 상대별 다음 배치 봉쇄 | The Voice | OQ-116(판정 B), imperium-base.md 13.1 | 구현 `a80be9ca`(`voice_blocked_space_ids`, 다음 배치나 라운드 끝에 풀림, 무엇으로도 못 넘음); 관측 v38 |
| turn 시작 뽑기 + 선택형 pass | Bindu Suspension | OQ-117 | 구현(`PassTurn(optional=True)`); 이어 가기 뒤 다른 시작 카드는 OQ-143(판정 2026-10-28 사용자: 구현대로 — Bloodlines의 Litany Against Fear·Withdrawn과 한 표시) |
| Mentat 셋 | Kwisatz Haderach, Urgent Mission, Calculated Hire | OQ-139 (가) 유지(2026-10-28 사용자), imperium-base.md 9·13.1·16 | 구현: Kwisatz `0e9ce20f`(빈 Leader로도 Agent turn, 보드의 자기 Agent를 `from_space`로 옮김, 아이콘·점유 무시, 비용·요구·한 번만·The Voice는 지킴; 자기 Agent 둘이 한 칸에 설 수 있음), Urgent Mission·Calculated Hire `2883b808`(빈 Leader에서 Plot 창으로 Agent turn이 다시 열림; Mentat 칸 효과를 풀기 전에 Calculated Hire로 가져가면 그 효과는 사라짐 — 조건은 해결할 때, OQ-028·OQ-057 (1)); 같은 칸 둘의 회수 줄 겹침 고침 `761cba10`. 화면은 (가) 규칙으로 좌석 패널에 Mentat 자리 `98465c26`(보드 위 말은 P5) |
| 프로모 셋 | Duncan, Loyal Blade·Jessica of Arrakis·Thumper | 16.3(앱 속성 표 + 영어 문구로 충분, 이미지 안 읽음) | 구현 `51f44a9f`(Duncan의 trash 줄은 한 방향·몇이든·Commander 포함, Jessica의 두 뽑기는 아이콘마다 BG 조건, Thumper는 보너스 spice만 두 배); 원판도 `promo_cards`를 받음 |

Imperium 묶음에서 아직 멈추지 않은 새 모양 후보(16.4): harvest 두 배(Carryall), Power Play, Test of Humanity, The Voice(OQ-116), Guild Bankers.

Imperium 묶음 2(2026-10-28 03:09~04:2x)가 멈춘 곳:
- **Firm Grip:** Agent box 화살표 비용이 Solari이고 보상이 세 진영 중 고르기 — Agent box 지불은 water·spice·specimen만, 무장 아이콘에 Influence 없음.
- **Shifting Allegiances:** Agent box 화살표 비용 `LoseInfluence`(대상) + spice → 한 진영 Influence 2.
- **Sardaukar Legion·Scout·Chani:** Reveal turn에 수를 고르는 병력 이동(garrison에서 셋까지 배치, 둘까지·몇이든 퇴각). 열린 질문: Commander도 "troop"인가
  `[Bloodlines p. 4]`, Combat 아이콘의 garrison 둘과 어떻게 합치는가.
- **Other Memory:** 버림 더미의 Bene Gesserit 카드를 손으로(공개 경로의 손 카드, OQ-010).
Imperium 묶음 3(04:41~06:12): Guild Bankers(`ReserveCostDiscount`), Carryall(`DoubleBaseHarvestSpice`), Power Play(Subversive Advisor의 상자),
Test of Humanity(`EachOpponentDiscardsOrLosesDeployedTroop`, Covert Operation 창에 손실 줄), Sardaukar Legion·Scout·Chani(수를 고르는 Reveal 병력 이동;
Commander는 16.10 1에서 넣음), Firm Grip(Solari 화살표 + 고른 진영) 구현. 멈춘 곳: Shifting Allegiances(Agent box의 대상 비용 + 한 진영 2), Other Memory(버림 더미의
Bene Gesserit 카드를 손으로, OQ-010), The Voice(상대별 다음 배치 봉쇄 상태, 관측 변경). 문서가 말하지 않는 가장자리: 같은 Reveal에서 Guild Bankers를 나중에
trash해도 이미 연 할인은 남는다(구현).
Imperium 마지막 둘(06:21~06:53): Shifting Allegiances(Agent box의 Influence 잃기 화살표 `influence_loss_box`, 한 진영 +2), Other Memory
(`TakeCardFromDiscard`, 버림 더미의 Bene Gesserit 카드를 `hand_public`으로 손에 — OQ-010) 구현. 남은 것: Firm Grip의 `pay_agent_card_solari`가
`graft_boxes.BOX_ACTION_IDS`에 없어 원판 + Immortality의 접합 차례에서 막혔다(16.10 2에서 고침).
휴리스틱은 새 행(`lose_agent_card_influence`, `take_agent_card_from_discard`, Bindu의 pass, 승리 책략)을 고르지 않는다 — P6.
- **Uprising Tread in Darkness(2026-10-28 확인, 동작 변경 없음):** 이 메모가 걱정한 "Bond가 깨져도 trash는 남는다"는 사실이 아니었다 — 두 아이콘
  모두 Bond로 걸리고 해결할 때 판정하며, 깨지면 회색으로 기다리다 턴 종료에 사라진다(OQ-028 "다시 확인"). `_WAITING_ICON_BOXES`는 조건 있는 아이콘과
  조건 없는 선택 아이콘이 섞인 상자(Gene Manipulation)에만 필요하다. Gene Manipulation의 순서 자유는 사용자 판정(같은 날, OQ-028 적용).

### 16.11 디컴파일러 시범 (D4-3 (나), 2026-10-28 저녁)

사용자(조정자 경유) "확실히 도움된다면 디컴파일러 써보지 뭐", 이 세션에서 "디컴파일러 내려받기 시작해"·"Download JDK 25". 내려받은 것: Ghidra 12.2
(`ghidra_12.2_PUBLIC_20261016.zip`, 569,712,708바이트, NationalSecurityAgency/ghidra 공식 release, SHA-256 릴리스 페이지와 같음), Temurin JDK 21.0.13
(약 200MB, 공식 체크섬과 같음; Ghidra 12.2는 Java 25 이상을 요구해 쓰지 못함), Temurin JDK 25.0.5(136,446,056바이트, 공식 체크섬과 같음). 설치는 P3
worktree의 `tmp/claude/2719085b/decompiler/`, 릴리스에 macOS용 디컴파일러 본체가 없어 같이 든 C++ 소스를 이 Mac의 make·clang으로 빌드했다(x86_64,
Rosetta로 돎; 더 내려받은 것 없음). Ghidra의 사용자 설정·임시 파일도 프로젝트 `tmp/`로(launch.sh를 거치지 않는 `headless.sh`). 앱에서 나온 것(x86_64
바이너리 사본, Ghidra 프로젝트, C 결과)은 assets의 git 무시 `reference/dune-steam-app/<build>/ghidra/`에만.

방법: 분석 없이 가져온 뒤(`-noanalysis`, 74초, 1.3GB) 우리 표로 이름을 붙임 — `methods.tsv`의 함수 이름과 기존 asm 주석의 메타데이터 전역(`MethodRef:`,
`TypeInfo:`, `Str:` 등) 198,148개 — 그리고 답을 아는 네 함수만 디컴파일해 기존 주석 asm과 견줌.

| 함수 (이미 아는 답) | asm | C | 답이 C에서 보이는가 |
| --- | --- | --- | --- |
| UrgentMissionAbility::Cost (`HasDeployedAgents(1)`) | 26줄 | 19줄 | 예 — `new HasDeployedAgents(…, 1)`로 바로 읽힘 |
| SpaceAbility GrantResources MoveNext (Carryall 기본·Thumper 보너스) | 1,731줄 | 1,007줄 | 예 — 로그 키로 두 가지를 찾고 더하기가 보임; 필드는 오프셋 숫자 |
| PlayerTurnPhase Cleanup MoveNext (The Voice 막힘 해제, OQ-116) | 9,841줄 | 5,434줄 | 반만 — asm 주석이 푸는 정적 필드 이름(`WormAttributes.BlockExceptions`)이 C에선 `+ 0x878` 숫자 |
| UrgentMissionAbility::GetTargets | 75줄 | 1,626줄 | 아니오 — 분석 없이 만든 함수 경계가 이웃 코드까지 넘어감 |

첫 판단(같은 날): **아직 "확실히 낫다"가 아니다.** 큰 함수는 글자 수가 약 45% 줄고 흐름(if/switch)이 바로 보이지만, (1) 함수 경계를 `methods.tsv`의 다음 주소로
정해 주지 않으면 엉뚱하게 커지고, (2) asm 주석이 주는 정적 필드 이름을 C가 잃는다. 둘을 고치면(경계를 표로 지정, 정적 필드 블록에 이름 붙이기 — 기존
`il2fields`의 표로) P3d 앱 동작 대조에 asm 대신 쓸 만하다. 다음: 그 두 수정 뒤 같은 네 함수 + 하나를 다시 재고 쓸지 정한다(사용자 확인).

**다시 잼(같은 저녁, 사용자 "Fix and re-measure"):** 두 가지를 고쳤다 — (1) 함수 시작점 표(`methods.tsv` + `generics.tsv`, 348,038개)로 함수 몸을 다음
시작점까지로 정하고, 몸 밖으로 뛰는 꼬리 `jmp`(공유 generic으로 가는 IL2CPP 꼬리 호출)를 call-return으로 표시; (2) asm 주석의 `~static Class.Field`로
클래스 2,290개의 정적 필드 블록 타입을 만들어 TypeInfo 전역에 입힘(`TypeInfo_…WormAttributes->static_fields->BlockExceptions`, cctor 확인은
`->cctor_finished`). The Voice의 비용(`NoCostAction`, OQ-116 앱 처리)을 다섯째로 더했다.

| 함수 (이미 아는 답) | asm | C | 답이 C에서 보이는가 |
| --- | --- | --- | --- |
| UrgentMissionAbility::Cost (`HasDeployedAgents(1)`) | 26줄 | 19줄 | 예 |
| TheVoiceAbility::Cost (`NoCostAction`) | 25줄 | 19줄 | 예 |
| UrgentMissionAbility::GetTargets (보드의 자기 Agent를 람다로 거름) | 75줄 | 59줄 | 예 — `Descendents.OfType<WormAgent>().Where(<GetTargets>b__0)` |
| SpaceAbility GrantResources MoveNext (Carryall·Thumper) | 1,731줄 | 1,011줄 | 예 — 로그 키로 가지를 찾고 더하기가 보임 |
| PlayerTurnPhase Cleanup MoveNext (The Voice 막힘 해제) | 9,841줄 | 5,465줄 | 예 — `BlockExceptions`가 이름으로 나옴 |

다섯의 합: asm 511,896자 → C 290,591자(43% 적음). 남은 차이: asm 주석이 푸는 **인스턴스 필드** 이름(`~WormPlaymat.<Board>k__BackingField`)은 C에서
아직 `+ 0xa0` 같은 오프셋이다(그 자리는 asm 주석이나 `il2fields`로 맞춰 읽는다). 큰 코루틴은 C도 수천 줄이다.

**결론(내 판단, 사용자 확인 전):** P3d의 앱 동작 대조에서는 **디컴파일한 C를 먼저 읽고**, 인스턴스 필드 이름과 결론을 가르는 줄은 주석 asm으로 확인한다.
글자 수가 약 43% 줄고 흐름(if/switch/LINQ 사슬)이 바로 보이며, 답을 아는 다섯이 모두 맞게 읽혔다. 도구: `scripts/dwgr/ghidra_tables.py`(표 셋을
assets의 `ghidra/`에), `scripts/dwgr/ghidra/DecompileTyped.java`(headless 스크립트). 한 번 불러와 이름·타입을 붙이는 데 약 80초, 메모리 약 1.5GB.
Ghidra는 launch.sh 대신 JDK 25로 직접 띄워 `-Duser.home`·`-Djava.io.tmpdir`를 프로젝트 `tmp/`로 둔다(launch.sh는 `~/Library/ghidra`에 씀 — 시범 첫 실행에서
생긴 파일 하나는 지웠다). macOS용 디컴파일러 본체는 릴리스에 없어 `Ghidra/Features/Decompiler/src/decompile/cpp`에서 `make ghidra_opt`로 빌드해
`os/mac_arm_64/decompile`에 둔다(x86_64, Rosetta).

### 16.10 조합 다시 보기 (2026-10-28 아침, 사용자 상시 지시)

사용자(조정자 경유): "뭔가 이런거 정할 때, 항상 다른 모든 확장들과 결합했을 때의 시나리오를 다 생각해야해. 원판 단독에서 문제없다고 끝나는게
아니야. 확장들과 결합 무조건 할거니까." 그래서 "원판 단독 판에서는 닿지 않는다, 조합은 P7"을 멈출 이유로 쓰지 않는다. OQ-139~144와 16.9의
행을 이렇게 다시 봤다. 조합마다 무엇이 닿는지는 각 OQ에 적었다. 정해진 것과 남은 일:

1. **Commander를 빠뜨린 넷(고칠 것):** Sardaukar Legion(garrison에서 셋까지 배치), Scout(둘까지 퇴각), Chani(몇이든 퇴각), Test of Humanity(배치한
   troop 잃기)는 "Commander는 P7에서 정한다"며 병력만 다룬다. 그러나 이미 정해져 있다 — "troop을 대상으로 하는 효과는 Commander에도
   적용된다" `[Bloodlines p. 4]`, OQ-115 사용자 판정(2026-10-22) "이후 조합 구현에서도 Commander를 빠뜨리지 않는다". Rapid Mobilization
   (`DeployFromGarrison`)과 Double Cross의 잃기는 이미 넣는다. 넷도 같은 처리로 고치고(Bloodlines Commander를 둔 테스트), 코드 주석의 "P7" 문장을
   지운다. 밤 작업에서 이 판정을 다시 열린 것으로 적은 것은 잘못이었다. **끝(`f5f1444a`, 조정자 go 2026-10-28 아침):** 세 이동은 수와
   Commander 몫마다 줄(Bloodlines가 있는 카탈로그에만), Test of Humanity는 Conflict의 Commander를 잃는 줄. Uprising 카탈로그 144개 바이트까지
   같음, 특성 405행 같음.
2. **Firm Grip 접합(고칠 것):** 원판 + Immortality에서 접합한 두 카드는 "두 카드의 효과를 board space 효과와 함께 원하는 순서로 얻는다"
   `[Immortality p. 10]`. 그래서 Firm Grip의 Solari 화살표 줄(`pay_agent_card_solari`)을 `graft_boxes.BOX_ACTION_IDS`에 더한다. Uprising +
   Immortality 카탈로그가 바뀌는지 먼저 확인한다(바뀌면 codec 문제라 따로 묻는다). **끝(`4c926fc0`):** 어느 카탈로그도 바뀌지 않았다 —
   box 1의 단계 줄은 Immortality가 있는 카탈로그에 이미 있었고, 막은 것은 효과 frame의 거절뿐이었다(Uprising 144개·원판 144개 줄마다 같음).
3. **차례 밖 획득의 창(그 조합을 열 때):** OQ-141 조합 — Scouts의 Critical Moment로 얻은 CHOAM Directorship·Lady Jessica. 차례 밖에서 Imperium 카드를
   얻는 길은 Impress(비용 3 이하라 닿지 않음)와 Critical Moment뿐이고, 획득 상자의 Influence는 한 곳(`_acquisition_influence`)을 지나 거절이 모든 길을
   덮는다(2026-10-28 Codex 리뷰 뒤 OQ-141에 적음).
4. **OQ-144(사용자 확인 대기):** Double Cross의 supply 배치에 Commander를 쓸 수 있는가.
5. **Guild Bankers:** 할인은 원판·Uprising의 The Spice Must Flow 두 인쇄를 모두 이름하고(`ReserveCostDiscount.card_ids`), Scouts의 Reserve 비용
   수정도 같은 값을 읽어(`scouts_modifiers.reserve_discount`) 조합에서도 같다.
6. **Rise of Ix(P4):** 카드를 전사할 때 이 절의 OQ들(획득 상자 OQ-141, 차례 시작 OQ-143, 승리 책략 OQ-142, "이 병력" OQ-140, Mentat OQ-139,
   Commander OQ-144)에 대어 본다. dreadnought는 troop이 아니다 `[Rise of Ix p. 6]`(OQ-115).

7. **Navigation card 4 + Recruitment Mission(P7):** Bloodlines Navigation card 4의 Plot이 The Spice Must Flow를 얻는 길(`ability_executor`의
   `reserve_acquisitions`)은 고를 단계 없는 자동 보상이라, Recruitment Mission이 켜진 Reveal turn에 얻어도 덱 위를 고를 수 없다. 원판 + Bloodlines가
   열리는 P7에서 고르기 단계를 둔다.

8. **Kwisatz Haderach의 자기 Agent 둘(P7):** 원판에서 회수 줄은 고쳤다(`761cba10`). Uprising의 Into the Fray(`leader_abilities.py`, 칸 id로 다
   지움)와 Immortality의 Twisted Mentat(같은 칸 줄 겹침)는 원판 카드와 섞이는 P7에서 같은 셈으로 고친다. Kwisatz가 Conflict의 Agent(Into the Fray)를
   옮길 수 있는가("from anywhere")는 [OQ-146](rules/open-questions.md#oq-146--kwisatz-haderach의-from-anywhere와-conflict에-있는-into-the-fray의-agent-원판--bloodlines) (가)로
   정해졌다(2026-10-28 사용자 "소환도 되는데 퀴사츠 헤더락도 가능하지"). P7 할 일: `_placements_for_card`의 출발점과 `_placing_owner`에 Conflict의
   Agent(`agent_in_conflict`)를 넣고, 옮기면 OQ-037 (d)의 recall처럼 유닛으로서 Conflict를 떠나게(전투력 갱신) 하며 테스트를 둔다.

9. **원판 카드의 graft(P7, 원판 + Immortality):** 공식 판정 셋이 원판 카드를 이름한다 — "Ghola — When grafted to Carryall, you get four times the base
   spice you harvest with your Agent. When grafted to Kwisatz Haderach, you still send only one Agent on your turn (though you draw two cards)."
   `[FAQ p. 2]`, "If you graft this card with Power Play to send an Agent to a faction board space, you gain only 2 Influence with that faction, the
   same as if you'd played Power Play alone." `[Immortality p. 14]`. 지금 Maker 칸 수확의 두 배(`rules/board_effects.apply_maker_space_action`)는
   놓인 칸의 카드(`active_agent_card`)만 읽어 graft 짝의 Carryall·Thumper를 빠뜨린다(Ghola + Carryall이 네 배가 아니라 두 배; 2026-10-28 Codex 리뷰).
   P7에서 두 칸의 카드를 모두 읽고(배수는 겹침 — 위 FAQ), Thumper의 보너스 spice 두 배도 같은 읽기로 겹치게 한다(Thumper는 FAQ가 이름하지 않아
   project convention으로 적는다). Power Play·Kwisatz는 위 두 문장대로 테스트를 둔다.
10. **Commander만 있는 Reveal 이동(고침 `09bf5f2d`):** 16.10 1의 세 이동 줄은 Commander 몫을 냈지만 선택이 열리는 조건은 troop만 세어, Commander만
   있으면 선택이 기다렸다(Codex 리뷰). 조건도 Commander를 센다 `[Bloodlines p. 4]`(OQ-115).
11. **Uprising Maker 칸의 sandworm 쪽 harvest(P7):** 공식 FAQ(Countess Ariana 항목) "When playing Uprising, it is possible to harvest no spice from
   Deep Desert and Hagga Basin (if there is no bonus spice there, and you choose to summon a sandworm rather than take base spice). In such a case, you
   did not “harvest spice” … so the “Spice Addict” ability does not apply." — 보너스 spice가 있으면 sandworm을 골라도 harvest다. 그래서 Uprising 판의
   원판 Thumper("Double the bonus spice you harvest with this Agent")는 sandworm 쪽에서도 보너스 spice를 두 배로 하고, Countess Ariana의 Spice Addict도
   보너스 spice가 있으면 sandworm 쪽에서 적용한다. 지금 `rules/board_effects.apply_maker_space_action`은 둘 다 `harvest_maker_spice` 쪽에서만 한다(P3d
   앱 대조; 앱은 보너스 두 배를 배치 때 함께 준다). 원판 판에는 sandworm이 없어 지금은 닿지 않는다.
12. **Masterstroke의 셈에서 sandworm·dreadnought 빼기(P4·P7):** OQ-115 판정은 troop과 Commander만 세고 "sandworm까지 세는 unit 조건 …의 전체 유닛 합계를
   Baron의 troop 수와 혼동하지 않는다", dreadnought도 뺀다 `[Rise of Ix p. 6]`. 그런데 `rules/masterstroke.masterstroke_is_due`는
   `units_deployed_turn`·`units_deployed_peak`를 읽고, 이 셈은 sandworm을 더한다(`board_effects.py`의 Maker 칸 소환, `reveal_turn`의 Reveal 배치; P3d
   앱 대조에서 확인). 원판 단독에는 sandworm·dreadnought가 없어 결과가 같다. 원판 + Ix(P4, dreadnought 배치)와 Uprising 판(P7) 전에 troop·Commander만
   세는 turn 셈과 그 최고치를 따로 둔다(관측·같음 확인 영향은 그때 판단).
13. **원판 Conflict 보상과 sandworm(P7):** "보상을 받을 때 자신의 sandworm이 Conflict에 하나 이상 있으면 자신이 받는 보상을 두 배로 한다"
   `[Main p. 14]`(combat-and-round-end.md 4). `rules/combat`의 보상 아이콘은 원판 Conflict의 보상 종류(Mentat, 한 진영 Influence, 보상 줄)를 "그 판에는
   sandworm이 없다"며 두 배로 하지 않는다. 원판 판 + Uprising 카드(P7)에서 sandworm이 Conflict에 들어오면 이 종류도 두 배다 — Cloak and Dagger
   3위의 "Intrigue -OR- spice"는 고르기를 두 번(앱도 두 번, P3d 앱 대조), 비용 있는 줄은 비용도 두 번 `[Main p. 14]`.
14. **Earl Memnon의 Connections와 칸 밖의 원로회 자리(P7):** 지도자 문구(앱) "When you take a High Council seat: [Influence 1, 고른 진영]". 지금은 High
   Council 칸의 아이콘에서만 일어난다(`rules/board_effects`의 `OnHighCouncilSeatTaken`). Uprising의 Corrinth City처럼 칸 밖에서 자리를 얻는 효과와 만나면
   그때도 일어나야 한다(앱도 `Fire::HighCouncilSeatTaken`으로 같은 사건을 쓴다, P3d 앱 대조). 원판 단독에는 칸 밖의 자리가 없다.
15. **Uprising 칸 id를 박아 둔 코드(P7):** 원판 칸은 이름이 같아도 id가 다르다(`imperium_sietch_tabr`, `imperium_high_council` …, 16.2·P1). Bloodlines
   Liet Kynes의 Sietch Tabr 요구 면제는 Uprising의 `sietch_tabr`에만 걸려 있어(`rules/agent_turn.py`) 원판 + Bloodlines에서 원판 Sietch Tabr에 닿지 않는다
   (P3d 앱 대조). CHOAM 모듈의 Harvest 계약이 원판 Maker 칸(Imperial Basin·Hagga Basin·The Great Flat)에서 성립하는지도 정해야 한다(앱은 Uprising 칸만
   이름하나 원판 보드와 CHOAM을 함께 쓰지 않는다). P7을 열 때 `rules/`·`content/`에서 Uprising 칸 id 문자열을 모두 찾아 원판 칸에도 맞는지 본다.

1·2는 조정자의 go(2026-10-28 아침)로 끝냈다(대상 테스트 `-n 2`, Uprising 카탈로그·특성 행 대조; 전체 pytest와 관문은 E7b 뒤 그대로).


### 16.12 P3d 끝: 두 덱 소크와 앱 행동 대조 (2026-10-28 밤 ~ 10-29 새벽)

조정자 go(22:4x, 사용자 "왜 계속 안 하고 멈춰있어"), 사용자 23:2x "평소대로 꼼꼼히 … 동시에 도는 agent는 2개(많아도 3개)".

**원판 두 덱 소크(`0618a2dc` 스냅숏, 22:43~22:51):** 원판 5,000판(휴리스틱·무작위 × Leader 돌리기·드래프트·프로모, 설정마다 1,000판, 시드 100000부터),
숨은 정보 검사 10결정마다, 제시한 모든 행동의 코덱 왕복 25결정마다 — 모두 끝까지, 실패 0. 내용 집계: 원판 카드 49종(프로모 포함) 모두 획득, Intrigue 34종
모두 사용, Conflict 18장, 지도자 8명 모두 등장. 원판은 아직 확장 옵션을 받지 않는다(`rules/setup._IMPERIUM_PENDING_OPTIONS`); 조합은 P4·P7.

**앱 행동 대조(10.4절 1):** 원판 카드·칸·지도자·Conflict 138항목(Imperium 46+스타터 7+Reserve 3, Intrigue 34, Conflict 18, 지도자 8, 칸 22) — 앱 BaseSet·Promo
아키타입과 모두 짝지음. 대조한 앱 능력 클래스의 메서드 3,983개를 Ghidra로 디컴파일(16.11의 도구, 약 15분, 한 번)해 클래스마다 C 파일로 모았고, agent가
C를 먼저 읽고 결론을 가르는 줄은 주석 asm으로 확인했다. 20묶음, Sonnet agent 20개(동시 2~3개), agent 토큰 약 1,130만. 차이로 보고된 것은 이 세션이 반박
위주로 다시 보고 `docs/rules` 인용으로 판정했다. 결과: 같음 58, 다름 74, 불명 6(주장 133개 — 대부분 이미 판정된 OQ가 앱과 다르게 정한 것과
조합 메모). 도구·묶음·결과는 assets의 `reference/dune-steam-app/<build>/analysis/p3d-compare-2026-10-28/`(로컬)에만.

- **고친 결함 넷(모두 OQ-071 "비용만 내고 보상을 받지 못하는 경우는 없어야 한다"와 그 recruit 기준·확장 2를 빠뜨린 자리):**
  - `b12933e5` Agent box 화살표의 recruit — Fremen Camp "[2 spice] → troop 셋", Duncan Idaho "[1 water] → troop, 카드"가 supply가 비어도(그리고 Duncan은
    뽑을 카드도 없을 때) 비용을 받았다. recruit는 supply에 troop이 있거나 되돌릴 specimen이 있을 때만 살아 있다(`immortality.troop_can_join`, Intrigue와 같은 셈).
  - `d30062e7` Gurney Halleck의 Reveal "[3 Solari] → troop 둘, 배치 가능"(supply 0이면 내지 않음; 하나 남으면 그대로 내고 나머지는 OQ-030·OQ-140의 부족분),
    Imperial Spy의 "Trash this card → Intrigue"(Intrigue 덱과 섞을 버림 더미가 비면 내지 않음 — 버리는 카드는 비용의 부수 효과라 줄을 살리지 못한다). 한 줄짜리
    trash 비용 box는 뽑기·recruit가 죽었으면 기다리고 화면이 이유를 말한다(Uprising의 trash→뽑기 줄도 같은 판정).
  - Codex 리뷰의 `09bf5f2d`(Commander만 있는 Reveal 이동, 16.10 10)도 이 밤의 고침이다.
- **판정이 이미 있어 바꾸지 않은 차이(앱이 다르게 함):** 비용 없는 효과의 불발(OQ-113 (C) — Bribery·Poison Snooper·Urgent Mission·Water of Life 등은 앱이 반대로 둔다),
  아이콘·효과의 자유 순서(OQ-027·OQ-106·OQ-112 — 앱은 칸 → 카드 → 지연 능력의 고정 순서와 자동 실행), Reveal 자원 줄(OQ-045), 6칸 진영(OQ-060), 상대 손실 창
  (OQ-036·OQ-138), 같은 순위 순서(OQ-002), Endgame 창(OQ-001), 승자의 창(OQ-121), 앞면 Intrigue(Charisma·Recruitment Mission — FAQ p. 2가 두 카드를 이름함, OQ-016),
  Bindu(OQ-117·OQ-143), Masterstroke의 셈과 자기 turn(OQ-115·OQ-063), Helena의 할인(FAQ p. 3 "the 1 persuasion discount will not apply"), Infiltrate의 "your next
  Agent"(인쇄), Control 방어 배치의 "may"(`[DI pp. 10, 16]`), Sort Through the Chaos의 Mentat(FAQ p. 4), Foldspace 카드를 먼저 trash한 뒤 Foldspace 칸에서 다시 얻기
  (효과 순서 자유 `[DI p. 9]`와 "Reserve cards are returned to their stack in the Reserve" `[DI]` trash 아이콘 설명).
- **사용자 판정(2026-10-29):** Research Station은 한 장씩 세 번(OQ-147, 고침). Spice Smugglers는 비용을 낸 뒤 Influence와 Solari를 소유자가 원하는 순서로(OQ-148 (가), 고침).
- **내 판단으로 그대로 둔 것(사용자 확인 대상, 위 판정 전):** Spice Smugglers의 지불은 Solari를 Influence보다 먼저 낸다(인쇄와 앱은 Influence 먼저). 화살표 지불 함수가 단순
  획득을 먼저 하고 효과 frame을 넘긴 뒤 Influence 같은 단계(창을 열 수 있음 — 동맹, Emperor 트랙 Spy)를 하기 때문이다. 인쇄 순서로 돌리면 그 창이 넘긴 frame
  아래에 쌓일 수 있다. 결과가 그 순서에 기대는 경우는 찾지 못했다(로그 순서만 다름). Research Station의 "카드 셋"은 화살표 뒤의 한 보상으로 한 번에 뽑는다(앱은
  뽑기 셋을 따로 둠). 
- **문서 정정:** OQ-125의 앱 설명(앱도 Reserve를 낸다 — 판정과 같음), OQ-124의 앱 설명(앱도 보낸 Mentat을 다시 가져가지 않는다 — 판정 A와 같음). OQ-042의
  "Double Cross가 `UndeployedTroops`를 쓴다"는 이번 대조에서 확실하지 않았다(빈 supply가 아니라 빈 garrison일 때만 쓴다는 읽기, 추론 포함) — 판정은 원칙
  ("원칙대로")에 선 것이라 바뀌지 않는다. OQ-117: 앱은 turn 시작의 다른 Plot 뒤에도 Bindu를 허용한다(우리는 디자이너 문장대로 첫 행동만).
- **조합에서 할 일(16.10 9·11~14):** graft 짝의 Carryall·Thumper와 Ghola 판정(9), Uprising Maker 칸 sandworm 쪽의 harvest(11), Masterstroke 셈의 sandworm·dreadnought(12),
  원판 Conflict 보상의 sandworm 두 배(13), Connections와 칸 밖의 원로회 자리(14), Uprising 칸 id를 박아 둔 코드(15: Liet Kynes의 Sietch Tabr 면제, CHOAM Harvest 계약).
- **P4 점검 목록(앱 코드에서 본 Ix 상호작용):** Guild Accord의 Heighliner spice 할인(2, Ghola와 4), Spaceport의 Foldspace 카드 덱 위, Combat 칸 배치 몫의
  dreadnought, Rise of Ix가 Hall of Oratory·Rally Troops·Secure Contract·Sell Melange를 보드에서 뺌, Yuna Moritani의 Smuggling Operation이 Windfall에도 +1
  Solari, dreadnought가 Control marker보다 먼저 칸의 controller가 됨(`WormSpace::get_ControllingPlayer`).

## 17. P4 계획 초안: Rise of Ix (원판 위) (2026-10-29, 브랜치 `claude/base-ix-p4`, P3 병합 master에서)

**상태: 초안.** 조정자 경유 사용자 승인 계획대로(2026-10-29 03:2x): P4 계획 절 초안·OQ 목록·P4a 틀 설계를 먼저 쓰고, 사용자 답이 필요한 OQ는 모아
아침에 올리고, 답 없이 되는 틀 작업은 계속한다. 규칙 명세는 P0의 [rise-of-ix.md](rules/rise-of-ix.md)(구성표·setup·Tech·Shipping·dreadnought·
Unload·잠입·칸·지도자·Epic·숨은 정보·결정 단위)이고, 판정은 OQ-119~OQ-127(Ix 몫)이 끝냈다. 범위는 8절 표의 P4: CHOAM 덮개 칸 넷, Ix 보드(Tech 18,
협상가, Shipping), dreadnought와 유닛 규칙, Discard·Unload·잠입 아이콘, 카드(Imperium 29종 35장 + 프로모 Boundless Ambition, Intrigue 17, Conflict 셋 +
이미 있는 Economic Supremacy), 지도자 6, 원판 + Ix의 Epic, 끝에 소크와 Ix 전부의 앱 행동 대조. 크기는 P0 분류(`…/p0-readings/dsl-coverage.md`):
Ix Imperium 60칸 중 새 조각 22, Intrigue 22절 중 9, 지도자는 hook이 많고, Tech 18장 중 새 조각·hook 10.

### 17.1 하위 단계 (추천)

| 단계 | 내용 | codec | 관측 |
| --- | --- | --- | --- |
| **P4a 틀** | Ix 정의를 앱 속성 표에서 생성(도구 1을 Ix로: Imperium 30·Intrigue 17·Conflict 3·지도자 6·Tech 18·칸 4), id(17.2), `rise_of_ix`를 원판에서 받기(Uprising + Ix는 P7까지 거절), CHOAM 덮개가 칸 넷을 바꿈, Conflict 덱(I 1·II 5·III 4, 원판 + Ix 카드에서), 덱은 효과가 들어간 카드만(P3처럼), 앱 표와 기계 대조 pytest | 브랜치 안에서는 그대로, 병합 때 한 번(사용자 2026-10-28 "병합 때 한 번") | **v39 한 번**: Ix id를 구간 끝에, 새 구간(17.4) |
| **P4b 유닛과 dreadnought** | `PlayerState`의 dreadnought(supply·garrison·Conflict·Control 칸 위), commission(좌석당 둘), strength 3, 끈질김, 지배(승자의 창의 줄, OQ-121), 배치 규칙의 "유닛"(rise-of-ix.md 6의 표), Masterstroke의 troop 셈(16.10 12) | 그대로 | (v39에 포함) |
| **P4c Ix 보드** | Tech 타일 — Bloodlines Tech 틀(세 더미, 획득 창, 할인, 뒤집기)을 Ix 타일로 다시 씀, 협상가, Shipping 트랙(Freighter 아이콘, 회수 보상 순서 자유, 차례 밖 회수), 덮개 칸 넷(Dreadnought·Tech Negotiation·Interstellar Shipping·Smuggling) | 그대로 | (v39) |
| **P4d 카드** | Imperium·Intrigue·Conflict를 card-implementer 묶음으로(동시 2~3), Discard 아이콘·Unload·잠입 | 그대로 | 그대로 |
| **P4e 지도자·Epic·프로모** | 지도자 6(숨은 정보: Hundro의 Intrigue 맨 위, Ilesa의 따로 둔 카드; Tessia의 Snooper), 원판 + Ix의 Epic(Uprising Epic 구현 재사용, 12점, Conflict I 없음), Boundless Ambition(`promo_cards`) | 그대로 | (v39) |
| **P4f 끝** | 원판 + Ix 소크(Epic·프로모·드래프트), Ix 전부의 앱 행동 대조(P3d와 같은 방법: 대조할 능력 클래스를 Ghidra로 디컴파일, C 먼저·asm으로 확인, agent 동시 2~3, 차이마다 반박 위주 재확인과 `docs/rules` 인용 판정) | – | – |

단계마다 엔진 관문 전체(2026-10-20 사용자 결정). 관측 변경은 P4a 한 번에 모은다(P3의 v37처럼): 필요한 구간을 P4a에서 미리 다 잡고, 뒤 단계는 값을
채우기만 한다. 뒤에서 구간이 더 필요해지면 그때 사용자에게 묻는다(P3의 v38처럼).

### 17.2 id (4.2절 7)

- 2026-10-29 스크립트(앱 `RiseOfIx`·Promo 아키타입 이름 → id, 지금 Imperium·Intrigue·지도자·Bloodlines Tech id와 대조): 겹침은 **Esmar Tuek**(Ix
  Imperium 카드 ↔ Bloodlines 지도자 `esmar_tuek`) 하나 → `esmar_tuek_card`(15.2·16.2와 같은 규칙). Tech 타일 18장과 Bloodlines Tech 18장은 이름이
  겹치지 않는다. 칸 넷: `dreadnought`, `tech_negotiation`, `interstellar_shipping`, `smuggling`(Uprising의 `shipping` 칸과 다르다).
- 이름이 비슷한 것 셋은 엔진 id와 화면 용어집에서 가른다(rise-of-ix.md 7): Uprising Spy의 "Infiltrate"(행동), 원판 Intrigue "Infiltrate", Ix의
  "Infiltration" 아이콘(`infiltration`).
- Control the Spice는 이미 있다(Uprising Epic, `content/uprising/starting_cards.py`) — 원판 + Ix Epic도 같은 카드다(앱도 `RiseOfIx` 아키타입 하나).

### 17.3 출처 (D1·D2, 2.4절)

- P3와 같다: 앱 속성 표(도구 1)와 카드별 화면 조각, 영어 문구. 카드면 스캔은 새로 읽지 않는다. Tech 타일은 앱 레이아웃(Bloodlines Tech 렌더가
  이미 앱 Ix 타일 틀을 씀). 프로모 Boundless Ambition은 앱에 Promo 아키타입과 문구가 있다.
- 순서·may/must·시점이 문구로 정해지지 않으면 디컴파일한 C(16.11)를 먼저 읽는다. 공식 문서가 답하지 않으면 OQ-147부터.
- 공식 문서: Rise of Ix 룰북(`22-2-11` 판), 2025-01-13 FAQ, 원판 룰북 — 받은 텍스트가 `tmp/official-rules/`에 있다. **Bloodlines 룰북은 없다**(17.6 1).

### 17.4 엔진·codec·관측

- **새 조각(P0 분류):** `FREIGHTER`(11곳: 카드·Intrigue·Conflict 보상·Hundro의 Signet; 차례 밖에서도 일어난다 `[FAQ p. 3]`), `UNLOAD`(9장: 버리거나
  trash할 때도 Reveal box), `INFILTRATION`(7장: 카드 Agent 아이콘의 표시), `DREAD_COMMISSION`(3곳), Discard 아이콘(비용), Tech 획득·협상가·뒤집기
  (Bloodlines 틀). `IGNORE_BLOCK`는 P3에서 생겼다(Infiltrate·Eyes Everywhere·Invasion Ships). hook 위험: Weirding Way의 추가 turn, Ilesa·Tessia·Hundro.
- **"턴 종료" 제공자 목록**(lessons 2026-10-18): 새 제공자(Freighter, Acquire Tech, 협상가, dreadnought 지배, Unload, Discard)를 그 판정과 제공자 목록을
  든 곳에서 이름으로 모두 찾아 함께 고친다(rise-of-ix.md 14).
- **codec:** 원판 + Ix 카탈로그에 새 행이 생긴다. Uprising 144개 카탈로그는 바이트까지 같아야 한다(P2·P3와 같은 대조). codec 버전은 병합 때 한 번.
- **관측 v39(P4a 한 번):** Ix id를 기존 구간 끝에(개인 카드·Intrigue·지도자·Conflict·Tech·칸). 새 구간 후보: 좌석의 dreadnought(supply·garrison·
  Conflict 수, Control 칸마다 놓인 dreadnought의 주인), Freighter 칸, 협상가 수, Snooper token(Tessia), Ix Tech 더미(지금 Bloodlines Tech의
  `tech_stacks`·`tech_face_up`·`tech_stack_sizes`를 Ix 타일로 다시 쓸 수 있는지 P4a에서 확인 — 두 모듈을 함께 쓰는 판은 17.6 1). 숨은 정보
  (rise-of-ix.md 13): Hundro가 아는 Intrigue 덱 맨 위, Court Intrigue·Sonic Snoopers로 덱 맨 아래에 놓은 카드(놓은 좌석), Ilesa가 따로 둔 카드(주인),
  Spaceport로 덱 위에 놓은 카드(모두 — OQ-145 (나)와 같은 길). 모두 `known_card_seats`·결정 표본·되돌리기 경계에. Uprising 열은 그대로, 형식 2
  이관으로 옮긴 망이 Uprising 판에서 같은 수(P2·P3처럼 `same_moves.py`). 엔티티 특성은 Uprising 405행 그대로.
- **같음 확인:** 상태에 새 칸이 생기면 선언 차이 파일. Uprising 판의 그 밖의 차이는 0.
- **휴리스틱:** 새 효과의 점수는 Ix 콘텐츠에서만 닿는 가지(P3와 같은 방식). 앱 AI는 P6.

### 17.5 조합 (상시 규칙 "모든 확장과 결합한 판으로 판정", 사용자 2026-10-28 — 16.10; 구현은 그 조합을 여는 단계)

P4는 원판 + Ix(+ 프로모, Epic, 지도자 드래프트)를 연다. 그 밖의 조합은 판정만 지금 하고 구현은 P7·P8에서 한다.

1. **Uprising + Ix(P7, `[Main p. 18]` "Adding Rise of Ix"):** CHOAM 덮개를 반만 펴 Assembly Hall·Gather Support를 덮는다. Ix·CHOAM 보드에 관측 초소가
   하나씩 있는 것으로 친다(Interstellar Shipping·Smuggling, Tech Negotiation·Dreadnought). Ix Conflict 카드는 넣지 않기를 권하되 넣어도 되고, Epic이면
   Economic Supremacy를 III에 더한다. Ilesa는 Foldspace를 얻을 수 있다(원판 Foldspace 카드가 필요). CHOAM 모듈과 Ix: 덮개가 계약 칸 하나를 바꾸므로
   Ix용 계약 10장을 좌석마다 둘씩 받아 하나 고른다(`[Main p. 16]`; 앱의 Uprising 계약 28장에 든다). dreadnought의 지배 칸은 그 판의 Control 칸(4.2절 6:
   Ix 기계는 보드에 묶지 않는다). sandworm·Shield Wall과 dreadnought의 관계는 17.6 3.
2. **Ix + Bloodlines(원판 또는 Uprising):** Sardaukar Commander는 troop이고 dreadnought는 troop이 아니다(rise-of-ix.md 6 표, `[Bloodlines p. 4]`).
   배치 몫(17.6 2). Tech Module과 Ix Tech를 함께 쓰는 판은 Bloodlines 룰북 p. 7이 다룬다(17.6 1).
3. **Ix + Immortality(원판, P7):** 앱은 Immortality에서 원판 Research Station을 빼고 Immortality판 칸을 쓴다(`RemovedFromSetList`, P3d). FAQ의 graft 예
   (16.10 9)와 Spaceport·Recruitment Mission·Tleilaxu 덱 위 놓기(OQ-145).
4. **Ix + Uprising Spy:** 잠입 아이콘(Ix)과 Spy의 Infiltrate(Uprising)는 다른 것이다 — 둘 다 상대 Agent를 무시하지만 The Voice는 못 넘는다.
5. **P3에서 넘어온 Ix 몫(16.10·16.12):** Masterstroke의 셈에서 dreadnought 빼기(16.10 12 — P4b에서 구현), Guild Accord의 Heighliner spice 할인(2, Ghola와 4),
   Spaceport의 Foldspace 칸 카드 덱 위, Combat 칸 배치 몫의 dreadnought, Ix가 Hall of Oratory·Rally Troops·Secure Contract·Sell Melange를 뺌, Yuna의
   Smuggling Operation이 Windfall에도 +1, dreadnought가 Control marker보다 먼저 칸의 controller(앱 `WormSpace::get_ControllingPlayer`). P3의 OQ들
   (OQ-139~145)은 Ix 카드를 전사할 때 대어 본다(16.10 6).

### 17.6 사용자 답이 필요한 것 (OQ 후보 — 아침에 한 번에)

1. ~~Bloodlines 룰북 받기~~ → **끝(2026-10-29, 사용자 "assets/rulebooks 에 룰북 다 있을텐데"):** 로컬 Bloodlines 룰북 p. 7만 읽어 [rise-of-ix.md](rules/rise-of-ix.md)
   10a에 옮겼다. 두 모듈을 함께 쓰면 타일 36장을 섞어 세 더미, Ix 전부를 쓰므로 Ixian Embassy 없음(High Council 할인 없음, Tech Negotiation 할인은 씀),
   덮인 Commander 자리 둘은 Dreadnought와 (4인) Tech Negotiation으로. 구현은 원판 + Bloodlines의 P7.
2. ~~배치 몫과 commission~~ → **문장으로 정해진다(묻지 않음):** "You may deploy any or all units recruited during your current turn … plus up to two
   more units from your garrison" `[Rise of Ix p. 6]`, "If you commissioned the dreadnought while sending an Agent to a Combat space, you may deploy it
   to the Conflict" `[Rise of Ix p. 6]`. 이번 turn에 commission한 dreadnought는 garrison 몫(둘) 밖에서 배치할 수 있고, garrison 몫 둘은 troop·
   Commander·dreadnought가 함께 쓴다(OQ-070의 "garrison 몫은 두 종류가 함께 쓴다"를 유닛으로 넓힘). P4b에서 테스트로 고정한다.
3. **Uprising + Ix의 dreadnought와 sandworm·Shield Wall(P7):** 둘 다 유닛이고 sandworm은 보상을 두 배로 한다 `[Main p. 14]`. dreadnought만 남은 쪽의
   Combat Intrigue 자격, Shield Wall이 있을 때 dreadnought 배치 — 공식 문장을 찾고, 없으면 OQ.
4. **(확인만) P4 끝 앱 행동 대조를 P3d와 같은 방법으로**(디컴파일러 C 먼저, Sonnet agent 동시 2~3, 약 100항목) — 추천.

### 17.7 P4a 틀 설계 (답 없이 하는 일)

- 생성기: `scripts/dwgr/imperium_entries.py`(P3 도구 1)를 Ix 아키타입에 넓혀 정의 줄을 만든다(이름·장수·비용·진영·Agent 아이콘·Reveal 값·획득
  보너스·잠입 아이콘·Unload 표시). `content/rise_of_ix/`(imperium·intrigue·conflicts·leaders·tech·board) 새 패키지, 합친 BY_ID 조회.
- 판 축: `content_for(config)`가 `rise_of_ix`면 원판 칸 목록에서 덮개 칸 넷을 바꾸고 Ix Conflict·카드·지도자·Tech를 더한다. `rules/setup`의
  `_IMPERIUM_PENDING_OPTIONS`에서 `rise_of_ix`와 `epic_game`(P4)을 뺀다; Uprising + Ix는 계속 거절(P7).
- 기계 대조 pytest: 앱 표(공개 저장소의 `agents/app_ai/data/archetypes.py`)와 Ix 정의를 칸마다 대조(P3a의 `test_imperium_app_table`처럼).
- 관측 v39 구간 설계(17.4) — 독립 리뷰 한 번(P3 v38처럼), Uprising 판 같은 수 확인.
- 소크: 원판 + Ix(효과 없는 카드는 덱 밖이라 틀만으로도 돈다).

**판 축(2026-10-29, `acc6a6f7`):** 원판 + `rise_of_ix`의 `content_for`가 덮개 칸 넷(Hall of Oratory, Rally Troops, Secure Contract, Sell
Melange)을 빼고 Ix 칸 넷을 끝에 더하고(22칸), Ix 지도자 여섯을 원판 여덟 뒤에, 덱은 `play_data_complete`인 Ix 카드만(아직 없음) 받는다.
Conflict: Economic Supremacy는 이 상자의 III이라 Epic이든 아니든 늘 풀에 있다(rise-of-ix.md 3의 3). Skirmish 둘·Trade Monopoly는 보상
(`reward_rows`)이 전사되면 풀과 codec 목록에 함께 들어간다(덱 카드가 효과를 기다리는 것과 같은 원칙) — 지금 풀은 I 4·II 10·III 5. codec의
`bloodlines_only`·`epic_only` 거름 넷은 `RulesetContent.conflicts_in_play()`(풀에 든 것)로 바뀌었다(Uprising은 같은 집합·같은 순서). 카탈로그 288개
(두 본판, Ix 없이) 그대로; 원판 + Ix 넷은 바뀐 칸·Ix 지도자·Economic Supremacy 줄만 달라졌다. setup은 계속 거절한다. **P4c 몫:**
`ConflictSetup`의 남는 장수 검사(지금 6·8; 원판 + Ix는 22 − 10 = 12, Epic도 12)를 본판과 Ix를 받게 고친 뒤 setup을 연다.

### 17.8 관측 v39 설계안 (P4a, 구현 전 독립 리뷰 대상)

v38은 137구간 8,265열이다. 원칙은 v35·v37·v38과 같다: 새 id는 각 어휘의 **끝에** 붙이고 새 구간은 배치의 **끝에** 둔다. 그래야 형식 2 이관이
열을 (구간, 자리)로 옮기고 새 열은 0에서 시작해, 옮긴 망이 Uprising 판에서 같은 수를 둔다(P2·P3처럼 `same_moves.py`).

- **어휘 끝에 붙일 Ix id:** 개인 카드 +30(Imperium 29종 + Boundless Ambition; Control the Spice는 이미 있음), Intrigue +17, Conflict +3(Economic
  Supremacy는 이미 `BATTLE_CARD_IDS`에), 지도자 +6, 칸 +4(Dreadnought·Tech Negotiation·Interstellar Shipping·Smuggling), Tech +18(Bloodlines 18장
  뒤에). 이 어휘를 쓰는 구간(손 공개·in play·discard·trash·덱 풀·imperium_removed·private_hand·엿본 카드·고르는 카드·Intrigue 구간들·`tech_trash`·
  `seatN_tech`·지도자 드래프트 풀·Agent 자리)은 길이만 늘고 뜻은 그대로다.
- **새 구간 후보(상태 칸은 P4a에서 기본값 0으로 먼저 만들고 값은 P4b·c·e가 채운다):**
  - `seatN_units`: dreadnought의 supply·garrison·Conflict 수(좌석마다 3열). troop·Commander 열은 이미 `seatN_scalars`에 있다.
  - `dreadnought_control`: Control 칸마다 그 칸에 dreadnought를 놓은 좌석(+1, 없으면 0)과 "다음 Combat 끝에 떠남" 표시 — 원판 Arrakeen·Carthag·Imperial
    Basin(Uprising 판이면 그 판의 Control 칸, P7). 칸 수는 `CONTROL_SPACE_IDS`(넷)를 다시 쓴다.
  - `seatN_ix`: Freighter 칸(0~3), 협상가 수, Snooper token 넷(Tessia; 트랙마다 남은 token 칸 또는 0).
  - Ix Tech 더미: 지금 `tech_face_up`(3)·`tech_stack_sizes`(3)를 그대로 쓴다. 두 모듈을 함께 쓰는 판(P7)도 더미가 셋이다(`[Bloodlines p. 7]`,
    rise-of-ix.md 10a) — Tech 어휘(Bloodlines 18 + Ix 18)만 늘면 된다.
  - 숨은 정보(rise-of-ix.md 13): `private_intrigue_top`(Hundro가 아는 Intrigue 덱 맨 위, 124+17열 one-hot), `private_intrigue_bottom`(Court Intrigue·Sonic
    Snoopers로 놓은 좌석이 아는 덱 맨 아래 카드들, 수 세기), `private_set_aside`(Ilesa가 따로 둔 카드, 주인만). Spaceport로 덱 위에 놓은 카드는 v38의
    `seatN_deck_public_top`(OQ-145)을 그대로 쓴다.
  - `ix_flags`: 판 표시(원판 + Ix인가, 4.2절 8)와 뒤집은 Tech(이미 `tech_flipped`가 좌석 상태에 있으면 그것).
- **확인할 것:** `known_card_seats`·결정 표본(determinizer)·되돌리기 경계에 Hundro·Court Intrigue·Sonic Snoopers·Ilesa를 넣는다. 엔티티 특성은 Uprising 개체로
  척도를 고정해 Uprising 405행 그대로(P2a의 `entity_features._table`). 크기 어림: 어휘 늘림 약 +1,100열, 새 구간 약 +330열 → 약 9,700열.

**독립 리뷰 반영(2026-10-29 04:4x, Codex gpt-6.1-sol 읽기 전용, `78a06d55`; 조정자가 1·5를 코드에서 확인):**

1. **Ilesa가 따로 둔 카드와 덱 풀(숨은 정보):** 공개 집계 `seatN_deck_pool`(`core/observation._deck_pool`: 덱 + 공개 아닌 손패)에서 따로 둔 카드를 빼면
   상대가 빼기로 그 카드를 안다. → 따로 둔 카드는 **공개 집계에 그대로 남긴다**(덱 풀 = 덱 + 공개 아닌 손패 + 따로 둔 카드). 정체는 주인의
   `private_set_aside`에만.
2. **덱 맨 아래에 놓은 Intrigue의 행방:** 놓은 좌석은 그 카드가 뽑힌 뒤 누가 가졌는지도 안다(rise-of-ix.md 13). → `private_known_intrigue`: 보는
   좌석이 아는 "다른 좌석 손의 Intrigue"를 상대 셋 × Intrigue 어휘의 수로 둔다(공개 `seatN_intrigue_faceup`에는 넣지 않는다 — 모두에게 새므로).
   `known_card_seats`·결정 표본도 같은 지식을 쓴다.
3. **Ilesa의 카드가 돌아온 뒤:** 정체는 OQ-010의 공개 경로 손패(`hand_public`)로 보인다. "둘째 turn 보너스" 자격은 Agent 수로 셀 수 없다(pass·Weirding
   Way, OQ-119) → `seatN_ix`에 "따로 둔 카드가 이번 turn에 돌아옴(보너스 대기)" 표시와 "이번 라운드에 끝낸 turn 수" 하나.
4. **남은 Shipping 회수 보상과 Tech 구매 방식:** Freighter 칸·협상가 수만으로는 열린 결정이 안 보인다. → 열린 결정의 구간 `ix_pending`: 남은 회수
   보상 셋(1·2·3칸, 받았는지), 열린 Acquire Tech의 할인(0·1·2), 지불 수단(spice·Appropriate의 Solari), 돌려받을 수 있는 협상가 수.
5. **이관과 좌석 × 어휘 행렬(확인됨):** `voice_blocks`는 `row * len(SPACE_IDS) + space_index`라 칸 어휘를 늘리면 좌석 1~3 행이 밀린다. → 옛 행렬은
   **그대로 두고** Ix 칸 넷은 새 구간 `voice_blocks_ix`(좌석 × 4)로. P4a 구현 때 `observation_encoding.py`에서 어휘 길이를 곱하는 구간을 모두 찾아
   같은 처리를 한다(검사: 옛 구간마다 v38과 v39의 열 뜻이 같은지 테스트로 고정).
6. **덱 맨 아래의 순서:** Sonic Snoopers는 "몇 장이든" 맨 아래로 보낸다 — 놓은 좌석은 놓은 순서를 안다. → `private_intrigue_bottom`은 수 세기가 아니라
   맨 아래부터의 자리(최대 8칸, 칸마다 Intrigue 어휘 index+1)로 두고, 공개 `global_scalars`에 Intrigue 덱 크기를 더한다(덱 크기는 공개 사실 — 맨 위로부터의
   거리는 덱 크기와 자리로 셈).

**v39 구현과 리뷰(2026-10-29):** `001a5b64`(Ix 상태 칸, 기본값이면 해시에서 빠짐), `78c00bac`(인코딩 8,265 → 10,189열, 137 → 155구간). Codex 독립 리뷰
지적 0. 남은 주의: 지식 칸을 채우고 비우는 효과(Hundro, Court Intrigue, Sonic Snoopers, Ilesa, 덱 섞기 때 무효화)를 P4b~e에서 넣을 때 섞기에서
지식이 지워지는지 테스트로 고정한다. Ix Tech 18장·칸 4개 정의와 P4b~e의 FrameKind 예약도 v39에 함께 넣는다(조정자 go, "v39 한 번" 유지).

**v39에 더한 것(2026-10-29, `f51fba6d`·`2ed0cd7f`·`4784d228`):** Ix Tech 18장(`content/rise_of_ix/tech.py`: 앱 표의 이름·spice 비용, 타일마다
`TechAbility` 새 멤버 — 능력 기록은 P4c)과 칸 넷(`content/rise_of_ix/board.py`: 17.2의 id·순서, Agent 아이콘, Dreadnought 3 Solari,
Interstellar Shipping의 Spacing Guild 2 — 효과 기록은 P4b·c)을 by-id 조회(`TECH_TILES_BY_ID`, `BOARD_SPACES_BY_ID`)에만 넣었다(더미·setup·덱·
`content_for` 밖). 획득 효과는 기존 조각이 있는 9장을 `TECH_ACQUIRE_ABILITIES`에 적었다(Chaumurky Intrigue 2, Disposal Facility trash, Flagship
1 VP, Invasion Ships troop 4, Memocorders Influence 1, Sonic Snoopers Intrigue 1, Spaceport 카드 2, Windtraps water 1, Shuttle Fleet 서로 다른
진영 둘 — OQ-114, Machinations와 같은 조각). water와 "서로 다른 둘"은 지금 획득 키가 내지 못하므로 그 두 타일의 `acquire_effect_keys`는 P4c까지
`NotImplementedError`다. 관측: `TECH_IDS` = Tech Module 18 + Ix 18(Tech 구간 여섯이 끝에 18열씩), `SPACE_IDS` 끝에 칸 넷(칸마다 열인 구간은
없다; `voice_blocks_ix`는 어휘로 색인하고 열은 그대로) → 10,189 → 10,297열, 155구간. FrameKind 다섯을 끝에 예약했다(`frames.IX_FRAME_KINDS`,
엔진 경로 없음): `freighter_move`(차례 밖 Freighter 아이콘의 답 — Conflict 보상 창의 선택 아이콘처럼), `shipping_reward_icons`(차례 밖 회수 보상,
`contract_reward_icons`처럼), `dreadnought_control_choice`(승자의 지배 칸 또는 Detonation), `round_start_set_aside`(Ilesa), `unload_icons`(차례
밖 Unload의 Reveal box). 조정자 go로 둘을 더해 일곱(`5bbb196d`): `optional_discard`(차례 밖의 선택 "버리기 →" 비용 — Conflict
보상의 Influence로 닿은 Tessia의 첫 Snooper 보상, `optional_trash`의 버리기 짝), `intrigue_bottom_pick`(Sonic Snoopers의 "몇 장이든" Intrigue를
고른 순서로 덱 맨 아래에 — `long_live_fighters`처럼 따로 고르는 창; Court Intrigue는 한 장이라 줄 하나의 대상). 재사용: Acquire Tech·협상가 반환은 `tech_acquisition`, Hundro의 Intelligence는 `intrigue_peek`(Imperium Ceremony와 같은
결정), 나머지(Duplicity, 협상가, Tech Negotiation 칸, commission·배치, 차례 안의 Discard 비용, 뒤집기)는 차례의 줄. 움직인 고정값: slot 키 1,957 → 2,020
(옛 키 순서 그대로), 엔티티 특성(+22 개체, tech 열 2개 — water·distinct; 옛 589행 차이 0), `test_teacher`의 teacher seed 1 → 2. v38 열의 골든
digest·고정 두 판, 카탈로그 288개, 상태 해시 6판은 그대로.

### 17.9 P4b 설계: 유닛과 dreadnought (2026-10-29)

규칙은 [rise-of-ix.md](rules/rise-of-ix.md) 6과 OQ-121(판정 1~6)이 정한다. setup은 P4c까지 Rise of Ix를 거절하므로 P4b의 동작은 손으로 만든 상태의
테스트로 고정하고, 관문은 Ix 없는 판이 그대로인지(같음 확인·카탈로그 288·엔티티 특성)를 본다. 상태 칸은 v39에 이미 있다(`PlayerState.dreadnoughts_*`,
`GameState.dreadnought_control`).

**`units_in_conflict` 감사(21곳).** 모두 "유닛"을 읽는 자리(`UnitsInConflictAtLeast`, 보상 받을 좌석, Conflict 끝 창의 좌석, Agent 회수 뒤 strength
0 규칙, swords가 세지는 조건, Recall 앞 확인, Reveal의 strength 공식)이고, 카드의 "troop"은 `troops_conflict`를 따로 읽는다. 그래서
`units_in_conflict`에 `dreadnoughts_conflict`를 더한다 — strength 0 규칙과 Combat Intrigue 자격에 dreadnought가 든다 `[Rise of Ix p. 6]` `[FAQ p. 2]`.
`GainSolariPerUnitType`(Uprising 카드)의 "유닛 종류"에 dreadnought가 드는지는 Uprising + Ix(P7)에서 판정한다.

1. **P4b-1 Conflict의 dreadnought.** strength 3(`DREADNOUGHT_STRENGTH`, 좌석별 함수로 — Prince Rhombur의 4는 P4e), 유닛 strength를 더하는 공식 모두.
   Combat 끝 정리에서 Conflict의 dreadnought는 supply가 아니라 garrison으로 가고 "잃은" 유닛에 들지 않는다(끈질김, OQ-121 판정 2·5 (2)). 지배:
   dreadnought가 하나라도 있는 Conflict의 승자에게 승자의 창(1위 보상과 같은 창)의 **의무 줄**이 생기고(OQ-121 판정 6 (1)), 그 줄에서 본판의 Control
   칸 가운데 dreadnought가 없는 칸 하나를 골라 dreadnought 하나를 놓는다(`dreadnought_control`에 `leaving` False). 칸의 controller는 dreadnought의
   주인이 marker보다 먼저다(앱 `WormSpace::get_ControllingPlayer`, 17.5 5) — 방문 보너스와 방어 배치가 그 좌석에. Combat 단계의 마지막 일로
   `leaving`인 것은 주인의 garrison으로 돌아가고 나머지는 `leaving`이 된다(승자가 없어도, OQ-121 판정 1). Detonation Devices의 "지배 대신 VP"는 그
   줄 안의 선택으로 P4c(Tech)에서 더한다.
2. **P4b-2 commission과 배치.** 새 DSL 조각 `CommissionDreadnought`(아이콘마다 "may", supply → garrison; supply가 비면 그 아이콘만 불발 — 칸은 갈 수
   있다, 디자이너 판정). 배치: "any or all units recruited during your current turn … plus up to two more units from your garrison" `[Rise of Ix
   p. 6]` — Commander의 틀(OQ-070, `deployment_rooms`)에 셋째 종류를 더한다: 이번 turn에 commission한 dreadnought는 제 종류의 자리, garrison 몫
   둘은 troop·Commander·dreadnought가 함께 쓴다(17.6 2). Masterstroke의 "4+ troops"는 dreadnought를 세지 않는다(16.10 12, rise-of-ix.md 6 표의
   Baron 줄) — `units_deployed_*` 셈과 따로 확인한다.
3. **P4b-3 마무리.** 스윕 불변식(dreadnought 둘, `dreadnought_control`과 좌석 칸의 합), rise-of-ix.md 6 룰북 예를 좌석별 문자 그대로 테스트(OQ-121),
   codec 행(원판 + Ix 카탈로그만), 관문(17.1 "단계마다 엔진 관문 전체"; 첫 P4 관문은 6352199d에서 새 같음 기준을 잡는다).

setup이 좌석마다 supply에 dreadnought 둘을 주는 일 `[Rise of Ix p. 3]`(rise-of-ix.md 3의 5)은 setup을 여는 P4c에서 한다.

**P4b-1 끝(2026-10-29, `c0d47fe7`·`44c643fd`):** dreadnought는 Conflict의 유닛(strength 3, strength 0 규칙·Combat Intrigue 자격), Combat 끝 정리에서
garrison으로, 칸의 controller는 dreadnought가 marker보다 먼저(방문 보너스·방어 배치·app_ai 미리보기; marker를 옮기는 보상·세 개 한도·관측은
marker 그대로), Combat 단계의 마지막에 `leaving`인 것은 garrison으로·나머지는 `leaving`. 승자의 창에 `dreadnought_control` 줄 하나(승리마다
하나, sandworm으로 두 배가 되지 않음), 답은 `DREADNOUGHT_CONTROL_CHOICE`의 `place_combat_reward_dreadnought`(Control 칸 셋 중 dreadnought가 없는 칸).
codec: 원판 + Ix 카탈로그만 +19행(Conflict마다 `take{icon: dreadnought_control}`), Ix 없는 카탈로그 288개 그대로. 룰북 예(Frida·Ned·Bodie)를
엔진으로 좌석별 테스트. **P4c 표시 몫(P5 화면 세션과 나눔):** `display/actions.py` `combat_reward_icon_action_text`에 `dreadnought_control` 갈래가 없어
그 줄이 "Influence 1"로 보인다; 엔진 이벤트 `dreadnought_control_placed`·`dreadnought_returned`의 로그 문구. setup이 열리기 전에는 닿지 않는다.

**P4b-2 끝(2026-10-29, `4aa62f61`·`4561910b`, 라벨 `904357ad`):** DSL 조각 `CommissionDreadnought`(아이콘마다 "may", supply → garrison; supply가
비면 그 아이콘만 불발 — `NO_DREADNOUGHT_TO_COMMISSION`). 이번 turn의 commission은 turn frame에 세고(Plot으로 놓기 전 commission한 것도 이번
turn의 것 — "units recruited during your current turn"과 같이), 배치는 셋째 종류(`deploy_dreadnoughts`·`withdraw_dreadnoughts`): commission한
dreadnought는 제 자리, garrison 몫 둘은 troop·Commander·dreadnought가 함께(`unit_deployment_rooms`: 종류마다 초과분의 합 ≤ 2). dreadnought는
troop이 아니라 `units_deployed_*`(Masterstroke·Distraction·Coercive Negotiation이 읽는 셈)에 들지 않는다. codec: 원판 + Ix만 +4행. 서버 라벨은
공식 한글이 없어 "dreadnought"를 영어로 둔다(용어집에 행 없음). **넘기는 일:** P4c — Dreadnought 칸·Tech의 commission 행(지금은 Intrigue 출처만
줄이 있다), 화면의 `FORCE_STEPPER_ACTIONS`(turn.js)에 dreadnought 배치/회수, 한글 이름(`effect_dsl_text_ko.py`의 "Commission a dreadnought"는
영어 임시), 훈련의 `UNDO_ACTION_IDS`에 `withdraw_dreadnoughts`(지금 넣으면 `test_selfplay`가 고정한 집합과 어긋남 — Ix 판 자체 대국 전에). P4d —
Diversion("four or more units")은 dreadnought를 세야 하므로 frame의 dreadnought 수를 조건에 더한다. P7 — Reveal turn의 Combat 아이콘 배치에
dreadnought(Bloodlines + Ix), Uprising의 "unit" 조건 카드.

### 17.10 P4c 조각 순서 (초안, 2026-10-29 — 구현 전에 코드 위치를 확인해 다듬는다)

규칙은 [rise-of-ix.md](rules/rise-of-ix.md) 3·4·5·8, OQ-114·122·126. setup은 마지막 조각에서 연다(그 전까지 테스트는 손으로 만든 상태).

1. **P4c-1 Tech 틀을 Ix 타일로.** Bloodlines Tech Module의 틀(더미, 앞면 맨 위, 획득 창, 뒤집기와 Round Start 되돌리기)을 Ix의 세 더미(6장씩)로
   쓴다 — v39는 Tech 구간을 Tech Module 18 + Ix 18로 이미 넓혔다. 획득은 Acquire Tech 아이콘으로만(아이콘마다 "may", 더미가 비면 고를 것이
   준다), Tech Discount −1·−2는 그 한 번에만·합치지 못함·의무(OQ-104), Negotiator(아이콘마다 supply troop 하나를 Ix board에, "may"; 획득 때 원하는
   만큼 돌려 spice 1씩; recruit 불가 `[FAQ p. 4]`, 12 troop 안에 셈). 두 모듈을 함께 쓰는 판(10a)은 P7.
2. **P4c-2 Tech 18장의 획득 효과와 능력.** 획득 효과 9장은 P4a에서 적었다(water·"서로 다른 둘"은 키가 없어 Windtraps·Shuttle Fleet이 P4c에서).
   능력은 때마다 묶는다: Reveal turn(Artillery, Disposal Facility OQ-126, Minimic Film, Restricted Ordnance), Round Start(Holtzman Engine,
   Shuttle Fleet — OQ-122 순서), Conflict 승리(Windtraps, Detonation Devices — `DREADNOUGHT_CONTROL_CHOICE` 안의 "VP 대신"), Endgame(Chaumurky
   동률, Holtzman Engine, Memocorders, Spy Satellites), 뒤집기 넷(Flagship, Holoprojectors, Invasion Ships, Training Drones — 자기 turn 중 라운드에
   한 번 `[FAQ p. 1]`), 자기 turn(Sonic Snoopers — `INTRIGUE_BOTTOM_PICK`, 아는 Intrigue는 OQ-149 틀; Spy Satellites 첫 능력), 상시(Spaceport,
   Troop Transports). card-implementer 묶음(동시 2) — 주간 95% 아래일 때.
3. **P4c-3 Shipping track과 Freighter.** 새 조각 `FREIGHTER`(아이콘마다 "may": 한 칸 위 또는 회수), 회수 보상(칸 1~3, 원하는 순서 —
   `SHIPPING_REWARD_ICONS`), 차례 밖 회수(Conflict 보상의 Freighter — `FREIGHTER_MOVE`, Combat 중 recruit는 garrison), Troop Transports.
4. **P4c-4 덮개 칸 넷.** Dreadnought(3 Solari, commission 그리고/또는 Acquire Tech — P4b의 `CommissionDreadnought`에 칸 출처 행), Tech Negotiation
   (고르기 + 여기 Agent가 있으면 Reveal에 Persuasion 1), Interstellar Shipping(Guild 2 요구, Freighter 둘; Kwisatz는 요구를 넘지 못함), Smuggling
   (1 Solari, Freighter 하나). Duke Leto의 Landsraad 할인.
5. **P4c-5 setup을 연다.** `_IMPERIUM_PENDING_OPTIONS`에서 `rise_of_ix`를 빼고: 좌석마다 dreadnought 둘을 supply에, Freighter를 맨 아래에, Tech
   18장을 섞어 세 더미, `ConflictSetup`의 남는 장수(원판 + Ix 12, Epic도 12), 휴리스틱이 새 결정을 모두 답하는지(소크), P4b가 넘긴 화면·훈련
   몫(17.9). 그다음 원판 + Ix 소크와 관문.

**P4c-1 끝(2026-10-29, `82b2bf2e`):** Ix 획득은 Bloodlines 틀(`tech_stacks`, `TECH_ACQUISITION` 창, `_take_tile`, 획득 효과)을 `rise_of_ix`
갈래로 쓴다: 값 = 타일 비용 − 할인 − 돌려준 Negotiator(0 아래로 안 감), High Council 할인은 없음(`tech_cost(high_council_discount=False)`,
Ixian Embassy가 없다), Bloodlines의 Landsraad 획득 제안은 `tech_module`일 때만. 조각은 Bloodlines의 `AcquireTech`를 그대로 쓰고(새 조각 없음)
`PlaceNegotiator`를 더했다(행 모양은 `Verb.RECRUIT`의 `negotiator` 변형 — 관측의 Verb 폭을 넓히지 않으려고; 규칙상 recruit가 아니다
`[FAQ p. 4]`). `ix_pending`의 `negotiators_returnable`은 min(가진 수, 앞면 타일 가운데 가장 비싼 값 − 할인). 세 더미 만들기
`deal_ix_tech_stacks`(setup에는 P4c-5에서). 원판 + Ix 카탈로그 +113행. **다음 조각이 꼭 할 일:** (1) `AcquireTech`의 기본 할인이 1(Bloodlines)이므로
Ix 콘텐츠는 `discount=0`/`1`을 늘 적는다(Dreadnought 칸은 0, Tech Negotiation은 1). (2) 거절(`decline`) 행이 원판 + Ix 카탈로그에 없다 — 창의
인쇄 출처(`_window_printers`)가 Intrigue 카드만 알므로, P4c-4·P4d가 칸·카드 출처를 더하기 전에 콘텐츠를 붙이면 codec이 거절을 담지 못한다.
(3) Windtraps·Shuttle Fleet은 아직 사면 `NotImplementedError`(P4c-2). (4) `PlaceNegotiator`·`CommissionDreadnought`는 Intrigue 출처 행만 있다.
**P4c-1 Codex 리뷰(2026-10-29):** (1) 버그 — 쌓인 획득 창이 열릴 때 찍은 `negotiators_returnable`을 관측이 그대로 읽음 → `f5e7421d`
(`core.observation.ix_negotiators_returnable`로 매번 계산). P4c-2a 뒤 정리: `rules/tech.py`의 같은 함수와 frame에 적는
`NEGOTIATORS_RETURNABLE_KEY`를 core 함수 하나로 합친다. (2)·(3) **P7 몫(Ix + Tech Module 함께):** Ix 갈래가 `_acquisition_variants()`를
건너뛰어 Advanced Data Analysis를 `post_id` 없이 내고(고르면 `KeyError`), codec의 Negotiator 구매 행이 Ix 타일에만 있어 Bloodlines 타일의
Negotiator 변형(예: Glowglobes를 Negotiator 1로)을 담지 못한다 — 두 모듈을 함께 여는 단계에서 갈래를 합친다(10a).

**P4c-2a·2b 끝(2026-10-29, `00f3a312`·`d3324e1c`; Codex 2a 지적 0):** Tech 18장 가운데 15장 — 획득 키(Windtraps water, Shuttle Fleet 서로 다른 둘),
Round Start(Holtzman Engine·Shuttle Fleet, OQ-122), Reveal(Artillery·Minimic Film·Restricted Ordnance·Disposal Facility, OQ-126), 승자의 창
(Windtraps 줄, Detonation Devices), Endgame(Chaumurky 동률이 VP 다음 첫 기준, Holtzman·Memocorders·Spy Satellites — Tech Module 줄 뒤 좌석
순서, OQ-040의 관례), 뒤집기 넷(Flagship 4 Solari·troop 3, Holoprojectors, Invasion Ships — 놓기 전 turn frame에서만, Training Drones; "discard →"
비용은 손 카드라 Reveal turn에는 없다). OQ-150 (가): Reveal 도중 얻은 Ix 타일도 그 turn에 듣는다. 원판 + Ix 카탈로그 1,889행. **P7 몫:** Tech
Module의 Self-Destroying Messages·Panopticon도 OQ-150의 같은 원칙으로 늦게 줘야 한다 — Uprising + Bloodlines만으로는 Reveal 도중 Tech를 얻을
길이 없어 지금은 닿지 않고(OQ-110 "같은 모양 전수"), Ix와 함께 여는 단계에서 맞춘다. **남은 P4c-2c:** Sonic Snoopers(`INTRIGUE_BOTTOM_PICK`,
아는 Intrigue는 OQ-149 틀), Spy Satellites 첫 능력, Spaceport(얻은 카드를 덱 위에 — OQ-145의 공개 덱 위). Troop Transports는 P4c-3.

**P4c-2c 끝(2026-10-29, `7913f5db`·`44cff763`):** Sonic Snoopers(`INTRIGUE_BOTTOM_PICK` — 한 장씩 아래로, 넣은 좌석만 알고 다른 좌석은 그 손의 아는
카드를 잊는다(OQ-149), 넣을 Intrigue가 있을 때만(OQ-071), Twisted는 넣지 않음(OQ-097)), Spy Satellites의 교환(spice 3 + 타일 trash → 1 VP),
Spaceport(얻는 카드를 덱 위에 — 뒤붙이 행이 있는 모든 획득, OQ-145로 공개). 원판 + Ix 1,892행. Tech 18장 가운데 17장 끝(Troop Transports는 P4c-3).
**P4c-4 몫:** Spaceport와 Foldspace 칸의 Foldspace 카드(17.5 5) — 자동 Foldspace 칸 줄(`board_effects.py`)에 덱 위 변형이 없어 지금은 닿지 않는다.

**P4c-3 끝(2026-10-29, `24da7aaf`·`dfa4fbb5`·`8b464fcb`):** `Freighter` 조각(아이콘마다 "may": 한 칸 위·회수·안 함), 회수 보상은 칸마다 줄 —
1번 Dividends 또는 spice 2, 2번은 recruit와 Influence가 **따로 두 줄**(OQ-148 원칙, 순서 자유), 3번 할인 2 Acquire Tech("may", 턴 종료에 소멸,
OQ-095 (2)); 차례 밖은 `FREIGHTER_MOVE`·`SHIPPING_REWARD_ICONS` 창. Troop Transports(Tech 18장 끝): 2번 recruit에 troop +1, 자기 turn이면 Combat
칸이 아니어도 그 troop을 따로 센 몫으로 배치(rise-of-ix.md 15, `SHIPPING_TROOPS_KEY`), 배치를 막는 효과는 "may"보다 먼저, Combat 해결 중의
회수는 garrison(OQ-151 (가)). 원판 + Ix 1,905행. **넘기는 일:** 화면 문구(`display/actions.py`에 `resolve_shipping_reward` 설명 없음, P5와
나눔), 칸·카드 출처의 Freighter 행(P4c-4·P4d), Windtraps를 Freighter 보상으로 얻은 승리의 water(Conflict 보상을 붙일 때, rise-of-ix.md 12).
