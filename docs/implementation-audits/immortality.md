# Immortality implementation audit

기준일: 2026-09-28(Go to 11 변형 추가), 2026-09-08 — 슬라이스 1(출처·명세·옵션 골격·카탈로그), 슬라이스 2(Bene Tleilax board·specimen·Research Station·Experimentation·Family Atomics), 슬라이스 3(Tleilaxu Row·Reclaimed Forces·첫 카드 3장), 슬라이스 4(Graft와 Graft 카드 8장), 슬라이스 5a(Intrigue 11장), 슬라이스 5b-1(Imperium 15종), 슬라이스 5b-2(Imperium 8종 — Imperium 25종 전부), 슬라이스 5c-1(Tleilaxu 6종 + 프로모 Piter), 슬라이스 5c-2(Ghola·Chairdog·Usurp — 카드 play data 전부), 슬라이스 6(UI·대규모 소크·census) 완료 — **M13 마감**. 2026-09-09에 baseline agent의 Immortality 가치를 더했다(아래 절).

규범 근거는 [`rules/immortality.md`](../rules/immortality.md)이며, 콘텐츠 정의는 `content/immortality/board.py`(research·Tleilaxu track), `content/immortality/tleilaxu.py`(Tleilaxu deck·Reclaimed Forces), `content/uprising/imperium.py`·`intrigue.py`의 `immortality_only` 항목이 소유한다. 모든 동작은 `RulesetConfig(immortality=True)`에서만 켜진다.

## 검증 방법

- 룰북: 공식 URL의 PDF를 scratchpad에서 받아(sha256 고정, 저장소에 넣지 않음) 텍스트를 추출하고, Bene Tleilax board는 p. 3의 board 그림을 500 dpi로 잘라 판독했다. 아이콘은 `assets/icons/`의 Uprising 아이콘(Solari = 회색 원, spice = 주황 육각, VP = 금색 구, Intrigue = 금색 카드, trash = 검은 카드의 X, Influence 선택 = 금색 ?)과 대조했다.
- 카드: 에셋 저장소 `cards/en/immortality/{imperium,intrigue,tleilaxu,starting,promo}/` 57장을 전부 직접 판독했고, Agent 아이콘 열은 `assets/icons/agent_icon_*.png`와 나란히 대조했다(Fremen = 파란 원 문양, City = 파란 원, Emperor = 투구, Guild = 붉은 ∞, BG = 보라 가면, Landsraad = 초록 오각, Spice Trade = 노란 삼각). 흰 X 검 두 자루는 Combat 아이콘(trash 아이콘은 검은 카드 위의 흰 ✕)이다.
- 수량: 처음엔 Dune Cards Hub의 `/api/cards`(`physicalCopies`: Imperium 27장·Intrigue 11장)를 썼으나 룰북 p. 3의 30·15장과 어긋났다. 2026-09-08 사용자가 알려준 BGG 카드 인벤토리 시트(Uprising 69장·Bloodlines 32장이 우리 전사와 정확히 일치해 신뢰; 에셋 저장소 `reference/bgg-card-inventory/`에 CSV 보관)로 확정: Imperium 30장(High Priority Travel·Planned Coupling·Spiritual Fervor도 2장씩), Intrigue 15장(Gruesome Sacrifice·Harvest Cells·Illicit Dealings·Vicious Talents 2장씩), Tleilaxu 18장(각 1장). 시트의 `Compatibility` 열은 Immortality 카드 중 Bene Tleilax 요소를 쓰는 카드(`Immortality`)와 어느 조합에서든 쓰는 카드(`All`)를 구분한다.

## 카드 전사 (슬라이스 1, 카드면)

아래 표는 2026-09-08에 카드면을 직접 판독한 전사이며, play data 구현은 이후 슬라이스에서 이 표를 기준으로 진행한다. `◆n` = Persuasion n(파란 마름모), `⚔` = 검, `(1M)`/`(2M)` = genetic marker 1개/2개 조건, `▶` = arrow(비용 → 보상), `◇?` = Influence 1 선택.

### Tleilaxu deck 18장 + Reclaimed Forces + 프로모

| 카드 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Beguiling Pheromones | `TRASH_GRAFTED_CARD_FOR_VISITED_FACTION_INFLUENCE`: 방문 space에 진영이 있고 graft일 때 `trash_grafted_card_for_influence(card_id)`로 두 grafted 카드 중 하나(play 영역에 있는 것)를 trash하고 그 진영 Influence 1. 인쇄문 "trash one of the grafted cards and gain an additional Influence"에는 "may"·화살표·검은 X가 없어 의무다 `[FAQ p. 3]` — 거절은 없고 어느 카드를 trash할지만 고른다(2026-09-26 정정: 이전에는 `decline_agent_card_payment`를 제시했다). 상대를 trash하면 상대의 미발동 box 소멸(`graft_pending_effect=False`), 자기를 trash하면 `agent_card_self_trashed`. | `[FAQ p. 1]`의 Beguiling Pheromones 판정(OQ-022). Faction 방문 여부는 `space_id`의 인쇄 진영. |
| Chairdog | `RETURN_OTHER_GRAFTED_TO_HAND_AT_REVEAL_START`: 해결 시 상대 카드 id를 좌석의 `chairdog_return_card_ids`에 적고, `begin_reveal_turn`이 `_return_chairdog_cards`로 play 영역에서 hand(`hand_public`)로 되돌린 뒤 그 hand를 Reveal한다. Round Start에 비운다. 관측 v15 좌석 scalar(대기 수). | 상대가 이미 play 영역을 떠났으면 무시. |
| Contaminator (Fremen) | 1 | Fremen | Tleilaxu | ◆1 |
| Corrino Genes (Emperor) | 1, 획득 시 Solari 2 | Emperor | If grafted: Tleilaxu | ◆1 |
| Face Dancer (Emperor·Guild·Fremen) | 2 | Emperor, Guild, Fremen | GRAFT: draw 1 | ◆1 |
| Face Dancer Initiate (Emperor·Guild·Fremen) | 1 | Emperor, Guild, Fremen | GRAFT: (효과 없음) | ◆1 |
| From the Tanks | 2 | Landsraad | troop 2 | ◆1 |
| Ghola | 정의에는 box가 없고(`agent_effect=None`), `rules/effects.py`의 `borrowed_agent_card`/`active_agent_card(context)`가 활성 카드가 Ghola면 상대 카드의 `agent_effect`와 Spy 배치 제한(`agent_spy_factions`, Reliable Informant의 "[Spy] on ...")을 끼운 정의를 돌려준다 — "Ghola copies the entire Agent box" `[Immortality p. 14]`(2026-09-26: 이전에는 효과만 복사해 제한 없이 놓았다). `agent_effects.py`의 활성 카드 조회 17곳, `acquisition.py`(Tleilaxu Master·Price is No Object provider), `leader_abilities.py`(Signet 판정)가 이 접근자를 쓴다. `apply_graft_partner`는 양쪽을 빌린 box로 판정해 `pending_*`/`graft_pending_*`을 채운다. | 상대 box가 비어 있으면(Face Dancer Initiate) Ghola도 비어 있다. 상대가 self-trash box면 Ghola 자신이 trash된다(`card_id`가 Ghola). |
| Guild Impersonator (Guild) | 2 | Guild | GRAFT: 이번 turn spice를 얻으면 Guild Influence 1 | ◆1 |
| Industrial Espionage | `DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED`: 2026-10-06부터 box가 draw 아이콘(`cards`)과 "If grafted:" 줄의 아이콘(`research`: specimen과 Research)을 대기시키고 소유자가 순서를 고른다(OQ-027, `agent_effects._PLACEMENT_ICONS`). Research를 먼저 하면 방향·보너스 frame(c3r3·c7r5의 선택 trash 포함)이 draw 앞에 오고, draw를 먼저 하면 그 trash가 방금 뽑은 카드를 고를 수 있다. graft가 아니면 `research` 아이콘은 기다리다 turn 종료에 소멸한다(OQ-057 (1)). 전에는 한 번의 해결이 graft면 specimen·research, 그 다음 draw로 순서를 고정했다. | `is_grafted`는 해결 시점 판정. `test_industrial_espionage_research_bonus_resolves_before_its_draw`, `test_industrial_espionage_draw_first_lets_the_bonus_trash_the_drawn_card`. |
| Reclaimed Forces (Row 고정) | 3 | — | — | 획득 box: troop 2 —OR— Tleilaxu |
| Scientific Breakthrough | `RESEARCH_AND_MAY_TRASH_SELF_FOR_VP_IF_TWO_MARKERS`: marker 2 이상이면 지불 provider가 `resolve_agent_card_effect`(research 먼저)와 `trash_agent_card_self_for_vp`(자기 trash + VP + research)를 연다. research를 먼저 해결하면 box는 열린 채 남고(`research_resolved_card_ids`), research가 끝난 뒤 marker가 2 이상이면 `decline_agent_card_payment`와 research 없는 `trash_agent_card_self_for_vp`를 연다 — 카드 자신의 Research가 두 번째 marker에 닿아도 trash 줄을 쓸 수 있다(OQ-028, 2026-09-26). 2 미만이면 줄은 turn 종료까지 보류된 뒤 소멸한다(OQ-057 (1)). 자기 trash는 `agent_card_self_trashed`(OQ-022: 자기 비용이라 보상 유지). | 두 번째 marker 뒤의 Research는 draw(슬라이스 2 판정). Ghola가 복사한 box는 따로 research한다(카드별 기록). |
| Slig Farmer | `GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU`: 상대 카드가 그 순간 가진 Agent 아이콘 수만큼 Solari(`_partner_icon_count` → `effective_agent_icons`, graft 기준); 받은 뒤 5 이상이면 `pay_agent_card_five_solari_for_tleilaxu`로 Tleilaxu 1칸. Tleilaxu token이 track 마지막 칸이면 그 지불은 제시하지 않는다(`agent_effects.agent_card_payment_block`, OQ-048·OQ-071, 2026-10-06; `test_slig_farmer_offers_no_track_step_at_the_tleilaxu_track_end`). | OQ-055(사용자 판정): Blank Slate의 graft 아이콘 등 추가 아이콘도 센다. |
| Stitched Horror | `CHOOSE_TWO_OF_WATER_TROOP_TRASH_TLEILAXU`: `choose_agent_card_reward(reward)`를 두 번, 같은 보상은 두 번 고를 수 없다(`rewards_chosen`). water·troop은 즉시, tleilaxu는 `advance_tleilaxu`, trash는 `optional_trash` frame(효과 frame 위에; 2026-09-30 OQ-095 전에는 둘째 선택이면 turn을 닫은 뒤). | "Choose two"의 순차 선택은 Long Reach와 같은 기계. |
| Subject X-137 | 2, 획득 시 Tleilaxu | Landsraad, Spice Trade | (1M): Tleilaxu | ◆1 |
| Tleilaxu Infiltrator | 2 | City | GRAFT: 이번 turn 적 Agent가 자신의 Agent를 막지 않는다. draw 1 —AND— (2M): Intrigue 1 | ◆1 |
| Twisted Mentat | 4 | Landsraad, City | GRAFT: 이번 turn 보낸 Agent를 recall할 수 있다 | ◆1 ⚔1 specimen 1 |
| Unnatural Reflexes | 3 | Spice Trade | GRAFT: (1M): draw 2 | ◆1 ⚔1 |
| Usurp | 아이콘·box 없음. 배치: graft 변형만, 후보 상대(Row 카드 + hand 카드) 아이콘의 합집합으로 space 결정(`_placements_for_card`; 따라올 상대가 없는 space는 제외; codec은 graft 변형을 모든 space에 둔다). 상대 선택: Row 카드와 hand 카드 중 그 space에 닿는 카드(`legal_graft_partner_actions`) — "may"라 hand 상대도 된다. Row 상대는 `take_imperium_row_card`로 빠지고 Row가 즉시 채워지며 좌석의 `usurped_row_card_id`에 남는다. 소유자가 `finish_agent_turn`을 누르면 `graft.trash_usurped_card`가 `trash_personal_card`로 **자동 trash**해 trash 이벤트·트리거가 발동한다(OQ-054, 사용자 판정). 2026-10-01부터(OQ-095 (5)) 그 trash는 아직 열린 turn 안에서 일어나 결과가 그 turn의 것이고, 의무 Contract나 배치할 수 있는 새 recruit가 생기면 turn이 다시 열린다(`combat_deployment.settle_finishing_agent_turn`). 이력: 그 전에는 turn이 닫힌 뒤 dispatcher(`usurp_trash_is_queued`·`resolve_usurp_trash`)가 trash했고, 그래서 `trash_personal_card`에 항상 `turn_closed=True`를 넘겼다 — 빌린 카드가 Sardaukar Standard(Bloodlines)면 이 값이 없으면 queue된 Skill 선택이 방금 다시 열린 같은 player의 새 turn frame을 잘못 credit한다(2026-09-26 review round 5, 상세는 `docs/implementation-audits/bloodlines.md`의 Eliminate Allies 행 (f)). 관측 v15 좌석 scalar(빌린 카드 여부). | hand 카드를 먼저 놓고 Usurp를 상대로 고르는 보통의 graft도 그대로 된다(Usurp box 없음). |
| Piter, Genius Advisor (프로모) | 3 | Landsraad, Spice Trade | Lose a troop ▶ draw 2 + Research | ◆1 ⚔1 |

