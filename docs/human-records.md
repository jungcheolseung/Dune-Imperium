# 사람이 둔 판을 데이터로: 기보 이전

2026-10-10. 사용자 질문 "사람이 플레이했던 기록을 학습에 반영하기 위한 데이터로 쓸 수 있을까?"에서 시작했다. 답을 정리한 뒤 사용자가 고른 일은 둘이다. 하나는 진단이고([evaluation/human-games-2026-10-10.md](evaluation/human-games-2026-10-10.md)), 다른 하나가 이 문서의 "엔진이 바뀌어도 기보가 살아남게"다. 누가 뒀는지와 무르기 기록은 쓰지 않기로 했다. 누가 잘하는지 판단하기 어렵고, 물렀다가 같은 수를 다시 두기도 하기 때문이다.

- 코드: `src/dune_imperium/records/`(`migration.py`, `saves.py`), `src/dune_imperium/cli/records.py`(`dune-imperium-records`).
- 저장본을 읽는 쪽에는 `parse_save_document(..., check_versions=False)` 하나만 더했다. 서버의 불러오기는 그대로 버전이 정확히 같아야 한다.
- 테스트: `tests/unit/records/`, 옛 엔진 기보 `tests/unit/records/data/`(만드는 스크립트 `scripts/records/old_engine_record.py`).

## 1. 왜 깨지나

저장본은 수를 **뜻으로** 적는다. 행동이면 `action_id`·actor·인자, chance면 결정 id와 뽑힌 값이다. codec 행 번호는 적지 않는다. 그래서 codec 번호가 올라갔다는 것만으로 기보를 못 읽게 되지는 않는다.

깨지는 것은 **엔진의 흐름**이 바뀔 때다. 새 엔진이 옛 엔진은 묻지 않던 것을 물으면, 다음에 적힌 수가 엉뚱한 결정을 만난다. 2026-10-10 로컬 저장본 네 판 중 옛 두 판(v135, v139)이 2라운드의 discard shuffle에서 멈춘 까닭이 이것이다. v140의 공개 앞 멈춤(OQ-103)이 그 앞에 chance 결정을 하나 끼워 넣었다.

## 2. 다리(bridge)

`migrate_record`는 적힌 수를 차례로 둔다. 엔진이 어떤 수를 거절하면, 다리가 엔진이 기다리는 결정에 옛 엔진이 "묻지 않음으로써" 답한 대로 답한다. 그다음 적힌 수를 다시 둔다.

