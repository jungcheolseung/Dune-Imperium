# 공식 문서만으로 확정할 수 없는 항목

이 목록은 규칙을 임의로 메우지 않기 위한 판정 대장이다. 아래 항목은 현재 확인한 Main Rulebook, Board Space Guide, 2025-01-13 FAQ에 명시적 답이 없거나, 구현에 필요한 정도로 순서가 정해져 있지 않다. 각 항목은 공식 근거가 나타나기 전까지 프로젝트가 어떤 판정을 채택했는지, 또는 아직 판정하지 않았는지를 기록한다.

상태 값은 다음과 같다.

- `OPEN`: 공식 판정이 더 필요하고 프로젝트 확정도 내리지 않았다.
- `CONTENT`: 실제 card/Leader 텍스트 전사 뒤 질문 자체가 성립하는지 재검토한다.
- `ARTWORK`: 공식 board/card artwork에서 전사·교차 검증해야 한다.
- `DECIDED`: 공식 문서가 침묵함을 확인한 뒤 프로젝트가 확정한 판정. 구현과 테스트가 이 판정을 따르며, 새 공식 룰북·FAQ·판정이 답을 주기 전까지 재검토하지 않는다. 답이 나오면 그 시점에 판정과 대조해 `RESOLVED`로 전환하거나 구현을 수정한다.
- `RESOLVED`: 공식 근거 또는 콘텐츠 분석으로 질문 자체가 닫혔다.

번호는 외부 링크의 안정성을 위해 재사용하지 않는다. 해결된 항목은 짧은 `RESOLVED` tombstone을 남기고 결과 문서로 연결한다.

**2026-09-01 확정 캠페인**: 공식 리소스 페이지를 재확인해 Uprising Main Rulebook·Rules Supplements 23-10-12판과 FAQ 2025-01-13판이 여전히 최신임을 확정한 뒤, 남아 있던 `OPEN`/`CONTENT` 19건 전부에 확정 판정을 내렸다. `DECIDED` 판정은 프로젝트의 최종 판정이며 "공식 답변 대기" 상태가 아니고, 새 공식 문서가 발표될 때만 해당 항목을 다시 연다. 같은 날 사용자 검토로 세 항목을 갱신했다: OQ-022는 디자이너 판정을 찾아 반대 방향으로 확정, OQ-023은 사용자 재판정으로 교체, OQ-010은 방향만 확정한 `OPEN`으로 되돌렸다가 2026-09-02에 사용자 판정 4건(상대 discard·완료 contract identity 공개, 실시간 로그 기준, 종료 후 전체 공개)으로 `DECIDED`했다.

## OQ-001 — Endgame 처리 순서와 priority

- 상태: `DECIDED`
- 공식 문서는 Endgame Intrigue를 먼저 play/resolve한 뒤 승자를 정하고, Endgame에 wild battle icon을 한 쌍 matching할 수 있다고 말한다. 그러나 어느 플레이어부터 Intrigue를 내는지, pass 뒤 다시 기회를 얻는지, wild matching을 Intrigue 전·중·후 언제 하는지는 설명하지 않는다. `[Main pp. 15, 20]`
- 필요한 답: Endgame decision window의 참가 순서, 종료 조건, wild matching window.
- 구현 convention(2026-08-29): First Player부터 시계 방향으로 각 플레이어가 Endgame window를 한 번씩 가진다. 자신의 window에서 Endgame Intrigue play와 wild battle icon matching을 원하는 만큼 자유로운 순서로 해결하고, pass하면 그 플레이어의 window는 다시 열리지 않는다. 아무도 Intrigue를 갖고 있지 않고 wild 쌍도 없으면 window 없이 즉시 종료한다. 순서가 상태에 영향을 주는 공개 효과가 없으므로 단일 순회로 충분하다는 판단이며, `tests/unit/rules/test_endgame.py`와 `tests/unit/rules/test_intrigue.py`로 고정한다.
- 확정(2026-09-01): 위 convention을 최종 판정으로 채택한다. 완결된 Endgame Intrigue 6종(Crysknife, Desert Mouse, Ornithopter, CHOAM Profits, Secure Spice Trade, Shadow Alliance)을 전수 재검토한 결과 모든 효과가 소유자 자신의 VP·spice 획득이고, 어떤 Endgame 효과도 다른 window의 조건 입력(자신의 completed contract 수, 자신의 The Spice Must Flow 보유 수, opponent의 Alliance 보유 track 위치)을 바꾸지 못한다. 따라서 늦은 window의 play가 이미 pass한 플레이어의 결정을 무효화할 수 없고, 단일 순회 근거는 콘텐츠 완결 이후에도 유효하다.

## OQ-002 — 동률 Combat reward 해결 순서

- 상태: `DECIDED`
- 공식 문서는 각 동률자의 reward 종류는 정하지만, 같은 rank의 여러 플레이어가 선택을 포함한 reward를 어떤 순서로 resolve하는지는 정하지 않는다. `[Main p. 14]`
- 필요한 답: 실제 Conflict reward 전사 후 순서가 상태에 영향을 주는 사례가 있는지 확인하고, 있다면 공식 판정을 찾는다.
- 확정(2026-09-01): 전사된 Conflict 15종 전수 검산으로 닫는다. 동률 규칙상 여러 플레이어가 같은 보상 줄을 받는 경우는 항상 2위·3위 줄이며(1위 동률 → 전원 2위 보상, 2위 동률 → 전원 3위 보상 `[Main p. 14]`), 그 두 줄에 인쇄된 보상은 Solari·spice·water·troop·Intrigue draw·(Trade Dispute 2위 줄의) 선택형 trash뿐이다. Influence 선택, contract, Spy 배치, VP, 선택형 지불, control은 전부 1위 줄 전용이라 단독 승자만 받는다. 따라서 동률자 사이의 순서가 바꿀 수 있는 상태는 공유 Intrigue 덱의 배분(비공개 무작위)과 각자 자기 카드에만 작용하는 공개 trash 선택의 제시 순서뿐이고, 플레이어 선택이 상호작용하는 사례는 없다. 확정 convention: 동률 그룹은 First Player 위치와 무관하게 좌석 번호 오름차순으로 해결한다(구현 그대로). `tests/unit/rules/test_combat.py`의 tied-order 테스트 2건으로 고정한다. 상호작용하는 동률 보상이 새 콘텐츠로 추가되면 다시 연다.

## OQ-003 — Combat Intrigue 도중 참가 자격 변화

- 상태: `DECIDED`
- Combat 시작 규칙은 Conflict에 unit이 하나 이상 있는 플레이어만 priority를 받는다고 한다. 진행 중 카드로 한 플레이어의 unit 수가 0↔1 이상으로 바뀔 때 priority 순환에 언제 들어오거나 빠지는지는 설명하지 않는다. `[Main p. 14]`
- 필요한 답: 해당 변화를 만들 수 있는 현재 범위의 card가 있는지 콘텐츠 전사로 확인한 뒤, 실제 사례가 있으면 공식 판정을 찾는다.
- 현재 범위 확인 결과(2026-08-28): Combat Intrigue 가운데 unit을 **줄이는** 카드는 Go to Ground, Spice is Power, Tactical Option, Reach Agreement이고, Combat 중 unit을 **늘리는** 카드는 없다.
- 구현 convention: (a) 카드 효과로 마지막 unit이 Conflict를 떠난 참가자는 그 즉시 priority 순환에서 빠지며, 그 플레이어가 priority를 갖고 있었다면 시계 방향의 다음 남은 참가자에게 넘어간다. 남은 참가자가 없으면 Combat Intrigue 단계가 끝난다. (b) Combat 시작 시 unit이 없던 플레이어는 순환에 없고 이후에도 들어올 수 없다. `tests/unit/rules/test_intrigue.py`로 고정한다.
- 확정(2026-09-01): Intrigue 39개 identity 완결 전사에서 census를 재검산했다 — Combat timing 옵션 가운데 unit을 늘리는 효과는 여전히 없고 줄이는 카드는 위 4종(retreat 비용·보상)뿐이다. 따라서 순환 "진입"은 현재 콘텐츠에서 구조적으로 불가능하고, "퇴장"은 위 convention (a)(b)를 최종 판정으로 채택한다. Combat 중 unit을 늘리는 새 콘텐츠가 추가되면 다시 연다.
- 사용자 재확인(2026-09-01): unit이 배치되지 않은 플레이어는 Combat 단계 자체에 참가하지 않아 Combat Intrigue 기회를 받지 않고, 참가자도 unit 상실·retreat로 배치 unit이 없어지면 즉시 배제된다는 위 판정을 사용자가 그대로 확정했다.

