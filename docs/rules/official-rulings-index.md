# 공식 clarification과 FAQ 판정 색인

이 문서는 4인 Uprising 규칙을 구현할 때 Main의 clarification과 공식 FAQ에서
빠뜨리기 쉬운 판정을 찾기 위한 색인이다. FAQ는 여러 제품을 함께 다루므로,
일반 규칙은 현재 문서에 바로 연결하되 named-card 판정은 지정된 공식 텍스트로
Uprising 기본 룰셋 소속을 확인할 수 있을 때만 활성 규칙으로 승격한다.

`반영 문서`는 판정을 상세히 설명하는 현재 규칙 문서를 뜻한다. 개별 카드나
Leader에만 적용되는 판정은 content manifest 전사 단계까지 이 색인에 보존한다.

## 1. 4인 Uprising에 직접 적용하는 일반 FAQ

| FAQ entry | FAQ page | 핵심 판정 | 반영 문서 |
| --- | --- | --- | --- |
| Alliance | [FAQ p. 1] | 보유자가 Influence를 잃기 전 다른 플레이어와 동률이었다면 그 플레이어에게 Alliance가 넘어간다. 동률 상대가 여러 명이면 기존 보유자가 받을 사람을 정한다. 보유자가 3 이하로 내려가고 받을 자격이 있는 플레이어가 없으면 token을 board로 돌린다. | [uprising-systems.md](uprising-systems.md) |
| Conflict | [FAQ p. 1] | Conflict 보상 규칙은 4인일 때 별도 분기를 사용한다. 1~3인용 보상 처리를 4인 게임에 재사용하지 않는다. | [combat-and-round-end.md](combat-and-round-end.md) |
| contract | [FAQ p. 1] | CHOAM Module을 켠 경우 조건을 만족한 계약은 의무적으로 완료한다. 같은 공간 계약 여러 개는 한 번의 Agent 방문으로 모두 완료하며, 공간 지정 계약은 board space와 Agent box 효과 사이에서 원하는 순서로 처리할 수 있는 Agent-turn 효과다. | [choam-module.md](choam-module.md) |
| discard | [FAQ p. 2] | 별도 위치가 없으면 discard 대상은 hand의 카드다. Main의 일반 용어에 따라 Intrigue를 명시하지 않은 discard는 Intrigue card를 대상으로 하지 않는다. | [uprising-systems.md](uprising-systems.md) |
| Endgame | [FAQ p. 2] | Main의 spice, Solari, water, garrison troop 비교로도 동률이면 가장 최근에 Reveal turn을 한 플레이어가 이긴다. | [setup-and-game-flow.md](setup-and-game-flow.md) |
| Intrigue cards | [FAQ p. 2] | Intrigue를 play하려면 조건과 비용을 충족해야 한다. 다음 Reveal turn에 적용되는 Plot은 그때까지 face-up으로 유지한다. Intrigue deck이 고갈되면 discard pile을 섞어 새 deck을 만든다. | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| maker board space | [FAQ p. 2] | Maker board space는 spice를 harvest하는 공간이라는 용어다. FAQ에 함께 적힌 다른 보드·인원수의 공간을 현재 4인 보드 정의에 자동 추가하지 않는다. | [uprising-systems.md](uprising-systems.md) |
| Maker hooks | [FAQ p. 2] | sandworm을 소환할 때 Maker Hooks token은 소비하지 않는다. | [uprising-systems.md](uprising-systems.md) |
| optional effects | [FAQ p. 3] | 효과는 원칙적으로 의무다. `may`, arrow 비용의 지불 여부, 검은색 trash 아이콘은 선택이지만, arrow 없이 카드가 자신을 trash하라고 하면 의무다. | [uprising-systems.md](uprising-systems.md) |
| paying a cost | [FAQ p. 3] | 하나의 arrow 비용-효과는 한 번만 선택할 수 있다. 비용을 배수로 내고 효과를 반복해서는 안 된다. | [uprising-systems.md](uprising-systems.md) |
| Retreat | [FAQ p. 3] | `any number`의 troop을 retreat할 수 있는 효과에서는 0개를 선택할 수 있다. | [uprising-systems.md](uprising-systems.md) |
| Reveal turn | [FAQ p. 3] | Reveal turn 도중 draw한 카드는 즉시 reveal해 그 turn에 사용한다. Reveal turn이 끝난 뒤 draw한 카드는 hand에 보관하고 다음 Round Start에 5장을 추가로 draw한다. | [setup-and-game-flow.md](setup-and-game-flow.md), [player-turns.md](player-turns.md) |
| Shield Wall | [FAQ p. 4] | Shield Wall 아이콘으로 token을 제거하는 것은 선택이다. 한 번 제거하면 게임이 끝날 때까지 돌아오지 않는다. | [uprising-systems.md](uprising-systems.md) |
| Spies | [FAQ p. 4] | Infiltrate나 Gather Intelligence로 Spy를 recall하려면 실제 Agent card를 play해야 한다. 한 turn에 Spy 두 개를 recall하려면 각각 서로 다른 효과에 써야 하며, 둘 다 Gather Intelligence에 쓸 수 없다. | [uprising-systems.md](uprising-systems.md) |
| troops | [FAQ p. 4] | recruit는 supply에서만 한다. garrison troop을 다시 recruit한 것처럼 처리해 deploy 제한을 우회할 수 없다. Combat space에 Agent를 보낸 turn에는 어떤 출처에서 recruit했든 그 troop을 Conflict에 deploy할 수 있다. | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| Victory Points | [FAQ p. 4] | 실제 점수는 인쇄된 Score track의 12를 넘을 수 있다. | [setup-and-game-flow.md](setup-and-game-flow.md) |
| “When you win a Conflict” | [FAQ p. 4] | 공동 1위는 Conflict 승리가 아니다. 승리 보상으로 뽑은 Intrigue가 바로 그 승리에 반응할 수 있다면 즉시 play할 수 있다. | [combat-and-round-end.md](combat-and-round-end.md) |
| The Spice Must Flow | [FAQ p. 4] | acquire할 때 얻은 VP는 해당 카드를 나중에 trash해도 유지한다. | [player-turns.md](player-turns.md) |

