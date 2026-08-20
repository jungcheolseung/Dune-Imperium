# 공식 규칙 source map

이 문서는 Uprising 기본 게임 4인 규칙 명세가 공식 자료의 어느 항목을
반영하는지 추적한다. 표의 상태는 다음 뜻으로만 사용한다.

- `covered`: 표시한 `rules/*.md`에 규칙이 명시되어 있다.
- `out of scope`: 1차 구현 범위가 아니거나 전략 팁·예시·크레딧·세계관처럼
  규칙이 아닌 내용이다.
- `deferred to content manifest`: 일반 규칙이 아니라 개별 카드, Leader, contract,
  Tech tile의 데이터 또는 판정이다. 이후 content manifest에 넣고
  [official-rulings-index.md](official-rulings-index.md)에서 출처를 찾을 수 있게 한다.
- `open question`: 현재 규칙 문서에 필요한 판정이 없거나, 지정된 공식 텍스트만으로
  구현 판정을 하나로 정할 수 없다. [open-questions.md](open-questions.md)에서 추적한다.

`deferred to content manifest`는 별도의 새 `rules/*.md`를 뜻하지 않는다. 개별
콘텐츠를 전사할 때 [공식 판정 색인](official-rulings-index.md)의 해당 항목과
연결한다.

## Main Rulebook

### Main pp. 3-8: 구성물, setup, 기본 개념

| 출처 | 규칙 주제 | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- | --- |
| `[Main p. 3]` | 플레이어별 Agent, marker, cube, disc, Spy와 10장 starting deck의 구성 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 3]` | board, 자원, Reserve·Imperium·Conflict·Intrigue·Objective, Leader, sandworm, Shield Wall, Maker Hooks, Alliance token, First Player marker의 수량 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 3]` | CHOAM 전용 카드와 Leader가 기본 구성물에 섞여 있다는 구분 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [choam-module.md](choam-module.md) |
| `[Main p. 3]` | 1·2인 Rivals 및 6인 추가 구성물 안내 | `out of scope` | 현재 4인 규칙셋에서 제외 |
| `[Main p. 4]` | board 면, Shield Wall, 네 Alliance token 배치 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 4]` | Conflict I 1장, II 5장, III 4장으로 10장 Conflict deck 구성 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 4]` | CHOAM 표시를 제외한 Intrigue·Imperium deck, Imperium Row 5장, 두 Reserve stack setup | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 4]` | Leader 공개 선택 또는 무작위 선택, module을 끄면 Shaddam 제외 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [choam-module.md](choam-module.md) |
| `[Main p. 4]` | 여러 플레이어가 Leader를 직접 고를 때의 선택 순서·draft 방식 | `open question` | [OQ-007](open-questions.md#oq-007--leader-선택-절차) |
| `[Main p. 4]` | Leader 난이도 아이콘과 첫 게임 추천 | `out of scope` | 전략 조언이며 규칙 상태가 아님 |
| `[Main p. 5]` | starting deck 배치, water 지급, 무제한 bank와 Maker Hooks setup | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 5]` | 색상 선택, Agent·Swordmaster, Score·Combat marker, 네 Influence cube, garrison troop, 공개 supply setup | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 5]` | 인원수에 맞는 Objective 배포와 First Player 결정 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 5]` | Uprising의 Mentat·Foldspace 부재와 Spy·sandworm·Maker Hooks 추가 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 5]` | 1·2·6인 추가 setup 안내 | `out of scope` | 현재 4인 규칙셋에서 제외 |
| `[Main p. 6]` | VP 증감, 라운드 종료 때 10 VP 또는 빈 Conflict deck으로 Endgame 진입 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 6]` | Leader의 일반 능력과 Signet Ring 능력 | `covered` | [uprising-systems.md](uprising-systems.md), [player-turns.md](player-turns.md) |
| `[Main p. 6]` | acquire한 카드의 discard 이동, 빈 deck 재구성, trash | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 6]` | Agent 2개로 시작, 세 번째 Agent 획득, 카드 없이 Agent를 보낼 수 없음 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [player-turns.md](player-turns.md) |
| `[Main p. 6]` | 카드 텍스트가 일반 규칙을 바꿀 수 있음 | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 6]` | Great House와 galactic figure를 전제로 한 Objective 도입 문구 | `out of scope` | 세계관 설명은 규칙 명세가 아님 |
| `[Main p. 7]` | 네 Faction, Influence 증감, 2 Influence VP, 4 Influence bonus | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 7]` | Alliance 획득, 더 높은 Influence의 상대에게 token과 VP 이전 | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[FAQ p. 1]` | Alliance 보유자가 3 이하로 내려갈 때 4 이상 수령 후보가 여러 명인 경우 | `covered` | [uprising-systems.md](uprising-systems.md), [OQ-014](open-questions.md#oq-014--alliance-상실-때-여러-수령-후보) |
| `[Main p. 7]` | Intrigue의 비공개 보관·확인·공개·공용 discard와 Plot·Combat·Endgame 시점 | `covered` | [player-turns.md](player-turns.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 7]` | Faction 세계관 설명을 p. 2에서 참조 | `out of scope` | 세계관 설명은 규칙 명세가 아님 |
| `[Main p. 8]` | 다섯 phase 순서, Conflict 공개, 각자 5장 draw | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 8]` | First Player부터 시계 방향 turn, Agent/Reveal 선택, Reveal 뒤 turn 종료 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [player-turns.md](player-turns.md) |
| `[Main p. 8]` | 자신의 Agent 또는 Reveal turn 중 Plot Intrigue 사용 | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 8]` | Agent box·Reveal box와 한 turn에 해당 box 하나만 사용 | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 8]` | card name·Faction·Agent icons·Persuasion cost·Acquire box라는 anatomy field | `deferred to content manifest` | field 값은 card 데이터에 두고 일반 icon 동작은 각 규칙 문서에서 처리 |