## OQ-004 — Imperium Deck 완전 고갈

- 상태: `DECIDED`
- Imperium Row는 항상 5장이어야 하며 빈자리를 Imperium Deck 위에서 즉시 보충한다고 적혀 있지만, deck과 row가 함께 고갈되어 5장을 채울 수 없는 경우를 다루지 않는다. 개인 deck과 Intrigue deck의 reshuffle 규칙은 별도로 있지만 Imperium discard reshuffle 규칙은 제시되지 않는다. `[Main pp. 6, 13]`
- 필요한 답: row를 줄인 채 진행하는지 등 최신 공식 판정.
- 구현 convention(2026-08-30): 물리적으로 강제되는 유일한 진행을 따른다. Imperium Deck이 비면 Row의 빈자리는 보충하지 않고 Row는 남은 카드 수로 계속 운영하며, 어떤 카드도 Imperium Deck으로 되돌아가지 않는다(공유 Imperium discard 존과 reshuffle 규칙이 존재하지 않으므로). 획득·set-aside의 모든 Row 제거 지점이 `rules/acquisition.py`의 `take_imperium_row_card` 헬퍼를 공유한다. heuristic policy sweep이 실제로 이 상태에 도달함을 확인했다(룰셋당 1,000판 중 기본 룰셋 6판이 `NotImplementedError` tripwire에 걸렸다). 관측 인코딩의 row 세그먼트는 5 슬롯 고정이며 빈자리는 0으로 남는다. `tests/unit/rules/test_acquisition.py`와 `tests/unit/rules/test_intrigue.py`로 고정한다.
- 확정(2026-09-01): 위 convention을 최종 판정으로 채택한다. 공식 문서에 공유 Imperium discard 존도 reshuffle 규칙도 없다는 근거가 그대로이므로, 보충 없는 Row 축소 운영이 물리적으로 강제되는 유일한 진행이다.

## OQ-005 — 여러 matching battle icon 중 pair 선택

- 상태: `RESOLVED`
- Conflict 승자가 새 face-up icon과 같은 face-up Conflict/Objective를 이미 여러 장 가졌을 때 어떤 한 장과 pair를 만들지, 선택권이 있는지 명시하지 않는다. Endgame wild icon도 후보가 여러 개일 수 있다. `[Main pp. 14, 20]`
- 콘텐츠 전사 완료 후 검토(2026-08-30): Combat의 즉시 matching은 공식 콘텐츠에서 후보가 두 장 이상일 수 없다. setup은 플레이어당 Objective 한 장을 주고, 이후 face-up battle card 추가는 승리한 Conflict뿐인데 도착 즉시 의무 pair로 뒤집히므로 printed icon당 face-up은 최대 한 장이며, wild는 Propaganda 한 장뿐이다. Endgame wild는 후보가 여러 개일 수 있고 어느 쪽을 뒤집는지가 Endgame Intrigue flip 대상(승리한 Conflict 한정)에 실제로 영향을 주므로, OQ-001 window 안에서 소유자가 pair를 직접 고르는 행동으로 구현했다. 분석과 soak 근거는 [`../implementation-audits/objectives.md`](../implementation-audits/objectives.md)에 있으며, 엔진은 Combat 다중 후보를 미래 콘텐츠 대비 guard로 계속 차단한다.

## OQ-006 — 한 space에 여러 opponent Agent가 있을 때 Infiltrate

- 상태: `DECIDED`
- Spy 규칙은 `다른 플레이어`의 Agent가 있는 space에 연결된 Spy 하나를 recall해 그 Agent를 무시할 수 있다고 설명한다. 이미 Infiltrate가 반복되어 서로 다른 opponent Agent가 둘 이상 있는 space에 새로 들어갈 때 Spy 하나로 충분한지는 명시하지 않는다. `[Main p. 11]` `[FAQ p. 4]`
- 필요한 답: 현재 콘텐츠로 이 상태가 가능한지 확인하고 공식 판정을 찾는다.
- 확정(2026-09-01): Main p. 11 원문은 "If you wish to send an Agent to a board space occupied by another player, you may recall your own Spy from a connected observation post to ignore the other player's Agent and send your Agent to that same board space"다. 발동 조건은 "다른 플레이어가 점유 중"이라는 상태 술어이고 인쇄된 비용은 연결된 Spy **하나**의 recall이므로, recall 하나가 점유 opponent Agent 수와 무관하게 배치를 허용한다고 확정한다. Agent 수에 비례해 비용이 늘어나는 독해는 본문·FAQ 어디에도 근거가 없고, "한 Agent만 무시한다"로 읽으면 두 번째 Agent가 여전히 배치를 막아 인쇄된 효과 자체가 성립하지 않는다. 이 상태는 연쇄 Infiltrate(한 명이 정상 배치, 이후 각자 Spy recall로 진입)로 실제 도달 가능하다. 엔진이 다중 opponent 점유 공간을 배치 불가로 막던 임시 guard를 제거했고, opponent Agent 2개 상태에서 Spy 하나의 recall로 진입하는 회귀를 `tests/unit/rules/test_agent_turn.py`로 고정한다. codec은 불변이다(기존 `infiltrate_post_id` 인자 형태 그대로).

## OQ-007 — Leader 선택 절차

- 상태: `DECIDED`
- setup은 각 플레이어가 Leader를 선택하거나 무작위로 정한다고만 한다. 모두가 선택할 때의 순서나 draft 방식은 정하지 않는다. 같은 House의 Leader를 동시에 쓰지 않는 것은 story상 권장 사항이지 금지 규칙이 아니다. `[Main pp. 2, 4]`
- 필요한 답: 학습 환경의 Leader selection을 공식 setup 범위에서 어떻게 표준화할지 별도 ruleset option으로 명시해야 한다. 이는 공식 규칙이라고 표시해서는 안 된다.
- 구현 convention(2026-08-30, ruleset option — 공식 규칙 아님): **6종 공개 draft**.
  1. 사용 룰셋의 합법 Leader 전체(기본 8종, CHOAM 켜면 Shaddam 포함 9종)에서 무작위로 6종을 뽑아 즉시 전원에게 공개한다(seeded chance로 replay 가능하게).
  2. Objective 배분으로 First Player가 정해진 뒤, 라운드 1 turn 순서의 **역순**(마지막 turn 플레이어부터 시작해 First Player가 마지막)으로 한 명씩 남은 pool에서 공개 선택한다.
  3. 모든 선택은 공개 정보이며, 선택되지 않은 2종은 그 게임에서 쓰지 않는다(공개).
  - 공식 setup은 Leader 선택(`[Main p. 4]`)이 Objective/First Player 결정(`[Main p. 5]`)보다 앞이지만, 이 convention은 pick 순서를 정의하기 위해 Leader 선택을 First Player 확정 뒤로 옮긴다. 두 단계 모두 공개 정보만 다루므로 정보 흐름은 달라지지 않는다.
  - 엔진에는 ruleset option으로 구현하고, 기존 고정 배정(테스트·sweep의 `DEFAULT_LEADER_IDS`) 경로는 재현성 용도로 유지한다. 공식 draft 절차가 발표되면 재검토한다.
  - 구현(2026-08-30): `RulesetConfig(leader_draft=True)`가 이 convention을 켠다. reset이 pick과 무관한 setup chance를 모두 seeded 해결한 뒤 `GamePhase.SETUP`의 `leader_draft` frame에서 멈추고, pick마다 좌석을 확정(setup face, 인쇄된 시작 카드 제거는 이미 섞인 덱에서 필터링 — 남은 순서는 균등 유지)하며, 마지막 pick이 Contract 시장을 배분한다(Shaddam pick 시 Sardaukar set-aside). `pick_leader` 템플릿(codec v79에서 도입, 이후 버전에도 유지), 관측 v2의 공개 pool 세그먼트. `tests/unit/rules/test_leader_draft.py`로 고정한다.
