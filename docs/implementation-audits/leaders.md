# Leader ability audit

기준일: 2026-08-30 — 인쇄된 Leader 9종(기본 8 + CHOAM 전용 Shaddam) 구현 완료.

Leader identity와 setup은 `content/uprising/leaders.py`, 능력 규칙은 `rules/leader_abilities.py`가 소유한다. Signet Ring 일반 규칙은 [`rules/player-turns.md`](../rules/player-turns.md)와 [`rules/uprising-systems.md`](../rules/uprising-systems.md)의 `[Main pp. 6, 20]` 문장을 따른다. 능력이 구현되지 않은 Leader는 `IMPLEMENTED_ABILITY_LEADER_IDS` 밖에 있고, dispatcher가 `leader_signet_is_implemented`로 해당 좌석의 Signet Ring 배치를 제시하지 않는다(과거의 `UNIMPLEMENTED_AGENT_EFFECTS` 전면 차단을 대체).

## 검증 방법

각 Leader의 카드 이미지(카탈로그 URL은 `leaders.py`)를 2026-08-29에 직접 판독해 전사했다. DIU `data/leader_data/*.json`은 부트스트랩 참고로만 썼고, 이미지와 충돌하면 이미지를 따랐다. 아이콘 기준: 회색 정육면체 = troop, 회색 원기둥 = Spy, 위 화살표가 붙은 원기둥 = Spy recall, 주황 육각형 = Spice, 은화 = Solari, 파란 물방울 = water, 초록 카드 = personal card draw, 금색 카드 = Intrigue draw. space 유형 아이콘(파란 원 = City, 초록 오각형 = Landsraad, 네 Faction 문양)은 공식 Board Space Guide p. 1의 space별 tile artwork와 대조해 확정했다.

## 구현된 Leader

### Gurney Halleck

- **Always Smiling** — "Reveal Turn: If you have 6* or more strength in the Conflict: 1 Persuasion" (*6인전 10). 4인 게임 값 6을 `ALWAYS_SMILING_STRENGTH`로 고정했다. 전이 후 dispatcher 훅 (`grant_leader_reveal_passives`)이 자신의 Reveal frame이 열려 있는 동안 `combat_strength ≥ 6`이 처음 성립한 시점에 Persuasion 1을 부여하고 frame에 기록해 중복 부여를 막는다. 부여 뒤 strength가 6 밑으로 내려가도 회수하지 않는다(OQ-020 convention).
- **Warmaster(Signet)** — troop 1 recruit. Combat space 방문 turn에는 다른 recruit와 같은 경로로 배치 가능 수에 합산된다 `[FAQ p. 4]`. supply가 비면 recruit 가능한 만큼만 얻는다(엔진 공통 `recruit_troops` 동작).

### Lady Amber Metulli

- **Desert Scouts** — "Reveal Turn: You may retreat one of your troops." Reveal frame에서 선택 액션(`retreat_leader_troop`)으로 제시하고, 카드 텍스트가 troop 하나를 대상으로 하므로 Reveal turn당 1회로 고정한다. 마지막 unit이 빠지면 sword strength가 더 이상 세지지 않는 기존 retreat 규칙과 같은 재계산을 쓴다 `[Main pp. 12-13, 20]`.
- **Fill Coffers(Signet)** — Solari 1, 그리고 "If you have an Alliance:" Spice 1. Alliance 보유는 `alliance_faction_ids` 비어 있지 않음으로 판정한다(임의 Faction).

### Feyd-Rautha Harkonnen

- **Devious Strength** — "Reveal Turn: [Spy recall] → 검 2." arrow 비용-효과이므로 Reveal turn당 1회 `[Main p. 20]` `[FAQ p. 3]`. 배치된 Spy 하나를 supply로 되돌리고 optional sword 2를 더한다. unit이 Conflict에 없으면 세지 않는 것은 기존 Reveal sword 처리와 동일하다.
- **Personal Training(Signet)** — "Move your Feyd token one space to the right on your Training track, earning the reward on the new space." 트랙은 분기 경로다: start → {1 Solari→trash | Spy} → trash → {trash | Spy → Spice 2} → 최종(troop 1 + Spy). 구조와 보상은 카드 이미지에서 전사해 `FEYD_TRAINING_TRACK`(content)에 고정했다. token은 setup 때 맨 왼쪽, 맨 오른쪽 도달 후 그대로 남는다 `[Main p. 17]`. 오른쪽 끝에서는 이동할 새 공간이 없으므로 보상이 없다(OQ-017 convention). trash 대상은 hand, discard pile, in play `[Main p. 20]`이고, Spy 배치는 supply가 비면 recall-first `[Main pp. 11, 20]`를 따른다. 관측소 13곳 > 전체 Spy 12개라 Spy 배치가 막히는 상태는 성립하지 않는다.
- DIU의 트랙 데이터는 위쪽 trash 분기를 지나도 Spice 칸을 통과하는 평탄 구조였으나, 카드 이미지의 연결선은 위 분기가 Spice 칸을 건너뛰고 바로 최종 칸으로 이어짐을 보여 준다. 이미지를 따랐다.

