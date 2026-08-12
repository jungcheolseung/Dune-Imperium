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

## OQ-004 — Imperium Deck 완전 고갈

- 상태: `OPEN`
- Imperium Row는 항상 5장이어야 하며 빈자리를 Imperium Deck 위에서 즉시
  보충한다고 적혀 있지만, deck과 row가 함께 고갈되어 5장을 채울 수 없는 경우를
  다루지 않는다. 개인 deck과 Intrigue deck의 reshuffle 규칙은 별도로 있지만
  Imperium discard reshuffle 규칙은 제시되지 않는다. `[Main pp. 6, 13]`
- 필요한 답: row를 줄인 채 진행하는지 등 최신 공식 판정.

## OQ-005 — 여러 matching battle icon 중 pair 선택

- 상태: `CONTENT`
- Conflict 승자가 새 face-up icon과 같은 face-up Conflict/Objective를 이미 여러
  장 가졌을 때 어떤 한 장과 pair를 만들지, 선택권이 있는지 명시하지 않는다.
  Endgame wild icon도 후보가 여러 개일 수 있다. `[Main pp. 14, 20]`
- 필요한 답: 어느 카드를 뒤집는지가 다른 card effect에 실제 영향을 주는지 콘텐츠
  전사 후 확인하고, 필요하면 공식 판정을 찾는다.

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

## OQ-011 — Gather Intelligence와 contract 완료의 상대 순서

- 상태: `OPEN`
- Gather Intelligence는 Agent를 놓은 `immediately after`에, board space나 Agent
  card 효과보다 먼저 선택한다. FAQ는 space 방문형 contract 완료가 Agent-turn
  효과이고 board space·Agent box와 자유롭게 순서를 정한다고 설명한다. 하지만
  contract 완료를 Gather Intelligence 전에도 처리할 수 있는지는 직접 말하지
  않는다. `[Main p. 11]` `[FAQ p. 1]`
- 필요한 답: contract completion과 Gather Intelligence 중 어느 decision window가
  먼저인지에 대한 공식 판정.

## OQ-012 — 자유 순서 그룹 밖 의무 효과의 충돌

- 상태: `CONTENT`
- Main은 board space, Agent box, Faction Influence의 처리 순서를 자유롭게 고르게
  하고 FAQ는 space형 contract를 그 그룹에 추가한다. 그 밖의 여러 의무 효과가
  동시에 적용되어 서로 충돌할 때의 일반 우선순위는 제시하지 않는다.
  `[Main p. 9]` `[FAQ pp. 1, 3]`
- 필요한 답: 콘텐츠 전사 후 실제 충돌 사례별 공식 판정을 확인한다.

## OQ-013 — Clean Up 이동과 일반적인 `discard` 반응

- 상태: `CONTENT`
- Reveal Clean Up은 in-play 카드를 discard pile로 옮긴다. Main은 Spacing Guild's
  Favor에 한해 이 이동이 그 카드의 discard ability를 발동하지 않고 hand에서의
  discard만 발동한다고 명시하지만, 모든 `discard` 반응에 적용되는 일반 규칙은
  제시하지 않는다. `[Main pp. 12, 17]`
- 필요한 답: 콘텐츠 전사 후 같은 표현을 쓰는 다른 카드가 있는지 확인하고,
  있다면 해당 카드별 공식 판정을 찾는다.

## OQ-014 — Alliance 상실 때 여러 수령 후보

- 상태: `CONTENT`
- 보유자가 Influence를 잃기 전에 다른 플레이어들과 동률이었다면 기존 보유자가
  그중 수령자 한 명을 정한다. 보유자가 3 이하로 내려갔을 때 다른 플레이어가
  4 이상이면 token을 board로 돌리지 않는다. 그러나 직전 동률자가 아닌 4 이상
  후보가 여러 명인 상태에서 어느 한 명이 받는지는 FAQ가 직접 정하지 않는다.
  `[Main p. 7]` `[FAQ p. 1]`
- 필요한 답: 실제 콘텐츠로 해당 상태가 가능한지 확인한 뒤 공식 판정을 찾는다.

## 판정이 생겼을 때 기록할 정보

각 항목을 닫을 때 다음을 함께 남긴다.

1. 공식 답변 URL 또는 새 룰북/FAQ의 문서명·버전·페이지
2. 이 명세에서 바뀐 문장
3. 구현에 선택지가 남았다면 공식 규칙과 project convention의 명확한 구분
4. 해당 edge case를 재현하는 scenario test
