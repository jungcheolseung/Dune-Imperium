# 플레이어 턴

## 플레이어 턴 단계

- First Player marker를 가진 플레이어부터 시계 방향으로 한 번씩 turn을 가진다. 각 turn에는 Agent turn 또는 Reveal turn 중 하나를 수행한다. [Main p. 8]
- Agent turn은 선택 사항이다. 배치하지 않은 Agent가 남아 있어도 Reveal turn을 선택할 수 있다. [Main p. 8]
- Reveal turn을 마친 플레이어는 나머지 플레이어들이 Reveal turn을 마칠 때까지 이 단계의 turn을 건너뛴다. 모든 플레이어가 Reveal turn을 마치면 Player Turns phase가 끝난다. [Main p. 8]
- 카드에는 Agent box와 Reveal box가 있으며, 한 turn에는 해당 turn 종류에 맞는 box 하나만 사용한다. [Main p. 8]
- Agent turn에 낸 카드와 Reveal turn에 reveal한 카드는 Reveal turn의 Clean Up 전까지 face-up `in play` 상태를 유지한다. [Main p. 20]

## Agent 턴

### 카드와 공간 선택

1. 손에서 카드 한 장을 앞면으로 내고, 그 카드로 리더 위의 Agent 하나를 게임 보드 공간 한 곳에 보낸다. [Main p. 9]
2. 선택한 공간의 왼쪽 위 Agent 아이콘은 카드에 있는 Agent 아이콘 하나와 일치해야 한다. 카드에 아이콘이 여러 개 있어도 하나만 선택하며, 한 장으로 여러 Agent를 보낼 수 없다. [Main p. 9]
3. Agent 아이콘이 없는 카드는 Agent 턴에 낼 수 없고 공개 턴에만 공개할 수 있다. [Main p. 9]
4. 기본적으로 이미 Agent가 있는 공간에는 들어갈 수 없다. Spy의 Infiltrate나
   점유 규칙을 명시적으로 override하는 효과는 예외가 될 수 있다. [Main p. 6]
   [Main p. 9] [Main p. 11]
5. 공간의 비용은 공간이나 낸 카드의 효과를 하나라도 처리하기 전에 즉시 전부 지불해야 한다. 지불할 수 없으면 그 공간을 선택할 수 없다. [Main p. 9]
6. 공간에 Influence requirement가 있으면 진입할 때 충족해야 한다. Imperial Privilege는 Emperor Influence 2 이상, Shipping은 Spacing Guild Influence 2 이상, Sietch Tabr는 Fremen Influence 2 이상을 요구한다. [Main p. 9]
   Undercover Asset은 그 카드를 사용해 Agent를 보내는 그 turn에 한해 이 Influence
   requirement들을 무시한다. 카드의 Agent icon, 공간 비용, 점유 제한 등 다른
   합법성 조건은 그대로 적용한다. `[Undercover Asset card]` `[Main p. 6]`

### Agent 아이콘과 Spy

- Agent icon은 Emperor, Spacing Guild, Bene Gesserit, Fremen, Landsraad, City, Spice Trade, Spy의 여덟 종류다. [Main p. 9]
- Spy Agent 아이콘은 현재 자신의 Spy가 놓인 관측소와 연결된 공간에 Agent를 보낼 수 있게 한다. 이 아이콘을 사용하기 위해 Spy를 회수하지는 않는다. [Main p. 11]
- Infiltrate하려면 상대 Agent가 있는 space와 연결된 observation post에서 자신의 Spy를 recall한다. Infiltrate를 사용하더라도 Agent turn의 card 한 장은 정상적으로 내야 한다. [Main p. 11] [FAQ p. 4]
- space에 Agent를 놓은 직후, space나 card의 효과를 받기 전에 연결된 자신의 Spy를 recall하면 card 한 장을 draw할 수 있다. 이것이 Gather Intelligence다. [Main p. 11]
- 같은 Spy를 Infiltrate와 Gather Intelligence에 함께 사용할 수 없다. 서로 다른 Spy 두 개를 한 turn에 recall해 하나는 Infiltrate, 하나는 Gather Intelligence에 사용할 수 있지만, 둘을 모두 Gather Intelligence에 사용할 수는 없다. [Main p. 11] [FAQ p. 4]

### 효과 처리