- 확정(2026-09-01): 위 6종 공개 draft convention을 학습·플레이 환경의 최종 ruleset option으로 채택한다. "공식 규칙 아님" 표기와, 공식 draft 절차가 발표될 때만 재검토한다는 단서는 유지한다.

## OQ-008 — Control bonus와 방문자 효과의 상대 순서

- 상태: `DECIDED`
- controller는 누구든 controlled space에 Agent를 보내면 bonus를 받는다. 방문자는 자신의 board/card/Faction 효과 순서를 고를 수 있지만, controller bonus가 그 순서 안에 포함되는지는 명시하지 않는다. `[Main pp. 9-10]`
- 필요한 답: 순서가 영향을 주는 card interaction이 있는지 전사 후 확인한다.
- 확정(2026-09-01): controller bonus는 Agent 배치 즉시 지급되며 방문자의 자유 순서 그룹에 속하지 않는다(구현 그대로: `agent_placed` 직후 `control_bonus_gained`). 근거는 두 가지다. (1) Main p. 11의 공식 예시가 Abby의 Arrakeen 방문에서 "John's Control marker is there from an earlier round, so he takes 1 Solari from the bank"를 서술한 **다음에야** "From the board space, Abby recruits a troop and draws another card"를 서술해, controller bonus가 방문자의 space 효과 이전에 방문 처리 자체에서 해결됨을 보여준다 `[Main p. 11 example]`. (2) 완결 콘텐츠 관측 가능성 검토 — Agent turn에 해결되는 어떤 현행 효과도 다른 플레이어의 자원 총량을 조건으로 읽지 않고(effect DSL 조건 전수: 자기 상태, Conflict의 sandworm 존재, Endgame 한정의 opponent Alliance뿐), 세 critical location의 진입 비용 통화와 bonus 통화도 겹치지 않으므로(Spice Refinery 비용 spice vs bonus Solari, Arrakeen·Imperial Basin 무비용) 현재 콘텐츠에서 이 시점 선택이 합법 행동이나 결과를 바꾸는 사례가 없다. `tests/unit/rules/test_agent_turn.py`의 control bonus 테스트 2건(상대 controller 지급, 자기 공간 방문 지급)으로 고정한다. 순서를 관측할 수 있는 새 콘텐츠가 추가되면 다시 연다.

## OQ-009 — observation post 연결 graph

- 상태: `RESOLVED`
- 공식 Main pp. 4-5의 setup board artwork에서 observation post 13개와 모든 직접 연결선을 전사했다. 결과와 검증 주의사항은 [`observation-posts.md`](observation-posts.md)에 있다.
- 텍스트 Board Space Guide에는 이 graph가 없으므로 이후 변경도 board artwork나 공식 textual listing과 대조해야 한다. `[Main pp. 4-5 board artwork]`

## OQ-010 — 손패·discard와 과거 공개 정보의 열람 범위

- 상태: `DECIDED`
- 공식 규칙은 Intrigue identity를 play 전까지 opponent에게 공개하지 않는다고 명시하고, 여러 deck을 face-down, discard를 face-up으로 놓게 한다. 하지만 일반 hand identity/장수, discard 전체 검사, deck 장수, 한 번 공개됐다가 face-down이 된 카드의 재확인 가능 여부를 포괄적으로 정의하지 않는다. `[Main pp. 4-7, 12-14, 16, 20]`
- 구현 convention(2026-08-30): 존의 **장수**(각 플레이어의 hand·개인 deck·discard 장수, 보유 Intrigue 장수)는 실물 테이블에서 항상 보이는 정보이므로 `PublicPlayerView`에 공개한다.
- 방향 확정(2026-09-01, 사용자): **한 번 공개된 정보는 다시 확인할 수 있어야 한다.**
- **확정(2026-09-02, 사용자 판정 4건)**. 모두 공식 규칙이 아니라 위 원칙을 적용한 프로젝트 판정이다.
  1. **상대 discard pile identity는 전원 공개.** discard pile에 들어오는 모든 경로가 공개 시점을 거친다: acquire한 카드는 face-up으로 놓고 `[Main p. 13]`, play·reveal한 카드는 Clean Up 전까지 face-up in play였으며 `[Main pp. 9, 12, 20]`, hand에서 버리는 카드도 face-up pile 위에 놓인다. reshuffle로 deck에 들어가는 순간 다시 비공개가 된다. `PublicPlayerView.discard_pile`, 관측 v3 `seat{n}_discard`. 같은 원칙으로 **공개 경로로 hand에 들어온 카드**(Corrinth City의 acquire-to-hand, Intrigue의 "put that card in your hand", Bene Gesserit Bond로 in play에서 hand로 돌아온 카드)는 hand를 떠날 때까지 공개다(`PlayerState.hand_public` → `PublicPlayerView.hand_public`; 나중에 face-down draw로 다시 들어오면 비공개). play돼 선택 해결 중이라 아직 소유자 보유 존에 있는 Intrigue도 이미 공개된 카드이므로 `PlayerView.intrigue_resolving`으로 공개한다.
  2. **완료 contract identity는 전원 공개.** 활성 중 face-up이었고 완료 시 사실과 reward를 알린 뒤 뒤집는다 `[Main p. 16]`. 뒤집힌 battle card를 `face_down_battle_card_ids`로 공개하는 선례와 같은 구조로 `PublicPlayerView.completed_contract_ids`(관측 v3 `seat{n}_completed_contracts`)에 둔다.
  3. **실시간 행동 로그의 기준.** 로그는 엔진 `event_log`를 `visible_to`로 걸러 보여 준다. 공개 이벤트(`visible_to=None`)의 payload에 담긴 card identity는 그 이벤트 직후 공개 존에 있는 카드만 허용하고, 비공개 존(hand·deck·보유 Intrigue·deck·bank)에 남는 identity를 담는 이벤트는 관련 좌석 한정으로 표시한다. 장수·수량만 담는 이벤트는 전원 공개다. sweep 불변식 `check_event_visibility`가 매 전이마다 이를 검사한다(미래 콘텐츠 tripwire). 적용 결과: Secrets의 강탈은 공개 `intrigue_card_stolen`(도둑·피해자만)과 `intrigue_card_stolen_identity`(도둑·피해자 한정, card_id 포함)로 분리 `[Main p. 7]`; `cards_drawn`·`personal_discard_shuffled`는 장수만 담으므로 공개. `tests/integration/test_sweep.py`.
  4. **게임 종료 후 전체 공개.** 이 항목만 재확인 원칙 밖이다(상대의 미사용 Intrigue와 deck 순서는 한 번도 공개된 적이 없다). 로컬 분석 도구라는 성격을 고려한 **검토 편의 convention**으로, FINISHED 이후에는 모든 좌석의 hand·deck 순서·보유 Intrigue와 Imperium/Intrigue/Conflict deck·contract bank 순서를 `disclose_hidden_zones`로 열고, M11 서버는 종료된 게임의 live view와 검토의 모든 step에 `disclosure`를 붙인다. 검토 라벨은 좌석 구분 없이 모든 행동을 상세 표시하고 chance 결과 값도 보여 주며, AI 좌석 시점의 검토도 허용한다. 진행 중인 게임의 view는 바뀌지 않는다. `tests/server/test_saves.py`, `tests/server/test_app.py`.
- 관련 설계(2026-09-02, 사용자): **행동 되돌리기**(M11 슬라이스 6, [`../implementation-plan.md`](../implementation-plan.md))의 허용 경계도 같은 원칙을 따른다 — 숨겨진 더미에서 누군가에게 흘러간 정보(자기 draw 포함)는 되돌릴 수 없고, 자기 비공개 존에서 공개 존으로 스스로 옮긴 정보(Intrigue play, hand discard/trash, Reveal)는 손해를 감수하고 되돌릴 수 있으며, 되돌린 행동은 로그에 공개로 남는다.
- 재개 조건: 새 공식 룰북·FAQ가 열람 정책을 직접 정할 때.

## OQ-011 — Gather Intelligence와 contract 완료의 상대 순서

