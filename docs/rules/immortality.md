# Immortality 확장

Immortality는 원본 Dune: Imperium의 두 번째 확장이며, Uprising Main Rulebook은 "Adding Immortality"로 Uprising과의 조합을 공식 지원한다 — 유일한 변경 지시는 Uprising의 Research Station도 Research Station overlay로 덮으라는 것이다 `[Main p. 18]`. 이 문서는 4인 Uprising 게임에 Immortality를 더했을 때 바뀌거나 추가되는 규칙을 구현 단위로 정리한다. 규범 근거는 [공식 Immortality 룰북](sources.md)이며, `[Immortality p. N]`은 그 PDF의 페이지 번호다(인쇄된 쪽수와 같다). 프로젝트는 확장을 `RulesetConfig(immortality=True)` 옵션으로 취급하며 기본값은 꺼짐이다. Bloodlines 옵션과는 독립이라 함께 켤 수 있다. p. 12의 Go to 11 변형은 `RulesetConfig(go_to_11=True)` 옵션이며 Immortality가 켜져 있어야 고를 수 있다(8절).

범위 밖: 1인 Rivals와 House Hagal 카드 `[Immortality p. 13]`, 원본 Dune: Imperium 전용 카드(Mentat, Foldspace 등)를 전제한 clarification. Uprising Rules Supplements의 Immortality 항목은 Rivals(p. 3)와 6인 팀전(p. 11)에 관한 것이라 범위 밖이다.

## 1. 구성물

- Bene Tleilax board 1장, Imperium 카드 30장, Intrigue 카드 15장, Tleilaxu deck 카드 18장(뒷면은 Imperium 카드와 같다), Reserve 카드 Reclaimed Forces 1장, Research Station overlay 1장, House Hagal 카드 4장(솔로 전용). 플레이어별: disc 2개(Research token·Tleilaxu token), Family Atomics token 1개, 시작 카드 Experimentation 2장. `[Immortality p. 3]`
- 카드 수량: Imperium 25종 30장(Dissecting Kit·Tleilaxu Master·High Priority Travel·Planned Coupling·Spiritual Fervor 2장씩), Intrigue 11종 15장(Gruesome Sacrifice·Harvest Cells·Illicit Dealings·Vicious Talents 2장씩), Tleilaxu 18종 18장 — 룰북의 30·15장과 일치한다. 사본 수는 사용자가 알려준 BGG 카드 인벤토리 시트(에셋 저장소 `reference/bgg-card-inventory/`)로 확정했다; Dune Cards Hub는 Imperium 27장·Intrigue 11장으로 적게 세었다([implementation-audits/immortality.md](../implementation-audits/immortality.md)). 카탈로그 수량을 채택하고 확인되면 갱신한다.
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
- 칸의 배치와 보너스는 룰북에 실린 공식 board 그림에서 전사했고(`[Immortality p. 3 board artwork]`; `content/immortality/board.py`), 2026-09-08 사용자의 고해상도 board 스캔(`assets/board/bene_tleilax.jpg`)과 22칸 전부 대조해 일치를 확인했다. 열 0이 시작 칸, 열 4 아래에 첫 genetic marker, 열 8(마지막 열) 아래에 두 번째 marker가 있다. 표의 좌표 `c열r행`은 프로젝트의 전사 좌표다.

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
| c7r3 | **Trash an Intrigue card** 아이콘 → draw 1 + Intrigue 1 (선택형 arrow; 2026-09-19 재전사 — 금색 Intrigue 카드 위의 X이고 일반 trash 아이콘이 아니다) | c8r2, c8r4 |
| c7r5 | trash 아이콘(선택) + specimen 1 | c8r4, c8r6 |
| c8r2 (marker 2, 끝) | spice 2 | — |
| c8r4 (marker 2, 끝) | Tleilaxu 1 | — |
| c8r6 (marker 2, 끝) | Solari 7 → Tleilaxu 2 (선택형 arrow) | — |

