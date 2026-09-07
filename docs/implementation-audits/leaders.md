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

## Bloodlines Leader (2026-09-07, `bloodlines` 옵션 전용)

카드면(`assets/cards/en/bloodlines/leader/*.webp`)을 직접 판독해 전사했다. 아이콘은 `assets/icons`와 대조했다(Emperor=회색 뿔 투구, Fremen=파란 원 sietch, Landsraad=초록 오각형, City=파란 원, Spice Trade=노란 삼각형, Spy=눈, Intrigue=노란 카드, draw=초록 카드, trash=X 카드). 룰북은 설정과 clarification만 더한다 `[Bloodlines pp. 3, 12]`. 새 상태는 관측 v8의 좌석 scalar `tactics_track_space`·`agent_in_conflict`다.

### Chani

- **Tactician** — "Whenever you retreat or lose any number of troops from the Conflict, advance your Tactics token that many spaces, earning rewards as you reach them. Reset the token after reaching the end of the track." 11칸 track: 4인은 3번째 칸(index 2)에서 시작, 6번째 칸 spice 1, 마지막 칸 water 1 뒤 시작 칸으로 reset; 끝을 넘기는 초과분은 버린다 `[Bloodlines p. 12]`. `rules/tactics.py`가 leaf `units.retreat_units` 안에서 호출되므로 모든 retreat 경로(Reveal·Intrigue·Signet)와 Conflict에서의 유닛 손실(`unit_loss`, Holy War)이 자동으로 센다. Commander는 troop으로 센다 `[Bloodlines p. 4]`. Combat 종료 후 garrison으로 돌아가는 유닛은 retreat가 아니다.
- **Fedaykin Maneuver(Signet)** — "Retreat any number of your troops. —OR— [Fremen] 2 Influence: water → 2 troops." `retreat_leader_troops(count[, commanders])`(0은 `decline_leader_signet_payment`), `pay_leader_signet_water`(Fremen Influence 2+, water 1+). Agent turn 중의 retreat는 `combat_deployment.reconcile_deployment_after_retreat`로 이번 turn의 배치 카운터를 함께 줄인다(회수 창 언더플로 방지; Intrigue의 Agent turn retreat도 같은 경로).

### Count Hasimir Fenring

- **Assassin** — "Whenever you trash a card: 1 Solari." `card_trash.trash_personal_card`에서 지급; Intrigue trash는 제외 `[Bloodlines p. 12]`.
- **Corrino Liaison(Signet)** — "You may trash a card in your play area. —OR— Spy on [Emperor]." play area의 어떤 카드든(Signet Ring 자신 포함) `trash_leader_card`, 또는 Emperor observation post에 `place_leader_spy`(supply가 비면 회수 먼저), 또는 거절.

### Duncan Idaho

- **Ginaz Swordmaster** — "The Swordmaster board space costs you 2 less." `agent_turn._effective_costs`가 좌석별로 8→6(다른 좌석이 먼저 샀을 때 6→4)을 적용한다.
- **Into the Fray(Signet)** — "You may take the Agent you sent this turn and deploy it to the Conflict as a 2 strength unit that can't be retreated. If you have your Swordmaster, it has 3 strength instead." `deploy_leader_agent`: 좌석 `agent_in_conflict=1`, 그 Agent는 `agent_locations`에서 빠져 공간이 다시 비고(OQ-037), `units_strength`가 2/3을 더하며, retreat·손실 대상이 아니다. Combat 정리 때 `agents_available`로 돌아간다.

### Esmar Tuek

- **Tuek's Sietch(능력)** — "Whenever you send an Agent to Tuek's Sietch: 1 Solari. Whenever an opponent sends an Agent there: 1 Intrigue." `agent_turn.apply_agent_action`의 배치 hook. 보드 타일 Tuek's Sietch(Dire Wolf design diary 이미지, `assets/cards/en/bloodlines/location/Tuek's Sietch.png`)는 Spice Trade 아이콘·Combat·Maker·비용 없음·"1 spice OR draw 1 card". `BoardSpace.required_leader_id="esmar_tuek"`로 Esmar가 있을 때만 배치 대상이며, `maker_bonus_spice` 원장에 4번째 항목으로 들어가 Makers 단계에 spice가 쌓인다 `[Bloodlines p. 12]`. 방문 행은 `take_tuek_sietch_spice`/`take_tuek_sietch_card`(bonus spice는 어느 쪽이든 가져간다). 인쇄된 sandworm 선택지가 없으므로 Maker Hooks 소환은 없다. UI 박스는 Imperial Basin 아래 빈 사막에 그린다.
- **Smuggle Spice(Signet)** — "Place 1 bonus spice on Tuek's Sietch. —OR— Take 1 bonus spice from a Maker board space." `place_leader_bonus_spice` / `take_leader_bonus_spice(space_id)`(bonus가 있는 Maker space만) / 거절. Signet을 먼저 해결하고 같은 turn의 방문 행으로 가져가는 순서는 자유 순서 그룹이 그대로 허용한다 `[Bloodlines p. 12]`.