- 상태: `DECIDED`
- Gather Intelligence는 Agent를 놓은 `immediately after`에, board space나 Agent card 효과보다 먼저 선택한다. FAQ는 space 방문형 contract 완료가 Agent-turn 효과이고 board space·Agent box와 자유롭게 순서를 정한다고 설명한다. 하지만 contract 완료를 Gather Intelligence 전에도 처리할 수 있는지는 직접 말하지 않는다. `[Main p. 11]` `[FAQ p. 1]`
- 필요한 답: contract completion과 Gather Intelligence 중 어느 decision window가 먼저인지에 대한 공식 판정.
- 구현 convention: 공식 판정을 찾기 전에는 Main p. 11의 `immediately after`를 우선해 Gather Intelligence를 먼저 완료하고, 그 뒤 contract·board space·Agent box 효과의 자유 순서 창을 연다. 이 순서는 공식 사실이 아니라 프로젝트 판정이며 contract 회귀 테스트로 고정한다.
- 확정(2026-09-01): 위 convention을 최종 판정으로 채택한다. Main p. 11 원문 "You must choose whether to do this immediately after placing your Agent (before receiving any effects of the board space or card you played)"가 Gather Intelligence 결정을 배치 직후의 독립 창으로 두고, FAQ p. 1은 space형 contract 완료를 board space·Agent box와 같은 자유 순서 그룹의 Agent-turn 효과로 분류하므로, Gather Intelligence 창이 그 그룹 전체보다 앞서는 현행 순서가 원문과 가장 정합적이다.

## OQ-012 — 자유 순서 그룹 밖 의무 효과의 충돌

- 상태: `DECIDED`
- Main은 board space, Agent box, Faction Influence의 처리 순서를 자유롭게 고르게 하고 FAQ는 space형 contract를 그 그룹에 추가한다. 그 밖의 여러 의무 효과가 동시에 적용되어 서로 충돌할 때의 일반 우선순위는 제시하지 않는다. `[Main p. 9]` `[FAQ pp. 1, 3]`
- 필요한 답: 콘텐츠 전사 후 실제 충돌 사례별 공식 판정을 확인한다.
- 현재 구현 convention: The Spice Must Flow를 acquire할 때 기존 카드의 acquire trigger를 먼저 처리하고, 그 뒤 Acquire Contract를 완료한다. standard Acquire Contract의 보상은 Spacing Guild Influence 1과 Solari 3뿐이지만, Influence 경계·Alliance 때문에 순서가 관측될 수 있으므로 공식 일반 판정이 나오면 다시 검토한다.
- 확정(2026-09-01): 콘텐츠 완결 시점에서 자유 순서 그룹 밖의 동시 의무 효과 계열은 획득(acquire) 이벤트 하나뿐임을 확인하고, 구현된 고정 순서를 최종 판정으로 채택한다: 획득한 카드 자신의 acquire 보상(예: The Spice Must Flow의 VP) → in-play 카드의 acquire trigger(spied Faction Influence) → Acquire Contract 완료(Spacing Guild Influence 1 + 3 Solari) → face-up trigger Intrigue(Call to Arms의 troop recruit). 네 단계 모두 같은 획득자에게 주는 가환 이득이고, Influence도 동일 플레이어의 순차 획득이라 Alliance 전이 판정이 순서에 불변이므로, 현재 콘텐츠에서 어떤 순서든 최종 상태가 같다. Clean Up discard trigger는 OQ-013(RESOLVED), 배치 trigger의 제시 시점은 OQ-016이 다룬다. 서로 비가환인 새 trigger 콘텐츠가 추가되면 다시 연다.
- 참고(2026-09-01): Faction 공간 방문의 Influence 상승 **시점**은 이 항목의 질문이 아니라 공식 자유 순서 규칙이 직접 답한다 — "If the board space belongs to one of the Factions, you also move your cube one space up on its Influence track. You may carry out all these effects in any order" `[Main p. 9]`. 즉 방문자가 board·card 효과와의 순서를 스스로 고르며, 엔진도 `resolve_faction_influence`를 자유 순서 그룹의 선택 행동으로 제시한다.
- 재개 조건(2026-09-01, 사용자): 다음 확장 Bloodlines는 Influence 획득의 순서를 관측 가능하게 만드는 trigger를 추가할 수 있다. Bloodlines 콘텐츠를 도입할 때 이 항목을 다시 열어, acquire 계열 밖의 새 충돌과 비가환 Influence trigger를 재검토한다.

## OQ-013 — Clean Up 이동과 일반적인 `discard` 반응

- 상태: `RESOLVED`
- 현재 Uprising 기본 Imperium 콘텐츠의 discard trigger는 Spacing Guild's Favor 하나뿐이며, Main은 이 카드가 hand에서 discard될 때만 발동한다고 직접 정한다. 구현은 hand-discard transition에서만 trigger를 처리하고 Reveal Clean Up은 in-play 카드를 직접 discard pile로 이동한다. 다른 확장 콘텐츠에서 새 discard trigger를 추가하면 해당 카드의 문구와 판정을 별도로 재검토한다. `[Main pp. 12, 17]`

## OQ-014 — Alliance 상실 때 여러 수령 후보

- 상태: `RESOLVED`
- Captured Mentat의 한 칸 Influence 감소로 실제 상태를 검토했다. 유효한 Alliance 보유자가 4에서 3으로 내려갈 때 Influence 4 이상인 다른 플레이어는 감소 직전 모두 보유자와 4에서 동률이므로 FAQ의 기존 보유자 선택 규칙이 적용된다. 보유자가 5 이상이면 한 칸 감소 뒤에도 4 이상이라 token 반환 조건에 들어가지 않는다. 여러 칸 감소도 한 칸씩 처리하면 같은 결론이 반복되므로, 직전 동률자가 아닌 복수 수령 후보 상태는 유효한 track 전이에서 발생하지 않는다. `[Main p. 7]` `[FAQ p. 1]`
- 구현은 감소 직전 동률 후보가 여러 명이면 기존 보유자의 명시적 선택을 요구한다.

## OQ-024 — The Beast's Spoils(프로모)의 battle icon별 보상 범위

- 상태: `DECIDED` (project convention)
- 카드면(Agent box): "Gain rewards for your face-up battle icons: Crysknife: trash 아이콘, Desert Mouse: spice 1, Ornithopter: troop". 이 카드는 정식 덱 밖의 Uprising 프로모라 어떤 공식 문서에도 없다. `[card face]` 공식 규칙은 battle icon을 Objective와 획득 Conflict 카드의 face-up 인쇄 아이콘으로 정의하고, Conflict 카드를 가져올 때 같은 아이콘의 face-up 카드가 있으면 반드시 짝을 뒤집으므로 **같은 아이콘의 face-up 카드는 종류당 최대 1장**이다. wild icon은 Endgame에서만 짝짓는다. `[Main pp. 14, 20]`
- 필요한 답: (a) face-up wild(Propaganda)가 세 아이콘 중 하나로 세어지는지, (b) trash 보상이 선택인지.
- 판정(2026-09-03, 사용자 지적 반영): 보상은 **face-up인 아이콘 종류마다 한 번**이다 — 즉시 매칭 규칙(`[Main p. 14]`) 때문에 종류당 face-up 카드가 둘 이상일 수 없으므로 "장수"를 셀 필요가 없다. (a) wild는 세지 않는다 — wild는 Endgame에서 하나의 아이콘과 짝짓기 위해 선택하는 것이지 그 자체가 Crysknife 등이 아니다(`[Main p. 20]`). (b) trash는 선택이다 — "Trashing is optional unless it's paying a cost"(`[Main p. 20]`)이고 여기서는 보상이다. 구현: `GAIN_REWARDS_PER_FACE_UP_BATTLE_ICON`은 `face_up_battle_icons`(아이콘 집합)로 spice·troop을 자동 지급한 뒤 Crysknife가 있으면 trash 선택(hand·discard·in play, 거절 가능)을 한 번 제시한다. `tests/unit/rules/test_promo_cards.py`.

## OQ-025 — Pivotal Gambit(프로모)의 "1위 보상에 Influence 1 선택 추가"

