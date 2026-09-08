# Immortality 확장

Immortality는 원본 Dune: Imperium의 두 번째 확장이며, Uprising Main Rulebook은 "Adding Immortality"로 Uprising과의 조합을 공식 지원한다 — 유일한 변경 지시는 Uprising의 Research Station도 Research Station overlay로 덮으라는 것이다 `[Main p. 18]`. 이 문서는 4인 Uprising 게임에 Immortality를 더했을 때 바뀌거나 추가되는 규칙을 구현 단위로 정리한다. 규범 근거는 [공식 Immortality 룰북](sources.md)이며, `[Immortality p. N]`은 그 PDF의 페이지 번호다(인쇄된 쪽수와 같다). 프로젝트는 확장을 `RulesetConfig(immortality=True)` 옵션으로 취급하며 기본값은 꺼짐이다. Bloodlines 옵션과는 독립이라 함께 켤 수 있다.

범위 밖: 1인 Rivals와 House Hagal 카드 `[Immortality p. 13]`, Rise of Ix Epic Game Mode·Go to 11 변형 `[Immortality p. 12]`, 원본 Dune: Imperium 전용 카드(Mentat, Foldspace 등)를 전제한 clarification. Uprising Rules Supplements의 Immortality 항목은 Rivals(p. 3)와 6인 팀전(p. 11)에 관한 것이라 범위 밖이다.

## 1. 구성물

- Bene Tleilax board 1장, Imperium 카드 30장, Intrigue 카드 15장, Tleilaxu deck 카드 18장(뒷면은 Imperium 카드와 같다), Reserve 카드 Reclaimed Forces 1장, Research Station overlay 1장, House Hagal 카드 4장(솔로 전용). 플레이어별: disc 2개(Research token·Tleilaxu token), Family Atomics token 1개, 시작 카드 Experimentation 2장. `[Immortality p. 3]`
- 카드 수량: Dune Cards Hub 카탈로그는 Imperium 25종 27장(Dissecting Kit·Tleilaxu Master 2장씩), Intrigue 11종 11장, Tleilaxu 18종 18장을 싣는다. 룰북의 30·15장과 다른 Imperium 3장·Intrigue 4장의 identity는 확인하지 못했다([implementation-audits/immortality.md](../implementation-audits/immortality.md)). 카탈로그 수량을 채택하고 확인되면 갱신한다.
- 룰북 밖의 프로모 Tleilaxu 카드 1장(Piter, Genius Advisor)은 `promo_cards` 옵션을 함께 켤 때만 Tleilaxu deck에 섞는다. 근거는 카드면뿐이다. `[card face]`

## 2. Setup 변경

Uprising setup에 다음 단계를 더하거나 바꾼다. `[Immortality pp. 4-5]`

1. Imperium 카드 30장을 Imperium Deck에 섞는다(Imperium Row를 만들기 전에). `[Immortality p. 4]`
2. Bene Tleilax board를 Imperium Row와 Reserve 카드 위에 놓는다. bank의 spice 2를 Tleilaxu track의 네 번째 칸에 놓는다. 각 플레이어는 자기 색 disc 2개를 받아 하나를 Tleilaxu token으로 Tleilaxu track의 맨 왼쪽 칸에, 하나를 research token으로 research track의 맨 왼쪽 칸에 놓는다. `[Immortality p. 4]`
3. Imperium Row 위에 Tleilaxu Row를 만든다. Reclaimed Forces를 Bene Tleilax board 왼쪽에 놓고, Tleilaxu Deck을 섞어 Imperium Deck 위에 face-down으로 둔 뒤 2장을 face-up으로 Reclaimed Forces 옆에 deal한다. `[Immortality p. 4]`
4. Research Station overlay를 Research Station 위에 덮는다(Uprising의 Research Station도). `[Immortality p. 5]` `[Main p. 18]`
5. 각 플레이어는 Family Atomics token을 supply에 둔다. `[Immortality p. 5]`
6. 각 플레이어는 starting deck의 Dune, the Desert Planet 2장을 box로 돌려보내고 Experimentation 2장으로 바꾼다. Intrigue 15장을 Intrigue Deck에 섞는다. `[Immortality p. 5]`

## 3. Bene Tleilax board

### Research track