| 다리 | 적용 | 무엇을 | 근거 |
|---|---|---|---|
| `pause` | 모든 기보 | 멈춤(결과가 하나뿐인 chance)에 그 결과로 답한다 | 멈춤은 공개 사실로 정한 자리에 서고, 붙잡아 둔 단계는 그대로 돈다(`rules/pauses.py`). 선택도 뽑기도 없다 |
| `conflict_end_window` | codec 141 미만 | Conflict 끝 책략 창을 거절한다 | v141(`e7eef001`)부터 창이 공개 사실로 열린다. 옛 엔진은 낼 카드가 없는 좌석에게 묻지 않았다 |
| `combat_intrigue_pass` | codec 139 미만 | 전투 책략에 pass한다 | v139(`5654d7f8`)부터 카드를 낸 바로 뒤의 pass는 창을 닫는 데 세지 않는다. 그래서 옛 엔진이 이미 닫은 자리에서 한 번 더 묻는다 |
| `agent_card_effect_named` | codec 137 미만 | 적힌 수를 다시 쓴다 | v137(`752c39fe`, 앱 카드 대조)부터 Stillsuit Manufacturer의 Water처럼 한 번에 풀던 Agent 칸 일부가 `effect`를 단 아이콘으로 나뉘었다. 인자 없는 `resolve_agent_card_effect`를, 지금 내놓는 이름 붙은 아이콘이 **딱 하나**일 때만 그것으로 바꾼다. 둘 이상이면 어느 것인지 기보가 말하지 않으므로 멈춘다 |
| `imperial_privilege_draw` | codec 142 미만, **직후** | 회수 직후 `resolve_board_effect{effect: cards}` | v142(`4c7150d3`)부터 Imperial Privilege의 카드 뽑기가 회수와 따로 노는 보드 아이콘이다. 옛 엔진은 회수 세 가지(`recall_agent_for_imperial_privilege`, `recall_conflict_agent_for_imperial_privilege`, `resolve_imperial_privilege_without_recall`) 단계의 맨 끝에서 같은 출처로 뽑았다 |
| `garrison_unit_troop` | codec 142 미만 | `scouts_lose_garrison_unit{}`(병력) | v142(`0ef97fa1`, OQ-105)부터 Bene Gesserit Treachery의 유닛 비용을 garrison에 병력과 Commander가 함께 있으면 묻는다. 옛 엔진은 묻지 않고 병력을 냈다 |
| `prison_planet_commanders_only` | codec 142 미만 | `scouts_decline_mission` | 같은 커밋부터 Prison Planet에 Commander로 참가할 수 있다. 옛 엔진은 garrison에 Commander만 있는 좌석에게 묻지 않고 건너뛰었다. 거절은 아무것도 바꾸지 않는다 |
| `shigawire_draw` | codec 142 미만, **직후** | `resolve_agent_card_effect{effect: cards}`(더해진 카드) | v142(`6947f446`, OQ-106 1)부터 Urgent Shigawire가 더한 draw가 배치와 따로 논다. 옛 엔진은 부스트된 배치 단계의 맨 끝에서 뽑았다. 그 행동이 더해진 카드를 뽑을 때만(box 자신의 `cards`가 먼저가 아닐 때) 쓴다 |
| `planetologist_intrigue` | codec 142 미만, **직후** | `draw_planetologist_intrigue` | v142(`9e9fbd71`, OQ-106 3)부터 Arrakis Planetologist의 Intrigue 카드가 대체마다 trash frame 안의 단계다. 옛 엔진은 소환 단계에서 모두 뽑았다 |
| `intrigue_held_rewards` | codec 142 미만, **직후** | `resolve_intrigue_rewards` | v142(`21069cbd`, OQ-106 2)부터 Cunning·Insider Information의 trash(또는 거절) 뒤 draw가 따로 남는다. 옛 엔진은 trash 단계에서 뽑고 카드를 끝냈다 |
| `piter_reward` | codec 142 미만, **직후** | `resolve_agent_card_effect{effect: research\|cards}` | v142(`2f76372b`, OQ-106 4)부터 Piter, Genius Advisor의 보상이 troop 비용과 따로 논다. 옛 엔진은 `lose_agent_card_troop` 안에서 Research 뒤 두 장을 뽑았다. 곧바로 끝나는 Research면 Research 먼저, 묻는 Research면 카드 먼저(옛 엔진은 방향을 묻기 전에 뽑았다) |
| `reverse_engineering_reward` | codec 142 미만, **직후** | `resolve_agent_card_effect{effect: intrigue\|cards}` | 같은 커밋부터 Kota Odax의 Reverse Engineering도 Tech tile 비용과 보상이 따로 논다. 옛 엔진은 `trash_leader_tech` 안에서 Intrigue, 카드 순으로 뽑았다 |
| `scouts_held_draw` | codec 142 미만, **직후** | `scouts_rewards_first` | v142(`2626df03`, OQ-106 10·11)부터 Scouts 줄의 보상 선택 뒤 draw가 줄의 단계로 남는다. 옛 엔진은 선택 단계에서 뽑았다 |
| `scouts_reward_pause` | codec 142 미만, **직후** | 멈춤의 한 결과 | v142(`aa600ee0`, OQ-106 12)부터 봉인 경매의 두 번째 이후 승자 보상 앞에 멈춤이 선다. 옛 엔진은 앞 승자를 끝낸 단계 안에서 다음 승자의 보상까지 줬다. `pause`도 답하지만 거절될 때만이라, 그 자리에서 끝나는 기보가 옛 상태로 끝나도록 바로 답한다 |
| `owed_draw` | codec 142 미만, **직후** | `draw_owed_intrigue`·`draw_owed_card` | v142(`6ec211d8`, `43fa4fa7`, OQ-106 5~8)부터 자기 turn 안에서 촉발된 draw(BG 4, Imperial Birthright, Tleilaxu track Intrigue, Sardaukar Soldier, Overthrow, Hungry for Spice)가 소유자의 단계로 남는다. 옛 엔진은 촉발한 단계 안에서 뽑았다 |
| `unpredictable_foe_draw` | codec 142 미만, **직후** | `draw_reveal_intrigue` | v142(`f8f7e080`, OQ-106 9)부터 Muad'Dib의 Unpredictable Foe 카드가 Reveal의 대기 목록에 들어간다. 옛 엔진은 조건을 처음 채운 단계에서 뽑았다. 부여 한 번에 한 번만(`draw_reveal_intrigue`가 가장 오래된 항목을 가져가므로) |
| `reshuffle_renamed` | codec 142 미만 | 적힌 reshuffle을 다시 쓴다 | 위 분리로 일부 draw의 출처 이름이 바뀌어(Piter `agent_card_payment` → `agent_card:<카드>:cards`·`:research`, Reverse Engineering `leader_signet:cards`, Shigawire `shigawire:<카드>:cards`, Cunning `:rewards:draw`) reshuffle id도 바뀌었다. 같은 라운드·같은 좌석의 **개인 덱** reshuffle이고 적힌 값이 지금 버림 더미와 정확히 같은(multiset) 때만 지금의 id로 바꾸고 순서는 그대로 둔다. Intrigue reshuffle은 바꾸지 않는다 |
| `refinish_agent_turn` | codec 142 미만 | `finish_agent_turn`을 한 번 더 | turn 종료 누름 자체(Usurp trash 등)가 번 draw를 v142는 붙잡아 turn을 다시 연다. 옛 엔진은 누름 안에서 뽑고 turn을 닫았다. `owed_draw`가 뽑은 뒤, 다음 적힌 수(다른 좌석의 것)가 거절되면 다시 누른다. 다시 열린 까닭이 그 draw뿐이고 누름이 turn을 닫을 때만 |
| `graft_switch`·`graft_box` | codec 143 미만 | 적힌 `switch_graft_card`를 지우고, 짝(칸 1)이 활성이던 동안의 칸 행동에 `box=1`을 붙인다 | v143([graft-boxes-plan.md](graft-boxes-plan.md))부터 graft한 Agent turn의 두 칸을 처음부터 함께 제시한다. 옛 엔진은 한 번에 한 칸만 풀었고 `switch_graft_card`로 다른 칸을 활성으로 바꿨다. 다른 다리와 달리 기보를 따라가며 옛 엔진의 활성 칸을 기억한다(`_GraftSlot`): `agent_turn`·`choose_graft_partner`에서 칸 0, switch마다 뒤집기, `finish_agent_turn` 뒤에는 그 누름이 남긴 칸(옛 엔진의 turn 종료도 대기 중인 짝 칸으로 바꿨고 이 엔진도 같다). 칸 1이 활성인 동안 적힌 칸 행동은 `box=1`을 붙인 행이 합법일 때 그것으로 바꾼다. 그 칸의 장치가 내지 않는 수는 turn의 다른 효과라 그대로 둔다. 그 칸의 수인데 이 엔진이 다른 칸의 묶음 선택(계획 4.3의 잠금) 때문에 그 칸 행을 숨기는 자리면 그 수에서 `Divergence`로 멈춘다(`graft_box_held`; 칸 0이 활성이던 수도 같다). 그대로 적용하면 다른 칸의 행이나 칸 없는 행으로 읽혀 다른 수가 되기 때문이다. 예: Piter의 troop을 낸 뒤 switch해 적힌 Tleilaxu Infiltrator의 `effect=cards`는 이 엔진에서 Piter의 두 장 보상이다. 칸 1이 활성인 동안의 `effect=cards`: 옛 엔진은 활성 칸의 아이콘이 먼저였으므로 칸 1이 그 아이콘을 내면 `box=1`이다. 칸 1에 그 아이콘이 없으면 옛 엔진에서는 Urgent Shigawire의 추가 draw였다. 이 엔진에서 태그 없는 같은 행은 칸 0이 자기 draw 아이콘을 아직 내면 칸 0의 아이콘을 해결한다. 뽑는 장수는 같고, 남는 것이 칸 0의 아이콘 대신 추가 draw일 뿐이다(나중에 적힌 칸 0의 `effect=cards`가 그 추가 draw가 된다) |
| `shigawire_partner_draw` | codec 144 미만 | 적힌 `finish_agent_turn` 바로 앞에 `resolve_agent_card_effect{box: 1, effect: cards}` | v144([OQ-107](rules/open-questions.md), 사용자 판정 "1. 짝도 받음")부터 Urgent Shigawire의 부스트가 남았을 때 graft 상대인 Bene Gesserit 카드가 부스트를 받고, 그 box(칸 1)에 더해진 draw가 turn 종료를 막는다. 옛 엔진은 상대에게 아무것도 주지 않았으므로 기보에 그 draw가 없다. turn 안의 적힌 수가 옛 엔진이 보인 손패를 그대로 보도록 가장 늦은 자리, 턴 종료 누름이 거절될 때 그 앞에서 뽑는다 |
| `box_refused_at_turn_end` | codec 144 미만 | 적힌 `finish_agent_turn` 바로 앞에 그 box의 거절(`decline_agent_card_payment`·`decline_agent_card_acquisition`, 칸 1이면 `box=1`) | v144(OQ-057 (1) 보강, 사용자 지시 "2. 고치자")부터 효과를 주는 선택을 아직 제시하는 Agent box가 턴 종료를 막는다. 옛 엔진은 Piter·Tleilaxu Surgeon·Dissecting Kit의 낼 수 있는 화살표와 Tleilaxu Master의 획득 곁에 턴 종료를 내놓았고(dry run의 오판), 누름이 box를 불발시켰다 — 거절과 같은 결과다("You do not have to pay such a cost on a card" `[Main p. 20]`). 의무 box(Stitched Horror의 "Choose two", Beguiling Pheromones의 trash)에는 거절이 없으므로 답하지 않는다 v146부터는 답하지 않는다: 그 칸들은 선택 효과라 턴 종료를 막지 않고, 적힌 누름이 그대로 칸을 사라지게 한다 |
| `boost_draw_at_turn_end` | codec 145 미만 | 적힌 `finish_agent_turn` 바로 앞에 남은 Urgent Shigawire draw(`resolve_agent_card_effect{effect: cards}`, 칸 1이면 `box: 1`) | v145에서 옛 엔진에 없던 더해진 draw가 둘 생겼다. ① 부스트를 받은 카드와 graft한 Ghola의 복사 box의 draw([OQ-107](rules/open-questions.md), 사용자 판정 "그래 고치자", "copies the entire Agent box" `[Immortality p. 14]`). ② Throne Room Politics처럼 자기 선택 trash 아이콘으로 자신을 trash한 카드의 draw(OQ-022 2026-10-12 보강; 옛 엔진은 지웠다). 둘 다 turn 종료를 막으므로 `shigawire_partner_draw`와 같은 이유로 턴 종료 누름이 거절될 때 그 앞에서 뽑는다. Ghola의 draw나 play에 없는 카드의 draw에만 답한다. `shigawire_draw`와 `shigawire_partner_draw`는 Ghola의 복사 draw를 건드리지 않는다 |
| `optional_refusal`(지움) | codec 146 미만 | 적힌 선택 효과 거절을 **지운다**(다리가 아니라 `dropped`에 `optional_refusal`로 남는다) | v146(사용자 판정 2026-10-14, OQ-095 (2) 보강)부터 Agent turn의 선택 효과("may", 화살표 비용, 검은 trash 아이콘 `[FAQ p. 3]`)는 거절 없이 제시되고, 쓰지 않으면 턴 종료 누름이 사라지게 한다. 옛 엔진의 거절(`decline_agent_card_*`, `decline_corrinth_city_payment`, `decline_imperial_privilege_intrigue`, `resolve_desert_tactics_without_trash`, `decline_sardaukar_commander`, `decline_tech`, `decline_subcommittee`, `decline_leader_board_repeat`, `decline_leader_signet_payment`, `decline_leader_card_trash`, `decline_other_memories`)은 짝이 없다: 이 엔진에서는 그 효과가 대기로 남았다가 적힌 `finish_agent_turn`에서 사라지므로 게임 상태가 같다. 엔진이 그 수를 거절하고 다른 다리도 답하지 않을 때만 지운다(접합한 다른 칸이 기다리는 동안 진행 중인 선택 효과의 거절처럼 이 엔진도 아직 내는 거절은 그대로 둔다). codec 149 미만의 `turn_row_refusal`(지움)도 같다: v149(정리-2b)부터 소유자 자신의 turn 안에서 얻은 선택 trash·research 보너스는 turn의 줄로 기다리고 거절이 없으므로 `decline_optional_trash`·`decline_research_bonus`를 지운다(turn 밖에서는 창과 거절이 남아 그대로 둔다). 둘 다 `migration.lapsed_refusal`이 가린다. 문제집에서 이 거절이 무엇이 되는지는 4절 |
| `repeated_mission_collection`(지움) | codec 146 미만 | 적힌 빈 `scouts_collect_mission`을 **지운다**(`dropped`에 남는다) | v146(사용자 판정 2026-10-14, OQ-019 보강)부터 Reverend Mother의 반복은 Arrakeen Scouts 임무 조각 받기를 다시 걸지 않는다. 옛 엔진은 걸었지만 조각은 반복 전에 모두 받았으므로 그 둘째 받기는 아무것도 가져가지 않았다. 지금 엔진이 그 수를 거부하면 지운다. |
| `reveal_choice_defer`·`reveal_choice_resume`·`reveal_optional_refusal`(지움)·`reveal_source`·`reveal_source_by_order` | codec 147 미만 | 적힌 `defer_reveal_choice`·`resume_reveal_choice`와 선택 Reveal 효과의 거절(`decline_reveal_card_trash`·`decline_reveal_influence_exchange`·`decline_reveal_influence_loss`·`decline_reveal_spice_influence`·`decline_reveal_troop_move`·`decline_reveal_troop_retreat`·`decline_reveal_troop_sacrifice`·`decline_command_acquisition`, 선택 회수(Spy Network·In High Places·Arrakis Observer)의 `decline_reveal_spy_recall`)를 **지우고**, `source`를 다는 열한 id(`trash_reveal_card`·`recall_spy_for_reveal`·`retreat_two_troops_for_reveal`·`place_reveal_spy`·`recall_spy_for_reveal_placement`·`keep_contract_reveal_spice`·`trash_contract_reveal_for_vp`·`gain_reveal_influence`·`deploy_reveal_card_troop`·`retreat_reveal_card_troop`·`decline_reveal_spy_recall`)의 적힌 수에 카드를 단다 | v147(사용자 판정 2026-10-14 "그래 그 구조로 진행하자", OQ-095 (7) 보강)부터 Reveal 선택 효과는 카드별 창 없이 Reveal frame의 대기 목록에서 구매·이득과 함께 제시되고, 선택 효과는 거절 없이 쓰지 않으면 `finish_reveal`에서 사라진다. 옛 엔진의 미루기·되가져오기·거절은 짝이 없어 지운다(게임 상태가 같다). 그 id를 지금 내는 카드가 하나면 그 카드(`reveal_source`), 여럿이면 옛 엔진이 맨 위에 둔 선택 창의 카드(`reveal_source_by_order`)를 단다. 옛 엔진의 창 순서를 기보를 따라가며 기억한다(`_RevealSlot`): 시작 때 조건이 맞는 선택은 손패 순서로 창(첫 카드가 맨 위), 나머지는 대기열; 미루기는 맨 위를 대기열 끝으로, 되가져오기는 그 종류의 지금 가능한 가장 오래된 항목을 맨 위로; 늦게 공개된 카드의 창은 Reveal frame 바로 위로. 선택 회수의 `decline_reveal_spy_recall`을 이 엔진이 빈 supply의 일반 Spy 아이콘 거절로 받을 수 있는 자리면 그 창 순서로 지운다(`reveal_optional_refusal_by_order`). 일반 Spy 아이콘의 거절은 그 창의 카드를 단다(`records.problems`의 망 수도 같다: 옛 맨 위 창이 선택 회수였으면 짝이 없다). 이 엔진은 다른 효과가 trash한 카드의 선택을 제시하지 않으므로(OQ-022) 그런 선택을 쓴 옛 기보는 그 수에서 갈라진다 |
| `conspiracy_icon`·`conspiracy_spice`(**직후**) | codec 152 미만 | 인자 없는 해결을 `resolve_agent_card_effect{effect: spice}`로 바꾸고, Faction 선택 직후 그 spice를 더한다 | v152(엔진 감사 2026-10-22 P4, OQ-027 보강 3)부터 Interstellar Conspiracy의 spice와 Influence가 아이콘 둘이다. 옛 엔진은 Emperor·Spacing Guild 짝이 없으면 spice만 주는 해결을, 있으면 spice까지 주는 Faction 선택만 내놓았다. 칸 1·Ghola 복사도 그 칸으로 |
| `breakthrough_research`(**직후**) | codec 152 미만 | trash 직후 `resolve_agent_card_effect`(남은 Research) | v152(P5, OQ-106)부터 Scientific Breakthrough가 먼저 자신을 trash하면 아직 하지 않은 Research가 소유자의 다음 단계다. 옛 엔진은 trash 단계 안에서 Research를 했다 |
| `guild_envoy_draw`(**직후**) | codec 152 미만 | Spacing Guild 카드 버림 직후 `resolve_agent_card_effect{effect: cards}` | v152(P6, OQ-106, 사용자 결정 2026-10-25 "(가) discard와 draw를 별개 단계로")부터 Guild Envoy의 두 장이 버림 뒤 따로 무장된 아이콘이다. 옛 엔진은 버림 단계에서 뽑았다 |
| `overthrow_for_space`·`overthrow_deferred`(지움)·`overthrow_with_the_space`(지움) | codec 152 미만 | 두 몫 가운데 하나를 Overthrow 칸의 해결(2)로 삼고 다른 하나를 **지운다** | v152(OQ-128, 사용자 판정 2026-10-25)부터 Overthrow의 "Gain two Influence instead of one."이 방문한 Faction 칸의 1을 대신한다. 옛 엔진은 칸의 1과 카드의 +1을 두 단계로 줬다. **같은 Agent turn에 두 몫이 모두 적혔을 때만** 다룬다(뒤를 내다본다, `_overthrow_plan`). 영향력 트랙 보상(2·4)이 옛 판과 같은 수에서 나오도록, 첫 몫 앞의 그 Faction 영향력이 홀수면 첫 몫에서(칸의 수는 Overthrow 칸으로 바꾼다), 짝수면 둘째 몫에서 2를 얻고 다른 몫은 지운다. 두 몫 사이에 그 카드를 이름으로 부르는 수(trash 등)나 접합 상대를 trash하는 수(Dissecting Kit, Beguiling Pheromones)가 있으면 첫 몫에서 얻는다 — 미루면 칸이 먼저 사라질 수 있다. 둘째 몫이 적히지 않았으면(옛 엔진이 카드가 먼저 trash돼 칸을 소멸시킨 판, OQ-022) 다루지 않는다: 이 엔진이 칸 뒤에 붙잡아 둔 칸의 수가 거절되어 그 자리에서 멈춘다(얻지 않은 2를 얻게 하지 않는다). 지우기 `overthrow_with_the_space`는 칸이 이미 해결된 Overthrow일 때만이다(Subversive Advisor 등 다른 카드의 "instead"는 아니다). v143 전 기보는 그 엔진이 활성으로 두던 접합 칸(`_GraftSlot`)대로 태그를 붙여 읽는다. 알려진 차이: 두 몫 사이에 다른 효과가 그 영향력을 바꾼 판(v151 묶음 2,000판 중 1판)과, 홀수 영향력에서 Alliance가 넘어가는 시점(첫 몫에서 넘어간다; 그 사이의 수가 Alliance 조건을 볼 때만 결과가 갈린다). 그 2가 일으킨 Navigation 카드 draw의 reshuffle id는 `navigation_reshuffle_renamed`가 같은 좌석·같은 더미·같은 Faction일 때만 바꾼다 |
| `mission_pass_alone` | codec 152 미만, **적힌 수 앞** | `scouts_decline_mission` | v152(OQ-131, 엔진 감사 G4)부터 Scouts 임무에 참가할 수 없는 좌석에게도 pass 하나만 있는 창을 연다. 옛 엔진은 묻지 않고 건너뛰었다(OQ-088). 그런 창은 기보가 답한 적이 없으므로 다음 적힌 수를 보기 전에 늘 pass로 넘긴다 — 그 좌석이 적은 pass는 뒤의 다른 임무의 것이다(`_pass_missions_alone`) |
| `equilibrium_alone` | codec 152 미만, **적힌 수 앞** | Political Equilibrium 창의 한 줄(`scouts_lose_influence`, 또는 모든 진영이 0이면 `resolve_scouts_loss_without_influence`) | v152(OQ-131 보강, 사용자 결정 2026-10-25 "모든 좌석에 창을 열어")부터 Political Equilibrium이 모든 좌석에 창을 연다. 옛 엔진은 가장 높은 진영이 하나인 좌석의 손실을 스스로 처리하고 모든 진영이 0인 좌석은 건너뛰었다(동률은 그때도 물었다). 한 줄짜리 창은 기보가 답한 적이 없으므로 다음 적힌 수를 보기 전에 그 줄로 답한다(`_answer_windows_never_asked`, `mission_pass_alone`과 같은 자리) |
| `scouts_pass_without_option` | codec 152 미만 | 적힌 `scouts_pass`를 "고를 것 없음" 확인으로 바꾼다 | v152(P2, OQ-071)부터 보상이 아무것도 바꾸지 못하는 Scouts 비용 줄을 내놓지 않는다. 옛 엔진이 내놓던 줄이 모두 빠진 자리에서 적힌 pass는 확인 하나와 같은 결과다. 그 줄을 골랐던 수는 짝이 없어 갈라진다(아래) |
| `scouts_faction_alone` | codec 153 미만, **적힌 수 앞** | 한 줄짜리 Faction 창의 그 줄(`scouts_choose_faction`) | v153(일반 규칙 감사 2026-10-25, 사용자 결정 2026-10-26 "Leverage는 OQ-111 (2)")부터 Scouts 줄의 "원하는 Faction" 단계(Leverage·Relations·Share Intelligence·Ingratiate)가 꼭대기 아래 진영이 하나뿐이어도 창을 연다(OQ-111 (2) "대상이 하나뿐이어도 둘째 단계를 연다"). 옛 엔진은 그 진영을 스스로 골랐다. 한 줄짜리 창은 기보가 답한 적이 없으므로 다음 적힌 수를 보기 전에 그 줄로 답한다(`_answer_windows_never_asked`, `equilibrium_alone`과 같은 자리) |
| `scouts_faction_alone_draw` | codec 153 미만, **적힌 수 앞** | `scouts_rewards_first` | 위 다리가 답한 Leverage 줄에서, 옛 엔진은 Faction과 함께 그 뒤 Intrigue 1장도 같은 단계에서 뽑았다(줄의 보상 선택이 없었으니 뽑기를 붙잡지 않았다, OQ-106). v153은 고른 Faction 뒤 뽑기를 줄의 단계로 남기므로 바로 이어 답한다. 줄의 앞 보상이 이미 선택이었으면 그때도 뽑기가 따로 남았으므로 기보의 것이다 |

