# 공식 문서만으로 확정할 수 없는 항목

이 목록은 규칙을 임의로 메우지 않기 위한 작업 대기열이다. 아래 항목은 현재
확인한 Main Rulebook, Board Space Guide, 2025-01-13 FAQ에 명시적 답이 없거나,
구현에 필요한 정도로 순서가 정해져 있지 않다. 답을 얻기 전에는 production
규칙으로 조용히 고정하지 않는다.

상태 값은 다음과 같다.

- `OPEN`: 공식 판정이 더 필요하다.
- `CONTENT`: 실제 card/Leader 텍스트 전사 뒤 질문 자체가 성립하는지 재검토한다.
- `ARTWORK`: 공식 board/card artwork에서 전사·교차 검증해야 한다.

번호는 외부 링크의 안정성을 위해 재사용하지 않는다. 해결된 항목은 짧은
`RESOLVED` tombstone을 남기고 결과 문서로 연결한다.

## OQ-001 — Endgame 처리 순서와 priority

- 상태: `OPEN`
- 공식 문서는 Endgame Intrigue를 먼저 play/resolve한 뒤 승자를 정하고, Endgame에
  wild battle icon을 한 쌍 matching할 수 있다고 말한다. 그러나 어느 플레이어부터
  Intrigue를 내는지, pass 뒤 다시 기회를 얻는지, wild matching을 Intrigue 전·중·후
  언제 하는지는 설명하지 않는다. `[Main pp. 15, 20]`
- 필요한 답: Endgame decision window의 참가 순서, 종료 조건, wild matching
  window.
- 구현 convention(2026-08-29): First Player부터 시계 방향으로 각 플레이어가
  Endgame window를 한 번씩 가진다. 자신의 window에서 Endgame Intrigue play와
  wild battle icon matching을 원하는 만큼 자유로운 순서로 해결하고, pass하면
  그 플레이어의 window는 다시 열리지 않는다. 아무도 Intrigue를 갖고 있지 않고
  wild 쌍도 없으면 window 없이 즉시 종료한다. 순서가 상태에 영향을 주는 공개
  효과가 없으므로 단일 순회로 충분하다는 판단이며,
  `tests/unit/rules/test_endgame.py`와 `tests/unit/rules/test_intrigue.py`로
  고정한다.

## OQ-002 — 동률 Combat reward 해결 순서

- 상태: `CONTENT`
- 공식 문서는 각 동률자의 reward 종류는 정하지만, 같은 rank의 여러 플레이어가
  선택을 포함한 reward를 어떤 순서로 resolve하는지는 정하지 않는다.
  `[Main p. 14]`
- 필요한 답: 실제 Conflict reward 전사 후 순서가 상태에 영향을 주는 사례가
  있는지 확인하고, 있다면 공식 판정을 찾는다.

## OQ-003 — Combat Intrigue 도중 참가 자격 변화

- 상태: `CONTENT`
- Combat 시작 규칙은 Conflict에 unit이 하나 이상 있는 플레이어만 priority를
  받는다고 한다. 진행 중 카드로 한 플레이어의 unit 수가 0↔1 이상으로 바뀔 때
  priority 순환에 언제 들어오거나 빠지는지는 설명하지 않는다. `[Main p. 14]`
- 필요한 답: 해당 변화를 만들 수 있는 현재 범위의 card가 있는지 콘텐츠 전사로
  확인한 뒤, 실제 사례가 있으면 공식 판정을 찾는다.
- 현재 범위 확인 결과(2026-08-28): Combat Intrigue 가운데 unit을 **줄이는** 카드는
  Go to Ground, Spice is Power, Tactical Option, Reach Agreement이고, Combat 중
  unit을 **늘리는** 카드는 없다.
- 구현 convention: (a) 카드 효과로 마지막 unit이 Conflict를 떠난 참가자는 그
  즉시 priority 순환에서 빠지며, 그 플레이어가 priority를 갖고 있었다면 시계
  방향의 다음 남은 참가자에게 넘어간다. 남은 참가자가 없으면 Combat Intrigue
  단계가 끝난다. (b) Combat 시작 시 unit이 없던 플레이어는 순환에 없고 이후에도
  들어올 수 없다. `tests/unit/rules/test_intrigue.py`로 고정한다.