`Gather Intelligence`와 `Infiltrate` FAQ entry는 `Spies`로, `Score track`은
`Victory Points`로, `tiebreaker`는 `Endgame`으로 보내는 교차 참조이므로 위
대표 entry에 합쳤다. [FAQ p. 2] [FAQ p. 3] [FAQ p. 4]

## 2. Main p. 20 구현 기준 용어

Main p. 20은 FAQ를 적용하기 전의 일반 용어 기준이다. 아래 항목은 이름이 비슷한
상태 이동이나 이벤트를 구현에서 합치지 않기 위한 최소 색인이다.

| 용어 | 놓치면 안 되는 기준 | 반영 문서 |
| --- | --- | --- |
| Acquire | acquire box는 카드를 얻는 순간 한 번만 처리하며, 나중에 hand에서 play할 때 반복하지 않는다. [Main p. 20] | [player-turns.md](player-turns.md) |
| Agent / Signet Ring | Swordmaster 공간으로 세 번째 Agent를 얻으면 남은 게임 동안 사용한다. Signet Ring 능력은 그 카드를 Agent turn에 play할 때 발동한다. [Main p. 20] | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| Battle Icon | Conflict 승자는 같은 face-up battle icon 한 쌍을 뒤집어 1 VP를 얻는다. Endgame의 wild icon은 세 종류 중 하나와 짝지을 수 있다. [Main p. 20] | [combat-and-round-end.md](combat-and-round-end.md), [setup-and-game-flow.md](setup-and-game-flow.md) |
| Contract | CHOAM Module을 끄면 contract 아이콘은 2 Solari다. 모듈을 켜면 face-up contract를 가져가고, 남은 계약이 없을 때 2 Solari를 얻는다. [Main p. 20] | [choam-module.md](choam-module.md) |
| Control | Control reward는 기존 opponent marker를 교체한다. 이미 control하는 장소의 Conflict가 reveal되면 supply troop 1개를 deploy할 수 있다. [Main p. 20] | [uprising-systems.md](uprising-systems.md), [setup-and-game-flow.md](setup-and-game-flow.md) |
| Discard / Draw | 일반 discard는 hand의 비-Intrigue 카드를 뜻한다. deck이 빈 상태에서 draw하면 discard pile을 섞고 계속 draw한다. [Main p. 20] | [uprising-systems.md](uprising-systems.md) |
| Fremen Bond / In Play | 다른 Fremen card가 in play일 때 Bond를 쓸 수 있고, Bond 카드 둘은 play 순서와 무관하게 서로를 활성화한다. Agent와 Reveal 카드는 Clean Up 전까지 in play다. [Main p. 20] | [uprising-systems.md](uprising-systems.md), [player-turns.md](player-turns.md) |
| Influence | 수치가 붙은 Influence 조건은 해당 Faction의 현재 수치를 검사한다. 임의 Faction에 Influence 2를 주는 일반 효과는 두 Faction으로 나누지 않는다. [Main p. 20] | [uprising-systems.md](uprising-systems.md) |
| Maker / Maker Hooks | Agent가 없는 Maker 공간은 Makers phase에 bonus spice 1개를 얻고, 방문자는 쌓인 bonus를 모두 가져간다. Maker Hooks는 이미 가진 플레이어에게 중복 지급하지 않는다. [Main p. 20] | [uprising-systems.md](uprising-systems.md) |
| Paying a cost | arrow 비용을 내지 않으면 효과를 얻지 못하며 같은 비용-효과는 turn당 한 번이다. sandworm으로 Conflict reward를 배가할 때는 별도 예외가 있다. [Main p. 20] | [uprising-systems.md](uprising-systems.md), [combat-and-round-end.md](combat-and-round-end.md) |
| Recall Agent | 방금 보낸 Agent가 아닌 board의 다른 자기 Agent를 Leader로 돌리고, 같은 라운드의 이후 Agent turn에 다시 사용할 수 있다. [Main p. 20] | [uprising-systems.md](uprising-systems.md) |
| Resources | Solari, spice, water의 gain과 payment는 bank와 플레이어 사이의 이동이다. [Main p. 20] | [setup-and-game-flow.md](setup-and-game-flow.md) |
| Retreat | retreat한 troop은 Conflict에서 garrison으로 이동한다. [Main p. 20] | [uprising-systems.md](uprising-systems.md) |
| Sandworm / Shield Wall | 보호 중인 현재 Conflict에서는 sandworm 효과가 아무 일도 하지 않는다. 그 외에는 bank의 sandworm을 즉시 Conflict에 deploy한다. Shield Wall 제거 아이콘은 token을 제거할 수 있게 한다. [Main p. 20] | [uprising-systems.md](uprising-systems.md) |
| Spy | Spy는 비어 있는 observation post에 놓는다. supply에 Spy가 없으면 기존 자기 Spy 하나를 효과 없이 먼저 recall할 수 있다. [Main p. 20] | [uprising-systems.md](uprising-systems.md) |
| Steal Intrigue | Intrigue가 4장 이상인 각 opponent에게서 무작위 1장을 받는다. 이 효과는 선택이 아니라 대상별 random outcome을 만든다. [Main p. 20] | [uprising-systems.md](uprising-systems.md), [board-spaces.md](board-spaces.md) |
| Trash | 일반 카드는 hand, discard pile, in play에서 trash할 수 있다. 일반 카드는 box로, Reserve 카드는 원래 Reserve stack으로 돌아간다. 비용이나 자기-trash 지시가 아니면 trash 아이콘은 선택이다. [Main p. 20] | [uprising-systems.md](uprising-systems.md) |
| Troop | recruit한 troop은 supply에서 garrison으로 간다. Combat space에 Agent를 보내며 recruit했다면 Conflict에 deploy할 수 있다. [Main p. 20] | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| Victory Point | VP를 얻거나 잃을 때 Score marker를 같은 수만큼 이동한다. [Main p. 20] | [setup-and-game-flow.md](setup-and-game-flow.md) |

