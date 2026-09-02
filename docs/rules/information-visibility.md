# 공개·비공개 정보

이 문서는 공식 규칙이 구성물을 face-up/face-down 또는 공개한다고 명시한 범위만 기록한다. 규칙서가 명시하지 않은 정보 정책은 관행으로 채우지 않고 끝의 미확정 항목에 남긴다.

## 명시적인 face-up 상태와 공개 배치

- Leader는 각 플레이어 앞에 놓는다. Main은 이 placement를 지시하지만 이 문장에서 별도로 `face-up`이라는 단어를 쓰지는 않는다. Objective는 무작위로 받은 뒤 자신의 supply에 face-up으로 둔다. `[Main pp. 4-5]`
- 각 플레이어의 남은 개인 구성물은 다른 모든 플레이어가 명확히 볼 수 있는 supply에 둔다. 여기에는 board나 Leader 위에 놓지 않은 token과 piece가 포함된다. `[Main p. 5]`
- Imperium Row의 카드 5장은 face-up이다. 카드를 acquire해 빈자리가 생기면 Imperium Deck 위 카드로 즉시 face-up 보충한다. `[Main pp. 4, 13]`
- 현재 Conflict는 Round Start에 face-up으로 공개한다. 승자가 가져간 Conflict와 플레이어가 받은 Objective도 battle icon matching으로 뒤집히기 전에는 supply에 face-up으로 있다. matching하지 않은 카드는 face-up 상태를 유지한다. `[Main pp. 5, 8, 14]`
- acquire한 Imperium/Reserve 카드는 자신의 discard pile에 face-up으로 놓는다. `[Main p. 13]`
- 해결한 Intrigue는 Intrigue Deck 옆의 face-up discard pile에 놓는다. `[Main p. 7]`
- Agent turn에 play한 카드와 Reveal turn에 reveal한 카드는 Clean Up 전까지 face-up in play다. `[Main pp. 9, 12, 20]`
- CHOAM Module의 시장 contract 2개와 플레이어가 아직 완료하지 않은 contract는 face-up이다. contract를 완료할 때 완료 사실과 reward를 알린 뒤 그 contract를 face-down으로 뒤집는다. `[Main p. 16]`

## 명시적으로 face-down 또는 보지 않는 정보

- Intrigue Deck과 Imperium Deck은 setup 때 shuffle한 뒤 face-down으로 둔다. `[Main p. 4]`
- 개인 starting deck은 shuffle한 뒤 face-down으로 둔다. deck이 비어 discard를 새 deck으로 만들 때도 shuffle한다. `[Main pp. 5-6]`
- Conflict Deck은 tier별로 shuffle하고 face-down으로 쌓는다. 사용하지 않는 Conflict 카드는 정체를 보지 않고 box로 돌려보낸다. `[Main p. 4]`
- 보유한 Intrigue card는 개인 deck과 분리해 face-down으로 둔다. 소유자는 언제든 볼 수 있지만 opponent에게는 play할 때만 공개한다. `[Main p. 7]`
- CHOAM Module의 미공개 contract 18개는 face-down bank에 둔다. 완료된 contract도 reward를 받은 뒤 face-down으로 유지한다. `[Main p. 16]`
- battle icon pair를 만들면 해당 두 face-up Conflict/Objective를 face-down으로 뒤집는다. `[Main pp. 14, 20]`

## 무작위 선택과 공개 여부

- 4인용으로 거른 Objective를 shuffle하고 각 플레이어에게 무작위로 하나씩 준 뒤 face-up으로 공개한다. `[Main p. 5]`
- Secrets의 무작위 Intrigue 이전처럼 effect가 `selected at random`이라고 명시하면 대상 card identity는 선택권자가 고르지 않고 무작위로 정한다. 이 표현만으로 card identity가 모든 opponent에게 공개되지는 않는다. Intrigue는 play할 때까지 opponent에게 공개하지 않는 일반 규칙을 따른다. `[Main p. 7]` `[Board Guide p. 2]`

## 공식 문서가 명시하지 않은 정보 정책

다음은 확인한 공식 문서에서 완전한 정책을 찾지 못했다. [OQ-010](open-questions.md#oq-010--손패discard와-과거-공개-정보의-열람-범위)이 "한 번 공개된 정보는 재확인 가능해야 한다"는 원칙으로 확정했다(2026-09-02, 사용자 판정; 공식 규칙이 아닌 프로젝트 convention). 현행 관측 v3 경계는 다음과 같다.

- 일반 hand의 identity는 소유자만 보고, 장수는 전원에게 공개한다. 단, 공개 경로로 hand에 들어온 카드(Corrinth City의 acquire-to-hand, Intrigue의 "put that card in your hand", Bond로 in play에서 돌아온 카드)는 hand를 떠날 때까지 전원이 identity를 본다(`hand_public`).
- face-up 개인 discard pile의 identity와 장수는 전원에게 공개한다(모든 카드가 face-up으로 들어오므로). reshuffle로 deck이 되는 순간 다시 비공개다.
- 개인 deck과 공용 deck·bank의 남은 장수는 언제나 공개한다. 개인 deck의 순서와 구성은 소유자에게도 노출하지 않는다.
- 보유 Intrigue의 identity는 소유자만 본다 `[Main p. 7]`. play돼 선택 해결 중인 Intrigue는 이미 공개됐으므로 전원이 본다(`intrigue_resolving`).
- matched Conflict/Objective의 identity는 뒤집힌 뒤에도 공개를 유지하고, completed contract도 identity를 공개한다(완료 사실이 공지됐으므로).
- 실시간 행동 로그는 엔진 이벤트를 `visible_to`로 걸러 보여 준다. 공개 이벤트는 그 직후 공개 존에 있는 카드만 이름을 담는다(sweep 불변식으로 검사).
- 게임 종료 후에는 모든 비공개 존(각 좌석의 hand·deck 순서·보유 Intrigue, 공용 deck·bank 순서)을 공개하고, 검토는 모든 좌석 시점과 모든 행동·chance 값을 보여 준다. 이는 재확인 원칙이 아니라 검토 편의 convention이다.