- Research 아이콘을 얻을 때마다 research token을 오른쪽으로 한 칸 전진한다. 대개 오른쪽 위·오른쪽 아래 두 방향 중 하나를 고르며(한 방향뿐인 칸도 있다), 위·아래·왼쪽으로는 움직일 수 없다. 전진한 칸의 보너스는 즉시 얻는다. `[Immortality pp. 6, 16]`
- research 칸의 Research 아이콘은 곧바로 또 한 번 전진하게 한다(예시: "triggering another research icon and immediately advancing her token again"). `[Immortality p. 6]`
- **Genetic marker**: token이 아래에 genetic marker가 있는 열에 도달하면 남은 게임 동안 그 아이콘이 붙은 카드 효과가 활성화된다. 첫 marker 하나로 작동하는 효과와 track 끝의 두 번째 marker까지 필요한 효과가 있다. `[Immortality pp. 6, 16]`
- 첫 genetic marker에 도달하면 남은 게임 동안 acquire한 Tleilaxu 카드를 deck 맨 위에 둘 수 있다. 두 번째 genetic marker에 도달하면 남은 게임 동안 Research 아이콘은 token을 전진시키지 않고 대신 card 1장을 draw한다. `[Immortality pp. 6, 16]`
- 칸의 배치와 보너스는 룰북에 실린 공식 board 그림에서 전사했다(`[Immortality p. 3 board artwork]`; `content/immortality/board.py`). 열 0이 시작 칸, 열 4 아래에 첫 genetic marker, 열 8(마지막 열) 아래에 두 번째 marker가 있다. 표의 좌표 `c열r행`은 프로젝트의 전사 좌표다.

| 칸 | 보너스 | 다음 칸 |
| --- | --- | --- |
| c0r3 (시작) | — | c1r3 |
| c1r3 | specimen 1 | c2r2, c2r4 |
| c2r2 | specimen 1 | c3r1, c3r3 |
| c2r4 | Tleilaxu 1 | c3r3, c3r5 |
| c3r1 | Research | c4r2 |
| c3r3 | trash 아이콘(선택) + specimen 1 | c4r2, c4r4 |
| c3r5 | Tleilaxu 1 + specimen 1 | c4r4, c4r6 |
| c4r2 (marker 1) | Tleilaxu 1 | c5r1, c5r3 |
| c4r4 (marker 1) | specimen 1 | c5r3, c5r5 |
| c4r6 (marker 1) | Research | c5r5 |
| c5r1 | Research | c6r2 |
| c5r3 | specimen 1 | c6r2, c6r4 |
| c5r5 | Solari 1 | c6r4, c6r6 |
| c6r2 | spice 1 | c7r1, c7r3 |
| c6r4 | Tleilaxu 1 | c7r3, c7r5 |
| c6r6 | Influence 1 선택 | c7r5 |
| c7r1 | Tleilaxu 1 | c8r2 |
| c7r3 | trash 아이콘 → draw 1 + Intrigue 1 (선택형 arrow) | c8r2, c8r4 |
| c7r5 | trash 아이콘(선택) + specimen 1 | c8r4, c8r6 |
| c8r2 (marker 2, 끝) | spice 2 | — |
| c8r4 (marker 2, 끝) | Tleilaxu 1 | — |
| c8r6 (marker 2, 끝) | Solari 7 → Tleilaxu 2 (선택형 arrow) | — |

- 검은 trash 아이콘은 hand·discard pile·in play의 카드 1장을 trash하는 선택 효과이고 `[Main p. 20]`, arrow 앞의 비용은 지불 여부를 고르는 선택이다 `[Main p. 9]`. c7r3·c8r6의 arrow 효과는 그렇게 읽는다. c6r6의 금색 "?"는 Uprising 아이콘 가이드의 "Influence 1 선택"이며, Bene Tleilax는 Faction이 아니므로 Tleilaxu track 전진으로 쓸 수 없다 `[FAQ p. 4]`.

### Tleilaxu track

- Tleilaxu 아이콘을 얻을 때마다 Tleilaxu token을 한 칸 전진한다. 보너스가 있는 칸에 도달하면 즉시 얻는다. `[Immortality pp. 7, 16]`
- 칸 0이 시작 칸이다. 칸 2: Intrigue 1, 칸 4: VP 1(각 플레이어가 도달할 때마다; **처음** 도달한 플레이어는 setup 때 놓인 spice 2도 가져간다), 칸 6: Intrigue 1, 칸 7(마지막): VP 1. `[Immortality pp. 4, 7]` `[Immortality p. 3 board artwork]`
- Bene Tleilax는 Faction이 아니다. "아무 Faction의 Influence"를 주는 효과로 Tleilaxu track을 전진할 수 없다. `[FAQ p. 4]`