### Main pp. 9-13: Player Turns

| 출처 | 규칙 주제 | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- | --- |
| `[Main p. 9]` | 카드 1장과 일치하는 Agent icon 하나로 Agent 1개 배치, icon 없는 카드는 Agent turn 불가 | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 9]` | 기본 점유 제한과 Spy 예외 | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 9]` | 공간 비용의 선지불과 Imperial Privilege·Shipping·Sietch Tabr Influence requirement | `covered` | [player-turns.md](player-turns.md), [board-spaces.md](board-spaces.md) |
| `[Main p. 9]` | space, Agent box, Faction Influence 효과의 자유로운 처리 순서 | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 9]` | arrow 비용은 선택, 미지불 시 결과 없음, 한 turn에 한 번 | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 9]` | 명시적으로 순서를 허용한 효과 밖에서 여러 의무 효과가 충돌할 때의 우선순위 | `open question` | [OQ-012](open-questions.md#oq-012--자유-순서-그룹-밖-의무-효과의-충돌); [player-turns.md](player-turns.md)에도 미확정으로 표시 |
| `[Main p. 10]` | Arrakeen·Spice Refinery·Imperial Basin control 획득, 방문 bonus, 방어 troop 배치 | `covered` | [uprising-systems.md](uprising-systems.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main pp. 9-10]` | controller bonus와 방문 플레이어의 orderable Agent-turn 효과 사이 처리 순서 | `open question` | [OQ-008](open-questions.md#oq-008--control-bonus와-방문자-효과의-상대-순서) |
| `[Main p. 10]` | Shield Wall이 세 critical location의 sandworm을 막고 detonation 뒤 영구 제거 | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 10]` | troop recruit, Combat space 방문 시 이번 turn recruit와 garrison 최대 2개 deploy | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 10]` | sandworm 즉시 deploy, Maker Hooks requirement, Shield Wall 제한 | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 10]` | Rise of Ix dreadnought 언급 | `out of scope` | 다른 확장의 unit은 현재 규칙셋에서 제외 |
| `[Main p. 11]` | 빈 observation post에 Spy 배치, supply가 비면 기존 Spy 무효 recall, 제한 icon 연결 | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 11]` | Recall Spy, Infiltrate, Gather Intelligence의 timing과 같은 Spy 중복 사용 금지 | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 11]` | Spy Agent icon은 현재 자기 Spy와 연결된 space를 허용하고 Spy를 회수하지 않음 | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 11]` | 여러 opponent Agent가 이미 있는 한 space에 새로 Infiltrate할 때 필요한 Spy 수 | `open question` | [OQ-006](open-questions.md#oq-006--한-space에-여러-opponent-agent가-있을-때-infiltrate) |
| `[Main p. 11]` `[FAQ p. 1]` | Gather Intelligence 즉시 window와 contract 완료의 상대 순서 | `open question` | [OQ-011](open-questions.md#oq-011--gather-intelligence와-contract-완료의-상대-순서) |
| `[Main pp. 4-5 board artwork]` | observation post와 board space의 실제 연결 graph | `covered` | 공식 setup 그림에서 전사한 [observation-posts.md](observation-posts.md) |
| `[Main p. 11]` | Agent turn 배치 예시 | `out of scope` | 설명 예시이며 별도 규칙이 아님 |
| `[Main p. 12]` | Reveal Cards, Resolve Reveal Effects, Clean Up 순서와 Agent card 구분 | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 12]` | Reveal 효과 자유 순서와 acquire의 전·사이·후 처리 | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 12]` | troop 2, sandworm 3, sword 1의 strength와 unit이 없으면 0 | `covered` | [player-turns.md](player-turns.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 12]` | Combat marker 공개, 20 초과 면, Agent/Reveal 카드 cleanup | `covered` | [player-turns.md](player-turns.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main pp. 12, 17]` | Clean Up의 discard-pile 이동이 일반적인 `discard` 반응을 발동하는지 | `open question` | [OQ-013](open-questions.md#oq-013--clean-up-이동과-일반적인-discard-반응) |
| `[Main p. 13]` | Persuasion 합산·분할, Row/Reserve acquire, 미사용 Persuasion 소멸 | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 13]` | acquire한 카드의 discard 이동과 Imperium Row 즉시 5장 보충 | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 13]` | Imperium deck 고갈로 Row를 5장 보충할 수 없는 경우 | `open question` | [OQ-004](open-questions.md#oq-004--imperium-deck-완전-고갈); [setup-and-game-flow.md](setup-and-game-flow.md)에도 미확정으로 표시 |
| `[Main p. 13]` | Reveal 효과 도중 원하는 시점에 strength 설정·갱신 | `covered` | [player-turns.md](player-turns.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 13]` | Reveal turn 진행 예시 | `out of scope` | 설명 예시이며 별도 규칙이 아님 |