### Imperium 25종

| 카드 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Bene Tleilax Lab | 2 | — | City, Spice Trade | specimen 1 | ◆1; (1M): spice 1 |
| Bene Tleilax Researcher | 4 | — | Landsraad | GRAFT: Research | ◆1; (1M): +◆1; (2M): +◆1 |
| Blank Slate | 1 | — | Landsraad, City, Spice Trade (+ 흐린 Emperor·Guild·BG·Fremen) | If grafted: Emperor, Guild, BG, Fremen 아이콘을 가진다 | ◆1 |
| Clandestine Meeting | 4 | BG | (없음) | BG Influence 1 + Intrigue 1 | ◆2 |
| Corrupt Smuggler | 3 | Guild·Fremen | Guild, Spice Trade | If grafted: spice 2 | ◆1 ⚔1 |
| Dissecting Kit ×2 | 2 | — | Landsraad, City | GRAFT: *다른* grafted 카드 trash ▶ specimen 1 | ◆1; (1M): Tleilaxu |
| For Humanity | Agent `GAIN_CHOSEN_INFLUENCE`(기존). Reveal choice `MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE`: `lose_reveal_influence_for_vp(faction[, alliance_recipient])`/거절 — 고른 한 진영에서 Influence 2를 잃는다(카드 면의 "?" 다이아몬드에 빨간 chevron 두 개 `[For Humanity card]`; 2026-09-26 이전에는 1로 오독). 열리는 조건: BG Alliance 보유 + Influence 2 이상인 진영 존재(화살표 비용은 전부 내거나 안 낸다 `[Main p. 20]`; OQ-028, 선택이 열릴 때 판정). | Influence 손실의 Alliance 이전은 OQ-015·`lose_faction_influence`와 동일하게 한 칸씩 처리하며, 수령자 선택은 token이 움직이는 칸(첫째 또는 둘째)에서 제시한다 `[FAQ p. 1]`. |
| High Priority Travel | `DRAW_ONE_OR_COMBAT_ICON_IF_SPACING_GUILD_INFLUENCE_TWO`: Guild 2 이상이면 `resolve_agent_card_effect`(draw)와 `take_agent_card_combat_icon` 중 선택, 아니면 불발. Combat 아이콘은 `grant_combat_icon`이 frame에 쓰므로 컨텍스트를 다시 읽고 닫는다(Occupation도 같은 수정). Reveal 1 Solari. | |
| Imperium Ceremony | `PEEK_TWO_INTRIGUE_KEEP_ONE` → `rules/intrigue_peek.py`의 `INTRIGUE_PEEK` frame(`keep_peeked_intrigue(instance_id)`). 소유자만 두 장을 본다: `PrivatePlayerView.peeked_intrigue_ids`(관측 v14 세그먼트 `private_peeked_intrigue`), `known_card_seats`, determinize·privacy invariant가 deck 맨 위 두 장을 고정. keep 이벤트는 공개 `intrigue_card_drawn`(수만) + 소유자 전용 `intrigue_card_kept`. | OQ-052(사용자 판정): 두 장 미만이면 맨 윗장을 두고 그 밑에 discard를 섞은 뒤 두 장을 본다(셔플 frame `purpose=peek`). 섞을 discard도 없이 한 장만 남았으면 그 한 장으로 같은 frame을 연다(keep만; 2026-10-02 사용자 판정 L2-Q3 "①②는 확인 창, ③은 회색 줄만"의 ②, 전에는 창 없이 draw 1장). |
| Interstellar Conspiracy | `GAIN_SPICE_AND_CHOSEN_INFLUENCE_IF_GRAFTED_WITH_EMPEROR_OR_GUILD`: 상대 카드에 Emperor/Guild 진영이 있으면 Influence provider가 4진영 선택을 열고 spice 1을 함께 지급, 아니면 일반 해결로 spice 1만. | Graft 카드. |
| Keys to Power | 5 | Guild·BG | Guild, BG, Landsraad | Emperor Influence 2: spice 2 | ◆2 |
| Lisan al Gaib | 4, 획득 시 spice 1 | BG·Fremen | Fremen, City, Spice Trade | 다른 BG 카드가 play 중이면 Fremen Influence 1 | ◆1; Fremen Bond: ⚔2 |
| Long Reach | 6 | BG | (흐린 Landsraad·City·Spice Trade) | 다른 BG 카드가 play 중이면 Landsraad·City·Spice Trade 아이콘을 가진다. 둘 선택: Emperor·Guild·BG·Fremen Influence 1 | ◆1 Intrigue 1 |
| Occupation | 8, 획득 시 troop 3 | Guild | Emperor, Guild, BG, Fremen, City, Spice Trade | draw 1 + Combat 아이콘 | water 1, spice 1, troop 1 |
| Organ Merchants | 3 | — | City, Spice Trade | specimen 1 ▶ Solari 4 | ◆1 Solari 1 |
| Planned Coupling | 3 | BG | BG | GRAFT: draw 1 | ◆1 |
| Replacement Eyes | 5 | — | City | GRAFT: trash될 때 Tleilaxu. trash ▶ draw 1 | ◆1 ⚔1 |
| Sardaukar Quartermaster | 2 | Emperor | Landsraad, City | If grafted: troop 1 + draw 1 | ◆1 ⚔2 |
| Shadout Mapes | Agent box 없음. Reveal choice `MAY_DEPLOY_OR_RETREAT_ONE_TROOP`: `deploy_reveal_card_troop`(`add_units_to_reveal`)·`retreat_reveal_card_troop`(`retreat_units`, 전투력 차이를 Reveal frame `strength`에 반영)·거절. 같은 행동을 Uprising의 Unswerving Loyalty("Fremen Bond: … deploy or retreat one of your troops")가 Fremen Bond 뒤에서 쓰므로(2026-09-26) 세 행동 template은 모든 catalog에 있다. Bloodlines와 함께면 Commander도 "troop"이므로 `[Bloodlines p. 4]` `commanders` 1 변형으로 garrison·Conflict의 Commander를 배치·후퇴할 수 있고(2026-09-26 감사 수정), 그 두 template은 Immortality 여부와 관계없이 Bloodlines catalog에 있다. | 배치는 Combat 아이콘 없이 카드 효과로 한다. |
| Show of Strength | 3 | Emperor·Fremen | (흐린 Landsraad·Spice Trade) | 배치한 troop이 각 상대보다 많으면 Landsraad·Spice Trade 아이콘을 가진다. draw 2 | ◆1 ⚔2 |
| Spiritual Fervor | 3, 획득 시 Research | — | Spice Trade | (없음) | ◆1 specimen 1 |
| Stillsuit Manufacturer | 5 | Fremen | Fremen, City | water 1 —AND— Fremen Alliance: 이 카드를 play에서 hand로 되돌린다 | ◆1 —AND— Fremen Bond: spice 2 |
| Throne Room Politics | 4 | Emperor·BG | Emperor | troop 1 + trash | ◆1 BG Influence 1 |
| Tleilaxu Master ×2 | 5 | — | Landsraad, Spice Trade | (1M): 비용 6 이하 카드 1장을 acquire할 수 있다. (2M): 그 카드를 hand에 둔다 | ◆1 Research Research |
| Tleilaxu Surgeon | `MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU`: `pay_agent_card_two_specimens`/거절 → `advance_tleilaxu` 2칸(Tleilaxu track 마지막 칸이면 지불은 제시하지 않는다 — `agent_card_payment_block`, OQ-071, 2026-10-06; `test_tleilaxu_surgeon_offers_no_payment_at_the_tleilaxu_track_end`). Reveal choice `MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS`: `lose_reveal_troops_for_specimens(zones)`/거절 → troop마다 존을 골라(garrison·Conflict 둘 다, 각각 하나씩) `lose_unit` ×2, 전투력 차이 반영, specimen 2. | OQ-053(사용자 판정: 존 혼합 허용, Commander 제외). |