### Specimen과 Axolotl tanks

- 카드나 board space의 specimen 아이콘이 나타날 때마다 specimen 하나를 생성한다: supply의 troop 하나를 Bene Tleilax board의 Axolotl tanks에 놓는다. `[Immortality pp. 8, 16]`
- Axolotl tanks의 specimen은 Tleilaxu Row의 Tleilaxu 카드를 acquire하거나(오른쪽 위의 specimen 비용) 자신의 카드의 specimen 비용 효과를 치르는 데 쓴다. specimen을 쓰면 supply로 돌려보낸다. `[Immortality pp. 8, 16]`
- 자신의 specimen은 언제든 supply로 돌려보낼 수 있다(recruit할 troop이 supply에 없을 때 유용하다). `[Immortality p. 8]`

## 4. Tleilaxu 카드와 Tleilaxu Row

- Tleilaxu 카드는 Imperium 카드와 비슷하다: Reveal turn에 acquire해 discard pile에 놓고, Agent turn에 play하거나 Reveal turn에 reveal한다. 다만 Tleilaxu Row에서 오고 Persuasion 대신 specimen을 비용으로 낸다. `[Immortality p. 8]`
- Tleilaxu Row는 항상 카드 2장과 Reclaimed Forces를 갖춰야 하며, 모자라면 Tleilaxu deck 맨 위에서 보충한다. Reclaimed Forces는 Row에서 제거되지 않는다: "acquire"하면 효과 하나를 고르고(troop 2 recruit 또는 Tleilaxu 1) 카드는 그 자리에 남긴다. 그 비용은 카드에 인쇄된 specimen 3이다. `[Immortality p. 9]` `[Reclaimed Forces card]`
- Imperium Row에서 카드를 acquire하는 효과로는 Tleilaxu 카드를 acquire할 수 없고, Persuasion 비용을 참조·수정하는 효과도 쓸 수 없다. `[Immortality p. 9]`
- Tleilaxu deck 18장은 [implementation-audits/immortality.md](../implementation-audits/immortality.md)에 카드면 전사로 기록한다. `[Tleilaxu card faces]`

## 5. Graft

Graft라고 적힌 특별한 배경의 Agent box를 가진 카드는 hand의 다른 카드와 결합해 play한다. `[Immortality p. 10]`

- Agent turn에 Graft 카드는 혼자 play할 수 없다. 그 turn에는 카드 두 장을(두 장만) play해야 한다. Graft 카드 둘, 또는 Graft 카드 하나와 일반 카드 하나를 함께 play할 수 있다. `[Immortality p. 10]`
- 어느 카드의 Agent 아이콘으로든 Agent를 보낼 수 있다. 어느 아이콘을 썼든 두 카드 모두 Agent를 "보낸" 것으로 취급한다. 두 카드의 효과를 board space 효과와 함께 원하는 순서로 얻는다. `[Immortality p. 10]`
- Graft 카드는 Reveal turn에 평소처럼 reveal해 Reveal box 효과를 쓸 수 있다. `[Immortality p. 10]`
- 함께 play한 두 장은 서로 "grafted"됐다고 하며, 일부 카드는 "if grafted"로 추가 효과를 낸다(예: Ghola는 grafted 상대 카드의 Agent box를 복사하므로 Corrino Genes와 함께 play하면 Tleilaxu를 두 번 전진한다). "the other grafted card"는 함께 graft된 상대 카드다. `[Immortality p. 11]`
- Clarification `[Immortality p. 14]`: Clandestine Meeting은 Agent turn에 play하려면 어떤 식으로든 Agent 아이콘을 얻어야 한다(예: graft). Ghola는 상대 카드의 Agent box 전체("Trash this card" 포함)를 복사하고, Bene Gesserit 카드에 graft하면 그 카드의 "BG 카드가 play 중이면" 조건은 그 카드 자신을 세지만 Ghola 자체는 BG 카드가 아니다. Usurp는 Imperium Row 카드 대신 hand의 카드에 graft할 수도 있고, Row에 있는 grafted 카드는 "in play"가 아니며, Usurp로 trash하는 것은 Replacement Eyes 같은 trash trigger를 발동한다.
- FAQ `[FAQ pp. 1-2]`: Beguiling Pheromones로 grafted 상대 카드를 trash할 때 그 카드의 "trash를 비용으로 하는" 효과는 함께 얻을 수 없다(Imperial Spy의 Intrigue draw 등); 어차피 trash될 카드(Seek Allies)를 trash 대상으로 고를 수는 있다. Chairdog로 상대 카드를 hand에 되돌린 뒤에는 Reveal turn을 그대로 마쳐야 하며 Agent turn으로 바꿀 수 없다.