## OQ-004 — Imperium Deck 완전 고갈

- 상태: `OPEN`
- Imperium Row는 항상 5장이어야 하며 빈자리를 Imperium Deck 위에서 즉시
  보충한다고 적혀 있지만, deck과 row가 함께 고갈되어 5장을 채울 수 없는 경우를
  다루지 않는다. 개인 deck과 Intrigue deck의 reshuffle 규칙은 별도로 있지만
  Imperium discard reshuffle 규칙은 제시되지 않는다. `[Main pp. 6, 13]`
- 필요한 답: row를 줄인 채 진행하는지 등 최신 공식 판정.
- 구현 convention(2026-08-30): 물리적으로 강제되는 유일한 진행을 따른다.
  Imperium Deck이 비면 Row의 빈자리는 보충하지 않고 Row는 남은 카드 수로
  계속 운영하며, 어떤 카드도 Imperium Deck으로 되돌아가지 않는다(공유
  Imperium discard 존과 reshuffle 규칙이 존재하지 않으므로). 획득·set-aside의
  모든 Row 제거 지점이 `rules/acquisition.py`의 `take_imperium_row_card`
  헬퍼를 공유한다. heuristic policy sweep이 실제로 이 상태에 도달함을
  확인했다(룰셋당 1,000판 중 기본 룰셋 6판이 `NotImplementedError`
  tripwire에 걸렸다).
  관측 인코딩의 row 세그먼트는 5 슬롯 고정이며 빈자리는 0으로 남는다.
  `tests/unit/rules/test_acquisition.py`와
  `tests/unit/rules/test_intrigue.py`로 고정한다.

## OQ-005 — 여러 matching battle icon 중 pair 선택

- 상태: `RESOLVED`
- Conflict 승자가 새 face-up icon과 같은 face-up Conflict/Objective를 이미 여러
  장 가졌을 때 어떤 한 장과 pair를 만들지, 선택권이 있는지 명시하지 않는다.
  Endgame wild icon도 후보가 여러 개일 수 있다. `[Main pp. 14, 20]`
- 콘텐츠 전사 완료 후 검토(2026-08-30): Combat의 즉시 matching은 공식
  콘텐츠에서 후보가 두 장 이상일 수 없다. setup은 플레이어당 Objective 한 장을
  주고, 이후 face-up battle card 추가는 승리한 Conflict뿐인데 도착 즉시 의무
  pair로 뒤집히므로 printed icon당 face-up은 최대 한 장이며, wild는 Propaganda
  한 장뿐이다. Endgame wild는 후보가 여러 개일 수 있고 어느 쪽을 뒤집는지가
  Endgame Intrigue flip 대상(승리한 Conflict 한정)에 실제로 영향을 주므로,
  OQ-001 window 안에서 소유자가 pair를 직접 고르는 행동으로 구현했다. 분석과
  soak 근거는
  [`../implementation-audits/objectives.md`](../implementation-audits/objectives.md)에
  있으며, 엔진은 Combat 다중 후보를 미래 콘텐츠 대비 guard로 계속 차단한다.

## OQ-006 — 한 space에 여러 opponent Agent가 있을 때 Infiltrate

- 상태: `CONTENT`
- Spy 규칙은 `다른 플레이어`의 Agent가 있는 space에 연결된 Spy 하나를 recall해
  그 Agent를 무시할 수 있다고 설명한다. 이미 Infiltrate가 반복되어 서로 다른
  opponent Agent가 둘 이상 있는 space에 새로 들어갈 때 Spy 하나로 충분한지는
  명시하지 않는다. `[Main p. 11]` `[FAQ p. 4]`
- 필요한 답: 현재 콘텐츠로 이 상태가 가능한지 확인하고 공식 판정을 찾는다.

