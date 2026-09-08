# Immortality implementation audit

기준일: 2026-09-08 — 슬라이스 1(출처·명세·옵션 골격·카탈로그), 슬라이스 2(Bene Tleilax board·specimen·Research Station·Experimentation·Family Atomics), 슬라이스 3(Tleilaxu Row·Reclaimed Forces·첫 카드 3장), 슬라이스 4(Graft와 Graft 카드 8장), 슬라이스 5a(Intrigue 11장), 슬라이스 5b-1(Imperium 15종), 슬라이스 5b-2(Imperium 8종 — Imperium 25종 전부), 슬라이스 5c-1(Tleilaxu 6종 + 프로모 Piter), 슬라이스 5c-2(Ghola·Chairdog·Usurp — 카드 play data 전부), 슬라이스 6(UI·대규모 소크·census) 완료 — **M13 마감**.

규범 근거는 [`rules/immortality.md`](../rules/immortality.md)이며, 콘텐츠 정의는 `content/immortality/board.py`(research·Tleilaxu track), `content/immortality/tleilaxu.py`(Tleilaxu deck·Reclaimed Forces), `content/uprising/imperium.py`·`intrigue.py`의 `immortality_only` 항목이 소유한다. 모든 동작은 `RulesetConfig(immortality=True)`에서만 켜진다.

## 검증 방법

- 룰북: 공식 URL의 PDF를 scratchpad에서 받아(sha256 고정, 저장소에 넣지 않음) 텍스트를 추출하고, Bene Tleilax board는 p. 3의 board 그림을 500 dpi로 잘라 판독했다. 아이콘은 `assets/icons/`의 Uprising 아이콘(Solari = 회색 원, spice = 주황 육각, VP = 금색 구, Intrigue = 금색 카드, trash = 검은 카드의 X, Influence 선택 = 금색 ?)과 대조했다.
- 카드: 에셋 저장소 `cards/en/immortality/{imperium,intrigue,tleilaxu,starting,promo}/` 57장을 전부 직접 판독했고, Agent 아이콘 열은 `assets/icons/agent_icon_*.png`와 나란히 대조했다(Fremen = 파란 원 문양, City = 파란 원, Emperor = 투구, Guild = 붉은 ∞, BG = 보라 가면, Landsraad = 초록 오각, Spice Trade = 노란 삼각). 흰 X 검 두 자루는 Combat 아이콘(trash 아이콘은 검은 카드 위의 흰 ✕)이다.
- 수량: Dune Cards Hub의 `/api/cards`(`physicalCopies`)로 확인했다. Imperium 25종 27장, Intrigue 11종 11장, Tleilaxu 18종 18장. 룰북 p. 3의 Imperium 30장·Intrigue 15장과 어긋나는 Imperium 3장·Intrigue 4장은 어느 identity의 추가 사본인지 확인하지 못했다(하브에는 없음). 카탈로그 수량을 채택했고, 실물 확인이 되면 `copies`와 census 테스트를 갱신한다.

## 카드 전사 (슬라이스 1, 카드면)

아래 표는 2026-09-08에 카드면을 직접 판독한 전사이며, play data 구현은 이후 슬라이스에서 이 표를 기준으로 진행한다. `◆n` = Persuasion n(파란 마름모), `⚔` = 검, `(1M)`/`(2M)` = genetic marker 1개/2개 조건, `▶` = arrow(비용 → 보상), `◇?` = Influence 1 선택.

### Tleilaxu deck 18장 + Reclaimed Forces + 프로모

| 카드 | specimen 비용 | Agent 아이콘 | Agent box | Reveal box |
| --- | --- | --- | --- | --- |
| Beguiling Pheromones | 3 | City, Spice Trade | GRAFT: 이번 turn Faction board space에 Agent를 보냈으면, grafted 카드 하나를 trash하고 그 Faction Influence 1 추가 | ◆1 ⚔1 |
| Chairdog | 2 | City | GRAFT: 자신의 Reveal turn 시작 때 *다른* grafted 카드를 play에서 hand로 되돌린다 | ◆1 |
| Contaminator (Fremen) | 1 | Fremen | Tleilaxu | ◆1 |
| Corrino Genes (Emperor) | 1, 획득 시 Solari 2 | Emperor | If grafted: Tleilaxu | ◆1 |
| Face Dancer (Emperor·Guild·Fremen) | 2 | Emperor, Guild, Fremen | GRAFT: draw 1 | ◆1 |
| Face Dancer Initiate (Emperor·Guild·Fremen) | 1 | Emperor, Guild, Fremen | GRAFT: (효과 없음) | ◆1 |
| From the Tanks | 2 | Landsraad | troop 2 | ◆1 |
| Ghola | 3 | City | GRAFT: 이 카드는 *다른* grafted 카드와 같은 Agent box를 가진다 | ◆1 ⚔1 |
| Guild Impersonator (Guild) | 2 | Guild | GRAFT: 이번 turn spice를 얻으면 Guild Influence 1 | ◆1 |
| Industrial Espionage | 1 | Landsraad | draw 1; If grafted: Research + specimen 1 | ◆1 |
| Reclaimed Forces (Row 고정) | 3 | — | — | 획득 box: troop 2 —OR— Tleilaxu |
| Scientific Breakthrough | 3 | Landsraad, City, Spice Trade | Research; (2M): 이 카드 trash ▶ VP 1 | ◆1 ⚔1 |
| Slig Farmer | 2 | Landsraad | GRAFT: *다른* grafted 카드의 Agent 아이콘마다 Solari 1; Solari 5 ▶ Tleilaxu | ◆1 |
| Stitched Horror | 3 | City | GRAFT: 둘 선택 — water 1, troop 1, trash, Tleilaxu | ◆1 ⚔1 |
| Subject X-137 | 2, 획득 시 Tleilaxu | Landsraad, Spice Trade | (1M): Tleilaxu | ◆1 |
| Tleilaxu Infiltrator | 2 | City | GRAFT: 이번 turn 적 Agent가 자신의 Agent를 막지 않는다. draw 1 —AND— (2M): Intrigue 1 | ◆1 |
| Twisted Mentat | 4 | Landsraad, City | GRAFT: 이번 turn 보낸 Agent를 recall할 수 있다 | ◆1 ⚔1 specimen 1 |
| Unnatural Reflexes | 3 | Spice Trade | GRAFT: (1M): draw 2 | ◆1 ⚔1 |
| Usurp | 4 | (없음) | GRAFT: Imperium Row의 카드에 acquire하지 않고 graft할 수 있다. 그러면 turn 끝에 그 카드를 trash | ◆1 ⚔1 specimen 1 |
| Piter, Genius Advisor (프로모) | 3 | Landsraad, Spice Trade | Lose a troop ▶ draw 2 + Research | ◆1 ⚔1 |