## 3. Main p. 17 Uprising clarification 전부

이 절은 Main p. 17의 clarification 다섯 항목을 빠짐없이 색인한다. 실제 기본
룰셋에 어느 카드·Leader를 활성화할지는 content manifest와 ruleset 설정이
결정하되, 활성화된 구성물에는 아래 판정을 적용한다.

| 대상 | 공식 판정 | 반영 위치 |
| --- | --- | --- |
| Feyd-Rautha Harkonnen | setup 때 Feyd token을 Leader의 Training track 맨 왼쪽에 둔다. 맨 오른쪽에 도달한 뒤에는 그 위치에 계속 둔다. [Main p. 17] | content manifest와 Leader scenario test |
| Lady Jessica | setup은 Reverend Mother Jessica가 아니라 Lady Jessica 면으로 시작한다. [Main p. 17] | content manifest와 Leader state-transition test |
| Lady Margot Fenring / Princess Irulan | 한 번에 여러 Influence를 얻어 2를 지나쳐도 `reach 2`다. Influence를 잃은 뒤 다시 올리면 같은 Faction에서 다시 2에 도달할 수 있고, 내려가는 중에는 `reach`가 발생하지 않는다. [Main p. 17] | [uprising-systems.md](uprising-systems.md)와 두 Leader scenario test |
| Shaddam Corrino IV | Signet Ring을 play해 Agent를 보낼 때 `Emperor of the Known Universe`의 unit deploy 제한은 즉시 적용된다. [Main p. 17] | content manifest와 Leader scenario test |
| Spacing Guild’s Favor | Clean Up으로 in-play 카드가 discard pile로 이동하는 것은 이 카드의 discard 능력을 발동하지 않는다. hand에서 discard될 때만 발동한다. [Main p. 17] | [player-turns.md](player-turns.md)의 zone-move reason과 card scenario test |

## 4. FAQ named-card 판정의 소속 게이트

### 현재 바로 활성화한 named-card FAQ entry

