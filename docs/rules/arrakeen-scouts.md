# Arrakeen Scouts 모듈

**Arrakeen Scouts**(공식 한국어 "아라킨 스카웃" `[KO app: spice.mainmenu.34pgame.label]`)는 Dire Wolf Game Room(Steam)의 Dune: Imperium 컴패니언 앱이 제공하는 3-4인 모드다. 앱이 무작위 일정을 만들고, 라운드마다 그 라운드의 **소위원회**·**임무**·**이벤트**·**경매**·**판매**를 공개한다. 공식 룰북은 없다. 이 문서의 근거는 앱의 정의 데이터·문구·아이콘·코드이며([sources.md](sources.md)의 "Arrakeen Scouts" 절), 효과는 모두 **의역**이다. 앱의 문구(영·한)는 이 저장소에 옮겨 적지 않는다.

프로젝트는 모듈을 `RulesetConfig(arrakeen_scouts=True)` 옵션으로 취급하며 기본값은 꺼짐이다. 설계와 구현 순서는 [arrakeen-scouts-design.md](../arrakeen-scouts-design.md)(M15)에 있다.

- **인원.** 엔진은 4인 전용이다. 4인 규칙만 옮긴다(소위원회 5개).
- **조합.** `immortality`를 켜면 Uprising+Immortality 풀, 아니면 Uprising 풀을 쓴다. CHOAM 필터는 `choam_module`을 따른다. Bloodlines·Tech·프로모·Leader draft는 풀에 영향이 없다(앱도 Bloodlines를 모른다). 모든 조합을 허용한다. `[Scouts schedule]`
- **범위 밖.** 3인 플레이, 원본 Dune: Imperium과 Rise of Ix 보드용 풀(기본판 풀 넷, Uprising+Ix의 Ix 전용 임무), 앱 자체의 저장·이어하기·뒤로 가기.

## 1. 출처와 인용

- 인용 태그:
  - `[Scouts help]`: 앱 도움말. 절차를 정한다.
  - `[Scouts subcommittee: <이름>]`, `[Scouts mission: <이름>]`, `[Scouts event: <이름>]`, `[Scouts auction: <이름>]`, `[Scouts sale: <이름>]`: 항목의 정의·문구·아이콘.
  - `[Scouts schedule]`: 일정 생성과 라운드 진행. 앱 코드의 동작을 재현한 것이다.
  - `[KO app: <loc key>]`: 앱의 공식 한국어 용어.
- 권위 순서:
  1. 앱의 영어 문구와 아이콘(sprite 이름과 배치)이 항목의 효과를 정한다.
  2. 앱 도움말이 절차를 정한다.
  3. 항목이 부르는 기본 행동(recruit, Spy 배치·회수, Influence, Contract, 카드 획득·trash·draw)의 처리는 여전히 Main Rulebook·Board Space Guide·FAQ가 정한다.
  4. 앱의 한국어 문구는 **용어**로만 쓴다. 한국어판에는 오역과 누락이 있다(OQ-086).
- 앱이 정하지 않은 판정은 OQ-071~OQ-090에 project convention으로 둔다. 2026-09-28 사용자 결정(D8)에 따라 제안한 convention으로 구현하고, 모든 슬라이스가 끝난 뒤 한꺼번에 검토받는다.

## 2. 일정

### 2.1 라운드별 항목 `[Scouts schedule]`

| 라운드 | 공개되는 것 |
|---|---|
| 1 | 소위원회 5개 |
| 2·3 | 임무 3개. 70%로 2라운드 2개·3라운드 1개, 30%로 2라운드 1개·3라운드 2개 |
| 4~7 | 라운드마다 이벤트 1개 |
| 5 또는 6 (각 50%) | 중간 경매. 같은 라운드의 이벤트보다 먼저 |
| 8 또는 9 (각 50%) | 후반 경매 |
| 8·9 중 후반 경매가 없는 라운드 | 판매 1개 |
| 10 | 없음 |

게임이 10 VP나 Conflict 덱 소진으로 먼저 끝나면 남은 항목은 나오지 않는다. 앱도 점수를 판정하지 않고 플레이어가 끝낸다.

### 2.2 추첨 규칙 `[Scouts schedule]`

앱은 게임 시작 때(리더를 고른 뒤) 일정 전체를 만든다. 각 추첨은 앞선 추첨 결과에만 의존한다.

- **소위원회.** CHOAM을 끄면 CHOAM 전용 항목을 뺀다. 등급 0·1·2에서 하나씩 균등 추첨한 뒤, 남은 전체(등급 무관)에서 비복원 균등 추첨으로 5개를 채운다.
- **임무.** CHOAM을 끄면 CHOAM 전용 항목을 뺀다.
  - 세 자리의 라운드는 [2,2,3](70%) 또는 [2,3,3](30%)이다.
  - 각 자리는 그 라운드가 항목의 라운드 창 안에 드는 후보 중 균등 추첨한다.
  - 한 항목을 뽑으면 같은 계열(앱의 beatId)을 모두 뺀다.
  - 세 번째 임무는 두 번째 임무와 임무 종류(missionType 0·1)가 달라야 한다. 첫째와 둘째는 같아도 된다. 그래서 두 종류가 한 번씩은 꼭 나온다.
- **이벤트.** CHOAM을 켜면 "CHOAM 없을 때 전용"을, 끄면 "CHOAM 전용"을 뺀다.
  - 4·5·6·7라운드 순서로 하나씩, 가중치(baseWeight × subWeight)에 비례해 추첨한다. 라운드 창이 맞지 않는 항목이 나오면 다시 뽑는다. 곧 그 라운드에 나올 수 있는 후보만의 가중 추첨이다.
  - 뽑은 계열은 모두 뺀다.
