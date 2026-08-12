# Combat and Round End

이 문서는 **Dune: Imperium — Uprising 기본 4인 게임**의 Combat부터 Endgame까지를 구현하기 위한 규칙 메모다. 규칙은 지정된 메인 룰북 텍스트와 2025-01-13 FAQ 텍스트만 간결하게 옮겼다.

## 1. Combat 시작과 strength

- 모든 플레이어가 Reveal turn을 마치면 Player Turns 단계가 끝나고, 라운드 순서에 따라 Phase 3: Combat가 시작된다. [Main p. 8]
- 플레이어는 Reveal turn의 Reveal 효과를 처리하는 동안 원하는 시점에 strength를 정하고, 이후 변화가 생기면 갱신한다. 이는 Reveal 효과와 Clean Up 사이의 별도 단계가 아니다. [Main p. 12] [Main p. 13]
- Conflict의 troop 하나는 strength 2, sandworm 하나는 strength 3을 제공한다. garrison이나 supply의 유닛은 strength를 제공하지 않으며, 이번 Reveal turn에 공개한 sword 하나는 strength 1을 제공한다. [Main p. 12]
- Conflict에 유닛이 하나도 없으면 sword가 있어도 strength는 0이다. 마지막 유닛이 제거되는 즉시 strength도 0이 된다. [Main p. 12]
- strength를 공개하고 Combat marker를 Combat track의 해당 칸으로 옮긴다. 20을 넘으면 marker의 `+20` 면을 사용해 track 처음부터 남은 수치를 센다. [Main p. 12]

## 2. Combat Intrigue 우선권과 pass

- First Player marker를 가진 플레이어부터 시계 방향으로, 현재 Conflict에 유닛이 하나 이상 있는 플레이어만 Combat Intrigue 기회를 갖는다. 해당 플레이어는 Combat Intrigue 카드를 원하는 수만큼 플레이하거나 pass한다. [Main p. 14]
- 앞선 기회에 pass했어도 Combat 단계에서 탈락하지 않는다. 전투 참여자 전원이 **연속으로** pass했을 때만 카드 플레이 절차를 끝내고 Combat를 해결한다. [Main p. 14]
- Combat Intrigue가 유닛 수나 strength를 바꾸면 즉시 Combat marker를 갱신한다. 효과가 strength를 낮추는 경우도 marker를 아래로 옮긴다. [Main p. 14] [FAQ p. 4]
- Intrigue 카드는 명시된 조건을 만족하고 비용을 지불해야 플레이할 수 있다. [FAQ p. 2]
- “When you win a Conflict” Combat Intrigue는 공동 1위로 비긴 경우 플레이할 수 없다. Conflict 승리 보상으로 그런 Intrigue를 새로 뽑았다면 즉시 플레이할 수 있다. [FAQ p. 4]

## 3. 4인 순위와 보상

- strength가 가장 높은 플레이어가 Conflict를 이기고 1위 보상을 받는다. 두 번째로 높은 플레이어는 2위 보상, 세 번째로 높은 플레이어는 3위 보상을 받으며, 4위는 보상이 없다. [Main p. 14]
- strength가 0인 플레이어는 어떤 순위 보상도 받지 못한다. [Main p. 14]
- 모든 순위 보상을 처리한 뒤, 승자는 Conflict 카드를 face-up 상태로 자신의 supply에 놓고 battle icon 일치를 확인한다. [Main p. 14]

### Combat 동률

