# Rise of Ix 확장 명세 (원판 위, `rise_of_ix` 옵션 예정)

상태: 초안 v1 (2026-10-22, P0). 구현 전이다 — 계획 [base-game-and-ix-plan.md](../base-game-and-ix-plan.md) P4에서 원판 판
([imperium-base.md](imperium-base.md)) 위에 얹는다. Uprising 위의 Rise of Ix(Main p. 18의 "Adding Rise of Ix")는 P7이다.

- **근거.** Rise of Ix 룰북 `[Rise of Ix p. N]`(PDF 쪽, `22-2-11` 판 — FAQ의 Ix errata 두 건이 이미 반영된 판), 2025-01-13 FAQ
  `[FAQ p. N]`, 원판 룰북 `[DI p. N]`. 버전은 [sources.md](sources.md).
- **이미 쓰는 부분.** Epic Game Mode(p. 10)와 두 카드(Control the Spice, Economic Supremacy)는 Uprising 위에서 `epic_game` 옵션으로
  돌고 있다([epic-game-mode.md](epic-game-mode.md)). 원판 + Ix의 Epic은 11절.
- **Bloodlines Tech Module과의 관계.** 세 더미·획득·할인·뒤집기의 틀이 같아 엔진은 그 틀을 다시 쓴다(계획 6절). 타일 18장과 협상가·Shipping·
  dreadnought는 Ix에만 있다. 두 모듈을 함께 쓰는 판(P7)은 이 문서 밖이다.

## 1. 범위

- 4인 게임. 1·2인 규칙(House Hagal 새 카드, Rival Tech, Solo 변형 `[Rise of Ix pp. 8-9]`)은 범위 밖이다.
- Ix 프로모 Boundless Ambition은 `promo_cards` 옵션 뒤에(계획 9절 8). 근거는 카드면.
- Epic Game Mode(p. 10)는 원판 + Ix에서도 쓴다(계획 9절 9, 11절).

## 2. 구성물과 구성표 (`[Rise of Ix p. 2]`)

룰북 합계, BGG 카드 시트, 앱 `CardCount`가 모두 같다(2026-10-22, [imperium-base.md](imperium-base.md) 3절과 같은 대조).

| 종류 | 종류 수 | 장수 | 룰북 | 비고 |
| --- | --- | --- | --- | --- |
| Imperium 덱에 섞는 카드 | 29 | 35 | 35 | 프로모 Boundless Ambition 1장은 따로 |
| Intrigue | 17 | 17 | 17 | Advanced Weaponry·Finesse(Plot/Combat), Machine Culture(Plot/Endgame), War Chest(Combat/Endgame)는 두 면 |
| Conflict | 4 | 4 | I 2, II 1, III 1 | 앱 `ConflictLevel`도 같다(Skirmish 둘이 I, Trade Monopoly II, Economic Supremacy III) |
| Leader | 6 | 6 | 6 | |
| Tech tile | 18 | 18 | 18 | |
| 시작 카드 | 1 | 좌석마다 1 | Control the Spice | Epic 전용 |
| 기타 | | | Ix board, CHOAM 덮개, 좌석마다 dreadnought 2·disc 1(Freighter), Snooper token 4(Tessia Vernius) | House Hagal 9장·Rival 참고 카드 2장은 범위 밖 |

## 3. Setup (`[Rise of Ix p. 3]`)

원판 setup에 더하거나 바꾼다.

1. CHOAM 덮개를 보드 오른쪽 위에 놓아 원판의 Landsraad와 CHOAM 구역을 덮는다. 앱은 원판 칸 넷(Hall of Oratory, Rally Troops, Secure
   Contract, Sell Melange)을 Rise of Ix에서 빼고(`RemovedFromSetList`), 새 칸 넷(Dreadnought, Tech Negotiation, Interstellar Shipping,
   Smuggling, 6절)을 더한다. Mentat·Swordmaster·High Council은 그대로다. 룰북 문장은 "덮는다"만 말하므로, 덮개에 다시 인쇄된 원판 칸이
   원판과 같은지는 덮개 그림을 찾으면(계획 9절 7) 확인한다.
2. Ix board를 보드 옆에 놓는다. Tech tile 18장을 뒷면으로 섞어 6장씩 세 더미로 놓고, 더미마다 맨 위를 앞면으로 뒤집는다.
3. Conflict 덱: 원판 카드에 Ix 카드 넷을 더해(I 6, II 11, III 5) 원판과 같은 모양(I 1, II 5, III 4)으로 만든다. 이제 III 하나가 남아 상자로 간다.
4. Ix Intrigue 17장과 Imperium 35장을 각 덱에 섞는다(Imperium은 Row를 놓기 전). Leader는 원판·Ix 어느 조합이든 고른다.
5. 좌석마다 dreadnought 둘을 supply에, disc 하나를 Freighter로 Shipping track 맨 아래 칸에 놓는다.
- Ix Leader의 setup: Viscount Hundro Moritani(Intelligence, 시작에 Intrigue 덱 위 두 장을 보고 하나를 갖고 하나를 위에 되돌림), "Princess" Yuna
  Moritani(water 없이 시작), Tessia Vernius(Snooper token을 각 Influence track의 2칸에) `[Leader cards]`. 순서: Baron(원판)의 진영 고르기와 같이
  "모든 setup 뒤, 첫 라운드 전"에 둔다 — Epic에서는 Hundro가 모두가 Intrigue를 뽑은 뒤 쓴다고 룰북이 정한다 `[Rise of Ix p. 10]`.

## 4. Tech tile (`[Rise of Ix p. 4]`)

- **얻기.** Acquire Tech 아이콘이 유일한 길이다. 아이콘마다 Ix board의 세 더미 맨 위 앞면 타일 하나를 얻을 수 있다("may"). spice 비용을 내고
  supply에 공개로 두고, 그 더미의 다음 타일을 앞면으로 뒤집는다. 더미가 비면 고를 것이 줄 뿐이다. 개수 제한 없음.
