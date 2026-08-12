# 4인 Uprising 보드 공간

이 표는 Uprising Rules Supplements의 Board Space Guide pp. 1-2에 있는 4인 board
space를 구현용으로 재구성한 것이다. Agent icon, Combat/Maker 속성, requirement,
cost, effect를 한 행에 모았다.

Faction space의 `Influence 1 획득`은 Main의 Faction 방문 규칙과 Board Space
Guide 양쪽에 같은 방문 결과로 적혀 있다. 아래 표에는 그 결과를 한 번만 적는다.
`[Main pp. 7, 9]` `[Board Guide pp. 1-2]`

Combat space를 방문하면 해당 turn에 recruit한 모든 troop과 기존 garrison의
troop 최대 2개를 Conflict에 deploy할 수 있다. 아래 각 행은 이 공통 배치 규칙을
반복하지 않는다. `[Board Guide p. 1]`

## Emperor

| space | 속성·진입 조건 | space 결과 | 출처 |
| --- | --- | --- | --- |
| Dutiful Service | Emperor | Emperor Influence 1. CHOAM Module을 쓰면 face-up contract 1개를 가져가고, 가져갈 contract가 없거나 module을 끄면 2 Solari. | `[Board Guide p. 1]` |
| Sardaukar | Emperor; 4인 cost 4 spice | Emperor Influence 1, Intrigue 1장 draw, troop 4개 recruit. | `[Board Guide p. 2]` |

## Spacing Guild

| space | 속성·진입 조건 | space 결과 | 출처 |
| --- | --- | --- | --- |
| Deliver Supplies | Spacing Guild | Spacing Guild Influence 1, water 1. | `[Board Guide p. 1]` |
| Heighliner | Spacing Guild; Combat; cost 5 spice | Spacing Guild Influence 1, troop 5개 recruit. | `[Board Guide p. 2]` |

## Bene Gesserit

| space | 속성·진입 조건 | space 결과 | 출처 |
| --- | --- | --- | --- |
| Espionage | Bene Gesserit; cost 1 spice | Bene Gesserit Influence 1, card 1장 draw, Spy 1개를 배치할 수 있음. | `[Board Guide p. 1]` `[Main p. 11]` |
| Secrets | Bene Gesserit | Bene Gesserit Influence 1, Intrigue 1장 draw. Intrigue를 4장 이상 가진 각 opponent에게서 무작위로 1장씩 받는다. | `[Board Guide p. 2]` |

## Fremen

| space | 속성·진입 조건 | space 결과 | 출처 |
| --- | --- | --- | --- |
| Desert Tactics | Fremen; Combat; cost 1 water | Fremen Influence 1, troop 1개 recruit, 원하면 card 1장 trash. | `[Board Guide p. 1]` `[Main p. 20]` |
| Fremkit | Fremen; Combat | Fremen Influence 1, card 1장 draw. | `[Board Guide p. 1]` |

## Landsraad

| space | 속성·진입 조건 | space 결과 | 출처 |
| --- | --- | --- | --- |
| Assembly Hall | Landsraad | Intrigue 1장 draw. 자신의 Agent가 이곳에 있으면 그 round의 Reveal turn에 Persuasion 1. | `[Board Guide p. 1]` |
| Gather Support | Landsraad; cost로 0 또는 2 Solari 선택 | troop 2개 recruit. 2 Solari를 냈다면 water 1도 획득. | `[Board Guide p. 1]` |
| High Council | Landsraad; cost 5 Solari | 첫 방문이면 비어 있는 Council seat에 Councilor token을 놓고, 이후 모든 Reveal turn에 Persuasion 2. 이후 이 space를 다시 방문할 때마다 spice 2, Intrigue 1장, troop 3개. | `[Board Guide p. 2]` |
| Imperial Privilege | Landsraad; Emperor Influence 2 이상; cost 3 Solari | 원하면 Intrigue 1장을 discard하고 Intrigue 1장을 draw. 이번 turn에 보낸 Agent가 아닌 자신의 다른 Agent 1개를 recall하고 card 1장을 draw. | `[Board Guide p. 2]` |
| Swordmaster | Landsraad; 아무도 Swordmaster를 얻지 않았다면 cost 8 Solari, 한 명이라도 얻은 뒤에는 6 Solari | 플레이어마다 게임 중 1회만 방문. setup 때 board 옆에 둔 세 번째 Agent를 Leader에 놓으며, 현재 round를 포함해 이후 사용한다. | `[Board Guide p. 2]` |