- 상태: `DECIDED` (project convention)
- 카드면(Agent box): "Trash this card → troop AND Add [Influence 1 선택 아이콘] to the first place reward for this conflict." 아이콘은 룰북 20쪽 "Gain one, gain two, lose one Influence. Choose any one of the four Factions"의 노란 마름모 `?`이다(wild battle icon의 평행사변형 `?`가 아님; 2026-09-03 처음 wild로 오독했던 것을 사용자가 바로잡았다). 공식 문서는 Conflict 카드에 인쇄되지 않은 보상을 추가하는 절차를 다루지 않는다. `[card face]` `[Main pp. 14, 20]`
- 필요한 답: (a) 추가된 Influence를 누가 받는가, (b) 1위가 없으면(동률) 어떻게 되는가, (c) sandworm의 보상 두 배가 적용되는가.
- 판정(2026-09-03, project convention): (a) 보상은 Conflict의 1위 보상에 붙으므로 누가 냈든 **그 Conflict의 1위**가 받는다(카드를 낸 플레이어 자신이 1위가 되도록 노리는 카드). (b) 1위가 없으면 다른 1위 보상처럼 사라진다. (c) 인쇄된 1위 보상과 같은 자격이므로 sandworm이 있으면 두 배가 된다(`[Main p. 14]`: control과 battle icon만 예외). 여러 장이 pledge되면 그만큼 누적된다. 구현: `GameState.conflict_first_place_influence_bonus`(라운드의 Conflict 공개 시 0) → `resolve_combat_rewards`가 1위 보상의 `choose_influence`에 더해 기존 `COMBAT_REWARD_INFLUENCE` 선택 frame으로 해결하고 0으로 되돌린다. 관측 v4 전역 scalar. `tests/unit/rules/test_promo_cards.py`.

## OQ-026 — Arrakis Revolt(프로모)의 Shield Wall 제거 선택과 보호된 Conflict

- 상태: `DECIDED` (project convention)
- 카드면(Agent box): "Maker Hooks: 2 spice → [Shield Wall 아이콘] [sandworm 아이콘]". 공식 아이콘 정의는 Shield Wall 아이콘을 "You **may** remove the Shield Wall token from the game board", sandworm을 "Does nothing if the current Conflict is protected by the Shield Wall. Otherwise, summon and deploy one sandworm"으로 둔다. `[Main p. 20]` 본문도 "When the Shield Wall detonation icon appears on a card or board space, you **may** remove the Shield Wall token"이라고 쓴다. `[Main p. 10]` `[card face]`
- 필요한 답: 비용을 내고 Shield Wall을 남긴 채 보호된 Conflict에 sandworm을 소환하는(아무 효과 없는) 선택을 제시할지, 비용 재판정 시점.
- 판정(2026-09-03, project convention; 제거가 선택이라는 점은 위 공식 문장 그대로): Maker Hooks는 배치 시 요구 조건이고 2 spice는 해결 시점에 다시 판정하는 화살표 비용이다(`[Main pp. 9, 20]`, 다른 화살표 비용과 같음). 선택지는 "지불 + Shield Wall 제거 + 소환"(벽이 있을 때)과 "지불 + 벽 유지 + 소환"(현재 Conflict가 보호되지 않을 때)이며, 보호된 Conflict에서 벽을 남기고 지불하는 무효 선택은 제시하지 않는다(2 spice로 아무것도 얻지 못하는 선택은 규칙상 가능하더라도 행동 공간에서 뺀다). Emperor of the Known Universe의 배치 차단(`[Main p. 17]`)은 sandworm 소환에도 적용된다. 구현: `MAY_PAY_TWO_SPICE_FOR_SHIELD_WALL_AND_SANDWORM_IF_MAKER_HOOKS`. `tests/unit/rules/test_promo_cards.py`.

## OQ-027 — 보드 공간에 인쇄된 여러 아이콘의 해결 단위

- 상태: `DECIDED`
- Main은 Agent를 보낸 뒤 board space의 효과들, card Agent box의 효과들, Faction Influence를 "원하는 순서로 처리한다(You may carry out all these effects in any order)"고 한다. `[Main p. 9]` 그러나 한 공간에 인쇄된 여러 아이콘(예: Arrakeen의 troop 1 recruit와 card 1 draw)이 각각 별개의 "효과"인지, 그리고 choose-one 괄호로 묶인 줄이나 문장으로 쓰인 효과가 어디까지 하나의 단위인지는 어느 문서도 명시하지 않는다. `[Board Guide pp. 1-2]`
- 필요한 답: 공간 아이콘의 해결 단위에 대한 공식 판정.
- 이전 구현(~2026-09-03, 폐기): 인자 없는 `resolve_board_effect` 한 행동이 공간의 자동 효과 전부(troop·draw·자원 등)를 한 번에 해결했다. Espionage의 draw+Spy, Desert Tactics의 troop+trash, Shipping의 Solari+Influence도 선택 행동 하나에 묶여 있었다.
- 확정(2026-09-03, 사용자 판정): 한 공간에 인쇄된 아이콘은 **각각 독립된 효과**이며, 소유자는 각 아이콘을 별개 행동으로 원하는 순서에 해결한다(OQ-015(d)의 Intrigue 아이콘 판정과 같은 방향, `[Main p. 9]`). 두 아이콘을 함께 해결해도 결과가 같은 경우가 많지만 결정 모델은 인쇄 단위를 따른다. 단위 경계는 project convention이다: (a) 자동 아이콘(자원·card draw·Intrigue draw·troop recruit)과 CHOAM contract 아이콘, High Council 착석, Swordmaster는 `resolve_board_effect(effect=<key>)`로 하나씩; (b) 선택이 필요한 아이콘 — Espionage의 Spy 배치, Desert Tactics의 trash, Shipping의 Faction 선택 — 은 각 공간의 전용 행동으로 하나씩; (c) Sietch Tabr의 choose-one 줄과 Maker 공간의 "bonus spice 후 spice 또는 sandworm" 선택은 인쇄된 하나의 선택 단위로 유지; (d) Imperial Privilege의 두 문장(선택적 Intrigue 교환, "recall하고 draw")과 Secrets의 "draw 후 무작위 강탈" 문장은 문장 단위로 유지한다(OQ-023의 recall/draw 분리 판정은 그대로). Reverend Mother의 반복(`[Reverend Mother Jessica card]`)은 공간의 인쇄 아이콘 전부를 다시 대기시킨다. 구현: frame context `board_icons`/`pending_board_icons`, `rules/board_effects.py`의 `board_icons_for`, codec v86(`resolve_board_effect` 템플릿 7종). `tests/unit/rules/test_board_effects.py`, `tests/unit/rules/test_leader_abilities.py`로 고정한다.
- 카드 Agent box 확장(2026-09-03 밤, 사용자 지시 "카드 효과도 마찬가지"): 한 Agent box에 인쇄된 여러 아이콘도 같은 단위로 해결한다. (a) 배치 시 대기하는 무비용 아이콘 — Hidden Missive(troop, card draw; 둘 다 Bene Gesserit 2 조건을 각 아이콘 해결 시점에 판정), Steersman(card draw, Agent recall), Maker Keeper(water@BG 2, spice@Fremen 2), Wheels Within Wheels(2 Solari@Emperor 2, spice@Guild 2), Dangerous Rhetoric(카드면: Influence 선택 마름모 + "Trash this card." 문장 — 화살표 없음); (b) 화살표 비용을 먼저 지불한 뒤 보상 아이콘을 대기시키는 카드 — Captured Mentat(discard → Intrigue draw, card draw), Guild Spy(discard → card draw, Guild 카드면 Intrigue draw), Branching Path(trash → Intrigue draw, troop 2), Pivotal Gambit(자기 trash → troop, 1위 보상 Influence 서약). 자동 아이콘은 `resolve_agent_card_effect(effect=<key>)`(키 8종: cards·intrigue·pledge·solari·spice·trash_self·troops·water, codec v87), 선택 아이콘(recall, influence)은 기존 전용 행동으로 해결한다. 카드가 **자기 비용이나 자기 아이콘으로** play 영역을 떠난 경우 남은 아이콘은 계속 지급되고(OQ-022 디자이너 판정의 "자기 효과" 예외), 다른 효과로 trash되면 OQ-022대로 box 전체가 만료된다. 단위 경계 유지: The Beast's Spoils(면 아이콘별 자동 보상 묶음 + trash 선택, OQ-024)와 Arrakis Revolt(OQ-026의 지불 변형)는 그대로이고, Long Live the Fighters·Subversive Advisor·Treacherous Maneuver 등 문장형·화살표 비용쌍 효과도 그대로다. `tests/unit/rules/test_agent_effects.py`, `tests/unit/rules/test_promo_cards.py`로 고정한다.
- Reveal box(2026-09-04 적용): Reveal의 자동 이득(Persuasion·sword·자원·troop·Intrigue draw·Influence)은 Reveal 시작 시 한꺼번에 적용된다 — 순수 이득의 시점은 결과에 영향을 주지 않는다. 선택형 Reveal 효과(`PersonalCardRevealChoiceEffect` 11종)는 카드 순서로 쌓인 `REVEAL_CHOICE` frame으로 제시되지만, `[Main p. 12]`("You may resolve Reveal effects in any order you like... use Persuasion at any time")에 따라 소유자가 순서를 고를 수 있다: 맨 위 선택을 `defer_reveal_choice`로 미루면 다음 선택이나 Reveal frame(획득·Intrigue·Leader 능력)이 드러나고, 미룬 선택은 Reveal frame에서 `resume_reveal_choice(effect=<종류>)`로 언제든 되가져온다. 되가져온 선택은 다시 미룰 수 없어 순환이 없고, 이미 시작한 선택(빈 supply의 Spy 배치를 위해 recall한 뒤)도 미룰 수 없으며, 미룬 선택이 남아 있으면 `finish_reveal`이 제시되지 않는다. 되가져올 때 가용성을 다시 판정해(`[Main pp. 9, 20]`의 해결 시점 판정과 같은 방향) 조건이 사라진 선택(예: Spy가 부족해진 두 Spy 회수)은 `reveal_choice_unavailable`로 소멸한다. codec v88(`defer_reveal_choice` 1 + `resume_reveal_choice` 11). `tests/unit/rules/test_reveal_turn.py`로 고정한다.