- **안전장치:** 다리는 적힌 수가 **바로 그 결정의 답**일 때는 끼어들지 않는다(`_made_for`). 결정을 가진 좌석이 둔 수가 다음 중 하나이면 그 결정의 답으로 본다.
  - 그 틀(frame)이 답으로 받는 `action_id`다. 전투 책략은 pass·`play_intrigue`, Conflict 끝 창은 거절·`play_conflict_end_intrigue`다.
  - 지금 그 결정이 내놓는 `action_id`다.
  - 첫째 조건은 규칙 변경으로 그 종류의 행동이 **모두** 사라진 경우를 위한 것이다(독립 리뷰가 찾은 빈틈).
- **직후 다리(`follows`).** 대부분의 다리는 적힌 수가 거절될 때 끼어든다. 그런데 새 엔진이 한 단계를 둘로 나눈 경우(Imperial Privilege)는 그때 끼우면 늦다.
  - 그 사이에 적힌 수들은 옛 판에서 이미 뽑은 카드를 보고 둔 것이다. 실제로 그 카드를 Insider Information으로 버린 판이 있었다.
  - 다른 뽑기의 reshuffle id도 어긋난다.
  - 그래서 `follows` 다리는 적힌 수가 적용된 **직후**, 옛 엔진이 그 일을 한 바로 그 순간에 나머지를 적용한다. 거절될 때는 쓰지 않는다.
  - 한 수 뒤에 여럿이 따라올 수 있다(Piter의 보상 둘, Scouts 줄 draw 뒤에야 제시되는 BG 4 카드, 연이은 경매 멈춤 셋). 그래서 `follows` 다리를 `BRIDGES` 순서로 처음부터 다시 묻고, 하나가 답하면 적용한 뒤 또 처음부터 묻는다. 아무도 답하지 않을 때 멈춘다(고정점). `BRIDGES` 순서는 옛 엔진이 그 단계 안에서 한 순서다: 그 수 자신의 draw, 그다음 hook의 draw(Hungry for Spice, 그다음 Reveal 수동 능력). 한 수 뒤에 32번을 넘게 답하면 서로 주고받는 다리로 보고 그 수에서 `Divergence`로 멈춘다.