- **경매.** CHOAM을 끄면 CHOAM 전용을 뺀다.
  - 중간 경매 라운드(5·6)와 후반 경매 라운드(8·9)는 각각 50%로 서로 독립이다.
  - 중간 경매: 그 라운드가 창 안에 드는 후보 중 균등 추첨. 그 계열을 모두 뺀다.
  - 후반 경매: 남은 후보 중 그 라운드가 창 안에 드는 것에서 균등 추첨. 곧 중간 경매와 다른 계열의 후반 판들이고, 중간 경매가 Mercenaries가 아니었으면 Mercenaries도 든다.
  - Mercenaries만 창이 5~9라 두 자리 모두에 나올 수 있다(한 게임에 한 번).
- **판매.** 풀 전체에서 균등 추첨한다. CHOAM과 라운드 창을 보지 않는다. 라운드는 8·9 중 후반 경매가 없는 쪽이다.

### 2.3 엔진의 추첨 (D2)

엔진은 앱처럼 게임 시작 때 일정 전체를 뽑지 않고, **공개되는 라운드에 chance로 뽑는다.** 각 추첨이 앞선 추첨 결과에만 의존하므로 분포는 같다. 미공개 일정이 상태에 없으므로 숨길 미래도 없다.

- 소위원회는 1라운드 시작에 추첨한다(Leader draft 뒤). setup chance를 쓰지 않으므로, 옵션을 켜도 setup 추첨과 덱은 옵션을 끈 게임과 같다.
- 임무 배치(70/30), 중간 경매 라운드, 후반 경매 라운드는 그 정보가 처음 필요한 라운드에 추첨한다.
- 이벤트 가중치는 **추첨표**로 표현한다. 가중치 × 10을 같은 선택지 수로 둔다(단일 이벤트 10장, 스파이스 획득·책략 보너스 계열의 변형 5장씩, 두 Influence 계열의 변형 6장씩. CHOAM 켬·끔으로 갈리는 Covert Operation과 Clear the Market은 한 게임에 한 변형만 남아 10장).

## 3. 라운드 흐름

`[Scouts help]`는 패를 뽑고 Conflict를 공개한 뒤 Scout을 누르라고 한다. 엔진의 Round Start는 Conflict 공개 → Control 방어 배치 → draw 순서다([setup-and-game-flow.md](setup-and-game-flow.md) 5절, `[Main p. 8]`, `[Main p. 20]`). **Scouts 단계는 Round Start가 끝난 뒤, 첫 turn 전에 둔다**(OQ-072). Scouts 단계 안의 순서는 앱과 같다.

1. 이번 라운드가 기한인 비밀 선택 보상(7.2절).
2. 그 라운드의 항목: 1라운드 소위원회 공개, 2·3라운드 임무, 4~7라운드 (중간 경매 →) 이벤트, 8·9라운드 후반 경매 또는 판매.
3. 첫 turn(First Player부터).

Scouts 단계의 결정은 누구의 turn에도 속하지 않는다. "이번 turn에" 세는 효과와 카운터에는 들어가지 않는다.

**차례 순서.** 좌석마다 차례로 결정하는 항목(선택형 이벤트, 판매, 임무 참여, 비밀 선택, 봉인 입찰, 공개 경매)은 First Player부터 시계 방향으로 진행하고, 각 좌석은 자기 차례의 상태로 판단한다(OQ-071, OQ-002 선례).

## 4. 소위원회

`[Scouts help]` `[Scouts subcommittee: <이름>]`

- 원로회 자리(High Council seat)를 차지할 때(High Council 칸, Corrinth City), 아직 아무도 가입하지 않은 소위원회 하나에 **가입할 수 있다**. 비용을 내고 보상을 한 번 받는다.
- 가입은 선택이다. 비용을 낼 수 있는 빈 소위원회가 없거나 거절하면 그 기회는 사라진다. 이후 원로회 칸을 방문해도 다시 가입할 수 없다(원로회 자리는 한 번만 얻는다). 소위원회 하나에는 한 명만 가입한다(OQ-076).
- 표의 "비용 → 보상"은 Uprising 판이다. 앱은 기본판 일정에서 셋(Appropriations, Intelligence, Oversight)에 다른 줄을 보여 주지만 여기서는 쓰지 않는다.

| id | 이름 (공식 한국어) | 등급 | 비용 → 보상 | 비고 |
|---|---|---|---|---|
| `appropriations` | Appropriations (재무) | 0 | 손의 카드 1장 버리기 → 물 1 | |
| `intelligence` | Intelligence (정보) | 0 | 없음 → Spy 1 배치 | |
| `readiness` | Readiness (긴급대응) | 0 | 없음 → troop 1 recruit | |
| `choam_coordination` | CHOAM Coordination (초암 조직화) | 0 | 없음 → Contract 1 | CHOAM 전용 |
| `growth_project` | Growth Project (성장 프로젝트) | 0 | 없음 → specimen 1 | Immortality 풀 |
| `oversight` | Oversight (관리감독) | 1 | Spy 1 회수 → 카드 1장 trash + spice 1 | trash는 trash 아이콘이라 선택 `[Main p. 20]` |
| `investigations` | Investigations (수사) | 1 | Solari 1 → Intrigue 1장 | 앱 한국어는 "스파이스"로 오역(OQ-086) |
| `forecasting` | Forecasting (예측) | 1 | spice 1 → 카드 2장 draw | |
| `choam_management` | CHOAM Management (초암 운영) | 1 | spice 1 → Contract 2 | CHOAM 전용 |
| `analytics` | Analytics (분석) | 1 | Solari 1 → Research | Immortality 풀 |
| `relations` | Relations (외교) | 2 | spice 2 → 원하는 Faction Influence +1 | |
| `contingencies` | Contingencies (유사시 대비) | 2 | Intrigue 1장 trash → 방금 보낸 Agent가 아닌 자기 Agent 1개 회수 | OQ-075 |
| `leverage` | Leverage (권위) | 2 | Spy 2 회수 → 원하는 Faction Influence +1 + Intrigue 1장 | |
| `tleilaxu_relations` | Tleilaxu Relations (협력: 틀레이락스) | 2 | spice 3 → Tleilaxu track 2칸 | Immortality 풀 |