## OQ-028 — 인쇄 조건의 판정 시점: 같은 turn의 뒤 선택으로 성립하는 조건

- 상태: `DECIDED`
- Main은 Agent turn의 space·Agent box·Faction 효과와 Reveal 효과를 소유자가 원하는 순서로 처리한다고 하지만(`[Main p. 9]` `[Main p. 12]`), 카드에 인쇄된 조건(Influence 2, Spy 2개 배치, Faction Bond, High Council, 자원 비용, Alliance, Conflict의 sandworm, 완료 contract 수 등)을 **언제 판정하는지**는 명시하지 않는다. 그 조건이 처음에는 거짓이다가 같은 turn 안의 소유자 선택(Faction Influence 단계, board의 water/spice 아이콘, Sietch Tabr 보급, Maker sandworm 소환, 다른 카드의 Reveal Spy 배치, Corrinth City의 High Council 구매, Reveal 중 늦게 도착한 카드, 획득으로 완료되는 Acquire contract)으로 참이 되는 경우가 실제로 있다.
- 필요한 답: 조건을 배치/Reveal 시작 시점에 고정하는지, 효과를 실제로 해결하는 시점(또는 조건이 성립한 시점)에 판정하는지의 공식 판정.
- 이전 구현(~2026-09-04, 폐기): Agent box는 배치 시점에 조건이 거짓이면 아예 pending되지 않아 이후 성립해도 제시되지 않았고(핸드오프의 "알려진 엔진 경계"), Reveal의 선택형 효과는 시작 시점에 조건이 거짓이면 frame이 생기지 않았으며 되가져올 때 조건이 없으면 소멸했고, Reveal의 자동 조건부 이득은 시작 시점에만 판정됐다.
- 확정(2026-09-04, 사용자 지적 "원래는 불가능했는데 플레이어의 선택으로 가능하게 변하는 조건들 확인"): 자유 순서 원칙의 귀결로, 조건은 **효과를 해결하는 시점**에 판정하며, 같은 turn 안에서 소유자의 뒤 선택으로 성립할 수 있는 조건은 그때까지 열려 있다. 구체 판정: (a) Agent box — 배치 시점에는 이후 어떤 효과로도 바뀔 수 없는 조건(방문한 space의 Faction·Maker 여부, 이미 play된 카드들 사이의 Faction Bond — Bond는 줄어들 수만 있음)만 판정하고, 나머지(Influence 문턱, 자원·손패·Intrigue 비용, Alliance, sandworm)는 box를 pending으로 두고 해결 시점에 판정한다. 화살표 지불은 비용이 성립할 때까지 decline만 제시하고, 조건이 거짓인 의무 효과는 해결 시 `agent_card_effect_unavailable`로 아무 것도 하지 않는다(Leadership, Guild Envoy). (b) Reveal 선택형 효과 — 시작 시점(또는 늦은 도착 시점)에 조건이 거짓이면 미룬 선택 큐에 넣고, `resume_reveal_choice`는 조건이 지금 성립하는 종류만 제시하며, `finish_reveal`은 지금 성립하는 미룬 선택이 없을 때만 제시한다(끝까지 성립하지 않은 선택은 `reveal_choice_unavailable`로 소멸). (c) Reveal 자동 조건부 이득 — Reveal 시작 시 지급된 효과를 frame에 기록(`granted_reveal_effects`)하고, 매 전이 뒤의 dispatcher pass(`grant_late_reveal_effects`)가 조건이 새로 성립한 효과를 한 번만 지급한다(Persuasion·자원·troop·Intrigue draw·Influence; 완료 contract당 Persuasion은 늘어난 수만큼 증분). OQ-020(한 번 성립하면 회수하지 않음)과 정합. 감사 결과 정적 조건은 그대로다: space 속성, Bond(감소만 가능), Swordmaster(Reveal 중 획득 불가), Intrigue deck 소진(reshuffle까지 포함해 0장이면 turn 안에 늘지 않음). 구현: `agent_turn._agent_effect_is_available`, `agent_effects`, `reveal_turn`(`_available_deferred_choices`, `grant_late_reveal_effects`), `engine`의 hook 순서. `tests/unit/rules/test_agent_effects.py`(Wheels Within Wheels·Branching Path·Ecological Testing Station·Leadership의 "뒤에 성립" 사례), `tests/unit/rules/test_reveal_turn.py`(In High Places·Bene Gesserit Operative·Paracompass·Northern Watermaster·Interstellar Trade)로 고정한다.

## 판정이 생겼을 때 기록할 정보

각 항목을 닫을 때 다음을 함께 남긴다. `DECIDED` 항목에 새 공식 답이 나왔을 때도 같다.

1. 공식 답변 URL 또는 새 룰북/FAQ의 문서명·버전·페이지
2. 이 명세에서 바뀐 문장
3. 구현에 선택지가 남았다면 공식 규칙과 project convention의 명확한 구분
4. 해당 edge case를 재현하는 scenario test

## OQ-016 — face-up trigger Intrigue의 수명

- 상태: `DECIDED`
- FAQ는 효과가 아직 적용되지 않는 Intrigue를 "그때까지 face up으로 두고, 그 다음 사용하고 discard한다"고 한다. 그러나 (a) trigger 창이 지나가도록 한 번도 발동하지 못한 카드(예: Call to Arms를 두고 Reveal에서 아무 카드도 acquire하지 않은 경우)를 언제 discard하는지, (b) "whenever" 반복 trigger의 discard 시점이 창의 끝인지 첫 발동인지, (c) 선택적 trigger("you may")를 거절하면 카드가 face up으로 남는지는 명시하지 않는다. `[FAQ p. 2]`
- 필요한 답: face-up Intrigue의 만료와 거절 시 처리에 대한 공식 판정.
- 구현 convention: (a)(b) 창이 명시된 카드(Call to Arms의 "이번 round의 자신의 Reveal turn")는 그 창이 닫힐 때(Reveal turn 종료) 발동 여부와 무관하게 discard한다. "whenever" trigger는 창이 닫힐 때까지 반복 발동한다. (c) 선택적 trigger(Distraction)를 거절한 카드는 사용된 것이 아니므로 face up으로 남아 이후의 조건 충족 turn에 다시 제시된다. 같은 turn에서는 배치 수가 마지막 제시 시점보다 늘었을 때만 다시 제시하며, 이미 제시가 지나간 수치에서 나중에 낸 두 번째 사본은 다음 배치 때 제시된다. 세 판정 모두 `tests/unit/rules/test_intrigue.py`로 고정한다.
- 확정(2026-09-01): 위 (a)-(c) convention 전부를 최종 판정으로 채택한다. 현재 face-up trigger 카드는 Call to Arms와 Distraction 두 종뿐이며 두 카드 모두 이 판정으로 완전히 규정된다.