### Imperium 25종

| 카드 | 비용 | Faction | Agent 아이콘 | Agent box | Reveal box |
| --- | --- | --- | --- | --- | --- |
| Bene Tleilax Lab | 2 | — | City, Spice Trade | specimen 1 | ◆1; (1M): spice 1 |
| Bene Tleilax Researcher | 4 | — | Landsraad | GRAFT: Research | ◆1; (1M): +◆1; (2M): +◆1 |
| Blank Slate | 1 | — | Landsraad, City, Spice Trade (+ 흐린 Emperor·Guild·BG·Fremen) | If grafted: Emperor, Guild, BG, Fremen 아이콘을 가진다 | ◆1 |
| Clandestine Meeting | 4 | BG | (없음) | BG Influence 1 + Intrigue 1 | ◆2 |
| Corrupt Smuggler | 3 | Guild·Fremen | Guild, Spice Trade | If grafted: spice 2 | ◆1 ⚔1 |
| Dissecting Kit ×2 | 2 | — | Landsraad, City | GRAFT: *다른* grafted 카드 trash ▶ specimen 1 | ◆1; (1M): Tleilaxu |
| For Humanity | 7 | BG | BG, Landsraad, Spice Trade | ◇? | ◆2; BG Alliance: Influence 1 잃기 ▶ VP 1 |
| High Priority Travel | 1 | Guild | Landsraad, Spice Trade | Guild Influence 2: draw 1 —OR— Combat 아이콘 | ◆1 Solari 1 |
| Imperium Ceremony | 6 | Emperor·Guild | Emperor, Guild, Landsraad | Intrigue deck 맨 위 2장을 보고 1장 keep, 나머지는 맨 위로 | ◆3 |
| Interstellar Conspiracy | 4 | — | City | GRAFT: spice 1 —AND— Emperor 또는 Guild 카드와 graft했으면 ◇? | ◆2 |
| Keys to Power | 5 | Guild·BG | Guild, BG, Landsraad | Emperor Influence 2: spice 2 | ◆2 |
| Lisan al Gaib | 4, 획득 시 spice 1 | BG·Fremen | Fremen, City, Spice Trade | 다른 BG 카드가 play 중이면 Fremen Influence 1 | ◆1; Fremen Bond: ⚔2 |
| Long Reach | 6 | BG | (흐린 Landsraad·City·Spice Trade) | 다른 BG 카드가 play 중이면 Landsraad·City·Spice Trade 아이콘을 가진다. 둘 선택: Emperor·Guild·BG·Fremen Influence 1 | ◆1 Intrigue 1 |
| Occupation | 8, 획득 시 troop 3 | Guild | Emperor, Guild, BG, Fremen, City, Spice Trade | draw 1 + Combat 아이콘 | water 1, spice 1, troop 1 |
| Organ Merchants | 3 | — | City, Spice Trade | specimen 1 ▶ Solari 4 | ◆1 Solari 1 |
| Planned Coupling | 3 | BG | BG | GRAFT: draw 1 | ◆1 |
| Replacement Eyes | 5 | — | City | GRAFT: trash될 때 Tleilaxu. trash ▶ draw 1 | ◆1 ⚔1 |
| Sardaukar Quartermaster | 2 | Emperor | Landsraad, City | If grafted: troop 1 + draw 1 | ◆1 ⚔2 |
| Shadout Mapes | 2 | Fremen | Fremen, Spice Trade | (없음) | ◆1 ⚔1; troop 1개를 deploy하거나 retreat할 수 있다 |
| Show of Strength | 3 | Emperor·Fremen | (흐린 Landsraad·Spice Trade) | 배치한 troop이 각 상대보다 많으면 Landsraad·Spice Trade 아이콘을 가진다. draw 2 | ◆1 ⚔2 |
| Spiritual Fervor | 3, 획득 시 Research | — | Spice Trade | (없음) | ◆1 specimen 1 |
| Stillsuit Manufacturer | 5 | Fremen | Fremen, City | water 1 —AND— Fremen Alliance: 이 카드를 play에서 hand로 되돌린다 | ◆1 —AND— Fremen Bond: spice 2 |
| Throne Room Politics | 4 | Emperor·BG | Emperor | troop 1 + trash | ◆1 BG Influence 1 |
| Tleilaxu Master ×2 | 5 | — | Landsraad, Spice Trade | (1M): 비용 6 이하 카드 1장을 acquire할 수 있다. (2M): 그 카드를 hand에 둔다 | ◆1 Research Research |
| Tleilaxu Surgeon | 3 | — | Emperor, City | specimen 2 ▶ Tleilaxu 2 | ◆2; troop 2 잃기 ▶ specimen 2 |

