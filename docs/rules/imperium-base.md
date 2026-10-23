# 원판 Dune: Imperium 4인 규칙 명세 (`imperium` 판)

상태: 초안 v1 (2026-10-22, P0). 구현 전이다 — 엔진은 아직 Uprising 판 하나뿐이고, 원판 판은
[base-game-and-ix-plan.md](../base-game-and-ix-plan.md)의 P1(판 축)·P2(보드·흐름)·P3(카드)에서 들어간다.
이 문서가 그 단계들의 규칙 근거다. Rise of Ix는 [rise-of-ix.md](rise-of-ix.md)에 따로 있다.

- **근거.** 원판 룰북 `[DI p. N]`(인쇄 쪽 = PDF 쪽), Player Aid `[DI Aid p. N]`(룰북 pp. 16-18과 같은 글), 2025-01-13
  FAQ `[FAQ p. N]`. 버전·checksum은 [sources.md](sources.md) "Dune: Imperium 룰북과 Player Aid".
- **Uprising과 같은 규칙은 다시 쓰지 않는다.** "Uprising과 같다"고 적은 곳은 이 저장소의 Uprising 명세를 가리키고, 원판 쪽
  근거 쪽수를 함께 단다. 같은지 다른지는 원판 룰북 문장과 Uprising Main 문장을 대조해 정했다(2026-10-22).
- **Uprising Main이 스스로 표시한 차이.** Uprising Main은 원판과 다른 곳에 기호를 붙였다("Played DUNE: IMPERIUM? Look for this
  symbol." `[Main p. 3]`). PDF에서 그 기호(이미지 xref 98)가 놓인 일곱 자리를 찾았다: setup(Mentat 없음·Shield Wall, Foldspace 카드
  없음, sandworm·Maker Hooks, Spy, Objective로 정하는 시작 플레이어 `[Main p. 5]`), Mentat Agent 없음 `[Main p. 6]`, Influence 2가
  필요한 칸이 늘고 Spy Agent 아이콘이 생김 `[Main p. 9]`, Spy `[Main p. 11]`, strength를 정하는 때 `[Main p. 13]`, battle icon·sandworm
  두 배·승자가 Conflict 카드를 가져감·sandworm 반환 `[Main p. 14]`, 카드 clarification과 CHOAM Module `[Main p. 17]`. 아래 2절의 차이표가
  이 일곱 자리를 모두 덮는다.
- **카드 자료.** 카드 효과는 이 문서에 다 적지 않는다. 카드별 값은 앱 속성 표(`agents/app_ai/data/archetypes.py`)와 앱 영어 문구에서
  옮기고 카드면으로 확인한다([card-data-sources.md](../card-data-sources.md) "Steam app data"). 이 문서는 규칙과, 카드가 새로 요구하는
  체계·판정만 적는다.

## 1. 범위

- 4인 게임만. House Hagal(1·2인 Rivals, `[DI pp. 19-20]`)은 범위 밖이다(계획 9절 5).
- 원판 프로모 3장(Duncan, Loyal Blade·Jessica of Arrakis·Thumper)은 `promo_cards` 옵션 뒤에 넣는다(계획 9절 8). 공식 문서에 없고
  근거는 카드면이다(Uprising 프로모와 같은 처리, [sources.md](sources.md) "프로모 카드의 출처").
- Uprising·Bloodlines·Immortality와의 조합, 원판의 Arrakeen Scouts는 이 문서 밖이다(계획 P7·P8).

## 2. Uprising과 다른 것 (요약표)

| 주제 | 원판 | Uprising | 근거 |
| --- | --- | --- | --- |
| 보드 | 22칸(3절), Faction 칸은 진영마다 둘(비용 있는 칸·없는 칸) | 22칸, observation post 13 | `[DI pp. 14, 17-18]` |
| 특수 Agent | Mentat(한 라운드 빌려 쓰는 Agent) | 없음 | `[DI pp. 6, 16, 18]`, `[Main p. 6]` |
| Agent 아이콘 | 7종(Emperor, Spacing Guild, Bene Gesserit, Fremen, Landsraad, City, Spice Trade) | 7종 + Spy | `[DI p. 9]`, `[Main p. 9]` |
| Influence 2 요구 칸 | Sietch Tabr 하나 | 여럿 | `[DI p. 9]`, `[Main p. 9]` |
| 없는 체계 | Spy·observation post, sandworm·Maker Hooks·Shield Wall, 계약(CHOAM Module), battle icon·Objective | 있음 | `[Main pp. 5, 9, 11, 14, 16]` |
| Reserve | 세 더미: Arrakis Liaison 8, The Spice Must Flow 10, Foldspace 6(Foldspace는 칸으로만 얻음) | 두 더미(Prepare the Way 8, The Spice Must Flow 10) | `[DI pp. 3, 4, 11]`, `[Main p. 3]`, `[FAQ p. 2]` |
| Control 칸 | Arrakeen, Carthag, Imperial Basin(보너스 1 Solari·1 Solari·1 spice) | Arrakeen, Spice Refinery, Imperial Basin | `[DI p. 10]`, `[Main p. 10]` |
| Maker 칸 | The Great Flat, Hagga Basin, Imperial Basin | Deep Desert, Hagga Basin, Imperial Basin(+6인 Habbanya Erg) | `[DI pp. 10, 13]`, `[FAQ p. 2]` |
| 시작 플레이어 | 무작위 | Objective 카드 | `[DI p. 5]`, `[Main p. 5]` |
| strength 정하기 | Reveal turn의 별도 단계(Reveal Cards → Resolve Reveal Effects → Set Strength → Clean Up) | Reveal 효과 중 아무 때나, 갱신 | `[DI p. 11]`, `[Main p. 13]` |
| strength 단위 | troop 2, sword 1; Conflict에 troop이 하나도 없으면 0 | troop 2, sandworm 3, sword 1; 유닛이 없으면 0 | `[DI p. 11]`, `[Main p. 12]` |
| Conflict 카드 | 공개한 카드는 덱 옆 face-up 더미에 쌓이고 승자가 가져가지 않는다 | 승자가 supply로 가져가 battle icon 확인 | `[DI pp. 8, 12]`, `[Main p. 14]` |
| Combat Intrigue 자격 | Conflict에 troop 하나 이상 | 유닛 하나 이상 | `[DI p. 12]`, `[Main p. 14]` |
| Influence 4칸 보너스 | 보드에 인쇄된 원판 값(값은 6절, 아직 미확인) | Spy·3 Solari·Intrigue·water | `[DI p. 7]`, [uprising-systems.md](uprising-systems.md) |
| Recall | Mentat을 제 칸으로 돌린 뒤 Agent recall, 시작 플레이어 넘김 | Agent recall, 시작 플레이어 넘김 | `[DI p. 13]`, `[Main p. 15]` |
| Leader | 8명, 한 면 | 양면 Leader 포함 | `[DI p. 3]`, `[Main p. 3]` |