Sardaukar Quartermaster는 카드면에 "Sarduakar"로 오식돼 있다(하브도 같은 슬러그); 프로젝트 ID는 `sardaukar_quartermaster`다.

### Intrigue 11종

| 카드 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Breakthrough | Plot | Research |
| Counterattack | `apply_intrigue_play`가 Combat 중 play된 Combat option의 좌석을 `combat_intrigue_players`에 기록하고 `finish_combat`이 비운다(관측 세그먼트). Plot의 "Deploy up to two troops from your garrison to the Conflict."는 배치할 수 있는 garrison unit이 있어야 내고(Harkonnen Advisor의 troop과 Emperor of the Known Universe의 배치 금지 turn은 세지 않는다 — `effect_interpreter.deployable_garrison_units`), 낸 뒤에는 0명도 고를 수 있다. 이력: 2026-10-06 앱 카드 대조가 빈 garrison에서도 내게 했고(OQ-057 (6) 보강, codec v137) 같은 날 사용자 판정 "아무 효과 없이 책략을 쓸 수 없는거지"로 되돌렸다(OQ-038 재판정, codec v138; `test_counterattack_plot_needs_a_deployable_garrison_unit`, `test_counterattack_plot_deploys_up_to_two_including_none`). | "in this Conflict" = 이번 Combat. |
| Disguised Bureaucrat | Plot | (1M): spice 1; (2M): ◇? |
| Economic Positioning | Combat / Endgame | troop 2개 retreat ▶ Solari 3 —OR— Solari 10 이상이면 VP 1 |
| Gruesome Sacrifice | Combat | Conflict의 자기 troop 2개 잃기 ▶ Tleilaxu + specimen 2 |
| Harvest Cells | "When you lose at least three troops at the end of a Conflict:" `[Harvest Cells card]`. 2026-10-06부터(사용자 판정 "앱처럼 전투 후에만", OQ-016) 보상 해결 뒤·정리 전의 `conflict_end_trigger` 창(`combat.offer_conflict_end_triggers`)에서만 낸다: 정리 전 Conflict의 troop+Commander 수를 "잃은 troop"으로 삼아(FAQ p. 1 Chani: supply로 돌아간 troop은 lost) 3 이상인 좌석이 First Player부터. 다른 Intrigue 창에서는 `IntriguePlayBlock.CONFLICT_END`로 막혀 Combat Intrigue에서 face-up으로 미리 낼 수 없다(화면은 흐리게). 낸 카드는 face-up에 놓였다가 `finish_combat`의 troop 반환 뒤 `resolve_faceup_trigger_option`으로 발동한다(Makers 전에 INTRIGUE_CHOICE frame). 만료(`intrigue_expired`) 분기는 닿을 수 없어 `RuntimeError`다. "You may also acquire a Tleilaxu card (paying its normal cost)."의 slot은 Reclaimed Forces도 제시한다(`acquire_intrigue_reclaimed_forces(choice)`, 사용자 판정 2026-10-06, OQ-066). 이력: 2026-09-26까지는 창에서 낸 카드가 반환 전에 즉시 발동해 supply가 비면 specimen 0이었고, 2026-10-06까지는 Combat Intrigue에서 face-up으로 내 3 미만을 잃으면 정리 때 만료됐다. 2026-10-06(책략 효과 판정, OQ-016 보강)부터 창은 그 사본이 무언가를 바꿀 수 있을 때만 카드를 넣는다(`combat._harvest_cells_has_effect`): supply와 Conflict의 troop에서 이미 face up으로 놓은 사본들의 specimen을 빼고 1 이상 남거나(Commander는 Commander supply로 가므로 세지 않는다), 앞 사본들이 만들 specimen까지 쳐서(상한 추정) Tleilaxu Row 카드나 Reclaimed Forces 효과를 살 수 있을 때. 한 사본을 낸 뒤에 다른 사본을 다시 찾으므로 첫 사본이 troop을 다 쓰면 창이 닫힌다(`apply_conflict_end_trigger`). | `[FAQ p. 1]` `[FAQ p. 2]` `[card face]`. `test_harvest_cells_is_never_played_in_combat_intrigue`, `test_harvest_cells_is_never_offered_below_three_troops_in_the_conflict`, `test_harvest_cells_may_take_reclaimed_forces_troops`, `test_harvest_cells_window_skips_a_copy_that_would_change_nothing`. |
| Illicit Dealings | Plot | Tleilaxu |
| Shadowy Bargain | Plot / Endgame | specimen 1 —OR— Tleilaxu |
| Study Melange | Plot / Endgame | spice 1 —OR— spice 3 이상이면 (2M): VP 1 |
| Tleilaxu Puppet | `PlayerState.reveal_persuasion_round_bonus`: Round Start에 0, `begin_reveal_turn`의 Persuasion 합계에 더한다(Command (6+) 판정에도 포함). 소유자의 Reveal이 이미 열린 뒤 play하면(Plot은 Reveal turn에도 쓸 수 있다 `[Main pp. 7, 8]`) 그 Reveal frame에 바로 더하고 round 보너스는 그대로 둔다(2026-09-26 감사 수정; 전에는 카드만 쓰이고 Persuasion이 사라졌다). | "this round". |
| Vicious Talents | Combat | ⚔2; (1M): +⚔2; (2M): +⚔2 |

Illicit Dealings의 에셋 파일명은 하브 슬러그 오타 "Illicit Deadlings"를 따른다(`content_id`로 연결).

### Experimentation (starting card ×2)

Spice Trade 아이콘. Agent: Research. Reveal: ◆1 specimen 1. 카드 이름 앞의 작은 삼각형은 시작 카드 표시다.

## 구현된 동작

| 영역 | 구현 | 메모 |
| --- | --- | --- |
| 옵션 | `RulesetConfig(immortality=True)`, identifier `+immortality`; 서버 `immortality` 필드·UI 체크박스·상태 배지, 저장 문서 플래그, sweep/tournament `--immortality`, coverage census, 체크포인트 룰셋 파싱. | `[Main p. 18]`. Bloodlines와 독립. |
| 카탈로그 | Imperium 25종(`immortality_only`), Intrigue 11종, Tleilaxu deck 18종 + Reclaimed Forces + 프로모 Piter(`content/immortality/tleilaxu.py`, instance `tleilaxu:<id>:<copy>`). play data가 없는 카드는 옵션을 켜도 덱에 들어가지 않는다. | 관측 identity 우주에 Imperium 25·Intrigue 11이 들어와 관측 v11. Tleilaxu 카드는 아직 관측 우주 밖(슬라이스 2). |
| board 전사 | research track 22칸(시작 포함)과 인접 규칙 `research_next_space_ids`, genetic marker 열 4·8, Tleilaxu track 8칸의 보너스, setup spice 2·네 번째 칸, Row 2장. | `[Immortality pp. 3-7, 16]`. |

## 슬라이스 2: Bene Tleilax board