- Agent를 보낸 뒤 space 효과와 낸 card의 Agent box 효과를 얻는다. Faction space라면 그 Faction Influence도 1 얻는다. 이 효과들은 원하는 순서로 처리한다. [Main p. 7] [Main p. 9]
- CHOAM Module을 사용할 때 공간 진입으로 contract 조건을 충족하면 완료는
  의무다. 같은 공간을 조건으로 하는 contract가 여러 개면 한 번의 진입으로
  모두 완료하며, contract 효과도 공간 효과 및 Agent box 효과와 원하는 순서로
  처리한다. [Main p. 16] [FAQ p. 1]
- 공간과 카드의 효과는 원칙적으로 의무다. 다만 카드가 선택 가능하다고 명시하거나, 화살표 비용을 지불하지 않거나, 검은색 카드 폐기 아이콘을 사용하지 않는 경우에는 그 효과를 생략할 수 있다. 카드가 화살표 없이 자기 자신을 폐기하라고 지시하면 그 폐기는 의무다. [FAQ p. 3]
- 화살표의 왼쪽 또는 위쪽은 비용이고 오른쪽 또는 아래쪽은 그 비용으로 얻는 효과다. 비용을 지불하지 않으면 효과를 얻지 못하며, 하나의 화살표 비용과 효과는 한 턴에 한 번만 선택할 수 있다. [Main p. 9] [FAQ p. 3]
- Intrigue 카드를 플레이할 때는 예외적으로 표시된 조건을 충족하고 비용을 지불해야 한다. [FAQ p. 2] [FAQ p. 3]
- Shield Wall detonation icon으로 Shield Wall을 제거하는 것은 선택 사항이며, 제거된 Shield Wall은 게임이 끝날 때까지 돌아오지 않는다. [Main p. 10] [FAQ p. 4]

### Agent box와 Signet Ring

- Agent turn에는 낸 card의 Agent box만 처리하고 그 card의 Reveal box는 무시한다. [Main p. 8] [Main p. 9]
- Smuggler's Haven은 Agent box의 화살표를 선택하면 Spice 4를 지불하고
  Victory Point 1을 얻는다. 공간 비용을 먼저 지불한 뒤 남은 Spice로 이 비용을
  낼 수 있어야 하며, 지불하지 않고 생략할 수 있다. `[Smuggler's Haven card]`
  `[Main p. 9]`
- Price is No Object는 Agent box를 처리할 때 Imperium Row 또는 Reserve의 card
  하나를 Persuasion 대신 같은 양의 Solari로 acquire해 hand에 놓거나 생략할 수
  있다. Acquire box가 있는 card를 고르면 그 보너스도 즉시 처리한다.
  `[Price is No Object card]` `[Main pp. 6, 9, 20]`
- Treacherous Maneuver는 Agent box의 화살표를 선택하면 이 카드와 hand의 다른
  Emperor card 한 장을 함께 trash하고, 방문한 Faction의 Influence를 기본 1 대신
  총 2 얻는다. 비용을 지불하지 않고 생략할 수 있으며 discard pile이나 이미
  play 영역에 있던 Emperor card는 비용으로 고를 수 없다.
  `[Treacherous Maneuver card]` `[Main p. 9]`
- Chani, Clever Tactician은 Agent box를 처리하는 시점에 Conflict에 troop과
  sandworm을 합쳐 unit이 3개 이상이면 Intrigue card 1장을 얻는다. 같은 Agent
  turn의 병력 배치를 먼저 처리해 세 번째 unit을 보낸 뒤 이 조건을 확인할 수
  있다. `[Chani, Clever Tactician card]` `[Main pp. 9-10]`
- Signet Ring card를 Agent turn에 내서 Agent를 보내면 Leader의 Signet Ring icon이 표시된 능력을 사용한다. [Main p. 6] [Main p. 20]
- CHOAM Module의 Shaddam Corrino IV에 관한 별도 판정은
  `choam-module.md`와 콘텐츠 명세에서 다룬다. [Main pp. 16-17]

## troop recruit와 Combat deploy

- troop icon 하나를 처리할 때 자신의 supply에서 troop 하나를 가져와 board의 garrison에 놓는다. supply에 troop이 없으면 recruit할 수 없다. [Main p. 10]
- Agent turn의 기본 deploy는 Combat space에 Agent를 보냈을 때 할 수 있다. Combat space는 사막 그림과 교차한 sword 표시가 있는 space다. [Main p. 10]
- Combat space에 들어간 turn에는 그 turn에 recruit한 troop을 원하는 수만큼 deploy하고, 그와 별도로 garrison의 troop을 최대 두 개 더 deploy할 수 있다. [Main p. 10]
- 그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수 있다. 이미 garrison에 있던 troop을 다시 recruit한 것으로 취급해 두 개 제한을 우회할 수는 없다. [Main p. 10] [FAQ p. 4]
- Sardaukar Coordination으로 Agent를 보내면 Combat space가 아니어도 그 turn에
  실제로 recruit한 troop을 Conflict에 deploy할 수 있다. 이 예외는 기존
  garrison troop 두 개를 추가로 deploy하는 권한을 주지 않는다.
  `[Sardaukar Coordination card]` `[Main p. 6]`