### Gaius Helen Mohiam

- **Clandestine** — "Each card you play has the Spy icon. Whenever you could recall a Spy to Gather Intelligence, you must." `card_can_access_space`가 그녀의 모든 카드에 Spy 아이콘 접근을 주고, `spies.legal_gather_intelligence_actions`는 회수 가능한 Spy가 있으면 거절을 빼고 제시한다. codec은 Bloodlines 카탈로그에서 모든 카드×모든 공간의 배치 템플릿을 갖는다.
- **Listeners(Signet)** — "Spy on [Landsraad] —OR— 1 spice → Spy." Landsraad post에 `place_leader_spy`, 또는 `pay_leader_signet_spice`(frame context `listeners_paid`) 뒤 아무 post에 배치, 또는 거절.

### Piter De Vries

- **Twisted Genius** — "Game Start: Shuffle the Twisted Intrigue deck and place it face down near you. Round Start: Draw a Twisted Intrigue card. (These count as Intrigue cards and can be stolen.)" setup의 chance `setup:twisted_intrigue`가 12장을 섞어 `GameState.twisted_deck_stock`에 두고, 고정 setup은 즉시·draft는 pick 뒤 `assign_twisted_deck`으로 Piter 좌석의 `twisted_deck`(순서 비공개, 장수 공개 — 관측 좌석 scalar `twisted_deck_size`)에 옮긴다. `phases.begin_round`가 매 round 1장을 `intrigue_cards`로 뽑는다. Twisted 카드는 `IntrigueCardEntry.twisted`로 표시된 Intrigue identity(관측 우주 57→69종)이며 공용 Intrigue 덱에는 절대 들어가지 않고, 손에 들어온 뒤에는 Secrets의 절도·Insidious의 증여·trash의 대상이 된다.
- **Harkonnen Advisor(Signet)** — "1 troop. You can't deploy this troop to the Conflict this turn." Warmaster에서 배치만 뺀 것(사용자 판정, OQ-038): troop을 garrison에 recruit하되 `troops_recruited`에 세지 않고, frame context `undeployable_troops`로 이번 turn 배치 가능한 garrison troop 수를 1 줄인다(`legal_combat_deployments`와 Intrigue `DeployFromGarrison` 모두). 같은 turn에 garrison에서 troop을 잃으면 `release_undeployable_troops`가 그 수를 되돌려 배치 가능 수를 정상화한다.
- **Twisted Intrigue 12장**(카드면 전사, `content/uprising/intrigue.py`의 `_twisted`): Ambitious(Plot: troop 3 잃기 → 상대가 더 앞선 진영의 Influence 1, `GainInfluence(where_opponent_leads=True)`), Calculating(Plot: Conflict의 유닛 종류당 Solari 1 — troop·sandworm·Commander·Into the Fray의 Agent, `GainSolariPerUnitType`), Controlled(Plot: 덱 맨 위 카드를 보고 되돌리기/discard/Solari 1로 draw, `PeekTopCard`; Combat: 검 1), Devious(Plot: hand 카드 의무 trash `TrashPersonalCard(hand_only, mandatory)` OR garrison에서 최대 2 배치), Discerning(Plot: discard → draw OR Alliance 보유 시 draw, `HasAlliance`), Insidious(Plot: 상대에게 hand의 Intrigue 1장 증여 → spice 1, 일반 Intrigue면 +1, `GiveIntrigueToOpponent`; 증여 카드 identity는 두 좌석에게만 보이는 이벤트), Resourceful(Plot: 이번 turn play하는 카드에 Landsraad·City·Spice Trade 아이콘, `GrantAgentIconsThisTurn`), Sadistic(Plot: troop 1 잃기 → draw), Shrewd(Combat: Conflict의 troop 1 잃기 → spice 1), Sinister(Combat: troop 2 잃기 → Intrigue 1 + Solari 1), Unnatural(Plot: hand의 Intrigue 1장 trash → Intrigue draw, 일반 Intrigue였으면 troop 1, `TrashIntrigueCard` — 4절의 "Trash an Intrigue card" 아이콘 구현), Withdrawn(Plot, 턴 시작에만: 턴 넘기기, `PassTurn` + `IntrigueOption.turn_start_only`). "lose troops" 비용 `LoseTroops(count, from_conflict)`는 잃는 플레이어가 zone과 종류(Commander 포함)를 고른다(OQ-038); Conflict에서 잃으면 retreat와 같이 strength를 빼고 배치 카운터를 맞춘다.