### Main pp. 14-17: Combat, round end, CHOAM, clarification

| 출처 | 규칙 주제 | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- | --- |
| `[Main p. 14]` | First Player부터 unit 보유자만 Combat Intrigue 사용 또는 pass, 전원 연속 pass까지 반복 | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 14]` | Intrigue가 unit 또는 strength를 바꾸면 marker 갱신 | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 14]` | 4인 1·2·3위 보상, 0 strength 무보상, 승자의 Conflict card 획득 | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 14]` | 1·2·3위 동률별 보상과 승자 부재 | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 14]` | 3인 이하와 6인의 보상·동률 분기 | `out of scope` | 현재 4인 규칙셋에서 제외 |
| `[Main p. 14]` | 같은 순위 여러 플레이어의 보상 처리 순서 | `open question` | [OQ-002](open-questions.md#oq-002--동률-combat-reward-해결-순서); [combat-and-round-end.md](combat-and-round-end.md)에도 미확정으로 표시 |
| `[Main p. 14]` | Combat 중 unit 증감에 따른 priority 참가자 변화 시점 | `open question` | [OQ-003](open-questions.md#oq-003--combat-intrigue-도중-참가-자격-변화) |
| `[Main p. 14]` | battle icon 일치 pair를 뒤집고 VP 획득 | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 14]` | sandworm 보상 2배, control·battle icon 제외, 선택 비용의 두 번째 지불 | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 14]` | 보상 뒤 troop은 supply, marker는 0, sandworm은 bank로 정리 | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 15]` | 3인 Combat 진행 예시 | `out of scope` | 설명 예시이고 목표 인원수도 아님 |
| `[Main p. 15]` | 비어 있는 Deep Desert·Hagga Basin·Imperial Basin에 bonus spice 누적 | `covered` | [combat-and-round-end.md](combat-and-round-end.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 15]` | 6인 Maker space Habbanya Erg | `out of scope` | 현재 4인 규칙셋에서 제외 |
| `[Main p. 15]` | Recall에서 Endgame 조건 확인, 계속하면 Agent 회수와 First Player 교대 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 15]` | Endgame Intrigue 뒤 VP 비교와 spice·Solari·water·garrison troop tiebreaker | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 15]` | Endgame Intrigue의 플레이 순환·재기회와 wild battle icon의 상대적 처리 순서 | `open question` | [OQ-001](open-questions.md#oq-001--endgame-처리-순서와-priority); [combat-and-round-end.md](combat-and-round-end.md)에도 미확정으로 표시 |
| `[Main p. 16]` | CHOAM Module의 선택 적용과 module-off 규칙 | `covered` | [choam-module.md](choam-module.md) |
| `[Main p. 16]` | standard contract 20개, 추가 Imperium·Intrigue 카드, Shaddam setup | `covered` | [choam-module.md](choam-module.md) |
| `[Main p. 16]` | contract icon으로 face-up contract 획득·보충, 소진 시 2 Solari | `covered` | [choam-module.md](choam-module.md) |
| `[Main p. 16]` | space·Harvest·Immediate·Acquire The Spice Must Flow 완료 조건, 완료 보상과 face-down 보관, 소급 완료 금지 | `covered` | [choam-module.md](choam-module.md) |
| `[Main p. 16]` | Rise of Ix용 contract 10개와 동시 비밀 선택 setup | `out of scope` | 다른 확장 혼합 규칙은 제외 |
| `[Main p. 17]` | Feyd-Rautha의 Training track setup과 끝칸 유지 | `covered` | setup은 [setup-and-game-flow.md](setup-and-game-flow.md), 끝칸 판정은 [official-rulings-index.md](official-rulings-index.md); 능력 데이터만 content manifest |
| `[Main p. 17]` | Lady Jessica의 시작 면 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [official-rulings-index.md](official-rulings-index.md); 전환 능력 데이터만 content manifest |
| `[Main p. 17]` | Lady Margot Fenring·Princess Irulan의 `reach 2 Influence` 판정 | `covered` | [uprising-systems.md](uprising-systems.md); 개별 능력 연결은 content manifest로 이관 |
| `[Main p. 17]` | Shaddam Signet Ring의 unit 배치 제한은 즉시 발효 | `covered` | [choam-module.md](choam-module.md); 능력 데이터는 content manifest로 이관 |
| `[Main p. 17]` | Spacing Guild's Favor는 Clean Up 이동이 아니라 hand discard에만 반응 | `deferred to content manifest` | 판정은 [player-turns.md](player-turns.md)와 [official-rulings-index.md](official-rulings-index.md)에 보존; card 소속과 연결은 content manifest |
| `[Main p. 17]` | 자원, Faction, Combat, Spy, sandworm에 관한 전략 팁 | `out of scope` | 전략 조언이며 규칙 상태가 아님 |

### Main p. 20: Icon Guide and Additional Terms

| 출처 | 용어 또는 icon | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- | --- |
| `[Main p. 20]` | Acquire box | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 20]` | 세 번째 Agent 획득 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [board-spaces.md](board-spaces.md) |
| `[Main p. 20]` | Alliance token requirement icon | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | battle icon과 Endgame wild battle icon | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 20]` | contract icon의 module-off/on 분기 | `covered` | [choam-module.md](choam-module.md) |
| `[Main p. 20]` | Control reward와 control 중 Conflict 방어 배치 | `covered` | [uprising-systems.md](uprising-systems.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 20]` | hand에서 일반 card discard, Intrigue 기본 제외 | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | card draw와 빈 deck reshuffle | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | Intrigue draw와 비공개 보관 | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 20]` | Fremen Bond의 `다른 Fremen card in play` 조건과 상호 활성화 | `covered` | 일반 keyword는 [uprising-systems.md](uprising-systems.md); 어떤 card가 갖는지는 content manifest |
| `[Main p. 20]` | `in play` 기간 | `covered` | [uprising-systems.md](uprising-systems.md), [player-turns.md](player-turns.md) |
| `[Main p. 20]` | Influence requirement·지정 Faction 증감·임의 Faction 증감 icon | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | Maker 공간의 bonus spice와 Maker Hooks 획득·requirement | `covered` | [uprising-systems.md](uprising-systems.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 20]` | arrow 비용과 turn당 1회, sandworm reward doubling 예외 | `covered` | [uprising-systems.md](uprising-systems.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 20]` | Persuasion | `covered` | [player-turns.md](player-turns.md) |
| `[Main p. 20]` | 현재 보낸 Agent가 아닌 다른 Agent recall | `covered` | [uprising-systems.md](uprising-systems.md), [board-spaces.md](board-spaces.md) |
| `[Main p. 20]` | Spy recall | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | Solari·spice·water의 bank 이동 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | troop retreat는 Conflict에서 garrison으로 이동 | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | sandworm summon, Shield Wall 보호 시 무효 | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | Shield Wall 제거 | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | Signet Ring | `covered` | [uprising-systems.md](uprising-systems.md), [player-turns.md](player-turns.md) |
| `[Main p. 20]` | Spy 배치와 supply가 비었을 때 무효 recall | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | Intrigue 무작위 탈취 | `covered` | [uprising-systems.md](uprising-systems.md), [board-spaces.md](board-spaces.md) |
| `[Main p. 20]` | sword strength | `covered` | [player-turns.md](player-turns.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `[Main p. 20]` | hand의 Intrigue trash icon | `covered` | 일반 icon은 [uprising-systems.md](uprising-systems.md); 실제 효과 위치는 content manifest |
| `[Main p. 20]` | hand·discard·in-play card trash, Reserve 반환, 선택 여부 | `covered` | [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | troop recruit | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `[Main p. 20]` | Uprising set 식별 icon | `covered` | effect 없음은 [uprising-systems.md](uprising-systems.md); content filtering에 사용 |
| `[Main p. 20]` | Victory Point 증감 | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `[Main p. 20]` | battle icon 후보가 여러 장일 때 pair 선택 | `open question` | [OQ-005](open-questions.md#oq-005--여러-matching-battle-icon-중-pair-선택); [combat-and-round-end.md](combat-and-round-end.md)에도 미확정으로 표시 |

### Cross-page information visibility

| 출처 | 규칙 주제 | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- | --- |
| `[Main pp. 4-8, 12-14, 16, 20]` | deck·Intrigue·contract의 face-down 상태와 Row·Conflict·Objective·discard·in-play card의 face-up 상태 | `covered` | [information-visibility.md](information-visibility.md) |
| `[Main pp. 4-7, 12-14, 16, 20]` | 일반 hand·discard·deck 장수와 과거 공개 뒤 face-down card의 재열람 범위 | `open question` | [OQ-010](open-questions.md#oq-010--손패discard와-과거-공개-정보의-열람-범위) |

## Board Space Guide

Board Guide의 공통 Combat space 배치 규칙은 [player-turns.md](player-turns.md)와
[uprising-systems.md](uprising-systems.md)에, 아래 22개 공간의 icon, requirement,
cost, effect는 [board-spaces.md](board-spaces.md)에 반영되어 있다.

| 출처 | 항목 | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- | --- |
| `[Board Guide p. 1]` | Combat space 방문 때 이번 turn recruit 전부와 garrison 최대 2개 deploy | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `[Board Guide p. 1]` | Accept Contract | `covered` | [board-spaces.md](board-spaces.md), module 분기는 [choam-module.md](choam-module.md) |
| `[Board Guide p. 1]` | Arrakeen | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 1]` | Assembly Hall | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 1]` | Deep Desert | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 1]` | Deliver Supplies | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 1]` | Desert Tactics | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 1]` | Dutiful Service | `covered` | [board-spaces.md](board-spaces.md), module 분기는 [choam-module.md](choam-module.md) |
| `[Board Guide p. 1]` | Espionage | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 1]` | Fremkit | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 1]` | Gather Support | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 1]` | 6인 추가 공간 안내 | `out of scope` | 현재 4인 규칙셋에서 제외 |
| `[Board Guide p. 2]` | Hagga Basin | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Heighliner | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | High Council | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Imperial Basin | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Imperial Privilege | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Research Station | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Sardaukar의 4인 cost | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Secrets | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Shipping | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Sietch Tabr | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Spice Refinery | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Swordmaster의 4인 cost와 game당 1회 획득 | `covered` | [board-spaces.md](board-spaces.md) |
| `[Board Guide p. 2]` | Sardaukar·Swordmaster의 6인 차이 | `out of scope` | 현재 4인 규칙셋에서 제외 |
| `[Main pp. 4-5 board artwork]` | observation post와 space 연결 graph | `covered` | Board Guide 텍스트에는 없으며 공식 setup 그림에서 [observation-posts.md](observation-posts.md)로 전사 |