- **할인.** 비용은 0보다 낮아지지 않는다.
  - Tech Discount: −1·−2가 붙은 Acquire Tech 아이콘은 그 한 번의 구매를 깎는다. 여러 아이콘의 할인은 합치지 못한다. "may"가 없으므로
    의무 할인이다(OQ-104의 원칙, Navigation Chamber와 같다).
  - Tech Negotiation(협상가): 아이콘마다 supply의 troop 하나를 Ix board에 Negotiator로 놓을 수 있다("may"; supply가 비면 아무 일도 없다).
    나중에 Acquire Tech 때 원하는 만큼("any number") Negotiator를 supply로 돌려 하나에 spice 1씩 깎는다. Tech Discount와 합칠 수 있다.
  - Negotiator는 recruit할 수 없다(Ix board의 troop을 garrison으로 데려오는 것이 아니다) `[FAQ p. 4]`.
- **쓰기.** 능력마다 쓰는 때가 적혀 있다(Reveal turn, Conflict 승리, Round Start, Endgame 등). 뒤집기 아이콘이 있는 능력은 자기 turn(Agent·Reveal)
  가운데 라운드에 한 번, 쓰면 뒷면으로 뒤집고 다음 라운드 Round Start에 되돌린다 `[Rise of Ix p. 4]` `[FAQ p. 1]`(첫 영어판은 Agent turn만이라고
  잘못 적었다). 때를 적지 않은 능력은 자기 turn 가운데 쓴다 `[FAQ p. 4]`(예: Spy Satellites의 첫 능력).
  Reveal turn 도중 Acquire Tech로 얻은 타일의 "Reveal turn" 능력도 그 turn에 듣는다(OQ-150 (가), 2026-10-29 사용자 — Artillery·Minimic Film·Restricted
  Ordnance·Disposal Facility 모두).
- **Round Start 순서**(OQ-122, 2026-10-23 사용자 확정, 앱과 같음): Conflict 공개 → Control 방어 → 각자 5장(뒤집은 Tech 되돌리기를 함께) →
  Holtzman Engine의 카드 1장·Shuttle Fleet의 2 Solari → Ilesa의 따로 두기(Holtzman Engine으로 뽑은 카드까지 든 손에서) → 첫 turn. 좌석 사이는
  First Player부터.
- **Appropriate** — Solari와 spice를 섞어 낼 수 없다. Negotiator 하나가 1 Solari를 깎는다 `[Rise of Ix p. 10]`. Shipping 맨 위 회수와 함께 쓰면 Acquire
  Tech가 둘이고 각각 따로다(−2 할인을 Solari 구매에 붙일 수 없다; Negotiator는 어느 쪽에나) — 디자이너 판정(Direwolf Discord).

| 타일 | spice | 획득 효과 | 능력 | 뒤집기 |
| --- | --- | --- | --- | --- |
| Artillery | 1 | – | Reveal turn: sword를 주는 공개 카드마다 sword 1 | |
| Chaumurky | 4 | Intrigue 2 | Endgame: 동률을 이긴다(다른 동률 기준보다 먼저 `[FAQ p. 1]`) | |
| Detonation Devices | 3 | – | dreadnought로 이겼을 때 칸을 지배하는 대신 dreadnought 하나를 supply로 돌려 1 VP("may") | |
| Disposal Facility | 3 | trash 1 | Reveal turn: 그 turn에 얻은 Persuasion 합계(쓴 것 포함)가 6 이상이면 in play 카드 하나를 trash할 수 있다(OQ-126) | |
| Flagship | 8 | 1 VP | 4 Solari → troop 3 | ○ |
| Holoprojectors | 3 | – | discard → 카드 1장 | ○ |
| Holtzman Engine | 6 | – | Round Start: 카드 1장; Endgame: The Spice Must Flow 2장 이상이면 1 VP | |
| Invasion Ships | 5 | troop 4 | discard → 이번 turn 상대 Agent가 내 Agent를 막지 않는다 | ○ |
| Memocorders | 2 | Influence 1(진영 골라) | Endgame: 네 track 모두 Influence 3 이상이면 1 VP | |
| Minimic Film | 2 | – | Reveal turn: Persuasion 1 | |
| Restricted Ordnance | 4 | – | Reveal turn: High Council 자리가 있으면 sword 4 | |
| Shuttle Fleet | 6 | 서로 다른 진영 둘을 먼저 골라 Influence 1씩(OQ-114, 2026-10-22 사용자 확정) | Round Start: 2 Solari | |
| Sonic Snoopers | 2 | Intrigue 1 | 이 타일 trash → Intrigue 몇 장이든 덱 맨 아래로, 그만큼 뽑기(맨 아래 카드는 공개하지 않음 `[Rise of Ix p. 10]`) | |
| Spaceport | 5 | 카드 2장 | 얻는 카드를 덱 위에 놓을 수 있다 | |
| Spy Satellites | 4 | – | spice 3 + 이 타일 trash → 1 VP(자기 turn에); Endgame: Influence 1 이하인 진영마다 1 VP | |
| Training Drones | 3 | – | troop 1 | ○ |
| Troop Transports | 2 | – | Shipping track에서 troop을 recruit할 때마다 하나 더; 그중 몇이든 Conflict에 배치할 수 있다 | |
| Windtraps | 2 | water 1 | Conflict를 이기면 water 1 | |

타일 문구는 블라인드로 읽은 카드면(2026-10-22)과 앱 문구에서 요약했다. 앱 문구가 없는 타일(Flagship, Holoprojectors, Training Drones)은 아이콘뿐이고,
Restricted Ordnance의 앱 loc 키는 철자가 다르다(`card.techtile.restrictedordinance.ability`). 비용 18개는 앱 `SpiceCost`와 같다.

## 5. Shipping track (`[Rise of Ix p. 5]`)

- Freighter 아이콘마다 Freighter를 둘 가운데 하나로 움직일 수 있다("may"): 한 칸 위로(맨 위면 불가) 또는 맨 아래로 회수. 회수하면 지금 칸과 그 아래
  모든 칸의 보상을 **원하는 순서로** 받는다.