Sardaukar Quartermaster는 카드면에 "Sarduakar"로 오식돼 있다(하브도 같은 슬러그); 프로젝트 ID는 `sardaukar_quartermaster`다.

### Intrigue 11종

| 카드 | timing | 전사 |
| --- | --- | --- |
| Breakthrough | Plot | Research |
| Counterattack | Plot / Combat | garrison에서 troop 최대 2개를 Conflict에 deploy —OR— 이 Conflict에서 상대가 Combat Intrigue를 play했으면 ⚔4 |
| Disguised Bureaucrat | Plot | (1M): spice 1; (2M): ◇? |
| Economic Positioning | Combat / Endgame | troop 2개 retreat ▶ Solari 3 —OR— Solari 10 이상이면 VP 1 |
| Gruesome Sacrifice | Combat | Conflict의 자기 troop 2개 잃기 ▶ Tleilaxu + specimen 2 |
| Harvest Cells | Combat | Conflict 끝에 troop을 3개 이상 잃으면: specimen 2. Tleilaxu 카드 1장을 (정상 비용으로) acquire할 수도 있다 |
| Illicit Dealings | Plot | Tleilaxu |
| Shadowy Bargain | Plot / Endgame | specimen 1 —OR— Tleilaxu |
| Study Melange | Plot / Endgame | spice 1 —OR— spice 3 이상이면 (2M): VP 1 |
| Tleilaxu Puppet | Plot / Endgame | 이번 round Reveal turn에 ◆1 —OR— High Council 자리가 있으면 (2M): VP 1 |
| Vicious Talents | Combat | ⚔2; (1M): +⚔2; (2M): +⚔2 |

Illicit Dealings의 에셋 파일명은 하브 슬러그 오타 "Illicit Deadlings"를 따른다(`content_id`로 연결).

### Experimentation (starting card ×2)

Spice Trade 아이콘. Agent: Research. Reveal: ◆1 specimen 1. 카드 이름 앞의 작은 삼각형은 시작 카드 표시다.

## 구현된 동작

| 영역 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| 옵션 | `RulesetConfig(immortality=True)`, identifier `+immortality`; 서버 `immortality` 필드·UI 체크박스·상태 배지, 저장 문서 플래그, sweep/tournament `--immortality`, coverage census, 체크포인트 룰셋 파싱. | `[Main p. 18]`. Bloodlines와 독립. |
| 카탈로그 | Imperium 25종(`immortality_only`), Intrigue 11종, Tleilaxu deck 18종 + Reclaimed Forces + 프로모 Piter(`content/immortality/tleilaxu.py`, instance `tleilaxu:<id>:<copy>`). play data가 없는 카드는 옵션을 켜도 덱에 들어가지 않는다. | 관측 identity 우주에 Imperium 25·Intrigue 11이 들어와 관측 v11. Tleilaxu 카드는 아직 관측 우주 밖(슬라이스 2). |
| board 전사 | research track 22칸(시작 포함)과 인접 규칙 `research_next_space_ids`, genetic marker 열 4·8, Tleilaxu track 8칸의 보너스, setup spice 2·네 번째 칸, Row 2장. | `[Immortality pp. 3-7, 16]`. |

## 슬라이스 2: Bene Tleilax board