### Steersman Y'rkoon

- **Strange Form** — "You start the game with no water and without Signet Ring in your deck." `LeaderDefinition.starting_water=0`, `removed_starting_card_ids=("signet_ring",)`.
- **Hungry for Spice** — "Whenever you gain 3 or more spice in a single turn: draw a card." 전이 후 hook `grant_hungry_for_spice`가 좌석의 `spice_gained_this_turn`(turn 시작 snapshot 기준, 다른 카드와 같은 정의)이 3 이상이면 turn당 1회 draw한다(`hungry_for_spice_granted_turn`, TURN frame이 열릴 때 초기화). reshuffle chance가 열려 있는 동안은 미뤄 두 reshuffle이 겹치지 않게 한다.
- **Plot Course(Signet 대신)** — "Game Start: Shuffle the Navigation cards and draw a hand of five. Choose four to place face down above, in order. Return all others to the box. Whenever you reach 2 Influence with a Faction, play the next Navigation card above (starting from the left)." setup chance `setup:navigation`이 10장을 섞어 `navigation_stock`에 두고, Y'rkoon 좌석이 정해지면(고정 setup 즉시, draft는 pick 뒤) 위 5장을 hand로 주고 `navigation_setup` frame(`place_navigation_card` ×4)을 열어 게임을 SETUP에 멈춘다 — 엔진 `reset`은 이 상태를 그대로 돌려주고 네 번째 선택 뒤 Round Start로 간다. slot은 소유자만 보는 비공개(관측 `private_navigation_slots`), box는 비공개, play된 카드는 공개. trigger는 `influence.gain_faction_influence`에서 Influence가 2에 닿을 때마다 `pending_navigation_plays`에 쌓이고 엔진 자동 전이 `begin_navigation_play`가 `navigation_choice` frame을 연다(OQ-012 재검토·OQ-039). 카드는 Intrigue 스키마의 `IntrigueCardEntry(navigation=True)`로 전사되어 `play_navigation(option)` 뒤 Intrigue 선택 frame으로 해결되며, `finish_intrigue_play`가 Navigation 카드를 discard 대신 `navigation_played`로 보낸다.
- **Navigation 10장**(카드면 전사): 1(spice 1 OR Solari 2 → trigger 진영이 아닌, Influence 2+인 진영에 Influence 1, `GainInfluence(different_from_trigger, minimum_own=2)`), 2(Spy 배치 OR Spy 회수 → Intrigue 1 + spice 2), 3(Solari 2; slot 4면 이후 모든 Reveal에 Persuasion 1, `PermanentRevealPersuasion` → 좌석 `reveal_persuasion_bonus`), 4(spice 1 OR slot 1이면 water → The Spice Must Flow 획득, `AcquireReserveCard`), 5(카드 trash(선택); 비용 1 이상이면 spice 2, `TrashPersonalCard(bonus_spice=2, bonus_minimum_cost=1)`), 6(troop 1 OR Solari 3 → troop 3), 7(spice 1; Alliance 보유 시 Intrigue 1), 8(water; Spacing Guild로 trigger됐으면 spice 1, `TriggeredByFaction`), 9(draw 1 OR spice 5 → VP 1), 10(Influence 1 잃기 → Influence 1 획득). 조건 `InNavigationSlot`·`TriggeredByFaction`은 play 중 좌석의 `navigation_active_slot`·`navigation_trigger_faction`으로 판정한다. 2인 게임의 "Spy card 제외"(`[Bloodlines p. 3]`)는 4인 구현에 해당 없음.

### Liet Kynes

- **Arrakis Planetologist** — "Ignore the Influence requirement of Sietch Tabr. You summon no sandworms. For each one you would, instead: [trash a card] [1 spice] [1 Intrigue]. (Even when the Conflict is protected by the Shield Wall.)" 첫 문장은 `legal_agent_actions`의 요구 검사에서 예외. 대체는 `rules/planetologist.py`: spice와 Intrigue draw는 즉시, trash는 sandworm마다 `optional_trash` frame(`trash_optional_card`/`decline_optional_trash`; hand·discard·in play)으로 제시한다 — trash 아이콘을 선택으로 읽은 것은 project convention(OQ-037 부기). 소환 경로 다섯 곳(Maker space, Desert Power Reveal, Arrakis Revolt, Intrigue DSL `SummonSandworm`, Reveal 중 Intrigue)이 모두 대체를 쓰며 Shield Wall 검사만 건너뛴다(Maker Hooks·Conflict 존재·Shaddam의 배치 금지는 그대로).
- **Judge of the Change(Signet)** — "If you sent an Agent this turn to... [Landsraad]: [Emperor] 2 Influence: water. [City]: 1 Solari. [Spice Trade]: 1 spice." 자동 해결: 방문 공간의 Agent 아이콘으로 판정하고, Landsraad는 Emperor Influence 2 이상일 때만 water.