- 칸의 보상(아래에서 위로; 순서는 Rivals 문장 "advances until it reaches the second space (recruit two troops and gain one Influence)"·"Dividends …
  for the first space" `[Rise of Ix p. 8]`로 확인):
  1. 고르기: Dividends(5 Solari, 상대마다 1 Solari) -OR- spice 2.
  2. troop 2 recruit + 진영 하나에 Influence 1.
  3. Tech Discount 2로 Acquire Tech.
- 회수로 recruit한 troop은 Combat 칸에 Agent를 보낸 turn이면 배치할 수 있다 `[FAQ p. 4]`. Troop Transports가 있으면 하나 더, 몇이든 배치 가능.
- 자기 turn 밖의 회수(Conflict 보상의 Freighter): Tech를 얻을 수 있고, Reveal turn 뒤에 뽑은 카드는 다음 라운드까지 갖는다(FAQ의 Trade Monopoly·
  Spaceport 예 `[FAQ p. 3]`). Combat 중에 recruit한 troop은 garrison으로(디자이너 판정, BGG forum — Trade Monopoly로 얻은 Troop Transports).

## 6. Dreadnought와 유닛 (`[Rise of Ix p. 6]`)

- **얻기.** Dreadnought 아이콘마다 supply의 dreadnought 하나를 garrison에 commission할 수 있다("may"). Combat 칸에 Agent를 보낸 turn이면 Conflict에
  배치할 수 있다. 한 좌석은 동시에 둘까지; supply에 없으면 더 얻지 못한다. Dreadnought 칸은 둘이 이미 있어도 갈 수 있고 그 아이콘만 불발한다
  (디자이너 판정, BGG forum).
- **힘.** Conflict의 dreadnought 하나는 strength 3(Prince Rhombur Vernius는 4). troop이 없어도 dreadnought가 있으면 strength가 0이 되지 않고, sword가
  세지고, Combat Intrigue를 낼 수 있다 `[Rise of Ix p. 6]` `[FAQ p. 2]`. garrison의 dreadnought는 아무것도 하지 않는다 `[FAQ p. 2]`.
- **끈질김.** Combat이 해결되면 Conflict의 dreadnought는 supply로 가지 않는다. 이기지 못하면(공동 1위 포함) garrison으로 — troop을 supply로
  돌리는 정리 단계에서 함께(OQ-121 판정 2, 2026-10-24).
- **지배.** dreadnought가 하나라도 있는 Conflict를 이기면 Arrakeen·Carthag·Imperial Basin 가운데 **dreadnought가 없는** 칸 하나를 골라(의무, "must")
  그 깃발에 dreadnought를 놓는다(있던 Control marker를 덮는다). 두 번째 dreadnought도 Conflict에 있었으면 garrison으로(위 끈질김의 정리 단계).
  그 칸의 Control 보너스(1 Solari·1 Solari·1 spice, 방어 배치 troop 1)를 받는다. 지배는 **다음** Combat 단계 끝까지이고, 그때 dreadnought는
  garrison으로 돌아가며 덮였던 marker의 주인이 다시 지배한다. Detonation Devices가 있으면 지배 대신 지배하러 갈 Conflict의 dreadnought를
  supply로 돌려 1 VP를 얻을 수 있다(칸 위·garrison의 것은 아님, OQ-121 판정 3).
  - **엔진(OQ-121 판정 1, 2026-10-24 사용자): 지난 지배 dreadnought는 Combat 단계의 마지막 일로** garrison에 돌아간다(룰북대로). 그 Combat에
    승자가 없어도 돌아간다. Combat 안의 순서는 OQ-121 (1)의 판정을 따르고, 복귀는 그 맨 끝이다.
  - 앱(2026-10-23 재검증, 코드만): dreadnought가 있는 칸은 고르지 못하고, 놓은 dreadnought는 다음 라운드 Combat까지 남았다가 그 라운드
    Recall에 garrison으로 간다 — 룰북과 같은 라운드지만 Combat 끝이 아니라 Makers 뒤다(P0의 "그 라운드 Recall"은 틀렸다). 지금 원판·Ix
    카드로는 그 사이에 지배·위치를 읽는 것이 없어 결과가 같지만, 엔진은 공식 문장을 따른다(OQ-121).
  - 지배 고르기의 자리(2026-10-25 사용자, OQ-121 판정 6 (1)): **승자의 창**(1위 보상과 같은 창)의 의무 줄이고, Detonation Devices는 그 줄 안의
    선택이다. 승자는 이 줄과 보상 아이콘, Windtraps 등 다른 줄의 순서를 고른다. 2위 보상보다 앞이며, 아래 룰북 예의 순서(Frida의 지배 → Ned의 2위 보상)와 같다.
    Conflict에 남은 dreadnought(진 쪽, 승자의 둘째)는 정리 때 troop과 함께 garrison으로 간다(OQ-121 판정 5 (2)).
  - 룰북 예: 지난 라운드의 dreadnought가 아직 Arrakeen에 있어 새 승자는 Imperial Basin을 골랐고, 그 뒤 "as the Combat phase ends" 지난 dreadnought가
    garrison으로 갔다 `[Rise of Ix p. 6]`. P4에서 좌석별로 문자 그대로 테스트한다(OQ-121).
  - 한 번에 locations 위에 있는 dreadnought는 둘을 넘지 않는다(놓이는 것 하나 + 다음 Combat 끝에 떠나는 것 하나) — 세 칸이 다 막히는 일은 없다.
- **유닛.** "unit"은 troop 또는 dreadnought다. 배치 규칙은 "이번 turn에 recruit한 유닛 전부 + garrison에서 유닛 둘까지"로 바뀐다. **원판 카드의
  "troop"은 유닛을 뜻하지 않아 dreadnought에 작용하지 않는다** `[Rise of Ix p. 6]`.

| 문장 | 원판·Ix 예 | dreadnought에 작용 |
| --- | --- | --- |
| troop recruit/잃기/retreat/배치 | Arrakeen·Gun Thopter·Chani·Scout·Sardaukar Legion·Rapid Mobilization·Double Cross·Staged Incident·Test of Humanity·Strongarm | 아니오 `[Rise of Ix p. 6]` |
| unit | Negotiated Withdrawal(retreat three units), Desert Ambush(enemy unit), Second Wave(deploy two units), Diversion(four or more units) | 예 |
| dreadnought | Cannon Turrets(each opponent retreats one dreadnought), Full-Scale Assault, Grand Conspiracy, Detonation Devices | 예 |
| 일반 규칙의 "troop" | strength 0 규칙, Combat Intrigue 자격 | dreadnought도 센다(룰북·FAQ가 바꿨다 `[Rise of Ix p. 6]` `[FAQ p. 2]`) |
| 일반 규칙의 "troop" | 배치 상한 "up to two more" | 유닛으로 바뀌었다 `[Rise of Ix p. 6]` |
| 일반 규칙의 "troop" | Endgame 동률의 "garrisoned troops" `[DI p. 13]`, Control 방어 배치 `[DI p. 10]` | 아니오(바꾼다는 문장이 없다) |
| Baron Harkonnen | "When you deploy 4+ troops" | 아니오 |

## 7. Discard, Unload, Infiltration (`[Rise of Ix p. 7]`)

- **Discard 아이콘.** 손의 카드 하나(Intrigue 아님)를 discard pile로. 대개 비용이고, 내지 않으면 효과도 없다.
- **Unload.** Unload 표시가 있는 Reveal box는 Reveal turn에 공개할 때(보통처럼, Unload 표시는 무시) 말고도, 그 카드를 **discard할 때**와 **trash할 때**
  얻는다. 남의 효과로 버려져도 된다(룰북 예: 상대의 Reverend Mother Mohiam). 카드 자체는 자기를 버리거나 trash하는 수단을 주지 않는다(Treachery는
  자기를 trash한다고 적혀 있어 예외 `[Rise of Ix p. 10]`). Unload 카드 9장: CHOAM Delegate, Esmar Tuek, Freighter Fleet, Guild Accord, In the Shadows,
  Ix-Guild Compact, Treachery, Water Peddler, Boundless Ambition(프로모) — 카드면과 앱 능력 목록이 같다.
  - "discard"는 따로 말이 없으면 손의 카드다 `[FAQ p. 2]` — Clean Up에서 in play 카드를 discard pile로 옮기는 것은 discard가 아니다.
  - 디자이너 판정: 비용 → 효과 줄의 왼쪽(비용)이 Unload를 일으키면 Unload를 끝까지 해결한 뒤 오른쪽으로 간다(BGG Forum 2023, 최신 판정). trash되는
    카드의 Unload는 trash되는 중에 일어난다(OQ-022의 예외가 아니다). Esmar Tuek를 Cull로 trash해 얻은 spice로 그 Agent box를 낼 수 없다(OQ-022).
  - 공개한 Unload 카드를 같은 Reveal turn에 trash하면 **다시 얻는다**(OQ-120, 2026-10-22 사용자 확정). 공개와 trash는 별도 사건이며
    turn당 1회 제한을 두지 않는다. 공식 예도 같은 Esmar Tuek를 discard한 뒤 trash하면 효과를 다시 받는다 `[Rise of Ix p. 7]`.
  - Combat 보상 지급 중(Terrible Purpose의 trash 보상 등)에 열린 Treachery의 Unload는 문장대로 troop 둘을 Conflict에 배치하고, 그 troop은 바로
    다음 단계에서 supply로 돌아간다(OQ-127, 2026-10-23 사용자 확정, 앱과 같음).
- **Infiltration.** Agent의 옆얼굴이 든 Agent 아이콘은 그 아이콘의 칸에서 상대 Agent(여럿이어도)를 무시하고 보낼 수 있게 한다. 자기 Agent가 이미 있는
  칸에는 못 보낸다. The Voice는 넘지 못한다. Dispatch an Envoy로 더한 아이콘은 잠입하지 못한다. `[Rise of Ix p. 7]` 잠입은 선택이다(빈 칸에 보통처럼
  보내도 된다) `[FAQ p. 2]`. 잠입 아이콘 카드 7장: Bounty Hunter(City), CHOAM Delegate(Spice Trade), Court Intrigue(Emperor), Embedded Agent(Landsraad),
  Guild Accord(Spacing Guild), Jamis(Fremen), Web of Power(Bene Gesserit) — 카드면과 앱 `InfiltrationIconList`가 같다.
  - 같은 "막지 않는다" 효과: 원판 Infiltrate(Intrigue), Helena Richese의 Eyes Everywhere, Invasion Ships. The Voice는 Agent가 아니라 이 효과들로도 넘지
    못한다(The Voice 판정 `[DI p. 13]`, Ix p. 7의 잠입 판정과 같은 이유 — 내 해석).
  - 이름: Uprising Spy의 "Infiltrate"(행동), 원판 Intrigue "Infiltrate", Ix의 "Infiltration" 아이콘은 다른 것이다. 엔진 id와 화면 용어집에서 셋을
    가른다(계획 10.1절 3, P7). Ix Imperium 카드 Esmar Tuek는 Bloodlines 지도자 Esmar Tuek와 이름이 같다 — 엔진 id를 가른다(계획 4.2절 7).

## 8. 새 보드 칸 (`[Rise of Ix p. 12]`)

| 칸 | 아이콘 | 비용·요구 | 효과 | 근거 |
| --- | --- | --- | --- | --- |
| Dreadnought | Landsraad | 3 Solari | dreadnought commission 그리고/또는 Acquire Tech | `[Rise of Ix p. 12]`, 앱 `SolariCost 3` |
| Tech Negotiation | Landsraad | – | 고르기: Tech Discount 1로 Acquire Tech -OR- Negotiator 하나; 여기 Agent가 있으면 자기 Reveal turn에 Persuasion 1 | `[Rise of Ix pp. 4, 12]` |
| Interstellar Shipping | Spice Trade | Spacing Guild Influence 2 이상 | Freighter 두 번 | `[Rise of Ix pp. 5, 12]` |
| Smuggling | Spice Trade | – | 1 Solari, Freighter 한 번 | `[Rise of Ix p. 12]` |

Duke Leto의 Landsraad 할인은 Dreadnought 칸에도 든다(3 → 2). Kwisatz Haderach는 Interstellar Shipping의 Influence 요구를 넘지 못한다(디자이너 판정).

## 9. Ix 카드에서 나오는 판정

### 9.1 룰북 clarification `[Rise of Ix p. 10]`

- Appropriate — 4절. Court Intrigue·Sonic Snoopers — Intrigue를 덱 맨 아래에 놓을 때 상대에게 보이지 않는다. Ilesa Ecaz — 라운드 첫 turn에 Reveal을 하면
  따로 둔 카드를 공개 카드에 더한다; 그때 spice·Solari는 없다. Imperial Bashar — 이번 turn에 실제로 sword를 준 다른 카드만 센다(Bene Gesserit Sister가
  Persuasion 2를 골랐으면 세지 않는다). Second Wave — Combat Intrigue이므로 Conflict에 유닛이 이미 있어야 낸다. Treachery — 7절.

### 9.2 FAQ의 Ix 항목

| 항목 | 쪽 | 판정 요지 |
| --- | --- | --- |
| Rise of Ix rulebook errata | 1 | p. 4 뒤집기는 Agent·Reveal turn 모두; p. 8 House Hagal 제거(범위 밖). 받은 PDF는 고친 판 |
| Archduke Armand Ecaz | 1 | Coordination: 세 아이콘 칸 어디든 Agent 둘 이상(같은 아이콘일 필요 없음) |
| Chaumurky | 1 | Endgame 동률에서 이긴다(spice·Solari·water·troop 비교 없이) |
| dreadnoughts | 2 | 6절 |
| Ilesa Ecaz | 2 | "otherwise"는 따로 둔 카드로 Agent를 보냈지만 Agent 아이콘이 정확히 하나가 아닐 때; 그 카드를 쓰지 않으면 아무것도 없음 |
| infiltration | 2 | 7절 |
| Manipulate | 3 | 다른 수단(Boundless Ambition 등)으로 얻을 수 있으나 할인은 없음 |
| "Princess" Yuna Moritani | 3 | 자기 turn에 Solari를 얻을 때마다 +1(예: Freighter 회수의 5 Solari와 Windfall) |
| Reveal turn (Trade Monopoly·Spaceport 예) | 3 | 5절 |
| Rivals | 3 | 범위 밖 |
| Tech tiles | 4 | 4절 |
| troops (Negotiator, Shipping) | 4 | 4·5절 |

### 9.3 디자이너 판정 감사의 남은 몫 (Ix)

정리본의 Ix 몫과 처리([imperium-base.md](imperium-base.md) 13.3과 같은 감사):

| 판정 (출처) | 처리 |
| --- | --- |
| Unload: 비용 쪽이 Unload를 일으키면 그 Unload를 끝낸 뒤 효과로(BGG Forum 2023) | 채택, 7절 |
| trash되는 카드의 Unload는 일어난다; Weirding Way처럼 "이미 설치된 효과"는 카드가 trash돼도 남는다(BGG Forum) | 채택. OQ-022 보강(설치형 효과 유지)과 같다 |
| Appropriate + Shipping 맨 위: Acquire Tech 둘은 따로(Direwolf Discord) | 채택, 4절 |
| Dreadnought 칸: 둘이 있어도 감, 불발(BGG forum) | 채택, 6절 |
| Cannon Turrets로 마지막 유닛인 dreadnought가 밀려나면 그 Combat에서 Intrigue를 더 못 냄(BGG Forum) | 채택(Combat Intrigue 자격) |
| Full-Scale Assault의 sword는 Reveal 때 고정, 나중에 dreadnought가 빠져도 유지(BGG Forum) | 채택 — sword는 공개한 카드가 준 값 `[DI p. 11]` |
| Desert Ambush: retreat시킬 유닛은 낸 사람이 고른다(BGG Forum); sandworm은 못 밀어냄 | 채택(sandworm은 P7) |
| Esmar Tuek를 Cull로 trash해 얻은 spice로 그 Agent box를 못 낸다 | 채택(OQ-022) |
| Machine Culture는 Tech를 얻어야 낸다; Cull은 trash해야 낸다; Strongarm·Quid Pro Quo는 Faction 칸에 Agent가 없으면 비용을 못 냄(Message from designer) | 채택(FAQ p. 2와 같은 방향). OQ-113 (C)와도 같다 — Cull은 1 Solari 비용 줄, Machine Culture의 Tech 획득은 타일 값을 내는 비용 줄로 본다(2026-10-24 사용자 (나): 살 수 있는 타일이 없으면 Plot면을 내지 않는다) |
| Advanced Weaponry는 dreadnought 둘이 있어도 3 Solari를 내고 낼 수 있다(출처 없음, 추정) | **채택하지 않음**(OQ-113 확정 2026-10-24): 3 Solari의 비용 줄이라 dreadnought를 얻을 수 없으면 Plot면을 내지 않는다(앱도 같다, `HasUnitsInSupply<WormDreadnought>`). Combat면은 그대로. 공지 대상 |
| Ilesa가 따로 둔 카드는 trash·discard 대상이 아니다(BGG Forum) | 채택, 10절 |
| Ilesa의 두 번째 Agent에 Dispatch an Envoy를 쓰면 아이콘이 넷 더해져 1 Solari(Agent를 보내기 전에 쓴 경우)(Message from designer) | 채택 |
| Spaceport의 획득 효과는 바로(Armand의 Signet으로 덱 위에 놓은 뒤 뽑기 불가, Direwolf Discord) | 채택(획득 효과는 획득하는 순간 `[DI p. 16]`) |
| Tessia: 버릴 카드가 없을 때 첫 Snooper를 얻어도 token은 가져가 맨 위 칸을 덮고, spice는 못 받음(BGG Forum) | 채택, 10절 |
| Weirding Way의 둘째 turn은 The Voice에 막히지 않음(BGG forum) | 채택, [imperium-base.md](imperium-base.md) 13.1 |
| Boundless Ambition + Usurp(Uprising·Immortality) | P7 |

## 10. Leader 6명

| Leader | 왼쪽 능력 | Signet Ring | 판정·주의 |
| --- | --- | --- | --- |
| Archduke Armand Ecaz (2) | Coordination: Reveal turn에 Landsraad·City·Spice Trade 칸에 Agent 둘 이상이면 in play 카드 하나를 trash할 수 있다 | Conscript: 비용 3 이하 카드 하나를 얻을 수 있다 | `[FAQ p. 1]`; Mentat도 그의 Agent로 센다(디자이너 판정) |
| Ilesa Ecaz (3) | One Step Ahead: Round Start에 손의 카드 하나를 따로 둔다. 라운드의 둘째 turn을 시작할 때 공개해 손으로 되돌린다. 그 turn에 그 카드로 Agent를 보내면 Agent 아이콘이 정확히 하나면 spice 1, 아니면 1 Solari | Guild Contacts: 1 Solari → Foldspace 획득 | `[Rise of Ix p. 10]` `[FAQ p. 2]`; Agent 없는 pass와 Weirding Way 추가 turn 모두 센다(OQ-119 사용자 확정) |
| Prince Rhombur Vernius (1) | Heavy Lasgun Cannons: dreadnought strength 4 | Ixian Technology: Acquire Tech -OR- Tech Negotiation | 오른쪽 아이콘이 Tech Negotiation인 근거: Rival 문장 "Acquire Tech if he can. If not, he will use the Tech Negotiation icon" `[Rise of Ix p. 8]` |
| "Princess" Yuna Moritani (2) | Smuggling Operation: water 없이 시작; 자기 turn에 Solari를 얻을 때마다 1 더 | Final Delivery: 7 Solari → Influence 1(골라)·troop 1·spice 1 | `[FAQ p. 3]`; Dividends로 남의 turn에 받는 1 Solari에는 붙지 않는다(OQ-042·OQ-063 "your turn") |
| Tessia Vernius (4) | Careful Observation: 시작에 Snooper token을 각 track의 Influence 2 칸에. 그 token에 도달할 때마다 Snooper track의 맨 위 덮이지 않은 보상을 받는다(① discard → spice 1, ② 그 track의 4칸 보너스, ③ 그 track에 Influence 1, ④ ②와 ③) | Duplicity: Influence 1 잃기 → Snooper token이 있는 진영에 Influence 1 | 디자이너 판정 9.3. "도달"은 Influence를 한꺼번에 얻으며 지나가도 도달(Uprising과 같다, [uprising-systems.md](uprising-systems.md)) |
| Viscount Hundro Moritani (1) | Intelligence: 게임 시작에 Intrigue 덱 위 두 장을 보고 하나를 갖고 하나를 위에 되돌린다 | Couriers: spice 1 → Freighter | Signet 아이콘이 Freighter인 근거: Rival 문장 "spend 1 spice … for the Freighter icon" `[Rise of Ix p. 8]` |

## 10a. Bloodlines Tech Module과 함께 (`[Bloodlines p. 7]`, P7)

2026-10-29, 사용자 지시("assets/rulebooks 에 룰북 다 있을텐데")로 로컬 Bloodlines 룰북의 해당 쪽만 읽었다. "Combining the Tech Module with RISE OF IX":

- 두 모듈의 Tech 타일을 모두 섞어 될 수 있는 대로 고르게 큰 더미 셋으로 나눈다.
- Rise of Ix의 Tech 타일만 쓸 때(Ix의 다른 구성물 없이): Detonation Devices와 Troop Transports를 빼고 나머지 16장을 Bloodlines 타일과 섞는다.
- Rise of Ix를 모두 쓸 때: Bloodlines의 Ixian Embassy 보드를 쓰지 않고 세 더미를 Ix 보드에 둔다. Tech Negotiation의 할인은 쓰고, High Council
  자리에 따른 Ixian Embassy 할인은 없다.
- Rise of Ix를 모두 쓸 때 CHOAM 덮개가 Sardaukar Commander 자리 둘을 덮으므로, setup에서 Commander 하나를 Dreadnought 칸에, 4인 판이면 다른 하나를
  Tech Negotiation 칸에 둔다.

엔진에는 "Ix의 Tech만" 쓰는 옵션이 없다(`rise_of_ix`는 Ix 전부). 그래서 Bloodlines(Tech Module) + Rise of Ix 판은 셋째·넷째 줄대로다: 타일 36장을 한 묶음으로
섞어 세 더미(12장씩), Ixian Embassy 없음, Commander 자리 옮김. 원판 + Bloodlines가 열리는 P7에서 구현한다(그때까지 setup이 거절).

## 11. Epic Game Mode (원판 + Ix, `[Rise of Ix p. 10]`)

12점까지. Conflict I을 쓰지 않고 무작위 II 다섯 장을 III 다섯 장 위에 놓는다 — 원판 + Ix의 III은 다섯 장(원판 4 + Economic Supremacy)이라 모두 쓴다. 좌석마다
Dune, the Desert Planet 하나를 Control the Spice로 바꾸고, 모두 Intrigue 1장을 뽑고(Hundro는 모두 뽑은 뒤 Intelligence), garrison troop 5로 시작한다.
Uprising 위의 구현([epic-game-mode.md](epic-game-mode.md))을 다시 쓴다(계획 9절 9).

## 12. Ix Conflict 카드

| 카드 | 단계 | 1위 | 2위 | 3위 |
| --- | --- | --- | --- | --- |
| Skirmish (앱 `SkirmishE`, 에셋 `Skirmish I.webp`) | I | Freighter, troop 1 | spice 2 | spice 1 |
| Skirmish (앱 `SkirmishF`, 에셋 `Skirmish II.webp`) | I | Freighter, spice 1 | 3 Solari | 2 Solari |
| Trade Monopoly | II | Freighter 2, troop 1 | Intrigue, water | Intrigue -OR- water |
| Economic Supremacy | III | [epic-game-mode.md](epic-game-mode.md) 6절 | | |

블라인드 읽기(2026-10-22)의 한 agent가 이 카드들과 Hundro의 Freighter 아이콘(청록 방패)을 dreadnought로 읽었다. Rival 문장 `[Rise of Ix p. 8]`, FAQ의 Trade
Monopoly 예 `[FAQ p. 3]`, 앱 태그(`Freighter`)로 바로잡았다. Skirmish 파일과 앱 정의의 대응은 2026-10-22 카드별 조사에서 보상 값을 앱 능력
클래스와 맞춰 정했다(원판도: `SkirmishA` = `Skirmish III.webp`, B = `Skirmish Iiii.webp`, C = `Skirmish II.webp`, D = `Skirmish I.webp`).
Freighter 보상으로 그 자리에서 Windtraps를 얻으면 이번 승리에도 water를 받는다 — 디자이너 판정(BGG forum, "one from the Acquire effect and one
for winning the combat")이고 Intrigue를 보상으로 받았을 때의 FAQ 판정 `[FAQ p. 4]`과 같은 방향이다. Detonation Devices도 같다.

## 13. 숨은 정보 (계획 10.1절 1)

| 효과 | 아는 좌석 | 언제까지 | 비고 |
| --- | --- | --- | --- |
| Hundro Moritani의 Intelligence | Hundro 좌석이 Intrigue 덱 맨 위 카드 | 공개 영역이나 Hundro의 손에 들어갈 때까지(다른 좌석이 뽑으면 그 손에 있는 것으로 계속 안다), 섞이면 지운다 — OQ-149 (가), Imperium Ceremony도 같다 | 갖는 카드는 손(숨김). 비공개 결정이고 지도자 고르기와 묶지 않는다(lessons 2026-10-05). Epic에서는 모두 뽑은 뒤 |
| Court Intrigue, Sonic Snoopers | 놓은 좌석이 Intrigue 덱 맨 아래 카드(들) | 그 카드가 뽑힐 때까지(뽑히면 누가 가졌는지 안다), 또는 덱을 다시 섞을 때까지 `[FAQ p. 2]` | 공개하지 않는다 `[Rise of Ix p. 10]` |
| Ilesa Ecaz의 따로 둔 카드 | Ilesa 좌석 | 둘째 turn에 공개(그 뒤 손에 있지만 공개 경로로 들어온 카드 — OQ-010) | 따로 둔 카드는 손·discard·in play가 아니어서 trash·discard 대상이 아니다(디자이너 판정) |
| Tech 더미의 다음 타일 | 아무도 | 앞면으로 뒤집을 때까지 | chance. 앞면 타일 셋은 공개 |
| Spaceport(덱 위에 놓기) | 모두 | 그 카드가 뽑힐 때까지 | 공개 경로로 덱 맨 위가 정해진다 |
| Discard 아이콘·Unload | 버린 카드는 discard pile에 face-up | | 상대 차례에 버려도(Mohiam) Unload가 열린다 — 상대 좌석의 결정이 내 turn 안에 생긴다 |
| Snooper token, Negotiator, Freighter, dreadnought | 모두 | | 공개 구성물 |

## 14. 결정 단위와 선택지의 근거 (계획 10.1절 6·7)

이미 정한 원칙(OQ-027 아이콘마다 독립·순서 자유, OQ-106 공개 선택과 숨은 뽑기는 별개, OQ-112 보상 줄 안의 순서, OQ-095 (2) 선택 효과는 거절 없이 turn
종료에 사라짐)을 처음부터 적용한다. 새 제공자(Freighter, Acquire Tech, Negotiator, dreadnought 지배, Unload)는 P4에서 "턴 종료" 판정·제공자 목록을 든 곳을
이름으로 모두 찾아 함께 고친다(lessons 2026-10-18).

| 결정 | 누가 | 선택지 | 근거 |
| --- | --- | --- | --- |
| Freighter 아이콘 하나 | 받은 좌석 | 위로 한 칸(맨 위가 아니면) -OR- 회수 -OR- 쓰지 않음 | "you may move your Freighter in one of two ways" `[Rise of Ix p. 5]` |
| 회수 보상 | 받은 좌석 | 받을 보상마다 따로, 순서 자유; 1칸은 Dividends -OR- spice 2; 2칸 Influence 진영 | "take your rewards in any order" `[Rise of Ix p. 5]` |
| Acquire Tech 아이콘 하나 | 받은 좌석 | 앞면 타일 셋 가운데 하나 -OR- 얻지 않음; 돌려받을 Negotiator 수(0~가진 수) | "you may acquire" `[Rise of Ix p. 4]`; "any number of your Negotiators" `[Rise of Ix p. 4]` |
| Tech Negotiation 아이콘 하나 | 받은 좌석 | troop 하나를 Negotiator로 -OR- 하지 않음 | "you may take a troop" `[Rise of Ix p. 4]` |
| Tech Negotiation 칸 | 보낸 좌석 | Acquire Tech(−1) -OR- Negotiator | "Choose one" `[Rise of Ix p. 12]` |
| Dreadnought 아이콘 하나 | 받은 좌석 | commission -OR- 하지 않음; Combat 칸 turn이면 배치 여부 | "you may commission" `[Rise of Ix p. 6]` |
| dreadnought 지배 | 승자 | dreadnought가 없는 Control 칸 하나(의무); Detonation Devices면 지배 대신 VP. 승자의 창의 줄(OQ-121) | "you must choose" `[Rise of Ix p. 6]`; "you may return" `[Detonation Devices tile]` |
| 승자의 창 | 승자 | 보상 아이콘·지배·Windtraps·Strategic Push의 승리 몫·승리 책략 줄의 순서; 승리 책략은 이 창에서만 | OQ-121 판정 3·6 |
| Unload | 그 카드의 주인 | Reveal box 그대로(그 안의 선택·비용만) | `[Rise of Ix p. 7]` |
| Discard 비용 | 낸 좌석 | 손의 카드 하나(Intrigue 아님) -OR- 내지 않음 | `[Rise of Ix p. 7]` |
| 잠입 | 보낸 좌석 | 상대 Agent가 있는 같은 아이콘 칸에도 보낼 수 있음 | `[Rise of Ix p. 7]` `[FAQ p. 2]` |
| 뒤집기 Tech | 가진 좌석 | 자기 turn에 쓸지, 라운드에 한 번 | `[Rise of Ix p. 4]` `[FAQ p. 1]` |
| Ilesa의 따로 두기 | Ilesa 좌석, Round Start | 손의 카드 하나 | "Set aside a card from your hand" `[Ilesa Ecaz card]` |
| Hundro의 Intelligence | Hundro 좌석, 시작 | 두 장 중 갖는 하나 | `[Hundro Moritani card]` |
| Tessia의 Duplicity | Tessia 좌석 | 잃을 진영, Snooper token이 있는 진영 하나 | `[Tessia Vernius card]` |
| Shuttle Fleet 획득 | 얻은 좌석 | 진영 둘 | OQ-114 |

## 15. 이미 정한 원칙으로 정해지는 것

계획 10.3절에서 Ix 카드에 닿는 것. 다시 묻지 않는다.

- Tech Discount 아이콘은 "may"가 없어 의무 할인, 하한 0(OQ-104·OQ-041). Negotiator 반환은 문장이 "may"라 선택.
- 끝 칸의 track은 아무것도 주지 않는다(OQ-048) — Freighter가 맨 위면 위로 가기를 고를 수 없다는 것은 룰북 문장 자체다.
- 진영을 고르는 보상은 6칸 진영을 제외한다(OQ-060) — Shipping 2칸, Memocorders·Shuttle Fleet 획득, Final Delivery.
- "your turn"은 자기 Agent·Reveal turn(OQ-042·OQ-063) — Yuna Moritani, 뒤집기 Tech.
- "deploy four or more units in a single turn"(Diversion)은 Distraction과 같은 판정(2026-10-03 OQ-016: 카드를 내는 조건, turn의 최고치; OQ-029 셈).
- Desert Ambush의 "for each troop you deploy this turn"은 OQ-029의 셈(같은 큐브를 retreat했다 다시 배치해도 두 번 세지 않음).
- 책략을 낼 수 있는지는 OQ-113의 통일 기준 (C)다(2026-10-24 사용자): 비용이 있는 줄은 보상이 살아 있어야 내고, 비용 없는 효과는 불발해도 낸다 —
  Advanced Weaponry의 Plot면(3 Solari → dreadnought)은 dreadnought 둘을 이미 가졌으면, Machine Culture의 Plot면(타일 값을 내는 Tech 획득)은 살 수
  있는 타일이 없으면 내지 않는다.
- trash된 카드의 남은 효과는 없다(OQ-022) — Unload는 trash되는 중의 trigger라 예외가 아니다(디자이너 판정).
- 비용만 내고 보상을 받을 수 없는 화살표 줄은 내지 않는다(OQ-071의 사용자 원칙 일반화) — 버릴 카드에 Unload가 있어도 같다(Ix-Guild Compact에서 dreadnought가
  둘 다 나가 있을 때, Invasion Ships를 Agent를 보낸 뒤에; 앱도 같다).
- Troop Transports의 "You may deploy any of them to the Conflict"는 카드 문장이 배치를 허락하므로 Combat 칸에 Agent를 보내지 않은 turn에도 배치할 수 있다
  (카드는 일반 규칙을 바꾼다 `[DI p. 6]`). Combat 해결 중의 회수로 recruit한 troop은 Troop Transports가 있어도 garrison으로 간다(OQ-151 (가), 2026-10-29 사용자).
- "Reveal Turn:" Tech를 Reveal turn 도중에 얻으면 그 turn에 쓴다(타일 문장; 지금 엔진은 Bloodlines의 Command 타일만 그렇게 한다 — P4 구현 메모).

## 16. 새 질문

[open-questions.md](open-questions.md)에 원문·앱 처리·추천과 함께 적었다. 원판 쪽은 OQ-113 ~ OQ-118([imperium-base.md](imperium-base.md) 17절).

- OQ-119 — **확정:** Ilesa Ecaz의 "둘째 turn"은 Agent 없는 pass와 Weirding Way 추가 turn 모두 센다.
- OQ-120 — **확정:** 공개한 Unload 카드를 같은 Reveal turn에 trash하면 Reveal box를 또 얻는다.
- OQ-121 — **확정(2026-10-24~25):** 세 판 공통으로 순위마다 "보상 + 그 좌석의 창"이다. 승자의 창에는 보상과 함께 지배·Detonation·
  Windtraps·Strategic Push의 승리 몫·승리 책략이 들고, 승자가 순서를 고른다. 승리 책략은 이 창에서만 낸다. Conflict에 남은 dreadnought(진 쪽,
  승자의 둘째)는 troop 정리 때, 지난 지배 dreadnought는 Combat 단계 끝(룰북대로, 앱의 Recall이 아님)에 garrison으로 간다. Detonation Devices는
  지배하러 갈 Conflict의 dreadnought만 supply로 보낸다(6절).
- OQ-122 — **확정(2026-10-23):** Round Start는 공개 → 방어 → 5장·Tech 되돌리기 → Holtzman Engine·Shuttle Fleet → Ilesa의 따로 두기(4절 "쓰기" 아래).
- OQ-126 — **확정(2026-10-23):** Disposal Facility는 그 Reveal turn에 얻은 Persuasion 합계(쓴 것 포함)로 판정한다.
- OQ-127 — **확정(2026-10-23):** Combat 보상 중 열린 Treachery의 Unload는 Conflict에 배치하고 곧 supply로 돌아간다.
- OQ-123은 **확정:** Grand Conspiracy·Holtzman Engine도 전체 보유 사본(덱·손·discard·in play, trash 제외)을 센다.
- 원판 쪽 OQ-125(비용 N 이하 획득 — Boundless Ambition·Conscript)도 Ix 카드에 닿는다: **확정(2026-10-23)** Row와 Reserve, Foldspace 제외.