| 영역 | 구현 | 메모 |
| --- | --- | --- |
| 상태 | `PlayerState.research_space`(칸 ID, 옵션 off ""), `tleilaxu_space`(0~7), `specimens`(troop 12개 불변식에 포함), `family_atomics`; `GameState.tleilaxu_deck`(비공개 순서)·`tleilaxu_row`·`tleilaxu_track_spice`. 옵션이 꺼지면 전부 비어 있어야 한다. | `[Immortality pp. 4-8, 12]`. |
| Setup | `create_unshuffled_players(immortality=)`가 Dune, the Desert Planet 2장을 Experimentation 2장으로 바꾸고, `_immortality_setup`이 Tleilaxu deck을 seeded chance `setup:tleilaxu_deck`으로 섞어(play data가 있는 카드가 없으면 생략) Row 2장을 deal하며, `_with_immortality`가 token·spice 2·Family Atomics를 놓는다. 고정 Leader setup과 draft setup 모두. Bloodlines 결정 뒤에 해결해 기존 chance 순서를 보존. | `[Immortality pp. 4-5]`. |
| Research 전진 | `advance_research`: 두 번째 marker 열이면 card draw 대체, 다음 칸이 하나면 즉시 이동, 둘이면 `research_advance` frame(`choose_research_space`). `move_research_token`이 칸 보너스를 즉시 해결하고 marker 도달 이벤트를 낸다. research 보너스 칸은 재귀로 다시 전진한다. | `[Immortality pp. 6, 16]`. 보드 아이콘·Agent box 모두 frame 정리 뒤에 전진을 열어 방향 선택 frame이 그 위에 놓인다. |
| 보너스 | specimen·Tleilaxu·Solari·spice는 자동; trash+specimen은 specimen 뒤 `optional_trash` frame(검은 trash 아이콘은 선택 `[Main p. 20]`); Influence 선택·trash→draw+Intrigue·Solari 7→Tleilaxu 2는 `research_bonus` frame. arrow 비용을 낼 수 없어도(hand에 Intrigue 카드 없음, Solari 7 미만) frame은 열리고 `decline_research_bonus`만 제시한다 — 지불 판정은 공개 함수 `research_bonus_block`(NO_INTRIGUE, SOLARI)이고, 화면은 같은 판정으로 지불 줄을 회색으로 보인다(`display/unavailable.py` `_research_bonus`, "choice" 표면). 2026-09-30 사용자 판정 "결정 창 없이 자동으로 넘어가는 곳도 모두 결정 창을 연다", 2026-10-02 구현; 그 전에는 frame 없이 `research_bonus_unavailable` 이벤트만 남겼다. 2026-10-06: c8r6의 "Solari 7 → Tleilaxu 2"는 Tleilaxu token이 마지막 칸이면 `ResearchBonusBlock.TLEILAXU_TRACK_END`로 막혀 거절만 남고(OQ-071; `test_seven_solari_bonus_is_not_offered_at_the_tleilaxu_track_end`), c6r6의 Influence 선택은 6인 진영을 제시하지 않으며 네 진영이 모두 6이면 `decline_research_bonus`만 제시한다(`research_influence_factions`, OQ-060; `test_influence_bonus_with_every_faction_at_the_top_offers_only_the_decline`). | `[Immortality p. 3 board artwork]`. c8r6은 저해상도 판독이라 UI 슬라이스에서 재확인. |
| Tleilaxu track | `advance_tleilaxu(steps)`: 칸 2·6 Intrigue, 4 VP + 첫 도달자 spice 2(`tleilaxu_track_spice` 소진), 7 VP; 끝에서는 `tleilaxu_track_end`(OQ-048). | `[Immortality p. 7]`. |
| Specimen | `rules/specimens.py`: `generate_specimens`(supply만큼, 부족분 `specimens_short`, OQ-049 — UI는 서버 dry-run의 `warning`으로 부족을 미리 표시; 2026-10-04부터 못 만든 수는 `ungained_specimens`에 기록돼 같은 player turn 안에서 supply에 troop이 돌아오면 recruit 부족분 다음으로 채운다, `rules/shortfall.py`), `spend_specimens`; `return_specimen`은 소유자의 turn·효과·Reveal frame, Combat Intrigue 우선권, supply가 빈 Control 방어에서 하나씩(OQ-050, 2026-10-04 재판정). Reveal 카드의 specimen은 `reveal_pending_gains`의 `specimens` 항목 → `generate_reveal_specimens`(OQ-045). | `[Immortality p. 8]`. |
| Research Station | `static_board_effects(..., immortality=True)`가 `(Draw 2, ResearchEffect)`; 아이콘 키 `research`는 `AUTOMATIC_BOARD_ICONS`에 들어가 `resolve_board_effect(effect=research)`로 해결한다. | `[Immortality pp. 5, 16]` `[Main p. 18]`. |
| Experimentation | `PersonalCardAgentEffect.RESEARCH`, `PersonalCardRevealEffect(specimens=1)`; `STARTING_CARDS_BY_ID`에 포함되지만 `STARTING_DECK`(7종)은 그대로. | `[Immortality p. 5]` `[card face]`. |
| Family Atomics | `use_family_atomics`: 소유자의 turn frame들에서 1회, Row 전부를 `imperium_removed`로 보내고 deck 맨 위 5장으로 새 Row(OQ-051). | `[Immortality p. 12]`. |
| 관측·codec | 관측 v12(위 상태 전부 공개), codec v96: `immortality` 카탈로그에 `choose_research_space` ×21·`choose_research_influence` ×4·`trash_for_research_bonus`(카드마다; codec v106부터 `trash_intrigue_for_research_bonus`(Intrigue 카드마다) — c7r3의 비용은 Trash an Intrigue card 아이콘이다, 2026-09-19 재전사)·`pay/decline_research_bonus`·`return_specimen`·`use_family_atomics`·`generate_reveal_specimens`; 기본 카탈로그는 `resolve_board_effect(research)` 1개만 늘었다. heuristic 우선순위와 UI 라벨을 추가. | 소크: random·heuristic 각 6판에서 모든 경로가 발화(연쇄·marker·atomics 포함). |

## 슬라이스 3: Tleilaxu Row

| 영역 | 구현 | 메모 |
| --- | --- | --- |
| 획득 | `rules/tleilaxu_row.py`: REVEAL frame 소유자에게 Row 카드마다 `acquire_tleilaxu(instance_id)`(specimen ≥ 비용), 첫 genetic marker 뒤에는 `to_deck_top=True` 변형도. 지불은 `spend_specimens`(tanks→supply), 카드는 discard pile 또는 deck 맨 위, Row는 deck 맨 위에서 보충(`refill_tleilaxu_row`), 획득 box는 Imperium과 같은 `resolve_acquisition_bonus`(Tleilaxu-aware) + `apply_acquisition_track_effects`. deck 맨 위로 보낸 카드의 instance는 이벤트에 싣지 않는다(deck 순서는 비공개, OQ-010). | `[Immortality pp. 6, 8-9]`. Imperium Row 획득 효과·Persuasion 효과는 Row를 보지 않으므로 자연히 배제된다. |
| Reclaimed Forces | `acquire_reclaimed_forces(choice)`: specimen 3, `troops`(recruit 2, `reveal_troops_recruited`에 합산) 또는 `tleilaxu`(1 전진); 카드는 Row에 남는다. 선택 효과 뒤 face-up Call to Arms가 발동한다(사용자 판정 2026-09-26, OQ-066; `[Immortality p. 9]`). 2026-10-06: Tleilaxu 선택은 track 마지막 칸에서 제시하지 않는다(`reclaimed_forces_block`의 `AcquireBlock.TLEILAXU_TRACK_END`, OQ-071; troop 선택은 낸 specimen 3이 먼저 supply로 돌아가 늘 recruit하므로 카드는 막히지 않는다). Harvest Cells도 같은 해결 `tleilaxu_row.acquire_reclaimed_forces`로 가져갈 수 있다(OQ-066). | `[Immortality p. 9]` `[Reclaimed Forces card]`. |
| 획득 box | `PersonalCardAcquisitionEffect.RESEARCH`·`ADVANCE_TLEILAXU`는 카드가 존에 들어간 뒤 state 수준에서 해결(`apply_acquisition_track_effects`; research는 방향 선택 frame을 열 수 있다). Imperium 획득 경로 4곳과 Tleilaxu 경로 모두. | Subject X-137, (슬라이스 5의) Spiritual Fervor. |
| 카드 | 구현 | 규칙 민감 메모 |
| codec | `immortality` 카탈로그: 모든 카드의 배치 템플릿에 `graft` 변형(Graft 카드는 graft만), `choose_graft_partner` ×개인 카드, `switch_graft_card`, `decline_agent_card_recall`. 기본 카탈로그 불변(4,367). | 4,578→6,857. |

## 슬라이스 4: Graft

| 영역 | 구현 | 메모 |
| --- | --- | --- |
| 배치 | `legal_agent_actions`: Graft 카드(`ImperiumCardEntry.graft`)는 `graft=True` 변형만, 일반 카드는 단독과 (hand에 Graft 상대가 있으면) graft 변형. 아이콘은 첫 카드 기준(`effective_agent_icons(grafted=)`; Blank Slate는 진영 4개 추가). 상대 Agent가 점유한 space는 hand에 Tleilaxu Infiltrator가 있을 때 graft 배치로 열린다. | `[Immortality p. 10]` "You may use an Agent icon from either card": 아이콘을 내는 카드를 첫 카드로 두면 어떤 쌍이든 표현된다. |
| 상대 선택 | `apply_agent_action(graft)`가 효과 frame 위에 `graft_partner` frame을 밀고, `choose_graft_partner(card_id)`는 hand의 카드 중 (첫 카드 또는 후보가 Graft) 조건을 만족하는 것만; 점유 space였으면 둘 중 하나가 Infiltrator여야 한다. 상대는 hand→in play, 효과 frame의 `graft_card_id`·`graft_pending_effect`·`graft_pending_icons`에 자기 box가 대기한다(`agent_effect_is_available`로 판정). | 두 카드 모두 "보낸" 것: Bond·"in play" 판정은 in_play로 자연 성립. |
| 해결 | `switch_graft_card`(효과 frame, 상대 box가 대기 중이고 Long Live 선택 중이 아닐 때)가 `card_id`↔`graft_card_id`와 pending 플래그·아이콘을 맞바꿔 기존 Agent box 기계로 해결한다. `agent_turn_has_other_pending_effects`가 `graft_pending_effect`를 본다. `expire_trashed_card_effects`는 상대 카드의 미발동 box도 만료한다(FAQ의 Beguiling Pheromones 판정). | `[Immortality pp. 10-11]` `[FAQ p. 1]`. `is_grafted`/`other_grafted_card_id`(`rules/effects.py`). |
| 카드 | 구현 | 규칙 민감 메모 |
| codec | `immortality` 카탈로그: 모든 카드의 배치 템플릿에 `graft` 변형(Graft 카드는 graft만), `choose_graft_partner` ×개인 카드, `switch_graft_card`, `decline_agent_card_recall`. 기본 카탈로그 불변(4,367). | 4,578→6,857. |

## 슬라이스 5a: Intrigue 11장