| 영역 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| 상태 | `PlayerState.research_space`(칸 ID, 옵션 off ""), `tleilaxu_space`(0~7), `specimens`(troop 12개 불변식에 포함), `family_atomics`; `GameState.tleilaxu_deck`(비공개 순서)·`tleilaxu_row`·`tleilaxu_track_spice`. 옵션이 꺼지면 전부 비어 있어야 한다. | `[Immortality pp. 4-8, 12]`. |
| Setup | `create_unshuffled_players(immortality=)`가 Dune, the Desert Planet 2장을 Experimentation 2장으로 바꾸고, `_immortality_setup`이 Tleilaxu deck을 seeded chance `setup:tleilaxu_deck`으로 섞어(play data가 있는 카드가 없으면 생략) Row 2장을 deal하며, `_with_immortality`가 token·spice 2·Family Atomics를 놓는다. 고정 Leader setup과 draft setup 모두. Bloodlines 결정 뒤에 해결해 기존 chance 순서를 보존. | `[Immortality pp. 4-5]`. |
| Research 전진 | `advance_research`: 두 번째 marker 열이면 card draw 대체, 다음 칸이 하나면 즉시 이동, 둘이면 `research_advance` frame(`choose_research_space`). `move_research_token`이 칸 보너스를 즉시 해결하고 marker 도달 이벤트를 낸다. research 보너스 칸은 재귀로 다시 전진한다. | `[Immortality pp. 6, 16]`. 보드 아이콘·Agent box 모두 frame 정리 뒤에 전진을 열어 방향 선택 frame이 그 위에 놓인다. |
| 보너스 | specimen·Tleilaxu·Solari·spice는 자동; trash+specimen은 specimen 뒤 `optional_trash` frame(검은 trash 아이콘은 선택 `[Main p. 20]`); Influence 선택·trash→draw+Intrigue·Solari 7→Tleilaxu 2는 `research_bonus` frame. arrow 비용을 낼 수 없으면(trash할 카드 없음, Solari 부족) frame 없이 `research_bonus_unavailable`. | `[Immortality p. 3 board artwork]`. c8r6은 저해상도 판독이라 UI 슬라이스에서 재확인. |
| Tleilaxu track | `advance_tleilaxu(steps)`: 칸 2·6 Intrigue, 4 VP + 첫 도달자 spice 2(`tleilaxu_track_spice` 소진), 7 VP; 끝에서는 `tleilaxu_track_end`(OQ-048). | `[Immortality p. 7]`. |
| Specimen | `rules/specimens.py`: `generate_specimens`(supply만큼, 부족분 `specimens_short`, OQ-049), `spend_specimens`; `return_specimen`은 소유자의 turn·효과·Reveal frame에서 하나씩(OQ-050). Reveal 카드의 specimen은 `reveal_pending_gains`의 `specimens` 항목 → `generate_reveal_specimens`(OQ-045). | `[Immortality p. 8]`. |
| Research Station | `static_board_effects(..., immortality=True)`가 `(Draw 2, ResearchEffect)`; 아이콘 키 `research`는 `AUTOMATIC_BOARD_ICONS`에 들어가 `resolve_board_effect(effect=research)`로 해결한다. | `[Immortality pp. 5, 16]` `[Main p. 18]`. |
| Experimentation | `PersonalCardAgentEffect.RESEARCH`, `PersonalCardRevealEffect(specimens=1)`; `STARTING_CARDS_BY_ID`에 포함되지만 `STARTING_DECK`(7종)은 그대로. | `[Immortality p. 5]` `[card face]`. |
| Family Atomics | `use_family_atomics`: 소유자의 turn frame들에서 1회, Row 전부를 `imperium_removed`로 보내고 deck 맨 위 5장으로 새 Row(OQ-051). | `[Immortality p. 12]`. |
| 관측·codec | 관측 v12(위 상태 전부 공개), codec v96: `immortality` 카탈로그에 `choose_research_space` ×21·`choose_research_influence` ×4·`trash_for_research_bonus`(카드마다)·`pay/decline_research_bonus`·`return_specimen`·`use_family_atomics`·`generate_reveal_specimens`; 기본 카탈로그는 `resolve_board_effect(research)` 1개만 늘었다. heuristic 우선순위와 UI 라벨을 추가. | 소크: random·heuristic 각 6판에서 모든 경로가 발화(연쇄·marker·atomics 포함). |

## 슬라이스 3: Tleilaxu Row

| 영역 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| 획득 | `rules/tleilaxu_row.py`: REVEAL frame 소유자에게 Row 카드마다 `acquire_tleilaxu(instance_id)`(specimen ≥ 비용), 첫 genetic marker 뒤에는 `to_deck_top=True` 변형도. 지불은 `spend_specimens`(tanks→supply), 카드는 discard pile 또는 deck 맨 위, Row는 deck 맨 위에서 보충(`refill_tleilaxu_row`), 획득 box는 Imperium과 같은 `resolve_acquisition_bonus`(Tleilaxu-aware) + `apply_acquisition_track_effects`. deck 맨 위로 보낸 카드의 instance는 이벤트에 싣지 않는다(deck 순서는 비공개, OQ-010). | `[Immortality pp. 6, 8-9]`. Imperium Row 획득 효과·Persuasion 효과는 Row를 보지 않으므로 자연히 배제된다. |
| Reclaimed Forces | `acquire_reclaimed_forces(choice)`: specimen 3, `troops`(recruit 2, `reveal_troops_recruited`에 합산) 또는 `tleilaxu`(1 전진); 카드는 Row에 남는다. | `[Immortality p. 9]` `[Reclaimed Forces card]`. |
| 획득 box | `PersonalCardAcquisitionEffect.RESEARCH`·`ADVANCE_TLEILAXU`는 카드가 존에 들어간 뒤 state 수준에서 해결(`apply_acquisition_track_effects`; research는 방향 선택 frame을 열 수 있다). Imperium 획득 경로 4곳과 Tleilaxu 경로 모두. | Subject X-137, (슬라이스 5의) Spiritual Fervor. |
| 카드 | Contaminator(Fremen, `ADVANCE_TLEILAXU`), From the Tanks(`RECRUIT_TWO_TROOPS`), Subject X-137(`ADVANCE_TLEILAXU_IF_ONE_MARKER`, 해결 시점 판정 OQ-028; 획득 box Tleilaxu). Graft 카드는 슬라이스 4 전까지 덱 밖. | 카드면 전사표와 일치. |
| codec | `immortality` 카탈로그에 `acquire_tleilaxu` ×2/카드, `acquire_reclaimed_forces` ×2, Tleilaxu 카드의 Agent 배치 템플릿, trash 계열 템플릿의 Tleilaxu instance; Bloodlines 없이도 `optional_trash` 템플릿(trash+specimen 칸). | codec v96 그대로(옵션 카탈로그만 커짐: 4,490→4,578). |

## 슬라이스 4: Graft