같은 것(문장 대조): 4인 setup의 Score 1칸·garrison troop 3·water 1, Conflict 덱(I 1장 위에 II 5장, 그 아래 III 4장, 쓰지 않는 카드는 보지 않고
상자로), Imperium Row 5장, 라운드 다섯 phase, Agent turn과 Reveal turn, Plot·Combat·Endgame Intrigue, 배치 규칙(이번 turn에 recruit한 troop 전부 +
garrison에서 둘까지), 4인 순위 보상과 동률, Combat 정리(troop은 supply로, marker는 0으로), Makers, 10점 또는 Conflict 덱 소진으로 Endgame,
Endgame 동률(spice → Solari → water → garrison troop, 그다음 가장 최근 Reveal turn). `[DI pp. 4-13]` `[Main pp. 4-15]` `[FAQ p. 2]`

## 3. 구성물과 구성표

룰북 합계, BGG 카드 시트(에셋 `reference/bgg-card-inventory/`), 앱 `CardCount`(로컬 추출 `reference/dune-steam-app/<build>/analysis/
base-ix-2026-10-22/`)가 카드 130종에서 **모두 같다**(2026-10-22 대조; 다른 것은 이름 표기뿐 — `<br>` 줄바꿈, "Arrakis Liason", "The Spice
Must Flow (Base)"). P1 이후 이 표를 테스트로 고정한다(계획 10.1절 5).

| 종류 | 종류 수 | 장수 | 룰북 | 비고 |
| --- | --- | --- | --- | --- |
| Imperium 덱 | 43 | 67 | 67 `[DI p. 3]` | 프로모 3종 3장은 따로(`promo_cards`) |
| Reserve | 3 | 24 | Arrakis Liaison 8, The Spice Must Flow 10, Foldspace 6 `[DI p. 3]` | |
| 시작 덱(좌석마다) | 7 | 10 | Convincing Argument 2, Dagger 2, Diplomacy 1, Dune, the Desert Planet 2, Reconnaissance 1, Seek Allies 1, Signet Ring 1 `[DI p. 3]` | Uprising 시작 덱과 같다(앱도 `BaseSet` 정의 하나를 쓴다) |
| Intrigue | 34 | 40 | 40 `[DI p. 3]` | Plot·Combat·Endgame; Tiebreaker는 Combat·Endgame 두 면 |
| Conflict | 18 | 18 | I 4, II 10, III 4 `[DI p. 3]` | 앱 `ConflictLevel`도 4·10·4 |
| Leader | 8 | 8 | `[DI p. 3]` | |
| 보드 칸 | 22 | | `[DI pp. 17-18]` | |
| 기타 | | | Mentat 1, Alliance token 4, First Player marker, Baron Harkonnen token 4 `[DI p. 3]` | 좌석마다 Agent 3(셋째는 Swordmaster), Control marker 3, cube 16(4는 Influence, 12는 troop), disc 2, Councilor 1, Combat marker 1 `[DI p. 3]` |

**앱과 카드면이 다른 값.** 블라인드로 읽은 Dune Cards Hub 스캔(2026-10-22, agent 넷, 카드 181장)을 앱 속성과 기계 대조했다.
Imperium 76종과 Tech 18장의 비용·Agent 아이콘·진영·무조건 Reveal 값에서 다른 곳은 **Duncan Idaho의 Reveal 검 하나**였다(앱 2, Dune
Cards Hub 스캔 3). 사용자가 다른 실물 스캔(duneimperiumassets.com, 검 2)을 찾아 앱 값이 맞고 Dune Cards Hub 그림이 틀렸음을
확인했다(2026-10-22). 그래서 카드면 확인에 쓰는 그림의 출처를 정할 일이 남았다(계획 2.4절 4, 사용자에게 묻는다). 시작 카드 7종과 Reserve 3종은
이번 블라인드 읽기에 넣지 않았다(시작 카드는 Uprising과 같은 카드이고 이미 전사돼 있다). Arrakis Liaison은 앱 자료밖에 없으니 P3 전에 카드면으로 확인한다.

## 4. Setup (4인)

순서와 내용은 `[DI pp. 4-5]`의 A~H를 따른다. Uprising과 다른 곳만 적는다.

- **A.** Mentat을 Mentat 칸에 눕혀 놓는다(A1). Alliance token 넷을 각 Faction Influence track의 표시된 자리에 놓는다(A2). `[DI p. 4]`
- **B.** Conflict 덱은 Uprising과 같은 모양(I 1, II 5, III 4)이다. 원판은 III 4장을 모두 쓴다. `[DI p. 4]`
- **C.** Intrigue 덱, Imperium 덱과 Row 5장, Reserve **세 더미**(Arrakis Liaison, The Spice Must Flow, Foldspace). `[DI p. 4]`
- **D.** Leader는 고르거나 무작위로 받는다. 같은 가문 둘을 함께 쓰지 말라는 것은 권고("shouldn't")이고 규칙이 아니다. `[DI pp. 2, 4]`
  이 프로젝트의 지도자 고르기 방식(고정·draft)은 Uprising과 같은 틀을 쓴다.
- **E~G.** 시작 덱 10장, water 1, bank(무제한), Agent 둘은 Leader 위·셋째(Swordmaster)는 보드 옆, Score 1칸(4인), Combat marker 0, Influence
  cube 넷, troop 3개를 가장 가까운 garrison에. `[DI p. 5]`
- **H.** 시작 플레이어는 **무작위**로 정한다. `[DI p. 5]`
- **Leader setup.** Glossu "Beast" Rabban은 spice 1·Solari 1을 더 받고 시작한다 `[Rabban card]`. Baron Vladimir Harkonnen은 모든 setup을 마친
  뒤 첫 라운드 전에 진영 둘을 비밀로 고른다 `[FAQ p. 1]`(4개 token 가운데 둘을 진영 면이 아래로 가게 Leader 위에 두고, 나머지 둘은 상대가
  못 보게 상자로 `[DI p. 13]`).

## 5. 라운드와 turn

Uprising과 같은 틀이다([setup-and-game-flow.md](setup-and-game-flow.md), [player-turns.md](player-turns.md)). 원판만의 것:

- **Round Start.** Conflict 공개 → (자기가 control하는 칸의 Conflict면) supply의 troop 하나를 Conflict에 배치할 수 있다 → 각자 5장 뽑기.
  `[DI pp. 8, 10, 16]` Uprising과 같다(OQ-072의 공개 → 방어 → 뽑기 순서).
- **Agent turn.** 카드를 내고 그 카드의 Agent 아이콘과 맞는 빈 칸에 Agent를 보낸다. 칸의 비용은 어떤 효과보다 먼저 낸다. 칸 효과, Agent box,
  Faction 칸의 Influence 1은 원하는 순서로 처리한다. `[DI p. 9]` Agent 아이콘이 없는 카드는 Agent turn에 낼 수 없다 `[DI p. 9]`.
- **Reveal turn.** Reveal Cards → Resolve Reveal Effects(순서 자유, Persuasion으로 카드 획득은 그 앞·사이·뒤 아무 때나) → **Set Strength** →
  Clean Up. `[DI p. 11]` 원판은 strength를 정하는 단계가 따로 있다. 원판에는 Reveal 도중 strength를 읽는 카드가 없으므로 엔진이 Uprising처럼
  strength를 계속 갱신해도 결과가 같다 — 이 "같다"는 원판 카드 전사(P3)에서 strength를 읽는 효과가 없는지 다시 확인한다.
- **카드 획득.** Imperium Row 5장, Reserve의 Arrakis Liaison·The Spice Must Flow. Foldspace는 Foldspace 아이콘으로만 얻는다. `[DI p. 11]`
  `[FAQ p. 2]` 획득한 카드는 discard pile로 간다. Row는 늘 5장으로 채운다. `[DI p. 11]`
- **Plot Intrigue**는 자기 Agent·Reveal turn 안에서 아무 때나 낸다. `[DI pp. 7-8]` Uprising과 같다.
- **Combat → Makers → Recall.** 7~9절.

## 6. Faction, Influence, Alliance

- 진영 넷(Emperor, Spacing Guild, Bene Gesserit, Fremen). Faction 칸에 Agent를 보내면 Influence 1. `[DI p. 7]`
- Influence 2 도달 → 1 VP(내려가면 잃음). Influence 4 도달 → 그 칸에 인쇄된 보너스(내려가도 돌려주지 않고, 다시 올라오면 또 받음). 처음 4에
  도달한 플레이어가 Alliance token과 그 VP를 얻고, 더 높이 올라온 상대에게 넘긴다. `[DI p. 7]` FAQ의 Alliance 판정(동률 상대에게 넘김, 3 이하로
  내려가면 잃음) `[FAQ p. 1]`. 모두 Uprising과 같다([uprising-systems.md](uprising-systems.md)).
- **글로 없는 값 (출처 미확정).** 원판 Influence 4칸 보너스 넷은 룰북에 글로 없고 보드 그림에만 있다("the bonus shown on that space of the track"
  `[DI p. 7]`). 룰북 p. 4의 setup 그림은 보드 이미지가 426×649 픽셀이라 이 아이콘을 읽기에 작다 — Uprising에서 작은 그림으로 읽다 틀린 일이
  있다(`docs/lessons.md` 2026-09-19). 그래서 이 명세는 값을 적지 않는다. P2 전에 앱(Influence 처리 `worm.canis.actions.GainFactionInfluence`와
  보드 장면)에서 값을 읽고, 고화질 보드 그림을 찾으면(계획 9절 7, 미룸) 그것으로 확인한다.
- Alliance token의 VP는 token에 인쇄돼 있다("gain the Victory Point shown on the Alliance token" `[DI p. 7]`). Uprising과 같이 1로 보이나 위와
  같은 출처로 P2에서 확인한다.

## 7. Control과 배치

- Arrakeen·Carthag·Imperial Basin의 Conflict를 이기면(카드 제목) 그 칸 깃발에 Control marker를 놓는다(상대 marker를 바꿈). 누가 그 칸에 Agent를
  보내든 controller가 Arrakeen·Carthag는 1 Solari, Imperial Basin은 1 spice를 받는다. 자기가 control하는 칸의 Conflict가 공개되면 supply의
  troop 하나를 Conflict에 배치할 수 있다. `[DI pp. 10, 16]`
- Combat 칸(사막 그림과 교차한 칼)에 Agent를 보내면 이번 turn에 recruit한 troop 전부와 garrison의 troop 둘까지를 Conflict에 배치할 수 있다. 원판의
  Combat 칸은 Arrakeen, Carthag, Research Station, Sietch Tabr, Imperial Basin, Hagga Basin, The Great Flat, Heighliner, Hardy Warriors, Stillsuits다.
  `[DI pp. 10, 17-18]` FAQ의 troops 판정(어느 출처로 recruit했든 배치 가능, garrison의 troop을 다시 recruit해 상한을 넘을 수 없음) `[FAQ p. 4]`.

## 8. 보드 칸 22개

비용은 효과보다 먼저 낸다 `[DI p. 9]`. "×"는 Combat 칸, "M"은 Maker 칸. 앱 속성(`SpaceArchetypes.BaseSet.*`)의 비용·병력·자원·요구 Influence와
모두 같다(2026-10-22 대조).

| 칸 | 아이콘 | 비용·요구 | 효과 | | 근거 |
| --- | --- | --- | --- | --- | --- |
| Conspire | Emperor | spice 4 | Emperor Influence 1, 5 Solari, troop 2, Intrigue 1 | | `[DI p. 17]` |
| Wealth | Emperor | – | Emperor Influence 1, 2 Solari | | `[DI p. 18]` |
| Heighliner | Spacing Guild | spice 6 | Guild Influence 1, troop 5, water 2 | × | `[DI p. 17]` |
| Foldspace | Spacing Guild | – | Guild Influence 1, Foldspace 카드 1장 획득 | | `[DI p. 17]` |
| Selective Breeding | Bene Gesserit | spice 2 | BG Influence 1, 카드 1장 trash → 2장 뽑기 | | `[DI p. 18]` |
| Secrets | Bene Gesserit | – | BG Influence 1, Intrigue 1, Intrigue 4장 이상인 상대마다 무작위 1장을 받음 | | `[DI p. 18]` |
| Hardy Warriors | Fremen | water 1 | Fremen Influence 1, troop 2 | × | `[DI p. 17]` |
| Stillsuits | Fremen | – | Fremen Influence 1, water 1 | × | `[DI p. 18]` |
| Hall of Oratory | Landsraad | – | troop 1; 여기 Agent가 있으면 자기 Reveal turn에 Persuasion 1 | | `[DI p. 17]` |
| Rally Troops | Landsraad | 4 Solari | troop 4 | | `[DI p. 18]` |
| Mentat | Landsraad | 2 Solari | 카드 1장; Mentat이 여기 있으면 가져가 이번 라운드 Agent로 씀(Recall에 돌려놓음) | | `[DI p. 18]` |
| Swordmaster | Landsraad | 8 Solari | 게임에 한 번; 셋째 Agent를 얻어 이번 라운드부터 씀 | | `[DI p. 18]` |
| High Council | Landsraad | 5 Solari | 게임에 한 번; Councilor를 빈 자리에, 이후 Reveal turn마다 Persuasion 2 | | `[DI p. 17]` |
| Arrakeen | City | – | troop 1, 카드 1장; controller 1 Solari | × | `[DI p. 17]` |
| Carthag | City | – | troop 1, Intrigue 1; controller 1 Solari | × | `[DI p. 17]` |
| Research Station | City | water 2 | 카드 3장 | × | `[DI p. 18]` |
| Sietch Tabr | City | Fremen Influence 2 이상 | troop 1, water 1 | × | `[DI pp. 9, 18]` |
| Imperial Basin | Spice Trade | – | spice 1 + 쌓인 bonus spice; controller 1 spice | × M | `[DI p. 18]` |
| Hagga Basin | Spice Trade | water 1 | spice 2 + bonus | × M | `[DI p. 17]` |
| The Great Flat | Spice Trade | water 2 | spice 3 + bonus | × M | `[DI p. 17]` |
| Secure Contract | Spice Trade | – | 3 Solari | | `[DI p. 18]` |
| Sell Melange | Spice Trade | spice 2~5 | 낸 양에 따라 보드에 인쇄된 Solari; 한 turn에 한 번만 교환 | | `[DI p. 18]` |

- **글로 없는 값.** Sell Melange의 교환표("the amount of Solari shown based on the cost you paid" `[DI p. 18]`)는 보드 그림에만 있다. 앱 코드는
  spice 2·3·4·5 → 6·8·10·12 Solari로 계산한다(`SpaceAbilities.BaseSet.SellMelangeSpaceAbility`, 2026-10-22 카드별 조사). 6절의 Influence 보너스와
  같이 P2에서 보드 그림으로 확인해 정한다.
- **같은 이름, 다른 인쇄(계획 4.2절 7).** 앱은 Arrakeen·Imperial Basin·Secrets를 원판과 Uprising이 함께 쓰는 정의 하나로 두고(인쇄가 같다),
  Heighliner(원판 spice 6 → troop 5·water 2 / Uprising spice 5 → troop 5)·Hagga Basin(원판 spice 2 / Uprising은 모래벌레 선택)·Sietch Tabr·
  Research Station·High Council·Swordmaster는 따로 둔다. 엔진 id도 이 구분을 따른다(같은 인쇄는 같은 id). Swordmaster와 High Council은 앱
  속성(비용 8·5)이 같지만 효과 문장이 다르다(Uprising의 High Council은 보상이 더 있다) — P1의 id 표에서 효과까지 비교해 정한다.
- **Selective Breeding의 trash.** "Trash one card to draw two cards" `[DI p. 18]`. trash가 2장 뽑기의 비용이므로 하지 않을 수 있다(화살표 비용,
  `[DI p. 9]` "You are never forced to pay such a cost"). 자기를 trash하는 카드(Seek Allies, Foldspace, Power Play, Rise of Ix의 Treachery)를
  이 비용으로 trash할 수 있고 그 카드의 다른 효과도 얻는다(디자이너 판정, BGG Forum; 공식 FAQ의 같은 방향 판정 — Beguiling Pheromones로
  "a card that would otherwise be trashed anyway (for example: Foldspace, Seek Allies)"를 trash할 수 있다 `[FAQ p. 1]`). OQ-022(trash된 카드의
  효과는 발동 불가)와 함께 읽으면 그 카드의 다른 효과를 먼저 해결하고 trash해야 얻는다.

## 9. Mentat

- Mentat 칸에 Agent를 보내면 카드 1장을 뽑고, Mentat이 칸에 있으면 가져와 Leader 위에 둔다. 이번 라운드 동안 Agent 하나로 쓴다(Agent turn에
  보낼 수 있다). Phase 5 Recall에 제 칸으로 돌린다. `[DI pp. 6, 13, 18]`
- Mentat 아이콘(Conflict 보상·Intrigue): 칸에 있을 때만 가져온다(상대나 다른 칸에서 못 가져옴). Conflict 보상으로 받으면 다음 라운드에 Agent로
  쓰고 이번 라운드 끝에 돌려놓지 않는다. `[DI p. 16]` Sort Through the Chaos를 이기면 Mentat은 다음 라운드 시작에 가져간다 `[FAQ p. 4]`(Steam 앱은
  Combat 중에 준다 — FAQ를 따른다). 그 다음 라운드 동안 Mentat 칸은 비어 있다. Mentat 자체도 Mentat 칸에 보낼 수 있지만 카드 1장만 뽑고 Agent로 남는다(다시 가져오지 않음, OQ-124 사용자 확정).
  Calculated Hire는 Mentat을 Landsraad의 제 자리에서만 가져온다 `[DI p. 13]`, Mentat이 그 자리에 있어야 낼 수 있다(디자이너 판정, BGG Forum).
- 가져간 Mentat은 그 라운드 끝까지 그 플레이어의 Agent(그 색)로 모든 목적에 친다(디자이너 판정, BGG Forum — Archduke Armand Ecaz의 Coordination이
  센다). 그래서 Agent recall 효과(Urgent Mission)가 Mentat을 되돌릴 수 있고, Kwisatz Haderach가 Mentat을 옮길 수 있다.

## 10. Combat, Makers, Recall, Endgame

- **strength.** troop 2, 이번 Reveal turn에 공개한 sword 1. Conflict에 troop이 하나도 없으면 0이고 어떤 수단으로도 올릴 수 없다. `[DI p. 11]`
- **Combat Intrigue.** 시작 플레이어부터 시계 방향으로, Conflict에 troop이 있는 플레이어가 Combat Intrigue를 내거나 pass한다. 참가자 전원이 연속으로
  pass하면 해결. "When you win a Conflict" 카드는 이긴 뒤 낸다. `[DI p. 12]` Uprising과 같다([combat-and-round-end.md](combat-and-round-end.md)).
- **보상·동률.** Uprising과 같다. `[DI p. 12]` 보상 순서는 OQ-102(순위대로)를 그대로 쓴다.
- **정리.** 보상을 다 준 뒤 troop은 supply로, Combat marker는 0으로. `[DI p. 12]` Conflict 카드는 공개한 자리에 남고 다음 라운드의 카드가 그 위에
  쌓인다 `[DI p. 8]`(승자가 가져가지 않는다 — Uprising과 다름).
- **Makers.** The Great Flat·Hagga Basin·Imperial Basin 가운데 Agent가 없는 칸마다 bonus spice 1. `[DI p. 13]`
- **Recall.** Endgame 조건(10점 이상 또는 Conflict 덱 소진)이 아니면 Mentat을 제 칸으로 돌리고(이미 있으면 그대로), Agent를 recall하고, 시작
  플레이어 marker를 시계 방향으로 넘긴다. `[DI p. 13]`
- **Endgame.** Endgame Intrigue를 내고 해결한 뒤 VP가 가장 많은 플레이어가 이긴다. 동률은 spice → Solari → water → garrison의 troop 순 `[DI p. 13]`,
  그래도 같으면 가장 최근에 Reveal turn을 한 플레이어 `[FAQ p. 2]`. Uprising과 같다.

## 11. 아이콘과 용어 (`[DI p. 16]`)

Uprising Main p. 20과 같은 정의: Acquire, Agent(Swordmaster), Alliance 조건, Control, 카드 뽑기, Intrigue 뽑기, Fremen Bond, In Play, Influence 조건,
Influence 얻기(하나·둘·잃기 — 둘은 한 진영), troop 잃기(supply로), Maker, 비용 화살표, Persuasion, Recall, 자원, Retreat(garrison으로), Signet Ring,
Steal Intrigue(4장 이상인 상대마다 무작위 1장), Sword, Trash(Reserve 카드는 제 더미로; 비용이거나 카드가 자기를 trash하라고 할 때만 의무), Troop,
Victory Point. 원판에만 있는 아이콘:

- **Foldspace 획득** — Reserve의 Foldspace 1장. `[DI p. 16]`
- **Mentat** — 9절. `[DI p. 16]`

Uprising에만 있는 아이콘(Spy, sandworm, Shield Wall, 계약, battle icon, Maker Hooks, 다른 Faction Bond 등)은 원판 카드에 없다. 원판에는 Bond가 Fremen
Bond 하나다 `[DI p. 16]`.

## 12. Leader 8명

능력 이름과 요지(카드면·앱 문구로 확인, 2026-10-22). 복잡도는 이름 옆 육각형 수 `[DI p. 4]`.

| Leader | 왼쪽 능력 | Signet Ring | 판정·주의 |
| --- | --- | --- | --- |
| Paul Atreides (1) | Prescience: 자기 덱 맨 위 카드를 언제든 볼 수 있다 | Discipline: 카드 1장 | 덱이 비면 볼 수 없다(discard를 섞지 않는다) `[DI p. 13]`. 숨은 정보 — 14절 |
| Duke Leto Atreides (2) | Landsraad Popularity: Landsraad 칸에 보내는 비용 1 Solari 적게 | Prudent Diplomacy: spice 1 → 상대가 나보다 Influence가 많은 진영에 Influence 1 | |
| Glossu "Beast" Rabban (1) | Arrakis Fiefdom: spice 1·Solari 1을 더 갖고 시작 | Brutality: troop 1, Faction Alliance가 하나라도 있으면 troop 2 | |
| Baron Vladimir Harkonnen (3) | Masterstroke: 시작에 진영 둘을 비밀로 고르고, 한 turn에 troop 4개 이상을 Conflict에 배치하면 공개해 각 진영 Influence 1 | Scheme: 1 Solari → Intrigue 1 | setup 뒤 첫 라운드 전에 고름, 게임에 한 번 `[FAQ p. 1]`. 첫 조건 달성 시 의무 공개; 기존 배치 조건의 문턱 4, Commander 포함·dreadnought 제외(OQ-115, 2026-10-22 사용자 판정) |
| Count Ilban Richese (1) | Ruthless Negotiator: 보드 칸의 비용으로 Solari를 낼 때마다 카드 1장 | Manufacturing: 1 Solari | 칸의 인쇄 비용으로 낼 때만 `[FAQ p. 2]` |
| Helena Richese (2) | Eyes Everywhere: 상대 Agent가 Landsraad·City 칸에서 내 Agent를 막지 않는다 | Manipulate: Imperium Row 카드 하나를 치우고 채움; 이번 라운드 Reveal turn에 치운 카드를 Persuasion 1 적게 획득 가능 | Manipulate는 Uprising Intrigue와 같은 판정 `[FAQ p. 3]` |
| Earl Memnon Thorvald (1) | Connections: High Council 자리를 얻을 때 Influence 1(진영 골라) | Spice Hoard: spice 1 | |
| Countess Ariana Thorvald (3) | Spice Addict: spice를 harvest할 때마다 spice 1 덜 얻고 카드 1장 | Hidden Reservoir: water 1 | 의무, Maker 칸에서 harvest할 때만 `[FAQ p. 2]` |

The Voice의 표시는 Control marker 수량과 무관한 별도 마커/UI로 한다(OQ-116, 2026-10-22 사용자 판정).

## 13. 카드 판정 (룰북 clarification, FAQ, 디자이너 판정)

### 13.1 룰북 clarification과 후속 판정 (기본 출처 `[DI p. 13]`; 차이는 개별 항목에 명시)

- **Bindu Suspension** — 차례 시작의 첫 행동으로만 낸다. 다른 행동을 하면 사용할 수 없다(기존 OQ-095 (6)의 turn-start 기준).
  카드 1장을 뽑은 뒤 pass하거나 정상 진행할지 **선택**한다. Agent가 없어 공개해야 하는 차례도 시작에 사용할 수 있고, 이미 공개를 시작한 뒤에는
  못 쓴다(OQ-117, 2026-10-22 사용자 선택 C). 사용자가 공식 문장으로 제시한 "then you may choose to pass your turn or play your turn normally"를
  적용한다. 고정 PDF의 의무 종료 문장과의 차이·출처 범위는 OQ-117에 남겼으며, 의무 종료라는 이전 명세는 폐기한다.
- **Calculated Hire** — 9절.
- **Demand Respect** — 이겨서 받은 spice로 낼 수 있다(To the Victor…로 먼저 spice를 얻어도 된다).
- **Kwisatz Haderach** — Agent가 남지 않아도 낼 수 있다(이미 칸에 있는 Agent를 보낸다). 방금 있던 칸으로 되돌려 보낼 수 있다. 게임에 한 번인 칸(High
  Council, Swordmaster)에 두 번 보낼 수 없고, The Voice를 넘지 못한다. Maker 칸을 떠난 뒤 Phase 4까지 비어 있으면 bonus spice가 쌓인다. 디자이너 판정:
  Agent를 먼저 놓고 카드를 뽑는다; Interstellar Shipping·Sietch Tabr의 Influence 요구는 넘지 못한다(BGG Forum, Direwolf Discord).
- **Paul Atreides / Poison Snooper** — 덱이 비면 맨 위를 볼 수 없다(discard를 섞어 덱을 만드는 것은 뽑아야 할 때뿐).
- **Test of Humanity** — 상대는 내 왼쪽부터 시계 방향으로 고른다. 각자 할 수 있는 것을 골라야 한다(손이 비면 버리기 불가, 배치한 troop이 없으면 잃기 불가).
  버리는 상대가 카드를 고른다(무작위 아님).
- **The Voice** — 고른 칸에 각 상대의 **이번 라운드 다음 Agent 배치 한 번**을 막는다(OQ-116, 2026-10-22 사용자 선택 B,
  카드 문구·디자이너 판정 채택). Bindu·Litany Against Fear 등으로 Agent를 보내지 않고 turn을 넘기면 그 상대의 봉쇄는 남는다.
  다른 칸에 Agent를 보내면 그 상대에게는 풀리므로 Weirding Way의 추가 turn에는 봉쇄가 없다. 라운드가 끝나면 남은 봉쇄도 끝난다.
  Control marker는 사용 조건·비용이 아니며 별도 목소리 마커나 UI로 표시한다. Kwisatz Haderach도 봉쇄를 넘지 못한다(`[DI p. 13]`).
  P0의 "앱은 라운드 내내 막는다"는 분석은 사용자 지적에 따라 재검증 대상으로 남겼으며 검증된 앱 동작으로 단정하지 않는다.
- **Baron Vladimir Harkonnen** — 4절·12절.

### 13.2 FAQ의 원판 항목 (`[FAQ pp. 1-4]`)

이 표가 [official-rulings-index.md](official-rulings-index.md) 4절의 "소속 미확정" 이름 가운데 원판 몫을 분류한다.

| 항목 | 쪽 | 판정 요지 |
| --- | --- | --- |
| Missionaria Protectiva (errata) | 1 | Bene Gesserit 진영, 2장. 첫 영어판의 진영 누락 오인쇄. 앱·우리 스캔도 BG |
| Assassination Mission | 1 | 다른 수단으로 trash해야 4 Solari; 카드가 스스로 trash하지 않는다 |
| Baron Vladimir Harkonnen | 1 | 진영은 setup 뒤 첫 라운드 전에 고른다; 공개·Influence는 게임에 한 번 |
| Carryall | 1 | 기본 spice: Imperial Basin 1, Hagga Basin 2, The Great Flat 3 |
| Chani (Imperium) → Retreat | 1, 3 | "any number"는 0 가능 |
| Charisma → Intrigue cards | 1, 2 | 다음 Reveal turn에 쓰는 Plot은 그때까지 face-up으로 둔다 |
| Corner the Market | 2 | 전체 보유 The Spice Must Flow(덱·손·discard·in play, trash 제외)를 센다(OQ-123 사용자 확정; FAQ는 덱·discard를 열거); 상대 하나라도 같거나 많으면 둘째 조건 실패. 두 조건은 따로 1 VP씩(Rivals 문장 "You'll need three yourself to get 2 Victory Points" `[DI p. 20]`) |
| Count Ilban Richese | 2 | 칸의 인쇄 비용으로 Solari를 낼 때만 |
| Countess Ariana Thorvald | 2 | 의무; Maker 칸 harvest만 |
| Demand Respect → Intrigue cards | 2 | 조건·비용을 갖춰야 낸다 |
| discard | 2 | 따로 말이 없으면 손의 카드(Mohiam, Test of Humanity) |
| Dispatch an Envoy | 2 | 아이콘을 지우지 않고, 이미 있는 아이콘을 하나 더 주지 않는다 |
| Double Cross | 2 | 상대 하나 이상이 Conflict에 troop이 있어야 낸다; 내 supply는 비어도 된다 |
| Foldspace | 2 | Foldspace 아이콘으로만 획득(칸, Ilesa Ecaz) |
| Guild Bankers | 2 | 이번 turn에 얻는 The Spice Must Flow마다 할인 |
| Gun Thopter | 2 | garrison troop이 없는 상대는 영향 없음 |
| Helena Richese → Manipulate | 2, 3 | Uprising Intrigue Manipulate와 같다 |
| Imperial Spy | 2 | 이 카드로 자신을 trash해야 Intrigue; 다른 수단으로 trash되면 없음 |
| Liet Kynes | 2 | 이번 라운드 Agent turn의 카드와 지금 Reveal turn의 카드를 센다; 장마다 Persuasion 2 |
| maker board space | 2 | 원판 Maker 칸: Hagga Basin, Imperial Basin, The Great Flat |
| Plans Within Plans | 3 | Influence 3 = VP 칸 바로 위 칸 |
| Poison Snooper → Reveal turn | 3 | Reveal turn에 뽑으면 바로 공개해 이번 turn에 쓴다 |
| Rapid Mobilization → Retreat | 3 | (FAQ는 Retreat을 가리킨다) "any number"는 0 가능 |
| Recruitment Mission | 3 | 카드 전체가 이번 라운드 Reveal turn에만; 획득마다 덱 위/discard를 따로 고름 |
| Refocus | 3 | discard가 비었으면 덱을 섞는다 |
| Reverend Mother Mohiam | 3 | 상대가 버릴 카드를 고르고, 내 왼쪽부터 시계 방향 |
| Shifting Allegiances | 4 | 같은 진영을 잃고 얻을 수 있다(결과 +1); Influence가 없는 진영은 잃을 수 없다 |
| Sort Through the Chaos | 4 | 이기면 다음 라운드 시작에 Mentat을 가져간다 |
| Staged Incident | 4 | strength를 낮추는 조정으로 marker를 옮긴다 |
| Test of Humanity → discard | 4 | 위 discard |
| The Spice Must Flow | 4 | 얻은 VP는 나중에 trash해도 유지 |
| To the Victor… → Intrigue cards | 4 | 이긴 뒤 낸다 |

### 13.3 디자이너 판정 감사의 남은 몫 (원판)

[designer-rulings-audit.md](designer-rulings-audit.md)는 2026-09-08에 원판 전용 판정을 건너뛰었다(17행). 같은 정리본(elessar, 2026-06-07판)을 2026-10-22에
다시 받아, 출처가 공식 문서가 아닌 항목(BGG Forum, Discord, Message from designer 등) 가운데 원판·Ix 이름이 나오는 57개를 읽었다. 원판 몫과 처리:

| 판정 (출처) | 처리 |
| --- | --- |
| Power Play의 두 문장은 별개 효과; Agent box는 Faction 칸에 보냈을 때만(BGG Forum) | 채택(OQ-057 일괄). Subversive Advisor·OQ-022 보강(2026-10-06)과 같은 모양 |
| 두 진영 Influence를 한꺼번에 올리는 효과(Power Play, Shifting Allegiances)는 끊을 수 없는 한 효과(BGG Forum) | 채택. OQ-057 (4) "Choose Two"의 원자성과 같은 원칙 |
| Foldspace의 두 문장("Trash this card", 카드 뽑기)은 별개 효과(BGG Forum) | 채택 |
| Selective Breeding로 자기 trash 카드를 trash하고 그 카드의 효과도 얻음(BGG Forum) | 채택, 8절 |
| Kwisatz Haderach: Chairdog로 두 번 못 씀; Agent 먼저 놓고 뽑기; Influence 요구 칸은 못 넘음 | 채택, 13.1 |
| Mentat은 가져간 라운드 동안 그 플레이어의 Agent(모든 목적) | 채택, 9절 |
| Calculated Hire는 Mentat이 제 자리에 있어야 낸다 | 채택, 9절 |
| Bindu Suspension: 뽑은 뒤 "you may choose to pass your turn or play your turn normally" — 룰북 p. 13의 "then immediately end your turn"을 고친 문구(BGG Forum, Paul의 정정) | 사용자 판정 C로 채택(OQ-117). P0 감사는 이 항목을 놓쳤다(2026-10-23 다시 걸러 찾음) |
| The Voice와 Bindu Suspension·Weirding Way | 채택, 13.1 |
| CHOAM Shares는 7 Solari를 내야 낸다; Allied Armada는 Alliance와 spice 2가 있어야 낸다 | 채택(FAQ p. 2 "pay its costs"와 같다) |
| Recruitment Mission은 소급하지 않는다 | 채택 |
| Urgent Mission은 Agent가 남지 않아도 낸다(Reveal turn을 선언하기 전) | 채택. 단 되돌릴 Agent가 보드에 없으면 아래 원칙으로 막힌다 |
| Charisma는 Persuasion을 쓰지 않아도 낸다 | 채택(Persuasion을 얻는 것이 효과) |
| Rapid Mobilization은 0개를 배치하며 낼 수 있다 | 채택하되 garrison에 troop이 없으면 막힘(아래) |
| Know Their Ways는 Fremen track 맨 위에서도 낸다(불발); Water of Life는 뽑을 카드가 없어도 낸다; Dispatch an Envoy는 Reveal turn이나 Agent를 보낸 뒤에도 낸다(아이콘 없음); Infiltrate는 Agent를 놓은 뒤에도 낸다 | **2026-10-06 사용자 원칙과 부딪친다**("책략 선택지는 … 효과 중 하나라도 지금 무언가를 바꿀 수 있을 때만 낸다", worklog 2026-10-06, 효과 없는 책략 play 금지). 원칙대로 막기를 추천 — OQ-113 |
| Staged Incident로 잃은 troop으로 Harvest Cells를 낼 수 없다(비공식 설명) | P7(Immortality 조합) 몫 |
| Test of Humanity·Mohiam으로 Ilesa가 따로 둔 카드를 버리게 할 수 없다 | Ix 몫([rise-of-ix.md](rise-of-ix.md)) |

## 14. 숨은 정보 (계획 10.1절 1)

효과마다 누가 무엇을 언제 아는지. 새 뒷면 더미나 엿보기는 `known_card_seats`·관측·되돌리기 경계에 들어가야 한다(lessons 2026-09-24, 10-09).
P2·P3에서 효과마다 "그 카드가 있든 없든 상대에게 똑같이 보인다" 테스트를 둔다.

| 효과 | 아는 좌석 | 언제까지 | 비고 |
| --- | --- | --- | --- |
| Paul Atreides의 Prescience | Paul 좌석이 자기 덱 맨 위 카드 | 그 카드가 덱을 떠날 때까지, 맨 위가 바뀔 때마다 새 카드 | 덱이 비면 없음 `[DI p. 13]`. 이 좌석의 되돌리기 경계는 맨 위 카드가 바뀌는 모든 전이(뽑기, 섞기, 덱 위에 놓기) |
| Poison Snooper | 낸 좌석이 자기 덱 맨 위 | 뽑으면 손으로(숨김), trash하면 공개 | Reveal turn에 뽑으면 바로 공개 `[FAQ p. 3]` |
| Baron의 Masterstroke | Baron 좌석이 고른 진영 둘 | 공개할 때까지(게임에 한 번) | 고르는 것은 비공개 결정(지도자 고르기에 묶지 않는다 — lessons 2026-10-05). 버린 token 둘은 아무도 보지 않는다 `[DI p. 13]` |
| Secrets의 Steal Intrigue | 받은 좌석과 준 좌석이 그 카드 | Intrigue는 낼 때까지 비공개 | 무작위 선택 `[DI p. 18]`, Uprising과 같다([information-visibility.md](information-visibility.md)) |
| Reverend Mother Mohiam, Test of Humanity | 버리는 상대가 고른다 | 버린 카드는 discard에 face-up이라 공개 | 상대 좌석의 결정이 내 turn 안에 생긴다(15절) |
| Other Memory | — | discard는 공개라 뽑은 카드도 누구나 안다 | OQ-010의 "공개 경로로 손에 들어온 카드" |
| Bypass Protocol, Recruitment Mission(덱 위에 놓기) | 모두 | 덱 맨 위 카드가 공개 경로로 정해진다 | 그 카드가 뽑힐 때까지 모든 좌석이 맨 위 카드를 안다 — 관측에 새로 넣을 정보 |
| Refocus | 아무도 | — | 섞기 |
| Intrigue·Imperium·Conflict 덱 | 아무도 | — | Uprising과 같다 |

## 15. 결정 단위와 선택지의 근거 (계획 10.1절 6·7)

이미 정한 원칙을 처음부터 적용한다: 칸·카드에 인쇄된 아이콘마다 독립·순서 자유(OQ-027), 보상 줄 안의 아이콘 순서(OQ-112), 공개 선택과 숨은 뽑기는
별개 단계(OQ-106), 선택 효과는 거절 없이 turn 종료에 사라짐(OQ-095 (2)), turn은 소유자의 "턴 종료"로만 끝남(OQ-095).
"근거"는 선택을 허락하는 문장이다. 근거 없는 선택지는 만들지 않는다.

| 결정 | 누가 | 선택지 | 근거 |
| --- | --- | --- | --- |
| Mentat 칸에서 Mentat 가져오기 | Agent를 보낸 좌석 | 없음(있으면 가져온다, 의무) | "If the Mentat is here, take it" `[DI p. 18]` |
| Mentat을 Agent로 쓰기 | 가진 좌석 | 다른 Agent와 같다 | `[DI p. 18]` |
| Selective Breeding의 trash → 2장 | 보낸 좌석 | trash할 카드(손·discard·in play) 또는 하지 않음 | 화살표 비용 `[DI p. 9]`, trash 대상 `[DI p. 16]` |
| Sell Melange | 보낸 좌석 | spice 2·3·4·5 가운데 하나 | `[DI p. 18]` "2 to 5 spice", 한 번만 |
| Foldspace 칸의 Foldspace 획득 | 보낸 좌석 | 없음(의무; 더미가 비면 불발) | `[DI pp. 16-17]` |
| Secrets의 Steal Intrigue | 엔진(무작위) | 없음 | "selected at random" `[DI p. 18]` |
| Control 방어 배치 | controller | troop 1을 배치/안 함 | "may deploy" `[DI p. 10]` |
| Combat 칸 배치 | 보낸 좌석 | 이번 turn에 recruit한 troop + garrison 둘까지, 몇 개든 | "may deploy any or all … plus up to two" `[DI p. 10]`; 한 번에 다 정하지 않아도 된다(디자이너 판정, Hidden Assets Discord) |
| The Voice | 낸 좌석 | 아무 칸 하나 | "Choose any board space" `[The Voice card]` |
| Kwisatz Haderach | 낸 좌석 | 옮길 내 Agent(어디에 있든) × 갈 칸(아무 칸, 차 있어도) | `[Kwisatz Haderach card]`, `[DI p. 13]` |
| Other Memory | 낸 좌석 | 카드 1장 -OR- discard의 Bene Gesserit 카드 1장 | `[Other Memory card]` |
| Test of Humanity | 각 상대(왼쪽부터) | 손에서 1장 버리기 -OR- 배치한 troop 1 잃기, 할 수 있는 것 중 | `[DI p. 13]` |
| Mohiam | 각 상대(왼쪽부터) | 손에서 최대 2장까지 가능한 만큼 의무로 버림 | `[FAQ p. 3]`; 한 장뿐이면 한 장(OQ-118, 사용자 확정) |
| Baron의 진영 고르기 | Baron 좌석, 첫 라운드 전 | 진영 넷 중 둘(token 넷 중 둘이라 서로 다름) | `[DI p. 13]` `[FAQ p. 1]` |
| Poison Snooper | 낸 좌석 | 뽑기 -OR- trash | `[Poison Snooper card]` |
| "Choose two"(Machinations 1위, Battle for Arrakeen 2위) | 받는 좌석 | 나열된 것 가운데 둘 | OQ-114 |

## 16. 이미 정한 원칙으로 정해지는 것

원판에서 다시 묻지 않는다. 계획 10.3절의 목록에서 원판 카드에 닿는 것:

- trash된 카드의 남은 효과는 없다(OQ-022 — 디자이너가 번복 판정의 예로 Esmar Tuek를 들었다). Imperial Spy·Power Play·Foldspace의 순서도 이것으로 정해진다.
- 조건은 해결할 때 판정한다(OQ-028·OQ-057 (1)) — Gene Manipulation·Missionaria Protectiva·Mohiam·Jessica of Arrakis의 "another Bene Gesserit card in play".
- Intrigue의 인쇄 줄은 따로, 적어도 한 줄; 쓸 때 낸다(OQ-058) — Bypass Protocol·Master Tactician·Demand Respect·Plans Within Plans·Tiebreaker.
- 효과 없는 Intrigue는 낼 수 없다(2026-10-06 사용자 원칙) — 디자이너 판정과 다른 다섯 건은 OQ-113으로 확인받는다.
- 6칸 진영은 Influence를 내지 않는다(OQ-060) — Missionaria Protectiva, Demand Respect, Earl Memnon의 Connections, Duke Leto의 Prudent Diplomacy.
- "each opponent"는 다음 좌석부터 시계 방향(OQ-036; 원판 룰북도 Test of Humanity에서 같다 `[DI p. 13]`).
- 공급 부족은 같은 turn 안에 채울 수 있다(OQ-030).
- "your turn"은 자기 Agent·Reveal turn(OQ-042·OQ-063) — Count Ilban·Countess Ariana에는 쓰이지 않지만 Rise of Ix의 Yuna Moritani에 쓰인다.
- 모든 recall은 Conflict의 Agent도(OQ-068) — 원판에는 Conflict에 Agent를 보내는 효과가 없다.
- "Choose Two"는 둘을 먼저 정하고 해결한다(OQ-057 (4)).
- 같은 순위 보상은 First Player부터(OQ-002), 순위 사이는 순위대로(OQ-102).
- 카드가 **자기 효과로** 자신을 trash하면 인쇄된 나머지 이득은 그대로 받는다(OQ-022의 디자이너 후속 답글, OQ-027 확장) — Seek Allies·Foldspace·Power Play의
  "Trash this card"를 먼저 해도 draw·Influence는 남는다. 다른 수단(Selective Breeding 등)으로 먼저 trash하면 남은 효과는 없다(OQ-022).
- 비용만 내고 보상을 받을 수 없는 화살표 줄은 내지 않는다(OQ-071의 2026-09-29 사용자 원칙 일반화) — 버린 카드에 Rise of Ix의 Unload가 있어도 같다.
- Finesse(Ix)·Shifting Allegiances로 같은 진영을 잃고 다시 얻을 수 있다(`[FAQ p. 4]`의 Shifting Allegiances 판정; Uprising의 Change Allegiances도 엔진이
  6→5→6을 허용한다). 4칸에서 3으로 내려갔다 다시 4가 되면 4칸 보너스를 또 받는다(`[DI p. 7]`).
- Calculated Hire·Urgent Mission은 자기 Reveal turn에도 낼 수 있다 — Mentat이 자리를 떠나거나 Agent가 칸을 비워 보드가 바뀐다(2026-10-06 원칙의 "무언가를
  바꿀 수 있을 때", 내 해석).
- Kwisatz Haderach는 내 다른 Agent가 있는 칸에도 보낼 수 있다("ANY board space (even if occupied)" `[Kwisatz Haderach card]`; 앱도 같다).
- Countess Ariana의 −1은 Carryall·Thumper로 두 배를 한 뒤 harvest 전체에서 한 번 뺀다(덧셈이라 순서가 결과를 바꾸지 않는다; 앱도 같다).

## 17. 새 질문 (P0에서 한꺼번에)

[open-questions.md](open-questions.md)에 공식 원문·앱 처리·기존 원칙·추천과 함께 적었다. P0에서 사용자 판정을 받은 뒤 P1에 들어간다(계획 10.4절 2).

- OQ-113 — **미확정, 앱 조사 필요**: 다섯 사례 모두 막는 쪽에 잠정 동의만. 앱 구현을 확인한 뒤 사용자 재판정
- OQ-114 — **확정(2026-10-22)**: 기존 Choose Two처럼 서로 다른 두 항목을 먼저 정하고 해결(Machinations, Battle for Arrakeen, Ix의 Shuttle Fleet)
- OQ-115 — **확정(2026-10-22)**: Baron 첫 조건 달성 시 의무 공개; 기존 이번 turn 배치 조건의 문턱 4, Commander 포함·dreadnought 제외
- OQ-116 — **확정(2026-10-22)**: 상대별 이번 라운드 다음 Agent 배치 한 번까지; Agent 없는 pass는 소비하지 않음, 별도 마커/UI로 표시. 앱 지속시간 분석은 재검증
- OQ-117 — **확정(2026-10-22)**: 차례 시작 첫 행동에만 사용, 공개해야 하는 차례도 가능; 뽑은 뒤 pass 여부 선택(의무 종료 명세 정정)
- OQ-118 — **확정(2026-10-22)**: 강제 두 장 버리기는 가능한 만큼, 한 장뿐이면 한 장
- OQ-123 — **확정:** 전체 보유 The Spice Must Flow를 센다(Corner the Market; Ix의 Grand Conspiracy·Holtzman Engine도).
- OQ-124 — **확정 A:** Mentat을 제 칸에 보내면 카드 1장을 뽑고 Agent로 남는다. 다시 가져오지 않는다.
- OQ-125 — **확정(2026-10-23)**: "비용 N 이하 카드를 얻는다"(Bypass Protocol; Ix의 Boundless Ambition·Conscript, Uprising의 Impress 등도)는 Row와
  Reserve에서 고르고 Foldspace는 뺀다(지금 Uprising 엔진 그대로; 앱은 Row만)

OQ-123 ~ OQ-127은 카드별 조사(2026-10-22, agent 넷이 카드 181장·보드 칸 26을 한 장씩 본 것, 자료 `tmp/claude/d0c52597/sweep/`)에서 나왔다.
Rise of Ix의 질문(OQ-119 ~)은 [rise-of-ix.md](rise-of-ix.md) 끝에 있다.
