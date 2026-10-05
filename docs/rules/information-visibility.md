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
- Bloodlines Coercive Negotiation의 "Reveal three contracts from the bank. Take one and trash the other two." `[Coercive Negotiation card]`로 공개한 contract는 모든 좌석에게 보인다 — 규칙서의 reveal은 opponent에게 보여 주는 것이다("Reveal them to your opponents only when you play them" `[Main p. 7]`, Conflict card를 "revealing ... Place it face up" `[Main p. 8]`). 소유자가 가져갈 수 없는 것(Intrigue 없이 Immediate `[Bloodlines p. 2]`)도 공개된 셋에 든다. 선택하는 동안 bank 위에 그대로 있고(관측 `revealed_contract_ids`, 인코딩 밖), 가져가지 않은 둘은 공개 zone `contract_trash`로 간다. 2026-09-26 전에는 소유자만 아는 것으로 다뤘다.

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
- 개인 deck과 공용 deck·bank의 남은 장수는 언제나 공개한다. 개인 deck의 **순서**는 소유자를 포함해 누구에게도 노출하지 않는다. 개인 deck의 **구성**(어떤 카드가 몇 장 들었는가)은 소유자에게만, 이름순으로 정렬해 순서가 묻어나지 않게 보여 준다(서버 view의 `private.deck_cards`와 UI의 "내 카드덱" 목록; 관측·인코딩 밖). 사용자 결정(2026-10-05)으로, OQ-010의 재확인 원칙을 적용한 프로젝트 convention이며 공식 규칙이 아니다. 근거: 개인 deck에 카드가 들어오는 모든 경로가 소유자가 보는 존을 거친다 — setup의 starting deck과 draw `[Main pp. 5-6]`, 다시 섞이는 자신의 face-up discard pile `[Main pp. 5-6, 13]`, 소유자가 고른 Tleilaxu 카드를 deck 맨 위에 두는 경우 `[Immortality pp. 6, 16]` — deck에서 나가는 경로(draw, 효과로 본 뒤의 trash·discard)도 마찬가지다. 그래서 구성은 소유자가 이미 추론할 수 있고 보여 줘도 새 정보가 아니다. 상대에게는 구성도 보이지 않는다(소유자의 hand를 모르므로 추론할 수 없다).
- 보유 Intrigue의 identity는 소유자만 본다 `[Main p. 7]`. play돼 선택 해결 중인 Intrigue는 이미 공개됐으므로 전원이 본다(`intrigue_resolving`).
- matched Conflict/Objective의 identity는 뒤집힌 뒤에도 공개를 유지하고, completed contract도 identity를 공개한다(완료 사실이 공지됐으므로).
- 실시간 행동 로그는 엔진 이벤트를 `visible_to`로 걸러 보여 준다. 공개 이벤트는 그 직후 공개 존에 있는 카드만 이름을 담는다(sweep 불변식으로 검사).
- 게임 종료 후에는 모든 비공개 존(각 좌석의 hand·deck 순서·보유 Intrigue, 공용 deck·bank 순서)을 공개하고, 검토는 모든 좌석 시점과 모든 행동·chance 값을 보여 준다. 이는 재확인 원칙이 아니라 검토 편의 convention이다.

## Arrakeen Scouts (`arrakeen_scouts` 옵션)

앱은 공개·비공개를 규칙으로 적지 않고 화면으로만 다룬다(비밀 선택 화면은 다음 좌석으로 넘어가면 표시를 지우고, 입찰은 전원 확정 뒤 한꺼번에 공개한다 `[Scouts help]` `[Scouts schedule]`). 엔진은 다음 경계를 쓴다(설계 [arrakeen-scouts-design.md](../arrakeen-scouts-design.md) 4.8절). 모두 project convention이다.

- **일정.** 아직 공개되지 않은 라운드의 항목은 상태에 없다(공개되는 라운드에 chance로 뽑는다). 공개된 소위원회·임무·이벤트·경매·판매와 가입 좌석, 이번 라운드 규칙 변경은 전원에게 공개다.
- **비밀 선택**(Covert Operation, Offworld Operation). 고른 좌석만 자기 선택을 본다. 다른 좌석은 "누가 이미 골랐는가"만 본다. 공개 라운드의 Scouts 단계 맨 앞에서 전원에게 공개한다. 기한 전에 게임이 끝나 사라진 선택은 종료 후 공개 패널에서 보인다.
  - 다음 라운드에 공개되지 않고 남은 선택은 두 라운드짜리 두 줄 가운데 하나임이 드러난다(탐색 AI의 재추첨과 비공개 검사도 그 둘 중에서만 바꾼다).
  - 구현(슬라이스 7): 선택은 좌석 한정 id(`secret_pick_id`)로 `known_card_seats`에 들어가므로 공개 단계는 되돌릴 수 없는 공개가 되고(행위자 자신의 선택만 공개되어도 그렇다: 규칙이 공개하는 것이지 행위자가 내보이는 것이 아니며, 예외를 두면 그 단계의 되돌리기 가능 여부가 상대의 기한 선택 유무를 알려 준다 — 2026-09-28 독립 리뷰 적발), 선택 자체는 다음 좌석이 행동하기 전까지 되돌릴 수 있다. 행동은 `scouts_secret_pick(pick)` 하나이고 네 값이 늘 모두 제시된다. 서버 로그는 이 행동의 인자를 게임이 끝날 때까지 다른 좌석에게 가리고(`SEALED_ACTION_IDS`), 행동 목록의 미리보기를 싣지 않는다(기한 선택의 공개로 이어지는 행동도 마찬가지: Control 방어, 다음 라운드가 chance 없이 열리는 라운드의 마지막 행동). 공개 이벤트 `scouts_secret_picked`는 좌석과 이벤트만 싣는다(소크의 이벤트 검사가 확인한다).
- **봉인 입찰**(경매의 봉인 판, Mercenaries). 입찰한 좌석만 자기 입찰액을 본다. 다른 좌석은 확정 여부만 본다. 입찰 범위는 자기 자원만으로 정해지고, 지불은 공개 때 한다(확정 때 줄어든 자원이 입찰을 드러내지 않도록). 전원이 확정한 뒤 한꺼번에 공개한다. 공개는 되돌릴 수 없다.
  - 구현(슬라이스 8): 비밀 선택과 같은 장치다. 입찰액은 좌석 한정 id(`secret_bid_id`)로 등록부에 있고, 로그는 `scouts_bid`의 인자를 가리며, 마지막 확정(공개)으로 이어지는 행동의 미리보기는 비운다.
- **공개 경매**(Critical Moment). 공개한 Imperium 덱 카드와 부른 액수는 전원에게 공개다.
- **칸 위의 뒷면 카드**(CHOAM Research의 Contract 2장, Emperor's Schemes의 Intrigue 2장). 가져가기 전까지 누구도 모른다. 가져간 좌석은 자기 카드로 보며, Contract는 가져가면 앞면 Contract가 되어 공개다(`[Main p. 16]`).