| 영역 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| 배치 | `legal_agent_actions`: Graft 카드(`ImperiumCardEntry.graft`)는 `graft=True` 변형만, 일반 카드는 단독과 (hand에 Graft 상대가 있으면) graft 변형. 아이콘은 첫 카드 기준(`effective_agent_icons(grafted=)`; Blank Slate는 진영 4개 추가). 상대 Agent가 점유한 space는 hand에 Tleilaxu Infiltrator가 있을 때 graft 배치로 열린다. | `[Immortality p. 10]` "You may use an Agent icon from either card": 아이콘을 내는 카드를 첫 카드로 두면 어떤 쌍이든 표현된다. |
| 상대 선택 | `apply_agent_action(graft)`가 효과 frame 위에 `graft_partner` frame을 밀고, `choose_graft_partner(card_id)`는 hand의 카드 중 (첫 카드 또는 후보가 Graft) 조건을 만족하는 것만; 점유 space였으면 둘 중 하나가 Infiltrator여야 한다. 상대는 hand→in play, 효과 frame의 `graft_card_id`·`graft_pending_effect`·`graft_pending_icons`에 자기 box가 대기한다(`agent_effect_is_available`로 판정). | 두 카드 모두 "보낸" 것: Bond·"in play" 판정은 in_play로 자연 성립. |
| 해결 | `switch_graft_card`(효과 frame, 상대 box가 대기 중이고 Long Live 선택 중이 아닐 때)가 `card_id`↔`graft_card_id`와 pending 플래그·아이콘을 맞바꿔 기존 Agent box 기계로 해결한다. `agent_turn_has_other_pending_effects`가 `graft_pending_effect`를 본다. `expire_trashed_card_effects`는 상대 카드의 미발동 box도 만료한다(FAQ의 Beguiling Pheromones 판정). | `[Immortality pp. 10-11]` `[FAQ p. 1]`. `is_grafted`/`other_grafted_card_id`(`rules/effects.py`). |
| 카드 | Face Dancer(GRAFT draw 1), Face Dancer Initiate(빈 box), Planned Coupling(Imperium, GRAFT draw 1), Bene Tleilax Researcher(Imperium, GRAFT Research; Reveal (1M)+1·(2M)+1 Persuasion → `minimum_genetic_markers`), Corrino Genes(`ADVANCE_TLEILAXU_IF_GRAFTED`), Unnatural Reflexes(`DRAW_TWO_IF_ONE_MARKER`), Tleilaxu Infiltrator(`DRAW_ONE_AND_INTRIGUE_IF_TWO_MARKERS`: cards·intrigue 아이콘, Intrigue는 해결 시점에 marker 2 판정), Twisted Mentat(`MAY_RECALL_AGENT_SENT_THIS_TURN`: recall 아이콘을 이번 turn의 space로 한정 + `decline_agent_card_recall`). | 조건은 해결 시점 판정(OQ-028). |
| codec | `immortality` 카탈로그: 모든 카드의 배치 템플릿에 `graft` 변형(Graft 카드는 graft만), `choose_graft_partner` ×개인 카드, `switch_graft_card`, `decline_agent_card_recall`. 기본 카탈로그 불변(4,367). | 4,578→6,857. |

## 슬라이스 5a: Intrigue 11장

| 영역 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| DSL | `effect_dsl.py`: 조건 `GeneticMarkersAtLeast(1|2)`·`SolariAtLeast`·`SpiceAtLeast`·`OpponentPlayedCombatIntrigue`·`AllConditions`(Study Melange·Tleilaxu Puppet의 두 조건); 보상 `Research`·`AdvanceTleilaxu(count)`·`GenerateSpecimens(count)`·`AcquireTleilaxuCard`·`RevealPersuasionThisRound`; trigger `OnTroopsLostAtConflictEnd(minimum)`(Combat timing 허용). | 전사표(위 Intrigue 표)와 1:1. |
| 해석 | `effect_interpreter.apply_rewards`가 자원 뒤에 specimen → Tleilaxu → Research 순으로 state 수준에서 해결(research는 방향 frame을 열 수 있어 마지막). `AcquireTleilaxuCard`는 선택 slot: Row 카드(specimen ≥ 비용)와 deck 맨 위 변형, 거절. Harvest Cells는 자동 보상(specimen 2)을 OQ-015대로 소유자가 `resolve_intrigue_rewards`로 먼저 받아야 살 수 있다. | `[Immortality pp. 6-8]`. |
| Counterattack | `apply_intrigue_play`가 Combat 중 play된 Combat option의 좌석을 `combat_intrigue_players`에 기록하고 `finish_combat`이 비운다(관측 세그먼트). | "in this Conflict" = 이번 Combat. |
| Harvest Cells | Combat에 play하면 face-up으로 대기; `finish_combat`이 정리 전 각 좌석의 Conflict troop+Commander 수를 "잃은 troop"으로 삼아(FAQ p. 1 Chani: supply로 돌아간 troop은 lost) 3 이상이면 `resolve_faceup_trigger_option`으로 발동(Makers 전에 INTRIGUE_CHOICE frame), 아니면 `intrigue_expired`로 discard. | `[FAQ p. 1]` `[card face]`. |
| Tleilaxu Puppet | `PlayerState.reveal_persuasion_round_bonus`: Round Start에 0, `begin_reveal_turn`의 Persuasion 합계에 더한다(Command (6+) 판정에도 포함). | "this round". |
| heuristic | `switch_graft_card` 우선순위를 0.2로 낮췄다(전 옵션 소크에서 두 box를 무한히 오가는 seed 발견). | |