| 영역 | 구현 | 메모 |
| --- | --- | --- |
| DSL | `effect_dsl.py`: 조건 `GeneticMarkersAtLeast(1|2)`·`SolariAtLeast`·`SpiceAtLeast`·`OpponentPlayedCombatIntrigue`·`AllConditions`(Study Melange·Tleilaxu Puppet의 두 조건); 보상 `Research`·`AdvanceTleilaxu(count)`·`GenerateSpecimens(count)`·`AcquireTleilaxuCard`·`RevealPersuasionThisRound`; trigger `OnTroopsLostAtConflictEnd(minimum)`(Combat timing 허용). | 전사표(위 Intrigue 표)와 1:1. |
| 해석 | `effect_interpreter.apply_rewards`가 자원 뒤에 specimen → Tleilaxu → Research 순으로 state 수준에서 해결(research는 방향 frame을 열 수 있어 마지막). `AcquireTleilaxuCard`는 선택 slot: Row 카드(specimen ≥ 비용)와 deck 맨 위 변형, 거절. Harvest Cells는 자동 보상(specimen 2)을 OQ-015대로 소유자가 `resolve_intrigue_rewards`로 먼저 받아야 살 수 있다. | `[Immortality pp. 6-8]`. |
| 효과 판정(2026-10-06, codec v138) | 사용자 판정 "아무 효과 없이 책략을 쓸 수 없는거지"(OQ-071의 카드 확장 2): option의 효과 중 하나라도 지금 무언가를 바꿀 수 있어야 낸다(`effect_interpreter.reward_can_change_something`). Immortality 보상의 판정: `Research`는 두 번째 genetic marker 전이면 늘(token이 움직인다), 그 뒤면 덱이나 버린 더미에 카드가 있을 때(그때 Research는 draw다 `[Immortality p. 6]`); `AdvanceTleilaxu`는 track이 끝나지 않았을 때(OQ-048); `GenerateSpecimens`는 비용을 낸 뒤 supply에 troop이 있거나 비용으로 잃는 troop이 supply로 돌아올 때(specimen 반환으로 specimen을 만드는 것은 변화가 아니다); `RevealPersuasionThisRound`(Tleilaxu Puppet)는 늘 센다(메인 세션 결정). 그래서 Breakthrough는 두 marker 뒤에 덱·버린 더미가 모두 비면, Illicit Dealings와 Shadowy Bargain의 Endgame option은 track 끝에서(칸 6에서는 VP 1을 얻으므로 낸다), Shadowy Bargain의 Plot specimen은 supply에 troop이 없으면, Gruesome Sacrifice는 track이 끝났고 supply에도 Conflict에도 troop이 없으면(Conflict에 Commander만 — Bloodlines+Immortality) 낼 수 없다. Chani가 Gruesome Sacrifice의 비용으로 얻는 Tactics 전진은 효과로 세지 않는다(메인 세션 결정). | `tests/unit/rules/test_immortality_intrigue.py`(`test_breakthrough_past_the_second_marker_needs_a_card_to_draw`, `test_illicit_dealings_is_not_offered_at_the_track_end`, `test_shadowy_bargain_endgame_advance_is_not_offered_at_the_track_end`, `test_shadowy_bargain_plot_specimen_needs_a_troop_in_the_supply`, `test_gruesome_sacrifice_needs_a_troop_or_a_track_space_to_change`). |
| Counterattack | `apply_intrigue_play`가 Combat 중 play된 Combat option의 좌석을 `combat_intrigue_players`에 기록하고 `finish_combat`이 비운다(관측 세그먼트). Plot의 "Deploy up to two troops from your garrison to the Conflict."는 배치할 수 있는 garrison unit이 있어야 내고(Harkonnen Advisor의 troop과 Emperor of the Known Universe의 배치 금지 turn은 세지 않는다 — `effect_interpreter.deployable_garrison_units`), 낸 뒤에는 0명도 고를 수 있다. 이력: 2026-10-06 앱 카드 대조가 빈 garrison에서도 내게 했고(OQ-057 (6) 보강, codec v137) 같은 날 사용자 판정 "아무 효과 없이 책략을 쓸 수 없는거지"로 되돌렸다(OQ-038 재판정, codec v138; `test_counterattack_plot_needs_a_deployable_garrison_unit`, `test_counterattack_plot_deploys_up_to_two_including_none`). | "in this Conflict" = 이번 Combat. |
| Harvest Cells | "When you lose at least three troops at the end of a Conflict:" `[Harvest Cells card]`. 2026-10-06부터(사용자 판정 "앱처럼 전투 후에만", OQ-016) 보상 해결 뒤·정리 전의 `conflict_end_trigger` 창(`combat.offer_conflict_end_triggers`)에서만 낸다: 정리 전 Conflict의 troop+Commander 수를 "잃은 troop"으로 삼아(FAQ p. 1 Chani: supply로 돌아간 troop은 lost) 3 이상인 좌석이 First Player부터. 다른 Intrigue 창에서는 `IntriguePlayBlock.CONFLICT_END`로 막혀 Combat Intrigue에서 face-up으로 미리 낼 수 없다(화면은 흐리게). 낸 카드는 face-up에 놓였다가 `finish_combat`의 troop 반환 뒤 `resolve_faceup_trigger_option`으로 발동한다(Makers 전에 INTRIGUE_CHOICE frame). 만료(`intrigue_expired`) 분기는 닿을 수 없어 `RuntimeError`다. "You may also acquire a Tleilaxu card (paying its normal cost)."의 slot은 Reclaimed Forces도 제시한다(`acquire_intrigue_reclaimed_forces(choice)`, 사용자 판정 2026-10-06, OQ-066). 이력: 2026-09-26까지는 창에서 낸 카드가 반환 전에 즉시 발동해 supply가 비면 specimen 0이었고, 2026-10-06까지는 Combat Intrigue에서 face-up으로 내 3 미만을 잃으면 정리 때 만료됐다. 2026-10-06(책략 효과 판정, OQ-016 보강)부터 창은 그 사본이 무언가를 바꿀 수 있을 때만 카드를 넣는다(`combat._harvest_cells_has_effect`): supply와 Conflict의 troop에서 이미 face up으로 놓은 사본들의 specimen을 빼고 1 이상 남거나(Commander는 Commander supply로 가므로 세지 않는다), 앞 사본들이 만들 specimen까지 쳐서(상한 추정) Tleilaxu Row 카드나 Reclaimed Forces 효과를 살 수 있을 때. 한 사본을 낸 뒤에 다른 사본을 다시 찾으므로 첫 사본이 troop을 다 쓰면 창이 닫힌다(`apply_conflict_end_trigger`). | `[FAQ p. 1]` `[FAQ p. 2]` `[card face]`. `test_harvest_cells_is_never_played_in_combat_intrigue`, `test_harvest_cells_is_never_offered_below_three_troops_in_the_conflict`, `test_harvest_cells_may_take_reclaimed_forces_troops`, `test_harvest_cells_window_skips_a_copy_that_would_change_nothing`. |
| Tleilaxu Puppet | `PlayerState.reveal_persuasion_round_bonus`: Round Start에 0, `begin_reveal_turn`의 Persuasion 합계에 더한다(Command (6+) 판정에도 포함). 소유자의 Reveal이 이미 열린 뒤 play하면(Plot은 Reveal turn에도 쓸 수 있다 `[Main pp. 7, 8]`) 그 Reveal frame에 바로 더하고 round 보너스는 그대로 둔다(2026-09-26 감사 수정; 전에는 카드만 쓰이고 Persuasion이 사라졌다). | "this round". |
| heuristic | `switch_graft_card` 우선순위를 0.2로 낮췄다(전 옵션 소크에서 두 box를 무한히 오가는 seed 발견). | |

## 슬라이스 5b-1: Imperium 15종

| 영역 | 구현 | 메모 |
| --- | --- | --- |
| 단일 box | `GENERATE_SPECIMEN`(Lab), `GAIN_BENE_GESSERIT_INFLUENCE_AND_INTRIGUE`(Clandestine Meeting — 아이콘이 없어 graft 상대로만 play), `GAIN_TWO_SPICE_IF_GRAFTED`(Corrupt Smuggler), `GAIN_TWO_SPICE_IF_EMPEROR_INFLUENCE_TWO`(Keys to Power), `GAIN_FREMEN_INFLUENCE_IF_BENE_GESSERIT_BOND`(Lisan al Gaib), `DRAW_ONE_AND_COMBAT_ICON`(Occupation), `DRAW_TWO_CARDS`(Show of Strength), `GAIN_WATER_AND_RETURN_SELF_IF_FREMEN_ALLIANCE`(Stillsuit Manufacturer — hand으로 돌아온 카드는 `hand_public`; 2026-10-06부터 water 아이콘과 `return_self` 아이콘으로 나뉘고, 반환은 같은 turn의 늦은 Fremen Alliance를 기다렸다가 없으면 turn 종료에 소멸한다, OQ-027·OQ-057 (1), `test_stillsuit_manufacturer_return_waits_for_a_later_fremen_alliance`), `RECRUIT_ONE_AND_MAY_TRASH`(Throne Room Politics — recruit 뒤 `optional_trash` frame). 모두 해결 시점 판정(OQ-028). | 카드면. |
| 선택 box | Long Reach `GAIN_TWO_DISTINCT_CHOSEN_INFLUENCE`: `choose_agent_card_influence`를 두 번, 두 번째는 다른 진영만(`influence_chosen` 컨텍스트). Organ Merchants `MAY_PAY_SPECIMEN_FOR_FOUR_SOLARI`: `pay_agent_card_specimen`/거절. Sardaukar Quartermaster `RECRUIT_ONE_AND_DRAW_ONE_IF_GRAFTED`: troops·cards 아이콘, graft 아닐 때 둘 다 불발. | |
| 조건부 아이콘 | `ImperiumCardEntry.icon_condition`: Long Reach(다른 BG 카드가 play 중), Show of Strength(배치 troop이 각 상대보다 많음 — `effective_agent_icons(opponents=)`). 조건이 없으면 아이콘 0개(play 불가). Blank Slate는 graft 시 진영 4개 추가. | play 시점 판정. graft 상대가 BG 카드(Planned Coupling)나 Ghola면 그 상대가 조건을 충족한다 — graft 쌍은 함께 play되고 `[Immortality p. 10]` Ghola 설명은 graft한 BG 카드를 in play로 센다 `[Immortality p. 14]`(`bond_partner`, OQ-057 (12)). 그 아이콘으로만 닿은 space면 partner는 그런 카드로 제한된다. play 중인 Long Reach 자신은 "another" BG 카드가 아니다. (2026-09-26 정정: 이전에는 BG 상대를 세지 않아 Long Reach를 첫 카드로 쓸 수 없었다.) |
| 획득·trash·Reveal | 획득 box `GAIN_ONE_SPICE`(Lisan)·`RECRUIT_THREE_TROOPS`(Occupation)·`RESEARCH`(Spiritual Fervor); trash trigger `ADVANCE_TLEILAXU`(Replacement Eyes, `card_trash.py` 지역 import); Reveal 필드 `tleilaxu`·`research`(Dissecting Kit·Tleilaxu Master용; Research는 방향 frame이 열리면 남은 아이콘을 다시 대기열에), Occupation의 water·spice·troop, Bene Tleilax Lab의 (1M) spice. | `[Immortality pp. 6-8]`. Occupation의 `RECRUIT_THREE_TROOPS`는 (Arrakis Revolt의 `RECRUIT_ONE_TROOP`와 함께) 모든 획득 경로(일반·manipulated Row 구매, Agent box 획득, 카드·Intrigue가 발동한 획득)에서 그 turn의 recruit 수에 더해지도록 2026-09-26에 고쳤다: "그 turn에 어떤 출처에서 recruit했든 새 troop은 Conflict에 deploy할 수 있다" `[Main p. 10]` `[FAQ p. 4]`(이전에는 garrison에만 더해지고 세지 않았다). |
| Graft 보강 | `apply_graft_partner`가 첫 카드의 Bond 조건 box를 상대가 들어온 뒤 다시 판정해 대기시킨다(Lisan al Gaib + BG 상대). | OQ-028의 연장. |