## OQ-015 — Intrigue의 Plot timing 시작점과 복수 비용 줄의 의무 지불

- 상태: `DECIDED`
- Main은 Plot Intrigue를 자신의 Agent turn 또는 Reveal turn 도중 사용할 수 있다고 하고, FAQ는 Intrigue를 play하면 조건을 충족하고 비용을 지불해야 한다고 한다. 하지만 (a) Agent/Reveal 선택을 확정하기 전, 즉 turn이 막 시작된 시점이 "turn 도중"에 포함되는지, (b) Strategic Stockpiling처럼 비용 줄이 둘이고 그중 하나가 Influence 조건으로 열리는 카드에서 조건을 만족하면 두 비용을 모두 지불해야 하는지는 명시하지 않는다. `[Main pp. 7-8]` `[FAQ p. 2]`
- 필요한 답: Plot play window의 시작점과, 조건부로 열린 두 번째 비용 줄의 의무 여부에 대한 공식 판정.
- 구현 convention: (a) 소유자에게 turn 선택이 제시된 순간부터 Plot을 낼 수 있고, Agent turn의 마지막 pending 그룹이 해결되면 turn이 자동으로 넘어가므로 그 전에 내야 한다. (b) 조건이 성립한 모든 비용 줄은 의무이며, 전부 지불할 수 없으면 카드를 낼 수 없다. (c) Reveal turn 중 card가 hand에 들어가는 Plot — 개인 card draw, 그리고 Inspire Awe처럼 조건이 성립해 hand로 acquire하는 경우 — 은 이제 Reveal turn 중에도 제시한다. hand에 들어간 card는 FAQ p. 3의 즉시 공개 규칙에 따라 그 자리에서 revealed된다: hand → in_play로 옮기고, 더 커진 revealed 집합 기준으로 자신의 Reveal 기여분(설득·검·자원·선택 효과)을 얻어 같은 Reveal turn에 사용한다. 앞서 Reveal에서 이미 지급된 금액은 확정이며 다시 계산하거나 회수하지 않는다. 늦게 도착한 card의 per_revealed_faction·strength_per_other_sword_card 같은 교차 효과는 그 도착이 이미 revealed된 다른 card들에 일으키는 증분만 더하고, 그 증분을 줄 자격은 도착 시점 조건으로 다시 판정한다. 현재 콘텐츠의 교차 효과 3종 (Stilgar, Sardaukar Coordination, Leadership)은 모두 자격 조건이 없어 이 재판정이 항상 공허하며, `tests/unit/rules/test_reveal_turn.py`의 pin 테스트로 고정한다(자격 조건이 있는 교차 효과가 새로 추가되면 회수 로직이 없는 이 구현이 실패하도록 하는 장치). (d — 폐기, 아래 재판정 참조) 한 option 안의 선택 슬롯은 자동 보상보다 먼저 해결한다고 했었다. 판정 (a)-(c)는 프로젝트 convention이며 `tests/unit/rules/test_intrigue.py`로 고정한다.
- 확정(2026-09-01): 위 (a)-(c) convention을 최종 판정으로 채택한다.
- (d) 재판정(2026-09-02, 사용자): 한 효과 줄에 인쇄된 여러 아이콘(draw, trash, Spy 등)은 **각각 독립된 효과**이며 인쇄가 순서를 강제하지 않으므로, 소유자가 해결 순서를 선택한다(board 효과의 "You may carry out all these effects in any order" `[Main p. 9]`와 같은 방향). 화살표 비용→보상 줄은 화살표 자체가 인쇄된 순서이므로 비용을 먼저 지불한다(`[Main pp. 9, 20]`). 구현: INTRIGUE_CHOICE frame에 `resolve_intrigue_rewards` 행동을 추가해, 비용 슬롯이 모두 지불된 뒤부터 소유자가 자동 보상 묶음을 남은 선택 슬롯 앞·사이·뒤 어느 시점에든 해결할 수 있다(codec v83). 따라서 Cunning은 draw를 먼저 해결해 방금 뽑은 card를 trash할 수 있고, trash를 먼저 하면 이전처럼 뽑기 전 후보만 남는다. 완결 콘텐츠에서 이 순서가 결과를 바꾸는 조합은 Cunning(draw+trash)뿐이고, Unexpected Allies(Shield Wall 파괴+소환)는 기존 고정 순서가 유일하게 합리적인 순서였으나 이제 양방향 모두 제공한다. 나머지 슬롯+자동 조합(Devour, Impress, Leverage)은 어느 순서든 결과가 같다. `tests/unit/rules/test_intrigue.py`와 `tests/integration/test_sweep.py`(mid-frame reshuffle seeds 485/563)로 고정한다.

## OQ-017 — Feyd token이 맨 오른쪽에 있을 때의 Signet 보상

- 상태: `DECIDED`
- Personal Training은 "Move your Feyd token one space to the right on your Training track, earning the reward on the new space"라고 인쇄돼 있고, Main은 token이 맨 오른쪽 칸에 도달하면 게임 끝까지 그 자리에 남는다고만 말한다. token이 더 이동할 수 없을 때 Signet Ring play가 무언가를 주는지는 명시하지 않는다. `[Feyd-Rautha Harkonnen card]` `[Main p. 17]`
- 필요한 답: 맨 오른쪽 칸에서 Signet Ring을 냈을 때 보상 유무의 공식 판정.
- 구현 convention(2026-08-29): 카드가 보상을 "새 칸"에 결부시키므로 이동이 없으면 보상도 없다. Signet Ring 카드 자체는 여전히 Agent를 보낸다. `tests/unit/rules/test_leader_abilities.py`로 고정한다.
- 확정(2026-09-01): 위 convention을 최종 판정으로 채택한다.

## OQ-018 — memory 0개일 때의 Other Memories 사용 가능 여부

- 상태: `DECIDED`
- Other Memories는 "you may return all your memories to your supply, drawing a card for each one. Then flip this Leader over"라고 인쇄돼 있다. memory가 하나도 없을 때 이 능력을 써서(아무것도 되돌리지 않고) flip만 할 수 있는지는 공식 문서에 없다. `[Lady Jessica card]`
- 필요한 답: memory 0개 상태에서 능력 사용(즉 flip)이 허용되는지의 공식 판정.
- 구현 convention(2026-08-29): "all your memories"는 0개를 포함하는 것으로 읽어 사용을 허용한다(retreat의 `any number`가 0을 허용하는 FAQ 판정과 같은 방향, `[FAQ p. 3]` 참고). draw는 0장이고 flip은 일어난다.
- 확정(2026-09-01): 위 convention을 최종 판정으로 채택한다.

## OQ-019 — Reverend Mother 반복의 적용 범위

- 상태: `DECIDED`
- Reverend Mother는 "repeat the effects printed on that space"라고 인쇄돼 있다. Faction board space 방문으로 얻는 Influence 1이 "그 space에 인쇄된 효과"에 포함되는지, space의 비용을 다시 지불해야 하는지는 공식 문서에 없다. `[Reverend Mother Jessica card]`
- 필요한 답: 반복 대상의 정확한 범위에 대한 공식 판정.
- 구현 convention(2026-08-29): Influence는 "Faction의 board space에 Agent를 보내면" 얻는 Faction 규칙이지 space의 인쇄 효과가 아니므로 반복하지 않는다 `[Main p. 7]`. space 비용도 효과가 아니므로 재지불하지 않고, 반복은 인쇄 효과 상자(board 효과 경로)만 다시 해결한다. `tests/unit/rules/test_leader_abilities.py`로 고정한다.
- 확정(2026-09-01): 위 convention을 최종 판정으로 채택한다.

## OQ-020 — Always Smiling 부여 뒤 strength가 내려간 경우

