# Arrakeen Scouts 모듈

**Arrakeen Scouts**(공식 한국어 "아라킨 스카웃" `[KO app: spice.mainmenu.34pgame.label]`)는 Dire Wolf Game Room(Steam)의 Dune: Imperium 컴패니언 앱이 제공하는 3-4인 모드다. 앱이 무작위 일정을 만들고, 라운드마다 그 라운드의 **소위원회**·**임무**·**이벤트**·**경매**·**판매**를 공개한다. 공식 룰북은 없다. 이 문서의 근거는 앱의 정의 데이터·문구·아이콘·코드이며([sources.md](sources.md)의 "Arrakeen Scouts" 절), 효과는 모두 **의역**이다. 앱의 문구(영·한)는 이 저장소에 옮겨 적지 않는다.

프로젝트는 모듈을 `RulesetConfig(arrakeen_scouts=True)` 옵션으로 취급하며 기본값은 꺼짐이다. 설계와 구현 순서는 arrakeen-scouts-design.md(M15)에 있다.

- **인원.** 엔진은 4인 전용이다. 4인 규칙만 옮긴다(소위원회 5개).
- **조합.** `immortality`를 켜면 Uprising+Immortality 풀, 아니면 Uprising 풀을 쓴다. CHOAM 필터는 `choam_module`을 따른다. `rise_of_ix`를 켜면 앱의 Uprising+Ix 풀(Immortality와 함께면 Uprising+Ix+Immortality)이다 — 임무 목록만 다르다: Send for Aid가 빠지고(그 Gather Support를 반쪽 덮개가 덮는다 `[Main p. 18]`) Rise of Ix 임무 셋(Secret Stash, Armed Escort, Stowaways)이 더해진다. 소위원회·이벤트·경매·판매 목록은 Ix가 없는 풀과 같다(2026-10-30 P7f-2, 앱 일정 정의를 기계로 대조 `tests/unit/content/test_arrakeen_scouts_extraction.py`). Bloodlines·Tech·프로모·Leader draft는 풀에 영향이 없다(앱은 Bloodlines 비트를 지우고 풀을 고른다). 모든 조합을 허용한다. `[Scouts schedule]`
- **원판(2026-10-31, P8).** `base_game`이 원판이면 앱의 원판 풀(원판, 원판 + Immortality, 그리고 각각의 + Ix)을 쓴다. 원판 풀은 Uprising 풀과 따로 만든
  목록이라 Spy·관측 초소를 쓰는 항목이 없다. 9a절. 앱이 Ix + Bloodlines에서 묻는 "Ix의 지도자와 Tech 타일만"은 P8-1(2026-11-01)부터
  `ix_leaders`다([rise-of-ix.md](rise-of-ix.md) 10a, OQ-165): 앱처럼 Ix 비트를 지운 풀(Ix 임무 없음)을 쓴다. `rise_of_ix`(Ix 전부)는 앱의 "Ix 전부" 답과
  같은 풀이다. Scouts와 함께는 이 둘만 고를 수 있고, "Ix Tech 타일만"(`ix_tech_tiles` 혼자)은 Scouts와 쓰지 않는다(사용자 판정 2026-11-01).
- **범위 밖.** 3인 플레이, 앱 자체의 저장·이어하기·뒤로 가기.

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

게임이 10 VP(Epic Game Mode에서는 12 VP, [epic-game-mode.md](epic-game-mode.md))나 Conflict 덱 소진으로 먼저 끝나면 남은 항목은 나오지 않는다. 앱도 점수를 판정하지 않고 플레이어가 끝낸다.

### 2.2 추첨 규칙 `[Scouts schedule]`

앱은 게임 시작 때(리더를 고른 뒤) 일정 전체를 만든다. 각 추첨은 앞선 추첨 결과에만 의존한다.

- **소위원회.** CHOAM을 끄면 CHOAM 전용 항목을 뺀다. 등급 0·1·2에서 하나씩 균등 추첨한 뒤, 남은 전체(등급 무관)에서 비복원 균등 추첨으로 5개를 채운다.
- **임무.** CHOAM을 끄면 CHOAM 전용 항목을 뺀다.
  - 세 자리의 라운드는 [2,2,3] (70%) 또는 [2,3,3] (30%)이다.
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
- 이벤트 가중치는 **추첨표**로 표현한다. Uprising 풀은 가중치 × 10을 같은 선택지 수로 둔다(단일 이벤트 10장, 스파이스 획득·책략 보너스 계열의 변형 5장씩, 두 Influence 계열의 변형 6장씩. CHOAM 켬·끔으로 갈리는 Covert Operation과 Clear the Market은 한 게임에 한 변형만 남아 10장). 원판 풀은 가중치가 3 × 0.25·3 × 0.4·3 × 0.15라 × 20이다(9a절). 두 풀에 함께 있는 Immortality 이벤트는 가중치 1이라 Uprising 풀에서 10장, 원판 풀에서 20장이다(`ScoutsEvent.tickets`).

## 3. 라운드 흐름

`[Scouts help]`는 패를 뽑고 Conflict를 공개한 뒤 Scout을 누르라고 한다. Round Start는 Conflict 공개 → (선택) Control 방어 배치 → draw 순서다([setup-and-game-flow.md](setup-and-game-flow.md) 5절, `[Main p. 8]`, `[Main p. 10]`, `[Main p. 20]`; 엔진도 2026-09-29부터 이 순서, OQ-072). **Scouts 단계는 Round Start가 모두 끝난 뒤(방어 배치 뒤), 첫 turn 전에 둔다**(OQ-072). Scouts 단계 안의 순서는 앱과 같다.

1. 이번 라운드가 기한인 비밀 선택 보상(7.2절).
2. 그 라운드의 항목: 1라운드 소위원회 공개, 2·3라운드 임무, 4~7라운드 (중간 경매 →) 이벤트, 8·9라운드 후반 경매 또는 판매.
3. 첫 turn(First Player부터).

Scouts 단계의 결정은 누구의 turn에도 속하지 않는다. "이번 turn에" 세는 효과와 카운터에는 들어가지 않는다.

**차례 순서.** 좌석마다 차례로 결정하는 항목(선택형 이벤트, 판매, 임무 참여, 비밀 선택, 봉인 입찰, 공개 경매)은 First Player부터 시계 방향으로 진행하고, 각 좌석은 자기 차례의 상태로 판단한다(OQ-071, OQ-002 선례).

### 3.1 나중에 받는 줄은 받는 좌석이 눌러서 받는다 (project convention, OQ-164)

사용자 결정(2026-11-01): "아라킨 스카웃 미션 선택으로 받는 것들 있잖아. 자동으로 받게 하지 말고, 플레이어가 무조건 선택으로 클릭해야 받을 수 있게 하자". 보상과 시점은 바꾸지 않는다. 받는 방식만 정한 결정 모델의 관례다(공식 규칙은 받는 방식을 정하지 않는다).

- **대상.** 앞서 한 선택 때문에 나중에 받는 줄: 공개된 비밀 선택의 비용 없는 줄(7.2절)과 경매 승자의 줄(봉인 입찰 8.1절, 원판 Mentat 경매 9a절). 그 줄은 받는 좌석의 "받기"(`scouts_collect_reward`) 한 번을 기다리고, 그 전에는 줄의 어떤 단계도 해결하지 않는다. "받기"는 그 결정의 유일한 행동이다(보상은 거절할 수 없다). 아무것도 주지 못하는 줄(모든 트랙이 꼭대기인 Influence)도 "받기"를 묻는다(결정 창 없이 넘어가는 곳도 창을 연다, 2026-09-30).
- **그대로인 것.** 그 자리에서 고르는 줄은 고르는 클릭이 받는 클릭이다: 이벤트·판매의 선택지, 공개된 비밀 선택의 비용 줄("선택"/"패스", OQ-085 (c)), 소위원회 가입, 임무 참여, Critical Moment의 카드 구매. 임무 칸 방문의 수집은 이미 방문의 효과 행(`scouts_collect_mission`)이다.
- **순서.** 해결 순서는 그대로다(비밀 선택은 이벤트 → 선택지 → First Player부터의 좌석, OQ-085 (b); 경매는 순위 → First Player부터, OQ-073). 좌석이 차례로 누른다. 두 번째 이후 승자 앞의 멈춤도 그대로다(8.1절).
- **줄 안.** "받기" 뒤 줄은 전과 같이 해결된다. 줄 안의 선택(버릴 카드, Faction, Spy 자리, Contract, Research 방향)은 각자의 단계이고, 보상 선택 뒤에 인쇄된 숨은 draw는 그 뒤의 따로 된 단계다(OQ-106). "받기"는 줄의 보상 선택이 아니므로, 선택 없이 곧바로 뽑는 줄(Intrigue 1장, Tleilaxu 토큰이 Intrigue 칸에 닿음)은 "받기"가 뽑는다. 그 "받기"는 무를 수 없고(OQ-010) 화면이 "확정 ▶"으로 보낸다. 아무것도 드러내지 않는 "받기"는 무를 수 있고, 그 좌석이 "턴 종료"를 누를 때까지 서버가 붙든다.
- **숨은 정보.** "받기"는 공개(7.2절) 뒤에만 열리므로 다른 좌석의 비밀 선택을 드러내지 않는다.
- **모두에게 주는 자동 이벤트와 임무 몫(2026-11-01 사용자 판정 "둘 다 클릭으로", 창의 자리는 "둘다 (가)로", OQ-164 (a)·(b)).**
  - 원판 Tap into Spice Reserves(9a): 좌석마다 spice 1을 "받기"로 받는다. First Player부터 차례로. 모두에게 주는 자동 이벤트는 이것 하나다(Mating Season·Clear the Market은 보드만 바꾸고, 규칙 변경 넷은 아무것도 주지 않으며, Political Equilibrium은 이미 모든 좌석에 창을 연다).
  - 임무 몫 다섯: CHOAM Escort의 Contract 위 Solari 1 + spice 1(그 Contract를 완료할 때), Tleilaxu Offering의 troop 2 → specimen 2(자기 Tleilaxu 토큰이 세 번째 칸에 닿을 때), Valued Informants의 관측소 물품(Spy가 그 관측소에 놓일 때, 무엇이 놓았든 — OQ-080), Sponsored Research의 Helix 옆 spice 2(처음 Helix에 닿을 때), Back Room Deal의 Reclaimed Forces 위 Solari 2(그 카드를 "획득"할 때). 생기는 순간 물품은 보드를 떠나 그 좌석의 "받을 몫"이 되고(그 사이 다른 좌석이 가져갈 수 없다), 그 좌석의 "받기"를 기다린다.
  - **창의 자리.** 받기 창은 몫이 생긴 그 전이가 끝나면 곧바로 연다 — 받는 좌석 자신의 turn 한가운데여도(질문 1 (가)), 다른 좌석의 행동 안이어도(질문 2 (가): Holy War·False Orders가 옮긴 Spy가 물품 관측소에 놓임, 다른 좌석의 Influence 손실로 얻은 Alliance가 Earn Any Alliance를 완료함 — 그 turn은 그 클릭을 기다린다; Emperor track Spy가 자기 turn 밖에서 곧바로 열리는 것과 같다). chance 결정이 먼저 있으면 그것이 끝난 뒤 연다. 받기 전에는 그 전이의 다른 일이 이어지지 않아, 뒤따르는 일은 몫을 받은 뒤의 상태를 본다.
  - 물품은 모두 공개 자원이라 이 "받기"는 아무것도 드러내지 않고 무를 수 있다. 줄의 받기와 같은 창·같은 행동(`scouts_collect_reward`)이다.
