# Arrakeen Scouts implementation audit

기준일: 2026-09-28 — 슬라이스 1(출처·명세·OQ·콘텐츠 카탈로그), 슬라이스 2(옵션 골격), 슬라이스 3a(일정·라운드 흐름·자동 이벤트), 슬라이스 3b(규칙 변경 넷), 슬라이스 4(소위원회), 슬라이스 5(선택형 이벤트·판매), 슬라이스 6a(임무 뼈대), 슬라이스 6b(나머지 임무 수령), 슬라이스 7(비밀 선택), 슬라이스 8(경매).

규범 근거는 [`rules/arrakeen-scouts.md`](../rules/arrakeen-scouts.md)이고, 콘텐츠 정의는 `content/arrakeen_scouts/`(소위원회 `subcommittees.py`, 임무 `missions.py`, 이벤트 `events.py`, 경매·판매 `auctions.py`)가 소유한다. 모든 동작은 `RulesetConfig(arrakeen_scouts=True)`에서만 켜진다(슬라이스 2부터). 설계와 슬라이스 순서는 [`arrakeen-scouts-design.md`](../arrakeen-scouts-design.md)다.

## 검증 방법

원자료는 저장소 밖에 있다(에셋 체크아웃의 git 무시 폴더 `reference/dwgr-arrakeen-scouts/`, [`rules/sources.md`](../rules/sources.md)의 "Arrakeen Scouts" 절).

1. **추출과 코드 분석(2026-09-27).** `scripts/dwgr/extract.py`로 정의 데이터·일정 풀·문구·아이콘 트리를 꺼냈다. 일정 생성과 경매 판정은 앱의 네이티브 코드를 디스어셈블해 읽었다. 분석 에이전트 4개가 서로 독립으로 같은 결론을 냈고, 반박 검증이 11개 주장 중 10개를 확인하고 1개의 세부를 보정했다. 항목 해석(Uprising 63개)은 반박 검증에서 규칙 의미가 모두 확인됐다(로컬 `analysis/verification/`).
2. **카탈로그 전사(2026-09-28).** 위 해석과 `data/beats_bundle.txt`(정의·영한 문구·아이콘)를 읽고 typed 레코드로 옮겼다. 효과는 effect DSL 기본 요소로, DSL에 없는 것만 Scouts 전용 요소(`LoseFactionInfluence`, `LoseGarrisonTroops`, `PaySpecimens`, `RecallOtherAgent`, `RecruitToConflict`, `AcquireReserveCardToHand`, `GainLowestInfluence`, `GainSpiceWithHelixBonus`)로 적었다.
3. **기계 대조.** `tests/unit/content/test_arrakeen_scouts_extraction.py`가 모든 레코드의 앱 asset 이름, 풀 소속(두 풀 모두 양방향), 계열·변형(beatId·beatSubId), 라운드 창, CHOAM 플래그, 가중치(`weight_tickets` = baseWeight × subWeight × 10), 등급·임무 종류, 비밀 선택의 기한, 경매의 봉인 여부·상한·통화·이기는 자리 수를 추출과 비교한다. 추출이 없는 기기에서는 skip한다. 추출 없이 도는 `test_arrakeen_scouts_content.py`는 풀 크기, id 고유성, 4라운드 추첨표 170/160, 계열 구성을 고정한다.
4. **독립 대조(2026-09-28).** 전사와 명세를 쓰지 않은 검증 에이전트 넷(소위원회·판매, 임무, 이벤트, 경매·일정)이 원자료와 코드·명세를 항목마다 비교했다. 결과는 아래 "독립 대조 결과"에 적는다.

## 해석이 아이콘에만 기대는 항목

- **Shadow Warfare**: 앱에 문구가 없다. 화살표 왼쪽 Spy 회수를 비용, 오른쪽 troop·spice를 보상으로 읽었고, "이 판매로 recruit한 troop은 곧바로 Conflict에"는 판매 공통 문구에서 왔다. 로컬 반박 검증도 같은 해석이다.
- **Imperium Connections, Secrets for Sale, Unravel the Future**: 선택지가 아이콘만이다(비용 숫자 → 보상 아이콘). 앱 영어 요약 문구와 일치한다.

## 항목 표

"엔진" 열은 구현 상태다(카탈로그 = 레코드만 있고 엔진 동작 없음). 슬라이스 3a부터 모든 항목은 일정대로 뽑혀 공개되고, 아직 동작이 없는 항목은 `scouts_item_unimplemented` 이벤트를 남긴다. 슬라이스가 동작을 구현하면 그 슬라이스와 테스트를 적는다.