- garrison이나 supply의 troop은 Conflict strength를 제공하지 않는다. [Main p. 10] [Main p. 12]

## Reveal turn

### 순서

1. 남은 Agent가 없거나 남은 Agent를 더 사용하지 않기로 하면 Reveal turn을 시작한다. [Main p. 8] [Main p. 12]
2. hand에 남은 card를 모두 face-up으로 reveal해 play 영역에 놓고, 이전 Agent turn에 낸 card와 구분한다. [Main p. 12]
3. 방금 reveal한 card들의 Reveal box 효과만 얻는다. 앞선 Agent turn에 낸 card의 Reveal box 효과는 얻지 않는다. [Main p. 12]
4. Reveal 효과는 원하는 순서로 처리한다. Persuasion을 사용한 acquire는 Reveal 효과의 전, 사이, 뒤 어느 때든 할 수 있다. [Main p. 12]
5. Reveal 효과를 처리하는 동안 strength를 설정하고, strength가 바뀌면 갱신한다. strength 설정은 Reveal 효과 처리와 Clean Up 사이의 별도 고정 단계가 아니다. [Main p. 12] [Main p. 13]
6. Clean Up 때 Agent turn과 Reveal turn에 face-up으로 낸 card를 모두 자신의 discard pile에 놓는다. [Main p. 12]

### Reveal turn 중 draw

- Reveal turn 도중 card를 draw하면 즉시 그 card를 reveal하고 이번 Reveal turn에 사용한다. [FAQ p. 3]
- Reveal turn이 끝난 뒤 card를 draw하면 다음 round까지 hand에 보관한다. 다음 Round Start에도 별도로 card 다섯 장을 draw한다. [FAQ p. 3]
- Smuggler's Haven은 Reveal에서 Persuasion 1을 얻고, 자신의 Spy가 Maker board
  space에 연결된 Observation Post에 있으면 Spice 2를 추가로 얻는다.
  `[Smuggler's Haven card]` `[Main p. 6]`
- Price is No Object는 Reveal에서 Persuasion 2와 Solari 2를 얻는다.
  `[Price is No Object card]`
- Treacherous Maneuver는 Reveal에서 Persuasion 1과 Intrigue card 1장을 얻는다.
  `[Treacherous Maneuver card]`

## 카드 획득과 Imperium Row 보충

- round 동안 얻은 Persuasion은 Reveal turn에 사용한다. Imperium Row의 card 다섯 장과 Reserve의 Prepare the Way 또는 The Spice Must Flow를 acquire할 수 있다. [Main p. 13]
- card 오른쪽 위의 Persuasion cost를 지불한다. 가진 Persuasion이 허용하는 만큼 여러 장을 acquire할 수 있다. [Main p. 13]
- 여러 출처의 Persuasion을 합쳐 card 한 장의 cost를 내거나, 한 출처의 Persuasion을 나누어 여러 card의 cost를 낼 수 있다. 사용하지 않은 Persuasion은 Reveal turn이 끝나면 사라진다. [Main p. 13]
- acquire한 card는 자신의 discard pile에 놓고 즉시 사용하지 않는다. 이후 deck에서 card를 draw할 수 없을 때 discard pile을 shuffle해 새 deck을 만든다. [Main p. 6] [Main p. 13]
- Price is No Object의 Agent 효과로 acquire한 card는 이 일반 규칙을 덮어써
  discard pile 대신 hand에 놓는다. The Spice Must Flow도 선택할 수 있으며,
  acquire 보상인 Victory Point를 즉시 얻는다. `[Price is No Object card]`
  `[The Spice Must Flow card]` `[Main p. 6]`
- Imperium Row에는 항상 card 다섯 장이 있어야 한다. card를 acquire해 자리가 비면 Imperium Deck 맨 위 card로 보충하며, Persuasion이 남아 있으면 새로 보충된 card도 acquire할 수 있다. [Main p. 13]
- card의 cost 아래에 acquire box가 있으면 그 효과는 card를 acquire하는 순간 한 번만 얻으며, 나중에 hand에서 그 card를 낼 때는 얻지 않는다. [Main p. 20]
- The Spice Must Flow를 acquire하며 얻은 Victory Point는 이후 그 카드를
  trash하더라도 유지한다. [FAQ p. 4]