- 두 명 이상이 1위로 동률이면 동률자 모두 2위 보상을 받는다. 이 경우 1위 보상은 지급되지 않고, 아무도 Conflict의 승자가 아니며, 아무도 Conflict 카드를 가져가지 않는다. [Main p. 14]
- 4인 게임에서 정확히 두 명이 1위로 동률이면 나머지 두 명이 3위 보상을 두고 경쟁한다. 둘 중 strength가 더 높은 플레이어가 3위 보상을 받고, 둘도 동률이면 3위 동률 규칙에 따라 아무도 받지 못한다. 단, strength 0인 플레이어는 보상을 받을 수 없다. [Main p. 14]
- 4인 게임에서 세 명 또는 네 명이 1위로 동률이면 그 동률자들이 각자 2위 보상을 받은 뒤 다른 보상은 지급하지 않는다. [Main p. 14]
- 두 명 이상이 2위로 동률이면 동률자 모두 3위 보상을 받는다. 1위 플레이어의 보상과 승리 및 Conflict 카드 획득은 유지되며, 그 뒤의 보상은 지급하지 않는다. [Main p. 14]
- 두 명 이상이 3위로 동률이면 동률자 모두 보상을 받지 못한다. [Main p. 14]

## 4. Sandworm 보상 두 배

- 보상을 받을 때 자신의 sandworm이 Conflict에 하나 이상 있으면 자신이 받는 보상을 두 배로 한다. sandworm 수가 둘 이상이어도 두 배보다 더 커지지 않는다. [Main p. 14]
- location의 control 획득과 승리한 Conflict 카드의 battle icon은 두 배가 되지 않는다. 따라서 control marker는 한 번만 배치하고, battle icon도 한 장에 인쇄된 그대로 처리한다. [Main p. 14]
- 보상에 “비용을 내고 효과를 얻기” 선택지가 있으면, 두 번째 효과를 얻기 위해 비용도 두 번째로 낼 수 있다. 한 번의 비용으로 효과만 자동으로 두 배가 되는 것은 아니다. [Main p. 14]
- reward의 Influence 1을 두 배로 받는 경우 두 번의 Influence를 같은 Faction에
  주거나 서로 다른 두 Faction에 하나씩 줄 수 있다. 이는 일반적인 `gain 2
  Influence`가 한 Faction을 고르는 규칙과 달리, reward를 두 번 받는 처리다.
  [Main p. 14] [Main p. 20]

## 5. Conflict 카드, control, battle icon

- 각 라운드 시작에 Conflict Deck 맨 위 카드를 공개해 deck 옆에 face-up으로 놓는다. 이전 라운드 카드가 남아 있다면 그 위에 놓는다. [Main p. 8]
- Arrakeen, Spice Refinery, Imperial Basin을 대상으로 하는 Conflict에서 승리해 control 보상을 받으면 해당 위치 아래 깃발에 자신의 Control marker를 놓으며, 기존 상대 marker가 있다면 교체한다. [Main p. 10] [Main p. 20]
- 자신이 Arrakeen 또는 Spice Refinery를 control하는 동안 어떤 플레이어든 그 공간에 Agent를 보내면 controller가 1 Solari를 받는다. Imperial Basin의 같은 보너스는 spice 1이다. [Main p. 10]
- 자신이 이미 control하는 위치의 Conflict 카드가 공개되면, 자신의 supply에서 troop 하나를 Conflict에 배치할 수 있다. 이 방어 배치는 선택 사항이다. [Main p. 10] [Main p. 20]
- battle icon은 Crysknife, Desert Mouse, Ornithopter 세 종류다. Conflict 승자가 새 카드를 supply에 가져왔을 때, supply의 다른 face-up Conflict 또는 Objective 카드에 같은 icon이 있으면 그 두 장을 반드시 face-down으로 뒤집고 Victory Point 1을 얻는다. [Main p. 14]
- Endgame 중 wild battle icon은 supply에 있는 세 종류 중 하나의 battle icon과 짝지을 수 있다. 선택했다면 두 장을 face-down으로 뒤집고 Victory Point 1을 얻는다. [Main p. 20]
- 공동 1위로 승자가 없으면 누구도 현재 Conflict 카드를 가져가지 않는다. 그 카드는 board에 face-up으로 남고, 다음 Round Start의 Conflict는 이전 카드 위에 놓인다. [Main pp. 8, 14]