### 소위원회 (슬라이스 4)

| id | 앱 정의 | 풀 | 등급 | CHOAM | 엔진 |
| --- | --- | --- | --- | --- | --- |
| `appropriations` | `Def_Subcommittee_E_Appropriations` 1.0 | 둘 다 | 0 |  | 4: 가입 + `scouts_effect` |
| `intelligence` | `Def_Subcommittee_E_Intelligence` 8.0 | 둘 다 | 0 |  | 4: 가입 + `scouts_effect` |
| `readiness` | `Def_Subcommittee_E_Readiness` 2.0 | 둘 다 | 0 |  | 4: 가입 + `scouts_effect` |
| `choam_coordination` | `Def_Subcommittee_E_CHOAMCoordination` 13.0 | 둘 다 | 0 | 전용 | 4: 가입 + `scouts_effect` |
| `growth_project` | `Def_Subcommittee_E_GrowthProject` 10.0 | +Immortality | 0 |  | 4: 가입 + `scouts_effect` |
| `oversight` | `Def_Subcommittee_M_Oversight` 3.0 | 둘 다 | 1 |  | 4: 가입 + `scouts_effect` |
| `investigations` | `Def_Subcommittee_M_Investigations` 4.0 | 둘 다 | 1 |  | 4: 가입 + `scouts_effect` |
| `forecasting` | `Def_Subcommittee_M_Forecasting` 14.0 | 둘 다 | 1 |  | 4: 가입 + `scouts_effect` |
| `choam_management` | `Def_Subcommittee_M_CHOAMManagement` 15.0 | 둘 다 | 1 | 전용 | 4: 가입 + `scouts_effect` |
| `analytics` | `Def_Subcommittee_M_Analytics` 11.0 | +Immortality | 1 |  | 4: 가입 + `scouts_effect` |
| `relations` | `Def_Subcommittee_L_Relations` 5.0 | 둘 다 | 2 |  | 4: 가입 + `scouts_effect` |
| `contingencies` | `Def_Subcommittee_L_Contingencies` 16.0 | 둘 다 | 2 |  | 4: 가입 + `scouts_effect` |
| `leverage` | `Def_Subcommittee_L_Leverage` 17.0 | 둘 다 | 2 |  | 4: 가입 + `scouts_effect` |
| `tleilaxu_relations` | `Def_Subcommittee_L_TleilaxuRelations` 12.0 | +Immortality | 2 |  | 4: 가입 + `scouts_effect` |

### 임무 (슬라이스 6)

| id | 앱 정의 | 풀 | 종류 | 라운드 | CHOAM | 엔진 |
| --- | --- | --- | --- | --- | --- | --- |
| `security_detail` | `Def_Mission_SecurityDetail` 13.0 | 둘 다 | 0 | 2~3 |  | 6a: 참여·방문 → Conflict |
| `imperial_reserve` | `Def_Mission_ImperialReserve` 14.0 | 둘 다 | 0 | 2~3 |  | 6a: 물품·방문(둘 중 하나) |
| `desert_riding` | `Def_Mission_DesertRiding` 15.0 | 둘 다 | 0 | 2~3 |  | 6a·6b: 토큰, Hagga Basin·Sietch Tabr |
| `urban_surveillance` | `Def_Mission_ValuedInformants_UrbanSurveillance` 15.0 | 둘 다 | 0 | 2~3 |  | 6a·6b: 물품, Spy 배치 때 수령 |
| `planetary_exploration` | `Def_Mission_ValuedInformants_PlanetaryExploration` 15.1 | 둘 다 | 0 | 2~3 |  | 6a·6b: 물품, Spy 배치 때 수령 |
| `choam_research` | `Def_Mission_CHOAMResearch` 16.0 | 둘 다 | 0 | 2~3 | 전용 | 6a: 뒷면 Contract 2장, 방문마다 1장 |
| `choam_escort` | `Def_Mission_CHOAMEscort` 17.0 | 둘 다 | 0 | 2~3 | 전용 | 6a·6b: 참여, 완료 때 수령 |
| `sponsored_research` | `Def_Mission_SponsoredResearch` 9.0 | +Immortality | 0 | 2~2 |  | 6a·6b: 물품, 첫 genetic marker 도달 때 수령 |
| `back_room_deal` | `Def_Mission_BackRoomDeal` 10.0 | +Immortality | 0 | 2~3 |  | 6a·6b: 물품, Reclaimed Forces 획득 때 수령 |
| `prison_planet` | `Def_Mission_EliteSardaukar_PrisonPlanet` 18.0 | Uprising | 1 | 2~3 |  | 6a: 참여·방문·세 번째 지배 |
| `emperors_schemes` | `Def_Mission_EliteSardaukar_EmperorsSchemes` 18.1 | 둘 다 | 1 | 2~3 |  | 6a: 뒷면 Intrigue 2장, 방문마다 1장 |
| `fedaykin_assistance` | `Def_Mission_FedaykinAssistance` 19.0 | 둘 다 | 1 | 3~3 |  | 6a: 참여·방문 → recruit |
| `weirding_warfare` | `Def_Mission_WeirdingWarfare` 20.0 | 둘 다 | 1 | 2~3 |  | 6a: 참여·방문 → Conflict |
| `send_for_aid` | `Def_Mission_SendForAid` 21.0 | 둘 다 | 1 | 2~3 |  | 6a: 참여·방문 → Conflict + 물 |
| `coordinate_with_the_emperor` | `Def_Mission_CoordinateWithTheEmporer2` 18.0 | +Immortality | 1 | 3~3 |  | 6a: 참여·방문 → garrison + Solari |
| `tleilaxu_offering` | `Def_Mission_TleilaxuOffering` 11.0 | +Immortality | 1 | 2~2 |  | 6a·6b: 참여, 세 번째 칸 도달 때 specimen |