- 검은 trash 아이콘은 hand·discard pile·in play의 카드 1장을 trash하는 선택 효과이고 `[Main p. 20]`, arrow 앞의 비용은 지불 여부를 고르는 선택이다 `[Main p. 9]`. c7r3·c8r6의 arrow 효과는 그렇게 읽는다. 단 c7r3의 비용 아이콘은 검은 trash가 아니라 **Trash an Intrigue card**(`[Immortality p. 16]`의 아이콘 정의: hand의 Intrigue 카드 1장을 trash)다 — 2026-09-19에 보드 스캔에 룰북 아이콘을 템플릿 매칭해 확인했고(일치도 0.94, 보드에서 이 아이콘은 이 한 곳뿐), 처음 전사는 일반 trash로 잘못 읽었다([lessons.md](../lessons.md)). trash한 카드는 공용 Intrigue 버림 더미로 간다(OQ-061, 2026-10-04). c7r3에서 hand에 Intrigue 카드가 없거나 c8r6에서 Solari가 7 미만이면 arrow 비용을 낼 수 없으므로 보너스를 얻지 못한다 — "비용을 지불하지 않으면 효과를 얻지 못하며" ([player-turns.md](player-turns.md) `[Main p. 9]` `[FAQ p. 3]`). 그래도 보너스 창(`research_bonus` frame)은 열리고 소유자는 `decline_research_bonus`("받지 않음") 하나만 받아 직접 확인하며, 화면은 지불 줄을 이유와 함께 "지금 고를 수 없는 선택지"에 회색으로 보인다("{trash}할 {intrigue} 없음", "{solari:7} 필요 (보유 N)"; 엔진의 `immortality.research_bonus_block`이 제시와 회색 줄을 함께 정한다). 지불할 수 있는지는 창이 맨 위에 와서 결정할 때 판정한다. 2026-09-30 사용자 판정, 2026-10-02 구현 ([unavailable-options-plan.md](../unavailable-options-plan.md) 5절): "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다"("플레이어가 직접 체크하는게 플레이하는데에는 도움이 될 것 같아"). 이전 판정(폐기, 공식 문서가 아닌 프로젝트 기본값): 비용을 낼 수 없으면 창 없이 공개 이벤트 `research_bonus_unavailable`("연구 보너스 불가")만 남기고 소멸했다. c6r6의 금색 "?"는 Uprising 아이콘 가이드의 "Influence 1 선택"이며, Bene Tleilax는 Faction이 아니므로 Tleilaxu track 전진으로 쓸 수 없다 `[FAQ p. 4]`.

### Tleilaxu track

- Tleilaxu 아이콘을 얻을 때마다 Tleilaxu token을 한 칸 전진한다. 보너스가 있는 칸에 도달하면 즉시 얻는다. `[Immortality pp. 7, 16]`
- 칸 0이 시작 칸이다. 칸 2: Intrigue 1, 칸 4: VP 1(각 플레이어가 도달할 때마다; **처음** 도달한 플레이어는 setup 때 놓인 spice 2도 가져간다), 칸 6: Intrigue 1, 칸 7(마지막): VP 1. `[Immortality pp. 4, 7]` `[Immortality p. 3 board artwork]`
- Bene Tleilax는 Faction이 아니다. "아무 Faction의 Influence"를 주는 효과로 Tleilaxu track을 전진할 수 없다. `[FAQ p. 4]`
- 마지막 칸(7)에서는 Tleilaxu 아이콘이 아무것도 하지 않으므로(OQ-048) 비용을 내고 Tleilaxu 전진만 얻는 줄 — Slig Farmer의 Solari 5, Tleilaxu Surgeon의 specimen 2, 연구 칸 c8r6의 Solari 7, Reclaimed Forces의 Tleilaxu 선택 — 은 제시하지 않는다(2026-10-06, 사용자 결정 "비용만 내고 보상을 받지 못하는 경우는 없어야 한다"의 확장, OQ-071). 같은 날 사용자 판정("아무 효과 없이 책략을 쓸 수 없는거지", OQ-071의 카드 확장 2)으로 비용이 없는 Intrigue의 전진도 같다: Illicit Dealings와 Shadowy Bargain의 Endgame option은 마지막 칸에서 낼 수 없고, Gruesome Sacrifice는 specimen을 만들 troop이 있을 때만 낸다(OQ-048의 2026-10-06 귀결).

### Specimen과 Axolotl tanks