## 6. 새 아이콘과 Research Station

- **Combat**: Combat space에 Agent를 보낸 것처럼 이번 turn troop을 Conflict에 deploy할 수 있다. Bloodlines의 같은 아이콘과 동일하다 `[Bloodlines p. 12]`. `[Immortality p. 16]`
- **Genetic marker**: research token이 해당 열에 도달하기 전에는 그 아이콘의 효과가 비활성이다. `[Immortality p. 16]`
- **Immortality 아이콘**: 카드 오른쪽 아래의 참고 표시. `[Immortality p. 16]`
- **Research**, **Specimen**, **Tleilaxu**: 3절. **Trash an Intrigue card**: hand의 Intrigue 카드 1장을 trash한다. `[Immortality p. 16]`
- **Research Station(개정)**: City 아이콘, Combat space, 비용 water 2: card 2장 draw와 Research. Uprising의 "troop 2 recruit, card 2 draw"를 대체한다. `[Immortality pp. 5, 16]` `[Main p. 18]` `[Board Guide p. 2]`

## 7. Family Atomics

- 각 플레이어는 setup 때 Family Atomics token을 받는다. 게임에 한 번, 자신의 turn에 token을 box로 돌려보내고 Imperium Row의 카드를 전부 제거한 뒤 Imperium Deck 맨 위에서 새 Imperium Row를 deal할 수 있다. `[Immortality p. 12]`

## 8. 기존 명세와의 관계

- specimen은 supply의 troop이므로 [player-turns.md](player-turns.md)의 recruit 규칙과 OQ-030(해결 시점의 supply만큼만 recruit, 소급 없음)이 그대로 적용된다. 플레이어는 specimen을 먼저 돌려보내 supply를 채운다 `[Immortality p. 8]`.
- Graft는 [player-turns.md](player-turns.md)의 "카드 1장과 일치하는 Agent 아이콘 하나로 Agent 1개 배치" `[Main p. 9]`를 카드 두 장으로 넓히는 예외이며, 두 카드의 Agent box는 space 효과와 같은 자유 순서 그룹에 들어간다(OQ-027).
- Bloodlines와 함께 쓸 때 "lose a troop"·retreat 효과의 Commander 취급은 [bloodlines.md](bloodlines.md) 3절을 따른다.
- 공식 문서가 침묵하는 판정은 [open-questions.md](open-questions.md)에 기록한다.

## 9. 구현 상태