- **다리 없이 갈라짐이 맞는 v142 변경**(독립 조사·반박 검증):
  - Navigation Chamber 할인 의무화(`4870efd5`): 옛 기보가 할인 없이 낸 수는 지금 불법이다. 할인된 수로 바꾸면 자원이 달라진다.
  - Bene Gesserit Treachery에서 garrison에 Commander만 있고 BG 영향력이 0인 좌석: 옛 엔진은 건너뛰었다. v142는 Commander를 잃는 선택지 하나를 강제한다. 강제 수로 이으면 그 Commander를 나중에 쓰는 적힌 수에서 반드시 다시 갈라진다(13개 기보 모두).
- **다리 없이 갈라지는 v143(graft 두 칸) 경우**(v142 묶음 2,000판 중 4판, 2026-10-12):
  - Ghola + Stitched Horror(1판): 옛 엔진은 두 번째 칸에 남은 보상 둘만 내고 한 번 고르면 끝냈고, 첫 칸의 보상을 다시 줬다. v143은 칸마다 둘을 고른다(OQ-057 (12) 보강, 규칙 수정). 적힌 다음 수(그 보상 병력의 배치)가 불법이 된다.
  - 잠금([graft-boxes-plan.md](graft-boxes-plan.md) 4.3)이 막는 순서(3판): 옛 엔진은 한 칸의 묶음 선택 도중에도 `switch_graft_card`로 다른 칸에 갈 수 있었다. The Beast's Spoils의 남은 trash를 두고 Dissecting Kit 칸으로 간 판 1, Signet Ring 칸의 Spy 회수 뒤 배치 전 1, Staban Tuek Signet의 Spy 배치 뒤 지불 전 1. 새 엔진은 그 칸의 묶음이 끝날 때까지 다른 칸 행을 숨기므로 적힌 다른 칸의 수가 불법이 된다. 적힌 수의 순서를 바꾸는 다리는 두지 않았다.