## 슬라이스 5b-1: Imperium 15종

| 영역 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| 단일 box | `GENERATE_SPECIMEN`(Lab), `GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE`(Clandestine Meeting — 아이콘이 없어 graft 상대로만 play), `GAIN_TWO_SPICE_IF_GRAFTED`(Corrupt Smuggler), `GAIN_TWO_SPICE_IF_EMPEROR_INFLUENCE_TWO`(Keys to Power), `GAIN_FREMEN_INFLUENCE_IF_BENE_GESSERIT_BOND`(Lisan al Gaib), `DRAW_ONE_AND_COMBAT_ICON`(Occupation), `DRAW_TWO_CARDS`(Show of Strength), `GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE`(Stillsuit Manufacturer — hand으로 돌아온 카드는 `hand_public`), `RECRUIT_ONE_AND_MAY_TRASH`(Throne Room Politics — recruit 뒤 `optional_trash` frame). 모두 해결 시점 판정(OQ-028). | 카드면. |
| 선택 box | Long Reach `GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE`: `choose_agent_card_influence`를 두 번, 두 번째는 다른 진영만(`influence_chosen` 컨텍스트). Organ Merchants `MAY_PAY_SPECIMEN_FOR_FOUR_SOLARI`: `pay_agent_card_specimen`/거절. Sardaukar Quartermaster `RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED`: troops·cards 아이콘, graft 아닐 때 둘 다 불발. | |
| 조건부 아이콘 | `ImperiumCardEntry.icon_condition`: Long Reach(다른 BG 카드가 play 중), Show of Strength(배치 troop이 각 상대보다 많음 — `effective_agent_icons(opponents=)`). 조건이 없으면 아이콘 0개(play 불가). Blank Slate는 graft 시 진영 4개 추가. | play 시점 판정. graft 상대가 BG면 Long Reach는 첫 카드로 쓸 수 없고 상대로 play한다(첫 카드의 아이콘만 space를 연다). |
| 획득·trash·Reveal | 획득 box `GAIN_ONE_SPICE`(Lisan)·`RECRUIT_THREE_TROOPS`(Occupation)·`RESEARCH`(Spiritual Fervor); trash trigger `ADVANCE_TLEILAXU`(Replacement Eyes, `card_trash.py` 지역 import); Reveal 필드 `tleilaxu`·`research`(Dissecting Kit·Tleilaxu Master용; Research는 방향 frame이 열리면 남은 아이콘을 다시 대기열에), Occupation의 water·spice·troop, Bene Tleilax Lab의 (1M) spice. | `[Immortality pp. 6-8]`. |
| Graft 보강 | `apply_graft_partner`가 첫 카드의 Bond 조건 box를 상대가 들어온 뒤 다시 판정해 대기시킨다(Lisan al Gaib + BG 상대). | OQ-028의 연장. |

## 슬라이스 5b-2: Imperium 8종

For Humanity와 Interstellar Conspiracy의 "◇?" 아이콘은 카드면 확대로 "원하는 진영의 Influence 1"로 확인했다.

| 카드 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Dissecting Kit | `MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN`: 지불 provider의 `trash_grafted_card_for_specimen`/거절. 상대 카드가 play 영역에 없으면 box 불발. trash 전에 상대의 `graft_pending_effect`를 끄고(OQ-022) 효과 frame을 정리한 뒤 trash·specimen 생성. Reveal (1M) Tleilaxu. | Graft 카드라 단독 play 불가 `[Immortality p. 10]`. |
| For Humanity | Agent `GAIN_CHOSEN_INFLUENCE`(기존). Reveal choice `MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE`: `lose_reveal_influence_for_vp(faction[, alliance_recipient])`/거절. 열리는 조건: BG Alliance 보유 + 잃을 Influence 존재(OQ-028, 선택이 열릴 때 판정). | Influence 손실의 Alliance 이전은 OQ-015·`lose_faction_influence`와 동일. |
| High Priority Travel | `DRAW_ONE_OR_COMBAT_ICON_IF_SPACING_GUILD_INFLUENCE_TWO`: Guild 2 이상이면 `resolve_agent_card_effect`(draw)와 `take_agent_card_combat_icon` 중 선택, 아니면 불발. Combat 아이콘은 `grant_combat_icon`이 frame에 쓰므로 컨텍스트를 다시 읽고 닫는다(Occupation도 같은 수정). Reveal 1 Solari. | |
| Imperium Ceremony | `PEEK_TWO_INTRIGUE_KEEP_ONE` → `rules/intrigue_peek.py`의 `INTRIGUE_PEEK` frame(`keep_peeked_intrigue(instance_id)`). 소유자만 두 장을 본다: `PrivatePlayerView.peeked_intrigue_ids`(관측 v14 세그먼트 `private_peeked_intrigue`), `known_card_seats`, determinize·privacy invariant가 deck 맨 위 두 장을 고정. keep 이벤트는 공개 `intrigue_card_drawn`(수만) + 소유자 전용 `intrigue_card_kept`. | OQ-052(두 장 미만). |
| Interstellar Conspiracy | `GAIN_SPICE_AND_CHOSEN_INFLUENCE_IF_GRAFTED_WITH_EMPEROR_OR_GUILD`: 상대 카드에 Emperor/Guild 진영이 있으면 Influence provider가 4진영 선택을 열고 spice 1을 함께 지급, 아니면 일반 해결로 spice 1만. | Graft 카드. |
| Shadout Mapes | Agent box 없음. Reveal choice `MAY_DEPLOY_OR_RETREAT_ONE_TROOP`: `deploy_reveal_card_troop`(`add_units_to_reveal`)·`retreat_reveal_card_troop`(`retreat_units`, 전투력 차이를 Reveal frame `strength`에 반영)·거절. | 배치는 Combat 아이콘 없이 카드 효과로 한다. |
| Tleilaxu Master | `MAY_ACQUIRE_CARD_UP_TO_SIX_IF_ONE_MARKER`: 획득 provider(`legal_agent_card_acquisitions`)가 marker 1 이상일 때 `acquire_reserve_by_card`/`acquire_imperium_by_card`(비용 6 이하, `acquirable_*` 헬퍼)·거절을 연다. marker 2 이상이면 hand로(`hand_public`). box를 먼저 닫고(`advance_after_effect`) `acquire_*_for_intrigue`로 획득해 Spy·Contract·Research 후속 frame이 turn 위에 쌓인다. Reveal Research ×2. | (1M)/(2M) 모두 해결 시점 판정(OQ-028). |
| Tleilaxu Surgeon | `MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU`: `pay_agent_card_two_specimens`/거절 → `advance_tleilaxu` 2칸. Reveal choice `MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS`: `lose_reveal_troops_for_specimens(zone)`/거절 → `lose_unit` ×2, 전투력 차이 반영, specimen 2. | OQ-053(한 존에서 2개, Commander 제외). |