## OQ-007 — Leader 선택 절차

- 상태: `OPEN`
- setup은 각 플레이어가 Leader를 선택하거나 무작위로 정한다고만 한다. 모두가
  선택할 때의 순서나 draft 방식은 정하지 않는다. 같은 House의 Leader를 동시에
  쓰지 않는 것은 story상 권장 사항이지 금지 규칙이 아니다. `[Main pp. 2, 4]`
- 필요한 답: 학습 환경의 Leader selection을 공식 setup 범위에서 어떻게
  표준화할지 별도 ruleset option으로 명시해야 한다. 이는 공식 규칙이라고
  표시해서는 안 된다.
- 구현 convention(2026-08-30, ruleset option — 공식 규칙 아님): **6종
  공개 draft**.
  1. 사용 룰셋의 합법 Leader 전체(기본 8종, CHOAM 켜면 Shaddam 포함
     9종)에서 무작위로 6종을 뽑아 즉시 전원에게 공개한다(seeded chance로
     replay 가능하게).
  2. Objective 배분으로 First Player가 정해진 뒤, 라운드 1 turn 순서의
     **역순**(마지막 turn 플레이어부터 시작해 First Player가 마지막)으로 한
     명씩 남은 pool에서 공개 선택한다.
  3. 모든 선택은 공개 정보이며, 선택되지 않은 2종은 그 게임에서 쓰지
     않는다(공개).
  - 공식 setup은 Leader 선택(`[Main p. 4]`)이 Objective/First Player
    결정(`[Main p. 5]`)보다 앞이지만, 이 convention은 pick 순서를 정의하기
    위해 Leader 선택을 First Player 확정 뒤로 옮긴다. 두 단계 모두 공개
    정보만 다루므로 정보 흐름은 달라지지 않는다.
  - 엔진에는 ruleset option으로 구현하고, 기존 고정 배정(테스트·sweep의
    `DEFAULT_LEADER_IDS`) 경로는 재현성 용도로 유지한다. 공식 draft 절차가
    발표되면 재검토한다.
  - 구현(2026-08-30): `RulesetConfig(leader_draft=True)`가 이 convention을
    켠다. reset이 pick과 무관한 setup chance를 모두 seeded 해결한 뒤
    `GamePhase.SETUP`의 `leader_draft` frame에서 멈추고, pick마다 좌석을
    확정(setup face, 인쇄된 시작 카드 제거는 이미 섞인 덱에서 필터링 —
    남은 순서는 균등 유지)하며, 마지막 pick이 Contract 시장을
    배분한다(Shaddam pick 시 Sardaukar set-aside). codec v79의
    `pick_leader` 템플릿, 관측 v2의 공개 pool 세그먼트.
    `tests/unit/rules/test_leader_draft.py`로 고정한다.

## OQ-008 — Control bonus와 방문자 효과의 상대 순서

- 상태: `CONTENT`
- controller는 누구든 controlled space에 Agent를 보내면 bonus를 받는다. 방문자는
  자신의 board/card/Faction 효과 순서를 고를 수 있지만, controller bonus가 그
  순서 안에 포함되는지는 명시하지 않는다. `[Main pp. 9-10]`
- 필요한 답: 순서가 영향을 주는 card interaction이 있는지 전사 후 확인한다.

## OQ-009 — observation post 연결 graph

- 상태: `RESOLVED`
- 공식 Main pp. 4-5의 setup board artwork에서 observation post 13개와 모든 직접
  연결선을 전사했다. 결과와 검증 주의사항은
  [`observation-posts.md`](observation-posts.md)에 있다.
- 텍스트 Board Space Guide에는 이 graph가 없으므로 이후 변경도 board artwork나
  공식 textual listing과 대조해야 한다. `[Main pp. 4-5 board artwork]`

## OQ-010 — 손패·discard와 과거 공개 정보의 열람 범위