- **다리 없이 갈라지는 v144 경우**(2026-10-12):
  - 의무 box를 남긴 채 누른 턴 종료: Beguiling Pheromones(Faction space에서 grafted 카드 하나를 trash하고 Influence 1)나 Stitched Horror의 "Choose two"가 남아 있는데 옛 엔진이 턴 종료를 내놓아 누름이 그 효과를 건너뛰었다. v144는 그 효과를 끝내야 턴 종료를 내놓는다(OQ-057 (1) 보강, 규칙 수정). 적힌 누름이 불법이 된다.
  - Bene Gesserit 상대가 받은 부스트의 뒤끝: `shigawire_partner_draw`가 뽑은 카드는 옛 기보의 손패에 없던 카드라, 그 카드에 대한 선택이 뒤에 필요하면(예: Reveal에서 그 카드의 표본 만들기) 적힌 수가 그 선택을 만나 갈라진다. 옛 엔진이 남겨 둔 부스트를 같은 라운드의 뒤 Bene Gesserit 카드가 쓴 기보도 그 수(모든 아이콘으로 닿은 배치나 더해진 draw)에서 갈라진다.
- **다리 없이 갈라지는 v152 경우**(엔진 감사 2026-10-22 수정, v151 묶음 2,000판 중 43판, 2026-10-25). 규칙을 바로잡아 옛 수가 이제 불법이거나 판의 흐름이 달라진 것이라 다리로 잇지 않는다.
  - 라운드 첫 turn의 turn 카운터 초기화(R1)·Shaddam의 Servo-Receivers 뒤 배치 금지: 옛 엔진이 허용한 배치 수(병력 4, Commander)가 이제 한도를 넘는다(12판).
  - 보상이 아무것도 바꾸지 못하는 Scouts 비용 줄(P2): 그 줄을 고른 수는 이제 없다(8판).
  - 다른 효과가 trash한 카드의 대기 trash(P1): 옛 엔진은 Dissecting Kit·Spy Drones가 trash한 Control the Spice·Stitched Horror의 trash를 그대로 썼다(2판).
  - Emperor's Schemes의 Intrigue가 Suspensor Suits를 세는 것(P3), 배치 없는 turn의 임무 병력이 garrison으로 가는 것(G3): Conflict의 병력이 달라져 보상 순서가 바뀐다(약 10판).
  - 배치 A의 나머지(R1~R3의 reshuffle 장수, Reveal 중 늦은 카드): A 묶음 관문에서 확인한 판들.
  - Overthrow 두 몫 사이에 영향력이 바뀐 판(1판, 위 `overthrow_*`).
- **OQ-106 분리 가운데 다리로 잇지 못하는 경우**(독립 조사·반박 검증, 2026-10-10). 엔진은 바꾸지 않았다.
  - Urgent Shigawire: 옛 엔진이 부스트된 배치 바로 뒤에 reshuffle을 적었는데, v142에서 먼저 답할 것(Gather Intelligence, graft 상대, box 자신의 `cards` 아이콘)이 있으면 그 자리에 기다리는 draw가 없다. box 아이콘을 미리 뽑는 다리는 기보가 그 아이콘을 끝내 쓰지 않으면(trash로 소멸) 멈추므로 두지 않았다. 1,563판 중 5판(Gather Intelligence 2, box 아이콘 3).
  - Cunning·Insider Information이 Sardaukar Standard를 trash하고 그 draw가 reshuffle하는 경우: 옛 엔진은 reshuffle 뒤 Skill 선택을 열었고, v142는 붙잡은 Intrigue 선택 위에 Skill 선택을 먼저 연다. 적힌 chance가 Skill 선택을 만나 멈춘다. 1,563판에는 없고, 같은 판에서 다른 trash를 고른 v141 기보 셋으로 재현됐다. reshuffle이 없으면 draw가 `choose_skill` 뒤로 한 수 늦을 뿐이다(2판). 엔진 순서는 바꾸지 않는다(2026-10-10 엔진 세션 결정 (b)): "trash될 때" 촉발의 Skill 선택은 공개 정보만으로 하는 선택이라 숨은 draw보다 먼저 오는 것이 OQ-106 원칙에 맞고, 옛 기보를 맞추려고 플레이어가 보는 순서를 바꾸지 않는다.
  - Muad'Dib의 Unpredictable Foe 카드가 Reveal 선택 아래에서 기다리는 동안 그 선택이 그 카드를 쓰는 경우(Intrigue를 trash하는 Immediate Contract): 1판.
  - 아직 어느 기보에도 없는 Intrigue reshuffle(Piter의 Research가 닿은 Tleilaxu Intrigue, 빈 Intrigue 덱의 Reverse Engineering, BG 4 카드, Planetologist): id가 새 출처를 따르는데 `reshuffle_renamed`는 개인 덱 reshuffle만 바꾼다.
- **한두 수 늦는 draw**(멈추지 않고 그 사이의 수가 카드 한 장 모자란 손을 본다). 엔진이 그 틀에서 draw를 내놓지 않기 때문이다.
  - Deep Desert의 두 번째 Planetologist 카드: 첫 trash 답 한 수(267곳).
  - Gather Intelligence·graft 상대 뒤의 Shigawire 카드 한 수, box 아이콘 먼저인 경우 기보의 box draw까지 1~7수.
  - Reveal 선택 아래의 Foe 카드 1~3수, Intrigue 효과·Reveal·Skill·Scouts 선택 안에서 촉발된 owed draw 1~3수.
- **codec 번호 한 개에 흐름 변경이 여럿.** v142에는 Navigation Chamber, Imperial Privilege, OQ-105가 들어 있고 OQ-106 분리도 들어갈 예정이다(다른 세션과 합의, 2026-10-10).
  - 문턱은 master가 지나온 번호다. master에서 만든 저장본은 v141 다음이 바로 이 묶음 전체의 v142다.
  - 그 사이의 브랜치 엔진이 쓴 v142 저장본(테스트 산출물뿐)은 지원하지 않는다.