- 2026-09-08 슬라이스 5a: Intrigue 11장 전부(effect DSL). 새 노드: 조건 `GeneticMarkersAtLeast`·`SolariAtLeast`·`SpiceAtLeast`·`OpponentPlayedCombatIntrigue`·`AllConditions`, 보상 `Research`·`AdvanceTleilaxu`·`GenerateSpecimens`·`AcquireTleilaxuCard`(선택형 slot, `acquire_intrigue_tleilaxu`/`decline_intrigue_tleilaxu`)·`RevealPersuasionThisRound`(round 한정 좌석 필드), trigger `OnTroopsLostAtConflictEnd`(Harvest Cells: Combat 중 play해 face-up으로 기다리다 Combat 정리에서 supply로 돌아간 troop·Commander 수가 3 이상이면 발동, 아니면 만료). Counterattack의 "상대가 Combat Intrigue를 play했으면"은 `GameState.combat_intrigue_players`(Conflict마다 초기화). 관측 v13.
- 2026-09-08 슬라이스 4: 5절의 Graft — `agent_turn`의 `graft` 인자로 첫 카드와 space를 정한 뒤 `graft_partner` frame의 `choose_graft_partner(card_id)`로 둘째 카드를 hand에서 고른다(Graft 카드는 혼자 play 불가, 일반 카드 둘은 graft 불가, 두 카드 모두 in play). 효과 frame은 활성 카드(`card_id`)와 상대(`graft_card_id`)의 Agent box를 따로 대기시키고 `switch_graft_card`로 바꿔 소유자 순서로 해결한다("if grafted"는 `graft_card_id` 유무, "the other grafted card"는 비활성 카드). trash된 상대의 미발동 box는 OQ-022로 만료된다. Tleilaxu Infiltrator는 상대 Agent가 있는 space를 열고(둘 중 하나가 Infiltrator일 때), Blank Slate는 graft 시 진영 아이콘 4개를 얻는다. 카드: Face Dancer, Face Dancer Initiate, Corrino Genes, Unnatural Reflexes, Tleilaxu Infiltrator, Twisted Mentat, Bene Tleilax Researcher, Planned Coupling. Reveal box의 genetic marker 조건(`minimum_genetic_markers`) 포함. `rules/graft.py`.
- 2026-09-08 슬라이스 3: 4절의 Tleilaxu Row — Reveal turn의 `acquire_tleilaxu(instance_id[, to_deck_top])`(specimen 지불, discard pile 또는 첫 genetic marker 뒤 deck 맨 위, Row 보충, 획득 box 해결)와 `acquire_reclaimed_forces(choice=troops|tleilaxu)`(specimen 3, 카드는 Row에 남음; troop 2는 Reveal의 Combat 아이콘 배치 한도에 합산). 획득 box에 `RESEARCH`·`ADVANCE_TLEILAXU`(Spiritual Fervor·Subject X-137)를 더해 Imperium 획득 경로 4곳(Reveal·Solari·Manipulate·Intrigue)에서도 해결한다. 첫 Tleilaxu 카드 3장(Contaminator, From the Tanks, Subject X-137)이 play되며 그때부터 setup이 `setup:tleilaxu_deck`을 셔플한다. `rules/tleilaxu_row.py`.
- 2026-09-08 슬라이스 2: 3절의 Bene Tleilax board 전부와 6·7절 — setup(token 2개, spice 2, Tleilaxu deck 셔플과 Row 2장, Experimentation 시작 덱, Family Atomics), research 전진(`advance_research`: 한 방향이면 즉시, 두 방향이면 `research_advance` frame의 `choose_research_space`; 보너스 즉시 해결, research 연쇄, genetic marker 이벤트, 두 번째 marker 뒤 draw 대체), research 보너스 frame(`choose_research_influence`, `trash_for_research_bonus`/`decline`, `pay_research_bonus`/`decline`; 살 수 없으면 `research_bonus_unavailable`), Tleilaxu track(`advance_tleilaxu`: Intrigue·VP·첫 도달 spice 2, 끝에서는 OQ-048), specimen 생성(`generate_specimens`, 부족분 OQ-049)·자유 반환(`return_specimen`, 창은 OQ-050)·지출(`spend_specimens`), 개정 Research Station(`research` 보드 아이콘), Experimentation(Agent: Research, Reveal: 소유자 시점의 `generate_reveal_specimens`), Family Atomics(`use_family_atomics`, 제거 카드는 OQ-051). 관측 v12, codec v96(`immortality` 카탈로그에 템플릿 추가; 기본 카탈로그는 `resolve_board_effect(research)` 1개만 늘어 4,367). 세부는 [implementation-audits/immortality.md](../implementation-audits/immortality.md).
- 2026-09-08 슬라이스 1: `RulesetConfig(immortality=True)` 옵션과 이 명세, 출처 등록, research track·Tleilaxu track 전사(`content/immortality/board.py`), Tleilaxu deck 18장 + Reclaimed Forces + 프로모 Piter의 카탈로그(`content/immortality/tleilaxu.py`), Imperium 25종·Intrigue 11종의 카탈로그 항목(`immortality_only`). 전사가 끝난 카드만 옵션 덱에 들어가며 아직 한 장도 없다. 서버·UI 체크박스, sweep/tournament `--immortality`, coverage census, 저장 문서 플래그, 체크포인트 룰셋 식별자(`+immortality`)까지 연결했다.
