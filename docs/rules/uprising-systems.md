# Uprising 공통 시스템

이 문서는 여러 phase와 보드 공간에 걸쳐 적용되는 공통 규칙을 모은다. 구체적인
턴 순서와 Combat 처리는 각각 `player-turns.md`와
`combat-and-round-end.md`를 따른다.

## 구성물 공급과 자원

- Solari, spice, water와 sandworm은 bank에 둔다. 이 공급은 제한 수량으로 보지
  않으며 구성물이 모자라면 적절한 대체물을 사용할 수 있다. `[Main p. 5]`
- 각 플레이어의 troop은 12개다. troop을 recruit할 때는 반드시 자신의 supply에서
  가져오며, 기본 목적지는 garrison이다. Combat space에 Agent를 보낸 turn에
  recruit한 troop은 즉시 Conflict에 deploy할 수 있다. supply에 troop이 없으면
  더 recruit할 수 없다. `[Main pp. 5, 10, 20]` `[FAQ p. 4]`
- Maker Hooks는 bank에 4개를 둔다. 플레이어는 이미 하나가 있으면 새 token을
  얻지 않으며, sandworm을 소환할 때 token을 소비하지 않는다.
  `[Main pp. 5, 20]` `[FAQ p. 2]`
- Reserve는 Prepare the Way 8장과 The Spice Must Flow 10장의 두 stack으로
  시작한다. `[Main p. 3]`

## deck-building과 카드 상태

- 각 플레이어는 동일한 10장 starting deck으로 시작한다. 새 Imperium/Reserve
  카드를 acquire하면 먼저 자신의 discard pile에 face-up으로 놓는다.
  `[Main pp. 3, 6, 13]`
- 카드를 draw해야 하는데 deck이 비어 있으면 자신의 discard pile을 shuffle해 새
  deck을 만든 뒤 필요한 수만큼 계속 draw한다. `[Main pp. 6, 20]`
- 카드를 trash하면 남은 게임 동안 자신의 deck 순환에서 제거한다. 일반 카드는
  box로 돌려보내고 Reserve 카드는 해당 Reserve stack으로 돌려보낸다.
  `[Main pp. 6, 20]`
- 일반 trash 아이콘은 hand, discard pile, in play 가운데 카드 1장을 대상으로
  한다. Intrigue trash 아이콘은 hand의 Intrigue card 1장을 대상으로 한다.
  `[Main p. 20]`
- Agent turn에 play한 카드와 현재 Reveal turn에 reveal한 카드는 Reveal turn의
  Clean Up 전까지 face-up `in play`다. 먼저 trash된 카드는 예외다.
  `[Main p. 20]`
- 별도 위치를 지정하지 않고 `discard a card`라고 하면 hand의 카드를 뜻한다.
  일반 카드 discard 지시는 Intrigue를 명시하지 않는 한 Intrigue card를 대상으로
  하지 않는다. `[Main p. 20]` `[FAQ p. 2]`

## 효과의 의무·선택과 비용

- board space나 play한 카드의 효과는 원칙적으로 의무다. `may`라고 적힌 효과,
  arrow의 비용을 지불할지 선택하는 효과, 검은색 trash 아이콘으로 trash하는
  효과는 선택이다. 단, 카드가 arrow 없이 자기 자신을 trash하라고 지시하면
  의무다. `[FAQ p. 3]`
- arrow의 왼쪽 또는 위쪽은 비용이고 오른쪽 또는 아래쪽은 결과다. 비용을
  지불하지 않으면 결과를 받지 않는다. 같은 arrow 비용-결과는 한 turn에 한 번만
  사용할 수 있다. Combat reward를 sandworm으로 배가하는 경우는 별도 예외다.
  `[Main pp. 9, 20]` `[FAQ p. 3]`
- Intrigue card를 play할 때는 그 카드의 조건을 만족하고 비용을 지불해야 한다.
  Intrigue의 비용은 일반적인 선택형 arrow와 달리 play를 선택했다면 필수다.
  `[FAQ pp. 2-3]`
- 검은색 trash 아이콘에 의한 trash는 선택이지만, 비용으로 trash하거나 카드가
  자기 자신을 trash하라고 지시하면 선택이 아니다. `[Main p. 20]`
- 카드 규칙은 일반 규칙을 바꿀 수 있다. `[Main p. 6]`

## Leader와 Signet Ring

- 각 Leader에는 일반 능력과 Signet Ring 아이콘으로 표시된 능력이 있다. 일반
  능력은 카드에 적힌 시점에 사용하고, Signet Ring 능력은 Signet Ring starting
  card를 Agent turn에 play할 때 발동한다. `[Main p. 6]`
- Uprising은 양면 Leader를 포함한다. 개별 Leader의 setup 면과 전환 조건은 해당
  Leader 텍스트 및 [공식 판정 색인](official-rulings-index.md)을 따른다.
  `[Main pp. 3, 17]`

## Faction Influence