- **다시 쓰기는 일반 규칙으로 두지 않는다.** 이 엔진에서는 인자가 없다는 것 자체가 선택이다. `graft`가 없으면 카드 한 장, `discount`·`infiltrate_post_id`·`commanders`가 없으면 그것을 쓰지 않은 것이다.
  - 처음에는 "같은 id에 인자만 늘어난 행동이 하나면 그것으로"라는 일반 규칙을 두었다. 독립 리뷰가 그 규칙이 불법이 된 수를 다른 선택으로 바꿔 끝까지 옮기는 경우를 재현했다.
  - 그래서 행동 하나·인자 하나·codec 문턱이 정해진 다리로 좁혔다.
- 그러니 규칙이 바뀌어 사람이 둔 수가 불법이 되면, 그 자리를 건너뛰지 않고 `Divergence`로 멈춘다. 그 앞까지의 수는 그대로 쓸 수 있다.
  - 실제 예: v135 AI 기보 10개 중 4개가 여기서 멈췄다. 적힌 Insider Information(선택지 1) play와 전투 책략 Battlefield Research를 지금 엔진은 그 자리에서 내놓지 않는다. v136~v139 사이의 규칙·카드 대조 변경 때문이다(어느 변경인지는 따로 가리지 않았다).
- **새 다리를 더할 때:** 엔진 변경으로 기보가 멈추면 `dune-imperium-records check`가 적힌 수와 엔진이 기다리는 결정을 함께 보여 준다.
  - 새 엔진이 옛 엔진은 묻지 않던 것을 묻기만 한다면, 흐름을 바꾼 codec 버전으로 막은 다리를 더한다. 그리고 옛 엔진 기보로 지킨다(3절).
  - 적힌 선택 자체가 불법이 되었다면 멈추는 것이 맞는 답이다.

## 3. 검증 — 옛 엔진과 한 수씩 대조

옮긴 판이 "같은 판"인지는 옛 코드로 확인했다. 기보를 쓴 날 master의 커밋(v135 `37727846`, v139 `5a2dfc19`, v140 `6b033158`)을 git worktree로 꺼내고(v141은 master `21eccca4`의 메인 체크아웃), 그 엔진으로 기보를 그대로 재생했다. 최종 해시는 모두 일치했다. 그리고 적힌 수마다 공개 상태를 비교했다. 비교한 것은 좌석별 VP·자원·영향력·병력·Spy·Alliance·Control·Agent 위치·손패·덱 크기다.

| 기보 | 수 | 옛 엔진과 다른 수 |
|---|---|---|
| 사람 판 v139(사람 1 + 앱 AI 3, R2) | 123 | 0 |
| 사람 판 v135(사람 2 + rollout_strong 2, R7) | 759 | 8 |
| AI 판 v139 10개(heuristic·app_ai 각 5, 3라운드) | 각 233~269 | 모두 0 |
| AI 판 v140 3개(heuristic, 3라운드) | 각 261~277 | 모두 0 |
| AI 판 v135 6개(멈추지 않은 것) | 각 233~267 | 1~5 |
| v142 엔진(`f1e17be0` + 다리)으로 옮긴 v141 AI 판 7개(IP 1~2회 2개, garrison 1~2회 3개, Prison Planet 1회 1개, Prison Planet을 병력·Commander 둘 다 가진 좌석이 병력으로 참가 1개; 2~9라운드) | 각 160~873 | 모두 0 |
| v142 엔진으로 옮긴 사람 판 4개(v135·v139·v141 ×2) | 123~1,202 | 모두 0(v141 엔진으로 옮긴 판과 대조) |

넓은 대조도 했다(2026-10-10). 리뷰 워크플로가 만든 v141 AI 기보 1,563판이다. 무작위·heuristic·앱 AI가 두었고, 모듈 조합은 전부 켬, Immortality 끔, Epic 끔, Tech 끔을 섞었다.
- 매 수 모든 좌석의 모든 필드(`PlayerState` 83개, 카드 영역 전부, 순서 없는 영역은 정렬)를 짧은 해시로만 남겨 v141과 v142(다리 포함)를 맞댔다. 처음에는 필드 몇 개와 손패·덱 크기만 비교했고, 이렇게 넓혀 다시 돌렸다.
- 1,422판은 끝까지 옮겨졌다. 다리는 IP 1,161회, garrison 92회, Prison Planet 3회 쓰였다.
- 141판은 갈라졌는데 모두 다리를 두지 않기로 한 두 경우다.
  - 140판: Navigation Chamber를 가진 좌석이 할인 없이 둔 Agent 턴
  - 1판: Commander만 있고 BG 영향력이 0인 좌석에게 강제된 Treachery
- 갈라지기 전까지 비교한 1,489,233수 가운데 다른 수는 0이다.

OQ-106 분리(codec v142에 함께 들어감)와 그 다리를 넣은 뒤 같은 1,563판과 사람 판을 다시 대조했다(2026-10-10, 같은 해시).
- 1,417판은 끝까지 옮겨졌다. 146판이 갈라졌다: Navigation Chamber 139, Treachery 1(위의 두 경우), Urgent Shigawire 5(배치 바로 뒤에 적힌 reshuffle), Unpredictable Foe 1(Reveal 선택이 그 카드를 씀). 모두 2절의 다리로 잇지 못하는 경우다.
- 갈라지기 전까지 비교한 1,487,504수 가운데 다른 수는 505다. 모두 2절의 "한두 수 늦는 draw"다: Deep Desert 267, Shigawire 93(한 수 37곳, box 아이콘 먼저인 연속 1~7수), Foe 78(1~3수), owed draw 65(1~3수), Sardaukar Standard 뒤 `choose_skill` 2.
- 다리 쓰임: owed draw 3,831, IP 2,572, 경매 멈춤 1,805, Scouts 줄 1,536, Cunning·Insider 961, Planetologist 897, Piter 368, Foe 284, Shigawire 273, reshuffle 이름 170, Reverse Engineering 148, garrison 124, Prison Planet 3.
- 사람 판 7개(4판)는 모두 끝까지 옮겨졌다. 세 판은 모든 수가 v141과 같다. v141 판 8124f5a2/fb716981은 929 한 수가 다르다. 겹친 Reveal 선택 안에서 닿은 BG 4 카드가 다음 선택이 닫힐 때까지 기다린다.

즉시 owed draw(fb-immediate)까지 넣은 `34aecd31`을 기보 corpus(v141 AI 판 2,000개, `local/records-corpus/v141-a61acb7e`)로 대조했다(2026-10-10, `dune-imperium-records corpus check`, `--around 'draws:*'`, 다리 15개 검토).
- exact 6, equal 639, transient 1,046, persistent 0, diverged 309, failed 0.
- 갈라진 309판은 모두 다리를 두지 않기로 한 경우다: Navigation Chamber를 할인 없이 둔 Agent 턴 298, Commander만 있는 Treachery 8, Shigawire(Gather Intelligence나 box 아이콘이 먼저, reshuffle) 3.
- 상태가 다른 구간 1,615곳은 다리가 끝냈다(`bridged-window`).
- 다리 없이 다른 7곳은 다음 수에 같아진다: Piter 뒤 `pending_track_spies` 출처 이름 6(값은 같다), owed draw로 늦게 공개된 카드가 Fremen War Name의 +2를 그 단계에서 줌 1(옛 엔진은 다음 수에서 줬다).
- `collateral` 88: Scouts 경매 멈춤·줄 draw 67, 근처에 hit 없는 Navigation Chamber 갈라짐 19, 옛 엔진이 CHOAM Transports 카드를 한 수 동안 `tech_cards_owed`에 둔 것 2(v142는 붙잡은 draw로 둔다).
- `bridge-without-hit` 106곳 중 목록에 오른 100곳(97판)은 절반이 뽑는 다리였다. 옛 엔진은 다리 바로 뒤에 적힌 reshuffle chance에서 뽑았는데, 판정이 그 chance의 hit을 세지 않았다. 세도록 고친 판정(`07a2d425`)으로 97판을 다시 보니 25곳이 남고, 모두 뽑지 않는 다리다(경매 멈춤 22, garrison 답 3).