- 상태: `OPEN`
- 공식 규칙은 Intrigue identity를 play 전까지 opponent에게 공개하지 않는다고
  명시하고, 여러 deck을 face-down, discard를 face-up으로 놓게 한다. 하지만 일반
  hand identity/장수, discard 전체 검사, deck 장수, 한 번 공개됐다가 face-down이
  된 카드의 재확인 가능 여부를 포괄적으로 정의하지 않는다.
  `[Main pp. 4-7, 12-14, 16, 20]`
- 필요한 답: 공식 FAQ/ruling 또는 tournament rule에서 각 정보의 열람 가능성을
  확인한다. 답을 얻기 전 RL `PlayerView`의 비공개 정책은 프로젝트 convention임을
  명시하고 규칙 사실처럼 적지 않는다.
- 구현 convention(2026-08-30, 부분): 존의 **장수**(각 플레이어의 hand·개인
  deck·discard 장수, 보유 Intrigue 장수)는 실물 테이블에서 항상 보이는
  정보이므로 `PublicPlayerView`에 공개한다. 카드 **identity**의 열람 범위는
  계속 이 항목의 미해결 질문으로 남으며, 기존 공개/비공개 구분(Intrigue
  identity는 play 전 비공개 등)은 바꾸지 않는다. 공식 근거가 아닌 관측 설계
  결정이며 `tests/unit/test_observation.py`로 고정한다.
- 구현 convention(2026-08-31, 추가): M11 서버의 종료 후 replay 검토도 같은
  경계를 따른다 — 검토는 사람 좌석의 `PlayerView` 시점 재생만 제공하고,
  step 라벨은 검토 좌석 자신의 행동만 상세히, 다른 좌석의 행동은 행동
  주체만, chance 결과는 decision id만 노출한다(셔플 결과는 비공개 덱
  순서를 그대로 담으므로). 게임 종료 후 전체 공개(상대 hand·덱 순서 열람)
  여부는 이 항목의 미해결 질문으로 남는다. `tests/server/test_saves.py`로
  고정한다.

## OQ-011 — Gather Intelligence와 contract 완료의 상대 순서

- 상태: `OPEN`
- Gather Intelligence는 Agent를 놓은 `immediately after`에, board space나 Agent
  card 효과보다 먼저 선택한다. FAQ는 space 방문형 contract 완료가 Agent-turn
  효과이고 board space·Agent box와 자유롭게 순서를 정한다고 설명한다. 하지만
  contract 완료를 Gather Intelligence 전에도 처리할 수 있는지는 직접 말하지
  않는다. `[Main p. 11]` `[FAQ p. 1]`
- 필요한 답: contract completion과 Gather Intelligence 중 어느 decision window가
  먼저인지에 대한 공식 판정.
- 구현 convention: 공식 판정을 찾기 전에는 Main p. 11의 `immediately after`를
  우선해 Gather Intelligence를 먼저 완료하고, 그 뒤 contract·board space·Agent
  box 효과의 자유 순서 창을 연다. 이 순서는 공식 사실이 아니라 프로젝트 판정이며
  contract 회귀 테스트로 고정한다.

## OQ-012 — 자유 순서 그룹 밖 의무 효과의 충돌

- 상태: `CONTENT`
- Main은 board space, Agent box, Faction Influence의 처리 순서를 자유롭게 고르게
  하고 FAQ는 space형 contract를 그 그룹에 추가한다. 그 밖의 여러 의무 효과가
  동시에 적용되어 서로 충돌할 때의 일반 우선순위는 제시하지 않는다.
  `[Main p. 9]` `[FAQ pp. 1, 3]`
- 필요한 답: 콘텐츠 전사 후 실제 충돌 사례별 공식 판정을 확인한다.
- 현재 구현 convention: The Spice Must Flow를 acquire할 때 기존 카드의 acquire
  trigger를 먼저 처리하고, 그 뒤 Acquire Contract를 완료한다. standard Acquire
  Contract의 보상은 Spacing Guild Influence 1과 Solari 3뿐이지만, Influence
  경계·Alliance 때문에 순서가 관측될 수 있으므로 공식 일반 판정이 나오면 다시
  검토한다.

