# Rise of Ix 확장 명세 (원판 위, `rise_of_ix` 옵션)

상태: 초안 v1 (2026-10-22, P0). 구현은 끝났다 — 계획 base-game-and-ix-plan.md P4에서 원판 판
([imperium-base.md](imperium-base.md)) 위에 얹었고(2026-10-30 master 병합 `21f28a1f`), Uprising 위의 Rise of Ix(Main p. 18의 "Adding Rise of Ix",
17절)와 Bloodlines Tech Module과 함께(10a절)는 P7(2026-10-31 `b0dfb2e5`), Ix Tech 타일만·Ix 지도자 + Tech 모드는 P8-1(2026-11-02 `3b42c827`)이다.

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
  - Spy Infiltrate와 겹칠 때(2026-10-31, P7g 앱 대조 A10): "If you wish to send an Agent to a board space occupied by another player, you may recall
    your own Spy from a connected observation post" `[Main p. 11]`은 점유된 칸이면 Spy 회수를 허락한다. 엔진은 놓는 카드 자신의 잠입 아이콘(그리고
    Helena·Infiltrate·Kwisatz)이 길을 열면 회수 줄을 내지 않고, graft 짝의 아이콘만 길을 열면 회수 줄도 낸다 — 짝을 배치 뒤에 고르므로 잠입하지 않는
    짝을 고르려면 회수가 필요하다. 앱(보조 증거, `AgentTurnPhase/<SpyInfiltrate>`)은 두 카드 중 하나의 아이콘 길이 열려 있으면 묻지 않는다(손 graft는
    두 카드를 함께 정한다). 고를 수 있는 결과는 같고 엔진의 짝 고르기 순서에서 오는 차이다.
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
| Usurp + Boundless Ambition(Immortality와 함께). 공식: "Trashing a card with Usurp does trigger effects like Replacement Eyes and cards with Unload (from RISE OF IX)." `[Immortality p. 14]` — turn 끝의 Usurp trash가 Unload를 일으킨다. 순서만(공식 아님): Usurp로 graft한 Boundless Ambition이 turn 끝에 trash되어 Unload로 카드를 얻을 때, Imperium Row를 5장으로 채우기 전인가 뒤인가 — "After. You immediately refill to 5 and can acquire that new card" (비용 5 이하일 때) (Direwolf Discord, 커뮤니티 정리본(elessar, 2026-06-07) 경유 — 공식 FAQ 아님, 말한 사람 이름 없음). 공식 FAQ(2025-01-13)와 Immortality 룰북에는 Row 채우기와 Unload의 순서를 달리 정하는 문장이 없다 | 채택(엔진 그대로, P7b 2026-10-30): graft할 때 빌린 Row 카드 자리가 덱 맨 위에서 바로 채워지므로(OQ-054, chance 단계 없음) 턴 종료 누름의 trash가 Unload를 일으킬 때 새 카드는 이미 Row에 있다. Unload는 소유자 자신의 turn 안에서 생겨 turn 줄(의무)로 기다리고 turn이 다시 열린다(OQ-095 (5)); 소유자가 줄을 눌러 획득 창(`UNLOAD_ACQUIRE_KEY`)을 열고 고른 뒤 다시 "턴 종료"를 눌러야 다음 좌석의 turn이 열린다. 시험 `tests/unit/rules/test_imperium_immortality.py::test_a_usurped_boundless_ambition_acquires_after_the_row_refills` |

## 10. Leader 6명