- 네 Faction은 Emperor, Spacing Guild, Bene Gesserit, Fremen이다. 각 플레이어의
  cube는 각 Influence track 맨 아래에서 시작한다. `[Main pp. 5, 7]`
- Faction board space에 Agent를 보내면 해당 Faction Influence를 1 올린다. 카드나
  다른 효과도 Influence를 올리거나 내릴 수 있다. `[Main p. 7]`
- Influence 2에 도달하면 1 VP를 얻는다. 이후 2 아래로 내려가면 그 VP를 잃는다.
  여러 Influence를 한 번에 얻으며 2를 지나가는 것도 `reach 2`이고, 내려갈 때가
  아니라 올라갈 때만 `reach`로 본다. Influence를 잃었다가 다시 올라오면 다시
  도달할 수 있다. `[Main pp. 7, 17]`
- Influence 4에 도달하면 track에 표시된 보너스를 얻는다. Emperor는 troop 2개,
  Spacing Guild는 water 3, Bene Gesserit은 Intrigue card 1장, Fremen은 water 1을
  얻는다. 이 값은 공식 setup board artwork와 p. 7의 Bene Gesserit track 예시를
  함께 전사했다. 4 아래로 내려가도
  보너스를 반환하지 않으며, 다시 4에 도달하면 같은 보너스를 다시 받을 수 있다.
  `[Main pp. 4, 7 board artwork]`

## Alliance

- 한 Faction에서 처음 Influence 4에 도달한 플레이어는 Alliance token과 그
  token의 1 VP를 얻는다. 다른 플레이어가 현재 보유자보다 **높은** 칸으로
  올라가면 token과 그 VP가 새 플레이어에게 이전된다. 동률만으로는 Main의 일반
  이전 조건을 충족하지 않는다. `[Main p. 7]`
- Alliance 보유자가 Influence를 잃기 전에 다른 플레이어와 이미 동률이었다면,
  그 동률 플레이어가 token을 즉시 가져간다. 동률 플레이어가 여러 명이면 기존
  보유자가 받을 한 명을 정한다. `[FAQ p. 1]`
- 보유자가 Influence 3 이하로 내려가면 Alliance token을 잃는다. 다른 어느
  플레이어도 Influence 4 이상이 아니면 token을 board로 돌려놓는다. 이때 4
  이상인 후보가 여러 명이면 감소 직전 보유자와 Influence 4에서 동률이므로,
  기존 보유자가 그중 한 명을 정한다. 한 칸씩 처리하는 유효한 track 전이에서는
  직전 동률이 아닌 복수 후보가 발생하지 않는다. `[FAQ p. 1]`

## Critical location과 Control

- critical location은 Arrakeen, Spice Refinery, Imperial Basin 세 곳이다. 해당
  이름의 Conflict를 이긴 플레이어는 그 공간의 flag에 자신의 Control marker를
  놓으며 기존 opponent marker가 있으면 교체한다. `[Main pp. 10, 20]`
- Control marker가 있는 동안 누가 그 공간에 Agent를 보내든 controller가 표시된
  bonus를 받는다. Arrakeen과 Spice Refinery는 1 Solari, Imperial Basin은
  1 spice다. `[Main p. 10]`
- 자신이 이미 control하는 location의 Conflict가 Round Start에 reveal되면,
  자신의 supply에서 troop 1개를 Conflict에 deploy할 수 있다. `[Main pp. 10, 20]`

## Shield Wall

- setup 때 Shield Wall token을 board에 놓는다. token이 있는 동안 Arrakeen,
  Spice Refinery, Imperial Basin의 Conflict에는 sandworm을 소환할 수 없다.
  `[Main pp. 4, 10]`
- 해당 Conflict 카드 오른쪽 아래의 Shield Wall 표시는 detonation 효과가 아니라
  현재 Conflict가 이 보호를 받는다는 표시다. Uprising 기본 Conflict에는 이
  표시가 있는 카드가 여섯 장이다. `[Main p. 10 board artwork]`
- Shield Wall detonation 아이콘은 token을 제거할 **선택권**을 준다. 제거한 token은
  box로 돌아가고 게임이 끝날 때까지 복구되지 않는다. 제거된 뒤에는 어느
  Conflict에도 Shield Wall로 인한 sandworm 금지가 없다.
  `[Main pp. 10, 20]` `[FAQ p. 4]`
- Shield Wall로 보호되는 현재 Conflict에 대한 sandworm 효과는 아무 일도 하지
  않는다. `[Main p. 20]`

## troop과 sandworm

- troop은 recruit되면 우선 garrison에 간다. Agent를 Combat space에 보낸 그
  turn에 recruit한 troop은 해당 Conflict에 바로 deploy할 수 있다.
  `[Main pp. 10, 20]`
- Combat space를 방문할 때 그 turn에 **어떤 출처에서든** recruit한 troop을
  원하는 수만큼 deploy할 수 있고, 여기에 더해 기존 garrison troop을 최대
  2개까지 deploy할 수 있다. garrison troop을 다시 recruit한 것으로 처리해 이
  제한을 우회할 수 없다. `[Main p. 10]` `[FAQ p. 4]`