## Reveal turn의 strength

- strength는 Conflict의 unit과 이번 Reveal turn에 reveal한 sword icon으로 계산한다. Conflict의 troop 하나는 strength 2, sandworm 하나는 strength 3, reveal한 sword 하나는 strength 1이다. [Main p. 12]
- Conflict에 unit이 하나 이상 있어야 strength를 가질 수 있다. 마지막 unit이 제거되면 sword가 남아 있어도 strength는 0이 된다. [Main p. 12]
- Calculus of Power는 Reveal 중 play 영역의 다른 Emperor card를 trash해 sword
  3을 얻거나 거절할 수 있다. 비용으로 자기 자신을 고를 수 없고, trash된 card의
  고유 trash 효과는 정상 처리한다. `[Calculus of Power card]`
- Sardaukar Coordination은 기본 sword 1개에 더해 이번 Reveal에 공개한 Emperor
  card마다 sword 1개를 얻으며 자기 자신도 센다. 이전 Agent turn에 낸 Emperor
  card는 이 수에 포함하지 않는다. `[Sardaukar Coordination card]`
- Chani, Clever Tactician은 Fremen Bond로 Persuasion 2를 얻는다. Reveal의
  선택형 화살표를 사용하면 Conflict의 troop 2개를 garrison으로 retreat하고
  sword 4개를 얻는다. 다른 unit이 남아 있으면 troop strength 4가 sword 4로
  대체되어 총 strength는 유지되지만, 마지막 unit을 모두 retreat하면 sword가
  남아 있어도 strength는 0이 된다. `[Chani, Clever Tactician card]`
  `[Main pp. 12, 20]`
- strength를 계산하면 다른 플레이어에게 알리고 Combat marker를 Combat track의 해당 칸으로 옮긴다. strength가 20을 넘으면 marker를 `+20` 면으로 뒤집고 track 처음부터 초과분을 표시한다. [Main p. 12]
- Reveal turn 중 효과가 unit 수나 strength를 바꾸면 Combat marker도 그에 맞게 갱신한다. [Main p. 13]

## Intrigue 카드의 시점

- Intrigue 카드는 자신의 덱과 분리해 뒷면으로 보관한다. 소유자는 언제든 확인할 수 있지만 플레이할 때만 상대에게 공개하며, 해결한 카드는 Intrigue Deck 옆의 앞면 버림 더미에 놓는다. [Main p. 7]
- Plot Intrigue 카드는 자신의 Agent 턴 또는 공개 턴 중 어느 때든 플레이할 수 있다. Combat Intrigue 카드는 전투 단계에만, Endgame Intrigue 카드는 게임 종료 때만 플레이할 수 있다. [Main p. 7] [Main p. 8]
- Intrigue 카드를 플레이하려면 카드의 모든 조건을 충족하고 모든 비용을 지불해야 한다. [FAQ p. 2]
- 다음 공개 턴까지 적용되지 않는 Plot 효과는 카드를 앞면으로 자신의 앞에 두었다가 그 공개 턴에 사용한 뒤 버린다. [FAQ p. 2]
- Intrigue Deck이 바닥나면 버린 Intrigue 카드를 섞어 새 Intrigue Deck을 만든다. [FAQ p. 2]

## `discard`의 의미

- 효과가 플레이어에게 카드 한 장을 `discard`하라고 지시하면 별도 지정이 없는 한 그 플레이어의 손에서 선택한다. [FAQ p. 2]
- 별도 지정이 없는 `discard` 대상으로 Intrigue 카드를 선택할 수 없다. [Main p. 20]
- 일반 카드의 버림 더미와 Intrigue 카드의 버림 더미는 서로 별개다. 일반 카드는 각 플레이어의 버림 더미에, 해결한 Intrigue 카드는 Intrigue Deck 옆의 공용 앞면 버림 더미에 놓는다. [Main p. 7] [Main p. 13]
- 현재 ruleset의 Spacing Guild's Favor는 Clean Up에 in-play 상태에서 discard
  pile로 옮기는 것으로 그 card의 `discard` 능력을
  발동하지 않는다. hand에서 discard할 때만 발동한다. [Main p. 17]

## 미확정 항목

- 여러 의무 효과가 서로 충돌할 때 적용할 일반 우선순위는 지정된 두 문서에서 확인되지 않는다. 확인된 범위에서는 공간 효과, Agent 상자 효과, 세력 영향력 및 조건을 충족한 계약 효과만 원하는 순서로 처리할 수 있다. [Main p. 9] [FAQ p. 1] [FAQ p. 3]