### 이벤트 (슬라이스 3·5·7)

| id | 앱 정의 | 풀 | 종류 | 라운드 | 추첨표 | CHOAM | 엔진 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `private_stock` | `Def_Event_SpiceGain_PrivateStock` 13.0 | 둘 다 | choice | 4~7 | 5 |  | 5: `scouts_choice` |
| `market_research` | `Def_Event_SpiceGain_MarketResearch` 13.1 | 둘 다 | choice | 4~7 | 5 |  | 5: `scouts_choice` |
| `smoke_and_mirrors` | `Def_Event_IntrigueBonus_SmokeAndMirrors` 14.0 | 둘 다 | choice | 4~7 | 5 |  | 5: `scouts_choice` |
| `rotating_doors` | `Def_Event_IntrigueBonus_RotatingDoors2` 14.1 | 둘 다 | choice | 4~7 | 5 |  | 5: `scouts_choice` |
| `moment_of_revelation` | `Def_Event_MomentOfRevelation` 15.0 | 둘 다 | choice | 4~7 | 10 |  | 5: `scouts_choice` |
| `water_discipline` | `Def_Event_WaterDiscipline` 16.0 | 둘 다 | choice | 4~7 | 10 |  | 5: `scouts_choice` |
| `royal_delegation` | `Def_Event_InfluenceGain_RoyalDelegation` 17.0 | 둘 다 | choice | 4~7 | 6 |  | 5: `scouts_choice` |
| `guild_negotiation` | `Def_Event_InfluenceGain_Negotiation2` 17.1 | 둘 다 | choice | 4~7 | 6 |  | 5: `scouts_choice` |
| `covert_assistance` | `Def_Event_InfluenceGain_CovertAssistance` 17.2 | 둘 다 | choice | 4~7 | 6 |  | 5: `scouts_choice` |
| `gift_of_water` | `Def_Event_InfluenceGain_GiftOfWater` 17.3 | 둘 다 | choice | 4~7 | 6 |  | 5: `scouts_choice` |
| `share_intelligence` | `Def_Event_InfluenceGain_ShareIntelligence` 17.4 | 둘 다 | choice | 4~7 | 6 |  | 5: `scouts_choice` |
| `political_equilibrium` | `Def_Event_InfluenceReduction_Equilibrium2` 18.0 | 둘 다 | automatic | 4~7 | 6 |  | 5: 좌석마다 `LoseHighestInfluence` |
| `crackdown` | `Def_Event_InfluenceReduction_Crackdown` 18.1 | 둘 다 | choice | 4~7 | 6 |  | 5: `scouts_choice` |
| `water_for_spice_smugglers` | `Def_Event_InfluenceReduction_Smugglers2` 18.2 | 둘 다 | choice | 4~7 | 6 |  | 5: `scouts_choice` |
| `bene_gesserit_treachery` | `Def_Event_InfluenceReduction_Treachery2` 18.3 | 둘 다 | choice | 4~7 | 6 |  | 5: `scouts_choice` |
| `funeral_rites` | `Def_Event_InfluenceReduction_FuneralRites` 18.4 | 둘 다 | choice | 4~7 | 6 |  | 5: `scouts_choice` |
| `covert_operation` | `Def_Event_CovertOperation2` 19.0 | 둘 다 | secret | 4~7 | 10 | 없을 때 전용 | 7: 비밀 선택·공개·해결 |
| `covert_operation_choam` | `Def_Event_CovertOperation3` 19.1 | 둘 다 | secret | 4~7 | 10 | 전용 | 7: 비밀 선택·공개·해결 |
| `mating_season` | `Def_Event_MatingSeason` 20.0 | 둘 다 | automatic | 4~7 | 10 |  | 3a: Maker 칸마다 +1 |
| `unlikely_allies` | `Def_Event_UnlikelyAllies` 21.0 | 둘 다 | round_modifier | 4~7 | 10 |  | 3b: Influence 요구 무시 (`agent_turn`) |
| `clear_the_market` | `Def_Event_ClearTheMarket` 22.0 | 둘 다 | automatic | 4~7 | 10 | 없을 때 전용 | 3a: Row 교체, 치운 카드는 `imperium_removed` |
| `clear_the_market_choam` | `Def_Event_ClearTheMarket2` 22.1 | 둘 다 | automatic | 4~7 | 10 | 전용 | 3a: Row 교체 + Contract 되섞기 chance |
| `market_opening` | `Def_Event_MarketOpening` 23.0 | 둘 다 | round_modifier | 4~7 | 10 |  | 3b: `reserve_cost` 할인, 첫 획득에 소진 |
| `eyes_on_arrakis` | `Def_Event_EyesOnArrakis` 24.0 | 둘 다 | round_modifier | 4~7 | 10 |  | 3b: Faction 칸이 Combat 칸 (`space_is_combat`) |
| `friends_everywhere` | `Def_Event_FriendsEverywhere` 25.0 | 둘 다 | round_modifier | 5~7 | 10 |  | 3b: `choose_four_bonus` 선택 frame |
| `rebuild_infrastructure` | `Def_Event_RebuildInfrastructure` 26.0 | 둘 다 | shared | 7~7 | 10 |  | 5: 두 좌석 분담 (OQ-084) |
| `choam_bargain` | `Def_Event_CHOAMBargain` 27.0 | 둘 다 | choice | 4~7 | 10 | 전용 | 5: `scouts_choice` |
| `ingratiate` | `Def_Event_Ingratiate` 8.0 | +Immortality | choice | 4~7 | 10 |  | 5: `scouts_choice` |
| `betrayal` | `Def_Event_Betrayal` 9.0 | +Immortality | choice | 4~7 | 10 |  | 5: `scouts_choice` |
| `new_innovations` | `Def_Event_NewInnovations` 10.0 | +Immortality | choice | 4~7 | 10 |  | 5: `scouts_choice` |
| `termination_request` | `Def_Event_TerminationRequest` 11.0 | +Immortality | choice | 4~7 | 10 |  | 5: `scouts_choice` |
| `offworld_operation` | `Def_Event_OffworldOperation` 12.0 | +Immortality | secret | 4~7 | 10 |  | 7: 비밀 선택·공개·해결 |