| Leader | 왼쪽 능력 | Signet Ring | 판정·주의 |
| --- | --- | --- | --- |
| Archduke Armand Ecaz (2) | Coordination: Reveal turn에 Landsraad·City·Spice Trade 칸에 Agent 둘 이상이면 in play 카드 하나를 trash할 수 있다 | Conscript: 비용 3 이하 카드 하나를 얻을 수 있다 | `[FAQ p. 1]`; Mentat도 그의 Agent로 센다(디자이너 판정) |
| Ilesa Ecaz (3) | One Step Ahead: Round Start에 손의 카드 하나를 따로 둔다. 라운드의 둘째 turn을 시작할 때 공개해 손으로 되돌린다. 그 turn에 그 카드로 Agent를 보내면 Agent 아이콘이 정확히 하나면 spice 1, 아니면 1 Solari | Guild Contacts: 1 Solari → Foldspace 획득 | `[Rise of Ix p. 10]` `[FAQ p. 2]`; Agent 없는 pass와 Weirding Way 추가 turn 모두 센다(OQ-119 사용자 확정) |
| Prince Rhombur Vernius (1) | Heavy Lasgun Cannons: dreadnought strength 4 | Ixian Technology: Acquire Tech -OR- Tech Negotiation | 오른쪽 아이콘이 Tech Negotiation인 근거: Rival 문장 "Acquire Tech if he can. If not, he will use the Tech Negotiation icon" `[Rise of Ix p. 8]` |
| "Princess" Yuna Moritani (2) | Smuggling Operation: water 없이 시작; 자기 turn에 Solari를 얻을 때마다 1 더 | Final Delivery: 7 Solari → Influence 1(골라)·troop 1·spice 1 | `[FAQ p. 3]`; Dividends로 남의 turn에 받는 1 Solari에는 붙지 않는다(OQ-042·OQ-063 "your turn") |
| Tessia Vernius (4) | Careful Observation: 시작에 Snooper token을 각 track의 Influence 2 칸에. 그 token에 도달할 때마다 Snooper track의 맨 위 덮이지 않은 보상을 받는다(① discard → spice 1, ② 그 track의 4칸 보너스, ③ 그 track에 Influence 1, ④ ②와 ③) | Duplicity: Influence 1 잃기 → Snooper token이 있는 진영에 Influence 1 | 디자이너 판정 9.3. "도달"은 Influence를 한꺼번에 얻으며 지나가도 도달(Uprising과 같다, [uprising-systems.md](uprising-systems.md)). 한 효과가 여러 진영을 함께 올리면 소유자가 순서를 고르고(Quid Pro Quo는 진영마다 줄, "Choose two:"는 고른 순서), Duplicity는 같은 진영을 잃고 얻어도 된다(OQ-153) |
| Viscount Hundro Moritani (1) | Intelligence: 게임 시작에 Intrigue 덱 위 두 장을 보고 하나를 갖고 하나를 위에 되돌린다 | Couriers: spice 1 → Freighter | Signet 아이콘이 Freighter인 근거: Rival 문장 "spend 1 spice … for the Freighter icon" `[Rise of Ix p. 8]` |

- Ix 보드 없이(지도자 + Tech 모드, `ix_leaders`, 10a): Armand·Ilesa·Yuna·Tessia만 고를 수 있다. Hundro(Couriers의 Freighter)와 Rhombur(dreadnought,
  Tech Negotiation)는 뺀다 — [OQ-165](open-questions.md#oq-165--ix-보드-없이-쓰는-ix-지도자와-tech-타일지도자tech-모드)(사용자 2026-11-01, project
  convention). Uprising 판의 Ilesa는 원판 Foldspace 더미를 쓴다(17절 `[Main p. 18]`).