## 슬라이스 5b-2: Imperium 8종

For Humanity와 Interstellar Conspiracy의 "◇?" 아이콘은 카드면 확대로 "원하는 진영의 Influence 1"로 확인했다.

| 카드 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Dissecting Kit | `MAY_TRASH_OTHER_GRAFTED_FOR_SPECIMEN`: 지불 provider의 `trash_grafted_card_for_specimen`/거절. 상대 카드가 play 영역에 없으면 box 불발. trash 전에 상대의 `graft_pending_effect`를 끄고(OQ-022) 효과 frame을 정리한 뒤 trash·specimen 생성. Reveal (1M) Tleilaxu. | Graft 카드라 단독 play 불가 `[Immortality p. 10]`. |
| For Humanity | Agent `GAIN_CHOSEN_INFLUENCE`(기존). Reveal choice `MAY_LOSE_INFLUENCE_FOR_VP_IF_BENE_GESSERIT_ALLIANCE`: `lose_reveal_influence_for_vp(faction[, alliance_recipient])`/거절 — 고른 한 진영에서 Influence 2를 잃는다(카드 면의 "?" 다이아몬드에 빨간 chevron 두 개 `[For Humanity card]`; 2026-09-26 이전에는 1로 오독). 열리는 조건: BG Alliance 보유 + Influence 2 이상인 진영 존재(화살표 비용은 전부 내거나 안 낸다 `[Main p. 20]`; OQ-028, 선택이 열릴 때 판정). | Influence 손실의 Alliance 이전은 OQ-015·`lose_faction_influence`와 동일하게 한 칸씩 처리하며, 수령자 선택은 token이 움직이는 칸(첫째 또는 둘째)에서 제시한다 `[FAQ p. 1]`. |
| High Priority Travel | `DRAW_ONE_OR_COMBAT_ICON_IF_SPACING_GUILD_INFLUENCE_TWO`: Guild 2 이상이면 `resolve_agent_card_effect`(draw)와 `take_agent_card_combat_icon` 중 선택, 아니면 불발. Combat 아이콘은 `grant_combat_icon`이 frame에 쓰므로 컨텍스트를 다시 읽고 닫는다(Occupation도 같은 수정). Reveal 1 Solari. | |
| Imperium Ceremony | `PEEK_TWO_INTRIGUE_KEEP_ONE` → `rules/intrigue_peek.py`의 `INTRIGUE_PEEK` frame(`keep_peeked_intrigue(instance_id)`). 소유자만 두 장을 본다: `PrivatePlayerView.peeked_intrigue_ids`(관측 v14 세그먼트 `private_peeked_intrigue`), `known_card_seats`, determinize·privacy invariant가 deck 맨 위 두 장을 고정. keep 이벤트는 공개 `intrigue_card_drawn`(수만) + 소유자 전용 `intrigue_card_kept`. | OQ-052(사용자 판정): 두 장 미만이면 맨 윗장을 두고 그 밑에 discard를 섞은 뒤 두 장을 본다(셔플 frame `purpose=peek`). 섞을 discard도 없이 한 장만 남았으면 그 한 장으로 같은 frame을 연다(keep만; 2026-10-02 사용자 판정 L2-Q3 "①②는 확인 창, ③은 회색 줄만"의 ②, 전에는 창 없이 draw 1장). |
| Interstellar Conspiracy | `GAIN_SPICE_AND_CHOSEN_INFLUENCE_IF_GRAFTED_WITH_EMPEROR_OR_GUILD`: 상대 카드에 Emperor/Guild 진영이 있으면 Influence provider가 4진영 선택을 열고 spice 1을 함께 지급, 아니면 일반 해결로 spice 1만. | Graft 카드. |
| Shadout Mapes | Agent box 없음. Reveal choice `MAY_DEPLOY_OR_RETREAT_ONE_TROOP`: `deploy_reveal_card_troop`(`add_units_to_reveal`)·`retreat_reveal_card_troop`(`retreat_units`, 전투력 차이를 Reveal frame `strength`에 반영)·거절. 같은 행동을 Uprising의 Unswerving Loyalty("Fremen Bond: … deploy or retreat one of your troops")가 Fremen Bond 뒤에서 쓰므로(2026-09-26) 세 행동 template은 모든 catalog에 있다. Bloodlines와 함께면 Commander도 "troop"이므로 `[Bloodlines p. 4]` `commanders` 1 변형으로 garrison·Conflict의 Commander를 배치·후퇴할 수 있고(2026-09-26 감사 수정), 그 두 template은 Immortality 여부와 관계없이 Bloodlines catalog에 있다. | 배치는 Combat 아이콘 없이 카드 효과로 한다. |
| Tleilaxu Master | `MAY_ACQUIRE_CARD_UP_TO_SIX_IF_ONE_MARKER`: 획득 provider(`legal_agent_card_acquisitions`)가 marker 1 이상일 때 `acquire_reserve_by_card`/`acquire_imperium_by_card`(비용 6 이하, `acquirable_*` 헬퍼)·거절을 연다. marker 2 이상이면 hand로(`hand_public`). box를 먼저 닫고(`advance_after_effect`) `acquire_*_for_intrigue`로 획득해 Spy·Contract·Research 후속 frame이 turn 위에 쌓인다. 2026-10-06: 소유자가 Manipulate로 빼 둔 카드도 인쇄 비용 6 이하이면 제시한다("You may use other means to acquire the card" `[FAQ p. 3]`; `acquirable_imperium_instance_ids(..., player=)`, `test_tleilaxu_master_reaches_its_owners_set_aside_card_at_the_printed_cost`). Reveal Research ×2. | (1M)/(2M) 모두 해결 시점 판정(OQ-028). |
| Tleilaxu Surgeon | `MAY_PAY_TWO_SPECIMENS_FOR_TWO_TLEILAXU`: `pay_agent_card_two_specimens`/거절 → `advance_tleilaxu` 2칸(Tleilaxu track 마지막 칸이면 지불은 제시하지 않는다 — `agent_card_payment_block`, OQ-071, 2026-10-06; `test_tleilaxu_surgeon_offers_no_payment_at_the_tleilaxu_track_end`). Reveal choice `MAY_LOSE_TWO_TROOPS_FOR_TWO_SPECIMENS`: `lose_reveal_troops_for_specimens(zones)`/거절 → troop마다 존을 골라(garrison·Conflict 둘 다, 각각 하나씩) `lose_unit` ×2, 전투력 차이 반영, specimen 2. | OQ-053(사용자 판정: 존 혼합 허용, Commander 제외). |

부수 수정(소크 heuristic seed 11이 적발): 획득한 카드의 Research 획득 box(Spiritual Fervor)가 여는 `RESEARCH_ADVANCE` frame이 (1) Intrigue 획득 slot의 choice frame을 묻어 `RuntimeError`, (2) Price is No Object의 `advance_after_effect`가 frame을 덮어쓰고, (3) Leader Signet 획득도 같은 구조였다. `intrigue.py`의 `_lift_pushed_frames`/`_restack`이 slot 처리 뒤 밀어 올린 frame을 다시 얹고(late reveal이 아래에 끼워 넣는 frame은 그대로), 나머지 두 경로는 box를 먼저 닫은 뒤 획득한다.

## 슬라이스 5c-1: Tleilaxu 6종 + Piter