- 카드나 board space의 specimen 아이콘이 나타날 때마다 specimen 하나를 생성한다: supply의 troop 하나를 Bene Tleilax board의 Axolotl tanks에 놓는다. `[Immortality pp. 8, 16]`
- Axolotl tanks의 specimen은 Tleilaxu Row의 Tleilaxu 카드를 acquire하거나(오른쪽 위의 specimen 비용) 자신의 카드의 specimen 비용 효과를 치르는 데 쓴다. specimen을 쓰면 supply로 돌려보낸다. `[Immortality pp. 8, 16]`
- 자신의 specimen은 언제든 supply로 돌려보낼 수 있다(recruit할 troop이 supply에 없을 때 유용하다). `[Immortality p. 8]`

## 4. Tleilaxu 카드와 Tleilaxu Row

- Tleilaxu 카드는 Imperium 카드와 비슷하다: Reveal turn에 acquire해 discard pile에 놓고, Agent turn에 play하거나 Reveal turn에 reveal한다. 다만 Tleilaxu Row에서 오고 Persuasion 대신 specimen을 비용으로 낸다. `[Immortality p. 8]`
- Tleilaxu Row는 항상 카드 2장과 Reclaimed Forces를 갖춰야 하며, 모자라면 Tleilaxu deck 맨 위에서 보충한다. Reclaimed Forces는 Row에서 제거되지 않는다: "acquire"하면 효과 하나를 고르고(troop 2 recruit 또는 Tleilaxu 1) 카드는 그 자리에 남긴다. 그 비용은 카드에 인쇄된 specimen 3이다. `[Immortality p. 9]` `[Reclaimed Forces card]`
- Reclaimed Forces의 "acquire" 역시 다른 Tleilaxu 카드와 마찬가지로 카드를 "acquire"하는 것이며(카드가 Row에 남는 점만 다르다), "whenever you acquire a card" 트리거(예: Call to Arms)의 대상이 된다(사용자 판정, 2026-09-26, OQ-066). `[Immortality p. 9]`
- Harvest Cells의 "You may also acquire a Tleilaxu card (paying its normal cost)." `[Harvest Cells card]`로도 Reclaimed Forces를 "acquire"할 수 있다 — specimen 3을 내고 효과 하나를 고르며 카드는 Row에 남는다(사용자 판정 2026-10-06 "허용", OQ-066). Harvest Cells 자체는 Conflict가 해결된 뒤의 창에서만 낸다(사용자 판정 2026-10-06, OQ-016·OQ-057 (11)).
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

## 8. Go to 11 변형 (`go_to_11` 옵션)