## 5. 임무

`[Scouts help]` `[Scouts mission: <이름>]`

- 임무로 놓인 조각은 라운드가 끝나도 남는다. 보상은 받을 때까지 유효하다. `[Scouts help]`
- 좌석별 참여 결정은 공개 때 First Player부터 차례로 한다. 비용을 낼 수 없는 좌석은 참여하지 않는다(OQ-071, OQ-088).
- 칸 위에 세워 둔 병력은 그 좌석의 troop이다. supply·garrison·Conflict 어디에도 없고, 12개 보존에 함께 센다.

| id | 이름 (공식 한국어) | 종류 | 라운드 | 내용 |
|---|---|---|---|---|
| `security_detail` | Security Detail (경호 요원) | 0 | 2~3 | 각자 원하면 supply의 troop 1을 Deliver Supplies에 세운다. 그 칸에 처음 Agent를 보낼 때 그 troop을 recruit해 곧바로 Conflict에 배치한다 |
| `imperial_reserve` | Imperial Reserve (제국 비축 물자) | 0 | 2~3 | Imperial Privilege에 spice 1과 Solari 2를 놓는다. 방문자는 둘 중 하나를 가진다. 남은 쪽은 다음 방문자 몫이다(도움말 해설, OQ-078) |
| `desert_riding` | Desert Riding (사막 질주) | 0 | 2~3 | Hagga Basin 옆에 Maker Hooks 토큰을 둔다. 방문자는 칸의 기본 spice 2 대신 그 토큰을 가질 수 있다(Maker 보너스 spice는 그대로). 토큰은 네 Maker Hooks 가운데 하나다(OQ-079) |
| `urban_surveillance` | Urban Surveillance (유익한 정보원 - 도시 감시) | 0 | 2~3 | City 칸에 연결된 빈 관측소마다 Solari 1을 둔다. 그 관측소에 Spy를 놓는 좌석이 그 Solari를 가진다(OQ-080) |
| `planetary_exploration` | Planetary Exploration (유익한 정보원 - 행성 탐사) | 0 | 2~3 | Maker 칸에 연결된 빈 관측소마다 spice 1을 둔다. 받는 방식은 위와 같다 |
| `choam_research` | CHOAM Research (초암 연구) | 0 | 2~3 | 뒷면 Contract 2장을 Research Station에 둔다. 방문할 때마다 1장씩 가져간다(OQ-078). CHOAM 전용 |
| `choam_escort` | CHOAM Escort (초암 호송대) | 0 | 2~3 | 각자 원하면 둘 중 하나: troop 1 recruit, 또는 자기 앞면 Contract 하나 위에 Solari 1 + spice 1을 올려 두고 그 Contract를 완료할 때 함께 받는다. CHOAM 전용 |
| `sponsored_research` | Sponsored Research (연구 후원) | 0 | 2 | research track의 Helix 옆에 spice 2를 둔다. 다음에 Helix에 닿는 좌석이 가진다. Immortality 풀 |
| `back_room_deal` | Back Room Deal (밀실 거래) | 0 | 2~3 | Tleilaxu Row의 Reclaimed Forces 위에 Solari 2를 둔다. 다음에 Reclaimed Forces를 "획득"하는 좌석이 가진다. Immortality 풀 |
| `prison_planet` | Prison Planet (정예 사다우카 - 감옥 행성) | 1 | 2~3 | 각자 원하면 garrison의 troop 1을 잃고, Sardaukar 칸에 자기 Control 마커와 spice 2를 둔다. 그 칸을 방문하면 마커와 spice를 되찾을 수 있다. 세 번째 칸을 지배하게 될 때 마커가 모자라면 이 마커를 가져다 쓰고 임무는 spice 없이 끝난다(도움말). Uprising 풀 |
| `emperors_schemes` | Emperor's Schemes (정예 사다우카 - 황제의 계략) | 1 | 2~3 | Intrigue 2장을 Sardaukar 칸에 둔다. 방문할 때마다 1장씩 가져간다(OQ-078) |
| `fedaykin_assistance` | Fedaykin Assistance (페다이킨의 지원) | 1 | 3 | 각자 원하면 spice 1을 내고 supply의 troop 2를 Desert Tactics에 세운다. 다음에 그 칸을 방문할 때 그 troop을 recruit한다 |
| `weirding_warfare` | Weirding Warfare (기이한 전투) | 1 | 2~3 | 각자 원하면 Solari 2를 내고 supply의 troop 2를 Espionage에 세운다. 다음 방문 때 recruit해 곧바로 Conflict에 배치한다 |
| `send_for_aid` | Send for Aid (지원 제공) | 1 | 2~3 | 각자 원하면 garrison의 troop 1을 Gather Support로 옮기고 그 밑에 물 1을 둔다. 다음 방문 때 그 troop을 recruit해 곧바로 Conflict에 배치하고 물을 가진다 |
| `coordinate_with_the_emperor` | Coordinate With The Emperor (황제와의 협력) | 1 | 3 | 각자 원하면 specimen 1을 Sardaukar 칸으로 옮기고 그 밑에 Solari 2를 둔다. 그 칸에 처음 Agent를 보낼 때 칸 효과에 더해 Solari 2를 받고 그 troop을 garrison에 둔다. Immortality 풀(Prison Planet 대신) |
| `tleilaxu_offering` | Tleilaxu Offering (틀레이락스의 공물) | 1 | 2 | 각자 원하면 supply의 troop 2를 Tleilaxu track의 세 번째 칸에 둔다. 자기 Tleilaxu 토큰이 그 칸에 닿으면 그 troop 2를 specimen으로 Axolotl tanks에 넣는다(OQ-089). Immortality 풀 |