부수 수정(소크 heuristic seed 11이 적발): 획득한 카드의 Research 획득 box(Spiritual Fervor)가 여는 `RESEARCH_ADVANCE` frame이 (1) Intrigue 획득 slot의 choice frame을 묻어 `RuntimeError`, (2) Price is No Object의 `advance_after_effect`가 frame을 덮어쓰고, (3) Leader Signet 획득도 같은 구조였다. `intrigue.py`의 `_lift_pushed_frames`/`_restack`이 slot 처리 뒤 밀어 올린 frame을 다시 얹고(late reveal이 아래에 끼워 넣는 frame은 그대로), 나머지 두 경로는 box를 먼저 닫은 뒤 획득한다.

## 슬라이스 5c-1: Tleilaxu 6종 + Piter

| 카드 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Industrial Espionage | `DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED`: box를 닫은 뒤 graft면 specimen·research(방향 frame은 turn 위에), 그 다음 draw. | `is_grafted`는 해결 시점 판정. |
| Scientific Breakthrough | `RESEARCH_AND_MAY_TRASH_SELF_FOR_VP_IF_TWO_MARKERS`: marker 2 이상이면 지불 provider가 `resolve_agent_card_effect`(research만)와 `trash_agent_card_self_for_vp`(자기 trash + VP + research)를 연다. 자기 trash는 `agent_card_self_trashed`(OQ-022: 자기 비용이라 보상 유지). | 두 번째 marker 뒤의 Research는 draw(슬라이스 2 판정). |
| Guild Impersonator | `GAIN_SPACING_GUILD_INFLUENCE_IF_GAINED_SPICE_THIS_TURN`: `spice_gained_this_turn(owner)`(turn 시작 대비 순증가 + 지출) ≥ 1이면 Guild Influence, 아니면 불발. | 해결 시점 판정(OQ-028): Hagga Basin의 spice를 먼저 받으면 성립. |
| Slig Farmer | `GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU`: 상대 카드의 *인쇄된* Agent 아이콘 수만큼 Solari(`_partner_icon_count`); 받은 뒤 5 이상이면 `pay_agent_card_five_solari_for_tleilaxu`로 Tleilaxu 1칸. | Blank Slate의 graft 시 추가 아이콘은 인쇄 아이콘이 아니라 세지 않는다(project convention). |
| Stitched Horror | `CHOOSE_TWO_OF_WATER_TROOP_TRASH_TLEILAXU`: `choose_agent_card_reward(reward)`를 두 번, 같은 보상은 두 번 고를 수 없다(`rewards_chosen`). water·troop은 즉시, tleilaxu는 `advance_tleilaxu`, trash는 `optional_trash` frame(첫 선택이면 효과 frame 위에, 둘째면 turn을 닫은 뒤). | "Choose two"의 순차 선택은 Long Reach와 같은 기계. |
| Beguiling Pheromones | `MAY_TRASH_GRAFTED_CARD_FOR_VISITED_FACTION_INFLUENCE`: 방문 space에 진영이 있고 graft일 때 `trash_grafted_card_for_influence(card_id)`로 두 grafted 카드 중 하나(play 영역에 있는 것)를 trash → 그 진영 Influence 1. 상대를 trash하면 상대의 미발동 box 소멸(`graft_pending_effect=False`), 자기를 trash하면 `agent_card_self_trashed`. | `[FAQ p. 1]`의 Beguiling Pheromones 판정(OQ-022). Faction 방문 여부는 `space_id`의 인쇄 진영. |
| Piter, Genius Advisor(프로모) | `MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH`: `lose_agent_card_troop(zone)`(garrison/Conflict, OQ-038의 존 선택; Conflict면 전투력·배치 카운터 조정) → box를 닫고 research(방향 frame) → draw 2. | `promo_cards`+`immortality`일 때만 덱에. |

## 슬라이스 5c-2: Ghola·Chairdog·Usurp