- 룰북은 Immortality가 덱빌딩 선택지를 늘리므로 조금 더 긴 게임을 원하는 그룹(특히 숙련자와 대회)에 11 Victory Point까지 하는 것을 권하고, 4인 게임은 0에서 시작해 10까지 한다고 적는다. 한국어판 이름은 "11점을 향해"다. `[Immortality p. 12]`
- 이 엔진은 4인 전용이므로 옵션이 바꾸는 것은 하나다: setup에서 각 플레이어의 Score marker를 1 `[Main p. 5]`이 아니라 0에 놓는다. Endgame 조건(라운드가 끝났을 때 10 Victory Point 이상인 플레이어가 있거나 Conflict deck이 비었다) `[Main p. 15]`은 그대로다. 변형 이름의 11을 종료 조건으로 옮기지 않는다. Epic Game Mode(`epic_game`)를 함께 켜면 0에서 시작해 12점에 Endgame이다([OQ-093](open-questions.md#oq-093--go-to-11과-epic-game-mode를-함께-쓸-때), [epic-game-mode.md](epic-game-mode.md) 5절).
- Victory Point를 잃는 경우는 Influence가 2 아래로 내려갈 때 `[Main pp. 7, 17]`와 Alliance token을 넘겨줄 때 `[Main p. 7]` `[FAQ p. 1]`뿐이고(카드·확장 효과에 VP를 잃는 것은 없다, 2026-09-28 코드 전수 확인), 둘 다 앞서 얻은 1점을 되돌린다([uprising-systems.md](uprising-systems.md)). 그래서 0에서 시작해도 점수는 0 아래로 내려가지 않는다. 모두 1점을 더 얻어야 하므로 Conflict deck이 비어 끝나는 게임은 늘 수 있다.
- 원판 Dune: Imperium용 변형을 Uprising에 적용하는 것과 Immortality를 켜야만 고를 수 있게 한 것은 공식 규칙이 아니라 사용자 결정이다([OQ-091](open-questions.md#oq-091--go-to-11-변형을-uprising에-적용하는-방식)). 엔진과 CLI의 기본값은 꺼짐이고, 브라우저 새 게임 화면의 체크박스는 기본으로 켜져 있다(Steam 디지털판은 기본으로 꺼 두지만, 사용자가 2026-10-04에 이 기본값을 유지하기로 했다 — OQ-091 (c) 재확인).

## 9. 기존 명세와의 관계

- p. 12의 "Immortality with Epic Game Mode" 문단(Control the Spice를 시작 덱 대신 discard pile에)은 `epic_game` 옵션과 함께 적용한다([epic-game-mode.md](epic-game-mode.md) 4절).

- specimen은 supply의 troop이므로 [player-turns.md](player-turns.md)의 recruit 규칙과 OQ-030이 그대로 적용된다. recruit는 해결 시점의 supply만큼 일어나고, 못 한 수는 같은 player turn 안에서 supply에 troop이 돌아오면 자동으로 채운다(2026-10-04 재판정). specimen 부족분도 같은 방식이다(OQ-049). 플레이어는 specimen을 먼저 돌려보내 supply를 채울 수도 있다 `[Immortality p. 8]`. 반환을 제시하는 창은 OQ-050이다(자기 turn, Combat Intrigue 우선권, supply가 빈 Control 방어).
- Graft는 [player-turns.md](player-turns.md)의 "카드 1장과 일치하는 Agent 아이콘 하나로 Agent 1개 배치" `[Main p. 9]`를 카드 두 장으로 넓히는 예외이며, 두 카드의 Agent box는 space 효과와 같은 자유 순서 그룹에 들어간다(OQ-027).
- Bloodlines와 함께 쓸 때 "lose a troop"·retreat 효과의 Commander 취급은 [bloodlines.md](bloodlines.md) 3절을 따른다.
- 공식 문서가 침묵하는 판정은 [open-questions.md](open-questions.md)에 기록한다.

## 10. 구현 상태

- 2026-10-06(책략 효과 판정, codec v138 — 사용자 판정 "아무 효과 없이 책략을 쓸 수 없는거지", OQ-071의 카드 확장 2): Immortality Intrigue도 효과 중 하나라도 지금 무언가를 바꿀 수 있어야 낸다. Breakthrough는 두 genetic marker 뒤에 덱과 버린 더미가 모두 비면, Illicit Dealings와 Shadowy Bargain의 Endgame option은 Tleilaxu track 끝에서, Shadowy Bargain의 specimen은 supply에 troop이 없으면, Counterattack의 Plot은 배치할 garrison unit이 없으면(아래 v137 줄을 되돌림, OQ-038 재판정), Gruesome Sacrifice는 track이 끝났고 specimen으로 만들 troop도 없으면 낼 수 없다. Harvest Cells는 Conflict 종료 창이 무언가를 바꿀 사본만 넣는다(OQ-016). 세부는 [implementation-audits/immortality.md](../implementation-audits/immortality.md).
- 2026-10-06(Steam 앱과의 카드 전수 대조, codec v137·관측 v30): Harvest Cells는 Conflict 보상 뒤의 창에서만 내고(OQ-016) Reclaimed Forces도 가져갈 수 있다(`acquire_intrigue_reclaimed_forces`, OQ-066). Industrial Espionage(draw와 "If grafted:" 줄)와 Stillsuit Manufacturer(water와 Fremen Alliance 반환)의 Agent box는 아이콘마다 해결한다(OQ-027·OQ-057 (1)). Tleilaxu track 마지막 칸의 비용 줄(위 Tleilaxu track 절)과 c6r6의 6인 진영은 제시하지 않는다(OQ-071·OQ-060). Counterattack의 Plot은 garrison이 비어도 내고 0명을 배치할 수 있다(OQ-057 (6)). Subversive Advisor를 graft 상대로 놓아도 space의 1을 대신한다(OQ-022). Tleilaxu Master는 소유자가 Manipulate로 빼 둔 카드도 인쇄 비용으로 얻을 수 있다(`[FAQ p. 3]`). 세부는 [implementation-audits/immortality.md](../implementation-audits/immortality.md).
- 2026-10-02: arrow 비용을 낼 수 없는 research 보너스(c7r3의 Intrigue trash, c8r6의 Solari 7)도 보너스 창을 열고 `decline_research_bonus` 하나만 제시한다. 지불 줄은 `research_bonus_block`(NO_INTRIGUE, SOLARI)의 이유와 함께 회색으로 보이고, 이벤트 `research_bonus_unavailable`은 없어졌다(2026-09-30 사용자 판정 "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다", 3절). codec v125(L2 문장, 템플릿 변화 없음).
- 2026-09-26: Twisted Mentat("You may recall the Agent you sent this turn.")이 recall하는 "이번 turn 보낸 Agent"는 Duncan Idaho(Bloodlines)의 Into the Fray가 그 사이 Conflict로 옮겼어도 여전히 그 Agent이므로, Mentat의 recall이 Conflict까지 따라간다(2026-09-26 사용자 판정, OQ-068; `docs/rules/uprising-systems.md` 97행).
- 2026-09-16: 점유된 space로의 graft 배치는 놓는 카드가 Ghola의 약속(OQ-057) 없이 그 space에 닿을 때만(또는 놓는 카드가 Tleilaxu Infiltrator일 때만) 제시한다 — 한 turn에 카드는 두 장뿐이라 `[Immortality p. 10]` "Infiltrator가 partner"와 "Ghola가 partner"를 한 partner가 다 지킬 수 없다. 전 확장 기준선 seed 42에서 Long Reach(BG Bond 아이콘)·Ghola·Infiltrator를 든 좌석이 점유된 Arrakeen에 graft 배치를 받고 partner 선택에 합법 행동이 없던 결함([evaluation/baseline-2026-09-10.md](../evaluation/baseline-2026-09-10.md) 18절(k)).
- 2026-09-08 슬라이스 6: 웹 UI(Tleilaxu Row·Bene Tleilax board 패널·좌석의 specimen/token/Family Atomics/Chairdog/Usurp 표시), 대규모 소크 830판 실패 0(적발한 결함 3계열 수정: Research draw의 이중 셔플, Usurp 배치의 상대 부재 교착, heuristic의 graft switch 무한 반복), census에서 Immortality 구성물 0회 없음. **M13 완료.**
- 2026-09-08 슬라이스 5c-2: Ghola(상대 grafted 카드의 Agent box를 빌린다 — `active_agent_card`), Chairdog(자기 Reveal turn 시작 때 상대 grafted 카드를 hand로), Usurp(Imperium Row 카드와도 graft할 수 있고, 빌린 카드는 turn이 닫히면 자동 trash — 트리거 발동, OQ-054). 관측 v15(좌석 scalar 51). Slig Farmer의 아이콘 셈은 OQ-055. **이로써 Immortality의 카드 play data(Imperium 25종, Intrigue 11장, Tleilaxu 18장 + Piter)가 완결됐다.**
- 2026-09-08 슬라이스 5c-1: Tleilaxu 6종 + 프로모 Piter — Industrial Espionage(draw; graft면 Research + specimen), Scientific Breakthrough(Research; (2M) 자기 trash → VP), Guild Impersonator(이번 turn spice를 얻었으면 Guild Influence), Slig Farmer(상대 카드의 인쇄 아이콘당 Solari 1; Solari 5 → Tleilaxu), Stitched Horror(water·troop·trash·Tleilaxu 중 둘), Beguiling Pheromones(Faction space 방문 시 grafted 카드 하나 trash → 그 진영 Influence; `[FAQ p. 1]`), Piter(troop 1 잃기 → 카드 2 + Research). 남은 것은 Ghola·Chairdog·Usurp(5c-2).
- 2026-09-08 슬라이스 5b-2: 남은 Imperium 8종 — Dissecting Kit(graft 상대 trash → specimen; 상대의 미발동 box는 OQ-022로 소멸), For Humanity(선택 Influence; BG Alliance: Influence 1 잃기 → VP — 2026-09-26 카드 면 재판독으로 한 진영 Influence **2** 잃기로 정정 `[For Humanity card]`), High Priority Travel(Guild 2: draw 또는 Combat 아이콘), Imperium Ceremony(Intrigue 두 장 peek → keep 1, `INTRIGUE_PEEK` frame, 관측 v14, OQ-052), Interstellar Conspiracy(spice 1 —AND— Emperor/Guild 상대와 graft 시 선택 Influence), Shadout Mapes(Reveal: troop 1 배치 또는 후퇴), Tleilaxu Master((1M) 비용 6 이하 카드 획득, (2M) hand로; Reveal Research ×2), Tleilaxu Surgeon(specimen 2 → Tleilaxu 2; Reveal: 한 존의 troop 2 잃기 → specimen 2, OQ-053). 이로써 Immortality Imperium 25종 전부가 play된다. 부수 수정: 획득한 카드의 Research box가 여는 방향 frame이 Intrigue 획득·Price is No Object·Leader Signet 획득의 frame을 묻지 않도록 위로 올린다.
- 2026-09-08 슬라이스 5b-1: Imperium 15종 — Bene Tleilax Lab, Blank Slate, Clandestine Meeting, Corrupt Smuggler, Keys to Power, Lisan al Gaib, Long Reach, Occupation, Organ Merchants, Replacement Eyes, Sardaukar Quartermaster, Show of Strength, Spiritual Fervor, Stillsuit Manufacturer, Throne Room Politics. 새 기계: 인쇄 조건부 Agent 아이콘(`icon_condition`: BG Bond, 상대 모두보다 많은 배치 troop — play 시점 판정), 획득 box `GAIN_ONE_SPICE`·`RECRUIT_THREE_TROOPS`, trash trigger `ADVANCE_TLEILAXU`, Reveal box의 Tleilaxu·Research 아이콘(소유자 시점의 `advance_reveal_tleilaxu`/`advance_reveal_research`), specimen 지불(`pay_agent_card_specimen`), "둘 선택" Influence, graft 상대가 뒤늦게 주는 Bond의 재판정.
- 2026-09-08 슬라이스 5a: Intrigue 11장 전부(effect DSL). 새 노드: 조건 `GeneticMarkersAtLeast`·`SolariAtLeast`·`SpiceAtLeast`·`OpponentPlayedCombatIntrigue`·`AllConditions`, 보상 `Research`·`AdvanceTleilaxu`·`GenerateSpecimens`·`AcquireTleilaxuCard`(선택형 slot, `acquire_intrigue_tleilaxu`/`decline_intrigue_tleilaxu`)·`RevealPersuasionThisRound`(round 한정 좌석 필드), trigger `OnTroopsLostAtConflictEnd`(Harvest Cells: Combat 중 play해 face-up으로 기다리다 Combat 정리에서 supply로 돌아간 troop·Commander 수가 3 이상이면 발동, 아니면 만료). Counterattack의 "상대가 Combat Intrigue를 play했으면"은 `GameState.combat_intrigue_players`(Conflict마다 초기화). 관측 v13.
- 2026-09-08 슬라이스 4: 5절의 Graft — `agent_turn`의 `graft` 인자로 첫 카드와 space를 정한 뒤 `graft_partner` frame의 `choose_graft_partner(card_id)`로 둘째 카드를 hand에서 고른다(Graft 카드는 혼자 play 불가, 일반 카드 둘은 graft 불가, 두 카드 모두 in play). 효과 frame은 활성 카드(`card_id`)와 상대(`graft_card_id`)의 Agent box를 따로 대기시키고 `switch_graft_card`로 바꿔 소유자 순서로 해결한다("if grafted"는 `graft_card_id` 유무, "the other grafted card"는 비활성 카드). trash된 상대의 미발동 box는 OQ-022로 만료된다. Tleilaxu Infiltrator는 상대 Agent가 있는 space를 열고(둘 중 하나가 Infiltrator일 때), Blank Slate는 graft 시 진영 아이콘 4개를 얻는다. 카드: Face Dancer, Face Dancer Initiate, Corrino Genes, Unnatural Reflexes, Tleilaxu Infiltrator, Twisted Mentat, Bene Tleilax Researcher, Planned Coupling. Reveal box의 genetic marker 조건(`minimum_genetic_markers`) 포함. `rules/graft.py`.
- 2026-09-08 슬라이스 3: 4절의 Tleilaxu Row — Reveal turn의 `acquire_tleilaxu(instance_id[, to_deck_top])`(specimen 지불, discard pile 또는 첫 genetic marker 뒤 deck 맨 위, Row 보충, 획득 box 해결)와 `acquire_reclaimed_forces(choice=troops|tleilaxu)`(specimen 3, 카드는 Row에 남음; troop 2는 Reveal의 Combat 아이콘 배치 한도에 합산). 획득 box에 `RESEARCH`·`ADVANCE_TLEILAXU`(Spiritual Fervor·Subject X-137)를 더해 Imperium 획득 경로 4곳(Reveal·Solari·Manipulate·Intrigue)에서도 해결한다. 첫 Tleilaxu 카드 3장(Contaminator, From the Tanks, Subject X-137)이 play되며 그때부터 setup이 `setup:tleilaxu_deck`을 셔플한다. `rules/tleilaxu_row.py`.
- 2026-09-08 슬라이스 2: 3절의 Bene Tleilax board 전부와 6·7절 — setup(token 2개, spice 2, Tleilaxu deck 셔플과 Row 2장, Experimentation 시작 덱, Family Atomics), research 전진(`advance_research`: 한 방향이면 즉시, 두 방향이면 `research_advance` frame의 `choose_research_space`; 보너스 즉시 해결, research 연쇄, genetic marker 이벤트, 두 번째 marker 뒤 draw 대체), research 보너스 frame(`choose_research_influence`, `trash_for_research_bonus`/`decline`, `pay_research_bonus`/`decline`; 살 수 없으면 `research_bonus_unavailable` — 2026-09-30 사용자 판정으로 바뀜, 2026-10-02부터는 창을 열고 `decline_research_bonus`만 제시한다, 3절), Tleilaxu track(`advance_tleilaxu`: Intrigue·VP·첫 도달 spice 2, 끝에서는 OQ-048), specimen 생성(`generate_specimens`, 부족분 OQ-049)·자유 반환(`return_specimen`, 창은 OQ-050)·지출(`spend_specimens`), 개정 Research Station(`research` 보드 아이콘), Experimentation(Agent: Research, Reveal: 소유자 시점의 `generate_reveal_specimens`), Family Atomics(`use_family_atomics`, 제거 카드는 OQ-051). 관측 v12, codec v96(`immortality` 카탈로그에 템플릿 추가; 기본 카탈로그는 `resolve_board_effect(research)` 1개만 늘어 4,367). 세부는 [implementation-audits/immortality.md](../implementation-audits/immortality.md).
- 2026-09-08 슬라이스 1: `RulesetConfig(immortality=True)` 옵션과 이 명세, 출처 등록, research track·Tleilaxu track 전사(`content/immortality/board.py`), Tleilaxu deck 18장 + Reclaimed Forces + 프로모 Piter의 카탈로그(`content/immortality/tleilaxu.py`), Imperium 25종·Intrigue 11종의 카탈로그 항목(`immortality_only`). 전사가 끝난 카드만 옵션 덱에 들어가며 아직 한 장도 없다. 서버·UI 체크박스, sweep/tournament `--immortality`, coverage census, 저장 문서 플래그, 체크포인트 룰셋 식별자(`+immortality`)까지 연결했다.
- 2026-09-09: 디자이너 판정 채택([OQ-057](open-questions.md#oq-057--디자이너-커뮤니티-판정의-일괄-채택-2026-09-09), OQ-054 보강) — Ghola + Long Reach는 세 아이콘 전부(`ghola_partner`), Usurp로 빌린 Stillsuit Manufacturer는 hand로 돌아오지 않음, Tleilaxu Master의 Reveal Research 2개는 행동 하나에 하나씩 따로 해결, Imperium Ceremony의 keep은 Suspensor Suits의 troop을 냄.
- 2026-09-09(배치 B): "Choose Two"(Stitched Horror·Long Reach·Rapid Engineering·Propaganda)는 두 선택을 먼저 받고 해결하고, Combat 보상으로 받은 Harvest Cells는 정리 전 `conflict_end_trigger` 창에서 즉시 play할 수 있다(OQ-057; 관측 v17, codec v101). 2026-09-26 정정: 창에서 play한 카드는 face-up으로 대기해 정리의 troop 반환 뒤 발동한다("troops that return to your supply are considered 'lost'" `[FAQ p. 1]`; 전에는 반환 전에 발동해 supply가 비면 specimen을 못 받았다).