## City

| space | 속성·진입 조건 | space 결과 | 출처 |
| --- | --- | --- | --- |
| Arrakeen | City; Combat; critical/control | troop 1개 recruit, card 1장 draw. Arrakeen controller는 1 Solari. | `[Board Guide p. 1]` |
| Research Station | City; Combat; cost 2 water | troop 2개 recruit, card 2장 draw. | `[Board Guide p. 2]` |
| Sietch Tabr | City; Combat; Fremen Influence 2 이상 | 다음 중 하나를 선택: (a) 아직 없다면 Maker Hooks token, troop 1개, water 1; (b) water 1, 그리고 원하면 Shield Wall 제거. | `[Board Guide p. 2]` |
| Spice Refinery | City; Combat; critical/control; cost로 0 또는 1 spice 선택 | 0 spice를 내면 2 Solari, 1 spice를 내면 4 Solari. Spice Refinery controller는 1 Solari. | `[Board Guide p. 2]` |

Sietch Tabr는 City icon space이며 Faction Agent icon space가 아니다. 진입에는 Fremen
Influence requirement가 있지만, Board Space Guide는 이 space의 결과로 Fremen
Influence 획득을 적지 않는다. `[Board Guide p. 2]`

## Spice Trade

| space | 속성·진입 조건 | space 결과 | 출처 |
| --- | --- | --- | --- |
| Accept Contract | Spice Trade | card 1장 draw. CHOAM Module을 쓰면 face-up contract 1개를 가져가고, 가져갈 contract가 없거나 module을 끄면 2 Solari. | `[Board Guide p. 1]` |
| Deep Desert | Spice Trade; Combat; Maker; cost 3 water | 이곳의 bonus spice 전부. 추가로 (a) spice 4, 또는 (b) Maker Hooks가 있으면 sandworm 2개 소환 중 하나를 선택. | `[Board Guide p. 1]` |
| Hagga Basin | Spice Trade; Combat; Maker; cost 1 water | 이곳의 bonus spice 전부. 추가로 (a) spice 2, 또는 (b) Maker Hooks가 있으면 sandworm 1개 소환 중 하나를 선택. | `[Board Guide p. 2]` |
| Imperial Basin | Spice Trade; Combat; Maker; critical/control | spice 1과 이곳의 bonus spice 전부. Imperial Basin controller는 spice 1. | `[Board Guide p. 2]` |
| Shipping | Spice Trade; Spacing Guild Influence 2 이상; cost 3 spice | 5 Solari, 선택한 Faction 하나의 Influence 1. | `[Board Guide p. 2]` |

Imperial Privilege는 Emperor Influence requirement가 있지만 Landsraad icon space이고,
Shipping은 Spacing Guild Influence requirement가 있지만 Spice Trade icon space다.
`[Board Guide p. 2]`

## 정적 속성 검산

위 공식 목록을 기준으로 한 4인 board의 정적 분류는 다음과 같다.

- Faction icon 8개, Landsraad 5개, City 4개, Spice Trade 5개로 총 22개다.
  `[Board Guide pp. 1-2]`
- Combat space는 Arrakeen, Deep Desert, Desert Tactics, Fremkit, Hagga Basin,
  Heighliner, Imperial Basin, Research Station, Sietch Tabr, Spice Refinery의
  10개다. `[Board Guide pp. 1-2]`
- Maker space는 Deep Desert, Hagga Basin, Imperial Basin의 3개다.
  `[Main p. 15]` `[Board Guide pp. 1-2]`
- critical/control location은 Arrakeen, Spice Refinery, Imperial Basin의 3개다.
  `[Main p. 10]`

## 이 guide가 제공하지 않는 정보

Board Space Guide의 텍스트는 observation post와 space 사이의 실제 연결 graph를
열거하지 않는다. 연결은 공식 setup board artwork에서 별도로 전사한
[`observation-posts.md`](observation-posts.md)를 사용하며, 이 표의 공간 배치만
보고 인접 관계를 추정해서는 안 된다. `[Main pp. 4-5 board artwork]`
