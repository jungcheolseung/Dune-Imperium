# CHOAM Module

CHOAM Module은 Uprising에 포함된 mini-expansion이다. 공식 룰북은 먼저 module 없이
게임에 익숙해진 뒤 추가하기를 권한다. 프로젝트의 첫 완성 룰셋도 module을 끄고,
이 문서의 규칙은 이후 `choam_module=True`일 때 적용한다. `[Main p. 16]`

## module을 끈 게임

- CHOAM 표시가 있는 Imperium card 4장과 Intrigue card 4장을 각 deck에서
  제외한다. Leader로 Shaddam Corrino IV를 선택할 수 없다.
  `[Main pp. 3-4, 16]`
- contract icon의 효과는 contract를 가져가는 대신 2 Solari다.
  `[Main pp. 16, 20]`

## 추가 구성물과 setup

- standard contract 20개를 face-down으로 shuffle한다. 그중 2개를 face-up으로
  board의 표시된 두 칸에 놓고, 나머지 18개를 face-down bank에 둔다.
  `[Main p. 16]`
- module 전용 Imperium card 4장을 Imperium Deck에, Intrigue card 4장을 Intrigue
  Deck에 섞는다. Shaddam Corrino IV를 Leader로 선택할 수 있지만 반드시 선택할
  필요는 없다. `[Main p. 16]`
- Uprising에 든 뒷면이 다른 Rise of Ix용 contract 10개와 그 setup은 Rise of Ix를
  함께 쓸 때만 사용한다. 현재 4인 Uprising-only 룰셋에는 넣지 않는다.
  `[Main p. 16]`

## contract 가져오기

- contract icon을 resolve하면 board의 face-up contract 하나를 골라 자신의
  supply에 face-up으로 놓는다. face-down bank에 contract가 남아 있으면 그중
  하나를 face-up으로 뒤집어 빈자리를 보충한다. `[Main p. 16]`
- bank의 face-down stack이 비었더라도 board에 face-up contract가 남아 있으면
  남은 contract를 가져간다. 모든 contract가 플레이어에게 넘어가 face-up
  contract도 남지 않았을 때 contract icon은 2 Solari로 돌아간다.
  `[Main p. 16]`

## contract 완료 조건

- 특정 board space 이름이 적힌 contract는 해당 space에 Agent를 보내면
  완료한다. `[Main p. 16]`
- Harvest contract는 Maker space에 Agent를 보내고, 그 turn에 모든 출처를
  합쳐 contract에 표시된 양의 spice를 얻으면 완료한다. `[Main p. 16]`
- Immediate contract는 가져오는 즉시 완료한다. `[Main p. 16]`
- Acquire The Spice Must Flow contract는 다음에 The Spice Must Flow를 acquire할
  때 완료한다. `[Main p. 16]`
- 이미 이번 turn에 Agent를 보낸 space와 관련된 contract를 그 turn 도중 새로
  가져와도 소급해 완료하지 않는다. Agent를 보낼 당시 contract를 보유하고
  있어야 하며, 아니면 이후 turn까지 기다린다. `[Main p. 16]`

## 완료 처리

- 조건을 만족한 contract는 반드시 완료한다. 같은 board space 조건의 contract를
  여러 개 보유했다면 한 번의 Agent 방문으로 모두 완료한다. `[FAQ p. 1]`
- 완료 사실을 알리고 표시된 reward를 받은 뒤 contract를 face-down으로 뒤집어
  자신의 supply에 둔다. completed contract를 참조하는 카드가 있으므로 제거하지
  않는다. `[Main p. 16]`
- board space 방문형 contract 완료는 Agent turn의 효과다. contract 효과와
  board space 효과, play한 card의 Agent box 효과는 플레이어가 순서를 정해
  처리할 수 있다. `[FAQ p. 1]`
- Gather Intelligence는 Agent를 놓은 직후 board space나 Agent card 효과보다
  먼저 결정한다. 공식 문서는 이 즉시 window와 contract 완료의 상대 순서를
  직접 명시하지 않는다. 공식 판정을 찾기 전 프로젝트 구현은 Gather
  Intelligence를 먼저 처리한다. 이 convention은
  [OQ-011](open-questions.md#oq-011--gather-intelligence와-contract-완료의-상대-순서)로
  남긴다. `[Main p. 11]` `[FAQ p. 1]`

## Shaddam 관련 경계

Shaddam의 setup 구성물과 두 능력은 Leader 및 별도 Sardaukar contract의 실제
card text를 콘텐츠 명세에 전사한 뒤 구현한다. FAQ는 Sardaukar Commander가
일반 face-up contract 대신 set-aside Sardaukar contract를 acquire할 선택권을
주며, 그 contract를 게임 시작 시 이미 보유한 것으로 보지 않는다고 명확히 한다.
Emperor of the Known Universe의 제한은 발동한 **그 turn**에만 적용된다.
Signet Ring으로 Agent를 보낼 때 그 제한은 즉시 적용된다. `[Main p. 17]`
`[FAQ p. 3]`

## 구현 상태

standard contract 20장의 identity·setup, 공개 시장의 take/refill·고갈, 모든
완료 조건과 인쇄 보상은 구현돼 있다. 공간 방문 시 보유하던 contract를 snapshot해
소급 완료를 막고, Harvest의 그 turn Spice 획득 합계와 The Spice Must Flow acquire
trigger도 연결한다. Shaddam의 set-aside Sardaukar contract 선택은 Leader 구현
단위로 남아 있다. 세부 상태·관측·codec 경계는
[Contract 구현 audit](../implementation-audits/contracts.md)에 기록한다.