## OQ-013 — Clean Up 이동과 일반적인 `discard` 반응

- 상태: `RESOLVED`
- 현재 Uprising 기본 Imperium 콘텐츠의 discard trigger는 Spacing Guild's Favor
  하나뿐이며, Main은 이 카드가 hand에서 discard될 때만 발동한다고 직접 정한다.
  구현은 hand-discard transition에서만 trigger를 처리하고 Reveal Clean Up은
  in-play 카드를 직접 discard pile로 이동한다. 다른 확장 콘텐츠에서 새 discard
  trigger를 추가하면 해당 카드의 문구와 판정을 별도로 재검토한다.
  `[Main pp. 12, 17]`

## OQ-014 — Alliance 상실 때 여러 수령 후보

- 상태: `RESOLVED`
- Captured Mentat의 한 칸 Influence 감소로 실제 상태를 검토했다. 유효한 Alliance
  보유자가 4에서 3으로 내려갈 때 Influence 4 이상인 다른 플레이어는 감소 직전
  모두 보유자와 4에서 동률이므로 FAQ의 기존 보유자 선택 규칙이 적용된다. 보유자가
  5 이상이면 한 칸 감소 뒤에도 4 이상이라 token 반환 조건에 들어가지 않는다.
  여러 칸 감소도 한 칸씩 처리하면 같은 결론이 반복되므로, 직전 동률자가 아닌
  복수 수령 후보 상태는 유효한 track 전이에서 발생하지 않는다.
  `[Main p. 7]` `[FAQ p. 1]`
- 구현은 감소 직전 동률 후보가 여러 명이면 기존 보유자의 명시적 선택을 요구한다.

## 판정이 생겼을 때 기록할 정보

각 항목을 닫을 때 다음을 함께 남긴다.

1. 공식 답변 URL 또는 새 룰북/FAQ의 문서명·버전·페이지
2. 이 명세에서 바뀐 문장
3. 구현에 선택지가 남았다면 공식 규칙과 project convention의 명확한 구분
4. 해당 edge case를 재현하는 scenario test

## OQ-016 — face-up trigger Intrigue의 수명

- 상태: `OPEN`
- FAQ는 효과가 아직 적용되지 않는 Intrigue를 "그때까지 face up으로 두고, 그
  다음 사용하고 discard한다"고 한다. 그러나 (a) trigger 창이 지나가도록 한 번도
  발동하지 못한 카드(예: Call to Arms를 두고 Reveal에서 아무 카드도 acquire하지
  않은 경우)를 언제 discard하는지, (b) "whenever" 반복 trigger의 discard 시점이
  창의 끝인지 첫 발동인지, (c) 선택적 trigger("you may")를 거절하면 카드가
  face up으로 남는지는 명시하지 않는다. `[FAQ p. 2]`