### Lady Jessica / Reverend Mother Jessica (양면)

- setup은 Lady Jessica 면으로 시작한다 `[Main p. 17]`; `PlayerState.leader_face_id`가 현재 면을 공개 상태로 들고 있고, 단면 Leader는 자기 identity를 값으로 가진다.
- **Spice Agony(Signet, Lady 면)** — "1 Spice → Intrigue 1 draw, 그리고 supply의 troop 1개를 board의 Bene Gesserit 구역으로(이제 memory)." memory는 `PlayerState.memories`로 세며 troop 12개 불변식에 포함된다. supply에 troop이 없으면 recruit 계열의 기존 관행대로 그 부분만 소실되고 Intrigue draw는 이행한다. 지불은 pay/decline 직렬 선택으로 제시해 legal/apply 판정이 갈라지지 않게 했다.
- **Other Memories(Lady 면)** — Bene Gesserit board space에 Agent를 보낼 때 memory 전부를 supply로 되돌리고 장당 personal card 1장을 draw한 뒤 Reverend Mother 면으로 flip할 수 있다. memory 0개여도 사용(즉 flip)할 수 있다(OQ-018 convention). flip한 바로 그 turn에 Reverend Mother 능력을 쓸 수 있으므로 `[FAQ p. 3]`, 사용 시 같은 배치에 대한 board repeat 창을 연다.
- **Water of Life(Signet, RM 면)** — "1 Spice → water 1."
- **Reverend Mother(RM 면)** — "Once during each turn", Bene Gesserit 또는 Fremen board space에 Agent를 보내면 water 1을 지불해 "그 space에 인쇄된 효과"를 반복할 수 있다. 인쇄 효과가 한 번 해결된 뒤에만 반복을 제시하고, 반복은 `pending_board_effect`를 다시 열어 기존 board 효과 경로(espionage의 선택 포함)를 재사용한다. Faction Influence는 space 인쇄 효과가 아니라 Agent를 보낸 데 따른 Faction 규칙이므로 반복하지 않는다 `[Main p. 7]` (OQ-019). space 비용 재지불도 없다. `secrets`·`desert_tactics`는 board 효과 미구현으로 dispatcher가 숨기므로 현재 반복 대상은 espionage와 fremkit이다.

### Lady Margot Fenring

- **Loyalty** — "When you reach [Bene Gesserit] 2 Influence: Spice 2." Influence 상승 루프에서 `reach 2` VP와 같은 지점에 연결해 다단 상승의 통과, 재도달, 하강 미발동 판정을 공식 의미론과 공유한다 `[Main pp. 7, 17]`.
- **Arrakis Informant(Signet)** — "[Spy] on [파란 원]" = City board space에 연결된 관측소에 Spy 배치. City 연결 관측소는 3곳뿐이라 전부 점유된 상태가 성립할 수 있고, supply Spy가 있는데 빈 City 관측소가 없으면 배치는 소실된다(recall-first는 supply가 빌 때만 `[Main pp. 11, 20]`; supply가 비었으면 City 관측소의 자기 Spy를 recall해 자리를 열 수 있다).

### Muad'Dib

- **Unpredictable Foe** — "Reveal Turn: If you have one or more sandworms in the Conflict: [Intrigue 1 draw]." Gurney와 같은 Reveal passive 훅으로 조건이 처음 성립한 시점에 1회 지급하고 frame에 기록한다. 자신의 Reveal turn 중 sandworm이 Conflict에서 빠지는 경로는 없어(retreat 효과는 troop 대상) 부여 후 조건 상실 문제가 없다.
- **Lead the Way(Signet)** — personal card 1 draw(공통 reshuffle chance 경로).

### Princess Irulan