- 상태: `DECIDED`
- Always Smiling은 "Reveal Turn: If you have 6* or more strength in the Conflict: 1 Persuasion"이다. Persuasion을 부여받은 뒤 같은 Reveal turn에 retreat 등으로 strength가 6 미만으로 내려가면 Persuasion을 회수해야 하는지는 공식 문서에 없다. `[Gurney Halleck card]`
- 필요한 답: 조건이 사후에 깨졌을 때의 공식 판정.
- 구현 convention(2026-08-29): 조건이 처음 성립한 시점에 1회 부여하고 회수하지 않는다. Persuasion은 이미 지출됐을 수 있는 turn 자원이라 회수가 정의되지 않기 때문이다. `tests/unit/rules/test_leader_abilities.py`로 고정한다.
- 확정(2026-09-01): 위 convention을 최종 판정으로 채택한다.

## OQ-021 — 시장이 빈 뒤의 set-aside Sardaukar contract 접근

- 상태: `DECIDED`
- Shaddam의 카드는 "Only you can acquire them during the game"이라 하고, FAQ는 Sardaukar Commander가 "일반적으로 얻을 수 있는 contract 대신(in place of)" set-aside contract를 acquire할 선택권을 준다고 한다. Main은 "모든 contract를 플레이어들이 가져갔다면" contract 아이콘이 2 Solari로 되돌아간다고 한다. face-up 시장과 bank가 모두 비었지만 set-aside가 남아 있을 때 Shaddam의 contract 아이콘이 여전히 set-aside를 가져올 수 있는지는 어느 문서도 직접 답하지 않는다. `[Shaddam Corrino IV card]` `[FAQ p. 3]` `[Main p. 16]`
- 필요한 답: 시장 고갈 후 set-aside 접근 가능 여부의 공식 판정.
- 이전 convention(2026-08-30 ~ 2026-09-01, 폐기): 시장이 고갈되면 Shaddam의 contract 아이콘도 다른 플레이어처럼 2 Solari로 자동 전환했다.
- 확정(2026-09-02, 사용자 재판정): face-up 시장과 bank가 모두 소진돼 contract 아이콘이 2 Solari로 인쇄 전환되는 상태에서(`[Main p. 16]`), set-aside Sardaukar contract를 아직 보유한 Shaddam은 아이콘마다 **2 Solari 획득과 set-aside contract 획득 중 하나를 선택**한다. "Only you can acquire them during the game"(`[Shaddam Corrino IV card]`)의 전용 재고가 남아 있는 한 그의 아이콘이 그 재고에 접근할 수 있어야 한다는 판정이다. 구현: 그의 아이콘은 고갈된 시장에서도 contract 시장 frame을 열고, set-aside 획득 행동 옆에 `take_exhausted_contract_solari`를 제시한다(codec v84). set-aside까지 소진되면, 그리고 다른 플레이어는 언제나, 기존 자동 2 Solari 전환을 유지한다. `tests/unit/rules/test_leader_abilities.py`로 고정한다.

## OQ-022 — Agent 효과 해결 전에 play된 카드 자체가 trash될 때

- 상태: `DECIDED`
- Agent turn의 자유 순서 안에서, play된 카드의 Agent box가 해결되기 전에 Intrigue의 trash 슬롯(예: Cunning) 등으로 그 카드 자체를 in play에서 trash할 수 있다. 공식 문서는 화살표 없는 자기 trash가 의무라고 정할 뿐 (`[FAQ p. 3]`), 이미 다른 효과로 trash된 카드의 보류 중인 Agent box를 어떻게 해결하는지는 답하지 않는다. `[Main pp. 9, 20]`
- 필요한 답: play된 카드가 해결 전에 zone을 떠났을 때 그 카드의 인쇄 효과가 여전히 해결되는지의 공식 판정.
- 이전 convention(2026-08-30 ~ 2026-09-01, 폐기): 의무 효과의 나머지 부분은 그대로 해결하고 자기 trash 지시는 충족으로 간주했다(`agent_card_self_trash_satisfied`). Dangerous Rhetoric 분기 확장, Delivery Agreement의 비용형 trash 미제시, trash된 source의 Bond를 남은 in-play 카드로 성립시키는 재판정까지 같은 모델이었다. 아래 디자이너 판정 발견으로 대체됐다.
- 확정(2026-09-01, 디자이너 판정 채택): 사용자 지시로 외부 커뮤니티와 공식 디지털 구현을 조사한 결과, 디자이너 Paul Dennen(BGG 계정 "Merakon", userid 31474)이 2023-02-19에 기존 pooled-effects 판정을 **공식 번복**하며 "you can't receive or activate an effect from a card that is already trashed"라고 판정한 것을 확인했다 — <https://boardgamegeek.com/thread/3031484> (페이지는 Cloudflare 사람 확인 뒤라 공개 geekdo API로 본문을 확인). 사례: Esmar Tuek을 trash해 얻은 spice로 그 Agent box를 발동할 수 없고, Foldspace를 draw 전에 trash하면 그 의무 draw도 발동하지 않는다(사실상 회피 가능). 후속 답글의 적용 세부: 이미 pool에 지급된 persuasion·sword는 유지, 카드가 **자기 효과로** 자신을 trash하는 경우 인쇄된 이득은 정상 지급, 설치형·지연 trigger는 source가 trash돼도 유지. 2025-01-13 FAQ의 Imperial Spy 항목(다른 수단으로 trash되면 draw하지 않는다)과 Beguiling Pheromones 항목이 같은 원칙의 named-card 적용이라, 이 판정이 최신 FAQ 시점에도 유효함을 뒷받침한다. `[FAQ pp. 1-2]`
- 엔진 반영(`76dbbf7`): dispatcher 훅 `expire_trashed_card_effects`가, 자유 순서 효과가 play된 카드를 trash하면 아직 발동하지 않은 Agent box 전체(의무 부분·Bond box·선택 슬롯)를 `agent_card_effect_expired`로 만료시킨다. 이전의 충족 간주·잔여 해결 경로와 그 이벤트는 제거했다. Delivery Agreement 비용형 미제시와 Weirding Woman 무효는 이 일반 판정의 특수 사례로 흡수되고, Reveal에서 이미 확정된 기여분은 회수하지 않으며, 카드가 자기 효과로 자신을 trash하는 정상 경로는 그대로다. `tests/unit/rules/test_agent_effects.py`, `tests/unit/rules/test_reveal_turn.py`, `tests/integration/test_sweep.py`로 고정한다.
- 출처가 공식 룰북·FAQ **문서**가 아닌 디자이너 포럼 판정이므로 상태는 `DECIDED`로 두고, 공식 문서에 인쇄되면 `RESOLVED`로 올린다.

## OQ-023 — Imperial Privilege의 recall 의무와 대상 부재 시 처리

- 상태: `DECIDED`
- Board Space Guide는 Imperial Privilege의 효과를 "원하면 Intrigue 1장을 discard하고 Intrigue 1장을 draw. 이번 turn에 보낸 Agent가 아닌 자신의 다른 Agent 1개를 recall하고 card 1장을 draw"로 인쇄한다. 첫 문장에만 선택 표지("원하면")가 있고, 다른 배치된 Agent가 하나도 없을 때 recall과 그에 결부된 card draw가 어떻게 되는지는 답하지 않는다. `[Board Guide p. 2]`
- 필요한 답: recall 절이 의무인지, 그리고 recall 대상이 없을 때 card draw만 따로 발생하는지의 공식 판정.
- 이전 convention(2026-09-01, 폐기): recall 대상이 없으면 절 전체(recall과 draw)를 무효화했다. 같은 날 사용자 재검토로 아래 판정으로 교체됐다.
- 확정(2026-09-01, 사용자 재판정): 인쇄문 "Recall one of your other Agents from the board, and draw a card"의 recall과 draw는 **별개의 효과**다. recall은 대상이 있으면 의무이고 소유자가 대상을 고르며, 다른 배치된 Agent가 없으면 불가능한 recall만 건너뛰고 card draw는 그대로 해결한다(의무 효과는 수행 가능한 부분을 수행한다는 원칙, `[FAQ p. 3]`의 의무 효과 판정과 정합). recall 대상 유무는 Intrigue 슬롯이 해결된 뒤의 해결 시점에 판정한다(`[Main pp. 9, 20]`). 엔진 반영은 `bce829e`, `tests/unit/rules/test_board_effects.py`로 고정한다.