| 카드 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Industrial Espionage | `DRAW_ONE_AND_RESEARCH_AND_SPECIMEN_IF_GRAFTED`: 2026-10-06부터 box가 draw 아이콘(`cards`)과 "If grafted:" 줄의 아이콘(`research`: specimen과 Research)을 대기시키고 소유자가 순서를 고른다(OQ-027, `agent_effects._PLACEMENT_ICONS`). Research를 먼저 하면 방향·보너스 frame(c3r3·c7r5의 선택 trash 포함)이 draw 앞에 오고, draw를 먼저 하면 그 trash가 방금 뽑은 카드를 고를 수 있다. graft가 아니면 `research` 아이콘은 기다리다 turn 종료에 소멸한다(OQ-057 (1)). 전에는 한 번의 해결이 graft면 specimen·research, 그 다음 draw로 순서를 고정했다. | `is_grafted`는 해결 시점 판정. `test_industrial_espionage_research_bonus_resolves_before_its_draw`, `test_industrial_espionage_draw_first_lets_the_bonus_trash_the_drawn_card`. |
| Scientific Breakthrough | `RESEARCH_AND_MAY_TRASH_SELF_FOR_VP_IF_TWO_MARKERS`: marker 2 이상이면 지불 provider가 `resolve_agent_card_effect`(research 먼저)와 `trash_agent_card_self_for_vp`(자기 trash + VP + research)를 연다. research를 먼저 해결하면 box는 열린 채 남고(`research_resolved_card_ids`), research가 끝난 뒤 marker가 2 이상이면 `decline_agent_card_payment`와 research 없는 `trash_agent_card_self_for_vp`를 연다 — 카드 자신의 Research가 두 번째 marker에 닿아도 trash 줄을 쓸 수 있다(OQ-028, 2026-09-26). 2 미만이면 줄은 turn 종료까지 보류된 뒤 소멸한다(OQ-057 (1)). 자기 trash는 `agent_card_self_trashed`(OQ-022: 자기 비용이라 보상 유지). | 두 번째 marker 뒤의 Research는 draw(슬라이스 2 판정). Ghola가 복사한 box는 따로 research한다(카드별 기록). |
| Guild Impersonator | `GAIN_SPACING_GUILD_INFLUENCE_IF_GAINED_SPICE_THIS_TURN`: `spice_gained_this_turn(owner)`(turn 시작 대비 순증가 + 지출) ≥ 1이면 Guild Influence, 아니면 불발. | 해결 시점 판정(OQ-028): Hagga Basin의 spice를 먼저 받으면 성립. |
| Slig Farmer | `GAIN_SOLARI_PER_PARTNER_ICON_AND_MAY_PAY_FIVE_SOLARI_FOR_TLEILAXU`: 상대 카드가 그 순간 가진 Agent 아이콘 수만큼 Solari(`_partner_icon_count` → `effective_agent_icons`, graft 기준); 받은 뒤 5 이상이면 `pay_agent_card_five_solari_for_tleilaxu`로 Tleilaxu 1칸. Tleilaxu token이 track 마지막 칸이면 그 지불은 제시하지 않는다(`agent_effects.agent_card_payment_block`, OQ-048·OQ-071, 2026-10-06; `test_slig_farmer_offers_no_track_step_at_the_tleilaxu_track_end`). | OQ-055(사용자 판정): Blank Slate의 graft 아이콘 등 추가 아이콘도 센다. |
| Stitched Horror | `CHOOSE_TWO_OF_WATER_TROOP_TRASH_TLEILAXU`: `choose_agent_card_reward(reward)`를 두 번, 같은 보상은 두 번 고를 수 없다(`rewards_chosen`). water·troop은 즉시, tleilaxu는 `advance_tleilaxu`, trash는 `optional_trash` frame(효과 frame 위에; 2026-09-30 OQ-095 전에는 둘째 선택이면 turn을 닫은 뒤). | "Choose two"의 순차 선택은 Long Reach와 같은 기계. |
| Beguiling Pheromones | `TRASH_GRAFTED_CARD_FOR_VISITED_FACTION_INFLUENCE`: 방문 space에 진영이 있고 graft일 때 `trash_grafted_card_for_influence(card_id)`로 두 grafted 카드 중 하나(play 영역에 있는 것)를 trash하고 그 진영 Influence 1. 인쇄문 "trash one of the grafted cards and gain an additional Influence"에는 "may"·화살표·검은 X가 없어 의무다 `[FAQ p. 3]` — 거절은 없고 어느 카드를 trash할지만 고른다(2026-09-26 정정: 이전에는 `decline_agent_card_payment`를 제시했다). 상대를 trash하면 상대의 미발동 box 소멸(`graft_pending_effect=False`), 자기를 trash하면 `agent_card_self_trashed`. | `[FAQ p. 1]`의 Beguiling Pheromones 판정(OQ-022). Faction 방문 여부는 `space_id`의 인쇄 진영. |
| Piter, Genius Advisor(프로모) | `MAY_LOSE_TROOP_TO_DRAW_TWO_AND_RESEARCH`: `lose_agent_card_troop(zone)`(garrison/Conflict, OQ-038의 존 선택; Conflict면 전투력과 회수할 수 있는 수·이번 turn 배치 수만 조정하고 쓴 기본 배치 한도는 돌아오지 않는다 — OQ-029 재판정 2026-10-04; garrison이면 Harkonnen Advisor의 배치 금지 troop을 먼저 잃은 것으로 친다 — OQ-038 (b)) — 처리 순서는 box의 frame을 먼저 닫고 → 손실과 그 조정 → research(방향 frame) → draw 2. 2026-10-04 정정: box의 frame을 손실보다 먼저 써서, 손실이 frame에 남긴 기록(회수 창 축소, 배치 금지 troop 해제)이 덮어써지지 않는다(`test_piters_troop_lost_from_the_conflict_does_not_reopen_the_deployment`, `test_piters_garrison_troop_is_the_undeployable_one`). | `promo_cards`+`immortality`일 때만 덱에. |

## 슬라이스 5c-2: Ghola·Chairdog·Usurp

| 카드 | 구현 | 규칙 민감 메모 |
| --- | --- | --- |
| Ghola | 정의에는 box가 없고(`agent_effect=None`), `rules/effects.py`의 `borrowed_agent_card`/`active_agent_card(context)`가 활성 카드가 Ghola면 상대 카드의 `agent_effect`와 Spy 배치 제한(`agent_spy_factions`, Reliable Informant의 "[Spy] on ...")을 끼운 정의를 돌려준다 — "Ghola copies the entire Agent box" `[Immortality p. 14]`(2026-09-26: 이전에는 효과만 복사해 제한 없이 놓았다). `agent_effects.py`의 활성 카드 조회 17곳, `acquisition.py`(Tleilaxu Master·Price is No Object provider), `leader_abilities.py`(Signet 판정)가 이 접근자를 쓴다. `apply_graft_partner`는 양쪽을 빌린 box로 판정해 `pending_*`/`graft_pending_*`을 채운다. | 상대 box가 비어 있으면(Face Dancer Initiate) Ghola도 비어 있다. 상대가 self-trash box면 Ghola 자신이 trash된다(`card_id`가 Ghola). |
| Chairdog | `RETURN_OTHER_GRAFTED_TO_HAND_AT_REVEAL_START`: 해결 시 상대 카드 id를 좌석의 `chairdog_return_card_ids`에 적고, `begin_reveal_turn`이 `_return_chairdog_cards`로 play 영역에서 hand(`hand_public`)로 되돌린 뒤 그 hand를 Reveal한다. Round Start에 비운다. 관측 v15 좌석 scalar(대기 수). | 상대가 이미 play 영역을 떠났으면 무시. |
| Usurp | 아이콘·box 없음. 배치: graft 변형만, 후보 상대(Row 카드 + hand 카드) 아이콘의 합집합으로 space 결정(`_placements_for_card`; 따라올 상대가 없는 space는 제외; codec은 graft 변형을 모든 space에 둔다). 상대 선택: Row 카드와 hand 카드 중 그 space에 닿는 카드(`legal_graft_partner_actions`) — "may"라 hand 상대도 된다. Row 상대는 `take_imperium_row_card`로 빠지고 Row가 즉시 채워지며 좌석의 `usurped_row_card_id`에 남는다. 소유자가 `finish_agent_turn`을 누르면 `graft.trash_usurped_card`가 `trash_personal_card`로 **자동 trash**해 trash 이벤트·트리거가 발동한다(OQ-054, 사용자 판정). 2026-10-01부터(OQ-095 (5)) 그 trash는 아직 열린 turn 안에서 일어나 결과가 그 turn의 것이고, 의무 Contract나 배치할 수 있는 새 recruit가 생기면 turn이 다시 열린다(`combat_deployment.settle_finishing_agent_turn`). 이력: 그 전에는 turn이 닫힌 뒤 dispatcher(`usurp_trash_is_queued`·`resolve_usurp_trash`)가 trash했고, 그래서 `trash_personal_card`에 항상 `turn_closed=True`를 넘겼다 — 빌린 카드가 Sardaukar Standard(Bloodlines)면 이 값이 없으면 queue된 Skill 선택이 방금 다시 열린 같은 player의 새 turn frame을 잘못 credit한다(2026-09-26 review round 5, 상세는 `docs/implementation-audits/bloodlines.md`의 Eliminate Allies 행 (f)). 관측 v15 좌석 scalar(빌린 카드 여부). | hand 카드를 먼저 놓고 Usurp를 상대로 고르는 보통의 graft도 그대로 된다(Usurp box 없음). |

heuristic: 활성 box가 decline만 제공할 때 `switch_graft_card`를 decline 아래로 내린다(Ghola가 Corrinth City의 box를 복사한 seed 11에서 두 box가 decline만 제공해 무한 switch).

2026-10-06: 이 강등과 Combat Intrigue 우선권의 `return_specimen` 강등은 `agents/heuristic_agent.demote_pointless_actions` 한 함수로 모였다(`scripts/ab/pypath/hvariants.py`의 A/B 변형도 같은 함수를 불러, null 변형이 heuristic과 결정마다 같다). 같은 함수가 새로 두 가지를 맨 아래로 둔다: garrison이 빈 채 "Deploy up to N troops" 줄만 있는 Intrigue play(Counterattack의 Plot, Detonation, Twisted Devious — codec v137부터 대상 없이도 낼 수 있어, heuristic이 카드만 쓰고 0명을 배치하던 것)와 count 0의 `deploy_intrigue_troops`·`retreat_intrigue_troops`(1 이상의 수는 순서와 무작위 추첨을 그대로 둔다). heuristic은 관측만 보므로 Harkonnen Advisor의 배치 금지 troop(OQ-038)과 Emperor of the Known Universe의 배치 금지는 보지 못해, 그런 turn에는 여전히 그 줄을 낼 수 있다. `tests/unit/test_heuristic_agent.py`(`test_a_deploy_up_to_plot_is_not_spent_on_an_empty_garrison`, `test_a_zero_unit_count_never_outranks_moving_a_unit`). 같은 날 사용자 판정(OQ-038 재판정, codec v138)으로 엔진이 배치할 unit이 없는 그 play를 다시 제시하지 않으므로(배치 금지 troop과 배치 금지 turn 포함), 빈 garrison의 Intrigue play 강등은 엔진 목록에서는 닿지 않는 안전망이 됐다(heuristic 코드는 그대로; 그 주석의 "since codec v137"은 낡았다). count 0 강등은 낸 뒤의 선택이라 그대로 쓰인다.