- **계열.** Desert Riding과 Valued Informants 두 종(Urban Surveillance, Planetary Exploration)은 한 계열이라 셋 중 하나만 나온다. Elite Sardaukar 두 종(Prison Planet, Emperor's Schemes)도 한 계열이고(앱의 제목은 "Valued Informants - …", "Elite Sardaukar - …"처럼 계열 이름을 앞에 붙인다), Immortality 풀에서는 Coordinate With The Emperor가 Prison Planet 대신 그 계열에 들어간다.
- 앱의 데이터에서 Desert Riding과 Urban Surveillance는 같은 id(15.0)를 쓴다. 프로젝트는 앱 id를 식별자로 쓰지 않는다.

## 6. 이벤트

`[Scouts event: <이름>]`. 표의 "추첨표"는 한 라운드 추첨표에서 그 이벤트가 차지하는 선택지 수다(2.3절).

- **선택형.** "각자 선택"인 이벤트는 First Player부터 차례로 한 가지를 고른다(앱 영어의 "in turn order"; 한국어판에는 빠져 있다). "또는 패스"가 있으면 선택하지 않아도 된다. 패스가 없으면 반드시 하나를 해야 하며, 할 수 없는 쪽은 고를 수 없다. 둘 다 할 수 없으면 아무 일도 없다(도움말, OQ-071).
- **이번 라운드 규칙 변경.** 공개된 라운드가 끝날 때까지 적용된다.

| id | 이름 (공식 한국어) | 계열 | 추첨표 | 라운드 | 내용 |
|---|---|---|---|---|---|
| `private_stock` | Private Stock (개인 비축품) | 스파이스 획득 | 5 | 4~7 | 각자 선택: spice 1, 또는 카드 1장 draw |
| `market_research` | Market Research (시장 조사) | 스파이스 획득 | 5 | 4~7 | 각자 선택: Spy 1 회수 → spice 2, 또는 패스 |
| `smoke_and_mirrors` | Smoke and Mirrors (진실의 왜곡) | 책략 보너스 | 5 | 4~7 | 각자 선택: Spy 1 배치, 또는 Solari 1 → Intrigue 1장 |
| `rotating_doors` | Rotating Doors (회전문) | 책략 보너스 | 5 | 4~7 | 각자 선택: Intrigue 1장 trash → Intrigue 1장 + 카드 1장 draw, 또는 패스 |
| `moment_of_revelation` | Moment of Revelation (폭로의 순간) | 단일 | 10 | 4~7 | 각자 원하면 spice 2를 내고 Reserve의 Prepare the Way를 **손으로** 획득 |
| `water_discipline` | Water Discipline (물 규칙) | 단일 | 10 | 4~7 | 각자 선택: 물 1 → 카드 1장 trash + 카드 1장 draw, 또는 패스 |
| `royal_delegation` | Royal Delegation (왕실 대표단) | 영향력 증가 | 6 | 4~7 | 각자 선택: Solari 2 → Emperor +1, 또는 패스 |
| `guild_negotiation` | Guild Negotiation (길드 협상) | 영향력 증가 | 6 | 4~7 | 각자 선택: spice 1 + 손의 카드 1장 버리기 → Spacing Guild +1, 또는 패스 |
| `covert_assistance` | Covert Assistance (비밀스러운 지원) | 영향력 증가 | 6 | 4~7 | 각자 선택: Spy 1 회수 → Bene Gesserit +1, 또는 패스 |
| `gift_of_water` | Gift of Water (물이 가져다 준 선물) | 영향력 증가 | 6 | 4~7 | 각자 선택: 물 1 → Fremen +1, 또는 패스 |
| `share_intelligence` | Share Intelligence (정보 공유) | 영향력 증가 | 6 | 4~7 | 각자 선택: Intrigue 1장 trash + Solari 1 → 원하는 Faction +1, 또는 패스 |
| `political_equilibrium` | Political Equilibrium (정치적 균형) | 영향력 축소 | 6 | 4~7 | 모두 자기 Influence가 가장 높은 Faction에서 −1. 동률이면 그중 하나를 고른다 |
| `crackdown` | Crackdown (강력 단속) | 영향력 축소 | 6 | 4~7 | 각자 선택: Spy 1 회수, 또는 Emperor −1 |
| `water_for_spice_smugglers` | Water for Spice Smugglers (밀수업자들에게 물 제공) | 영향력 축소 | 6 | 4~7 | 각자 선택: 물 1 잃기, 또는 Spacing Guild −1 |
| `bene_gesserit_treachery` | Bene Gesserit Treachery (베네 게세리트의 음모) | 영향력 축소 | 6 | 4~7 | 각자 선택: garrison의 troop 1 잃기, 또는 Bene Gesserit −1 |
| `funeral_rites` | Funeral Rites (장례 의식) | 영향력 축소 | 6 | 4~7 | 각자 선택: 손의 카드 1장 trash, 또는 Fremen −1 |
| `covert_operation` | Covert Operation (작전 변경) | CHOAM 변형 | 10 | 4~7 | 비밀 선택(7절). CHOAM 없을 때 전용 |
| `covert_operation_choam` | Covert Operation (작전 변경) | CHOAM 변형 | 10 | 4~7 | 비밀 선택(7절). CHOAM 전용 |
| `mating_season` | Mating Season (교미기) | 단일 | 10 | 4~7 | Maker 칸마다 spice 1 추가(OQ-082) |
| `unlikely_allies` | Unlikely Allies (뜻밖의 동맹) | 단일 | 10 | 4~7 | 이번 라운드, 칸의 Influence 요구를 무시한다 |
| `clear_the_market` | Clear the Market (시장 정리) | CHOAM 변형 | 10 | 4~7 | Imperium Row를 치우고 새로 채운다(OQ-083). CHOAM 없을 때 전용 |
| `clear_the_market_choam` | Clear the Market (시장 정리) | CHOAM 변형 | 10 | 4~7 | Imperium Row를 치우고 새로 채운 뒤, 앞면 Contract 2장도 치우고 새로 채운다. 치운 Contract는 뒷면 더미에 섞는다. CHOAM 전용 |
| `market_opening` | Market Opening (시장 개장) | 단일 | 10 | 4~7 | 이번 라운드 처음 획득되는 The Spice Must Flow의 비용이 Persuasion 2 적다(OQ-081) |
| `eyes_on_arrakis` | Eyes on Arrakis (아라키스를 지켜보는 눈) | 단일 | 10 | 4~7 | 이번 라운드 모든 Faction 칸이 Combat 칸이다 |
| `friends_everywhere` | Friends Everywhere (어디든 있는 벗) | 단일 | 10 | 5~7 | 이번 라운드, Influence 4 도달 보너스를 받을 때 대신 아무 Faction의 보너스를 골라도 된다(OQ-081) |
| `rebuild_infrastructure` | Rebuild Infrastructure (인프라 재구축) | 단일 | 10 | 7 | Shield Wall 토큰이 제거된 상태면, 두 좌석이 각 spice 1을 내서 토큰을 되돌릴 수 있다(OQ-084) |
| `choam_bargain` | CHOAM Bargain (초암 협정) | 단일 | 10 | 4~7 | 각자 선택: 카드 1장 draw, 또는 Contract 1. CHOAM 전용 |
| `ingratiate` | Ingratiate (비위 맞추기) | 단일 | 10 | 4~7 | 각자 선택: specimen 1 → 원하는 Faction +1, 또는 패스. Immortality 풀 |
| `betrayal` | Betrayal (배반) | 단일 | 10 | 4~7 | 각자 선택: Bene Gesserit −1 → Tleilaxu track 1칸, 또는 패스. Immortality 풀 |
| `new_innovations` | New Innovations (새로운 혁신) | 단일 | 10 | 4~7 | 각자 원하면 Solari 1 또는 spice 1을 내고 Research. Immortality 풀 |
| `termination_request` | Termination Request (폐기 요청) | 단일 | 10 | 4~7 | 각자 원하면 손의 카드 1장 trash → specimen 1. Immortality 풀 |
| `offworld_operation` | Offworld Operation (외우주 작전) | 단일 | 10 | 4~7 | 비밀 선택(7절). Immortality 풀 |

- 추첨표의 합(Uprising 풀): 4라운드는 CHOAM 켬 170, 끔 160(Friends Everywhere와 Rebuild Infrastructure가 빠진다). 7라운드는 켬 190.
- 한 게임 등장 확률(Uprising 풀, 앱 분석): 영향력 증가 계열 켬 0.568 / 끔 0.596, Rebuild Infrastructure 켬 0.071 / 끔 0.077.

### 6.1 이번 라운드 규칙 변경의 범위

- **Unlikely Allies.** 칸의 Influence 요구만 무시한다. 비용과 점유 규칙은 그대로다.
- **Eyes on Arrakis.** Faction 칸(Emperor·Spacing Guild·Bene Gesserit·Fremen의 여덟 칸)이 이번 라운드 Combat 칸이다. 그 칸에 Agent를 보낸 turn에는 Combat 칸의 배치 규칙을 쓴다(`[Main p. 10]`).
- **Market Opening.** 탁자 전체에서 이번 라운드에 처음 획득되는 The Spice Must Flow 한 장의 비용이 2 적다(OQ-081).
- **Friends Everywhere.** 이번 라운드에 어느 Faction에서든 Influence 4에 닿아 보너스를 받을 때, 그 Faction 대신 다른 Faction의 4 보너스를 골라도 된다(OQ-081).

## 7. 비밀 선택

`[Scouts event: Covert Operation]` `[Scouts event: Offworld Operation]` `[Scouts help]`

### 7.1 선택

- 이벤트가 공개되면 First Player부터 차례로 각 좌석이 네 가지 중 하나를 **비밀리에** 고른다. 선택은 공개될 때까지 다른 좌석이 모른다.
- 선택에는 공개 라운드(1 또는 2라운드 뒤)가 정해져 있다.

| 이벤트 | 선택 | 공개 | 공개 방식 |
|---|---|---|---|
| Covert Operation(CHOAM 끔) | Spy 1 배치 | 다음 라운드 | 묶음 |
| | Solari 2 | 다음 라운드 | 한 명씩 |
| | 손의 카드 1장 버리기 → troop 3 recruit | 두 라운드 뒤 | 한 명씩 |
| | Influence가 가장 낮은 Faction +1(동률이면 선택) | 두 라운드 뒤 | 묶음 |
| Covert Operation(CHOAM 켬) | Spy 1 배치 | 다음 라운드 | 묶음 |
| | Contract 1 | 다음 라운드 | 묶음 |
| | 손의 카드 1장 버리기 → troop 3 recruit | 두 라운드 뒤 | 한 명씩 |
| | Influence가 가장 낮은 Faction +1(동률이면 선택) | 두 라운드 뒤 | 묶음 |
| Offworld Operation | Solari 2 | 다음 라운드 | 한 명씩 |
| | spice 1, 또는 Helix에 닿았으면 spice 2 | 다음 라운드 | 한 명씩 |
| | Tleilaxu track 1칸 | 두 라운드 뒤 | 묶음 |
| | Intrigue 1장 draw | 두 라운드 뒤 | 묶음 |

### 7.2 공개와 해결

- 공개 라운드의 Scouts 단계 맨 앞(그 라운드의 항목보다 먼저)에 선택을 공개하고 보상을 해결한다. 7라운드에 나온 이벤트의 "두 라운드 뒤"는 9라운드다.
- 앱의 "묶음"은 같은 선택을 한 좌석을 한 화면에 모아 차례 순서로 처리하라는 뜻이다. 엔진은 기한이 된 선택을 모두 공개한 뒤 이벤트가 나온 순서 → 선택지 순서(표의 순서) → First Player부터의 좌석 순서로 해결한다(OQ-085). "한 명씩"도 결과는 같다.
- 보상에 선택이 있으면(Spy를 놓을 관측소, 가져올 Contract, 버릴 카드, 동률 Faction) 그 좌석이 결정한다.
- 기한 전에 게임이 끝나면 그 보상은 사라진다(OQ-085).

## 8. 경매

`[Scouts auction: <이름>]` `[Scouts help]`

### 8.1 봉인 입찰

- First Player부터 차례로 각 좌석이 입찰액을 비공개로 확정한다. 범위는 0부터 가진 자원(경매의 통화)과 상한(99, Mercenaries 3) 중 작은 쪽까지다. 앞선 입찰은 보이지 않는다.
- 모두 확정하면 한꺼번에 공개하고 순위를 매긴다(앱 코드):
  - 입찰액 내림차순의 공동 순위(동점은 같은 순위).
  - 순위가 이기는 자리 수 이내이고 입찰액이 0보다 크면 이긴다. 1위가 동점이면 모두 1위 보상을 받고 2위 보상은 없다. 2위가 여럿 동점이면 모두 2위 보상을 받는다.
  - 이긴 좌석만 입찰액을 낸다. 진 좌석은 내지 않는다(Mercenaries는 예외).
  - 이긴 좌석들의 보상은 First Player부터 차례로 해결한다(앱의 "in turn order", OQ-073).

| id | 이름 (공식 한국어) | 자리 | 통화 | 1위 | 2위 |
|---|---|---|---|---|---|
| `highest_bidder_mid` | To The Highest Bidder (최고 입찰자에게) | 중간 | Solari | 카드 1장 draw | — |
| `highest_bidder_late` | To The Highest Bidder | 후반 | Solari | 카드 2장 draw | 카드 1장 draw |
| `spies_for_hire_mid` | Spies for Hire (스파이 고용) | 중간 | Solari | Spy 1 배치 | — |
| `spies_for_hire_late` | Spies for Hire | 후반 | Solari | Spy 1 배치 + Intrigue 1장 | Spy 1 배치 |
| `choam_negotiations_mid` | CHOAM Negotiations (초암 협상) | 중간 | Solari | Contract 1 | — |
| `choam_negotiations_late` | CHOAM Negotiations | 후반 | Solari | Contract 1 + Intrigue 1장 | Contract 1 |
| `competitive_study_mid` | Competitive Study (경쟁적인 연구) | 중간 | Solari | Research + specimen 1 | — |
| `competitive_study_late` | Competitive Study | 후반 | Solari | Research + specimen 1 | Research |

CHOAM Negotiations는 CHOAM 전용, Competitive Study는 Immortality 풀이다.

### 8.2 Mercenaries (용병단)

- 중간·후반 어느 자리에도 나온다(라운드 5~9). 봉인 입찰로 각자 spice 0~3을 확정한다.
- 공개 뒤 **모두** 입찰한 spice를 내고, 낸 만큼 supply의 troop을 Conflict에 넣는다(부족하면 있는 만큼, OQ-074).
- 가장 적게 낸 좌석은 그렇게 넣은 troop 가운데 원하는 만큼(전부 또는 일부)을 garrison으로 후퇴시킬 수 있다. 최저가 동점이면 모두 그렇다(OQ-074).

### 8.3 공개 경매: Critical Moment (중대한 순간)

- 중간 판은 Imperium 덱 위 2장, 후반 판은 3장을 공개한다.
- First Player부터 시계 방향으로 한 번씩, 1부터 가진 spice까지의 액수를 부르거나 패스한다(최소 1은 OQ-087). **이미 나온 액수와 같은 액수는 부를 수 없다.** 한국어판에는 이 조건이 빠져 있다(OQ-086).
- 가장 높게 부른 좌석이 그 spice를 내고 공개된 카드 1장을 **손으로** 획득한다. 후반 판은 두 번째로 높게 부른 좌석도 원하면 부른 spice를 내고 남은 카드 중 1장을 손으로 획득한다(사지 않으면 내지 않는다, OQ-087).
- 남은 카드는 치운다(OQ-083). 모두 패스한 경우와 덱이 모자란 경우는 OQ-087.

## 9. 판매

`[Scouts sale: <이름>]`. First Player부터 차례로 각 좌석이 두 줄 중 하나를 사거나 패스한다.

| id | 이름 (공식 한국어) | 선택 |
|---|---|---|
| `unravel_the_future` | Unravel the Future (미래의 실타래를 풀다) | spice 1 → 카드 1장 draw, 또는 spice 3 → 카드 2장 draw |
| `imperium_connections` | Imperium Connections (임페리움 접점) | Solari 2 → Spy 1 배치, 또는 Solari 2 → 물 1 |
| `secrets_for_sale` | Secrets for Sale (기밀 정보 판매) | spice 1 → Intrigue 1장, 또는 spice 3 → Intrigue 2장 |
| `shadow_warfare` | Shadow Warfare (그림자 속 전투) | Spy 1 회수 → troop 1 + spice 1, 또는 Spy 2 회수 → troop 3 + spice 2. 이 판매로 recruit한 troop은 곧바로 Conflict에 넣는다 |

Shadow Warfare는 앱에 문구 없이 아이콘만 있다. 화살표 왼쪽을 비용, 오른쪽을 보상으로 읽었다(로컬 분석의 반박 검증도 같은 해석).

## 10. 기존 명세와의 관계

- 항목이 부르는 recruit·Spy 배치와 회수·Influence·Contract·카드 획득·trash·draw는 [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md), [choam-module.md](choam-module.md), [observation-posts.md](observation-posts.md)의 규칙을 그대로 따른다. 예: Spy를 놓을 때 supply에 Spy가 없으면 먼저 하나를 회수한다 `[Main pp. 11, 20]`. 획득 비용 없는 "획득"도 Reserve에서 가져온다.
- Scouts 단계의 recruit는 turn 밖이다. "이번 turn에 recruit한 troop" 배치 규칙 `[Main p. 10]`은 적용되지 않는다. 곧바로 Conflict에 넣으라는 Scouts 단계의 항목(Shadow Warfare, Mercenaries)만 그렇게 한다(OQ-074).
- 임무 칸을 방문해 세워 둔 troop을 받는 것(Security Detail, Fedaykin Assistance, Weirding Warfare, Send for Aid)은 그 좌석의 Agent turn 안에서 일어난다. 그 troop은 그 turn에 recruit한 troop이다(OQ-077).
- 비밀 선택·봉인 입찰의 가시성은 [information-visibility.md](information-visibility.md)에 적는다.
- 공식 문서와 앱이 침묵하는 판정은 [open-questions.md](open-questions.md)의 OQ-071~OQ-090에 기록한다.

## 11. 구현 상태

- 2026-09-28 슬라이스 6a: 5절 임무의 뼈대(`rules/scouts_missions.py`).
  - 공개하면 은행 물품과 뒷면 카드를 놓고(`scouts_goods`, `scouts_goods_cards`), 참여 임무는 First Player부터 좌석마다 참여/패스를 묻는다(frame `scouts_mission`; 참여할 수 없는 좌석은 묻지 않는다, OQ-088).
  - 세워 둔 troop은 `PlayerState.troops_parked`로 12개 보존에 든다(`scouts_parked`가 위치를 적는다).
  - Agent가 그 칸을 방문하면 그 좌석의 조각을 받는 것이 방문 효과 하나로 붙는다(`scouts_collect_mission`, Bloodlines Commander 선례). Security Detail·Weirding Warfare·Send for Aid의 troop은 Conflict로, Fedaykin Assistance의 troop은 이번 turn에 recruit한 troop으로 garrison에, Coordinate With The Emperor의 specimen은 garrison으로 간다(OQ-077). Imperial Reserve는 둘 중 하나를 고른다(OQ-078). Prison Planet은 garrison troop 1을 잃고 지배 마커와 spice 2를 둔다; 마커는 지배 칸과 합쳐 3개를 넘지 않고, 그 좌석이 Conflict 보상으로 세 번째 칸을 지배하게 되면 마커를 가져다 쓰고 spice는 은행으로 돌아간다(`scouts_prison_marker_taken`). CHOAM Research의 뒷면 카드가 Bloodlines의 Immediate이고 방문자에게 Intrigue가 없으면 다음 장을 받는다(OQ-090).
  - CHOAM Research의 Contract 2장과 Emperor's Schemes의 Intrigue 2장은 뒷면이다: 누구도 모르며(`known_card_seats`), 탐색 AI의 재추첨과 비공개 검사에서 bank·덱과 함께 섞이고, 카드 보존 검사에 든다. 방문마다 1장씩 받는다.
  - 관측 v23(임무별 세워 둔 troop과 물품), codec v116.
  - 남은 것(6b): Desert Riding, Valued Informants의 관측소 물품 수령, CHOAM Escort의 완료 보상, Sponsored Research, Back Room Deal, Tleilaxu Offering의 수령. 이들의 물품은 놓이지만 아직 받을 수 없다.
- 2026-09-28 슬라이스 5: 6절의 선택형 이벤트(Immortality 넷 포함)와 9절의 판매, Political Equilibrium, Rebuild Infrastructure.
  - 공개되면 First Player부터 좌석마다 `scouts_choice` frame을 연다. 낼 수 있는 줄만 `scouts_choose_option`으로, 패스가 있으면 `scouts_pass`로 제시한다. 패스가 없는데 할 수 있는 줄이 하나뿐이면 결정 없이 그 줄을, 하나도 없으면 아무것도 하지 않는다(OQ-071). 고른 줄은 슬라이스 4의 `scouts_effect` frame이 푼다.
  - Influence 잃기(`LoseFactionInfluence`, Political Equilibrium의 `LoseHighestInfluence`)는 효과 frame의 선택이다. 동률인 가장 높은 Faction과, Alliance를 넘겨받을 상대가 동률일 때의 받는 좌석을 고른다(`scouts_lose_influence`, `scouts_lose_influence_to`; `[Main p. 7]`의 Alliance 규칙은 기존 `lose_faction_influence`).
  - Rebuild Infrastructure: Shield Wall이 서 있으면 아무 일도 없다. 먼저 내기로 한 두 좌석이 spice 1씩 내면 토큰이 돌아오고, 그 뒤 좌석에는 묻지 않는다. 끝까지 한 좌석뿐이면 아무도 내지 않는다(OQ-084).
  - codec v115. 소크(codec 왕복 검사)가 잡은 결함: 기본 룰셋+Scouts에서 trash 아이콘(Water Discipline)이 여는 기존 선택 trash frame의 행동이 카탈로그에 없었다(그 행동은 Bloodlines·Immortality 카탈로그에만 있었다). Scouts 카탈로그에 더했다.
- 2026-09-28 슬라이스 4: 4절의 소위원회.
  - High Council 칸의 자리 아이콘과 Corrinth City의 자리 획득이 가입 기회 하나를 대기열에 넣고, 엔진이 곧바로 연다(`rules/scouts_effects.py`, frame `scouts_subcommittee`). 비용을 낼 수 있는 빈 소위원회만 제시하고, 하나도 없으면 결정 없이 사라진다. 거절도 기회를 없앤다(OQ-076).
  - 가입하면 그 소위원회의 비용 → 보상 줄을 `scouts_effect` frame이 한 칸씩 푼다. 자동 칸(지불, 자원·recruit·draw·Influence·Contract·specimen·연구·Tleilaxu)은 기존 효과 해석기로, 선택 칸(버릴 카드, trash할 카드·Intrigue, 회수할 Spy, Faction, 회수할 Agent)은 이 frame의 행동으로 푼다. Spy 배치와 선택 trash는 기존 frame을 연다. 같은 frame이 슬라이스 5~8의 모든 좌석별 줄에 쓰인다.
  - Contingencies는 방금 원로회 자리를 얻게 한 Agent(High Council 칸의 Agent)를 뺀 자기 Agent 하나를 회수한다(OQ-075).
  - 자리 아이콘이 그 turn의 마지막 효과여서 turn이 이미 닫혔으면, 가입으로 얻은 것은 새로 열린 turn에 세지 않는다(OQ-044 (d) 선례).
  - 관측: 가입한 소위원회의 칸은 1 + 가입 좌석의 상대 번호. codec v114.
- 2026-09-28 슬라이스 3b: 6.1절의 규칙 변경 넷을 읽는 곳.
  - Unlikely Allies: Agent를 보낼 칸을 고를 때 Influence 요구를 건너뛴다(`agent_turn`).
  - Eyes on Arrakis: Faction 칸 여덟 곳이 Combat 칸이다(`scouts.space_is_combat`). 그 칸에 Agent를 보낸 turn에는 이번 turn에 recruit한 troop과 garrison의 troop 2개까지 배치할 수 있다 `[Main p. 10]`.
  - Market Opening: Reserve 카드의 비용을 읽는 곳을 모두 `acquisition.reserve_cost()` 하나로 모은 뒤, 이번 라운드 처음 획득되는 The Spice Must Flow의 비용을 2 줄인다. 누구든 한 장을 획득하면 할인은 끝난다(OQ-081 (b)).
  - Friends Everywhere: Influence 4에 닿으면 보너스를 바로 주지 않고 대기열에 넣는다. 엔진이 그 좌석에게 네 Faction의 4칸 보너스 중 하나를 고르게 한다(`choose_four_bonus`, frame `scouts_four_bonus`; OQ-081 (a)). Emperor를 고르면 그 Spy 배치가 이어진다. Conflict 보상의 고정 Influence도 같은 대기열을 탄다.
  - codec v113(Scouts 카탈로그만 행동 4개 추가, 다른 룰셋은 그대로).
- 2026-09-28 슬라이스 3a: 2절의 일정 전부와 3절의 흐름.
  - 공개 라운드의 chance frame(`scouts_draw`)으로 뽑는다(`rules/scouts.py`): 1라운드의 소위원회(등급 0·1·2 → 나머지 2개), 임무 배치(70/30)와 임무(계열 제거, 마지막 종류 규칙), 이벤트 추첨표(가중치 × 10), 중간·후반 경매 라운드와 후보, 판매.
  - Scouts 단계는 Control 방어 배치 뒤에 `_advance_automatic`이 한 단위씩 진행하고, 끝나면 First Player의 turn을 연다(그 좌석의 turn 카운터를 전부 다시 찍는다).
  - 자동 이벤트 Mating Season과 Clear the Market(CHOAM 판의 Contract 되섞기 chance 포함)이 동작한다. 규칙 변경 넷은 설정되고 다음 Round Start에 풀린다. 규칙 변경을 읽는 곳은 슬라이스 3b다.
  - 나머지 항목은 공개만 하고 `scouts_item_unimplemented` 이벤트를 남긴다.
  - 관측 v22: Scouts 칸을 벡터 끝에 붙였다. 옵션을 끈 게임은 옛 칸이 바이트 그대로다. `mlp_slots` 체크포인트의 embedding 행은 키로 이관한다.
  - 앱 분석의 정확한 확률(임무 71/180·79/308, 영향력 증가 0.5681·0.5959, Rebuild Infrastructure 0.0712·0.0774)을 추첨표 열거로 재현한다(`tests/unit/rules/test_scouts_schedule.py`).
- 2026-09-28 슬라이스 2: `RulesetConfig(arrakeen_scouts=True)`와 식별자 `+scouts`(맨 뒤). 서버 API·요약·저장 파일·sweep·coverage·대회·PettingZoo 배선, Scouts 게임의 `checkpoint:`·`search:` 좌석 거절(설계 4.9). codec v112(카탈로그 변화 없음). 학습 설정(`train`, `problems`)에는 넣지 않았다(D6). UI 체크박스는 슬라이스 9다.
- 2026-09-28 슬라이스 1: 이 명세, 출처 등록([sources.md](sources.md), [source-map.md](source-map.md)), OQ-071~OQ-089, 용어([glossary-ko.md](glossary-ko.md)), 콘텐츠 카탈로그(`content/arrakeen_scouts/`: 소위원회 14, 임무 16, 이벤트 32, 경매 11, 판매 4)와 추출 데이터 대조 감사([implementation-audits/arrakeen-scouts.md](../implementation-audits/arrakeen-scouts.md)). 엔진 동작은 바뀌지 않았다.