- **Imperial Birthright** — "When you reach [Emperor] 2 Influence: [Intrigue 1 draw]." Loyalty와 같은 지점에 연결했고, Intrigue deck이 비면 기존 `pending_intrigue_draws` 경로로 보류한다.
- **Chronicler's Insight(Signet)** — "You may choose: Acquire a card that costs 1 to your hand —OR— Trash a card from your hand. If it has a cost of 1 or more: Spice 2." 획득은 인쇄 비용이 정확히 1인 Row/Reserve 카드를 Persuasion 없이 hand로 가져오며(현재 콘텐츠에서 비용 1은 Imperium 5종), 기존 공용 획득 경로(Row 보충 `[Main p. 13]`, acquire box, Contract 완료 확인)를 재사용한다. Row 보충 불가(Imperium deck 고갈) 상태에서는 Row 획득을 제시하지 않는다. trash는 hand 한정이고 시작 카드는 인쇄 비용이 없어 Spice를 주지 않는다. "may choose"이므로 전체 거절이 가능하다.

### Staban Tuek

- **Limited Allies** — "You start the game without Diplomacy in your deck." setup의 Leader 배정 시 시작 덱에서 제거하며(9장), 이후의 셔플 chance decision은 줄어든 덱을 대상으로 한다.
- **Smuggle Spice** — "Whenever another player sends an Agent to a Maker board space you are spying on: Spice 1." 다른 플레이어의 Agent 배치 시점에 해당 Maker space에 연결된 관측소에 Staban의 Spy가 있으면 자동 지급한다. DIU 데이터는 "you are spying on" 조건을 누락했으며 카드 이미지를 따랐다.
- **Unseen Network(Signet)** — Spy 1 배치(제한 없음). "If placed on... [초록 오각형=Landsraad]: Spice 1 → Solari 3. [4개 Faction 문양]: Solari 2 → Intrigue 1 draw." 배치한 관측소가 Landsraad 또는 Faction space에 연결된 경우에만 해당 arrow 지불을 선택할 수 있고, CHOAM·Maker 관측소에는 후속이 없다. 관측소 13곳 > Spy 12개이므로 무제한 배치는 항상 가능하다.

### Shaddam Corrino IV (CHOAM 전용, 2026-08-30)

- **Sardaukar Commander** — "Set aside both Sardaukar contracts. Only you can acquire them during the game." Shaddam이 선택된 CHOAM setup은 셔플 전에 Sardaukar 2장을 `GameState.sardaukar_contract_ids`로 빼고 남은 18장을 섞는다(6인 보충 규칙의 base-CHOAM setup 지시와 일치). contract 시장 frame이 열려 있는 동안 Shaddam의 선택지에 set-aside가 추가되고, 가져가면 face-up 대신이므로 시장 보충이 없다 `[FAQ p. 3]`. 시장·bank가 모두 소진된 뒤에도 set-aside가 남아 있으면 그의 아이콘은 2 Solari와 set-aside 획득 중 하나를 선택한다(`take_exhausted_contract_solari`, OQ-021 재판정 2026-09-02); set-aside까지 소진되면 자동 2 Solari 전환으로 돌아간다.
- **Emperor of the Known Universe(Signet)** — "Units can't be deployed to the Conflict this turn." + (Solari 1 + troop 1) —OR— (Solari 3 → 임의 Faction Influence 1). 제한은 Signet Ring 배치 즉시 발효되고 `[Main p. 17]` 그 turn에만 적용된다 `[FAQ p. 3]`. frame context의 `units_deploy_blocked`가 Combat 배치(pending 자체를 열지 않음), Maker sandworm 소환, Plot Intrigue의 배치 option(Detonation)을 막고, Intrigue SummonSandworm은 Shield Wall 규칙과 같은 무효 경로로 처리한다. 보상 선택은 의무이며 Solari 3 미만이면 troop 옵션만 제시된다. recruit된 troop은 같은 제한 때문에 그 turn에 배치할 수 없다.

## 남은 Leader

없음 — 인쇄된 Uprising Leader 9종(기본 8 + CHOAM 전용 Shaddam)의 능력과 Signet Ring이 모두 구현됐다. Sardaukar II contract의 Agent recall 보상은 [contracts audit](contracts.md)의 2026-08-30 manifest 수정과 함께 들어갔다.

## 회귀 테스트

`tests/unit/rules/test_leader_abilities.py`가 signet 자동 해결, Feyd 트랙 분기·단계·최종 칸, Devious/Desert Scouts의 Reveal 액션과 1회 제한, Always Smiling·Unpredictable Foe 문턱과 중복 방지, Jessica 지불·flip·repeat 경로, reach-2 보너스(통과·재도달·타 Faction 미발동), Margot·Staban의 Spy 배치 제한과 후속 지불, Chronicler's Insight의 획득·trash·거절, Limited Allies setup, Smuggle Spice 조건, setup 면 배정을 고정한다. 기본 4종과 신규 4종 각각의 random 4인 완주 soak에서 모든 신규 이벤트가 발동함을 확인했고 replay 검증을 통과했다.