### Kota Odax of Ix (Tech Module 전용, 2026-09-07)

- **Secret Project** — "Game Start: Peek at the bottom Tech tile of each stack. Place one face down here. Whenever you could acquire a Tech tile, you may choose this one. It costs 1 less." setup에서 Kota 좌석이 정해지면(고정 setup 즉시, draft는 pick 뒤; Y'rkoon의 Navigation setup 위에 쌓인다) `tech_secret_project` frame(`choose_secret_project(tech_id)`, 후보는 비지 않은 stack의 맨 아래 tile)이 열려 게임을 SETUP에 멈춘다. 고른 tile은 stack에서 빠져 `PlayerState.secret_project_tech_id`(소유자 전용 관측 `private_secret_project`, 상대에게는 `has_secret_project`)에 놓이고, 이후 모든 Acquire Tech(Landsraad 방문·Tech Discount 아이콘)에서 한 후보로 더 제시되며 `tech_cost`가 1을 뺀다(High Council·아이콘 할인과 합산, 하한 0). 획득하면 일반 tile처럼 supply로 간다. "보유 Tech tile" 수에는 들지 않고, 나머지 두 bottom tile을 본 기억은 관측에 넣지 않는다(OQ-041).
- **Reverse Engineering(Signet)** — "1 spice — OR — Trash one of your Tech tiles → Intrigue 1, draw 1." 효과 frame의 `gain_leader_signet_spice` / `trash_leader_tech(tech_id)`(보유 tile마다 하나; `apply_kota_signet_action`). trash한 tile은 `tech_trash`로 가고 flip 상태도 지운다; Intrigue는 `draw_or_queue_intrigue_cards`, 카드는 `draw_or_request_personal_cards`로 Signet 해결 뒤에 뽑는다.
- Leader pool: `LeaderDefinition.tech_only=True`이며 `leaders_for_choam(..., tech_module=True)`에서만 나온다(고정 setup 검증·draft pool·codec `pick_leader`·sweep/tournament 회전 모두 같은 필터). 카드면은 에셋 저장소 `bloodlines/leader/Kota Odax of Ix.webp`(content id `kota_odax_of_ix`).

## 남은 Leader

없음 — 인쇄된 Uprising Leader 9종(기본 8 + CHOAM 전용 Shaddam)의 능력과 Signet Ring이 모두 구현됐다. Sardaukar II contract의 Agent recall 보상은 [contracts audit](contracts.md)의 2026-08-30 manifest 수정과 함께 들어갔다.

## 회귀 테스트

`tests/unit/rules/test_navigation.py`(9건)가 Steersman Y'rkoon의 setup 선택·Strange Form·Hungry for Spice와 Navigation 카드의 trigger 순서·slot 조건·불발·카드 1/3/4/5/8 경로를 고정한다. `tests/unit/rules/test_twisted_intrigue.py`(12건)가 Piter De Vries의 setup·round start·Signet과 Twisted Intrigue 12장의 play 경로(Controlled의 비공개 peek 포함)를 고정한다. `tests/unit/rules/test_bloodlines_leaders.py`(14건)가 Bloodlines Leader 6종의 능력과 Signet(Tuek's Sietch의 존재 조건·방문 행·상대 방문 Intrigue·Smuggle Spice·Makers 누적, Tactics 전진·reset, Fedaykin 후퇴·water 지불, Assassin, Corrino Liaison, Swordmaster 할인, Into the Fray와 비워진 공간, Clandestine 접근·강제 수집, Listeners 두 경로, Planetologist의 Sietch Tabr·sandworm 대체·선택 trash, Judge of the Change 세 아이콘)을 고정한다.

`tests/unit/rules/test_leader_abilities.py`가 signet 자동 해결, Feyd 트랙 분기·단계·최종 칸, Devious/Desert Scouts의 Reveal 액션과 1회 제한, Always Smiling·Unpredictable Foe 문턱과 중복 방지, Jessica 지불·flip·repeat 경로, reach-2 보너스(통과·재도달·타 Faction 미발동), Margot·Staban의 Spy 배치 제한과 후속 지불, Chronicler's Insight의 획득·trash·거절, Limited Allies setup, Smuggle Spice 조건, setup 면 배정을 고정한다. 기본 4종과 신규 4종 각각의 random 4인 완주 soak에서 모든 신규 이벤트가 발동함을 확인했고 replay 검증을 통과했다.