## 6. Combat 정리

- 모든 보상 지급 후 각 troop을 Conflict에서 소유자의 supply로 돌려보낸다. garrison으로 돌려보내지 않는다. 모든 Combat marker는 0으로 되돌리고, 모든 sandworm은 bank로 돌려보낸다. [Main p. 14]

### Retreat

- Retreat는 troop을 Conflict에서 자기 garrison으로 옮긴다. 효과가 `any number`의
  troop을 Retreat하게 하면 0개도 선택할 수 있다. [Main p. 20] [FAQ p. 3]

## 7. Phase 4: Makers

- 4인 게임에서는 Deep Desert, Hagga Basin, Imperial Basin을 확인한다. Agent가 없는 각 Maker 공간에 bank의 spice 1을 bonus spice 위치에 놓으며, 기존 bonus spice가 있으면 누적한다. [Main p. 15]
- Maker 공간에 Agent를 보낼 때 그 공간에 누적된 bonus spice를 모두 얻는다. [Main p. 20]

## 8. Phase 5: Recall과 Endgame 진입

- 플레이어 중 누구라도 Score track에서 Victory Point 10 이상이거나 Conflict Deck이 비어 있으면 Endgame을 시작한다. 이 조건은 즉시 승자를 정하는 조건이 아니라 Endgame을 여는 조건이다. [Main p. 15]
- Endgame 조건이 충족되면 다음 라운드를 준비하는 Agent recall과 First Player marker 전달을 하지 않고 Endgame으로 진행한다. [Main p. 15]
- Endgame이 시작되지 않으면 모든 플레이어는 board의 Agent를 자신의 Leader로 돌려보내고, First Player marker를 시계 방향의 다음 플레이어에게 넘긴 뒤 Phase 1부터 새 라운드를 시작한다. [Main p. 15]

## 9. Endgame, Endgame Intrigue, 최종 동률

- Endgame Intrigue 카드는 게임 종료 시점에만 플레이할 수 있다. Endgame에 들어가면 먼저 각자 가진 Endgame Intrigue를 원하는 만큼 플레이하고 해결한 뒤 최종 Victory Point를 비교한다. [Main p. 7] [Main p. 15]
- 최종 Victory Point가 가장 높은 플레이어가 승리한다. [Main p. 15]
- 같은 Victory Point인 플레이어 사이의 기본 tiebreaker는 spice 수, Solari 수, water 수, garrison의 troop 수 순서다. 앞 항목으로 풀리지 않을 때만 다음 항목을 비교한다. [Main p. 15]
- 위 tiebreaker로도 동률이면 가장 최근에 Reveal turn을 수행한 플레이어가 최종 승자다. [FAQ p. 2]

## 미확정 항목

- 같은 순위에 묶인 여러 플레이어가 동일한 보상을 실제로 해결하는 플레이어 순서는 두 출처에 명시되어 있지 않다. 상호작용하는 보상을 모델링하기 전 별도의 판정 정책이 필요하다. [Main p. 14]
- Combat Intrigue로 어떤 플레이어의 유닛 수가 0에서 1 이상 또는 1 이상에서 0으로 바뀔 때, 진행 중인 우선권 순환에 그 플레이어를 정확히 언제 추가하거나 제외하는지는 명시되어 있지 않다. [Main p. 14]
- Endgame Intrigue를 플레이하는 플레이어 순서, 한 플레이어가 pass한 뒤 다시 기회를 얻는지, 그리고 Endgame wild battle icon 처리를 Endgame Intrigue 전후 어느 시점에 하는지는 명시되어 있지 않다. [Main p. 15] [Main p. 20]
- 새 Conflict 카드와 일치하는 face-up 카드가 여러 장일 때 어느 한 장을 짝으로 선택하는지는 명시되어 있지 않다. [Main p. 14] [Main p. 20]