- 그대로 둔 것(사용자 판정 2026-11-01): 세워 둔 임무 troop의 Conflict 이동(이미 방문의 클릭 안), Mercenaries의 troop 투입(입찰의 대가).

## 4. 소위원회

`[Scouts help]` `[Scouts subcommittee: <이름>]`

- 원로회 자리(High Council seat)를 차지할 때(High Council 칸, Corrinth City), 아직 아무도 가입하지 않은 소위원회 하나에 **가입할 수 있다**. 비용을 내고 보상을 한 번 받는다.
- **가입 시점(project convention, OQ-076 대안 C, 2026-09-30 사용자 판정).** 앱은 자리를 차지할 "때" 가입한다고 적지만, 여기서는 자리를 차지한 **그 turn 안 아무 때나** 다른 효과와 같은 자유 순서로 가입한다("You may carry out all these effects in any order." `[Main p. 9]`). 예: 자리를 차지해 Tech를 spice 1 싸게 사고(`[Bloodlines p. 7]`) 그 다음 소위원회를 고른다, 카드의 Agent 효과를 먼저 풀고 고른다.
  - High Council 칸: 자리 아이콘을 풀면 방문의 효과 목록에 "소위원회 선택"(`choose_subcommittee`, 지금 가입할 수 있는 곳이 있을 때만)이 더해진다. "소위원회 선택"을 누르면 가입할 소위원회를 고른다(`join_subcommittee`, 또는 거절). 쓰지 않고 "턴 종료 ▶"를 누르면 기회는 사라진다(`board_effect_lapsed`; 2026-10-14 OQ-095 (2) 보강, codec v146 — 그 전에는 "소위원회 가입 안 함"(`decline_subcommittee`)을 눌러야 turn이 끝났다).
  - Corrinth City: 그 Reveal turn 안에서 같은 두 행동이 다른 Reveal 효과 옆에 나온다. 가입하거나 거절하기 전에는 Reveal을 마칠 수 없다(묻지 않고 사라지는 기회는 없다).
- 가입은 선택이다. 거절하면 그 기회는 사라진다. 빈 소위원회가 하나도 없어도 기회는 열리고 거절만 남는다(2026-09-30 사용자 판정 "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다", 2026-10-02 구현; 화면은 "소위원회 선택"을 "모든 소위원회에 가입한 좌석이 있음"과 함께 회색으로 둔다; 4인 게임에서는 소위원회가 늘 5개라 일어나지 않는다, OQ-076 (c); 이전 판정(폐기): 빈 소위원회가 하나도 없으면 기회 없이 넘어간다). 빈 소위원회가 있지만 지금 비용을 낼 수 없으면 기회는 열린 채로 남고, turn 중 다른 효과로 비용이 마련되면 그때 고를 수 있다. 이후 원로회 칸을 방문해도 다시 가입할 수 없다(원로회 자리는 한 번만 얻는다). 소위원회 하나에는 한 명만 가입한다(OQ-076).
- 비용 있는 소위원회는 그 비용을 내야 가입한다(`spice.subcommittees.<이름>.instructions`의 괄호, `spice.help.body.uprising`). 비용을 낼 수 있어도 보상이 아무 일도 못 하면(회수할 다른 Agent가 없는 Contingencies) 가입할 수 없다(OQ-071, OQ-075). 자리를 차지한 Agent는 목록을 여는 순간에 정해서, 그 사이 Into the Fray로 Conflict에 간 그 Agent도 회수 대상이 아니다. 화면은 빈 소위원회를 모두 보여 주고 가입할 수 없는 것은 이유와 함께 회색으로 둔다. 지금 가입할 수 있는 곳이 없으면 "소위원회 선택"도 이유와 함께 회색으로 남는다. 아직 풀지 않은 High Council 행동에는 자리를 차지한 직후 가입할 수 있는 소위원회를 미리 보여 준다.
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
| `contingencies` | Contingencies (유사시 대비) | 2 | Intrigue 1장 trash → 방금 보낸 Agent가 아닌 자기 Agent 1개 회수(Into the Fray로 Conflict에 있는 Agent 포함) | OQ-075 |
| `leverage` | Leverage (권위) | 2 | Spy 2 회수 → 원하는 Faction Influence +1 + Intrigue 1장 | Faction을 고른 뒤 Intrigue는 따로 뽑는다(OQ-106) |
| `tleilaxu_relations` | Tleilaxu Relations (협력: 틀레이락스) | 2 | spice 3 → Tleilaxu track 2칸 | Immortality 풀 |

## 5. 임무

`[Scouts help]` `[Scouts mission: <이름>]`

- 임무로 놓인 조각은 라운드가 끝나도 남는다. 보상은 받을 때까지 유효하다. `[Scouts help]`
- 좌석별 참여 결정은 공개 때 First Player부터 차례로 한다. 비용을 낼 수 없는 좌석은 참여하지 않는다(OQ-071, OQ-088).
- 세우는 troop 수는 인쇄된 수 그대로다. 모자라면 참여할 수 없다(OQ-088). Immortality에서는 supply에 모자란 만큼 specimen을 supply로 되돌려 채울 수 있다(CHOAM Escort의 recruit도 같다; `[Immortality p. 8]`, OQ-074).
- 칸 위에 세워 둔 병력은 그 좌석의 troop이다. supply·garrison·Conflict 어디에도 없고, 12개 보존에 함께 센다.
- 방문이 곧바로 Conflict에 넣는 유닛(troop, Armed Escort의 dreadnought, 세워 둔 Commander)은 그 turn에 배치한 unit으로 센다 — Distraction·Coercive
  Negotiation·Diversion의 "units", Masterstroke, Desert Ambush, 그 turn의 배치 최고치가 센다. 기본 배치 한도를 쓰지 않고 회수할 수도 없다(OQ-077 보강
  2026-11-02, 디자이너 판정 "deployed to the conflict this turn").