| 카드 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Ghola | 정의에는 box가 없고(`agent_effect=None`), `rules/effects.py`의 `borrowed_agent_card`/`active_agent_card(context)`가 활성 카드가 Ghola면 상대 카드의 `agent_effect`를 끼운 정의를 돌려준다. `agent_effects.py`의 활성 카드 조회 17곳, `acquisition.py`(Tleilaxu Master·Price is No Object provider), `leader_abilities.py`(Signet 판정)가 이 접근자를 쓴다. `apply_graft_partner`는 양쪽을 빌린 box로 판정해 `pending_*`/`graft_pending_*`을 채운다. | 상대 box가 비어 있으면(Face Dancer Initiate) Ghola도 비어 있다. 상대가 self-trash box면 Ghola 자신이 trash된다(`card_id`가 Ghola). |
| Chairdog | `RETURN_OTHER_GRAFTED_TO_HAND_AT_REVEAL_START`: 해결 시 상대 카드 id를 좌석의 `chairdog_return_card_ids`에 적고, `begin_reveal_turn`이 `_return_chairdog_cards`로 play 영역에서 hand(`hand_public`)로 되돌린 뒤 그 hand를 Reveal한다. Round Start에 비운다. 관측 v15 좌석 scalar(대기 수). | 상대가 이미 play 영역을 떠났으면 무시. |
| Usurp | 아이콘·box 없음. 배치: graft 변형만, Row 카드 아이콘의 합집합으로 space 결정(`_placements_for_card`; codec은 graft 변형을 모든 space에 둔다). 상대 선택: Row 카드 + hand 카드 중 그 space에 닿는 카드(`legal_graft_partner_actions`). Row 상대는 `take_imperium_row_card`로 빠지고 Row가 즉시 채워지며 좌석의 `usurped_row_card_id`에 남는다. turn이 닫히면(`usurp_trash_is_queued`, 소유자의 효과 frame이 사라진 뒤) `resolve_usurp_trash`가 어느 존에 있든 `imperium_removed`로 보낸다(OQ-054). 관측 v15 좌석 scalar(빌린 카드 여부). | hand 카드를 먼저 놓고 Usurp를 상대로 고르는 보통의 graft도 그대로 된다(Usurp box 없음). |

heuristic: 활성 box가 decline만 제공할 때 `switch_graft_card`를 decline 아래로 내린다(Ghola가 Corrinth City의 box를 복사한 seed 11에서 두 box가 decline만 제공해 무한 switch).

## 슬라이스 6: UI·소크·census

| 영역 | 구현 | 메모 |
| --- | --- | --- |
| UI | 카탈로그에 Tleilaxu deck + Reclaimed Forces(specimen 비용·Graft 표시·이미지)와 `bene_tleilax` 절(research hex의 열·행·보너스, genetic marker 열, Tleilaxu track). market에 Tleilaxu Row(deck 수, specimen 배지, Reclaimed Forces)와 Bene Tleilax board 패널(research grid 위 좌석 token, Tleilaxu track 위 token과 bank spice); 좌석 카드에 specimen·research/Tleilaxu 위치·Family Atomics·Chairdog 반환 대기·Usurp 빌린 카드. headless Chromium으로 렌더 확인. | Bene Tleilax board 스캔은 없어 합성 grid로 그린다. |
| 소크 | `dune-imperium-sweep --rotate-leaders --soundness-interval 25`: immortality+promo random 300·heuristic 150, 전 옵션(base·CHOAM × promo+Bloodlines+Tech+Immortality) random 200·heuristic 120, immortality draft 60 — 830판 실패 0. 첫 실행이 적발한 결함 3계열은 아래. | |
| census | Immortality Imperium 25·Intrigue 11·Tleilaxu 19 전부 play/acquire 0회 없음(Clandestine Meeting은 graft 상대로만 play되므로 census가 `card_grafted`를 세도록 보강). `immortality` 카탈로그 전용 행동 가운데 0회는 `decline_agent_card_recall`(Twisted Mentat의 recall 거절)과 `decline_reveal_influence_loss`(For Humanity, BG Alliance 필요)뿐이며 둘 다 단위 테스트가 덮는다. research 보너스·Family Atomics·Tleilaxu track 끝(OQ-048)·specimen 부족(OQ-049)·반환 모두 발화. | |

첫 소크가 적발한 결함(`37fa1b7`): (1) 두 번째 marker 뒤 Research ×2의 draw가 빈 deck에서 discard 셔플 chance frame을 두 번 밀어 같은 카드가 두 존에 — `draw_or_request_personal_cards`가 같은 좌석의 대기 중인 셔플에 합류; (2) Usurp를 Infiltrator 약속으로 점유된 space에 놓았는데 Infiltrator가 그 space에 닿지 않아 상대 선택이 비는 교착 — 배치 시점에 따라올 수 있는 상대가 있는 space만 제공; (3) Ghola가 CHOAM Demands를 복사한 두 box에서 heuristic이 `switch_graft_card`(0.2)를 `complete_contract_by_card`(0.0)보다 골라 무한 반복 — 해결 가능한 box 행동이 있으면 switch를 최하위로.

## 미완 경계

- 카드 play data·UI·소크·census는 끝났다. 남은 것은 콘텐츠 밖의 후속: Bene Tleilax board 스캔이 들어오면 합성 grid를 오버레이로 바꾸는 것, heuristic의 Immortality 가치(Tleilaxu 카드 구매·research 방향은 고정 prior뿐)와 rollout 가중치 조정, 학습(M10) 재개 시 관측 v15 체크포인트 새로 시작.