리뷰 반영 뒤의 코드(`records.migration.walk`)로 사람 판 v135, 테스트 기보 셋(v135·v139·v140), AI 판 v140 셋을 다시 대조했다. 결과는 위와 같다.

graft 두 칸 변환(codec v143, 2절 표의 `graft_switch`·`graft_box`)을 넣은 뒤 다시 쟀다(2026-10-12).
- `dune-imperium-records check`(로컬 저장본 6판: v135·v139·v141 ×2·v142 ×2): 6판 모두 끝까지 옮겨졌다. 지운 `switch_graft_card`는 판마다 9·0·9·9·12·18, `box=1`을 붙인 수는 6·0·9·8·10·14다. 6판 모두 마지막 상태(`decision_stack`·`event_log`·`revision` 제외)의 해시가 switch를 쓰던 엔진(`f88cd455`)으로 옮긴 것과 같다.
- `problems check`(사람 판 문제집 285곳): 285곳 모두 풀린다. 판정 수가 `switch_graft_card`인 곳이 없어 빠진 곳은 0이다. 칸 1이 활성인 자리가 10곳이고, 그중 4곳은 사람 수에 `box=1`을 붙였다.
- `corpus check local/records-corpus/v142-c29f79d1`(2,000판, 3코어 약 7분): exact 560, equal 1,436, transient 0, persistent 0, diverged 4, failed 0.
  - 다리 쓰임: `graft_box` 11,474수(1,434판), `graft_switch` 14,682수(1,440판).
  - 갈라진 4판은 2절의 v143 경우다(Ghola + Stitched Horror 1, 잠금 3). 판정은 4판 모두 `collateral`이다. 잠금 3판은 리뷰 뒤(`graft_box_held`)에는 "그 칸의 수가 다른 칸의 선택이 끝날 때까지 기다린다"는 이유로 같은 수에서 멈춘다. 그 전에는 같은 수가 불법이라는 이유로 멈췄다. 결과 수는 리뷰 전후가 같다. 셋은 갈라진 자리에서도 필드 차이가 없고, Ghola 판은 그 좌석의 자원·병력이 다르다(옛 엔진이 다시 준 보상과 병력).
  - 갈라지기 전까지 필드가 다른 구간은 없다.
- 리뷰 반영(잠금 교착 수정, `graft_box_held`) 뒤 세 측정을 다시 돌렸고, 수는 모두 같다.

codec v144(턴 종료를 막는 선택 box — OQ-057 (1) 보강, Bene Gesserit graft 상대의 Urgent Shigawire 부스트 — OQ-107)와 다리 둘(`shigawire_partner_draw`, `box_refused_at_turn_end`)을 넣은 뒤 다시 쟀다(2026-10-12).
- `dune-imperium-records check`(로컬 저장본 6판): 6판 모두 끝까지 옮겨졌고 다리 쓰임은 v143 때와 같다(새 다리 0회). 6판 모두 마지막 상태의 해시(`canonical_state_hash` 전체)가 v143 엔진(`944bb1b7`)으로 옮긴 것과 같다.
- `problems check`(사람 판 문제집 285곳): 285곳 모두 풀린다.
- `corpus check v143-944bb1b7`(2,000판, worker 2, 약 11분): exact 1,861, equal 5, transient 0, persistent 1, diverged 133, failed 0.
  - 다리 쓰임: `box_refused_at_turn_end` 5수(5판, 모두 Dissecting Kit — 그 5판이 equal), `shigawire_partner_draw` 2수(2판).
  - 갈라진 133판: 132판은 Faction space의 Beguiling Pheromones trash를 남긴 채 누른 턴 종료다(2절의 v144 경우, 규칙 수정; 그중 17판은 조건을 기다리는 다른 box(Fremen War Name, Lisan al Gaib 등)나 거절만 남은 Tleilaxu Surgeon이 함께 있다). Stitched Horror를 남긴 판은 없었다. 1판(`no-scouts-epic.h4.144`)은 `shigawire_partner_draw`가 뽑은 카드가 뒤의 Reveal에서 표본 만들기를 요구해 적힌 `finish_reveal`이 그 선택을 만난다(2절).
  - persistent 1판(`full.ha.67`): `shigawire_partner_draw`가 뽑은 카드가 손패·덱·play에 끝까지 남고, 부스트가 옛 판보다 일찍 소비된다(`bene_gesserit_boost_pending`). 판정은 133판과 함께 모두 `collateral`이고, 갈라지기 전까지 필드가 다른 구간은 없다.

v135 기보의 차이는 모두 **Conflict 보상을 주는 도중**이다.
- 옛 엔진은 받는 사람들의 자동 보상을 한꺼번에 주고 선택을 물었다. 지금 엔진은 받는 사람 순서대로 준다.
- 보상이 끝나면 다시 같아진다. 그 자리의 선택은 같지만, 그때 보이던 **다른 사람의** 자원이 조금 다르다.

테스트(`tests/unit/records/test_record_migration.py`)가 지키는 것:
- 이 엔진의 기보는 그대로 재생된다.
- 이 엔진의 기보에서 옛 엔진이 적지 않았을 것을 빼면, 다리를 거쳐 원래 수와 해시로 돌아온다. 뺀 것은 멈춤, 거절밖에 없던 창, 다른 좌석으로 넘어가기 전의 pass다.
- codec 문턱을 넘은 기보에서는 그 다리가 끼어들지 않는다.
- 결정의 답이었던 수에는 다리가 끼어들지 않는다. 그 종류의 행동이 지금 하나도 없을 때도 마찬가지다.
- 다른 곳에서 빠진 인자(`discount`)는 선택이므로 다시 쓰지 않고 멈춘다.
- 옛 엔진이 실제로 쓴 기보 열아홉 개가 끝까지 재생된다. 어느 기보가 무엇을 지키는지는 테스트 모듈 머리말과 `OQ106_FIXTURES`에 있다.
  - v135 app_ai seed 3, v139 heuristic seed 1, v140 heuristic seed 1
  - v141 다섯: IP 둘, garrison 하나, Prison Planet 둘
  - v141 열하나(OQ-106, 1~5라운드): Shigawire, Cunning·Insider와 그 reshuffle, Piter(reshuffle 뒤 Research, 곧바로 끝나는 Research 뒤 reshuffle), Reverse Engineering 둘(Servo-Receivers, reshuffle), Water Discipline(reshuffle), 경매 멈춤, owed draw 둘(Overthrow 카드를 Intrigue 선택에서 trash, Hungry for Spice의 reshuffle), Foe 둘(부여 한 번에 한 번만)