- 앱 대조(2026-10-31, 보조 증거, P6 세션 `p7g-app-compare-2026-10-31.md` 8절 A11): 앱은 한 번의 Influence 변화에서 진영 칸 보너스(2칸 VP, 동맹,
  4칸 보너스)를 먼저 주고 그 뒤에 Snooper를 낸다. 엔진은 칸을 하나씩 올라 2칸의 Snooper가 4칸 보너스보다 먼저다. 둘이 갈리는 것은 Snooper가 남은
  track에서 한 번의 획득이 2칸과 4칸을 함께 지날 때뿐이다 — Snooper token은 Tessia가 처음 2칸에 닿을 때 가져가므로 1 이하에서 4 이상으로, 한 진영에
  +3 이상이 한 번에 와야 한다. 어느 조합의 카드·보상도 한 진영에 한 번에 +2를 넘게 주지 않는다(`GainInfluence(times=2, ...)`가 가장 크다). Snooper ③의
  Influence 1이 +2 뒤에 이어져 4칸에 닿는 경우도 끝 상태와 받는 보너스는 두 순서에서 같다. 그래서 플레이어가 보는 차이가 없어 엔진을 바꾸지 않는다.
  같은 묶음의 A12(Foldspace 6장은 Reserve에 두되 Guild Contacts만 얻음), A13(Strongarm: troop 하나, 둘 다 있을 때만 물음), A14(dreadnought의 지배 칸:
  Uprising의 Arrakeen·Spice Refinery·Imperial Basin)는 엔진과 같다.

## 10a. Bloodlines Tech Module과 함께 (`[Bloodlines p. 7]`, P7)

2026-10-29, 사용자 지시("assets/rulebooks 에 룰북 다 있을텐데")로 로컬 Bloodlines 룰북의 해당 쪽만 읽었다. "Combining the Tech Module with RISE OF IX":

- 두 모듈의 Tech 타일을 모두 섞어 될 수 있는 대로 고르게 큰 더미 셋으로 나눈다.
- Rise of Ix의 Tech 타일만 쓸 때(Ix의 다른 구성물 없이): Detonation Devices와 Troop Transports를 빼고 나머지 16장을 Bloodlines 타일과 섞는다.
- Rise of Ix를 모두 쓸 때: Bloodlines의 Ixian Embassy 보드를 쓰지 않고 세 더미를 Ix 보드에 둔다. Tech Negotiation의 할인은 쓰고, High Council
  자리에 따른 Ixian Embassy 할인은 없다.
- Rise of Ix를 모두 쓸 때 CHOAM 덮개가 Sardaukar Commander 자리 둘을 덮으므로, setup에서 Commander 하나를 Dreadnought 칸에, 4인 판이면 다른 하나를
  Tech Negotiation 칸에 둔다.