## FAQ, last updated 2025-01-13

FAQ의 `See ...` 항목은 새 규칙이 없더라도 연결 대상의 coverage를 표시한다.
개별 콘텐츠 판정은 일반 규칙 문서에 복제하지 않고 content manifest와
[official-rulings-index.md](official-rulings-index.md)로 보낸다.

### FAQ p. 1

| 항목 | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- |
| `Missionaria Protectiva` errata `[FAQ p. 1]` | `deferred to content manifest` | Faction 표식과 장수는 content manifest, 출처는 `official-rulings-index.md` |
| Rise of Ix rulebook p. 4 once-per-round Tech timing errata `[FAQ p. 1]` | `out of scope` | Rise of Ix 제외 |
| Rise of Ix rulebook p. 8 House Hagal setup errata `[FAQ p. 1]` | `out of scope` | Rise of Ix 및 1·2인 제외 |
| `Alliance` token 상실·동률 이전·board 반환 `[FAQ p. 1]` | `covered` | [uprising-systems.md](uprising-systems.md) |
| `Archduke Armand Ecaz — Coordination` `[FAQ p. 1]` | `deferred to content manifest` | Leader 데이터와 `official-rulings-index.md` |
| `Assassination Mission` `[FAQ p. 1]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `Baron Vladimir Harkonnen — Masterstroke` `[FAQ p. 1]` | `deferred to content manifest` | Leader 데이터와 `official-rulings-index.md` |
| `Beguiling Pheromones` graft/trash `[FAQ p. 1]` | `out of scope` | Immortality의 graft 규칙 제외 |
| `Carryall`의 Uprising base harvest 수치 `[FAQ p. 1]` | `deferred to content manifest` | card 판정과 `official-rulings-index.md`; 6인 Habbanya Erg는 제외 |
| `Chairdog`의 grafted card 반환 뒤 Reveal 지속 `[FAQ p. 1]` | `out of scope` | Immortality의 graft 규칙 제외 |
| `Chani` Imperium card의 Retreat 참조 `[FAQ p. 1]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md`; Retreat 일반 규칙은 [uprising-systems.md](uprising-systems.md) |
| `Chani` Leader의 Combat 정리 troop `lost` 판정 `[FAQ p. 1]` | `deferred to content manifest` | 현재 ruleset 소속 확인과 Leader 능력 연결은 content manifest 및 `official-rulings-index.md` |
| `Charisma`의 Intrigue timing 참조 `[FAQ p. 1]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md`; 일반 timing은 [player-turns.md](player-turns.md) |
| `Chaumurky` Endgame tiebreaker `[FAQ p. 1]` | `out of scope` | Tech tile을 쓰는 확장 조합 제외 |
| `Conflict`의 4인 보상 차이 `[FAQ p. 1]` | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `contract`의 의무 완료·동시 완료·Agent 효과 순서 `[FAQ p. 1]` | `covered` | [choam-module.md](choam-module.md), [player-turns.md](player-turns.md) |

### FAQ p. 2

| 항목 | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- |
| `Corner the Market`의 The Spice Must Flow 수량 비교 `[FAQ p. 2]` | `deferred to content manifest` | Intrigue 데이터와 `official-rulings-index.md` |
| `Count Ilban Richese — Ruthless Negotiator`의 printed space cost 한정 `[FAQ p. 2]` | `deferred to content manifest` | Leader 데이터와 `official-rulings-index.md` |
| `Countess Ariana Thorvald — Spice Addict`의 의무성과 harvest 범위 `[FAQ p. 2]` | `deferred to content manifest` | Leader 데이터와 `official-rulings-index.md` |
| `Demand Respect`의 Intrigue timing 참조 `[FAQ p. 2]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md`; 일반 timing은 [player-turns.md](player-turns.md) |
| `discard`는 별도 지정이 없으면 hand `[FAQ p. 2]` | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `Dispatch an Envoy`의 icon 추가 방식 `[FAQ p. 2]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `Double Cross`의 상대 troop 조건 `[FAQ p. 2]` | `deferred to content manifest` | Intrigue 데이터와 `official-rulings-index.md` |
| `dreadnoughts`의 strength·Combat Intrigue 참가 `[FAQ p. 2]` | `out of scope` | Rise of Ix unit 제외 |
| `Endgame` 최종 tiebreaker `[FAQ p. 2]` | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `Faction`의 Tleilaxu track 참조 `[FAQ p. 2]` | `out of scope` | Immortality track 제외 |
| `False Orders`의 Spy 이동 `[FAQ p. 2]` | `deferred to content manifest` | Intrigue 데이터와 `official-rulings-index.md` |
| `Foldspace` acquire 제한 `[FAQ p. 2]` | `out of scope` | Uprising setup에는 Foldspace stack이 없음 |
| `Gather Intelligence` 참조 `[FAQ p. 2]` | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `Ghola`와 grafted card 상호작용 `[FAQ p. 2]` | `out of scope` | Immortality의 graft 규칙 제외 |
| `Guild Bankers` discount `[FAQ p. 2]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `Guild Envoy`의 의무 discard `[FAQ p. 2]` | `covered` | [../implementation-audits/personal-cards.md](../implementation-audits/personal-cards.md)와 card scenario test |
| `Gun Thopter`의 opponent garrison 조건 `[FAQ p. 2]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `Helena Richese`의 Manipulate 참조 `[FAQ p. 2]` | `deferred to content manifest` | Leader 데이터와 `official-rulings-index.md` |
| `Ilesa Ecaz — One Step Ahead`의 `otherwise` `[FAQ p. 2]` | `deferred to content manifest` | Leader 데이터와 `official-rulings-index.md` |
| `Infiltrate` 참조 `[FAQ p. 2]` | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| Rise of Ix `infiltration` icon `[FAQ p. 2]` | `out of scope` | Rise of Ix 제외 |
| `Imperial Spy` self-trash cost `[FAQ p. 2]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `Intrigue cards`의 조건·비용, Plot timing, 지연 효과, discard 재구성 `[FAQ p. 2]` | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `Liet Kynes`의 in-play card 계산 `[FAQ p. 2]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `Litany Against Fear`의 red box 무시 `[FAQ p. 2]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `maker board space`의 Uprising 4인 목록 `[FAQ p. 2]` | `covered` | [uprising-systems.md](uprising-systems.md), [combat-and-round-end.md](combat-and-round-end.md) |
| `Maker Hooks`는 sandworm summon 때 소비하지 않음 `[FAQ p. 2]` | `covered` | [uprising-systems.md](uprising-systems.md) |

### FAQ p. 3

| 항목 | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- |
| `Manipulate`의 제거 card acquire와 기한 `[FAQ p. 3]` | `deferred to content manifest` | Leader·Intrigue 데이터와 `official-rulings-index.md` |
| `optional effects`의 의무 기본값과 세 예외 `[FAQ p. 3]` | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `paying a cost`의 arrow 1회 제한 `[FAQ p. 3]` | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `Plans Within Plans`의 3 Influence 칸 정의 `[FAQ p. 3]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `Poison Snooper`의 Reveal turn 참조 `[FAQ p. 3]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md`; 일반 draw timing은 [player-turns.md](player-turns.md) |
| `Princess Yuna Moritani — Smuggling Operation` `[FAQ p. 3]` | `deferred to content manifest` | Leader 데이터와 `official-rulings-index.md` |
| `Rapid Mobilization`의 Retreat 참조 `[FAQ p. 3]` | `deferred to content manifest` | Intrigue 데이터와 `official-rulings-index.md`; Retreat 일반 규칙은 [uprising-systems.md](uprising-systems.md) |
| `Recruitment Mission`의 Reveal 한정과 여러 acquire 선택 `[FAQ p. 3]` | `deferred to content manifest` | Intrigue 데이터와 `official-rulings-index.md` |
| `Refocus`의 빈 discard 때 deck reshuffle `[FAQ p. 3]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `Retreat any number`는 0개 선택 가능 `[FAQ p. 3]` | `covered` | [uprising-systems.md](uprising-systems.md) |
| Reveal turn 중 draw는 즉시 reveal, turn 뒤 draw는 다음 round의 5장에 추가 `[FAQ p. 3]` | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md), [player-turns.md](player-turns.md) |
| `Reverend Mother Jessica`의 flip turn 능력 사용 `[FAQ p. 3]` | `deferred to content manifest` | Leader 데이터와 `official-rulings-index.md` |
| `Reverend Mother Mohiam` discard 선택 순서 `[FAQ p. 3]` | `deferred to content manifest` | Leader 데이터와 `official-rulings-index.md` |
| `Rivals`의 조건부 space, Ix tie, Uprising Swordmaster cost `[FAQ p. 3]` | `out of scope` | 1·2인 Rivals와 다른 확장 제외 |
| `Score track`의 Victory Points 참조 `[FAQ p. 3]` | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `Shaddam — Sardaukar Commander` contract 선택 `[FAQ p. 3]` | `deferred to content manifest` | Leader·contract 데이터와 `official-rulings-index.md` |
| `Shaddam — Emperor of the Known Universe`는 그 turn에만 적용 `[FAQ p. 3]` | `covered` | [choam-module.md](choam-module.md); 6인 Ally 부분은 제외 |

### FAQ p. 4

| 항목 | 상태 | 반영 위치 또는 처리 |
| --- | --- | --- |
| `Shield Wall` 제거는 선택이고 게임 동안 영구적 `[FAQ p. 4]` | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `Shifting Allegiances`의 같은 Faction 선택과 실제 cost 지불 `[FAQ p. 4]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md` |
| `Solo Play`의 Rival Influence VP·Alliance·4 Influence bonus `[FAQ p. 4]` | `out of scope` | Solo Rival 제외 |
| `Expert Troop Deployment` Rival 판단 `[FAQ p. 4]` | `out of scope` | Solo Rival 및 dreadnought 제외 |
| `Sort Through the Chaos`의 다음 round Mentat `[FAQ p. 4]` | `out of scope` | Uprising에는 Mentat Agent가 없음 |
| `Spaceport`의 Reveal turn 참조 `[FAQ p. 4]` | `out of scope` | Tech tile을 쓰는 확장 조합 제외 |
| `Spies`는 card play 필요, 두 Spy는 서로 다른 두 효과에만 사용 `[FAQ p. 4]` | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| `The Spice Must Flow`를 trash해도 acquire VP 유지 `[FAQ p. 4]` | `covered` | 일반 판정은 [player-turns.md](player-turns.md); card 데이터와 test는 content manifest |
| `Staged Incident`로 strength를 낮출 때 marker 갱신 `[FAQ p. 4]` | `deferred to content manifest` | 일반 marker 갱신은 [combat-and-round-end.md](combat-and-round-end.md); card 소속과 효과 연결은 content manifest |
| timing 미지정 `Tech tiles`는 자기 turn에 사용 `[FAQ p. 4]` | `out of scope` | Tech tile을 쓰는 확장 조합 제외 |
| `Test of Humanity`의 discard 참조 `[FAQ p. 4]` | `deferred to content manifest` | 일반 discard는 [player-turns.md](player-turns.md); card 소속과 효과 연결은 content manifest |
| `tiebreaker`의 Endgame 참조 `[FAQ p. 4]` | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
| `Tleilaxu track`은 Faction이 아님 `[FAQ p. 4]` | `out of scope` | Immortality track 제외 |
| `To the Victor…`의 Intrigue timing 참조 `[FAQ p. 4]` | `deferred to content manifest` | card 데이터와 `official-rulings-index.md`; 일반 timing은 [player-turns.md](player-turns.md) |
| `troops`는 supply에서 recruit, garrison 재모집 금지, 그 turn의 모든 recruit 출처 deploy 가능 `[FAQ p. 4]` | `covered` | [player-turns.md](player-turns.md), [uprising-systems.md](uprising-systems.md) |
| Score track을 넘어 12 VP 초과 가능 `[FAQ p. 4]` | `covered` | [setup-and-game-flow.md](setup-and-game-flow.md) |
| `When you win a Conflict`는 공동 1위 제외, 보상으로 얻은 해당 Intrigue 즉시 사용 가능 `[FAQ p. 4]` | `covered` | [combat-and-round-end.md](combat-and-round-end.md) |