- OQ-106 다리는 적힌 수 바로 뒤에 그 단계를 넣는다. 기보마다 어느 적힌 수 뒤에 몇 번 넣는지를 정확히 대조한다(거절을 기다리면 늦거나 못 넣는다). 옮긴 수를 v142로 찍으면 다리 없이 그대로 재생된다(문턱이 없으면 다리가 그 단계를 먼저 가져간다).
- reshuffle 이름은 같은 좌석·같은 버림 더미일 때만 바꾼다(다른 좌석, 다른 값, Intrigue reshuffle, v142 기보는 멈춘다). 한 수 뒤의 다리가 정해진 수(32)를 넘으면 그 수에서 멈춘다. 경매 멈춤 직후에 끝나는 기보는 다음 승자의 보상까지 준 상태로 끝난다.
- turn 종료 누름이 번 draw로 다시 열린 turn은 v141 기보에 없어서, 만든 상태(Usurp한 Replacement Eyes가 Tleilaxu token을 Intrigue 칸으로)로 `refinish_agent_turn`을 지킨다.
- v142 문턱: 같은 v141 기보를 v142로 찍으면 v142 다리가 끼어들지 않고 멈춘다.
- IP 뽑기는 회수 바로 다음에 들어간다. v141 heuristic seed 1023은 회수 뒤에 엔진이 받아들이는 수(`decline_tech`)가 와서, 거절을 기다리는 방식이면 한 수 늦게 뽑는다.
- OQ-105 다리 둘은 그 결정에 대한 좌석 자신의 답(지금은 불법)에는 끼어들지 않는다. Prison Planet 거절은 옛 엔진이 물었던 좌석(병력 참가 가능)에는 하지 않는다.
- 다리 하나씩, 문턱 하나씩, 안전장치를 빼면 각각 해당 테스트가 실패하는 것을 확인했다.
  - 리뷰가 찾은 빈틈(IP 타이밍 테스트가 두 방식을 구별하지 못함, OQ-105 안전장치 미검증)도 그렇게 막았다.
  - OQ-106 다리 열하나는 각각 빼기, 문턱 없애기, `follows`(또는 rewrite·거절) 종류 뒤집기 33가지와 고정점을 한 번 묻기로 되돌리기 1가지를 모두 테스트가 잡는다. 안쪽 조건도 다섯 가지를 확인했다: Foe의 부여 한 번 조건, Piter 순서를 카드 먼저·Research 먼저로 고정, reshuffle 이름의 좌석·더미 조건, turn 다시 닫기의 "다시 열렸는가" 조건.
  - Prison Planet의 Commander 대상 조건과 틀 확인은 지금 엔진에서 빠져도 결과가 같은 방어용이다. 코드 주석에 적었다.

옛 엔진 기보를 다시 만드는 법은 `scripts/records/old_engine_record.py` 머리말에 있다. 그 스크립트가 같은 파일을 바이트까지 똑같이 만든다. 사람 기보는 공개 저장소에 넣지 않으려고 AI 판을 썼다.

## 4. 쓰는 법

```bash
uv run dune-imperium-records check
```

`saves/`의 저장본을 판마다 하나씩 읽는다(`one_save_per_game`). 같은 판은 룰셋, 시드, 좌석 배정이 같은 저장본들이다. 자동 저장, 수동 저장, 그리고 불러온 세션의 저장본(불러오면 게임 id가 새로 생기지만 좌석은 그대로다)이 여기에 든다. 룰셋과 시드가 같아도 좌석이 다르면(기보 corpus의 좌석 조합처럼) 다른 판이다.
- 판의 줄기는 가장 새 **끝난** 저장본을 지난다. 끝난 것이 없으면 가장 새 저장본을 지난다.
- 줄기 위의 저장본(하나가 다른 하나의 앞부분)은 같은 판이고, 수가 가장 많은 것을 쓴다.
- 줄기 밖의 저장본은 버린다. 무르고 다르게 둔 갈래나, 불러와 잠깐 다르게 둬 본 갈래다.

`--every-save`는 모두 본다. 결과는 넷 중 하나다.
- 그대로 재생(exact)
- 옮김(migrated, 쓴 다리와 횟수)
- 갈라짐(diverged, 몇 번째 수, 엔진이 기다린 결정)
- 엔진 오류(failed). 그 판만 보고하고 다음 판으로 간다.

2026-10-10 로컬 결과는 네 판 중 2판 exact, 2판 migrated다. codec v142(OQ-106 다리 포함)에서는 네 판 모두 migrated다. 모두 v142보다 옛 판이라 v142 다리를 쓴다.

코드에서는 다음과 같이 쓴다.
- `records.saves.saved_games(디렉터리)` → `SavedGame`
- `human_decisions(game)` → 사람이 둔 수마다 그 직전 상태, 합법 행동, 고른 수(`HumanDecision`). 다리가 넣은 수는 사람의 선택이 아니므로 빠진다.
- 진단 도구 `scripts/records/human_diagnosis.py`가 이것을 쓴다.
- `records.problems`: 진단에서 두 판정이 일치한 포지션을 기보째 고정한 문제집이다. 포지션은 이 이전으로 되살린다. 채점은 `dune-imperium-records problems check|score`([evaluation/human-games-2026-10-10.md](evaluation/human-games-2026-10-10.md) 6절).
  - **지운 거절(2026-10-23):** 옛 엔진에서 판정한 수가 2절의 `optional_refusal`·`turn_row_refusal` 거절이면 그 수만 따로 옮길 다리가 없다. 거절은 상태를 바꾸지 않고, 이 엔진에서는 그 효과가 turn에 남았다가 턴 종료에 사라진다.
    - 사람이 거절하고(같은 좌석의 지운 거절이 더 이어져도) 바로 자기 턴을 끝냈으면, 이 엔진에서는 그 자리에서 "턴 종료" 한 번이 같은 결정이다. 그래서 그 턴 종료 앞 국면에서, 턴 종료를 사람의 수로 묻는다(`885ed2f0:578`·`:756`, `decline_tech` 뒤 `finish_agent_turn`). 판정은 거절 뒤를 망이 이어 둔 값이었고 다시 판정하지는 않았다.
    - 거절 뒤에 다른 수를 둔 사람, 그리고 망의 거절은 "그 효과를 두고 계속 둔다"는 선택이다. 이 엔진에는 그것을 한 수로 하는 행동이 없다. 앞의 것은 그대로 "the person's move at step N has no counterpart on this engine (optional_refusal)", 뒤의 것은 "the network's move <id> has no counterpart on this engine (optional_refusal|turn_row_refusal)"로 보고하고 채점에서 뺀다(`8f8df4bc:765`·`fb716981:447`의 Twisted Mentat 회수 거절, `c3adefb4:471`·`fb716981:607`의 turn 안 trash 거절 — 이 4곳은 같은 날 사용자 결정으로 문제집에서 뺐다). 이 엔진이 그 자리에서 아직 내는 거절(turn 밖 Water Discipline의 trash 창 등)은 그대로 묻는다.

## 5. 한계

- **서버의 불러오기는 그대로다.** 옛 저장본으로 게임을 이어 두지는 못한다. 이어 두려면 세션 로그(무르기 기록)와 AI 좌석의 난수 재현까지 옮겨야 한다. 지금 필요한 것은 판 자체뿐이라 하지 않았다.
- **보장은 "적힌 모든 수가 지금 엔진에서 합법"까지다.** 규칙 수정이 어떤 카드의 결과를 바꾸면, 그 뒤의 상태는 사람이 본 것과 조금 다를 수 있다. 3절의 대조는 v135·v139에서 그런 차이가 보상 순서뿐이었다는 증거다. 앞으로의 변경에는 같은 대조를 다시 해야 안다.
- 흐름을 바꾸는 codec 변경 때 `dune-imperium-records check`를 돌려 보는 것이 가장 싸다. 그때 고치면 무엇이 바뀌었는지 아직 기억한다.