## 슬라이스 6: UI·소크·census

| 영역 | 구현 | 메모 |
| --- | --- | --- |
| UI | 카탈로그에 Tleilaxu deck + Reclaimed Forces(specimen 비용·Graft 표시·이미지)와 `bene_tleilax` 절(research hex의 열·행·보너스, genetic marker 열, Tleilaxu track, 스캔 URL과 percent 레이아웃). market에 Tleilaxu Row(deck 수, specimen 배지, Reclaimed Forces)와 Bene Tleilax board 패널 — 사용자가 가져온 스캔(`assets/board/bene_tleilax.jpg`, 5551x3952, `/bene-tleilax-image`) 위에 좌석의 research token·Tleilaxu token·bank spice를 percent 좌표(`display/bene_tleilax_layout.py`, 5% grid로 측정)로 그리고, 스캔이 없으면 합성 grid로 대체; 좌석 카드에 specimen·research/Tleilaxu 위치·Family Atomics·Chairdog 반환 대기·Usurp 빌린 카드. headless Chromium으로 렌더·정렬 확인. | 스캔으로 research track 22칸 보너스와 Tleilaxu track 배치를 대조했고 전사와 전부 일치한다(c8r6 "Solari 7 → Tleilaxu 2" 포함). |
| 소크 | `dune-imperium-sweep --rotate-leaders --soundness-interval 25`: immortality+promo random 300·heuristic 150, 전 옵션(base·CHOAM × promo+Bloodlines+Tech+Immortality) random 200·heuristic 120, immortality draft 60 — 830판 실패 0. 첫 실행이 적발한 결함 3계열은 아래. | |
| census | Immortality Imperium 25·Intrigue 11·Tleilaxu 19 전부 play/acquire 0회 없음(Clandestine Meeting은 graft 상대로만 play되므로 census가 `card_grafted`를 세도록 보강). `immortality` 카탈로그 전용 행동 가운데 0회는 `decline_agent_card_recall`(Twisted Mentat의 recall 거절)과 `decline_reveal_influence_loss`(For Humanity, BG Alliance 필요)뿐이며 둘 다 단위 테스트가 덮는다. research 보너스·Family Atomics·Tleilaxu track 끝(OQ-048)·specimen 부족(OQ-049)·반환 모두 발화. | |

첫 소크가 적발한 결함(`37fa1b7`): (1) 두 번째 marker 뒤 Research ×2의 draw가 빈 deck에서 discard 셔플 chance frame을 두 번 밀어 같은 카드가 두 존에 — `draw_or_request_personal_cards`가 같은 좌석의 대기 중인 셔플에 합류; (2) Usurp를 Infiltrator 약속으로 점유된 space에 놓았는데 Infiltrator가 그 space에 닿지 않아 상대 선택이 비는 교착 — 배치 시점에 따라올 수 있는 상대가 있는 space만 제공; (3) Ghola가 CHOAM Demands를 복사한 두 box에서 heuristic이 `switch_graft_card`(0.2)를 `complete_contract_by_card`(0.0)보다 골라 무한 반복 — 해결 가능한 box 행동이 있으면 switch를 최하위로.

## baseline agent의 Immortality 가치 (2026-09-09)

heuristic은 Tleilaxu 카드를 전부 2.5, research 분기를 전부 3.0으로 매기는 고정 prior였고 rollout의 `player_value`에는 Immortality 항이 아예 없었다. 두 baseline에 같은 축척으로 넣었다.

| 대상 | 채점 | 근거 |
| --- | --- | --- |
| `acquire_tleilaxu` | 기본 2.5 + 인쇄된 specimen 비용 + `_TLEILAXU_BONUSES` + deck-top 0.5 | Imperium 획득과 같은 구조("Tleilaxu cards ... cost specimens to acquire rather than persuasion" `[Immortality p. 8]`). 보너스는 획득 box가 즉시 값을 치르거나 득점하는 5종(Subject X-137 1.0, Scientific Breakthrough 1.0, Corrino Genes 0.5, Twisted Mentat 0.5, Usurp 0.5). deck-top은 첫 genetic marker가 여는 무료 상향 `[Immortality p. 6]` |
| `choose_research_space` | 기본 3.0 + 도착 칸의 인쇄 보너스(`_RESEARCH_BONUS_SCORES`) | Research 2.0이 최고 — "triggering another research icon and immediately advancing her token again" `[Immortality p. 6]`. 나머지는 `player_value`의 자산 계수(Influence 1.5, specimen·Tleilaxu 0.5, spice 0.4, Solari 0.25)에 맞춤 |
| `acquire_reclaimed_forces` | troops 0.7 / tleilaxu 0.5 | 같은 specimen 3의 두 선택 `[Immortality p. 9]`; garrison troop 2개(0.6×2)가 track 한 칸(0.5)보다 크다 |
| `player_value` | specimen 0.5, research 열 0.4, Tleilaxu 칸 0.5, Family Atomics 0.3 | specimen은 Axolotl tanks에 있는 supply troop이고 `[Immortality p. 8]` supply의 troop은 0점이므로 순증가다. 두 track은 영구 진행(Tleilaxu track은 칸 4·7에서 VP) |

A/B(변경 전 스냅샷을 별도 baseline으로 등록해 같은 seed·좌석 회전으로 대전, `--immortality --rotate-leaders`, 400 seed × 4 회전 = 1,599 매치, 2:2 미러): 새 가중치 승률 27.9%·평균 순위 2.403·평균 VP 7.20, 스냅샷 22.1%·2.597·6.92. 미러의 기준선 25% 대비 +2.9%p이고 독립 seed 블록 4개 전부에서 평균 순위가 개선됐다.

같은 A/B가 엔진 교착 1건을 적발했다(seed 78): Ghola가 Steersman의 "draw 1 + recall" box를 복사하면 첫 box의 recall이 이번 turn의 유일한 Agent를 되돌린 뒤 복사본의 recall 아이콘에 대상이 없어지는데, 불발 판정이 아이콘이 남은 box를 즉시 "불발 아님"으로 처리해 `finish_agent_turn`이 제시되지 않았다. OQ-057 (1)의 확정 판정("의무 box는 turn 종료까지 보류되고 그때 불발")을 아이콘 box에도 적용하도록 고쳤다(`_pending_icons_offer_nothing`, `fizzle_pending_agent_icons`; 회귀 테스트는 `tests/unit/rules/test_immortality_tleilaxu_cards.py`).

## Go to 11 변형 (2026-09-28)

규범 근거는 [`rules/immortality.md`](../rules/immortality.md) 8절과 [OQ-091](../rules/open-questions.md#oq-091--go-to-11-변형을-uprising에-적용하는-방식)이다. 4인 게임의 승점 마커만 1 `[Main p. 5]`에서 0으로 옮기고 `[Immortality p. 12]`, 10점 Endgame 조건(`rules/phases.py`의 `>= 10`)은 건드리지 않는다.

| 항목 | 구현 | 고정하는 테스트 |
| --- | --- | --- |
| 옵션 | `RulesetConfig.go_to_11`(Immortality 없이 켜면 `ValueError`), 식별자 `+go11`(`+immortality` 뒤), `starting_victory_points` | `tests/unit/test_config.py` |
| setup | `create_unshuffled_players(victory_points=...)`를 고정 Leader·draft 두 경로가 모두 넘긴다. 무작위 결정은 늘지 않아 chance 기록이 같다. `PlayerState`의 기본값 1은 fixture를 위해 그대로 둔다 | `tests/unit/rules/test_immortality.py`(`test_go_to_11_starts_every_score_marker_on_zero`) |
| Endgame | 조건 그대로(9점은 아니고 10점이면 Endgame) — 변형 이름의 11로 잘못 고치는 것을 막는다 | `tests/unit/rules/test_phases.py`(`test_go_to_11_still_enters_endgame_at_ten`) |
| codec·관측 | 카탈로그·인코딩 변화 없음. 새 필드가 모든 state hash를 바꾸므로 codec v120으로 올려 옛 저장 파일이 깔끔한 버전 오류를 받게 했다(v112 선례) | `test_go_to_11_leaves_the_action_catalog_alone` |
| 음수 방지 | VP를 잃는 곳은 `rules/influence.py`의 세 곳(Influence 2 → 1, Alliance 이전·반환)뿐이고 모두 앞선 +1을 되돌린다. `PlayerState`의 음수 검사가 안전망이다 | `test_a_go_to_11_game_finishes_from_zero`, sweep |
| 서버·저장 | `CreateGameRequest`·요약·저장 문서의 `go_to_11`(없으면 꺼짐). checkpoint·search 좌석도 허용한다(사용자 결정) | `tests/server/test_app.py`, `test_saves.py`, `test_sessions.py` |
| 브라우저 | 불멸 아래 체크박스(기본 체크, 불멸이 꺼지면 비활성·해제 — Tech와 같다), 머리글 배지 | `scripts/e2e/setup_options.py` |
| CLI | sweep·tournament `--go-to-11`(`--immortality` 없으면 `parser.error`) | `tests/integration/test_sweep.py`, `test_tournament.py` |

검증(2026-09-28): `--immortality --go-to-11 --soundness-interval 25` sweep 2,200판 실패 0 — random 800·heuristic 400(base·CHOAM), 전 확장 random 600, 전 확장 + leader draft heuristic 200, Bloodlines·Tech·Arrakeen Scouts random 200. 라운드 중앙값 10.

## 미완 경계

- 카드 play data·UI(스캔 오버레이 포함)·소크·census는 끝났고, 2026-09-09에 heuristic·rollout의 Immortality 가치도 넣었다(위 절). 남은 것은 학습(M10) 재개 시 관측 v18 체크포인트 새로 시작.
- `choose_research_influence`(c6r6의 "Influence 1 선택")는 여전히 네 진영이 같은 점수다. `score_action`은 상태를 보지 않으므로 어느 진영이 Alliance·VP에 가까운지 알 수 없다 — 진영 선택의 차등은 rollout·학습 정책의 몫으로 남긴다.