### 경매 (슬라이스 8)

| id | 앱 정의 | 풀 | 방식 | 자리 | 통화·상한 | 이기는 자리 | CHOAM | 엔진 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `highest_bidder_mid` | `Def_Auction_HighestBidder_Mid` 1.0 | 둘 다 | sealed | mid | solari 99 | 1 |  | 8: 봉인 입찰 |
| `highest_bidder_late` | `Def_Auction_HighestBidder_Late` 1.1 | 둘 다 | sealed | late | solari 99 | 2 |  | 8: 봉인 입찰 |
| `mercenaries` | `Def_Auction_Mercenaries` 3.0 | 둘 다 | mercenaries | either | spice 3 | 1 |  | 8: 봉인 입찰·전원 지불·후퇴 |
| `competitive_study_mid` | `Def_Auction_CompetitiveStudy_Mid` 4.0 | +Immortality | sealed | mid | solari 99 | 1 |  | 8: 봉인 입찰 |
| `competitive_study_late` | `Def_Auction_CompetitiveStudy_Late` 4.1 | +Immortality | sealed | late | solari 99 | 2 |  | 8: 봉인 입찰 |
| `spies_for_hire_mid` | `Def_Auction_SpiesForHire_Mid` 5.0 | 둘 다 | sealed | mid | solari 99 | 1 |  | 8: 봉인 입찰 |
| `spies_for_hire_late` | `Def_Auction_SpiesForHire_Late` 5.1 | 둘 다 | sealed | late | solari 99 | 2 |  | 8: 봉인 입찰 |
| `critical_moment_mid` | `Def_Auction_CriticalMoment_Mid` 6.0 | 둘 다 | open_cards | mid | spice 99 | 1 |  | 8: 공개 경매 |
| `critical_moment_late` | `Def_Auction_CriticalMoment_Late` 6.1 | 둘 다 | open_cards | late | spice 99 | 2 |  | 8: 공개 경매 |
| `choam_negotiations_mid` | `Def_Auction_CHOAMNegotiations_Mid` 7.0 | 둘 다 | sealed | mid | solari 99 | 1 | 전용 | 8: 봉인 입찰 |
| `choam_negotiations_late` | `Def_Auction_CHOAMNegotiations_Late` 7.1 | 둘 다 | sealed | late | solari 99 | 2 | 전용 | 8: 봉인 입찰 |