- Bloodlines에서는 garrison troop을 옮기는 임무(Send for Aid, 9a절의 Genetic Research)에 garrison의 Sardaukar Commander를 대신 보낼 수 있다(둘 다
  있으면 고른다; project convention, [OQ-166](open-questions.md#oq-166--garrison-troop을-옮기는-scouts-임무에-sardaukar-commander), `[Bloodlines
  p. 4]`). 세워 둔 Commander도 그 좌석의 조각이고, 방문 때 곧바로 Conflict에 들어간다.

| id | 이름 (공식 한국어) | 종류 | 라운드 | 내용 |
|---|---|---|---|---|
| `security_detail` | Security Detail (경호 요원) | 0 | 2~3 | 각자 원하면 supply의 troop 1을 Deliver Supplies에 세운다. 그 칸에 처음 Agent를 보낼 때 그 troop을 recruit해 곧바로 Conflict에 배치한다 |
| `imperial_reserve` | Imperial Reserve (제국 비축 물자) | 0 | 2~3 | Imperial Privilege에 spice 1과 Solari 2를 놓는다. 방문자는 둘 중 하나를 가진다. 남은 쪽은 다음 방문자 몫이다(도움말 해설, OQ-078) |
| `desert_riding` | Desert Riding (사막 질주) | 0 | 2~3 | Hagga Basin 옆에 Maker Hooks 토큰을 둔다. 방문자는 칸의 기본 spice 2 대신 그 토큰을 가질 수 있다(Maker 보너스 spice는 그대로). 토큰은 네 Maker Hooks 가운데 하나다(OQ-079) |
| `urban_surveillance` | Urban Surveillance (유익한 정보원 - 도시 감시) | 0 | 2~3 | City 칸에 연결된 빈 관측소마다 Solari 1을 둔다. 그 관측소에 Spy를 놓는 좌석이 그 Solari를 가진다(OQ-080) |
| `planetary_exploration` | Planetary Exploration (유익한 정보원 - 행성 탐사) | 0 | 2~3 | Maker 칸에 연결된 빈 관측소마다 spice 1을 둔다. 받는 방식은 위와 같다 |
| `choam_research` | CHOAM Research (초암 연구) | 0 | 2~3 | 뒷면 Contract 2장을 Research Station에 둔다(Bloodlines의 Immediate는 놓지 않는다, OQ-090). 방문할 때마다 1장씩 가져간다(OQ-078). CHOAM 전용 |
| `choam_escort` | CHOAM Escort (초암 호송대) | 0 | 2~3 | 각자 원하면 둘 중 하나: troop 1 recruit, 또는 자기 앞면 Contract 하나 위에 Solari 1 + spice 1을 올려 두고 그 Contract를 완료할 때 함께 받는다. CHOAM 전용 |
| `sponsored_research` | Sponsored Research (연구 후원) | 0 | 2 | research track의 Helix 옆에 spice 2를 둔다. 다음에 Helix에 닿는 좌석이 가진다. Immortality 풀 |
| `back_room_deal` | Back Room Deal (밀실 거래) | 0 | 2~3 | Tleilaxu Row의 Reclaimed Forces 위에 Solari 2를 둔다. 다음에 Reclaimed Forces를 "획득"하는 좌석이 가진다. Immortality 풀 |
| `prison_planet` | Prison Planet (정예 사다우카 - 감옥 행성) | 1 | 2~3 | 각자 원하면 garrison의 troop 1을 잃고(Bloodlines에서는 garrison의 Sardaukar Commander로 낼 수도 있다, OQ-105), Sardaukar 칸에 자기 Control 마커를 둔다. 은행의 spice 2를 그 위에 둔다. 그 좌석이 그 칸을 방문하면 마커를 되찾고 spice를 얻는다. 세 번째 칸을 지배하게 될 때 마커가 모자라면 이 마커를 가져다 쓰고 임무는 spice 없이 끝난다(도움말). Uprising 풀 |
| `emperors_schemes` | Emperor's Schemes (정예 사다우카 - 황제의 계략) | 1 | 2~3 | Intrigue 2장을 Sardaukar 칸에 둔다(덱이 모자라면 버린 Intrigue를 섞어 채운다). 방문할 때마다 1장씩 가져간다(OQ-078) |
| `fedaykin_assistance` | Fedaykin Assistance (페다이킨의 지원) | 1 | 3 | 각자 원하면 spice 1을 내고 supply의 troop 2를 모두 Desert Tactics에 세운다. 다음에 그 칸을 방문할 때 그 troop을 recruit한다 |
| `weirding_warfare` | Weirding Warfare (기이한 전투) | 1 | 2~3 | 각자 원하면 Solari 2를 내고 supply의 troop 2를 모두 Espionage에 세운다. 다음 방문 때 recruit해 곧바로 Conflict에 배치한다 |
| `send_for_aid` | Send for Aid (지원 제공) | 1 | 2~3 | 각자 원하면 garrison의 troop 1을 Gather Support로 옮긴다(Bloodlines에서는 garrison의 Sardaukar Commander를 대신 보낼 수도 있다, OQ-166). 은행의 물 1을 그 밑에 둔다. 다음 방문 때 그 troop을 recruit해 곧바로 Conflict에 배치하고 물을 얻는다 |
| `coordinate_with_the_emperor` | Coordinate With The Emperor (황제와의 협력) | 1 | 3 | 각자 원하면 specimen 1을 Sardaukar 칸으로 옮긴다. 은행의 Solari 2를 그 밑에 둔다. 그 칸에 처음 Agent를 보낼 때 칸 효과에 더해 Solari 2를 얻고 그 troop을 garrison으로 recruit한다(OQ-089 (c)). Immortality 풀(Prison Planet 대신) |
| `tleilaxu_offering` | Tleilaxu Offering (틀레이락스의 공물) | 1 | 2 | 각자 원하면 supply의 troop 2를 모두 Tleilaxu track의 세 번째 칸에 둔다. 자기 Tleilaxu 토큰이 그 칸에 닿으면 그 troop 2를 specimen으로 Axolotl tanks에 넣는다(OQ-089). Immortality 풀 |
| `secret_stash` | Secret Stash (비자금) | 0 | 3 | 은행의 spice 2를 Smuggling 칸에 둔다. 다음에 그 칸에 Agent를 보내는 좌석이 가진다. Rise of Ix 풀 `[Scouts mission: Secret Stash]` |
| `armed_escort` | Armed Escort (무장 경호) | 0 | 2~3 | 각 좌석이 supply의 dreadnought 1대를 Dreadnought 칸으로 옮기고 은행의 spice 1을 그 밑에 둔다("may"가 없어 의무 — 묻지 않는다). 그 좌석이 그 칸에 처음 Agent를 보낼 때 spice를 가지고 그 dreadnought를 곧바로 Conflict에 배치한다. Rise of Ix 풀 `[Scouts mission: Armed Escort]` |
| `stowaways` | Stowaways (밀항자) | 1 | 2~3 | 각자 원하면 spice 1을 내고 supply의 troop 2를 모두 Smuggling 칸에 세운다. 다음 방문 때 그 troop을 곧바로 Conflict로 옮긴다. Rise of Ix 풀 `[Scouts mission: Stowaways]` |

- **계열.** Desert Riding과 Valued Informants 두 종(Urban Surveillance, Planetary Exploration)은 한 계열이라 셋 중 하나만 나온다. Elite Sardaukar 두 종(Prison Planet, Emperor's Schemes)도 한 계열이고(앱의 제목은 "Valued Informants - …", "Elite Sardaukar - …"처럼 계열 이름을 앞에 붙인다), Immortality 풀에서는 Coordinate With The Emperor가 Prison Planet 대신 그 계열에 들어간다.
- 앱의 데이터에서 Desert Riding과 Urban Surveillance는 같은 id(15.0)를 쓴다. 프로젝트는 앱 id를 식별자로 쓰지 않는다.
- **Rise of Ix 임무(2026-10-30 P7f-2).** 앱 정의(`Def_Mission_SecretStash`·`ArmedEscort`·`Stowaways`: 라운드 창, missionType, 계열 6·7·8)와 문구(`spice.mission.muster.secretstash.desc`, `spice.mission.armedescort.desc`, `spice.mission.stowaways.desc`)에서 옮겼다. 셋 다 계열이 따로라 서로 막지 않는다.
  - Stowaways는 Weirding Warfare와 같은 장치(세워 둔 troop을 방문 때 Conflict로, OQ-077)이고, Secret Stash는 Imperial Reserve처럼 누구나 받는 물품이다.
  - Armed Escort의 dreadnought는 세워 둔 조각(`scouts_parked`, 그 임무의 행은 troop이 아니라 dreadnought, `PlayerState.dreadnoughts_parked`)이고 supply·garrison·Conflict 어디에도 없다. **project convention(앱 문장에 없음):** supply에 dreadnought가 없는 좌석은 아무것도 놓지 않는다(spice도 없음) — 인쇄된 수를 낼 수 없으면 참여할 수 없다는 OQ-088과 같은 원칙. 유닛을 배치할 수 없는 turn(Shaddam)이면 그 dreadnought는 garrison으로 간다 — 임무 troop의 OQ-130과 같다. 칸 자체의 효과는 그대로 해결한다(다른 임무의 방문 수집과 같다).
- **Prison Planet의 지배 마커(2026-09-30 원문 재확인).** 앱은 좌석 **자신의 지배 마커 하나**를 놓게 한다(`spice.mission.elitesardaukar.prisonplanet.desc`의 "one of their control markers"; 참여 표시용 별도 토큰이 아니다). 지배 마커는 색마다 3개이고 지배 칸도 3개다("Control marker 3개" `[Main p. 3]`, `setup-and-game-flow.md`; Arrakeen·Spice Refinery·Imperial Basin `[Main p. 10]`). 모자라는 경우는 앱 도움말이 직접 정한다: 세 번째 칸을 지배하게 되는데 마커가 아직 Sardaukar에 있으면 그 마커를 가져와 세 번째 칸에 놓고, 그 좌석은 임무를 더 완수할 수 없으며 spice를 얻지 못한다(`spice.help.body.uprising`의 Clarifications). 기본판 일정의 Sapho Juice(Mentat 칸)도 같은 방식과 같은 해설을 쓴다(`spice.mission.saphojuice.desc`, `spice.help.body`). 그래서 기본 규칙의 마커 3개는 넘지 않는다. **project convention(앱 문장에 없음):** 되가져간 마커 위의 spice 2는 은행으로 돌아간다("gains no spice"만 있다), 잃은 garrison troop은 돌려받지 않는다, 세 마커를 모두 쓴 좌석(지배 칸 + 임무 위 마커 = 3)에게는 참여를 묻지 않는다(놓을 마커가 실물로 없다). 구현: `rules/scouts_missions.py` `free_prison_marker`·참여 검사, `rules/combat.py`의 지배 보상 직전 호출; `tests/unit/rules/test_scouts_missions.py`의 prison 테스트 셋.

## 6. 이벤트

`[Scouts event: <이름>]`. 표의 "추첨표"는 한 라운드 추첨표에서 그 이벤트가 차지하는 선택지 수다(2.3절).

- **선택형.** "각자 선택"인 이벤트는 First Player부터 차례로 한 가지를 고른다(앱 영어의 "in turn order"; 한국어판에는 빠져 있다. Moment of Revelation의 문구에는 순서 말이 없어 같은 순서가 프로젝트 convention이다, OQ-071). "또는 패스"가 있으면 선택하지 않아도 된다. 패스가 없으면 반드시 하나를 해야 하며, 할 수 없는 쪽은 고를 수 없다(한 쪽만 할 수 있어도 결정은 열리고 할 수 없는 쪽은 회색으로 보인다). 둘 다 할 수 없으면 아무 일도 없다(도움말, OQ-071) — 그래도 그 좌석에게 결정 창이 열려 회색 줄과 "할 수 있는 선택 없음 — 확인"을 보인다(2026-10-17 사용자 결정, 정리-2a, OQ-071 보강).
- **이번 라운드 규칙 변경.** 공개된 라운드가 끝날 때까지 적용된다.

| id | 이름 (공식 한국어) | 계열 | 추첨표 | 라운드 | 내용 |
|---|---|---|---|---|---|
| `private_stock` | Private Stock (개인 비축품) | 스파이스 획득 | 5 | 4~7 | 각자 선택: spice 1, 또는 카드 1장 draw |
| `market_research` | Market Research (시장 조사) | 스파이스 획득 | 5 | 4~7 | 각자 선택: Spy 1 회수 → spice 2, 또는 패스 |
| `smoke_and_mirrors` | Smoke and Mirrors (진실의 왜곡) | 책략 보너스 | 5 | 4~7 | 각자 선택: Spy 1 배치, 또는 Solari 1 → Intrigue 1장 |
| `rotating_doors` | Rotating Doors (회전문) | 책략 보너스 | 5 | 4~7 | 각자 선택: Intrigue 1장 trash → Intrigue 1장 + 카드 1장 draw, 또는 패스 |
| `moment_of_revelation` | Moment of Revelation (폭로의 순간) | 단일 | 10 | 4~7 | 각자 원하면 spice 2를 내고 Reserve의 Prepare the Way를 **손으로** 획득. Reserve에 남은 카드가 없으면 제시하지 않고 spice도 받지 않는다(OQ-071) |
| `water_discipline` | Water Discipline (물 규칙) | 단일 | 10 | 4~7 | 각자 선택: 물 1 → 카드 1장 trash + 카드 1장 draw, 또는 패스. trash와 draw는 원하는 순서(OQ-100)이고, trash를 먼저 하면 draw는 따로 한다(OQ-106) |
| `royal_delegation` | Royal Delegation (왕실 대표단) | 영향력 증가 | 6 | 4~7 | 각자 선택: Solari 2 → Emperor +1, 또는 패스 |
| `guild_negotiation` | Guild Negotiation (길드 협상) | 영향력 증가 | 6 | 4~7 | 각자 선택: spice 1 + 손의 카드 1장 버리기 → Spacing Guild +1, 또는 패스 |
| `covert_assistance` | Covert Assistance (비밀스러운 지원) | 영향력 증가 | 6 | 4~7 | 각자 선택: Spy 1 회수 → Bene Gesserit +1, 또는 패스 |
| `gift_of_water` | Gift of Water (물이 가져다 준 선물) | 영향력 증가 | 6 | 4~7 | 각자 선택: 물 1 → Fremen +1, 또는 패스 |
| `share_intelligence` | Share Intelligence (정보 공유) | 영향력 증가 | 6 | 4~7 | 각자 선택: Intrigue 1장 trash + Solari 1 → 원하는 Faction +1, 또는 패스 |
| `political_equilibrium` | Political Equilibrium (정치적 균형) | 영향력 축소 | 6 | 4~7 | 모두 자기 Influence가 가장 높은 Faction에서 −1. 동률이면 그중 하나를 고른다. First Player부터 한 좌석씩 처리한다(Alliance가 오갈 수 있어 순서가 결과를 바꾼다, OQ-071). 모든 좌석에 창을 연다 — 가장 높은 Faction이 하나면 그 한 줄, 모두 0이면 "잃을 영향력 없음" 확인(OQ-131 보강, 2026-10-25 사용자) |
| `crackdown` | Crackdown (강력 단속) | 영향력 축소 | 6 | 4~7 | 각자 선택: Spy 1 회수, 또는 Emperor −1 |
| `water_for_spice_smugglers` | Water for Spice Smugglers (밀수업자들에게 물 제공) | 영향력 축소 | 6 | 4~7 | 각자 선택: 물 1 잃기, 또는 Spacing Guild −1 |
| `bene_gesserit_treachery` | Bene Gesserit Treachery (베네 게세리트의 음모) | 영향력 축소 | 6 | 4~7 | 각자 선택: garrison의 troop 1 잃기, 또는 Bene Gesserit −1. Bloodlines에서는 garrison의 Sardaukar Commander로도 낼 수 있고, 둘 다 있으면 고른다(OQ-105) |
| `funeral_rites` | Funeral Rites (장례 의식) | 영향력 축소 | 6 | 4~7 | 각자 선택: 손의 카드 1장 trash, 또는 Fremen −1 |
| `covert_operation` | Covert Operation (작전 변경) | CHOAM 변형 | 10 | 4~7 | 비밀 선택(7절). CHOAM 없을 때 전용 |
| `covert_operation_choam` | Covert Operation (작전 변경) | CHOAM 변형 | 10 | 4~7 | 비밀 선택(7절). CHOAM 전용 |
| `mating_season` | Mating Season (교미기) | 단일 | 10 | 4~7 | Maker 칸마다 spice 1 추가(OQ-082) |
| `unlikely_allies` | Unlikely Allies (뜻밖의 동맹) | 단일 | 10 | 4~7 | 이번 라운드, 칸의 Influence 요구를 무시한다 |
| `clear_the_market` | Clear the Market (시장 정리) | CHOAM 변형 | 10 | 4~7 | Imperium Row를 치우고 새로 채운다(OQ-083). CHOAM 없을 때 전용 |
| `clear_the_market_choam` | Clear the Market (시장 정리) | CHOAM 변형 | 10 | 4~7 | Imperium Row를 치우고 새로 채운 뒤, 앞면 Contract 2장도 치우고 새로 채운다. 치운 Contract는 뒷면 더미에 섞는다. bank가 모자라도 교체하고 있는 만큼만 채운다(OQ-083). CHOAM 전용 |
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
- 비용 없는 줄은 그 좌석이 "받기"를 눌러야 해결된다(3.1절, OQ-164). 비용 줄은 "선택"/"패스"가 그 클릭이다.
- 기한 전에 게임이 끝나면 그 보상은 사라진다(OQ-085).

## 8. 경매

`[Scouts auction: <이름>]` `[Scouts help]`

### 8.1 봉인 입찰

- First Player부터 차례로 각 좌석이 입찰액을 비공개로 확정한다. 범위는 0부터 가진 자원(경매의 통화)과 상한(99, Mercenaries 3) 중 작은 쪽까지다. 앞선 입찰은 보이지 않는다.
- 모두 확정하면 한꺼번에 공개하고 순위를 매긴다(앱 코드):
  - 입찰액 내림차순의 공동 순위(동점은 같은 순위).
  - 순위가 이기는 자리 수 이내이고 입찰액이 0보다 크면 이긴다. 1위가 동점이면 모두 1위 보상을 받고 2위 보상은 없다. 2위가 여럿 동점이면 모두 2위 보상을 받는다.
  - 이긴 좌석만 입찰액을 낸다. 진 좌석은 내지 않는다(Mercenaries는 예외).
  - 이긴 좌석들의 보상은 순위대로(1위 먼저) 해결하고, 같은 순위끼리는 First Player부터 차례로 해결한다(OQ-073). 앱 영어의 "turn order"는 1위 동점의 괄호에만 있다.
  - 두 번째 이후 각 승자의 보상 전에 엔진이 멈춘다(project convention, OQ-103·OQ-106): Competitive Study 2위의 Research가 1위의 방향 선택과 한 단계에서 카드를 뽑지 않게. Spies for Hire·CHOAM Negotiations 후반 1위의 Intrigue는 Spy 배치·Contract 뒤의 따로 된 단계다(OQ-106).
  - 각 승자의 줄은 그 좌석이 "받기"를 눌러야 해결된다(3.1절, OQ-164). 원판 Mentat 경매 승자의 줄도 같다.

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

- 중간·후반 어느 자리에도 나온다(라운드 5~9). 봉인 입찰로 각자 spice 0~3을 확정한다. 상한은 넣을 수 있는 troop 수(supply, Immortality면 specimen 포함)도 넘지 않는다(OQ-074).
- 공개 뒤 **모두** 입찰한 spice를 내고, 낸 만큼 troop을 Conflict에 넣는다. supply가 모자라면 그만큼 specimen을 자동으로 supply로 되돌려 채운다(Immortality, OQ-074).
- 1 이상 입찰한 좌석 가운데 가장 적게 낸 좌석은 그렇게 넣은 troop 가운데 원하는 만큼(전부 또는 일부)을 garrison으로 후퇴시킬 수 있다. 최저가 동점이면 모두 그렇다. 0은 입찰이 아니라 후퇴하지도 남을 막지도 않는다(OQ-074, 2026-09-29 사용자 결정). 이 후퇴는 게임의 후퇴다(앱 영어의 동사가 retreat): Chani의 Tactics token이 후퇴한 troop 수만큼 전진한다(OQ-074).

### 8.3 공개 경매: Critical Moment (중대한 순간)

- 중간 판은 Imperium 덱 위 2장, 후반 판은 3장을 공개한다. 덱이 그보다 적으면 그 라운드의 경매 추첨에서 이 경매를 뺀다(OQ-087).
- First Player부터 시계 방향으로 한 번씩, 1부터 가진 spice까지의 액수를 부르거나 패스한다(최소 1은 OQ-087). **이미 나온 액수와 같은 액수는 부를 수 없다.** 한국어판에는 이 조건이 빠져 있다(OQ-086).
- 가장 높게 부른 좌석이 그 spice를 내고 공개된 카드 1장을 **손으로** 획득한다. 후반 판은 두 번째로 높게 부른 좌석도 원하면 부른 spice를 내고 남은 카드 중 1장을 손으로 획득한다(사지 않으면 내지 않는다, OQ-087).
- 남은 카드는 게임에서 뺀다(앱 영어는 discard; Imperium 카드의 버림 더미가 없어 게임에서 빼는 것으로 읽는다, OQ-083). 모두 패스한 경우와 덱이 모자란 경우는 OQ-087.

## 9. 판매

`[Scouts sale: <이름>]`. First Player부터 차례로 각 좌석이 두 줄 중 하나를 사거나 패스한다.

| id | 이름 (공식 한국어) | 선택 |
|---|---|---|
| `unravel_the_future` | Unravel the Future (미래의 실타래를 풀다) | spice 1 → 카드 1장 draw, 또는 spice 3 → 카드 2장 draw |
| `imperium_connections` | Imperium Connections (임페리움 접점) | Solari 2 → Spy 1 배치, 또는 Solari 2 → 물 1 |
| `secrets_for_sale` | Secrets for Sale (기밀 정보 판매) | spice 1 → Intrigue 1장, 또는 spice 3 → Intrigue 2장 |
| `shadow_warfare` | Shadow Warfare (그림자 속 전투) | Spy 1 회수 → troop 1 + spice 1, 또는 Spy 2 회수 → troop 3 + spice 2. 이 판매로 recruit한 troop은 곧바로 Conflict에 넣는다 |

Shadow Warfare의 두 줄은 아이콘이고(화살표 왼쪽이 비용, 오른쪽이 보상), 이 판매로 recruit한 troop은 모두 Conflict에 곧바로 배치한다는 문구 한 줄이 따로 있다(`spice.sale.description.shadowwarfare2`; 2026-09-29 확인 — 전에는 아이콘만 있다고 잘못 적었다).

## 9a. 원판의 일정 풀 (2026-10-31, P8)

`[Scouts schedule]` 앱의 원판 풀 넷(원판, + Ix, + Immortality, + Ix + Immortality; 앱 코드 `SpiceDataController.get_Schedule`, 계획
base-game-and-ix-plan.md 20.1). 일정 생성(2절)·라운드 흐름(3절)·비밀 선택(7절)·경매 순위(8.1절)·판매(9절)의 절차는 같고, 앱의
원판 도움말도 같은 절차다(`spice.help.body`; Clarifications는 Sapho Juice 하나). 원판 판에는 CHOAM 모듈이 없다(앱도 원판에서는 묻지 않는다; 엔진은
원판 + CHOAM을 열지 않는다, 계획 19.4 P7-1).

- **Spy를 쓰는 항목은 없다.** 원판 풀은 Uprising 풀과 따로 만든 목록이다. Spy·관측 초소를 쓰는 Uprising 항목(Leverage, Valued Informants 둘, Market
  Research, Smoke and Mirrors, Covert Assistance, Crackdown, Covert Operation 두 판, Spies for Hire, Imperium Connections, Shadow Warfare)은 원판 풀에 없다.
- **같은 정의, 다른 문구.** Appropriations·Intelligence·Oversight는 두 판이 한 정의를 쓰고, 앱은 Uprising 판에서만 `.uprising` 문구를 쓴다. 원판에서는
  아래의 원판 줄이다. 엔진은 원판 줄을 따로 된 기록(`imperium_*` id)으로 둔다.
- **두 판이 같이 쓰는 것.** Readiness, Investigations, Relations, To The Highest Bidder 두 판, Mercenaries, Unravel the Future, Immortality 항목(소위원회
  셋, 임무 셋, 이벤트 다섯, Competitive Study 두 판), Rise of Ix 임무 셋(Secret Stash, Armed Escort, Stowaways — 원판 + Ix 판의 Ix 보드 칸).
- **Rise of Ix.** 원판 + Ix 풀은 Muster an Army 둘(Rally Troops — Ix 덮개가 덮는다, [rise-of-ix.md](rise-of-ix.md) 3)과 Guild Maneuvers를 빼고 Rise of
  Ix 임무 셋을 더한다. 다른 목록은 같다. Guild Maneuvers를 빼는 근거는 덮인 칸이 아니라(Foldspace는 원판 + Ix 보드에 남는다) 앱의 `base+Ix` 일정
  정의의 `availableMissions`에 그 임무가 없다는 것뿐이다(앱은 이유를 적지 않는다; `test_the_rise_of_ix_pools_differ_only_in_missions`가 추출본과 대조).
- **이벤트 가중치.** 스파이스 획득·책략 보너스 계열의 변형은 1 × 0.5, 영향력 증가 계열 변형은 3 × 0.25, 영향력 축소 계열은 Political Equilibrium
  3 × 0.4와 나머지 넷 3 × 0.15, 나머지는 1이다. 추첨표는 × 20이다(10·10, 15씩, 24와 9씩, 20).

**소위원회.** (같이 쓰는 Readiness·Investigations·Relations와 Immortality 셋은 4절.)

| id | 이름 (공식 한국어) | 등급 | 비용 → 보상 |
|---|---|---|---|
| `imperium_appropriations` | Appropriations (재무) | 0 | 없음 → spice 1 |
| `imperium_intelligence` | Intelligence (정보) | 0 | 없음 → 카드 1장 draw |
| `imperium_oversight` | Oversight (관리감독) | 1 | Solari 1 → 카드 1장 trash(trash 아이콘이라 선택, 4절의 Oversight와 같다) |
| `joint_forces` | Joint Forces (합동군) | 1 | Solari 2 → troop 3 recruit |
| `development` | Development (개발) | 2 | spice 3 → 카드 3장 draw |
| `political_affairs` | Political Affairs (정치) | 2 | spice 4 → 한 진영 Influence 2(두 진영에 나누지 않는다 `[DI p. 16]`) |

**임무.** (같이 쓰는 Immortality 셋과 Rise of Ix 셋은 5절.) 5절의 공통 규칙(차례 순서 참여, 인쇄된 수, specimen 보충 OQ-074, 칸 위의 troop은 그 좌석의
troop)이 같다.

| id | 이름 (공식 한국어) | 종류 | 라운드 | 내용 |
|---|---|---|---|---|
| `space_travel_deal` | Space Travel Deal (우주 여행 계약) | 0 | 2~3 | 은행의 Solari 3을 Heighliner 칸에 둔다. 다음에 그 칸에 Agent를 보내는 좌석이 가진다 |
| `muster_spice_incentive` | Muster an Army - Spice Incentive (군대 모병 - 스파이스 인센티브) | 0 | 2~3 | 은행의 spice 2를 Rally Troops 칸에 둔다. 다음 방문자가 가진다. Ix 없는 풀 |
| `muster_strongarmed_alliance` | Muster an Army - Strongarmed Alliance (군대 모병 - 강인한 동맹) | 0 | 2~3 | 각 좌석이 supply의 troop 1을 Rally Troops 칸에 세운다("may"가 없어 의무 — 묻지 않는다; supply에 없으면 놓지 않는다, OQ-088. Immortality에서 supply가 비고 specimen이 있으면 그 좌석은 먼저 specimen 1을 supply로 되돌릴 수 있다 — OQ-074 (a) 보강의 "supply보다 많은 troop을 요구받은 좌석"이라 그 선택만 묻는다). 그 좌석이 그 칸에 처음 Agent를 보낼 때 칸 효과에 더해 그 troop을 곧바로 Conflict에 배치한다. Muster 둘은 한 계열. Ix 없는 풀 |
| `botanical_stationed_support` | Botanical Testing - Stationed Support (식물학 실험 - 주둔 지원) | 0 | 2~3 | 각자 원하면 손의 카드 1장을 버리고 supply의 troop 2를 Research Station 칸에 세운다. 그 칸에 처음 Agent를 보낼 때 칸 효과에 더해 곧바로 Conflict에 배치한다. 버리기가 비용이라 먼저다("비용은 효과보다 먼저" `[DI p. 9]`, [imperium-base.md](imperium-base.md) 8). 버린 카드의 Unload(Rise of Ix)는 끝까지 해결한 뒤 세운다(디자이너 판정, [rise-of-ix.md](rise-of-ix.md) 7). 그 사이 supply가 2보다 적어지면 있는 만큼만 세운다(OQ-030 "해결 시점의 supply만큼", OQ-074 (a); Immortality면 먼저 specimen을 되돌릴 수 있다). 손이 비면 참여할 수 없다(OQ-088) |
| `botanical_secrets_in_the_desert` | Botanical Testing - Secrets in the Desert (식물학 실험 - 사막의 비밀) | 0 | 2~3 | Intrigue 덱 위 2장을 Research Station 칸에 둔다. 그 칸에 Agent를 보낸 좌석이 한 장씩 가져갈 수 있다(같은 좌석이 두 번 가져갈 수 있다 — 영어 문구가 권위, 1절). 가져가지 않을 수도 있다("may" — 원판의 Secrets 칸은 Intrigue 4장 이상인 상대에게서 한 장을 받아 가므로 받지 않는 것이 뜻이 있다, [imperium-base.md](imperium-base.md) 8). 남은 카드는 다 가져갈 때까지 칸에 남는다(OQ-078 "칸 위 물품은 모두 다 가져갈 때까지 남는다"; 앱 문구의 "다음 두 번"은 카드 두 장이다). Botanical Testing 둘은 한 계열 |
| `genetic_research` | Genetic Research (유전학 연구) | 1 | 2~3 | 각자 원하면 garrison의 troop 1을 Selective Breeding 칸으로 옮기고(Bloodlines에서는 garrison의 Sardaukar Commander를 대신 보낼 수도 있다, OQ-166) 은행의 Solari 2를 그 밑에 둔다. 그 칸에 처음 Agent를 보낼 때 칸 효과에 더해 Solari 2를 얻고 그 troop을 곧바로 Conflict에 배치한다 |
| `sapho_juice` | Sapho Juice (사포 주스) | 1 | 2~3 | 각 좌석이 자기 Control marker 하나를 Mentat 칸에 두고 은행의 spice 1을 그 위에 둔다(의무). 그 좌석이 Mentat 칸에 Agent를 보내면 자기 marker와 spice를 가져간다(앱은 "may"; 되찾는 것이 늘 이득이라 5절 Prison Planet의 같은 문구처럼 방문 때 가져간다). 세 번째 지배 칸에 marker가 필요한데 아직 Mentat 칸에 있으면 그것을 가져다 쓰고, 그 좌석은 임무를 더 못 하며 spice를 받지 못한다(앱 도움말; 5절 Prison Planet의 project convention과 같다) |
| `guild_maneuvers` | Guild Maneuvers (길드와의 연합 작전) | 1 | 3 | 각자 원하면 spice 1을 내고 supply의 troop 2를 Foldspace 칸에 세운다. 그 칸에 Agent를 보낼 때 그 troop을 곧바로 Conflict로 옮긴다. Ix 없는 풀 |
| `imperium_coordinate_with_the_emperor` | Coordinate With The Emperor (황제와의 협력) | 1 | 3 | 각자 원하면 specimen 1을 Conspire 칸으로 옮기고 은행의 Solari 2를 그 밑에 둔다. 그 칸에 처음 Agent를 보낼 때 칸 효과에 더해 Solari 2를 얻고 그 troop을 garrison으로 recruit한다(5절의 Uprising 판과 같은 장치, OQ-089 (c)). 원판 + Immortality 풀, 계열은 Uprising 판과 따로 |

**이벤트.** (같이 쓰는 Immortality 다섯은 6절.) 6절의 공통 규칙(차례 순서, 할 수 없는 쪽은 고를 수 없음)이 같다.

| id | 이름 (공식 한국어) | 계열 | 라운드 | 내용 |
|---|---|---|---|---|
| `tap_into_spice_reserves` | Tap into Spice Reserves (스파이스 비축품 활용) | 스파이스 획득 | 4~7 | 모두 spice 1을 얻는다(앱은 자동; 여기서는 좌석마다 "받기", 3.1절·OQ-164 (a)) |
| `assassination` | Assassination (암살) | 스파이스 획득 | 6~7 | 각자 원하면 손의 카드 1장 trash → spice 2 |
| `imperium_secrets_for_sale` | Secrets for Sale (기밀 정보 판매) | 책략 보너스 | 4~7 | 각자 원하면 Solari 1 또는 spice 1 → Intrigue 1장 |
| `imperium_rotating_doors` | Rotating Doors (회전문) | 책략 보너스 | 6~7 | 각자 원하면 Intrigue 1장 버리기(Intrigue 버림 더미로, trash가 아니다) → Intrigue 1장 |
| `change_of_plans` | Change of Plans (계획 변경) | 단일 | 4~7 | 각자 원하면 카드 1장 버리기 → 카드 1장 draw |
| `no_coming_back` | No Coming Back (귀환은 없다) | 단일 | 4 | 각자 원하면 손의 시작 카드 1장을 trash한다. Seek Allies면 원하는 진영 Influence 1, Diplomacy면 한 진영 Influence 2. 다른 시작 카드는 보상 없이 trash할 수 있다(문장대로; 그런 카드가 손에 있을 때만 그 줄을 준다). 시작 카드는 각 좌석이 게임을 시작할 때 받은 카드다 — 시작 덱과, Immortality + Epic에서 버림 더미로 시작하는 Control the Spice(`[Immortality p. 12]`) |
| `imperium_covert_operation` | Covert Operation (작전 변경) | 단일 | 4~7 | 비밀 선택(7절): 다음 라운드 Solari 2 / 다음 라운드 카드 1장 버리기 → 지금 고른 진영 Influence 1 / 두 라운드 뒤 spice 2 / 두 라운드 뒤 카드 2장 버리기 → 지금 고른 진영 Influence 2. 진영은 선택과 함께 숨는다. 공개 때 버리기는 7.2절의 다른 비용 줄처럼 내지 않고 넘길 수 있다(OQ-085 (c)); 손이 모자라거나 고른 진영이 이미 꼭대기면 그 줄은 제시되지 않는다(OQ-071, OQ-060) |
| `imperium_gift_of_water` | Gift of Water (물이 가져다 준 선물) | 단일 | 4~7 | 각자 원하면 물 1 → Reserve의 Arrakis Liaison 1장을 손으로 |
| `test_of_loyalty` | Test of Loyalty (충성심 테스트) | 영향력 증가 | 4~7 | 각자 선택: garrison의 troop 1 잃기 → Emperor +1, 또는 패스 |
| `imperium_guild_negotiation` | Guild Negotiation (길드 협상) | 영향력 증가 | 4~7 | 각자 선택: Solari 2 → Spacing Guild +1, 또는 패스 |
| `intriguing_gift` | Intriguing Gift (흥미로운 선물) | 영향력 증가 | 4~7 | 각자 선택: Intrigue 1장 버리기 → Bene Gesserit +1, 또는 패스 |
| `desert_gift` | Desert Gift (버림받은 선물) | 영향력 증가 | 4~7 | 각자 선택: 시작 카드(No Coming Back 줄의 정의)가 아닌 카드 1장 버리기 → Fremen +1, 또는 패스 |
| `imperium_political_equilibrium` | Political Equilibrium (정치적 균형) | 영향력 축소 | 5~7 | 모두 Influence가 가장 높은 진영에서 1을 잃는다(동률이면 고른다; 자동, 6절의 Uprising 판과 같다) |
| `emperors_tax` | The Emperor's Tax (황제가 거두는 세금) | 영향력 축소 | 5~7 | 각자 선택: spice 1 잃기, 또는 Emperor −1 |
| `imperium_water_for_spice_smugglers` | Water for Spice Smugglers (밀수업자들에게 물 제공) | 영향력 축소 | 5~7 | 각자 선택: 물 1 잃기, 또는 Spacing Guild −1 |
| `imperium_bene_gesserit_treachery` | Bene Gesserit Treachery (베네 게세리트의 음모) | 영향력 축소 | 5~7 | 각자 선택: 카드 1장 버리기, 또는 Bene Gesserit −1 |
| `fremen_exchange` | Fremen Exchange (프레멘과의 거래) | 영향력 축소 | 5~7 | 각자 선택: troop 1 잃기 — garrison이나 Conflict에서, Bloodlines면 Commander도(OQ-163) — 또는 Fremen −1 |

**경매.** (같이 쓰는 To The Highest Bidder·Mercenaries·Competitive Study는 8절.)

| id | 이름 (공식 한국어) | 자리 | 방식 | 통화 | 1위 | 2위 |
|---|---|---|---|---|---|---|
| `mentat_mid` | Mentat (멘타트) | 중간 | 공개 | Solari | 이번 라운드의 Mentat(없으면 원하는 진영 Influence 1, OQ-162) | — |
| `mentat_late` | Mentat | 후반 | 공개 | spice | 이번 라운드의 Mentat + 카드 1장 draw(Mentat이 없는 라운드에는 추첨에서 빠진다, OQ-162) | — |
| `treachery_mid` | Treachery (배반) | 중간 | 봉인 | spice | Intrigue 1장 | — |
| `treachery_late` | Treachery | 후반 | 봉인 | spice | Intrigue 2장 | Intrigue 1장 |

- **Mentat 공개 경매.** First Player부터 시계 방향으로 한 번씩, 앞선 최고 호가보다 높은 액수(1부터 가진 통화까지)를 부르거나 패스한다(OQ-162 (3)).
  가장 높게 부른 좌석이 그 액수를 내고 Mentat을 가져와 이번 라운드에 Agent로 쓴다([imperium-base.md](imperium-base.md) 9의 Mentat 아이콘). 모두
  패스하면 아무 일도 없다. Mentat 두 판은 한 계열이라 한 게임에 하나만 나온다. Treachery는 8.1절의 봉인 입찰이다(이긴 좌석만 낸다).

**판매.** (같이 쓰는 Unravel the Future는 9절.)

| id | 이름 (공식 한국어) | 선택 |
|---|---|---|
| `water_peddlers` | Soo-Soo Sook! Water Peddlers (수수 숙! 물장수) | 차례로: Solari 2 → 물 1, 또는 Solari 4 → 물 2 |
| `fremen_mercenaries` | Fremen Mercenaries (프레멘 용병) | 각자 원하는 만큼 물을 내고 물마다 troop 2를 recruit해 곧바로 Conflict에 배치한다. 엔진은 물 1~6개를 줄 여섯으로 둔다(좌석의 troop은 12). 판매 줄이라 항목 줄의 규칙이 그대로다: 낼 수 있고 troop을 하나라도 넣을 수 있는 줄을 주고(OQ-071), supply가 모자라면 그 좌석이 먼저 specimen을 되돌릴지 고르며(OQ-074 (a) 보강, Shadow Warfare와 같다), 넣는 것은 그때 supply에 있는 만큼이다(OQ-030) |

## 10. 기존 명세와의 관계

- 항목이 부르는 recruit·Spy 배치와 회수·Influence·Contract·카드 획득·trash·draw는 [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md), [choam-module.md](choam-module.md), [observation-posts.md](observation-posts.md)의 규칙을 그대로 따른다. 예: Spy를 놓을 때 supply에 Spy가 없으면 먼저 하나를 회수한다 `[Main pp. 11, 20]`. 획득 비용 없는 "획득"도 Reserve에서 가져온다.
- Scouts 단계의 recruit는 turn 밖이다. "이번 turn에 recruit한 troop" 배치 규칙 `[Main p. 10]`은 적용되지 않는다. 곧바로 Conflict에 넣으라는 Scouts 단계의 항목(Shadow Warfare, Mercenaries)만 그렇게 한다(OQ-074).
- Immortality에서 Scouts 항목이 supply보다 많은 troop을 요구하면(항목 줄의 recruit, Mercenaries 투입, 임무 참여) 그 좌석은 먼저 specimen을 supply로 되돌릴 수 있다. specimen은 "언제든" 되돌릴 수 있다는 규칙 `[Immortality p. 8]`을 Scouts 단계에 적용한 것이다(2026-09-29 사용자 결정, OQ-074).
- 임무 칸을 방문해 세워 둔 troop을 받는 것(Security Detail, Fedaykin Assistance, Weirding Warfare, Send for Aid, Coordinate With The Emperor)은 그 좌석의 Agent turn 안에서 일어난다. 그 troop은 그 turn에 recruit한 troop이다(OQ-077, OQ-089 (c)). 곧바로 Conflict로 가는 유닛은 그 turn에 배치한 unit이다(OQ-077 보강 2026-11-02).
- 비밀 선택·봉인 입찰의 가시성은 [information-visibility.md](information-visibility.md)에 적는다.
- 공식 문서와 앱이 침묵하는 판정은 [open-questions.md](open-questions.md)의 OQ-071~OQ-090에 기록한다.

## 11. 구현 상태

- 2026-11-01 지급의 받기 클릭(사용자 판정 "둘 다 클릭으로", "둘다 (가)로", OQ-164 (a)·(b); 브랜치 `claude/scouts-collect-payouts`, codec은 병합 커밋에서 올림): Tap into Spice Reserves는 좌석별 받기 줄, 다섯 임무 몫은 보드를 떠나 그 좌석의 받을 몫 행(`scouts_goods`·`scouts_parked`의 자리 `owed:…`, 새 상태 칸·관측 변경 없음)이 되고 곧바로 여는 받기 창을 기다린다(`scouts_effects.open_scouts_payout`, 같은 `scouts_effect` 창·`scouts_collect_reward` 행동이라 새 템플릿 없음). 그 전 기록은 다리 `scouts_payout`(codec 162 미만, `scouts_collect`를 대신함)이 "받기"를 누른다.

- 2026-11-01 받기 클릭(사용자 결정, project convention, OQ-164; 브랜치 `claude/scouts-collect-click`, codec은 병합 커밋에서 올림): 공개된 비밀 선택의 비용 없는 줄과 경매 승자의 줄이 `scouts_effect` frame에서 받는 좌석의 `scouts_collect_reward`("받기", 새 템플릿, 모든 Scouts 카탈로그)를 기다린다(3.1절). 그 전의 기록은 다리 `scouts_collect`가 "받기"를 누른다. 계기는 2026-11-01 WSL 판: 6라운드 Scouts 단계에서 좌석 3의 Offworld Operation "Tleilaxu track 1"이 공개와 함께 한 자동 단계 안에서 Tleilaxu 1→2칸과 그 칸의 Intrigue 1장을 줬고, 사용자는 받은 것을 몰랐다.

- 2026-10-26 일반 규칙 감사 수정(사용자 결정 "Leverage는 OQ-111 (2)", codec v153): "원하는 Faction" 단계(Leverage·Relations·Share Intelligence·Ingratiate)는 꼭대기 아래 Faction이 하나뿐이어도 창을 연다(OQ-111 (2), OQ-106 (10) 보정). Leverage의 Intrigue는 그 뒤 줄의 단계(`scouts_rewards_first`)다. 옛 기록 다리 `scouts_faction_alone`·`scouts_faction_alone_draw`(이 다리들은 codec v156까지 있었고 2026-10-29 남은 기보를 v156으로 변환하며 지웠다).
- 2026-10-17 정리-2a(효과 조각 엔진 전환 정리-2, 브랜치 `cleanup2`, codec v149, 사용자 결정 "정한 규칙 판단" 6): 할 수 있는 줄이 없는 좌석에게도 `scouts_choice` 창을 연다(이벤트·판매·공개된 비밀 선택의 비용 줄). 줄은 이유와 함께 회색, 유일한 행동 `resolve_scouts_choice_without_option`(한 번 누름, 배너 "할 수 있는 선택 없음 · 턴 종료")이 전과 같은 `scouts_choice_skipped`를 낸다. 건너뛴 좌석 알림은 없앴다. 옛 기록은 다리 `scouts_no_option_window`(OQ-071; 이 다리는 codec v156까지 있었고 2026-10-29 남은 기보를 v156으로 변환하며 지웠다).
- 2026-10-10 OQ-106 셋째 묶음(사용자 판정 "그 외에는 전부 나누자", project convention; codec v142에 함께, 템플릿 변화 없음).
  - 줄의 보상 하나가 소유자의 선택이었으면(Faction, 선택 trash, Spy 배치, Contract, Research 방향) 그 뒤에 인쇄된 숨은 draw는 줄의 자기 단계로 남아 `scouts_rewards_first`("남은 보상 받기") 하나로 뽑는다: Leverage, Water Discipline, Spies for Hire 후반 1위, CHOAM Negotiations 후반 1위. 비용 칸의 선택(Rotating Doors의 Intrigue trash)은 보상과 한 단위로 남는다.
  - 봉인 경매의 두 번째 이후 각 승자의 보상 앞에 멈춤(`rules/pauses.py` `SCOUTS_REWARD`): Competitive Study 2위의 Research(두 번째 genetic marker 뒤의 draw, 한 갈래 전진)가 1위의 방향 선택 단계에서 일어나지 않는다.
  - records bridge `scouts_held_draw`(codec 142 미만; codec v156까지 있었고 2026-10-29 남은 기보를 v156으로 변환하며 지웠다), 멈춤은 기존 `pause` bridge.
- 2026-09-30 AI 좌석(사용자 결정, 설계 D6·4.9절).
  - Scouts 게임에 `checkpoint:`·`search:` 좌석을 앉힐 수 있다. 서버와 대회의 거절을 풀었고, 좌석은 게임의 설정으로 만들어져 정책 head가 Scouts 카탈로그로 옮겨진다(Epic 병합의 룰셋 재지정). 비밀 선택·봉인 입찰·뒷면 카드는 7·8절대로 `known_card_seats`에 있어 탐색 좌석의 재추첨이 섞는다.
  - 합법 행동이 전부 체크포인트가 학습하지 않은 템플릿인 결정(Scouts 없이 학습한 파일에게는 입찰·호가·비밀 선택·임무 참여·소위원회 가입·이벤트 줄 대부분)은 에이전트 seed의 heuristic이 답한다. 섞인 결정은 네트워크가 답한다. 규칙 동작은 바뀌지 않는다(엔진·codec·관측 무변경).
- 2026-09-30 OQ-076 대안 C(사용자 판정, project convention).
  - 소위원회 가입이 자리를 차지한 turn 안의 자유 순서 효과가 됐다: High Council 칸에서는 방문의 효과 하나(`BOARD_ICON_SUBCOMMITTEE`), Corrinth City에서는 그 Reveal turn 동안의 기회. turn frame에 `choose_subcommittee`(지금 가입할 수 있을 때만)와 `decline_subcommittee`, 고르면 `scouts_subcommittee` frame에서 `join_subcommittee`. 자리를 얻는 즉시 열리던 결정은 없앴다.
  - 비용은 낸다. 가입 가능 여부는 고르는 순간의 자원으로, Contingencies의 제외 Agent도 그 순간에 정한다(OQ-075).
  - 화면: "소위원회 선택" 행, 가입할 수 없을 때는 이유와 함께 회색 행, 미리보기는 자리를 차지한 직후 기준. heuristic은 가입할 수 있으면 고른다.
  - codec v123(`choose_subcommittee` 템플릿), 관측 v27 그대로.
- 2026-09-29 D8 3차 반영(사용자 결정).
  - Round Start를 규칙 순서로(공개 → 선택 방어 배치 → draw; 모든 게임, codec v122, OQ-072).
  - Mercenaries 입찰 상한에 넣을 수 있는 troop 수를 넣고 모자란 supply는 specimen으로 자동 보충(선택형 보충 frame 제거, 관측 v27, OQ-074).
  - Critical Moment는 덱이 모자라면 추첨에서 뺀다(OQ-087). Clear the Market은 옛 Contract를 먼저 섞고 채운다(OQ-083). Emperor's Schemes는 덱이 모자라면 버린 Intrigue를 섞는다(OQ-078). CHOAM Research는 Immediate를 놓지 않는다(OQ-090).
  - 의무 이벤트에서 한 줄만 할 수 있어도 결정이 열린다(OQ-071).
  - 게임 전체에 "지금 고를 수 없는 선택지"를 이유와 함께 회색으로: 구매(Reveal의 Row·Reserve·Tleilaxu), Intrigue 사용, 조건을 기다리는 효과(1단계).
- 2026-09-29 D8 2차 반영(사용자 결정).
  - Corrinth City로 Contingencies에 가입한 좌석도 Conflict의 Agent를 회수하고, 전투력과 Reveal frame 합계를 다시 센다(`effects.recall_conflict_agent`; OQ-075).
  - 소위원회 가입은 비용을 낼 수 있고 보상이 무언가를 할 때만 가능하다. 이번 turn에 Into the Fray로 옮긴 좌석 차지 Agent는 회수 대상이 아니다.
  - Mercenaries 후퇴는 1 이상 입찰 가운데 최저(OQ-074). Clear the Market의 CHOAM 판은 항상 교체한다(OQ-083).
  - 화면: 지금 고를 수 없는 줄(이벤트·판매·소위원회·임무)을 이유와 함께 회색으로 보이고, High Council 행동에 소위원회 미리보기, 건너뛴 좌석 알림, 로그의 Scouts id를 이름으로(OQ-071). 엔진 합법 행동·codec·관측·이벤트는 그대로다.
- 2026-09-29 D8 일괄 검토 1차 반영(사용자 결정과 영어 원문 대조 감사).
  - 경매 보상은 순위대로, 같은 순위는 First Player부터(OQ-073).
  - Immortality의 specimen 보충: Scouts 줄의 recruit(`scouts_effect` frame의 선택 단계), Mercenaries 투입(frame `scouts_top_up`), 임무 참여(참여 frame 안에서) 전에 `scouts_return_specimens(count)`(OQ-074, OQ-088).
  - Mercenaries의 후퇴는 `units.retreat_units`를 거친다(Chani의 Tactics, OQ-074).
  - 비용이 있는 줄은 보상이 무언가를 할 수 있을 때만 제시한다(`scouts_effects.line_is_offered`): Moment of Revelation은 Reserve에 Prepare the Way가 없으면, 영향력 줄은 대상 track이 모두 꼭대기면, recruit 줄은 병력도 specimen도 없으면 제시하지 않는다(OQ-071; 보상 없는 손실 줄은 이 검사에서 빠진다).
  - 임무는 인쇄된 troop 수를 모두 세워야 참여한다(OQ-088). garrison으로 가는 임무 troop은 모두 이번 turn의 recruit다(OQ-089 (c)).
  - Contingencies의 회수 대상에 Into the Fray로 Conflict에 있는 Agent를 넣었다(OQ-075 (D)).
  - 소위원회의 가입 시점과 비용(OQ-075, OQ-076)은 영어 원문과 사용자 방향이 달라 다시 묻는 중이다(2026-09-30 대안 C로 결정, 위).
  - 화면 문구: Prison Planet·Send for Aid·Coordinate With The Emperor의 물품이 은행에서 온다는 점, Offworld Operation의 "Helix에 닿으면".
  - 관측 v26(frame kind `scouts_top_up`), slot key 1,140, action codec v121.
- 2026-09-28 슬라이스 10: heuristic이 봉인 입찰을 한 번 고르고 곧바로 확정하며(전에는 모든 액수와 확정이 같은 점수라 확정을 뽑을 때까지 다시 골랐다), Critical Moment에서 아직 안 나온 1~3 중 가장 큰 액수를 부른다. Scouts 행동이 없는 게임의 동작은 그대로다. 단독·교차 소크(무작위·heuristic × 기본·CHOAM·Immortality·전 확장+draft) 실패 0. **모든 슬라이스 완료**; OQ-071~OQ-090은 D8에 따라 일괄 검토를 기다린다.
- 2026-09-28 슬라이스 9: 서버·UI.
  - 새 게임 화면에 "아라킨 스카웃" 체크박스(기본 꺼짐)와 머리글 배지.
  - 오른쪽 열의 Scouts 패널: 소위원회와 가입 좌석, 이번 라운드 항목과 그 줄, 임무 조각(칸·관측소·Contract 위 물품, 세워 둔 병력, 뒷면 카드 수), 기다리는 비밀 선택(누가, 자기 선택은 줄까지), 진행 중인 경매(확정한 좌석, 자기 입찰액, Critical Moment의 카드와 호가), 지난 항목. view만 읽으므로 숨은 값은 나오지 않는다.
  - 선택지 버튼에 줄의 효과를 쓴다(`display/scouts.py`, 한/영). 한국어 항목 이름은 [glossary-ko.md](glossary-ko.md)의 공식 용어다. 효과 문장은 우리 문장이다(D7).
  - 봉인 입찰은 개수 스테퍼(입찰액이 0뿐이어도)와 배너의 "턴 종료 ▶" 한 줄(= 확정)이다. 게임이 끝나면 쓰이지 않은 비밀 선택이 종료 후 공개에 나온다.
  - `scripts/e2e/scouts.py`: 사람 좌석 하나로 시드 게임을 끝까지 두며 위 화면을 확인한다(영어에서 한글 없음 포함).
- 2026-09-28 슬라이스 8: 8절 경매(`rules/scouts_auctions.py`).
  - 봉인 입찰: First Player부터 좌석마다 `scouts_bid(count)`로 고르고(몇 번이든 바꿀 수 있다) `confirm_scouts_bid`로 확정한다(frame `scouts_bid`). 범위는 0부터 자기 통화와 상한 중 작은 쪽까지다. 입찰액은 `GameState.scouts_bids`에 있고 그 좌석만 안다(`secret_bid_id`). 마지막 확정이 전원의 입찰을 공개하고(`scouts_bid_revealed`), 앱 코드대로 순위를 매겨 이긴 좌석만 지불한 뒤 차례 순서로 보상을 해결한다(OQ-073).
  - Mercenaries: 전원이 입찰한 spice를 내고 그만큼 supply의 troop을 Conflict에 넣는다. 최저 입찰자(동점이면 모두)는 그 troop 중 원하는 만큼 garrison으로 후퇴한다(`scouts_retreat(count)`, OQ-074).
  - Critical Moment: Imperium 덱 위 2장(후반 3장)을 공개하고(`scouts_market_cards`, 덱이 모자라면 있는 만큼), 좌석마다 한 번 `scouts_call(count)`(0은 패스, 이미 나온 액수는 없음). 1위는 부른 spice를 내고 한 장을 손으로 획득하며(`scouts_take_card(slot)`), 후반 판의 2위는 사거나 사지 않는다(`scouts_decline_card`). 남은 카드는 게임에서 빠진다(`imperium_removed`, OQ-083, OQ-087).
  - 봉인 장치를 입찰로 넓혔다: 서버 로그가 `scouts_bid`의 인자를 가리고, 공개로 이어지는 확정의 미리보기를 싣지 않으며, 확정은 명시적 턴 종료다(`EXPLICIT_TURN_ENDS`). 탐색 AI와 비공개 검사는 상대의 입찰을 그 좌석이 낼 수 있던 다른 액수로 바꾼다.
  - 관측 v25(확정 여부·자기 입찰액, 공개 카드, 호가), codec v119.
- 2026-09-28 슬라이스 7: 7절 비밀 선택(`rules/scouts_secrets.py`).
  - 이벤트가 나오면 First Player부터 좌석마다 `scouts_secret_pick(pick)`으로 고른다(frame `scouts_secret`, 네 값이 늘 모두 제시된다). 선택은 `GameState.scouts_secret_picks`에 남고 그 좌석만 안다.
  - 공개 라운드의 Scouts 단계 첫 일로 기한이 된 선택을 모두 공개하고(`scouts_secret_revealed`), 이벤트 → 줄 → First Player부터의 좌석 순서로 해결한다. "카드 1장 버리기 → troop 3"은 받을지 고른다. Offworld Operation의 둘째 줄은 첫 genetic marker에 닿았으면 spice 2(OQ-085, OQ-089 (b)).
  - 봉인 장치: 좌석 한정 id로 숨은 정보 등록부(`known_card_seats`)에 넣어 공개 단계가 되돌릴 수 없는 공개가 되고, 서버 로그는 선택 인자를 게임이 끝날 때까지 가리며, 행동 목록의 미리보기를 싣지 않는다. 탐색 AI(`determinize`)와 소크의 비공개 검사는 상대의 선택을 구별할 수 없는 줄로 바꾼다. 종료 후 공개에 남은 선택이 보인다([information-visibility.md](information-visibility.md)).
  - 관측 v24(좌석별 숨은 선택 수, 자기 선택), codec v118.
- 2026-09-28 슬라이스 6b: 나머지 임무의 수령.
  - Desert Riding: Hagga Basin의 Maker 선택에 `take_desert_riding_hooks`(spice 2 대신 토큰, bonus spice는 그대로, 같은 방문 sandworm 없음). Maker Hooks가 있는 좌석에는 없다. 토큰이 남은 마지막 Maker Hooks이면 Sietch Tabr의 Maker Hooks 획득이 가져간다(OQ-079).
  - Valued Informants(Urban Surveillance, Planetary Exploration)와 CHOAM Escort: 매 전이 뒤 자동 단계가 Spy가 놓인 물품 관측소와 완료된 Contract를 찾아 물품을 준다. 어느 배치·완료 경로든 같다(OQ-080).
  - Sponsored Research: research token이 첫 genetic marker 열에 처음 닿을 때 spice 2. Tleilaxu Offering: Tleilaxu token이 세 번째 칸(index 3)에 닿을 때 세워 둔 troop 2가 specimen 2가 된다. 이미 그 칸이나 뒤에 있는 좌석에는 참여를 묻지 않는다. Back Room Deal: Reclaimed Forces를 다음에 획득하는 좌석이 Solari 2(OQ-089).
  - codec v117(`take_desert_riding_hooks`). 관측은 그대로(v23).
- 2026-09-28 슬라이스 6a: 5절 임무의 뼈대(`rules/scouts_missions.py`).
  - 공개하면 은행 물품과 뒷면 카드를 놓고(`scouts_goods`, `scouts_goods_cards`), 참여 임무는 First Player부터 좌석마다 참여/패스를 묻는다(frame `scouts_mission`; 참여할 수 없는 좌석은 묻지 않는다, OQ-088).
  - 세워 둔 troop은 `PlayerState.troops_parked`로 12개 보존에 든다(`scouts_parked`가 위치를 적는다).
  - Agent가 그 칸을 방문하면 그 좌석의 조각을 받는 것이 방문 효과 하나로 붙는다(`scouts_collect_mission`, Bloodlines Commander 선례). 칸에 인쇄된 효과가 아니므로 Reverend Mother의 반복은 이것을 다시 걸지 않는다(OQ-019 보강, 2026-10-14 사용자 판정). Security Detail·Weirding Warfare·Send for Aid의 troop은 Conflict로, Fedaykin Assistance의 troop은 이번 turn에 recruit한 troop으로 garrison에, Coordinate With The Emperor의 specimen은 garrison으로 간다(OQ-077). Imperial Reserve는 둘 중 하나를 고른다(OQ-078). Prison Planet은 garrison troop 1(또는 Bloodlines의 garrison Commander 1, OQ-105)을 잃고 지배 마커와 spice 2를 둔다; 마커는 지배 칸과 합쳐 3개를 넘지 않고, 그 좌석이 Conflict 보상으로 세 번째 칸을 지배하게 되면 마커를 가져다 쓰고 spice는 은행으로 돌아간다(`scouts_prison_marker_taken`). CHOAM Research의 뒷면 카드가 Bloodlines의 Immediate이고 방문자에게 Intrigue가 없으면 다음 장을 받는다(OQ-090).
  - CHOAM Research의 Contract 2장과 Emperor's Schemes의 Intrigue 2장은 뒷면이다: 누구도 모르며(`known_card_seats`), 탐색 AI의 재추첨과 비공개 검사에서 bank·덱과 함께 섞이고, 카드 보존 검사에 든다. 방문마다 1장씩 받는다.
  - 관측 v23(임무별 세워 둔 troop과 물품), codec v116.
  - 남은 것은 슬라이스 6b에서 끝냈다(아래).
- 2026-09-28 슬라이스 5: 6절의 선택형 이벤트(Immortality 넷 포함)와 9절의 판매, Political Equilibrium, Rebuild Infrastructure.
  - 공개되면 First Player부터 좌석마다 `scouts_choice` frame을 연다. 낼 수 있는 줄만 `scouts_choose_option`으로, 패스가 있으면 `scouts_pass`로 제시한다. 패스가 없는데 할 수 있는 줄이 하나뿐이면 결정 없이 그 줄을, 하나도 없으면 아무것도 하지 않는다(OQ-071). 고른 줄은 슬라이스 4의 `scouts_effect` frame이 푼다.
  - Influence 잃기(`LoseFactionInfluence`, Political Equilibrium의 `LoseHighestInfluence`)는 효과 frame의 선택이다. 동률인 가장 높은 Faction과, Alliance를 넘겨받을 상대가 동률일 때의 받는 좌석을 고른다(`scouts_lose_influence`, `scouts_lose_influence_to`; `[Main p. 7]`의 Alliance 규칙은 기존 `lose_faction_influence`).
  - Rebuild Infrastructure: Shield Wall이 서 있으면 아무 일도 없다. 먼저 내기로 한 두 좌석이 spice 1씩 내면 토큰이 돌아오고, 그 뒤 좌석에는 묻지 않는다. 끝까지 한 좌석뿐이면 아무도 내지 않는다(OQ-084).
  - codec v115. 소크(codec 왕복 검사)가 잡은 결함: 기본 룰셋+Scouts에서 trash 아이콘(Water Discipline)이 여는 기존 선택 trash frame의 행동이 카탈로그에 없었다(그 행동은 Bloodlines·Immortality 카탈로그에만 있었다). Scouts 카탈로그에 더했다.
- 2026-09-28 슬라이스 4: 4절의 소위원회.
  - High Council 칸의 자리 아이콘과 Corrinth City의 자리 획득이 가입 기회 하나를 대기열에 넣고, 엔진이 곧바로 연다(`rules/scouts_effects.py`, frame `scouts_subcommittee`). 비용을 낼 수 있는 빈 소위원회만 제시하고, 하나도 없으면 결정 없이 사라진다. 거절도 기회를 없앤다(OQ-076; 2026-09-30부터는 turn 안 자유 순서 효과, 위).
  - 가입하면 그 소위원회의 비용 → 보상 줄을 `scouts_effect` frame이 한 칸씩 푼다. 자동 칸(지불, 자원·recruit·draw·Influence·Contract·specimen·연구·Tleilaxu)은 기존 효과 해석기로, 선택 칸(버릴 카드, trash할 카드·Intrigue, 회수할 Spy, Faction, 회수할 Agent)은 이 frame의 행동으로 푼다. Spy 배치와 선택 trash는 기존 frame을 연다. 같은 frame이 슬라이스 5~8의 모든 좌석별 줄에 쓰인다.
  - Contingencies는 방금 원로회 자리를 얻게 한 Agent(High Council 칸의 Agent)를 뺀 자기 Agent 하나를 회수한다(OQ-075).
  - 자리 아이콘이 그 turn의 마지막 효과여서 turn이 이미 닫혔으면, 가입으로 얻은 것은 새로 열린 turn에 세지 않는다(OQ-044 (d) 선례). (2026-09-30 OQ-095로 바뀜: Agent turn은 소유자의 "턴 종료"로만 끝나므로 가입은 언제나 열린 turn 안에서 일어나고, 얻은 것은 그 turn의 것으로 센다.)
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
- 2026-09-28 슬라이스 2: `RulesetConfig(arrakeen_scouts=True)`와 식별자 `+scouts`(맨 뒤). 서버 API·요약·저장 파일·sweep·coverage·대회·PettingZoo 배선, Scouts 게임의 `checkpoint:`·`search:` 좌석 거절(설계 4.9; 2026-09-30에 풀었다). codec v112(카탈로그 변화 없음). 학습 설정(`train`, `problems`)에는 넣지 않았다(D6). UI 체크박스는 슬라이스 9다.
- 2026-09-28 슬라이스 1: 이 명세, 출처 등록([sources.md](sources.md), [source-map.md](source-map.md)), OQ-071~OQ-089, 용어([glossary-ko.md](glossary-ko.md)), 콘텐츠 카탈로그(`content/arrakeen_scouts/`: 소위원회 14, 임무 16, 이벤트 32, 경매 11, 판매 4)와 추출 데이터 대조 감사(implementation-audits/arrakeen-scouts.md). 엔진 동작은 바뀌지 않았다.