- sandworm 아이콘은 허용되는 경우 bank에서 sandworm 1개를 가져와 즉시
  Conflict에 deploy한다. sandworm은 garrison에 놓지 않는다. `[Main pp. 10, 20]`
- sandworm 아이콘 앞의 Maker Hooks 표시는 그 token을 보유해야 한다는
  requirement다. Maker Hooks는 사용해도 소모되지 않는다.
  `[Main pp. 10, 20]` `[FAQ p. 2]`

## Spy와 observation post

- board의 observation post는 하나 이상의 board space에 연결된다. Spy icon이
  나오면 자신의 supply에서 Spy를 가져와 비어 있는 observation post 한 곳에
  놓을 수 있다. 효과가 특정 Agent icon 연결을 요구하면 그 조건을 만족하는
  post만 선택할 수 있다. `[Main pp. 11, 20]`
- Double Agent는 이번 Agent turn에 방문한 space를 이미 spying 중일 때 상대
  Spy가 있는 observation post에 자기 Spy를 함께 놓을 수 있다. 같은 플레이어가
  자기 Spy 둘을 한 post에 놓는 것은 허용되지 않는다. `[Double Agent card]`
- Spy 배치를 선택했지만 supply에 Spy가 없다면, 먼저 board의 자기 Spy 하나를
  효과 없이 recall할 수 있다. `[Main pp. 11, 20]`
- Recall Spy 아이콘은 observation post의 자기 Spy 하나를 supply로 돌려보낼 수
  있게 한다.
  `[Main pp. 11, 20]`
- `Infiltrate`: 다른 플레이어의 Agent가 있는 space로 Agent를 보내려 할 때,
  연결된 자기 Spy를 recall하면 그 Agent의 점유를 무시하고 같은 space에 Agent를
  보낼 수 있다. 이 경우에도 Agent turn에 card를 play해야 한다.
  `[Main p. 11]` `[FAQ p. 4]`
- `Gather Intelligence`: Agent를 space에 놓은 직후, board space와 Agent card의
  효과를 받기 전에 연결된 자기 Spy를 recall하면 card 1장을 draw한다. 이
  경우에도 실제 Agent card play가 필요하다. `[Main p. 11]` `[FAQ p. 4]`
- 하나의 Spy를 Infiltrate와 Gather Intelligence 양쪽에 사용할 수 없다. 한 turn에
  Spy 두 개를 recall할 수 있는 경우는 하나를 Infiltrate에, 다른 하나를 Gather
  Intelligence에 쓰는 경우뿐이다. 두 개를 모두 Gather Intelligence에 쓸 수는
  없다. `[Main p. 11]` `[FAQ p. 4]`
- Spy Agent icon은 현재 자기 Spy가 있는 observation post와 연결된 board space를
  Agent 목적지로 허용한다. 이 사용 자체로 Spy를 recall하지 않는다.
  `[Main pp. 9, 11]`

Observation post 13개의 공식 board 연결선 전사는
[`observation-posts.md`](observation-posts.md)에 따로 둔다. `[Main pp. 4-5
board artwork]`

## Maker space

- 현재 4인 board에서 spice를 harvest할 수 있는 Maker space는 Deep Desert,
  Hagga Basin, Imperial Basin이다. `[Main p. 15]` `[FAQ p. 2]`
- Maker phase의 누적과 space 방문 시 bonus spice 획득은
  `combat-and-round-end.md`와 `board-spaces.md`에 정리한다.

## 추가 icon과 용어

- Alliance 조건 아이콘이 붙은 효과는 표시된 Faction의 Alliance token을 가진
  경우에만 사용할 수 있다. `[Main p. 20]`
- Fremen Bond 효과는 다른 Fremen card가 하나 이상 in play일 때 사용할 수 있다.
  Fremen Bond 카드 두 장은 play 순서와 관계없이 서로를 활성화할 수 있다.
  `[Main p. 20]`
- 임의의 Faction Influence를 1 또는 2 얻거나 1 잃는 효과는 네 Faction 가운데
  하나를 고른다. Influence 2를 얻을 때 서로 다른 Faction에 나누지 않는다.
  `[Main p. 20]`
- Recall Agent는 이번 turn에 방금 보낸 Agent가 아닌 board의 다른 자기 Agent를
  Leader로 돌린다. 돌아온 Agent는 같은 round의 이후 Agent turn에 다시 사용할
  수 있다. `[Main p. 20]`
- Retreat는 troop을 Conflict에서 자기 garrison으로 옮긴다. 효과가 `any number`의
  troop을 retreat하게 하면 0개도 선택할 수 있다. `[Main p. 20]` `[FAQ p. 3]`
- Steal Intrigue는 Intrigue card가 4장 이상인 각 opponent에게서 무작위로 1장씩
  받는 효과다. `[Main p. 20]`
- Uprising 아이콘은 set 식별용이며 그 자체로 게임 효과가 없다. `[Main p. 20]`