### 판매 (슬라이스 5)

| id | 앱 정의 | 풀 | 엔진 |
| --- | --- | --- | --- |
| `unravel_the_future` | `Def_Sale_Future` 2.0 | 둘 다 | 5: `scouts_choice` |
| `imperium_connections` | `Def_Sale_ImperiumConnections` 3.0 | 둘 다 | 5: `scouts_choice` |
| `secrets_for_sale` | `Def_Sale_SecretsForSale` 4.0 | 둘 다 | 5: `scouts_choice` |
| `shadow_warfare` | `Def_Sale_ShadowWarfare` 5.0 | 둘 다 | 5: `scouts_choice` |

## 독립 대조 결과

2026-09-28, 검증 에이전트 넷(읽기 전용). 각자 `data/beats_bundle.txt`의 문구·아이콘 트리, 정의 JSON, `schedules.json`, 로컬 분석(`analysis/findings/`)을 코드와 명세에 항목마다 대었다.

- **데이터: 불일치 0건.** 77개 레코드 전부(소위원회 14, 임무 16, 이벤트 32, 경매 11, 판매 4)의 비용·보상·수량·Faction·패스 여부·칸·세워 둔 troop의 수와 출처·물품·라운드·종류·CHOAM 플래그·가중치·풀·비밀 선택의 기한과 묶음·경매 방식과 자리가 원자료와 맞았다. 공식 한국어 이름도 모두 맞았다.
- **일정과 경매 판정: 불일치 0건.** 소위원회 4인 추첨, 임무 배치와 마지막 종류 규칙, 이벤트 가중 추첨과 계열 제거, 중간·후반 경매 후보 집합, 판매, Scouts 단계 안의 순서, 봉인 입찰 순위(공동 순위, 0은 이기지 못함, 1위 동점이면 2위 없음, 진 좌석은 지불하지 않음, Mercenaries 전원 지불)가 앱 코드 분석과 맞았다. 풀 도우미의 CHOAM 필터도 앱의 필터와 같다.
- **고친 문서 표현**(동작은 그대로):
  - Send for Aid: 앱은 방문 때 그 troop을 "recruit해 곧바로 배치"한다고 한다. 명세와 OQ-077 (d)를 앱의 말대로 고쳤다(garrison을 이미 떠난 troop이라 `[FAQ p. 4]`에 걸리지 않는다).
  - CHOAM Escort의 참여는 "may"다. 명세와 OQ-088을 선택으로 고쳤다(패스 가능).
  - 명세 3절의 끊긴 절 참조(7.3절 → 7.2절·7절), 2.2절 후반 경매 후보 문장, 8.2절 Mercenaries 후퇴(전부 또는 일부), 8.3절 Critical Moment의 최소 1과 2위의 선택 구매(OQ-087), 2.3절과 `events.py`의 추첨표 설명(5장은 스파이스 획득·책략 보너스 계열만), 6절의 Covert Operation·Clear the Market 계열 표시(CHOAM 변형), 7.2절 해결 순서를 OQ-085와 맞춤, 임무 칸의 공식 한국어 이름에 계열 접두어.
  - 코드 설명: `Mission.goods`(Valued Informants는 관측소마다, Imperial Reserve는 둘 중 하나), `ScoutsAuction`(Critical Moment 2위는 살 수도 있다), `MAX_AUCTION_BID`(공개 경매에는 앱이 상한을 쓰지 않는다).
- **더한 기계 대조.** 비밀 선택의 묶음 여부를 앱의 `CondenseEventCompletions`가 묶는 선택 id(5, 6, 7, 8, 10)와 대조한다. 패스 여부는 아이콘 트리에만 있어 기계 대조가 없고, 위 독립 대조로 확인했다.