`rise_of_ix`는 Ix 전부다. 그래서 `rise_of_ix`를 켠 Bloodlines(Tech Module) + Rise of Ix 판은 셋째·넷째 줄대로다: 타일 36장을 한 묶음으로
섞어 세 더미(12장씩), Ixian Embassy 없음, Commander 자리 옮김 — Uprising에서다(CHOAM이 없으면 CHOAM Transports를 빼 35장). 원판에서는 Bloodlines
타일 다섯을 빼고("If you are playing with the original DUNE: IMPERIUM rather than UPRISING, exclude Advanced Data Analysis, Forbidden Weapons,
Ornithopter Fleet, Panopticon, and Spy Drones." `[Bloodlines p. 6]`) CHOAM이 없어 CHOAM Transports도 빼므로 12장, Ix를 더해 30장을 세 더미(10장씩)로
나눈다. 원판 + Bloodlines가 열리는 P7c에서 구현한다(그때까지 setup이 거절).

- 구현 (P7c, `3b15a8f7`): 원판 + Bloodlines(Tech Module) + Ix는 타일 30장(Ix 18 + Tech 12)을 Bloodlines setup에서 한 번 섞어 10·10·10으로 Ix 보드에
  둔다. Ixian Embassy가 없으므로 Landsraad 방문의 Acquire Tech와 High Council 할인이 없고, Ix 판의 Acquire Tech가 두 모듈 타일 모두에 Negotiator
  할인과 Kota Odax의 Secret Project(spice 1 할인)를 준다(codec에 Tech Module 타일의 Negotiator 행 — `tech_module`과 `rise_of_ix`를 함께 켠 카탈로그에만).
  Commander 자리는 Dreadnought·Tech Negotiation. Uprising판의 36/35장과 자리 옮김은 같은 함수(`tech_tile_pool`, `commander_setup_space_ids`)에 있고 setup이
  아직 거절한다(P7f).

- 구현 (P8-1, 2026-11-01, [OQ-165](open-questions.md#oq-165--ix-보드-없이-쓰는-ix-지도자와-tech-타일지도자tech-모드)): 둘째 줄의 "Tech 타일만"은
  `ix_tech_tiles`다(Tech Module이 필요하고 `rise_of_ix`와 함께 켜지 않는다). Ix 타일 16장(`IX_TILES_LEFT_OUT_WITHOUT_IX_BOARD`를 뺌)을 Tech Module
  타일과 한 번 섞어 Ixian Embassy의 세 더미로 될 수 있는 대로 고르게 나눈다 — Uprising 34장(12·11·11)·CHOAM 없이 33장(11·11·11),
  원판 28장(10·9·9). Embassy를 빼는 문장은 "Rise of Ix를 모두 쓸 때"뿐이라 Embassy가 그대로 있고, Landsraad 방문의 Acquire Tech와 High Council 할인이 Ix
  타일에도 붙는다. Negotiator·Freighter·dreadnought는 없다. Ix 타일의 능력(Round Start 둘, Reveal 넷, 뒤집기 넷, trash 둘, Spaceport, Windtraps,
  Endgame 셋)은 판이 아니라 타일의 것이라 그대로 돈다(`RulesetConfig.ix_tech_in_play`). 사용자 판정(2026-11-01)으로 Game Room 앱의 "Ix 지도자 + Tech"도
  옵션이다(`ix_leaders`, project convention): 같은 16장에 Ix 보드가 필요 없는 지도자 넷 — Hundro와 Rhombur는 뺀다(OQ-165, 10절). Scouts와 함께면 Ix 전부나
  지도자 + Tech만 고를 수 있다(사용자 판정). 원판의 Epic은 Ix 전부와만(11절). 시험: `tests/unit/rules/test_ix_parts.py`.

## 11. Epic Game Mode (원판 + Ix, `[Rise of Ix p. 10]`)

12점까지. Conflict I을 쓰지 않고 무작위 II 다섯 장을 III 다섯 장 위에 놓는다 — 원판 + Ix의 III은 다섯 장(원판 4 + Economic Supremacy)이라 모두 쓴다. 좌석마다
Dune, the Desert Planet 하나를 Control the Spice로 바꾸고, 모두 Intrigue 1장을 뽑고(Hundro는 모두 뽑은 뒤 Intelligence), garrison troop 5로 시작한다.
Uprising 위의 구현([epic-game-mode.md](epic-game-mode.md))을 다시 쓴다(계획 9절 9).
- 구현(2026-10-30, P4e, `d88c6a7d`·`e8a0a2d8`·`556e57ea`): setup은 원판에서 `epic_game`을 `rise_of_ix`와 함께일 때만 받는다(없으면
  `NotImplementedError`). Conflict 단계·garrison 5·12점 끝·First Player부터의 Intrigue 나누기는 Uprising Epic 경로가 그대로 읽고, 원판 시작 덱만
  Dune, the Desert Planet 하나를 Control the Spice로 바꾼다(원판 시작 카드는 Uprising 인쇄본, imperium-base.md 3). Hundro의 Intelligence는 두
  setup 경로 모두 모두가 뽑은 뒤 섞인 덱을 본다(시험: `tests/unit/rules/test_ix_epic.py`). Go to 11은 Immortality가 필요해 원판에서는 P7까지 닿지 않는다
  (OQ-093의 0 → 12는 시험으로 고정). 관측은 v28의 `epic_game` 표시를 그대로 쓴다.

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
| Ilesa Ecaz의 따로 둔 카드 | Ilesa 좌석 | 둘째 turn에 공개(그 뒤 손에 있지만 공개 경로로 들어온 카드 — OQ-010) | 따로 둔 카드는 손·discard·in play가 아니어서 trash·discard 대상이 아니다(디자이너 판정). 행동 로그의 라운드 시작 "따로 둠" 줄은 카드가 돌아온 뒤에도 다른 좌석에 `(비공개)`(OQ-154, 2026-10-30 사용자) |
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

## 17. Uprising과 함께 (`[Main p. 18]` "ADDING RISE OF IX", P7)

Uprising Main Rulebook p. 18(공식 온라인 PDF, `tmp/official-rules/diu-main.txt`):

- setup에서 CHOAM 덮개를 반만 펴 Uprising 보드의 오른쪽 위만 덮는다 — 새 CHOAM 구역이 생기고 Landsraad의 Assembly Hall·Gather Support를 덮으며,
  Uprising Landsraad의 나머지 칸은 그대로다.
- **덮이는 칸은 넷이다(2026-10-30, 사용자 "shipping / accept contract 도 가려지잖아"):** 새 CHOAM 구역은 그 구석에 있던 Uprising의 CHOAM 칸
  Shipping·Accept Contract 위에 놓인다. "나머지는 그대로"는 Landsraad 칸에만 하는 말이다. 같은 결론을 두 공식 문장이 준다 — "The RISE OF IX expansion
  replaces one of the locations on the UPRISING board where you can take a new contract." `[Main p. 16]`(계약을 주는 칸은 Dutiful Service와 Accept
  Contract뿐이므로 그 칸은 Accept Contract), "RISE OF IX: Remove these 5 UPRISING cards: Accept Contract/Shipping (2 copies), Gather Support (2 copies),
  and Assembly Hall." `[Supplements p. 6]`(House Hagal에서 판에 없는 칸의 카드를 뺀다). 보드 그림에서도 Assembly Hall·Gather Support(x≈65.6%)와
  Shipping·Accept Contract(x≈85%)는 같은 위쪽 줄(y 3~13%)이다(`display/board_layout.py`). 그래서 판의 계약 칸은 Dutiful Service뿐이고, Ix 계약
  10장(`[Main p. 16]`)이 그 보충이다.
- 덮개와 Ix 보드에는 관측 초소가 인쇄돼 있지 않다. 각 보드에 관측 초소가 하나씩 있는 것으로 친다: 하나는 Interstellar Shipping·Smuggling에, 다른 하나는
  Tech Negotiation·Dreadnought에 이어진다.
- Rise of Ix의 Conflict 카드는 넣지 않기를 권한다(넣어도 된다). Epic Game Mode에는 Conflict III가 하나 더 필요하므로 Economic Supremacy를 더한다. —
  **사용자 결정(2026-10-30, 계획 19.4 P7-3 (가)):** 넣지 않는다. Uprising 판에는 Uprising Conflict만, Epic이면 Economic Supremacy만.
- Ilesa Ecaz는 원판의 Foldspace 카드가 있어야 한다 — 다른 누구도 얻을 수 없지만 Ilesa는 Foldspace를 얻을 수 있다.
- **dreadnought와 Uprising(계획 19.4 P7-4, 문서로 정해짐):** "A deployed dreadnought allows the same [strength, swords, Combat Intrigue], even if you
  have it in a conflict without any troops. However, a dreadnought in your garrison does none of these things" `[FAQ p. 2]` — Conflict에 dreadnought만
  있어도 전투력·sword·Combat Intrigue를 쓴다. Shield Wall은 "no sandworms can be summoned to a Conflict at one of these three protected locations"
  `[Main p. 10]` — sandworm만 막고 dreadnought 배치는 막지 않는다. sandworm의 두 배는 "Most rewards can be doubled (but taking control of a location cannot, nor can battle icons on Conflict cards you win)"
  `[Main p. 14]` — Ix의 dreadnought 지배도 자리를 지배하는 것이라 두 배가 아니다.
- 이 결합의 구현과 그 밖의 판정은 계획 19.2 P7f.
- 구현 (P7f, `0a855f60`; 덮이는 칸 넷은 그 뒤 고침): setup이 Uprising에서 `rise_of_ix`를 받는다. 보드는 Uprising 칸에서 Assembly Hall·Gather
  Support·Shipping·Accept Contract를 빼고 Ix 칸 넷을 뒤에 둔다(`rulesets.UPRISING_IX_OVERLAID_SPACE_IDS`). 관측 초소는 새 초소 둘
  (`choam-interstellar-shipping-smuggling`, `landsraad-tech-negotiation-dreadnought`)을 더하고, 덮인 칸에만 이어진 초소 둘
  (`landsraad-assembly-hall-gather-support`, `choam-shipping-accept-contract`)은 뺀다 — 덮개는 "cover only the top-right corner of the UPRISING board"이고 그
  구석에 남는 초소는 덮개의 것 하나로 친다 `[Main p. 18]`([OQ-159](open-questions.md#oq-159--uprising--rise-of-ix에서-덮개가-덮는-landsraad-관측-초소), 룰북으로 해결). Spy 배치는 판의 초소를, 칸과 초소의 연결을 읽는
  곳(Infiltrate, Gather Intelligence, 회수, "[Spy] on [아이콘]", Leader 능력)은 모든 초소를 읽는다. Conflict는 Uprising 것만(P7-3), Epic은 Uprising의
  Economic Supremacy. Ix Imperium·Intrigue·지도자를 섞고, 원판 Foldspace 더미(6장, Reserve에서 사지 못함)를 두어 Ilesa의 Guild Contacts만 얻는다.
  dreadnought의 지배 칸은 Uprising의 Control 칸 셋. 관측 v40(초소 둘, +10칸). 2026-10-31 P7f-2부터 모든 옵션을 받는다:
  Bloodlines·Tech Module(P7c, Panopticon은 진영마다 줄, OQ-153), CHOAM 모듈(Ix 계약 10장, [choam-module.md](choam-module.md), OQ-161), Arrakeen
  Scouts(Send for Aid를 빼고 Ix 임무 셋, [arrakeen-scouts.md](arrakeen-scouts.md)). 위 dreadnought 판정 셋과 Spy Infiltrate·Ix 잠입이 The Voice를
  못 넘는 것, Strategic Push·Windtraps 줄이 sandworm으로 두 배가 아닌 것(근거: [combat-and-round-end.md](combat-and-round-end.md) 4절 — Conflict 카드의 보상이
  아니다 `[Main p. 14]`), Tessia의 Snooper ②가 Uprising 4칸 보너스(Emperor Spy, Bene Gesserit
  Intrigue)를 주는 것은 `tests/unit/rules/test_uprising_ix.py`.
- (정정, 2026-10-30) 한때 이 자리에 `[Main p. 16]`의 "계약 칸 하나를 바꾼다"가 보드와 어긋난다고 적었다. 어긋남이 아니었다 — 덮개가 Accept Contract도
  덮는다(위 "덮이는 칸은 넷이다"). CHOAM 모듈 + Ix는 아직 구현 전(Ix 계약 10장 전사, 둘 받아 하나 고르기, P7f-2).
- 구현 (P7f, `2aef37f5`): Ix와 함께면 Distraction·Coercive Negotiation의 "units"에 이번 turn의 dreadnought가 들고(Diversion과 같은 하한), Calculating의
  유닛 종류에 dreadnought가 든다 — "The RISE OF IX expansion includes another type of unit, called dreadnoughts." `[Main p. 10]`(6절 "unit" 줄).
- 구현 (P7f, `c6fed0fa`): Arrakeen Scouts 줄의 TrashCard 비용과 Reveal 선택의 trash 비용도 Unload를 비용 안에서 낸다(7절 디자이너 판정). Feyd·Fenring·Irulan의
  Signet trash는 카드 문장상 비용이 아니다(Irulan: 화살표 없이 "Trash a card from your hand. If it has a cost of 1 or more: 2 spice") — 그대로 turn 줄.