| FAQ entry | 공식적으로 확인된 소속 | 판정 | 반영 위치 |
| --- | --- | --- | --- |
| The Spice Must Flow | Uprising 기본 Reserve card. `[Main p. 3]` | acquire할 때 얻은 VP는 card를 나중에 trash해도 유지한다. `[FAQ p. 4]` | [player-turns.md](player-turns.md); card 수치와 test는 content manifest |
| Reverend Mother Jessica | Uprising 기본 Leader인 Lady Jessica의 반대 면. module 전용 Leader는 Shaddam이다. `[Main pp. 4, 16-17]` | 이 면으로 flip한 바로 그 turn에 Reverend Mother 능력을 사용할 수 있다. `[FAQ p. 3]` | Leader content manifest와 state-transition test |
| Shaddam Corrino IV | CHOAM Module 전용 Leader. `[Main pp. 4, 16]` | Sardaukar contract는 처음부터 보유하지 않으며 일반 contract 대신 set-aside contract를 얻는 선택지다. `Emperor of the Known Universe`는 발동한 turn에만 적용된다. `[FAQ p. 3]` | [choam-module.md](choam-module.md)와 Leader content manifest |

### content manifest 전사 시 확인: Uprising 연결은 명시됨

아래 FAQ entry는 FAQ가 Uprising card라고 직접 말하지만, 지정된 근거만으로
기본 룰셋과 CHOAM Module 사이의 소속까지 확정되지 않는다. content manifest
확인 전에는 활성 규칙으로 등록하지 않는다.

| FAQ entry | 확인 가능한 범위 | 판정 | 상태 |
| --- | --- | --- | --- |
| Manipulate | FAQ가 이 이름의 Intrigue card를 Uprising card라고 직접 설명한다. [FAQ p. 3] | 제거한 Imperium Row 카드는 opponent가 acquire할 수 없다. 자신은 다른 효과로 얻을 수 있지만 1 Persuasion 할인은 받지 못하며, 다음 Reveal turn 끝까지 얻지 않으면 게임에서 제거한다. [FAQ p. 3] | 기본 룰셋 카드로 구현; [intrigue audit](../implementation-audits/intrigue.md) |

### content manifest 전사 시 확인: 소속 자체가 미확정

다음 named-card/Leader entry는 FAQ에 판정이 있지만, 지정된 공식 텍스트만으로는
Uprising 기본 룰셋 소속을 확정할 수 없다. 따라서 현재 규범 규칙이나 테스트에
효과를 복사하지 않고, content manifest가 공식 카드 목록을 확정할 때 다시
분류한다.

- FAQ p. 1: Missionaria Protectiva, Archduke Armand Ecaz,
  Assassination Mission, Baron Vladimir Harkonnen, Beguiling Pheromones,
  Carryall, Chairdog, Chani (Imperium), Chani (Leader), Charisma,
  Chaumurky. [FAQ p. 1]
- FAQ p. 2: Corner the Market, Count Ilban Richese,
  Countess Ariana Thorvald, Demand Respect, Dispatch an Envoy, Double Cross,
  False Orders, Foldspace, Ghola, Guild Bankers, Guild Envoy, Gun Thopter,
  Helena Richese, Ilesa Ecaz, Imperial Spy, Liet Kynes, Litany Against Fear.
  [FAQ p. 2]
- FAQ p. 3: Plans Within Plans, Poison Snooper, “Princess” Yuna Moritani,
  Rapid Mobilization, Recruitment Mission, Refocus, Reverend Mother Mohiam.
  [FAQ p. 3]
- FAQ p. 4: Shifting Allegiances, Sort Through the Chaos, Spaceport,
  Staged Incident, Test of Humanity, To the Victor… .
  [FAQ p. 4]

목록에 있다는 사실은 해당 항목이 Uprising에 속하거나 속하지 않는다는 판정이
아니다. 오직 현재 허용된 근거만으로 소속을 확정하지 않았다는 뜻이다.

## 5. 제외 원칙

- Rise of Ix rulebook errata와 Rise of Ix infiltration icon 판정은 현재 4인
  Uprising 기본 룰셋에 반영하지 않는다. [FAQ p. 1] [FAQ p. 2]
- dreadnought 관련 보강은 FAQ가 Rise of Ix unit이라고 명시하므로 제외한다.
  [FAQ p. 2]
- Rivals, Solo Play, House Hagal, 1·2인 setup 판정은 현재 4인 게임에 반영하지
  않는다. [FAQ p. 1] [FAQ p. 3] [FAQ p. 4]
- FAQ entry 안의 6인 전용 문장은 같은 entry의 4인 적용 부분과 분리해 제외한다.
  [FAQ p. 3]
- Tech tile과 Tleilaxu track처럼 현재 기본 ruleset에 없는 확장 시스템은 이
  색인에서 실행 규칙으로 승격하지 않는다. named entry의 소속이 불명확하면
  확장 소속이라고 추정하지 않고 앞의 content-manifest 확인 목록에 유지한다.
  [FAQ p. 2] [FAQ p. 3] [FAQ p. 4]