- 필요한 답: face-up Intrigue의 만료와 거절 시 처리에 대한 공식 판정.
- 구현 convention: (a)(b) 창이 명시된 카드(Call to Arms의 "이번 round의 자신의
  Reveal turn")는 그 창이 닫힐 때(Reveal turn 종료) 발동 여부와 무관하게
  discard한다. "whenever" trigger는 창이 닫힐 때까지 반복 발동한다.
  (c) 선택적 trigger(Distraction)를 거절한 카드는 사용된 것이 아니므로 face up
  으로 남아 이후의 조건 충족 turn에 다시 제시된다. 같은 turn에서는 배치 수가
  마지막 제시 시점보다 늘었을 때만 다시 제시하며, 이미 제시가 지나간 수치에서
  나중에 낸 두 번째 사본은 다음 배치 때 제시된다. 세 판정 모두
  `tests/unit/rules/test_intrigue.py`로 고정한다.

## OQ-015 — Intrigue의 Plot timing 시작점과 복수 비용 줄의 의무 지불

- 상태: `OPEN`
- Main은 Plot Intrigue를 자신의 Agent turn 또는 Reveal turn 도중 사용할 수 있다고
  하고, FAQ는 Intrigue를 play하면 조건을 충족하고 비용을 지불해야 한다고 한다.
  하지만 (a) Agent/Reveal 선택을 확정하기 전, 즉 turn이 막 시작된 시점이 "turn
  도중"에 포함되는지, (b) Strategic Stockpiling처럼 비용 줄이 둘이고 그중 하나가
  Influence 조건으로 열리는 카드에서 조건을 만족하면 두 비용을 모두 지불해야
  하는지는 명시하지 않는다. `[Main pp. 7-8]` `[FAQ p. 2]`
- 필요한 답: Plot play window의 시작점과, 조건부로 열린 두 번째 비용 줄의 의무
  여부에 대한 공식 판정.
- 구현 convention: (a) 소유자에게 turn 선택이 제시된 순간부터 Plot을 낼 수 있고,
  Agent turn의 마지막 pending 그룹이 해결되면 turn이 자동으로 넘어가므로 그
  전에 내야 한다. (b) 조건이 성립한 모든 비용 줄은 의무이며, 전부 지불할 수 없으면
  카드를 낼 수 없다. (c) Reveal turn 중 card가 hand에 들어가는 Plot — 개인 card
  draw, 그리고 Inspire Awe처럼 조건이 성립해 hand로 acquire하는 경우 — 은
  이제 Reveal turn 중에도 제시한다. hand에 들어간 card는 FAQ p. 3의 즉시
  공개 규칙에 따라 그 자리에서 revealed된다: hand → in_play로 옮기고, 더
  커진 revealed 집합 기준으로 자신의 Reveal 기여분(설득·검·자원·선택 효과)을
  얻어 같은 Reveal turn에 사용한다. 앞서 Reveal에서 이미 지급된 금액은
  확정이며 다시 계산하거나 회수하지 않는다. 늦게 도착한 card의
  per_revealed_faction·strength_per_other_sword_card 같은 교차 효과는 그
  도착이 이미 revealed된 다른 card들에 일으키는 증분만 더하고, 그 증분을 줄
  자격은 도착 시점 조건으로 다시 판정한다. discard로 acquire하는 형태는
  Reveal 중에도 그대로 제시한다. 현재 콘텐츠의 교차 효과 3종
  (Stilgar, Sardaukar Coordination, Leadership)은 모두 자격 조건이 없어 이
  재판정이 항상 공허하며, `tests/unit/rules/test_reveal_turn.py`의 pin
  테스트로 고정한다(자격 조건이 있는 교차 효과가 새로 추가되면 회수 로직이
  없는 이 구현이 실패하도록 하는 장치). (d) 한 option 안의 선택
  슬롯(trash, Spy 등)은 자동 보상(draw 등)보다 먼저 해결하므로 Cunning처럼
  "draw 후 trash"로 인쇄된 카드에서 방금 draw한 card는 trash 대상이 되지 않는다.
  네 판정 모두 프로젝트 convention이며 `tests/unit/rules/test_intrigue.py`로
  고정한다.


## OQ-017 — Feyd token이 맨 오른쪽에 있을 때의 Signet 보상

- 상태: `OPEN`
- Personal Training은 "Move your Feyd token one space to the right on your
  Training track, earning the reward on the new space"라고 인쇄돼 있고, Main은
  token이 맨 오른쪽 칸에 도달하면 게임 끝까지 그 자리에 남는다고만 말한다.
  token이 더 이동할 수 없을 때 Signet Ring play가 무언가를 주는지는 명시하지
  않는다. `[Feyd-Rautha Harkonnen card]` `[Main p. 17]`
- 필요한 답: 맨 오른쪽 칸에서 Signet Ring을 냈을 때 보상 유무의 공식 판정.
- 구현 convention(2026-08-29): 카드가 보상을 "새 칸"에 결부시키므로 이동이
  없으면 보상도 없다. Signet Ring 카드 자체는 여전히 Agent를 보낸다.
  `tests/unit/rules/test_leader_abilities.py`로 고정한다.

## OQ-018 — memory 0개일 때의 Other Memories 사용 가능 여부

- 상태: `OPEN`
- Other Memories는 "you may return all your memories to your supply, drawing
  a card for each one. Then flip this Leader over"라고 인쇄돼 있다. memory가
  하나도 없을 때 이 능력을 써서(아무것도 되돌리지 않고) flip만 할 수 있는지는
  공식 문서에 없다. `[Lady Jessica card]`
- 필요한 답: memory 0개 상태에서 능력 사용(즉 flip)이 허용되는지의 공식 판정.
- 구현 convention(2026-08-29): "all your memories"는 0개를 포함하는 것으로
  읽어 사용을 허용한다(retreat의 `any number`가 0을 허용하는 FAQ 판정과 같은
  방향, `[FAQ p. 3]` 참고). draw는 0장이고 flip은 일어난다.

## OQ-019 — Reverend Mother 반복의 적용 범위

- 상태: `OPEN`
- Reverend Mother는 "repeat the effects printed on that space"라고 인쇄돼
  있다. Faction board space 방문으로 얻는 Influence 1이 "그 space에 인쇄된
  효과"에 포함되는지, space의 비용을 다시 지불해야 하는지는 공식 문서에 없다.
  `[Reverend Mother Jessica card]`
- 필요한 답: 반복 대상의 정확한 범위에 대한 공식 판정.
- 구현 convention(2026-08-29): Influence는 "Faction의 board space에 Agent를
  보내면" 얻는 Faction 규칙이지 space의 인쇄 효과가 아니므로 반복하지 않는다
  `[Main p. 7]`. space 비용도 효과가 아니므로 재지불하지 않고, 반복은 인쇄
  효과 상자(board 효과 경로)만 다시 해결한다.
  `tests/unit/rules/test_leader_abilities.py`로 고정한다.

## OQ-020 — Always Smiling 부여 뒤 strength가 내려간 경우

- 상태: `OPEN`
- Always Smiling은 "Reveal Turn: If you have 6* or more strength in the
  Conflict: 1 Persuasion"이다. Persuasion을 부여받은 뒤 같은 Reveal turn에
  retreat 등으로 strength가 6 미만으로 내려가면 Persuasion을 회수해야 하는지는
  공식 문서에 없다. `[Gurney Halleck card]`
- 필요한 답: 조건이 사후에 깨졌을 때의 공식 판정.
- 구현 convention(2026-08-29): 조건이 처음 성립한 시점에 1회 부여하고 회수하지
  않는다. Persuasion은 이미 지출됐을 수 있는 turn 자원이라 회수가 정의되지
  않기 때문이다. `tests/unit/rules/test_leader_abilities.py`로 고정한다.

## OQ-021 — 시장이 빈 뒤의 set-aside Sardaukar contract 접근

- 상태: `OPEN`
- Shaddam의 카드는 "Only you can acquire them during the game"이라 하고, FAQ는
  Sardaukar Commander가 "일반적으로 얻을 수 있는 contract 대신(in place of)"
  set-aside contract를 acquire할 선택권을 준다고 한다. Main은 "모든 contract를
  플레이어들이 가져갔다면" contract 아이콘이 2 Solari로 되돌아간다고 한다.
  face-up 시장과 bank가 모두 비었지만 set-aside가 남아 있을 때 Shaddam의
  contract 아이콘이 여전히 set-aside를 가져올 수 있는지는 어느 문서도 직접
  답하지 않는다. `[Shaddam Corrino IV card]` `[FAQ p. 3]` `[Main p. 16]`
- 필요한 답: 시장 고갈 후 set-aside 접근 가능 여부의 공식 판정.
- 구현 convention(2026-08-30): FAQ의 "in place of one of the generally
  available contracts"를 따라 set-aside 선택은 열린 contract 시장 frame에서만
  제시하고, 시장이 고갈되면 Shaddam의 contract 아이콘도 다른 플레이어처럼
  2 Solari로 전환한다. 반대 해석(그의 아이콘은 set-aside가 남는 한 되돌아가지
  않음)도 가능하므로 공식 판정이 나오면 재검토한다.
  `tests/unit/rules/test_leader_abilities.py`로 고정한다.

## OQ-022 — Agent 효과 해결 전에 play된 카드 자체가 trash될 때

- 상태: `OPEN`
- Agent turn의 자유 순서 안에서, play된 카드의 Agent box가 해결되기 전에
  Intrigue의 trash 슬롯(예: Cunning) 등으로 그 카드 자체를 in play에서 trash할
  수 있다. 공식 문서는 화살표 없는 자기 trash가 의무라고 정할 뿐
  (`[FAQ p. 3]`), 이미 다른 효과로 trash된 카드의 보류 중인 Agent box를 어떻게
  해결하는지는 답하지 않는다. `[Main pp. 9, 20]`
- 필요한 답: play된 카드가 해결 전에 zone을 떠났을 때 그 카드의 인쇄 효과가
  여전히 해결되는지의 공식 판정.
- 구현 convention(2026-08-30): 의무 효과의 나머지 부분(예: Subversive Advisor의
  Influence 2)은 그대로 해결하고, 자기 자신에 대한 trash 지시는 카드가 이미
  trash 존에 있으므로 이미 충족된 것으로 본다
  (`agent_card_self_trash_satisfied` event). 자기 자신을 hand로 되돌리는
  효과(Weirding Woman)는 카드가 게임에서 제거됐으므로 무효로 해결한다. 조건부
  효과(Bond, Influence 문턱)는 해결 시점에 다시 판정한다(`[Main pp. 9, 20]`의
  자유 순서 판정). `tests/unit/rules/test_agent_effects.py`로 고정한다.
- 적용 확장(2026-09-01): 같은 convention을 Dangerous Rhetoric의
  `TRASH_SELF_AND_GAIN_CHOSEN_INFLUENCE` 분기에도 적용했다(Desert Tactics의
  board trash가 Spy 아이콘으로 그 칸에 낸 카드 자체를 잡을 수 있어 random
  sweep CHOAM seed 2735에서 적발). 반대로 Delivery Agreement의 "trash해서
  VP" 선택은 화살표 없는 지시가 아니라 **비용**이므로, 카드가 이미 trash된
  뒤에는 충족으로 보지 않고 해결 시점 판정(`[Main pp. 9, 20]`)에 따라 그
  선택지를 제시하지 않는다. `tests/unit/rules/test_reveal_turn.py`,
  `tests/integration/test_sweep.py`로 고정한다.

## OQ-023 — Imperial Privilege의 recall 의무와 대상 부재 시 처리

- 상태: `OPEN`
- Board Space Guide는 Imperial Privilege의 효과를 "원하면 Intrigue 1장을
  discard하고 Intrigue 1장을 draw. 이번 turn에 보낸 Agent가 아닌 자신의 다른
  Agent 1개를 recall하고 card 1장을 draw"로 인쇄한다. 첫 문장에만 선택
  표지("원하면")가 있고, 다른 배치된 Agent가 하나도 없을 때 recall과 그에
  결부된 card draw가 어떻게 되는지는 답하지 않는다. `[Board Guide p. 2]`
- 필요한 답: recall 절이 의무인지, 그리고 recall 대상이 없을 때 card draw만
  따로 발생하는지의 공식 판정.
- 구현 convention(2026-09-01): 선택 표지가 없는 recall 절은 대상이 있으면
  의무이며, 어느 Agent를 recall할지는 소유자가 고른다. 다른 배치된 Agent가
  없으면 절 전체(recall과 draw)가 무효화되어 draw도 발생하지 않는다 — draw는
  "recall하고 draw"로 recall에 결부돼 있기 때문이다. recall 대상은 Intrigue
  슬롯이 해결된 뒤의 해결 시점에 판정한다(`[Main pp. 9, 20]`).
  `tests/unit/rules/test_board_effects.py`로 고정한다.
