# Immortality implementation audit

기준일: 2026-09-08 — 슬라이스 1(출처·명세·옵션 골격·카탈로그) 완료.

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

## 미완 경계

- 슬라이스 2 이후: Bene Tleilax board의 상태·행동(research 전진 선택, Tleilaxu track, specimen 생성·반환·지출), 개정 Research Station, Experimentation 시작 덱, Family Atomics, Tleilaxu Row 획득과 Reclaimed Forces, Graft, 카드 play data, UI 표시.
- 공식 문서가 침묵하는 판정(슬라이스 2에서 open-questions에 등록): Tleilaxu track 끝에서의 추가 전진, supply가 빈 상태의 specimen 생성, specimen 자유 반환의 결정 창, Family Atomics로 제거한 카드의 행선지, "lose a troop"의 출처 존 선택.
